#!/usr/bin/env python3.11
"""Kopru v1.3.0'i merkez depoya ekler (Windows + Linux, ayri paketler).

MERKEZDE calisir: /opt/goktungu/merkez/python/

NEDEN PLATFORM AYRIMI
---------------------
1.2.1'e kadar tek `ortak` paket vardi ve icinde hem `kur.bat` hem
`kur.sh` bulunuyordu. Artik kurulum betikleri platforma ozgu:
Windows tarafi Gorev Zamanlayici + Program Files + .ico, Linux tarafi
systemd + /opt + hicolor PNG kullaniyor. Tek pakette tasimak,
kullaniciya isini yapmayan yarim dosyalar indirtir.

Bu yuzden ayni surum iki kayit olarak eklenir; `surumler` tablosunun
tekil kisiti (urun, surum, platform, paket_tur) buna izin verir.

`ortak` kayitlar KAPATILMAZ: sahada 1.2.x kurulu koprulerin guncelleme
denetimi `platform='ortak'` sorabilir. Eski kayitlar durur, yeni surum
platforma ozgu gelir.
"""
from __future__ import annotations

import sys

sys.path.insert(0, "/opt/goktungu/merkez/python")

import mk_depo  # noqa: E402

SURUM = "1.3.0"
NOTLAR = (
    "Kurulum yeniden yazildi. Windows: Program Files altina kurulum, "
    "Gorev Zamanlayici ile sistem baslangicinda otomatik calisma, "
    "Baslat menusu ve masaustu kisayollari (GOKTUNGU mavi ikonu), "
    "Program Ekle/Kaldir kaydi. Ubuntu: /opt/goktungu/kopru altina kurulum, "
    "systemd kullanici servisi, uygulama menusu ve masaustu kisayolu. "
    "Her iki platformda yerinde yukseltme: servis durdurulur, dosyalar "
    "guncellenir, servis yeniden baslatilir; ayarlar ve merkez kaydi "
    "korunur. 1.2.0'daki Turkce karakterli yol hatasi (80070003) giderildi."
)

HEDEFLER = [
    ("windows", f"/tmp/goktungu-kopru-{SURUM}-windows.zip"),
    ("linux", f"/tmp/goktungu-kopru-{SURUM}-linux.tar.gz"),
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

    ortak = mk_depo.son_surum("kopru", platform="ortak", paket_tur="tam")
    if ortak:
        print(f"  {'ortak':8s} son surum: {ortak.get('surum')} "
              f"(eski kurulumlar icin korundu)")

    return 0 if basarili == len(HEDEFLER) else 1


if __name__ == "__main__":
    sys.exit(main())
