#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GRCOFF arka plan güncelleme servisi (dosya tabanlı).

NEDEN (2.5.26): Önceki model her güncellemede imzasız bir NSIS `.exe`
indirip çalıştırıyordu; Windows Defender bunu sezgisel olarak
`Trojan:Win32/Sabsik.FL.A!ml` diye karantinaya alıp güncellemeyi
`[Errno 22]` ile bozuyordu. Bu servis bunun yerine yalnız DEĞİŞEN düz
veri dosyalarını (.py/.js/.html/...) indirir — çalıştırılabilir kurulum
indirmez, dolayısıyla AV sezgiselini tetiklemez. Ayrıca yalnız değişen
dosyalar indiği için güncelleme küçük ve hızlıdır (artımlı).

ROL:
  1. Uygulamayı (main.py) alt süreç olarak başlatır ve ayakta tutar
     (uygulama çökse bile bu servis yaşar; yeniden başlatır).
  2. Belirli aralıklarla katalogtan İMZALI dosya manifesti çeker.
  3. Yerel dosyalarla karşılaştırır, yalnız sha256'sı farklı olanları
     indirir, her dosyayı doğrular.
  4. Uygulamayı durdurur, dosyaları ATOMİK yerleştirir, silinecekleri
     kaldırır, PostgreSQL göçü uygulamanın açılışında koşar, uygulamayı
     yeniden başlatır. Herhangi bir adım başarısızsa GERİ ALIR.

GÜVENLİK (savunma sistemi): manifest Ed25519 imzalı (gömülü açık
anahtar), yalnız goktungu.com HTTPS, her dosya sha256 doğrulanır,
lisans kimliği zorunlu, dizin-gezinme koruması, atomik uygulama + geri
alma. Bu modül cv2/psycopg2 gibi ağır/yerel bağımlılık İÇE ALMAZ.
"""
from __future__ import annotations

import hashlib
import json
import os
import ssl
import sys
import time
import urllib.request

KATALOG = "https://goktungu.com"
MANIFEST_YOLU = "/api/istemci/dosya_manifesti"
DOSYA_YOLU = "/api/istemci/dosya"
# Güncellemeyle YÖNETİLEN kökler (yalnız bunların altındaki dosyalar
# yazılır/silinir). Kullanıcı verisi (veri/, ai_kayitlar/, *.log,
# merkez_lisans.json, pg.json) ASLA dokunulmaz.
YONETILEN_KOKLER = ("assets/", "ai_modeller/")
YONETILEN_DOSYALAR = ("main.py", "requirements.txt", "goktungu_guncelleyici.py")
KORUNAN = ("veri/", "ai_kayitlar/", "gunluk/", "telemetri_tampon/")
_BLOK = 256 * 1024
_AZAMI_DOSYA = 80 * 1024 * 1024


def _sha256_dosya(yol: str) -> str:
    h = hashlib.sha256()
    try:
        with open(yol, "rb") as f:
            for blok in iter(lambda: f.read(_BLOK), b""):
                h.update(blok)
    except OSError:
        return ""
    return h.hexdigest()


def _guvenli_bilesenler(bagil: str):
    """Manifest yolunu güvenli göreli parçalara çevirir; kötüyse None."""
    bagil = str(bagil or "").replace("\\", "/")
    if not bagil or bagil.startswith("/") or ".." in bagil.split("/"):
        return None
    # Sürücü harfi / iki nokta / geri gidiş yok
    if ":" in bagil:
        return None
    parcalar = [p for p in bagil.split("/") if p not in ("", ".")]
    return parcalar or None


def _yonetilen_mi(bagil: str) -> bool:
    b = bagil.replace("\\", "/")
    if any(b == d or b.startswith(k) for k in KORUNAN for d in ()):
        return False
    if any(b.startswith(k) for k in KORUNAN):
        return False
    return b in YONETILEN_DOSYALAR or any(b.startswith(k) for k in YONETILEN_KOKLER)


class GuncellemeMotoru:
    """Manifest çek → farkı bul → indir → uygula. Ağ enjekte edilebilir
    (sınav için `_getir` ve `_dosya_getir` override edilir)."""

    def __init__(self, kok: str, urun: str, mevcut_surum: str,
                 lisans_belgesi=None, gunluk=print):
        self.kok = os.path.abspath(kok)
        self.urun = urun
        self.mevcut_surum = mevcut_surum
        self.lisans_belgesi = lisans_belgesi or {}
        self.gunluk = gunluk

    # -- ağ (gerçek) --------------------------------------------------
    def _istek(self, yol, govde):
        veri = json.dumps(govde, ensure_ascii=False).encode("utf-8")
        return urllib.request.Request(
            KATALOG + yol, data=veri, method="POST",
            headers={"Content-Type": "application/json",
                     "User-Agent": "GOKTUNGU-Guncelleyici/" + self.mevcut_surum})

    def _getir_manifest(self) -> dict:
        istek = self._istek(MANIFEST_YOLU,
                            {"urun": self.urun, "surum": self.mevcut_surum,
                             "lisans": self.lisans_belgesi})
        with urllib.request.urlopen(istek, timeout=20,
                                    context=ssl.create_default_context()) as y:
            return json.loads(y.read() or b"{}")

    def _dosya_getir(self, surum: str, bagil: str) -> bytes:
        istek = self._istek(DOSYA_YOLU,
                            {"urun": self.urun, "surum": surum, "yol": bagil,
                             "lisans": self.lisans_belgesi})
        with urllib.request.urlopen(istek, timeout=45,
                                    context=ssl.create_default_context()) as y:
            veri = b""
            while True:
                blok = y.read(_BLOK)
                if not blok:
                    break
                veri += blok
                if len(veri) > _AZAMI_DOSYA:
                    raise ValueError("dosya beklenenden büyük")
            return veri

    # -- doğrulama ----------------------------------------------------
    def _manifest_dogrula(self, m: dict) -> dict | None:
        try:
            from goktungu import lisans
        except Exception:
            import lisans  # düz yapı yedeği
        imza = str(m.get("imza") or "")
        govde = m.get("manifest")
        if not isinstance(govde, dict) or not imza:
            self.gunluk("[GUNC] Manifest eksik (imza/govde yok)")
            return None
        if str(govde.get("acik_anahtar") or "") != lisans.ACIK_ANAHTAR_B64:
            self.gunluk("[GUNC] Manifest imza anahtarı tanınmıyor")
            return None
        if not lisans.imza_dogrula(lisans.govde_bayt(govde), imza):
            self.gunluk("[GUNC] Manifest imzası geçersiz")
            return None
        if str(govde.get("urun")) != self.urun:
            return None
        dosyalar = govde.get("dosyalar")
        if not isinstance(dosyalar, list):
            return None
        return govde

    # -- fark ---------------------------------------------------------
    def fark_bul(self, manifest: dict):
        """(indirilecek [(yol,sha256,boyut)], silinecek [yol]) döndürür."""
        indir, gecersiz = [], []
        for d in manifest.get("dosyalar", []):
            bagil = d.get("yol"); sha = str(d.get("sha256") or "").lower()
            parc = _guvenli_bilesenler(bagil)
            if not parc or len(sha) != 64 or not _yonetilen_mi(bagil):
                gecersiz.append(bagil)
                continue
            yerel = os.path.join(self.kok, *parc)
            if _sha256_dosya(yerel) != sha:
                indir.append((bagil, sha, int(d.get("boyut", 0))))
        if gecersiz:
            self.gunluk("[GUNC] Manifestte %d geçersiz/yönetilmeyen yol atlandı"
                        % len(gecersiz))
        silinecek = []
        for bagil in manifest.get("silinecekler", []):
            parc = _guvenli_bilesenler(bagil)
            if parc and _yonetilen_mi(bagil) and \
                    os.path.isfile(os.path.join(self.kok, *parc)):
                silinecek.append(bagil)
        return indir, silinecek

    # -- indir + uygula ----------------------------------------------
    def uygula(self, dur_geri_cagir=None, baslat_geri_cagir=None) -> dict:
        """Tam döngü: manifest → fark → indir(stage) → uygula(atomik).

        `dur_geri_cagir`/`baslat_geri_cagir`: uygulamayı durdur/başlat.
        Döner: {"guncellendi": bool, "surum": ..., "neden": ...}
        """
        try:
            ham = self._getir_manifest()
        except Exception as e:
            return {"guncellendi": False, "neden": "manifest alınamadı: %s" % e}
        manifest = self._manifest_dogrula(ham)
        if not manifest:
            return {"guncellendi": False, "neden": "manifest doğrulanamadı"}
        hedef = str(manifest.get("surum") or "")
        if not _surum_yeni_mi(self.mevcut_surum, hedef):
            return {"guncellendi": False, "surum": hedef, "neden": "guncel"}

        indir, silinecek = self.fark_bul(manifest)
        if not indir and not silinecek:
            return {"guncellendi": False, "surum": hedef,
                    "neden": "fark yok (sürüm damgası tazelenecek)"}
        self.gunluk("[GUNC] %s -> %s: %d dosya indirilecek, %d silinecek"
                    % (self.mevcut_surum, hedef, len(indir), len(silinecek)))

        # 1) Stage: değişen dosyaları geçici dizine indir + doğrula
        sahne = os.path.join(self.kok, ".guncelleme_sahne")
        _rmtree(sahne)
        os.makedirs(sahne, exist_ok=True)
        try:
            for bagil, sha, boyut in indir:
                veri = self._dosya_getir(hedef, bagil)
                if hashlib.sha256(veri).hexdigest().lower() != sha:
                    raise ValueError("sha256 uyuşmadı: %s" % bagil)
                parc = _guvenli_bilesenler(bagil)
                hedef_yol = os.path.join(sahne, *parc)
                os.makedirs(os.path.dirname(hedef_yol), exist_ok=True)
                with open(hedef_yol, "wb") as f:
                    f.write(veri)
        except Exception as e:
            _rmtree(sahne)
            return {"guncellendi": False, "neden": "indirme/doğrulama: %s" % e}

        # 2) Uygula: uygulamayı durdur, yedekle, taşı, sil, yeniden başlat
        if dur_geri_cagir:
            try:
                dur_geri_cagir()
            except Exception as e:
                self.gunluk("[GUNC] Uygulama durdurma uyarısı: %s" % e)
        yedek = os.path.join(self.kok, ".guncelleme_yedek")
        _rmtree(yedek)
        os.makedirs(yedek, exist_ok=True)
        uygulanan = []
        try:
            for bagil, sha, boyut in indir:
                parc = _guvenli_bilesenler(bagil)
                canli = os.path.join(self.kok, *parc)
                yeni = os.path.join(sahne, *parc)
                if os.path.isfile(canli):
                    yb = os.path.join(yedek, *parc)
                    os.makedirs(os.path.dirname(yb), exist_ok=True)
                    _kopyala(canli, yb)
                os.makedirs(os.path.dirname(canli), exist_ok=True)
                _kopyala(yeni, canli)
                uygulanan.append(bagil)
            for bagil in silinecek:
                parc = _guvenli_bilesenler(bagil)
                canli = os.path.join(self.kok, *parc)
                if os.path.isfile(canli):
                    yb = os.path.join(yedek, *parc)
                    os.makedirs(os.path.dirname(yb), exist_ok=True)
                    _kopyala(canli, yb)
                    os.remove(canli)
                    uygulanan.append("-" + bagil)
        except Exception as e:
            self.gunluk("[GUNC] Uygulama hatası, GERİ ALINIYOR: %s" % e)
            self._geri_al(yedek, uygulanan, silinecek)
            _rmtree(sahne)
            if baslat_geri_cagir:
                try: baslat_geri_cagir()
                except Exception: pass
            return {"guncellendi": False, "neden": "uygulama hatası: %s" % e}

        _rmtree(sahne)
        _rmtree(yedek)
        # 3) Sürüm damgası (isteğe bağlı; asıl sürüm js/surum.js'ten okunur)
        try:
            with open(os.path.join(self.kok, ".surum"), "w") as f:
                f.write(hedef + "\n")
        except OSError:
            pass
        if baslat_geri_cagir:
            try:
                baslat_geri_cagir()
            except Exception as e:
                self.gunluk("[GUNC] Uygulama başlatma uyarısı: %s" % e)
        self.gunluk("[GUNC] Güncelleme tamam: %s" % hedef)
        return {"guncellendi": True, "surum": hedef, "sayi": len(uygulanan)}

    def _geri_al(self, yedek, uygulanan, silinecek):
        for bagil in uygulanan:
            try:
                if bagil.startswith("-"):
                    b = bagil[1:]; parc = _guvenli_bilesenler(b)
                    yb = os.path.join(yedek, *parc)
                    if os.path.isfile(yb):
                        _kopyala(yb, os.path.join(self.kok, *parc))
                else:
                    parc = _guvenli_bilesenler(bagil)
                    yb = os.path.join(yedek, *parc)
                    if os.path.isfile(yb):
                        _kopyala(yb, os.path.join(self.kok, *parc))
            except Exception:
                pass


def _surum_yeni_mi(mevcut: str, aday: str) -> bool:
    def p(s):
        try:
            return tuple(int(x) for x in str(s).split("."))
        except (TypeError, ValueError):
            return ()
    a, b = p(mevcut), p(aday)
    return bool(b) and (not a or b > a)


def _kopyala(kaynak, hedef):
    with open(kaynak, "rb") as g:
        veri = g.read()
    gecici = hedef + ".yeni"
    with open(gecici, "wb") as f:
        f.write(veri)
        f.flush()
        os.fsync(f.fileno())
    os.replace(gecici, hedef)


def _rmtree(yol):
    import shutil
    try:
        shutil.rmtree(yol)
    except FileNotFoundError:
        pass
    except OSError:
        pass


# ======================================================================
# Arka plan servisi (gözetmen): main.py'yi çalıştırır + günceller
# ======================================================================
import subprocess
import threading

URUN = "gcs"
KONTROL_ARALIGI = 15 * 60      # 15 dk'da bir güncelleme kontrolü
ILK_KONTROL_GECIKME = 60       # açılıştan 60 sn sonra ilk kontrol
# 2.5.30: Uygulama içi "Şimdi Güncelle" düğmesi VERİ köküne bu dosyayı
# yazar; gözetmen görünce 15 dk'yı beklemeden hemen güncelleme uygular.
# (goktungu/guncelleme_dosya.TETIK_ADI ile birebir aynı olmalı.)
TETIK_ADI = ".guncelleme_istek"


def _kurulum_koku() -> str:
    """Kurulum kökü = bu dosyanın bulunduğu dizin (main.py ile aynı)."""
    return os.path.dirname(os.path.abspath(__file__))


def _yol_kur(kok: str):
    """goktungu paketini içe alabilmek için sys.path'i hazırlar.

    Paket yapısında kod <kok>/assets/python altında; düz geliştirme
    yapısında <kok> altındadır. İkisi de eklenir."""
    for p in (os.path.join(kok, "assets", "python"), kok):
        if p not in sys.path and os.path.isdir(p):
            sys.path.insert(0, p)


def _surum_oku(kok: str) -> str:
    """Kurulu uygulama sürümünü js/surum.js -> GCS_SURUM'dan okur."""
    import re
    for aday in (os.path.join(kok, "assets", "web", "js", "surum.js"),
                 os.path.join(kok, "js", "surum.js")):
        try:
            with open(aday, encoding="utf-8") as f:
                bas = f.read(2048)
            m = re.search(r'GCS_SURUM\s*=\s*["\']([0-9][0-9.]*)["\']', bas)
            if m:
                return m.group(1)
        except OSError:
            continue
    return "0.0.0"


def _veri_koku() -> str:
    v = (os.environ.get("GOKTUNGU_VERI_KOKU") or "").strip()
    if v:
        return v
    kok = _kurulum_koku()
    return os.path.join(kok, "veri")


def _lisans_belgesi(veri: str):
    """merkez_lisans.json içeriğini ({lisans, imza, acik_anahtar}) okur."""
    yol = os.path.join(veri, "merkez_lisans.json")
    try:
        with open(yol, encoding="utf-8") as f:
            belge = json.load(f)
        if isinstance(belge, dict) and isinstance(belge.get("lisans"), dict):
            return belge
    except (OSError, ValueError):
        pass
    return None


class Gozetmen:
    """main.py'yi alt süreç olarak çalıştırır, ayakta tutar; ayrı bir
    iş parçacığında periyodik güncelleme uygular."""

    def __init__(self, gunluk=print):
        self.kok = _kurulum_koku()
        self.gunluk = gunluk
        self.surec = None
        self._calis = True
        self._guncelleniyor = threading.Event()
        self._kilit = threading.Lock()
        _yol_kur(self.kok)

    # -- uygulama süreci --
    def _ana_baslat(self):
        with self._kilit:
            if self.surec and self.surec.poll() is None:
                return
            py = sys.executable
            ana = os.path.join(self.kok, "main.py")
            bayrak = 0
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                bayrak |= subprocess.CREATE_NO_WINDOW
            self.surec = subprocess.Popen(
                [py, ana, "--tarayici-yok"], cwd=self.kok,
                env=dict(os.environ), creationflags=bayrak)
            self.gunluk("[GOZETMEN] Uygulama başlatıldı (PID %d)" % self.surec.pid)

    def _ana_durdur(self, sure=25):
        with self._kilit:
            s = self.surec
            self.surec = None
        if not s or s.poll() is not None:
            return
        try:
            if os.name == "nt" and hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
                import signal
                s.send_signal(getattr(signal, "CTRL_BREAK_EVENT", signal.SIGTERM))
            else:
                s.terminate()
        except Exception:
            try: s.terminate()
            except Exception: pass
        try:
            s.wait(timeout=sure)
        except Exception:
            try: s.kill()
            except Exception: pass
        self.gunluk("[GOZETMEN] Uygulama durduruldu")

    # -- güncelleme --
    def _guncelle_dene(self):
        veri = _veri_koku()
        belge = _lisans_belgesi(veri)
        if belge is None:
            self.gunluk("[GUNC] Lisans belgesi yok; güncelleme atlandı "
                        "(merkez_lisans.json gerekli)")
            return
        surum = _surum_oku(self.kok)
        motor = GuncellemeMotoru(self.kok, URUN, surum,
                                 lisans_belgesi=belge, gunluk=self.gunluk)
        self._guncelleniyor.set()
        try:
            sonuc = motor.uygula(dur_geri_cagir=lambda: self._ana_durdur(),
                                 baslat_geri_cagir=lambda: self._ana_baslat())
        except Exception as e:
            self.gunluk("[GUNC] Güncelleme hatası: %s" % e)
            self._ana_baslat()
            return
        finally:
            self._guncelleniyor.clear()
        if sonuc.get("guncellendi"):
            self.gunluk("[GUNC] %s sürümüne güncellendi (%d dosya)"
                        % (sonuc.get("surum"), sonuc.get("sayi", 0)))

    def _tetik_tuket(self):
        """Uygulama içi 'Şimdi Güncelle' isteği (tetik dosyası) var mı?
        Varsa siler ve True döner (tek seferlik tüketim)."""
        try:
            yol = os.path.join(_veri_koku(), TETIK_ADI)
            if os.path.isfile(yol):
                try:
                    os.remove(yol)
                except OSError:
                    pass
                return True
        except OSError:
            pass
        return False

    def _guncelle_dongu(self):
        # İlk kontrol gecikmesi de tetiğe duyarlı (kullanıcı hemen isteyebilir).
        for _ in range(ILK_KONTROL_GECIKME):
            if not self._calis or self._tetik_tuket():
                break
            time.sleep(1)
        while self._calis:
            try:
                self._guncelle_dene()
            except Exception as e:
                self.gunluk("[GUNC] Döngü hatası: %s" % e)
            for _ in range(KONTROL_ARALIGI):
                if not self._calis:
                    break
                if self._tetik_tuket():
                    self.gunluk("[GUNC] Uygulama içi güncelleme isteği alındı")
                    break
                time.sleep(1)

    def calis(self):
        self.gunluk("[GOZETMEN] Başladı; kök=%s sürüm=%s"
                    % (self.kok, _surum_oku(self.kok)))
        self._ana_baslat()
        threading.Thread(target=self._guncelle_dongu, daemon=True,
                         name="guncelleme").start()
        # Ana süreç gözetimi: güncelleme sırasında DEĞİLKEN çökerse yeniden başlat
        while self._calis:
            time.sleep(3)
            if self._guncelleniyor.is_set():
                continue
            s = self.surec
            if s is not None and s.poll() is not None:
                self.gunluk("[GOZETMEN] Uygulama beklenmedik durdu "
                            "(kod %s); yeniden başlatılıyor" % s.returncode)
                time.sleep(2)
                self._ana_baslat()

    def durdur(self):
        self._calis = False
        self._ana_durdur()


def main():
    g = Gozetmen()
    try:
        g.calis()
    except KeyboardInterrupt:
        g.durdur()


if __name__ == "__main__":
    main()
