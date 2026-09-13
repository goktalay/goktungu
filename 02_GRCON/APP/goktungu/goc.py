"""GOKTUNGU v2.4.51 — Sema surum defteri ve ilerleme bildirimli goc motoru.

Neden bu modul var
------------------
v2.4.50'ye kadar sema gocleri `veritabani._sema_guncelle()` icinde
dagitik yapiliyordu ve `ayarlar` tablosuna `goc_v2421` gibi tek tek
isaretler birakiliyordu. Bu yaklasimin UC eksigi olculdu:

1. **Merkezi sema surumu YOK.** "Bu veritabani hangi surumde?" sorusu
   cevaplanamiyordu; her goc kendi isaretini ayri okuyordu.
2. **Ilerleme bildirimi YOK.** Kullanici uzun bir goc sirasinda
   (ornegin 100 bin telemetri satiri tekillemesi) programin donup
   kalmadigini anlayamiyordu.
3. **Denetlenebilir defter YOK.** Hangi adim ne zaman, ne kadar surede
   uygulandi bilgisi tutulmuyordu; bir goc yarida kesilirse durum
   belirsizdi.

Bu modul ucunu birden cozer:

- `sema_surumu()` / `sema_surumu_yaz()` — merkezi surum numarasi
- `sema_goc_defteri` tablosu — her adim icin kayit (ad, surum, ts, sure,
  durum, hata)
- `GocMotoru.calistir(ilerleme=...)` — her adimda geri cagirma ile
  ilerleme yuzdesi ve **ne yapildigini anlatan** ileti

Tasarim kararlari
-----------------
- **Adimlar idempotent olmak ZORUNDA.** Defter kaydi olsa bile adim
  yeniden calisabilir; bu, yarida kesilen goclerden kurtulmayi saglar.
- **Defter kaydi adim BASARILI olduktan sonra yazilir.** Once yazilirsa
  yarida kesilen adim "uygulandi" gorunur ve bir daha calismaz —
  veritabani tutarsiz kalir.
- **Adim basarisiz olursa goc DURUR.** Sonraki adimlar oncekine
  dayanabilir; korlemesine devam etmek veriyi bozar.
- Her adim kendi islemini (transaction) yonetir; boylece basarili
  adimlar korunur.
"""
from __future__ import annotations

import time
import traceback
from typing import Callable, Optional

# Bu surumun bekledigi sema surumu. Yeni goc adimi eklendiginde
# ARTIRILIR ve `ADIMLAR` listesine karsilik gelen adim yazilir.
SEMA_SURUMU = 2467

# Goc defteri tablosu. `veritabani.tablolari_olustur()` icinde degil
# BURADA olusturulur; cunku goc motoru tablolar kurulmadan once de
# calisabilmeli (ilk kurulum durumu).
_DEFTER_SQL = """
CREATE TABLE IF NOT EXISTS sema_goc_defteri (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    adim      TEXT NOT NULL,
    surum     INTEGER NOT NULL,
    ts        REAL NOT NULL,
    sure_ms   INTEGER NOT NULL DEFAULT 0,
    durum     TEXT NOT NULL DEFAULT 'tamam',
    ileti     TEXT NOT NULL DEFAULT '',
    hata      TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_goc_adim
    ON sema_goc_defteri (adim);
"""


# ==================================================================
# Sema surumu
# ==================================================================
def defter_kur():
    """Goc defteri tablosunu olusturur (idempotent)."""
    from . import veritabani as vt
    with vt.baglanti() as con:
        for parca in _DEFTER_SQL.strip().split(";"):
            if parca.strip():
                con.execute(parca)


def sema_surumu() -> int:
    """Veritabanindaki mevcut sema surumunu dondurur.

    Defter tablosu yoksa 0 doner (ilk kurulum). `ayarlar` tablosundaki
    eski `goc_v*` isaretleri de dikkate alinir: bunlar varsa veritabani
    bos DEGILDIR ve en azindan o surumdedir.
    """
    from . import veritabani as vt
    try:
        with vt.baglanti() as con:
            r = con.execute(
                "SELECT deger FROM ayarlar WHERE anahtar=?",
                ("sema_surumu",)).fetchone()
            if r is not None:
                try:
                    return int(str(r["deger"]).strip() or 0)
                except (ValueError, TypeError):
                    pass
    except Exception:
        return 0

    # Eski kurulum tespiti: `goc_v2421` isareti varsa sema en az 2421
    try:
        with vt.baglanti() as con:
            r = con.execute(
                "SELECT deger FROM ayarlar WHERE anahtar=?",
                ("goc_v2421",)).fetchone()
            if r is not None and str(r["deger"]) == "1":
                return 2421
    except Exception:
        pass
    return 0


def sema_surumu_yaz(surum: int):
    """Sema surumunu kaydeder."""
    from . import veritabani as vt
    with vt.baglanti() as con:
        con.execute(
            "INSERT OR REPLACE INTO ayarlar (anahtar, deger) VALUES (?,?)",
            ("sema_surumu", str(int(surum))))


def adim_uygulandi_mi(adim: str) -> bool:
    """Adim daha once BASARIYLA uygulandi mi."""
    from . import veritabani as vt
    try:
        with vt.baglanti() as con:
            r = con.execute(
                "SELECT durum FROM sema_goc_defteri WHERE adim=?",
                (adim,)).fetchone()
            return r is not None and str(r["durum"]) == "tamam"
    except Exception:
        return False


def adim_kaydet(adim: str, surum: int, sure_ms: int,
                durum: str = "tamam", ileti: str = "", hata: str = ""):
    """Adimi deftere yazar.

    KRITIK: yalnizca adim BASARILI olduktan sonra cagrilir. Once
    yazilsaydi yarida kesilen adim 'uygulandi' gorunur ve bir daha
    calismaz -> veritabani tutarsiz kalir.
    """
    from . import veritabani as vt
    with vt.baglanti() as con:
        con.execute(
            "INSERT OR REPLACE INTO sema_goc_defteri"
            " (adim, surum, ts, sure_ms, durum, ileti, hata)"
            " VALUES (?,?,?,?,?,?,?)",
            (adim, int(surum), time.time(), int(sure_ms),
             durum, ileti[:500], hata[:1000]))


def defter_oku():
    """Defterdeki tum kayitlari dondurur (yeniden eskiye)."""
    from . import veritabani as vt
    try:
        with vt.baglanti() as con:
            return [dict(r) for r in con.execute(
                "SELECT adim, surum, ts, sure_ms, durum, ileti, hata"
                " FROM sema_goc_defteri ORDER BY ts DESC").fetchall()]
    except Exception:
        return []


# ==================================================================
# Goc adimlari
# ==================================================================
class Adim:
    """Tek bir goc adimi.

    `ad`: defterdeki benzersiz ad
    `surum`: bu adimin ait oldugu sema surumu
    `aciklama`: kullaniciya GOSTERILEN ileti (sihirbazda okunur)
    `islev`: `islev(con, bildir)` — `bildir(yuzde, ileti)` ile alt
             ilerleme bildirebilir (uzun adimlar icin)
    `agirlik`: toplam ilerleme icindeki agirligi (uzun adimlar > 1)
    """

    def __init__(self, ad: str, surum: int, aciklama: str,
                 islev: Callable, agirlik: int = 1):
        self.ad = ad
        self.surum = surum
        self.aciklama = aciklama
        self.islev = islev
        self.agirlik = max(1, int(agirlik))


def _adim_tablolar(con, bildir):
    """27 tabloyu ve 3 gorunumu olusturur."""
    from . import veritabani as vt
    bildir(10, "Tablolar olusturuluyor")
    vt.tablolari_olustur()
    bildir(100, "Tablolar hazir")
    return "27 tablo, 3 gorunum"


def _adim_citext(con, bildir):
    """`citext` eklentisini kurar (buyuk/kucuk harf duyarsiz e-posta)."""
    from . import pg
    from . import veritabani as vt
    if not vt.pg_kipinde():
        return "PG kipinde degil, atlandi"
    bildir(30, "citext eklentisi denetleniyor")
    var = pg.citext_kur()
    bildir(100, "citext hazir" if var else "citext yok, duz TEXT")
    return "citext etkin" if var else "citext yok (lower() ile telafi)"


def _adim_json_goc(con, bildir):
    """Eski JSON dosyalarini (kullanicilar, ayarlar, rotalar) tasir.

    Bu adim `KullaniciYoneticisi` ve `AyarYoneticisi` kurulumunda
    kendiliginden calisir; burada YALNIZCA tetiklenir ve deftere
    islenir, boylece hangi kurulumda tasindigi denetlenebilir.
    """
    bildir(20, "Kullanici dosyasi denetleniyor")
    from .kullanicilar import KullaniciYoneticisi
    KullaniciYoneticisi()
    bildir(60, "Ayar dosyasi denetleniyor")
    from .ayarlar import AyarYoneticisi
    AyarYoneticisi(lambda *a, **k: None)
    bildir(100, "JSON dosyalari tasindi")
    return "kullanicilar + ayarlar"


# v2.4.53: FIRMA IZOLASYONU
# Merkezde (/app/) calisan ornek cok firmalidir; ayni surece farkli
# firmalarin pilotlari baglanir. Veri katmani firma_id ile bolunmezse
# bir firma digerinin dronlarini gorur. Lokal kurulumda kolon NULL
# kalir ve hicbir suzgec devreye girmez (davranis birebir korunur).
# v2.4.56: `ai_sunucular` EKLENDI. Eksikligi olculdu: merkezde bir
# firmanin ekledigi AI bilgisayari tum firmalarin AI panelinde
# goruluyordu (host/port ve SSH kullanici adi dahil).
_FIRMA_TABLOLARI = ("dronlar", "baglantilar", "kameralar", "rotalar",
                    "ai_sunucular")


def _adim_firma_izolasyon(con, bildir):
    """Firma izolasyonu icin firma_id kolonlarini ekler."""
    from . import veritabani as vt
    eklenen = []
    toplam = len(_FIRMA_TABLOLARI)
    for i, tablo in enumerate(_FIRMA_TABLOLARI):
        bildir(int(90.0 * i / toplam), "%s tablosu denetleniyor" % tablo)
        try:
            with vt.baglanti() as c2:
                if vt.pg_kipinde():
                    c2.execute(
                        "ALTER TABLE %s ADD COLUMN IF NOT EXISTS "
                        "firma_id INTEGER" % tablo)
                else:
                    # SQLite: IF NOT EXISTS yok; kolon varsa hata alinir
                    var = False
                    for r in c2.execute("PRAGMA table_info(%s)" % tablo):
                        if str(r[1]) == "firma_id":
                            var = True
                            break
                    if not var:
                        c2.execute(
                            "ALTER TABLE %s ADD COLUMN firma_id INTEGER"
                            % tablo)
                c2.execute(
                    "CREATE INDEX IF NOT EXISTS ix_%s_firma"
                    " ON %s (firma_id)" % (tablo, tablo))
            eklenen.append(tablo)
        except Exception as e:
            # Kolon zaten varsa veya tablo yoksa goc DURMAZ; izolasyon
            # suzgeci kolon yokken de guvenli calisir (suzgec atlanir).
            print("[GOC] firma_id eklenemedi (%s): %s" % (tablo, e))
    bildir(100, "Firma izolasyonu hazir")
    return "firma_id: " + ", ".join(eklenen) if eklenen else "degisiklik yok"


# v2.4.53 Faz 7: Baglanti Yoneticisi kayitlari KOPRU basina gruplanir.
# Kullanici istegi: "dron baglanti yoneticisinde sisteme baglanan
# kullanicilarin uygulamalari altinda gruplanacak" ve "bu gruplama
# ayni zamanda ai ve video icin de gecerli olacak".
#
# `kopru_ornek_id` merkezdeki `sunucu_ornekleri.ornek_id` degerini
# tasir. YABANCI ANAHTAR TANIMLANMAZ: kayitlar GCS veritabaninda,
# ornekler MERKEZ veritabanindadir (ayri veritabanlari). Butunluk
# uygulama katmaninda korunur.
#
# NULL degeri "kopruye bagli degil" anlamindadir; lokal kurulumda tum
# kayitlar NULL kalir ve gruplama hic devreye girmez (davranis birebir
# korunur).
# v2.4.56: `ai_sunucular` listeye EKLENDI. Onceki surumde eksikti ve
# bu iki kusura yol aciyordu: (1) AI sunuculari merkezde TUM firmalar
# arasinda paylasiliyordu (firma izolasyonu ihlali), (2) AI sunucusu
# hangi kopru makinesinde oldugu bilinmedigi icin merkezden dogrudan
# HTTP ile yoklaniyor, saha agindaki 192.168.x adresi merkeze kapali
# oldugundan her zaman "cevrimdisi" gorunuyordu.
_KOPRU_TABLOLARI = ("baglantilar", "kameralar", "ai_sunucular")


def _adim_kopru_gruplama(con, bildir):
    """Kayitlari kopruye baglamak icin kopru_ornek_id kolonu ekler."""
    from . import veritabani as vt
    eklenen = []
    toplam = len(_KOPRU_TABLOLARI)
    for i, tablo in enumerate(_KOPRU_TABLOLARI):
        bildir(int(90.0 * i / toplam), "%s tablosu denetleniyor" % tablo)
        try:
            with vt.baglanti() as c2:
                if vt.pg_kipinde():
                    c2.execute(
                        "ALTER TABLE %s ADD COLUMN IF NOT EXISTS "
                        "kopru_ornek_id INTEGER" % tablo)
                else:
                    var = False
                    for r in c2.execute("PRAGMA table_info(%s)" % tablo):
                        if str(r[1]) == "kopru_ornek_id":
                            var = True
                            break
                    if not var:
                        c2.execute(
                            "ALTER TABLE %s ADD COLUMN "
                            "kopru_ornek_id INTEGER" % tablo)
                c2.execute(
                    "CREATE INDEX IF NOT EXISTS ix_%s_kopru"
                    " ON %s (kopru_ornek_id)" % (tablo, tablo))
            eklenen.append(tablo)
        except Exception as e:
            # Kolon yoksa gruplama suzgeci atlanir; goc DURMAZ.
            print("[GOC] kopru_ornek_id eklenemedi (%s): %s" % (tablo, e))
    bildir(100, "Kopru gruplama hazir")
    return ("kopru_ornek_id: " + ", ".join(eklenen) if eklenen
            else "degisiklik yok")


def _kolon_ekle(tablo, kolon, indeks_eki):
    """Tabloya kolon ve indeks ekler; varsa sessizce gecer.

    Hem PG hem SQLite yolunu tasir. Basarisizlikta Exception firlatir;
    cagiran adim karari verir (goc DURMAZ, yalniz bildirir).
    """
    from . import veritabani as vt
    with vt.baglanti() as c2:
        if vt.pg_kipinde():
            c2.execute("ALTER TABLE %s ADD COLUMN IF NOT EXISTS %s INTEGER"
                       % (tablo, kolon))
        else:
            var = False
            for r in c2.execute("PRAGMA table_info(%s)" % tablo):
                if str(r[1]) == kolon:
                    var = True
                    break
            if not var:
                c2.execute("ALTER TABLE %s ADD COLUMN %s INTEGER"
                           % (tablo, kolon))
        c2.execute("CREATE INDEX IF NOT EXISTS ix_%s_%s ON %s (%s)"
                   % (tablo, indeks_eki, tablo, kolon))


def _adim_ai_sunucu_izolasyon(con, bildir):
    """ai_sunucular tablosuna firma_id ve kopru_ornek_id ekler.

    NEDEN AYRI ADIM: `firma_izolasyon` ve `kopru_gruplama` adimlari
    sahadaki veritabanlarinda UYGULANMIS isaretli. Tablo listelerine
    yeni bir tablo eklemek o adimlari yeniden kosturmaz, cunku goc
    defteri adim ADINA bakar. Bu yuzden yeni adim adi sarttir.
    """
    yapilan = []
    isler = (("firma_id", "firma"), ("kopru_ornek_id", "kopru"))
    for i, (kolon, eki) in enumerate(isler):
        bildir(int(90.0 * i / len(isler)),
               "ai_sunucular.%s denetleniyor" % kolon)
        try:
            _kolon_ekle("ai_sunucular", kolon, eki)
            yapilan.append(kolon)
        except Exception as e:
            # Tablo henuz yoksa (ilk kurulum sirasi) adim bosa doner;
            # `tablolar` adimi tabloyu kolonlariyla birlikte olusturur.
            print("[GOC] ai_sunucular.%s eklenemedi: %s" % (kolon, e))
    bildir(100, "AI sunucu izolasyonu hazir")
    return ("ai_sunucular: " + ", ".join(yapilan) if yapilan
            else "degisiklik yok")


def _adim_yerel_kopru(con, bildir):
    """`yerel_kopruler` tablosunu kurar (kapali devre kopru kabulu).

    v2.4.67. Kullanici sarti: "merkez uygulamayi satin alan sirket
    sinirsiz kullanim hakkina sahip oluyor. isterse KAPALI DEVRE
    kullanabiliyor."

    Kapali devrede bulut merkez sureci yoktur; kopru kayitlari (kurulum
    kimligi + sir ozeti) YEREL veritabaninda tutulmak zorundadir. Bulut
    tarafindaki karsiligi `sunucu_ornekleri` tablosudur, ancak o tablo
    firma cok kiracililigi tasir; yerel kurulum tek firmalidir ve
    `firma_id` kolonu TASINMAZ (bkz. goktungu/kopru_kabul.py).

    NEDEN AYRI ADIM: `tablolar` adimi sahadaki veritabanlarinda zaten
    UYGULANMIS isaretlidir; `veritabani.tablolari_olustur()`a yeni bir
    tablo eklemek o adimi yeniden kosturmaz (goc defteri adim ADINA
    bakar). Yeni ad = yeni is.
    """
    bildir(10, "Yerel kopru tablosu olusturuluyor")
    from . import kopru_kabul
    kopru_kabul.tablo_kur()
    bildir(100, "Yerel kopru kabulu hazir")
    return "yerel_kopruler tablosu"


ADIMLAR = [
    Adim("tablolar", 2451, "Veritabani tablolari olusturuluyor",
         _adim_tablolar, agirlik=3),
    Adim("citext", 2451, "E-posta buyuk/kucuk harf duyarsizligi kuruluyor",
         _adim_citext, agirlik=1),
    Adim("json_goc", 2451, "Eski dosya tabanli veriler tasiniyor",
         _adim_json_goc, agirlik=2),
    Adim("firma_izolasyon", 2453,
         "Firma izolasyonu kuruluyor (cok firmali merkez)",
         _adim_firma_izolasyon, agirlik=1),
    Adim("kopru_gruplama", 2453,
         "Kopru gruplamasi kuruluyor (dron/AI/video)",
         _adim_kopru_gruplama, agirlik=1),
    # v2.4.56: `firma_izolasyon` ve `kopru_gruplama` adimlari zaten
    # UYGULANMIS isaretlidir; tablo listelerine `ai_sunucular` eklemek
    # onlari yeniden kosturmaz. Bu yuzden AYRI BIR ADIM gerekir.
    # Adim adi goc defterinde birincil anahtardir: yeni ad = yeni is.
    Adim("ai_sunucu_izolasyon", 2456,
         "AI sunuculari firma ve kopruye baglaniyor",
         _adim_ai_sunucu_izolasyon, agirlik=1),
    # v2.4.67: kapali devre kurulumun kopru kabul kayitlari.
    Adim("yerel_kopru", 2467,
         "Kopru kabul ucu kuruluyor (kapali devre)",
         _adim_yerel_kopru, agirlik=1),
]


# ==================================================================
# Goc motoru
# ==================================================================
class GocMotoru:
    """Goc adimlarini sirayla, ilerleme bildirerek uygular."""

    def __init__(self, konsol: Optional[Callable] = None):
        self.konsol = konsol or (lambda *a, **k: None)
        self.son_hata = ""

    def gerekli_mi(self) -> bool:
        """Goc gerekli mi (uygulanmamis adim var mi)."""
        try:
            defter_kur()
        except Exception:
            # Defter kurulamiyorsa tablolar da yoktur -> goc gerekli
            return True
        return any(not adim_uygulandi_mi(a.ad) for a in ADIMLAR)

    def bekleyen_adimlar(self):
        """Uygulanmamis adimlarin listesi."""
        try:
            defter_kur()
        except Exception:
            return list(ADIMLAR)
        return [a for a in ADIMLAR if not adim_uygulandi_mi(a.ad)]

    def durum(self) -> dict:
        """Sihirbaz icin durum ozeti."""
        from . import veritabani as vt
        bekleyen = self.bekleyen_adimlar()
        return {
            "kip": vt.KIP,
            "sema_surumu": sema_surumu(),
            "hedef_surum": SEMA_SURUMU,
            "guncel": len(bekleyen) == 0,
            "bekleyen": [
                {"ad": a.ad, "aciklama": a.aciklama, "surum": a.surum}
                for a in bekleyen
            ],
            "defter": defter_oku(),
        }

    def calistir(self, ilerleme: Optional[Callable] = None) -> dict:
        """Bekleyen adimlari uygular.

        `ilerleme(yuzde, ileti, adim_ad)` her ilerleme noktasinda
        cagrilir. Yuzde TOPLAM ilerlemedir (0-100).

        Donus: {"tamam": bool, "uygulanan": int, "hata": str,
                "adimlar": [...]}
        """
        # OLCULEN KUSUR (dene_pg_ws.py): yuzde GERI SARIYORDU.
        # Olculen dizi: [2, 6, 0, 5.0, 50.0, ...] — cagiran taraf
        # (sunucu.py) kendi hazirlik adimlari icin 2 ve 6 bildirir,
        # ardindan goc motoru 0'dan baslar. Kullanici ilerleme cubugunun
        # geri atladigini gorur ve surecin bastan basladigini sanir.
        #
        # COZUM: TEK YONLU kelepce. Yuzde asla azalmaz; azalma isteyen
        # bildirim en son bildirilen degeri KORUR (ileti metni yine
        # guncellenir, boylece "neyin surdugu" bilgisi kaybolmaz).
        _dis = ilerleme or (lambda *a, **k: None)
        _en_yuksek = [0.0]

        def bildir_dis(yuzde, ileti, ad=""):
            try:
                y = float(yuzde)
            except (TypeError, ValueError):
                y = _en_yuksek[0]
            y = max(0.0, min(100.0, y))
            if y < _en_yuksek[0]:
                y = _en_yuksek[0]
            else:
                _en_yuksek[0] = y
            _dis(round(y, 1), ileti, ad)

        try:
            defter_kur()
        except Exception as e:
            # Defter kurulamiyor: baglanti sorunu olabilir
            self.son_hata = f"{type(e).__name__}: {e}"
            return {"tamam": False, "uygulanan": 0,
                    "hata": self.son_hata, "adimlar": []}

        bekleyen = self.bekleyen_adimlar()
        if not bekleyen:
            bildir_dis(100, "Veritabani guncel", "")
            return {"tamam": True, "uygulanan": 0, "hata": "",
                    "adimlar": []}

        toplam_agirlik = sum(a.agirlik for a in bekleyen)
        birikmis = 0
        sonuclar = []

        for adim in bekleyen:
            bas = time.time()
            pay = adim.agirlik / toplam_agirlik

            def bildir(alt_yuzde, alt_ileti, _adim=adim, _b=birikmis,
                       _p=pay):
                # Alt ilerlemeyi toplam ilerlemeye cevir
                toplam = (_b + _p * (max(0, min(100, alt_yuzde)) / 100)) * 100
                bildir_dis(round(toplam, 1), alt_ileti, _adim.ad)

            bildir_dis(round(birikmis * 100, 1), adim.aciklama, adim.ad)
            self.konsol(f"[GOC] {adim.aciklama}...")
            try:
                from . import veritabani as vt
                # Adim kendi baglantisini/islemini yonetir; `con`
                # gecmek zorunlu degil ama API tutarliligi icin verilir
                with vt.baglanti() as con:
                    ozet = adim.islev(con, bildir)
                sure_ms = int((time.time() - bas) * 1000)
                # KRITIK: defter kaydi adim BASARILI olduktan SONRA
                adim_kaydet(adim.ad, adim.surum, sure_ms, "tamam",
                            str(ozet or ""))
                sonuclar.append({"ad": adim.ad, "durum": "tamam",
                                 "sure_ms": sure_ms,
                                 "ozet": str(ozet or "")})
                self.konsol(f"[GOC] {adim.ad}: tamam ({sure_ms} ms)"
                            + (f" — {ozet}" if ozet else ""))
            except Exception as e:
                hata = f"{type(e).__name__}: {e}"
                iz = traceback.format_exc()[-800:]
                sure_ms = int((time.time() - bas) * 1000)
                try:
                    adim_kaydet(adim.ad, adim.surum, sure_ms, "hata",
                                adim.aciklama, hata + "\n" + iz)
                except Exception:
                    pass
                self.son_hata = hata
                self.konsol(f"[GOC] HATA {adim.ad}: {hata}")
                sonuclar.append({"ad": adim.ad, "durum": "hata",
                                 "sure_ms": sure_ms, "ozet": hata})
                # KRITIK: sonraki adimlar oncekine dayanabilir; DUR
                return {"tamam": False,
                        "uygulanan": len([s for s in sonuclar
                                          if s["durum"] == "tamam"]),
                        "hata": hata, "adimlar": sonuclar}

            birikmis += pay

        try:
            sema_surumu_yaz(SEMA_SURUMU)
        except Exception:
            pass
        bildir_dis(100, "Goc tamamlandi", "")
        return {"tamam": True,
                "uygulanan": len(sonuclar), "hata": "",
                "adimlar": sonuclar}
