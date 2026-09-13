# -*- coding: utf-8 -*-
"""KOPRU YAZILIMI — YER KONTROL ISTASYONU DUAL (GCCDUAL) SERVISI.

## KULLANICI ISTEGI (birebir)

    "radar ve ground control dual dedigimiz yer kontrol istasyonu, bu
     ikiside sunucu yazilimi icinde olmali, kopru olarak cikmali,
     arayuzde Goktungu menusunun altinda eger online ise gorunmeli"

## GOREVI

Iki ekranli sahra cantasindaki ESP32-S3 kontrol panelini okur: 11 push
buton (P1-P11), 2 toggle (T1, T2), 2 analog joystick (J1, J2), 7 LED
cikisi. Merkeze dugme/eksen olaylarini yollar; merkezden gelen LED
komutlarini cantaya yazar.

## PROTOKOL (GCS istasyon2.py ile BIREBIR AYNI)

    Baglanti : USB seri, 115200 baud, satir bazli (\\n), UTF-8
    ESP32->PC: her satir TAM durum iceren JSON
    PC->ESP32: DUZ METIN — LED,P3,ON | LED,ALL,OFF | PING
    PING cevabi: PONG (duz metin, JSON DEGIL)

Protokol GCS'teki uygulamayla ayni tutuldu; ayrisirsa ayni cantada iki
farkli davranis olusur ve sahada teshis imkansizlasir.

## KRITIK TUZAKLAR (GCS uygulamasindan devralindi)

1. Gelen satir ONCE `PONG` mu diye denetlenir, SONRA JSON cozumlenir.
   Ters sirada her PONG "bozuk satir" olarak raporlanir.
2. `event` alani yalniz TETIKLEYICIyi gosterir; govde HER ZAMAN tum
   sistemin durumudur. Bu yuzden durum KOMPLE degistirilir, birlestirme
   (merge) YAPILMAZ. Birlestirme yapilirsa birakılan bir dugme basili
   kalmis gorunur.
3. Joystick orta noktasi ~2048'dir ama SABIT VARSAYILMAZ; ilk
   orneklerden kalibre edilir. Sabit varsayilirsa canta her acildiginda
   dron kendi etrafinda yavasca doner (kullanicinin daha once bildirdigi
   kusur).
4. Windows'ta port duzgun kapatilmazsa "ReadFile failed" olusur;
   kapatma try/finally icindedir.

## KOMUT KANALI (2026-08-14, KUSUR-GCSDUAL-PORT)

Kullanici bildirimi:

    "GCS icinde kopru kurulu olan makinede porta baglanmali, sanirim su
     an sunucu da ariyor portu, GCS bilgisayarinda aslinda ttyACM0 var"

Onceki durumda merkezdeki "Yer Istasyonu 2" paneli Baglan/Portlari tara
dugmelerini MERKEZ surecinde uyguluyordu. Merkez sunucusunun seri portu
yoktur; sonuc `[Errno 2] could not open port /dev/ttyACM0` ve 2 saniyede
bir yinelenen uyari oluyordu. Canta SAHA makinesine takilidir, yani bu
servisin kostugu makineye.

Artik panel komutlari `servis_kanal` uzerinden BU SURECE iner ve seri
port GERCEKTEN burada acilir. Desteklenen eylemler:

| eylem      | veri                  | islev                            |
|------------|-----------------------|----------------------------------|
| `portlar`  | `{"tumu": bool}`      | seri port envanteri (aday isaretli) |
| `baglan`   | `{"port": "..."}`     | portu ayarlar, hemen baglanir    |
| `kes`      | -                     | baglantiyi keser, otomatigi durdurur |
| `led`      | `{"kanal","acik"}`    | LED yaz (`ALL`, `PING` dahil)    |
| `kalibre`  | `{"sil": bool}`       | eksen merkezlerini ogren/sil     |
| `durum`    | -                     | canli canta durumu               |

KOMUT GECIKMESI: komutlar okuma dongusu icinde, her `readline`
zamanasiminda (1 sn) yoklanir. Ayri bir is parcacigi KULLANILMAZ;
seri portu iki parcacigin paylasmasi Windows'ta "ReadFile failed"
uretir ve kapatma sirasi ongorulemez hale gelir.
"""
import json
import os
import time

from .servis_temel import Servis, calistir

CIHAZ_KODU = "GCCDUAL"
CIHAZ_ADI = "Yer Kontrol Istasyonu Dual"
BAUD = 115200
OKUMA_ZAMAN_ASIMI = 1.0
YENIDEN_DENE_SN = 5.0
DURUM_BILDIRIM_SN = 30.0
KALIBRASYON_ORNEK = 12
EKSEN_OLU_BOLGE = 60          # ham birim; ~%3
ESIK = 40                     # firmware JOYSTICK_THRESHOLD (bilgi)
SESSIZLIK_SINIRI = 12.0       # sn - bu surede satir gelmezse kopuk
PING_ARALIK = 5.0             # sn - canlilik denetimi
# LED yazildiktan sonra cantanin onayi bu sure boyunca beklenir. Bu
# pencerede panel BIZIM yazdigimiz degeri gosterir (yoksa dugme hic
# yanmaz); pencere dolunca cantanin bildirdigi GERCEK durum gecerlidir
# (yoksa cihaz LED'i yakmadiysa panel yanlis bilgi verir).
LED_ONAY_PENCERESI = 3.0      # sn

# ---------------------------------------------------------------------
# v1.4.3: ARAYUZ SOZLESMESI
#
# Bu sabitler GCS `goktungu/istasyon2.py` ile BIREBIR ayni olmak
# zorundadir. Panel (`js/istasyon2.js` -> `i2PanelCiz`) buton
# izgarasini, LED dugmelerini ve eksen gostergelerini bu tablolardan
# cizer. Ayrisirsa panel merkez kipinde SESSIZCE bos/yanlis gorunur:
# hicbir hata dusmez, yalnizca tuslarin uzerinde eylem adi cikmaz.
#
# Ozellikle eksen adlari ALT CIZGILIDIR (`J1_X`, `J1X` DEGIL).
# ---------------------------------------------------------------------
BUTONLAR = ["P%d" % i for i in range(1, 12)]     # P1..P11
LEDLI = ["P%d" % i for i in range(1, 8)]         # P1..P7 LED cikisi var
EKSENLER = ["J1_X", "J1_Y", "J2_X", "J2_Y"]      # panel joystickleri
T2_DEGERLERI = ("UP", "CENTER", "DOWN")
PATLAT_LED = "P7"

# Cantadaki EK dron joysticklerinin olasi alan adlari; firmware
# hangisini kullaniyorsa ilk gelen satirdan saptanir.
EK_EKSEN_ADAYLARI = [
    ("J3_X", "J3_Y", "J4_X", "J4_Y"),
    ("D1_X", "D1_Y", "D2_X", "D2_Y"),
    ("DRON1_X", "DRON1_Y", "DRON2_X", "DRON2_Y"),
]

UCUS_EYLEMLERI = {
    "arm_disarm": "ARM / DISARM",
    "takeoff_land": "TAKEOFF / LAND",
    "rtl": "RETURN HOME",
    "mod_guided": "GUIDED modu",
    "mod_althold": "ALT_HOLD modu",
    "mod_auto": "AUTO modu",
    "gorev_baslat": "Gorevi baslat",
    "gorev_iptal": "Gorevi iptal et",
}
HARITA_EYLEMLERI = {
    "harita_kaynak": "Harita kaynagini degistir",
    "kullanici_konum": "Kullanici konumuna git",
    "hepsini_kapsa": "Tum nesneleri kapsa",
    "nokta_gez": "Noktalar arasinda gez",
    "patlat_onay": "Patlatma onayi",
}
VARSAYILAN_BUTON = {
    "P1": "arm_disarm",
    "P2": "takeoff_land",
    "P3": "rtl",
    "P4": "mod_guided",
    "P5": "mod_althold",
    "P6": "mod_auto",
    "P7": "",                 # LED T1 tarafindan surulur, eylem yok
    "P8": "harita_kaynak",
    "P9": "kullanici_konum",
    "P10": "hepsini_kapsa",
    "P11": "nokta_gez",
}
VARSAYILAN_TOGGLE = {
    "T1": "patlat_onay",
    "T2_UP": "harita_zoom_in",
    "T2_CENTER": "harita_zoom_dur",
    "T2_DOWN": "harita_zoom_out",
}


def _bos_durum():
    """Canta hic satir gondermemisken panelin cizebilecegi durum.

    Bos sozluk dondurulurse panel tuslari `undefined` okur ve izgara
    hic cizilmez; pilot paneli "bozuk" olarak gorur.
    """
    return {
        "event": "",
        "buttons": {b: 0 for b in BUTONLAR},
        "toggles": {"T1": 0, "T2": "CENTER"},
        "joysticks": {e: 2048 for e in EKSENLER},
        "leds": {p: 0 for p in LEDLI},
        "ek_eksen": {},
    }


class GcsdualServisi(Servis):
    ad = "gcsdual"
    baslik = "Yer Kontrol Istasyonu Dual"

    def hazirla(self):
        self.port_adi = (os.environ.get("GOKTUNGU_GCSDUAL_PORT")
                         or self._varsayilan_port())
        self.seri = None
        self.canta_bagli = False
        self.durum_son = {}
        self.olay_sayaci = 0
        self._son_bildirim = 0.0
        self._kalibrasyon = {}      # eksen -> [ornekler]
        self._merkez = {}           # eksen -> orta nokta
        self._son_hata = ""
        # v1.4.3: panel olcum seridinin okudugu sayaclar. Bunlar
        # olmadan pilot "komut gitti mi" sorusunu yanitlayamaz: seride
        # her deger sifir gorunur ve canta bagliyken bile olu sanilir.
        self._sayac = {"rx": 0, "tx": 0, "pong": 0, "bozuk": 0}
        self._gecikme_ms = 0.0
        self._ping_gonderim = 0.0    # son PING'in gonderilme ani
        self._son_satir_ani = 0.0    # sessizlik denetimi icin
        self._son_ping = 0.0
        # LED durumu cantadan GERI GELMEZ; yazdigimiz son deger burada
        # tutulur ki panel dugmenin yandigini gosterebilsin.
        self._led_durum = {p: 0 for p in LEDLI}
        # Yazilan ama canta tarafindan HENUZ onaylanmamis LED'ler:
        # {kanal: (deger, yazma_ani)}. Onay penceresi boyunca panelde
        # bizim degerimiz gorunur (bkz. LED_ONAY_PENCERESI).
        self._led_beklemede = {}
        # Kullanici "Kes"e bastiginda otomatik yeniden baglanma DURUR.
        # Durmazsa 5 saniye sonra kendiliginden geri baglanir ve pilot
        # kesme dugmesinin bozuk oldugunu dusunur.
        self._otomatik = True
        # "Baglan" komutunun ust donguye ulasma yolu. Okuma dongusu
        # bunu gorunce mevcut baglantiyi birakir ve ust dongu yeni
        # portla baglanir.
        self._baglanma_istegi = False
        try:
            from . import servis_kanal as _sk
            self.kanal = _sk.ServisKanali()
        except Exception as e:
            self.kanal = None
            self.yaz("Komut kanali kurulamadi: %s" % e, "uyari")
        self.yaz("Cihaz: %s, port: %s, %d baud"
                 % (CIHAZ_KODU, self.port_adi, BAUD))
        self.yaz("Port degistirmek icin: GOKTUNGU_GCSDUAL_PORT ortam "
                 "degiskeni")
        if self.kanal is not None and self.kanal.etkin():
            self.yaz("Merkez komut kanali etkin (port bu makinede "
                     "acilir)")
        try:
            import serial                                  # noqa: F401
            self.serial_var = True
        except Exception:
            self.serial_var = False
            self.yaz("pyserial kurulu degil; canta okunamaz. Kurmak "
                     "icin: pip install pyserial", "uyari")

    @staticmethod
    def _varsayilan_port():
        # Kullanici GCS tarafinda /dev/ttyACM0 kullaniyor. Windows'ta
        # COM portu numarasi degisken oldugu icin varsayilan verilmez;
        # port otomatik taranir.
        return "/dev/ttyACM0" if os.name == "posix" else ""

    # -----------------------------------------------------------------
    def dongu(self):
        if not self.serial_var:
            # Servis COKMEZ: kullanici pyserial'i kurup paneli
            # yenilediginde calismaya baslamalidir. Cokerse panelde
            # "durdu" gorunur ve neden gorunmez.
            while not self.durdur_istendi():
                self.bekle(30.0)
                self.yaz("pyserial bekleniyor", "uyari")
            return
        while not self.durdur_istendi():
            # Komutlar baglanti YOKKEN de islenmeli: kullanici "Kes"
            # dedikten sonra tekrar "Baglan" diyebilmelidir. Yalniz
            # okuma dongusunde yoklanirsa panel kalici olarak yanitsiz
            # kalir.
            self._komutlari_isle()
            if not self._otomatik:
                self.bekle(0.4)
                continue
            if not self._baglan():
                # Beklerken de komut yoklanir; aksi halde "Baglan"
                # komutu 5 saniyeye kadar gecikir.
                self._bekle_komutlu(YENIDEN_DENE_SN)
                continue
            try:
                self._oku_dongusu()
            finally:
                self.canta_bagli = False
                self._kapat_seri()
            if not self.durdur_istendi() and self._otomatik:
                self.yaz("Canta baglantisi koptu; yeniden denenecek",
                         "uyari")
                self._bekle_komutlu(YENIDEN_DENE_SN)

    def _bekle_komutlu(self, sn):
        """Beklerken komut yoklar. Donus: durdurma istendi mi."""
        bitis = time.time() + max(0.0, float(sn or 0))
        while time.time() < bitis:
            if self.durdur_istendi():
                return True
            self.bekle(0.4)
            self._komutlari_isle()
            # Baglanma istegi geldiyse beklemeyi KES: pilot dugmeye
            # bastiginda saniyeler suren bir gecikme gormemeli.
            if self._baglanma_istegi:
                return False
        return self.durdur_istendi()

    def _port_bul(self):
        """Kullanilacak seri portu bulur.

        Elle verilen port ONCE denenir, ancak VAR OLDUGU dogrulanir.
        Onceki surumde elle verilen port yoksa otomatik taramaya hic
        dusulmuyordu: canta `/dev/ttyACM1` olarak takildiginda (USB
        siralamasi degistiginde yaygin) servis sonsuza kadar ayni hatayi
        basiyor ve canta HIC bulunamiyordu.
        """
        elle = (self.port_adi or "").strip()
        if elle and self._port_mevcut(elle):
            return elle
        adaylar = self._adaylari_tara()
        if elle and adaylar:
            self.yaz("Belirtilen port (%s) yok; bulunan: %s"
                     % (elle, adaylar[0]), "uyari")
        return adaylar[0] if adaylar else elle

    @staticmethod
    def _port_mevcut(ad):
        # POSIX'te aygit dosyasi denetlenir. Windows'ta COM adlari dosya
        # sisteminde gorunmez; orada acma denemesi tek gecerli olcuttur.
        if os.name == "posix":
            return os.path.exists(ad)
        return True

    def _adaylari_tara(self):
        try:
            from serial.tools import list_ports
        except Exception:
            return []
        bulunan = []
        for p in list_ports.comports():
            # ESP32-S3 genellikle CDC-ACM olarak gorunur. USB kimligi
            # olmayan girdiler (cekirdek sanal portlari) atlanir.
            if not getattr(p, "vid", None):
                continue
            ad = (p.device or "")
            if "ACM" in ad.upper() or ad.upper().startswith("COM"):
                bulunan.append(ad)
        return bulunan

    def _baglan(self):
        import serial
        port = self._port_bul()
        if not port:
            self.yaz("Canta bulunamadi (takili cihaz yok)", "uyari")
            return False
        try:
            self.seri = serial.Serial(port, BAUD,
                                      timeout=OKUMA_ZAMAN_ASIMI)
        except Exception as e:
            self.yaz("Port acilamadi (%s): %s" % (port, e), "uyari")
            self._son_hata = str(e)
            # Istek tuketildi: basarisiz denemeden sonra bayrak acik
            # kalirsa ust dongu bekleme adimini surekli atlar ve
            # saniyede onlarca deneme yapar.
            self._baglanma_istegi = False
            self._durum_olcum_yaz()
            return False
        self.canta_bagli = True
        self.port_adi = port
        self._son_hata = ""
        self._baglanma_istegi = False
        # Canlilik zamanlari SIFIRLANIR. Yapilmazsa onceki oturumdan
        # kalan `_son_satir_ani` hemen sessizlik sinirini asar ve yeni
        # baglanti aninda kopuk sayilip sonsuz dongu olusur.
        simdi = time.time()
        self._son_satir_ani = simdi
        self._son_ping = simdi
        self._ping_gonderim = simdi
        self.yaz("Canta baglandi: %s" % port, "basari")
        if not self._yaz_seri("PING"):
            self._ping_gonderim = 0.0
        self._durum_olcum_yaz()
        return True

    def _kapat_seri(self):
        s, self.seri = self.seri, None
        if not s:
            return
        try:
            s.close()          # Windows "ReadFile failed" onlemi
        except Exception:
            pass

    def _yaz_seri(self, metin):
        s = self.seri
        if not s:
            return False
        try:
            s.write((metin + "\n").encode("ascii", "ignore"))
            # Gonderim sayaci: panel olcum seridinde "Gonderilen"
            # degeridir. Artmiyorsa pilot komutun cantaya hic
            # ulasmadigini anlar.
            self._sayac["tx"] += 1
            return True
        except Exception as e:
            self.yaz("Yazma hatasi: %s" % e, "uyari")
            self._son_hata = str(e)
            return False

    # -----------------------------------------------------------------
    def _oku_dongusu(self):
        while not self.durdur_istendi():
            s = self.seri
            if not s:
                return
            try:
                ham = s.readline()
            except Exception as e:
                self.yaz("Okuma hatasi: %s" % e, "hata")
                self._son_hata = str(e)
                return
            if ham:
                self._satir_isle(ham)
            self._canlilik_denetle()
            self._durum_bildir()
            # Komut yoklamasi okuma dongusunun ICINDE yapilir: seri
            # portu ikinci bir is parcacigina paylastirmak Windows'ta
            # "ReadFile failed" uretir.
            self._komutlari_isle()
            if not self._otomatik or self._baglanma_istegi:
                # "Kes" veya baska bir porta "Baglan" geldi: bu
                # baglantiyi birak, ust dongu karar verir.
                return

    def _canlilik_denetle(self):
        """Duzenli PING atar, yanit vermeyen cantayi KOPUK sayar.

        Neden gerekli: seri port acik kalabilirken cihaz cevap vermeyi
        birakabilir (USB kablosu gevsedi, canta kapandi). `readline`
        bu durumda hata vermez, yalnizca bos doner. Denetim olmasa
        panel "BAGLI" gostermeye devam eder ve pilot dronu kontrol
        ettigini sanir — en tehlikeli sessiz basarisizlik budur.
        """
        simdi = time.time()
        if self._son_satir_ani <= 0:
            # Henuz hic satir gelmedi: baglanti anini baslangic say.
            self._son_satir_ani = simdi
            return
        if simdi - self._son_ping >= PING_ARALIK:
            self._son_ping = simdi
            # OLCULDU (K1, v1.4.3): burada eskiden `if not
            # self._ping_gonderim:` kosulu vardi. `_ping_gonderim`
            # yalniz PONG islenirken sifirlandigi icin, PONG bir kez
            # kacirildiginda alan SONSUZA KADAR dolu kalir ve bir daha
            # HIC PING atilmaz. Boylece canlilik yoklamasi sessizce
            # oler: kablo cekildiginde bile yoklama calismaz. PING
            # gonderimi yanit bekleme durumundan BAGIMSIZ olmalidir.
            #
            # `_ping_gonderim` yalnizca gidis-donus suresini olcmek
            # icindir: bekleyen bir olcum varsa (henuz PONG gelmedi)
            # ustune YAZILMAZ, boylece gecikme degeri en eski bekleyen
            # PING'e gore hesaplanir ve yapay olarak kucuk gorunmez.
            if self._yaz_seri("PING"):
                if not self._ping_gonderim:
                    self._ping_gonderim = simdi
            else:
                self._ping_gonderim = 0.0
        if simdi - self._son_satir_ani >= SESSIZLIK_SINIRI:
            if self.canta_bagli:
                self.canta_bagli = False
                self._son_hata = ("Canta %d sn yanit vermedi (kablo veya "
                                  "cihaz)" % int(SESSIZLIK_SINIRI))
                self.yaz(self._son_hata, "uyari")
                self._durum_olcum_yaz()
            # Portu birak: ust dongu yeniden baglanmayi dener. Aksi
            # halde olu bir tanitici uzerinde sonsuza kadar beklenir.
            self._baglanma_istegi = True

    def _satir_isle(self, ham):
        try:
            satir = ham.decode("utf-8", "replace").strip()
        except Exception:
            self._sayac["bozuk"] += 1
            return
        if not satir:
            return
        self._sayac["rx"] += 1
        self._son_satir_ani = time.time()
        # SIRA ONEMLI: PONG duz metindir, JSON cozumlemesi denenmez.
        if satir == "PONG":
            self._sayac["pong"] += 1
            # Gidis-donus suresi: PING'i biz gonderdigimiz icin tek
            # yonlu tahmin degil GERCEK olcumdur.
            if self._ping_gonderim:
                self._gecikme_ms = max(
                    0.0, (time.time() - self._ping_gonderim) * 1000.0)
                self._ping_gonderim = 0.0
            return
        try:
            m = json.loads(satir)
        except Exception:
            # Bozuk satir sayilir: baud hatasi ya da kablo gurultusu
            # bu sayacta gorunur ve pilot yanlis portu sectigini anlar.
            self._sayac["bozuk"] += 1
            return
        if not isinstance(m, dict):
            self._sayac["bozuk"] += 1
            return
        # Govde tum sistemin durumudur -> KOMPLE degistirilir.
        self.durum_son = m
        self.olay_sayaci += 1
        self._eksen_kalibre(m.get("joysticks") or {})
        olay = m.get("event")
        if olay:
            self.yaz("Olay: %s" % olay)

    def _eksen_kalibre(self, eksenler):
        """Orta noktayi ilk orneklerden ogrenir.

        Sabit 2048 varsayilirsa cantanin kendi sapmasi surekli komut
        olarak yorumlanir ve dron durdugu yerde donmeye baslar.
        """
        if not isinstance(eksenler, dict):
            return
        for ad, deger in eksenler.items():
            try:
                v = int(deger)
            except (TypeError, ValueError):
                continue
            if ad in self._merkez:
                continue
            ornekler = self._kalibrasyon.setdefault(ad, [])
            ornekler.append(v)
            if len(ornekler) >= KALIBRASYON_ORNEK:
                ornekler.sort()
                # Ortanca: tek bir sicrama ortalamayi bozmasin
                self._merkez[ad] = ornekler[len(ornekler) // 2]
                self._kalibrasyon.pop(ad, None)
                self.yaz("Eksen kalibre edildi: %s merkez=%d"
                         % (ad, self._merkez[ad]))

    def eksen_degeri(self, ad):
        """Kalibre edilmis, olu bolgesi uygulanmis eksen degeri."""
        eksenler = self.durum_son.get("joysticks") or {}
        try:
            ham = int(eksenler.get(ad))
        except (TypeError, ValueError):
            return 0
        merkez = self._merkez.get(ad, 2048)
        sapma = ham - merkez
        if abs(sapma) < EKSEN_OLU_BOLGE:
            return 0
        return sapma

    def _durum_bildir(self):
        simdi = time.time()
        if simdi - self._son_bildirim < DURUM_BILDIRIM_SN:
            return
        self._son_bildirim = simdi
        self.yaz("Durum: %s, %d olay, %d eksen kalibre"
                 % ("bagli" if self.canta_bagli else "kopuk",
                    self.olay_sayaci, len(self._merkez)))
        self._durum_olcum_yaz()

    def _durum_olcum_yaz(self):
        """Panelin olcum seridine canta durumunu yazar.

        Komut kanalindan AYRIDIR ve ayri bir amaca hizmet eder: panel
        (ve merkezin yetenek bildirimi) hicbir komut gondermeden
        cantanin bagli olup olmadigini gorebilmelidir. Yalniz komut
        yaniti kullanilsaydi, kimse dugmeye basmadigi surece durum
        bilinmezdi.
        """
        with_hata = (self._son_hata or "")[:200]
        self.durum_yaz(canta_bagli=bool(self.canta_bagli),
                       port=self.port_adi or "",
                       olay_sayaci=int(self.olay_sayaci),
                       kalibre_eksen=len(self._merkez),
                       otomatik=bool(self._otomatik),
                       hata=with_hata)

    # -----------------------------------------------------------------
    # KOMUT KANALI
    # -----------------------------------------------------------------
    def _normalize(self, ad, ham):
        """Ham eksen degerini -1..+1 arasina cevirir.

        Panel cubuk gostergesini bu degerden cizer. Merkez kalibre
        edilmemisse 2048 varsayilir; olu bolge icinde tam 0 dondurulur
        ki gosterge titremesin.
        """
        try:
            v = int(ham)
        except (TypeError, ValueError):
            return 0.0
        merkez = self._merkez.get(ad, 2048)
        sapma = v - merkez
        if abs(sapma) < EKSEN_OLU_BOLGE:
            return 0.0
        # Ust ve alt aralik farkli olabilir (merkez tam ortada degilse);
        # her yon kendi aralignia gore olceklenir, yoksa cubuk bir yone
        # daha erken doyar.
        aralik = (4095 - merkez) if sapma > 0 else merkez
        if aralik <= 0:
            return 0.0
        oran = sapma / float(aralik)
        return round(max(-1.0, min(1.0, oran)), 4)

    def _ek_eksen_coz(self, eksenler):
        """Cantadaki EK dron joysticklerini saptar. Donus: `(ad_listesi,
        deger_sozlugu)`.

        Firmware surumleri farkli adlandirma kullanir; hangi takim
        geliyorsa o kullanilir. Hicbiri yoksa panel ek cubuk cizmez.
        """
        if not isinstance(eksenler, dict):
            return [], {}
        for takim in EK_EKSEN_ADAYLARI:
            if all(a in eksenler for a in takim):
                return list(takim), {a: eksenler[a] for a in takim}
        return [], {}

    def _durum_ozeti(self):
        """Merkez panelinin bekledigi alanlarla canli durum.

        Alan adlari GCS `istasyon2.durum()` ile BIREBIR ayni tutulmustur.
        Ayrisirsa arayuzun iki farkli bicimle ugrasmasi gerekir ve biri
        SESSIZCE bos gorunur — panel acilir, hata dusmez, ama tuslarin
        uzerinde eylem adi cikmaz ve olcum seridi sifir gosterir.
        Olculdu: eksik alanlar `buttons/toggles/joysticks` sarmalayicisi
        (`durum`), `sayac`, `gecikme_ms`, `normalize` ve esleme
        tablolariydi.
        """
        ham = self.durum_son if isinstance(self.durum_son, dict) else {}
        bos = _bos_durum()
        eksenler = dict(bos["joysticks"])
        eksenler.update(ham.get("joysticks") or {})
        butonlar = dict(bos["buttons"])
        butonlar.update(ham.get("buttons") or {})
        kollar = dict(bos["toggles"])
        kollar.update(ham.get("toggles") or {})
        # LED DURUMU — SIRA KRITIK (K2, v1.4.3'te olculdu).
        #
        # Gercek firmware `leds` tablosunu HER pakette gonderir. Eskiden
        # canta tablosu en sona yaziliyordu; bu yuzden LED komutu
        # cantaya ulassa bile bir sonraki pakette ESKI deger geri geliyor
        # ve panelde dugme hic yanmiyordu. Firmware'in LED'i uygulayip
        # yeni durumu bildirmesi bir tur surer (bizim yazmamiz ile onun
        # sonraki paketi arasinda yaris var).
        #
        # Cozum: yazdigimiz deger, cantanin ONAYI gelene kadar (kisa bir
        # pencere boyunca) ustun tutulur. Pencere kapandiktan sonra
        # cantanin bildirdigi GERCEK durum gecerlidir — boylece cihaz
        # LED'i gercekten yakmadiysa panel yanlis bilgi gostermez.
        ledler = dict(bos["leds"])
        canta_led = ham.get("leds") or {}
        ledler.update(canta_led)
        simdi = time.time()
        for p, (deger, ani) in list(self._led_beklemede.items()):
            if simdi - ani > LED_ONAY_PENCERESI:
                # Onay penceresi doldu: artik cantanin dedigi gecerli.
                self._led_beklemede.pop(p, None)
                continue
            if p in canta_led and int(canta_led.get(p, 0)) == deger:
                # Canta onayladi: izlemeye gerek kalmadi.
                self._led_beklemede.pop(p, None)
                continue
            ledler[p] = deger
        # Canta `leds` alanini HIC gondermiyorsa (eski firmware) son
        # yazilan deger tek bilgi kaynagidir.
        if not canta_led:
            ledler.update(self._led_durum)
        ek_adlar, ek_deger = self._ek_eksen_coz(eksenler)

        normalize = {e: self._normalize(e, eksenler.get(e))
                     for e in EKSENLER}
        for a, v in ek_deger.items():
            normalize[a] = self._normalize(a, v)

        return {
            # -- kunye
            "cihaz": CIHAZ_KODU,
            "cihaz_adi": CIHAZ_ADI,
            "arayuz_acik": True,
            # -- baglanti
            "bagli": bool(self.canta_bagli),
            "istenen": bool(self._otomatik),
            "port": self.port_adi or "",
            "port_ayar": self.port_adi or "",
            "otomatik": bool(self._otomatik),
            "baud": BAUD,
            "hata": self._son_hata or "",
            # -- olcumler
            "sayac": dict(self._sayac),
            "gecikme_ms": round(float(self._gecikme_ms), 1),
            "esik": ESIK,
            "olu_bolge": EKSEN_OLU_BOLGE,
            "merkez": dict(self._merkez),
            "kalibre": bool(self._merkez),
            "olay_sayaci": int(self.olay_sayaci),
            "kalibrasyon": dict(self._merkez),
            # -- esleme tablolari (panel izgarasini bunlardan cizer)
            "buton_esleme": dict(VARSAYILAN_BUTON),
            "toggle_esleme": dict(VARSAYILAN_TOGGLE),
            "ledli": list(LEDLI),
            "patlat_led": PATLAT_LED,
            "ucus_eylemleri": dict(UCUS_EYLEMLERI),
            "harita_eylemleri": dict(HARITA_EYLEMLERI),
            "ek_eksen_aktif": bool(ek_adlar),
            "ek_eksen_adlari": ek_adlar,
            "harita_hiz": 1.0,
            # -- canli durum
            "durum": {
                "event": ham.get("event") or "",
                "buttons": butonlar,
                "toggles": kollar,
                "joysticks": eksenler,
                "leds": ledler,
                "ek_eksen": ek_deger,
            },
            "normalize": normalize,
            "event": ham.get("event") or "",
            "buttons": butonlar,
            "toggles": kollar,
            "joysticks": eksenler,
            "kopru": True,
        }

    def _komutlari_isle(self):
        k = self.kanal
        if k is None or not k.etkin():
            return
        # `_baglanma_istegi` ust donguye "bu baglantiyi birak, yenisini
        # kur" demenin tek yoludur; her yoklamada sifirlanir.
        for komut in k.oku():
            kid = komut.get("id")
            eylem = str(komut.get("eylem") or "")
            veri = komut.get("veri") or {}
            try:
                tamam, hata, cikti = self._komut_uygula(eylem, veri)
            except Exception as e:
                tamam, hata, cikti = False, "%s: %s" % (
                    type(e).__name__, e), {}
            k.yanit(kid, tamam, hata, cikti)

    def _komut_uygula(self, eylem, veri):
        """Tek komutu uygular. Donus: `(tamam, hata, veri)`."""
        if eylem == "durum":
            return True, "", self._durum_ozeti()

        if eylem == "portlar":
            return True, "", {"portlar": self._port_envanteri(
                bool(veri.get("tumu")))}

        if eylem == "baglan":
            istenen = str(veri.get("port") or "").strip()
            # SIRA ONEMLI: karsilastirma ATAMADAN once yapilir. Ters
            # sirada `self.port_adi` zaten istenen degere esitlenmis
            # olur, "port degisti mi" sorusu HER ZAMAN hayir yanitini
            # verir ve pilot baska bir porta gecemez.
            onceki = (self.port_adi or "").strip()
            port_degisti = bool(istenen) and istenen != onceki
            if istenen:
                self.port_adi = istenen
            self._otomatik = True
            self._son_hata = ""
            if not self.canta_bagli or port_degisti:
                self._baglanma_istegi = True
            # Zaten istenen porta bagliysa yeniden baglanilmaz:
            # gereksiz kesinti telemetriyi bir sure kor birakir.
            return True, "", self._durum_ozeti()

        if eylem == "kes":
            self._otomatik = False
            self._baglanma_istegi = False
            if self.seri:
                self._yaz_seri("LED,ALL,OFF")
            self._kapat_seri()
            self.canta_bagli = False
            self.yaz("Merkez istegiyle baglanti kesildi")
            self._durum_olcum_yaz()
            return True, "", self._durum_ozeti()

        if eylem == "led":
            kanal = str(veri.get("kanal") or "").upper()
            if not self.canta_bagli:
                return False, "Canta bagli degil.", self._durum_ozeti()
            if kanal == "PING":
                # Gonderim ani KAYDEDILIR; PONG geldiginde gidis-donus
                # suresi buradan olculur. Kaydedilmezse panel gecikmeyi
                # her zaman 0 ms gosterir.
                self._ping_gonderim = time.time()
                ok = self._yaz_seri("PING")
                if not ok:
                    self._ping_gonderim = 0.0
                return ok, ("" if ok else "PING yazilamadi"), {}
            if not kanal:
                return False, "LED kanali verilmedi.", {}
            acik = bool(veri.get("acik"))
            durum = "ON" if acik else "OFF"
            ok = self._yaz_seri("LED,%s,%s" % (kanal, durum))
            if ok:
                # Yazilan deger izlenir: canta onayi gelene kadar panel
                # dugmeyi yanmis gosterir, sonra gercek durum gecerlidir.
                yeni = 1 if acik else 0
                simdi = time.time()
                if kanal == "ALL":
                    for p in LEDLI:
                        self._led_durum[p] = yeni
                        self._led_beklemede[p] = (yeni, simdi)
                elif kanal in self._led_durum:
                    self._led_durum[kanal] = yeni
                    self._led_beklemede[kanal] = (yeni, simdi)
                # LEDLI DISI kanallar (P8-P11/T1/T2) firmware'de sessizce
                # yok sayilir. Durum tablosuna yazilmaz: panel var
                # olmayan bir LED'i yanmis gostermemeli.
            return ok, ("" if ok else "LED komutu yazilamadi"), {
                "kanal": kanal, "acik": acik}

        if eylem == "kalibre":
            if veri.get("sil"):
                self._merkez.clear()
                self._kalibrasyon.clear()
                self.yaz("Kalibrasyon silindi")
                return True, "", self._durum_ozeti()
            if not self.canta_bagli:
                return False, "Canta bagli degil.", self._durum_ozeti()
            # Yeniden ogrenme: mevcut merkezler silinir, sonraki
            # orneklerden yeniden olculur. Anlik olcum YAPILMAZ; tek
            # ornekten merkez cikarmak cantanin o andaki sapmasini
            # kalici hale getirir.
            self._merkez.clear()
            self._kalibrasyon.clear()
            self.yaz("Kalibrasyon yenileniyor (%d ornek toplanacak)"
                     % KALIBRASYON_ORNEK)
            return True, "", self._durum_ozeti()

        return False, "Desteklenmeyen eylem: %s" % eylem, {}

    def _port_envanteri(self, tumu=False):
        """Seri port listesi; ESP32 UART kopru adaylari basa alinir.

        `aday` bayragi ZORUNLUDUR: kart iki port olarak gorunur ve
        yanlis olani secmek sessiz basarisizliga yol acar. GCS
        tarafindaki `Istasyon2.portlari_listele()` ile ayni sozlesme.
        """
        try:
            from serial.tools import list_ports
        except Exception:
            return []
        aday_imza = ("cp210", "ch340", "ch34", "ftdi", "ft232",
                     "esp32", "usb serial", "usb-serial", "cdc")
        liste = []
        for p in list_ports.comports():
            ad = p.device or ""
            if not ad:
                continue
            aciklama = "%s %s" % (p.description or "",
                                  getattr(p, "manufacturer", "") or "")
            usb_var = bool(getattr(p, "vid", None))
            if not (tumu or usb_var):
                # USB kimligi olmayan girdiler cekirdek sanal
                # portlaridir (ttyS0-ttyS63 gibi); listeyi doldurup
                # gercek adayi gozden kaybettirir.
                continue
            metin = aciklama.lower()
            aday = (any(im in metin for im in aday_imza)
                    or "ACM" in ad.upper())
            liste.append({"port": ad, "aciklama": (
                p.description or "").strip(), "aday": bool(aday),
                "usb": usb_var})
        # Adaylar basa: pilot listenin ilk satirini secme egilimindedir.
        liste.sort(key=lambda x: (not x["aday"], x["port"]))
        return liste

    def kapat(self):
        # LED'ler sondurulur: canta uzerinde yanik LED birakmak,
        # servis kapaliyken sistem calisiyor izlenimi verir.
        if self.seri:
            self._yaz_seri("LED,ALL,OFF")
        self._kapat_seri()
        self.yaz("Canta baglantisi kapatildi")


if __name__ == "__main__":
    calistir(GcsdualServisi)
