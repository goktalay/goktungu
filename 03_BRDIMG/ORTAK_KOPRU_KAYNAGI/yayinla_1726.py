#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""GOKTUNGU Kopru v1.7.26 — depo yayin betigi.

NEDEN BU SURUM (1.7.26): Turkbey Teknoloji A.S. amblemi tum kopru ikonlarinda.

Kullanim (MERKEZ SUNUCUDA):
    python3.11 yayinla_1726.py
"""
import sys

sys.path.insert(0, "/opt/goktungu/merkez/python")

import mk_depo  # noqa: E402

SURUM = "1.7.26"

NOTLAR = (
    "MARKA: Türkbey Teknoloji A.Ş. amblemi (kırmızı kalkan-kurt) tüm köprü ikonlarına "
    "uygulandı (kurulum, hicolor, favicon, .ico). İşlevsel değişiklik yok; yalnız marka görseli."
)

HEDEFLER = [
    ("windows", "/root/goktungu_github/03_BRDIMG/ORTAK_KOPRU_KAYNAGI/"
                "dagitim/GOKTUNGU-Kopru-Setup-1.7.26.exe"),
    ("linux", "/root/goktungu_github/03_BRDIMG/ORTAK_KOPRU_KAYNAGI/"
              "dagitim/goktungu-kopru_1.7.26_all.deb"),
]


def main() -> int:
    basarili = 0
    for platform, yol in HEDEFLER:
        print(f"\n== {platform} ==")
        try:
            sonuc = mk_depo.paket_ekle(
                "kopru", SURUM, yol, platform=platform, kanal="kararli",
                paket_tur="tam", notlar=NOTLAR)
        except Exception as hata:  # noqa: BLE001
            print(f"  [HATA] {type(hata).__name__}: {hata}")
            continue
        print(f"  [OK] {sonuc.get('dosya_ad')} {sonuc.get('dosya_boyut'):,} bayt "
              f"imza={'VAR' if sonuc.get('imza') else 'YOK'}")
        basarili += 1
    print("\n== DOGRULAMA ==")
    for platform, _ in HEDEFLER:
        son = mk_depo.son_surum("kopru", platform=platform, paket_tur="tam")
        print(f"  {platform:8s} son surum: {son.get('surum') if son else '[KALDI]'}")
    return 0 if basarili == len(HEDEFLER) else 1


if __name__ == "__main__":
    sys.exit(main())
