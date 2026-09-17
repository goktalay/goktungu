"""aiohttp web uygulaması: statik arayüz, REST API, tarayıcıya WebSocket yayını."""
from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import weakref
from pathlib import Path

from aiohttp import WSMsgType, web

from . import k2_protokol as P
from .filo import Filo
from .surum import FIRMA, SURUM, URUN_ADI, URUN_KODU

log = logging.getLogger("prnfrm.web")
FILO_ANAHTAR = web.AppKey("filo", Filo)
WS_ISTEMCILER = web.AppKey("ws_istemciler", weakref.WeakSet)
WEB_DIZIN = Path(__file__).resolve().parent.parent / "web"


def _json(veri, durum: int = 200) -> web.Response:
    return web.json_response(veri, status=durum, dumps=lambda v: json.dumps(v, ensure_ascii=False))


def _hata(mesaj: str, durum: int = 400) -> web.Response:
    return _json({"hata": mesaj}, durum)


async def _govde(istek: web.Request) -> dict:
    try:
        veri = await istek.json()
    except (ValueError, json.JSONDecodeError):
        raise web.HTTPBadRequest(text="geçersiz JSON")
    if not isinstance(veri, dict):
        raise web.HTTPBadRequest(text="JSON nesnesi bekleniyor")
    return veri


def _ip_dogrula(ip: str) -> str:
    try:
        return str(ipaddress.ip_address(ip.strip()))
    except ValueError:
        raise web.HTTPBadRequest(text=f"geçersiz IP: {ip}")


def uygulama_olustur(filo: Filo) -> web.Application:
    app = web.Application()
    app[FILO_ANAHTAR] = filo
    app[WS_ISTEMCILER] = weakref.WeakSet()

    async def yayin(mesaj: dict) -> None:
        metin = json.dumps(mesaj, ensure_ascii=False)
        for ws in list(app[WS_ISTEMCILER]):
            try:
                await ws.send_str(metin)
            except Exception:  # noqa: BLE001
                pass

    filo.yayinci_ekle(yayin)

    # --- sayfalar ---
    async def ana_sayfa(_):
        return web.FileResponse(WEB_DIZIN / "index.html")

    # --- API ---
    async def surum(_):
        return _json({"urun": URUN_KODU, "ad": URUN_ADI, "surum": SURUM, "firma": FIRMA})

    async def yazicilar(_):
        return _json({"yazicilar": filo.yazicilar_gorunum(), "sayilar": filo.ozet_sayilar()})

    async def yazici(istek):
        yid = int(istek.match_info["id"])
        if yid not in filo.kayitlar:
            return _hata("yazıcı bulunamadı", 404)
        return _json({"yazici": filo.yazici_gorunum(yid), "ham": filo.ham(yid),
                      "olaylar": filo.vt.olaylar(50, yid)})

    async def yazici_ekle(istek):
        v = await _govde(istek)
        ip = _ip_dogrula(str(v.get("ip", "")))
        if ip in filo.kayitli_ipler():
            return _hata("bu IP zaten kayıtlı", 409)
        port = int(v.get("port") or P.WS_PORT)
        kayit = await filo.yazici_ekle(str(v.get("ad", "")), ip, port,
                                       model=str(v.get("model", "")), hostname=str(v.get("hostname", "")),
                                       grup=str(v.get("grup", "")), notlar=str(v.get("notlar", "")))
        return _json({"yazici": kayit}, 201)

    async def toplu_ekle(istek):
        v = await _govde(istek)
        secilen = v.get("yazicilar")
        if not isinstance(secilen, list) or not secilen:
            return _hata("yazicilar listesi boş")
        eklenen, atlanan = [], []
        for s in secilen:
            if not isinstance(s, dict):
                continue
            try:
                ip = _ip_dogrula(str(s.get("ip", "")))
            except web.HTTPBadRequest:
                atlanan.append({"ip": s.get("ip"), "neden": "geçersiz IP"})
                continue
            if ip in filo.kayitli_ipler():
                atlanan.append({"ip": ip, "neden": "zaten kayıtlı"})
                continue
            kayit = await filo.yazici_ekle(str(s.get("ad", "")), ip, int(s.get("port") or P.WS_PORT),
                                           model=str(s.get("model", "")), hostname=str(s.get("hostname", "")),
                                           grup=str(s.get("grup", "")))
            eklenen.append(kayit)
        return _json({"eklenen": eklenen, "atlanan": atlanan}, 201)

    async def yazici_guncelle(istek):
        yid = int(istek.match_info["id"])
        v = await _govde(istek)
        alanlar = {}
        for k in ("ad", "grup", "notlar", "model"):
            if k in v:
                alanlar[k] = str(v[k])
        if "ip" in v:
            ip = _ip_dogrula(str(v["ip"]))
            if any(k["ip"] == ip and k["id"] != yid for k in filo.kayitlar.values()):
                return _hata("bu IP başka bir yazıcıda kayıtlı", 409)
            alanlar["ip"] = ip
        if "port" in v:
            alanlar["port"] = int(v["port"])
        if "etkin" in v:
            alanlar["etkin"] = 1 if v["etkin"] else 0
        kayit = await filo.yazici_guncelle(yid, **alanlar)
        if kayit is None:
            return _hata("yazıcı bulunamadı", 404)
        return _json({"yazici": kayit})

    async def yazici_sil(istek):
        yid = int(istek.match_info["id"])
        if not await filo.yazici_sil(yid):
            return _hata("yazıcı bulunamadı", 404)
        return _json({"silindi": yid})

    async def komut(istek):
        yid = int(istek.match_info["id"])
        v = await _govde(istek)
        ad = str(v.get("komut", ""))
        if yid not in filo.kayitlar:
            return _hata("yazıcı bulunamadı", 404)
        try:
            sonuc = await filo.komut(yid, ad, v.get("deger"))
        except ValueError as e:
            return _hata(str(e))
        return _json({"gonderildi": sonuc})

    async def aglar(_):
        return _json({"aglar": filo.aglar()})

    async def tarama_baslat(istek):
        v = await _govde(istek)
        cidr = str(v.get("cidr", "")).strip()
        if not cidr:
            return _hata("cidr gerekli")
        try:
            ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            return _hata("geçersiz CIDR")
        try:
            t = filo.tarama_baslat(cidr, int(v.get("port") or P.WS_PORT))
        except RuntimeError as e:
            return _hata(str(e), 409)
        return _json({"tarama": filo.tarama_gorunum(), "id": t.id}, 202)

    async def tarama_durum(_):
        t = filo.tarama_gorunum()
        if t is None:
            return _hata("tarama yok", 404)
        return _json({"tarama": t})

    async def tarama_iptal(_):
        if filo.tarama is None:
            return _hata("tarama yok", 404)
        filo.tarama.iptal()
        return _json({"iptal": True})

    async def olaylar(istek):
        limit = min(int(istek.query.get("limit", "100")), 1000)
        return _json({"olaylar": filo.vt.olaylar(limit)})

    async def ws_ucu(istek):
        ws = web.WebSocketResponse(heartbeat=25)
        await ws.prepare(istek)
        app[WS_ISTEMCILER].add(ws)
        try:
            await ws.send_str(json.dumps({
                "tur": "anlik", "yazicilar": filo.yazicilar_gorunum(),
                "sayilar": filo.ozet_sayilar(), "olaylar": filo.vt.olaylar(50),
                "tarama": filo.tarama_gorunum()}, ensure_ascii=False))
            async for msg in ws:
                if msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                    break
        finally:
            app[WS_ISTEMCILER].discard(ws)
        return ws

    app.router.add_get("/", ana_sayfa)
    app.router.add_get("/api/surum", surum)
    app.router.add_get("/api/yazicilar", yazicilar)
    app.router.add_post("/api/yazicilar", yazici_ekle)
    app.router.add_post("/api/yazicilar/toplu", toplu_ekle)
    app.router.add_get(r"/api/yazicilar/{id:\d+}", yazici)
    app.router.add_put(r"/api/yazicilar/{id:\d+}", yazici_guncelle)
    app.router.add_delete(r"/api/yazicilar/{id:\d+}", yazici_sil)
    app.router.add_post(r"/api/yazicilar/{id:\d+}/komut", komut)
    app.router.add_get("/api/aglar", aglar)
    app.router.add_post("/api/tarama", tarama_baslat)
    app.router.add_get("/api/tarama", tarama_durum)
    app.router.add_post("/api/tarama/iptal", tarama_iptal)
    app.router.add_get("/api/olaylar", olaylar)
    app.router.add_get("/ws", ws_ucu)
    app.router.add_static("/static/", WEB_DIZIN, show_index=False)

    async def kapanis(_):
        for ws in list(app[WS_ISTEMCILER]):
            await ws.close()
        await filo.durdur()

    app.on_shutdown.append(kapanis)
    return app
