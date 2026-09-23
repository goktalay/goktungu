# -*- coding: utf-8 -*-
"""GÖKTUNGU KÖPRÜ — DJI OSDK ADAPTÖR KATMANI (saf Python).

Bu modül, Merkez tarafındaki `goktungu/osdk_adaptor.py`'nin KÖPRÜ
ÇEKİRDEĞİNE taşınmış ve sadeleştirilmiş halidir. Amaç: DJI Onboard SDK
(OSDK) verisini GDP (satır-ayrılmış NDJSON) olarak yerel Merkez / role
kanalına köprülemek.

## KATMANLAR

  * `GdpIstemci`  — yerel DJI GDP dinleyicisine (DjiKopruYoneticisi /
    role kanalı ucuna) bağlanan, satır-JSON konuşan, otomatik yeniden
    bağlanan TCP istemcisi. Android DJI köprüsüyle AYNI protokolü konuşur;
    Merkez için ikisi ayırt edilemez.
  * `OsdkKanal`   — donanım tarafındaki native C++ yardımcı süreçle
    (`goktungu_osdk_kopru`) konuşan kanal. Yardımcı, OSDK Telemetry
    aboneliklerini ve FlightController çağrılarını JSON'a çevirip bir
    Unix domain soketi (veya `host:port`) üzerinden sunar.
  * `SimKanal`    — OSDK donanımı olmadan uçtan uca akış doğrulaması için
    basit benzetim kanalı (donanımsız). Native yardımcı gelmeden servis
    çalışabilsin diye vardır.
  * `OsdkAdaptor` — bir kanalı (OsdkKanal/SimKanal) GDP'ye köprüleyen ana
    döngü. Servis bunu ARKA PLAN İŞ PARÇACIĞINDA çalıştırır.
  * `OsdkYardimci`— native `goktungu_osdk_kopru` yardımcısını ALT SÜREÇ
    olarak başlatmayı DENEYEN başlatıcı. Bu ortamda native ikili henüz
    YOKTUR; `kullanilabilir()` False döner ve servis SimKanal'a ya da
    "yardımcı bekleniyor" durumuna düşer (çökme YOK).

## NEDEN `print` YOK

Merkez sürümü `print` kullanıyordu (bağımsız CLI). Köprüde her satır
servis konsoluna ait olmalı; bu yüzden tüm günlük çağrıları enjekte
edilen `yaz(mesaj, seviye)` geri çağrısına gider (servis_temel.Servis.yaz
ile aynı imza).

## NATIVE ENTEGRASYON NOKTASI

`OsdkYardimci.baslat()` native `goktungu_osdk_kopru` ikilisini başlatır,
uygulama kimliğini (app id/key/lisans) ORTAM DEĞİŞKENİYLE geçirir
(süreç argümanında görünmez) ve yardımcının açtığı sokete `OsdkKanal`
bağlanır. İkili sağlandığında burada başka değişiklik gerekmez.
"""
from __future__ import annotations

import contextlib
import json
import math
import os
import shutil
import socket
import subprocess
import threading
import time
from typing import Any, Callable, Dict, Optional

# Yerel DJI GDP ucu (Android köprüsü / OSDK adaptörü ile aynı port).
VARSAYILAN_GDP_ADRES = "127.0.0.1"
VARSAYILAN_GDP_PORT = 8790
# Native yardımcının varsayılan soketi (UDS yolu veya "host:port").
VARSAYILAN_OSDK_SOKET = "/tmp/goktungu_osdk.sock"
# Native yardımcı ikilisinin varsayılan adı (PATH'te aranır).
YARDIMCI_ADI = "goktungu_osdk_kopru"


def _sessiz_yaz(_m: str, _s: str = "bilgi") -> None:
    """Varsayılan (sessiz) günlükleyici."""


class GdpIstemci:
    """Yerel DJI GDP dinleyicisine bağlanan GDP TCP istemcisi.

    Satır-ayrılmış JSON, otomatik yeniden bağlanma. Sunucu tarafı komut
    gönderirse `komut_isleyici(id, ad, args)` çağrılır.
    """

    def __init__(self, adres: str, port: int,
                 komut_isleyici: Callable[[Any, str, dict], None],
                 merhaba_uret: Callable[[], dict],
                 yaz: Callable[[str, str], None] = _sessiz_yaz):
        self.adres = adres
        self.port = int(port)
        self.komut_isleyici = komut_isleyici
        self.merhaba_uret = merhaba_uret
        self._yaz = yaz
        self.soket: Optional[socket.socket] = None
        self.bagli = False
        self._durdur = threading.Event()
        self._yaz_kilit = threading.Lock()
        self._thread: Optional[threading.Thread] = None

    def baslat(self) -> None:
        self._durdur.clear()
        self._thread = threading.Thread(target=self._dongu, daemon=True,
                                        name="dji-gdp")
        self._thread.start()

    def durdur(self) -> None:
        self._durdur.set()
        if self.soket:
            with contextlib.suppress(OSError):
                self.soket.close()
        self.bagli = False

    def _dongu(self) -> None:
        while not self._durdur.is_set():
            try:
                s = socket.create_connection((self.adres, self.port),
                                             timeout=5.0)
                s.settimeout(None)
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.soket = s
                self.bagli = True
                self._yaz("GDP bağlandı: %s:%d" % (self.adres, self.port),
                          "basari")

                m = dict(self.merhaba_uret())
                m["tip"] = "merhaba"
                self.gonder(m)

                tampon = b""
                while not self._durdur.is_set():
                    veri = s.recv(4096)
                    if not veri:
                        break
                    tampon += veri
                    while b"\n" in tampon:
                        satir, tampon = tampon.split(b"\n", 1)
                        if not satir.strip():
                            continue
                        try:
                            mesaj = json.loads(satir.decode("utf-8"))
                        except (ValueError, UnicodeDecodeError):
                            continue
                        if mesaj.get("tip") == "komut":
                            self.komut_isleyici(
                                mesaj.get("id"),
                                str(mesaj.get("ad") or ""),
                                mesaj.get("args") or {})
            except OSError as e:
                self._yaz("GDP bağlantı hatası: %s" % e, "uyari")
            finally:
                self.bagli = False
                if self.soket:
                    with contextlib.suppress(OSError):
                        self.soket.close()
                    self.soket = None
            if not self._durdur.is_set():
                # 3 sn: yeniden bağlanma sıklığı; sunucu geçici kapalıysa
                # konsolu boğmadan bekler.
                self._durdur.wait(3.0)

    def gonder(self, mesaj: dict) -> bool:
        s = self.soket
        if s is None:
            return False
        try:
            veri = (json.dumps(mesaj, ensure_ascii=False) + "\n").encode("utf-8")
            with self._yaz_kilit:
                s.sendall(veri)
            return True
        except OSError:
            return False

    def yanit(self, komut_id: Any, tamam: bool, mesaj: str = "") -> None:
        self.gonder({"tip": "yanit", "komut_id": komut_id,
                     "sonuc": "tamam" if tamam else "hata", "mesaj": mesaj})


class OsdkKanal:
    """Native OSDK C++ yardımcısıyla (goktungu_osdk_kopru) konuşan kanal.

    Yardımcı mesajları (satır JSON):
      yardımcı -> python: {"t":"telem", ...alanlar}
                          {"t":"ack","id":N,"ok":true/false,"msg":""}
                          {"t":"info","sn":"...","fw":"...","model":"..."}
      python -> yardımcı: {"t":"cmd","id":N,"ad":"...","args":{}}
    """

    def __init__(self, soket_yolu: str,
                 yaz: Callable[[str, str], None] = _sessiz_yaz):
        self.soket_yolu = soket_yolu
        self._yaz = yaz
        self.soket: Optional[socket.socket] = None
        self.bagli = False
        self.son_telem: Dict[str, Any] = {}
        self.bilgi: Dict[str, Any] = {}
        self._ackler: Dict[Any, dict] = {}
        self._durdur = threading.Event()
        self._yaz_kilit = threading.Lock()

    def baslat(self) -> None:
        self._durdur.clear()
        threading.Thread(target=self._dongu, daemon=True,
                         name="dji-osdk-kanal").start()

    def durdur(self) -> None:
        self._durdur.set()
        if self.soket:
            with contextlib.suppress(OSError):
                self.soket.close()

    def _baglan(self) -> socket.socket:
        if ":" in self.soket_yolu and not self.soket_yolu.startswith("/"):
            host, port = self.soket_yolu.rsplit(":", 1)
            return socket.create_connection((host, int(port)), timeout=5.0)
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(self.soket_yolu)
        return s

    def _dongu(self) -> None:
        while not self._durdur.is_set():
            try:
                s = self._baglan()
                s.settimeout(None)
                self.soket = s
                self.bagli = True
                self._yaz("OSDK yardımcısına bağlandı: %s" % self.soket_yolu,
                          "basari")
                tampon = b""
                while not self._durdur.is_set():
                    veri = s.recv(4096)
                    if not veri:
                        break
                    tampon += veri
                    while b"\n" in tampon:
                        satir, tampon = tampon.split(b"\n", 1)
                        try:
                            m = json.loads(satir.decode("utf-8"))
                        except (ValueError, UnicodeDecodeError):
                            continue
                        t = m.get("t")
                        if t == "telem":
                            self.son_telem = m
                        elif t == "info":
                            self.bilgi = m
                        elif t == "ack":
                            self._ackler[m.get("id")] = m
            except OSError as e:
                self._yaz("OSDK yardımcı bağlantısı yok: %s" % e, "uyari")
            finally:
                self.bagli = False
                if self.soket:
                    with contextlib.suppress(OSError):
                        self.soket.close()
                    self.soket = None
            if not self._durdur.is_set():
                self._durdur.wait(3.0)

    def komut(self, kid: Any, ad: str, args: dict,
              zaman_asimi: float = 8.0):
        """Yardımcıya komut gönderir ve ack bekler (senkron)."""
        s = self.soket
        if s is None:
            return False, "OSDK yardımcısı bağlı değil"
        try:
            veri = (json.dumps({"t": "cmd", "id": kid, "ad": ad,
                                "args": args}, ensure_ascii=False) + "\n"
                    ).encode("utf-8")
            with self._yaz_kilit:
                s.sendall(veri)
        except OSError as e:
            return False, str(e)
        bitis = time.time() + zaman_asimi
        while time.time() < bitis:
            ack = self._ackler.pop(kid, None)
            if ack is not None:
                return bool(ack.get("ok")), str(ack.get("msg") or "")
            time.sleep(0.05)
        return False, "OSDK ack zaman aşımı"


class SimKanal:
    """OSDK yardımcısı olmadan test için basit benzetim kanalı.

    Ankara civarında bir çokpervaneli araç benzetimi: telemetri üretir,
    goto/takeoff/land/rtl komutlarına tepki verir. Gerçek OSDK donanımı
    olmadan uçtan uca GDP akışı ve entegrasyon doğrulaması içindir.
    """

    def __init__(self):
        self.bagli = True
        self.bilgi = {"sn": "OSDK-SIM-001", "model": "Matrice 300 RTK",
                      "fw": "OSDK 4.1.0-sim"}
        self.lat = 39.9350
        self.lon = 32.5980
        self.alt_rel = 0.0
        self.heading = 0.0
        self.armed = False
        self.ucusta = False
        self.mod = "GPS"
        self.hedef = None  # (lat, lon, alt)
        self.batarya = 100.0
        self._dur = threading.Event()

    def baslat(self) -> None:
        self._dur.clear()
        threading.Thread(target=self._fizik, daemon=True,
                         name="dji-sim-fizik").start()

    def durdur(self) -> None:
        self.bagli = False
        self._dur.set()

    @property
    def son_telem(self) -> Dict[str, Any]:
        return {
            "lat": self.lat, "lon": self.lon,
            "alt_msl": 800.0 + self.alt_rel, "alt_rel": self.alt_rel,
            "heading": self.heading, "hiz": 8.0 if self.hedef else 0.0,
            "vz": 0.0, "roll": 0.0, "pitch": 0.0,
            "batarya_pct": int(self.batarya), "batarya_v": 22.8,
            "gps_fix": 3, "uydu": 18, "mod": self.mod,
            "armed": self.armed, "ucusta": self.ucusta,
            "ev_lat": 39.9350, "ev_lon": 32.5980,
        }

    def _fizik(self) -> None:
        R = 6371000.0
        while not self._dur.is_set() and self.bagli:
            if self.ucusta:
                self.batarya = max(5.0, self.batarya - 0.01)
            if self.hedef:
                hlat, hlon, halt = self.hedef
                dlat = (hlat - self.lat) * math.pi / 180 * R
                dlon = ((hlon - self.lon) * math.pi / 180 * R *
                        math.cos(math.radians(self.lat)))
                mesafe = math.hypot(dlat, dlon)
                if mesafe < 2.0 and abs(halt - self.alt_rel) < 1.0:
                    if self.mod == "GO_HOME":
                        self.ucusta = False
                        self.armed = False
                        self.alt_rel = 0.0
                        self.mod = "GPS"
                    self.hedef = None
                else:
                    adim = min(8.0 * 0.2, mesafe)  # 8 m/s, 5 Hz
                    if mesafe > 0.1:
                        self.heading = math.degrees(
                            math.atan2(dlon, dlat)) % 360
                        self.lat += (dlat / mesafe * adim) / R * 180 / math.pi
                        self.lon += ((dlon / mesafe * adim) /
                                     (R * math.cos(math.radians(self.lat)))
                                     * 180 / math.pi)
                    fark = halt - self.alt_rel
                    self.alt_rel += max(-0.6, min(0.6, fark))
            self._dur.wait(0.2)

    def komut(self, kid: Any, ad: str, args: dict, zaman_asimi: float = 8.0):
        if ad == "takeoff":
            self.armed = True
            self.ucusta = True
            self.hedef = (self.lat, self.lon, float(args.get("irtifa", 10.0)))
            self.mod = "GPS"
            return True, ""
        if ad == "land":
            self.mod = "AUTO_LANDING"
            self.hedef = (self.lat, self.lon, 0.0)
            return True, ""
        if ad == "rtl":
            self.mod = "GO_HOME"
            self.hedef = (39.9350, 32.5980, self.alt_rel)
            return True, ""
        if ad == "goto":
            try:
                self.hedef = (float(args["lat"]), float(args["lon"]),
                              float(args.get("irtifa", self.alt_rel or 30)))
                self.mod = "VIRTUAL_STICK"
                return True, ""
            except (KeyError, TypeError, ValueError):
                return False, "geçersiz koordinat"
        if ad == "dur":
            self.hedef = None
            self.mod = "GPS"
            return True, ""
        if ad in ("hiz", "gimbal", "irtifa", "gorev_yukle", "gorev_baslat",
                  "gorev_durdur", "video_baslat", "video_durdur",
                  "disarm", "arm", "param_oku"):
            return True, ""
        return False, "sim: bilinmeyen komut %s" % ad


class OsdkAdaptor:
    """Bir kanalın (OSDK/Sim) verisini GDP'ye köprüleyen ana döngü.

    Merkez sürümündeki `calistir()` bloklayan bir döngüydü (CLI). Köprüde
    servis ALT SÜREÇ olduğundan döngü `baslat()` ile arka plan iş
    parçacığında koşar, `durdur()` ile durur.
    """

    PARAMLAR = {"OSDK_YUKSEKLIK_LIMIT": 120.0, "OSDK_RTL_YUKSEKLIK": 30.0}

    def __init__(self, gcs_adres: str, gcs_port: int, kanal,
                 video_url: str = "",
                 yaz: Callable[[str, str], None] = _sessiz_yaz):
        self.kanal = kanal
        self.video_url = video_url
        self._yaz = yaz
        self.gdp = GdpIstemci(gcs_adres, gcs_port, self._komut_isle,
                              self._merhaba, yaz=yaz)
        self._durdur = threading.Event()
        self._is: Optional[threading.Thread] = None
        self.telem_gonderilen = 0

    def _merhaba(self) -> dict:
        b = getattr(self.kanal, "bilgi", {}) or {}
        m = {"sdk": "osdk",
             "sn": b.get("sn", "OSDK-?"),
             "model": b.get("model", "DJI OSDK"),
             "fw": b.get("fw", "")}
        if self.video_url:
            m["video_url"] = self.video_url
        return m

    def _komut_isle(self, kid: Any, ad: str, args: dict) -> None:
        def _calistir():
            if ad == "param_oku":
                self.gdp.gonder({"tip": "param_liste",
                                 "parametreler": dict(self.PARAMLAR)})
                self.gdp.yanit(kid, True)
                return
            if ad == "param_yaz":
                p = str(args.get("ad") or "")
                if p in self.PARAMLAR:
                    try:
                        self.PARAMLAR[p] = float(args.get("deger"))
                        self.gdp.yanit(kid, True)
                    except (TypeError, ValueError):
                        self.gdp.yanit(kid, False, "geçersiz değer")
                else:
                    self.gdp.yanit(kid, False, "bilinmeyen param %s" % p)
                return
            tamam, mesaj = self.kanal.komut(kid, ad, args)
            self.gdp.yanit(kid, tamam, mesaj)
        threading.Thread(target=_calistir, daemon=True).start()

    def baslat(self, telem_periyot: float = 0.2) -> None:
        self._durdur.clear()
        self._is = threading.Thread(target=self._dongu, args=(telem_periyot,),
                                    daemon=True, name="dji-adaptor")
        self._is.start()

    def _dongu(self, telem_periyot: float) -> None:
        self.kanal.baslat()
        self.gdp.baslat()
        son_kalp = 0.0
        try:
            while not self._durdur.is_set():
                if self.gdp.bagli and getattr(self.kanal, "bagli", False):
                    t = dict(self.kanal.son_telem or {})
                    if t:
                        t.pop("t", None)
                        t["tip"] = "telemetri"
                        if self.gdp.gonder(t):
                            self.telem_gonderilen += 1
                elif self.gdp.bagli:
                    # Araç bağlı değilken soketi canlı tut (sunucu 30 sn
                    # veri gelmezse istemciyi düşürür): 5 sn'de bir kalp.
                    simdi = time.time()
                    if simdi - son_kalp >= 5.0:
                        son_kalp = simdi
                        self.gdp.gonder({"tip": "kalp", "urun": False})
                self._durdur.wait(telem_periyot)
        finally:
            self.gdp.durdur()
            self.kanal.durdur()

    def durdur(self) -> None:
        self._durdur.set()

    def durum(self) -> Dict[str, Any]:
        return {
            "gdp_bagli": bool(self.gdp.bagli),
            "kanal_bagli": bool(getattr(self.kanal, "bagli", False)),
            "telem_gonderilen": self.telem_gonderilen,
            "gcs_adres": self.gdp.adres,
            "gcs_port": self.gdp.port,
        }


class OsdkYardimci:
    """Native `goktungu_osdk_kopru` C++ yardımcısını ALT SÜREÇ başlatıcı.

    Bu ortamda native ikili YOKTUR; `kullanilabilir()` False döner. İkili
    sağlandığında `baslat()` onu çalıştırır, uygulama kimliğini ORTAM
    DEĞİŞKENİYLE geçirir (`ps` çıktısında görünmez) ve açtığı sokete
    `OsdkKanal` bağlanır.
    """

    BASLATMA_ZAMAN_ASIMI = 20.0

    def __init__(self, cfg: Dict[str, Any],
                 yaz: Callable[[str, str], None] = _sessiz_yaz):
        self._cfg = dict(cfg or {})
        self._yaz = yaz
        self._surec: Optional[subprocess.Popen] = None
        self.soket_yolu = str(self._cfg.get("osdk_soket")
                              or VARSAYILAN_OSDK_SOKET)

    @staticmethod
    def ikili_bul(cfg: Dict[str, Any]) -> Optional[str]:
        """Native yardımcı ikilisinin yolunu bulur (config/PATH/paket)."""
        cfg = cfg or {}
        aday = str(cfg.get("osdk_yardimci") or "").strip()
        if aday and os.path.isfile(aday) and os.access(aday, os.X_OK):
            return aday
        yol = shutil.which(YARDIMCI_ADI)
        if yol:
            return yol
        # Paketle birlikte gelen vendor dizini (ileride doldurulacak).
        vendor = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "osdk_vendor", YARDIMCI_ADI)
        if os.path.isfile(vendor) and os.access(vendor, os.X_OK):
            return vendor
        return None

    @classmethod
    def kullanilabilir(cls, cfg: Dict[str, Any]) -> bool:
        return cls.ikili_bul(cfg) is not None

    @staticmethod
    def eksik_gerekce(cfg: Dict[str, Any]) -> str:
        if OsdkYardimci.ikili_bul(cfg) is None:
            return ("OSDK native yardımcısı (%s) bulunamadı; config "
                    "'osdk_yardimci' yolu veya PATH gerekir" % YARDIMCI_ADI)
        return ""

    def baslat(self) -> str:
        """Yardımcıyı başlatır; hata metni ('' = başarı) döner."""
        ikili = self.ikili_bul(self._cfg)
        if ikili is None:
            return self.eksik_gerekce(self._cfg)
        # Uygulama kimliği ORTAM DEĞİŞKENİYLE geçirilir; argümanda ve
        # günlükte YER ALMAZ. İçerik burada OKUNMAZ/yazılmaz, yalnız
        # alt sürece aktarılır.
        env = dict(os.environ)
        for anahtar, cev in (("app_id", "GOKTUNGU_DJI_APP_ID"),
                             ("app_key", "GOKTUNGU_DJI_APP_KEY"),
                             ("lisans", "GOKTUNGU_DJI_LISANS")):
            deger = self._cfg.get(anahtar)
            if deger:
                env[cev] = str(deger)
        cmd = [ikili, "--soket", self.soket_yolu]
        gcs_adres = str(self._cfg.get("gcs_adres") or VARSAYILAN_GDP_ADRES)
        if self._cfg.get("osdk_ek_arg"):
            with contextlib.suppress(Exception):
                cmd += [str(x) for x in self._cfg["osdk_ek_arg"]]
        self._yaz("OSDK native yardımcısı başlatılıyor: %s (soket %s)"
                  % (os.path.basename(ikili), self.soket_yolu), "bilgi")
        try:
            self._surec = subprocess.Popen(
                cmd, env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except OSError as exc:
            return "OSDK yardımcısı başlatılamadı: %s" % exc
        threading.Thread(target=self._stderr_dongu, daemon=True,
                         name="dji-osdk-stderr").start()
        # UDS ise soketin belirmesini kısa süre bekle.
        son = time.time() + self.BASLATMA_ZAMAN_ASIMI
        uds = self.soket_yolu.startswith("/")
        while time.time() < son:
            if self._surec.poll() is not None:
                return ("OSDK yardımcısı çıktı (kod %s); günlüğe bakın"
                        % self._surec.returncode)
            if not uds or os.path.exists(self.soket_yolu):
                return ""
            time.sleep(0.25)
        # Zaman aşımı olsa da OsdkKanal yeniden bağlanmayı sürdürür.
        return ""

    def _stderr_dongu(self) -> None:
        p = self._surec
        if p is None or p.stderr is None:
            return
        for satir in p.stderr:
            try:
                m = satir.decode("utf-8", "replace").rstrip()
            except Exception:
                continue
            if m:
                self._yaz("[osdk] " + m[:300], "bilgi")

    def calisiyor(self) -> bool:
        return bool(self._surec and self._surec.poll() is None)

    def kapat(self) -> None:
        p = self._surec
        if p is None:
            return
        with contextlib.suppress(Exception):
            p.terminate()
        try:
            p.wait(timeout=3)
        except Exception:
            with contextlib.suppress(Exception):
                p.kill()
        self._surec = None
