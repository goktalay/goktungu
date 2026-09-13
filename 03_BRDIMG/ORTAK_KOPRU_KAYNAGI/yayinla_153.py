# -*- coding: utf-8 -*-
"""Kopru v1.5.3'i merkez depoya ekler (setup.exe + .deb).

1.5.3'TE NE DEGISTI
-------------------
Panel v1.5.2'den beri aga acik (0.0.0.0) calisiyor, ancak kurulum tani
araci ozetinde yalnizca 127.0.0.1 adresini yaziyordu. Kullanici paneli
baska bir bilgisayardan acmak istediginde makinenin ag adresini elle
bulmak zorunda kaliyordu. Tani araci artik ayni agdan girilecek gercek
adresi de yazar.

Kullanim (MERKEZ SUNUCUDA):
    python3.11 yayinla_153.py
"""
import sys

sys.path.insert(0, "/opt/goktungu/merkez/python")

import mk_depo  # noqa: E402

SURUM = "1.5.3"

NOTLAR = (
    "PANEL AG UZERINDEN ACILABILIYOR (v1.5.2 ile geldi, bu surumde "
    "tamamlandi). Yerel panel yalnizca kurulu oldugu bilgisayardan "
    "(127.0.0.1) erisilebiliyordu; artik varsayilan olarak tum ag "
    "arayuzlerini dinler (0.0.0.0), boylece ayni agdaki baska bir "
    "bilgisayardan veya tabletten de acilabilir. Ayar dosyasinda "
    "127.0.0.1 yazili mevcut kurulumlar yukseltmede otomatik olarak "
    "aga acilir; elle baska bir adres yazilmissa o adres KORUNUR. "
    "TANI ARACI ARTIK AG ADRESINI DE YAZIYOR. Kurulumla gelen "
    "/opt/goktungu/kopru/tani_sifirla.sh ozeti yalnizca 127.0.0.1 "
    "adresini veriyordu; artik ayni agdaki baska bir bilgisayardan "
    "girilecek gercek adres (ornek: http://192.168.1.40:8790/) de "
    "ayrica gosterilir. Kurulum bittiginde de her iki adres yazilir. "
    "AGA ACIK PANELDE KURULUM BILGISI SIZDIRILMIYOR. Giris yapmadan "
    "sorulan durum bilgisinde kurulum kimligi, firma adi ve e-posta "
    "yalnizca ayni bilgisayardan gorunur. Servisleri yonetmek icin "
    "merkez girisi zorunludur; merkeze kayit ve ayar yazma gibi kalici "
    "islemler ise YALNIZ koprunun kurulu oldugu bilgisayardan "
    "yapilabilir. Erisimi tek bir aga sinirlamak icin guvenlik duvari "
    "kurali onerilir; yalniz bu bilgisayardan erisim istenirse panel "
    "ayarlarindaki 'Panel arayuzu' alanina 127.0.0.1 yazilir. "
    "UBUNTU'DA SERVIS OLUSMAMA SORUNU GIDERILDI. Eski kur.sh ile "
    "kurulmus kullanici servisi ayni adi tasidigi icin yeni sistem "
    "servisiyle ayni porta giriyordu; kurulum artik bu kalintiyi "
    "otomatik devre disi birakir. Servis kaydi veya baslatma "
    "basarisiz olursa kurulum bunu acikca yazar. Not: "
    "'service --status-all' YALNIZCA SysV betiklerini listeler ve bu "
    "servisi ASLA gostermez; dogru komut 'systemctl status "
    "goktungu-kopru'dur. "
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
