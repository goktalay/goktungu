#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""GOKTUNGU Kopru v1.7.23 — depo yayin betigi.

NEDEN BU SURUM (1.7.23): ilk kurulumda GRCON/GRCOFF secimi + API kodu
(Destek > Kopruler); e-posta/sifre ile merkeze kayit adimi kalkti.

Kullanim (MERKEZ SUNUCUDA):
    python3.11 yayinla_1723.py
"""
import sys

sys.path.insert(0, "/opt/goktungu/merkez/python")

import mk_depo  # noqa: E402

SURUM = "1.7.23"

NOTLAR = (
    "API KODU ILE KURULUM: ilk acilis sihirbazi 'GRCON - Merkez Sunucu mu, GRCOFF - "
    "Yerel Kurulum mu?' sorar ve yalniz API kodu (GTK1.) ister; kod merkezin Destek > "
    "Kopruler panelinde uretilir, kimligi ve merkez adresini birlikte tasir. IP/adres ve "
    "e-posta/sifre ile kayit adimi kalkti. Panelde 'API kodu ile eslestir' bolumu "
    "(Kodu yenile / merkez tasima). Merkez 2.4.232 (GRCOFF 2.5.102) ile birlikte; servis "
    "surumleri degismedi (radar 2.3.0, M50 1.2.0)."
)

HEDEFLER = [
    ("windows", "/root/goktungu_github/03_BRDIMG/ORTAK_KOPRU_KAYNAGI/"
                "dagitim/GOKTUNGU-Kopru-Setup-1.7.23.exe"),
    ("linux", "/root/goktungu_github/03_BRDIMG/ORTAK_KOPRU_KAYNAGI/"
              "dagitim/goktungu-kopru_1.7.23_all.deb"),
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
