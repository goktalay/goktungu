# -*- coding: utf-8 -*-
"""GOKTUNGU - PYTHON MAKROLARI (v2.4.243, IS137).

## KULLANICI ISTEGI (birebir)

    "dronlar icin uygulanmak uzere python makrolari olusturabilecegim bir
     sistem ... Rotalar menusu altinda makrolar diye bir menu olsun,
     standart kayit paneli olarak acilsin, yeni makro dediğimde bana makro
     ismini sorsun, kaydet dersem makroyu olustursun ve listeye gelsin,
     listede yaninda script ikonu gorunsun, buna tiklayinca python
     duzenleme paneli acilsin, ... kullanabilecegim degiskenleri sen altta
     listele ... mavutil'e erisim lazim"

## NE YAPAR

* `MakroKayitlari`: `makrolar` tablosu (ad, aciklama, kod, sure_sn,
  firma_id). Kod metni tabloda TEXT olarak durur (rotalar.meta gibi).
* `MakroCalistirici`: makroyu AYRI, KISITLI bir Python surecinde kosar
  (`makro_kosucu.py`). Dron erisimi, GCS'in her dron icin zaten actigi
  9000+sysid MAVLink UDP aynasi uzerindendir (`udp_yayin.py`); makro
  surecine `mavutil` baglantisi (`mav`) ve kolay islevler (`dron`) verilir.
  Cikti satirlari halka tamponda tutulur ve `kanca` ile arayuze akar.

## NEDEN AYRI SUREC

Kullanici kodu GCS sureci icinde `exec` edilseydi tek bir sonsuz dongu
telemetri dongusunu kilitler, bir istisna sunucuyu dusururdu. Ayri surec
+ kaynak sinirlari (bellek, CPU, dosya) + yalniz-127.0.0.1 soket kurali
bu riskleri sinirlar. Merkez kipinde (GRCON) makro calistirma yetkisi
`dron_komut` ile AYNI izne baglidir: makro araci arm edip ucurabilir.
"""
from __future__ import annotations

import atexit
import collections
import contextlib
import json
import os
import subprocess
import sys
import threading
import time

from . import veritabani
from .sabitler import _veri_alt_yolu

KOD_ENUST = 200_000
CIKTI_ENUST_SATIR = 2000
VARSAYILAN_SURE_SN = 3600


class MakroKayitlari:
    ALANLAR = ("ad", "aciklama", "kod", "sure_sn")

    @staticmethod
    def _temiz(kayit):
        k = {}
        ad = str((kayit or {}).get("ad") or "").strip()
        if "ad" in (kayit or {}):
            k["ad"] = ad[:64] or "Makro"
        if "aciklama" in (kayit or {}):
            k["aciklama"] = str(kayit.get("aciklama") or "")[:500]
        if "kod" in (kayit or {}):
            k["kod"] = str(kayit.get("kod") or "")[:KOD_ENUST]
        if "sure_sn" in (kayit or {}):
            try:
                k["sure_sn"] = max(0, min(86400, int(kayit.get("sure_sn") or 0)))
            except (TypeError, ValueError):
                k["sure_sn"] = VARSAYILAN_SURE_SN
        return k

    def listele(self, firma_id=None, kod_dahil=False):
        kolonlar = "id, ad, aciklama, sure_sn, firma_id, guncelleme_ts" + (", kod" if kod_dahil else "")
        with veritabani.baglanti() as con:
            if firma_id:
                rows = con.execute(
                    "SELECT %s FROM makrolar WHERE (firma_id = ? OR firma_id IS NULL) ORDER BY id" % kolonlar,
                    (int(firma_id),)).fetchall()
            else:
                rows = con.execute("SELECT %s FROM makrolar ORDER BY id" % kolonlar).fetchall()
        return [dict(r) for r in rows]

    def bul(self, makro_id):
        with veritabani.baglanti() as con:
            row = con.execute("SELECT * FROM makrolar WHERE id = ?", (int(makro_id),)).fetchone()
        return dict(row) if row else None

    def firma_ata(self, makro_id, firma_id):
        if not firma_id:
            return
        with veritabani.baglanti() as con:
            con.execute("UPDATE makrolar SET firma_id = ? WHERE id = ? AND firma_id IS NULL",
                        (int(firma_id), int(makro_id)))

    def ekle(self, kayit):
        k = self._temiz(kayit)
        k.setdefault("ad", "Makro")
        k.setdefault("aciklama", "")
        k.setdefault("kod", "")
        k.setdefault("sure_sn", VARSAYILAN_SURE_SN)
        with veritabani.baglanti() as con:
            cur = con.execute(
                "INSERT INTO makrolar (ad, aciklama, kod, sure_sn, guncelleme_ts) VALUES (?,?,?,?,?)",
                (k["ad"], k["aciklama"], k["kod"], k["sure_sn"], time.time()))
            return int(cur.lastrowid)

    def guncelle(self, makro_id, kayit):
        k = self._temiz(kayit)
        if not k:
            return False
        k["guncelleme_ts"] = time.time()
        sutunlar = ", ".join("%s = ?" % a for a in k)
        with veritabani.baglanti() as con:
            cur = con.execute("UPDATE makrolar SET %s WHERE id = ?" % sutunlar,
                              tuple(k.values()) + (int(makro_id),))
            return cur.rowcount > 0

    def sil(self, makro_id):
        with veritabani.baglanti() as con:
            con.execute("DELETE FROM makrolar WHERE id = ?", (int(makro_id),))


class _Calisma:
    __slots__ = ("makro_id", "sysid", "surec", "baslama_ts", "bitis_ts", "cikis_kodu",
                 "dosya", "sure_sn", "durduruldu", "son_hata")

    def __init__(self, makro_id, sysid, surec, dosya, sure_sn):
        self.makro_id = int(makro_id)
        self.sysid = int(sysid or 0)
        self.surec = surec
        self.dosya = dosya
        self.sure_sn = int(sure_sn or 0)
        self.baslama_ts = time.time()
        self.bitis_ts = 0.0
        self.cikis_kodu = None
        self.durduruldu = False
        self.son_hata = ""


class MakroCalistirici:
    """Makrolari kisitli alt surecte kosar; ciktiyi tamponlar ve kancaya verir."""

    def __init__(self, kayitlar, konsol=None, port_cozucu=None, portlar_cozucu=None):
        self.kayitlar = kayitlar
        self.konsol = konsol or (lambda *a, **k: None)
        self._port_cozucu = port_cozucu            # sysid -> udp port
        self._portlar_cozucu = portlar_cozucu      # () -> {sysid: port}
        self._calismalar = {}                      # makro_id -> _Calisma
        self._cikti = collections.defaultdict(lambda: collections.deque(maxlen=CIKTI_ENUST_SATIR))
        self._kilit = threading.Lock()
        self.kanca = None                          # (makro_id, satirlar, durum) -> None
        atexit.register(self.tumunu_durdur)
        self._bekleyen = collections.defaultdict(list)

    # ------------------------------------------------------------------
    @staticmethod
    def _pymavlink_yolu():
        try:
            import pymavlink
            return os.path.dirname(os.path.dirname(os.path.abspath(pymavlink.__file__)))
        except Exception:
            return ""

    def _kosucu_yolu(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "makro_kosucu.py")

    def _calisma_dizini(self):
        d = _veri_alt_yolu("makrolar", "calisma")
        os.makedirs(d, exist_ok=True)
        return d

    def calisiyor_mu(self, makro_id):
        with self._kilit:
            c = self._calismalar.get(int(makro_id))
        return bool(c and c.surec.poll() is None)

    def durum(self, makro_id):
        with self._kilit:
            c = self._calismalar.get(int(makro_id))
        if c is None:
            return {"durum": "hazir", "calisiyor": False}
        canli = c.surec.poll() is None
        if canli:
            d = "calisiyor"
        elif c.durduruldu:
            d = "durduruldu"
        elif c.cikis_kodu == 0:
            d = "bitti"
        else:
            d = "hata"
        return {"durum": d, "calisiyor": canli, "sysid": c.sysid,
                "baslama_ts": c.baslama_ts, "bitis_ts": c.bitis_ts,
                "cikis_kodu": c.cikis_kodu, "sure_sn": c.sure_sn,
                "gecen_sn": round((c.bitis_ts or time.time()) - c.baslama_ts, 1),
                "son_hata": c.son_hata}

    def durumlar(self):
        with self._kilit:
            idler = list(self._calismalar)
        return {str(i): self.durum(i) for i in idler}

    def cikti(self, makro_id):
        with self._kilit:
            return list(self._cikti.get(int(makro_id), []))

    def cikti_temizle(self, makro_id):
        with self._kilit:
            self._cikti.pop(int(makro_id), None)

    # ------------------------------------------------------------------
    def calistir(self, makro_id, sysid=None):
        """Makroyu baslatir. Doner `(tamam, hata)`."""
        makro_id = int(makro_id)
        if self.calisiyor_mu(makro_id):
            return False, "Makro zaten calisiyor"
        kayit = self.kayitlar.bul(makro_id)
        if not kayit:
            return False, "Makro kaydi bulunamadi"
        kod = kayit.get("kod") or ""
        if not kod.strip():
            return False, "Makro kodu bos"
        try:
            sysid = int(sysid or 0)
        except (TypeError, ValueError):
            sysid = 0
        port = 0
        if sysid and self._port_cozucu:
            try:
                port = int(self._port_cozucu(sysid) or 0)
            except Exception:
                port = 0
        portlar = {}
        if self._portlar_cozucu:
            try:
                portlar = {int(k): int(v) for k, v in (self._portlar_cozucu() or {}).items()}
            except Exception:
                portlar = {}
        dizin = self._calisma_dizini()
        dosya = os.path.join(dizin, "m%d.py" % makro_id)
        try:
            with open(dosya, "w", encoding="utf-8") as f:
                f.write(kod)
            os.chmod(dosya, 0o600)
        except OSError as e:
            return False, "Makro dosyasi yazilamadi: %s" % e
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": dizin, "TMPDIR": dizin, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
            "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
            "GOKTUNGU_MAKRO_ID": str(makro_id),
            "GOKTUNGU_MAKRO_AD": str(kayit.get("ad") or ""),
            "GOKTUNGU_MAKRO_SYSID": str(sysid),
            "GOKTUNGU_MAKRO_PORT": str(port),
            "GOKTUNGU_MAKRO_PORTLAR": json.dumps(portlar),
            "GOKTUNGU_MAKRO_SURE": str(int(kayit.get("sure_sn") or 0)),
            "GOKTUNGU_MAKRO_DIZIN": dizin,
            # -I kipinde kullanici site-packages ve PYTHONPATH yok sayilir;
            # pymavlink'in yeri ana surecten alinip cocuga bildirilir.
            "GOKTUNGU_MAKRO_PYMAVLINK_YOL": self._pymavlink_yolu(),
        }
        if sys.platform.startswith("win"):
            env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")
        komut = [sys.executable, "-I", "-u", self._kosucu_yolu(), dosya]
        kw = {"cwd": dizin, "env": env, "stdout": subprocess.PIPE,
              "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL}
        if sys.platform.startswith("win"):
            kw["creationflags"] = 0x08000000
        else:
            kw["start_new_session"] = True
        try:
            p = subprocess.Popen(komut, **kw)
        except Exception as e:
            return False, "Makro sureci baslatilamadi: %s: %s" % (type(e).__name__, e)
        c = _Calisma(makro_id, sysid, p, dosya, kayit.get("sure_sn") or 0)
        with self._kilit:
            self._calismalar[makro_id] = c
            self._cikti[makro_id].clear()
        self._satir_ekle(makro_id, "Makro basladi (sysid %s, port %s)" % (sysid or "-", port or "-"), "basari")
        threading.Thread(target=self._oku, args=(c,), daemon=True).start()
        threading.Thread(target=self._bekci, args=(c,), daemon=True).start()
        self.konsol("MAKRO", "Makro #%d '%s' baslatildi (sysid %s)" % (makro_id, kayit.get("ad") or "", sysid or "-"), "basari")
        return True, ""

    def durdur(self, makro_id):
        with self._kilit:
            c = self._calismalar.get(int(makro_id))
        if c is None or c.surec.poll() is not None:
            return False
        c.durduruldu = True
        self._sonlandir(c)
        return True

    def tumunu_durdur(self):
        with self._kilit:
            cs = list(self._calismalar.values())
        for c in cs:
            if c.surec.poll() is None:
                c.durduruldu = True
                self._sonlandir(c)

    @staticmethod
    def _sonlandir(c):
        p = c.surec
        with contextlib.suppress(Exception):
            p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(Exception):
                p.kill()
            with contextlib.suppress(Exception):
                p.wait(timeout=5)

    # ------------------------------------------------------------------
    def _satir_ekle(self, makro_id, metin, sev="bilgi"):
        satir = {"ts": time.time(), "metin": str(metin)[:2000], "sev": sev}
        with self._kilit:
            self._cikti[makro_id].append(satir)
            self._bekleyen[makro_id].append(satir)

    def _bosalt(self, makro_id, durum=None):
        with self._kilit:
            satirlar = self._bekleyen.pop(makro_id, [])
        if not satirlar and durum is None:
            return
        kanca = self.kanca
        if kanca:
            try:
                kanca(makro_id, satirlar, durum or self.durum(makro_id))
            except Exception:
                pass

    def _oku(self, c):
        p = c.surec
        son_bosaltma = time.time()
        try:
            for ham in iter(p.stdout.readline, b""):
                metin = ham.decode("utf-8", "replace").rstrip("\r\n")
                if not metin:
                    continue
                sev = "bilgi"
                if metin.startswith("[BILDIR] "):
                    sev = "bildir"
                elif metin.startswith("[HATA]") or metin.startswith("Traceback") or "Error" in metin[:40]:
                    sev = "hata"
                elif metin.startswith("[UYARI]"):
                    sev = "uyari"
                self._satir_ekle(c.makro_id, metin, sev)
                if time.time() - son_bosaltma >= 0.2:
                    self._bosalt(c.makro_id)
                    son_bosaltma = time.time()
        except Exception as e:
            c.son_hata = "%s: %s" % (type(e).__name__, e)
        p.wait()
        c.cikis_kodu = p.returncode
        c.bitis_ts = time.time()
        if c.durduruldu:
            self._satir_ekle(c.makro_id, "Makro durduruldu", "uyari")
        elif c.cikis_kodu == 0:
            self._satir_ekle(c.makro_id, "Makro bitti (%.1f sn)" % (c.bitis_ts - c.baslama_ts), "basari")
        else:
            self._satir_ekle(c.makro_id, "Makro hata ile bitti (cikis kodu %s)" % c.cikis_kodu, "hata")
        self._bosalt(c.makro_id, self.durum(c.makro_id))
        with contextlib.suppress(Exception):
            os.remove(c.dosya)

    def _bekci(self, c):
        while c.surec.poll() is None:
            time.sleep(0.5)
            if c.sure_sn and time.time() - c.baslama_ts > c.sure_sn:
                c.son_hata = "Zaman asimi (%d sn)" % c.sure_sn
                self._satir_ekle(c.makro_id, "Zaman asimi: makro %d sn sonra durduruldu" % c.sure_sn, "uyari")
                c.durduruldu = True
                self._sonlandir(c)
                break
