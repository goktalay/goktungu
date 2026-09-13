# -*- coding: utf-8 -*-
"""
SISTEM BAKIM KIPI — FAZ18-IS24-BAKIM-KIPI
==========================================

NEDEN AYRI MODUL (ad cakismasi tuzagi)
--------------------------------------
`mk_bakim.py` ADI ZATEN VAR ve TAMAMEN BASKA bir kavramı yönetir:
kiracının *bakım/güncelleme aboneliği* süresi (`bakim_bitis`,
`odeme_durumu`). Bir müşterinin bakım aboneliğinin bitmesi ile
sistemin bakıma alınması ilgisiz iki olaydır. Aynı modüle eklenirse
"bakım" kelimesi kodda çift anlamlı olur.

NEDEN AYRI DOSYA, `merkez_ayar.json` DEGIL  (OLCUMLE DUZELTILDI)
----------------------------------------------------------------
Ilk tasarımda bayrak `merkez_ayar.json` içinde tutulacaktı ve gerekçe
"`ayar_oku()` her çağrıda diskten okur" varsayımıydı. **Bu varsayım
ölçümle çürütüldü:** `mk_ayar.ayar_oku()` süreç ömrü boyunca
`_ayar_onbellek` sözlüğünde önbelleğe alır. Ölçüm: bayrak diske
yazıldı, kayıt uçları hâlâ 400 döndü, durum ucu `acik: false` dedi.

Bakım kipinin tek anlamlı kullanım biçimi ANINDA açılıp kapanmasıdır.
Her açma/kapama için servisi yeniden başlatmak, tam da korumaya
çalıştığı anda sistemi kesintiye uğratır — kendi amacını yok eder.

Bu yüzden bayrak KENDI dosyasında tutulur ve `mtime` denetimiyle
okunur: dosya değişmediyse bellekteki değer kullanılır (her istekte
disk okuması yapılmaz), değiştiyse anında yeniden okunur.

NEDEN 503, 403 DEGIL
--------------------
403 "yetkin yok" der ve kullanıcıyı kendi hesabında sorun aramaya
yönlendirir. 503 (Service Unavailable) geçici kullanılamazlığın doğru
karşılığıdır, `Retry-After` taşıyabilir ve arama motorları kalıcı
kusur saymaz.

MUAFIYET ILKESI
---------------
Bakım kipi YALNIZ yeni kayıt/başvuru akışını durdurur. Mevcut
kullanıcıların girişi, App çalışması, köprü trafiği ve e-posta
doğrulaması tamamlama HIC etkilenmez. Aksi halde bakım kipi,
korumaya çalıştığı sistemi kullanılamaz hale getirirdi.

Yarım kalmış doğrulamalar özellikle muaftır: kullanıcı bakım
başlamadan önce kayıt olmuş ve doğrulama beklemede olabilir; bu akışı
kesmek onu hiçbir zaman tamamlanamayacak bir durumda bırakır.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any

from mk_ayar import VERI_KOKU

# Bayrak dosyası. `merkez_ayar.json` YANINDA ama AYRI:
# ayar önbelleğinden bağımsız okunması gerekiyor (yukarıdaki gerekçe).
BAKIM_DOSYA = os.path.join(VERI_KOKU, "sistem_bakim.json")

# Bakım kipinde REDDEDILECEK uçlar.
#
# Bu küme kasıtlı DAR: yalnız YENI kayıt yaratan uçlar. Bir uç buraya
# eklenirken sorulacak soru: "Bu uç engellenirse hâlihazırda sistemi
# kullanan biri engellenir mi?" Yanıt evet ise uç buraya GIRMEZ.
KAPALI_UCLAR = {
    "/api/firma/kayit",
    "/api/bireysel/kayit",
}

VARSAYILAN_MESAJ = (
    "Sistem şu anda bakım aşamasındadır. Yeni kayıtlar geçici olarak "
    "alınamıyor. Lütfen daha sonra yeniden deneyin."
)

_kilit = threading.Lock()
_onbellek: dict[str, Any] = {}
_mtime: float = -1.0


def _yapilandirma() -> dict[str, Any]:
    """Bayrak dosyasını `mtime` denetimiyle okur.

    Dosya yoksa bakım kipi KAPALI kabul edilir: kip opt-in'dir.
    Dosya bozuksa da kapalı kabul edilir — okunamayan bir dosya
    yüzünden kayıt akışını kapatmak kusuru büyütmek olurdu.
    """
    global _onbellek, _mtime
    try:
        m = os.path.getmtime(BAKIM_DOSYA)
    except BaseException:
        # Dosya yok: kip kapalı.
        with _kilit:
            _onbellek = {}
            _mtime = -1.0
        return {}
    with _kilit:
        if m == _mtime:
            return _onbellek
    try:
        with open(BAKIM_DOSYA, "r", encoding="utf-8") as f:
            v = json.load(f)
        if not isinstance(v, dict):
            v = {}
    except BaseException:
        v = {}
    with _kilit:
        _onbellek = v
        _mtime = m
        return v


def acik_mi() -> bool:
    """Bakım kipi etkin mi."""
    return bool(_yapilandirma().get("acik"))


def mesaj() -> str:
    """Kullanıcıya gösterilecek metin."""
    m = _yapilandirma().get("mesaj")
    if isinstance(m, str) and m.strip():
        return m.strip()
    return VARSAYILAN_MESAJ


def bitis() -> str | None:
    """Tahmini bitiş zamanı (bilgilendirme amaçlı, serbest metin)."""
    b = _yapilandirma().get("bitis")
    if isinstance(b, str) and b.strip():
        return b.strip()
    return None


def durum() -> dict[str, Any]:
    """Arayüzün okuyacağı genel durum nesnesi."""
    return {"acik": acik_mi(), "mesaj": mesaj(), "bitis": bitis()}


def uc_kapali_mi(uc: str) -> bool:
    """Verilen uç, bakım kipi nedeniyle reddedilmeli mi.

    Sorgu sırası önemli: önce uç kümede mi diye bakılır, sonra kip
    okunur. Böylece bakım kipiyle ilgisi olmayan uçlarda dosya
    denetimi hiç yapılmaz.
    """
    if (uc or "") not in KAPALI_UCLAR:
        return False
    return acik_mi()


def yanit_govdesi() -> dict[str, Any]:
    """503 ile birlikte yazılacak gövde.

    `bakim: True` bayrağı arayüzün bu yanıtı olağan bir doğrulama
    hatasından ayırt etmesini sağlar.
    """
    g: dict[str, Any] = {"hata": mesaj(), "bakim": True}
    b = bitis()
    if b:
        g["bitis"] = b
    return g


def yaz(acik: bool, mesaj_metni: str | None = None,
        bitis_metni: str | None = None) -> dict[str, Any]:
    """Bayrağı atomik olarak yazar (admin ucu ve komut satırı için).

    Atomik yazım (`os.replace`) zorunlu: yazma sırasında okunan
    yarım dosya, JSON ayrıştırma hatasıyla kipin sessizce kapanmasına
    yol açardı.
    """
    v: dict[str, Any] = {"acik": bool(acik)}
    if mesaj_metni and mesaj_metni.strip():
        v["mesaj"] = mesaj_metni.strip()
    if bitis_metni and bitis_metni.strip():
        v["bitis"] = bitis_metni.strip()
    gecici = BAKIM_DOSYA + ".yeni"
    os.makedirs(os.path.dirname(BAKIM_DOSYA), exist_ok=True)
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(v, f, ensure_ascii=False, indent=2)
    os.replace(gecici, BAKIM_DOSYA)
    return durum()
