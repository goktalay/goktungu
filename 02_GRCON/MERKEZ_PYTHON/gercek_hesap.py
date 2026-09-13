#!/usr/bin/env python3.11
# =================================================================
# GOKTUNGU MERKEZ - gercek kullanici hesabini olustur
# Kullanicinin sahada kullandigi hesap (Gokkubbe Teknoloji) merkeze
# eklenir; boylece GCS'in "acik sunucular" akisi gercek kimlikle
# uctan uca sinanir. Ornek veri hesaplari @ornek.local uzantilidir
# ve bu hesapla karismaz.
# =================================================================
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mk_db as db      # noqa: E402
import mk_api as api    # noqa: E402
import mk_role as role  # noqa: E402

EPOSTA = "mkaderoglu@gokkubbetech.com"
# GUVENLIK (BULGU_05): parola kaynak kodda DUZ METIN durmaz.
# Ayni deger sunucunun SSH root parolasiydi.
# Varsayilan deger YOKTUR: konursa parola yine kodda kalir.
GOKTUNGU_SINAV_SIFRE = os.environ.get("GOKTUNGU_SINAV_SIFRE", "")
if not GOKTUNGU_SINAV_SIFRE:
    raise SystemExit("HATA: GOKTUNGU_SINAV_SIFRE ortam degiskeni bos. "
                     "Bu betik gercek bir hesap sifresi kullanir; "
                     "sifre kaynak kodda tutulmaz.")
SIFRE = GOKTUNGU_SINAV_SIFRE
UNVAN = "Gökkubbe Teknoloji Anonim Şirketi"
KISA = "GÖKKUBBE TEK"


def firma_bul_veya_ekle() -> int:
    k = db.tek("SELECT firma_id FROM firmalar WHERE kisa_ad = %s", (KISA,))
    if k:
        return int(k["firma_id"])
    fid, hata = api.firma_ekle({
        "unvan": UNVAN,
        "kisa_ad": KISA,
        "vergi_no": "0000000000",
        "adres": "Sincan, Ankara, Türkiye",
        "telefon": "+90 312 000 00 00",
        "eposta": "info@gokkubbetech.com",
        "abonelik": "kurumsal",
        "maks_kullanici": 100,
        "maks_sunucu": 20,
    })
    if hata:
        raise SystemExit(f"firma eklenemedi: {hata}")
    return int(fid)


def kullanici_bul_veya_ekle(firma_id: int) -> int:
    k = db.tek("SELECT kullanici_id FROM kullanicilar WHERE eposta = %s",
               (EPOSTA,))
    if k:
        return int(k["kullanici_id"])
    kid, hata = api.kullanici_ekle({
        "firma_id": firma_id,
        "eposta": EPOSTA,
        "sifre": SIFRE,
        "ad_soyad": "Muhammed Kaderoğlu",
        "rol": "firma_yonetici",
        "telefon": "+90 312 000 00 00",
        "pilot_lisans": "TR-SHGM-0001",
    })
    if hata:
        raise SystemExit(f"kullanici eklenemedi: {hata}")
    return int(kid)


def sunucu_bul_veya_ekle(firma_id: int, ad: str) -> dict:
    k = db.tek("SELECT kurulum_uid FROM sunucu_ornekleri "
               "WHERE firma_id = %s AND ad = %s", (firma_id, ad))
    if k:
        return {"kurulum_uid": k["kurulum_uid"], "gizli": None}
    kayit, hata = role.ornek_kaydet(firma_id, ad,
                                   "Saha GCS kurulumu (ASUS Ascent GX10)")
    if hata:
        raise SystemExit(f"sunucu eklenemedi: {hata}")
    return kayit


def main() -> int:
    fid = firma_bul_veya_ekle()
    kid = kullanici_bul_veya_ekle(fid)
    print(f"firma_id={fid} kullanici_id={kid} eposta={EPOSTA}")
    for ad in ("Sincan Saha GCS", "Ankara Merkez GCS"):
        kayit = sunucu_bul_veya_ekle(fid, ad)
        gizli = kayit.get("gizli")
        print(f"  sunucu: {ad}")
        print(f"    kurulum_uid = {kayit['kurulum_uid']}")
        if gizli:
            print(f"    gizli       = {gizli}   (YALNIZ BIR KEZ GORUNUR)")
        else:
            print("    gizli       = (zaten kayitli; yeniden uretilmedi)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
