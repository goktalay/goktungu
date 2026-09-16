#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CSS'te YEDEKSIZ tanimsiz tema degiskeni kullanimini olcer.

`var(--x, yedek)` bicimi guvenlidir (yedek deger var).
`var(--x)` bicimi ve --x tanimli degilse -> gorunum bozulur.
"""
import io
import os
import re
import sys

KOK = os.path.dirname(os.path.abspath(__file__))
if os.path.isdir(os.path.join(KOK, "goktungu", "css")):
    KOK = os.path.join(KOK, "goktungu")

DOSYALAR = ["css/stil.css", "css/flight.css"]


def tanimlilar():
    ad = set()
    for d in DOSYALAR:
        y = os.path.join(KOK, d)
        if not os.path.exists(y):
            continue
        s = io.open(y, encoding="utf-8").read()
        ad |= set(re.findall(r"--([a-zA-Z0-9_-]+)\s*:", s))
    return ad


def main():
    tanim = tanimlilar()
    hata = 0
    for d in DOSYALAR:
        y = os.path.join(KOK, d)
        if not os.path.exists(y):
            continue
        s = io.open(y, encoding="utf-8").read()
        satirlar = s.split("\n")
        for i, sat in enumerate(satirlar, 1):
            # yedeksiz kullanim: var(--ad)  (virgul YOK)
            for ad in re.findall(r"var\(\s*--([a-zA-Z0-9_-]+)\s*\)", sat):
                if ad not in tanim:
                    print("[KUSUR] %s:%d  var(--%s) tanimsiz ve yedeksiz"
                          % (d, i, ad))
                    print("        %s" % sat.strip()[:100])
                    hata += 1
    print("=" * 60)
    if hata:
        print("SONUC: %d YEDEKSIZ TANIMSIZ DEGISKEN" % hata)
        return 1
    print("SONUC: yedeksiz tanimsiz degisken YOK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
