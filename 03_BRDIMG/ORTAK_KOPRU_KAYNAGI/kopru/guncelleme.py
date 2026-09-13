"""GOKTUNGU istemci guncelleme cekirdegi.

Bu modul, calisan programin dosyalarini dogrudan degistirmez. Imzali
manifesti sabit GOKTUNGU katalog adresinden okur, imzayi ve indirilen paketin
SHA-256 ozetini dogrular, paketi kullanici veri dizinine atomik yazar ve
kurulumu AYRI bir islem olarak kullanicinin acik onayindan sonra baslatir.

Guvenlik sinirlari:
* Katalog adresi paket icinde sabittir; yerel ayar ile degistirilemez.
* Ed25519 acik anahtari paket icindeki lisans anahtariyla esit olmalidir.
* Paket imzasi ``urun|surum|platform|paket_tur|sha256|boyut`` baglaminda
  dogrulanir; URL ve notlar imzali paket kimliginin yerine gecemez.
* Lisansli GCS paketi statik indirme yolundan degil, imzali yerel lisans
  belgesiyle yetkili istemci ucundan alinir.
* Indirme/kontrol arka plandadir; telemetri ve arayuz dongusunu bekletmez.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform as _platform
import re
import ssl
import subprocess
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid

from . import ayar as ayar_mod
from . import imza

_KATALOG = "https://goktungu.com"
_MANIFEST_YOLU = "/api/genel/guncelleme"
_PAKET_YOLU = "/api/istemci/guncelleme_paket"
_AZAMI_MANIFEST = 128 * 1024
_AZAMI_PAKET = 2 * 1024 * 1024 * 1024
_BLOK = 256 * 1024
_DOSYA_ADI = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,180}$")
_SURUM = re.compile(r"^[0-9]+(?:\.[0-9]+){1,3}(?:[-+][A-Za-z0-9._-]+)?$")


def platform_adi() -> str:
    """Katalogdaki platform degerini verir; belirsiz platformu reddeder."""
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    return ""


def _surum_parcalari(deger: str) -> tuple[int, ...] | None:
    """Basit sayisal surumleri karsilastirmak icin parcalar."""
    metin = str(deger or "").strip()
    if not _SURUM.fullmatch(metin):
        return None
    ana = metin.split("-", 1)[0].split("+", 1)[0]
    try:
        return tuple(int(x) for x in ana.split("."))
    except ValueError:
        return None


def surum_yeni_mi(mevcut: str, aday: str) -> bool:
    """Adayin mevcut sayisal surumden kesin olarak yeni olup olmadigini verir."""
    a, b = _surum_parcalari(mevcut), _surum_parcalari(aday)
    if a is None or b is None:
        return False
    uzunluk = max(len(a), len(b))
    return a + (0,) * (uzunluk - len(a)) < b + (0,) * (uzunluk - len(b))


def _guvenli_dizin(kok: str) -> str:
    dizin = os.path.join(str(kok), "guncellemeler")
    os.makedirs(dizin, mode=0o700, exist_ok=True)
    try:
        os.chmod(dizin, 0o700)
    except OSError:
        pass
    return dizin


class GuncellemeYoneticisi:
    """Tek urun/platform icin durumlu, arka planli guncelleme istemcisi."""

    def __init__(self, urun: str, surum: str, veri_koku: str,
                 platform: str | None = None, gunluk=None):
        self.urun = str(urun or "").strip().lower()
        self.surum = str(surum or "").strip()
        self.platform = str(platform or platform_adi()).strip().lower()
        self.veri_koku = str(veri_koku)
        self._gunluk = gunluk
        self._kilit = threading.RLock()
        self._is = None
        self._manifest = None
        self._durum = {
            "kontrol_edildi": False,
            "guncelleme_var": False,
            "asama": "bekliyor",
            "hata": "",
            "mevcut_surum": self.surum,
            "hedef_surum": "",
            "notlar": "",
            "indirilen": 0,
            "toplam": 0,
            "yeniden_baslat_gerekli": False,
        }

    def _yaz(self, asama=None, hata=None, **alanlar):
        with self._kilit:
            if asama is not None:
                self._durum["asama"] = str(asama)
            if hata is not None:
                self._durum["hata"] = str(hata)
            self._durum.update(alanlar)

    def _gunluk_yaz(self, metin, seviye="bilgi"):
        if self._gunluk:
            try:
                self._gunluk("GUNCELLEME", str(metin), seviye)
                return
            except Exception:
                pass
        print("[GUNCELLEME] " + str(metin))

    def durum(self) -> dict:
        with self._kilit:
            return dict(self._durum)

    def _manifest_url(self) -> str:
        sorgu = urllib.parse.urlencode({
            "urun": self.urun, "surum": self.surum, "platform": self.platform,
        })
        return _KATALOG + _MANIFEST_YOLU + "?" + sorgu

    def _manifest_al(self) -> dict:
        if self.urun not in ("gcs", "kopru", "video") or not self.platform:
            raise ValueError("Guncelleme urun veya platform bilgisi gecersiz")
        istek = urllib.request.Request(
            self._manifest_url(),
            headers={"Accept": "application/json", "User-Agent":
                     "GOKTUNGU-Istemci-Guncelleyici/" + self.surum},
            method="GET")
        baglam = ssl.create_default_context()
        with urllib.request.urlopen(istek, timeout=15, context=baglam) as yanit:
            ham = yanit.read(_AZAMI_MANIFEST + 1)
        if len(ham) > _AZAMI_MANIFEST:
            raise ValueError("Guncelleme bildirimi beklenenden buyuk")
        try:
            veri = json.loads(ham.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise ValueError("Guncelleme bildirimi okunamadi") from e
        if not isinstance(veri, dict):
            raise ValueError("Guncelleme bildirimi nesne degil")
        return veri

    def _manifest_dogrula(self, m: dict) -> dict | None:
        """Guncel paket alanlarini ve imzasini dogrular; yoksa None."""
        if not bool(m.get("guncelleme_var")):
            return None
        zorunlu = ("urun", "surum", "platform", "paket_tur", "dosya_ad",
                   "dosya_boyut", "sha256", "imza", "acik_anahtar", "url")
        if any(x not in m for x in zorunlu):
            raise ValueError("Guncelleme bildirimi eksik alan iceriyor")
        if str(m["urun"]).lower() != self.urun or str(m["platform"]).lower() != self.platform:
            raise ValueError("Guncelleme bildirimi baska urune ait")
        hedef = str(m["surum"] or "")
        if not surum_yeni_mi(self.surum, hedef):
            raise ValueError("Guncelleme surumu gecerli degil")
        ad = str(m["dosya_ad"] or "")
        if not _DOSYA_ADI.fullmatch(ad):
            raise ValueError("Guncelleme paketi adi gecersiz")
        try:
            boyut = int(m["dosya_boyut"])
        except (TypeError, ValueError) as e:
            raise ValueError("Guncelleme paketi boyutu gecersiz") from e
        ozet = str(m["sha256"] or "").lower()
        if boyut < 1 or boyut > _AZAMI_PAKET or not re.fullmatch(r"[0-9a-f]{64}", ozet):
            raise ValueError("Guncelleme paketi ozeti gecersiz")
        if str(m["acik_anahtar"] or "") != imza.ACIK_ANAHTAR_B64:
            raise ValueError("Guncelleme imza anahtari taninmiyor")
        baglam = "|".join((self.urun, hedef, self.platform,
                            str(m["paket_tur"]), ozet, str(boyut))).encode("utf-8")
        if not imza.dogrula(baglam, str(m["imza"] or "")):
            raise ValueError("Guncelleme paketi imzasi gecersiz")
        url = str(m["url"] or "")
        parca = urllib.parse.urlsplit(url)
        if parca.scheme != "https" or parca.netloc.lower() != "goktungu.com":
            raise ValueError("Guncelleme paketi adresi guvenli degil")
        return {
            "urun": self.urun, "surum": hedef, "platform": self.platform,
            "paket_tur": str(m["paket_tur"]), "dosya_ad": ad,
            "dosya_boyut": boyut, "sha256": ozet, "imza": str(m["imza"]),
            "notlar": str(m.get("notlar") or ""), "url": url,
        }

    def denetle(self) -> dict:
        """Sunucuya erisim varsa imzali guncellemeyi denetler; hata sessizce eski surumu bozmaz."""
        self._yaz("denetleniyor", "", kontrol_edildi=False)
        try:
            aday = self._manifest_dogrula(self._manifest_al())
        except (OSError, ValueError, urllib.error.URLError) as e:
            self._yaz("hata", str(e), kontrol_edildi=True, guncelleme_var=False,
                      hedef_surum="", notlar="")
            self._gunluk_yaz("Surum denetimi basarisiz: " + str(e), "uyari")
            return self.durum()
        with self._kilit:
            self._manifest = aday
        if aday is None:
            self._yaz("guncel", "", kontrol_edildi=True, guncelleme_var=False,
                      hedef_surum="", notlar="", indirilen=0, toplam=0)
        else:
            self._yaz("hazir", "", kontrol_edildi=True, guncelleme_var=True,
                      hedef_surum=aday["surum"], notlar=aday["notlar"],
                      indirilen=0, toplam=aday["dosya_boyut"])
            self._gunluk_yaz("Yeni surum hazir: " + aday["surum"], "bilgi")
        return self.durum()

    def denetle_arka_planda(self) -> bool:
        with self._kilit:
            if self._is and self._is.is_alive():
                return False
            self._is = threading.Thread(target=self.denetle,
                                        name="guncelleme-denetim", daemon=True)
            self._is.start()
            return True

    @staticmethod
    def _kurulum_belgesi() -> dict:
        """Kopru kurulumunun merkezce verilen kimligini tasir; gizli disari yazilmaz."""
        kimlik = ayar_mod.kimlik_oku()
        kurulum_uid = str(kimlik.get("kurulum_uid") or "").strip()
        gizli = str(kimlik.get("gizli") or "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", kurulum_uid) or not gizli:
            raise PermissionError("Guncelleme icin etkin Kopru kurulum kimligi gerekli")
        return {"kurulum_uid": kurulum_uid, "gizli": gizli}

    def _paket_indir(self, m: dict, hedef: str):
        """Lisansli istemci ucundan paketi alir ve aktarim ozetini denetler."""
        govde = json.dumps({"urun": self.urun, "surum": m["surum"],
                             "platform": self.platform, "dosya": m["dosya_ad"],
                             **self._kurulum_belgesi()},
                            ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        istek = urllib.request.Request(
            _KATALOG + _PAKET_YOLU, data=govde, method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/octet-stream",
                     "User-Agent": "GOKTUNGU-Kopru-Guncelleyici/" + self.surum})
        gecici = hedef + "." + uuid.uuid4().hex + ".part"
        toplam, ozet = 0, hashlib.sha256()
        try:
            with urllib.request.urlopen(istek, timeout=45, context=ssl.create_default_context()) as yanit:
                with open(gecici, "xb") as f:
                    while True:
                        blok = yanit.read(_BLOK)
                        if not blok:
                            break
                        toplam += len(blok)
                        if toplam > m["dosya_boyut"] or toplam > _AZAMI_PAKET:
                            raise ValueError("Paket beklenen boyutu asti")
                        ozet.update(blok)
                        f.write(blok)
                        self._yaz("indiriliyor", "", indirilen=toplam, toplam=m["dosya_boyut"])
                    f.flush()
                    os.fsync(f.fileno())
            if toplam != m["dosya_boyut"] or ozet.hexdigest().lower() != m["sha256"]:
                raise ValueError("Indirilen paketin SHA-256 dogrulamasi basarisiz")
            os.replace(gecici, hedef)
        except Exception:
            try:
                os.unlink(gecici)
            except OSError:
                pass
            raise

    def indir_arka_planda(self) -> tuple[bool, str]:
        with self._kilit:
            m = dict(self._manifest or {})
            if not m or not self._durum.get("guncelleme_var"):
                return False, "Indirilecek dogrulanmis bir guncelleme yok"
            if self._is and self._is.is_alive():
                return False, "Guncelleme islemi zaten calisiyor"
            self._is = threading.Thread(target=self._indir_is, args=(m,),
                                        name="guncelleme-indir", daemon=True)
            self._is.start()
        return True, "Guncelleme indiriliyor"

    def _indir_is(self, m: dict):
        self._yaz("indiriliyor", "", indirilen=0, toplam=m["dosya_boyut"])
        try:
            hedef = os.path.join(_guvenli_dizin(self.veri_koku), m["dosya_ad"])
            self._paket_indir(m, hedef)
            self._yaz("indirildi", "", indirilen=m["dosya_boyut"],
                      toplam=m["dosya_boyut"], paket_yolu=hedef)
            self._gunluk_yaz("Paket dogrulandi: " + m["dosya_ad"], "basari")
        except Exception as e:
            self._yaz("hata", str(e))
            self._gunluk_yaz("Paket indirilemedi: " + str(e), "hata")

    def kurulum_baslat(self) -> tuple[bool, str]:
        """Indirilmis, dogrulanmis paketi kullanicinin OS yetkisiyle baslatir."""
        with self._kilit:
            m = dict(self._manifest or {})
            yol = str(self._durum.get("paket_yolu") or "")
            if self._durum.get("asama") != "indirildi" or not m or not os.path.isfile(yol):
                return False, "Dogrulanmis paket henuz indirilmadi"
            if os.path.getsize(yol) != int(m["dosya_boyut"]):
                return False, "Paket boyutu sonradan degismis"
        try:
            with open(yol, "rb") as f:
                ozet = hashlib.file_digest(f, "sha256").hexdigest()
            if ozet.lower() != m["sha256"]:
                return False, "Paket SHA-256 ozeti sonradan degismis"
            if self.platform == "windows" and yol.lower().endswith(".exe"):
                # Ayri komut yorumlayicisi program kapanirken kurucuyu calistirir;
                # NSIS kendi UAC bildirimiyle yetki ister ve kullanici verisini korur.
                komut = 'ping 127.0.0.1 -n 3 >nul & start "" /wait "{}" /S /NORESTART'.format(yol.replace('"', ''))
                subprocess.Popen([os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", komut],
                                 creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
                self._yaz("kurulum_baslatildi", "", yeniden_baslat_gerekli=True)
                return True, "Kurulum baslatildi; tamamlaninca uygulamayi yeniden acin"
            if self.platform == "linux" and yol.lower().endswith(".deb"):
                subprocess.Popen(["pkexec", "/usr/bin/dpkg", "-i", yol],
                                 start_new_session=True)
                self._yaz("kurulum_baslatildi", "", yeniden_baslat_gerekli=True)
                return True, "Yonetici onayi acildi; kurulum bitince servis yeniden baslatilir"
            return False, "Bu platform icin otomatik kurulum paketi desteklenmiyor"
        except (OSError, ValueError) as e:
            self._yaz("hata", str(e))
            return False, "Kurulum baslatilamadi: " + str(e)
