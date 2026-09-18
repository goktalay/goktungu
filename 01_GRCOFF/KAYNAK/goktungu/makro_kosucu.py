# -*- coding: utf-8 -*-
"""GOKTUNGU MAKRO KOSUCUSU (v2.4.243, IS137) -- ayri surecte calisir.

Kullanim (MakroCalistirici tarafindan): python -I -u makro_kosucu.py <makro.py>
Ortam: GOKTUNGU_MAKRO_SYSID, GOKTUNGU_MAKRO_PORT (9000+sysid MAVLink UDP
aynasi), GOKTUNGU_MAKRO_PORTLAR (json sysid->port), GOKTUNGU_MAKRO_SURE,
GOKTUNGU_MAKRO_DIZIN.

## KISITLAR (sandbox)

* Kaynak sinirlari: bellek, CPU, dosya boyutu, acik dosya (POSIX).
* Soketler YALNIZ 127.0.0.1'e baglanabilir (MAVLink aynasi); dis aga cikis yok.
* `subprocess`, `ctypes`, `multiprocessing`, `shutil` vb. iceri alinamaz;
  `os.system/popen/exec*/fork/kill/remove...` kapalidir.
* Dosya acma yalniz makronun kendi calisma dizininde.
Bu kisitlar operator hatalarina ve kaba kotuye kullanima karsi savunmadir;
GRCON'da makro calistirma yetkisi `dron_komut` ile ayni izne baglidir.

## MAKRO ORTAMI (kullanicinin gordugu isimler)

    mav       pymavlink mavutil baglantisi (secili dron; udpout:127.0.0.1:port)
    mavutil   pymavlink.mavutil modulu
    mavlink   MAVLink lehcesi (mav.mav ile ayni sabitler: MAV_CMD_*, MAV_MODE_*)
    dron      Secili dronun kolay arayuzu (DronFasadi)
    dronlar   {sysid: DronFasadi} -- bagli tum dronlar (tembel acilir)
    dron_bul(sysid)   dronlar icinden facade dondurur
    bekle(sn)         time.sleep
    yaz(*metin)       ciktiya yaz (konsolda gorunur)
    bildir(metin)     arayuzde uyari balonu olarak goster
    durdur()          makroyu bitir
    time, math, json  standart moduller
    dron.param_get(ad) / dron.param_set(ad, deger)  otopilot parametreleri (2.4.246)
"""
import builtins
import io
import json
import math
import os
import sys
import threading
import time

_DIZIN = os.environ.get("GOKTUNGU_MAKRO_DIZIN") or os.getcwd()
_SYSID = int(os.environ.get("GOKTUNGU_MAKRO_SYSID") or 0)
_PORT = int(os.environ.get("GOKTUNGU_MAKRO_PORT") or 0)
try:
    _PORTLAR = {int(k): int(v) for k, v in json.loads(os.environ.get("GOKTUNGU_MAKRO_PORTLAR") or "{}").items()}
except Exception:
    _PORTLAR = {}
_SURE = int(os.environ.get("GOKTUNGU_MAKRO_SURE") or 0)
_PYMAV_YOL = os.environ.get("GOKTUNGU_MAKRO_PYMAVLINK_YOL") or ""
if _PYMAV_YOL and os.path.isdir(_PYMAV_YOL) and _PYMAV_YOL not in sys.path:
    sys.path.append(_PYMAV_YOL)


def _yaz(*parcalar, sev=None):
    metin = " ".join(str(p) for p in parcalar)
    if sev:
        metin = "[%s] %s" % (sev, metin)
    sys.stdout.write(metin + "\n")
    sys.stdout.flush()


# ----------------------------------------------------------------------
# SANDBOX
# ----------------------------------------------------------------------
def _sinirlar():
    try:
        import resource
    except ImportError:
        return
    def _koy(ad, deger):
        r = getattr(resource, ad, None)
        if r is None:
            return
        try:
            yumusak, sert = resource.getrlimit(r)
            yeni = deger if sert == resource.RLIM_INFINITY else min(deger, sert)
            resource.setrlimit(r, (yeni, yeni if sert == resource.RLIM_INFINITY else sert))
        except Exception:
            pass
    _koy("RLIMIT_AS", 1024 * 1024 * 1024)
    _koy("RLIMIT_CPU", max(60, (_SURE or 3600) + 60))
    _koy("RLIMIT_FSIZE", 64 * 1024 * 1024)
    _koy("RLIMIT_NOFILE", 256)


_YASAK_MODULLER = {
    "subprocess", "ctypes", "multiprocessing", "shutil", "pty", "code", "pdb",
    "webbrowser", "http.server", "socketserver", "xmlrpc", "ftplib", "smtplib",
    "telnetlib", "paramiko", "importlib", "sqlite3", "psycopg2", "goktungu",
    "asyncio.subprocess", "_posixsubprocess", "concurrent.futures.process",
}


class _YasakBulucu:
    def find_spec(self, ad, yol=None, hedef=None):
        kok = ad.split(".")[0]
        if ad in _YASAK_MODULLER or kok in _YASAK_MODULLER:
            raise ImportError("Makroda '%s' modulu kullanilamaz (guvenlik kisiti)" % ad)
        return None


def _yol_izinli(yol):
    try:
        p = os.path.abspath(str(yol))
    except Exception:
        return False
    return p.startswith(os.path.abspath(_DIZIN) + os.sep) or p == os.path.abspath(_DIZIN)


_gercek_open = builtins.open
_gercek_os_open = os.open


def _kisitli_open(dosya, mod="r", *a, **k):
    if isinstance(dosya, int):
        return _gercek_open(dosya, mod, *a, **k)
    if not _yol_izinli(dosya):
        raise PermissionError("Makro yalniz kendi calisma dizininde dosya acabilir: %s" % dosya)
    return _gercek_open(dosya, mod, *a, **k)


def _kisitli_os_open(yol, *a, **k):
    if not _yol_izinli(yol):
        raise PermissionError("Makro yalniz kendi calisma dizininde dosya acabilir: %s" % yol)
    return _gercek_os_open(yol, *a, **k)


def _kapali(*a, **k):
    raise PermissionError("Bu islem makroda kullanilamaz (guvenlik kisiti)")


def _soket_kisitla():
    import socket
    izinli = ("127.0.0.1", "localhost", "::1")

    def _adres_izinli(adres):
        try:
            host = adres[0] if isinstance(adres, (tuple, list)) else adres
        except Exception:
            return False
        return str(host) in izinli

    class KisitliSoket(socket.socket):
        def connect(self, adres):
            if not _adres_izinli(adres):
                raise PermissionError("Makro yalniz 127.0.0.1'e baglanabilir")
            return super().connect(adres)

        def connect_ex(self, adres):
            if not _adres_izinli(adres):
                raise PermissionError("Makro yalniz 127.0.0.1'e baglanabilir")
            return super().connect_ex(adres)

        def sendto(self, veri, *a):
            adres = a[-1] if a else None
            if adres is not None and not _adres_izinli(adres):
                raise PermissionError("Makro yalniz 127.0.0.1'e gonderebilir")
            return super().sendto(veri, *a)

        def bind(self, adres):
            if not _adres_izinli(adres) and str(adres[0]) not in ("", "0.0.0.0"):
                raise PermissionError("Makro yalniz 127.0.0.1'e bind edebilir")
            if str(adres[0]) in ("", "0.0.0.0"):
                adres = ("127.0.0.1", adres[1])
            return super().bind(adres)

    socket.socket = KisitliSoket
    socket.create_connection = _kapali


def _sandbox_kur():
    _sinirlar()
    sys.meta_path.insert(0, _YasakBulucu())
    for ad in sys.modules:
        pass
    for ad in ("system", "popen", "execv", "execve", "execvp", "execvpe", "execl", "execle",
               "execlp", "execlpe", "spawnl", "spawnle", "spawnv", "spawnve", "fork", "forkpty",
               "kill", "killpg", "remove", "unlink", "rmdir", "removedirs", "rename", "renames",
               "replace", "chmod", "chown", "symlink", "link", "truncate",
               "startfile", "posix_spawn", "posix_spawnp"):
        if hasattr(os, ad):
            setattr(os, ad, _kapali)
    os.open = _kisitli_os_open
    builtins.open = _kisitli_open
    io.open = _kisitli_open
    _soket_kisitla()


# ----------------------------------------------------------------------
# DRON FASADI
# ----------------------------------------------------------------------
class DronFasadi:
    """Secili dronun kolay arayuzu; ham erisim icin `.mav`."""

    def __init__(self, sysid, port, mavutil, isim=""):
        self.sysid = int(sysid)
        self.port = int(port)
        self.isim = isim or ("Dron %d" % self.sysid)
        self._mavutil = mavutil
        self.mav = mavutil.mavlink_connection("udpout:127.0.0.1:%d" % self.port,
                                              source_system=250, source_component=190)
        self._t = {"lat": None, "lon": None, "irtifa": None, "irtifa_msl": None, "hiz": None,
                   "yon": None, "batarya": None, "batarya_v": None, "mod": None, "armed": None,
                   "gps_fix": None, "uydu": None, "roll": None, "pitch": None, "son_ts": 0.0}
        self._kilit = threading.Lock()
        self._paramlar = {}      # 2.4.246: PARAM_VALUE -> {AD: (deger, tip, ts)}
        self._dur = False
        self._kalp_ts = 0.0
        threading.Thread(target=self._oku, daemon=True).start()
        threading.Thread(target=self._kalp, daemon=True).start()

    # --- arka plan ------------------------------------------------------
    def _kalp(self):
        while not self._dur:
            try:
                self.mav.mav.heartbeat_send(6, 8, 0, 0, 0)  # GCS, invalid autopilot
            except Exception:
                pass
            time.sleep(1.0)

    def _oku(self):
        while not self._dur:
            try:
                m = self.mav.recv_match(blocking=True, timeout=1.0)
            except Exception:
                time.sleep(0.2)
                continue
            if m is None:
                continue
            t = m.get_type()
            try:
                src = m.get_srcSystem()
            except Exception:
                src = self.sysid
            if src != self.sysid:
                continue
            with self._kilit:
                self._t["son_ts"] = time.time()
                if t == "HEARTBEAT":
                    self._kalp_ts = time.time()
                    self._t["armed"] = bool(m.base_mode & 128)
                    try:
                        self._t["mod"] = self.mav.mode_mapping_inv().get(m.custom_mode) if hasattr(self.mav, "mode_mapping_inv") else None
                    except Exception:
                        pass
                    if self._t["mod"] is None:
                        try:
                            eslem = self.mav.mode_mapping() or {}
                            self._t["mod"] = next((k for k, v in eslem.items() if v == m.custom_mode), None)
                        except Exception:
                            pass
                elif t == "GLOBAL_POSITION_INT":
                    self._t["lat"] = m.lat / 1e7
                    self._t["lon"] = m.lon / 1e7
                    self._t["irtifa"] = m.relative_alt / 1000.0
                    self._t["irtifa_msl"] = m.alt / 1000.0
                    self._t["yon"] = m.hdg / 100.0 if m.hdg != 65535 else None
                elif t == "VFR_HUD":
                    self._t["hiz"] = m.groundspeed
                elif t == "SYS_STATUS":
                    self._t["batarya_v"] = m.voltage_battery / 1000.0
                    self._t["batarya"] = m.battery_remaining if m.battery_remaining >= 0 else None
                elif t == "GPS_RAW_INT":
                    self._t["gps_fix"] = m.fix_type
                    self._t["uydu"] = m.satellites_visible
                elif t == "ATTITUDE":
                    self._t["roll"] = math.degrees(m.roll)
                    self._t["pitch"] = math.degrees(m.pitch)
                elif t == "PARAM_VALUE":
                    # 2.4.246: param_get/param_set bu sozlukten bekler (arka
                    # plan okuyucu mesajlari tukettigi icin recv_match ile
                    # beklemek yarisirdi).
                    try:
                        pid = m.param_id
                        if isinstance(pid, bytes):
                            pid = pid.decode("ascii", "ignore")
                        pid = str(pid).rstrip("\x00").upper()
                        self._paramlar[pid] = (float(m.param_value), int(m.param_type), time.time())
                    except Exception:
                        pass

    # --- durum ------------------------------------------------------
    def _al(self, ad):
        with self._kilit:
            return self._t.get(ad)

    lat = property(lambda s: s._al("lat"))
    lon = property(lambda s: s._al("lon"))
    irtifa = property(lambda s: s._al("irtifa"))
    irtifa_msl = property(lambda s: s._al("irtifa_msl"))
    hiz = property(lambda s: s._al("hiz"))
    yon = property(lambda s: s._al("yon"))
    batarya = property(lambda s: s._al("batarya"))
    batarya_v = property(lambda s: s._al("batarya_v"))
    mod = property(lambda s: s._al("mod"))
    armed = property(lambda s: s._al("armed"))
    gps_fix = property(lambda s: s._al("gps_fix"))
    uydu = property(lambda s: s._al("uydu"))
    roll = property(lambda s: s._al("roll"))
    pitch = property(lambda s: s._al("pitch"))

    @property
    def konum(self):
        return (self.lat, self.lon)

    @property
    def bagli(self):
        return (time.time() - self._kalp_ts) < 5.0

    @property
    def konum_gecerli(self):
        """GPS/EKF konumu kullanilabilir mi? (0,0) veya fix<2 ise False.

        2.4.251: konumsuz aracta GUIDED/git/kalk, ArduPilot'ta
        'Location cannot be (0, 0, 0)' panigine yol acar (SITL'de olculdu);
        bu yuzden konum gerektiren islevler once bunu denetler.
        """
        lat, lon, fix = self.lat, self.lon, self.gps_fix
        if lat is None or lon is None:
            return False
        if abs(lat) < 1e-6 and abs(lon) < 1e-6:
            return False
        if fix is not None and fix < 2:
            return False
        return True

    def bekle_konum(self, zaman_asimi=30.0):
        """Gecerli konum gelene kadar bekler."""
        bitis = time.time() + zaman_asimi
        while time.time() < bitis:
            if self.konum_gecerli:
                return True
            time.sleep(0.25)
        return False

    KONUM_GEREKTIREN_MODLAR = {"GUIDED", "AUTO", "RTL", "LOITER", "CIRCLE", "SMART_RTL", "FOLLOW",
                               "QLOITER", "QRTL", "QLAND", "CRUISE", "TAKEOFF", "POSHOLD", "BRAKE",
                               "AUTOTUNE", "THERMAL", "AVOID_ADSB", "GUIDED_NOGPS"}

    def _konum_denetle(self, islem, zorla=False):
        if zorla or self.konum_gecerli:
            return
        raise RuntimeError("%s icin gecerli konum yok (GPS kilidi/EKF hazir degil; lat=%s lon=%s fix=%s). "
                           "dron.bekle_konum() ile bekleyin; zorla=True ile atlanabilir ama otopilot cokebilir."
                           % (islem, self.lat, self.lon, self.gps_fix))

    @property
    def ucusta(self):
        irt = self.irtifa
        return bool(self.armed) and irt is not None and irt > 1.0

    def durum(self):
        with self._kilit:
            return dict(self._t)

    def bekle_baglanti(self, zaman_asimi=15.0):
        bitis = time.time() + zaman_asimi
        while time.time() < bitis:
            if self.bagli:
                return True
            time.sleep(0.2)
        return False

    # --- komutlar -----------------------------------------------------
    def komut(self, komut_id, p1=0, p2=0, p3=0, p4=0, p5=0, p6=0, p7=0, onay_bekle=True, zaman_asimi=5.0):
        self.mav.mav.command_long_send(self.sysid, 1, int(komut_id), 0,
                                       float(p1), float(p2), float(p3), float(p4),
                                       float(p5), float(p6), float(p7))
        if not onay_bekle:
            return None
        bitis = time.time() + zaman_asimi
        while time.time() < bitis:
            m = self.mav.recv_match(type="COMMAND_ACK", blocking=True, timeout=0.5)
            if m is not None and m.command == int(komut_id):
                return m.result
        return None

    def mod_ayarla(self, ad, bekle=True, zaman_asimi=5.0, zorla=False):
        eslem = self.mav.mode_mapping() or {}
        ad_u = str(ad).upper()
        if ad_u in self.KONUM_GEREKTIREN_MODLAR:
            self._konum_denetle("mod_ayarla('%s')" % ad_u, zorla)
        if ad_u not in eslem:
            raise ValueError("Bilinmeyen mod '%s'; secenekler: %s" % (ad, ", ".join(sorted(eslem))))
        self.mav.set_mode(eslem[ad_u])
        if not bekle:
            return True
        bitis = time.time() + zaman_asimi
        while time.time() < bitis:
            if (self.mod or "").upper() == ad_u:
                return True
            time.sleep(0.2)
        return False

    def arm(self, bekle=True, zorla=False, zaman_asimi=10.0):
        if not self.konum_gecerli:
            _yaz("arm: gecerli konum yok (lat=%s lon=%s fix=%s); konumsuz arm/ucus otopilotu cokertebilir"
                 % (self.lat, self.lon, self.gps_fix), sev="UYARI")
        MAV_CMD = 400
        self.komut(MAV_CMD, 1, 21196 if zorla else 0, onay_bekle=False)
        if not bekle:
            return True
        bitis = time.time() + zaman_asimi
        while time.time() < bitis:
            if self.armed:
                return True
            time.sleep(0.2)
        return False

    def disarm(self, zorla=False):
        return self.komut(400, 0, 21196 if zorla else 0)

    def kalk(self, irtifa=10.0, bekle=True, zaman_asimi=60.0, zorla=False):
        """GUIDED moda gecer, arm eder ve verilen irtifaya kalkar."""
        self._konum_denetle("kalk", zorla)
        if not self.mod_ayarla("GUIDED"):
            raise RuntimeError("GUIDED moda gecilemedi")
        if not self.armed and not self.arm():
            raise RuntimeError("Arm edilemedi (prearm denetimlerini kontrol edin)")
        self.komut(22, 0, 0, 0, 0, 0, 0, float(irtifa), onay_bekle=False)   # MAV_CMD_NAV_TAKEOFF
        if not bekle:
            return True
        bitis = time.time() + zaman_asimi
        while time.time() < bitis:
            irt = self.irtifa
            if irt is not None and irt >= float(irtifa) * 0.95:
                return True
            time.sleep(0.5)
        return False

    def git(self, lat, lon, irtifa=None, bekle=False, tol_m=3.0, zaman_asimi=300.0, zorla=False):
        """GUIDED hedef (goreli irtifa). bekle=True ise varisa kadar bekler."""
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            raise ValueError("git: lat/lon sayisal olmali")
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0) or (abs(lat) < 1e-6 and abs(lon) < 1e-6):
            raise ValueError("git: gecersiz hedef konum (%s, %s)" % (lat, lon))
        self._konum_denetle("git", zorla)
        if irtifa is None:
            irtifa = self.irtifa or 10.0
        MASKE = 0b0000111111111000   # yalniz konum
        self.mav.mav.set_position_target_global_int_send(
            0, self.sysid, 1, 6,   # MAV_FRAME_GLOBAL_RELATIVE_ALT_INT
            MASKE, int(float(lat) * 1e7), int(float(lon) * 1e7), float(irtifa),
            0, 0, 0, 0, 0, 0, 0, 0)
        if bekle:
            return self.bekle_varis(lat, lon, tol_m=tol_m, zaman_asimi=zaman_asimi)
        return True

    def eve_don(self):
        return self.mod_ayarla("RTL")

    def in_(self):
        """LAND modu (kullanim: dron.inis())."""
        return self.mod_ayarla("LAND")

    def hiz_ayarla(self, m_s):
        return self.komut(178, 1, float(m_s), -1, 0)   # MAV_CMD_DO_CHANGE_SPEED

    def mesafe(self, lat, lon):
        if self.lat is None or self.lon is None:
            return None
        R = 6371000.0
        p1, p2 = math.radians(self.lat), math.radians(float(lat))
        dl = math.radians(float(lon) - self.lon)
        a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * R * math.asin(math.sqrt(a))

    def bekle_varis(self, lat, lon, tol_m=3.0, zaman_asimi=300.0):
        bitis = time.time() + zaman_asimi
        while time.time() < bitis:
            d = self.mesafe(lat, lon)
            if d is not None and d <= tol_m:
                return True
            time.sleep(0.5)
        return False

    def bekle_irtifa(self, irtifa, tol_m=1.0, zaman_asimi=120.0):
        bitis = time.time() + zaman_asimi
        while time.time() < bitis:
            irt = self.irtifa
            if irt is not None and abs(irt - float(irtifa)) <= tol_m:
                return True
            time.sleep(0.5)
        return False

    # --- parametreler (2.4.246, kullanici: "makroya param_set koy") -----
    def _param_bekle(self, ad, sonra_ts, zaman_asimi):
        bitis = time.time() + zaman_asimi
        while time.time() < bitis:
            with self._kilit:
                v = self._paramlar.get(ad)
            if v is not None and v[2] >= sonra_ts:
                return v
            time.sleep(0.05)
        return None

    def param_get(self, ad, zaman_asimi=3.0, deneme=3):
        """Parametre okur (PARAM_REQUEST_READ). Deger (float) veya None."""
        ad = str(ad).strip().upper()
        for _ in range(max(1, int(deneme))):
            t0 = time.time()
            self.mav.mav.param_request_read_send(self.sysid, 1, ad.encode("ascii", "ignore"), -1)
            v = self._param_bekle(ad, t0, zaman_asimi)
            if v is not None:
                return v[0]
        return None

    def param_set(self, ad, deger, zaman_asimi=3.0, deneme=3, dogrula=True):
        """Parametre yazar (PARAM_SET) ve PARAM_VALUE ile dogrular.

        Tip, daha once okunmus PARAM_VALUE'dan alinir (yoksa REAL32;
        ArduPilot tam sayi parametreleri REAL32 ile de kabul eder).
        Doner: True (dogrulandi) / False.
        """
        ad = str(ad).strip().upper()
        deger = float(deger)
        with self._kilit:
            onceki = self._paramlar.get(ad)
        tip = onceki[1] if onceki else 9   # 9 = MAV_PARAM_TYPE_REAL32
        for _ in range(max(1, int(deneme))):
            t0 = time.time()
            self.mav.mav.param_set_send(self.sysid, 1, ad.encode("ascii", "ignore"), deger, int(tip))
            if not dogrula:
                return True
            v = self._param_bekle(ad, t0, zaman_asimi)
            if v is not None and abs(v[0] - deger) <= max(1e-6, abs(deger) * 1e-6):
                return True
        return False

    param_oku = param_get
    param_ayarla = param_set

    def kapat(self):
        self._dur = True
        try:
            self.mav.close()
        except Exception:
            pass


DronFasadi.inis = DronFasadi.in_
setattr(DronFasadi, "in", DronFasadi.in_)   # getattr(dron, 'in') ile erisim


class _Dronlar(dict):
    """Tembel: dronlar[sysid] ilk erisimde baglanti acar."""

    def __init__(self, mavutil):
        super().__init__()
        self._mavutil = mavutil

    def __missing__(self, sysid):
        sysid = int(sysid)
        port = _PORTLAR.get(sysid) or (9000 + sysid)
        d = DronFasadi(sysid, port, self._mavutil)
        self[sysid] = d
        return d

    def sysidler(self):
        return sorted(_PORTLAR)


# ----------------------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        _yaz("makro dosyasi verilmedi", sev="HATA")
        return 2
    dosya = sys.argv[1]
    try:
        kod = _gercek_open(dosya, "r", encoding="utf-8").read()
    except OSError as e:
        _yaz("makro dosyasi okunamadi: %s" % e, sev="HATA")
        return 2
    # pymavlink SANDBOX'TAN ONCE yuklenir: ice aktarma sirasinda dosya
    # sistemine ve ortama dokunur; kisitlar kullanici koduna uygulanir.
    try:
        from pymavlink import mavutil
        from pymavlink.dialects.v20 import ardupilotmega as mavlink
    except Exception as e:
        _yaz("pymavlink yuklenemedi: %s" % e, sev="HATA")
        return 3
    _sandbox_kur()
    dronlar = _Dronlar(mavutil)
    dron = None
    mav = None
    if _SYSID and _PORT:
        _PORTLAR.setdefault(_SYSID, _PORT)
        dron = dronlar[_SYSID]
        mav = dron.mav
        if not dron.bekle_baglanti(10.0):
            _yaz("dron %d'den 10 sn icinde heartbeat gelmedi (baglanti yok olabilir)" % _SYSID, sev="UYARI")
    else:
        _yaz("secili dron yok: 'dron' ve 'mav' tanimsiz; dronlar[sysid] ile erisin", sev="UYARI")

    class _Durdur(SystemExit):
        pass

    def bildir(metin):
        _yaz(str(metin), sev="BILDIR")

    def durdur():
        raise _Durdur(0)

    ortam = {
        "__name__": "__makro__", "__builtins__": builtins,
        "mav": mav, "mavutil": mavutil, "mavlink": mavlink,
        "dron": dron, "dronlar": dronlar, "dron_bul": lambda s: dronlar[int(s)],
        "bekle": time.sleep, "yaz": _yaz, "print": _yaz, "bildir": bildir, "durdur": durdur,
        "time": time, "math": math, "json": json, "sysid": _SYSID,
    }
    kod_obj = compile(kod, os.path.basename(dosya), "exec")
    cikis = 0
    try:
        exec(kod_obj, ortam)
    except SystemExit as e:
        cikis = int(e.code or 0) if isinstance(e.code, int) else 0
    except KeyboardInterrupt:
        cikis = 130
    except Exception:
        import traceback
        for satir in traceback.format_exc().splitlines():
            _yaz(satir)
        cikis = 1
    finally:
        for d in list(dronlar.values()):
            try:
                d.kapat()
            except Exception:
                pass
    return cikis


if __name__ == "__main__":
    sys.exit(main())
