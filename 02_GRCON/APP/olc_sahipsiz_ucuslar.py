#!/usr/bin/env python3.11
"""Sahipsiz ucus segmentlerini olcer (SILME YAPMAZ).

Merkez sunucuda calistirilir. Amac: `ucus_listesi()` yeni sahiplik
kuraliyla hangi ucuslari "sahipsiz" saydigini GORMEK; temizlik karari
bu olcumden sonra verilir.

Kullanim (merkez sunucuda):
    cd /opt/goktungu/app && /usr/bin/python3.11 olc_sahipsiz_ucuslar.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _pg_kur() -> bool:
    """main.py:213-232 ile AYNI kurulumu yapar.

    AGENTS.md notu: yardimci betikler bu kurulumu atlarsa
    `veritabani.baglanti()` PostgreSQL yerine SQLite'a duser ve olcum
    YANLIS depoyu okur. Bu yuzden basarisizlikta betik durur.
    """
    from goktungu import pg as _pg
    from goktungu import veritabani as _vt
    if not _pg.dosya_var():
        print("HATA: PostgreSQL yapilandirma dosyasi yok.")
        return False
    if not _pg.dosyadan_yukle():
        print("HATA: PostgreSQL yapilandirmasi yuklenemedi.")
        return False
    if not _pg.VAR:
        print("HATA: psycopg2 surucusu yok.")
        return False
    _vt.kip_ayarla("postgresql")
    y = _pg.yapilandirma_oku() or {}
    print("Depo: PostgreSQL %s@%s:%s/%s"
          % (y.get("user", "?"), y.get("host", "?"),
             y.get("port", "?"), y.get("dbname", "?")))
    return True


def main() -> int:
    if not _pg_kur():
        return 2
    from goktungu import veritabani

    print("=" * 62)

    # Yonetici gozuyle TUM ucuslar
    tumu = veritabani.ucus_listesi(yonetici=True, limit=5000)
    print(f"Toplam ucus segmenti: {len(tumu)}")

    sahipli, sahipsiz = [], []
    for u in tumu:
        if str(u.get("sahip_eposta") or "").strip():
            sahipli.append(u)
        else:
            sahipsiz.append(u)

    print(f"  Sahipli  : {len(sahipli)}")
    print(f"  Sahipsiz : {len(sahipsiz)}")
    print()

    if sahipli:
        print("--- SAHIPLI UCUSLAR ---")
        sayac: dict = {}
        for u in sahipli:
            ep = str(u.get("sahip_eposta") or "").lower()
            sayac[ep] = sayac.get(ep, 0) + 1
        for ep, n in sorted(sayac.items()):
            print(f"  {ep}: {n} ucus")
        print()

    if sahipsiz:
        print("--- SAHIPSIZ UCUSLAR (yalniz yoneticiye gorunur) ---")
        for u in sahipsiz[:40]:
            print(f"  id={u['id']} dron={u['dron_id']} "
                  f"nokta={u.get('nokta', '?')} "
                  f"pilotlar(eski)={u.get('pilotlar')}")
        if len(sahipsiz) > 40:
            print(f"  ... ve {len(sahipsiz) - 40} tane daha")
        print()

    # Yeni pilotun gozuyle: hicbir sey gormemesi gerekir
    yeni = veritabani.ucus_listesi(
        eposta="fatih.gemi@gokkubbetech.com", yonetici=False, limit=5000)
    print("--- YENI PILOT GORUNUMU (fatih.gemi@gokkubbetech.com) ---")
    print(f"  Gordugu ucus sayisi: {len(yeni)}  "
          f"(beklenen: 0 — hic takeoff vermedi)")

    # Sahibin gozuyle
    sahip = veritabani.ucus_listesi(
        eposta="mkaderoglu@gokkubbetech.com", yonetici=False, limit=5000)
    print("--- SAHIP GORUNUMU (mkaderoglu@gokkubbetech.com) ---")
    print(f"  Gordugu ucus sayisi: {len(sahip)}")

    print()
    print("=" * 62)
    hatali = 0
    if len(yeni) == 0:
        print("[GECTI] Yeni pilot hicbir ucus GORMUYOR.")
    else:
        print(f"[KUSUR] Yeni pilot {len(yeni)} ucus goruyor!")
        hatali += 1
    if sahipli and len(sahip) == len(sahipli):
        print(f"[GECTI] Sahip kendi {len(sahip)} ucusunu goruyor.")
    elif sahipli:
        print(f"[KUSUR] Sahip {len(sahip)} goruyor, "
              f"beklenen {len(sahipli)}.")
        hatali += 1
    return 1 if hatali else 0


if __name__ == "__main__":
    sys.exit(main())
