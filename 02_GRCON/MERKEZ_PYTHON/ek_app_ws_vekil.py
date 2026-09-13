#!/usr/bin/env python3
"""mk_sunucu.py'ye /app/ws WebSocket vekilini ekler.

websockets 17.0.1 (asyncio.server) API'si kullanılır:
  yol = soket.request.path
"""
import io
import sys

P = "mk_sunucu.py"
s = io.open(P, encoding="utf-8").read()

if "_app_ws_vekil" in s:
    print("ATLANDI: vekil zaten var")
    sys.exit(0)

# ---------------------------------------------------------------- 1) vekil işlevi
ESKI_BAS = '''# ==========================================================================
# WEBSOCKET — köprü ters bağlantıları
# ==========================================================================
async def _ws_isle(soket) -> None:
    import websockets

    ip = None'''

YENI_BAS = '''# ==========================================================================
# WEBSOCKET — /app/ arayüz vekili
# ==========================================================================
def _ws_gorev_sonuc_tuket(tamamlanan, nere=""):
    """asyncio.wait TAMAMLANAN kumesinin istisnalarini TUKETIR.

    FAZ18-IS13B-TAMAMLANAN-TUKET

    NEDEN: `asyncio.wait(FIRST_COMPLETED)` iki kume dondurur.
    Tamamlanan kume genellikle `_` ile atilir; ama FIRST_COMPLETED
    ile ilk biten gorev cogu zaman HATA nedeniyle biter. Sonucu
    kimse okumadigi icin asyncio "Task exception was never
    retrieved" yigin izi basar. `.exception()` cagrisi asyncio'ya
    "istisna alindi" der ve uyari uretilmez.

    SESSIZ YUTMA YAPILMAZ: beklenen kopus istisnalari bastirilir,
    beklenmeyenler gunluge yazilir.
    """
    for _g in (tamamlanan or ()):
        try:
            if _g.cancelled():
                continue
            _hata = _g.exception()          # <-- istisnayi TUKETIR
        except BaseException:
            continue
        if _hata is None:
            continue
        _adi = type(_hata).__name__
        # Kopus/iptal beklenen durumdur: ust `except` blogu isler.
        if "ConnectionClosed" in _adi or "CancelledError" in _adi:
            continue
        # Beklenmeyen istisna: SESSIZ KALMAZ.
        try:
            print("[APP-WS] Kopru gorevi beklenmeyen hata%s: %s: %s"
                  % ((" (" + nere + ")") if nere else "", _adi, _hata))
        except BaseException:
            pass


async def _app_ws_vekil(soket) -> None:
    """GÖKTUNGU arayüzünün WebSocket trafiğini yerel GCS sürecine taşır.

    Tarayıcı TLS ile 9443'e ``/app/ws`` yolundan bağlanır; bu işlev
    şifresiz olarak ``ws://127.0.0.1:<gcs_ws_port>`` adresine bağlanıp
    iki yönde çerçeveleri aktarır. Böylece GCS kodu değişmeden merkezde
    çalışabilir ve dışarıya yalnızca 443/9443 açık kalır.
    """
    import websockets

    a = ayar_oku()
    hedef_port = int(a.get("app_ws_port", 18765))
    hedef = f"ws://127.0.0.1:{hedef_port}"
    try:
        async with websockets.connect(
                hedef, max_size=32 * 1024 * 1024,
                ping_interval=20, ping_timeout=20,
                open_timeout=10) as ic:

            async def ileri() -> None:
                """Tarayıcı → GCS"""
                async for ham in soket:
                    await ic.send(ham)

            async def geri() -> None:
                """GCS → tarayıcı"""
                async for ham in ic:
                    await soket.send(ham)

            gorevler = [asyncio.create_task(ileri()),
                        asyncio.create_task(geri())]
            # FAZ18-IS13B-TAMAMLANAN-TUKET: tamamlanan kume ARTIK atilmiyor.
            # Canli olcum: istisnayi firlatan gorev BEKLEYEN
            # degil TAMAMLANAN gorevdi (`async for ham in soket`
            # icinde ConnectionClosedError). `_` ile atilan kume
            # istisnayi TASIYAN kumeydi.
            tamamlanan, bekleyen = await asyncio.wait(
                gorevler, return_when=asyncio.FIRST_COMPLETED)
            _ws_gorev_sonuc_tuket(tamamlanan, "ana")
            # FAZ18-IS13-GOREV-BEKLE (olu kod, ice alan yok): kusurlu
            # kalibin kopyalanmasini onlemek icin burada da
            # duzeltildi.
            for g in bekleyen:
                g.cancel()
            if bekleyen:
                await asyncio.gather(*bekleyen, return_exceptions=True)
    except Exception as e:
        adi = type(e).__name__
        if "ConnectionClosed" not in adi and "CancelledError" not in adi:
            print(f"[APP-WS] Vekil hatasi ({hedef}): {adi}: {e}")
        with __import__("contextlib").suppress(Exception):
            await soket.close(1011, "arayuz sunucusuna ulasilamadi")


def _ws_yolu(soket) -> str:
    """websockets 17 (asyncio.server) bağlantısından istek yolunu okur."""
    istek = getattr(soket, "request", None)
    if istek is not None:
        return str(getattr(istek, "path", "") or "")
    # legacy sürüm yedeği
    return str(getattr(soket, "path", "") or "")


# ==========================================================================
# WEBSOCKET — köprü ters bağlantıları
# ==========================================================================
async def _ws_isle(soket) -> None:
    import websockets

    # /app/ws → arayüz vekili (köprü protokolü DEĞİL)
    yol = _ws_yolu(soket)
    if yol.split("?")[0].rstrip("/") in ("/app/ws", "/app_ws"):
        await _app_ws_vekil(soket)
        return

    ip = None'''

if ESKI_BAS not in s:
    print("HATA: _ws_isle başlangıcı bulunamadı")
    sys.exit(1)
s = s.replace(ESKI_BAS, YENI_BAS, 1)

io.open(P, "w", encoding="utf-8").write(s)
print("TAMAM: /app/ws vekili eklendi")
