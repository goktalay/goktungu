#!/usr/bin/env python3
"""v2.4.51 — Veri okuma/yazma yollarini GERCEK PostgreSQL uzerinde olcer.

`dene_pg_gecit.py` ag gecidi katmanini olcer (44/0). Bu betik bir ust
katmani olcer: `veritabani.py` icindeki GERCEK is fonksiyonlari PG
kipinde dogru calisiyor mu.

Neden gerekli: ag gecidi tek basina yeterli DEGIL. Ornegin
`kullanici_ekle()` icinde `INSERT OR REPLACE` + `lastrowid` + citext
birlikte kullanilir; her biri ayri ayri gecse de BIRLIKTE calismalari
olculmelidir.
"""
import os
import sys
import time

KOK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(KOK, "goktungu"))

from goktungu import pg                                    # noqa: E402
from goktungu import veritabani as vt                      # noqa: E402

G = K = 0
BASARISIZ = []


def olc(ad, kosul, detay=""):
    global G, K
    if kosul:
        G += 1
        print(f"  [GECTI] {ad}")
    else:
        K += 1
        BASARISIZ.append(ad)
        print(f"  [KALDI] {ad}" + (f" -> {detay}" if detay else ""))


def bolum(ad):
    print(f"\n=== {ad} ===")


pg.yapilandir(host="127.0.0.1", port=5432, veritabani="goktungu",
              kullanici="goktungu", sifre="goktungu2451")

# Temiz baslangic
con = pg.baglanti()
with con as c:
    c.execute("DROP SCHEMA public CASCADE")
    c.execute("CREATE SCHEMA public")
pg._CITEXT_VAR = None
pg.citext_kur()
vt.tablolari_olustur()

bolum("kip ve sema")
olc("KIP postgresql", vt.KIP == "postgresql", vt.KIP)
olc("pg_kipinde() True", vt.pg_kipinde())
with pg.baglanti() as c:
    n = c.execute(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema='public' AND table_type='BASE TABLE'"
    ).fetchone()[0]
olc("en az 27 tablo (v2.4.51: 31)", n >= 27, str(n))

bolum("kullanici yollari (citext + INSERT OR REPLACE)")
# Olculdu: sinif tabanli API (`Kullanicilar.ekle`), modul duzeyinde
# `kullanici_ekle` YOK.
try:
    from goktungu.kullanicilar import KullaniciYoneticisi
    kl = KullaniciYoneticisi()
    kurulum = True
    hata = ""
except Exception as e:
    kurulum = False
    hata = f"{type(e).__name__}: {e}"
olc("KullaniciYoneticisi() kurulur", kurulum, hata)

if kurulum:
    try:
        kayit, khata = kl.ekle("mkaderoglu@gokkubbetech.com",
                               ad_soyad="Muhammed Kaderoglu",
                               rol="yonetici", sifre="gokkubbe2026")
        olc("kl.ekle calisir", kayit is not None, str(khata))
    except Exception as e:
        olc("kl.ekle calisir", False, f"{type(e).__name__}: {e}")

    k = kl.bul("mkaderoglu@gokkubbetech.com")
    olc("kl.bul bulur", k is not None)
    if k:
        olc("ad_soyad dogru", k.get("ad_soyad") == "Muhammed Kaderoglu",
            str(k.get("ad_soyad")))
        olc("rol yonetici", k.get("rol") == "yonetici", str(k.get("rol")))

    # citext: BUYUK harfle de bulmali
    kb = kl.bul("MKADEROGLU@GOKKUBBETECH.COM")
    olc("BUYUK harfle de bulur (citext)", kb is not None)

    try:
        dogru = kl.dogrula("mkaderoglu@gokkubbetech.com", "gokkubbe2026")
        yanlis = kl.dogrula("mkaderoglu@gokkubbetech.com", "yanlis")
        olc("dogru sifre kabul", bool(dogru), str(dogru))
        olc("yanlis sifre RED", not yanlis, str(yanlis))
    except Exception as e:
        olc("kl.dogrula calisir", False, f"{type(e).__name__}: {e}")

    # Ilk yonetici guvencesi PG'de de calismali
    try:
        liste = kl.listesi_guvenli()
        olc("listesi_guvenli liste doner", isinstance(liste, list),
            str(type(liste)))
    except Exception as e:
        olc("listesi_guvenli", False, f"{type(e).__name__}: {e}")

bolum("ayar yollari (INSERT OR REPLACE)")
try:
    from goktungu.ayarlar import AyarYoneticisi
    ay = AyarYoneticisi(lambda *a, **k: None)
    ay.kaydet({"dene_anahtar": {"a": 1, "b": "iki"}})
    o = ay.yukle()
    olc("ayar kaydet+yukle", o.get("dene_anahtar", {}).get("b") == "iki",
        str(o.get("dene_anahtar")))
    ay.kaydet({"dene_anahtar": {"a": 2, "b": "uc"}})
    o2 = ay.yukle()
    olc("ayar UZERINE yazilir (REPLACE)",
        o2.get("dene_anahtar", {}).get("b") == "uc",
        str(o2.get("dene_anahtar")))
except Exception as e:
    import traceback
    olc("ayar yollari", False,
        f"{type(e).__name__}: {e} | {traceback.format_exc()[-250:]}")

bolum("dron kayit yollari (lastrowid)")
try:
    did, yeni = vt.dron_kayit_al_veya_olustur(
        "DENE-UID-001", isim="Dene Dron", sysid=7, renk="#ff0000")
    olc("dron_kayit_al_veya_olustur id doner",
        isinstance(did, int) and did > 0, str(did))
    olc("ilk cagri yeni=True", yeni is True, str(yeni))
    did2, yeni2 = vt.dron_kayit_al_veya_olustur("DENE-UID-001")
    olc("ikinci cagri AYNI id", did2 == did, f"{did} vs {did2}")
    olc("ikinci cagri yeni=False", yeni2 is False, str(yeni2))
except Exception as e:
    olc("dron kayit yollari", False, f"{type(e).__name__}: {e}")

bolum("telemetri yazma ve v_ucuslar gorunumu")
try:
    simdi = time.time()
    # Ucus tespiti icin yeterli ornek: armed=1, irtifa>esik
    satirlar = []
    for i in range(30):
        satirlar.append((did, None, simdi + i, 39.9 + i * 1e-5,
                         32.8, 50.0 + i, 12.0, 90.0, "GUIDED", 1,
                         "mkaderoglu@gokkubbetech.com", "Muhammed"))
    with pg.baglanti() as c:
        c.executemany(
            "INSERT INTO telemetri (dron_id, oturum_id, ts, lat, lon,"
            " irtifa, hiz, yaw, mod, armed, pilot_eposta, pilot_isim)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", satirlar)
    with pg.baglanti() as c:
        n = c.execute("SELECT count(*) FROM telemetri").fetchone()[0]
    olc("telemetri executemany 30 satir", n == 30, str(n))

    with pg.baglanti() as c:
        u = c.execute("SELECT * FROM v_ucuslar").fetchall()
    olc("v_ucuslar ucus tespit eder", len(u) >= 1, f"{len(u)} ucus")
    if u:
        r = u[0]
        olc("v_ucuslar.id bicimi YYYYMMDD_HHMMSS_D{sysid}",
            "_D7" in str(r["id"]) and len(str(r["id"]).split("_")[0]) == 8,
            str(r["id"]))
        olc("sure sayisal", r["sure"] is not None, str(r["sure"]))
        olc("max_irtifa dogru", abs(float(r["max_irtifa"]) - 79.0) < 0.5,
            str(r["max_irtifa"]))
        olc("nokta sayisi 30", int(r["nokta"]) == 30, str(r["nokta"]))
except Exception as e:
    import traceback
    olc("telemetri/v_ucuslar", False,
        f"{type(e).__name__}: {e} | {traceback.format_exc()[-300:]}")

bolum("sema guncelleme (PRAGMA table_info yolu)")
try:
    # tablolari_olustur idempotent olmali (ikinci cagri hata vermemeli)
    vt.tablolari_olustur()
    olc("tablolari_olustur idempotent", True)
except Exception as e:
    olc("tablolari_olustur idempotent", False, f"{type(e).__name__}: {e}")

bolum("havuz durumu")
d = vt.havuz_durumu()
olc("havuz_durumu kip bildirir", d.get("kip") == "postgresql", str(d))

print(f"\n{'=' * 52}")
print(f"SONUC: {G} gecti, {K} kaldi")
if BASARISIZ:
    print("\nBASARISIZ:")
    for b in BASARISIZ:
        print(f"  - {b}")
pg.tum_baglantilari_kapat()
sys.exit(1 if K else 0)
