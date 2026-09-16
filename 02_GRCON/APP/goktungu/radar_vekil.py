# -*- coding: utf-8 -*-
"""GÖKTUNGU — MERKEZ KIPI RADAR VEKILI.

## KULLANICI ISTEGI (birebir)

    "radarda da ayni sorun var, radarin kopru yazilimi calisiyor ama
     sistem radari sunucuda ariyor"

Kullanicinin gordugu ekran: RADAR AYARLARI panelinde
`192.168.8.168:5001` girili, RADAR DURUMU = **HATA / timed out**.

## KOK NEDEN

Radar donanimi sahadaki OZEL agda durur (192.168.8.x). Merkez sunucu
(104.247.173.243) bu adrese ULASAMAZ; merkezde kosan `RadarIstemcisi`
sonsuza kadar TCP zaman asimi verir. Sorun ayar degil, TOPOLOJIDIR.

## COZUM

C20 oturumu SAHADA, kopru makinesinde kurulur (`kopru/servis_radar.py`
+ `kopru/radar_c20.py`). Merkez yalniz COZUMLENMIS durum ve iz verisini
kopruden ceker.

## NEDEN VEKIL SINIFI

Merkezdeki `sunucu.py` radar nesnesinin YEDI uyesini kullanir:

    durum · radar_ayarlar · hedefler · radar_konum() · ayar_kuyruk
    baglan() · kes()

Ayrica `angajman.py` de `radar.hedefler`i okur ve takipci motoru
(`self.takipci.isle`) bu sozluklerden beslenir. Bu nesneyi kaldirmak
yerine AYNI YUZU sunan bir vekil koymak, telemetri dongusunu, takipci
motorunu, kayit alt yapisini ve angajman mantigini HIC DEGISTIRMEDEN
kopru verisiyle beslemeyi saglar.

Alternatif "sunucu.py icine kopru dallari serpmek" olurdu; o yol yedi
ayri yerde kip denetimi gerektirir ve bir gun biri atlanirsa merkez
yeniden sahadaki adrese baglanmayi dener.

## SAAT FARKI (kritik)

Merkez izin tazeligini `simdi - h["son"] <= RADAR_IZ_ZAMANASIMI` ile
olcer. `son` degeri SAHA makinesinin saatidir; iki makinenin saati ayni
degildir (NTP olmayabilir). Fark ileri ise butun izler ANINDA suzulur,
geri ise dusen hedef haritada sonsuza kadar kalir.

Bu yuzden kopru her ize `yas_sn` (izin kac saniye once gorulduugu,
kendi saatiyle olculmus GORELI deger) koyar; vekil `son` alanini
MERKEZ saatine gore yeniden damgalar. Iki ayri saat hic
karsilastirilmaz.

## COKME YALITIMI

Kopru cagrisi basarisiz olursa vekil ESKI izleri korumaz; durumu
"hata" yazar ve iz listesini bosaltir. Gerekce: kopmus bir kopruden
gelen son iz, aslinda artik havada olmayan bir hedefi haritada
birakir. Operatorun bos harita gormesi, hayali hedef gormesinden
guvenlidir.
"""

from __future__ import annotations

import threading
import time


# Kopruden veri cekme araligi. Radar 2 Hz iz yayinlar; daha sik cekmek
# ayni veriyi tekrar tasir. Telemetri dongusu bundan hizli dondugu icin
# cekme SONUCU onbellekten okunur.
CEKME_ARALIK_SN = 0.5

# Kopru yanit vermezse durum "hata"ya cevrilmeden once taninan sure.
# Tek bir yavas yanit haritayi bosaltmamalidir; ancak gercek bir kopma
# en fazla bu sure icinde gorunur olmalidir.
KOPMA_TOLERANS_SN = 6.0


class RadarVekili:
    """`RadarIstemcisi` yuzunu tasiyan, kopru beslemeli vekil.

    Merkez kipinde `RadarIstemcisi` yerine konur. Kendi basina TCP
    baglantisi KURMAZ; komutlari kopruye devreder ve durumu kopruden
    okur.
    """

    def __init__(self, konsol, ayarlar, kilit, cek=None, radar_id=1):
        """
        konsol  : KonsolLog
        ayarlar : AyarYoneticisi (merkez konum yedegi icin)
        kilit   : paylasilan threading.Lock
        cek     : `() -> (paket, hata)` — kopruden BU radarin durumunu
                  getirir. v2.4.192 (Faz C): `RadarYoneticisi` tek kopru
                  cagrisini radar_id'ye gore boler ve her vekile kendi
                  alt paketini veren bir kapanis baglar. None ise vekil
                  "kopru yok" durumunda kalir.
        radar_id: bu vekilin radar kimligi (RadarIstemcisi ile ayni yuz).
        """
        self.konsol = konsol
        self.ayarlar = ayarlar
        self.kilit = kilit
        self._cek = cek
        self.radar_id = int(radar_id or 1)
        self.isim = ""
        self.konum_yedek = (None, None)
        self._son_cekme = 0.0
        self._son_basarili = 0.0
        self._cekme_kilit = threading.Lock()

        # --- RadarIstemcisi ile AYNI yuz ---
        self.durum = {
            "durum": "kapali", "ip": "", "port": 0, "hata": "",
            "lat": None, "lon": None, "hdt": None,
            "rtk_durum": "", "rtk_ilerleme": 0,
            "baglanti_ani": None, "son_veri_ani": None,
            "veri_hizi": 0.0, "hb_gecikme_ms": None,
            "crc_hata": 0, "toplam_mesaj": 0,
        }
        self.hedefler = {}
        self.radar_ayarlar = {
            "frekans": None, "hiz_esigi": None,
            "tespit_esigi": None, "rcs_esigi": None,
            "calisma_modu": None, "merkez_yonu": 0.0,
            "kaynak": "", "son_sonuc": "",
        }
        # Merkez kipinde ayarlar KOPRUDE uygulanir; kuyruk yalniz yuz
        # uyumlulugu icin durur ve hic islenmez.
        self.ayar_kuyruk = []
        self.kes_kancasi = None

    # ------------------------------------------------------------------
    # Yuz uyumlulugu
    # ------------------------------------------------------------------
    def ayar_yukle(self):
        """Merkez yonu ofsetini yerel ayardan yukler.

        Kopru de kendi merkez yonunu saklar; ancak merkez tarafinda bu
        deger yalniz kopru henuz hic yanit vermediginde gosterilir.
        """
        try:
            a = self.ayarlar.yukle()
            self.radar_ayarlar["merkez_yonu"] = (
                float(a.get("radar_merkez_yonu", 0.0)) % 360.0)
        except (TypeError, ValueError, AttributeError):
            self.radar_ayarlar["merkez_yonu"] = 0.0

    def radar_konum(self):
        """Radar konumu: kopruden gelen RTK varsa onu, yoksa merkez ayari.

        v2.4.198: KILIT ALINMAZ — cagiran (`RadarYoneticisi.hedefler`)
        telemetri dongusunde ayni yeniden girissiz kilidin icindedir;
        burada alinsa olay dongusu kilitlenir (bkz. radar.py:radar_konum).
        """
        lat = self.durum.get("lat")
        lon = self.durum.get("lon")
        if lat is not None and lon is not None:
            return lat, lon
        # v2.4.192: kayittaki kurulu konum (radarlar.lat/lon) merkez
        # ayarindan once gelir; aksi halde 2 numarali radar merkezin
        # konumunda sanilir ve izleri yanlis yere duser.
        try:
            ky = self.konum_yedek
            if ky and ky[0] is not None and ky[1] is not None:
                return float(ky[0]), float(ky[1])
        except (TypeError, ValueError):
            pass
        try:
            a = self.ayarlar.yukle()
            return float(a["merkez_lat"]), float(a["merkez_lon"])
        except (KeyError, TypeError, ValueError, AttributeError):
            return None, None

    def baglan(self, ip, port):
        """Merkez kipinde CAGRILMAZ.

        `sunucu.py` radar komutlarini kopruye yonlendirir; bu yol
        yalnizca bir gerileme olursa devreye girer. Sessiz kalmak
        yerine gunluge yazar: sahadaki radara merkezden baglanma
        denemesi her zaman zaman asimiyla biter.
        """
        self.konsol("RADAR", "Merkez kipinde radar baglantisi kopru "
                             "uzerinden kurulur; yerel deneme atlandi.")
        return False

    def kes(self):
        self.konsol("RADAR", "Merkez kipinde radar oturumu kopruden "
                             "kesilir; yerel deneme atlandi.")
        return False

    # ------------------------------------------------------------------
    # Kopru beslemesi
    # ------------------------------------------------------------------
    def cek_gerekirse(self):
        """Telemetri dongusunden cagrilir; gerekiyorsa kopruden ceker.

        Donguyu BLOKLAMAMAK icin cekme araligi uygulanir ve ayni anda
        yalniz bir cekme yapilir. Kilit alinamazsa (baska bir cekme
        suruyorsa) sessizce cikilir: onbellekteki son veri kullanilir.
        """
        simdi = time.time()
        if simdi - self._son_cekme < CEKME_ARALIK_SN:
            return
        if not self._cekme_kilit.acquire(blocking=False):
            return
        try:
            self._son_cekme = simdi
            if self._cek is None:
                self._kopru_yok("Kopru baglantisi yapilandirilmadi")
                return
            paket, hata = self._cek()
            if hata or not isinstance(paket, dict):
                self._kopru_hatasi(hata or "Kopru yanit vermedi")
                return
            self._uygula(paket, simdi)
            self._son_basarili = simdi
        except Exception as e:            # cekme HIC cokmemeli
            self._kopru_hatasi("%s: %s" % (type(e).__name__, e))
        finally:
            self._cekme_kilit.release()

    def _uygula(self, paket, simdi):
        """Kopru paketini vekil durumuna yazar (saat yeniden damgalanir)."""
        d = paket.get("radar_durum")
        a = paket.get("radar_ayarlar")
        izler = paket.get("izler")
        with self.kilit:
            if isinstance(d, dict):
                # Alanlari TEK TEK yazmak yerine guncelleme: kopru
                # surumu eski olup bir alani gondermezse eldeki deger
                # korunur, KeyError ile telemetri dongusu kirilmaz.
                self.durum.update(d)
            if isinstance(a, dict):
                self.radar_ayarlar.update(a)
            if isinstance(izler, list):
                yeni = {}
                for v in izler:
                    if not isinstance(v, dict):
                        continue
                    k = dict(v)
                    kid = k.get("id")
                    if kid is None:
                        continue
                    # SAAT FARKI DUZELTMESI: goreli yas -> merkez saati
                    try:
                        yas = float(k.pop("yas_sn", 0.0) or 0.0)
                    except (TypeError, ValueError):
                        yas = 0.0
                    k["son"] = simdi - max(0.0, yas)
                    yeni[kid] = k
                self.hedefler = yeni

    def _kopru_yok(self, mesaj):
        with self.kilit:
            self.durum["durum"] = "kapali"
            self.durum["hata"] = mesaj
            self.hedefler = {}

    def _kopru_hatasi(self, mesaj):
        """Kopru cagrisi basarisiz: tolerans asildiysa izleri bosalt."""
        simdi = time.time()
        if (self._son_basarili
                and simdi - self._son_basarili < KOPMA_TOLERANS_SN):
            # Gecici yavaslik: eldeki veri korunur, durum degistirilmez.
            return
        with self.kilit:
            self.durum["durum"] = "hata"
            self.durum["hata"] = mesaj
            self.hedefler = {}
