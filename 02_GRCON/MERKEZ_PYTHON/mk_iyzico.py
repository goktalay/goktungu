"""GÖKTUNGU MERKEZ — iyzico (iyzipay) API istemcisi.

Tahsilat: **Türkbey Teknoloji Anonim Şirketi**
VKN 6290873411 · Ticaret Sicil 418199
Ahi Evren OSB Mah. Büyük Selçuklu Cad. No:2/B Sincan/Ankara

NEDEN SDK KULLANILMIYOR
-----------------------
`pip install iyzipay` paketi mevcut ancak **abonelik API'sini
desteklemiyor** (iyzico/iyzipay-python konusu #75, 2021'den beri açık).
Bu yüzden IYZWSv2 imzası elle üretilir ve HTTP çağrıları `urllib` ile
yapılır. Mevcut `mk_odeme.py` da Stripe'a aynı desenle bağlanıyordu.

IYZWSv2 İMZA SÖZLEŞMESİ (belgelenmiş)
-------------------------------------
    randomKey = <zaman damgası><rastgele>
    payload   = randomKey + uri_yolu + istek_govdesi
    imza      = HMAC-SHA256(secretKey, payload)  → HEX
    yetki     = "apiKey:<k>&randomKey:<r>&signature:<imza>"
    Authorization: IYZWSv2 base64(yetki)

DİKKAT: `uri_yolu` sorgu dizesi HARİÇ yoldur; gövde JSON'unun
**birebir gönderilen hali** imzalanır. Gövdeyi yeniden serileştirmek
imzayı bozar — bu yüzden bir kez üretilip hem imzada hem istekte aynı
bayt dizisi kullanılır.

PARA BİRİMİ KISITI (belgelenmiş, kritik)
----------------------------------------
> Yabancı para biriminde sadece yabancı kart kullanılabilir.

Yani TRY olmayan bir plana Türk kartıyla abone OLUNAMAZ. Bu yüzden
`paketler` tablosu iki fiyat taşır ve kiracının `para_birimi` alanına
göre uygun plan referansı seçilir.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import random
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import mk_db as db

# ---------------------------------------------------------------------------
# Yapılandırma
# ---------------------------------------------------------------------------
CANLI_TABAN = "https://api.iyzipay.com"
SINAV_TABAN = "https://sandbox-api.iyzipay.com"

# Abonelik durumları (belgelenmiş)
DURUM_ETKIN = "ACTIVE"
DURUM_BEKLEYEN = "PENDING"
DURUM_ODENMEMIS = "UNPAID"
DURUM_YUKSELTILMIS = "UPGRADED"
DURUM_IPTAL = "CANCELED"
DURUM_BITMIS = "EXPIRED"

# Yetki kaybına yol açan durumlar. `PENDING` DAHİL DEĞİLDİR: iyzico
# kart doğrulaması sırasında aboneliği kısa süre PENDING tutar; bu
# durumu ödemesizlik sanmak yeni müşteriyi anında kısıtlardı.
SORUNLU_DURUMLAR = (DURUM_ODENMEMIS,)
BITMIS_DURUMLAR = (DURUM_IPTAL, DURUM_BITMIS)

_ZAMAN_ASIMI = 30


class IyzicoHatasi(Exception):
    """iyzico çağrısı başarısız. `kod` ve `mesaj` taşır."""

    def __init__(self, mesaj: str, kod: str = "", ham: Any = None):
        super().__init__(mesaj)
        self.kod = kod
        self.mesaj = mesaj
        self.ham = ham


# ---------------------------------------------------------------------------
# Kimlik bilgileri
#
# `mk_odeme.py` (Stripe) deseni birebir izlenir: JSON dosyası + ortam
# değişkeni üstünlüğü. Merkez veritabanında `ayarlar` tablosu YOKTUR
# (o tablo app tarafında yaşar) — bu ölçülerek doğrulandı.
# ---------------------------------------------------------------------------
def _ayar_dosyasi() -> str:
    kok = os.environ.get("GOKTUNGU_MERKEZ_VERI") or "/opt/goktungu/merkez/veri"
    return os.path.join(kok, "iyzico.json")


def yapilandirma() -> dict[str, str]:
    """iyzico kimlik bilgileri ve kip.

    Okuma sırası: `iyzico.json` → ortam değişkenleri (üstün).
    Gizli anahtar HIÇBİR zaman arayüze döndürülmez (`durum()`
    yalnız bayrak döner).
    """
    d: dict[str, str] = {}
    try:
        with open(_ayar_dosyasi(), encoding="utf-8") as f:
            d = json.load(f) or {}
    except (OSError, ValueError):
        d = {}
    for cevre, alan in (("IYZICO_API_KEY", "api_anahtar"),
                        ("IYZICO_SECRET_KEY", "gizli_anahtar"),
                        ("IYZICO_MODE", "kip"),
                        ("IYZICO_CALLBACK", "geri_donus")):
        v = os.environ.get(cevre)
        if v:
            d[alan] = v
    kip = str(d.get("kip") or "sinav").lower()
    return {
        "api_anahtar": str(d.get("api_anahtar") or ""),
        "gizli_anahtar": str(d.get("gizli_anahtar") or ""),
        "kip": kip,
        "taban": CANLI_TABAN if kip == "canli" else SINAV_TABAN,
        "geri_donus": str(d.get("geri_donus")
                          or "https://goktungu.com/company/odeme/sonuc"),
    }


def yapilandirilmis_mi() -> bool:
    y = yapilandirma()
    return bool(y["api_anahtar"] and y["gizli_anahtar"])


def durum() -> dict[str, Any]:
    """Arayüze dönecek GÜVENLİ durum özeti.

    Gizli anahtar veya API anahtarı ASLA döndürülmez.
    """
    y = yapilandirma()
    return {
        "saglayici": "iyzico",
        "acik": bool(y["api_anahtar"] and y["gizli_anahtar"]),
        "kip": y["kip"],
        "sinav_modu": y["kip"] != "canli",
        "tahsilat": "Türkbey Teknoloji Anonim Şirketi",
        "vkn": "6290873411",
        "para_birimleri": ["TRY", "USD"],
        "bildirim_yolu": "/api/genel/iyzico_bildirim",
    }


def yapilandirma_yaz(api_anahtar: str = "", gizli_anahtar: str = "",
                     kip: str = "", geri_donus: str = "") -> None:
    """Kimlik bilgilerini dosyaya yazar (yalnız dolu alanlar güncellenir).

    Boş dizge gönderilen alan KORUNUR — arayüzde maskelenmiş alanın
    boş gönderilmesi mevcut anahtarı silmesin.
    """
    mevcut: dict[str, str] = {}
    try:
        with open(_ayar_dosyasi(), encoding="utf-8") as f:
            mevcut = json.load(f) or {}
    except (OSError, ValueError):
        mevcut = {}
    for alan, deger in (("api_anahtar", api_anahtar),
                        ("gizli_anahtar", gizli_anahtar),
                        ("kip", kip), ("geri_donus", geri_donus)):
        if deger:
            mevcut[alan] = str(deger)
    yol = _ayar_dosyasi()
    gecici = yol + ".gecici"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(mevcut, f, ensure_ascii=False, indent=2)
    os.chmod(gecici, 0o600)
    os.replace(gecici, yol)


# ---------------------------------------------------------------------------
# IYZWSv2 imzası
# ---------------------------------------------------------------------------
def _rastgele_anahtar() -> str:
    return "%d%06d" % (int(time.time() * 1000), random.randint(0, 999999))


def _yetki_basligi(api_anahtar: str, gizli: str, uri_yolu: str,
                   govde_metni: str, rastgele: str) -> str:
    """IYZWSv2 Authorization başlığını üretir.

    `govde_metni` GÖNDERİLEN gövdenin birebir kendisi olmalıdır.
    Yeniden serileştirme (anahtar sırası, boşluk) imzayı bozar.
    """
    yuk = rastgele + uri_yolu + govde_metni
    imza = hmac.new(gizli.encode("utf-8"), yuk.encode("utf-8"),
                    hashlib.sha256).hexdigest()
    yetki = "apiKey:%s&randomKey:%s&signature:%s" % (
        api_anahtar, rastgele, imza)
    return "IYZWSv2 " + base64.b64encode(yetki.encode("utf-8")).decode("ascii")


# ---------------------------------------------------------------------------
# HTTP katmanı
# ---------------------------------------------------------------------------
def _cagir(yontem: str, yol: str, govde: dict | None = None,
           sorgu: dict | None = None) -> dict:
    """iyzico'ya imzalı istek gönderir.

    `yol` sorgu dizesi İÇERMEZ; imza yalnız yolu kapsar.
    """
    y = yapilandirma()
    if not (y["api_anahtar"] and y["gizli_anahtar"]):
        raise IyzicoHatasi(
            "iyzico kimlik bilgileri yapılandırılmamış. Yönetim "
            "panelinden API anahtarı ve gizli anahtar tanımlanmalıdır.",
            kod="yapilandirma_yok")

    govde_metni = json.dumps(govde or {}, ensure_ascii=False,
                             separators=(",", ":")) if govde is not None else ""
    rastgele = _rastgele_anahtar()
    yetki = _yetki_basligi(y["api_anahtar"], y["gizli_anahtar"],
                           yol, govde_metni, rastgele)

    url = y["taban"] + yol
    if sorgu:
        url += "?" + urllib.parse.urlencode(sorgu)

    veri = govde_metni.encode("utf-8") if govde is not None else None
    istek = urllib.request.Request(url, data=veri, method=yontem)
    istek.add_header("Authorization", yetki)
    istek.add_header("x-iyzi-rnd", rastgele)
    istek.add_header("Content-Type", "application/json")
    istek.add_header("Accept", "application/json")

    baglam = ssl.create_default_context()
    try:
        with urllib.request.urlopen(istek, timeout=_ZAMAN_ASIMI,
                                    context=baglam) as yanit:
            ham = yanit.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        ham = e.read().decode("utf-8", "replace")
        try:
            j = json.loads(ham)
        except Exception:
            raise IyzicoHatasi("iyzico HTTP %s: %s" % (e.code, ham[:300]),
                               kod="http_%s" % e.code, ham=ham)
        raise IyzicoHatasi(
            j.get("errorMessage") or "iyzico hatası (HTTP %s)" % e.code,
            kod=str(j.get("errorCode") or "http_%s" % e.code), ham=j)
    except urllib.error.URLError as e:
        raise IyzicoHatasi("iyzico erişilemedi: %s" % e.reason,
                           kod="ag_hatasi")

    try:
        j = json.loads(ham)
    except Exception:
        raise IyzicoHatasi("iyzico yanıtı okunamadı: %s" % ham[:300],
                           kod="cozumleme")

    if j.get("status") == "failure":
        raise IyzicoHatasi(j.get("errorMessage") or "iyzico işlemi başarısız",
                           kod=str(j.get("errorCode") or ""), ham=j)
    return j


# ---------------------------------------------------------------------------
# Ürün ve plan yönetimi
# ---------------------------------------------------------------------------
def urun_olustur(ad: str, aciklama: str = "") -> str:
    """Abonelik ürünü oluşturur, referans kodunu döndürür."""
    y = _cagir("POST", "/v2/subscription/products",
               {"locale": "tr", "name": ad,
                "description": aciklama or ad})
    d = y.get("data") or {}
    ref = d.get("referenceCode")
    if not ref:
        raise IyzicoHatasi("Ürün referans kodu alınamadı", ham=y)
    return ref


def plan_olustur(urun_ref: str, ad: str, tutar: float, para: str,
                 aralik: str = "MONTHLY", deneme_gun: int = 0) -> str:
    """Ödeme planı oluşturur, plan referans kodunu döndürür.

    DİKKAT: iyzico'da **plan fiyatı sonradan güncellenemez**; yalnız
    `name` ve `trialPeriodDays` değiştirilebilir. Fiyat değişirse YENİ
    plan açılmalıdır. Bu yüzden TRY fiyatları kura endekslenmez.
    """
    govde: dict[str, Any] = {
        "locale": "tr",
        "productReferenceCode": urun_ref,
        "name": ad,
        "price": ("%.2f" % float(tutar)),
        "currencyCode": (para or "TRY").upper(),
        "paymentInterval": aralik,
        "paymentIntervalCount": 1,
        "planPaymentType": "RECURRING",
    }
    if deneme_gun and int(deneme_gun) > 0:
        govde["trialPeriodDays"] = int(deneme_gun)
    y = _cagir("POST",
               "/v2/subscription/products/%s/pricing-plans"
               % urllib.parse.quote(urun_ref), govde)
    d = y.get("data") or {}
    ref = d.get("referenceCode")
    if not ref:
        raise IyzicoHatasi("Plan referans kodu alınamadı", ham=y)
    return ref


def urunleri_listele() -> list[dict]:
    y = _cagir("GET", "/v2/subscription/products",
               sorgu={"page": 1, "count": 100})
    d = y.get("data") or {}
    return d.get("items") or []


# ---------------------------------------------------------------------------
# Plan eşleme — paketler tablosu ile iyzico arasındaki köprü
# ---------------------------------------------------------------------------
_PLAN_KOLON = {
    ("TRY", "aylik"): "iyz_plan_ref_ay_try",
    ("TRY", "yillik"): "iyz_plan_ref_yil_try",
    ("USD", "aylik"): "iyz_plan_ref_ay_usd",
    ("USD", "yillik"): "iyz_plan_ref_yil_usd",
}


def plan_referansi(paket_anahtar: str, donem: str, para: str) -> str | None:
    kolon = _PLAN_KOLON.get(((para or "TRY").upper(), donem))
    if not kolon:
        return None
    return db.deger("SELECT %s FROM paketler WHERE anahtar = %%s" % kolon,
                    (paket_anahtar,))


def planlari_kur(zorla: bool = False) -> dict[str, Any]:
    """Satılabilir paketler için iyzico ürün ve planlarını oluşturur.

    Var olan referanslar KORUNUR (`zorla=False`) — aksi halde her
    çağrıda yeni plan açılır ve mevcut abonelikler yörüngesiz kalır.

    Ücretsiz paket (`baslangic`) ATLANIR: iyzico sıfır tutarlı plan
    kabul etmez ve zaten tahsilat gerekmez.
    """
    import mk_paket as paket

    sonuc: dict[str, Any] = {"olusan": [], "atlanan": [], "hata": []}
    for p in paket.fiyat_listesi(ust_yonetici=True):
        a = p["paket"]
        if p["tur"] != "saas" or not p["satilabilir"] or p["ucretsiz"]:
            sonuc["atlanan"].append({"paket": a, "sebep": "saas degil/ucretsiz"})
            continue

        urun_ref = db.deger(
            "SELECT iyz_urun_ref FROM paketler WHERE anahtar = %s", (a,))
        try:
            if not urun_ref or zorla:
                urun_ref = urun_olustur(
                    "GOKTUNGU %s" % p["ad_tr"],
                    p.get("aciklama_tr") or p["ad_tr"])
                db.calistir("UPDATE paketler SET iyz_urun_ref = %s, "
                            "guncel_ts = now() WHERE anahtar = %s",
                            (urun_ref, a))

            for para in ("TRY", "USD"):
                aylik = p.get("aylik_" + para.lower())
                if aylik is None or float(aylik) <= 0:
                    continue
                for donem, tutar, aralik in (
                        ("aylik", float(aylik), "MONTHLY"),
                        ("yillik", paket.yillik_tutar(float(aylik)), "YEARLY")):
                    kolon = _PLAN_KOLON[(para, donem)]
                    mevcut = db.deger(
                        "SELECT %s FROM paketler WHERE anahtar = %%s" % kolon,
                        (a,))
                    if mevcut and not zorla:
                        sonuc["atlanan"].append(
                            {"paket": a, "donem": donem, "para": para,
                             "sebep": "zaten var", "ref": mevcut})
                        continue
                    ref = plan_olustur(
                        urun_ref,
                        "%s %s %s" % (p["ad_tr"],
                                      "Aylık" if donem == "aylik" else "Yıllık",
                                      para),
                        tutar, para, aralik)
                    db.calistir(
                        "UPDATE paketler SET %s = %%s, guncel_ts = now() "
                        "WHERE anahtar = %%s" % kolon, (ref, a))
                    sonuc["olusan"].append(
                        {"paket": a, "donem": donem, "para": para,
                         "tutar": tutar, "ref": ref})
        except IyzicoHatasi as e:
            sonuc["hata"].append({"paket": a, "kod": e.kod, "mesaj": e.mesaj})
    import mk_paket as _p
    _p.onbellek_bosalt()
    return sonuc


# ---------------------------------------------------------------------------
# Abonelik akışı
# ---------------------------------------------------------------------------
def _musteri_govdesi(f: dict, eposta: str, ad: str, soyad: str,
                     gsm: str, kimlik_no: str) -> dict:
    """iyzico müşteri gövdesi.

    ZORUNLU ALANLAR (belgelenmiş): name, surname, email, gsmNumber,
    identityNumber, billingAddress{address, contactName, city, country}

    `identityNumber`: gerçek kişide TCKN, tüzel kişide VKN kabul edilir.
    Kurumsal kiracıda `firmalar.kimlik_no` (VKN'den kopyalanmış) verilir.
    """
    unvan = f.get("unvan") or f.get("kisa_ad") or "GOKTUNGU Müşterisi"
    adres = f.get("adres") or "Belirtilmedi"
    sehir = f.get("sehir") or "Ankara"
    return {
        "name": ad or unvan[:50],
        "surname": soyad or "Kurumsal",
        "email": eposta,
        "gsmNumber": gsm or "+905000000000",
        "identityNumber": kimlik_no,
        "shippingAddress": {
            "contactName": unvan, "city": sehir, "country": "Turkey",
            "address": adres,
        },
        "billingAddress": {
            "contactName": unvan, "city": sehir, "country": "Turkey",
            "address": adres,
        },
    }


def abonelik_formu_baslat(firma_id: int, paket_anahtar: str,
                          donem: str = "aylik",
                          eposta: str = "", ad: str = "", soyad: str = "",
                          gsm: str = "", kimlik_no: str = "",
                          geri_donus: str | None = None) -> dict:
    """Ödeme formu (checkout) oturumu başlatır.

    Dönüş: `{"token": ..., "form_icerik": ..., "form_url": ...}`
    Arayüz `form_icerik`'i sayfaya gömer veya `form_url`'e yönlendirir.
    """
    import mk_paket as paket

    f = db.tek(
        "SELECT firma_id, unvan, kisa_ad, adres, sehir, kimlik_no, "
        "       para_birimi, eposta FROM firmalar WHERE firma_id = %s",
        (int(firma_id),))
    if not f:
        raise IyzicoHatasi("Firma bulunamadı", kod="firma_yok")

    para = (f["para_birimi"] or "TRY").upper()
    kimlik = kimlik_no or (f["kimlik_no"] or "")
    if not kimlik:
        raise IyzicoHatasi(
            "iyzico abonelik için kimlik numarası zorunludur "
            "(gerçek kişide TCKN, tüzel kişide VKN). Kurumsal panelden "
            "firma bilgilerini tamamlayın.", kod="kimlik_no_yok")

    plan_ref = plan_referansi(paket_anahtar, donem, para)
    if not plan_ref:
        raise IyzicoHatasi(
            "Bu paket için %s/%s ödeme planı tanımlı değil. Yönetim "
            "panelinden planları kurun." % (para, donem),
            kod="plan_yok")

    # Fiyatı KENDİ motorumuzdan hesapla — kayda geçer, iyzico'nun
    # döndürdüğü tutarla karşılaştırılabilir.
    nf = paket.net_fiyat(firma_id, paket_anahtar, donem, para)

    govde = {
        "locale": "tr",
        "conversationId": "gt-%d-%s-%s" % (int(firma_id), paket_anahtar, donem),
        "pricingPlanReferenceCode": plan_ref,
        "subscriptionInitialStatus": "ACTIVE",
        "callbackUrl": geri_donus or yapilandirma()["geri_donus"],
        "customer": _musteri_govdesi(
            dict(f), eposta or (f["eposta"] or ""), ad, soyad, gsm, kimlik),
    }
    y = _cagir("POST", "/v2/subscription/checkoutform/initialize", govde)
    d = y.get("data") or {}
    jeton = d.get("token")
    if not jeton:
        raise IyzicoHatasi("Ödeme formu belirteci alınamadı", ham=y)

    db.calistir(
        "INSERT INTO odeme_oturumlari (saglayici, firma_id, paket_anahtar, "
        "  donem, para_birimi, tutar, jeton, durum, ham_yanit) "
        "VALUES ('iyzico',%s,%s,%s,%s,%s,%s,'baslatildi',%s)",
        (int(firma_id), paket_anahtar, donem, para, nf["net"], jeton,
         json.dumps(d, ensure_ascii=False)))

    return {"token": jeton,
            "form_icerik": d.get("checkoutFormContent"),
            "form_url": d.get("payWithIyzicoPageUrl"),
            "tutar": nf["net"], "para_birimi": para}


def abonelik_dogrula(jeton: str) -> dict:
    """Ödeme formu sonucunu doğrular ve yetkiyi uygular.

    KRİTİK: yetki YALNIZ iyzico'nun doğruladığı sonuca göre verilir.
    İstemciden gelen "ödeme tamam" bildirimine GÜVENİLMEZ.
    """
    y = _cagir("POST", "/v2/subscription/checkoutform/%s"
               % urllib.parse.quote(jeton), {"locale": "tr"})
    d = y.get("data") or {}
    durum = (d.get("subscriptionStatus")
             or d.get("status") or "").upper()
    abonelik_ref = d.get("referenceCode") or d.get("subscriptionReferenceCode")

    o = db.tek("SELECT oturum_id, firma_id, paket_anahtar, donem, "
               "       para_birimi, tutar FROM odeme_oturumlari "
               "WHERE jeton = %s ORDER BY oturum_id DESC LIMIT 1", (jeton,))
    if not o:
        raise IyzicoHatasi("Ödeme oturumu bulunamadı", kod="oturum_yok")

    db.calistir(
        "UPDATE odeme_oturumlari SET durum = %s, saglayici_ref = %s, "
        "  ham_yanit = %s, guncel_ts = now() WHERE oturum_id = %s",
        (durum.lower() or "bilinmiyor", abonelik_ref,
         json.dumps(d, ensure_ascii=False), int(o["oturum_id"])))

    if durum == DURUM_ETKIN:
        _yetki_uygula(int(o["firma_id"]), o["paket_anahtar"], o["donem"],
                      abonelik_ref, float(o["tutar"] or 0),
                      o["para_birimi"])
        return {"tamam": True, "durum": durum, "abonelik_ref": abonelik_ref}
    return {"tamam": False, "durum": durum or "bilinmiyor",
            "abonelik_ref": abonelik_ref,
            "mesaj": d.get("errorMessage") or ""}


def _yetki_uygula(firma_id: int, paket_anahtar: str, donem: str,
                  abonelik_ref: str | None, tutar: float,
                  para: str) -> None:
    """Ödeme onaylandıktan sonra yetkiyi açar."""
    import mk_bakim as bakim
    import mk_yetki as yetki

    db.calistir(
        "UPDATE firmalar SET iyz_abonelik_ref = %s, fatura_donemi = %s, "
        "  guncel_ts = now() WHERE firma_id = %s",
        (abonelik_ref, donem, int(firma_id)))
    bakim.odeme_basarili(int(firma_id))
    try:
        yetki.kalem_uygula(int(firma_id), paket_anahtar, 1, donem,
                           kaynak="iyzico")
    except Exception:
        # Yetki uygulaması başarısız olsa bile ödeme kaydı DURMAZ;
        # kayıt tutulur, yönetici elle uygulayabilir.
        pass
    db.calistir(
        "INSERT INTO odeme_olaylari (saglayici, firma_id, olay_turu, "
        "  saglayici_ref, tutar, para_birimi, govde) "
        "VALUES ('iyzico',%s,'abonelik_etkin',%s,%s,%s,%s)",
        (int(firma_id), abonelik_ref, tutar, para,
         json.dumps({"paket": paket_anahtar, "donem": donem},
                    ensure_ascii=False)))


def abonelik_durumu(abonelik_ref: str) -> dict:
    y = _cagir("GET", "/v2/subscription/subscriptions/%s"
               % urllib.parse.quote(abonelik_ref))
    return y.get("data") or {}


def abonelik_iptal(abonelik_ref: str) -> dict:
    """Aboneliği iptal eder.

    VERİ SİLİNMEZ ve kiracı ÇALIŞMAYA DEVAM EDER; yalnız yenileme
    durur. Dönem sonunda `odemesiz_donem_tara()` salt-okunur kipe
    geçirir.
    """
    y = _cagir("POST", "/v2/subscription/subscriptions/%s/cancel"
               % urllib.parse.quote(abonelik_ref), {"locale": "tr"})
    db.calistir(
        "UPDATE firmalar SET abonelik = 'iptal', guncel_ts = now() "
        "WHERE iyz_abonelik_ref = %s", (abonelik_ref,))
    return y.get("data") or {}


def abonelik_yukselt(abonelik_ref: str, yeni_plan_ref: str,
                     hemen: bool = True) -> dict:
    """Aboneliği başka plana yükseltir (koltuk artışı, paket değişimi)."""
    y = _cagir("POST", "/v2/subscription/subscriptions/%s/upgrade"
               % urllib.parse.quote(abonelik_ref),
               {"locale": "tr", "newPricingPlanReferenceCode": yeni_plan_ref,
                "upgradePeriod": "NOW" if hemen else "NEXT_PERIOD",
                "useTrial": False, "resetRecurrenceCount": False})
    return y.get("data") or {}


def kart_guncelleme_formu(abonelik_ref: str,
                          geri_donus: str | None = None) -> dict:
    """Kart güncelleme formu başlatır (başarısız ödeme sonrası)."""
    y = _cagir("POST",
               "/v2/subscription/card-update/checkoutform/initialize",
               {"locale": "tr",
                "subscriptionReferenceCode": abonelik_ref,
                "callbackUrl": geri_donus or yapilandirma()["geri_donus"]})
    d = y.get("data") or {}
    return {"form_icerik": d.get("checkoutFormContent"),
            "form_url": d.get("payWithIyzicoPageUrl")}


# ---------------------------------------------------------------------------
# Bildirim (webhook) işleme
# ---------------------------------------------------------------------------
def bildirim_isle(govde: dict) -> dict:
    """iyzico bildirimini işler ve yetkiyi güncel tutar.

    GÜVENLİK: bildirim gövdesine körü körüne güvenilmez. Abonelik
    durumu iyzico'dan YENİDEN SORULUR (`abonelik_durumu`). Aksi halde
    uydurma bir bildirim ücretsiz yetki açardı.
    """
    import mk_bakim as bakim

    ref = (govde.get("subscriptionReferenceCode")
           or govde.get("referenceCode") or "")
    olay = (govde.get("iyziEventType") or govde.get("eventType") or "")

    db.calistir(
        "INSERT INTO odeme_olaylari (saglayici, olay_turu, saglayici_ref, "
        "  govde) VALUES ('iyzico',%s,%s,%s)",
        (olay or "bildirim", ref, json.dumps(govde, ensure_ascii=False)))

    if not ref:
        return {"tamam": False, "sebep": "referans yok"}

    f = db.tek("SELECT firma_id FROM firmalar WHERE iyz_abonelik_ref = %s",
               (ref,))
    if not f:
        return {"tamam": False, "sebep": "firma eslesmedi"}
    fid = int(f["firma_id"])

    # Durumu iyzico'dan DOĞRULA — bildirime güvenme.
    try:
        d = abonelik_durumu(ref)
        durum = (d.get("subscriptionStatus") or d.get("status") or "").upper()
    except IyzicoHatasi as e:
        return {"tamam": False, "sebep": "durum sorgulanamadi: %s" % e.mesaj}

    db.calistir("UPDATE firmalar SET iyz_abonelik_durum = %s, "
                "guncel_ts = now() WHERE firma_id = %s", (durum, fid))

    if durum == DURUM_ETKIN:
        bakim.odeme_basarili(fid)
        return {"tamam": True, "durum": durum, "eylem": "yetki_acildi"}
    if durum in SORUNLU_DURUMLAR:
        sonuc = bakim.odeme_basarisiz(fid, sebep=olay)
        return {"tamam": True, "durum": durum, "eylem": "odemesizlik",
                "ayrinti": sonuc}
    if durum in BITMIS_DURUMLAR:
        db.calistir("UPDATE firmalar SET abonelik = 'iptal', "
                    "guncel_ts = now() WHERE firma_id = %s", (fid,))
        return {"tamam": True, "durum": durum, "eylem": "abonelik_bitti"}
    return {"tamam": True, "durum": durum, "eylem": "kayit"}
