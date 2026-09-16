#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.4.49 servis/guc WS komutlarini CALISAN sunucuda sinar.

Neden gerekli: servis.py birim sinavlari islevin kendisini olcer, ancak
WS katmanindaki yetki denetimi, alan adi eslesmesi ve JSON sozlesmesi
ancak gercek sunucuya baglanarak olculebilir. v2.4.49'da iki kusur tam
burada yakalandi (dron.hepsi() yok, eylem() sozluk doner).
"""
import os
import asyncio
import json
import ssl
import sys

WS = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:8765"
EPOSTA = sys.argv[2] if len(sys.argv) > 2 else "mkaderoglu@gokkubbetech.com"
SIFRE = sys.argv[3] if len(sys.argv) > 3 else os.environ.get("GOKTUNGU_SINAV_SIFRE", "")

gecti = 0
kaldi = 0


def olc(ad, kosul, ayrinti=""):
    global gecti, kaldi
    if kosul:
        gecti += 1
        print(f"  GECTI  {ad}")
    else:
        kaldi += 1
        print(f"  KALDI  {ad}  {ayrinti}")


async def main():
    import websockets
    ctx = None
    if WS.startswith("wss://"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    async with websockets.connect(WS, ssl=ctx, max_size=None) as ws:
        await ws.send(json.dumps({"tip": "giris", "eposta": EPOSTA,
                                  "sifre": SIFRE}))
        girdi = False
        rol = ""
        son = asyncio.get_event_loop().time() + 25
        while asyncio.get_event_loop().time() < son:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
            except asyncio.TimeoutError:
                continue
            # GERCEK SOZLESME: tip="giris_sonuc", kullanici={...}
            if m.get("tip") == "giris_sonuc":
                girdi = bool(m.get("basarili"))
                rol = (m.get("kullanici") or {}).get("rol", "")
                break
        olc("giris yapildi", girdi, f"rol={rol}")
        if not girdi:
            return

        # 1) servis_durum
        await ws.send(json.dumps({"tip": "servis_durum"}))
        d = None
        son = asyncio.get_event_loop().time() + 20
        while asyncio.get_event_loop().time() < son:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
            except asyncio.TimeoutError:
                continue
            if m.get("tip") == "servis_durum":
                d = m
                break
        olc("servis_durum yanit verdi", d is not None)
        if d:
            olc("destekli alani var", "destekli" in d, str(d.get("destekli")))
            olc("yetkili alani var", "yetkili" in d, str(d.get("yetkili")))
            olc("yonetici yetkili gorunuyor", d.get("yetkili") is True,
                f"yetkili={d.get('yetkili')} rol={rol}")
            olc("kurulu alani var", "kurulu" in d, str(d.get("kurulu")))
            olc("guc_hazir alani var", "guc_hazir" in d,
                str(d.get("guc_hazir")))
            olc("pid alani gercek surec", isinstance(d.get("pid"), int))
            print(f"    [bilgi] kip={d.get('kip')} kurulu={d.get('kurulu')} "
                  f"aktif={d.get('aktif')} guc_hazir={d.get('guc_hazir')}")

        # 2) servis_gunluk
        await ws.send(json.dumps({"tip": "servis_gunluk", "satir": 20}))
        g = None
        son = asyncio.get_event_loop().time() + 25
        while asyncio.get_event_loop().time() < son:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
            except asyncio.TimeoutError:
                continue
            if m.get("tip") == "servis_gunluk":
                g = m
                break
        olc("servis_gunluk yanit verdi", g is not None)
        if g:
            olc("satirlar listesi doner", isinstance(g.get("satirlar"), list),
                str(type(g.get("satirlar"))))
            # Servis kurulu degilse basarili=False ve ANLASILIR hata
            # beklenir; sessiz bos yanit KABUL EDILMEZ.
            olc("kurulu degilken anlasilir hata",
                bool(g.get("basarili")) or bool(g.get("hata")),
                f"basarili={g.get('basarili')} hata={g.get('hata')!r}")

        # 3) Bilinmeyen eylem reddedilmeli (sessiz gecmemeli)
        await ws.send(json.dumps({"tip": "servis_eylem", "ad": "sacma"}))
        s = None
        son = asyncio.get_event_loop().time() + 20
        while asyncio.get_event_loop().time() < son:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
            except asyncio.TimeoutError:
                continue
            if m.get("tip") == "servis_sonuc":
                s = m
                break
        olc("bilinmeyen eylem yanit verdi", s is not None)
        if s:
            olc("bilinmeyen eylem reddedildi", s.get("basarili") is False,
                str(s.get("basarili")))
            olc("red gerekcesi bildirildi",
                bool(s.get("hata") or s.get("ileti")),
                f"{s.get('hata')!r}")

        # 4) makine_kapat: yetki yoksa ONCEDEN reddedilmeli.
        #    DIKKAT - sandbox'ta guc_hazir False oldugu icin makine
        #    KAPANMAZ; bu sinav guvenle kosturulabilir. Gercek makinede
        #    guc_hazir True ise bu adim ATLANIR.
        if d and d.get("guc_hazir") is False:
            await ws.send(json.dumps({"tip": "makine_kapat", "ad": "kapat"}))
            mk = None
            son = asyncio.get_event_loop().time() + 20
            while asyncio.get_event_loop().time() < son:
                try:
                    m = json.loads(await asyncio.wait_for(ws.recv(),
                                                          timeout=3))
                except asyncio.TimeoutError:
                    continue
                if m.get("tip") == "makine_sonuc":
                    mk = m
                    break
            olc("makine_kapat yanit verdi", mk is not None)
            if mk:
                olc("yetki yoksa ONCEDEN reddedildi",
                    mk.get("basarili") is False, str(mk.get("basarili")))
                olc("red gerekcesi cozum iceriyor",
                    "servis_kur" in (mk.get("hata") or "")
                    or "yetki" in (mk.get("hata") or "").lower(),
                    f"{mk.get('hata')!r}")
        else:
            print("    [atlandi] guc_hazir True; makine KAPANMASIN diye "
                  "kapatma sinavi kosturulmadi")

        # 5) Bilinmeyen guc eylemi reddedilmeli
        await ws.send(json.dumps({"tip": "makine_kapat", "ad": "sacma"}))
        mb = None
        son = asyncio.get_event_loop().time() + 20
        while asyncio.get_event_loop().time() < son:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
            except asyncio.TimeoutError:
                continue
            if m.get("tip") == "makine_sonuc":
                mb = m
                break
        olc("bilinmeyen guc eylemi reddedildi",
            mb is not None and mb.get("basarili") is False,
            str(mb))


asyncio.run(main())
print(f"\nSONUC: {gecti} gecti / {kaldi} kaldi")
sys.exit(1 if kaldi else 0)
