"""mk_sunucu.py'ye iyzico ödeme + paket/iskonto yönetimi uçlarını ekler.

Yeniden koşulabilir (işaret dizesiyle korunur).

Projenin GERÇEK kalıbı kullanılır:
  - `@yol(yontem, desen, yetki=...)` dekoratörü
  - `yetki="acik"`            → kimlik denetimi yok
  - `yetki="firma"`           → kurumsal panel oturumu
  - `yetki="firma_yonetici"`  → şirket yöneticisi
  - yetki verilmezse          → üst yönetim (admin) oturumu
  - Yanıt: `h.json_yaz(veri, kod)` / `h.hata_yaz(kod, mesaj)`
  - Gövde: `istek.govde` (JSON), `istek.ham` (HAM BAYT)

Eklenen uçlar
-------------
  GET  /api/genel/fiyatlar              (acik)   satılabilir paket listesi
  GET  /api/firma/paket_durum           (firma)  paket + bakım + ödeme
  POST /api/firma/abonelik_baslat       (f.yön.) iyzico ödeme formu
  POST /api/firma/abonelik_dogrula      (f.yön.) form sonucunu doğrula
  POST /api/firma/abonelik_iptal        (f.yön.) yenilemeyi durdur
  GET  /api/firma/kart_guncelle         (f.yön.) kart güncelleme formu
  POST /api/genel/iyzico_bildirim       (acik)   iyzico bildirimi
  GET  /api/admin/paketler              (admin)  tüm katalog
  POST /api/admin/paket_guncelle        (admin)  fiyat/alan güncelle
  GET  /api/admin/iskontolar            (admin)  iskonto listesi
  POST /api/admin/iskonto_tanimla       (admin)  müşteriye özel iskonto
  POST /api/admin/iskonto_iptal         (admin)  iskonto kaldır
  GET  /api/admin/iyzico_durum          (admin)  yapılandırma durumu
  POST /api/admin/iyzico_ayar           (admin)  kimlik bilgisi yaz
  POST /api/admin/iyzico_plan_kur       (admin)  ürün/plan oluştur
  POST /api/admin/bakim_yenile          (admin)  bakım süresi uzat
  GET  /api/admin/gelir_ozet            (admin)  kiracı gelir özeti
"""
from __future__ import annotations

YOL = "mk_sunucu.py"
IM = "# === GOKTUNGU IYZICO + PAKET UCLARI (mk_iyzico/mk_paket) ==="

with open(YOL, encoding="utf-8") as f:
    m = f.read()

if IM in m:
    print("! iyzico/paket uclari zaten ekli; cikiliyor")
    raise SystemExit(0)

taban = len(m)

# 1) İçe aktarımlar ---------------------------------------------------------
if "import mk_yetki as yetki" not in m:
    raise SystemExit("HATA: mk_yetki ice aktarimi bulunamadi")

eklenecek = []
if "import mk_paket as paket" not in m:
    eklenecek.append("import mk_paket as paket")
if "import mk_bakim as bakim" not in m:
    eklenecek.append("import mk_bakim as bakim")
if "import mk_iyzico as iyzico" not in m:
    eklenecek.append("import mk_iyzico as iyzico")

if eklenecek:
    m = m.replace("import mk_yetki as yetki",
                  "import mk_yetki as yetki\n" + "\n".join(eklenecek), 1)
    print("+ ice aktarildi: %s" % ", ".join(eklenecek))

# 2) Uç noktaları -----------------------------------------------------------
EKLENTI = '''

# ==========================================================================
# === GOKTUNGU IYZICO + PAKET UCLARI (mk_iyzico/mk_paket) ===
# ==========================================================================
# TASARIM ILKELERI
#
# 1. BILDIRIM TEK FIKIR KAYNAGI DEGILDIR, iyzico'nun KENDISI oyle.
#    Tarayici "odedim" diyemez; ustelik bildirim govdesine de
#    guvenilmez. `mk_iyzico.bildirim_isle` abonelik durumunu iyzico'dan
#    YENIDEN SORAR. Aksi halde uydurma bir bildirim bedava yetki acardi.
#
# 2. Odeme onayi, ust yonetimin elle tanimlamasiyla AYNI yolu kullanir
#    (`yetki.kalem_uygula`). Iki ayri yetki mantigi olusup ayrisamaz.
#
# 3. FIYAT ISTEMCIDEN ALINMAZ. Tutar daima `mk_paket.net_fiyat` ile
#    sunucuda hesaplanir; istemcinin gonderdigi tutar YOK SAYILIR.
#    Aksi halde musteri kendi fiyatini yazardi.
#
# 4. BAKIM BITSE BILE CALISMA DURMAZ (savunma musterisi ilkesi).
#    `calisma_hakki` hicbir kosulda kapanmaz; yalnız guncelleme durur.


@yol("GET", r"/api/genel/fiyatlar", yetki="acik")
def _u_genel_fiyatlar(h, istek, oturum):
    """Satilabilir paketlerin genel fiyat listesi (tanitim sayfasi)."""
    try:
        liste = paket.fiyat_listesi()
    except Exception as e:
        h.hata_yaz(500, "Fiyat listesi okunamadi: %s" % e)
        return
    h.json_yaz({
        "tamam": True,
        "paketler": liste,
        "yillik_indirim": paket.YILLIK_INDIRIM,
        "tahsilat": "Gokkubbe Teknoloji Anonim Sirketi",
        "saglayici": "iyzico",
        "odeme_acik": iyzico.yapilandirilmis_mi(),
    })


@yol("GET", r"/api/firma/paket_durum", yetki="firma")
def _u_firma_paket_durum(h, istek, oturum):
    """Kiracinin paketi, bakim durumu ve odeme durumu."""
    fid = oturum.get("firma_id")
    if not fid:
        h.hata_yaz(400, "Firma oturumu yok")
        return
    fid = int(fid)
    try:
        y = yetki.firma_yetkileri(fid)
        b = bakim.bakim_durumu(fid)
        o = bakim.odeme_durumu(fid)
        pk = y.get("paket_anahtar")
        p = paket.paket(pk) if pk else None
    except Exception as e:
        h.hata_yaz(500, "Durum okunamadi: %s" % e)
        return
    h.json_yaz({
        "tamam": True,
        "yetkiler": y,
        "paket": p,
        "bakim": b,
        "odeme": o,
        "odeme_acik": iyzico.yapilandirilmis_mi(),
    })


@yol("POST", r"/api/firma/abonelik_baslat", yetki="firma_yonetici")
def _u_firma_abonelik_baslat(h, istek, oturum):
    """iyzico odeme formu baslatir.

    TUTAR ISTEMCIDEN ALINMAZ; sunucuda hesaplanir.
    """
    fid = oturum.get("firma_id")
    if not fid:
        h.hata_yaz(400, "Firma oturumu yok")
        return
    g = istek.govde or {}
    pk = str(g.get("paket") or "").strip()
    donem = str(g.get("donem") or "aylik").strip()
    if not pk:
        h.hata_yaz(400, "Paket belirtilmedi")
        return
    if donem not in ("aylik", "yillik"):
        h.hata_yaz(400, "Gecersiz donem")
        return
    if not iyzico.yapilandirilmis_mi():
        h.hata_yaz(503, "Odeme altyapisi henuz yapilandirilmadi")
        return
    try:
        sonuc = iyzico.abonelik_formu_baslat(
            int(fid), pk, donem,
            eposta=str(g.get("eposta") or ""),
            ad=str(g.get("ad") or ""),
            soyad=str(g.get("soyad") or ""),
            gsm=str(g.get("gsm") or ""),
            kimlik_no=str(g.get("kimlik_no") or ""))
    except iyzico.IyzicoHatasi as e:
        h.json_yaz({"tamam": False, "kod": e.kod, "mesaj": e.mesaj}, 400)
        return
    except Exception as e:
        h.hata_yaz(500, "Odeme formu baslatilamadi: %s" % e)
        return
    sonuc["tamam"] = True
    h.json_yaz(sonuc)


@yol("POST", r"/api/firma/abonelik_dogrula", yetki="firma_yonetici")
def _u_firma_abonelik_dogrula(h, istek, oturum):
    """Odeme formu sonucunu iyzico'ya sorarak dogrular."""
    g = istek.govde or {}
    jeton = str(g.get("token") or g.get("jeton") or "").strip()
    if not jeton:
        h.hata_yaz(400, "Belirtec yok")
        return
    try:
        sonuc = iyzico.abonelik_dogrula(jeton)
    except iyzico.IyzicoHatasi as e:
        h.json_yaz({"tamam": False, "kod": e.kod, "mesaj": e.mesaj}, 400)
        return
    except Exception as e:
        h.hata_yaz(500, "Dogrulama basarisiz: %s" % e)
        return
    h.json_yaz(sonuc)


@yol("POST", r"/api/firma/abonelik_iptal", yetki="firma_yonetici")
def _u_firma_abonelik_iptal(h, istek, oturum):
    """Yenilemeyi durdurur. VERI SILINMEZ, sistem CALISMAYA DEVAM EDER."""
    fid = oturum.get("firma_id")
    if not fid:
        h.hata_yaz(400, "Firma oturumu yok")
        return
    ref = db.deger("SELECT iyz_abonelik_ref FROM firmalar "
                   "WHERE firma_id = %s", (int(fid),))
    if not ref:
        h.hata_yaz(404, "Etkin abonelik bulunamadi")
        return
    try:
        iyzico.abonelik_iptal(ref)
    except iyzico.IyzicoHatasi as e:
        h.json_yaz({"tamam": False, "kod": e.kod, "mesaj": e.mesaj}, 400)
        return
    h.json_yaz({"tamam": True,
                "mesaj": "Yenileme durduruldu. Donem sonuna kadar "
                         "hizmet aynen surer; veriler silinmez."})


@yol("GET", r"/api/firma/kart_guncelle", yetki="firma_yonetici")
def _u_firma_kart_guncelle(h, istek, oturum):
    """Basarisiz odeme sonrasi kart guncelleme formu."""
    fid = oturum.get("firma_id")
    if not fid:
        h.hata_yaz(400, "Firma oturumu yok")
        return
    ref = db.deger("SELECT iyz_abonelik_ref FROM firmalar "
                   "WHERE firma_id = %s", (int(fid),))
    if not ref:
        h.hata_yaz(404, "Etkin abonelik bulunamadi")
        return
    try:
        sonuc = iyzico.kart_guncelleme_formu(ref)
    except iyzico.IyzicoHatasi as e:
        h.json_yaz({"tamam": False, "kod": e.kod, "mesaj": e.mesaj}, 400)
        return
    sonuc["tamam"] = True
    h.json_yaz(sonuc)


@yol("POST", r"/api/genel/iyzico_bildirim", yetki="acik")
def _u_iyzico_bildirim(h, istek, oturum):
    """iyzico bildirimi.

    GUVENLIK: govdeye guvenilmez; durum iyzico'dan yeniden sorulur.
    Bildirim her durumda 200 doner (aksi halde iyzico yeniden dener
    ve gunluk sisir).
    """
    g = istek.govde or {}
    try:
        sonuc = iyzico.bildirim_isle(g)
    except Exception as e:
        try:
            db.calistir(
                "INSERT INTO odeme_olaylari (saglayici, olay_turu, govde) "
                "VALUES ('iyzico','bildirim_hatasi',%s)",
                (json.dumps({"hata": str(e)}, ensure_ascii=False),))
        except Exception:
            pass
        h.json_yaz({"tamam": False}, 200)
        return
    h.json_yaz(sonuc, 200)


# --------------------------------------------------------------------------
# UST YONETIM (admin)
# --------------------------------------------------------------------------

@yol("GET", r"/api/admin/paketler")
def _u_admin_paketler(h, istek, oturum):
    """Tum katalog (gizli paketler dahil)."""
    try:
        liste = paket.fiyat_listesi(ust_yonetici=True)
    except Exception as e:
        h.hata_yaz(500, "Katalog okunamadi: %s" % e)
        return
    h.json_yaz({"tamam": True, "paketler": liste,
                "yillik_indirim": paket.YILLIK_INDIRIM})


@yol("POST", r"/api/admin/paket_guncelle")
def _u_admin_paket_guncelle(h, istek, oturum):
    """Paket alanlarini guncelle (beyaz listeli)."""
    g = istek.govde or {}
    pk = str(g.get("paket") or "").strip()
    alanlar = g.get("alanlar") or {}
    if not pk or not isinstance(alanlar, dict):
        h.hata_yaz(400, "Paket ve alanlar gerekli")
        return
    ok, hata = paket.paket_guncelle(pk, alanlar)
    if not ok:
        h.json_yaz({"tamam": False, "mesaj": hata}, 400)
        return
    h.json_yaz({"tamam": True, "paket": paket.paket(pk)})


@yol("GET", r"/api/admin/iskontolar")
def _u_admin_iskontolar(h, istek, oturum):
    """Iskonto listesi. `firma_id` sorgusuyla suzulur."""
    s = istek.sorgu or {}
    fid = s.get("firma_id")
    try:
        liste = paket.iskonto_listesi(int(fid) if fid else None)
    except Exception as e:
        h.hata_yaz(500, "Iskontolar okunamadi: %s" % e)
        return
    h.json_yaz({"tamam": True, "iskontolar": liste})


@yol("POST", r"/api/admin/iskonto_tanimla")
def _u_admin_iskonto_tanimla(h, istek, oturum):
    """Musteriye ozel iskonto tanimlar."""
    g = istek.govde or {}
    fid = g.get("firma_id")
    if not fid:
        h.hata_yaz(400, "firma_id gerekli")
        return
    kim = (oturum.get("eposta") or oturum.get("kullanici")
           or "admin")
    iid, hata = paket.iskonto_tanimla(
        int(fid),
        str(g.get("tur") or "yuzde"),
        g.get("deger"),
        paket_anahtar=(str(g.get("paket")) if g.get("paket") else None),
        para_birimi=(str(g.get("para_birimi")) if g.get("para_birimi") else None),
        gecerli_bas=(str(g.get("gecerli_bas")) if g.get("gecerli_bas") else None),
        gecerli_bit=(str(g.get("gecerli_bit")) if g.get("gecerli_bit") else None),
        gerekce=str(g.get("gerekce") or ""),
        tanimlayan=str(kim))
    if not iid:
        h.json_yaz({"tamam": False, "mesaj": hata}, 400)
        return
    h.json_yaz({"tamam": True, "iskonto_id": iid}, 201)


@yol("POST", r"/api/admin/iskonto_iptal")
def _u_admin_iskonto_iptal(h, istek, oturum):
    g = istek.govde or {}
    iid = g.get("iskonto_id")
    if not iid:
        h.hata_yaz(400, "iskonto_id gerekli")
        return
    ok = paket.iskonto_iptal(int(iid))
    h.json_yaz({"tamam": bool(ok)}, 200 if ok else 404)


@yol("GET", r"/api/admin/iyzico_durum")
def _u_admin_iyzico_durum(h, istek, oturum):
    """iyzico yapilandirma durumu. GIZLI ANAHTAR DONMEZ."""
    d = iyzico.durum()
    try:
        d["plan_sayisi"] = int(db.deger(
            "SELECT count(*) FROM paketler "
            "WHERE iyz_plan_ref_ay_try IS NOT NULL "
            "   OR iyz_plan_ref_ay_usd IS NOT NULL") or 0)
    except Exception:
        d["plan_sayisi"] = 0
    h.json_yaz({"tamam": True, "durum": d})


@yol("POST", r"/api/admin/iyzico_ayar")
def _u_admin_iyzico_ayar(h, istek, oturum):
    """iyzico kimlik bilgilerini yazar. Bos alanlar KORUNUR."""
    g = istek.govde or {}
    kip = str(g.get("kip") or "").lower()
    if kip and kip not in ("sinav", "canli"):
        h.hata_yaz(400, "Kip 'sinav' veya 'canli' olmali")
        return
    try:
        iyzico.yapilandirma_yaz(
            api_anahtar=str(g.get("api_anahtar") or ""),
            gizli_anahtar=str(g.get("gizli_anahtar") or ""),
            kip=kip,
            geri_donus=str(g.get("geri_donus") or ""))
    except Exception as e:
        h.hata_yaz(500, "Ayar yazilamadi: %s" % e)
        return
    h.json_yaz({"tamam": True, "durum": iyzico.durum()})


@yol("POST", r"/api/admin/iyzico_plan_kur")
def _u_admin_iyzico_plan_kur(h, istek, oturum):
    """Satilabilir paketler icin iyzico urun/plan kayitlarini olusturur.

    `zorla` verilmedikce mevcut plan referanslari KORUNUR — aksi halde
    her cagri yeni plan acar ve mevcut abonelikler yorungesiz kalir.
    """
    g = istek.govde or {}
    if not iyzico.yapilandirilmis_mi():
        h.hata_yaz(503, "iyzico kimlik bilgileri yapilandirilmamis")
        return
    try:
        sonuc = iyzico.planlari_kur(zorla=bool(g.get("zorla")))
    except Exception as e:
        h.hata_yaz(500, "Plan kurulumu basarisiz: %s" % e)
        return
    h.json_yaz({"tamam": True, "sonuc": sonuc})


@yol("POST", r"/api/admin/bakim_yenile")
def _u_admin_bakim_yenile(h, istek, oturum):
    """Kiracinin bakim/guncelleme suresini uzatir."""
    g = istek.govde or {}
    fid = g.get("firma_id")
    if not fid:
        h.hata_yaz(400, "firma_id gerekli")
        return
    try:
        yil = int(g.get("yil") or 1)
    except (TypeError, ValueError):
        h.hata_yaz(400, "yil sayisal olmali")
        return
    ok, sonuc = bakim.bakim_yenile(int(fid), yil)
    if not ok:
        h.json_yaz({"tamam": False, "mesaj": sonuc}, 400)
        return
    h.json_yaz({"tamam": True, "bakim_bitis": sonuc})


@yol("GET", r"/api/admin/gelir_ozet")
def _u_admin_gelir_ozet(h, istek, oturum):
    """Kiraci bazinda paket/bakim/odeme ozeti."""
    try:
        satirlar = db.sorgu(
            "SELECT f.firma_id, f.unvan, f.kisa_ad, f.paket_anahtar, "
            "       f.para_birimi, f.fatura_donemi, f.pilot_koltuk, "
            "       f.bakim_bitis, f.abonelik, f.salt_okunur, "
            "       f.odeme_deneme, f.odemesiz_bitis, "
            "       f.iyz_abonelik_durum, p.ad_tr AS paket_ad, "
            "       p.tur AS paket_tur "
            "  FROM firmalar f "
            "  LEFT JOIN paketler p ON p.anahtar = f.paket_anahtar "
            " ORDER BY f.firma_id")
    except Exception as e:
        h.hata_yaz(500, "Ozet okunamadi: %s" % e)
        return
    liste = []
    for s in satirlar:
        d = dict(s)
        for a in ("bakim_bitis", "odemesiz_bitis"):
            if d.get(a):
                d[a] = str(d[a])
        try:
            d["iskonto"] = len(paket.iskonto_listesi(int(d["firma_id"])))
        except Exception:
            d["iskonto"] = 0
        liste.append(d)
    h.json_yaz({"tamam": True, "kiracilar": liste})
'''

m = m.rstrip("\n") + "\n" + EKLENTI

with open(YOL, "w", encoding="utf-8") as f:
    f.write(m)

print("+ %d bayt eklendi (%d -> %d)" % (len(m) - taban, taban, len(m)))
print("TAMAM")
