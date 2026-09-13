#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GOKTUNGU v2.4.43 - ANGAJMAN ONGORUSU: GERCEK SITL OLCUMU

Iki SITL multirotoru baslatir:
  - HEDEF   : rota yuklenip AUTO modda ucurulur (gorev durumu olusur)
  - SALDIRAN: hedefe angaje edilir

Olculen sorular:
  1. Hedefin hiz vektoru (vx, vy) telemetriye akiyor mu?
  2. Hedef GOREVDEyken angajman `ongoru_kaynak="gorev"` uretiyor mu?
  3. Kesisme cozumu bir sapma (one nisan) uretiyor mu?
  4. `gorev_dikkate=False` iken davranis saf takibe donuyor mu?
  5. `angajman_ayar` WS komutu ayari KALICI kaydediyor mu?
     (param property kusuru gerilemesi)

Hicbir sonuc varsayilmaz; olculen degerler yazdirilir.
"""

import os
import asyncio
import json
import math
import sys
import time

import websockets

WS = "ws://127.0.0.1:8765"
EPOSTA = "mkaderoglu@gokkubbetech.com"
SIFRE = os.environ.get("GOKTUNGU_SINAV_SIFRE", "")  # koda parola yazilmaz

# Ankara Sincan civari
KALKIS_LAT, KALKIS_LON = 39.9700, 32.5800

sonuclar = []


def kayit(ad, gecti, olculen=""):
    sonuclar.append((ad, gecti, olculen))
    isaret = "GECTI" if gecti else "BASARISIZ"
    print(f"[{isaret:9}] {ad}" + (f"  ->  {olculen}" if olculen else ""))


def bilgi(m):
    print(f"    {m}")


async def mesaj_bekle(ws, tipler, sure=20.0, kosul=None):
    bitis = time.time() + sure
    while time.time() < bitis:
        kalan = bitis - time.time()
        if kalan <= 0:
            return None
        try:
            ham = await asyncio.wait_for(ws.recv(), timeout=kalan)
        except asyncio.TimeoutError:
            return None
        try:
            m = json.loads(ham)
        except (ValueError, TypeError):
            continue
        if m.get("tip") in tipler:
            if kosul is None or kosul(m):
                return m
    return None


async def telemetri_bekle(ws, sure=20.0, kosul=None):
    """Telemetri mesaji bekler (kosul tum mesaj uzerinde calisir)."""
    return await mesaj_bekle(ws, {"telemetri"}, sure=sure, kosul=kosul)


def dron_bul(m, sysid):
    for d in (m.get("dronlar") or []):
        if int(d.get("sysid", -1)) == int(sysid):
            return d
    return None


def angajman_bul(m, sysid):
    """`angajmanlar` SOZLUKTUR: {saldiran_sysid: {...}}

    Olculdu: angajman.durum_paketi() -> dict(self._canli) ve
    ws.js:112 `m.angajmanlar || {}` seklinde tuketiyor. JSON'da
    anahtarlar METIN olur, bu yuzden iki bicim de denenir.
    """
    a = m.get("angajmanlar") or {}
    if isinstance(a, dict):
        return a.get(str(sysid)) or a.get(sysid)
    for kayit_ in a:
        if int(kayit_.get("saldiran_sysid", -1)) == int(sysid):
            return kayit_
    return None


async def dronlar_bekle(ws, adet, sure=180.0):
    """Konumu olan `adet` kadar dron gorunene kadar bekler."""
    bitis = time.time() + sure
    while time.time() < bitis:
        m = await telemetri_bekle(ws, sure=bitis - time.time())
        if not m:
            continue
        konumlu = [d for d in (m.get("dronlar") or [])
                   if d.get("lat") is not None]
        if len(konumlu) >= adet:
            return konumlu
    return None


def mesafe_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp / 2) ** 2 +
         math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


async def baglanti_kur(ws, isim, lat, lon, adet):
    """Sanal (SITL) baglanti ekler ve baslatir; kayit id dondurur."""
    await ws.send(json.dumps({
        "tip": "baglanti_ekle", "isim": isim, "tur": "sanal",
        "sanal_tip": "multirotor", "sanal_lat": lat, "sanal_lon": lon,
        "sanal_adet": adet}))
    m = await mesaj_bekle(ws, {"baglanti_listesi", "baglanti_hata"}, sure=25)
    if m is None or m.get("tip") == "baglanti_hata":
        return None
    bid = None
    for b in (m.get("baglantilar") or []):
        if b.get("isim") == isim:
            bid = b.get("id")
    if bid is None:
        return None
    await ws.send(json.dumps({"tip": "baglanti_baslat", "id": bid}))
    return bid


async def main():
    async with websockets.connect(WS, max_size=None) as ws:
        # ---------------- Oturum ----------------
        await ws.send(json.dumps({"tip": "giris", "eposta": EPOSTA,
                                  "sifre": SIFRE}))
        g = await mesaj_bekle(ws, {"giris_sonuc", "oturum"}, sure=15)
        if not g:
            kayit("Oturum acildi", False, "giris cevabi gelmedi")
            return 1
        kayit("Oturum acildi", True, g.get("tip"))

        # ---------- 5) angajman_ayar KALICILIK sinavi ----------
        # Once ayari degistir, sonra geri al; kalici sozluge yazildigini
        # `angajman_baslat` davranisindan DEGIL, dogrudan cevaptan olc.
        await ws.send(json.dumps({"tip": "angajman_ayar",
                                  "gorev_dikkate": False,
                                  "ongoru": True}))
        a1 = await mesaj_bekle(ws, {"angajman_ayar_sonuc"}, sure=15)
        if not a1:
            kayit("angajman_ayar cevabi geldi", False, "cevap yok")
        else:
            # Cevap alani `ayar` (olculdu: sunucu.py:1474)
            kayit("angajman_ayar cevabi geldi", bool(a1.get("basari")),
                  f"basari={a1.get('basari')} ayar={a1.get('ayar')}")
            p = a1.get("ayar") or {}
            kayit("Ayar KALICI sozluge yazildi (gorev_dikkate=False)",
                  p.get("gorev_dikkate") is False,
                  f"gorev_dikkate={p.get('gorev_dikkate')} "
                  f"ongoru={p.get('ongoru')}")
        # Geri ac (asil olcum icin gerekli)
        await ws.send(json.dumps({"tip": "angajman_ayar",
                                  "gorev_dikkate": True, "ongoru": True}))
        a2 = await mesaj_bekle(ws, {"angajman_ayar_sonuc"}, sure=15)
        if a2:
            p2 = a2.get("ayar") or {}
            kayit("Ayar geri acildi (gorev_dikkate=True)",
                  p2.get("gorev_dikkate") is True,
                  f"gorev_dikkate={p2.get('gorev_dikkate')}")

        # ---------------- Iki SITL dronu ----------------
        bilgi("Iki SITL multirotoru baslatiliyor (ilk acilis uzun surer)...")
        bid = await baglanti_kur(ws, "SINAV ANGAJMAN", KALKIS_LAT,
                                 KALKIS_LON, 2)
        if bid is None:
            kayit("Iki sanal dron baglantisi kuruldu", False,
                  "baglanti kurulamadi")
            return 1
        kayit("Iki sanal dron baglantisi kuruldu", True, f"id={bid}")

        dronlar = await dronlar_bekle(ws, 2, sure=240)
        if not dronlar:
            kayit("Iki dron telemetrisi geldi", False,
                  "2 dron gorunmedi")
            await ws.send(json.dumps({"tip": "baglanti_durdur", "id": bid}))
            return 1
        sysid_hedef = int(dronlar[0]["sysid"])
        sysid_sald = int(dronlar[1]["sysid"])
        kayit("Iki dron telemetrisi geldi", True,
              f"hedef sysid={sysid_hedef}, saldiran sysid={sysid_sald}")

        # ---------- 1) Hiz vektoru telemetride ----------
        m = await telemetri_bekle(ws, sure=20)
        d = dron_bul(m, sysid_hedef) if m else None
        var = d is not None and "vx" in d and "vy" in d
        kayit("Hedef hiz vektoru (vx,vy) telemetri semasinda", var,
              f"vx={d.get('vx') if d else '?'} vy={d.get('vy') if d else '?'}")

        # ---------- EKF/GPS oturmasi beklenir ----------
        # Olculdu: temiz SITL acilisindan sonra ~22 sn'de
        #   "PreArm: Need Position Estimate"
        # ~60 sn'de   "Arming motors" -> ARMED
        # Bu bir urun kusuru DEGIL, gercek otopilot davranisi: konum
        # tahmini oturmadan ARM reddedilir. Sinav bunu beklemek
        # zorunda, aksi halde kendi aceleciligini urun kusuru sanar.
        # HOME once kurulur: v2.4.42 kurali geregi HOME olmadan dron
        # "hazir" sayilmaz (ve otopilot da ARM etmez). Bu yuzden
        # hazirlik beklemesinden ONCE HOME kurulur.
        for _sid in (sysid_hedef, sysid_sald):
            await ws.send(json.dumps({
                "tip": "dron_komut", "sysid": _sid,
                "aksiyon": "set_home",
                "lat": KALKIS_LAT, "lon": KALKIS_LON}))
            await asyncio.sleep(1.5)

        # DIKKAT: `uydu >= 6` YETERLI DEGIL. Olculdu:
        #   [DRON] PreArm: Need Position Estimate   (uydu zaten 10)
        #   [DRON] EKF3 IMU0 is using GPS           (birkac sn SONRA)
        # Uydu sayisi GPS'in gordugu uydu; EKF'nin o GPS'i konum
        # tahmininde KULLANMASI ayri ve daha sonra olur. Bu yuzden
        # urunun kendi hazirlik gostergesi (hazirlik.hazir) beklenir —
        # bu ayni zamanda o gostergenin dogru calistigini da olcer.
        bilgi("Urunun hazirlik gostergesi bekleniyor (hazirlik.hazir)...")
        oturdu = False
        bitis_ekf = time.time() + 240
        while time.time() < bitis_ekf:
            m = await telemetri_bekle(ws, sure=bitis_ekf - time.time())
            if not m:
                break
            dh = dron_bul(m, sysid_hedef)
            ds = dron_bul(m, sysid_sald)
            if not dh or not ds:
                continue
            hh = (dh.get("hazirlik") or {}).get("hazir")
            hs = (ds.get("hazirlik") or {}).get("hazir")
            if hh and hs:
                oturdu = True
                break
        kayit("Iki dron ARM'a hazir bildirildi (hazirlik.hazir)", oturdu,
              "urun hazirlik gostergesi ARM'a hazir diyor" if oturdu
              else "240 sn icinde hazirlik.hazir dogru olmadi")

        # ---------- HOME kurulur (v2.4.42 set_home) ----------
        # Olculdu: HOME kurulmadan otopilot ARM etmiyor:
        #   [DRON] [230] PreArm: AHRS: waiting for home
        # Bu, v2.4.42'de eklenen "HOME yoksa hazir degil" kuralinin
        # otopilot tarafindan da dayatildiginin kanitidir. Ayni
        # zamanda set_home komutunun gorev ucusunu gercekten mumkun
        # kildigini olcer.
        bilgi("HOME telemetri teyidi bekleniyor...")
        home_ok = False
        bitis_h = time.time() + 60
        while time.time() < bitis_h:
            m = await telemetri_bekle(ws, sure=bitis_h - time.time())
            if not m:
                break
            dh = dron_bul(m, sysid_hedef)
            if dh and dh.get("home_lat") is not None:
                home_ok = True
                break
        kayit("HOME kuruldu ve telemetride goruldu (set_home)", home_ok,
              "home_lat telemetride mevcut" if home_ok
              else "60 sn icinde home_lat gelmedi")

        # ---------- Hedefe rota yukle ve ucur ----------
        # Kalkis noktasindan DOGUYA giden duz bir bacak: kesisme
        # gudumunun one nisan almasi gereken klasik senaryo.
        noktalar = []
        for i in range(1, 5):
            noktalar.append({"lat": KALKIS_LAT,
                             "lon": KALKIS_LON + 0.006 * i,
                             "irtifa": 40.0, "hiz": 12.0})
        await ws.send(json.dumps({
            "tip": "rota_kaydet", "isim": "SINAV BACAK",
            "irtifa": 40.0, "hiz": 12.0, "noktalar": noktalar}))
        rl = await mesaj_bekle(ws, {"rota_listesi"}, sure=20)
        rota_id = rl.get("yeni_id") if rl else None
        kayit("Sinav rotasi olusturuldu", rota_id is not None,
              f"rota_id={rota_id}, {len(noktalar)} nokta, dogu bacagi")
        if rota_id is None:
            await ws.send(json.dumps({"tip": "baglanti_durdur", "id": bid}))
            return 1

        await ws.send(json.dumps({"tip": "gorev_yukle",
                                  "sysid": sysid_hedef,
                                  "rota_id": rota_id}))
        gy = await mesaj_bekle(ws, {"gorev_yukle_sonuc"}, sure=40)
        kayit("Gorev yukleme KABUL edildi", bool(gy and gy.get("basari")),
              f"{gy.get('bilgi') if gy else 'cevap yok'}")

        # `gorev_yukle_sonuc` YALNIZCA "kabul edildi" demektir; gorev
        # ogeleri drona hala gonderiliyor olabilir. Olculdu:
        #   [GOREV] ... gorev henuz yukleniyor, baslatma bekletildi.
        # Bu yuzden asamanin "yuklendi"ye gectigi telemetriden
        # dogrulanir, sonra baslatilir.
        bilgi("Gorev ogelerinin drona yuklenmesi bekleniyor...")
        yuklendi = False
        bitis_y = time.time() + 120
        while time.time() < bitis_y:
            m = await telemetri_bekle(ws, sure=bitis_y - time.time())
            if not m:
                break
            gd = (m.get("gorev_durum") or {}).get(str(sysid_hedef)) or {}
            if gd.get("asama") == "yuklendi":
                yuklendi = True
                break
        kayit("Gorev drona TAM yuklendi (asama=yuklendi)", yuklendi,
              "gorev ogeleri gonderildi" if yuklendi
              else "120 sn icinde asama 'yuklendi' olmadi")

        await ws.send(json.dumps({"tip": "gorev_baslat",
                                  "sysid": sysid_hedef}))
        gb = await mesaj_bekle(ws, {"gorev_baslat_sonuc"}, sure=60)
        kayit("Gorev baslatildi (ARM + AUTO)",
              bool(gb and gb.get("basari")),
              f"{gb.get('bilgi') if gb else 'cevap yok'}")

        # Hedefin SEYIR hizina ulasmasi beklenir (rota hizi 12 m/s).
        # Olculdu: 3.4 m/s'de kesisme suresi 0.6 sn cikiyor ve ileri
        # mesafe 1 m'de kaliyor — matematik dogru olsa da olcum
        # anlamsiz kalir. Bu yuzden esik seyir hizina yakin tutulur.
        bilgi("Hedefin seyir hizina ulasmasi bekleniyor (> 8 m/s)...")
        hareket = None
        bitis = time.time() + 180
        while time.time() < bitis:
            m = await telemetri_bekle(ws, sure=bitis - time.time())
            if not m:
                continue
            d = dron_bul(m, sysid_hedef)
            if not d:
                continue
            vx, vy = d.get("vx") or 0.0, d.get("vy") or 0.0
            yatay = math.sqrt(vx * vx + vy * vy)
            if yatay > 8.0:
                hareket = (d, yatay)
                break
        if hareket:
            d, yatay = hareket
            kayit("Hedef hareket ediyor ve hiz vektoru OLCULDU", True,
                  f"vx={vx:.2f} (kuzey) vy={vy:.2f} (dogu) "
                  f"yatay={yatay:.2f} m/s mod={d.get('mod')}")
        else:
            kayit("Hedef hareket ediyor ve hiz vektoru OLCULDU", False,
                  "yatay hiz 3 m/s'yi gecmedi")

        # ---------- Saldiran da kaldirilir ----------
        # Olculdu: saldiran yerde kalirsa hedef ondan yalnizca ~200 m
        # uzakta oldugu icin kesisme suresi 0.7 sn cikiyor ve ileri
        # mesafe 3 m'de kaliyor. Ongoru dogru calissa bile olcum
        # anlamsiz olur. Gercek angajmanda saldiran havadadir; sinav
        # da bunu taklit etmelidir.
        bilgi("Saldiran kaldiriliyor (takeoff 40 m)...")
        await ws.send(json.dumps({
            "tip": "dron_komut", "sysid": sysid_sald,
            "aksiyon": "takeoff", "irtifa": 40.0}))
        havada = False
        bitis_t = time.time() + 120
        while time.time() < bitis_t:
            m = await telemetri_bekle(ws, sure=bitis_t - time.time())
            if not m:
                continue
            ds = dron_bul(m, sysid_sald)
            if ds and (ds.get("irtifa") or 0) > 25.0:
                havada = True
                break
        kayit("Saldiran havada (takeoff)", havada,
              "irtifa > 25 m" if havada else "120 sn icinde kalkmadi")

        # Hedefin yeterince uzaklasmasi beklenir: kesisme suresi
        # mesafeyle buyur, ancak o zaman ongoru olculebilir hale gelir.
        bilgi("Hedefin uzaklasmasi bekleniyor (> 400 m)...")
        bitis_u = time.time() + 120
        uzak_m = 0.0
        while time.time() < bitis_u:
            m = await telemetri_bekle(ws, sure=bitis_u - time.time())
            if not m:
                continue
            dh = dron_bul(m, sysid_hedef)
            ds = dron_bul(m, sysid_sald)
            if not dh or not ds or dh.get("lat") is None:
                continue
            uzak_m = mesafe_m(ds["lat"], ds["lon"], dh["lat"], dh["lon"])
            if uzak_m > 400.0:
                break
        bilgi(f"Hedef-saldiran mesafesi: {uzak_m:.0f} m")

        # ---------- 2-3) Angajmani baslat ve cozumu olc ----------
        await ws.send(json.dumps({
            "tip": "angajman_baslat",
            "saldiran_sysid": sysid_sald,
            "hedef_tip": "dron", "hedef_id": sysid_hedef}))
        ab = await mesaj_bekle(ws, {"angajman"}, sure=25)
        kayit("Angajman baslatildi", ab is not None,
              f"{(ab or {}).get('durum')}")
        # Angajman kaydinda hedef konumu YOK; kesisme noktasinin hedefin
        # ilerisinde oldugunu olcmek icin hedefin anlik konumu ayrica
        # telemetriden okunur.
        hedef_anlik = None

        bilgi("Angajman cozumu bekleniyor (telemetri icinde)...")
        cozum = None
        bitis = time.time() + 90
        while time.time() < bitis:
            m = await telemetri_bekle(ws, sure=bitis - time.time())
            if not m:
                continue
            a = angajman_bul(m, sysid_sald)
            if a and a.get("ongoru_kaynak") in ("gorev", "hiz"):
                cozum = a
                break
        if cozum:
            kayit("Angajman ONGORU cozumu uretti", True,
                  f"kaynak={cozum.get('ongoru_kaynak')} "
                  f"kesisme_sn={cozum.get('kesisme_sn')} "
                  f"sapma={cozum.get('sapma')} derece "
                  f"hedef_hiz={cozum.get('hedef_hiz')} m/s")
            kayit("Cozum kaynagi GOREV (hedef AUTO modda rotada)",
                  cozum.get("ongoru_kaynak") == "gorev",
                  f"kaynak={cozum.get('ongoru_kaynak')} "
                  f"hedef_mod={cozum.get('hedef_mod')} "
                  f"gorev_seq={cozum.get('hedef_gorev_seq')}")
            sapma = cozum.get("sapma") or 0.0
            kayit("Kesisme one nisan aliyor (sapma > 0)", sapma > 0.0,
                  f"sapma={sapma} derece")
            kesisme_sn = cozum.get("kesisme_sn")
            kayit("Kesisme suresi makul (0 < t <= 120 sn)",
                  kesisme_sn is not None and 0 < kesisme_sn <= 120,
                  f"kesisme_sn={kesisme_sn}")
            # Kesisme noktasi hedefin ONUNDE mi?
            # Angajman kaydinda hedef KONUMU yok (olculdu: yalniz
            # hedef_alt/hedef_hiz var), bu yuzden hedefin anlik konumu
            # telemetriden ayrica okunur.
            k_lat, k_lon = cozum.get("kesisme_lat"), cozum.get("kesisme_lon")
            m_h = await telemetri_bekle(ws, sure=15)
            d_h = dron_bul(m_h, sysid_hedef) if m_h else None
            if k_lat and k_lon and d_h and d_h.get("lat") is not None:
                ileri = mesafe_m(d_h["lat"], d_h["lon"], k_lat, k_lon)
                kayit("Kesisme noktasi hedefin ILERISINDE", ileri > 5.0,
                      f"kesisme={k_lat:.6f},{k_lon:.6f} "
                      f"hedef={d_h['lat']:.6f},{d_h['lon']:.6f} "
                      f"ileri={ileri:.0f} m")
            else:
                kayit("Kesisme noktasi hedefin ILERISINDE", False,
                      f"kesisme_lat={k_lat} kesisme_lon={k_lon} "
                      f"hedef_konum={(d_h or {}).get('lat')}")
        else:
            # Cozum gelmediyse angajman kaydini teshis icin yaz
            son = None
            m = await telemetri_bekle(ws, sure=15)
            if m:
                son = angajman_bul(m, sysid_sald)
            kayit("Angajman ONGORU cozumu uretti", False,
                  f"son kayit={son}")

        # ---------- 4) gorev_dikkate=False -> saf takip ----------
        await ws.send(json.dumps({"tip": "angajman_iptal",
                                  "saldiran_sysid": sysid_sald}))
        await asyncio.sleep(3)
        await ws.send(json.dumps({"tip": "angajman_ayar",
                                  "gorev_dikkate": False, "ongoru": True}))
        await mesaj_bekle(ws, {"angajman_ayar_sonuc"}, sure=15)
        await ws.send(json.dumps({
            "tip": "angajman_baslat",
            "saldiran_sysid": sysid_sald,
            "hedef_tip": "dron", "hedef_id": sysid_hedef}))
        await mesaj_bekle(ws, {"angajman"}, sure=25)
        bilgi("gorev_dikkate=False ile cozum kaynagi olculuyor...")
        c2 = None
        bitis = time.time() + 60
        while time.time() < bitis:
            m = await telemetri_bekle(ws, sure=bitis - time.time())
            if not m:
                continue
            a = angajman_bul(m, sysid_sald)
            if a and a.get("durum") == "aktif":
                c2 = a
                break
        if c2:
            kayit("gorev_dikkate=False iken kaynak GOREV DEGIL",
                  c2.get("ongoru_kaynak") != "gorev",
                  f"kaynak={c2.get('ongoru_kaynak')} "
                  f"(gorev yerine hiz vektoru veya cozum yok)")
        else:
            kayit("gorev_dikkate=False iken kaynak GOREV DEGIL", False,
                  "cozum kaydi gelmedi")

        # ---------- 6) ongoru=False -> tamamen saf takip ----------
        await ws.send(json.dumps({"tip": "angajman_iptal",
                                  "saldiran_sysid": sysid_sald}))
        await asyncio.sleep(3)
        await ws.send(json.dumps({"tip": "angajman_ayar",
                                  "gorev_dikkate": True, "ongoru": False}))
        await mesaj_bekle(ws, {"angajman_ayar_sonuc"}, sure=15)
        await ws.send(json.dumps({
            "tip": "angajman_baslat",
            "saldiran_sysid": sysid_sald,
            "hedef_tip": "dron", "hedef_id": sysid_hedef}))
        await mesaj_bekle(ws, {"angajman"}, sure=25)
        bilgi("ongoru=False ile davranis olculuyor...")
        c3 = None
        bitis = time.time() + 60
        while time.time() < bitis:
            m = await telemetri_bekle(ws, sure=bitis - time.time())
            if not m:
                continue
            a = angajman_bul(m, sysid_sald)
            if a and a.get("mesafe") is not None:
                c3 = a
                break
        if c3:
            kayit("ongoru=False iken ongoru KAPALI bildiriliyor",
                  c3.get("ongoru") is False,
                  f"ongoru={c3.get('ongoru')} "
                  f"kaynak={c3.get('ongoru_kaynak')} "
                  f"sapma={c3.get('sapma')}")
            kayit("ongoru=False iken sapma yok (saf takip)",
                  not c3.get("sapma"),
                  f"sapma={c3.get('sapma')}")
        else:
            kayit("ongoru=False iken ongoru KAPALI bildiriliyor", False,
                  "angajman kaydi gelmedi")

        # ---------------- Temizlik ----------------
        await ws.send(json.dumps({"tip": "angajman_iptal",
                                  "saldiran_sysid": sysid_sald}))
        await asyncio.sleep(2)
        # Ayarlari varsayilana dondur
        await ws.send(json.dumps({"tip": "angajman_ayar",
                                  "gorev_dikkate": True, "ongoru": True}))
        await asyncio.sleep(1)
        await ws.send(json.dumps({"tip": "gorev_iptal",
                                  "sysid": sysid_hedef}))
        await asyncio.sleep(2)
        await ws.send(json.dumps({"tip": "baglanti_durdur", "id": bid}))
        await asyncio.sleep(3)
        await ws.send(json.dumps({"tip": "baglanti_sil", "id": bid}))
        await asyncio.sleep(2)
        if rota_id is not None:
            await ws.send(json.dumps({"tip": "rota_sil", "id": rota_id}))
            await asyncio.sleep(1)

    print("\n" + "=" * 70)
    gecen = sum(1 for _, g, _ in sonuclar if g)
    print(f"SONUC: {gecen}/{len(sonuclar)} sinav gecti")
    print("=" * 70)
    return 0 if gecen == len(sonuclar) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
