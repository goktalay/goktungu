"""Ağ tarayıcı: alt ağdaki 9999 portunu paralel yoklar, bulunanlara kimlik sorar."""
from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import shutil
import socket
import subprocess
import time
from typing import Awaitable, Callable

import aiohttp

from . import k2_protokol as P

log = logging.getLogger("prnfrm.tarayici")

EN_FAZLA_HOST = 4096      # /20'den büyük alt ağ taranmaz (bilinçli sınır)
KIMLIK_BEKLEME_SN = 4.0


def yerel_aglar() -> list[dict]:
    """Makinedeki IPv4 arayüzlerini CIDR olarak listeler (loopback hariç)."""
    sonuc: list[dict] = []
    if shutil.which("ip"):
        try:
            cikti = subprocess.run(["ip", "-j", "-4", "addr"], capture_output=True,
                                   text=True, timeout=3, check=False).stdout
            for arayuz in json.loads(cikti or "[]"):
                for adres in arayuz.get("addr_info", []):
                    ip, onek = adres.get("local"), adres.get("prefixlen")
                    if not ip or onek is None:
                        continue
                    ag = ipaddress.ip_network(f"{ip}/{onek}", strict=False)
                    if ag.is_loopback or ag.is_link_local:
                        continue
                    sonuc.append({"arayuz": arayuz.get("ifname", ""), "ip": ip,
                                  "cidr": str(ag), "host_sayisi": ag.num_addresses})
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            log.debug("ip addr okunamadı: %s", e)
    if not sonuc:
        # Yedek yol: varsayılan rotanın kaynak IP'si + /24 varsayımı
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("10.255.255.255", 1))
                ip = s.getsockname()[0]
            ag = ipaddress.ip_network(f"{ip}/24", strict=False)
            sonuc.append({"arayuz": "", "ip": ip, "cidr": str(ag),
                          "host_sayisi": ag.num_addresses})
        except OSError:
            pass
    return sonuc


def hostlar(cidr: str) -> list[str]:
    ag = ipaddress.ip_network(cidr.strip(), strict=False)
    if ag.version != 4:
        raise ValueError("yalnız IPv4 desteklenir")
    if ag.num_addresses > EN_FAZLA_HOST:
        raise ValueError(f"alt ağ çok büyük ({ag.num_addresses} adres); en fazla /20")
    if ag.num_addresses <= 2:
        return [str(a) for a in ag]
    return [str(a) for a in ag.hosts()]


async def port_acik_mi(ip: str, port: int, zaman_asimi: float) -> bool:
    try:
        _, w = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=zaman_asimi)
    except (OSError, asyncio.TimeoutError):
        return False
    w.close()
    try:
        await w.wait_closed()
    except OSError:
        pass
    return True


async def kimlik_sor(ip: str, port: int = P.WS_PORT,
                     bekleme: float = KIMLIK_BEKLEME_SN) -> dict:
    """WebSocket açar, kısa süre telemetri toplayıp hostname/model döndürür."""
    bilgi = {"ip": ip, "port": port, "hostname": "", "model": "", "model_surum": "",
             "ws": False, "hata": ""}
    ham: dict = {}
    son = time.monotonic() + bekleme
    try:
        zaman = aiohttp.ClientTimeout(total=bekleme + 2, sock_connect=3)
        async with aiohttp.ClientSession(timeout=zaman) as oturum:
            async with oturum.ws_connect(f"ws://{ip}:{port}", protocols=[P.ALT_PROTOKOL],
                                         heartbeat=None) as ws:
                bilgi["ws"] = True
                await ws.send_str(P.istek_get(P.GET_YAZICI_PARAM))
                while time.monotonic() < son:
                    kalan = son - time.monotonic()
                    try:
                        msg = await ws.receive(timeout=max(0.1, kalan))
                    except asyncio.TimeoutError:
                        break
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        break
                    veri = P.cozumle(msg.data)
                    if veri is None:
                        continue
                    if P.kalp_atisi_mi(veri):
                        await ws.send_str(P.KALP_ATISI_YANIT)
                        continue
                    ham.update(veri)
                    if ham.get("hostname") and ham.get("model"):
                        break
    except Exception as e:  # noqa: BLE001
        bilgi["hata"] = str(e) or e.__class__.__name__
    o = P.ozet(ham)
    bilgi.update({"hostname": o["hostname"], "model": o["model"],
                  "model_surum": o["model_surum"]})
    return bilgi


class Tarama:
    """Tek bir tarama işi; ilerleme ve sonuçları taşır."""

    def __init__(self, cidr: str, port: int = P.WS_PORT, eszamanli: int = 256,
                 zaman_asimi: float = 0.7,
                 on_ilerleme: Callable[["Tarama"], Awaitable[None] | None] | None = None) -> None:
        self.cidr = cidr
        self.port = port
        self.eszamanli = eszamanli
        self.zaman_asimi = zaman_asimi
        self.on_ilerleme = on_ilerleme
        self.id = int(time.time() * 1000)
        self.baslangic = time.time()
        self.bitis: float | None = None
        self.toplam = 0
        self.taranan = 0
        self.asama = "hazir"      # hazir | port | kimlik | bitti | iptal | hata
        self.hata = ""
        self.bulunan: list[dict] = []
        self._iptal = asyncio.Event()

    def iptal(self) -> None:
        self._iptal.set()

    def sozluk(self) -> dict:
        return {"id": self.id, "cidr": self.cidr, "port": self.port, "asama": self.asama,
                "toplam": self.toplam, "taranan": self.taranan, "hata": self.hata,
                "bulunan": self.bulunan, "baslangic": self.baslangic, "bitis": self.bitis}

    async def _bildir(self) -> None:
        if self.on_ilerleme:
            r = self.on_ilerleme(self)
            if asyncio.iscoroutine(r):
                await r

    async def calistir(self) -> None:
        try:
            liste = hostlar(self.cidr)
        except ValueError as e:
            self.asama, self.hata = "hata", str(e)
            await self._bildir()
            return
        self.toplam = len(liste)
        self.asama = "port"
        await self._bildir()
        sema = asyncio.Semaphore(self.eszamanli)
        acik: list[str] = []
        son_bildirim = time.monotonic()

        async def tek(ip: str) -> None:
            nonlocal son_bildirim
            if self._iptal.is_set():
                return
            async with sema:
                if await port_acik_mi(ip, self.port, self.zaman_asimi):
                    acik.append(ip)
            self.taranan += 1
            if time.monotonic() - son_bildirim > 0.5:
                son_bildirim = time.monotonic()
                await self._bildir()

        await asyncio.gather(*(tek(ip) for ip in liste))
        if self._iptal.is_set():
            self.asama = "iptal"
            self.bitis = time.time()
            await self._bildir()
            return
        self.asama = "kimlik"
        await self._bildir()
        acik.sort(key=lambda a: tuple(int(x) for x in a.split(".")))
        kimlikler = await asyncio.gather(*(kimlik_sor(ip, self.port) for ip in acik))
        self.bulunan = [k for k in kimlikler if k["ws"]]
        self.asama = "iptal" if self._iptal.is_set() else "bitti"
        self.bitis = time.time()
        await self._bildir()
