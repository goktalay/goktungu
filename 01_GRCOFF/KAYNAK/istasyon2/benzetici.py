#!/usr/bin/env python3
"""Yer Istasyonu 2 - ESP32-S3 benzeticisi.

README_istasyon2.md'de tanimlanan protokolu BIREBIR uretir. Gercek donanim
olmadan test HTML'inin dogrulanmasi icin kullanilir.

Iki calisma kipi:
  --pty     : sahte seri port (PTY) acar, pyserial ile baglanilabilir
  --ws PORT : WebSocket sunucusu acar, test HTML'i dogrudan baglanir

Protokol notlari (belgeden):
  - Her satir TAM durum iceren JSON, \n ile biter
  - PC -> ESP32 komutlari DUZ METIN: LED,P3,ON | LED,ALL,OFF | PING
  - PING cevabi "PONG" (JSON DEGIL)
  - P8-P11/T1/T2 icin LED komutu SESSIZCE yok sayilir
  - Joystick esigi 40 birim (JOYSTICK_THRESHOLD)
  - Buton debounce ~25 ms
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import random
import sys
import time

# --- Firmware sabitleri (belgeden) ---------------------------------------
BAUD = 115200
JOYSTICK_THRESHOLD = 40
DEBOUNCE_MS = 25
ADC_MAKS = 4095

BUTONLAR = [f"P{i}" for i in range(1, 12)]      # P1..P11
LEDLI = [f"P{i}" for i in range(1, 8)]          # P1..P7 (yalniz bunlarda LED var)
EKSENLER = ["J1_X", "J1_Y", "J2_X", "J2_Y"]
T2_POZ = ("UP", "CENTER", "DOWN")
# v2.4.44: cantada panel joysticklerinden AYRI 2 adet 2 eksenli joystick
# var (dron ucurmak icin). Firmware bunlari ayni JSON'un `joysticks`
# alaninda ek anahtar olarak basar. --ek-eksen ile benzetilir.
EK_EKSENLER = ["J3_X", "J3_Y", "J4_X", "J4_Y"]


class Istasyon2Benzetici:
    """ESP32 firmware davranisini taklit eder."""

    def __init__(self, gurultu: bool = True, ek_eksen: bool = True):
        self.gurultu = gurultu
        # Cantadaki ek dron joysticklerini de bas (varsayilan: evet)
        self.eksen_listesi = list(EKSENLER) + (
            list(EK_EKSENLER) if ek_eksen else [])
        # Gercek donanimda orta nokta tam 2048 degildir; belge bunu vurguluyor.
        # Her eksene kalici bir sapma veriyoruz ki PC tarafi kalibrasyonu
        # gercekten sinanabilsin.
        self.merkez = {e: 2048 + random.randint(-40, 40)
                       for e in self.eksen_listesi}
        self.buttons = {b: 0 for b in BUTONLAR}
        self.toggles = {"T1": 0, "T2": "CENTER"}
        self.joysticks = dict(self.merkez)
        self.leds = {p: 0 for p in LEDLI}
        # Eksigin gonderildigi son deger (esik bu referansa gore)
        self._son_gonderilen = dict(self.joysticks)
        self._son_degisim = {b: 0.0 for b in BUTONLAR}
        self._yoksayilan_led = 0   # olculebilir: sessizce yok sayilan komut sayisi

    # -- durum uretimi ---------------------------------------------------
    def durum_json(self, event: str) -> str:
        return json.dumps({
            "event": event,
            "buttons": dict(self.buttons),
            "toggles": dict(self.toggles),
            "joysticks": {k: int(v) for k, v in self.joysticks.items()},
            "leds": dict(self.leds),
        }, separators=(",", ":"))

    # -- PC -> ESP32 komut isleme ----------------------------------------
    def komut_isle(self, satir: str):
        """Duz metin komutu isler. Cevap listesi dondurur (gonderilecek satirlar)."""
        satir = (satir or "").strip()
        if not satir:
            return []                                  # bos satir sessizce yok sayilir
        if satir.upper() == "PING":
            return ["PONG"]                            # JSON DEGIL
        parca = satir.split(",")
        if len(parca) != 3 or parca[0].strip().upper() != "LED":
            return []                                  # gecersiz format sessizce yok sayilir
        kanal = parca[1].strip().upper()
        eylem = parca[2].strip().upper()
        if eylem not in ("ON", "OFF"):
            return []
        deger = 1 if eylem == "ON" else 0
        if kanal == "ALL":
            for p in LEDLI:
                self.leds[p] = deger
            return [self.durum_json("LED_CMD")]
        if kanal in self.leds:
            self.leds[kanal] = deger
            return [self.durum_json("LED_CMD")]
        # P8-P11 / T1 / T2 -> LED yok, SESSIZCE yok sayilir
        self._yoksayilan_led += 1
        return []

    # -- fiziksel etki benzetimi -----------------------------------------
    def buton_bas(self, ad: str, basili: bool):
        """Buton durumunu degistirir; debounce suresi gecmediyse yok sayar."""
        if ad not in self.buttons:
            return None
        simdi = time.monotonic()
        if (simdi - self._son_degisim[ad]) * 1000.0 < DEBOUNCE_MS:
            return None                                # debounce
        yeni = 1 if basili else 0
        if self.buttons[ad] == yeni:
            return None
        self.buttons[ad] = yeni
        self._son_degisim[ad] = simdi
        return self.durum_json(ad)

    def toggle_ayarla(self, ad: str, deger):
        if ad == "T1":
            yeni = 1 if str(deger) in ("1", "True", "true", "ON") else 0
            if self.toggles["T1"] == yeni:
                return None
            self.toggles["T1"] = yeni
            return self.durum_json("T1")
        if ad == "T2":
            v = str(deger).upper()
            if v not in T2_POZ or self.toggles["T2"] == v:
                return None
            self.toggles["T2"] = v
            return self.durum_json("T2")
        return None

    def eksen_ayarla(self, eksen: str, ham: int):
        """Eksen degerini ayarlar; ESP32 esigini uygular (40 birim)."""
        if eksen not in self.joysticks:
            return None
        ham = max(0, min(ADC_MAKS, int(ham)))
        self.joysticks[eksen] = ham
        if abs(ham - self._son_gonderilen[eksen]) >= JOYSTICK_THRESHOLD:
            self._son_gonderilen[eksen] = ham
            return self.durum_json(eksen)
        return None                                    # esigin altinda: GONDERILMEZ

    # -- sinav komutlari (yalniz benzeticide; gercek firmware'de YOK) -----
    def sim_komut(self, satir: str):
        """`SIM,...` sinav komutlarini isler.

        Gercek ESP32 firmware'inde bu komutlar YOKTUR; benzeticide
        fiziksel etkiyi (dugmeye basmak, kolu cevirmek, cubugu itmek)
        betikten tetiklemek icin vardir. Boylece protokol sinavi insan
        eli gerektirmez.
            SIM,BTN,P3,1        dugmeye bas / birak
            SIM,TGL,T2,UP       kolu cevir
            SIM,JOY,J1_X,3500   panel cubugunu it
            SIM,EKJOY,J3_Y,3800 ek dron cubugunu it
        """
        p = [x.strip() for x in satir.split(",")]
        if len(p) != 4 or p[0].upper() != "SIM":
            return []
        tur = p[1].upper()
        if tur == "BTN":
            c = self.buton_bas(p[2].upper(), p[3] not in ("0", ""))
            return [c] if c else []
        if tur == "TGL":
            c = self.toggle_ayarla(p[2].upper(), p[3])
            return [c] if c else []
        if tur in ("JOY", "EKJOY"):
            try:
                c = self.eksen_ayarla(p[2].upper(), int(p[3]))
            except ValueError:
                return []
            return [c] if c else []
        return []

    def gurultu_uygula(self):
        """Donanim gurultusunu taklit eder; esigi asmaz, mesaj uretmez."""
        if not self.gurultu:
            return
        for e in self.eksen_listesi:
            sapma = random.randint(-8, 8)
            yeni = max(0, min(ADC_MAKS, self.joysticks[e] + sapma))
            self.joysticks[e] = yeni


# ---------------------------------------------------------------------------
# WebSocket kipi: test HTML'i dogrudan baglanir
# ---------------------------------------------------------------------------
async def ws_kipi(port: int, gurultu: bool, ek_eksen: bool = True):
    import websockets

    sim = Istasyon2Benzetici(gurultu=gurultu, ek_eksen=ek_eksen)
    istemciler: set = set()

    async def yayinla(satir: str):
        if not satir:
            return
        olu = []
        for w in list(istemciler):
            try:
                await w.send(satir)
            except Exception:
                olu.append(w)
        for w in olu:
            istemciler.discard(w)

    async def islemci(ws):
        istemciler.add(ws)
        # Boot davranisi: baglanan her istemciye READY gonderilir
        await ws.send(sim.durum_json("READY"))
        try:
            async for mesaj in ws:
                # Test sayfasindan iki tur girdi gelir:
                #   1) duz metin ESP32 komutu (LED,.. / PING)
                #   2) {"sim": ...} ile fiziksel etki benzetimi
                ham = mesaj.strip()
                if ham.startswith("{"):
                    try:
                        d = json.loads(ham)
                    except Exception:
                        continue
                    s = d.get("sim") or {}
                    cikti = None
                    if s.get("tur") == "buton":
                        cikti = sim.buton_bas(s.get("ad"), bool(s.get("basili")))
                    elif s.get("tur") == "toggle":
                        cikti = sim.toggle_ayarla(s.get("ad"), s.get("deger"))
                    elif s.get("tur") == "eksen":
                        cikti = sim.eksen_ayarla(s.get("ad"), s.get("deger"))
                    if cikti:
                        await yayinla(cikti)
                else:
                    for cevap in sim.komut_isle(ham):
                        await yayinla(cevap)
        except Exception:
            pass
        finally:
            istemciler.discard(ws)

    async def gurultu_dongusu():
        while True:
            await asyncio.sleep(0.1)
            sim.gurultu_uygula()

    print(f"[BENZETICI] WebSocket hazir: ws://0.0.0.0:{port}", flush=True)
    asyncio.create_task(gurultu_dongusu())
    async with websockets.serve(islemci, "0.0.0.0", port):
        await asyncio.Future()


# ---------------------------------------------------------------------------
# PTY kipi: gercek seri port gibi davranir (pyserial ile baglanilir)
# ---------------------------------------------------------------------------
def pty_kipi(gurultu: bool, otomatik: bool, ek_eksen: bool = True):
    import pty
    import select
    import termios
    import tty

    ana, ikincil = pty.openpty()
    yol = os.ttyname(ikincil)
    try:
        tty.setraw(ana)
    except Exception:
        pass
    print(f"[BENZETICI] Sahte seri port: {yol}", flush=True)
    print(f"[BENZETICI] Baud {BAUD} (PTY'de baud etkisizdir, protokol aynidir)",
          flush=True)
    sys.stdout.flush()

    sim = Istasyon2Benzetici(gurultu=gurultu, ek_eksen=ek_eksen)
    os.write(ana, (sim.durum_json("READY") + "\n").encode())

    tampon = b""
    t0 = time.monotonic()
    son_hareket = 0.0
    try:
        while True:
            r, _, _ = select.select([ana], [], [], 0.05)
            if r:
                try:
                    veri = os.read(ana, 4096)
                except OSError:
                    break
                if not veri:
                    break
                tampon += veri
                while b"\n" in tampon:
                    satir, tampon = tampon.split(b"\n", 1)
                    metin = satir.decode("utf-8", "ignore")
                    # SIM,... sinav komutlari once denenir; firmware
                    # komutlariyla (LED/PING) cakismaz.
                    cevaplar = sim.sim_komut(metin) or sim.komut_isle(metin)
                    for cevap in cevaplar:
                        os.write(ana, (cevap + "\n").encode())
            sim.gurultu_uygula()
            if otomatik:
                # Olculebilir hareket: J1_X sinus, her ~2 sn P1 basili/birakilir
                t = time.monotonic() - t0
                hedef = int(2048 + 900 * math.sin(t * 0.8))
                cikti = sim.eksen_ayarla("J1_X", hedef)
                if cikti:
                    os.write(ana, (cikti + "\n").encode())
                if t - son_hareket > 2.0:
                    son_hareket = t
                    c = sim.buton_bas("P1", sim.buttons["P1"] == 0)
                    if c:
                        os.write(ana, (c + "\n").encode())
    except KeyboardInterrupt:
        pass
    finally:
        os.close(ana)
        os.close(ikincil)


def main():
    ap = argparse.ArgumentParser(description="Yer Istasyonu 2 benzeticisi")
    ap.add_argument("--ws", type=int, default=0, help="WebSocket portu")
    ap.add_argument("--pty", action="store_true", help="Sahte seri port kipi")
    ap.add_argument("--otomatik", action="store_true",
                    help="PTY kipinde otomatik hareket uret")
    ap.add_argument("--gurultusuz", action="store_true", help="ADC gurultusu kapali")
    ap.add_argument("--ek-eksensiz", action="store_true",
                    help="cantadaki ek dron joysticklerini basma")
    a = ap.parse_args()
    if a.pty:
        pty_kipi(gurultu=not a.gurultusuz, otomatik=a.otomatik,
                 ek_eksen=not a.ek_eksensiz)
    elif a.ws:
        asyncio.run(ws_kipi(a.ws, gurultu=not a.gurultusuz,
                            ek_eksen=not a.ek_eksensiz))
    else:
        ap.error("--ws PORT veya --pty gerekli")


if __name__ == "__main__":
    main()
