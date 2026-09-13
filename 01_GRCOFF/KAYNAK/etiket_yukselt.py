#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""Betik/stil onbellek etiketlerini (?v=vXXXX) tek surume hizalar.

## NEDEN GEREKLI

Tarayici `js/i18n.js?v=v2453` adresini bir kez indirip onbellege alir.
Dosya sunucuda degisse bile adres AYNI kaldigi surece tarayici eski
kopyayi kullanmaya devam eder. Bu yuzden her surumde etiket artirilir.

Kusur: `video.html` v2453'te kalmisti, `index.html` ise v2461'e
tasinmisti. Ayni `i18n.js` dosyasi iki farkli adresten sunuldugu icin
video duvari sayfasi ESKI ceviri sozlugunu kullaniyordu; yeni eklenen
metinler orada gorunmuyordu.

Elle duzeltmek guvenilmezdir: etiket sayisi dosya basina onlarcadir ve
biri atlanirsa kusur sessizce surer. Bu betik hepsini olcerek hizalar.
"""
import os
import re
import sys

KOK = os.path.dirname(os.path.abspath(__file__))
DESEN = re.compile(r"\?v=v[0-9]+")


def surum_etiketi():
    """js/surum.js icindeki GCS_SURUM degerinden etiket uretir."""
    yol = os.path.join(KOK, "js", "surum.js")
    with open(yol, encoding="utf-8") as f:
        m = re.search(r'GCS_SURUM\s*=\s*["\']([0-9][0-9.]*)["\']',
                      f.read(2048))
    if not m:
        raise SystemExit("GCS_SURUM okunamadi: %s" % yol)
    return "v" + m.group(1).replace(".", ""), m.group(1)


def main():
    etiket, surum = surum_etiketi()
    yeni = "?v=" + etiket
    print("Hedef surum: %s  ->  etiket: %s" % (surum, etiket))

    hedefler = []
    for dizin, altlar, dosyalar in os.walk(KOK):
        # Uretim disi ve buyuk dizinleri atla: node_modules ve
        # harita_cache binlerce dosya icerir ve taramayi kilitler.
        #
        # `gomulu_merkez/calisma` ise Windows paketine gomulen UCUNCU
        # TARAF Python dagitimidir (win32com belgeleri dahil).  Bu
        # dosyalar bizim degildir, onbellek etiketi tasimazlar ve bir
        # kismi UTF-8 DEGILDIR: taranmaya kalkilinca betik
        # `UnicodeDecodeError` ile coker ve hicbir dosya hizalanmaz.
        # OLCULDU (2026-08-16): 5 dosya cp1252 kodlu.
        altlar[:] = [a for a in altlar
                     if a not in ("node_modules", "__pycache__",
                                  "harita_cache", "veri", "sitl",
                                  "dron_loglari", "ai_kayitlar",
                                  "ai_modeller", "ai_yuzler", "avatars",
                                  ".git", "gomulu_merkez", "site-packages")]
        for d in dosyalar:
            if d.endswith(".html"):
                hedefler.append(os.path.join(dizin, d))

    degisen = 0
    atlanan = []
    for yol in sorted(hedefler):
        # UTF-8 olmayan bir dosya betigi CIKARMAMALI: aksi halde o
        # dosyadan SONRAKI tum hedefler hizalanmadan kalir ve kusur
        # sessizce surer (etiket_yukselt.py'nin var olma nedeni tam
        # olarak bu tur sessiz atlamalardir).
        try:
            with open(yol, encoding="utf-8") as f:
                metin = f.read()
        except UnicodeDecodeError:
            atlanan.append(os.path.relpath(yol, KOK))
            continue
        eski = set(DESEN.findall(metin))
        if not eski:
            continue
        yeni_metin = DESEN.sub(yeni, metin)
        bagil = os.path.relpath(yol, KOK)
        if yeni_metin != metin:
            with open(yol, "w", encoding="utf-8") as f:
                f.write(yeni_metin)
            degisen += 1
            print("  GUNCEL  %-28s %s -> %s"
                  % (bagil, ",".join(sorted(eski)), yeni))
        else:
            print("  ZATEN   %-28s %s" % (bagil, yeni))

    print("\n%d dosya guncellendi." % degisen)
    if atlanan:
        print("UTF-8 olmadigi icin atlanan (ucuncu taraf, etiket "
              "tasimaz): %d dosya" % len(atlanan))
        for a in atlanan:
            print("    %s" % a)

    # DOGRULAMA: hicbir dosyada baska etiket kalmamali.
    kalan = {}
    for yol in hedefler:
        try:
            with open(yol, encoding="utf-8") as f:
                icerik = f.read()
        except UnicodeDecodeError:
            continue
        for e in set(DESEN.findall(icerik)):
            if e != yeni:
                kalan.setdefault(os.path.relpath(yol, KOK),
                                 set()).add(e)
    if kalan:
        print("\nHATA - hizalanmamis etiketler kaldi:")
        for k, v in kalan.items():
            print("  %s: %s" % (k, ", ".join(sorted(v))))
        return 1
    print("Dogrulama TAMAM: tum etiketler %s" % yeni)
    return 0


if __name__ == "__main__":
    sys.exit(main())
