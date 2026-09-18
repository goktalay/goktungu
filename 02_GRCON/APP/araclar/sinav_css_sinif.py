#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GOKTUNGU GCS - CSS sinif butunluk denetimi (v2.4.33'te eklendi)

NEDEN VAR:
v2.4.32'de widget_pusula.js ve widget_konum.js yazildi ama bu
dosyalarin kullandigi CSS siniflari hic yazilmadi. Sonuc:
  - pusula: SVG <circle> varsayilan fill=BLACK -> ortada siyah daire
  - konum : bicimsiz metin akisi
  - hava  : kirmizi yenile dugmesi duz metin
Bu kusur sinifi TAMAMEN SESSIZDIR: konsola tek satir hata yazmaz,
sunucu 200 doner, sozdizimi denetimi gecer. Yalnizca goz denetimiyle
ya da bu betikle yakalanir.

NE YAPAR:
JS ve HTML dosyalarinda uretilen CSS siniflarini toplar, CSS
dosyalarinda tanimli sinif kumesiyle karsilastirir, tanimsiz olanlari
bildirir.

KULLANIM:
  python3 araclar/sinav_css_sinif.py [proje_dizini]
Cikis kodu: 0 = temiz, 1 = tanimsiz sinif var
"""

import os
import re
import sys

# Bu on eklere sahip siniflar denetlenir. Cerceve/kutuphane siniflari
# (fa-, cesium-, leaflet-) ve tek kullanimlik yardimcilar disaridadir.
DENETLENEN_ONEK = (
    "pusula-", "konum-", "hava-", "saat-", "widget-",
    "bag-", "dron-", "kam-", "rota-", "hedef-", "radar-",
    "msj-", "pilot-", "bolum-", "sekme-", "dok-", "pfd-",
    # v2.4.34: dron kartinin sinif ailesi (dk-*) listede YOKTU.
    # Sonuc: 128 kullanim denetim disi kaldi ve dk-baslik-ozet /
    # dk-ozet-irt / dk-ozet-kip kurallarinin hic yazilmadigi
    # gozden kacti. Kullanici baslikta "30 mGUIDED" bitismesini
    # bildirdi. Onek eklendi.
    "dk-", "sayac-",
    # v2.4.34: Sistem Kaynaklari widget'inin sinif ailesi.
    "kyn-", "sg-",
)

# Bu onekleri tasiyan siniflar denetim disi (dis kutuphane / ikon seti)
DIS_ONEK = ("fa-", "fas", "far", "fab", "cesium", "leaflet", "ol-")

# ------------------------------------------------------------------
# BILINEN YANLIS POZITIFLER (v2.4.33'te tek tek incelenip dogrulandi)
# ------------------------------------------------------------------
# Bu betik statik desen taramasi yapar; asagidaki durumlari ayirt
# edemez. Her biri elle incelenmis, GORSEL KUSUR URETMEDIGI
# dogrulanmistir. Gerekce olmadan bu listeye ekleme YAPILMAMALIDIR:
# aksi halde denetim gercek kusurlari da gizlemeye baslar.
YANLIS_POZITIF = {
    # Calisma aninda birlestirilen onekler: kaynakta "bag-tur-" + tip
    # yazilir; gercek sinif adi (bag-tur-seri, bag-tur-tcp ...) CSS'te
    # tanimlidir. Betik dize birlestirmesini cozemez.
    "bag-tur-": "calisma aninda birlestirilen onek (bag-tur- + tip)",
    "kam-prot-": "calisma aninda birlestirilen onek (kam-prot- + protokol)",
    "dok-": "calisma aninda birlestirilen onek",
    # Yalnizca yerlesim kabi; gorsel bicimi ic ogelerden gelir.
    "bag-tur-alan": "yalnizca form alani kabi, bicimi giris ogelerinden gelir",
    "bag-tur-dji": "rozet metni; renk .bag-tur ortak kuralindan gelir",
    # Bagimsiz sinav sayfalari (uretim arayuzunde kullanilmaz)
    "bolum-baslik": "sinav_widget.html sayfasina ozgu, uretimde yok",
    "bolum-govde": "sinav_widget.html sayfasina ozgu, uretimde yok",
    # Geometri/bicim ust siniftan devralinir
    "dok-bolme-ad": "bicim .dok-bolme-baslik ic secicilerinden gelir",
    "dok-bolme-coz": "bicim .dok-bolme-baslik ic secicilerinden gelir",
    "dok-sekmeli": "yalnizca JS durum isareti, gorsel kural gerektirmez",
    "kam-onizleme": "yalnizca JS secici kancasi, gorsel kural yok",
    "saat-dij-ss": "saniye alani; bicim .saat-dij ic secicisinden gelir",
    # dronlar.js:2648'de acikca belgelenmis: bicim .dk-pp-input'tan
    # gelir; bu ikinci sinif YALNIZCA secici cakismasini onlemek icin
    # (arama kutusu ile duzenleme alanini ayirt etmek) eklenmistir.
    "dk-pp-duzenle-input": "JS secici ayirt edici; bicim .dk-pp-input'tan gelir",
}

# Sinif adi cikarma desenleri
DESEN_CLASSNAME = re.compile(r'className\s*=\s*["\']([^"\']+)["\']')
DESEN_CLASS_ATTR = re.compile(r'class\s*=\s*["\']([^"\']+)["\']')
DESEN_CLASSLIST = re.compile(
    r'classList\.(?:add|remove|toggle|contains|replace)\(\s*([^)]*)\)'
)
DESEN_SETATTR = re.compile(
    r'setAttribute\(\s*["\']class["\']\s*,\s*["\']([^"\']+)["\']'
)
DESEN_DIZE = re.compile(r'["\']([^"\']+)["\']')
# CSS icindeki sinif secicileri
DESEN_CSS_SINIF = re.compile(r'\.(-?[_a-zA-Z][\w-]*)')


def dis_mi(ad: str) -> bool:
    return any(ad.startswith(o) for o in DIS_ONEK) or ad in ("fa", "fas", "far", "fab")


def denetlenir_mi(ad: str) -> bool:
    if dis_mi(ad):
        return False
    if ad in YANLIS_POZITIF:
        return False
    # Tire ile biten adlar dize birlestirmesinin yarim parcasidir
    # ("sayac-btn " + tip gibi). Gercek sinif adi calisma aninda olusur.
    if ad.endswith("-"):
        return False
    return any(ad.startswith(o) for o in DENETLENEN_ONEK)


def css_siniflarini_topla(css_dizin: str):
    """CSS dosyalarinda tanimli tum sinif adlarini dondurur."""
    tanimli = set()
    dosyalar = []
    if not os.path.isdir(css_dizin):
        return tanimli, dosyalar
    for ad in sorted(os.listdir(css_dizin)):
        if not ad.endswith(".css"):
            continue
        yol = os.path.join(css_dizin, ad)
        dosyalar.append(ad)
        with open(yol, encoding="utf-8", errors="replace") as f:
            metin = f.read()
        # Yorumlari kaldir: yorum icindeki ornek secici sayilmasin
        metin = re.sub(r'/\*.*?\*/', ' ', metin, flags=re.S)
        for m in DESEN_CSS_SINIF.finditer(metin):
            tanimli.add(m.group(1))
    return tanimli, dosyalar


def dize_siniflari(parca: str):
    """classList.add("a","b") gibi cok argumanli cagriyi coz."""
    bulunan = []
    for m in DESEN_DIZE.finditer(parca):
        for tek in m.group(1).split():
            bulunan.append(tek)
    return bulunan


def kaynak_siniflarini_topla(kok: str):
    """JS + HTML dosyalarinda uretilen siniflari (sinif -> {dosya:satir})."""
    kullanim = {}

    def kaydet(ad, dosya, satir):
        if not denetlenir_mi(ad):
            return
        kullanim.setdefault(ad, set()).add(f"{dosya}:{satir}")

    hedefler = []
    js_dizin = os.path.join(kok, "js")
    if os.path.isdir(js_dizin):
        for ad in sorted(os.listdir(js_dizin)):
            if ad.endswith(".js"):
                hedefler.append(os.path.join(js_dizin, ad))
    for ad in sorted(os.listdir(kok)):
        if ad.endswith(".html"):
            hedefler.append(os.path.join(kok, ad))

    for yol in hedefler:
        gorunen = os.path.relpath(yol, kok)
        with open(yol, encoding="utf-8", errors="replace") as f:
            satirlar = f.readlines()
        for no, satir in enumerate(satirlar, 1):
            for m in DESEN_CLASSNAME.finditer(satir):
                for tek in m.group(1).split():
                    kaydet(tek, gorunen, no)
            for m in DESEN_CLASS_ATTR.finditer(satir):
                for tek in m.group(1).split():
                    kaydet(tek, gorunen, no)
            for m in DESEN_SETATTR.finditer(satir):
                for tek in m.group(1).split():
                    kaydet(tek, gorunen, no)
            for m in DESEN_CLASSLIST.finditer(satir):
                for tek in dize_siniflari(m.group(1)):
                    kaydet(tek, gorunen, no)
    return kullanim


def main():
    kok = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "goktungu"
    )
    kok = os.path.abspath(kok)
    if not os.path.isdir(kok):
        print(f"HATA: proje dizini yok: {kok}")
        return 2

    css_dizin = os.path.join(kok, "css")
    tanimli, css_dosyalari = css_siniflarini_topla(css_dizin)
    kullanim = kaynak_siniflarini_topla(kok)

    print("=" * 66)
    print("  GOKTUNGU CSS SINIF BUTUNLUK DENETIMI")
    print("=" * 66)
    print(f"Proje       : {kok}")
    print(f"CSS dosyasi : {len(css_dosyalari)} ({', '.join(css_dosyalari)})")
    print(f"Tanimli sinif: {len(tanimli)}")
    print(f"Denetlenen kullanim: {len(kullanim)}")
    print(f"Bilinen yanlis pozitif (denetim disi): {len(YANLIS_POZITIF)}")
    print("-" * 66)

    eksik = {ad: yerler for ad, yerler in kullanim.items() if ad not in tanimli}

    if not eksik:
        print("SONUC: TEMIZ - JS/HTML'de uretilen tum siniflar CSS'te tanimli.")
        print("=" * 66)
        return 0

    print(f"SONUC: {len(eksik)} TANIMSIZ SINIF BULUNDU")
    print()
    # Onege gore grupla, okunur cikti
    for ad in sorted(eksik):
        yerler = sorted(eksik[ad])
        ilk = ", ".join(yerler[:3])
        artik = f" (+{len(yerler) - 3})" if len(yerler) > 3 else ""
        print(f"  EKSIK  .{ad}")
        print(f"         kullanim: {ilk}{artik}")
    print()
    print("Bu siniflar CSS'te tanimli degil. SVG ogeleri icin bu durum")
    print("SESSIZ GORSEL KUSUR uretir (circle fill varsayilani siyahtir).")
    print("=" * 66)
    return 1


if __name__ == "__main__":
    sys.exit(main())
