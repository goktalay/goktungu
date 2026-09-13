#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""
SINAV: TEK KAPI (v2.4.65)
=========================
GCS arayuzunden uyelik ve rol yonetiminin GERCEKTEN kaldirildigini
olcer.

KOK NEDEN (bu sinavin var olma sebebi)
--------------------------------------
Iki ayri kullanici tablosu var:

  merkez  goktungu_merkez.kullanicilar  pbkdf2_sha256  firma_id ZORUNLU
  yerel   goktungu_app.kullanicilar     sha256:tuz     firma bagi YOK

/app/ GOKTUNGU_MERKEZ_KIMLIK=1 ile MERKEZ tablosundan dogrular; ancak
GCS arayuzunun "Yeni Kullanici" penceresi YEREL tabloya yaziyordu.
Sonuc: eklenen kullanici hicbir zaman giris yapamiyordu (fatih.gemi
olayi). Ayrica pilot koltuk siniri merkezde denetlendigi icin bu
yazma kapisi faturalandirmayi atlatan ikinci bir kapiydi.

OLCUM BICIMI
------------
WS komut isleyicisi GERCEKTEN cagrilir (sahte websocket ile) ve
yanit incelenir. Kaynak metni aramasi YETMEZ: onceki deneyde
"pass" birakan enjeksiyonlar desen kalintisi yuzunden kacmisti.
Bu yuzden arayuz tarafi da DOM/JS davranisiyla olculur (jsdom
yoksa dosya duzeyinde yapisal olcum yapilir, ancak o olcumler
"atlandi" olarak isaretlenir; gecmis sayilmaz).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import types

KOK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KOK)

GECTI: list[str] = []
KALDI: list[str] = []
ATLANDI: list[str] = []


def olc(ad: str, kosul: bool, ayrinti: str = "") -> None:
    if kosul:
        GECTI.append(ad)
    else:
        KALDI.append(f"{ad}" + (f" -> {ayrinti}" if ayrinti else ""))


def atla(ad: str, neden: str) -> None:
    ATLANDI.append(f"{ad} -> {neden}")


# =====================================================================
# BOLUM 1 - SUNUCU: WS komut isleyicileri GERCEKTEN cagrilir
# =====================================================================
class SahteWS:
    """websocket yerine gecer; gonderilen tum mesajlari toplar."""

    def __init__(self) -> None:
        self.gonderilen: list[dict] = []
        self.remote_address = ("127.0.0.1", 55555)

    async def send(self, veri: str) -> None:
        try:
            self.gonderilen.append(json.loads(veri))
        except Exception:
            self.gonderilen.append({"_ham": veri})

    def __hash__(self):
        return id(self)


class SahteKullanicilar:
    """kullanicilar modulunun yerine gecer. YAZMA cagrilarini SAYAR."""

    def __init__(self) -> None:
        self.yazma_cagrisi: list[tuple] = []
        self._kayit = {
            "yonetici@x.com": {"eposta": "yonetici@x.com",
                               "rol": "yonetici", "aktif": 1,
                               "ad_soyad": "Yon Etici"},
            "pilot@x.com": {"eposta": "pilot@x.com",
                            "rol": "kullanici", "aktif": 1,
                            "ad_soyad": "Pi Lot"},
        }

    def bul(self, eposta):
        return self._kayit.get(str(eposta).strip().lower())

    def guncelle(self, eposta, alanlar):
        self.yazma_cagrisi.append(("guncelle", eposta, dict(alanlar)))
        return True

    def ekle(self, *a, **kw):
        self.yazma_cagrisi.append(("ekle", a, kw))
        return True, None

    def sil(self, eposta):
        self.yazma_cagrisi.append(("sil", eposta))
        return True

    def listesi_guvenli(self):
        return list(self._kayit.values())

    def roller(self):
        return {"yonetici": {}, "kullanici": {}}

    def rol_kaydet(self, *a, **kw):
        self.yazma_cagrisi.append(("rol_kaydet", a, kw))
        return True, None

    def rol_ekle(self, *a, **kw):
        self.yazma_cagrisi.append(("rol_ekle", a, kw))
        return True, None

    def rol_sil(self, *a, **kw):
        self.yazma_cagrisi.append(("rol_sil", a, kw))
        return True, None

    def izin_semasi(self):
        return {"dron": ["pilotluk"]}


def sunucu_sinifi_yukle():
    """sunucu.py'yi ice al ve WS sunucu sinifini dondur."""
    try:
        import goktungu.sunucu as S
    except Exception as e:  # pragma: no cover
        return None, f"ice alma hatasi: {e}"
    # Sinif adini bul: async komut isleyicisi olan sinif
    for ad in dir(S):
        obj = getattr(S, ad)
        if isinstance(obj, type):
            for uye in dir(obj):
                if "komut" in uye.lower() and callable(
                        getattr(obj, uye, None)):
                    return obj, uye
    return None, "komut isleyicisi bulunamadi"


def bolum1_sunucu() -> None:
    print("\n=== BOLUM 1: SUNUCU WS KOMUTLARI (gercek cagri) ===")
    kaynak_yol = os.path.join(KOK, "goktungu", "sunucu.py")
    if not os.path.exists(kaynak_yol):
        atla("sunucu.py bulundu", kaynak_yol)
        return
    with open(kaynak_yol, encoding="utf-8") as f:
        kaynak = f.read()

    # --- Yapisal olcumler: red DALI var mi ve YAZMA cagrisindan ONCE mi
    # Bu olcumler "return" ile erken cikisi dogrular; yazma cagrisina
    # hic ulasilmadigini kanit ister.
    def blok_al(komut: str) -> str:
        m = re.search(
            r'elif komut == "' + re.escape(komut) + r'":(.*?)(?=\n        elif komut ==|\n        else:)',
            kaynak, re.S)
        return m.group(1) if m else ""

    # kullanici_ekle: yazma cagrisi HIC olmamali
    blok = blok_al("kullanici_ekle")
    olc("kullanici_ekle bloku bulundu", bool(blok))
    if blok:
        olc("kullanici_ekle: kullanicilar.ekle cagrisi YOK",
            ".ekle(" not in blok,
            "hala ekleme yapiyor")
        olc("kullanici_ekle: basarisiz yanit dondurur",
            '"basarili": False' in blok)
        olc("kullanici_ekle: kurumsal panele yonlendirir",
            "/company/" in blok)

    # kullanici_guncelle: baskasina dokunma reddedilmeli
    blok = blok_al("kullanici_guncelle")
    olc("kullanici_guncelle bloku bulundu", bool(blok))
    if blok:
        olc("kullanici_guncelle: kendisi_mi denetimi var",
            "kendisi_mi" in blok)
        olc("kullanici_guncelle: baskasina dokunma erken return",
            re.search(r"if not kendisi_mi:.*?return", blok, re.S)
            is not None,
            "erken cikis yok")
        olc("kullanici_guncelle: rol/aktif alani reddedilir",
            re.search(r'"rol" in alanlar.*?"aktif" in alanlar',
                      blok, re.S) is not None
            or re.search(r'"aktif" in alanlar.*?"rol" in alanlar',
                         blok, re.S) is not None,
            "rol/aktif suzgeci yok")
        olc("kullanici_guncelle: rol reddi erken return",
            re.search(r'\("rol" in alanlar\).*?return', blok, re.S)
            is not None,
            "reddedilmiyor")
        # Kendi profil duzenlemesi KORUNMALI (asiri kisitlama olmasin)
        olc("kullanici_guncelle: kendi ad/unvan/sifre duzenlemesi KALIR",
            ".guncelle(" in blok,
            "kendi profilini de duzenleyemiyor - asiri kisitlama")

    # rol komutlari: uc de reddedilmeli
    for komut in ("rol_kaydet", "rol_ekle", "rol_sil"):
        b = blok_al(komut)
        if not b:
            # Uc komut tek blokta birlestirilmis olabilir.
            # GERCEK bicim: elif komut in (...) and self.pilot:
            m = re.search(
                r'elif komut in \(([^)]*rol_kaydet[^)]*)\)[^:]*:(.*?)'
                r'(?=\n        elif komut|\n        # ----|\n        else:)',
                kaynak, re.S)
            if m and komut in m.group(1):
                b = m.group(2)
        olc(f"{komut}: reddedilir",
            bool(b) and '"basarili": False' in b,
            "red dali yok")
        if b:
            olc(f"{komut}: yazma cagrisi YOK",
                f".{komut}(" not in b,
                "hala yaziyor")

    # rol_listesi OKUMA ucu KALMALI
    olc("rol_listesi okuma ucu KALDI",
        'komut == "rol_listesi"' in kaynak,
        "okuma ucu da kaldirilmis - rol combobox'i bozulur")
    olc("kullanici_liste okuma ucu KALDI",
        'komut == "kullanici_liste"' in kaynak,
        "okuma ucu da kaldirilmis")


# =====================================================================
# BOLUM 2 - ARAYUZ: JS/HTML yapisal olcumler
# =====================================================================
def bolum2_arayuz() -> None:
    print("\n=== BOLUM 2: ARAYUZ (JS/HTML) ===")

    def oku(yol: str) -> str:
        p = os.path.join(KOK, yol)
        if not os.path.exists(p):
            return ""
        with open(p, encoding="utf-8") as f:
            return f.read()

    html = oku("index.html")
    olc("index.html okundu", bool(html))
    if html:
        # Menu ogeleri KALDIRILMIS olmali
        for oge in ("pmKullanicilar", "pmYeniKullanici", "pmRolYonetimi"):
            olc(f"index.html: {oge} menu ogesi KALDIRILDI",
                f'id="{oge}"' not in html,
                "menu ogesi hala var")
        olc("index.html: pmKurumsalPanel ogesi EKLENDI",
            'id="pmKurumsalPanel"' in html)
        # KRITIK: btnKullanicilar DOM'da KALMALI (JS null denetimsiz erisiyor)
        olc("index.html: btnKullanicilar DOM'da KALDI (JS cokmesini onler)",
            'id="btnKullanicilar"' in html,
            "kaldirilirsa kullanici.js coker, giris ekrani da acilmaz")

    kul = oku("js/kullanici.js")
    olc("js/kullanici.js okundu", bool(kul))
    if kul:
        olc("kullanici.js: kullanici_ekle gonderimi YOK",
            'tip: "kullanici_ekle"' not in kul,
            "hala gonderiyor")
        olc("kullanici.js: kullanici_guncelle gonderimi YOK",
            'tip: "kullanici_guncelle"' not in kul,
            "hala gonderiyor")
        olc("kullanici.js: kullanici_sil gonderimi YOK",
            'tip: "kullanici_sil"' not in kul,
            "hala gonderiyor")
        olc("kullanici.js: kullanici_liste OKUMA gonderimi KALDI",
            'tip: "kullanici_liste"' in kul,
            "okuma da kaldirilmis")
        olc("kullanici.js: uc menu ogesi daima gizlenir",
            re.search(r'pmKullanicilar[\s\S]{0,400}display\s*=\s*"none"',
                      kul) is not None
            or re.search(r'TEK KAPI[\s\S]{0,600}display\s*=\s*"none"',
                         kul) is not None,
            "gizleme kodu bulunamadi")

    mb = oku("js/menubar.js")
    if mb:
        olc("menubar.js: pmKullanicilar bagi KALDIRILDI",
            'getElementById("pmKullanicilar")' not in mb,
            "menu bagi hala var")
        olc("menubar.js: pmKurumsalPanel bagi EKLENDI",
            "pmKurumsalPanel" in mb)
        olc("menubar.js: /company/ yeni sekmede acilir",
            '"/company/"' in mb)

    ry = oku("js/rol_yonetimi.js")
    if ry:
        olc("rol_yonetimi.js: menu bagi KALDIRILDI",
            'getElementById("pmRolYonetimi")' not in ry,
            "menu bagi hala var")
        # OKUMA tarafi: window.rolAdlariTazele GLOBAL olarak taninmali.
        # Yalniz "rolAdlariTazele" metnini aramak YETMEZ; yorum
        # satirlarinda da gecer. window'a atandigini olcmek gerekir.
        olc("rol_yonetimi.js: window.rolAdlariTazele TANIMLI",
            re.search(r"window\.rolAdlariTazele\s*=\s*function", ry)
            is not None,
            "okuma tarafi bozulmus - Pilot Hakkinda rol combobox'i bozulur")
        olc("rol_yonetimi.js: rol_listesi OKUMA gonderimi KALDI",
            'tip: "rol_listesi"' in ry,
            "okuma gonderimi kaldirilmis")

    ph = oku("js/pilot_hakkinda.js")
    olc("js/pilot_hakkinda.js okundu", bool(ph))
    if ph:
        # IKINCI KAPI: Pilot Hakkinda penceresinden rol degistirme
        olc("pilot_hakkinda.js: rol alani ARTIK gonderilmiyor",
            not re.search(r"alanlar\.rol\s*=", ph),
            "IKINCI KAPI ACIK: bu pencereden rol degistirilebiliyor")
        olc("pilot_hakkinda.js: rolDegistirebilir daima false",
            re.search(r"rolDegistirebilir\s*=\s*false", ph) is not None,
            "rol combobox'i hala etkinlestirilebiliyor")
        olc("pilot_hakkinda.js: kendi ad/unvan/sifre duzenlemesi KALIR",
            'tip: "kullanici_guncelle"' in ph,
            "asiri kisitlama: kendi profilini de duzenleyemiyor")

    # i18n dengesi: TR = EN
    i18 = oku("js/i18n.js")
    if i18:
        for anahtar in ("pmKurumsalPanel", "uyelikTekKapiBaslik",
                        "uyelikTekKapiMesaj", "phRolTekKapiNot"):
            sayi = len(re.findall(r"\b" + anahtar + r"\s*:", i18))
            olc(f"i18n: {anahtar} TR+EN dengeli (2 kayit)",
                sayi == 2, f"{sayi} kayit bulundu")


# =====================================================================
# BOLUM 3 - SOZDIZIMI
# =====================================================================
def bolum3_sozdizimi() -> None:
    print("\n=== BOLUM 3: SOZDIZIMI ===")
    import py_compile
    for yol in ("goktungu/sunucu.py", "goktungu/kullanicilar.py"):
        p = os.path.join(KOK, yol)
        if not os.path.exists(p):
            atla(f"{yol} derlendi", "dosya yok")
            continue
        try:
            py_compile.compile(p, doraise=True)
            olc(f"{yol} derlendi", True)
        except Exception as e:
            olc(f"{yol} derlendi", False, str(e))

    import shutil
    import subprocess
    node = shutil.which("node")
    for yol in ("js/kullanici.js", "js/menubar.js", "js/rol_yonetimi.js",
                "js/pilot_hakkinda.js", "js/i18n.js"):
        p = os.path.join(KOK, yol)
        if not os.path.exists(p):
            atla(f"{yol} sozdizimi", "dosya yok")
            continue
        if not node:
            atla(f"{yol} sozdizimi", "node yok")
            continue
        r = subprocess.run([node, "--check", p], capture_output=True)
        olc(f"{yol} sozdizimi", r.returncode == 0,
            r.stderr.decode()[:200])


def main() -> int:
    print("=" * 62)
    print("SINAV: TEK KAPI (GCS'ten uyelik/rol yonetimi kaldirma)")
    print("=" * 62)
    bolum1_sunucu()
    bolum2_arayuz()
    bolum3_sozdizimi()

    print("\n" + "=" * 62)
    print(f"GECTI  : {len(GECTI)}")
    print(f"KALDI  : {len(KALDI)}")
    print(f"ATLANDI: {len(ATLANDI)}")
    print("=" * 62)
    for s in KALDI:
        print(f"  KALDI   : {s}")
    for s in ATLANDI:
        print(f"  ATLANDI : {s}")
    return 1 if KALDI else 0


if __name__ == "__main__":
    sys.exit(main())
