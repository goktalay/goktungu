#!/usr/bin/env python3.11
"""Kopru v1.4.4'u merkez depoya ekler (setup.exe + .deb).

MERKEZDE calisir: /opt/goktungu/merkez/python/

1.4.4'TE NE DEGISTI
-------------------
Kullanici bildirimi iki saha donanimi icin ayni kusuru gosteriyordu:

    "GCS icinde kopru kurulu olan makinede porta baglanmali, sanirim su
     an sunucu da ariyor portu, GCS bilgisayarinda aslinda ttyACM0 var"
    "radarda da ayni sorun var, radarin kopru yazilimi calisiyor ama
     sistem radari sunucuda ariyor"

Kok neden: GCCDUAL cantasi ve C20 radari icin seri port / TCP oturumu
MERKEZ sunucuda aciliyordu. Merkez sunucu bir veri merkezindedir; ne
cantanin `/dev/ttyACM0` aygitini ne de radarin yerel agdaki
`192.168.8.186:5001` adresini gorur. Donanim sahadaki kopru
makinesindeyken oturumun merkezde acilmasi tanim geregi basarisizdir.

Duzeltme: iki donanimin da oturumu artik SAHADA, koprunun kurulu
oldugu makinede kurulur.

  * C20 radar istemcisi (protokol, CRC, cerceveleme, iz cozumlemesi)
    merkezden kopruye TASINDI; koprude `radar` servisi olarak kosar.
  * GCCDUAL seri oturumu koprude kosar; panel komutlari (baglan, kes,
    LED, joystick esiği) dosya tabanli iki yonlu kanaldan servise
    iletilir.
  * Merkez artik radar icin bir VEKIL tutar: koprunun bildirdigi durum,
    izler ve radar konumunu panele sunar, panel komutlarini ilgili
    kopruye yonlendirir.
  * Panelde kopru secicisi vardir: birden fazla kopru bagliysa komutun
    hangi sahaya gidecegi secilir.
  * Izler mutlak zaman damgasi yerine GORELI yas (`yas_sn`) ile
    tasinir; iki makinenin saati farkliysa izler ne aninda eskir ne de
    haritada sonsuza kadar kalir.
  * Radar susarsa (kablo cikar, radar kapanir, ag kopar) izler zamana
    bagli olarak silinir; haritada hayalet hedef kalmaz.

Olculdu: koprude 190 olcum (modul yolu 25, yorumlayici 20, GCCDUAL
kanali 83, radar C20 uctan uca 62) ve kurulu paket uzerinde 32 canli
olcum; merkezde 148 olcum (GCCDUAL yonlendirme 52, radar yonlendirme
35, radar vekili 61) ve arayuzde 58 olcum. Tumu gecti.

Radar olcumunun sanal C20 sunucusu, cerceveleme ve CRC islevlerini
urun kodundan ithal eder; kendi protokolunu yazarsa iki taraf da yanlis
olsa bile olcum gecerdi.

Paket kayitlari yine iki platform olarak eklenir; eski platform ve
`ortak` kayitlari KAPATILMAZ, cunku sahadaki 1.2.x/1.3.x kopruler
guncelleme denetiminde eski kayitlari sorabilir.
"""
from __future__ import annotations

import sys

sys.path.insert(0, "/opt/goktungu/merkez/python")

import mk_depo  # noqa: E402

SURUM = "1.4.4"

NOTLAR = (
    "KUSUR GIDERILDI: saha donanimlarinin komutlari artik merkez "
    "sunucuya degil, koprunun kurulu oldugu makineye gidiyor. "
    "Onceki surumlerde Yer Kontrol Istasyonu Dual (GCCDUAL) cantasinin "
    "seri portu ve C20 radarinin TCP oturumu MERKEZ sunucuda acilmaya "
    "calisiliyordu; merkez sunucu ne cantanin /dev/ttyACM0 aygitini ne "
    "de radarin yerel agdaki adresini gordugu icin baglanti hicbir "
    "zaman kurulamiyordu. C20 radar protokolu (oturum acma, register "
    "okuma/yazma, RTK konumu, hedef izleri) tumuyle kopruye tasindi ve "
    "koprude Radar sunucusu olarak kosuyor; GCCDUAL seri oturumu da "
    "koprude kosuyor. Panelden verilen komutlar (baglan, kes, ayar "
    "oku/yaz, RTK, LED, joystick) iki yonlu kanaldan sahadaki servise "
    "iletiliyor. Birden fazla kopru bagliysa panelde komutun hangi "
    "sahaya gidecegini seciyorsunuz. Hedef izleri artik goreli yas ile "
    "tasindigi icin saha bilgisayarinin saati merkezden farkli olsa "
    "bile izler ne aninda kayboluyor ne de haritada asili kaliyor; "
    "radar susarsa (kablo cikar, radar kapanir, ag kopar) izler "
    "otomatik siliniyor, haritada hayalet hedef kalmiyor. "
    "Windows: GOKTUNGU-Kopru-Setup.exe sihirbazi, Python 3.11 gomulu, "
    "C:\\Program Files\\Goktungu\\Kopru altina kurulur, services.msc'de "
    "gorunen gercek Windows servisi. Ubuntu: goktungu-kopru.deb, systemd "
    "sistem servisi. Yukseltme yerinde yapilir: servis durdurulur, "
    "dosyalar guncellenir, servis baslatilir; ayarlar ve merkez kaydi "
    "korunur."
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
