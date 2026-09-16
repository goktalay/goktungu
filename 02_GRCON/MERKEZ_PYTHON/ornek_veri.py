# -*- coding: utf-8 -*-
"""Merkez paneli doğrulaması için gerçekçi örnek veri üretir.

Üretilen kayıtlar `ORNEK-` önekli vergi numarası ile işaretlenir;
`--sil` ile tümü (bağlı kayıtlarla birlikte) kaldırılır. Böylece gerçek
müşteri verisiyle karışmaz.
"""
from __future__ import annotations

import datetime as dt
import math
import random
import sys

import mk_api as api
import mk_db as db

ISARET = "ORNEK-"

FIRMALAR = [
    ("Türkbey Teknoloji Anonim Şirketi", "TÜRKBEY", "Ankara, Sincan",
     "kurumsal", 25, 8, 39.95, 32.58),
    ("Türkbey Teknoloji A.Ş.", "TÜRKBEY", "Ankara, Sincan",
     "kurumsal", 20, 6, 39.97, 32.62),
    ("Anadolu Tarım Havacılık Ltd.", "ANADOLU", "Konya, Selçuklu",
     "standart", 10, 3, 37.87, 32.49),
    ("Ege Enerji Denetim A.Ş.", "EGE", "İzmir, Bornova",
     "deneme", 6, 2, 38.46, 27.21),
]

PILOTLAR = [
    ("Muhammed", "Kaderoglu", "firma_yonetici"),
    ("Ahmet", "Yilmaz", "pilot"),
    ("Elif", "Demir", "pilot"),
    ("Burak", "Sahin", "pilot"),
    ("Zeynep", "Kaya", "gozlemci"),
]

DRONLAR = [
    ("GÖKTUNGU VTOL-1", "vtol", "ArduPlane", 1),
    ("GÖKGÖZ Q-450", "multirotor", "ArduCopter", 2),
    ("İlaçlama H-20", "multirotor", "ArduCopter", 3),
]

MODLAR = ["GUIDED", "AUTO", "LOITER", "RTL", "ALT_HOLD"]
GOREVLER = ["kesif", "koridor", "ilaclama", "denetim"]


def sil() -> int:
    n = db.calistir("DELETE FROM firmalar WHERE vergi_no LIKE %s",
                    (ISARET + "%",))
    print(f"Ornek firma silindi: {n} (bagli kayitlar CASCADE ile gitti)")
    return 0


def _telemetri(ucus_id: int, lat0: float, lon0: float,
               bas: dt.datetime, sure_sn: int) -> int:
    """Dairesel görev rotası boyunca örnek telemetri üretir."""
    hedef_ornek = 120
    adim = max(1, sure_sn // hedef_ornek)
    n = max(2, sure_sn // adim)
    ornekler = []
    for i in range(n):
        oran = i / (n - 1)
        aci = oran * 2 * math.pi
        lat = lat0 + 0.008 * math.sin(aci)
        lon = lon0 + 0.010 * math.cos(aci)
        if oran < 0.1:
            irtifa = 120 * (oran / 0.1)
        elif oran > 0.9:
            irtifa = 120 * ((1 - oran) / 0.1)
        else:
            irtifa = 120 + 15 * math.sin(aci * 3)
        hiz = 0.0 if (oran < 0.05 or oran > 0.95) else 14 + 4 * math.sin(aci * 2)
        ornekler.append({
            "ts": (bas + dt.timedelta(seconds=i * adim)).isoformat(),
            "lat": round(lat, 7), "lon": round(lon, 7),
            "irtifa_m": round(irtifa, 1), "hiz_ms": round(hiz, 2),
            "yon_derece": round((math.degrees(aci) + 90) % 360, 1),
            "batarya_v": round(25.2 - 3.6 * oran, 2),
            "batarya_yuzde": int(100 - 62 * oran),
            "uydu_sayisi": random.randint(14, 21),
            "mod": random.choice(MODLAR),
        })
    return api.telemetri_yaz(ucus_id, ornekler)


def _eposta(ad: str, soyad: str, kisa: str) -> str:
    return f"{ad.lower()}.{soyad.lower()}.{kisa.lower()}@ornek.local"


def uret() -> int:
    random.seed(20260813)
    simdi = dt.datetime.now(dt.timezone.utc)
    ozet = {"firma": 0, "kullanici": 0, "sunucu": 0, "ucus": 0,
            "telemetri": 0, "video": 0}

    for sira, (unvan, kisa, adres, abonelik, maks_k, maks_s, lat0, lon0) in \
            enumerate(FIRMALAR):
        fid, hata = api.firma_ekle({
            "unvan": unvan, "kisa_ad": kisa, "adres": adres,
            "vergi_no": f"{ISARET}{1000 + sira}", "vergi_dairesi": "Merkez",
            "telefon": f"+90 312 000 {10 + sira:02d}",
            "eposta": f"bilgi@{kisa.lower()}.example",
            "abonelik": abonelik, "maks_kullanici": maks_k,
            "maks_sunucu": maks_s, "ulke": "TR",
        })
        if hata:
            print(f"  [ATLA] firma {unvan}: {hata}")
            continue
        ozet["firma"] += 1

        pilotlar: list[tuple[str, str]] = []
        for ad, soyad, rol in PILOTLAR:
            ep = _eposta(ad, soyad, kisa)
            kid, hata = api.kullanici_ekle({
                "firma_id": fid, "eposta": ep, "sifre": "Ornek2026!",
                "ad": ad, "soyad": soyad, "rol": rol,
                "telefon": f"+90 5{random.randint(300000000, 399999999)}",
                "lisans_no": f"SHGM-{random.randint(10000, 99999)}",
            })
            if hata:
                print(f"  [ATLA] kullanici {ep}: {hata}")
                continue
            ozet["kullanici"] += 1
            if rol in ("firma_yonetici", "pilot"):
                pilotlar.append((ep, f"{ad} {soyad}"))
        if not pilotlar:
            continue

        s_veri, hata = api.sunucu_ekle(fid, f"{kisa} Saha Sunucusu",
                                       "Örnek kurulum")
        ornek_id = None
        if not hata and s_veri:
            ornek_id = int(s_veri["ornek_id"])
            ozet["sunucu"] += 1
            db.calistir(
                "UPDATE sunucu_ornekleri SET surum = %s, platform = %s, "
                "makine_adi = %s WHERE ornek_id = %s",
                ("2.4.52", "linux", f"{kisa.lower()}-gcs", ornek_id))
        else:
            print(f"  [ATLA] sunucu {kisa}: {hata}")

        dron_sayisi = 3 if sira < 2 else 2
        for d_sira, (d_ad, tur, otopilot, sysid) in \
                enumerate(DRONLAR[:dron_sayisi]):
            for u_sira in range(random.randint(2, 4)):
                ep, pilot_ad = random.choice(pilotlar)
                gun_once = random.randint(0, 13)
                bas = simdi - dt.timedelta(days=gun_once,
                                           hours=random.randint(0, 9))
                sure = random.randint(420, 2100)
                u_uid = f"{ISARET}{kisa[:3]}{d_sira}{u_sira}{gun_once:02d}"
                d_lat, d_lon = lat0 + d_sira * 0.02, lon0 + d_sira * 0.02
                ucus_id, hata = api.ucus_yaz(fid, {
                    "ucus_uid": u_uid,
                    "baslangic_ts": bas.isoformat(),
                    "bitis_ts": (bas + dt.timedelta(seconds=sure)).isoformat(),
                    "sure_sn": sure,
                    "pilot_eposta": ep, "pilot_ad": pilot_ad,
                    "dron_uid": f"{kisa[:3]}-{sysid}",
                    "dron_ad": d_ad, "arac_turu": tur, "otopilot": otopilot,
                    "sysid": sysid, "seri_no": f"SN-{sira}{d_sira}{sysid:02d}",
                    "maks_irtifa_m": round(random.uniform(95, 145), 1),
                    "maks_hiz_ms": round(random.uniform(15, 24), 1),
                    "mesafe_m": round(sure * random.uniform(9, 14), 1),
                    "kalkis_lat": round(d_lat, 7), "kalkis_lon": round(d_lon, 7),
                    "inis_lat": round(d_lat, 7), "inis_lon": round(d_lon, 7),
                    "gorev_turu": random.choice(GOREVLER),
                    "gorev_durumu": "tamamlandi",
                    "kalkis_kontrol": {"pervane": True, "servo": True,
                                       "gps": True, "pilot": pilot_ad,
                                       "ts": bas.isoformat()},
                    "ozet": {"ruzgar_knot": random.randint(3, 14),
                             "sicaklik_c": random.randint(12, 34)},
                }, ornek_id)
                if hata or not ucus_id:
                    print(f"  [ATLA] ucus {u_uid}: {hata}")
                    continue
                ozet["ucus"] += 1
                ozet["telemetri"] += _telemetri(int(ucus_id), d_lat, d_lon,
                                                bas, sure)

                if random.random() < 0.7:
                    _, hata = api.video_yaz(fid, {
                        "video_uid": "V" + u_uid,
                        "ucus_uid": u_uid,
                        "pilot_eposta": ep,
                        "baslik": f"{d_ad} — görev kaydı",
                        "kaynak": random.choice(["gimbal", "fpv", "termal"]),
                        "baslangic_ts": bas.isoformat(),
                        "bitis_ts": (bas + dt.timedelta(
                            seconds=sure)).isoformat(),
                        "sure_sn": sure,
                        "boyut_bayt": sure * random.randint(180000, 420000),
                        "cozunurluk": random.choice(
                            ["1920x1080", "2560x1440", "3840x2160"]),
                        "kodek": "h264", "depo_yeri": "yerel",
                        "yerel_yol": f"veri/video/{u_uid}.mp4",
                        "durum": "hazir",
                    }, ornek_id)
                    if hata:
                        print(f"  [ATLA] video {u_uid}: {hata}")
                    else:
                        ozet["video"] += 1

    print("Uretilen ornek veri:")
    for a, d in ozet.items():
        print(f"  {a:<10}: {d}")
    print(f"  {'dron':<10}: {db.deger('SELECT count(*) FROM dronlar')}")
    return 0


if __name__ == "__main__":
    sys.exit(sil() if "--sil" in sys.argv[1:] else uret())
