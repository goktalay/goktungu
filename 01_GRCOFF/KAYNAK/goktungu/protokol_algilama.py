# -*- coding: utf-8 -*-
"""GÖKTUNGU — Seri/RFD900 otomatik MAVLink veya MSP algılayıcı.

Algılayıcı bir seri portu kısa süreliğine TEK BAŞINA açar. Önce hiçbir veri
iletmeden geçerli CRC'li MAVLink HEARTBEAT dinler. Bu kanıt yoksa yalnız
Betaflight'ın salt-okunur MSP_API_VERSION sorgusunu gönderir. ARM, motor,
RC, yapılandırma, reboot, CLI veya başka bir MSP/MAVLink komutu üretmez.
"""
from __future__ import annotations

import time

from .betaflight_msp import MSP_API_VERSION, MspV1Cozucu, msp_v1_sorgu

_MAVLINK_HEARTBEAT = 0
_MAVLINK_HEARTBEAT_CRC_EXTRA = 50


def _x25_bayt(crc, bayt):
    """MAVLink X.25 CRC güncellemesi."""
    tmp = (int(bayt) ^ (crc & 0xFF)) & 0xFF
    tmp = (tmp ^ ((tmp << 4) & 0xFF)) & 0xFF
    return ((crc >> 8) ^ (tmp << 8) ^ (tmp << 3) ^ (tmp >> 4)) & 0xFFFF


def _x25(veri, extra):
    crc = 0xFFFF
    for bayt in bytes(veri or b""):
        crc = _x25_bayt(crc, bayt)
    return _x25_bayt(crc, extra)


def _mavlink_heartbeat_var_mi(tampon):
    """Tampondaki geçerli MAVLink v1/v2 HEARTBEAT çerçevesini bulur.

    Sadece mesaj kimliği 0 ve doğrulanmış CRC kabul edilir. Geçersiz veya
    başka MAVLink mesajları protokol kanıtı sayılmaz; bu sayede rastgele
    seri gürültüsü yanlış ArduPilot sonucu üretemez.
    """
    veri = bytearray(tampon or b"")
    i = 0
    while i < len(veri):
        stx = veri[i]
        if stx not in (0xFE, 0xFD):
            i += 1
            continue
        if stx == 0xFE:
            if len(veri) - i < 8:
                break
            yuk_boy = int(veri[i + 1])
            toplam = 8 + yuk_boy
            if len(veri) - i < toplam:
                break
            mesaj_id = int(veri[i + 5])
            crc_veri = veri[i + 1:i + 6 + yuk_boy]
            crc_ofset = i + 6 + yuk_boy
            crc_alinan = int(veri[crc_ofset]) | (int(veri[crc_ofset + 1]) << 8)
            if mesaj_id == _MAVLINK_HEARTBEAT and _x25(
                    crc_veri, _MAVLINK_HEARTBEAT_CRC_EXTRA) == crc_alinan:
                return True
            i += toplam
            continue
        # MAVLink v2: STX, 9 bayt baslik, yuk, CRC ve imzaliysa 13 bayt imza.
        if len(veri) - i < 12:
            break
        yuk_boy = int(veri[i + 1])
        uyumsuz = int(veri[i + 2])
        temel = 12 + yuk_boy
        toplam = temel + (13 if (uyumsuz & 0x01) else 0)
        if len(veri) - i < toplam:
            break
        mesaj_id = (int(veri[i + 7]) | (int(veri[i + 8]) << 8) |
                    (int(veri[i + 9]) << 16))
        crc_veri = veri[i + 1:i + 10 + yuk_boy]
        crc_ofset = i + 10 + yuk_boy
        crc_alinan = int(veri[crc_ofset]) | (int(veri[crc_ofset + 1]) << 8)
        if mesaj_id == _MAVLINK_HEARTBEAT and _x25(
                crc_veri, _MAVLINK_HEARTBEAT_CRC_EXTRA) == crc_alinan:
            return True
        i += toplam
    return False


def _seri_oku(seri, en_az=1):
    """PySerial ve test çiftlerinde güvenli, sınırlı okuma yapar."""
    try:
        bekleyen = int(getattr(seri, "in_waiting", 0) or 0)
    except Exception:
        bekleyen = 0
    try:
        return bytes(seri.read(max(int(en_az), min(1024, bekleyen or 1))) or b"")
    except Exception:
        return b""


def seri_protokol_algila(kayit, mavlink_sure=2.5, msp_sure=1.2,
                          seri_sinifi=None, zaman=None):
    """Seri/RFD900 bağlantısının uçuş yazılımını güvenli biçimde belirler.

    Dönüş sözlüğü yalnız `ardupilot`, `betaflight` veya `bilinmiyor` sonucu
    taşır. Port, sonuç ne olursa olsun bu yordam sonunda kapatılır; gerçek
    MAVLink veya MSP oturumu portu algılama tamamlandıktan sonra yeniden açar.
    """
    kayit = dict(kayit or {})
    if str(kayit.get("tur") or "").lower() != "seri":
        return {"tamam": False, "protokol": "bilinmiyor",
                "hata": "Otomatik protokol algilama yalniz seri/RFD900 baglantida kullanilir."}
    port = str(kayit.get("port") or "").strip()
    if not port:
        return {"tamam": False, "protokol": "bilinmiyor",
                "hata": "Seri port bos olamaz."}
    try:
        baud = int(kayit.get("baud") or 57600)
    except (TypeError, ValueError):
        baud = 57600
    saat = zaman or time.monotonic
    if seri_sinifi is None:
        try:
            import serial
            seri_sinifi = serial.Serial
        except Exception as e:
            return {"tamam": False, "protokol": "bilinmiyor",
                    "hata": "Seri istemcisi kullanilamiyor: %s" % e}
    try:
        seri = seri_sinifi(port=port, baudrate=baud, timeout=0.08,
                           write_timeout=1)
    except Exception as e:
        return {"tamam": False, "protokol": "bilinmiyor",
                "hata": "Seri port acilamadi (%s): %s" % (port, e)}
    try:
        try:
            seri.reset_input_buffer()
        except Exception:
            pass
        tampon = bytearray()
        son = saat() + max(0.2, float(mavlink_sure))
        while saat() < son:
            parca = _seri_oku(seri)
            if parca:
                tampon.extend(parca)
                if _mavlink_heartbeat_var_mi(tampon):
                    return {"tamam": True, "protokol": "ardupilot",
                            "kanit": "mavlink_heartbeat", "port": port,
                            "baud": baud}
        # MAVLink kaniti yoksa yalnız MSP API_VERSION sorgusu yapılır.
        try:
            seri.reset_input_buffer()
        except Exception:
            pass
        try:
            seri.write(msp_v1_sorgu(MSP_API_VERSION))
            seri.flush()
        except Exception as e:
            return {"tamam": False, "protokol": "bilinmiyor",
                    "hata": "MSP API_VERSION sorgusu gonderilemedi: %s" % e}
        cozu = MspV1Cozucu()
        son = saat() + max(0.2, float(msp_sure))
        while saat() < son:
            for komut, yuk, hata_yaniti in cozu.besle(_seri_oku(seri)):
                if (komut == MSP_API_VERSION and not hata_yaniti and
                        len(yuk) >= 3):
                    return {"tamam": True, "protokol": "betaflight",
                            "kanit": "msp_api_version", "port": port,
                            "baud": baud, "msp_api": "%d.%d" %
                            (int(yuk[1]), int(yuk[2]))}
        return {"tamam": False, "protokol": "bilinmiyor",
                "hata": ("MAVLink HEARTBEAT veya Betaflight MSP API_VERSION "
                         "yaniti alinmadi. RFD900/seri hat, baud hizi ve FC "
                         "uzerindeki MSP ayarini kontrol edin.")}
    finally:
        try:
            seri.close()
        except Exception:
            pass
