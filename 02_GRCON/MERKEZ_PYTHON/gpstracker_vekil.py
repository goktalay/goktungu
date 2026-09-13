"""GÖKTUNGU Merkez HTTPS kapısı için gpstracker açık iz API vekili.

Alt alanın statik dosyaları merkez web kökünden sunulur. Bu modül yalnız
`/gpstracker/api/v1/public/tracks` isteğini loopback GPS gateway'e taşır.
Kimlik, cihaz sırrı, ham paket ve kaynak IP bilgisi dışarı verilmez.
"""

from __future__ import annotations

import urllib.error
import urllib.request

HEDEF = "http://127.0.0.1:18088"
ATLANAN_BASLIKLAR = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
}
ACIK_YOLLAR = {"/gpstracker/api/v1/public/tracks"}


def isle(handler, istek) -> None:
    """Yalnız okunabilir kamuya açık iz anlık görüntüsünü loopbackten iletir."""
    if handler.command != "GET" or istek.yol not in ACIK_YOLLAR:
        handler.hata_yaz(404, "Bulunamadı")
        return

    hedef = HEDEF + "/api/v1/public/tracks"
    istek_nesnesi = urllib.request.Request(hedef, method="GET")
    istek_nesnesi.add_header("Accept", "application/json")
    try:
        yanit = urllib.request.urlopen(istek_nesnesi, timeout=10)
    except urllib.error.HTTPError as hata:
        yanit = hata
    except Exception:
        handler.hata_yaz(502, "GPS takip hizmetine ulaşılamadı")
        return

    try:
        with yanit:
            icerik = yanit.read(4 * 1024 * 1024)
            if len(icerik) == 4 * 1024 * 1024:
                handler.hata_yaz(502, "GPS takip yanıtı beklenmeyen büyüklükte")
                return
            kod = getattr(yanit, "status", None) or yanit.code
            basliklar = list(yanit.headers.items())
    except Exception:
        handler.hata_yaz(502, "GPS takip yanıtı okunamadı")
        return

    handler.send_response(kod)
    for ad, deger in basliklar:
        if ad.lower() not in ATLANAN_BASLIKLAR and ad.lower() not in {"content-length", "server", "date"}:
            handler.send_header(ad, deger)
    handler.send_header("Content-Length", str(len(icerik)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.end_headers()
    try:
        handler.wfile.write(icerik)
    except (BrokenPipeError, ConnectionResetError):
        pass
