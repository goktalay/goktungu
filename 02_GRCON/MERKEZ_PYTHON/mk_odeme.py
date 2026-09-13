"""GÖKTUNGU ödeme katmanı — Stripe (Veilox LLC, USD).

TASARIM KARARLARI
-----------------
1. **`stripe` kütüphanesi KULLANILMAZ.** Sunucuda ne `stripe` ne
   `requests` var; ikisi de yeni bağımlılık ve yükseltme yükü demek.
   Stripe REST API'si `application/x-www-form-urlencoded` konuşur ve
   webhook imzası yalnız HMAC-SHA256'dır; ikisi de standart kütüphaneyle
   güvenli biçimde yapılır. Kapalı devre kurulumlarda eksik bağımlılık
   sorunu da doğmaz.

2. **Sağlayıcı bir eklenti katmanıdır.** Ödeme onaylandığında bu modül
   kendi yetki mantığını YAZMAZ; `mk_yetki.kalem_uygula()` çağırır —
   VEILOX'un elle tanımlamasıyla tam aynı yolu kullanır. Böylece iki
   ayrı yetki mantığı oluşup ayrışamaz ve sağlayıcı değişirse yalnız
   bu dosya değişir.

3. **Webhook FİKRİ KAYNAKTIR, istemci değil.** Tarayıcı "ödedim"
   diyemez; yetki yalnız Stripe'ın imzalı webhook'uyla açılır. Aksi
   halde `success_url`'e elle giden biri bedava koltuk alırdı.

4. **Olay tekrarı zararsızdır (idempotent).** Stripe aynı olayı
   yeniden gönderebilir (ağ hatası, yeniden deneme). `stripe_olaylari`
   tablosuna olay kimliği YAZILIR ve daha önce işlenmişse atlanır.
   Bu olmadan tek ödeme için koltuk iki kez eklenirdi.

5. **Anahtarlar koda gömülmez.** `STRIPE_SECRET_KEY` ve
   `STRIPE_WEBHOOK_SECRET` ortam değişkeninden ya da
   `veri/stripe.json`'dan okunur. Anahtar yoksa modül "kapalı" moda
   düşer: satın alma uçları 503 döner, VEILOX'un elle tanımlaması
   çalışmaya devam eder.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import mk_db as db
import mk_yetki as yetki

STRIPE_API = "https://api.stripe.com/v1"

# Stripe kuruş (cent) ile çalışır; USD için 100 ile çarpılır.
KURUS = 100


# ---------------------------------------------------------------------------
# Yapılandırma
# ---------------------------------------------------------------------------
def _ayar_dosyasi() -> str:
    kok = os.environ.get("GOKTUNGU_MERKEZ_VERI") or "/opt/goktungu/merkez/veri"
    return os.path.join(kok, "stripe.json")


def ayarlar() -> dict[str, str]:
    """Stripe ayarlarını okur. Ortam değişkeni dosyanın önüne geçer."""
    d: dict[str, str] = {}
    yol = _ayar_dosyasi()
    try:
        with open(yol, encoding="utf-8") as f:
            d = json.load(f) or {}
    except (OSError, ValueError):
        d = {}
    for a, c in (("STRIPE_SECRET_KEY", "gizli_anahtar"),
                 ("STRIPE_WEBHOOK_SECRET", "webhook_sirri"),
                 ("STRIPE_PUBLIC_KEY", "acik_anahtar")):
        v = os.environ.get(a)
        if v:
            d[c] = v
    return {k: str(v) for k, v in d.items() if v}


def acik_mi() -> bool:
    """Ödeme alma etkin mi? Anahtar yoksa satış kapalıdır."""
    return bool(ayarlar().get("gizli_anahtar"))


def test_modu() -> bool:
    """Anahtar test anahtarı mı (`sk_test_`)?"""
    return ayarlar().get("gizli_anahtar", "").startswith("sk_test_")


def durum() -> dict[str, Any]:
    a = ayarlar()
    return {
        "acik": bool(a.get("gizli_anahtar")),
        "test_modu": a.get("gizli_anahtar", "").startswith("sk_test_"),
        "webhook_hazir": bool(a.get("webhook_sirri")),
        "acik_anahtar": a.get("acik_anahtar", ""),
        "para_birimi": "usd",
        "tahsilat": "Veilox LLC",
    }


# ---------------------------------------------------------------------------
# Stripe REST çağrısı (urllib)
# ---------------------------------------------------------------------------
def _duzle(veri: Any, onek: str = "") -> list[tuple[str, str]]:
    """İç içe sözlük/listeyi Stripe'ın beklediği düz forma çevirir.

    Stripe `line_items[0][price]=x` biçimini bekler; JSON kabul etmez.
    """
    cikti: list[tuple[str, str]] = []
    if isinstance(veri, dict):
        for k, v in veri.items():
            ad = "%s[%s]" % (onek, k) if onek else str(k)
            cikti.extend(_duzle(v, ad))
    elif isinstance(veri, (list, tuple)):
        for i, v in enumerate(veri):
            cikti.extend(_duzle(v, "%s[%d]" % (onek, i)))
    elif isinstance(veri, bool):
        cikti.append((onek, "true" if veri else "false"))
    elif veri is None:
        pass
    else:
        cikti.append((onek, str(veri)))
    return cikti


class StripeHata(Exception):
    def __init__(self, mesaj: str, kod: str = "", http: int = 0):
        super().__init__(mesaj)
        self.kod = kod
        self.http = http


def cagir(yol: str, veri: dict[str, Any] | None = None,
          yontem: str = "POST", idem: str = "") -> dict[str, Any]:
    """Stripe API çağrısı. Anahtar yoksa `StripeHata` yükseltir."""
    a = ayarlar()
    anahtar = a.get("gizli_anahtar")
    if not anahtar:
        raise StripeHata("Stripe yapılandırılmadı (gizli anahtar yok)",
                         "yapilandirma_yok", 503)

    url = "%s/%s" % (STRIPE_API, yol.lstrip("/"))
    govde = None
    if veri:
        cift = _duzle(veri)
        if yontem == "GET":
            url += "?" + urllib.parse.urlencode(cift)
        else:
            govde = urllib.parse.urlencode(cift).encode("utf-8")

    istek = urllib.request.Request(url, data=govde, method=yontem)
    istek.add_header("Authorization", "Bearer %s" % anahtar)
    istek.add_header("Stripe-Version", "2024-06-20")
    if govde is not None:
        istek.add_header("Content-Type", "application/x-www-form-urlencoded")
    if idem:
        # Ağ hatasında yeniden denerken çift kayıt oluşmasın.
        istek.add_header("Idempotency-Key", idem)

    try:
        with urllib.request.urlopen(istek, timeout=30) as y:
            return json.loads(y.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            g = json.loads(e.read().decode("utf-8") or "{}")
            h = (g.get("error") or {})
            raise StripeHata(h.get("message") or str(e),
                             h.get("code") or "", e.code) from None
        except (ValueError, AttributeError):
            raise StripeHata("Stripe hatası: HTTP %s" % e.code,
                             "", e.code) from None
    except OSError as e:
        raise StripeHata("Stripe'a ulaşılamadı: %s" % e, "ag", 0) from None


# ---------------------------------------------------------------------------
# Ürün ve fiyat kayıtları
# ---------------------------------------------------------------------------
def _arama_anahtari(kalem: str, donem: str) -> str:
    """Fiyat için sabit `lookup_key`. Böylece fiyat kimliği saklanmaz."""
    return "goktungu_%s_%s" % (kalem, donem)


def satilabilir_kalemler() -> list[tuple[str, str]]:
    """(kalem, dönem) çiftleri — yalnız satılabilir olanlar."""
    cikti: list[tuple[str, str]] = []
    for k, t in yetki.KALEMLER.items():
        if k in yetki.YALNIZ_VEILOX:
            continue
        if t.get("tek"):
            cikti.append((k, "tek"))
        else:
            cikti.append((k, "aylik"))
            cikti.append((k, "yillik"))
    return cikti


def fiyatlari_kur() -> dict[str, Any]:
    """Stripe'ta ürün ve fiyat kayıtlarını oluşturur (yeniden koşulabilir).

    Fiyatlar `lookup_key` ile bulunur; varsa yeniden oluşturulmaz.
    Tutar değişmişse yeni fiyat açılır ve `lookup_key` ona taşınır —
    Stripe fiyat tutarını değiştirmeye izin vermez.
    """
    sonuc: dict[str, Any] = {"urunler": {}, "fiyatlar": {}, "islem": []}
    for kalem, donem in satilabilir_kalemler():
        t = yetki.KALEMLER[kalem]
        urun_anahtar = "goktungu_%s" % kalem
        # Ürün ---------------------------------------------------------
        var = cagir("products/%s" % urun_anahtar, yontem="GET")\
            if _urun_var(urun_anahtar) else None
        if not var:
            var = cagir("products", {
                "id": urun_anahtar,
                "name": "GÖKTUNGU — %s" % t["ad"],
                "metadata": {"kalem": kalem},
            }, idem="urun_%s" % urun_anahtar)
            sonuc["islem"].append("urun olusturuldu: %s" % urun_anahtar)
        sonuc["urunler"][kalem] = var["id"]

        # Fiyat --------------------------------------------------------
        ak = _arama_anahtari(kalem, donem)
        tutar = int(round(yetki.kalem_fiyat(kalem, donem) * KURUS))
        mevcut = _fiyat_bul(ak)
        if mevcut and int(mevcut.get("unit_amount") or 0) == tutar:
            sonuc["fiyatlar"][ak] = mevcut["id"]
            continue
        govde: dict[str, Any] = {
            "currency": "usd",
            "unit_amount": tutar,
            "product": var["id"],
            "lookup_key": ak,
            "transfer_lookup_key": True,
            "nickname": "%s (%s)" % (t["ad"], donem),
            "metadata": {"kalem": kalem, "donem": donem},
        }
        if donem == "aylik":
            govde["recurring"] = {"interval": "month",
                                  "usage_type": "licensed"}
        elif donem == "yillik":
            govde["recurring"] = {"interval": "year",
                                  "usage_type": "licensed"}
        yeni = cagir("prices", govde)
        sonuc["fiyatlar"][ak] = yeni["id"]
        sonuc["islem"].append("fiyat olusturuldu: %s = %s USD"
                              % (ak, tutar / KURUS))
    return sonuc


def _urun_var(urun_id: str) -> bool:
    try:
        cagir("products/%s" % urun_id, yontem="GET")
        return True
    except StripeHata:
        return False


def _fiyat_bul(arama_anahtari: str) -> dict[str, Any] | None:
    try:
        y = cagir("prices", {"lookup_keys": [arama_anahtari],
                             "active": True, "limit": 1}, yontem="GET")
    except StripeHata:
        return None
    d = y.get("data") or []
    return d[0] if d else None


def fiyat_kimligi(kalem: str, donem: str) -> str | None:
    f = _fiyat_bul(_arama_anahtari(kalem, donem))
    return f["id"] if f else None


# ---------------------------------------------------------------------------
# Checkout oturumu
# ---------------------------------------------------------------------------
def _kok_url() -> str:
    return (os.environ.get("GOKTUNGU_KOK_URL")
            or "https://goktungu.com").rstrip("/")


def checkout_olustur(firma_id: int, kalem: str, adet: int = 1,
                     donem: str = "aylik",
                     eposta: str = "") -> tuple[str, str]:
    """Ödeme sayfası bağlantısı üretir. `(url, hata)` döner."""
    if kalem not in yetki.KALEMLER:
        return "", "Geçersiz kalem"
    if kalem in yetki.YALNIZ_VEILOX:
        return "", ("Bu modül satın alınamaz; sistem yöneticisi tarafından "
                    "tanımlanır. Lütfen bizimle iletişime geçin.")
    if adet < 1:
        return "", "Adet en az 1 olmalı"
    if kalem == "merkez":
        donem = "tek"
        adet = 1  # tek seferlik kurulum; adet anlamsız
    if donem not in ("aylik", "yillik", "tek"):
        return "", "Geçersiz dönem"

    f = db.tek("SELECT firma_id, kisa_ad, durum, stripe_musteri "
               "FROM firmalar WHERE firma_id = %s", (int(firma_id),))
    if not f:
        return "", "Firma bulunamadı"
    if f["durum"] != "etkin":
        return "", "Firma hesabı etkin değil"

    # Merkez lisansı zaten varsa ikinci kez satılmaz.
    if kalem == "merkez" and yetki.ozellik_acik_mi(firma_id,
                                                   "merkez_lisans"):
        return "", "Merkez Uygulama lisansı bu firmada zaten açık"

    fid = fiyat_kimligi(kalem, donem)
    if not fid:
        return "", ("Stripe fiyat kaydı yok (%s/%s). Önce fiyatları kurun."
                    % (kalem, donem))

    kok = _kok_url()
    govde: dict[str, Any] = {
        "mode": "payment" if donem == "tek" else "subscription",
        "line_items": [{"price": fid, "quantity": int(adet)}],
        "success_url": ("%s/company/#/abonelik?odeme=tamam"
                        "&oturum={CHECKOUT_SESSION_ID}" % kok),
        "cancel_url": "%s/company/#/abonelik?odeme=iptal" % kok,
        "client_reference_id": "firma_%d" % int(firma_id),
        "locale": "tr",
        # Webhook'un hangi firmaya ne uygulayacağını buradan okur.
        "metadata": {"firma_id": int(firma_id), "kalem": kalem,
                     "adet": int(adet), "donem": donem},
    }
    if donem != "tek":
        govde["subscription_data"] = {
            "metadata": {"firma_id": int(firma_id), "kalem": kalem,
                         "adet": int(adet), "donem": donem},
        }
    else:
        govde["invoice_creation"] = {"enabled": True}
    if f.get("stripe_musteri"):
        govde["customer"] = f["stripe_musteri"]
    elif eposta:
        govde["customer_email"] = eposta
        govde["customer_creation"] = "always"
    else:
        govde["customer_creation"] = "always"

    try:
        o = cagir("checkout/sessions", govde)
    except StripeHata as e:
        return "", "Ödeme sayfası açılamadı: %s" % e

    db.calistir(
        "INSERT INTO stripe_oturumlari (oturum_id, firma_id, kalem, adet, "
        "  donem, tutar_usd, durum) VALUES (%s,%s,%s,%s,%s,%s,'acik') "
        "ON CONFLICT (oturum_id) DO NOTHING",
        (o["id"], int(firma_id), kalem, int(adet), donem,
         round(yetki.kalem_fiyat(kalem, donem) * int(adet), 2)))
    return o.get("url") or "", ""


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------
def imza_dogrula(govde: bytes, imza_basligi: str,
                 tolerans: int = 300) -> tuple[bool, str]:
    """Stripe-Signature başlığını doğrular.

    Zaman toleransı, kaydedilmiş bir isteğin sonradan yeniden
    oynatılmasını engeller.
    """
    sir = ayarlar().get("webhook_sirri")
    if not sir:
        return False, "Webhook sırrı yapılandırılmadı"
    if not imza_basligi:
        return False, "Stripe-Signature başlığı yok"

    zaman = ""
    imzalar: list[str] = []
    for parca in imza_basligi.split(","):
        if "=" not in parca:
            continue
        k, _, v = parca.strip().partition("=")
        if k == "t":
            zaman = v
        elif k == "v1":
            imzalar.append(v)
    if not zaman or not imzalar:
        return False, "Başlık biçimi geçersiz"
    try:
        t = int(zaman)
    except ValueError:
        return False, "Zaman damgası geçersiz"
    if tolerans and abs(time.time() - t) > tolerans:
        return False, "Zaman damgası tolerans dışı"

    beklenen = hmac.new(
        sir.encode("utf-8"),
        b"%s.%s" % (zaman.encode("ascii"), govde),
        hashlib.sha256).hexdigest()
    for i in imzalar:
        if hmac.compare_digest(beklenen, i):
            return True, ""
    return False, "İmza eşleşmedi"


def _olay_islendi_mi(olay_id: str) -> bool:
    """Olay daha önce işlendiyse True. Aynı anda gelen kopyaları da eler."""
    y = db.tek(
        "INSERT INTO stripe_olaylari (olay_id, tur) VALUES (%s,%s) "
        "ON CONFLICT (olay_id) DO NOTHING RETURNING olay_id",
        (olay_id, ""))
    return y is None


def webhook_isle(govde: bytes, imza_basligi: str) -> tuple[bool, str]:
    """İmzayı doğrular ve olayı uygular. `(tamam, mesaj)` döner."""
    tamam, hata = imza_dogrula(govde, imza_basligi)
    if not tamam:
        return False, hata
    try:
        olay = json.loads(govde.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return False, "Gövde JSON değil"

    oid = str(olay.get("id") or "")
    tur = str(olay.get("type") or "")
    if not oid:
        return False, "Olay kimliği yok"
    if _olay_islendi_mi(oid):
        return True, "zaten islendi: %s" % oid
    db.calistir("UPDATE stripe_olaylari SET tur = %s WHERE olay_id = %s",
                (tur, oid))

    nesne = ((olay.get("data") or {}).get("object") or {})
    if tur == "checkout.session.completed":
        return _oturum_tamam(nesne)
    if tur in ("customer.subscription.deleted",
               "customer.subscription.paused"):
        return _abonelik_bitti(nesne)
    if tur == "invoice.payment_failed":
        return _odeme_basarisiz(nesne)
    return True, "ilgisiz olay: %s" % tur


def _ust_veri(nesne: dict[str, Any]) -> dict[str, str]:
    m = nesne.get("metadata") or {}
    return {str(k): str(v) for k, v in m.items()}


def _oturum_tamam(o: dict[str, Any]) -> tuple[bool, str]:
    """Ödeme tamamlandı → yetkiyi aç."""
    if o.get("payment_status") not in ("paid", "no_payment_required"):
        return True, "odeme henuz alinmadi"
    m = _ust_veri(o)
    try:
        firma_id = int(m.get("firma_id") or 0)
        adet = int(m.get("adet") or 1)
    except ValueError:
        return False, "metadata sayisal degil"
    kalem = m.get("kalem") or ""
    donem = m.get("donem") or "aylik"
    if not firma_id or kalem not in yetki.KALEMLER:
        return False, "metadata eksik (firma_id/kalem)"

    if o.get("customer"):
        db.calistir("UPDATE firmalar SET stripe_musteri = %s, "
                    "guncel_ts = now() WHERE firma_id = %s",
                    (str(o["customer"]), firma_id))

    tamam, hata = yetki.kalem_uygula(
        firma_id, kalem, adet, donem, kaynak="stripe",
        notlar="Stripe oturumu %s" % o.get("id"))
    if not tamam:
        return False, "kalem uygulanamadi: %s" % hata

    db.calistir(
        "UPDATE stripe_oturumlari SET durum = 'tamam', odendi_ts = now(), "
        "  stripe_abonelik = %s WHERE oturum_id = %s",
        (str(o.get("subscription") or "") or None, str(o.get("id") or "")))
    return True, "yetki acildi: firma=%d kalem=%s adet=%d" % (
        firma_id, kalem, adet)


def _abonelik_bitti(a: dict[str, Any]) -> tuple[bool, str]:
    """Abonelik iptal/duraklatıldı → kalemi kapat.

    DİKKAT: koltuk DÜŞÜRÜLÜRKEN mevcut pilot sayısının altına
    inilmez. Aksi halde şirket kendi etkin pilotları yüzünden kilitlenir
    ve hiçbirini yönetemez. Fazla pilotlar pasife alınmaz; şirket
    yöneticisi hangisini çıkaracağına kendi karar verir.
    """
    m = _ust_veri(a)
    try:
        firma_id = int(m.get("firma_id") or 0)
        adet = int(m.get("adet") or 1)
    except ValueError:
        return False, "metadata sayisal degil"
    kalem = m.get("kalem") or ""
    if not firma_id or kalem not in yetki.KALEMLER:
        return True, "metadata yok; atlandi"

    t = yetki.KALEMLER[kalem]
    koltuk = int(t.get("koltuk") or 0) * adet
    if koltuk:
        db.calistir(
            "UPDATE firmalar f SET pilot_koltuk = GREATEST(%s, "
            "    f.pilot_koltuk - %s, "
            "    (SELECT count(*) FROM kullanicilar k "
            "      WHERE k.firma_id = f.firma_id AND k.rol = 'pilot' "
            "        AND k.durum = 'etkin')), "
            "  guncel_ts = now() WHERE f.firma_id = %s",
            (yetki.TABAN_PILOT_KOLTUK, koltuk, firma_id))
    if kalem == "ai":
        db.calistir("UPDATE firmalar SET ai_etkin = false, "
                    "guncel_ts = now() WHERE firma_id = %s", (firma_id,))

    db.calistir(
        "UPDATE abonelik_kalemleri SET durum = 'iptal', bitis = CURRENT_DATE "
        " WHERE firma_id = %s AND kalem = %s AND durum = 'etkin'",
        (firma_id, kalem))
    return True, "kalem kapatildi: firma=%d kalem=%s" % (firma_id, kalem)


def _odeme_basarisiz(f: dict[str, Any]) -> tuple[bool, str]:
    """Ödeme başarısız → firmaya not düşülür, yetki HEMEN kapatılmaz.

    Stripe birkaç gün yeniden dener; ilk başarısızlıkta erişimi kesmek
    geçici kart sorununda sahadaki uçuşu durdurur.
    """
    mus = str(f.get("customer") or "")
    if not mus:
        return True, "musteri yok"
    db.calistir(
        "UPDATE firmalar SET odeme_uyari_ts = now(), guncel_ts = now() "
        " WHERE stripe_musteri = %s", (mus,))
    return True, "odeme uyarisi islendi"


# ---------------------------------------------------------------------------
# Müşteri portalı (kart/iptal yönetimi)
# ---------------------------------------------------------------------------
def portal_baglantisi(firma_id: int) -> tuple[str, str]:
    """Stripe müşteri portalı bağlantısı. Kart ve iptal yönetimi orada."""
    f = db.tek("SELECT stripe_musteri FROM firmalar WHERE firma_id = %s",
               (int(firma_id),))
    if not f or not f.get("stripe_musteri"):
        return "", "Bu firmanın Stripe müşteri kaydı yok"
    try:
        o = cagir("billing_portal/sessions", {
            "customer": f["stripe_musteri"],
            "return_url": "%s/company/#/abonelik" % _kok_url(),
        })
    except StripeHata as e:
        return "", "Portal açılamadı: %s" % e
    return o.get("url") or "", ""
