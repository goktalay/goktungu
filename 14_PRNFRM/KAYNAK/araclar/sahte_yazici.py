#!/usr/bin/env python3
"""Sahte Creality K2 yazıcı simülatörü — donanım olmadan test ve tanıtım için.

Her sahte yazıcı ayrı bir loopback adresinde (127.0.0.2, 127.0.0.3, …) 9999
portunu dinler; böylece ağ tarayıcısı ``127.0.0.0/28`` üzerinde gerçekçi
biçimde denenir. Telemetri, kalp atışı ve ``set`` komutları (pause/stop/
lightSw/nozzleTempControl) K2 protokolünün topluluk gözlemlerine göre taklit
edilir.

Kullanım: ``python3 araclar/sahte_yazici.py --adet 5``
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiohttp import WSMsgType, web  # noqa: E402

from prnfrm import k2_protokol as P  # noqa: E402


class SahteYazici:
    def __init__(self, ip: str, sira: int, port: int = P.WS_PORT, hizli: bool = False) -> None:
        self.ip, self.port, self.sira = ip, port, sira
        self.hizli = hizli
        self.hostname = f"K2Plus-{sira:02d}"
        self.durum = {
            "hostname": self.hostname, "model": "K2 Plus", "modelVersion": "V1.2.3.4",
            "state": 0, "deviceState": 0, "printFileName": "", "printProgress": 0,
            "printLeftTime": 0, "printJobTime": 0, "layer": 0, "TotalLayer": 0,
            "nozzleTemp": 25.0, "targetNozzleTemp": 0, "bedTemp0": 24.0, "targetBedTemp0": 0,
            "boxTemp": 26.0, "targetBoxTemp": 0, "fanPct": 0, "lightSw": 1,
            "curFeedratePct": 100, "materialStatus": 0, "err": {"errcode": 0, "key": ""},
        }
        self.istemciler: set[web.WebSocketResponse] = set()
        self.gelen_komutlar: list[dict] = []
        self._runner: web.AppRunner | None = None
        self._gorev: asyncio.Task | None = None

    async def baslat(self) -> None:
        app = web.Application()
        app.router.add_get("/", self._ws)
        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        await web.TCPSite(self._runner, self.ip, self.port).start()
        self._gorev = asyncio.create_task(self._dongu())

    async def durdur(self) -> None:
        if self._gorev:
            self._gorev.cancel()
        for ws in list(self.istemciler):
            await ws.close()
        if self._runner:
            await self._runner.cleanup()

    def baski_baslat(self, dosya: str = "parca.gcode", katman: int = 120) -> None:
        self.durum.update({"state": 1, "printFileName": dosya, "printProgress": 0,
                           "TotalLayer": katman, "layer": 0, "printLeftTime": katman * 30,
                           "printJobTime": 0, "targetNozzleTemp": 220, "targetBedTemp0": 60})

    async def _ws(self, istek: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(protocols=[P.ALT_PROTOKOL])
        await ws.prepare(istek)
        self.istemciler.add(ws)
        try:
            await ws.send_str(json.dumps(self.durum))
            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    break
                if msg.data == "ok":
                    continue
                try:
                    veri = json.loads(msg.data)
                except ValueError:
                    continue
                if veri.get("method") == "get":
                    await ws.send_str(json.dumps(self.durum))
                elif veri.get("method") == "set":
                    self._komut(veri.get("params") or {})
                    await ws.send_str(json.dumps(self.durum))
        finally:
            self.istemciler.discard(ws)
        return ws

    def _komut(self, p: dict) -> None:
        self.gelen_komutlar.append(p)
        if "pause" in p:
            if p["pause"] == 1 and self.durum["state"] == 1:
                self.durum["state"] = 5
            elif p["pause"] == 0 and self.durum["state"] == 5:
                self.durum["state"] = 1
        if p.get("stop") == 1:
            self.durum.update({"state": 4, "printProgress": 0, "printFileName": "",
                               "targetNozzleTemp": 0, "targetBedTemp0": 0})
        if "lightSw" in p:
            self.durum["lightSw"] = int(p["lightSw"])
        if "nozzleTempControl" in p:
            self.durum["targetNozzleTemp"] = float(p["nozzleTempControl"])
        if isinstance(p.get("bedTempControl"), dict):
            self.durum["targetBedTemp0"] = float(p["bedTempControl"].get("val", 0))

    async def _yayin(self, veri: dict) -> None:
        metin = json.dumps(veri)
        for ws in list(self.istemciler):
            try:
                await ws.send_str(metin)
            except Exception:  # noqa: BLE001
                pass

    async def _dongu(self) -> None:
        sayac = 0
        adim = 0.2 if self.hizli else 2.0
        while True:
            await asyncio.sleep(adim)
            sayac += 1
            d = self.durum
            for anahtar, hedef in (("nozzleTemp", "targetNozzleTemp"), ("bedTemp0", "targetBedTemp0")):
                h = d[hedef] or 25.0
                d[anahtar] = round(d[anahtar] + (h - d[anahtar]) * 0.25 + random.uniform(-0.3, 0.3), 1)
            if d["state"] == 1:
                d["printProgress"] = min(100, d["printProgress"] + (5 if self.hizli else 1))
                d["layer"] = int(d["TotalLayer"] * d["printProgress"] / 100)
                d["printJobTime"] += int(adim)
                d["printLeftTime"] = max(0, d["printLeftTime"] - int(adim))
                d["fanPct"] = 100
                if d["printProgress"] >= 100:
                    d["state"] = 2
                    d["targetNozzleTemp"] = d["targetBedTemp0"] = 0
            degisen = {k: d[k] for k in ("nozzleTemp", "bedTemp0", "boxTemp", "state",
                                        "printProgress", "layer", "printLeftTime", "printJobTime",
                                        "fanPct", "lightSw", "targetNozzleTemp", "targetBedTemp0")}
            await self._yayin(degisen)
            if sayac % (5 if self.hizli else 3) == 0:
                await self._yayin({"ModeCode": "heart_beat", "hostname": self.hostname,
                                   "timestamp": int(time.time())})


async def filo_kur(adet: int, baslangic: int = 2, port: int = P.WS_PORT,
                   hizli: bool = False) -> list[SahteYazici]:
    yazicilar = []
    for i in range(adet):
        y = SahteYazici(f"127.0.0.{baslangic + i}", i + 1, port, hizli)
        await y.baslat()
        yazicilar.append(y)
    return yazicilar


async def ana(argv=None) -> None:
    p = argparse.ArgumentParser(description="Sahte K2 yazıcı filosu")
    p.add_argument("--adet", type=int, default=5)
    p.add_argument("--baslangic", type=int, default=2, help="127.0.0.<N> başlangıcı")
    p.add_argument("--port", type=int, default=P.WS_PORT)
    n = p.parse_args(argv)
    yazicilar = await filo_kur(n.adet, n.baslangic, n.port)
    for i, y in enumerate(yazicilar):
        if i % 2 == 0:
            y.baski_baslat(f"parca_{i + 1}.gcode", katman=100 + i * 10)
        print(f"{y.hostname}  ws://{y.ip}:{y.port}")
    print("Ctrl+C ile durdurun. Tarama için CIDR: 127.0.0.0/28")
    try:
        await asyncio.Event().wait()
    finally:
        for y in yazicilar:
            await y.durdur()


if __name__ == "__main__":
    try:
        asyncio.run(ana())
    except KeyboardInterrupt:
        pass
