#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""
KONTROL DENEYI: sinav_tek_kapi.py gercek kusurlari yakalıyor mu?
================================================================
Her enjeksiyon, kapatilan bir kapiyi YENIDEN ACAR. Sinav bunu
yakalamazsa sinav degersizdir.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

KOK = os.path.dirname(os.path.abspath(__file__))

# (ad, dosya, bul, degistir)
ENJEKSIYONLAR = [
    # --- SUNUCU: kapiyi yeniden ac ---
    ("S1 kullanici_ekle yeniden yazar",
     "goktungu/sunucu.py",
     'self.konsol("AUTH",\n                        "Kullanici ekleme istegi reddedildi (tek kapi): "',
     'self.kullanicilar.ekle(eposta, "x", "kullanici")\n            self.konsol("AUTH",\n                        "Kullanici ekleme istegi reddedildi (tek kapi): "'),

    ("S2 kullanici_guncelle baskasina izin verir",
     "goktungu/sunucu.py",
     "            if not kendisi_mi:",
     "            if False:"),

    ("S3 kullanici_guncelle rol alanini kabul eder",
     "goktungu/sunucu.py",
     '            if ("rol" in alanlar) or ("aktif" in alanlar):',
     "            if False:"),

    ("S4 rol komutlari basarili doner",
     "goktungu/sunucu.py",
     '"tip": "rol_islem", "basarili": False,',
     '"tip": "rol_islem", "basarili": True,'),

    ("S5 rol_listesi OKUMA ucu kaldirilir (asiri kisitlama)",
     "goktungu/sunucu.py",
     'elif komut == "rol_listesi"',
     'elif komut == "rol_listesi_KALDIRILDI"'),

    ("S6 kendi profil duzenlemesi de engellenir (asiri kisitlama)",
     "goktungu/sunucu.py",
     "            bulundu = self.kullanicilar.guncelle(hedef, alanlar)",
     "            bulundu = False  # guncelle cagrisi kaldirildi"),

    # --- ARAYUZ: kapiyi yeniden ac ---
    ("A1 index.html kullanici menusu geri gelir",
     "index.html",
     '  <div class="profil-menu-item" id="pmKurumsalPanel"',
     '  <div class="profil-menu-item" id="pmKullanicilar">X</div>\n  <div class="profil-menu-item" id="pmKurumsalPanel"'),

    ("A2 index.html rol yonetimi menusu geri gelir",
     "index.html",
     '  <div class="profil-menu-item" id="pmKurumsalPanel"',
     '  <div class="profil-menu-item" id="pmRolYonetimi">X</div>\n  <div class="profil-menu-item" id="pmKurumsalPanel"'),

    ("A3 btnKullanicilar DOM'dan kaldirilir (JS coker)",
     "index.html",
     'id="btnKullanicilar"',
     'id="btnKullanicilar_KALDIRILDI"'),

    ("A4 kullanici.js ekleme gonderimi geri gelir",
     "js/kullanici.js",
     "    // v2.4.65 TEK KAPI: kullanici_ekle komutu ARTIK gonderilmez.",
     '    ws.send(JSON.stringify({ tip: "kullanici_ekle" }));\n    // v2.4.65 TEK KAPI: kullanici_ekle komutu ARTIK gonderilmez.'),

    ("A5 kullanici.js guncelleme gonderimi geri gelir",
     "js/kullanici.js",
     "// v2.4.65 TEK KAPI: Bu islev ARTIK sunucuya yazma komutu gondermez.",
     '// v2.4.65 TEK KAPI: Bu islev ARTIK sunucuya yazma komutu gondermez.\nfunction _kdGeriAc() { ws.send(JSON.stringify({ tip: "kullanici_guncelle" })); }'),

    ("A6 kullanici.js okuma gonderimi de kaldirilir (asiri kisitlama)",
     "js/kullanici.js",
     'tip: "kullanici_liste"',
     'tip: "kullanici_liste_KALDIRILDI"'),

    ("A7 menubar.js kullanici menu bagi geri gelir",
     "js/menubar.js",
     '  const pmKurumsal = document.getElementById("pmKurumsalPanel");',
     '  const eskiK = document.getElementById("pmKullanicilar");\n  const pmKurumsal = document.getElementById("pmKurumsalPanel");'),

    ("A8 rol_yonetimi.js menu bagi geri gelir",
     "js/rol_yonetimi.js",
     "// v2.4.65 TEK KAPI: Menu baglantisi KALDIRILDI",
     'document.getElementById("pmRolYonetimi");\n// v2.4.65 TEK KAPI: Menu baglantisi KALDIRILDI'),

    ("A9 rol_yonetimi.js okuma tarafi bozulur (asiri kisitlama)",
     "js/rol_yonetimi.js",
     'window.rolAdlariTazele = function () {',
     'window.rolAdlariTazele_KALDIRILDI = function () {'),

    # --- IKINCI KAPI: Pilot Hakkinda ---
    ("P1 pilot_hakkinda.js rol gonderimi geri gelir (IKINCI KAPI)",
     "js/pilot_hakkinda.js",
     "    // v2.4.65 TEK KAPI: ROL DEGISTIRME BU PENCEREDEN KALDIRILDI.",
     "    if (rolDegistirebilir) { alanlar.rol = document.getElementById('phRol').value; }\n    // v2.4.65 TEK KAPI: ROL DEGISTIRME BU PENCEREDEN KALDIRILDI."),

    ("P2 pilot_hakkinda.js rol combobox'i yeniden etkinlesir",
     "js/pilot_hakkinda.js",
     "  const rolDegistirebilir = false;",
     "  const rolDegistirebilir = yonetici && !kendi;"),

    ("P3 pilot_hakkinda.js kendi profil duzenlemesi kaldirilir",
     "js/pilot_hakkinda.js",
     'tip: "kullanici_guncelle", yetkili: oturum.eposta,',
     'tip: "hicbir_sey", yetkili: oturum.eposta,'),

    # --- i18n dengesi ---
    ("I1 i18n EN karsiligi silinir (TR != EN)",
     "js/i18n.js",
     '    phRolTekKapiNot: "Role assignment is handled in the corporate panel.",',
     ""),

    ("I2 i18n TR karsiligi silinir",
     "js/i18n.js",
     '    pmKurumsalPanel: "Kurumsal Panel",',
     ""),
]


def calistir(gecici: str) -> tuple[int, int, int]:
    """Sinavi verilen kopyada kos; (gecti, kaldi, atlandi) dondur."""
    r = subprocess.run(
        [sys.executable, "sinav_tek_kapi.py"],
        cwd=gecici, capture_output=True, timeout=600)
    cikti = r.stdout.decode(errors="replace")
    g = k = a = -1
    for satir in cikti.splitlines():
        if satir.startswith("GECTI"):
            g = int(satir.split(":")[1].strip())
        elif satir.startswith("KALDI"):
            k = int(satir.split(":")[1].strip())
        elif satir.startswith("ATLANDI"):
            a = int(satir.split(":")[1].strip())
    return g, k, a


def main() -> int:
    print("=" * 66)
    print("KONTROL DENEYI: sinav_tek_kapi.py kusurlari yakalıyor mu?")
    print("=" * 66)

    yakalandi = 0
    kacti: list[str] = []
    uygulanamadi: list[str] = []

    for ad, dosya, bul, degistir in ENJEKSIYONLAR:
        gecici = tempfile.mkdtemp(prefix="tk_")
        try:
            hedef = os.path.join(gecici, "kopya")
            shutil.copytree(KOK, hedef, symlinks=True,
                            ignore=shutil.ignore_patterns(
                                "__pycache__", "*.pyc", "veri",
                                ".git", "node_modules"))
            yol = os.path.join(hedef, dosya)
            if not os.path.exists(yol):
                uygulanamadi.append(f"{ad} -> dosya yok: {dosya}")
                continue
            with open(yol, encoding="utf-8") as f:
                icerik = f.read()
            if bul not in icerik:
                uygulanamadi.append(f"{ad} -> desen bulunamadi")
                continue
            with open(yol, "w", encoding="utf-8") as f:
                f.write(icerik.replace(bul, degistir, 1))

            g, k, a = calistir(hedef)
            if k > 0:
                print(f"  YAKALANDI : {ad}  (kaldi={k})")
                yakalandi += 1
            else:
                print(f"  KACTI     : {ad}  (gecti={g} kaldi={k})")
                kacti.append(ad)
        finally:
            shutil.rmtree(gecici, ignore_errors=True)

    print("=" * 66)
    toplam = len(ENJEKSIYONLAR) - len(uygulanamadi)
    print(f"YAKALANDI    : {yakalandi}/{toplam}")
    print(f"KACTI        : {len(kacti)}")
    print(f"UYGULANAMADI : {len(uygulanamadi)}")
    for s in kacti:
        print(f"  KACTI        : {s}")
    for s in uygulanamadi:
        print(f"  UYGULANAMADI : {s}")
    return 1 if (kacti or uygulanamadi) else 0


if __name__ == "__main__":
    sys.exit(main())
