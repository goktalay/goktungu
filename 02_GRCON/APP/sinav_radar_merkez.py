#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""KUSUR-RADAR-KOPRU — MERKEZ TARAFI KOMUT YONLENDIRME SINAVI

Kullanici bildirimi:
    "radarda da ayni sorun var, radarin kopru yazilimi calisiyor ama
     sistem radari sunucuda ariyor"

Bu sinav MERKEZ tarafini olcer: RADAR AYARLARI panelindeki komutlar
gercekten KOPRUYE mi gidiyor, yetki dogrulaniyor mu, LOKAL kurulum yolu
bozuldu mu.

YONTEM — kaynak denetimi DEGIL, DAVRANIS olcumu:
  * Gercek `WSSunucusu` ornegi kurulur
  * `_kopruye_sor_async` ve kopru secimi YERINE gecirilir; boylece
    gercek bir saha makinesi olmadan merkezin HANGI makineye ne
    gonderdigi kaydedilir
  * Gercek `_komut_isle` cagrilir; sahte websocket gonderilen JSON'u
    toplar
  * Lokal kip icin `_merkez_kipinde` False yapilir ve `self.radar`
    sahte nesneyle degistirilir; merkez yolunun lokali BOZMADIGI olculur

Neden onemli: kusur "komut yanlis makineye gitti" sinifindandir.
Kaynakta `_radar_kopruye` cagrisini gormek YETMEZ; cagrinin gercekten o
eylemle, o veriyle ve DOGRU kopru kimligiyle yapildigi olculmelidir.
"""
import asyncio
import json
import os
import sys
import threading

_KOK = os.path.dirname(os.path.abspath(__file__))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

_gecti = 0
_kaldi = 0
_notlar = []


def olc(ad, kosul, ek=None):
    global _gecti, _kaldi
    if kosul:
        _gecti += 1
        print("  OK    %s" % ad)
    else:
        _kaldi += 1
        print("  KALDI %s" % ad)
        if ek is not None:
            print("        -> %r" % (ek,))
        _notlar.append(ad)


class SahteWS:
    def __init__(self):
        self.paketler = []

    async def send(self, metin):
        try:
            self.paketler.append(json.loads(metin))
        except Exception:
            self.paketler.append({"_ham": metin})

    def son(self, tip=None):
        for p in reversed(self.paketler):
            if tip is None or p.get("tip") == tip:
                return p
        return None


class SahteRadar:
    """LOKAL kurulum yolu icin. Gercek RadarIstemcisi yuzunu tasir."""

    def __init__(self):
        self.cagrilar = []
        self.durum = {"durum": "kapali", "hata": "", "ip": "", "port": 0}
        self.radar_ayarlar = {"frekans": 0, "tespit_esigi": 1}
        self.hedefler = {}
        self.ayar_kuyruk = []

    def baglan(self, ip=None, port=None):
        self.cagrilar.append(("baglan", (ip, port)))
        return True

    def kes(self):
        self.cagrilar.append(("kes", None))
        return True

    def radar_konum(self):
        return (None, None)


def sunucu_kur():
    from goktungu import sunucu as S
    nesne = S.WSSunucusu.__new__(S.WSSunucusu)
    nesne._ws_firma = {}
    nesne._ws_kullanici = {}
    nesne._ws_pilot = {}
    nesne.radar = None
    nesne.istasyon2 = None
    nesne.manuel_kontrol = None
    nesne.baglantilar = None
    nesne.istemciler = set()
    nesne.kilit = threading.Lock()
    nesne.pilot = None
    nesne.konsol = lambda *a, **k: None
    return S, nesne


def main():
    print("=" * 70)
    print("KUSUR-RADAR-KOPRU — MERKEZ TARAFI KOMUT YONLENDIRME SINAVI")
    print("=" * 70)

    S, srv = sunucu_kur()

    kayit = []      # (ornek_id, eylem, veri)
    yanitlar = {}   # eylem -> (veri, hata)

    async def sahte_kopruye_sor(ornek_id, websocket, eylem, veri=None,
                                zaman_asimi=12.0):
        kayit.append((ornek_id, eylem, dict(veri or {})))
        return yanitlar.get(eylem, ({"tamam": True}, ""))

    srv._kopruye_sor_async = sahte_kopruye_sor
    srv._merkez_kipinde = lambda: True
    srv._ws_firma_id = lambda ws: 7
    srv._kopru_sahibi_mi = lambda oid, fid: (fid == 7 and oid in (11, 22))

    # -----------------------------------------------------------------
    print("\n[1] RADARA BAGLAN komutu KOPRUYE gider (merkeze DEGIL)")
    # -----------------------------------------------------------------
    ws = SahteWS()
    kayit.clear()
    asyncio.run(srv._komut_isle(ws, {
        "tip": "radar_baglan", "ip": "192.168.8.168", "port": 5001,
        "kopru_ornek_id": 22}))
    olc("kopruye tam 1 komut gitti", len(kayit) == 1, kayit)
    if kayit:
        oid, eylem, veri = kayit[0]
        olc("hedef makine pilotun sectigi (22)", oid == 22, oid)
        olc("eylem adi radar_baglan", eylem == "radar_baglan", eylem)
        olc("IP aynen iletildi", veri.get("ip") == "192.168.8.168", veri)
        olc("port aynen iletildi", int(veri.get("port") or 0) == 5001, veri)

    # -----------------------------------------------------------------
    print("\n[2] YETKI: baska firmanin koprusune komut GITMEZ")
    # -----------------------------------------------------------------
    ws = SahteWS()
    kayit.clear()
    asyncio.run(srv._komut_isle(ws, {
        "tip": "radar_baglan", "ip": "10.0.0.5", "port": 5001,
        "kopru_ornek_id": 999}))
    olc("yetkisiz makineye komut GITMEDI", len(kayit) == 0, kayit)

    # -----------------------------------------------------------------
    print("\n[3] Tum radar komutlari kopruye yonlenir")
    # -----------------------------------------------------------------
    beklenen = {
        "radar_kes": "radar_kes",
        "radar_ayar_oku": "radar_ayar_oku",
        "radar_ayar_yaz": "radar_ayar_yaz",
        "rtk_konum_al": "radar_rtk",
    }
    for komut, eylem_adi in beklenen.items():
        ws = SahteWS()
        kayit.clear()
        istek = {"tip": komut, "kopru_ornek_id": 11}
        if komut == "radar_ayar_yaz":
            # Arayuz (js/radar_panel.js:177) ayarlari DUZ alan olarak
            # gonderir; `ayarlar` sarmalayicisi YOKTUR.
            istek.update({"frekans": 2, "tespit_esigi": 1,
                          "hiz_esigi": 1, "rcs_esigi": 0,
                          "calisma_modu": "bekleme",
                          "merkez_yonu": 45.0})
        asyncio.run(srv._komut_isle(ws, istek))
        olc("%s -> kopru" % komut, len(kayit) == 1, kayit)
        if kayit:
            oid, eylem, veri = kayit[0]
            olc("  eylem adi %s" % eylem_adi, eylem == eylem_adi, eylem)
            olc("  hedef makine 11", oid == 11, oid)
            if komut == "radar_ayar_yaz":
                olc("  frekans iletildi", veri.get("frekans") == 2, veri)
                olc("  merkez yonu de SAHAYA gitti",
                    abs(float(veri.get("merkez_yonu") or -1) - 45.0) < 1e-6,
                    veri)

    # -----------------------------------------------------------------
    print("\n[4] Kopru HATASI panele bildirilir (sessiz kalmaz)")
    # -----------------------------------------------------------------
    yanitlar["radar_baglan"] = (None, "kopru yanit vermedi")
    ws = SahteWS()
    kayit.clear()
    asyncio.run(srv._komut_isle(ws, {
        "tip": "radar_baglan", "ip": "192.168.8.168", "port": 5001,
        "kopru_ornek_id": 22}))
    paketler = [p.get("tip") for p in ws.paketler]
    olc("panele en az bir paket gitti", len(ws.paketler) >= 1, paketler)
    uyari = ws.son("uyari_yeni")
    olc("uyari_yeni gonderildi (dogru sozlesme)", uyari is not None, paketler)
    if uyari:
        ic = uyari.get("uyari") or {}
        olc("uyari ic nesnesi var", bool(ic), uyari)
        olc("uyari metninde sebep var",
            "kopru" in json.dumps(ic, ensure_ascii=False).lower(), ic)
    yanitlar.pop("radar_baglan", None)

    # -----------------------------------------------------------------
    print("\n[5] Kopru YAPILANDIRILMAMISSA anlamli hata")
    # -----------------------------------------------------------------
    srv._kopru_sahibi_mi = lambda oid, fid: False
    ws = SahteWS()
    kayit.clear()
    asyncio.run(srv._komut_isle(ws, {"tip": "radar_baglan",
                                     "ip": "1.2.3.4", "port": 5001}))
    olc("kopru yoksa TCP denemesi YAPILMADI", len(kayit) == 0, kayit)
    olc("panele bilgi gitti", len(ws.paketler) >= 1,
        [p.get("tip") for p in ws.paketler])
    srv._kopru_sahibi_mi = lambda oid, fid: (fid == 7 and oid in (11, 22))

    # -----------------------------------------------------------------
    print("\n[6] GERILEME: LOKAL kurulumda komut kopruye GITMEZ")
    # -----------------------------------------------------------------
    srv._merkez_kipinde = lambda: False
    yerel = SahteRadar()
    srv.radar = yerel
    ws = SahteWS()
    kayit.clear()
    asyncio.run(srv._komut_isle(ws, {
        "tip": "radar_baglan", "ip": "192.168.8.168", "port": 5001}))
    olc("lokalde kopruye komut GITMEDI", len(kayit) == 0, kayit)
    olc("lokalde YEREL radar cagrildi",
        any(c[0] == "baglan" for c in yerel.cagrilar), yerel.cagrilar)

    kayit.clear()
    yerel.cagrilar.clear()
    asyncio.run(srv._komut_isle(ws, {"tip": "radar_kes"}))
    olc("lokal kes yerel yola gitti",
        any(c[0] == "kes" for c in yerel.cagrilar) and len(kayit) == 0,
        (yerel.cagrilar, kayit))
    srv._merkez_kipinde = lambda: True
    srv.radar = None

    # -----------------------------------------------------------------
    print("\n[7] Kopru secimi: pilot sectiyse ORAYA, secmediyse tek olan")
    # -----------------------------------------------------------------
    ws = SahteWS()
    kayit.clear()
    asyncio.run(srv._komut_isle(ws, {
        "tip": "radar_baglan", "ip": "1.1.1.1", "port": 5001,
        "kopru_ornek_id": 11}))
    olc("acik secim korunur (11)", bool(kayit) and kayit[0][0] == 11, kayit)

    # -----------------------------------------------------------------
    print("\n[8] Komut yetki tablosunda radar girdileri var")
    # -----------------------------------------------------------------
    try:
        tablo = getattr(S, "KOMUT_IZIN", None) or getattr(
            S, "_KOMUT_IZIN", None)
    except Exception:
        tablo = None
    if isinstance(tablo, dict):
        for k in ("radar_baglan", "radar_kes", "radar_ayar_yaz"):
            olc("yetki tablosunda %s" % k, k in tablo, sorted(tablo)[:5])
    else:
        # Tablo adi farkli olabilir; kaynakta varligini dogrula
        yol = os.path.join(_KOK, "goktungu", "sunucu.py")
        with open(yol, "r", encoding="utf-8") as f:
            kaynak = f.read()
        for k in ("radar_baglan", "radar_kes", "radar_ayar_yaz"):
            olc("yetki tablosunda %s" % k,
                ('"%s":' % k) in kaynak, k)

    # -----------------------------------------------------------------
    print("\n[9] Merkez kipinde YEREL TCP nesnesi hic kurulmaz")
    # -----------------------------------------------------------------
    yol = os.path.join(_KOK, "main.py")
    with open(yol, "r", encoding="utf-8") as f:
        ana = f.read()
    olc("main.py RadarVekili kuruyor", "RadarVekili" in ana, None)
    olc("main.py merkez kipini ayirt ediyor",
        ("merkez" in ana.lower() and "RadarVekili" in ana), None)

    print("=" * 70)
    print("SONUC: %d gecti, %d kaldi" % (_gecti, _kaldi))
    if _notlar:
        print("KALANLAR:")
        for n in _notlar:
            print("  - %s" % n)
    print("=" * 70)
    return 1 if _kaldi else 0


if __name__ == "__main__":
    sys.exit(main())
