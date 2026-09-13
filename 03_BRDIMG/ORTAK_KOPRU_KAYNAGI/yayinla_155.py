# -*- coding: utf-8 -*-
"""Kopru v1.5.5'i merkez depoya ekler (setup.exe + .deb).

1.5.5'TE NE DEGISTI
-------------------
Kullanici bildirdi: "video sunucusunu baslatmaya calistigimda bu
uyarilari veriyor. normalde bilgisayarda ffmpeg kurulu windows ta".

Kok neden olculdu: kopru bir WINDOWS SERVISI olarak LocalSystem
hesabiyla calisir. O hesabin PATH degiskeni, kullanicinin oturum PATH'i
DEGILDIR; dolayisiyla kullanicinin konsolunda calisan ffmpeg servis
icin "yok" sayiliyordu. Kullanici kendi konsolunda denedigi icin kusur
uzun sure gorunmedi.

Cozum: ortak bir arac bulucu (kopru/arac_bul.py) olagan kurulum
konumlarini tarar, bulunan yolu kalici olarak saklar ve arac hicbir
yerde yoksa konsola isletim sistemine gore kurulum yonergesi yazar.
OpenCV ve numpy gomulu calisma zamanina eklendi; kullanicinin ayrica
Python paketi kurmasi gerekmez.

Kullanim (MERKEZ SUNUCUDA):
    python3.11 yayinla_155.py
"""

import sys

sys.path.insert(0, "/opt/goktungu/merkez/python")

import mk_depo  # noqa: E402

SURUM = "1.5.5"

NOTLAR = (
    "VIDEO SUNUCUSU ARTIK KURULU ffmpeg'i BULUYOR. Bilgisayarinizda "
    "ffmpeg kurulu olmasina ragmen video servisi 'ffmpeg bulunamadi' "
    "diyordu. Nedeni sudur: kopru bir WINDOWS SERVISI olarak "
    "LocalSystem hesabiyla calisir ve o hesabin PATH'i sizin oturum "
    "PATH'iniz DEGILDIR. Kendi konsolunuzda 'ffmpeg' yazip calistigini "
    "gorseniz bile servis onu goremiyordu. "
    "ARAC ARTIK OLAGAN KURULUM KONUMLARINDA DA ARANIYOR. Windows'ta "
    "Program Files, ProgramData, WinGet, Chocolatey, Scoop ve kullanici "
    "klasorleri; Ubuntu'da /usr/bin, /usr/local/bin, /snap/bin ve /opt "
    "taranir. Bulunan yol saklanir, sonraki acilislarda arama yeniden "
    "yapilmaz. Servisi yeniden baslatmaniz yeterlidir. "
    "ARAC GERCEKTEN YOKSA KONSOLDA NE YAPACAGINIZ YAZIYOR. Yalnizca "
    "'bulunamadi' demek yeterli degildi: hangi araci, nereye, hangi "
    "komutla kuracaginizi bilmiyordunuz. Video servisinin konsolunda "
    "artik isletim sisteminize uygun, kopyalanabilir kurulum komutu ve "
    "kurulumdan sonra servisi yeniden baslatmaniz gerektigi bildirilir. "
    "YEREL USB KAMERA ICIN GEREKEN OpenCV KURULUMLA BIRLIKTE GELIYOR. "
    "Onceden ayrica Python paketi kurmaniz gerekiyordu; kurmadiginizda "
    "yerel kamera hicbir kosulda acilamiyordu. Windows kurulumunda "
    "OpenCV ve numpy gomulu calisma zamaninin icindedir; yerel kamera "
    "ve AI tespit cizimi kurulumdan hemen sonra calisir. Bu nedenle "
    "setup dosyasinin boyutu bu surumde artmistir. "
    "AYNI KUSUR IKINCI BIR YERDE DE YASIYORDU: video vekili, servis "
    "ffmpeg'i bulsa bile ciplak 'ffmpeg' komutunu cagirmaya devam "
    "ediyordu. Vekil de ayni buluculara baglandi. "
    "MERKEZ TARAFINDA BU SURUMLE BIRLIKTE GELENLER (GCS v2.4.64): "
    "yeni olusturulan kullanicinin sisteme girememesi giderildi; "
    "ucus kayitlari artik pilota gore suzuluyor (TAKEOFF komutunu "
    "veren pilot ucusun sahibidir, yalnizca yonetici tum ucuslari "
    "gorur); rota noktalari arasindaki mesafe etiketi buyutuldu; "
    "ucus grafigi YAZDIR dugmesi calisiyor ve alt seride yer aliyor; "
    "ucus gecmisi oynaticisinda harita uzerine kare kod ve kayit "
    "paneli icin tam ekran dugmesi eklendi. "
    "RADAR DAVRANISI (v1.5.4) KORUNDU: servis kendi basina hicbir "
    "adrese baglanmaz, yalnizca merkezden gelen 'bu adrese baglan' "
    "komutuyla baglanir ve verilen adresi hatirlar. "
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
