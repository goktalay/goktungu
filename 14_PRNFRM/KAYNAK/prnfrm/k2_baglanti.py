"""Tek bir yazıcıya kalıcı WebSocket bağlantısı (aiohttp istemcisi).

Bağlantı koptuğunda üstel geri çekilme ile yeniden dener; sessizlikte
``ReqPrinterPara`` ile yoklar; kalp atışına ``ok`` yanıtı verir. Gelen
her JSON parça ``ham`` sözlüğüne birleştirilir (yazıcı yalnız değişen
alanları gönderir), ardından ``on_guncelleme`` geri çağrısı tetiklenir.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, Awaitable, Callable

import aiohttp

from . import k2_protokol as P

log = logging.getLogger("prnfrm.baglanti")

B_KOPUK = "kopuk"
B_BAGLANIYOR = "baglaniyor"
B_BAGLI = "bagli"

SESSIZLIK_YOKLAMA_SN = 10.0     # bu kadar veri gelmezse yokla
SESSIZLIK_KOPUK_SN = 40.0       # bu kadar veri gelmezse bağlantı ölü say
PARAM_ISTEK_SN = 5.0            # periyodik ReqPrinterPara
KUTU_ISTEK_SN = 300.0           # periyodik boxsInfo (CFS)
GERI_CEKILME_MIN = 1.0
GERI_CEKILME_MAX = 60.0

Geri = Callable[["YaziciBaglantisi"], Awaitable[None] | None]


class YaziciBaglantisi:
    def __init__(self, yazici_id: int, ip: str, port: int = P.WS_PORT,
                 on_guncelleme: Geri | None = None,
                 on_baglanti: Geri | None = None,
                 alt_protokol: str | None = P.ALT_PROTOKOL) -> None:
        self.yazici_id = yazici_id
        self.ip = ip
        self.port = port
        self.alt_protokol = alt_protokol
        self.on_guncelleme = on_guncelleme
        self.on_baglanti = on_baglanti
        self.ham: dict[str, Any] = {}
        self.baglanti = B_KOPUK
        self.son_veri: float | None = None
        self.son_hata = ""
        self.deneme = 0
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._gorev: asyncio.Task | None = None
        self._kapat = asyncio.Event()

    @property
    def url(self) -> str:
        return f"ws://{self.ip}:{self.port}"

    def baslat(self) -> None:
        if self._gorev is None or self._gorev.done():
            self._kapat.clear()
            self._gorev = asyncio.create_task(self._dongu(), name=f"yazici-{self.yazici_id}")

    async def durdur(self) -> None:
        self._kapat.set()
        if self._ws is not None and not self._ws.closed:
            try:
                await self._ws.close()
            except Exception:  # noqa: BLE001
                pass
        if self._gorev is not None:
            self._gorev.cancel()
            try:
                await self._gorev
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._gorev = None
        await self._durum_degistir(B_KOPUK)

    async def gonder(self, metin: str) -> bool:
        ws = self._ws
        if ws is None or ws.closed:
            return False
        try:
            await ws.send_str(metin)
            return True
        except Exception as e:  # noqa: BLE001
            self.son_hata = f"gönderim: {e}"
            return False

    async def komut(self, ad: str, deger: Any = None) -> bool:
        uret = {
            "duraklat": lambda: P.komut_duraklat(),
            "surdur": lambda: P.komut_surdur(),
            "durdur": lambda: P.komut_durdur(),
            "isik": lambda: P.komut_isik(bool(deger)),
            "nozul": lambda: P.komut_nozul_sicaklik(float(deger)),
            "tabla": lambda: P.komut_tabla_sicaklik(float(deger)),
            "fan": lambda: P.komut_fan(int(deger)),
        }.get(ad)
        if uret is None:
            raise ValueError(f"bilinmeyen komut: {ad}")
        return await self.gonder(uret())

    def ozet(self) -> dict:
        o = P.ozet(self.ham)
        if self.baglanti != B_BAGLI:
            o["durum"] = P.D_CEVRIMDISI
        o.update({
            "veri_var": bool(self.ham),
            "baglanti": self.baglanti,
            "son_veri": self.son_veri,
            "son_hata": self.son_hata,
        })
        return o

    # --- iç ---
    async def _durum_degistir(self, yeni: str) -> None:
        if yeni == self.baglanti:
            return
        self.baglanti = yeni
        if self.on_baglanti:
            r = self.on_baglanti(self)
            if asyncio.iscoroutine(r):
                await r

    async def _dongu(self) -> None:
        geri = GERI_CEKILME_MIN
        while not self._kapat.is_set():
            baslangic = time.monotonic()
            try:
                await self._durum_degistir(B_BAGLANIYOR)
                await self._oturum()
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                self.son_hata = str(e) or e.__class__.__name__
                log.debug("%s bağlantı hatası: %s", self.url, self.son_hata)
            await self._durum_degistir(B_KOPUK)
            if self._kapat.is_set():
                break
            if time.monotonic() - baslangic > 10:
                geri = GERI_CEKILME_MIN   # kararlı oturumdu, sıfırla
            self.deneme += 1
            bekle = min(geri * (1.0 + random.random() * 0.3), GERI_CEKILME_MAX)
            geri = min(geri * 1.8, GERI_CEKILME_MAX)
            try:
                await asyncio.wait_for(self._kapat.wait(), timeout=bekle)
            except asyncio.TimeoutError:
                pass

    async def _oturum(self) -> None:
        protokoller = [self.alt_protokol] if self.alt_protokol else []
        zaman = aiohttp.ClientTimeout(total=None, sock_connect=5)
        async with aiohttp.ClientSession(timeout=zaman) as oturum:
            ws_zaman = aiohttp.ClientWSTimeout(ws_receive=SESSIZLIK_KOPUK_SN, ws_close=5)
            async with oturum.ws_connect(self.url, protocols=protokoller,
                                         heartbeat=None, autoping=True, timeout=ws_zaman,
                                         max_msg_size=4 * 1024 * 1024) as ws:
                self._ws = ws
                self.son_hata = ""
                self.deneme = 0
                await self._durum_degistir(B_BAGLI)
                await ws.send_str(P.istek_get(P.GET_YAZICI_PARAM))
                await ws.send_str(P.istek_get(P.GET_KUTU_BILGISI))
                yoklayici = asyncio.create_task(self._yoklayici(ws))
                try:
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self._mesaj(ws, msg.data)
                        elif msg.type in (aiohttp.WSMsgType.CLOSED,
                                          aiohttp.WSMsgType.CLOSE,
                                          aiohttp.WSMsgType.ERROR):
                            break
                finally:
                    yoklayici.cancel()
                    self._ws = None
        raise ConnectionError("oturum kapandı")

    async def _yoklayici(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        son_param = son_kutu = time.monotonic()
        while not ws.closed:
            await asyncio.sleep(1.0)
            simdi = time.monotonic()
            sessiz = simdi - (self.son_veri or simdi)
            if simdi - son_param >= PARAM_ISTEK_SN or sessiz >= SESSIZLIK_YOKLAMA_SN:
                await ws.send_str(P.istek_get(P.GET_YAZICI_PARAM))
                son_param = simdi
            if simdi - son_kutu >= KUTU_ISTEK_SN:
                await ws.send_str(P.istek_get(P.GET_KUTU_BILGISI))
                son_kutu = simdi

    async def _mesaj(self, ws: aiohttp.ClientWebSocketResponse, metin: str) -> None:
        self.son_veri = time.time()
        veri = P.cozumle(metin)
        if veri is None:
            return
        if P.kalp_atisi_mi(veri):
            await ws.send_str(P.KALP_ATISI_YANIT)
            return
        self.ham.update(P.sayilastir(veri))
        if self.on_guncelleme:
            r = self.on_guncelleme(self)
            if asyncio.iscoroutine(r):
                await r
