# -*- coding: utf-8 -*-
"""GÖKTUNGU MERKEZ — HTTP ve WebSocket sunucusu.

İki dinleyici vardır:

  1. HTTP/HTTPS — tanıtım sayfası, `/admin` paneli, `/api/*` uç
     noktaları, `/indir/*` güncelleme deposu.
  2. WebSocket (varsayılan 9443) — köprü sunucularının **ters**
     bağlantıları. Merkez hiçbir zaman köprüye bağlanmaz; köprü
     bağlanır, merkez o soket üzerinden istek gönderir.

HTTP tarafı `ThreadingHTTPServer` ile ayrı iş parçacıklarında,
WebSocket tarafı `asyncio` döngüsünde çalışır. İki dünya arasında
`asyncio.run_coroutine_threadsafe` ile köprü kurulur; HTTP isteği
canlı bir köprüden veri isteyebilir.
"""

from __future__ import annotations

import base64
import hashlib
import time
import asyncio
import cgi
import datetime as dt
import io
import json
import mimetypes
import hmac
import os
import re
import ssl
import threading
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import posixpath
import urllib.parse
import urllib.request
import urllib.error
from typing import Any, Callable

import mk_akis as akis
import gpstrack_vekil  # /gpstrack/ yalniz yerel GPS gateway vekili
import gpstracker_vekil  # gpstracker acik iz API vekili
import mk_video as video
import mk_api as api
import mk_db as db
import mk_depo as depo
# === FIYAT UCU BIRLESTIRILDI (mk_paket) ===
import mk_yetki as yetki
import mk_paket as paket


# ==========================================================================
# IS67 — GZIP SIKISTIRMA (isaret: IS67_GZIP_v1)
# ==========================================================================
# OLCUM: app arayuzu 111 kaynak / 10.48 MB ham; gzip-6 ile 2.82 MB
# (%73.1 kazanc). Sunucu daha once HIC sikistirmiyordu.
#
# CPU TUZAGI: Cesium.js'i her istekte sikistirmak 239 ms yakar. Bu
# yuzden sikisik govde bellekte onbelleklenir; anahtar ham govdenin
# (uzunluk, sha1) ikilisidir. Vekil yolunda dosya yolu/mtime YOKTUR,
# elimizde yalniz govde vardir — tek tutarli anahtar icerigin ozetidir.
import gzip as _gzip
import hashlib as _hashlib
import threading as _threading
from collections import OrderedDict as _OrderedDict

# Sikistirilacak icerik turleri. Zaten sikisik olanlar (jpeg/png/zip/
# mp4/woff2...) DISARIDA: yeniden sikistirmak dosyayi BUYUTUR.
_GZ_TURLER = (
    "text/", "application/javascript", "application/json",
    "application/xml", "application/xhtml+xml", "image/svg+xml",
    "application/manifest+json", "application/wasm",
)
# gzip basligi ~20 bayt; bunun altinda kazanc yok, CPU bosa gider.
_GZ_ALT_SINIR = 1024
# Seviye 6: olculdu, seviye 1'e gore Cesium'da 247 KB daha kazandiriyor.
# Onbellek sayesinde CPU maliyeti dosya basina BIR KEZ odenir.
_GZ_SEVIYE = 6
# Onbellek tavani: en buyuk 12 kaynak toplami ~9 MB; 64 MB rahat yeter.
_GZ_ONBELLEK_TAVAN = 64 * 1024 * 1024

_gz_onbellek: "_OrderedDict[tuple, bytes]" = _OrderedDict()
_gz_kilit = _threading.Lock()
_gz_boyut = 0


def _gz_uygun_mu(tur: str, govde: bytes, istek_basliklari) -> bool:
    """Bu yanit sikistirilmali mi? Tum kapilar burada."""
    if not govde or len(govde) < _GZ_ALT_SINIR:
        return False
    t = (tur or "").split(";")[0].strip().lower()
    if not any(t.startswith(x) or t == x for x in _GZ_TURLER):
        return False
    try:
        kabul = (istek_basliklari.get("Accept-Encoding") or "").lower()
    except Exception:
        return False
    return "gzip" in kabul


def _gz_sikistir(govde: bytes) -> bytes:
    """Sikisik govdeyi dondurur; ayni icerik icin bir kez hesaplanir."""
    global _gz_boyut
    anahtar = (len(govde), _hashlib.sha1(govde).digest())
    with _gz_kilit:
        v = _gz_onbellek.get(anahtar)
        if v is not None:
            _gz_onbellek.move_to_end(anahtar)
            return v
    # Sikistirma KILIT DISINDA yapilir: 239 ms'lik Cesium sikistirmasi
    # kilidi tutsaydi tum es zamanli istekler beklerdi.
    sikisik = _gzip.compress(govde, _GZ_SEVIYE)
    # Sikisik hali daha buyukse (rastgele/zaten sikisik veri) ham kalir.
    if len(sikisik) >= len(govde):
        return govde
    with _gz_kilit:
        if anahtar not in _gz_onbellek:
            _gz_onbellek[anahtar] = sikisik
            _gz_boyut += len(sikisik)
            while _gz_boyut > _GZ_ONBELLEK_TAVAN and _gz_onbellek:
                _, eski = _gz_onbellek.popitem(last=False)
                _gz_boyut -= len(eski)
    return sikisik

import mk_bakim as bakim
import mk_iyzico as iyzico

# Tahsilat kunyesi -- TEK KAYNAK.
# RESMI UNVAN, Turkce karakterler ZORUNLU: bu alan fatura kunyesinde ve
# odeme sayfasinda gorunur; ASCII'ye dusurulmus unvan ticari belge
# hatasidir. Iki ayri ucta kopyalanmaz -- biri eskir.
_TAHSILAT_KUNYE = {
    "unvan": "Türkbey Teknoloji Anonim Şirketi",
    "vkn": "6290873411",
    "vergi_dairesi": "Sincan",
    "ticaret_sicil": "418199",
    "adres": ("Ahi Evren OSB Mah. Büyük Selçuklu Cad. "
              "No:2/B Sincan/Ankara"),
}
import mk_odeme as odeme
import mk_kimlik as kimlik
import mk_kaba_kuvvet as kaba_kuvvet
import mk_bakim_kipi as bakim_kipi  # FAZ18-IS24-BAKIM-KIPI
import mk_guvenlik as guvenlik  # FAZ18-IS9-GUVENLIK-IZLEME
import mk_gunluk as gunluk  # FAZ18-IS10-GUNLUK
import mk_role as role
from mk_ayar import DEPO_KOKU, VERI_KOKU, WEB_KOKU, ayar_oku

# --------------------------------------------------------------------------
# asyncio döngüsü (WebSocket tarafı) — HTTP iş parçacıklarından erişilir
# --------------------------------------------------------------------------
_DONGU: asyncio.AbstractEventLoop | None = None


def dongu_ata(d: asyncio.AbstractEventLoop) -> None:
    global _DONGU
    _DONGU = d
    # Akis koprusu de ayni donguyu kullanir: UDP soketleri bu donguye
    # `add_reader` ile baglanir, kanal basina is parcacigi ACILMAZ.
    akis.AKIS.dongu_ata(d)


def kopruye_sor(ornek_id: int, eylem: str, veri: dict | None = None,
                zaman_asimi: float = 15.0) -> tuple[dict | None, str | None]:
    """HTTP iş parçacığından canlı köprüye eşzamanlı istek."""
    o = role.ROLE.ornek_ile(ornek_id)
    if o is None:
        return None, "Sunucu çevrimiçi değil"
    if _DONGU is None:
        return None, "Röle döngüsü hazır değil"
    gelecek = asyncio.run_coroutine_threadsafe(
        role.kopruden_iste(o, eylem, veri, zaman_asimi), _DONGU)
    try:
        return gelecek.result(timeout=zaman_asimi + 5), None
    except Exception as e:
        return None, str(e)


# --------------------------------------------------------------------------
# HTTP yardımcıları
# --------------------------------------------------------------------------
def _json_varsayilan(x: Any) -> Any:
    if isinstance(x, (dt.datetime, dt.date)):
        return x.isoformat()
    if isinstance(x, dt.timedelta):
        return x.total_seconds()
    if hasattr(x, "__str__"):
        return str(x)
    raise TypeError(type(x))


class Istek:
    """Bir HTTP isteğinin ayrıştırılmış hâli."""

    def __init__(self, isleyici: "MerkezIsleyici") -> None:
        self.h = isleyici
        parcalar = urllib.parse.urlsplit(isleyici.path)
        self.yol = urllib.parse.unquote(parcalar.path)
        self.sorgu = {
            a: d[0] for a, d in urllib.parse.parse_qs(parcalar.query).items()
        }
        self.govde: dict[str, Any] = {}
        self.ham: bytes = b""
        uzunluk = int(isleyici.headers.get("Content-Length") or 0)
        if 0 < uzunluk <= 64 * 1024 * 1024:
            self.ham = isleyici.rfile.read(uzunluk)
            tur = (isleyici.headers.get("Content-Type") or "").lower()
            if "application/json" in tur:
                try:
                    self.govde = json.loads(self.ham.decode("utf-8") or "{}")
                except Exception:
                    self.govde = {}
            elif "application/x-www-form-urlencoded" in tur:
                self.govde = {
                    a: d[0] for a, d in urllib.parse.parse_qs(
                        self.ham.decode("utf-8")).items()
                }

    @property
    def ip(self) -> str:
        ileri = self.h.headers.get("X-Forwarded-For")
        if ileri:
            return ileri.split(",")[0].strip()
        return self.h.client_address[0]

    def kurabiye(self, ad: str) -> str | None:
        ham = self.h.headers.get("Cookie") or ""
        for parca in ham.split(";"):
            if "=" in parca:
                a, d = parca.split("=", 1)
                if a.strip() == ad:
                    return urllib.parse.unquote(d.strip())
        return None

    def jeton(self) -> str | None:
        yetki = self.h.headers.get("Authorization") or ""
        if yetki.lower().startswith("bearer "):
            return yetki[7:].strip()
        return self.kurabiye("goktungu_admin")

    def firma_jetonu(self) -> str | None:
        """Firma kullanicisi oturum jetonu. AYRI kurabiye adi kullanilir;
        `Authorization` basligina BAKILMAZ, cunku ayni tarayicida hem
        yonetici hem firma oturumu acik olabilir ve tek baslik iki alani
        birbirine karistirirdi."""
        return self.kurabiye("goktungu_firma")


# Yönlendirme tablosu: (yöntem, derlenmiş desen, işlev, yetki)
YOL_TABLOSU: list[tuple[str, re.Pattern, Callable, str]] = []


# === YOL CAKISMA DENETIMI ===
# YOL_TABLOSU bir LISTEDIR ve ILK eslesen kazanir. Ayni (yontem, desen)
# ikilisi iki kez kaydedilirse ikinci uc SESSIZCE olu kalir.
#
# Bu 2026-08-18'de yasandi: `/api/genel/fiyatlar` iki kez kaydedildi,
# yeni paket motoruna bagli uc hic calismadi ve canli yanit eski
# bicimde dondu. Sessiz kalmasin diye kayit aninda uyari basilir.
_YOL_KAYITLI: set = set()


def yol(yontem: str, desen: str, yetki: str = "yonetici"):
    def sarmala(f: Callable) -> Callable:
        anahtar = (yontem, desen)
        if anahtar in _YOL_KAYITLI:
            print("[UYARI] YOL CAKISMASI: %s %s zaten kayitli; "
                  "'%s' fonksiyonu OLU kalacak (ilk eslesen kazanir)."
                  % (yontem, desen, getattr(f, "__name__", "?")))
        _YOL_KAYITLI.add(anahtar)
        YOL_TABLOSU.append((yontem, re.compile("^" + desen + "$"), f, yetki))
        return f
    return sarmala



# ----------------------------------------------------------------- #
# YEDEK / KAYNAK DOSYA DESEN ENGELI                                  #
#                                                                    #
# Bu sunucuda nginx YOKTUR; statik dosyalari bu surec sunuyor.       #
# nginx'in ontanimli "yedek uzantisini sunma" korumasi burada        #
# bulunmadigi icin engel elle kurulur.                               #
#                                                                    #
# 2026-08-17 denetiminde olculdu: gecis sirasinda birakilan 13       #
# `.adbak` dosyasi ve 2 panel yedek dizini HTTP 200 donuyordu.       #
# Sizan icerik: eski marka, eski alan adi, yururlukten kalkmis KVKK  #
# metni ve panel kaynak kodu.                                        #
#                                                                    #
# 404 doner (403 DEGIL): 403 dosyanin varligini dogrular ve          #
# saldirgana harita cizer.                                           #
# ----------------------------------------------------------------- #
_ENGELLI_UZANTI = (
    ".adbak", ".bak", ".orij", ".orig", ".eski", ".old",
    ".save", ".swp", ".swo", ".tmp", ".rej", ".patch", ".diff",
)
_ENGELLI_DESEN = re.compile(
    r"(^|/)\."              # nokta ile baslayan (gizli) dosya ya da dizin
    r"|~$"                  # editor yedegi: dosya.html~
    r"|_yedek(_|/|$)"       # company_yedek_2105/
    r"|yedek_arsiv"         # arsiv dizini
    r"|(^|/)__pycache__(/|$)",
    re.IGNORECASE,
)


def _yedek_yolu_mu(yol: str) -> bool:
    """Yol bir yedek/kaynak/gizli dosyaya mi isaret ediyor."""
    d = (yol or "").lower()
    if d.endswith(_ENGELLI_UZANTI):
        return True
    return bool(_ENGELLI_DESEN.search(d))


# ----------------------------------------------------------------- #
# /app/ VEKILI ICIN SIZINTI ENGELI (BULGU_04)                       #
#                                                                   #
# `_dosya_sun` icindeki `_yedek_yolu_mu` engeli /app/ dalini KAPSAMAZ:#
# vekil dali YOL_TABLOSU'ndan once donuyor (satir ~492). Olculen     #
# sizinti: /app/veri/pg.json veritabani parolasini donduruyordu.     #
#                                                                   #
# Bu, app tarafindaki engelin IKINCI katmanidir. Iki katman ayni     #
# oruntuleri bagimsiz olarak sorgular; biri kaldirilirsa digeri      #
# sizintiyi durdurur.                                               #
# ----------------------------------------------------------------- #
_APP_ENGEL_UZANTI = (
    ".py", ".pyc", ".pyo", ".pyd", ".sh", ".bat", ".ps1",
    ".json", ".ini", ".cfg", ".conf", ".yaml", ".yml", ".toml",
    ".log", ".db", ".sqlite", ".sqlite3", ".sql", ".jsonl",
    ".env", ".pem", ".key", ".crt", ".csr", ".p12", ".pfx", ".jks",
)

# PWA islevi icin zorunlu; engellenirse uygulama kurulamaz.
# Yol `/app/` onegi SOYULDUKTAN sonra karsilastirilir.
_APP_IZIN_TAM = frozenset((
    "/manifest.json",
    "/sw.js",
    "/js/surum.js",
))
# FAZ18-IS29: ISLEVSEL ONEK IZNI (vekil katmani).
#
# OLCULEN KUSUR: `.json` kara listesi Cesium'un ISLEVSEL varliklarini
# da vuruyordu ve harita SAHNESI hic kurulmuyordu:
#   /lib/Cesium/Assets/approximateTerrainHeights.json  (arazi yuksekligi)
#   /lib/Cesium/Assets/IAU2006_XYS/IAU2006_XYS_*.json  (gok referansi)
# Ikisi de reddedilince Cesium `promise` reddiyle coker; dron ikonu,
# lokasyon ikonu, cetvel ve rota isaretcileri BIRLIKTE gorunmez olur
# (dort belirti, tek kok neden).
#
# BU KATMAN NICIN AYRI YAMALANIR: yukaridaki yorumda anlatildigi gibi
# app ve vekil kara listeleri BILINCLI olarak birbirinden bagimsizdir.
# Bagimsizlik sizinti karsisinda degerlidir, ancak ISLEVSEL izin de
# iki katmanda AYNI olmak zorundadir; yoksa App 200 dondururken vekil
# 404 doner (olculdu).
#
# NEDEN ONEK, TEK TEK DOSYA DEGIL: Cesium 30 .json varligi tasir ve
# surum yukseltmesinde liste degisir; tek tek saymak yeni surumde
# SESSIZ 404 uretir.
#
# GUVENLIK OLCUMU: /lib/ altinda riskli uzanti 0 dosya, sir izi
# (password/secret/token) tasiyan .json 0 dosya.
#
# YOL GECISI: denetim normpath ve unquote SONRASINDA yapilir, bu yuzden
# `/lib/../veri/pg.json` ve `%2e%2e` kodlamalari `/veri/pg.json` olarak
# normalize edilir ve `_APP_ENGEL_ONEK` tarafindan engellenmeye DEVAM
# eder.
_APP_IZIN_ONEK = (
    "/lib/",
)

# /app/ dalina OZEL desenler. Genel `_ENGELLI_DESEN` degistirilmez:
# o desen /company/ ve /admin/ dallarinda da kullanilir ve orada
# `requirements.txt` mesru bir kurulum belgesi olabilir.
_APP_ENGEL_DESEN = re.compile(
    r"(^|/)requirements\.txt$"
    r"|(^|/)calisma\.json$"
    r"|(^|/)__pycache__(/|$)"
    r"|\.txt$",
    re.IGNORECASE,
)

_APP_ENGEL_ONEK = (
    "/veri/",
    "/sertifika/",
    "/goktungu/",
    "/ai_modeller/",
    "/araclar/",
    "/python/",
    "/assets/python/",
)


def _app_engelli_mi(ic_yol: str) -> bool:
    """`/app/` onegi soyulmus yol hassas bir kaynaga mi isaret ediyor.

    Yol NORMALLESTIRILIR: `/js/../veri/pg.json` onek denetimini
    atlatmasin. Yuzde kodlamasi da cozulur (`%2e%2e`).
    """
    d = (ic_yol or "").split("?", 1)[0].split("#", 1)[0]
    try:
        d = urllib.parse.unquote(d)
    except Exception:
        pass
    d = d.replace("\\", "/")
    dizin_istegi = d.endswith("/")
    d = posixpath.normpath(d)
    if not d.startswith("/"):
        d = "/" + d
    if dizin_istegi and not d.endswith("/"):
        d += "/"
    alt = d.lower()
    if alt in _APP_IZIN_TAM:
        return False
    # FAZ18-IS29: islevsel onek izni. Engel ONEK ve DESEN denetimleri
    # bu izinden BAGIMSIZ uygulanmaya devam eder; boylece /lib/
    # altindaki .json varliklari servis edilirken /veri/, /goktungu/,
    # __pycache__ ve yedek engelleri bozulmaz.
    if alt.startswith(_APP_IZIN_ONEK):
        if not alt.startswith(_APP_ENGEL_ONEK):
            if not _APP_ENGEL_DESEN.search(alt):
                if not _ENGELLI_DESEN.search(alt):
                    return False
    if alt.endswith(_APP_ENGEL_UZANTI):
        return True
    if alt.startswith(_APP_ENGEL_ONEK):
        return True
    if _APP_ENGEL_DESEN.search(alt):
        return True
    return bool(_ENGELLI_DESEN.search(alt))


class MerkezIsleyici(BaseHTTPRequestHandler):
    server_version = "GoktunguMerkez/1.1"
    protocol_version = "HTTP/1.1"

    # -- altyapı --------------------------------------------------------
    def log_message(self, bicim: str, *arg: Any) -> None:  # sessiz
        pass

    def setup(self) -> None:
        """TLS el sıkışmasını istek iş parçacığında tamamla.

        `ThreadingHTTPServer` iş parçacığını `get_request()` döndükten
        sonra açar. Dinleme soketi doğrudan `ssl.wrap_socket` ile
        sarmalanırsa el sıkışma `accept()` içinde, yani kabul iş
        parçacığında yapılır ve bağlantılar sıraya girer: uzak
        istemcilerde gecikme her yeni bağlantıda ~2×RTT birikir
        (ölçüldü: 8 eşzamanlı istekte 0,43 s → 2,38 s merdiveni).
        Bu yüzden soket düz kabul edilir ve TLS burada kurulur.
        """
        ctx = getattr(self.server, "tls_baglam", None)
        # DIKKAT: `self.connection` ancak `super().setup()` icinde olusur;
        # bu asamada yalniz `self.request` (ham soket) vardir.
        if ctx is not None and not isinstance(self.request, ssl.SSLSocket):
            try:
                self.request = ctx.wrap_socket(
                    self.request, server_side=True)
                self.connection = self.request
            except (ssl.SSLError, OSError):
                # TLS kurulamadı (düz HTTP isteği, tarama, kopan bağlantı)
                try:
                    self.request.close()
                except OSError:
                    pass
                self.connection = self.request
                self.close_connection = True
                self.rfile = io.BytesIO(b"")
                self.wfile = io.BytesIO()
                return
        super().setup()

    # ----------------------------------------------------------------- #
    # KABA KUVVET KORUMASI (KK_GONDERIM_v1)                                    #
    #                                                                    #
    # OLCULEN ACIK: `/api/firma/giris` ucuna 15 ardisik hatali parola    #
    # gonderildi; on besi de ayni hizda 401 dondu. Hiz siniri, artan     #
    # gecikme ve hesap kilidi YOKTU. Ayni durum `/api/admin/giris`       #
    # (sistem yoneticisi) ve `/api/dogrulama/onayla` (dogrulama kodu)    #
    # uclarinda da gecerliydi.                                          #
    #                                                                    #
    # Bu sunucuda nginx YOKTUR; `limit_req` gibi hazir bir katman        #
    # bulunmadigi icin koruma kodda kurulur.                            #
    # ----------------------------------------------------------------- #
    def _kk_es(self) -> str:
        """Hiz siniri anahtari: GERCEK TCP esi.

        `istek.ip` KULLANILMAZ. O ozellik `X-Forwarded-For` basligini
        onceler ve baslik istemci tarafindan UYDURULABILIR; onunla
        anahtarlanan bir sinir, her istekte farkli baslik gonderilerek
        TAMAMEN atlanir. Ayni sozlesme `_ic_uc_dogrula` icinde de
        uygulanir.
        """
        try:
            return self.client_address[0]
        except Exception:
            return ""

    def _bakim_denetle(self, istek) -> bool:
        """Bakim kipi kapisi. FAZ18-IS24-BAKIM-KIPI

        Donus: `True` ise istek REDDEDILDI (yanit yazildi),
        cagirici hemen donmeli. Kaba kuvvet katmaniyla ayni
        sozlesme.

        MUAFIYET: sistem yoneticisi oturumu varsa kayit uclari
        calismaya devam eder. Gerekce: bakim sirasinda yapilan
        duzeltmelerin kayit akisi uzerinde dogrulanabilmesi
        gerekir; aksi halde bakim biter, kusur canliya cikar ve
        ilk gercek kullanici kusuru bulur.
        """
        uc = getattr(istek, "yol", "") or ""
        try:
            if not bakim_kipi.uc_kapali_mi(uc):
                return False
        except BaseException:
            # Bakim modulu kendi kusuruyla kayit akisini
            # kapatmasin.
            return False
        # Sistem yoneticisi muafiyeti.
        try:
            if kimlik.yonetici_oturum(istek.jeton()):
                return False
        except BaseException:
            pass
        try:
            self.json_yaz(bakim_kipi.yanit_govdesi(), 503,
                          {"Retry-After": "3600"})
        except BaseException:
            pass
        return True

    def _kk_denetle(self, istek) -> bool:
        """Istek isleme alinmadan once cagrilir.

        Donus: `True` ise istek REDDEDILDI (yanit yazildi), cagirici
        hemen donmeli.
        """
        uc = getattr(istek, "yol", "") or ""
        if uc not in kaba_kuvvet.KORUNAN_UCLAR:
            return False
        es = self._kk_es()
        hesap = kaba_kuvvet.hesap_coz(getattr(istek, "govde", None))
        # Baglam: `_yaz` sonucu bu sozlukten okuyacak.
        self._kk_baglam = {"uc": uc, "es": es, "hesap": hesap}
        engel = kaba_kuvvet.denetle(es, uc, hesap)
        if engel:
            kalan, sebep = engel
            self._kk_islendi = True
            if sebep == "hesap":
                mesaj = ("Bu hesap icin cok fazla basarisiz deneme yapildi. "
                         "Lutfen %d saniye sonra yeniden deneyin."
                         % int(kalan))
            else:
                mesaj = ("Cok fazla deneme yapildi. Lutfen %d saniye sonra "
                         "yeniden deneyin." % int(kalan))
            try:
                self.json_yaz({"hata": mesaj, "kalan": int(kalan),
                               "sebep": sebep}, 429,
                              {"Retry-After": str(int(kalan))})
            except Exception:
                pass
            return True
        # ARTAN GECIKME: otomatik araclarin hizini dusurur. Mesru
        # kullanici 2-3 denemede gecer ve gecikmeyi hissetmez.
        bekle = kaba_kuvvet.gecikme(es, uc)
        if bekle > 0:
            try:
                time.sleep(bekle)
            except Exception:
                pass
        return False

    def _kk_sonuc(self, kod: int) -> None:
        """Yanit kodundan sonucu cikarip sayaca isler."""
        baglam = getattr(self, "_kk_baglam", None)
        if not baglam or getattr(self, "_kk_islendi", False):
            return
        self._kk_islendi = True
        try:
            if kod in (401, 403):
                kaba_kuvvet.basarisiz(baglam["es"], baglam["uc"],
                                      baglam["hesap"])
            elif 200 <= kod < 300:
                kaba_kuvvet.basarili(baglam["es"], baglam["uc"],
                                     baglam["hesap"])
        except BaseException:
            # Koruma katmani ISTEGI ASLA KIRMAZ: sayac hatasi yuzunden
            # mesru bir giris basarisiz olmamali.
            pass

    def _yaz(self, kod: int, govde: bytes, tur: str = "application/json",
             ek: dict[str, str] | None = None) -> None:
        self._kk_sonuc(kod)
        # IS67_GZIP_v1: govde, basliklar yazilmadan ONCE
        # sikistirilir; `Content-Length` sikisik boyutu
        # gostermek ZORUNDADIR, aksi halde tarayici govdeyi
        # eksik okur ve sayfa yarim kalir.
        _gz_ek = None
        try:
            if (kod == 200 and self.command != "HEAD"
                    and not (ek or {}).get("Content-Encoding")
                    and _gz_uygun_mu(tur, govde, self.headers)):
                _s = _gz_sikistir(govde)
                if len(_s) < len(govde):
                    govde = _s
                    _gz_ek = "gzip"
        except BaseException:
            # Sikistirma HICBIR kosulda yaniti dusuremez;
            # hata halinde ham govde gonderilir.
            _gz_ek = None
        self.send_response(kod)
        self.send_header("Content-Type", tur)
        if _gz_ek:
            self.send_header("Content-Encoding", _gz_ek)
        # `Vary` HER metin yanitta gonderilir (sikistirilmasa
        # bile): ara onbellekler sikisik ve ham surumu ayri
        # saklamazsa gzip anlamayan istemciye sikisik govde
        # servis edilir.
        self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(govde)))
        self.send_header("X-Content-Type-Options", "nosniff")
        # BULGU_10b GUVENLIK (2026-08-17): tarayici tarafli
        # savunma basliklari. `nosniff` zaten vardi.
        #
        # CSP: `unsafe-inline` ve `unsafe-eval` DAHIL edildi.
        # Gerekce olculdu: (1) arayuz genelinde satir ici
        # `onclick`/`style` kullanimi var, (2) Cesium harita
        # motoru modul yuklemek icin `new Function` cagiriyor
        # (8 yerde olculdu). Bunlar olmadan arayuz KIRILIR.
        # Bu haliyle CSP XSS'i tumuyle engellemez ama veri
        # sizdirmayi (dis adrese istek) ve cerceve icine
        # almayi engeller — kismi ama gercek kazanc.
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob: https:; "
            "connect-src 'self' ws: wss: https:; "
            "worker-src 'self' blob:; "
            "font-src 'self' data:; "
            "object-src 'none'; "
            "frame-ancestors 'self'; "
            "base-uri 'self'")
        # HSTS: tarayiciyi 1 yil boyunca HTTPS'e kilitler.
        # `includeSubDomains` guvenli: joker sertifika
        # (*.goktungu.com) tum alt alanlari kapsiyor.
        # `preload` EKLENMEDI — geri alinmasi cok zor ve
        # tarayici listesine girmek kalici baglayicilik
        # yaratir; once uretimde bir sure izlenmeli.
        self.send_header(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains")
        # Tiklama hirsizligi (clickjacking) korumasi.
        # CSP `frame-ancestors` modern tarayicilarda yeterli
        # ama eski surumler yalniz bu basligi taniyor.
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        # Dis adrese gidilirken tam adres (jeton icerebilir)
        # gonderilmesin.
        self.send_header(
            "Referrer-Policy", "strict-origin-when-cross-origin")
        for a, d in (ek or {}).items():
            self.send_header(a, d)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(govde)

    def json_yaz(self, veri: Any, kod: int = 200,
                 ek: dict[str, str] | None = None) -> None:
        govde = json.dumps(veri, ensure_ascii=False,
                           default=_json_varsayilan).encode("utf-8")
        self._yaz(kod, govde, "application/json; charset=utf-8", ek)

    def hata_yaz(self, kod: int, mesaj: str) -> None:
        self.json_yaz({"hata": mesaj}, kod)

    def dosya_akit(self, hedef: str, indirme_ad: str) -> None:
        """Diskteki bir dosyayi indirme olarak akitir.

        v2.4.65 — lisans denetimli Merkez Uygulama indirmesi icin
        eklendi. `_dosya_sun()` kullanilamaz: o islev istegin YOLUNDAN
        dosya cozer ve kimlik denetimi yapmaz; burada dosya zaten
        yetkilendirilmis olarak verilir.
        """
        try:
            boyut = os.path.getsize(hedef)
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(boyut))
            self.send_header("Content-Disposition",
                             'attachment; filename="%s"' % indirme_ad)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if self.command == "HEAD":
                return
            with open(hedef, "rb") as f:
                while True:
                    parca = f.read(256 * 1024)
                    if not parca:
                        break
                    self.wfile.write(parca)
        except BrokenPipeError:
            pass

    # -- yöntemler ------------------------------------------------------
    def do_GET(self) -> None:
        self._isle("GET")

    def do_HEAD(self) -> None:
        self._isle("GET")

    def do_POST(self) -> None:
        self._isle("POST")

    def do_PUT(self) -> None:
        self._isle("PUT")

    def do_DELETE(self) -> None:
        self._isle("DELETE")

    # ------------------------------------------------------------------
    # WEBSOCKET TÜNELİ (443 → yerel WS)
    # ------------------------------------------------------------------
    # GCS'nin WebSocket sunucusu ayrı bir asyncio döngüsünde 9443'te
    # çalışır. Ancak sahada telefon operatörü ağları ve kurum güvenlik
    # duvarları STANDART DIŞI portları düzenli olarak kapatır; canlı
    # gözlemde /app/ arayüzü mobil ağda `wss://...:9443` adresine
    # bağlanamadı ve "Sunucu bağlantısı yok" hatası verdi.
    #
    # `ThreadingHTTPServer` WebSocket yükseltmesini bilmez. Bu yüzden
    # yükseltme isteği HTTP düzeyinde İŞLENMEZ; soket ham TCP olarak
    # yerel WS sunucusuna bağlanıp çift yönlü aktarılır. Böylece tek
    # açık port (443) hem arayüzü hem WebSocket'i taşır.
    WS_TUNEL_YOLLARI = {"/app/ws", "/app_ws", "/kopru", "/ws"}

    def _ws_yukseltme_mi(self) -> bool:
        # RFC 6455: `Upgrade: websocket` + `Connection: Upgrade`.
        # Vekiller Connection başlığına başka değer ekleyebildiği için
        # tam eşitlik değil İÇERME aranır.
        y = (self.headers.get("Upgrade") or "").strip().lower()
        b = (self.headers.get("Connection") or "").strip().lower()
        return y == "websocket" and "upgrade" in b

    def _ws_tunel(self) -> None:
        """Ham TCP düzeyinde yerel WebSocket sunucusuna tünel açar.

        İstek satırı ve başlıklar OLDUĞU GİBİ iletilir; el sıkışmasını
        yerel WS sunucusu yapar. Merkez yalnızca bayt taşır — bu, WS
        protokolünü burada yeniden uygulamak zorunda kalmadan (çerçeve
        ayrıştırma, maskeleme, parçalama) tam uyumluluk sağlar.
        """
        import selectors
        import socket as _sk

        a = ayar_oku()
        # Yerelde şifresiz WS portu: TLS'i dış bacakta zaten yaptık,
        # 127.0.0.1 üzerinde ikinci kez TLS kurmak yalnızca gecikme ekler.
        hedef_port = int(os.environ.get(
            "GOKTUNGU_WS_TUNEL_PORT", a.get("ws_duz_port", 9080)))
        try:
            ic = _sk.create_connection(("127.0.0.1", hedef_port), timeout=15)
        except Exception as e:
            print(f"[WS-TUNEL] Yerel WS'e baglanilamadi "
                  f"(127.0.0.1:{hedef_port}): {type(e).__name__}: {e}")
            self.hata_yaz(502, "WebSocket sunucusuna ulasilamadi")
            return

        # El sıkışma isteğini yeniden kur ve olduğu gibi ilet.
        #
        # KK_TUNEL_XFF_v1: GERCEK tarayici adresi burada eklenir. Bu, zincirin
        # tek noktasi olan yerdir: sonraki katmanlar (`_ws_isle` ->
        # `_app_ws_vekil`) yerelden baglandigi icin es adresi olarak
        # `127.0.0.1` gorur ve gercek istemciyi ASLA bilemez.
        #
        # ISTEMCIDEN GELEN basliklar ATILIR. Aksi halde saldirgan her
        # istekte farkli bir `X-Forwarded-For` gonderip kaba kuvvet
        # sayacinin anahtarini degistirir ve siniri TAMAMEN atlatir.
        # Ayni sozlesme HTTP tarafinda da gecerli (`_kk_es` gercek TCP
        # esini kullanir, basligi degil).
        _atilan = ("x-forwarded-for", "x-real-ip")
        try:
            _gercek = str(self.client_address[0] or "")
        except Exception:
            _gercek = ""
        satirlar = [f"{self.command} {self.path} HTTP/1.1\r\n"]
        for ad, deger in self.headers.items():
            if str(ad).strip().lower() in _atilan:
                continue
            satirlar.append(f"{ad}: {deger}\r\n")
        if _gercek:
            satirlar.append(f"X-Forwarded-For: {_gercek}\r\n")
            satirlar.append(f"X-Real-IP: {_gercek}\r\n")
        satirlar.append("\r\n")
        try:
            ic.sendall("".join(satirlar).encode("latin-1", "replace"))
        except Exception as e:
            print(f"[WS-TUNEL] El sikisma gonderilemedi: {e}")
            with __import__("contextlib").suppress(Exception):
                ic.close()
            return

        dis = self.connection
        # `close_connection` işaretlenmezi: bu soket artık HTTP değildir,
        # BaseHTTPRequestHandler döngüsüne geri dönmemelidir.
        self.close_connection = True
        for s in (dis, ic):
            with __import__("contextlib").suppress(Exception):
                s.settimeout(None)
                s.setsockopt(_sk.IPPROTO_TCP, _sk.TCP_NODELAY, 1)

        sec = selectors.DefaultSelector()
        sec.register(dis, selectors.EVENT_READ, ic)
        sec.register(ic, selectors.EVENT_READ, dis)
        try:
            while True:
                # Zaman aşımı: iki taraf da sessizse döngü sonsuza
                # kilitlenmesin. WS ping aralığı 20 sn olduğu için 300 sn
                # sessizlik bağlantının gerçekten öldüğü anlamına gelir.
                olaylar = sec.select(timeout=300)
                if not olaylar:
                    break
                for anahtar, _ in olaylar:
                    kaynak = anahtar.fileobj
                    hedef_s = anahtar.data
                    try:
                        veri = kaynak.recv(65536)
                    except Exception:
                        return
                    if not veri:
                        return
                    try:
                        hedef_s.sendall(veri)
                    except Exception:
                        return
        finally:
            with __import__("contextlib").suppress(Exception):
                sec.close()
            with __import__("contextlib").suppress(Exception):
                ic.close()

    # ------------------------------------------------------------------
    # v2.4.71 — ALAN ADI VE ŞEMA YÖNLENDİRMESİ
    # ------------------------------------------------------------------
    # İki ayrı görev tek yerde toplanır:
    #   1. Düz HTTP (port 80) → HTTPS. Önceden port 80 içeriği 200 ile
    #      sunuyordu; oturum çerezi şifresiz ağda taşınıyordu.
    #   2. Eski alan adı (`gozcu.veilox.com.tr`) → `goktungu.com`. Marka
    #      geçişi sonrası eski adres çalışmaya devam eder ama kalıcı
    #      olarak yeni adrese taşınır.
    #
    # MUAFİYET: `/.well-known/acme-challenge/` yönlendirilmez. Let's
    # Encrypt HTTP-01 doğrulaması düz HTTP üzerinden yapılır; burada
    # yönlendirme yapılırsa eski alan adının sertifika yenilemesi kırılır.
    #
    # 301 (kalıcı) kullanılır: tarayıcı ve arama motoru yeni adresi
    # önbelleğe alır. GET/HEAD dışı yöntemlerde 308 kullanılır çünkü 301
    # istemcilerin POST'u GET'e çevirmesine izin verir ve gövde kaybolur.

    ACME_MUAF = "/.well-known/acme-challenge/"
    # v2.4.72 MUAFIYET 2: dahili uclar (`/api/ic/`). Bu uclar yalniz
    # 127.0.0.1 esinden ve `X-Ic-Anahtar` paylasilan siri ile erisilir;
    # app sureci merkeze ayni makineden POST atar. HTTPS zorlamasi
    # burada guvenlik katkisi saglamaz, yalniz cagriyi kirar: `urllib`
    # POST isteginde 308 yonlendirmesini IZLEMEZ, bu yuzden `servis_durum`
    # dahil tum kopru sorgulari "HTTP 308" ile doner ve arayuzde bes
    # servis rozeti `?` kalir (olculdu 18 Agu 2026).
    IC_MUAF = "/api/ic/"

    def _konak(self) -> str:
        """`Host` başlığından port ve köşeli parantezi ayıklar."""
        h = (self.headers.get("Host") or "").strip().lower()
        if h.startswith("["):                      # IPv6 literal
            kapanis = h.find("]")
            return h[: kapanis + 1] if kapanis > 0 else h
        return h.split(":", 1)[0]

    # ================= FAZ15-ALTALAN =================================
    # Alt alan adi -> ic yol yeniden yazimi.
    #
    #   app.goktungu.com/js/ws.js  -> ic yol /app/js/ws.js
    #   admin.goktungu.com/        -> ic yol /admin/
    #   company.goktungu.com/      -> ic yol /company/
    #   support.goktungu.com/      -> ic yol /yardim/
    #
    # YONLENDIRME DEGIL yeniden yazim: 301 kullanilsa kullanici
    # `goktungu.com/app/` adresine duser ve alt alan adinin amaci bosa
    # cikardi.  Yeniden yazimda adres cubugu alt alan adinda kalir.
    #
    # MERKEZ UYGULAMA KISITI: Merkez Uygulama satin alan firmalar
    # sistemi kapali devre veya `localhost` uzerinde calistiriyor; orada
    # alt alan adi YOKTUR.  Bu tablo yalniz ana makine
    # `<alt>.<alan_adi>` kalibina uyarsa devreye girer.  Yol tabanli
    # erisim (`/app/`, `/admin/`, ...) ASLA kaldirilmaz.
    ALTALAN_ONEK = {
        "app": "/app",
        "admin": "/admin",
        "company": "/company",
        "support": "/yardim",
        "gpstracker": "/gpstracker",
    }

    # Yeniden yazimdan MUAF yollar.  En kritik grup PAYLASILAN
    # VARLIKLAR: dort panelin hepsi `/js/tema.js`, `/img/...webp` gibi
    # KOK yollari kullaniyor (olculdu).  Bunlar yeniden yazilirsa
    # `/admin/js/tema.js` aranir, bulunmaz ve tum paneller kirilir.
    ALTALAN_MUAF = (
        "/api/",            # merkez API tablosu
        "/indir/",          # depo + lisans/oturum kapisi
        "/varlik/",         # kullanici varliklari
        "/video/",          # video kayitlari
        "/js/",             # PAYLASILAN
        "/css/",            # PAYLASILAN
        "/img/",            # PAYLASILAN
        "/fonts/",          # PAYLASILAN
        "/yasal/",          # paylasilan yasal metinler
        "/.well-known/",    # ACME
    )
    # Tam eslesen kok varliklar (onek degil, birebir).
    ALTALAN_MUAF_TAM = (
        "/favicon.ico", "/manifest.json", "/sw.js", "/robots.txt",
        "/sitemap.xml",
    )

    def _altalan(self) -> str | None:
        """Ana makine `<alt>.<alan_adi>` ise alt adi, degilse None.

        Merkez kurulumlarinda (IP, `localhost`, firmanin kendi alan
        adi) None doner ve yeniden yazim hic devreye girmez.
        """
        konak = self._konak()
        if not konak:
            return None
        try:
            kok = (ayar_oku().get("alan_adi") or "").strip().lower()
        except Exception:
            return None
        if not kok or "." not in kok:
            return None
        son = "." + kok
        if not konak.endswith(son):
            return None
        alt = konak[: -len(son)]
        # Yalniz TEK etiketli alt ad kabul edilir; `a.b.goktungu.com`
        # tanimli degil ve sessizce `a.b` olarak eslenmemeli.
        if not alt or "." in alt:
            return None
        return alt if alt in self.ALTALAN_ONEK else None

    # FAZ15-ALTALAN-APP: muafiyet ALT ALAN ADI BASINA ayrilir.
    #
    # `admin`/`company`/`support` merkez web kokunu PAYLASIR; onlarda
    # `/js/`, `/css/`, `/img/` gibi kok yollar muaf kalmali yoksa
    # `/admin/js/tema.js` aranir ve paneller stilsiz kalir.
    #
    # `app` ise KENDI KOKUNDE tam bir uygulama ve varliklarini GORELI
    # yolla cagiriyor (`src="js/ws.js"`).  Alt alan adinda sayfa `/`
    # kokunde durdugu icin tarayici `/js/ws.js` ister; muaf tutulursa
    # merkezin kok dizininde aranir.  Olculen sonuc: `/js/ws.js` 404,
    # `/css/stil.css` ise 404 bile vermeyip MERKEZIN CSS'ini donuyordu
    # (app yanlis stille acilirdi).  Bu yuzden `app` icin varlik
    # muafiyeti UYGULANMAZ.
    ALTALAN_MUAF_YOK = ("app", "gpstracker")

    def _altalan_muaf_mi(self, yol: str, alt: str | None = None) -> bool:
        # WebSocket tunelleri her alt alan adinda muaf: kopru
        # `wss://goktungu.com/kopru` kullaniyor, sahadaki kurulu
        # koprular kirilmamali.
        if yol.rstrip("/") in {y.rstrip("/") for y in self.WS_TUNEL_YOLLARI}:
            return True
        # ACME her durumda muaf; sertifika yenilemesi kirilmamali.
        if yol.startswith("/.well-known/"):
            return True
        if alt in self.ALTALAN_MUAF_YOK:
            return False
        if yol in self.ALTALAN_MUAF_TAM:
            return True
        for o in self.ALTALAN_MUAF:
            if yol.startswith(o):
                return True
        return False

    def _altalan_yaz(self) -> None:
        """Alt alan adindan gelen istegin ic yolunu yeniden yazar.

        `self.path` uzerinde calisir cunku `Istek` nesnesi henuz
        kurulmamis olabilir ve `_dosya_sun`/`_app_vekil` ikisi de bu
        alandan turer.
        """
        alt = self._altalan()
        if not alt:
            return
        onek = self.ALTALAN_ONEK[alt]
        ham = self.path or "/"
        parca = ham.split("?", 1)
        yol = parca[0] or "/"
        sorgu = ("?" + parca[1]) if len(parca) == 2 else ""
        if self._altalan_muaf_mi(yol, alt):
            return
        # Zaten onekliyse ikinci kez yazma (idempotent).
        if yol == onek or yol.startswith(onek + "/"):
            return
        yeni = onek + yol
        # Kok istek: `/app` degil `/app/` olmali -- `/app` 301 dongusune
        # girer, `/admin` ise DIZIN_YOLLARI uzerinden yine 301 alir.
        if yol == "/":
            yeni = onek + "/"
        self.path = yeni + sorgu

    def _kanonik_altalan(self, yontem: str) -> str | None:
        """Kok alan adindaki panel yolunu alt alan adina tasir.

        `goktungu.com/app/x` -> `https://app.goktungu.com/x`

        YALNIZ kok alan adinda ve TLS varken yapilir.  Merkez
        kurulumlarinda `alan_adi` firmanin kendi adi olur ve alt alan
        adlari tanimsizdir; bu yuzden ana makine kok alan adina birebir
        esit olmali VE alt alan adi cozumleniyor olmali sayilmaz --
        cozumleme sunucunun bilgisi disindadir, bu yuzden karar
        AYAR'a baglanir (`altalan_kanonik`, ontanimli kapali).
        """
        try:
            a = ayar_oku()
        except Exception:
            return None
        if not a.get("altalan_kanonik", False):
            return None
        kok = (a.get("alan_adi") or "").strip().lower()
        if not kok:
            return None
        if self._konak() != kok:
            return None
        ham = self.path or "/"
        parca = ham.split("?", 1)
        yol = parca[0] or "/"
        sorgu = ("?" + parca[1]) if len(parca) == 2 else ""
        for alt, onek in self.ALTALAN_ONEK.items():
            if yol == onek or yol == onek + "/" or yol.startswith(onek + "/"):
                # Muafiyet hedef alt alan adina gore degerlendirilir:
                # `/app/js/ws.js` app icin muaf DEGIL (tasinmali),
                # `/admin/api/x` ise `/api/` muafiyetiyle yerinde kalir.
                if self._altalan_muaf_mi(yol[len(onek):] or "/", alt):
                    return None
                kalan = yol[len(onek):] or "/"
                if not kalan.startswith("/"):
                    kalan = "/" + kalan
                return f"https://{alt}.{kok}{kalan}{sorgu}"
        return None
    # ================= /FAZ15-ALTALAN ================================

    def _yonlendirme_gerek(self, yontem: str) -> str | None:
        """Gerekiyorsa tam hedef adresi, gerekmiyorsa None döndürür."""
        yol = self.path or "/"
        if yol.startswith(self.ACME_MUAF):
            return None
        if yol.startswith(self.IC_MUAF):
            return None
        konak = self._konak()
        if not konak:
            return None
        tls_var = getattr(self.server, "tls_baglam", None) is not None
        a = ayar_oku()
        hedef_ad = (a.get("alan_adi") or "").strip().lower()
        eski = {e.strip().lower()
                for e in (a.get("eski_alan_adlari") or []) if e.strip()}

        # Eski alan adı → yeni alan adı (şema her durumda https olur)
        if konak in eski and hedef_ad:
            return f"https://{hedef_ad}{yol}"
        # Düz HTTP → HTTPS (konak korunur; alt alan adları çalışsın)
        if not tls_var:
            # Klasik SIM800 TLS 1.2 ile uyumlu değildir. Yalnız HMAC ile
            # doğrulanan GPS POST ucu HTTP'de kalır; diğer tüm yollar HTTPS'e
            # yönlendirilir. Konum gizliliği için TLS 1.2 modem zorunludur.
            _ham_yol = yol.split("?", 1)[0]
            if yontem == "POST" and _ham_yol.startswith("/gpstrack/"):
                return None
            if not a.get("https_zorla", True):
                return None
            return f"https://{konak}{yol}"
        return None

    def _yonlendir(self, hedef: str, yontem: str) -> None:
        kod = 301 if yontem in ("GET", "HEAD") else 308
        self.send_response(kod)
        self.send_header("Location", hedef)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "max-age=0")
        self.end_headers()

    def _isle(self, yontem: str) -> None:
        # v2.4.71: şema/alan adı yönlendirmesi EN BAŞTA. WebSocket
        # yükseltmesinden de önce gelir: `ws://` ile eski adrese bağlanan
        # istemci `wss://` yeni adrese taşınmalıdır, tünellenmemelidir.
        _hedef = self._yonlendirme_gerek(yontem)
        if _hedef:
            self._yonlendir(_hedef, yontem)
            return
        # FAZ15-ALTALAN: kok alan adindaki panel yolunu alt alan adina
        # tasi (kanonik adres), ardindan alt alan adindan gelen istegin
        # ic yolunu yeniden yaz.  SIRA KRITIK: yeniden yazim `/app/`
        # vekil dalindan ve `YOL_TABLOSU`'ndan ONCE olmali.
        _kan = self._kanonik_altalan(yontem)
        if _kan:
            self._yonlendir(_kan, yontem)
            return
        self._altalan_yaz()
        # WebSocket yükseltmesi HTTP yönlendirmesinden ÖNCE ele alınır:
        # Istek nesnesi gövde okumaya çalışır, oysa yükseltme isteğinde
        # gövde yoktur ve soket ham aktarıma geçmelidir.
        if yontem == "GET" and self._ws_yukseltme_mi() and \
                self.path.split("?")[0].rstrip("/") in {
                    y.rstrip("/") for y in self.WS_TUNEL_YOLLARI}:
            self._ws_tunel()
            return
        try:
            istek = Istek(self)
        except Exception:
            self.hata_yaz(400, "İstek okunamadı")
            return
        # GPSTRACKER AÇIK İZ API'Sİ: Sadece listelenen GET ucu yerel
        # GPS gateway'e taşınır. Statik kullanıcı arayüzü WEB_KOKU'ndan
        # sunulmaya devam eder; oturum veya cihaz sırrı bu dala girmez.
        if istek.yol.startswith("/gpstracker/api/"):
            gpstracker_vekil.isle(self, istek)
            return
        # GPS ALIM KAPISI: Ana uygulama yollarından tamamen ayrıdır.
        # Yerel gateway yalnız 127.0.0.1:18088 dinler; bu dal ona TLS
        # sonlandırılmış /gpstrack/ isteğini iletir.
        if istek.yol == "/gpstrack":
            self.send_response(301)
            self.send_header("Location", "/gpstrack/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if istek.yol.startswith("/gpstrack/"):
            gpstrack_vekil.isle(self, istek)
            return
        # /app/ altindaki her sey GOKTUNGU surecine tasinir. Bu dal
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
        # v2.4.57: ikinci ekran ucus duvari kisayolu.
        # GCS surecinde sayfa `/flight` adresinde durur, ancak merkezde
        # GCS tumuyle `/app/` onekinin ARKASINDADIR. Operator ikinci
        # ekrana yalnizca `/flight` yazdiginda merkez bu yolu kendi
        # statik dosya kokunde arar, bulamaz ve `{"hata":"Bulunamadi"}`
        # doner (olculen vaka). Yol `/app/flight` olarak tasinir;
        # 302 kullanilir cunku ilgili adres kalicilik vaadi tasimaz.
        if istek.yol.rstrip("/") == "/flight":
            hedef = "/app/flight"
            sorgu = self.path.split("?", 1)
            if len(sorgu) == 2:
                hedef += "?" + sorgu[1]
            self.send_response(302)
            self.send_header("Location", hedef)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        # KABA KUVVET: yetki denetiminden ONCE. Yeni bir giris
        # ucu eklendiginde koruma elle kopyalanmak zorunda
        # kalmasin diye ortak katmandadir.
        if self._kk_denetle(istek):
            return
        # FAZ18-IS24-BAKIM-KIPI: BAKIM KIPI KAPISI.
        # Kaba kuvvet denetiminden SONRA, yetki denetiminden ONCE.
        # Tasima katmaninda olmasinin gerekcesi kaba kuvvet ile
        # ayni: yeni bir kayit ucu eklendiginde kapi elle
        # kopyalanmak zorunda kalmasin ve sessizce atlanmasin.
        if self._bakim_denetle(istek):
            return
        try:
            for y, desen, islev, yetki in YOL_TABLOSU:
                if y != yontem:
                    continue
                m = desen.match(istek.yol)
                if not m:
                    continue
                oturum = None
                if yetki == "yonetici":
                    oturum = kimlik.yonetici_oturum(istek.jeton())
                    if not oturum:
                        self.hata_yaz(401, "Oturum gerekli")
                        return
                elif yetki == "firma":
                    oturum = kimlik.kullanici_oturum(istek.firma_jetonu())
                    if not oturum:
                        self.hata_yaz(401, "Oturum gerekli")
                        return
                elif yetki == "destek":
                    # Destek personeli VEYA sistem yoneticisi (ust yetki).
                    # Rol denetimi TASIMA KATMANINDA: uc govdesinde
                    # yapilinca yeni uc eklendiginde atlanabilir ve
                    # sessiz yetki yukseltmesi olusur.
                    oturum = kimlik.yonetici_oturum(istek.jeton())
                    if not oturum:
                        self.hata_yaz(401, "Oturum gerekli")
                        return
                    if str(oturum.get("rol")) not in ("sistem_yonetici",
                                                       "destek_personel"):
                        self.hata_yaz(403, "Destek yetkisi gerekir")
                        return
                elif yetki == "firma_yonetici":
                    # ROL KAPISI: `yetki="firma"` YALNIZ oturum varligini
                    # dogrular, rol AYIRMAZ.  Dolayisiyla pilot ve gozlemci
                    # rolleri de firma uclarinin tamamini cagirabiliyordu;
                    # rol denetimi uc uc, islev govdesinde elle yapiliyordu
                    # (`if oturum.get("rol") != "firma_yonetici"`) ve yeni
                    # eklenen bir ucta atlanmasi sessiz bir yetki yukseltme
                    # kusuru dogururdu.  Bu duzey denetimi tasima katmanina
                    # tasir: yalniz firma yoneticisi gecer.
                    oturum = kimlik.kullanici_oturum(istek.firma_jetonu())
                    if not oturum:
                        self.hata_yaz(401, "Oturum gerekli")
                        return
                    if str(oturum.get("rol")) != "firma_yonetici":
                        self.hata_yaz(
                            403, "Bu işlem için kurum yöneticisi yetkisi "
                                 "gerekir")
                        return
                elif yetki != "acik":
                    # SERTLESTIRME (v2.5.1): taninmayan yetki degeri
                    # REDDEDILIR.
                    #
                    # NEDEN: bu zincir bir `else` dali TASIMIYORDU.  Bir uc
                    # `yetki="admin"` gibi var olmayan bir degerle
                    # tanimlandiginda hicbir dala girmiyor, `oturum` None
                    # kaliyor ve islev KIMLIK DOGRULAMASI OLMADAN
                    # calisiyordu.  Bu gercekten yasandi: SMTP yapilandirma
                    # uclari `yetki="admin"` ile eklendi ve
                    # `GET /api/admin/smtp` yetkisiz 200 dondu.
                    #
                    # Sessiz acik kalmak yerine sessiz kapali kalmak
                    # secildi: yazim yanlisi olan bir uc 500 verip hemen
                    # fark edilir, kimlik dogrulamasiz calismaz.
                    print("[YETKI] Taninmayan yetki duzeyi %r (%s %s) - "
                          "istek reddedildi" % (yetki, yontem, istek.yol))
                    self.hata_yaz(500, "Sunucu yapılandırma hatası")
                    return
                islev(self, istek, oturum, *m.groups())
                return
            # API dışı yollar dosya olarak sunulur
            if yontem == "GET":
                self._dosya_sun(istek)
                return
            self.hata_yaz(404, "Bulunamadı")
        except BrokenPipeError:
            pass
        except Exception as e:
            print(f"[HTTP] {istek.yol} hata: {e}")
            traceback.print_exc()
            try:
                self.hata_yaz(500, f"Sunucu hatası: {e}")
            except Exception:
                pass

    # -- statik dosya ---------------------------------------------------
    # Egik cizgisiz dizin adresleri 301 ile egik cizgiliye tasinir.
    # NEDEN: tarayici `/admin` adresini DOSYA sayar ve HTML icindeki
    # goreli `href="stil.css"` yolunu `/stil.css` olarak cozer; o yol
    # yok, 404 doner ve panel BICIMLENDIRMESIZ gorunur. Yonlendirme
    # olmadan bu kusur her dizin altinda tekrarlanir.
    DIZIN_YOLLARI = ("/admin", "/company")

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
    }

    # -- /app/ vekili ---------------------------------------------------
    def _app_vekil_akis(self, y) -> None:
        """Sonsuz/parcali yaniti TAMPONSUZ olarak istemciye aktarir.

        MJPEG canli goruntu bu yoldan gecer. `Content-Length`
        YAZILMAZ (bilinmiyor) ve baglanti kapanana kadar surer.
        Her parcadan sonra `flush()` cagrilir: aksi halde isletim
        sistemi tamponu dolana kadar kareler BEKLETILIR ve canli
        goruntu donuk/gecikmeli gorunur.
        """
        try:
            kod = getattr(y, "status", None) or y.code
            self.send_response(kod)
            for ad, deger in y.headers.items():
                dad = ad.lower()
                if dad in self.ATLANAN_BASLIK:
                    continue
                # Uzunluk/kodlama basliklari YENIDEN uretilmez:
                # akisin boyutu bilinmiyor, parcali kodlamayi da
                # biz yapmiyoruz (baglanti kapanisi sinir olur).
                if dad in ("content-length", "transfer-encoding"):
                    continue
                self.send_header(ad, deger)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command == "HEAD":
                return
            while True:
                p = y.read(8192)
                if not p:
                    break
                self.wfile.write(p)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # Izleyici sekmeyi kapatti. Beklenen son; gunluge
            # yazmak gurultu olur.
            pass
        except Exception:
            # Akis ortasinda hata: baslik zaten gonderildigi icin
            # HTTP hata kodu YAZILAMAZ. Baglantiyi birakmak tek
            # dogru davranis; istemci yeniden baglanir.
            pass
        finally:
            try:
                y.close()
            except Exception:
                pass

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
        # SIZINTI ENGELI (BULGU_04): kaynak kod, `veri/`, sertifika ve
        # yedek dosyalari GCS surecine HIC tasinmaz. Karar `/app/`
        # onegi soyulmus yol uzerinden verilir; boylece app tarafindaki
        # engelle ayni yol uzayinda calisir.
        if _app_engelli_mi(ic_yol):
            self.hata_yaz(404, "Bulunamadı")
            return
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
        # FAZ19-IS60B: AKIS KIPI AYRIMI.
        # MJPEG (`multipart/x-mixed-replace`) SONSUZ bir yanittir;
        # `y.read()` asla donmez, istek 120 sn sonra timeout olur ve
        # bu arada bellek siser. Boyle yanitlar PARCA PARCA aktarilir.
        # Diger tum yanitlar ESKI yoldan gider: `Content-Length` ile
        # kesin boyut bildirimi tarayici onbellegi icin degerlidir,
        # calisan davranisi gereksiz yere degistirmiyoruz.
        try:
            y = urllib.request.urlopen(istek_nesnesi, timeout=120)
        except urllib.error.HTTPError as e:
            y = e
        except Exception as e:
            self.hata_yaz(
                502, f"Uygulama sunucusuna ulasilamadi: {e}")
            return
        _ct = (y.headers.get("Content-Type") or "").lower()
        _te = (y.headers.get("Transfer-Encoding") or "").lower()
        if ("multipart/x-mixed-replace" in _ct
                or "chunked" in _te):
            self._app_vekil_akis(y)
            return
        # NOT: `HTTPError` YUKARIDA yakalanip `y`ye baglandi (HTTPError
        # de bir yanit nesnesidir: `.read()`, `.headers`, `.code` tasir).
        # Burada ikinci kez yakalamak OLU KOD olurdu.
        try:
            with y:
                icerik = y.read()
                kod = getattr(y, "status", None) or y.code
                basliklar = list(y.headers.items())
        except Exception as e:
            # Govde okunurken kopma. Baslik henuz YAZILMADIGI icin
            # gercek bir HTTP hata kodu dondurulebilir.
            self.hata_yaz(502, f"Uygulama sunucusuna ulasilamadi: {e}")
            return
        # IS67_GZIP_v1: app surecinden (18000/SimpleHTTP) gelen
        # govde sikistirilmamistir — arayuzun 10.48 MB'lik yuku
        # TAM OLARAK buradan gecer. Sikistirma bu kapida yapilir;
        # app sureci hic degistirilmez.
        _gz_tur = ""
        _gz_var = False
        for _a, _d in basliklar:
            _al = _a.lower()
            if _al == "content-type":
                _gz_tur = _d
            elif _al == "content-encoding":
                _gz_var = True
        _gz_ek = None
        try:
            if (kod == 200 and self.command != "HEAD"
                    and not _gz_var
                    and _gz_uygun_mu(_gz_tur, icerik, self.headers)):
                _s = _gz_sikistir(icerik)
                if len(_s) < len(icerik):
                    icerik = _s
                    _gz_ek = "gzip"
        except BaseException:
            _gz_ek = None
        self.send_response(kod)
        for ad, deger in basliklar:
            if ad.lower() in self.ATLANAN_BASLIK:
                continue
            if ad.lower() == "vary" and _gz_ek:
                continue
            self.send_header(ad, deger)
        if _gz_ek:
            self.send_header("Content-Encoding", _gz_ek)
            self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(icerik)))
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(icerik)
            except BrokenPipeError:
                pass

    def _dosya_sun(self, istek: Istek) -> None:
        yol_ = istek.yol
        # Yedek/kaynak dosya engeli: statik sunumun ILK kapisi.
        # Yol cozumlemesinden ONCE bakilir; boylece `/varlik/`,
        # `/video/` ve web koku dallarinin hepsi kapsanir.
        if _yedek_yolu_mu(yol_):
            self.hata_yaz(404, "Bulunamadı")
            return
        if yol_ in self.DIZIN_YOLLARI:
            self.send_response(301)
            self.send_header("Location", yol_ + "/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if yol_.startswith("/indir/"):
            # LISANS KAPISI: `/indir/` kimlik istemeyen statik sunucudur.
            # Ucretsiz dagitilan urunler (kopru vb.) buradan serbestce
            # inilir; ancak `depo.LISANSLI_URUNLER` uyeleri parayla
            # satilir ve dosya adini bilen herkese acik olamaz. Onlar
            # yalnizca oturum + lisans dogrulayan `/api/firma/merkez_indir`
            # ucundan inilir. Ad tahmini korumasi degil, gercek kapi:
            # urun parcasi listede ise istek burada reddedilir.
            goreli = yol_[len("/indir/"):]
            ilk = goreli.split("/", 1)[0].strip().lower()
            if ilk in depo.LISANSLI_URUNLER:
                self.hata_yaz(
                    403, "Bu ürün lisanslıdır; kurumsal panelinizden "
                         "indirmeniz gerekir")
                return
            # OTURUM KAPISI: kopru ucretsizdir ama dagitimi kurumsal
            # panelden yurur (kullanici karari 2026-08-16).  Boylece
            # kimin indirdigi kayitlanir ve tanitim sayfasinda eskiyen
            # surum baglantisi kalmaz.
            if ilk in getattr(depo, "OTURUM_GEREKEN_URUNLER", ()):
                # IS83B-KAPI-MESAJI
                # OLCULEN KUSUR: mesaj SABIT "Kopru Yazilimi sayfasini
                # kullanin" diyordu. `OTURUM_GEREKEN_URUNLER` artik iki
                # urun tasidigi icin Goruntu Koprusu indirmeye calisan
                # kullanici YANLIS sayfaya yonlendiriliyordu.
                #
                # Bilinmeyen urun icin sayfa adi VERILMEZ: yanlis sayfa
                # adi vermektense hic vermemek dogru davranistir.
                _sayfa = {"kopru": "Köprü Yazılımı",
                          "video": "Görüntü Köprüsü"}.get(ilk)
                self.hata_yaz(
                    403, "Bu paket kurumsal panelinizden indirilir; "
                         "giriş yaptıktan sonra " +
                         ("%s sayfasını" % _sayfa if _sayfa
                          else "ilgili indirme sayfasını") +
                         " kullanın")
                return
            kok = DEPO_KOKU
        elif yol_.startswith("/varlik/"):
            kok, goreli = os.path.join(VERI_KOKU, "varlik"), yol_[len("/varlik/"):]
        elif yol_.startswith("/video/"):
            kok, goreli = os.path.join(VERI_KOKU, "video"), yol_[len("/video/"):]
        else:
            kok, goreli = WEB_KOKU, yol_.lstrip("/")
        if yol_ in ("/", ""):
            goreli = "index.html"
        elif yol_ == "/admin/":
            kok, goreli = WEB_KOKU, "admin/index.html"
        elif yol_ == "/company/":
            # ROL KAPISI: kurumsal panel YALNIZ kurum yoneticisine acilir
            # (kullanici karari 2026-08-16: "sistem yoneticisi olmayan
            # pilotlar kurumsal panele giremesin").
            #
            # OTURUMSUZ ERISIM SERBEST BIRAKILIR ve bu kasitlidir: sayfa
            # kendi giris formunu barindirir, kimlik istenirse hicbir
            # kullanici giris yapamaz.  Kapi yalniz KIMLIGI BILINEN ve
            # rolu yetersiz olan oturumu reddeder.  Boylece pilot,
            # tanitim sayfasindan giris yaptiktan sonra adres cubugna
            # /company/ yazarak paneli acamaz.
            o = kimlik.kullanici_oturum(istek.firma_jetonu())
            if o and str(o.get("rol")) != "firma_yonetici":
                self.hata_yaz(
                    403, "Kurumsal panel yalnız kurum yöneticisi "
                         "tarafından kullanılır")
                return
            kok, goreli = WEB_KOKU, "company/index.html"
        hedef = os.path.normpath(os.path.join(kok, goreli))
        if not hedef.startswith(os.path.realpath(kok)) and \
           not hedef.startswith(kok):
            self.hata_yaz(403, "Erişim engellendi")
            return
        if os.path.isdir(hedef):
            hedef = os.path.join(hedef, "index.html")
        if not os.path.isfile(hedef):
            # v2.13: tarayici istegi ise bicimlendirilmis 404 sayfasi
            # sunulur.  JSON yalniz API/varlik istekleri icin kalir:
            # `curl`, `fetch` ve <img>/<script> istekleri HTML govde
            # alirsa sessizce bozulur.  Ayrim `Accept` basligiyla
            # yapilir -- tarayici gezinme istegi daima `text/html` ister.
            kabul = (self.headers.get('Accept') or '')
            s404 = os.path.join(WEB_KOKU, '404.html')
            if 'text/html' in kabul and os.path.isfile(s404):
                try:
                    with open(s404, 'rb') as _f:
                        govde = _f.read()
                    self.send_response(404)
                    self.send_header('Content-Type',
                                     'text/html; charset=utf-8')
                    self.send_header('Content-Length', str(len(govde)))
                    self.send_header('X-Content-Type-Options', 'nosniff')
                    self.end_headers()
                    if self.command != 'HEAD':
                        self.wfile.write(govde)
                    return
                except BrokenPipeError:
                    return
                except Exception:
                    pass   # sayfa okunamadi: JSON'a dus
            self.hata_yaz(404, "Bulunamadı")
            return
        tur = mimetypes.guess_type(hedef)[0] or "application/octet-stream"
        boyut = os.path.getsize(hedef)
        # Bayt aralığı (video oynatma için zorunlu)
        aralik = self.headers.get("Range")
        if aralik and aralik.startswith("bytes="):
            try:
                bas_s, _, son_s = aralik[6:].partition("-")
                bas = int(bas_s) if bas_s else 0
                son = int(son_s) if son_s else boyut - 1
                son = min(son, boyut - 1)
                if bas > son:
                    raise ValueError
                with open(hedef, "rb") as f:
                    f.seek(bas)
                    parca = f.read(son - bas + 1)
                self.send_response(206)
                self.send_header("Content-Type", tur)
                self.send_header("Content-Length", str(len(parca)))
                self.send_header("Content-Range", f"bytes {bas}-{son}/{boyut}")
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(parca)
                return
            except Exception:
                pass
        with open(hedef, "rb") as f:
            govde = f.read()
        # Arayuz kodu (html/js/css/json) her istekte dogrulanir: aksi halde
        # sunucu guncellendikten sonra tarayici eski JS'i calistirir ve
        # panel, dogru API yanitina ragmen bos veya hatali gorunur. Medya
        # ve gorseller uzun sureli onbelleklenir.
        kod = hedef.endswith((".html", ".js", ".css", ".json", ".map"))
        ek = {"Accept-Ranges": "bytes"}
        if kod:
            ek["Cache-Control"] = "no-cache, must-revalidate"
            try:
                d = os.stat(hedef)
                ek["ETag"] = f'W/"{int(d.st_mtime)}-{d.st_size}"'
            except OSError:
                pass
            # Istemcideki kopya guncel ise govde tekrar gonderilmez
            if ek.get("ETag") and \
                    self.headers.get("If-None-Match") == ek["ETag"]:
                self.send_response(304)
                for a, d2 in ek.items():
                    self.send_header(a, d2)
                self.end_headers()
                return
        else:
            ek["Cache-Control"] = "public, max-age=86400"
        self._yaz(200, govde, tur, ek)


# ==========================================================================
# GENEL UÇ NOKTALAR
# ==========================================================================
@yol("GET", r"/api/genel/kimlik", yetki="acik")
def _u_kimlik(h, istek, oturum):
    h.json_yaz(api.sunucu_kimligi())


@yol("GET", r"/api/genel/saglik", yetki="acik")
def _u_saglik(h, istek, oturum):
    h.json_yaz(api.saglik())


@yol("POST", r"/api/admin/giris", yetki="acik")
def _u_giris(h, istek, oturum):
    e = (istek.govde.get("eposta") or "").strip()
    s = istek.govde.get("sifre") or ""
    veri, hata = kimlik.yonetici_giris(
        e, s, istek.ip, istek.h.headers.get("User-Agent"))
    if hata == "E-POSTA_DOGRULANMADI":
        h.json_yaz({"hata": "E-posta adresiniz doğrulanmadı",
                    "dogrulama_gerekli": True}, 403)
        return
    if hata:
        h.json_yaz({"hata": hata}, 401)
        return
    # IS9B-CEREZ-ALANI: `Host` gecirilir; cerez kok alan adina baglanir.
    kurabiye = kimlik.kurabiye_yaz("goktungu_admin", veri["jeton"],
                                   istek.h.headers.get("Host"))
    h.json_yaz({"tamam": True, "yonetici": veri}, 200, {"Set-Cookie": kurabiye})


@yol("POST", r"/api/admin/cikis")
def _u_cikis(h, istek, oturum):
    kimlik.yonetici_cikis(oturum["jeton"])
    # IS9B-CEREZ-ALANI: silme dizesi yazma ile AYNI Domain'i tasir.
    h.json_yaz({"tamam": True}, 200,
               {"Set-Cookie": kimlik.kurabiye_sil(
                   "goktungu_admin", istek.h.headers.get("Host"))})


@yol("GET", r"/api/admin/ben")
def _u_ben(h, istek, oturum):
    h.json_yaz({"yonetici": {a: oturum[a] for a in
                             ("yonetici_id", "eposta", "ad_soyad", "unvan", "rol")}})


# ==========================================================================
# GÖSTERGE / DENETİM
# ==========================================================================
@yol("GET", r"/api/admin/gosterge")
def _u_gosterge(h, istek, oturum):
    h.json_yaz(api.gosterge())


# ---------------------------------------------------------------- #
# GUVENLIK / SALDIRI IZLEME UCLARI                    FAZ18-IS9-GUVENLIK-IZLEME       #
#                                                                    #
# Yetki: `yol()` ontanimli `yonetici`. Rol denetimi TASIMA           #
# KATMANINDA (satir ~979). Govdede elle denetim YOK — kodun kendi    #
# sozlesmesi bunu yasakliyor (sessiz yetki yukseltmesi riski).       #
#                                                                    #
# Veri kaynagi UC katmanli, `mk_guvenlik` birlestirir:               #
#   1. `mk_kaba_kuvvet` bellegi -> etkin bloklar (KALICI DEGIL)      #
#   2. merkez gunlugu           -> kalici blok gecmisi               #
#   3. fail2ban gunlugu         -> ag katmani yasaklari              #
#                                                                    #
# Yeni tablo eklenmedi: veri zaten iki yerde kalici; her giris       #
# denemesinde veritabani yazimi saldiri aninda veritabanini yuk      #
# altinda birakirdi.                                                 #
# ---------------------------------------------------------------- #
@yol("GET", r"/api/admin/guvenlik/ozet")
def _u_guvenlik_ozet(h, istek, oturum):
    try:
        gun = int(istek.sorgu.get("gun", 7))
    except BaseException:
        gun = 7
    gun = max(1, min(gun, 90))
    try:
        h.json_yaz(guvenlik.ozet(gun))
    except BaseException as e:
        # Gorunurluk ucu ASLA panelin tamamini dusurmemeli.
        h.json_yaz({"hata": str(e), "canli": {}, "gecmis": {},
                    "fail2ban": {}}, 200)


@yol("GET", r"/api/admin/guvenlik/olaylar")
def _u_guvenlik_olaylar(h, istek, oturum):
    try:
        sinir = int(istek.sorgu.get("sinir", 200))
    except BaseException:
        sinir = 200
    try:
        h.json_yaz(guvenlik.olaylar(sinir,
                                    str(istek.sorgu.get("tur") or ""),
                                    str(istek.sorgu.get("ip") or "")))
    except BaseException as e:
        h.json_yaz({"olaylar": [], "kalici": False, "hata": str(e)}, 200)


@yol("POST", r"/api/admin/guvenlik/coz")
def _u_guvenlik_coz(h, istek, oturum):
    g = istek.govde or {}
    ip = str(g.get("ip") or "").strip()
    hesap = str(g.get("hesap") or "").strip()
    if not ip and not hesap:
        h.hata_yaz(400, "ip veya hesap zorunlu")
        return
    try:
        sonuc = guvenlik.blok_coz(ip, hesap)
    except BaseException as e:
        h.hata_yaz(500, str(e))
        return
    if not sonuc.get("tamam"):
        h.hata_yaz(400, str(sonuc.get("hata") or "cozulemedi"))
        return
    h.json_yaz(sonuc)


# ---------------------------------------------------------------- #
# GUNLUK GORUNTULEME UCLARI                          FAZ18-IS10-GUNLUK #
#                                                                    #
# DORT kaynak (`mk_gunluk`): uygulama, app, sistem (journald), ag.   #
#                                                                    #
# ZAMAN SUZGECI ASIMETRISI — olculdu, gizlenmiyor:                   #
#   Uygulama gunluklerinde satirlarin %0'i tarih damgasi tasiyor     #
#   (12074 satirda 4). Uygulama `print()` ile yaziyor ve birim       #
#   `StandardOutput=append:` kullandigi icin journald damga          #
#   eklemiyor. Bu yuzden zaman araligi suzgeci YALNIZ `sistem`       #
#   kaynaginda etkin; her kaynak `zaman_suzulebilir` bayragi ile     #
#   yetenegini kendisi bildirir ve arayuz ona gore davranir.         #
#                                                                    #
# VERITABANI GUNLUGU KAPSAM DISI: PG dosyalari 0600/postgres.        #
# Okumak PG yeniden baslatmasi gerektirirdi; goruntuleme isi icin    #
# canli veritabani kesintiye ugratilmadi. Arayuz bunu YAZAR.         #
#                                                                    #
# Onbellek YOK: `journalctl -n 200 -o json` olculdu -> 75 ms.        #
# Gereksiz karmasiklik eklenmedi.                                    #
# ---------------------------------------------------------------- #
@yol("GET", r"/api/admin/gunluk/kaynaklar")
def _u_gunluk_kaynaklar(h, istek, oturum):
    try:
        h.json_yaz(gunluk.kaynaklar())
    except BaseException as e:
        # Gorunurluk ucu ASLA panelin tamamini dusurmemeli.
        h.json_yaz({"hata": str(e), "kaynaklar": [], "duzeyler": []}, 200)


@yol("GET", r"/api/admin/gunluk")
def _u_gunluk(h, istek, oturum):
    s = istek.sorgu
    try:
        h.json_yaz(gunluk.oku(
            kaynak=str(s.get("kaynak") or "uygulama"),
            en_cok=int(s.get("en_cok") or 200),
            ara=str(s.get("ara") or ""),
            duzey=str(s.get("duzey") or ""),
            birim=str(s.get("birim") or ""),
            saat=int(s.get("saat") or 0)))
    except BaseException as e:
        h.json_yaz({"hata": str(e), "kayitlar": [],
                    "okunabilir": False}, 200)


@yol("GET", r"/api/admin/denetim")
def _u_denetim(h, istek, oturum):
    h.json_yaz(api.denetim_liste(int(istek.sorgu.get("sayfa", 1)),
                                 int(istek.sorgu.get("boyut", 100))))


@yol("GET", r"/api/admin/surumler")
def _u_surumler(h, istek, oturum):
    h.json_yaz({"surumler": depo.liste(istek.sorgu.get("urun"),
                                       istek.sorgu.get("kanal")),
                "acik_anahtar": depo.acik_anahtar_b64(),
                "urunler": list(depo.URUNLER),
                "platformlar": list(depo.PLATFORMLAR),
                "kanallar": list(depo.KANALLAR)})


@yol("POST", r"/api/admin/surumler/yukle")
def _u_surum_yukle(h, istek, oturum):
    """Depoda **hazır bekleyen** bir dosyayı sürüm olarak yayımlar.

    Paket dosyaları büyük olduğu için tarayıcıdan yükleme yerine sunucuya
    (scp/rsync) konan dosya yolu verilir; sunucu dosyayı depoya alır,
    SHA-256 özetini hesaplar ve Ed25519 ile imzalar.
    """
    g = istek.govde or {}
    kaynak = str(g.get("kaynak_yol") or "").strip()
    if not kaynak:
        h.hata_yaz(400, "kaynak_yol zorunlu")
        return
    try:
        kayit = depo.paket_ekle(
            str(g.get("urun") or ""), str(g.get("surum") or ""), kaynak,
            platform=str(g.get("platform") or "ortak"),
            kanal=str(g.get("kanal") or "kararli"),
            paket_tur=str(g.get("paket_tur") or "guncelleme"),
            asgari_surum=(g.get("asgari_surum") or None),
            notlar=(g.get("notlar") or None),
            yonetici_id=oturum["yonetici_id"])
    except (ValueError, FileNotFoundError) as e:
        h.hata_yaz(400, str(e))
        return
    h.json_yaz({"tamam": True, "surum": kayit}, 201)


@yol("POST", r"/api/admin/surumler/(\d+)/devre_disi")
def _u_surum_devre_disi(h, istek, oturum, sid):
    if not depo.paket_devre_disi(int(sid), oturum["yonetici_id"]):
        h.hata_yaz(404, "Sürüm bulunamadı")
        return
    h.json_yaz({"tamam": True})


@yol("POST", r"/api/admin/surumler/(\d+)/etkinlestir")
def _u_surum_etkinlestir(h, istek, oturum, sid):
    if not depo.paket_etkinlestir(int(sid)):
        h.hata_yaz(404, "Sürüm bulunamadı")
        return
    h.json_yaz({"tamam": True})


@yol("GET", r"/api/genel/guncelleme", yetki="acik")
def _u_guncelleme_kontrol(h, istek, oturum):
    """Saha yazılımının açılışta çağırdığı güncelleme kontrolü.

    Kimlik istemez: paket zaten imzalı ve açık anahtar istemcide gömülü;
    kimlik zorunlu kılmak, sürüm kontrolünü çevrimdışı kurulumlarda
    kırılganlaştırırdı.
    """
    s = istek.sorgu
    urun = (s.get("urun") or "gcs").strip().lower()
    mevcut = (s.get("surum") or "0.0.0").strip()
    if urun not in depo.URUNLER:
        h.hata_yaz(400, f"geçersiz ürün: {urun}")
        return
    alan = (ayar_oku().get("alan_adi") or "").strip()
    taban = f"https://{alan}" if alan else ""
    h.json_yaz(depo.guncelleme_kontrol(
        urun, mevcut,
        platform=(s.get("platform") or "ortak").strip().lower(),
        kanal=(s.get("kanal") or "kararli").strip().lower(),
        paket_tur=(s.get("paket_tur") or "guncelleme").strip().lower(),
        taban_url=taban))


@yol("GET", r"/api/genel/katalog", yetki="acik")
def _u_genel_katalog(h, istek, oturum):
    """Tanıtım sayfasının indirme bölümünün okuduğu genel sürüm kataloğu.

    Yalnızca ETKİN ve dosyası gerçekten diskte bulunan kayıtlar döner:
    tanıtım sayfasında görünen her satır indirilebilir olmalıdır, aksi
    halde ziyaretçi 404 alır. Yönetim ucundan (``/api/admin/surumler``)
    ayrılmasının nedeni de budur; o uç devre dışı kayıtları da gösterir
    ve oturum ister.

    ``depo.GENEL_GIZLI_URUNLER`` listesindeki ürünler bu vitrinden
    çıkarılır. Şu an tek üye ``gcs``: komuta kontrol yazılımı merkezde
    ``/app/`` altında sunulduğu için sahaya indirilecek bir paketi
    yoktur; sahaya yalnızca köprü kurulur. Kayıt depoda etkin kaldığı
    için doğrudan indirme yolu ve güncelleme ucu çalışmaya devam eder
    (kendi sunucusunu işleten kurumlar bu yolu kullanır).
    """
    urun = (istek.sorgu.get("urun") or "").strip().lower() or None
    if urun and urun not in depo.URUNLER:
        h.hata_yaz(400, f"geçersiz ürün: {urun}")
        return
    gizli = set(getattr(depo, "GENEL_GIZLI_URUNLER", ()))
    if urun and urun in gizli:
        # Açıkça sorulan ürün gizliyse boş katalog döner; 404 değil,
        # çünkü ürün geçersiz değil, yalnızca vitrinde yok.
        h.json_yaz({"urunler": [], "kayitlar": []})
        return
    kayitlar = [k for k in depo.liste(urun, "kararli", etkin_yalniz=True)
                if k.get("dosya_var") and k.get("urun") not in gizli]
    # imza/sha alanları katalogda gereksiz yer kaplar; bütünlük
    # doğrulaması istemcinin güncelleme ucundan aldığı veriyle yapılır.
    for k in kayitlar:
        k.pop("imza", None)
    h.json_yaz({"urunler": sorted({k["urun"] for k in kayitlar}),
                "kayitlar": kayitlar})


@yol("GET", r"/api/genel/imza_anahtari", yetki="acik")
def _u_imza_anahtari(h, istek, oturum):
    h.json_yaz({"algoritma": "Ed25519",
                "acik_anahtar": depo.acik_anahtar_b64()})


# ==========================================================================
# MÜŞTERİLER
# ==========================================================================
@yol("GET", r"/api/admin/firmalar")
def _u_firmalar(h, istek, oturum):
    h.json_yaz(api.firma_liste(istek.sorgu.get("arama"),
                               istek.sorgu.get("durum"),
                               int(istek.sorgu.get("sayfa", 1)),
                               int(istek.sorgu.get("boyut", 50))))


@yol("POST", r"/api/admin/firmalar")
def _u_firma_ekle(h, istek, oturum):
    fid, hata = api.firma_ekle(istek.govde)
    if hata:
        h.hata_yaz(400, hata)
        return
    kimlik.denetim(oturum["yonetici_id"], "firma_ekle", "firma", str(fid),
                   {"unvan": istek.govde.get("unvan")}, istek.ip)
    h.json_yaz({"tamam": True, "firma_id": fid}, 201)


@yol("GET", r"/api/admin/firmalar/(\d+)")
def _u_firma_getir(h, istek, oturum, fid):
    f = api.firma_getir(int(fid))
    if not f:
        h.hata_yaz(404, "Firma bulunamadı")
        return
    h.json_yaz(f)


@yol("PUT", r"/api/admin/firmalar/(\d+)")
def _u_firma_guncelle(h, istek, oturum, fid):
    tamam, hata = api.firma_guncelle(int(fid), istek.govde)
    if not tamam:
        h.hata_yaz(400, hata or "Güncellenemedi")
        return
    kimlik.denetim(oturum["yonetici_id"], "firma_guncelle", "firma", fid,
                   {"alanlar": sorted(istek.govde.keys())}, istek.ip)
    h.json_yaz({"tamam": True})


@yol("DELETE", r"/api/admin/firmalar/(\d+)")
def _u_firma_sil(h, istek, oturum, fid):
    if oturum["rol"] != "sistem_yonetici":
        h.hata_yaz(403, "Bu işlem için sistem yöneticisi olmalısınız")
        return
    tamam, hata = api.firma_sil(int(fid))
    if not tamam:
        h.hata_yaz(404, hata or "Silinemedi")
        return
    kimlik.denetim(oturum["yonetici_id"], "firma_sil", "firma", fid, {}, istek.ip)
    h.json_yaz({"tamam": True})


# ==========================================================================
# KULLANICILAR
# ==========================================================================
@yol("GET", r"/api/admin/kullanicilar")
def _u_kullanicilar(h, istek, oturum):
    fid = istek.sorgu.get("firma_id")
    h.json_yaz(api.kullanici_liste(int(fid) if fid else None,
                                   istek.sorgu.get("arama"),
                                   istek.sorgu.get("rol"),
                                   int(istek.sorgu.get("sayfa", 1)),
                                   int(istek.sorgu.get("boyut", 50))))


@yol("POST", r"/api/admin/kullanicilar")
def _u_kullanici_ekle(h, istek, oturum):
    kid, hata = api.kullanici_ekle(istek.govde)
    if hata:
        h.hata_yaz(400, hata)
        return
    kimlik.denetim(oturum["yonetici_id"], "kullanici_ekle", "kullanici",
                   str(kid), {"eposta": istek.govde.get("eposta")}, istek.ip)
    h.json_yaz({"tamam": True, "kullanici_id": kid}, 201)


@yol("GET", r"/api/admin/kullanicilar/(\d+)")
def _u_kullanici_getir(h, istek, oturum, kid):
    k = api.kullanici_getir(int(kid))
    if not k:
        h.hata_yaz(404, "Kullanıcı bulunamadı")
        return
    h.json_yaz(k)


@yol("PUT", r"/api/admin/kullanicilar/(\d+)")
def _u_kullanici_guncelle(h, istek, oturum, kid):
    tamam, hata = api.kullanici_guncelle(int(kid), istek.govde)
    if not tamam:
        h.hata_yaz(400, hata or "Güncellenemedi")
        return
    kimlik.denetim(oturum["yonetici_id"], "kullanici_guncelle", "kullanici",
                   kid, {"alanlar": sorted(istek.govde.keys())}, istek.ip)
    h.json_yaz({"tamam": True})


@yol("DELETE", r"/api/admin/kullanicilar/(\d+)")
def _u_kullanici_sil(h, istek, oturum, kid):
    tamam, hata = api.kullanici_sil(int(kid))
    if not tamam:
        h.hata_yaz(404, hata or "Silinemedi")
        return
    kimlik.denetim(oturum["yonetici_id"], "kullanici_sil", "kullanici", kid,
                   {}, istek.ip)
    h.json_yaz({"tamam": True})


# ==========================================================================
# UÇUŞ KAYITLARI
# ==========================================================================
@yol("GET", r"/api/admin/ucuslar")
def _u_ucuslar(h, istek, oturum):
    s = istek.sorgu
    h.json_yaz(api.ucus_liste(
        int(s["firma_id"]) if s.get("firma_id") else None,
        int(s["kullanici_id"]) if s.get("kullanici_id") else None,
        int(s["dron_id"]) if s.get("dron_id") else None,
        s.get("baslangic"), s.get("bitis"),
        int(s.get("sayfa", 1)), int(s.get("boyut", 50))))


@yol("GET", r"/api/admin/ucuslar/(\d+)")
def _u_ucus_getir(h, istek, oturum, uid):
    u = api.ucus_getir(int(uid))
    if not u:
        h.hata_yaz(404, "Uçuş kaydı bulunamadı")
        return
    h.json_yaz(u)


@yol("GET", r"/api/admin/ucuslar/(\d+)/telemetri")
def _u_ucus_telemetri(h, istek, oturum, uid):
    h.json_yaz({"kayitlar": api.ucus_telemetri(
        int(uid), int(istek.sorgu.get("seyreltme", 1)))})


# ==========================================================================
# VİDEO KAYITLARI
# ==========================================================================
@yol("GET", r"/api/admin/videolar")
def _u_videolar(h, istek, oturum):
    s = istek.sorgu
    h.json_yaz(api.video_liste(
        int(s["firma_id"]) if s.get("firma_id") else None,
        int(s["kullanici_id"]) if s.get("kullanici_id") else None,
        int(s["ucus_id"]) if s.get("ucus_id") else None,
        int(s.get("sayfa", 1)), int(s.get("boyut", 50))))


@yol("GET", r"/api/admin/videolar/(\d+)")
def _u_video_getir(h, istek, oturum, vid):
    v = api.video_getir(int(vid))
    if not v:
        h.hata_yaz(404, "Video kaydı bulunamadı")
        return
    h.json_yaz(v)


@yol("GET", r"/api/admin/videolar/(\d+)/akis")
def _u_video_akis(h, istek, oturum, vid):
    """Video oynatma. Merkezdeyse dosya, yereldeyse köprüden parça."""
    v = api.video_getir(int(vid))
    if not v:
        h.hata_yaz(404, "Video kaydı bulunamadı")
        return
    if v["depo_yeri"] == "merkez" and v.get("dosya_yol"):
        hedef = os.path.normpath(os.path.join(VERI_KOKU, "video",
                                              v["dosya_yol"].lstrip("/")))
        if not os.path.isfile(hedef):
            h.hata_yaz(404, "Video dosyası merkezde bulunamadı")
            return
        istek.yol = "/video/" + v["dosya_yol"].lstrip("/")
        h._dosya_sun(istek)
        return
    if not v.get("ornek_id"):
        h.hata_yaz(409, "Video yerel sunucuda ve sunucu bilinmiyor")
        return
    veri, hata = kopruye_sor(int(v["ornek_id"]), "video_parca",
                             {"yerel_yol": v.get("yerel_yol"),
                              "video_uid": v.get("video_uid")}, 30.0)
    if hata:
        h.hata_yaz(503, f"Yerel sunucudan alınamadı: {hata}")
        return
    import base64
    govde = base64.b64decode((veri or {}).get("b64") or "")
    h._yaz(200, govde, (veri or {}).get("tur") or "video/mp4")


# ==========================================================================
# SUNUCU ÖRNEKLERİ
# ==========================================================================
@yol("GET", r"/api/admin/sunucular")
def _u_sunucular(h, istek, oturum):
    fid = istek.sorgu.get("firma_id")
    h.json_yaz({"kayitlar": api.sunucu_liste(int(fid) if fid else None)})


@yol("POST", r"/api/admin/sunucular")
def _u_sunucu_ekle(h, istek, oturum):
    try:
        fid = int(istek.govde.get("firma_id") or 0)
    except (TypeError, ValueError):
        h.hata_yaz(400, "Geçersiz firma")
        return
    veri, hata = api.sunucu_ekle(fid, istek.govde.get("ad") or "",
                                 istek.govde.get("aciklama"))
    if hata:
        h.hata_yaz(400, hata)
        return
    kimlik.denetim(oturum["yonetici_id"], "sunucu_ekle", "sunucu",
                   str((veri or {}).get("ornek_id")),
                   {"ad": istek.govde.get("ad")}, istek.ip)
    h.json_yaz({"tamam": True, "sunucu": veri}, 201)


@yol("DELETE", r"/api/admin/sunucular/(\d+)")
def _u_sunucu_sil(h, istek, oturum, oid):
    tamam, hata = api.sunucu_sil(int(oid))
    if not tamam:
        h.hata_yaz(404, hata or "Silinemedi")
        return
    kimlik.denetim(oturum["yonetici_id"], "sunucu_sil", "sunucu", oid, {},
                   istek.ip)
    h.json_yaz({"tamam": True})


@yol("GET", r"/api/admin/sunucular/(\d+)/sor/([a-z_]+)")
def _u_sunucu_sor(h, istek, oturum, oid, eylem):
    """Canlı köprüye sorgu (dron listesi, port listesi, servis durumu)."""
    veri, hata = kopruye_sor(int(oid), eylem, dict(istek.sorgu))
    if hata:
        h.hata_yaz(503, hata)
        return
    h.json_yaz({"tamam": True, "veri": veri})


# ==========================================================================
# İSTEMCİ (firma kullanıcısı) UÇ NOKTALARI
# ==========================================================================
@yol("POST", r"/api/istemci/giris", yetki="acik")
def _u_istemci_giris(h, istek, oturum):
    k, hata = kimlik.kullanici_dogrula(
        (istek.govde.get("eposta") or "").strip(),
        istek.govde.get("sifre") or "")
    if hata:
        h.json_yaz({"hata": hata}, 401)
        return
    h.json_yaz({"tamam": True, "kullanici": k})


@yol("POST", r"/api/istemci/acik_sunucular", yetki="acik")
def _u_acik_sunucular(h, istek, oturum):
    """Bağlantı yöneticisi: kullanıcının firmasına ait **açık** sunucular.

    Kimlik doğrulaması istek gövdesindeki kullanıcı bilgisiyle yapılır;
    böylece saha GCS'i merkez oturumu tutmak zorunda kalmaz.
    """
    k, hata = kimlik.kullanici_dogrula(
        (istek.govde.get("eposta") or "").strip(),
        istek.govde.get("sifre") or "")
    if hata:
        h.json_yaz({"hata": hata}, 401)
        return
    h.json_yaz({"tamam": True, "firma_id": k["firma_id"],
                "sunucular": api.acik_sunucular(int(k["firma_id"]))})


@yol("POST", r"/api/istemci/sunucu_kayit", yetki="acik")
def _u_istemci_sunucu_kayit(h, istek, oturum):
    """GCS kendini merkeze **sunucu örneği** olarak kaydeder.

    Köprü ajanının ilk adımıdır: `kurulum_uid` ve `gizli` yalnızca bu
    yanıtta döner; istemci bunları `veri/kopru.json` içine yazar. Aynı
    makine ve aynı ürün için ikinci kez kayıt istenirse yeni örnek üretilmez;
    409 ile var olan kayıt bildirilir. `yenile: true` gönderilirse yalnız aynı
    ürün kaydının gizlisi tazelenir. Böylece aynı bilgisayardaki Dron Köprüsü
    (`kopru`) ile Görüntü Köprüsü (`video`) birbirinin kimliğini ezemez.
    """
    k, hata = kimlik.kullanici_dogrula(
        (istek.govde.get("eposta") or "").strip(),
        istek.govde.get("sifre") or "")
    if hata:
        h.json_yaz({"hata": hata}, 401)
        return
    g = istek.govde or {}
    makine = (g.get("makine_adi") or "").strip()
    ad = (g.get("ad") or makine or "").strip()
    if not ad:
        h.json_yaz({"hata": "Sunucu adı zorunlu"}, 400)
        return
    firma_id = int(k["firma_id"])
    platform = (g.get("platform") or "").strip() or None
    surum = (g.get("surum") or "").strip() or None
    aciklama = (g.get("aciklama") or "").strip() or None
    yenile = bool(g.get("yenile"))
    eski_uid = (g.get("kurulum_uid") or "").strip()
    urun = (g.get("urun") or "kopru").strip().lower()
    if urun not in ("kopru", "video", "radar", "gccdual", "dji"):
        h.json_yaz({"hata": "Geçersiz sunucu ürünü"}, 400)
        return

    # İş 109: Kurulum kimliği ve makine adı yalnız AYNI ürün içinde eşleşir.
    # Eski istemciler `urun` göndermez; geriye uyumlu varsayılan `kopru`dur.
    mevcut = None
    urun_kurtarma = False
    if eski_uid:
        mevcut = db.tek(
            "SELECT ornek_id, ad FROM sunucu_ornekleri "
            "WHERE kurulum_uid = %s AND firma_id = %s "
            "AND COALESCE(yetenekler->>'urun', 'kopru') = %s",
            (eski_uid, firma_id, urun))
    if not mevcut and makine:
        mevcut = db.tek(
            "SELECT ornek_id, ad FROM sunucu_ornekleri "
            "WHERE firma_id = %s AND makine_adi = %s AND durum <> 'iptal' "
            "AND COALESCE(yetenekler->>'urun', 'kopru') = %s "
            "ORDER BY ornek_id LIMIT 1", (firma_id, makine, urun))

    # Yerelde başka ürünün kimliği kalmışsa yalnız firma içinde TEK bir etkin
    # aynı-ürün kaydı bulunduğunda onu kurtar. Birden fazla adayda tahmin etme.
    if not mevcut and yenile and eski_uid:
        if str(k.get("rol") or "") != "firma_yonetici":
            h.json_yaz({"hata": "Kurulum kimliği onarımı için firma "
                                "yöneticisi yetkisi gerekir",
                        "urun": urun}, 403)
            return
        adaylar = db.tumu(
            "SELECT ornek_id, ad FROM sunucu_ornekleri "
            "WHERE firma_id = %s AND durum <> 'iptal' "
            "AND COALESCE(yetenekler->>'urun', 'kopru') = %s "
            "ORDER BY ornek_id LIMIT 2", (firma_id, urun))
        if len(adaylar) == 1:
            mevcut = adaylar[0]
            urun_kurtarma = True
            ad = (mevcut.get("ad") or ad).strip()
        elif len(adaylar) > 1:
            h.json_yaz({"hata": "Bu firma için birden fazla ürün kaydı var; "
                                "kurulum otomatik eşlenemedi",
                        "urun": urun, "kayitli": True}, 409)
            return

    if mevcut and not yenile:
        h.json_yaz({"hata": "Bu makine zaten kayıtlı", "kayitli": True,
                    "ornek_id": int(mevcut["ornek_id"]),
                    "ad": mevcut["ad"]}, 409)
        return

    if mevcut:
        import secrets as _s
        yeni_uid = role.kurulum_uid_uret()
        gizli = _s.token_urlsafe(32)
        db.calistir(
            "UPDATE sunucu_ornekleri SET ad = %s, aciklama = %s, "
            "platform = %s, makine_adi = %s, surum = %s, kurulum_uid = %s, "
            "gizli_ozet = %s, durum = 'etkin', guncel_ts = now(), "
            "yetenekler = COALESCE(yetenekler, '{}'::jsonb) || "
            "jsonb_build_object('urun', %s, 'surum', %s) "
            "WHERE ornek_id = %s",
            (ad, aciklama, platform, makine or None, surum, yeni_uid,
             role.gizli_ozetle(gizli), urun, surum,
             int(mevcut["ornek_id"])))
        sonuc = {"ornek_id": int(mevcut["ornek_id"]), "kurulum_uid": yeni_uid,
                 "gizli": gizli, "ad": ad,
                 "merkez_adres": ayar_oku().get(
                     "kopru_adres", "wss://goktungu.com/kopru")}
    else:
        sonuc, hata = api.sunucu_ekle(firma_id, ad, aciklama=aciklama)
        if hata:
            h.json_yaz({"hata": hata}, 400)
            return
        db.calistir(
            "UPDATE sunucu_ornekleri SET platform = %s, makine_adi = %s, "
            "surum = %s, guncel_ts = now(), "
            "yetenekler = COALESCE(yetenekler, '{}'::jsonb) || "
            "jsonb_build_object('urun', %s, 'surum', %s) "
            "WHERE ornek_id = %s",
            (platform, makine or None, surum, urun, surum,
             int(sonuc["ornek_id"])))

    sonuc = dict(sonuc)
    sonuc["tamam"] = True
    sonuc["urun"] = urun
    sonuc["kimlik_onarildi"] = bool(urun_kurtarma)
    sonuc["firma_id"] = firma_id
    sonuc["firma_kisa_ad"] = k.get("firma_kisa_ad")
    h.json_yaz(sonuc)


# ==========================================================================
# FİRMA PANELİ (/company/) UÇ NOKTALARI
# ==========================================================================
# Bu bolumdeki her uc `yetki="firma"` ile korunur ve YALNIZ oturum
# sahibinin firmasina ait veriyi dondurur. Firma kimligi ISTEK GOVDESINDEN
# DEGIL, oturumdan okunur; aksi halde bir musteri baska bir musterinin
# firma_id degerini gonderip verisini gorebilirdi. Bu ayrim panelin
# guvenlik temelidir ve degistirilmemelidir.


def _firma_id(oturum) -> int:
    return int(oturum["firma_id"])


def _pilot_kisitla(oturum, kid):
    """Pilot rolu YALNIZ kendi kayitlarini gorur; firma yoneticisi ve
    gozlemci firmanin tumunu gorur."""
    if oturum.get("rol") == "pilot":
        return int(oturum["kullanici_id"])
    return int(kid) if kid else None


@yol("GET", r"/api/genel/bakim", yetki="acik")
def _u_genel_bakim(h, istek, oturum):
    """Bakim kipi durumu. FAZ18-IS24-BAKIM-KIPI

    Arayuz bu ucu SAYFA YUKLENIRKEN cagirir ve kayit formunun
    ustune bilgi bandi koyar. Kullanicinin formu doldurup
    gonderdikten sonra 503 gormesi kotu bir deneyimdir; kip
    acikken bunu bastan bildirmek gerekir.

    Uc `yetki="acik"` olmak ZORUNDA: bakim kipini gormesi
    gereken kitle tam olarak henuz oturumu olmayan kitledir.
    """
    try:
        h.json_yaz(bakim_kipi.durum())
    except BaseException:
        h.json_yaz({"acik": False, "mesaj": "", "bitis": None})

@yol("POST", r"/api/bireysel/kayit", yetki="acik")
def _u_bireysel_kayit(h, istek, oturum):
    """Bireysel kullanıcı kaydı: kişi + tek kullanıcı, TEK işlemde.

    Bireysel kullanıcı kurumsal yapıdan farklıdır:
      * Kurum unvanı, vergi no, adres SORULMAZ.
      * `firmalar` kaydı yine açılır (`tur='bireysel'`) çünkü
        `kullanicilar.firma_id` NOT NULL ve tüm veri izolasyonu bu
        ilişki üzerinden yürür. Kullanıcı bu kaydı hiç görmez.
      * Radar ve GCCDual ZORUNLU kapalıdır; veritabanı CHECK kısıtı
        (`firmalar_bireysel_modul_check`) bunu ayrıca zorlar.
      * AI modülü kapalı açılır; ücretli olarak sonradan etkinleşir.
      * Kayıt sonrası OTURUM AÇILMAZ — e-posta doğrulaması zorunludur.
    """
    g = istek.govde or {}
    eposta = (g.get("eposta") or "").strip().lower()
    sifre = g.get("sifre") or ""
    sifre2 = g.get("sifre2") or ""
    ad = (g.get("ad") or "").strip()
    soyad = (g.get("soyad") or "").strip()
    telefon = (g.get("telefon") or "").strip()

    if not ad:
        h.json_yaz({"hata": "Ad zorunlu"}, 400)
        return
    if len(ad) < 2:
        h.json_yaz({"hata": "Ad en az 2 karakter olmali"}, 400)
        return
    if not soyad:
        h.json_yaz({"hata": "Soyad zorunlu"}, 400)
        return
    if "@" not in eposta or "." not in eposta.split("@")[-1]:
        h.json_yaz({"hata": "Gecerli bir e-posta adresi girin"}, 400)
        return
    if sifre2 and sifre != sifre2:
        h.json_yaz({"hata": "Sifreler eslesmiyor"}, 400)
        return
    # Şifre gücü kimlik katmanında da denetlenir; burada ÖNCE denetlemek
    # boşuna firma kaydı oluşmasını önler.
    sg = kimlik.sifre_gucu(sifre)
    if sg:
        h.json_yaz({"hata": sg}, 400)
        return
    # E-posta tekilliği firma oluşturmadan ÖNCE denetlenir; aksi halde
    # sahipsiz firma kaydı kalır.
    if db.tek("SELECT 1 FROM kullanicilar WHERE eposta = %s", (eposta,)):
        h.json_yaz({"hata": "Bu e-posta zaten kayitli"}, 409)
        return

    tam_ad = (ad + " " + soyad).strip()
    fid, hata = api.firma_ekle({
        "unvan": tam_ad,          # firmalar.unvan NOT NULL
        "kisa_ad": ad[:40],
        "eposta": eposta,
        "telefon": telefon,
        "ulke": (g.get("ulke") or "TR").strip(),
        "durum": "etkin",
        "abonelik": "bireysel",
        "tur": "bireysel",
        # Bireysel hesap ekip yönetmez: tek kullanıcı, tek koltuk.
        "maks_kullanici": 1,
        "maks_sunucu": 1,
        "pilot_koltuk": 1,
        # Radar, GCCDual ve M50 bireysel hesapta KULLANILAMAZ.
        # M50 yalnız açık VEILOX donanım tahsisiyle açılır; yeni kayıt
        # güvenli olarak kapalı başlar.
        "radar_etkin": False,
        "gccdual_etkin": False,
        "m50_etkin": False,
        # AI ücretli modül; kapalı açılır, sonradan etkinleşir.
        "ai_etkin": False,
    })
    if hata or not fid:
        h.json_yaz({"hata": hata or "Hesap olusturulamadi"}, 400)
        return

    # Rol ZORUNLU `firma_yonetici`: bireysel kullanıcı kendi hesabının
    # yöneticisidir. `pilot` verilse hesap ayarlarına erişemez.
    kid, hata = api.kullanici_ekle({
        "firma_id": fid, "eposta": eposta, "sifre": sifre,
        "ad": ad, "soyad": soyad, "rol": "firma_yonetici",
        "telefon": telefon,
    })
    if hata or not kid:
        # Kullanıcı oluşmadıysa firma da GERİ ALINIR; aksi halde
        # erişilemeyen bir kayıt kalır ve e-posta bloke olur.
        api.firma_sil(int(fid))
        h.json_yaz({"hata": hata or "Hesap olusturulamadi"}, 400)
        return

    kimlik.denetim(None, "bireysel_kayit", "firma", str(fid),
                   {"ad": tam_ad, "eposta": eposta}, istek.ip)

    # OTURUM AÇILMAZ: e-posta doğrulaması zorunlu. Doğrulama bağlantısı
    # ayrı bir adımda gönderilir (bkz. mk_eposta).
    h.json_yaz({"tamam": True, "firma_id": int(fid),
                "kullanici_id": int(kid), "giris": False,
                "dogrulama_gerekli": True,
                "eposta": eposta}, 201)

@yol("POST", r"/api/firma/kayit", yetki="acik")
def _u_firma_kayit(h, istek, oturum):
    """Kurumsal kayit: firma + ilk yonetici kullanici, TEK islemde.

    NEDEN TEK ISLEM: firma ile yonetici ayri isteklerde olusturulsa,
    ikinci istek basarisiz oldugunda sahipsiz firma kaydi kalirdi ve
    ayni vergi no ile yeniden kayit engellenirdi.
    """
    g = istek.govde or {}
    unvan = (g.get("unvan") or "").strip()
    eposta = (g.get("eposta") or "").strip()
    sifre = g.get("sifre") or ""
    sifre2 = g.get("sifre2") or ""
    ad = (g.get("ad") or "").strip()
    soyad = (g.get("soyad") or "").strip()

    if not unvan:
        h.json_yaz({"hata": "Kurum unvani zorunlu"}, 400)
        return
    if len(unvan) < 3:
        h.json_yaz({"hata": "Kurum unvani en az 3 karakter olmali"}, 400)
        return
    if "@" not in eposta or "." not in eposta.split("@")[-1]:
        h.json_yaz({"hata": "Gecerli bir e-posta adresi girin"}, 400)
        return
    if not ad:
        h.json_yaz({"hata": "Yetkili adi zorunlu"}, 400)
        return
    if sifre2 and sifre != sifre2:
        h.json_yaz({"hata": "Sifreler eslesmiyor"}, 400)
        return
    # Sifre gucu kimlik katmaninda da denetlenir; burada ONCE denetlemek
    # firma kaydinin bosuna olusmasini onler.
    sg = kimlik.sifre_gucu(sifre)
    if sg:
        h.json_yaz({"hata": sg}, 400)
        return
    # E-posta tekilligi firma olusturmadan ONCE denetlenir; aksi halde
    # sahipsiz firma kaydi kalir.
    if db.tek("SELECT 1 FROM kullanicilar WHERE eposta = %s", (eposta,)):
        h.json_yaz({"hata": "Bu e-posta zaten kayitli"}, 409)
        return

    fid, hata = api.firma_ekle({
        "unvan": unvan,
        "kisa_ad": (g.get("kisa_ad") or "").strip() or unvan[:40],
        "vergi_no": (g.get("vergi_no") or "").strip(),
        "vergi_dairesi": (g.get("vergi_dairesi") or "").strip(),
        "adres": (g.get("adres") or "").strip(),
        "telefon": (g.get("telefon") or "").strip(),
        "eposta": eposta,
        "web": (g.get("web") or "").strip(),
        "ulke": (g.get("ulke") or "TR").strip(),
        "durum": "etkin",
        "abonelik": "deneme",
    })
    if hata or not fid:
        h.json_yaz({"hata": hata or "Kurum olusturulamadi"}, 400)
        return

    kid, hata = api.kullanici_ekle({
        "firma_id": fid, "eposta": eposta, "sifre": sifre,
        "ad": ad, "soyad": soyad, "rol": "firma_yonetici",
        "telefon": (g.get("telefon") or "").strip(),
    })
    if hata or not kid:
        # Yonetici olusmadiysa firma da GERI ALINIR; aksi halde
        # erisilemeyen bir kurum kaydi kalir ve vergi no bloke olur.
        api.firma_sil(int(fid))
        h.json_yaz({"hata": hata or "Yetkili hesabi olusturulamadi"}, 400)
        return

    # Kendi kendine kayitta yonetici_id YOKTUR (None); denetim izinde
    # eylemi kimin yaptigi e-posta ile taninir.
    # v2.4.53 Faz 4: kurum logosu. Logo BASARISIZ olsa bile kayit
    # geri alinmaz — kurum olusmustur ve logo sonradan Kurum Bilgileri
    # ekranindan yuklenebilir. Kullanici uyarilir.
    logo_uyari = ""
    try:
        _lg, _lh = logo_yaz(int(fid), g.get("logo"))
        if _lh:
            logo_uyari = _lh
    except Exception as _le:
        logo_uyari = "Logo kaydedilemedi: %s" % _le

    kimlik.denetim(None, "firma_kayit", "firma", str(fid),
                   {"unvan": unvan, "eposta": eposta}, istek.ip)

    # Kayit sonrasi oturum acilir; kullanici tekrar sifre girmez.
    veri, hata = kimlik.kullanici_giris(
        eposta, sifre, istek.ip, istek.h.headers.get("User-Agent"))
    if hata or not veri:
        # Kayit BASARILI, yalniz otomatik giris olmadi; kullanici
        # giris ekranina yonlendirilir.
        h.json_yaz({"tamam": True, "firma_id": int(fid),
                    "kullanici_id": int(kid), "giris": False,
                    "logo_uyari": logo_uyari})
        return
    # IS9B-CEREZ-ALANI: `Host` gecirilir; cerez kok alan adina baglanir.
    kurabiye = kimlik.kurabiye_yaz("goktungu_firma", veri["jeton"],
                                   istek.h.headers.get("Host"))
    h.json_yaz({"tamam": True, "firma_id": int(fid),
                "kullanici_id": int(kid), "giris": True,
                "kullanici": veri, "logo_uyari": logo_uyari},
               200, {"Set-Cookie": kurabiye})


# ==========================================================================
# E-POSTA DOGRULAMA  (v2.5.1)
# ==========================================================================
#
# TASARIM: dogrulama bagi 43 karakter urlsafe jeton. Veritabaninda
# YALNIZ SHA-256 ozeti durur (mk_eposta.kod_uret); duz kod yalniz
# e-postada gecer. Bu yuzden "kodu tekrar goster" ucu YOKTUR - sunucu
# kodu bilmez, yalnizca yenisini uretebilir.



# ============================================================
#  DESTEK (TICKET) SISTEMI
# ============================================================

DESTEK_MODULLER = (
    "app", "kopru", "merkez", "radar", "gccdual", "m50", "dji", "ai", "video",
    "kurumsal_panel", "yonetim_paneli", "odeme", "kurulum", "diger",
)
DESTEK_MODUL_AD = (
    ("app", "GCS Uygulamasi"), ("kopru", "Kopru Yazilimi"),
    ("merkez", "Merkez Uygulama"), ("radar", "Radar Modulu"),
    ("m50", "M50 Elektro-Optik Modulu"),
    ("gccdual", "Yer Kontrol Istasyonu Dual"),
    ("dji", "DJI Koprusu (Android)"), ("ai", "AI Sunucusu"),
    ("video", "Video Sunucusu"), ("kurumsal_panel", "Kurumsal Panel"),
    ("yonetim_paneli", "Yonetim Paneli"), ("odeme", "Odeme / Abonelik"),
    ("kurulum", "Kurulum / Sihirbaz"), ("diger", "Diger"),
)
DESTEK_ONCELIK = ("dusuk", "normal", "yuksek", "kritik")
DESTEK_DURUM = ("yeni", "islemde", "yanit_bekliyor", "cozuldu", "kapandi")

DESTEK_EK_MAKS = 8 * 1024 * 1024
DESTEK_EK_MAKS_ADET = 5
DESTEK_EK_MIME = {
    "image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
    "image/webp": ".webp", "application/pdf": ".pdf",
    "text/plain": ".txt", "application/json": ".json",
    "application/zip": ".zip", "application/gzip": ".gz",
    "text/csv": ".csv", "application/x-tar": ".tar",
}
DESTEK_EK_KOK = "/opt/goktungu/merkez/veri/destek_ekleri"


def _destek_kul_ad(oturum):
    """Firma oturumunda `ad` ve `soyad` AYRI alanlardir (olculdu);
    `oturum.get("ad")` tek basina soyadi dusururdu.  Yonetici
    oturumunda ise tek bir `ad_soyad` alani var -- ikisini de
    karsilayacak sekilde birlestirilir."""
    t = (oturum.get("ad_soyad") or "").strip()
    if t:
        return t
    p = " ".join(x for x in ((oturum.get("ad") or "").strip(),
                             (oturum.get("soyad") or "").strip()) if x)
    return p or (oturum.get("eposta") or "Kullanici")


def _destek_ticket_no():
    """GT-YYYY-NNNNN.  Diziden uretilir; iki es zamanli talep ayni
    numarayi ALMAZ (sayim sorgusu kullanilsaydi yaris kosulu olurdu)."""
    n = db.deger("SELECT nextval('destek_talepleri_ticket_id_seq')")
    return "GT-%s-%05d" % (time.strftime("%Y"), int(n))


def _destek_ek_yaz(ticket_id, mesaj_id, ekler):
    """base64 ekleri diske yazar.  Doner: (yazilan_adet, hata_metni)."""
    if not ekler:
        return 0, None
    if not isinstance(ekler, list):
        return 0, "Ekler liste olmali"
    if len(ekler) > DESTEK_EK_MAKS_ADET:
        return 0, "En fazla %d dosya eklenebilir" % DESTEK_EK_MAKS_ADET

    kok = os.path.join(DESTEK_EK_KOK, str(int(ticket_id)))
    os.makedirs(kok, exist_ok=True)
    yazilan = 0

    for e in ekler:
        if not isinstance(e, dict):
            return yazilan, "Ek bicimi gecersiz"
        mime = (e.get("mime") or "").strip().lower()
        ad = (e.get("ad") or "").strip()
        if mime not in DESTEK_EK_MIME:
            return yazilan, "Desteklenmeyen dosya turu: %s" % (mime or "?")
        if not ad:
            return yazilan, "Dosya adi bos"
        try:
            ham = base64.b64decode(e.get("veri") or "", validate=True)
        except Exception:
            return yazilan, "Ek base64 cozulemedi: %s" % ad
        if not ham:
            return yazilan, "Ek bos: %s" % ad
        if len(ham) > DESTEK_EK_MAKS:
            return yazilan, "Dosya cok buyuk (maks %d MB): %s" % (
                DESTEK_EK_MAKS // (1024 * 1024), ad)

        # Disk adi ozgun addan DEGIL sha256'dan: yol gecisi kapanir.
        sha = hashlib.sha256(ham).hexdigest()
        disk_yol = os.path.join(kok, "%s%s" % (sha[:32], DESTEK_EK_MIME[mime]))
        with open(disk_yol, "wb") as f:
            f.write(ham)
        os.chmod(disk_yol, 0o640)

        db.calistir(
            "INSERT INTO destek_ekleri "
            "(ticket_id, mesaj_id, dosya_ad, mime, boyut, disk_yol, sha256) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (ticket_id, mesaj_id, ad[:255], mime, len(ham), disk_yol, sha))
        yazilan += 1

    return yazilan, None


# ---------- KULLANICI TARAFI ----------

@yol("GET", r"/api/destek/moduller", yetki="acik")
def _u_destek_moduller(h, istek, oturum):
    """Modul/oncelik listesi.  Arayuz sabit kodlamasin: yeni modul
    eklendiginde tek yerden yayilir."""
    h.json_yaz({
        "moduller": [{"anahtar": a, "ad": b} for a, b in DESTEK_MODUL_AD],
        "oncelikler": [
            {"anahtar": "dusuk", "ad": "Dusuk"},
            {"anahtar": "normal", "ad": "Normal"},
            {"anahtar": "yuksek", "ad": "Yuksek"},
            {"anahtar": "kritik", "ad": "Kritik"},
        ],
        "ek_maks_mb": DESTEK_EK_MAKS // (1024 * 1024),
        "ek_maks_adet": DESTEK_EK_MAKS_ADET,
        "ek_mime": sorted(DESTEK_EK_MIME.keys()),
    }, 200)


@yol("POST", r"/api/destek/talepler", yetki="firma")
def _u_destek_talep_ac(h, istek, oturum):
    g = istek.govde or {}
    modul = (g.get("modul") or "").strip()
    konu = (g.get("konu") or "").strip()
    aciklama = (g.get("aciklama") or "").strip()
    oncelik = (g.get("oncelik") or "normal").strip()
    ekler = g.get("ekler") or []

    if modul not in DESTEK_MODULLER:
        h.json_yaz({"hata": "Gecersiz modul"}, 400)
        return
    if len(konu) < 3:
        h.json_yaz({"hata": "Konu en az 3 karakter olmali"}, 400)
        return
    if len(konu) > 200:
        h.json_yaz({"hata": "Konu en fazla 200 karakter olmali"}, 400)
        return
    if len(aciklama) < 10:
        h.json_yaz({"hata": "Aciklama en az 10 karakter olmali"}, 400)
        return
    if oncelik not in DESTEK_ONCELIK:
        h.json_yaz({"hata": "Gecersiz oncelik"}, 400)
        return

    # Firma izolasyonu: OTURUMDAN alinir, istekten ASLA.
    fid = oturum.get("firma_id")
    kid = oturum.get("kullanici_id")
    tno = _destek_ticket_no()

    tid = db.deger(
        "INSERT INTO destek_talepleri "
        "(ticket_no, firma_id, kullanici_id, acan_eposta, acan_ad, "
        " modul, konu, aciklama, oncelik) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING ticket_id",
        (tno, fid, kid, oturum.get("eposta") or "",
         _destek_kul_ad(oturum), modul, konu, aciklama, oncelik))

    mid = db.deger(
        "INSERT INTO destek_mesajlari "
        "(ticket_id, yazan_tur, yazan_id, yazan_ad, govde) "
        "VALUES (%s,'kullanici',%s,%s,%s) RETURNING mesaj_id",
        (tid, kid, _destek_kul_ad(oturum), aciklama))

    ek_n, ek_hata = _destek_ek_yaz(tid, mid, ekler)
    out = {"ticket_id": int(tid), "ticket_no": tno, "ek_sayisi": ek_n}
    if ek_hata:
        # Talep KORUNUR: aciklama kaydedildi, silmek veri kaybi olur.
        out["uyari"] = ek_hata
    h.json_yaz(out, 201)


@yol("GET", r"/api/destek/talepler", yetki="firma")
def _u_destek_talep_liste(h, istek, oturum):
    satir = db.sorgu(
        "SELECT t.ticket_id, t.ticket_no, t.modul, t.konu, t.oncelik, "
        "       t.durum, t.olusma_ts, t.guncel_ts, t.son_yanit_ts, "
        "       (SELECT count(*) FROM destek_mesajlari m "
        "         WHERE m.ticket_id=t.ticket_id AND m.ic_not=false) AS mesaj, "
        "       (SELECT count(*) FROM destek_ekleri e "
        "         WHERE e.ticket_id=t.ticket_id) AS ek "
        "FROM destek_talepleri t WHERE t.firma_id=%s "
        "ORDER BY t.guncel_ts DESC LIMIT 200", (oturum.get("firma_id"),))
    h.json_yaz({"talepler": satir}, 200)


@yol("GET", r"/api/destek/talep/(\d+)", yetki="firma")
def _u_destek_talep_getir(h, istek, oturum, tid):
    t = db.tek(
        "SELECT * FROM destek_talepleri WHERE ticket_id=%s AND firma_id=%s",
        (int(tid), oturum.get("firma_id")))
    if not t:
        h.json_yaz({"hata": "Talep bulunamadi"}, 404)
        return
    # ic_not=false: dahili personel notlari kullaniciya DONMEZ.
    m = db.sorgu(
        "SELECT mesaj_id, yazan_tur, yazan_ad, govde, olusma_ts "
        "FROM destek_mesajlari WHERE ticket_id=%s AND ic_not=false "
        "ORDER BY mesaj_id", (int(tid),))
    e = db.sorgu(
        "SELECT ek_id, mesaj_id, dosya_ad, mime, boyut, olusma_ts "
        "FROM destek_ekleri WHERE ticket_id=%s ORDER BY ek_id", (int(tid),))
    h.json_yaz({"talep": t, "mesajlar": m, "ekler": e}, 200)


@yol("POST", r"/api/destek/talep/(\d+)/mesaj", yetki="firma")
def _u_destek_talep_yanit(h, istek, oturum, tid):
    g = istek.govde or {}
    govde = (g.get("govde") or "").strip()
    if len(govde) < 2:
        h.json_yaz({"hata": "Mesaj bos olamaz"}, 400)
        return
    t = db.tek("SELECT ticket_id, durum FROM destek_talepleri "
               "WHERE ticket_id=%s AND firma_id=%s",
               (int(tid), oturum.get("firma_id")))
    if not t:
        h.json_yaz({"hata": "Talep bulunamadi"}, 404)
        return
    if t["durum"] == "kapandi":
        h.json_yaz({"hata": "Kapanmis talebe mesaj eklenemez"}, 409)
        return

    mid = db.deger(
        "INSERT INTO destek_mesajlari "
        "(ticket_id, yazan_tur, yazan_id, yazan_ad, govde) "
        "VALUES (%s,'kullanici',%s,%s,%s) RETURNING mesaj_id",
        (int(tid), oturum.get("kullanici_id"), _destek_kul_ad(oturum), govde))
    ek_n, ek_hata = _destek_ek_yaz(int(tid), mid, g.get("ekler") or [])

    # Kullanici yanit verdi -> personel bakmali.
    db.calistir(
        "UPDATE destek_talepleri SET guncel_ts=now(), "
        "durum=CASE WHEN durum IN ('cozuldu','yanit_bekliyor') "
        "           THEN 'islemde' ELSE durum END WHERE ticket_id=%s",
        (int(tid),))

    out = {"mesaj_id": int(mid), "ek_sayisi": ek_n}
    if ek_hata:
        out["uyari"] = ek_hata
    h.json_yaz(out, 201)


@yol("POST", r"/api/destek/talep/(\d+)/kapat", yetki="firma")
def _u_destek_talep_kapat(h, istek, oturum, tid):
    n = db.calistir(
        "UPDATE destek_talepleri SET durum='kapandi', kapanma_ts=now(), "
        "guncel_ts=now() WHERE ticket_id=%s AND firma_id=%s "
        "AND durum<>'kapandi'", (int(tid), oturum.get("firma_id")))
    if not n:
        h.json_yaz({"hata": "Talep bulunamadi veya zaten kapali"}, 404)
        return
    db.calistir(
        "INSERT INTO destek_mesajlari (ticket_id, yazan_tur, yazan_ad, govde) "
        "VALUES (%s,'sistem','Sistem','Talep kullanici tarafindan kapatildi.')",
        (int(tid),))
    h.json_yaz({"tamam": True}, 200)


@yol("GET", r"/api/destek/ek/(\d+)", yetki="firma")
def _u_destek_ek_indir(h, istek, oturum, ek_id):
    # Firma izolasyonu JOIN ile: baska firmanin eki indirilemez.
    e = db.tek(
        "SELECT e.disk_yol, e.dosya_ad FROM destek_ekleri e "
        "JOIN destek_talepleri t ON t.ticket_id=e.ticket_id "
        "WHERE e.ek_id=%s AND t.firma_id=%s",
        (int(ek_id), oturum.get("firma_id")))
    if not e:
        h.json_yaz({"hata": "Ek bulunamadi"}, 404)
        return
    if not os.path.isfile(e["disk_yol"]):
        h.json_yaz({"hata": "Dosya diskte yok"}, 410)
        return
    h.dosya_akit(e["disk_yol"], e["dosya_ad"])


# ---------- PERSONEL TARAFI ----------

@yol("GET", r"/api/destek/personel/talepler", yetki="destek")
def _u_destek_p_liste(h, istek, oturum):
    durum = (istek.sorgu.get("durum") or "").strip()
    modul = (istek.sorgu.get("modul") or "").strip()
    kosul, par = [], []
    if durum in DESTEK_DURUM:
        kosul.append("t.durum=%s")
        par.append(durum)
    if modul in DESTEK_MODULLER:
        kosul.append("t.modul=%s")
        par.append(modul)
    nerede = ("WHERE " + " AND ".join(kosul)) if kosul else ""

    satir = db.sorgu(
        "SELECT t.ticket_id, t.ticket_no, t.modul, t.konu, t.oncelik, "
        "       t.durum, t.acan_eposta, t.acan_ad, t.firma_id, "
        "       t.atanan_yonetici_id, t.olusma_ts, t.guncel_ts, "
        "       f.unvan AS firma_unvan, f.tur AS firma_tur, "
        "       y.ad_soyad AS atanan_ad, "
        "       (SELECT count(*) FROM destek_mesajlari m "
        "         WHERE m.ticket_id=t.ticket_id) AS mesaj "
        "FROM destek_talepleri t "
        "LEFT JOIN firmalar f ON f.firma_id=t.firma_id "
        "LEFT JOIN sistem_yoneticileri y "
        "       ON y.yonetici_id=t.atanan_yonetici_id " + nerede +
        " ORDER BY CASE t.oncelik WHEN 'kritik' THEN 0 WHEN 'yuksek' THEN 1 "
        "          WHEN 'normal' THEN 2 ELSE 3 END, t.guncel_ts DESC "
        "LIMIT 500", tuple(par))
    sayim = db.sorgu(
        "SELECT durum, count(*) AS n FROM destek_talepleri GROUP BY durum")
    h.json_yaz({"talepler": satir,
                "sayim": {r["durum"]: int(r["n"]) for r in sayim}}, 200)


@yol("GET", r"/api/destek/personel/talep/(\d+)", yetki="destek")
def _u_destek_p_getir(h, istek, oturum, tid):
    t = db.tek(
        "SELECT t.*, f.unvan AS firma_unvan, f.tur AS firma_tur "
        "FROM destek_talepleri t "
        "LEFT JOIN firmalar f ON f.firma_id=t.firma_id "
        "WHERE t.ticket_id=%s", (int(tid),))
    if not t:
        h.json_yaz({"hata": "Talep bulunamadi"}, 404)
        return
    # Personel dahili notlari DA gorur: ic_not suzgeci YOK.
    m = db.sorgu(
        "SELECT mesaj_id, yazan_tur, yazan_ad, govde, ic_not, olusma_ts "
        "FROM destek_mesajlari WHERE ticket_id=%s ORDER BY mesaj_id",
        (int(tid),))
    e = db.sorgu(
        "SELECT ek_id, mesaj_id, dosya_ad, mime, boyut, olusma_ts "
        "FROM destek_ekleri WHERE ticket_id=%s ORDER BY ek_id", (int(tid),))
    h.json_yaz({"talep": t, "mesajlar": m, "ekler": e}, 200)


@yol("POST", r"/api/destek/personel/talep/(\d+)/mesaj", yetki="destek")
def _u_destek_p_yanit(h, istek, oturum, tid):
    g = istek.govde or {}
    govde = (g.get("govde") or "").strip()
    ic_not = bool(g.get("ic_not"))
    if len(govde) < 2:
        h.json_yaz({"hata": "Mesaj bos olamaz"}, 400)
        return
    if not db.tek("SELECT ticket_id FROM destek_talepleri WHERE ticket_id=%s",
                  (int(tid),)):
        h.json_yaz({"hata": "Talep bulunamadi"}, 404)
        return

    mid = db.deger(
        "INSERT INTO destek_mesajlari "
        "(ticket_id, yazan_tur, yazan_id, yazan_ad, govde, ic_not) "
        "VALUES (%s,'personel',%s,%s,%s,%s) RETURNING mesaj_id",
        (int(tid), oturum.get("yonetici_id"),
         oturum.get("ad_soyad") or "Destek", govde, ic_not))
    ek_n, ek_hata = _destek_ek_yaz(int(tid), mid, g.get("ekler") or [])

    # Dahili not durumu DEGISTIRMEZ: kullaniciya gitmeyen bir not
    # "yanit bekliyor" anlamina gelmez.
    if ic_not:
        db.calistir("UPDATE destek_talepleri SET guncel_ts=now() "
                    "WHERE ticket_id=%s", (int(tid),))
    else:
        db.calistir(
            "UPDATE destek_talepleri SET son_yanit_ts=now(), guncel_ts=now(), "
            "durum=CASE WHEN durum IN ('yeni','islemde') "
            "           THEN 'yanit_bekliyor' ELSE durum END "
            "WHERE ticket_id=%s", (int(tid),))

    kimlik.denetim(oturum.get("yonetici_id"), "destek_yanit", "ticket",
                   str(tid), {"ic_not": ic_not}, istek.ip)
    out = {"mesaj_id": int(mid), "ek_sayisi": ek_n}
    if ek_hata:
        out["uyari"] = ek_hata
    h.json_yaz(out, 201)


@yol("POST", r"/api/destek/personel/talep/(\d+)/durum", yetki="destek")
def _u_destek_p_durum(h, istek, oturum, tid):
    durum = ((istek.govde or {}).get("durum") or "").strip()
    if durum not in DESTEK_DURUM:
        h.json_yaz({"hata": "Gecersiz durum"}, 400)
        return
    if durum == "kapandi":
        n = db.calistir(
            "UPDATE destek_talepleri SET durum=%s, guncel_ts=now(), "
            "kapanma_ts=now() WHERE ticket_id=%s", (durum, int(tid)))
    else:
        n = db.calistir(
            "UPDATE destek_talepleri SET durum=%s, guncel_ts=now() "
            "WHERE ticket_id=%s", (durum, int(tid)))
    if not n:
        h.json_yaz({"hata": "Talep bulunamadi"}, 404)
        return
    db.calistir(
        "INSERT INTO destek_mesajlari (ticket_id, yazan_tur, yazan_ad, govde) "
        "VALUES (%s,'sistem','Sistem',%s)",
        (int(tid), "Durum degistirildi: %s" % durum))
    kimlik.denetim(oturum.get("yonetici_id"), "destek_durum", "ticket",
                   str(tid), {"durum": durum}, istek.ip)
    h.json_yaz({"tamam": True, "durum": durum}, 200)


@yol("POST", r"/api/destek/personel/talep/(\d+)/ata", yetki="destek")
def _u_destek_p_ata(h, istek, oturum, tid):
    yid = (istek.govde or {}).get("yonetici_id")
    if yid in (None, "", 0):
        yid = oturum.get("yonetici_id")          # kendine ata
    if not db.tek("SELECT yonetici_id FROM sistem_yoneticileri "
                  "WHERE yonetici_id=%s AND durum='etkin'", (int(yid),)):
        h.json_yaz({"hata": "Gecersiz personel"}, 400)
        return
    n = db.calistir(
        "UPDATE destek_talepleri SET atanan_yonetici_id=%s, guncel_ts=now(), "
        "durum=CASE WHEN durum='yeni' THEN 'islemde' ELSE durum END "
        "WHERE ticket_id=%s", (int(yid), int(tid)))
    if not n:
        h.json_yaz({"hata": "Talep bulunamadi"}, 404)
        return
    kimlik.denetim(oturum.get("yonetici_id"), "destek_ata", "ticket",
                   str(tid), {"yonetici_id": int(yid)}, istek.ip)
    h.json_yaz({"tamam": True, "atanan_yonetici_id": int(yid)}, 200)


@yol("GET", r"/api/destek/personel/ek/(\d+)", yetki="destek")
def _u_destek_p_ek_indir(h, istek, oturum, ek_id):
    e = db.tek("SELECT disk_yol, dosya_ad FROM destek_ekleri WHERE ek_id=%s",
               (int(ek_id),))
    if not e:
        h.json_yaz({"hata": "Ek bulunamadi"}, 404)
        return
    if not os.path.isfile(e["disk_yol"]):
        h.json_yaz({"hata": "Dosya diskte yok"}, 410)
        return
    h.dosya_akit(e["disk_yol"], e["dosya_ad"])


@yol("GET", r"/api/destek/personel/liste", yetki="destek")
def _u_destek_p_personel(h, istek, oturum):
    """Atama icin etkin personel listesi."""
    r = db.sorgu(
        "SELECT yonetici_id, ad_soyad, eposta, rol FROM sistem_yoneticileri "
        "WHERE durum='etkin' AND rol IN ('sistem_yonetici','destek_personel') "
        "ORDER BY ad_soyad")
    h.json_yaz({"personel": r}, 200)

# =====================================================================
# SISTEM YONETICISI / DESTEK PERSONELI YONETIMI
# ---------------------------------------------------------------------
# Bu uclar Turkbey ic personelini yonetir (`sistem_yoneticileri`).
# Firma kullanicilari (`kullanicilar`) ayri bir tablodur ve
# `/api/admin/kullanicilar` uclari ile yonetilir -- karistirilmamali.
#
# ROL DENETIMI UC ICINDE yapilir: yetki katmani `yonetici` duzeyinde
# `gozlemci` ve `destek_personel` rollerini de geciriyor, ama personel
# yonetimi YALNIZ `sistem_yonetici` isidir.  Yetki katmanina yeni bir
# duzey eklemek yerine uc ici denetim secildi; boylece yetki zinciri
# (ve onunla gelen kirilma riski) degismeden kalir.
# =====================================================================
ROL_PERSONEL = ("sistem_yonetici", "gozlemci", "destek_personel")
DURUM_PERSONEL = ("etkin", "askida")


def _personel_kapi(h, oturum):
    """Yalniz `sistem_yonetici` gecer.  Gecerse True doner."""
    if str(oturum.get("rol")) != "sistem_yonetici":
        h.hata_yaz(403, "Bu islem icin sistem yoneticisi yetkisi gerekir")
        return False
    return True


def _etkin_yonetici_sayisi(haric=None):
    """Etkin `sistem_yonetici` sayisi.  `haric` verilirse o kayit
    sayilmaz -- "bu islemden SONRA kac tane kalir" sorusunu yanitlar."""
    if haric:
        return int(db.deger(
            "SELECT count(*) FROM sistem_yoneticileri "
            "WHERE rol = 'sistem_yonetici' AND durum = 'etkin' "
            "AND yonetici_id <> %s", (int(haric),)) or 0)
    return int(db.deger(
        "SELECT count(*) FROM sistem_yoneticileri "
        "WHERE rol = 'sistem_yonetici' AND durum = 'etkin'") or 0)


@yol("GET", r"/api/admin/kk_durum", yetki="yonetici")
def _u_kk_durum(h, istek, oturum):
    """KK_YONETIM_UC_v1 — kaba kuvvet korumasinin anlik durumu.

    Donus: `{tamam, esikler, durum, olaylar}`

    `olaylar` en yeni once siralanir ve varsayilan olarak 200 kayit
    doner. Bellekte tutulan tampon sinirli oldugu icin (modulde
    `_SON_OLAY_SINIR`) bu uc kalici bir denetim izi DEGILDIR; anlik
    gorunurluk saglar. Kalici iz gerekiyorsa ag katmani kayitlari
    (`/var/log/goktungu-merkez.log`, fail2ban) kullanilmalidir.
    """
    if not _personel_kapi(h, oturum):
        return
    try:
        # `istek.sorgu` degerleri DUZ DIZE (olculdu: mk_sunucu.py:121
        # `{a: d[0] for ...}`), liste DEGIL. Liste varsayimi burada
        # sessiz bir TypeError uretirdi ve uc her zaman 200'e duserdi.
        sinir = int(istek.sorgu.get("sinir") or 200)
    except BaseException:
        sinir = 200
    sinir = max(1, min(sinir, 1000))
    try:
        h.json_yaz({
            "tamam": True,
            "esikler": {
                "hesap_esik": kaba_kuvvet.HESAP_ESIK,
                "hesap_pencere": kaba_kuvvet.HESAP_PENCERE,
                "hesap_ceza": kaba_kuvvet.HESAP_CEZA,
                "ip_kisa_esik": kaba_kuvvet.IP_KISA_ESIK,
                "ip_kisa_pencere": kaba_kuvvet.IP_KISA_PENCERE,
                "ip_kisa_ceza": kaba_kuvvet.IP_KISA_CEZA,
                "ip_uzun_esik": kaba_kuvvet.IP_UZUN_ESIK,
                "ip_uzun_pencere": kaba_kuvvet.IP_UZUN_PENCERE,
                "ip_uzun_ceza": kaba_kuvvet.IP_UZUN_CEZA,
            },
            "durum": kaba_kuvvet.durum(),
            "olaylar": kaba_kuvvet.son_olaylar(sinir),
        })
    except BaseException as e:
        # Gorunurluk ucu asla yonetim panelini cokertmez.
        h.hata_yaz(500, "Koruma durumu okunamadi: %s" % e)


@yol("DELETE", r"/api/admin/kk_blok", yetki="yonetici")
def _u_kk_blok_coz(h, istek, oturum):
    """KK_YONETIM_UC_v1 — elle blok cozme.

    Govde: `{"hesap": "..."}` ve/veya `{"ip": "...", "uc": "..."}`

    `uc` verilmezse o adresin TUM uclardaki bloklari cozulur. Bu
    bilincli: yonetici "su kullanicinin erisimini ac" derken hangi
    ucun kilitlendigini bilmek zorunda kalmamalidir.

    Cozme islemi sayaclari da sifirlar; aksi halde kullanici bir
    deneme daha yapinca aninda yeniden kilitlenirdi.
    """
    if not _personel_kapi(h, oturum):
        return
    g = istek.govde or {}
    hesap = (g.get("hesap") or "").strip().lower()
    ip = (g.get("ip") or "").strip()
    uc = (g.get("uc") or "").strip()
    if not hesap and not ip:
        h.hata_yaz(400, "hesap veya ip verilmeli")
        return
    cozulen = {"hesap": 0, "ip": 0}
    try:
        with kaba_kuvvet._kilit:
            if hesap:
                if kaba_kuvvet._hesap_bloklar.pop(hesap, None) is not None:
                    cozulen["hesap"] += 1
                kaba_kuvvet._hesap_denemeler.pop(hesap, None)
            if ip:
                for a in list(kaba_kuvvet._ip_bloklar.keys()):
                    if a[0] == ip and (not uc or a[1] == uc):
                        kaba_kuvvet._ip_bloklar.pop(a, None)
                        cozulen["ip"] += 1
                for a in list(kaba_kuvvet._ip_denemeler.keys()):
                    if a[0] == ip and (not uc or a[1] == uc):
                        kaba_kuvvet._ip_denemeler.pop(a, None)
            kaba_kuvvet._olay_ekle(
                "elle_cozme", ip or "-", uc or "-", hesap,
                "yonetici=%s" % (oturum.get("eposta") or "?"))
    except BaseException as e:
        h.hata_yaz(500, "Cozme basarisiz: %s" % e)
        return
    h.json_yaz({"tamam": True, "cozulen": cozulen})


@yol("GET", r"/api/admin/yoneticiler", yetki="yonetici")
def _u_yoneticiler(h, istek, oturum):
    """Personel listesi.  Sifre ozeti ASLA dondurulmez."""
    if not _personel_kapi(h, oturum):
        return
    r = db.sorgu(
        "SELECT yonetici_id, eposta, ad_soyad, unvan, rol, durum, "
        "       son_giris_ts, son_ip, olusma_ts, "
        "       (eposta_dogrulama_ts IS NOT NULL) AS eposta_dogrulandi "
        "FROM sistem_yoneticileri ORDER BY yonetici_id")
    h.json_yaz({
        "personel": r,
        "sayim": {
            "toplam": len(r),
            "sistem_yonetici": sum(
                1 for x in r if x["rol"] == "sistem_yonetici"),
            "destek_personel": sum(
                1 for x in r if x["rol"] == "destek_personel"),
            "gozlemci": sum(1 for x in r if x["rol"] == "gozlemci"),
            "askida": sum(1 for x in r if x["durum"] == "askida"),
        },
        "ben": oturum.get("yonetici_id"),
    }, 200)


@yol("POST", r"/api/admin/yoneticiler", yetki="yonetici")
def _u_yonetici_ekle(h, istek, oturum):
    """Yeni personel ekler.

    E-posta dogrulama damgasi ATILMAZ: yeni personel ilk girisinde
    dogrulama yapmak zorundadir (kullanici istegi).  SMTP hazir
    degilse yonetici damgayi elle atabilir.
    """
    if not _personel_kapi(h, oturum):
        return
    g = istek.govde or {}
    eposta = (g.get("eposta") or "").strip().lower()
    sifre = g.get("sifre") or ""
    ad_soyad = (g.get("ad_soyad") or "").strip()
    unvan = (g.get("unvan") or "").strip() or None
    rol = (g.get("rol") or "destek_personel").strip()

    if not eposta or "@" not in eposta:
        h.hata_yaz(400, "Gecerli bir e-posta adresi girin")
        return
    if not ad_soyad:
        h.hata_yaz(400, "Ad soyad zorunlu")
        return
    if rol not in ROL_PERSONEL:
        h.hata_yaz(400, "Gecersiz rol")
        return

    yid, hata = kimlik.yonetici_olustur(eposta, sifre, ad_soyad, unvan, rol)
    if hata:
        h.hata_yaz(400, hata)
        return
    kimlik.denetim(oturum["yonetici_id"], "personel_ekle", "yonetici",
                   str(yid), {"eposta": eposta, "rol": rol}, istek.ip)
    h.json_yaz({"tamam": True, "yonetici_id": yid}, 201)


@yol("PUT", r"/api/admin/yoneticiler/(\d+)", yetki="yonetici")
def _u_yonetici_guncelle(h, istek, oturum, yid):
    """Ad/unvan/rol/durum guncellemesi.

    KENDI rolunu veya durumunu degistirmek YASAK: yetki yukseltme ve
    kendini kilitleme boylece onlenir.  Ad ve unvan degistirilebilir.
    """
    if not _personel_kapi(h, oturum):
        return
    yid = int(yid)
    g = istek.govde or {}
    mevcut = db.tek("SELECT yonetici_id, eposta, rol, durum "
                    "FROM sistem_yoneticileri WHERE yonetici_id = %s", (yid,))
    if not mevcut:
        h.hata_yaz(404, "Personel bulunamadi")
        return

    kendisi = int(oturum.get("yonetici_id") or 0) == yid
    alanlar = []
    degerler = []

    if "ad_soyad" in g:
        ad = (g.get("ad_soyad") or "").strip()
        if not ad:
            h.hata_yaz(400, "Ad soyad bos olamaz")
            return
        alanlar.append("ad_soyad = %s")
        degerler.append(ad)

    if "unvan" in g:
        alanlar.append("unvan = %s")
        degerler.append((g.get("unvan") or "").strip() or None)

    if "rol" in g and g["rol"] != mevcut["rol"]:
        if kendisi:
            h.hata_yaz(403, "Kendi rolunuzu degistiremezsiniz")
            return
        rol = (g.get("rol") or "").strip()
        if rol not in ROL_PERSONEL:
            h.hata_yaz(400, "Gecersiz rol")
            return
        # Son etkin sistem yoneticisinin rolu dusurulemez
        if (mevcut["rol"] == "sistem_yonetici"
                and mevcut["durum"] == "etkin"
                and rol != "sistem_yonetici"
                and _etkin_yonetici_sayisi(haric=yid) == 0):
            h.hata_yaz(409, "Son etkin sistem yoneticisinin rolu "
                            "dusurulemez")
            return
        alanlar.append("rol = %s")
        degerler.append(rol)

    if "durum" in g and g["durum"] != mevcut["durum"]:
        if kendisi:
            h.hata_yaz(403, "Kendi durumunuzu degistiremezsiniz")
            return
        durum = (g.get("durum") or "").strip()
        if durum not in DURUM_PERSONEL:
            h.hata_yaz(400, "Gecersiz durum")
            return
        if (durum == "askida"
                and mevcut["rol"] == "sistem_yonetici"
                and _etkin_yonetici_sayisi(haric=yid) == 0):
            h.hata_yaz(409, "Son etkin sistem yoneticisi askiya "
                            "alinamaz")
            return
        alanlar.append("durum = %s")
        degerler.append(durum)

    if not alanlar:
        h.json_yaz({"tamam": True, "degisiklik": 0})
        return

    degerler.append(yid)
    db.calistir("UPDATE sistem_yoneticileri SET " + ", ".join(alanlar) +
                " WHERE yonetici_id = %s", tuple(degerler))
    kimlik.denetim(oturum["yonetici_id"], "personel_guncelle", "yonetici",
                   str(yid), {"alanlar": sorted(g.keys())}, istek.ip)
    h.json_yaz({"tamam": True, "degisiklik": len(alanlar)})


@yol("POST", r"/api/admin/yoneticiler/(\d+)/sifre", yetki="yonetici")
def _u_yonetici_sifre(h, istek, oturum, yid):
    """Personel sifresini sifirlar.

    Mevcut sifre SORULMAZ: bu bir yonetici islemi, kullanicinin kendi
    sifre degistirmesi degil.  Kendi sifresini degistirmek isteyen
    yonetici de bu ucu kullanabilir.
    """
    if not _personel_kapi(h, oturum):
        return
    yid = int(yid)
    sifre = (istek.govde or {}).get("sifre") or ""
    hata = kimlik.sifre_gucu(sifre)
    if hata:
        h.hata_yaz(400, hata)
        return
    if not db.tek("SELECT 1 FROM sistem_yoneticileri "
                  "WHERE yonetici_id = %s", (yid,)):
        h.hata_yaz(404, "Personel bulunamadi")
        return
    db.calistir("UPDATE sistem_yoneticileri SET sifre_ozet = %s "
                "WHERE yonetici_id = %s",
                (kimlik.sifre_ozetle(sifre), yid))
    kimlik.denetim(oturum["yonetici_id"], "personel_sifre", "yonetici",
                   str(yid), {}, istek.ip)
    h.json_yaz({"tamam": True})


@yol("DELETE", r"/api/admin/yoneticiler/(\d+)", yetki="yonetici")
def _u_yonetici_sil(h, istek, oturum, yid):
    """Personel siler.

    Iki koruma: kimse kendini silemez, ve son etkin sistem yoneticisi
    silinemez.  Ikincisi olmadan sisteme yonetici erisimi tumden
    kapanabilir ve geri donus yolu kalmaz.
    """
    if not _personel_kapi(h, oturum):
        return
    yid = int(yid)
    if int(oturum.get("yonetici_id") or 0) == yid:
        h.hata_yaz(403, "Kendi hesabinizi silemezsiniz")
        return
    mevcut = db.tek("SELECT eposta, rol, durum FROM sistem_yoneticileri "
                    "WHERE yonetici_id = %s", (yid,))
    if not mevcut:
        h.hata_yaz(404, "Personel bulunamadi")
        return
    if (mevcut["rol"] == "sistem_yonetici"
            and _etkin_yonetici_sayisi(haric=yid) == 0):
        h.hata_yaz(409, "Son etkin sistem yoneticisi silinemez")
        return
    # Atanmis destek talepleri BOSA CIKARILIR, talep silinmez.
    db.calistir("UPDATE destek_talepleri SET atanan_yonetici_id = NULL "
                "WHERE atanan_yonetici_id = %s", (yid,))
    db.calistir("DELETE FROM sistem_yoneticileri WHERE yonetici_id = %s",
                (yid,))
    kimlik.denetim(oturum["yonetici_id"], "personel_sil", "yonetici",
                   str(yid), {"eposta": mevcut["eposta"],
                              "rol": mevcut["rol"]}, istek.ip)
    h.json_yaz({"tamam": True})


@yol("POST", r"/api/admin/yoneticiler/(\d+)/dogrula", yetki="yonetici")
def _u_yonetici_dogrula(h, istek, oturum, yid):
    """E-posta dogrulama damgasini ELLE atar.

    SMTP hazir olmadiginda personelin sisteme girebilmesi icin
    gereklidir.  Denetim kaydina yazilir -- kimin kimi elle
    dogruladigi izlenebilir olmali.
    """
    if not _personel_kapi(h, oturum):
        return
    yid = int(yid)
    if not db.tek("SELECT 1 FROM sistem_yoneticileri "
                  "WHERE yonetici_id = %s", (yid,)):
        h.hata_yaz(404, "Personel bulunamadi")
        return
    db.calistir("UPDATE sistem_yoneticileri SET eposta_dogrulama_ts = now() "
                "WHERE yonetici_id = %s", (yid,))
    kimlik.denetim(oturum["yonetici_id"], "personel_elle_dogrula",
                   "yonetici", str(yid), {}, istek.ip)
    h.json_yaz({"tamam": True})


@yol("POST", r"/api/dogrulama/gonder", yetki="acik")
def _u_dogrulama_gonder(h, istek, oturum):
    """Dogrulama bagi gonderir/yeniler.

    Hesap VARLIGI SIZDIRILMAZ: kayitli olmayan adres icin de 200
    doner. Aksi halde bu uc bir hesap sayim araci olur.
    """
    e = (istek.govde.get("eposta") or "").strip().lower()
    if not e or "@" not in e:
        h.json_yaz({"hata": "Geçerli bir e-posta adresi girin"}, 400)
        return
    # Hedef cozumleme: adres once kullanici, sonra yonetici tablosunda
    # aranir.  Hesap varligi SIZDIRILMAZ; bulunmasa da 200 doner.
    hedef_tur = None
    hedef_id = None
    ad = ""
    try:
        k = db.tek("SELECT kullanici_id, ad, soyad, eposta_dogrulama_ts "
                   "FROM kullanicilar WHERE eposta = %s", (e,))
        if k:
            hedef_tur = "kullanici"
            hedef_id = int(k["kullanici_id"])
            ad = ((k.get("ad") or "") + " " + (k.get("soyad") or "")).strip()
        else:
            y = db.tek("SELECT yonetici_id, ad_soyad, eposta_dogrulama_ts "
                       "FROM sistem_yoneticileri WHERE eposta = %s", (e,))
            if y:
                hedef_tur = "yonetici"
                hedef_id = int(y["yonetici_id"])
                ad = (y.get("ad_soyad") or "").strip()
    except Exception as x:
        print("[DOGRULAMA] hedef cozumleme hatasi: %s" % x)
        h.json_yaz({"hata": "Gönderim başarısız"}, 500)
        return
    if not hedef_tur:
        # Kayitli olmayan adres: hesap sayimi engellemek icin 200.
        h.json_yaz({"tamam": True,
                    "mesaj": "Doğrulama bağı e-posta adresinize "
                             "gönderildi"}, 200)
        return
    try:
        import mk_eposta as ep
        tamam, hata = ep.dogrulama_gonder(hedef_tur, hedef_id, e, ad)
    except Exception as x:
        print("[DOGRULAMA] gonder hata: %s" % x)
        h.json_yaz({"hata": "Gönderim başarısız"}, 500)
        return
    if not tamam:
        # `kod_uret` hiz sinirini "Cok sik istek" ile bildirir -> 429.
        m = hata or "Gönderim başarısız"
        h.json_yaz({"hata": m},
                   429 if m.startswith("Cok sik istek") else 500)
        return
    kimlik.denetim(None, "dogrulama_gonder", hedef_tur, str(hedef_id),
                   {"eposta": e}, istek.ip)
    h.json_yaz({"tamam": True,
                "mesaj": "Doğrulama bağı e-posta adresinize gönderildi"}, 200)


@yol("POST", r"/api/dogrulama/onayla", yetki="acik")
def _u_dogrulama_onayla(h, istek, oturum):
    """Dogrulama bagini tuketir ve hesabi dogrulanmis isaretler."""
    kod = (istek.govde.get("kod") or "").strip()
    if not kod:
        h.json_yaz({"hata": "Doğrulama bağı eksik"}, 400)
        return
    try:
        import mk_eposta as ep
        veri, hata = ep.kod_dogrula(kod)
    except Exception as x:
        print("[DOGRULAMA] onayla hata: %s" % x)
        h.json_yaz({"hata": "Doğrulama başarısız"}, 500)
        return
    if hata:
        h.json_yaz({"hata": hata}, 400)
        return
    h.json_yaz({"tamam": True, "hedef_tur": veri.get("hedef_tur"),
                "mesaj": "E-posta adresiniz doğrulandı. Giriş yapabilirsiniz."},
               200)


@yol("GET", r"/api/dogrulama/durum", yetki="acik")
def _u_dogrulama_durum(h, istek, oturum):
    """Adresin dogrulanmis olup olmadigini bildirir.

    Hesap varligi sizdirmaz: bilinmeyen adres icin de
    {"dogrulandi": false, "gerekli": false} doner.
    """
    e = (istek.sorgu.get("eposta") or "").strip().lower()
    if not e:
        h.json_yaz({"dogrulandi": False, "gerekli": False})
        return
    # `except Exception` ile hata YUTULMAZ: sessiz yanlis cevap,
    # gorunur hatadan kotudur.  Yalniz gercek veritabani hatasi 500
    # verir; bilinmeyen adres normal 200 akisindan doner.
    try:
        import mk_eposta as ep
        k = db.tek("SELECT kullanici_id, eposta_dogrulama_ts "
                   "FROM kullanicilar WHERE eposta = %s", (e,))
        if k:
            h.json_yaz({"dogrulandi": bool(k.get("eposta_dogrulama_ts")),
                        "gerekli": True})
            return
        y = db.tek("SELECT yonetici_id, eposta_dogrulama_ts "
                   "FROM sistem_yoneticileri WHERE eposta = %s", (e,))
        if y:
            h.json_yaz({"dogrulandi": bool(y.get("eposta_dogrulama_ts")),
                        "gerekli": True})
            return
    except Exception as x:
        print("[DOGRULAMA] durum hata: %s" % x)
        h.json_yaz({"hata": "Durum okunamadi"}, 500)
        return
    # Bilinmeyen adres: hesap varligi sizdirilmaz.
    h.json_yaz({"dogrulandi": False, "gerekli": False})


@yol("GET", r"/api/admin/smtp", yetki="yonetici")
def _u_admin_smtp_oku(h, istek, oturum):
    """SMTP ayarlarini dondurur. PAROLA ALANI YANITA GIRMEZ."""
    try:
        import mk_eposta as ep
        h.json_yaz({"smtp": ep.smtp_gorunum()})
    except Exception as x:
        h.json_yaz({"hata": str(x)}, 500)


@yol("POST", r"/api/admin/smtp", yetki="yonetici")
def _u_admin_smtp_yaz(h, istek, oturum):
    """SMTP ayarlarini yazar.

    Parola BOS gelirse mevcut parola KORUNUR (arayuz parolayi hic
    okumadigi icin her kayitta yeniden yazmasi beklenemez).
    """
    try:
        import mk_eposta as ep
        ep.smtp_yaz(istek.govde or {})
        kimlik.denetim(oturum.get("yonetici_id"), "smtp_ayar", "sistem", None,
                       ip=istek.ip)
        h.json_yaz({"tamam": True, "smtp": ep.smtp_gorunum()}, 200)
    except Exception as x:
        h.json_yaz({"hata": str(x)}, 400)


@yol("POST", r"/api/admin/smtp/sina", yetki="yonetici")
def _u_admin_smtp_sina(h, istek, oturum):
    """Sinav e-postasi gonderir."""
    hedef = (istek.govde.get("hedef") or oturum.get("eposta") or "").strip()
    if not hedef or "@" not in hedef:
        h.json_yaz({"hata": "Geçerli bir hedef adres girin"}, 400)
        return
    try:
        import mk_eposta as ep
        ep.gonder(hedef, "GÖKTUNGU SMTP sınavı",
                  "<p>Bu bir sınav iletisidir. SMTP yapılandırması "
                  "çalışıyor.</p>",
                  "Bu bir sinav iletisidir. SMTP yapilandirmasi calisiyor.")
    except Exception as x:
        h.json_yaz({"hata": str(x)}, 400)
        return
    h.json_yaz({"tamam": True, "mesaj": "Sınav iletisi gönderildi"}, 200)


@yol("POST", r"/api/firma/giris", yetki="acik")
def _u_firma_giris(h, istek, oturum):
    veri, hata = kimlik.kullanici_giris(
        (istek.govde.get("eposta") or "").strip(),
        istek.govde.get("sifre") or "",
        istek.ip, istek.h.headers.get("User-Agent"))
    if hata == "E-POSTA_DOGRULANMADI":
        # 403 (401 DEGIL): kimlik dogru, eksik olan e-posta onayi.
        # Arayuz bu ayrimi gorup "dogrulama bagi gonder" akisina
        # yonlendirir; 401 donsaydi kullaniciya "sifre hatali"
        # gosterilirdi ve sifresini bosuna sifirlamaya calisirdi.
        h.json_yaz({"hata": "E-posta adresiniz doğrulanmadı",
                    "dogrulama_gerekli": True}, 403)
        return
    if hata:
        h.json_yaz({"hata": hata}, 401)
        return
    # IS9B-CEREZ-ALANI: `Host` gecirilir; cerez kok alan adina baglanir.
    kurabiye = kimlik.kurabiye_yaz("goktungu_firma", veri["jeton"],
                                   istek.h.headers.get("Host"))
    h.json_yaz({"tamam": True, "kullanici": veri}, 200,
               {"Set-Cookie": kurabiye})


@yol("POST", r"/api/firma/cikis", yetki="firma")
def _u_firma_cikis(h, istek, oturum):
    kimlik.kullanici_cikis(oturum["jeton"])
    # IS9B-CEREZ-ALANI: silme dizesi yazma ile AYNI Domain'i tasir.
    h.json_yaz({"tamam": True}, 200,
               {"Set-Cookie": kimlik.kurabiye_sil(
                   "goktungu_firma", istek.h.headers.get("Host"))})


@yol("GET", r"/api/firma/ben", yetki="firma")
def _u_firma_ben(h, istek, oturum):
    # Oturum bitisi ve kalan sure YANITA KATILIR: tanitim sayfasi
    # kullanici menusunu bu bilgiyle yonetir ve sure dolunca kendini
    # kapatir.  Bunlar dondurulmezse arayuz oturumun ne zaman
    # dusecegini bilemez, kullanici da bos ekranla karsilasir.
    b = oturum.get("bitis_ts")
    try:
        bitis_iso = b.isoformat() if hasattr(b, "isoformat") else (
            str(b) if b else None)
    except Exception:
        bitis_iso = None
    kalan = None
    if hasattr(b, "timestamp"):
        try:
            simdi = dt.datetime.now(b.tzinfo) if b.tzinfo else \
                dt.datetime.now()
            kalan = max(0, int((b - simdi).total_seconds()))
        except Exception:
            kalan = None
    h.json_yaz({
        "kullanici": {a: oturum.get(a) for a in (
            "kullanici_id", "firma_id", "eposta", "ad", "soyad", "rol",
            "firma_unvan", "firma_kisa_ad")},
        "oturum": {
            "bitis_ts": bitis_iso,
            "kalan_sn": kalan,
            "omur_sn": kimlik.oturum_saniye(),
            # Kurumsal panel rol kapisi arayuzde de bilinmelidir: menu
            # ogesi yalniz yetkili kullaniciya gosterilir.  Sunucu kapisi
            # (_dosya_sun /company/) yine baskindir; bu alan gorunum
            # kararidir, guvenlik dayanagi degildir.
            "panel_yetkisi": str(oturum.get("rol")) == "firma_yonetici",
        },
    })


@yol("GET", r"/api/firma/gosterge", yetki="firma")
def _u_firma_gosterge(h, istek, oturum):
    """Firma ozeti. `api.gosterge()` TUM sistemi kapsadigi icin burada
    KULLANILAMAZ; firma sinirli sorgular ayrica yazilir."""
    fid = _firma_id(oturum)
    t = db.tek(
        "SELECT (SELECT count(*) FROM kullanicilar "
        "        WHERE firma_id = %s) AS kullanici, "
        "(SELECT count(*) FROM kullanicilar WHERE firma_id = %s "
        "        AND durum = 'etkin') AS kullanici_etkin, "
        "(SELECT count(*) FROM ucus_telemetri t "
        "   JOIN ucus_kayitlari u ON u.ucus_id = t.ucus_id "
        "  WHERE u.firma_id = %s) AS telemetri, "
        "(SELECT coalesce(sum(mesafe_m), 0) FROM ucus_kayitlari "
        "        WHERE firma_id = %s) AS toplam_mesafe_m, "
        "(SELECT count(*) FROM dronlar WHERE firma_id = %s) AS dron, "
        "(SELECT count(*) FROM ucus_kayitlari WHERE firma_id = %s) AS ucus, "
        "(SELECT coalesce(sum(sure_sn), 0) FROM ucus_kayitlari "
        "        WHERE firma_id = %s) AS toplam_sure_sn, "
        "(SELECT count(*) FROM ucus_kayitlari WHERE firma_id = %s "
        "        AND baslangic_ts > now() - interval '7 days') AS ucus_7gun, "
        "(SELECT count(*) FROM video_kayitlari WHERE firma_id = %s "
        "        AND durum = 'hazir') AS video, "
        "(SELECT coalesce(sum(boyut_bayt), 0) FROM video_kayitlari "
        "        WHERE firma_id = %s AND durum = 'hazir') AS video_bayt, "
        "(SELECT count(*) FROM sunucu_ornekleri WHERE firma_id = %s "
        "        AND durum = 'etkin') AS sunucu",
        (fid,) * 11) or {}
    sunucular = api.sunucu_liste(fid)
    t["sunucu_cevrimici"] = sum(1 for s in sunucular if s.get("cevrimici"))
    t["son_ucuslar"] = api.ucus_liste(firma_id=fid, boyut=10)["kayitlar"]
    t["gunluk_ucus"] = db.sorgu(
        "SELECT g::date AS gun, count(u.ucus_id) AS adet, "
        "       coalesce(sum(u.sure_sn), 0) AS sure_sn "
        "FROM generate_series(current_date - interval '13 days', "
        "                     current_date, interval '1 day') g "
        "LEFT JOIN ucus_kayitlari u ON u.baslangic_ts::date = g::date "
        "                          AND u.firma_id = %s "
        "GROUP BY g ORDER BY g", (fid,))
    t["dron_ucus"] = db.sorgu(
        "SELECT d.ad, d.yerel_uid, d.arac_turu, count(u.ucus_id) AS adet, "
        "       coalesce(sum(u.sure_sn), 0) AS sure "
        "FROM dronlar d "
        "JOIN ucus_kayitlari u ON u.dron_id = d.dron_id "
        "WHERE d.firma_id = %s "
        "GROUP BY d.dron_id, d.ad, d.yerel_uid, d.arac_turu "
        "ORDER BY adet DESC, sure DESC LIMIT 10", (fid,))
    t["firma"] = db.tek(
        "SELECT unvan, kisa_ad, vergi_no, adres, telefon, web, ulke, "
        "       maks_kullanici, maks_sunucu, abonelik, "
        "       abonelik_bitis, durum, olusma_ts "
        "FROM firmalar WHERE firma_id = %s",
        (fid,)) or {}
    h.json_yaz(t)


@yol("GET", r"/api/firma/kullanicilar", yetki="firma")
def _u_firma_kullanicilar(h, istek, oturum):
    s = istek.sorgu
    h.json_yaz(api.kullanici_liste(
        _firma_id(oturum), s.get("arama") or None, s.get("rol") or None,
        int(s.get("sayfa", 1)), int(s.get("boyut", 50))))


@yol("GET", r"/api/firma/ucuslar", yetki="firma")
def _u_firma_ucuslar(h, istek, oturum):
    s = istek.sorgu
    h.json_yaz(api.ucus_liste(
        _firma_id(oturum), _pilot_kisitla(oturum, s.get("kullanici_id")),
        int(s["dron_id"]) if s.get("dron_id") else None,
        s.get("baslangic") or None, s.get("bitis") or None,
        int(s.get("sayfa", 1)), int(s.get("boyut", 50))))


def _firma_ucus_al(h, oturum, uid):
    """Ucus kaydini firma ve pilot sinirlarini DOGRULAYARAK dondurur.
    Yetkisizse yanit yazilir ve None doner."""
    u = api.ucus_getir(int(uid))
    if not u or int(u.get("firma_id") or 0) != _firma_id(oturum):
        h.hata_yaz(404, "Uçuş kaydı bulunamadı")
        return None
    if oturum.get("rol") == "pilot" and \
            int(u.get("kullanici_id") or 0) != int(oturum["kullanici_id"]):
        h.hata_yaz(403, "Bu uçuş kaydına erişim yetkiniz yok")
        return None
    return u


@yol("GET", r"/api/firma/ucuslar/(\d+)", yetki="firma")
def _u_firma_ucus_getir(h, istek, oturum, uid):
    u = _firma_ucus_al(h, oturum, uid)
    if u:
        h.json_yaz(u)


@yol("GET", r"/api/firma/ucuslar/(\d+)/telemetri", yetki="firma")
def _u_firma_ucus_telemetri(h, istek, oturum, uid):
    if _firma_ucus_al(h, oturum, uid):
        h.json_yaz({"kayitlar": api.ucus_telemetri(
            int(uid), int(istek.sorgu.get("seyreltme", 1)))})


@yol("GET", r"/api/firma/videolar", yetki="firma")
def _u_firma_videolar(h, istek, oturum):
    s = istek.sorgu
    h.json_yaz(api.video_liste(
        _firma_id(oturum), _pilot_kisitla(oturum, s.get("kullanici_id")),
        int(s["ucus_id"]) if s.get("ucus_id") else None,
        int(s.get("sayfa", 1)), int(s.get("boyut", 50))))


@yol("GET", r"/api/firma/videolar/(\d+)", yetki="firma")
def _u_firma_video_getir(h, istek, oturum, vid):
    v = api.video_getir(int(vid))
    if not v or int(v.get("firma_id") or 0) != _firma_id(oturum):
        h.hata_yaz(404, "Video kaydı bulunamadı")
        return
    h.json_yaz(v)


@yol("GET", r"/api/firma/videolar/(\d+)/akis", yetki="firma")
def _u_firma_video_akis(h, istek, oturum, vid):
    """Video oynatma. Yonetici ucuyla ayni mantik, firma sinirli."""
    v = api.video_getir(int(vid))
    if not v or int(v.get("firma_id") or 0) != _firma_id(oturum):
        h.hata_yaz(404, "Video kaydı bulunamadı")
        return
    if v["depo_yeri"] == "merkez" and v.get("dosya_yol"):
        hedef = os.path.normpath(os.path.join(VERI_KOKU, "video",
                                              v["dosya_yol"].lstrip("/")))
        if not os.path.isfile(hedef):
            h.hata_yaz(404, "Video dosyası merkezde bulunamadı")
            return
        istek.yol = "/video/" + v["dosya_yol"].lstrip("/")
        h._dosya_sun(istek)
        return
    if not v.get("ornek_id"):
        h.hata_yaz(409, "Video yerel sunucuda ve sunucu bilinmiyor")
        return
    veri, hata = kopruye_sor(int(v["ornek_id"]), "video_parca",
                             {"yerel_yol": v.get("yerel_yol"),
                              "video_uid": v.get("video_uid")}, 30.0)
    if hata:
        h.hata_yaz(503, f"Yerel sunucudan alınamadı: {hata}")
        return
    import base64
    govde = base64.b64decode((veri or {}).get("b64") or "")
    h._yaz(200, govde, (veri or {}).get("tur") or "video/mp4")


@yol("GET", r"/api/firma/sunucular", yetki="firma")
def _u_firma_sunucular(h, istek, oturum):
    """Firmanin kayitli GCS istasyonlari ve canli cevrimici durumu.
    `/app/` erisim kapisi bu ucu kullanir."""
    h.json_yaz({"kayitlar": api.sunucu_liste(_firma_id(oturum))})


@yol("GET", r"/api/firma/sunucular/(\d+)/sor/([a-z_]+)", yetki="firma")
def _u_firma_sunucu_sor(h, istek, oturum, oid, eylem):
    """Firmanin kendi istasyonuna canli koprü sorgusu (dron/port/servis).
    Ornegin SAHIBI dogrulanir; baska firmanin ornegi sorgulanamaz."""
    o = db.tek("SELECT firma_id FROM sunucu_ornekleri WHERE ornek_id = %s",
               (int(oid),))
    if not o or int(o["firma_id"]) != _firma_id(oturum):
        h.hata_yaz(404, "Sunucu bulunamadı")
        return
    veri, hata = kopruye_sor(int(oid), eylem, dict(istek.sorgu))
    if hata:
        h.hata_yaz(503, hata)
        return
    h.json_yaz(veri or {})


def _ic_uc_dogrula(h, istek):
    """IC UC ortak korumasi: `(ornek_id, firma_id)` dondurur veya yanit yazip
    None dondurur.

    `/api/ic/kopru_sor` ile AYNI iki katmanli koruma. Ortak islev olarak
    cikarilmasinin nedeni: her yeni ic uc icin denetimi elle kopyalamak,
    bir gun bir ucta `X-Ic-Anahtar` denetimini atlamaya yol acar.
    """
    try:
        es = h.client_address[0]
    except Exception:
        es = ""
    if es not in ("127.0.0.1", "::1", "localhost"):
        h.hata_yaz(404, "Bulunamadı")
        return None
    beklenen = (os.environ.get("GOKTUNGU_IC_ANAHTAR") or "").strip()
    if not beklenen:
        h.hata_yaz(404, "Bulunamadı")
        return None
    gelen = (h.headers.get("X-Ic-Anahtar") or "").strip()
    if not hmac.compare_digest(gelen, beklenen):
        h.hata_yaz(403, "İç anahtar geçersiz")
        return None
    g = istek.govde or {}
    try:
        oid = int(g.get("ornek_id") or 0)
        fid = int(g.get("firma_id") or 0)
    except Exception:
        h.hata_yaz(400, "ornek_id ve firma_id zorunlu")
        return None
    if not (oid and fid):
        h.hata_yaz(400, "ornek_id ve firma_id zorunlu")
        return None
    # FIRMA IZOLASYONU: ornegin gercekten o firmaya ait oldugu
    # dogrulanir. Boylece GCS'de bir kusur olsa bile capraz firma
    # sorgusu yapilamaz.
    o = db.tek("SELECT firma_id FROM sunucu_ornekleri WHERE ornek_id = %s",
               (oid,))
    if not o or int(o["firma_id"]) != fid:
        h.hata_yaz(404, "Sunucu bulunamadı")
        return None
    return oid, fid


@yol("POST", r"/api/ic/akis_ac", yetki="acik")
def _u_ic_akis_ac(h, istek, oturum):
    """IC UC — ham MAVLink akis kanali acar.

    Iki asamali: (1) merkezde yerel UDP portu ayrilir, (2) koprue
    `akis_ac` istegi yollanir. Sira ONEMLIDIR: port once ayrilir, cunku
    kopru kanali actiktan hemen sonra telemetri gonderebilir ve port
    hazir olmazsa ilk paketler kaybolur.

    Kopru tarafi basarisiz olursa ayrilan port SERBEST BIRAKILIR; aksi
    halde her basarisiz denemede merkezde bir port sizar.

    v2.4.56: govdede `gcs_port` gelirse GCS o portu KENDİSİ bind etmistir
    ve merkez oraya yazar. Yanitta donen `port`, GCS'nin dinleyecegi port
    olmalidir; merkez kendi portunu `merkez.port` alaninda bildirir.
    Eskiden merkez portu `port` olarak donuyordu ve GCS ayni portu bind
    etmeye calisip `Address already in use` aliyordu (olculdu).
    """
    d = _ic_uc_dogrula(h, istek)
    if d is None:
        return
    oid, fid = d
    g = istek.govde or {}
    try:
        kid = int(g.get("kanal_id") or 0)
    except Exception:
        kid = 0
    if not kid:
        h.hata_yaz(400, "kanal_id zorunlu")
        return
    tanim = dict(g.get("tanim") or {})
    try:
        gcs_port = int(g.get("gcs_port") or 0)
    except Exception:
        gcs_port = 0
    ozet, hata = akis.AKIS.kanal_ac(oid, kid, tanim, gcs_port=gcs_port)
    if hata:
        h.json_yaz({"basarili": False, "hata": hata})
        return
    veri, khata = kopruye_sor(oid, "akis_ac",
                             {"kanal_id": kid, "tanim": tanim},
                             float(g.get("zaman_asimi") or 12.0))
    if khata or not (veri or {}).get("tamam"):
        akis.AKIS.kanal_kapat(oid, kid)
        h.json_yaz({"basarili": False,
                    "hata": khata or (veri or {}).get("hata")
                    or "Köprü kanalı açamadı"})
        return
    # GCS portu bildirmisse onu geri dondur: cagirici o portu bind etmis
    # durumdadir ve yanittaki degeri dogrulama icin karsilastirir.
    # Bildirmemisse (eski GCS) merkez portu donulur.
    h.json_yaz({"basarili": True,
                "port": gcs_port or ozet["port"],
                "gcs_port": gcs_port,
                "merkez_port": ozet["port"],
                "adres": akis.YEREL_ADRES, "merkez": ozet,
                "kopru": (veri or {}).get("kanal") or {}})


@yol("POST", r"/api/ic/video_ac", yetki="acik")
def _u_ic_video_ac(h, istek, oturum):
    """IC UC — canli kamera karesi kanali acar (FAZ19-IS60).

    Iki asamali, SIRA ONEMLIDIR:
      1. merkezde UDP ucu ayrilir (App'in bind ettigi porta yazacak)
      2. kopruye `video_canli_ac` yollanir

    Port once ayrilir cunku kopru kanali actiktan hemen sonra kare
    gondermeye baslar; uc hazir olmazsa ilk kareler kaybolur ve
    App'in `ilk_kare_bekle` tavani bosuna dolar.

    Kopru tarafi basarisiz olursa ayrilan uc SERBEST BIRAKILIR.
    """
    d = _ic_uc_dogrula(h, istek)
    if d is None:
        return
    oid, fid = d
    g = istek.govde or {}
    try:
        kid = int(g.get("kamera_id") or 0)
        app_port = int(g.get("app_port") or 0)
    except Exception:
        kid, app_port = 0, 0
    if not kid:
        h.hata_yaz(400, "kamera_id zorunlu")
        return
    if not app_port:
        h.hata_yaz(400, "app_port zorunlu")
        return
    ozet, hata = video.VIDEO.kanal_ac(oid, kid, app_port)
    if hata:
        h.json_yaz({"basarili": False, "hata": hata})
        return
    veri, khata = kopruye_sor(oid, "video_canli_ac", {"id": kid},
                              float(g.get("zaman_asimi") or 12.0))
    if khata or not (veri or {}).get("tamam"):
        video.VIDEO.kanal_kapat(oid, kid)
        h.json_yaz({"basarili": False,
                    "hata": khata or (veri or {}).get("hata")
                    or "Kopru canli yayini baslatamadi"})
        return
    h.json_yaz({"basarili": True, "merkez": ozet,
                "kopru": veri or {}})


@yol("POST", r"/api/ic/video_kapat", yetki="acik")
def _u_ic_video_kapat(h, istek, oturum):
    """IC UC — canli kamera kanalini kapatir.

    Merkez tarafi HER ZAMAN kapatilir, kopru yanit vermese bile;
    aksi halde kopru cevrimdisi oldugunda UDP ucu sizar.
    """
    d = _ic_uc_dogrula(h, istek)
    if d is None:
        return
    oid, fid = d
    g = istek.govde or {}
    try:
        kid = int(g.get("kamera_id") or 0)
    except Exception:
        kid = 0
    if not kid:
        h.hata_yaz(400, "kamera_id zorunlu")
        return
    vardi = video.VIDEO.kanal_kapat(oid, kid)
    kopru_hata = None
    if role.ROLE.ornek_ile(oid) is not None:
        _, kopru_hata = kopruye_sor(oid, "video_canli_kapat",
                                    {"id": kid}, 6.0)
    h.json_yaz({"basarili": True, "merkez_vardi": bool(vardi),
                "kopru_hata": kopru_hata or ""})


@yol("POST", r"/api/ic/video_durum", yetki="acik")
def _u_ic_video_durum(h, istek, oturum):
    """IC UC — acik canli kamera kanallari (tanilama)."""
    d = _ic_uc_dogrula(h, istek)
    if d is None:
        return
    oid, fid = d
    g = istek.govde or {}
    yanit = {"basarili": True, "merkez": video.VIDEO.durum(oid)}
    if g.get("kopru"):
        veri, khata = kopruye_sor(oid, "video_canli_durum", {}, 6.0)
        yanit["kopru"] = veri or {}
        yanit["kopru_hata"] = khata or ""
    h.json_yaz(yanit)


@yol("POST", r"/api/ic/akis_kapat", yetki="acik")
def _u_ic_akis_kapat(h, istek, oturum):
    """IC UC — akis kanalini kapatir.

    Merkez tarafi HER ZAMAN kapatilir, kopru yanit vermese bile. Aksi
    halde kopru cevrimdisi oldugunda GCS kanali kapatamaz ve UDP portu
    sizar.
    """
    d = _ic_uc_dogrula(h, istek)
    if d is None:
        return
    oid, fid = d
    g = istek.govde or {}
    try:
        kid = int(g.get("kanal_id") or 0)
    except Exception:
        kid = 0
    if not kid:
        h.hata_yaz(400, "kanal_id zorunlu")
        return
    vardi = akis.AKIS.kanal_kapat(oid, kid)
    kopru_hata = None
    if role.ROLE.ornek_ile(oid) is not None:
        _, kopru_hata = kopruye_sor(oid, "akis_kapat", {"kanal_id": kid}, 6.0)
    h.json_yaz({"basarili": True, "merkez_vardi": bool(vardi),
                "kopru_hata": kopru_hata or ""})


@yol("POST", r"/api/ic/akis_durum", yetki="acik")
def _u_ic_akis_durum(h, istek, oturum):
    """IC UC — bu ornegin acik kanallari (tanilama).

    Merkez tarafi olcumleri (byte sayaclari, son paket zamani) doner;
    kopru tarafi olcumu icin `kopru=1` istenir. Kopru sorgusu ontanimli
    KAPALIDIR cunku her tanilama cagrisinda WSS gidis-donusu eklemek,
    arayuz periyodik olarak sorarsa gereksiz yuk uretir.
    """
    d = _ic_uc_dogrula(h, istek)
    if d is None:
        return
    oid, fid = d
    g = istek.govde or {}
    yanit = {"basarili": True, "kanallar": akis.AKIS.durum(oid)}
    if g.get("kopru"):
        veri, hata = kopruye_sor(oid, "akis_durum", {}, 6.0)
        yanit["kopru"] = (veri or {}).get("kanallar") or []
        yanit["kopru_hata"] = hata or ""
    h.json_yaz(yanit)


@yol("POST", r"/api/ic/kopru_sor", yetki="acik")
def _u_ic_kopru_sor(h, istek, oturum):
    """IC UC — merkezde calisan GCS icin canli koprü sorgusu.

    v2.4.53 Faz 7: `/app/` altindaki GCS ayri bir surectir ve firma
    oturum kurabiyesine sahip degildir; Baglanti Yoneticisi'nde AI ve
    video servis durumlarini gostermek icin bu uctan gecer.

    GUVENLIK — iki katman:

    1. **Gercek TCP esi** 127.0.0.1 / ::1 olmalidir. `istek.ip`
       KULLANILMAZ: o ozellik `X-Forwarded-For` basligini onceler ve
       bu baslik istemci tarafindan UYDURULABILIR. Dogrulama gercek
       soket adresiyle (`h.client_address`) yapilir.
    2. **Paylasilan sir** (`GOKTUNGU_IC_ANAHTAR`). Ayni makinede calisan
       baska bir kullanicinin (ornegin barindirma ortamindaki farkli
       bir hesap) bu uca ulasmasini engeller. Sir tanimli degilse uc
       KAPALIDIR: sessizce acik kalmasi, gizli bir yetki yukseltme
       yolu birakmak olurdu.

    Firma izolasyonu: cagirici `firma_id` bildirmek ZORUNDADIR ve
    ornegin gercekten o firmaya ait oldugu dogrulanir. Boylece GCS'de
    bir kusur olsa bile capraz firma sorgusu yapilamaz.
    """
    try:
        es = h.client_address[0]
    except Exception:
        es = ""
    if es not in ("127.0.0.1", "::1", "localhost"):
        h.hata_yaz(404, "Bulunamadı")
        return
    beklenen = (os.environ.get("GOKTUNGU_IC_ANAHTAR") or "").strip()
    if not beklenen:
        h.hata_yaz(404, "Bulunamadı")
        return
    gelen = (h.headers.get("X-Ic-Anahtar") or "").strip()
    if not hmac.compare_digest(gelen, beklenen):
        h.hata_yaz(403, "İç anahtar geçersiz")
        return
    g = istek.govde or {}
    try:
        oid = int(g.get("ornek_id") or 0)
        fid = int(g.get("firma_id") or 0)
    except Exception:
        h.hata_yaz(400, "ornek_id ve firma_id zorunlu")
        return
    eylem = str(g.get("eylem") or "").strip()
    if not (oid and fid and eylem):
        h.hata_yaz(400, "ornek_id, firma_id ve eylem zorunlu")
        return
    if not re.fullmatch(r"[a-z_]{1,32}", eylem):
        h.hata_yaz(400, "Geçersiz eylem")
        return
    o = db.tek("SELECT firma_id FROM sunucu_ornekleri WHERE ornek_id = %s",
               (oid,))
    if not o or int(o["firma_id"]) != fid:
        h.hata_yaz(404, "Sunucu bulunamadı")
        return
    veri, hata = kopruye_sor(oid, eylem, dict(g.get("veri") or {}),
                             float(g.get("zaman_asimi") or 8.0))
    if hata:
        h.json_yaz({"basarili": False, "hata": hata})
        return
    h.json_yaz({"basarili": True, "veri": veri or {}})


@yol("GET", r"/api/firma/ekip", yetki="firma")
def _u_firma_ekip(h, istek, oturum):
    """Firmanin kullanici listesi + kisi basi ucus ozeti.

    `api.kullanici_liste()` sayfali ve arama odakli oldugu icin panelin
    ekip sayfasi burada AYRI sorgu kullanir: ucus sayisi ve toplam sure
    kullanici bazinda toplanir. Pilot rolu de kendi ekibini gorur, cunku
    bu sayfa kisisel veri degil kurum rehberi niteligindedir; ancak ucus
    sayilari zaten kisi bazlidir, capraz veri sizmaz."""
    h.json_yaz({"kullanicilar": db.sorgu(
        "SELECT k.kullanici_id, k.eposta, k.ad, k.soyad, k.rol, k.durum, "
        "       k.son_giris_ts, k.olusma_ts, "
        "       (SELECT count(*) FROM ucus_kayitlari u "
        "          WHERE u.kullanici_id = k.kullanici_id) AS ucus_sayisi, "
        "       (SELECT coalesce(sum(u.sure_sn), 0) FROM ucus_kayitlari u "
        "          WHERE u.kullanici_id = k.kullanici_id) AS toplam_sure_sn "
        "FROM kullanicilar k WHERE k.firma_id = %s "
        "ORDER BY k.ad, k.soyad, k.eposta",
        (_firma_id(oturum),))})


@yol("GET", r"/api/firma/kurum", yetki="firma")
def _u_firma_kurum(h, istek, oturum):
    """Kurum kunyesi + kullanim ozeti (kota karsilastirmasi icin)."""
    fid = _firma_id(oturum)
    f = db.tek(
        "SELECT firma_id, unvan, kisa_ad, vergi_no, adres, telefon, eposta, "
        "       web, ulke, maks_kullanici, maks_sunucu, abonelik, "
        "       abonelik_bitis, durum, olusma_ts, "
        # v2.4.53 Faz 4: logo YOLU degil VARLIGI dondurulur; dosya adi
        # rastgele belirtec icerir ve sizdirilmasi gerekmez.
        "       (logo_yol IS NOT NULL AND logo_yol <> '') AS logo_var "
        "FROM firmalar WHERE firma_id = %s", (fid,))
    if not f:
        h.hata_yaz(404, "Kurum kaydı bulunamadı")
        return
    o = db.tek(
        "SELECT (SELECT count(*) FROM kullanicilar WHERE firma_id = %s) "
        "         AS kullanici, "
        "(SELECT count(*) FROM sunucu_ornekleri WHERE firma_id = %s "
        "        AND durum = 'etkin') AS sunucu, "
        "(SELECT count(*) FROM dronlar WHERE firma_id = %s) AS dron, "
        "(SELECT count(*) FROM ucus_kayitlari WHERE firma_id = %s) AS ucus, "
        "(SELECT coalesce(sum(sure_sn), 0) FROM ucus_kayitlari "
        "        WHERE firma_id = %s) AS toplam_sure_sn, "
        "(SELECT count(*) FROM video_kayitlari WHERE firma_id = %s "
        "        AND durum = 'hazir') AS video, "
        "(SELECT coalesce(sum(boyut_bayt), 0) FROM video_kayitlari "
        "        WHERE firma_id = %s AND durum = 'hazir') AS video_bayt",
        (fid,) * 7) or {}
    h.json_yaz({"firma": f, "ozet": o})


@yol("GET", r"/api/firma/dronlar", yetki="firma")
def _u_firma_dronlar(h, istek, oturum):
    h.json_yaz({"kayitlar": db.sorgu(
        "SELECT d.dron_id, d.yerel_uid, d.ad, d.arac_turu, d.sysid, "
        "       d.otopilot, d.seri_no, d.durum, d.ilk_gorulme_ts, "
        "       d.son_gorulme_ts, "
        "       (SELECT count(*) FROM ucus_kayitlari u "
        "          WHERE u.dron_id = d.dron_id) AS ucus_sayisi, "
        "       (SELECT max(u.baslangic_ts) FROM ucus_kayitlari u "
        "          WHERE u.dron_id = d.dron_id) AS son_ucus_ts "
        "FROM dronlar d WHERE d.firma_id = %s ORDER BY d.ad",
        (_firma_id(oturum),))})


# ==========================================================================
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
    # KK_APP_VEKIL_XFF_v1: GERCEK istemci adresi ic baglantiya tasinir.
    #
    # Bu cagri ek baslik GECIRMIYORDU; App tarafinda her istemci
    # `127.0.0.1` gorunuyordu. Sonucu iki katliydi: (1) App'te kaba
    # kuvvet korumasi anahtarlanamaz, (2) `giris_log.ip` alani her
    # satirda `127.0.0.1` yaziyor ve saldirganin adresi KAYBOLUYOR.
    #
    # `Origin` de tasinir: App tarafi kaynak denetimi yapiyorsa vekil
    # arkasinda dogru degeri gormeli.
    # KK_TUNEL_XFF_v1: GELEN basligi aktar, kendi es adresini KULLANMA.
    #
    # Bu islev zincirin IKINCI katmanidir ve `soket.remote_address`
    # degeri her zaman `127.0.0.1`'dir (birinci katman yerelden
    # baglanir). Gercek adres birinci katmanda (`_ws_tunel`) yazilan
    # `X-Forwarded-For` basliginda tasinir.
    _bas = {}
    try:
        _istek = getattr(soket, "request", None)
        _h = getattr(_istek, "headers", None) or {}
        for _ad in ("X-Forwarded-For", "X-Real-IP", "Origin", "User-Agent"):
            _d = _h.get(_ad)
            if _d:
                _bas[_ad] = str(_d)
    except Exception:
        pass
    if "X-Forwarded-For" not in _bas:
        # Yedek: baslik yoksa (dogrudan baglanti) gercek es kullanilir.
        try:
            _u = getattr(soket, "remote_address", None)
            if _u and _u[0]:
                _bas["X-Forwarded-For"] = str(_u[0])
        except Exception:
            pass
    try:
        async with websockets.connect(
                hedef, max_size=32 * 1024 * 1024,
                ping_interval=20, ping_timeout=20,
                open_timeout=10, additional_headers=_bas) as ic:

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
            # FAZ18-IS13-GOREV-BEKLE: iptal ISTEGI koymak yetmez. Gorev
            # `await ic.send(...)` icinde bekliyorsa, `async with`
            # bloktan cikildiginda soket kapanir ve gorev sonra
            # kapali sokette uyanip istisna firlatir. Kimse
            # beklemedigi icin asyncio yigin izi basar. Ayni
            # kalip kopru_ajan.py icinde dogru uygulanmis:
            # iptal et VE bekle.
            for g in bekleyen:
                g.cancel()
            if bekleyen:
                # return_exceptions=True sart: CancelledError ve
                # ConnectionClosedError burada YUTULUR, vekil
                # govdesi kendi kapanis akisini surdurur.
                await asyncio.gather(*bekleyen, return_exceptions=True)
    except TypeError as e:
        # ESKI `websockets` surumu `additional_headers` tanimiyor
        # olabilir (sunucuda 17.0.1 olculdu, kapali devre kurulumlarda
        # daha eskisi bulunabilir). Bu durumda baslik AKTARILMADAN
        # yeniden denenir: kaba kuvvet anahtari kotulesir ama ARAYUZ
        # CALISMAYA DEVAM EDER. Sessiz kalmaz, uyari basar.
        print("[APP-WS] additional_headers desteklenmiyor (%s); "
              "baslik aktarilmadan yeniden deneniyor" % e)
        try:
            async with websockets.connect(
                    hedef, max_size=32 * 1024 * 1024,
                    ping_interval=20, ping_timeout=20,
                    open_timeout=10) as ic2:

                async def _ileri2() -> None:
                    async for ham in soket:
                        await ic2.send(ham)

                async def _geri2() -> None:
                    async for ham in ic2:
                        await soket.send(ham)

                g2 = [asyncio.create_task(_ileri2()),
                      asyncio.create_task(_geri2())]
                # FAZ18-IS13B-TAMAMLANAN-TUKET (yedek dal): ana dalla ayni
                # sozlesme.
                tamamlanan2, bekleyen2 = await asyncio.wait(
                    g2, return_when=asyncio.FIRST_COMPLETED)
                _ws_gorev_sonuc_tuket(tamamlanan2, "yedek")
                # FAZ18-IS13-GOREV-BEKLE (yedek dal): ana dalla ayni
                # sozlesme. Eski websockets surumu yolunda da
                # gorevler iptal edilip BEKLENIR.
                for g in bekleyen2:
                    g.cancel()
                if bekleyen2:
                    await asyncio.gather(*bekleyen2,
                                         return_exceptions=True)
        except Exception:
            with __import__("contextlib").suppress(Exception):
                await soket.close(1011, "arayuz sunucusuna ulasilamadi")
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
# IS97 — MERKEZ → APP GUVENLI IC KANAL
# ==========================================================================
# mk_role.KopruOturumu __slots__ kullanır; buradaki sayaç/özet alanları
# oturum nesnesine dinamik nitelik olarak yazılamaz. Durum event-loop içinde
# bu ayrı sözlükte tutulur ve bağlantı kapanırken silinir.
_is97_oturum_durum = {}


def _app_ic_post(yol, veri, zaman_asimi=3.0):
    """App'in loopback iç ucuna paylaşılan sırla küçük JSON POST yapar.

    Hedef adresi yapılandırılabilir olsa da uzak ana makine kesinlikle kabul
    edilmez. Böylece ortam değişkeni hatası hedef metadatasını ağ dışına
    çıkaramaz. Dönüş ``(yanit_sozlugu, hata)`` biçimindedir.
    """
    taban = str(os.environ.get(
        "GOKTUNGU_APP_HEDEF", "http://127.0.0.1:18000") or "").rstrip("/")
    try:
        p = urllib.parse.urlsplit(taban)
    except BaseException as e:
        return None, "App hedefi gecersiz: %s" % e
    if (p.scheme != "http" or p.hostname not in
            ("127.0.0.1", "::1", "localhost")):
        return None, "App ic hedefi yalniz loopback olabilir"
    anahtar = str(os.environ.get("GOKTUNGU_IC_ANAHTAR") or "")
    if len(anahtar) < 24:
        return None, "ic anahtar yapilandirilmamis"
    try:
        govde = json.dumps(veri, ensure_ascii=False,
                           separators=(",", ":")).encode("utf-8")
    except BaseException as e:
        return None, "JSON uretilemedi: %s" % e
    if len(govde) > 512 * 1024:
        return None, "ic kanal govdesi cok buyuk"
    istek = urllib.request.Request(
        taban + "/" + str(yol or "").lstrip("/"), data=govde,
        headers={"Content-Type": "application/json",
                 "X-Ic-Anahtar": anahtar}, method="POST")
    try:
        with urllib.request.urlopen(istek, timeout=float(zaman_asimi)) as y:
            ham = y.read(1024 * 1024)
        sonuc = json.loads(ham or b"{}")
        return (sonuc if isinstance(sonuc, dict) else {}), None
    except urllib.error.HTTPError as e:
        try:
            ayrinti = (e.read(8192) or b"").decode("utf-8", "replace")
        except BaseException:
            ayrinti = ""
        return None, "App HTTP %s: %s" % (e.code, ayrinti[:300])
    except BaseException as e:
        return None, "%s: %s" % (type(e).__name__, e)


async def _kamera_kaynaklari_yolla(o, zorla=False):
    """Doğrulanmış oturumun firma kaynaklarını değiştiğinde köprüye yollar."""
    simdi = time.time()
    durum = _is97_oturum_durum.setdefault(id(o), {})
    if not zorla and simdi - float(durum.get("kaynak_kontrol_ts", 0)) < 10.0:
        return False
    durum["kaynak_kontrol_ts"] = simdi
    veri, hata = await asyncio.to_thread(
        _app_ic_post, "/api/ic/kamera_kaynaklari",
        {"firma_id": int(o.firma_id), "ornek_id": int(o.ornek_id),
         "kurulum_uid": str(o.kurulum_uid or "")}, 3.0)
    if hata or not isinstance(veri, dict) or not veri.get("tamam"):
        son = float(durum.get("kaynak_hata_ts", 0))
        if simdi - son > 30.0:
            print("[IS97] Kamera kaynaklari alinamadi (ornek %s): %s" %
                  (o.ornek_id, hata or (veri or {}).get("hata") or "bilinmiyor"))
            durum["kaynak_hata_ts"] = simdi
        return False
    paket = {
        "tur": "kamera_kaynaklari", "zaman": float(veri.get("zaman") or simdi),
        "lokasyonlar": list(veri.get("lokasyonlar") or [])[:500],
        "dronlar": list(veri.get("dronlar") or [])[:500],
    }
    ozet = hashlib.sha256(json.dumps(
        {"lokasyonlar": paket["lokasyonlar"], "dronlar": paket["dronlar"]},
        ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()
    if not zorla and ozet == durum.get("kaynak_ozet", ""):
        return False
    await o.soket.send(json.dumps(paket, ensure_ascii=False,
                                  separators=(",", ":")))
    durum["kaynak_ozet"] = ozet
    return True


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

    ip = None
    try:
        ip = soket.remote_address[0] if soket.remote_address else None
    except Exception:
        pass
    o = role.KopruOturumu(soket, ip)
    dogrulandi = False
    try:
        async for ham in soket:
            try:
                m = json.loads(ham)
            except Exception:
                continue
            if not isinstance(m, dict):
                continue
            tur = m.get("tur")

            if not dogrulandi:
                if tur != "merhaba":
                    await soket.send(json.dumps(
                        {"tur": "hata", "mesaj": "İlk mesaj merhaba olmalı"}))
                    return
                uid = str(m.get("kurulum_uid") or "")
                gizli = str(m.get("gizli") or "")
                k = db.tek(
                    "SELECT s.ornek_id, s.firma_id, s.ad, s.gizli_ozet, s.durum, "
                    "       f.durum AS firma_durum "
                    "FROM sunucu_ornekleri s "
                    "JOIN firmalar f ON f.firma_id = s.firma_id "
                    "WHERE s.kurulum_uid = %s", (uid,))
                if not k or not role.gizli_dogrula(gizli, k["gizli_ozet"]):
                    await soket.send(json.dumps(
                        {"tur": "hata", "mesaj": "Kurulum kimliği geçersiz"}))
                    return
                if k["durum"] != "etkin" or k["firma_durum"] != "etkin":
                    await soket.send(json.dumps(
                        {"tur": "hata", "mesaj": "Kurulum veya firma etkin değil"}))
                    return
                o.ornek_id = int(k["ornek_id"])
                o.firma_id = int(k["firma_id"])
                o.kurulum_uid = uid
                o.ad = k["ad"]
                o.surum = str(m.get("surum") or "")
                o.platform = str(m.get("platform") or "")
                o.makine_adi = str(m.get("makine_adi") or "")
                if isinstance(m.get("yetenekler"), dict):
                    o.yetenekler = m["yetenekler"]
                o.dron_sayisi = int(m.get("dron_sayisi") or 0)
                # IS47_TEK_OTURUM_v1: ayni kurulum icin canli oturum varsa
                # `ekle` IkinciOturumHatasi firlatir. Bu durumda
                # `dogrulandi` FALSE kalir; `finally` blogu
                # `baglanti_kapandi` CAGIRMAZ ve boylece CANLI
                # oturumun `cevrimici` isareti EZILMEZ.
                try:
                    await role.ROLE.ekle(o)
                except role.IkinciOturumHatasi:
                    print("[ROLE] Ikinci oturum reddedildi: "
                          "%s (ornek %s, %s)"
                          % (o.ad, o.ornek_id, ip))
                    with __import__("contextlib").suppress(Exception):
                        await soket.send(json.dumps(
                            {"tur": "hata", "kod": "zaten_bagli",
                             "mesaj": "Bu kurulum icin merkezde "
                                       "zaten canli bir oturum var"},
                            ensure_ascii=False))
                    return
                role.baglanti_acildi(o)
                dogrulandi = True
                # Akis koprusune GONDERICI kaydi: GCS'den gelen MAVLink
                # komutlari bu cagrilabilir uzerinden bu sokete yazilir.
                # Kayit dogrulamadan SONRA yapilir; aksi halde kimligi
                # dogrulanmamis bir soket komut alabilirdi.
                akis.AKIS.gonderici_ata(
                    o.ornek_id,
                    lambda kid, v64, s=soket: s.send(json.dumps(
                        {"tur": "akis", "kanal_id": int(kid), "veri": v64})))
                await soket.send(json.dumps({
                    "tur": "merhaba_tamam", "kanal": o.kanal,
                    "ornek_id": o.ornek_id, "ad": o.ad,
                    "sunucu_zamani": dt.datetime.now(dt.timezone.utc).isoformat(),
                }, ensure_ascii=False))
                print(f"[ROLE] Kopru baglandi: {o.ad} (ornek {o.ornek_id}, {ip})")
                # IS97: doğrulanmış firma/kurulum bağlamından üretilir;
                # köprünün merhaba gövdesindeki firma iddiasına güvenilmez.
                await _kamera_kaynaklari_yolla(o, zorla=True)
                continue

            if tur == "nabiz":
                role.nabiz_isle(o, m)
                await soket.send(json.dumps({"tur": "nabiz_tamam"}))
                # Kaynak kayıtları/bağlılık değişirse en geç 10 saniyede
                # köprü önbelleğine yenisi ulaşır; değişmediyse veri gitmez.
                await _kamera_kaynaklari_yolla(o)
            elif tur == "yanit":
                role.yanit_isle(o, m)
            elif tur == "ucus":
                uid_, hata = api.ucus_yaz(int(o.firma_id), m.get("veri") or {},
                                          o.ornek_id)
                if uid_ and (m.get("veri") or {}).get("telemetri"):
                    api.telemetri_yaz(uid_, m["veri"]["telemetri"])
                await soket.send(json.dumps(
                    {"tur": "ucus_tamam", "istek_id": m.get("istek_id"),
                     "ucus_id": uid_, "hata": hata}, ensure_ascii=False))
            elif tur == "telemetri":
                ucus_id = db.deger(
                    "SELECT ucus_id FROM ucus_kayitlari WHERE ucus_uid = %s",
                    (m.get("ucus_uid"),))
                adet = api.telemetri_yaz(int(ucus_id), m.get("ornekler") or []) \
                    if ucus_id else 0
                await soket.send(json.dumps(
                    {"tur": "telemetri_tamam", "istek_id": m.get("istek_id"),
                     "adet": adet}))
            elif tur == "video":
                vid, hata = api.video_yaz(int(o.firma_id), m.get("veri") or {},
                                          o.ornek_id)
                await soket.send(json.dumps(
                    {"tur": "video_tamam", "istek_id": m.get("istek_id"),
                     "video_id": vid, "hata": hata}, ensure_ascii=False))
            elif tur == "hedef":
                # IS97: görüntü değil, yalnız sayısal hedef metadatası. Firma,
                # örnek ve kurulum kimliği istemci paketinden değil doğrulanmış
                # WebSocket oturumundan alınır. Yanıt köprüye yazılmaz.
                _yanit, _hata = await asyncio.to_thread(
                    _app_ic_post, "/api/ic/hedef",
                    {"firma_id": int(o.firma_id),
                     "ornek_id": int(o.ornek_id),
                     "kurulum_uid": str(o.kurulum_uid or ""),
                     "kopru_ad": str(o.ad or "")[:160],
                     "paket": m}, 3.0)
                if _hata:
                    _simdi = time.time()
                    _durum = _is97_oturum_durum.setdefault(id(o), {})
                    if _simdi - float(_durum.get("hedef_hata_ts", 0)) > 30.0:
                        print("[IS97] Hedef App'e aktarilamadi (ornek %s): %s" %
                              (o.ornek_id, _hata))
                        _durum["hedef_hata_ts"] = _simdi
            elif tur == "dron_gecmis_kare":
                # IS99: Genel görüntü yasağının dar, açık yöneticili istisnası.
                # Firma/köprü bağlamı istemci iddiasından değil doğrulanmış
                # WebSocket oturumundan damgalanır. App; JPEG, SHA, 1 FPS,
                # dron sahipliği, saklama ve kota kapılarını yeniden uygular.
                _yanit, _hata = await asyncio.to_thread(
                    _app_ic_post, "/api/ic/goruntu_kare",
                    {"firma_id": int(o.firma_id),
                     "ornek_id": int(o.ornek_id),
                     "kurulum_uid": str(o.kurulum_uid or ""),
                     "kopru_ad": str(o.ad or "")[:160],
                     "paket": m}, 5.0)
                if _hata or not (_yanit or {}).get("tamam"):
                    _simdi = time.time()
                    _durum = _is97_oturum_durum.setdefault(id(o), {})
                    if _simdi - float(_durum.get("kare_hata_ts", 0)) > 30.0:
                        print("[IS99] Gecmis karesi App'e aktarilamadi "
                              "(ornek %s): %s" %
                              (o.ornek_id, _hata or
                               (_yanit or {}).get("hata") or "reddedildi"))
                        _durum["kare_hata_ts"] = _simdi
            elif tur == "durum":
                role.nabiz_isle(o, m)
            elif tur == "video_kare":
                # FAZ19-IS60 — CANLI KAMERA KARESI.
                # `akis` daliyla AYNI kalip: veritabanina yazilmaz,
                # gunluge dusmez, yanit uretilmez. Video icin bu daha
                # da onemlidir: 10 fps x N kamera, her kare icin
                # gunluk satiri diski doldurur.
                video.VIDEO.kopruden_geldi(
                    o.ornek_id, m.get("kamera_id") or 0,
                    m.get("veri") or "")
            elif tur == "akis":
                # HAM MAVLINK BYTE. Veritabanina YAZILMAZ ve gunluge
                # DUSMEZ: saniyede ~50 paket gelir, her birini gunluge
                # yazmak diski doldurur ve gercek olaylari gorunmez
                # kilar. Yanit da uretilmez (atesle-unut); yanit
                # beklemek 20 ms araliklarla gelen pakette koprude
                # gecikme biriktirir.
                akis.AKIS.kopruden_geldi(
                    o.ornek_id, m.get("kanal_id") or 0, m.get("veri") or "")
    except Exception as e:
        if not isinstance(e, (asyncio.CancelledError,)):
            adi = type(e).__name__
            if "ConnectionClosed" not in adi:
                print(f"[ROLE] Oturum hatasi: {adi}: {e}")
    finally:
        _is97_oturum_durum.pop(id(o), None)
        if dogrulandi:
            await role.ROLE.cikar(o)
            # Akis kanallari KAPATILIR. Kapatilmazsa GCS var olmayan bir
            # koprue komut gondermeye devam eder ve pilot komutun
            # gittigini sanar. Yalniz bu oturum halen kayitli
            # gonderici ise temizlenir: kopru yeniden baglandiysa yeni
            # oturum kaydi EZILMEMELIDIR.
            with __import__("contextlib").suppress(Exception):
                if role.ROLE.ornek_ile(int(o.ornek_id)) is None:
                    n = akis.AKIS.gonderici_sil(o.ornek_id)
                    if n:
                        print(f"[AKIS] {n} kanal kapatildi (kopru ayrildi: "
                              f"ornek {o.ornek_id})")
                    # FAZ19-IS60: video kanallari da kapatilir. Aksi
                    # halde App, kare gelmeyen bir kanaldan yayin
                    # bekler ve kullanici donmus goruntu gorur.
                    nv = video.VIDEO.ornek_kapat(o.ornek_id)
                    if nv:
                        print(f"[VIDEO] {nv} canli kamera kapatildi "
                              f"(kopru ayrildi: ornek {o.ornek_id})")
            try:
                role.baglanti_kapandi(o, "soket kapandi")
            except Exception:
                pass
            print(f"[ROLE] Kopru ayrildi: {o.ad} (ornek {o.ornek_id})")


async def _nabiz_goktungusu() -> None:
    """Zaman aşımına uğrayan köprüleri düşürür."""
    import time
    while True:
        await asyncio.sleep(30)
        sinir = int(ayar_oku().get("kopru_zaman_asimi_sn", 90))
        for ozet in list(role.ROLE.tumu()):
            o = role.ROLE.uid_ile(ozet["kurulum_uid"])
            if o and (time.time() - o.son_nabiz) > sinir:
                print(f"[ROLE] Nabiz yok, dusuruluyor: {o.ad}")
                with __import__("contextlib").suppress(Exception):
                    await o.soket.close()
        # Terk edilmis akis kanallari: GCS coktuyse `akis_kapat` cagrisi
        # HIC gelmez ve UDP portu sonsuza dek acik kalir. Bu temizlik,
        # uzun caliskan bir merkezde port ve bellek sizintisini onler.
        with __import__("contextlib").suppress(Exception):
            dusen = akis.AKIS.terk_edilenleri_temizle()
            if dusen:
                print(f"[AKIS] {len(dusen)} terk edilmis kanal kapatildi")


# ==========================================================================
# v2.4.71 — SNI ÇOĞULLAMALI TLS BAĞLAMI
# ==========================================================================
# Merkez tek süreçte birden çok alan adı taşır:
#   * goktungu.com + *.goktungu.com  (Sectigo wildcard, birincil)
#   * gozcu.veilox.com.tr            (Let's Encrypt, eski adres)
#
# Önceki kod tek `load_cert_chain` çağrısı yapıyordu; sonuç olarak hangi
# alan adı istenirse istenmesin AYNI sertifika sunuluyordu ve eski adrese
# gelen tarayıcı `ERR_CERT_COMMON_NAME_INVALID` alıyordu. Çözüm SNI:
# istemci el sıkışmada hangi adı istediğini söyler, `sni_callback` o ada
# uyan bağlamı soketle eşler.
#
# NEDEN `sni_callback` ve `set_servername_callback` DEĞİL: Python'da
# `sni_callback` bağlamı doğrudan değiştirmeye izin verir
# (`soket.context = ...`); bu, sertifika seçiminin el sıkışma
# tamamlanmadan yapılmasını sağlar.
#
# DİKKAT: Geri çağrı içinde YÜKSELTİLEN istisna el sıkışmayı sessizce
# düşürür ve hata ayıklaması çok zordur. Bu yüzden gövde tümüyle
# korumalıdır ve başarısızlıkta birincil bağlama düşer.

_TLS_ONBELLEK: dict[str, ssl.SSLContext] = {}
_TLS_KILIT = threading.Lock()


def _ad_uyar_mi(desen: str, ad: str) -> bool:
    """Sertifika adı deseninin istenen ada uyup uymadığını söyler.

    Joker karakter YALNIZCA en soldaki etikette ve TEK etiketi karşılar
    (RFC 6125): `*.goktungu.com` → `app.goktungu.com` uyar,
    `a.b.goktungu.com` UYMAZ, `goktungu.com` UYMAZ.
    """
    desen = (desen or "").strip().lower().rstrip(".")
    ad = (ad or "").strip().lower().rstrip(".")
    if not desen or not ad:
        return False
    if desen == ad:
        return True
    if desen.startswith("*."):
        kok = desen[2:]
        if not ad.endswith("." + kok):
            return False
        return "." not in ad[: -(len(kok) + 1)]
    return False


def _sertifika_adlari(crt_yolu: str) -> list[str]:
    """Sertifikadaki SAN (yoksa CN) adlarını döndürür.

    `ssl._ssl._test_decode_cert` özel bir işlevdir ancak ek bağımlılık
    (cryptography) getirmeden PEM'i çözmenin tek yerleşik yoludur.
    Başarısız olursa boş liste döner; çağıran dosya adına düşer.
    """
    adlar: list[str] = []
    try:
        bilgi = ssl._ssl._test_decode_cert(crt_yolu)  # noqa: SLF001
        for tur, deger in bilgi.get("subjectAltName", ()):
            if tur.lower() == "dns":
                adlar.append(deger)
        if not adlar:
            for demet in bilgi.get("subject", ()):
                for anahtar, deger in demet:
                    if anahtar == "commonName":
                        adlar.append(deger)
    except Exception as e:
        print(f"[TLS] {crt_yolu} adlari okunamadi: {e}")
    return adlar


def tls_baglamlari() -> tuple[ssl.SSLContext | None,
                              list[tuple[list[str], ssl.SSLContext]]]:
    """(birincil bağlam, [(adlar, bağlam), ...]) döndürür.

    Birincil bağlam ayar dosyasındaki `sertifika` girdisidir ve SNI
    göndermeyen istemcilere sunulur. `ek_sertifikalar` listesindeki her
    girdi ayrıca yüklenir.
    """
    a = ayar_oku()
    girdiler: list[dict] = []
    ana = a.get("sertifika") or {}
    if ana.get("crt") and ana.get("key"):
        girdiler.append(dict(ana))
    for ek in (a.get("ek_sertifikalar") or []):
        if isinstance(ek, dict) and ek.get("crt") and ek.get("key"):
            girdiler.append(dict(ek))

    yuklu: list[tuple[list[str], ssl.SSLContext]] = []
    birincil: ssl.SSLContext | None = None
    for g in girdiler:
        crt, key = g["crt"], g["key"]
        if not (os.path.isfile(crt) and os.path.isfile(key)):
            print(f"[TLS] Atlandi (dosya yok): {crt}")
            continue
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            # TLS 1.0/1.1 ve zayif sifreler kapali: SSL Labs A notu ve
            # PCI uyumu icin gerekli. TLS 1.2 tabanı korunur cunku
            # sahadaki Windows 8.1 ve eski Android istemciler 1.3
            # konusamaz.
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.load_cert_chain(crt, key)
        except Exception as e:
            print(f"[TLS] Yuklenemedi {crt}: {e}")
            continue
        adlar = g.get("adlar") or _sertifika_adlari(crt)
        yuklu.append((adlar, ctx))
        if birincil is None:
            birincil = ctx
        print(f"[TLS] Yuklendi: {crt} -> {', '.join(adlar) or '(ad yok)'}")

    if birincil is not None and len(yuklu) > 1:
        def _sni(soket, istenen_ad, _ctx):  # noqa: ANN001, ANN202
            try:
                if not istenen_ad:
                    return None          # birincil bağlamda kal
                for adlar, ctx in yuklu:
                    for d in adlar:
                        if _ad_uyar_mi(d, istenen_ad):
                            soket.context = ctx
                            return None
            except Exception:
                pass                     # sessizce birincile düş
            return None

        for _adlar, ctx in yuklu:
            ctx.sni_callback = _sni

    return birincil, yuklu


def tls_baglam_kur() -> ssl.SSLContext | None:
    """Süreç genelinde tek kez kurulan TLS bağlamını döndürür.

    HTTPS dinleyicisi ve WebSocket dinleyicisi AYNI bağlamı paylaşır;
    böylece sertifika yolu tek yerden yönetilir ve iki dinleyicinin
    farklı sertifika sunması gibi bir tutarsızlık oluşamaz.
    """
    with _TLS_KILIT:
        hazir = _TLS_ONBELLEK.get("birincil")
        if hazir is not None:
            return hazir
        birincil, _ = tls_baglamlari()
        if birincil is not None:
            _TLS_ONBELLEK["birincil"] = birincil
        return birincil


async def _ws_calistir() -> None:
    import websockets

    a = ayar_oku()
    dongu_ata(asyncio.get_running_loop())
    role.bayat_temizle()
    # v2.4.71: sertifika yükleme `tls_baglam_kur()`a taşındı; HTTPS ve
    # WSS artık AYNI SNI çoğullamalı bağlamı paylaşır.
    ssl_ctx = tls_baglam_kur()
    if ssl_ctx is not None:
        print(f"[WS] Guvenli WebSocket: wss://{a['dinleme']}:{a['ws_port']}")
    else:
        print(f"[WS] Sertifika yok; sifresiz: ws://{a['dinleme']}:{a['ws_port']}")
    asyncio.ensure_future(_nabiz_goktungusu())
    # İkİ DİNLEYİCİ:
    #  1) `ws_port` (9443) — TLS'li, dışa açık. Geriye uyumluluk için
    #     korunur: sahadaki v2.4.52 ve öncesi köprüler bu adresi bilir.
    #  2) `ws_duz_port` (9080) — şifresiz, YALNIZCA 127.0.0.1. 443'teki
    #     HTTP sunucusunun WS tüneli buraya bağlanır. TLS dış bacakta
    #     zaten yapıldığı için iç bacakta ikinci kez kurulmaz.
    duz_port = int(a.get("ws_duz_port", 9080))
    print(f"[WS] Yerel duz dinleyici (443 tuneli icin): "
          f"ws://127.0.0.1:{duz_port}")
    async with websockets.serve(_ws_isle, a["dinleme"], int(a["ws_port"]),
                                ssl=ssl_ctx, max_size=32 * 1024 * 1024,
                                ping_interval=20, ping_timeout=20), \
            websockets.serve(_ws_isle, "127.0.0.1", duz_port,
                             max_size=32 * 1024 * 1024,
                             ping_interval=20, ping_timeout=20):
        await asyncio.Future()


def ws_iplikte_baslat() -> threading.Thread:
    def kos() -> None:
        try:
            asyncio.run(_ws_calistir())
        except Exception as e:
            print(f"[WS] Durdu: {e}")
    t = threading.Thread(target=kos, name="role-ws", daemon=True)
    t.start()
    return t


# ==========================================================================
# HTTP dinleyicileri
# ==========================================================================
class MerkezHTTPSunucu(ThreadingHTTPServer):
    """Kuyrugu buyutulmus, TLS baglami tasiyabilen HTTP sunucusu."""

    daemon_threads = True
    request_queue_size = 128   # varsayilan 5; es zamanli baglantida yetmiyor
    tls_baglam: ssl.SSLContext | None = None


def http_baslat(port: int, tls: bool = False) -> ThreadingHTTPServer | None:
    a = ayar_oku()
    try:
        sunucu = MerkezHTTPSunucu((a["dinleme"], port), MerkezIsleyici)
    except OSError as e:
        print(f"[HTTP] Port {port} acilamadi: {e}")
        return None
    sunucu.daemon_threads = True
    sunucu.tls_baglam = None
    if tls:
        ctx = tls_baglam_kur()
        if ctx is None:
            print(f"[HTTPS] Sertifika bulunamadi; port {port} kapatildi")
            sunucu.server_close()
            return None
        # Dinleme soketi SARMALANMAZ: el sikisma accept() icinde yapilirsa
        # kabul is parcacigi tikanir ve uzak istemcilerde gecikme birikir.
        # Sarmalama MerkezIsleyici.setup() icinde, istek is parcaciginda.
        sunucu.tls_baglam = ctx
    ad = "HTTPS" if tls else "HTTP"
    print(f"[{ad}] Dinleniyor: {'https' if tls else 'http'}://"
          f"{a['dinleme']}:{port}")
    threading.Thread(target=sunucu.serve_forever, name=f"http-{port}",
                     daemon=True).start()
    return sunucu


# ======================================================================
# v2.4.53 Faz 4 — KURUM LOGOSU
# ======================================================================
# Logo, kurum /company/ altinda kayit olurken yuklenir ve merkezde
# saklanir. /app/ altindaki GOKTUNGU arayuzu giris yaptiginda kendi
# kurumunun logosuyla acilir; ucus raporu antedi de ayni logoyu
# kullanir. Boylece kullanici hangi bilgisayardan girerse girsin
# kurumsal kimlik korunur.
LOGO_DIZIN = os.path.join(VERI_KOKU, "varlik", "logo")
LOGO_MAKS_BAYT = 2 * 1024 * 1024          # 2 MB
LOGO_TURLERI = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}


def logo_coz(veri_url):
    """`data:` URL'sini (tur, baytlar) ikilisine cozer.

    Donus: (uzanti, baytlar, hata). Hata varsa ilk iki deger None.

    NEDEN data URL: kayit formu tek JSON istegi gonderir; multipart
    kullanmak icin hem istemci hem sunucu tarafinda ayri bir ayristirici
    gerekirdi. Logo boyutu 2 MB ile sinirli oldugu icin base64
    genislemesi (%33) kabul edilebilir.
    """
    s = str(veri_url or "").strip()
    if not s:
        return None, None, None                # logo istege bagli
    if not s.startswith("data:"):
        return None, None, "Logo bicimi taninmadi"
    basl, _, govde64 = s.partition(",")
    if not govde64:
        return None, None, "Logo verisi bos"
    tur = basl[5:].split(";")[0].strip().lower()
    uzanti = LOGO_TURLERI.get(tur)
    if not uzanti:
        return None, None, ("Desteklenmeyen logo turu: %s "
                            "(PNG, JPEG, WEBP veya SVG kullanin)" % tur)
    if "base64" not in basl:
        return None, None, "Logo base64 kodlanmis olmali"
    import base64 as _b64
    try:
        baytlar = base64.b64decode(govde64, validate=False)
    except Exception:
        return None, None, "Logo verisi cozulemedi"
    if not baytlar:
        return None, None, "Logo verisi bos"
    if len(baytlar) > LOGO_MAKS_BAYT:
        return None, None, ("Logo cok buyuk (%.1f MB); en fazla 2 MB"
                            % (len(baytlar) / 1048576.0))
    # Ikili imza denetimi: uzanti ile gercek icerik uyusmuyorsa dosya
    # sunucuda yanlis Content-Type ile sunulur.
    if uzanti == ".png" and not baytlar.startswith(b"\x89PNG"):
        return None, None, "Dosya gercek bir PNG degil"
    if uzanti == ".jpg" and not baytlar.startswith(b"\xff\xd8"):
        return None, None, "Dosya gercek bir JPEG degil"
    if uzanti == ".webp" and baytlar[8:12] != b"WEBP":
        return None, None, "Dosya gercek bir WEBP degil"
    if uzanti == ".svg":
        try:
            bas = baytlar[:400].decode("utf-8", "ignore").lower()
        except Exception:
            bas = ""
        if "<svg" not in bas:
            return None, None, "Dosya gercek bir SVG degil"
        # SVG icinde betik calistirilabilir; kurum logosunda buna
        # gerek yoktur ve saklanan dosya baska kullanicilara sunulur.
        if "<script" in baytlar.decode("utf-8", "ignore").lower():
            return None, None, "SVG icinde betik bulundu; kabul edilmez"
    return uzanti, baytlar, None


def logo_yaz(firma_id, veri_url):
    """Logoyu diske yazar ve `firmalar.logo_yol` degerini gunceller.

    Donus: (logo_yol|None, hata|None). Logo bos ise (None, None).
    """
    uzanti, baytlar, hata = logo_coz(veri_url)
    if hata:
        return None, hata
    if not baytlar:
        return None, None
    import secrets as _sec
    os.makedirs(LOGO_DIZIN, exist_ok=True)
    # Rastgele belirtec: firma_id tahmin edilerek baska kurumun logosu
    # dogrudan /varlik/ yolundan cekilemesin.
    ad = "firma_%d_%s%s" % (int(firma_id), _sec.token_hex(8), uzanti)
    tam = os.path.join(LOGO_DIZIN, ad)
    try:
        with open(tam, "wb") as f:
            f.write(baytlar)
    except OSError as e:
        return None, "Logo kaydedilemedi: %s" % e
    goreli = "logo/" + ad
    # Eski logo dosyasi varsa silinir; aksi halde her guncellemede
    # disk sisirilir.
    try:
        eski = db.deger(
            "SELECT logo_yol FROM firmalar WHERE firma_id = %s",
            (int(firma_id),))
        if eski and str(eski) != goreli:
            e_tam = os.path.join(VERI_KOKU, "varlik", str(eski))
            if os.path.isfile(e_tam) and os.path.realpath(
                    e_tam).startswith(os.path.realpath(LOGO_DIZIN)):
                os.remove(e_tam)
    except Exception:
        pass
    try:
        db.calistir(
            "UPDATE firmalar SET logo_yol = %s, guncel_ts = now()"
            " WHERE firma_id = %s", (goreli, int(firma_id)))
    except Exception as e:
        return None, "Logo yolu yazilamadi: %s" % e
    return goreli, None


@yol("GET", r"/api/genel/firma_logo", yetki="acik")
def _u_firma_logo(h, istek, oturum):
    """Kurum logosunu sunar (kimlik gerekmez).

    NEDEN KIMLIKSIZ: logo, giris ekraninda ve ucus raporu antedinde
    gorunur; her ikisi de oturum acilmadan once cizilebilir. Logo
    hassas veri DEGILDIR (kurumun web sitesinde de yayindadir).
    """
    try:
        fid = int(istek.sorgu.get("firma_id") or 0)
    except (TypeError, ValueError):
        fid = 0
    if not fid:
        h.hata_yaz(400, "firma_id zorunlu")
        return
    goreli = db.deger(
        "SELECT logo_yol FROM firmalar WHERE firma_id = %s", (fid,))
    if not goreli:
        h.hata_yaz(404, "Logo yok")
        return
    tam = os.path.normpath(os.path.join(VERI_KOKU, "varlik", str(goreli)))
    if not os.path.realpath(tam).startswith(
            os.path.realpath(os.path.join(VERI_KOKU, "varlik"))):
        h.hata_yaz(403, "Erisim engellendi")
        return
    if not os.path.isfile(tam):
        h.hata_yaz(404, "Logo dosyasi bulunamadi")
        return
    tur = mimetypes.guess_type(tam)[0] or "application/octet-stream"
    with open(tam, "rb") as f:
        icerik = f.read()
    h.send_response(200)
    h.send_header("Content-Type", tur)
    h.send_header("Content-Length", str(len(icerik)))
    # Dosya adi rastgele belirtec icerdigi icin degisince URL de degisir;
    # bu yuzden uzun onbellek guvenlidir.
    h.send_header("Cache-Control", "public, max-age=86400")
    h.end_headers()
    try:
        h.wfile.write(icerik)
    except BrokenPipeError:
        pass


@yol("POST", r"/api/firma/logo", yetki="firma")
def _u_firma_logo_yaz(h, istek, oturum):
    """Oturum acmis kurum yoneticisi logoyu degistirir."""
    if str(oturum.get("rol")) not in ("firma_yonetici", "yonetici",
                                      "admin"):
        h.json_yaz({"hata": "Bu islem icin yonetici yetkisi gerekir"}, 403)
        return
    fid = int(oturum.get("firma_id") or 0)
    if not fid:
        h.json_yaz({"hata": "Kurum bulunamadi"}, 400)
        return
    g = istek.govde or {}
    goreli, hata = logo_yaz(fid, g.get("logo"))
    if hata:
        h.json_yaz({"hata": hata}, 400)
        return
    if not goreli:
        h.json_yaz({"hata": "Logo verisi gonderilmedi"}, 400)
        return
    kimlik.denetim(None, "firma_logo", "firma", str(fid),
                   {"logo_yol": goreli}, istek.ip)
    h.json_yaz({"tamam": True,
                "logo_url": "/api/genel/firma_logo?firma_id=%d" % fid})


# ==========================================================================
# === ABONELIK VE LISANS UCLARI (v2.4.65) ===
# ==========================================================================
# Bu bolumun tamami 2026-08-15'te abonelik/faturalandirma katmani icin
# eklendi. Yetki kararlari YALNIZ `mk_yetki` modulunden sorulur; burada
# kopya mantik YOKTUR.


# -------------------------------------------------------------- genel: fiyat
@yol("GET", r"/api/genel/fiyatlar", yetki="acik")
def _u_genel_fiyatlar(h, istek, oturum):
    """Tanitim sayfasinin ve kurumsal panelin okudugu fiyat listesi.

    Fiyatlar `mk_yetki.KALEMLER` tek kaynagindan TURETILIR; arayuze
    elle yazilmaz. Aksi halde aylik fiyat degistiginde tanitim sayfasi
    sessizce eskir.
    """
    # FIYAT KAYNAGI: `paketler` tablosu (mk_paket). `mk_yetki.KALEMLER`
    # artik yalnizca TOHUM veridir, calisma aninda okunmaz.
    #
    # `kalemler` ALAN ADI KORUNUR — arayuz onu okuyor:
    #   merkez/web/admin/uygulama.js:530    → `.kalemler`
    #   merkez/web/company/uygulama.js:1369 → `ab.kalemler`
    # Alan adini degistirmek iki paneli birden bozardi.
    try:
        liste = paket.fiyat_listesi()
    except Exception as e:
        h.hata_yaz(500, "Fiyat listesi okunamadi: %s" % e)
        return
    h.json_yaz({
        "kalemler": liste,
        "paketler": liste,          # yeni ad (esanlamli)
        "yillik_indirim": paket.YILLIK_INDIRIM,
        "taban_pilot": yetki.TABAN_PILOT_KOLTUK,
        "para": "TRY",              # yurt ici birincil
        "para_birimleri": ["TRY", "USD"],
        "tahsilat": _TAHSILAT_KUNYE,
        "vkn": "6290873411",
        "saglayici": "iyzico",
        "odeme_acik": iyzico.yapilandirilmis_mi(),
        "tamam": True,
    })


# ------------------------------------------------------ genel: uyelik talebi
@yol("POST", r"/api/genel/uyelik_talebi", yetki="acik")
def _u_genel_uyelik_talebi(h, istek, oturum):
    """Tanitim sayfasindan gelen on talep. Kimlik ISTEMEZ.

    Sirket henuz kayitli olmayabilir; bu yuzden `firma_id` bos
    gecilebilir ve iletisim bilgisi zorunludur.
    """
    g = istek.govde or {}
    eposta = (g.get("iletisim_eposta") or "").strip()
    if "@" not in eposta:
        h.hata_yaz(400, "Gecerli bir e-posta gerekli")
        return
    kalem = (g.get("kalem") or "").strip()
    tid, hata = yetki.talep_olustur(
        None, kalem, int(g.get("adet") or 1),
        (g.get("donem") or "aylik").strip(),
        (g.get("iletisim_ad") or "").strip(), eposta,
        (g.get("iletisim_tel") or "").strip(),
        (g.get("mesaj") or "").strip())
    if hata:
        h.hata_yaz(400, hata)
        return
    h.json_yaz({"talep_id": tid, "durum": "bekliyor"}, 201)


# ------------------------------------------------------------- firma: ozet
@yol("GET", r"/api/firma/abonelik", yetki="firma")
def _u_firma_abonelik(h, istek, oturum):
    """Sirketin abonelik durumu: koltuk kullanimi, ozellikler, kalemler."""
    fid = _firma_id(oturum)
    y = yetki.firma_yetkileri(fid)
    if not y:
        h.hata_yaz(404, "Firma bulunamadi")
        return
    # GELIR MODELI v2: firma_id gecirilir -- aksi halde
    # `fiyat_listesi()` iskonto hesaplamaz ve kuruma ozel iskonto
    # kurumsal panelde GORUNMEZ (musteri ham fiyati gorur, odeme
    # ekraninda farkli tutar cikar -> guven kaybi).
    pb = (istek.sorgu.get("para") or "").strip().upper()
    if pb not in ("TRY", "USD"):
        pb = None
    h.json_yaz({
        "yetkiler": y,
        "kalemler": yetki.kalem_listesi(fid),
        "talepler": yetki.talep_listesi(firma_id=fid),
        "fiyatlar": yetki.fiyat_listesi(firma_id=fid, para=pb),
        "yillik_indirim": yetki.YILLIK_INDIRIM,
        "tahsilat": _TAHSILAT_KUNYE,
    })


@yol("POST", r"/api/firma/uyelik_talebi", yetki="firma_yonetici")
def _u_firma_uyelik_talebi(h, istek, oturum):
    """Sirket yoneticisinin panelden olusturdugu abonelik talebi."""
    if oturum.get("rol") != "firma_yonetici":
        h.hata_yaz(403, "Bu islem icin firma yoneticisi olmalisiniz")
        return
    g = istek.govde or {}
    tid, hata = yetki.talep_olustur(
        _firma_id(oturum), (g.get("kalem") or "").strip(),
        int(g.get("adet") or 1), (g.get("donem") or "aylik").strip(),
        (g.get("iletisim_ad") or oturum.get("ad") or "").strip(),
        (g.get("iletisim_eposta") or oturum.get("eposta") or "").strip(),
        (g.get("iletisim_tel") or "").strip(),
        (g.get("mesaj") or "").strip())
    if hata:
        h.hata_yaz(400, hata)
        return
    h.json_yaz({"talep_id": tid, "durum": "bekliyor"}, 201)


# --------------------------------------------- firma: uyelik (ekip) yonetimi
# GCS'ten KALDIRILAN yetenegin yeni ve TEK adresi. Kullanici acikca
# "tum uyelik surecleri kurumsal panelden sirket yoneticisi tarafindan
# yapilsin" dedi.
@yol("POST", r"/api/firma/ekip", yetki="firma_yonetici")
def _u_firma_ekip_ekle(h, istek, oturum):
    if oturum.get("rol") != "firma_yonetici":
        h.hata_yaz(403, "Bu islem icin firma yoneticisi olmalisiniz")
        return
    g = dict(istek.govde or {})
    # Firma KENDI firmasina ekler; govdeden gelen firma_id yok sayilir,
    # aksi halde bir sirket baska sirkete kullanici ekleyebilirdi.
    g["firma_id"] = _firma_id(oturum)
    rol = (g.get("rol") or "pilot").strip()
    if rol not in ("pilot", "gozlemci", "firma_yonetici"):
        h.hata_yaz(400, "Gecersiz rol: %s" % rol)
        return
    g["rol"] = rol
    kid, hata = api.kullanici_ekle(g)
    if hata:
        # Koltuk dolulugu 409 ile bildirilir; arayuz bunu "talep olustur"
        # yonlendirmesine cevirir.
        h.hata_yaz(409 if "koltu" in hata.lower() else 400, hata)
        return
    h.json_yaz({"kullanici_id": kid}, 201)


@yol("PUT", r"/api/firma/ekip/(\d+)", yetki="firma_yonetici")
def _u_firma_ekip_guncelle(h, istek, oturum, kid):
    if oturum.get("rol") != "firma_yonetici":
        h.hata_yaz(403, "Bu islem icin firma yoneticisi olmalisiniz")
        return
    fid = _firma_id(oturum)
    k = db.tek("SELECT firma_id, rol FROM kullanicilar "
               "WHERE kullanici_id = %s", (int(kid),))
    if not k or int(k["firma_id"]) != fid:
        h.hata_yaz(404, "Kullanici bulunamadi")
        return
    g = dict(istek.govde or {})
    for yasak in ("firma_id", "kullanici_id"):
        g.pop(yasak, None)
    if g.get("rol") and g["rol"] not in ("pilot", "gozlemci",
                                         "firma_yonetici"):
        h.hata_yaz(400, "Gecersiz rol: %s" % g["rol"])
        return
    # Son firma yoneticisinin rolu dusurulemez / pasife alinamaz:
    # aksi halde sirket kendi panelinden tamamen kilitlenir.
    if k["rol"] == "firma_yonetici" and (
            (g.get("rol") and g["rol"] != "firma_yonetici")
            or (g.get("durum") and g["durum"] != "etkin")):
        kalan = db.deger(
            "SELECT count(*) FROM kullanicilar WHERE firma_id = %s "
            "AND rol = 'firma_yonetici' AND durum = 'etkin' "
            "AND kullanici_id <> %s", (fid, int(kid)))
        if not int(kalan or 0):
            h.hata_yaz(409, "Son firma yoneticisi devre disi birakilamaz")
            return
    tamam, hata = api.kullanici_guncelle(int(kid), g)
    if not tamam:
        h.hata_yaz(409 if "koltu" in (hata or "").lower() else 400,
                   hata or "Guncellenemedi")
        return
    h.json_yaz({"tamam": True})


@yol("DELETE", r"/api/firma/ekip/(\d+)", yetki="firma_yonetici")
def _u_firma_ekip_sil(h, istek, oturum, kid):
    if oturum.get("rol") != "firma_yonetici":
        h.hata_yaz(403, "Bu islem icin firma yoneticisi olmalisiniz")
        return
    fid = _firma_id(oturum)
    k = db.tek("SELECT firma_id, rol FROM kullanicilar "
               "WHERE kullanici_id = %s", (int(kid),))
    if not k or int(k["firma_id"]) != fid:
        h.hata_yaz(404, "Kullanici bulunamadi")
        return
    if int(kid) == int(oturum["kullanici_id"]):
        h.hata_yaz(409, "Kendi hesabinizi silemezsiniz")
        return
    if k["rol"] == "firma_yonetici":
        kalan = db.deger(
            "SELECT count(*) FROM kullanicilar WHERE firma_id = %s "
            "AND rol = 'firma_yonetici' AND durum = 'etkin' "
            "AND kullanici_id <> %s", (fid, int(kid)))
        if not int(kalan or 0):
            h.hata_yaz(409, "Son firma yoneticisi silinemez")
            return
    tamam, hata = api.kullanici_sil(int(kid))
    if not tamam:
        h.hata_yaz(400, hata or "Silinemedi")
        return
    h.json_yaz({"tamam": True})


# ------------------------------------------- firma: Merkez Uygulama indirme
# =====================================================================
#  CANLI APP SURUMU  [IS52-APP-SURUM-V1]
#
#  NEDEN SUNUCU TARAFINDA OKUNUYOR
#  -------------------------------
#  Indirme sayfasi paket surumunu canli App surumuyle karsilastirmali.
#  Ilk tasarim tarayicidan `https://app.goktungu.com/js/surum.js`
#  cekmekti; OLCUM BU TASARIMI CURUTTU: App sunucusu CORS basligi
#  dondurmuyor ve gercek Chromium ile yapilan denemede istek
#  "Failed to fetch" ile ENGELLENDI. App sunucusuna genel CORS acmak
#  gereksiz saldiri yuzeyi olusturacagi icin tercih edilmedi.
#
#  Merkez ile App AYNI makinede calistigi icin surum dosyadan okunur.
#  Dosya yoksa (App ayri makinede kurulu, kapali devre kurulum vb.)
#  None doner ve arayuz "bilinmiyor" der; sessizce "guncel" varsaymaz.
#
#  ONBELLEK: dosya her istekte okunmaz; degisme zamani (mtime)
#  izlenir. Boylece App guncellendiginde deger kendiliginden tazelenir,
#  ama her indirme sayfasi acilisinda disk okumasi yapilmaz.
# =====================================================================
_APP_SURUM_YOL = os.environ.get(
    "GOKTUNGU_APP_SURUM_YOL", "/opt/goktungu/app/js/surum.js")
_app_surum_onbellek = {"mtime": None, "deger": None}


def _canli_app_surumu():
    """`js/surum.js` icindeki `GCS_SURUM` degerini dondurur; yoksa None."""
    try:
        mt = os.path.getmtime(_APP_SURUM_YOL)
    except BaseException:
        return None
    if _app_surum_onbellek["mtime"] == mt:
        return _app_surum_onbellek["deger"]
    deger = None
    try:
        with open(_APP_SURUM_YOL, "r", encoding="utf-8") as f:
            # Dosyanin tamami okunmaz; surum satiri en baslarda.
            bas = f.read(4096)
        e = re.search(r'GCS_SURUM\s*=\s*"([0-9]+(?:\.[0-9]+)*)"', bas)
        if e:
            deger = e.group(1)
    except BaseException:
        deger = None
    _app_surum_onbellek["mtime"] = mt
    _app_surum_onbellek["deger"] = deger
    return deger

@yol("GET", r"/api/firma/merkez_paketler", yetki="firma")
def _u_firma_merkez_paketler(h, istek, oturum):
    """Lisansli sirketin indirebilecegi Merkez Uygulama paketleri.

    Lisans yoksa 403 doner ve paket listesi HIC uretilmez.
    """
    fid = _firma_id(oturum)
    y = yetki.firma_yetkileri(fid)
    if not y.get("merkez_lisans"):
        h.hata_yaz(403, "Merkez Uygulama lisansiniz bulunmuyor")
        return
    kayitlar = [k for k in depo.liste("gcs", "kararli", etkin_yalniz=True)
                if k.get("dosya_var")]
    for k in kayitlar:
        k.pop("imza", None)
    h.json_yaz({"kayitlar": kayitlar,
                # Canli App surumu; paket geride mi diye
                # istemci bunu kendi paketleriyle karsilastirir.
                "app_guncel": _canli_app_surumu(),
                "lisans_uid": (db.deger(
                    "SELECT lisans_uid FROM merkez_lisanslari "
                    "WHERE firma_id = %s AND iptal_ts IS NULL "
                    "ORDER BY olusma_ts DESC LIMIT 1", (fid,)) or "")})


@yol("GET", r"/api/firma/merkez_lisans", yetki="firma_yonetici")
def _u_firma_merkez_lisans(h, istek, oturum):
    """Sirkete ozel imzali lisans belgesini uretir ve dondurur.

    Bu belge Merkez Uygulama kurulumuna yerlestirilir. Uygulama KAPALI
    DEVRE calisabildigi icin lisansi cevrimici dogrulayamaz; imzayi
    gomulu acik anahtarla dogrular.
    """
    if oturum.get("rol") != "firma_yonetici":
        h.hata_yaz(403, "Bu islem icin firma yoneticisi olmalisiniz")
        return
    lisans, hata = yetki.lisans_uret(_firma_id(oturum))
    if hata:
        h.hata_yaz(403, hata)
        return
    h.json_yaz({"lisans": lisans["govde"], "imza": lisans["imza"],
                "acik_anahtar": depo.acik_anahtar_b64()})


@yol("GET", r"/api/firma/merkez_kullanicilar", yetki="firma_yonetici")
def _u_firma_merkez_kullanicilar(h, istek, oturum):
    """Merkez Uygulama kurulumu icin firma kullanici listesi.

    OLCULEN KUSUR (2026-08-16) — NEDEN BU UC VAR
    --------------------------------------------
    Merkez Uygulama satin alan firma kurulumu tamamladiginda, yerel
    `kullanicilar` tablosu BOS kaliyordu. Bu durumda GOKTUNGU'nun
    `kullanicilar.py::_ilk_yonetici_guvence()` yordami kaynak koda
    GOMULU bir hesap yaratiyordu (`gokkubbe2026`). Sonuc: firmanin
    /company/ panelinde tanimladigi sifre GECERSIZ kaliyor, buna
    karsilik her kurulumda AYNI bilinen sifre gecerli oluyordu.

    Bu uc, kurulumun merkezdeki gercek kullanici listesini bir kez
    cekip yerel tabloya yazmasini saglar. Boylece:
      - merkezde tanimlanan sifre Merkez Uygulama'da da gecerli olur
      - gomulu varsayilan hesaba HIC gerek kalmaz
      - esitleme bir kez yapilir, sonrasinda KAPALI DEVRE calisir
        (kullanicinin sarti; surekli merkez baglantisi gerekmez)

    NEDEN SIFRE OZETI GONDERILIYOR
    ------------------------------
    Duz sifre merkezde de saklanmaz; yalniz `pbkdf2_sha256$...` ozeti
    vardir. Ozet oldugu gibi tasinir ve GOKTUNGU tarafinda
    `veritabani.sifre_dogrula()` bu bicimi tanir. Ozet tasimak duz
    sifre tasimaktan guvenlidir; ayrica alternatifi (kullanicilarin
    sifresini yeniden belirlemesi) kullanici istegine aykiridir.

    UC KAPI (hassas veri dondurdugu icin)
    -------------------------------------
      1. Gecerli firma oturumu (`yetki="firma"`)
      2. `firma_yonetici` rolu
      3. `merkez_lisans` yetkisi (5.000 USD urunu satin almis olmak)

    Firma yoneticisi zaten kendi kullanicilarinin sahibidir; bu uc
    baska firmanin verisine ERISMEZ (sorgu `firma_id` ile sinirli).
    """
    if oturum.get("rol") != "firma_yonetici":
        h.hata_yaz(403, "Bu islem icin firma yoneticisi olmalisiniz")
        return
    fid = _firma_id(oturum)
    y = yetki.firma_yetkileri(fid)
    if not y.get("merkez_lisans"):
        h.hata_yaz(403, "Merkez Uygulama lisansiniz bulunmuyor")
        return
    # OLCULDU: `kullanicilar` tablosunda `unvan` kolonu YOKTUR.
    # Gercek kolonlar: kullanici_id firma_id eposta sifre_ozet ad soyad
    # rol durum telefon pilot_lisans avatar_yol son_giris_ts ...
    satirlar = db.sorgu(
        "SELECT eposta, ad, soyad, rol, sifre_ozet, durum, "
        "       pilot_lisans, telefon "
        "  FROM kullanicilar WHERE firma_id = %s ORDER BY kullanici_id",
        (fid,))
    liste = []
    for k in satirlar:
        liste.append({
            "eposta": k["eposta"],
            # GOKTUNGU tek alanda ad_soyad tutar; merkez ad/soyad ayrik.
            "ad_soyad": ("%s %s" % (k["ad"] or "", k["soyad"] or "")).strip(),
            "unvan": k["pilot_lisans"] or "",
            "telefon": k["telefon"] or "",
            "rol": k["rol"],
            "sifre_ozet": k["sifre_ozet"],
            "aktif": 1 if k["durum"] == "etkin" else 0,
        })
    h.json_yaz({"firma_id": fid, "kullanicilar": liste,
                "sayi": len(liste)})


@yol("GET", r"/api/firma/merkez_indir", yetki="firma")
def _u_firma_merkez_indir(h, istek, oturum):
    """Lisans denetimli Merkez Uygulama indirmesi.

    NEDEN AYRI UC: `/indir/` yolu statik dosya sunucusudur ve KIMLIK
    ISTEMEZ. `gcs` urununun yalnizca tanitim katalogundan gizlenmesi
    gercek bir kilit degildir; dosya adini bilen herkes 5.000 USD'lik
    urunu indirebilirdi. Bu uc oturumu ve lisansi dogrular, indirmeyi
    sayar, sonra dosyayi akitir.
    """
    fid = _firma_id(oturum)
    y = yetki.firma_yetkileri(fid)
    if not y.get("merkez_lisans"):
        h.hata_yaz(403, "Merkez Uygulama lisansiniz bulunmuyor")
        return
    surum = (istek.sorgu.get("surum") or "").strip()
    dosya = (istek.sorgu.get("dosya") or "").strip()
    if not surum or not dosya:
        h.hata_yaz(400, "surum ve dosya zorunlu")
        return
    # Dizin gezinme korumasi: dosya adinda ayirici olamaz.
    if "/" in dosya or "\\" in dosya or ".." in dosya:
        h.hata_yaz(400, "Gecersiz dosya adi")
        return
    hedef = depo.indirme_coz("gcs", surum, dosya)
    if not hedef or not os.path.isfile(hedef):
        h.hata_yaz(404, "Paket bulunamadi")
        return
    db.calistir(
        "UPDATE merkez_lisanslari SET indirme_sayisi = indirme_sayisi + 1, "
        "  son_indirme_ts = now() WHERE firma_id = %s AND iptal_ts IS NULL",
        (fid,))
    h.dosya_akit(hedef, dosya)


# ----------------------------------------- istemci: otomatik guncelleme paketi
# IS-2521-GUNCELLEME (2026-09-12): Kurulu Merkez (`gcs`) ve Kopru
# (`kopru`/`video`) istemcilerindeki `guncelleme.py::_paket_indir` bu uca
# POST eder. OLCULEN KUSUR: uc sunucuda HIC YOKTU (404); istemcideki
# "Indir ve dogrula" her kosulda basarisiz oluyordu.
#
# Kimlik tarayici oturumu DEGILDIR (servis olarak calisan istemcinin
# oturumu yoktur):
#   * gcs         -> kurulumdaki imzali `merkez_lisans.json`. Imza bu
#                    sunucunun anahtariyla dogrulanir, lisans_uid bu
#                    firmaya verilmis olmali, firma BUGUN etkin ve
#                    `merkez_lisans` sahibi olmali, bakim kapsami surmeli.
#                    Yetki degisimiyle tazelenmis (iptal_ts dolu) eski UID
#                    KABUL edilir: kapali devre kurulum lisansini yeniden
#                    indirmemis olabilir; asil hak firmanin guncel yetkisidir.
#   * kopru/video -> merkezce verilen `kurulum_uid` + `gizli` (ucretsiz
#                    urunler; bakim kapisi uygulanmaz).
# Yalniz katalogda ETKIN ve urun/surum/platform/dosya ile birebir eslesen
# kayit akitilir. Kaba kuvvet korumasi: mk_kaba_kuvvet.KORUNAN_UCLAR.
_GUNCELLEME_PAKET_URUNLERI = ("gcs", "kopru", "video")


@yol("POST", r"/api/istemci/guncelleme_paket", yetki="acik")
def _u_istemci_guncelleme_paket(h, istek, oturum):
    g = istek.govde if isinstance(istek.govde, dict) else {}
    urun = str(g.get("urun") or "").strip().lower()
    surum = str(g.get("surum") or "").strip()
    platform = str(g.get("platform") or "").strip().lower()
    dosya = str(g.get("dosya") or "").strip()
    if (urun not in _GUNCELLEME_PAKET_URUNLERI or not surum
            or not platform or not dosya):
        h.hata_yaz(400, "urun, surum, platform ve dosya zorunlu")
        return
    if "/" in dosya or "\\" in dosya or ".." in dosya:
        h.hata_yaz(400, "Gecersiz dosya adi")
        return

    if urun == "gcs":
        belge = g.get("lisans")
        govde = belge.get("lisans") if isinstance(belge, dict) else None
        imza = str(belge.get("imza") or "") if isinstance(belge, dict) else ""
        if (not isinstance(govde, dict) or not imza
                or not depo.veri_imza_dogrula(yetki.govde_bayt(govde), imza)):
            h.hata_yaz(403, "Lisans belgesi dogrulanamadi")
            return
        try:
            fid = int(govde.get("firma_id"))
        except (TypeError, ValueError):
            h.hata_yaz(403, "Lisans belgesi dogrulanamadi")
            return
        if not db.deger(
                "SELECT 1 FROM merkez_lisanslari "
                "WHERE firma_id = %s AND lisans_uid = %s",
                (fid, str(govde.get("lisans_uid") or ""))):
            h.hata_yaz(403, "Lisans bu sunucuda kayitli degil")
            return
        y = yetki.firma_yetkileri(fid)
        if not y or y.get("durum") != "etkin" or not y.get("merkez_lisans"):
            h.hata_yaz(403, "Merkez Uygulama lisansi etkin degil")
            return
        hakli, neden = bakim.guncelleme_alabilir_mi(fid)
        if not hakli:
            h.hata_yaz(403, neden)
            return
    else:
        uid = str(g.get("kurulum_uid") or "").strip()
        gizli = str(g.get("gizli") or "")
        k = db.tek(
            "SELECT s.firma_id, s.gizli_ozet, s.durum, "
            "       f.durum AS firma_durum "
            "FROM sunucu_ornekleri s "
            "JOIN firmalar f ON f.firma_id = s.firma_id "
            "WHERE s.kurulum_uid = %s", (uid,)) if uid else None
        if not k or not role.gizli_dogrula(gizli, k["gizli_ozet"]):
            h.hata_yaz(403, "Kurulum kimligi gecersiz")
            return
        if k["durum"] != "etkin" or k["firma_durum"] != "etkin":
            h.hata_yaz(403, "Kurulum veya firma etkin degil")
            return
        fid = int(k["firma_id"])

    kayit = db.tek(
        "SELECT surum_id FROM surumler "
        "WHERE urun = %s AND surum = %s AND platform IN (%s, 'ortak') "
        "AND dosya_ad = %s AND etkin AND paket_tur IN ('tam', 'guncelleme') "
        "ORDER BY (platform = %s) DESC, surum_id DESC LIMIT 1",
        (urun, surum, platform, dosya, platform))
    hedef = depo.indirme_coz(urun, surum, dosya) if kayit else None
    if not hedef:
        h.hata_yaz(404, "Paket bulunamadi")
        return
    if urun == "gcs":
        db.calistir(
            "UPDATE merkez_lisanslari SET indirme_sayisi = indirme_sayisi + 1, "
            "  son_indirme_ts = now() WHERE firma_id = %s AND iptal_ts IS NULL",
            (fid,))
    depo.indirme_say(int(kayit["surum_id"]), h._kk_es())
    h.dosya_akit(hedef, dosya)


# ---------------------------- dosya tabanli guncelleyici (2.5.26) --------------
# NEDEN: Imzasiz .exe kurulumlari Windows Defender'da yanlis-pozitif
# (Sabsik.FL.A!ml) uretip guncellemeyi bozuyordu. Arka plan guncelleme
# servisi bunun yerine yalniz DEGISEN duz dosyalari indirir. Bu iki uc
# imzali manifesti ve tek tek dosyalari lisans denetimiyle sunar.
import re as _re
GCS_DOSYA_KOK = "/opt/goktungu/merkez/depo/gcs_dosya"


def _gcs_lisans_dogrula(g):
    """gcs icin imzali merkez lisansini dogrular. (firma_id, hata) doner."""
    belge = g.get("lisans")
    govde = belge.get("lisans") if isinstance(belge, dict) else None
    imza = str(belge.get("imza") or "") if isinstance(belge, dict) else ""
    if (not isinstance(govde, dict) or not imza
            or not depo.veri_imza_dogrula(yetki.govde_bayt(govde), imza)):
        return None, "Lisans belgesi dogrulanamadi"
    try:
        fid = int(govde.get("firma_id"))
    except (TypeError, ValueError):
        return None, "Lisans belgesi dogrulanamadi"
    if not db.deger(
            "SELECT 1 FROM merkez_lisanslari "
            "WHERE firma_id = %s AND lisans_uid = %s",
            (fid, str(govde.get("lisans_uid") or ""))):
        return None, "Lisans bu sunucuda kayitli degil"
    y = yetki.firma_yetkileri(fid)
    if not y or y.get("durum") != "etkin" or not y.get("merkez_lisans"):
        return None, "Merkez Uygulama lisansi etkin degil"
    hakli, neden = bakim.guncelleme_alabilir_mi(fid)
    if not hakli:
        return None, neden
    return fid, ""


def _kopru_kimlik_dogrula(g):
    """kopru/video icin kurulum_uid+gizli dogrular. (firma_id, hata)."""
    uid = str(g.get("kurulum_uid") or "").strip()
    gizli = str(g.get("gizli") or "")
    k = db.tek(
        "SELECT s.firma_id, s.gizli_ozet, s.durum, f.durum AS firma_durum "
        "FROM sunucu_ornekleri s JOIN firmalar f ON f.firma_id = s.firma_id "
        "WHERE s.kurulum_uid = %s", (uid,)) if uid else None
    if not k or not role.gizli_dogrula(gizli, k["gizli_ozet"]):
        return None, "Kurulum kimligi gecersiz"
    if k["durum"] != "etkin" or k["firma_durum"] != "etkin":
        return None, "Kurulum veya firma etkin degil"
    return int(k["firma_id"]), ""


def _guncel_dosya_surum():
    """Dosya deposundaki en yeni yayinlanmis surum (GUNCEL isaretcisi)."""
    try:
        with open(os.path.join(GCS_DOSYA_KOK, "GUNCEL"), encoding="utf-8") as f:
            s = f.read().strip()
        return s if _re.fullmatch(r"[0-9]+(\.[0-9]+){1,3}", s) else ""
    except OSError:
        return ""


def _dosya_kok_coz(surum, bagil):
    """depo/gcs_dosya/<surum>/<bagil> guvenli mutlak yol; kotuyse None."""
    if not _re.fullmatch(r"[0-9]+(\.[0-9]+){1,3}", str(surum or "")):
        return None
    parcalar = [x for x in str(bagil or "").replace("\\", "/").split("/")
                if x not in ("", ".")]
    if not parcalar or any(x == ".." or ":" in x for x in parcalar):
        return None
    taban = os.path.realpath(os.path.join(GCS_DOSYA_KOK, surum))
    tam = os.path.realpath(os.path.join(taban, *parcalar))
    if tam != taban and not tam.startswith(taban + os.sep):
        return None
    return tam


@yol("POST", r"/api/istemci/dosya_manifesti", yetki="acik")
def _u_istemci_dosya_manifesti(h, istek, oturum):
    g = istek.govde if isinstance(istek.govde, dict) else {}
    urun = str(g.get("urun") or "").strip().lower()
    if urun not in _GUNCELLEME_PAKET_URUNLERI:
        h.hata_yaz(400, "urun zorunlu")
        return
    if urun == "gcs":
        fid, hata = _gcs_lisans_dogrula(g)
    else:
        fid, hata = _kopru_kimlik_dogrula(g)
    if hata:
        h.hata_yaz(403, hata)
        return
    surum = _guncel_dosya_surum()
    yol_ = os.path.join(GCS_DOSYA_KOK, surum, "MANIFEST.imzali.json") if surum else ""
    if not surum or not os.path.isfile(yol_):
        h.hata_yaz(404, "Yayinlanmis dosya manifesti yok")
        return
    try:
        with open(yol_, encoding="utf-8") as f:
            veri = json.load(f)
    except (OSError, ValueError):
        h.hata_yaz(500, "Manifest okunamadi")
        return
    h.json_yaz(veri)


@yol("POST", r"/api/istemci/dosya", yetki="acik")
def _u_istemci_dosya(h, istek, oturum):
    g = istek.govde if isinstance(istek.govde, dict) else {}
    urun = str(g.get("urun") or "").strip().lower()
    surum = str(g.get("surum") or "").strip()
    bagil = str(g.get("yol") or "").strip()
    if urun not in _GUNCELLEME_PAKET_URUNLERI or not surum or not bagil:
        h.hata_yaz(400, "urun, surum ve yol zorunlu")
        return
    if urun == "gcs":
        fid, hata = _gcs_lisans_dogrula(g)
    else:
        fid, hata = _kopru_kimlik_dogrula(g)
    if hata:
        h.hata_yaz(403, hata)
        return
    tam = _dosya_kok_coz(surum, bagil)
    if not tam or not os.path.isfile(tam):
        h.hata_yaz(404, "Dosya bulunamadi")
        return
    h.dosya_akit(tam, os.path.basename(tam))


# --------------------------------------------------------- kopru indirmeleri
# KULLANICI KARARI (2026-08-16): "bence herkes uye panelinden indirsin,
# ayni merkez yazilim gibi. siteye direkt koymayalim"
#
# OLCULEN KUSUR: tanitim sayfasindaki kopru baglantisi 1.4.2 surumune
# isaret ediyordu (guncel: 1.5.6) - link "yok" degil, ESKI ve gecersizdi.
# Ayrica kurumsal panelde kopru indirmesi HIC yoktu.
#
# NEDEN LISANS SARTI YOK: kopru UCRETSIZDIR. `merkez_indir` lisans
# dogrular cunku Merkez Uygulama 5.000 USD'lik urundur. Kopru icin tek
# sart oturumdur; boylece kimin indirdigi kayda gecer ama ucretsiz
# erisim engellenmez.
@yol("GET", r"/api/firma/kopru_paketler", yetki="firma")
def _u_firma_kopru_paketler(h, istek, oturum):
    """Firmanin indirebilecegi kopru paketleri (Windows + Linux).

    Lisans SORULMAZ - kopru ucretsizdir. Yalniz oturum yeter.
    """
    kayitlar = [k for k in depo.liste("kopru", "kararli", etkin_yalniz=True)
                if k.get("dosya_var")]
    for k in kayitlar:
        # Imza govdesi istemciye gerekmez; paket dogrulamasi indirme
        # sonrasi `depo.acik_anahtar_b64()` ile yapilir.
        k.pop("imza", None)
    h.json_yaz({"kayitlar": kayitlar})


@yol("GET", r"/api/firma/kopru_indir", yetki="firma")
def _u_firma_kopru_indir(h, istek, oturum):
    """Oturum denetimli kopru indirmesi.

    `/indir/kopru/...` statik yolu ACIK BIRAKILMISTIR (mevcut kurulumlarin
    otomatik guncellemesi bu yoldan gecer; kapatmak sahadaki koprulerin
    guncelleme almasini durdurur). Bu uc, panelden inen kullanici icin
    kayitli/denetlenebilir yolu saglar.
    """
    surum = (istek.sorgu.get("surum") or "").strip()
    dosya = (istek.sorgu.get("dosya") or "").strip()
    if not surum or not dosya:
        h.hata_yaz(400, "surum ve dosya zorunlu")
        return
    # Dizin gezinme korumasi - `merkez_indir` ile ayni kural.
    if "/" in dosya or "\\" in dosya or ".." in dosya:
        h.hata_yaz(400, "Gecersiz dosya adi")
        return
    hedef = depo.indirme_coz("kopru", surum, dosya)
    if not hedef or not os.path.isfile(hedef):
        h.hata_yaz(404, "Paket bulunamadi")
        return
    h.dosya_akit(hedef, dosya)


# ------------------------------------------------- goruntu koprusu indirme
# IS83-GORUNTU-DAGITIM
#
# Goruntu Koprusu, sokulen video/AI katmaninin yerine gecen AYRI urundur.
# Kamera yakalama ve AI cikarimi tek surecte, tamamen yerel calisir;
# goruntu merkeze hic gonderilmez.
#
# NEDEN AYRI UC (kopru_indir yeniden kullanilmadi): `depo.indirme_coz`
# urun adini parametre alir ve `kopru_indir` icinde "kopru" SABIT
# yazilidir. Ayni uctan iki urun sunmak icin urun adini istemciden
# almak gerekirdi; bu, istemcinin urun adi gondererek LISANSLI urunlere
# ulasmayi denemesine kapi acardi. Ayri uc, urun adini sunucuda sabit
# tutar.
#
# NEDEN LISANS SORULMUYOR: Goruntu Koprusu ayri satilan bir urun degil;
# `kopru` ile ayni ucretsiz dagitim modelindedir. Tek sart oturumdur,
# boylece kimin indirdigi kayda gecer.
@yol("GET", r"/api/firma/goruntu_paketler", yetki="firma")
def _u_firma_goruntu_paketler(h, istek, oturum):
    """Firmanin indirebilecegi Goruntu Koprusu paketleri."""
    kayitlar = [k for k in depo.liste("video", "kararli", etkin_yalniz=True)
                if k.get("dosya_var")]
    for k in kayitlar:
        # Imza govdesi istemciye gerekmez; `kopru_paketler` ile ayni kural.
        k.pop("imza", None)
    h.json_yaz({"kayitlar": kayitlar})


@yol("GET", r"/api/firma/goruntu_indir", yetki="firma")
def _u_firma_goruntu_indir(h, istek, oturum):
    """Oturum denetimli Goruntu Koprusu indirmesi."""
    surum = (istek.sorgu.get("surum") or "").strip()
    dosya = (istek.sorgu.get("dosya") or "").strip()
    if not surum or not dosya:
        h.hata_yaz(400, "surum ve dosya zorunlu")
        return
    # Dizin gezinme korumasi — `kopru_indir` ile ayni kural.
    if "/" in dosya or "\\" in dosya or ".." in dosya:
        h.hata_yaz(400, "Gecersiz dosya adi")
        return
    hedef = depo.indirme_coz("video", surum, dosya)
    if not hedef or not os.path.isfile(hedef):
        h.hata_yaz(404, "Paket bulunamadi")
        return
    h.dosya_akit(hedef, dosya)


# ------------------------------------------------------- admin: yetki/abone
@yol("GET", r"/api/admin/firma/(\d+)/abonelik")
def _u_admin_firma_abonelik(h, istek, oturum, fid):
    y = yetki.firma_yetkileri(int(fid))
    if not y:
        h.hata_yaz(404, "Firma bulunamadi")
        return
    h.json_yaz({"yetkiler": y,
                "kalemler": yetki.kalem_listesi(int(fid)),
                "talepler": yetki.talep_listesi(firma_id=int(fid)),
                "fiyatlar": yetki.fiyat_listesi()})


@yol("POST", r"/api/admin/firma/(\d+)/yetki")
def _u_admin_firma_yetki(h, istek, oturum, fid):
    """VEILOX sistem yoneticisinin anahtar acma/kapama islemi.

    Radar ve GCCDUAL SATILMAZ; yalniz bu uctan acilir. Kullanici:
    "Radar ve GCCDual ozelligi en tepedeki sirketleri yoneten veilox
    kullanicisi acip kapatabilecek."
    """
    g = istek.govde or {}
    alan = (g.get("alan") or "").strip()
    if "deger" not in g:
        h.hata_yaz(400, "deger zorunlu")
        return
    deger = bool(g.get("deger"))
    tamam, hata = yetki.yetki_ayarla(int(fid), alan, deger,
                                     oturum.get("yonetici_id"))
    if not tamam:
        h.hata_yaz(400, hata)
        return
    kimlik.denetim(oturum.get("yonetici_id"), "firma_yetki", "firma",
                   str(fid), {"alan": alan, "deger": deger}, istek.ip)
    h.json_yaz({"tamam": True, "yetkiler": yetki.firma_yetkileri(int(fid))})


@yol("POST", r"/api/admin/firma/(\d+)/kalem")
def _u_admin_firma_kalem(h, istek, oturum, fid):
    """VEILOX'un elle uyelik tanimlamasi (odeme akisini atlayarak).

    Kullanici: "veilox sistem yoneticisi isterse sirketlere her turlu
    uyeligi ekleyebilecek."
    """
    g = istek.govde or {}
    tamam, hata = yetki.kalem_uygula(
        int(fid), (g.get("kalem") or "").strip(),
        int(g.get("adet") or 1), (g.get("donem") or "aylik").strip(),
        kaynak=(g.get("kaynak") or "veilox").strip(),
        yonetici_id=oturum.get("yonetici_id"),
        notlar=(g.get("notlar") or "").strip() or None,
        bitis=(g.get("bitis") or "").strip() or None)
    if not tamam:
        h.hata_yaz(400, hata)
        return
    kimlik.denetim(oturum.get("yonetici_id"), "abonelik_kalem", "firma",
                   str(fid), g, istek.ip)
    h.json_yaz({"tamam": True, "yetkiler": yetki.firma_yetkileri(int(fid))})


@yol("GET", r"/api/admin/talepler")
def _u_admin_talepler(h, istek, oturum):
    h.json_yaz({"kayitlar": yetki.talep_listesi(
        (istek.sorgu.get("durum") or "").strip() or None)})


@yol("POST", r"/api/admin/talep/(\d+)/karar")
def _u_admin_talep_karar(h, istek, oturum, tid):
    g = istek.govde or {}
    onay = bool(g.get("onay"))
    tamam, hata = yetki.talep_karar(int(tid), onay,
                                    oturum.get("yonetici_id"),
                                    (g.get("notu") or "").strip())
    if not tamam:
        h.hata_yaz(400, hata)
        return
    kimlik.denetim(oturum.get("yonetici_id"), "uyelik_talep_karar", "talep",
                   str(tid), {"onay": onay}, istek.ip)
    h.json_yaz({"tamam": True})


@yol("POST", r"/api/admin/firma/(\d+)/merkez_lisans")
def _u_admin_merkez_lisans(h, istek, oturum, fid):
    """Merkez Uygulama lisansini elle aktiflestirir.

    Kullanici: "ben veilox olarak istedigim sirkete merkezi yazilim
    lisansi aktiflestirebilirim."
    """
    g = istek.govde or {}
    ac = bool(g.get("etkin", True))
    tamam, hata = yetki.yetki_ayarla(int(fid), "merkez_lisans", ac,
                                     oturum.get("yonetici_id"))
    if not tamam:
        h.hata_yaz(400, hata)
        return
    if ac:
        # Kalem defterine de yazilir; boylece "kim ne zaman verdi"
        # denetim izi kalir ve gelir raporlamasi eksik cikmaz.
        yetki.kalem_uygula(int(fid), "merkez", 1, "tek", kaynak="veilox",
                           yonetici_id=oturum.get("yonetici_id"),
                           notlar="Admin panelinden elle aktiflestirildi")
    kimlik.denetim(oturum.get("yonetici_id"), "merkez_lisans", "firma",
                   str(fid), {"etkin": ac}, istek.ip)
    h.json_yaz({"tamam": True, "yetkiler": yetki.firma_yetkileri(int(fid))})


# ==========================================================================
# === GOKTUNGU ODEME UCLARI (mk_odeme) ===
# ==========================================================================
# TASARIM: Webhook TEK fikir kaynagidir. Tarayici "odedim" diyemez;
# yetki YALNIZ Stripe'in imzali webhook'uyla acilir. Aksi halde
# success_url'e elle giden biri bedava koltuk alirdi.
#
# Odeme onayi, VEILOX'un elle tanimlamasiyla AYNI yolu kullanir
# (`yetki.kalem_uygula`). Iki ayri yetki mantigi olusup ayrisamaz.


@yol("GET", r"/api/firma/odeme_durum", yetki="firma")
def _u_firma_odeme_durum(h, istek, oturum):
    """Cevrimici satis acik mi? Arayuz dugmeleri buna gore gorunur."""
    d = odeme.durum()
    d["fiyatlar"] = yetki.fiyat_listesi()
    d["yillik_indirim"] = yetki.YILLIK_INDIRIM
    h.json_yaz(d)


@yol("POST", r"/api/firma/checkout", yetki="firma_yonetici")
def _u_firma_checkout(h, istek, oturum):
    """Odeme sayfasi baglantisi uretir (Stripe Checkout)."""
    if oturum.get("rol") != "firma_yonetici":
        h.hata_yaz(403, "Bu islem icin firma yoneticisi olmalisiniz")
        return
    if not odeme.acik_mi():
        h.hata_yaz(503, "Cevrimici odeme henuz etkin degil. Lutfen "
                        "uyelik talebi olusturun; sistem yoneticisi "
                        "degerlendirip tanimlayacaktir.")
        return
    g = istek.govde or {}
    try:
        adet = int(g.get("adet") or 1)
    except (TypeError, ValueError):
        h.hata_yaz(400, "adet sayisal olmali")
        return
    url, hata = odeme.checkout_olustur(
        _firma_id(oturum), (g.get("kalem") or "").strip(), adet,
        (g.get("donem") or "aylik").strip(),
        eposta=(oturum.get("eposta") or "").strip())
    if hata:
        h.hata_yaz(400, hata)
        return
    h.json_yaz({"url": url})


@yol("GET", r"/api/firma/odeme_portali", yetki="firma_yonetici")
def _u_firma_odeme_portali(h, istek, oturum):
    """Stripe musteri portali: kart guncelleme, iptal, fatura gecmisi."""
    if oturum.get("rol") != "firma_yonetici":
        h.hata_yaz(403, "Bu islem icin firma yoneticisi olmalisiniz")
        return
    url, hata = odeme.portal_baglantisi(_firma_id(oturum))
    if hata:
        h.hata_yaz(400, hata)
        return
    h.json_yaz({"url": url})


@yol("POST", r"/api/genel/stripe_webhook", yetki="acik")
def _u_stripe_webhook(h, istek, oturum):
    """Stripe olay ucu. Kimlik denetimi YOK; guvenlik IMZAYLA saglanir.

    DIKKAT: Govde HAM BAYT (`istek.ham`) olarak kullanilmalidir.
    JSON'a cevrilip yeniden serilestirilirse imza BOZULUR ve tum
    odemeler reddedilir.
    """
    tamam, mesaj = odeme.webhook_isle(
        istek.ham or b"", istek.h.headers.get("Stripe-Signature") or "")
    if not tamam:
        # Stripe 4xx'te yeniden DENEMEZ, 5xx'te dener. Imza/govde hatasi
        # kalicidir (400); veritabani hatasi gecicidir (500).
        alt = mesaj.lower()
        kod = 400 if ("imza" in alt or "govde" in alt
                      or "baslik" in alt or "tolerans" in alt) else 500
        try:
            print("[STRIPE] webhook reddedildi (%d): %s" % (kod, mesaj))
        except Exception:
            pass
        h.json_yaz({"hata": mesaj}, kod)
        return
    h.json_yaz({"tamam": True, "mesaj": mesaj})


@yol("POST", r"/api/admin/stripe/fiyat_kur")
def _u_admin_stripe_fiyat_kur(h, istek, oturum):
    """VEILOX: Stripe'ta urun ve fiyat kayitlarini olusturur.

    Yeniden kosulabilir; mevcut fiyat ayni tutardaysa dokunulmaz.
    Stripe fiyat tutarini degistirmeye izin vermedigi icin tutar
    degismisse yeni fiyat acilir ve `lookup_key` ona tasinir.
    """
    if oturum.get("rol") != "sistem_yonetici":
        h.hata_yaz(403, "Yalniz sistem yoneticisi")
        return
    if not odeme.acik_mi():
        h.hata_yaz(503, "Stripe gizli anahtari tanimli degil")
        return
    try:
        s = odeme.fiyatlari_kur()
    except Exception as e:
        h.hata_yaz(502, "Stripe hatasi: %s" % e)
        return
    kimlik.denetim(oturum.get("yonetici_id"), "stripe_fiyat_kur",
                   "stripe", None, {"islem": s.get("islem")})
    h.json_yaz(s)


@yol("GET", r"/api/admin/stripe/durum")
def _u_admin_stripe_durum(h, istek, oturum):
    """VEILOX: yapilandirma durumu ve fiyat esleme tablosu."""
    d = odeme.durum()
    d["kalemler"] = [{
        "kalem": k, "donem": dn,
        "usd": yetki.kalem_fiyat(k, dn),
        "arama_anahtari": "goktungu_%s_%s" % (k, dn),
    } for k, dn in odeme.satilabilir_kalemler()]
    d["webhook_yolu"] = "/api/genel/stripe_webhook"
    h.json_yaz(d)


# ==========================================================================
# === GOKTUNGU IYZICO + PAKET UCLARI (mk_iyzico/mk_paket) ===
# ==========================================================================
# TASARIM ILKELERI
#
# 1. BILDIRIM TEK FIKIR KAYNAGI DEGILDIR, iyzico'nun KENDISI oyle.
#    Tarayici "odedim" diyemez; ustelik bildirim govdesine de
#    guvenilmez. `mk_iyzico.bildirim_isle` abonelik durumunu iyzico'dan
#    YENIDEN SORAR. Aksi halde uydurma bir bildirim bedava yetki acardi.
#
# 2. Odeme onayi, ust yonetimin elle tanimlamasiyla AYNI yolu kullanir
#    (`yetki.kalem_uygula`). Iki ayri yetki mantigi olusup ayrisamaz.
#
# 3. FIYAT ISTEMCIDEN ALINMAZ. Tutar daima `mk_paket.net_fiyat` ile
#    sunucuda hesaplanir; istemcinin gonderdigi tutar YOK SAYILIR.
#    Aksi halde musteri kendi fiyatini yazardi.
#
# 4. BAKIM BITSE BILE CALISMA DURMAZ (savunma musterisi ilkesi).
#    `calisma_hakki` hicbir kosulda kapanmaz; yalnız guncelleme durur.


@yol("GET", r"/api/firma/paket_durum", yetki="firma")
def _u_firma_paket_durum(h, istek, oturum):
    """Kiracinin paketi, bakim durumu ve odeme durumu."""
    fid = oturum.get("firma_id")
    if not fid:
        h.hata_yaz(400, "Firma oturumu yok")
        return
    fid = int(fid)
    try:
        y = yetki.firma_yetkileri(fid)
        b = bakim.bakim_durumu(fid)
        o = bakim.odeme_durumu(fid)
        pk = y.get("paket_anahtar")
        p = paket.paket(pk) if pk else None
    except Exception as e:
        h.hata_yaz(500, "Durum okunamadi: %s" % e)
        return
    h.json_yaz({
        "tamam": True,
        "yetkiler": y,
        "paket": p,
        "bakim": b,
        "odeme": o,
        "odeme_acik": iyzico.yapilandirilmis_mi(),
    })


@yol("POST", r"/api/firma/abonelik_baslat", yetki="firma_yonetici")
def _u_firma_abonelik_baslat(h, istek, oturum):
    """iyzico odeme formu baslatir.

    TUTAR ISTEMCIDEN ALINMAZ; sunucuda hesaplanir.
    """
    fid = oturum.get("firma_id")
    if not fid:
        h.hata_yaz(400, "Firma oturumu yok")
        return
    g = istek.govde or {}
    pk = str(g.get("paket") or "").strip()
    donem = str(g.get("donem") or "aylik").strip()
    if not pk:
        h.hata_yaz(400, "Paket belirtilmedi")
        return
    if donem not in ("aylik", "yillik"):
        h.hata_yaz(400, "Gecersiz donem")
        return
    if not iyzico.yapilandirilmis_mi():
        h.hata_yaz(503, "Odeme altyapisi henuz yapilandirilmadi")
        return
    try:
        sonuc = iyzico.abonelik_formu_baslat(
            int(fid), pk, donem,
            eposta=str(g.get("eposta") or ""),
            ad=str(g.get("ad") or ""),
            soyad=str(g.get("soyad") or ""),
            gsm=str(g.get("gsm") or ""),
            kimlik_no=str(g.get("kimlik_no") or ""))
    except iyzico.IyzicoHatasi as e:
        h.json_yaz({"tamam": False, "kod": e.kod, "mesaj": e.mesaj}, 400)
        return
    except Exception as e:
        h.hata_yaz(500, "Odeme formu baslatilamadi: %s" % e)
        return
    sonuc["tamam"] = True
    h.json_yaz(sonuc)


@yol("POST", r"/api/firma/abonelik_dogrula", yetki="firma_yonetici")
def _u_firma_abonelik_dogrula(h, istek, oturum):
    """Odeme formu sonucunu iyzico'ya sorarak dogrular."""
    g = istek.govde or {}
    jeton = str(g.get("token") or g.get("jeton") or "").strip()
    if not jeton:
        h.hata_yaz(400, "Belirtec yok")
        return
    try:
        sonuc = iyzico.abonelik_dogrula(jeton)
    except iyzico.IyzicoHatasi as e:
        h.json_yaz({"tamam": False, "kod": e.kod, "mesaj": e.mesaj}, 400)
        return
    except Exception as e:
        h.hata_yaz(500, "Dogrulama basarisiz: %s" % e)
        return
    h.json_yaz(sonuc)


@yol("POST", r"/api/firma/abonelik_iptal", yetki="firma_yonetici")
def _u_firma_abonelik_iptal(h, istek, oturum):
    """Yenilemeyi durdurur. VERI SILINMEZ, sistem CALISMAYA DEVAM EDER."""
    fid = oturum.get("firma_id")
    if not fid:
        h.hata_yaz(400, "Firma oturumu yok")
        return
    ref = db.deger("SELECT iyz_abonelik_ref FROM firmalar "
                   "WHERE firma_id = %s", (int(fid),))
    if not ref:
        h.hata_yaz(404, "Etkin abonelik bulunamadi")
        return
    try:
        iyzico.abonelik_iptal(ref)
    except iyzico.IyzicoHatasi as e:
        h.json_yaz({"tamam": False, "kod": e.kod, "mesaj": e.mesaj}, 400)
        return
    h.json_yaz({"tamam": True,
                "mesaj": "Yenileme durduruldu. Donem sonuna kadar "
                         "hizmet aynen surer; veriler silinmez."})


@yol("GET", r"/api/firma/kart_guncelle", yetki="firma_yonetici")
def _u_firma_kart_guncelle(h, istek, oturum):
    """Basarisiz odeme sonrasi kart guncelleme formu."""
    fid = oturum.get("firma_id")
    if not fid:
        h.hata_yaz(400, "Firma oturumu yok")
        return
    ref = db.deger("SELECT iyz_abonelik_ref FROM firmalar "
                   "WHERE firma_id = %s", (int(fid),))
    if not ref:
        h.hata_yaz(404, "Etkin abonelik bulunamadi")
        return
    try:
        sonuc = iyzico.kart_guncelleme_formu(ref)
    except iyzico.IyzicoHatasi as e:
        h.json_yaz({"tamam": False, "kod": e.kod, "mesaj": e.mesaj}, 400)
        return
    sonuc["tamam"] = True
    h.json_yaz(sonuc)


@yol("POST", r"/api/genel/iyzico_bildirim", yetki="acik")
def _u_iyzico_bildirim(h, istek, oturum):
    """iyzico bildirimi.

    GUVENLIK: govdeye guvenilmez; durum iyzico'dan yeniden sorulur.
    Bildirim her durumda 200 doner (aksi halde iyzico yeniden dener
    ve gunluk sisir).
    """
    g = istek.govde or {}
    try:
        sonuc = iyzico.bildirim_isle(g)
    except Exception as e:
        try:
            db.calistir(
                "INSERT INTO odeme_olaylari (saglayici, olay_turu, govde) "
                "VALUES ('iyzico','bildirim_hatasi',%s)",
                (json.dumps({"hata": str(e)}, ensure_ascii=False),))
        except Exception:
            pass
        h.json_yaz({"tamam": False}, 200)
        return
    h.json_yaz(sonuc, 200)


# --------------------------------------------------------------------------
# UST YONETIM (admin)
# --------------------------------------------------------------------------

@yol("GET", r"/api/admin/paketler")
def _u_admin_paketler(h, istek, oturum):
    """Tum katalog (gizli paketler dahil)."""
    try:
        liste = paket.fiyat_listesi(ust_yonetici=True)
    except Exception as e:
        h.hata_yaz(500, "Katalog okunamadi: %s" % e)
        return
    h.json_yaz({"tamam": True, "paketler": liste,
                "yillik_indirim": paket.YILLIK_INDIRIM})


@yol("POST", r"/api/admin/paket_guncelle")
def _u_admin_paket_guncelle(h, istek, oturum):
    """Paket alanlarini guncelle (beyaz listeli)."""
    g = istek.govde or {}
    pk = str(g.get("paket") or "").strip()
    alanlar = g.get("alanlar") or {}
    if not pk or not isinstance(alanlar, dict):
        h.hata_yaz(400, "Paket ve alanlar gerekli")
        return
    ok, hata = paket.paket_guncelle(pk, alanlar)
    if not ok:
        h.json_yaz({"tamam": False, "mesaj": hata}, 400)
        return
    h.json_yaz({"tamam": True, "paket": paket.paket(pk)})


@yol("GET", r"/api/admin/iskontolar")
def _u_admin_iskontolar(h, istek, oturum):
    """Iskonto listesi. `firma_id` sorgusuyla suzulur."""
    s = istek.sorgu or {}
    fid = s.get("firma_id")
    try:
        liste = paket.iskonto_listesi(int(fid) if fid else None)
    except Exception as e:
        h.hata_yaz(500, "Iskontolar okunamadi: %s" % e)
        return
    h.json_yaz({"tamam": True, "iskontolar": liste})


@yol("POST", r"/api/admin/iskonto_tanimla")
def _u_admin_iskonto_tanimla(h, istek, oturum):
    """Musteriye ozel iskonto tanimlar."""
    g = istek.govde or {}
    fid = g.get("firma_id")
    if not fid:
        h.hata_yaz(400, "firma_id gerekli")
        return
    # OLCULEN IMZA: yonetici_id (int), `tanimlayan` DIYE PARAMETRE YOK.
    # Oturumdaki yonetici kimligi denetim izine yazilir; bulunamazsa
    # None gecilir -- cagri yine calisir, yalniz iz bos kalir.
    yid = None
    for _a in ("yonetici_id", "id", "kimlik"):
        _v = oturum.get(_a)
        if _v is not None:
            try:
                yid = int(_v)
                break
            except (TypeError, ValueError):
                continue
    try:
        deger = float(g.get("deger"))
    except (TypeError, ValueError):
        h.hata_yaz(400, "deger sayisal olmali")
        return
    iid, hata = paket.iskonto_tanimla(
        int(fid),
        str(g.get("tur") or "yuzde"),
        deger,
        paket_anahtar=(str(g.get("paket")) if g.get("paket") else None),
        para_birimi=(str(g.get("para_birimi")) if g.get("para_birimi") else None),
        gecerli_bas=(str(g.get("gecerli_bas")) if g.get("gecerli_bas") else None),
        gecerli_bit=(str(g.get("gecerli_bit")) if g.get("gecerli_bit") else None),
        gerekce=str(g.get("gerekce") or ""),
        yonetici_id=yid)
    if not iid:
        h.json_yaz({"tamam": False, "mesaj": hata}, 400)
        return
    h.json_yaz({"tamam": True, "iskonto_id": iid}, 201)


@yol("POST", r"/api/admin/iskonto_iptal")
def _u_admin_iskonto_iptal(h, istek, oturum):
    g = istek.govde or {}
    iid = g.get("iskonto_id")
    if not iid:
        h.hata_yaz(400, "iskonto_id gerekli")
        return
    # OLCULEN IMZA: (bool, str) IKILISI doner. Demeti dogrudan bool()
    # ile degerlendirmek DAIMA True verir (bos olmayan demet truthy) --
    # olmayan iskonto icin de 200 donerdi. Demet acilir.
    try:
        ok, mesaj = paket.iskonto_iptal(int(iid))
    except (TypeError, ValueError):
        h.hata_yaz(400, "iskonto_id sayisal olmali")
        return
    h.json_yaz({"tamam": bool(ok), "mesaj": mesaj}, 200 if ok else 404)


@yol("GET", r"/api/admin/iyzico_durum")
def _u_admin_iyzico_durum(h, istek, oturum):
    """iyzico yapilandirma durumu. GIZLI ANAHTAR DONMEZ."""
    d = iyzico.durum()
    try:
        d["plan_sayisi"] = int(db.deger(
            "SELECT count(*) FROM paketler "
            "WHERE iyz_plan_ref_ay_try IS NOT NULL "
            "   OR iyz_plan_ref_ay_usd IS NOT NULL") or 0)
    except Exception:
        d["plan_sayisi"] = 0
    h.json_yaz({"tamam": True, "durum": d})


@yol("POST", r"/api/admin/iyzico_ayar")
def _u_admin_iyzico_ayar(h, istek, oturum):
    """iyzico kimlik bilgilerini yazar. Bos alanlar KORUNUR."""
    g = istek.govde or {}
    kip = str(g.get("kip") or "").lower()
    if kip and kip not in ("sinav", "canli"):
        h.hata_yaz(400, "Kip 'sinav' veya 'canli' olmali")
        return
    try:
        iyzico.yapilandirma_yaz(
            api_anahtar=str(g.get("api_anahtar") or ""),
            gizli_anahtar=str(g.get("gizli_anahtar") or ""),
            kip=kip,
            geri_donus=str(g.get("geri_donus") or ""))
    except Exception as e:
        h.hata_yaz(500, "Ayar yazilamadi: %s" % e)
        return
    h.json_yaz({"tamam": True, "durum": iyzico.durum()})


@yol("POST", r"/api/admin/iyzico_plan_kur")
def _u_admin_iyzico_plan_kur(h, istek, oturum):
    """Satilabilir paketler icin iyzico urun/plan kayitlarini olusturur.

    `zorla` verilmedikce mevcut plan referanslari KORUNUR — aksi halde
    her cagri yeni plan acar ve mevcut abonelikler yorungesiz kalir.
    """
    g = istek.govde or {}
    if not iyzico.yapilandirilmis_mi():
        h.hata_yaz(503, "iyzico kimlik bilgileri yapilandirilmamis")
        return
    try:
        sonuc = iyzico.planlari_kur(zorla=bool(g.get("zorla")))
    except Exception as e:
        h.hata_yaz(500, "Plan kurulumu basarisiz: %s" % e)
        return
    h.json_yaz({"tamam": True, "sonuc": sonuc})


@yol("POST", r"/api/admin/bakim_yenile")
def _u_admin_bakim_yenile(h, istek, oturum):
    """Kiracinin bakim/guncelleme suresini uzatir."""
    g = istek.govde or {}
    fid = g.get("firma_id")
    if not fid:
        h.hata_yaz(400, "firma_id gerekli")
        return
    try:
        yil = int(g.get("yil") or 1)
    except (TypeError, ValueError):
        h.hata_yaz(400, "yil sayisal olmali")
        return
    ok, sonuc = bakim.bakim_yenile(int(fid), yil)
    if not ok:
        h.json_yaz({"tamam": False, "mesaj": sonuc}, 400)
        return
    h.json_yaz({"tamam": True, "bakim_bitis": sonuc})


@yol("GET", r"/api/admin/gelir_ozet")
def _u_admin_gelir_ozet(h, istek, oturum):
    """Kiraci bazinda paket/bakim/odeme ozeti."""
    try:
        satirlar = db.sorgu(
            "SELECT f.firma_id, f.unvan, f.kisa_ad, f.paket_anahtar, "
            "       f.para_birimi, f.fatura_donemi, f.pilot_koltuk, "
            "       f.bakim_bitis, f.abonelik, f.salt_okunur, "
            "       f.odeme_deneme, f.odemesiz_bitis, "
            "       f.iyz_abonelik_durum, p.ad_tr AS paket_ad, "
            "       p.tur AS paket_tur "
            "  FROM firmalar f "
            "  LEFT JOIN paketler p ON p.anahtar = f.paket_anahtar "
            " ORDER BY f.firma_id")
    except Exception as e:
        h.hata_yaz(500, "Ozet okunamadi: %s" % e)
        return
    liste = []
    for s in satirlar:
        d = dict(s)
        for a in ("bakim_bitis", "odemesiz_bitis"):
            if d.get(a):
                d[a] = str(d[a])
        try:
            d["iskonto"] = len(paket.iskonto_listesi(int(d["firma_id"])))
        except Exception:
            d["iskonto"] = 0
        liste.append(d)
    h.json_yaz({"tamam": True, "kiracilar": liste})
