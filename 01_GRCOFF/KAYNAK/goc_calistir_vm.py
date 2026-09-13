#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gelistirme VM'inde PostgreSQL semasini kurar / gunceller.

`sinav_2451_pg.py` uc maddeden kaliyordu ("PG'de tablolar kurulu",
"sema surumu damgalanmis", "gercek PG olcumu"): veritabani BOS oldugu
icin. Bu betik goc motorunu calistirir; boylece sinav artik gercek
semayi olcer.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from goktungu import pg, goc  # noqa: E402


def main() -> int:
    if not pg.yapilandirma_var() and not pg.dosyadan_yukle():
        print("[HATA] pg.json yok; once pg_ayarla_vm.py calistirin.")
        return 1

    motor = goc.GocMotoru(konsol=lambda *a: print("[GOC]", *a))
    d = motor.durum()
    print("[BILGI] kip=%s sema=%s hedef=%s bekleyen=%d"
          % (d["kip"], d["sema_surumu"], d["hedef_surum"],
             len(d["bekleyen"])))

    def ilerleme(yuzde, ileti, ad=""):
        print("  %5.1f%%  %s %s" % (yuzde, ileti, ("(%s)" % ad) if ad else ""))

    s = motor.calistir(ilerleme)
    print("[SONUC] tamam=%s uygulanan=%s hata=%s"
          % (s.get("tamam"), s.get("uygulanan"), s.get("hata") or "-"))

    with pg.baglanti() as b:
        im = b.cursor()
        im.execute("SELECT count(*) FROM information_schema.tables"
                   " WHERE table_schema='public'")
        print("[OLCUM] public sema tablo sayisi: %s" % im.fetchone()[0])
    print("[OLCUM] sema surumu: %s" % goc.sema_surumu())
    pg.tum_baglantilari_kapat()
    return 0 if s.get("tamam") else 1


if __name__ == "__main__":
    raise SystemExit(main())
