# -*- coding: utf-8 -*-
"""GÖKTUNGU MERKEZ — TLS/SNI baglam yardimcilari.

Bu modul `mk_sunucu.py`den DAVRANIS-KORUYUCU olarak ayrilmistir (Risk 6,
kademeli modulerlestirme). Icerik BIREBIR tasinmistir; mantik, sabit,
string, sira ve global durum DEGISTIRILMEMISTIR.

Icerik: SNI ad eslesme (`_ad_uyar_mi`), sertifika SAN/CN cozumu
(`_sertifika_adlari`), coklu-sertifika SNI baglami kurulumu
(`tls_baglamlari`) ve surec-genelinde tek kez kurulan onbellekli birincil
baglam (`tls_baglam_kur`).

Geriye tam uyumluluk: `mk_sunucu.py` bu moduldeki isimleri
`from mk_sunucu_tls import *` (+ altcizgili adlar icin acik liste) ile
yeniden disa acar; boylece `mk_sunucu.tls_baglam_kur`,
`mk_sunucu.tls_baglamlari` gibi mevcut erisimler AYNEN calisir.

DIKKAT: `_TLS_ONBELLEK` ve `_TLS_KILIT` global onbellek durumudur;
`tls_baglam_kur` bunlari kullanir. Bu global durum, onu okuyan/yazan tum
fonksiyonlarla BIRLIKTE tasindi, boylece tutarli kalir.

Bagimliliklar: stdlib (ssl, os, threading) ve `mk_ayar.ayar_oku`.
`mk_ayar` `mk_sunucu`yu import ETMEZ -> import dongusu YOKTUR.
"""
from __future__ import annotations

import os
import ssl
import threading

from mk_ayar import ayar_oku

__all__ = [
    "_TLS_ONBELLEK",
    "_TLS_KILIT",
    "_ad_uyar_mi",
    "_sertifika_adlari",
    "tls_baglamlari",
    "tls_baglam_kur",
]


# ==========================================================================
# v2.4.71 — SNI ÇOĞULLAMALI TLS BAĞLAMI
# ==========================================================================
# Merkez tek süreçte birden çok alan adı taşır:
#   * goktungu.com + *.goktungu.com  (Sectigo wildcard, birincil)
#   * gozcu.veilox.com.tr            (Let's Encrypt, eski adres)
#
# Önceki kod tek `load_cert_chain` çağrısı yapıyordu; sonuç olarak hangi
# alan adı istenirse istenmesin AYNI sertifika sunuluyordu ve eski adrese
# gelen tarayıcı `ERR_CERT_COMMON_NAME_INVALID` alıyordu. Çözüm SNI:
# istemci el sıkışmada hangi adı istediğini söyler, `sni_callback` o ada
# uyan bağlamı soketle eşler.
#
# NEDEN `sni_callback` ve `set_servername_callback` DEĞİL: Python'da
# `sni_callback` bağlamı doğrudan değiştirmeye izin verir
# (`soket.context = ...`); bu, sertifika seçiminin el sıkışma
# tamamlanmadan yapılmasını sağlar.
#
# DİKKAT: Geri çağrı içinde YÜKSELTİLEN istisna el sıkışmayı sessizce
# düşürür ve hata ayıklaması çok zordur. Bu yüzden gövde tümüyle
# korumalıdır ve başarısızlıkta birincil bağlama düşer.

_TLS_ONBELLEK: dict[str, ssl.SSLContext] = {}
_TLS_KILIT = threading.Lock()


def _ad_uyar_mi(desen: str, ad: str) -> bool:
    """Sertifika adı deseninin istenen ada uyup uymadığını söyler.

    Joker karakter YALNIZCA en soldaki etikette ve TEK etiketi karşılar
    (RFC 6125): `*.goktungu.com` → `app.goktungu.com` uyar,
    `a.b.goktungu.com` UYMAZ, `goktungu.com` UYMAZ.
    """
    desen = (desen or "").strip().lower().rstrip(".")
    ad = (ad or "").strip().lower().rstrip(".")
    if not desen or not ad:
        return False
    if desen == ad:
        return True
    if desen.startswith("*."):
        kok = desen[2:]
        if not ad.endswith("." + kok):
            return False
        return "." not in ad[: -(len(kok) + 1)]
    return False


def _sertifika_adlari(crt_yolu: str) -> list[str]:
    """Sertifikadaki SAN (yoksa CN) adlarını döndürür.

    `ssl._ssl._test_decode_cert` özel bir işlevdir ancak ek bağımlılık
    (cryptography) getirmeden PEM'i çözmenin tek yerleşik yoludur.
    Başarısız olursa boş liste döner; çağıran dosya adına düşer.
    """
    adlar: list[str] = []
    try:
        bilgi = ssl._ssl._test_decode_cert(crt_yolu)  # noqa: SLF001
        for tur, deger in bilgi.get("subjectAltName", ()):
            if tur.lower() == "dns":
                adlar.append(deger)
        if not adlar:
            for demet in bilgi.get("subject", ()):
                for anahtar, deger in demet:
                    if anahtar == "commonName":
                        adlar.append(deger)
    except Exception as e:
        print(f"[TLS] {crt_yolu} adlari okunamadi: {e}")
    return adlar


def tls_baglamlari() -> tuple[ssl.SSLContext | None,
                              list[tuple[list[str], ssl.SSLContext]]]:
    """(birincil bağlam, [(adlar, bağlam), ...]) döndürür.

    Birincil bağlam ayar dosyasındaki `sertifika` girdisidir ve SNI
    göndermeyen istemcilere sunulur. `ek_sertifikalar` listesindeki her
    girdi ayrıca yüklenir.
    """
    a = ayar_oku()
    girdiler: list[dict] = []
    ana = a.get("sertifika") or {}
    if ana.get("crt") and ana.get("key"):
        girdiler.append(dict(ana))
    for ek in (a.get("ek_sertifikalar") or []):
        if isinstance(ek, dict) and ek.get("crt") and ek.get("key"):
            girdiler.append(dict(ek))

    yuklu: list[tuple[list[str], ssl.SSLContext]] = []
    birincil: ssl.SSLContext | None = None
    for g in girdiler:
        crt, key = g["crt"], g["key"]
        if not (os.path.isfile(crt) and os.path.isfile(key)):
            print(f"[TLS] Atlandi (dosya yok): {crt}")
            continue
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            # TLS 1.0/1.1 ve zayif sifreler kapali: SSL Labs A notu ve
            # PCI uyumu icin gerekli. TLS 1.2 tabanı korunur cunku
            # sahadaki Windows 8.1 ve eski Android istemciler 1.3
            # konusamaz.
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.load_cert_chain(crt, key)
        except Exception as e:
            print(f"[TLS] Yuklenemedi {crt}: {e}")
            continue
        adlar = g.get("adlar") or _sertifika_adlari(crt)
        yuklu.append((adlar, ctx))
        if birincil is None:
            birincil = ctx
        print(f"[TLS] Yuklendi: {crt} -> {', '.join(adlar) or '(ad yok)'}")

    if birincil is not None and len(yuklu) > 1:
        def _sni(soket, istenen_ad, _ctx):  # noqa: ANN001, ANN202
            try:
                if not istenen_ad:
                    return None          # birincil bağlamda kal
                for adlar, ctx in yuklu:
                    for d in adlar:
                        if _ad_uyar_mi(d, istenen_ad):
                            soket.context = ctx
                            return None
            except Exception:
                pass                     # sessizce birincile düş
            return None

        for _adlar, ctx in yuklu:
            ctx.sni_callback = _sni

    return birincil, yuklu


def tls_baglam_kur() -> ssl.SSLContext | None:
    """Süreç genelinde tek kez kurulan TLS bağlamını döndürür.

    HTTPS dinleyicisi ve WebSocket dinleyicisi AYNI bağlamı paylaşır;
    böylece sertifika yolu tek yerden yönetilir ve iki dinleyicinin
    farklı sertifika sunması gibi bir tutarsızlık oluşamaz.
    """
    with _TLS_KILIT:
        hazir = _TLS_ONBELLEK.get("birincil")
        if hazir is not None:
            return hazir
        birincil, _ = tls_baglamlari()
        if birincil is not None:
            _TLS_ONBELLEK["birincil"] = birincil
        return birincil
