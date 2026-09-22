#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""
goktungu_ikiz_denetle.py — İKİZ paket drift denetimi (Risk 1 kapısı).

GRCOFF ve GRCON, ortak `goktungu/` Python paketini ayrı ayrı FİZİKSEL KOPYA
olarak taşır (symlink/submodule değil). İki kopya birebir aynı kalmalıdır;
birindeki hata düzeltmesi diğerine elle uygulanmazsa sürüklenme (drift) oluşur.

Bu betik iki kopyayı (ve GRCON'a özel ikiz veritabani.py çiftini) karşılaştırır.
Fark bulursa çıkış kodu 1 ile döner — CI/derleme öncesi kapı olarak kullanın:

    python3.11 10_ORTAK_ARACLAR/goktungu_ikiz_denetle.py

Fark yoksa çıkış kodu 0. Hiçbir dosyayı DEĞİŞTİRMEZ (salt-okuma).
"""
import sys
import filecmp
from pathlib import Path

# Depo kökü: bu dosya 10_ORTAK_ARACLAR/ altında → bir üst dizin köktür.
KOK = Path(__file__).resolve().parent.parent

# (etiket, sol yol, sağ yol) — birebir aynı olması beklenen ikizler.
# NOT: GRCON APP/veritabani.py ile POSTGRESQL_AKTARIM/veritabani.py KASITLI olarak
# farklıdır (aktarım aracı ≠ çalışma zamanı adaptörü), bu yüzden ikiz sayılmaz.
IKIZLER = [
    (
        "goktungu/ paketi (GRCOFF ↔ GRCON)",
        KOK / "01_GRCOFF" / "KAYNAK" / "goktungu",
        KOK / "02_GRCON" / "APP" / "goktungu",
    ),
]


def _dizin_farklari(sol: Path, sag: Path) -> list[str]:
    """İki dizini özyinelemeli karşılaştırıp fark satırlarını döndürür."""
    farklar: list[str] = []
    kar = filecmp.dircmp(str(sol), str(sag))

    def _gez(k: filecmp.dircmp, on_ek: str = "") -> None:
        for ad in k.left_only:
            farklar.append(f"  yalnız SOLDA : {on_ek}{ad}")
        for ad in k.right_only:
            farklar.append(f"  yalnız SAĞDA : {on_ek}{ad}")
        for ad in k.diff_files:
            farklar.append(f"  İÇERİK FARKLI: {on_ek}{ad}")
        for ad in k.funny_files:
            farklar.append(f"  okunamadı    : {on_ek}{ad}")
        for alt_ad, alt in k.subdirs.items():
            _gez(alt, f"{on_ek}{alt_ad}/")

    _gez(kar)
    return farklar


def main() -> int:
    toplam_fark = 0
    for etiket, sol, sag in IKIZLER:
        if not sol.exists() or not sag.exists():
            print(f"[ATLA] {etiket}: taraf yok ({sol if not sol.exists() else sag})")
            continue

        if sol.is_dir():
            farklar = _dizin_farklari(sol, sag)
        else:
            farklar = [] if filecmp.cmp(str(sol), str(sag), shallow=False) else [
                f"  İÇERİK FARKLI: {sol.name}"
            ]

        if farklar:
            toplam_fark += len(farklar)
            print(f"[FARK] {etiket} — {len(farklar)} sürüklenme:")
            for satir in farklar:
                print(satir)
        else:
            print(f"[TAMAM] {etiket}: birebir aynı")

    print("-" * 60)
    if toplam_fark:
        print(f"SONUÇ: {toplam_fark} sürüklenme bulundu — ikiz kopyaları eşitleyin.")
        return 1
    print("SONUÇ: tüm ikizler senkron.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
