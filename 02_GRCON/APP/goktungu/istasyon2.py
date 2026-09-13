# =================================================================
# GOKTUNGU - YER ISTASYONU 2 (ESP32-S3 kontrol paneli)  v2.4.44
# -----------------------------------------------------------------
# Iki ekranli sahra cantasindaki ESP32-S3 kontrol panelini GCS'e
# baglar: 11 push buton (P1-P11), 2 toggle (T1, T2), 2 analog
# joystick (J1, J2), 7 LED cikisi (P1-P7).
#
# PROTOKOL (README_istasyon2.md'den birebir):
#   Baglanti : USB seri, 115200 baud, satir bazli (\n), UTF-8
#   ESP32->PC: her satir TAM durum iceren JSON
#              {"event":"P3","buttons":{...11...},
#               "toggles":{"T1":0,"T2":"CENTER"},
#               "joysticks":{"J1_X":2048,...},"leds":{...7...}}
#   PC->ESP32: DUZ METIN (JSON DEGIL)
#              LED,P3,ON | LED,P3,OFF | LED,ALL,ON | LED,ALL,OFF | PING
#   PING cevabi: PONG  (duz metin -> JSON parse EDILMEZ)
#
# KRITIK NOKTALAR (protokol belgesindeki tuzaklar):
#   1. Gelen satir once PONG mu diye denetlenir, SONRA JSON parse edilir.
#   2. T2 degeri STRING ("UP"/"DOWN"/"CENTER"), T1 ve butonlar INT.
#   3. Joystick orta noktasi ~2048 ama SABIT VARSAYILMAZ -> kalibrasyon.
#   4. Windows'ta port duzgun kapatilmazsa "ReadFile failed" -> try/finally.
#   5. event alani yalniz TETIKLEYICIyi gosterir; govde HER ZAMAN tum
#      sistemin durumudur -> state komple overwrite edilir, merge yok.
#
# -----------------------------------------------------------------
# KANAL ESLEMESI (kullanici tanimi, 09.08.2026)
#
#   UCUS KANALLARI - yalniz "joystick kontrolu (manuel) ACIK" dronlarda:
#     P1  ARM / DISARM        (degismeli: armed ise disarm)
#     P2  TAKEOFF / LAND      (degismeli: havadaysa land)
#     P3  RETURN HOME (RTL)
#     P4  GUIDED modu
#     P5  ALT_HOLD modu
#     P6  AUTO modu
#
#   T1 (2 poz):
#     1 -> P7 LED YANAR + arayuzde "Patlatmak icin emin misiniz?" onayi
#     0 -> P7 LED SONER, hicbir sey yapilmaz
#     Bu yuzden P7 otomatik ucus gostergesi DEGILDIR; T1'i yansitir.
#
#   HARITA KANALLARI - dron gerekmez, ARAYUZDE yurutulur:
#     J1 (sol)   harita 3B dondurme + egim
#     J2 (sag)   harita kaydirma
#     T2 UP      zoom, DOWN ters zoom, CENTER durur
#     P8   harita kaynagini sirayla degistir
#     P9   kullanici konumuna git
#     P10  tum nesneleri kapsayacak zoom
#     P11  haritadaki noktalar arasinda sirayla gez
#
#   EK DRON JOYSTICKLERI: cantada panel joysticklerinden AYRI 2 adet
#   2 eksenli joystick var; dron joystick modu acikken DRONU ucururlar.
#   Ayni ESP32'den ek eksen alani olarak gelirlerse (J3_*/J4_*/D1_*/D2_*)
#   burada otomatik algilanir ve ManuelKontrol'e aktarilir. Bilgisayara
#   ayri USB HID olarak takilirlarsa tarayici (Gamepad API) veya backend
#   (pygame) yolu kullanilir; ikisi de zaten mevcuttur.
#
# -----------------------------------------------------------------
# MIMARI:
#   Seri portu OKUYAN ayri bir is parcacigi (thread) vardir; asyncio
#   dongusu bloke edilmez. Okunan her tam durum, sunucunun verdigi
#   `duyur` geri cagrisi ile arayuze yayinlanir.
#
#   Modul KOMUT URETMEZ: "su eylem tetiklendi" bilgisini geri cagriya
#   verir. Ucus komutlari sunucu.py'de tek yerde uygulanir (yetki
#   denetimi atlanmis olmaz), harita eylemleri arayuzde yurutulur
#   (harita durumu yalniz tarayicida vardir).
# =================================================================
import json
import threading
import time

# Protokol sabitleri
# v2.4.45: cihaz kunyesi. Kullanici bu cantanin adini GCCDUAL olarak
# bildirdi ve farkli istasyon cihazlari olacagini belirtti; kunye ayri
# tutulur ki sonraki modeller ayni altyapiya eklenebilsin.
CIHAZ_KODU = "GCCDUAL"
CIHAZ_ADI = "Yer Kontrol Istasyonu Dual"

BAUD = 115200
ESIK = 40                  # firmware JOYSTICK_THRESHOLD (bilgi amacli)
OKUMA_ZAMAN_ASIMI = 0.2    # sn - pyserial read timeout
YENIDEN_DENE = 2.0         # sn - port dusunce yeniden deneme araligi
PING_ARALIK = 5.0          # sn - canlilik denetimi
SESSIZLIK_SINIRI = 12.0    # sn - bu surede hic satir gelmezse kopuk say
# Cubuk hareketi saniyede onlarca tam durum satiri uretir (firmware
# esigi 40 birim). Her satiri WS'ye basmak arayuzu bogar. Bu yuzden
# YALNIZ eksen kaynakli guncellemeler bu araliga sinirlanir; buton,
# toggle ve LED degisimleri GECIKMESIZ yayinlanir.
YAYIN_ARALIK = 0.05        # sn (20 Hz)

BUTONLAR = ["P%d" % i for i in range(1, 12)]      # P1..P11
LEDLI = ["P%d" % i for i in range(1, 8)]          # P1..P7 (LED cikisi var)
EKSENLER = ["J1_X", "J1_Y", "J2_X", "J2_Y"]       # panel joystickleri
T2_DEGERLERI = ("UP", "CENTER", "DOWN")

# Cantadaki EK dron joysticklerinin olasi alan adlari. Firmware hangi
# adlandirmayi kullaniyorsa o algilanir; hicbiri yoksa ek eksen yok
# sayilir (panel yalniz 4 eksen basar) ve dron kontrolu tarayici/pygame
# joystick yolundan yapilir.
EK_EKSEN_ADAYLARI = [
    ("J3_X", "J3_Y", "J4_X", "J4_Y"),
    ("D1_X", "D1_Y", "D2_X", "D2_Y"),
    ("DRON1_X", "DRON1_Y", "DRON2_X", "DRON2_Y"),
    ("K1_X", "K1_Y", "K2_X", "K2_Y"),
]

# Ek dron joysticklerinin varsayilan eslemesi (RC "Mode 2" yerlesimi):
#   birinci cubuk  -> irtifa (Y) + yaw (X)
#   ikinci cubuk   -> ileri/geri (Y) + yanal (X)
EK_EKSEN_HEDEF = [
    {"hedef": "yaw", "ters": False},   # 1. cubuk X
    {"hedef": "vz", "ters": True},     # 1. cubuk Y
    {"hedef": "vy", "ters": False},    # 2. cubuk X
    {"hedef": "vx", "ters": True},     # 2. cubuk Y
]

# Buton eylemleri. Bos dize = eylem atanmamis.
# "ucus" eylemleri sunucuda, "harita" eylemleri arayuzde yurutulur.
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

# T1 = patlatma kolu (P7 LED + onay penceresi)
# T2 = harita zoom; UP/DOWN arayuzde surekli uygulanir, CENTER durdurur
VARSAYILAN_TOGGLE = {
    "T1": "patlat_onay",
    "T2_UP": "harita_zoom_in",
    "T2_CENTER": "harita_zoom_dur",
    "T2_DOWN": "harita_zoom_out",
}

# T1 hangi LED'i surer (kullanici tanimi: P7)
PATLAT_LED = "P7"


def _bos_durum():
    return {
        "event": "",
        "buttons": {b: 0 for b in BUTONLAR},
        "toggles": {"T1": 0, "T2": "CENTER"},
        "joysticks": {e: 2048 for e in EKSENLER},
        "leds": {p: 0 for p in LEDLI},
        "ek_eksen": {},          # cantadaki ek dron joystickleri (ham)
    }


class Istasyon2:
    """ESP32-S3 kontrol panelini seri port uzerinden okur/yazar."""

    def __init__(self, konsol, ayarlar=None, manuel_kontrol=None,
                 duyur=None, eylem=None):
        self.konsol = konsol
        self.ayarlar = ayarlar
        self.manuel = manuel_kontrol
        self._duyur = duyur      # callable(mesaj_dict) - arayuze yayin
        self._eylem = eylem      # callable(eylem_adi, ayrinti) - ucus eylemi

        self.kilit = threading.RLock()
        self._port_adi = ""
        self._istenen = False          # kullanici/otomatik baglanti istedi mi
        self._bagli = False
        self._seri = None
        self._is = None                # okuma is parcacigi
        self._durdur = threading.Event()

        self._durum = _bos_durum()
        self._son_satir_ts = 0.0
        self._son_ping = 0.0
        self._pong_ts = 0.0
        self._gecikme_ms = 0.0
        self._sayac = {"rx": 0, "tx": 0, "bozuk": 0, "pong": 0}
        self._hata = ""
        self._uyari_verildi = False    # ayni port hatasini tekrar yazma
        self._led_kuyruk = []          # gonderilecek duz metin komutlar
        self._ek_eksen_adlari = None   # algilanan ek eksen alanlari
        self._son_yayin = 0.0          # eksen yayini hiz siniri

        # ---- Ayarlar --------------------------------------------------
        a = {}
        if ayarlar is not None:
            try:
                a = ayarlar.yukle().get("istasyon2", {}) or {}
            except Exception:
                a = {}
        # Kullanici talebi: varsayilan port /dev/ttyACM0
        self.port_ayar = str(a.get("port") or "/dev/ttyACM0")
        self.otomatik = bool(a.get("otomatik", True))
        # v2.4.45: GCCDUAL cihaz kunyesi. Kullanici birden fazla istasyon
        # cihazi olacagini bildirdi; cihaz turu ayri tutulur ki sonraki
        # modeller ayni altyapiya eklenebilsin.
        self.cihaz = str(a.get("cihaz") or CIHAZ_KODU)
        self.merkez = dict(a.get("merkez") or {})
        self.olu_bolge = int(a.get("olu_bolge", 120))
        self.buton_esleme = dict(VARSAYILAN_BUTON)
        self.buton_esleme.update(
            {k: str(v) for k, v in (a.get("buton_esleme") or {}).items()
             if k in VARSAYILAN_BUTON})
        self.toggle_esleme = dict(VARSAYILAN_TOGGLE)
        self.toggle_esleme.update(
            {k: str(v) for k, v in (a.get("toggle_esleme") or {}).items()
             if k in VARSAYILAN_TOGGLE})
        # Ek dron joystickleri ManuelKontrol'e aktarilsin mi
        self.ek_eksen_aktif = bool(a.get("ek_eksen_aktif", True))
        # Harita kontrol duyarliligi (arayuz kullanir)
        self.harita_hiz = float(a.get("harita_hiz", 1.0))

    # ------------------------------------------------------------------
    # Ayar kalicilastirma
    # ------------------------------------------------------------------
    def _ayar_yaz(self):
        if self.ayarlar is None:
            return
        try:
            self.ayarlar.kaydet({"istasyon2": {
                "port": self.port_ayar,
                "otomatik": self.otomatik,
                "cihaz": self.cihaz,
                "merkez": self.merkez,
                "olu_bolge": self.olu_bolge,
                "buton_esleme": self.buton_esleme,
                "toggle_esleme": self.toggle_esleme,
                "ek_eksen_aktif": self.ek_eksen_aktif,
                "harita_hiz": self.harita_hiz,
            }})
        except Exception:
            pass

    # ------------------------------------------------------------------
    # GCCDUAL etkinlik denetimi (Program Ayarlari)
    # ------------------------------------------------------------------
    def arayuz_acik(self):
        """Program Ayarlari'nda GCCDUAL acik mi.

        Ayar `istasyon2_arayuz` anahtarinda tutulur (radar_arayuz ile ayni
        desen). Anahtar hic yazilmamissa VARSAYILAN KAPALI'dir: kullanici
        farkli istasyon cihazlari kullandigini bildirdi, dolayisiyla
        cantasi olmayan kurulumlarda menude bos bir oge gorunmemelidir.
        """
        if self.ayarlar is None:
            return False
        try:
            a = self.ayarlar.yukle() or {}
        except Exception:
            return False
        return bool(a.get("istasyon2_arayuz", False))

    # ------------------------------------------------------------------
    # Baglanti yonetimi
    # ------------------------------------------------------------------
    def otomatik_baslat(self):
        """main.py acilista cagirir: ayardaki port ile sessizce baglanir.

        Port yoksa program NORMAL acilir; okuma dongusu 2 sn'de bir
        yeniden dener. Bu yuzden burada basarisizlik OLUMCUL DEGILDIR.
        """
        # v2.4.45: GCCDUAL Program Ayarlari'nda KAPALI ise hic denenmez.
        # Kullanici istegi: "Program ayarlarinda 'Yer Kontrol Istasyonu
        # Dual' kapali ise menude gorunmemeli... Acilistada program
        # ayarlarinda varsa baglanmaya calismali."
        if not self.arayuz_acik():
            self.konsol("IST2", "%s (%s) Program Ayarlari'nda kapali; "
                                "baglanti denenmedi."
                        % (CIHAZ_ADI, self.cihaz))
            return False
        if not self.otomatik:
            self.konsol("IST2", "Yer Istasyonu 2 otomatik baglanti kapali "
                                "(Program Ayarlari'ndan acilabilir).")
            return False
        if not self.port_ayar:
            return False
        basari, sebep = self.baglan(self.port_ayar, kaydet=False)
        if not basari:
            self.konsol("IST2", "Yer Istasyonu 2 baslatilamadi (%s): %s"
                        % (self.port_ayar, sebep), "uyari")
        return basari

    def baglan(self, port, kaydet=True):
        """Seri porta baglanmayi baslatir (thread ile, bloke etmez)."""
        port = str(port or "").strip()
        if not port:
            return False, "Port belirtilmedi"
        # v2.4.45: cihaz Program Ayarlari'nda kapaliysa baglanma reddedilir.
        # Kapali bir cihazin ucus komutu uretmesi kabul edilemez.
        if not self.arayuz_acik():
            self._hata = ("%s Program Ayarlari'nda kapali" % CIHAZ_ADI)
            return False, self._hata
        try:
            import serial  # noqa: F401
        except ImportError:
            self._hata = "pyserial kurulu degil -> pip install pyserial"
            self.konsol("IST2", self._hata, "hata")
            return False, self._hata
        self.kes(yayinla=False)
        with self.kilit:
            self._port_adi = port
            self.port_ayar = port
            self._istenen = True
            self._hata = ""
            self._uyari_verildi = False
            self._durdur.clear()
            self._is = threading.Thread(target=self._dongu, daemon=True)
            self._is.start()
        if kaydet:
            self._ayar_yaz()
        self.konsol("IST2", "Yer Istasyonu 2 baglaniyor: %s @ %d"
                    % (port, BAUD))
        return True, ""

    def kes(self, yayinla=True):
        """Baglantiyi kapatir ve is parcacigini durdurur."""
        with self.kilit:
            self._istenen = False
            self._durdur.set()
            s = self._seri
            calisan = self._is
        # Portu kapatmak okuma bloklamasini da cozer
        try:
            if s is not None:
                s.close()
        except Exception:
            pass
        if calisan is not None and calisan.is_alive():
            calisan.join(timeout=1.5)
        with self.kilit:
            self._seri = None
            self._is = None
            if self._bagli:
                self.konsol("IST2", "Yer Istasyonu 2 baglantisi kapatildi.")
            self._bagli = False
        # Panel kopukken cubuklar dronu suruklemesin
        self._eksen_sifirla()
        if yayinla:
            self._yayinla()

    def _eksen_sifirla(self):
        if self.manuel is not None:
            try:
                self.manuel.istasyon2_eksen(0.0, 0.0, 0.0, 0.0, aktif=False)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Okuma dongusu (ayri is parcacigi)
    # ------------------------------------------------------------------
    def _dongu(self):
        import serial
        while not self._durdur.is_set():
            with self.kilit:
                port = self._port_adi
                istenen = self._istenen
            if not istenen:
                return
            s = None
            try:
                s = serial.Serial(port, BAUD, timeout=OKUMA_ZAMAN_ASIMI)
                with self.kilit:
                    self._seri = s
                    self._bagli = True
                    self._hata = ""
                    self._uyari_verildi = False
                    self._son_satir_ts = time.time()
                self.konsol("IST2", "Baglandi: %s" % port, "basari")
                self._yayinla()
                # Firmware durumunu hemen almak icin PING
                self._yaz("PING")
                self._oku_dongu(s)
            except Exception as e:
                with self.kilit:
                    self._hata = str(e)
                    onceki = self._bagli
                    self._bagli = False
                    ilk = not self._uyari_verildi
                    self._uyari_verildi = True
                if self._durdur.is_set() or not self._istenen:
                    # Kullanici kes dedi; kapanma sirasindaki okuma
                    # istisnasi beklenen davranistir.
                    return
                if onceki:
                    self.konsol("IST2", "Baglanti koptu: %s" % e, "hata")
                elif ilk:
                    # Port takili degilse her 2 saniyede bir ayni satiri
                    # yazmak konsolu doldurur; yalniz ILK denemede uyar.
                    self.konsol("IST2", "Port acilamadi (%s): %s "
                                        "- 2 sn'de bir yeniden denenecek"
                                % (port, e), "uyari")
                self._eksen_sifirla()
                self._yayinla()
            finally:
                # Windows'ta port duzgun kapatilmazsa sonraki acilista
                # "ReadFile failed" alinir; bu yuzden her kosulda kapat.
                try:
                    if s is not None:
                        s.close()
                except Exception:
                    pass
                with self.kilit:
                    self._seri = None
            # Yeniden deneme (kullanici kes demedikce)
            for _ in range(int(YENIDEN_DENE / 0.1)):
                if self._durdur.is_set():
                    return
                time.sleep(0.1)

    def _oku_dongu(self, s):
        tampon = b""
        while not self._durdur.is_set():
            self._kuyruk_bosalt(s)
            simdi = time.time()
            if (simdi - self._son_ping) > PING_ARALIK:
                self._son_ping = simdi
                self._yaz("PING")
            if (simdi - self._son_satir_ts) > SESSIZLIK_SINIRI:
                raise IOError("panel yanit vermiyor (%.0f sn sessiz)"
                              % (simdi - self._son_satir_ts))
            try:
                gelen = s.read(256)
            except TypeError:
                # kes() portu kapatti: pyserial kapali portta None
                # dondurup TypeError uretebiliyor. Kullanici istegiyle
                # kapanma HATA DEGILDIR, sessizce cikilir.
                if self._durdur.is_set() or not self._istenen:
                    return
                raise
            if not gelen:
                continue
            tampon += gelen
            while b"\n" in tampon:
                ham, tampon = tampon.split(b"\n", 1)
                satir = ham.decode("utf-8", "replace").strip()
                if satir:
                    self._satir_isle(satir)
            if len(tampon) > 8192:
                tampon = b""
                with self.kilit:
                    self._sayac["bozuk"] += 1

    def _kuyruk_bosalt(self, s):
        with self.kilit:
            kuyruk = self._led_kuyruk
            self._led_kuyruk = []
        for komut in kuyruk:
            try:
                s.write((komut + "\n").encode("utf-8"))
                s.flush()
                with self.kilit:
                    self._sayac["tx"] += 1
            except Exception:
                with self.kilit:
                    self._led_kuyruk = kuyruk
                raise

    # ------------------------------------------------------------------
    # Protokol ayristirma
    # ------------------------------------------------------------------
    def _satir_isle(self, satir):
        """Gelen bir satiri isler.

        SIRA ONEMLI: PING cevabi `PONG` DUZ METINDIR, JSON degildir.
        JSON parse denemesi once yapilirsa her PONG bozuk satir olarak
        sayilir ve gecikme olcumu hic calismaz.
        """
        with self.kilit:
            self._son_satir_ts = time.time()
        if satir == "PONG":
            with self.kilit:
                self._sayac["pong"] += 1
                self._pong_ts = time.time()
                self._gecikme_ms = max(
                    0.0, (self._pong_ts - self._son_ping) * 1000.0)
            return
        if not satir.startswith("{"):
            with self.kilit:
                self._sayac["bozuk"] += 1
            return
        try:
            m = json.loads(satir)
        except Exception:
            with self.kilit:
                self._sayac["bozuk"] += 1
            return
        if not isinstance(m, dict) or "buttons" not in m:
            with self.kilit:
                self._sayac["bozuk"] += 1
            return
        self._durum_uygula(m)

    def _ek_eksen_coz(self, js):
        """Cantadaki ek dron joysticklerinin alan adlarini algilar."""
        if self._ek_eksen_adlari is not None:
            return self._ek_eksen_adlari
        for adaylar in EK_EKSEN_ADAYLARI:
            if all(ad in js for ad in adaylar):
                self._ek_eksen_adlari = list(adaylar)
                self.konsol("IST2", "Ek dron joystickleri algilandi: "
                            + ", ".join(adaylar))
                return self._ek_eksen_adlari
        # Bilinen desen yok: panel yalniz 4 eksen basiyor demektir.
        # Ek joystickler USB HID ise tarayici/pygame yolundan gelir.
        return []

    def _durum_uygula(self, m):
        """Tam durumu uygular ve degisimleri eyleme cevirir.

        Govde HER ZAMAN tum sistemin durumudur (diff/merge yok), bu yuzden
        state komple overwrite edilir. Buton eylemleri icin ONCEKI durumla
        karsilastirma yapilir: yalniz 0->1 gecisi (basma ani) tetikler,
        basili tutmak tekrar tetiklemez.
        """
        js_ham = m.get("joysticks") or {}
        ek_adlar = self._ek_eksen_coz(js_ham)
        with self.kilit:
            eski = self._durum
            yeni = _bos_durum()
            yeni["event"] = str(m.get("event", ""))
            for b in BUTONLAR:
                try:
                    yeni["buttons"][b] = 1 if int(
                        (m.get("buttons") or {}).get(b, 0)) else 0
                except (TypeError, ValueError):
                    yeni["buttons"][b] = 0
            tg = m.get("toggles") or {}
            try:
                yeni["toggles"]["T1"] = 1 if int(tg.get("T1", 0)) else 0
            except (TypeError, ValueError):
                yeni["toggles"]["T1"] = 0
            # T2 STRING'dir - int'e cevirmeye calismak hataya yol acar
            t2 = str(tg.get("T2", "CENTER")).upper()
            yeni["toggles"]["T2"] = t2 if t2 in T2_DEGERLERI else "CENTER"
            for e in EKSENLER:
                try:
                    yeni["joysticks"][e] = max(
                        0, min(4095, int(js_ham.get(e, 2048))))
                except (TypeError, ValueError):
                    yeni["joysticks"][e] = 2048
            for e in ek_adlar:
                try:
                    yeni["ek_eksen"][e] = max(
                        0, min(4095, int(js_ham.get(e, 2048))))
                except (TypeError, ValueError):
                    yeni["ek_eksen"][e] = 2048
            ld = m.get("leds") or {}
            for p in LEDLI:
                try:
                    yeni["leds"][p] = 1 if int(ld.get(p, 0)) else 0
                except (TypeError, ValueError):
                    yeni["leds"][p] = 0
            self._durum = yeni
            self._sayac["rx"] += 1
            buton_esleme = dict(self.buton_esleme)
            toggle_esleme = dict(self.toggle_esleme)
            ek_aktif = self.ek_eksen_aktif

        # Ek dron joysticklerini manuel kontrole aktar
        if ek_adlar and ek_aktif:
            self._ek_eksenleri_aktar(yeni["ek_eksen"], ek_adlar)

        # Buton kenar tespiti (0 -> 1)
        for b in BUTONLAR:
            if yeni["buttons"][b] and not eski["buttons"][b]:
                ad = buton_esleme.get(b, "")
                if ad:
                    self._eylem_tetik(ad, {"kanal": b, "deger": 1})

        # T1 degisimi -> patlatma kolu: P7 LED + onay
        if yeni["toggles"]["T1"] != eski["toggles"]["T1"]:
            acik = bool(yeni["toggles"]["T1"])
            # LED dogrudan burada surulur; arayuz beklenmez (kol fiziksel
            # geri bildirim istiyor, WS gecikmesine bagli olmamali).
            self.led(PATLAT_LED, acik)
            ad = toggle_esleme.get("T1", "")
            if ad:
                self._eylem_tetik(ad, {"kanal": "T1",
                                       "deger": 1 if acik else 0,
                                       "acik": acik})

        # T2 degisimi (string!) -> harita zoom
        if yeni["toggles"]["T2"] != eski["toggles"]["T2"]:
            ad = toggle_esleme.get("T2_" + yeni["toggles"]["T2"], "")
            if ad:
                self._eylem_tetik(ad, {"kanal": "T2",
                                       "deger": yeni["toggles"]["T2"]})
        # Olay varsa gecikmesiz, yalniz cubuk hareketi varsa hiz sinirli
        olay = (yeni["buttons"] != eski["buttons"]
                or yeni["toggles"] != eski["toggles"]
                or yeni["leds"] != eski["leds"])
        simdi = time.monotonic()
        if olay or (simdi - self._son_yayin) >= YAYIN_ARALIK:
            self._son_yayin = simdi
            self._yayinla()

    def _eylem_tetik(self, ad, ayrinti):
        """Eylemi sunucuya bildirir.

        Harita eylemleri de ayni yoldan gecer: sunucu onlari arayuze
        yayinlar. Modul burada harita/ucus ayrimi YAPMAZ, cunku esleme
        kullanici tarafindan degistirilebilir ve tek dogruluk kaynagi
        sunucudaki eylem isleyicisidir.
        """
        if self._eylem is None:
            return
        try:
            self._eylem(ad, ayrinti)
        except Exception as e:
            self.konsol("IST2", "Eylem hatasi (%s): %s" % (ad, e), "hata")

    # ------------------------------------------------------------------
    # Eksen normalizasyonu
    # ------------------------------------------------------------------
    def _merkez(self, eksen):
        try:
            return int(self.merkez.get(eksen, 2048))
        except (TypeError, ValueError):
            return 2048

    def normalize(self, eksen, ham=None):
        """Ham degeri (-1..+1) araligina cevirir.

        Merkez kalibrasyondan gelir; protokol belgesi orta noktanin sabit
        2048 varsayilmamasini sart kosuyor. Olu bolge merkez cevresinde
        uygulanir, disinda ORANSAL olarak yeniden olceklenir (aksi halde
        olu bolge sinirinda hiz sicramasi olur).
        """
        if ham is None:
            with self.kilit:
                ham = (self._durum["joysticks"].get(eksen)
                       or self._durum["ek_eksen"].get(eksen, 2048))
        m = self._merkez(eksen)
        fark = float(ham) - m
        olu = max(0, int(self.olu_bolge))
        if abs(fark) <= olu:
            return 0.0
        if fark > 0:
            aralik = float(max(1, 4095 - m - olu))
            return min(1.0, (fark - olu) / aralik)
        aralik = float(max(1, m - olu))
        return max(-1.0, (fark + olu) / aralik)

    def _ek_eksenleri_aktar(self, ham, adlar):
        """Ek dron joysticklerini ManuelKontrol'e aktarir.

        ManuelKontrol yalnizca manuel anahtari ACIK dronlara komut
        gonderir; anahtar kapaliysa bu deger etkisizdir. Yani "dron
        joystick modu acikken kontrol et" sarti orada saglanir.
        """
        if self.manuel is None:
            return
        v = {"vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw": 0.0}
        for i, ad in enumerate(adlar[:4]):
            kural = EK_EKSEN_HEDEF[i]
            # `normalize` cantanin KENDI merkez kalibrasyonunu ve olu
            # bolgesini uygular (12-bit ADC). Bu katman KORUNUR; pilot
            # tercihi bunun UZERINE biner.
            d = self.normalize(ad, ham.get(ad, 2048))
            if kural["ters"]:
                d = -d
            v[kural["hedef"]] = d
        # v2.4.50: pilot tercihi (ters cevirme + olcek). Canta zaten
        # -1..1 uretti, bu yuzden ikinci kez merkez/olu bolge UYGULANMAZ
        # (cift olu bolge ekseni gereksiz olduruur); yalniz `ters` ve
        # `olcek` uygulanir.
        try:
            t = self.manuel.tercih().get("tercih") or {}
            ters = t.get("ters") or {}
            olcek = t.get("olcek") or {}
            for e in ("vx", "vy", "vz", "yaw"):
                if ters.get(e):
                    v[e] = -v[e]
                try:
                    v[e] = max(-1.0, min(1.0,
                                         v[e] * float(olcek.get(e, 1.0))))
                except (TypeError, ValueError):
                    pass
        except Exception:
            pass
        try:
            self.manuel.istasyon2_eksen(v["vx"], v["vy"], v["vz"],
                                        v["yaw"], aktif=True)
        except Exception:
            pass

    def kalibre_et(self):
        """O anki joystick degerlerini merkez olarak kaydeder."""
        with self.kilit:
            yeni = dict(self._durum["joysticks"])
            yeni.update(self._durum["ek_eksen"])
            self.merkez = yeni
            m = dict(self.merkez)
        self._ayar_yaz()
        self.konsol("IST2", "Joystick merkezi kalibre edildi: "
                    + ", ".join("%s=%d" % (k, v)
                                for k, v in sorted(m.items())))
        self._yayinla()
        return m

    def kalibrasyon_sil(self):
        with self.kilit:
            self.merkez = {}
        self._ayar_yaz()
        self.konsol("IST2", "Joystick kalibrasyonu sifirlandi "
                            "(varsayilan merkez 2048).")
        self._yayinla()

    # ------------------------------------------------------------------
    # LED yazma
    # ------------------------------------------------------------------
    def _yaz(self, komut):
        """Duz metin komutu kuyruga alir (okuma is parcacigi gonderir)."""
        with self.kilit:
            if not self._bagli:
                return False
            if len(self._led_kuyruk) > 64:
                # Kuyruk sismesi: en eskileri dus (LED komutu idempotent)
                self._led_kuyruk = self._led_kuyruk[-32:]
            self._led_kuyruk.append(str(komut))
        return True

    def led(self, kanal, acik):
        """LED,Px,ON|OFF veya LED,ALL,ON|OFF gonderir.

        P8-P11/T1/T2 icin firmware komutu SESSIZCE YOK SAYAR (LED cikisi
        yok). Bu bir hata degildir ve burada da engellenmez; panelin
        gercek davranisini gizlemek teshisi zorlastirir. Yalniz gecersiz
        kanal adlari reddedilir.
        """
        k = str(kanal or "").upper()
        if k != "ALL" and k not in BUTONLAR:
            return False, "Gecersiz kanal: %s" % kanal
        return self._yaz("LED,%s,%s" % (k, "ON" if acik else "OFF")), ""

    def ping(self):
        with self.kilit:
            self._son_ping = time.time()
        return self._yaz("PING")

    # ------------------------------------------------------------------
    # Durum / yayin
    # ------------------------------------------------------------------
    def durum(self):
        with self.kilit:
            ek = dict(self._durum["ek_eksen"])
            d = {
                # v2.4.45: cihaz kunyesi + Program Ayarlari etkinligi
                "cihaz": self.cihaz,
                "cihaz_adi": CIHAZ_ADI,
                "arayuz_acik": self.arayuz_acik(),
                "bagli": self._bagli,
                "istenen": self._istenen,
                "port": self._port_adi or self.port_ayar,
                "port_ayar": self.port_ayar,
                "otomatik": self.otomatik,
                "baud": BAUD,
                "hata": self._hata,
                "sayac": dict(self._sayac),
                "gecikme_ms": round(self._gecikme_ms, 1),
                "esik": ESIK,
                "olu_bolge": self.olu_bolge,
                "merkez": dict(self.merkez),
                "kalibre": bool(self.merkez),
                "buton_esleme": dict(self.buton_esleme),
                "toggle_esleme": dict(self.toggle_esleme),
                "ek_eksen_aktif": self.ek_eksen_aktif,
                "ek_eksen_adlari": list(self._ek_eksen_adlari or []),
                "harita_hiz": self.harita_hiz,
                "ledli": list(LEDLI),
                "patlat_led": PATLAT_LED,
                "ucus_eylemleri": dict(UCUS_EYLEMLERI),
                "harita_eylemleri": dict(HARITA_EYLEMLERI),
                "durum": {
                    "event": self._durum["event"],
                    "buttons": dict(self._durum["buttons"]),
                    "toggles": dict(self._durum["toggles"]),
                    "joysticks": dict(self._durum["joysticks"]),
                    "leds": dict(self._durum["leds"]),
                    "ek_eksen": ek,
                },
            }
        d["normalize"] = {e: round(self.normalize(
            e, d["durum"]["joysticks"][e]), 4) for e in EKSENLER}
        for e, ham in ek.items():
            d["normalize"][e] = round(self.normalize(e, ham), 4)
        return d

    def ayar_yaz(self, k):
        """Arayuzden gelen ayar guncellemesi."""
        yeniden_bagla = None
        with self.kilit:
            if "olu_bolge" in k:
                try:
                    self.olu_bolge = max(0, min(1000, int(k["olu_bolge"])))
                except (TypeError, ValueError):
                    pass
            if "harita_hiz" in k:
                try:
                    self.harita_hiz = max(0.1, min(5.0,
                                                   float(k["harita_hiz"])))
                except (TypeError, ValueError):
                    pass
            if "otomatik" in k:
                self.otomatik = bool(k["otomatik"])
            if "ek_eksen_aktif" in k:
                self.ek_eksen_aktif = bool(k["ek_eksen_aktif"])
                kapat = not self.ek_eksen_aktif
            else:
                kapat = False
            if "port" in k:
                yeni_port = str(k.get("port") or "").strip()
                if yeni_port and yeni_port != self.port_ayar:
                    self.port_ayar = yeni_port
                    if self._istenen:
                        yeniden_bagla = yeni_port
            for kanal, v in (k.get("buton_esleme") or {}).items():
                if kanal in VARSAYILAN_BUTON:
                    self.buton_esleme[kanal] = str(v or "")
            for kanal, v in (k.get("toggle_esleme") or {}).items():
                if kanal in VARSAYILAN_TOGGLE:
                    self.toggle_esleme[kanal] = str(v or "")
        if kapat:
            self._eksen_sifirla()
        self._ayar_yaz()
        if yeniden_bagla:
            # Port degistiyse ve baglanti aktifse yeni porta gec
            self.baglan(yeniden_bagla)
        else:
            self._yayinla()

    def _yayinla(self):
        if self._duyur is None:
            return
        try:
            self._duyur({"tip": "istasyon2_durum", **self.durum()})
        except Exception:
            pass

    @staticmethod
    def portlari_listele():
        """Seri portlari dondurur (ESP32 adaylari basta)."""
        try:
            from serial.tools import list_ports
        except ImportError:
            return [{"port": "", "aciklama":
                     "pyserial kurulu degil -> pip install pyserial"}]
        try:
            liste = []
            for p in list_ports.comports():
                ac = (p.description or "")
                # ESP32-S3 UART kopruleri: CP210x, CH340, FTDI; native USB
                # (JTAG/serial) ise "USB JTAG" olarak gorunur ve YALNIZ
                # firmware yuklemek icindir. Adaylari basa almak, iki
                # portlu karttan dogru olani secmeyi kolaylastirir.
                aday = any(x in ac.upper() for x in
                           ("CP210", "CH34", "FTDI", "USB SERIAL",
                            "USB-SERIAL", "SILICON LABS", "ESP32",
                            "ACM"))
                if "ACM" in (p.device or "").upper():
                    aday = True
                liste.append({"port": p.device, "aciklama": ac,
                              "aday": aday})
            liste.sort(key=lambda x: (not x["aday"], x["port"]))
            return liste
        except Exception:
            return []
