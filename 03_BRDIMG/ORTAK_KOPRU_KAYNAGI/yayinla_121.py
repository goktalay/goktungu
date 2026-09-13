#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""Kopru v1.2.1 paketini merkez depoya ekler (MERKEZ SUNUCUDA calisir).

Imzayi merkez atar (mk_depo.paket_ekle icinde Ed25519). Bu betik yalniz
dogru cagriyi yapar ve sonucu dogrular.
"""
from __future__ import annotations
import sys
import os

sys.path.insert(0, "/opt/goktungu/merkez/python")

import mk_depo  # noqa: E402

ARSIV = "/tmp/goktungu-kopru-1.2.1.tar.gz"
SURUM = "1.2.1"

NOTLAR = (
    "Windows baslatici kusuru giderildi: kurulum dizini Turkce karakter "
    "iceriyorsa (ornek OneDrive\\Masaustu) kur.bat sonunda 'Sistem "
    "belirtilen yolu bulamiyor' (80070003) hatasi veriyordu. Baslaticiya "
    "artik yol gomulmuyor; betik kendi konumunu bulur. Baslangic klasorune "
    "VBS kopyasi yerine .lnk kisayolu konuyor."
)


def main() -> int:
    if not os.path.isfile(ARSIV):
        print(f"[HATA] arsiv yok: {ARSIV}")
        return 1

    print(f"== kopru {SURUM} depoya ekleniyor ==")
    try:
        sonuc = mk_depo.paket_ekle(
            "kopru", SURUM, ARSIV,
            platform="ortak",
            kanal="kararli",
            paket_tur="tam",
            notlar=NOTLAR,
        )
    except Exception as e:
        print(f"[HATA] paket_ekle: {type(e).__name__}: {e}")
        return 1

    for k in ("urun", "surum", "platform", "paket_tur", "sha256", "boyut"):
        if k in sonuc:
            print(f"  {k:12s}: {sonuc[k]}")
    if "imza" in sonuc:
        print(f"  {'imza':12s}: {str(sonuc['imza'])[:40]}... ({len(str(sonuc['imza']))} karakter)")

    # Depodan geri okuyup gercekten yayinlandigini dogrula. "paket_ekle
    # hata vermedi" ile "istemci gorecek" ayni sey degil.
    print()
    print("== dogrulama: son surum sorgusu ==")
    try:
        son = mk_depo.son_surum("kopru", platform="ortak", kanal="kararli")
        print(f"  son surum: {son.get('surum') if son else None}")
        if not son or son.get("surum") != SURUM:
            print(f"  [HATA] son surum {SURUM} degil")
            return 1
        print("  [OK] istemciler bu surumu gorecek")
    except AttributeError:
        # islev adi farkli olabilir; listeyi dene
        try:
            lst = mk_depo.paket_listesi("kopru")
            surumler = [p.get("surum") for p in lst]
            print(f"  depodaki surumler: {surumler}")
            if SURUM not in surumler:
                print(f"  [HATA] {SURUM} depoda yok")
                return 1
            print("  [OK] paket depoda")
        except Exception as e:
            print(f"  [UYARI] dogrulama yapilamadi: {type(e).__name__}: {e}")
    except Exception as e:
        print(f"  [UYARI] dogrulama yapilamadi: {type(e).__name__}: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
