#!/usr/bin/env python3
"""KURULU .deb uzerinde lisans akisini GERCEKTEN olcer.

Neden bu olcum ayri:
  `sinav_lisans.py` kaynak agacinda kosuyor. Ama musteri KURULU paketi
  kullanacak ve orada iki sey farkli:
    1) veri dizini `GOKTUNGU_VERI_KOKU` ile `/var/lib/goktungu-merkez`e tasindi
    2) modul yolu `assets/python` altindan cozuluyor
  Bu iki farkin lisansi bozmadigi, kurulu paket uzerinde olculmeli.

Olculen sey: merkezin GERCEK gizli anahtariyla uretilmis imza, KURULU
pakete gomulu acik anahtarla dogrulaniyor mu; ve kurcalanmis lisans
reddediliyor mu.

Kosum:  sudo -u goktungu-merkez .venv/bin/python canli_deb_lisans_olcum.py
"""
import json
import os
import subprocess
import sys

KURULUM = "/opt/goktungu/merkez"
VERI = "/var/lib/goktungu-merkez"

# Merkezin gercek gizli anahtariyla uretilmis ornek cift.
# (imza_ornek_uret.py ile merkez sunucuda uretildi; gizli anahtar
#  merkezde kaldi, buraya yalniz imza indi)
# NOT: bu cift `paketle_merkez.py` icindekiyle BIREBIR ayni olmali.
# Ilk yazimda alanlari elle uydurmustum (urun/veriliş/bitis) ve imza
# dogrulanmadi — imza kanonik GOVDEYE baglidir, tek alan farki yeter.
# Olcum kaldi, kod dogruydu.
ORNEK_GOVDE = {
    "surum": 1,
    "firma_id": 1,
    "firma_unvan": "VEILOX Savunma Teknolojileri A.S.",
    "lisans_uid": "PKTDOGRULAMA01",
    "yetkiler": {"sinirsiz": True, "ai": True,
                 "radar": True, "gccdual": True},
}
ORNEK_IMZA = (
    "WFJ9qDt6hZw8vEoRRigZwQhw22hHBvepaKwrrloEHQnT7uGlV77R+NVAwbU/Y0ZIhGlu"
    "dB9bEhZ8cpuAb7WADg=="
)

gecti = []
kaldi = []


def olc(ad, kosul, ayrinti=""):
    (gecti if kosul else kaldi).append(ad)
    im = "GECTI" if kosul else "KALDI"
    print(f"  [{im}] {ad}" + (f"  -- {ayrinti}" if ayrinti and not kosul
                              else ""))


def main():
    print("=" * 66)
    print(" KURULU .deb UZERINDE LISANS OLCUMU")
    print("=" * 66)

    # --- 1) Kurulum yapisi ---
    olc("kurulum dizini var", os.path.isdir(KURULUM))
    olc("veri dizini var", os.path.isdir(VERI))

    py_kok = os.path.join(KURULUM, "assets", "python")
    olc("assets/python var", os.path.isdir(py_kok))

    # --- 2) Lisans modulu kurulu paketten ice alinir ---
    sys.path.insert(0, py_kok)
    try:
        from goktungu import lisans as L
        olc("lisans modulu ice alindi", True)
    except Exception as e:
        olc("lisans modulu ice alindi", False, str(e))
        rapor()
        return

    # --- 3) Veri kokunun GERCEKTEN tasindigini olc ---
    # Kurulumda GOKTUNGU_VERI_KOKU=/var/lib/goktungu-merkez veriliyor.
    os.environ.setdefault("GOKTUNGU_VERI_KOKU", VERI)
    try:
        from goktungu import sabitler as S
        vk = os.path.realpath(S.VERI_KOKU)
        olc("VERI_KOKU /var/lib/goktungu-merkez'e tasindi",
            vk == os.path.realpath(VERI), f"gorulen: {vk}")
    except Exception as e:
        olc("sabitler ice alindi", False, str(e))

    # --- 4) Gomulu acik anahtar GERCEK imzayi dogruluyor mu ---
    # En kritik olcum: bu kalirsa 5.000 $ odemis musteri gecerli
    # lisansiyla yazilimi acamaz.
    try:
        gb = L.govde_bayt(ORNEK_GOVDE)
        olc("kanonik govde uretildi", isinstance(gb, bytes) and len(gb) > 50,
            f"{len(gb) if isinstance(gb, bytes) else '?'} bayt")
        olc("GERCEK imza gomulu anahtarla DOGRULANDI",
            L.imza_dogrula(gb, ORNEK_IMZA))
    except Exception as e:
        olc("GERCEK imza gomulu anahtarla DOGRULANDI", False, str(e))

    # --- 5) Kurcalanmis lisans reddedilmeli ---
    try:
        bozuk = json.loads(json.dumps(ORNEK_GOVDE))
        bozuk["firma_id"] = 999
        olc("firma_id kurcalamasi REDDEDILDI",
            not L.imza_dogrula(L.govde_bayt(bozuk), ORNEK_IMZA))

        bozuk2 = json.loads(json.dumps(ORNEK_GOVDE))
        bozuk2["yetkiler"]["pilot_koltuk"] = 9999
        olc("yetki yukseltme REDDEDILDI",
            not L.imza_dogrula(L.govde_bayt(bozuk2), ORNEK_IMZA))

        bozuk3 = json.loads(json.dumps(ORNEK_GOVDE))
        bozuk3["firma_unvan"] = "BASKA FIRMA A.S."
        olc("firma unvani kurcalamasi REDDEDILDI",
            not L.imza_dogrula(L.govde_bayt(bozuk3), ORNEK_IMZA))

        # Imzanin tek biti cevrilirse
        ham = bytearray(__import__("base64").b64decode(ORNEK_IMZA))
        ham[0] ^= 0x01
        bozuk_imza = __import__("base64").b64encode(bytes(ham)).decode()
        olc("bit cevrilmis imza REDDEDILDI",
            not L.imza_dogrula(L.govde_bayt(ORNEK_GOVDE), bozuk_imza))
    except Exception as e:
        olc("kurcalama olcumleri", False, str(e))

    # --- 6) Lisans dosyasi yokken yazilim CALISMALI ---
    # Merkez Uygulama lisansi olmayan olagan kurulum bozulmamali.
    try:
        yol = L.lisans_yolu()
        olc("lisans yolu veri dizininde",
            os.path.realpath(os.path.dirname(yol)) ==
            os.path.realpath(VERI), f"gorulen: {yol}")
        if not os.path.exists(yol):
            olc("lisans yokken merkez_uygulama_kipinde() False",
                L.merkez_uygulama_kipinde() is False)
            # Gercek sozlesme: alan adi `lisansli` (ilk yazimda `var`
            # varsaymistim). Lisans yokken `kaynak: merkez` donmesi
            # KASITLI: olagan kurulum yetkilerini merkezden alir, yerel
            # lisans yoklugu "yetkisiz" demek DEGILDIR.
            oz = L.yetki_ozeti()
            olc("lisans yokken lisansli=False",
                isinstance(oz, dict) and oz.get("lisansli") is False,
                repr(oz)[:90])
            olc("lisans yokken yetki kaynagi MERKEZ",
                isinstance(oz, dict) and oz.get("kaynak") == "merkez",
                repr(oz)[:90])
    except Exception as e:
        olc("lisans yoklugu olcumleri", False, str(e))

    # --- 7) HTTP: hicbir cevrimdisi dogrulama agi kullanmamali ---
    kaynak = os.path.join(py_kok, "goktungu", "lisans.py")
    try:
        with open(kaynak, encoding="utf-8") as f:
            metin = f.read()
        yasak = ["urllib", "requests", "http.client", "socket"]
        bulunan = [y for y in yasak if y in metin]
        olc("lisans dogrulama AG KULLANMIYOR (kapali devre)",
            not bulunan, f"bulunan: {bulunan}")
    except Exception as e:
        olc("kaynak okundu", False, str(e))

    rapor()


def rapor():
    print("-" * 66)
    print(f" SONUC: {len(gecti)} gecti / {len(kaldi)} kaldi")
    if kaldi:
        for k in kaldi:
            print(f"   KALDI: {k}")
    print("=" * 66)
    sys.exit(1 if kaldi else 0)


if __name__ == "__main__":
    main()
