#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""SINAV — MERKEZ BOS RADAR IP'SINI VARSAYILANA DUSURMEZ (v2.4.62).

## OLCULEN KULLANICI ISTEGI (birebir)

    "neden radar koprusu 192.168.8.186'ya baglanmaya calisiyor, radar
     ben merkez yazilimdan hangi ipye baglan dersem o ipye baglanmali,
     kopru kendisine baglan komutu gelmeden baglanmamali"

## BU SINAV NEDEN AYRI DURUYOR

Kusurun IKI kopyasi vardi ve ikisini duzeltmek ayri islerdir:

1. **Kopru tarafi** — `servis_radar.hazirla()` komut beklemeden gomulu
   adrese baglaniyordu. Olcumu: `goktungu_kopru/sinav_radar_komut_bekle.py`
2. **Merkez tarafi (bu sinav)** — `sunucu.py` icindeki
   `str(k.get("ip","")).strip() or RADAR_VARSAYILAN_IP` satiri, operator
   IP alanini BOS biraktiginda sessizce `192.168.8.186` yaziyordu.

Ikincisi tek basina kalirsa kullanicinin sikayeti AYNEN surer: kopru
artik kendi basina baglanmaz, ama merkez ona gomulu adresi "operatorun
istegi" gibi gonderir. Bu yuzden merkez tarafi bagimsiz olculur.

## YONTEM

Gercek `WSSunucusu` ornegi kurulur, kopruye giden cagri yerine gecirilir
ve GERCEK `_komut_isle` cagrilir. Olculen: kopruye ne gitti, operatore
ne bildirildi.
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
    """LOKAL kurulum yolu icin."""

    def __init__(self):
        self.cagrilar = []
        self.durum = {"durum": "kapali", "hata": "", "ip": "", "port": 0}
        self.radar_ayarlar = {}
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
    print("SINAV — MERKEZ BOS RADAR IP'SINI VARSAYILANA DUSURMEZ")
    print("=" * 70)
    S, srv = sunucu_kur()

    kayit = []
    uyarilar = []

    async def sahte_kopruye_sor(ornek_id, websocket, eylem, veri=None,
                                zaman_asimi=12.0):
        kayit.append((ornek_id, eylem, dict(veri or {})))
        return ({"tamam": True}, "")

    async def sahte_uyari(websocket, kaynak, mesaj, seviye="uyari"):
        uyarilar.append((str(kaynak), str(mesaj), seviye))

    srv._kopruye_sor_async = sahte_kopruye_sor
    srv._uyari_gonder = sahte_uyari
    srv._merkez_kipinde = lambda: True
    srv._ws_firma_id = lambda ws: 7
    srv._kopru_sahibi_mi = lambda oid, fid: (fid == 7 and oid in (11, 22))

    # -----------------------------------------------------------------
    print("\n[1] BOS IP: kopruye komut GITMEZ, operator UYARILIR")
    # -----------------------------------------------------------------
    for etiket, istek in (
            ("alan hic yok", {"tip": "radar_baglan",
                              "kopru_ornek_id": 22}),
            ("bos dize", {"tip": "radar_baglan", "ip": "",
                          "kopru_ornek_id": 22}),
            ("yalniz bosluk", {"tip": "radar_baglan", "ip": "   ",
                               "kopru_ornek_id": 22}),
            ("bos + port var", {"tip": "radar_baglan", "ip": "",
                                "port": 5001, "kopru_ornek_id": 22}),
    ):
        ws = SahteWS()
        kayit.clear()
        uyarilar.clear()
        asyncio.run(srv._komut_isle(ws, dict(istek)))
        olc("bos IP (%s): kopruye komut gitmedi" % etiket,
            len(kayit) == 0, kayit)
        olc("bos IP (%s): operator uyarildi" % etiket,
            len(uyarilar) == 1 and uyarilar[0][0] == "radar", uyarilar)
        if uyarilar:
            olc("bos IP (%s): uyari metni yol gosteriyor" % etiket,
                "adres" in uyarilar[0][1].lower()
                or "ip" in uyarilar[0][1].lower(), uyarilar[0][1])

    # -----------------------------------------------------------------
    print("\n[2] Gomulu adres hicbir yere SIZMIYOR")
    # -----------------------------------------------------------------
    ws = SahteWS()
    kayit.clear()
    uyarilar.clear()
    asyncio.run(srv._komut_isle(ws, {"tip": "radar_baglan", "ip": "",
                                     "kopru_ornek_id": 22}))
    tum_metin = json.dumps(
        {"kayit": kayit, "uyarilar": uyarilar,
         "paketler": ws.paketler}, ensure_ascii=False)
    olc("192.168.8.186 hicbir cikista yok",
        "192.168.8.186" not in tum_metin, tum_metin[:200])

    # -----------------------------------------------------------------
    print("\n[3] DOLU IP: davranis DEGISMEDI (gerileme yok)")
    # -----------------------------------------------------------------
    ws = SahteWS()
    kayit.clear()
    uyarilar.clear()
    asyncio.run(srv._komut_isle(ws, {
        "tip": "radar_baglan", "ip": "192.168.1.50", "port": 5001,
        "kopru_ornek_id": 22}))
    olc("dolu IP: kopruye tam 1 komut gitti", len(kayit) == 1, kayit)
    if kayit:
        oid, eylem, veri = kayit[0]
        olc("dolu IP: eylem radar_baglan", eylem == "radar_baglan", eylem)
        olc("dolu IP: adres AYNEN iletildi",
            veri.get("ip") == "192.168.1.50", veri)
        olc("dolu IP: port aynen iletildi",
            int(veri.get("port") or 0) == 5001, veri)
    olc("dolu IP: gereksiz uyari verilmedi", len(uyarilar) == 0, uyarilar)

    # Bosluklu ama gecerli adres kirpilarak gonderilmeli.
    ws = SahteWS()
    kayit.clear()
    asyncio.run(srv._komut_isle(ws, {
        "tip": "radar_baglan", "ip": "  10.20.30.40  ",
        "kopru_ornek_id": 22}))
    olc("bosluklu gecerli adres kirpildi",
        len(kayit) == 1 and kayit[0][2].get("ip") == "10.20.30.40",
        kayit)

    # -----------------------------------------------------------------
    print("\n[4] PORT: varsayilan korunur, gecersiz reddedilir")
    # -----------------------------------------------------------------
    ws = SahteWS()
    kayit.clear()
    uyarilar.clear()
    asyncio.run(srv._komut_isle(ws, {
        "tip": "radar_baglan", "ip": "192.168.1.50",
        "kopru_ornek_id": 22}))
    olc("port verilmezse C20 varsayilani (5001) gider",
        len(kayit) == 1 and int(kayit[0][2].get("port") or 0) == 5001,
        kayit)

    for etiket, p in (("sifir", 0), ("negatif", -5), ("cok buyuk", 70000)):
        ws = SahteWS()
        kayit.clear()
        uyarilar.clear()
        asyncio.run(srv._komut_isle(ws, {
            "tip": "radar_baglan", "ip": "192.168.1.50", "port": p,
            "kopru_ornek_id": 22}))
        olc("gecersiz port (%s) reddedildi" % etiket,
            len(kayit) == 0 and len(uyarilar) == 1, (kayit, uyarilar))

    # Metin port: sayiya cevrilemezse varsayilana duser (eski davranis).
    ws = SahteWS()
    kayit.clear()
    uyarilar.clear()
    asyncio.run(srv._komut_isle(ws, {
        "tip": "radar_baglan", "ip": "192.168.1.50", "port": "abc",
        "kopru_ornek_id": 22}))
    olc("sayiya cevrilemeyen port varsayilana duser",
        len(kayit) == 1 and int(kayit[0][2].get("port") or 0) == 5001,
        (kayit, uyarilar))

    # -----------------------------------------------------------------
    print("\n[5] LOKAL kurulum yolu BOZULMADI")
    # -----------------------------------------------------------------
    srv._merkez_kipinde = lambda: False
    sr = SahteRadar()
    srv.radar = sr

    ws = SahteWS()
    uyarilar.clear()
    asyncio.run(srv._komut_isle(ws, {
        "tip": "radar_baglan", "ip": "192.168.1.77", "port": 5001}))
    olc("lokal: radar.baglan cagrildi",
        ("baglan", ("192.168.1.77", 5001)) in sr.cagrilar, sr.cagrilar)

    sr.cagrilar.clear()
    ws = SahteWS()
    uyarilar.clear()
    asyncio.run(srv._komut_isle(ws, {"tip": "radar_baglan", "ip": ""}))
    olc("lokal: bos IP ile radar.baglan CAGRILMADI",
        len(sr.cagrilar) == 0, sr.cagrilar)
    olc("lokal: bos IP'de de operator uyarildi",
        len(uyarilar) == 1, uyarilar)

    srv._merkez_kipinde = lambda: True

    # -----------------------------------------------------------------
    print("\n[6] Kaynak: gomulu IP dususu kalmadi")
    # -----------------------------------------------------------------
    yol = os.path.join(_KOK, "goktungu", "sunucu.py")
    with open(yol, encoding="utf-8") as f:
        satirlar = f.readlines()
    kod = [s for s in satirlar if not s.strip().startswith("#")]
    kod_metni = "".join(kod)
    olc("sunucu.py'de 'or RADAR_VARSAYILAN_IP' dususu yok",
        "or RADAR_VARSAYILAN_IP" not in kod_metni)
    olc("RADAR_VARSAYILAN_PORT hala kullanilir (port varsayilani gerekli)",
        "RADAR_VARSAYILAN_PORT" in kod_metni)

    print("\n" + "=" * 70)
    print("SONUC: %d gecti, %d kaldi" % (_gecti, _kaldi))
    if _notlar:
        print("\nKALAN OLCUMLER:")
        for n in _notlar:
            print("  - %s" % n)
    print("=" * 70)
    return 1 if _kaldi else 0


if __name__ == "__main__":
    sys.exit(main())
