# -*- coding: utf-8 -*-
"""GOKTUNGU — Drone GCS Angajman Sistemi backend paketi.

Moduller (her sinif kendi dosyasinda):
    sabitler      : Tum sabitler ve dosya yollari
    konsol        : KonsolLog       — merkezi konsol/log tamponu
    ayarlar       : AyarYoneticisi  — gcs_ayarlar.json kaliciligi
    kullanicilar  : KullaniciYoneticisi — kimlik dogrulama + kullanici DB
    lokasyonlar   : LokasyonYoneticisi  — kayitli lokasyonlar
    kayit         : KayitYoneticisi     — radar kaydi + tekrar oynatma
    dron          : DronYoneticisi      — MAVLink baglanti + telemetri + komut
    radar         : RadarIstemcisi      — C20 radar protokolu + saglik
    angajman      : AngajmanYoneticisi  — interceptor gudum dongusu
    sunucu        : WSSunucusu, HttpSunucusu — arayuz koprusu
    takip         : Takip paketi (Takipci, Iz, KalmanEksen, GNN, ayarlar)

Giris noktasi: main.py (proje kokunde)
"""

# ---------------------------------------------------------------------
# SURUM — TEK KAYNAK  (v2.4.29)
# Onceden burada elle yazilmis "2.0.0" duruyordu; web arayuzu ise
# js/surum.js icindeki GCS_SURUM degerini gosteriyordu. Iki kaynak
# birbirinden kopmustu (Python 2.0.0 / arayuz 2.4.23).
# Artik surum yalnizca js/surum.js icinde tanimlanir ve buradan
# okunur. Dosya bulunamazsa son bilinen surume duser.
# ---------------------------------------------------------------------
import os as _os
import re as _re

_SON_BILINEN = "2.4.252"


def _surum_oku():
    """js/surum.js icindeki GCS_SURUM degerini okur.

    v2.4.52: klasor yapisi degisti; `js/` artik `assets/web/js/`
    altinda. Yalniz eski yol denenirse dosya bulunamaz ve kod
    SESSIZCE `_SON_BILINEN` degerine duser — surum yanlis gorunur,
    hicbir hata verilmez. Bu yuzden aday yollar SIRAYLA denenir:

      1. `<kok>/assets/web/js/surum.js`  (v2.4.52+ yeni yapi)
      2. `<kok>/js/surum.js`             (v2.4.51 ve oncesi duz yapi)

    `sabitler.py` ice ALINMAZ: bu kod paket ilklendirmesinde calisir,
    dairesel ice alma riski vardir.
    """
    paket = _os.path.dirname(_os.path.abspath(__file__))
    ust1 = _os.path.dirname(paket)      # .../assets/python | <kok>
    adaylar = []
    if (_os.path.basename(ust1) == "python"
            and _os.path.basename(_os.path.dirname(ust1)) == "assets"):
        # YENI yapi: paket <kok>/assets/python/goktungu icinde
        _assets = _os.path.dirname(ust1)
        _kok = _os.path.dirname(_assets)
        adaylar.append(_os.path.join(_assets, "web", "js", "surum.js"))
        adaylar.append(_os.path.join(_kok, "js", "surum.js"))
    else:
        # ESKI duz yapi: paket <kok>/goktungu icinde
        adaylar.append(_os.path.join(ust1, "js", "surum.js"))
        adaylar.append(_os.path.join(ust1, "assets", "web", "js",
                                     "surum.js"))
    for yol in adaylar:
        try:
            with open(yol, "r", encoding="utf-8") as f:
                bas = f.read(2048)  # GCS_SURUM ilk satirlarda tanimli
            m = _re.search(r'GCS_SURUM\s*=\s*["\']([0-9][0-9.]*)["\']',
                           bas)
            if m:
                return m.group(1)
        except Exception:
            continue
    return _SON_BILINEN


__version__ = _surum_oku()
