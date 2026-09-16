#!/usr/bin/env python3
"""Yer Istasyonu 2 - seri port <-> WebSocket koprusu.

GERCEK donanim icin: ESP32-S3'un UART portunu okur, gelen her satiri
WebSocket ile test sayfasina basar; sayfadan gelen duz metin komutlari
(LED,.. / PING) seri porta yazar.

Bu koprunun mimarisi GCS entegrasyonunda kullanilacak yolun aynisidir
(tarayici seri porta dogrudan erisemez).

Kullanim:
    python3 kopru.py                      # portlari listeler
    python3 kopru.py COM7                 # Windows
    python3 kopru.py /dev/ttyUSB0 8765    # Linux, port secmeli
    python3 kopru.py /dev/pts/4           # benzetici PTY'sine baglanir

Baglanti kopmasi durumunda 2 sn arayla yeniden dener; sayfaya durum
bildirimi {"kopru": {...}} olarak gonderilir (ESP32 JSON'undan ayirt
edilebilmesi icin ayri anahtar kullanildi).
"""
from __future__ import annotations

import asyncio
import json
import sys
import threading
import time

BAUD = 115200
VARSAYILAN_PORT = 8765


def portlari_listele():
    try:
        from serial.tools import list_ports
    except Exception as h:
        print(f"pyserial yok: {h}\nKurulum: pip install pyserial")
        return
    bulunan = list(list_ports.comports())
    if not bulunan:
        print("Seri port bulunamadi.")
        return
    print("Bulunan seri portlar:")
    for p in bulunan:
        print(f"  {p.device:20s} {p.description}")
    print("\nNOT: ESP32-S3 iki port olarak gorunur. UART/COM portunu secin;")
    print("     native USB portu yalniz firmware yukleme icindir.")


class SeriKopru:
    """Seri portu ayri is parcaciginda okur, satirlari kuyruga basar."""

    def __init__(self, yol: str, dongu: asyncio.AbstractEventLoop,
                 kuyruk: asyncio.Queue):
        self.yol = yol
        self.dongu = dongu
        self.kuyruk = kuyruk
        self.sp = None
        self.calisiyor = True
        self.baglandi = False
        self.sayac_alinan = 0
        self.sayac_gonderilen = 0

    def _bildir(self, satir: str):
        self.dongu.call_soon_threadsafe(self.kuyruk.put_nowait, satir)

    def _durum(self, **k):
        self._bildir(json.dumps({"kopru": k}, separators=(",", ":")))

    def dongu_calistir(self):
        import serial
        tampon = b""
        while self.calisiyor:
            # --- baglanti kurma ---
            if self.sp is None:
                try:
                    self.sp = serial.Serial(self.yol, BAUD, timeout=0.1)
                    self.baglandi = True
                    tampon = b""
                    print(f"[KOPRU] Acildi: {self.yol} @ {BAUD}", flush=True)
                    self._durum(durum="acik", port=self.yol, baud=BAUD)
                except Exception as h:
                    self.baglandi = False
                    self._durum(durum="hata", hata=str(h), port=self.yol)
                    print(f"[KOPRU] Acilamadi ({h}); 2 sn sonra yeniden...",
                          flush=True)
                    time.sleep(2.0)
                    continue
            # --- okuma ---
            try:
                veri = self.sp.read(256)
            except Exception as h:
                # Windows'ta port cekilirse ReadFile failed gelir (belge md.6)
                print(f"[KOPRU] Okuma hatasi: {h}", flush=True)
                self._durum(durum="koptu", hata=str(h))
                self._kapat()
                time.sleep(2.0)
                continue
            if veri:
                tampon += veri
                while b"\n" in tampon:
                    satir, tampon = tampon.split(b"\n", 1)
                    s = satir.decode("utf-8", "ignore").strip()
                    if s:
                        self.sayac_alinan += 1
                        self._bildir(s)
        self._kapat()

    def yaz(self, satir: str) -> bool:
        """Duz metin komutu seri porta yazar."""
        if not self.sp:
            return False
        try:
            self.sp.write((satir.strip() + "\n").encode())
            self.sp.flush()
            self.sayac_gonderilen += 1
            return True
        except Exception as h:
            print(f"[KOPRU] Yazma hatasi: {h}", flush=True)
            return False

    def _kapat(self):
        # Belge md.6: portu her zaman duzgun kapat
        if self.sp:
            try:
                self.sp.close()
            except Exception:
                pass
        self.sp = None
        self.baglandi = False

    def dur(self):
        self.calisiyor = False


async def calistir(yol: str, ws_port: int):
    import websockets

    dongu = asyncio.get_running_loop()
    kuyruk: asyncio.Queue = asyncio.Queue()
    kopru = SeriKopru(yol, dongu, kuyruk)
    threading.Thread(target=kopru.dongu_calistir, daemon=True).start()

    istemciler: set = set()

    async def islemci(ws):
        istemciler.add(ws)
        await ws.send(json.dumps({"kopru": {
            "durum": "acik" if kopru.baglandi else "bekliyor",
            "port": yol, "baud": BAUD}}, separators=(",", ":")))
        try:
            async for mesaj in ws:
                # Sayfadan gelen her sey ESP32'ye giden DUZ METIN komuttur
                kopru.yaz(mesaj)
        except Exception:
            pass
        finally:
            istemciler.discard(ws)

    async def yayin_dongusu():
        while True:
            satir = await kuyruk.get()
            for w in list(istemciler):
                try:
                    await w.send(satir)
                except Exception:
                    istemciler.discard(w)

    print(f"[KOPRU] WebSocket: ws://0.0.0.0:{ws_port}", flush=True)
    print(f"[KOPRU] Test sayfasinda bu adresi girin.", flush=True)
    asyncio.create_task(yayin_dongusu())
    try:
        async with websockets.serve(islemci, "0.0.0.0", ws_port):
            await asyncio.Future()
    finally:
        kopru.dur()


def main():
    if len(sys.argv) < 2:
        portlari_listele()
        print(f"\nKullanim: python3 kopru.py <PORT> [WS_PORT={VARSAYILAN_PORT}]")
        return 0
    yol = sys.argv[1]
    ws_port = int(sys.argv[2]) if len(sys.argv) > 2 else VARSAYILAN_PORT
    try:
        asyncio.run(calistir(yol, ws_port))
    except KeyboardInterrupt:
        print("\n[KOPRU] Kapatildi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
