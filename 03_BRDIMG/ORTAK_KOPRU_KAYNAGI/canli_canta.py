#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KURULU KOPRU icin sanal GCCDUAL cantasi (canli olcum araci).

Gercek fiziksel canta olmadan, KURULU koprunun GroundGCC servisinin
gercekten seri port acip komut isledigini olcmeye yarar. `socat` ile
kurulan sanal seri cifti uzerinde firmware davranisini taklit eder:

  * duzenli JSON durum paketi basar (buton/kol/eksen)
  * `PING` gorurse `PONG` yanitlar (canlilik denetimi)
  * `LED <kanal> <0|1>` gorurse gunluge yazar (komut ulasti kaniti)

Kullanim:
    socat -d PTY,raw,echo=0,link=/tmp/uc_a PTY,raw,echo=0,link=/tmp/uc_b &
    python3 canli_canta.py /tmp/uc_b --gunluk /tmp/canta.log

Sinirsiz calisir; olcum bitince surec oldurulur.
"""

import argparse
import json
import os
import sys
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port")
    ap.add_argument("--gunluk", default="")
    ap.add_argument("--hz", type=float, default=10.0)
    a = ap.parse_args()

    gunluk = None
    if a.gunluk:
        gunluk = open(a.gunluk, "a", buffering=1)

    def yaz(satir):
        if gunluk:
            gunluk.write(satir + "\n")
        print(satir, flush=True)

    def guvenli_yaz(fd, bayt):
        """Tampon doluysa (EAGAIN) sessizce vazgecer; cikmaz."""
        try:
            os.write(fd, bayt)
            return True
        except BlockingIOError:
            return False
        except OSError as e:
            yaz("CANTA YAZMA HATASI: %s" % e)
            return False

    dusen = [0]
    ledler = {"P%d" % i: 0 for i in range(1, 8)}   # P1..P7 LED cikisi

    f = os.open(a.port, os.O_RDWR | os.O_NOCTTY)
    os.set_blocking(f, False)
    yaz("CANTA HAZIR: %s" % a.port)

    tampon = b""
    aralik = 1.0 / max(a.hz, 1.0)
    sonraki = time.time()

    while True:
        # --- gelen komutlar
        try:
            g = os.read(f, 4096)
        except BlockingIOError:
            g = b""
        except OSError as e:
            yaz("CANTA OKUMA HATASI: %s" % e)
            break

        if g:
            tampon += g
            while b"\n" in tampon:
                satir, tampon = tampon.split(b"\n", 1)
                s = satir.decode("utf-8", "ignore").strip()
                if not s:
                    continue
                if s == "PING":
                    if guvenli_yaz(f, b"PONG\n"):
                        yaz("CANTA PONG GONDERDI")
                    else:
                        yaz("CANTA PONG YAZILAMADI (tampon dolu)")
                elif s.startswith("LED"):
                    # GERCEK PROTOKOL: `LED,P3,ON` / `LED,ALL,OFF`
                    # (bkz. goktungu/istasyon2.py satir 15). Firmware
                    # gibi davranip LED durumunu guncelle: panel LED
                    # durumunu cantanin `leds` alanindan da dogrular.
                    yaz("CANTA LED ALDI: %s" % s)
                    par = [p.strip().upper() for p in s.split(",")]
                    if len(par) >= 3:
                        kanal, deger = par[1], (1 if par[2] == "ON" else 0)
                        if kanal == "ALL":
                            for p in list(ledler):
                                ledler[p] = deger
                        elif kanal in ledler:
                            ledler[kanal] = deger
                else:
                    yaz("CANTA BILINMEYEN: %s" % s)

        # --- durum paketi
        simdi = time.time()
        if simdi >= sonraki:
            sonraki = simdi + aralik
            # GERCEK FIRMWARE PAKETI (goktungu/istasyon2.py satir 11-13):
            # eksenler `joysticks` alanindadir, `axes` DEGIL. Yanlis alan
            # adi kullanilirsa panel eksenleri hic gormez ve kusur urun
            # kodunda sanilir.
            pak = {
                "event": "",
                "buttons": {"P%d" % i: 0 for i in range(1, 12)},
                "toggles": {"T1": 0, "T2": "CENTER"},
                "joysticks": {"J1_X": 2048, "J1_Y": 2048,
                              "J2_X": 2048, "J2_Y": 2048,
                              "J3_X": 2048, "J3_Y": 2048,
                              "J4_X": 2048, "J4_Y": 2048},
                "leds": dict(ledler),
            }
            # Bloklamayan yazmada tampon dolabilir. GERCEK cantada bu
            # kosul olusmaz (karsi taraf surekli okur), bu yuzden
            # tikanma bir OLCUM ARACI sorunudur ve cikmak YANLIS olur:
            # arac oldugu icin "canta veri gondermiyor" gibi gorunur ve
            # urun kodunda olmayan bir kusur aranir. Paket dusurulup
            # dongu surdurulur.
            if not guvenli_yaz(f, (json.dumps(pak) + "\n").encode()):
                dusen[0] += 1
                if dusen[0] % 50 == 1:
                    yaz("CANTA paket dusuruldu (tampon dolu, toplam %d)"
                        % dusen[0])

        time.sleep(0.01)

    os.close(f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
