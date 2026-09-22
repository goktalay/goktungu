# -*- coding: utf-8 -*-
"""GÖKTUNGU MERKEZ — GZIP sikistirma yardimcilari (IS67_GZIP_v1).

Bu modul `mk_sunucu.py`den DAVRANIS-KORUYUCU olarak ayrilmistir (Risk 6,
kademeli modulerlestirme ilk adimi). Icerik BIREBIR tasinmistir; mantik,
sabit, string, sira ve global durum DEGISTIRILMEMISTIR.

Geriye tam uyumluluk: `mk_sunucu.py` bu moduldeki isimleri
`from mk_sunucu_yardimci import *` ile yeniden disa acar; boylece
`mk_sunucu._gz_sikistir`, `mk_sunucu._gz_uygun_mu` gibi mevcut
erisimler AYNEN calisir.

Bagimlilik: yalniz standart kutuphane (gzip, hashlib, threading,
collections.OrderedDict). `mk_sunucu` veya diger mk_* modullerinden
HICBIR sey ice almaz -> import dongusu YOKTUR.

DIKKAT: `_gz_boyut` global durumu `_gz_sikistir` icinde `global` ile
guncellenir; onbellek durumu (`_gz_onbellek`, `_gz_kilit`, `_gz_boyut`)
bu modulle BIRLIKTE tasindi, boylece global baglam tutarli kalir.
"""
from __future__ import annotations

__all__ = [
    "_GZ_TURLER",
    "_GZ_ALT_SINIR",
    "_GZ_SEVIYE",
    "_GZ_ONBELLEK_TAVAN",
    "_gz_onbellek",
    "_gz_kilit",
    "_gz_boyut",
    "_gz_uygun_mu",
    "_gz_sikistir",
    "_json_varsayilan",
]

# JSON serilestirme yardimcisi: `json.dumps(..., default=_json_varsayilan)`
# icin varsayilan donusturucu. `mk_sunucu.py`den DAVRANIS-KORUYUCU olarak
# BIREBIR tasinmistir. Yalniz stdlib `datetime`e baglidir -> import
# dongusu YOKTUR.
import datetime as dt
from typing import Any


def _json_varsayilan(x: Any) -> Any:
    if isinstance(x, (dt.datetime, dt.date)):
        return x.isoformat()
    if isinstance(x, dt.timedelta):
        return x.total_seconds()
    if hasattr(x, "__str__"):
        return str(x)
    raise TypeError(type(x))


# ==========================================================================
# IS67 — GZIP SIKISTIRMA (isaret: IS67_GZIP_v1)
# ==========================================================================
# OLCUM: app arayuzu 111 kaynak / 10.48 MB ham; gzip-6 ile 2.82 MB
# (%73.1 kazanc). Sunucu daha once HIC sikistirmiyordu.
#
# CPU TUZAGI: Cesium.js'i her istekte sikistirmak 239 ms yakar. Bu
# yuzden sikisik govde bellekte onbelleklenir; anahtar ham govdenin
# (uzunluk, sha1) ikilisidir. Vekil yolunda dosya yolu/mtime YOKTUR,
# elimizde yalniz govde vardir — tek tutarli anahtar icerigin ozetidir.
import gzip as _gzip
import hashlib as _hashlib
import threading as _threading
from collections import OrderedDict as _OrderedDict

# Sikistirilacak icerik turleri. Zaten sikisik olanlar (jpeg/png/zip/
# mp4/woff2...) DISARIDA: yeniden sikistirmak dosyayi BUYUTUR.
_GZ_TURLER = (
    "text/", "application/javascript", "application/json",
    "application/xml", "application/xhtml+xml", "image/svg+xml",
    "application/manifest+json", "application/wasm",
)
# gzip basligi ~20 bayt; bunun altinda kazanc yok, CPU bosa gider.
_GZ_ALT_SINIR = 1024
# Seviye 6: olculdu, seviye 1'e gore Cesium'da 247 KB daha kazandiriyor.
# Onbellek sayesinde CPU maliyeti dosya basina BIR KEZ odenir.
_GZ_SEVIYE = 6
# Onbellek tavani: en buyuk 12 kaynak toplami ~9 MB; 64 MB rahat yeter.
_GZ_ONBELLEK_TAVAN = 64 * 1024 * 1024

_gz_onbellek: "_OrderedDict[tuple, bytes]" = _OrderedDict()
_gz_kilit = _threading.Lock()
_gz_boyut = 0


def _gz_uygun_mu(tur: str, govde: bytes, istek_basliklari) -> bool:
    """Bu yanit sikistirilmali mi? Tum kapilar burada."""
    if not govde or len(govde) < _GZ_ALT_SINIR:
        return False
    t = (tur or "").split(";")[0].strip().lower()
    if not any(t.startswith(x) or t == x for x in _GZ_TURLER):
        return False
    try:
        kabul = (istek_basliklari.get("Accept-Encoding") or "").lower()
    except Exception:
        return False
    return "gzip" in kabul


def _gz_sikistir(govde: bytes) -> bytes:
    """Sikisik govdeyi dondurur; ayni icerik icin bir kez hesaplanir."""
    global _gz_boyut
    anahtar = (len(govde), _hashlib.sha1(govde).digest())
    with _gz_kilit:
        v = _gz_onbellek.get(anahtar)
        if v is not None:
            _gz_onbellek.move_to_end(anahtar)
            return v
    # Sikistirma KILIT DISINDA yapilir: 239 ms'lik Cesium sikistirmasi
    # kilidi tutsaydi tum es zamanli istekler beklerdi.
    sikisik = _gzip.compress(govde, _GZ_SEVIYE)
    # Sikisik hali daha buyukse (rastgele/zaten sikisik veri) ham kalir.
    if len(sikisik) >= len(govde):
        return govde
    with _gz_kilit:
        if anahtar not in _gz_onbellek:
            _gz_onbellek[anahtar] = sikisik
            _gz_boyut += len(sikisik)
            while _gz_boyut > _GZ_ONBELLEK_TAVAN and _gz_onbellek:
                _, eski = _gz_onbellek.popitem(last=False)
                _gz_boyut -= len(eski)
    return sikisik
