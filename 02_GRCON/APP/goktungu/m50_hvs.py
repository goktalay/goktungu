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
import math
import re
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
M50_HIZ_MIN, M50_HIZ_MAX = 1, 60   # v2.4.205: kullanici istegi, ust sinir 60
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
            "tarama": {"tur": "yok", "kontrol": "durdur", "yol": 0},
            # v2.4.191: cihazın kendi RTK/GPS konumu ve pusulası (konum_oku)
            "konum": None, "pusula": None,
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
        windows = platform.system().lower() == "windows"
        for kok in adaylar:
            if not (kok / "Hvs" / "sdk.py").is_file():
                continue
            if windows and ((kok / "HVideoSDK.dll").is_file() or
                            (kok / "bin" / "HVideoSDK.dll").is_file()):
                return kok
            # v2.4.216: Linux — ureticinin .so paketi (aarch64 ile dogrulandi)
            if not windows and ((kok / "lib" / "libHVideoSDK.so").is_file() or
                                (kok / "libHVideoSDK.so").is_file()):
                return kok
        if windows:
            raise M50Hata("M50 Windows SDK bulunamadı; desteklenen SDK paketini kurun")
        raise M50Hata("M50 Linux SDK (lib/libHVideoSDK.so) bulunamadı; bu mimari için "
                      "üreticinin Linux paketi gerekir (%s)" % platform.machine())

    @classmethod
    def yerli_sdk_var(cls, ayar=None) -> bool:
        """Bu platformda SDK dogrudan yuklenebilir mi? (Wine'a gerek var mi?)"""
        try:
            cls._sdk_kok(ayar or {})
        except Exception:
            return False
        if platform.system().lower() == "windows":
            return platform.architecture()[0] == "64bit"
        # Linux: .so'nun mimarisi ile makine uyusmali (aarch64 paketi x86_64'te yuklenmez)
        try:
            kok = cls._sdk_kok(ayar or {})
            so = kok / "lib" / "libHVideoSDK.so"
            if not so.is_file():
                so = kok / "libHVideoSDK.so"
            with open(so, "rb") as f:
                bas = f.read(20)
            e_machine = int.from_bytes(bas[18:20], "little")
            mak = platform.machine().lower()
            return (e_machine == 183 and mak in ("aarch64", "arm64")) or \
                   (e_machine == 62 and mak in ("x86_64", "amd64"))
        except Exception:
            return False

    def _sdk_yukle(self) -> None:
        windows = platform.system().lower() == "windows"
        if windows and platform.architecture()[0] != "64bit":
            raise M50Hata("M50 HVS SDK yalnız 64 bit Windows'ta çalışır")
        if self._sdk is not None:
            return
        ayar = self._ayar_oku() or {}
        kok = self._sdk_kok(ayar)
        if windows:
            dll_dizin = kok / "bin" if (kok / "bin" / "HVideoSDK.dll").is_file() else kok
            try:
                # Dönüş nesnesi tutulur; çöp toplayıcı aksi halde DLL arama
                # yolunu bağlantı sürerken kapatabilir.
                self._dll_dizin_handle = os.add_dll_directory(str(dll_dizin))
            except (AttributeError, FileNotFoundError, OSError) as exc:
                raise M50Hata("M50 DLL dizini yüklenemedi: %s" % exc) from exc
        else:
            # v2.4.216: Linux — .so dizini bağlayıcıya ortamla bildirilir.
            if not self.yerli_sdk_var(ayar):
                raise M50Hata("M50 Linux SDK bu makinenin mimarisiyle (%s) uyuşmuyor"
                              % platform.machine())
            lib_dizin = kok / "lib" if (kok / "lib" / "libHVideoSDK.so").is_file() else kok
            os.environ["GOKTUNGU_M50_SDK_LIB"] = str(lib_dizin)
        # Üreticinin bağlayıcısı Hvs mutlak paket adını kullanır.
        sys.path.insert(0, str(kok))
        try:
            self._sdk = importlib.import_module("Hvs.sdk")
            self._dat = importlib.import_module("Hvs.datdefs")
        except Exception as exc:
            self._sdk = self._dat = None
            # Linux'ta en sik neden eksik sistem kutuphanesi (libtiff.so.5,
            # libasound2, libX11...); OSError iletisi hangi dosyanin
            # eksik oldugunu soyler — aynen aktarilir.
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

    # ------------------------------------------------------------------
    # v2.4.188 — SDK'nın geri kalanı: açı okuma, ön ayarlar, tarama,
    # takip yeteneği/modu. Hepsi üreticinin DemoPy/main.py örneğindeki
    # çağrı biçimlerini birebir izler.
    # ------------------------------------------------------------------
    def aci_oku(self) -> Dict[str, Any]:
        """Canlı azimut/eğim (GetAngleX/Y). Bağlı değilse None bırakır."""
        cihaz = self._bagli_cihaz()
        ct = importlib.import_module("ctypes")
        x, y = ct.c_double(), ct.c_double()
        try:
            okx = bool(cihaz.GetAngleX(x))
            oky = bool(cihaz.GetAngleY(y))
        except Exception as exc:
            raise M50Hata("M50 açı okunamadı: %s" % exc) from exc
        self._durum_yaz(azimut=round(x.value, 2) if okx else None,
                        egim=round(y.value, 2) if oky else None)
        return self.durum()

    def onayarlar(self) -> list:
        """Cihazdaki ön ayar (preset) listesi: [{no, ad}]."""
        cihaz = self._bagli_cihaz()
        ct = importlib.import_module("ctypes")
        PresetInfo_t = importlib.import_module("Hvs.preset").PresetInfo_t
        bilgi = ct.POINTER(PresetInfo_t)()
        sayi = ct.c_int()
        try:
            if not bool(cihaz.GetPresets(bilgi, sayi)):
                return []
            liste = []
            for i in range(max(0, min(int(sayi.value), 256))):
                try:
                    ad = bilgi[i].name.decode("utf-8", errors="replace").strip("\x00 ")
                except Exception:
                    ad = ""
                liste.append({"no": int(bilgi[i].preset), "ad": ad})
            try:
                cihaz.FreePresets(bilgi, sayi)
            except Exception:
                pass
            return liste
        except M50Hata:
            raise
        except Exception as exc:
            raise M50Hata("M50 ön ayarları okunamadı: %s" % exc) from exc

    @staticmethod
    def _onayar_no(no: Any) -> int:
        return int(_sayi(no, "ön ayar numarası", 0, 255))

    def onayar_kaydet(self, no: Any, ad: Any, hiz: Any = 5) -> Dict[str, Any]:
        n = self._onayar_no(no)
        ad_m = _temiz_metin(ad or ("Onayar %d" % n), "ön ayar adı", 64)
        hiz_i = int(_sayi(hiz, "ön ayar hızı", 1, 63))
        cihaz = self._bagli_cihaz()
        try:
            ok = bool(cihaz.SetPreset(n, ad_m.encode("utf-8"), hiz_i))
        except Exception as exc:
            raise M50Hata("M50 ön ayar kaydedilemedi: %s" % exc) from exc
        if not ok:
            raise M50Hata("M50 ön ayar kaydı kabul edilmedi")
        self._durum_yaz(son_islem="onayar_kaydet:%d" % n)
        return self.durum()

    def onayar_cagir(self, no: Any) -> Dict[str, Any]:
        n = self._onayar_no(no)
        cihaz = self._bagli_cihaz()
        try:
            ok = bool(cihaz.CallPreset(n))
        except Exception as exc:
            raise M50Hata("M50 ön ayara gidilemedi: %s" % exc) from exc
        if not ok:
            raise M50Hata("M50 ön ayar çağrısı kabul edilmedi")
        self._durum_yaz(son_islem="onayar_cagir:%d" % n)
        return self.durum()

    def onayar_sil(self, no: Any) -> Dict[str, Any]:
        n = self._onayar_no(no)
        cihaz = self._bagli_cihaz()
        try:
            ok = bool(cihaz.ClearPreset(n))
        except Exception as exc:
            raise M50Hata("M50 ön ayar silinemedi: %s" % exc) from exc
        if not ok:
            raise M50Hata("M50 ön ayar silme kabul edilmedi")
        self._durum_yaz(son_islem="onayar_sil:%d" % n)
        return self.durum()

    def onayar_hepsini_sil(self) -> Dict[str, Any]:
        cihaz = self._bagli_cihaz()
        try:
            ok = bool(cihaz.ClearAllPreset())
        except Exception as exc:
            raise M50Hata("M50 ön ayarlar silinemedi: %s" % exc) from exc
        if not ok:
            raise M50Hata("M50 tüm ön ayarları silme kabul edilmedi")
        self._durum_yaz(son_islem="onayar_hepsini_sil")
        return self.durum()

    def tarama(self, tur: Any, kontrol: Any, yol: Any = 0) -> Dict[str, Any]:
        """Tarama/devriye: tür (onayar/yatay/panorama/yelpaze/kare/desen/dikey)
        ve kontrol (baslat/durdur/duraklat/devam)."""
        turler = {"yok": "SCAN_TYPE_NONE", "onayar": "SCAN_TYPE_PRESET",
                  "yatay": "SCAN_TYPE_HORIZONTAL", "panorama": "SCAN_TYPE_PANORAMA",
                  "yelpaze": "SCAN_TYPE_FAN", "kare": "SCAN_TYPE_FRAME",
                  "desen": "SCAN_TYPE_PATTERN", "dikey": "SCAN_TYPE_VERTICAL"}
        kontroller = {"baslat": "SCT_START", "durdur": "SCT_STOP",
                      "duraklat": "SCT_PAUSE", "devam": "SCT_CONTINUE"}
        t = str(tur or "").strip().lower()
        k = str(kontrol or "").strip().lower()
        if t not in turler:
            raise M50Hata("izin verilmeyen M50 tarama türü")
        if k not in kontroller:
            raise M50Hata("izin verilmeyen M50 tarama kontrolü")
        yol_i = int(_sayi(yol, "tarama yolu", 0, 31))
        cihaz = self._bagli_cihaz()
        try:
            ok = bool(cihaz.ControlScan(getattr(self._dat.ScanType_e, turler[t]),
                                        getattr(self._dat.ScanCtrlType_e, kontroller[k]),
                                        yol_i))
        except Exception as exc:
            raise M50Hata("M50 tarama komutu başarısız: %s" % exc) from exc
        if not ok:
            raise M50Hata("M50 tarama komutu kabul edilmedi")
        self._durum_yaz(tarama={"tur": t, "kontrol": k, "yol": yol_i},
                        son_islem="tarama:%s:%s" % (t, k))
        return self.durum()

    def takip_yetenek(self, kanal: Any, etkin: Any) -> Dict[str, Any]:
        video = self._video_enum(kanal)
        cihaz = self._bagli_cihaz()
        try:
            ok = bool(cihaz.EnableTrackAbility(video, bool(etkin)))
        except Exception as exc:
            raise M50Hata("M50 takip yeteneği değiştirilemedi: %s" % exc) from exc
        if not ok:
            raise M50Hata("M50 takip yeteneği komutu kabul edilmedi")
        self._durum_yaz(son_islem="takip_yetenek:%s" % ("acik" if etkin else "kapali"))
        return self.durum()

    def takip_modu_oku(self, kanal: Any) -> Optional[str]:
        video = self._video_enum(kanal)
        cihaz = self._bagli_cihaz()
        ct = importlib.import_module("ctypes")
        mod = ct.c_int()
        # IPC_device.GetTrackMode sarmalayıcısı `mode.value` çağırıp
        # DEĞER geçirir (çıkış parametresi olamaz); ham bağlayıcı byref
        # ile doğrudan çağrılır. `__handle__` çift alt çizgiyle bittiği
        # için ad karıştırmaya (name mangling) uğramaz.
        try:
            if not bool(importlib.import_module("Hvs.track").GetTrackMode(
                    cihaz.__handle__, video.value, ct.byref(mod))):
                return None
        except Exception:
            return None
        ters = {0: "hava_yari_otomatik", 1: "hava_otomatik", 2: "kara_manuel",
                3: "kara_yari_otomatik", 4: "kara_otomatik"}
        return ters.get(int(mod.value))

    # ------------------------------------------------------------------
    # v2.4.191 — Cihazın kendi konumu (RTK/GPS) ve pusulası.
    # `HVS_GetDevicePos` üretici başlığında "(Disabled)"; çevre birimi
    # yolu (HVS_GetExternDeviceInfo, ED_GPS/ED_COMPASS) geri çağrıyla
    # veri verir. Geri çağrı nesnesi `self._dis_cb` içinde tutulur;
    # çöp toplayıcı alırsa SDK serbest bırakılmış adrese döner.
    # ------------------------------------------------------------------
    def konum_oku(self) -> Dict[str, Any]:
        cihaz = self._bagli_cihaz()
        ct = importlib.import_module("ctypes")
        dev = importlib.import_module("Hvs.device")
        if getattr(self, "_dis_cb", None) is None:
            def _cb(user, tur, veri, boyut):
                try:
                    if tur == 1:
                        # v2.4.206 TANI (kullanici: "Konum al 0.00000 atiyor",
                        # "harita ikonu yok"): SDK yapisi (lon,lat,alt double)
                        # ile gercek veri uyusmazsa okunan degerler sifira
                        # yakin cop (denormal) olur; eski (lat or lon) denetimi
                        # bunu GECERLI sayip RTK konumu 0,0'a yaziyordu — ikon
                        # Null Island'a dusuyor, form 0.0000000 doluyordu.
                        # Ilk geri cagrinin ham baytlari gunluge alinir.
                        if "konum_tani" not in self._durum:
                            n = max(0, min(int(boyut or 0), 64))
                            ham = ct.string_at(veri, n).hex() if (veri and n) else ""
                            self._durum_yaz(konum_tani="GPS cb boyut=%s beklenen=%s ham=%s"
                                            % (boyut, ct.sizeof(dev.GPSData_t), ham))
                    if tur == 1 and boyut >= ct.sizeof(dev.GPSData_t):
                        g = ct.cast(veri, ct.POINTER(dev.GPSData_t)).contents
                        lat, lon, alt = float(g.lat), float(g.lon), float(g.alt)
                        # v2.4.212 OLCUM (kullanici gunlugu): ham 24 bayt uc adet
                        # x64 ISARETCI (…fc7f0000) — veri gomulu double DEGIL,
                        # double*/char* dizisi. Isaretciler cozulur: once double,
                        # sonra metin (or. "39.97"); makul olan alinir.
                        try:
                            ptrs = ct.cast(veri, ct.POINTER(ct.c_void_p * 3)).contents
                            cozum = []
                            for pi in range(3):
                                pv = ptrs[pi]
                                if not pv or pv < 0x10000:
                                    cozum.append(None); continue
                                d = None
                                try:
                                    dv = ct.cast(pv, ct.POINTER(ct.c_double)).contents.value
                                    if math.isfinite(dv) and abs(dv) < 1e7:
                                        d = dv
                                except Exception:
                                    d = None
                                if d is None or abs(d) < 1e-6:
                                    try:
                                        sv = ct.string_at(pv, 32).split(b"\x00", 1)[0].decode("ascii", "ignore").strip()
                                        m = re.search(r"-?\d+(?:\.\d+)?", sv)
                                        if m:
                                            d = float(m.group(0))
                                    except Exception:
                                        pass
                                cozum.append(d)
                            if "konum_tani2" not in self._durum:
                                self._durum_yaz(konum_tani2="GPS ptr cozum lon/lat/alt=%r" % (cozum,))
                            c_lon, c_lat, c_alt = cozum
                            if (c_lat is not None and c_lon is not None and
                                    -90.0 <= c_lat <= 90.0 and -180.0 <= c_lon <= 180.0 and
                                    (abs(c_lat) >= 1e-3 or abs(c_lon) >= 1e-3)):
                                lat, lon = c_lat, c_lon
                                alt = c_alt if (c_alt is not None and abs(c_alt) < 50000) else 0.0
                        except Exception:
                            pass
                        makul = (math.isfinite(lat) and math.isfinite(lon) and math.isfinite(alt)
                                 and -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0
                                 and (abs(lat) >= 1e-3 or abs(lon) >= 1e-3)
                                 and abs(alt) < 50000.0)
                        if makul:
                            self._durum_yaz(konum={"lat": round(lat, 7), "lon": round(lon, 7),
                                                   "alt": round(alt, 1), "ts": time.time(),
                                                   "kaynak": "rtk"})
                        elif isinstance(self._durum.get("konum"), dict) and \
                                self._durum["konum"].get("kaynak") == "rtk":
                            self._durum_yaz(konum=None)   # bayat/gecersiz RTK temizlenir
                    elif tur == 0 and boyut >= ct.sizeof(dev.CompassData_t):
                        c = ct.cast(veri, ct.POINTER(dev.CompassData_t)).contents
                        self._durum_yaz(pusula={"yon": round(float(c.angleX), 2) % 360.0,
                                                "egim": round(float(c.angleY), 2),
                                                "yatis": round(float(c.angleZ), 2),
                                                "ts": time.time()})
                except Exception:
                    pass
            self._dis_cb = dev.ExternData_CB(_cb)
        try:
            cihaz.GetExternDeviceInfo(1, self._dis_cb, None)   # GPS
            cihaz.GetExternDeviceInfo(0, self._dis_cb, None)   # pusula
        except Exception as exc:
            raise M50Hata("M50 konum/pusula istenemedi: %s" % exc) from exc
        return self.durum()

    # ------------------------------------------------------------------
    # v2.4.215 — CİHAZ OSD'Sİ (kareye basılan yazı). Yapı üreticinin
    # datdefs.h (OSD_INFO, `_OsdInfo`) tanımından birebir aktarıldı;
    # POINTEx_t = {long x; long y} (Windows x64'te long = 4 bayt, ctypes
    # c_long buna uyar). Desen belge örneğiyle aynı: Get → değiştir → Set.
    # ------------------------------------------------------------------
    _OSD_KONUM_ALANLARI = ("namePos", "timePos", "osdPtzPos", "osdCompassPos")
    _OSD_BOOL_ALANLARI = ("displayWeek", "displayPtz", "displayFocalPos", "displayFov",
                          "displayZoomTimes", "showMilliSec", "snapshotOsd", "cpuInfo",
                          "displayFocalMax", "showCtrlStatus", "displayPtzState",
                          "displayLensSelf", "displayTrackState", "displayPtzAngDir",
                          "multiLine", "colorInvert", "horCoord", "cross", "showGrid",
                          "crossRuler", "showCompass", "showGPS", "displaySelfDefine",
                          "dpyLaserRange", "dpyCoolIrUnuserTime", "dpyBurglaAlarm",
                          "dpySelfDefineLaserRange")
    _OSD_INT_ALANLARI = {"fontSize": (16, 64), "channelNameAlign": (0, 1), "timeFormat": (0, 2),
                         "timeMode": (0, 1), "timeAlign": (0, 1), "ptzAlign": (0, 1),
                         "ptzMode": (0, 9), "ptzAngleDecCount": (0, 2), "zoomDisMode": (0, 1),
                         "compassAlign": (0, 1), "crossPosType": (0, 1), "crossType": (0, 1),
                         "rulerType": (0, 1), "crossAlpha": (0, 128), "osdOtherRegionType": (0, 2),
                         "regionWidthCoef": (1, 100), "regionHeightCoef": (1, 100)}
    _OSD_METIN_ALANLARI = {"crossColor": 16, "fontColor": 16, "radarInfo": 128, "selfDefineSetOsd": 128}

    def _osd_yapisi(self):
        ct = importlib.import_module("ctypes")
        if getattr(self, "_OsdInfo", None) is not None:
            return ct, self._OsdInfo

        class POINTEx_t(ct.Structure):
            _fields_ = [("x", ct.c_long), ("y", ct.c_long)]

        class OsdInfo_t(ct.Structure):
            _fields_ = [
                ("channel", ct.c_int), ("fontSize", ct.c_int),
                ("channelName", (ct.c_char * 256) * 8),
                ("namePos", ct.c_int), ("namePosCoord", POINTEx_t), ("channelNameAlign", ct.c_int),
                ("timeFormat", ct.c_int), ("timeMode", ct.c_int), ("displayWeek", ct.c_bool),
                ("timePos", ct.c_int), ("timePosCoord", POINTEx_t), ("timeAlign", ct.c_int),
                ("osdPtzPos", ct.c_int), ("osdPtzCoord", POINTEx_t), ("ptzAlign", ct.c_int),
                ("displayPtz", ct.c_bool), ("displayFocalPos", ct.c_bool), ("displayFov", ct.c_bool),
                ("displayZoomTimes", ct.c_bool), ("showMilliSec", ct.c_bool), ("snapshotOsd", ct.c_bool),
                ("cpuInfo", ct.c_bool), ("displayFocalMax", ct.c_bool), ("showCtrlStatus", ct.c_bool),
                ("displayPtzState", ct.c_bool), ("displayLensSelf", ct.c_bool), ("displayTrackState", ct.c_bool),
                ("displayPtzAngDir", ct.c_bool), ("multiLine", ct.c_bool), ("colorInvert", ct.c_bool),
                ("horCoord", ct.c_bool), ("dirCoord", POINTEx_t),
                ("ptzMode", ct.c_int), ("ptzAngleDecCount", ct.c_int), ("zoomDisMode", ct.c_int),
                ("regionWidthCoef", ct.c_int), ("regionHeightCoef", ct.c_int),
                ("osdCompassPos", ct.c_int), ("osdCompassPosAuto", POINTEx_t), ("compassAlign", ct.c_int),
                ("cross", ct.c_bool), ("crossPosType", ct.c_int), ("crossCoord", POINTEx_t),
                ("crossType", ct.c_int), ("crossColor", ct.c_char * 16), ("fontColor", ct.c_char * 16),
                ("rulerType", ct.c_int), ("showGrid", ct.c_bool), ("crossAlpha", ct.c_int),
                ("crossRuler", ct.c_bool), ("showCompass", ct.c_bool), ("showGPS", ct.c_bool),
                ("displaySelfDefine", ct.c_bool), ("radarInfo", ct.c_char * 128),
                ("osdOtherRegionType", ct.c_int), ("osdOtherRegion", POINTEx_t),
                ("dpyLaserRange", ct.c_bool), ("dpyCoolIrUnuserTime", ct.c_bool),
                ("dpyBurglaAlarm", ct.c_bool), ("dpySelfDefineLaserRange", ct.c_bool),
                ("selfDefineSetOsd", ct.c_char * 128), ("reserved", ct.c_char * 1024),
            ]
        self._POINTEx = POINTEx_t
        self._OsdInfo = OsdInfo_t
        return ct, OsdInfo_t

    def _osd_fonksiyon(self, ad: str):
        ct, OsdInfo_t = self._osd_yapisi()
        dat = self._dat
        fn = getattr(dat.sdk, ad)
        fn.restype = ct.c_bool
        if ad == "HVS_SetOsdInfo":
            fn.argtypes = [ct.c_int, ct.POINTER(OsdInfo_t)]
        else:
            fn.argtypes = [ct.c_int, ct.c_int, ct.POINTER(OsdInfo_t)]
        return fn

    @staticmethod
    def _osd_kanal_no(kanal: Any) -> int:
        ad = str(kanal or "gorunur").strip().lower()
        if ad in ("gorunur", "0"):
            return 0
        if ad in ("termal", "1"):
            return 1
        raise M50Hata("M50 OSD kanalı 'gorunur' veya 'termal' olmalıdır")

    def _osd_sozluk(self, o) -> Dict[str, Any]:
        def metin(b):
            try:
                return bytes(b).split(b"\x00", 1)[0].decode("utf-8", "replace")
            except Exception:
                return ""
        d: Dict[str, Any] = {"channel": int(o.channel)}
        for a in self._OSD_INT_ALANLARI:
            d[a] = int(getattr(o, a))
        for a in self._OSD_BOOL_ALANLARI:
            d[a] = bool(getattr(o, a))
        for a in self._OSD_KONUM_ALANLARI:
            d[a] = int(getattr(o, a))
        for a in self._OSD_METIN_ALANLARI:
            d[a] = metin(getattr(o, a))
        d["channelName"] = [metin(o.channelName[i]) for i in range(8)]
        for a in ("namePosCoord", "timePosCoord", "osdPtzCoord", "osdCompassPosAuto", "crossCoord", "dirCoord", "osdOtherRegion"):
            p = getattr(o, a)
            d[a] = {"x": int(p.x), "y": int(p.y)}
        return d

    def _osd_getir(self, kanal_no: int):
        ct, OsdInfo_t = self._osd_yapisi()
        cihaz = self._bagli_cihaz()
        o = OsdInfo_t()
        fn = self._osd_fonksiyon("HVS_GetOsdInfo")
        try:
            ok = bool(fn(int(cihaz.__handle__), int(kanal_no), ct.byref(o)))
        except Exception as exc:
            raise M50Hata("M50 OSD okunamadı: %s" % exc) from exc
        if not ok:
            raise M50Hata("M50 OSD bilgisi cihazdan alınamadı (kanal %d)" % kanal_no)
        return ct, o

    def osd_oku(self, kanal: Any) -> Dict[str, Any]:
        kn = self._osd_kanal_no(kanal)
        _ct, o = self._osd_getir(kn)
        return self._osd_sozluk(o)

    def osd_yaz(self, kanal: Any, alanlar: Any) -> Dict[str, Any]:
        """Get → yalnız verilen alanları değiştir → Set (belge örneği)."""
        if not isinstance(alanlar, dict):
            raise M50Hata("OSD alanları sözlük olmalıdır")
        kn = self._osd_kanal_no(kanal)
        ct, o = self._osd_getir(kn)
        o.channel = kn
        for a, (alt, ust) in self._OSD_INT_ALANLARI.items():
            if a in alanlar:
                try:
                    v = int(alanlar[a])
                except (TypeError, ValueError):
                    raise M50Hata("OSD alanı sayı olmalı: %s" % a)
                if a == "fontSize":
                    v = max(16, min(64, int(round(v / 8.0)) * 8))
                setattr(o, a, max(alt, min(ust, v)))
        for a in self._OSD_KONUM_ALANLARI:
            if a in alanlar:
                try:
                    setattr(o, a, max(0, min(5, int(alanlar[a]))))
                except (TypeError, ValueError):
                    raise M50Hata("OSD konumu sayı olmalı: %s" % a)
        for a in self._OSD_BOOL_ALANLARI:
            if a in alanlar:
                setattr(o, a, bool(alanlar[a]))
        for a, uz in self._OSD_METIN_ALANLARI.items():
            if a in alanlar:
                b = str(alanlar[a] or "").encode("utf-8")[:uz - 1]
                setattr(o, a, b)
        adlar = alanlar.get("channelName")
        if isinstance(adlar, str):
            adlar = [adlar]
        if isinstance(adlar, list):
            for i, ad in enumerate(adlar[:8]):
                b = str(ad or "").encode("utf-8")[:255]
                tampon = (ct.c_char * 256)()
                tampon.value = b
                o.channelName[i] = tampon
        for a in ("namePosCoord", "timePosCoord", "osdPtzCoord", "osdCompassPosAuto", "crossCoord"):
            p = alanlar.get(a)
            if isinstance(p, dict):
                try:
                    getattr(o, a).x = max(0, min(100, int(p.get("x", 0))))
                    getattr(o, a).y = max(0, min(100, int(p.get("y", 0))))
                except (TypeError, ValueError):
                    pass
        fn = self._osd_fonksiyon("HVS_SetOsdInfo")
        cihaz = self._bagli_cihaz()
        try:
            ok = bool(fn(int(cihaz.__handle__), ct.byref(o)))
        except Exception as exc:
            raise M50Hata("M50 OSD yazılamadı: %s" % exc) from exc
        if not ok:
            raise M50Hata("M50 OSD ayarı cihaz tarafından kabul edilmedi")
        self._durum_yaz(son_islem="osd_yaz:%d" % kn)
        _ct2, o2 = self._osd_getir(kn)
        return self._osd_sozluk(o2)

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
        # v2.4.204 OLCULEN KUSUR (kullanici: "PTZ calisiyor ama goruntu
        # gelmiyor"): cihaz URI'ye kullanici bilgisi gomdugunde bu yordam
        # None donuyor, kamera "adres bildirilmedi" hatasiyla hic
        # acilmiyordu. Kimlik yine telemetriye/duruma TASINMAZ: adres
        # ARINDIRILARAK (kullanici/parola/sorgu atilarak) doner; yakalama
        # katmani gerekirse kayitli kimligi kendi ekler.
        port = (":%d" % ayrik.port) if ayrik.port else ""
        return "%s://%s%s%s" % (ayrik.scheme.lower(), ayrik.hostname, port,
                                ayrik.path or "/")
