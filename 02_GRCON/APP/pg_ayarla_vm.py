#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kalici gelistirme VM'i icin PostgreSQL yapilandirmasini yazar.

sinav_2452.py'nin [6] GERCEK OLCUM bolumu `pg.json` bulunmadiginda
sessizce ATLANIR. Atlanan olcum, havuz sizintisinin ASIL kanitidir
(kod denetimi sizintiyi gostermez); bu yuzden gelistirme makinesinde
yapilandirma bir kez yazilmalidir.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from goktungu import pg as P  # noqa: E402

HOST = "127.0.0.1"
PORT = 5432
VT = "goktungu"
KUL = "goktungu"
SIFRE = "goktungu2026"


def main() -> int:
    d = P.dene(HOST, PORT, VT, KUL, SIFRE)
    if not d.get("tamam"):
        print("[HATA] baglanti denemesi basarisiz: %s" % d.get("hata"))
        return 1
    print("[OK] surum=%s tablo_olustur=%s yazma=%s"
          % (d.get("surum_no"), d["yetki"]["tablo_olustur"],
             d["yetki"]["yazma"]))
    P.yapilandir(HOST, PORT, VT, KUL, SIFRE, diske_yaz=True)
    print("[OK] pg.json: %s" % P._pg_dosya_yolu())
    print("[OK] yapilandirma_var=%s dosya_var=%s"
          % (P.yapilandirma_var(), P.dosya_var()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
