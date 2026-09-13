#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""GOKTUNGU Kopru v1.6.0 — depo yayin betigi.

NEDEN BU SURUM: Urun adi GOKTUNGU oldu. Eski ad, kullanicinin gordugu
her yuzeyden kaldirildi: Windows denetim masasindaki kayit adi,
services.msc'deki servis gorunen adi ve aciklamasi, Linux uygulama
menusu girdisi (TR ve EN), Debian paket aciklamasi, kurulum
sihirbazinin bilesen adi, kisayol ipuclari, yerel panelin sekme
basligi, ust seritteki marka yazisi ve Hakkinda penceresi.

Firma logosu TUMUYLE KALDIRILDI; yalniz GOKTUNGU urun logosu
kullaniliyor. Firma unvani artik yalnizca Hakkinda penceresindeki
sahiplik satirinda gorunuyor.

YUKSELTME YOLU KORUNDU: paket adi (goktungu-kopru), Windows servis adi
(GoktunguKopru), kaldirma ve ayar kayit anahtarlari, kurulum dizinleri ve
ortam degiskenleri DEGISMEDI. Bunlar marka degil kimliktir; paket adi
degistirilse apt yukseltme yerine ikinci bir paket kurar ve iki servis
ayni portu dinlemeye calisirdi.

Kullanim (MERKEZ SUNUCUDA):
    python3.11 yayinla_160.py
"""
import sys

sys.path.insert(0, "/opt/goktungu/merkez/python")

import mk_depo  # noqa: E402

SURUM = "1.6.0"

NOTLAR = (
    "URUN ADI GOKTUNGU OLDU. Yazilimin adi degisti ve eski ad "
    "kullanicinin gordugu her yerden kaldirildi: Windows Program "
    "Ekle/Kaldir listesindeki kayit, services.msc'de gorunen servis "
    "adi ve aciklamasi, Linux uygulama menusu girdisi (Turkce ve "
    "Ingilizce), Debian paket aciklamasi, kurulum sihirbazinin "
    "bilesen adi, Baslat menusu ve masaustu kisayol ipuclari, yerel "
    "panelin sekme basligi, ust seritteki marka yazisi ve Hakkinda "
    "penceresi. Kurulum dosyasinin adi da GOKTUNGU-Kopru-Setup "
    "oldu. "
    "FIRMA LOGOSU KALDIRILDI. Panelde artik yalnizca GOKTUNGU urun "
    "logosu var. Firma unvani tek bir yerde, Hakkinda penceresindeki "
    "sahiplik satirinda gorunuyor: Gokkubbe Teknoloji Anonim "
    "Sirketi. Mavi urun ikonu KORUNDU. "
    "MEVCUT KURULUMLAR DOGRUDAN YUKSELTILIR. Paket adi, Windows "
    "servis adi, kayit anahtarlari ve kurulum dizinleri BILINCLI "
    "OLARAK DEGISTIRILMEDI. Bunlar marka degil kimliktir: paket adi "
    "degistirilseydi apt yukseltme yapmak yerine ikinci bir paket "
    "kurar ve iki servis ayni portu dinlemeye calisirdi; servis adi "
    "degistirilseydi eski servis sistemde asili kalirdi; kayit "
    "anahtari degistirilseydi onceki kurulum denetim masasindan "
    "kaldirilamaz hale gelirdi. Bu yuzden kurulu koprulerinizi "
    "kaldirmaniz gerekmez: yeni kurulumu uzerine calistirmak "
    "yeterlidir. Ayarlar, merkez kaydi ve kimlik bilgileri korunur. "
    "PAKET KUNYESI GOKKUBBE OLARAK GUNCELLENDI. Windows kurulumunun "
    "yayimci alani ve Debian paketinin bakimci alani artik Gokkubbe "
    "Teknoloji Anonim Sirketi kunyesini tasiyor. "
    "UYGULAMA MENUSU ARAMASI ESKI ADI DA TANIR. Linux uygulama "
    "menusunde eski adla arama yapan kullanici koprüyu bulmaya devam "
    "eder; arama anahtarlarina yeni ad eklendi, eski ad korundu. "
    "INDIRME KURALI DEGISMEDI: kurulum paketleri tanitim sitesinden "
    "dogrudan verilmez; yalnizca kurumsal panelden oturum acarak "
    "indirilir. "
    "Windows: GOKTUNGU-Kopru-Setup.exe sihirbazi, Python 3.11 "
    "gomulu, C:\\Program Files\\Goktungu\\Kopru altina kurulur, "
    "services.msc'de gorunen gercek Windows servisi. Ubuntu: "
    "goktungu-kopru.deb, systemd sistem servisi. Yukseltme yerinde "
    "yapilir: servis durdurulur, dosyalar guncellenir, servis "
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

    ortak = mk_depo.son_surum("kopru", platform="ortak", paket_tur="tam")
    print(f"  {'ortak':8s} son surum: "
          f"{ortak.get('surum') if ortak else '[KALDI] okunamadi'}")

    return 0 if basarili == len(HEDEFLER) else 1


if __name__ == "__main__":
    sys.exit(main())
