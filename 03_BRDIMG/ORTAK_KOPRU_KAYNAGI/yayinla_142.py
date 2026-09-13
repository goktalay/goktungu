#!/usr/bin/env python3.11
"""Kopru v1.4.2'yi merkez depoya ekler (setup.exe + .deb).

MERKEZDE calisir: /opt/goktungu/merkez/python/

1.4.2'DE NE DEGISTI
-------------------
v1.4.1 alt servislerin YANLIS YORUMLAYICIYLA baslatilmasini gidermisti
(pywin32 barindiricisi bir Python yorumlayicisi degildir). Sahada bir
sonraki katman ortaya cikti: yorumlayici artik dogruydu ama kopru
yaziliminin kendi paketini bulamiyordu.

    ModuleNotFoundError: No module named 'kopru'

Kok neden: setup icine gomulen Python dagitimi, yanindaki
`python311._pth` dosyasi yuzunden CPython'un "isolated" kipinde acilir.
O kipte PYTHONPATH ve calisma dizini YOK SAYILIR; arama yollari yalniz
`._pth` dosyasindan okunur. Kopru paket yolunu PYTHONPATH ile
verdiginden ayar hicbir etki yapmiyordu.

Duzeltme iki katmanli:

1. `._pth` dosyasina kurulum kokunu gosteren goreli satir yazilir
   (asil duzeltme; kurulum dizini tasinsa da gecerli kalir).
2. Alt servis baslatma komutu paket kokunu kendi icinde tasir
   (ikinci savunma; `._pth` bozuk/eksik olsa da servisler kalkar).
3. Setup, dosyalari yazdiktan sonra gercek yorumlayiciyla paket okuma
   denemesi yapar ve basarisizsa kullaniciya dosya yolunu bildirir.

Linux (.deb) tarafinda kullanilan PYTHONPATH yolu KALDIRILMADI; sistem
Python'unda calisan yol odur. Iki isletim sistemi de desteklenir.

Paket kayitlari yine iki platform olarak eklenir; eski platform ve
`ortak` kayitlari KAPATILMAZ, cunku sahadaki 1.2.x/1.3.x kopruler
guncelleme denetiminde eski kayitlari sorabilir.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "/opt/goktungu/merkez/python")

import mk_depo  # noqa: E402

SURUM = "1.4.2"

NOTLAR = (
    "KUSUR GIDERILDI: sunucular baslatilirken 'No module named kopru' "
    "hatasi veriyordu. Kurulumla gelen Python yalitilmis kipte "
    "calistigi icin kopru yaziliminin kendi dosyalarini bulamiyordu; "
    "bes sunucu (Dron, AI, Video, GroundGCC, Radar) BASLAT dugmesine "
    "basildiginda aninda sonlaniyordu. Kurulum koku artik Python "
    "yapilandirmasina yaziliyor, ayrica paket yolu baslatma komutuna da "
    "gomuluyor: yapilandirma bozuk veya eksik olsa bile sunucular ayaga "
    "kalkar. Kurulum programi dosyalari yazdiktan sonra kendini "
    "denetliyor ve sorun varsa hangi dosyanin bakilacagini soyluyor. "
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
