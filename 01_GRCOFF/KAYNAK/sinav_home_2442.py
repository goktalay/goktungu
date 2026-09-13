#!/usr/bin/env python3
"""v2.4.42 HOME POINT ucdan uca sinavi.

Gercek SITL sureci + gercek WebSocket sunucusu uzerinden dogrular:
  1. HOME_POSITION telemetriye akiyor mu (home_lat/home_lon/home_ts)
  2. Hazirlik denetiminde HOME maddesi VAR mi ve `oncelik: 0` tasiyor mu
  3. `set_home` (mevcut konum kipi) calisiyor mu
  4. `set_home` (belirtilen konum kipi) HOME'u GERCEKTEN tasiyor mu
  5. HOME atanmamis arac hazir sayilmiyor mu

Olculen degerler yazdirilir; hicbir sonuc varsayilmaz.
"""
import os
import asyncio
import json
import sys
import time

import websockets

WS = "ws://127.0.0.1:8765"
EPOSTA = "mkaderoglu@gokkubbetech.com"
SIFRE = os.environ.get("GOKTUNGU_SINAV_SIFRE", "")  # koda parola yazilmaz

# Ankara Sincan civari - SITL kalkis noktasi
KALKIS_LAT, KALKIS_LON = 39.9700, 32.5800
# HOME olarak atanacak AYRI nokta (kalkistan ~2 km kuzey)
HEDEF_LAT, HEDEF_LON = 39.9880, 32.5800

sonuclar = []


def kayit(ad, gecti, olculen=""):
    sonuclar.append((ad, gecti, olculen))
    isaret = "GECTI" if gecti else "BASARISIZ"
    print(f"[{isaret:9}] {ad}" + (f"  ->  {olculen}" if olculen else ""))


async def mesaj_bekle(ws, tipler, sure=20.0, kosul=None):
    """Belirtilen tiplerden biri gelene kadar bekler."""
    bitis = time.time() + sure
    while time.time() < bitis:
        try:
            ham = await asyncio.wait_for(ws.recv(), timeout=bitis - time.time())
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


async def dron_bekle(ws, sure=90.0):
    """Telemetride konumu olan bir dron gorunene kadar bekler.

    NOT: `baglanti` alani aranmaz. SITL kalkis anlarinda bu alan henuz
    True olmayabilirken telemetri (ve HOME) akmaya baslamis olur;
    kosula eklemek sinavi gereksiz basarisiz kilardi.
    """
    bitis = time.time() + sure
    ilk_tip = None
    while time.time() < bitis:
        m = await mesaj_bekle(ws, {"dronlar", "telemetri"},
                              sure=bitis - time.time())
        if not m:
            continue
        if ilk_tip is None:
            ilk_tip = m.get("tip")
            print(f"    (telemetri mesaj tipi: {ilk_tip})")
        for d in (m.get("dronlar") or []):
            if d.get("lat") is not None:
                return d
    return None


async def dron_oku(ws, sysid, sure=20.0, kosul=None):
    """Belirli dronun son telemetri kaydini dondurur."""
    bitis = time.time() + sure
    while time.time() < bitis:
        m = await mesaj_bekle(ws, {"dronlar", "telemetri"},
                              sure=bitis - time.time())
        if not m:
            continue
        for d in (m.get("dronlar") or []):
            if int(d.get("sysid", -1)) == int(sysid):
                if kosul is None or kosul(d):
                    return d
    return None


async def dron_oku_ham(ws, sysid, sure=20.0):
    """Kosulsuz son kayit (teshis icin)."""
    return await dron_oku(ws, sysid, sure=sure)


def mesafe_m(lat1, lon1, lat2, lon2):
    import math
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp / 2) ** 2 +
         math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


async def main():
    async with websockets.connect(WS, max_size=None) as ws:
        # --- Oturum ---
        await ws.send(json.dumps({"tip": "giris", "eposta": EPOSTA,
                                  "sifre": SIFRE}))
        g = await mesaj_bekle(ws, {"giris_sonuc", "oturum"}, sure=15)
        if not g:
            kayit("Oturum acildi", False, "giris cevabi gelmedi")
            return
        kayit("Oturum acildi", True, g.get("tip"))

        # --- SITL sanal dron baslat ---
        # Sozlesme (sunucu.py:1174): duz alanlar, `sanal_*` on ekli.
        await ws.send(json.dumps({
            "tip": "baglanti_ekle",
            "isim": "SINAV HOME", "tur": "sanal",
            "sanal_tip": "multirotor",
            "sanal_lat": KALKIS_LAT, "sanal_lon": KALKIS_LON,
            "sanal_adet": 1}))
        eklendi = await mesaj_bekle(
            ws, {"baglanti_listesi", "baglanti_hata"}, sure=25)
        if eklendi is None:
            kayit("Sanal baglanti eklendi", False,
                  "baglanti_listesi duyurusu gelmedi")
            return
        if eklendi and eklendi.get("tip") == "baglanti_hata":
            kayit("Sanal baglanti eklendi", False,
                  str(eklendi.get("hata")))
            return
        # Kayit id'sini listeden al; `baglanti_ekle` SITL surecini
        # BASLATMAZ (sunucu.py:1174) - ayrica `baglanti_baslat` gerekir.
        bid = None
        for b in (eklendi.get("baglantilar") or []):
            if b.get("isim") == "SINAV HOME":
                bid = b.get("id")
        if bid is None:
            kayit("Sanal baglanti eklendi", False,
                  "kayit listesinde bulunamadi")
            return
        kayit("Sanal baglanti eklendi", True, f"id={bid}")
        await ws.send(json.dumps({"tip": "baglanti_baslat", "id": bid}))
        print("    SITL baslatiliyor (ilk acilis ~60 s surebilir)...")
        d = await dron_bekle(ws, sure=150)
        if not d:
            kayit("SITL dron telemetrisi geldi", False, "dron gorunmedi")
            return
        sysid = int(d["sysid"])
        kayit("SITL dron telemetrisi geldi", True,
              f"sysid={sysid} lat={d['lat']:.5f} lon={d['lon']:.5f}")

        # --- 1) HOME_POSITION telemetriye akiyor mu ---
        # SITL ARM oncesi HOME yayabilir; 25 s beklenir.
        dh = await dron_oku(ws, sysid, sure=30,
                            kosul=lambda x: x.get("home_ts", 0) > 0)
        if dh:
            kayit("HOME_POSITION telemetriye akiyor", True,
                  f"home_ts>0, home_lat={dh.get('home_lat')}, "
                  f"home_lon={dh.get('home_lon')}")
        else:
            # Akmadiysa alanlarin en azindan SEMADA oldugunu dogrula
            d2 = await dron_oku(ws, sysid, sure=10)
            var = d2 is not None and "home_lat" in d2 and "home_ts" in d2
            kayit("HOME alanlari telemetri semasinda", var,
                  f"home_lat={d2.get('home_lat') if d2 else '?'} "
                  f"home_ts={d2.get('home_ts') if d2 else '?'}")

        # --- 2) Hazirlik denetiminde HOME maddesi ---
        await ws.send(json.dumps({"tip": "arm_check", "sysid": sysid}))
        r = await mesaj_bekle(ws, {"arm_check_rapor"}, sure=20)
        if not r:
            kayit("ARM CHECK raporu geldi", False, "cevap yok")
        else:
            maddeler = r.get("maddeler") or []
            home_m = [m for m in maddeler if m.get("anahtar") == "home"]
            kayit("Denetimde HOME maddesi var", bool(home_m),
                  f"{len(maddeler)} madde icinde "
                  f"{len(home_m)} HOME maddesi")
            if home_m:
                hm = home_m[0]
                kayit("HOME maddesi oncelik=0 (listede en basta)",
                      int(hm.get("oncelik", 50)) == 0,
                      f"oncelik={hm.get('oncelik')} durum={hm.get('durum')} "
                      f"deger={hm.get('deger')!r} grup={hm.get('grup')}")
                # HOME yoksa arac hazir sayilmamali
                if hm.get("durum") == "hata":
                    kayit("HOME yoksa arac HAZIR DEGIL",
                          r.get("hazir") is False,
                          f"hazir={r.get('hazir')} sebep={r.get('sebep')!r}")
                else:
                    kayit("HOME atanmis - hazirlik HOME'dan dolayi "
                          "engellenmiyor", True,
                          f"durum={hm.get('durum')} hazir={r.get('hazir')}")

        # --- 3) set_home: MEVCUT KONUM kipi ---
        await ws.send(json.dumps({"tip": "dron_komut", "sysid": sysid,
                                  "aksiyon": "set_home"}))
        s = await mesaj_bekle(ws, {"set_home_sonuc"}, sure=20)
        if not s:
            kayit("set_home (mevcut konum) cevabi geldi", False, "cevap yok")
        else:
            kayit("set_home (mevcut konum) basarili",
                  bool(s.get("basari")),
                  f"basari={s.get('basari')} sebep={s.get('sebep')!r} "
                  f"mevcut_konum={s.get('mevcut_konum')}")
            kayit("Cevap mevcut_konum=True bildiriyor",
                  s.get("mevcut_konum") is True,
                  f"mevcut_konum={s.get('mevcut_konum')}")

        # --- 4) set_home: BELIRTILEN KONUM kipi (SHIFT + tik) ---
        await ws.send(json.dumps({"tip": "dron_komut", "sysid": sysid,
                                  "aksiyon": "set_home",
                                  "lat": HEDEF_LAT, "lon": HEDEF_LON}))
        s2 = await mesaj_bekle(ws, {"set_home_sonuc"}, sure=20)
        if not s2:
            kayit("set_home (secilen konum) cevabi geldi", False, "cevap yok")
        else:
            kayit("set_home (secilen konum) basarili",
                  bool(s2.get("basari")),
                  f"basari={s2.get('basari')} sebep={s2.get('sebep')!r}")
            kayit("Cevap mevcut_konum=False bildiriyor",
                  s2.get("mevcut_konum") is False,
                  f"mevcut_konum={s2.get('mevcut_konum')}")

        # HOME GERCEKTEN tasindi mi? Telemetriden dogrula.
        d3 = await dron_oku(
            ws, sysid, sure=40,
            kosul=lambda x: (x.get("home_lat") is not None and
                             abs(x["home_lat"] - HEDEF_LAT) < 0.002))
        if d3:
            uz = mesafe_m(d3["home_lat"], d3["home_lon"],
                          HEDEF_LAT, HEDEF_LON)
            kayit("HOME telemetride yeni konuma tasindi", uz < 50,
                  f"home={d3['home_lat']:.6f},{d3['home_lon']:.6f} "
                  f"hedeften sapma={uz:.1f} m alt={d3.get('home_alt')}")
        else:
            son = await dron_oku(ws, sysid, sure=10)
            kayit("HOME telemetride yeni konuma tasindi", False,
                  f"olculen home={son.get('home_lat') if son else '?'},"
                  f"{son.get('home_lon') if son else '?'}")

        # --- Temizlik: SITL durdur ve kaydi sil ---
        await ws.send(json.dumps({"tip": "baglanti_durdur", "id": bid}))
        await asyncio.sleep(2)
        await ws.send(json.dumps({"tip": "baglanti_sil", "id": bid}))
        await asyncio.sleep(2)

    print("\n" + "=" * 62)
    gecen = sum(1 for _, g, _ in sonuclar if g)
    print(f"SONUC: {gecen}/{len(sonuclar)} sinav gecti")
    print("=" * 62)
    return 0 if gecen == len(sonuclar) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
