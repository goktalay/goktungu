#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v2.4.41 KALKIS KONTROL LISTESI - GERCEK KAYIT TESTI
====================================================
Statik denetim "kod var mi" der. Bu test "kayit GERCEKTEN yaziliyor
mu, pilot/tarih damgasi DOGRU mu, madde madde cevaplar OKUNABILIYOR
mu" sorularini gercek SQLite veritabani uzerinde olcer.

Kullanicinin istegi birebir buydu:
  "Pilot TAKEOFF'u tamamla dugmesine basarsa mutlaka tarih, saat ve
   pilot ile kayit altina alsin. Hangi sorulara ne cevap verdi
   kaydetsin."

Bu yuzden test edilen sey ekran degil, DENETIM IZI (audit trail).

Kullanim:  cd /home/ubuntu/goktungu_244/goktungu && python3 test_2441_kalkis.py
"""
import os
import sys
import time
import datetime

KOK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KOK)

GECTI = []
KALDI = []


def re_ara(s):
    import re as _re
    return _re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", str(s or ""))


def kaydet(ad, kosul, ek=""):
    if kosul:
        GECTI.append(ad)
        print(f"[GECTI     ] {ad}" + (f"  ({ek})" if ek else ""))
    else:
        KALDI.append((ad, ek))
        print(f"[BASARISIZ ] {ad}" + (f"  ({ek})" if ek else ""))


def main():
    from goktungu import veritabani as vt

    print("=" * 62)
    print("v2.4.41 KALKIS KONTROL LISTESI - GERCEK KAYIT TESTI")
    print("=" * 62)

    # ---------- 1. Sema gercekten olustu mu ----------
    vt.tablolari_olustur()
    with vt.baglanti() as db:
        cur = db.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tablolar = {r[0] for r in cur.fetchall()}
    kaydet("kalkis_kontrolleri tablosu OLUSTU",
           "kalkis_kontrolleri" in tablolar)
    kaydet("kalkis_kontrol_maddeleri tablosu OLUSTU",
           "kalkis_kontrol_maddeleri" in tablolar)

    # Kolonlar gercekten var mi (pilot + zaman damgasi zorunlu)
    with vt.baglanti() as db:
        cur = db.cursor()
        cur.execute("PRAGMA table_info(kalkis_kontrolleri)")
        kol = {r[1] for r in cur.fetchall()}
    for gerekli in ("ts", "yerel_saat", "pilot_eposta", "pilot_isim",
                    "sysid", "dron_id", "hedef_irtifa", "tam_onay",
                    "takeoff_gonderildi", "takeoff_hata"):
        kaydet(f"kalkis_kontrolleri.{gerekli} kolonu var", gerekli in kol)

    with vt.baglanti() as db:
        cur = db.cursor()
        cur.execute("PRAGMA table_info(kalkis_kontrol_maddeleri)")
        mkol = {r[1] for r in cur.fetchall()}
    for gerekli in ("kontrol_id", "sira", "anahtar", "soru", "cevap"):
        kaydet(f"kalkis_kontrol_maddeleri.{gerekli} kolonu var",
               gerekli in mkol)

    # ---------- 2. Gercek kayit yaz ----------
    TEST_SYSID = 9941
    maddeler = [
        {"sira": 0, "anahtar": "pervane_yon", "grup": "arac",
         "soru": "Pervane yonleri ve sikiligi kontrol edildi mi?",
         "cevap": True, "zorunlu": True, "kaynak": "tip"},
        {"sira": 1, "anahtar": "servo_kontrol", "grup": "arac",
         "soru": "Servolar ve kumanda yuzeyleri kontrol edildi mi?",
         "cevap": True, "zorunlu": True, "kaynak": "tip"},
        {"sira": 2, "anahtar": "alan_guvenli", "grup": "saha",
         "soru": "Kalkis alani insanlardan temiz mi?",
         "cevap": False, "zorunlu": False, "kaynak": "genel"},
    ]
    once = time.time()
    kid = vt.kalkis_kontrol_kaydet(
        TEST_SYSID, maddeler,
        pilot_eposta="test@gokkubbetech.com",
        pilot_isim="Test Pilot",
        hedef_irtifa=15.0,
        arac_tipi=2, arac_tipi_ad="Multirotor",
    )
    sonra = time.time()
    kaydet("kayit yazildi ve id dondu", bool(kid), f"id={kid}")

    # ---------- 3. Kayit geri okunabiliyor mu ----------
    kayitlar = vt.kalkis_kontrol_listele(sysid=TEST_SYSID, limit=5,
                                        maddeler=True)
    kaydet("kayit geri okunabiliyor", len(kayitlar) >= 1,
           f"{len(kayitlar)} kayit")
    k = kayitlar[0] if kayitlar else {}

    kaydet("PILOT e-postasi kayitta dogru",
           k.get("pilot_eposta") == "test@gokkubbetech.com",
           str(k.get("pilot_eposta")))
    kaydet("PILOT adi kayitta dogru",
           k.get("pilot_isim") == "Test Pilot", str(k.get("pilot_isim")))
    kaydet("hedef irtifa kayitta dogru",
           abs(float(k.get("hedef_irtifa") or 0) - 15.0) < 0.01,
           str(k.get("hedef_irtifa")))
    kaydet("arac tipi adi kayitta",
           k.get("arac_tipi_ad") == "Multirotor",
           str(k.get("arac_tipi_ad")))
    # tam_onay: zorunlularin HEPSI evet -> 1. Ucuncu madde zorunlu
    # DEGIL ve HAYIR; yine de tam onay saymali.
    kaydet("tam_onay zorunlu maddelere gore hesaplandi",
           int(k.get("tam_onay") or 0) == 1,
           "zorunlu 2/2 evet, opsiyonel madde hayir")
    kaydet("madde ve evet sayilari kayitta",
           int(k.get("madde_sayisi") or 0) == 3
           and int(k.get("evet_sayisi") or 0) == 2,
           f"madde={k.get('madde_sayisi')} evet={k.get('evet_sayisi')}")
    # yerel_saat insan okunur damga (pilot imzali ciktida gorunur)
    kaydet("yerel saat damgasi yazildi",
           bool(re_ara(k.get("yerel_saat"))), str(k.get("yerel_saat")))

    # Zaman damgasi: SUNUCU saatiyle ve testin calistigi araliga dusmeli
    ts = k.get("ts")
    ts_ok = False
    ts_ek = str(ts)
    try:
        if isinstance(ts, (int, float)):
            ts_ok = (once - 5) <= float(ts) <= (sonra + 5)
        else:
            # ISO metin ise ayristir
            d = datetime.datetime.fromisoformat(str(ts).replace("Z", ""))
            fark = abs(d.timestamp() - once)
            ts_ok = fark < 120
            ts_ek = f"{ts} (fark {fark:.0f}s)"
    except Exception as e:
        ts_ek = f"{ts} / {e}"
    kaydet("TARIH-SAAT damgasi kayit anini gosteriyor", ts_ok, ts_ek)

    # ---------- 4. Madde madde cevaplar ----------
    mad = k.get("maddeler") or []
    kaydet("maddeler kayitla birlikte okunuyor", len(mad) == 3,
           f"{len(mad)} madde")

    sozluk = {m.get("anahtar"): m for m in mad}
    kaydet("EVET cevabi EVET olarak saklandi",
           "pervane_yon" in sozluk
           and bool(sozluk["pervane_yon"].get("cevap")) is True)
    kaydet("HAYIR cevabi HAYIR olarak saklandi",
           "alan_guvenli" in sozluk
           and bool(sozluk["alan_guvenli"].get("cevap")) is False,
           "cevaplar karismamali")
    kaydet("zorunlu/opsiyonel ayrimi kayitta korundu",
           "pervane_yon" in sozluk and "alan_guvenli" in sozluk
           and int(sozluk["pervane_yon"].get("zorunlu", 0)) == 1
           and int(sozluk["alan_guvenli"].get("zorunlu", 1)) == 0)
    kaydet("madde KAYNAGI (tip/param/genel) kayitta",
           "pervane_yon" in sozluk
           and sozluk["pervane_yon"].get("kaynak") == "tip",
           "hangi maddenin nereden geldigi denetimde onemli")
    kaydet("SORU METNI saklandi (sonradan soru degisse bile iz kalir)",
           "Pervane" in str(sozluk.get("pervane_yon", {}).get("soru", "")))
    kaydet("madde sirasi korundu",
           [m.get("sira") for m in mad] == [0, 1, 2],
           str([m.get("sira") for m in mad]))

    # ---------- 5. Takeoff sonucu isaretlenebiliyor ----------
    vt.kalkis_kontrol_takeoff_isaretle(kid, True, "")
    k2 = vt.kalkis_kontrol_listele(sysid=TEST_SYSID, limit=1)[0]
    kaydet("takeoff gonderildi bayragi yazildi",
           bool(k2.get("takeoff_gonderildi")) is True)
    # Ucus raporunda kullanilan aralik sorgusu da gercekten donmeli
    if k.get("dron_id") is None:
        kaydet("aralik sorgusu dron_id olmadan bos doner (guvenli)",
               vt.kalkis_kontrol_araligi(None, once - 60, sonra + 60) == [],
               "dron kaydi olmayan sysid icin rapor bolumu bos kalir")

    kid2 = vt.kalkis_kontrol_kaydet(
        TEST_SYSID, maddeler[:1], pilot_eposta="t2@x.com",
        pilot_isim="P2", hedef_irtifa=8.0,
        arac_tipi=1, arac_tipi_ad="Sabit Kanat")
    vt.kalkis_kontrol_takeoff_isaretle(kid2, False, "MAVLink cevap yok")
    k3 = [r for r in vt.kalkis_kontrol_listele(sysid=TEST_SYSID, limit=5)
          if r.get("id") == kid2]
    kaydet("BASARISIZ takeoff da kayitta kaliyor (hata sebebiyle)",
           bool(k3) and bool(k3[0].get("takeoff_gonderildi")) is False
           and "MAVLink" in str(k3[0].get("takeoff_hata") or ""),
           "kalkmadiysa bile denetim izi silinmez")

    # ---------- 6. CASCADE: kayit silinirse maddeler de gider ----------
    with vt.baglanti() as db:
        cur = db.cursor()
        cur.execute("PRAGMA foreign_keys")
        fk_acik = cur.fetchone()[0]
        cur.execute("DELETE FROM kalkis_kontrolleri WHERE id=?", (kid2,))
        db.commit()
        cur.execute("SELECT COUNT(*) FROM kalkis_kontrol_maddeleri"
                    " WHERE kontrol_id=?", (kid2,))
        kalan = cur.fetchone()[0]
    kaydet("foreign_keys PRAGMA acik", bool(fk_acik), str(fk_acik))
    kaydet("kayit silinince maddeleri de silindi (CASCADE)", kalan == 0,
           f"{kalan} yetim madde")

    # ---------- 7. Temizlik ----------
    with vt.baglanti() as db:
        cur = db.cursor()
        cur.execute("DELETE FROM kalkis_kontrolleri WHERE sysid=?",
                    (TEST_SYSID,))
        db.commit()
        cur.execute("SELECT COUNT(*) FROM kalkis_kontrolleri WHERE sysid=?",
                    (TEST_SYSID,))
        kalan2 = cur.fetchone()[0]
    kaydet("test kayitlari temizlendi", kalan2 == 0)

    print("=" * 62)
    print(f"SONUC: {len(GECTI)}/{len(GECTI) + len(KALDI)} gecti")
    if KALDI:
        print("BASARISIZ:")
        for ad, ek in KALDI:
            print(f"  - {ad}" + (f"  ({ek})" if ek else ""))
    print("=" * 62)
    return 0 if not KALDI else 1


if __name__ == "__main__":
    sys.exit(main())
