#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GRCOFF pasif takip verisi dinleyicisi.

Yalnız yerel NDJSON dosyasını okur ve olayları standart çıktıya yazar.
Ağ, araç, joystick, uçuş, aktüatör veya komut kodu içermez.
"""
import argparse
import json
import os
import time

VARSAYILAN_YOL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "veri", "track_verisi.ndjson")


def olaylari_oku(yol, baslangictan=False):
    """Dosyayı takip eder; yalnız geçerli JSON satırlarını verir."""
    konum = 0
    while True:
        try:
            with open(yol, "r", encoding="utf-8") as dosya:
                if not baslangictan and konum == 0:
                    dosya.seek(0, os.SEEK_END)
                else:
                    dosya.seek(konum)
                while True:
                    satir = dosya.readline()
                    if not satir:
                        konum = dosya.tell()
                        break
                    try:
                        olay = json.loads(satir)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(olay, dict):
                        yield olay
        except FileNotFoundError:
            pass
        time.sleep(0.25)


def main():
    ayrac = argparse.ArgumentParser(description="GRCOFF pasif takip NDJSON dinleyicisi")
    ayrac.add_argument("--dosya", default=VARSAYILAN_YOL,
                       help="Yerel track_verisi.ndjson yolu")
    ayrac.add_argument("--gecmis", action="store_true",
                       help="Mevcut satırları da yazdır")
    ayrac.add_argument("--adet", type=int, default=0,
                       help="Bu sayıda olaydan sonra güvenli biçimde çık")
    args = ayrac.parse_args()
    sayac = 0
    for olay in olaylari_oku(args.dosya, baslangictan=args.gecmis):
        print(json.dumps(olay, ensure_ascii=False, separators=(",", ":")),
              flush=True)
        sayac += 1
        if args.adet and sayac >= args.adet:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
