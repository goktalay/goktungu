#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""GOKTUNGU Kopru v1.7.20 — depo yayin betigi.

NEDEN BU SURUM (1.7.20): Faz D — yerel AI cikarimi artik koprunun
icinde calisir (ayri AI bilgisayari zorunlu degil) ve AI tespit
kutulari saha goruntusune CIZILIR (olculen kusur: hic cizilmiyordu).

Kullanim (MERKEZ SUNUCUDA):
    python3.11 yayinla_1719.py
"""
import sys

sys.path.insert(0, "/opt/goktungu/merkez/python")

import mk_depo  # noqa: E402

SURUM = "1.7.20"

NOTLAR = (
    "YENI (Faz D): YEREL AI CIKARIMI KOPRUNUN ICINDE. Her kopru kurulumu "
    "kendi AI iscisini 127.0.0.1 uzerinde alt surec olarak calistirir; "
    "ayri bir AI bilgisayari artik zorunlu degil (uzak AI kayitlari "
    "korunur, ikisi birlikte kullanilir). DUZELTME (olculdu): AI tespit "
    "kutulari saha goruntusune HIC cizilmiyordu; kutulari besleyen yol "
    "yoktu. Servis artik yerel bir alici acar, kutulari once video "
    "servisine yazar (kare uzerine cizim), sonra merkeze aynen iletir. "
    "Linux kurulumu yerel AI icin numpy+OpenCV'yi ayri bir adimda kurar; "
    "basarisiz olursa kurulum dusmez. Windows kurulumu gomulu "
    "onnxruntime nedeniyle buyudu (52,7 MB -> 72 MB)."
)

HEDEFLER = [
    ("windows", "/root/goktungu_github/03_BRDIMG/ORTAK_KOPRU_KAYNAGI/"
                "dagitim/GOKTUNGU-Kopru-Setup-1.7.20.exe"),
    ("linux", "/root/goktungu_github/03_BRDIMG/ORTAK_KOPRU_KAYNAGI/"
              "dagitim/goktungu-kopru_1.7.20_all.deb"),
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
