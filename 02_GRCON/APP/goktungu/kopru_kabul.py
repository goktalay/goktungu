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
    return True


def kopru_kaydet(ad, aciklama=""):
    """Yeni kopru kaydi uretir. `gizli` YALNIZ BIR KEZ doner.

    Sir veritabaninda ozet olarak tutulur; kaybedilirse yeni kayit
    uretilmesi gerekir. Bulut `ornek_kaydet()` ile ayni sozlesme.
    """
    from . import veritabani as vt
    uid = kurulum_uid_uret()
    gizli = gizli_uret()
    with vt.baglanti() as con:
        im = con.execute(
            "INSERT INTO " + TABLO +
            " (kurulum_uid, gizli_ozet, ad, aciklama) VALUES (?,?,?,?)",
            (uid, gizli_ozetle(gizli), str(ad or "Yerel Kopru"),
             str(aciklama or "")))
        oid = getattr(im, "lastrowid", None)
    if not oid:
        with vt.baglanti() as con:
            s = con.execute(
                "SELECT ornek_id FROM " + TABLO +
                " WHERE kurulum_uid=?", (uid,)).fetchone()
            oid = int(s[0]) if s else None
    return {
        "ornek_id": int(oid) if oid else None,
        "kurulum_uid": uid,
        "gizli": gizli,
        "ad": str(ad or "Yerel Kopru"),
    }


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
                "       son_ip, dron_sayisi, yetenekler, durum"
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
            con.execute(
                "UPDATE " + TABLO + " SET cevrimici=?, son_gorulme_ts=?,"
                " son_ip=?, surum=?, platform=?, makine_adi=?"
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
            elif tur == "akis":
                # HAM MAVLINK BYTE: saniyede ~50 paket. Gunluge
                # YAZILMAZ ve yanit URETILMEZ (atesle-unut); yanit
                # beklemek 20 ms araliklarli pakette kopruude gecikme
                # biriktirir. Yerel kurulumda akis kopruusu GCS'in
                # kendi UDP yayini uzerinden yurur.
                pass
    except Exception as e:
        adi = type(e).__name__
        if "ConnectionClosed" not in adi and not isinstance(
                e, asyncio.CancelledError):
            yaz("KOPRU", "Oturum hatasi: %s: %s" % (adi, e), "uyari")
    finally:
        if dogrulandi:
            await ROLE.cikar(o)
            _baglanti_kapandi(o)
            yaz("KOPRU", "Kopru ayrildi: %s (ornek %s)"
                % (o.ad, o.ornek_id))
