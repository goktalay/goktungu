#!/usr/bin/env python3.11
"""Kopru v1.4.1'i merkez depoya ekler (setup.exe + .deb).

MERKEZDE calisir: /opt/goktungu/merkez/python/

1.4.1'DA NE DEGISTI
-------------------
1.3.0'a kadar dagitilan sey bir ARSIVDI: kullanici zip/tar aciyor,
icindeki `kur.bat` / `kur.sh` konsol betigini calistiriyordu. Kullanici
bunu acikca reddetti: "konsol degil bildigin kurulum setup programi
istemistim, exe olarak" ve "servis olarak calismasini istemistim".

Artik dagitilan sey gercek kurulum programidir:

- Windows : GOKTUNGU-Kopru-Setup-1.4.1.exe  (NSIS sihirbaz, ~17 MB)
            Python 3.11.9 GOMULU gelir; kullanici Python kurmaz.
            Servis, Windows Servis Denetim Yoneticisi'ne (SCM) kayitli
            gercek bir servistir (pywin32), Gorev Zamanlayici DEGIL.
- Ubuntu  : goktungu-kopru_1.4.1_all.deb   (apt ile kurulur, ~546 KB)
            systemd SISTEM servisi, kendi servis kullanicisiyla.

Paket biciminin degismesi onemli: eski kayitlar `.zip`/`.tar.gz`
tasiyordu, indirme sayfasi uzantiya gore kurulum komutu gosteriyor.
Bu yuzden ayni surum yine iki platform kaydi olarak eklenir.

`ortak` ve eski platform kayitlari KAPATILMAZ: sahada 1.2.x/1.3.x
kurulu kopruler guncelleme denetimi yaparken eski kayitlari sorabilir.
"""
from __future__ import annotations

import sys

sys.path.insert(0, "/opt/goktungu/merkez/python")

import mk_depo  # noqa: E402

SURUM = "1.4.1"
NOTLAR = (
    "Gercek kurulum programi. Windows: GOKTUNGU-Kopru-Setup.exe sihirbazi "
    "(cift tiklanir, yonetici izni ister), Python 3.11 gomulu gelir, "
    "C:\\Program Files\\Goktungu\\Kopru altina kurulur ve Windows Servis "
    "Denetim Yoneticisi'ne kayitli GERCEK SERVIS olarak calisir "
    "(services.msc'de gorunur, otomatik baslangic, coktuginde kendini "
    "toparlar). Baslat menusu ve masaustu kisayollari GOKTUNGU mavi ikonuyla. "
    "Denetim Masasi > Program Ekle/Kaldir kaydi olusur. "
    "Ubuntu: goktungu-kopru.deb paketi, 'apt install' ile kurulur, systemd "
    "sistem servisi olarak kendi servis kullanicisiyla calisir, uygulama "
    "menusu ve masaustu kisayolu eklenir. Her iki platformda yukseltme "
    "yerinde yapilir: servis durdurulur, dosyalar guncellenir, servis "
    "baslatilir; ayarlar ve merkez kaydi korunur."
)

HEDEFLER = [
    ("windows", f"/tmp/GOKTUNGU-Kopru-Setup-{SURUM}.exe"),
    ("linux", f"/tmp/goktungu-kopru_{SURUM}_all.deb"),
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
