# -*- coding: utf-8 -*-
"""KOPRU AJANI — GCS'den merkeze kalici TERS WebSocket baglantisi.

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
   `veri/kopru.json` icinde `kurulum_uid` + `gizli` yoksa ajan sessizce
   baslamaz (hata degildir: merkez kullanmayan kurulumlar normaldir).

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
import contextlib
import json
import ssl
import threading
import time

VARSAYILAN_KOPRU_ADRES = "wss://goktungu.com/kopru"

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

    def calisiyor(self):
        return bool(self._iplik and self._iplik.is_alive())

    def baslat(self):
        """Ajani arka planda baslatir. `(basarili, hata)` dondurur."""
        if not self.yapilandirildi():
            return False, ("Merkez kaydi yok. Program Ayarlari -> Merkez "
                           "Sunucu bolumunden 'Bu kurulumu merkeze kaydet' "
                           "dugmesini kullanin.")
        if self.calisiyor():
            return True, None
        self._dur.clear()
        self._iplik = threading.Thread(target=self._kos, name="kopru-ajan",
                                       daemon=True)
        self._iplik.start()
        return True, None

    def durdur(self, bekle=3.0):
        """Ajani durdurur; acik soketi kapatir."""
        self._dur.set()
        dongu, soket = self._dongu, self._soket
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
            await asyncio.sleep(gecikme)
            gecikme = min(gecikme * 2, YENIDEN_BAGLAN_ENUST_SN)
        self.gunluk("Ajan durduruldu.", "bilgi")

    # ------------------------------------------------------------------
    # Tek oturum
    # ------------------------------------------------------------------
    def _ssl_baglami(self):
        adres = self.adres
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
        import websockets

        adres = self.adres
        self.gunluk(f"Merkeze baglaniliyor: {adres}")
        async with websockets.connect(
                adres, ssl=self._ssl_baglami(), ping_interval=20,
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
