"""mk_sunucu.py'ye Stripe ödeme uçlarını ekler. Yeniden koşulabilir.

Projenin GERÇEK kalıbı kullanılır:
  - `@yol(yontem, desen, yetki=...)` dekoratörü
  - `yetki="acik"`   → kimlik denetimi yok
  - `yetki="firma"`  → kurumsal panel oturumu
  - yetki verilmezse → VEILOX admin oturumu (varsayılan)
  - Yanıt: `h.json_yaz(veri, kod)` / `h.hata_yaz(kod, mesaj)`
  - Gövde: `istek.govde` (JSON), `istek.ham` (HAM BAYT)

Eklenen uçlar
-------------
  GET  /api/firma/odeme_durum         (firma)  satış açık mı
  POST /api/firma/checkout            (firma)  ödeme sayfası bağlantısı
  GET  /api/firma/odeme_portali       (firma)  Stripe müşteri portalı
  POST /api/genel/stripe_webhook      (acik)   imzalı olay → yetki açar
  POST /api/admin/stripe/fiyat_kur    (admin)  ürün/fiyat kayıtları
  GET  /api/admin/stripe/durum        (admin)  yapılandırma durumu
"""
from __future__ import annotations

YOL = "mk_sunucu.py"
IM = "# === GOKTUNGU ODEME UCLARI (mk_odeme) ==="

with open(YOL, encoding="utf-8") as f:
    m = f.read()

if IM in m:
    print("! odeme uclari zaten ekli; cikiliyor")
    raise SystemExit(0)

# 1) mk_odeme içe aktarımı --------------------------------------------------
if "import mk_odeme as odeme" not in m:
    if "import mk_yetki as yetki" not in m:
        raise SystemExit("HATA: mk_yetki ice aktarimi bulunamadi")
    m = m.replace("import mk_yetki as yetki",
                  "import mk_yetki as yetki\nimport mk_odeme as odeme", 1)
    print("+ mk_odeme ice aktarildi")

# 2) Uç noktaları -----------------------------------------------------------
EKLENTI = '''

# ==========================================================================
# === GOKTUNGU ODEME UCLARI (mk_odeme) ===
# ==========================================================================
# TASARIM: Webhook TEK fikir kaynagidir. Tarayici "odedim" diyemez;
# yetki YALNIZ Stripe'in imzali webhook'uyla acilir. Aksi halde
# success_url'e elle giden biri bedava koltuk alirdi.
#
# Odeme onayi, VEILOX'un elle tanimlamasiyla AYNI yolu kullanir
# (`yetki.kalem_uygula`). Iki ayri yetki mantigi olusup ayrisamaz.


@yol("GET", r"/api/firma/odeme_durum", yetki="firma")
def _u_firma_odeme_durum(h, istek, oturum):
    """Cevrimici satis acik mi? Arayuz dugmeleri buna gore gorunur."""
    d = odeme.durum()
    d["fiyatlar"] = yetki.fiyat_listesi()
    d["yillik_indirim"] = yetki.YILLIK_INDIRIM
    h.json_yaz(d)


@yol("POST", r"/api/firma/checkout", yetki="firma_yonetici")
def _u_firma_checkout(h, istek, oturum):
    """Odeme sayfasi baglantisi uretir (Stripe Checkout)."""
    if oturum.get("rol") != "firma_yonetici":
        h.hata_yaz(403, "Bu islem icin firma yoneticisi olmalisiniz")
        return
    if not odeme.acik_mi():
        h.hata_yaz(503, "Cevrimici odeme henuz etkin degil. Lutfen "
                        "uyelik talebi olusturun; sistem yoneticisi "
                        "degerlendirip tanimlayacaktir.")
        return
    g = istek.govde or {}
    try:
        adet = int(g.get("adet") or 1)
    except (TypeError, ValueError):
        h.hata_yaz(400, "adet sayisal olmali")
        return
    url, hata = odeme.checkout_olustur(
        _firma_id(oturum), (g.get("kalem") or "").strip(), adet,
        (g.get("donem") or "aylik").strip(),
        eposta=(oturum.get("eposta") or "").strip())
    if hata:
        h.hata_yaz(400, hata)
        return
    h.json_yaz({"url": url})


@yol("GET", r"/api/firma/odeme_portali", yetki="firma_yonetici")
def _u_firma_odeme_portali(h, istek, oturum):
    """Stripe musteri portali: kart guncelleme, iptal, fatura gecmisi."""
    if oturum.get("rol") != "firma_yonetici":
        h.hata_yaz(403, "Bu islem icin firma yoneticisi olmalisiniz")
        return
    url, hata = odeme.portal_baglantisi(_firma_id(oturum))
    if hata:
        h.hata_yaz(400, hata)
        return
    h.json_yaz({"url": url})


@yol("POST", r"/api/genel/stripe_webhook", yetki="acik")
def _u_stripe_webhook(h, istek, oturum):
    """Stripe olay ucu. Kimlik denetimi YOK; guvenlik IMZAYLA saglanir.

    DIKKAT: Govde HAM BAYT (`istek.ham`) olarak kullanilmalidir.
    JSON'a cevrilip yeniden serilestirilirse imza BOZULUR ve tum
    odemeler reddedilir.
    """
    tamam, mesaj = odeme.webhook_isle(
        istek.ham or b"", istek.h.headers.get("Stripe-Signature") or "")
    if not tamam:
        # Stripe 4xx'te yeniden DENEMEZ, 5xx'te dener. Imza/govde hatasi
        # kalicidir (400); veritabani hatasi gecicidir (500).
        alt = mesaj.lower()
        kod = 400 if ("imza" in alt or "govde" in alt
                      or "baslik" in alt or "tolerans" in alt) else 500
        try:
            print("[STRIPE] webhook reddedildi (%d): %s" % (kod, mesaj))
        except Exception:
            pass
        h.json_yaz({"hata": mesaj}, kod)
        return
    h.json_yaz({"tamam": True, "mesaj": mesaj})


@yol("POST", r"/api/admin/stripe/fiyat_kur")
def _u_admin_stripe_fiyat_kur(h, istek, oturum):
    """VEILOX: Stripe'ta urun ve fiyat kayitlarini olusturur.

    Yeniden kosulabilir; mevcut fiyat ayni tutardaysa dokunulmaz.
    Stripe fiyat tutarini degistirmeye izin vermedigi icin tutar
    degismisse yeni fiyat acilir ve `lookup_key` ona tasinir.
    """
    if oturum.get("rol") != "sistem_yonetici":
        h.hata_yaz(403, "Yalniz sistem yoneticisi")
        return
    if not odeme.acik_mi():
        h.hata_yaz(503, "Stripe gizli anahtari tanimli degil")
        return
    try:
        s = odeme.fiyatlari_kur()
    except Exception as e:
        h.hata_yaz(502, "Stripe hatasi: %s" % e)
        return
    kimlik.denetim(oturum.get("yonetici_id"), "stripe_fiyat_kur",
                   "stripe", None, {"islem": s.get("islem")})
    h.json_yaz(s)


@yol("GET", r"/api/admin/stripe/durum")
def _u_admin_stripe_durum(h, istek, oturum):
    """VEILOX: yapilandirma durumu ve fiyat esleme tablosu."""
    d = odeme.durum()
    d["kalemler"] = [{
        "kalem": k, "donem": dn,
        "usd": yetki.kalem_fiyat(k, dn),
        "arama_anahtari": "goktungu_%s_%s" % (k, dn),
    } for k, dn in odeme.satilabilir_kalemler()]
    d["webhook_yolu"] = "/api/genel/stripe_webhook"
    h.json_yaz(d)
'''

m = m.rstrip() + "\n" + EKLENTI + "\n"
print("+ 6 odeme ucu eklendi")

with open(YOL, "w", encoding="utf-8") as f:
    f.write(m)

print("TAMAM: mk_sunucu.py yamalandi.")
