"""GRCOFF dosya tabanlı (artımlı) güncelleme — istemci içi DENETİM + TETİK.

NEDEN (2.5.30): Kullanıcı isteği — "uygulamada güncelleme var mı kontrol
eden, varsa güncellememi sağlayan Yardım menüsü altında bir düğme olmalı".

Eski model (guncelleme.py) her güncellemede imzasız bir .exe indirip
çalıştırıyordu; Windows Defender bunu yanlış-pozitif karantinaya alıp
güncellemeyi bozuyordu. Yeni model dosya tabanlıdır: yalnız DEĞİŞEN düz
dosyalar (.py/.js/.html/...) indirilir ve asıl uygulama arka plandaki
GÖZETMEN (goktungu_guncelleyici.Gozetmen) tarafından yapılır — çünkü
çalışan süreç kendi kodunu (özellikle Windows'ta dosya kilidiyle)
güvenle değiştiremez.

Bu yönetici, çalışan uygulamanın İÇİNDEN yalnız şunları yapar:
  * imzalı dosya manifestini çeker (/api/istemci/dosya_manifesti),
  * Ed25519 imzasını gömülü açık anahtarla doğrular (lisans.imza_dogrula),
  * yerel dosyalarla sha256 farkını çıkarıp KAÇ dosya değişeceğini bulur,
  * kullanıcının açık onayında VERİ köküne bir TETİK dosyası yazar.
Gözetmen bu tetiği görüp güncellemeyi hemen uygular (bkz.
goktungu_guncelleyici.Gozetmen._guncelle_dongu).

Güvenlik: katalog adresi sabittir; manifest Ed25519 imzalıdır ve imza
anahtarı pakete gömülü lisans anahtarıyla eşit olmalıdır; ağ istekleri
yalnız HTTPS; denetim arka plandadır ve telemetri/arayüz döngüsünü
BEKLETMEZ. Bu modül cv2/psycopg2 gibi ağır bağımlılık içe almaz.
"""

from __future__ import annotations

import hashlib
import json
import os
import ssl
import threading
import time
import urllib.error
import urllib.request

from . import lisans
from . import sabitler

_KATALOG = "https://goktungu.com"
_MANIFEST_YOLU = "/api/istemci/dosya_manifesti"
_AZAMI_MANIFEST = 4 * 1024 * 1024
_BLOK = 256 * 1024

# Güncellemeyle YÖNETİLEN kökler/dosyalar — goktungu_guncelleyici ile
# BİREBİR aynı olmalı (aksi halde "kaç dosya" sayısı sapar; güvenliği
# etkilemez, uygulamayı gözetmen kendi farkıyla yapar).
_YONETILEN_KOKLER = ("assets/", "ai_modeller/")
_YONETILEN_DOSYALAR = ("main.py", "requirements.txt", "goktungu_guncelleyici.py")
_KORUNAN = ("veri/", "ai_kayitlar/", "gunluk/", "telemetri_tampon/")

# Gözetmenin izlediği tetik dosyası (VERİ kökünde — her zaman yazılabilir).
TETIK_ADI = ".guncelleme_istek"
# 2.5.33: gözetmenin yazdığı ayrıntılı ilerleme ve kod işareti.
ILERLEME_ADI = "guncelleme_ilerleme.json"
GOZETMEN_ISARET_ADI = "gozetmen_kod.json"
SERVIS_ADI_WIN = "GoktunguMerkez"


def _surum_parcalari(deger):
    try:
        return tuple(int(x) for x in str(deger or "").strip().split("."))
    except (TypeError, ValueError):
        return ()


def surum_yeni_mi(mevcut, aday):
    a, b = _surum_parcalari(mevcut), _surum_parcalari(aday)
    if not b:
        return False
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) < b + (0,) * (n - len(b))


def _yonetilen_mi(bagil):
    b = str(bagil or "").replace("\\", "/")
    if not b or b.startswith("/") or ".." in b.split("/") or ":" in b:
        return False
    if any(b.startswith(k) for k in _KORUNAN):
        return False
    return b in _YONETILEN_DOSYALAR or any(b.startswith(k) for k in _YONETILEN_KOKLER)


def _sha256_dosya(yol):
    h = hashlib.sha256()
    try:
        with open(yol, "rb") as f:
            for blok in iter(lambda: f.read(_BLOK), b""):
                h.update(blok)
    except OSError:
        return ""
    return h.hexdigest()


class DosyaGuncellemeYoneticisi:
    """Çalışan uygulama içinden dosya tabanlı güncellemeyi DENETLER ve
    kullanıcı onayında gözetmen için bir tetik yazar. Uygulamayı kendisi
    YAPMAZ (bkz. modül başlığı). Arayüzü eski GuncellemeYoneticisi ile
    uyumludur: durum() / denetle() / denetle_arka_planda()."""

    def __init__(self, urun, surum, veri_koku=None, kok=None, gunluk=None):
        self.urun = str(urun or "").strip().lower()
        self.surum = str(surum or "").strip()
        self.veri_koku = str(veri_koku or getattr(sabitler, "VERI_KOKU", "."))
        self.kok = str(kok or getattr(sabitler, "PROJE_KOKU", "."))
        self._gunluk = gunluk
        self._kilit = threading.RLock()
        self._is = None
        self._durum = {
            "kontrol_edildi": False,
            "guncelleme_var": False,
            "asama": "bekliyor",       # bekliyor|denetleniyor|guncel|hazir|uygula_istendi|hata
            "hata": "",
            "mevcut_surum": self.surum,
            "hedef_surum": "",
            "notlar": "",
            "dosya_sayisi": 0,
            "indirilen": 0,
            "toplam": 0,
            "yeniden_baslat_gerekli": False,
        }

    # -- durum -------------------------------------------------------
    def durum(self):
        with self._kilit:
            d = dict(self._durum)
        d["ilerleme"] = self._ilerleme_oku()
        d["gozetmen_guncel"] = self._gozetmen_guncel_mi()
        d["servis_yenilenebilir"] = (os.name == "nt")
        return d

    def _ilerleme_oku(self):
        try:
            with open(os.path.join(self.veri_koku, ILERLEME_ADI),
                      encoding="utf-8") as f:
                v = json.load(f)
            return v if isinstance(v, dict) else None
        except (OSError, ValueError):
            return None

    def _gozetmen_guncel_mi(self):
        """Çalışan gözetmen diskteki goktungu_guncelleyici.py ile aynı mı?
        Eski gözetmen işaret dosyası yazmaz -> False."""
        try:
            with open(os.path.join(self.veri_koku, GOZETMEN_ISARET_ADI),
                      encoding="utf-8") as f:
                isaret = json.load(f)
            disk = _sha256_dosya(os.path.join(self.kok, "goktungu_guncelleyici.py"))
            return bool(disk) and isaret.get("ozet") == disk
        except (OSError, ValueError, AttributeError):
            return False

    def servisi_yeniden_baslat(self):
        """Merkez servisini (gözetmen dahil) yeniden başlatır. Yalnız
        Windows servisi; komut ayrık süreçte çalışır (servis dururken
        ölmesin). (basari, bilgi) döner."""
        if os.name != "nt":
            return False, ("Linux'ta: sudo systemctl restart goktungu-merkez")
        import subprocess
        komut = ('ping -n 3 127.0.0.1 >nul & net stop "%s" & '
                 'ping -n 3 127.0.0.1 >nul & net start "%s"'
                 % (SERVIS_ADI_WIN, SERVIS_ADI_WIN))
        taban = (getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                 | getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for bayrak in (taban | 0x01000000, taban):   # BREAKAWAY_FROM_JOB
            try:
                subprocess.Popen([os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", komut],
                                 creationflags=bayrak, close_fds=True)
                self._gunluk_yaz("Servis yeniden başlatma komutu verildi", "uyari")
                return True, "Servis yeniden başlatılıyor (yaklaşık 15-30 sn)"
            except OSError:
                continue
        return False, "Servis yeniden başlatma komutu çalıştırılamadı"

    def _yaz(self, asama=None, hata=None, **alan):
        with self._kilit:
            if asama is not None:
                self._durum["asama"] = str(asama)
            if hata is not None:
                self._durum["hata"] = str(hata)
            self._durum.update(alan)

    def _gunluk_yaz(self, metin, seviye="bilgi"):
        if self._gunluk:
            try:
                self._gunluk("GUNCELLEME", str(metin), seviye)
                return
            except Exception:
                pass
        print("[GUNCELLEME] " + str(metin))

    # -- lisans belgesi (imzalı) -------------------------------------
    @staticmethod
    def _lisans_belgesi():
        yetki, hata = lisans.lisans_oku()
        if not yetki:
            raise PermissionError(
                "Güncelleme için geçerli Merkez lisansı gerekli: " + str(hata))
        try:
            with open(lisans.lisans_yolu(), "r", encoding="utf-8") as f:
                belge = json.load(f)
        except (OSError, ValueError) as e:
            raise PermissionError("Lisans belgesi okunamadı") from e
        if not isinstance(belge, dict) or not isinstance(belge.get("lisans"), dict):
            raise PermissionError("Lisans belgesi geçersiz")
        return belge

    # -- manifest çek + doğrula --------------------------------------
    def _manifest_al(self):
        govde = json.dumps(
            {"urun": self.urun, "surum": self.surum,
             "lisans": self._lisans_belgesi()},
            ensure_ascii=False).encode("utf-8")
        istek = urllib.request.Request(
            _KATALOG + _MANIFEST_YOLU, data=govde, method="POST",
            headers={"Content-Type": "application/json",
                     "Accept": "application/json",
                     "User-Agent": "GOKTUNGU-Merkez-Guncelleyici/" + self.surum})
        with urllib.request.urlopen(
                istek, timeout=20, context=ssl.create_default_context()) as y:
            ham = y.read(_AZAMI_MANIFEST + 1)
        if len(ham) > _AZAMI_MANIFEST:
            raise ValueError("Manifest beklenenden büyük")
        veri = json.loads(ham.decode("utf-8"))
        if not isinstance(veri, dict):
            raise ValueError("Manifest nesne değil")
        return veri

    def _manifest_dogrula(self, ham):
        imza = str(ham.get("imza") or "")
        govde = ham.get("manifest")
        if not isinstance(govde, dict) or not imza:
            raise ValueError("Manifest eksik (imza/gövde yok)")
        if str(govde.get("acik_anahtar") or "") != lisans.ACIK_ANAHTAR_B64:
            raise ValueError("Manifest imza anahtarı tanınmıyor")
        if not lisans.imza_dogrula(lisans.govde_bayt(govde), imza):
            raise ValueError("Manifest imzası geçersiz")
        if str(govde.get("urun") or "").lower() != self.urun:
            raise ValueError("Manifest başka ürüne ait")
        if not isinstance(govde.get("dosyalar"), list):
            raise ValueError("Manifest dosya listesi yok")
        return govde

    def _fark_say(self, manifest):
        """(degisen_sayi, degisen_bayt) — yerel sha256 ile karşılaştırır."""
        sayi, bayt = 0, 0
        _liste = manifest.get("dosyalar", [])
        _n = len(_liste)
        for _i, d in enumerate(_liste, 1):
            if _i % 40 == 0 or _i == _n:
                self._yaz(denetim={"mesaj": "Yerel dosyalar karşılaştırılıyor (%d/%d)"
                                   % (_i, _n), "yuzde": 30 + 65.0 * _i / max(1, _n)})
            bagil = str(d.get("yol") or "")
            sha = str(d.get("sha256") or "").lower()
            if len(sha) != 64 or not _yonetilen_mi(bagil):
                continue
            yerel = os.path.join(self.kok, *bagil.split("/"))
            if _sha256_dosya(yerel) != sha:
                sayi += 1
                try:
                    bayt += int(d.get("boyut", 0))
                except (TypeError, ValueError):
                    pass
        for bagil in manifest.get("silinecekler", []):
            if _yonetilen_mi(bagil) and \
                    os.path.isfile(os.path.join(self.kok, *str(bagil).split("/"))):
                sayi += 1
        return sayi, bayt

    # -- denetim -----------------------------------------------------
    def denetle(self):
        """Sunucu erişilebilirse imzalı manifesti denetler. Hata durumunda
        mevcut sürümü BOZMAZ; yalnız durumu 'hata' yapar."""
        self._yaz("denetleniyor", "", kontrol_edildi=False,
                  denetim={"mesaj": "Sunucudan imzalı sürüm listesi alınıyor", "yuzde": 10})
        try:
            ham = self._manifest_al()
            self._yaz(denetim={"mesaj": "Ed25519 imzası doğrulanıyor", "yuzde": 25})
            manifest = self._manifest_dogrula(ham)
        except PermissionError as e:
            self._yaz("hata", str(e), kontrol_edildi=True, guncelleme_var=False)
            self._gunluk_yaz("Sürüm denetimi: " + str(e), "uyari")
            return self.durum()
        except (OSError, ValueError, urllib.error.URLError) as e:
            self._yaz("hata", str(e), kontrol_edildi=True, guncelleme_var=False)
            self._gunluk_yaz("Sürüm denetimi başarısız: " + str(e), "uyari")
            return self.durum()
        hedef = str(manifest.get("surum") or "")
        if not surum_yeni_mi(self.surum, hedef):
            self._yaz("guncel", "", kontrol_edildi=True, guncelleme_var=False,
                      denetim={"mesaj": "Yazılım güncel", "yuzde": 100},
                      hedef_surum=hedef, notlar="", dosya_sayisi=0,
                      indirilen=0, toplam=0)
            self._gunluk_yaz("Yazılım güncel (%s)" % self.surum, "bilgi")
            return self.durum()
        sayi, bayt = self._fark_say(manifest)
        self._yaz("hazir", "", kontrol_edildi=True, guncelleme_var=True,
                  denetim={"mesaj": "Yeni sürüm bulundu", "yuzde": 100},
                  hedef_surum=hedef, notlar=str(manifest.get("notlar") or ""),
                  dosya_sayisi=sayi, indirilen=0, toplam=bayt)
        self._gunluk_yaz(
            "Yeni sürüm hazır: %s (%d dosya)" % (hedef, sayi), "bilgi")
        return self.durum()

    def denetle_arka_planda(self):
        with self._kilit:
            if self._is and self._is.is_alive():
                return False
            self._is = threading.Thread(
                target=self.denetle, name="guncelleme-denetim", daemon=True)
            self._is.start()
            return True

    # -- tetik (asıl güncellemeyi gözetmene devret) ------------------
    def guncelle_baslat(self):
        """Kullanıcı onayında gözetmen için tetik dosyası yazar. Gözetmen
        güncellemeyi uygular (uygulamayı durdurur, dosyaları yerleştirir,
        yeniden başlatır). (basari, bilgi) döner."""
        with self._kilit:
            if not self._durum.get("guncelleme_var"):
                return False, "Uygulanacak doğrulanmış bir güncelleme yok"
            hedef = self._durum.get("hedef_surum") or ""
        try:
            os.makedirs(self.veri_koku, exist_ok=True)
            tetik = os.path.join(self.veri_koku, TETIK_ADI)
            with open(tetik, "w", encoding="utf-8") as f:
                json.dump({"istek": "guncelle", "hedef": hedef,
                           "zaman": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                  time.gmtime())}, f)
                f.flush()
                os.fsync(f.fileno())
        except OSError as e:
            self._yaz("hata", "Tetik yazılamadı: " + str(e))
            return False, "Güncelleme başlatılamadı: " + str(e)
        self._yaz("uygula_istendi", "", yeniden_baslat_gerekli=True)
        try:
            with open(os.path.join(self.veri_koku, ILERLEME_ADI + ".yeni"), "w",
                      encoding="utf-8") as f:
                json.dump({"kimlik": "istek-%d" % int(time.time() * 1000),
                           "tetik": "kullanici", "etkin": True, "asama": "istek",
                           "durum": "calisiyor", "yuzde": 0.5,
                           "mesaj": "Güncelleme servisine istek iletildi; servis yanıtı bekleniyor",
                           "mevcut_surum": self.surum, "hedef_surum": hedef,
                           "basla_ts": time.time(), "guncel_ts": time.time(),
                           "adimlar": [{"ts": time.time(), "asama": "istek",
                                        "durum": "tamam",
                                        "mesaj": "Kullanıcı güncellemeyi başlattı (%s → %s)"
                                                 % (self.surum, hedef)}]},
                          f, ensure_ascii=False)
            os.replace(os.path.join(self.veri_koku, ILERLEME_ADI + ".yeni"),
                       os.path.join(self.veri_koku, ILERLEME_ADI))
        except OSError:
            pass
        self._gunluk_yaz(
            "Güncelleme istendi (%s); gözetmen uyguluyor" % hedef, "bilgi")
        return True, ("Güncelleme başlatıldı; uygulama birazdan yeniden "
                      "başlatılacak")
