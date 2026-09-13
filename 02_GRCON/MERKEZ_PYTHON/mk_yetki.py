"""GÖKTUNGU MERKEZ — abonelik ve yetki motoru.

TEK DOĞRULUK KAYNAĞI. Koltuk sayımı, özellik kilitleri ve lisans
muafiyeti YALNIZ bu modülden sorulur. Denetim mantığı çağıran yerlere
kopyalanırsa er ya da geç ikisi ayrışır ve biri sınırı atlar.

TASARIM KARARLARI
-----------------
1. **Koltuk yalnız pilotu sayar.** Ücretsiz taban "1 pilot + 1
   yönetici" olduğu için yöneticinin koltuk tüketmesi şirketin ilk
   pilotu hiç ekleyememesine yol açardı. `firma_yonetici` ve
   `gozlemci` koltuk tüketmez.

2. **Sınırsız, sayı değil bayraktır.** `pilot_koltuk = -1` gibi bir
   sihirli sayı kullanılsaydı `mevcut >= koltuk` karşılaştırması
   sessizce ters çalışırdı (her sayı -1'den büyüktür → sınırsız
   lisanslı şirket hiç pilot ekleyemezdi). Bu yüzden `sinirsiz`
   ayrı bir kolda, karşılaştırmadan ÖNCE ele alınır.

3. **Merkez lisansı sınırsızlığı kapsar.** Merkez Uygulama satın alan
   şirket kendi sunucusunda çalışır; koltuk ve AI ücretlerine tabi
   değildir.

4. **Etkinleştirme de koltuk tüketir.** Yalnız oluşturma denetlenirse
   şirket 20 pilotu pasif oluşturup sonra hepsini etkinleştirerek
   sınırı atlar.
"""
from __future__ import annotations

import json
import secrets
from typing import Any

import mk_db as db
import mk_paket as paket

# ---------------------------------------------------------------------------
# Ücret matrisi — tek kaynak
# ---------------------------------------------------------------------------
# Yıllık fiyat aylığın 12 katının %80'idir (kullanıcı: "yıllık isterse
# yüzde 20 daha düşük"). Tutarlar burada TÜRETİLİR, elle yazılmaz;
# aksi halde aylık fiyat değişince yıllık fiyat sessizce eskir.
YILLIK_INDIRIM = 0.20

# TOHUM VERİ — ÇALIŞMA ANINDA OKUNMAZ.
#
# Fiyat ve kapsamın TEK DOĞRULUK KAYNAĞI `paketler`
# tablosudur (bkz. mk_paket.py). Bu sözlük yalnız ilk
# kurulum ve göç için tohum olarak durur; `goc_sema9.sql`
# tabloyu bundan doldurdu.
#
# NEDEN SİLİNMEDİ: veritabanı boş kalırsa veya göç yarım
# biterse sistem fiyatsız kalır ve satın alma akışı çöker.
# Bu sözlük son çare geri düşüş katmanıdır.
#
# kalem -> (aylık USD, kazandırdığı pilot koltuğu, açıklama)
KALEMLER: dict[str, dict[str, Any]] = {
    "pilot_1": {"aylik": 5.0, "koltuk": 1, "ad": "Pilot koltuğu"},
    "pilot_5": {"aylik": 15.0, "koltuk": 5, "ad": "5 pilotluk paket"},
    "pilot_10": {"aylik": 35.0, "koltuk": 10, "ad": "10 pilotluk paket"},
    "ai": {"aylik": 10.0, "koltuk": 0, "ad": "AI sistemi"},
    # Merkez Uygulama tek seferliktir; aylık karşılığı yoktur.
    "merkez": {"tek": 5000.0, "koltuk": 0,
               "ad": "Merkez Uygulama kurulumu"},
    # Radar, GCCDUAL ve M50 SATILMAZ; yalnız VEILOX açık donanım tahsisi
    # ile açar. M50, radar yetkisinden bağımsız ve varsayılan kapalıdır.
    "radar": {"aylik": 0.0, "koltuk": 0, "ad": "Radar modülü"},
    "gccdual": {"aylik": 0.0, "koltuk": 0, "ad": "GCCDUAL modülü"},
    "m50": {"aylik": 0.0, "koltuk": 0, "ad": "M50 elektro-optik modülü"},
}

# Yalnız VEILOX sistem yöneticisinin açabileceği kalemler.
YALNIZ_VEILOX = ("radar", "gccdual", "m50")

# Ücretsiz taban
TABAN_PILOT_KOLTUK = 1


def yillik_usd(kalem: str) -> float:
    """Kalemin yıllık USD fiyatı (%20 indirimli).

    Paket tablosundan okunur; tabloda yoksa tohum veriye düşer.
    """
    try:
        a = paket.ham_fiyat(kalem, "aylik", "USD")
        return paket.yillik_tutar(a)
    except Exception:
        pass
    t = KALEMLER.get(kalem) or {}
    if "aylik" not in t:
        return 0.0
    return round(float(t["aylik"]) * 12 * (1.0 - YILLIK_INDIRIM), 2)


def kalem_fiyat(kalem: str, donem: str = "aylik",
                para: str = "USD") -> float:
    """Kalemin verilen dönemdeki birim fiyatı.

    Paket tablosu TEK KAYNAKTIR. Tabloda kayıt yoksa tohum
    veriye düşer; ikisinde de yoksa 0.0 döner.

    DİKKAT: 0.0 dönüşü BEDAVA SATIŞ demektir. Çağıran yer
    ödeme akışında bunu mutlaka denetlemelidir; bu yüzden
    ödeme uçları `mk_paket.net_fiyat()` kullanır ve o fonksiyon
    fiyat bulamazsa sessizce sıfır dönmek yerine HATA atar.
    """
    try:
        return paket.ham_fiyat(kalem, donem, para)
    except Exception:
        pass
    t = KALEMLER.get(kalem)
    if not t:
        return 0.0
    if donem == "tek":
        return float(t.get("tek") or 0.0)
    if donem == "yillik":
        return yillik_usd(kalem)
    return float(t.get("aylik") or 0.0)


def fiyat_listesi(firma_id: int | None = None,
                  para: str | None = None,
                  ust_yonetici: bool = False) -> list[dict[str, Any]]:
    """Arayüzlerin gösterdiği fiyat tablosu.

    Paket tablosundan üretilir. `firma_id` verilirse kiracıya
    özel iskontolu net fiyat da eklenir.
    """
    try:
        liste = paket.fiyat_listesi(firma_id, para, ust_yonetici)
        if liste:
            return liste
    except Exception:
        pass
    # Geri düşüş: tohum veriden üret (eski sözleşme)
    cikti = []
    for k, t in KALEMLER.items():
        if k in YALNIZ_VEILOX:
            continue  # satılmaz, listede gösterilmez
        tek = t.get("tek")
        cikti.append({
            "kalem": k,
            "ad": t["ad"],
            "koltuk": t["koltuk"],
            "tek_usd": float(tek) if tek else None,
            "aylik_usd": None if tek else float(t.get("aylik") or 0.0),
            "yillik_usd": None if tek else yillik_usd(k),
        })
    return cikti


# ---------------------------------------------------------------------------
# Firma yetkileri
# ---------------------------------------------------------------------------
def firma_yetkileri(firma_id: int) -> dict[str, Any]:
    """Firmanın tüm yetkilerini TEK sorguda döndürür.

    `pilot_bos` sınırsız durumda `None` döner — sayı DEĞİL. Böylece
    çağıran yer sınırsızlığı sayısal karşılaştırmayla yanlışlıkla
    "0 boş koltuk" sanamaz.
    """
    f = db.tek(
        "SELECT f.firma_id, f.kisa_ad, f.unvan, f.durum, f.abonelik, "
        "       f.abonelik_bitis, f.fatura_donemi, f.pilot_koltuk, "
        "       f.ai_etkin, f.radar_etkin, f.gccdual_etkin, f.m50_etkin, "
        "       f.merkez_lisans, f.merkez_lisans_ts, f.sinirsiz, "
        "       f.paket_anahtar, f.para_birimi, f.salt_okunur, "
        "       f.bakim_bitis, "
        "       f.maks_kullanici, f.maks_sunucu, "
        "       (SELECT count(*) FROM kullanicilar k "
        "         WHERE k.firma_id = f.firma_id AND k.rol = 'pilot' "
        "           AND k.durum = 'etkin') AS pilot_kullanilan, "
        "       (SELECT count(*) FROM kullanicilar k "
        "         WHERE k.firma_id = f.firma_id "
        "           AND k.durum = 'etkin') AS hesap_kullanilan "
        "FROM firmalar f WHERE f.firma_id = %s",
        (int(firma_id),))
    if not f:
        return {}
    sinirsiz = bool(f["sinirsiz"]) or bool(f["merkez_lisans"])
    koltuk = int(f["pilot_koltuk"])
    kullanilan = int(f["pilot_kullanilan"])
    return {
        "firma_id": int(f["firma_id"]),
        "kisa_ad": f["kisa_ad"],
        "unvan": f["unvan"],
        "durum": f["durum"],
        "abonelik": f["abonelik"],
        "abonelik_bitis": f["abonelik_bitis"],
        "fatura_donemi": f["fatura_donemi"],
        "sinirsiz": sinirsiz,
        "pilot_koltuk": koltuk,
        "pilot_kullanilan": kullanilan,
        # Sınırsızda None; sayısal karşılaştırmaya sokulmasın.
        "pilot_bos": None if sinirsiz else max(0, koltuk - kullanilan),
        "hesap_kullanilan": int(f["hesap_kullanilan"]),
        "maks_kullanici": int(f["maks_kullanici"]),
        # AI sınırsız lisansta da açıktır.
        "ai": sinirsiz or bool(f["ai_etkin"]),
        # Radar/GCCDUAL sınırsızlıktan BAĞIMSIZDIR: satılmazlar, yalnız
        # VEILOX açar. Merkez lisansı bunları kendiliğinden açmaz.
        "radar": bool(f["radar_etkin"]),
        "gccdual": bool(f["gccdual_etkin"]),
        # Eski/yamalı şema satırında alan bulunmuyorsa M50 asla açılmaz.
        "m50": bool(f.get("m50_etkin", False)),
        "merkez_lisans": bool(f["merkez_lisans"]),
        "merkez_lisans_ts": f["merkez_lisans_ts"],
        # --- Faz 14: paket, bakım ve ödeme durumu ---
        "paket": f["paket_anahtar"],
        "para_birimi": f["para_birimi"] or "TRY",
        # Salt-okunur kip: ödemesiz dönem bitti. Veri SİLİNMEZ,
        # yalnız yazma işlemleri kısıtlanır.
        "salt_okunur": bool(f["salt_okunur"]),
        "bakim_bitis": f["bakim_bitis"],
    }


def koltuk_uygun_mu(firma_id: int, rol: str) -> tuple[bool, str]:
    """Verilen rolde yeni bir ETKİN hesap açılabilir mi?

    Pilot dışı roller koltuk tüketmez; yalnız toplam hesap üst sınırı
    (`maks_kullanici`) uygulanır — aksi halde sınırsız sayıda gözlemci
    açılabilirdi.
    """
    y = firma_yetkileri(firma_id)
    if not y:
        return False, "Firma bulunamadı"
    if y["durum"] != "etkin":
        return False, "Firma hesabı etkin değil"
    # SALT-OKUNUR KİP (Faz 14): ödemesiz dönem bitmiş.
    # Yeni koltuk açılamaz ancak MEVCUT veri ve kullanıcılar
    # OLDUĞU GİBİ ÇALIŞIR — hiçbir şey silinmez.
    if y.get("salt_okunur"):
        return False, ("Aboneliğiniz ödeme bekliyor. Mevcut "
                       "hesaplarınız çalışmaya devam eder; yeni "
                       "hesap açmak için ödemenizi tamamlayın.")
    if y["sinirsiz"]:
        return True, ""
    if rol == "pilot":
        if y["pilot_kullanilan"] >= y["pilot_koltuk"]:
            return False, (
                "Pilot koltuğu dolu (%d/%d). Yeni pilot eklemek için "
                "kurumsal panelden pilot koltuğu talep edin."
                % (y["pilot_kullanilan"], y["pilot_koltuk"]))
        return True, ""
    if y["hesap_kullanilan"] >= y["maks_kullanici"]:
        return False, ("Hesap üst sınırına ulaşıldı (%d). Artırmak için "
                       "kurumsal panelden talep oluşturun."
                       % y["maks_kullanici"])
    return True, ""


def ozellik_acik_mi(firma_id: int, ozellik: str) -> bool:
    """`ai` | `radar` | `gccdual` | `m50` | `merkez_lisans` yetkisi açık mı?"""
    y = firma_yetkileri(firma_id)
    if not y:
        return False
    return bool(y.get(ozellik))


def kopru_yetkileri(firma_id: int) -> dict[str, bool]:
    """Köprünün giriş yanıtına eklenen özet.

    Köprü paneli hangi servis menülerini göstereceğine buna bakar.
    Dron/video her zaman açıktır; ücretlendirilmeyen çekirdek
    yeteneklerdir.
    """
    y = firma_yetkileri(firma_id)
    return {
        "dron": True,
        "video": True,
        "ai": bool(y.get("ai")),
        "radar": bool(y.get("radar")),
        "gccdual": bool(y.get("gccdual")),
        "m50": bool(y.get("m50", False)),
    }


# ---------------------------------------------------------------------------
# Kalem uygulama (VEILOX elle tanımlama ve talep onayı)
# ---------------------------------------------------------------------------
def kalem_uygula(firma_id: int, kalem: str, adet: int = 1,
                 donem: str = "aylik", kaynak: str = "veilox",
                 yonetici_id: int | None = None,
                 notlar: str | None = None,
                 bitis: str | None = None) -> tuple[bool, str]:
    """Firmaya bir abonelik kalemi tanımlar ve yetkilerini günceller.

    `kaynak='veilox'` → sistem yöneticisi ödeme akışını atlayarak
    tanımladı. Kullanıcı bunu açıkça istedi.
    """
    # Paket tablosu TEK KAYNAKTIR; tohum veri yalnız geri düşüş.
    t = None
    try:
        p = paket.paket(kalem)
        t = {"koltuk": int(p["koltuk"]), "ad": p["ad_tr"],
             "paket": p}
    except Exception:
        t = KALEMLER.get(kalem)
    if not t:
        return False, "Geçersiz kalem: %s" % kalem
    if adet < 1:
        return False, "Adet en az 1 olmalı"
    if kalem == "merkez":
        donem = "tek"
    if donem not in ("aylik", "yillik", "tek"):
        return False, "Geçersiz dönem: %s" % donem
    if not db.tek("SELECT 1 FROM firmalar WHERE firma_id = %s",
                  (int(firma_id),)):
        return False, "Firma bulunamadı"

    birim = kalem_fiyat(kalem, donem)
    db.calistir(
        "INSERT INTO abonelik_kalemleri (firma_id, kalem, adet, donem, "
        "  birim_usd, toplam_usd, kaynak, veren_yonetici_id, bitis, notlar) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (int(firma_id), kalem, int(adet), donem, birim,
         round(birim * adet, 2), kaynak, yonetici_id, bitis, notlar))

    # Yetki etkisi ------------------------------------------------------
    # KOLTUK BAŞINA FİYATLAMA (Faz 14): Profesyonel paket pilot
    # başına ücretlendirilir; `adet` doğrudan koltuk sayısıdır.
    # `koltuk` alanı 1 olduğu için çarpım zaten doğru sonucu
    # verir, ancak sınırsız koltuklu paketlerde çarpım YAPILMAZ.
    _p = t.get("paket") if isinstance(t, dict) else None
    if _p and _p.get("koltuk_sinirsiz"):
        koltuk = 0            # sınırsızlık bayrakla verilir
    else:
        koltuk = int(t["koltuk"]) * int(adet)
    if koltuk:
        db.calistir(
            "UPDATE firmalar SET pilot_koltuk = pilot_koltuk + %s, "
            "  guncel_ts = now() WHERE firma_id = %s",
            (koltuk, int(firma_id)))
    # PAKET KAPSAMI (Faz 14): yeni paketler kapsamı tablodan
    # taşır. Kurumsal Bulut YZ modülünü DAHİL eder; lisans
    # SKU'ları radar/gccdual kapsamını taşıyabilir.
    if _p:
        if _p.get("ai_dahil"):
            db.calistir("UPDATE firmalar SET ai_etkin = true, "
                        "guncel_ts = now() WHERE firma_id = %s",
                        (int(firma_id),))
        if _p.get("radar_dahil"):
            db.calistir("UPDATE firmalar SET radar_etkin = true, "
                        "guncel_ts = now() WHERE firma_id = %s",
                        (int(firma_id),))
        if _p.get("gccdual_dahil"):
            db.calistir("UPDATE firmalar SET gccdual_etkin = true, "
                        "guncel_ts = now() WHERE firma_id = %s",
                        (int(firma_id),))
        if _p.get("koltuk_sinirsiz"):
            db.calistir(
                "UPDATE firmalar SET sinirsiz = true, "
                "  abonelik = 'sinirsiz', guncel_ts = now() "
                "WHERE firma_id = %s", (int(firma_id),))
        # Kiracının paket bağı güncellenir.
        db.calistir("UPDATE firmalar SET paket_anahtar = %s, "
                    "guncel_ts = now() WHERE firma_id = %s",
                    (kalem, int(firma_id)))
        # Kapalı devre lisansında bakım kapsamı 1 yıl başlar.
        if _p.get("tur") == "lisans":
            db.calistir(
                "UPDATE firmalar SET bakim_bitis = "
                "  (CURRENT_DATE + INTERVAL '1 year')::date, "
                "  guncel_ts = now() WHERE firma_id = %s",
                (int(firma_id),))
    if kalem == "ai":
        db.calistir("UPDATE firmalar SET ai_etkin = true, guncel_ts = now() "
                    "WHERE firma_id = %s", (int(firma_id),))
    elif kalem == "radar":
        db.calistir("UPDATE firmalar SET radar_etkin = true, "
                    "guncel_ts = now() WHERE firma_id = %s", (int(firma_id),))
    elif kalem == "gccdual":
        db.calistir("UPDATE firmalar SET gccdual_etkin = true, "
                    "guncel_ts = now() WHERE firma_id = %s", (int(firma_id),))
    elif kalem == "m50":
        db.calistir("UPDATE firmalar SET m50_etkin = true, "
                    "guncel_ts = now() WHERE firma_id = %s", (int(firma_id),))
    elif kalem == "merkez":
        # Merkez Uygulama SINIRSIZ kullanım hakkı kazandırır.
        db.calistir(
            "UPDATE firmalar SET merkez_lisans = true, sinirsiz = true, "
            "  merkez_lisans_ts = coalesce(merkez_lisans_ts, now()), "
            "  abonelik = 'sinirsiz', guncel_ts = now() "
            "WHERE firma_id = %s", (int(firma_id),))
    if donem in ("aylik", "yillik"):
        db.calistir("UPDATE firmalar SET fatura_donemi = %s, "
                    "guncel_ts = now() WHERE firma_id = %s",
                    (donem, int(firma_id)))
    return True, ""


def yetki_ayarla(firma_id: int, alan: str, deger: bool,
                 yonetici_id: int | None = None) -> tuple[bool, str]:
    """VEILOX sistem yöneticisinin anahtar açma/kapama işlemi.

    Yalnız `radar`, `gccdual`, `m50`, `ai`, `merkez_lisans`, `sinirsiz`.
    """
    esleme = {
        "radar": "radar_etkin",
        "gccdual": "gccdual_etkin",
        "m50": "m50_etkin",
        "ai": "ai_etkin",
        "merkez_lisans": "merkez_lisans",
        "sinirsiz": "sinirsiz",
    }
    kolon = esleme.get(alan)
    if not kolon:
        return False, "Geçersiz yetki alanı: %s" % alan
    if not db.tek("SELECT 1 FROM firmalar WHERE firma_id = %s",
                  (int(firma_id),)):
        return False, "Firma bulunamadı"
    db.calistir("UPDATE firmalar SET %s = %%s, guncel_ts = now() "
                "WHERE firma_id = %%s" % kolon,
                (bool(deger), int(firma_id)))
    # Merkez lisansı açılırsa sınırsızlık da açılır (satın alan şirket
    # sınırsız kullanım hakkı kazanır).
    if alan == "merkez_lisans" and deger:
        db.calistir(
            "UPDATE firmalar SET sinirsiz = true, abonelik = 'sinirsiz', "
            "  merkez_lisans_ts = coalesce(merkez_lisans_ts, now()), "
            "  guncel_ts = now() WHERE firma_id = %s", (int(firma_id),))
    return True, ""


def kalem_listesi(firma_id: int) -> list[dict]:
    return db.sorgu(
        "SELECT kalem_id, kalem, adet, donem, birim_usd, toplam_usd, "
        "       kaynak, baslangic, bitis, durum, notlar, olusma_ts "
        "FROM abonelik_kalemleri WHERE firma_id = %s "
        "ORDER BY olusma_ts DESC", (int(firma_id),))


# ---------------------------------------------------------------------------
# Üyelik talepleri
# ---------------------------------------------------------------------------
def talep_olustur(firma_id: int | None, kalem: str, adet: int = 1,
                  donem: str = "aylik", iletisim_ad: str = "",
                  iletisim_eposta: str = "", iletisim_tel: str = "",
                  mesaj: str = "") -> tuple[int | None, str]:
    if kalem not in KALEMLER:
        return None, "Geçersiz kalem"
    if kalem in YALNIZ_VEILOX:
        return None, ("Bu modül satın alınamaz; sistem yöneticisi tarafından "
                      "tanımlanır. Lütfen bizimle iletişime geçin.")
    if adet < 1:
        return None, "Adet en az 1 olmalı"
    tid = db.deger(
        "INSERT INTO uyelik_talepleri (firma_id, kalem, adet, donem, "
        "  iletisim_ad, iletisim_eposta, iletisim_tel, mesaj) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING talep_id",
        (firma_id, kalem, int(adet), donem, iletisim_ad or None,
         iletisim_eposta or None, iletisim_tel or None, mesaj or None))
    return int(tid), ""


def talep_karar(talep_id: int, onay: bool, yonetici_id: int | None = None,
                notu: str = "") -> tuple[bool, str]:
    t = db.tek("SELECT * FROM uyelik_talepleri WHERE talep_id = %s",
               (int(talep_id),))
    if not t:
        return False, "Talep bulunamadı"
    if t["durum"] != "bekliyor":
        return False, "Talep zaten sonuçlanmış (%s)" % t["durum"]
    db.calistir(
        "UPDATE uyelik_talepleri SET durum = %s, karar_yonetici_id = %s, "
        "  karar_ts = now(), karar_notu = %s WHERE talep_id = %s",
        ("onaylandi" if onay else "reddedildi", yonetici_id,
         notu or None, int(talep_id)))
    if onay and t["firma_id"]:
        return kalem_uygula(int(t["firma_id"]), t["kalem"], int(t["adet"]),
                            t["donem"], kaynak="talep",
                            yonetici_id=yonetici_id,
                            notlar="Talep #%d onayı" % int(talep_id))
    return True, ""


def talep_listesi(durum: str | None = None,
                  firma_id: int | None = None) -> list[dict]:
    kosul, par = [], []
    if durum:
        kosul.append("t.durum = %s")
        par.append(durum)
    if firma_id:
        kosul.append("t.firma_id = %s")
        par.append(int(firma_id))
    nerede = (" WHERE " + " AND ".join(kosul)) if kosul else ""
    return db.sorgu(
        "SELECT t.*, f.kisa_ad AS firma_kisa_ad, f.unvan AS firma_unvan "
        "FROM uyelik_talepleri t "
        "LEFT JOIN firmalar f ON f.firma_id = t.firma_id" + nerede +
        " ORDER BY t.olusma_ts DESC LIMIT 500", tuple(par))


# ---------------------------------------------------------------------------
# Merkez Uygulama lisansı
# ---------------------------------------------------------------------------
_UID_ABC = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # I,O,0,1 yok (karışmasın)


def _lisans_uid() -> str:
    def blok() -> str:
        return "".join(secrets.choice(_UID_ABC) for _ in range(4))
    return "MRK-%s-%s" % (blok(), blok())


def lisans_govdesi(firma_id: int) -> dict[str, Any]:
    """İmzalanacak lisans gövdesi. Anahtar sırası SABİT tutulmalıdır;
    imza gövdenin bayt dizisi üzerinden üretilir."""
    y = firma_yetkileri(firma_id)
    if not y:
        raise ValueError("Firma bulunamadı: %s" % firma_id)
    return {
        "surum": 1,
        "firma_id": y["firma_id"],
        "firma_unvan": y["unvan"],
        "yetkiler": {
            "sinirsiz": True,          # Merkez Uygulama = sınırsız
            "ai": bool(y["ai"]),
            "radar": bool(y["radar"]),
            "gccdual": bool(y["gccdual"]),
            # Yeni lisanslarda alan her zaman vardır; eski belgede yoksa
            # istemci bunu kapalı kabul etmek zorundadır.
            "m50": bool(y.get("m50", False)),
        },
    }


def govde_bayt(govde: dict[str, Any]) -> bytes:
    """Gövdenin imzalanacak kanonik baytları.

    `sort_keys=True` ZORUNLU: sözlük sırası değişse bile imza aynı
    kalmalı, aksi halde doğrulama rastgele başarısız olur.
    """
    return json.dumps(govde, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def lisans_uret(firma_id: int) -> tuple[dict | None, str]:
    """Firma için imzalı lisans üretir (veya var olanı döndürür).

    İMZA BÜTÜNLÜĞÜ — DİKKAT
    ----------------------
    İmza, `lisans_uid` DAHİL eksiksiz gövde üzerinden üretilir. Bu
    yüzden var olan lisans yeniden kullanılırken gövde, imzanın
    üretildiği ANDAKİ haliyle birebir yeniden kurulmalıdır; önce
    imzalayıp sonra gövdeye alan eklemek (veya tersini yapmak) imzayı
    geçersiz kılar. İlk sürümde tam bu kusur vardı: `lisans_uid` yeni
    lisansta imzadan ÖNCE, yeniden kullanılan lisansta imzadan SONRA
    ekleniyordu; ikinci indirmede doğrulama başarısız oluyordu. Kapalı
    devre kurulumda bunun sonucu, yazılımın hiç açılmamasıdır.
    """
    import mk_depo as depo

    y = firma_yetkileri(firma_id)
    if not y:
        return None, "Firma bulunamadı"
    if not y["merkez_lisans"]:
        return None, "Bu firmanın Merkez Uygulama lisansı yok"

    govde = lisans_govdesi(firma_id)
    # Var olan iptal edilmemiş lisans YENİDEN KULLANILIR; her indirmede
    # yeni UID üretmek sahadaki kurulumların izini kaybettirirdi.
    mevcut = db.tek(
        "SELECT lisans_uid, yetkiler, imza FROM merkez_lisanslari "
        "WHERE firma_id = %s AND iptal_ts IS NULL "
        "ORDER BY olusma_ts DESC LIMIT 1", (int(firma_id),))
    if mevcut:
        eski = mevcut["yetkiler"]
        if isinstance(eski, str):
            eski = json.loads(eski)
        # Yetkiler değişmişse lisans TAZELENİR; aksi halde şirket
        # sonradan açılan AI/Radar'ı kapalı devrede kullanamaz.
        if eski == govde["yetkiler"]:
            govde["lisans_uid"] = mevcut["lisans_uid"]
            # İmza bu gövdeyi gerçekten doğrulamalı. Doğrulamazsa
            # (örn. imza anahtarı döndürüldü, ya da eski bir sürümün
            # tutarsız imzası kayıtta kaldı) sessizce bozuk lisans
            # vermek yerine yeniden imzalanır.
            if depo.veri_imza_dogrula(govde_bayt(govde), mevcut["imza"]):
                db.calistir(
                    "UPDATE merkez_lisanslari SET indirme_sayisi = "
                    "  indirme_sayisi + 1, son_indirme_ts = now() "
                    "WHERE lisans_uid = %s", (mevcut["lisans_uid"],))
                return {"govde": govde, "imza": mevcut["imza"]}, ""
            try:
                yeni_imza = depo.veri_imzala(govde_bayt(govde))
            except Exception as e:
                return None, "Lisans imzalanamadı: %s" % e
            db.calistir(
                "UPDATE merkez_lisanslari SET imza = %s, "
                "  indirme_sayisi = indirme_sayisi + 1, "
                "  son_indirme_ts = now() WHERE lisans_uid = %s",
                (yeni_imza, mevcut["lisans_uid"]))
            return {"govde": govde, "imza": yeni_imza}, ""
        db.calistir("UPDATE merkez_lisanslari SET iptal_ts = now() "
                    "WHERE lisans_uid = %s", (mevcut["lisans_uid"],))

    govde["lisans_uid"] = _lisans_uid()
    try:
        imza = depo.veri_imzala(govde_bayt(govde))
    except Exception as e:                       # imza anahtarı yoksa
        return None, "Lisans imzalanamadı: %s" % e
    db.calistir(
        "INSERT INTO merkez_lisanslari (firma_id, lisans_uid, yetkiler, "
        "  imza, indirme_sayisi, son_indirme_ts) "
        "VALUES (%s,%s,%s,%s,1,now())",
        (int(firma_id), govde["lisans_uid"],
         json.dumps(govde["yetkiler"], sort_keys=True), imza))
    return {"govde": govde, "imza": imza}, ""


def lisans_dogrula(govde: dict[str, Any], imza_b64: str) -> bool:
    """Lisans imzasını doğrular (merkez tarafı sınavı için)."""
    import mk_depo as depo
    g = dict(govde)
    return depo.veri_imza_dogrula(govde_bayt(g), imza_b64)
