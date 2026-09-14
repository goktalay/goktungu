#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""GOKTUNGU Kopru v1.7.19 — depo yayin betigi.

NEDEN BU SURUM (1.7.19): Faz C — coklu radar (radar_id) ve coklu M50
(eo_id) servisleri; 1.7.18 SDK eylemlerinin ajan haritasindaki eksigi
giderildi; M50 RTK/pusula okuma Merkeze tasinir.

Kullanim (MERKEZ SUNUCUDA):
    python3.11 yayinla_1719.py
"""
import sys

sys.path.insert(0, "/opt/goktungu/merkez/python")

import mk_depo  # noqa: E402

SURUM = "1.7.19"

NOTLAR = (
    "YENI (Faz C): COKLU RADAR ve COKLU M50. Radar servisi radar_id, M50 "
    "servisi eo_id basina ayri istemci calistirir; Merkez 2.4.192 her "
    "cihazi ayri baglar/keser, RTK/ayar/PTZ komutlari cihaz kimligiyle "
    "gider. Durum paketi 'radarlar' ve 'eo_cihazlar' tasir; eski Merkez "
    "surumleri birincil cihazla calismaya devam eder. Kopru paneli M50 "
    "penceresinde cihaz no; servis kartinda cihaz sayilari. M50 RTK/GPS "
    "ve pusula SDK'dan okunup Merkeze tasinir. DUZELTME: 1.7.18 SDK "
    "eylemleri (aci okuma, on ayarlar, tarama, takip yetenegi) ajan "
    "haritasinda eksikti."
)

HEDEFLER = [
    ("windows", "/root/goktungu_github/03_BRDIMG/ORTAK_KOPRU_KAYNAGI/"
                "dagitim/GOKTUNGU-Kopru-Setup-1.7.19.exe"),
    ("linux", "/root/goktungu_github/03_BRDIMG/ORTAK_KOPRU_KAYNAGI/"
              "dagitim/goktungu-kopru_1.7.19_all.deb"),
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
