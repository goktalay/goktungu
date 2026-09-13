#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GRCOFF 2.5.21 yerel AI -> angajman altyapisi regresyon testi.

Fiziksel cihaz, ag, gercek kamera veya dron KULLANMAZ; veritabani da
gerektirmez (kamera saglayici taklit edilir). Dogrulanan:
  * yerel_hedef.YerelHedefBesleyici piksel -> cografi konum cozumu,
  * iki kamera tipi (sabit yer duzlemi / drona takili gorunen boyut),
  * hedef_deposu cozucu entegrasyonu ve konum_guvenilir kapisi,
  * KameraYoneticisi._kalibrasyon_dogrula kalibre bayragi kurallari,
  * kalibresiz/yasak sinif/kayip olay davranislari.

Ayrica 2.5.20 PASIF TAKIP SOZLESMESININ (NDJSON) yerel besleme kolu
tarafindan BOZULMADIGINI dogrular.

Calistirma:
    python3.11 test_grcoff_yerel_angajman_20260912.py
"""
import json
import math
import os
import pathlib
import sys
import tempfile

# Kaynak agaci GORELI cozulur (sabit mutlak yol YOK).
KOK = (pathlib.Path(__file__).resolve().parent.parent.parent
       / "01_GRCOFF" / "KAYNAK")
if not (KOK / "goktungu").is_dir():
    raise SystemExit("GRCOFF kaynagi bulunamadi: %s" % KOK)
sys.path.insert(0, str(KOK))

from goktungu import hedef_deposu                       # noqa: E402
from goktungu.kameralar import KameraYoneticisi         # noqa: E402
from goktungu.yerel_hedef import (                      # noqa: E402
    YerelHedefBesleyici, YEREL_ORNEK_TABAN)


def konsol(*_a, **_k):
    return None


class SahteKameralar:
    """DB'siz kamera saglayici: kamera_id -> kayit dict."""
    def __init__(self, kayitlar):
        self._k = kayitlar

    def bul(self, kamera_id):
        return self._k.get(int(kamera_id))


def esit(gercek, beklenen, ad):
    if gercek != beklenen:
        raise AssertionError("%s: %r != %r" % (ad, gercek, beklenen))


def yakin(gercek, beklenen, tol, ad):
    if gercek is None or abs(gercek - beklenen) > tol:
        raise AssertionError("%s: %r, beklenen %r +-%r" %
                             (ad, gercek, beklenen, tol))


def test_kalibrasyon_dogrula():
    """Saf kalibrasyon dogrulayici: kalibre bayragi kurallari."""
    d = KameraYoneticisi._kalibrasyon_dogrula
    # Eksik sabit kalibrasyon -> kalibre 0
    esit(d({"kamera_tipi": "sabit", "lat": 39.0})["kalibre"], 0,
         "eksik sabit -> kalibresiz")
    # Tam sabit kalibrasyon -> kalibre 1
    tam = d({"kamera_tipi": "sabit", "lat": 39.0, "lon": 32.0,
             "kam_yukseklik": 30.0, "yon": 0.0, "tilt": 30.0,
             "fov_yatay": 60.0, "fov_dikey": 40.0})
    esit(tam["kalibre"], 1, "tam sabit -> kalibre")
    # Gecersiz FOV -> kalibre 0
    esit(d({"kamera_tipi": "sabit", "lat": 39.0, "lon": 32.0,
            "kam_yukseklik": 30.0, "yon": 0.0, "tilt": 30.0,
            "fov_yatay": 0.0, "fov_dikey": 40.0})["kalibre"], 0,
         "gecersiz fov -> kalibresiz")
    # Dron kamera montaj eksik -> 0
    esit(d({"kamera_tipi": "dron", "dron_uid": "d1",
            "fov_yatay": 60.0, "fov_dikey": 40.0})["kalibre"], 0,
         "dron montajsiz -> kalibresiz")
    # Dron kamera tam -> 1
    esit(d({"kamera_tipi": "dron", "dron_uid": "d1",
            "fov_yatay": 60.0, "fov_dikey": 40.0,
            "montaj_pan": 0.0, "montaj_tilt": 0.0,
            "montaj_roll": 0.0})["kalibre"], 1, "dron tam -> kalibre")
    # Dron kamera uid'siz -> 0
    esit(d({"kamera_tipi": "dron", "dron_uid": "",
            "fov_yatay": 60.0, "fov_dikey": 40.0,
            "montaj_pan": 0.0, "montaj_tilt": 0.0,
            "montaj_roll": 0.0})["kalibre"], 0, "dron uid'siz -> kalibresiz")
    # Gecersiz tip -> sabit'e duser
    esit(d({"kamera_tipi": "sacma"})["kamera_tipi"], "sabit",
         "gecersiz tip -> sabit")
    print("KALIBRASYON_DOGRULA: 7/7 gecti")


def test_sabit_kara_hedefi():
    """Sabit kamera, kara hedefi: yer duzlemi mesafesi."""
    depo = hedef_deposu.HedefDeposu()
    kam = {1: {"isim": "S1", "kalibre": 1, "kamera_tipi": "sabit",
               "lat": 39.0, "lon": 32.0, "kam_yukseklik": 30.0,
               "yon": 0.0, "tilt": 30.0, "fov_yatay": 60.0,
               "fov_dikey": 40.0, "dron_uid": ""}}
    b = YerelHedefBesleyici(konsol, SahteKameralar(kam), depo)
    # Merkez hedef: isin egimi = tilt = 30 -> slant = H/sin30 = 60 m,
    # yatay menzil = H/tan30 = ~51.96 m kuzeyde.
    olay = {"kamera_id": 1, "sinif": "insan", "track_id": 11,
            "kutu_px": [630, 350, 650, 370], "merkez_px": [640, 360],
            "kare_boyutu": [1280, 720], "ts": 1.0}
    s = b.ai_olayi(olay)
    if not s.get("tamam"):
        raise AssertionError("sabit kara hedefi cozulemedi: %r" % s)
    esit(s["ornek_id"], YEREL_ORNEK_TABAN + 1, "ornek_id")
    if not (s["lat"] > 39.0):
        raise AssertionError("kuzeydeki hedef lat artmali: %r" % s["lat"])
    yakin(s["lon"], 32.0, 1e-4, "merkez hedef lon ~ kamera lon")
    yakin(s["lat"], 39.0 + 51.96 / 111320.0, 5e-5, "sabit hedef lat")
    cz = depo.hedef_bul(s["ornek_id"], 1, 11, firma_id=None)
    esit(bool(cz["konum_guvenilir"]), True, "konum_guvenilir")
    yakin(cz["alt"], 0.0, 1.0, "kara hedefi yer seviyesinde")
    # Kayip olay depoyu temizler
    b.ai_olayi({"kamera_id": 1, "kayip": True, "track_id": 11})
    if depo.hedef_bul(s["ornek_id"], 1, 11, firma_id=None):
        raise AssertionError("kayip sonrasi hedef silinmeliydi")
    print("SABIT_KARA_HEDEFI: gecti")


def test_sabit_hava_hedefi():
    """Sabit kamera, hava araci (dron): gorunen boyut mesafesi."""
    depo = hedef_deposu.HedefDeposu()
    kam = {1: {"isim": "S1", "kalibre": 1, "kamera_tipi": "sabit",
               "lat": 39.0, "lon": 32.0, "kam_yukseklik": 30.0,
               "yon": 0.0, "tilt": 10.0, "fov_yatay": 60.0,
               "fov_dikey": 40.0, "dron_uid": ""}}
    b = YerelHedefBesleyici(konsol, SahteKameralar(kam), depo)
    olay = {"kamera_id": 1, "sinif": "hava_araci", "track_id": 21,
            "kutu_px": [620, 200, 660, 240], "merkez_px": [640, 220],
            "kare_boyutu": [1280, 720], "ts": 2.0, "guven": 0.9}
    s = b.ai_olayi(olay)
    if not s.get("tamam"):
        raise AssertionError("hava araci cozulemedi: %r" % s)
    odak_d = 720.0 / (2.0 * math.tan(math.radians(40.0) / 2.0))
    yakin(s["mesafe_m"], 1.0 * odak_d / 40.0, 1.0, "hava araci mesafe")
    if not (s["mesafe_guven"] < 0.6):
        raise AssertionError("gorunen-boyut guveni dusuk olmali: %r"
                             % s["mesafe_guven"])
    print("SABIT_HAVA_HEDEFI (dron tespiti): gecti")


def test_retler():
    """Kalibresiz kamera, yasak sinif ve bagli olmayan dron kamerasi."""
    depo = hedef_deposu.HedefDeposu()
    kam = {
        2: {"isim": "kalibresiz", "kalibre": 0, "kamera_tipi": "sabit"},
        1: {"isim": "S1", "kalibre": 1, "kamera_tipi": "sabit",
            "lat": 39.0, "lon": 32.0, "kam_yukseklik": 30.0, "yon": 0.0,
            "tilt": 30.0, "fov_yatay": 60.0, "fov_dikey": 40.0},
        3: {"isim": "dron-kam", "kalibre": 1, "kamera_tipi": "dron",
            "dron_uid": "drn-A", "fov_yatay": 60.0, "fov_dikey": 40.0,
            "montaj_pan": 0.0, "montaj_tilt": 0.0, "montaj_roll": 0.0},
    }
    b = YerelHedefBesleyici(konsol, SahteKameralar(kam), depo, dron=None)
    r = b.ai_olayi({"kamera_id": 2, "sinif": "insan", "track_id": 5,
                    "kutu_px": [1, 2, 3, 4], "merkez_px": [10, 10],
                    "kare_boyutu": [1280, 720]})
    esit(r["tamam"], False, "kalibresiz kamera reddedildi")
    r = b.ai_olayi({"kamera_id": 1, "sinif": "yuz", "track_id": 9,
                    "kutu_px": [1, 2, 3, 4], "merkez_px": [640, 360],
                    "kare_boyutu": [1280, 720]})
    esit(r["tamam"], False, "yasak sinif reddedildi")
    # dron=None -> hareketli cozum kaynak dronu bulamaz -> ret
    r = b.ai_olayi({"kamera_id": 3, "sinif": "hava_araci", "track_id": 3,
                    "kutu_px": [620, 200, 660, 240], "merkez_px": [640, 220],
                    "kare_boyutu": [1280, 720], "ts": 3.0})
    esit(r["tamam"], False, "dron bagli degilken hareketli hedef reddedildi")
    print("RETLER: 3/3 gecti")


def test_ndjson_sozlesmesi():
    """2.5.20 NDJSON sozlesmesi yerel besleme ile BOZULMAMALI."""
    from goktungu.ai_yonetici import AIYonetici
    with tempfile.TemporaryDirectory(prefix="grcoff-ndjson-") as td:
        yol = os.path.join(td, "track_verisi.ndjson")
        yon = AIYonetici(konsol, {})
        yon.hedef_besleyici = None
        yon._track_yol = yol
        yon._kamera_dron_uid = lambda kid: "drn-x" if kid == 7 else None
        yon.takipler[7] = {"tur": "insan", "track_id": "k7"}
        sonuc = yon.takip_isle({
            "kamera_id": 7, "tur": "insan", "ts": 1726100000.25,
            "kutu": [10, 20, 30, 40], "merkez": [25.0, 40.0],
            "kare_boyutu": [1280, 720], "guven": 0.87, "kayip": False})
        if not sonuc.get("tamam"):
            raise AssertionError("NDJSON olayi yazilamadi: %r" % sonuc)
        with open(yol, "r", encoding="utf-8") as f:
            olay = json.loads(f.readline())
        beklenen_alan = {"surum", "olay", "ts", "kamera_id", "dron_uid",
                         "track_id", "sinif", "kutu_px", "merkez_px",
                         "kare_boyutu", "guven", "durum"}
        esit(set(olay.keys()), beklenen_alan, "NDJSON kanonik alan kumesi")
        for yasak in ("lat", "lon", "alt", "mesafe_m", "komut", "joystick"):
            if yasak in olay:
                raise AssertionError("NDJSON sozlesmesine sizinti: %s" % yasak)
        esit(olay["durum"], "aktif", "NDJSON durum")
    print("NDJSON_SOZLESME_KORUNDU: gecti")


if __name__ == "__main__":
    test_kalibrasyon_dogrula()
    test_sabit_kara_hedefi()
    test_sabit_hava_hedefi()
    test_retler()
    test_ndjson_sozlesmesi()
    print("TUM YEREL ANGAJMAN TESTLERI GECTI")
