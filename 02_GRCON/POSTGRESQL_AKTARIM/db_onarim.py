"""v2.4.25: SQLite bozulma algilama ve HEDEFLI onarim.

## Neden bu modul var

Kullanici sahada su hatayi aldi (log, 12:27:25 -> 12:30:37):

    [DB] Telemetri yazma hatasi: database disk image is malformed
         (1 satir korundu) ... (191 satir korundu)

Olculen hasar profili (`tani_bozuk_db.py`, 4,16 MB bozuk dosya):

  - Dosya basligi SAGLAM (sayfa_boyu 4096, sayfa_sayisi 1066,
    beklenen boyut = gercek boyut) -> kesik dosya DEGIL
  - `quick_check`: Tree 59 ve Tree 61 sayfalarinda yuzlerce
    `btreeInitPage() returns error code 11` (SQLITE_CORRUPT)
  - 27 tablodan **YALNIZCA `telemetri`** bozuk. Diger 26 tablo
    (kullanicilar 19, dronlar 7, dron_parametreler 1324,
    pilot_log 275, ...) tamamen okunabilir.

## Kok neden arastirmasi (8 senaryo, hicbiri bozulma uretmedi)

`tani_bozulma_uret.py` ve `tani_bozulma2.py` ile denendi:

| Senaryo | Sonuc |
|---|---|
| Esanli yazma (8 is parcasi x 400) | integrity ok |
| Yazma sirasinda `tum_baglantilari_kapat()` | **SIGSEGV**, ama integrity ok |
| Ayni baglanti nesnesi cok is parcasindan | 268 hata, integrity ok |
| Yazma sirasinda WAL/SHM silinmesi | integrity ok |
| WAL buyurken SIGKILL | integrity ok |
| Checkpoint calisirken SIGKILL | integrity ok |
| `synchronous=OFF` + checkpoint kesintisi | integrity ok |
| Tekrarli SIGKILL, 10 tur | 10/10 ok |

Sonuc: bozulma YAZILIM YOLUYLA URETILEMEDI. SQLite WAL kipi ani surec
olumune karsi dayaniklidir. Kok neden depolama katmanindadir:
antivirus/yedekleme mudahalesi, `fsync` sozunu tutmayan depolama,
ag suruculeri veya senkronize klasorler (OneDrive/Dropbox), disk
arizasi. Bunlar kullanici ortamina ozgudur.

## Bu modulun stratejisi: KOK NEDENI DEGIL, ETKISINI ORTADAN KALDIR

Bozulma `telemetri` ile sinirli kaldigi icin onarim da hedefli olur:
yalnizca `telemetri` tablosu + indeksleri dusurulup yeniden kurulur,
gorunumler tazelenir. Kullanicilar, dronlar, rotalar, parametreler,
ayarlar, pilot kayitlari **DOKUNULMAZ**.

Kullanici onayi (bu oturum): "eski verinin bir onemi yok" -> telemetri
icerigini kurtarmaya CALISILMAZ, tablo bosaltilir.

## NEDEN telemetri ayri DOSYAYA tasinmadi

Ilk tasarim telemetriyi ayri bir `.db` dosyasina almakti. Vazgecildi:
`v_telemetri_isaretli`, `v_telemetri_segment` ve `v_ucuslar` gorunumleri
`telemetri` ile `dronlar` tablosunu JOIN eder (bkz. veritabani.py:556+).
SQLite gorunumleri dosyalar arasi JOIN yapamaz; her baglantida `ATTACH`
gerekirdi ve ucus gecmisi ozelligi kirilma riski tasirdi.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import time

# `database disk image is malformed` ve akrabalarini tanimak icin.
# SQLite bu durumlari farkli metinlerle bildirir.
BOZULMA_IZLERI = (
    "database disk image is malformed",
    "database corruption",
    "malformed database schema",
    "file is not a database",
    "database or disk is full",   # ayri sorun ama ayni yolu tetikler
    # ---- v2.4.25 EKLEMESI ----
    # Kullanicinin 2.4.23'ten beri bildirdigi asil hata metni
    # `disk I/O error` (SQLITE_IOERR) idi ve bu listede YOKTU.
    # Sonuc: `calisma_zamani_onarim` ilk satirda `bozulma_mi` False
    # dondugu icin erken cikiyor, otomatik onarim HIC tetiklenmiyordu.
    # Kullanicinin "halen veri yazma hatasi var" bildiriminin dogrudan
    # nedeni bu eksiklikti.
    "disk i/o error",
    "disk image is malformed",     # kisa varyant
    "database is corrupt",
    "corrupt database",
)


def bozulma_mi(hata) -> bool:
    """Verilen istisna bir veritabani bozulmasi mi?

    `sqlite3.DatabaseError` alt siniflari ve duz metin karsilastirmasi
    birlikte kullanilir; SQLite surumleri arasi metin farklari olabilir.
    """
    if isinstance(hata, sqlite3.DatabaseError):
        metin = str(hata).lower()
        return any(iz in metin for iz in BOZULMA_IZLERI)
    return False


def butunluk_denetle(dosya: str, hizli: bool = True):
    """Veritabaninin butunlugunu denetler.

    Donus: (saglam_mi, mesaj)

    `hizli=True` ise `quick_check` kullanilir (buyuk dosyalarda
    `integrity_check` dakikalar surebilir; acilista bu kabul edilemez).
    """
    if not os.path.exists(dosya):
        return True, "dosya yok (ilk kurulum)"
    try:
        # immutable=1 KULLANILMAZ: WAL'deki taahhut edilmis veriyi de
        # gormemiz gerekir, aksi halde saglam dosya bozuk gorunebilir.
        con = sqlite3.connect(dosya, timeout=15)
        try:
            pragma = "quick_check" if hizli else "integrity_check"
            satirlar = con.execute("PRAGMA %s" % pragma).fetchall()
        finally:
            con.close()
    except sqlite3.DatabaseError as e:
        return False, "acilamadi: %s" % e

    if len(satirlar) == 1 and satirlar[0][0] == "ok":
        return True, "ok"
    return False, "; ".join(str(s[0])[:120] for s in satirlar[:3])


def bozuk_tablolari_bul(dosya: str):
    """Hangi tablolarin okunamadigini tespit eder.

    Her tabloya `SELECT COUNT(*)` calistirilir; hata verenler bozuktur.
    Donus: (bozuk_listesi, saglam_listesi)
    """
    bozuk, saglam = [], []
    try:
        con = sqlite3.connect(dosya, timeout=15)
    except sqlite3.DatabaseError:
        return ["<dosya acilamadi>"], []
    try:
        try:
            tablolar = [r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        except sqlite3.DatabaseError:
            return ["<sqlite_master okunamadi>"], []

        for t in tablolar:
            try:
                con.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()
                saglam.append(t)
            except sqlite3.DatabaseError:
                bozuk.append(t)
    finally:
        con.close()
    return bozuk, saglam


def _tablo_var(con, ad) -> bool:
    r = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (ad,)).fetchone()
    return r is not None


# Onarim sirasinda ATLANACAK nesneler: bozuk tablo ve ona bagli olanlar.
# Gorunumler yeni dosyada `_gorunumleri_olustur()` ile kurulur.
_ATLANAN_TABLOLAR = ("telemetri",)
_ATLANAN_GORUNUMLER = ("v_telemetri_isaretli", "v_telemetri_segment",
                       "v_ucuslar")


def _sqlite_master_dokum(con):
    """Sema nesnelerini (tablo/indeks/tetikleyici/gorunum) listeler.

    Donus: [(tur, ad, sql), ...] — olusturma sirasina uygun.
    `sqlite_%` ic nesneleri ve sql'i NULL olanlar (otomatik indeksler)
    atlanir.
    """
    satirlar = con.execute(
        "SELECT type, name, sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' AND sql IS NOT NULL").fetchall()
    sira = {"table": 0, "view": 1, "index": 2, "trigger": 3}
    return sorted(satirlar, key=lambda r: sira.get(r[0], 9))


# ----------------------------------------------------------------------
# v2.4.26: bayt -> metin donusumu
#
# Onarim, bozuk UTF-8 baytlarini kaybetmemek icin kaynak baglantida
# `text_factory = bytes` kullanir. Bu, kaynaktan okunan her TEXT
# degerin `bytes` gelmesi anlamina gelir. `bytes` bir parametre olarak
# baglandiginda SQLite onu BLOB olarak saklar; dolayisiyla asagidaki
# donusum YAPILMAZSA onarim sonrasi tum metin kolonlari BLOB olur ve
# uygulama `TypeError: keys must be str ... not bytes` ile coker.
# ----------------------------------------------------------------------

# SQLite tip yakinligi kurallari (bkz. SQLite belgeleri, 3. bolum):
# bildirilen tipte "CHAR", "CLOB" veya "TEXT" gecen kolon TEXT
# yakinligindadir. "BLOB" gecen veya tip bildirilmeyen kolon BLOB
# yakinligindadir.
_METIN_IZLERI = ("CHAR", "CLOB", "TEXT")


def _metin_tipi_mi(bildirilen) -> bool:
    """Kolonun bildirilen tipi METIN yakinliginda mi?"""
    if not bildirilen:
        return False
    try:
        t = str(bildirilen).upper()
    except Exception:
        return False
    if "BLOB" in t:
        return False
    return any(iz in t for iz in _METIN_IZLERI)


def _deger_donustur(deger, metin_mi: bool):
    """Tek bir degeri hedefe yazilabilir hale getirir.

    `bytes` deger METIN kolona gidiyorsa UTF-8 olarak cozulur. Gercekten
    bozuk baytlar varsa `errors="replace"` ile kurtarilir; veri kaybi
    yerine tek bir karakterin degismesi tercih edilir. BLOB kolonlara
    giden `bytes` degerlere dokunulmaz.
    """
    if not isinstance(deger, bytes) or not metin_mi:
        return deger
    try:
        return deger.decode("utf-8")
    except UnicodeDecodeError:
        return deger.decode("utf-8", errors="replace")


def _satir_donustur(satir, metin_mi_listesi):
    """Bir satirin tum degerlerini kolon tiplerine gore donusturur."""
    n = len(metin_mi_listesi)
    return tuple(
        _deger_donustur(d, metin_mi_listesi[i] if i < n else False)
        for i, d in enumerate(satir))


def _guvenli_ad(ad) -> str:
    """SAVEPOINT adi icin guvenli bir tanimlayici uretir.

    SAVEPOINT adlari parametre olarak baglanamaz; SQL metnine gomulur.
    Bu nedenle tablo/kolon adindan yalnizca harf, rakam ve alt cizgi
    korunur.
    """
    return "".join(c if (c.isalnum() or c == "_") else "_"
                   for c in str(ad))[:40] or "x"


def _yinelenen_sil(con, tablo, kolon, rid, metin_deger):
    """UNIQUE cakismasi yaratan BAYT satiri siler.

    Cagrilma kosulu: `UPDATE ... SET kolon = metin_deger` islemi
    `IntegrityError` verdi; yani ayni degere sahip bir METIN satir zaten
    var. Bayt satir uygulama tarafindan artik bulunamaz (BLOB != TEXT
    oldugu icin hicbir `WHERE kolon = ?` sorgusu ona ulasamaz), bu
    yuzden guvenle silinebilir.

    Silmeden once metin kopyanin GERCEKTEN var oldugu dogrulanir; aksi
    halde cakisma baska bir kisittan kaynaklaniyor demektir ve satira
    DOKUNULMAZ.

    Donus: (silindi_mi, aciklama)
    """
    try:
        kopya = con.execute(
            'SELECT COUNT(*) FROM "%s" WHERE "%s" = ? AND rowid <> ?'
            % (tablo, kolon), (metin_deger, rid)).fetchone()[0]
    except sqlite3.DatabaseError as e:
        return False, "kopya denetlenemedi: %s" % e

    if not kopya:
        # Cakisma bu kolondan degil (bileşik kisit, baska UNIQUE kolon
        # vb.). Satiri silmek veri kaybi olur.
        return False, "metin kopya bulunamadi, satir korundu"

    nokta = "sil_%s_%s_%d" % (_guvenli_ad(tablo), _guvenli_ad(kolon), rid)
    con.execute("SAVEPOINT %s" % nokta)
    try:
        con.execute('DELETE FROM "%s" WHERE rowid=?' % tablo, (rid,))
        con.execute("RELEASE %s" % nokta)
        return True, "silindi"
    except sqlite3.DatabaseError as e:
        con.execute("ROLLBACK TO %s" % nokta)
        con.execute("RELEASE %s" % nokta)
        return False, "silinemedi: %s" % e


def metin_kolonlarini_onar(dosya: str, konsol=None):
    """Onceki hatali onarimin BLOB'a cevirdigi metin kolonlarini duzeltir.

    v2.4.25 ve oncesindeki onarim, hedef baglantida da
    `text_factory = bytes` kullandigi icin aktarilan tum TEXT kolonlari
    BLOB olarak yazmisti. Bu fonksiyon, ETKILENMIS bir veritabanini
    yerinde duzeltir: bildirilen tipi metin olan kolonlardaki BLOB
    degerler UTF-8 metne cevrilir.

    ## v2.4.27: UNIQUE CAKISMASI (kullanici sahada aldi)

    v2.4.26 gocu bazi satirlari duzeltemedi:

        [DB] yazilamadi roller.ad rowid=2: UNIQUE constraint failed
        [DB] yazilamadi ayarlar.anahtar rowid=10: UNIQUE constraint failed
        [WS] Komut hatasi (rol_listesi): keys must be str ... not bytes

    Nedeni: v2.4.25 onarimindan SONRA uygulama bir sure calisti ve yeni
    satirlar yazdi. `INSERT OR REPLACE` / `ON CONFLICT(ad)` kullanan
    yollar, bayt satirla CAKISMADI — cunku SQLite BLOB ile TEXT'i esit
    saymaz. Sonucta ayni mantiksal anahtar iki satir olarak yasamaya
    basladi:

        rowid=1  blob  b'yonetici'   <- v2.4.25 onarimindan
        rowid=3  text  'yonetici'    <- sonradan uygulama yazdi

    `UPDATE ... SET ad='yonetici'` calistiginda ikinci satirla cakisir.
    Bu durumda BAYT SATIR SILINIR ve metin satir korunur; metin satir
    daha yeni yazilmis oldugu icin guncel veriyi tasir.

    Donus: (duzeltildi_mi, mesaj)
    """
    def bildir(m, seviye="bilgi"):
        if konsol:
            try:
                konsol("DB", m, seviye)
            except TypeError:
                konsol("DB", m)

    if not os.path.exists(dosya):
        return False, "dosya yok"

    con = None
    try:
        con = sqlite3.connect(dosya, timeout=30)
        tablolar = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'")]
        toplam = 0
        silinen_toplam = 0
        etkilenen_tablolar = []
        silinen_tablolar = []
        for tablo in tablolar:
            try:
                bilgi = list(con.execute(
                    'PRAGMA table_info("%s")' % tablo))
            except sqlite3.DatabaseError:
                continue
            metin_kolonlar = [r[1] for r in bilgi if _metin_tipi_mi(r[2])]
            if not metin_kolonlar:
                continue
            # Anahtar kolonlari: WHERE rowid = ? kullanilabilmesi icin
            # rowid'siz (WITHOUT ROWID) tablolar atlanir.
            try:
                con.execute('SELECT rowid FROM "%s" LIMIT 1' % tablo)
            except sqlite3.DatabaseError:
                bildir("rowid yok, atlandi: %s" % tablo, "uyari")
                continue
            tablo_sayaci = 0
            tablo_silinen = 0
            for kolon in metin_kolonlar:
                try:
                    bozuk = con.execute(
                        'SELECT rowid, "%s" FROM "%s" '
                        "WHERE typeof(\"%s\")='blob'"
                        % (kolon, tablo, kolon)).fetchall()
                except sqlite3.DatabaseError as e:
                    bildir("okunamadi %s.%s: %s" % (tablo, kolon, e),
                           "uyari")
                    continue
                for rid, ham in bozuk:
                    if not isinstance(ham, bytes):
                        continue
                    try:
                        yeni = ham.decode("utf-8")
                    except UnicodeDecodeError:
                        yeni = ham.decode("utf-8", errors="replace")
                    # Her satir kendi kaydedilme noktasinda islenir; bir
                    # satirin basarisizligi digerlerini geri almamali.
                    nokta = "goc_%s_%s_%d" % (
                        _guvenli_ad(tablo), _guvenli_ad(kolon), rid)
                    con.execute("SAVEPOINT %s" % nokta)
                    try:
                        con.execute(
                            'UPDATE "%s" SET "%s"=? WHERE rowid=?'
                            % (tablo, kolon), (yeni, rid))
                        con.execute("RELEASE %s" % nokta)
                        tablo_sayaci += 1
                    except sqlite3.IntegrityError:
                        # UNIQUE cakismasi: ayni mantiksal anahtarin
                        # metin kopyasi zaten var. Bayt satir artik
                        # erisilemez bir kalintidir ve SILINIR.
                        con.execute("ROLLBACK TO %s" % nokta)
                        con.execute("RELEASE %s" % nokta)
                        silindi, not_ = _yinelenen_sil(
                            con, tablo, kolon, rid, yeni)
                        if silindi:
                            tablo_silinen += 1
                        else:
                            bildir("cozulemedi %s.%s rowid=%s: %s"
                                   % (tablo, kolon, rid, not_), "uyari")
                    except sqlite3.DatabaseError as e:
                        con.execute("ROLLBACK TO %s" % nokta)
                        con.execute("RELEASE %s" % nokta)
                        bildir("yazilamadi %s.%s rowid=%s: %s"
                               % (tablo, kolon, rid, e), "uyari")
            if tablo_sayaci:
                etkilenen_tablolar.append("%s(%d)" % (tablo, tablo_sayaci))
                toplam += tablo_sayaci
            if tablo_silinen:
                silinen_tablolar.append("%s(%d)" % (tablo, tablo_silinen))
                silinen_toplam += tablo_silinen
        con.commit()
        if toplam or silinen_toplam:
            parcalar = []
            if toplam:
                parcalar.append("%d deger BLOB'dan metne cevrildi: %s"
                                % (toplam, ", ".join(etkilenen_tablolar)))
            if silinen_toplam:
                parcalar.append(
                    "%d yinelenen eski satir silindi (guncel metin "
                    "kopyasi korundu): %s"
                    % (silinen_toplam, ", ".join(silinen_tablolar)))
            mesaj = " | ".join(parcalar)
            bildir(mesaj)
            return True, mesaj
        return False, "duzeltme gerekmedi"
    except sqlite3.DatabaseError as e:
        return False, "hata: %s" % e
    finally:
        if con is not None:
            try:
                con.close()
            except sqlite3.Error:
                pass


def telemetri_sifirla(dosya: str, konsol=None):
    """Veritabanini YENIDEN INSA eder; `telemetri` bos kurulur.

    DIGER TUM TABLOLARIN VERISI KORUNUR.

    ## Neden `DROP TABLE` kullanilmiyor (v2.4.25 olcumu)

    Ilk surumde `DROP TABLE telemetri` denendi ve GERCEK bozuk dosya
    uzerinde BASARISIZ oldu:

        3) HEDEFLI ONARIM: telemetri_sifirla()
           sonuc: False | onarim basarisiz: database disk image is malformed

    Sebep: `DROP TABLE` sayfalari serbest listeye almak icin B-tree'yi
    DOLASMAK zorundadir; bozuk sayfaya rastlayinca `SQLITE_CORRUPT`
    firlatir. Bozuk bir tablo DUSURULEMEZ.

    Ayrica o surum yan hasar biraktı: gorunumler `DROP TABLE`'dan ONCE
    dusuruldugu icin, tablo dusurme basarisiz olunca gorunumler silinmis
    halde kaldi (`v_ucuslar` dahil uc gorunum kayboldu).

    ## Kullanilan yontem: yeni dosyaya kopyala + atomik yer degistirme

    Bozuk sayfalara HIC DOKUNULMAZ:

      1. Yeni bos dosya olustur (`<dosya>.onarim_<zaman>`)
      2. Kaynaktan sema nesnelerini kopyala (`telemetri` ve ona bagli
         gorunumler HARIC)
      3. Saglam tablolarin verisini satir satir aktar
      4. `telemetri`yi TELEMETRI_SEMA ile BOS kur
      5. Basari halinde atomik `os.replace` ile yerine koy;
         eski dosya `<dosya>.bozuk_<zaman>` olarak saklanir

    Herhangi bir adim basarisiz olursa gecici dosya silinir ve KAYNAK
    DOSYAYA DOKUNULMAZ — yan hasar imkansizdir.

    Kullanici onayi: "eski verinin bir onemi yok" -> bozuk `telemetri`
    icerigi kurtarilmaya CALISILMAZ.

    Donus: (basarili_mi, mesaj)
    """
    def bildir(m, tur="bilgi"):
        if konsol:
            konsol("DB", m, tur)

    if not os.path.exists(dosya):
        return False, "dosya yok: %s" % dosya

    damga = time.strftime("%Y%m%d_%H%M%S")
    gecici = "%s.onarim_%s" % (dosya, damga)
    for ek in ("", "-wal", "-shm"):
        if os.path.exists(gecici + ek):
            try:
                os.remove(gecici + ek)
            except OSError:
                pass

    kaynak = hedef = None
    aktarilan = {}
    atlanan_satir = {}
    try:
        # ONEMLI: sema okumasi METIN baglantisiyla yapilir, veri aktarimi
        # BAYT baglantisiyla. `text_factory = bytes` sema sorgusunda da
        # etkili olsaydi tablo adlari bayt donerdi ve `_ATLANAN_TABLOLAR`
        # karsilastirmasi HER ZAMAN basarisiz olurdu (telemetri atlanmaz).
        sema_con = sqlite3.connect(dosya, timeout=30)
        try:
            nesneler = _sqlite_master_dokum(sema_con)
            # Kolon adlari da metin olarak alinmali.
            kolon_haritasi = {}
            # v2.4.26: her kolonun METIN olup olmadigi. `PRAGMA
            # table_info` uc numarali alanda bildirilen tipi verir
            # (TEXT, INTEGER, REAL, BLOB, ...). SQLite tipi zorunlu
            # tutmaz, ancak onarimda bildirilen tipe uymak dogru
            # davranistir: BLOB bildirilen kolon BLOB kalir, TEXT
            # bildirilen kolon TEXT olarak yazilir.
            metin_kolon_haritasi = {}
            for _t, _a, _s in nesneler:
                if _t != "table":
                    continue
                try:
                    _bilgi = list(sema_con.execute(
                        'PRAGMA table_info("%s")' % _a))
                    kolon_haritasi[_a] = [r[1] for r in _bilgi]
                    metin_kolon_haritasi[_a] = [
                        _metin_tipi_mi(r[2]) for r in _bilgi]
                except sqlite3.DatabaseError:
                    kolon_haritasi[_a] = []
                    metin_kolon_haritasi[_a] = []
            # sqlite_sequence degerleri (metin adlarla)
            try:
                dizi_degerleri = list(sema_con.execute(
                    "SELECT name, seq FROM sqlite_sequence"))
            except sqlite3.DatabaseError:
                dizi_degerleri = []
        finally:
            sema_con.close()

        kaynak = sqlite3.connect(dosya, timeout=30)
        # Bozuk UTF-8 baytlari da tasinsin; `TEXT` kolonlarda gecersiz
        # bayt dizileri varsa `str` donusumu UnicodeDecodeError verirdi.
        # Bu YALNIZCA OKUMA yonu icindir.
        kaynak.text_factory = bytes
        hedef = sqlite3.connect(gecici, timeout=30)
        # ## v2.4.26 KRITIK DUZELTME
        #
        # Burada eskiden `hedef.text_factory = bytes` yaziliydi.
        # `text_factory`nin yalnizca okuma yonunu etkiledigi
        # varsayilmisti. Gercek: kaynaktan okunan her `TEXT` deger
        # `bytes` nesnesi olarak gelir ve `bytes` bir parametre olarak
        # baglandiginda SQLite onu **BLOB** olarak saklar. Sonuc:
        # onarim sonrasi veritabanindaki TUM metin kolonlari BLOB olur.
        #
        # Olculen etki (`testler/tani_bytes_anahtar.py`):
        #
        #   Onarim oncesi: 'tema' anahtar=text  deger=text
        #   Onarim sonrasi: b'tema' anahtar=blob deger=blob
        #
        # Bunun uzerine `ayarlar.yukle()` sozluk anahtarlarini `bytes`
        # olarak dondurdu ve `sunucu.py:544` her arayuz baglantisinda
        # coktu:
        #
        #   TypeError: keys must be str, int, float, bool or None,
        #              not bytes
        #
        # Hasar `ayarlar` ile sinirli degildi; `kullanicilar.eposta`
        # de BLOB oldugu icin giris dogrulamasi da bozulmustu.
        #
        # Cozum: hedefte `text_factory` DEGISTIRILMEZ ve aktarim
        # sirasinda her deger `_deger_donustur()` ile kolonun bildirilen
        # tipine gore metne cevrilir.
        hedef.execute("PRAGMA journal_mode=WAL")
        # Aktarim sirasinda kisitlar kapali; sira bagimliligi olmasin.
        hedef.execute("PRAGMA foreign_keys=OFF")
        tablolar = [(a, s) for t, a, s in nesneler if t == "table"
                    and a not in _ATLANAN_TABLOLAR]
        digerleri = [(t, a, s) for t, a, s in nesneler
                     if t != "table"
                     and a not in _ATLANAN_GORUNUMLER
                     and not a.startswith("ix_telemetri")]

        # 1) Tablo semalarini kur
        for ad, sql in tablolar:
            try:
                hedef.execute(sql)
            except sqlite3.DatabaseError as e:
                bildir("Sema kurulamadi (%s): %s" % (ad, e), "uyari")

        # 2) `telemetri`yi BOS kur (tek kaynak semadan)
        from .veritabani import TELEMETRI_SEMA
        hedef.executescript(TELEMETRI_SEMA)
        hedef.commit()

        # 3) Verileri aktar
        for ad, _sql in tablolar:
            kolonlar = kolon_haritasi.get(ad) or []
            if not kolonlar:
                continue
            # v2.4.26: hangi kolonlar METIN? Yalnizca onlarda bayt ->
            # metin donusumu yapilir; gercek BLOB kolonlari korunur.
            metin_mi = metin_kolon_haritasi.get(ad) or [False] * len(kolonlar)
            kolon_ifade = ",".join('"%s"' % k for k in kolonlar)
            yer = ",".join("?" * len(kolonlar))
            ekle = ('INSERT OR IGNORE INTO "%s" (%s) VALUES (%s)'
                    % (ad, kolon_ifade, yer))
            n = hata = 0
            try:
                imlec = kaynak.execute(
                    'SELECT %s FROM "%s"' % (kolon_ifade, ad))
                while True:
                    try:
                        yigin = imlec.fetchmany(500)
                    except sqlite3.DatabaseError:
                        # Bozuk sayfaya rastlandi; bu tablonun kalani
                        # okunamaz ama okunanlar korunur.
                        hata += 1
                        break
                    if not yigin:
                        break
                    # v2.4.26: bayt -> metin donusumu (BLOB'a yazmayi
                    # onler). Bkz. yukaridaki KRITIK DUZELTME notu.
                    yigin = [_satir_donustur(s, metin_mi) for s in yigin]
                    try:
                        hedef.executemany(ekle, yigin)
                        n += len(yigin)
                    except sqlite3.DatabaseError:
                        # Yigin halinde yazilamadi; satir satir dene
                        for s in yigin:
                            try:
                                hedef.execute(ekle, s)
                                n += 1
                            except sqlite3.DatabaseError:
                                hata += 1
                hedef.commit()
            except sqlite3.DatabaseError as e:
                bildir("Tablo aktarilamadi (%s): %s" % (ad, e), "uyari")
            aktarilan[ad] = n
            if hata:
                atlanan_satir[ad] = hata

        # 4) Indeks / tetikleyici / gorunumler
        #    Gorunumler `_gorunumleri_olustur()` ile kurulacagi icin
        #    burada yalnizca digerleri denenir.
        for tur, ad, sql in digerleri:
            if tur == "view":
                continue
            try:
                hedef.execute(sql)
            except sqlite3.DatabaseError as e:
                bildir("%s kurulamadi (%s): %s" % (tur, ad, e), "uyari")

        # 5) sqlite_sequence degerlerini koru (AUTOINCREMENT surekliligi)
        for ad, deger in dizi_degerleri:
            if ad in _ATLANAN_TABLOLAR:
                continue
            try:
                hedef.execute(
                    "UPDATE sqlite_sequence SET seq=? WHERE name=?",
                    (deger, ad))
            except sqlite3.DatabaseError:
                pass

        hedef.execute("PRAGMA foreign_keys=ON")
        hedef.commit()
        try:
            hedef.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.DatabaseError:
            pass
    except sqlite3.DatabaseError as e:
        for c in (kaynak, hedef):
            try:
                if c:
                    c.close()
            except sqlite3.Error:
                pass
        for ek in ("", "-wal", "-shm"):
            try:
                if os.path.exists(gecici + ek):
                    os.remove(gecici + ek)
            except OSError:
                pass
        return False, "yeniden insa basarisiz: %s" % e

    for c in (kaynak, hedef):
        try:
            if c:
                c.close()
        except sqlite3.Error:
            pass

    # Yeni dosya gercekten saglam mi? DEGILSE kaynaga dokunma.
    saglam, mesaj = butunluk_denetle(gecici, hizli=False)
    if not saglam:
        for ek in ("", "-wal", "-shm"):
            try:
                if os.path.exists(gecici + ek):
                    os.remove(gecici + ek)
            except OSError:
                pass
        return False, "yeni dosya da bozuk: %s" % mesaj

    # Atomik yer degistirme. Eski dosya saklanir (silinmez).
    eski = "%s.bozuk_%s" % (dosya, damga)
    try:
        for ek in ("-wal", "-shm"):
            if os.path.exists(dosya + ek):
                try:
                    os.remove(dosya + ek)
                except OSError:
                    pass
        os.replace(dosya, eski)
        os.replace(gecici, dosya)
        for ek in ("-wal", "-shm"):
            if os.path.exists(gecici + ek):
                try:
                    os.replace(gecici + ek, dosya + ek)
                except OSError:
                    pass
    except OSError as e:
        return False, "yer degistirme basarisiz: %s" % e

    ozet = ", ".join("%s=%d" % (a, n)
                     for a, n in sorted(aktarilan.items()) if n)
    bildir("Yeniden insa tamam. Aktarilan: %s" % (ozet or "(bos)"))
    if atlanan_satir:
        bildir("Okunamayan satir olan tablolar: %s"
               % ", ".join("%s=%d" % (a, n)
                           for a, n in sorted(atlanan_satir.items())),
               "uyari")
    bildir("Eski dosya saklandi: %s" % os.path.basename(eski))

    # Gorunumleri kur (veritabani.py havuzunu kullanir).
    #
    # DIKKAT — `tum_baglantilari_kapat()` BURADA CAGRILMAZ:
    # v2.4.25 olcumu, o fonksiyonun BASKA is parcasindan cagrilmasinin
    # SIGSEGV (C seviyesi bellek ihlali) urettigini kanitladi. Bir is
    # parcasi SQLite baglantisini kullanirken baska bir is parcasi
    # `close()` cagirinca serbest birakilmis yapiya erisilir. Bu Python
    # istisnasi DEGILDIR; try/except yakalamaz, surec komple oler.
    #
    # Onarim canli ucus sirasinda tetiklenebilir (telemetri yazma
    # hatasinda), yani diger is parcaciklari AKTIF yazma yapiyor olabilir.
    #
    # Cozum: baglantilari kapatmak yerine GECERSIZ KIL. `baglanti()`
    # her cagrida `SELECT 1` ile canlilik dogruluyor (satir 152); dosya
    # `os.replace` ile degistigi icin eski tanitici olu kalir ve her is
    # parcasi KENDI baglantisini kendi icinde yeniler. Kapatma islemi
    # boylece sahibi olan is parcasinda gerceklesir.
    try:
        from . import veritabani as _vt
        # Yalnizca BU is parcasinin baglantisi kapatilir (guvenli).
        _vt.baglanti_kapat()
        _vt._gorunumleri_olustur()
        bildir("Ucus tespiti gorunumleri olusturuldu.")
    except Exception as e:
        bildir("Gorunumler olusturulamadi: %s" % e, "uyari")

    return True, ("yeniden insa edildi; telemetri bos, "
                  "%d tablo aktarildi" % len([1 for n in
                                              aktarilan.values() if n]))


def dosyayi_kenara_al(dosya: str, konsol=None):
    """Bozuk veritabanini yeniden adlandirir; yeni dosya olusturulacak.

    SON CARE. `telemetri_sifirla` basarisiz olursa kullanilir; tum
    veriler (kullanicilar dahil) yeni dosyada SIFIRDAN kurulur.
    Eski dosya `gcs.db.bozuk_<zaman>` olarak SAKLANIR (silinmez).

    Donus: (basarili_mi, yeni_ad_veya_mesaj)
    """
    if not os.path.exists(dosya):
        return True, "dosya yok"
    damga = time.strftime("%Y%m%d_%H%M%S")
    hedef = "%s.bozuk_%s" % (dosya, damga)
    try:
        # WAL/SHM de tasinir; aksi halde yeni dosya eski WAL'i okur.
        shutil.move(dosya, hedef)
        for ek in ("-wal", "-shm"):
            if os.path.exists(dosya + ek):
                try:
                    shutil.move(dosya + ek, hedef + ek)
                except OSError:
                    try:
                        os.remove(dosya + ek)
                    except OSError:
                        pass
    except OSError as e:
        return False, "tasinamadi: %s" % e

    if konsol:
        konsol("DB", "Bozuk veritabani kenara alindi: %s"
               % os.path.basename(hedef), "uyari")
    return True, hedef


def acilis_denetimi(dosya: str, konsol=None):
    """Acilista butunluk denetimi yapar; bozuksa hedefli onarim dener.

    Donus: sozluk
        {"saglam": bool, "onarildi": bool, "yontem": str, "mesaj": str}

    Sira:
      1. `quick_check` -> saglamsa cik (hizli yol)
      2. Bozuksa hangi tablolarin bozuk oldugunu belirle
      3. Yalnizca `telemetri` bozuksa -> `telemetri_sifirla`
      4. Baska tablolar da bozuksa -> dosyayi kenara al (son care)
    """
    def bildir(m, tur="bilgi"):
        if konsol:
            konsol("DB", m, tur)

    saglam, mesaj = butunluk_denetle(dosya, hizli=True)

    # v2.4.26 GOC: v2.4.25 onarimi tum metin kolonlari BLOB'a
    # cevirmisti. Etkilenmis bir kurulumda veritabani BUTUNLUK
    # DENETIMINI GECER (dosya saglamdir) ama uygulama
    # `TypeError: keys must be str ... not bytes` ile coker. Bu
    # nedenle goc, saglamlik denetiminden BAGIMSIZ olarak calisir.
    try:
        goc_ok, goc_mesaj = metin_kolonlarini_onar(dosya, konsol)
        if goc_ok:
            bildir("v2.4.26 goc: %s" % goc_mesaj)
    except Exception as e:              # goc hicbir zaman acilisi engellemez
        bildir("v2.4.26 goc denenemedi: %s" % e, "uyari")

    if saglam:
        return {"saglam": True, "onarildi": False,
                "yontem": "yok", "mesaj": mesaj}

    bildir("Veritabani butunluk denetimi BASARISIZ: %s" % mesaj, "hata")

    bozuk, saglam_tablolar = bozuk_tablolari_bul(dosya)
    bildir("Bozuk tablo(lar): %s | saglam: %d tablo"
           % (", ".join(bozuk) if bozuk else "belirlenemedi",
              len(saglam_tablolar)), "uyari")

    # Yalnizca telemetri bozuksa hedefli onarim yeter.
    if bozuk == ["telemetri"]:
        ok, m = telemetri_sifirla(dosya, konsol)
        if ok:
            bildir("Hedefli onarim BASARILI: telemetri sifirlandi, "
                   "diger %d tablo korundu." % len(saglam_tablolar))
            return {"saglam": True, "onarildi": True,
                    "yontem": "telemetri_sifirla", "mesaj": m}
        bildir("Hedefli onarim basarisiz: %s" % m, "hata")

    # Son care: dosyayi kenara al.
    ok, m = dosyayi_kenara_al(dosya, konsol)
    if ok:
        return {"saglam": True, "onarildi": True,
                "yontem": "dosya_kenara", "mesaj": m}
    return {"saglam": False, "onarildi": False,
            "yontem": "basarisiz", "mesaj": m}


# ------------------------------------------------------------------
# Calisma zamani onarimi (yazma hatasi aninda)
# ------------------------------------------------------------------
_son_onarim = 0.0
ONARIM_ARA = 60.0     # s; ayni dakika icinde tekrar onarim denenmez


def calisma_zamani_onarim(dosya: str, hata, konsol=None) -> bool:
    """Yazma hatasi bozulma kaynakliysa hedefli onarim dener.

    `sunucu.py` telemetri yazma hatasinda cagirir. Ayni hata saniyede
    bir tekrarlayabilecegi icin onarim en fazla `ONARIM_ARA` saniyede
    bir denenir; aksi halde onarim dongusune girilir.

    Donus: onarim yapildi mi (True ise cagiran taraf yazmayi
    yeniden denemelidir).
    """
    global _son_onarim

    if not bozulma_mi(hata):
        return False

    simdi = time.time()
    if (simdi - _son_onarim) < ONARIM_ARA:
        return False
    _son_onarim = simdi

    if konsol:
        konsol("DB", "Bozulma algilandi, hedefli onarim baslatiliyor: %s"
               % hata, "uyari")

    # Havuzdaki baglantilar bozuk dosyaya bakiyor; kapatilmali.
    # DIKKAT: `tum_baglantilari_kapat` BASKA is parcasindan cagrilirsa
    # SIGSEGV riski vardir (v2.4.25 bulgusu). Bu yuzden yalnizca BU is
    # parcasinin baglantisi kapatilir.
    try:
        from . import veritabani as _vt
        _vt.baglanti_kapat()
    except Exception:
        pass

    ok, m = telemetri_sifirla(dosya, konsol)
    if ok:
        if konsol:
            konsol("DB", "Onarim tamamlandi: %s" % m)
        return True
    if konsol:
        konsol("DB", "Onarim basarisiz: %s" % m, "hata")
    return False


def durum(dosya: str):
    """Tanilama: veritabani saglik ozeti (arayuz/log icin)."""
    d = {"dosya": dosya, "var": os.path.exists(dosya)}
    if not d["var"]:
        return d
    d["boyut"] = os.path.getsize(dosya)
    for ek in ("-wal", "-shm"):
        p = dosya + ek
        d["boyut" + ek.replace("-", "_")] = (
            os.path.getsize(p) if os.path.exists(p) else 0)
    saglam, mesaj = butunluk_denetle(dosya, hizli=True)
    d["saglam"] = saglam
    d["denetim"] = mesaj
    if not saglam:
        bozuk, ok_tablolar = bozuk_tablolari_bul(dosya)
        d["bozuk_tablolar"] = bozuk
        d["saglam_tablo_sayisi"] = len(ok_tablolar)
    return d
