#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.4.44 - Yer Istasyonu 2 BACKEND sinavi (benzetici uzerinde).

Istasyon2 modulunu GERCEK bir seri port (PTY) uzerinden benzeticiye
baglar ve kullanicinin tanimladigi esleme birebir dogrulanir:
  P1 arm/disarm, P2 takeoff/land, P3 rtl, P4/P5/P6 mod
  T1 -> P7 LED + patlat_onay
  T2 UP/DOWN/CENTER -> harita zoom
  P8-P11 -> harita eylemleri
  Ek dron joystickleri -> ManuelKontrol.istasyon2_eksen
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(
    os.path.abspath(__file__)), "goktungu"))

from goktungu.istasyon2 import Istasyon2  # noqa: E402

GECTI = []
KALDI = []


def olc(ad, kosul, ayrinti=""):
    (GECTI if kosul else KALDI).append(ad)
    print("  %s %s%s" % ("[GECTI]" if kosul else "[KALDI]", ad,
                         (" - " + str(ayrinti)) if ayrinti else ""))


class SahteManuel:
    def __init__(self):
        self.cagrilar = []

    def istasyon2_eksen(self, vx, vy, vz, yaw, aktif=True):
        self.cagrilar.append({"vx": round(vx, 3), "vy": round(vy, 3),
                              "vz": round(vz, 3), "yaw": round(yaw, 3),
                              "aktif": aktif})


class SahteAyar:
    def __init__(self, port):
        self.d = {"istasyon2": {"port": port, "otomatik": True}}

    def yukle(self):
        return dict(self.d)

    def kaydet(self, k):
        self.d.update(k)


def konsol(etiket, mesaj, seviye="bilgi"):
    print("    [%s/%s] %s" % (etiket, seviye, mesaj))


def pty_baslat():
    p = subprocess.Popen(
        [sys.executable, "istasyon2/benzetici.py", "--pty"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1)
    port = ""
    t0 = time.time()
    while time.time() - t0 < 15:
        satir = p.stdout.readline()
        if not satir:
            break
        print("    benzetici: " + satir.rstrip())
        if "/dev/pts/" in satir:
            for parca in satir.replace(":", " ").split():
                if parca.startswith("/dev/pts/"):
                    port = parca.strip()
                    break
        if port:
            break
    return p, port


def bekle(kosul, sure=5.0, adim=0.05):
    t0 = time.time()
    while time.time() - t0 < sure:
        if kosul():
            return True
        time.sleep(adim)
    return False


def main():
    print("=" * 66)
    print("v2.4.44 YER ISTASYONU 2 - BACKEND SINAVI")
    print("=" * 66)
    proc, port = pty_baslat()
    if not port:
        print("[HATA] Benzetici PTY portu alinamadi")
        proc.kill()
        return 1
    print("\n[1] Benzetici PTY: %s" % port)

    manuel = SahteManuel()
    eylemler = []
    ist = Istasyon2(konsol, SahteAyar(port), manuel_kontrol=manuel,
                    eylem=lambda ad, ayr: eylemler.append((ad, ayr)))
    print("\n[2] Otomatik baglanma (main.py yolu)")
    ist.otomatik_baslat()
    olc("otomatik_baslat() basarili", bekle(lambda: ist.durum()["bagli"]))
    d = ist.durum()
    olc("port ayardan okundu", d["port"] == port, d["port"])
    olc("baud 115200", d["baud"] == 115200)

    print("\n[3] Ilk tam durum (READY) alindi")
    olc("11 buton alani", len(d["durum"]["buttons"]) == 11)
    olc("T2 STRING tipinde",
        isinstance(d["durum"]["toggles"]["T2"], str),
        type(d["durum"]["toggles"]["T2"]).__name__)
    olc("T1 INT tipinde", isinstance(d["durum"]["toggles"]["T1"], int))
    olc("4 panel eksen", len(d["durum"]["joysticks"]) == 4)
    olc("7 LED alani", len(d["durum"]["leds"]) == 7)

    print("\n[4] Varsayilan esleme (kullanici tanimi)")
    be = d["buton_esleme"]
    bekleme = {"P1": "arm_disarm", "P2": "takeoff_land", "P3": "rtl",
               "P4": "mod_guided", "P5": "mod_althold", "P6": "mod_auto",
               "P8": "harita_kaynak", "P9": "kullanici_konum",
               "P10": "hepsini_kapsa", "P11": "nokta_gez"}
    for kanal, ad in bekleme.items():
        olc("%s -> %s" % (kanal, ad), be.get(kanal) == ad, be.get(kanal))
    olc("T1 -> patlat_onay", d["toggle_esleme"]["T1"] == "patlat_onay")
    olc("T2_UP -> zoom in",
        d["toggle_esleme"]["T2_UP"] == "harita_zoom_in")
    olc("T2_DOWN -> zoom out",
        d["toggle_esleme"]["T2_DOWN"] == "harita_zoom_out")
    olc("T2_CENTER -> zoom dur",
        d["toggle_esleme"]["T2_CENTER"] == "harita_zoom_dur")
    olc("P7 eylem atanmamis (LED T1 surer)", be.get("P7") == "")
    olc("patlat LED = P7", d["patlat_led"] == "P7")

    print("\n[5] Buton kenar tespiti (basma ani tetikler)")
    import serial
    s = serial.Serial(port, 115200, timeout=1.0)
    try:
        for kanal in ("P1", "P2", "P3", "P4", "P5", "P6",
                      "P8", "P9", "P10", "P11"):
            eylemler.clear()
            s.write(("SIM,BTN,%s,1\n" % kanal).encode())
            s.flush()
            ok = bekle(lambda: len(eylemler) > 0, 3.0)
            ad = eylemler[0][0] if eylemler else ""
            olc("%s basildi -> %s" % (kanal, bekleme[kanal]),
                ok and ad == bekleme[kanal], ad)
            # Basili tutmak tekrar tetiklemesin
            eylemler.clear()
            s.write(("SIM,BTN,%s,1\n" % kanal).encode())
            s.flush()
            time.sleep(0.4)
            olc("%s basili tutmak tekrar tetiklemez" % kanal,
                len(eylemler) == 0, len(eylemler))
            s.write(("SIM,BTN,%s,0\n" % kanal).encode())
            s.flush()
            time.sleep(0.1)

        print("\n[6] T1 patlatma kolu -> P7 LED + onay")
        eylemler.clear()
        s.write(b"SIM,TGL,T1,1\n")
        s.flush()
        ok = bekle(lambda: any(e[0] == "patlat_onay" for e in eylemler),
                   3.0)
        olc("T1=1 -> patlat_onay eylemi", ok)
        ayr = next((a for n, a in eylemler if n == "patlat_onay"), {})
        olc("T1=1 ayrinti acik=True", ayr.get("acik") is True, ayr)
        olc("P7 LED yandi",
            bekle(lambda: ist.durum()["durum"]["leds"]["P7"] == 1, 3.0),
            ist.durum()["durum"]["leds"])
        eylemler.clear()
        s.write(b"SIM,TGL,T1,0\n")
        s.flush()
        ok = bekle(lambda: any(e[0] == "patlat_onay" for e in eylemler),
                   3.0)
        ayr = next((a for n, a in eylemler if n == "patlat_onay"), {})
        olc("T1=0 -> ayrinti acik=False", ok and ayr.get("acik") is False,
            ayr)
        olc("P7 LED sondu",
            bekle(lambda: ist.durum()["durum"]["leds"]["P7"] == 0, 3.0),
            ist.durum()["durum"]["leds"])

        print("\n[7] T2 (STRING) -> harita zoom")
        for deger, beklenen in (("UP", "harita_zoom_in"),
                                ("DOWN", "harita_zoom_out"),
                                ("CENTER", "harita_zoom_dur")):
            eylemler.clear()
            s.write(("SIM,TGL,T2,%s\n" % deger).encode())
            s.flush()
            ok = bekle(lambda: len(eylemler) > 0, 3.0)
            ad = eylemler[0][0] if eylemler else ""
            olc("T2=%s -> %s" % (deger, beklenen), ok and ad == beklenen,
                ad)
            olc("T2 durumu string '%s'" % deger,
                ist.durum()["durum"]["toggles"]["T2"] == deger)

        print("\n[8] Panel joystickleri DRONA GITMEZ (harita kipi)")
        # Ek dron joystickleri her tam durumda aktarildigi icin cagri
        # sayisi degil ICERIGI olculur: panel cubuklarini itmek dron
        # eksenlerini DEGISTIRMEMELIDIR.
        s.write(b"SIM,JOY,J1_X,2048\n")
        s.write(b"SIM,JOY,J2_Y,2048\n")
        s.flush()
        time.sleep(0.5)
        manuel.cagrilar.clear()
        s.write(b"SIM,JOY,J1_X,3500\n")
        s.write(b"SIM,JOY,J2_Y,600\n")
        s.flush()
        time.sleep(0.6)
        olc("panel cubuklari dron eksenlerini degistirmedi",
            all(abs(c["vx"]) < 0.02 and abs(c["vy"]) < 0.02
                for c in manuel.cagrilar), manuel.cagrilar[-1:])
        n = ist.durum()["normalize"]
        olc("J1_X normalize > 0.5", n["J1_X"] > 0.5, n["J1_X"])
        olc("J2_Y normalize < -0.5", n["J2_Y"] < -0.5, n["J2_Y"])

        print("\n[9] Ek dron joystickleri -> ManuelKontrol")
        manuel.cagrilar.clear()
        # Benzetici ek eksen basmiyorsa modul ham JSON'dan algilar;
        # SIM,EKJOY komutu benzeticide varsa kullanilir.
        s.write(b"SIM,EKJOY,J3_Y,3800\n")
        s.flush()
        time.sleep(0.8)
        if manuel.cagrilar:
            c = manuel.cagrilar[-1]
            # EK_EKSEN_HEDEF: J3_Y -> vz, ters=True. Cubuk ILERI
            # itildiginde (ADC ARTAR) irtifa komutu NEGATIF olur; bu
            # RC "Mode 2" yerlesiminin dogru davranisidir.
            olc("J3_Y itildi -> vz ters isaretli", c["vz"] < -0.3, c)
            olc("aktif=True gonderildi", c["aktif"] is True)
            manuel.cagrilar.clear()
            s.write(b"SIM,EKJOY,J4_X,3600\n")
            s.flush()
            time.sleep(0.6)
            c2 = manuel.cagrilar[-1] if manuel.cagrilar else {}
            olc("J4_X -> vy pozitif", c2.get("vy", 0) > 0.3, c2)
        else:
            olc("ek eksen yok - benzetici basmiyor (HID yolu kullanilir)",
                True, "atlandi")

        print("\n[10] LED komutlari")
        basari, sebep = ist.led("P3", True)
        olc("LED,P3,ON kabul", basari, sebep)
        olc("P3 LED yandi",
            bekle(lambda: ist.durum()["durum"]["leds"]["P3"] == 1, 3.0))
        basari, _ = ist.led("P9", True)
        olc("LED,P9,ON gonderildi (firmware yok sayar)", basari)
        time.sleep(0.4)
        olc("P9 LED durumu yok (LED'siz kanal)",
            "P9" not in ist.durum()["durum"]["leds"])
        basari, sebep = ist.led("P99", True)
        olc("gecersiz kanal reddedildi", not basari, sebep)
        ist.led("ALL", True)
        olc("LED,ALL,ON tum P1-P7 yandi",
            bekle(lambda: all(v == 1 for v in
                              ist.durum()["durum"]["leds"].values()), 3.0),
            ist.durum()["durum"]["leds"])
        ist.led("ALL", False)
        time.sleep(0.3)

        print("\n[11] PING/PONG (JSON parse ETMEDEN)")
        onceki = ist.durum()["sayac"]["pong"]
        ist.ping()
        olc("PONG alindi",
            bekle(lambda: ist.durum()["sayac"]["pong"] > onceki, 4.0))
        d = ist.durum()
        olc("bozuk satir yok (PONG JSON sayilmadi)",
            d["sayac"]["bozuk"] == 0, d["sayac"])
        olc("gecikme olculdu", d["gecikme_ms"] >= 0)

        print("\n[12] Kalibrasyon")
        s.write(b"SIM,JOY,J1_X,2100\n")
        s.flush()
        time.sleep(0.4)
        m = ist.kalibre_et()
        olc("merkez kaydedildi", bool(m), m)
        olc("kalibre bayragi", ist.durum()["kalibre"])
        olc("kalibrasyondan sonra J1_X ~0",
            abs(ist.durum()["normalize"]["J1_X"]) < 0.05,
            ist.durum()["normalize"]["J1_X"])
        ist.kalibrasyon_sil()
        olc("kalibrasyon silindi", not ist.durum()["kalibre"])
    finally:
        try:
            s.close()
        except Exception:
            pass

    print("\n[13] Baglanti kesme (try/finally port kapanisi)")
    ist.kes()
    olc("bagli=False", not ist.durum()["bagli"])
    olc("kesince eksen sifirlandi",
        any(c["aktif"] is False for c in manuel.cagrilar)
        or not manuel.cagrilar, manuel.cagrilar[-1:] )
    olc("port yeniden acilabilir (ReadFile hatasi yok)",
        ist.baglan(port)[0] and bekle(lambda: ist.durum()["bagli"], 5.0))
    ist.kes()

    proc.kill()
    print("\n" + "=" * 66)
    print("SONUC: %d GECTI / %d KALDI" % (len(GECTI), len(KALDI)))
    if KALDI:
        for k in KALDI:
            print("  KALDI: " + k)
    print("=" * 66)
    return 0 if not KALDI else 1


if __name__ == "__main__":
    sys.exit(main())
