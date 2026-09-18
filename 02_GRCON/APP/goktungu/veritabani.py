# -*- coding: utf-8 -*-
"""Merkezi SQLite veritabani (gcs.db).

Kullanicilar, baglantilar, rotalar, kameralar ve lokasyonlar tek bir
WAL-modlu SQLite dosyasinda tutulur.  Var olan JSON dosyalarindan ilk
calistirmada otomatik tasima yapilir; JSON dosyalari korunur.

Sifre guvenligi
---------------
Sifreler   ``sha256:<16-bayt-hex-tuz>:<64-bayt-hex-hash>``   biciminde
saklanir.  Eski duz-metin sifreler ilk basarili girisde otomatik olarak
hashli bicime donusturulur.
"""
import base64
import hashlib
import json
import os
import secrets
import sqlite3
import threading

from . import pg as _pg
from .sabitler import _veri_yolu

# v2.4.52: gcs.db artik VERI kokunde (eski yapida proje kokunde).
# Birincil depo v2.4.51'den beri PostgreSQL'dir; bu dosya yalnizca
# goc kaynagi ve yedek olarak okunur. `_veri_yolu` gecis kurali
# sayesinde eski konumdaki mevcut `gcs.db` de bulunur — aksi halde
# program BOS bir veritabani gorur ve kullanici tum ucus gecmisini
# kaybettigini sanar.
DOSYA = _veri_yolu("gcs.db")


# ------------------------------------------------------------------
# v2.4.24: Baglanti havuzu (is parcasi basina KALICI baglanti)
# ------------------------------------------------------------------
# KOK NEDEN (olculdu, bkz. BULGU_DISK_HATASI.md):
#   `with sqlite3.connect(...) as con:` deyimi yalnizca ISLEMI kapatir,
#   BAGLANTIYI KAPATMAZ. Eski kod her cagrida yeni baglanti aciyor ve
#   close() hic cagrilmiyordu -> dosya taniticisi sizintisi.
#   Olcum: 200 cagri sonrasi fd 5 -> 406. Tanitici tukendiginde SQLite
#   "unable to open database file" verir; kullanicinin gordugu "disk
#   hatasi" budur. Windows'ta sinir cok daha dusuk (512/8192).
#   Ayrica timeout verilmedigi icin (varsayilan 5 sn) esanli yazmada
#   240 yazmanin 238'i "database is locked" ile dustu (150 sn).
#
# COZUM: is parcasi basina TEK kalici baglanti. Ayni is parcasindan
#   yapilan tum cagrilar ayni baglantiyi kullanir; `with` blogu
#   islemi kapatir ama baglanti acik kalir ve YENIDEN KULLANILIR.
#
# GUVENLIK NOTU: bu tasarim yalnizca IC ICE `with baglanti()` kullanimi
#   YOKSA guvenlidir; ic ice kullanimda ic blok cikisi dis blogun
#   islemini de commit eder. `tani_ic_ice_baglanti.py` ile tum kod
#   tabani tarandi: 84 fonksiyon baglanti() kullaniyor, ic ice kullanim
#   SIFIR (ne dogrudan ne dolayli). Bu nedenle havuzlama guvenlidir.
#   Bu kosul degisirse tani betigi yeniden calistirilmalidir.

# Kilit bekleme suresi. Eski varsayilan 5 sn idi ve esanli yazmada
# yetmiyordu. SQLite kilidi ortalama milisaniyeler surer; 30 sn genis
# bir guvenlik payidir ve gercek bir kilitlenmede yine hata dondurur.
KILIT_ZAMAN_ASIMI = 30.0

# ------------------------------------------------------------------
# v2.4.25: telemetri semasi TEK KAYNAK
# ------------------------------------------------------------------
# Sema hem `tablolari_olustur()` hem `db_onarim.telemetri_sifirla()`
# tarafindan kullanilir. Iki yerde ayri ayri yazilirsa biri guncellenip
# digeri unutulur; bu sabit o riski ortadan kaldirir.
TELEMETRI_SEMA = """
    CREATE TABLE IF NOT EXISTS telemetri (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        dron_id    INTEGER NOT NULL,
        oturum_id  INTEGER,
        ts         REAL NOT NULL,
        lat        REAL,
        lon        REAL,
        irtifa     REAL,
        irtifa_msl REAL,
        hiz        REAL,
        dikey_hiz  REAL,
        yaw        REAL,
        roll       REAL,
        pitch      REAL,
        mod        TEXT NOT NULL DEFAULT '',
        armed      INTEGER NOT NULL DEFAULT 0,
        batarya_v  REAL,
        batarya_y  INTEGER,
        uydu       INTEGER,
        hdop       REAL,
        pilot_eposta TEXT NOT NULL DEFAULT '',
        pilot_isim   TEXT NOT NULL DEFAULT '',
        FOREIGN KEY (dron_id) REFERENCES dronlar(id)
            ON DELETE CASCADE,
        FOREIGN KEY (oturum_id) REFERENCES dron_oturumlari(id)
            ON DELETE SET NULL
    );
    CREATE INDEX IF NOT EXISTS ix_telemetri_dron_ts
        ON telemetri (dron_id, ts);
    CREATE INDEX IF NOT EXISTS ix_telemetri_oturum
        ON telemetri (oturum_id, ts);
    CREATE INDEX IF NOT EXISTS ix_telemetri_ts
        ON telemetri (ts);
"""

_yerel = threading.local()
_havuz_kilit = threading.Lock()
_havuz_kayit = []          # tum acik baglantilar (kapatma icin)

# ------------------------------------------------------------------
# v2.4.51: VERI DEPOSU KIPI
# ------------------------------------------------------------------
# "sqlite" | "postgresql"
#
# Olculdu: `baglanti()` 146 cagri yerinde kullaniliyor, `?` yer tutucu
# 256 yerde. Cagri yerlerini tek tek cevirmek yerine `baglanti()`
# PG kipinde `pg.baglanti()` dondurur; `pg.Baglanti` sinifi sqlite3
# API'sini taklit eder (bkz. pg.py, 44/0 olcum).
#
# v2.4.51'den itibaren VARSAYILAN KIP PostgreSQL'dir. SQLite yalnizca
# GOC KAYNAGI olarak okunur (`gecis.py`); yeni kurulumlarda hic
# kullanilmaz.
KIP = "postgresql"


def kip_ayarla(kip: str):
    """Veri deposu kipini belirler. "sqlite" | "postgresql"."""
    global KIP
    if kip not in ("sqlite", "postgresql"):
        raise ValueError(f"gecersiz kip: {kip}")
    KIP = kip


def pg_kipinde() -> bool:
    return KIP == "postgresql"


def _yeni_baglanti() -> sqlite3.Connection:
    """Tek bir yapilandirilmis SQLite baglantisi olusturur."""
    con = sqlite3.connect(
        DOSYA,
        check_same_thread=False,
        timeout=KILIT_ZAMAN_ASIMI,
    )
    con.row_factory = sqlite3.Row

    # journal_mode KALICI bir dosya ozelligidir; her baglantida
    # yeniden ayarlanmasi gereksizdir, ancak ilk olusturmada dosya
    # henuz WAL degilse gerekir. Baglanti basina BIR kez uygulanir.
    con.execute("PRAGMA journal_mode=WAL")

    # synchronous=NORMAL: WAL modunda dayanikliligi korur (islem
    # butunlugu WAL ile garanti), yalnizca checkpoint aninda fsync
    # yapar. FULL her islemde fsync yapiyordu -> yazma yavasligi.
    # Guc kesintisinde son birkac islem kaybedilebilir; telemetri icin
    # kabul edilebilir, ayrica dakikalik dosya tamponu yedek saglar.
    con.execute("PRAGMA synchronous=NORMAL")

    # WAL dosyasinin sinirsiz buyumesini engeller (~4 MB).
    con.execute("PRAGMA wal_autocheckpoint=1000")

    # Kilit bekleme suresini SQLite tarafinda da uygula (timeout
    # parametresi yalnizca Python katmanini baglar).
    con.execute(f"PRAGMA busy_timeout={int(KILIT_ZAMAN_ASIMI * 1000)}")

    con.execute("PRAGMA foreign_keys=ON")
    return con


def baglanti():
    """Bu is parcasina ait KALICI veritabani baglantisini dondurur.

    v2.4.51: PG kipinde `pg.baglanti()` dondurur. Donen nesne sqlite3
    `Connection` API'sini taklit eder; 146 cagri yerinin hicbiri
    degistirilmek zorunda degildir.
    """
    if KIP == "postgresql":
        return _pg.baglanti()
    return _sqlite_baglanti()


def _sqlite_baglanti() -> sqlite3.Connection:
    """Bu is parcasina ait KALICI SQLite baglantisini dondurur.

    Imza ve donus tipi eski surumle aynidir; 123 cagri yerinin
    hicbiri degistirilmek zorunda degildir. Fark: her cagrida yeni
    baglanti ACILMAZ, ayni baglanti yeniden kullanilir.

    `with baglanti() as con:` deseni calismaya devam eder; blok
    cikisinda islem commit/rollback edilir, baglanti acik kalir.
    """
    con = getattr(_yerel, "con", None)
    if con is not None:
        # Baglantinin hala kullanilabilir oldugunu dogrula. Disk
        # hatasi, dosya silinmesi veya harici kapatma sonrasi olu
        # baglantiyi yeniden kullanmak sessiz basarisizlik uretir.
        try:
            con.execute("SELECT 1")
            return con
        except sqlite3.Error:
            try:
                con.close()
            except sqlite3.Error:
                pass
            with _havuz_kilit:
                if con in _havuz_kayit:
                    _havuz_kayit.remove(con)
            _yerel.con = None

    con = _yeni_baglanti()
    _yerel.con = con
    with _havuz_kilit:
        _havuz_kayit.append(con)
    return con


def baglanti_kapat():
    """Bu is parcasinin baglantisini kapatir.

    v2.4.51: PG kipinde `pg.baglanti_kapat()` cagrilir.
    """
    if KIP == "postgresql":
        return _pg.baglanti_kapat()
    return _sqlite_baglanti_kapat()


def _sqlite_baglanti_kapat():
    """SQLite: bu is parcasinin baglantisini kapatir.

    Kisa omurlu is parcaciklari (ornegin istek basina thread) icin
    cagrilmalidir; aksi halde baglanti is parcasi olduktan sonra da
    havuz kaydinda kalir.
    """
    con = getattr(_yerel, "con", None)
    if con is None:
        return
    try:
        con.close()
    except sqlite3.Error:
        pass
    with _havuz_kilit:
        if con in _havuz_kayit:
            _havuz_kayit.remove(con)
    _yerel.con = None


def tum_baglantilari_kapat(zorla: bool = False):
    """Havuz kaydini bosaltir.

    v2.4.51: PG kipinde `pg.tum_baglantilari_kapat()` cagrilir.
    SQLite'taki SIGSEGV riski psycopg2'de YOKTUR (baglanti kapatmak
    Python seviyesinde `InterfaceError` uretir, surec olmez).
    """
    if KIP == "postgresql":
        _pg.tum_baglantilari_kapat()
        return 0
    return _sqlite_tum_baglantilari_kapat(zorla)


def _sqlite_tum_baglantilari_kapat(zorla: bool = False):
    """SQLite: havuz kaydini bosaltir. VARSAYILAN OLARAK KAPATMAZ.

    ## v2.4.25 KRITIK UYARI — SIGSEGV riski

    Bu fonksiyonun ONCEKI hali, baska is parcaciklarinin baglantilarini
    `close()` ediyordu. Olculdu ve KANITLANDI: bir is parcasi baglantiyi
    kullanirken baska bir is parcasi onu kapatirsa surec SIGSEGV ile
    oler (C seviyesi bellek ihlali; Python istisnasi DEGIL, `try/except`
    YAKALAMAZ).

    Yeniden uretim (`tani_bozulma_kos.sh`, senaryo 2):

        senaryo 2 (yazma sirasinda tum_baglantilari_kapat)
        cikis kodu: 139  (SIGSEGV)
        integrity : ok   (veritabani BOZULMADI, ama surec coktu)

    Canli ucusta bu, GCS'nin aniden kapanmasi anlamina gelir.

    ## Varsayilan davranis (guvenli)

    Baglantilar KAPATILMAZ, yalnizca havuz kaydi bosaltilir ve CAGIRAN
    is parcasinin kendi baglantisi kapatilir. Diger is parcaciklari
    baglantilarini `baglanti()` icindeki `SELECT 1` canlilik denetimi
    sayesinde KENDILERI yeniler (satir 152). Boylece her `close()`
    islemi, baglantinin SAHIBI olan is parcasinda gerceklesir.

    ## `zorla=True`

    Yalnizca surec KAPANIRKEN ve diger is parcaciklarinin durdugu
    KESIN oldugunda kullanilmalidir.

    Donus: havuz kaydindan cikarilan baglanti sayisi.
    """
    with _havuz_kilit:
        kayit = list(_havuz_kayit)
        _havuz_kayit.clear()

    kendi = getattr(_yerel, "con", None)
    for con in kayit:
        # Kendi baglantimizi her zaman kapatabiliriz (sahibi biziz).
        if con is kendi or zorla:
            try:
                con.close()
            except sqlite3.Error:
                pass
    _yerel.con = None
    return len(kayit)


def havuz_durumu():
    """Tanilama: acik baglanti sayisi."""
    if KIP == "postgresql":
        d = _pg.havuz_durumu()
        return {"acik_baglanti": d.get("acik", 0),
                "zaman_asimi": _pg.DEYIM_ZAMAN_ASIMI_MS / 1000.0,
                "kip": "postgresql"}
    with _havuz_kilit:
        return {"acik_baglanti": len(_havuz_kayit),
                "zaman_asimi": KILIT_ZAMAN_ASIMI,
                "kip": "sqlite"}


def tablolari_olustur():
    """Eksik tablolari olusturur; var olanlara dokunmaz (idempotent)."""
    with baglanti() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS kullanicilar (
                eposta      TEXT PRIMARY KEY COLLATE NOCASE,
                ad_soyad    TEXT NOT NULL DEFAULT '',
                unvan       TEXT NOT NULL DEFAULT '',
                rol         TEXT NOT NULL DEFAULT 'kullanici',
                sifre       TEXT NOT NULL DEFAULT '',
                avatar      TEXT NOT NULL DEFAULT '',
                aktif       INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS baglantilar (
                id          INTEGER PRIMARY KEY,
                isim        TEXT NOT NULL,
                tur         TEXT NOT NULL,
                port        TEXT NOT NULL,
                baud        INTEGER,
                host        TEXT,
                -- v2.4.142: Eski satırlar güvenli varsayımla ArduPilot
                -- kabul edilir; DJI kaydı uygulama katmanında zorunlu dji olur.
                ucus_yazilimi TEXT NOT NULL DEFAULT 'ardupilot'
            );

            CREATE TABLE IF NOT EXISTS rotalar (
                id          INTEGER PRIMARY KEY,
                isim        TEXT NOT NULL,
                irtifa      REAL NOT NULL DEFAULT 50.0,
                hiz         REAL NOT NULL DEFAULT 10.0,
                gorunur     INTEGER NOT NULL DEFAULT 1,
                noktalar    TEXT NOT NULL DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS kameralar (
                id          INTEGER PRIMARY KEY,
                isim        TEXT NOT NULL,
                protokol    TEXT NOT NULL,
                url         TEXT NOT NULL
            );

            -- v2.4.191: coklu elektro-optik (eo_cihazlar.py).
            CREATE TABLE IF NOT EXISTS eo_cihazlar (
                id              INTEGER PRIMARY KEY,
                isim            TEXT NOT NULL DEFAULT 'M50',
                tur             TEXT NOT NULL DEFAULT 'm50',
                ip              TEXT NOT NULL DEFAULT '',
                port            INTEGER NOT NULL DEFAULT 39020,
                lat             REAL,
                lon             REAL,
                kopru_ornek_id  INTEGER,
                otomatik_baglan INTEGER NOT NULL DEFAULT 1,
                firma_id        INTEGER
            );

            -- v2.4.190: coklu radar (radarlar.py). Eski tek radar ayari
            -- ilk acilista 'Radar 1' olarak tasinir.
            CREATE TABLE IF NOT EXISTS radarlar (
                id              INTEGER PRIMARY KEY,
                isim            TEXT NOT NULL DEFAULT 'Radar',
                ip              TEXT NOT NULL DEFAULT '',
                port            INTEGER NOT NULL DEFAULT 5001,
                lat             REAL,
                lon             REAL,
                merkez_yonu     REAL NOT NULL DEFAULT 0.0,
                kopru_ornek_id  INTEGER,
                otomatik_baglan INTEGER NOT NULL DEFAULT 0,
                firma_id        INTEGER
            );

            -- v2.4.243 (IS137): dron Python makrolari
            CREATE TABLE IF NOT EXISTS makrolar (
                id              INTEGER PRIMARY KEY,
                ad              TEXT NOT NULL DEFAULT 'Makro',
                aciklama        TEXT NOT NULL DEFAULT '',
                kod             TEXT NOT NULL DEFAULT '',
                sure_sn         INTEGER NOT NULL DEFAULT 3600,
                guncelleme_ts   REAL,
                firma_id        INTEGER
            );

            CREATE TABLE IF NOT EXISTS lokasyonlar (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ad          TEXT NOT NULL,
                lat         REAL NOT NULL,
                lon         REAL NOT NULL,
                firma_id    INTEGER
            );

            -- v2.1.7: rol/izin sistemi
            CREATE TABLE IF NOT EXISTS roller (
                ad          TEXT PRIMARY KEY COLLATE NOCASE,
                izinler     TEXT NOT NULL DEFAULT '{}'
            );

            -- v2.1.7: pilot etiketli kalici islem kaydi
            CREATE TABLE IF NOT EXISTS pilot_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          REAL NOT NULL,
                eposta      TEXT NOT NULL DEFAULT '',
                isim        TEXT NOT NULL DEFAULT '',
                kategori    TEXT NOT NULL DEFAULT '',
                islem       TEXT NOT NULL DEFAULT '',
                detay       TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS ix_pilot_log_eposta
                ON pilot_log (eposta, ts DESC);

            -- v2.1.7: merkezi uyari sistemi
            CREATE TABLE IF NOT EXISTS uyarilar (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          REAL NOT NULL,
                eposta      TEXT NOT NULL DEFAULT '',
                kategori    TEXT NOT NULL DEFAULT '',
                mesaj       TEXT NOT NULL DEFAULT '',
                okundu      INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS ix_uyarilar_eposta
                ON uyarilar (eposta, okundu, ts DESC);

            -- v2.4.32: pilotlar arasi canli mesajlasma
            -- Not: `uyarilar` tablosu tek yonludur (gonderen yok);
            -- sohbet icin ayri tablo gerekir.
            CREATE TABLE IF NOT EXISTS mesajlar (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          REAL NOT NULL,
                gonderen    TEXT NOT NULL DEFAULT '' COLLATE NOCASE,
                alici       TEXT NOT NULL DEFAULT '' COLLATE NOCASE,
                metin       TEXT NOT NULL DEFAULT '',
                okundu      INTEGER NOT NULL DEFAULT 0,
                okundu_ts   REAL
            );
            -- Okunmamis sayaci icin (header ikonu her giriste sorar)
            CREATE INDEX IF NOT EXISTS ix_mesajlar_alici
                ON mesajlar (alici, okundu, ts DESC);
            -- Sohbet gecmisi icin (iki yonlu sorgu)
            CREATE INDEX IF NOT EXISTS ix_mesajlar_sohbet
                ON mesajlar (gonderen, alici, ts DESC);

            -- v2.3.0: program ayarlari (gcs_ayarlar.json yerine)
            CREATE TABLE IF NOT EXISTS ayarlar (
                anahtar     TEXT PRIMARY KEY,
                deger       TEXT NOT NULL DEFAULT 'null'
            );

            -- v2.3.0: kayitli dron isimleri (gcs_dronlar.json yerine)
            CREATE TABLE IF NOT EXISTS dron_kayitlari (
                uid         TEXT PRIMARY KEY,
                veri        TEXT NOT NULL DEFAULT '{}'
            );

            -- v2.3.0: ucus gecmisi dron kayitlari
            --         (gcs_ucus_gecmisi/dronlar.json yerine)
            CREATE TABLE IF NOT EXISTS ucus_dronlari (
                anahtar     TEXT PRIMARY KEY,
                renk        TEXT NOT NULL DEFAULT '',
                isim        TEXT NOT NULL DEFAULT '',
                sysid       INTEGER,
                uid         TEXT NOT NULL DEFAULT ''
            );

            -- v2.3.0: ucus kayitlari + telemetri izleri
            --         (gcs_ucus_gecmisi/ucus_*.json yerine)
            CREATE TABLE IF NOT EXISTS ucuslar (
                id          TEXT PRIMARY KEY,
                anahtar     TEXT NOT NULL DEFAULT '',
                sysid       INTEGER,
                isim        TEXT NOT NULL DEFAULT '',
                baslangic   REAL NOT NULL DEFAULT 0,
                bitis       REAL,
                sure        REAL NOT NULL DEFAULT 0,
                nokta       INTEGER NOT NULL DEFAULT 0,
                max_irtifa  REAL NOT NULL DEFAULT 0,
                pilotlar    TEXT NOT NULL DEFAULT '[]',
                noktalar    TEXT NOT NULL DEFAULT '[]'
            );
            CREATE INDEX IF NOT EXISTS ix_ucuslar_anahtar
                ON ucuslar (anahtar, baslangic DESC);

            -- v2.3.0: giris/oturum kaydi (tum login denemeleri +
            --         istemci baglanti ayrintilari)
            CREATE TABLE IF NOT EXISTS giris_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          REAL NOT NULL,
                eposta      TEXT NOT NULL DEFAULT '',
                isim        TEXT NOT NULL DEFAULT '',
                basarili    INTEGER NOT NULL DEFAULT 0,
                sebep       TEXT NOT NULL DEFAULT '',
                ip          TEXT NOT NULL DEFAULT '',
                port        INTEGER,
                yerel_ip    TEXT NOT NULL DEFAULT '',
                user_agent  TEXT NOT NULL DEFAULT '',
                origin      TEXT NOT NULL DEFAULT '',
                host        TEXT NOT NULL DEFAULT '',
                forwarded   TEXT NOT NULL DEFAULT '',
                detay       TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS ix_giris_log_ts
                ON giris_log (ts DESC);
            CREATE INDEX IF NOT EXISTS ix_giris_log_eposta
                ON giris_log (eposta, ts DESC);

            -- v2.4.0: AI islem sunuculari (NVIDIA/CPU isciler)
            CREATE TABLE IF NOT EXISTS ai_sunucular (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ad          TEXT NOT NULL,
                tip         TEXT NOT NULL DEFAULT 'cpu',
                host        TEXT NOT NULL DEFAULT '127.0.0.1',
                port        INTEGER NOT NULL DEFAULT 8900,
                kapasite    INTEGER NOT NULL DEFAULT 4,
                aktif       INTEGER NOT NULL DEFAULT 1,
                notlar      TEXT NOT NULL DEFAULT '',
                -- v2.4.45: SSH ile uzaktan baslatma
                ssh_kullanici TEXT NOT NULL DEFAULT '',
                ssh_port      INTEGER NOT NULL DEFAULT 22,
                ssh_anahtar   TEXT NOT NULL DEFAULT '',
                ssh_komut     TEXT NOT NULL DEFAULT '',
                ssh_sifre     TEXT NOT NULL DEFAULT '',
                -- v2.4.56: cok firmali merkez + kopru gruplamasi
                -- firma_id NULL  -> lokal kurulum (suzgec devre disi)
                -- kopru_ornek_id -> AI bilgisayarinin bagli oldugu
                --   kopru; NULL ise merkezden dogrudan yoklanir
                firma_id       INTEGER,
                kopru_ornek_id INTEGER
            );

            -- v2.4.0: kutuphane - kisiler
            CREATE TABLE IF NOT EXISTS kisiler (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ad          TEXT NOT NULL,
                seviye      TEXT NOT NULL DEFAULT 'GUVENLI',
                notlar      TEXT NOT NULL DEFAULT '',
                olusturma   REAL NOT NULL DEFAULT 0
            );

            -- v2.4.0: kisi yuz kayitlari (foto + embedding)
            CREATE TABLE IF NOT EXISTS kisi_yuzler (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                kisi_id     INTEGER NOT NULL,
                dosya       TEXT NOT NULL DEFAULT '',
                embedding   BLOB,
                olusturma   REAL NOT NULL DEFAULT 0,
                FOREIGN KEY (kisi_id) REFERENCES kisiler(id)
                    ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS ix_kisi_yuzler_kisi
                ON kisi_yuzler (kisi_id);

            -- v2.4.0: kutuphane - araclar
            CREATE TABLE IF NOT EXISTS araclar (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                plaka       TEXT NOT NULL,
                marka       TEXT NOT NULL DEFAULT '',
                model       TEXT NOT NULL DEFAULT '',
                renk        TEXT NOT NULL DEFAULT '',
                seviye      TEXT NOT NULL DEFAULT 'GUVENLI',
                notlar      TEXT NOT NULL DEFAULT '',
                olusturma   REAL NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS ix_araclar_plaka
                ON araclar (plaka);

            -- v2.4.0: AI tespit gecmisi (yuz/plaka; kisi_id/arac_id
            --         NULL ise kayitsiz tespit)
            CREATE TABLE IF NOT EXISTS ai_tespitler (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          REAL NOT NULL,
                kamera_id   INTEGER,
                sunucu_id   INTEGER,
                tur         TEXT NOT NULL DEFAULT 'yuz',
                kisi_id     INTEGER,
                arac_id     INTEGER,
                etiket      TEXT NOT NULL DEFAULT '',
                seviye      TEXT NOT NULL DEFAULT '',
                guven       REAL NOT NULL DEFAULT 0,
                foto        TEXT NOT NULL DEFAULT '',
                klip        TEXT NOT NULL DEFAULT '',
                incelendi   INTEGER NOT NULL DEFAULT 0,
                -- v2.4.2: tespit aninda kameranin bagli oldugu dronun
                --         aktif ucus kaydi (ucuslar.id, or.
                --         20260729_141530_D1); bos = ucus disi tespit
                ucus_id     TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS ix_ai_tespitler_ts
                ON ai_tespitler (ts DESC);
            -- NOT: ix_ai_tespitler_ucus indeksi _sema_guncelle()'de
            -- olusturulur; burada olsaydi eski kurulumlarda ucus_id
            -- sutunu eklenmeden once calisip hata verirdi.
            CREATE INDEX IF NOT EXISTS ix_ai_tespitler_kayitsiz
                ON ai_tespitler (tur, kisi_id, arac_id, ts DESC);

            -- v2.4.17: dron parametre onbellegi (tam okuma sonuclari)
            -- sysid basina tek satir; parametreler JSON sozlugu.
            -- v2.4.21: ARTIK YAZILMIYOR. Icerigi dron_parametreler
            -- tablosuna tasindi; param_cache_* fonksiyonlari geriye
            -- uyumluluk icin yeni tabloyu okur/yazar (adapter).
            CREATE TABLE IF NOT EXISTS param_cache (
                sysid       INTEGER PRIMARY KEY,
                parametreler TEXT NOT NULL DEFAULT '{}',
                toplam      INTEGER NOT NULL DEFAULT 0,
                okuma_ts    REAL NOT NULL DEFAULT 0
            );

            -- ==========================================================
            -- v2.4.21: NORMALIZE DRON VERI MODELI
            -- ----------------------------------------------------------
            -- dronlar            : benzersiz kimlik + ilk kayit izi
            -- dron_oturumlari    : her baglanti oturumu (bagli sure)
            -- dron_parametreler  : dron basina ad/deger (guncel)
            -- dron_parametre_gecmisi : her degisiklik (eski -> yeni)
            -- telemetri          : kesintisiz telemetri kaydi
            -- v_ucuslar (VIEW)   : telemetriden akilli ucus tespiti
            -- ==========================================================

            -- Benzersiz dron kimlik kaydi. uid: donanim UID (hex) veya
            -- turetilmis parmak izi ('fp:...'). Daha once kayitli
            -- degilse ilk baglantida olusur; ilk_kayit_ts ve
            -- kaydeden_eposta bir daha degismez.
            CREATE TABLE IF NOT EXISTS dronlar (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                uid             TEXT NOT NULL UNIQUE,
                uid_kaynak      TEXT NOT NULL DEFAULT 'turetilmis',
                isim            TEXT NOT NULL DEFAULT '',
                renk            TEXT NOT NULL DEFAULT '',
                sysid           INTEGER,
                arac_tipi       INTEGER NOT NULL DEFAULT 0,
                arac_sinifi     TEXT NOT NULL DEFAULT '',
                otopilot        TEXT NOT NULL DEFAULT '',
                firmware        TEXT NOT NULL DEFAULT '',
                ilk_kayit_ts    REAL NOT NULL DEFAULT 0,
                kaydeden_eposta TEXT NOT NULL DEFAULT '',
                kaydeden_isim   TEXT NOT NULL DEFAULT '',
                son_gorulme_ts  REAL NOT NULL DEFAULT 0,
                notlar          TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS ix_dronlar_sysid
                ON dronlar (sysid);

            -- Baglanti oturumu: dron gorunur oldugu andan telemetrisi
            -- kesilene kadar. Telemetri kayitlari bu oturuma baglanir.
            CREATE TABLE IF NOT EXISTS dron_oturumlari (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                dron_id      INTEGER NOT NULL,
                baglanti_id  INTEGER,
                sysid        INTEGER,
                baslangic_ts REAL NOT NULL DEFAULT 0,
                bitis_ts     REAL,
                pilot_eposta TEXT NOT NULL DEFAULT '',
                pilot_isim   TEXT NOT NULL DEFAULT '',
                pilotlar     TEXT NOT NULL DEFAULT '[]',
                FOREIGN KEY (dron_id) REFERENCES dronlar(id)
                    ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS ix_dron_oturum_dron
                ON dron_oturumlari (dron_id, baslangic_ts DESC);

            -- Dron basina guncel parametre degerleri. Sonraki
            -- baglantilarda yeni ad eklenir, var olan deger guncellenir.
            CREATE TABLE IF NOT EXISTS dron_parametreler (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                dron_id        INTEGER NOT NULL,
                ad             TEXT NOT NULL,
                deger          REAL,
                tip            INTEGER NOT NULL DEFAULT 0,
                ilk_okuma_ts   REAL NOT NULL DEFAULT 0,
                guncelleme_ts  REAL NOT NULL DEFAULT 0,
                kaynak         TEXT NOT NULL DEFAULT 'dron',
                UNIQUE (dron_id, ad),
                FOREIGN KEY (dron_id) REFERENCES dronlar(id)
                    ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS ix_dron_param_dron
                ON dron_parametreler (dron_id, ad);

            -- Her parametre degisikliginin denetim kaydi: eski -> yeni,
            -- tarih ve degisikligi yapan kullanici.
            CREATE TABLE IF NOT EXISTS dron_parametre_gecmisi (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                dron_id     INTEGER NOT NULL,
                param_id    INTEGER,
                ad          TEXT NOT NULL,
                eski_deger  REAL,
                yeni_deger  REAL,
                ts          REAL NOT NULL DEFAULT 0,
                kullanici_eposta TEXT NOT NULL DEFAULT '',
                kullanici_isim   TEXT NOT NULL DEFAULT '',
                kaynak      TEXT NOT NULL DEFAULT 'dron',
                FOREIGN KEY (dron_id) REFERENCES dronlar(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (param_id) REFERENCES dron_parametreler(id)
                    ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS ix_param_gecmis_dron
                ON dron_parametre_gecmisi (dron_id, ts DESC);
            CREATE INDEX IF NOT EXISTS ix_param_gecmis_ad
                ON dron_parametre_gecmisi (dron_id, ad, ts DESC);

            -- v2.4.41: KALKIS ONCESI KONTROL LISTESI KAYITLARI
            -- Pilot her TAKEOFF'ta listeyi doldurur; kayit YAZILAMAZSA
            -- kalkis komutu gonderilMEZ. Bu yuzden kayit tablosu
            -- denetim (audit) niteligindedir ve silinmez.
            -- Tarih/saat ve pilot kimligi SUNUCUDA damgalanir; istemci
            -- gonderemez (saat kaydirma / kimlik taklidi engeli).
            CREATE TABLE IF NOT EXISTS kalkis_kontrolleri (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                dron_id      INTEGER,
                sysid        INTEGER NOT NULL DEFAULT 0,
                oturum_id    INTEGER,
                ts           REAL NOT NULL DEFAULT 0,
                yerel_saat   TEXT NOT NULL DEFAULT '',
                pilot_eposta TEXT NOT NULL DEFAULT '',
                pilot_isim   TEXT NOT NULL DEFAULT '',
                arac_tipi    INTEGER NOT NULL DEFAULT 0,
                arac_tipi_ad TEXT NOT NULL DEFAULT '',
                hedef_irtifa REAL NOT NULL DEFAULT 0,
                madde_sayisi INTEGER NOT NULL DEFAULT 0,
                evet_sayisi  INTEGER NOT NULL DEFAULT 0,
                tam_onay     INTEGER NOT NULL DEFAULT 0,
                takeoff_gonderildi INTEGER NOT NULL DEFAULT 0,
                takeoff_hata TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (dron_id) REFERENCES dronlar(id)
                    ON DELETE SET NULL,
                FOREIGN KEY (oturum_id) REFERENCES dron_oturumlari(id)
                    ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS ix_kalkis_kontrol_dron
                ON kalkis_kontrolleri (dron_id, ts DESC);
            CREATE INDEX IF NOT EXISTS ix_kalkis_kontrol_ts
                ON kalkis_kontrolleri (ts DESC);
            CREATE INDEX IF NOT EXISTS ix_kalkis_kontrol_pilot
                ON kalkis_kontrolleri (pilot_eposta, ts DESC);

            -- Hangi soruya ne cevap verildigi. Soru metni de saklanir:
            -- yazilim guncellenip soru metni degisse bile ESKI kayit
            -- pilotun O GUN gordugu metni korur (denetim gerekliligi).
            CREATE TABLE IF NOT EXISTS kalkis_kontrol_maddeleri (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                kontrol_id INTEGER NOT NULL,
                sira       INTEGER NOT NULL DEFAULT 0,
                anahtar    TEXT NOT NULL DEFAULT '',
                soru       TEXT NOT NULL DEFAULT '',
                grup       TEXT NOT NULL DEFAULT '',
                kaynak     TEXT NOT NULL DEFAULT '',
                zorunlu    INTEGER NOT NULL DEFAULT 1,
                cevap      INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (kontrol_id)
                    REFERENCES kalkis_kontrolleri(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS ix_kalkis_madde_kontrol
                ON kalkis_kontrol_maddeleri (kontrol_id, sira);

            -- KESINTISIZ telemetri kaydi: dron bagli oldugu surece
            -- (takeoff/land beklenmez). Ucuslar VIEW ile tespit edilir.
            -- Sema TELEMETRI_SEMA sabitinde (tek kaynak); v2.4.25'te
            -- db_onarim.py de ayni sabiti kullanir.
        """ + TELEMETRI_SEMA + """

            -- ==========================================================
            -- v2.4.51: DOSYADAN VERITABANINA TASINAN DURUMLAR
            -- ==========================================================
            -- Kullanici istegi: "fiziksel dosyalarda tuttugun tamponlari
            -- ve ayar dosyalarini da PostgreSQL'e tasiyalim".
            --
            -- `veri/calisma.json` BILINCLI OLARAK DISARIDA BIRAKILDI:
            -- kiosk betigi (v2.4.49) portu sunucu AYAKTA DEGILKEN okur;
            -- veritabanina tasinsa acilista baglanamaz ve iki ekran
            -- duzeni kirilir.

            -- Gorev surdurme kaydi (onceden veri/gorev_durum.json).
            -- Batarya degisiminde dron offline olup donunce gorev
            -- kaldigi yerden surer; bu kayit o surdurmeyi saglar.
            -- ANAHTAR `sysid`'DIR, `dron_uid` DEGIL.
            -- Olculdu (dene_faz5.py): anahtar `dron_uid` iken iki dron
            -- ayni satira coktu ve BIRININ surdurme kaydi silindi.
            -- Sahada sonucu: iki dron ayni anda gorevdeyken batarya
            -- degisiminden sonra biri gorevi KALDIGI YERDEN SURDURMEZ.
            -- Calisma aninda dronu tanimlayan deger `sysid`'dir;
            -- `surdurulebilir` sozlugunun anahtari da odur.
            CREATE TABLE IF NOT EXISTS gorev_durum (
                sysid      INTEGER PRIMARY KEY,
                dron_uid   TEXT NOT NULL DEFAULT '',
                kayit      TEXT NOT NULL DEFAULT '{}',
                ts         REAL NOT NULL DEFAULT 0
            );

            -- Telemetri tamponu KAYIT DEFTERI.
            -- Ham ornekler DISKTE kalir (olculdu: PG kesintisinde
            -- dogrudan yazma ucusun %50'sini kaybediyor, tampon %0).
            -- Bu tablo hangi dosyanin ne zaman aktarildigini izler;
            -- merkezi gorunurluk saglar, dayanikliligi bozmaz.
            CREATE TABLE IF NOT EXISTS telemetri_tampon_kayit (
                dosya      TEXT PRIMARY KEY,
                satir      INTEGER NOT NULL DEFAULT 0,
                durum      TEXT NOT NULL DEFAULT '',
                deneme     INTEGER NOT NULL DEFAULT 0,
                hata       TEXT NOT NULL DEFAULT '',
                ts         REAL NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS ix_tampon_kayit_ts
                ON telemetri_tampon_kayit (ts DESC);

            -- Harita karo onbellegi (JPEG/PNG ikili veri).
            -- Karolar GEOMETRI DEGIL, goruntudur -> PostGIS ilgisiz.
            -- Kullanim karari OLCUME baglidir (bkz. dene_karo.py).
            CREATE TABLE IF NOT EXISTS harita_karo (
                kaynak     TEXT NOT NULL,
                z          INTEGER NOT NULL,
                x          INTEGER NOT NULL,
                y          INTEGER NOT NULL,
                veri       BLOB,
                bayt       INTEGER NOT NULL DEFAULT 0,
                ts         REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (kaynak, z, x, y)
            );
        """)
    _sema_guncelle()
    _gorunumleri_olustur()
    _varsayilan_roller()
    _varsayilan_ai_sunuculari()


# ==================================================================
# v2.4.21: AKILLI UCUS TESPITI (VIEW)
# ==================================================================
# Telemetri kesintisiz yazilir; ucuslar bu gorunumlerle tespit edilir.
#
# v_telemetri_isaretli : her ornege "ucusta mi" bayragi + yeni segment
#                        baslangici (gap > UCUS_BOSLUK sn) isareti
# v_telemetri_segment  : gaps-and-islands ile segment numarasi
# v_ucuslar            : segment ozetleri (eski "ucuslar" tablosunun
#                        yerini alir; ayni id bicimi uretir)
#
# Ucusta sayilma kosulu: armed=1 VE (irtifa > 1.5 m VEYA hiz > 1.5 m/s)
# Segment kesme esigi  : ardisik ucus ornekleri arasi > 10 sn bosluk
# Gecerli ucus         : >= 4 ornek VE >= 5 sn sure
UCUS_IRTIFA_ESIK = 1.5      # m
UCUS_HIZ_ESIK = 1.5         # m/s
UCUS_BOSLUK = 10.0          # s
UCUS_MIN_ORNEK = 4
UCUS_MIN_SURE = 5.0         # s


def _gorunumleri_olustur():
    """v2.4.21: ucus tespiti gorunumlerini (yeniden) olusturur.

    Gorunumler her acilista DROP + CREATE edilir; boylece esik
    degisiklikleri kurulumlara otomatik yansir.
    """
    with baglanti() as con:
        con.executescript(f"""
            DROP VIEW IF EXISTS v_ucuslar;
            DROP VIEW IF EXISTS v_telemetri_segment;
            DROP VIEW IF EXISTS v_telemetri_isaretli;

            -- 1) Her ornege ucus bayragi ve yeni segment isareti
            CREATE VIEW v_telemetri_isaretli AS
            SELECT
                t.id, t.dron_id, t.oturum_id, t.ts,
                t.lat, t.lon, t.irtifa, t.hiz, t.yaw,
                t.mod, t.armed, t.pilot_eposta, t.pilot_isim,
                CASE WHEN t.armed = 1
                      AND (COALESCE(t.irtifa, 0) > {UCUS_IRTIFA_ESIK}
                           OR COALESCE(t.hiz, 0) > {UCUS_HIZ_ESIK})
                     THEN 1 ELSE 0 END AS ucusta
            FROM telemetri t;

            -- 2) Gaps-and-islands: ucus orneklerini segmentlere ayir
            CREATE VIEW v_telemetri_segment AS
            SELECT
                i.*,
                SUM(i.yeni_segment) OVER (
                    PARTITION BY i.dron_id ORDER BY i.ts
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS segment_no
            FROM (
                SELECT
                    v.*,
                    CASE WHEN LAG(v.ts) OVER (
                              PARTITION BY v.dron_id ORDER BY v.ts)
                              IS NULL
                              OR (v.ts - LAG(v.ts) OVER (
                                  PARTITION BY v.dron_id ORDER BY v.ts))
                                 > {UCUS_BOSLUK}
                         THEN 1 ELSE 0 END AS yeni_segment
                FROM v_telemetri_isaretli v
                WHERE v.ucusta = 1
            ) i;

            -- 3) Segment ozetleri = tespit edilen ucuslar.
            -- id bicimi eski "ucuslar" tablosuyla ayni tutulur
            -- (ai_tespitler.ucus_id uyumu): YYYYMMDD_HHMMSS_D{{sysid}}
            CREATE VIEW v_ucuslar AS
            SELECT
                strftime('%Y%m%d_%H%M%S',
                         MIN(s.ts), 'unixepoch', 'localtime')
                    || '_D' || COALESCE(d.sysid, s.dron_id) AS id,
                s.dron_id,
                s.segment_no,
                d.uid              AS anahtar,
                d.isim             AS isim,
                d.sysid            AS sysid,
                d.renk             AS renk,
                MIN(s.ts)          AS baslangic,
                MAX(s.ts)          AS bitis,
                ROUND(MAX(s.ts) - MIN(s.ts), 1) AS sure,
                COUNT(*)           AS nokta,
                ROUND(MAX(COALESCE(s.irtifa, 0)), 1) AS max_irtifa,
                ROUND(MAX(COALESCE(s.hiz, 0)), 1)    AS max_hiz,
                ROUND(AVG(COALESCE(s.hiz, 0)), 2)    AS ort_hiz
            FROM v_telemetri_segment s
            JOIN dronlar d ON d.id = s.dron_id
            -- v2.4.51: d.* alanlari GROUP BY'a EKLENDI.
            -- SQLite gruplanmayan kolonu hosgoruyle kabul eder ve
            -- RASTGELE bir satirin degerini alir; PG standart uyumlu
            -- oldugu icin reddeder:
            --   GroupingError: column "d.sysid" must appear in the
            --   GROUP BY clause or be used in an aggregate function
            -- `d.id = s.dron_id` ve `d.id` birincil anahtar oldugundan
            -- bu alanlar dron basina TEK degerlidir; GROUP BY'a eklemek
            -- sonucu DEGISTIRMEZ, yalnizca belirsiz davranisi giderir.
            GROUP BY s.dron_id, s.segment_no,
                     d.uid, d.isim, d.sysid, d.renk
            HAVING COUNT(*) >= {UCUS_MIN_ORNEK}
               AND (MAX(s.ts) - MIN(s.ts)) >= {UCUS_MIN_SURE};
        """)


# ==================================================================
# v2.4.21: DRON KIMLIK KAYDI
# ==================================================================
def dron_kayit_al_veya_olustur(uid, *, uid_kaynak="turetilmis", isim="",
                               sysid=None, arac_tipi=0, arac_sinifi="",
                               otopilot="", firmware="", renk="",
                               kaydeden_eposta="", kaydeden_isim="",
                               firma_id=None):
    """UID icin dron kaydini dondurur; yoksa olusturur (idempotent).
    Daha once kayitliysa `ilk_kayit_ts`, `kaydeden_eposta` ve
    `kaydeden_isim` DEGISTIRILMEZ; yalnizca `son_gorulme_ts`, `sysid`
    ve bos olan tanimlayici alanlar tazelenir.
    Donus: (dron_id, yeni_mi)

    ## firma_id (v2.4.54) — YARIM KALMIS IZOLASYONUN TAMAMLANMASI

    Goc adim 25 `dronlar.firma_id` kolonunu ve `ix_dronlar_firma`
    indeksini ekledi, `firma_kosulu()` suzgeci de onu okuyor. Ancak
    YAZMA yolu hic baglanmamisti: merkezde bir dron ilk kez
    baglandiginda kayit `firma_id = NULL` olusuyordu.

    Suzgec `(firma_id IS NULL OR firma_id = ?)` bicimindedir; yani NULL
    kayitlar HER firmaya gorunur. Sonuc: A firmasinin dronu B firmasinin
    "Kayitli Dronlar" listesinde cikiyordu. Kolon vardi, indeks vardi,
    suzgec vardi — yalniz deger yoktu.

    Sahiplik BIR KEZ yazilir, sonra DEGISTIRILMEZ:

      - INSERT: kayit olusurken firma_id yazilir.
      - UPDATE: yalnizca `firma_id IS NULL` ise doldurulur.

    UPDATE'in kosullu olmasi kasitlidir. Ayni fiziksel arac bir baska
    firmaya baglanirsa sahipligi SESSIZCE devralmamalidir; aksi halde
    iki firma arasinda gidip gelen bir dron, her baglantida gecmis
    ucuslarini karsi tarafa acar. NULL kayitlarin doldurulmasi ise
    gereklidir: bu duzeltmeden ONCE olusmus kayitlar aksi halde sonsuza
    kadar herkese gorunur kalirdi.

    `firma_id=None` (lokal kurulum) davranisi DEGISTIRMEZ: kolon NULL
    kalir, suzgec de zaten devre disidir.
    """
    try:
        firma_id = int(firma_id) if firma_id else None
    except (TypeError, ValueError):
        firma_id = None
    firma_yaz = bool(firma_id) and firma_kolonu_var("dronlar")
    import time as _t
    uid = str(uid or "").strip()
    if not uid:
        return None, False
    simdi = _t.time()
    with baglanti() as con:
        r = con.execute(
            "SELECT id, isim, renk, otopilot, firmware, arac_sinifi"
            " FROM dronlar WHERE uid=?", (uid,)).fetchone()
        if r is not None:
            dron_id = int(r["id"])
            con.execute(
                "UPDATE dronlar SET son_gorulme_ts=?, sysid=COALESCE(?,"
                " sysid), arac_tipi=CASE WHEN ?>0 THEN ? ELSE arac_tipi"
                " END, arac_sinifi=CASE WHEN arac_sinifi='' THEN ? ELSE"
                " arac_sinifi END, otopilot=CASE WHEN otopilot='' THEN ?"
                " ELSE otopilot END, firmware=CASE WHEN firmware='' THEN"
                " ? ELSE firmware END, renk=CASE WHEN renk='' THEN ?"
                " ELSE renk END, uid_kaynak=CASE WHEN uid_kaynak="
                "'turetilmis' AND ?<>'turetilmis' THEN ? ELSE uid_kaynak"
                " END WHERE id=?",
                (simdi, sysid, int(arac_tipi or 0), int(arac_tipi or 0),
                 str(arac_sinifi or ""), str(otopilot or ""),
                 str(firmware or ""), str(renk or ""),
                 str(uid_kaynak or ""), str(uid_kaynak or ""), dron_id))
            if firma_yaz:
                # SAHIPSIZ kayitlari sahiplendirir, sahipli olani
                # ASLA devralmaz (bkz. islev aciklamasi).
                try:
                    con.execute(
                        "UPDATE dronlar SET firma_id=? WHERE id=?"
                        " AND firma_id IS NULL", (firma_id, dron_id))
                except Exception:
                    # Kolon beklenmedik bicimde yoksa kimlik kaydi
                    # yazilmis olmali; izolasyon eksigi ucusu
                    # engellemekten iyidir.
                    pass
            return dron_id, False
        if firma_yaz:
            cur = con.execute(
                "INSERT INTO dronlar (uid, uid_kaynak, isim, renk, sysid,"
                " arac_tipi, arac_sinifi, otopilot, firmware, ilk_kayit_ts,"
                " kaydeden_eposta, kaydeden_isim, son_gorulme_ts, firma_id)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (uid, str(uid_kaynak or "turetilmis"), str(isim or ""),
                 str(renk or ""), sysid, int(arac_tipi or 0),
                 str(arac_sinifi or ""), str(otopilot or ""),
                 str(firmware or ""), simdi, str(kaydeden_eposta or ""),
                 str(kaydeden_isim or ""), simdi, firma_id))
        else:
            cur = con.execute(
                "INSERT INTO dronlar (uid, uid_kaynak, isim, renk, sysid,"
                " arac_tipi, arac_sinifi, otopilot, firmware, ilk_kayit_ts,"
                " kaydeden_eposta, kaydeden_isim, son_gorulme_ts)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (uid, str(uid_kaynak or "turetilmis"), str(isim or ""),
                 str(renk or ""), sysid, int(arac_tipi or 0),
                 str(arac_sinifi or ""), str(otopilot or ""),
                 str(firmware or ""), simdi, str(kaydeden_eposta or ""),
                 str(kaydeden_isim or ""), simdi))
        return int(cur.lastrowid), True


# v2.4.22: FK ile dronlar(id)'ye bagli tablolar (birlestirmede tasinir)
DRON_BAGLI_TABLOLAR = ("dron_oturumlari", "dron_parametreler",
                       "dron_parametre_gecmisi", "telemetri")


def dron_kimlik_yukselt(kaynak_id, yeni_uid, yeni_kaynak="autopilot_uid"):
    """v2.4.22: Turetilmis kimlikli kaydi gercek UID'ye tasir.

    Ayni fiziksel arac icin iki kayit olusmasini onler:
    - `yeni_uid` henuz kayitli degilse kaynak satirin UID'si YERINDE
      yukseltilir; boylece tum FK'li veri (oturum, parametre, parametre
      gecmisi, telemetri) oldugu gibi korunur.
    - `yeni_uid` baska bir satirda kayitliysa kaynak satirin FK'li tum
      verisi hedef satira TASINIR, kaynak satir silinir. Hedef satirin
      `ilk_kayit_ts`/`kaydeden_*` bilgisi iki kayittan en ESKI olanla
      korunur.

    Donus: (hedef_dron_id, islem) — islem: 'yukseltildi' | 'birlestirildi'
            | 'gerekmedi' | None (hata/bulunamadi)
    """
    yeni_uid = str(yeni_uid or "").strip()
    if not yeni_uid or not kaynak_id:
        return None, None
    with baglanti() as con:
        k = con.execute(
            "SELECT id, uid, uid_kaynak, isim, renk, ilk_kayit_ts,"
            " kaydeden_eposta, kaydeden_isim FROM dronlar WHERE id=?",
            (int(kaynak_id),)).fetchone()
        if k is None:
            return None, None
        if str(k["uid"]) == yeni_uid:
            return int(k["id"]), "gerekmedi"
        h = con.execute("SELECT id, ilk_kayit_ts, isim, renk,"
                        " kaydeden_eposta, kaydeden_isim FROM dronlar"
                        " WHERE uid=?", (yeni_uid,)).fetchone()
        if h is None:
            # Yerinde yukseltme: FK'lar korunur
            con.execute("UPDATE dronlar SET uid=?, uid_kaynak=? WHERE id=?",
                        (yeni_uid, str(yeni_kaynak or "autopilot_uid"),
                         int(k["id"])))
            return int(k["id"]), "yukseltildi"
        hedef_id = int(h["id"])
        kaynak_db_id = int(k["id"])
        if hedef_id == kaynak_db_id:
            return hedef_id, "gerekmedi"
        # FK'li satirlari hedefe tasi.
        #
        # v2.4.54: onceki kod `UPDATE OR IGNORE` kullaniyordu. Bu SQLite'a
        # ozgudur; `pg.py` lehce cevirisi yalniz `INSERT OR IGNORE` /
        # `INSERT OR REPLACE` kaliplarini tanidigi icin PG'de sozdizim
        # hatasi olusuyordu. Hata `except: pass` ile yutuluyordu ama
        # PostgreSQL'de yutulan hata ISLEMI BOZAR: ayni islemdeki her
        # sonraki deyim "current transaction is aborted" verir. Sonuc,
        # `dron_kimlik_yukselt()`in PG'de HIC calismamasiydi — turetilmis
        # kimlikli kayit gercek UID'ye yukseltilemiyor, ayni arac icin
        # mukerrer kayitlar birikiyordu.
        #
        # Cozum, iki lehcede de gecerli olan siradir: catisacak hedef
        # satirlari ONCE dus, sonra yalin UPDATE ile tasi. Catisma
        # yalniz UNIQUE(dron_id, ...) kisitli tablolarda olusabilir
        # (olculdu: `dron_parametreler` (dron_id, ad),
        # `telemetri` (dron_id, ts)); catisan satir zaten atilacakti.
        _CAKISAN = {
            "dron_parametreler": ("ad",),
            "telemetri": ("ts",),
        }
        for tablo in DRON_BAGLI_TABLOLAR:
            anahtar = _CAKISAN.get(tablo)
            if anahtar:
                kolonlar = ", ".join(anahtar)
                try:
                    con.execute(
                        f"DELETE FROM {tablo} WHERE dron_id=? AND"
                        f" ({kolonlar}) IN (SELECT {kolonlar} FROM {tablo}"
                        f" WHERE dron_id=?)",
                        (kaynak_db_id, hedef_id))
                except Exception as e:
                    # Yutmuyoruz: PG'de bozulan islem sessiz veri kaybina
                    # yol acar. Cagiran hatayi gorup kullaniciya bildirir.
                    raise RuntimeError(
                        "Kimlik birlestirmede catisan satirlar"
                        " temizlenemedi (%s): %s" % (tablo, e))
            try:
                con.execute(f"UPDATE {tablo} SET dron_id=?"
                            f" WHERE dron_id=?", (hedef_id, kaynak_db_id))
            except Exception as e:
                raise RuntimeError(
                    "Kimlik birlestirmede satirlar tasinamadi"
                    " (%s): %s" % (tablo, e))
        # Tasinmadan kalan artik satirlari sil (FK butunlugu icin)
        for tablo in DRON_BAGLI_TABLOLAR:
            try:
                con.execute(f"DELETE FROM {tablo} WHERE dron_id=?",
                            (kaynak_db_id,))
            except Exception:
                pass
        # En eski kayit bilgisini koru
        try:
            k_ts = float(k["ilk_kayit_ts"] or 0) or 0.0
            h_ts = float(h["ilk_kayit_ts"] or 0) or 0.0
            if k_ts and (not h_ts or k_ts < h_ts):
                con.execute(
                    "UPDATE dronlar SET ilk_kayit_ts=?,"
                    " kaydeden_eposta=?, kaydeden_isim=? WHERE id=?",
                    (k_ts, str(k["kaydeden_eposta"] or ""),
                     str(k["kaydeden_isim"] or ""), hedef_id))
        except (TypeError, ValueError):
            pass
        # Bos alanlari kaynaktan tamamla
        con.execute(
            "UPDATE dronlar SET isim=CASE WHEN isim='' THEN ? ELSE isim"
            " END, renk=CASE WHEN renk='' THEN ? ELSE renk END"
            " WHERE id=?",
            (str(k["isim"] or ""), str(k["renk"] or ""), hedef_id))
        # v2.4.54: firma sahipligi de tasinir. Kaynak kayit sahipliyken
        # hedef sahipsizse, silinen satirla birlikte sahiplik de yok
        # olurdu; sonucta birlesmis kayit `firma_id IS NULL` kalir ve
        # `firma_kosulu()` onu TUM firmalara gosterir. Yalnizca hedef
        # sahipsizken yazilir; sahipli hedef ASLA devralinmaz.
        if firma_kolonu_var("dronlar"):
            try:
                con.execute(
                    "UPDATE dronlar SET firma_id=(SELECT firma_id FROM"
                    " dronlar WHERE id=?) WHERE id=? AND firma_id IS NULL",
                    (kaynak_db_id, hedef_id))
            except Exception:
                pass
        con.execute("DELETE FROM dronlar WHERE id=?", (kaynak_db_id,))
        return hedef_id, "birlestirildi"


def dron_mukerrer_birlestir():
    """v2.4.22: Ayni fiziksel arac icin olusmus `fp:` kayitlarini birlestirir.

    Donanim UID'li (uid_kaynak != 'turetilmis') bir kayitla ayni sysid ve
    ayni otopilote sahip turetilmis kayitlar hedefe tasinir.

    Donus: birlestirilen kayit sayisi
    """
    sayi = 0
    with baglanti() as con:
        turetilmis = [dict(r) for r in con.execute(
            "SELECT id, sysid, otopilot FROM dronlar"
            " WHERE uid LIKE 'fp:%' OR uid_kaynak='turetilmis'")]
        hedefler = [dict(r) for r in con.execute(
            "SELECT id, uid, sysid, otopilot FROM dronlar"
            " WHERE uid NOT LIKE 'fp:%' AND uid_kaynak<>'turetilmis'")]
    for t in turetilmis:
        esles = [h for h in hedefler
                 if int(h.get("sysid") or 0) == int(t.get("sysid") or 0)
                 and str(h.get("otopilot") or "")
                 == str(t.get("otopilot") or "")]
        if len(esles) != 1:
            continue
        _, islem = dron_kimlik_yukselt(t["id"], esles[0]["uid"],
                                       "autopilot_uid")
        if islem == "birlestirildi":
            sayi += 1
    return sayi


def dron_kaydi_oku(uid=None, dron_id=None):
    """UID veya id ile dron kaydini sozluk olarak dondurur (yoksa None)."""
    with baglanti() as con:
        if dron_id is not None:
            r = con.execute("SELECT * FROM dronlar WHERE id=?",
                            (int(dron_id),)).fetchone()
        else:
            r = con.execute("SELECT * FROM dronlar WHERE uid=?",
                            (str(uid or ""),)).fetchone()
    return dict(r) if r is not None else None


# ----------------------------------------------------------------------
# v2.4.53: FIRMA IZOLASYONU
# ----------------------------------------------------------------------
# Merkezde calisan ornek cok firmalidir. Suzgecler yalnizca firma_id
# kolonu VARSA ve cagiran bir firma_id VERDIYSE devreye girer; lokal
# kurulumda ikisi de yoktur ve sorgular birebir eskisi gibi calisir.
_FIRMA_KOLON_ONBELLEK = {}
# v2.4.53 Faz 7: genel kolon varligi onbellegi -> {(tablo, kolon): bool}
_KOLON_ONBELLEK = {}


def kolon_var(tablo, kolon):
    """Tabloda belirtilen kolon var mi (onbellekli).

    Surum gecisi sirasinda kolonun VAR OLMAMASI normaldir: sahadaki
    v2.4.24 veritabani korunmak zorunda oldugu icin yeni alanlar
    kosullu yazilir. Bu islev o kosulun tek dogruluk kaynagidir.

    Tablo/kolon adlari SQL'e dogrudan gomuldugu icin (PRAGMA baglama
    kabul etmez) yalniz tanimlayici karakterlere izin verilir.
    """
    anahtar = (str(tablo), str(kolon))
    if anahtar in _KOLON_ONBELLEK:
        return _KOLON_ONBELLEK[anahtar]
    import re as _re
    if not (_re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(tablo))
            and _re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(kolon))):
        _KOLON_ONBELLEK[anahtar] = False
        return False
    sonuc = False
    try:
        with baglanti() as con:
            if pg_kipinde():
                r = con.execute(
                    "SELECT 1 FROM information_schema.columns"
                    " WHERE table_name=? AND column_name=?",
                    (str(tablo), str(kolon))).fetchone()
                sonuc = r is not None
            else:
                for r in con.execute("PRAGMA table_info(%s)" % tablo):
                    if str(r[1]) == str(kolon):
                        sonuc = True
                        break
    except Exception:
        sonuc = False
    _KOLON_ONBELLEK[anahtar] = sonuc
    return sonuc


def firma_kolonu_var(tablo):
    """Tabloda firma_id kolonu var mi (onbellekli)."""
    if tablo in _FIRMA_KOLON_ONBELLEK:
        return _FIRMA_KOLON_ONBELLEK[tablo]
    sonuc = kolon_var(tablo, "firma_id")
    _FIRMA_KOLON_ONBELLEK[tablo] = sonuc
    return sonuc


def firma_kosulu(tablo, firma_id, onek=""):
    """(sql_parcasi, argumanlar) doner; suzgec gerekmezse ("", []).

    Suzgec `firma_id IS NULL OR firma_id = ?` bicimindedir: sahipsiz
    (eski) kayitlar gorunur kalir, aksi halde merkeze tasinan mevcut
    veriler bir anda kaybolur.
    """
    if not firma_id or not firma_kolonu_var(tablo):
        return "", []
    k = "%sfirma_id" % (onek + "." if onek else "")
    return "(%s IS NULL OR %s = ?)" % (k, k), [int(firma_id)]


def dron_kayitlari_listele(firma_id=None):
    """Kayitli dronlari ilk kayit sirasiyla dondurur.

    `firma_id` verilirse (merkezde calisan cok firmali ornek) yalnizca
    o firmanin ve sahipsiz dronlari doner. Lokal kurulumda parametre
    verilmez ve tum kayitlar doner (eski davranis).
    """
    kosul, arg = firma_kosulu("dronlar", firma_id)
    sql = "SELECT * FROM dronlar"
    if kosul:
        sql += " WHERE " + kosul
    sql += " ORDER BY ilk_kayit_ts, id"
    with baglanti() as con:
        return [dict(r) for r in con.execute(sql, arg)]


def dron_kaynaklari_listele(firma_id):
    """Kamera kaynak seçimi için yalnız kesin sahipli firma dronlarını döndürür.

    Genel ``dron_kayitlari_listele`` geriye uyumluluk nedeniyle ``firma_id
    IS NULL`` kayıtlarını da gösterir. Bulut köprüsüne gönderilen snapshot'ta
    bu davranış veri sızıntısı olur; burada yalnız ``firma_id = ?`` kabul edilir.
    """
    try:
        fid = int(firma_id)
    except (TypeError, ValueError):
        return []
    if fid <= 0 or not firma_kolonu_var("dronlar"):
        return []
    with baglanti() as con:
        return [dict(r) for r in con.execute(
            "SELECT id, uid, isim, sysid, son_gorulme_ts FROM dronlar "
            "WHERE firma_id=? AND uid IS NOT NULL AND uid<>'' "
            "ORDER BY ilk_kayit_ts, id", (fid,))]


def dron_alan_guncelle(dron_id, **alanlar):
    """Dron kaydinda izin verilen alanlari gunceller (isim, renk, notlar)."""
    izinli = {"isim", "renk", "notlar", "arac_sinifi", "sysid",
              "arac_tipi", "otopilot", "firmware"}
    setler, degerler = [], []
    for ad, deger in alanlar.items():
        if ad in izinli:
            setler.append(f"{ad}=?")
            degerler.append(deger)
    if not setler:
        return False
    degerler.append(int(dron_id))
    with baglanti() as con:
        cur = con.execute(
            f"UPDATE dronlar SET {', '.join(setler)} WHERE id=?", degerler)
        return cur.rowcount > 0


def dron_id_bul(sysid=None, uid=None):
    """UID (tercihli) veya sysid ile dron_id dondurur; bulunamazsa None."""
    with baglanti() as con:
        if uid:
            r = con.execute("SELECT id FROM dronlar WHERE uid=?",
                            (str(uid),)).fetchone()
            if r is not None:
                return int(r["id"])
        if sysid is not None:
            r = con.execute(
                "SELECT id FROM dronlar WHERE sysid=?"
                " ORDER BY son_gorulme_ts DESC LIMIT 1",
                (int(sysid),)).fetchone()
            if r is not None:
                return int(r["id"])
    return None


# ==================================================================
# v2.4.21: BAGLANTI OTURUMLARI
# ==================================================================
def oturum_baslat(dron_id, sysid=None, baglanti_id=None,
                  pilot_eposta="", pilot_isim="", pilotlar=None):
    """Yeni bir baglanti oturumu acar ve id'sini dondurur."""
    import time as _t
    with baglanti() as con:
        cur = con.execute(
            "INSERT INTO dron_oturumlari (dron_id, baglanti_id, sysid,"
            " baslangic_ts, pilot_eposta, pilot_isim, pilotlar)"
            " VALUES (?,?,?,?,?,?,?)",
            (int(dron_id), baglanti_id, sysid, _t.time(),
             str(pilot_eposta or ""), str(pilot_isim or ""),
             json.dumps(list(pilotlar or []), ensure_ascii=False)))
        return int(cur.lastrowid)


def oturum_dron_tasi(oturum_id, yeni_dron_id):
    """v2.4.22: Acik oturumu (ve telemetrisini) yeni dron kaydina tasir."""
    with baglanti() as con:
        con.execute("UPDATE dron_oturumlari SET dron_id=? WHERE id=?",
                    (int(yeni_dron_id), int(oturum_id)))
        con.execute("UPDATE telemetri SET dron_id=? WHERE oturum_id=?",
                    (int(yeni_dron_id), int(oturum_id)))


def oturum_bitir(oturum_id, pilotlar=None):
    """Oturumu kapatir; pilot listesi verilirse gunceller."""
    import time as _t
    with baglanti() as con:
        if pilotlar is not None:
            con.execute(
                "UPDATE dron_oturumlari SET bitis_ts=?, pilotlar=?"
                " WHERE id=? AND bitis_ts IS NULL",
                (_t.time(), json.dumps(list(pilotlar), ensure_ascii=False),
                 int(oturum_id)))
        else:
            con.execute(
                "UPDATE dron_oturumlari SET bitis_ts=? WHERE id=?"
                " AND bitis_ts IS NULL", (_t.time(), int(oturum_id)))


def acik_oturumlari_kapat():
    """Program acilisinda kalmis (bitis_ts NULL) oturumlari kapatir.

    Bitis zamani, o oturumun son telemetri ornegi (yoksa baslangic).
    """
    with baglanti() as con:
        cur = con.execute(
            "UPDATE dron_oturumlari SET bitis_ts = COALESCE("
            "  (SELECT MAX(t.ts) FROM telemetri t"
            "    WHERE t.oturum_id = dron_oturumlari.id),"
            "  baslangic_ts) WHERE bitis_ts IS NULL")
        return cur.rowcount


def oturum_pilot_ekle(oturum_id, eposta):
    """Oturumun pilot listesine (JSON) yeni e-posta ekler."""
    eposta = str(eposta or "").strip()
    if not eposta:
        return
    with baglanti() as con:
        r = con.execute("SELECT pilotlar FROM dron_oturumlari WHERE id=?",
                        (int(oturum_id),)).fetchone()
        if r is None:
            return
        try:
            liste = json.loads(r["pilotlar"]) or []
        except (ValueError, TypeError):
            liste = []
        if eposta in liste:
            return
        liste.append(eposta)
        con.execute("UPDATE dron_oturumlari SET pilotlar=? WHERE id=?",
                    (json.dumps(liste, ensure_ascii=False),
                     int(oturum_id)))


# ==================================================================
# v2.4.21: TELEMETRI KAYDI (kesintisiz)
# ==================================================================
TELEMETRI_ALANLARI = (
    "dron_id", "oturum_id", "ts", "lat", "lon", "irtifa", "irtifa_msl",
    "hiz", "dikey_hiz", "yaw", "roll", "pitch", "mod", "armed",
    "batarya_v", "batarya_y", "uydu", "hdop",
    "pilot_eposta", "pilot_isim",
)

# `telemetri` semasinda NOT NULL DEFAULT tanimli alanlar.
#
# ## Neden gerekli (v2.4.24 duzeltmesi)
#
# `INSERT INTO telemetri (mod, ...) VALUES (?, ...)` seklinde kolon
# ACIKCA listelendiginde, deger `None` gecilirse SQLite semadaki
# `DEFAULT ''` degerini UYGULAMAZ; `NOT NULL` ihlali firlatir:
#     NOT NULL constraint failed: telemetri.mod
#
# MAVLink paketinde `mod`/`armed` henuz gelmemisse (baglantinin ilk
# saniyeleri = KALKIS ANI) satir yazilamaz ve v2.4.23'te sessizce
# kaybolurdu. Bu esleme, semanin varsayilanini yazma yolunda uygular.
TELEMETRI_VARSAYILAN = {
    "mod": "",
    "armed": 0,
    "pilot_eposta": "",
    "pilot_isim": "",
}

# Varsayilan uygulanacak alanlarin demet icindeki indisleri (hiz icin
# bir kez hesaplanir).
_TEL_VARSAYILAN_INDIS = tuple(
    (TELEMETRI_ALANLARI.index(a), v)
    for a, v in TELEMETRI_VARSAYILAN.items()
    if a in TELEMETRI_ALANLARI
)


def telemetri_satir_duzelt(satir):
    """NOT NULL alanlarinda `None` olan degerleri varsayilana cevirir.

    Girdi/cikti: TELEMETRI_ALANLARI sirasinda demet.
    Degisiklik gerekmiyorsa AYNI demet doner (gereksiz kopya yok).
    """
    duzelt = None
    for indis, varsayilan in _TEL_VARSAYILAN_INDIS:
        if indis < len(satir) and satir[indis] is None:
            if duzelt is None:
                duzelt = list(satir)
            duzelt[indis] = varsayilan
    return tuple(duzelt) if duzelt is not None else satir


def telemetri_toplu_yaz(satirlar):
    """Telemetri satirlarini toplu yazar.

    satirlar: TELEMETRI_ALANLARI sirasinda demet listesi.
    Donus: yazilan satir sayisi.

    NOT NULL alanlarindaki `None` degerler sema varsayilanina cevrilir;
    aksi halde kalkis anindaki (mod/armed henuz bilinmeyen) ornekler
    kisit ihlaliyle reddedilirdi. Bkz. TELEMETRI_VARSAYILAN.
    """
    if not satirlar:
        return 0
    satirlar = [telemetri_satir_duzelt(s) for s in satirlar]
    yer = ",".join("?" * len(TELEMETRI_ALANLARI))
    # v2.4.43: `OR IGNORE` — `ux_telemetri_dron_ts` tekillemesiyle
    # uyumlu olmak icin.
    #
    # Neden gerekli: tampon dosyasi "DB'ye yazildi ama .aktarildi olarak
    # isaretlenemedi" durumunda yeniden denenir (Windows dosya kilidi).
    # Duz `INSERT` bu tekrarda UNIQUE ihlali firlatir ve TUM toplu yazma
    # duser; oysa satirlarin cogu yeni olabilir. `OR IGNORE` mukerrerleri
    # sessizce atlar, yeni satirlari yazar.
    #
    # Donus degeri artik `len(satirlar)` DEGIL, gercekten eklenen satir
    # sayisidir (`total_changes` farki). Cagirici bu sayiya guvenerek
    # "kac ornek aktarildi" bildirir; sisirilmis sayi yanlis olurdu.
    sql = (f"INSERT OR IGNORE INTO telemetri"
           f" ({','.join(TELEMETRI_ALANLARI)}) VALUES ({yer})")
    with baglanti() as con:
        once = con.total_changes
        con.executemany(sql, satirlar)
        return con.total_changes - once


def telemetri_temizle(gun=30):
    """Belirtilen gunden eski telemetri kayitlarini siler."""
    import time as _t
    if not gun or gun <= 0:
        return 0
    esik = _t.time() - float(gun) * 86400.0
    with baglanti() as con:
        cur = con.execute("DELETE FROM telemetri WHERE ts < ?", (esik,))
        return cur.rowcount


# ==================================================================
# v2.4.21: PARAMETRE KALICILIGI + DEGISIKLIK GECMISI
# ==================================================================
def param_snapshot_kaydet(dron_id, parametreler, kaynak="dron",
                          eposta="", isim=""):
    """Tam okuma sonucunu dron_parametreler'e islerler (upsert).

    Yeni ad eklenir, var olanin degeri guncellenir. Deger degistiyse
    dron_parametre_gecmisi'ne eski -> yeni kaydi yazilir.

    Donus: (eklenen, guncellenen)
    """
    import time as _t
    if not parametreler:
        return 0, 0
    simdi = _t.time()
    eklenen = guncellenen = 0
    with baglanti() as con:
        mevcut = {r["ad"]: (int(r["id"]), r["deger"]) for r in con.execute(
            "SELECT id, ad, deger FROM dron_parametreler WHERE dron_id=?",
            (int(dron_id),))}
        for ad, deger in parametreler.items():
            ad = str(ad)
            try:
                yeni = float(deger)
            except (TypeError, ValueError):
                continue
            kayit = mevcut.get(ad)
            if kayit is None:
                cur = con.execute(
                    "INSERT INTO dron_parametreler (dron_id, ad, deger,"
                    " ilk_okuma_ts, guncelleme_ts, kaynak)"
                    " VALUES (?,?,?,?,?,?)",
                    (int(dron_id), ad, yeni, simdi, simdi, str(kaynak)))
                con.execute(
                    "INSERT INTO dron_parametre_gecmisi (dron_id,"
                    " param_id, ad, eski_deger, yeni_deger, ts,"
                    " kullanici_eposta, kullanici_isim, kaynak)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (int(dron_id), int(cur.lastrowid), ad, None, yeni,
                     simdi, str(eposta or ""), str(isim or ""),
                     str(kaynak) + ":ilk"))
                eklenen += 1
                continue
            param_id, eski = kayit
            eski_f = None
            try:
                eski_f = None if eski is None else float(eski)
            except (TypeError, ValueError):
                eski_f = None
            if eski_f is not None and abs(eski_f - yeni) < 1e-9:
                con.execute(
                    "UPDATE dron_parametreler SET guncelleme_ts=?"
                    " WHERE id=?", (simdi, param_id))
                continue
            con.execute(
                "UPDATE dron_parametreler SET deger=?, guncelleme_ts=?,"
                " kaynak=? WHERE id=?",
                (yeni, simdi, str(kaynak), param_id))
            con.execute(
                "INSERT INTO dron_parametre_gecmisi (dron_id, param_id,"
                " ad, eski_deger, yeni_deger, ts, kullanici_eposta,"
                " kullanici_isim, kaynak) VALUES (?,?,?,?,?,?,?,?,?)",
                (int(dron_id), param_id, ad, eski_f, yeni, simdi,
                 str(eposta or ""), str(isim or ""), str(kaynak)))
            guncellenen += 1
    return eklenen, guncellenen


def param_deger_yaz(dron_id, ad, deger, kaynak="gcs", eposta="",
                    isim=""):
    """Tek parametre degerini gunceller ve gecmise denetim kaydi yazar.

    Parametre tabloda yoksa eklenir (drona yeni bir ad yazilmis olabilir).
    Donus: True (yazildi) / False (gecersiz deger)
    """
    import time as _t
    ad = str(ad or "").strip()
    if not ad:
        return False
    try:
        yeni = float(deger)
    except (TypeError, ValueError):
        return False
    simdi = _t.time()
    with baglanti() as con:
        r = con.execute(
            "SELECT id, deger FROM dron_parametreler WHERE dron_id=?"
            " AND ad=?", (int(dron_id), ad)).fetchone()
        if r is None:
            cur = con.execute(
                "INSERT INTO dron_parametreler (dron_id, ad, deger,"
                " ilk_okuma_ts, guncelleme_ts, kaynak)"
                " VALUES (?,?,?,?,?,?)",
                (int(dron_id), ad, yeni, simdi, simdi, str(kaynak)))
            param_id, eski = int(cur.lastrowid), None
        else:
            param_id = int(r["id"])
            try:
                eski = None if r["deger"] is None else float(r["deger"])
            except (TypeError, ValueError):
                eski = None
            con.execute(
                "UPDATE dron_parametreler SET deger=?, guncelleme_ts=?,"
                " kaynak=? WHERE id=?",
                (yeni, simdi, str(kaynak), param_id))
        con.execute(
            "INSERT INTO dron_parametre_gecmisi (dron_id, param_id, ad,"
            " eski_deger, yeni_deger, ts, kullanici_eposta,"
            " kullanici_isim, kaynak) VALUES (?,?,?,?,?,?,?,?,?)",
            (int(dron_id), param_id, ad, eski, yeni, simdi,
             str(eposta or ""), str(isim or ""), str(kaynak)))
    return True


def param_listesi_oku(dron_id):
    """Dronun guncel parametrelerini {ad: deger} olarak dondurur."""
    with baglanti() as con:
        return {r["ad"]: r["deger"] for r in con.execute(
            "SELECT ad, deger FROM dron_parametreler WHERE dron_id=?",
            (int(dron_id),))}


def param_ozet_oku(dron_id):
    """(parametreler, toplam, son_guncelleme_ts) dondurur."""
    with baglanti() as con:
        satirlar = con.execute(
            "SELECT ad, deger, guncelleme_ts FROM dron_parametreler"
            " WHERE dron_id=?", (int(dron_id),)).fetchall()
    params = {r["ad"]: r["deger"] for r in satirlar}
    ts = max((float(r["guncelleme_ts"] or 0) for r in satirlar),
             default=0.0)
    return params, len(params), ts


def param_gecmisi_oku(dron_id, ad="", limit=200):
    """Parametre degisiklik gecmisini (en yeni ustte) dondurur."""
    limit = max(1, min(2000, int(limit or 200)))
    with baglanti() as con:
        if ad:
            satirlar = con.execute(
                "SELECT * FROM dron_parametre_gecmisi WHERE dron_id=?"
                " AND ad=? ORDER BY ts DESC LIMIT ?",
                (int(dron_id), str(ad), limit)).fetchall()
        else:
            satirlar = con.execute(
                "SELECT * FROM dron_parametre_gecmisi WHERE dron_id=?"
                " ORDER BY ts DESC LIMIT ?",
                (int(dron_id), limit)).fetchall()
    return [dict(r) for r in satirlar]


# ==================================================================
# v2.4.41: KALKIS ONCESI KONTROL LISTESI KAYITLARI
# ==================================================================
def kalkis_kontrol_kaydet(sysid, maddeler, *, dron_id=None,
                          oturum_id=None, pilot_eposta="",
                          pilot_isim="", arac_tipi=0, arac_tipi_ad="",
                          hedef_irtifa=0.0):
    """Pilotun kontrol listesi cevaplarini kalici olarak yazar.

    Tarih/saat ve pilot kimligi CAGIRAN SUNUCU tarafindan verilir;
    istemciden gelen deger kullanilMAZ. Donus: kontrol_id (int).

    Yazma basarisiz olursa istisna yukselir; cagiran takeoff komutunu
    GONDERMEMELIDIR.
    """
    import time as _t
    simdi = _t.time()
    yerel = _t.strftime("%Y-%m-%d %H:%M:%S", _t.localtime(simdi))
    liste = list(maddeler or [])
    zorunlular = [m for m in liste if m.get("zorunlu", True)]
    evet = sum(1 for m in zorunlular if m.get("cevap") is True)
    tam = 1 if (zorunlular and evet == len(zorunlular)) else 0
    with baglanti() as con:
        cur = con.execute(
            "INSERT INTO kalkis_kontrolleri (dron_id, sysid, oturum_id,"
            " ts, yerel_saat, pilot_eposta, pilot_isim, arac_tipi,"
            " arac_tipi_ad, hedef_irtifa, madde_sayisi, evet_sayisi,"
            " tam_onay) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (dron_id, int(sysid or 0), oturum_id, simdi, yerel,
             str(pilot_eposta or ""), str(pilot_isim or ""),
             int(arac_tipi or 0), str(arac_tipi_ad or ""),
             float(hedef_irtifa or 0.0), len(liste), evet, tam))
        kontrol_id = int(cur.lastrowid)
        for i, m in enumerate(liste):
            con.execute(
                "INSERT INTO kalkis_kontrol_maddeleri (kontrol_id, sira,"
                " anahtar, soru, grup, kaynak, zorunlu, cevap)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (kontrol_id, int(m.get("sira", i)),
                 str(m.get("anahtar", ""))[:64],
                 str(m.get("soru", ""))[:400],
                 str(m.get("grup", ""))[:32],
                 str(m.get("kaynak", ""))[:32],
                 1 if m.get("zorunlu", True) else 0,
                 1 if m.get("cevap") is True else 0))
    return kontrol_id


def kalkis_kontrol_takeoff_isaretle(kontrol_id, gonderildi, hata=""):
    """Kayda takeoff komutunun sonucunu isler (denetim izi)."""
    with baglanti() as con:
        con.execute(
            "UPDATE kalkis_kontrolleri SET takeoff_gonderildi=?,"
            " takeoff_hata=? WHERE id=?",
            (1 if gonderildi else 0, str(hata or "")[:300],
             int(kontrol_id)))


def kalkis_kontrol_listele(dron_id=None, sysid=None, limit=50,
                           maddeler=False):
    """Kalkis kontrol kayitlarini (en yeni ustte) dondurur.

    maddeler=True ise her kaydin cevap listesi de eklenir.
    """
    limit = max(1, min(500, int(limit or 50)))
    with baglanti() as con:
        if dron_id is not None:
            satirlar = con.execute(
                "SELECT * FROM kalkis_kontrolleri WHERE dron_id=?"
                " ORDER BY ts DESC LIMIT ?",
                (int(dron_id), limit)).fetchall()
        elif sysid is not None:
            satirlar = con.execute(
                "SELECT * FROM kalkis_kontrolleri WHERE sysid=?"
                " ORDER BY ts DESC LIMIT ?",
                (int(sysid), limit)).fetchall()
        else:
            satirlar = con.execute(
                "SELECT * FROM kalkis_kontrolleri"
                " ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        sonuc = [dict(r) for r in satirlar]
        if maddeler and sonuc:
            for k in sonuc:
                k["maddeler"] = [dict(x) for x in con.execute(
                    "SELECT sira, anahtar, soru, grup, kaynak, zorunlu,"
                    " cevap FROM kalkis_kontrol_maddeleri"
                    " WHERE kontrol_id=? ORDER BY sira",
                    (int(k["id"]),))]
    return sonuc


def kalkis_kontrol_araligi(dron_id, bas_ts, bit_ts):
    """Bir ucus araligina dusen kalkis kontrol kayitlarini dondurur.

    PDF ucus raporunda kullanilir. Kalkis kontrolu ucusun BASLAMASINDAN
    hemen once yapildigi icin alt sinir 10 dakika geriye cekilir.
    """
    # v2.4.41: dron_id None gelebilir (henuz dronlar tablosuna yazilmamis
    # sysid, ornegin ilk baglantida cikan ucus). int(None) TypeError
    # atip TUM raporu dusurecegi icin burada bos donuyoruz: raporun
    # kalkis kontrolu bolumu bos kalir, rapor yine uretilir.
    if dron_id is None:
        return []
    try:
        b = float(bas_ts) - 600.0
        s = float(bit_ts) + 60.0
        did = int(dron_id)
    except (TypeError, ValueError):
        return []
    with baglanti() as con:
        satirlar = con.execute(
            "SELECT * FROM kalkis_kontrolleri WHERE dron_id=?"
            " AND ts BETWEEN ? AND ? ORDER BY ts",
            (did, b, s)).fetchall()
        sonuc = [dict(r) for r in satirlar]
        for k in sonuc:
            k["maddeler"] = [dict(x) for x in con.execute(
                "SELECT sira, anahtar, soru, grup, kaynak, zorunlu,"
                " cevap FROM kalkis_kontrol_maddeleri"
                " WHERE kontrol_id=? ORDER BY sira",
                (int(k["id"]),))]
    return sonuc


def acik_oturum_bul(sysid=None, dron_id=None):
    """v2.4.41: Halen acik olan oturumun id'sini dondurur (yoksa None).

    Kalkis kontrol kaydini dogru ucus oturumuna baglamak icin gerekir.
    """
    with baglanti() as con:
        if dron_id is not None:
            r = con.execute(
                "SELECT id FROM dron_oturumlari WHERE dron_id=?"
                " AND bitis_ts IS NULL ORDER BY baslangic_ts DESC"
                " LIMIT 1", (int(dron_id),)).fetchone()
            if r is not None:
                return int(r["id"])
        if sysid is not None:
            r = con.execute(
                "SELECT id FROM dron_oturumlari WHERE sysid=?"
                " AND bitis_ts IS NULL ORDER BY baslangic_ts DESC"
                " LIMIT 1", (int(sysid),)).fetchone()
            if r is not None:
                return int(r["id"])
    return None


# ------------------------------------------------------------------
# v2.4.17 uyumluluk katmani: param_cache_* -> dron_parametreler
# ------------------------------------------------------------------
# Bu fonksiyonlar sysid ile calisir ve eski cagiranlar (angajman.py
# _maks_hiz, sunucu.py _arm_check_parametreleri) icin korunmustur.
# Artik param_cache tablosu yerine dron_parametreler kullanilir.
def param_cache_kaydet(sysid, parametreler, toplam, uid=None,
                       kaynak="dron", eposta="", isim=""):
    """Tam okuma sonucunu dronun parametre tablosuna isler."""
    dron_id = dron_id_bul(sysid=sysid, uid=uid)
    if dron_id is None:
        return
    param_snapshot_kaydet(dron_id, parametreler, kaynak=kaynak,
                          eposta=eposta, isim=isim)


def param_cache_oku(sysid, uid=None):
    """(parametreler, toplam, okuma_ts) doner; kayit yoksa ({}, 0, 0)."""
    dron_id = dron_id_bul(sysid=sysid, uid=uid)
    if dron_id is None:
        return {}, 0, 0
    return param_ozet_oku(dron_id)


def param_cache_deger_guncelle(sysid, ad, deger, uid=None,
                               kaynak="gcs", eposta="", isim=""):
    """Tek parametre yazildiginda kalici degeri gunceller + gecmis."""
    dron_id = dron_id_bul(sysid=sysid, uid=uid)
    if dron_id is None:
        return
    param_deger_yaz(dron_id, ad, deger, kaynak=kaynak, eposta=eposta,
                    isim=isim)


# ==================================================================
# v2.4.21: VIEW TABANLI UCUS OKUMA (eski "ucuslar" tablosunun yerine)
# ==================================================================
# ------------------------------------------------------------------
# v2.4.64: UCUS SAHIPLIGI — TEK DOGRULUK KAYNAGI
# ------------------------------------------------------------------
# Operatorun baglayici kurali: "takeoff'u kim verdiyse o ucusun
# sahibi odur". Bu kural iki yerde gerekir:
#   1) ucus_listesi()  -> gorunurluk suzgeci
#   2) ucus_gecmisi.sahip_mi() -> erisim denetimi (oku/sil)
# Ayni kuralin iki kopyasi olursa biri digerini bosa cikarir; bu
# yuzden tek fonksiyonda toplanmistir.
#
# Pencere neden 30 dakika: takeoff kontrolu ucustan ONCE yapilir.
# Pilot kontrol listesini doldurup bekledikten sonra kalkis verebilir
# ve v_ucuslar segmenti gercek kalkis aninda baslar. Cok dar bir
# pencere sahibi kaybeder ve ucus "sahipsiz" gorunur.
UCUS_SAHIP_PENCERE = 1800.0        # saniye (30 dakika)


def ucus_sahibi(dron_id, baslangic, bitis, con=None):
    """Bir ucus segmentinin sahibini (takeoff'u veren pilot) dondurur.

    Donus: (eposta, isim) ikilisi degil, YALNIZCA eposta dizesi.
    Sahip bulunamazsa '' doner (= sahipsiz; yalnizca yoneticiye
    gorunur).

    `kalkis_kontrolleri.pilot_eposta` sunucuda damgalanir (sema yorumu:
    "pilot kimligi SUNUCUDA damgalanir; istemci gonderemez"), bu yuzden
    kimlik taklidine kapalidir ve sahiplik icin dogru dayanaktir.
    """
    ep, _ = ucus_sahibi_detay(dron_id, baslangic, bitis, con=con)
    return ep


def ucus_sahibi_detay(dron_id, baslangic, bitis, con=None):
    """ucus_sahibi() ile ayni, ancak (eposta, isim) ikilisi dondurur."""
    sql = ("SELECT pilot_eposta, pilot_isim"
           " FROM kalkis_kontrolleri"
           " WHERE dron_id = ? AND pilot_eposta <> ''"
           "   AND ts <= ? AND ts >= ?"
           " ORDER BY takeoff_gonderildi DESC, ts DESC"
           " LIMIT 1")
    try:
        arg = (int(dron_id), float(bitis),
               float(baslangic) - UCUS_SAHIP_PENCERE)
    except (TypeError, ValueError):
        return "", ""

    def _calistir(baglanti_nesnesi):
        r = baglanti_nesnesi.execute(sql, arg).fetchone()
        if not r:
            return "", ""
        return (str(r["pilot_eposta"] or "").strip(),
                str(r["pilot_isim"] or "").strip())

    try:
        if con is not None:
            return _calistir(con)
        with baglanti() as c:
            return _calistir(c)
    except Exception:
        # kalkis_kontrolleri yoksa/okunamazsa ucus SAHIPSIZ kalir ve
        # yoneticiden baskasina gorunmez (guvenli yon).
        return "", ""


def ucus_listesi(dron_id=None, eposta="", yonetici=False,
                 limit=500, firma_id=None):
    """v_ucuslar gorunumunden tespit edilen ucuslari dondurur.

    eposta/yonetici: yonetici olmayan kullanici YALNIZCA kendi sahibi
    oldugu ucuslari gorur (bkz. v2.4.64 notu; sahip = takeoff'u veren
    pilot). Yonetici tumunu gorur.

    [v2.4.42] Iki alan doner:
      pilotlar     : e-posta listesi (ESKI SOZLESME, degismedi)
      pilotlar_ad  : ayni sirada ad soyad listesi (yeni)

    Ad soyad cozumleme sirasi: telemetri.pilot_isim -> kullanicilar
    .ad_soyad -> e-posta (son care; ad uydurulmaz). Imzali ucus raporu
    `pilotlar_ad` kullanir; e-posta yazmak resmi belgede kabul edilemez.

    [v2.4.64] SAHIPLIK KURALI DEGISTI (operatorun baglayici talimati):

        "takeoff'u kim verdiyse o ucusun sahibi odur"

    Onceki davranis iki yonden yanlisti:

      1) `if not u["pilotlar"]` kosulu SAHIPSIZ ucuslari HERKESE
         gosteriyordu. Yeni olusturulan bir pilot, hic ucmamis olmasina
         ragmen baska ucuslari goruyordu. Bu bir yetkilendirme kusurudur.

      2) Sahiplik, telemetride adi gecen HERHANGI bir pilottu. Vardiya
         degisimi, batarya degisimi veya gozlemci girisi sirasinda
         telemetriye baska bir e-posta damgalanirsa o kisi de sahip
         sayiliyordu. Takeoff'u veren pilot ile telemetride gorunen
         pilot ayni olmak zorunda degildir.

    Sahiplik artik `kalkis_kontrolleri` tablosundan cozulur. O tablo
    sunucuda damgalanir (sema yorumu: "pilot kimligi SUNUCUDA
    damgalanir; istemci gonderemez"), yani kimlik taklidine kapalidir
    ve bu is icin dogru dayanaktir.

    Yeni alanlar:
      sahip_eposta : takeoff'u veren pilotun e-postasi ('' = sahipsiz)
      sahip_ad     : ayni pilotun adi soyadi

    Suzme kurali:
      yonetici      -> tum ucuslar
      diger roller  -> yalnizca sahip_eposta kendisine ait olanlar
      sahipsiz ucus -> YALNIZCA yoneticiye gorunur

    `pilotlar` / `pilotlar_ad` alanlari eski sozlesmedir ve imzali ucus
    raporu bunlari kullanir; bu yuzden KALDIRILMADI.
    """
    limit = max(1, min(5000, int(limit or 500)))
    kosul, arg = [], []
    if dron_id is not None:
        kosul.append("v.dron_id = ?")
        arg.append(int(dron_id))
    # v2.4.53: firma izolasyonu. Ucus, dronun firmasina aittir; bu
    # yuzden suzgec `dronlar` tablosu uzerinden alt sorgu ile uygulanir
    # (v_ucuslar gorunumunde firma_id kolonu yoktur).
    if firma_id and firma_kolonu_var("dronlar"):
        kosul.append(
            "v.dron_id IN (SELECT id FROM dronlar"
            " WHERE firma_id IS NULL OR firma_id = ?)")
        arg.append(int(firma_id))
    sql = "SELECT * FROM v_ucuslar v"
    if kosul:
        sql += " WHERE " + " AND ".join(kosul)
    sql += " ORDER BY v.baslangic DESC LIMIT ?"
    arg.append(limit)
    with baglanti() as con:
        satirlar = [dict(r) for r in con.execute(sql, arg)]
        # v2.4.42: Kullanici defteri (eposta -> ad soyad). Telemetride
        # pilot_isim bos kalmis eski kayitlar buradan tamamlanir.
        defter = {}
        try:
            for r in con.execute(
                    "SELECT eposta, ad_soyad FROM kullanicilar"):
                e_ = str(r["eposta"] or "").strip().lower()
                a_ = str(r["ad_soyad"] or "").strip()
                if e_ and a_:
                    defter[e_] = a_
        except Exception:
            defter = {}
        # Her ucusun pilot listesi: segmentteki farkli e-postalar
        for u in satirlar:
            pl, ad = [], []
            for r in con.execute(
                    "SELECT pilot_eposta, MAX(pilot_isim) AS pilot_isim"
                    " FROM telemetri"
                    " WHERE dron_id=? AND ts BETWEEN ? AND ?"
                    " AND pilot_eposta <> ''"
                    " GROUP BY pilot_eposta",
                    (u["dron_id"], u["baslangic"], u["bitis"])):
                ep = str(r["pilot_eposta"] or "").strip()
                if not ep:
                    continue
                pl.append(ep)
                isim = str(r["pilot_isim"] or "").strip()
                if not isim:
                    isim = defter.get(ep.lower(), "")
                ad.append(isim or ep)
            u["pilotlar"] = pl
            u["pilotlar_ad"] = ad

            # ----------------------------------------------------------
            # v2.4.64: SAHIP = takeoff'u veren pilot
            #
            # Takeoff kontrolu ucustan hemen ONCE yapilir, bu yuzden
            # segment baslangicindan once veya segment icinde kalan en
            # YAKIN kayit aranir. Sinir biraz genis tutulur (varsayilan
            # 30 dk): pilot kontrol listesini doldurup bekledikten sonra
            # kalkis verebilir ve v_ucuslar segmenti gercek kalkis
            # aninda baslar. Cok dar bir pencere sahibi kaybeder.
            #
            # takeoff_gonderildi=1 olanlar tercih edilir; komut hic
            # gonderilmediyse o kontrol o ucusa ait olmayabilir.
            # ----------------------------------------------------------
            sahip_ep, sahip_ad = ucus_sahibi_detay(
                u["dron_id"], u["baslangic"], u["bitis"], con=con)
            if sahip_ep and not sahip_ad:
                sahip_ad = defter.get(sahip_ep.lower(), "")
            u["sahip_eposta"] = sahip_ep
            u["sahip_ad"] = sahip_ad or sahip_ep
    if not yonetici:
        # v2.4.64: sahip = takeoff'u veren pilot. Sahipsiz ucuslar
        # yoneticiden baskasina GOSTERILMEZ (eskiden herkese aciktir).
        e = (eposta or "").strip().lower()
        if not e:
            return []          # kimlik yoksa hicbir kayit gosterilmez
        satirlar = [u for u in satirlar
                    if str(u.get("sahip_eposta", "")).strip().lower() == e]
    return satirlar


def ucus_iz_oku(dron_id, baslangic, bitis, maks_nokta=4000):
    """Bir ucusun iz noktalarini oynatici bicimiyle dondurur.

    Donus: [[t_rel, lat, lon, irtifa, hiz, yaw, bat_y, bat_v], ...]
    Cok uzun ucuslarda seyreltme yapilir (maks_nokta).

    [v2.4.41] Batarya alanlari (bat_y = yuzde, bat_v = voltaj) dizinin
    SONUNA eklendi. Indeks 0-5 DEGISMEDI; iz oynatici (gecmis.js) yalnizca
    0-3 arasini kullanir, bu nedenle ekleme geriye donuk uyumludur.
    Gerekce: imzali ucus raporunda batarya, coklu batarya (batarya
    degisimli) operasyonlarin operasyonel cekirdegidir ve telemetride
    zaten kayitlidir (batarya_v / batarya_y kolonlari).
    """
    with baglanti() as con:
        satirlar = con.execute(
            "SELECT ts, lat, lon, irtifa, hiz, yaw, batarya_y, batarya_v"
            " FROM telemetri"
            " WHERE dron_id=? AND ts BETWEEN ? AND ?"
            " AND lat IS NOT NULL AND lon IS NOT NULL"
            " AND NOT (lat = 0 AND lon = 0) ORDER BY ts",
            (int(dron_id), float(baslangic), float(bitis))).fetchall()
    adim = 1
    if maks_nokta and len(satirlar) > maks_nokta:
        adim = (len(satirlar) // int(maks_nokta)) + 1
    bas = float(baslangic)
    return [[round(float(r["ts"]) - bas, 2),
             round(float(r["lat"]), 7), round(float(r["lon"]), 7),
             round(float(r["irtifa"] or 0), 1),
             round(float(r["hiz"] or 0), 1),
             round(float(r["yaw"] or 0), 0),
             (None if r["batarya_y"] is None else int(r["batarya_y"])),
             (None if r["batarya_v"] is None
              else round(float(r["batarya_v"]), 2))]
            for r in satirlar[::adim]]


def ucus_bul(ucus_id):
    """v_ucuslar icinde id ile ucus arar (yoksa None)."""
    with baglanti() as con:
        r = con.execute("SELECT * FROM v_ucuslar WHERE id=?",
                        (str(ucus_id),)).fetchone()
    return dict(r) if r is not None else None


def telemetri_aralik_sil(dron_id, baslangic, bitis):
    """Bir ucusa karsilik gelen telemetri araligini siler.

    VIEW tabanli mimaride "ucus silmek" = o araliktaki telemetriyi
    silmek demektir. Donus: silinen ornek sayisi.
    """
    with baglanti() as con:
        cur = con.execute(
            "DELETE FROM telemetri WHERE dron_id=? AND ts BETWEEN ? AND ?",
            (int(dron_id), float(baslangic), float(bitis)))
        return cur.rowcount


def telemetri_tumunu_sil():
    """TUM telemetri kaydini siler (dron/parametre kayitlari kalir)."""
    with baglanti() as con:
        cur = con.execute("DELETE FROM telemetri")
        return cur.rowcount


def _sema_guncelle():
    """Var olan tablolara v2.4.0 sutunlarini ekler (idempotent)."""
    eklenecekler = {
        "lokasyonlar": [
            ("adres", "TEXT NOT NULL DEFAULT ''"),
            # v2.4.128 / Is 97: lokasyonlar kamera kaynagi olarak
            # koprulere dagitildigi icin sirketler arasi izolasyon zorunlu.
            ("firma_id", "INTEGER"),
        ],
        "kameralar": [
            # v2.4.193 (Faz D, kullanici istegi "kamera ayarlarinda FPS
            # siniri verebileyim"): kare hizi tavani. 0/NULL degil 15
            # varsayilani verilir; eski davranis (kodda sabit 15) birebir
            # korunur ve mevcut kayitlar davranis degistirmez.
            ("fps", "INTEGER NOT NULL DEFAULT 15"),
            # v2.4.207 (kullanici istegi: M50 penceresinde cozunurluk secimi):
            # vekil ciktisinin en buyuk genisligi (px). 960 = onceki sabit.
            ("genislik", "INTEGER NOT NULL DEFAULT 960"),
            ("lokasyon_id", "INTEGER"),
            ("lat", "REAL"),
            ("lon", "REAL"),
            # v2.4.2: drona bagli kamera (dron paneli kamera izleme)
            ("dron_uid", "TEXT NOT NULL DEFAULT ''"),
            # v2.4.2: kamera basina AI gorevleri (CSV):
            # yuz,plaka,hava_araci,insan,kara_araci
            ("ai_gorevler", "TEXT NOT NULL DEFAULT ''"),
            # v2.5.21 / Yerel AI angajman altyapisi: kamera iki tipten
            # biridir ve tip, yerel hedefin cografi konumunun HANGI
            # yolla cozulecegini belirler:
            #   'sabit' -> kamera sabit bir noktada; hedef konumu
            #             kalibrasyondan cozulur (lat/lon/kam_yukseklik/
            #             yon/tilt/fov) ve AYRI bir interceptor dron
            #             angaje olur. Cozum: hedef_deposu.konum_coz.
            #   'dron'  -> kamera bir dronun govdesine sabittir ve onunla
            #             hareket eder; konum dronun canli MAVLink pozundan
            #             cozulur. Cozum: hedef_deposu.hareketli_konum_coz.
            # Bos/eski kayitlar 'sabit' sayilir ama 'kalibre'=0 oldugu
            # icin angajmana ALINAMAZ (sessiz yanlis konum yerine acik
            # ret). dron_uid alani (yukarida) tip='dron' icin kaynak
            # dronu tasir.
            ("kamera_tipi", "TEXT NOT NULL DEFAULT 'sabit'"),
            # Sabit kamera kalibrasyonu (tip='sabit' icin anlamli):
            ("kam_yukseklik", "REAL"),   # kamera merceginin yer ustu yuksekligi (m)
            ("yon", "REAL"),             # kamera boresight azimutu (derece, 0=kuzey, saat yonu)
            ("tilt", "REAL"),            # boresight ufuk alti egim acisi (derece, +asagi)
            ("fov_yatay", "REAL"),       # yatay gorus acisi (derece)
            ("fov_dikey", "REAL"),       # dikey gorus acisi (derece)
            # Kamera montaj acilari (tip='dron' icin; hareketli_konum_coz):
            ("montaj_pan", "REAL"),
            ("montaj_tilt", "REAL"),
            ("montaj_roll", "REAL"),
            # 0/1: kalibrasyon eksiksiz mi? Eksikse angajman reddedilir.
            ("kalibre", "INTEGER NOT NULL DEFAULT 0"),
            # v2.5.24: sınıf başına yerel AI hassasiyeti (JSON).
            # {"insan":50,"kara_araci":50,"hava_araci":50}; 10-90.
            # Boş/eksik => 50 (işçide mevcut davranışa eşit; regresyon yok).
            ("ai_hassasiyet", "TEXT NOT NULL DEFAULT ''"),
        ],
        "ai_tespitler": [
            # v2.4.2: tespit -> ucus kaydi bagi (ucuslar.id TEXT)
            ("ucus_id", "TEXT NOT NULL DEFAULT ''"),
        ],
        "baglantilar": [
            # v2.4.142: Eski bağlantılarda alan yoktur. Varsayılan,
            # çalışmakta olan tüm MAVLink kayıtlarını ArduPilot olarak
            # korur; geçiş hiçbir port/host/baud değerini değiştirmez.
            ("ucus_yazilimi", "TEXT NOT NULL DEFAULT 'ardupilot'"),
        ],
        "rotalar": [
            # v2.4.5: rota tipi meta verisi (serbest form: koseler,
            # aralik, yon) — cift tiklama ile duzenleme icin
            ("meta", "TEXT NOT NULL DEFAULT ''"),
        ],
        "ai_sunucular": [
            # v2.4.45: AI bilgisayarini SSH ile uzaktan baslatma.
            # `ssh_sifre` duz metin TUTULMAZ; kullanici sifre girerse
            # yalniz o oturumda kullanilir. Kalici alan olarak ozel
            # anahtar YOLU (dosya yolu) saklanir — anahtarin kendisi
            # veritabaninda tutulmaz.
            ("ssh_kullanici", "TEXT NOT NULL DEFAULT ''"),
            ("ssh_port", "INTEGER NOT NULL DEFAULT 22"),
            ("ssh_anahtar", "TEXT NOT NULL DEFAULT ''"),
            ("ssh_komut", "TEXT NOT NULL DEFAULT ''"),
            # Sifre saklama kullanici tercihine baglidir (varsayilan 0)
            ("ssh_sifre", "TEXT NOT NULL DEFAULT ''"),
        ],
    }
    with baglanti() as con:
        for tablo, sutunlar in eklenecekler.items():
            mevcut = {r[1] for r in con.execute(
                f"PRAGMA table_info({tablo})").fetchall()}
            for ad, tanim in sutunlar:
                if ad not in mevcut:
                    con.execute(
                        f"ALTER TABLE {tablo} ADD COLUMN {ad} {tanim}")
        # v2.4.2: ucus bazli tespit sorgusu indeksi (goc kurulumlari)
        con.execute("CREATE INDEX IF NOT EXISTS ix_ai_tespitler_ucus"
                    " ON ai_tespitler (ucus_id, ts)")
    _v2421_goc()
    _v2422_goc()
    _v2443_goc()


def _v2421_goc():
    """v2.4.21: eski dron/ucus/parametre verisini yeni semaya tasir.

    1) dron_kayitlari + ucus_dronlari -> dronlar (kimlik kaydi)
    2) param_cache -> dron_parametreler (+ ilk kayit gecmisi)
    3) ESKI ucus verisi (ucuslar, ucus_dronlari) SILINIR
       Kullanici istegi: ucuslar artik telemetriden VIEW ile tespit
       edilir; takeoff/land tabanli eski kayitlar kullanilmaz.
    Goc bir kez calisir; 'ayarlar' tablosunda isaret birakir.
    """
    import time as _t
    with baglanti() as con:
        r = con.execute("SELECT deger FROM ayarlar WHERE anahtar=?",
                        ("goc_v2421",)).fetchone()
        if r is not None and str(r["deger"]) == "1":
            return

    simdi = _t.time()
    tasinan_dron = 0
    tasinan_param = 0
    silinen_ucus = 0

    with baglanti() as con:
        # --- 1) Eski dron kimlik kayitlari -> dronlar ---------------
        eski = {}
        try:
            for row in con.execute("SELECT uid, veri FROM dron_kayitlari"):
                uid = str(row["uid"] or "").strip()
                if not uid:
                    continue
                try:
                    veri = json.loads(row["veri"] or "{}") or {}
                except (ValueError, TypeError):
                    veri = {}
                eski[uid] = veri
        except Exception:
            eski = {}
        # ucus_dronlari renk/isim/sysid bilgisi tasiyor
        ek = {}
        try:
            for row in con.execute(
                    "SELECT anahtar, renk, isim, sysid, uid"
                    " FROM ucus_dronlari"):
                anahtar = str(row["anahtar"] or "").strip()
                if not anahtar:
                    continue
                ek[anahtar] = {"renk": row["renk"] or "",
                               "isim": row["isim"] or "",
                               "sysid": row["sysid"],
                               "uid": row["uid"] or ""}
        except Exception:
            ek = {}

        birlesik = {}
        for uid, veri in eski.items():
            birlesik[uid] = {"isim": veri.get("isim", ""),
                             "renk": veri.get("renk", ""),
                             "sysid": veri.get("sysid"),
                             "kaynak": "dron_kayitlari"}
        for anahtar, veri in ek.items():
            uid = veri.get("uid") or anahtar
            hedef = birlesik.setdefault(
                uid, {"isim": "", "renk": "", "sysid": None,
                      "kaynak": "ucus_dronlari"})
            if not hedef.get("isim"):
                hedef["isim"] = veri.get("isim", "")
            if not hedef.get("renk"):
                hedef["renk"] = veri.get("renk", "")
            if hedef.get("sysid") is None:
                hedef["sysid"] = veri.get("sysid")

        for uid, veri in birlesik.items():
            var = con.execute("SELECT id FROM dronlar WHERE uid=?",
                              (uid,)).fetchone()
            if var is not None:
                continue
            kaynak = ("autopilot_uid" if not uid.startswith("fp:")
                      else "turetilmis")
            con.execute(
                "INSERT INTO dronlar (uid, uid_kaynak, isim, renk, sysid,"
                " ilk_kayit_ts, kaydeden_eposta, kaydeden_isim,"
                " son_gorulme_ts, notlar) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (uid, kaynak, str(veri.get("isim") or ""),
                 str(veri.get("renk") or ""), veri.get("sysid"),
                 simdi, "", "", simdi,
                 "v2.4.21 gocu ile aktarildi"))
            tasinan_dron += 1

        # --- 2) param_cache -> dron_parametreler -------------------
        try:
            cache_satirlari = con.execute(
                "SELECT sysid, parametreler, okuma_ts FROM param_cache"
            ).fetchall()
        except Exception:
            cache_satirlari = []
        for row in cache_satirlari:
            sysid = row["sysid"]
            try:
                params = json.loads(row["parametreler"] or "{}") or {}
            except (ValueError, TypeError):
                params = {}
            if not params:
                continue
            d = con.execute(
                "SELECT id FROM dronlar WHERE sysid=?"
                " ORDER BY son_gorulme_ts DESC LIMIT 1",
                (int(sysid),)).fetchone()
            if d is None:
                continue
            dron_id = int(d["id"])
            ts = float(row["okuma_ts"] or simdi)
            for ad, deger in params.items():
                try:
                    v = float(deger)
                except (TypeError, ValueError):
                    continue
                cur = con.execute(
                    "INSERT OR IGNORE INTO dron_parametreler (dron_id,"
                    " ad, deger, ilk_okuma_ts, guncelleme_ts, kaynak)"
                    " VALUES (?,?,?,?,?,?)",
                    (dron_id, str(ad), v, ts, ts, "goc_v2421"))
                if cur.rowcount:
                    tasinan_param += 1

        # --- 3) Eski ucus verisini SIL -----------------------------
        # Kullanici istegi: eski (takeoff/land tabanli) ucus verisi
        # tamamen kaldirilir; ucuslar artik v_ucuslar VIEW'undan gelir.
        try:
            silinen_ucus = con.execute(
                "SELECT COUNT(*) FROM ucuslar").fetchone()[0]
            con.execute("DELETE FROM ucuslar")
        except Exception:
            silinen_ucus = 0
        try:
            con.execute("DELETE FROM ucus_dronlari")
        except Exception:
            pass
        try:
            con.execute("DELETE FROM param_cache")
        except Exception:
            pass

        con.execute(
            "INSERT INTO ayarlar (anahtar, deger) VALUES (?,?)"
            " ON CONFLICT(anahtar) DO UPDATE SET deger=excluded.deger",
            ("goc_v2421", "1"))

    if tasinan_dron or tasinan_param or silinen_ucus:
        print(f"[DB] v2.4.21 gocu: {tasinan_dron} dron kimligi, "
              f"{tasinan_param} parametre tasindi; "
              f"{silinen_ucus} eski ucus kaydi silindi.")


def _v2422_goc():
    """v2.4.22: mukerrer dron kayitlarini birlestirir (tek seferlik).

    v2.4.21'de UID beklemesi kisa oldugu icin ayni fiziksel arac hem
    turetilmis (`fp:`) hem donanim UID'si ile kaydedilmis olabilir; bu
    goc turetilmis kaydin tum verisini gercek UID'li kayda tasir.
    """
    with baglanti() as con:
        r = con.execute("SELECT deger FROM ayarlar WHERE anahtar=?",
                        ("goc_v2422",)).fetchone()
        yapildi = r is not None and str(r["deger"]) == "1"
    if not yapildi:
        try:
            birlesen = dron_mukerrer_birlestir()
        except Exception as e:
            birlesen = 0
            print(f"[DB] v2.4.22 birlestirme hatasi: {e}")
        with baglanti() as con:
            con.execute(
                "INSERT INTO ayarlar (anahtar, deger) VALUES (?,?)"
                " ON CONFLICT(anahtar) DO UPDATE SET deger=excluded.deger",
                ("goc_v2422", "1"))
        if birlesen:
            print(f"[DB] v2.4.22 gocu: {birlesen} mukerrer dron kaydi "
                  f"birlestirildi.")


def _v2443_goc():
    """v2.4.43: mukerrer telemetri satirlarini siler ve tekilleme kurar.

    ## Neden gerekli

    `telemetri_tampon.py`'deki bir kusur yuzunden (v2.4.42 ve oncesi)
    ayni tampon dosyasi Windows'ta sonsuz dongude yeniden aktariliyordu:
    dosya isaretlenemiyor (`[WinError 32]`), hata yalniz loglaniyor,
    deneme sayaci sifirlaniyor ve ayni ornekler her turda YENIDEN
    veritabanina yaziliyordu. Kullanici raporu (2026-08-09): ayni 17
    ornek tekrar tekrar aktarildi.

    Kok neden `telemetri_tampon.py`'de duzeltildi. Bu goc, ZATEN
    birikmis mukerrer satirlari temizler ve tekrarin bir daha
    olusmamasi icin tekilleme indeksi kurar.

    ## Tekilleme olcutu: (dron_id, ts)

    `ekle()` her telemetri turunda BIR kez cagrilir ve `ts` 10 ms'ye
    yuvarlanir (`round(float(simdi), 2)`). Ayni dron icin ayni 10 ms
    diliminde iki MESRU ornek beklenmez; dolayisiyla bu ikili dogal
    anahtardir.

    ## Sira onemli: ONCE temizlik, SONRA indeks

    `CREATE UNIQUE INDEX` mevcut mukerrerler yuzunden BASARISIZ olur.
    Bu yuzden once fazla satirlar silinir (en kucuk `id` korunur),
    ardindan indeks kurulur. Indeks kurulduktan sonra `INSERT` bir
    daha mukerrer uretemez.

    ## Basarisizlik durumunda ne olur

    Indeks kurulamazsa (beklenmeyen bir cakisma kalirsa) goc isareti
    BIRAKILMAZ; bir sonraki acilista yeniden denenir. Temizlik idempotent
    oldugu icin tekrar calismasi zararsizdir.
    """
    with baglanti() as con:
        r = con.execute("SELECT deger FROM ayarlar WHERE anahtar=?",
                        ("goc_v2443",)).fetchone()
        if r is not None and str(r["deger"]) == "1":
            return

    silinen = 0
    indeks_kuruldu = False
    try:
        with baglanti() as con:
            # Fazla satirlari sil: her (dron_id, ts) icin en kucuk id kalir.
            cur = con.execute(
                "DELETE FROM telemetri WHERE id NOT IN ("
                "  SELECT MIN(id) FROM telemetri GROUP BY dron_id, ts)")
            silinen = cur.rowcount or 0
        with baglanti() as con:
            con.execute("CREATE UNIQUE INDEX IF NOT EXISTS"
                        " ux_telemetri_dron_ts ON telemetri (dron_id, ts)")
            indeks_kuruldu = True
    except Exception as e:
        print(f"[DB] v2.4.43 telemetri tekilleme hatasi: {e}")

    if indeks_kuruldu:
        with baglanti() as con:
            con.execute(
                "INSERT INTO ayarlar (anahtar, deger) VALUES (?,?)"
                " ON CONFLICT(anahtar) DO UPDATE SET deger=excluded.deger",
                ("goc_v2443", "1"))
        if silinen:
            print(f"[DB] v2.4.43 gocu: {silinen} mukerrer telemetri satiri "
                  f"silindi, (dron_id, ts) tekillemesi kuruldu.")
        else:
            print("[DB] v2.4.43 gocu: (dron_id, ts) telemetri tekillemesi "
                  "kuruldu (mukerrer satir yok).")


# ------------------------------------------------------------------
# Rol/izin varsayilanlari (v2.1.7)
# ------------------------------------------------------------------
# Izin semasi: {grup: {izin: bool}}
IZIN_SEMASI = {
    "radar": ["izleme", "hedef_yonetimi", "parametre"],
    "dron": ["izleme", "kayit_yonetimi", "parametre", "pilotluk",
             "angajman"],
    "kamera": ["izleme", "kayit_yonetimi"],
    "rota": ["izleme", "kayit_yonetimi"],
    # v2.4.1: AI goruntu isleme katmani izinleri
    "ai": ["izleme", "kutuphane_yonetimi", "sunucu_yonetimi",
           "tespit_yonetimi"],
}


def tum_izinler(deger=True):
    """Semadaki tum izinleri ayni degerle iceren sozluk dondurur."""
    return {g: {i: bool(deger) for i in izinler}
            for g, izinler in IZIN_SEMASI.items()}


def _varsayilan_roller():
    """'yonetici' ve 'kullanici' rollerini yoksa tum izinlerle tohumlar.

    Mevcut davranis bozulmasin diye her iki rol de tam izinli baslar;
    kisitlamalar Rol Yonetimi popup'indan yapilir.
    """
    with baglanti() as con:
        for ad in ("yonetici", "kullanici"):
            con.execute(
                "INSERT OR IGNORE INTO roller (ad, izinler) VALUES (?,?)",
                (ad, json.dumps(tum_izinler(True))),
            )
        # v2.4.1: semaya sonradan eklenen gruplari (or. "ai") mevcut
        # rollere tam izinli olarak tohumla (idempotent gocme).
        for satir in con.execute("SELECT ad, izinler FROM roller").fetchall():
            try:
                izinler = json.loads(satir["izinler"] or "{}")
            except (ValueError, TypeError):
                izinler = {}
            degisti = False
            for grup, grup_izinleri in IZIN_SEMASI.items():
                mevcut = izinler.setdefault(grup, {})
                for izin in grup_izinleri:
                    if izin not in mevcut:
                        mevcut[izin] = True
                        degisti = True
            if degisti:
                con.execute(
                    "UPDATE roller SET izinler=? WHERE ad=?",
                    (json.dumps(izinler), satir["ad"]))


def _varsayilan_ai_sunuculari():
    """v2.4.0: Varsayilan AI islem sunucu kayitlarini tohumlar.

    - ASUS Ascent GX10: NVIDIA GB10 tabanli isci (host guncellenmeli)
    - CPU AI Sunucusu (Yerel): ana makinede otomatik baslatilan isci

    v2.4.56 — MERKEZ KIPINDE TOHUMLAMA YAPILMAZ.

    Lokal kurulumda bu iki kayit isini yapar: kullanici programi kendi
    makinesine kurar, AI iscisi ayni makinede (127.0.0.1) veya yerel
    agindaki bir kutuda (192.168.x.x) calisir; hazir kayit kolaylik
    saglar.

    Merkezde ayni tohumlama iki ayri kusur uretir:

    1. Kayitlarin ``firma_id`` alani bostur, yani hicbir kuruma ait
       degildir. Firma suzgeci sahipsiz kaydi kimseye ait saymaz; ancak
       suzgecsiz listeleyen bir yol kalirsa kayit TUM kurumlara gorunur
       ve bir kurumun AI bilgisayarinin adresi ile SSH kullanici adi
       digerlerine sizar.
    2. Adresler merkez icin anlamsizdir. Merkezde ``127.0.0.1`` merkez
       sunucusunun kendisidir, ``192.168.1.100`` ise merkezin erisemedigi
       bir ozel ag adresidir. Kullanici bu kayitlarin baslat dugmesine
       bastiginda merkez yanlis makineye baglanmaya calisir.

    Merkezde AI bilgisayarlari kullanicinin kendi koprusu altinda
    olusturulur; adres o koprunun agindan cozulur.
    """
    try:
        from . import merkez_kimlik
        if merkez_kimlik.merkez_kipinde():
            return
    except Exception:
        pass

    # v2.4.153: ORNEK KAYITLAR ARTIK TOHUMLANMAZ. GRCOFF yerel isciyi
    # main.py::_yerel_ai_kaydet gercek portuyla kendisi kaydeder; ornek
    # adresli (192.168.1.100) ve eski portlu (127.0.0.1:8900) kayitlar
    # arayuzde hayalet "yanit vermiyor" sunucular olarak kaliyordu.
    kayitlar = []
    with baglanti() as con:
        for ad, tip, host, port, kapasite, notlar in kayitlar:
            var = con.execute(
                "SELECT id FROM ai_sunucular WHERE ad=?", (ad,)
            ).fetchone()
            if var is None:
                con.execute(
                    "INSERT INTO ai_sunucular (ad, tip, host, port,"
                    " kapasite, notlar, aktif) VALUES (?,?,?,?,?,?,1)",
                    (ad, tip, host, port, kapasite, notlar))


# ------------------------------------------------------------------
# Sifre guvenligi
# ------------------------------------------------------------------
# BULGU_08 GUVENLIK: PBKDF2 tur sayisi. Merkez katmani
# (`mk_kimlik.YINELEME`) ile AYNI tutulmalidir — iki katman ayni
# sistemde farkli guvenlik duzeyi uygulamamali.
PBKDF2_YINELEME = 240_000


def sifre_hashle(sifre: str) -> str:
    """Sifreyi PBKDF2-HMAC-SHA256 + rasgele tuz ile hashler.

    Donus bicimi: ``pbkdf2_sha256$<yineleme>$<tuz_b64>$<ozet_b64>``

    NEDEN PBKDF2 (BULGU_08, 2026-08-17)
    -----------------------------------
    Eski surum tek tur SHA-256 kullaniyordu. Tuz rasgeleydi ve kayit
    basina uretiliyordu — bu dogruydu — ancak ANAHTAR ESNETME yoktu.
    Tek tur SHA-256 bir GPU'da saniyede milyarlarca kez hesaplanir;
    veritabani sizarsa parolalar hizla kirilir.

    Merkez katmani (`mk_kimlik.sifre_ozetle`) ayni is icin 240 000 tur
    PBKDF2 kullaniyordu. Ayni sistemin iki katmani farkli guvenlik
    duzeyi uygulamamali: saldirgan zayif olani secer.

    Uretilen bicim merkez bicimiyle AYNI. Bunun ek faydasi: merkezden
    esitlenen ozetler ile yerel uretilen ozetler artik ayirt edilemez,
    yani `sifre_dogrula` icindeki bicim dallanmasi sadelesir.
    """
    tuz = secrets.token_bytes(16)
    ozet = hashlib.pbkdf2_hmac(
        "sha256", sifre.encode("utf-8"), tuz, PBKDF2_YINELEME)
    return "$".join([
        "pbkdf2_sha256",
        str(PBKDF2_YINELEME),
        base64.b64encode(tuz).decode("ascii"),
        base64.b64encode(ozet).decode("ascii"),
    ])


def sifre_dogrula(sifre: str, kayitli: str) -> bool:
    """Girilen sifreyi kayitli ozet ile karsilastirir.

    UC bicim taninir:

    1. ``sha256:<tuz>:<ozet>``        -> yerel GCS bicimi
    2. ``pbkdf2_sha256$<n>$<tuz>$<ozet>`` -> MERKEZ bicimi
    3. onek yok                       -> eski duz metin (gecis donemi)

    NEDEN MERKEZ BICIMI BURADA (olculen kusur, 2026-08-16)
    ------------------------------------------------------
    Merkez Uygulama satin alan firma, merkezde (/company/ panelinde)
    tanimladigi sifre ile giris yapmak zorundadir. Merkez sifreleri
    ``pbkdf2_sha256$...`` bicimindedir. Kullanici esitlemesi bu
    ozetleri OLDUGU GIBI yerel tabloya yazar (duz sifre merkezde de
    saklanmadigi icin baska yolu yoktur). Bu dal olmadan esitlenen
    kullanici HIC giris yapamaz.

    DUZ METIN DALI NEDEN DARALTILDI
    -------------------------------
    Eski davranis, onek tanimadigi her degeri duz metin sanip
    ``sifre == kayitli`` karsilastirmasi yapiyordu. Merkez ozetleri
    tabloya girdikten sonra bu, ozet METNINI sifre olarak kabul eden
    bir kapiya donusurdu (ozet zaten API yanitlarinda gorulebilir).
    Bu yuzden bilinen ozet onekleri artik duz metne DUSMEZ; yalniz
    hicbir onegi olmayan gercek eski kayitlar duser.
    """
    kayitli = str(kayitli or "")
    if not kayitli:
        return False

    if kayitli.startswith("sha256:"):
        # ESKI BICIM — yalniz DOGRULAMA icin korunur (BULGU_08).
        # `sifre_hashle` artik bu bicimi URETMEZ. Dal kaldirilirsa
        # mevcut `sha256:` kayitlari kilitlenir; bu yuzden dogrulanir
        # ve cagiran taraf basarili girliste kaydi PBKDF2'ye
        # yukseltir (`ozet_zayif_mi` ile sorgulanir).
        parcalar = kayitli.split(":", 2)
        if len(parcalar) != 3:
            return False
        _, tuz, h = parcalar
        hesaplanan = hashlib.sha256(
            (sifre + tuz).encode("utf-8")).hexdigest()
        return secrets.compare_digest(hesaplanan, h)

    if kayitli.startswith("pbkdf2_sha256$"):
        # Merkez bicimi: pbkdf2_sha256$<yineleme>$<tuz_b64>$<ozet_b64>
        try:
            etiket, yineleme, tuz_b64, ozet_b64 = kayitli.split("$")
            if etiket != "pbkdf2_sha256":
                return False
            tuz = base64.b64decode(tuz_b64)
            beklenen = base64.b64decode(ozet_b64)
            hesap = hashlib.pbkdf2_hmac(
                "sha256", str(sifre).encode("utf-8"), tuz, int(yineleme))
            return secrets.compare_digest(hesap, beklenen)
        except Exception:
            return False

    # BULGU_08: DUZ METIN DALI KALDIRILDI (2026-08-17)
    # ------------------------------------------------------------------
    # Eski davranis, taninmayan her degeri duz metin parola sanip
    # `compare_digest(sifre, kayitli)` yapiyordu. Bu dal bir kez
    # somurulebilir hale gelmisti: merkez ozetleri tabloya girdikten
    # sonra OZET METNININ KENDISI parola olarak kabul ediliyordu ve
    # ozet API yanitlarinda gorulebiliyordu (v2.4.67 notu).
    #
    # v2.4.67'de dal daraltilmisti (`"$" in kayitli or startswith("sha")`
    # -> red) ama KALDIRILMAMISTI. Onegi olmayan tek bir kayit — yanlis
    # bir goc, elle yapilmis bir INSERT — kapiyi yeniden acardi.
    #
    # Kullanici sistemi yalniz kendisi denedi; geriye uyumluluk kisiti
    # yok. Taninmayan bicim artik KOSULSUZ reddedilir.
    return False

def ozet_zayif_mi(kayitli: str) -> bool:
    """Kayitli ozet ESKI/ZAYIF bicimde mi (yukseltilmeli mi).

    BULGU_08: `sha256:` tek tur SHA-256 bicimi anahtar esnetme
    icermez. Bu bicimdeki kayitlar basarili bir girliste sessizce
    PBKDF2'ye yukseltilmelidir — kullaniciya sifre degistirtmeye
    gerek kalmaz.
    """
    return str(kayitli or "").startswith("sha256:")

