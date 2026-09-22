# -*- coding: utf-8 -*-
"""GÖKTUNGU MERKEZ — statik sunum sizinti engeli yardimcilari.

Bu modul `mk_sunucu.py`den DAVRANIS-KORUYUCU olarak ayrilmistir (Risk 6,
kademeli modulerlestirme). Icerik BIREBIR tasinmistir; mantik, sabit,
string ve sira DEGISTIRILMEMISTIR.

Iki bagimsiz engel katmani burada birlikte durur:
  1. `_yedek_yolu_mu` + `_ENGELLI_UZANTI` / `_ENGELLI_DESEN`
     (yedek/kaynak/gizli dosya engeli; statik sunumun ILK kapisi).
  2. `_app_engelli_mi` + `_APP_*` sabitleri (`/app/` vekili icin ikinci
     katman sizinti engeli). Bu katman `_ENGELLI_DESEN`'e BAGLIDIR, bu
     yuzden ikisi ayni module tasinmistir.

Geriye tam uyumluluk: `mk_sunucu.py` bu moduldeki isimleri
`from mk_sunucu_statik import *` ile yeniden disa acar; boylece
`mk_sunucu._yedek_yolu_mu`, `mk_sunucu._app_engelli_mi`,
`mk_sunucu._ENGELLI_DESEN` gibi mevcut erisimler AYNEN calisir.

Bagimlilik: yalniz standart kutuphane (re, posixpath, urllib.parse).
`mk_sunucu` veya diger mk_* modullerinden HICBIR sey ice almaz ->
import dongusu YOKTUR.
"""
from __future__ import annotations

import posixpath
import re
import urllib.parse

__all__ = [
    "_ENGELLI_UZANTI",
    "_ENGELLI_DESEN",
    "_yedek_yolu_mu",
    "_APP_ENGEL_UZANTI",
    "_APP_IZIN_TAM",
    "_APP_IZIN_ONEK",
    "_APP_ENGEL_DESEN",
    "_APP_ENGEL_ONEK",
    "_app_engelli_mi",
]


# ----------------------------------------------------------------- #
# YEDEK / KAYNAK DOSYA DESEN ENGELI                                  #
#                                                                    #
# Bu sunucuda nginx YOKTUR; statik dosyalari bu surec sunuyor.       #
# nginx'in ontanimli "yedek uzantisini sunma" korumasi burada        #
# bulunmadigi icin engel elle kurulur.                               #
#                                                                    #
# 2026-08-17 denetiminde olculdu: gecis sirasinda birakilan 13       #
# `.adbak` dosyasi ve 2 panel yedek dizini HTTP 200 donuyordu.       #
# Sizan icerik: eski marka, eski alan adi, yururlukten kalkmis KVKK  #
# metni ve panel kaynak kodu.                                        #
#                                                                    #
# 404 doner (403 DEGIL): 403 dosyanin varligini dogrular ve          #
# saldirgana harita cizer.                                           #
# ----------------------------------------------------------------- #
_ENGELLI_UZANTI = (
    ".adbak", ".bak", ".orij", ".orig", ".eski", ".old",
    ".save", ".swp", ".swo", ".tmp", ".rej", ".patch", ".diff",
)
_ENGELLI_DESEN = re.compile(
    r"(^|/)\."              # nokta ile baslayan (gizli) dosya ya da dizin
    r"|~$"                  # editor yedegi: dosya.html~
    r"|_yedek(_|/|$)"       # company_yedek_2105/
    r"|yedek_arsiv"         # arsiv dizini
    r"|(^|/)__pycache__(/|$)",
    re.IGNORECASE,
)


def _yedek_yolu_mu(yol: str) -> bool:
    """Yol bir yedek/kaynak/gizli dosyaya mi isaret ediyor."""
    d = (yol or "").lower()
    if d.endswith(_ENGELLI_UZANTI):
        return True
    return bool(_ENGELLI_DESEN.search(d))


# ----------------------------------------------------------------- #
# /app/ VEKILI ICIN SIZINTI ENGELI (BULGU_04)                       #
#                                                                   #
# `_dosya_sun` icindeki `_yedek_yolu_mu` engeli /app/ dalini KAPSAMAZ:#
# vekil dali YOL_TABLOSU'ndan once donuyor (satir ~492). Olculen     #
# sizinti: /app/veri/pg.json veritabani parolasini donduruyordu.     #
#                                                                   #
# Bu, app tarafindaki engelin IKINCI katmanidir. Iki katman ayni     #
# oruntuleri bagimsiz olarak sorgular; biri kaldirilirsa digeri      #
# sizintiyi durdurur.                                               #
# ----------------------------------------------------------------- #
_APP_ENGEL_UZANTI = (
    ".py", ".pyc", ".pyo", ".pyd", ".sh", ".bat", ".ps1",
    ".json", ".ini", ".cfg", ".conf", ".yaml", ".yml", ".toml",
    ".log", ".db", ".sqlite", ".sqlite3", ".sql", ".jsonl",
    ".env", ".pem", ".key", ".crt", ".csr", ".p12", ".pfx", ".jks",
)

# PWA islevi icin zorunlu; engellenirse uygulama kurulamaz.
# Yol `/app/` onegi SOYULDUKTAN sonra karsilastirilir.
_APP_IZIN_TAM = frozenset((
    "/manifest.json",
    "/sw.js",
    "/js/surum.js",
))
# FAZ18-IS29: ISLEVSEL ONEK IZNI (vekil katmani).
#
# OLCULEN KUSUR: `.json` kara listesi Cesium'un ISLEVSEL varliklarini
# da vuruyordu ve harita SAHNESI hic kurulmuyordu:
#   /lib/Cesium/Assets/approximateTerrainHeights.json  (arazi yuksekligi)
#   /lib/Cesium/Assets/IAU2006_XYS/IAU2006_XYS_*.json  (gok referansi)
# Ikisi de reddedilince Cesium `promise` reddiyle coker; dron ikonu,
# lokasyon ikonu, cetvel ve rota isaretcileri BIRLIKTE gorunmez olur
# (dort belirti, tek kok neden).
#
# BU KATMAN NICIN AYRI YAMALANIR: yukaridaki yorumda anlatildigi gibi
# app ve vekil kara listeleri BILINCLI olarak birbirinden bagimsizdir.
# Bagimsizlik sizinti karsisinda degerlidir, ancak ISLEVSEL izin de
# iki katmanda AYNI olmak zorundadir; yoksa App 200 dondururken vekil
# 404 doner (olculdu).
#
# NEDEN ONEK, TEK TEK DOSYA DEGIL: Cesium 30 .json varligi tasir ve
# surum yukseltmesinde liste degisir; tek tek saymak yeni surumde
# SESSIZ 404 uretir.
#
# GUVENLIK OLCUMU: /lib/ altinda riskli uzanti 0 dosya, sir izi
# (password/secret/token) tasiyan .json 0 dosya.
#
# YOL GECISI: denetim normpath ve unquote SONRASINDA yapilir, bu yuzden
# `/lib/../veri/pg.json` ve `%2e%2e` kodlamalari `/veri/pg.json` olarak
# normalize edilir ve `_APP_ENGEL_ONEK` tarafindan engellenmeye DEVAM
# eder.
_APP_IZIN_ONEK = (
    "/lib/",
)

# /app/ dalina OZEL desenler. Genel `_ENGELLI_DESEN` degistirilmez:
# o desen /company/ ve /admin/ dallarinda da kullanilir ve orada
# `requirements.txt` mesru bir kurulum belgesi olabilir.
_APP_ENGEL_DESEN = re.compile(
    r"(^|/)requirements\.txt$"
    r"|(^|/)calisma\.json$"
    r"|(^|/)__pycache__(/|$)"
    r"|\.txt$",
    re.IGNORECASE,
)

_APP_ENGEL_ONEK = (
    "/veri/",
    "/sertifika/",
    "/goktungu/",
    "/ai_modeller/",
    "/araclar/",
    "/python/",
    "/assets/python/",
)


def _app_engelli_mi(ic_yol: str) -> bool:
    """`/app/` onegi soyulmus yol hassas bir kaynaga mi isaret ediyor.

    Yol NORMALLESTIRILIR: `/js/../veri/pg.json` onek denetimini
    atlatmasin. Yuzde kodlamasi da cozulur (`%2e%2e`).
    """
    d = (ic_yol or "").split("?", 1)[0].split("#", 1)[0]
    try:
        d = urllib.parse.unquote(d)
    except Exception:
        pass
    d = d.replace("\\", "/")
    dizin_istegi = d.endswith("/")
    d = posixpath.normpath(d)
    if not d.startswith("/"):
        d = "/" + d
    if dizin_istegi and not d.endswith("/"):
        d += "/"
    alt = d.lower()
    if alt in _APP_IZIN_TAM:
        return False
    # FAZ18-IS29: islevsel onek izni. Engel ONEK ve DESEN denetimleri
    # bu izinden BAGIMSIZ uygulanmaya devam eder; boylece /lib/
    # altindaki .json varliklari servis edilirken /veri/, /goktungu/,
    # __pycache__ ve yedek engelleri bozulmaz.
    if alt.startswith(_APP_IZIN_ONEK):
        if not alt.startswith(_APP_ENGEL_ONEK):
            if not _APP_ENGEL_DESEN.search(alt):
                if not _ENGELLI_DESEN.search(alt):
                    return False
    if alt.endswith(_APP_ENGEL_UZANTI):
        return True
    if alt.startswith(_APP_ENGEL_ONEK):
        return True
    if _APP_ENGEL_DESEN.search(alt):
        return True
    return bool(_ENGELLI_DESEN.search(alt))
