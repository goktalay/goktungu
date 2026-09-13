# -*- coding: utf-8 -*-
"""GOKTUNGU MERKEZ — KABA KUVVET (BRUTE FORCE) KORUMASI

OLCULEN ACIK
============
`/api/firma/giris` ucuna 15 ardisik hatali parola denemesi gonderildi;
on besi de ayni hizda 401 dondu. Hiz siniri, artan gecikme veya hesap
kilidi YOKTU. Ayni durum `/api/admin/giris` (sistem yoneticisi) ve
`/api/dogrulama/onayla` (dogrulama kodu) uclarinda da gecerliydi.

MIMARI KISIT — TERS VEKIL YOK
=============================
Bu sunucuda nginx/apache YOKTUR; Python sureci 80/443'u dogrudan tutar.
Yani `limit_req` gibi hazir bir katman bulunmaz, koruma KODDA olmak
zorundadir.

KRITIK: `istek.ip` KULLANILMAZ
==============================
`istek.ip` ozelligi `X-Forwarded-For` basligini onceler ve bu baslik
istemci tarafindan UYDURULABILIR. Hiz siniri o deger ile anahtarlanirsa
saldirgan her istekte farkli bir baslik gondererek siniri TAMAMEN atlar.
Anahtarlama GERCEK TCP esi (`h.client_address[0]`) ile yapilir. Ayni
sozlesme `_ic_uc_dogrula` icinde de uygulanir (mk_sunucu.py:3071).

ESIKLER
=======
| Anahtar     | Pencere | Esik | Ceza    |
|-------------|---------|------|---------|
| IP + uc     |   60 sn |   10 |   60 sn |
| IP + uc     |  900 sn |   30 |  900 sn |
| Hesap       |  900 sn |    8 |  900 sn |

Basarili giriste hem hesap hem IP sayaci SIFIRLANIR: mesru kullanici
parolasini hatirlayinca cezalandirilmaz.

ARTAN GECIKME
=============
3. denemeden sonra `0.4 * (n - 2)` sn, en cok 2 sn. Amac otomatik
araclarin hizini dusurmek; mesru kullanici 2-3 denemede gecer ve
gecikmeyi hissetmez. Gecikme YANITTAN ONCE uygulanir.

KAPALI DEVRE MUAFIYETI
======================
5000 USD'lik Merkez Uygulama alan sirketler sistemi yerel agda ya da
tek makinede calistirir; kendi kendine istek atan bilesenler (kopru,
GCS vekili) kilitlenmemelidir. Yerel geri dongu ve RFC 1918 ozel ag
ariliklari MUAFTIR. Bu muafiyet gercek TCP esine bakar, basliga
bakmaz; disaridan "ozel ag" taklidi yapilamaz.

MUAFIYET NEDEN ACIK LISTE ILE TANIMLI (olculdu)
===============================================
Ilk yazimda muafiyet `ipaddress.is_private` ozelligine dayaniyordu ve
birim sinavi SIFIR sayac dondurdu. Olculen neden: Python 3.11'de
`is_private`, RFC 1918 ozel aglarinin yaninda RFC 5737 BELGELEME
araliklarini (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`),
`100.64.0.0/10` tasiyici NAT'ini ve baska ayrilmis bloklari da kapsar.
Yani "ozel ag" degil "genel yonlendirilebilir olmayan her sey"
anlamina gelir.

Bu, muafiyet yuzeyini niyet edilenden GENIS tutardi: tasiyici NAT muaf
sayilsa, o araligin arkasindaki mobil aglardan gelen saldirilar hic
sayilmazdi. Bu yuzden muafiyet ACIK ARALIK LISTESI ile tanimlanir ve
`is_private` KULLANILMAZ.

BELLEK SINIRI
=============
Sayaclar bellek ici sozluklerde tutulur (surec tekildir, coklu isci
yoktur). Sinirsiz buyume bir bellek tukenme saldirisina donusebilecegi
icin `_TEMIZLE_ESIK` asildiginda suresi gecmis kayitlar silinir.
"""
from __future__ import annotations

import sys as _sys  # KK_GUNLUK_v1
import time as _zaman  # KK_GUNLUK_TARIH_v1
import ipaddress
import threading
import time

# Muaf aglar. `is_private` KULLANILMAZ (yukaridaki olcum notuna bakin).
# `100.64.0.0/10` (tasiyici NAT) ve RFC 5737 belge araliklari MUAF DEGIL.
_MUAF_AGLAR = tuple(ipaddress.ip_network(a) for a in (
    "127.0.0.0/8",        # geri dongu
    "10.0.0.0/8",         # RFC 1918
    "172.16.0.0/12",      # RFC 1918
    "192.168.0.0/16",     # RFC 1918
    "169.254.0.0/16",     # baglanti yereli
    "::1/128",            # IPv6 geri dongu
    "fe80::/10",          # IPv6 baglanti yereli
    "fc00::/7",           # IPv6 tekil yerel
))

# ----------------------------------------------------------------- #
# ESIKLER                                                            #
# ----------------------------------------------------------------- #
IP_KISA_PENCERE = 60
IP_KISA_ESIK = 10
IP_KISA_CEZA = 60

IP_UZUN_PENCERE = 900
IP_UZUN_ESIK = 30
IP_UZUN_CEZA = 900

HESAP_PENCERE = 900
HESAP_ESIK = 8
HESAP_CEZA = 900

GECIKME_BASLA = 3          # kacinci denemeden sonra gecikme baslar
GECIKME_KATSAYI = 0.4      # sn
GECIKME_EN_COK = 2.0       # sn

_TEMIZLE_ESIK = 4000       # kayit sayisi bu degeri asinca temizlik yapilir

# Korunan uclar. Desen DEGIL tam yol; yol tablosundaki desenle
# karistirilmamasi icin ayri tutulur.
KORUNAN_UCLAR = {
    "/api/firma/giris",
    "/api/admin/giris",
    "/api/istemci/giris",
    "/api/firma/kayit",
    "/api/bireysel/kayit",
    "/api/istemci/sunucu_kayit",
    "/api/dogrulama/gonder",
    "/api/dogrulama/onayla",
    "/api/sifre/sifirla",
    "/api/sifre/talep",
    # KK_APP_WS_v1 — App (GCS) yuzeyleri.
    #
    # WS komutlari yol DEGIL; ayni ad alanina dusmemeleri icin `ws:`
    # oneki ile ayrilir. Boylece `/api/firma/giris` sayaci ile
    # `ws:giris` sayaci karismaz ve bir yuzeydeki kilit digerini
    # etkilemez (uc ayrimi ilkesi).
    "ws:giris",
    "ws:jeton_giris",
    # Oturum devri: kurumsal cerezi App jetonuna cevirir. Cerez
    # tahminine karsi korunur.
    "/api/oturum/devir",
}

# Hesap adinin okunacagi govde alanlari (ilk bulunan kullanilir).
HESAP_ALANLARI = ("eposta", "email", "kullanici", "kullanici_adi", "ad")

_kilit = threading.Lock()
# ip_uc -> [ts, ...]
_ip_denemeler: dict[tuple[str, str], list[float]] = {}
# hesap -> [ts, ...]
_hesap_denemeler: dict[str, list[float]] = {}
# ip_uc -> bitis_ts
_ip_bloklar: dict[tuple[str, str], float] = {}
# hesap -> bitis_ts
_hesap_bloklar: dict[str, float] = {}

# Kayit gecmisi (gorunurluk icin; kalici kayit DB katmanindadir).
_son_olaylar: list[dict] = []
_SON_OLAY_SINIR = 500


def _simdi() -> float:
    return time.time()


def yerel_mi(ip: str) -> bool:
    """Gercek TCP esi yerel geri dongu ya da ozel ag mi.

    Kapali devre kurulumlarda (merkez uygulama, IP/localhost erisimi)
    bilesenler birbirine yerel agdan istek atar. Bunlar kilitlenmemeli.
    """
    d = (ip or "").strip()
    if not d:
        return False
    if d == "localhost":
        return True
    try:
        a = ipaddress.ip_address(d)
    except ValueError:
        # Cozulemeyen deger MUAF DEGILDIR: aksi halde bozuk bir adres
        # gonderen istemci korumayi atlardi.
        return False
    for ag in _MUAF_AGLAR:
        if a.version == ag.version and a in ag:
            return True
    return False


def _temizle_kilitli(simdi: float) -> None:
    """Suresi gecmis kayitlari sil. `_kilit` TUTULUYOR olmalidir."""
    for sozluk, pencere in ((_ip_denemeler, IP_UZUN_PENCERE),
                            (_hesap_denemeler, HESAP_PENCERE)):
        olecek = []
        for anahtar, dizi in sozluk.items():
            yeni = [t for t in dizi if simdi - t <= pencere]
            if yeni:
                sozluk[anahtar] = yeni
            else:
                olecek.append(anahtar)
        for anahtar in olecek:
            sozluk.pop(anahtar, None)
    for sozluk in (_ip_bloklar, _hesap_bloklar):
        for anahtar in [a for a, b in sozluk.items() if b <= simdi]:
            sozluk.pop(anahtar, None)


def _olay_ekle(tur: str, ip: str, uc: str, hesap: str, ek: str = "") -> None:
    # KK_GUNLUK_v1 — blok olaylarini systemd gunlugune bas.
    #
    # fail2ban `goktungu-http` hapsi bu satiri arar. Boylece uygulama
    # katmani 429 dondururken ag katmani da adresi dusurur ve saldirgan
    # TLS el sikismasi maliyetini bize odetemez.
    #
    # Yalniz BLOK turleri basilir; her basarisiz deneme basilsa gunluk
    # saldirinin kendisiyle sisirilirdi (20 bin satir/48 saat olculdu).
    if tur in ("ip_blok_kisa", "ip_blok_uzun", "hesap_kilit"):
        try:
            # KK_GUNLUK_TARIH_v1 — fail2ban tarih cozumleyicisi icin
            # ISO damga. Damga OLMADAN fail2ban satiri atlar.
            _sys.stderr.write(
                "%s GOKTUNGU-KK-BLOK ip=%s uc=%s tur=%s %s\n"
                % (_zaman.strftime("%Y-%m-%d %H:%M:%S"),
                   ip or "-", uc or "-", tur, ek or "")
            )
            _sys.stderr.flush()
        except BaseException:
            # Gunluk yazimi asla kimlik akisini kirmaz.
            pass
    _son_olaylar.append({
        "ts": _simdi(), "tur": tur, "ip": ip, "uc": uc,
        "hesap": hesap or "", "ek": ek,
    })
    if len(_son_olaylar) > _SON_OLAY_SINIR:
        del _son_olaylar[:len(_son_olaylar) - _SON_OLAY_SINIR]


def son_olaylar(sinir: int = 100) -> list[dict]:
    """Gorunurluk icin son olaylar (en yeni once)."""
    with _kilit:
        return list(reversed(_son_olaylar[-int(sinir or 100):]))


def durum() -> dict:
    """Anlik koruma durumu (yonetim paneli icin)."""
    simdi = _simdi()
    with _kilit:
        return {
            "ip_blok": [
                {"ip": a[0], "uc": a[1], "kalan": int(b - simdi)}
                for a, b in _ip_bloklar.items() if b > simdi
            ],
            "hesap_blok": [
                {"hesap": a, "kalan": int(b - simdi)}
                for a, b in _hesap_bloklar.items() if b > simdi
            ],
            "izlenen_ip": len(_ip_denemeler),
            "izlenen_hesap": len(_hesap_denemeler),
            "esik": {
                "ip_kisa": [IP_KISA_ESIK, IP_KISA_PENCERE, IP_KISA_CEZA],
                "ip_uzun": [IP_UZUN_ESIK, IP_UZUN_PENCERE, IP_UZUN_CEZA],
                "hesap": [HESAP_ESIK, HESAP_PENCERE, HESAP_CEZA],
            },
        }


def hesap_coz(govde) -> str:
    """Istek govdesinden hesap adini cikar (kucuk harfe indirilmis)."""
    if not isinstance(govde, dict):
        return ""
    for alan in HESAP_ALANLARI:
        d = govde.get(alan)
        if isinstance(d, str) and d.strip():
            return d.strip().lower()[:190]
    return ""


def denetle(ip: str, uc: str, hesap: str = ""):
    """Istek isleme ALINMADAN once cagrilir.

    Donus: `None` (gecebilir) veya `(kalan_sn, sebep)` demeti (bloklu).
    """
    if yerel_mi(ip):
        return None
    simdi = _simdi()
    with _kilit:
        if len(_ip_denemeler) + len(_hesap_denemeler) > _TEMIZLE_ESIK:
            _temizle_kilitli(simdi)
        anahtar = (ip, uc)
        bitis = _ip_bloklar.get(anahtar, 0.0)
        if bitis > simdi:
            return (int(bitis - simdi) + 1, "ip")
        if hesap:
            bitis = _hesap_bloklar.get(hesap, 0.0)
            if bitis > simdi:
                return (int(bitis - simdi) + 1, "hesap")
    return None


def gecikme(ip: str, uc: str) -> float:
    """Bu IP/uc icin uygulanacak artan gecikme (sn)."""
    if yerel_mi(ip):
        return 0.0
    simdi = _simdi()
    with _kilit:
        dizi = _ip_denemeler.get((ip, uc)) or []
        n = len([t for t in dizi if simdi - t <= IP_KISA_PENCERE])
    if n < GECIKME_BASLA:
        return 0.0
    return min(GECIKME_EN_COK, GECIKME_KATSAYI * (n - GECIKME_BASLA + 1))


def basarisiz(ip: str, uc: str, hesap: str = "") -> dict:
    """Basarisiz kimlik denemesi kaydi. Esik asilirsa blok kurar.

    Donus: `{"ip_blok": bool, "hesap_blok": bool, "ip_n": int, "hesap_n": int}`
    """
    sonuc = {"ip_blok": False, "hesap_blok": False, "ip_n": 0, "hesap_n": 0}
    if yerel_mi(ip):
        return sonuc
    simdi = _simdi()
    with _kilit:
        anahtar = (ip, uc)
        dizi = _ip_denemeler.setdefault(anahtar, [])
        dizi.append(simdi)
        kisa = len([t for t in dizi if simdi - t <= IP_KISA_PENCERE])
        uzun = len([t for t in dizi if simdi - t <= IP_UZUN_PENCERE])
        sonuc["ip_n"] = kisa
        if uzun >= IP_UZUN_ESIK:
            _ip_bloklar[anahtar] = simdi + IP_UZUN_CEZA
            sonuc["ip_blok"] = True
            _olay_ekle("ip_blok_uzun", ip, uc, hesap, "n=%d" % uzun)
        elif kisa >= IP_KISA_ESIK:
            _ip_bloklar[anahtar] = simdi + IP_KISA_CEZA
            sonuc["ip_blok"] = True
            _olay_ekle("ip_blok_kisa", ip, uc, hesap, "n=%d" % kisa)
        if hesap:
            hd = _hesap_denemeler.setdefault(hesap, [])
            hd.append(simdi)
            hn = len([t for t in hd if simdi - t <= HESAP_PENCERE])
            sonuc["hesap_n"] = hn
            if hn >= HESAP_ESIK:
                _hesap_bloklar[hesap] = simdi + HESAP_CEZA
                sonuc["hesap_blok"] = True
                _olay_ekle("hesap_kilit", ip, uc, hesap, "n=%d" % hn)
        _olay_ekle("basarisiz", ip, uc, hesap,
                   "ip_n=%d" % sonuc["ip_n"])
    return sonuc


def basarili(ip: str, uc: str, hesap: str = "") -> None:
    """Basarili giris: hem hesap hem IP sayaci sifirlanir.

    Mesru kullanici parolasini hatirlayinca cezalandirilmaz. Bu, hesap
    kilidini bir hizmet engelleme aracina donusmekten de korur.
    """
    if yerel_mi(ip):
        return
    with _kilit:
        _ip_denemeler.pop((ip, uc), None)
        _ip_bloklar.pop((ip, uc), None)
        if hesap:
            _hesap_denemeler.pop(hesap, None)
            _hesap_bloklar.pop(hesap, None)
        _olay_ekle("basarili", ip, uc, hesap)


def sifirla_hepsi() -> None:
    """SINAV amacli tam sifirlama."""
    with _kilit:
        _ip_denemeler.clear()
        _hesap_denemeler.clear()
        _ip_bloklar.clear()
        _hesap_bloklar.clear()
        del _son_olaylar[:]
