#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""GOKTUNGU Kopru v1.7.22 — depo yayin betigi.

NEDEN BU SURUM (1.7.22): sahip firma unvani 'Turkbey Teknoloji Anonim
Sirketi' — Windows kurulum kunyesi (yayimci), Debian bakimci alani,
uygulama menusu telif satiri ve konsol basligi.

Kullanim (MERKEZ SUNUCUDA):
    python3.11 yayinla_1721.py
"""
import sys

sys.path.insert(0, "/opt/goktungu/merkez/python")

import mk_depo  # noqa: E402

SURUM = "1.7.22"

NOTLAR = (
    "SIRKET UNVANI: sahip firma adi Windows kurulum kunyesi (yayimci), Debian "
    "paket bakimcisi, uygulama menusu telif satiri ve konsol basligi dahil her "
    "yerde 'Turkbey Teknoloji Anonim Sirketi' olarak guncellendi. Alan adi, "
    "e-posta ve servis davranisi degismedi (radar 2.3.0, M50 1.2.0 ile ayni)."
)

HEDEFLER = [
    ("windows", "/root/goktungu_github/03_BRDIMG/ORTAK_KOPRU_KAYNAGI/"
                "dagitim/GOKTUNGU-Kopru-Setup-1.7.22.exe"),
    ("linux", "/root/goktungu_github/03_BRDIMG/ORTAK_KOPRU_KAYNAGI/"
              "dagitim/goktungu-kopru_1.7.22_all.deb"),
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
