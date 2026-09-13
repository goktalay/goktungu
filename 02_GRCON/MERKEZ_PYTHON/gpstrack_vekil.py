"""GÖKTUNGU Merkez HTTPS kapısı için /gpstrack/ ters vekili.

Bu modül yalnızca 127.0.0.1:18088 üzerinde çalışan GPS gateway'e iletir.
Ana GÖKTUNGU uygulama vekilinden bağımsızdır ve erişim kapsamı /gpstrack/
önekinden dışarı taşamaz.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request

HEDEF = "http://127.0.0.1:18088"
ATLANAN_BASLIKLAR = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
}


def isle(handler, istek) -> None:
    """`/gpstrack/...` isteğini başlık ve gövde boyutları güvenli biçimde iletir."""
    ham = handler.path or "/"
    ayrik = urllib.parse.urlsplit(ham)
    yol = ayrik.path
    if not yol.startswith("/gpstrack/"):
        handler.hata_yaz(404, "Bulunamadı")
        return

    ic_yol = yol[len("/gpstrack"):] or "/"
    hedef = HEDEF + ic_yol
    if ayrik.query:
        hedef += "?" + ayrik.query

    govde = istek.ham if handler.command in ("POST", "PUT", "PATCH") else None
    istek_nesnesi = urllib.request.Request(hedef, data=govde, method=handler.command)
    for ad, deger in handler.headers.items():
        if ad.lower() not in ATLANAN_BASLIKLAR:
            istek_nesnesi.add_header(ad, deger)
    istek_nesnesi.add_header("X-Forwarded-For", handler.client_address[0])
    istek_nesnesi.add_header("X-Forwarded-Proto", "https")

    try:
        yanit = urllib.request.urlopen(istek_nesnesi, timeout=75)
    except urllib.error.HTTPError as hata:
        yanit = hata
    except Exception:
        handler.hata_yaz(502, "GPS alım hizmetine ulaşılamadı")
        return

    try:
        with yanit:
            icerik = yanit.read(4096)
            if len(icerik) == 4096:
                handler.hata_yaz(502, "GPS alım hizmeti beklenmeyen büyüklükte yanıt verdi")
                return
            kod = getattr(yanit, "status", None) or yanit.code
            basliklar = list(yanit.headers.items())
    except Exception:
        handler.hata_yaz(502, "GPS alım hizmeti yanıtı okunamadı")
        return

    handler.send_response(kod)
    for ad, deger in basliklar:
        if ad.lower() not in ATLANAN_BASLIKLAR and ad.lower() not in {"content-length", "server", "date"}:
            handler.send_header(ad, deger)
    handler.send_header("Content-Length", str(len(icerik)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    if handler.command != "HEAD":
        try:
            handler.wfile.write(icerik)
        except (BrokenPipeError, ConnectionResetError):
            pass
