#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.4.51: PostgreSQL ag gecidi katmanini GERCEK PG uzerinde olcer.

Amac: sarmalayicinin sqlite3 semantigini birebir sagladigini kanitlamak.
Olculen bes uyusmazlik: ? -> %s, AUTOINCREMENT, lastrowid,
INSERT OR REPLACE/IGNORE, PRAGMA.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "goktungu"))

from goktungu import pg          # noqa: E402

GECTI = 0
KALDI = 0


def olc(ad, kosul, ayrinti=""):
    global GECTI, KALDI
    if kosul:
        GECTI += 1
        print(f"  [GECTI] {ad}")
    else:
        KALDI += 1
        print(f"  [KALDI] {ad}" + (f" -> {ayrinti}" if ayrinti else ""))


print("=" * 62)
print("v2.4.51 PG AG GECIDI OLCUMU")
print("=" * 62)

# ------------------------------------------------------------------
print("\n[1] Modul ve surucu")
olc("psycopg2 kurulu", pg.VAR)
olc("yapilandirma baslangicta yok", not pg.yapilandirma_var())

# ------------------------------------------------------------------
print("\n[2] Yer tutucu cevirisi (tirnak farkindalikli)")
c = pg._yer_tutucu_cevir
olc("basit ? -> %s", c("SELECT * FROM t WHERE a=?") ==
    "SELECT * FROM t WHERE a=%s",
    c("SELECT * FROM t WHERE a=?"))
olc("coklu ?", c("INSERT INTO t (a,b) VALUES (?,?)") ==
    "INSERT INTO t (a,b) VALUES (%s,%s)")
olc("tirnak icindeki ? KORUNUR", c("SELECT '?' FROM t WHERE a=?") ==
    "SELECT '?' FROM t WHERE a=%s",
    c("SELECT '?' FROM t WHERE a=?"))
olc("literal % kacirilir", c("SELECT * FROM t WHERE a LIKE '%x%'") ==
    "SELECT * FROM t WHERE a LIKE '%%x%%'",
    c("SELECT * FROM t WHERE a LIKE '%x%'"))

# ------------------------------------------------------------------
print("\n[3] Sema cevirisi")
s = pg.sema_cevir
olc("AUTOINCREMENT -> BIGSERIAL",
    "BIGSERIAL PRIMARY KEY" in s(
        "CREATE TABLE t (id INTEGER PRIMARY KEY AUTOINCREMENT)"))
olc("INTEGER PRIMARY KEY -> BIGSERIAL",
    "BIGSERIAL PRIMARY KEY" in s("CREATE TABLE t (id INTEGER PRIMARY KEY)"))
olc("REAL -> DOUBLE PRECISION",
    "DOUBLE PRECISION" in s("CREATE TABLE t (x REAL)"))
olc("BLOB -> BYTEA", "BYTEA" in s("CREATE TABLE t (v BLOB)"))
olc("WITHOUT ROWID kaldirilir",
    "WITHOUT ROWID" not in s("CREATE TABLE t (a int) WITHOUT ROWID"))

# ------------------------------------------------------------------
print("\n[4] Catisma cevirisi")
cc = pg._catisma_cevir
r = cc("INSERT OR IGNORE INTO roller (ad) VALUES (?)", pg.CATISMA)
olc("OR IGNORE -> ON CONFLICT DO NOTHING",
    "ON CONFLICT DO NOTHING" in r and "OR IGNORE" not in r, r)
r = cc("INSERT OR REPLACE INTO ayarlar (anahtar,deger) VALUES (?,?)",
       pg.CATISMA)
olc("OR REPLACE -> ON CONFLICT DO UPDATE",
    "ON CONFLICT (anahtar) DO UPDATE SET deger=EXCLUDED.deger" in r, r)
try:
    cc("INSERT OR REPLACE INTO bilinmeyen (a) VALUES (?)", pg.CATISMA)
    olc("tanimsiz tablo icin ACIK hata", False, "hata verilmedi")
except ValueError:
    olc("tanimsiz tablo icin ACIK hata", True)

# ------------------------------------------------------------------
print("\n[5] Gercek PG baglantisi")
BILGI = dict(host="127.0.0.1", port=5432, veritabani="goktungu",
             kullanici="goktungu", sifre="goktungu2451")
d = pg.dene(**BILGI)
olc("dene() tamam", d["tamam"], d["hata"])
olc("surum okundu", bool(d["surum"]), d["surum"])
olc("surum >= 12", d["surum_no"] >= 120000, str(d["surum_no"]))
olc("CREATE TABLE yetkisi", d["yetki_tablo"], d["hata"])
d2 = pg.dene(host="127.0.0.1", port=5432, veritabani="yok_boyle_bir_db",
             kullanici="goktungu", sifre="goktungu2451")
olc("olmayan DB tespit edilir", not d2["tamam"] and not d2["veritabani_var"],
    d2["hata"][:60])
d3 = pg.dene(host="127.0.0.1", port=5432, veritabani="goktungu",
             kullanici="goktungu", sifre="yanlis_sifre")
olc("yanlis sifre tespit edilir", not d3["tamam"], d3["hata"][:60])

pg.yapilandir(**BILGI)
olc("yapilandirma kaydedildi", pg.yapilandirma_var())
olc("yapilandirma_oku sifreyi gizler",
    pg.yapilandirma_oku().get("password") == "***")

# ------------------------------------------------------------------
print("\n[6] Havuzlama (v2.4.24 fd sizintisi onlemi)")
con = pg.baglanti()
con2 = pg.baglanti()
olc("ayni is parcasi AYNI baglantiyi alir", con is con2)
olc("havuz 1 baglanti bildirir", pg.havuz_durumu()["acik"] == 1,
    str(pg.havuz_durumu()))

import threading                                       # noqa: E402
digerleri = []


def _isci():
    digerleri.append(pg.baglanti())
    pg.baglanti_kapat()


t = threading.Thread(target=_isci)
t.start()
t.join()
olc("baska is parcasi FARKLI baglanti alir",
    digerleri and digerleri[0] is not con)

# ------------------------------------------------------------------
print("\n[7] Sema olusturma ve lastrowid (KRITIK)")
with con as c:
    c.execute("DROP TABLE IF EXISTS dene_tel")
    c.execute("DROP TABLE IF EXISTS dene_ayar")
    c.executescript("""
        CREATE TABLE dene_tel (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            ad     TEXT NOT NULL DEFAULT '',
            deger  REAL,
            ham    BLOB
        );
    """)
    c.execute("CREATE TABLE dene_ayar (anahtar TEXT PRIMARY KEY,"
              " deger TEXT NOT NULL DEFAULT '')")

with con as c:
    cur = c.execute("INSERT INTO dene_tel (ad,deger) VALUES (?,?)",
                    ("bir", 1.5))
    id1 = cur.lastrowid
    cur = c.execute("INSERT INTO dene_tel (ad,deger) VALUES (?,?)",
                    ("iki", 2.5))
    id2 = cur.lastrowid

olc("lastrowid deger dondurur (None DEGIL)", id1 is not None, str(id1))
olc("lastrowid artan", id2 == id1 + 1, f"{id1} -> {id2}")

# ------------------------------------------------------------------
print("\n[8] Satir erisimi (sqlite3.Row taklidi)")
with con as c:
    s = c.execute("SELECT id, ad, deger FROM dene_tel WHERE ad=?",
                  ("bir",)).fetchone()
olc("satir bulundu", s is not None)
if s is not None:
    olc("ada gore erisim", s["ad"] == "bir", repr(s["ad"]))
    olc("indekse gore erisim", s[1] == "bir", repr(s[1]))
    olc("fetchone()[0] deseni", s[0] == id1, f"{s[0]} vs {id1}")
    olc("keys()", "ad" in s.keys(), str(s.keys()))
    olc("dict(zip(...)) uyumu", dict(zip(s.keys(), s))["ad"] == "bir")
    olc("in operatoru", "deger" in s)
    olc("get() varsayilan", s.get("yok", "vars") == "vars")

# ------------------------------------------------------------------
print("\n[9] INSERT OR REPLACE gercek davranis")
with con as c:
    c.execute("INSERT OR REPLACE INTO dene_ayar (anahtar,deger)"
              " VALUES (?,?)", ("tema", "koyu"))
    c.execute("INSERT OR REPLACE INTO dene_ayar (anahtar,deger)"
              " VALUES (?,?)", ("tema", "acik"))
    n = c.execute("SELECT count(*) FROM dene_ayar").fetchone()[0]
    v = c.execute("SELECT deger FROM dene_ayar WHERE anahtar=?",
                  ("tema",)).fetchone()[0]
olc("REPLACE tek satir birakir", n == 1, str(n))
olc("REPLACE degeri GUNCELLER", v == "acik", repr(v))

with con as c:
    c.execute("INSERT OR IGNORE INTO dene_ayar (anahtar,deger)"
              " VALUES (?,?)", ("tema", "yesil"))
    v2 = c.execute("SELECT deger FROM dene_ayar WHERE anahtar=?",
                   ("tema",)).fetchone()[0]
olc("IGNORE mevcut degeri KORUR", v2 == "acik", repr(v2))

# ------------------------------------------------------------------
print("\n[10] executemany (toplu telemetri yazimi)")
with con as c:
    c.executemany("INSERT INTO dene_tel (ad,deger) VALUES (?,?)",
                  [(f"k{i}", float(i)) for i in range(200)])
    n = c.execute("SELECT count(*) FROM dene_tel").fetchone()[0]
olc("executemany 200 satir yazdi", n == 202, str(n))

# ------------------------------------------------------------------
print("\n[11] Islem yonetimi (with blogu)")
try:
    with con as c:
        c.execute("INSERT INTO dene_ayar (anahtar,deger) VALUES (?,?)",
                  ("gecici", "x"))
        raise RuntimeError("bilincli hata")
except RuntimeError:
    pass
with con as c:
    n = c.execute("SELECT count(*) FROM dene_ayar WHERE anahtar=?",
                  ("gecici",)).fetchone()[0]
olc("istisna GERI SARAR", n == 0, str(n))
olc("baglanti istisnadan sonra KULLANILABILIR",
    con.execute("SELECT 1").fetchone()[0] == 1)

# ------------------------------------------------------------------
print("\n[12] BYTEA (harita karosu icin)")
with con as c:
    ham = bytes(range(256))
    c.execute("INSERT INTO dene_tel (ad,ham) VALUES (?,?)", ("ikili", ham))
    geri = c.execute("SELECT ham FROM dene_tel WHERE ad=?",
                     ("ikili",)).fetchone()[0]
olc("ikili veri bozulmadan doner", bytes(geri) == ham,
    f"{len(bytes(geri))} bayt")

# ------------------------------------------------------------------
print("\n[13] Olu baglanti kurtarma")
with con as c:
    try:
        c.execute("SELECT * FROM yok_boyle_tablo")
    except Exception:
        pass
con3 = pg.baglanti()
olc("hatali sorgudan sonra baglanti kurtarilir",
    con3.execute("SELECT 42").fetchone()[0] == 42)

# temizlik
with pg.baglanti() as c:
    c.execute("DROP TABLE IF EXISTS dene_tel")
    c.execute("DROP TABLE IF EXISTS dene_ayar")
pg.tum_baglantilari_kapat()
olc("tum_baglantilari_kapat havuzu bosaltir",
    pg.havuz_durumu()["acik"] == 0, str(pg.havuz_durumu()))

print("\n" + "=" * 62)
print(f"SONUC: {GECTI} gecti, {KALDI} kaldi")
print("=" * 62)
sys.exit(1 if KALDI else 0)
