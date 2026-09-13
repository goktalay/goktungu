"""AngajmanYoneticisi: Coklu esanli hedef-bazli angajman motoru.

Her angajman bir (saldiran_sysid, hedef) ciftidir ve ayri thread'de calisir.
Hedef tipi "radar" (takip edilen radar hedefi), "dron" (baska bir dron)
veya "goruntu" (yerelde secilip merkezde konumu dogrulanan iz) olabilir.
Telemetri ve goruntu kipleri ayni icra dronunda eszamanli baslatilamaz.
"""
import math
import threading
import time

from pymavlink import mavutil

# v2.4.18 - Interceptor angajman profili
# Hucum hizi kullaniciya SORULMAZ: daima maksimum hizda gidilir.
MAKS_HIZ_MS = 83.3          # 300 km/h (drondan daha yuksek okunursa o kullanilir)
HEDEF_MIN_IRTIFA = 3.0      # m - hedef bu irtifanin altina duserse angajman biter
HEDEF_ZAMANASIMI = 10.0     # sn - hedef/dron verisi bu sure alinamazsa offline sayilir

# ----------------------------------------------------------------------
# v2.4.43 - ONGORULU KESISME (lead / intercept) GUDUMU
# ----------------------------------------------------------------------
# Eski davranis saf takipti (pure pursuit): her turda hedefin O ANKI
# konumuna yonelinir. Hedef hareketliyse saldiran daima hedefin ARKASINA
# doner ("kopek kuyrugu" egrisi); yol uzar ve hedef saldirandan hizliysa
# yakalama kesisme yolu ile mumkun olsa bile gerceklesmez.
#
# Yeni davranis: hedefin hiz vektoru (veya GOREVDEYSE rota bacagi)
# kullanilarak kesisme noktasi cozulur ve oraya yonelinir.
HEDEF_DURGUN_HIZ = 1.0      # m/s - bunun altinda hedef durgun sayilir
ONGORU_UST_SINIR = 120.0    # sn - kesisme cozumu bu sureyi asarsa kullanilmaz
GOREV_BACAK_TOLERANS = 15.0  # m - rota bacagina bu kadar yakinsa bacak bitmis sayilir

# Konum tasiyan MAVLink gorev komutlari. DO_CHANGE_SPEED (178) ve
# CONDITION_YAW (115) gibi ogelerin x/y alani 0'dir; ongoruyu bunlara
# kurmak hedefi 0,0 (Gine Korfezi) yapardi.
KONUMLU_KOMUTLAR = frozenset((
    16,   # MAV_CMD_NAV_WAYPOINT
    17,   # MAV_CMD_NAV_LOITER_UNLIM
    18,   # MAV_CMD_NAV_LOITER_TURNS
    19,   # MAV_CMD_NAV_LOITER_TIME
    21,   # MAV_CMD_NAV_LAND
    22,   # MAV_CMD_NAV_TAKEOFF
    82,   # MAV_CMD_NAV_SPLINE_WAYPOINT
))


def metre_basi_derece(lat):
    """Verilen enlemde 1 metrenin kac derece oldugunu dondurur.

    Donen: (derece_enlem_basina_metre, derece_boylam_basina_metre)
    Kucuk mesafelerde (angajman olceginde: <10 km) duzlem yaklasimi
    haversine ile ayni sonucu verir ve ikinci derece denklemi cozmeyi
    mumkun kilar.
    """
    d_lat = 111320.0
    d_lon = 111320.0 * max(0.01, math.cos(math.radians(lat)))
    return d_lat, d_lon


def kesisme_suresi(dx, dy, dz, hx, hy, hz, hiz):
    """Sabit hizli hedef icin kesisme suresini (sn) cozer.

    dx,dy,dz : hedefin saldirana gore KONUM farki (m, dogu/kuzey/yukari)
    hx,hy,hz : hedefin HIZ vektoru (m/s, ayni eksenler)
    hiz      : saldiranin sabit sur'ati (m/s)

    |D + H*t| = hiz*t denklemi t icin ikinci derecedir:
        (H.H - hiz^2) t^2 + 2(D.H) t + (D.D) = 0

    Donen: en kucuk pozitif kok, yoksa None.
    None donmesi bir hata DEGILDIR: hedef saldirandan hizli ve
    kaciyorsa kesisme matematiksel olarak yoktur.
    """
    a = hx * hx + hy * hy + hz * hz - hiz * hiz
    b = 2.0 * (dx * hx + dy * hy + dz * hz)
    c = dx * dx + dy * dy + dz * dz

    if abs(a) < 1e-9:
        # Hedef tam saldiran hiziyla gidiyor: denklem dogrusallasir
        if abs(b) < 1e-9:
            return None
        t = -c / b
        return t if t > 0 else None

    disk = b * b - 4.0 * a * c
    if disk < 0:
        return None
    kok = math.sqrt(disk)
    t1 = (-b - kok) / (2.0 * a)
    t2 = (-b + kok) / (2.0 * a)
    kokler = sorted(t for t in (t1, t2) if t > 1e-6)
    return kokler[0] if kokler else None



def haversine(lat1, lon1, lat2, lon2):
    """Iki GPS noktasi arasi mesafe (metre)."""
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def bearing(lat1, lon1, lat2, lon2):
    """Iki GPS noktasi arasi yatay yon (derece, 0=kuzey, saat yonu)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlam = math.radians(lon2 - lon1)
    x = math.sin(dlam) * math.cos(phi2)
    y = (math.cos(phi1) * math.sin(phi2)
         - math.sin(phi1) * math.cos(phi2) * math.cos(dlam))
    return (math.degrees(math.atan2(x, y)) + 360) % 360


class AngajmanYoneticisi:

    def __init__(self, konsol, dron, kilit, takipci=None, radar=None,
                 hedef_deposu=None):
        """
        konsol       : KonsolLog
        dron         : DronYoneticisi
        kilit        : paylasilan threading.Lock
        takipci      : Takipci (radar hedef konumu icin)
        radar        : RadarYoneticisi (ham hedef fallback icin)
        hedef_deposu : HedefDeposu (IS93 -- goruntu hedefi konumu icin)

        `hedef_deposu` ISTEGE BAGLIDIR: verilmezse goruntu hedefi
        cozulemez ve angajman reddedilir. Boylece bu surumu eski bir
        cagri yeriyle kullanmak COKME degil, GORUNUR RET uretir.
        """
        self.konsol = konsol
        self.dron = dron
        self.kilit = kilit
        self.takipci = takipci
        self.radar = radar
        self.hedef_deposu = hedef_deposu
        # Aktif angajmanlar: saldiran_sysid -> {thread, durdur_event, hedef_tip, hedef_id, param}
        self._aktif = {}
        # Canli durum: saldiran_sysid -> {mesafe, dikey_fark, yon, hiz, eta, ...}
        self._canli = {}
        self.aktif = False  # Geriye uyumluluk (en az bir angajman aktif mi)

        # --------------------------------------------------------------
        # v2.4.43 DUZELTME: parametreler artik KALICI ornek sozlugu.
        #
        # Onceki surumlerde `param` bir @property idi ve her cagrida YENI
        # bir sozluk uretiyordu. sunucu.py:angajman_param_yukle() ise
        # `p = self.angajman.param; p["gudum_hz"] = ...` yazdigi icin
        # kaydedilmis ayarlar GECICI bir kopyaya yaziliyor ve fonksiyon
        # bitince kayboluyordu. Yani angajman ayarlari hicbir zaman
        # uygulanmiyordu. Simdi tek ve kalici bir sozluk var.
        # --------------------------------------------------------------
        self._param = {
            # Hizmet kararliligi: seri/MAVLink ve WS akisini bogmamak icin
            # varsayilan iki guncelleme/sn; backend ayrica ust sinir uygular.
            "gudum_hz": 2,
            "yakalama_mesafe": 2.0,
            # v2.4.18: hucum_hizi kullaniciya sorulmaz; daima MAKS_HIZ_MS
            # (veya drondan okunan daha yuksek ust sinir) kullanilir.
            "hucum_hizi": MAKS_HIZ_MS,
            # v2.4.43: hedefin GOREV durumu (rota, siradaki nokta)
            # ongoruye katilsin mi? Kullanici ayardan secer. Kapali ise
            # yalniz hiz vektoru kullanilir.
            "gorev_dikkate": True,
            # Kesisme ongorusu tamamen kapatilirsa v2.4.18 saf takip
            # davranisi birebir korunur.
            "ongoru": True,
        }

    @property
    def param(self):
        """Kalici angajman parametreleri (yazilabilir sozluk).

        DIKKAT: Donen sozluk canli nesnedir; uzerine yazmak ayari
        gercekten degistirir. Yeni angajman baslatirken kopyalanir
        (`baslat()`), boylece ucus sirasinda ayar degisimi devam eden
        angajmani etkilemez.
        """
        return self._param

    # ------------------------------------------------------------------
    # v2.4.18: Saldiran dronun maksimum hizi
    # ------------------------------------------------------------------
    def _maks_hiz(self, sysid):
        """Saldiran dron icin kullanilacak maksimum hizi (m/s) dondurur.

        Drondan okunan hiz parametresi (WPNAV_SPEED cm/s, AIRSPEED_MAX m/s
        vb.) MAKS_HIZ_MS'den buyukse o deger kullanilir; aksi halde
        MAKS_HIZ_MS (300 km/h) esas alinir. Interceptor profili: hiz asla
        kullanicidan sorulmaz ve asla dusurulmez.
        """
        hiz = MAKS_HIZ_MS
        try:
            from . import veritabani
            degerler, _toplam, _ts = veritabani.param_cache_oku(int(sysid))
            degerler = degerler or {}
            for ad, carpan in (("WPNAV_SPEED", 0.01),
                               ("AIRSPEED_MAX", 1.0),
                               ("ARSPD_FBW_MAX", 1.0)):
                v = degerler.get(ad)
                if v is None:
                    continue
                try:
                    v = float(v) * carpan
                except (TypeError, ValueError):
                    continue
                if v > hiz:
                    hiz = v
        except Exception:
            pass
        return hiz

    def _hiz_komutu(self, master, sysid, hiz_ms):
        """MAV_CMD_DO_CHANGE_SPEED ile hedef hizi maksimuma sabitler."""
        try:
            with self.kilit:
                master.mav.command_long_send(
                    sysid, 1,
                    mavutil.mavlink.MAV_CMD_DO_CHANGE_SPEED,
                    0,
                    1,          # param1: 1 = groundspeed
                    hiz_ms,     # param2: hiz (m/s)
                    -1,         # param3: throttle (degistirme)
                    0, 0, 0, 0)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Baslat / durdur
    # ------------------------------------------------------------------
    def baslat(self, saldiran_sysid, hedef_tip, hedef_id, param=None):
        """Belirli bir saldiran dron icin angajman baslatir.

        Doner: (basladi_mi, gerekce)

        NEDEN DEGER DONUYOR (IS93): eskiden bu yontem sessizce `return`
        ediyordu ve `sunucu.py:5508` sonucu SORMADAN arayuze
        `"aktif": True` duyuruyordu. Angajman reddedilse bile operator
        ekranda "aktif" goruyordu. Cagri yerleri donusu yok sayabilir;
        degisiklik geriye uyumludur.
        """
        if hedef_tip not in ("radar", "dron", "goruntu"):
            gerekce = "Angajman hedef turu gecersiz."
            self.konsol("ANGAJMAN", gerekce, "hata")
            return False, gerekce

        if saldiran_sysid in self._aktif:
            gerekce = "Dron zaten angajmanda, once iptal edin."
            self.konsol("ANGAJMAN", f"D{saldiran_sysid} {gerekce}",
                        "uyari")
            return False, gerekce

        if param is None:
            param = self.param.copy()
        elif not isinstance(param, dict):
            param = dict(self.param)
        goruntu_firma_id = param.get("_goruntu_firma_id")

        # IS93/IS99: goruntu hedefi ON DENETIMI. Merkez kipinde firma
        # kimliği sunucunun doğruladığı iç parametreden gelir; istemci hedef
        # kimliğiyle başka kiracının anlık izini çözemez.
        #
        # Angajman baslatildiktan SONRA hedefin konumsuz oldugunu
        # anlamak kotudur: is parcacigi acilir, operatore "angajman
        # baslatildi" duyurusu gider, dron LOITER'da bekler ve hicbir
        # sey olmaz. Eski `ai_takip` dalinin davranisi tam buydu.
        # Reddetmek gerekiyorsa BASLAMADAN reddedilmeli.
        if hedef_tip == "goruntu":
            h = self._goruntu_hedefi(hedef_id, goruntu_firma_id)
            if h is None:
                gerekce = (f"Goruntu hedefi bulunamadi ({hedef_id}); "
                           f"iz kaybolmus ya da veri bayat olabilir.")
                self.konsol("ANGAJMAN", gerekce, "hata")
                return False, gerekce
            if not h.get("konum_guvenilir"):
                gerekce = (f"Goruntu hedefi angajmana ALINAMAZ: "
                           f"{h.get('konum_gerekce') or 'konum cozulemedi'}. "
                           f"Kamerayi kalibre edin (enlem, boylam, "
                           f"gorus acisi).")
                self.konsol("ANGAJMAN", gerekce, "hata")
                return False, gerekce

        durdur = threading.Event()
        t = threading.Thread(
            target=self._dongu,
            args=(saldiran_sysid, hedef_tip, hedef_id, param, durdur),
            daemon=True)
        self._aktif[saldiran_sysid] = {
            "thread": t, "durdur": durdur,
            "hedef_tip": hedef_tip, "hedef_id": hedef_id, "param": param
        }
        t.start()
        self.aktif = True
        self.konsol("ANGAJMAN",
                    f"D{saldiran_sysid} -> {hedef_tip.upper()} #{hedef_id} angajman baslatildi!",
                    "basari")
        return True, ""

    def durdur(self, saldiran_sysid=None):
        """Belirli bir angajmani durdurur. sysid=None ise tumu durdurulur."""
        if saldiran_sysid is not None:
            bilgi = self._aktif.pop(saldiran_sysid, None)
            if bilgi:
                bilgi["durdur"].set()
                self.konsol("ANGAJMAN",
                            f"D{saldiran_sysid} angajmani durduruldu.", "uyari")
                # Saldiran dronu LOITER'a al
                self._loiter_yap(saldiran_sysid)
        else:
            for sid, bilgi in list(self._aktif.items()):
                bilgi["durdur"].set()
            self._aktif.clear()
            self.konsol("ANGAJMAN", "Tum angajmanlar durduruldu.", "uyari")

        self.aktif = len(self._aktif) > 0

    def durum_paketi(self):
        """Canli angajman durumlarini dict olarak dondurur.
        {saldiran_sysid: {mesafe, eta_sn, hiz, ...}}"""
        return dict(self._canli)

    def sessiz_durdur(self):
        """Baglanti kesilirken cagirilir (LOITER komutu gondermeden)."""
        for bilgi in self._aktif.values():
            bilgi["durdur"].set()
        self._aktif.clear()
        self.aktif = False

    def _loiter_yap(self, sysid):
        """Dronu LOITER moduna al."""
        master = self.dron.master_bul(sysid)
        if master:
            with self.kilit:
                try:
                    master.mav.set_mode_send(
                        sysid,
                        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                        5)  # LOITER
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Hedef konumunu al
    # ------------------------------------------------------------------
    def _hedef_konum(self, hedef_tip, hedef_id, firma_id=None):
        """Hedefin guncel lat, lon, alt degerlerini dondurur."""
        if hedef_tip == "dron":
            with self.kilit:
                d = self.dron.dronlar.get(int(hedef_id))
                if d and d["lat"] is not None:
                    return d["lat"], d["lon"], d.get("alt_rel", 0) or 0
        elif hedef_tip == "radar":
            # Oncelik 1: takipci izleri (int ve str anahtarla dene)
            if self.takipci:
                for hid in (hedef_id, int(hedef_id) if not isinstance(hedef_id, int) else None,
                            str(hedef_id) if isinstance(hedef_id, int) else None):
                    if hid is None:
                        continue
                    iz = self.takipci.iz_al(hid)
                    if iz and iz.get("lat") is not None:
                        return iz["lat"], iz["lon"], iz.get("yukseklik", 0) or 0
            # Oncelik 2: ham radar hedefleri (radar.hedefler dict)
            if self.radar:
                with self.kilit:
                    for hid in (hedef_id, int(hedef_id) if not isinstance(hedef_id, int) else str(hedef_id)):
                        h = self.radar.hedefler.get(hid)
                        if h and h.get("lat") is not None:
                            return h["lat"], h["lon"], h.get("yukseklik", 0) or 0
        elif hedef_tip == "goruntu":
            # IS93: Goruntu Koprusu hedefi.
            #
            # `ai_takip` DALI BURADAN SILINDI. Iki gerekce, ikisi de
            # olculdu (bkz. is_merkez/BULGU_AI_TAKIP.md):
            #   1. Dal zaten olmustu: `ai_yonetici` Is 71'de bos
            #      omurgaya cevrildi, `son_takip_konum` None donuyor,
            #      `lat, lon, _ = None` TypeError firlatiyor ve alttaki
            #      `except` bunu yutuyordu. Her cagri sessizce basarisiz.
            #   2. Calissaydi bile YANLISTI: hedef konumu olarak
            #      KAMERANIN konumunu donduruyordu (+15 m irtifa).
            #      Saldiran dron hedefe degil kameranin diregine ucardi.
            #
            # Yeni yol: konum KOPRUDE degil MERKEZDE cozulur
            # (`hedef_deposu.konum_coz`) ve hedefe islenmis gelir.
            # Kalibre olmayan kamerada `konum_guvenilir` False'tur ve
            # burada ACIKCA reddedilir -- sessiz basarisizlik yok.
            h = self._goruntu_hedefi(hedef_id, firma_id)
            if h and h.get("konum_guvenilir") and h.get("lat") is not None:
                return h["lat"], h["lon"], h.get("alt") or 0.0
        return None, None, None

    # ------------------------------------------------------------------
    # IS93: Goruntu hedefi cozumu
    # ------------------------------------------------------------------
    @staticmethod
    def _goruntu_kimlik(hedef_id):
        """`hedef_id`yi (ornek_id, kamera, iz) uclusune ayirir.

        Bicim: "ornek_id:kamera:iz" -- ornegin "a1b2c3:1:7".

        NEDEN BILESIK ANAHTAR: iz numaralari kamera basina uretilir ve
        her koprude bastan baslar. Yalniz `iz` tasinsaydi iki ayri
        koprunun 7 numarali izleri ayirt edilemez ve dron YANLIS
        hedefe yonlendirilebilirdi.
        """
        try:
            parca = str(hedef_id).split(":")
            if len(parca) != 3:
                return None
            return parca[0], int(parca[1]), int(parca[2])
        except (TypeError, ValueError):
            return None

    def _goruntu_hedefi(self, hedef_id, firma_id=None):
        """Goruntu hedefinin GUNCEL kaydini depodan okur.

        Her cagrida yeniden okunur: hedef hareket eder, onbelleklenmis
        konumla guduM yapmak hedefi kacirir. Iz kaybolduysa ya da veri
        bayatladiysa None doner ve guduM dongusu angajmani keser.
        """
        kimlik = self._goruntu_kimlik(hedef_id)
        if not kimlik:
            return None
        depo = getattr(self, "hedef_deposu", None)
        if depo is None:
            return None
        try:
            return depo.hedef_bul(*kimlik, firma_id=firma_id)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # v2.4.43: Hedefin KONUM + HIZ VEKTORU + GOREV durumu
    # ------------------------------------------------------------------
    def _hedef_durum(self, hedef_tip, hedef_id, firma_id=None):
        """Hedefin ongoru icin gereken tam durumunu dondurur.

        Donen sozluk (hedef bulunamazsa None):
          lat, lon, alt      : konum
          ve, vn, vu         : hiz vektoru (m/s) - DOGU, KUZEY, YUKARI
          hiz                : yatay sur'at (m/s)
          mod                : ucus modu (dron hedefi icin, yoksa "")
          gorev              : {seq, lat, lon, alt} siradaki rota noktasi
                               veya None

        EKSEN UYARISI: dron telemetrisi MAVLink NED kullanir
        (vx=KUZEY, vy=DOGU); takipci ENU kullanir (vx=DOGU, vy=KUZEY).
        Ikisi burada TEK duzene (dogu, kuzey, yukari) cevrilir. Bu
        donusum atlanirsa hedef 90 derece sapmayla ongorulur.
        """
        if hedef_tip == "dron":
            with self.kilit:
                d = self.dron.dronlar.get(int(hedef_id))
                if not d or d.get("lat") is None:
                    return None
                lat = d["lat"]
                lon = d["lon"]
                alt = d.get("alt_rel", 0) or 0
                # MAVLink NED -> (dogu, kuzey, yukari)
                vn = float(d.get("vx") or 0.0)   # kuzey
                ve = float(d.get("vy") or 0.0)   # dogu
                vu = float(d.get("vz") or 0.0)   # dron.py'de +yukari'ya cevrilmis
                mod = str(d.get("mod") or "")
            durum = {"lat": lat, "lon": lon, "alt": alt,
                     "ve": ve, "vn": vn, "vu": vu,
                     "hiz": math.sqrt(ve * ve + vn * vn),
                     "mod": mod, "gorev": None}
            durum["gorev"] = self._hedef_gorev_noktasi(int(hedef_id))
            return durum

        if hedef_tip == "radar":
            if self.takipci:
                for hid in (hedef_id,
                            int(hedef_id) if not isinstance(hedef_id, int) else None,
                            str(hedef_id) if isinstance(hedef_id, int) else None):
                    if hid is None:
                        continue
                    iz = self.takipci.iz_al(hid)
                    if iz and iz.get("lat") is not None:
                        # Takipci ENU: vx=dogu, vy=kuzey, vz=yukari
                        ve = float(iz.get("vx") or 0.0)
                        vn = float(iz.get("vy") or 0.0)
                        vu = float(iz.get("vz") or 0.0)
                        return {"lat": iz["lat"], "lon": iz["lon"],
                                "alt": iz.get("yukseklik", 0) or 0,
                                "ve": ve, "vn": vn, "vu": vu,
                                "hiz": math.sqrt(ve * ve + vn * vn),
                                "mod": "", "gorev": None}
            # Ham radar hedefi: hiz vektoru yok, yalniz konum
            if self.radar:
                with self.kilit:
                    for hid in (hedef_id,
                                int(hedef_id) if not isinstance(hedef_id, int)
                                else str(hedef_id)):
                        h = self.radar.hedefler.get(hid)
                        if h and h.get("lat") is not None:
                            return {"lat": h["lat"], "lon": h["lon"],
                                    "alt": h.get("yukseklik", 0) or 0,
                                    "ve": 0.0, "vn": 0.0, "vu": 0.0,
                                    "hiz": 0.0, "mod": "", "gorev": None}
            return None

        if hedef_tip == "goruntu":
            # IS93: goruntu hedefinin HIZ VEKTORU yoktur.
            #
            # Kopru acisal hiz (`aci_hiz`, derece/sn) ve piksel hizi
            # olcer. Bunlari m/s'ye cevirmek MESAFEYE bolmeyi gerektirir
            # ve mesafe zaten bir TAHMINDIR (guven <= 0.60). Tahminden
            # turetilen hizla ongoru yapmak, ongorunun kendisini
            # guvenilmez kilar: hedef 200 m yerine 300 m'deyse hiz %50
            # sapar ve kesisme noktasi tamamen kayar.
            #
            # Bu yuzden hiz SIFIR verilir. Sonuc: `_kesisme_coz()`
            # ongoru yapmaz, dron hedefin ANLIK konumuna surulur
            # (saf takip). Yavas hedefte (insan, arac) bu yeterlidir.
            # Hizli hedefte operator radar izini kullanmalidir.
            h = self._goruntu_hedefi(hedef_id, firma_id)
            if not h or not h.get("konum_guvenilir") or h.get("lat") is None:
                return None
            return {"lat": h["lat"], "lon": h["lon"],
                    "alt": h.get("alt") or 0.0,
                    "ve": 0.0, "vn": 0.0, "vu": 0.0,
                    "hiz": 0.0, "mod": "", "gorev": None}

        # Bilinmeyen tipler: eski yol (hiz bilgisi yok)
        lat, lon, alt = self._hedef_konum(hedef_tip, hedef_id, firma_id)
        if lat is None:
            return None
        return {"lat": lat, "lon": lon, "alt": alt,
                "ve": 0.0, "vn": 0.0, "vu": 0.0,
                "hiz": 0.0, "mod": "", "gorev": None}

    def _hedef_gorev_noktasi(self, sysid):
        """Hedef dron GOREVDEYSE siradaki rota noktasini dondurur.

        Donen: {"seq": int, "lat": float, "lon": float, "alt": float}
        veya None (gorev yok / yuklenmemis / konumlu oge kalmamis).

        Ek MAVLink istegi YAPILMAZ: gorev ogeleri zaten sunucu
        belleginde (GorevYoneticisi.gorevler[sysid]["ogeler"]).

        TUZAK: ogeler listesinde DO_CHANGE_SPEED (178) ve CONDITION_YAW
        (115) gibi konum TASIMAYAN ogeler de var; onlarin x/y alani
        0'dir. mevcut_seq boyle bir ogeyi gosterirken x/y okunsa hedef
        0,0 (Gine Korfezi) cikar. Bu yuzden komut tipi denetlenir ve
        gerekirse ILERI dogru ilk konumlu oge aranir.
        """
        gorev = getattr(self, "gorev", None)
        if gorev is None:
            return None
        try:
            kayit = gorev.gorevler.get(sysid)
        except Exception:
            return None
        if not kayit:
            return None
        if kayit.get("asama") != "gorevde":
            # Yalniz UCULAN gorev ongoruye girer. "yuklendi" asamasinda
            # dron henuz rotaya baslamamistir; o rotayi ongoru saymak
            # hedefi olmayan bir harekete gore yonlendirmek olurdu.
            return None
        ogeler = kayit.get("ogeler") or []
        if not ogeler:
            return None
        try:
            mevcut = int(kayit.get("mevcut_seq") or 0)
        except (TypeError, ValueError):
            mevcut = 0

        # mevcut_seq'ten baslayarak ILK konumlu ogeyi bul
        for oge in ogeler:
            try:
                seq = int(oge[0])
                komut = int(oge[2])
                x = int(oge[9])
                y = int(oge[10])
                z = float(oge[11])
            except (IndexError, TypeError, ValueError):
                continue
            if seq < mevcut:
                continue
            if komut not in KONUMLU_KOMUTLAR:
                continue
            if x == 0 and y == 0:
                # TAKEOFF gibi ogeler konum tasimaz (x=y=0)
                continue
            return {"seq": seq, "lat": x / 1e7, "lon": y / 1e7, "alt": z}
        return None

    # ------------------------------------------------------------------
    # v2.4.43: Kesisme cozumu
    # ------------------------------------------------------------------
    def _kesisme_coz(self, s_lat, s_lon, s_alt, hedef, hiz, param):
        """Yonelinecek noktayi ve cozum bilgisini dondurur.

        s_*    : saldiranin konumu
        hedef  : `_hedef_durum()` sozlugu
        hiz    : saldiranin hucum hizi (m/s)
        param  : angajman parametreleri (gorev_dikkate, ongoru)

        Donen sozluk:
          lat, lon, alt   : YONELINECEK nokta (kesisme veya hedefin kendisi)
          kaynak          : "gorev" | "hiz" | "yok"
          kesisme_sn      : cozulen kesisme suresi veya None
          hedef_hiz       : hedefin yatay sur'ati (m/s)
          sapma           : saf takip yonu ile ongoru yonu arasi fark (derece)

        kaynak=="yok" ise donen nokta hedefin ANLIK konumudur; bu,
        v2.4.18 saf takip davranisinin aynisidir.
        """
        h_lat, h_lon, h_alt = hedef["lat"], hedef["lon"], hedef["alt"]
        sonuc = {"lat": h_lat, "lon": h_lon, "alt": h_alt,
                 "kaynak": "yok", "kesisme_sn": None,
                 "hedef_hiz": round(hedef.get("hiz", 0.0), 1),
                 "sapma": 0.0}

        if not param.get("ongoru", True):
            return sonuc

        ve = hedef.get("ve", 0.0)
        vn = hedef.get("vn", 0.0)
        vu = hedef.get("vu", 0.0)
        yatay_hiz = math.sqrt(ve * ve + vn * vn)

        gorev = hedef.get("gorev") if param.get("gorev_dikkate", True) else None

        # Hedef durgun ve gorev de yoksa ongorulecek bir sey yok
        if yatay_hiz < HEDEF_DURGUN_HIZ and not gorev:
            return sonuc

        d_lat_m, d_lon_m = metre_basi_derece(h_lat)
        # Hedefin saldirana gore konum farki (dogu, kuzey, yukari)
        dx = (h_lon - s_lon) * d_lon_m
        dy = (h_lat - s_lat) * d_lat_m
        dz = h_alt - s_alt

        kaynak = "yok"

        # --------------------------------------------------------------
        # Kaynak 1: GOREV BACAGI
        # Hedef GOREVDEyse gidecegi yer bellidir. Hiz vektoru anlik
        # savrulmalardan (ruzgar, viraj, mod gecisi) etkilenir; rota
        # bacagi etkilenmez. Bu yuzden gorev varsa hedefin hiz YONU
        # bacak yonuyle degistirilir, SUR'AT olculen degerde kalir.
        # --------------------------------------------------------------
        if gorev:
            g_dx = (gorev["lon"] - h_lon) * d_lon_m
            g_dy = (gorev["lat"] - h_lat) * d_lat_m
            g_dz = (gorev.get("alt") or h_alt) - h_alt
            bacak = math.sqrt(g_dx * g_dx + g_dy * g_dy)
            if bacak > GOREV_BACAK_TOLERANS:
                # Sur'at: olculen yatay hiz; hic hareket yoksa bacak
                # yonunde ilerledigi VARSAYILMAZ (0 kalir, asagida
                # durgun sayilir) - hayali hiz uretmek yaniltici olurdu.
                if yatay_hiz >= HEDEF_DURGUN_HIZ:
                    olcek = yatay_hiz / bacak
                    ve = g_dx * olcek
                    vn = g_dy * olcek
                    # Dikey: bacak boyunca gereken tirmanma/inis
                    sure_bacak = bacak / max(yatay_hiz, 0.1)
                    vu = g_dz / sure_bacak if sure_bacak > 0.1 else vu
                    kaynak = "gorev"

        if kaynak != "gorev":
            if yatay_hiz < HEDEF_DURGUN_HIZ:
                return sonuc
            kaynak = "hiz"

        t = kesisme_suresi(dx, dy, dz, ve, vn, vu, hiz)
        if t is None or t > ONGORU_UST_SINIR:
            # Kesisme yok (hedef kaciyor ve daha hizli) veya cozum cok
            # uzak: saf takibe DUS. Boyle bir durumda hedefin arkasindan
            # gitmek yine de dogru davranistir - hedef yavaslarsa veya
            # doner-ki gorevli hedefler doner- mesafe kapanir.
            sonuc["kesisme_sn"] = None
            sonuc["kaynak"] = "yok"
            return sonuc

        # Kesisme noktasi
        k_lat = h_lat + (vn * t) / d_lat_m
        k_lon = h_lon + (ve * t) / d_lon_m
        k_alt = h_alt + vu * t
        if k_alt < HEDEF_MIN_IRTIFA:
            # Ongorulen nokta yerin altinda/cok alcak: irtifayi hedefin
            # mevcut irtifasinda tut. Yer carpmasina yonelmek yerine
            # yatay ongoruyu korumak dogru davranistir.
            k_alt = h_alt

        saf_yon = bearing(s_lat, s_lon, h_lat, h_lon)
        ong_yon = bearing(s_lat, s_lon, k_lat, k_lon)
        sapma = abs((ong_yon - saf_yon + 180.0) % 360.0 - 180.0)

        sonuc.update({"lat": k_lat, "lon": k_lon, "alt": k_alt,
                      "kaynak": kaynak, "kesisme_sn": round(t, 1),
                      "sapma": round(sapma, 1)})
        return sonuc

    # ------------------------------------------------------------------
    # Gudum dongusu (thread)
    # ------------------------------------------------------------------
    def _dongu(self, saldiran_sysid, hedef_tip, hedef_id, param, durdur):
        """Saldiran dronu hedef konumuna yonlendiren gudum dongusu."""
        try:
            GUDUM_HZ = float(param.get("gudum_hz", 2))
        except (TypeError, ValueError):
            GUDUM_HZ = 2.0
        # Bir angajman is parcaciginin ortak seri kilidini ve WS yayinini
        # bogmasini engelleyen muhafazakar hizmet siniri.
        GUDUM_HZ = max(1.0, min(4.0, GUDUM_HZ))
        YAKALAMA_MESAFE = param.get("yakalama_mesafe", 2.0)
        goruntu_firma_id = param.get("_goruntu_firma_id")
        # v2.4.18: hucum hizi kullanicidan ALINMAZ; daima maksimum
        HUCUM_HIZI = self._maks_hiz(saldiran_sysid)

        hedef_kayip_basi = None  # hedef konumu alinamayan ilk an
        veri_kayip_basi = None   # saldiran dron verisi alinamayan ilk an
        son_hiz_komutu = 0.0     # DO_CHANGE_SPEED tekrar zamani
        son_mod_komutu = 0.0     # GUIDED moda gecis tekrar zamani
        self.konsol("ANGAJMAN",
                    f"D{saldiran_sysid}: TAM HIZ angajman - hedef hiz "
                    f"{HUCUM_HIZI:.1f} m/s ({HUCUM_HIZI * 3.6:.0f} km/h), "
                    f"yaklasma yavaslamasi KAPALI", "basari")

        # Baslangic durumu: popup'in bos kalmamasini sagla
        self._canli[saldiran_sysid] = {
            "durum": "hedef_bekleniyor",
            "hedef_tip": hedef_tip, "hedef_id": hedef_id,
            "mesafe": None, "eta_sn": None, "hiz": None,
            "hucum_hizi": HUCUM_HIZI, "yakalama_mesafe": YAKALAMA_MESAFE,
            "yon": None, "dikey_fark": None,
            "saldiran_alt": None, "hedef_alt": None,
            "yatay_mesafe": None,
            # v2.4.43: ongoru alanlari bastan tanimli olsun ki arayuz
            # "undefined" okumasin
            "ongoru": False, "ongoru_kaynak": "yok", "kesisme_sn": None,
            "kesisme_lat": None, "kesisme_lon": None, "kesisme_alt": None,
            "hedef_hiz": None, "sapma": None,
            "hedef_mod": "", "hedef_gorev_seq": None,
            "gorev_dikkate": bool(param.get("gorev_dikkate", True)),
        }

        while not durdur.is_set():
            master = self.dron.master_bul(saldiran_sysid)
            if master is None:
                if veri_kayip_basi is None:
                    veri_kayip_basi = time.time()
                elif (time.time() - veri_kayip_basi) >= HEDEF_ZAMANASIMI:
                    self.konsol("ANGAJMAN",
                                f"D{saldiran_sysid}: Dron baglantisi {HEDEF_ZAMANASIMI:.0f}sn alinamadi, "
                                f"angajman IPTAL ediliyor!", "hata")
                    break
                time.sleep(0.5)
                continue
            veri_kayip_basi = None
            # Saldiran dron konumu. Bekleme KESINLIKLE ortak kilit
            # icinde yapilmaz; aksi halde telemetri alicisi ve WS islemleri
            # ayni kilitte bekleyerek tum Merkezi kilitlerdi.
            with self.kilit:
                saldiran = dict(self.dron.dronlar.get(saldiran_sysid) or {})
            if not saldiran or saldiran.get("lat") is None:
                time.sleep(0.2)
                continue
            s_lat, s_lon = saldiran["lat"], saldiran["lon"]
            s_alt = saldiran.get("alt_rel", 0) or 0

            # Hedef durumu (konum + hiz vektoru + gorev) - v2.4.43
            hedef_durum = self._hedef_durum(
                hedef_tip, hedef_id, goruntu_firma_id)
            if hedef_durum is None:
                h_lat = h_lon = h_alt = None
            else:
                h_lat = hedef_durum["lat"]
                h_lon = hedef_durum["lon"]
                h_alt = hedef_durum["alt"]
            if h_lat is None:
                if hedef_kayip_basi is None:
                    hedef_kayip_basi = time.time()
                elif (time.time() - hedef_kayip_basi) >= HEDEF_ZAMANASIMI:
                    self.konsol("ANGAJMAN",
                                f"D{saldiran_sysid}: Hedef konumu {HEDEF_ZAMANASIMI:.0f}sn alinamadi, "
                                f"angajman IPTAL ediliyor!", "hata")
                    self._loiter_yap(saldiran_sysid)
                    break
                # Popup'a durum bildir
                self._canli[saldiran_sysid] = {
                    "durum": "hedef_bekleniyor",
                    "hedef_tip": hedef_tip, "hedef_id": hedef_id,
                    "mesafe": None, "eta_sn": None, "hiz": None,
                    "hucum_hizi": HUCUM_HIZI, "yakalama_mesafe": YAKALAMA_MESAFE,
                    "yon": None, "dikey_fark": None,
                    "saldiran_alt": round(s_alt, 1), "hedef_alt": None,
                    "yatay_mesafe": None,
                    "ongoru": False, "ongoru_kaynak": "yok", "kesisme_sn": None,
                    "kesisme_lat": None, "kesisme_lon": None, "kesisme_alt": None,
                    "hedef_hiz": None, "sapma": None,
                    "hedef_mod": "", "hedef_gorev_seq": None,
                    "gorev_dikkate": bool(param.get("gorev_dikkate", True)),
                }
                time.sleep(0.2)
                continue
            # Hedef konumu alindi — zamanlayiciyi sifirla
            hedef_kayip_basi = None

            # Mesafe
            mesafe = haversine(s_lat, s_lon, h_lat, h_lon)
            dikey_fark = abs(h_alt - s_alt)
            toplam_mesafe = math.sqrt(mesafe ** 2 + dikey_fark ** 2)
            yon_derece = bearing(s_lat, s_lon, h_lat, h_lon)

            # v2.4.43: ONGORULU KESISME COZUMU
            # Yonelinecek nokta hedefin ANLIK konumu olmak zorunda degil;
            # hedef hareketliyse kesisme noktasi cozulur.
            cozum = self._kesisme_coz(s_lat, s_lon, s_alt, hedef_durum,
                                      HUCUM_HIZI, param)
            g_lat, g_lon, g_alt = cozum["lat"], cozum["lon"], cozum["alt"]

            # Canli hiz (dron groundspeed)
            canli_hiz = saldiran.get("groundspeed", 0) or 0
            # ETA (saniye) = mesafe / hiz (hucum hizi veya canli hiz)
            etkin_hiz = max(canli_hiz, 0.1)
            eta_sn = toplam_mesafe / etkin_hiz if etkin_hiz > 0.5 else -1
            # Canli durumu kaydet (thread-safe: dict atama atomik)
            self._canli[saldiran_sysid] = {
                "durum": "aktif",
                "mesafe": round(toplam_mesafe, 1),
                "yatay_mesafe": round(mesafe, 1),
                "dikey_fark": round(h_alt - s_alt, 1),
                "yon": round(yon_derece, 1),
                "hiz": round(canli_hiz, 1),
                "hucum_hizi": HUCUM_HIZI,
                "eta_sn": round(eta_sn, 1) if eta_sn >= 0 else None,
                "saldiran_alt": round(s_alt, 1),
                "hedef_alt": round(h_alt, 1),
                "hedef_tip": hedef_tip,
                "hedef_id": hedef_id,
                "yakalama_mesafe": YAKALAMA_MESAFE,
                # v2.4.43: ongoru cozumu (arayuz gosterimi icin)
                "ongoru": cozum["kaynak"] != "yok",
                "ongoru_kaynak": cozum["kaynak"],
                "kesisme_sn": cozum["kesisme_sn"],
                "kesisme_lat": round(g_lat, 7) if cozum["kaynak"] != "yok" else None,
                "kesisme_lon": round(g_lon, 7) if cozum["kaynak"] != "yok" else None,
                "kesisme_alt": round(g_alt, 1) if cozum["kaynak"] != "yok" else None,
                "hedef_hiz": cozum["hedef_hiz"],
                "sapma": cozum["sapma"],
                "hedef_mod": hedef_durum.get("mod") or "",
                "hedef_gorev_seq": (hedef_durum.get("gorev") or {}).get("seq"),
                "gorev_dikkate": bool(param.get("gorev_dikkate", True)),
            }

            # ----------------------------------------------------------
            # v2.4.18: SONLANMA KOSULLARI
            # Angajman YALNIZCA su durumlarda biter:
            #   1) Hedef irtifasi HEDEF_MIN_IRTIFA (3 m) altina dustu
            #      (dusuruldu / yere indi)
            #   2) Hedef veya saldiran dron offline oldu (yukarida
            #      HEDEF_ZAMANASIMI ile ele alinir)
            #   3) Operator elle durdurdu
            # Yakalama mesafesine girmek ARTIK angajmani bitirmez ve hiz
            # dusurulmez - temas anina kadar tam hizda devam edilir.
            # ----------------------------------------------------------
            if h_alt < HEDEF_MIN_IRTIFA:
                self.konsol("ANGAJMAN",
                            f"D{saldiran_sysid}: Hedef irtifasi {h_alt:.1f} m "
                            f"(< {HEDEF_MIN_IRTIFA:.0f} m) - hedef etkisiz, "
                            f"angajman TAMAMLANDI", "basari")
                self._loiter_yap(saldiran_sysid)
                break
            # Bilgi amacli temas bildirimi (angajman DEVAM eder)
            if toplam_mesafe <= YAKALAMA_MESAFE:
                self._canli[saldiran_sysid]["durum"] = "temas"

            # ----------------------------------------------------------
            # v2.4.18: TAM HIZ GUDUM (yaklasma yavaslamasi yok)
            # Konum hedefi yerine HIZ VEKTORU gonderilir; boylece
            # ArduPilot'un "hedefe yaklasirken yavasla" profili devreye
            # girmez ve temas anina kadar maksimum hiz korunur.
            # ----------------------------------------------------------
            # v2.4.43: yon artik COZUM noktasina gore kurulur. Cozum
            # yoksa (kaynak=="yok") g_* hedefin anlik konumudur, yani
            # v2.4.18 saf takip davranisi birebir korunur.
            yon = bearing(s_lat, s_lon, g_lat, g_lon)
            yatay_gudum = haversine(s_lat, s_lon, g_lat, g_lon)
            simdi = time.time()
            try:
                # GUIDED modu her guncellemede yazilmaz. Telemetri gec
                # guncellense dahi iki saniyeden once tekrar komut yoktur.
                mod = str(saldiran.get("mod") or "").upper()
                if mod != "GUIDED" and simdi - son_mod_komutu >= 2.0:
                    with self.kilit:
                        master.mav.set_mode_send(
                            saldiran_sysid,
                            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                            4)  # GUIDED
                    son_mod_komutu = simdi
                # Hiz ust sinirini periyodik olarak maksimumda tut
                if simdi - son_hiz_komutu > 2.0:
                    self._hiz_komutu(master, saldiran_sysid, HUCUM_HIZI)
                    son_hiz_komutu = simdi
                # Yonelinen noktaya birim vektor (NED) * maksimum hiz
                yatay = max(yatay_gudum, 0.001)
                dz = g_alt - s_alt          # +yukari
                norm = math.sqrt(yatay ** 2 + dz ** 2) or 1.0
                yon_rad = math.radians(yon)
                vx = HUCUM_HIZI * (yatay / norm) * math.cos(yon_rad)  # kuzey
                vy = HUCUM_HIZI * (yatay / norm) * math.sin(yon_rad)  # dogu
                vz = -HUCUM_HIZI * (dz / norm)   # NED: asagi pozitif
                with self.kilit:
                    master.mav.set_position_target_global_int_send(
                        0,  # time_boot_ms
                        saldiran_sysid, 1,  # target_system, target_component
                        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                        # type_mask: yalniz HIZ kullan (konum+ivme+yaw yok)
                        0b0000111111000111,
                        0, 0, 0,          # lat, lon, alt (yok sayilir)
                        vx, vy, vz,       # hiz vektoru (m/s)
                        0, 0, 0,          # afx, afy, afz
                        0, 0)             # yaw, yaw_rate (yok sayilir)
            except Exception as e:
                self.konsol("ANGAJMAN", f"Komut hatasi: {e}", "hata")

            time.sleep(1.0 / GUDUM_HZ)

        # Dongu bitti: temizle
        self._aktif.pop(saldiran_sysid, None)
        self._canli.pop(saldiran_sysid, None)
        self.aktif = len(self._aktif) > 0
