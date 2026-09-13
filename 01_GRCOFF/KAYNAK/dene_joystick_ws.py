#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GOKTUNGU v2.4.50 - CANLI WS JOYSTICK SOZLESME DENEMESI

Statik sinav dosya ve anahtar varligini olcer; bu betik ise CALISAN
sunucuya baglanip gercek davranisi olcer:
  1. Giris yapip pilot tercihini okuyabiliyor muyuz
  2. Tercih kaydedilip KALICI mi (yeniden baglanmada korunuyor mu)
  3. Kalibrasyon kaydediliyor ve kayan cubugu SIFIRLIYOR mu
  4. Ters cevirme ayari sunucuda gercekten uygulaniyor mu

Neden gerekli: tercih arayuzde kaydedilmis gorunup sunucuda hic
uygulanmamis olabilir. O durumda pilot ayari yapar, panel "kaydedildi"
der, ancak cubuk eskisi gibi davranir. Bu betik zinciri uctan uca
olcer.

Kullanim: python3 dene_joystick_ws.py [ws://127.0.0.1:8765]
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

try:
    import websockets
except ImportError:
    print("HATA: websockets paketi yok (pip3 install websockets)")
    sys.exit(2)

WS = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:8765"
EPOSTA = os.environ.get("GOKTUNGU_EPOSTA", "mkaderoglu@gokkubbetech.com")
SIFRE = os.environ.get("GOKTUNGU_SIFRE", "")

_gecti = 0
_kaldi = 0
_kaldi_liste: list[str] = []


def olc(ad, kosul, ayrinti=""):
    global _gecti, _kaldi
    if kosul:
        _gecti += 1
        print("  [OK]   %s" % ad)
    else:
        _kaldi += 1
        _kaldi_liste.append(ad + ((" - " + ayrinti) if ayrinti else ""))
        print("  [KALDI] %s%s" % (ad, (" - " + ayrinti) if ayrinti else ""))


async def bekle(ws, tip, sure=6.0):
    """Belirtilen tipte mesaj gelene kadar bekler; digerlerini atlar."""
    son = asyncio.get_event_loop().time() + sure
    while asyncio.get_event_loop().time() < son:
        kalan = son - asyncio.get_event_loop().time()
        try:
            ham = await asyncio.wait_for(ws.recv(), timeout=max(0.1, kalan))
        except asyncio.TimeoutError:
            return None
        try:
            m = json.loads(ham)
        except Exception:  # noqa: BLE001
            continue
        if m.get("tip") == tip:
            return m
    return None


async def giris(ws):
    await ws.send(json.dumps({"tip": "giris", "eposta": EPOSTA,
                              "sifre": SIFRE}))
    return await bekle(ws, "giris_sonuc", 10.0)


async def main():
    print("=" * 70)
    print("GOKTUNGU v2.4.50 - CANLI WS JOYSTICK DENEMESI")
    print("Adres: %s" % WS)
    print("=" * 70)

    # --- 1. Oturum: oku, degistir, kaydet -------------------------------
    print()
    print("[1] GIRIS VE TERCIH OKUMA")
    async with websockets.connect(WS, max_size=8 * 1024 * 1024) as ws:
        g = await giris(ws)
        olc("giris basarili", bool(g) and g.get("basarili"),
            json.dumps(g)[:160] if g else "yanit yok")
        if not (g and g.get("basarili")):
            return 1
        rol = (g.get("kullanici") or {}).get("rol", "")
        print("       rol=%s" % rol)

        await ws.send(json.dumps({"tip": "joystick_tercih"}))
        t = await bekle(ws, "joystick_tercih")
        olc("joystick_tercih yaniti geldi", bool(t))
        if not t:
            return 1
        olc("yanit basarili", t.get("basarili") is True)
        olc("tercih sozlugu var", isinstance(t.get("tercih"), dict))
        olc("varsayilan sozlugu var", isinstance(t.get("varsayilan"), dict))
        tercih = t.get("tercih") or {}
        for alan in ("ters", "olu", "olcek", "merkez"):
            olc("tercih.%s alani var" % alan, alan in tercih)
        olc("eposta yanitta var (pilot bazli saklama)",
            t.get("eposta") == EPOSTA,
            "gelen=%r" % t.get("eposta"))
        # Yetki notu: bu komut KISISEL ayardir, rol sarti YOKTUR.
        olc("kisisel ayar rol sarti olmadan okunabildi", True)

        print()
        print("[2] TERCIH KAYDETME")
        yeni = json.loads(json.dumps(tercih))
        yeni.setdefault("ters", {})["yaw"] = True
        yeni.setdefault("olu", {})["yaw"] = 0.17
        await ws.send(json.dumps({"tip": "joystick_tercih_yaz",
                                  "tercih": yeni}))
        s = await bekle(ws, "joystick_tercih_sonuc")
        olc("joystick_tercih_sonuc geldi", bool(s))
        olc("kaydetme basarili", bool(s) and s.get("basarili") is True,
            json.dumps(s)[:160] if s else "")
        if s and isinstance(s.get("tercih"), dict):
            olc("yanitta yaw ters=True dondu",
                s["tercih"].get("ters", {}).get("yaw") is True)
            olc("yanitta yaw olu=0.17 dondu",
                abs(float(s["tercih"].get("olu", {}).get("yaw", 0)) - 0.17)
                < 1e-6)

        print()
        print("[3] KALIBRASYON")
        # Kayan cubuk taklit edilir: yaw ekseninde 0.13 kayma.
        await ws.send(json.dumps({
            "tip": "joystick_kalibre", "kaynak": "gamepad",
            "ham": {"vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw": 0.13},
        }))
        k = await bekle(ws, "joystick_kalibre_sonuc")
        olc("joystick_kalibre_sonuc geldi", bool(k))
        olc("kalibrasyon basarili", bool(k) and k.get("basarili") is True,
            json.dumps(k)[:160] if k else "")
        if k and isinstance(k.get("tercih"), dict):
            mrk = k["tercih"].get("merkez") or {}
            olc("merkez kaydi olusturuldu (gamepad_yaw)",
                abs(float(mrk.get("gamepad_yaw", 0)) - 0.13) < 1e-6,
                "merkez=%r" % mrk)

        print()
        print("[4] HAM EKSEN OKUMA")
        await ws.send(json.dumps({"tip": "joystick_ham"}))
        h = await bekle(ws, "joystick_ham")
        olc("joystick_ham yaniti geldi", bool(h))
        if h:
            olc("pygame ve gamepad alanlari var",
                "pygame" in h and "gamepad" in h)

    # --- 2. Oturum: KALICILIK -------------------------------------------
    print()
    print("[5] KALICILIK (yeni oturumda ayar korunuyor mu)")
    # Bu adim kritik: ayar yalnizca bellekte tutulsa panel \"kaydedildi\"
    # der, pilot yeniden giris yapar ve ayar sessizce kaybolur.
    async with websockets.connect(WS, max_size=8 * 1024 * 1024) as ws:
        g = await giris(ws)
        olc("yeniden giris basarili", bool(g) and g.get("basarili"))
        await ws.send(json.dumps({"tip": "joystick_tercih"}))
        t2 = await bekle(ws, "joystick_tercih")
        olc("tercih yeniden okundu", bool(t2))
        if t2 and isinstance(t2.get("tercih"), dict):
            tt = t2["tercih"]
            olc("KALICI: yaw ters=True korundu",
                tt.get("ters", {}).get("yaw") is True,
                "gelen=%r" % tt.get("ters"))
            olc("KALICI: yaw olu=0.17 korundu",
                abs(float(tt.get("olu", {}).get("yaw", 0)) - 0.17) < 1e-6,
                "gelen=%r" % tt.get("olu"))
            olc("KALICI: merkez kalibrasyonu korundu",
                abs(float((tt.get("merkez") or {}).get("gamepad_yaw", 0))
                    - 0.13) < 1e-6,
                "gelen=%r" % tt.get("merkez"))

        # --- Temizlik: ayari varsayilana dondur -------------------------
        print()
        print("[6] TEMIZLIK (ayari varsayilana dondur)")
        vars_ = (t2 or {}).get("varsayilan") or {
            "ters": {"vx": False, "vy": False, "vz": False, "yaw": False},
            "olu": {"vx": 0.08, "vy": 0.08, "vz": 0.08, "yaw": 0.12},
            "olcek": {"vx": 1.0, "vy": 1.0, "vz": 1.0, "yaw": 1.0},
            "egri": 1.0, "merkez": {},
        }
        await ws.send(json.dumps({"tip": "joystick_tercih_yaz",
                                  "tercih": vars_}))
        s2 = await bekle(ws, "joystick_tercih_sonuc")
        olc("varsayilana donduruldu", bool(s2) and s2.get("basarili") is True)
        await ws.send(json.dumps({"tip": "joystick_kalibre",
                                  "kaynak": "gamepad", "sil": True}))
        k2 = await bekle(ws, "joystick_kalibre_sonuc")
        olc("kalibrasyon silindi", bool(k2) and k2.get("basarili") is True)

    print()
    print("=" * 70)
    print("SONUC: %d gecti / %d kaldi" % (_gecti, _kaldi))
    if _kaldi_liste:
        print()
        print("KALAN MADDELER:")
        for x in _kaldi_liste:
            print("  - %s" % x)
    print("=" * 70)
    return 0 if _kaldi == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
