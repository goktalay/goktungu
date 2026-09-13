# -*- coding: utf-8 -*-
"""KOPRU AJANI — merkeze kalici TERS WebSocket baglantisi.

BU DOSYA GCS ILE PAYLASILAN CEKIRDEKTIR (`goktungu/goktungu/kopru.py` ile ayni
sinif). Kopru yazilimi ayni protokolu konusur; boylece merkez tarafinda
IKINCI bir protokol uygulamasi gerekmez. Ayni protokol iki yerde ayri
yazilsaydi biri degistiginde diger sessizce uyumsuz kalir ve kusur
yalniz sahada gorunurdu.

## NEDEN BU MODUL VAR

Kullanici istegi (birebir):

    "iletisim tek tarafli olacak bunuda belirteyim. Yani client to
     server olacak server kendisine yapilan baglanti uzerinden
     haberlesecek, yani kullanicilarin kurdugu sunucularin sabit ip'si
     yok"

Saha GCS kurulumlari NAT/guvenlik duvari arkasindadir. Merkez ASLA
sahaya baglanamaz. Bu yuzden baglantiyi HER ZAMAN saha acar ve merkez
ayni soket uzerinden istek gonderir:

    Saha GCS  --- WSS connect --->  Merkez (9443/kopru)
              <-- {"tur":"istek"} --
              --- {"tur":"yanit"} ->

Boylece sahada tek bir acik port bile gerekmez.

## TASARIM KARARLARI

1) AYRI IS PARCACIGI, AYRI ASYNCIO DONGUSU
   Ajan kendi `asyncio.run()` dongusunde calisir. GCS'nin ana dongusu
   telemetri yayinini 10 Hz surdurur; merkeze giden bir istek 12 sn
   bloke olsa bile ana dongu ETKILENMEZ. Ana dongude calistirilsaydi
   tek bir yavas merkez yaniti tum ucus arayuzunu dondururdu.

2) KAYIT YOKSA HIC BASLAMAZ
   Kimlik icinde `kurulum_uid` + `gizli` yoksa ajan sessizce baslamaz
   (hata degildir: kopru henuz merkeze kaydedilmemis olabilir). Kopru
   yaziliminda kimlik `kopru.ayar.kimlik_oku()`, GCS'de ise
   `veri/kopru.json` ile gelir; ajan kaynagi BILMEZ, yalniz sozlugu alir.

3) USTEL GERI CEKILME
   Merkez bakimda olabilir. Yeniden baglanma 3 sn'den baslar, 60 sn'ye
   kadar ikiye katlanir. Sabit kisa aralik, merkez kapali oldugunda
   binlerce kurulumdan gelen selle merkezi acilista bogar.

4) ISLEV HARITASI DISARIDAN ENJEKTE EDILIR
   Ajan GCS'nin ic yapilarini BILMEZ; `islevler` sozlugu alir. Boylece
   `sunucu.py` degistiginde bu modul degismez ve sinanabilir kalir
   (sinav betigi sahte islevlerle ajani dogrular).

5) KAYIT KAYBEDILMEZ
   Baglanti yokken gonderilen ucus/telemetri/video paketleri bellekte
   kuyruga alinir ve baglanti kurulunca sirayla aktarilir. Kuyruk 5000
   paketle sinirlidir (bellek korumasi).
"""
import asyncio
import base64
import contextlib
import json
import ssl
import threading
import time


def _b64(veri):
    return base64.b64encode(veri or b"").decode("ascii")


def _b64_coz(metin):
    try:
        return base64.b64decode(metin or "", validate=False)
    except Exception:
        return b""

# ONTANIMLI ADRES: 443 (portsuz).
# NEDEN: mobil operator aglari, otel/kurum guvenlik duvarlari ve bazi
# ulke omurgalari 9443 gibi standart disi portlari kapatir. Sahada
# telefonda /app/ arayüzu tam bu yuzden "Sunucu baglantisi yok" hatasi
# verdi. Merkez artik 443 uzerinde /kopru yolunda WS tuneli sundugu
# icin ontanimli adres portsuzdur ve her agda gecer.
VARSAYILAN_KOPRU_ADRES = "wss://goktungu.com/kopru"

# 443 kapali/filtreli ise denenecek YEDEK adresler. Eski kurulumlar ve
# 443'u TLS denetimiyle bozan vekiller icin 9443 korunur.
YEDEK_PORTLAR = (443, 9443)

# Nabiz araligi: merkez 90 sn'de bir nabiz gormezse kurulumu "kapali"
# isaretler (mk_ayar.kopru_zaman_asimi_sn). 25 sn, iki nabiz kaybini
# tolere eder ve yine de zaman asimindan once yenisini gonderir.
NABIZ_ARALIK_SN = 25.0
YENIDEN_BAGLAN_TABAN_SN = 3.0
YENIDEN_BAGLAN_ENUST_SN = 60.0
KUYRUK_SINIR = 5000
EL_SIKISMA_ZAMAN_ASIMI = 20.0
YEREL_ADLAR = ("127.0.0.1", "localhost", "::1", "0.0.0.0")


def _yerel_mi(adres):
    ad = str(adres or "")
    for on in ("wss://", "ws://"):
        if ad.startswith(on):
            ad = ad[len(on):]
            break
    ad = ad.split("/", 1)[0]
    if ":" in ad and not ad.startswith("["):
        ad = ad.split(":", 1)[0]
    return ad.lower() in YEREL_ADLAR


class KopruAjani:
    """Merkeze kalici ters baglanti tutan ajan (is parcacigi tabanli)."""

    def __init__(self, kimlik, islevler=None, gunluk=None):
        """
        kimlik: veri/kopru.json icerigi -> kurulum_uid, gizli,
                merkez_adres, ad, ornek_id, surum, platform, makine_adi
        islevler: eylem adi -> cagrilabilir. Merkez `{"tur":"istek",
                "eylem":"dron_liste"}` gonderdiginde ilgili islev
                cagrilir ve donusu `yanit.veri` olur.
        gunluk: (etiket, metin, seviye) alan cagrilabilir; GCS konsolu.
        """
        self.kimlik = dict(kimlik or {})
        self.islevler = dict(islevler or {})
        self._gunluk = gunluk
        self._iplik = None
        self._dur = threading.Event()
        self._dongu = None
        self._soket = None
        self.bagli = False
        self.kanal = None
        self.ornek_id = self.kimlik.get("ornek_id")
        self.son_hata = None
        self.baglanma_ts = None
        self.son_nabiz_ts = None
        self.deneme = 0
        self._kuyruk = []
        self._kuyruk_kilit = threading.Lock()
        # Yeniden baglanma beklemesini kesen olay. Olay dongusu icinde
        # kurulur (`_ana_dongu`); burada None baslatilir cunku ajan
        # nesnesi olay dongusu OLMAYAN bir is parcaciginda yaratilir.
        self._dur_aio = None

    # ------------------------------------------------------------------
    # Gunluk
    # ------------------------------------------------------------------
    def gunluk(self, metin, seviye="bilgi"):
        if self._gunluk:
            with contextlib.suppress(Exception):
                self._gunluk("KOPRU", metin, seviye)
                return
        print(f"[KOPRU] {metin}")

    # ------------------------------------------------------------------
    # Yasam dongusu
    # ------------------------------------------------------------------
    def yapilandirildi(self):
        return bool(self.kimlik.get("kurulum_uid") and self.kimlik.get("gizli"))

    @property
    def adres(self):
        return (str(self.kimlik.get("merkez_adres") or "").strip()
                or VARSAYILAN_KOPRU_ADRES)

    def _aday_adresler(self):
        """Denenecek adresleri sirayla dondurur (443 once).

        Kullanici acik bir port yazdiysa ona DOKUNULMAZ: elle verilen
        yapilandirma her zaman ustundur. Port yazmadiysa 443 ile
        baslanir, basarisiz olursa 9443 denenir; boylece 443'u TLS
        denetimiyle bozan vekillerin arkasindaki kurulumlar da baglanir.
        """
        ham = self.adres
        try:
            from urllib.parse import urlsplit, urlunsplit
            p = urlsplit(ham)
            if p.port:                      # elle port verilmis
                return [ham]
                                            # port yok -> yedekleri uret
            konak = p.hostname or ""
            if not konak:
                return [ham]
            adaylar = []
            for port in YEDEK_PORTLAR:
                yer = konak if port == 443 else f"{konak}:{port}"
                adaylar.append(urlunsplit(
                    (p.scheme, yer, p.path or "/kopru", "", "")))
            return adaylar
        except Exception:
            return [ham]

    def calisiyor(self):
        return bool(self._iplik and self._iplik.is_alive())

    def baslat(self):
        """Ajani arka planda baslatir. `(basarili, hata)` dondurur."""
        if not self.yapilandirildi():
            return False, ("Merkez kaydi yok. Panelde MERKEZ KAYDI "
                           "bolumunden 'Bu bilgisayari merkeze kaydet' "
                           "dugmesini kullanin.")
        if self.calisiyor():
            return True, None
        self._dur.clear()
        self._iplik = threading.Thread(target=self._kos, name="kopru-ajan",
                                       daemon=True)
        self._iplik.start()
        return True, None

    def durdur(self, bekle=3.0):
        """Ajani durdurur; acik soketi kapatir.

        v1.5.8: yeniden baglanma beklemesi de KESILIR (bkz.
        `_ana_dongu` icindeki aciklama). Yalnizca `self._dur` isaretlemek
        yetmiyordu: ajan beklemeden uyanip bir kez daha baglaniyordu.
        """
        self._dur.set()
        dongu, soket = self._dongu, self._soket
        # Bekleme olayini tetikle. `call_soon_threadsafe` kullanilir:
        # `asyncio.Event.set` is parcaciklari arasi guvenli DEGILDIR ve
        # dogrudan cagrilirsa uyanma bildirimi kaybolabilir.
        olay = getattr(self, "_dur_aio", None)
        if dongu is not None and olay is not None:
            with contextlib.suppress(Exception):
                dongu.call_soon_threadsafe(olay.set)
        if dongu is not None and soket is not None:
            with contextlib.suppress(Exception):
                asyncio.run_coroutine_threadsafe(soket.close(), dongu)
        if self._iplik and self._iplik.is_alive() and bekle:
            self._iplik.join(timeout=bekle)

    def durum(self):
        """Arayuze gonderilebilir durum ozeti (sir icermez)."""
        return {
            "yapilandirildi": self.yapilandirildi(),
            "calisiyor": self.calisiyor(),
            "bagli": bool(self.bagli),
            "adres": self.adres,
            "ad": self.kimlik.get("ad") or "",
            "ornek_id": self.ornek_id,
            "kanal": self.kanal,
            "son_hata": self.son_hata or "",
            "baglanma_ts": self.baglanma_ts,
            "son_nabiz_ts": self.son_nabiz_ts,
            "deneme": self.deneme,
            "bekleyen_kayit": len(self._kuyruk),
        }

    def _kos(self):
        try:
            asyncio.run(self._ana_dongu())
        except Exception as e:
            self.son_hata = f"{type(e).__name__}: {e}"
            self.gunluk(f"Ajan durdu: {self.son_hata}", "uyari")
        finally:
            self.bagli = False
            self._dongu = None

    async def _ana_dongu(self):
        self._dongu = asyncio.get_running_loop()
        # v1.5.8: DURDURMA BEKLEMEYI KESER.
        #
        # OLCULEN KUSUR: `durdur()` yalnizca `threading.Event`
        # (`self._dur`) isaretliyordu. Ajan yeniden baglanma
        # beklemesinde (`asyncio.sleep(3..60)`) ise bayragi ancak
        # uyandiginda goruyordu; uyanma ile bayrak denetimi arasinda
        # `_oturum()` cagrilip YENI bir baglanti kuruluyordu.
        #
        # Sahadaki etkisi: kullanici kopru panelinde "Durdur"a bastiktan
        # sonra ajan bir kez daha merkeze baglaniyor; merkez kurulumu
        # "cevrimici" gosteriyor ve operator durdurdugunu sandigi
        # makineye komut gonderebiliyor.
        #
        # Cozum: bekleme, olay dongusune ait bir `asyncio.Event`
        # uzerinden yapilir ve `durdur()` bu olayi is parcaciklari arasi
        # guvenli bicimde tetikler.
        self._dur_aio = asyncio.Event()
        gecikme = YENIDEN_BAGLAN_TABAN_SN
        while not self._dur.is_set():
            self.deneme += 1
            try:
                await self._oturum()
                gecikme = YENIDEN_BAGLAN_TABAN_SN     # basarili oturum
            except Exception as e:
                self.son_hata = f"{type(e).__name__}: {e}"
                if not self._dur.is_set():
                    self.gunluk(f"Baglanti kesildi ({self.son_hata}); "
                                f"{int(gecikme)} sn sonra yeniden denenecek",
                                "uyari")
            finally:
                self.bagli = False
                self.kanal = None
                self._soket = None
            if self._dur.is_set():
                break
            # Kesilebilir bekleme: durdurma isteginde ANINDA doner.
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._dur_aio.wait(), gecikme)
            if self._dur.is_set():
                break
            gecikme = min(gecikme * 2, YENIDEN_BAGLAN_ENUST_SN)
        self.gunluk("Ajan durduruldu.", "bilgi")

    # ------------------------------------------------------------------
    # Tek oturum
    # ------------------------------------------------------------------
    def _ssl_baglami(self, adres=None):
        adres = adres or self.adres
        if not adres.startswith("wss://"):
            return None
        baglam = ssl.create_default_context()
        # Yerel merkez kurulumunda (ayni makine) kendinden imzali
        # sertifika kacinilmazdir. Uzak adreslerde dogrulama ASLA
        # gevsetilmez: aksi halde her saha kurulumu ortadaki adam
        # saldirisina acilir.
        if _yerel_mi(adres) or self.kimlik.get("sertifika_dogrulama") is False:
            baglam.check_hostname = False
            baglam.verify_mode = ssl.CERT_NONE
        return baglam

    def _merhaba(self):
        return {
            "tur": "merhaba",
            "kurulum_uid": self.kimlik.get("kurulum_uid"),
            "gizli": self.kimlik.get("gizli"),
            "surum": str(self.kimlik.get("surum") or ""),
            "platform": str(self.kimlik.get("platform") or ""),
            "makine_adi": str(self.kimlik.get("makine_adi") or ""),
            "yetenekler": self._yetenekler(),
            "dron_sayisi": self._sayi("dron_sayisi"),
        }

    def _yetenekler(self):
        f = self.islevler.get("yetenekler")
        if f:
            with contextlib.suppress(Exception):
                y = f({})
                if isinstance(y, dict):
                    return y
        return {}

    def _sayi(self, ad):
        f = self.islevler.get(ad)
        if not f:
            return 0
        with contextlib.suppress(Exception):
            return int(f({}) or 0)
        return 0

    async def _oturum(self):
        """Aday adresleri sirayla dener; ilk kurulan baglanti kullanilir."""
        adaylar = self._aday_adresler()
        son_hata = None
        for i, adres in enumerate(adaylar):
            try:
                await self._tek_oturum(adres)
                return
            except Exception as e:
                son_hata = e
                # El sikisma/aga bagli hatalarda SIRADAKI adayi dene.
                # Kimlik reddi (merhaba_tamam gelmemesi) kalicidir;
                # port degistirmek cozmez, hemen yukari tasi.
                if isinstance(e, ConnectionError) and \
                        "Merkez baglantiyi kabul etmedi" not in str(e) and \
                        "gecersiz" not in str(e).lower():
                    pass
                elif isinstance(e, ConnectionError):
                    raise
                if i + 1 < len(adaylar):
                    self.gunluk(f"{adres} basarisiz "
                                f"({type(e).__name__}); siradaki adres "
                                f"deneniyor", "uyari")
        raise son_hata if son_hata else ConnectionError("Baglanti kurulamadi")

    async def _tek_oturum(self, adres):
        import websockets

        self.gunluk(f"Merkeze baglaniliyor: {adres}")
        async with websockets.connect(
                adres, ssl=self._ssl_baglami(adres), ping_interval=20,
                ping_timeout=20, close_timeout=5,
                max_size=32 * 1024 * 1024,
                open_timeout=EL_SIKISMA_ZAMAN_ASIMI) as soket:
            self._soket = soket
            await soket.send(json.dumps(self._merhaba(), ensure_ascii=False))
            ilk = json.loads(await asyncio.wait_for(
                soket.recv(), timeout=EL_SIKISMA_ZAMAN_ASIMI))
            if ilk.get("tur") != "merhaba_tamam":
                # Merkez reddi KALICI bir kusur olabilir (gizli gecersiz,
                # firma askida). Metni aynen tasi: kullanici cozecek.
                raise ConnectionError(ilk.get("mesaj")
                                      or "Merkez baglantiyi kabul etmedi")
            self.bagli = True
            self.son_hata = None
            self.kanal = ilk.get("kanal")
            self.ornek_id = ilk.get("ornek_id")
            self.baglanma_ts = time.time()
            self.son_nabiz_ts = time.time()
            self.gunluk(f"Merkeze baglandi: {ilk.get('ad') or '?'} "
                        f"(ornek {self.ornek_id}, kanal {self.kanal})",
                        "basari")
            nabiz = asyncio.ensure_future(self._nabiz_dongusu(soket))
            kuyruk = asyncio.ensure_future(self._kuyruk_dongusu(soket))
            try:
                async for ham in soket:
                    try:
                        m = json.loads(ham)
                    except ValueError:
                        continue
                    if isinstance(m, dict):
                        await self._mesaj_isle(soket, m)
            finally:
                for g in (nabiz, kuyruk):
                    g.cancel()
                    with contextlib.suppress(Exception,
                                             asyncio.CancelledError):
                        await g

    async def _nabiz_dongusu(self, soket):
        while True:
            await asyncio.sleep(NABIZ_ARALIK_SN)
            paket = {"tur": "nabiz", "dron_sayisi": self._sayi("dron_sayisi"),
                     "yetenekler": self._yetenekler()}
            f = self.islevler.get("durum")
            if f:
                with contextlib.suppress(Exception):
                    ek = f({})
                    if isinstance(ek, dict):
                        paket.update(ek)
            await soket.send(json.dumps(paket, ensure_ascii=False,
                                        default=str))

    async def _kuyruk_dongusu(self, soket):
        """Baglanti yokken biriken kayitlari merkeze aktarir."""
        while True:
            await asyncio.sleep(5.0)
            with self._kuyruk_kilit:
                if not self._kuyruk:
                    continue
                parti = self._kuyruk[:20]
            for paket in parti:
                await soket.send(json.dumps(paket, ensure_ascii=False,
                                            default=str))
            with self._kuyruk_kilit:
                self._kuyruk = self._kuyruk[len(parti):]

    async def _mesaj_isle(self, soket, m):
        tur = m.get("tur")
        if tur == "akis":
            # HIZLI YOL: merkezden gelen ham MAVLink byte'i. `istek`
            # cercevesinden AYRI tutuldu cunku yanit uretmez. Her komut
            # icin istek_id/Future/yanit ucgeni kurmak, 20 ms'de bir
            # gelebilen paketlerde gereksiz yuk ve gecikme demektir.
            islev = self.islevler.get("akis_yaz_ham")
            if islev is None:
                return
            with contextlib.suppress(Exception):
                islev(m.get("kanal_id"), _b64_coz(m.get("veri")))
            return
        if tur == "istek":
            eylem = str(m.get("eylem") or "")
            islev = self.islevler.get(eylem)
            yanit = {"tur": "yanit", "istek_id": m.get("istek_id")}
            if islev is None:
                yanit["hata"] = f"Bu kurulum '{eylem}' eylemini desteklemiyor"
            else:
                try:
                    sonuc = islev(m.get("veri") or {})
                    if asyncio.iscoroutine(sonuc):
                        sonuc = await sonuc
                    yanit["veri"] = (sonuc if isinstance(sonuc, dict)
                                     else {"sonuc": sonuc})
                except Exception as e:
                    yanit["hata"] = f"{type(e).__name__}: {e}"
            await soket.send(json.dumps(yanit, ensure_ascii=False,
                                        default=str))
        elif tur == "kapat":
            self.gunluk("Merkez baglantiyi kapatmak istedi.", "uyari")
            await soket.close()
        elif tur == "nabiz_tamam":
            self.son_nabiz_ts = time.time()
        elif tur in ("ucus_tamam", "video_tamam", "telemetri_tamam"):
            if m.get("hata"):
                self.gunluk(f"Merkez uyarisi ({tur}): {m['hata']}", "uyari")
        elif tur == "hata":
            self.son_hata = str(m.get("mesaj") or "Merkez hata bildirdi")
            self.gunluk(f"Merkez hatasi: {self.son_hata}", "uyari")

    # ------------------------------------------------------------------
    # Kayit gonderimi (ucus / telemetri / video)
    # ------------------------------------------------------------------
    def _gonder(self, paket):
        """Paketi merkeze yollar; baglanti yoksa kuyruga alir."""
        dongu, soket = self._dongu, self._soket
        if self.bagli and soket is not None and dongu is not None:
            try:
                asyncio.run_coroutine_threadsafe(
                    soket.send(json.dumps(paket, ensure_ascii=False,
                                          default=str)),
                    dongu).result(timeout=10)
                return True
            except Exception as e:
                self.son_hata = f"{type(e).__name__}: {e}"
        with self._kuyruk_kilit:
            self._kuyruk.append(paket)
            if len(self._kuyruk) > KUYRUK_SINIR:
                # En YENI kayitlar korunur: eski uclar zaten yerel
                # veritabaninda durur, merkez senkronu gecikmeli tamamlanir.
                self._kuyruk = self._kuyruk[-KUYRUK_SINIR:]
        return False

    def ucus_gonder(self, veri):
        return self._gonder({"tur": "ucus", "veri": veri})

    def telemetri_gonder(self, ucus_uid, ornekler):
        return self._gonder({"tur": "telemetri", "ucus_uid": ucus_uid,
                             "ornekler": list(ornekler or [])})

    def video_gonder(self, veri):
        return self._gonder({"tur": "video", "veri": veri})

    # ------------------------------------------------------------------
    # Radar akisi (durum + izler)
    # ------------------------------------------------------------------
    def akis_gonder(self, kanal_id, veri):
        """Ham MAVLink byte'ini merkeze yollar.

        `_gonder`'DEN AYRI yazilmistir ve KUYRUGA ALMAZ. Nedeni:
        `_gonder` baglanti yokken paketi kuyruga koyar; bu ucus
        kayitlari icin dogrudur ama telemetri byte'lari icin YANLISTIR.
        Kopmus baglantida 60 saniye biriken MAVLink cerceveleri, baglanti
        dondugunde GCS'ye toplu halde bosalir; GCS bunlari GUNCEL
        telemetri sanir ve dronu 60 sn once oldugu yerde gosterir. Sahada
        bu, pilotun gecmis konuma bakarak karar vermesi demektir.

        Ayrica `_gonder` her paket icin `result(timeout=10)` ile BLOKE
        olur; 50 paket/sn akista bu kabul edilemez. Burada gonderim
        atesle-unut bicimindedir.
        """
        dongu, soket = self._dongu, self._soket
        if not (self.bagli and soket is not None and dongu is not None):
            return False
        paket = {"tur": "akis", "kanal_id": int(kanal_id),
                 "veri": _b64(veri)}
        try:
            asyncio.run_coroutine_threadsafe(
                soket.send(json.dumps(paket, ensure_ascii=False)), dongu)
            return True
        except Exception as e:
            self.son_hata = f"{type(e).__name__}: {e}"
            return False
