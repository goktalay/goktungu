# =================================================================
# GOKTUNGU - MANUEL KONTROL (WASD klavye + fiziksel joystick)
# -----------------------------------------------------------------
# - Her dron icin "manuel" anahtari frontend'den acilir/kapatilir.
# - Anahtar ACIK olan TUM dronlara ayni hiz komutu es zamanli gider.
# - Klavye: frontend WS uzerinden eksen vektoru yollar
#     {tip:"manuel_eksen", vx, vy, vz, yaw}  (-1..1 normalize)
# - Joystick: backend bilgisayarina bagli joystick pygame ile okunur
#   ve ayni sekilde eksen vektorune donusturulur (klavye ile toplanir).
# - v2.4.44 Yer Istasyonu 2: ESP32-S3 kontrol panelinin iki analog
#   cubugu UCUNCU eksen kaynagi olarak eklenir (istasyon2_eksen).
#   Klavye + pygame + istasyon2 TOPLANIR ve (-1..1) araligina kirpilir.
# - 10 Hz'de SET_POSITION_TARGET_LOCAL_NED (BODY_OFFSET_NED frame,
#   yalniz velocity bitleri) gonderilir. Girdi yoksa 0 hiz gonderilir
#   (fren) ve ~1 sn sonra komut akisi kesilir (failsafe: dron loiter).
# =================================================================
import math
import threading
import time
from pymavlink import mavutil

from . import joystick_ayar

# Hiz limitleri (m/s) - eksen degeri (-1..1) ile carpilir
YATAY_HIZ = 5.0     # WASD ileri/geri/sag/sol
DIKEY_HIZ = 2.5     # yukari/asagi
YAW_HIZ = 1.2       # rad/s (joystick yaw ekseni icin)
DONGU_HZ = 10.0     # komut gonderme frekansi
GIRDI_ZAMAN_ASIMI = 0.8   # sn - girdi gelmezse 0 hiz, sonra sessizlik
FREN_SURESI = 1.0   # sn - girdi bittikten sonra 0-hiz gonderme suresi

# Velocity-only type_mask (pozisyon/ivme/yaw yok, yaw_rate var)
_VEL_YAWRATE_MASK = 0b0000010111000111
_VEL_MASK = 0b0000111111000111


class ManuelKontrol:
    def __init__(self, dron_yonetici, konsol, dji_kopru=None):
        self.dron = dron_yonetici
        self.konsol = konsol
        self.dji_kopru = dji_kopru  # v2.1.8: DJI virtual stick koprusu
        self.kilit = threading.Lock()
        self.aktif = {}            # sysid -> True (manuel anahtar acik)
        self._eksen = {"vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw": 0.0}
        self._son_girdi = 0.0      # son klavye girdisi zamani
        self._joy_eksen = {"vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw": 0.0}
        # v2.4.50: ISLENMEMIS pygame eksenleri (kalibrasyon icin okunur)
        self._joy_ham = {"vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw": 0.0}
        # v2.4.50: tarayici joystick'inin islenmemis son eksenleri
        self._tarayici_ham = {}
        self._joy_var = False
        self._joy_adi = ""
        # v2.4.44: Yer Istasyonu 2 (ESP32-S3) eksen katkisi
        self._ist2_eksen = {"vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw": 0.0}
        self._ist2_aktif = False
        self._ist2_son = 0.0
        self._durdur = threading.Event()
        self._fren_sonu = 0.0
        # v2.4.50: etkin pilot joystick tercihi (ters cevirme, olu bolge,
        # merkez kalibrasyonu). `None` ise varsayilan kullanilir.
        # Tercih PILOT BAZLIDIR; sunucu oturum acan pilota gore yukler.
        self._tercih = joystick_ayar.varsayilan_tercih()
        self._tercih_eposta = ""
        threading.Thread(target=self._dongu, daemon=True).start()
        threading.Thread(target=self._joystick_dongu, daemon=True).start()

    # ------------------------------------------------------------------
    # v2.4.50: pilot joystick tercihi
    # ------------------------------------------------------------------
    def tercih_ayarla(self, tercih, eposta=""):
        """Etkin pilotun joystick tercihini yukler.

        Tercih ANINDA gecerli olur; pilot ayar penceresini kapatmadan
        cubugu oynatip sonucu gorebilir. Bu, ters eksen ayarinin dogru
        yonde oldugunu sinamanin tek pratik yoludur.
        """
        t = joystick_ayar.tercih_duzelt(tercih)
        with self.kilit:
            self._tercih = t
            self._tercih_eposta = str(eposta or "")
            # Tercih degisince bayat eksen degerleri sifirlanir; aksi
            # halde eski (ters) isaretli deger bir dongu daha uygulanir.
            self._joy_eksen = {"vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw": 0.0}
            self._eksen = {"vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw": 0.0}
        return t

    def tercih(self):
        with self.kilit:
            return {"eposta": self._tercih_eposta,
                    "tercih": dict(self._tercih)}

    def ham_joystick(self):
        """pygame joystick'inin ISLENMEMIS eksen degerleri.

        Arayuzdeki kalibrasyon adimi bunu okur: pilot cubugu birakir,
        okunan ham deger merkez olarak kaydedilir. Islenmis degeri
        okumak ise yaramaz, cunku olu bolge kaymayi zaten maskeler ve
        merkez hep 0 gorunur.
        """
        with self.kilit:
            return dict(self._joy_ham)

    # ------------------------------------------------------------------
    # WS API
    # ------------------------------------------------------------------
    def anahtar(self, sysid, acik):
        """Bir dronun manuel kontrol anahtarini ac/kapat."""
        sysid = int(sysid)
        with self.kilit:
            if acik:
                self.aktif[sysid] = True
            else:
                self.aktif.pop(sysid, None)
        self.konsol("MANUEL",
                    f"D{sysid} manuel kontrol "
                    + ("ACIK" if acik else "KAPALI"))
        if not acik and self.dji_kopru and self.dji_kopru.dji_mi(sysid):
            self.dji_kopru.gonder(sysid, "stick_kapat")
        if acik:
            # DJI: virtual stick modunu ac/kapat
            if self.dji_kopru and self.dji_kopru.dji_mi(sysid):
                self.dji_kopru.gonder(sysid, "stick_ac")
                return
            # GUIDED moda al (hiz komutlari GUIDED gerektirir)
            master = self.dron.master_bul(sysid)
            if master is not None:
                master.mav.set_mode_send(
                    sysid,
                    mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                    4)  # GUIDED

    def eksen_guncelle(self, vx, vy, vz, yaw=0.0, ham=None):
        """Frontend'den gelen normalize eksen vektoru (-1..1).

        v2.4.50: `ham` verilirse (tarayici joystick'inin ISLENMEMIS
        eksenleri) pilot tercihi burada uygulanir. Klavye eksenleri
        (`vx..yaw`) tercihten ETKILENMEZ: W tusu her zaman ileri
        gitmelidir. Ters cevirme yalniz FIZIKSEL cubuk icin anlamlidir;
        klavyeye uygulanmasi "W geri gidiyor" gibi sasirtici bir
        davranis uretir.
        """
        def _k(x):
            try:
                return max(-1.0, min(1.0, float(x)))
            except (TypeError, ValueError):
                return 0.0
        klavye = {"vx": _k(vx), "vy": _k(vy),
                  "vz": _k(vz), "yaw": _k(yaw)}
        if isinstance(ham, dict) and ham:
            with self.kilit:
                t = dict(self._tercih)
            g = joystick_ayar.isle(ham, t, kaynak="gamepad")
            for e in joystick_ayar.EKSENLER:
                klavye[e] = max(-1.0, min(1.0, klavye[e] + g[e]))
        with self.kilit:
            self._eksen = klavye
            self._tarayici_ham = (dict(ham) if isinstance(ham, dict)
                                  else {})
            self._son_girdi = time.time()

    def tarayici_ham(self):
        """Tarayici joystick'inin ISLENMEMIS son eksenleri.

        Kalibrasyon arayuzu bunu okur. Tarayici joystick'i sunucuya
        yalniz ISLENMIS deger gonderirse merkez kalibrasyonu yapilamaz,
        cunku kayma zaten maskelenmis olur.
        """
        with self.kilit:
            return dict(getattr(self, "_tarayici_ham", {}) or {})

    def istasyon2_eksen(self, vx, vy, vz, yaw=0.0, aktif=True):
        """v2.4.44: Yer Istasyonu 2 joystick eksenleri (-1..1).

        Panel yalniz DEGISIM aninda mesaj yayinlar (firmware 40 birim
        esik uygular), yani cubuk sabit tutuldugunda yeni mesaj GELMEZ.
        Bu yuzden klavyedeki gibi kisa bir zaman asimi uygulanamaz:
        `_ist2_aktif` bayragi baglanti kesilene ya da eksen aktarimi
        kapatilana kadar acik kalir, kaynak kapandiginda `aktif=False`
        ile sifirlanir (failsafe bu iki yolla saglanir).
        """
        def _k(x):
            try:
                return max(-1.0, min(1.0, float(x)))
            except (TypeError, ValueError):
                return 0.0
        with self.kilit:
            if not aktif:
                self._ist2_eksen = {"vx": 0.0, "vy": 0.0,
                                    "vz": 0.0, "yaw": 0.0}
                self._ist2_aktif = False
                return
            self._ist2_eksen = {"vx": _k(vx), "vy": _k(vy),
                                "vz": _k(vz), "yaw": _k(yaw)}
            self._ist2_aktif = True
            self._ist2_son = time.time()

    def durum(self):
        with self.kilit:
            return {
                "aktif": sorted(self.aktif.keys()),
                "joystick": self._joy_var,
                "joystick_adi": self._joy_adi,
                "istasyon2": self._ist2_aktif,
                "istasyon2_eksen": dict(self._ist2_eksen),
            }

    # ------------------------------------------------------------------
    # Komut dongusu (10 Hz)
    # ------------------------------------------------------------------
    def _dongu(self):
        aralik = 1.0 / DONGU_HZ
        while not self._durdur.is_set():
            time.sleep(aralik)
            with self.kilit:
                hedefler = list(self.aktif.keys())
                e = dict(self._eksen)
                je = dict(self._joy_eksen)
                son = self._son_girdi
                # v2.4.44: Yer Istasyonu 2 katkisi (aktif degilse sifir)
                ie = (dict(self._ist2_eksen) if self._ist2_aktif
                      else {"vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw": 0.0})
            if not hedefler:
                continue
            simdi = time.time()
            # Klavye girdisi bayatladiysa sifirla
            if (simdi - son) > GIRDI_ZAMAN_ASIMI:
                e = {"vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw": 0.0}
            # Klavye + pygame joystick + Yer Istasyonu 2 topla (kirp)
            vx = max(-1.0, min(1.0, e["vx"] + je["vx"] + ie["vx"]))
            vy = max(-1.0, min(1.0, e["vy"] + je["vy"] + ie["vy"]))
            vz = max(-1.0, min(1.0, e["vz"] + je["vz"] + ie["vz"]))
            yw = max(-1.0, min(1.0, e["yaw"] + je["yaw"] + ie["yaw"]))
            # v2.4.50: Eskiden `abs(x) > 0.02` sabit esigi kullaniliyordu.
            # Kayan bir cubuk bu esigi astigi icin "hareket var" sayilir,
            # fren HIC devreye girmez ve dron sonsuza kadar donerdi
            # (kullanicinin bildirdigi yaw kaymasi belirtisi). Olu bolge
            # ISLENDIKTEN sonra notr deger TAM 0.0 oldugu icin artik
            # sabit esige gerek yok.
            hareket_var = not joystick_ayar.notr_mu(
                {"vx": vx, "vy": vy, "vz": vz, "yaw": yw})
            if hareket_var:
                self._fren_sonu = simdi + FREN_SURESI
            elif simdi > self._fren_sonu:
                # Fren suresi bitti: komut gondermeyi kes
                # (ArduPilot son hizda kalmaz, hedefsiz kalinca durur;
                #  akisi kesmek RC/otonom komutlara alan acar)
                continue
            for sysid in hedefler:
                self._hiz_gonder(sysid, vx, vy, vz, yw)

    def _hiz_gonder(self, sysid, vx, vy, vz, yw):
        # DJI dronlari: hiz vektoru kopru uzerinden virtual stick'e gider
        if self.dji_kopru and self.dji_kopru.dji_mi(sysid):
            try:
                self.dji_kopru.hiz_gonder(
                    int(sysid),
                    vx * YATAY_HIZ, vy * YATAY_HIZ,
                    vz * DIKEY_HIZ, yw * math.degrees(YAW_HIZ))
            except Exception:
                pass
            return
        master = self.dron.master_bul(sysid)
        if master is None:
            return
        try:
            # LOCAL_NED frame + dron heading'ine gore KENDI donusumumuz.
            # (BODY_OFFSET_NED velocity bazi ArduPilot surumlerinde
            # tutarsiz/ters islendiginden kullanilmaz.)
            # vx = ileri (burun yonu), vy = sag, vz = yukari (+)
            hdg = 0.0
            kayit = self.dron.dronlar.get(int(sysid))
            if kayit:
                hdg = math.radians(float(kayit.get("heading", 0.0)))
            ileri = vx * YATAY_HIZ
            sag = vy * YATAY_HIZ
            # NED: x=Kuzey, y=Dogu, z=Asagi(+)
            vn = ileri * math.cos(hdg) - sag * math.sin(hdg)
            ve = ileri * math.sin(hdg) + sag * math.cos(hdg)
            vd = -vz * DIKEY_HIZ   # yukari tusu (+vz) -> NED asagi negatif
            master.mav.set_position_target_local_ned_send(
                0, int(sysid), 1,
                mavutil.mavlink.MAV_FRAME_LOCAL_NED,
                _VEL_YAWRATE_MASK,
                0, 0, 0,
                vn, ve, vd,
                0, 0, 0,
                0, yw * YAW_HIZ)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Fiziksel joystick (pygame, backend bilgisayari)
    # ------------------------------------------------------------------
    def _joystick_dongu(self):
        # v2.4.57: MERKEZ KIPINDE fiziksel joystick hic aranmaz. Joystick
        # PILOTUN bilgisayarina takilir; merkez sunucusunun USB portu
        # yoktur ve zaten tarayici uzerinden gelen joystick yolu
        # (Gamepad API) merkezde de calismaya devam eder. Eski davranis
        # merkezde yalnizca her acilista "pygame kurulu degil, pip install
        # pygame" ogudu yaziyordu; ogut merkez operatoru icin yanlis.
        try:
            from . import merkez_kimlik as _mk_joy
            if _mk_joy.merkez_kipinde():
                return
        except Exception:
            pass
        try:
            import os
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            # Pencere odakta olmasa da joystick olaylarini isle (Windows)
            os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
            import pygame
        except ImportError:
            self.konsol("MANUEL",
                        "pygame kurulu degil - fiziksel joystick devre disi "
                        "(pip install pygame). Alternatif: joystick'i "
                        "tarayicinin calistigi bilgisayara takin.")
            return
        pygame.init()
        pygame.joystick.init()
        joy = None
        son_tarama = 0.0

        while not self._durdur.is_set():
            simdi = time.time()
            # 3 sn'de bir joystick tak/cikar taramasi
            if joy is None and (simdi - son_tarama) > 3.0:
                son_tarama = simdi
                pygame.joystick.quit()
                pygame.joystick.init()
                if pygame.joystick.get_count() > 0:
                    try:
                        joy = pygame.joystick.Joystick(0)
                        joy.init()
                        with self.kilit:
                            self._joy_var = True
                            self._joy_adi = joy.get_name()
                        self.konsol("MANUEL",
                                    f"Joystick bulundu: {joy.get_name()}",
                                    "basari")
                    except Exception:
                        joy = None
            if joy is None:
                time.sleep(0.5)
                continue
            try:
                pygame.event.pump()
                n = joy.get_numaxes()
                # Eksen esleme (eksen sayisina gore):
                #  4+ eksen: 0=yanal(sag+), 1=ileri/geri(ters), 2=yaw,
                #            3=irtifa(ters)  [cift analog / RC tipi]
                #  3 eksen:  0=yanal, 1=ileri/geri, 2=yaw (irtifa yok)
                #  2 eksen:  0=yanal, 1=ileri/geri
                # v2.4.50: HAM degerler okunur; olu bolge/merkez/ters
                # islemi ortak modulde yapilir. Y eksenlerinin donanimsal
                # tersligi (RC yerlesimi) burada uygulanir, cunku bu
                # PILOT TERCIHI DEGIL donanim gercegidir; pilot tercihi
                # bunun uzerine `ters` bayragiyla biner.
                ham = {
                    "vy": joy.get_axis(0) if n > 0 else 0.0,
                    "vx": -joy.get_axis(1) if n > 1 else 0.0,
                    "yaw": joy.get_axis(2) if n > 2 else 0.0,
                    "vz": -joy.get_axis(3) if n > 3 else 0.0,
                }
                with self.kilit:
                    t = dict(self._tercih)
                    self._joy_ham = dict(ham)
                self._joy_eksen = joystick_ayar.isle(
                    ham, t, kaynak="pygame")
                time.sleep(0.05)
            except Exception:
                # Joystick cikarildi
                with self.kilit:
                    self._joy_var = False
                    self._joy_adi = ""
                    self._joy_eksen = {"vx": 0.0, "vy": 0.0,
                                       "vz": 0.0, "yaw": 0.0}
                    self._joy_ham = {"vx": 0.0, "vy": 0.0,
                                     "vz": 0.0, "yaw": 0.0}
                self.konsol("MANUEL", "Joystick baglantisi kesildi.")
                joy = None
