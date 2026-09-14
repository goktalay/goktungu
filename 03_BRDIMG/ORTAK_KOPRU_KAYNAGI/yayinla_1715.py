#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""GOKTUNGU Kopru v1.7.15 — depo yayin betigi.

NEDEN BU SURUM: M50 servisi (servis_m50.py/m50_hvs.py) onceki
surumlerde (1.7.13/1.7.14, katalogda etkin son surum) koda girmisti
ama pakette ureticinin gercek calisma-zamani ikilileri
(HVideoSDK.dll, HVideoUtility.dll) ve Python baglayicisi (Hvs paketi)
YOKTU. Panelde M50 servisi hic gorunmuyordu (kullanicinin sagladigi
SDK dosyalari o surumden sonra geldi) ve servis calistirilsa bile
"M50 Windows SDK bulunamadi" ile reddedilirdi. `kopru/m50_sdk/`
altina ureticinin dogrulanmis SDK kopyasi gomuldu; kurulum ayrica
yapilandirma gerektirmez.

Kullanim (MERKEZ SUNUCUDA):
    python3.11 yayinla_1715.py
"""
import sys

sys.path.insert(0, "/opt/goktungu/merkez/python")

import mk_depo  # noqa: E402

SURUM = "1.7.15"

NOTLAR = (
    "M50 SERVISI GERCEKTEN CALISIR HALE GELDI. Onceki surumde "
    "servis_m50.py/m50_hvs.py koda girmisti ama pakette uretici "
    "SDK'sinin calisma-zamani ikilileri (HVideoSDK.dll, "
    "HVideoUtility.dll) ve Python baglayicisi (Hvs paketi) yoktu; "
    "M50 baglanti denemesi \"M50 Windows SDK bulunamadi\" ile "
    "reddediliyordu. kopru/m50_sdk/ altina ureticinin dogrulanmis "
    "SDK kopyasi eklendi (bin/HVideoSDK.dll, bin/HVideoUtility.dll, "
    "Hvs/*.py). Kurulum ek yapilandirma gerektirmez; m50_hvs.py bu "
    "yolu otomatik bulur. "
    "Windows: GOKTUNGU-Kopru-Setup.exe sihirbazi, Python 3.11 "
    "gomulu, C:\\Program Files\\Goktungu\\Kopru altina kurulur, "
    "services.msc'de gorunen gercek Windows servisi. Ubuntu: "
    "goktungu-kopru.deb, systemd sistem servisi. Yukseltme yerinde "
    "yapilir: servis durdurulur, dosyalar guncellenir, servis "
    "baslatilir; ayarlar ve merkez kaydi korunur."
)

HEDEFLER = [
    ("windows", "/root/goktungu_github/03_BRDIMG/ORTAK_KOPRU_KAYNAGI/"
                "dagitim/GOKTUNGU-Kopru-Setup-1.7.15.exe"),
    ("linux", "/root/goktungu_github/03_BRDIMG/ORTAK_KOPRU_KAYNAGI/"
              "dagitim/goktungu-kopru_1.7.15_all.deb"),
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
