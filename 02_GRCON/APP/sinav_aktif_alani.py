#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""Sinav: kullanici 'aktif' alani tip dayanikliligi (v2.4.64).

KULLANICI BILDIRIMI
    "fatih.gemi@gokkubbetech.com kullanici adi ile kullanici olusturdum
     ama giris yapmasina izin vermiyor neden"
    "ben goruyorum ama kullaniciyi"

KOK NEDEN
    Veritabani 'aktif' alanini INTEGER 0/1 tutar. Sunucu ham tamsayiyi
    arayuze gonderiyordu; JavaScript'te 0 === false DAIMA false verir.
    Sonuc:
      * pasif kullanici listede ETKIN gorunur
      * etkinlestirme dugmesi {aktif:false} gonderir -> pasif KALIR

    Ayrica Python tarafinda bool("0") True oldugu icin "0" dizesi 1
    olarak yaziliyordu (pasiflestirme sessizce basarisiz).

NEDEN BU SINAV GEREKLI
    Kusur iki dilin tip kurallarinin kesisiminde. Her iki taraf da kendi
    icinde tutarli gorunur; uyumsuzluk yalnizca gercek veri akarken
    ortaya cikar. Bu yuzden sinav GERCEK veritabani kaydi olusturup
    listesi_guvenli() / dogrula() / guncelle() zincirini olcer.
"""
from __future__ import annotations

import os
import sys
import tempfile

KOK = os.path.dirname(os.path.abspath(__file__))
if KOK not in sys.path:
    sys.path.insert(0, KOK)

GECTI = 0
KALDI = 0
HATALAR: list[str] = []


def olc(ad: str, kosul: bool, ayrinti: str = "") -> None:
    global GECTI, KALDI
    if kosul:
        GECTI += 1
        print(f"  [GECTI] {ad}")
    else:
        KALDI += 1
        HATALAR.append(f"{ad}{(' -> ' + ayrinti) if ayrinti else ''}")
        print(f"  [KALDI] {ad}" + (f" -> {ayrinti}" if ayrinti else ""))


# ----------------------------------------------------------------------
# 1) aktif_mi() ortak kurali
# ----------------------------------------------------------------------
def bolum_aktif_mi() -> None:
    print("\n=== 1) aktif_mi() ortak kurali ===")
    from goktungu.kullanicilar import aktif_mi

    # Veritabani bicimi (INTEGER) — kusurun merkezi
    olc("aktif_mi(1) -> True", aktif_mi(1) is True)
    olc("aktif_mi(0) -> False", aktif_mi(0) is False)

    # Arayuz bicimi (JSON boolean)
    olc("aktif_mi(True) -> True", aktif_mi(True) is True)
    olc("aktif_mi(False) -> False", aktif_mi(False) is False)

    # Dize bicimi — bool(\"0\") True oldugu icin eskiden yanlisti
    olc('aktif_mi("0") -> False (bool("0") tuzagi)',
        aktif_mi("0") is False,
        "bool('0') Python'da True'dur; ozel islenmeli")
    olc('aktif_mi("1") -> True', aktif_mi("1") is True)
    olc('aktif_mi("false") -> False', aktif_mi("false") is False)
    olc('aktif_mi("true") -> True', aktif_mi("true") is True)

    # Eksik alan -> DB DEFAULT 1 ile uyumlu olmali
    olc("aktif_mi(None) -> True (DB DEFAULT 1)", aktif_mi(None) is True)
    olc('aktif_mi("") -> True (bos = degistirme)', aktif_mi("") is True)

    # Bosluklu dize
    olc('aktif_mi(" 0 ") -> False', aktif_mi(" 0 ") is False)


# ----------------------------------------------------------------------
# 2) Gercek veritabani zinciri
# ----------------------------------------------------------------------
def bolum_veritabani() -> None:
    print("\n=== 2) Gercek veritabani zinciri ===")

    gecici = tempfile.mkdtemp(prefix="sinav_aktif_")
    os.environ["GOKTUNGU_VERI_DIZIN"] = gecici

    import importlib
    import goktungu.sabitler
    importlib.reload(goktungu.sabitler)
    import goktungu.veritabani
    importlib.reload(goktungu.veritabani)
    import goktungu.kullanicilar
    importlib.reload(goktungu.kullanicilar)

    from goktungu.kullanicilar import KullaniciYoneticisi
    from goktungu.veritabani import baglanti

    ky = KullaniciYoneticisi()

    # --- Yeni kullanici ETKIN olusmali (ekle() daima 1 yazar) ---
    tamam, hata = ky.ekle("pilot.sinav@ornek.local", "Pilot Sinav",
                          "Pilot", "kullanici", "SifreDeneme123")
    olc("ekle() basarili", tamam is True, str(hata))

    liste = ky.listesi_guvenli()
    kayit = next((x for x in liste
                  if x["eposta"] == "pilot.sinav@ornek.local"), None)
    olc("yeni kullanici listede var", kayit is not None)

    if kayit is not None:
        olc("listesi_guvenli(): aktif BOOLEAN tipinde",
            isinstance(kayit["aktif"], bool),
            f"tip={type(kayit['aktif']).__name__} deger={kayit['aktif']!r}")
        olc("yeni kullanici aktif=True", kayit["aktif"] is True)

    # --- Giris yapabilmeli ---
    g = ky.dogrula("pilot.sinav@ornek.local", "SifreDeneme123")
    olc("etkin kullanici giris yapabiliyor", g is not None)

    # --- Pasiflestir (arayuzun gonderdigi boolean ile) ---
    ky.guncelle("pilot.sinav@ornek.local", {"aktif": False})
    with baglanti() as con:
        ham = con.execute(
            "SELECT aktif FROM kullanicilar WHERE eposta = ?",
            ("pilot.sinav@ornek.local",)).fetchone()[0]
    olc("pasiflestirme diske 0 yazdi", int(ham) == 0, f"ham={ham!r}")

    g = ky.dogrula("pilot.sinav@ornek.local", "SifreDeneme123")
    olc("pasif kullanici giris YAPAMIYOR", g is None)

    liste = ky.listesi_guvenli()
    kayit = next((x for x in liste
                  if x["eposta"] == "pilot.sinav@ornek.local"), None)
    olc("pasif kullanici listede aktif=False",
        kayit is not None and kayit["aktif"] is False,
        f"deger={kayit['aktif']!r}" if kayit else "kayit yok")
    olc("pasif kayitta aktif hala BOOLEAN",
        kayit is not None and isinstance(kayit["aktif"], bool))

    # --- Etkinlestir (KULLANICININ YASADIGI SENARYO) ---
    # Arayuz artik mevcut durumun TERSINI gonderir: pasif -> True
    ky.guncelle("pilot.sinav@ornek.local", {"aktif": True})
    g = ky.dogrula("pilot.sinav@ornek.local", "SifreDeneme123")
    olc("etkinlestirme SONRASI giris yapabiliyor (asil kusur)",
        g is not None,
        "etkinlestirme dugmesi pasif kullaniciyi kurtarmali")

    # --- "0" dizesi tuzagi: pasiflestirme gercekten yazilmali ---
    ky.guncelle("pilot.sinav@ornek.local", {"aktif": "0"})
    with baglanti() as con:
        ham = con.execute(
            "SELECT aktif FROM kullanicilar WHERE eposta = ?",
            ("pilot.sinav@ornek.local",)).fetchone()[0]
    olc('guncelle(aktif="0") diske 0 yazdi (bool tuzagi)',
        int(ham) == 0, f"ham={ham!r}")
    g = ky.dogrula("pilot.sinav@ornek.local", "SifreDeneme123")
    olc('aktif="0" sonrasi giris YAPAMIYOR', g is None)

    # --- Ham "0" dizesi DB'de olsa bile giris kapali olmali ---
    with baglanti() as con:
        con.execute(
            "UPDATE kullanicilar SET aktif = 0 WHERE eposta = ?",
            ("pilot.sinav@ornek.local",))
    g = ky.dogrula("pilot.sinav@ornek.local", "SifreDeneme123")
    olc("DB'de 0 iken giris kapali", g is None)

    # --- Geri etkinlestir ve kapat ---
    ky.guncelle("pilot.sinav@ornek.local", {"aktif": 1})
    g = ky.dogrula("pilot.sinav@ornek.local", "SifreDeneme123")
    olc("aktif=1 ile giris yeniden acildi", g is not None)


# ----------------------------------------------------------------------
# 3) Arayuz kaynagi: ham karsilastirma kalmamali
# ----------------------------------------------------------------------
def bolum_arayuz() -> None:
    print("\n=== 3) Arayuz kaynagi denetimi ===")

    yol = os.path.join(KOK, "js", "kullanici.js")
    with open(yol, "r", encoding="utf-8") as f:
        satirlar = f.readlines()

    # Aciklama satirlarini disla: kusuru ANLATAN yorum kusur degildir
    kod = []
    for i, s in enumerate(satirlar, 1):
        kirp = s.strip()
        if kirp.startswith("//") or kirp.startswith("*") \
                or kirp.startswith("/*"):
            continue
        kod.append((i, s))

    kotu = [(i, s.strip()) for i, s in kod
            if "aktif === false" in s or "aktif === true" in s]
    olc("js/kullanici.js: ham 'aktif === false/true' kalmadi",
        not kotu, "; ".join(f"satir {i}: {s}" for i, s in kotu))

    metin = "".join(satirlar)
    olc("kulAktifMi() yardimcisi tanimli",
        "function kulAktifMi(" in metin)
    olc("liste cizimi kulAktifMi kullaniyor",
        "kulAktifMi(k.aktif)" in metin)
    olc("dugme mevcut durumun TERSINI gonderiyor",
        "{aktif: !kAktif}" in metin)

    # kulAktifMi mantigini Node ile GERCEKTEN calistir
    import json
    import subprocess

    bas = metin.index("function kulAktifMi(")
    son = metin.index("\n}", bas) + 2
    islev = metin[bas:son]

    betik = islev + """
const sonuc = {
  bir: kulAktifMi(1), sifir: kulAktifMi(0),
  dogru: kulAktifMi(true), yanlis: kulAktifMi(false),
  dizeSifir: kulAktifMi("0"), dizeBir: kulAktifMi("1"),
  tanimsiz: kulAktifMi(undefined), bos: kulAktifMi("")
};
console.log(JSON.stringify(sonuc));
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     encoding="utf-8") as f:
        f.write(betik)
        gecici_js = f.name
    try:
        cikti = subprocess.run(["node", gecici_js], capture_output=True,
                               text=True, timeout=60)
        veri = json.loads(cikti.stdout.strip() or "{}")
        olc("Node: kulAktifMi(0) === false (asil kusur)",
            veri.get("sifir") is False, str(veri))
        olc("Node: kulAktifMi(1) === true", veri.get("bir") is True)
        olc("Node: kulAktifMi(false) === false",
            veri.get("yanlis") is False)
        olc("Node: kulAktifMi(true) === true", veri.get("dogru") is True)
        olc('Node: kulAktifMi("0") === false',
            veri.get("dizeSifir") is False)
        olc('Node: kulAktifMi("1") === true',
            veri.get("dizeBir") is True)
        olc("Node: kulAktifMi(undefined) === true",
            veri.get("tanimsiz") is True)
    finally:
        os.unlink(gecici_js)


# ----------------------------------------------------------------------
# 4) Sunucu kaynagi: ortak kural kullanimda
# ----------------------------------------------------------------------
def bolum_sunucu_kaynak() -> None:
    print("\n=== 4) Sunucu kaynagi denetimi ===")
    import ast

    yol = os.path.join(KOK, "goktungu", "kullanicilar.py")
    with open(yol, "r", encoding="utf-8") as f:
        kaynak = f.read()

    agac = ast.parse(kaynak)

    islevler = {}
    for dugum in ast.walk(agac):
        if isinstance(dugum, (ast.FunctionDef, ast.AsyncFunctionDef)):
            islevler[dugum.name] = dugum

    olc("aktif_mi() tanimli", "aktif_mi" in islevler)

    # dogrula() ortak kurali cagirmali
    dg = islevler.get("dogrula")
    if dg is not None:
        cagrilar = {d.func.id for d in ast.walk(dg)
                    if isinstance(d, ast.Call)
                    and isinstance(d.func, ast.Name)}
        olc("dogrula() aktif_mi() cagiriyor", "aktif_mi" in cagrilar,
            f"cagrilar={sorted(cagrilar)}")

    lg = islevler.get("listesi_guvenli")
    if lg is not None:
        cagrilar = {d.func.id for d in ast.walk(lg)
                    if isinstance(d, ast.Call)
                    and isinstance(d.func, ast.Name)}
        olc("listesi_guvenli() aktif_mi() cagiriyor",
            "aktif_mi" in cagrilar, f"cagrilar={sorted(cagrilar)}")

    gc = islevler.get("guncelle")
    if gc is not None:
        cagrilar = {d.func.id for d in ast.walk(gc)
                    if isinstance(d, ast.Call)
                    and isinstance(d.func, ast.Name)}
        olc("guncelle() aktif_mi() cagiriyor", "aktif_mi" in cagrilar,
            f"cagrilar={sorted(cagrilar)}")


def main() -> int:
    print("=" * 62)
    print("SINAV: kullanici 'aktif' alani tip dayanikliligi (v2.4.64)")
    print("=" * 62)

    bolum_aktif_mi()
    bolum_veritabani()
    bolum_arayuz()
    bolum_sunucu_kaynak()

    print("\n" + "=" * 62)
    print(f"SONUC: {GECTI} gecti, {KALDI} kaldi")
    if HATALAR:
        print("\nKALAN OLCUMLER:")
        for h in HATALAR:
            print(f"  - {h}")
    print("=" * 62)
    return 0 if KALDI == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
