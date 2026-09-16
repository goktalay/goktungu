#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""GOKTUNGU Kopru v1.7.21 — depo yayin betigi.

NEDEN BU SURUM (1.7.21): Merkez 2.4.227 radar yonetim penceresi icin
T serisi tarama radari protokolunun kalan komutlari (SETSELECT/GETSELECT,
SETJSON/GETJSON, UPLOAD_TARGET_V3) ve M50 PTZ hiz 1-60 + RTSP adres
arindirma (Merkez 2.4.204/205 ile uyum).

Kullanim (MERKEZ SUNUCUDA):
    python3.11 yayinla_1721.py
"""
import sys

sys.path.insert(0, "/opt/goktungu/merkez/python")

import mk_depo  # noqa: E402

SURUM = "1.7.21"

NOTLAR = (
    "RADAR (Merkez 2.4.227 radar yonetim penceresi): T serisi tarama radari "
    "protokolunun kalan komutlari eklendi — SETSELECT/GETSELECT (secili iz), "
    "SETJSON/GETJSON (koordinat ve sistem JSON yapilandirmasi), UPLOAD_TARGET_V3 "
    "nokta izi sayaci. Yeni eylemler secim_yaz/secim_oku/json_oku/json_yaz; "
    "sonuclar durum paketiyle merkeze tasinir (radar servisi 2.3.0). "
    "M50 (servis 1.2.0): PTZ hiz ust siniri 10 -> 60; cihazin RTSP adresine "
    "gomulu kimlik geldiginde akis kapatilmaz, adres arindirilir (kimlik "
    "telemetriye cikmaz)."
)

HEDEFLER = [
    ("windows", "/root/goktungu_github/03_BRDIMG/ORTAK_KOPRU_KAYNAGI/"
                "dagitim/GOKTUNGU-Kopru-Setup-1.7.21.exe"),
    ("linux", "/root/goktungu_github/03_BRDIMG/ORTAK_KOPRU_KAYNAGI/"
              "dagitim/goktungu-kopru_1.7.21_all.deb"),
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
