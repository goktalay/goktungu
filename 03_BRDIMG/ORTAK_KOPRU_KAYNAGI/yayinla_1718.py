#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""GOKTUNGU Kopru v1.7.18 — depo yayin betigi.

NEDEN BU SURUM (1.7.18): SDK geri kalani. Onceki: M50 gorunur/termal RTSP yayin adresi artik cihazin
kendisinden (HVS_GetRtspUrl) otomatik okunur; operatorun elle adres
girmesi gerekmez. Adres, Merkez'in kamera akisinin gercekten okudugu
m50_ayarlar alanina yazilir (1.7.16'da yalniz durum ozetine gidiyor,
"bagli" gorunse de video gelmiyordu).

Kullanim (MERKEZ SUNUCUDA):
    python3.11 yayinla_1717.py
"""
import sys

sys.path.insert(0, "/opt/goktungu/merkez/python")

import mk_depo  # noqa: E402

SURUM = "1.7.18"

NOTLAR = (
    "YENI: M50 servisi SDK'nin geri kalanini destekler: aci okuma "
    "(GetAngleX/Y), on ayarlar (GetPresets/SetPreset/CallPreset/"
    "ClearPreset/ClearAllPreset), tarama/devriye (ControlScan) ve "
    "takip yetenegi (EnableTrackAbility). Merkez 2.4.188 Elektro-Optik "
    "paneli bu komutlari kopru uzerinden de kullanabilir."
)

HEDEFLER = [
    ("windows", "/root/goktungu_github/03_BRDIMG/ORTAK_KOPRU_KAYNAGI/"
                "dagitim/GOKTUNGU-Kopru-Setup-1.7.18.exe"),
    ("linux", "/root/goktungu_github/03_BRDIMG/ORTAK_KOPRU_KAYNAGI/"
              "dagitim/goktungu-kopru_1.7.18_all.deb"),
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
