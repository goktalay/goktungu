# -*- coding: utf-8 -*-
"""v2.4.51: PostgreSQL ag gecidi katmani.

AMAC
----
`veritabani.baglanti()` cagri yerlerinin (146 adet, 16 dosyada) HICBIRI
degismeden PostgreSQL uzerinde calissin. Bu modul `sqlite3` API'sini
taklit eden ince bir sarmalayici saglar.

NEDEN SARMALAYICI
-----------------
Olculdu (bkz. DURUM_2451.md):
  - `baglanti()` cagri yeri: 146
  - `?` yer tutucu: 256
  - `cur.lastrowid`: 11
  - `INSERT OR REPLACE/IGNORE`: 14
  - satir erisimi HEM sozluk HEM indeks (`fetchone()[0]` 14 yerde)

146 cagri yerini elle cevirmek hataya cok acik. Sarmalayici bu
uyusmazliklari TEK yerde cozer.

COZULEN BES UYUSMAZLIK
----------------------
| SQLite                              | PostgreSQL                  |
|-------------------------------------|-----------------------------|
| `?`                                 | `%s`                        |
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `BIGSERIAL PRIMARY KEY`     |
| `cur.lastrowid`                     | `RETURNING id` + fetch      |
| `INSERT OR REPLACE/IGNORE`          | `ON CONFLICT`               |
| `PRAGMA table_info`                 | `information_schema.columns`|

KRITIK: `lastrowid` psycopg2'de VARDIR ama SQLite anlaminda CALISMAZ —
`cursor.lastrowid` PG'de OID dondurur (tablo OID'siz ise None). Sessizce
None donmesi, yeni eklenen dron/rota kimliginin alinamamasina ve kaydin
kopuk kalmasina yol acar. Bu yuzden `Imlec.execute()` INSERT sorgularina
otomatik `RETURNING id` ekler ve `lastrowid` bunu dondurur.
"""
from __future__ import annotations

import re
import threading
import time
import weakref

try:
    import psycopg2
    import psycopg2.extras
    import psycopg2.extensions
    VAR = True
except ImportError:                                   # pragma: no cover
    psycopg2 = None
    VAR = False


# ------------------------------------------------------------------
# NUMERIC -> float (KRITIK, olculen vaka)
# ------------------------------------------------------------------
# SQLite `NUMERIC`/`REAL` kolonlarini Python `float` olarak dondururdu.
# psycopg2 ise PostgreSQL `numeric`/`decimal` icin `decimal.Decimal`
# dondurur. `Decimal` JSON'a YAZILAMAZ:
#     TypeError: Object of type Decimal is not JSON serializable
#
# Bu hata SESSIZ DEGIL ama GORUNMEZ: WS yanit yazimi patlar, arayuze
# hicbir sey gitmez, panel bos kalir. Olculen vaka: gercek ucus
# tamamlandi, `ucuslar` satiri veritabaninda VARDI, fakat
# `dron_gecmis_liste` yaniti (max_hiz/ort_hiz `numeric`) yazilamadigi
# icin ucus gecmisi bos gorundu.
#
# Neden burada, tek noktada:
#   - Her sorguya `::float` yazmak 100+ noktada hatirlanmayi gerektirir;
#     biri unutulunca ayni kusur baska panelde geri doner.
#   - JSON yazarken `default=float` koymak yalniz JSON yolunu korur;
#     Decimal'in aritmetikte `float` ile karismasi (`Decimal + float`
#     -> TypeError) sürer.
# Bu yuzden donusum SURUCU KATMANINDA yapilir: PG'den gelen her
# `numeric` degeri dogrudan `float` olur, SQLite davranisiyla ayni.
#
# `None` korunur (NULL -> None). Donusum basarisiz olursa deger metne
# dusurulur; veri kaybetmek yerine gorunur kalmasi yeglenir.
if VAR:
    def _numeric_float(deger, imlec):
        if deger is None:
            return None
        try:
            return float(deger)
        except (TypeError, ValueError):
            return deger

    # 1700 = numeric/decimal, 1231 = numeric[]
    _NUMERIC_FLOAT = psycopg2.extensions.new_type(
        (1700,), "NUMERIC_FLOAT", _numeric_float)
    psycopg2.extensions.register_type(_NUMERIC_FLOAT)
    try:
        psycopg2.extensions.register_type(
            psycopg2.extensions.new_array_type(
                (1231,), "NUMERIC_FLOAT_ARRAY", _NUMERIC_FLOAT))
    except Exception:                                 # pragma: no cover
        pass


# ------------------------------------------------------------------
# Yapilandirma (sihirbaz tarafindan doldurulur)
# ------------------------------------------------------------------
_yapilandirma: dict | None = None
_yerel = threading.local()
_havuz_kilit = threading.Lock()
_havuz_kayit: list = []

# Baglanti zaman asimi (sn). SQLite'in KILIT_ZAMAN_ASIMI=30 karsiligi.
BAGLANTI_ZAMAN_ASIMI = 10
# Deyim zaman asimi (ms). Kilitli bir sorgunun sonsuza kadar beklemesini
# onler; SQLite busy_timeout=30000 karsiligi.
DEYIM_ZAMAN_ASIMI_MS = 30000


def yapilandir(host, port, veritabani, kullanici, sifre, ssl="",
               diske_yaz=False):
    """PG baglanti bilgilerini kaydeder. Baglanti ACMAZ.

    `diske_yaz=True` ise bilgiler `veri/pg.json`'a 0600 izinle yazilir
    ve sonraki aciliste `dosyadan_yukle()` ile geri okunur.
    """
    global _yapilandirma
    _yapilandirma = {
        "host": str(host or "127.0.0.1"),
        "port": int(port or 5432),
        "dbname": str(veritabani or "goktungu"),
        "user": str(kullanici or "goktungu"),
        "password": str(sifre or ""),
        "sslmode": str(ssl) if ssl else "prefer",
    }
    if diske_yaz:
        _dosyaya_yaz(_yapilandirma)


# ------------------------------------------------------------------
# Kalici yapilandirma (v2.4.51)
# ------------------------------------------------------------------
# NEDEN DOSYA: PG baglanti bilgisi veritabaninin KENDISINE yazilamaz
# (tavuk-yumurta). `calisma.json` gibi bu da dosyada kalmak ZORUNDA.
#
# GUVENLIK: sifre duz metin yazilir ancak dosya izni 0600 (yalniz sahip).
# Sifrelemek ANLAMSIZ olurdu: cozme anahtari da ayni makinede durmak
# zorunda oldugu icin saldirganin isini yalnizca bir adim uzatir.
_PG_DOSYA_ADI = "pg.json"


def _pg_dosya_yolu() -> str:
    """`pg.json` icin tam yol.

    v2.4.52: klasor yapisi degisti; yol artik `sabitler._veri_yolu`
    uzerinden cozulur. ONCEDEN paketin bir ust dizinine `veri/`
    ekleniyordu; yeni yapida bu `assets/python/veri/pg.json` olurdu.
    Sonuc SESSIZ olurdu: dosya bulunamayinca `yapilandirildi()` False
    doner, sunucu sihirbazi YENIDEN acar ve kullanici kurulumu her
    acilista bastan yapmak zorunda kalir.

    `_veri_yolu` gecis kurali sayesinde v2.4.51 kurulumunun mevcut
    `veri/pg.json` dosyasi da bulunur (eski konum).
    """
    from .sabitler import _veri_alt_yolu
    return _veri_alt_yolu(_PG_DOSYA_ADI)


def _dosyaya_yaz(kayit: dict) -> None:
    import json
    import os
    yol = _pg_dosya_yolu()
    try:
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        gecici = yol + ".yeni"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump(kayit, f, ensure_ascii=False, indent=2)
        # Once izin, SONRA yerine tasi: acik pencerede okunmasin
        try:
            os.chmod(gecici, 0o600)
        except OSError:
            pass
        os.replace(gecici, yol)
    except OSError as e:
        print(f"[PG] Yapilandirma yazilamadi: {e}")


def dosyadan_yukle() -> bool:
    """`veri/pg.json` varsa yapilandirmayi yukler. Baglanti ACMAZ.

    Doner: True = yapilandirma yuklendi, False = dosya yok/bozuk.
    """
    global _yapilandirma
    import json
    import os
    yol = _pg_dosya_yolu()
    if not os.path.exists(yol):
        return False
    try:
        with open(yol, "r", encoding="utf-8") as f:
            k = json.load(f)
    except (OSError, ValueError) as e:
        print(f"[PG] Yapilandirma okunamadi: {e}")
        return False
    if not isinstance(k, dict) or not k.get("dbname"):
        return False
    _yapilandirma = {
        "host": str(k.get("host") or "127.0.0.1"),
        "port": int(k.get("port") or 5432),
        "dbname": str(k.get("dbname")),
        "user": str(k.get("user") or "goktungu"),
        "password": str(k.get("password") or ""),
        "sslmode": str(k.get("sslmode") or "prefer"),
    }
    return True


def dosya_var() -> bool:
    """Kalici yapilandirma dosyasi var mi (yuklemeden olcer)."""
    import os
    return os.path.exists(_pg_dosya_yolu())


def dosyayi_sil() -> None:
    """Kalici yapilandirmayi siler (sihirbazi yeniden actirmak icin)."""
    import os
    try:
        os.remove(_pg_dosya_yolu())
    except OSError:
        pass


def _hata_sadelestir(e) -> str:
    """psycopg2 hatasini kullanicinin anlayacagi tek satira indirger."""
    m = str(e).strip().replace("\n", " ")
    dusuk = m.lower()
    if "could not translate host name" in dusuk or "name or service not known" in dusuk:
        return "Sunucu adresi cozumlenemedi (IP/ad hatali)"
    if "connection refused" in dusuk:
        return "Baglanti reddedildi (PostgreSQL calismiyor veya port kapali)"
    if "timeout expired" in dusuk or "timed out" in dusuk:
        return "Baglanti zaman asimi (guvenlik duvari veya yanlis IP)"
    if "password authentication failed" in dusuk:
        return "Kullanici adi veya sifre hatali"
    if "does not exist" in dusuk and "database" in dusuk:
        return "Veritabani bulunamadi (once PostgreSQL'de olusturun)"
    if "no pg_hba.conf entry" in dusuk:
        return ("Sunucu bu adresten baglantiya izin vermiyor "
                "(pg_hba.conf duzenlenmeli)")
    return m[:300]


def yapilandirma_var() -> bool:
    return _yapilandirma is not None


def yapilandirma_oku() -> dict:
    """Sifresiz kopya dondurur (gunluge yazmak icin guvenli)."""
    if not _yapilandirma:
        return {}
    k = dict(_yapilandirma)
    k["password"] = "***" if k.get("password") else ""
    return k


def yapilandirmayi_sil():
    """Yapilandirmayi ve tum baglantilari temizler (sinav icin)."""
    global _yapilandirma
    tum_baglantilari_kapat()
    _yapilandirma = None


# ------------------------------------------------------------------
# SQL lehce cevirisi
# ------------------------------------------------------------------
# `?` -> `%s`. Tirnak icindeki `?` KORUNMALI (or. "SELECT '?'").
# Ayrica psycopg2 `%` isaretini bicimlendirme olarak yorumlar; SQL'de
# gecen literal `%` (LIKE '%x%') `%%` olarak kacirilmalidir.
_TIRNAK = re.compile(r"'(?:[^']|'')*'")

# PG yer tutucusu: `%s` veya `%(ad)s`. Bir sorguda `?` yoksa ama bu
# desen varsa sorgu ZATEN PG bicimindedir ve cevrilmemelidir.
_PG_YER_TUTUCU = re.compile(r"%(?:s|\([A-Za-z_][A-Za-z0-9_]*\)s)")

# `total_changes` yalnizca YAZMA deyimlerinde artmalidir. `rowcount`
# SELECT icin de deger dondurur; okuma islemleri sayaci sisirirse
# `telemetri_toplu_yaz()` "kac ornek aktarildi" bilgisini YANLIS
# bildirir.
_YAZMA_DEYIMI = re.compile(
    r"\s*(?:INSERT|UPDATE|DELETE|REPLACE)\b", re.IGNORECASE)


def _yer_tutucu_cevir(sql: str) -> str:
    """`?` -> `%s`, literal `%` -> `%%` (tirnak dışında).

    KRITIK (v2.4.51'de olculerek yakalandi): sorgu ZATEN `%s`
    kullaniyorsa bu islev onu `%%s` yapiyordu ve psycopg2 `%%`'yi
    literal `%` olarak cozup `s` diye bir KOLON ariyordu:

        DELETE FROM telemetri WHERE mod=%s
        -> UndefinedColumn: column "s" does not exist

    Kod tabaninda `?` kullanilir, ancak yeni yazilan kod veya sinav
    betikleri dogrudan `%s` yazabilir. Ikisi de calismali.

    Cozum: sorguda `?` yer tutucusu YOKSA ve `%s`/`%(ad)s` VARSA sorgu
    ZATEN PG bicimindedir; hicbir cevirme yapilmaz. Aksi halde `?`
    ceviriside yapilir ve literal `%` kacirilir.
    """
    # `?` yok ama PG yer tutucusu var -> sorgu zaten PG biciminde
    if "?" not in sql and _PG_YER_TUTUCU.search(sql):
        return sql

    parcalar = []
    son = 0
    for m in _TIRNAK.finditer(sql):
        parcalar.append((son, m.start(), False))
        parcalar.append((m.start(), m.end(), True))
        son = m.end()
    parcalar.append((son, len(sql), False))

    cikti = []
    for bas, bit, tirnakli in parcalar:
        p = sql[bas:bit]
        if tirnakli:
            # Tirnak icindeki `%` de psycopg2 tarafindan yorumlanir.
            cikti.append(p.replace("%", "%%"))
        else:
            cikti.append(p.replace("%", "%%").replace("?", "%s"))
    return "".join(cikti)


# ------------------------------------------------------------------
# COLLATE NOCASE -> citext
# ------------------------------------------------------------------
# SQLite'ta `COLLATE NOCASE` buyuk/kucuk harf duyarsiz karsilastirma
# saglar. Olculdu: 4 yerde kullaniliyor (kullanicilar.eposta,
# roller.ad, mesajlar.gonderen, mesajlar.alici).
#
# PG'de `NOCASE` diye bir siralama duzeni YOKTUR. Cevrilmezse sonuc
# SESSIZ ve CIDDI olur: ayni e-postanin farkli harf duzeniyle IKINCI
# bir kullanici kaydi olusur, pilot kendi ucus kayitlarini goremez.
#
# Cozum: `citext` eklentisi (buyuk/kucuk harf duyarsiz TEXT).
# Eklenti yoksa duz TEXT'e dusulur; kod zaten `.strip().lower()`
# normalizasyonu yapiyor (olculdu: kullanicilar.py 4 yerde), bu yuzden
# dusus guvenlidir ancak veritabani duzeyinde garanti kaybedilir.
_CITEXT_VAR = None          # None = henuz olculmedi


def citext_var(con=None) -> bool:
    """`citext` eklentisinin KURULU olup olmadigini olcer (onbellekli)."""
    global _CITEXT_VAR
    if _CITEXT_VAR is not None:
        return _CITEXT_VAR
    try:
        c = con or baglanti()
        s = c.execute(
            "SELECT count(*) FROM pg_extension WHERE extname='citext'"
        ).fetchone()
        _CITEXT_VAR = bool(s and int(s[0]) > 0)
    except Exception:
        _CITEXT_VAR = False
    return _CITEXT_VAR


def citext_kur(con=None) -> dict:
    """`citext` eklentisini kurmayi dener.

    `CREATE EXTENSION` yetkisi gerektirir (superuser veya veritabani
    sahibi). Yetki yoksa acik hata dondurur; sihirbaz bunu kullaniciya
    gosterir ve duz TEXT ile devam eder.
    """
    global _CITEXT_VAR
    sonuc = {"tamam": False, "hata": "", "zaten": False}
    try:
        c = con or baglanti()
        if citext_var(c):
            sonuc["tamam"] = True
            sonuc["zaten"] = True
            return sonuc
        c.execute("CREATE EXTENSION IF NOT EXISTS citext")
        c.commit()
        _CITEXT_VAR = True
        sonuc["tamam"] = True
    except Exception as e:
        try:
            (con or baglanti()).rollback()
        except Exception:
            pass
        _CITEXT_VAR = False
        sonuc["hata"] = f"{type(e).__name__}: {e}"
    return sonuc


# ------------------------------------------------------------------
# PRAGMA cevirisi
# ------------------------------------------------------------------
# Olculdu: `veritabani.py:1665` -> `PRAGMA table_info({tablo})`
# (`_sema_guncelle()` icinde, idempotent kolon ekleme icin).
#
# SQLite `PRAGMA table_info` satirlari: (cid, name, type, notnull,
# dflt_value, pk). Kod `r[1]` ile KOLON ADINI okuyor:
#     mevcut = {r[1] for r in con.execute(f"PRAGMA table_info({t})")}
# Bu yuzden PG karsiligi AYNI SIRADA kolon dondurmeli, yoksa kolon
# adlari yerine baska bir alan okunur ve `ALTER TABLE` her acilista
# yeniden denenir (hata uretir).
_PRAGMA_TABLE_INFO = re.compile(
    r"^\s*PRAGMA\s+table_info\s*\(\s*[\"']?([A-Za-z_][A-Za-z0-9_]*)"
    r"[\"']?\s*\)\s*;?\s*$", re.I)
# Diger PRAGMA'lar PG'de karsiligi olmayan SQLite dosya ayarlaridir
# (journal_mode, synchronous, wal_autocheckpoint, busy_timeout,
# foreign_keys). PG'de bu ayarlar sunucu tarafindadir; sessizce
# yoksayilirlar.
_PRAGMA_DIGER = re.compile(r"^\s*PRAGMA\s+", re.I)


def _pragma_cevir(sql: str):
    """`PRAGMA` -> PG karsiligi. Doner: (sql, parametreler) veya None.

    None donerse deyim yoksayilmalidir (PG'de karsiligi yok).
    """
    m = _PRAGMA_TABLE_INFO.match(sql)
    if m:
        # SQLite kolon sirasi: cid, name, type, notnull, dflt_value, pk
        return (
            "SELECT (ordinal_position - 1) AS cid, column_name AS name,"
            " data_type AS type,"
            " CASE WHEN is_nullable='NO' THEN 1 ELSE 0 END AS notnull,"
            " column_default AS dflt_value, 0 AS pk"
            " FROM information_schema.columns"
            " WHERE table_schema='public' AND table_name=%s"
            " ORDER BY ordinal_position",
            (m.group(1).lower(),),
        )
    if _PRAGMA_DIGER.match(sql):
        return None
    return "", None


# ------------------------------------------------------------------
# SQLite SQL islev cevirileri
# ------------------------------------------------------------------
# Sistematik tarandi (tum goktungu/*.py, SQL dizeleri): SQL icinde
# PG'de karsiligi OLMAYAN tek islev `strftime(...)`.
#
#   veritabani.py:803 (v_ucuslar gorunumu):
#       strftime('%Y%m%d_%H%M%S', MIN(s.ts), 'unixepoch', 'localtime')
#
# Diger eslesmeler ya Python kodu (`time.strftime`, `hex()`,
# `shlex.quote`) ya da PG'de de gecerli standart islevlerdir
# (`ROUND`, `COALESCE`, `ABS`, `REPLACE`, `SUBSTR`, `CAST`).
# `typeof(...)` yalnizca `db_onarim.py` icinde ve o modul PG kipinde
# devre disidir.
#
# KRITIK: `v_ucuslar.id` bicimi `YYYYMMDD_HHMMSS_D{sysid}` olarak
# KORUNMALIDIR; `ai_tespitler.ucus_id` bu bicimle eslesiyor ve ucus
# raporlari bu kimlikle birlestiriliyor. Bicim degisirse eski
# tespitler ucuslarla eslesmez.
_SQLITE_BICIM_PG = {
    "%Y": "YYYY", "%m": "MM", "%d": "DD",
    "%H": "HH24", "%M": "MI", "%S": "SS",
    "%j": "DDD", "%W": "IW", "%w": "D", "%%": "%",
}

# DIKKAT: Duz regex `strftime\((.+?)\)` YETMEZ. Olculdu ve KANITLANDI:
# `strftime('%Y', MIN(s.ts), 'unixepoch')` ifadesinde tembel eslesme
# ILK kapanis parantezinde durur ve `MIN(s.ts` seklinde BOZUK SQL
# uretir:
#     to_char(CAST(MIN(s.ts AS timestamptz), 'YYYY...
#                          ^ syntax error at or near "AS"
# Bu yuzden parantez dengesi ELLE takip edilir.
_STRFTIME_BAS = re.compile(r"\bstrftime\s*\(", re.I)

# ------------------------------------------------------------------
# ROUND(x, n) tip uyusmazligi
# ------------------------------------------------------------------
# Olculdu ve KANITLANDI (v_ucuslar gorunumu, ucus SURESI hesabi):
#     ROUND(MAX(s.ts) - MIN(s.ts), 1)
#     -> UndefinedFunction: round(double precision, integer) does not exist
#
# SQLite `ROUND(x, n)` her sayisal tipi kabul eder. PG'de IKI argumanli
# `round` YALNIZCA `numeric` icin tanimlidir; `double precision` ile
# cagrilirsa islev bulunamaz.
#
# Bu ilk taramada "PG'de de standart" diye gecilmisti; OLCUM duzeltti.
# Cozum: ilk argumani `::numeric` ile donustur.
_ROUND_BAS = re.compile(r"\bROUND\s*\(", re.I)


def _round_cevir(sql: str) -> str:
    """Iki argumanli `ROUND(x, n)` -> `ROUND((x)::numeric, n)`.

    Tek argumanli `ROUND(x)` PG'de `double precision` ile calisir,
    dokunulmaz.
    """
    ara = 0
    while True:
        m = _ROUND_BAS.search(sql, ara)
        if not m:
            return sql
        ic_bas = m.end()
        derinlik, tirnak, i = 1, None, ic_bas
        while i < len(sql) and derinlik > 0:
            ch = sql[i]
            if tirnak:
                if ch == tirnak:
                    tirnak = None
            elif ch in "'\"":
                tirnak = ch
            elif ch == "(":
                derinlik += 1
            elif ch == ")":
                derinlik -= 1
            i += 1
        if derinlik != 0:
            return sql
        ic = sql[ic_bas:i - 1]
        parcalar = _ust_duzey_virgul_ayir(ic)
        if len(parcalar) != 2:
            # Tek argumanli veya beklenmeyen bicim: dokunma
            ara = i
            continue
        x, n = parcalar[0].strip(), parcalar[1].strip()
        if "::numeric" in x.lower() or "as numeric" in x.lower():
            ara = i
            continue
        yeni = f"ROUND(({x})::numeric, {n})"
        sql = sql[:m.start()] + yeni + sql[i:]
        ara = m.start() + len(yeni)


def _strftime_cevir(sql: str) -> str:
    """SQLite `strftime()` -> PG `to_char(to_timestamp(...))`.

    SQLite bicim belirtecleri (`%Y`) PG belirteclerine (`YYYY`)
    cevrilir. `'unixepoch'` degistirici zaman damgasinin Unix saniyesi
    oldugunu bildirir -> `to_timestamp()`. `'localtime'` yerel saat
    dilimine cevirir -> `AT TIME ZONE`.

    Parantez dengesi elle takip edilir (ic ice `MIN(...)` icin sart).
    """
    while True:
        m = _STRFTIME_BAS.search(sql)
        if not m:
            return sql
        bas = m.start()
        ic_bas = m.end()          # '(' sonrasi
        # Dengeli kapanis parantezini bul
        derinlik, tirnak, i = 1, None, ic_bas
        while i < len(sql) and derinlik > 0:
            ch = sql[i]
            if tirnak:
                if ch == tirnak:
                    tirnak = None
            elif ch in "'\"":
                tirnak = ch
            elif ch == "(":
                derinlik += 1
            elif ch == ")":
                derinlik -= 1
            i += 1
        if derinlik != 0:
            # Dengesiz parantez: dokunmadan birak (bozmaktan iyidir)
            return sql
        ic = sql[ic_bas:i - 1]
        parcalar = [p.strip() for p in _ust_duzey_virgul_ayir(ic)]
        if not parcalar:
            return sql

        bicim = parcalar[0].strip().strip("'\"")
        ifade = parcalar[1] if len(parcalar) > 1 else "0"
        degistiriciler = {p.strip().strip("'\"").lower()
                          for p in parcalar[2:]}

        pg_bicim = bicim
        for s, p in _SQLITE_BICIM_PG.items():
            pg_bicim = pg_bicim.replace(s, p)

        if "unixepoch" in degistiriciler:
            zaman = f"to_timestamp({ifade})"
        else:
            zaman = f"CAST({ifade} AS timestamptz)"

        if "localtime" in degistiriciler:
            zaman = f"({zaman} AT TIME ZONE current_setting('TimeZone'))"
        elif "utc" in degistiriciler:
            zaman = f"({zaman} AT TIME ZONE 'UTC')"

        sql = sql[:bas] + f"to_char({zaman}, '{pg_bicim}')" + sql[i:]


def _ust_duzey_virgul_ayir(s: str):
    """En ust duzey virgullere gore ayirir (parantez/tirnak farkindalikli)."""
    parcalar, derinlik, tirnak, tampon = [], 0, None, []
    for ch in s:
        if tirnak:
            tampon.append(ch)
            if ch == tirnak:
                tirnak = None
            continue
        if ch in "'\"":
            tirnak = ch
            tampon.append(ch)
        elif ch == "(":
            derinlik += 1
            tampon.append(ch)
        elif ch == ")":
            derinlik -= 1
            tampon.append(ch)
        elif ch == "," and derinlik == 0:
            parcalar.append("".join(tampon))
            tampon = []
        else:
            tampon.append(ch)
    if tampon:
        parcalar.append("".join(tampon))
    return parcalar


_COLLATE_NOCASE = re.compile(r"\s+COLLATE\s+NOCASE\b", re.I)
_TEXT_NOCASE = re.compile(
    r"\bTEXT\b((?:\s+(?:PRIMARY\s+KEY|NOT\s+NULL|DEFAULT\s+'[^']*'))*)"
    r"\s+COLLATE\s+NOCASE\b", re.I)


# Sema cevirisi: SQLite tipleri -> PG tipleri
_SEMA_KURALLARI = [
    # AUTOINCREMENT birincil anahtar -> BIGSERIAL
    (re.compile(r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b", re.I),
     "BIGSERIAL PRIMARY KEY"),
    # AUTOINCREMENT'siz INTEGER PRIMARY KEY: KOLON ADINA gore ayrilir.
    #
    # KRITIK KUSUR (v2.4.51'de olculerek yakalandi). Onceki kural bunu
    # kosulsuz `BIGSERIAL` yapiyordu ve gerekce yorumu "SQLite'ta da
    # otomatik artar" diyordu. Bu KISMEN dogru ama kritik farki atlar:
    # SQLite'ta deger ACIKCA VERILIRSE onu kullanir, yalnizca
    # verilmezse artirir. `BIGSERIAL` ise `nextval()` varsayilanini
    # devreye sokar.
    #
    # OLCULEN SONUC (dene_faz5.py): `gorev_durum.sysid` BIGSERIAL oldu,
    # iki dron (sysid 7 ve 9) AYNI satira dustu ve biri kayboldu:
    #     gonderilen 7 -> tabloda [7, 9]
    #     gonderilen 9 -> tabloda [9]        <- 7 KAYBOLDU
    # `sysid` dronun MAVLink kimligidir (anlamli deger), sayac DEGIL.
    # Sahada etkisi: iki dron ayni anda gorevdeyken birinin surdurme
    # kaydi silinir; batarya degisiminde gorev kaldigi yerden SURMEZ.
    # `param_cache.sysid` de ayni kusurdan etkileniyordu: parametre
    # onbellegi YANLIS drona yazilabilirdi.
    #
    # AYRIM: `id` adli anahtari veritabani uretir (11 yerde
    # `lastrowid` bekleniyor) -> BIGSERIAL. `sysid` gibi anlamli
    # anahtarlari UYGULAMA verir -> BIGINT (deger korunur).
    (re.compile(r"\bid\s+INTEGER\s+PRIMARY\s+KEY\b(?!\s*,?\s*\()", re.I),
     "id BIGSERIAL PRIMARY KEY"),
    (re.compile(r"\bINTEGER\s+PRIMARY\s+KEY\b(?!\s*,?\s*\()", re.I),
     "BIGINT PRIMARY KEY"),
    # SQLite REAL -> PG DOUBLE PRECISION
    (re.compile(r"\bREAL\b", re.I), "DOUBLE PRECISION"),
    # WITHOUT ROWID PG'de yok
    (re.compile(r"\bWITHOUT\s+ROWID\b", re.I), ""),
    # SQLite'in tip adlari
    (re.compile(r"\bBLOB\b", re.I), "BYTEA"),
]


def sema_cevir(sql: str, citext: bool | None = None) -> str:
    """SQLite CREATE TABLE/VIEW ifadesini PG'ye cevirir.

    `citext`: `citext` eklentisi kullanilsin mi. None ise olculur.
    """
    # SQLite'a ozgu SQL islevleri (gorunumlerde kullaniliyor)
    dusuk = sql.lower()
    if "strftime" in dusuk:
        sql = _strftime_cevir(sql)
    if "round" in dusuk:
        sql = _round_cevir(sql)
    # COLLATE NOCASE once islenmeli (TEXT -> CITEXT donusumu icin)
    if citext is None:
        try:
            citext = citext_var()
        except Exception:
            citext = False
    if citext:
        # `TEXT ... COLLATE NOCASE` -> `CITEXT ...`
        sql = _TEXT_NOCASE.sub(lambda m: "CITEXT" + m.group(1), sql)
    # Kalan COLLATE NOCASE ifadelerini kaldir (PG'de gecersiz)
    sql = _COLLATE_NOCASE.sub("", sql)

    for desen, yeni in _SEMA_KURALLARI:
        sql = desen.sub(yeni, sql)
    return sql


# INSERT OR REPLACE / IGNORE -> ON CONFLICT
_OR_REPLACE = re.compile(r"\bINSERT\s+OR\s+REPLACE\s+INTO\b", re.I)
_OR_IGNORE = re.compile(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", re.I)
_INSERT_INTO = re.compile(
    r"\bINSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)", re.I)


def _catisma_cevir(sql: str, catisma_kolonlari: dict) -> str:
    """`INSERT OR REPLACE/IGNORE` -> `ON CONFLICT ...`.

    `catisma_kolonlari`: {tablo: [kolon, ...]} — hangi kolonlarda
    catisma bekleniyor. PG'de `ON CONFLICT` hedef belirtmek ZORUNLUDUR
    (SQLite gibi "herhangi bir kisitlama" davranisi yoktur).
    """
    if _OR_IGNORE.search(sql):
        sql = _OR_IGNORE.sub("INSERT INTO", sql)
        if "ON CONFLICT" not in sql.upper():
            sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
        return sql

    if _OR_REPLACE.search(sql):
        temiz = _OR_REPLACE.sub("INSERT INTO", sql)
        m = _INSERT_INTO.search(temiz)
        if not m:
            return temiz
        tablo = m.group(1).lower()
        kolonlar = [k.strip() for k in m.group(2).split(",")]
        hedef = catisma_kolonlari.get(tablo)
        if not hedef:
            # Hedef bilinmiyorsa DO NOTHING'e dusmek REPLACE anlamini
            # bozar (guncelleme yapilmaz). Bu yuzden acikca bildir.
            raise ValueError(
                f"INSERT OR REPLACE icin catisma kolonu tanimsiz: {tablo}. "
                "pg.CATISMA sozlugune ekleyin.")
        guncelle = [k for k in kolonlar if k not in hedef]
        if guncelle:
            atama = ", ".join(f"{k}=EXCLUDED.{k}" for k in guncelle)
            ek = (f" ON CONFLICT ({', '.join(hedef)}) DO UPDATE SET {atama}")
        else:
            ek = f" ON CONFLICT ({', '.join(hedef)}) DO NOTHING"
        return temiz.rstrip().rstrip(";") + ek

    return sql


# Tablo -> catisma kolonlari. `INSERT OR REPLACE` kullanan 14 yer icin
# olculdu (ayarlar.py, dron.py, kayit.py, db_onarim.py).
CATISMA = {
    "ayarlar": ["anahtar"],
    # Kalici kullanici dron adi kayitlari; PostgreSQL semasinda PRIMARY KEY(uid).
    # Catisma cevirisi fiziksel sema takma adini degil, uygulamanin SQL'indeki
    # ozgun tablo adini okur; bu nedenle anahtar `dron_kayitlari` olmalidir.
    "dron_kayitlari": ["uid"],
    "dron_parametreler": ["dron_id", "ad"],
    "param_cache": ["sysid"],
    "kisi_yuzler": ["kisi_id", "yuz_id"],
    "roller": ["ad"],
    "izinler": ["rol", "izin"],
    "joystick_pilot": ["eposta"],
    "harita_karo": ["kaynak", "z", "x", "y"],
    "telemetri_tampon_kayit": ["dosya"],
    # Anahtar `sysid`'dir. Olculdu (dene_faz5.py): sozlukte `dron_uid`
    # yazarken PG "ON CONFLICT icin eslesen benzersizlik kisiti yok"
    # dedi ve gorev surdurme HIC yazilamadi. Hata konsola uyari olarak
    # dusup dosyaya geri donuldugu icin SESSIZ kalirdi: pilot batarya
    # degistirir, gorev kaldigi yerden SURMEZ.
    "gorev_durum": ["sysid"],
    # v2.4.51 goc defteri (goktungu/goc.py). Olculdu ve KANITLANDI:
    # bu girdi eksikken defter kaydi HIC yazilamiyordu ve goc zinciri
    # tamamen coktu (11 madde KALDI). Ag gecidinin bilinmeyen tabloda
    # SESSIZCE `DO NOTHING`'e dusmek yerine ACIK hata vermesi kusuru
    # aninda gosterdi; sessiz dusseydi goc "basarili" gorunur, defter
    # bos kalir ve her acilista goc yeniden calisirdi.
    "sema_goc_defteri": ["adim"],
    # Sinav tablosu (dene_pg_gecit.py)
    "dene_ayar": ["anahtar"],
}


# ------------------------------------------------------------------
# sqlite3 API taklidi
# ------------------------------------------------------------------
class Satir:
    """`sqlite3.Row` taklidi: HEM ada HEM indekse gore erisim.

    Olculdu: kod tabaninda satirlar hem `r["ad"]` hem `r[0]` biciminde
    okunuyor (`fetchone()[0]` 14 yerde). psycopg2'nin `DictRow`'u
    indeksle erisimi destekler ancak `keys()` ve `dict()` davranisi
    farklidir; bu sinif SQLite semantigini birebir saglar.
    """

    __slots__ = ("_deger", "_ad")

    def __init__(self, adlar, degerler):
        self._ad = adlar
        self._deger = degerler

    def __getitem__(self, k):
        if isinstance(k, str):
            try:
                return self._deger[self._ad.index(k)]
            except ValueError:
                raise IndexError(k)
        return self._deger[k]

    def __iter__(self):
        return iter(self._deger)

    def __len__(self):
        return len(self._deger)

    def keys(self):
        return list(self._ad)

    def __contains__(self, k):
        return k in self._ad

    def get(self, k, varsayilan=None):
        try:
            return self[k]
        except (IndexError, KeyError):
            return varsayilan

    def __repr__(self):
        return f"Satir({dict(zip(self._ad, self._deger))})"


# ------------------------------------------------------------------
# `id` kolonu onbellegi
# ------------------------------------------------------------------
# `RETURNING id` yalnizca `id` kolonu OLAN tablolara eklenebilir.
# Onbellek olmadan her INSERT icin `information_schema` sorgusu
# gerekir; bu telemetri yazma yolunu yavaslatir.
_ID_KOLONU: dict = {}
_ID_KOLONU_KILIT = threading.Lock()

_INSERT_TABLO = re.compile(
    r"^\s*INSERT\s+(?:OR\s+\w+\s+)?INTO\s+[\"']?"
    r"([A-Za-z_][A-Za-z0-9_]*)", re.I)


def _tablo_adi(sql: str) -> str:
    """`INSERT INTO <tablo>` icinden tablo adini ayiklar."""
    m = _INSERT_TABLO.match(sql or "")
    return m.group(1).lower() if m else ""


def id_onbellegini_temizle() -> None:
    """Sema degisiminden sonra onbellegi bosaltir (goc motoru cagirir)."""
    with _ID_KOLONU_KILIT:
        _ID_KOLONU.clear()


class Imlec:
    """`sqlite3.Cursor` taklidi."""

    def __init__(self, pg_imlec):
        self._i = pg_imlec
        self._son_id = None

    def _id_kolonu_var(self, sql: str) -> bool:
        """Hedef tabloda `id` kolonu var mi (onbellekli olcum).

        KRITIK: Tahmin edilmez, OLCULUR. `information_schema` sorgusu
        tablo basina BIR kez yapilir ve sonuc onbelleklenir.
        Tablo adi cozulemezse `False` dondurulur; `RETURNING`
        eklenmez ve boylece geri sarma yoluna HIC girilmez.
        """
        tablo = _tablo_adi(sql)
        if not tablo:
            return False
        with _ID_KOLONU_KILIT:
            bilinen = _ID_KOLONU.get(tablo)
        if bilinen is not None:
            return bilinen
        # KRITIK: Olcum AYRI imlecte yapilir. Ayni imlec kullanilirsa
        # `fetchone()` imlecin sonucunu tuketir ve hemen ardindan
        # calisan INSERT'in `RETURNING id` degeri OKUNAMAZ ->
        # `lastrowid` None doner (v2.4.51'de olculerek yakalandi).
        try:
            yardimci = self._i.connection.cursor()
            try:
                yardimci.execute(
                    "SELECT 1 FROM information_schema.columns"
                    " WHERE table_schema='public' AND table_name=%s"
                    " AND column_name='id' LIMIT 1", (tablo,))
                var = yardimci.fetchone() is not None
            finally:
                yardimci.close()
        except psycopg2.Error:
            var = False
        with _ID_KOLONU_KILIT:
            _ID_KOLONU[tablo] = var
        return var

    # -- lastrowid --------------------------------------------------
    @property
    def lastrowid(self):
        """SQLite `lastrowid` karsiligi.

        KRITIK: psycopg2'nin kendi `lastrowid`'i OID dondurur ve
        modern PG tablolarinda (OID'siz) None'dir. Sessizce None
        donmesi yeni kaydin kimliginin alinamamasina yol acar.
        Bu yuzden `execute()` INSERT'lere `RETURNING id` ekler ve
        deger burada tutulur.
        """
        return self._son_id

    @property
    def rowcount(self):
        return self._i.rowcount

    @property
    def description(self):
        return self._i.description

    def _adlar(self):
        d = self._i.description
        return [k[0] for k in d] if d else []

    def execute(self, sql, parametreler=()):
        # PRAGMA once islenmeli (PG'de gecersiz sozdizimi)
        if sql.lstrip()[:7].upper() == "PRAGMA ":
            cevrim = _pragma_cevir(sql)
            if cevrim is None:
                # PG'de karsiligi yok; bos sonuc kumesi dondur ki
                # `.fetchall()` cagrisi patlamasin.
                self._i.execute("SELECT 1 WHERE false")
                self._son_id = None
                return self
            yeni_sql, yeni_par = cevrim
            if yeni_sql:
                self._i.execute(yeni_sql, yeni_par)
                self._son_id = None
                return self

        # Tekil DDL deyimleri de cevrilmelidir. Olculdu: `CREATE TABLE`
        # tek deyim olarak da cagriliyor (`_sema_guncelle`, `ALTER TABLE
        # ADD COLUMN ... REAL`), yalnizca `executescript` yolunu cevirmek
        # yetmez; `REAL`/`AUTOINCREMENT` iceren tekil DDL PG'de patlar.
        u0 = sql.lstrip()[:14].upper()
        if u0.startswith(("CREATE TABL", "CREATE INDE", "ALTER TABLE",
                          "CREATE VIEW", "CREATE UNIQ")):
            sql = sema_cevir(sql, citext=_CITEXT_VAR)
        cevrilmis = _yer_tutucu_cevir(_catisma_cevir(sql, CATISMA))
        yukselt = False
        # INSERT ise ve RETURNING yoksa, lastrowid icin ekle.
        #
        # KRITIK KUSUR (v2.4.51'de olculerek yakalandi ve duzeltildi)
        # -----------------------------------------------------------
        # `RETURNING id` YALNIZCA tabloda `id` kolonu VARSA eklenir.
        # Onceki hali kosulsuz ekliyor, patlayinca su satirla
        # kurtarmaya calisiyordu:
        #     self._i.connection.rollback()
        # `rollback()` yalnizca basarisiz DEYIMI degil, AYNI ISLEMDEKI
        # TUM ONCEKI YAZIMLARI geri alir.
        #
        # Olculen belirti (`id` kolonu OLMAYAN `gorev_durum`, ayni
        # baglanti blogunda iki ekleme):
        #     sysid=7 -> [7]
        #     sysid=9 -> [9]        <- 7 KAYBOLDU
        # Ham psycopg2 ile AYNI SQL: [7, 9] (DOGRU)
        # -> kusur bu katmandaydi, SQL'de veya semada degildi.
        #
        # Etkilenen tablolar: `id` kolonu olmayan HEPSI --
        # `gorev_durum`, `param_cache`, `ayarlar`, `sema_goc_defteri`,
        # `harita_karo`, `telemetri_tampon_kayit`. Toplu telemetri
        # yaziminda da ayni islemdeki onceki satirlar silinirdi.
        u = cevrilmis.lstrip().upper()
        if u.startswith("INSERT") and "RETURNING" not in cevrilmis.upper():
            if self._id_kolonu_var(cevrilmis):
                cevrilmis = cevrilmis.rstrip().rstrip(";") + " RETURNING id"
                yukselt = True
        try:
            if yukselt:
                # Onbellek yanilsa bile (yarista sema degisimi)
                # SAVEPOINT geri sarmayi YALNIZCA bu deyime sinirlar;
                # ayni islemdeki onceki yazimlar KORUNUR.
                self._i.execute("SAVEPOINT goktungu_ins")
                try:
                    self._i.execute(cevrilmis, tuple(parametreler))
                except psycopg2.Error:
                    self._i.execute("ROLLBACK TO SAVEPOINT goktungu_ins")
                    t = _tablo_adi(cevrilmis)
                    if t:
                        with _ID_KOLONU_KILIT:
                            _ID_KOLONU[t] = False
                    yalin = _yer_tutucu_cevir(
                        _catisma_cevir(sql, CATISMA))
                    self._i.execute(yalin, tuple(parametreler))
                    self._son_id = None
                    return self
                else:
                    # KRITIK SIRA: `RETURNING id` sonucu, SAVEPOINT
                    # serbest birakilMADAN once okunur. `RELEASE`
                    # bir SQL deyimidir ve ayni imlecte calisirsa
                    # `RETURNING` sonucunu gecersiz kilar ->
                    # `lastrowid` None doner (olculerek yakalandi).
                    try:
                        satir = self._i.fetchone()
                        self._son_id = (
                            int(satir[0]) if satir else None)
                    except psycopg2.Error:
                        self._son_id = None
                    self._i.execute("RELEASE SAVEPOINT goktungu_ins")
                    return self
            else:
                self._i.execute(cevrilmis, tuple(parametreler))
        except psycopg2.Error:
            raise
        return self

    def executemany(self, sql, dizi):
        cevrilmis = _yer_tutucu_cevir(_catisma_cevir(sql, CATISMA))
        psycopg2.extras.execute_batch(
            self._i, cevrilmis, [tuple(p) for p in dizi], page_size=500)
        return self

    def fetchone(self):
        s = self._i.fetchone()
        if s is None:
            return None
        return Satir(self._adlar(), list(s))

    def fetchall(self):
        adlar = self._adlar()
        return [Satir(adlar, list(s)) for s in self._i.fetchall()]

    def fetchmany(self, n=1):
        adlar = self._adlar()
        return [Satir(adlar, list(s)) for s in self._i.fetchmany(n)]

    def close(self):
        try:
            self._i.close()
        except psycopg2.Error:
            pass

    def __iter__(self):
        adlar = self._adlar()
        for s in self._i:
            yield Satir(adlar, list(s))


class Baglanti:
    """`sqlite3.Connection` taklidi.

    `with baglanti() as con:` deseni SQLite'ta islemi commit/rollback
    eder ve BAGLANTIYI KAPATMAZ. Ayni davranis burada da saglanir —
    v2.4.24'te olculen dosya taniticisi sizintisi hatasini
    tekrarlamamak icin baglanti havuzda KALIR.

    `total_changes` (v2.4.51'de olculerek eklendi)
    ----------------------------------------------
    `veritabani.telemetri_toplu_yaz()` GERCEKTEN eklenen satir sayisini
    `total_changes` farkiyla olcer (`INSERT OR IGNORE` mukerrerleri
    atladigi icin `len(satirlar)` yanlis olurdu). PG baglanti nesnesinde
    boyle bir nitelik YOKTUR.

    Olculen etki (dene_kesinti.py): nitelik yokken tampon aktarimi HER
    turda `AttributeError` aliyordu -> telemetri HIC veritabanina
    gecmiyor, dosyalar birikiyor, 5 denemeden sonra karantinaya
    aliniyordu. Ucus gecmisi BOS kalirdi (veri kaybi olmaz, cunku
    tampon dosyayi korur — ama veri de gorunmez).

    Cozum: her imlecin `rowcount`'u calisan toplama eklenir. PG'de
    `rowcount` `INSERT ... ON CONFLICT DO NOTHING` icin GERCEKTEN
    eklenen satir sayisini verir; bu SQLite `total_changes`
    semantigiyle ayni.
    """

    def __init__(self, pg_con):
        self._c = pg_con
        self.row_factory = None      # uyumluluk; Satir zaten donuyor
        self._degisim = 0            # `total_changes` sayaci

    @property
    def total_changes(self) -> int:
        """`sqlite3.Connection.total_changes` karsiligi.

        Bu baglanti uzerinde YAZILAN (eklenen/guncellenen/silinen)
        toplam satir sayisi. `telemetri_toplu_yaz()` iki okuma
        arasindaki FARKI alarak gercekten eklenen satiri olcer.
        """
        return self._degisim

    def _degisim_ekle(self, im) -> None:
        """Imlecin `rowcount`'unu calisan toplama ekler.

        `rowcount` SELECT icin de deger dondurur; yalnizca yazma
        deyimleri sayilmalidir, aksi halde okuma islemleri sayaci
        sisirir ve `telemetri_toplu_yaz` yanlis sayi bildirir.
        """
        try:
            n = im.rowcount
        except Exception:
            return
        if isinstance(n, int) and n > 0:
            self._degisim += n

    # -- islem yonetimi ---------------------------------------------
    def __enter__(self):
        return self

    def __exit__(self, tip, deger, iz):
        if tip is None:
            self._c.commit()
        else:
            self._c.rollback()
        return False                  # istisnayi yut MA

    def commit(self):
        self._c.commit()

    def rollback(self):
        self._c.rollback()

    # -- sorgu ------------------------------------------------------
    def execute(self, sql, parametreler=()):
        im = Imlec(self._c.cursor())
        sonuc = im.execute(sql, parametreler)
        if _YAZMA_DEYIMI.match(sql or ""):
            self._degisim_ekle(im)
        return sonuc
    def executemany(self, sql, dizi):
        im = Imlec(self._c.cursor())
        sonuc = im.executemany(sql, dizi)
        if _YAZMA_DEYIMI.match(sql or ""):
            self._degisim_ekle(im)
        return sonuc

    def executescript(self, betik):
        """`sqlite3.executescript` karsiligi.

        SQLite noktali virgulle ayrilmis coklu deyimi kabul eder.
        psycopg2 de kabul eder, ancak sema cevirisi uygulanmalidir.
        """
        im = self._c.cursor()
        im.execute(sema_cevir(betik, citext=_CITEXT_VAR))
        im.close()
        return self

    def cursor(self):
        return Imlec(self._c.cursor())

    def close(self):
        try:
            self._c.close()
        except Exception:
            pass

    @property
    def kapali(self) -> bool:
        return self._c.closed != 0


def ikili(veri: bytes):
    """Ham baytlari PG BYTEA parametresi olarak sarar.

    SQLite `bytes` nesnesini dogrudan kabul eder. psycopg2 de kabul
    eder, ANCAK `bytes` bazi durumlarda metin olarak yorumlanabilir
    (ozellikle `executemany` ile karisik tipli demetlerde). `Binary`
    sarmalayicisi tipi KESINLESTIRIR.

    Harita karolari (JPEG/PNG) ve AI gomme vektorleri bu yoldan gecer;
    tek bayt bozulmasi karoyu okunamaz yapar.
    """
    if veri is None:
        return None
    if not VAR:
        return veri
    return psycopg2.Binary(veri)


# ==================================================================
# BAGLANTI HAVUZU (v2.4.52'de YENIDEN YAZILDI)
# ==================================================================
# v2.4.51 KUSURU (olc_baglanti.py ile GERCEK PG uzerinde olculdu):
#
#   Havuz deseni `threading.local` uzerine kuruluydu: is parcasi
#   basina KALICI baglanti. Bu desen v2.4.24'te SQLite icin yazildi ve
#   ORADA DOGRUYDU (baglanti = dosya taniticisi, sunucu tarafi sinir
#   yok). PostgreSQL'e AYNEN tasinmasi iki kusur uretti:
#
#   KUSUR A — baglanti sayisi is parcasi sayisina esit:
#       20 is parcasi -> 20 PG backend sureci (olculdu).
#       Kod tabaninda 36 yerde is parcasi uretilir ve cogu DRON
#       BASINA; 10 dronlu ucus 10 kat demektir. `max_connections`
#       varsayilani 100 -> tukenme.
#
#   KUSUR B — SIZINTI (asil neden):
#       15 gecici is parcasi `baglanti_kapat()` cagirmadan OLDU;
#       15 baglanti PG'de ACIK KALDI (olculdu). `threading.local`
#       baglantiyi tutar, is parcasi olurken kimse kapatmaz. Uzun bir
#       GCS oturumunda olusup olen her gecici parca kalici olarak bir
#       yuva sizdirir.
#
#   Sonuc (kullanicinin gordugu hata):
#       FATAL: sorry, too many clients already
#   pgAdmin dahil YENI GELEN HERKES disari itilir.
#
#   EK BULGU — `idle in transaction`:
#       Olculen 20 baglantinin durumu "idle" DEGIL "idle in
#       transaction"di. `autocommit=False` oldugu icin `SELECT 1`
#       bile islem baslatir. Boyle bir baglanti kilitleri BIRAKMAZ ve
#       `VACUUM`'un olu satirlari toplamasini ENGELLER (xmin horizon)
#       -> telemetri gibi yuksek hacimli tablolar SISER.
#
# v2.4.52 COZUMU: SINIRLI PAYLASILAN HAVUZ
#
#   - Baglanti sayisi is parcasi sayisindan BAGIMSIZ; ust sinir
#     `HAVUZ_MAKS` (varsayilan 10).
#   - Is parcasi baglantiyi ODUNC alir. Odunc, is parcasi OLDUGUNDE
#     otomatik iade edilir (zayif referans + olum kancasi).
#   - Iade sirasinda `rollback()` cagrilir -> `idle in transaction`
#     durumu KAPANIR.
#   - Havuzda bosta duran baglanti `BOSTA_ZAMAN_ASIMI` sn sonra
#     gercekten kapatilir (bellek geri verilir).
#   - Sinir doluysa cagiran BEKLER; sonsuz bekleme YOK
#     (`ODUNC_ZAMAN_ASIMI` sonunda acik hata).
#
#   146 cagri yeri DEGISMEDI: `baglanti()` yine cagrildigi is
#   parcasinda ayni nesneyi dondurur, `with` bloku gerektirmez.
# ==================================================================

# Havuzdaki ES ZAMANLI baglanti ust siniri. PG'de her baglanti ayri
# bir surec (~5-10 MB) oldugu icin bu sayi kucuk tutulmalidir.
HAVUZ_MAKS = 10
# Havuzda bosta bekleyen baglanti bu sureden sonra GERCEKTEN kapanir.
BOSTA_ZAMAN_ASIMI = 300.0
# Havuz doluyken odunc almak icin beklenecek en uzun sure (sn).
ODUNC_ZAMAN_ASIMI = 20.0
# Bir is parcasi baglantiyi bu sureden uzun tutar ve ARADA HIC SORGU
# YAPMAZSA odunc geri cagrilir. "Is parcasi yasiyor ama saatlerdir DB
# kullanmiyor" durumu yuva tutmasin diye.
ATIL_ODUNC_SURESI = 600.0

_havuz_kosul = threading.Condition(_havuz_kilit)
# Bosta bekleyen baglantilar: [(Baglanti, en_son_kullanim_zamani), ...]
_bosta: list = []
# Odunc verilenler: {is_parcasi_id: _Odunc}
_oduncler: dict = {}
# Toplam canli baglanti sayisi (bosta + odunc). Sinir buna uygulanir.
_canli = 0
# Tanilama sayaclari
_sayac = {"acilan": 0, "kapanan": 0, "iade": 0, "bekleme": 0,
          "olum_iadesi": 0, "atil_geri_alma": 0, "zaman_asimi": 0}


class _Odunc:
    """Bir is parcasina odunc verilen baglantinin kaydi.

    `izci` alanı KRITIKTIR: is parcasinin `threading.local` sozlugune
    yerlestirilen bir nesnedir. Is parcasi olunce Python bu sozlugu
    yok eder, `izci` icin cop toplama calisir ve zayif referans geri
    cagrimi tetiklenir -> baglanti OTOMATIK iade edilir.

    v2.4.51'de bu mekanizma YOKTU; is parcasi olunce baglanti PG'de
    asili kaliyordu (olculdu: 15/15 sizinti).
    """

    __slots__ = ("con", "is_id", "alindi", "son_kullanim", "izci_ref")

    def __init__(self, con, is_id):
        self.con = con
        self.is_id = is_id
        self.alindi = time.monotonic()
        self.son_kullanim = self.alindi
        self.izci_ref = None


class _Izci:
    """Is parcasi omru izleyicisi. Tek gorevi YOK EDILMEK."""

    __slots__ = ("is_id", "__weakref__")

    def __init__(self, is_id):
        self.is_id = is_id


def _olum_kancasi(is_id):
    """Is parcasi oldugunde cagrilir (zayif referans geri cagrimi).

    DIKKAT: bu geri cagrim cop toplama sirasinda calisir. Icinde
    kilit almak GUVENLIDIR (GIL tutulur, ayni kilidi bekleyen baska
    parca varsa beklenir), ANCAK istisna firlatmak sessizce yutulur.
    Bu yuzden her adim ayri ayri korunur.
    """
    def _kanca(_zayif_ref):
        try:
            _iade_et(is_id, olum=True)
        except Exception:
            pass
    return _kanca


def _yeni_baglanti_ac() -> Baglanti:
    """Gercek PG baglantisi acar. Havuz muhasebesi YAPMAZ."""
    if not VAR:
        raise RuntimeError(
            "psycopg2 kurulu degil. Kurulum: pip3 install psycopg2-binary")
    if not _yapilandirma:
        raise RuntimeError(
            "PostgreSQL yapilandirilmadi. Kurulum sihirbazini calistirin.")
    con = psycopg2.connect(
        connect_timeout=BAGLANTI_ZAMAN_ASIMI,
        options=f"-c statement_timeout={DEYIM_ZAMAN_ASIMI_MS}",
        application_name="goktungu",
        **_yapilandirma,
    )
    con.autocommit = False
    return Baglanti(con)


def _canli_mi(con) -> bool:
    """Baglanti gercekten kullanilabilir mi.

    Sadece `closed` bakmak YETMEZ: sunucu tarafi baglantiyi
    dusurmus olabilir (ag kesintisi, `pg_terminate_backend`,
    idle_session_timeout). Gercek sorgu ile olculur.
    """
    try:
        if con.kapali:
            return False
    except Exception:
        return False
    try:
        con.execute("SELECT 1").fetchone()
        return True
    except Exception:
        # Islem bozulmus olabilir; geri al ve TEKRAR dene.
        try:
            con.rollback()
            con.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False


def _gercekten_kapat(con) -> None:
    try:
        con.close()
    except Exception:
        pass


def _bostalari_temizle_kilitli(simdi: float) -> list:
    """Zaman asimina ugramis bosta baglantilari listeler ve cikarir.

    Kilit TUTULARAK cagrilmali. Donen baglantilar kilit BIRAKILDIKTAN
    sonra kapatilmali (kapatma ag islemi; kilit altinda yapilmasi tum
    havuzu bloke eder).
    """
    global _canli
    kalan = []
    kapatilacak = []
    for con, zaman in _bosta:
        if simdi - zaman > BOSTA_ZAMAN_ASIMI:
            kapatilacak.append(con)
            _canli -= 1
            _sayac["kapanan"] += 1
        else:
            kalan.append((con, zaman))
    _bosta[:] = kalan
    return kapatilacak


def _atillari_geri_al_kilitli(simdi: float) -> None:
    """Uzun suredir sorgu yapmayan oduncleri geri cagirir.

    Bir is parcasi yasiyor ancak `ATIL_ODUNC_SURESI` boyunca hic sorgu
    yapmadiysa, tuttugu yuva bosa gidiyor demektir. Baglanti havuza
    geri alinir; is parcasi bir dahaki `baglanti()` cagrisinda YENI
    baglanti alir (cagri yeri bunu FARK ETMEZ).

    Kilit TUTULARAK cagrilmali.
    """
    global _canli
    for is_id in list(_oduncler.keys()):
        od = _oduncler.get(is_id)
        if od is None:
            continue
        if simdi - od.son_kullanim <= ATIL_ODUNC_SURESI:
            continue
        _oduncler.pop(is_id, None)
        _sayac["atil_geri_alma"] += 1
        # Islemi geri al ve havuza koy. Kilit altinda rollback
        # yapmamak icin bosta listesine "dogrulanacak" olarak eklenir;
        # `baglanti()` zaten `_canli_mi()` ile dogrular.
        _bosta.append((od.con, simdi))
        _havuz_kosul.notify()


def baglanti() -> Baglanti:
    """Bu is parcasina odunc verilmis PG baglantisini dondurur.

    v2.4.52: ARTIK is parcasi basina KALICI baglanti DEGIL, sinirli
    havuzdan ODUNC. Cagri sozlesmesi degismedi:
      - Ayni is parcasi ayni nesneyi alir (146 cagri yeri etkilenmez)
      - `with baglanti() as con:` calismaya devam eder
      - Is parcasi olunce baglanti OTOMATIK iade edilir
    """
    global _canli
    is_id = threading.get_ident()

    # 1) Bu is parcasinin zaten odunc aldigi baglanti var mi?
    with _havuz_kilit:
        od = _oduncler.get(is_id)
    if od is not None:
        if _canli_mi(od.con):
            od.son_kullanim = time.monotonic()
            return od.con
        # Olu baglanti: muhasebeden dus, yenisini al.
        with _havuz_kilit:
            if _oduncler.get(is_id) is od:
                _oduncler.pop(is_id, None)
                _canli -= 1
                _sayac["kapanan"] += 1
        _gercekten_kapat(od.con)

    # 2) Havuzdan odunc al (gerekirse bekle).
    bitis = time.monotonic() + ODUNC_ZAMAN_ASIMI
    beklendi = False
    while True:
        kapatilacak = []
        con = None
        yeni_ac = False
        with _havuz_kilit:
            simdi = time.monotonic()
            kapatilacak = _bostalari_temizle_kilitli(simdi)
            _atillari_geri_al_kilitli(simdi)

            if _bosta:
                con, _ = _bosta.pop()
            elif _canli < HAVUZ_MAKS:
                _canli += 1                    # yuvayi SIMDI ayir
                yeni_ac = True
            else:
                # Havuz dolu: bekle.
                kalan = bitis - simdi
                if kalan <= 0:
                    _sayac["zaman_asimi"] += 1
                    raise RuntimeError(
                        f"PostgreSQL baglanti havuzu dolu "
                        f"({HAVUZ_MAKS} baglanti) ve {ODUNC_ZAMAN_ASIMI:.0f} "
                        f"sn icinde bosalmadi. Es zamanli veritabani "
                        f"islemi cok fazla.")
                beklendi = True
                _havuz_kosul.wait(min(kalan, 1.0))

        for c in kapatilacak:
            _gercekten_kapat(c)

        if yeni_ac:
            try:
                con = _yeni_baglanti_ac()
            except Exception:
                # Ayrilan yuvayi GERI VER; aksi halde basarisiz her
                # deneme havuzu kalici olarak kucultur ve sonunda
                # hicbir baglanti acilamaz.
                with _havuz_kilit:
                    _canli -= 1
                    _havuz_kosul.notify()
                raise
            with _havuz_kilit:
                _sayac["acilan"] += 1
        elif con is not None:
            # Havuzdan gelen baglantiyi DOGRULA.
            if not _canli_mi(con):
                _gercekten_kapat(con)
                with _havuz_kilit:
                    _canli -= 1
                    _sayac["kapanan"] += 1
                    _havuz_kosul.notify()
                continue                       # bastan dene
        else:
            continue                           # bekledik, tekrar dene

        if beklendi:
            with _havuz_kilit:
                _sayac["bekleme"] += 1

        # 3) Odunc kaydini olustur ve OLUM KANCASINI kur.
        od = _Odunc(con, is_id)
        izci = _Izci(is_id)
        od.izci_ref = weakref.ref(izci, _olum_kancasi(is_id))
        # Izci is parcasinin yerel sozlugune konur; is parcasi olunce
        # yok edilir ve kanca tetiklenir.
        _yerel.izci = izci
        with _havuz_kilit:
            _oduncler[is_id] = od
        return con


def _iade_et(is_id, olum: bool = False) -> None:
    """Bir is parcasinin oduncunu havuza geri verir.

    `olum=True` ise is parcasi olmustur; baglanti havuzda YENIDEN
    KULLANILIR (kapatilmaz), cunku baglanti saglamdir ve yeniden
    acmak pahalidir.

    KRITIK: iade sirasinda `rollback()` cagrilir. v2.4.51'de olculen
    `idle in transaction` durumu boylece kapanir; aksi halde baglanti
    kilit tutmaya ve `VACUUM`'u engellemeye devam eder.
    """
    global _canli
    with _havuz_kilit:
        od = _oduncler.pop(is_id, None)
        if od is None:
            return
        if olum:
            _sayac["olum_iadesi"] += 1
        _sayac["iade"] += 1

    # Islemi KAPAT (kilit disinda; ag islemi).
    temiz = True
    try:
        od.con.rollback()
    except Exception:
        temiz = False

    if not temiz:
        _gercekten_kapat(od.con)
        with _havuz_kilit:
            _canli -= 1
            _sayac["kapanan"] += 1
            _havuz_kosul.notify()
        return

    with _havuz_kilit:
        _bosta.append((od.con, time.monotonic()))
        _havuz_kosul.notify()


def baglanti_kapat():
    """Bu is parcasinin baglantisini havuza IADE eder.

    v2.4.51'de bu islev baglantiyi GERCEKTEN KAPATIYORDU. v2.4.52'de
    iade eder: baglanti saglamsa havuzda kalir ve baska is parcasi
    kullanir. Cagri yerleri (db_onarim.py dahil) davranis farki
    GORMEZ — is parcasinin baglantisi birakilmis olur.
    """
    _iade_et(threading.get_ident(), olum=False)
    try:
        _yerel.izci = None
    except Exception:
        pass


def tum_baglantilari_kapat():
    """TUM havuzu bosaltir ve baglantilari GERCEKTEN kapatir.

    Yalnizca kapanista, sihirbaz yeniden yapilandirmasinda ve
    sinavlarda cagrilmalidir. Kullanimda olan baglantiyi kapatmak
    psycopg2'de `InterfaceError` uretir (SQLite'taki SIGSEGV riski
    YOKTUR), surec olmez.
    """
    global _canli
    with _havuz_kilit:
        kopya = [c for c, _ in _bosta]
        _bosta.clear()
        for od in _oduncler.values():
            kopya.append(od.con)
        _oduncler.clear()
        _canli = 0
        _sayac["kapanan"] += len(kopya)
        _havuz_kosul.notify_all()
    for c in kopya:
        _gercekten_kapat(c)
    try:
        _yerel.izci = None
    except Exception:
        pass


def havuz_durumu() -> dict:
    """Tanilama: havuzun GERCEK durumu.

    `acik` alani geriye uyumluluk icin korunur (v2.4.51 sozlesmesi):
    canli baglanti sayisi.
    """
    with _havuz_kilit:
        return {
            "acik": _canli,
            "kip": "postgresql",
            "bosta": len(_bosta),
            "odunc": len(_oduncler),
            "maks": HAVUZ_MAKS,
            "sayac": dict(_sayac),
        }


def havuz_sinirini_ayarla(maks: int) -> int:
    """Havuz ust sinirini degistirir (ayarlardan cagrilir).

    Kucultme ANINDA baglanti kapatmaz; fazlalik, bosta zaman asimiyla
    dogal olarak erir. Boylece calisan bir sorgu kesilmez.
    """
    global HAVUZ_MAKS
    try:
        yeni = int(maks)
    except Exception:
        return HAVUZ_MAKS
    yeni = max(1, min(yeni, 100))
    with _havuz_kilit:
        HAVUZ_MAKS = yeni
        _havuz_kosul.notify_all()
    return HAVUZ_MAKS


# ------------------------------------------------------------------
# Baglanti denemesi (sihirbaz dogrulamasi)
# ------------------------------------------------------------------
def dene(host, port, veritabani, kullanici, sifre, ssl="") -> dict:
    """Verilen bilgilerle GERCEK baglanti dener ve yetkileri olcer.

    Sihirbazin "Ilerle" dugmesi bu olcume baglidir; tahminle
    ilerlenmez. Doner: {tamam, hata, surum, surum_no, yetki_tablo,
    yetki_yazma, mevcut_tablo}
    """
    sonuc = {
        "tamam": False, "hata": "", "surum": "", "surum_no": 0,
        "yetki_tablo": False, "yetki_yazma": False, "mevcut_tablo": 0,
        "veritabani_var": False,
        # Sihirbazin okudugu ozet sozluk (arayuz tek yerden okur)
        "yetki": {"tablo_olustur": False, "yazma": False, "citext": False},
    }
    if not VAR:
        sonuc["hata"] = ("psycopg2 kurulu degil. "
                         "Kurulum: pip3 install psycopg2-binary")
        return sonuc
    con = None
    try:
        con = psycopg2.connect(
            host=str(host or "127.0.0.1"), port=int(port or 5432),
            dbname=str(veritabani or "goktungu"), user=str(kullanici or ""),
            password=str(sifre or ""),
            sslmode=str(ssl) if ssl else "prefer",
            connect_timeout=BAGLANTI_ZAMAN_ASIMI,
        )
        sonuc["veritabani_var"] = True
        im = con.cursor()
        im.execute("SELECT version()")
        sonuc["surum"] = (im.fetchone() or [""])[0]
        im.execute("SHOW server_version_num")
        try:
            sonuc["surum_no"] = int((im.fetchone() or ["0"])[0])
        except (TypeError, ValueError):
            sonuc["surum_no"] = 0
        # Mevcut tablo sayisi (kurulum mu, guncelleme mi ayirt etmek icin)
        im.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema='public' AND table_type='BASE TABLE'")
        sonuc["mevcut_tablo"] = int((im.fetchone() or [0])[0])
        # CREATE TABLE yetkisi — GERCEKTEN dene, tahmin etme
        try:
            im.execute("CREATE TABLE _goktungu_yetki_deneme (x integer)")
            im.execute("INSERT INTO _goktungu_yetki_deneme (x) VALUES (1)")
            im.execute("DROP TABLE _goktungu_yetki_deneme")
            con.commit()
            sonuc["yetki_tablo"] = True
            sonuc["yetki_yazma"] = True
        except psycopg2.Error as e:
            con.rollback()
            sonuc["hata"] = ("Tablo olusturma yetkisi yok: "
                             + _hata_sadelestir(e))
        # citext eklentisi: e-posta buyuk/kucuk harf duyarsizligi icin.
        # Yoksa sema cevirisi lower() indeksine duser; sihirbaz bunu
        # bildirsin diye OLCULUR.
        try:
            im.execute("SELECT 1 FROM pg_available_extensions "
                       "WHERE name='citext'")
            sonuc["yetki"]["citext"] = im.fetchone() is not None
        except psycopg2.Error:
            con.rollback()
        sonuc["yetki"]["tablo_olustur"] = sonuc["yetki_tablo"]
        sonuc["yetki"]["yazma"] = sonuc["yetki_yazma"]
        sonuc["tamam"] = bool(sonuc["yetki_tablo"])
        if sonuc["surum_no"] and sonuc["surum_no"] < 120000:
            sonuc["tamam"] = False
            sonuc["hata"] = (
                f"PostgreSQL 12 veya ustu gerekli (bulunan: "
                f"{sonuc['surum']})")
    except psycopg2.OperationalError as e:
        m = str(e).strip()
        # Ham psycopg2 metni kullaniciya gosterilmez; sihirbazda
        # "connection to server at ... FATAL" gibi bir yigin izi degil,
        # ne yapmasi gerektigini soyleyen tek satir gorunur.
        sonuc["hata"] = _hata_sadelestir(e)
        # "database does not exist" ayirt edilmeli: sihirbaz olusturma
        # teklif edebilir.
        if "does not exist" in m.lower() and "database" in m.lower():
            sonuc["veritabani_var"] = False
    except Exception as e:                            # pragma: no cover
        sonuc["hata"] = _hata_sadelestir(e)
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:
                pass
    return sonuc


def veritabani_olustur(host, port, veritabani, kullanici, sifre,
                       ssl="") -> dict:
    """Verilen veritabanini olusturur (yoksa).

    `postgres` bakim veritabanina baglanip `CREATE DATABASE` calistirir.
    `CREATE DATABASE` islem blogu icinde CALISMAZ; autocommit gerekir.
    """
    sonuc = {"tamam": False, "hata": ""}
    if not VAR:
        sonuc["hata"] = "psycopg2 kurulu degil"
        return sonuc
    con = None
    try:
        con = psycopg2.connect(
            host=str(host or "127.0.0.1"), port=int(port or 5432),
            dbname="postgres", user=str(kullanici or ""),
            password=str(sifre or ""),
            sslmode=str(ssl) if ssl else "prefer",
            connect_timeout=BAGLANTI_ZAMAN_ASIMI,
        )
        con.set_isolation_level(
            psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        im = con.cursor()
        im.execute("SELECT 1 FROM pg_database WHERE datname=%s",
                   (str(veritabani),))
        if im.fetchone():
            sonuc["tamam"] = True
            return sonuc
        # Veritabani adi parametre olarak gecirilemez; kimlik olarak
        # kacirilmalidir (SQL enjeksiyonu onlemi).
        ad = psycopg2.extensions.quote_ident(str(veritabani), con)
        im.execute(f"CREATE DATABASE {ad}")
        sonuc["tamam"] = True
    except Exception as e:
        sonuc["hata"] = f"{type(e).__name__}: {e}"
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:
                pass
    return sonuc
