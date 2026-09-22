# -*- coding: utf-8 -*-
"""GÖKTUNGU — Betaflight MSP v1 salt-okunur tanılama sürücüsü.

KÖPRÜ KOPYASI (Faz 5): Bu modül GRCOFF sürücüsünün
(01_GRCOFF/KAYNAK/goktungu/betaflight_msp.py) köprü çekirdeğine birebir
alınmış eşidir. Köprünün BRDTLM dron servisi Betaflight/MSP telemetrisini
salt-okunur olarak buradan okur. Sürücü mantığı GRCOFF ile ortak
tutulmalıdır; ikisinden birinde düzeltme yapılırsa diğeri de güncellenir.

Bu modül MAVLink'e veri dönüştürmez ve uçuş kumandası sağlamaz. Açıkça
izinli olan MSP sorguları dışında hiçbir çerçeve yazılamaz. Özellikle
MSP_SET_*, MSP_REBOOT, MSP_SET_RAW_RC, motor, ARM, kalibrasyon ve CLI bu
modülde tanımlı ya da gönderilebilir değildir.

MSP v1 referansı: https://betaflight.com/docs/development/MSP-Protocol-Reference-Dev
"""
from __future__ import annotations

import copy
import struct
import threading
import time
from collections import deque

# Sadece ilk sürümdeki salt-okunur sorgular. Sayısal kimlikler MSP v1
# cevabının komut baytıdır; izin listesi hem encoder hem oturum katmanında
# zorunlu denetlenir.
MSP_API_VERSION = 1
MSP_FC_VARIANT = 2
MSP_FC_VERSION = 3
MSP_BOARD_INFO = 4
MSP_BUILD_INFO = 5
MSP_NAME = 10
MSP_STATUS = 101
MSP_RAW_IMU = 102
MSP_RC = 105
MSP_ATTITUDE = 108
MSP_ALTITUDE = 109
MSP_ANALOG = 110
MSP_BATTERY_STATE = 130
MSP_UID = 160

IZINLI_SORGU_KOMUTLARI = frozenset((
    MSP_API_VERSION, MSP_FC_VARIANT, MSP_FC_VERSION, MSP_BOARD_INFO,
    MSP_BUILD_INFO, MSP_NAME, MSP_UID, MSP_STATUS, MSP_RAW_IMU, MSP_RC,
    MSP_ATTITUDE, MSP_ALTITUDE, MSP_ANALOG, MSP_BATTERY_STATE,
))
TANILAMA_SORGULARI = (
    MSP_API_VERSION, MSP_FC_VARIANT, MSP_FC_VERSION, MSP_BOARD_INFO,
    MSP_BUILD_INFO, MSP_NAME, MSP_UID,
)
CANLI_SORGULAR = (
    MSP_STATUS, MSP_RAW_IMU, MSP_ATTITUDE, MSP_ALTITUDE, MSP_ANALOG,
    MSP_BATTERY_STATE,
)
KOMUT_ADLARI = {
    MSP_API_VERSION: "API_VERSION", MSP_FC_VARIANT: "FC_VARIANT",
    MSP_FC_VERSION: "FC_VERSION", MSP_BOARD_INFO: "BOARD_INFO",
    MSP_BUILD_INFO: "BUILD_INFO", MSP_NAME: "NAME", MSP_UID: "UID",
    MSP_STATUS: "STATUS", MSP_RAW_IMU: "RAW_IMU", MSP_RC: "RC",
    MSP_ATTITUDE: "ATTITUDE", MSP_ALTITUDE: "ALTITUDE",
    MSP_ANALOG: "ANALOG", MSP_BATTERY_STATE: "BATTERY_STATE",
}


def _metin(veri: bytes) -> str:
    """NUL/dolgu baytlarını kaldırıp zararsız görünür metin döndürür."""
    return bytes(veri or b"").split(b"\x00", 1)[0].decode(
        "ascii", "replace").strip()


def _u16(veri: bytes, ofset: int = 0, varsayilan=None):
    if len(veri) < ofset + 2:
        return varsayilan
    return struct.unpack_from("<H", veri, ofset)[0]


def _i16(veri: bytes, ofset: int = 0, varsayilan=None):
    if len(veri) < ofset + 2:
        return varsayilan
    return struct.unpack_from("<h", veri, ofset)[0]


def _i32(veri: bytes, ofset: int = 0, varsayilan=None):
    if len(veri) < ofset + 4:
        return varsayilan
    return struct.unpack_from("<i", veri, ofset)[0]


def msp_v1_sorgu(komut: int) -> bytes:
    """Yalnız boş-yük MSP v1 sorgu çerçevesi üretir.

    Bu kamuya açık encoder kasıtlı olarak veri yükü almaz. Böylece MSP yazma
    komutları ya da herhangi bir ayar/motor/RC içeriği bu modül üzerinden
    üretilemez.
    """
    try:
        komut = int(komut)
    except (TypeError, ValueError):
        raise ValueError("MSP komut kimliği sayısal olmalı")
    if komut not in IZINLI_SORGU_KOMUTLARI:
        raise PermissionError("Bu MSP komutu salt-okunur izin listesinde değil")
    # $M< + payload_size(0) + command + xor(size, command)
    return b"$M<" + bytes((0, komut, komut))


class MspV1Cozucu:
    """Parçalı seri okumada MSP v1 yanıtlarını checksum ile çözer."""

    AZAMI_YUK = 256

    def __init__(self):
        self._tampon = bytearray()
        self.hatali_checksum = 0
        self.gecersiz_cerceve = 0

    def besle(self, veri: bytes):
        """`[(komut, yuk, hata_yaniti)]` listesi döndürür.

        Yalnız `$M>` başarı ve `$M!` hata yanıtları kabul edilir. Girdi yönü
        `$M<` görülürse çözücü onu atar; yerel seri hattından komut enjekte
        edilmesini işleme katmanına taşımamak için bu yön yanıt sayılmaz.
        """
        if veri:
            self._tampon.extend(veri)
        sonuc = []
        while True:
            bas = self._tampon.find(b"$M")
            if bas < 0:
                # Başlık olmadığında yalnız son iki baytı tut; olası "$M"
                # başlangıcı bir sonraki seri okumada tamamlanabilir.
                if len(self._tampon) > 2:
                    del self._tampon[:-2]
                break
            if bas:
                del self._tampon[:bas]
            if len(self._tampon) < 5:
                break
            yon = self._tampon[2]
            boy = self._tampon[3]
            komut = self._tampon[4]
            if yon not in (ord(">"), ord("!")) or boy > self.AZAMI_YUK:
                self.gecersiz_cerceve += 1
                del self._tampon[0]
                continue
            toplam = 6 + boy
            if len(self._tampon) < toplam:
                break
            paket = bytes(self._tampon[:toplam])
            del self._tampon[:toplam]
            hesap = 0
            for b in paket[3:-1]:
                hesap ^= b
            if hesap != paket[-1]:
                self.hatali_checksum += 1
                continue
            sonuc.append((komut, paket[5:-1], yon == ord("!")))
        return sonuc


def msp_veri_coz(komut: int, yuk: bytes):
    """İzinli MSP yanıtını küçük, seri hale getirilebilir tanı sözlüğüne çevirir.

    Bilinmeyen/uzatılmış Betaflight alanları yok sayılır; tam ham yanıt yerine
    yalnız sınırlı `ham_hex` tanı değeri saklanır. Bu işlev bir uçuş komutu ya
    da MAVLink telemetrisi üretmez.
    """
    komut = int(komut)
    veri = bytes(yuk or b"")
    if komut not in IZINLI_SORGU_KOMUTLARI:
        return {"ad": KOMUT_ADLARI.get(komut, str(komut)), "bilinmiyor": True}
    ad = KOMUT_ADLARI.get(komut, str(komut))
    sonuc = {"ad": ad}
    if komut == MSP_API_VERSION and len(veri) >= 3:
        sonuc.update({"protokol": int(veri[0]), "api": "%d.%d" %
                       (int(veri[1]), int(veri[2]))})
    elif komut == MSP_FC_VARIANT:
        sonuc["fc_turu"] = _metin(veri[:4])
    elif komut == MSP_FC_VERSION and len(veri) >= 3:
        sonuc["fc_surumu"] = "%d.%d.%d" % tuple(int(x) for x in veri[:3])
    elif komut == MSP_BOARD_INFO:
        sonuc["kart"] = _metin(veri[:4])
        if len(veri) >= 6:
            sonuc["kart_surumu"] = _u16(veri, 4)
        if len(veri) > 6:
            sonuc["hedef"] = _metin(veri[6:])
    elif komut == MSP_BUILD_INFO:
        # Betaflight sürümleri tarih, saat ve revizyonu değişken uzunlukta
        # döndürebilir; güvenli görünür metin işlemesi yeterlidir.
        sonuc["yapi"] = _metin(veri)
    elif komut == MSP_NAME:
        sonuc["ad"] = _metin(veri)
    elif komut == MSP_UID and len(veri) >= 12:
        sonuc["uid"] = "-".join("%08x" % struct.unpack_from("<I", veri, i)[0]
                                for i in (0, 4, 8))
    elif komut == MSP_STATUS:
        sonuc.update({"dovus_dongusu_us": _u16(veri, 0),
                       "i2c_hata": _u16(veri, 2),
                       "sensor_maskesi": _u16(veri, 4),
                       "ucus_modu_maskesi": _u32le(veri, 6),
                       "profil": (int(veri[10]) if len(veri) > 10 else None)})
    elif komut == MSP_RAW_IMU and len(veri) >= 18:
        sonuc["imu"] = {"ivme": [_i16(veri, 0), _i16(veri, 2), _i16(veri, 4)],
                          "gyro": [_i16(veri, 6), _i16(veri, 8), _i16(veri, 10)],
                          "manyeto": [_i16(veri, 12), _i16(veri, 14), _i16(veri, 16)]}
    elif komut == MSP_RC and len(veri) >= 2:
        sonuc["kanallar"] = [_u16(veri, i) for i in range(0, len(veri) - 1, 2)]
    elif komut == MSP_ATTITUDE and len(veri) >= 6:
        sonuc["tutum"] = {"roll_deg": round(_i16(veri, 0) / 10.0, 1),
                            "pitch_deg": round(_i16(veri, 2) / 10.0, 1),
                            "heading_deg": _i16(veri, 4)}
    elif komut == MSP_ALTITUDE and len(veri) >= 4:
        sonuc["irtifa_cm"] = _i32(veri, 0)
        if len(veri) >= 6:
            sonuc["dikey_hiz_cm_s"] = _i16(veri, 4)
    elif komut == MSP_ANALOG:
        if veri:
            sonuc["gerilim_v"] = round(int(veri[0]) / 10.0, 2)
        if len(veri) >= 3:
            sonuc["tuketim_mah"] = _u16(veri, 1)
        if len(veri) >= 5:
            sonuc["rssi"] = _u16(veri, 3)
    elif komut == MSP_BATTERY_STATE:
        if veri:
            sonuc["hucre_sayisi"] = int(veri[0])
        if len(veri) >= 3:
            sonuc["kapasite_mah"] = _u16(veri, 1)
        if len(veri) >= 4:
            sonuc["durum"] = int(veri[3])
    else:
        sonuc["ham_hex"] = veri[:64].hex()
    return sonuc


def _u32le(veri: bytes, ofset: int = 0, varsayilan=None):
    if len(veri) < ofset + 4:
        return varsayilan
    return struct.unpack_from("<I", veri, ofset)[0]


class BetaflightMspOturumu:
    """Bir seri/VCP portunda sınırlı MSP sorgu döngüsü yürütür."""

    def __init__(self, kayit, durum_degisti=None):
        self.kayit = dict(kayit or {})
        self.bid = int(self.kayit.get("id") or 0)
        self.port = str(self.kayit.get("port") or "").strip()
        self.baud = int(self.kayit.get("baud") or 115200)
        self._durum_degisti = durum_degisti
        self._durum_kilit = threading.Lock()
        self._durum = {
            "durum": "baglaniyor", "hata": "", "protokol": "betaflight_msp",
            "salt_okunur": True, "baglanti_id": self.bid, "port": self.port,
            "baud": self.baud, "son_veri_ts": None, "yanit_sayisi": 0,
            "bilgi": {}, "yasak_komutlar": True,
        }
        self._dur = threading.Event()
        self._is_parcacigi = None

    def baslat(self):
        if not self.port:
            self._durum_yaz("hata", "Seri port tanimli degil.")
            return False
        if self._is_parcacigi and self._is_parcacigi.is_alive():
            return True
        self._dur.clear()
        self._is_parcacigi = threading.Thread(
            target=self._calis, name="bf-msp-%s" % self.bid, daemon=True)
        self._is_parcacigi.start()
        return True

    def durdur(self, bekle=1.5):
        self._dur.set()
        if self._is_parcacigi and self._is_parcacigi.is_alive():
            self._is_parcacigi.join(timeout=float(bekle))
        self._durum_yaz("kapali", self.durum().get("hata") or "")

    def durum(self):
        with self._durum_kilit:
            return copy.deepcopy(self._durum)

    def _durum_yaz(self, durum=None, hata=None, **ek):
        with self._durum_kilit:
            if durum is not None:
                self._durum["durum"] = str(durum)
            if hata is not None:
                self._durum["hata"] = str(hata)
            self._durum.update(ek)
            kopya = copy.deepcopy(self._durum)
        if self._durum_degisti:
            try:
                self._durum_degisti(kopya)
            except Exception:
                pass

    def _calis(self):
        try:
            import serial  # pyserial: mevcut Merkez/Köprü paket bağımlılığı
        except Exception as e:
            self._durum_yaz("hata", "pyserial kullanilamiyor: %s" % e)
            return
        try:
            seri = serial.Serial(self.port, self.baud, timeout=0.20,
                                 write_timeout=1.0)
        except Exception as e:
            self._durum_yaz("hata", "MSP seri portu acilamadi: %s" % e)
            return
        cozucu = MspV1Cozucu()
        sorgular = deque(TANILAMA_SORGULARI)
        sonraki_canli = time.monotonic()
        self._durum_yaz("bagli", "")
        try:
            while not self._dur.is_set():
                simdi = time.monotonic()
                if not sorgular and simdi >= sonraki_canli:
                    sorgular.extend(CANLI_SORGULAR)
                    # 1 Hz sorgu turu; beklemeyen hızlı seri döngü yoktur.
                    sonraki_canli = simdi + 1.0
                if sorgular:
                    komut = sorgular.popleft()
                    # Yalnız msp_v1_sorgu() çağrısı yazabilir; izin listesi
                    # burada ikinci kez zorlanır.
                    if komut not in IZINLI_SORGU_KOMUTLARI:
                        raise PermissionError("Izin disi MSP sorgusu engellendi")
                    seri.write(msp_v1_sorgu(komut))
                    seri.flush()
                ham = seri.read(256)
                for komut, yuk, hata_yaniti in cozucu.besle(ham):
                    if komut not in IZINLI_SORGU_KOMUTLARI:
                        continue
                    if hata_yaniti:
                        self._durum_yaz("bagli", "MSP hata yaniti: %s" %
                                        KOMUT_ADLARI.get(komut, komut))
                        continue
                    parca = msp_veri_coz(komut, yuk)
                    with self._durum_kilit:
                        bilgi = dict(self._durum.get("bilgi") or {})
                        bilgi[str(komut)] = parca
                        yanit = int(self._durum.get("yanit_sayisi") or 0) + 1
                    self._durum_yaz("bagli", "", bilgi=bilgi,
                                    son_veri_ts=time.time(), yanit_sayisi=yanit,
                                    son_sorgu=KOMUT_ADLARI.get(komut, str(komut)),
                                    hatali_checksum=cozucu.hatali_checksum)
        except Exception as e:
            self._durum_yaz("hata", "MSP okuma/sorgu hatasi: %s" % e)
        finally:
            try:
                seri.close()
            except Exception:
                pass


class BetaflightMspYonetici:
    """Bağlantı kimliği başına salt-okunur MSP oturumlarını yönetir."""

    def __init__(self, konsol=None):
        self.konsol = konsol or (lambda *a, **k: None)
        self._kilit = threading.Lock()
        self._oturumlar = {}

    @staticmethod
    def _dogrula(kayit):
        if str((kayit or {}).get("ucus_yazilimi") or "").lower() != "betaflight":
            return "Betaflight MSP oturumu icin ucus yazilimi betaflight olmali."
        if str((kayit or {}).get("tur") or "").lower() != "seri":
            return "Betaflight ilk surumde yalniz seri/VCP portunda desteklenir."
        if not str((kayit or {}).get("port") or "").strip():
            return "Betaflight seri portu bos olamaz."
        return None

    def baslat(self, kayit):
        hata = self._dogrula(kayit)
        if hata:
            return False, hata
        bid = int(kayit.get("id") or 0)
        if not bid:
            return False, "Baglanti kimligi gecersiz."
        self.durdur(bid)
        oturum = BetaflightMspOturumu(kayit)
        with self._kilit:
            self._oturumlar[bid] = oturum
        oturum.baslat()
        self.konsol("BETAFIGHT", "Salt-okunur MSP baslatildi: %s" %
                    (kayit.get("isim") or bid), "bilgi")
        return True, None

    def durdur(self, baglanti_id):
        try:
            bid = int(baglanti_id)
        except (TypeError, ValueError):
            return
        with self._kilit:
            oturum = self._oturumlar.pop(bid, None)
        if oturum:
            oturum.durdur()
            self.konsol("BETAFIGHT", "MSP durduruldu: id=%s" % bid, "bilgi")

    def durumlar(self):
        with self._kilit:
            oturumlar = list(self._oturumlar.items())
        return {str(bid): oturum.durum() for bid, oturum in oturumlar}

    def kapat(self):
        with self._kilit:
            kimlikler = list(self._oturumlar)
        for bid in kimlikler:
            self.durdur(bid)
