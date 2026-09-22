# -*- coding: utf-8 -*-
"""GOKTUNGU KOPRU — Betaflight MSP + protokol algilama sinavi (Faz 5).

Dogrular:
  1) MAVLink yolu KORUNUR: gecerli HEARTBEAT -> 'ardupilot'.
  2) Betaflight yolu EKLENDI: MSP_API_VERSION yaniti -> 'betaflight'.
  3) SALT-OKUNUR: yazma komutu (MSP_SET_RAW_RC=200) reddedilir.
  4) MSP cozucu bir yaniti dogru cozer.
  5) DronServisi protokol soyutlama komutlari dogru yonlenir.

Seri donanim gerekmez: enjekte edilen sahte seri sinifi kullanilir.
"""
import os
import sys

KOK = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..",
    "03_BRDIMG", "ORTAK_KOPRU_KAYNAGI"))
sys.path.insert(0, KOK)

from kopru import betaflight_msp as BF          # noqa: E402
from kopru import protokol_algilama as PA       # noqa: E402
from kopru import servis_dron as SD             # noqa: E402

_gecen = 0
_kalan = 0


def d(baslik, kosul, neden=""):
    global _gecen, _kalan
    if kosul:
        _gecen += 1
        print("  [GECTI] %s" % baslik)
    else:
        _kalan += 1
        print("  [KALDI] %s%s" % (baslik, (" — %s" % neden) if neden else ""))


def _msp_yanit(cmd, payload):
    govde = bytes((len(payload), cmd)) + payload
    crc = 0
    for b in govde:
        crc ^= b
    return b"$M>" + govde + bytes((crc,))


def _mavlink_heartbeat():
    payload = bytes(9)  # 9 baytlik HEARTBEAT yuku
    govde = bytes((len(payload), 0, 1, 1, 0)) + payload  # len,seq,sys,comp,id=0
    crc = PA._x25(govde, 50)
    return b"\xFE" + govde + bytes((crc & 0xFF, (crc >> 8) & 0xFF))


class SahteSeri:
    """Yalniz algilama testinde: reset no-op, write -> yaniti tampona ekler."""

    def __init__(self, port=None, baudrate=None, timeout=None,
                 write_timeout=None, **k):
        self._kaynak = bytearray()
        self._yanit = b""

    @property
    def in_waiting(self):
        return len(self._kaynak)

    def read(self, n=1):
        n = max(0, int(n))
        parca = bytes(self._kaynak[:n])
        del self._kaynak[:n]
        return parca

    def write(self, veri):
        self._kaynak.extend(self._yanit)
        return len(veri)

    def flush(self):
        pass

    def reset_input_buffer(self):
        pass

    def close(self):
        pass


def sinav_mavlink_korunur():
    print("\n--- 1) MAVLink (ArduPilot) yolu KORUNUR ---")

    def yap(port=None, **k):
        s = SahteSeri()
        s._kaynak.extend(_mavlink_heartbeat())
        return s

    sonuc = PA.seri_protokol_algila(
        {"tur": "seri", "port": "/dev/ttyUSB0", "baud": 57600},
        mavlink_sure=0.4, msp_sure=0.2, seri_sinifi=yap)
    d("HEARTBEAT -> ardupilot", sonuc.get("protokol") == "ardupilot",
      "gelen: %s" % sonuc)
    d("kanit mavlink_heartbeat", sonuc.get("kanit") == "mavlink_heartbeat")


def sinav_betaflight_eklendi():
    print("\n--- 2) Betaflight (MSP) yolu EKLENDI ---")

    def yap(port=None, **k):
        s = SahteSeri()
        # HEARTBEAT yok; MSP_API_VERSION sorgusu yazilinca yanit gelir.
        s._yanit = _msp_yanit(BF.MSP_API_VERSION, bytes((1, 1, 46)))
        return s

    sonuc = PA.seri_protokol_algila(
        {"tur": "seri", "port": "/dev/ttyUSB0", "baud": 115200},
        mavlink_sure=0.2, msp_sure=0.6, seri_sinifi=yap)
    d("MSP_API_VERSION -> betaflight", sonuc.get("protokol") == "betaflight",
      "gelen: %s" % sonuc)
    d("msp_api okundu", sonuc.get("msp_api") == "1.46", "gelen: %s" % sonuc)


def sinav_salt_okunur():
    print("\n--- 3) SALT-OKUNUR: yazma komutu reddedilir ---")
    # Izinli salt-okunur sorgu cerceve uretir.
    try:
        cer = BF.msp_v1_sorgu(BF.MSP_STATUS)
        d("izinli sorgu cercevesi uretilir", cer.startswith(b"$M<"))
    except Exception as e:
        d("izinli sorgu cercevesi uretilir", False, str(e))
    # MSP_SET_RAW_RC = 200 (yazma). Surucu bunu reddetmeli.
    try:
        BF.msp_v1_sorgu(200)
        d("yazma komutu (200) reddedilir", False, "istisna atilmadi")
    except PermissionError:
        d("yazma komutu (200) reddedilir (PermissionError)", True)
    except Exception as e:
        d("yazma komutu (200) reddedilir", False,
          "beklenmeyen istisna: %s" % e)
    # Izin listesi yazma komutlarini icermemeli.
    d("200 izin listesinde YOK", 200 not in BF.IZINLI_SORGU_KOMUTLARI)
    d("ARM/SET komutlari izinli degil",
      all(c not in BF.IZINLI_SORGU_KOMUTLARI for c in (200, 205, 68, 214)))


def sinav_cozucu():
    print("\n--- 4) MSP cozucu round-trip ---")
    cer = _msp_yanit(BF.MSP_FC_VARIANT, b"BTFL")
    cozucu = BF.MspV1Cozucu()
    cikan = cozucu.besle(cer)
    d("bir yanit cozuldu", len(cikan) == 1, "gelen: %s" % cikan)
    if cikan:
        komut, yuk, hata = cikan[0]
        d("komut FC_VARIANT", komut == BF.MSP_FC_VARIANT)
        d("hata yaniti degil", hata is False)
        coz = BF.msp_veri_coz(komut, yuk)
        d("fc_turu BTFL", coz.get("fc_turu") == "BTFL", "gelen: %s" % coz)
    # Bozuk checksum sayilir.
    bozuk = cer[:-1] + bytes((cer[-1] ^ 0xFF,))
    c2 = BF.MspV1Cozucu()
    d("bozuk checksum atilir", c2.besle(bozuk) == [] and c2.hatali_checksum == 1)


def sinav_dron_komut_soyutlamasi():
    print("\n--- 5) DronServisi protokol komut yonlendirmesi ---")
    srv = SD.DronServisi()
    # protokol_algila komutu: sahte seri ile ardupilot.
    _orij = PA.seri_protokol_algila
    try:
        PA.seri_protokol_algila = lambda kayit, **k: {
            "tamam": True, "protokol": "ardupilot", "port": kayit.get("port")}
        tamam, hata, veri = srv._komut_uygula(
            "protokol_algila", {"port": "/dev/ttyUSB0", "baud": 57600})
        d("protokol_algila komutu -> ardupilot",
          tamam and veri.get("protokol") == "ardupilot", "veri: %s" % veri)
    finally:
        PA.seri_protokol_algila = _orij
    # msp_durum: MSP yoneticisi henuz kurulmamis -> bos oturum, hatasiz.
    tamam, hata, veri = srv._komut_uygula("msp_durum", {})
    d("msp_durum bos oturum dondurur",
      tamam and veri.get("oturumlar") == {}, "veri: %s" % veri)
    # Bilinmeyen komut reddedilir.
    tamam, hata, veri = srv._komut_uygula("ucur", {})
    d("bilinmeyen komut reddedilir", tamam is False and "Bilinmeyen" in hata)
    # msp_baslat portsuz -> dogrulama hatasi (yazma yok, guvenli).
    tamam, hata, veri = srv._komut_uygula(
        "msp_baslat", {"id": 1, "ucus_yazilimi": "betaflight", "tur": "seri"})
    d("msp_baslat portsuz reddedilir", tamam is False and bool(hata),
      "hata: %s" % hata)
    d("PROTOKOLLER sabiti dogru",
      SD.PROTOKOLLER == ("ardupilot", "betaflight", "bilinmiyor"))


def main():
    print("=" * 62)
    print(" BETAFLIGHT MSP + PROTOKOL ALGILAMA SINAVI (Faz 5)")
    print("=" * 62)
    sinav_mavlink_korunur()
    sinav_betaflight_eklendi()
    sinav_salt_okunur()
    sinav_cozucu()
    sinav_dron_komut_soyutlamasi()
    print("\nSONUC: %d gecti / %d kaldi" % (_gecen, _kalan))
    return 1 if _kalan else 0


if __name__ == "__main__":
    sys.exit(main())
