#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GOKTUNGU v2.4.44 - Istasyon 2 ucus dugmelerinin GERCEK SITL sinavi.

Onceki canli sinav, joystick kontrolu KAPALI iken dugmelerin komut
GONDERMEDIGINI olcuyordu. Bu betik tersini olcer: sanal dron (SITL)
baglanip manuel (joystick) kontrol ACILDIGINDA panel dugmeleri gercek
MAVLink komutlarina donusuyor mu?

Akis:
  benzetici (PTY) <-> backend <-> WS <-> bu betik
                 SITL dron  <-> backend

Kullanim:
  python3 sinav_2444_sitl.py <pty_yolu> [ws_url]
"""
import os
import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    print("websockets gerekli")
    sys.exit(2)
try:
    import serial
except ImportError:
    print("pyserial gerekli")
    sys.exit(2)

PTY = sys.argv[1] if len(sys.argv) > 1 else "/dev/pts/4"
WS = sys.argv[2] if len(sys.argv) > 2 else "ws://127.0.0.1:8765"
EPOSTA = "mkaderoglu@gokkubbetech.com"
SIFRE = os.environ.get("GOKTUNGU_SINAV_SIFRE", "")  # koda parola yazilmaz

_gecti = 0
_kaldi = []


def denet(ad, kosul, kanit=""):
    global _gecti
    if kosul:
        _gecti += 1
        print("[GECTI    ] %s%s" % (ad, ("  ->  " + kanit) if kanit else ""))
    else:
        _kaldi.append(ad)
        print("[BASARISIZ] %s%s" % (ad, ("  ->  " + kanit) if kanit else ""))


class Kutu:
    def __init__(self):
        self.hepsi = []
        self.dronlar = {}
        self.eylem_sonuclari = []
        self.manuel = None

    def ekle(self, m):
        t = m.get("tip", "")
        self.hepsi.append(m)
        if t == "istasyon2_eylem_sonuc":
            self.eylem_sonuclari.append(m)
        elif t == "manuel_durum":
            self.manuel = m
        elif t == "telemetri":
            for d in (m.get("dronlar") or []):
                try:
                    self.dronlar[int(d.get("sysid"))] = d
                except (TypeError, ValueError):
                    pass

    def sonuc(self, eylem):
        return [e for e in self.eylem_sonuclari if e.get("eylem") == eylem]

    def sifirla(self):
        self.eylem_sonuclari.clear()


async def main():
    kutu = Kutu()
    sp = serial.Serial(PTY, 115200, timeout=0.2)

    def sim(*p):
        sp.write(("SIM," + ",".join(str(x) for x in p) + "\n").encode())
        sp.flush()

    async with websockets.connect(WS, max_size=8 * 1024 * 1024) as ws:
        async def dinle():
            try:
                async for ham in ws:
                    try:
                        kutu.ekle(json.loads(ham))
                    except Exception:
                        pass
            except Exception:
                pass

        gorev = asyncio.create_task(dinle())

        async def g(paket):
            await ws.send(json.dumps(paket))

        async def bek(sn):
            await asyncio.sleep(sn)

        print("=" * 70)
        print("GOKTUNGU v2.4.44 - ISTASYON 2 UCUS DUGMELERI / GERCEK SITL")
        print("=" * 70)

        await g({"tip": "giris", "eposta": EPOSTA, "sifre": SIFRE})
        await bek(2.0)

        # Panel baglantisi
        await g({"tip": "istasyon2_baglan", "port": PTY})
        await bek(2.0)

        # --- Sanal dron (SITL) baslat -------------------------------
        print("\n--- 1. Sanal dron (SITL) ---")
        # Sanal baglanti olustur (tur=sanal, host="tip|lat|lon|adet")
        await g({"tip": "baglanti_ekle", "isim": "IST2-SINAV",
                 "tur": "sanal", "port": "",
                 "sanal_tip": "multirotor", "sanal_lat": 39.0,
                 "sanal_lon": 35.0, "sanal_adet": 1})
        await bek(2.5)
        # Listeyi al, kaydin kimligini bul
        bid = None
        for _ in range(6):
            await g({"tip": "baglanti_listesi"})
            await bek(1.2)
            for m in reversed(kutu.hepsi):
                if m.get("tip") in ("baglanti_listesi", "baglantilar"):
                    for b in (m.get("baglantilar") or m.get("liste") or []):
                        if b.get("isim") == "IST2-SINAV":
                            bid = b.get("id")
                            break
                    break
            if bid:
                break
        print("    baglanti id =", bid)
        if bid:
            await g({"tip": "baglanti_baslat", "id": int(bid)})
        # SITL'in ayaga kalkmasi ve MAVLink akisi zaman alir
        sysid = None
        for _ in range(45):
            await bek(2.0)
            if kutu.dronlar:
                sysid = sorted(kutu.dronlar.keys())[0]
                break
        denet("SITL dronu baglandi", sysid is not None,
              "sysid=%s" % sysid)
        if sysid is None:
            gorev.cancel()
            sp.close()
            print("\nSITL baslamadi; sinav durduruldu.")
            return 1

        # --- Manuel (joystick) kontrolu AC --------------------------
        print("\n--- 2. Joystick kontrolu aciliyor ---")
        await g({"tip": "manuel_anahtar", "sysid": sysid, "acik": True})
        await bek(2.0)
        denet("manuel kontrol acildi",
              bool(kutu.manuel) and sysid in
              [int(x) for x in (kutu.manuel.get("aktif") or [])],
              "aktif=%s" % json.dumps((kutu.manuel or {}).get("aktif")))

        # --- P1: ARM ------------------------------------------------
        print("\n--- 3. P1 -> ARM ---")
        kutu.sifirla()
        sim("BTN", "P1", 1)
        await bek(1.0)
        sim("BTN", "P1", 0)
        await bek(2.5)
        es = kutu.sonuc("arm_disarm")
        denet("P1 arm komutu uygulandi",
              bool(es) and es[0].get("basari") is True,
              json.dumps({"basari": es[0].get("basari"),
                          "aksiyonlar": es[0].get("aksiyonlar"),
                          "sysidler": es[0].get("sysidler")})
              if es else "eylem_sonuc gelmedi")
        if es:
            denet("  hedef sysid dogru", sysid in (es[0].get("sysidler") or []),
                  str(es[0].get("sysidler")))
            denet("  aksiyon 'arm'", "arm" in (es[0].get("aksiyonlar") or []),
                  str(es[0].get("aksiyonlar")))

        # --- P4: GUIDED modu ---------------------------------------
        print("\n--- 4. P4 -> GUIDED ---")
        kutu.sifirla()
        sim("BTN", "P4", 1)
        await bek(1.0)
        sim("BTN", "P4", 0)
        await bek(2.5)
        es = kutu.sonuc("mod_guided")
        denet("P4 GUIDED komutu uygulandi",
              bool(es) and es[0].get("basari") is True,
              json.dumps(es[0].get("aksiyonlar")) if es else "-")
        if es:
            denet("  mod adi GUIDED",
                  "GUIDED" in (es[0].get("aksiyonlar") or []),
                  str(es[0].get("aksiyonlar")))

        # --- P5 / P6 ------------------------------------------------
        for tus, eylem, beklenen in (("P5", "mod_althold", "ALT_HOLD"),
                                     ("P6", "mod_auto", "AUTO")):
            print("\n--- %s -> %s ---" % (tus, beklenen))
            kutu.sifirla()
            sim("BTN", tus, 1)
            await bek(1.0)
            sim("BTN", tus, 0)
            await bek(2.5)
            es = kutu.sonuc(eylem)
            denet("%s komutu uygulandi" % tus,
                  bool(es) and es[0].get("basari") is True,
                  json.dumps(es[0].get("aksiyonlar")) if es else "-")
            if es:
                denet("  mod adi %s" % beklenen,
                      beklenen in (es[0].get("aksiyonlar") or []),
                      str(es[0].get("aksiyonlar")))

        # --- P3: RTL ------------------------------------------------
        print("\n--- P3 -> RTL ---")
        kutu.sifirla()
        sim("BTN", "P3", 1)
        await bek(1.0)
        sim("BTN", "P3", 0)
        await bek(2.5)
        es = kutu.sonuc("rtl")
        denet("P3 RTL komutu uygulandi",
              bool(es) and es[0].get("basari") is True,
              json.dumps(es[0].get("aksiyonlar")) if es else "-")

        # --- P2: TAKEOFF/LAND ---------------------------------------
        print("\n--- P2 -> TAKEOFF/LAND ---")
        kutu.sifirla()
        sim("BTN", "P2", 1)
        await bek(1.0)
        sim("BTN", "P2", 0)
        await bek(2.5)
        es = kutu.sonuc("takeoff_land")
        denet("P2 komutu uygulandi",
              bool(es) and es[0].get("basari") is True,
              json.dumps(es[0].get("aksiyonlar")) if es else "-")
        if es:
            denet("  yerdeyken takeoff secildi (havada degil -> land degil)",
                  "takeoff" in (es[0].get("aksiyonlar") or []),
                  str(es[0].get("aksiyonlar")))

        # --- Ek joystick dron eksenine gidiyor ----------------------
        print("\n--- Ek dron joysticki -> manuel eksen ---")
        sim("EKJOY", "J3_Y", 3600)
        await bek(1.5)
        await g({"tip": "istasyon2_durum"})
        await bek(1.2)
        d = None
        for m in reversed(kutu.hepsi):
            if m.get("tip") == "istasyon2_durum":
                d = m
                break
        nrm = (d or {}).get("normalize") or {}
        denet("J3_Y normalize edildi", abs(nrm.get("J3_Y", 0)) > 0.3,
              "J3_Y_n=%s" % nrm.get("J3_Y"))
        sim("EKJOY", "J3_Y", 2048)
        await bek(0.8)

        # --- Joystick kontrolunu KAPAT, dugme etkisiz kalmali -------
        print("\n--- Joystick kontrolu kapatiliyor ---")
        await g({"tip": "manuel_anahtar", "sysid": sysid, "acik": False})
        await bek(2.0)
        kutu.sifirla()
        sim("BTN", "P1", 1)
        await bek(1.0)
        sim("BTN", "P1", 0)
        await bek(2.5)
        es = kutu.sonuc("arm_disarm")
        denet("kontrol kapaliyken P1 komut gondermiyor",
              bool(es) and es[0].get("basari") is False
              and es[0].get("sebep") == "joystick_kapali",
              json.dumps({"basari": es[0].get("basari"),
                          "sebep": es[0].get("sebep")}) if es else "-")

        # Temizlik: SITL kapat
        if bid:
            await g({"tip": "baglanti_durdur", "id": int(bid)})
            await bek(1.5)
            await g({"tip": "baglanti_sil", "id": int(bid)})
        await bek(1.5)
        gorev.cancel()

    sp.close()
    print("\n" + "=" * 70)
    print("SONUC: %d GECTI / %d KALDI" % (_gecti, len(_kaldi)))
    for k in _kaldi:
        print("  - " + k)
    print("=" * 70)
    return 1 if _kaldi else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
