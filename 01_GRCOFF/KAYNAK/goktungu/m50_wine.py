# -*- coding: utf-8 -*-
"""GÖKTUNGU — M50 SDK'sı için WINE KÖPRÜ VEKİLİ (Linux tarafı).

v2.4.216 — Kullanıcı kararı: "Wine köprü süreci" (Ubuntu'da M50).

Üreticinin SDK'sı yalnız Windows x64 DLL'idir. Linux'ta Merkez, gömülü
Windows Python'u `wine64` altında ayrı bir yardımcı süreçte
(`m50_sdk_servis.py`) çalıştırır; bu sınıf (`M50WineIstemcisi`)
`m50_hvs.M50Istemcisi` ile AYNI yüzü sunar ve her çağrıyı 127.0.0.1
üzerinde JSON satırıyla yardımcı sürece iletir. `m50_yerel.py` için fark
yoktur: Windows'ta doğrudan DLL, Linux'ta Wine vekili.

Gereksinimler (Ubuntu): `wine64` (veya `wine`) paketi kurulu olmalı;
gömülü Windows Python zip'i Merkez paketiyle gelir
(`/opt/goktungu/merkez/wine/python-3.11.9-embed-amd64.zip`) ve veri
kökündeki `wine/python` dizinine ilk kullanımda açılır. WINEPREFIX veri
kökünde tutulur (`ProtectSystem=strict` altında tek yazılabilir yer).

Sınırlar / bilinen riskler: Wine altında `winsock` + `ctypes` geri
çağrıları çalışır; SDK'nın grafik penceresi isteyen yolları (PlayVideo)
kullanılmaz (Merkez RTSP'den okur). Sahada doğrulama gerekir; yardımcı
süreç yanıt vermezse `M50Hata` ile açık hata döner, Merkez kilitlenmez.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
import threading
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional

from .m50_hvs import M50Hata

WINE_ADAYLARI = ("wine64", "wine")
PY_EMBED_AD = "python-3.11.9-embed-amd64.zip"
ISTEK_ZAMAN_ASIMI = 25.0     # SDK bağlanma denemesi (timeout 5000 ms + pay)
BASLATMA_ZAMAN_ASIMI = 40.0  # Wine ilk açılışta prefix kurar; yavaş olabilir


def wine_yolu() -> Optional[str]:
    for ad in WINE_ADAYLARI:
        y = shutil.which(ad)
        if y:
            return y
    return None


def _veri_koku() -> Path:
    try:
        from . import sabitler as _sb
        return Path(getattr(_sb, "VERI_KOKU", "."))
    except Exception:
        return Path(os.environ.get("GOKTUNGU_VERI_KOKU", "."))


def _paket_koku() -> Path:
    """/opt/goktungu/merkez (assets/python/goktungu/.. yukarı üç dizin)."""
    return Path(__file__).resolve().parent.parent.parent.parent


def _embed_zip_adaylari():
    kok = _paket_koku()
    yield kok / "wine" / PY_EMBED_AD
    yield Path(__file__).resolve().parent.parent.parent / "gomulu_merkez" / PY_EMBED_AD
    yield Path(os.environ.get("GOKTUNGU_WINE_PYTHON_ZIP", "") or "/nonexistent")


def kullanilabilir() -> bool:
    """Linux'ta Wine köprüsü kurulabilir mi? (wine + gömülü Python zip'i)."""
    if platform.system().lower() != "linux":
        return False
    if wine_yolu() is None:
        return False
    return any(p.is_file() for p in _embed_zip_adaylari())


def eksik_gerekce() -> str:
    if platform.system().lower() != "linux":
        return "Wine köprüsü yalnız Linux'ta kullanılır"
    if wine_yolu() is None:
        return "wine64 kurulu değil (sudo apt install wine64)"
    if not any(p.is_file() for p in _embed_zip_adaylari()):
        return "gömülü Windows Python paketi (%s) bulunamadı" % PY_EMBED_AD
    return ""


def _linux_to_wine(yol: Path) -> str:
    return "Z:" + str(yol.resolve()).replace("/", "\\")


class M50WineIstemcisi:
    """`M50Istemcisi` yüzü; her yordam Wine'daki yardımcı sürece iletilir."""

    def __init__(self, yaz=None, ayar_oku=None, ayar_yaz=None, eo_id: int = 1):
        self._yaz = yaz or (lambda _m, _s="bilgi": None)
        self._ayar_oku = ayar_oku or (lambda: {})
        self._eo_id = int(eo_id or 1)
        self._kilit = threading.RLock()
        self._surec: Optional[subprocess.Popen] = None
        self._sok: Optional[socket.socket] = None
        self._okuyucu = None
        self._yazici = None
        self._sayac = 0
        self._port = 0
        self._son_durum: Dict[str, Any] = {
            "tur": "m50", "durum": "kapali", "bagli": False, "sdk_hazir": False,
            "ip": "", "port": 0, "hata": "", "azimut": None, "egim": None,
            "takip": {"etkin": False, "kanal": ""}, "tarama": {"tur": "yok", "kontrol": "durdur", "yol": 0},
            "konum": None, "pusula": None, "video": {"gorunur": False, "termal": False},
            "son_islem": "", "guncelleme": time.time(), "wine": True,
        }

    # ---- M50Istemcisi ile aynı statik yüz (m50_yerel.kullanilabilir) ----
    @staticmethod
    def _sdk_kok(ayar: Dict[str, Any]) -> Path:
        from .m50_hvs import M50Istemcisi
        return M50Istemcisi._sdk_kok(ayar)

    # ------------------------------------------------------------------
    # Yardımcı süreç yaşam döngüsü
    # ------------------------------------------------------------------
    def _python_hazirla(self) -> Path:
        hedef = _veri_koku() / "wine" / "python"
        exe = hedef / "python.exe"
        if exe.is_file():
            return exe
        zipy = next((p for p in _embed_zip_adaylari() if p.is_file()), None)
        if zipy is None:
            raise M50Hata("Wine köprüsü: gömülü Windows Python paketi bulunamadı")
        hedef.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zipy) as z:
            z.extractall(hedef)
        # Gömülü Python'da `import site` kapalıdır; kendi betiğimiz yola
        # göre yüklenir, ek paket gerekmez. `._pth` içindeki `.` kökü yeter.
        if not exe.is_file():
            raise M50Hata("Wine köprüsü: python.exe açılamadı")
        return exe

    def _baslat(self) -> None:
        wine = wine_yolu()
        if wine is None:
            raise M50Hata("Wine köprüsü: wine64 kurulu değil (sudo apt install wine64)")
        exe = self._python_hazirla()
        prefix = _veri_koku() / "wine" / "prefix"
        prefix.mkdir(parents=True, exist_ok=True)
        # Boş port seç
        s = socket.socket(); s.bind(("127.0.0.1", 0)); self._port = s.getsockname()[1]; s.close()
        burada = Path(__file__).resolve().parent
        sdk_dizin = None
        try:
            sdk_dizin = self._sdk_kok(self._ayar_oku() or {})
        except Exception:
            sdk_dizin = burada / "m50_sdk"
        self._jeton = os.urandom(12).hex()
        env = dict(os.environ)
        env.update({
            "WINEDEBUG": "-all", "WINEPREFIX": str(prefix), "WINEARCH": "win64",
            "HOME": str(_veri_koku() / "wine"), "WINEDLLOVERRIDES": "mscoree,mshtml=",
            "DISPLAY": "",
        })
        cmd = [wine, _linux_to_wine(exe), _linux_to_wine(burada / "m50_sdk_servis.py"),
               "--port", str(self._port), "--sdk", _linux_to_wine(burada),
               "--sdk-dizin", _linux_to_wine(Path(sdk_dizin)), "--jeton", self._jeton]
        self._yaz("Wine köprüsü başlatılıyor: %s (port %d)" % (os.path.basename(wine), self._port))
        try:
            self._surec = subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                           cwd=str(_veri_koku() / "wine"))
        except OSError as exc:
            raise M50Hata("Wine köprüsü başlatılamadı: %s" % exc) from exc
        threading.Thread(target=self._stderr_dongu, daemon=True).start()
        # Bağlanmayı bekle
        son = time.time() + BASLATMA_ZAMAN_ASIMI
        while time.time() < son:
            if self._surec.poll() is not None:
                raise M50Hata("Wine köprüsü süreci çıktı (kod %s); günlüğe bakın" % self._surec.returncode)
            try:
                sok = socket.create_connection(("127.0.0.1", self._port), timeout=2.0)
                sok.settimeout(ISTEK_ZAMAN_ASIMI)
                self._sok = sok
                self._okuyucu = sok.makefile("r", encoding="utf-8", newline="\n")
                self._yazici = sok.makefile("w", encoding="utf-8", newline="\n")
                self._ham_cagir("jeton", jeton=self._jeton)
                cevap = self._ham_cagir("ping")
                self._yaz("Wine köprüsü hazır (yardımcı %s)" % (cevap.get("surum") if isinstance(cevap, dict) else cevap))
                return
            except (OSError, M50Hata):
                time.sleep(0.5)
        self.kapat()
        raise M50Hata("Wine köprüsü %d sn içinde yanıt vermedi" % int(BASLATMA_ZAMAN_ASIMI))

    def _stderr_dongu(self) -> None:
        p = self._surec
        if p is None or p.stderr is None:
            return
        for satir in p.stderr:
            try:
                m = satir.decode("utf-8", "replace").rstrip()
            except Exception:
                continue
            if m and "err:" not in m[:5]:
                self._yaz("[wine] " + m[:300], "uyari" if "uyari" in m or "Traceback" in m else "bilgi")

    def kapat(self) -> None:
        with self._kilit:
            try:
                if self._yazici is not None:
                    self._yazici.write(json.dumps({"id": 0, "yordam": "kapat"}) + "\n"); self._yazici.flush()
            except Exception:
                pass
            for f in (self._okuyucu, self._yazici, self._sok):
                try:
                    if f is not None:
                        f.close()
                except Exception:
                    pass
            self._okuyucu = self._yazici = self._sok = None
            if self._surec is not None:
                try:
                    self._surec.wait(timeout=3)
                except Exception:
                    try:
                        self._surec.kill()
                    except Exception:
                        pass
                self._surec = None

    def _hazir_et(self) -> None:
        if self._sok is not None and self._surec is not None and self._surec.poll() is None:
            return
        self.kapat()
        self._baslat()

    # ------------------------------------------------------------------
    # Çağrı taşıma
    # ------------------------------------------------------------------
    def _ham_cagir(self, yordam: str, *args: Any, **kwargs: Any) -> Any:
        self._sayac += 1
        istek: Dict[str, Any] = {"id": self._sayac, "yordam": yordam}
        if yordam == "jeton":
            istek["jeton"] = kwargs.get("jeton", "")
        else:
            istek["args"] = list(args)
            istek["kwargs"] = dict(kwargs)
        assert self._yazici is not None and self._okuyucu is not None
        self._yazici.write(json.dumps(istek) + "\n")
        self._yazici.flush()
        satir = self._okuyucu.readline()
        if not satir:
            raise OSError("Wine köprüsü bağlantısı kapandı")
        yanit = json.loads(satir)
        if "hata" in yanit:
            raise M50Hata(str(yanit["hata"]))
        if yordam == "ping":
            return yanit
        return yanit.get("sonuc")

    def _cagir(self, yordam: str, *args: Any, **kwargs: Any) -> Any:
        with self._kilit:
            self._hazir_et()
            try:
                sonuc = self._ham_cagir(yordam, *args, **kwargs)
            except (OSError, ValueError) as exc:
                # Bağlantı koptu: bir kez yeniden başlat ve tekrar dene
                self._yaz("Wine köprüsü bağlantısı koptu (%s); yeniden başlatılıyor" % exc, "uyari")
                self.kapat()
                self._baslat()
                sonuc = self._ham_cagir(yordam, *args, **kwargs)
            if isinstance(sonuc, dict) and "durum" in sonuc and "bagli" in sonuc:
                self._son_durum = dict(sonuc)
                self._son_durum["wine"] = True
            return sonuc

    # ------------------------------------------------------------------
    # M50Istemcisi yüzü
    # ------------------------------------------------------------------
    def durum(self) -> Dict[str, Any]:
        # Yardımcı süreç hiç başlatılmadıysa cihaz kapalıdır; süreç
        # başlatmak için bağlan komutu beklenir (boşta Wine açılmaz).
        if self._sok is None:
            d = dict(self._son_durum)
            d["takip"] = dict(d.get("takip") or {})
            d["video"] = dict(d.get("video") or {})
            return d
        try:
            return self._cagir("durum")
        except M50Hata as exc:
            d = dict(self._son_durum); d.update({"durum": "hata", "bagli": False, "hata": str(exc)})
            return d

    def baglan(self, veri):            return self._cagir("baglan", veri)
    def kes(self):
        try:
            return self._cagir("kes")
        finally:
            pass
    def ptz(self, yon, hiz, basili=True):          return self._cagir("ptz", yon, hiz, basili)
    def lens(self, eylem, kanal, basili=True):     return self._cagir("lens", eylem, kanal, basili)
    def aci_konumla(self, azimut, egim, hiz):      return self._cagir("aci_konumla", azimut, egim, hiz)
    def aci_oku(self):                              return self._cagir("aci_oku")
    def takip_sec(self, kanal, video_dikdortgen, secim): return self._cagir("takip_sec", kanal, video_dikdortgen, secim)
    def takip_baslat(self, kanal, mod="hava_yari_otomatik"): return self._cagir("takip_baslat", kanal, mod)
    def takip_durdur(self, kanal):                  return self._cagir("takip_durdur", kanal)
    def takip_yetenek(self, kanal, etkin=True):     return self._cagir("takip_yetenek", kanal, etkin)
    def onayarlar(self):                            return self._cagir("onayarlar")
    def onayar_kaydet(self, no, ad, hiz=5):         return self._cagir("onayar_kaydet", no, ad, hiz)
    def onayar_cagir(self, no):                     return self._cagir("onayar_cagir", no)
    def onayar_sil(self, no):                       return self._cagir("onayar_sil", no)
    def onayar_hepsini_sil(self):                   return self._cagir("onayar_hepsini_sil")
    def tarama(self, tur, kontrol, yol=0):          return self._cagir("tarama", tur, kontrol, yol)
    def konum_oku(self):                            return self._cagir("konum_oku")
    def rtsp_url(self, kanal):                      return self._cagir("rtsp_url", kanal)
    def osd_oku(self, kanal):                       return self._cagir("osd_oku", kanal)
    def osd_yaz(self, kanal, alanlar):              return self._cagir("osd_yaz", kanal, alanlar)
