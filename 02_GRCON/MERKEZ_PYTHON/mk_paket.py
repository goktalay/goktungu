"""GÖKTUNGU MERKEZ — paket kataloğu ve fiyatlandırma motoru.

TEK DOĞRULUK KAYNAĞI: paket tanımı, fiyat ve kapsam YALNIZ `paketler`
tablosundan okunur. Fiyat kodda sabitlenmez; fiyat değişikliği kod
dağıtımı gerektirmez.

`mk_yetki.KALEMLER` sözlüğü TOHUM VERİ olarak yerinde kalır ancak
çalışma anında OKUNMAZ — göç betiği tabloyu ondan doldurur.

TASARIM KARARLARI
-----------------
1. **Fiyat bulunamazsa HATA verilir.** `0.0` dönmek bedava satış
   demektir; sessiz sıfır en pahalı kusur türüdür.

2. **İki para birimi zorunlu.** iyzico belgelenmiş kısıtı: yabancı para
   biriminde yalnız yabancı kart kullanılabilir. Türk müşteri USD
   planına Türk kartıyla abone olamaz. Bu yüzden her paketin TRY ve USD
   fiyatı ayrı tutulur; kiracının `para_birimi` alanı hangisinin
   uygulanacağını belirler.

3. **İskonto sırası: ÖNCE dönem indirimi, SONRA müşteri iskontosu.**
   Ters sıra müşteriye pazarlıkta beklediğinden az indirim verir.
   Örnek: 100 birim, yıllık %20, müşteri %10.
     Doğru : 100×12×0.80 = 960 → 960×0.90 = 864
     Ters  : 100×0.90 = 90 → 90×12×0.80 = 864  (aynı)
   Yüzde iskontolarda sıra matematiksel olarak fark etmez, ancak
   TUTAR iskontosunda eder: 960 − 50 = 910 iken 100−50=50 → 480.
   Bu yüzden tutar iskontosu DAİMA dönem toplamına uygulanır.

4. **İskonto negatif fiyat üretemez.** Tutar iskontosu paket fiyatını
   aşarsa sonuç 0'a kelepçelenir. Yüzde zaten CHECK ile ≤100.

5. **Önbellek TTL 60 sn.** Brifing gereği. Fiyat sorgusu her istekte
   veritabanına gitmez ama 60 saniyeden eski veri de kullanılmaz.
   Fiyat güncellemesi `onbellek_bosalt()` ile hemen yayılır.
"""
from __future__ import annotations

import threading
import time
from typing import Any

import mk_db as db

# Dönem indirimi — yıllık peşin ödeme (brifing: %20 korunur)
YILLIK_INDIRIM = 0.20

# Önbellek ömrü (saniye). Brifing: yetki servisi TTL ≤ 60 sn.
ONBELLEK_OMRU = 60.0

_kilit = threading.Lock()
_onbellek: dict[str, Any] = {"ts": 0.0, "paketler": None}


class PaketHatasi(Exception):
    """Paket veya fiyat bulunamadı. Sessizce 0.0 dönmek yerine atılır."""


# ---------------------------------------------------------------------------
# Katalog okuma
# ---------------------------------------------------------------------------
def _paketleri_oku() -> dict[str, dict]:
    satirlar = db.sorgu(
        "SELECT anahtar, ad_tr, ad_en, tur, aylik_usd, aylik_try, "
        "       tek_usd, tek_try, koltuk, koltuk_basina, koltuk_sinirsiz, "
        "       ai_dahil, radar_dahil, gccdual_dahil, bakim_orani, "
        "       fiyat_tabani, satilabilir, vitrin, yalniz_ust, miras, ucretsiz, "
        "       sira, aciklama_tr, aciklama_en, durum, "
        "       iyz_urun_ref, iyz_plan_ref_ay_try, iyz_plan_ref_yil_try, "
        "       iyz_plan_ref_ay_usd, iyz_plan_ref_yil_usd "
        "FROM paketler WHERE durum = 'etkin' ORDER BY sira, anahtar")
    return {s["anahtar"]: dict(s) for s in satirlar}


def katalog(tazele: bool = False) -> dict[str, dict]:
    """Etkin paketlerin tamamı. 60 sn önbellekli."""
    simdi = time.time()
    with _kilit:
        bayat = (simdi - float(_onbellek["ts"])) > ONBELLEK_OMRU
        if tazele or bayat or _onbellek["paketler"] is None:
            _onbellek["paketler"] = _paketleri_oku()
            _onbellek["ts"] = simdi
        return _onbellek["paketler"]


def onbellek_bosalt() -> None:
    """Fiyat/paket değişikliğinden sonra çağrılır; TTL beklenmez."""
    with _kilit:
        _onbellek["ts"] = 0.0
        _onbellek["paketler"] = None


def paket(anahtar: str) -> dict:
    """Tek paketi döndürür. Yoksa `PaketHatasi` atar."""
    p = katalog().get(anahtar)
    if not p:
        # Önbellek bayat olabilir; bir kez tazeleyip yeniden dene.
        p = katalog(tazele=True).get(anahtar)
    if not p:
        raise PaketHatasi("Paket bulunamadı: %s" % anahtar)
    return p


def paket_var_mi(anahtar: str) -> bool:
    try:
        paket(anahtar)
        return True
    except PaketHatasi:
        return False


# ---------------------------------------------------------------------------
# Fiyatlandırma
# ---------------------------------------------------------------------------
def _birim_fiyat(p: dict, donem: str, para: str) -> float | None:
    """Paketin ham birim fiyatı (iskonto ve dönem indirimi UYGULANMAMIŞ).

    `None` dönerse paket o dönem/para biriminde satılmıyor.
    """
    para = (para or "TRY").upper()
    if donem == "tek":
        d = p.get("tek_try") if para == "TRY" else p.get("tek_usd")
    else:
        d = p.get("aylik_try") if para == "TRY" else p.get("aylik_usd")
    return None if d is None else float(d)


def yillik_tutar(aylik: float) -> float:
    """Aylık fiyattan yıllık peşin tutarı (%20 indirimli)."""
    return round(aylik * 12 * (1.0 - YILLIK_INDIRIM), 2)


def ham_fiyat(anahtar: str, donem: str = "aylik",
              para: str = "TRY", adet: int = 1) -> float:
    """İskonto UYGULANMAMIŞ toplam tutar.

    `donem`: `aylik` | `yillik` | `tek`
    """
    p = paket(anahtar)
    if donem == "tek":
        birim = _birim_fiyat(p, "tek", para)
        if birim is None:
            raise PaketHatasi(
                "%s paketi %s biriminde tek seferlik satılmıyor"
                % (anahtar, para))
        return round(birim * max(1, int(adet)), 2)

    aylik = _birim_fiyat(p, "aylik", para)
    if aylik is None:
        raise PaketHatasi(
            "%s paketi %s biriminde abonelik olarak satılmıyor"
            % (anahtar, para))
    if donem == "yillik":
        return round(yillik_tutar(aylik) * max(1, int(adet)), 2)
    if donem == "aylik":
        return round(aylik * max(1, int(adet)), 2)
    raise PaketHatasi("Geçersiz dönem: %s" % donem)


# ---------------------------------------------------------------------------
# İskonto
# ---------------------------------------------------------------------------
def etkin_iskontolar(firma_id: int, paket_anahtar: str | None = None
                     ) -> list[dict]:
    """Firmanın bugün geçerli iskontoları.

    `paket_anahtar` verilirse yalnız o pakete VE tüm paketlere geçerli
    olanlar (NULL) döner.
    """
    return db.sorgu(
        "SELECT iskonto_id, paket_anahtar, tur, deger, para_birimi, "
        "       gecerli_bas, gecerli_bit, gerekce "
        "FROM iskontolar "
        "WHERE firma_id = %s AND durum = 'etkin' "
        "  AND gecerli_bas <= CURRENT_DATE "
        "  AND (gecerli_bit IS NULL OR gecerli_bit >= CURRENT_DATE) "
        "  AND (paket_anahtar IS NULL OR paket_anahtar = %s) "
        "ORDER BY paket_anahtar NULLS LAST, iskonto_id",
        (int(firma_id), paket_anahtar))


def iskonto_uygula(tutar: float, iskontolar: list[dict],
                   para: str = "TRY") -> tuple[float, float, int | None]:
    """İskontoları uygular.

    Dönüş: (net tutar, indirilen tutar, kullanılan iskonto kimliği)

    KURALLAR
    --------
    * Pakete özgü iskonto, genel iskontoya göre ÖNCELİKLİDİR (sorgu
      sıralaması bunu sağlar; ilk uygun kayıt kullanılır).
    * Tutar iskontosu YALNIZ kendi para biriminde uygulanır. Farklı
      birimdeki kayıt ATLANIR — 10 USD indirimi 10 TRY sanmak ciddi
      bir hata olurdu.
    * Sonuç asla negatif olmaz; 0'a kelepçelenir.
    * Tek iskonto uygulanır (kümülatif indirim istenmiyor; iki ayrı
      %50 iskonto ürünü bedava yapardı).
    """
    para = (para or "TRY").upper()
    for i in iskontolar:
        if i["tur"] == "yuzde":
            oran = float(i["deger"]) / 100.0
            net = round(tutar * (1.0 - oran), 2)
            return max(0.0, net), round(tutar - net, 2), int(i["iskonto_id"])
        if i["tur"] == "tutar":
            if (i.get("para_birimi") or "").upper() != para:
                continue          # birim uyuşmuyor, bu kaydı atla
            net = round(tutar - float(i["deger"]), 2)
            net = max(0.0, net)
            return net, round(tutar - net, 2), int(i["iskonto_id"])
    return round(tutar, 2), 0.0, None


def net_fiyat(firma_id: int | None, anahtar: str, donem: str = "aylik",
              para: str = "TRY", adet: int = 1) -> dict:
    """Kiracıya özel nihai fiyat.

    Dönüş sözlüğü arayüzün ve ödeme akışının ORTAK sözleşmesidir;
    ikisi ayrı hesap yaparsa er ya da geç ayrışırlar.
    """
    brut = ham_fiyat(anahtar, donem, para, adet)
    if not firma_id:
        return {"paket": anahtar, "donem": donem, "para_birimi": para,
                "adet": int(adet), "brut": brut, "iskonto": 0.0,
                "net": brut, "iskonto_id": None}
    isk = etkin_iskontolar(int(firma_id), anahtar)
    net, indirilen, iid = iskonto_uygula(brut, isk, para)
    return {"paket": anahtar, "donem": donem, "para_birimi": para,
            "adet": int(adet), "brut": brut, "iskonto": indirilen,
            "net": net, "iskonto_id": iid}


# ---------------------------------------------------------------------------
# Arayüz fiyat listesi
# ---------------------------------------------------------------------------
def fiyat_listesi(firma_id: int | None = None, para: str | None = None,
                  ust_yonetici: bool = False) -> list[dict]:
    """Arayüzlerin gösterdiği paket listesi.

    * `ust_yonetici = False` → satılmayan paketler (modüller, SKU'lar,
      miras planlar) LİSTELENMEZ. Müşteri satın alamayacağı bir şeyi
      görmemeli.
    * `ust_yonetici = True` → hepsi listelenir (yönetim paneli).
    * `firma_id` verilirse iskontolu net fiyat da eklenir.
    """
    para = (para or "TRY").upper()
    cikti: list[dict] = []
    for a, p in katalog().items():
        if not ust_yonetici:
            # GOSTERIM != SATIN ALINABILIRLIK.
            # SKU basamaklari satilabilir=FALSE ama vitrin=TRUE:
            # fiyati gorunur, odeme akisi talep uzerine yurur.
            if not p.get("vitrin"):
                continue
        satir: dict[str, Any] = {
            "paket": a,
            # kalem/ad esanlamlilari -- ZORUNLU.
            # Tum arayuzler ve eski sozlesme `kalem` + `ad` okur:
            #   kurumsal panel  -> kacir(f.ad)          (baslik)
            #   satin al dugmesi -> data-kalem="${f.kalem}"
            #   talep penceresi  -> [f.kalem, f.ad]
            # Bu alanlar olmadan sayfa ACILIR, kartlar GORULUR, ama
            # isimsiz ve tiklanamaz olur -- sessiz bozulma.
            "kalem": a,
            "anahtar": a,
            "ad": p["ad_tr"],
            "ad_tr": p["ad_tr"],
            "ad_en": p["ad_en"],
            "tur": p["tur"],
            "koltuk": int(p["koltuk"]),
            "koltuk_basina": bool(p["koltuk_basina"]),
            "koltuk_sinirsiz": bool(p["koltuk_sinirsiz"]),
            "ai_dahil": bool(p["ai_dahil"]),
            "radar_dahil": bool(p["radar_dahil"]),
            "gccdual_dahil": bool(p["gccdual_dahil"]),
            "ucretsiz": bool(p["ucretsiz"]),
            "miras": bool(p["miras"]),
            "satilabilir": bool(p["satilabilir"]),
            "vitrin": bool(p.get("vitrin")),
            "yalniz_ust": bool(p["yalniz_ust"]),
            "fiyat_tabani": bool(p["fiyat_tabani"]),
            "bakim_orani": (float(p["bakim_orani"])
                            if p["bakim_orani"] is not None else None),
            "aciklama_tr": p["aciklama_tr"],
            "aciklama_en": p["aciklama_en"],
            "para_birimi": para,
            "sira": int(p["sira"]),
        }
        # Ham fiyatlar — her iki para birimi de verilir; arayüz
        # kiracının birimini gösterir ama diğerini de bilir.
        for pb in ("TRY", "USD"):
            ek = pb.lower()
            aylik = _birim_fiyat(p, "aylik", pb)
            tek = _birim_fiyat(p, "tek", pb)
            satir["aylik_" + ek] = aylik
            satir["yillik_" + ek] = (yillik_tutar(aylik)
                                     if aylik is not None else None)
            satir["tek_" + ek] = tek
        # Kiracıya özel net fiyat.
        #
        # KOSUL `vitrin`, `satilabilir` DEGIL. SKU basamaklari
        # (GTU-MERKEZ, GTU-TAM ...) `satilabilir=FALSE` cunku kredi
        # kartiyla dogrudan satilmiyorlar -- sozlesmeyle veriliyorlar.
        # Ama kullanicinin acik talebi "musteriye ozel iskonto";
        # 180.000 USD'lik lisansta iskonto EN COK orada gerekir.
        # `satilabilir` kosulu bu kalemleri iskonto disinda birakiyordu.
        if firma_id and p.get("vitrin"):
            for donem in ("aylik", "yillik", "tek"):
                try:
                    net = net_fiyat(firma_id, a, donem, para)["net"]
                except PaketHatasi:
                    net = None
                # Eski ad KORUNUR (baska okuyucular kirilmasin) ve
                # para birimi ekli ad EKLENIR -- ham fiyatlar
                # `aylik_try`/`aylik_usd` bicimindeyken net fiyatin
                # eksiz olmasi arayuzde eslesmeme yaratiyordu.
                satir["net_" + donem] = net
                satir["net_" + donem + "_" + para.lower()] = net
        cikti.append(satir)
    return cikti


# ---------------------------------------------------------------------------
# Paket yönetimi (yönetim paneli)
# ---------------------------------------------------------------------------
_GUNCELLENEBILIR = (
    "ad_tr", "ad_en", "aylik_usd", "aylik_try", "tek_usd", "tek_try",
    "koltuk", "koltuk_basina", "koltuk_sinirsiz", "ai_dahil",
    "radar_dahil", "gccdual_dahil", "bakim_orani", "fiyat_tabani",
    "satilabilir", "vitrin", "yalniz_ust", "miras", "ucretsiz", "sira",
    "aciklama_tr", "aciklama_en", "durum",
)


def paket_guncelle(anahtar: str, alanlar: dict) -> tuple[bool, str]:
    """Paket alanlarını güncelle (yönetim paneli).

    Beyaz liste ZORUNLU: aksi halde `anahtar` veya `paket_id` gibi
    kimlik alanları dışarıdan değiştirilebilirdi.
    """
    if not paket_var_mi(anahtar):
        return False, "Paket bulunamadı: %s" % anahtar
    setler, par = [], []
    for k, v in (alanlar or {}).items():
        if k not in _GUNCELLENEBILIR:
            continue
        setler.append("%s = %%s" % k)
        par.append(v)
    if not setler:
        return False, "Güncellenecek geçerli alan yok"
    setler.append("guncel_ts = now()")
    par.append(anahtar)
    db.calistir("UPDATE paketler SET %s WHERE anahtar = %%s"
                % ", ".join(setler), tuple(par))
    onbellek_bosalt()
    return True, ""


def iskonto_tanimla(firma_id: int, tur: str, deger: float,
                    paket_anahtar: str | None = None,
                    para_birimi: str | None = None,
                    gecerli_bas: str | None = None,
                    gecerli_bit: str | None = None,
                    gerekce: str = "",
                    yonetici_id: int | None = None
                    ) -> tuple[int | None, str]:
    """Kiracıya özel iskonto tanımlar (kullanıcı talebi)."""
    if tur not in ("yuzde", "tutar"):
        return None, "Geçersiz iskonto türü: %s" % tur
    try:
        d = float(deger)
    except (TypeError, ValueError):
        return None, "İskonto değeri sayı olmalı"
    if d <= 0:
        return None, "İskonto değeri sıfırdan büyük olmalı"
    if tur == "yuzde" and d > 100:
        return None, "Yüzde iskonto 100'ü aşamaz"
    if tur == "tutar":
        pb = (para_birimi or "").upper()
        if pb not in ("TRY", "USD"):
            return None, ("Tutar iskontosunda para birimi zorunludur "
                          "(TRY veya USD)")
        para_birimi = pb
    else:
        para_birimi = None
    if paket_anahtar and not paket_var_mi(paket_anahtar):
        return None, "Paket bulunamadı: %s" % paket_anahtar
    if not db.tek("SELECT 1 FROM firmalar WHERE firma_id = %s",
                  (int(firma_id),)):
        return None, "Firma bulunamadı"
    iid = db.deger(
        "INSERT INTO iskontolar (firma_id, paket_anahtar, tur, deger, "
        "  para_birimi, gecerli_bas, gecerli_bit, gerekce, "
        "  veren_yonetici_id) "
        "VALUES (%s,%s,%s,%s,%s,coalesce(%s::date, CURRENT_DATE),"
        "        %s::date,%s,%s) RETURNING iskonto_id",
        (int(firma_id), paket_anahtar, tur, d, para_birimi,
         gecerli_bas, gecerli_bit, gerekce or None, yonetici_id))
    return int(iid), ""


def iskonto_iptal(iskonto_id: int) -> tuple[bool, str]:
    if not db.tek("SELECT 1 FROM iskontolar WHERE iskonto_id = %s",
                  (int(iskonto_id),)):
        return False, "İskonto bulunamadı"
    db.calistir("UPDATE iskontolar SET durum = 'iptal' "
                "WHERE iskonto_id = %s", (int(iskonto_id),))
    return True, ""


def iskonto_listesi(firma_id: int | None = None) -> list[dict]:
    if firma_id:
        return db.sorgu(
            "SELECT i.*, f.kisa_ad AS firma_kisa_ad FROM iskontolar i "
            "LEFT JOIN firmalar f ON f.firma_id = i.firma_id "
            "WHERE i.firma_id = %s ORDER BY i.olusma_ts DESC",
            (int(firma_id),))
    return db.sorgu(
        "SELECT i.*, f.kisa_ad AS firma_kisa_ad FROM iskontolar i "
        "LEFT JOIN firmalar f ON f.firma_id = i.firma_id "
        "ORDER BY i.olusma_ts DESC LIMIT 500")
