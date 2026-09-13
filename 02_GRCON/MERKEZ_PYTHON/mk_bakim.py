"""GÖKTUNGU MERKEZ — bakım kapısı ve ödeme yaşam döngüsü.

BAKIM KAPISI — DEĞİŞTİRİLEMEZ İLKE
----------------------------------
Brifing:
> Bakımı biten kurum ÇALIŞMAYA DEVAM EDER — sistem asla kilitlenmez.
> Yalnız yeni sürüm, yeni özellik ve güvenlik yaması alamaz. Savunma
> müşterisinde uzaktan devre dışı bırakma kabul edilemez.

Bu modül bu ilkeyi zorunlu kılar. `bakim_durumu()` yalnız GÜNCELLEME
hakkını değerlendirir; hiçbir koşulda çalışma zamanı yetkisini
kısıtlamaz. Yetki kısıtlaması YALNIZ abonelik ödemesizliğinden doğar ve
o da salt-okunur kipe düşürür — veri SİLMEZ.

ÖDEMESİZLİK AKIŞI (brifing)
---------------------------
3 başarısız deneme + 7 gün ödemesiz dönem → koltuklar salt-okunur kipe
düşer, veri silinmez.

Durum makinesi:
    ACTIVE
      ├─ ödeme başarısız → odeme_deneme += 1
      ├─ deneme < 3 → yeniden dene (iyzico kendisi de dener)
      └─ deneme >= 3 → odemesiz_bitis = bugün + 7
             ├─ bugün <= odemesiz_bitis → hâlâ tam yetkili (uyarı gösterilir)
             └─ bugün > odemesiz_bitis → salt_okunur = TRUE
    Ödeme gelirse → odeme_deneme = 0, odemesiz_bitis = NULL,
                    salt_okunur = FALSE (tam geri dönüş)
"""
from __future__ import annotations

import datetime as _dt
from typing import Any

import mk_db as db

# Ödemesiz dönem (gün) — brifing: 7
ODEMESIZ_GUN = 7

# Başarısız deneme üst sınırı — brifing: 3
DENEME_SINIRI = 3

# Bakım yenileme uyarı eşikleri (gün) — brifing: 60 ve 30
UYARI_ESIKLERI = (60, 30)


def _bugun() -> _dt.date:
    return _dt.date.today()


# ---------------------------------------------------------------------------
# Bakım kapısı
# ---------------------------------------------------------------------------
def bakim_durumu(firma_id: int) -> dict[str, Any]:
    """Firmanın bakım kapsamı durumu.

    DÖNÜŞ SÖZLEŞMESİ
    ----------------
    `guncelleme_hakki`  — yeni sürüm/yama alabilir mi?
    `calisma_hakki`     — DAİMA True. Bakım bitişi çalışmayı ETKİLEMEZ.
                          Alan bilinçli olarak vardır: çağıran yerin
                          "bakım bitti → kapat" diye yanlış çıkarım
                          yapmasını önler.
    `kalan_gun`         — negatifse bakım bitmiş
    `uyari`             — 60/30 gün eşiği aşıldıysa uyarı metni anahtarı
    """
    f = db.tek(
        "SELECT firma_id, kisa_ad, bakim_bitis, paket_anahtar, "
        "       merkez_lisans, sinirsiz "
        "FROM firmalar WHERE firma_id = %s", (int(firma_id),))
    if not f:
        return {"var": False, "guncelleme_hakki": False,
                "calisma_hakki": True, "kalan_gun": None, "uyari": None}

    bitis = f["bakim_bitis"]
    if not bitis:
        # Bakım kapsamı tanımsız. SaaS aboneleri için bakım kavramı
        # yoktur (abonelik zaten sürekli güncelleme içerir); kapalı
        # devre lisansı olmayan kiracı güncelleme alabilir.
        return {"var": False, "guncelleme_hakki": True,
                "calisma_hakki": True, "kalan_gun": None, "uyari": None,
                "bakim_bitis": None}

    if isinstance(bitis, str):
        bitis = _dt.date.fromisoformat(bitis)
    kalan = (bitis - _bugun()).days
    uyari = None
    if kalan < 0:
        uyari = "bakim.bitti"
    else:
        for esik in sorted(UYARI_ESIKLERI):
            if kalan <= esik:
                uyari = "bakim.uyari%d" % esik
                break

    return {
        "var": True,
        "bakim_bitis": bitis.isoformat(),
        "kalan_gun": kalan,
        # Bakımı biten kurum güncelleme ALAMAZ...
        "guncelleme_hakki": kalan >= 0,
        # ...ama ÇALIŞMAYA DEVAM EDER. Bu değer asla False olmaz.
        "calisma_hakki": True,
        "uyari": uyari,
    }


def guncelleme_alabilir_mi(firma_id: int) -> tuple[bool, str]:
    """Güncelleme sunucusunun sorduğu soru.

    Bakım kapsamı bitmişse yeni sürüm verilmez ancak kurulu sürüm
    çalışmaya devam eder.
    """
    d = bakim_durumu(firma_id)
    if d["guncelleme_hakki"]:
        return True, ""
    return False, ("Bakım kapsamı %s tarihinde sona erdi. Kurulu sürüm "
                   "çalışmaya devam eder; yeni sürüm için bakım "
                   "yenilenmelidir." % d.get("bakim_bitis"))


def bakim_yenile(firma_id: int, yil: int = 1,
                 yonetici_id: int | None = None) -> tuple[bool, str]:
    """Bakım kapsamını uzatır.

    Bitiş tarihi GEÇMİŞTE ise bugünden, GELECEKTE ise mevcut bitişten
    uzatılır. Aksi halde erken yenileyen müşteri hak kaybeder.
    """
    f = db.tek("SELECT bakim_bitis FROM firmalar WHERE firma_id = %s",
               (int(firma_id),))
    if not f:
        return False, "Firma bulunamadı"
    mevcut = f["bakim_bitis"]
    if isinstance(mevcut, str):
        mevcut = _dt.date.fromisoformat(mevcut)
    taban = mevcut if (mevcut and mevcut > _bugun()) else _bugun()
    yeni = taban.replace(year=taban.year + max(1, int(yil)))
    db.calistir("UPDATE firmalar SET bakim_bitis = %s, guncel_ts = now() "
                "WHERE firma_id = %s", (yeni, int(firma_id)))
    db.calistir(
        "UPDATE merkez_lisanslari SET bakim_bitis = %s "
        "WHERE firma_id = %s AND iptal_ts IS NULL",
        (yeni, int(firma_id)))
    return True, yeni.isoformat()


def bakim_uyari_listesi() -> list[dict]:
    """Bakımı 60 gün içinde bitecek veya bitmiş kiracılar.

    Panel uyarısı ve e-posta hatırlatması bu listeden beslenir.
    """
    return db.sorgu(
        "SELECT firma_id, kisa_ad, unvan, bakim_bitis, paket_anahtar, "
        "       (bakim_bitis - CURRENT_DATE) AS kalan_gun "
        "FROM firmalar "
        "WHERE bakim_bitis IS NOT NULL "
        "  AND bakim_bitis <= CURRENT_DATE + INTERVAL '60 days' "
        "ORDER BY bakim_bitis")


# ---------------------------------------------------------------------------
# Ödeme yaşam döngüsü
# ---------------------------------------------------------------------------
def odeme_basarisiz(firma_id: int, sebep: str = "") -> dict[str, Any]:
    """Başarısız ödeme bildirimini işler.

    3. denemeden sonra ödemesiz dönem başlatılır. Ödemesiz dönem
    boyunca kiracı TAM YETKİLİDİR — yalnız uyarı gösterilir. Dönem
    biterse salt-okunur kipe düşer.
    """
    f = db.tek("SELECT odeme_deneme, odemesiz_bitis, salt_okunur "
               "FROM firmalar WHERE firma_id = %s", (int(firma_id),))
    if not f:
        return {"tamam": False, "hata": "Firma bulunamadı"}

    deneme = int(f["odeme_deneme"] or 0) + 1
    if deneme < DENEME_SINIRI:
        db.calistir(
            "UPDATE firmalar SET odeme_deneme = %s, guncel_ts = now() "
            "WHERE firma_id = %s", (deneme, int(firma_id)))
        return {"tamam": True, "deneme": deneme, "odemesiz": False,
                "salt_okunur": False}

    # Üçüncü deneme: ödemesiz dönem başlat (varsa uzatılmaz).
    bitis = f["odemesiz_bitis"]
    if not bitis:
        bitis = _bugun() + _dt.timedelta(days=ODEMESIZ_GUN)
        db.calistir(
            "UPDATE firmalar SET odeme_deneme = %s, odemesiz_bitis = %s, "
            "  guncel_ts = now() WHERE firma_id = %s",
            (deneme, bitis, int(firma_id)))
    else:
        db.calistir(
            "UPDATE firmalar SET odeme_deneme = %s, guncel_ts = now() "
            "WHERE firma_id = %s", (deneme, int(firma_id)))
    return {"tamam": True, "deneme": deneme, "odemesiz": True,
            "odemesiz_bitis": (bitis.isoformat()
                               if hasattr(bitis, "isoformat") else bitis),
            "salt_okunur": False}


def odeme_basarili(firma_id: int) -> None:
    """Ödeme alındı — tüm ödemesizlik izleri temizlenir.

    Salt-okunur kip de kaldırılır: müşteri borcunu ödediğinde tam
    yetkiye DERHAL dönmelidir.
    """
    db.calistir(
        "UPDATE firmalar SET odeme_deneme = 0, odemesiz_bitis = NULL, "
        "  salt_okunur = FALSE, guncel_ts = now() WHERE firma_id = %s",
        (int(firma_id),))


def odemesiz_donem_tara() -> list[dict]:
    """Ödemesiz dönemi bitmiş kiracıları salt-okunur kipe düşürür.

    Zamanlanmış görev olarak günde bir çalıştırılır.

    VERİ SİLİNMEZ. Yalnız `salt_okunur` bayrağı açılır; uçuş kayıtları,
    telemetri, kullanıcılar ve videolar OLDUĞU GİBİ KALIR.
    """
    dusenler = db.sorgu(
        "SELECT firma_id, kisa_ad, odemesiz_bitis FROM firmalar "
        "WHERE odemesiz_bitis IS NOT NULL "
        "  AND odemesiz_bitis < CURRENT_DATE "
        "  AND salt_okunur = FALSE")
    for f in dusenler:
        db.calistir(
            "UPDATE firmalar SET salt_okunur = TRUE, guncel_ts = now() "
            "WHERE firma_id = %s", (int(f["firma_id"]),))
    return dusenler


def odeme_durumu(firma_id: int) -> dict[str, Any]:
    """Kiracının ödeme durumu özeti (panel uyarısı için)."""
    f = db.tek(
        "SELECT odeme_deneme, odemesiz_bitis, salt_okunur, "
        "       abonelik, abonelik_bitis, iyz_abonelik_ref "
        "FROM firmalar WHERE firma_id = %s", (int(firma_id),))
    if not f:
        return {}
    ob = f["odemesiz_bitis"]
    if isinstance(ob, str):
        ob = _dt.date.fromisoformat(ob)
    return {
        "deneme": int(f["odeme_deneme"] or 0),
        "odemesiz_bitis": ob.isoformat() if ob else None,
        "odemesiz_kalan_gun": ((ob - _bugun()).days if ob else None),
        "salt_okunur": bool(f["salt_okunur"]),
        "abonelik": f["abonelik"],
        "abonelik_bitis": f["abonelik_bitis"],
        "abonelik_ref": f["iyz_abonelik_ref"],
        # Uyarı anahtarı — arayüz i18n ile çözer
        "uyari": ("odeme.salt_okunur" if f["salt_okunur"]
                  else ("odeme.odemesiz" if ob else None)),
    }
