#!/usr/bin/env python3
"""v2.4.37 dogrulamasi: "Itki / Motor" maddesi kaldirildi mi ve temiz
telemetride uyari sayisi gercekten 0 oluyor mu?

NEDEN VAR: madde kaldirmak tek satirlik bir islem gibi gorunur, ama
gerekcesi "hazirlik_ozeti() artik temiz dronda uyari uretmesin" idi. Bu
sonucu olcmeden madde silinmis olabilir ve baska bir madde ayni kalici
uyariyi uretmeye devam edebilir. Bu betik SONUCU olcer, satiri degil.

Kullanim: goktungu kok dizininde  ->  python3 dogrula_2437_itki.py
"""
import os
import sys
import time

sys.path.insert(0, os.getcwd())

from goktungu.dron import (  # noqa: E402
    DronYoneticisi, SENSOR_GYRO, SENSOR_ACCEL, SENSOR_MAG, SENSOR_BARO,
    SENSOR_GPS, SENSOR_AHRS, SENSOR_BATTERY, SENSOR_RC, SENSOR_PREARM,
    SENSOR_PROPULSION,
    EKF_ATTITUDE, EKF_VELOCITY_HORIZ, EKF_VELOCITY_VERT,
    EKF_POS_HORIZ_REL, EKF_POS_HORIZ_ABS, EKF_POS_VERT_ABS,
    EKF_POS_VERT_AGL, EKF_PRED_POS_HORIZ_REL, EKF_PRED_POS_HORIZ_ABS,
)

# Saglikli bir EKF cozumu: tum yetenek bayraklari set, CONST_POS_MODE ve
# UNINITIALIZED bayraklari YOK. 0xFFFF gibi "hepsi bir" bir deger
# kullanilamaz; o deger UNINITIALIZED'i de set eder ve EKF maddesi
# "baslatilmadi" diye hata verir.
EKF_SAGLIKLI = (EKF_ATTITUDE | EKF_VELOCITY_HORIZ | EKF_VELOCITY_VERT |
                EKF_POS_HORIZ_REL | EKF_POS_HORIZ_ABS | EKF_POS_VERT_ABS |
                EKF_POS_VERT_AGL | EKF_PRED_POS_HORIZ_REL |
                EKF_PRED_POS_HORIZ_ABS)

gecti = 0
kaldi = 0


def denetle(ad, kosul, ayrinti=""):
    global gecti, kaldi
    if kosul:
        gecti += 1
        print(f"[GECTI     ] {ad}" + (f"  ({ayrinti})" if ayrinti else ""))
    else:
        kaldi += 1
        print(f"[KALDI     ] {ad}" + (f"  ({ayrinti})" if ayrinti else ""))


y = DronYoneticisi.__new__(DronYoneticisi)

# ArduPilot'un GERCEKTE yaydigi bit kumesi. PROPULSION biti bilincli
# olarak YOK: sahadaki durum bu.
ARDUPILOT_BITLERI = (SENSOR_GYRO | SENSOR_ACCEL | SENSOR_MAG | SENSOR_BARO |
                     SENSOR_GPS | SENSOR_AHRS | SENSOR_BATTERY | SENSOR_RC |
                     SENSOR_PREARM)


def temiz_telemetri():
    """Her yonuyle saglikli, kalkisa hazir bir arac."""
    return {
        "sensor_mevcut": ARDUPILOT_BITLERI,
        "sensor_saglik": ARDUPILOT_BITLERI,
        "sensor_etkin": ARDUPILOT_BITLERI,
        "gps_fix": 6, "uydu": 18, "hdop": 0.8,
        "batarya_v": 24.6, "batarya_pct": 96,
        "ekf_bayrak": EKF_SAGLIKLI,
        "titresim": 8.0,
        "sistem_durum": 3,          # MAV_STATE_STANDBY
        "son_mesaj": time.time(),   # telemetri taze
    }


d = temiz_telemetri()
maddeler = y.hazirlik_maddeleri(d)
anahtarlar = [m["anahtar"] for m in maddeler]

print("=" * 60)
print("v2.4.37 — Itki / Motor maddesi dogrulamasi")
print("=" * 60)

denetle("motor maddesi listeden kalkti",
        "motor" not in anahtarlar,
        f"{len(maddeler)} madde")

denetle("Itki / Motor adi hicbir maddede gecmiyor",
        not any("İtki" in m["ad"] or "Itki" in m["ad"] for m in maddeler))

guc = [m for m in maddeler if m["grup"] == "guc"]
denetle("guc grubu bos kalmadi", len(guc) > 0,
        ", ".join(m["anahtar"] for m in guc))

denetle("guc grubunda batarya maddesi duruyor",
        any(m["anahtar"] == "batarya" for m in guc))

# ASIL OLCUM: temiz telemetride hicbir uyari kalmamali.
ozet = y.hazirlik_ozeti(d)
uyarili = [(m["anahtar"], m["deger"]) for m in maddeler
           if m["durum"] == "uyari"]
kritikli = [(m["anahtar"], m["deger"]) for m in maddeler
            if m["durum"] == "hata"]

denetle("temiz telemetride hazir=True", ozet["hazir"] is True,
        f"hazir={ozet['hazir']}")
denetle("temiz telemetride kritik yok", ozet["kritik"] == 0,
        str(kritikli) if kritikli else "0")
denetle("temiz telemetride UYARI YOK (asil kazanim)",
        ozet["uyari"] == 0,
        str(uyarili) if uyarili else "0")

# PROPULSION biti YAYILSA bile davranis degismemeli: madde artik yok,
# yani biti yayan bir ucus yazilimi da ek uyari uretmemeli.
d2 = temiz_telemetri()
d2["sensor_mevcut"] |= SENSOR_PROPULSION
d2["sensor_saglik"] |= SENSOR_PROPULSION
ozet2 = y.hazirlik_ozeti(d2)
denetle("PROPULSION biti gelse de uyari uretmiyor",
        ozet2["uyari"] == 0 and ozet2["hazir"] is True,
        f"uyari={ozet2['uyari']}")

# Gercek bir arizada sistem HALA uyarabilmeli: madde kaldirmak
# hazirlik denetimini kormus olmamali.
d3 = temiz_telemetri()
d3["sensor_saglik"] &= ~SENSOR_MAG      # pusula arizali
ozet3 = y.hazirlik_ozeti(d3)
denetle("gercek ariza hala yakalaniyor (pusula)",
        ozet3["hazir"] is False and ozet3["kritik"] > 0,
        f"hazir={ozet3['hazir']} kritik={ozet3['kritik']}")

# Zorunlu olmayan madde (RC) bit yoksa uyari uretmemeli — motor
# maddesinin dustugu tuzagin baskasinda tekrarlamadigini gosterir.
d4 = temiz_telemetri()
d4["sensor_mevcut"] &= ~SENSOR_RC
d4["sensor_saglik"] &= ~SENSOR_RC
ozet4 = y.hazirlik_ozeti(d4)
denetle("RC biti yoksa uyari uretilmiyor (zorunlu=False)",
        ozet4["uyari"] == 0,
        f"uyari={ozet4['uyari']}")

print("=" * 60)
print(f"SONUC: {gecti}/{gecti + kaldi} gecti")
print("=" * 60)
sys.exit(1 if kaldi else 0)
