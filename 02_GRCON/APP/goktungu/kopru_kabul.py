# -*- coding: utf-8 -*-
"""KOPRU KABUL UCU — yerel Merkez Uygulama'nin kopru dinleyicisi.

## NEDEN BU MODUL VAR

Kullanici istegi (birebir):
    "isteyen sirket yoneticisi ayni bilgisayara ister merkez yazilimini
     isterse ayni anda kopru yazilimini calistirabilir"
    "merkez uygulamayi satin alan sirket sinirsiz kullanim hakkina
     sahip oluyor. isterse KAPALI DEVRE kullanabiliyor."
    "tabiki yapmalisin yoksa sistemin anlamI yok"

Olculen kusur: kopru yazilimi yerel merkeze (`wss://127.0.0.1/kopru`)
baglanamiyordu. Kok neden mimariydi, yapilandirma degildi:

    Bulutta:   kopru --WSS--> mk_sunucu(9443)  [dinleyici mk_role.ROLE]
               GCS   --HTTP-> /api/ic/kopru_sor  (AYRI surec)
    Yerelde:   kopru --WSS--> ???               [dinleyici YOK]

`goktungu/sunucu.py` acikca yaziyordu: "ters WSS baglantisini GCS acar" —
yani yerel GCS de bir AJAN'di, kopru KABUL EDEN taraf degildi. Kapali
devre kurulumda merkez sunucu sureci hic yok; bu yuzden hem dinleyici
hem kayit defteri GCS surecinin ICINDE olmak zorunda.

## BULUT ILE FARK: HTTP KATMANI YOK

`merkez_kimlik.kopruye_sor()` merkez surecine HTTP POST yapar cunku GCS
ayri bir surectir. Burada dinleyici ve GCS AYNI surecte oldugu icin
`kopruden_iste()` dogrudan sokete yazar: bir HTTP atlamasi, bir ic
anahtar ve bir seri hale getirme turu daha az.

## SOZLESME BULUTLA BIREBIR AYNI

Kopru tarafinda TEK BIR satir kod degismesin diye mesaj turleri, alan
adlari ve sir ozetleme tuzu buluttan birebir kopyalanmistir
(bkz. OLCUM_KOPRU_UC_SOZLESME.md). Ayni kopru ikilisi hem buluta hem
yerel merkeze baglanabilir. Iki ayri sir bicimi tutmak bakim yuku ve
sessiz kimlik kusuru kaynagi olurdu.

    kopru --> {"tur":"merhaba","kurulum_uid":..,"gizli":..}
    merkez -> {"tur":"merhaba_tamam","kanal":..,"ornek_id":..}
    kopru --> {"tur":"nabiz","dron_sayisi":..,"yetenekler":{..}}
    merkez -> {"tur":"nabiz_tamam"}
    merkez -> {"tur":"istek","istek_id":..,"eylem":..,"veri":{..}}
    kopru --> {"tur":"yanit","istek_id":..,"veri":{..}}   | {"hata":..}

## FIRMA IZOLASYONU

Bulutta her kopru bir firmaya aittir (`sunucu_ornekleri.firma_id`).
Yerel kurulum TEK FIRMALIdir: Merkez Uygulama'yi satin alan sirket.
Bu yuzden yerel tabloda `firma_id` YOKTUR ve capraz firma sizmasi
kavramsal olarak imkansizdir. `firma_id` alani oturum nesnesinde
None kalir; cagiran taraf bunu bilerek suzgec uygulamaz.
"""
import asyncio
import contextlib
import datetime as dt
import hashlib
import hmac
import json
import secrets
import threading
import time

# Bulutla AYNI tuz. Degistirilirse mevcut kopru kayitlari gecersiz olur
# ve kopru ayni kodla iki merkeze baglanamaz (bkz. modul basligi).
_TUZ = "GOKTUNGU-MERKEZ-2026"

# Nabiz gormeyen kopru bu sureden sonra cevrimdisi sayilir. Kopru 30 sn
# arayla nabiz atar; 90 sn iki kacirilan nabza tolerans tanir (gecici ag
# kesintisinde kurulumu gereksiz yere dusurmemek icin).
NABIZ_ZAMAN_ASIMI_SN = 90

TABLO = "yerel_kopruler"


# ======================================================================
# Sir ozetleme (bulutla birebir)
# ======================================================================
# IS91: hedef deposu (bellekte, veritabanina YAZILMAZ)
try:
    from . import hedef_deposu as _hd
except Exception:      # modul yoksa kopru yine calisir
    _hd = None


def gizli_ozetle(gizli):
    """Kopru sirrinin saklanan ozeti."""
    return hashlib.sha256(
        (_TUZ + str(gizli)).encode("utf-8")).hexdigest()


def gizli_dogrula(gizli, saklanan_ozet):
    """Sabit zamanli karsilastirma.

    `hmac.compare_digest` kullanilir: normal `==` karsilastirmasi ilk
    farkli baytta doner ve olculebilir zaman sizintisi uretir.
    """
    return hmac.compare_digest(gizli_ozetle(gizli), str(saklanan_ozet or ""))


def kurulum_uid_uret():
    return secrets.token_hex(16)


def gizli_uret():
    return secrets.token_urlsafe(32)


# ======================================================================
# v2.4.232: KOPRU API KODU
# ======================================================================
# Kullanici istegi (2026-09-17): "yeni koprude sadece kopru ismini
# sorsun, olusturulunca bir API kodu olustursun, bu kodu listedeyken
# kopyalayabilsin ... kopru ilk kurulumda ... api kodunu sorsun,
# girdiginde kopru iletisimi saglansin".
#
# Kod, koprunun baglanmak icin bilmesi gereken HER SEYI tasir: kurulum
# kimligi (uid), sir (gizli), merkezin WS/HTTP adresi ve kayit adi.
# Bicim: `GTK1.` + base64url(JSON). Onek surum tasir; ileride alanlar
# degisirse kopru eski kodu tanimayi surdurebilir.
#
# GUVENLIK: kod SIRRI acik tasir. Bu yuzden veritabaninda yalniz kopru
# ILK KEZ basariyla baglanana kadar tutulur; baglanti acilinca silinir
# (`_baglanti_acildi`). Kaybolan kod icin `kopru_kod_yenile` yeni sir
# uretir; eski sirla baglanan kopru duser.
API_KOD_ONEK = "GTK1."


def api_kodu_uret(kurulum_uid, gizli, merkez_adres, merkez_http="",
                  ad="", ornek_id=None, tur="grcoff", urun="kopru"):
    """`p` (urun): "kopru" saha koprusu, "gcs" Merkezi Yazilim (GRCOFF)
    kaydi. Yerel kip yalniz kopru kodu uretir; GRCON kurumsal paneli
    ikisini de uretir."""
    import base64
    govde = {"u": str(kurulum_uid or ""), "g": str(gizli or ""),
             "m": str(merkez_adres or ""), "t": str(tur or "grcoff"),
             "p": str(urun or "kopru")}
    if merkez_http:
        govde["h"] = str(merkez_http)
    if ad:
        govde["a"] = str(ad)
    if ornek_id:
        govde["o"] = int(ornek_id)
    ham = json.dumps(govde, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return API_KOD_ONEK + base64.urlsafe_b64encode(ham).decode(
        "ascii").rstrip("=")


def api_kodu_coz(kod):
    """`(sozluk, hata)` dondurur. Bosluk/satir sonu yok sayilir."""
    import base64
    kod = "".join(str(kod or "").split())
    if not kod.startswith(API_KOD_ONEK):
        return None, "API kodu '%s' ile baslamali" % API_KOD_ONEK
    govde = kod[len(API_KOD_ONEK):]
    govde += "=" * (-len(govde) % 4)
    try:
        d = json.loads(base64.urlsafe_b64decode(govde).decode("utf-8"))
    except Exception:
        return None, "API kodu cozulemedi (eksik veya bozuk)"
    if not isinstance(d, dict) or not (d.get("u") and d.get("g")
                                       and d.get("m")):
        return None, "API kodu eksik alan iceriyor"
    return d, None


def _api_kodu_sutunu_garanti(con, pg):
    """`api_kodu` sutunu eski kurulumlarda yoktur; bir kez eklenir."""
    if pg:
        con.execute("ALTER TABLE " + TABLO +
                    " ADD COLUMN IF NOT EXISTS api_kodu TEXT DEFAULT ''")
        return
    mevcut = {r[1] for r in con.execute(
        "PRAGMA table_info(" + TABLO + ")").fetchall()}
    if "api_kodu" not in mevcut:
        con.execute("ALTER TABLE " + TABLO +
                    " ADD COLUMN api_kodu TEXT DEFAULT ''")


# ======================================================================
# Oturum nesnesi
# ======================================================================
class KopruOturumu:
    """Yerel merkeze bagli tek bir kopru kurulumu."""

    __slots__ = (
        "soket", "ornek_id", "kurulum_uid", "firma_id", "ad", "surum",
        "platform", "makine_adi", "ip", "baglanma_ts", "son_nabiz",
        "yetenekler", "dron_sayisi", "kanal", "bekleyen",
        "hedef_paket", "son_hedef_ts",
    )

    def __init__(self, soket, ip=None):
        self.soket = soket
        self.ip = ip or ""
        self.ornek_id = None
        self.kurulum_uid = ""
        # Yerel kurulum tek firmalidir; alan bulut sozlesmesiyle
        # bicimsel uyum icin durur (bkz. modul basligi).
        self.firma_id = None
        self.ad = ""
        self.surum = ""
        self.platform = ""
        self.makine_adi = ""
        self.baglanma_ts = time.time()
        self.son_nabiz = time.time()
        self.yetenekler = {}
        self.dron_sayisi = 0
        self.kanal = secrets.token_hex(8)
        # istek_id -> asyncio.Future
        self.bekleyen = {}
        # IS91: hedef verisi sayaclari (goruntu DEGIL, sayac)
        self.hedef_paket = 0
        self.son_hedef_ts = 0.0

    def ozet(self):
        """Panel/arayuz icin guvenli ozet.

        `gizli_ozet` ASLA yer almaz: arayuze sizmasi kayit sahtekarligi
        riski yaratir (bulut tarafindaki ayni gerekce).
        """
        return {
            "ornek_id": self.ornek_id,
            "kurulum_uid": self.kurulum_uid,
            "ad": self.ad,
            "surum": self.surum,
            "platform": self.platform,
            "makine_adi": self.makine_adi,
            "kanal": self.kanal,
            "cevrimici": True,
            "ip": self.ip,
            "dron_sayisi": self.dron_sayisi,
            "yetenekler": self.yetenekler,
            "baglanma_ts": dt.datetime.fromtimestamp(
                self.baglanma_ts, dt.timezone.utc).isoformat(),
            "son_gorulme_ts": dt.datetime.fromtimestamp(
                self.son_nabiz, dt.timezone.utc).isoformat(),
            "son_nabiz_sn": round(time.time() - self.son_nabiz, 1),
            "durum": "etkin",
            "hedef_paket": self.hedef_paket,
            "son_hedef_sn": (round(time.time() - self.son_hedef_ts, 1)
                             if self.son_hedef_ts else None),
        }


# ======================================================================
# Canli baglanti kayit defteri
# ======================================================================
# IS47_TEK_OTURUM_v1: ayni kurulum_uid ile IKINCI baglanti geldiginde eski
# oturum CANLI ise yenisi reddedilir. 0 yapilirsa yama
# etkisizlesir ve eski (dusurme) davranisi geri gelir.
TEK_OTURUM_KORUMA_SN = 45


class IkinciOturumHatasi(Exception):
    """Ayni kurulum icin canli bir oturum zaten var."""


class RoleYoneticisi:
    """Canli kopru soketlerinin kayit defteri (bellek ici).

    Veritabani `cevrimici` bayragi da tutar ama TEK GERCEK KAYNAK
    burasidir: veritabani surec cokmesinden sonra bayat kalabilir,
    bellekteki soket kalamaz.
    """

    def __init__(self):
        self._uid = {}
        self._kanallar = {}
        self._kilit = None   # ilk kullanimda kurulur (dongu gerekir)

    def _kilit_al(self):
        # asyncio.Lock() bir olay dongusu gerektirir; modul yuklenirken
        # dongu henuz yoktur. Tembel kurulum bu bagimliligi kirar.
        if self._kilit is None:
            self._kilit = asyncio.Lock()
        return self._kilit

    async def ekle(self, o):
        async with self._kilit_al():
            # Ayni kurulum ikinci kez baglanirsa ESKISI dusurulur.
            # Aksi halde kopru yeniden baslatildiginda iki kayit olur ve
            # komutlar olu sokete gider (pilot komutun gittigini sanir).
            eski = self._uid.get(o.kurulum_uid)
            if eski is not None and eski is not o:
                # IS47_TEK_OTURUM_v1: eski oturum CANLI ise yenisini REDDET.
                # Ayni kopru iki yoldan baglandiginda taraflar
                # birbirini dusuruyor ve `cevrimici` bayragi
                # saniyelik salinim yapiyordu.
                if TEK_OTURUM_KORUMA_SN > 0 and (
                        time.time() - eski.son_nabiz
                ) < TEK_OTURUM_KORUMA_SN:
                    raise IkinciOturumHatasi(o.kurulum_uid)
                with contextlib.suppress(Exception):
                    await eski.soket.close()
                self._kanallar.pop(eski.kanal, None)
            self._uid[o.kurulum_uid] = o
            self._kanallar[o.kanal] = o

    async def cikar(self, o):
        async with self._kilit_al():
            if self._uid.get(o.kurulum_uid) is o:
                self._uid.pop(o.kurulum_uid, None)
            self._kanallar.pop(o.kanal, None)
        # Bekleyen istekler SESSIZCE birakilmaz: cagiran taraf zaman
        # asimina kadar bloke kalir ve kullanici "sistem dondu" gorur.
        for f in list(o.bekleyen.values()):
            if not f.done():
                f.set_exception(ConnectionError("Kopru baglantisi kapandi"))
        o.bekleyen.clear()

    def uid_ile(self, kurulum_uid):
        return self._uid.get(str(kurulum_uid or ""))

    def kanal_ile(self, kanal):
        return self._kanallar.get(str(kanal or ""))

    def ornek_ile(self, ornek_id):
        try:
            hedef = int(ornek_id)
        except (TypeError, ValueError):
            return None
        for o in self._uid.values():
            if o.ornek_id == hedef:
                return o
        return None

    def tumu(self):
        return [o.ozet() for o in self._uid.values()]

    def sayi(self):
        return len(self._uid)


ROLE = RoleYoneticisi()


# ======================================================================
# Veritabani katmani
# ======================================================================
def tablo_kur():
    """`yerel_kopruler` tablosunu olusturur (varsa dokunmaz).

    Goc adimi bunu cagirir. Kullanici sarti geregi veri PostgreSQL'de
    tutulur ("sqlite'a donmeyecegiz, lutfen her veriyi postgresql'e
    cevir"); JSON dosyasi kullanilmaz.
    """
    from . import veritabani as vt
    with vt.baglanti() as con:
        if vt.pg_kipinde():
            con.execute(
                "CREATE TABLE IF NOT EXISTS " + TABLO + " ("
                " ornek_id SERIAL PRIMARY KEY,"
                " kurulum_uid TEXT UNIQUE NOT NULL,"
                " gizli_ozet TEXT NOT NULL,"
                " ad TEXT NOT NULL,"
                " aciklama TEXT DEFAULT '',"
                " surum TEXT DEFAULT '',"
                " platform TEXT DEFAULT '',"
                " makine_adi TEXT DEFAULT '',"
                " cevrimici BOOLEAN DEFAULT FALSE,"
                " son_gorulme_ts TIMESTAMPTZ,"
                " son_ip TEXT DEFAULT '',"
                " dron_sayisi INTEGER DEFAULT 0,"
                " yetenekler JSONB DEFAULT '{}'::jsonb,"
                " durum TEXT DEFAULT 'etkin',"
                " olusma_ts TIMESTAMPTZ DEFAULT now())")
        else:
            # SQLite yolu yalniz gelistirme/gerileme icin durur; urun
            # kipinde PG kullanilir.
            con.execute(
                "CREATE TABLE IF NOT EXISTS " + TABLO + " ("
                " ornek_id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " kurulum_uid TEXT UNIQUE NOT NULL,"
                " gizli_ozet TEXT NOT NULL,"
                " ad TEXT NOT NULL,"
                " aciklama TEXT DEFAULT '',"
                " surum TEXT DEFAULT '',"
                " platform TEXT DEFAULT '',"
                " makine_adi TEXT DEFAULT '',"
                " cevrimici INTEGER DEFAULT 0,"
                " son_gorulme_ts TEXT,"
                " son_ip TEXT DEFAULT '',"
                " dron_sayisi INTEGER DEFAULT 0,"
                " yetenekler TEXT DEFAULT '{}',"
                " durum TEXT DEFAULT 'etkin',"
                " olusma_ts TEXT DEFAULT CURRENT_TIMESTAMP)")
        con.execute(
            "CREATE INDEX IF NOT EXISTS ix_yerel_kopruler_uid"
            " ON " + TABLO + " (kurulum_uid)")
        # v2.4.232: API kodu sutunu (bkz. api_kodu_uret).
        with contextlib.suppress(Exception):
            _api_kodu_sutunu_garanti(con, vt.pg_kipinde())
    return True


def kopru_kaydet(ad, aciklama="", merkez_adres="", merkez_http=""):
    """Yeni kopru kaydi uretir. `gizli` YALNIZ BIR KEZ doner.

    Sir veritabaninda ozet olarak tutulur; kaybedilirse yeni kayit
    uretilmesi gerekir. Bulut `ornek_kaydet()` ile ayni sozlesme.

    v2.4.232: `merkez_adres` (ws://...) verilirse koprunun kurulumda
    girecegi API kodu uretilir ve ilk basarili baglantiya kadar
    `api_kodu` sutununda tutulur (bkz. api_kodu_uret).
    """
    from . import veritabani as vt
    uid = kurulum_uid_uret()
    gizli = gizli_uret()
    ad = str(ad or "Yerel Kopru")
    kod = ""
    if merkez_adres:
        kod = api_kodu_uret(uid, gizli, merkez_adres, merkez_http, ad,
                            None, "grcoff")
    with vt.baglanti() as con:
        im = con.execute(
            "INSERT INTO " + TABLO +
            " (kurulum_uid, gizli_ozet, ad, aciklama, api_kodu)"
            " VALUES (?,?,?,?,?)",
            (uid, gizli_ozetle(gizli), ad, str(aciklama or ""), kod))
        oid = getattr(im, "lastrowid", None)
    if not oid:
        with vt.baglanti() as con:
            s = con.execute(
                "SELECT ornek_id FROM " + TABLO +
                " WHERE kurulum_uid=?", (uid,)).fetchone()
            oid = int(s[0]) if s else None
    if kod and oid:
        # Kod ornek kimligini de tasisin (kopru panelinde gosterilir).
        kod = api_kodu_uret(uid, gizli, merkez_adres, merkez_http, ad,
                            int(oid), "grcoff")
        with vt.baglanti() as con:
            con.execute("UPDATE " + TABLO + " SET api_kodu=? WHERE ornek_id=?",
                        (kod, int(oid)))
    return {
        "ornek_id": int(oid) if oid else None,
        "kurulum_uid": uid,
        "gizli": gizli,
        "ad": ad,
        "api_kodu": kod,
    }


def kopru_kod_yenile(ornek_id, merkez_adres, merkez_http=""):
    """Kaydin sirrini ve API kodunu YENILER; eski sir gecersizlesir.

    Kod ilk baglantida silindigi icin koprunun yeniden kurulmasi
    (makine degisti, dosya kayboldu) yeni bir kod gerektirir. Cagiran
    taraf canli oturumu kapatmalidir (eski sirla baglanan kopru
    dusmeli).
    """
    from . import veritabani as vt
    with vt.baglanti() as con:
        s = con.execute(
            "SELECT kurulum_uid, ad FROM " + TABLO +
            " WHERE ornek_id=? AND durum <> 'iptal'",
            (int(ornek_id),)).fetchone()
    if not s:
        return None
    gizli = gizli_uret()
    kod = api_kodu_uret(str(s["kurulum_uid"]), gizli, merkez_adres,
                        merkez_http, str(s["ad"] or ""), int(ornek_id),
                        "grcoff")
    with vt.baglanti() as con:
        con.execute(
            "UPDATE " + TABLO + " SET gizli_ozet=?, api_kodu=?"
            " WHERE ornek_id=?", (gizli_ozetle(gizli), kod, int(ornek_id)))
    return {"ornek_id": int(ornek_id), "api_kodu": kod}


def _kayit_urunu(satir):
    """Kaydin urununu JSONB/TEXT yeteneklerden guvenle okur.

    Eski kayitlarda `urun` yoktur; geriye uyumlu varsayim `kopru`dur.
    """
    try:
        yet = satir["yetenekler"]
    except Exception:
        yet = None
    if isinstance(yet, str):
        try:
            yet = json.loads(yet)
        except Exception:
            yet = {}
    if not isinstance(yet, dict):
        yet = {}
    return str(yet.get("urun") or "kopru").strip().lower(), yet


def istemci_sunucu_kaydet(ad, aciklama="", makine_adi="", platform="",
                           surum="", urun="kopru", yenile=False,
                           eski_uid=""):
    """Kopru HTTP ilk-kayit sozlesmesini yerel kimlik deposuna baglar.

    Ayni makine icindeki farkli urunler (dron/video/radar/GCCDUAL/DJI)
    birbirinin kimligini ezmez. Gizli veritabanina ASLA duz yazilmaz;
    yalnizca SHA-256 ozeti saklanir ve duz gizli tek kez doner.

    Donus: `(sonuc, hata, http_kodu)`.
    """
    from . import veritabani as vt

    izinli_urunler = {"kopru", "radar", "gccdual", "dji"}
    urun = str(urun or "kopru").strip().lower()
    # v2.4.193 (Faz D): AYRI "Goruntu Koprusu" urunu (`video`) kaldirildi;
    # islevi saha Koprusunun `video`/`ai` servislerine tasindi. Sahada
    # KURULU eski surumler hala `urun="video"` ile kayit isteyebilir.
    # Bunlari REDDETMEK, calisan bir saha makinesini sessizce cevrimdisi
    # yapardi (operator sebebini goremez). Bu yuzden reddedilmez,
    # `kopru` olarak KABUL EDILIR: makine kaydini korur ve guncelleme
    # akisiyla yeni Kopruye gecebilir.
    if urun == "video":
        urun = "kopru"
    if urun not in izinli_urunler:
        return None, "Gecersiz sunucu urunu", 400

    ad = str(ad or "").strip()
    makine_adi = str(makine_adi or "").strip()
    platform = str(platform or "").strip()
    surum = str(surum or "").strip()
    aciklama = str(aciklama or "").strip()
    eski_uid = str(eski_uid or "").strip()
    if not ad:
        return None, "Sunucu adi zorunlu", 400

    tablo_kur()
    mevcutlar = []
    with vt.baglanti() as con:
        if eski_uid:
            s = con.execute(
                "SELECT ornek_id, kurulum_uid, ad, yetenekler FROM " +
                TABLO + " WHERE kurulum_uid=? AND durum <> 'iptal'",
                (eski_uid,)).fetchone()
            if s and _kayit_urunu(s)[0] == urun:
                mevcutlar = [s]
        if not mevcutlar and makine_adi:
            adaylar = con.execute(
                "SELECT ornek_id, kurulum_uid, ad, yetenekler FROM " +
                TABLO + " WHERE makine_adi=? AND durum <> 'iptal' "
                "ORDER BY ornek_id", (makine_adi,)).fetchall()
            mevcutlar = [s for s in (adaylar or [])
                          if _kayit_urunu(s)[0] == urun]

        if len(mevcutlar) > 1:
            return ({"kayitli": True, "urun": urun},
                    "Bu makine icin birden fazla urun kaydi var; "
                    "otomatik esleme yapilmadi", 409)

        mevcut = mevcutlar[0] if mevcutlar else None
        if mevcut is not None and not bool(yenile):
            return ({"kayitli": True,
                     "ornek_id": int(mevcut["ornek_id"]),
                     "ad": str(mevcut["ad"] or ad), "urun": urun},
                    "Bu makine zaten kayitli", 409)

        uid = kurulum_uid_uret()
        gizli = gizli_uret()
        gizli_ozet = gizli_ozetle(gizli)
        if mevcut is not None:
            _, yetenekler = _kayit_urunu(mevcut)
            yetenekler.update({"urun": urun, "surum": surum})
            con.execute(
                "UPDATE " + TABLO +
                " SET kurulum_uid=?, gizli_ozet=?, ad=?, aciklama=?, "
                "surum=?, platform=?, makine_adi=?, yetenekler=?, "
                "durum='etkin', cevrimici=? WHERE ornek_id=?",
                (uid, gizli_ozet, ad, aciklama, surum, platform,
                 makine_adi, json.dumps(yetenekler, ensure_ascii=False),
                 False if vt.pg_kipinde() else 0,
                 int(mevcut["ornek_id"])))
            oid = int(mevcut["ornek_id"])
        else:
            yetenekler = {"urun": urun, "surum": surum}
            im = con.execute(
                "INSERT INTO " + TABLO +
                " (kurulum_uid, gizli_ozet, ad, aciklama, surum, "
                "platform, makine_adi, yetenekler, durum, cevrimici) "
                "VALUES (?,?,?,?,?,?,?,?, 'etkin', ?)",
                (uid, gizli_ozet, ad, aciklama, surum, platform,
                 makine_adi, json.dumps(yetenekler, ensure_ascii=False),
                 False if vt.pg_kipinde() else 0))
            oid = getattr(im, "lastrowid", None)
            if not oid:
                s = con.execute(
                    "SELECT ornek_id FROM " + TABLO +
                    " WHERE kurulum_uid=?", (uid,)).fetchone()
                oid = int(s["ornek_id"] if hasattr(s, "keys") else s[0])

    return ({"ornek_id": int(oid), "kurulum_uid": uid,
             "gizli": gizli, "ad": ad, "urun": urun,
             "kimlik_onarildi": bool(mevcut is not None)}, None, 200)


def kopru_sil(ornek_id):
    """Kaydi iptal eder. SATIR SILINMEZ: `kopru_ornek_id` tasiyan dron/
    kamera/AI kayitlari yetim kalmasin diye durum `iptal` yapilir."""
    from . import veritabani as vt
    with vt.baglanti() as con:
        con.execute(
            "UPDATE " + TABLO + " SET durum='iptal', cevrimici=? "
            "WHERE ornek_id=?", (False if vt.pg_kipinde() else 0,
                                 int(ornek_id)))
    o = ROLE.ornek_ile(ornek_id)
    return bool(o is None or True)


def kopru_listesi():
    """Kayitli kopruleri dondurur; canli durum bellekten uzerine yazilir.

    Veritabanindaki `cevrimici` bayragi surec cokmesinden sonra bayat
    kalabilir. Tek gercek kaynak `ROLE`dir; bu yuzden liste okunduktan
    sonra canli soketlerle DUZELTILIR.
    """
    from . import veritabani as vt
    cikti = []
    try:
        with vt.baglanti() as con:
            satirlar = con.execute(
                "SELECT ornek_id, kurulum_uid, ad, aciklama, surum,"
                "       platform, makine_adi, cevrimici, son_gorulme_ts,"
                "       son_ip, dron_sayisi, yetenekler, durum, api_kodu"
                "  FROM " + TABLO + " WHERE durum <> 'iptal'"
                " ORDER BY ad").fetchall()
    except Exception as e:
        print("[KOPRU] Yerel kopru listesi okunamadi: %s" % e)
        return []
    for s in satirlar or []:
        yet = s["yetenekler"]
        if isinstance(yet, str):
            try:
                yet = json.loads(yet)
            except Exception:
                yet = {}
        oid = int(s["ornek_id"])
        canli = ROLE.ornek_ile(oid)
        k = {
            "ornek_id": oid,
            "kurulum_uid": str(s["kurulum_uid"] or ""),
            "ad": str(s["ad"] or ""),
            "aciklama": str(s["aciklama"] or ""),
            "surum": str(s["surum"] or ""),
            "platform": str(s["platform"] or ""),
            "makine_adi": str(s["makine_adi"] or ""),
            "cevrimici": canli is not None,
            "son_gorulme_ts": (
                s["son_gorulme_ts"].isoformat()
                if hasattr(s["son_gorulme_ts"], "isoformat")
                else s["son_gorulme_ts"]),
            "ip": str(s["son_ip"] or ""),
            "dron_sayisi": int(s["dron_sayisi"] or 0),
            "yetenekler": yet if isinstance(yet, dict) else {},
            "durum": str(s["durum"] or ""),
            "yerel": True,
            # v2.4.232: kod yalniz ilk baglantiya kadar doludur.
            "api_kodu": str(s["api_kodu"] or ""),
        }
        if canli is not None:
            # Canli oturum daha guncel: nabiz henuz veritabanina
            # yazilmamis olabilir.
            k["dron_sayisi"] = canli.dron_sayisi
            k["yetenekler"] = canli.yetenekler or k["yetenekler"]
            k["surum"] = canli.surum or k["surum"]
            k["ip"] = canli.ip or k["ip"]
        cikti.append(k)
    return cikti


def _kimlik_oku(kurulum_uid):
    from . import veritabani as vt
    with vt.baglanti() as con:
        return con.execute(
            "SELECT ornek_id, gizli_ozet, ad, durum FROM " + TABLO +
            " WHERE kurulum_uid=?", (str(kurulum_uid),)).fetchone()


def _baglanti_acildi(o):
    from . import veritabani as vt
    with contextlib.suppress(Exception):
        with vt.baglanti() as con:
            # v2.4.232: kopru basariyla baglandi -> API kodu (sirri acik
            # tasir) artik gerekmez; veritabanindan silinir.
            con.execute(
                "UPDATE " + TABLO + " SET cevrimici=?, son_gorulme_ts=?,"
                " son_ip=?, surum=?, platform=?, makine_adi=?, api_kodu=''"
                " WHERE ornek_id=?",
                (True if vt.pg_kipinde() else 1,
                 dt.datetime.now(dt.timezone.utc), o.ip, o.surum,
                 o.platform, o.makine_adi, int(o.ornek_id)))


def _baglanti_kapandi(o):
    from . import veritabani as vt
    with contextlib.suppress(Exception):
        with vt.baglanti() as con:
            con.execute(
                "UPDATE " + TABLO + " SET cevrimici=?, son_gorulme_ts=?"
                " WHERE ornek_id=?",
                (False if vt.pg_kipinde() else 0,
                 dt.datetime.now(dt.timezone.utc), int(o.ornek_id)))


def _nabiz_yaz(o):
    from . import veritabani as vt
    with contextlib.suppress(Exception):
        with vt.baglanti() as con:
            con.execute(
                "UPDATE " + TABLO + " SET son_gorulme_ts=?, dron_sayisi=?,"
                " yetenekler=? WHERE ornek_id=?",
                (dt.datetime.now(dt.timezone.utc), int(o.dron_sayisi),
                 json.dumps(o.yetenekler, ensure_ascii=False),
                 int(o.ornek_id)))


def bayat_temizle():
    """Surec cokmesinden sonra `cevrimici` kalmis kayitlari duzeltir.

    Acilista cagrilir. Yapilmazsa panel var olmayan koprueri cevrimici
    gosterir ve operator komutun gittigini sanir.
    """
    from . import veritabani as vt
    with contextlib.suppress(Exception):
        with vt.baglanti() as con:
            con.execute(
                "UPDATE " + TABLO + " SET cevrimici=? WHERE cevrimici=?",
                (False if vt.pg_kipinde() else 0,
                 True if vt.pg_kipinde() else 1))
    return True


# ======================================================================
# Merkez -> kopru istek/yanit
# ======================================================================
# ======================================================================
# v2.4.233: YEREL AKIS ROLESI — kopru <-> GCS ham byte kanali
# ======================================================================
# Merkez kipinde bu isi merkezin `mk_akis.AkisKopruleyici`si yapar
# (kopru --WSS--> merkez --UDP--> GCS). Yerel (kapali devre) kipte
# kopru soketi BU SURECTEDIR; yine de dron.py/pymavlink'in `udpin`
# arayuzu degismesin diye ayni desen kullanilir: kanal basina bir
# loopback UDP soketi acilir, kopruden gelen `akis` paketi o sokete
# yazilir, GCS'nin yazdigi datagram kopruye `akis` olarak gider.
#
# NEDEN GEREKLI: onceki surumde yerel kipte `akis` mesaji `pass` ile
# yutuluyordu ve `_akis_kanali_ac` merkez ic ucunu (`/api/ic/akis_ac`)
# cagirdigi icin kapali devre kurulumda kopru uzerinden dron baglantisi
# HIC calismiyordu. Android MAVLink/DJI kopruleri de gercek kopru ajani
# olunca (1.1.0) bu yol zorunlu hale geldi.
_AKIS_YEREL_ADRES = "127.0.0.1"
_AKIS_OKUMA_TAMPON = 65536
_AKIS_BEKLEME_ENUST = 256 * 1024


class YerelAkisKanali:
    __slots__ = ("ornek_id", "kanal_id", "tanim", "soket", "port", "gcs_es",
                 "beklemede", "kopruden_byte", "gcsden_byte", "son_hata",
                 "acilma_ts", "son_kopru_ts", "son_gcs_ts")

    def __init__(self, ornek_id, kanal_id, tanim):
        self.ornek_id = int(ornek_id)
        self.kanal_id = int(kanal_id)
        self.tanim = dict(tanim or {})
        self.soket = None
        self.port = 0
        self.gcs_es = None
        self.beklemede = bytearray()
        self.kopruden_byte = 0
        self.gcsden_byte = 0
        self.son_hata = ""
        self.acilma_ts = time.time()
        self.son_kopru_ts = 0.0
        self.son_gcs_ts = 0.0

    def ozet(self):
        return {"ornek_id": self.ornek_id, "kanal_id": self.kanal_id,
                "port": self.port, "tanim": self.tanim,
                "gcs_es": list(self.gcs_es) if self.gcs_es else None,
                "kopruden_byte": self.kopruden_byte,
                "gcsden_byte": self.gcsden_byte, "son_hata": self.son_hata,
                "acilma_ts": self.acilma_ts}


class YerelAkis:
    """Yerel kipte acik akis kanallarinin kayit defteri (bellek ici).

    `kanal_ac` OLAY DONGUSU is parcacigindan cagrilmalidir
    (`_akis_kanali_ac` bir coroutine'dir; kosul saglanir): soket
    okuyucusu `loop.add_reader` ile o donguye baglanir.
    """

    def __init__(self):
        self._kanallar = {}
        self._kilit = threading.Lock()

    def kanal_ac(self, ornek_id, kanal_id, tanim, gcs_port):
        oid, kid = int(ornek_id), int(kanal_id)
        try:
            dongu = asyncio.get_running_loop()
        except RuntimeError:
            return None, "Olay dongusu hazir degil"
        with self._kilit:
            eski = self._kanallar.get((oid, kid))
        if eski is not None:
            self.kanal_kapat(oid, kid)
        k = YerelAkisKanali(oid, kid, tanim)
        import socket as _sk
        s = _sk.socket(_sk.AF_INET, _sk.SOCK_DGRAM)
        try:
            s.bind((_AKIS_YEREL_ADRES, 0))
            s.setblocking(False)
        except Exception as e:
            with contextlib.suppress(Exception):
                s.close()
            return None, "UDP portu ayrilamadi: %s" % e
        k.soket = s
        k.port = int(s.getsockname()[1])
        if int(gcs_port or 0) > 0:
            k.gcs_es = (_AKIS_YEREL_ADRES, int(gcs_port))
        try:
            dongu.add_reader(s, self._gcsden_oku, k)
        except Exception as e:
            with contextlib.suppress(Exception):
                s.close()
            return None, "Soket donguye baglanamadi: %s" % e
        with self._kilit:
            self._kanallar[(oid, kid)] = k
        return k.ozet(), None

    def kanal_kapat(self, ornek_id, kanal_id):
        with self._kilit:
            k = self._kanallar.pop((int(ornek_id), int(kanal_id)), None)
        if k is None:
            return False
        s, k.soket = k.soket, None
        if s is not None:
            with contextlib.suppress(Exception):
                asyncio.get_running_loop().remove_reader(s)
            with contextlib.suppress(Exception):
                s.close()
        return True

    def ornek_kapat(self, ornek_id):
        """Kopru ayrildiginda o kopruye ait tum kanallar kapatilir."""
        with self._kilit:
            anahtarlar = [a for a in self._kanallar if a[0] == int(ornek_id)]
        for a in anahtarlar:
            self.kanal_kapat(*a)
        return len(anahtarlar)

    def kanal(self, ornek_id, kanal_id):
        with self._kilit:
            return self._kanallar.get((int(ornek_id), int(kanal_id)))

    def durum(self):
        with self._kilit:
            return [k.ozet() for k in self._kanallar.values()]

    # ---- kopru -> GCS ----
    def kopruden_geldi(self, ornek_id, kanal_id, veri_b64):
        k = self.kanal(ornek_id, kanal_id)
        if k is None or k.soket is None:
            return 0
        try:
            import base64 as _b64
            veri = _b64.b64decode(veri_b64 or "", validate=False)
        except Exception:
            return 0
        if not veri:
            return 0
        if k.gcs_es is None:
            k.beklemede.extend(veri)
            if len(k.beklemede) > _AKIS_BEKLEME_ENUST:
                del k.beklemede[:len(k.beklemede) - _AKIS_BEKLEME_ENUST]
            return 0
        try:
            n = k.soket.sendto(veri, k.gcs_es)
        except Exception as e:
            k.son_hata = "%s: %s" % (type(e).__name__, e)
            return 0
        k.kopruden_byte += n
        k.son_kopru_ts = time.time()
        return n

    # ---- GCS -> kopru ----
    def _gcsden_oku(self, k):
        s = k.soket
        if s is None:
            return
        while True:
            try:
                veri, es = s.recvfrom(_AKIS_OKUMA_TAMPON)
            except (BlockingIOError, InterruptedError):
                return
            except Exception as e:
                k.son_hata = "%s: %s" % (type(e).__name__, e)
                return
            if not veri:
                return
            if es[0] != _AKIS_YEREL_ADRES:
                continue
            if k.gcs_es != es:
                k.gcs_es = es
                if k.beklemede:
                    bek, k.beklemede = bytes(k.beklemede), bytearray()
                    with contextlib.suppress(Exception):
                        for i in range(0, len(bek), 8192):
                            k.soket.sendto(bek[i:i + 8192], es)
            k.gcsden_byte += len(veri)
            k.son_gcs_ts = time.time()
            o = ROLE.ornek_ile(k.ornek_id)
            if o is None:
                k.son_hata = "Kopru bagli degil"
                continue
            import base64 as _b64
            paket = json.dumps({"tur": "akis", "kanal_id": k.kanal_id,
                                "veri": _b64.b64encode(veri).decode("ascii")})
            with contextlib.suppress(Exception):
                asyncio.ensure_future(o.soket.send(paket))


AKIS = YerelAkis()


# ---------------------------------------------------------------------
# v2.4.242 (IS140): YEREL VIDEO ROLESI — kopruden gelen `video_kare`
# mesajlarini GRCOFF'un video vekilinin UDP portuna teslim eder (merkezdeki
# mk_video ile ayni sozlesme ve ayni GKVK parcalama bicimi).
# ---------------------------------------------------------------------
_VIDEO_PARCA_BYTE = 60000
_VIDEO_KARE_ENUST = 4 * 1024 * 1024
_VIDEO_MAGIC = b"GKVK"
_DONGU = None


def _video_parcala(veri, kare_no):
    import struct as _st
    if len(veri) <= _VIDEO_PARCA_BYTE:
        return [veri]
    parcalar = [veri[i:i + _VIDEO_PARCA_BYTE] for i in range(0, len(veri), _VIDEO_PARCA_BYTE)]
    say = len(parcalar)
    return [_VIDEO_MAGIC + _st.pack("!IHH", kare_no & 0xFFFFFFFF, i, say) + p
            for i, p in enumerate(parcalar)]


class YerelVideo:
    def __init__(self):
        self._kanallar = {}
        self._kilit = threading.Lock()
        self._sayac = 0

    def kanal_ac(self, ornek_id, kamera_id, app_port):
        import socket as _sk
        oid, kid = int(ornek_id), int(kamera_id)
        try:
            ap = int(app_port or 0)
        except Exception:
            ap = 0
        if ap <= 0 or ap > 65535:
            return None, "app_port zorunlu"
        self.kanal_kapat(oid, kid)
        s = _sk.socket(_sk.AF_INET, _sk.SOCK_DGRAM)
        try:
            s.bind(("127.0.0.1", 0))
            with contextlib.suppress(OSError):
                s.setsockopt(_sk.SOL_SOCKET, _sk.SO_SNDBUF, 4 << 20)
        except Exception as e:
            with contextlib.suppress(Exception):
                s.close()
            return None, "UDP portu ayrilamadi: %s" % e
        k = {"soket": s, "es": ("127.0.0.1", ap), "kare": 0, "byte": 0,
             "dusen": 0, "son_ts": 0.0, "son_hata": "", "acilma_ts": time.time()}
        with self._kilit:
            self._kanallar[(oid, kid)] = k
        return {"ornek_id": oid, "kamera_id": kid, "app_port": ap}, None

    def kanal_kapat(self, ornek_id, kamera_id):
        with self._kilit:
            k = self._kanallar.pop((int(ornek_id), int(kamera_id)), None)
        if k is None:
            return False
        with contextlib.suppress(Exception):
            k["soket"].close()
        return True

    def ornek_kapat(self, ornek_id):
        oid = int(ornek_id)
        with self._kilit:
            anahtarlar = [a for a in self._kanallar if a[0] == oid]
        for _, kid in anahtarlar:
            self.kanal_kapat(oid, kid)
        return len(anahtarlar)

    def kopruden_geldi(self, ornek_id, kamera_id, veri_b64):
        import base64 as _b64
        with self._kilit:
            k = self._kanallar.get((int(ornek_id), int(kamera_id)))
        if k is None:
            return 0
        try:
            veri = _b64.b64decode(veri_b64 or "", validate=True)
        except Exception as e:
            k["dusen"] += 1
            k["son_hata"] = "Kare cozulemedi (base64): %s" % type(e).__name__
            return 0
        if not veri or veri[:2] != b"\xff\xd8":
            k["dusen"] += 1
            k["son_hata"] = "Kare JPEG degil"
            return 0
        if len(veri) > _VIDEO_KARE_ENUST:
            k["dusen"] += 1
            k["son_hata"] = "Kare cok buyuk (%d bayt)" % len(veri)
            return 0
        self._sayac += 1
        toplam = 0
        try:
            for p in _video_parcala(veri, self._sayac):
                toplam += k["soket"].sendto(p, k["es"])
        except Exception as e:
            k["dusen"] += 1
            k["son_hata"] = "%s: %s" % (type(e).__name__, e)
            return 0
        k["kare"] += 1
        k["byte"] += toplam
        k["son_ts"] = time.time()
        return toplam

    def durum(self, ornek_id=None):
        with self._kilit:
            ks = list(self._kanallar.items())
        cikti = []
        for (oid, kid), k in ks:
            if ornek_id is not None and oid != int(ornek_id):
                continue
            cikti.append({"ornek_id": oid, "kamera_id": kid, "app_port": k["es"][1],
                          "kare": k["kare"], "byte": k["byte"], "dusen": k["dusen"],
                          "son_hata": k["son_hata"]})
        return cikti


VIDEO = YerelVideo()


def _dongu_cagir(coro, zaman_asimi):
    """Olay dongusu disindan (MJPEG is parcacigi) koprüye istek."""
    dongu = _DONGU
    if dongu is None or not dongu.is_running():
        return None, "Olay dongusu hazir degil"
    try:
        gelecek = asyncio.run_coroutine_threadsafe(coro, dongu)
        return gelecek.result(timeout=zaman_asimi), None
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)


def video_ac(ornek_id, firma_id, kamera_id, app_port, zaman_asimi=20.0):
    """`merkez_kimlik.video_ac` ile AYNI imza (sunucu._saha_video_kanal_ac)."""
    o = ROLE.ornek_ile(int(ornek_id))
    if o is None:
        return False, "Kopru cevrimdisi"
    ozet, hata = VIDEO.kanal_ac(ornek_id, kamera_id, app_port)
    if hata:
        return False, hata
    sonuc, h2 = _dongu_cagir(kopruden_iste(o, "video_canli_ac", {"id": int(kamera_id)},
                                           zaman_asimi=zaman_asimi), zaman_asimi + 2)
    if h2 or not isinstance(sonuc, tuple):
        VIDEO.kanal_kapat(ornek_id, kamera_id)
        return False, h2 or "Kopru yanit vermedi"
    veri, khata = sonuc
    if khata or not (veri or {}).get("tamam"):
        VIDEO.kanal_kapat(ornek_id, kamera_id)
        return False, khata or (veri or {}).get("hata") or "Kopru canli yayini baslatamadi"
    return True, ""


def video_kapat(ornek_id, firma_id, kamera_id):
    VIDEO.kanal_kapat(ornek_id, kamera_id)
    o = ROLE.ornek_ile(int(ornek_id))
    if o is None:
        return None
    _s, h = _dongu_cagir(kopruden_iste(o, "video_canli_kapat", {"id": int(kamera_id)},
                                       zaman_asimi=6.0), 8.0)
    return h


async def kopruden_iste(o, eylem, veri=None, zaman_asimi=15.0):
    """Kopruye istek gonderir ve yanitini bekler.

    Baglanti kopru tarafindan acildigi icin yerel merkez HICBIR GELEN
    PORT acmadan kopruye komut gonderebilir; kopru makinesinde guvenlik
    duvari kurali gerekmez.
    """
    if o is None:
        raise ConnectionError("Kopru cevrimdisi")
    istek_id = secrets.token_hex(8)
    dongu = asyncio.get_running_loop()
    global _DONGU
    _DONGU = dongu
    gelecek = dongu.create_future()
    o.bekleyen[istek_id] = gelecek
    paket = {"tur": "istek", "istek_id": istek_id, "eylem": str(eylem),
             "veri": veri or {}}
    try:
        await o.soket.send(json.dumps(paket, ensure_ascii=False))
        return await asyncio.wait_for(gelecek, timeout=float(zaman_asimi))
    except asyncio.TimeoutError:
        raise TimeoutError("Kopru yanit vermedi: %s" % eylem) from None
    finally:
        o.bekleyen.pop(istek_id, None)


def _yanit_isle(o, m):
    f = o.bekleyen.get(str(m.get("istek_id") or ""))
    if f is None or f.done():
        return
    if m.get("hata"):
        f.set_exception(RuntimeError(str(m["hata"])))
    else:
        f.set_result(m.get("veri") or {})


def _nabiz_isle(o, m):
    o.son_nabiz = time.time()
    try:
        o.dron_sayisi = int(m.get("dron_sayisi") or 0)
    except (TypeError, ValueError):
        o.dron_sayisi = 0
    if isinstance(m.get("yetenekler"), dict):
        o.yetenekler = m["yetenekler"]
    _nabiz_yaz(o)


# ======================================================================
# WebSocket oturumu
# ======================================================================
async def oturum(soket, konsol=None):
    """Bir kopru WS baglantisini bastan sona isler.

    `sunucu.ws_baglanti` yol `/kopru` ise BURAYA devreder ve soketi
    arayuz istemcileri kumesine EKLEMEZ: eklerse 10 Hz telemetri yayini
    kopruye gonderilir ve kopru protokolu bozulur.
    """
    def yaz(etiket, mesaj, seviye="bilgi"):
        if konsol:
            with contextlib.suppress(Exception):
                konsol(etiket, mesaj, seviye)
        else:
            print("[%s] %s" % (etiket, mesaj))

    ip = ""
    with contextlib.suppress(Exception):
        uzak = getattr(soket, "remote_address", None)
        if uzak:
            ip = str(uzak[0] or "")

    o = KopruOturumu(soket, ip)
    dogrulandi = False
    try:
        async for ham in soket:
            try:
                m = json.loads(ham)
            except Exception:
                continue
            if not isinstance(m, dict):
                continue
            tur = m.get("tur")

            if not dogrulandi:
                # ILK MESAJ merhaba OLMALI. Aksi halde kimlik
                # dogrulanmadan komut isleyen bir yol acilir.
                if tur != "merhaba":
                    await soket.send(json.dumps(
                        {"tur": "hata", "mesaj": "Ilk mesaj merhaba olmali"},
                        ensure_ascii=False))
                    return
                uid = str(m.get("kurulum_uid") or "")
                gizli = str(m.get("gizli") or "")
                k = None
                with contextlib.suppress(Exception):
                    k = _kimlik_oku(uid)
                if not k or not gizli_dogrula(gizli, k["gizli_ozet"]):
                    await soket.send(json.dumps(
                        {"tur": "hata",
                         "mesaj": "Kurulum kimligi gecersiz"},
                        ensure_ascii=False))
                    yaz("KOPRU", "Kimlik reddedildi (%s)" % (ip or "?"),
                        "uyari")
                    return
                if str(k["durum"] or "") != "etkin":
                    await soket.send(json.dumps(
                        {"tur": "hata", "mesaj": "Kurulum etkin degil"},
                        ensure_ascii=False))
                    return

                o.ornek_id = int(k["ornek_id"])
                o.kurulum_uid = uid
                o.ad = str(k["ad"] or "")
                o.surum = str(m.get("surum") or "")
                o.platform = str(m.get("platform") or "")
                o.makine_adi = str(m.get("makine_adi") or "")
                if isinstance(m.get("yetenekler"), dict):
                    o.yetenekler = m["yetenekler"]
                with contextlib.suppress(TypeError, ValueError):
                    o.dron_sayisi = int(m.get("dron_sayisi") or 0)

                # IS47_TEK_OTURUM_v1: canli oturum varsa `ekle` hata firlatir;
                # `dogrulandi` FALSE kalir ve `finally` blogu
                # CANLI oturumun isaretini EZMEZ.
                try:
                    await ROLE.ekle(o)
                except IkinciOturumHatasi:
                    print("[ROLE] Ikinci oturum reddedildi: "
                          "%s (ornek %s)" % (o.ad, o.ornek_id))
                    with contextlib.suppress(Exception):
                        await soket.send(json.dumps(
                            {"tur": "hata", "kod": "zaten_bagli",
                             "mesaj": "Bu kurulum icin zaten canli "
                                       "bir oturum var"},
                            ensure_ascii=False))
                    return
                _baglanti_acildi(o)
                dogrulandi = True
                await soket.send(json.dumps({
                    "tur": "merhaba_tamam",
                    "kanal": o.kanal,
                    "ornek_id": o.ornek_id,
                    "ad": o.ad,
                    "sunucu_zamani": dt.datetime.now(
                        dt.timezone.utc).isoformat(),
                }, ensure_ascii=False))
                yaz("KOPRU", "Kopru baglandi: %s (ornek %d, %s)"
                    % (o.ad, o.ornek_id, ip or "?"))
                continue

            if tur == "nabiz":
                _nabiz_isle(o, m)
                await soket.send(json.dumps({"tur": "nabiz_tamam"}))
            elif tur == "yanit":
                _yanit_isle(o, m)
            elif tur == "durum":
                _nabiz_isle(o, m)
            elif tur == "ucus":
                # Yerel kurulumda ucus kayitlari ZATEN yerel
                # veritabanindadir (GCS'in kendisi ucusu yazar). Kopru
                # ayrica gondermeye calisirsa cift kayit olusur; bu
                # yuzden kabul edilir ama YAZILMAZ, yalniz onaylanir.
                await soket.send(json.dumps(
                    {"tur": "ucus_tamam", "istek_id": m.get("istek_id"),
                     "ucus_id": None, "hata": None}))
            elif tur == "telemetri":
                await soket.send(json.dumps(
                    {"tur": "telemetri_tamam",
                     "istek_id": m.get("istek_id"), "adet": 0}))
            elif tur == "hedef":
                # IS91: GORUNTU KOPRUSU hedef verisi.
                # Yanit URETILMEZ: saniyede 2 paket gelir,
                # her birine yanit yazmak hatti bosuna mesgul
                # eder. Kopru tarafi da yanit BEKLEMEZ.
                o.hedef_paket += 1
                o.son_hedef_ts = time.time()
                if _hd is not None:
                    _hd.DEPO.yaz(o.ornek_id, o.ad, m)
            elif tur == "video_kare":
                # v2.4.242 (IS140): canli kamera karesi -> yerel video rolesi
                VIDEO.kopruden_geldi(o.ornek_id, m.get("kamera_id") or 0,
                                     m.get("veri") or "")
            elif tur == "akis":
                # HAM MAVLINK/GDP BYTE: saniyede ~50 paket. Gunluge
                # YAZILMAZ ve yanit URETILMEZ (atesle-unut). v2.4.233:
                # yerel role (`AKIS`) GCS'nin UDP portuna teslim eder.
                AKIS.kopruden_geldi(o.ornek_id, m.get("kanal_id") or 0,
                                    m.get("veri") or "")
    except Exception as e:
        adi = type(e).__name__
        if "ConnectionClosed" not in adi and not isinstance(
                e, asyncio.CancelledError):
            yaz("KOPRU", "Oturum hatasi: %s: %s" % (adi, e), "uyari")
    finally:
        if dogrulandi:
            await ROLE.cikar(o)
            # v2.4.233: kopru ayrildi -> bu kopruye ait akis kanallari
            # kapanir (yeniden baglanan oturum yeni kanal acar).
            if ROLE.ornek_ile(int(o.ornek_id)) is None:
                with contextlib.suppress(Exception):
                    AKIS.ornek_kapat(o.ornek_id)
                    VIDEO.ornek_kapat(o.ornek_id)
            _baglanti_kapandi(o)
            yaz("KOPRU", "Kopru ayrildi: %s (ornek %s)"
                % (o.ad, o.ornek_id))
