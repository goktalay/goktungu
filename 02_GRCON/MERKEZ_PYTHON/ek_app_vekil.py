#!/usr/bin/env python3
"""mk_sunucu.py'ye /app/ HTTP vekilini ekler.

NEDEN VEKIL: GOKTUNGU programi merkezde AYRI bir surec olarak calisir
(127.0.0.1:18000 HTTP, 18765 WS). Tarayici ise TLS altindaki
https://goktungu.com/app/ adresine gelir. Merkez sunucu bu iki
katmani birlestirir: /app/ altindaki her istegi GCS surecine tasir ve
yaniti oldugu gibi geri yazar. Boylece GCS kod tabani degistirilmeden
merkezde sunulur ve TLS tek noktada sonlandirilmis kalir.
"""
import io
import re
import sys

P = "mk_sunucu.py"
m = io.open(P, encoding="utf-8").read()
ilk = len(m)

# --------------------------------------------------------------------------
# 1) urllib.request ice aktarimi (vekil istegi icin)
# --------------------------------------------------------------------------
if "import urllib.request" not in m:
    hedef = "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer"
    if hedef not in m:
        print("HATA: ice aktarim capasi bulunamadi")
        sys.exit(1)
    m = m.replace(
        hedef,
        "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer\n"
        "import urllib.request\n"
        "import urllib.error",
        1)
    print("+ urllib.request / urllib.error ice aktarildi")

# --------------------------------------------------------------------------
# 2) APP_HEDEF sabiti — GCS surecinin yerel adresi
# --------------------------------------------------------------------------
if "APP_HEDEF" not in m:
    capa = '    DIZIN_YOLLARI = ("/admin", "/app", "/company")'
    if capa not in m:
        print("HATA: DIZIN_YOLLARI capasi bulunamadi")
        sys.exit(1)
    yeni = '''    DIZIN_YOLLARI = ("/admin", "/company")

    # GOKTUNGU programinin merkezde calistigi yerel adres. /app/ altindaki
    # istekler bu surece tasinir; boylece GCS kod tabani degistirilmeden
    # TLS altinda sunulur. Port, ortam degiskeni ile degistirilebilir.
    APP_HEDEF = os.environ.get("GOKTUNGU_APP_HEDEF", "http://127.0.0.1:18000")

    # Vekilde tasinmayan basliklar: baglanti/aktarim duzeyine aittir ve
    # oldugu gibi kopyalanirsa istemci yanlis govde uzunlugu okur.
    ATLANAN_BASLIK = {
        "connection", "keep-alive", "proxy-authenticate",
        "proxy-authorization", "te", "trailers", "transfer-encoding",
        "upgrade", "host", "content-length",
    }'''
    m = m.replace(capa, yeni, 1)
    print("+ APP_HEDEF ve ATLANAN_BASLIK eklendi (/app DIZIN_YOLLARI'ndan cikarildi)")

# --------------------------------------------------------------------------
# 3) _app_vekil() yontemi — HTTP istegini GCS surecine tasir
# --------------------------------------------------------------------------
if "_app_vekil" not in m:
    capa = "    def _dosya_sun(self, istek: Istek) -> None:"
    if capa not in m:
        print("HATA: _dosya_sun capasi bulunamadi")
        sys.exit(1)
    vekil = '''    # -- /app/ vekili ---------------------------------------------------
    def _app_vekil(self, istek: Istek) -> None:
        """`/app/...` istegini merkezde calisan GOKTUNGU surecine tasir.

        Yol donusumu: `/app/js/ws.js` -> `/js/ws.js`. GCS kendi kokunde
        `/` bekler; onek korunursa tum varliklar 404 doner.
        """
        # Sorgu dizesi ham `self.path` uzerinden alinir: Istek sinifi
        # yalnizca ayristirilmis sozlugu tutar, yeniden kodlamak
        # sirayi/yinelenen anahtarlari bozar.
        ham_yol = self.path
        ic_yol = ham_yol[len("/app"):] or "/"
        if not ic_yol.startswith("/"):
            ic_yol = "/" + ic_yol
        hedef = self.APP_HEDEF + ic_yol
        # Govde: POST/PUT icin okunan ham govde yeniden kullanilir
        govde = istek.ham or None
        istek_nesnesi = urllib.request.Request(
            hedef, data=govde, method=self.command)
        for ad, deger in self.headers.items():
            if ad.lower() in self.ATLANAN_BASLIK:
                continue
            istek_nesnesi.add_header(ad, deger)
        # Gercek istemci adresi GCS'ye bildirilir (gunluk/denetim icin)
        istek_nesnesi.add_header("X-Forwarded-For", self.client_address[0])
        istek_nesnesi.add_header("X-Forwarded-Proto", "https")
        try:
            with urllib.request.urlopen(istek_nesnesi, timeout=120) as y:
                icerik = y.read()
                kod = y.status
                basliklar = list(y.headers.items())
        except urllib.error.HTTPError as e:
            icerik = e.read()
            kod = e.code
            basliklar = list(e.headers.items())
        except Exception as e:
            # GCS surecinin kapali olmasi 502 ile bildirilir; sessiz 500
            # yerine acik hata operatorun sorunu hemen gormesini saglar.
            self.hata_yaz(502, f"Uygulama sunucusuna ulasilamadi: {e}")
            return
        self.send_response(kod)
        for ad, deger in basliklar:
            if ad.lower() in self.ATLANAN_BASLIK:
                continue
            self.send_header(ad, deger)
        self.send_header("Content-Length", str(len(icerik)))
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(icerik)
            except BrokenPipeError:
                pass

'''
    m = m.replace(capa, vekil + capa, 1)
    print("+ _app_vekil() yontemi eklendi")

# --------------------------------------------------------------------------
# 4) _isle() icinde /app/ dallanmasi — YOL_TABLOSU'ndan ONCE
# --------------------------------------------------------------------------
if "self._app_vekil(istek)" not in m:
    capa = """        try:
            for y, desen, islev, yetki in YOL_TABLOSU:"""
    if capa not in m:
        print("HATA: _isle dongu capasi bulunamadi")
        sys.exit(1)
    yeni = """        # /app/ altindaki her sey GOKTUNGU surecine tasinir. Bu dal
        # YOL_TABLOSU'ndan ONCE gelir: GCS'nin kendi /api/... yollari
        # merkezin API tablosuyla cakismaz.
        if istek.yol == "/app":
            self.send_response(301)
            self.send_header("Location", "/app/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if istek.yol.startswith("/app/"):
            self._app_vekil(istek)
            return
        try:
            for y, desen, islev, yetki in YOL_TABLOSU:"""
    m = m.replace(capa, yeni, 1)
    print("+ _isle() icine /app/ dallanmasi eklendi")

# --------------------------------------------------------------------------
# 5) /app/ statik esleme satirini kaldir (artik vekil kullaniliyor)
# --------------------------------------------------------------------------
eski_esleme = """        elif yol_ == "/app/":
            kok, goreli = WEB_KOKU, "app/index.html"
"""
if eski_esleme in m:
    m = m.replace(eski_esleme, "", 1)
    print("+ eski /app/ statik eslemesi kaldirildi")

io.open(P, "w", encoding="utf-8").write(m)
print(f"\nTAMAM: {ilk} -> {len(m)} bayt")
