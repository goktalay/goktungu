# -*- coding: utf-8 -*-
"""GÖKTUNGU — MERKEZ KIPI VIDEO ve AI VEKILLERI.

## KULLANICI ISTEGI (birebir)

    "hem ai icin hem kameralar icin ayni kopru gruplamasi gerekiyor"

ve daha once radar/GCCDUAL icin soylenen:

    "GCS icinde kopru kurulu olan makinede porta baglanmali, sanirim su
     an sunucu da ariyor portu"

## KOK NEDEN (radar kusurunun AYNISI)

Kameralar ve AI bilgisayarlari sahadaki OZEL agda durur:

    kamera        rtsp://192.168.1.50/stream    ya da USB indeks 0
    AI bilgisayari http://192.168.1.100:8900

Merkez sunucu (104.247.173.243) bir veri merkezindedir ve bu adreslerin
HICBIRINE ulasamaz. Onceki surumde:

  * `kamera_cihazlari` merkezde `cv2.VideoCapture(0..5)` deniyordu ->
    merkezde kamera aygiti YOK, liste HER ZAMAN bos donuyordu;
  * kamera akisi merkezdeki `VideoProxy` tarafindan aciliyordu -> yalniz
    genel internete acik kameralar calisiyordu (kullanicinin ekledigi
    `97.76.27.170` bu yuzden geliyordu, `192.168.x.x` gelmiyordu);
  * `ai_izleme_baslat` merkezden `http://{saha AI}:8900/izle` cagiriyordu
    -> her istek zaman asimina dusuyordu. Ustelik isciye verilen akis
    adresi de MERKEZIN 8801 vekilini gosteriyordu; isci o adrese de
    erisemezdi. Zincir iki noktadan birden kopuyordu.

## COZUM

Akis ve cikarim SAHADA kosar (`kopru/servis_video.py`,
`kopru/servis_ai.py`). Merkez yalniz COZUMLENMIS durumu kopruden ceker.

## NEDEN VEKIL SINIFI (radar vekiliyle ayni gerekce)

`sunucu.py` bu iki nesnenin belirli uyelerini cagirir. Nesneleri
kaldirmak yerine AYNI YUZU sunan bir vekil koymak, kamera listesi
duyurusunu, AI izleme esitlemesini ve angajman mantigini HIC
DEGISTIRMEDEN kopru verisiyle beslemeyi saglar.

Alternatif "sunucu.py icine kopru dallari serpmek" olurdu; o yol her
cagri yerinde kip denetimi gerektirir ve bir gun biri atlanirsa merkez
yeniden sahadaki adrese baglanmayi dener — yani kusur sessizce geri
gelir.

## GORUNTU MERKEZE TASINMAZ (bilincli karar)

Vekil kopruden KARE cekmez, yalnizca durum ozeti ceker. Gerekce
olculebilir: radar izi saniyede birkac kilobayt, video ise kiraci
basina megabit olcegindedir. Kareleri merkeze tasimak, kiraci sayisiyla
carpilan bir bant genisligi yuku dogurur ve paylasilan merkezi coker.
Operator goruntuyu kopru panelinden (yerel agda, 8801) izler; merkez
akisin ACIK olup olmadigini bilir ve durumu dogru gosterir.

## COKME YALITIMI

Kopru cagrisi basarisiz olursa vekil ESKI ozeti korumaz: durumu "hata"
yazar ve listeleri bosaltir. Kopmus bir kopruden gelen son ozet,
aslinda kapali olan bir akisi "yayinda" gosterir; operatorun bos liste
gormesi, olmayan bir yayina guvenmesinden guvenlidir.
"""

from __future__ import annotations

import contextlib
import socket
import threading
import time

# Kopruden ozet cekme araligi.
#
# Radar vekilinden (0.5 sn) DAHA SEYREKtir ve bu bilincli: radar izi
# harita uzerinde surekli hareket eder, video/AI ozeti ise durum
# gostergesidir (akis acik mi, isci cevrimici mi). Yarim saniyede bir
# sormak ayni veriyi tasiyip merkezle kopru arasindaki baglantiyi bosa
# mesgul ederdi.
CEKME_ARALIK_SN = 2.0

# Kopru yanit vermezse durum "hata"ya cevrilmeden once taninan sure.
# Tek bir yavas yanit listeyi bosaltmamalidir; ancak gercek bir kopma
# en fazla bu sure icinde gorunur olmalidir.
KOPMA_TOLERANS_SN = 8.0


class _KopruVekilTemel:
    """Iki vekilin paylastigi cekme/yalitim mantigi.

    Iki ayri kopya tutmak, birinde duzeltilen kusurun otekinde kalmasina
    yol acar (bkz. `_kopru_servis_sec` ayni gerekceyle ortaklastirildi).
    """

    def __init__(self, konsol, kilit, cek=None, etiket="SAHA"):
        self.konsol = konsol
        self.kilit = kilit
        self._cek = cek
        self._etiket = etiket
        self._son_cekme = 0.0
        self._son_basarili = 0.0
        self._cekme_kilit = threading.Lock()
        self._kopru_hata = ""

    # ------------------------------------------------------------------
    def cek_gerekirse(self, zorla=False):
        """Gerekiyorsa kopruden ozet ceker.

        HICBIR KOSULDA ISTISNA FIRLATMAZ: cagiran taraf telemetri
        dongusu ya da WS komut isleyicisidir; orada olusan bir istisna
        butun yayini durdurur.
        """
        simdi = time.time()
        if not zorla and (simdi - self._son_cekme) < CEKME_ARALIK_SN:
            return
        # Kilit BEKLEMEDEN denenir: birden fazla oturum es zamanli
        # sorabilir, ikinci cagri beklemek yerine onbellekten okumaya
        # devam etmelidir.
        if not self._cekme_kilit.acquire(blocking=False):
            return
        try:
            self._son_cekme = simdi
            if not self._cek:
                self._bozuk("Saha makinesi baglantisi kurulmadi.")
                return
            try:
                paket, hata = self._cek()
            except Exception as e:                      # savunma amacli
                paket, hata = None, "%s: %s" % (type(e).__name__, e)
            if hata or not isinstance(paket, dict):
                # Tolerans: tek bir yavas/bos yanit listeyi bosaltmaz.
                if (simdi - self._son_basarili) > KOPMA_TOLERANS_SN:
                    self._bozuk(hata or "Saha makinesi yanit vermedi.")
                return
            self._son_basarili = simdi
            self._kopru_hata = ""
            try:
                self._uygula(paket)
            except Exception as e:
                self._bozuk("Saha verisi cozumlenemedi: %s: %s"
                            % (type(e).__name__, e))
        finally:
            self._cekme_kilit.release()

    # Alt siniflar dolduracak.
    def _uygula(self, paket):
        raise NotImplementedError

    def _bozuk(self, hata):
        raise NotImplementedError

    def _hata_yaz(self, hata):
        """Ayni hatayi tekrar tekrar gunluge yazmaz.

        Kopru kapaliyken cekme her 2 saniyede bir basarisiz olur; her
        birini yazmak konsolu kullanilamaz hale getirir ve gercek
        hatalari gomer.
        """
        if hata and hata != self._kopru_hata:
            self._kopru_hata = hata
            try:
                self.konsol(self._etiket, hata, "uyari")
            except Exception:
                pass


KARE_MAGIC = b"GKVK"
_BASLIK_BICIM = "!IHH"
_BASLIK_BOY = 4 + 8


class KareBirlestirici:
    """v2.4.242 (IS140): merkezden gelen datagramlari JPEG kareye cevirir.

    Iki bicim kabul edilir:
      * ham JPEG datagram (eski merkez / kucuk kare) -> oldugu gibi
      * `GKVK + kare_no(u32) + parca_no(u16) + parca_sayisi(u16) + veri`
        parcalari -> ayni kare_no'nun tum parcalari gelince birlestirilir.
    Eksik parcali kare, yeni bir kare_no gelince ATILIR (tamponlanmaz).
    """

    def __init__(self):
        self.kare_no = None
        self.parcalar = {}
        self.sayi = 0
        self.dusen = 0
        self.birlesen = 0

    def ekle(self, veri):
        if not veri:
            return None
        if veri[:2] == b"\xff\xd8":
            return veri
        if len(veri) < _BASLIK_BOY or veri[:4] != KARE_MAGIC:
            return None
        import struct as _st
        no, idx, say = _st.unpack(_BASLIK_BICIM, veri[4:_BASLIK_BOY])
        if say == 0 or idx >= say:
            return None
        if no != self.kare_no:
            if self.kare_no is not None and self.parcalar:
                self.dusen += 1
            self.kare_no = no
            self.parcalar = {}
            self.sayi = say
        self.parcalar[idx] = veri[_BASLIK_BOY:]
        if len(self.parcalar) < self.sayi:
            return None
        kare = b"".join(self.parcalar[i] for i in range(self.sayi))
        self.parcalar = {}
        self.kare_no = None
        if kare[:2] != b"\xff\xd8":
            self.dusen += 1
            return None
        self.birlesen += 1
        return kare


class _UzakYayin:
    """Merkez uzerinden gelen kareleri tasiyan yayin nesnesi.

    `video_proxy._Yayin` ile AYNI sozlesmeyi uygular; boylece
    `mjpeg_sunucusu_kos` govdesi hangi kipte oldugunu bilmez.

    ## NEDEN AYRI SINIF (ve `_Yayin`den turetilmiyor)

    `_Yayin.baslat()` protokole gore ffmpeg sureci ya da OpenCV
    yakalamasi acar; ikisi de burada YANLIStir — kaynak sahadadir.
    Turetip `baslat`i ezmek, miras alinan `surec`, `url`, `protokol`
    alanlarini anlamsiz birakirdi. Ayri sinif, sozlesmeyi acikca
    yazar ve yanlis alan tasimaz.
    """

    #  Tek datagram = tek JPEG kare. Merkez tarafi 63 KB ustunu zaten
    #  dusurur; buradaki tampon UDP mutlak tavanidir.
    OKUMA_TAMPON = 65535

    def __init__(self, kamera_id, kanal_ac, kanal_kapat, konsol=None):
        self.kamera_id = int(kamera_id)
        self.konsol = konsol
        self._kanal_ac = kanal_ac
        self._kanal_kapat = kanal_kapat
        self.soket = None
        self.port = 0
        self.son_kare = None
        self.kare_no = 0
        self.kosul = threading.Condition()
        self.calisiyor = False
        self.izleyiciler = 0
        self.hata = None
        self._son_izleyici_zamani = time.time()

    # ------------------------------------------------------------------
    def baslat(self):
        """UDP ucunu acar ve merkeze kanal actirir. `(ok, gerekce)`.

        SIRA ONEMLIDIR: port ONCE burada bind edilir, sonra merkeze
        bildirilir. Ters sira, MAVLink akisinda olculmus
        `[Errno 98] Address already in use` kusurunun aynisini
        uretirdi.
        """
        if self.calisiyor:
            return True, ""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.bind(("127.0.0.1", 0))
            s.settimeout(1.0)
            with contextlib.suppress(OSError):
                s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
        except Exception as e:
            with contextlib.suppress(Exception):
                s.close()
            self.hata = "UDP portu acilamadi: %s" % e
            return False, self.hata
        self.soket = s
        self.port = int(s.getsockname()[1])
        try:
            tamam, gerekce = self._kanal_ac(self.kamera_id, self.port)
        except Exception as e:
            tamam, gerekce = False, "%s: %s" % (type(e).__name__, e)
        if not tamam:
            with contextlib.suppress(Exception):
                s.close()
            self.soket = None
            self.hata = str(gerekce or "Merkez canli kanali acmadi")
            return False, self.hata
        self.calisiyor = True
        self.hata = None
        threading.Thread(target=self._oku, daemon=True).start()
        threading.Thread(target=self._bekci, daemon=True).start()
        if self.konsol:
            self.konsol("Canli yayin acildi (kamera %d, port %d)"
                        % (self.kamera_id, self.port))
        return True, ""

    def _oku(self):
        """UDP'den kare okur. Datagram ya TAM bir JPEG ya da GKVK parcasidir (v2.4.242)."""
        bos_tur = 0
        birlestirici = KareBirlestirici()
        while self.calisiyor and self.soket is not None:
            try:
                veri, _ = self.soket.recvfrom(self.OKUMA_TAMPON)
            except socket.timeout:
                bos_tur += 1
                # 60 sn kare gelmezse kaynak gercekten durmustur.
                # Sessizce beklemek yerine gerekce yazilir; operator
                # "goruntu donmus" yerine nedeni gorur.
                if bos_tur >= 60 and self.izleyiciler > 0:
                    self.hata = ("Saha makinesinden 60 saniyedir kare "
                                 "gelmiyor")
                continue
            except OSError:
                break
            except Exception:
                break
            if not veri:
                continue
            bos_tur = 0
            kare = birlestirici.ekle(veri)
            if kare is None:
                continue
            self.hata = None
            with self.kosul:
                self.son_kare = kare
                self.kare_no += 1
                self.kosul.notify_all()
        self.calisiyor = False
        with self.kosul:
            self.kosul.notify_all()

    def ilk_kare_bekle(self, sure=12.0):
        """Ilk kare gelene kadar bekler.

        `_Yayin.ilk_kare_bekle` ile ayni gerekce (v2.4.33): basliklar
        kare gelmeden yazilirsa tarayici bos govdeli multipart'ta
        `error` atesler ve kutu kalici "YAYIN ALINAMIYOR" durumuna
        duser.
        """
        bitis = time.time() + float(sure)
        while time.time() < bitis:
            if self.son_kare is not None:
                return True
            if not self.calisiyor:
                return False
            with self.kosul:
                self.kosul.wait(timeout=0.25)
        return self.son_kare is not None

    def durdur(self):
        self.calisiyor = False
        if self._kanal_kapat:
            with contextlib.suppress(Exception):
                self._kanal_kapat(self.kamera_id)
        s, self.soket = self.soket, None
        if s is not None:
            with contextlib.suppress(Exception):
                s.close()
        with self.kosul:
            self.kosul.notify_all()

    def _bekci(self):
        """Izleyici kalmadiysa 30 sn sonra kanali kapatir.

        `_Yayin._bekci` ile ayni sure. Burada daha da onemlidir:
        kanal acik kaldigi surece SAHADAN merkeze bant genisligi
        harcanir. Kimse izlemiyorsa bu tamamen bosa gider.
        """
        while self.calisiyor:
            time.sleep(5)
            if self.izleyiciler <= 0 and \
                    time.time() - self._son_izleyici_zamani > 30:
                if self.konsol:
                    self.konsol("Izleyici kalmadi, canli yayin "
                                "kapatildi (kamera %d)" % self.kamera_id)
                self.durdur()
                break

    def izleyici_ekle(self):
        self.izleyiciler += 1
        self._son_izleyici_zamani = time.time()

    def izleyici_cikar(self):
        self.izleyiciler = max(0, self.izleyiciler - 1)
        self._son_izleyici_zamani = time.time()


class VideoVekili(_KopruVekilTemel):
    """`VideoProxy` yuzunu tasiyan, kopru beslemeli vekil.

    Merkez kipinde `VideoProxy` yerine konur. Kendi basina KAYNAK ACMAZ;
    komutlari kopruye devreder ve durumu kopruden okur.

    `sunucu.py` ve `ai_yonetici.py` su uyeleri kullanir:
        cihaz_listesi() · yayin_durdur(id) · dji_kopru
        calistir() · durum()
    """

    def __init__(self, konsol, kilit, cek=None, komut=None):
        """
        cek   : `() -> (paket, hata)` — kopruden video durumu getirir.
        komut : `(eylem, veri) -> (sonuc, hata)` — kopruye komut gonderir.
        """
        super().__init__(konsol, kilit, cek, etiket="VIDEO")
        self._komut = komut
        self.akislar = {}          # id -> ozet
        self.durum_ozet = {
            "hazir": False, "etkin": 0, "port": 0,
            "ffmpeg": False, "opencv": False, "hata": "",
        }
        # `dji_kopru` merkezde de atanir (main.py); DJI kamera URL
        # cozumu icin durur. Merkez kipinde DJI akisi da sahada acilir,
        # ancak nitelik varligi cagiranlarin kirilmamasi icin korunur.
        self.dji_kopru = None
        # FAZ19-IS60 — canli yayin durumu
        try:
            from .video_proxy import VIDEO_PROXY_PORT as _vp
        except Exception:
            try:
                from video_proxy import VIDEO_PROXY_PORT as _vp
            except Exception:
                _vp = 8801
        self.port = _vp
        self._yayinlar = {}
        self._yayin_kilit = threading.Lock()
        self._son_acilis_hata = {}
        # `sunucu.py` baglar; imza `_komut` ile ayni gerekceyle
        # ayridir: kanal acmak ornek_id/firma_id baglami ister ve o
        # baglam sunucuda durur, vekilde DEGIL.
        self._kanal_ac = None      # (kamera_id, app_port) -> (ok, hata)
        self._kanal_kapat = None   # (kamera_id) -> hata | None

    # ------------------------------------------------------------------
    # VideoProxy yuz uyumlulugu
    # ------------------------------------------------------------------
    def calistir(self):
        """MJPEG vekil sunucusunu acar (FAZ19-IS60).

        ## ONCEKI DAVRANIS VE NEDEN YANLISTI

        Bu islev BOS donuyordu; gerekce olarak "merkezde kaynak yok"
        yaziliydi. O gerekce dogruydu ama EKSIKTI: arayuz tarafi
        `window.location.hostname + ":8801"` adresine baglanmaya
        devam ediyordu. Yani tasarim "akis sahada sunulur" diyor,
        kod ise merkezin portunu cagiriyordu. Olculen sonuc: merkez
        kipinde hicbir kamera goruntusu GELMIYORDU (kopru gunlugu
        "Izleyici kalmadi" satirini basiyordu — akisi tuketen kimse
        yoktu).

        ## SIMDIKI DAVRANIS

        Kopru 1.7.5 kareyi merkeze yolluyor, merkez onu bu surecin
        UDP portuna tesliminciyor. Artik burada gercek bir sunucu
        acilir ve `yayin_al()` uzak kareleri besler.
        """
        try:
            self.konsol("VIDEO",
                        "Merkez kipi: kamera akisi saha koprusunden "
                        "aktarilir (port %d)." % self.port, "bilgi")
        except Exception:
            pass
        try:
            from .video_proxy import mjpeg_sunucusu_kos
        except Exception:
            from video_proxy import mjpeg_sunucusu_kos
        mjpeg_sunucusu_kos(self, self.port, self._konsol_tek)

    def _konsol_tek(self, metin):
        """`mjpeg_sunucusu_kos` tek argumanli konsol bekler."""
        try:
            self.konsol("VIDEO", str(metin), "bilgi")
        except Exception:
            pass

    def son_hata(self, kamera_id):
        """`mjpeg_sunucusu_kos` 503 gerekcesi icin cagirir."""
        with self._yayin_kilit:
            y = self._yayinlar.get(int(kamera_id))
        if y is not None and y.hata:
            return str(y.hata)
        return self._son_acilis_hata.get(int(kamera_id)) or \
            "Canli yayin baslatilamadi"

    def cihaz_listesi(self, en_fazla=6):
        """SAHADAKI yerel kameralari listeler.

        Onceki surumde bu tarama merkezde yapiliyordu ve merkezde kamera
        aygiti olmadigi icin HER ZAMAN bos donuyordu; kullanici cantaya
        takili kamerayi listede goremiyordu.

        Donus, `VideoProxy.cihaz_listesi` ile ayni bicimdedir (sozluk
        listesi); boylece arayuz tarafi degismez.
        """
        if not self._komut:
            return []
        try:
            sonuc, hata = self._komut("video_cihazlar",
                                      {"en_fazla": int(en_fazla or 6)})
        except Exception as e:
            self._hata_yaz("Cihaz taramasi basarisiz: %s" % e)
            return []
        if hata:
            self._hata_yaz("Cihaz taramasi basarisiz: %s" % hata)
            return []
        sonuc = sonuc or {}
        if sonuc.get("opencv") is False:
            # Kullaniciya EYLEME DONUK gerekce: "kamera yok" demek
            # yanlis olurdu, eksik olan OpenCV'dir.
            self._hata_yaz(
                "Saha makinesinde OpenCV kurulu degil; yerel USB kamera "
                "taranamadi. Kurulum: pip install opencv-python-headless")
        return list(sonuc.get("cihazlar") or [])

    def yayin_al(self, kamera_id):
        """Uzak kamera icin yayin nesnesi dondurur (FAZ19-IS60).

        Basarisizlikta `None` doner ve gerekce `son_hata()` ile
        okunabilir hale gelir. Gerekcenin ayri tutulmasi bilincli:
        `mjpeg_sunucusu_kos` 503 govdesine o metni yazar ve operator
        "YAYIN ALINAMIYOR" yerine gercek nedeni gorur.
        """
        try:
            kid = int(kamera_id)
        except (TypeError, ValueError):
            return None
        with self._yayin_kilit:
            y = self._yayinlar.get(kid)
            if y is not None and y.calisiyor:
                return y
            if y is not None:
                # Olu yayin: temizlenir, yenisi acilir.
                self._yayinlar.pop(kid, None)
        if not self._kanal_ac:
            self._son_acilis_hata[kid] = (
                "Saha makinesi baglantisi kurulmadi.")
            return None
        y = _UzakYayin(kid, self._kanal_ac, self._kanal_kapat,
                       self._konsol_tek)
        tamam, gerekce = y.baslat()
        if not tamam:
            self._son_acilis_hata[kid] = gerekce or "kanal acilamadi"
            return None
        with self._yayin_kilit:
            self._yayinlar[kid] = y
        self._son_acilis_hata.pop(kid, None)
        return y

    def yayin_durdur(self, kamera_id):
        """Yayini durdurur: ONCE yerel durum, SONRA saha komutu.

        FAZ19-IS63 — NEDEN: onceki surum yalnizca sahaya komut
        gonderiyordu. `self._yayinlar` kaydi silinmedigi ve
        `_UzakYayin.durdur()` cagrilmadigi icin `calisiyor`
        bayragi True kaliyordu; `yayin_al()` bir sonraki cagrida
        bu OLU nesneyi geri veriyordu. Saha kaynagi kapali
        oldugundan kare gelmiyor, tarayici siyah kutu goruyor ve
        her deneme `ilk_kare_bekle` suresince istegi acik tutup
        sistemi tikiyordu.

        Yerel kipteki `VideoProxy.yayin_durdur` ayni sozlesmeyi
        zaten uyguluyor (pop + durdur); merkez kipi de uygular.

        SIRA BILINCLI: yerel temizlik saha komutundan ONCE yapilir.
        Ters sirada saha komutu ag gecikmesi yasarsa kayit o sure
        boyunca olu kalir ve ayni kusur kucuk pencerede tekrarlar.
        """
        try:
            kid = int(kamera_id)
        except (TypeError, ValueError):
            return
        # 1) Yerel kayit ve nesne — kilit altinda cikarilir.
        with self._yayin_kilit:
            y = self._yayinlar.pop(kid, None)
        self._son_acilis_hata.pop(kid, None)
        if y is not None:
            # `durdur()` UDP soketini kapatir, merkez kanalini
            # `_kanal_kapat` ile kapattirir ve `calisiyor`u
            # False yapar. Bekleyen okuyucular uyandirilir.
            try:
                y.durdur()
            except BaseException as e:
                self._hata_yaz("Yerel yayin kapatilamadi: %s" % e)
        # 2) Saha kaynagi — yerel temizlik BASARISIZ olsa da denenir.
        if not self._komut:
            return
        try:
            self._komut("video_akis_durdur", {"id": kid})
        except Exception as e:
            self._hata_yaz("Akis durdurulamadi: %s" % e)

    def yayin_baslat(self, kamera_id, kayit=None, bekle=12.0):
        """Akisi SAHADA acar. Donus: `(acildi, gerekce)`.

        Gerekce bilincli olarak geri dondurulur: "acilamadi" demek
        yetmez, operator NEDEN acilamadigini bilmeli (yanlis URL, kimlik
        dogrulama, ffmpeg yok, kare gelmiyor).
        """
        if not self._komut:
            return False, "Saha makinesi baglantisi kurulmadi."
        veri = {"id": int(kamera_id), "bekle": float(bekle or 12.0)}
        if isinstance(kayit, dict):
            veri["kamera"] = kayit
        try:
            sonuc, hata = self._komut("video_akis_baslat", veri)
        except Exception as e:
            return False, "%s: %s" % (type(e).__name__, e)
        if hata:
            return False, hata
        sonuc = sonuc or {}
        if sonuc.get("acildi"):
            return True, ""
        return False, str(sonuc.get("gerekce") or "kaynak acilamadi")

    def anotasyon_guncelle(self, kamera_id, kutular):
        """AI tespit kutularini sahaya iletir.

        Cizim SAHADA yapilir; kutulari merkeze getirip cizmek, kareyi de
        merkeze getirmeyi gerektirirdi (bkz. modul basligi).
        """
        if not self._komut:
            return
        try:
            self._komut("video_anotasyon",
                        {"id": int(kamera_id), "kutular": kutular or []})
        except (TypeError, ValueError):
            return
        except Exception:
            # Anotasyon KOZMETIKTIR; basarisizligi gunluge bogmaz.
            return

    def durum(self):
        with self.kilit:
            return {"akislar": list(self.akislar.values()),
                    **dict(self.durum_ozet)}

    # ------------------------------------------------------------------
    # Kopru beslemesi
    # ------------------------------------------------------------------
    def _uygula(self, paket):
        akislar = {}
        for a in (paket.get("video_akislar") or []):
            try:
                kid = int(a.get("id"))
            except (TypeError, ValueError):
                continue
            akislar[kid] = {
                "id": kid,
                "calisiyor": bool(a.get("calisiyor")),
                "izleyici": int(a.get("izleyici") or 0),
                "kare_no": int(a.get("kare_no") or 0),
                "protokol": str(a.get("protokol") or ""),
                "hata": str(a.get("hata") or ""),
            }
        with self.kilit:
            self.akislar = akislar
            self.durum_ozet.update({
                "hazir": bool(paket.get("video_hazir")),
                "etkin": int(paket.get("video_etkin") or 0),
                "port": int(paket.get("video_port") or 0),
                "ffmpeg": bool(paket.get("ffmpeg")),
                "opencv": bool(paket.get("opencv")),
                "hata": str(paket.get("video_vekil_hata") or ""),
            })

    def _bozuk(self, hata):
        with self.kilit:
            self.akislar = {}
            self.durum_ozet.update({"hazir": False, "etkin": 0,
                                    "hata": hata})
        self._hata_yaz(hata)


class AiVekili(_KopruVekilTemel):
    """`AIYonetici` yuzunu tasiyan, kopru beslemeli vekil.

    Merkez kipinde AI islemi sahada kosar. `sunucu.py` su uyeleri
    kullanir:
        izleme_baslat · izleme_durdur · izleme_listesi
        sunucu_durumlari · baslat · kapat
    Ayrica `main.py` su nitelikleri atar:
        ucus_gecmisi · video_proxy · kameralar · duyuru_cb
    """

    def __init__(self, konsol, kilit, cek=None, komut=None):
        super().__init__(konsol, kilit, cek, etiket="AI")
        self._komut = komut
        self.sunucular = []
        self.gorevler = []
        self.ozet = {"hazir": False, "sunucu_sayisi": 0,
                     "cevrimici": 0, "hizlandirici": "", "hata": ""}
        # main.py'nin atadigi nitelikler (yuz uyumlulugu)
        self.ucus_gecmisi = None
        self.video_proxy = None
        self.kameralar = None
        self.duyuru_cb = None

    # ------------------------------------------------------------------
    # AIYonetici yuz uyumlulugu
    # ------------------------------------------------------------------
    def baslat(self):
        try:
            self.konsol("AI",
                        "Merkez kipi: AI cikarimi saha koprusunde "
                        "kosar; merkezde yoklama baslatilmadi.", "bilgi")
        except Exception:
            pass
        # FAZ19-IS65-K2-MERKEZ-ACILIS-IZLEME
        # `AIYonetici.baslat` acilista `_gorevleri_geri_yukle`
        # calistirir (v2.4.8): `ai_gorevler` dolu kameralar
        # kendiliginden izlemeye alinir. Merkez kipinde bu sinif
        # devrede oldugu icin o kazanim YOK'tu; operator AI'yi
        # actigini sanip hicbir tespit alamiyordu.
        try:
            threading.Thread(target=self._acilis_izlemesi,
                             daemon=True,
                             name="ai-vekil-acilis").start()
        except BaseException:
            pass

    def _acilis_izlemesi(self):
        """`ai_gorevler` dolu kameralari acilista izlemeye alir.

        Kopru baglantisi merkez acilisindan SONRA kurulur; bu yuzden
        `self._komut` hazir olana kadar araliklarla beklenir. Sinirli
        sayida deneme yapilir: kopru hic baglanmazsa is parcacigi
        sonsuza kadar donmemelidir.
        """
        for _deneme in range(20):          # 20 x 6sn = 2 dk
            time.sleep(6)
            if self._komut:
                break
        else:
            return
        if self.kameralar is None:
            return
        try:
            kameralar = self.kameralar.listele()
        except BaseException as e:
            try:
                self.konsol("AI", "Acilis kamera taramasi: %s: %s"
                            % (type(e).__name__, e), "uyari")
            except BaseException:
                pass
            return
        for kam in kameralar:
            try:
                gorevler = (kam.get("ai_gorevler") or "").strip()
                if not gorevler:
                    continue
                kid = kam.get("id")
                try:
                    self.konsol("AI", "Kamera #%s AI gorevleri secili;"
                                " izleme otomatik baslatiliyor" % kid,
                                "bilgi")
                except BaseException:
                    pass
                # `url`/`protokol` bos: `izleme_baslat` bu ikisini
                # yok sayar, akis adresini kopru kendisi uretir.
                sonuc = self.izleme_baslat(kid, "", "", gorevler)
                if not (sonuc or {}).get("tamam"):
                    try:
                        self.konsol("AI", "Kamera #%s izlemesi"
                                    " baslatilamadi: %s"
                                    % (kid, (sonuc or {}).get("hata")
                                       or "bilinmeyen"), "uyari")
                    except BaseException:
                        pass
            except BaseException:
                continue

    def kapat(self):
        return

    def izleme_baslat(self, kamera_id, url, protokol, gorevler=""):
        """Izleme gorevini SAHADAN atar.

        `url` ve `protokol` MERKEZ tarafindan uretilir (`/kamera/<id>` +
        `gcs_proxy`) ama merkez kipinde ANLAMSIZDIR: o adres merkezin
        kendi vekilini gosterir ve saha iscisi ona erisemez. Bu yuzden
        kopruye yalniz `kamera_id` ve gorevler gonderilir; akis adresini
        kopru kendi yerel vekiline gore uretir.
        """
        try:
            kamera_id = int(kamera_id)
        except (TypeError, ValueError):
            return {"tamam": False, "hata": "Gecersiz kamera kimligi."}
        if not self._komut:
            return {"tamam": False,
                    "hata": "Saha makinesi baglantisi kurulmadi."}
        veri = {"kamera_id": kamera_id, "gorevler": gorevler or ""}
        # Kamera kaydi varsa birlikte gonderilir: kopru kamerayi kendi
        # defterinde bulamazsa akisi acamaz ve gorev bosa duser.
        if self.kameralar is not None:
            try:
                k = self.kameralar.bul(kamera_id)
                if k:
                    veri["kamera"] = {
                        "id": kamera_id,
                        "isim": k.get("isim"),
                        "protokol": k.get("protokol"),
                        "url": k.get("url"),
                        "ai_gorevler": k.get("ai_gorevler") or "",
                    }
            except Exception:
                pass
        try:
            sonuc, hata = self._komut("ai_izleme_baslat", veri)
        except Exception as e:
            return {"tamam": False, "hata": "%s: %s" % (type(e).__name__, e)}
        if hata:
            return {"tamam": False, "hata": hata}
        sonuc = sonuc or {}
        # FAZ19-IS64-SOZLESME: zincirin ortak sozlesmesi `tamam`/`hata`.
        # Onceki surum `atandi`/`gerekce` okuyordu; bu anahtarlari
        # isci de kopru de HIC uretmez, dolayisiyla basarili atamalar
        # bile "gorev atanamadi" olarak gorunuyordu. Eski anahtarlar
        # geriye donuk uyum icin ikincil sirada korunur.
        if sonuc.get("tamam") or sonuc.get("atandi"):
            self.cek_gerekirse(zorla=True)
            return {"tamam": True, "sunucu": sonuc.get("sunucu")}
        return {"tamam": False,
                "hata": str(sonuc.get("hata")
                            or sonuc.get("gerekce") or "gorev atanamadi")}

    def izleme_durdur(self, kamera_id, kalici=True):
        try:
            kamera_id = int(kamera_id)
        except (TypeError, ValueError):
            return {"tamam": False, "hata": "Gecersiz kamera kimligi."}
        if not self._komut:
            return {"tamam": False,
                    "hata": "Saha makinesi baglantisi kurulmadi."}
        try:
            _s, hata = self._komut("ai_izleme_durdur",
                                   {"kamera_id": kamera_id})
        except Exception as e:
            return {"tamam": False, "hata": "%s: %s" % (type(e).__name__, e)}
        if hata:
            return {"tamam": False, "hata": hata}
        self.cek_gerekirse(zorla=True)
        return {"tamam": True}

    def izleme_listesi(self):
        self.cek_gerekirse()
        with self.kilit:
            return list(self.gorevler)

    def sunucu_durumlari(self):
        self.cek_gerekirse()
        with self.kilit:
            return list(self.sunucular)

    def durum(self):
        self.cek_gerekirse()
        with self.kilit:
            return dict(self.ozet)

    # ------------------------------------------------------------------
    # Kopru beslemesi
    # ------------------------------------------------------------------
    def _uygula(self, paket):
        sunucular = []
        for s in (paket.get("ai_sunucular") or []):
            if not isinstance(s, dict):
                continue
            sunucular.append(dict(s))
        gorevler = []
        for g in (paket.get("ai_gorevler") or []):
            if not isinstance(g, dict):
                continue
            gorevler.append(dict(g))
        with self.kilit:
            self.sunucular = sunucular
            self.gorevler = gorevler
            self.ozet.update({
                "hazir": bool(paket.get("ai_hazir")),
                "sunucu_sayisi": int(paket.get("ai_sunucu_sayisi") or 0),
                "cevrimici": int(paket.get("ai_cevrimici") or 0),
                "hizlandirici": str(paket.get("hizlandirici") or ""),
                "hata": "",
            })

    def _bozuk(self, hata):
        with self.kilit:
            self.sunucular = []
            self.gorevler = []
            self.ozet.update({"hazir": False, "cevrimici": 0,
                              "hata": hata})
        self._hata_yaz(hata)
    # ------------------------------------------------------------------
    # FAZ18_IS9_AI_VEKIL_YUZ — EKSIK YUZ TAMAMLAMASI
    # ------------------------------------------------------------------
    # OLCULEN KUSUR: `sunucu.py` `ai_yonetici` uzerinden 17 yontem
    # cagiriyordu; bu vekil yalniz 3'unu tasiyordu. Merkez kipinde
    # AI panelini acmak `'AiVekili' object has no attribute 'listele'`,
    # tespit gecmisini acmak `... has no attribute 'gecmis'` veriyordu.
    #
    # AYRIM (AST ile olculdu):
    #   DB isi (merkezde birebir calisir) : kaydet sahibi_mi _sunucu_kaydi
    #       ucus_tespitleri gecmis tespit_islenmis tespit_kisi_ata
    #       tespit_arac_ata yuz_onbellek_sifirla
    #   DB + saglik onbellegi             : listele sil
    #   SAHA erisimi (kopruye devredilir) : track_baslat track_durdur
    #       embed_hesapla
    #
    # NEDEN GOVDE KOPYALANMIYOR: bu dosyanin kendi belge dizesi uyariyor —
    # "Iki ayri kopya tutmak, birinde duzeltilen kusurun otekinde
    # kalmasina yol acar". Bu yuzden DB yontemleri `AIYonetici`'nin islev
    # nesnesi uzerinden VEKIL ORNEGIYLE cagrilir; tek kaynak korunur.
    @staticmethod
    def _ay():
        """`AIYonetici` sinifini tembel ice alir.

        Modul basinda ice alinmaz: `ai_yonetici` agir bagimliliklar
        (numpy/opencv) tasiyabilir ve bu dosya merkez disinda da
        yuklenir. Tembel ice alim, vekil kullanilmadikca bedel
        odemez.
        """
        from goktungu.ai_yonetici import AIYonetici
        return AIYonetici

    @property
    def saglik(self):
        """`{sunucu_id: {cevrimici, son_durum}}` — KOPRUDEN turetilir.

        `AIYonetici`'de bu sozluk merkezin kendi yoklama dongusuyle
        dolar. Merkez kipinde yoklama SAHADA kosar; durum ozeti
        `_uygula` ile `self.sunucular`a yazilir. Devralinan DB
        yontemleri (`listele`, `sil`) bu sozlugu okudugu icin ayni
        bicimde uretilir — o govdeler DEGISTIRILMEZ.
        """
        d = {}
        with self.kilit:
            kayitlar = list(self.sunucular)
        for s in kayitlar:
            if not isinstance(s, dict):
                continue
            sid = s.get("id")
            if sid is None:
                continue
            try:
                sid = int(sid)
            except (TypeError, ValueError):
                continue
            d[sid] = {
                "cevrimici": bool(s.get("cevrimici")),
                "son_yoklama_ts": s.get("son_yoklama_ts") or 0.0,
                "son_durum": {
                    "yuk": s.get("yuk", 0),
                    "kapasite": s.get("kapasite_canli", s.get("kapasite")),
                    "akislar": s.get("akislar") or [],
                    "yuz_destegi": s.get("yuz_destegi"),
                },
            }
        return d

    @saglik.setter
    def saglik(self, _deger):
        """Yazma YOK SAYILIR (sessizce).

        `AIYonetici`'nin devralinan govdeleri bazi yollarda
        `self.saglik[...] = ...` yazabilir. Merkez kipinde saglik
        kaynagi kopru oldugu icin yazma anlamsizdir; istisna firlatmak
        ise WS komut isleyicisini dusurur. Bu yuzden yok sayilir.
        """
        return

    # --- DB yontemleri: tek kaynak, govde kopyalanmadi ----------------
    # FAZ18/IS6 -- `_firma_suzgeci` iletimi.
    # `AIYonetici.listele` govdesi ILK satirda kosulsuz olarak
    # `self._firma_suzgeci(...)` cagirir.  Merkez kipinde `self` bir
    # AiVekili ornegi oldugu icin bu uye BULUNAMIYOR ve AI Sunucu
    # listesi HER cagride AttributeError ile dusuyordu -- `firma_id`
    # None olsa bile, cunku cagri kosulsuzdur.  Hata WS katmanindaki
    # sarmalayici tarafindan yutuldugu icin gunluge iz BIRAKMIYORDU.
    # `ai_yonetici.py` bilerek DEGISTIRILMEDI: o dosya lokal kurulumda
    # da kosuyor ve orada kusur yok.  Kusur vekil katmanindadir --
    # iletmesi gereken bir uyeyi iletmiyordu.
    # Iletim `_ay()` uzerinden yapilir; boylece suzgec mantigi tek
    # kaynakta (AIYonetici) kalir ve govde KOPYALANMAZ -- bu dosyanin
    # kendi sozlesmesi bunu gerektiriyor.
    @staticmethod
    def _firma_suzgeci(firma_id):
        from goktungu.ai_yonetici import AIYonetici
        return AIYonetici._firma_suzgeci(firma_id)

    def listele(self, firma_id=None):
        return self._ay().listele(self, firma_id=firma_id)

    def kaydet(self, sid, ad, tip, host, port, kapasite, notlar="",
               ssh=None, firma_id=None, kopru_ornek_id=None):
        return self._ay().kaydet(self, sid, ad, tip, host, port, kapasite,
                                 notlar=notlar, ssh=ssh, firma_id=firma_id,
                                 kopru_ornek_id=kopru_ornek_id)

    def sahibi_mi(self, *a, **k):
        return self._ay().sahibi_mi(self, *a, **k)

    def sil(self, *a, **k):
        return self._ay().sil(self, *a, **k)

    def _sunucu_kaydi(self, *a, **k):
        return self._ay()._sunucu_kaydi(self, *a, **k)

    def ucus_tespitleri(self, *a, **k):
        return self._ay().ucus_tespitleri(self, *a, **k)

    def gecmis(self, *a, **k):
        return self._ay().gecmis(self, *a, **k)

    def tespit_islenmis(self, *a, **k):
        return self._ay().tespit_islenmis(self, *a, **k)

    def tespit_kisi_ata(self, *a, **k):
        return self._ay().tespit_kisi_ata(self, *a, **k)

    def tespit_arac_ata(self, *a, **k):
        return self._ay().tespit_arac_ata(self, *a, **k)

    def yuz_onbellek_sifirla(self, *a, **k):
        return self._ay().yuz_onbellek_sifirla(self, *a, **k)

    # --- Saha yontemleri: kopruye devredilir --------------------------
    # Bunlar `AIYonetici`'de `self._http(kayit, ...)` ile SAHA AI
    # bilgisayarina gider (ornegin http://192.168.1.100:8900). Merkez o
    # ozel aga erisemez; devralmak her istegi zaman asimina dusururdu.
    def _sahaya(self, komut, veri, hata_adi):
        if not self._komut:
            return {"tamam": False,
                    "hata": "Saha makinesi baglantisi kurulmadi."}
        try:
            sonuc, hata = self._komut(komut, veri)
        except Exception as e:
            return {"tamam": False,
                    "hata": "%s: %s" % (type(e).__name__, e)}
        if hata:
            # Kopru bu komutu tanimiyorsa SESSIZ KALINMAZ: kullanici
            # neden calismadigini gormeli.
            return {"tamam": False,
                    "hata": "%s: %s" % (hata_adi, hata)}
        return sonuc or {"tamam": True}

    def track_baslat(self, kamera_id, tur="", kutu=None):
        try:
            kamera_id = int(kamera_id)
        except (TypeError, ValueError):
            return {"tamam": False, "hata": "Gecersiz kamera kimligi."}
        return self._sahaya("ai_track_baslat",
                            {"kamera_id": kamera_id, "tur": tur or "",
                             "kutu": kutu or []},
                            "hedef takibi baslatilamadi")

    def track_durdur(self, kamera_id):
        try:
            kamera_id = int(kamera_id)
        except (TypeError, ValueError):
            return {"tamam": False, "hata": "Gecersiz kamera kimligi."}
        sonuc = self._sahaya("ai_track_durdur", {"kamera_id": kamera_id},
                             "hedef takibi durdurulamadi")
        # Durdurma her kosulda arayuze duyurulur: kopru yanit vermese de
        # arayuzde takip gostergesi acik kalmamalidir.
        if self.duyuru_cb:
            try:
                self.duyuru_cb({"tip": "ai_takip", "kamera_id": kamera_id,
                                "aktif": False, "kayip": False})
            except Exception:
                pass
        return sonuc

    def embed_hesapla(self, foto_b64):
        return self._sahaya("ai_embed_hesapla", {"foto_b64": foto_b64},
                            "yuz vektoru hesaplanamadi")


# FAZ18-IS6-AIVEKIL-FIRMA-SUZGEC
