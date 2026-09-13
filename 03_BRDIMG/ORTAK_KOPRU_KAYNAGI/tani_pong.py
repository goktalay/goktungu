#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K2 TANI: PONG neden sayilmiyor?

Gercek `pyserial` ile sanal cantaya baglanip HAM baytlari okur.
Boylece PONG'un tel uzerinde hangi bicimde geldigi gorulur:
kendi satirinda mi, yoksa JSON ile ayni tamponda mi.

Kullanim:
    python3 tani_pong.py /tmp/canli2/uc_a
"""

import sys
import time

import serial


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "/tmp/canli2/uc_a"
    s = serial.Serial(port, 115200, timeout=1.0)
    print("BAGLANDI: %s" % port)

    # Cantanin akisi zaten basliyor; birkac satir tuket.
    for _ in range(3):
        s.readline()

    print("\n--- PING gonderiliyor ---")
    s.write(b"PING\n")
    s.flush()

    bulundu = False
    t0 = time.time()
    while time.time() - t0 < 6.0:
        ham = s.readline()
        if not ham:
            continue
        cozulmus = ham.decode("utf-8", "replace")
        kirpik = cozulmus.strip()
        if "PONG" in cozulmus:
            bulundu = True
            print("\n>>> PONG ICEREN SATIR BULUNDU")
            print("    ham repr      : %r" % ham[:120])
            print("    strip() sonucu: %r" % kirpik[:120])
            print("    == 'PONG' ?   : %s" % (kirpik == "PONG"))
            print("    uzunluk       : %d" % len(kirpik))
            if kirpik != "PONG":
                print("    ** SATIR SAF PONG DEGIL — birlesmis **")
                print("    ilk 60 bayt: %r" % ham[:60])
            break

    if not bulundu:
        print("\n>>> PONG HIC GELMEDI")

    s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
