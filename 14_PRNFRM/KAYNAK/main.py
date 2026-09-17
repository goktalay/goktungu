#!/usr/bin/env python3
"""PRNFRM giriş noktası: ``python3 main.py --port 8090``"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aiohttp import web  # noqa: E402

from prnfrm.ayarlar import ayarlari_oku  # noqa: E402
from prnfrm.filo import Filo  # noqa: E402
from prnfrm.surum import FIRMA, SURUM, URUN_ADI  # noqa: E402
from prnfrm.veritabani import Veritabani  # noqa: E402
from prnfrm.web import uygulama_olustur  # noqa: E402


async def calistir(argv: list[str] | None = None) -> None:
    ayar = ayarlari_oku(argv)
    logging.basicConfig(level=getattr(logging, ayar.log_seviye, logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    log = logging.getLogger("prnfrm")
    vt = Veritabani(ayar.veritabani)
    filo = Filo(vt)
    await filo.baslat()
    app = uygulama_olustur(filo)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, ayar.host, ayar.port)
    await site.start()
    log.info("%s %s — %s — http://%s:%d/", URUN_ADI, SURUM, FIRMA, ayar.host, ayar.port)
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        vt.kapat()


if __name__ == "__main__":
    try:
        asyncio.run(calistir())
    except KeyboardInterrupt:
        pass
