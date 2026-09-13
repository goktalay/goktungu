# -*- coding: utf-8 -*-
"""GOKTUNGU Merkez Uygulama — CEVRIMDISI lisans dogrulamasi.

NE ISE YARAR
    Merkez Uygulama (5.000 $ tek seferlik) satin alan sirketin kurulumu,
    kendi lisans belgesini INTERNETE CIKMADAN dogrular.

NEDEN CEVRIMDISI (kullanici istegi, birebir)
    "merkez uygulamayi satin alan sirket sinirsiz kullanim hakkina sahip
     oluyor. isterse KAPALI DEVRE kullanabiliyor."

    Kapali devre demek: makinenin internet erisimi YOK. Lisansi merkeze
    sorarak dogrulayan bir tasarim, tam bu musteride yazilimi hic
    acilmaz hale getirir. Bu yuzden:

      - acik anahtar PAKETE GOMULUDUR (asagida ACIK_ANAHTAR_B64)
      - dogrulama tamamen yerel; hicbir HTTP cagrisi YOK
      - lisans dosyasi kullanicinin veri dizinindedir

NEDEN `cryptography` ZORUNLU BAGIMLILIK DEGIL
    Lisans dogrulamasi yazilimin ACILMASI icin sarttir. Onu kurulum
    sirasinda C uzantisi derlenmesi gereken bir pakete baglamak,
    "parasini odemis musteri yazilimi hic acamadi" riskini dogurur.
    Bu yuzden iki yol var:

      1. `cryptography` kuruluysa onun Ed25519 dogrulayicisi (hizli)
      2. Kurulu degilse SAF PYTHON yedek (bu dosyada, ~70 satir)

    Yedek YALNIZ DOGRULAMA yapar, IMZALAMA yapmaz. Gizli anahtar
    istemciye hic inmedigi icin (imzayi merkez atar) yan kanal
    sizintisi endisesi de yoktur; dogrulanan veri ve imza zaten
    acikca tasinan verilerdir.

IMZA SOZLESMESI (mk_yetki.py'den OLCULDU, varsayilmadi)
    Govde:
        {"surum": 1, "firma_id": <int>, "firma_unvan": <str>,
         "lisans_uid": <str>,
         "yetkiler": {"sinirsiz": true, "ai": bool,
                      "radar": bool, "gccdual": bool, "m50": bool}}

    `m50` eski imzalı lisanslarda bulunmaz; eksik alan güvenli olarak
    kapalı yorumlanır.

    Kanonik bayt:
        json.dumps(govde, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False).encode("utf-8")

    `sort_keys=True` ve `ensure_ascii=False` imzanin PARCASIDIR; biri
    degisirse imza dogrulanmaz. `separators` bosluk uretmemek icin.

    Imza: ham Ed25519 (64 bayt), STANDART base64 (urlsafe DEGIL).

    DIKKAT: `lisans_uid` govdeye imzadan ONCE eklenir (mk_yetki.py'de
    olculen ve duzeltilen kusur buydu). Dolayisiyla burada dogrulanan
    govde de `lisans_uid` ICERMELIDIR.
"""

import base64
import hashlib
import json
import os

# ----------------------------------------------------------------------
# MERKEZIN ACIK ANAHTARI — pakete gomulu.
#
# Kaynak: GET https://goktungu.com/api/genel/imza_anahtari
# Bu deger merkezin `veri/imza/` altindaki Ed25519 anahtar ciftinin
# ACIK yarisidir. Gizli yari YALNIZ merkez sunucudadir.
#
# Anahtar dondurulurse (rotate) bu sabit guncellenip yeni surum
# yayinlanmalidir. Anahtari calisma aninda indirmek KAPALI DEVRE
# kurulumda imkansiz oldugu icin bilincli olarak gomulu tutulur.
# ----------------------------------------------------------------------
ACIK_ANAHTAR_B64 = "ZDnJD1vKUwNUkfAx84JcGoRHsU3Vwyh4s/CHzZXCVRo="

LISANS_DOSYA_ADI = "merkez_lisans.json"


# ======================================================================
# Ed25519 dogrulama — saf Python yedek
# ======================================================================
# RFC 8032 referans uygulamasinin DOGRULAMA yarisi. Imzalama yok.
_q = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493


def _ters(x):
    return pow(x, _q - 2, _q)


_d = -121665 * _ters(121666) % _q
_I = pow(2, (_q - 1) // 4, _q)


def _x_geri_kazan(y):
    xx = (y * y - 1) * _ters(_d * y * y + 1)
    x = pow(xx, (_q + 3) // 8, _q)
    if (x * x - xx) % _q != 0:
        x = (x * _I) % _q
    if x % 2 != 0:
        x = _q - x
    return x


_By = 4 * _ters(5) % _q
_Bx = _x_geri_kazan(_By)
# Genisletilmis (X:Y:Z:T) koordinatlar: her toplamada ters alma
# maliyetini odememek icin. Ters alma pow(x, q-2, q) demek ve saf
# Python'da en pahali islem odur; 256 kez cagrilirsa dogrulama
# saniyeler surer. Genisletilmis biciminde tek ters alma yeterli.
_B = (_Bx % _q, _By % _q, 1, _Bx * _By % _q)


def _nokta_topla(P, Q):
    A = (P[1] - P[0]) * (Q[1] - Q[0]) % _q
    B = (P[1] + P[0]) * (Q[1] + Q[0]) % _q
    C = 2 * P[3] * Q[3] * _d % _q
    D = 2 * P[2] * Q[2] % _q
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _q, G * H % _q, F * G % _q, E * H % _q)


def _nokta_ikile(P):
    A = P[0] * P[0] % _q
    B = P[1] * P[1] % _q
    C = 2 * P[2] * P[2] % _q
    H = A + B
    E = H - (P[0] + P[1]) ** 2 % _q
    G = A - B
    F = C + G
    return (E * F % _q, G * H % _q, F * G % _q, E * H % _q)


def _skaler_carp(P, e):
    if e == 0:
        return (0, 1, 1, 0)
    Q = _skaler_carp(P, e // 2)
    Q = _nokta_ikile(Q)
    if e & 1:
        Q = _nokta_topla(Q, P)
    return Q


def _nokta_esit(P, Q):
    # Projektif karsilastirma: X1*Z2 == X2*Z1 ve Y1*Z2 == Y2*Z1.
    # Koordinatlari tek tek karsilastirmak YANLIS olurdu; ayni nokta
    # farkli Z ile farkli (X,Y) tasir.
    if (P[0] * Q[2] - Q[0] * P[2]) % _q != 0:
        return False
    return (P[1] * Q[2] - Q[1] * P[2]) % _q == 0


def _bit(h, i):
    return (h[i // 8] >> (i % 8)) & 1


def _nokta_coz(s):
    """32 baytlik sikistirilmis noktayi acar. Gecersizse None."""
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    isaret = y >> 255
    y &= (1 << 255) - 1
    if y >= _q:
        return None
    xx = (y * y - 1) * _ters(_d * y * y + 1) % _q
    x = pow(xx, (_q + 3) // 8, _q)
    if (x * x - xx) % _q != 0:
        x = (x * _I) % _q
    if (x * x - xx) % _q != 0:
        return None
    if x % 2 != isaret:
        x = _q - x
    return (x, y, 1, x * y % _q)


def _saf_dogrula(acik_anahtar: bytes, imza: bytes, ileti: bytes) -> bool:
    if len(imza) != 64 or len(acik_anahtar) != 32:
        return False
    R = _nokta_coz(imza[:32])
    if R is None:
        return False
    A = _nokta_coz(acik_anahtar)
    if A is None:
        return False
    S = int.from_bytes(imza[32:], "little")
    if S >= _L:
        return False
    h = hashlib.sha512(imza[:32] + acik_anahtar + ileti).digest()
    k = int.from_bytes(h, "little") % _L
    # sB == R + kA
    sol = _skaler_carp(_B, S)
    sag = _nokta_topla(R, _skaler_carp(A, k))
    return _nokta_esit(sol, sag)


def imza_dogrula(ham: bytes, imza_b64: str) -> bool:
    """Ham baytlarin merkez imzasini dogrular.

    `cryptography` varsa onu kullanir (hizli, denenmis); yoksa saf
    Python yedege duser. Iki yol AYNI sonucu vermek zorundadir —
    sinav bunu acikca olcer.
    """
    try:
        imza = base64.b64decode(str(imza_b64 or ""), validate=True)
    except Exception:
        return False
    try:
        acik = base64.b64decode(ACIK_ANAHTAR_B64)
    except Exception:
        return False
    if len(imza) != 64 or len(acik) != 32:
        return False

    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PublicKey,
        )
        from cryptography.exceptions import InvalidSignature
        try:
            Ed25519PublicKey.from_public_bytes(acik).verify(imza, ham)
            return True
        except (InvalidSignature, ValueError, TypeError):
            return False
    except ImportError:
        # Yedek yol: kutuphane yok.
        return _saf_dogrula(acik, imza, ham)


# ======================================================================
# Lisans belgesi
# ======================================================================
def govde_bayt(govde: dict) -> bytes:
    """Govdenin imzalanan kanonik baytlari.

    mk_yetki.govde_bayt() ile BIREBIR ayni olmak zorundadir. Tek
    karakter fark (ornegin ensure_ascii) tum lisanslari gecersiz
    kilar; Turkce unvanlarda bu fark hemen ortaya cikar.
    """
    return json.dumps(govde, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def lisans_yolu() -> str:
    """Lisans dosyasinin tam yolu (kullanici veri dizini altinda)."""
    try:
        from goktungu import sabitler
        return sabitler._veri_alt_yolu(LISANS_DOSYA_ADI)
    except Exception:
        # sabitler ice aktarilamiyorsa (cok erken cagri) main.py'nin
        # yanindaki veri/ dizinine duser.
        kok = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(kok, "veri", LISANS_DOSYA_ADI)


def lisans_oku(yol: str | None = None) -> tuple[dict | None, str]:
    """Lisans dosyasini okur ve IMZASINI dogrular.

    Donus: (yetkiler, hata). Yetkiler None ise hata metni doludur.

    HATA METINLERI KULLANICIYA GOSTERILIR. "gecersiz lisans" demek
    yetmez; kapali devre musteri destek arayamayabilir, ekranda ne
    yapmasi gerektigini gormeli.
    """
    y = yol or lisans_yolu()
    if not os.path.isfile(y):
        return None, ("Lisans dosyasi bulunamadi: %s\n"
                      "Kurumsal panelden (Abonelik > Merkez Uygulama) "
                      "lisans belgesini indirip bu konuma koyun." % y)
    try:
        with open(y, "r", encoding="utf-8") as f:
            belge = json.load(f)
    except (OSError, ValueError) as e:
        return None, "Lisans dosyasi okunamadi veya bozuk: %s" % e

    if not isinstance(belge, dict):
        return None, "Lisans dosyasi beklenen bicimde degil (nesne bekleniyor)"

    govde = belge.get("lisans")
    imza = belge.get("imza")
    if not isinstance(govde, dict) or not imza:
        return None, ("Lisans dosyasi eksik: 'lisans' ve 'imza' alanlari "
                      "zorunlu. Belgeyi kurumsal panelden yeniden indirin.")

    if not imza_dogrula(govde_bayt(govde), str(imza)):
        return None, ("Lisans IMZASI gecersiz. Dosya degistirilmis ya da "
                      "baska bir kuruluma ait. Kurumsal panelden yeniden "
                      "indirin.")

    yetkiler = govde.get("yetkiler")
    if not isinstance(yetkiler, dict):
        return None, "Lisans govdesinde 'yetkiler' alani yok"

    return {
        "firma_id": govde.get("firma_id"),
        "firma_unvan": govde.get("firma_unvan") or "",
        "lisans_uid": govde.get("lisans_uid") or "",
        "sinirsiz": bool(yetkiler.get("sinirsiz")),
        "ai": bool(yetkiler.get("ai")),
        "radar": bool(yetkiler.get("radar")),
        "gccdual": bool(yetkiler.get("gccdual")),
        # Eski imzalı belge alanı taşımıyorsa M50 kesinlikle açılmaz.
        "m50": bool(yetkiler.get("m50", False)),
    }, ""


def lisans_yaz(belge: dict, yol: str | None = None) -> tuple[bool, str]:
    """Indirilen lisans belgesini diske yazar (imzayi ONCE dogrular).

    Dogrulamadan yazmak, bozuk bir belgeyi kalici hale getirir ve
    kullanici bir sonraki acilista sebebini anlamaz.
    """
    govde = (belge or {}).get("lisans")
    imza = (belge or {}).get("imza")
    if not isinstance(govde, dict) or not imza:
        return False, "Belge eksik: 'lisans' ve 'imza' zorunlu"
    if not imza_dogrula(govde_bayt(govde), str(imza)):
        return False, "Belge imzasi gecersiz; yazilmadi"

    y = yol or lisans_yolu()
    try:
        os.makedirs(os.path.dirname(y), exist_ok=True)
        gecici = y + ".yeni"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump({"lisans": govde, "imza": str(imza)}, f,
                      ensure_ascii=False, indent=2)
        os.replace(gecici, y)  # atomik: yarim dosya birakmaz
        return True, ""
    except OSError as e:
        return False, "Lisans yazilamadi: %s" % e


# ======================================================================
# Kip belirleme
# ======================================================================
def merkez_uygulama_kipinde() -> bool:
    """Bu kurulum LISANSLI Merkez Uygulama mi?

    Merkez Uygulama, VEILOX'un islettigi merkez ornegiyle KARISTIRILMAMALI:

      merkez_kimlik.merkez_kipinde()  -> VEILOX'un cok kiracili ornegi
      lisans.merkez_uygulama_kipinde() -> musterinin satin aldigi kurulum

    Ikisi ayni makinede ASLA birlikte bulunmaz ama isimleri benzer
    oldugu icin karistirilmasi kolaydir; bu yuzden ayrimi burada
    belgeliyorum.
    """
    y, _ = lisans_oku()
    return bool(y and y.get("sinirsiz"))


def yetki_ozeti() -> dict:
    """Kurulumun yetki ozeti. Lisans yoksa TABAN yetkiler doner.

    Taban yetkiler neden sifir degil: lisanssiz kurulum da (kopru
    uzerinden merkeze baglanan olagan kullanim) calisir; yetkilerini
    MERKEZDEN alir. Bu islev yalnizca YEREL lisans belgesine bakar,
    dolayisiyla lisans yokken "bilinmiyor" demeli, "yetkisiz"
    dememeli. Aksi halde olagan kurulumda AI/radar menuleri lisans
    dosyasi yok diye kapanirdi.
    """
    y, hata = lisans_oku()
    if y:
        return {"lisansli": True, "kaynak": "yerel_lisans",
                "sinirsiz": y["sinirsiz"], "ai": y["ai"],
                "radar": y["radar"], "gccdual": y["gccdual"],
                "m50": bool(y.get("m50", False)),
                "firma_unvan": y["firma_unvan"],
                "lisans_uid": y["lisans_uid"], "hata": ""}
    return {"lisansli": False, "kaynak": "merkez",
            "sinirsiz": False, "ai": False,
            "radar": False, "gccdual": False, "m50": False,
            "firma_unvan": "", "lisans_uid": "", "hata": hata}
