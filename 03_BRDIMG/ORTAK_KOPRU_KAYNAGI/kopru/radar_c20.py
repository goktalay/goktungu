# -*- coding: utf-8 -*-
"""KOPRU YAZILIMI — C20 RADAR ISTEMCISI (protokol v3.0.0).

## NEDEN BU DOSYA KOPRUDE

Radar donanimi sahadaki YEREL agda durur (ornegin 192.168.8.186).
Merkez sunucu (goktungu.com) bu ozel ag adresine ULASAMAZ;
merkezde kosan bir radar istemcisi sonsuza kadar "timed out" verir.
Kullanicinin bildirdigi kusur tam olarak buydu:

    "radarda da ayni sorun var, radarin kopru yazilimi calisiyor ama
     sistem radari sunucuda ariyor"

Bu yuzden C20 oturumu SAHADA, koprunun kurulu oldugu makinede
kurulur; merkeze yalniz cozumlenmis durum ve iz verisi cikar.

## KAYNAK BIRLIGI

Bu dosya merkezdeki `goktungu/radar.py` ile AYNI protokol uygulamasidir
(CRC16-MODBUS, LOGIN, HEARTBEAT, UPLOAD_TRACK_V3 cozumu, RTK,
GETREG/SETREG). Protokol sahadaki gercek donanimla dogrulanmis
oldugu icin yeniden yazilmadi; yalniz BAGIMLILIKLARI kopru ortamina
uyarlandi:

  * `.sabitler` yerine C20 sabitleri bu dosyada gomulu — kopru pakedi
    merkez kaynak agacina bagimli olmamalidir
  * `ayarlar` nesnesi yerine iki geri cagirma: `ayar_oku()` /
    `ayar_yaz(sozluk)`
  * `konsol(kaynak, mesaj, seviye)` yerine kopru servis konsolu:
    `yaz(mesaj, seviye)`

Protokol govdesi (cerceveleme, bayt duzenleri, register adresleri)
BIREBIR korunmustur; degistirilmesi sahadaki radarla uyumu bozar.

## CERCEVE BICIMI

    0x55AA55AA + uzunluk(u32 BE) + komut(u32 BE) + frameID(u32 BE)
    + ek veri + CRC16-MODBUS (LITTLE-ENDIAN yazilir)

CRC'nin little-endian yazilmasi gercek donanimla dogrulanmistir;
buyuk-endian yazilirsa radar cerceveyi sessizce atar.
"""
import math
import socket
import struct
import threading
import time

# --- C20 protokol sabitleri (merkez goktungu/sabitler.py ile AYNI) -------
# Kopru pakedi merkez kaynak agacindan bagimsiz kurulabilmelidir; bu
# yuzden sabitler burada gomulu. Merkezdeki tanimlarla ayni kalmalidir.
RADAR_VARSAYILAN_IP = "192.168.8.186"
RADAR_VARSAYILAN_PORT = 5001
RADAR_IZ_ZAMANASIMI = 3.0     # sn: yenilenmeyen iz silinir

C20_HEARTBEAT        = 0x00000001
C20_LOGIN            = 0x00000002
C20_SETREG           = 0x00000040
C20_GETREG           = 0x00000041
C20_UPLOAD_TARGET_V3 = 0x00030001
C20_UPLOAD_TRACK_V3  = 0x00030002
C20_REQUEST_RTK      = 0x00010005
C20_UPLOAD_RTK       = 0x00010006

C20_HEDEF_TIPLERI = {
    0: "BELIRSIZ", 1: "INSAN", 2: "ARAC",
    3: "DRON", 4: "KUS", 5: "TANIMSIZ",
}
# WORKING_MODE kombinasyonlari (dokuman 2.4.2): (hiz<<8)|mod
C20_MOD_KODLARI = {
    "bekleme": 0x0000, "tarama1": 0x0401,
    "tarama2": 0x0101, "tarama4": 0x0201,
}
C20_MOD_ADLARI = {v: k for k, v in C20_MOD_KODLARI.items()}
# RTK tamam sayilmadan once alinacak ornek sayisi
RTK_HEDEF_ORNEK = 20


class RadarIstemcisi:

    def __init__(self, yaz, ayar_oku, ayar_yaz, kilit=None):
        """
        yaz      : yaz(mesaj, seviye="bilgi") — kopru servis konsolu
        ayar_oku : () -> sozluk (merkez_lat / merkez_lon /
                   radar_merkez_yonu)
        ayar_yaz : (sozluk) -> None — kalici ayar yazimi
        kilit    : threading.Lock; verilmezse kendi kilidini kurar

        Merkezdeki surumde `konsol` ve `ayarlar` NESNELERI gecilir.
        Koprude bu nesneler yoktur; bagimlilik en kucuk yuzeye (uc
        geri cagirma) indirilmistir. Protokol govdesi degismemistir.
        """
        self._yaz = yaz
        self._ayar_oku = ayar_oku
        self._ayar_yaz = ayar_yaz
        self.kilit = kilit or threading.Lock()
        self.durum = {   # panelde gosterilen radar baglanti durumu
            "durum": "kapali",   # kapali | baglaniyor | bagli | hata
            "ip": "", "port": 0, "hata": "",
            "lat": None, "lon": None,  # radar konumu (RTK veya merkez)
            "hdt": None,               # radar yonu (derece, RTK'dan)
            "rtk_durum": "",           # "" | "aliniyor" | "tamam" | "hata"
            "rtk_ilerleme": 0,         # 0-100
            # --- Saglik telemetrisi ---
            "baglanti_ani": None,      # login basarili an (epoch)
            "son_veri_ani": None,      # son TRACK mesaji ani (epoch)
            "veri_hizi": 0.0,          # TRACK mesaji / sn (kayan pencere)
            "hb_gecikme_ms": None,     # heartbeat gidis-donus gecikmesi
            "crc_hata": 0,             # bozuk cerceve / senkron kaybi
            "toplam_mesaj": 0,         # alinan toplam gecerli mesaj
        }
        self.hedefler = {}   # target_id -> hedef verisi
        # Radar calisma ayarlari (USER_CFG0 + WORKING_MODE registerlari)
        # frekans: 0-7 | hiz_esigi: 0=0.25 1=0.5 2=0.75 3=1.0 m/s
        # tespit_esigi: 0=dusuk 1=normal 2=yuksek
        # rcs_esigi: 0=kapali 1=0.01 2=0.05 m2
        # calisma_modu: "bekleme" | "tarama1" | "tarama2" | "tarama4"
        self.radar_ayarlar = {
            "frekans": None, "hiz_esigi": None,
            "tespit_esigi": None, "rcs_esigi": None,
            "calisma_modu": None,
            "merkez_yonu": 0.0,   # derece; azimut ofseti (dosyada saklanir)
            "kaynak": "",         # "radar" (GETREG ile okundu) | ""
            "son_sonuc": "",      # son SETREG sonucu: "ok" | "hata: ..."
        }
        self.ayar_kuyruk = []     # ("oku",) | ("yaz", {alanlar}) | ("rtk",)
        self._thread = None
        self._durdur = threading.Event()
        # Radar kesildiginde takipci izleri temizlenir (kanca main'de kurulur)
        self.kes_kancasi = None

    # ------------------------------------------------------------------
    # Ayar yukleme
    # ------------------------------------------------------------------
    def konsol(self, _kaynak, mesaj, seviye="bilgi"):
        """Merkezdeki `konsol(kaynak, mesaj, seviye)` imzasinin kopru
        karsiligi. Protokol govdesindeki cagrilar degistirilmedigi icin
        bu koprulenme burada yapilir; `kaynak` koprude gereksizdir
        (servis adi zaten satir onune eklenir)."""
        try:
            self._yaz(mesaj, seviye)
        except Exception:
            pass

    def ayar_yukle(self):
        """Ayar deposundan merkez yonu ofsetini yukler."""
        a = self._ayar_oku() or {}
        try:
            self.radar_ayarlar["merkez_yonu"] = (
                float(a.get("radar_merkez_yonu", 0.0)) % 360.0)
        except (TypeError, ValueError):
            self.radar_ayarlar["merkez_yonu"] = 0.0

    # ------------------------------------------------------------------
    # C20 protokol yardimcilari
    # ------------------------------------------------------------------
    @staticmethod
    def crc16(veri: bytes) -> int:
        """CRC16-MODBUS (dokuman Ek-I ile ayni sonucu uretir)."""
        crc = 0xFFFF
        for b in veri:
            crc ^= b
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc

    @classmethod
    def cerceve(cls, komut: int, frame_id: int, ek: bytes) -> bytes:
        """Radara gonderilecek tam cerceveyi olusturur.

        Not: CRC16-MODBUS sonucu cerceveye LITTLE-ENDIAN yazilir.
        Radarin gercek donanimi ile dogrulandi (yanit CRC'si 0x4079 =
        MODBUS 0x7940'in bayt takasli hali). Dokumandaki C kodu
        ((uchCRCHi<<8)|uchCRCLo) da ayni takasli degeri uretir."""
        govde = struct.pack(">II", komut, frame_id) + ek
        crc = cls.crc16(govde)
        uzunluk = len(govde) + 2   # govde + CRC (header ve length haric)
        return (struct.pack(">II", 0x55AA55AA, uzunluk) + govde
                + struct.pack("<H", crc))

    def radar_konum(self):
        """Radar konumu: RTK varsa onu, yoksa kayitli merkez konumu."""
        with self.kilit:
            if (self.durum["lat"] is not None
                    and self.durum["lon"] is not None):
                return self.durum["lat"], self.durum["lon"]
        a = self._ayar_oku() or {}
        try:
            return float(a["merkez_lat"]), float(a["merkez_lon"])
        except (KeyError, TypeError, ValueError):
            return None, None

    @staticmethod
    def hedef_coz(veri: bytes):
        """UPLOAD_TRACK_V3 ek verisini cozer, hedef listesi dondurur."""
        # Baslik: i64 utc, i64 frame_id, i64 upload_ts, i32 bas_aci,
        # i32 son_aci, u8 rsv, u8 rsv, u8 kuzey_bayragi, u8 tarama_yonu,
        # i32 N  = 40 bayt
        if len(veri) < 40:
            return []
        (_utc, _fid, _ts, _bas, _son,
         _r1, _r2, kuzey_bayragi, _yon, n) = struct.unpack(
            ">qqqiiBBBBi", veri[:40])
        hedefler = []
        ofs = 40
        HEDEF_BOYU = 64
        for _ in range(max(0, n)):
            if ofs + HEDEF_BOYU > len(veri):
                break
            h = veri[ofs:ofs + HEDEF_BOYU]
            ofs += HEDEF_BOYU
            (x, y, z, vx, vy, vz, tid, snr, rcs,
             _rz1, _rz2, _rz3, ttip, _rz4, _rz5, _rz6, _rz7,
             _rcs2, secili) = struct.unpack(">iiiiiiIhhhHHbbqiiii", h)
            hedefler.append({
                "id": int(tid),
                "x": x / 100.0, "y": y / 100.0, "z": z / 100.0,
                "vx": vx / 100.0, "vy": vy / 100.0, "vz": vz / 100.0,
                "snr": snr / 100.0, "rcs": rcs / 100.0,
                "tip_kod": int(ttip),
                "tip": C20_HEDEF_TIPLERI.get(int(ttip), "TANIMSIZ"),
                "secili": bool(secili),
                "kuzey": (kuzey_bayragi == 0),
            })
        return hedefler

    def hedef_konumlandir(self, h):
        """Radar-merkezli xyz'yi cografi konuma cevirir (Ek-II)."""
        rlat, rlon = self.radar_konum()
        if rlat is None:
            return None
        x, y, z = h["x"], h["y"], h["z"]
        yatay = math.sqrt(x * x + y * y)
        azimut = math.degrees(math.atan2(x, y))
        # Kuzey modunda degilse radar yonu (RTK hdt) ile duzelt
        if not h.get("kuzey", True):
            with self.kilit:
                hdt = self.durum.get("hdt")
            if hdt:
                azimut += hdt
        # Merkez yonu duzeltmesi (kullanici kalibrasyonu)
        with self.kilit:
            azimut += self.radar_ayarlar.get("merkez_yonu", 0.0) or 0.0
        az_rad = math.radians(azimut)
        dlat = (yatay * math.cos(az_rad)) / 111320.0
        dlon = (yatay * math.sin(az_rad)) / (
            111320.0 * math.cos(math.radians(rlat)))
        hiz = math.sqrt(h["vx"] ** 2 + h["vy"] ** 2 + h["vz"] ** 2)
        return {
            "lat": rlat + dlat, "lon": rlon + dlon,
            "yukseklik": z,           # radara gore metre
            "mesafe": math.sqrt(x * x + y * y + z * z),
            "azimut": (azimut + 360.0) % 360.0,
            "hiz": hiz,
        }

    @staticmethod
    def _tam_oku(s, n):
        """Soketten tam n bayt okur; baglanti kapanirsa None."""
        parcalar = b""
        while len(parcalar) < n:
            p = s.recv(n - len(parcalar))
            if not p:
                return None
            parcalar += p
        return parcalar

    # ------------------------------------------------------------------
    # Baglanti yonetimi
    # ------------------------------------------------------------------
    def baglan(self, ip, port=RADAR_VARSAYILAN_PORT):
        """Verilen adrese C20 oturumu acar.

        `ip` icin VARSAYILAN ARGUMAN YOKTUR (v1.5.4). Eskiden imza
        `ip=RADAR_VARSAYILAN_IP` idi; cagiran taraf adresi vermeyi
        atlarsa sessizce `192.168.8.186` yoklaniyordu. Kullanici bunu
        acikca istemedi: "kopru kendisine baglan komutu gelmeden
        baglanmamali". Adres artik cagiranin sorumlulugundadir ve bos
        gecilirse hata yukselir — sessiz varsayim yerine gorunur hata.
        """
        ip = str(ip or "").strip()
        if not ip:
            raise ValueError("radar IP adresi verilmedi")
        self.kes()
        self._durdur.clear()
        self._thread = threading.Thread(
            target=self._dongu, args=(ip, port, self._durdur), daemon=True)
        self._thread.start()

    def kes(self):
        if self._thread and self._thread.is_alive():
            self._durdur.set()
            self._thread.join(timeout=4.0)
        self._thread = None
        with self.kilit:
            self.hedefler.clear()
            self.durum.update(durum="kapali", ip="", port=0, hata="",
                              lat=None, lon=None, hdt=None,
                              rtk_durum="", rtk_ilerleme=0)
        # Radar kapatilinca izlenen hedefler de temizlenir; ekranda
        # eski tespitler kalmaz (kullanici istegi)
        if self.kes_kancasi:
            self.kes_kancasi()
        self.konsol("RADAR", "Baglanti kesildi, hedef izleri temizlendi.")

    # ------------------------------------------------------------------
    # Ana okuma dongusu (thread)
    # ------------------------------------------------------------------
    def _dongu(self, ip, port, durdur):
        """C20 radarina baglanir, login olur, iz verisini surekli okur."""
        with self.kilit:
            self.durum.update(durum="baglaniyor", ip=ip, port=port, hata="")
        self.konsol("RADAR", f"Baglaniliyor: {ip}:{port}")

        try:
            s = socket.create_connection((ip, port), timeout=5.0)
            s.settimeout(2.0)
        except Exception as e:
            with self.kilit:
                self.durum.update(durum="hata", hata=str(e))
            self.konsol("RADAR", f"Baglanti hatasi: {e}", "hata")
            return

        frame_sayac = 1

        def gonder(komut, ek):
            nonlocal frame_sayac
            s.sendall(self.cerceve(komut, frame_sayac, ek))
            frame_sayac = (frame_sayac + 1) & 0xFFFFFFFF

        try:
            # 1) SADECE LOGIN gonder (yonetici tipi 0x03).
            #    RTK ve SETREG, login yaniti geldikten SONRA gonderilir;
            #    bazi radarlar login oncesi komutlarda baglantiyi keser.
            gonder(C20_LOGIN, struct.pack(">II", 0x00000003, 0x00000000))
            self.konsol("RADAR", "LOGIN gonderildi, yanit bekleniyor...")
        except Exception as e:
            with self.kilit:
                self.durum.update(durum="hata", hata=f"Komut hatasi: {e}")
            self.konsol("RADAR", f"Komut gonderme hatasi: {e}", "hata")
            try:
                s.close()
            except Exception:
                pass
            return

        son_kalp = time.time()
        login_ok = False
        rtk_sayac = 0
        ardisik_hata = 0
        hb_gonderim_ani = None    # heartbeat gidis zamani (gecikme olcumu)
        track_zamanlar = []       # son TRACK zamanlari (veri hizi icin)

        def ayar_registerlari_oku():
            """USER_CFG0 ve WORKING_MODE registerlarini radardan ister."""
            gonder(C20_GETREG,
                   struct.pack(">III", 2, 0x00000440, 0x00000401))

        def ayar_registerlari_yaz(a):
            """Arayuzden gelen ayarlari SETREG ile radara yazar."""
            regler = []
            if all(a.get(k) is not None for k in
                   ("frekans", "hiz_esigi", "tespit_esigi", "rcs_esigi")):
                deger = ((int(a["frekans"]) & 0xFF) << 24 |
                         (int(a["hiz_esigi"]) & 0xFF) << 16 |
                         (int(a["tespit_esigi"]) & 0xFF) << 8 |
                         (int(a["rcs_esigi"]) & 0xFF))
                regler.append((0x00000440, deger))
            if a.get("calisma_modu") in C20_MOD_KODLARI:
                regler.append((0x00000401,
                               C20_MOD_KODLARI[a["calisma_modu"]]))
            if not regler:
                return
            ek = struct.pack(">I", len(regler))
            for adres, deger in regler:
                ek += struct.pack(">II", adres, deger)
            gonder(C20_SETREG, ek)
            print("[RADAR] SETREG gonderildi: "
                  + ", ".join(f"0x{a_:08X}=0x{d:08X}" for a_, d in regler))

        while not durdur.is_set():
            # 10 sn'de bir kalp atisi
            if time.time() - son_kalp > 10.0:
                try:
                    gonder(C20_HEARTBEAT, b"\x00" * 8)
                    son_kalp = time.time()
                    hb_gonderim_ani = son_kalp
                except Exception as e:
                    with self.kilit:
                        self.durum.update(durum="hata",
                                          hata=f"Kalp atisi: {e}")
                    self.konsol("RADAR", f"Kalp atisi hatasi: {e}", "uyari")
                    break

            # Arayuzden gelen ayar isteklerini isle (login sonrasi)
            if login_ok and self.ayar_kuyruk:
                with self.kilit:
                    istekler = self.ayar_kuyruk[:]
                    self.ayar_kuyruk.clear()
                for istek in istekler:
                    try:
                        if istek[0] == "oku":
                            ayar_registerlari_oku()
                        elif istek[0] == "yaz":
                            ayar_registerlari_yaz(istek[1])
                        elif istek[0] == "rtk":
                            # RTK yayinini yeniden ac; sayaci sifirla
                            rtk_sayac = 0
                            with self.kilit:
                                self.durum["rtk_durum"] = "aliniyor"
                                self.durum["rtk_ilerleme"] = 0
                            gonder(C20_REQUEST_RTK, struct.pack(">bb", 1, 0))
                            self.konsol("RADAR", "RTK konum istegi "
                                        "gonderildi, veriler bekleniyor...")
                    except Exception as e:
                        with self.kilit:
                            self.radar_ayarlar["son_sonuc"] = f"hata: {e}"
                        print(f"[RADAR] Ayar istegi hatasi: {e}")

            # Cerceve basligini bul (0x55AA55AA senkronizasyonu)
            try:
                bas = self._tam_oku(s, 4)
                if bas is None:
                    if not login_ok:
                        raise ConnectionError(
                            "radar login yanitindan once baglantiyi "
                            "kapatti (port yanlis olabilir veya radarin "
                            "kendi yazilimi hala bagli olabilir)")
                    raise ConnectionError("baglanti kapandi")
                while bas != b"\x55\xaa\x55\xaa":
                    ek_bayt = self._tam_oku(s, 1)
                    if ek_bayt is None:
                        raise ConnectionError("baglanti kapandi")
                    bas = bas[1:] + ek_bayt
                uz_ham = self._tam_oku(s, 4)
                if uz_ham is None:
                    raise ConnectionError("baglanti kapandi")
                uzunluk = struct.unpack(">I", uz_ham)[0]
                if not (10 <= uzunluk <= 1024 * 1024):
                    with self.kilit:
                        self.durum["crc_hata"] += 1
                    continue   # bozuk uzunluk, yeniden senkronize ol
                govde = self._tam_oku(s, uzunluk)
                if govde is None:
                    raise ConnectionError("baglanti kapandi")
                ardisik_hata = 0
            except socket.timeout:
                continue
            except Exception as e:
                ardisik_hata += 1
                if ardisik_hata >= 5 or isinstance(e, ConnectionError):
                    with self.kilit:
                        self.durum.update(durum="hata", hata=str(e))
                    self.konsol("RADAR", f"Okuma hatasi: {e}", "uyari")
                    break
                continue

            komut, _fid = struct.unpack(">II", govde[:8])
            ek = govde[8:-2]   # son 2 bayt CRC
            with self.kilit:
                self.durum["toplam_mesaj"] += 1
            if komut == C20_HEARTBEAT and hb_gonderim_ani is not None:
                with self.kilit:
                    self.durum["hb_gecikme_ms"] = round(
                        (time.time() - hb_gonderim_ani) * 1000.0, 1)
                hb_gonderim_ani = None

            if komut == C20_LOGIN:
                durum_kodu = (struct.unpack(">H", ek[4:6])[0]
                              if len(ek) >= 6 else 1)
                login_ok = (durum_kodu == 0)
                with self.kilit:
                    if login_ok:
                        self.durum["durum"] = "bagli"
                        self.durum["hata"] = ""
                        self.durum["baglanti_ani"] = time.time()
                        self.durum["crc_hata"] = 0
                        self.durum["toplam_mesaj"] = 0
                    else:
                        self.durum.update(
                            durum="hata",
                            hata=f"Login reddedildi: {durum_kodu}")
                self.konsol("RADAR",
                            f"Login {'basarili' if login_ok else 'BASARISIZ'}",
                            "basari" if login_ok else "hata")
                if not login_ok:
                    break
                # Login basarili -> RTK istegi ve radar baslatma gonderilir
                try:
                    gonder(C20_REQUEST_RTK, struct.pack(">bb", 1, 0))
                    gonder(C20_SETREG,
                           struct.pack(">III", 1, 0x00000401, 0x00000101))
                    self.konsol("RADAR",
                                "RTK istegi ve baslatma komutu gonderildi.")
                    # Mevcut calisma ayarlarini radardan oku
                    ayar_registerlari_oku()
                except Exception as e:
                    self.konsol("RADAR",
                                f"Baslatma komutu hatasi: {e}", "hata")

            elif komut == C20_UPLOAD_RTK and len(ek) >= 28:
                lat_i, lon_i, hdt_i, uydu = struct.unpack(">qqqi", ek[:28])
                if lat_i != 0 or lon_i != 0:
                    with self.kilit:
                        self.durum["lat"] = lat_i * 1e-9
                        self.durum["lon"] = lon_i * 1e-9
                        self.durum["hdt"] = hdt_i * 1e-9
                    rtk_sayac += 1
                    with self.kilit:
                        if self.durum["rtk_durum"] == "aliniyor":
                            self.durum["rtk_ilerleme"] = min(
                                100, int(rtk_sayac * 100 / RTK_HEDEF_ORNEK))
                    if rtk_sayac == RTK_HEDEF_ORNEK:
                        # Yeterli RTK verisi alindi, yayini kapat
                        try:
                            gonder(C20_REQUEST_RTK, struct.pack(">bb", 0, 0))
                        except Exception:
                            pass
                        with self.kilit:
                            lat = self.durum["lat"]
                            lon = self.durum["lon"]
                            self.durum["rtk_durum"] = "tamam"
                            self.durum["rtk_ilerleme"] = 100
                        # Merkez konumu RTK konumuyla guncelle ve kaydet
                        try:
                            self._ayar_yaz(
                                {"merkez_lat": lat, "merkez_lon": lon})
                        except Exception:
                            pass
                        self.konsol("RADAR",
                                    f"RTK konumu alindi: {lat:.6f}, "
                                    f"{lon:.6f}", "basari")

            elif komut == C20_UPLOAD_TRACK_V3:
                simdi = time.time()
                hedefler = self.hedef_coz(ek)
                # Saglik: veri hizi (10 sn kayan pencere) ve son veri ani
                track_zamanlar.append(simdi)
                while track_zamanlar and simdi - track_zamanlar[0] > 10.0:
                    track_zamanlar.pop(0)
                with self.kilit:
                    self.durum["son_veri_ani"] = simdi
                    self.durum["veri_hizi"] = round(
                        len(track_zamanlar) / 10.0, 2)
                    if self.durum["durum"] == "baglaniyor":
                        self.durum["durum"] = "bagli"  # veri geliyorsa bagli
                for h in hedefler:
                    konum = self.hedef_konumlandir(h)
                    kayit = dict(h)
                    kayit["son"] = simdi
                    if konum:
                        kayit.update(konum)
                    with self.kilit:
                        self.hedefler[h["id"]] = kayit
                # Eski izleri sil (3 sn yenilenmeyen)
                with self.kilit:
                    for tid in list(self.hedefler.keys()):
                        if (simdi - self.hedefler[tid]["son"]
                                > RADAR_IZ_ZAMANASIMI):
                            del self.hedefler[tid]

            elif komut == C20_GETREG and len(ek) >= 4:
                # GETREG yaniti: adet + (adres, deger) ciftleri
                adet = struct.unpack(">I", ek[:4])[0]
                ofs = 4
                with self.kilit:
                    for _ in range(min(adet, 16)):
                        if ofs + 8 > len(ek):
                            break
                        adres, deger = struct.unpack(">II", ek[ofs:ofs + 8])
                        ofs += 8
                        if adres == 0x00000440:
                            self.radar_ayarlar["frekans"] = (deger >> 24) & 0xFF
                            self.radar_ayarlar["hiz_esigi"] = (deger >> 16) & 0xFF
                            self.radar_ayarlar["tespit_esigi"] = (deger >> 8) & 0xFF
                            self.radar_ayarlar["rcs_esigi"] = deger & 0xFF
                        elif adres == 0x00000401:
                            self.radar_ayarlar["calisma_modu"] = (
                                C20_MOD_ADLARI.get(deger & 0xFFFF))
                    self.radar_ayarlar["kaynak"] = "radar"
                self.konsol("RADAR", f"Ayarlar okundu ({adet} register).")

            elif komut == C20_SETREG:
                # SETREG yaniti: durum kodu (0x0000 = basarili)
                durum_kodu = (struct.unpack(">H", ek[:2])[0]
                              if len(ek) >= 2 else 1)
                with self.kilit:
                    self.radar_ayarlar["son_sonuc"] = (
                        "ok" if durum_kodu == 0
                        else f"hata: kod {durum_kodu}")
                print(f"[RADAR] SETREG yaniti: "
                      f"{'basarili' if durum_kodu == 0 else 'HATA ' + str(durum_kodu)}")
                if durum_kodu == 0:
                    # Yazim basarili -> guncel degerleri geri oku (dogrulama)
                    try:
                        ayar_registerlari_oku()
                    except Exception:
                        pass

            # HEARTBEAT ve diger yanitlar: sessizce gec

        # Kapanis: radari durdur (standby) ve soketi kapat
        try:
            gonder(C20_SETREG, struct.pack(">III", 1, 0x00000401, 0x00000000))
        except Exception:
            pass
        try:
            s.close()
        except Exception:
            pass
        with self.kilit:
            if self.durum["durum"] != "hata":
                self.durum["durum"] = "kapali"
            self.durum["baglanti_ani"] = None
            self.durum["son_veri_ani"] = None
            self.durum["veri_hizi"] = 0.0
            self.durum["hb_gecikme_ms"] = None
            self.hedefler.clear()
        self.konsol("RADAR", "Baglanti kapatildi.", "uyari")
