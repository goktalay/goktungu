# -*- coding: utf-8 -*-
"""Statik sunum sizinti engeli: yardimci sabitler ve `_statik_engelli_mi`.

Bu modul `sunucu.py`den DAVRANIS-KORUYUCU olarak ayrilmistir (Risk 6,
kademeli modulerlestirme ilk adimi). Icerik BIREBIR tasinmistir; mantik,
sabit, string ve sira DEGISTIRILMEMISTIR.

Geriye tam uyumluluk: `sunucu.py` bu moduldeki tum isimleri
`from .sunucu_yardimci import *` ile yeniden disa acar; boylece
`goktungu.sunucu._statik_engelli_mi`, `goktungu.sunucu._STATIK_ENGEL_ONEK`
gibi mevcut erisimler AYNEN calisir.

Bagimlilik: yalniz standart kutuphane (re, posixpath, urllib.parse).
Orijinal modulden HICBIR sey ice almaz -> import dongusu YOKTUR.
"""
import posixpath
import re
import urllib.parse

__all__ = [
    "_STATIK_ENGEL_UZANTI",
    "_STATIK_IZIN_TAM",
    "_STATIK_IZIN_ONEK",
    "_STATIK_ENGEL_ONEK",
    "_STATIK_ENGEL_DESEN",
    "_statik_engelli_mi",
]


# ----------------------------------------------------------------- #
# STATIK SUNUM SIZINTI ENGELI (v2.4.70, BULGU_04)                   #
#                                                                   #
# OLCULEN ACIK: /app/veri/pg.json 200 donuyordu ve icinde veritabani #
# parolasi vardi; /app/main.py ve /app/goktungu/*.py kaynak kodu     #
# aciktı; dizin listelemesi etkindi. Sebep: duz kurulum yapisinda    #
# WEB_KOKU == PROJE_KOKU, yani Python kaynagi ve `veri/` web         #
# varliklariyla ayni dizinde.                                        #
#                                                                   #
# KARA LISTE, BEYAZ LISTE DEGIL: beyaz liste 40+ js dosyasini tek    #
# tek saymak zorunda kalir; yeni dosya eklendiginde SESSIZCE 404     #
# doner ve arayuz kirilir (olculen sinif: `ai_yuzler` vakasi).       #
#                                                                   #
# 404 DONER (403 DEGIL): 403 dosyanin varligini dogrular.            #
# ----------------------------------------------------------------- #
_STATIK_ENGEL_UZANTI = (
    # kaynak kod
    ".py", ".pyc", ".pyo", ".pyd", ".sh", ".bat", ".ps1",
    # yapilandirma ve veri
    ".json", ".ini", ".cfg", ".conf", ".yaml", ".yml", ".toml",
    ".log", ".db", ".sqlite", ".sqlite3", ".sql", ".jsonl",
    # sir ve sertifika
    ".env", ".pem", ".key", ".crt", ".csr", ".p12", ".pfx", ".jks",
    # yedek
    ".bak", ".adbak", ".orij", ".orig", ".eski", ".old", ".save",
    ".swp", ".swo", ".tmp", ".rej", ".patch", ".diff",
    # paket
    ".deb", ".exe", ".msi", ".aab", ".apk",
)

# PWA ve surum bilgisi web katmaninin ISLEVSEL parcasi: engellenirse
# uygulama kurulamaz (manifest) ya da surum kontrolu kirilir.
# Tam yol esitligi aranir; `/veri/manifest.json` gibi yollar ACILMAZ.
_STATIK_IZIN_TAM = frozenset((
    "/manifest.json",
    "/sw.js",
    "/js/surum.js",
))
# FAZ18-IS29: ISLEVSEL ONEK IZNI (olculen kusur: Cesium sahnesi hic
# kurulmuyordu).
#
# `.json` uzantisi `_STATIK_ENGEL_UZANTI` icinde KALIR: /veri/pg.json
# sizintisi (BULGU_04) geri gelmemeli. Ancak ucuncu parti kutuphaneler
# ISLEVSEL .json varliklari tasir ve bunlar engellenince arayuz
# sessizce kirilir:
#   /lib/Cesium/Assets/approximateTerrainHeights.json  (arazi yuksekligi)
#   /lib/Cesium/Assets/IAU2006_XYS/IAU2006_XYS_*.json  (gok referansi)
# Bu iki varlik reddedilince Cesium `promise` reddiyle coker ve SAHNE
# OLUSMAZ; dron ikonu, lokasyon ikonu, cetvel ve rota isaretcileri
# BIRLIKTE gorunmez oldu (dort belirti, tek kok neden).
#
# NEDEN ONEK, TEK TEK DOSYA DEGIL: Cesium 30 .json varligi tasir ve
# surum yukseltmesinde bu liste degisir. Tek tek saymak, yeni surumde
# SESSIZ 404 uretir -- kara liste yorumunda anlatilan `ai_yuzler`
# sinifinin aynisi.
#
# GUVENLIK OLCUMU: /lib/ altinda riskli uzanti (.py/.env/.pem/.key/
# .db/.log/.conf/.sh) 0 dosya; sir izi (password/secret/token) tasiyan
# .json 0 dosya. Icerik yalniz Cesium, flightindicators, fontawesome,
# hls.min.js, jquery.min.js.
#
# YOL GECISI: bu denetim normpath SONRASINDA yapilir, bu yuzden
# `/lib/../veri/pg.json` istegi `/veri/pg.json` olarak normalize edilir
# ve `_STATIK_ENGEL_ONEK` tarafindan engellenmeye DEVAM eder.
_STATIK_IZIN_ONEK = (
    "/lib/",
)

# Hassas ust duzey dizinler: icerigi web varligi DEGIL.
# `/veri/` burada; `_VERI_ESLEME` eslemeleri istek yolunu
# `/avatars/` ve `/ai_yuzler/` olarak korur, `/veri/` olarak GELMEZ,
# bu yuzden esleme bozulmaz (olculdu).
_STATIK_ENGEL_ONEK = (
    "/veri/",
    "/sertifika/",
    "/goktungu/",
    "/ai_modeller/",
    "/araclar/",
    "/python/",
    "/assets/python/",
)

_STATIK_ENGEL_DESEN = re.compile(
    r"(^|/)\."                 # gizli dosya/dizin: /.git/config
    r"|~$"                      # editor yedegi: index.html~
    r"|(^|/)__pycache__(/|$)"   # derlenmis Python
    r"|_yedek(_|/|$)"           # veri_yedek_2105/
    r"|yedek_arsiv"
    r"|(^|/)requirements\.txt$"
    r"|(^|/)calisma\.json$",
    re.IGNORECASE,
)


def _statik_engelli_mi(yol: str) -> bool:
    """Istek yolu hassas bir kaynaga mi isaret ediyor.

    Yol NORMALLESTIRILIR: `/js/../veri/pg.json` gibi istekler onek
    denetimini atlatmasin. `SimpleHTTPRequestHandler.translate_path`
    kendi icinde de temizlik yapar, ancak engel karari ONCE verildigi
    icin normalizasyon burada tekrarlanir (savunma katmanlari
    birbirine guvenmez).
    """
    d = (yol or "").split("?", 1)[0].split("#", 1)[0]
    try:
        d = urllib.parse.unquote(d)
    except Exception:
        pass
    d = d.replace("\\", "/")
    # posixpath.normpath `/js/../veri` -> `/veri` yapar; sonda `/`
    # kaybolur, bu yuzden dizin isteginde geri eklenir.
    dizin_istegi = d.endswith("/")
    d = posixpath.normpath(d)
    if not d.startswith("/"):
        d = "/" + d
    if dizin_istegi and not d.endswith("/"):
        d += "/"
    alt = d.lower()
    if alt in _STATIK_IZIN_TAM:
        return False
    # FAZ18-IS29: islevsel onek izni. UZANTI denetiminden ONCE, ancak
    # ONEK/DESEN engellerinden ONCE DEGIL -- asagidaki engel denetimleri
    # calismaya devam eder. Boylece /lib/ altindaki .json varliklari
    # servis edilirken /veri/, /goktungu/, gizli dosya ve yedek
    # engelleri bozulmaz.
    if alt.startswith(_STATIK_IZIN_ONEK):
        if not alt.startswith(_STATIK_ENGEL_ONEK):
            if not _STATIK_ENGEL_DESEN.search(alt):
                return False
    if alt.endswith(_STATIK_ENGEL_UZANTI):
        return True
    if alt.startswith(_STATIK_ENGEL_ONEK):
        return True
    return bool(_STATIK_ENGEL_DESEN.search(alt))
