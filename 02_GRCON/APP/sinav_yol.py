#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GOKTUNGU sinav betikleri icin ORTAK YOL COZUMLEME (v2.4.52).

NEDEN GEREKLI
-------------
v2.4.52 ile klasor yapisi degisti:

    ESKI (duz)              YENI (assets)
    <kok>/index.html        <kok>/assets/web/index.html
    <kok>/js/...            <kok>/assets/web/js/...
    <kok>/goktungu/...         <kok>/assets/python/goktungu/...
    <kok>/main.py           <kok>/main.py          (degismedi)

Sinav betikleri yollari duz yapiya GOMULU yaziyordu
(`os.path.join(KOK, "js", "surum.js")`). Yeni yapida bu yol
bulunamaz ve `oku()` bos dize dondurur. Sonuc SESSIZ ve YANILTICIDIR:

  * "icinde X gecmeli" bicimindeki maddeler bos metinde bulunamaz
    -> KALDI. Sinav yamanin bozuk oldugunu soyler, oysa yama saglamdir.
  * "icinde X GECMEMELI" bicimindeki maddeler bos metinde de saglanir
    -> OK. Bu daha tehlikelidir: gercekten bozuk bir yama sinavi GECER.

Bu modul yapiyi CALISMA ANINDA algilar ve iki yapida da dogru yolu
dondurur. Boylece ayni sinav, yamadan once (duz) ve sonra (assets)
degistirilmeden calisir.
"""
from __future__ import annotations

import os
import sys


def kok_bul(baslangic=None):
    """`main.py` iceren proje kokunu YUKARI dogru arar.

    Sinav betigi kokte de (`<kok>/sinav_x.py`) alt klasorde de
    (`<kok>/assets/python/sinavlar/sinav_x.py`) durabilir.
    """
    d = os.path.abspath(baslangic or os.path.dirname(
        os.path.abspath(sys.argv[0] if sys.argv[0] else __file__)))
    if os.path.isfile(d):
        d = os.path.dirname(d)
    for _ in range(6):
        if os.path.isfile(os.path.join(d, "main.py")):
            return d
        ust = os.path.dirname(d)
        if ust == d:
            break
        d = ust
    # Bulunamadi: calisilan dizini kok say (eski davranis)
    return os.path.abspath(os.getcwd())


KOK = kok_bul()

# --- Yapi algilama --------------------------------------------------
# Olcut DOSYA VARLIGIDIR, klasor varligi degil: bos bir `assets/web`
# klasoru tasima yarim kaldiginda olusabilir ve yanlis yapi secilir.
_ASSETS_WEB = os.path.join(KOK, "assets", "web")
_ASSETS_PY = os.path.join(KOK, "assets", "python")

YENI_YAPI = (os.path.isfile(os.path.join(_ASSETS_WEB, "index.html"))
             or os.path.isdir(os.path.join(_ASSETS_PY, "goktungu")))

WEB_KOKU = _ASSETS_WEB if YENI_YAPI else KOK
PY_KOKU = _ASSETS_PY if YENI_YAPI else KOK
VERI_KOKU = os.path.join(KOK, "veri") if YENI_YAPI else KOK

YAPI_ADI = "assets" if YENI_YAPI else "duz"


def web(*parcalar):
    """Web varliginin (HTML/JS/CSS) tam yolu."""
    return os.path.join(WEB_KOKU, *parcalar)


def py(*parcalar):
    """Python kaynaginin tam yolu."""
    return os.path.join(PY_KOKU, *parcalar)


def veri(*parcalar):
    """Calisma zamani verisinin tam yolu."""
    return os.path.join(VERI_KOKU, *parcalar)


def kok(*parcalar):
    """Proje kokune gore yol (main.py, kur_*.sh gibi)."""
    return os.path.join(KOK, *parcalar)


def _oku_yol(yol):
    if not os.path.isfile(yol):
        return ""
    with open(yol, encoding="utf-8", errors="replace") as f:
        return f.read()


def web_oku(*parcalar):
    return _oku_yol(web(*parcalar))


def py_oku(*parcalar):
    return _oku_yol(py(*parcalar))


def kok_oku(*parcalar):
    return _oku_yol(kok(*parcalar))


# --- Eski sinavlar icin tek noktadan esleme -------------------------
# Eski sinavlar `os.path.join(KOK, *parcalar)` yaziyordu. Yeni yapida
# ilk parcaya bakarak dogru koke yonlendirmek yeterlidir; boylece
# 400+ satirlik sinav govdelerine dokunmaya gerek kalmaz.
_WEB_ILK = {
    "js", "css", "lib", "pwa",
    "index.html", "flight.html", "video.html",
    "manifest.json", "sw.js", "dron.glb",
    "logo.png", "gokkubbe.png", "veilox.png", "novixair.png",
}
_PY_ILK = {
    "goktungu", "ai_sunucu.py", "istasyon2", "araclar",
    "requirements.txt",
}
_BETIK_ILK = {
    "kiosk_baslat.sh", "servis_kur.sh", "goktungu.service.sablon",
}


def coz(*parcalar):
    """Duz yapiya gore yazilmis yolu, gecerli yapida cozer.

    Ornek: coz("js", "surum.js")
      duz   -> <kok>/js/surum.js
      yeni  -> <kok>/assets/web/js/surum.js
    """
    if not parcalar:
        return KOK
    # Tek dizede birlesik yol gelebilir: "goktungu/pg.py"
    duz = []
    for p in parcalar:
        duz.extend(str(p).replace("\\", "/").split("/"))
    duz = [p for p in duz if p not in ("", ".")]
    if not duz:
        return KOK
    if not YENI_YAPI:
        return os.path.join(KOK, *duz)
    ilk = duz[0]
    if ilk in _WEB_ILK:
        return os.path.join(WEB_KOKU, *duz)
    if ilk in _PY_ILK:
        return os.path.join(PY_KOKU, *duz)
    if ilk in _BETIK_ILK:
        return os.path.join(PY_KOKU, "betikler", *duz)
    if ilk == "veri":
        return os.path.join(KOK, *duz)
    if ilk == "main.py":
        return os.path.join(KOK, *duz)
    if ilk.endswith(".md"):
        return os.path.join(KOK, "assets", "belgeler", *duz)
    if ilk.startswith("sinav_") or ilk.startswith("dene_") \
            or ilk.startswith("olc_"):
        return os.path.join(PY_KOKU, "sinavlar", *duz)
    # Bilinmeyen: once kok, sonra veri/ denenir.
    aday = os.path.join(KOK, *duz)
    if os.path.exists(aday):
        return aday
    aday2 = os.path.join(KOK, "veri", *duz)
    return aday2 if os.path.exists(aday2) else aday


def coz_oku(*parcalar):
    """`coz()` ile bulunan dosyanin icerigi (yoksa bos dize)."""
    return _oku_yol(coz(*parcalar))


def ice_aktarma_yolu_kur():
    """`import goktungu` calissin diye Python kokunu sys.path'e ekler."""
    for p in (PY_KOKU, KOK):
        if p not in sys.path:
            sys.path.insert(0, p)


def ozet():
    return ("YAPI=%s  KOK=%s  WEB=%s  PY=%s"
            % (YAPI_ADI, KOK, WEB_KOKU, PY_KOKU))


if __name__ == "__main__":
    print(ozet())
    print("index.html :", os.path.isfile(web("index.html")))
    print("goktungu/pg.py:", os.path.isfile(py("goktungu", "pg.py")))
    print("main.py    :", os.path.isfile(kok("main.py")))
