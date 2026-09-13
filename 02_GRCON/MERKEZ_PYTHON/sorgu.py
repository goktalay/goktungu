#!/usr/bin/env python3.11
# =================================================================
# GOKTUNGU MERKEZ - hizli sorgu yardimcisi (gelistirme araci)
# Kullanim: python3.11 sorgu.py "SELECT ..."
# Merkez ayar dosyasindan PG bilgilerini okur; boylece SSH uzerinden
# ic ice tirnak kacisiyla ugrasmak gerekmez.
# =================================================================
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mk_db as db  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("kullanim: sorgu.py \"SELECT ...\"")
        return 2
    sql = sys.argv[1]
    try:
        satirlar = db.sorgu(sql)
    except Exception as e:
        print(f"HATA: {e}")
        return 1
    if not satirlar:
        print("(bos)")
        return 0
    basliklar = list(satirlar[0].keys())
    print(" | ".join(basliklar))
    print("-" * 70)
    for s in satirlar:
        print(" | ".join(str(s.get(b)) for b in basliklar))
    print(f"({len(satirlar)} satir)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
