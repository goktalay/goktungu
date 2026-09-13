# -*- coding: utf-8 -*-
"""Kopru v1.5.1'i merkez depoya ekler (setup.exe + .deb).

1.5.1'TE NE DEGISTI
-------------------
Kamera (video) ve AI zincirinde de v1.4.3/v1.4.4 ile radar ve GCCDUAL'de
giderilen kusurun AYNISI vardi: is MERKEZ SUNUCUDA yapiliyordu.

  * Kamera akisini merkez sureci aciyordu -> saha agindaki kameralar
    (192.168.x.x) ve USB kameralar hicbir kosulda acilamiyordu.
  * 'Yerel kameralari tara' merkez sunucuda cv2.VideoCapture(0..5)
    kosuyordu -> merkezde kamera aygiti olmadigi icin liste HER ZAMAN
    bostu.
  * AI izleme atama ve saglik yoklamasi merkezden saha AI bilgisayarina
    HTTP istegi atiyordu -> zaman asimi; AI sunucusu surekli 'yanit
    vermiyor' gorunuyordu.
  * AI iscisine verilen goruntu adresi merkezi gosteriyordu -> isci o
    adrese erisemiyordu; zincir ikinci noktadan da kopuyordu.

Bu surumde kamera baglantisi, cihaz taramasi, AI yoklamasi ve gorev
atamasi tumuyle kopruye tasindi. Goruntu yerel agda kalir; merkeze kare
GONDERILMEZ, yalnizca akis durumu ozeti bildirilir.

Kullanim (MERKEZ SUNUCUDA):
    python3.11 yayinla_150.py
"""
import sys

sys.path.insert(0, "/opt/goktungu/merkez/python")

import mk_depo  # noqa: E402

SURUM = "1.5.1"

NOTLAR = (
    "KUSUR GIDERILDI: kamera ve AI islemleri artik merkez sunucuda "
    "degil, koprunun kurulu oldugu makinede yapiliyor. Onceki "
    "surumlerde kamera baglantisini (RTSP/MJPEG/USB) ve AI izleme "
    "isteklerini MERKEZ sunucu kuruyordu; merkez bir veri merkezinde "
    "oldugu ve pilotun yerel agini gormedigi icin 192.168.x.x "
    "adresindeki kameralar ile AI bilgisayarlari hicbir zaman "
    "erisilemiyordu. Yalnizca internete acik kameralar calisiyor, bu da "
    "kusuru gizliyordu. "
    "Kamera baglantisi artik sahada aciliyor ve goruntu yerel agda "
    "kaliyor: merkeze kare TASINMAZ, yalnizca akisin acik olup "
    "olmadigi, izleyici sayisi ve kare sayaci bildirilir. "
    "'Yerel kameralari tara' dugmesi artik gercekten bu makinedeki "
    "kameralari listeler; onceden merkezde tarandigi icin liste her "
    "zaman bos donuyordu. Yerel USB kamera icin OpenCV gerekir, kurulu "
    "degilse kurulum komutu bildirilir; ag kameralari OpenCV olmadan "
    "da calisir. "
    "AI izleme gorevleri ve saglik yoklamasi da bu makineden yapiliyor; "
    "AI iscisine verilen goruntu adresi artik yerel adrestir. Bir AI "
    "bilgisayari duserse gorevi cevrimici olan diger isciye tasinir; "
    "onceden kamera sessizce izlemesiz kalirdi. Kamera acilamazsa "
    "sebebi bildirilir (adres, kimlik dogrulama, ffmpeg eksik, kaynak "
    "kare uretmiyor). "
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
