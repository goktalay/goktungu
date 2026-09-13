#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GOKTUNGU v2.4.43 - KESISME (INTERCEPT) MATEMATIGI SINAVI

Bu sinav SITL gerektirmez: angajman.py icindeki saf fonksiyonlari
dogrudan cagirip matematigi olcer.

Sinanan sorular:
  1. Durgun hedefte kesisme suresi = mesafe / hiz olmali.
  2. Kacan hedefte (hedef daha hizli) cozum OLMAMALI (None).
  3. Yandan gecen hedefte cozum olmali ve kestirme acisi > 0 olmali.
  4. Kesisme noktasi gercekten kesisme olmali: hedef t sn sonra ORADA
     olmali VE saldiran t sn sonra oraya VARABILMELI (iki yol da t*hiz).
  5. Kesisme yolu, saf takip yolundan KISA olmali (asil iddia).
  6. Gorev bacagi ongorusu: konum tasimayan komutlar atlanmali,
     x=y=0 tuzagina dusmemeli.
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "goktungu"))

from goktungu import angajman as A  # noqa: E402

GECEN = 0
KALAN = 0


def olc(ad, kosul, detay=""):
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print("  [GECTI ] %-52s %s" % (ad, detay))
    else:
        KALAN += 1
        print("  [KALDI ] %-52s %s" % (ad, detay))


def basla(ad):
    print("\n" + ad)
    print("-" * 78)


# =================================================================
# 1. DURGUN HEDEF
# =================================================================
basla("1. DURGUN HEDEF: kesisme suresi = mesafe / hiz")

# Hedef 1000 m doguda, hareketsiz. Saldiran 50 m/s.
t = A.kesisme_suresi(1000.0, 0.0, 0.0, 0.0, 0.0, 0.0, 50.0)
olc("cozum bulundu", t is not None, "t=%s" % t)
if t is not None:
    beklenen = 1000.0 / 50.0
    olc("sure dogru (20 sn)", abs(t - beklenen) < 1e-6,
        "t=%.6f beklenen=%.6f" % (t, beklenen))

# =================================================================
# 2. KACAN HEDEF (hedef daha hizli)
# =================================================================
basla("2. KACAN HEDEF: hedef saldirandan hizli -> cozum YOK")

# Hedef 1000 m doguda, 60 m/s ile DOGUYA kaciyor. Saldiran 50 m/s.
t = A.kesisme_suresi(1000.0, 0.0, 0.0, 60.0, 0.0, 0.0, 50.0)
olc("cozum yok (dogru)", t is None, "t=%s" % t)

# Hedef ayni hizda kaciyorsa da yakalanamaz (asimptotik).
t = A.kesisme_suresi(1000.0, 0.0, 0.0, 50.0, 0.0, 0.0, 50.0)
olc("esit hizda kacan: cozum yok", t is None, "t=%s" % t)

# Ama hedef DOGRU BIZE dogru geliyorsa yakalanir (hizli olsa bile).
t = A.kesisme_suresi(1000.0, 0.0, 0.0, -60.0, 0.0, 0.0, 50.0)
olc("bize dogru gelen hizli hedef: cozum var", t is not None, "t=%s" % t)
if t is not None:
    # Kapanma hizi 110 m/s -> 1000/110 = 9.0909 sn
    olc("sure dogru (9.0909 sn)", abs(t - 1000.0 / 110.0) < 1e-6,
        "t=%.6f" % t)

# =================================================================
# 3. YANDAN GECEN HEDEF: kesisme noktasi tutarli olmali
# =================================================================
basla("3. YANDAN GECEN HEDEF: kesisme noktasi tutarliligi")

# Hedef 1000 m KUZEYDE, 40 m/s ile DOGUYA gidiyor. Saldiran 60 m/s.
dx, dy, dz = 0.0, 1000.0, 0.0      # dogu, kuzey, yukari (hedef - saldiran)
hx, hy, hz = 40.0, 0.0, 0.0        # hedef hiz vektoru
hiz = 60.0
t = A.kesisme_suresi(dx, dy, dz, hx, hy, hz, hiz)
olc("cozum bulundu", t is not None, "t=%s" % t)

if t is not None:
    # Hedefin t sn sonraki yeri (saldirana gore)
    kx, ky, kz = dx + hx * t, dy + hy * t, dz + hz * t
    yol_saldiran = math.sqrt(kx * kx + ky * ky + kz * kz)
    yol_gerekli = hiz * t
    # ASIL DENKLEM: saldiranin t sn'de gidecegi yol, kesisme noktasina
    # olan mesafeye ESIT olmali. Bu saglanmiyorsa cozum yanlistir.
    olc("kesisme kosulu saglaniyor (|K| = hiz*t)",
        abs(yol_saldiran - yol_gerekli) < 1e-6,
        "|K|=%.4f hiz*t=%.4f fark=%.2e" % (yol_saldiran, yol_gerekli,
                                            abs(yol_saldiran - yol_gerekli)))

    # Kestirme acisi: saf takip yonu ile kesisme yonu arasindaki fark
    aci_takip = math.degrees(math.atan2(dx, dy))     # hedefin su anki yonu
    aci_kesis = math.degrees(math.atan2(kx, ky))     # kesisme noktasi yonu
    sapma = abs(aci_kesis - aci_takip)
    olc("kestirme acisi > 0 (one nisan aliyor)", sapma > 1.0,
        "sapma=%.2f derece" % sapma)

# =================================================================
# 4. ASIL IDDIA: kesisme yolu saf takipten KISA
# =================================================================
basla("4. ASIL IDDIA: kesisme yolu saf takip yolundan kisa")


def saf_takip_benzet(dx, dy, hx, hy, hiz, dt=0.05, sure_sinir=600.0,
                     yakalama=5.0):
    """Saf takip (pure pursuit) benzetimi: her adimda hedefin O ANKI
    yerine dogru ucar. Yol uzunlugunu ve sureyi dondurur."""
    sx, sy = 0.0, 0.0
    tx, ty = dx, dy
    yol = 0.0
    t = 0.0
    while t < sure_sinir:
        mx, my = tx - sx, ty - sy
        m = math.sqrt(mx * mx + my * my)
        if m <= yakalama:
            return yol, t
        # saldiran hedefin ANKI yerine yonelir
        ux, uy = mx / m, my / m
        sx += ux * hiz * dt
        sy += uy * hiz * dt
        yol += hiz * dt
        # hedef kendi yolunda ilerler
        tx += hx * dt
        ty += hy * dt
        t += dt
    return None, None


def kesisme_benzet(dx, dy, hx, hy, hiz, dt=0.05, sure_sinir=600.0,
                   yakalama=5.0):
    """Kesisme gudumu benzetimi: her adimda kesisme noktasi yeniden
    cozulur ve ona yonelir (gercek uygulamadaki davranis)."""
    sx, sy = 0.0, 0.0
    tx, ty = dx, dy
    yol = 0.0
    t = 0.0
    while t < sure_sinir:
        mx, my = tx - sx, ty - sy
        m = math.sqrt(mx * mx + my * my)
        if m <= yakalama:
            return yol, t
        tk = A.kesisme_suresi(mx, my, 0.0, hx, hy, 0.0, hiz)
        if tk is None:
            # cozum yok -> saf takibe dus (gercek koddaki davranis)
            ux, uy = mx / m, my / m
        else:
            kx, ky = mx + hx * tk, my + hy * tk
            kn = math.sqrt(kx * kx + ky * ky)
            ux, uy = kx / kn, ky / kn
        sx += ux * hiz * dt
        sy += uy * hiz * dt
        yol += hiz * dt
        tx += hx * dt
        ty += hy * dt
        t += dt
    return None, None


senaryolar = [
    # (ad, dogu, kuzey, hedef_vx_dogu, hedef_vy_kuzey, saldiran_hiz)
    ("yandan gecen (hedef doguya 40 m/s)", 0.0, 1000.0, 40.0, 0.0, 60.0),
    ("caprazdan gecen",                    500.0, 800.0, 30.0, -20.0, 60.0),
    ("hafif kacan (hedef 45 m/s)",         0.0, 1200.0, 45.0, 0.0, 60.0),
    ("bize dogru gelen",                   0.0, 1000.0, 0.0, -40.0, 60.0),
]

for ad, dx, dy, hx, hy, hiz in senaryolar:
    yol_t, sure_t = saf_takip_benzet(dx, dy, hx, hy, hiz)
    yol_k, sure_k = kesisme_benzet(dx, dy, hx, hy, hiz)
    if yol_t is None or yol_k is None:
        olc(ad, False, "benzetim tamamlanmadi (takip=%s kesisme=%s)"
            % (yol_t, yol_k))
        continue
    kazanc_yol = 100.0 * (yol_t - yol_k) / yol_t
    kazanc_sure = 100.0 * (sure_t - sure_k) / sure_t
    # "Bize dogru gelen" senaryosunda iki yol da neredeyse ayni olur
    # (kafa kafaya); orada kazanc ~0 beklenir, kotuleme OLMAMALI.
    olc(ad, yol_k <= yol_t * 1.001,
        "takip=%.0f m/%.1f sn  kesisme=%.0f m/%.1f sn  kazanc=%.1f%% yol, %.1f%% sure"
        % (yol_t, sure_t, yol_k, sure_k, kazanc_yol, kazanc_sure))

# =================================================================
# 5. GOREV BACAGI: konum tasimayan komut tuzagi
# =================================================================
basla("5. GOREV BACAGI: konum tasimayan komutlar atlanmali")

olc("KONUMLU_KOMUTLAR tanimli", hasattr(A, "KONUMLU_KOMUTLAR"),
    "%s" % (sorted(A.KONUMLU_KOMUTLAR) if hasattr(A, "KONUMLU_KOMUTLAR") else "-"))
if hasattr(A, "KONUMLU_KOMUTLAR"):
    olc("NAV_WAYPOINT (16) kabul", 16 in A.KONUMLU_KOMUTLAR)
    olc("DO_CHANGE_SPEED (178) REDDEDILIYOR", 178 not in A.KONUMLU_KOMUTLAR)
    olc("CONDITION_YAW (115) REDDEDILIYOR", 115 not in A.KONUMLU_KOMUTLAR)

# =================================================================
# 6. metre_basi_derece: enleme gore boylam daralmasi
# =================================================================
basla("6. metre_basi_derece: derece basina METRE olcegi")

# NOT: fonksiyon adi "metre_basi_derece" ama gercekte DERECE BASINA
# METRE dondurur (kaynakta `dx = (h_lon - s_lon) * d_lon_m` seklinde
# kullaniliyor: derece farki * olcek = metre). Sinav gercek sozlesmeyi
# olcer, adi degil.
d_lat_0, d_lon_0 = A.metre_basi_derece(0.0)
d_lat_60, d_lon_60 = A.metre_basi_derece(60.0)
olc("enlem olcegi enlemden bagimsiz",
    abs(d_lat_0 - d_lat_60) < 1e-9,
    "0=%.1f 60=%.1f m/derece" % (d_lat_0, d_lat_60))
# Ekvatorda 1 derece boylam ~111.3 km
olc("ekvatorda 1 derece boylam ~111.3 km",
    abs(d_lon_0 - 111320.0) < 1.0, "%.1f m" % d_lon_0)
# 60 derecede cos(60)=0.5 -> 1 derece boylam YARIYA duser
olc("60 derecede boylam olcegi yariya duser",
    abs(d_lon_60 / d_lon_0 - 0.5) < 0.01,
    "oran=%.4f" % (d_lon_60 / d_lon_0))

# Ankara enleminde 1000 m dogu kac derece? (ters cevrim)
d_lat_a, d_lon_a = A.metre_basi_derece(39.95)
derece = 1000.0 / d_lon_a
olc("Ankara'da 1000 m dogu ~0.01169 derece",
    abs(derece - 0.011692) < 0.0002,
    "%.6f derece" % derece)
# Kutupta sifira bolme korumasi (kritik: 90 derecede cos=0)
d_lat_k, d_lon_k = A.metre_basi_derece(90.0)
olc("kutupta sifira bolunme yok (taban siniri var)",
    d_lon_k > 0.0, "%.1f m/derece" % d_lon_k)

# =================================================================
print("\n" + "=" * 78)
print("SONUC: %d gecti, %d kaldi" % (GECEN, KALAN))
print("=" * 78)
sys.exit(0 if KALAN == 0 else 1)
