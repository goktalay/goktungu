# -*- coding: utf-8 -*-
"""GÖKTUNGU MERKEZ — kurum logosu cozumleme ve saklama yardimcilari.

Bu modul `mk_sunucu.py`den DAVRANIS-KORUYUCU olarak ayrilmistir (Risk 6,
kademeli modulerlestirme). Icerik BIREBIR tasinmistir; mantik, sabit,
string ve sira DEGISTIRILMEMISTIR.

Icerik: logo klasoru/sinir/tur sabitleri (`LOGO_DIZIN`, `LOGO_MAKS_BAYT`,
`LOGO_TURLERI`), `data:` URL cozucusu (`logo_coz`) ve diske yazip
`firmalar.logo_yol`u guncelleyen `logo_yaz`.

Geriye tam uyumluluk: `mk_sunucu.py` bu moduldeki isimleri
`from mk_sunucu_logo import *` ile yeniden disa acar; boylece
`mk_sunucu.logo_coz`, `mk_sunucu.logo_yaz`, `mk_sunucu.LOGO_DIZIN` gibi
mevcut erisimler AYNEN calisir.

Bagimliliklar: stdlib (os, base64, secrets), `mk_ayar.VERI_KOKU` ve
`mk_db` (veritabani erisimi icin `db.deger` / `db.calistir`). `mk_ayar`
ve `mk_db` `mk_sunucu`yu import ETMEZ -> import dongusu YOKTUR.
"""
from __future__ import annotations

import base64
import os

from mk_ayar import VERI_KOKU
import mk_db as db

__all__ = [
    "LOGO_DIZIN",
    "LOGO_MAKS_BAYT",
    "LOGO_TURLERI",
    "logo_coz",
    "logo_yaz",
]


# ======================================================================
# v2.4.53 Faz 4 — KURUM LOGOSU
# ======================================================================
# Logo, kurum /company/ altinda kayit olurken yuklenir ve merkezde
# saklanir. /app/ altindaki GOKTUNGU arayuzu giris yaptiginda kendi
# kurumunun logosuyla acilir; ucus raporu antedi de ayni logoyu
# kullanir. Boylece kullanici hangi bilgisayardan girerse girsin
# kurumsal kimlik korunur.
LOGO_DIZIN = os.path.join(VERI_KOKU, "varlik", "logo")
LOGO_MAKS_BAYT = 2 * 1024 * 1024          # 2 MB
LOGO_TURLERI = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}


def logo_coz(veri_url):
    """`data:` URL'sini (tur, baytlar) ikilisine cozer.

    Donus: (uzanti, baytlar, hata). Hata varsa ilk iki deger None.

    NEDEN data URL: kayit formu tek JSON istegi gonderir; multipart
    kullanmak icin hem istemci hem sunucu tarafinda ayri bir ayristirici
    gerekirdi. Logo boyutu 2 MB ile sinirli oldugu icin base64
    genislemesi (%33) kabul edilebilir.
    """
    s = str(veri_url or "").strip()
    if not s:
        return None, None, None                # logo istege bagli
    if not s.startswith("data:"):
        return None, None, "Logo bicimi taninmadi"
    basl, _, govde64 = s.partition(",")
    if not govde64:
        return None, None, "Logo verisi bos"
    tur = basl[5:].split(";")[0].strip().lower()
    uzanti = LOGO_TURLERI.get(tur)
    if not uzanti:
        return None, None, ("Desteklenmeyen logo turu: %s "
                            "(PNG, JPEG, WEBP veya SVG kullanin)" % tur)
    if "base64" not in basl:
        return None, None, "Logo base64 kodlanmis olmali"
    import base64 as _b64
    try:
        baytlar = base64.b64decode(govde64, validate=False)
    except Exception:
        return None, None, "Logo verisi cozulemedi"
    if not baytlar:
        return None, None, "Logo verisi bos"
    if len(baytlar) > LOGO_MAKS_BAYT:
        return None, None, ("Logo cok buyuk (%.1f MB); en fazla 2 MB"
                            % (len(baytlar) / 1048576.0))
    # Ikili imza denetimi: uzanti ile gercek icerik uyusmuyorsa dosya
    # sunucuda yanlis Content-Type ile sunulur.
    if uzanti == ".png" and not baytlar.startswith(b"\x89PNG"):
        return None, None, "Dosya gercek bir PNG degil"
    if uzanti == ".jpg" and not baytlar.startswith(b"\xff\xd8"):
        return None, None, "Dosya gercek bir JPEG degil"
    if uzanti == ".webp" and baytlar[8:12] != b"WEBP":
        return None, None, "Dosya gercek bir WEBP degil"
    if uzanti == ".svg":
        try:
            bas = baytlar[:400].decode("utf-8", "ignore").lower()
        except Exception:
            bas = ""
        if "<svg" not in bas:
            return None, None, "Dosya gercek bir SVG degil"
        # SVG icinde betik calistirilabilir; kurum logosunda buna
        # gerek yoktur ve saklanan dosya baska kullanicilara sunulur.
        if "<script" in baytlar.decode("utf-8", "ignore").lower():
            return None, None, "SVG icinde betik bulundu; kabul edilmez"
    return uzanti, baytlar, None


def logo_yaz(firma_id, veri_url):
    """Logoyu diske yazar ve `firmalar.logo_yol` degerini gunceller.

    Donus: (logo_yol|None, hata|None). Logo bos ise (None, None).
    """
    uzanti, baytlar, hata = logo_coz(veri_url)
    if hata:
        return None, hata
    if not baytlar:
        return None, None
    import secrets as _sec
    os.makedirs(LOGO_DIZIN, exist_ok=True)
    # Rastgele belirtec: firma_id tahmin edilerek baska kurumun logosu
    # dogrudan /varlik/ yolundan cekilemesin.
    ad = "firma_%d_%s%s" % (int(firma_id), _sec.token_hex(8), uzanti)
    tam = os.path.join(LOGO_DIZIN, ad)
    try:
        with open(tam, "wb") as f:
            f.write(baytlar)
    except OSError as e:
        return None, "Logo kaydedilemedi: %s" % e
    goreli = "logo/" + ad
    # Eski logo dosyasi varsa silinir; aksi halde her guncellemede
    # disk sisirilir.
    try:
        eski = db.deger(
            "SELECT logo_yol FROM firmalar WHERE firma_id = %s",
            (int(firma_id),))
        if eski and str(eski) != goreli:
            e_tam = os.path.join(VERI_KOKU, "varlik", str(eski))
            if os.path.isfile(e_tam) and os.path.realpath(
                    e_tam).startswith(os.path.realpath(LOGO_DIZIN)):
                os.remove(e_tam)
    except Exception:
        pass
    try:
        db.calistir(
            "UPDATE firmalar SET logo_yol = %s, guncel_ts = now()"
            " WHERE firma_id = %s", (goreli, int(firma_id)))
    except Exception as e:
        return None, "Logo yolu yazilamadi: %s" % e
    return goreli, None
