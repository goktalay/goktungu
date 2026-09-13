# -*- coding: utf-8 -*-
"""OsdkAdaptor: DJI Onboard SDK (OSDK) Python entegrasyonu.

DJI Onboard SDK, dronun uzerindeki yardimci bilgisayardan (Manifold,
Raspberry Pi, Jetson vb.) UART uzerinden ucus kontrolcusuyle konusan
C++ kutuphanesidir. DJI, OSDK'yi 2022'de arsivleyip yerini Payload
SDK'ya (PSDK) birakmistir; ancak M600/M210/M100/A3/N3 filolarinda OSDK
hala sahada kullanilmaktadir.

Bu modul iki calisms bicimi sunar:

1. **vendor kutuphane kipi** (varsayilan): yardimci bilgisayarda calisan
   `osdk_vendor/goktungu_osdk_kopru` C++ yardimcisiyla (OSDK'ye baglanan
   kucuk bir kopru; UDS/TCP JSON arayuzu) konusur. Yardimci program
   OSDK'nin Telemetry/FlightController API'lerini GDP mesajlarina
   cevirir.

2. **dogrudan kip**: OSDK yardimcisi ayni makinede degilse, bu adaptorun
   kendisi GDP istemcisi olarak GCS'teki DjiKopruYoneticisi'ne TCP ile
   baglanir ve OSDK verisini iletir. Boylece MSDK Android koprusuyle
   ayni sunucu tarafi kod yolu kullanilir; GCS icin ikisi ayirt
   edilemez.

Kullanim (yardimci bilgisayarda):
    python3 -m goktungu.osdk_adaptor --gcs 192.168.1.100 --port 8790 \
        --osdk-soket /tmp/goktungu_osdk.sock
    # veya OSDK yardimcisi yoksa test/simulasyon kipi:
    python3 -m goktungu.osdk_adaptor --gcs 127.0.0.1 --port 8790 --sim
"""
import argparse
import json
import math
import socket
import threading
import time


class GdpIstemci:
    """GCS DjiKopruYoneticisi'ne baglanan GDP TCP istemcisi.

    Android uygulamasindaki GdpIstemcisi.kt ile ayni protokolu konusur:
    satir-ayrilmis JSON, otomatik yeniden baglanma.
    """

    def __init__(self, adres, port, komut_isleyici, merhaba_uret):
        self.adres = adres
        self.port = port
        self.komut_isleyici = komut_isleyici
        self.merhaba_uret = merhaba_uret
        self.soket = None
        self.bagli = False
        self._durdur = threading.Event()
        self._yaz_kilit = threading.Lock()
        self._thread = None

    def baslat(self):
        self._durdur.clear()
        self._thread = threading.Thread(target=self._dongu, daemon=True)
        self._thread.start()

    def durdur(self):
        self._durdur.set()
        if self.soket:
            try:
                self.soket.close()
            except OSError:
                pass
        self.bagli = False

    def _dongu(self):
        while not self._durdur.is_set():
            try:
                print(f"[GDP] Baglaniliyor: {self.adres}:{self.port}")
                s = socket.create_connection(
                    (self.adres, self.port), timeout=5.0)
                s.settimeout(None)
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.soket = s
                self.bagli = True
                print("[GDP] Baglandi")

                m = self.merhaba_uret()
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
                print(f"[GDP] Baglanti hatasi: {e}")
            finally:
                self.bagli = False
                if self.soket:
                    try:
                        self.soket.close()
                    except OSError:
                        pass
                    self.soket = None
            if not self._durdur.is_set():
                time.sleep(3.0)

    def gonder(self, mesaj):
        s = self.soket
        if s is None:
            return False
        try:
            veri = (json.dumps(mesaj, ensure_ascii=False) + "\n"
                    ).encode("utf-8")
            with self._yaz_kilit:
                s.sendall(veri)
            return True
        except OSError:
            return False

    def yanit(self, komut_id, tamam, mesaj=""):
        self.gonder({"tip": "yanit", "komut_id": komut_id,
                     "sonuc": "tamam" if tamam else "hata",
                     "mesaj": mesaj})


class OsdkKanal:
    """OSDK C++ yardimcisiyla (goktungu_osdk_kopru) konusan kanal.

    Yardimci, OSDK Telemetry aboneliklerini ve FlightController
    cagrilarini JSON'a cevirip bir Unix domain soket (veya TCP)
    uzerinden sunar. Bu sinif o sokete baglanir.

    Yardimci mesajlari (satir JSON):
      yardimci -> python: {"t":"telem", ...alanlar}
                          {"t":"ack","id":N,"ok":true/false,"msg":""}
                          {"t":"info","sn":"...","fw":"...","model":"..."}
      python -> yardimci: {"t":"cmd","id":N,"ad":"...","args":{}}
    """

    def __init__(self, soket_yolu):
        self.soket_yolu = soket_yolu
        self.soket = None
        self.bagli = False
        self.son_telem = {}
        self.bilgi = {}
        self._ackler = {}
        self._durdur = threading.Event()
        self._yaz_kilit = threading.Lock()

    def baslat(self):
        self._durdur.clear()
        threading.Thread(target=self._dongu, daemon=True).start()

    def durdur(self):
        self._durdur.set()
        if self.soket:
            try:
                self.soket.close()
            except OSError:
                pass

    def _baglan(self):
        if ":" in self.soket_yolu and not self.soket_yolu.startswith("/"):
            host, port = self.soket_yolu.rsplit(":", 1)
            return socket.create_connection((host, int(port)), timeout=5.0)
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(self.soket_yolu)
        return s

    def _dongu(self):
        while not self._durdur.is_set():
            try:
                s = self._baglan()
                s.settimeout(None)
                self.soket = s
                self.bagli = True
                print(f"[OSDK] Yardimciya baglandi: {self.soket_yolu}")
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
                print(f"[OSDK] Yardimci baglantisi yok: {e}")
            finally:
                self.bagli = False
                if self.soket:
                    try:
                        self.soket.close()
                    except OSError:
                        pass
                    self.soket = None
            if not self._durdur.is_set():
                time.sleep(3.0)

    def komut(self, kid, ad, args, zaman_asimi=8.0):
        """Yardimciya komut gonderir ve ack bekler (senkron)."""
        s = self.soket
        if s is None:
            return False, "OSDK yardimcisi bagli degil"
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
        return False, "OSDK ack zaman asimi"


class SimKanal:
    """OSDK yardimcisi olmadan test icin basit simulasyon kanali.

    Ankara civarinda sabit kanatli olmayan bir quadcopter benzetimi:
    telemetri uretir, goto/takeoff/land/rtl komutlarina tepki verir.
    Gercek OSDK donanimi olmadan ucus testleri ve GCS entegrasyon
    dogrulamasi icin kullanilir.
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
        threading.Thread(target=self._fizik, daemon=True).start()

    def baslat(self):
        pass

    def durdur(self):
        self.bagli = False

    @property
    def son_telem(self):
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

    def _fizik(self):
        R = 6371000.0
        while self.bagli:
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
            time.sleep(0.2)

    def komut(self, kid, ad, args, zaman_asimi=8.0):
        if ad == "takeoff":
            self.armed = True
            self.ucusta = True
            self.mod = "TAKE_OFF"
            self.hedef = (self.lat, self.lon,
                          float(args.get("irtifa", 10.0)))
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
                return False, "gecersiz koordinat"
        if ad == "dur":
            self.hedef = None
            self.mod = "GPS"
            return True, ""
        if ad in ("hiz", "gimbal", "irtifa", "gorev_yukle",
                  "gorev_baslat", "gorev_durdur", "video_baslat",
                  "video_durdur", "disarm", "arm"):
            return True, ""
        if ad == "param_oku":
            return True, ""
        return False, f"sim: bilinmeyen komut {ad}"


class OsdkAdaptor:
    """OSDK verisini GDP'ye kopruleyen ana adaptor."""

    PARAMLAR = {"OSDK_YUKSEKLIK_LIMIT": 120.0,
                "OSDK_RTL_YUKSEKLIK": 30.0}

    def __init__(self, gcs_adres, gcs_port, kanal, video_url=""):
        self.kanal = kanal
        self.video_url = video_url
        self.gdp = GdpIstemci(gcs_adres, gcs_port,
                              self._komut_isle, self._merhaba)
        self._durdur = threading.Event()

    def _merhaba(self):
        b = getattr(self.kanal, "bilgi", {}) or {}
        m = {"sdk": "osdk",
             "sn": b.get("sn", "OSDK-?"),
             "model": b.get("model", "DJI OSDK"),
             "fw": b.get("fw", "")}
        if self.video_url:
            m["video_url"] = self.video_url
        return m

    def _komut_isle(self, kid, ad, args):
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
                        self.gdp.yanit(kid, False, "gecersiz deger")
                else:
                    self.gdp.yanit(kid, False, f"bilinmeyen param {p}")
                return
            tamam, mesaj = self.kanal.komut(kid, ad, args)
            self.gdp.yanit(kid, tamam, mesaj)
        threading.Thread(target=_calistir, daemon=True).start()

    def calistir(self, telem_periyot=0.2):
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
                        self.gdp.gonder(t)
                elif self.gdp.bagli:
                    # Arac bagli degilken soketi canli tut (sunucu 30 sn
                    # veri gelmezse istemciyi dusurur): 5 sn'de bir kalp.
                    simdi = time.time()
                    if simdi - son_kalp >= 5.0:
                        son_kalp = simdi
                        self.gdp.gonder({"tip": "kalp", "urun": False})
                time.sleep(telem_periyot)
        except KeyboardInterrupt:
            pass
        finally:
            self.gdp.durdur()
            self.kanal.durdur()


def main():
    p = argparse.ArgumentParser(
        description="GOKTUNGU DJI Onboard SDK adaptoru")
    p.add_argument("--gcs", default="127.0.0.1",
                   help="GCS sunucu adresi (GDP dinleyicisi)")
    p.add_argument("--port", type=int, default=8790, help="GDP portu")
    p.add_argument("--osdk-soket", default="/tmp/goktungu_osdk.sock",
                   help="OSDK C++ yardimci soketi (UDS yolu veya host:port)")
    p.add_argument("--video-url", default="",
                   help="OSDK tarafinda yayinlanan MJPEG/RTSP video URL'si")
    p.add_argument("--sim", action="store_true",
                   help="OSDK donanimi olmadan simulasyon kipi")
    p.add_argument("--periyot", type=float, default=0.2,
                   help="Telemetri gonderim periyodu (sn)")
    a = p.parse_args()

    kanal = SimKanal() if a.sim else OsdkKanal(a.osdk_soket)
    adaptor = OsdkAdaptor(a.gcs, a.port, kanal, a.video_url)
    print(f"[OSDK-ADAPTOR] GCS={a.gcs}:{a.port} "
          f"kip={'SIM' if a.sim else 'OSDK'}")
    adaptor.calistir(a.periyot)


if __name__ == "__main__":
    main()
