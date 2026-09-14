#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""GOKTUNGU Kopru v1.7.16 — depo yayin betigi.

NEDEN BU SURUM: 1.7.15'te uretici HVS SDK'sinin Hvs/datdefs.py dosyasi
DLL dizinini calisma dizinine (cwd) gore '..\\bin' olarak hesapliyordu;
bu yalniz ureticinin kendi demo klasor duzeninde dogruydu. Koprunun
calisma dizini farkli oldugu icin M50 baglantisi "[WinError 2] Sistem
belirtilen dosyayi bulamiyor" ile reddediliyordu. Yol artik dosyanin
kendi konumundan hesaplaniyor; calisma dizininden bagimsiz.

Kullanim (MERKEZ SUNUCUDA):
    python3.11 yayinla_1716.py
"""
import sys

sys.path.insert(0, "/opt/goktungu/merkez/python")

import mk_depo  # noqa: E402

SURUM = "1.7.16"

NOTLAR = (
    "DUZELTME: uretici SDK'sinin Hvs/datdefs.py dosyasi DLL dizinini "
    "calisma dizinine (cwd) gore '..\\bin' olarak hesapliyordu; bu "
    "yalniz ureticinin kendi demo klasor duzeninde dogruydu. Koprunun "
    "calisma dizini farkli oldugu icin M50 baglantisi \"[WinError 2] "
    "Sistem belirtilen dosyayi bulamiyor\" ile reddediliyordu (1.7.15'te "
    "SDK ikilileri pakette vardi ama bu yol kusuru yuzunden hala "
    "baglanamiyordu). Yol artik dosyanin kendi konumundan hesaplaniyor; "
    "calisma dizininden bagimsiz."
)

HEDEFLER = [
    ("windows", "/root/goktungu_github/03_BRDIMG/ORTAK_KOPRU_KAYNAGI/"
                "dagitim/GOKTUNGU-Kopru-Setup-1.7.16.exe"),
    ("linux", "/root/goktungu_github/03_BRDIMG/ORTAK_KOPRU_KAYNAGI/"
              "dagitim/goktungu-kopru_1.7.16_all.deb"),
]


def main() -> int:
    basarili = 0
    for platform, yol in HEDEFLER:
        print(f"\n== {platform} ==")
        print(f"  kaynak: {yol}")
        try:
            sonuc = mk_depo.paket_ekle(
                "kopru",
                SURUM,
                yol,
                platform=platform,
                kanal="kararli",
                paket_tur="tam",
                notlar=NOTLAR,
            )
        except Exception as hata:  # noqa: BLE001
            print(f"  [HATA] {type(hata).__name__}: {hata}")
            continue
        print(f"  [OK] eklendi: {sonuc.get('dosya_ad')}")
        print(f"       boyut  : {sonuc.get('dosya_boyut'):,} bayt")
        sha = sonuc.get("sha256") or ""
        print(f"       sha256 : {sha[:20]}...")
        imza = sonuc.get("imza")
        print(f"       imza   : {'VAR (Ed25519)' if imza else 'YOK'}")
        basarili += 1

    print("\n== DOGRULAMA ==")
    for platform, _ in HEDEFLER:
        son = mk_depo.son_surum("kopru", platform=platform, paket_tur="tam")
        if son:
            print(f"  {platform:8s} son surum: {son.get('surum')} "
                  f"({son.get('dosya_ad')})")
        else:
            print(f"  {platform:8s} [KALDI] son surum okunamadi")

    return 0 if basarili == len(HEDEFLER) else 1


if __name__ == "__main__":
    sys.exit(main())
