"""GÖKTUNGU — M50 elektro-optik Windows SDK sürücüsü.

`kopru/m50_hvs.py` ile BİREBİR aynı dosyadır (kasıtlı ikiz kopya): hem
saha Köprüsü hem de Merkez'in kendi "doğrudan mod"u (bkz. m50_yerel.py)
aynı, tek doğrulanmış sürücüyü kullanır. Biri değişirse diğeri elle
senkronize edilmelidir.

Bu modül yalnız üreticinin HVS SDK 3.0.10.869 Python örneğinde doğrulanan
çağrıları kullanır. Cihaz, kullanıcı veya Merkez tarafından açıkça verilen
adresle bağlanmadıkça hiçbir IP'ye erişmez. SDK, Windows x64 DLL'leri
(HVideoSDK.dll/HVideoUtility.dll) gerektirdiği için Linux'ta kapalı kalır.

Tarayıcıya ham SDK video baytı aktarılmaz: üreticinin PlayVideo çağrısı bir
Windows pencere tutamacı ister; ham olay verisinin codec'i SDK belgesinde
web aktarımı için tanımlanmamıştır. Görüntü kaynağı, operatörün açıkça
ayarladığı RTSP/RTSPS URI üzerinden mevcut yerel görüntü hattına eklenir.
"""
from __future__ import annotations

import importlib
import ipaddress
import os
import platform
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Dict, Optional, Tuple

M50_SDK_SURUM = "3.0.10.869"
M50_VARSAYILAN_PORT = 8000
M50_AZIMUT_MIN, M50_AZIMUT_MAX = -360.0, 360.0
M50_EGIM_MIN, M50_EGIM_MAX = -90.0, 90.0
M50_HIZ_MIN, M50_HIZ_MAX = 1, 10
M50_MAX_PIKSEL = 8192


class M50Hata(RuntimeError):
    """M50 sürücüsünün kullanıcıya güvenle açıklanabilir hata türü."""


def _temiz_metin(deger: Any, alan: str, en_cok: int = 128) -> str:
    metin = str(deger or "").strip()
    if not metin:
        raise M50Hata("%s boş olamaz" % alan)
    if len(metin) > en_cok or "\x00" in metin:
        raise M50Hata("%s geçersiz" % alan)
    return metin


def _ip_dogrula(deger: Any) -> str:
    ip = _temiz_metin(deger, "M50 IP adresi", 64)
    try:
        ipaddress.ip_address(ip)
    except ValueError as exc:
        raise M50Hata("M50 IP adresi geçersiz") from exc
    return ip


def _sayi(deger: Any, ad: str, alt: float, ust: float) -> float:
    try:
        sonuc = float(deger)
    except (TypeError, ValueError) as exc:
        raise M50Hata("%s sayısal olmalıdır" % ad) from exc
    if not (alt <= sonuc <= ust):
        raise M50Hata("%s %s–%s aralığında olmalıdır" % (ad, alt, ust))
    return sonuc


class M50Istemcisi:
    """M50 bağlantı ve kontrolü için thread-güvenli, kapalı-varsayılan sarmalayıcı."""

    def __init__(self, yaz=None, ayar_oku=None, ayar_yaz=None):
        self._yaz = yaz or (lambda _m, _s="bilgi": None)
        self._ayar_oku = ayar_oku or (lambda: {})
        self._ayar_yaz = ayar_yaz or (lambda _d: None)
        self._kilit = threading.RLock()
        self._sdk = None
        self._dat = None
        self._cihaz = None
        self._acik_komut = False
        self._son_baglanti: Dict[str, Any] = {}
        self._durum: Dict[str, Any] = {
            "tur": "m50", "durum": "kapali", "bagli": False,
            "sdk_surumu": M50_SDK_SURUM, "sdk_hazir": False,
            "ip": "", "port": 0, "hata": "", "azimut": None,
            "egim": None, "takip": {"etkin": False, "kanal": ""},
            "video": {"gorunur": False, "termal": False,
                      "kaynak": "sdk_ham_veri_webde_desteklenmez"},
            "son_islem": "", "guncelleme": time.time(),
        }
        self._angle_cb = None
        # Her kanal için kullanıcı tarafından açıkça iletilmiş seçimin
        # varlığı tutulur. Dikdörtgen koordinatları saklanmaz; işaret yalnız
        # takip ön koşulunu uygular ve bağlantı kesilince sıfırlanır.
        self._takip_secildi = {"gorunur": False, "termal": False}
        self._dll_dizin_handle = None

    def durum(self) -> Dict[str, Any]:
        with self._kilit:
            sonuc = dict(self._durum)
            sonuc["takip"] = dict(self._durum["takip"])
            sonuc["video"] = dict(self._durum["video"])
            return sonuc

    def _durum_yaz(self, **alanlar: Any) -> None:
        with self._kilit:
            self._durum.update(alanlar)
            self._durum["guncelleme"] = time.time()

    @staticmethod
    def _sdk_kok(ayar: Dict[str, Any]) -> Path:
        """SDK'nın kurulu olduğu yeri açık yapılandırmadan çözer.

        Öncelik: uygulama paketindeki m50_sdk, ortam değişkeni ve operatörün
        yerel ayarı. Dosya yoksa bağlantı reddedilir; ağda başka yol aranmaz.
        """
        adaylar = []
        burada = Path(__file__).resolve().parent
        adaylar.append(burada / "m50_sdk")
        ortam = os.environ.get("GOKTUNGU_M50_SDK_DIZIN", "").strip()
        if ortam:
            adaylar.append(Path(ortam))
        ayar_yol = str(ayar.get("m50_sdk_dizin") or "").strip()
        if ayar_yol:
            adaylar.append(Path(ayar_yol))
        for kok in adaylar:
            if (kok / "Hvs" / "sdk.py").is_file() and (
                    (kok / "HVideoSDK.dll").is_file() or
                    (kok / "bin" / "HVideoSDK.dll").is_file()):
                return kok
        raise M50Hata("M50 Windows SDK bulunamadı; desteklenen SDK paketini kurun")

    def _sdk_yukle(self) -> None:
        if platform.system().lower() != "windows" or platform.architecture()[0] != "64bit":
            raise M50Hata("M50 HVS SDK yalnız Windows x64 Köprü üzerinde çalışır")
        if self._sdk is not None:
            return
        ayar = self._ayar_oku() or {}
        kok = self._sdk_kok(ayar)
        dll_dizin = kok / "bin" if (kok / "bin" / "HVideoSDK.dll").is_file() else kok
        try:
            # Dönüş nesnesi tutulur; çöp toplayıcı aksi halde DLL arama
            # yolunu bağlantı sürerken kapatabilir.
            self._dll_dizin_handle = os.add_dll_directory(str(dll_dizin))
        except (AttributeError, FileNotFoundError, OSError) as exc:
            raise M50Hata("M50 DLL dizini yüklenemedi: %s" % exc) from exc
        # Üreticinin bağlayıcısı Hvs mutlak paket adını kullanır.
        sys.path.insert(0, str(kok))
        try:
            self._sdk = importlib.import_module("Hvs.sdk")
            self._dat = importlib.import_module("Hvs.datdefs")
        except Exception as exc:
            self._sdk = self._dat = None
            raise M50Hata("M50 SDK Python bağlayıcısı yüklenemedi: %s" % exc) from exc
        finally:
            try:
                sys.path.remove(str(kok))
            except ValueError:
                pass
        self._durum_yaz(sdk_hazir=True)

    def baglan(self, veri: Dict[str, Any]) -> Dict[str, Any]:
        """Operatör tarafından belirtilen M50'ye oturum açar.

        Varsayılan IP yoktur. Kullanıcı adı/parola sadece RAM'de SDK çağrısı
        süresince tutulur; kalıcı ayara kesinlikle yazılmaz.
        """
        if not isinstance(veri, dict):
            raise M50Hata("M50 bağlantı verisi geçersiz")
        ip = _ip_dogrula(veri.get("ip"))
        # IP gibi port da operatör tarafından açıkça girilmelidir; cihaz
        # erişiminde örtük hedef/port varsayımı yapılmaz.
        port = int(_sayi(veri.get("port"), "M50 portu", 1, 65535))
        kullanici = _temiz_metin(veri.get("kullanici"), "M50 kullanıcı adı", 64)
        parola = _temiz_metin(veri.get("parola"), "M50 parolası", 128)
        zaman_asimi = int(_sayi(veri.get("zaman_asimi", 5000), "bağlantı zaman aşımı", 1000, 30000))
        with self._kilit:
            self.kes(_ic=True)
            self._durum_yaz(durum="baglaniyor", bagli=False, ip=ip, port=port, hata="")
            self._sdk_yukle()
            try:
                cihaz = self._sdk.IPC_device(self._dat.DeviceType_e.DEVICE_HPWS)
                basarili = bool(cihaz.Connect(ip.encode("ascii"), port,
                                               kullanici.encode("utf-8"),
                                               parola.encode("utf-8"),
                                               zaman_asimi))
            except Exception as exc:
                # SDK istisnası oturum girdilerini içerebilir; bağlantı
                # hatasını parolayı durum/konsole taşımadan sunuyoruz.
                self._durum_yaz(durum="hata", bagli=False,
                                 hata="M50 SDK bağlantısı kurulamadı")
                raise M50Hata("M50 SDK bağlantısı kurulamadı") from exc
            if not basarili:
                self._durum_yaz(durum="hata", bagli=False,
                                 hata="M50 oturumu doğrulanamadı")
                raise M50Hata("M50 oturumu doğrulanamadı")
            self._cihaz = cihaz
            self._acik_komut = True
            self._son_baglanti = {"ip": ip, "port": port}
            self._durum_yaz(durum="bagli", bagli=True, ip=ip, port=port,
                             hata="", son_islem="baglandi")
        self._yaz("M50 elektro-optik oturumu bağlandı: %s:%d" % (ip, port))
        return self.durum()

    def kes(self, _ic: bool = False) -> Dict[str, Any]:
        with self._kilit:
            cihaz, self._cihaz = self._cihaz, None
            self._acik_komut = False
            if cihaz is not None:
                try:
                    cihaz.StopTrack(self._dat.VideoType_e.VT_LIGHT)
                except Exception:
                    pass
                try:
                    cihaz.StopTrack(self._dat.VideoType_e.VT_IRD)
                except Exception:
                    pass
                try:
                    cihaz.DisConnect()
                except Exception:
                    pass
            self._takip_secildi = {"gorunur": False, "termal": False}
            self._durum_yaz(durum="kapali", bagli=False, ip="", port=0,
                             takip={"etkin": False, "kanal": ""},
                             son_islem="baglanti_kesildi")
        if not _ic:
            self._yaz("M50 elektro-optik bağlantısı kesildi")
        return self.durum()

    def _bagli_cihaz(self):
        with self._kilit:
            if not self._acik_komut or self._cihaz is None:
                raise M50Hata("M50 bağlı değil")
            try:
                if not bool(self._cihaz.IsConnected()):
                    self._durum_yaz(durum="hata", bagli=False,
                                     hata="M50 oturumu kesildi")
                    raise M50Hata("M50 oturumu kesildi")
            except M50Hata:
                raise
            except Exception as exc:
                raise M50Hata("M50 bağlantı durumu okunamadı: %s" % exc) from exc
            return self._cihaz

    def ptz(self, yon: Any, hiz: Any, basili: Any = True) -> Dict[str, Any]:
        """PTZ hareketini yalnız izinli SDK yönleriyle sınırlar."""
        izinli = {
            "dur": "PCT_STATIC", "yukari": "PCT_UP", "asagi": "PCT_DOWN",
            "sol": "PCT_LEFT", "sag": "PCT_RIGHT", "sol_yukari": "PCT_LEFT_UP",
            "sag_yukari": "PCT_RIGHT_UP", "sol_asagi": "PCT_LEFT_DOWN",
            "sag_asagi": "PCT_RIGHT_DOWN",
        }
        anahtar = str(yon or "").strip().lower()
        if anahtar not in izinli:
            raise M50Hata("izin verilmeyen M50 PTZ yönü")
        hiz_i = int(_sayi(hiz, "PTZ hızı", M50_HIZ_MIN, M50_HIZ_MAX))
        cihaz = self._bagli_cihaz()
        try:
            enum = getattr(self._dat.PtzControlType_e, izinli[anahtar])
            basarili = bool(cihaz.ControlMove(enum, bool(basili), hiz_i, hiz_i))
        except Exception as exc:
            raise M50Hata("M50 PTZ komutu başarısız: %s" % exc) from exc
        if not basarili:
            raise M50Hata("M50 PTZ komutu kabul edilmedi")
        self._durum_yaz(son_islem="ptz:%s" % anahtar)
        return self.durum()

    def lens(self, eylem: Any, kanal: Any, basili: Any = True) -> Dict[str, Any]:
        izinli = {"zoom_artir": "CCT_ZOOM_IN", "zoom_azalt": "CCT_ZOOM_OUT",
                  "odak_yakin": "CCT_FOCUS_NEAR", "odak_uzak": "CCT_FOCUS_FAR",
                  "iris_ac": "CCT_IRIS_OPEN", "iris_kapat": "CCT_IRIS_CLOSE"}
        eylem = str(eylem or "").strip().lower()
        if eylem not in izinli:
            raise M50Hata("izin verilmeyen M50 lens komutu")
        video = self._video_enum(kanal)
        cihaz = self._bagli_cihaz()
        try:
            basarili = bool(cihaz.CameraMove(getattr(self._dat.CameraType_e, izinli[eylem]),
                                              bool(basili), video))
        except Exception as exc:
            raise M50Hata("M50 lens komutu başarısız: %s" % exc) from exc
        if not basarili:
            raise M50Hata("M50 lens komutu kabul edilmedi")
        self._durum_yaz(son_islem="lens:%s" % eylem)
        return self.durum()

    def _video_enum(self, kanal: Any):
        ad = str(kanal or "gorunur").strip().lower()
        if ad == "gorunur":
            return self._dat.VideoType_e.VT_LIGHT
        if ad == "termal":
            return self._dat.VideoType_e.VT_IRD
        raise M50Hata("M50 video kanalı 'gorunur' veya 'termal' olmalıdır")

    def aci_konumla(self, azimut: Any, egim: Any, hiz: Any) -> Dict[str, Any]:
        cihaz = self._bagli_cihaz()
        x = _sayi(azimut, "azimut", M50_AZIMUT_MIN, M50_AZIMUT_MAX)
        y = _sayi(egim, "eğim", M50_EGIM_MIN, M50_EGIM_MAX)
        hiz_i = int(_sayi(hiz, "konumlama hızı", M50_HIZ_MIN, M50_HIZ_MAX))
        try:
            basarili = bool(cihaz.PositionXY(x, y, hiz_i))
        except Exception as exc:
            raise M50Hata("M50 konum komutu başarısız: %s" % exc) from exc
        if not basarili:
            raise M50Hata("M50 konum komutu kabul edilmedi")
        self._durum_yaz(azimut=x, egim=y, son_islem="aci_konumla")
        return self.durum()

    def takip_baslat(self, kanal: Any, mod: Any = "hava_yari_otomatik") -> Dict[str, Any]:
        """Seçimden sonra takip modunu açık operatör komutuyla başlatır."""
        # SDK'nın otomatik hedef edinim modları sistem arayüzüne açılmaz.
        # Her takip, operatörün elle çizdiği tek hedef seçimine dayanır.
        modlar = {"hava_yari_otomatik": "TRACK_AIR_SEMIAUTO",
                  "kara_manuel": "TRACK_GROUND_MANUAL",
                  "kara_yari_otomatik": "TRACK_GROUND_SEMIAUTO"}
        mod = str(mod or "").strip().lower()
        if mod not in modlar:
            raise M50Hata("izin verilmeyen M50 takip modu")
        kanal_ad = "termal" if str(kanal).lower() == "termal" else "gorunur"
        if not self._takip_secildi.get(kanal_ad):
            raise M50Hata("takip için önce operatörün manuel hedef dikdörtgeni gerekir")
        video = self._video_enum(kanal)
        cihaz = self._bagli_cihaz()
        try:
            if not bool(cihaz.EnableTrackAbility(video, True)):
                raise M50Hata("M50 takip yeteneği etkinleştirilemedi")
            if not bool(cihaz.SetTrackMode(video, getattr(self._dat.TrackMode_e, modlar[mod]))):
                raise M50Hata("M50 takip modu kabul edilmedi")
            if not bool(cihaz.StartTrack(video)):
                raise M50Hata("M50 takip başlatma komutu kabul edilmedi")
        except M50Hata:
            raise
        except Exception as exc:
            raise M50Hata("M50 takip başlatılamadı: %s" % exc) from exc
        self._takip_secildi[kanal_ad] = False
        self._durum_yaz(takip={"etkin": True, "kanal": kanal_ad},
                         son_islem="takip_baslat:%s" % mod)
        return self.durum()

    def takip_durdur(self, kanal: Any) -> Dict[str, Any]:
        video = self._video_enum(kanal)
        cihaz = self._bagli_cihaz()
        try:
            basarili = bool(cihaz.StopTrack(video))
        except Exception as exc:
            raise M50Hata("M50 takip durdurulamadı: %s" % exc) from exc
        if not basarili:
            raise M50Hata("M50 takip durdurma komutu kabul edilmedi")
        kanal_ad = "termal" if str(kanal).lower() == "termal" else "gorunur"
        self._takip_secildi[kanal_ad] = False
        self._durum_yaz(takip={"etkin": False, "kanal": ""},
                         son_islem="takip_durdur")
        return self.durum()

    def takip_sec(self, kanal: Any, video_dikdortgen: Dict[str, Any], secim: Dict[str, Any]) -> Dict[str, Any]:
        """Operatörün görüntü üzerinde seçtiği dikdörtgeni SDK'ya aktarır."""
        video = self._video_enum(kanal)
        def dikdortgen(ham: Dict[str, Any], ad: str) -> Tuple[int, int, int, int]:
            if not isinstance(ham, dict):
                raise M50Hata("%s dikdörtgeni geçersiz" % ad)
            try:
                sol, ust = int(ham["sol"]), int(ham["ust"])
                sag, alt = int(ham["sag"]), int(ham["alt"])
            except (KeyError, TypeError, ValueError) as exc:
                raise M50Hata("%s dikdörtgeni eksik" % ad) from exc
            if not (0 <= sol < sag <= M50_MAX_PIKSEL and 0 <= ust < alt <= M50_MAX_PIKSEL):
                raise M50Hata("%s dikdörtgeni sınır dışında" % ad)
            return sol, ust, sag, alt
        vs, vu, vsag, valt = dikdortgen(video_dikdortgen, "video")
        ss, su, ssag, salt = dikdortgen(secim, "seçim")
        if not (vs <= ss < ssag <= vsag and vu <= su < salt <= valt):
            raise M50Hata("takip seçimi video alanının dışında")
        cihaz = self._bagli_cihaz()
        try:
            Rect = importlib.import_module("Hvs.track").Rect
            vr, sr = Rect(), Rect()
            vr.left, vr.top, vr.right, vr.bottom = vs, vu, vsag, valt
            sr.left, sr.top, sr.right, sr.bottom = ss, su, ssag, salt
            basarili = bool(cihaz.SelectRectTrack(video, vr, sr))
        except Exception as exc:
            raise M50Hata("M50 takip seçimi gönderilemedi: %s" % exc) from exc
        if not basarili:
            raise M50Hata("M50 takip seçimi kabul edilmedi")
        kanal_ad = "termal" if str(kanal).lower() == "termal" else "gorunur"
        self._takip_secildi[kanal_ad] = True
        self._durum_yaz(son_islem="takip_sec")
        return self.durum()

    def rtsp_url(self, kanal: Any) -> Optional[str]:
        """Cihazın kendi yayınladığı RTSP adresini SDK'dan okur.

        Operatörün elle bir RTSP adresi girmesine GEREK KALMAZ: M50
        `HVS_GetRtspUrl` ile kendi akış adresini bildirir. Bağlı
        değilse, SDK çağrısı başarısızsa ya da dönen değer kimlik
        bilgisi taşıyan/şüpheli bir URI ise `None` döner — çağıran yer
        (varsa) operatörün elle girdiği adrese düşer.
        """
        try:
            cihaz = self._bagli_cihaz()
        except M50Hata:
            return None
        try:
            video = self._video_enum(kanal)
            ham = cihaz.GetRtspUrl(video, 0)
        except Exception:
            return None
        if not ham:
            return None
        try:
            ayrik = urlparse(str(ham).strip())
        except Exception:
            return None
        if ayrik.scheme.lower() not in ("rtsp", "rtsps") or not ayrik.hostname:
            return None
        # İkinci savunma hattı: cihaz sürümü/donanımı URI'ye kullanıcı
        # bilgisi gömse dahi bu asla telemetriye/duruma taşınmaz.
        if (ayrik.username is not None or ayrik.password is not None or
                ayrik.query or ayrik.fragment):
            return None
        return str(ham).strip()
