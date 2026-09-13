#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""SINAV — goktungu/lisans.py cevrimdisi lisans dogrulamasi.

EN KRITIK OLCUM
    Saf Python Ed25519 dogrulayicisi ile `cryptography` AYNI sonucu
    vermek zorunda. Ayrilirlarsa kusur yalnizca `cryptography`
    KURULU OLMAYAN musteri makinesinde ortaya cikar — yani en zor
    tani konulan yerde. Bu yuzden iki yol yuzlerce vektorde
    karsilastirilir.

IKINCI KRITIK OLCUM
    Istemcinin kanonik bayt uretimi merkezin (`mk_yetki.govde_bayt`)
    uretimiyle BIREBIR ayni olmali. Tek karakter fark tum lisanslari
    gecersiz kilar ve Turkce unvanlarda (ensure_ascii) hemen patlar.
"""

import base64
import json
import os
import sys
import tempfile

KOK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KOK)

from goktungu import lisans  # noqa: E402

GECTI = KALDI = 0
KUSURLAR: list[str] = []


def olc(ad: str, kosul: bool, ayrinti: str = "") -> None:
    global GECTI, KALDI
    if kosul:
        GECTI += 1
        print("  [OK] %s" % ad)
    else:
        KALDI += 1
        KUSURLAR.append(ad + ((" — " + ayrinti) if ayrinti else ""))
        print("  [KALDI] %s%s" % (ad, (" — " + ayrinti) if ayrinti else ""))


def bolum(ad: str) -> None:
    print("\n--- %s ---" % ad)


# ======================================================================
bolum("1. Modul sozlesmesi")

for isim in ("imza_dogrula", "govde_bayt", "lisans_oku", "lisans_yaz",
             "lisans_yolu", "merkez_uygulama_kipinde", "yetki_ozeti"):
    olc("islev var: %s" % isim, callable(getattr(lisans, isim, None)))

olc("ACIK_ANAHTAR_B64 tanimli ve 32 bayt cozuluyor",
    len(base64.b64decode(lisans.ACIK_ANAHTAR_B64)) == 32)

# Canli merkezin yayinladigi anahtarla ayni olmali. Ayrilirsa uretilen
# hicbir lisans dogrulanmaz.
olc("gomulu acik anahtar canli merkezle ayni",
    lisans.ACIK_ANAHTAR_B64 ==
    "ZDnJD1vKUwNUkfAx84JcGoRHsU3Vwyh4s/CHzZXCVRo=",
    "merkez anahtari dondurulmusse bu sabit guncellenmeli")

olc("lisans dogrulamasi HTTP cagrisi YAPMIYOR (kapali devre)",
    all(x not in open(os.path.join(KOK, "goktungu", "lisans.py"),
                      encoding="utf-8").read()
        for x in ("urllib.request", "requests.get", "http.client",
                  "socket.create_connection")),
    "kapali devre kurulumda ag cagrisi lisansi dogrulanamaz kilar")


# ======================================================================
bolum("2. Kanonik bayt uretimi merkezle BIREBIR ayni")

# Merkezin uretimi (mk_yetki.govde_bayt) burada yeniden kurulur.
def merkez_govde_bayt(govde: dict) -> bytes:
    return json.dumps(govde, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


ornekler = [
    {"surum": 1, "firma_id": 3, "firma_unvan": "VEILOX Savunma A.S.",
     "lisans_uid": "ABC123",
     "yetkiler": {"sinirsiz": True, "ai": True, "radar": False,
                  "gccdual": False}},
    # TURKCE KARAKTER: ensure_ascii farki tam burada patlar.
    {"surum": 1, "firma_id": 7,
     "firma_unvan": "Gökkubbe Teknoloji Ltd. Şti. — Çığır Ölçüm",
     "lisans_uid": "ŞğİÖÜ-42",
     "yetkiler": {"sinirsiz": True, "ai": False, "radar": True,
                  "gccdual": True}},
    # ANAHTAR SIRASI TERS: sort_keys ikisinde de ayni sonucu vermeli.
    {"yetkiler": {"radar": True, "ai": True, "gccdual": True,
                  "sinirsiz": True},
     "lisans_uid": "Z", "firma_unvan": "A", "firma_id": 1, "surum": 1},
]
for i, g in enumerate(ornekler, 1):
    olc("kanonik bayt merkezle ayni (ornek %d)" % i,
        lisans.govde_bayt(g) == merkez_govde_bayt(g))

olc("Turkce karakter ASCII'ye kacirilmiyor (ensure_ascii=False)",
    "ö".encode("utf-8") in lisans.govde_bayt(ornekler[1]),
    "ensure_ascii=True olursa \\u kacislari uretilir ve imza bozulur")

olc("kanonik baytta bosluk yok (separators)",
    b", " not in lisans.govde_bayt(ornekler[0]) and
    b": " not in lisans.govde_bayt(ornekler[0]))


# ======================================================================
bolum("3. Saf Python Ed25519 == cryptography (EN KRITIK)")

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey, Ed25519PublicKey)
    KUTUPHANE = True
except ImportError:
    KUTUPHANE = False

olc("sinav ortaminda cryptography var (karsilastirma yapilabilir)",
    KUTUPHANE, "kutuphane yoksa iki yol karsilastirilamaz")

if KUTUPHANE:
    import random
    rnd = random.Random(20260815)

    gecerli_ayni = 0
    bozuk_ayni = 0
    ORNEK = 120

    for _ in range(ORNEK):
        gizli = Ed25519PrivateKey.generate()
        acik = gizli.public_key().public_bytes_raw()
        ileti = bytes(rnd.randrange(256)
                      for _ in range(rnd.randrange(0, 200)))
        imza = gizli.sign(ileti)

        # Saf yol
        saf = lisans._saf_dogrula(acik, imza, ileti)
        # Kutuphane yolu
        try:
            Ed25519PublicKey.from_public_bytes(acik).verify(imza, ileti)
            kut = True
        except Exception:
            kut = False
        if saf == kut is True:
            gecerli_ayni += 1

        # BOZUK imza: tek bit cevrilir. Iki yol da REDDETMELI.
        ba = bytearray(imza)
        ba[rnd.randrange(64)] ^= 1 << rnd.randrange(8)
        bozuk = bytes(ba)
        saf_b = lisans._saf_dogrula(acik, bozuk, ileti)
        try:
            Ed25519PublicKey.from_public_bytes(acik).verify(bozuk, ileti)
            kut_b = True
        except Exception:
            kut_b = False
        if saf_b == kut_b is False:
            bozuk_ayni += 1

    olc("gecerli imza: saf ve kutuphane %d/%d ornekte AYNI (kabul)"
        % (gecerli_ayni, ORNEK), gecerli_ayni == ORNEK)
    olc("bozuk imza: saf ve kutuphane %d/%d ornekte AYNI (ret)"
        % (bozuk_ayni, ORNEK), bozuk_ayni == ORNEK)

    # ILETI DEGISIKLIGI: imza gecerli ama ileti farkli.
    gizli = Ed25519PrivateKey.generate()
    acik = gizli.public_key().public_bytes_raw()
    imza = gizli.sign(b"dogru ileti")
    olc("saf yol: ileti degistirilirse reddeder",
        lisans._saf_dogrula(acik, imza, b"yanlis ileti") is False)
    olc("saf yol: dogru ileti kabul eder",
        lisans._saf_dogrula(acik, imza, b"dogru ileti") is True)

    # BASKA ANAHTAR: imza baskasinin anahtariyla dogrulanmamali.
    baska = Ed25519PrivateKey.generate().public_key().public_bytes_raw()
    olc("saf yol: baska anahtarla dogrulanmaz",
        lisans._saf_dogrula(baska, imza, b"dogru ileti") is False)

    # BICIM DENETIMLERI
    olc("saf yol: 64 bayt olmayan imzayi reddeder",
        lisans._saf_dogrula(acik, imza[:63], b"x") is False)
    olc("saf yol: 32 bayt olmayan anahtari reddeder",
        lisans._saf_dogrula(acik[:31], imza, b"x") is False)
    # S >= L: RFC 8032 bunu reddetmeyi sart kosar (esnek imza).
    kotu = imza[:32] + (lisans._L + 1).to_bytes(32, "little")
    olc("saf yol: S >= L olan imzayi reddeder (esneklik onlemi)",
        lisans._saf_dogrula(acik, kotu, b"dogru ileti") is False)


# ======================================================================
bolum("4. imza_dogrula() — gomulu anahtarla ucdan uca")

# Gomulu anahtar merkezin; ona ait gizli anahtar burada yok. Bu yuzden
# gomulu anahtari GECICI olarak sinav anahtariyla degistirip ucdan uca
# akisi olcuyoruz. Degistirme sonunda geri alinir.
if KUTUPHANE:
    ozgun = lisans.ACIK_ANAHTAR_B64
    try:
        gizli = Ed25519PrivateKey.generate()
        acik_b64 = base64.b64encode(
            gizli.public_key().public_bytes_raw()).decode("ascii")
        lisans.ACIK_ANAHTAR_B64 = acik_b64

        govde = {"surum": 1, "firma_id": 42,
                 "firma_unvan": "Gökkubbe Teknoloji Ltd. Şti.",
                 "lisans_uid": "TEST-UID-1",
                 "yetkiler": {"sinirsiz": True, "ai": True,
                              "radar": True, "gccdual": False}}
        ham = lisans.govde_bayt(govde)
        imza_b64 = base64.b64encode(gizli.sign(ham)).decode("ascii")

        olc("imza_dogrula: gecerli imzayi kabul eder",
            lisans.imza_dogrula(ham, imza_b64) is True)
        olc("imza_dogrula: govde degisirse reddeder",
            lisans.imza_dogrula(ham + b" ", imza_b64) is False)
        olc("imza_dogrula: bos imzayi reddeder",
            lisans.imza_dogrula(ham, "") is False)
        olc("imza_dogrula: base64 olmayan imzayi reddeder (coker degil)",
            lisans.imza_dogrula(ham, "bu base64 degil!!") is False)
        olc("imza_dogrula: None imzayi reddeder",
            lisans.imza_dogrula(ham, None) is False)

        # urlsafe base64 KULLANILMAMALI. Standart base64 bekleniyor.
        urlsafe = base64.urlsafe_b64encode(gizli.sign(ham)).decode("ascii")
        if urlsafe != imza_b64:
            olc("imza_dogrula: standart base64 bekliyor (urlsafe degil)",
                lisans.imza_dogrula(ham, urlsafe) is False or
                "-" not in urlsafe and "_" not in urlsafe)
        else:
            GECTI += 1
            print("  [OK] imza urlsafe ile ayni (ayrim gozlenemedi)")

        # ---------------- lisans_yaz / lisans_oku ucdan uca
        gecici = tempfile.mkdtemp(prefix="lisans_sinav_")
        yol = os.path.join(gecici, "veri", "merkez_lisans.json")

        tamam, hata = lisans.lisans_yaz(
            {"lisans": govde, "imza": imza_b64}, yol)
        olc("lisans_yaz: gecerli belgeyi yazar", tamam, hata)
        olc("lisans_yaz: dosya gercekten olustu", os.path.isfile(yol))
        olc("lisans_yaz: yarim dosya birakmiyor (.yeni kalmadi)",
            not os.path.exists(yol + ".yeni"))

        y, hata = lisans.lisans_oku(yol)
        olc("lisans_oku: yazilani okur", y is not None, hata)
        if y:
            olc("lisans_oku: firma_id dogru", y["firma_id"] == 42)
            olc("lisans_oku: unvan Turkce karakterle bozulmadan geldi",
                y["firma_unvan"] == "Gökkubbe Teknoloji Ltd. Şti.",
                repr(y.get("firma_unvan")))
            olc("lisans_oku: sinirsiz dogru", y["sinirsiz"] is True)
            olc("lisans_oku: ai dogru", y["ai"] is True)
            olc("lisans_oku: radar dogru", y["radar"] is True)
            olc("lisans_oku: gccdual dogru", y["gccdual"] is False)
            olc("lisans_oku: lisans_uid dogru",
                y["lisans_uid"] == "TEST-UID-1")

        # ---------------- KURCALAMA: yetkiyi elle yukseltme denemesi
        with open(yol, encoding="utf-8") as f:
            belge = json.load(f)
        belge["lisans"]["yetkiler"]["gccdual"] = True   # yetki yukseltme
        with open(yol, "w", encoding="utf-8") as f:
            json.dump(belge, f, ensure_ascii=False)
        y2, hata2 = lisans.lisans_oku(yol)
        olc("KURCALAMA: yetki elle yukseltilirse lisans REDDEDILIR",
            y2 is None, "yetki yukseltme imzayi bozmali")
        olc("KURCALAMA: hata metni imzayi isaret ediyor",
            "IMZA" in (hata2 or "").upper() or
            "imza" in (hata2 or ""), repr(hata2))

        # ---------------- KURCALAMA: unvan degistirme
        belge["lisans"]["yetkiler"]["gccdual"] = False   # geri al
        belge["lisans"]["firma_unvan"] = "Baska Sirket A.S."
        with open(yol, "w", encoding="utf-8") as f:
            json.dump(belge, f, ensure_ascii=False)
        y3, _ = lisans.lisans_oku(yol)
        olc("KURCALAMA: unvan degistirilirse lisans REDDEDILIR",
            y3 is None)

        # ---------------- lisans_yaz gecersiz belgeyi YAZMAMALI
        yol2 = os.path.join(gecici, "veri", "bozuk.json")
        tamam2, hata3 = lisans.lisans_yaz(
            {"lisans": govde, "imza": base64.b64encode(b"x" * 64)
             .decode("ascii")}, yol2)
        olc("lisans_yaz: gecersiz imzali belgeyi YAZMAZ",
            tamam2 is False and not os.path.exists(yol2), hata3)

        tamam3, _ = lisans.lisans_yaz({"lisans": govde}, yol2)
        olc("lisans_yaz: imzasiz belgeyi reddeder", tamam3 is False)
        tamam4, _ = lisans.lisans_yaz({"imza": imza_b64}, yol2)
        olc("lisans_yaz: govdesiz belgeyi reddeder", tamam4 is False)

        # ---------------- Eksik / bozuk dosya davranisi
        yok = os.path.join(gecici, "hic_yok.json")
        y4, hata4 = lisans.lisans_oku(yok)
        olc("lisans_oku: dosya yoksa None + aciklayici hata",
            y4 is None and len(hata4) > 30, repr(hata4[:60]))
        olc("lisans_oku: hata metni kullaniciya YOL GOSTERIYOR",
            "kurumsal panel" in hata4.lower() or
            "Kurumsal panelden" in hata4,
            "kapali devre musteri ne yapacagini ekrandan gormeli")

        bozuk_yol = os.path.join(gecici, "bozuk2.json")
        with open(bozuk_yol, "w", encoding="utf-8") as f:
            f.write("{bu gecerli json degil")
        y5, hata5 = lisans.lisans_oku(bozuk_yol)
        olc("lisans_oku: bozuk JSON'da cokmez", y5 is None and bool(hata5))

        liste_yol = os.path.join(gecici, "liste.json")
        with open(liste_yol, "w", encoding="utf-8") as f:
            json.dump([1, 2, 3], f)
        y6, _ = lisans.lisans_oku(liste_yol)
        olc("lisans_oku: nesne yerine dizi gelirse cokmez", y6 is None)

    finally:
        lisans.ACIK_ANAHTAR_B64 = ozgun


# ======================================================================
bolum("5. yetki_ozeti() — lisanssiz kurulum kilitlenmemeli")

# LISANSSIZ kurulum olagan kullanimdir (kopru ile merkeze baglanir) ve
# yetkilerini MERKEZDEN alir. Bu islev yalniz YEREL belgeye bakar;
# lisans yokken "kaynak: merkez" demeli, yetkileri kapatmakla
# yetinmemeli. Aksi halde olagan kurulumda AI/radar menuleri lisans
# dosyasi yok diye kapanirdi.
gecici2 = tempfile.mkdtemp(prefix="lisans_ozet_")
ozgun_yolu = lisans.lisans_yolu
try:
    lisans.lisans_yolu = lambda: os.path.join(gecici2, "yok.json")
    ozet = lisans.yetki_ozeti()
    olc("yetki_ozeti: lisans yoksa lisansli=False", ozet["lisansli"] is False)
    olc("yetki_ozeti: lisans yoksa kaynak='merkez' (kilit DEGIL)",
        ozet["kaynak"] == "merkez",
        "lisanssiz kurulum yetkisini merkezden alir")
    olc("yetki_ozeti: hata metni tasiniyor", bool(ozet["hata"]))
    olc("merkez_uygulama_kipinde: lisans yoksa False",
        lisans.merkez_uygulama_kipinde() is False)
    for a in ("lisansli", "kaynak", "sinirsiz", "ai", "radar", "gccdual",
              "firma_unvan", "lisans_uid", "hata"):
        olc("yetki_ozeti alani var: %s" % a, a in ozet)
finally:
    lisans.lisans_yolu = ozgun_yolu


# ======================================================================
bolum("6. lisans_yolu() veri dizinine yazmali")

yol_s = lisans.lisans_yolu()
olc("lisans_yolu mutlak yol donduruyor", os.path.isabs(yol_s), yol_s)
olc("lisans_yolu dosya adi merkez_lisans.json",
    os.path.basename(yol_s) == "merkez_lisans.json", yol_s)
olc("lisans_yolu veri dizini altinda (kod dizinine yazmiyor)",
    os.sep + "veri" + os.sep in yol_s or "/veri/" in yol_s, yol_s)


# ======================================================================
print("\n" + "=" * 62)
print(" SONUC: %d gecti, %d kaldi" % (GECTI, KALDI))
print("=" * 62)
if KUSURLAR:
    print("\nKUSURLAR:")
    for k in KUSURLAR:
        print("  - %s" % k)
sys.exit(1 if KALDI else 0)
