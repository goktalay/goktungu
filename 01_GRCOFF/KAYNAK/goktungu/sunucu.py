# -*- coding: utf-8 -*-
"""WSSunucusu ve HttpSunucusu: arayuz ile backend arasindaki koprular.

WSSunucusu : WebSocket komut isleme + periyodik telemetri yayini
HttpSunucusu: index.html ve statik dosyalari sunan basit HTTP sunucusu
"""
import asyncio
import contextlib
import functools
import hashlib
import hmac
import http.server
import ipaddress
import json
import os
import secrets
import ssl
import posixpath
import re
import socketserver
import threading
import urllib.parse
import time

from . import goruntu_gecmisi

# IS94_TELEMETRI_KISMA: veri degismese bile en gec bu kadar saniyede
# bir paket gonderilir. Gerekce: NAT/LTE ara kutulari uzun sessizlikte
# baglantiyi dusurur. Sunucu ping araligi 20 sn oldugu icin 10 sn
# guvenli tarafta kalir.
IS94_SESSIZLIK_TAVANI = 10.0

# v2.4.163: asyncio.to_thread varsayilan havuz is parcaciklari HIC olmez;
# PostgreSQL havuzundan odunc aldiklari baglanti is parcacigi olumunde geri
# alinir -> hic geri verilmiyordu. Birkac AI ayar degisikliginden sonra
# havuz (10) doluyor, sonraki islemler 20 sn bekleyip arayuzu kilitliyordu.
# Her cagri sonunda baglanti havuza iade edilir.
def _db_iade_ederek(fn, *a, **k):
    try:
        return fn(*a, **k)
    finally:
        try:
            from . import veritabani as _vt
            _vt.baglanti_kapat()
        except Exception:
            pass


async def _db_is_parcasi(fn, *a, **k):
    return await asyncio.to_thread(_db_iade_ederek, fn, *a, **k)


from .sabitler import (WS_PORTLAR, HTTP_PORTLAR, YAYIN_HZ, PROJE_KOKU,
                       WS_ADRES, HTTP_ADRES,
                       WEB_KOKU, AVATAR_KLASORU, _veri_yolu,
                       HTTPS_PORT, WSS_PORT, SERTIFIKA_KLASORU,
                       RADAR_VARSAYILAN_IP, RADAR_VARSAYILAN_PORT,
                       RADAR_IZ_ZAMANASIMI, C20_MOD_KODLARI)

# v2.4.52: HTTP koku `assets/web`, kullanici verisi `veri/` altinda.
# Arayuz bu dosyalari KOK-GORELI ister ve istenen yollar veritabaninda
# kayitlidir (`avatars/x.png`, `ai_yuzler/kisiN_....jpg`); yol bicimi
# degistirilemez, cunku mevcut kayitlar bozulur. Bu yuzden istek yolu
# korunur, dosya sistemi tarafinda gercek konuma cevrilir.
#
# Yeni bir kullanici-verisi klasoru arayuze acilacaksa BURAYA eklenir;
# tek tek `translate_path` icine yazilirsa biri unutulur ve eksik olan
# SESSIZCE 404 doner (olculen vaka: `ai_yuzler`).
_VERI_ESLEME = (
    ("/avatars/", AVATAR_KLASORU),
    ("/ai_yuzler/", _veri_yolu("ai_yuzler")),
)

# KK_APP_WS_v1 — kaba kuvvet korumasi.
#
# App KENDI kopyasini tasir (`goktungu/kaba_kuvvet.py`); merkez
# modulune bagimli DEGIL. Sebep: kapali devre kurulumda merkez
# python dizini bulunmaz ve koruma SESSIZCE devre disi kalirdi.
# Ice alma basarisiz olursa `_KK` None kalir ve her kanca kendini
# atlar; boylece modul kaybolsa bile arayuz calismaya devam eder,
# ama bu durum acikca gunluge yazilir.
try:
    from . import kaba_kuvvet as _KK
except BaseException as _e:      # noqa: BLE001
    _KK = None
    print("[KK] kaba_kuvvet modulu yuklenemedi, koruma DEVRE DISI: %s" % _e)


# ----------------------------------------------------------------- #
# STATIK SUNUM SIZINTI ENGELI (v2.4.70, BULGU_04)                   #
#                                                                   #
# OLCULEN ACIK: /app/veri/pg.json 200 donuyordu ve icinde veritabani #
# parolasi vardi; /app/main.py ve /app/goktungu/*.py kaynak kodu     #
# aciktı; dizin listelemesi etkindi. Sebep: duz kurulum yapisinda    #
# WEB_KOKU == PROJE_KOKU, yani Python kaynagi ve `veri/` web         #
# varliklariyla ayni dizinde.                                        #
#                                                                   #
# KARA LISTE, BEYAZ LISTE DEGIL: beyaz liste 40+ js dosyasini tek    #
# tek saymak zorunda kalir; yeni dosya eklendiginde SESSIZCE 404     #
# doner ve arayuz kirilir (olculen sinif: `ai_yuzler` vakasi).       #
#                                                                   #
# 404 DONER (403 DEGIL): 403 dosyanin varligini dogrular.            #
# ----------------------------------------------------------------- #
_STATIK_ENGEL_UZANTI = (
    # kaynak kod
    ".py", ".pyc", ".pyo", ".pyd", ".sh", ".bat", ".ps1",
    # yapilandirma ve veri
    ".json", ".ini", ".cfg", ".conf", ".yaml", ".yml", ".toml",
    ".log", ".db", ".sqlite", ".sqlite3", ".sql", ".jsonl",
    # sir ve sertifika
    ".env", ".pem", ".key", ".crt", ".csr", ".p12", ".pfx", ".jks",
    # yedek
    ".bak", ".adbak", ".orij", ".orig", ".eski", ".old", ".save",
    ".swp", ".swo", ".tmp", ".rej", ".patch", ".diff",
    # paket
    ".deb", ".exe", ".msi", ".aab", ".apk",
)

# PWA ve surum bilgisi web katmaninin ISLEVSEL parcasi: engellenirse
# uygulama kurulamaz (manifest) ya da surum kontrolu kirilir.
# Tam yol esitligi aranir; `/veri/manifest.json` gibi yollar ACILMAZ.
_STATIK_IZIN_TAM = frozenset((
    "/manifest.json",
    "/sw.js",
    "/js/surum.js",
))
# FAZ18-IS29: ISLEVSEL ONEK IZNI (olculen kusur: Cesium sahnesi hic
# kurulmuyordu).
#
# `.json` uzantisi `_STATIK_ENGEL_UZANTI` icinde KALIR: /veri/pg.json
# sizintisi (BULGU_04) geri gelmemeli. Ancak ucuncu parti kutuphaneler
# ISLEVSEL .json varliklari tasir ve bunlar engellenince arayuz
# sessizce kirilir:
#   /lib/Cesium/Assets/approximateTerrainHeights.json  (arazi yuksekligi)
#   /lib/Cesium/Assets/IAU2006_XYS/IAU2006_XYS_*.json  (gok referansi)
# Bu iki varlik reddedilince Cesium `promise` reddiyle coker ve SAHNE
# OLUSMAZ; dron ikonu, lokasyon ikonu, cetvel ve rota isaretcileri
# BIRLIKTE gorunmez oldu (dort belirti, tek kok neden).
#
# NEDEN ONEK, TEK TEK DOSYA DEGIL: Cesium 30 .json varligi tasir ve
# surum yukseltmesinde bu liste degisir. Tek tek saymak, yeni surumde
# SESSIZ 404 uretir -- kara liste yorumunda anlatilan `ai_yuzler`
# sinifinin aynisi.
#
# GUVENLIK OLCUMU: /lib/ altinda riskli uzanti (.py/.env/.pem/.key/
# .db/.log/.conf/.sh) 0 dosya; sir izi (password/secret/token) tasiyan
# .json 0 dosya. Icerik yalniz Cesium, flightindicators, fontawesome,
# hls.min.js, jquery.min.js.
#
# YOL GECISI: bu denetim normpath SONRASINDA yapilir, bu yuzden
# `/lib/../veri/pg.json` istegi `/veri/pg.json` olarak normalize edilir
# ve `_STATIK_ENGEL_ONEK` tarafindan engellenmeye DEVAM eder.
_STATIK_IZIN_ONEK = (
    "/lib/",
)

# Hassas ust duzey dizinler: icerigi web varligi DEGIL.
# `/veri/` burada; `_VERI_ESLEME` eslemeleri istek yolunu
# `/avatars/` ve `/ai_yuzler/` olarak korur, `/veri/` olarak GELMEZ,
# bu yuzden esleme bozulmaz (olculdu).
_STATIK_ENGEL_ONEK = (
    "/veri/",
    "/sertifika/",
    "/goktungu/",
    "/ai_modeller/",
    "/araclar/",
    "/python/",
    "/assets/python/",
)

_STATIK_ENGEL_DESEN = re.compile(
    r"(^|/)\."                 # gizli dosya/dizin: /.git/config
    r"|~$"                      # editor yedegi: index.html~
    r"|(^|/)__pycache__(/|$)"   # derlenmis Python
    r"|_yedek(_|/|$)"           # veri_yedek_2105/
    r"|yedek_arsiv"
    r"|(^|/)requirements\.txt$"
    r"|(^|/)calisma\.json$",
    re.IGNORECASE,
)


def _statik_engelli_mi(yol: str) -> bool:
    """Istek yolu hassas bir kaynaga mi isaret ediyor.

    Yol NORMALLESTIRILIR: `/js/../veri/pg.json` gibi istekler onek
    denetimini atlatmasin. `SimpleHTTPRequestHandler.translate_path`
    kendi icinde de temizlik yapar, ancak engel karari ONCE verildigi
    icin normalizasyon burada tekrarlanir (savunma katmanlari
    birbirine guvenmez).
    """
    d = (yol or "").split("?", 1)[0].split("#", 1)[0]
    try:
        d = urllib.parse.unquote(d)
    except Exception:
        pass
    d = d.replace("\\", "/")
    # posixpath.normpath `/js/../veri` -> `/veri` yapar; sonda `/`
    # kaybolur, bu yuzden dizin isteginde geri eklenir.
    dizin_istegi = d.endswith("/")
    d = posixpath.normpath(d)
    if not d.startswith("/"):
        d = "/" + d
    if dizin_istegi and not d.endswith("/"):
        d += "/"
    alt = d.lower()
    if alt in _STATIK_IZIN_TAM:
        return False
    # FAZ18-IS29: islevsel onek izni. UZANTI denetiminden ONCE, ancak
    # ONEK/DESEN engellerinden ONCE DEGIL -- asagidaki engel denetimleri
    # calismaya devam eder. Boylece /lib/ altindaki .json varliklari
    # servis edilirken /veri/, /goktungu/, gizli dosya ve yedek
    # engelleri bozulmaz.
    if alt.startswith(_STATIK_IZIN_ONEK):
        if not alt.startswith(_STATIK_ENGEL_ONEK):
            if not _STATIK_ENGEL_DESEN.search(alt):
                return False
    if alt.endswith(_STATIK_ENGEL_UZANTI):
        return True
    if alt.startswith(_STATIK_ENGEL_ONEK):
        return True
    return bool(_STATIK_ENGEL_DESEN.search(alt))


def _merkez_panel_adresi():
    """Kurumsal panelin (merkez sunucudaki) tam adresini dondurur.

    Merkez Uygulama kurulumunda `/company/` yereldeki dosyalardan
    servis EDILEMEZ: panel 23 ayri `/api/firma/...` ucu cagirir ve
    bu uclar yalniz merkez sunucuda vardir (olculdu). Bu yuzden
    istek merkeze yonlendirilir.

    Adres program ayarindan (`merkez_adres`) okunur; lisans
    dosyasindan DEGIL. Lisans govdesine alan eklemek imza
    sozlesmesini degistirir ve dagitilmis tum lisanslari gecersiz
    kilar.

    Merkez kullanilmayan (kapali devre) kurulumda bos dizi doner;
    cagiran taraf kullaniciyi bilgilendirir.
    """
    # `AyarYoneticisi` KULLANILMAZ: kurucusu `konsol` parametresi ister
    # ve icinde `tablolari_olustur()` + JSON gocu calistirir. Her HTTP
    # isteginde ornek yaratmak hem hatali (konsol yok) hem pahalidir.
    # Yalniz gereken anahtar dogrudan okunur.
    try:
        from . import merkez as _merkez
        from . import veritabani as _vt
    except Exception:
        return ""
    try:
        with _vt.baglanti() as con:
            r = con.execute(
                "SELECT deger FROM ayarlar WHERE anahtar = ?",
                ("merkez_adres",)).fetchone()
        ham = r["deger"] if r else None
        try:
            deger = json.loads(ham) if ham is not None else None
        except (ValueError, TypeError):
            deger = None
        ayar = _merkez.ayar_coz({"merkez_adres": deger})
    except Exception:
        return ""
    # `etkin` degil `adres` olculur: merkez kimlik dogrulamasi kapali
    # olsa da (yerel kullanicilarla giris) kurumsal panel adresi
    # gecerli olabilir. Ters durum da olur; bu yuzden adres bos ise
    # panel yok sayilir.
    adres = str(ayar.get("adres") or "").strip()
    if not adres:
        return ""
    try:
        taban = _merkez._taban(adres)
    except Exception:
        return ""
    return f"{taban}/company/" if taban else ""


def ssl_baglami():
    """Kendinden imzali sertifika ile SSL baglami dondurur.

    sertifika/gcs.crt + gcs.key yoksa openssl ile otomatik uretir.
    openssl bulunamazsa veya uretim basarisiz olursa None doner
    (HTTPS/WSS devre disi kalir, HTTP/WS calismaya devam eder).
    """
    import ssl
    import subprocess
    crt = os.path.join(SERTIFIKA_KLASORU, "gcs.crt")
    key = os.path.join(SERTIFIKA_KLASORU, "gcs.key")
    if not (os.path.exists(crt) and os.path.exists(key)):
        try:
            os.makedirs(SERTIFIKA_KLASORU, exist_ok=True)
            subprocess.run(
                ["openssl", "req", "-x509", "-newkey", "rsa:2048",
                 "-keyout", key, "-out", crt,
                 "-days", "3650", "-nodes",
                 "-subj", "/CN=goktungu-gcs"],
                check=True, capture_output=True, timeout=30)
            print(f"[SSL] Kendinden imzali sertifika uretildi: {crt}")
        except Exception as e:
            print(f"[SSL] Sertifika uretilemedi ({e}); "
                  f"HTTPS/WSS devre disi. openssl kurulu mu?")
            return None
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(crt, key)
        return ctx
    except Exception as e:
        print(f"[SSL] Sertifika yuklenemedi ({e}); HTTPS/WSS devre disi.")
        return None


def _goruntu_kamera_listesi_coz(veri):
    """Köprü kamera yanıtının doğrudan veya zarflı liste biçimini çözer."""
    if isinstance(veri, dict):
        veri = veri.get("sonuc", veri.get("kameralar"))
    return veri if isinstance(veri, list) else None


class WSSunucusu:
    """WebSocket sunucusu: istemci komutlarini isler, telemetri yayinlar."""

    def __init__(self, konsol, ayarlar, kullanicilar, lokasyonlar,
                 kayit, dron, radar, angajman, takipci, etiket=None,
                 rotalar=None, gorev=None, baglantilar=None,
                 kameralar=None, video_proxy=None, ucus_gecmisi=None,
                 manuel_kontrol=None, dron_takip=None, suru=None,
                 pilot=None,
                 dji_kopru=None, ai_yonetici=None, kisiler=None,
                 araclar=None, mesajlar=None, istasyon2=None, m50=None,
                 m50_yerel=None):
        self.konsol = konsol
        self.ayarlar = ayarlar
        self.kullanicilar = kullanicilar
        self.lokasyonlar = lokasyonlar
        self.kayit = kayit
        self.etiket = etiket
        self.rotalar = rotalar
        self.gorev = gorev
        self.kameralar = kameralar
        self.video_proxy = video_proxy
        # v2.4.210 (kullanici istegi: video kayit): vekil akisindan dosyaya
        # kayit. Veri koku sabitlerden; vekil portu video_proxy ile ayni.
        try:
            from . import sabitler as _sb
            from .video_kayit import VideoKaydedici as _VK
            self.video_kaydedici = _VK(konsol=self.konsol,
                                       veri_koku=getattr(_sb, "VERI_KOKU", "."),
                                       proxy=self.video_proxy)
        except Exception as _vk_e:
            self.video_kaydedici = None
            try:
                self.konsol("KAYIT", "Video kaydedici kurulamadi: %s" % _vk_e, "uyari")
            except Exception:
                pass
        self.baglantilar = baglantilar
        self.dron = dron
        self.radar = radar
        # M50 HVS SDK bu süreçte yüklenmez; nesne yalnız saha Köprüsünün
        # arındırılmış durumunu taşıyan vekildir.
        self.m50 = m50
        # v2.4.184: Merkez KENDİSİ Windows x64 ise ve gömülü SDK varsa
        # (m50_sdk/), M50 köprüsüz de çalışabilir. `_m50_kopruye` önce
        # bunu dener; kullanılamazsa (Linux Merkez, SDK eksik) saha
        # Köprüsü akışına sessizce düşer.
        self.m50_yerel = m50_yerel
        self.angajman = angajman
        self.takipci = takipci
        self.kilit = dron.kilit          # paylasilan threading.Lock
        self.istemciler = set()
        self._takipci_son_isle = 0.0
        self.ucus_gecmisi = ucus_gecmisi  # dron renkleri + ucus kayitlari
        self.manuel_kontrol = manuel_kontrol  # WASD/joystick manuel kontrol
        # v2.4.44: Yer Istasyonu 2 (ESP32-S3 kontrol paneli). main.py'de
        # olusturulur; None ise panel komutlari sessizce yok sayilir ve
        # sistemin geri kalani etkilenmez (pyserial yok / donanim yok).
        self.istasyon2 = istasyon2
        if self.istasyon2 is not None:
            # Modul is parcaciginda calisir; asyncio dongusune guvenli
            # kopru _ist2_yayinla/_ist2_eylem icinde kurulur.
            self.istasyon2._duyur = self._ist2_yayinla
            self.istasyon2._eylem = self._ist2_eylem
        self.dron_takip = dron_takip          # dron-dron takip motoru
        self.suru = suru                        # v2.4.3: sürü uçuş motoru
        self.pilot = pilot                    # v2.1.7: log + rol/izin + uyari
        self.mesajlar = mesajlar              # v2.4.32: pilot mesajlasma
        self.dji_kopru = dji_kopru            # v2.1.8: DJI kopru sunucusu
        # v2.4.39: sanal dron = gercek ArduPilot SITL sureci. Yonetici
        # main.py'de olusturulup enjekte edilir; None ise sanal baglantilar
        # baslatilamaz ama diger her sey normal calisir.
        self.sitl = None
        # v2.5.18: main.py tarafindan enjekte edilen imzali paket
        # denetleyicisi. None iken tum eski kurulumlar calismaya devam eder.
        self.guncelleme = None
        # v2.4.49: gercekte alinan WS portu; `calistir()` doldurur.
        self.aktif_ws_port = None
        # v2.4.0: AI katmani
        self.ai_yonetici = ai_yonetici        # AI islem sunuculari + tespit
        # v2.4.45: AI bilgisayarini SSH ile uzaktan baslatma + canli
        # konsol. main.py'de olusturulup enjekte edilir; None ise SSH
        # komutlari anlasilir hata dondurur, sistemin geri kalani calisir.
        self.ai_ssh = None
        # v2.4.49: systemd servis ve makine guc yonetimi. main.py'de
        # olusturulup enjekte edilir; None ise servis komutlari anlasilir
        # hata dondurur (ornegin Windows'ta systemd yoktur).
        self.servis = None
        self.kisiler = kisiler                # kutuphane: kisiler
        self.araclar = araclar                # kutuphane: araclar
        self._loop = None                     # ana asyncio dongusu
        # websocket -> giris yapan kullanici (pilot) eslemesi
        self._ws_pilot = {}
        # v2.4.53: websocket -> firma_id eslemesi (izolasyon)
        self._ws_firma = {}
        # IS99: Yerel tam ekran seçim paketi yaklaşık 2 Hz akar. Aynı
        # seçim için her pakette pencere açılmasını önleyen kısa ömürlü,
        # yalnız bellek içi tekrar defteri; süreç yeniden başlarsa boşalır.
        self._goruntu_aday_kilit = threading.Lock()
        self._goruntu_aday_son = {}
        self._goruntu_aday_ttl_sn = 15.0
        # IS109: canlı küçük kare yayını için yalnız firma kimliği/hedef sayısı
        # tutan operasyonel tanı; içerik, URL veya kullanıcı bilgisi kaydedilmez.
        self._goruntu_yayin_hedef_son = {}
        # v2.4.53 Faz 11: baglanti_id -> acik ham MAVLink akis kanali.
        # `merkez` turu baglantilarda dron trafigi kopruden merkeze WSS
        # uzerinden gelir; merkez surec bunu yerel bir UDP portuna doker
        # ve GCS o portu `udpin:` ile dinler. Defter kapatma icin
        # gereklidir: hangi ornek/firma ile hangi kanalin acildigini
        # baglanti kaydindan TEKRAR cozmek guvenilmez (kayit silinmis
        # veya kopru degismis olabilir) — o zaman merkezde port sizar.
        self._akis_kanallari = {}
        # v2.4.142: Betaflight MSP, MAVLink akis/komut hattindan tamamen
        # ayridir. `main.py` yerel salt-okunur yoneticiyi buraya enjekte
        # eder; merkez-kopru oturumlari ayri defterde tutulur.
        self.betaflight = None
        self._betaflight_kopruleri = {}
        # Uzak MSP oturumuna ait yönlendirme verisi yalnız süreç belleğinde
        # tutulur; istemciye yayımlanan durum sözlüğüne firma/örnek kimliği
        # veya kimlik doğrulama bilgisi eklenmez.
        self._betaflight_kopru_meta = {}
        self._betaflight_kopru_son_yenile = 0.0
        self._betaflight_kopru_yenilemeleri = {}
        # RFD900/seri bağlantılarında `otomatik` tercih kalıcı ayar değil,
        # çalışma anı sonucudur. Süreç belleğinde tutulur ve durdurmada
        # silinir; yanlış algılama sonraki başlatmada yeniden denenir.
        self._otomatik_protokoller = {}
        # v2.3.0: websocket -> istemci baglanti ayrintilari (ip, port,
        # user-agent vb.) — giris_log tablosuna yazilir
        self._ws_istemci = {}
        # v2.4.21: KESINTISIZ telemetri kaydi — bellekte tampon, periyodik
        # toplu yazma (SQLite'a her karede yazmamak icin)
        self._tel_tampon = []          # YEDEK yol (dosya tamponu yoksa)
        self._tel_son_ornek = {}       # sysid -> son ornekleme ts
        self._tel_son_yazma = 0.0      # son toplu yazma ts
        self._tel_son_temizlik = 0.0   # son saklama suresi temizligi
        # v2.4.24: dakikalik fiziksel dosya tamponu (kullanici talebi)
        self._tel_tampon_nesne = None  # TelemetriTampon (gec olusturulur)
        self._tel_tampon_hata = False  # kurulum denendi ve basarisiz
        self._tel_sysid_dron = {}      # sysid -> dron_id (aktarim cozumu)
        # Dron katmanina aktif pilot saglayicisi (kimlik/oturum kaydi)
        if self.dron is not None:
            self.dron.pilot_saglayici = self._aktif_pilot
        if self.dji_kopru is not None:
            self.dji_kopru.pilot_saglayici = self._aktif_pilot
        # v2.4.59: MERKEZ KIPI RADAR VEKILI beslemesi.
        # `RadarVekili` kendi basina kopruyu bulamaz: firma baglami
        # (hangi kiracinin radari) ve ic uc anahtari burada yasar.
        # Vekil degilse (lokal kurulum) hicbir sey yapilmaz.
        if getattr(self.radar, "_cek", "YOK") is None:
            self.radar._cek = self._radar_kopru_durum_cek
        # M50 vekili yalnız `m50_durum` Köprü eylemini çeker; bağlantı
        # kimlik bilgileri bu süreçte tutulmaz.
        if self.m50 is not None and getattr(self.m50, "_cek", "YOK") is None:
            self.m50._cek = self._m50_kopru_durum_cek
        # v2.4.61: MERKEZ KIPI VIDEO ve AI VEKILI beslemesi.
        #
        # Radar ile ayni gerekce: vekil kendi basina kopruyu bulamaz,
        # cunku firma baglami (hangi kiracinin kamerasi / AI bilgisayari)
        # ve ic uc anahtari burada yasar.
        #
        # `_komut` de baglanir: cihaz taramasi ve izleme atama gibi
        # eylemler WS komut isleyicisinden DEGIL vekil uzerinden gecer
        # (`_ai_izleme_esitle` gibi ic cagrilar da ayni yoldan gitmeli;
        # aksi halde otomatik esitleme merkezden atamaya devam ederdi).
        if getattr(self.video_proxy, "_cek", "YOK") is None:
            self.video_proxy._cek = self._video_kopru_durum_cek
            self.video_proxy._komut = self._saha_komut_eszamanli
        # FAZ19-IS60: canli kamera kanali geri cagrilari.
        # `_komut` ile ayni gerekce — ornek_id/firma_id burada cozulur.
        if getattr(self.video_proxy, "_kanal_ac", "YOK") is None:
            self.video_proxy._kanal_ac = self._saha_video_kanal_ac
            self.video_proxy._kanal_kapat = self._saha_video_kanal_kapat
        if getattr(self.ai_yonetici, "_cek", "YOK") is None:
            self.ai_yonetici._cek = self._ai_kopru_durum_cek
            self.ai_yonetici._komut = self._saha_komut_eszamanli
        # v2.4.53: MERKEZ KOPRU AJANI. Merkez sahaya baglanamaz (saha
        # kurulumlari NAT arkasindadir ve sabit IP'leri yoktur); bu yuzden
        # ters WSS baglantisini GCS acar. Ajan `veri/kopru.json` icindeki
        # kurulum kimligiyle calisir; kayit yoksa hic baslatilmaz ve
        # sistemin geri kalani etkilenmez.
        self.kopru = None                     # goktungu.kopru.KopruAjani
        self._kopru_kilit = None              # asyncio kurulum kilidi

    # ------------------------------------------------------------------
    # v2.4.21: KESINTISIZ TELEMETRI KAYDI
    # ------------------------------------------------------------------
    TEL_ORNEK_ARALIK = 1.0      # s; dron basina ornekleme periyodu (1 Hz)
    TEL_YAZMA_ARALIK = 5.0      # s; (v2.4.24: artik kullanilmiyor)
    TEL_TEMIZLIK_ARALIK = 3600  # s; saklama suresi denetim periyodu
    TEL_SAKLAMA_GUN = 30        # gun; bundan eski telemetri silinir
    # v2.4.24: dakikalik dosya tamponu -> DB aktarim periyodu
    TEL_AKTARIM_ARALIK = 60.0   # s; kullanici talebi: "her bir dakikada bir"
    # v2.4.25: yedek bellek yolunda tamponun ust siniri.
    # Kullanici logunda DB bozuk oldugu icin tampon sinirsiz buyuyordu
    # (191 satir ve artiyor). Ucus sirasinda bellek tukenmesi GCS'yi
    # tamamen durdurabilir. 200.000 ornek ~40 MB'dir ve 1 Hz'de tek
    # dron icin ~55 saat veri demektir; pratikte asilmaz.
    TEL_TAMPON_SINIR = 200000   # ornek

    def _telemetri_kaydet(self, paket, simdi):
        """Bagli her dronun telemetrisini kesintisiz kaydeder.

        Ucuslar `v_ucuslar` gorunumu ile tespit edilir, bu yuzden burada
        hicbir ucus mantigi yoktur: dron bagli oldugu surece ornek
        yazilir.

        ## v2.4.24 degisikligi (kullanici talebi)

        "dron calismaya basladiginda 1'er dakikalik fiziksel dosyalar
         tutalim sonra her bir dakikada bir veritabanina yazalim"

        Ornekler artik once DISKE (JSONL, dakikalik dosya) yazilir,
        dakikada bir veritabanina aktarilir. v2.4.23'te ucu ayri veri
        kaybi noktasi vardi:

        1. Tampon YALNIZCA bellekteydi; surec cokerse 5 saniyelik
           telemetri yok oluyordu.
        2. `satirlar, self._tel_tampon = self._tel_tampon, []` satiri
           tamponu yazma DENENMEDEN bosaltiyordu. Yazma basarisiz
           olursa `satirlar` fonksiyon cikisinda yok oluyordu; geri
           alma yolu YOKTU.
        3. `dron_id` henuz olusmamissa ornek tamamen atlaniyordu
           (`continue`) — dronun ilk saniyeleri, kalkisani dahil,
           hic kaydedilmiyordu.

        Artik ornek her durumda diske yazilir; `dron_id` bilinmiyorsa
        `None` olarak kaydedilir ve aktarim aninda cozulmeye calisilir.
        """
        from . import veritabani as _vt
        p = self._aktif_pilot()
        eposta, isim = p.get("eposta", ""), p.get("isim", "")
        tampon = self._tel_tampon_al()

        ornekler = []
        for d in paket:
            if not d.get("baglanti"):
                continue
            sysid = d.get("sysid")
            son = self._tel_son_ornek.get(sysid, 0.0)
            if (simdi - son) < self.TEL_ORNEK_ARALIK:
                continue
            self._tel_son_ornek[sysid] = simdi

            # v2.4.24: dron_id yoksa ATLAMIYORUZ. Ornek diske yazilir,
            # `sysid` sayesinde aktarimda cozulebilir.
            dron_id = self.dron.dron_db_id.get(sysid)
            ornekler.append({
                "dron_id": int(dron_id) if dron_id else None,
                "oturum_id": self.dron.oturum_id.get(sysid),
                "ts": round(float(simdi), 2),
                "lat": d.get("lat"),
                "lon": d.get("lon"),
                "irtifa": round(float(d.get("alt_rel") or 0.0), 2),
                "irtifa_msl": round(float(d.get("alt_msl") or 0.0), 2),
                "hiz": round(float(d.get("groundspeed") or 0.0), 2),
                "dikey_hiz": round(float(d.get("vz") or 0.0), 2),
                "yaw": round(float(d.get("heading") or 0.0), 1),
                "roll": round(float(d.get("roll") or 0.0), 2),
                "pitch": round(float(d.get("pitch") or 0.0), 2),
                "mod": str(d.get("mod") or ""),
                "armed": 1 if d.get("armed") else 0,
                "batarya_v": round(float(d.get("batarya_v") or 0.0), 2),
                "batarya_y": int(d.get("batarya_pct")
                                 if d.get("batarya_pct") is not None
                                 else -1),
                "uydu": int(d.get("uydu") or 0),
                "hdop": float(d.get("hdop") or 0.0),
                "pilot_eposta": eposta,
                "pilot_isim": isim,
                # Sema disi; `_normalle` dusurur ama `_sysid_kaydet`
                # aktarim cozumlemesi icin ayri tutar.
                "_sysid": sysid,
            })

        if ornekler:
            if tampon is not None:
                # sysid -> dron_id eslemesini akilda tut (aktarimda
                # gerekebilir; dosyaya sema disi alan yazilmaz)
                for o in ornekler:
                    sid = o.pop("_sysid", None)
                    if sid is not None and o.get("dron_id"):
                        self._tel_sysid_dron[sid] = o["dron_id"]
                tampon.coklu_ekle(ornekler, simdi)
            else:
                # Tampon kurulamadiysa (dizin yazilamaz vb.) eski
                # bellek yoluna DUS; telemetri tamamen kaybolmasin.
                for o in ornekler:
                    o.pop("_sysid", None)
                    if not o.get("dron_id"):
                        continue
                    self._tel_tampon.append(
                        tuple(o.get(a) for a in _vt.TELEMETRI_ALANLARI))

        # v2.4.24: dakikada bir dosyadan DB'ye aktar
        if tampon is not None:
            tampon.dongu_adimi(
                _vt.telemetri_toplu_yaz,
                dron_id_cozucu=self._tel_dron_id_coz,
                simdi=simdi,
                aktarim_aralik=self.TEL_AKTARIM_ARALIK,
                temizlik_aralik=self.TEL_TEMIZLIK_ARALIK,
            )
        elif (self._tel_tampon
                and (simdi - self._tel_son_yazma) >= self.TEL_YAZMA_ARALIK):
            # Yedek yol: tampon yoksa eski davranis, ancak artik
            # BASARISIZLIKTA VERI GERI KONUYOR.
            satirlar, self._tel_tampon = self._tel_tampon, []
            self._tel_son_yazma = simdi
            try:
                _vt.telemetri_toplu_yaz(satirlar)
            except Exception as e:
                # v2.4.24: satirlari GERI KOY; v2.4.23'te yok oluyordu.
                self._tel_tampon = satirlar + self._tel_tampon
                self.konsol("DB", f"Telemetri yazma hatasi: {e} "
                            f"({len(satirlar)} satir korundu)", "hata")

                # --- v2.4.25: BOZULMA ALGILANIRSA OTOMATIK ONARIM ---
                # Kullanici logunda bu hata 5 sn'de bir tekrarladi ve
                # sayac 191 satira kadar cikti; telemetri diske HIC
                # yazilamadi. Onarim bu kisir dongüyü kirar.
                # `calisma_zamani_onarim` en fazla 60 sn'de bir dener
                # (ONARIM_ARA), yani onarim dongüsüne girilmez.
                try:
                    from . import db_onarim as _dbo
                    if _dbo.calisma_zamani_onarim(
                            _vt.DOSYA, e, self.konsol):
                        # Onarim yapildi; bekleyen satirlari HEMEN yaz.
                        # Basarisiz olursa satirlar tamponda kalir.
                        try:
                            bekleyen, self._tel_tampon = (
                                self._tel_tampon, [])
                            _vt.telemetri_toplu_yaz(bekleyen)
                            self.konsol(
                                "DB", f"Onarim sonrasi {len(bekleyen)} "
                                "telemetri satiri yazildi.")
                        except Exception as e2:
                            self._tel_tampon = bekleyen + self._tel_tampon
                            self.konsol("DB", "Onarim sonrasi yazma da "
                                        f"basarisiz: {e2}", "hata")
                except Exception as e3:
                    self.konsol("DB", f"Onarim denenemedi: {e3}", "uyari")

                # Tampon sinirsiz buyumesin: bellek tukenmesi ucus
                # sirasinda GCS'yi tamamen durdurabilir. 200k ornek
                # ~40 MB'dir; en ESKI satirlar dusurulur, cunku canli
                # ucusta guncel veri daha degerlidir.
                if len(self._tel_tampon) > self.TEL_TAMPON_SINIR:
                    dusen = len(self._tel_tampon) - self.TEL_TAMPON_SINIR
                    self._tel_tampon = self._tel_tampon[dusen:]
                    self.konsol("DB", f"Telemetri tamponu sinira ulasti; "
                                f"{dusen} en eski ornek dusuruldu.",
                                "uyari")

        # Saklama suresi temizligi (varsayilan 30 gun)
        if (simdi - self._tel_son_temizlik) >= self.TEL_TEMIZLIK_ARALIK:
            self._tel_son_temizlik = simdi
            try:
                gun = int(self.ayarlar.yukle().get(
                    "telemetri_saklama_gun", self.TEL_SAKLAMA_GUN))
                silinen = _vt.telemetri_temizle(gun)
                if silinen:
                    self.konsol("DB", f"{silinen} eski telemetri ornegi "
                                f"silindi ({gun} gun saklama).")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # v2.4.44: YER ISTASYONU 2 - eylem yurutme ve yayin koprusu
    # ------------------------------------------------------------------
    # Istasyon2 modulu SERI PORT IS PARCACIGINDA calisir; asyncio
    # nesnelerine oradan dokunulamaz. Bu iki yardimci, is parcacigindan
    # gelen cagriyi `call_soon_threadsafe` ile ana dongude siraya koyar.
    #
    # UCUS eylemleri BURADA yurutulur (yetki ve dron erisimi tek yerde
    # kalsin). HARITA eylemleri yurutulmez, arayuze YAYINLANIR: harita
    # durumu (Cesium kamerasi, katman sirasi, nesne listesi) yalniz
    # tarayicida vardir.

    # Ucus eylemi -> gerektirdigi mod adi (arac tipine gore numaraya
    # cevrilir; kopter GUIDED=4 iken plane GUIDED=15'tir)
    IST2_MOD_EYLEM = {
        "mod_guided": ("GUIDED", "GUIDED"),
        "mod_althold": ("ALT_HOLD", "QHOVER"),   # plane'de ALT_HOLD yok
        "mod_auto": ("AUTO", "AUTO"),
    }
    IST2_HARITA_EYLEMLERI = (
        "harita_kaynak", "kullanici_konum", "hepsini_kapsa",
        "nokta_gez", "patlat_onay",
        "harita_zoom_in", "harita_zoom_out", "harita_zoom_dur",
    )

    def _ist2_yayinla(self, mesaj):
        """Istasyon2 durum yayini (is parcacigindan cagrilir)."""
        if self._loop is None:
            return
        try:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(self._duyur(mesaj)))
        except Exception:
            pass

    def _ist2_eylem(self, ad, ayrinti):
        """Istasyon2 buton/toggle eylemi (is parcacigindan cagrilir)."""
        if ad in self.IST2_HARITA_EYLEMLERI:
            # Arayuze bildir; yurutmeyi tarayici yapar.
            self._ist2_yayinla({"tip": "istasyon2_eylem", "eylem": ad,
                                "ayrinti": ayrinti})
            return
        if self._loop is None:
            return
        try:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(
                    self._ist2_ucus_eylem(ad, ayrinti)))
        except Exception:
            pass

    def _ist2_manuel_dronlar(self):
        """Manuel (joystick) kontrolu ACIK olan bagli dronlarin sysid'leri.

        Kullanici sarti: "dugmeler dronlarda joystick kontrolu aciksa
        calisacak". Anahtar kapaliyken P1-P6 hicbir sey yapmaz; boylece
        cantadaki bir dugmeye yanlislikla basmak ARM/TAKEOFF gondermez.
        """
        if not self.manuel_kontrol:
            return []
        try:
            acik = set(int(s) for s in
                       (self.manuel_kontrol.durum().get("aktif") or []))
        except Exception:
            return []
        simdi = time.time()
        sonuc = []
        with self.kilit:
            for sysid, d in self.dron.dronlar.items():
                if int(sysid) in acik and (simdi - d["son_mesaj"]) < 8.0:
                    sonuc.append(int(sysid))
        return sorted(sonuc)

    def _ist2_mod_no(self, sysid, kopter_adi, plane_adi):
        """Mod adini aracin mod haritasindan numaraya cevirir."""
        try:
            harita = self.dron._mod_haritasi(sysid)
        except Exception:
            harita = self.dron.MOD_HARITASI
        for ad in (kopter_adi, plane_adi):
            for no, isim in harita.items():
                if isim == ad:
                    return int(no), isim
        return None, ""

    async def _ist2_ucus_eylem(self, ad, ayrinti):
        """Panel butonundan gelen UCUS eylemini uygular."""
        kanal = str((ayrinti or {}).get("kanal", ""))
        hedefler = self._ist2_manuel_dronlar()
        if not hedefler:
            # v2.4.45: Bu satir GENEL konsola YAZILMAZ. Panelde bir
            # butona her basista uyari basmak genel konsolu doldurur
            # (kullanici: "dronlarin iletisim konsol ciktilarini genel
            # konsola yazma"). Ret bilgisi panelin kendi olay akisina
            # `istasyon2_eylem_sonuc` ile gider. Genel konsola yalnizca
            # durum DEGISTIGINDE bir kez dusulur, boylece "neden hicbir
            # sey olmuyor" sorusu yine cevaplanabilir.
            if not getattr(self, "_ist2_ret_bildirildi", False):
                self._ist2_ret_bildirildi = True
                self.konsol("IST2", "Panel ucus butonlari devre disi: "
                                    "joystick kontrolu acik bagli dron "
                                    "yok (bu uyari tekrarlanmaz).",
                            "uyari")
            await self._duyur({"tip": "istasyon2_eylem_sonuc",
                               "eylem": ad, "kanal": kanal,
                               "basari": False, "sysidler": [],
                               "sebep": "joystick_kapali"})
            return
        # Hedef bulundu: bir sonraki ret durumunda yeniden bildirilebilsin.
        self._ist2_ret_bildirildi = False
        uygulanan = []
        for sysid in hedefler:
            with self.kilit:
                d = dict(self.dron.dronlar.get(sysid) or {})
            armed = bool(d.get("armed"))
            # "Havada mi" olcutu: ARM + zemine gore irtifa > 1 m.
            # Yalniz irtifaya bakmak yeterli degil (zeminde 0.4 m gurultu
            # gorulebilir), yalniz ARM'a bakmak da yeterli degil (motor
            # calisirken yerde bekleyen dron havada sayilmamali).
            try:
                alt = float(d.get("alt_rel") or 0.0)
            except (TypeError, ValueError):
                alt = 0.0
            havada = armed and alt > 1.0
            if ad == "arm_disarm":
                aksiyon = "disarm" if armed else "arm"
                self.dron.komut_gonder(sysid, aksiyon)
                uygulanan.append((sysid, aksiyon))
            elif ad == "takeoff_land":
                if havada:
                    self.dron.komut_gonder(sysid, "land")
                    uygulanan.append((sysid, "land"))
                else:
                    # Kalkis irtifasi: dronun kendi ayari (yoksa
                    # varsayilan). Panel dugmesinde irtifa girisi yok.
                    self.dron.komut_gonder(sysid, "takeoff")
                    uygulanan.append((sysid, "takeoff"))
            elif ad == "rtl":
                self.dron.komut_gonder(sysid, "rtl")
                uygulanan.append((sysid, "rtl"))
            elif ad in self.IST2_MOD_EYLEM:
                kopter_adi, plane_adi = self.IST2_MOD_EYLEM[ad]
                mod_no, mod_adi = self._ist2_mod_no(sysid, kopter_adi,
                                                    plane_adi)
                if mod_no is None:
                    self.konsol("IST2", f"D{sysid}: {kopter_adi} modu bu "
                                        "arac tipinde yok", "uyari")
                    continue
                self.dron.komut_gonder(sysid, "set_mode", mod_no)
                uygulanan.append((sysid, mod_adi))
            elif ad == "gorev_baslat" and self.gorev:
                self.gorev.baslat(sysid)
                uygulanan.append((sysid, "gorev_baslat"))
            elif ad == "gorev_iptal" and self.gorev:
                self.gorev.iptal(sysid)
                uygulanan.append((sysid, "gorev_iptal"))
        if uygulanan:
            self.konsol("IST2", "%s -> %s" % (kanal or ad, ", ".join(
                "D%d:%s" % (s, a) for s, a in uygulanan)), "basari")
        await self._duyur({
            "tip": "istasyon2_eylem_sonuc", "eylem": ad, "kanal": kanal,
            "basari": bool(uygulanan),
            "sysidler": [s for s, _ in uygulanan],
            "aksiyonlar": [a for _, a in uygulanan],
            "sebep": "" if uygulanan else "uygulanamadi"})

    # ------------------------------------------------------------------
    def _tel_tampon_al(self):
        """Dakikalik dosya tamponunu (gec) olusturur.

        Tampon kurulamazsa `None` doner ve cagiran taraf eski bellek
        yoluna duser. Tampon kurulamadi diye telemetriyi tamamen
        kaybetmek kabul edilemez.
        """
        if self._tel_tampon_nesne is not None:
            return self._tel_tampon_nesne
        if self._tel_tampon_hata:
            return None            # bir kez denendi, basarisiz
        try:
            from .telemetri_tampon import TelemetriTampon
            from .sabitler import _veri_alt_yolu
            # v2.4.52: veri kokune bagli. ESKI yapida bu yol
            # <kok>/veri/telemetri_tampon idi; `_veri_yolu` yeni
            # yapida <kok>/veri/telemetri_tampon dondurur, yani
            # AYNI dizin. Boylece aktarilmamis ucus ornekleri
            # gecis sirasinda kaybolmaz.
            dizin = _veri_alt_yolu("telemetri_tampon")
            self._tel_tampon_nesne = TelemetriTampon(dizin, self.konsol)

            # v2.4.25: BOZULMA ONARIM KANCASI.
            # DB bozuldugunda aktarim her turda basarisiz olur ve
            # dosyalar MAKS_DENEME sonrasi karantinaya gider. Kanca
            # olmadan bu durum kendiliginden DUZELMEZ.
            def _onarim_kancasi(hata):
                # `_vt` bu kapsamda YOK; modul duzeyinde import edilmiyor
                # (yalnizca `_telemetri_kaydet` icinde yerel). Burada
                # yerel import sart, aksi halde onarim tam ihtiyac
                # duyuldugu anda `NameError` verir.
                try:
                    from . import db_onarim as _dbo
                    from . import veritabani as _vtk
                    return _dbo.calisma_zamani_onarim(
                        _vtk.DOSYA, hata, self.konsol)
                except Exception as _e:
                    self.konsol("DB", f"Onarim denenemedi: {_e}", "uyari")
                    return False
            self._tel_tampon_nesne.onarim_kancasi = _onarim_kancasi

            self.konsol("TEL", f"Dakikalik telemetri tamponu hazir: {dizin}")
            return self._tel_tampon_nesne
        except Exception as e:
            self._tel_tampon_hata = True
            self.konsol("TEL", f"Dosya tamponu kurulamadi, bellek yoluna "
                        f"dusuluyor: {e}", "uyari")
            return None

    def _tel_dron_id_coz(self, kayit):
        """Aktarim aninda `dron_id`'yi cozmeye calisir.

        Ornek yazildiginda kimlik kaydi henuz olusmamis olabilir
        (UID bekleme). Aktarim dakika sonra yapildigi icin bu arada
        kimlik olusmus olabilir; ayni oturumun `oturum_id`'sinden veya
        sysid eslemesinden cozulur.
        """
        oturum_id = kayit.get("oturum_id")
        if oturum_id:
            for sid, oid in getattr(self.dron, "oturum_id", {}).items():
                if oid == oturum_id:
                    did = self.dron.dron_db_id.get(sid)
                    if did:
                        return int(did)
                    did = self._tel_sysid_dron.get(sid)
                    if did:
                        return int(did)
        return None

    def telemetri_tampon_durumu(self):
        """Tanilama: tampon durumunu dondurur (arayuz/log icin)."""
        if self._tel_tampon_nesne is None:
            return {"aktif": False, "bellek_satir": len(self._tel_tampon)}
        d = self._tel_tampon_nesne.durum()
        d["aktif"] = True
        d["bellek_satir"] = len(self._tel_tampon)
        return d

    def _aktif_pilot(self):
        """v2.4.21: o an oturum acik ilk pilotu ve tum listeyi dondurur.

        Dron kimlik kaydi ("kaydeden pilot") ve oturum sahipligi icin
        `dron.py` / `dji_kopru.py` tarafindan cagrilir.
        """
        pilotlar = [p.get("eposta", "") for p in self._ws_pilot.values()
                    if p.get("eposta")]
        ilk = next(iter(self._ws_pilot.values()), {}) or {}
        # v2.4.54: firma_id de tasinir. Dron kimlik kaydi (`dronlar`
        # tablosu) sahipligi bu degerle yazilir; yoksa kayit NULL kalir
        # ve `firma_kosulu()` suzgeci NULL'i HER firmaya gosterdigi icin
        # bir firmanin dronu digerinin listesinde cikar.
        firma_id = None
        try:
            if ilk.get("firma_id"):
                firma_id = int(ilk["firma_id"])
        except (TypeError, ValueError):
            firma_id = None
        return {"eposta": ilk.get("eposta", ""),
                "isim": ilk.get("ad_soyad", "") or ilk.get("isim", ""),
                "firma_id": firma_id,
                "pilotlar": pilotlar}

    # ------------------------------------------------------------------
    # Takipci ayar kalicilik yardimcilari
    # ------------------------------------------------------------------
    def takipci_ayar_yukle(self):
        """Takipci ayarlarini gcs_ayarlar.json'dan yukler."""
        a = self.ayarlar.yukle()
        ta = a.get("takipci", {})
        if ta:
            self.takipci.ayar.from_dict(ta)
            print(f"[TAKIPCI] Ayarlar yuklendi: "
                  f"M={self.takipci.ayar.M}/{self.takipci.ayar.N}, "
                  f"GNN={'ACIK' if self.takipci.ayar.gnn_acik else 'KAPALI'}")

    def takipci_ayar_kaydet(self):
        """Takipci ayarlarini gcs_ayarlar.json'a kaydeder."""
        self.ayarlar.kaydet({"takipci": self.takipci.ayar.to_dict()})

    def siniflandirma_ayar_yukle(self):
        """Siniflandirma ayarlarini gcs_ayarlar.json'dan yukler."""
        sa = self.ayarlar.yukle().get("siniflandirma", {})
        s = self.takipci.siniflandirici.ayar
        if sa:
            s.from_dict(sa)
        print(f"[SINIF] Kural tabanli siniflandirici: "
              f"{'ACIK' if s.acik else 'KAPALI'} "
              f"(min_ornek={s.min_ornek}, histerezis={s.histerezis}, "
              f"esik={s.guven_esigi})")

    def siniflandirma_ayar_kaydet(self):
        """Siniflandirma ayarlarini gcs_ayarlar.json'a kaydeder."""
        self.ayarlar.kaydet(
            {"siniflandirma": self.takipci.siniflandirici.ayar.to_dict()})

    def angajman_param_yukle(self):
        """Kayitli angajman parametrelerini yukler."""
        a = self.ayarlar.yukle().get("angajman", {})
        p = self.angajman.param
        try:
            if "gudum_hz" in a:
                p["gudum_hz"] = max(1, min(4, int(a["gudum_hz"])))
            if "yakalama_mesafe" in a:
                p["yakalama_mesafe"] = max(0.5, min(100.0,
                                                    float(a["yakalama_mesafe"])))
            if "hucum_hizi" in a:
                # v2.4.13: interceptor profili - ust sinir 300 km/h
                p["hucum_hizi"] = max(1.0, min(83.3,
                                               float(a["hucum_hizi"])))
            # v2.4.43: ongoru anahtarlari. `p` artik KALICI sozluktur
            # (angajman.py'de property yerine ornek sozlugu kullaniliyor),
            # bu yuzden buraya yazilan degerler gercekten uygulanir.
            if "gorev_dikkate" in a:
                p["gorev_dikkate"] = bool(a["gorev_dikkate"])
            if "ongoru" in a:
                p["ongoru"] = bool(a["ongoru"])
        except (TypeError, ValueError):
            pass

    def angajman_ayar_kaydet(self):
        """Angajman ayarlarini gcs_ayarlar.json'a kaydeder (v2.4.43)."""
        p = self.angajman.param
        self.ayarlar.kaydet({"angajman": {
            "gudum_hz": p.get("gudum_hz", 2),
            "yakalama_mesafe": p.get("yakalama_mesafe", 2.0),
            "gorev_dikkate": bool(p.get("gorev_dikkate", True)),
            "ongoru": bool(p.get("ongoru", True)),
        }})


    # ------------------------------------------------------------------
    # Yardimcilar
    # ------------------------------------------------------------------
    async def _duyur(self, mesaj: dict):
        """Tum bagli istemcilere JSON mesaji gonderir."""
        veri = json.dumps(mesaj)
        await asyncio.gather(
            *(w.send(veri) for w in list(self.istemciler)),
            return_exceptions=True)

    # ---- v2.4.32: hedefli gonderim (mesajlasma) ----
    #
    # `_duyur` TUM istemcilere gonderir. Mesajlar gizli oldugu icin
    # yalnizca ilgili pilotun oturumlarina yazilmasi gerekir.
    # Ayni pilot birden fazla sekmede olabilir; hepsine gonderilir,
    # aksi halde bir sekmede yazilan mesaj digerinde gorunmez.
    def _pilot_websocketleri(self, eposta):
        ep = str(eposta or "").strip().lower()
        if not ep:
            return []
        bulunan = []
        for w in list(self.istemciler):
            p = self._ws_pilot.get(id(w))
            if p and str(p.get("eposta", "")).lower() == ep:
                bulunan.append(w)
        return bulunan

    async def _pilota_gonder(self, eposta, mesaj: dict):
        """Yalnizca belirtilen pilotun acik oturumlarina gonderir."""
        hedefler = self._pilot_websocketleri(eposta)
        if not hedefler:
            return 0
        veri = json.dumps(mesaj)
        await asyncio.gather(*(w.send(veri) for w in hedefler),
                            return_exceptions=True)
        return len(hedefler)

    async def _firmaya_gonder(self, firma_id, mesaj: dict):
        """Yalnız doğrulanmış aynı firma oturumlarına JSON gönderir."""
        try:
            fid = int(firma_id)
        except (TypeError, ValueError):
            return 0
        hedefler = [w for w in list(self.istemciler)
                    if self._ws_firma_id(w) == fid]
        if not hedefler:
            return 0
        veri = json.dumps(mesaj, ensure_ascii=False)
        await asyncio.gather(*(w.send(veri) for w in hedefler),
                            return_exceptions=True)
        return len(hedefler)

    def goruntu_kare_yayinla(self, firma_id, kayit):
        """HTTP iş parçacığından canlı dron önizlemesini güvenli yayınlar."""
        if self._loop is None or not self.istemciler or not kayit:
            return False
        try:
            yas_ms = max(0, int((time.time() - float(kayit.get("alis_ts"))) * 1000))
        except (TypeError, ValueError):
            yas_ms = 0
        mesaj = {"tur": "dron_goruntu_kare", "kare": {
            "id": kayit.get("id"), "kamera_id": kayit.get("kamera_id"),
            "dron_id": kayit.get("dron_id"), "dron_uid": kayit.get("dron_uid"),
            "sysid": kayit.get("sysid"),
            "ts": kayit.get("ts"), "alis_ts": kayit.get("alis_ts"),
            "yas_ms": yas_ms,
            "lat": kayit.get("lat"),
            "lon": kayit.get("lon"), "irtifa": kayit.get("irtifa"),
            "genislik": kayit.get("genislik"),
            "yukseklik": kayit.get("yukseklik"),
            "url": kayit.get("url") or "",
        }}
        gelecek = asyncio.run_coroutine_threadsafe(
            self._firmaya_gonder(firma_id, mesaj), self._loop)

        def _sonuc(f):
            try:
                adet = int(f.result() or 0)
                fid = int(firma_id)
                onceki = self._goruntu_yayin_hedef_son.get(fid)
                self._goruntu_yayin_hedef_son[fid] = adet
                # Her 1 FPS karede log basılmaz; yalnız 0↔pozitif geçişi
                # kaydedilir. Böylece canlı teslim yolu sahada kanıtlanabilir.
                if onceki is None or bool(onceki) != bool(adet):
                    print("[GORUNTU] Kucuk kare WS hedefi: firma=%d hedef=%d" %
                          (fid, adet))
            except BaseException as e:
                print("[GORUNTU] Kucuk kare WS yayin hatasi: %s" %
                      type(e).__name__)

        gelecek.add_done_callback(_sonuc)
        return True

    async def _firma_yoneticilerine_gonder(self, firma_id, mesaj: dict):
        """Aday olayını yalnız doğrulanmış aynı firma yöneticilerine gönderir.

        Pilotlar ``hedef_liste`` ile salt okunur hedefleri görmeye devam eder;
        hukuki sonuç doğuran angajman penceresi kendiliğinden yalnız yönetici
        rolünde açılır. Yerel kurulumda firma kimliği ``None`` olabilir, fakat
        yine doğrulanmış pilot kaydı ve yönetici rolü zorunludur.
        """
        try:
            fid = int(firma_id) if firma_id is not None else None
        except (TypeError, ValueError):
            return 0
        hedefler = []
        for w in list(self.istemciler):
            p = self._ws_pilot.get(id(w)) or {}
            if p.get("rol") != "yonetici":
                continue
            wf = self._ws_firma_id(w)
            if (fid is None and wf is None) or (fid is not None and wf == fid):
                hedefler.append(w)
        if not hedefler:
            return 0
        veri = json.dumps(mesaj, ensure_ascii=False)
        await asyncio.gather(*(w.send(veri) for w in hedefler),
                            return_exceptions=True)
        return len(hedefler)

    def goruntu_angajman_adayi_yayinla(self, firma_id, baglam):
        """HTTP iş parçacığından taze seçili izi tek-seferlik aday yapar."""
        if self._loop is None or not self.istemciler or not isinstance(baglam, dict):
            return False
        hedef = baglam.get("hedef") or {}
        kal = baglam.get("kalibrasyon") or {}
        try:
            oid = int(baglam.get("ornek_id"))
            kid = int(baglam.get("kamera"))
            iz = int(hedef.get("iz"))
            secim_ts = float(hedef.get("secim_zamani") or 0.0)
        except (TypeError, ValueError):
            return False
        simdi = time.time()
        if (not bool(hedef.get("yerel_secili")) or secim_ts <= 0 or
                secim_ts > simdi + 2.0 or simdi - secim_ts > 30.0):
            return False
        # Seçim zamanı Köprü saatinden App alım saatine göreli yaşla taşındığı
        # için her hedef paketinde milisaniyelik fark gösterebilir. Tekilleştirme
        # firma + doğrulanmış köprü + kamera + iz kimliğine bağlanır; böylece
        # aynı seçili iz 15 saniyelik pencere içinde tekrar aday üretemez.
        anahtar = "%s:%s:%s:%s" % (
            str(firma_id if firma_id is not None else "yerel"),
            oid, kid, iz)
        with self._goruntu_aday_kilit:
            eski = [a for a, ts in self._goruntu_aday_son.items()
                    if simdi - ts > self._goruntu_aday_ttl_sn]
            for a in eski:
                self._goruntu_aday_son.pop(a, None)
            if anahtar in self._goruntu_aday_son:
                return False
            self._goruntu_aday_son[anahtar] = simdi
        hedef_id = "%d:%d:%d" % (oid, kid, iz)
        mesaj = {
            "tip": "goruntu_angajman_adayi",
            "hedef_id": hedef_id,
            "kaynak": {
                "ornek_id": oid,
                "kopru_ad": str(baglam.get("kopru_ad") or "Görüntü Köprüsü")[:160],
                "kamera_id": kid,
                "kamera_ad": "Kamera %d" % kid,
                "iz_id": iz,
                "secim_ts": secim_ts,
                "kaynak_dron_uid": str(kal.get("kaynak_dron_id") or "")[:160],
                "poz_kaynak": str(kal.get("poz_kaynak") or "manuel")[:12],
                "kalibre": bool(kal.get("kalibre")),
                "lat": hedef.get("lat"), "lon": hedef.get("lon"),
                "alt": hedef.get("alt"),
                "konum_guvenilir": bool(hedef.get("konum_guvenilir")),
                "konum_gerekce": str(hedef.get("konum_gerekce") or "")[:240],
            },
        }
        asyncio.run_coroutine_threadsafe(
            self._firma_yoneticilerine_gonder(firma_id, mesaj), self._loop)
        return True

    def _cevrimici_pilotlar(self):
        """O an oturum acik pilot e-postalari (kume).

        Kume kullanilir: ayni pilot birden fazla sekmede olabilir,
        liste sayimi yanlis sonuc verir.
        """
        return {str(p.get("eposta", "")).lower()
                for p in self._ws_pilot.values()
                if p and p.get("eposta")}

    def _pilot_listesi(self, isteyen=None):
        """Sirket ici pilot listesi + cevrimici durumu + okunmamis.

        Bu kurulum tek firmalidir (`kullanicilar` tablosunda firma
        kolonu yoktur), bu nedenle tum kayitli kullanicilar ayni
        sirketin pilotlaridir.
        """
        cevrimici = self._cevrimici_pilotlar()
        okunmamislar = {}
        if self.mesajlar and isteyen:
            okunmamislar = self.mesajlar.sohbet_okunmamislari(isteyen)
        ben = str(isteyen or "").strip().lower()
        liste = []
        for k in (self.kullanicilar.listesi_guvenli() or []):
            ep = str(k.get("eposta", "")).lower()
            if not ep:
                continue
            liste.append({
                "eposta": ep,
                "ad_soyad": k.get("ad_soyad", "") or ep,
                "unvan": k.get("unvan", "") or "",
                "rol": k.get("rol", "") or "",
                "aktif": bool(k.get("aktif", 1)),
                "avatar": k.get("avatar", "") or "",
                "cevrimici": ep in cevrimici,
                "kendisi": ep == ben,
                "okunmamis": int(okunmamislar.get(ep, 0)),
            })
        # Cevrimiciler once, sonra ada gore
        liste.sort(key=lambda x: (not x["cevrimici"],
                                  x["ad_soyad"].lower()))
        return liste

    async def _pilot_durum_duyur(self, eposta, cevrimici):
        """Bir pilotun cevrimici durumu degisince herkese bildirir.

        Not: pilot listesi ALICIYA gore degisir (okunmamis sayaclari
        ve `kendisi` alani). Bu nedenle tek bir liste yayinlanamaz;
        yalnizca DEGISEN pilot bildirilir, istemci kendi listesini
        yerinde guncellenir.
        """
        await self._duyur({"tip": "pilot_durum",
                           "eposta": str(eposta or "").lower(),
                           "cevrimici": bool(cevrimici)})

    async def _ai_izleme_esitle(self, kamera_id):
        """v2.4.8: Kameranin ai_gorevler alanina gore AI izlemesini
        esitler. Gorev seciliyse izlemeyi (yeniden) baslatir, gorevler
        bosaltildiysa aktif izlemeyi durdurur. kamera_kaydet sonrasi
        cagrilir; kullanicinin ayrica izleme baslatmasi gerekmez."""
        if not (self.ai_yonetici and self.kameralar):
            return
        try:
            kamera_id = int(kamera_id)
        except (TypeError, ValueError):
            return
        kamera = self.kameralar.bul(kamera_id)
        if not kamera:
            return
        # v2.4.158: Kamera kaydı AI izlemesini BAŞLATMAZ (manuel kontrol).
        # İzleme YALNIZ çalışıyorsa görev/hassasiyet güncellenir; çalışmıyorsa
        # dokunulmaz (kullanıcı "Başlat" demeden webcam açılmaz).
        gorevler = (kamera.get("ai_gorevler") or "").strip()
        try:
            aktif = {iz["kamera_id"]
                     for iz in self.ai_yonetici.izleme_listesi()}
            if kamera_id not in aktif:
                return
            if gorevler:
                await _db_is_parcasi(
                    self.ai_yonetici.izleme_baslat, kamera_id,
                    "/kamera/%s" % kamera_id, "gcs_proxy", gorevler,
                    kamera.get("ai_hassasiyet") or "")
            else:
                await _db_is_parcasi(
                    self.ai_yonetici.izleme_durdur, kamera_id)
                self.konsol("AI", f"AI izleme durduruldu (kamera"
                            f" #{kamera_id}: gorev secili degil)", "uyari")
        except Exception as e:
            self.konsol("AI", f"Izleme esitleme hatasi (kamera"
                        f" #{kamera_id}): {e}", "hata")
        await self._duyur(
            {"tip": "ai_izleme_listesi",
             "izlemeler": self.ai_yonetici.izleme_listesi()})

    # ------------------------------------------------------------------
    # v2.4.33: HARITA ONBELLEK OZETI YAYINI (durum cubugu)
    # ------------------------------------------------------------------
    # Kullanici istegi: durum cubugunda harita onbellek boyutu dursun ve
    # harita gezildikce / yeni karo indikce guncellensin.
    #
    # TASARIM KISITI
    # Karo indirme saniyede yuzlerce dosya olabilir (ozellikle bolge
    # toplu indirmede). Her karoda WS iletisi gondermek arayuzu bogar ve
    # telemetri ile bant genisligi yarisir. Bu yuzden yayin KISILIR:
    # en fazla `_TILE_OZET_ARALIK` saniyede bir ileti gider. Arada gelen
    # degisiklikler kaybolmaz; bir sonraki yayin en guncel toplami
    # tasidigi icin son deger her zaman dogrudur.
    _TILE_OZET_ARALIK = 2.0

    def _tile_ozet_kur(self):
        """Onbellek ozeti dinleyicisini baglar ve ilk tam olcumu baslatir.

        Ilk olcum ARKA PLANDA yapilir; `os.walk` GB'lik onbellekte
        saniyeler surebilir ve asyncio dongusunu bloklarsa telemetri
        akisi donar.
        """
        from . import tile_cache
        self._tile_ozet_son = 0.0

        def _dinleyici(ozet):
            simdi = time.time()
            # Kisma: hazir olmayan (ilk olcum bitmemis) durum ile
            # temizleme sonrasi sifirlama HER ZAMAN gonderilir; bunlar
            # seyrek olaylardir ve kullaniciya aninda yansimalidir.
            zorla = (not ozet.get("hazir")) or ozet.get("adet", 0) == 0
            if not zorla and simdi - self._tile_ozet_son < self._TILE_OZET_ARALIK:
                return
            self._tile_ozet_son = simdi
            mesaj = dict(ozet)
            mesaj["tip"] = "tile_cache_ozet"
            self.duyur_threadden(mesaj)

        tile_cache.ozet_dinleyici_ekle(_dinleyici)
        tile_cache.toplam_olc(arka_planda=True)

    def duyur_threadden(self, mesaj: dict):
        """v2.4.0: Baska thread'lerden (AI yoklama, HTTP tespit
        endpoint'i) guvenli WS yayini. Ana asyncio dongusune aktarir."""
        if self._loop is None or not self.istemciler:
            return
        try:
            asyncio.run_coroutine_threadsafe(self._duyur(mesaj),
                                             self._loop)
        except RuntimeError:
            pass

    # ------------------------------------------------------------------
    # WS baglanti isleyici
    # ------------------------------------------------------------------
    @staticmethod
    def _ws_yolu(websocket):
        """WS el sikismasindan istek yolunu okur ("/kopru" vb.).

        websockets 17'de yol `websocket.request.path`tedir; eski
        surumlerde dogrudan `websocket.path`. Ikisi de denenir cunku
        paketlenmis kurulumlarda kutuphane surumu sabitlenmemistir.
        """
        istek = getattr(websocket, "request", None)
        if istek is not None:
            return str(getattr(istek, "path", "") or "")
        return str(getattr(websocket, "path", "") or "")

    async def ws_baglanti(self, websocket):
        # Baglanti kopma istisnalari (keepalive ping timeout, ani kapanma,
        # ag degisimi, tablet uykusu vb.) normal olaylardir; yigin izi
        # basilmadan sessizce temizlenir.
        import websockets

        # ------------------------------------------------------------
        # v2.4.67: KOPRU KABUL UCU (kapali devre kurulum)
        # ------------------------------------------------------------
        # Kullanici sarti: "merkez uygulamayi satin alan sirket sinirsiz
        # kullanim hakkina sahip oluyor. isterse KAPALI DEVRE
        # kullanabiliyor." Kapali devrede bulut merkez sureci YOKTUR;
        # bu yuzden kopru kabul dinleyicisi GCS'in kendi WS sunucusunda
        # yasar (bkz. goktungu/kopru_kabul.py modul basligi).
        #
        # AYRI PORT ACILMAZ: kullanici kopru ve Merkez Uygulama'yi AYNI
        # bilgisayarda calistirabilmek istiyor, port butcesi sikidir ve
        # 8443 bazi Windows kurulumlarinda ayricalik hatasi veriyor
        # (olculen log: "[HTTPS] Port 8443 acilamadi ([WinError 10013]").
        # Yol tabanli dallanma mevcut 8765 dinleyicisini yeniden kullanir.
        #
        # KRITIK: soket `self.istemciler`e EKLENMEDEN once dallanir.
        # Eklenirse 10 Hz telemetri yayini kopruye gonderilir, kopru
        # protokolu bozulur ve arayuz istemci sayaci yanlis okunur.
        #
        # YALNIZ LOKAL KURULUMDA ACIK (v2.4.67 guvenlik olcumu):
        # Bulut merkezinde (/app/) kopru kabulu mk_sunucu'nun kendi
        # 9443/9080 ucundadir; GCS'in ucu ORADA GEREKSIZDIR. Olculen
        # canli durum bu ucun kapatilmasini zorunlu kildi:
        #   - GCS WS portu 18765 `0.0.0.0` uzerinde dinliyor
        #   - sunucuda iptables INPUT zinciri BOS (policy ACCEPT)
        #   - nginx 18765'i proxy ETMIYOR, yani port dogrudan disa acik
        # Sonuc: merkez kipinde dallanma acik kalirsa
        # `ws://<sunucu>:18765/kopru` internetten erisilebilir bir kayit
        # ucu olur. Kimlik dogrulamasi var (sir olmadan baglanilamaz)
        # ancak merkezde bu ucun VAR OLMASI bile gereksiz saldiri
        # yuzeyidir; kapali devre kurulumu bundan etkilenmez.
        try:
            _yol = self._ws_yolu(websocket).split("?")[0].rstrip("/")
        except Exception:
            _yol = ""
        if _yol == "/kopru":
            if self._merkez_kipinde():
                # Sessizce kapat: merkezde bu uc YOK. 1008 = policy
                # violation; kopru ajani bunu kalici ret olarak gorur ve
                # yeniden deneme dongusune girmez.
                try:
                    await websocket.close(
                        code=1008,
                        reason="kopru kabul ucu yalniz lokal kurulumda")
                except Exception:
                    pass
                return
            from . import kopru_kabul
            await kopru_kabul.oturum(websocket, self.konsol)
            return

        self.istemciler.add(websocket)
        # v2.3.0: istemci baglanti ayrintilarini yakala (giris_log icin)
        try:
            uzak = getattr(websocket, "remote_address", None) or ("", None)
            # websockets 16.x: basliklar websocket.request.headers'ta;
            # eski surumlerde request_headers dogrudan mevcuttu.
            basliklar = getattr(websocket, "request_headers", None)
            if basliklar is None:
                _req = getattr(websocket, "request", None)
                basliklar = getattr(_req, "headers", None) or {}
            yerel = None
            try:
                yerel = websocket.transport.get_extra_info("sockname")
            except Exception:
                pass
            # KK_APP_WS_v1: kaba kuvvet anahtari icin GERCEK istemci adresi.
            #
            # App vekil zincirinin ARKASINDA calisir ve her istemciyi
            # `127.0.0.1` gorur. Gercek adres `X-Forwarded-For`
            # basligindadir; oraya BIRINCI katman (`_ws_tunel`) yazar
            # ve istemciden geleni ATAR — yani baslik guvenilirdir.
            #
            # Baslik YALNIZ es yerelse dikkate alinir. Dogrudan
            # baglanan saldirgan baslik uydurabilir ama esi yerel
            # olmadigi icin degeri yok sayilir.
            _kk_es = ""
            try:
                _ham = websocket.remote_address
                _kk_es = str(_ham[0]) if _ham else ""
            except BaseException:
                pass
            try:
                if _KK is not None and _kk_es and _KK.yerel_mi(_kk_es):
                    _xff = ""
                    try:
                        _bh = getattr(websocket, "request", None)
                        _bh = getattr(_bh, "headers", None) or {}
                        _xff = str(_bh.get("X-Forwarded-For")
                                   or _bh.get("X-Real-IP") or "")
                    except BaseException:
                        _xff = ""
                    if _xff:
                        _kk_es = _xff.split(",")[0].strip()
            except BaseException:
                pass
            self._ws_istemci[id(websocket)] = {
                "ip": str(uzak[0] or ""),
                "kk_es": _kk_es or str(uzak[0] or ""),
                "port": (int(uzak[1]) if len(uzak) > 1 and uzak[1]
                         else None),
                "yerel_ip": str(yerel[0]) if yerel else "",
                "user_agent": str(basliklar.get("User-Agent") or ""),
                "origin": str(basliklar.get("Origin") or ""),
                "host": str(basliklar.get("Host") or ""),
                "forwarded": str(basliklar.get("X-Forwarded-For") or
                                 basliklar.get("X-Real-IP") or ""),
            }
        except Exception:
            self._ws_istemci[id(websocket)] = {}
        _bi = self._ws_istemci.get(id(websocket), {})
        self.konsol("WS", f"Arayuz baglandi ({len(self.istemciler)} istemci"
                    + (f", {_bi.get('ip')}:{_bi.get('port')}"
                       if _bi.get('ip') else "") + ")")
        try:
            # Baglanir baglanmaz port listesini ve kayitli ayarlari gonder
            await websocket.send(json.dumps(
                {"tip": "portlar", "portlar": self.dron.portlari_listele()}))
            await websocket.send(json.dumps(
                {"tip": "ayarlar", "ayarlar": self.ayarlar.yayin()}))
            if self.baglantilar:
                await websocket.send(json.dumps(
                    {"tip": "baglanti_listesi",
                     "baglantilar": self.baglantilar.listele(
                         firma_id=self._ws_firma_id(websocket)),
                     "durumlar": self._baglanti_durumlari()}))
            if self.rotalar:
                await websocket.send(json.dumps(
                    {"tip": "rota_listesi",
                     "rotalar": self.rotalar.rota_listele()}))
            if self.kameralar:
                await websocket.send(json.dumps(
                    {"tip": "kamera_listesi",
                     "kameralar": self.kameralar.listele()}))
            # v2.4.0: harita kamera ikonlari icin lokasyonlar da gonderilir
            await websocket.send(json.dumps(
                {"tip": "lokasyon_liste",
                 "lokasyonlar": self.lokasyonlar.yukle()}))
            # v2.4.33: durum cubugu harita onbellek gostergesi.
            # `ozet()` disk taramasi yapmaz (bellekteki calisan toplam),
            # bu yuzden baglanti kurulumunu geciktirmez.
            try:
                from . import tile_cache
                _oz = tile_cache.ozet()
                _oz["tip"] = "tile_cache_ozet"
                await websocket.send(json.dumps(_oz))
            except Exception:
                pass
            async for ham in websocket:
                try:
                    k = json.loads(ham)
                except json.JSONDecodeError:
                    continue
                # v2.4.197 OLCULEN KUSUR: komutlar bu dongude SIRAYLA
                # islenir. Sayfa acilisinda siraya giren yavas bir komut
                # (internet yokken merkeze giden bir HTTP istegi gibi)
                # arkasindaki kurulum sihirbazi komutunu (pg_dene) DAKIKA-
                # LARCA bekletiyordu; kullanici "Baglanti dogrulaniyor"
                # dugmesinin kilitlendigini goruyordu. Sihirbaz komutlari
                # artik siradan bagimsiz, ayri gorev olarak islenir.
                _komut_adi = str((k or {}).get("tip") or "")
                if _komut_adi.startswith("pg_"):
                    asyncio.create_task(self._komut_isle_korumali(websocket, k))
                    continue
                _t0 = time.time()
                try:
                    await self._komut_isle(websocket, k)
                    # Teshis: 3 sn'den uzun suren komut gunluge yazilir;
                    # boylece sirayi tikayan komut ADIYLA gorunur.
                    _dt = time.time() - _t0
                    if _dt > 3.0:
                        self.konsol("WS", "YAVAS KOMUT: '%s' %.1f sn surdu "
                                    "(arkasindaki komutlar bekledi)"
                                    % (_komut_adi, _dt), "uyari")
                except websockets.exceptions.ConnectionClosed:
                    # Komut isleme sirasinda istemci koptu
                    break
                except Exception as e:
                    # v2.4.18: tek bir komuttaki hata tum WS baglantisini
                    # dusurmesin; hatayi logla ve dinlemeye devam et.
                    import traceback
                    self.konsol(
                        "WS",
                        f"Komut hatasi ({k.get('tip') if isinstance(k, dict) else '?'}): {e}",
                        "hata")
                    traceback.print_exc()
        except (websockets.exceptions.ConnectionClosed,
                TimeoutError, OSError):
            # Kopan baglanti: normal durum, sessizce ayril
            pass
        finally:
            self.istemciler.discard(websocket)
            # v2.4.32: pilotu esleme SILINDIKTEN sonra duyurmak gerekir;
            # aksi halde _cevrimici_pilotlar() onu hala cevrimici sayar.
            _ayrilan = self._ws_pilot.pop(id(websocket), None)
            self._ws_istemci.pop(id(websocket), None)
            # v2.4.53 Faz 3: firma izolasyon eslemesi de birakilir; aksi
            # halde id(websocket) yeniden kullanildiginda onceki oturumun
            # firmasi yeni oturuma sizabilir.
            self._ws_firma.pop(id(websocket), None)
            if _ayrilan:
                _eposta = str(_ayrilan.get("eposta", "")).strip().lower()
                if _eposta:
                    # Ayni pilotun baska sekmesi acik olabilir; gercek
                    # durum esleme uzerinden yeniden hesaplanir.
                    _hala = _eposta in self._cevrimici_pilotlar()
                    try:
                        await self._pilot_durum_duyur(_eposta, _hala)
                    except Exception:
                        pass
            self.konsol("WS",
                        f"Arayuz ayrildi ({len(self.istemciler)} istemci)")

    def _baglanti_durumlari(self):
        """MAVLink, DJI ve salt-okunur MSP bağlantı durumlarını birleştirir."""
        durumlar = self.dron.durumlar()
        if self.dji_kopru:
            durumlar.update(self.dji_kopru.durumlar())
        if self.betaflight:
            durumlar.update(self.betaflight.durumlar())
        # Merkez kipinde MSP oturumu saha Köprüsünde yaşar. Bu defterde
        # yalnız Köprüden alınan durum özeti tutulur; ham seri veri veya
        # MAVLink benzeri bir dönüşüm kesinlikle tutulmaz.
        durumlar.update(dict(self._betaflight_kopruleri))
        # Otomatik tercih saklanır, fakat algılanan protokol gerçek çalışma
        # durumunun yanında görünür olmalıdır. Bu yalnız tanı bilgisidir;
        # ham seri veri veya komut içeriği içermez.
        for bid, sonuc in self._otomatik_protokoller.items():
            mevcut = dict(durumlar.get(str(bid)) or {})
            mevcut["algilanan_ucus_yazilimi"] = str(
                (sonuc or {}).get("protokol") or "bilinmiyor")
            mevcut["algilama_kaniti"] = str(
                (sonuc or {}).get("kanit") or "")
            durumlar[str(bid)] = mevcut
        return durumlar

    async def _baglanti_listesi_duyur(self):
        """Guncel baglanti listesi + durumlarini istemcilere yayinlar.

        v2.4.53 FIRMA IZOLASYONU: merkezde calisan ornek cok firmalidir,
        bu yuzden TEK mesaj tum istemcilere gonderilemez — bir firma
        digerinin baglantilarini gorurdu. Liste istemcinin firmasina
        gore ayri ayri uretilir. Lokal kurulumda hicbir oturumda
        firma_id olmadigi icin tek liste uretilir ve davranis birebir
        korunur (ek maliyet yok).
        """
        if not self.baglantilar:
            return
        durumlar = self._baglanti_durumlari()
        sitl_ozet = self.sitl.durum_ozeti() if self.sitl else None

        # Firma basina liste onbellegi: ayni firmadan N sekme varsa
        # sorgu bir kez calisir.
        onbellek = {}

        def _mesaj(firma_id):
            if firma_id not in onbellek:
                m = {"tip": "baglanti_listesi",
                     "baglantilar": self.baglantilar.listele(
                         firma_id=firma_id),
                     "durumlar": durumlar}
                if sitl_ozet is not None:
                    # v2.4.39: arayuz sanal baglantinin SITL sureci
                    # gercekten yasiyor mu bilmek zorunda. MAVLink
                    # durumu "dinliyor" iken SITL cokmus olabilir.
                    m["sitl"] = sitl_ozet
                onbellek[firma_id] = json.dumps(m)
            return onbellek[firma_id]

        gorevler = []
        for w in list(self.istemciler):
            gorevler.append(w.send(_mesaj(self._ws_firma_id(w))))
        if gorevler:
            await asyncio.gather(*gorevler, return_exceptions=True)

    async def _firma_bazli_duyur(self, tip, alan, uretici, ek=None):
        """Firma basina ayri uretilen liste mesajini yayinlar.

        v2.4.56: `_baglanti_listesi_duyur` ile ayni gerekcedir — merkezde
        tek surece birden fazla firmanin pilotu baglanir; TEK mesaj
        gonderilirse bir firma digerinin kayitlarini gorur.

        `alan` listenin mesajdaki anahtar adidir (arayuz bu adi bekler;
        turetmeye kalkmak sessiz kusur uretir: kamera_listesi ->
        "kameralar" ama ai_sunucu_listesi -> "sunucular").
        `uretici(firma_id)` o firmaya ait listeyi dondurur. `ek` varsa
        mesaja eklenir (ornegin `{"yeni_id": 5}`). Lokal kurulumda tum
        oturumlarda firma_id None oldugu icin sorgu BIR kez calisir ve
        davranis birebir korunur.
        """
        onbellek = {}

        def _mesaj(firma_id):
            if firma_id not in onbellek:
                m = {"tip": tip}
                if ek:
                    m.update(ek)
                m[alan] = uretici(firma_id)
                onbellek[firma_id] = json.dumps(m)
            return onbellek[firma_id]

        gorevler = [w.send(_mesaj(self._ws_firma_id(w)))
                    for w in list(self.istemciler)]
        if gorevler:
            await asyncio.gather(*gorevler, return_exceptions=True)

    async def _hata_bildir(self, websocket, etiket, ileti):
        """Istemciye tekil hata bildirir ve konsola yazar.

        v2.4.56: kamera/AI kayit yollarinda kopru dogrulamasi hata
        uretebilir. Arayuz `hata_bildirim` mesajini uyari merkezinde
        gosterir (bkz. js/uyari_merkezi.js) — sessizce donmek
        kullanicinin "kaydet bir sey yapmiyor" demesine yol acar.
        """
        self.konsol(etiket, ileti, "hata")
        try:
            await websocket.send(json.dumps(
                {"tip": "hata_bildirim", "kaynak": etiket,
                 "hata": ileti}))
        except Exception:
            pass

    async def _kamera_listesi_duyur(self, yeni_id=None):
        """Kamera listesini firma basina ayri yayinlar."""
        if not self.kameralar:
            return
        ek = {"yeni_id": yeni_id} if yeni_id is not None else None
        await self._firma_bazli_duyur(
            "kamera_listesi", "kameralar",
            lambda fid: self.kameralar.listele(firma_id=fid),
            ek)

    async def _ai_sunucu_listesi_duyur(self):
        """AI sunucu listesini firma basina ayri yayinlar."""
        if not self.ai_yonetici:
            return
        await self._firma_bazli_duyur(
            "ai_sunucu_listesi", "sunucular",
            lambda fid: self.ai_yonetici.listele(firma_id=fid))

    # ------------------------------------------------------------------
    # v2.4.39: sanal dron (gercek ArduPilot SITL) yardimcilari
    # ------------------------------------------------------------------
    @staticmethod
    def _sanal_host_derle(k):
        """Arayuzden gelen sanal_* alanlarini "tip|lat|lon|adet" yapar.

        Dogrulamayi BaglantiYoneticisi yapar; burada yalniz birlestirme var.
        Eksik alanda bos dize donulur -> kayit katmani anlasilir hata verir
        (sessizce varsayilan konuma dusmek, dronun kullanicinin beklemedigi
        yerde dogmasina yol acardi).
        """
        # v2.4.45: alan adlarinda esneklik. Arayuz surumleri arasinda
        # `sanal_lat` / `lat` farki olusabiliyor; ad uyusmazligi eskiden
        # bos host uretip kaydi sessizce dusuruyordu.
        tip = str(k.get("sanal_tip") or k.get("tip_sanal")
                  or k.get("dron_tipi") or "").strip().lower()
        lat = k.get("sanal_lat")
        if lat is None:
            lat = k.get("lat")
        lon = k.get("sanal_lon")
        if lon is None:
            lon = k.get("lon")
        adet = k.get("sanal_adet") or k.get("adet") or 1
        if not tip or lat is None or lon is None:
            return ""
        try:
            return "%s|%s|%s|%d" % (tip, float(lat), float(lon), int(adet))
        except (TypeError, ValueError):
            return ""

    # ------------------------------------------------------------------
    # v2.4.53: merkez sunucu baglantisi yardimcilari
    # ------------------------------------------------------------------
    @staticmethod
    def _merkez_host_derle(k):
        """Arayuzden gelen merkez alanlarini "uid|ad|firma" yapar.

        Dogrulamayi BaglantiYoneticisi yapar; burada yalniz birlestirme
        var. `uid` yoksa bos dize donulur -> cagirici kullaniciya
        anlasilir hata verir. Sessizce bos hedefle kayit acmak, arayuzde
        "var" gorunup asla calismayan bir baglanti uretirdi (v2.4.45
        dersi).

        Alan adlarinda esneklik bilincli: arayuz surumleri arasinda
        `ornek_uid` / `uid` / `sunucu_uid` farki olusabilir; ad
        uyusmazliginin kaydi sessizce dusurmesi kabul edilemez.
        """
        uid = str(k.get("ornek_uid") or k.get("uid")
                  or k.get("sunucu_uid") or "").strip()
        if not uid:
            return ""
        ad = str(k.get("sunucu_ad") or k.get("ad") or "").strip()
        firma = str(k.get("firma") or k.get("firma_unvan") or "").strip()
        # Boru karakteri alan ayiricisidir; adlarda gecerse bicim bozulur.
        return "%s|%s|%s" % (uid.replace("|", " "),
                             ad.replace("|", " "),
                             firma.replace("|", " "))

    # ------------------------------------------------------------------
    # v2.4.53: MERKEZ KOPRU AJANI (ters WebSocket)
    # ------------------------------------------------------------------
    # Merkez, admin panelinden bu kuruluma soru sorar (dron listesi, port
    # listesi, servis durumu, sistem bilgisi). Yanitlar GCS'nin MEVCUT
    # veri yapilarindan uretilir; ayri bir kopya durum tutulmaz — iki
    # kaynak tutmak, panelde gercekten olmayan dronlar gostermeye yol
    # acardi.
    def _kopru_islevleri(self):
        """Merkezin sorabilecegi eylemler -> islev haritasi."""
        return {
            "dron_sayisi": self._k_dron_sayisi,
            "dron_liste": self._k_dron_liste,
            "port_liste": self._k_port_liste,
            "servis_durum": self._k_servis_durum,
            "sistem_bilgi": self._k_sistem_bilgi,
            "baglanti_liste": self._k_baglanti_liste,
            "yetenekler": self._k_yetenekler,
            "durum": self._k_nabiz_eki,
        }

    def _k_dron_sayisi(self, veri=None):
        with self.kilit:
            return len(self.dron.dronlar)

    def _k_dron_liste(self, veri=None):
        """Merkeze dron ozeti. TAM telemetri GONDERILMEZ.

        Yayin paketi dron basina ~60 alan tasir (EKF varyanslari, sensor
        maskeleri, prearm metinleri). Merkez paneli bunlarin hicbirini
        gostermez; her nabizda tasimak bant genisligini bosa harcar ve
        saha baglantisi GSM ise ucus verisiyle yarisir. Bu yuzden yalniz
        panelde gorunen alanlar secilir.
        """
        simdi = time.time()
        dronlar = []
        with self.kilit:
            for d in self.dron.dronlar.values():
                bid = self.dron.sysid_baglanti.get(d.get("sysid"))
                dronlar.append({
                    "sysid": d.get("sysid"),
                    "uid": d.get("uid") or "",
                    "ad": (d.get("kullanici_isim")
                           or d.get("isim") or ""),
                    "tip": d.get("tip") or "",
                    "arac_tipi": d.get("arac_tipi"),
                    "mod": d.get("mod") or "?",
                    "armed": bool(d.get("armed")),
                    "lat": d.get("lat"), "lon": d.get("lon"),
                    "alt_rel": d.get("alt_rel"),
                    "alt_msl": d.get("alt_msl"),
                    "groundspeed": d.get("groundspeed"),
                    "batarya_v": d.get("batarya_v"),
                    "batarya_pct": d.get("batarya_pct"),
                    "gps_fix": d.get("gps_fix"),
                    "uydu": d.get("uydu"),
                    "cevrimici": (simdi - float(d.get("son_mesaj") or 0)) < 8.0,
                    "baglanti_id": str(bid) if bid is not None else "",
                })
        return {"dronlar": dronlar, "adet": len(dronlar)}

    def _k_port_liste(self, veri=None):
        try:
            portlar = self.dron.portlari_listele()
        except Exception as e:
            return {"portlar": [], "hata": f"{type(e).__name__}: {e}"}
        return {"portlar": portlar, "adet": len(portlar)}

    def _k_servis_durum(self, veri=None):
        if self.servis is None:
            return {"destekli": False,
                    "aciklama": "Bu platformda servis yonetimi yok "
                                "(systemd bulunmuyor)."}
        try:
            d = self.servis.ozet()
        except Exception as e:
            return {"destekli": True, "hata": f"{type(e).__name__}: {e}"}
        d["destekli"] = True
        return d

    def _k_sistem_bilgi(self, veri=None):
        import platform as _pf
        bilgi = {
            "platform": _pf.platform(),
            "isletim": _pf.system(),
            "mimari": _pf.machine(),
            "python": _pf.python_version(),
            "makine_adi": _pf.node(),
            "ws_port": self.aktif_ws_port,
            "istemci_sayisi": len(self.istemciler),
            "dron_sayisi": self._k_dron_sayisi(),
            "calisma_dizini": os.getcwd(),
        }
        # v2.4.53: arayuz adresi. Merkez paneli (/app/) operatoru kendi
        # istasyonunun web arayuzune yonlendirir; bunun icin HTTP portunu
        # BILMEK zorunludur. Port TAHMIN EDILEMEZ: HTTP_PORTLAR sirayla
        # denenir (8000, 8080, 8888, 9000, 5500) ve 8000 dolu ise sessizce
        # 8080'e dusulur. Gercek deger `veri/calisma.json`a yazilir
        # (main.py `_port_dosyasi_yaz`), buradan okunur.
        bilgi["http_port"] = None
        bilgi["arayuz_adresleri"] = []
        try:
            import json as _js
            # v2.4.133 / İş 107: yazıcıyla aynı eski/yeni veri yolu
            # sözleşmesi; duz kurulumda <kok>/veri/calisma.json.
            from .sabitler import _veri_alt_yolu
            _yol = _veri_alt_yolu("calisma.json")
            with open(_yol, encoding="utf-8") as _f:
                _c = _js.load(_f)
            if _c.get("http_port"):
                bilgi["http_port"] = int(_c["http_port"])
            # `kesin=False` ise port yalnizca tahmindir; panel bunu
            # kullaniciya "dogrulanmadi" olarak gostermek zorundadir,
            # aksi halde yanlis adrese yonlendirir.
            bilgi["port_kesin"] = bool(_c.get("kesin"))
        except Exception:
            bilgi["port_kesin"] = False
        # Yerel adresler: istasyon NAT arkasindadir, merkezin gordugu
        # `son_ip` cogu zaman kurumsal cikis IP'sidir ve arayuze ERISMEZ.
        # Bu yuzden istasyonun kendi LAN adresleri de bildirilir; operator
        # ayni ag icindeyse bunlardan birine baglanir.
        if bilgi["http_port"]:
            try:
                import socket as _sk
                _p = bilgi["http_port"]
                _adlar = set()
                for _bilgi in _sk.getaddrinfo(_sk.gethostname(), None):
                    _a = str(_bilgi[4][0])
                    # Yalnizca IPv4 ve baglanti-yerel olmayan adresler.
                    if _a.count(".") == 3 and not _a.startswith("127."):
                        _adlar.add(_a)
                for _a in sorted(_adlar):
                    bilgi["arayuz_adresleri"].append(f"http://{_a}:{_p}")
                bilgi["arayuz_adresleri"].append(f"http://127.0.0.1:{_p}")
            except Exception:
                pass
        try:
            from . import __version__ as _v
            bilgi["surum"] = str(_v or "")
        except Exception:
            bilgi["surum"] = ""
        # Telemetri tamponu ve veritabani saglik ozeti: merkez panelinde
        # "kayit akiyor mu" sorusunun tek bakista yanitidir.
        try:
            bilgi["telemetri_tampon"] = self.telemetri_tampon_durumu()
        except Exception:
            pass
        return bilgi

    def _k_baglanti_liste(self, veri=None):
        if self.baglantilar is None:
            return {"baglantilar": [], "durumlar": {}}
        try:
            liste = self.baglantilar.listele()
        except Exception as e:
            return {"baglantilar": [], "durumlar": {},
                    "hata": f"{type(e).__name__}: {e}"}
        return {"baglantilar": liste,
                "durumlar": self._baglanti_durumlari(),
                "adet": len(liste)}

    def _k_yetenekler(self, veri=None):
        """Merkeze bildirilen yetenek bayraklari (panelde rozet olur)."""
        return {
            "dron": self.dron is not None,
            "video": bool(self.kameralar),
            "ai": self.ai_yonetici is not None,
            "radar": self.radar is not None,
            "m50": self.m50 is not None,
            "sitl": self.sitl is not None,
            "servis": self.servis is not None,
            "istasyon2": self.istasyon2 is not None,
        }

    def _k_nabiz_eki(self, veri=None):
        """Her nabizda merkeze giden kucuk durum eki."""
        return {"istemci_sayisi": len(self.istemciler),
                "aktif_baglanti": len(getattr(self.dron, "baglantilar", {}))}

    def _kopru_durum_ozet(self):
        """Arayuze gidecek kopru durumu (sir icermez)."""
        if self.kopru is None:
            try:
                from . import merkez as _merkez
                kayitli = not _merkez.kayit_gerekli_mi()
            except Exception:
                kayitli = False
            return {"yapilandirildi": kayitli, "calisiyor": False,
                    "bagli": False, "son_hata": ""}
        try:
            return self.kopru.durum()
        except Exception as e:
            return {"yapilandirildi": False, "calisiyor": False,
                    "bagli": False, "son_hata": f"{type(e).__name__}: {e}"}

    def _kopru_kur(self):
        """Kopru ajanini olusturur/gunceller ve baslatir (senkron).

        `(basarili, hata)` dondurur. Kayit yoksa `(False, None)` doner:
        bu bir kusur DEGILDIR — merkez kullanmayan kurulumlar normaldir.
        """
        try:
            from . import kopru as _kopru
            from . import merkez as _merkez
        except Exception as e:
            return False, f"Kopru modulu yuklenemedi: {e}"
        kimlik = _merkez.kimlik_oku()
        if not (kimlik.get("kurulum_uid") and kimlik.get("gizli")):
            return False, None
        ayar = _merkez.ayar_coz(self.ayarlar.yukle())
        if not ayar.get("etkin"):
            return False, None
        # Kurulum kimligi surum/platform alanlarini kayit aninda saklar;
        # GCS guncellendiginde merkez eski surumu gorurdu. Her kurulumda
        # tazelenir.
        try:
            from . import __version__ as _v
            kimlik["surum"] = str(_v or kimlik.get("surum") or "")
        except Exception:
            pass
        kimlik.setdefault("platform", _merkez.platform_adi())
        kimlik.setdefault("makine_adi", _merkez.makine_adi())
        if self.kopru is not None and self.kopru.calisiyor():
            eski = self.kopru.kimlik.get("kurulum_uid")
            if eski == kimlik.get("kurulum_uid"):
                self.kopru.kimlik.update(kimlik)
                return True, None
            self.kopru.durdur()
        self.kopru = _kopru.KopruAjani(
            kimlik, islevler=self._kopru_islevleri(),
            gunluk=lambda etiket, metin, sev="bilgi": self.konsol(
                etiket, metin, sev))
        return self.kopru.baslat()

    async def _kopru_yeniden_kur(self):
        """Kopru ajanini asyncio dongusunu bloke etmeden yeniden kurar."""
        loop = asyncio.get_running_loop()
        basarili, hata = await loop.run_in_executor(None, _db_iade_ederek, self._kopru_kur)
        if hata:
            self.konsol("KOPRU", hata, "uyari")
        return basarili

    async def _sanal_hata(self, websocket, hata):
        """Sanal baglanti hatasini hem konsola hem arayuze bildirir.

        v2.4.38'de ogrendigimiz ders: sessizce dusen komut en pahali kusur
        tipi. SITL baslatilamadiginda kullanici NEDEN'i gormek zorunda.
        """
        self.konsol("SITL", hata, "hata")
        try:
            await websocket.send(json.dumps(
                {"tip": "baglanti_hata", "hata": hata}))
        except Exception:
            pass

    async def _sanal_baslat(self, websocket, kayit):
        """Sanal baglantiyi baslatir: SITL sureci + MAVLink dinleme.

        Sanal dron ozel bir kod yolu KULLANMAZ: SITL ayaga kalktiktan sonra
        dron.dinle() normal bir TCP baglantisi gibi baglanir. Boylece
        parametre okuma, gorev yukleme, angajman ve UDP disa aktarim gercek
        dronla birebir ayni kodu kullanir (kullanici istegi).
        """
        if not self.sitl:
            await self._sanal_hata(
                websocket,
                "SITL yoneticisi kurulu degil; sunucuyu yeniden baslatin.")
            return
        from .baglantilar import BaglantiYoneticisi as _BY
        coz = _BY.sanal_coz(kayit)
        if not coz:
            await self._sanal_hata(
                websocket, "Sanal dron kaydi bozuk (tip/konum okunamadi).")
            return
        bid = int(kayit.get("id"))
        try:
            taban = int(kayit.get("port") or 0)
        except (TypeError, ValueError):
            taban = 0
        if taban <= 0:
            from .baglantilar import SANAL_PORT_BASI
            taban = SANAL_PORT_BASI

        # Adet > 1 ise ayni kayit altinda birden fazla SITL ornegi calisir.
        # Her ornek KENDI surecidir (kendi eeprom'u, kendi port blogu) ve
        # ayri bir sysid alir; aksi halde MAVLink tarafinda ayni sysid'li
        # iki arac birbirinin telemetrisini ezerdi.
        adet = int(coz.get("adet") or 1)
        # Konumlari ust uste bindirmemek icin kucuk bir aralik verilir
        # (~30 m). Ayni noktada dogan araclar haritada tek ikon gibi
        # gorunur ve angajman denemelerinde ayirt edilemez.
        AYRIK_DERECE = 0.00027

        # SITL baslatma diski ve agi kullanir, ~2 sn surer; asyncio
        # dongusunu kilitlememek icin is parcacigina alinir.
        basarili = 0
        ilk_hata = None
        for i in range(adet):
            alt_id = bid if i == 0 else self.sitl.alt_kimlik(bid, i)
            lat_i = float(coz["lat"]) + (AYRIK_DERECE * i)
            lon_i = float(coz["lon"])
            # v2.4.40 duzeltmesi: sysid ARTIK kayit id'sinden turetilir.
            #
            # Eski hali `None if adet == 1 else (i + 1)` idi ve iki ayri
            # kusuru birden tasiyordu:
            #   1) adet == 1 iken sysid HIC verilmiyordu -> SITL varsayilani
            #      MAV_SYSID=1 kullaniyordu. Iki ayri sanal baglanti acan
            #      kullanici iki araci da sysid 1 ile goruyordu.
            #   2) adet > 1 iken sayac KAYIT ICI idi (1,2,3...) -> farkli
            #      kayitlarin ornekleri ayni sysid'lere dusuyordu.
            # DronYoneticisi dronlari sysid'e gore sozlukte tuttugu icin
            # sonuc, iki aracin tek dron olarak gorunmesi ve telemetrinin
            # karismasiydi (kullanici bildirdi, olculdu).
            sysid_i = self.sitl.sysid_uret(bid, i)
            taban_i = taban + (i * 10)

            def _isle(_aid=alt_id, _lat=lat_i, _lon=lon_i,
                      _sys=sysid_i, _tb=taban_i, _sira=i):
                return self.sitl.baslat(
                    _aid, coz["tip"], _lat, _lon, _tb, sysid=_sys,
                    sira=_sira)

            port, hata = await asyncio.get_running_loop().run_in_executor(None, _db_iade_ederek, _isle)
            if not port:
                ilk_hata = ilk_hata or hata
                continue

            if i == 0:
                # Kayitli port SITL'in gercekten aldigi porttan farkli
                # olabilir (blok doluysa kaydirilir); kayit guncellenmezse
                # arayuz ve sonraki baslatma yanlis porta bakar.
                if str(port) != str(kayit.get("port")):
                    self.baglantilar.guncelle(bid, port=str(port))
                    kayit = self.baglantilar.bul(bid) or kayit
                url = self.baglantilar.mavutil_url(kayit)
                self.dron.dinle(kayit, url)
            else:
                # Ek ornekler icin ayri bir dinleme kaydi gerekir; kayit
                # veritabanina YAZILMAZ (kullanici tek baglanti gordu),
                # yalniz dinleme icin gecici bir kopya kullanilir.
                #
                # v2.4.43 DUZELTMESI (olculdu): kopyaya YENI BIR `id`
                # verilmeliydi. Eski kod `dict(kayit)` ile ayni `id`'yi
                # tasiyordu ve `dron.dinle()` ilk isi olarak
                # `self.durdur(bid)` cagirdigi icin (dron.py:563) ikinci
                # ornek BIRINCININ dinleyicisini kapatiyor, `self.dronlar`
                # sozlugunden birinci dronu siliyordu (dron.py:588-593).
                #
                # Belirti: iki SITL sureci de calisirken GCS yalniz
                # SONUNCU dronu goruyordu. Gunlukte kanit:
                #   [SITL] ...15710 (pid A) / Baglanti acildi
                #   [SITL] ...15720 (pid B)
                #   [MAVLINK] Baglanti kapatildi   <-- birinci dustu
                # Bu, angajman denemelerini imkansiz kiliyordu (hedef ve
                # saldiran ayni kayit altinda uretilir).
                #
                # `alt_id` zaten SITL sureci icin uretilmis cakismayan ic
                # kimlik (sitl.alt_kimlik: 1_000_000 tabani); dinleme
                # kaydinda da ayni kimlik kullanilir, boylece durdurma
                # yolu (`alt_kimlikler`) ile birebir esler.
                ek = dict(kayit)
                ek["id"] = alt_id
                ek["port"] = str(port)
                url = "tcp:127.0.0.1:%d" % int(port)
                self.dron.dinle(ek, url)
            basarili += 1
            self.konsol("SITL",
                        f"Sanal dron dinleniyor: {kayit.get('isim')}"
                        f"{'' if adet == 1 else ' #' + str(i + 1)} -> {url}",
                        "basari")

        if not basarili:
            await self._sanal_hata(websocket, ilk_hata or "SITL baslatilamadi.")
            return
        if basarili < adet:
            # Kismi basari sessizce gecilemez: kullanici 5 dron bekleyip
            # 2 gorurse nedenini bilmek zorunda.
            await self._sanal_hata(
                websocket,
                f"{adet} sanal drondan {basarili} tanesi baslatildi. "
                f"Ilk hata: {ilk_hata or 'bilinmiyor'}")

    def _dron_durdur_hepsi(self, bid):
        """Bir kayda ait TUM MAVLink dinleyicilerini durdurur.

        v2.4.43: `sanal_adet > 1` olan kayitlar birden fazla dinleyici
        dogurur ve ek ornekler `sitl.alt_kimlik()` ile turetilmis ic
        kimlikler altinda kayitlidir. `dron.durdur(bid)` yalniz ana
        kimligi kapatir; ek dinleyiciler ayakta kalir ve durdurulmus
        sanilan baglantinin dronlari telemetride gorunmeye devam eder.

        `sitl.durdur()` surecleri `alt_kimlikler()` ile toplu olarak
        oldurdugu icin dinleyici tarafi da ayni listeyi kullanmalidir;
        aksi halde iki taraf ayrisir.
        """
        bid = int(bid)
        idler = [bid]
        if self.sitl:
            try:
                idler = self.sitl.alt_kimlikler(bid) or [bid]
            except Exception:
                idler = [bid]
        for k in idler:
            self.dron.durdur(k)

    async def _sitl_durum(self, websocket, tip):
        """FAZ18-DURUM-UCU: tipe ozgu SITL hazirlik durumunu olcer.

        Sihirbazin 2. adimi ONCE bunu sorar. Ikili zaten varsa indirme
        HIC baslamaz; adim "hazir" deyip gecer. Kullanici karari
        (v2.4.45): "gerekli tum dosyalari sisteme bir kere indir,
        sunucuyu baslatmadan once SITL dosyalari zaten sistemde olsun".
        Yani on paketlenmis kurulumda indirme adimi gorunmez olmalidir.

        `hazir_mi()` HER IKI ikiliyi (arducopter + arduplane) arar ve
        biri eksikse False doner. Sihirbaz icin bu FAZLA GENISTIR:
        kullanici coklu pervaneli secmisse `arduplane` eksikligi onu
        ilgilendirmez. Bu yuzden tipe ozgu olcum `ikili_bul()` ile
        yapilir.
        """
        from . import sitl as _sitl
        def _isle():
            yol, model, hata = _sitl.ikili_bul(tip)
            return {
                "hazir": bool(yol),
                "yol": yol or "",
                "model": model or "",
                "hata": hata or "",
            }
        d = await asyncio.get_running_loop().run_in_executor(None, _db_iade_ederek, _isle)
        d["tip"] = "sitl_durum"
        d["sanal_tip"] = tip
        # FAZ18-IS1B-GONDER-ZAMANASIMI: `self._gonder` DIYE BIR YONTEM YOK.
        # Faz 18 sunucu yamasinda bu ad OLCULMEDEN varsayilmisti;
        # AttributeError firlatiyor ve `sitl_durum` yaniti hic
        # gonderilmiyordu. Arayuz yaniti bekledigi icin sihirbaz
        # "denetleniyor..." durumunda sonsuza kaliyordu.
        # WSSunucusu sinifinin gercek tek-istemci yazma deseni
        # dogrudan `websocket.send(json.dumps(...))` (bkz.
        # `_hata_bildir`, `_joystick_tercih_gonder`).
        await websocket.send(json.dumps(d))

    async def _sitl_indir(self, websocket, tip):
        """SITL ikilisini indirir (uzun surer -> is parcaciginda)."""
        from . import sitl as _sitl
        await self._duyur({"tip": "sitl_indirme", "durum": "basladi",
                           "sanal_tip": tip})
        # FAZ18-ILERLEME: is parcacigindan gelen ilerleme bildirimleri
        # ana olay dongusune koprulenir.
        #
        # TUZAK (olculdu): `indir()` `run_in_executor` ile ayri is
        # parcaciginda kosar; `self._duyur` bir esyordamdir. Is
        # parcacigindan dogrudan `await` edilemez, `asyncio.create_task`
        # da "no running event loop" verir. Tek dogru kopru
        # `run_coroutine_threadsafe`dir ve dongu referansi ONCEDEN
        # alinmalidir (is parcaciginda `get_running_loop` yoktur).
        _dongu = asyncio.get_running_loop()
        _son = [0.0]
        def _ilerle(inen, toplam):
            # Kisma: en cok saniyede 4 duyuru. Ham blok basina duyuru
            # 262 KB'lik bloklarla ~28 duyuru/sn uretir ve WS kanalini
            # telemetriyle yarisir hale getirir. Son blok kismadan
            # BAGIMSIZ gecer, yoksa cubuk %97'de asili kalir.
            t = time.monotonic()
            son_blok = bool(toplam) and inen >= toplam
            if (t - _son[0]) < 0.25 and not son_blok:
                return
            _son[0] = t
            try:
                asyncio.run_coroutine_threadsafe(self._duyur({
                    "tip": "sitl_indirme", "durum": "ilerleme",
                    "sanal_tip": tip, "inen": int(inen),
                    "toplam": int(toplam),
                }), _dongu)
            except BaseException:
                pass
        def _isle():
            return _sitl.indir(tip, self.konsol, ilerleme=_ilerle)

        ok, hata = await asyncio.get_running_loop().run_in_executor(None, _db_iade_ederek, _isle)
        await self._duyur({"tip": "sitl_indirme",
                           "durum": "bitti" if ok else "hata",
                           "sanal_tip": tip, "hata": hata})
        if not ok:
            await self._sanal_hata(websocket, hata or "Indirme basarisiz.")

    # ------------------------------------------------------------------
    # Pilot yardimcilari (v2.1.7)
    # ------------------------------------------------------------------
    def _pilot_bilgi(self, websocket):
        """Websocket'e bagli oturum acmis pilotu dondurur (dict|None)."""
        return self._ws_pilot.get(id(websocket))

    # ------------------------------------------------------------------
    # v2.4.50: pilot bazli joystick tercihi
    # ------------------------------------------------------------------
    def _joystick_tercih_oku(self, eposta):
        """Bir pilotun joystick tercihini dondurur (kayit yoksa varsayilan).

        Saklama: `ayarlar` tablosu -> `joystick_pilot` anahtari ->
        {eposta: tercih}. Program geneli TEK ayar YANLIS olur: ayni yer
        istasyonunu birden fazla pilot kullanir ve biri "Mode 1", digeri
        "Mode 2" yerlesimine alisiktir. Kullanicinin istegi de budur:
        "bazi pilotlar farkli kullanabiliyor".
        """
        from . import joystick_ayar
        tum = (self.ayarlar.yukle().get("joystick_pilot") or {})
        if not isinstance(tum, dict):
            tum = {}
        ham = tum.get(str(eposta or "").lower())
        return joystick_ayar.tercih_duzelt(ham)

    def _joystick_tercih_kaydet(self, eposta, tercih):
        """Pilotun tercihini kalici yazar ve duzeltilmis halini dondurur."""
        from . import joystick_ayar
        temiz = joystick_ayar.tercih_duzelt(tercih)
        tum = (self.ayarlar.yukle().get("joystick_pilot") or {})
        if not isinstance(tum, dict):
            tum = {}
        tum[str(eposta or "").lower()] = temiz
        self.ayarlar.kaydet({"joystick_pilot": tum})
        return temiz

    def _joystick_tercih_uygula(self, websocket):
        """Oturum acan pilotun tercihini ManuelKontrol'e yukler.

        Giris aninda cagrilir. Yuklenmezse pilot ayarini kaydeder,
        yeniden giris yapar ve ayar sessizce ETKISIZ kalir — bu tam
        olarak kullanicinin "ayar duruyor ama ise yaramiyor" diyecegi
        durumdur.
        """
        if not self.manuel_kontrol:
            return None
        p = self._pilot_bilgi(websocket) or {}
        eposta = str(p.get("eposta") or "")
        t = self._joystick_tercih_oku(eposta)
        self.manuel_kontrol.tercih_ayarla(t, eposta)
        return t

    async def _joystick_tercih_gonder(self, websocket):
        from . import joystick_ayar
        p = self._pilot_bilgi(websocket) or {}
        eposta = str(p.get("eposta") or "")
        if not eposta:
            await websocket.send(json.dumps(
                {"tip": "joystick_tercih", "basarili": False,
                 "hata": "Oturum bulunamadi."}))
            return
        t = self._joystick_tercih_oku(eposta)
        # Tercihi ayni anda etkin hale getir (arayuz acildiginda
        # sunucudaki degerle arayuzdeki gosterim ayrismasin)
        if self.manuel_kontrol:
            self.manuel_kontrol.tercih_ayarla(t, eposta)
        durum = (self.manuel_kontrol.durum()
                 if self.manuel_kontrol else {})
        await websocket.send(json.dumps({
            "tip": "joystick_tercih", "basarili": True,
            "eposta": eposta, "tercih": t,
            "varsayilan": joystick_ayar.varsayilan_tercih(),
            "joystick": bool(durum.get("joystick")),
            "joystick_adi": durum.get("joystick_adi", ""),
            "istasyon2": bool(durum.get("istasyon2")),
        }))

    async def _joystick_tercih_yaz(self, websocket, k):
        p = self._pilot_bilgi(websocket) or {}
        eposta = str(p.get("eposta") or "")
        if not eposta:
            await websocket.send(json.dumps(
                {"tip": "joystick_tercih_sonuc", "basarili": False,
                 "hata": "Oturum bulunamadi."}))
            return
        t = self._joystick_tercih_kaydet(eposta, k.get("tercih"))
        if self.manuel_kontrol:
            self.manuel_kontrol.tercih_ayarla(t, eposta)
        self._pilot_log(websocket, "ayar", "joystick_tercih",
                        {"ters": t.get("ters"), "olu": t.get("olu"),
                         "egri": t.get("egri"), "olcek": t.get("olcek")})
        await websocket.send(json.dumps(
            {"tip": "joystick_tercih_sonuc", "basarili": True,
             "tercih": t}))

    async def _joystick_kalibre(self, websocket, k):
        """Cubugun o anki ham degerini MERKEZ olarak kaydeder.

        Olculen gercek: olu bolge tek basina yaw kaymasini gidermez.
        0.13 kaymis bir cubukta olu bolge sonrasi hala 0.011 kalir ve
        dron yavas da olsa DONER. Merkez kalibrasyonu kaymayi
        kaynagindan giderir (0.000). Ikisi birlikte kullanilir.
        """
        p = self._pilot_bilgi(websocket) or {}
        eposta = str(p.get("eposta") or "")
        if not eposta:
            await websocket.send(json.dumps(
                {"tip": "joystick_kalibre_sonuc", "basarili": False,
                 "hata": "Oturum bulunamadi."}))
            return
        kaynak = str(k.get("kaynak") or "gamepad")
        if kaynak not in ("gamepad", "pygame"):
            await websocket.send(json.dumps(
                {"tip": "joystick_kalibre_sonuc", "basarili": False,
                 "hata": "Gecersiz kaynak."}))
            return
        # SILME ile KAYDETME ayri yollardir. Silme icin ham degere
        # IHTIYAC YOKTUR; asagidaki "joystick verisi yok" denetimi bu
        # yuzden yalnizca kaydetmeye uygulanir. Canli denemede olculdu:
        # denetim silmeye de uygulandiginda, cubuk takili degilken
        # "Kalibrasyonu sifirla" dugmesi hata veriyor ve pilot yanlis
        # kalibrasyonla mahsur kaliyordu.
        siliniyor = bool(k.get("sil"))
        ham = k.get("ham")
        if not siliniyor:
            if not isinstance(ham, dict) or not ham:
                # Arayuz ham deger vermediyse sunucudaki son deger okunur
                if not self.manuel_kontrol:
                    ham = {}
                elif kaynak == "pygame":
                    ham = self.manuel_kontrol.ham_joystick()
                else:
                    ham = self.manuel_kontrol.tarayici_ham()
            if not ham:
                await websocket.send(json.dumps(
                    {"tip": "joystick_kalibre_sonuc", "basarili": False,
                     "hata": "Joystick verisi yok; cubugu bir kez "
                             "oynatip tekrar deneyin."}))
                return
        if not isinstance(ham, dict):
            ham = {}
        t = self._joystick_tercih_oku(eposta)
        merkez = dict(t.get("merkez") or {})
        if siliniyor:
            for e in ("vx", "vy", "vz", "yaw"):
                merkez.pop("%s_%s" % (kaynak, e), None)
        else:
            for e in ("vx", "vy", "vz", "yaw"):
                try:
                    merkez["%s_%s" % (kaynak, e)] = float(ham.get(e, 0.0))
                except (TypeError, ValueError):
                    continue
        t["merkez"] = merkez
        t = self._joystick_tercih_kaydet(eposta, t)
        if self.manuel_kontrol:
            self.manuel_kontrol.tercih_ayarla(t, eposta)
        self._pilot_log(websocket, "ayar", "joystick_kalibre",
                        {"kaynak": kaynak, "sil": siliniyor,
                         "merkez": merkez})
        await websocket.send(json.dumps(
            {"tip": "joystick_kalibre_sonuc", "basarili": True,
             "kaynak": kaynak, "tercih": t, "silindi": siliniyor}))

    def _dron_uid(self, sysid):
        """v2.4.21: sysid'nin canli UID'sini dondurur ('' ise None).

        Parametre/telemetri kayitlari dogru kalici drona baglanabilsin
        diye kullanilir; sysid tek basina benzersiz degildir.
        """
        try:
            d = self.dron.dronlar.get(int(sysid)) or {}
        except (AttributeError, TypeError, ValueError):
            return None
        return str(d.get("uid") or "") or None

    def _param_kalici_kaydet(self, websocket, sysid, ad, deger,
                             kaynak="gcs"):
        """v2.4.21: Parametre degisikligini kalici tabloya + gecmise yazar.

        `ad` PARAM_HARITASI kisayolu ise ("hareket_hizi" gibi) gercek
        ArduPilot adina ve ham degerine cevrilir; boylece gecmiste daima
        dronun gordugu ad/deger saklanir.
        """
        ad = str(ad or "").strip()
        if not ad or deger is None:
            return
        try:
            tanim = self.dron.PARAM_HARITASI.get(ad)
        except AttributeError:
            tanim = None
        if tanim:
            p_ad, carpan, alt, ust = tanim
            try:
                v = max(alt, min(ust, float(deger))) * carpan
            except (TypeError, ValueError):
                return
            ad, deger = p_ad, v
        try:
            from . import veritabani as _vt
            p = self._pilot_bilgi(websocket) or {}
            _vt.param_cache_deger_guncelle(
                int(sysid), ad, deger, uid=self._dron_uid(sysid),
                kaynak=kaynak, eposta=p.get("eposta", ""),
                isim=p.get("ad_soyad", ""))
        except Exception as e:
            self.konsol("PARAM", f"Parametre kaydi hatasi: {e}", "uyari")

    def _pilot_log(self, websocket, kategori, islem, detay=None):
        """Islemi pilot etiketiyle kalici olarak kaydeder."""
        if not self.pilot:
            return
        p = self._pilot_bilgi(websocket) or {}
        self.pilot.log_yaz(p.get("eposta", ""), p.get("ad_soyad", ""),
                           kategori, islem, detay)

    def _kopru_sahibi_mi(self, ornek_id, firma_id):
        """Verilen kopru gercekten bu firmaya mi ait.

        Kopru kimligi arayuzden gelir; dogrulanmazsa bir firma
        kaydini baska firmanin koprusune baglayip o makinenin
        seri portlarina komut gonderebilir.

        v2.4.67: YEREL KURULUM ARTIK KOPRU KABUL EDER. Onceki surumde
        bu islev `not _mk.etkin()` durumunda kosulsuz False donuyordu
        ("lokal kurulumda kopru kavrami yoktur") ve kapali devre Merkez
        Uygulama'ya bagli kopruye hicbir komut gonderilemiyordu.

        Yerel kurulum TEK FIRMALIdir (Merkez Uygulama'yi satin alan
        sirket), bu yuzden capraz firma sizmasi kavramsal olarak
        imkansizdir; kaydin VARLIGI sahiplik icin yeterlidir.
        """
        try:
            from . import merkez_kimlik as _mk
            if not _mk.etkin():
                return self._yerel_kopru_var_mi(ornek_id)
            if not firma_id:
                return False
            for k in _mk.firma_kopruleri(firma_id) or []:
                if int(k.get("ornek_id") or 0) == int(ornek_id):
                    return True
        except Exception as e:
            print(f"[KOPRU] Sahiplik dogrulanamadi: {e}")
        return False

    @staticmethod
    def _yerel_kopru_var_mi(ornek_id):
        """Yerel kurulumda bu kopru kaydi var ve iptal edilmemis mi."""
        try:
            from . import kopru_kabul
            hedef = int(ornek_id)
            for k in kopru_kabul.kopru_listesi():
                if int(k.get("ornek_id") or 0) == hedef:
                    return True
        except Exception as e:
            print(f"[KOPRU] Yerel sahiplik dogrulanamadi: {e}")
        return False


    # ---- IS91/92: GORUNTU KOPRUSU hedef verisi + angajman kuyrugu ----
    # Bu uclar GORUNTU sunmaz. Yalnizca hedefin NEREDE oldugunu
    # (azimut/yukselis/oncelik) ve operatorun verdigi KARARI tasir.
    async def _hedef_komut(self, websocket, komut, k):
        def _yanit(basarili, hata="", **ek):
            p = {"tip": "hedef_sonuc", "komut": komut,
                 "basarili": bool(basarili), "hata": str(hata)}
            p.update(ek)
            return json.dumps(p, ensure_ascii=False)

        try:
            from . import hedef_deposu as _hd
        except Exception as e:
            await websocket.send(_yanit(
                False, "Hedef modulu yuklenemedi: %s" % e))
            return

        # ---- Yetki ----
        # Hedef LISTESI her pilota aciktir: operatorun sahayi gormesi
        # gerekir. ANGAJMAN KARARI yalnizca yoneticidedir; karar
        # hukuki sorumluluk dogurur ve kim verdigi kayda gecer.
        p = self._pilot_bilgi(websocket) or {}
        rol = p.get("rol")
        eposta = p.get("eposta") or ""
        firma_id = self._ws_firma_id(websocket)
        try:
            from . import merkez_kimlik as _mk_hedef
            merkez_kipi = bool(_mk_hedef.etkin())
        except BaseException:
            merkez_kipi = False
        if merkez_kipi and not firma_id:
            await websocket.send(_yanit(
                False, "Firma oturumu dogrulanamadi."))
            return
        if komut in ("angajman_ekle", "angajman_karar"):
            if rol != "yonetici":
                self.konsol("ANGAJMAN",
                            "Angajman istegi reddedildi (yonetici "
                            "degil): %s" % (eposta or "?"), "uyari")
                await websocket.send(_yanit(
                    False, "Angajman kuyrugunu yalnizca yonetici "
                           "yonetebilir."))
                return

        if komut == "hedef_liste":
            await websocket.send(_yanit(
                True, "", kopruler=_hd.DEPO.listele(firma_id),
                sayim=_hd.DEPO.sayim(firma_id)))
            return

        if komut == "angajman_liste":
            durum = k.get("durum") or None
            await websocket.send(_yanit(
                True, "", kayitlar=_hd.KUYRUK.listele(durum, firma_id),
                sayim=_hd.KUYRUK.sayim(firma_id)))
            return

        if komut == "angajman_ekle":
            istek_hedef = k.get("hedef")
            if not isinstance(istek_hedef, dict) or istek_hedef.get("iz") is None:
                await websocket.send(_yanit(
                    False, "Hedef verisi eksik."))
                return
            hedef = _hd.DEPO.hedef_bul(
                k.get("ornek_id"), k.get("kamera"),
                istek_hedef.get("iz"), firma_id)
            if not hedef:
                await websocket.send(_yanit(
                    False, "Hedef bulunamadi, bayat veya firma kapsami disinda."))
                return
            if not hedef.get("konum_guvenilir"):
                await websocket.send(_yanit(
                    False, hedef.get("konum_gerekce") or
                    "Hedef konumu guvenilir degil."))
                return
            kayit = _hd.KUYRUK.ekle(k.get("ornek_id"), k.get("kamera"),
                                    hedef, eposta, firma_id)
            self.konsol("ANGAJMAN",
                        "Kuyruga alindi: iz %s (%s) -- %s"
                        % (hedef.get("iz"), hedef.get("tur"),
                           eposta or "?"))
            self._pilot_log(websocket, "ANGAJMAN", "kuyruga_al",
                            {"kayit_id": kayit.get("id"),
                             "iz": hedef.get("iz"),
                             "tur": hedef.get("tur")})
            await websocket.send(_yanit(
                True, "", kayit=kayit,
                sayim=_hd.KUYRUK.sayim(firma_id)))
            return

        if komut == "angajman_karar":
            try:
                kid = int(k.get("id") or 0)
            except (TypeError, ValueError):
                kid = 0
            if kid <= 0:
                await websocket.send(_yanit(False, "Gecersiz kayit."))
                return
            kayit, hata = _hd.KUYRUK.karar(
                kid, str(k.get("durum") or ""), eposta,
                str(k.get("aciklama") or ""), firma_id)
            if hata:
                await websocket.send(_yanit(False, hata))
                return
            self.konsol("ANGAJMAN",
                        "Karar: kayit %s -> %s (%s)"
                        % (kid, kayit.get("durum"), eposta or "?"),
                        "uyari")
            self._pilot_log(websocket, "ANGAJMAN", "karar",
                            {"kayit_id": kid,
                             "durum": kayit.get("durum"),
                             "iz": kayit.get("iz")})
            await websocket.send(_yanit(
                True, "", kayit=kayit,
                sayim=_hd.KUYRUK.sayim(firma_id)))
            return

        await websocket.send(_yanit(False, "Bilinmeyen komut."))

    def _goruntu_angajman_dogrula(self, websocket, istek, saldiran, hedef_id):
        """İş 99 görüntü angajmanını motor çağrısından önce kapalı doğrular.

        Dönen bağlam yalnız sunucu depolarından üretilir. İstemcinin kaynak
        alanları karar kaynağı değildir; yalnız yeniden oynatma/bağlam değiştirme
        girişimini yakalamak için depodaki değerlerle karşılaştırılır.
        """
        pilot = self._pilot_bilgi(websocket) or {}
        if pilot.get("rol") != "yonetici":
            return None, "Görüntü angajmanını yalnızca yönetici başlatabilir."
        firma_id = self._ws_firma_id(websocket)
        try:
            from . import merkez_kimlik as _mk_goruntu
            merkez_kipi = bool(_mk_goruntu.etkin())
        except BaseException:
            merkez_kipi = False
        if merkez_kipi and not firma_id:
            return None, "Firma oturumu doğrulanamadı."
        try:
            parca = str(hedef_id).split(":")
            if len(parca) != 3:
                raise ValueError
            oid, kid, iz = int(parca[0]), int(parca[1]), int(parca[2])
            istek_oid = int(istek.get("kaynak_kopru_id"))
            istek_kid = int(istek.get("kaynak_kamera_id"))
            istek_iz = int(istek.get("kaynak_iz_id"))
            istek_secim = float(istek.get("kaynak_secim_ts"))
        except (TypeError, ValueError):
            return None, "Görüntü hedefi kaynak bağlamı eksik veya geçersiz."
        if min(oid, kid, iz, saldiran) <= 0:
            return None, "Görüntü hedefi veya icra dronu geçersiz."
        if (oid, kid, iz) != (istek_oid, istek_kid, istek_iz):
            return None, "Köprü/kamera/iz bağlamı hedef kimliğiyle uyuşmuyor."
        if not self._kopru_sahibi_mi(oid, firma_id):
            return None, "Seçilen Görüntü Köprüsü bu firmaya ait değil."
        try:
            from . import hedef_deposu as _hd_goruntu
            baglam = _hd_goruntu.DEPO.hedef_baglam_bul(
                oid, kid, iz, firma_id=firma_id)
        except BaseException:
            baglam = None
        if not baglam:
            return None, "Hedef kayıp, bayat veya firma kapsamı dışında."
        hedef = baglam.get("hedef") or {}
        kal = baglam.get("kalibrasyon") or {}
        try:
            secim_ts = float(hedef.get("secim_zamani") or 0.0)
        except (TypeError, ValueError):
            secim_ts = 0.0
        simdi = time.time()
        if not bool(hedef.get("yerel_secili")):
            return None, "Hedef yerel tam ekran görüntüde seçilmemiş."
        if (secim_ts <= 0 or secim_ts > simdi + 2.0 or
                simdi - secim_ts > 30.0):
            return None, "Yerel hedef seçimi bayat; hedefi yeniden seçin."
        if abs(istek_secim - secim_ts) > 0.001:
            return None, "Yerel seçim zamanı güncel hedefle uyuşmuyor."
        if not bool(kal.get("kalibre")):
            return None, "Kamera kalibre değil."
        if not bool(hedef.get("konum_guvenilir")):
            return None, str(hedef.get("konum_gerekce") or
                             "Hedef konumu güvenilir değil.")
        if hedef.get("lat") is None or hedef.get("lon") is None:
            return None, "Hedef coğrafi konumu çözülemedi."
        poz_kaynak = str(kal.get("poz_kaynak") or "manuel").lower()
        if (poz_kaynak == "dron" and
                str(kal.get("gimbal_kipi") or "govdeye_sabit").lower() !=
                "govdeye_sabit"):
            return None, "Gimbal telemetrisi olmadan görüntü angajmanı yapılamaz."

        with self.kilit:
            dron = dict(self.dron.dronlar.get(int(saldiran)) or {})
        if not dron:
            return None, "İcra dronu bağlı değil."
        try:
            son_mesaj = float(dron.get("son_mesaj") or 0.0)
        except (TypeError, ValueError):
            son_mesaj = 0.0
        if son_mesaj <= 0 or simdi - son_mesaj > 8.0:
            return None, "İcra dronu telemetrisi bayat."
        dron_uid = str(dron.get("uid") or self._dron_uid(saldiran) or "").strip()
        if not dron_uid:
            return None, "İcra dronunun kalıcı UID bilgisi yok."
        if firma_id:
            try:
                from . import veritabani as _vt_goruntu
                izinli = _vt_goruntu.dron_kaynaklari_listele(firma_id) or []
            except BaseException:
                izinli = []
            if not any(str(d.get("uid") or "").strip() == dron_uid
                       for d in izinli if isinstance(d, dict)):
                return None, "İcra dronu bu firmaya ait değil."
        kaynak_uid = str(kal.get("kaynak_dron_id") or "").strip()
        if poz_kaynak == "dron":
            if not kaynak_uid:
                return None, "Kamera kaynak dron UID bilgisi yok."
            if dron_uid != kaynak_uid:
                return None, "Drona bağlı kamera için icra dronu kamera dronuyla aynı olmalıdır."
        baglam["firma_id"] = firma_id
        baglam["icra_dron_uid"] = dron_uid
        baglam["hedef_id"] = "%d:%d:%d" % (oid, kid, iz)
        return baglam, ""

    def _kopru_listesi_birlesik(self, firma_id=None):
        """Kopru listesini kipten BAGIMSIZ dondurur.

        Merkez kipinde merkez veritabanindan (`firma_kopruleri`), yerel
        kipte GCS'in kendi `yerel_kopruler` tablosundan okur. Cagiran
        taraflarin kip denetimi yapmasi gerekmez; iki yolun ayni sozluk
        bicimini dondurmesi bu islevin sozlesmesidir.
        """
        try:
            from . import merkez_kimlik as _mk
            if _mk.etkin():
                if not firma_id:
                    return []
                return _mk.firma_kopruleri(firma_id) or []
            from . import kopru_kabul
            return kopru_kabul.kopru_listesi()
        except Exception as e:
            print(f"[KOPRU] Liste okunamadi: {e}")
            return []

    def _ws_firma_id(self, websocket):

        """Oturumun firma_id degeri (yoksa None).


        Veri sorgularinda firma izolasyonu icin kullanilir.

        """

        try:

            _fid = self._ws_firma.get(id(websocket))

            if _fid:

                return _fid

        except Exception:

            pass

        # IS44_OTURUM_GERIDUSUS_v1: `_ws_firma` SOKET BASINA tutulur.

        # Arayuz ayni anda birden fazla WS soketi acabiliyor

        # (ucus duvari, video duvari, ikinci sekme). Giris yapan

        # soket ile komutu gonderen soket farkli oldugunda firma

        # kimligi bos kaliyordu. Pilot kaydi ayni soket icin

        # zaten tutuluyor; oradan turetip onbellege yaziyoruz.

        try:

            _kul = self._ws_pilot.get(id(websocket)) or {}

            _pf = _kul.get("firma_id")

            if _pf:

                _pf = int(_pf)

                self._ws_firma[id(websocket)] = _pf

                return _pf

        except Exception:

            pass

        return None


    # ------------------------------------------------------------------
    # v2.4.53 Faz 11: `merkez` turu baglantilar icin ham MAVLink akisi
    # ------------------------------------------------------------------
    @staticmethod
    def _kopru_uzerinde_mi(kayit):
        """Kayit bir KOPRU makinesinde mi acilmali? (True/False)

        Iki durum vardir:

        * `tur == "merkez"` — v2.4.53'te eklenen ozel tur; hedef makine
          `host` alaninda kodlu. Geriye donuk uyum icin korunur.
        * `kopru_ornek_id` dolu — v2.4.55: her tur (seri/tcp/udp) bir
          saha makinesine baglanabilir. Kaydin turu artik NEREDE degil
          NASIL baglanildigini soyler.

        `sanal` ve `dji` bu yola girmez: ilkini merkez kendi surecinde
        calistirir, ikincisi kendi koprusunu isletir.
        """
        k = kayit or {}
        if str(k.get("tur") or "").lower() == "merkez":
            return True
        try:
            return int(k.get("kopru_ornek_id") or 0) > 0
        except (TypeError, ValueError):
            return False

    # ------------------------------------------------------------------
    # v2.4.59: GCCDUAL CANTASI KOPRU MAKINESINDE ACILIR
    #
    # Kullanici bildirimi: "GCS icinde kopru kurulu olan makinede porta
    # baglanmali, sanirim su an sunucu da ariyor portu, GCS
    # bilgisayarinda aslinda ttyACM0 var".
    #
    # Merkez sunucusunun seri portu YOKTUR. Onceki surumde "Yer
    # Istasyonu 2" panelinin Baglan/Portlari tara dugmeleri merkezin
    # kendi surecinde `self.istasyon2` uzerinden calisiyordu; sonuc
    # `[Errno 2] could not open port /dev/ttyACM0` uyarisinin 2 saniyede
    # bir yinelenmesiydi. Canta pilotun makinesine takilidir, yani
    # koprunun kostugu makineye.
    #
    # LOKAL KURULUM DEGISMEZ: `_merkez_kipinde()` false ise `self.
    # istasyon2` yolu birebir korunur. Ayni GCS ikilisi iki kipte de
    # calisir ve lokal kullanicinin cantasi merkez uzerinden dolasmaz.
    # ------------------------------------------------------------------
    async def _gcsdual_kopru_sec(self, websocket, istenen=None):
        """Cantanin bulundugu kopruyu secer. Donus: `(ornek_id, hata)`.

        Secim siralamasi:

        1. Arayuz acikca bir kopru bildirdiyse (`kopru_ornek_id`) o
           kullanilir — pilot birden fazla saha makinesi isletiyorsa
           kararin sahibi pilottur.
        2. Bildirmediyse `gcsdual` servisi CALISAN cevrimici kopruler
           taranir. Tam bir tane varsa o secilir.
        3. Birden fazla varsa SECIM ZORUNLU kilinir. Rastgele birini
           secmek, pilotun A cantasini kalibre ederken B cantasina
           komut gondermesi demektir.

        Yetki her durumda `_kopru_sahibi_mi` ile dogrulanir.

        v2.4.60: govde `_kopru_servis_sec` ortak yardimcisina tasindi.
        Radar ayni secim mantigini kullanir; iki kopya tutmak, birinde
        yapilan duzeltmenin digerine gecmemesi riskini dogurur.
        """
        return await self._kopru_servis_sec(
            websocket, "gcsdual", istenen,
            servis_adi="GroundGCC Sunucusu")

    async def _gcsdual_kopru_cagir(self, websocket, eylem, veri=None,
                                   istenen_kopru=None, zaman_asimi=10.0):
        """GCCDUAL eylemini kopru makinesinde calistirir.

        Donus: `(veri, hata)`. Kopru yanitindaki `tamam=False` durumu da
        HATA olarak dondurulur; arayuzun iki ayri basarisizlik bicimiyle
        ugrasmasi gerekmez.
        """
        oid, hata = await self._gcsdual_kopru_sec(websocket, istenen_kopru)
        if oid is None:
            return None, hata
        sonuc, hata = await self._kopruye_sor_async(
            oid, websocket, eylem, veri or {}, zaman_asimi=zaman_asimi)
        if hata:
            return None, hata
        sonuc = sonuc if isinstance(sonuc, dict) else {}
        if not sonuc.get("tamam", True):
            return None, str(sonuc.get("hata") or "Saha makinesi komutu "
                                                 "uygulayamadi.")
        sonuc["kopru_ornek_id"] = oid
        return sonuc, ""

    # ------------------------------------------------------------------
    # v2.4.60: C20 RADAR KOPRU MAKINESINDE ACILIR
    #
    # Kullanici bildirimi: "radarda da ayni sorun var, radarin kopru
    # yazilimi calisiyor ama sistem radari sunucuda ariyor".
    #
    # Radar donanimi sahadaki YEREL agda durur (ornegin 192.168.8.168).
    # Merkez sunucu bu ozel ag adresine ULASAMAZ; panelin "RADARA BAGLAN"
    # dugmesi merkezdeki `self.radar` nesnesini cagirdigi icin sonuc her
    # zaman "HATA / timed out" oluyordu.
    #
    # LOKAL KURULUM DEGISMEZ: `_merkez_kipinde()` false ise `self.radar`
    # yolu birebir korunur. Ayni GCS ikilisi iki kipte de calisir.
    # ------------------------------------------------------------------
    async def _radar_kopru_sec(self, websocket, istenen=None):
        """Radarin bagli oldugu kopruyu secer. Donus: `(ornek_id, hata)`.

        Secim GCCDUAL ile ayni siralamayi izler: acik bildirim > tek
        aday > secim zorunlu. Birden fazla saha makinesinde radar
        calisiyorsa rastgele secmek, operatorun A radarinin esigini
        degistirdigini sanirken B radarini ayarlamasi demektir.
        """
        return await self._kopru_servis_sec(
            websocket, "radar", istenen,
            servis_adi="Radar Sunucusu")

    async def _radar_kopru_cagir(self, websocket, eylem, veri=None,
                                 istenen_kopru=None, zaman_asimi=10.0):
        """Radar eylemini kopru makinesinde calistirir.

        Donus: `(veri, hata)`. Kopru yanitindaki `tamam=False` durumu da
        HATA olarak dondurulur; arayuzun iki ayri basarisizlik bicimiyle
        ugrasmasi gerekmez.
        """
        oid, hata = await self._radar_kopru_sec(websocket, istenen_kopru)
        if oid is None:
            return None, hata
        sonuc, hata = await self._kopruye_sor_async(
            oid, websocket, eylem, veri or {}, zaman_asimi=zaman_asimi)
        if hata:
            return None, hata
        sonuc = sonuc if isinstance(sonuc, dict) else {}
        if not sonuc.get("tamam", True):
            return None, str(sonuc.get("hata") or "Saha makinesi komutu "
                                                 "uygulayamadi.")
        sonuc["kopru_ornek_id"] = oid
        return sonuc, ""

    async def _radar_kopruye(self, websocket, eylem, veri, k=None):
        """Radar eylemini kopruye gonderir ve sonucu panele bildirir.

        Hata durumunda `self.radar.durum` uzerine HATA metni yazilir.
        Bunun nedeni panelin "RADAR DURUMU" alanini bu sozlukten
        okumasidir: hata yalniz uyari balonunda gosterilse, panel
        "baglaniyor" yazip sonsuza kadar oyle kalirdi.
        """
        istenen = None
        rid = None
        if isinstance(k, dict):
            istenen = k.get("kopru_ornek_id")
            rid = k.get("radar_id")
        # v2.4.192 (Faz C): radar kimligi KOPRUYE tasinir (Kopru 1.7.19
        # radar_id basina ayri C20 istemcisi calistirir). Kayittaki
        # kopru ornegi (radarlar.kopru_ornek_id) verilmisse o kopru secilir.
        ist = self._radar_istemci(rid)
        try:
            rid_int = int(getattr(ist, "radar_id", None) or rid or 1)
        except (TypeError, ValueError):
            rid_int = 1
        veri = dict(veri or {})
        veri.setdefault("radar_id", rid_int)
        if not istenen and hasattr(self.radar, "kayitlar"):
            try:
                kayit = self.radar.kayitlar.bul(rid_int) or {}
                istenen = kayit.get("kopru_ornek_id") or None
            except Exception:
                istenen = None
        sonuc, hata = await self._radar_kopru_cagir(
            websocket, eylem, veri, istenen_kopru=istenen)
        # Radar nesnesi kurulmamis olabilir (ornegin radar kapali bir
        # kurulum). Durum yazimi bu yuzden korumali yapilir; aksi halde
        # panele hata bildirmek yerine komut isleyici cokerdi.
        durum = getattr(ist if ist is not None else self.radar, "durum", None)
        if not isinstance(durum, dict):
            durum = None
        if hata:
            if durum is not None:
                with self.kilit:
                    durum["durum"] = "hata"
                    durum["hata"] = hata
                    if eylem == "radar_rtk":
                        durum["rtk_durum"] = "hata"
            self.konsol("RADAR", hata, "hata")
            await self._uyari_gonder(websocket, "RADAR", hata, "hata")
            return None
        if eylem == "radar_baglan":
            # Baglanma ISTEGI iletildi; gercek el sikisma sahada surer.
            # Panel "baglaniyor" gostermeli, "bagli" DEGIL: LOGIN yaniti
            # gelmeden bagli demek, operatoru olmayan bir radara
            # guvendirir.
            if durum is not None:
                with self.kilit:
                    durum["durum"] = "baglaniyor"
                    durum["hata"] = ""
                    durum["ip"] = str((veri or {}).get("ip") or "")
                    try:
                        durum["port"] = int((veri or {}).get("port") or 0)
                    except (TypeError, ValueError):
                        pass
        elif eylem == "radar_rtk":
            if durum is not None:
                with self.kilit:
                    durum["rtk_durum"] = "aliniyor"
                    durum["rtk_ilerleme"] = 0
        return sonuc

    # ------------------------------------------------------------------
    # v2.4.190 — COKLU RADAR yardimcilari
    # ------------------------------------------------------------------
    def _radar_istemci(self, radar_id=None):
        """radar_id'ye gore istemci; RadarYoneticisi yoksa tek nesne."""
        if hasattr(self.radar, "istemci"):
            return self.radar.istemci(radar_id)
        return self.radar

    def _radar_birincil_mi(self, radar_id=None) -> bool:
        """v2.4.192 (Faz C): merkez kipinde HER radar kopru yolundan
        gider (Kopru 1.7.19 coklu radar). Islev geriye uyum icin durur."""
        return True

    # ------------------------------------------------------------------
    # M50 ELEKTRO-OPTİK — SAHA KÖPRÜSÜ VEKİL KOMUTLARI
    # ------------------------------------------------------------------
    _M50_IZINLI_EYLEMLER = frozenset((
        "durum", "ayar_oku", "ayar_yaz", "baglan", "kes", "ptz", "lens",
        "aci_konumla", "takip_sec", "takip_baslat", "takip_durdur",
        # v2.4.188: SDK'nın geri kalanı
        "aci_oku", "onayar_liste", "onayar_kaydet", "onayar_cagir",
        "onayar_sil", "onayar_hepsini_sil", "tarama", "takip_yetenek",
    ))
    # Yalnız yerel (köprüsüz) modda anlamlı: köprüye asla iletilmez.
    _M50_YEREL_EK_EYLEMLER = frozenset(("baglan_kayitli",))

    async def _m50_kopru_sec(self, websocket, istenen=None):
        """M50'nin çalıştığı tek yetkili saha Köprüsünü seçer."""
        return await self._kopru_servis_sec(
            websocket, "m50", istenen, servis_adi="M50 Elektro-Optik Servisi")

    async def _m50_kopru_cagir(self, websocket, eylem, veri=None,
                                istenen_kopru=None, zaman_asimi=12.0):
        """M50 eylemini yalnız seçili saha Köprüsüne yönlendirir.

        M50 SDK/DLL veya fiziksel ağ oturumu bu süreçte hiçbir zaman açılmaz.
        """
        if eylem not in self._M50_IZINLI_EYLEMLER:
            return None, "M50 için izin verilmeyen komut"
        oid, hata = await self._m50_kopru_sec(websocket, istenen_kopru)
        if oid is None:
            return None, hata
        sonuc, hata = await self._kopruye_sor_async(
            oid, websocket, "m50_" + eylem, veri or {}, zaman_asimi=zaman_asimi)
        if hata:
            return None, hata
        sonuc = sonuc if isinstance(sonuc, dict) else {}
        if not sonuc.get("tamam", True):
            return None, str(sonuc.get("hata") or "Saha Köprüsü M50 komutunu uygulayamadı.")
        sonuc["kopru_ornek_id"] = oid
        return sonuc, ""

    # v2.4.191: COKLU EO — komuttaki eo_id'ye gore vekil/yerel cifti.
    def _eo_vekil(self, k=None):
        eo = getattr(self, "eo", None)
        if eo is not None:
            return eo.vekil(k.get("eo_id") if isinstance(k, dict) else None)
        return getattr(self, "m50", None)

    def _eo_yerel(self, k=None):
        eo = getattr(self, "eo", None)
        if eo is not None:
            return eo.yerel(k.get("eo_id") if isinstance(k, dict) else None)
        return getattr(self, "m50_yerel", None)

    async def _m50_yerelden(self, websocket, eylem, veri=None, k=None):
        """M50 komutunu Merkez'in kendi gömülü SDK'sıyla (köprüsüz) uygular.

        SDK çağrıları senkron/bloklayıcı olduğu için asyncio döngüsünü
        kilitlememek adına `asyncio.to_thread` ile ayrı iş parçacığında
        çalıştırılır — `ai_track_baslat/durdur` ile aynı desen.
        """
        yerel = self._eo_yerel(k)
        hedef = self._eo_vekil(k)
        try:
            sonuc = await asyncio.to_thread(yerel.uygula, eylem, veri or {})
        except Exception as exc:
            hata = str(exc)[:256] or "M50 komutu uygulanamadı"
            if hedef is not None:
                with self.kilit:
                    hedef.durum.update({"durum": "hata", "bagli": False,
                                         "hata": hata, "ip": "", "port": 0})
            self.konsol("M50", hata, "hata")
            await self._uyari_gonder(websocket, "M50", hata, "hata")
            return None
        if hedef is not None and isinstance(sonuc, dict):
            hedef._uygula(sonuc)
        return sonuc

    async def _m50_kopruye(self, websocket, eylem, veri=None, k=None):
        """M50 komutunu uygular: köprüsüz mod kullanılabilirse ONU, aksi
        halde saha Köprüsünü seçer. Sır içeren veriyi hiçbir durumda
        günlüğe/duruma yazmaz."""
        yerel = self._eo_yerel(k)
        if yerel is not None and yerel.kullanilabilir():
            return await self._m50_yerelden(websocket, eylem, veri, k)
        if eylem in self._M50_YEREL_EK_EYLEMLER:
            await self._uyari_gonder(
                websocket, "M50",
                "Kayıtlı kimlikle bağlanma yalnız köprüsüz modda çalışır; "
                "IP, port, kullanıcı adı ve parolayı girin.", "hata")
            return None
        istenen = k.get("kopru_ornek_id") if isinstance(k, dict) else None
        hedef = self._eo_vekil(k)
        # v2.4.192 (Faz C): cihaz kimligi KOPRUYE tasinir (Kopru 1.7.19
        # eo_id basina ayri SDK istemcisi). Kayittaki kopru ornegi
        # (eo_cihazlar.kopru_ornek_id) verilmisse o kopru secilir.
        try:
            eid = int(getattr(hedef, "eo_id", None) or 1)
        except (TypeError, ValueError):
            eid = 1
        veri = dict(veri or {})
        veri.setdefault("eo_id", eid)
        _eo = getattr(self, "eo", None)
        if not istenen and _eo is not None:
            try:
                kayit = _eo.kayitlar.bul(eid) or {}
                istenen = kayit.get("kopru_ornek_id") or None
            except Exception:
                istenen = None
        sonuc, hata = await self._m50_kopru_cagir(
            websocket, eylem, veri, istenen_kopru=istenen)
        if hata:
            if hedef is not None:
                with self.kilit:
                    hedef.durum.update({"durum": "hata", "bagli": False,
                                         "hata": str(hata)[:256],
                                         "ip": "", "port": 0})
            self.konsol("M50", hata, "hata")
            await self._uyari_gonder(websocket, "M50", hata, "hata")
            return None
        if hedef is not None and eylem == "baglan":
            # Bağlan komutu kabul edildi; el sıkışma sonucunu saha durumundan
            # bekleriz. Kullanıcı adı/parola hiçbir durumda Merkez belleğine
            # durum olarak yazılmaz.
            with self.kilit:
                hedef.durum.update({"durum": "baglaniyor", "bagli": False,
                                     "hata": "", "ip": "", "port": 0})
        return sonuc

    def _m50_kopru_durum_cek(self):
        """Köprüden M50 durumunu çeker; SDK çağırmaz ve istisna yaymaz."""
        return self._saha_durum_cek_guvenli(
            "m50", "m50_durum", "M50 Elektro-Optik Servisini")

    # ------------------------------------------------------------------
    # v2.4.59 — RADAR VEKILI BESLEMESI (senkron, telemetri dongusunden)
    # ------------------------------------------------------------------
    # `RadarVekili.cek_gerekirse()` bu islevi cagirir. SENKRON olmasi
    # bilinclidir: `merkez_kimlik.kopruye_sor` zaten senkron bir HTTP
    # istegidir ve vekil onu kendi cekme araligiyla (0.5 sn) ve tek
    # bir kilitle sinirlar. Araya asyncio koprusu koymak, telemetri
    # dongusunun icinde calisan `cek_gerekirse` cagrisini bir gorev
    # kuyruguna baglar ve yayin hizini radar gecikmesine bagimli
    # kilardi.
    #
    # Firma baglami AKTIF OTURUMDAN alinir (`_aktif_pilot`), cunku
    # telemetri yayini tek pakettir ve firma basina ayrilmaz. Merkezde
    # ayni GCS surecine farkli firmalardan pilotlar baglanabilir; radar
    # her zaman ILK oturumun firmasina ait olandir. Bu, dron kimlik
    # kaydinda (`dron.py::_firma_al`) kullanilan desenin aynisidir.
    # ------------------------------------------------------------------
    def _radar_kopru_durum_cek(self):
        """Kopruden radar durumu + izleri ceker. Donus: `(paket, hata)`.

        Hicbir kosulda ISTISNA FIRLATMAZ: cagiran telemetri dongusudur
        ve orada olusan bir istisna butun yayini durdurur.
        """
        try:
            p = self._aktif_pilot() or {}
            firma_id = p.get("firma_id")
            if not firma_id:
                return None, "Oturum gerekli."
            try:
                from . import merkez_kimlik as _mk
            except Exception as e:
                return None, "Merkez kimlik modulu yuklenemedi: %s" % e
            return self._saha_durum_cek("radar", "radar_durum",
                                        "Radar Sunucusunu",
                                        int(firma_id), _mk)
        except Exception as e:
            return None, "%s: %s" % (type(e).__name__, e)

    # ------------------------------------------------------------------
    # v2.4.61 — VIDEO ve AI VEKIL BESLEMESI
    # ------------------------------------------------------------------
    # Radar ile AYNI yol kullanilir. Servis adi parametrelenerek tek bir
    # govde uc servise hizmet eder; uc ayri kopya tutmak, birinde
    # duzeltilen kusurun otekilerde kalmasi anlamina gelirdi (radar
    # zincirinde bir kez yasandi).
    # ------------------------------------------------------------------
    def _video_kopru_durum_cek(self):
        """Kopruden kamera akis ozetini ceker. Donus: `(paket, hata)`."""
        return self._saha_durum_cek_guvenli(
            "video", "video_durum", "Video Sunucusunu")

    def _ai_kopru_durum_cek(self):
        """Kopruden AI isci/gorev ozetini ceker. Donus: `(paket, hata)`."""
        return self._saha_durum_cek_guvenli(
            "ai", "ai_durum", "AI Sunucusunu")

    async def _kamera_sahaya_ilet(self, websocket, kamera_id):
        """Kamera kaydini saha koprusunun defterine yazar.

        ## NEDEN GEREKLI

        Akis SAHADA acilir; kopru kamerayi kendi defterinde bulamazsa
        URL'yi bilemez ve akis hic acilmaz. Kayit yalniz merkez
        veritabaninda kalirsa kullanici "kaydettim ama goruntu gelmiyor"
        durumuyla karsilasir.

        ## SESSIZ BASARISIZLIK YOK, ANCAK AKIS DA ENGELLENMEZ

        Iletim basarisiz olursa kayit merkezde durur ve kullaniciya
        gerekce bildirilir. Kaydi geri almak DAHA KOTU olurdu: operator
        kamerayi yeniden girmek zorunda kalir, oysa kopru birkac saniye
        sonra ayaga kalkabilir.
        """
        if not (self.kameralar and self._merkez_kipinde()):
            return
        if getattr(self.video_proxy, "_komut", None) is None:
            return                      # lokal kurulum: vekil yok
        try:
            kayit = self.kameralar.bul(int(kamera_id))
        except Exception:
            kayit = None
        if not kayit:
            return
        paket = {
            "id": int(kamera_id),
            "isim": kayit.get("isim"),
            "protokol": kayit.get("protokol"),
            "url": kayit.get("url"),
            "ai_gorevler": kayit.get("ai_gorevler") or "",
            # v2.4.193: FPS tavani saha makinesine de gider (Kopru 1.7.20
            # video vekili ayni alani okur). Eksik gonderilirse saha
            # yayini hep 15'te kalir ve ayar yalniz yerel kipte islerdi.
            "fps": kayit.get("fps") or 15,
            "genislik": kayit.get("genislik") or 960,   # v2.4.207
        }
        _s, hata = await _db_is_parcasi(
            self._saha_komut_eszamanli, "video_kamera_yaz",
            {"kamera": paket})
        if hata:
            await self._hata_bildir(
                websocket, "KAMERA",
                "Kamera kaydi saha makinesine iletilemedi: %s" % hata)

    def _saha_video_baglam(self):
        """`(mk, oid, firma_id)` cozer ya da `(None, None, gerekce)`.

        `_saha_komut_eszamanli` ile AYNI cozum; ayri islev olmasinin
        nedeni donus bicimi: kanal islevleri merkez_kimlik modulune
        DOGRUDAN erisir (`_ic_cagri` yolu), kopruye komut gondermez.
        """
        try:
            from . import merkez_kimlik as _mk
        except Exception as e:
            return None, None, "Merkez kimlik modulu yuklenemedi: %s" % e
        if not _mk.etkin():
            return None, None, ("Yerel kipte canli kanal gerekmez "
                                "(kamera dogrudan acilir).")
        p = self._aktif_pilot() or {}
        firma_id = p.get("firma_id")
        if not firma_id:
            return None, None, "Oturum gerekli."
        firma_id = int(firma_id)
        oid = self._saha_kopru_onbellek_oid(_mk, firma_id, "video")
        if oid is None:
            return None, None, ("VIDEO servisi calisan saha makinesi "
                                "yok. Kopru panelinde Video Sunucusunu "
                                "baslatin.")
        return _mk, oid, firma_id

    def _saha_video_kanal_ac(self, kamera_id, app_port):
        """Canli kamera kanali acar. Doner: `(tamam, gerekce)`.

        ISTISNA FIRLATMAZ: cagiran taraf `_UzakYayin.baslat` icidir ve
        oradaki bir istisna MJPEG sunucusunun is parcacigini dusururdu.
        """
        try:
            _mk, oid, firma_id = self._saha_video_baglam()
            if _mk is None:
                return False, str(firma_id)
            tamam, hata = _mk.video_ac(oid, firma_id, int(kamera_id),
                                       int(app_port))
            if not tamam:
                self._saha_kopru_onbellek_dusur("video")
                return False, str(hata or "Canli kanal acilamadi")
            return True, ""
        except Exception as e:
            return False, "%s: %s" % (type(e).__name__, e)

    def _saha_video_kanal_kapat(self, kamera_id):
        """Canli kamera kanalini kapatir. Gerekce dondurur (yoksa None).

        ISTISNA FIRLATMAZ: `_UzakYayin.durdur` temizlik yolundadir;
        buradaki bir istisna soketin kapanmasini engellerdi.
        """
        try:
            _mk, oid, firma_id = self._saha_video_baglam()
            if _mk is None:
                return str(firma_id)
            return _mk.video_kapat(oid, firma_id, int(kamera_id))
        except Exception as e:
            return "%s: %s" % (type(e).__name__, e)

    def _saha_komut_eszamanli(self, eylem, veri=None, zaman_asimi=12.0):
        """Vekillerin kullandigi ESZAMANLI kopru komut yolu.

        Donus: `(sonuc, hata)`.

        ## NEDEN ESZAMANLI (asyncio DEGIL)

        `VideoVekili.cihaz_listesi` gibi cagrilar hem WS komut
        isleyicisinden (asyncio dongusu icinde) hem de
        `_ai_izleme_esitle` gibi `asyncio.to_thread` ile is
        parcacigindan cagrilir. Islevi `async` yapmak, is parcacigindan
        cagrildiginda dongu bulunamamasi yuzunden coker; bu yuzden
        `merkez_kimlik.kopruye_sor` esas alinir (radar vekilinin
        `_cek` yolu da aynidir).

        ## EYLEM ADINDAN SERVIS COZUMU

        Eylem adinin oneki hedef servisi belirler (`video_*` -> video,
        `ai_*` -> ai). Boylece cagiran taraf servis adini ayrica
        gecirmek zorunda kalmaz ve yanlis servise komut gonderme
        olasiligi ortadan kalkar.
        """
        try:
            servis = "video" if str(eylem).startswith("video_") else (
                "ai" if str(eylem).startswith("ai_") else None)
            if servis is None:
                return None, "Bilinmeyen saha eylemi: %s" % eylem
            gosterim = ("Video Sunucusunu" if servis == "video"
                        else "AI Sunucusunu")
            try:
                from . import merkez_kimlik as _mk
            except Exception as e:
                return None, "Merkez kimlik modulu yuklenemedi: %s" % e
            # v2.4.67: yerel kipte firma oturumu ARANMAZ. Kapali devre
            # kurulumda tek firma vardir ve `_aktif_pilot()` firma_id
            # tasimaz; onceki hali burada "Oturum gerekli." ile
            # duruyordu ve yerel kopruye hicbir video/AI komutu
            # gonderilemiyordu.
            if _mk.etkin():
                p = self._aktif_pilot() or {}
                firma_id = p.get("firma_id")
                if not firma_id:
                    return None, "Oturum gerekli."
                firma_id = int(firma_id)
            else:
                firma_id = None
            oid = self._saha_kopru_onbellek_oid(_mk, firma_id, servis)
            if oid is None:
                return None, ("%s servisi calisan saha makinesi yok. "
                              "Kopru panelinde %s baslatin."
                              % (servis.upper(), gosterim))
            sonuc, hata = self._kopruye_sor_eszamanli(
                _mk, oid, firma_id, eylem, veri or {},
                zaman_asimi=zaman_asimi)
            if hata:
                self._saha_kopru_onbellek_dusur(servis)
                return None, str(hata)
            sonuc = sonuc if isinstance(sonuc, dict) else {}
            if not sonuc.get("tamam", True):
                return None, str(sonuc.get("hata")
                                 or "Saha makinesi komutu uygulayamadi.")
            return sonuc, ""
        except Exception as e:
            return None, "%s: %s" % (type(e).__name__, e)

    def _saha_durum_cek_guvenli(self, servis, eylem, gosterim):
        """`_saha_durum_cek` sarmalayicisi; firma baglamini cozer.

        ISTISNA FIRLATMAZ: cagiran vekil telemetri dongusunden ya da WS
        komut isleyicisinden gelir.
        """
        try:
            try:
                from . import merkez_kimlik as _mk
            except Exception as e:
                return None, "Merkez kimlik modulu yuklenemedi: %s" % e
            if _mk.etkin():
                p = self._aktif_pilot() or {}
                firma_id = p.get("firma_id")
                if not firma_id:
                    return None, "Oturum gerekli."
                firma_id = int(firma_id)
            else:
                # Yerel kip: tek firmali kurulum (bkz.
                # `_saha_komut_eszamanli` aciklamasi).
                firma_id = None
            return self._saha_durum_cek(servis, eylem, gosterim,
                                        firma_id, _mk)
        except Exception as e:
            return None, "%s: %s" % (type(e).__name__, e)

    def _saha_durum_cek(self, servis, eylem, gosterim, firma_id, _mk):
        """Belirtilen servisin kosut kopruden durum ceker.

        Donus: `(paket, hata)`. Yanittaki `tamam=False` durumu da HATA
        olarak dondurulur; cagiranin iki ayri basarisizlik bicimiyle
        ugrasmasi gerekmez.
        """
        oid = self._saha_kopru_onbellek_oid(_mk, firma_id, servis)
        if oid is None:
            return None, ("%s servisi calisan saha makinesi yok. "
                          "Kopru panelinde %s baslatin."
                          % (servis.upper(), gosterim))
        veri, hata = self._kopruye_sor_eszamanli(
            _mk, oid, firma_id, eylem, {}, zaman_asimi=4.0)
        if hata:
            # Kopru degismis olabilir (operator baska makineye tasidi):
            # onbellegi dusur ki sonraki cekme yeniden tarasin, aksi
            # halde olu bir ornege sonsuza kadar sorulur.
            self._saha_kopru_onbellek_dusur(servis)
            return None, str(hata)
        if not isinstance(veri, dict):
            return None, "Saha makinesi gecersiz yanit verdi."
        if not veri.get("tamam", True):
            return None, str(veri.get("hata")
                             or "Saha makinesi %s durumunu veremedi."
                             % servis)
        return veri, ""

    # Servis adi -> onbellek nitelik adlari. Radar icin ESKI nitelik
    # adlari korunur (`_radar_kopru_oid`): baska yerlerde de okunuyor ve
    # yeniden adlandirmak gereksiz gerileme riski dogurur.
    _SAHA_ONBELLEK_AD = {
        "radar": ("_radar_kopru_oid", "_radar_kopru_oid_ts"),
        "m50": ("_m50_kopru_oid", "_m50_kopru_oid_ts"),
        "video": ("_video_kopru_oid", "_video_kopru_oid_ts"),
        "ai": ("_ai_kopru_oid", "_ai_kopru_oid_ts"),
    }

    def _saha_kopru_onbellek_dusur(self, servis):
        ad = self._SAHA_ONBELLEK_AD.get(servis)
        if ad:
            setattr(self, ad[0], None)

    @staticmethod
    def _servis_kaydi(yanit, servis):
        """Kopru `servis_durum` yanitindan BIR servisin kaydini dondurur.

        v2.4.63 - KUSUR-SERVIS-LISTE.

        Kullanici bildirimi: "radar baglan dedigimde 'list' object has no
        attribute 'get' hatasi veriyor" (radar ayakta ve kopru
        makinesinden ping atilabiliyorken).

        Kok neden: kopru `servisler` alanini LISTE olarak uretir
        (`kopru/servisler.py` -> `[{"ad": "radar", ...}, ...]`), merkez
        ise sozluk sanip `servisler.get(servis)` cagiriyordu. Liste
        uzerinde `.get` bulunmadigi icin komut isleyici cokuyor ve
        operator radara HIC baglanamiyordu.

        Neden burada tek bir yardimci: ayni varsayim merkezde iki ayri
        yerde tekrarlanmisti (onbellekli secim ve es zamanli tarama).
        Iki kopyayi ayri ayri duzeltmek, birinde yapilan duzeltmenin
        digerine gecmemesi riskini surdururdu.

        Her IKI bicim de kabul edilir. Yalniz listeyi desteklemek
        yeterli GORUNUR, ancak koprunun yanit bicimi surum atlamali
        yukseltmelerde degisebilir; merkez ile kopru surumleri sahada
        her zaman ayni olmaz (kullanici koprusu elle yukseltir). Iki
        bicimi birlikte tasimak, surum uyusmazligini panelde sessiz bir
        cokme yerine dogru davranisa cevirir.

        Donus: HER ZAMAN sozluk (kayit yoksa bos sozluk); cagiran taraf
        tip denetimi yapmak zorunda kalmaz.
        """
        if not isinstance(yanit, dict):
            return {}
        ham = yanit.get("servisler")
        istenen = str(servis or "")
        if isinstance(ham, dict):
            k = ham.get(istenen)
            return k if isinstance(k, dict) else {}
        if isinstance(ham, list):
            for k in ham:
                if isinstance(k, dict) and str(k.get("ad") or "") == istenen:
                    return k
        return {}

    def _saha_kopru_onbellek_oid(self, _mk, firma_id, servis="radar",
                                 tazele_sn=20.0):
        """Belirtilen servisin calistigi kopruyu bulur ve onbellekler.

        Her cekmede butun saha makinelerini taramak merkezi gereksiz
        yuke sokar; bulunan ornek `tazele_sn` boyunca yeniden kullanilir.
        Cagri basarisiz olursa `_saha_durum_cek` onbellegi dusurur.
        """
        ad = self._SAHA_ONBELLEK_AD.get(servis)
        if not ad:
            return None
        oid_ad, ts_ad = ad
        simdi = time.time()
        oid = getattr(self, oid_ad, None)
        ts = getattr(self, ts_ad, 0.0)
        if oid is not None and (simdi - ts) < tazele_sn:
            return oid
        try:
            liste = self._kopru_listesi_birlesik(firma_id)
        except Exception:
            return None
        for k in liste:
            if not k.get("cevrimici"):
                continue
            try:
                d, h = self._kopruye_sor_eszamanli(
                    _mk, k["ornek_id"], firma_id, "servis_durum", {},
                    zaman_asimi=4.0)
            except Exception:
                continue
            if h or not isinstance(d, dict):
                continue
            s = self._servis_kaydi(d, servis)
            if s.get("calisiyor"):
                setattr(self, oid_ad, k["ornek_id"])
                setattr(self, ts_ad, simdi)
                return k["ornek_id"]
        setattr(self, oid_ad, None)
        setattr(self, ts_ad, simdi)
        return None

    # Geriye donuk ad: baska cagri yeri kalmis olabilir.
    def _radar_kopru_onbellek_oid(self, _mk, firma_id, tazele_sn=20.0):
        return self._saha_kopru_onbellek_oid(_mk, firma_id, "radar",
                                             tazele_sn)

    def _kopruye_sor_eszamanli(self, _mk, ornek_id, firma_id, eylem,
                               veri=None, zaman_asimi=8.0):
        """ESZAMANLI kopru sorgusu; kipe gore dogru tasiyiciyi secer.

        Donus: `(veri, hata)` — `merkez_kimlik.kopruye_sor` ile birebir
        ayni sozlesme, boylece cagiran taraflar degismek zorunda kalmaz.

        ## NEDEN AYRI YARDIMCI

        Yerel kipte kopru soketi BU SURECTEDIR ve ona yazmak `await`
        gerektirir; oysa cagiran yerler (video/AI vekilleri, telemetri
        dongusu) es zamanlidir ve bir kismi zaten `asyncio.to_thread`
        icinden gelir. Bu yuzden istek, sunucunun ANA dongusune
        `run_coroutine_threadsafe` ile aktarilir ve sonucu es zamanli
        beklenir. Ayri bir dongu acmak soketi sahiplenen dongudem
        farkli olacagi icin calismaz.
        """
        if _mk.etkin():
            return _mk.kopruye_sor(ornek_id, firma_id, eylem, veri or {},
                                   zaman_asimi=zaman_asimi)

        from . import kopru_kabul
        o = kopru_kabul.ROLE.ornek_ile(ornek_id)
        if o is None:
            return None, ("Kopru cevrimdisi. Kopru yazilimini baslatip "
                          "yerel merkeze baglandigini dogrulayin.")
        dongu = getattr(self, "_loop", None)
        if dongu is None or not dongu.is_running():
            return None, "Sunucu dongusu hazir degil."
        try:
            import concurrent.futures as _cf
            is_ = asyncio.run_coroutine_threadsafe(
                kopru_kabul.kopruden_iste(o, eylem, veri or {},
                                          zaman_asimi=zaman_asimi),
                dongu)
            try:
                return (is_.result(timeout=float(zaman_asimi) + 4.0)
                        or {}), None
            except _cf.TimeoutError:
                is_.cancel()
                return None, "Kopru yanit vermedi: %s" % eylem
        except Exception as e:
            return None, "%s: %s" % (type(e).__name__, e)

    async def _uyari_gonder(self, websocket, kaynak, mesaj, seviye="uyari"):
        """Panelin sag ust kosesindeki bildirim balonunu tetikler.

        Kullanici istegi: "programda her turlu hata bildirimlere uyari
        olarak dusecek ve ekranin sag kosesinde gorunecek".

        DIKKAT - mesaj tipi `uyari_yeni` OLMAK ZORUNDA. Arayuz
        (`ws.js`) yalniz bu tipi tanir ve uyari govdesini IC ICE
        `uyari` alanindan okur (`window.uyariYeniIsle` -> `m.uyari`).
        Duz `{"tip": "uyari"}` gonderilse mesaj sessizce dusurulur:
        operator hicbir sey gormez ve panel sonsuza kadar
        "baglaniyor" yazar.

        Uyari ayrica pilotun uyari defterine YAZILIR; boylece operator
        balonu kacirsa ust bardaki can ikonundan geri okuyabilir.
        """
        p = self._pilot_bilgi(websocket) or {}
        ep = p.get("eposta", "")
        kayit = None
        try:
            kayit = self.pilot.uyari_ekle(ep, str(kaynak).lower(),
                                          str(mesaj))
        except Exception:
            kayit = None
        if not isinstance(kayit, dict):
            # Defter yazimi basarisiz olsa bile BALON gosterilmeli:
            # kalici kayit ikincil, operatorun aninda haberdar olmasi
            # birincildir.
            # Alan adlari `pilot.uyari_ekle` donusuyle BIREBIR ayni
            # olmali (`ts`, `okundu`, `id`); arayuz bunlari okur ve
            # eksik alan liste goruntusunu bozar.
            kayit = {"id": 0, "ts": time.time(),
                     "eposta": ep, "kategori": str(kaynak).lower(),
                     "mesaj": str(mesaj), "okundu": 0}
        kayit["seviye"] = seviye
        try:
            okunmamis = self.pilot.okunmamis_sayi(ep)
        except Exception:
            okunmamis = 0
        try:
            await websocket.send(json.dumps(
                {"tip": "uyari_yeni", "uyari": kayit,
                 "okunmamis": okunmamis}))
        except Exception:
            pass

    async def _kopru_servis_sec(self, websocket, servis, istenen=None,
                                servis_adi=None):
        """Belirtilen alt servisin CALISTIGI kopruyu secer.

        `_gcsdual_kopru_sec` ile ayni mantik; servis adi parametrelesmis
        halidir. Iki ayri kopya tutmak, birinde yapilan duzeltmenin
        digerine gecmemesi riskini dogurur.
        """
        gosterim = servis_adi or servis
        try:
            from . import merkez_kimlik as _mk
        except Exception as e:
            return None, "Merkez kimlik modulu yuklenemedi: %s" % e
        # v2.4.67: yerel (kapali devre) kipte firma oturumu aranmaz;
        # kurulum tek firmalidir. Onceki hali burada duruyor ve yerel
        # kurulumda radar/GCCDUAL kopruude CALISIYOR olsa bile
        # secilemiyordu.
        if _mk.etkin():
            firma_id = self._ws_firma_id(websocket)
            if not firma_id:
                return None, "Oturum gerekli."
        else:
            firma_id = None
        try:
            secilen = int(istenen or 0)
        except (TypeError, ValueError):
            secilen = 0
        if secilen > 0:
            if not self._kopru_sahibi_mi(secilen, firma_id):
                return None, ("Secilen saha makinesi bu firmaya ait "
                              "degil.")
            return secilen, ""
        try:
            liste = await _db_is_parcasi(
                self._kopru_listesi_birlesik, firma_id)
        except Exception as e:
            return None, "Saha makinesi listesi okunamadi: %s" % e
        cevrimici = [k for k in (liste or []) if k.get("cevrimici")]
        if not cevrimici:
            return None, ("Cevrimici saha makinesi yok. Kopru "
                          "yazilimini baslatin.")

        def _tara(_liste=cevrimici, _f=firma_id):
            import concurrent.futures as _cf

            def _bir(_kk):
                return _kk, self._kopruye_sor_eszamanli(
                    _mk, _kk["ornek_id"], _f, "servis_durum", {},
                    zaman_asimi=5.0)

            with _cf.ThreadPoolExecutor(min(8, len(_liste))) as _h:
                return list(_h.map(_bir, _liste))

        try:
            sonuclar = await _db_is_parcasi(_tara)
        except Exception as e:
            return None, "Saha makineleri sorgulanamadi: %s" % e
        uygun = []
        for kk, (veri, _hata) in sonuclar:
            # KUSUR-SERVIS-LISTE: `servisler` LISTE gelir; sozluk
            # varsayimi burada `.get` cokmesine yol aciyordu.
            s = self._servis_kaydi(veri, servis)
            if s.get("calisiyor"):
                uygun.append(kk)
        if not uygun:
            return None, ("Hicbir saha makinesinde %s calismiyor. "
                          "Kopru panelinde baslatin." % gosterim)
        if len(uygun) > 1:
            adlar = ", ".join(str(k.get("ad") or k.get("kurulum_uid")
                                  or k.get("ornek_id"))
                              for k in uygun[:5])
            return None, ("Birden fazla saha makinesinde %s calisiyor "
                          "(%s). Panelden makine secin." % (gosterim, adlar))
        return int(uygun[0]["ornek_id"]), ""

    async def _kopruye_sor_async(self, ornek_id, websocket, eylem,
                                 veri=None, zaman_asimi=12.0):
        """Kopruye SENKRON HTTP sorgusunu asyncio dongusunu bloke
        etmeden yapar. Donus: `(veri, hata)`.

        Neden is parcacigi: `merkez_kimlik.kopruye_sor` urllib ile
        senkron istek yapar. Dogrudan cagrilirsa TUM arayuz WS trafigi
        (butun pilotlarin telemetrisi dahil) sorgu suresince donar. SSH
        baslatma 15 sn'ye kadar surebilir; bu kabul edilemez.

        Yetki: `ornek_id` arayuzden DEGIL veritabani kaydindan gelir,
        ancak yine de firma listesine karsi dogrulanir — kayit eski bir
        kopruye isaret ediyor olabilir.

        v2.4.67: YEREL KIPTE HTTP ATLAMASI YOK. Kapali devre kurulumda
        merkez sureci yoktur; kopru soketi bu surecin ICINDEDIR ve
        dogrudan yazilir. Bu yol hem daha hizlidir hem de ic anahtar /
        ic taban yapilandirmasi gerektirmez.
        """
        try:
            oid = int(ornek_id or 0)
        except (TypeError, ValueError):
            oid = 0
        if oid <= 0:
            return None, "Kopru kimligi tanimsiz."

        try:
            from . import merkez_kimlik as _mk
        except Exception as e:
            return None, "Merkez kimlik modulu yuklenemedi: %s" % e

        # ---- YEREL KIP: dogrudan soket ----
        if not _mk.etkin():
            if not self._kopru_sahibi_mi(oid, None):
                return None, ("Kopru kaydi bulunamadi. Merkez Uygulama "
                              "kurulum kimligini yeniden uretin.")
            from . import kopru_kabul
            o = kopru_kabul.ROLE.ornek_ile(oid)
            if o is None:
                return None, ("Kopru cevrimdisi. Kopru yazilimini "
                              "baslatip yerel merkeze baglandigini "
                              "dogrulayin.")
            try:
                sonuc = await kopru_kabul.kopruden_iste(
                    o, eylem, veri or {}, zaman_asimi=zaman_asimi)
                return (sonuc or {}), None
            except Exception as e:
                return None, "%s: %s" % (type(e).__name__, e)

        # ---- MERKEZ KIP: merkez surecine HTTP ----
        firma_id = self._ws_firma_id(websocket)
        if not firma_id:
            return None, "Oturum gerekli."
        if not self._kopru_sahibi_mi(oid, firma_id):
            return None, ("Kayit bu firmaya ait olmayan bir kopruye "
                          "bagli. Kaydi duzenleyip kopruyu yeniden "
                          "secin.")

        def _cagir():
            return _mk.kopruye_sor(oid, firma_id, eylem, veri or {},
                                   zaman_asimi=zaman_asimi)

        try:
            return await _db_is_parcasi(_cagir)
        except Exception as e:
            return None, "Kopru sorgusu basarisiz: %s" % e

    async def _goruntu_kamera_kaynaklari(self, websocket, secilen=None):
        """Firma kapsamındaki Görüntü Köprülerinden güvenli kamera listesini alır.

        Köprü kayıtlarında ürün yeteneği eski sürümlerde bulunmayabildiği
        için çevrimiçi köprüler doğrudan sorgulanır; yalnız
        `goruntu_kamera_liste` eylemine geçerli liste döndürenler sonuca
        girer. Kamera URL'si, kare veya biyometri bu sözleşmede yoktur.
        """
        firma_id = self._ws_firma_id(websocket)
        try:
            from . import merkez_kimlik as _mk
            if _mk.etkin() and not firma_id:
                return [], "Oturum gerekli."
        except Exception as e:
            return [], "Merkez kimlik modulu yuklenemedi: %s" % e
        try:
            istenen = int(secilen or 0)
        except (TypeError, ValueError):
            istenen = 0
        liste = await _db_is_parcasi(self._kopru_listesi_birlesik,
                                         firma_id)
        adaylar = []
        for kayit in liste or []:
            try:
                oid = int(kayit.get("ornek_id") or 0)
            except (TypeError, ValueError):
                continue
            if oid <= 0 or (istenen and oid != istenen):
                continue
            if not kayit.get("cevrimici"):
                if istenen:
                    return [{"ornek_id": oid,
                             "ad": str(kayit.get("ad") or "Goruntu Koprusu")[:120],
                             "cevrimici": False, "kameralar": [],
                             "hata": "Goruntu Koprusu cevrimdisi."}], ""
                continue
            adaylar.append((oid, kayit))
        if istenen and not adaylar:
            return [], "Secilen Goruntu Koprusu bulunamadi."
        if not adaylar:
            return [], "Cevrimici Goruntu Koprusu bulunamadi."

        async def _bir(oid, kayit):
            veri, hata = await self._kopruye_sor_async(
                oid, websocket, "goruntu_kamera_liste", {}, zaman_asimi=5.0)
            if hata:
                return None
            # Kopru ajani geriye uyumluluk icin sozluk olmayan islev
            # sonuclarini {"sonuc": ...} zarfina alir. Goruntu Koprusu
            # 1.3.4 kamera listesini dogrudan liste olarak uretir; bu nedenle
            # merkez hem yeni zarfli hem eski dogrudan liste bicimini kabul
            # etmelidir. Aksi halde cevrimici kopru basariyla yanit verse bile
            # dron duzenleme penceresi onu sessizce listeden dusurur.
            veri = _goruntu_kamera_listesi_coz(veri)
            if veri is None:
                return None
            temiz = []
            for kamera in veri:
                if not isinstance(kamera, dict):
                    continue
                try:
                    kid = int(kamera.get("id") or 0)
                except (TypeError, ValueError):
                    continue
                if kid <= 0:
                    continue
                temiz.append({
                    "id": kid,
                    "isim": str(kamera.get("isim") or "Kamera")[:120],
                    "tur": str(kamera.get("tur") or "")[:24],
                    "etkin": bool(kamera.get("etkin")),
                    "canli": bool(kamera.get("canli")),
                    "ai_acik": bool(kamera.get("ai_acik")),
                    "poz_kaynak": str(kamera.get("poz_kaynak") or "manuel")[:12],
                    "kaynak_dron_id": str(kamera.get("kaynak_dron_id") or "")[:160],
                    "kalibre": bool(kamera.get("kalibre")),
                    "hedef_sayisi": max(0, min(9999, int(
                        kamera.get("hedef_sayisi") or 0))),
                    "gecmis_kare_acik": bool(
                        kamera.get("gecmis_kare_acik")),
                })
            return {"ornek_id": oid,
                    "ad": str(kayit.get("ad") or kayit.get("makine_adi") or
                              "Goruntu Koprusu")[:120],
                    "cevrimici": True, "kameralar": temiz}

        sonuclar = await asyncio.gather(
            *(_bir(oid, kayit) for oid, kayit in adaylar),
            return_exceptions=True)
        kopruler = [s for s in sonuclar if isinstance(s, dict)]
        if istenen and not kopruler:
            return [], "Secilen saha yazilimi bir Goruntu Koprusu degil veya yanit vermedi."
        return kopruler, ""

    async def _goruntu_son_kareler(self, websocket):
        """Oturum firmasındaki kayıtlı dronların en son onaylı kareleri.

        Yanıt, tarayıcının kalıcı dron UID/ID değerini canlı SYSID ile kesin
        eşleştirebilmesi için yalnız asgari kimlik özetini taşır. Kamera adı,
        normal video, tespit, yüz adı/embedding veya ham görüntü içermez.
        """
        firma_id = self._ws_firma_id(websocket)
        try:
            from . import merkez_kimlik as _mk
            if _mk.etkin() and not firma_id:
                return [], [], "Oturum gerekli."
        except Exception as e:
            return [], [], "Merkez kimlik modulu yuklenemedi: %s" % e
        if not firma_id:
            return [], [], "Firma kapsami bulunamadi."
        try:
            from . import veritabani as _vt
            kaynaklar = _vt.dron_kaynaklari_listele(firma_id) or []
        except Exception as e:
            return [], [], "Dron listesi okunamadi: %s" % e

        eslemeler = []
        uidler = []
        for d in kaynaklar[:500]:
            if not isinstance(d, dict):
                continue
            uid = str(d.get("uid") or "").strip()[:120]
            if not uid:
                continue
            try:
                did = int(d.get("id") or 0)
            except (TypeError, ValueError):
                did = 0
            try:
                sysid = int(d.get("sysid") or 0)
            except (TypeError, ValueError):
                sysid = 0
            if did <= 0:
                continue
            uidler.append(uid)
            eslemeler.append({
                "id": did,
                "uid": uid,
                "sysid": sysid if 1 <= sysid <= 255 else None,
            })
        try:
            kareler = await _db_is_parcasi(
                goruntu_gecmisi.son_kareler, firma_id, uidler, 100)
        except Exception as e:
            return eslemeler, [], "Son kareler okunamadi: %s" % e
        simdi = time.time()
        for kare in kareler:
            try:
                kare["yas_ms"] = max(
                    0, int((simdi - float(kare.get("alis_ts"))) * 1000))
            except (TypeError, ValueError):
                kare["yas_ms"] = None
        return eslemeler, kareler, ""

    async def _goruntu_kamera_dron_bagla(self, websocket, istek):
        """Merkezde seçilen kamerayı kalıcı dron UID'sine bağlar/çözer."""
        pilot = self._pilot_bilgi(websocket) or {}
        if pilot.get("rol") != "yonetici":
            return False, "Kamera-dron bagini yalnizca yonetici degistirebilir.", []
        try:
            oid = int(istek.get("ornek_id") or 0)
            kid = int(istek.get("kamera_id") or 0)
        except (TypeError, ValueError):
            oid = kid = 0
        uid = str(istek.get("dron_uid") or "").strip()
        if oid <= 0 or kid <= 0 or len(uid) > 160:
            return False, "Gecersiz kopru, kamera veya dron kimligi.", []
        firma_id = self._ws_firma_id(websocket)
        try:
            from . import merkez_kimlik as _mk
            if _mk.etkin() and not firma_id:
                return False, "Oturum gerekli.", []
        except Exception as e:
            return False, "Merkez kimlik modulu yuklenemedi: %s" % e, []
        if not self._kopru_sahibi_mi(oid, firma_id):
            return False, "Secilen Goruntu Koprusu bu firmaya ait degil.", []
        if uid:
            try:
                from . import veritabani as _vt
                dronlar = _vt.dron_kaynaklari_listele(firma_id) or []
            except Exception as e:
                return False, "Dron listesi okunamadi: %s" % e, []
            izinli = any(str(d.get("uid") or "").strip() == uid
                         for d in dronlar if isinstance(d, dict))
            if not izinli:
                return False, "Dron bu firmanin kayitli kaynaklarinda bulunamadi.", []
        veri, hata = await self._kopruye_sor_async(
            oid, websocket, "goruntu_kamera_dron_bagla",
            {"kamera_id": kid, "dron_uid": uid}, zaman_asimi=8.0)
        if hata:
            return False, hata, []
        if not isinstance(veri, dict) or not veri.get("basarili"):
            return False, str((veri or {}).get("hata") or
                              "Goruntu Koprusu bagi reddetti."), []
        kameralar = veri.get("kameralar") or []
        self._pilot_log(websocket, "GORUNTU_KAMERA", "dron_bagla",
                        {"ornek_id": oid, "kamera_id": kid,
                         "dron_uid": uid or None})
        return True, "", kameralar

    @staticmethod
    def _ai_kayit_kopruye(kayit):
        """AI sunucu kaydinin kopruye GONDERILECEK alanlarini secer.

        Tum satiri gondermek yanlis olur: `ssh_sifre` ayri bir alanda
        (maskelenmis olarak degil, cozulmus olarak) tasinir ve gereksiz
        alanlar sahaya sizmamalidir. Beyaz liste kullanilir.
        """
        k = kayit or {}
        return {
            "id": k.get("id"),
            "ad": k.get("ad"),
            "host": k.get("host"),
            "port": k.get("port"),
            "ssh_kullanici": k.get("ssh_kullanici"),
            "ssh_port": k.get("ssh_port"),
            "ssh_anahtar": k.get("ssh_anahtar"),
            "ssh_komut": k.get("ssh_komut"),
        }

    def _kopru_ornek_coz(self, kayit, firma_id):
        """Kayittan `(ornek_id, hata)` cozer (kopruye baglanan her tur).

        Kayitta `host` alani `"kurulum_uid|ad|firma"` bicimindedir; ancak
        merkezin akis uclari METIN uid degil TAMSAYI `ornek_id` bekler.
        Esleme merkez veritabanindan (`firma_kopruleri`) yapilir ve bu
        ayni zamanda YETKI DENETIMIDIR: uid baska bir firmaya aitse
        listede bulunmaz ve baglanti baslatilamaz.

        Ayrica `kopru_ornek_id` kolonu doluysa oncelikle o kullanilir;
        yine de firma listesine karsi DOGRULANIR (kolon eski bir
        koprue isaret ediyor olabilir).
        """
        try:
            from . import merkez_kimlik as _mk
        except Exception as e:
            return None, "Merkez kimlik modulu yuklenemedi: %s" % e
        # v2.4.67: onceki surumde burada kosulsuz "Merkez baglantilari
        # yalniz merkezde calisan kurulumda kullanilabilir" donuyordu.
        # Kapali devre Merkez Uygulama artik kopru KABUL ETTIGI icin
        # yerel kurulumda da kopru uzerinden dron baglantisi acilabilir.
        yerel_kip = not _mk.etkin()
        coz = self.baglantilar.merkez_coz(kayit) or {}
        uid = str(coz.get("uid") or "")
        try:
            kolon = int(kayit.get("kopru_ornek_id") or 0)
        except (TypeError, ValueError):
            kolon = 0
        if not (uid or kolon):
            return None, "Baglanti kaydinda hedef sunucu yok."
        if yerel_kip:
            liste = self._kopru_listesi_birlesik(None)
            bulunan = None
            for k in liste:
                if uid and str(k.get("kurulum_uid") or "") == uid:
                    bulunan = k
                    break
            if bulunan is None:
                for k in liste:
                    if kolon and int(k.get("ornek_id") or 0) == kolon:
                        bulunan = k
                        break
            if bulunan is None:
                return None, ("Hedef kopru kaydi bulunamadi. Merkez "
                              "Uygulama'da kopru kimligi uretip kopru "
                              "yazilimina girin.")
            if not bulunan.get("cevrimici"):
                return None, ("Baglantinin kurulacagi makine (%s) su an "
                              "cevrimdisi. Kopru yazilimini o "
                              "bilgisayarda baslatin."
                              % (bulunan.get("ad")
                                 or bulunan.get("ornek_id")))
            return int(bulunan["ornek_id"]), None
        # v2.4.57: firma_id BOS olabilir ve bu bir OTURUM sorunudur, veri
        # sorunu degil. Olculdu: kayitli baglantiyi acilista otomatik
        # baslatan yol (`baglanti_baslat`) daha oturum kurulmamis bir
        # soketle cagrilabiliyor; `int(None)` patliyor ve pilot
        # "Merkez sunucu listesi okunamadi: int() argument must be ...
        # not 'NoneType'" gibi anlamsiz bir ileti goruyordu. Ileti
        # kullaniciyi veritabani ya da ag arizasi sanmaya yonlendirirken
        # gercek neden yalnizca oturumun henuz yuklenmemis olmasiydi.
        try:
            _fid = int(firma_id)
        except (TypeError, ValueError):
            # IS44_OTURUM_GERIDUSUS_v1: oturum sokette cozulemedi.
            # Baglanti KAYDI zaten bir firmaya ait; o alana
            # duseriz. Yetki GENISLEMEZ: asagidaki
            # `firma_kopruleri(_fid)` dogrulamasi korunur;
            # uid/kolon o firmanin listesinde yoksa baglanti
            # yine reddedilir.
            try:
                _fid = int((kayit or {}).get("firma_id") or 0)
            except (TypeError, ValueError):
                _fid = 0
            if not _fid:
                return None, ("Oturum bilgisi henuz yuklenmedi; baglantiyi "
                              "birkac saniye sonra yeniden baslatin.")
        try:
            liste = _mk.firma_kopruleri(_fid) or []
        except Exception as e:
            return None, "Merkez sunucu listesi okunamadi: %s" % e
        bulunan = None
        for k in liste:
            if uid and str(k.get("kurulum_uid") or "") == uid:
                bulunan = k
                break
        if bulunan is None:
            for k in liste:
                if kolon and int(k.get("ornek_id") or 0) == kolon:
                    bulunan = k
                    break
        if bulunan is None:
            return None, ("Hedef sunucu bu firmada bulunamadi (silinmis "
                          "veya baska firmaya tasinmis olabilir).")
        # v2.4.55: cevrimdisi kopruye kanal acma denemesi merkez
        # tarafinda zaman asimina kadar bekler ve pilot yalnizca
        # "acilamadi" gorur. Nedeni BURADA, beklemeden bildirilir.
        if not bulunan.get("cevrimici"):
            return None, ("Baglantinin kurulacagi makine (%s) su an "
                          "cevrimdisi. Kopru yazilimini o bilgisayarda "
                          "baslatin." % (bulunan.get("ad") or
                                         bulunan.get("ornek_id")))
        return int(bulunan["ornek_id"]), None

    async def _akis_kanali_ac(self, kayit, firma_id):
        """Merkez turu baglanti icin akis kanali acar; `(url, hata)` doner.

        Donen `url` dogrudan `dron.dinle()`e verilebilecek bir mavutil
        dizesidir (`udpin:127.0.0.1:<port>`). Boylece `dron.py` icindeki
        MAVLink mantigi (heartbeat, parametre, gorev protokolu, disa UDP
        yayini) HIC DEGISMEDEN calisir.

        Cagri SENKRON HTTP oldugu icin is parcaciginda calistirilir;
        aksi halde kanal acilirken TUM arayuz WS trafigi durur.
        """
        # MSP verisi ham MAVLink kanalina konulmaz ve sahte MAVLink'e
        # cevrilmez. Bu savunma, yanlis cagirici yolu olsa bile ayrimi
        # korur; Betaflight icin `_merkez_betaflight_baslat` kullanilir.
        if str(kayit.get("ucus_yazilimi") or "ardupilot").lower() == "betaflight":
            return None, "Betaflight MSP baglantisi MAVLink akis kanali acamaz."
        bid = int(kayit["id"])
        oid, hata = self._kopru_ornek_coz(kayit, firma_id)
        if hata:
            return None, hata
        # Ayni baglanti icin acik kanal varsa once kapatilir: `play`
        # ustune `play` basildiginda merkezde iki port ayrilmis olurdu ve
        # eski port sonsuza dek sizardi.
        await self._akis_kanali_kapat(bid)
        from . import merkez_kimlik as _mk

        # v2.4.55: kanal tanimi kaydin KENDI turunden uretilir.
        #
        # Eski kod `kopru_tur` / `kopru_host` alanlarini okuyordu, ama
        # bu alanlari hicbir yer YAZMIYORDU (olculdu: baglantilar.py'de
        # gecmiyorlar). Sonuc: her kanal koprue "seri" ve bos host ile
        # gidiyordu; TCP dronu hicbir zaman baglanamazdi. Kaydin turu
        # zaten seri/tcp/udp olarak saklaniyor ve koprunun akis modulu
        # (kopru/akis.py) tam bu ucunu bekliyor.
        #
        # `merkez` turu geriye donuk uyum icin korunur: o kayitlarda
        # hedef makine `host` alaninda kodludur, tasima turu ise
        # `kopru_tur` alaninda tutulmus olabilir.
        _tur = str(kayit.get("tur") or "").lower()
        if _tur == "merkez":
            _kt = str(kayit.get("kopru_tur") or "seri")
            _kh = str(kayit.get("kopru_host") or "")
        else:
            _kt = _tur or "seri"
            _kh = str(kayit.get("host") or "")
        tanim = {
            "tur": _kt,
            "port": str(kayit.get("port") or ""),
            "baud": int(kayit.get("baud") or 57600),
            "host": _kh,
            "isim": str(kayit.get("isim") or ""),
            "ucus_yazilimi": str(kayit.get("ucus_yazilimi") or "ardupilot"),
        }

        # v2.4.56: BOŞ PORTU BİZ SEÇERİZ.
        #
        # `udpin:` bir bind cagrisidir. Merkezin bind ettigi portu bize
        # bildirmesi, ayni portu iki surecin baglamasi demekti ve olculen
        # sonuc `[Errno 98] Address already in use` idi: play'e basan
        # pilot hicbir telemetri gormuyordu. Portu bind EDECEK taraf
        # sectiginde cakisma yapisal olarak imkansizlasir.
        #
        # Soket burada gecici olarak acilir, port numarasi ogrenilir ve
        # HEMEN kapatilir; pymavlink ayni portu kendisi baglayacaktir.
        # Kisa yaris penceresi kalir (port kapanip pymavlink baglayana
        # kadar), ancak isletim sistemi yakin zamanda serbest kalan portu
        # yeniden dagitmayi geciktirdigi icin pratikte guvenlidir ve
        # alternatifi (soketi acik tutup pymavlink'e devretmek) mavutil
        # arayuzunde mumkun degildir.
        import socket as _socket
        try:
            _s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
            try:
                _s.bind(("127.0.0.1", 0))
                gcs_port = int(_s.getsockname()[1])
            finally:
                _s.close()
        except Exception as e:
            return None, "Yerel UDP portu ayrilamadi: %s" % e

        def _isle():
            return _mk.akis_ac(oid, int(firma_id), bid, tanim,
                              gcs_port=gcs_port)

        try:
            port, hata = await _db_is_parcasi(_isle)
        except Exception as e:
            return None, "%s: %s" % (type(e).__name__, e)
        if hata or not port:
            return None, hata or "Merkez port bildirmedi"
        with self.kilit:
            self._akis_kanallari[bid] = {
                "ornek_id": int(oid), "firma_id": int(firma_id),
                "port": int(port), "tanim": tanim,
            }
        self.konsol("AKIS",
                    f"Kanal acildi: {tanim['isim'] or bid} -> "
                    f"udpin:127.0.0.1:{port} (ornek {oid})", "basari")
        return "udpin:127.0.0.1:%d" % int(port), None

    async def _akis_kanali_kapat(self, bid):
        """Baglantinin akis kanalini kapatir (yoksa sessizce doner).

        Defter kaydi HER DURUMDA silinir, merkez cagrisi basarisiz olsa
        bile: aksi halde kanal "acik" gorunur ve yeniden baslatma
        denemesi de basarisiz olur. Merkez tarafinda terk edilen kanal
        `_nabiz_goktungusu` temizligine takilir.
        """
        bid = int(bid)
        with self.kilit:
            k = self._akis_kanallari.pop(bid, None)
        if not k:
            return
        try:
            from . import merkez_kimlik as _mk

            def _isle():
                return _mk.akis_kapat(k["ornek_id"], k["firma_id"], bid)

            hata = await _db_is_parcasi(_isle)
            if hata:
                self.konsol("AKIS",
                            f"Kanal kapatma uyarisi (id={bid}): {hata}",
                            "uyari")
            else:
                self.konsol("AKIS", f"Kanal kapatildi (id={bid})", "bilgi")
        except Exception as e:
            self.konsol("AKIS",
                        f"Kanal kapatilamadi (id={bid}): {e}", "uyari")

    def _calisan_ucus_yazilimi(self, kayit):
        """Kayıt tercihini aktif çalışma protokolüne çözer.

        `otomatik` veritabanında tercih olarak kalır; seçilen protokol yalnız
        süreç belleğindeki doğrulanmış algılama sonucundan gelir.
        """
        yazilim = str((kayit or {}).get("ucus_yazilimi") or "ardupilot").lower()
        if yazilim != "otomatik":
            return yazilim
        bid = str((kayit or {}).get("id") or "")
        return str((self._otomatik_protokoller.get(bid) or {}).get(
            "protokol") or "otomatik").lower()

    async def _otomatik_protokol_algila(self, kayit, firma_id):
        """Tek seri portta güvenli MAVLink Heartbeat/MSP API ayrımı yapar."""
        if str((kayit or {}).get("tur") or "").lower() != "seri":
            return None, "Otomatik protokol algilama yalniz seri/RFD900 baglantida kullanilir."
        bid = int((kayit or {}).get("id") or 0)
        if not bid:
            return None, "Baglanti kimligi gecersiz."
        try:
            if self._kopru_uzerinde_mi(kayit):
                oid, hata = self._kopru_ornek_coz(kayit, firma_id)
                if hata:
                    return None, hata
                from . import merkez_kimlik as _mk
                veri, hata = await _db_is_parcasi(
                    _mk.kopruye_sor, oid, int(firma_id), "protokol_algila",
                    {"kayit": dict(kayit)}, 8.0)
                if hata:
                    return None, hata
                sonuc = dict(veri or {})
            else:
                from .protokol_algilama import seri_protokol_algila
                sonuc = await _db_is_parcasi(seri_protokol_algila,
                                                dict(kayit))
        except Exception as e:
            return None, "%s: %s" % (type(e).__name__, e)
        protokol = str(sonuc.get("protokol") or "").lower()
        if not bool(sonuc.get("tamam")) or protokol not in (
                "ardupilot", "betaflight"):
            return None, str(sonuc.get("hata") or
                             "Ucus yazilimi otomatik algilanamadi.")
        self._otomatik_protokoller[str(bid)] = dict(sonuc)
        self.konsol("ALGILAMA", "%s: %s (%s)" % (
            kayit.get("isim") or bid, protokol,
            sonuc.get("kanit") or "dogrulandi"), "bilgi")
        return protokol, None

    async def _baglanti_baslat_uygula(self, websocket, kayit, firma_id):
        """Tercih veya güvenli algılama sonucuna göre tek sürücüyü başlatır."""
        calisan = dict(kayit or {})
        yazilim = self._calisan_ucus_yazilimi(calisan)
        if yazilim == "otomatik":
            yazilim, hata = await self._otomatik_protokol_algila(calisan, firma_id)
            if hata:
                return False, hata
            calisan["ucus_yazilimi"] = yazilim
        if yazilim == "betaflight":
            return await self._merkez_betaflight_baslat(calisan, firma_id)
        if yazilim != "ardupilot":
            return False, "Algilanan ucus yazilimi desteklenmiyor."
        if calisan.get("tur") == "dji" and self.dji_kopru:
            self.dji_kopru.dinle(calisan)
            return True, None
        if calisan.get("tur") == "sanal":
            await self._sanal_baslat(websocket, calisan)
            return True, None
        if self._kopru_uzerinde_mi(calisan):
            tamam = await self._merkez_baglanti_baslat(
                websocket, calisan, firma_id)
            return bool(tamam), None if tamam else "Merkez akisi acilamadi."
        self.dron.dinle(calisan, self.baglantilar.mavutil_url(calisan))
        return True, None

    async def _merkez_betaflight_baslat(self, kayit, firma_id):
        """Betaflight MSP tanı oturumunu yerelde veya yetkili Köprüde açar.

        Bu yol MAVLink akış kanalı kullanmaz. Köprüye yalnız bağlanma
        tanımı gönderilir; yazılabilir MSP paketi, uçuş komutu veya ham
        bayt iletimi için bir arayüz tanımlı değildir.
        """
        bid = int(kayit.get("id") or 0)
        if not bid:
            return False, "Baglanti kimligi gecersiz."
        if self._kopru_uzerinde_mi(kayit):
            oid, hata = self._kopru_ornek_coz(kayit, firma_id)
            if hata:
                return False, hata
            from . import merkez_kimlik as _mk
            tanim = {"id": bid, "isim": str(kayit.get("isim") or ""),
                     "tur": str(kayit.get("tur") or ""),
                     "port": str(kayit.get("port") or ""),
                     "baud": int(kayit.get("baud") or 115200),
                     "ucus_yazilimi": "betaflight"}
            try:
                veri, hata = await _db_is_parcasi(
                    _mk.kopruye_sor, oid, int(firma_id), "msp_baslat",
                    {"kayit": tanim}, 12.0)
            except Exception as e:
                return False, "%s: %s" % (type(e).__name__, e)
            if hata:
                return False, hata
            if not bool((veri or {}).get("tamam")):
                return False, str((veri or {}).get("hata") or
                                  "Kopru MSP oturumunu acamadi.")
            durum = dict((veri or {}).get("durum") or {})
            if not durum:
                durum = {"durum": "baglaniyor", "protokol": "betaflight_msp",
                          "salt_okunur": True, "baglanti_id": bid}
            self._betaflight_kopruleri[str(bid)] = durum
            self._betaflight_kopru_meta[str(bid)] = {
                "ornek_id": int(oid), "firma_id": int(firma_id)}
            self.konsol("BETAFIGHT", "Koprude salt-okunur MSP baslatildi: %s" %
                        (kayit.get("isim") or bid), "bilgi")
            return True, None
        if not self.betaflight:
            return False, "Betaflight MSP yoneticisi baslatilmamis."
        tamam, hata = self.betaflight.baslat(kayit)
        return bool(tamam), hata

    async def _betaflight_durdur(self, kayit, firma_id):
        """Yerel veya Köprüdeki MSP oturumunu kapatır; hata metnini döndürür."""
        bid = int((kayit or {}).get("id") or 0)
        if not bid:
            return None
        self._betaflight_kopruleri.pop(str(bid), None)
        self._betaflight_kopru_meta.pop(str(bid), None)
        _yenileme = self._betaflight_kopru_yenilemeleri.pop(str(bid), None)
        if _yenileme is not None and not _yenileme.done():
            _yenileme.cancel()
        if self._kopru_uzerinde_mi(kayit):
            oid, hata = self._kopru_ornek_coz(kayit, firma_id)
            if hata:
                return hata
            from . import merkez_kimlik as _mk
            try:
                veri, hata = await _db_is_parcasi(
                    _mk.kopruye_sor, oid, int(firma_id), "msp_durdur",
                    {"baglanti_id": bid}, 8.0)
            except Exception as e:
                return "%s: %s" % (type(e).__name__, e)
            if hata:
                return hata
            if not bool((veri or {}).get("tamam", True)):
                return str((veri or {}).get("hata") or "Kopru MSP durdurulamadi.")
            return None
        if self.betaflight:
            self.betaflight.durdur(bid)
        return None

    def _betaflight_kopru_durumlarini_yenile(self):
        """Uzak MSP durum sorgularını telemetriyi bekletmeden planlar.

        Bu yordam tek başına MSP paketi üretmez; yalnız Köprü uygulamasının
        bellek içi oturum durumunu okur. Ağ gecikmesi ana yayın döngüsünü
        bloke etmesin diye her sorgu bağımsız bir arka plan görevidir.
        """
        if not self._betaflight_kopru_meta:
            return
        simdi = time.monotonic()
        if simdi - self._betaflight_kopru_son_yenile < 2.0:
            return
        self._betaflight_kopru_son_yenile = simdi

        for bid, meta in list(self._betaflight_kopru_meta.items()):
            onceki = self._betaflight_kopru_yenilemeleri.get(str(bid))
            if onceki is not None and not onceki.done():
                continue

            async def _birini_yenile(_bid=str(bid), _meta=dict(meta)):
                try:
                    from . import merkez_kimlik as _mk
                    def _isle():
                        return _mk.kopruye_sor(
                            _meta["ornek_id"], _meta["firma_id"],
                            "msp_durum", {"baglanti_id": int(_bid)}, 4.0)
                    veri, hata = await _db_is_parcasi(_isle)
                    if hata:
                        return
                    oturumlar = dict((veri or {}).get("oturumlar") or {})
                    durum = oturumlar.get(_bid)
                    # Oturum bu ağ isteği sürerken kapatılmış ya da
                    # farklı bir Köprüde yeniden açılmış olabilir; eski
                    # yanıtı geri yazmak yerine yok say.
                    if (isinstance(durum, dict) and
                            self._betaflight_kopru_meta.get(_bid) == _meta):
                        self._betaflight_kopruleri[_bid] = dict(durum)
                except Exception:
                    # Durum sorgusunun aksamasi yerleşik MAVLink/DJI yollarını
                    # etkilemez; son başarılı durum görünür kalır.
                    return

            gorev = asyncio.create_task(_birini_yenile())
            self._betaflight_kopru_yenilemeleri[str(bid)] = gorev

    async def _merkez_baglanti_baslat(self, websocket, kayit, firma_id):
        """Merkez turu baglantiyi baslatir; basarisizsa arayuze UYARI doner.

        Sessiz basarisizlik kabul edilemez: pilot `play`e basip yesil
        gormezse nedenini bilmek zorundadir (Faz 5'te olculen "play'e
        basiyorum hicbir sey olmuyor" kusurunun kokeni buydu).
        """
        url, hata = await self._akis_kanali_ac(kayit, firma_id)
        if hata:
            self.konsol("AKIS",
                        f"Kanal acilamadi ({kayit.get('isim') or ''}): "
                        f"{hata}", "hata")
            # Programin merkezi uyari yolu kullanilir (`uyari_yeni`):
            # boylece hata sag kose bildiriminde GORUNUR ve uyari
            # merkezinde KAYITLI kalir. Yeni bir mesaj tipi uretmek,
            # arayuzde isleyicisi olmadigi icin sessiz kusur olurdu.
            with __import__("contextlib").suppress(Exception):
                if self.pilot:
                    _p = self._pilot_bilgi(websocket) or {}
                    _ep = str(_p.get("eposta") or "")
                    _k = self.pilot.uyari_ekle(
                        _ep, "baglanti",
                        "Merkez baglantisi acilamadi "
                        f"({kayit.get('isim') or kayit.get('id')}): {hata}")
                    await websocket.send(json.dumps({
                        "tip": "uyari_yeni", "uyari": _k,
                        "okunmamis": self.pilot.okunmamis_sayi(_ep)}))
            return False
        self.dron.dinle(kayit, url)
        return True

    # =================================================================
    # OTURUM JETONU (BULGU_10a, 2026-08-17)
    # -----------------------------------------------------------------
    # Istemci artik PAROLA saklamaz; sunucudan aldigi oturum jetonunu
    # saklar ve otomatik girise onu kullanir.
    #
    # NEDEN parolayi silmek yetmedi: `localStorage`taki parola sadece
    # saklanmiyordu, 800 ms'lik zamanlayici onu otomatik giris icin
    # YENIDEN KULLANIYORDU. Alani silmek "Bilgileri sakla" islevini
    # tumuyle bozardi. Jeton ayni islevi gorur ama sizmasi kalici
    # erisim vermez.
    #
    # Tasarim:
    #   - 256 bit rastgele (`secrets.token_urlsafe(32)`)
    #   - veritabaninda YALNIZ SHA-256 ozeti tutulur (parola ozetiyle
    #     ayni mantik: veritabani sizarsa jetonlar kullanilamaz)
    #   - 30 gun gecerli
    #   - `hmac.compare_digest` ile sabit zamanli karsilastirma
    #
    # Veritabani erisimi bu kod tabaninin SQLITE UYUMLU sozlesmesini
    # kullanir: `baglanti()` + `?` yer tutucusu + `con.execute()`.
    # PG kipinde sarmalayici cevirir.
    # =================================================================
    _JETON_GUN = 30

    _JETON_SEMA = """
        CREATE TABLE IF NOT EXISTS oturum_jeton (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            eposta      TEXT NOT NULL,
            jeton_ozet  TEXT NOT NULL UNIQUE,
            olusma      REAL NOT NULL,
            bitis       REAL NOT NULL,
            aciklama    TEXT NOT NULL DEFAULT ''
        )
    """

    def _jeton_tablo_hazir(self):
        """`oturum_jeton` tablosunu bir kez olusturur.

        NEDEN `ayarlar` tablosu kullanilmadi: jetonlar kullaniciya bagli
        ve cok sayida olabilir (her cihaz icin bir tane); `ayarlar`
        anahtar-deger yapisi bunu tasimaz.

        NEDEN `REAL` epoch: sema sqlite sozdizimiyle yazilir ve PG
        kipinde sarmalayici cevirir. `TIMESTAMPTZ`/`now()` iki kipte
        ayni davranmaz; epoch her ikisinde de tasinabilir.
        """
        if getattr(self, "_jeton_tablo_ok", False):
            return True
        try:
            from .veritabani import baglanti
            with baglanti() as con:
                con.execute(self._JETON_SEMA)
                try:
                    con.execute("CREATE INDEX IF NOT EXISTS "
                                "oturum_jeton_ozet_ix "
                                "ON oturum_jeton (jeton_ozet)")
                except Exception:
                    pass
            self._jeton_tablo_ok = True
            return True
        except Exception as e:
            self.konsol("AUTH", f"Jeton tablosu hazirlanamadi: {e}",
                        "uyari")
            return False

    @staticmethod
    def _jeton_ozetle(jeton):
        import hashlib
        return hashlib.sha256(
            str(jeton or "").encode("utf-8")).hexdigest()

    def _jeton_uret(self, eposta, aciklama=""):
        """Yeni oturum jetonu uretir; DUZ jetonu dondurur.

        Duz jeton YALNIZ burada bilinir ve istemciye bir kez gonderilir.
        Veritabaninda ozeti durur.
        """
        import secrets
        import time as _t
        if not self._jeton_tablo_hazir():
            return None
        duz = secrets.token_urlsafe(32)
        ozet = self._jeton_ozetle(duz)
        simdi = _t.time()
        bitis = simdi + self._JETON_GUN * 86400
        try:
            from .veritabani import baglanti
            with baglanti() as con:
                con.execute(
                    "INSERT INTO oturum_jeton "
                    "(eposta, jeton_ozet, olusma, bitis, aciklama) "
                    "VALUES (?,?,?,?,?)",
                    ((eposta or "").strip().lower(), ozet, simdi, bitis,
                     str(aciklama or "")[:200]))
                # Suresi gecmis kayitlari temizle (tablo sismesin)
                con.execute("DELETE FROM oturum_jeton WHERE bitis < ?",
                            (simdi,))
            return duz
        except Exception as e:
            self.konsol("AUTH", f"Jeton uretilemedi: {e}", "uyari")
            return None

    def _jeton_dogrula(self, jeton):
        """Jetonu dogrular; gecerliyse kullanici sozlugunu dondurur.

        HATA DURUMUNDA `None` DONER. Veritabani erisilemezse kapi
        ACILMAZ — GDP belirtec dogrulamasinda da uygulanan kural.
        Kimlik dogrulamanin "basarisiz acik" davranmasi yaygin ve
        agir bir kusur sinifidir.
        """
        import hmac
        import time as _t
        if not jeton or not self._jeton_tablo_hazir():
            return None
        ozet = self._jeton_ozetle(jeton)
        try:
            from .veritabani import baglanti
            with baglanti() as con:
                s = con.execute(
                    "SELECT eposta, jeton_ozet FROM oturum_jeton "
                    "WHERE jeton_ozet = ? AND bitis > ?",
                    (ozet, _t.time())).fetchone()
            if not s:
                return None
            _kayit_ozet = s["jeton_ozet"] if hasattr(s, "keys") else s[1]
            _eposta = s["eposta"] if hasattr(s, "keys") else s[0]
            # Sabit zamanli karsilastirma: SQL esitligi zaten yapti,
            # katmanli savunma olarak yinelenir.
            if not hmac.compare_digest(str(_kayit_ozet), ozet):
                return None
            kul = self.kullanicilar.bul(_eposta)
            if not kul:
                # IS9B-OTURUM-DEVRI: MERKEZ DUSUSU.
                #
                # OLCULEN KUSUR (18 Agu 2026): merkez kipinde
                # kullanicilar merkez PostgreSQL'inde yasar ve yerel
                # `kullanicilar` tablosuna OTOMATIK YAZILMAZ. Yerel
                # tabloda kaydi olmayan hesap jetonu gecerli olsa bile
                # burada `None` alir ve giris SESSIZCE reddedilir.
                # Merkezdeki uc kullanicidan yalniz biri yerel tabloda
                # bulunuyordu; yani kusur gelistiricinin hesabinda
                # gorunmez, musteri hesaplarinda gorunurdu.
                #
                # KAPALI DEVRE: `etkin()` yanlissa (lokal kurulum,
                # Merkez Uygulama) bu dal HIC calismaz ve eski
                # davranis birebir korunur.
                try:
                    from . import merkez_kimlik as _mkj
                    if _mkj.etkin():
                        kul = _mkj.eposta_ile_coz(_eposta)
                except Exception as _e:
                    self.konsol("AUTH",
                                "Merkez kullanici cozumu basarisiz: %s"
                                % _e, "uyari")
                if not kul:
                    return None
            # IS49_FIRMA_TAMAMLA_v1 — jetonla giriste firma_id kaybi.
            #
            # OLCULEN KUSUR (20 Agu 2026): yerel `kullanicilar`
            # tablosunda `firma_id` KOLONU YOKTUR. Yerel kayit
            # VARSA yukaridaki `if not kul:` dali hic girilmez ve
            # merkez cozumu calismaz; donen sozlukte firma_id
            # bulunmaz. Bunun sonucunda `_ws_firma` yazilmaz,
            # `_ws_firma_id()` None doner ve `kopru_liste`
            # "Oturum gerekli." yanitiyla bos liste gonderir —
            # arayuz bunu "Cevrimici kopru yok" olarak gosterir.
            #
            # Is 44 yamasi dogruydu ama YETERSIZDI: yalniz yerel
            # kayit YOKKEN merkeze dusuyordu. Burada kayit VARSA
            # da firma_id merkezden tamamlanir.
            #
            # KAPALI DEVRE: `etkin()` False ise bu blok hicbir sey
            # yapmaz; lokal kurulum ve Merkez Uygulama davranisi
            # birebir korunur.
            #
            # BIRLESTIRME SECICIDIR. Sinav (Kume 6) korumasiz
            # `update()` ile bir GUVENLIK GERILEMESI olctu:
            # yonetici hesabi YERELDE pasiflestirmisse
            # (`aktif=0`) merkezdeki `aktif=1` degeri onu ezip
            # pasif hesabin jetonla GIRMESINE izin veriyordu.
            # Bu yuzden YALNIZ firma baglami tasinir; yetki ve
            # durum alanlari (aktif, rol, sifre) yerel kayitta
            # NE ISE OYLE KALIR.
            try:
                if not (kul or {}).get("firma_id"):
                    from . import merkez_kimlik as _mkf
                    if _mkf.etkin():
                        _mk_kul = _mkf.eposta_ile_coz(_eposta)
                        if _mk_kul and _mk_kul.get("firma_id"):
                            _birlesik = dict(kul or {})
                            for _a49 in ("firma_id",
                                         "firma_unvan",
                                         "firma_kisa_ad",
                                         "kullanici_id",
                                         "merkez_rol"):
                                if _mk_kul.get(_a49) is not None:
                                    _birlesik[_a49] = _mk_kul[_a49]
                            kul = _birlesik
            except BaseException as _e49:
                self.konsol("AUTH",
                            "Merkez firma tamamlamasi basarisiz: %s"
                            % _e49, "uyari")
            # Pasiflestirilmis hesap jetonla GIREMEZ. Bu denetim
            # atlanirsa yonetici hesabi kapattiginda kullanici eski
            # jetonuyla girmeye devam eder — sessiz ve agir kusur.
            from .kullanicilar import aktif_mi
            if not aktif_mi(kul.get("aktif")):
                return None
            kul = dict(kul)
            kul.pop("sifre", None)
            return kul
        except Exception as e:
            self.konsol("AUTH", f"Jeton dogrulanamadi: {e}", "uyari")
            return None

    def _jeton_iptal(self, jeton=None, eposta=None):
        """Tek jetonu veya kullanicinin TUM jetonlarini iptal eder."""
        if not self._jeton_tablo_hazir():
            return False
        try:
            from .veritabani import baglanti
            with baglanti() as con:
                if jeton:
                    con.execute(
                        "DELETE FROM oturum_jeton WHERE jeton_ozet = ?",
                        (self._jeton_ozetle(jeton),))
                elif eposta:
                    con.execute(
                        "DELETE FROM oturum_jeton WHERE eposta = ?",
                        ((eposta or "").strip().lower(),))
            return True
        except Exception as e:
            self.konsol("AUTH", f"Jeton iptal edilemedi: {e}", "uyari")
            return False

    def _kimlik_dogrula(self, eposta, sifre):

        """Kimligi dogrular; (kullanici|None, hata|None) doner.


        Merkezde calisan ornek (GOKTUNGU_MERKEZ_KIMLIK=1) kurumsal

        hesaplari merkez veritabanindan dogrular; boylece

        /company/ altindan kayit olan firma ayni kimlikle

        /app/ uzerinde ucus yapar. Lokal kurulumda eski davranis

        korunur (yerel kullanicilar tablosu).

        """

        try:

            from . import merkez_kimlik

            if merkez_kimlik.etkin():

                kul, hata = merkez_kimlik.dogrula(eposta, sifre)

                if kul:

                    return kul, None

                # Merkez veritabani erisilemezse yerel tabloya

                # dusulur; saha uygulamasi calismaya devam eder.

                if hata and "ulasilamadi" in str(hata):

                    self.konsol(

                        "AUTH",

                        "Merkez kimligi kullanilamadi (%s); "

                        "yerel tabloya dusuluyor" % hata,

                        "uyari")

                else:

                    return None, hata

        except Exception as e:

            self.konsol("AUTH",

                        "Merkez kimlik modulu yuklenemedi: %s" % e,

                        "uyari")

        return self.kullanicilar.dogrula(eposta, sifre), None

    def _firma_kimligi(self, websocket):
        """v2.4.53 Faz 4: oturumun kurum kimligi (unvan + logo).

        Arayuz baslik ve ucus raporu antedi icin kurumun unvanini ve
        logosunu bilmek zorundadir. Logo, kurum /company/ altinda
        kayit olurken yuklenir ve merkez `firmalar` tablosunda
        saklanir; boylece kullanici hangi bilgisayardan girerse
        girsin kendi logosuyla calisir.

        Donus: {"firma_id", "unvan", "kisa_ad", "logo_url"} veya None
        """
        firma_id = self._ws_firma_id(websocket)
        if not firma_id:
            return None
        p = self._pilot_bilgi(websocket) or {}
        kimlik = {
            "firma_id": int(firma_id),
            "unvan": str(p.get("firma_unvan") or ""),
            "kisa_ad": str(p.get("firma_kisa_ad") or ""),
        }
        # Logo, merkez uzerinden HTTP ile sunulur; ikili veriyi WS
        # mesajina gomseydik her giriste yuz KB'lar tasinirdi ve
        # tarayici onbellegi kullanilamazdi.
        try:
            from . import merkez_kimlik
            if merkez_kimlik.etkin():
                bilgi = merkez_kimlik.firma_bilgi(int(firma_id)) or {}
                if bilgi:
                    kimlik["unvan"] = (bilgi.get("unvan")
                                       or kimlik["unvan"])
                    kimlik["kisa_ad"] = (bilgi.get("kisa_ad")
                                         or kimlik["kisa_ad"])
                    if bilgi.get("logo_var"):
                        kimlik["logo_url"] = (
                            "/api/genel/firma_logo?firma_id=%d"
                            % int(firma_id))
                    # Antetli ucus raporu adres/telefon/vergi bilgisi
                    # ister; merkez kipinde bunlar kurum kaydindan
                    # gelir (yerel `sirket` ayarindan DEGIL), yoksa
                    # cok firmali ornekte tek adres tum kurumlara
                    # basilirdi.
                    for _a in ("vergi_no", "vergi_dairesi", "adres",
                               "telefon", "eposta", "web"):
                        _d = str(bilgi.get(_a) or "").strip()
                        if _d:
                            kimlik[_a] = _d
        except Exception:
            pass
        return kimlik

    def _giris_logla(self, websocket, eposta, isim, basarili, sebep):
        """v2.3.0: Giris denemesini istemci baglanti ayrintilariyla
        giris_log tablosuna yazar (basarili + basarisiz hepsi)."""
        from . import veritabani
        b = self._ws_istemci.get(id(websocket), {})
        try:
            with veritabani.baglanti() as con:
                con.execute(
                    "INSERT INTO giris_log (ts, eposta, isim, basarili,"
                    " sebep, ip, port, yerel_ip, user_agent, origin,"
                    " host, forwarded, detay)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (time.time(), eposta or "", isim or "",
                     1 if basarili else 0, sebep or "",
                     # KK_APP_DEVIR_v1: `ip` alani vekil bacagini
                     # (127.0.0.1) gosteriyordu; `kk_es` GERCEK
                     # istemci adresini tasir. `yerel_ip` ve
                     # `forwarded` DEGISMEDI - adli inceleme icin
                     # vekil bacagi da gerekli.
                     (b.get("kk_es") or b.get("ip", "")), b.get("port"),
                     b.get("yerel_ip", ""), b.get("user_agent", ""),
                     b.get("origin", ""), b.get("host", ""),
                     b.get("forwarded", ""), "{}"))
        except Exception as e:
            self.konsol("AUTH", f"giris_log yazilamadi: {e}", "hata")

    async def _izin_var(self, websocket, grup, izin, islem_adi):
        """Islem oncesi izin denetimi.

        Izin varsa True. Yoksa islem YAPILMAZ: merkezi uyari uretilir,
        istemciye 'uyari_yeni' mesaji gonderilir ve False doner.
        """
        if not self.pilot:
            return True
        p = self._pilot_bilgi(websocket)
        rol = (p or {}).get("rol", "")
        if self.pilot.izin_var(rol, grup, izin):
            return True
        ep = (p or {}).get("eposta", "")
        mesaj = (f"Yetkisiz islem engellendi: {islem_adi} "
                 f"({grup}.{izin} izni gerekli)")
        kayit = self.pilot.uyari_ekle(ep, "izin", mesaj)
        self.konsol("IZIN", f"{ep or 'anonim'}: {mesaj}", "uyari")
        try:
            await websocket.send(json.dumps({
                "tip": "uyari_yeni", "uyari": kayit,
                "okunmamis": self.pilot.okunmamis_sayi(ep)}))
        except Exception:
            pass
        return False

    # v2.4.19: ARM CHECK ekraninda gosterilen kalkis parametreleri.
    # (parametre adi, aciklama, tur) — tur: "bitmask" | "sayi" | "secim"
    ARM_CHECK_PARAMLARI = [
        ("ARMING_SKIPCHK", "Atlanan ARM ön kontrolleri", "bitmask"),
        ("ARMING_OPTIONS", "ARM seçenekleri", "bitmask"),
        ("ARMING_NEED_LOC", "ARM için konum gereksinimi", "secim"),
        ("ARMING_RUDDER", "Rudder ile ARM", "secim"),
        ("ARMING_MIS_ITEMS", "Zorunlu görev öğeleri", "bitmask"),
        ("ARMING_ACCTHRESH", "İvmeölçer hata eşiği", "sayi"),
        ("ARMING_MAGTHRESH", "Pusula alan şiddeti hata eşiği", "sayi"),
        ("BRD_SAFETY_DEFLT", "Güvenlik anahtarı varsayılanı", "secim"),
        ("BRD_SAFETYENABLE", "Güvenlik anahtarı", "secim"),
        ("BRD_SAFETYOPTION", "Güvenlik anahtarı seçenekleri", "bitmask"),
        ("GPS_TYPE", "GPS 1 tipi", "secim"),
        ("GPS1_TYPE", "GPS 1 tipi (4.6+)", "secim"),
        ("GPS_HDOP_GOOD", "Kabul edilen HDOP eşiği", "sayi"),
        ("AHRS_EKF_TYPE", "Kullanılan EKF sürümü", "secim"),
        ("EK3_ENABLE", "EKF3 etkin", "secim"),
        ("COMPASS_USE", "Pusula 1 kullanımı", "secim"),
        ("BATT_MONITOR", "Batarya izleme", "secim"),
        ("BATT_ARM_VOLT", "ARM için asgari gerilim", "sayi"),
        ("BATT_LOW_VOLT", "Düşük gerilim eşiği", "sayi"),
        ("BATT_CRT_VOLT", "Kritik gerilim eşiği", "sayi"),
        ("FS_THR_ENABLE", "Gaz failsafe", "secim"),
        ("FS_GCS_ENABLE", "GCS failsafe", "secim"),
        ("FS_EKF_ACTION", "EKF failsafe eylemi", "secim"),
        ("FS_EKF_THRESH", "EKF failsafe eşiği", "secim"),
        ("RTL_ALT", "RTL irtifası", "sayi"),
    ]

    def _arm_check_parametreleri(self, sysid):
        """v2.4.19: ARM CHECK ekrani icin onbellekten parametre degerleri.

        Onbellek bossa bos liste doner (arayuz "TUMUNU AL" onerir).
        """
        try:
            from . import veritabani as _vt
            params, _toplam, ts = _vt.param_cache_oku(sysid)
        except Exception:
            return []
        if not params:
            return []
        sonuc = []
        for ad, aciklama, tur in self.ARM_CHECK_PARAMLARI:
            if ad in params:
                sonuc.append({"ad": ad, "aciklama": aciklama,
                              "tur": tur, "deger": params[ad],
                              "onbellek_ts": ts})
        return sonuc

    # Komut -> (grup, izin, kategori) izin haritasi. Kategori pilot_log
    # kaydinda kullanilir. Haritada olmayan komutlar serbesttir.
    IZIN_HARITASI = {
        "baglanti_ekle":    ("dron", "kayit_yonetimi", "baglanti"),
        "baglanti_guncelle": ("dron", "kayit_yonetimi", "baglanti"),
        "baglanti_sil":     ("dron", "kayit_yonetimi", "baglanti"),
        "baglanti_baslat":  ("dron", "izleme", "baglanti"),
        "baglanti_durdur":  ("dron", "izleme", "baglanti"),
        # v2.4.39: SITL ikilisini indirmek diske yazma islemidir; kayit
        # yonetimi izniyle ayni seviyede tutuldu.
        "sitl_indir":       ("dron", "kayit_yonetimi", "baglanti"),
        # FAZ18-DURUM-UCU: salt okuma olcum, indirme ile ayni yetki
        "sitl_durum":       ("dron", "kayit_yonetimi", "baglanti"),
        # v2.4.49: SERVIS VE GUC YONETIMI
        # Bu komutlar makinenin tamamini etkiler (servisi durdurmak tum
        # ucuslari keser, kapatmak makineyi kapatir). Bu yuzden komut
        # islemede AYRICA rol=yonetici denetimi yapilir; buradaki kayit
        # pilot_log'a yazilmasi icindir (kim, ne zaman, ne yapti).
        "servis_eylem":     ("sistem", "servis", "servis"),
        "makine_kapat":     ("sistem", "servis", "servis"),
        "dron_isim_kaydet": ("dron", "kayit_yonetimi", "dron"),
        "dron_renk_kaydet": ("dron", "kayit_yonetimi", "dron"),
        "param_yaz":        ("dron", "parametre", "parametre"),
        # v2.5.0: MOTOR TESTI VE ARAC HAZIRLIK ARACLARI
        # Motor testi pervaneleri dondurur: pilotluk izni ister ve
        # pilot_log'a yazilir (kim, hangi motoru, hangi degerle test
        # etti). Ayrica dron.py icinde arm denetimi vardir.
        "motor_test":       ("dron", "pilotluk", "pilotaj"),
        "motor_test_dur":   ("dron", "pilotluk", "pilotaj"),
        # Ivme yon onayi kalibrasyon akisinin parcasi:
        # pervane dondurmez, arac yonelimini onaylar.
        # Kalibrasyon parametre yazdigi icin parametre izni.
        "ivme_yon_onay":    ("dron", "parametre", "parametre"),
        # Kalibrasyon mesajlari yalniz OKUMA: izleme izni yeterli.
        "kalib_mesajlari":  ("dron", "izleme", "dron"),
        # Ilk ayar ongorusu hesaptir (yazma YOK) ama sonucu parametre
        # yazmaya hazirlik oldugu icin parametre izniyle korunur.
        "ilk_ayar_ongoru":  ("dron", "parametre", "parametre"),
        "ilk_ayar_uygula":  ("dron", "parametre", "parametre"),
        "manuel_anahtar":   ("dron", "pilotluk", "pilotaj"),
        "gorev_yukle_baslat": ("dron", "pilotluk", "gorev"),
        "gorev_yukle":      ("dron", "pilotluk", "gorev"),
        "gorev_baslat":     ("dron", "pilotluk", "gorev"),
        "gorev_durdur":     ("dron", "pilotluk", "gorev"),
        "gorev_devam":      ("dron", "pilotluk", "gorev"),
        "gorev_iptal":      ("dron", "pilotluk", "gorev"),
        # v2.4.35: yarim kalmis gorevi surdurmek araci HAVADA AUTO moda
        # alir; diger gorev komutlariyla ayni yetkiyi gerektirir.
        "gorev_surdur":     ("dron", "pilotluk", "gorev"),
        "angajman_baslat":  ("dron", "angajman", "angajman"),
        # v2.5.21: yerel AI hedefine angajman (Goruntu Koprusu yerine yerel
        # kalibreli kamera hedefi). Ayni "angajman" izni istenir.
        "yerel_angajman_baslat": ("dron", "angajman", "angajman"),
        "angajman_iptal":   ("dron", "angajman", "angajman"),
        # v2.4.43: ongoru ayarlarini kaydetme de angajman yetkisi ister
        "angajman_ayar":    ("dron", "angajman", "angajman"),
        # v2.4.44: Yer Istasyonu 2. Panel joystickleri dronu UCURUR ve
        # butonlari ARM/TAKEOFF gonderir; bu yuzden baglanti ve ayar
        # komutlari da pilotluk izni ister (salt gorunum degildir).
        "istasyon2_baglan":  ("dron", "pilotluk", "pilotaj"),
        "istasyon2_kes":     ("dron", "pilotluk", "pilotaj"),
        "istasyon2_led":     ("dron", "pilotluk", "pilotaj"),
        "istasyon2_ayar":    ("dron", "pilotluk", "pilotaj"),
        "istasyon2_kalibre": ("dron", "pilotluk", "pilotaj"),
        # v2.4.45: dron haberlesme konsolunu TEMIZLEMEK kanit niteligindeki
        # satirlari siler; kayit yonetimi izni istenir. Gecmisi OKUMAK
        # serbesttir (haritada yok) — izleme yetkisi olan herkes gorebilir.
        "dron_konsol_temizle": ("dron", "kayit_yonetimi", "dron"),
        "takip_baslat":     ("dron", "pilotluk", "takip"),
        "takip_iptal":      ("dron", "pilotluk", "takip"),
        "radar_baglan":     ("radar", "parametre", "radar"),
        "radar_kes":        ("radar", "parametre", "radar"),
        "radar_ayar_yaz":   ("radar", "parametre", "radar"),
        "rtk_konum_al":     ("radar", "parametre", "radar"),
        "radar_listesi":    ("radar", "parametre", "radar"),
        "radar_kaydet":     ("radar", "parametre", "radar"),
        "radar_sil":        ("radar", "parametre", "radar"),
        "takipci_ayar":     ("radar", "hedef_yonetimi", "radar"),
        "filtre_ayar":      ("radar", "hedef_yonetimi", "radar"),
        "siniflandirma_ayar": ("radar", "hedef_yonetimi", "radar"),
        "iz_sil":           ("radar", "hedef_yonetimi", "hedef"),
        "izleri_temizle":   ("radar", "hedef_yonetimi", "hedef"),
        # M50 fiziksel cihaz eylemleri ayrı ürün lisansı (aşağıda `m50`)
        # ve mevcut sensör yönetimi rolleriyle korunur. Takip sadece açık
        # kullanıcı seçimi sonrasında başlayabildiğinden hedef-yönetimi
        # izni ayrıca zorunludur.
        "m50_baglan":       ("radar", "parametre", "m50"),
        "m50_kes":          ("radar", "parametre", "m50"),
        "m50_ayar_yaz":    ("radar", "parametre", "m50"),
        "m50_ptz":          ("radar", "parametre", "m50"),
        "m50_lens":         ("radar", "parametre", "m50"),
        "m50_aci_konumla":  ("radar", "parametre", "m50"),
        "m50_takip_sec":    ("radar", "hedef_yonetimi", "m50"),
        "m50_takip_baslat": ("radar", "hedef_yonetimi", "m50"),
        "m50_takip_durdur": ("radar", "hedef_yonetimi", "m50"),
        "m50_osd_oku":      ("radar", "parametre", "m50"),
        "m50_osd_yaz":      ("radar", "parametre", "m50"),
        "m50_aci_oku":      ("radar", "parametre", "m50"),
        "m50_onayar_liste": ("radar", "parametre", "m50"),
        "m50_onayar_kaydet": ("radar", "parametre", "m50"),
        "m50_onayar_cagir": ("radar", "parametre", "m50"),
        "m50_onayar_sil":   ("radar", "parametre", "m50"),
        "m50_onayar_hepsini_sil": ("radar", "parametre", "m50"),
        "m50_tarama":       ("radar", "parametre", "m50"),
        "m50_takip_yetenek": ("radar", "hedef_yonetimi", "m50"),
        "eo_listesi":       ("radar", "parametre", "m50"),
        "eo_kaydet":        ("radar", "parametre", "m50"),
        "eo_sil":           ("radar", "parametre", "m50"),
        "kamera_kaydet":    ("kamera", "kayit_yonetimi", "kamera"),
        # v2.4.210: video kaydi (M50 penceresi) — kamera izleme yetkisi yeter
        "video_kayit_baslat": ("kamera", "kayit_yonetimi", "kamera"),
        "video_kayit_durdur": ("kamera", "kayit_yonetimi", "kamera"),
        "video_kayit_durum":  ("kamera", "kayit_yonetimi", "kamera"),
        "kamera_sil":       ("kamera", "kayit_yonetimi", "kamera"),
        "kamera_konsol_temizle": ("kamera", "kayit_yonetimi", "kamera"),
        "kamera_dron_bagla": ("kamera", "kayit_yonetimi", "kamera"),
        "rota_kaydet":      ("rota", "kayit_yonetimi", "rota"),
        "rota_sil":         ("rota", "kayit_yonetimi", "rota"),
    }

    # Pilot loguna yazilacak komutlarin ozet detaylari (izin haritasindaki
    # her komut + dron_komut/manuel_eksen ozel islenir).
    LOG_DETAY_ALANLARI = ("sysid", "id", "isim", "ad", "deger", "aksiyon",
                          "irtifa", "lat", "lon", "alan", "rota_id",
                          "hedef_tip", "hedef_id", "saldiran_sysid",
                          "takipci_sysid", "hedef_sysid", "ip", "port",
                          "tur", "acik", "frekans", "calisma_modu")

    def _log_detay(self, k):
        return {a: k[a] for a in self.LOG_DETAY_ALANLARI
                if a in k and k[a] is not None}

    # ---- v2.4.51: PostgreSQL ilk kurulum / goc sihirbazi ----

    def _merkez_kipinde(self):
        """Bu ornek merkezde mi calisiyor? (v2.4.54)

        Merkezde (/app/) sema yonetimi OPERATORUN isidir; goc acilista
        sunucu tarafinda uygulanir (main.py). Lokal kurulumda ise
        veritabani kurumun kendi sunucusundadir ve sihirbaz gerekli
        kalir. Bu yardimci iki davranisi ayirir.

        Modul yuklenemezse LOKAL varsayilir: yanlis tarafta hata yapmak
        istersek, sihirbazi gostermek (kullanici cozebilir) sema
        guncellemesini sessizce engellemekten iyidir.
        """
        try:
            from . import merkez_kimlik as _mkk
            return bool(_mkk.merkez_kipinde())
        except Exception:
            return False

    async def _pg_sihirbaz(self, websocket, komut, k):
        """PostgreSQL sihirbaz komutlarini isler.

        Kullanici istegi: "sistemi ilk actigimda bana sunucu
        bilgilerini sorsun, ip adresi, kullanici adi, sifresi,
        veritabani adi, sonra ilk kurulumu yapsin, eger daha once
        kurulum yapildiysa ilk acilista veri tabaninda tablolarda yada
        diger seylerde bir guncelleme varsa sihirbaz acilsin ve
        guncellemeyi yapsin. tum bu sureclerde mutlaka progressbar
        olsun ve neyin surdugunu bilgilendirsin."

        Komutlar:
          pg_durum   -> yapilandirma var mi, goc gerekli mi
          pg_dene    -> baglanti bilgilerini DOGRULA (kaydetmez)
          pg_olustur -> veritabanini olustur (yoksa)
          pg_kur     -> yapilandirmayi kaydet + semayi kur (ilerlemeli)
          pg_goc     -> mevcut kurulumu guncelle (ilerlemeli)
        """
        from . import pg as _pg

        # --- MERKEZ KIPI KAPISI (v2.4.54) ---
        # Kullanici istegi (birebir): "merkez guncellemesini sen yap
        # neden kullaniciya yaptiriyorsun".
        #
        # Merkezde calisan ornek COK KIRACILIDIR ve semasi operatorun
        # sorumlulugundadir; goc acilista sunucu tarafinda uygulanir
        # (main.py). Bir pilotun WS istemcisi semayi DEGISTIREMEZ.
        #
        # `pg_durum` acik kalir: arayuz sihirbazi acmali mi diye sorar ve
        # merkez kipinde yanit her zaman "acma" der (asagida).
        if komut != "pg_durum" and self._merkez_kipinde():
            await websocket.send(json.dumps(
                {"tip": "pg_sonuc", "komut": komut, "basarili": False,
                 "merkez_kipi": True,
                 "hata": "Bu GOKTUNGU ornegi merkezde calisiyor. "
                         "Veritabani semasi merkez operatoru "
                         "tarafindan yonetilir; arayuzden "
                         "degistirilemez."}))
            return

        # --- KAPI DENETIMI (lokal kurulum) ---
        # pg_durum her zaman aciktir (arayuz sihirbazi acmali mi diye
        # sorar). Digerleri YALNIZCA yapilandirma yoksa ya da oturum
        # acmis bir yonetici varsa calisir. Aksi halde agdan baglanan
        # herkes calisan bir kurulumun veritabanini degistirebilirdi.
        if komut != "pg_durum":
            p = self._pilot_bilgi(websocket) or {}
            if _pg.yapilandirma_var() and p.get("rol") != "yonetici":
                await websocket.send(json.dumps(
                    {"tip": "pg_sonuc", "komut": komut,
                     "basarili": False,
                     "hata": "Veritabani yapilandirmasi zaten "
                             "tamamlanmis. Degistirmek icin yonetici "
                             "olarak giris yapin."}))
                return

        loop = asyncio.get_running_loop()

        if komut == "pg_durum":
            # Arayuz acilista bunu sorar ve sihirbazi buna gore acar.
            # OLCULDU: yapilandirma iki yerde bulunabilir — bellekte
            # (`yapilandirma_var()`) veya diskte (`dosya_var()`). Sunucu
            # yeni baslamis ve main.py yuklemesi basarisiz olmussa disk
            # dosyasi vardir ama bellek bostur; bu durumda sihirbaz
            # "ilk kurulum" gibi davranmamali.
            yap = _pg.yapilandirma_var() or _pg.dosya_var()
            # v2.4.195 (kullanici bildirimi: "yeniden kurdum, sihirbaz
            # gelmedi"): karar ve dayandigi dosya yolu GUNLUGE yazilir.
            # Boylece "neden sihirbaz acilmadi" sorusu tahminle degil
            # konsol satiriyla yanitlanir (ornegin eski konumda kalmis
            # bir pg.json).
            try:
                _pg_yol = _pg._pg_dosya_yolu()
            except Exception:
                _pg_yol = "?"
            self.konsol("PG", "Sihirbaz karari: %s (pg.json %s: %s)"
                        % ("yapilandirilmis, sihirbaz ACILMAZ" if yap
                           else "yapilandirma YOK, kurulum sihirbazi ACILIR",
                           "bulundu" if _pg.dosya_var() else "yok", _pg_yol),
                        "bilgi")
            durum = {"tip": "pg_durum",
                     "yapilandirildi": bool(yap),
                     "surucu_var": bool(_pg.VAR),
                     "kip": "pg" if yap else "yok",
                     "pg_dosya": _pg_yol}
            if yap:
                if not _pg.yapilandirma_var():
                    # Diskte var, bellekte yok: yukle (baglanti ACMAZ).
                    try:
                        _pg.dosyadan_yukle()
                    except Exception:
                        pass
                # Yapilandirma var: goc gerekli mi olc. Bu, kullanicinin
                # "guncelleme varsa sihirbaz acilsin" istegidir.
                try:
                    from . import goc as _goc

                    def _goc_durum():
                        from . import veritabani as _vt
                        _vt.kip_ayarla("postgresql")
                        return _goc.GocMotoru().durum()

                    d = await loop.run_in_executor(None, _db_iade_ederek, _goc_durum)
                    # DIKKAT: `durum()` "guncel" doner; "gerekli" onun
                    # TERSIDIR. Karistirmak sihirbazi hic actirmaz.
                    durum["goc_gerekli"] = not bool(d.get("guncel"))
                    durum["sema_surum"] = d.get("sema_surumu", 0)
                    durum["hedef_surum"] = d.get("hedef_surum", 0)
                    durum["bekleyen"] = d.get("bekleyen", [])
                    durum["erisim"] = True
                except Exception as e:
                    # Yapilandirma var ama sunucuya erisilemiyor: bu da
                    # sihirbaz acilmasi gereken bir durumdur (sifre
                    # degismis, sunucu tasinmis olabilir).
                    durum["erisim"] = False
                    durum["goc_gerekli"] = False
                    durum["hata"] = _pg._hata_sadelestir(e)
                # SIFRE GONDERILMEZ (`yapilandirma_oku` maskeler).
                # Anahtarlar psycopg2 adlaridir; arayuz TR adlari bekler.
                bilgi = _pg.yapilandirma_oku() or {}
                durum["sunucu"] = bilgi.get("host", "")
                durum["port"] = bilgi.get("port", 5432)
                durum["veritabani"] = bilgi.get("dbname", "")
                durum["kullanici"] = bilgi.get("user", "")

            # --- MERKEZ KIPI: SIHIRBAZI BASTIR (v2.4.54) ---
            # Arayuz `goc_gerekli` ve `yapilandirildi` alanlarina bakarak
            # sihirbazi acar (js/pg_sihirbaz.js::pgDurumGeldi). Merkezde
            # sihirbaz HICBIR kosulda acilmamali:
            #
            #   goc_gerekli  -> goc acilista sunucu tarafinda uygulandi
            #                   (main.py); bekleyen adim kalsa bile bu
            #                   pilotun cozecegi bir sey degil.
            #   yapilandirildi -> merkezde yapilandirma ortam
            #                   degiskenleriyle/dosyayla operator
            #                   tarafindan kurulur; "ilk kurulum"
            #                   sihirbazi anlamsizdir.
            #
            # `merkez_kipi` bayragi arayuze ACIKCA bildirilir; bastirma
            # sessiz olmaz, arayuz nedenini bilir. Gercek sema durumu
            # `sema_surum` / `bekleyen` alanlarinda KORUNUR (operator
            # tarayici konsolundan gorebilir), yalniz sihirbaz tetigi
            # kapatilir.
            if self._merkez_kipinde():
                durum["merkez_kipi"] = True
                durum["yapilandirildi"] = True
                durum["erisim"] = True
                if durum.get("goc_gerekli"):
                    # Operator gunlugu icin: bastirilan gercek durum.
                    self.konsol(
                        "GOC",
                        "Merkez kipi: %s bekleyen sema adimi var; "
                        "sihirbaz pilota GOSTERILMEDI. Servis yeniden "
                        "baslatildiginda goc kendiliginden uygulanir."
                        % len(durum.get("bekleyen") or []),
                        "uyari")
                durum["goc_gerekli"] = False

            await websocket.send(json.dumps(durum))
            return

        if not _pg.VAR:
            await websocket.send(json.dumps(
                {"tip": "pg_sonuc", "komut": komut, "basarili": False,
                 "hata": "PostgreSQL surucusu (psycopg2) kurulu "
                         "degil. Kurmak icin: pip3 install "
                         "psycopg2-binary"}))
            return

        bilgi = {
            "sunucu": str(k.get("sunucu") or "").strip(),
            "port": k.get("port") or 5432,
            "veritabani": str(k.get("veritabani") or "").strip(),
            "kullanici": str(k.get("kullanici") or "").strip(),
            "sifre": str(k.get("sifre") or ""),
        }

        if komut in ("pg_dene", "pg_olustur", "pg_kur"):
            # Alan dogrulamasi: bos alanla denemek ham surucu hatasi
            # uretir; kullaniciya anlamli ileti vermek gerekir.
            eksik = [a for a in ("sunucu", "veritabani", "kullanici")
                     if not bilgi[a]]
            if eksik:
                adlar = {"sunucu": "Sunucu adresi",
                         "veritabani": "Veritabani adi",
                         "kullanici": "Kullanici adi"}
                await websocket.send(json.dumps(
                    {"tip": "pg_sonuc", "komut": komut,
                     "basarili": False,
                     "hata": ", ".join(adlar[a] for a in eksik)
                             + " zorunludur."}))
                return
            try:
                bilgi["port"] = int(bilgi["port"])
                if not (1 <= bilgi["port"] <= 65535):
                    raise ValueError
            except (TypeError, ValueError):
                await websocket.send(json.dumps(
                    {"tip": "pg_sonuc", "komut": komut,
                     "basarili": False,
                     "hata": "Port 1-65535 arasinda bir sayi olmali."}))
                return

        # `pg.dene`/`pg.veritabani_olustur` ADLI PARAMETRE alir (sozluk
        # DEGIL). Arayuz TR alan adlari gonderir; esleme burada yapilir.
        cagri = {"host": bilgi["sunucu"], "port": bilgi["port"],
                 "veritabani": bilgi["veritabani"],
                 "kullanici": bilgi["kullanici"], "sifre": bilgi["sifre"]}

        if komut == "pg_dene":
            # Kullanici istegi: "her ilerle dediginde mutlaka girilen
            # bilgileri dogrulamali". Bu komut KAYDETMEZ.
            s = await loop.run_in_executor(None, _db_iade_ederek, lambda: _pg.dene(**cagri))
            s["tip"] = "pg_sonuc"
            s["komut"] = "pg_dene"
            s["basarili"] = bool(s.get("tamam"))
            # Arayuz `tablo_sayisi` ve ust duzey `citext` okur; `dene()`
            # bunlari `mevcut_tablo` ve `yetki.citext` olarak doner.
            s["tablo_sayisi"] = s.get("mevcut_tablo", 0)
            s["citext"] = bool((s.get("yetki") or {}).get("citext"))
            await websocket.send(json.dumps(s))
            return

        if komut == "pg_olustur":
            s = await loop.run_in_executor(None, _db_iade_ederek, lambda: _pg.veritabani_olustur(**cagri))
            s["tip"] = "pg_sonuc"
            s["komut"] = "pg_olustur"
            s["basarili"] = bool(s.get("tamam"))
            await websocket.send(json.dumps(s))
            return

        # --- pg_kur ve pg_goc: ILERLEMELI ---
        # Kullanici istegi: "mutlaka progressbar olsun ve neyin
        # surdugunu bilgilendirsin". Ilerleme, goc motorunun geri
        # cagirmasi ile ANLIK yayinlanir; sonda tek seferde degil.
        async def _ilerleme_gonder(yuzde, ileti, ad=""):
            try:
                await websocket.send(json.dumps(
                    {"tip": "pg_ilerleme", "komut": komut,
                     "yuzde": yuzde, "ileti": ileti, "ad": ad}))
            except Exception:
                # Arayuz kapanmis olabilir; goc DEVAM ETMELI.
                pass

        kuyruk = asyncio.Queue()

        # OLCULEN KUSUR (dene_pg_ws.py): yayinlanan yuzde GERI SARIYOR.
        # Olculen dizi: [2, 6, 0.0, 5.0, ...] — hazirlik adimlari 2 ve 6
        # bildirir, ardindan goc motoru kendi olceginde 0'dan baslar.
        # Kullanici cubugun geri atladigini gorur ve surecin bastan
        # basladigini sanir.
        #
        # Kelepce goc motorunun ICINDE degil BURADA olmali: motorun
        # kendi kelepcesi yalnizca kendi cagrilarini kapsar, hazirlik
        # adimlari cagiran taraftan gelir. Tek dogru yer, iki kaynagin
        # BIRLESTIGI yayin noktasidir.
        _tavan = [0.0]

        def _geri_cagir(yuzde, ileti, ad=""):
            # Bu islev ayri bir is parcasinda (executor) calisir;
            # asyncio kuyruguna guvenli sekilde aktarilir.
            try:
                y = float(yuzde)
            except (TypeError, ValueError):
                y = _tavan[0]
            y = max(0.0, min(100.0, y))
            if y < _tavan[0]:
                # Geri sarma: yuzde KORUNUR, ileti metni GUNCELLENIR
                # (boylece "neyin surdugu" bilgisi kaybolmaz).
                y = _tavan[0]
            else:
                _tavan[0] = y
            try:
                loop.call_soon_threadsafe(
                    kuyruk.put_nowait, (round(y, 1), ileti, ad))
            except Exception:
                pass

        async def _kuyruk_bosalt():
            while True:
                try:
                    y, i, a = await kuyruk.get()
                except asyncio.CancelledError:
                    return
                if y is None:
                    return
                await _ilerleme_gonder(y, i, a)

        bosaltici = asyncio.create_task(_kuyruk_bosalt())

        try:
            if komut == "pg_kur":
                def _kur():
                    from . import goc as _goc
                    from . import veritabani as _vt
                    # Hazirlik adimlari 0-6 aralIgIni kullanir; goc
                    # motoru 0'dan baslar ama `calistir()` icindeki tek
                    # yonlu kelepce geri sarmayi onler (olculen kusur).
                    _geri_cagir(2, "Baglanti dogrulaniyor")
                    s = _pg.dene(**cagri)
                    if not s.get("tamam"):
                        return {"tamam": False,
                                "hata": s.get("hata") or "Baglanti yok"}
                    if not s.get("yetki_tablo"):
                        # Yetki YOKSA sema kurulumu yarida patlar;
                        # yapilandirmayi diske yazmadan once dur.
                        return {"tamam": False,
                                "hata": "Bu kullanicinin tablo olusturma "
                                        "yetkisi yok. PostgreSQL'de "
                                        "GRANT CREATE verin veya "
                                        "veritabani sahibi olan bir "
                                        "kullanici girin."}
                    _geri_cagir(6, "Yapilandirma kaydediliyor")
                    # diske_yaz=True -> veri/pg.json (izin 0600). Bir
                    # sonraki aciliste main.py bunu okur.
                    _pg.yapilandir(diske_yaz=True, **cagri)
                    _vt.kip_ayarla("postgresql")
                    return _goc.GocMotoru(
                        konsol=lambda m: self.konsol("PG", m)
                    ).calistir(ilerleme=_geri_cagir)
                self.konsol("PG", "Kurulum basladi (pg_kur): %s@%s:%s/%s"
                            % (cagri.get("user", "?"), cagri.get("host", "?"),
                               cagri.get("port", "?"), cagri.get("dbname", "?")), "bilgi")
                sonuc = await loop.run_in_executor(None, _db_iade_ederek, _kur)
                self.konsol("PG", "Kurulum bitti (pg_kur): %s%s"
                            % ("BASARILI" if sonuc.get("tamam") else "HATA",
                               "" if sonuc.get("tamam") else " — " + str(sonuc.get("hata") or "")),
                            "basari" if sonuc.get("tamam") else "hata")
            else:
                def _goc_uygula():
                    from . import goc as _goc
                    from . import veritabani as _vt
                    if not (_pg.yapilandirma_var() or _pg.dosya_var()):
                        return {"tamam": False,
                                "hata": "Veritabani yapilandirilmamis."}
                    if not _pg.yapilandirma_var():
                        _pg.dosyadan_yukle()
                    _vt.kip_ayarla("postgresql")
                    return _goc.GocMotoru(
                        konsol=lambda m: self.konsol("PG", m)
                    ).calistir(ilerleme=_geri_cagir)
                sonuc = await loop.run_in_executor(None, _db_iade_ederek, _goc_uygula)
        except Exception as e:
            sonuc = {"tamam": False, "hata": _pg._hata_sadelestir(e)}

        # Kuyrugu kapat ve bekleyen tum ilerleme iletilerini gonder.
        kuyruk.put_nowait((None, "", ""))
        try:
            await asyncio.wait_for(bosaltici, timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            bosaltici.cancel()

        # OLCULDU: `calistir()` "surum" DONDURMEZ ("uygulanan" doner).
        # Sema surumu defterden okunur; okunamazsa 0 gonderilir.
        _sema = 0
        try:
            from . import goc as _goc2
            _sema = await loop.run_in_executor(None, _db_iade_ederek, _goc2.sema_surumu)
        except Exception:
            pass
        yanit = {"tip": "pg_sonuc", "komut": komut,
                 "basarili": bool(sonuc.get("tamam")),
                 "hata": sonuc.get("hata", ""),
                 "adimlar": sonuc.get("adimlar", []),
                 "uygulanan": sonuc.get("uygulanan", 0),
                 "sema_surum": _sema}

        # ---- v2.4.67: KURULUM HESABI BILGISI ----
        #
        # OLCULEN KUSUR (2026-08-16, kullanici bildirimi):
        # "kopru yazilimina dogru kullanici adi ve sifre ile
        #  girebilmeme ragmen merkez yazilimina hic bir sifre ile
        #  giremiyorum"
        #
        # Kok neden: temiz kurulumda yerel `kullanicilar` tablosu
        # bostur; `_ilk_yonetici_guvence()` `kurulum@yerel` hesabini
        # RASTGELE sifreyle acar (v2.4.66'da gomulu `gokkubbe2026`
        # kaldirildi). Sifre yalnizca kurulum KONSOLUNA ve
        # `ilk_giris.txt` dosyasina yazilir. Servis olarak kurulunca
        # konsol gorunmez -> kullanici KILITLI kalir.
        #
        # Sihirbazin 4. adimi (merkez esitlemesi) ATLANABILIR olmak
        # ZORUNDA (kullanicinin acik sarti: "isterse kapali devre
        # kullanabiliyor"). Bu yuzden cozum "Atla'yi kaldirmak" degil,
        # atlayan kullaniciya kurulum kimligini EKRANDA gostermektir.
        if yanit["basarili"]:
            try:
                yanit["kurulum_hesabi"] = self._kurulum_hesabi_oku()
            except Exception as e:
                # Bilgilendirme amacli; kurulumu ASLA basarisiz saymaz.
                self.konsol("PG", "kurulum hesabi okunamadi: %s" % e,
                            "uyari")
        if yanit["basarili"]:
            self.konsol("PG", f"{komut} tamamlandi "
                        f"(sema surum {yanit['sema_surum']})", "basari")
        else:
            self.konsol("PG", f"{komut} basarisiz: {yanit['hata']}",
                        "hata")
        # v2.4.196: yanit gonderilemezse (WS bu arada koptuysa) SESSIZ
        # kalinmaz; istemci yeniden baglaninca pg_durum ile toparlar.
        try:
            await websocket.send(json.dumps(yanit))
        except Exception as _ge:
            self.konsol("PG", "Sihirbaz yaniti gonderilemedi (%s: %s); istemci "
                        "yeniden baglaninca durumu sorup toparlayacak"
                        % (type(_ge).__name__, _ge), "uyari")

    # ------------------------------------------------------------------
    # v2.4.67: KURULUM HESABI KIMLIGI
    # ------------------------------------------------------------------
    def _kurulum_hesabi_oku(self):
        """Kurulum hesabinin kimligini dondurur (sihirbaz gosterimi).

        Donus: {"var": bool, "eposta": str, "sifre": str, "kaynak": str}

        NEDEN BU YORDAM VAR
        ===================
        Temiz kurulumda yerel `kullanicilar` tablosu bostur ve
        `_ilk_yonetici_guvence()` `kurulum@yerel` hesabini RASTGELE
        sifreyle acar. Sifre yalnizca kurulum konsoluna ve
        `ilk_giris.txt`e yazilir; servis olarak kurulunca konsol
        gorunmez. Merkez esitlemesini atlayan kullanici sisteme HIC
        giremez (olculen kusur, 2026-08-16).

        GUVENLIK GEREKCESI
        ==================
        Sifre YALNIZCA `ilk_giris.txt` dosyasindan okunur; dosya
        kurulumu yapan surecin sahibine ait ve izni 0600'dur. Yordam
        sifreyi UYDURMAZ ve kayitli ozetten geri cozmeye CALISMAZ
        (ozet tek yonludur). Dosya yoksa `sifre` bos doner ve arayuz
        kullaniciyi dosyanin yoluna yonlendirir.

        Hesap zaten degistirilmisse (merkez esitlemesi kosmus ya da
        kullanici baska hesap acmis) `var: False` doner; boylece
        gecersiz bir kimlik gosterilmez.
        """
        import os
        sonuc = {"var": False, "eposta": "", "sifre": "",
                 "kaynak": "", "yol": ""}
        eposta = "kurulum@yerel"
        # 1) Hesap hala duruyor mu? Esitleme kostuysa silinmis/degismis
        #    olabilir; o durumda kimlik GOSTERILMEMELIDIR.
        try:
            from . import veritabani as _vt
            with _vt.baglanti() as con:
                satir = con.execute(
                    "SELECT eposta FROM kullanicilar WHERE eposta = ?",
                    (eposta,)).fetchone()
                if not satir:
                    return sonuc
                # Tabloda BASKA hesap da varsa (esitleme kosmus)
                # kurulum hesabi artik birincil kimlik degildir.
                adet = con.execute(
                    "SELECT COUNT(*) FROM kullanicilar").fetchone()[0]
        except Exception:
            return sonuc
        sonuc["var"] = True
        sonuc["eposta"] = eposta
        sonuc["tek_hesap"] = (int(adet) == 1)
        # 2) Sifreyi ilk_giris.txt dosyasindan oku.
        try:
            from .sabitler import VERI_KOKU
            yol = os.path.join(VERI_KOKU, "ilk_giris.txt")
            sonuc["yol"] = yol
            if os.path.exists(yol):
                with open(yol, "r", encoding="utf-8") as f:
                    for satir in f:
                        if satir.lower().startswith("sifre"):
                            _, _, d = satir.partition(":")
                            sonuc["sifre"] = d.strip()
                            sonuc["kaynak"] = "ilk_giris.txt"
                            break
        except Exception:
            pass
        return sonuc

    # ------------------------------------------------------------------
    # v2.4.68: KURULUM PENCERESI DENETIMI
    # ------------------------------------------------------------------
    def _kurulum_penceresi_acik(self):
        """Ilk yonetici HENUZ olusmadi mi? (kimlik dogrulamasiz komutlar)

        `yonetici_kur` komutu giris ONCESI calismak zorundadir; bu da
        agdan baglanan herkesin erisebilecegi bir kapi acar. Riski
        sinirlamak icin kapi yalnizca su durumda aciktir:

          - Tablo bos, VEYA
          - Tabloda SADECE `kurulum@yerel` guvence hesabi var.

        Gercek bir yonetici olustugu anda kapi KAPANIR; sifre degisimi
        artik yalnizca Kullanicilar bolumunden (oturum + izin denetimi
        ile) yapilabilir.

        Hata durumunda `False` doner (kapali): denetim yapilamiyorsa
        guvenli taraf kapali olmaktir.
        """
        try:
            from . import veritabani as _vt
            with _vt.baglanti() as con:
                satirlar = con.execute(
                    "SELECT eposta FROM kullanicilar").fetchall()
        except Exception:
            # Veritabani henuz yok/erisilemez: sihirbaz zaten
            # `pg_kur` adimindadir, hesap adimina gelinmemistir.
            return True
        gercek = [s[0] for s in satirlar
                  if str(s[0] or "").strip().lower() != "kurulum@yerel"]
        return len(gercek) == 0

    # ------------------------------------------------------------------
    # v2.4.68: KURULUM SIHIRBAZINDA YONETICI HESABI TANIMLAMA
    # ------------------------------------------------------------------
    async def _yonetici_kur(self, websocket, k):
        """Kullanicinin KENDI belirledigi yerel yonetici hesabini kurar.

        Istek : {"tip":"yonetici_kur","eposta":..,"sifre":..,
                 "ad_soyad":..}
        Yanit : {"tip":"yonetici_kur_sonuc","basarili":bool,"hata":str,
                 "eposta":str,"degistirildi":bool}

        NEDEN BU KOMUT VAR (olculen kusur, 2026-08-16)
        ==============================================
        Merkez Uygulama'yi satin alan sirket, kapali devre kurulumda
        sisteme HIC giremiyordu. Zincir soyleydi:

          1. Temiz kurulumda yerel `kullanicilar` tablosu bos olur.
          2. `_ilk_yonetici_guvence()` `kurulum@yerel` hesabini
             RASTGELE bir sifreyle acar.
          3. Sifre yalnizca kurulum konsoluna ve `ilk_giris.txt`e
             yazilir. Servis olarak kurulunca konsol GORUNMEZ.
          4. Merkez esitlemesi atlanirsa (kullanicinin acik sarti:
             "isterse kapali devre kullanabiliyor") kullanicinin
             elinde hicbir kimlik kalmaz.

        v2.4.67 bunu "uretilen sifreyi ekranda goster" ile cozmeye
        calisti. Sahada YETMEDI: kullanicinin bildirimi ---
        "hala merkez yazilima kendi sifremle giremiyorum, en azindan
        sihirbazda bana sorsun kullanici adi sifreyi, merkezden
        bagimsiz olarak".

        Dogru cozum: kullanici kendi kimligini KENDISI belirlesin.
        Bu komut merkeze HIC bagli degildir; kapali devre kurulumda da
        calisir.

        GUVENLIK
        ========
        - Sifre en az 8 karakter (arayuz de ayrica denetler; sunucu
          tarafi son savunma hattidir, arayuze GUVENILMEZ).
        - Ozet `sifre_hashle()` ile uretilir; duz metin SAKLANMAZ.
        - Rol daima `yonetici`: sihirbazi kosan kisi kurulum sahibidir.
        - Hesap zaten varsa sifresi GUNCELLENIR (kullanici sihirbazi
          yeniden kosturuyor olabilir; "zaten kayitli" hatasi verip
          onu yeniden kilitlemek kusurun tekrari olurdu).
        - Islem sonrasi `kurulum@yerel` guvence hesabi SILINIR: artik
          gercek bir yonetici vardir ve rastgele sifreli, kimsenin
          bilmedigi bir hesabin acik kalmasi gereksiz bir saldiri
          yuzeyidir.
        """
        eposta = str(k.get("eposta") or "").strip().lower()
        sifre = str(k.get("sifre") or "")
        ad_soyad = str(k.get("ad_soyad") or "").strip()

        def _hata(msg):
            return {"tip": "yonetici_kur_sonuc", "basarili": False,
                    "hata": msg, "eposta": eposta,
                    "degistirildi": False}

        if not eposta or "@" not in eposta:
            await websocket.send(json.dumps(
                _hata("Gecerli bir e-posta adresi girin.")))
            return
        if len(sifre) < 8:
            await websocket.send(json.dumps(
                _hata("Sifre en az 8 karakter olmalidir.")))
            return

        try:
            from .kullanicilar import KullaniciYoneticisi
            ky = (getattr(self, "kullanicilar", None)
                  or KullaniciYoneticisi())
            mevcut = ky.bul(eposta)
            if mevcut:
                # Sihirbaz yeniden kosuyor: sifreyi ve rolu tazele.
                ky.guncelle(eposta, {"sifre": sifre, "rol": "yonetici",
                                     "aktif": 1})
                degistirildi = True
            else:
                ok, hata = ky.ekle(eposta, ad_soyad=ad_soyad,
                                   unvan="Sistem Yoneticisi",
                                   rol="yonetici", sifre=sifre)
                if not ok:
                    await websocket.send(json.dumps(
                        _hata(str(hata or "Hesap olusturulamadi."))))
                    return
                degistirildi = False

            # Guvence hesabini kaldir (artik gercek yonetici var).
            silindi = False
            if eposta != "kurulum@yerel":
                try:
                    from . import veritabani as _vt
                    with _vt.baglanti() as con:
                        con.execute(
                            "DELETE FROM kullanicilar "
                            "WHERE eposta = ?", ("kurulum@yerel",))
                    silindi = True
                except Exception as e:
                    # Kurulumu ASLA basarisiz saymaz: yonetici hesabi
                    # olustu, asil amaca ulasildi.
                    self.konsol("KUR", "guvence hesabi silinemedi: %s"
                                % e, "uyari")

            # `ilk_giris.txt` artik gecersiz: icindeki rastgele sifre
            # calismayacak. Yanlis yonlendirmemek icin kaldiriyoruz.
            try:
                import os
                from .sabitler import VERI_KOKU
                y = os.path.join(VERI_KOKU, "ilk_giris.txt")
                if os.path.exists(y):
                    os.remove(y)
            except Exception:
                pass

            self.konsol("KUR", "yerel yonetici hesabi hazir: %s%s"
                        % (eposta,
                           " (guvence hesabi kaldirildi)" if silindi
                           else ""), "basari")
            await websocket.send(json.dumps(
                {"tip": "yonetici_kur_sonuc", "basarili": True,
                 "hata": "", "eposta": eposta,
                 "degistirildi": degistirildi}))
        except Exception as e:
            self.konsol("KUR", "yonetici hesabi kurulamadi: %s" % e,
                        "hata")
            await websocket.send(json.dumps(
                _hata("Hesap olusturulamadi: %s" % e)))

    # ------------------------------------------------------------------
    # v2.4.66: MERKEZ KULLANICI ESITLEMESI
    # ------------------------------------------------------------------
    async def _lisans_yenile(self, websocket, k):
        """v2.4.201: Merkezden guncel lisans belgesini indirip yerine koyar.

        Istek : {"tip":"lisans_yenile","adres":..,"eposta":..,"sifre":..}
        Yanit : {"tip":"lisans_yenile_sonuc","basarili":bool,"hata":str,
                 "lisans": <yetki ozeti>}
        Yalniz yonetici. Ag islemi executor'da kosar (WS dongusu donmasin).
        Basarida yeni ozet yanita konur; arayuz menuleri servis yeniden
        baslatilmadan gunceller. Sifre gunluge/duruma yazilmaz.
        """
        p = self._pilot_bilgi(websocket) or {}
        if p.get("rol") != "yonetici":
            await websocket.send(json.dumps(
                {"tip": "lisans_yenile_sonuc", "basarili": False,
                 "hata": "Lisansi yalnizca yonetici yenileyebilir."}))
            return
        adres = str(k.get("adres") or "").strip()
        eposta = str(k.get("eposta") or "").strip()
        sifre = str(k.get("sifre") or "")
        eksik = [a for a, v in (("Merkez adresi", adres), ("E-posta", eposta),
                                ("Sifre", sifre)) if not v]
        if eksik:
            await websocket.send(json.dumps(
                {"tip": "lisans_yenile_sonuc", "basarili": False,
                 "hata": ", ".join(eksik) + " zorunludur."}))
            return
        loop = asyncio.get_event_loop()

        def _calistir():
            from . import merkez_esitle as _me
            from . import lisans as _lis
            belge, hata = _me.lisans_cek(adres, eposta, sifre)
            if hata:
                return None, hata
            tamam, hata2 = _lis.lisans_yaz(belge)
            if not tamam:
                return None, hata2
            return _lis.yetki_ozeti(), ""
        try:
            ozet, hata = await loop.run_in_executor(None, _db_iade_ederek, _calistir)
        except Exception as e:
            ozet, hata = None, "Lisans yenileme basarisiz: %s" % e
        if hata:
            self.konsol("LISANS", "Lisans yenilenemedi: %s" % hata, "hata")
            await websocket.send(json.dumps(
                {"tip": "lisans_yenile_sonuc", "basarili": False, "hata": hata}))
            return
        self.konsol("LISANS", "Lisans belgesi yenilendi: %s (ai=%s radar=%s "
                    "gccdual=%s m50=%s)" % (ozet.get("firma_unvan") or "?",
                    ozet.get("ai"), ozet.get("radar"), ozet.get("gccdual"),
                    ozet.get("m50")), "basari")
        await websocket.send(json.dumps(
            {"tip": "lisans_yenile_sonuc", "basarili": True, "hata": "",
             "lisans": ozet}))

    async def _merkez_esitle(self, websocket, k):
        """Merkezden firma kullanicilarini cekip yerel tabloya yazar.

        Istek : {"tip":"merkez_esitle","adres":..,"eposta":..,"sifre":..}
        Yanit : {"tip":"merkez_esitle_sonuc","basarili":bool,"hata":str,
                 "cekilen":int,"eklendi":int,"guncellendi":int}

        Ag islemi oldugu icin ayri is parcaciginda kosar; aksi halde
        20 saniyelik zaman asimi boyunca TUM WebSocket dongusu
        (dolayisiyla telemetri) donar. Bu, olculmus bir kalip:
        `_pg_sihirbaz` da ayni nedenle `run_in_executor` kullanir.
        """
        adres = str(k.get("adres") or "").strip()
        eposta = str(k.get("eposta") or "").strip()
        sifre = str(k.get("sifre") or "")

        # Alan dogrulamasi: bos alanla denemek ham ag hatasi uretir;
        # kullaniciya anlamli ileti vermek gerekir (pg sihirbazi ile
        # ayni desen).
        eksik = []
        if not adres:
            eksik.append("Merkez adresi")
        if not eposta:
            eksik.append("E-posta")
        if not sifre:
            eksik.append("Sifre")
        if eksik:
            await websocket.send(json.dumps(
                {"tip": "merkez_esitle_sonuc", "basarili": False,
                 "hata": ", ".join(eksik) + " zorunludur."}))
            return

        loop = asyncio.get_event_loop()

        def _calistir():
            from . import merkez_esitle as _me
            return _me.esitle(adres, eposta, sifre)

        try:
            ozet, hata = await loop.run_in_executor(None, _db_iade_ederek, _calistir)
        except Exception as e:
            ozet, hata = None, "Esitleme basarisiz: %s" % e

        if hata:
            self.konsol("MERKEZ", "Kullanici esitlemesi basarisiz: %s"
                        % hata, "hata")
            await websocket.send(json.dumps(
                {"tip": "merkez_esitle_sonuc", "basarili": False,
                 "hata": hata}))
            return

        self.konsol("MERKEZ",
                    "Kullanici esitlemesi tamam: %d cekildi, %d eklendi, "
                    "%d guncellendi"
                    % (ozet["cekilen"], ozet["eklendi"],
                       ozet["guncellendi"]), "basari")
        yanit = {"tip": "merkez_esitle_sonuc", "basarili": True,
                 "hata": ""}
        yanit.update(ozet)
        await websocket.send(json.dumps(yanit))

    # ------------------------------------------------------------------
    # v2.4.67: KAPALI DEVRE KOPRU KIMLIK YONETIMI
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # BULGU_07: DJI KOPRU BELIRTECI (GDP 8790 kimlik dogrulamasi)
    # ------------------------------------------------------------------
    # SOZLESME
    #   istek  {"tip":"dji_belirtec_durum"}
    #          {"tip":"dji_belirtec_uret"}
    #          {"tip":"dji_belirtec_sil"}
    #   yanit  {"tip":"dji_belirtec_sonuc","komut":..,"basarili":bool,
    #           "hata":str,"tanimli":bool,"kuyruk":str,"belirtec":str}
    #
    # `belirtec` YALNIZ `uret` yaniti icinde doludur. `durum` yaniti
    # belirteci ASLA dondurmez; yalnizca `tanimli` bayragi ve son 4
    # karakter (`kuyruk`) doner. Gerekce: `durum` popup her acildiginda
    # cagrilir; belirteci her seferinde gondermek onu tarayici
    # belleginde ve WebSocket gunlugunde gereksizce cogaltirdi.
    #
    # KUYRUK NEDEN VAR: kullanici Android'e girdigi belirtecin DOGRU
    # olani olup olmadigini ayirt edebilmeli. Tam belirteci gostermeden
    # bunu saglamanin en ucuz yolu son 4 karakter. Tek basina ise
    # yaramaz (43 karakterlik bir sirrin 4 karakteri).
    async def _dji_belirtec_komut(self, websocket, komut, k):
        import secrets

        def yanit(basarili, hata="", tanimli=False, kuyruk="",
                  belirtec=""):
            return json.dumps({
                "tip": "dji_belirtec_sonuc", "komut": komut,
                "basarili": bool(basarili), "hata": str(hata),
                "tanimli": bool(tanimli), "kuyruk": str(kuyruk),
                "belirtec": str(belirtec)})

        p = self._pilot_bilgi(websocket) or {}
        if p.get("rol") != "yonetici":
            self.konsol("IZIN", "DJI belirtec islemi reddedildi "
                        f"(yonetici degil): {p.get('eposta', '?')}",
                        "uyari")
            await websocket.send(yanit(
                False, "DJI kopru belirtecini yalnizca yonetici "
                       "yonetebilir."))
            return

        try:
            mevcut = str((self.ayarlar.yukle() or {}).get(
                "dji_belirtec") or "")
        except Exception as e:
            # Ayar okunamiyorsa DURUM bildirilemez. Sessizce "tanimsiz"
            # demek yanlis olurdu: kullanici belirteci yeniden uretir,
            # eski belirtecle calisan cihazlar sessizce kopar.
            self.konsol("DJI", f"Belirtec durumu okunamadi: {e}", "hata")
            await websocket.send(yanit(
                False, "Ayarlar okunamadi; belirtec durumu bilinmiyor."))
            return

        if komut == "dji_belirtec_durum":
            await websocket.send(yanit(
                True, "", bool(mevcut), mevcut[-4:] if mevcut else ""))
            return

        if komut == "dji_belirtec_sil":
            self.ayarlar.kaydet({"dji_belirtec": ""})
            self.konsol("DJI", "Kopru belirteci SILINDI; uzak DJI "
                        f"baglantilari reddedilecek ({p.get('eposta', '?')})",
                        "uyari")
            self._pilot_log(websocket, "ayar", "dji_belirtec_sil", {})
            await websocket.send(yanit(True, "", False, ""))
            return

        # uret: 32 bayt -> 43 karakter URL-guvenli metin.
        # `secrets` kullanilir; `random` ONGORULEBILIR ve bir sir icin
        # kabul edilemez.
        yeni = secrets.token_urlsafe(32)
        self.ayarlar.kaydet({"dji_belirtec": yeni})
        # Belirtec ASLA gunluge yazilmaz.
        self.konsol("DJI", "Yeni kopru belirteci uretildi "
                    f"(...{yeni[-4:]}) ({p.get('eposta', '?')})", "basari")
        self._pilot_log(websocket, "ayar", "dji_belirtec_uret",
                        {"kuyruk": yeni[-4:]})
        await websocket.send(yanit(True, "", True, yeni[-4:], yeni))

    async def _kopru_kimlik_komut(self, websocket, komut, k):
        """Yerel kurulumun kopru kurulum kimliklerini yonetir.

        Istekler:
            {"tip":"kopru_kimlik_liste"}
            {"tip":"kopru_kimlik_uret","ad":..,"aciklama":..}
            {"tip":"kopru_kimlik_sil","ornek_id":..}
        Yanit:
            {"tip":"kopru_kimlik_sonuc","komut":..,"basarili":bool,
             "hata":str,"liste":[...],"kimlik":{...},"uc":str}

        ## GIZLI YALNIZ BIR KEZ DONER

        `kopru_kimlik_uret` yanitindaki `gizli` veritabaninda ozet olarak
        saklanir ve BIR DAHA okunamaz. Arayuz bunu kullaniciya gostermek
        ve kopyalatmak zorundadir; kaybedilirse yeni kimlik uretilmesi
        gerekir. Sirri geri okunabilir tutmak, veritabani yedegi sizan
        her durumda tum saha makinelerinin ele gecirilmesi anlamina
        gelirdi.
        """
        def _yanit(basarili, hata="", **ek):
            p = {"tip": "kopru_kimlik_sonuc", "komut": komut,
                 "basarili": bool(basarili), "hata": str(hata)}
            p.update(ek)
            return json.dumps(p, ensure_ascii=False)

        # ---- Kip denetimi ----
        # Merkez kipinde kimlikler /company/ panelinden uretilir ve
        # merkez veritabaninda yasar. Burada ikinci bir uretim yolu
        # acmak, ayni kimligi iki ayri tabloda tutmak olurdu.
        try:
            if self._merkez_kipinde():
                await websocket.send(_yanit(
                    False, "Merkez kipinde kopru kimlikleri kurumsal "
                           "panelden yonetilir."))
                return
        except Exception:
            pass

        # ---- Yetki: yalnizca yonetici ----
        p = self._pilot_bilgi(websocket) or {}
        if p.get("rol") != "yonetici":
            self.konsol("IZIN", "Kopru kimlik istegi reddedildi "
                        f"(yonetici degil): {p.get('eposta', '?')}",
                        "uyari")
            await websocket.send(_yanit(
                False, "Kopru kimliklerini yalnizca yonetici "
                       "yonetebilir."))
            return

        from . import kopru_kabul as _kk
        loop = asyncio.get_event_loop()

        # Koprunun gireceei adres. `aktif_ws_port` gercekte ALINAN
        # porttur (8765 mesgulse siradaki denenir); sabit yazmak yanlis
        # adres gosterir.
        try:
            _port = int(getattr(self, "aktif_ws_port", 0) or 8765)
        except (TypeError, ValueError):
            _port = 8765

        try:
            if komut == "kopru_kimlik_liste":
                liste = await loop.run_in_executor(None, _db_iade_ederek, _kk.kopru_listesi)
                await websocket.send(_yanit(
                    True, "", liste=liste, port=_port,
                    canli=_kk.ROLE.sayi()))
                return

            if komut == "kopru_kimlik_uret":
                ad = str(k.get("ad") or "").strip() or "Saha Makinesi"
                aciklama = str(k.get("aciklama") or "").strip()

                def _uret():
                    return _kk.kopru_kaydet(ad, aciklama)

                kimlik = await loop.run_in_executor(None, _db_iade_ederek, _uret)
                self.konsol("KOPRU",
                            "Yeni kopru kimligi uretildi: %s (ornek %s)"
                            % (ad, kimlik.get("ornek_id")), "basari")
                self._pilot_log(websocket, "KOPRU", "kimlik_uret",
                                {"ad": ad,
                                 "ornek_id": kimlik.get("ornek_id")})
                liste = await loop.run_in_executor(None, _db_iade_ederek, _kk.kopru_listesi)
                await websocket.send(_yanit(
                    True, "", kimlik=kimlik, liste=liste, port=_port))
                return

            if komut == "kopru_kimlik_sil":
                try:
                    oid = int(k.get("ornek_id") or 0)
                except (TypeError, ValueError):
                    oid = 0
                if oid <= 0:
                    await websocket.send(_yanit(
                        False, "Kopru kimligi belirtilmedi."))
                    return

                # Canli baglantiyi DUSUR: kayit iptal edildiginde soket
                # acik kalirsa kopru komut almaya devam eder ve
                # operator kimligi iptal ettigini sanir.
                o = _kk.ROLE.ornek_ile(oid)
                if o is not None:
                    with contextlib.suppress(Exception):
                        await o.soket.close()

                await loop.run_in_executor(None, _db_iade_ederek, _kk.kopru_sil, oid)
                self.konsol("KOPRU", "Kopru kimligi iptal edildi "
                            "(ornek %d)" % oid, "uyari")
                self._pilot_log(websocket, "KOPRU", "kimlik_sil",
                                {"ornek_id": oid})
                liste = await loop.run_in_executor(None, _db_iade_ederek, _kk.kopru_listesi)
                await websocket.send(_yanit(True, "", liste=liste,
                                            port=_port))
                return
        except Exception as e:
            self.konsol("KOPRU", "Kimlik islemi basarisiz: %s: %s"
                        % (type(e).__name__, e), "hata")
            await websocket.send(_yanit(
                False, "%s: %s" % (type(e).__name__, e)))

    # ------------------------------------------------------------------
    # v2.4.65: MERKEZ UYGULAMA LISANSI — SUNUCU TARAFI UST SINIR
    # ------------------------------------------------------------------
    # Hangi komut hangi lisans alanina bagli. Arayuzdeki menu
    # gorunurlugu ile AYNI alanlari okur; ikisi ayrilirsa "menude yok
    # ama komut calisiyor" celiskisi dogar.
    #
    # `ai` alani BILEREK bos birakildi: AI ozelligi koltuk/abonelik
    # tarafinda merkez sunucuda denetleniyor (Faz 3). Burada ikinci bir
    # kapi acmak, ayni kurali iki yerde tutmak olurdu.
    LISANS_KOMUT_ALANI = {
        "radar_baglan": "radar",
        "radar_kes": "radar",
        "radar_ayar_yaz": "radar",
        "rtk_konum_al": "radar",
        "radar_listesi": "radar", "radar_kaydet": "radar", "radar_sil": "radar",
        "takipci_ayar": "radar",
        "filtre_ayar": "radar",
        "siniflandirma_ayar": "radar",
        # M50 lisans alanı yoksa `_lisans_izni_var` bu komutları reddeder;
        # eski paketlerde yanlışlıkla radar lisansına açılmaz.
        "m50_ayar_oku": "m50",
        "m50_baglan": "m50",
        "m50_kes": "m50",
        "m50_ayar_yaz": "m50",
        "m50_ptz": "m50",
        "m50_lens": "m50",
        "m50_aci_konumla": "m50",
        "m50_takip_sec": "m50",
        "m50_takip_baslat": "m50",
        "m50_takip_durdur": "m50",
        "m50_osd_oku": "m50", "m50_osd_yaz": "m50",
        "m50_aci_oku": "m50", "m50_onayar_liste": "m50",
        "m50_onayar_kaydet": "m50", "m50_onayar_cagir": "m50",
        "m50_onayar_sil": "m50", "m50_onayar_hepsini_sil": "m50",
        "m50_tarama": "m50", "m50_takip_yetenek": "m50",
        "eo_listesi": "m50", "eo_kaydet": "m50", "eo_sil": "m50",
        "istasyon2_portlar": "gccdual",
        "istasyon2_baglan": "gccdual",
        "istasyon2_kes": "gccdual",
        "istasyon2_led": "gccdual",
        "istasyon2_kalibre": "gccdual",
        "istasyon2_ayar": "gccdual",
    }

    def _lisans_ozeti_al(self):
        """Lisans yetki ozeti; modul yoksa sinirsiz sayilir."""
        try:
            from . import lisans as _lis
            return _lis.yetki_ozeti()
        except Exception:
            # Lisans modulu ice aktarilamazsa UST SINIR UYGULANMAZ.
            # Yanlis tarafta hata yapmak gerekiyorsa, calisan bir
            # kurulumu kilitlemek yerine eski davranisi surdurmek
            # tercih edilir; kullanici sahada v2.4.24 ile uculuyor.
            return None

    async def _lisans_izni_var(self, websocket, komut):
        alan = self.LISANS_KOMUT_ALANI.get(komut)
        if not alan:
            return True
        ozet = self._lisans_ozeti_al()
        # Lisans dosyasi YOKSA sinir uygulanmaz: olagan kurulum ve
        # VEILOX merkez ornegi eski davranisini birebir surdurur.
        # Lisans yalnizca Merkez Uygulama kipinde soz sahibidir.
        if not ozet or not ozet.get("lisansli"):
            return True
        if ozet.get(alan):
            return True
        ad = {"radar": "Radar", "m50": "M50 Elektro-Optik"}.get(
            alan, "Yer Kontrol Istasyonu Dual")
        # Sessiz basarisizlik yasagi: operator NEDEN'i gormek zorunda.
        # Kapali devre kurulumda destek arayamayabilir; ekranda ne
        # yapacagini okumali.
        #
        # `_uyari_gonder` KULLANILIR, duz `{"tip": "uyari"}` GONDERILMEZ:
        # arayuz (ws.js) yalniz `uyari_yeni` tipini tanir ve govdeyi ic
        # ice `uyari` alanindan okur. Duz bicim sessizce dusurulur ve
        # operator hicbir sey gormez (bkz. `_uyari_gonder` govdesi).
        await self._uyari_gonder(
            websocket, alan,
            f"{ad} modulu bu Merkez Uygulama lisansinda KAPALI. "
            f"Yetki VEILOX tarafindan sirket bazinda acilir; "
            f"kurumsal panelden (Abonelik) talep edin.",
            "hata")
        self.konsol("LISANS", f"{komut} reddedildi: {alan} yetkisi yok",
                    "hata")
        return False

    # ------------------------------------------------------------------
    # KK_APP_WS_v1 — KABA KUVVET KANCALARI (WS)
    # ------------------------------------------------------------------
    def _kk_es_al(self, websocket) -> str:
        """Bu baglanti icin kaba kuvvet anahtari (GERCEK istemci adresi)."""
        try:
            b = self._ws_istemci.get(id(websocket)) or {}
            return str(b.get("kk_es") or b.get("ip") or "")
        except BaseException:
            return ""

    async def _kk_ws_denetle(self, websocket, uc: str, k) -> bool:
        """Komut islenmeden ONCE cagrilir.

        Bloklu ise istemciye `giris_sonuc` reddi gonderir ve `True`
        doner (cagiran hemen donmeli). Ayrica artan gecikmeyi uygular.

        Gecikme `asyncio.sleep` ile yapilir: WS islemcisi tek olay
        dongusunde calistigi icin `time.sleep` TUM baglantilari
        dondururdu.
        """
        if _KK is None:
            return False
        es = self._kk_es_al(websocket)
        if not es:
            return False
        hesap = ""
        try:
            hesap = _KK.hesap_coz(k if isinstance(k, dict) else {})
        except BaseException:
            hesap = ""
        try:
            engel = _KK.denetle(es, uc, hesap)
        except BaseException:
            return False
        if engel:
            kalan, sebep = engel
            mesaj = ("Cok fazla basarisiz deneme. "
                     "%d saniye sonra yeniden deneyin." % int(kalan))
            if sebep == "hesap":
                mesaj = ("Bu hesap gecici olarak kilitli. "
                         "%d saniye sonra yeniden deneyin." % int(kalan))
            with __import__("contextlib").suppress(BaseException):
                await websocket.send(__import__("json").dumps({
                    "tip": "giris_sonuc", "tamam": False, "hata": mesaj,
                    "kilit": True, "kalan": int(kalan), "sebep": sebep,
                }))
            return True
        try:
            bekle = float(_KK.gecikme(es, uc) or 0.0)
        except BaseException:
            bekle = 0.0
        if bekle > 0:
            with __import__("contextlib").suppress(BaseException):
                await asyncio.sleep(min(bekle, 5.0))
        return False

    def _kk_ws_sonuc(self, websocket, uc: str, k, basarili: bool) -> None:
        """Komut islendikten SONRA sonucu sayaclara yazar."""
        if _KK is None:
            return
        es = self._kk_es_al(websocket)
        if not es:
            return
        hesap = ""
        with __import__("contextlib").suppress(BaseException):
            hesap = _KK.hesap_coz(k if isinstance(k, dict) else {})
        with __import__("contextlib").suppress(BaseException):
            if basarili:
                _KK.basarili(es, uc, hesap)
            else:
                _KK.basarisiz(es, uc, hesap)

    async def _komut_isle_korumali(self, websocket, k):
        """`asyncio.create_task` ile siradan bagimsiz kosan komutlar icin
        istisna kalkani (v2.4.197): gorev icindeki hata baglantiyi
        dusurmez, gunluge yazilir; sihirbaz istemcisi bekcisiyle toparlar."""
        try:
            await self._komut_isle(websocket, k)
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            import traceback
            self.konsol("WS", "Komut hatasi (%s): %s: %s"
                        % ((k or {}).get("tip"), type(e).__name__, e), "hata")
            self.konsol("WS", traceback.format_exc()[-800:], "hata")

    async def _komut_isle(self, websocket, k):
        """Tek bir istemci komutunu isler."""
        # v2.4.18: bozuk/null JSON gelirse WS baglantisini komple dusurmek
        # yerine sessizce yok say (onceki surumde AttributeError ile
        # baglanti handler'i cokuyordu).
        if not isinstance(k, dict):
            return
        komut = k.get("tip")

        # ---- v2.4.65: MERKEZ UYGULAMA LISANSI UST SINIRI ----
        # Arayuzde menuyu gizlemek YETMEZ: istemci WebSocket komutunu
        # dogrudan gonderebilir. Ayni ilke Faz 8'de koprude uygulandi
        # (suzgec sunucuda, arayuz yalniz suzulmus listeyi cizer).
        #
        # Bu denetim IZIN_HARITASI'ndan ONCE calisir: lisans yoksa
        # modul HIC yoktur, rol izni sormanin anlami kalmaz. Sirayi
        # tersine cevirmek, yetkisiz modulun izin hatasi yerine rol
        # hatasi dondurmesine yol acardi ve operator sorunu yanlis
        # yerde arardi.
        if not await self._lisans_izni_var(websocket, komut):
            return

        # ---- v2.1.7: merkezi izin denetimi + pilot loglama ----
        harita = self.IZIN_HARITASI.get(komut)
        if harita:
            grup, izin, kategori = harita
            if not await self._izin_var(websocket, grup, izin, komut):
                return
            self._pilot_log(websocket, kategori, komut, self._log_detay(k))
        elif komut == "dron_komut":
            aksiyon = str(k.get("aksiyon", ""))
            if aksiyon == "param":
                grup, izin, kategori = "dron", "parametre", "parametre"
            else:
                grup, izin, kategori = "dron", "pilotluk", "pilotaj"
            if not await self._izin_var(websocket, grup, izin,
                                        f"dron_komut:{aksiyon}"):
                return
            self._pilot_log(websocket, kategori,
                            "dron_komut:" + aksiyon, self._log_detay(k))
        elif komut == "manuel_eksen":
            # Surekli akan eksen verisi: loglanmaz ama izin denetlenir
            if not await self._izin_var(websocket, "dron", "pilotluk",
                                        "manuel_eksen"):
                return
        elif komut in ("suru_kur", "suru_dagit", "suru_cikar"):
            # v2.4.3: suru komutlari pilotluk izni gerektirir
            if not await self._izin_var(websocket, "dron", "pilotluk",
                                        komut):
                return
            self._pilot_log(websocket, "pilotaj", komut,
                            self._log_detay(k))

        if komut == "baglanti_ekle":
            # {"tip":"baglanti_ekle","isim":"..","tur":"seri|tcp|udp",
            #  "port":"..","baud":57600,"host":".."}
            host = k.get("host")
            if str(k.get("tur") or "").lower() == "merkez":
                # v2.4.53: merkez turunde hedef sunucu ayri alanlarda
                # gelir (ornek_uid/sunucu_ad/firma); sanal turde alinan
                # kararla ayni gerekcelerle `host` alaninda birlestirilir.
                host = self._merkez_host_derle(k)
                if not host:
                    # Sessiz basarisizlik yasagi (v2.4.45 dersi):
                    # hedefsiz merkez kaydi arayuzde "var" gorunup asla
                    # calismaz. Kullanici NEDEN'i gormek zorunda.
                    await websocket.send(json.dumps(
                        {"tip": "baglanti_hata",
                         "hata": "Merkez baglantisi icin acik sunucu "
                                 "listesinden bir sunucu secilmeli."}))
                    await self._baglanti_listesi_duyur()
                    return
            elif str(k.get("tur") or "").lower() == "sanal":
                # v2.4.39: sanal dronun tipi/konumu ayri alanlarda gelir;
                # kayit semasinda yeni kolon acmamak icin `host` alaninda
                # "tip|lat|lon|adet" olarak birlestirilir. Kolon eklemek
                # sema gocu gerektirir, kullanicinin calisan v2.4.24
                # veritabani korunmak zorunda.
                host = self._sanal_host_derle(k)
                if not host:
                    # v2.4.45: eskiden bos host ile ekle() cagriliyor,
                    # kayit olusmuyor ve hata da bildirilmiyordu ->
                    # kullanici sanal dron ekliyor, hicbir sey olmuyor.
                    # Sessiz basarisizlik en pahali kusur tipidir.
                    await self._sanal_hata(
                        websocket,
                        "Sanal dron icin tip ve konum (enlem/boylam) "
                        "zorunludur.")
                    await self._baglanti_listesi_duyur()
                    return
            # v2.4.53: kayit, olusturan pilotun firmasina baglanir; aksi
            # halde merkezde baska firmalar da bu baglantiyi gorur.
            _fid = self._ws_firma_id(websocket)
            # v2.4.53 Faz 7: kayit bir KOPRU makinesine baglanabilir.
            # Kopru kimligi ISTEMCIDEN gelir, bu yuzden SAHIPLIK
            # DOGRULANIR: baska firmanin koprusune kayit baglanamaz.
            _kid = k.get("kopru_ornek_id")
            if _kid in ("", 0, "0"):
                _kid = None
            if _kid is not None:
                try:
                    _kid = int(_kid)
                except (TypeError, ValueError):
                    _kid = None
            if _kid is not None and not self._kopru_sahibi_mi(_kid, _fid):
                await websocket.send(json.dumps(
                    {"tip": "baglanti_hata",
                     "hata": "Kopru bulunamadi veya yetkiniz yok."}))
                return
            kayit, hata = self.baglantilar.ekle(
                k.get("isim"), k.get("tur"), k.get("port"),
                baud=k.get("baud"), host=host,
                firma_id=_fid, kopru_ornek_id=_kid,
                ucus_yazilimi=k.get("ucus_yazilimi"))
            if hata:
                await websocket.send(json.dumps(
                    {"tip": "baglanti_hata", "hata": hata}))
            elif not kayit:
                # v2.4.45: hata dizesi bos olsa bile kayit yoksa
                # kullanici NEDEN'i gormek zorunda.
                await websocket.send(json.dumps(
                    {"tip": "baglanti_hata",
                     "hata": "Baglanti kaydi olusturulamadi "
                             "(bilinmeyen sebep)."}))
            await self._baglanti_listesi_duyur()
        elif komut == "baglanti_guncelle":
            # v2.4.12: {"tip":"baglanti_guncelle","id":N,"isim":"..",
            #  "port":"..","baud":57600,"host":".."} — tur degistirilemez.
            bid = int(k.get("id", 0))
            eski = self.baglantilar.bul(bid)
            if not eski:
                await websocket.send(json.dumps(
                    {"tip": "baglanti_hata", "hata": "Kayit bulunamadi."}))
                await self._baglanti_listesi_duyur()
                return
            # Dogrulama (ekle() ile ayni kurallar; tur sabit kalir)
            isim = str(k.get("isim") or "").strip()
            port = str(k.get("port") or "").strip()
            hata = None
            if not isim:
                hata = "Baglanti adi bos olamaz."
            elif not port and eski.get("tur") not in ("dji", "sanal",
                                                       "merkez"):
                # v2.4.39: sanal turde port kullaniciya sorulmaz, dahili
                # atanir; bos gelmesi hata degil.
                # v2.4.53: merkez turunde port ANLAMSIZ (hedef sunucu
                # ornek_uid ile adreslenir), bos gelmesi normaldir.
                hata = "Port bos olamaz."
            elif (eski.get("tur") == "tcp"
                  and not str(k.get("host") or "").strip()):
                hata = "Sunucu adresi (host) bos olamaz."
            if hata:
                await websocket.send(json.dumps(
                    {"tip": "baglanti_hata", "hata": hata}))
                await self._baglanti_listesi_duyur()
                return
            # Eski istemciler alan gondermez: mevcut/varsayilan ArduPilot
            # korunur. DJI icin istemci verisi yok sayilir ve `dji` atanir.
            yazilim, yhata = self.baglantilar.ucus_yazilimi_coz(
                eski.get("tur"), k.get("ucus_yazilimi",
                                        eski.get("ucus_yazilimi")))
            if yhata:
                await websocket.send(json.dumps(
                    {"tip": "baglanti_hata", "hata": yhata}))
                await self._baglanti_listesi_duyur()
                return
            alanlar = {"isim": isim,
                       "port": port or eski.get("port"),
                       "ucus_yazilimi": yazilim}
            if eski.get("tur") == "seri":
                try:
                    alanlar["baud"] = int(k.get("baud") or 57600)
                except (TypeError, ValueError):
                    alanlar["baud"] = 57600
            elif eski.get("tur") == "tcp":
                alanlar["host"] = str(k.get("host") or "").strip()
            elif eski.get("tur") == "sanal":
                # Tip/konum degistirilebilir; port dahili kalir.
                yeni_host = self._sanal_host_derle(k)
                if yeni_host:
                    alanlar["host"] = yeni_host
                alanlar["port"] = port or eski.get("port")
            elif eski.get("tur") == "merkez":
                # v2.4.53: hedef sunucu degistirilebilir. Bos gelirse
                # eski hedef KORUNUR — aksi halde kullanici adi
                # duzeltirken baglantinin hedefi sessizce silinirdi.
                yeni_host = self._merkez_host_derle(k)
                if yeni_host:
                    alanlar["host"] = yeni_host
                alanlar["port"] = port or eski.get("port") or "0"
            # v2.4.55: baglantinin kuruldugu KOPRU makinesi degistirilebilir
            # (dron baska bir saha bilgisayarina tasinmis olabilir). Alan
            # yalniz istekte GECIYORSA ele alinir; eski arayuzler alani
            # gondermez ve o kayitlarin koprusu korunmalidir.
            if "kopru_ornek_id" in k and eski.get("tur") not in (
                    "sanal", "merkez"):
                _nk = k.get("kopru_ornek_id")
                if _nk in ("", 0, "0"):
                    _nk = None
                if _nk is not None:
                    try:
                        _nk = int(_nk)
                    except (TypeError, ValueError):
                        _nk = None
                # Sahiplik denetimi ekleme yolundakiyle AYNI: baska
                # firmanin koprusune kayit tasinamaz.
                if _nk is not None and not self._kopru_sahibi_mi(
                        _nk, self._ws_firma_id(websocket)):
                    await websocket.send(json.dumps(
                        {"tip": "baglanti_hata",
                         "hata": "Kopru bulunamadi veya yetkiniz yok."}))
                    await self._baglanti_listesi_duyur()
                    return
                alanlar["kopru_ornek_id"] = _nk
            # Aktif baglanti: once durdur, guncelle, yeniden baslat
            d = self._baglanti_durumlari().get(str(bid), {})
            aktifti = d.get("durum") in ("bagli", "baglaniyor", "dinliyor")
            if aktifti:
                if self._calisan_ucus_yazilimi(eski) == "betaflight":
                    await self._betaflight_durdur(eski, self._ws_firma_id(websocket))
                else:
                    self._dron_durdur_hepsi(bid)
                self._otomatik_protokoller.pop(str(bid), None)
                if self.dji_kopru:
                    self.dji_kopru.durdur(bid)
                # Sanal: SITL sureci de durdurulmali. Yeni tip/konum
                # ancak yeni bir SITL sureciyle etkili olur.
                if eski.get("tur") == "sanal" and self.sitl:
                    self.sitl.durdur(bid)
            yeni = self.baglantilar.guncelle(bid, **alanlar)
            self.konsol("BAGLANTI",
                        f"Kayit guncellendi: {isim} (id={bid})", "basari")
            if aktifti:
                # Kayit degistiyse eski kanal GECERSIZDIR (hedef port,
                # baud veya kopru degismis olabilir); yeniden acilir.
                await self._akis_kanali_kapat(bid)
            if yeni and aktifti:
                tamam, hata = await self._baglanti_baslat_uygula(
                    websocket, yeni, self._ws_firma_id(websocket))
                if not tamam:
                    await websocket.send(json.dumps({
                        "tip": "baglanti_hata", "hata": hata or
                        "Baglanti yeniden baslatilamadi."}))
            await self._baglanti_listesi_duyur()
        elif komut == "baglanti_sil":
            bid = int(k.get("id", 0))
            _eski = self.baglantilar.bul(bid)
            if _eski and self._calisan_ucus_yazilimi(_eski) == "betaflight":
                await self._betaflight_durdur(_eski, self._ws_firma_id(websocket))
            else:
                self._dron_durdur_hepsi(bid)
            self._otomatik_protokoller.pop(str(bid), None)
            if self.dji_kopru:
                self.dji_kopru.durdur(bid)
            # v2.4.39: kayit silinmeden ONCE SITL durdurulmali; aksi halde
            # surec kalir ve tuttugu port blogu bir daha kullanilamaz
            # (kayit gittigi icin hangi porta ait oldugu da bilinemez).
            if self.sitl:
                self.sitl.durdur(bid)
            # Kayit silinmeden ONCE kanal kapatilmali: kapatma cagrisi
            # `_akis_kanallari` defterine dayanir, ama kaydin gitmesi
            # sonraki tanilamayi imkansiz kilar.
            await self._akis_kanali_kapat(bid)
            self.baglantilar.sil(bid)
            await self._baglanti_listesi_duyur()
        elif komut == "baglanti_baslat":
            bid = int(k.get("id", 0))
            kayit = self.baglantilar.bul(bid)
            if kayit:
                tamam, hata = await self._baglanti_baslat_uygula(
                    websocket, kayit, self._ws_firma_id(websocket))
                if not tamam:
                    await websocket.send(json.dumps({
                        "tip": "baglanti_hata", "hata": hata or
                        "Baglanti baslatilamadi."}))
            await self._baglanti_listesi_duyur()
        elif komut == "baglanti_durdur":
            bid = int(k.get("id", 0))
            _kayit = self.baglantilar.bul(bid)
            if _kayit and self._calisan_ucus_yazilimi(_kayit) == "betaflight":
                await self._betaflight_durdur(_kayit, self._ws_firma_id(websocket))
            else:
                self._dron_durdur_hepsi(bid)
            self._otomatik_protokoller.pop(str(bid), None)
            if self.dji_kopru:
                self.dji_kopru.durdur(bid)
            if self.sitl:
                self.sitl.durdur(bid)
            # Akis kanali dinleyici durduktan SONRA kapatilir: ters
            # sirada kapatilsa son paketler yazilacak soket bulamaz ve
            # gunluge anlamsiz hata dokulur.
            await self._akis_kanali_kapat(bid)
            await self._baglanti_listesi_duyur()
        elif komut == "sitl_durum":
            # FAZ18-DURUM-UCU: sihirbazin 2. adimi indirmeye gerek olup
            # olmadigini bundan ogrenir.
            await self._sitl_durum(
                websocket, str(k.get("sanal_tip") or "multirotor"))
        elif komut == "sitl_indir":
            # v2.4.39: SITL ikilisi guncelleme paketine GOMULMEZ (paket
            # 100-300 KB olmak zorunda, ikili ~30 MB). Kullanici istegiyle
            # indirilir. Indirme uzun surer -> ayri is parcaciginda.
            tip = str(k.get("sanal_tip") or "multirotor")
            await self._sitl_indir(websocket, tip)
        elif komut == "radar_baglan":
            # v2.4.62: BOS IP ARTIK VARSAYILANA DUSMEZ.
            #
            # Kullanici istegi: "radar ben merkez yazilimdan hangi ipye
            # baglan dersem o ipye baglanmali, kopru kendisine baglan
            # komutu gelmeden baglanmamali".
            #
            # Eskiden bu satir `or RADAR_VARSAYILAN_IP` ile bos alani
            # sessizce 192.168.8.186 yapiyordu. Sonuc: operator alani
            # bos biraktiginda kendi girmedigi bir adrese baglanma
            # denemesi baslıyor, panelde sebebi anlasilmayan bir hata
            # cikiyordu. Sessiz varsayim yerine GORUNUR uyari veriyoruz.
            ip = str(k.get("ip", "")).strip()
            if not ip:
                await self._uyari_gonder(
                    websocket, "radar",
                    "Radar IP adresi girilmedi. Baglanmak icin radarin "
                    "saha agindaki adresini yazin.")
                return
            try:
                rport = int(k.get("port", RADAR_VARSAYILAN_PORT))
            except (TypeError, ValueError):
                rport = RADAR_VARSAYILAN_PORT
            if not (0 < rport < 65536):
                await self._uyari_gonder(
                    websocket, "radar",
                    "Radar portu gecersiz: %s" % (k.get("port"),))
                return
            # v2.4.60: merkezde radar SAHADA acilir (KUSUR-RADAR-KOPRU).
            # Radar 192.168.8.x yerel agindadir; merkez sunucu oraya
            # ulasamaz ve panel "timed out" gosterirdi.
            # v2.4.190: radar_id ile hedeflenir; verilmezse birincil radar.
            _rid = k.get("radar_id")
            if self._merkez_kipinde():
                # Faz C: adres KAYDA da yazilir; kopru yeniden baslasa
                # bile panel dogru IP'yi gosterir ve kopru kendi kalici
                # kaydindan ayni radara baglanir.
                _ist = self._radar_istemci(_rid)
                if hasattr(self.radar, "kayitlar"):
                    try:
                        self.radar.kayitlar.guncelle(
                            int(getattr(_ist, "radar_id", 1) or 1),
                            {"ip": ip, "port": rport})
                    except Exception:
                        pass
                await self._radar_kopruye(
                    websocket, "radar_baglan",
                    {"ip": ip, "port": rport,
                     "isim": getattr(_ist, "isim", "")}, k)
            elif hasattr(self.radar, "istemciler"):
                if not self.radar.baglan(ip, rport, _rid):
                    await self._uyari_gonder(websocket, "radar",
                                             "Radar kaydi bulunamadi: %s" % _rid)
            else:
                self.radar.baglan(ip, rport)

        elif komut == "radar_kes":
            _rid = k.get("radar_id")
            if self._merkez_kipinde():
                await self._radar_kopruye(websocket, "radar_kes", {}, k)
            elif hasattr(self.radar, "istemciler"):
                self.radar.kes(_rid)
            else:
                self.radar.kes()

        elif komut == "radar_ayar_oku":
            _rid = k.get("radar_id")
            if self._merkez_kipinde():
                await self._radar_kopruye(websocket, "radar_ayar_oku",
                                          {}, k)
            else:
                _ist = self._radar_istemci(_rid)
                if _ist is not None:
                    with self.kilit:
                        _ist.ayar_kuyruk.append(("oku",))

        # ---- v2.4.191: coklu elektro-optik kayit yonetimi ----
        elif komut == "eo_listesi":
            _eo = getattr(self, "eo", None)
            if _eo is not None:
                await websocket.send(json.dumps({
                    "tip": "eo_listesi", "cihazlar": _eo.kayitlar.listele()}))

        elif komut == "eo_kaydet":
            _eo = getattr(self, "eo", None)
            if _eo is not None:
                try:
                    _eid = k.get("eo_id") or k.get("id")
                    if _eid:
                        _eo.kayitlar.guncelle(int(_eid), k)
                    else:
                        _eid = _eo.kayitlar.ekle(k)
                    _eo.tazele()
                    # v2.4.194 (kullanici istegi): kimlik (IP, port,
                    # kullanici adi, parola) CIHAZ KAYDIYLA BIRLIKTE
                    # kaydedilir; kontrol panelinde ayrica sorulmaz.
                    # Parola/kullanici BOS gonderildiyse mevcut deger
                    # KORUNUR (duzenleme formu parolayi geri gostermez;
                    # bos alan "degistirme" demektir). Kayit yerel ayar
                    # anahtarindadir; parola WS'e/telemetriye asla cikmaz.
                    _kimlik = {}
                    for _a in ("ip", "port", "kullanici", "parola"):
                        _v = k.get(_a)
                        if _v not in (None, "", 0):
                            _kimlik[_a] = _v
                    _y = _eo.yerel(int(_eid)) if _eid else None
                    if _kimlik and _y is not None:
                        try:
                            _y._ayar_yaz_ic(_kimlik)
                        except Exception as _ke:
                            self.konsol("M50", "EO kimligi yazilamadi: %s" % _ke, "uyari")
                    self.konsol("M50", "Elektro-optik kaydi guncellendi: #%s %s"
                                % (_eid, k.get("isim") or ""), "basari")
                    await websocket.send(json.dumps({
                        "tip": "eo_listesi", "cihazlar": _eo.kayitlar.listele()}))
                except Exception as _e:
                    await self._uyari_gonder(websocket, "M50",
                                             "EO kaydi yazilamadi: %s" % _e, "hata")

        elif komut == "eo_sil":
            _eo = getattr(self, "eo", None)
            if _eo is not None:
                try:
                    _eid = int(k.get("eo_id") or k.get("id") or 0)
                except (TypeError, ValueError):
                    _eid = 0
                if _eid and len(_eo.kayitlar.listele()) > 1:
                    _y = _eo.yereller.get(_eid)
                    if _y is not None:
                        try:
                            await asyncio.to_thread(_y.uygula, "kes", {})
                        except Exception:
                            pass
                    _eo.kayitlar.sil(_eid)
                    _eo.tazele()
                    self.konsol("M50", "Elektro-optik kaydi silindi: #%d" % _eid)
                    await websocket.send(json.dumps({
                        "tip": "eo_listesi", "cihazlar": _eo.kayitlar.listele()}))
                else:
                    await self._uyari_gonder(websocket, "M50",
                                             "Son elektro-optik kaydi silinemez.", "hata")

        # ---- v2.4.190: coklu radar kayit yonetimi ----
        elif komut == "radar_listesi":
            if hasattr(self.radar, "kayitlar"):
                await websocket.send(json.dumps({
                    "tip": "radar_listesi",
                    "radarlar": self.radar.kayitlar.listele()}))

        elif komut == "radar_kaydet":
            if hasattr(self.radar, "kayitlar"):
                try:
                    _rid = k.get("radar_id") or k.get("id")
                    if _rid:
                        self.radar.kayitlar.guncelle(int(_rid), k)
                    else:
                        _rid = self.radar.kayitlar.ekle(k)
                    self.radar.tazele()
                    self.konsol("RADAR", "Radar kaydi guncellendi: #%s %s"
                                % (_rid, k.get("isim") or ""), "basari")
                    await websocket.send(json.dumps({
                        "tip": "radar_listesi",
                        "radarlar": self.radar.kayitlar.listele()}))
                except Exception as _e:
                    await self._uyari_gonder(websocket, "radar",
                                             "Radar kaydi yazilamadi: %s" % _e)

        elif komut == "radar_sil":
            if hasattr(self.radar, "kayitlar"):
                try:
                    _rid = int(k.get("radar_id") or k.get("id") or 0)
                except (TypeError, ValueError):
                    _rid = 0
                if _rid and len(self.radar.kayitlar.listele()) > 1:
                    self.radar.kes(_rid)
                    self.radar.kayitlar.sil(_rid)
                    self.radar.tazele()
                    self.konsol("RADAR", "Radar kaydi silindi: #%d" % _rid)
                    await websocket.send(json.dumps({
                        "tip": "radar_listesi",
                        "radarlar": self.radar.kayitlar.listele()}))
                else:
                    await self._uyari_gonder(websocket, "radar",
                                             "Son radar kaydi silinemez.")

        elif komut == "radar_ayar_yaz":
            a = {}
            try:
                if "frekans" in k:
                    a["frekans"] = max(0, min(7, int(k["frekans"])))
                if "hiz_esigi" in k:
                    a["hiz_esigi"] = max(0, min(3, int(k["hiz_esigi"])))
                if "tespit_esigi" in k:
                    a["tespit_esigi"] = max(0, min(2, int(k["tespit_esigi"])))
                if "rcs_esigi" in k:
                    a["rcs_esigi"] = max(0, min(2, int(k["rcs_esigi"])))
                if k.get("calisma_modu") in C20_MOD_KODLARI:
                    a["calisma_modu"] = k["calisma_modu"]
            except (TypeError, ValueError):
                a = {}
            _rid = k.get("radar_id")
            if self._merkez_kipinde():
                # Merkez yonu de KOPRUYE gider: kalibrasyon radarin
                # bulundugu makinede saklanir, cunku izleri cografi
                # konuma ceviren kod artik orada kosuyor. Merkezde
                # tutulsa saha makinesi yeniden baslatildiginda izler
                # dogru yone donmezdi.
                gonder = dict(a)
                if "merkez_yonu" in k:
                    gonder["merkez_yonu"] = k.get("merkez_yonu")
                if gonder:
                    await self._radar_kopruye(websocket, "radar_ayar_yaz",
                                              gonder, k)
            else:
                _ist = self._radar_istemci(_rid)
                # Merkez yonu yerel bir kalibrasyon: kayda/dosyaya
                # kaydedilir, radara gonderilmez (protokolde registeri yok)
                if "merkez_yonu" in k and _ist is not None:
                    try:
                        my = float(k["merkez_yonu"]) % 360.0
                        with self.kilit:
                            _ist.radar_ayarlar["merkez_yonu"] = my
                        if hasattr(self.radar, "kayitlar"):
                            self.radar.kayitlar.guncelle(
                                getattr(_ist, "radar_id", 1), {"merkez_yonu": my})
                        else:
                            self.ayarlar.kaydet({"radar_merkez_yonu": my})
                    except (TypeError, ValueError):
                        pass
                if a and _ist is not None:
                    with self.kilit:
                        _ist.radar_ayarlar["son_sonuc"] = "gonderiliyor"
                        _ist.ayar_kuyruk.append(("yaz", a))

        elif komut == "rtk_konum_al":
            _rid = k.get("radar_id")
            if self._merkez_kipinde():
                # "Radar bagli mi" denetimi de SAHADA yapilir: bagli olup
                # olmadigini bilen taraf oradaki C20 istemcisidir.
                await self._radar_kopruye(websocket, "radar_rtk", {}, k)
            else:
                _ist = self._radar_istemci(_rid)
                radar_bagli = False
                if _ist is not None:
                    with self.kilit:
                        radar_bagli = _ist.durum["durum"] == "bagli"
                        if radar_bagli:
                            _ist.durum["rtk_durum"] = "aliniyor"
                            _ist.durum["rtk_ilerleme"] = 0
                            _ist.ayar_kuyruk.append(("rtk",))
                        else:
                            _ist.durum["rtk_durum"] = "hata"
                if not radar_bagli:
                    self.konsol("RADAR",
                                "RTK konumu alinamadi: radar bagli degil",
                                "hata")

        elif komut == "m50_baglan":
            # Açık operatör isteği olmadan hiçbir M50 bağlantısı kurulmaz.
            # Kimlik bilgileri yalnız bu kısa ömürlü istek sözlüğünde kalır;
            # durum, konsol veya pilot günlüğüne eklenmez.
            ip = str(k.get("ip") or "").strip()
            kullanici = str(k.get("kullanici") or "").strip()
            parola = str(k.get("parola") or "")
            try:
                port = int(k.get("port"))
            except (TypeError, ValueError):
                port = 0
            try:
                import ipaddress
                ipaddress.ip_address(ip)
                gecerli_ip = True
            except (ValueError, TypeError):
                gecerli_ip = False
            _yerel = self._eo_yerel(k)   # v2.4.192: eo_id'ye gore yerel servis
            if (not ip and not kullanici and not parola and _yerel is not None
                    and _yerel.kullanilabilir()):
                # v2.4.187: alanlar boş bırakıldı → kayıtlı kimlikle bağlan
                # (yerel mod kimliği bir kez girildikten sonra saklar).
                await self._m50_kopruye(websocket, "baglan_kayitli", {
                    "zaman_asimi": k.get("zaman_asimi", 5000)}, k)
            elif (not ip and not kullanici and not parola
                    and _yerel is not None):
                # v2.4.192 (Faz C): KÖPRÜ modunda da kayıtlı kimlik. Alanlar
                # boş bırakıldı ve bu makinede SDK yok (Linux Merkez): cihaz
                # kaydındaki kimlikle saha Köprüsüne 'baglan' gönderilir.
                # Parola Merkez belleğinde/durumda tutulmaz; yalnız bu
                # istekte Köprüye taşınır.
                _a = _yerel._ayar_oku()
                if _a.get("ip") and _a.get("kullanici") and _a.get("parola"):
                    try:
                        _p = int(_a.get("port") or 39020)
                    except (TypeError, ValueError):
                        _p = 39020
                    await self._m50_kopruye(websocket, "baglan", {
                        "ip": str(_a["ip"]), "port": _p,
                        "kullanici": str(_a["kullanici"]),
                        "parola": str(_a["parola"]),
                        "zaman_asimi": k.get("zaman_asimi", 5000),
                    }, k)
                else:
                    await self._uyari_gonder(
                        websocket, "M50",
                        "Kayıtlı M50 kimliği yok; IP, port, kullanıcı adı ve "
                        "parolayı bir kez girin.", "hata")
            elif not ip or not kullanici or not parola or not gecerli_ip:
                await self._uyari_gonder(
                    websocket, "M50", "M50 bağlantısı için geçerli IP, port, kullanıcı adı ve parola gereklidir.", "hata")
            elif not (0 < port < 65536):
                await self._uyari_gonder(websocket, "M50", "M50 portu geçersiz.", "hata")
            else:
                _sonuc = await self._m50_kopruye(websocket, "baglan", {
                    "ip": ip, "port": port, "kullanici": kullanici,
                    "parola": parola,
                    "zaman_asimi": k.get("zaman_asimi", 5000),
                }, k)
                # v2.4.192: Köprü yoluyla bağlantı kabul edildiyse kimlik
                # cihaz kaydına yazılır (yerel modda bunu yerel servis
                # kendisi yapar). Bir dahaki sefer alanlar boş bırakılır.
                if (_sonuc is not None and _yerel is not None
                        and not _yerel.kullanilabilir()):
                    try:
                        _yerel._ayar_yaz_ic({"ip": ip, "port": port,
                                             "kullanici": kullanici,
                                             "parola": parola})
                    except Exception:
                        pass
        elif komut == "m50_kes":
            await self._m50_kopruye(websocket, "kes", {}, k)
        elif komut == "m50_ayar_oku":
            await self._m50_kopruye(websocket, "ayar_oku", {}, k)
        elif komut == "m50_ayar_yaz":
            # SDK yolu ve RTSP kaynakları kalıcı ayara ancak Köprüde yazılır.
            # Şema bu üç açık anahtarla sınırlıdır; parola/oturum anahtarını
            # ayar olarak taşıyan çağrılar kesinlikle kabul edilmez.
            ayarlar = {a: k.get(a) for a in
                        ("m50_sdk_dizin", "rtsp_gorunur", "rtsp_termal")
                        if a in k}
            if not ayarlar:
                await self._uyari_gonder(websocket, "M50", "Kaydedilecek geçerli M50 ayarı yok.", "hata")
            else:
                await self._m50_kopruye(websocket, "ayar_yaz", ayarlar, k)
        elif komut == "m50_ptz":
            await self._m50_kopruye(websocket, "ptz", {
                "yon": k.get("yon"), "hiz": k.get("hiz"),
                "basili": bool(k.get("basili", True)),
            }, k)
        # ---- v2.4.210: VIDEO KAYDI (vekil akisindan dosyaya) ----
        elif komut in ("video_kayit_baslat", "video_kayit_durdur", "video_kayit_durum"):
            _vk = getattr(self, "video_kaydedici", None)
            if _vk is None:
                await self._uyari_gonder(websocket, "KAYIT", "Video kaydedici kullanilamiyor", "hata")
                return
            if komut == "video_kayit_baslat":
                _kam = self.kameralar.bul(k.get("kamera_id")) if self.kameralar else None
                if not _kam:
                    await self._uyari_gonder(websocket, "KAYIT", "Kamera bulunamadi", "hata")
                    return
                _s = await _db_is_parcasi(_vk.baslat, _kam["id"],
                                          str(k.get("etiket") or _kam.get("isim") or ""),
                                          _kam.get("fps") or 15)
                if not _s.get("tamam"):
                    await self._uyari_gonder(websocket, "KAYIT",
                                             "Kayit baslatilamadi: %s" % _s.get("hata", ""), "hata")
                else:
                    self._pilot_log(websocket, "kamera", "video_kayit_baslat",
                                    "kamera #%s" % _kam["id"])
            elif komut == "video_kayit_durdur":
                _s = await _db_is_parcasi(_vk.durdur, k.get("kamera_id"))
                if not _s.get("tamam"):
                    await self._uyari_gonder(websocket, "KAYIT",
                                             "Kayit durdurulamadi: %s" % _s.get("hata", ""), "uyari")
                else:
                    self._pilot_log(websocket, "kamera", "video_kayit_durdur",
                                    "kamera #%s" % k.get("kamera_id"))
            await self._duyur({"tip": "video_kayit_durum", "kayitlar": _vk.durumlar()})
        elif komut == "m50_lens":
            await self._m50_kopruye(websocket, "lens", {
                "eylem": k.get("eylem"), "kanal": k.get("kanal"),
                "basili": bool(k.get("basili", True)),
            }, k)
        elif komut == "m50_aci_konumla":
            await self._m50_kopruye(websocket, "aci_konumla", {
                "azimut": k.get("azimut"), "egim": k.get("egim"),
                "hiz": k.get("hiz"),
            }, k)
        elif komut == "m50_takip_sec":
            # Dikdörtgen seçimi sürücüde zorunludur. Merkez yalnız geçici
            # koordinatı iletir; vekil ve telemetri bunu saklamaz.
            await self._m50_kopruye(websocket, "takip_sec", {
                "kanal": k.get("kanal"),
                "video_dikdortgen": k.get("video_dikdortgen"),
                "secim": k.get("secim"),
            }, k)
        elif komut == "m50_takip_baslat":
            await self._m50_kopruye(websocket, "takip_baslat", {
                "kanal": k.get("kanal"), "mod": k.get("mod"),
            }, k)
        elif komut == "m50_takip_durdur":
            await self._m50_kopruye(websocket, "takip_durdur", {
                "kanal": k.get("kanal"),
            }, k)
        # --- v2.4.215: cihaz OSD'si (HVS_GetOsdInfo / HVS_SetOsdInfo) ---
        elif komut == "m50_osd_oku":
            await self._m50_kopruye(websocket, "osd_oku", {"kanal": k.get("kanal")}, k)
        elif komut == "m50_osd_yaz":
            _alan = k.get("alanlar")
            _s = await self._m50_kopruye(websocket, "osd_yaz", {
                "kanal": k.get("kanal"),
                "alanlar": _alan if isinstance(_alan, dict) else {},
            }, k)
            if _s is not None:
                self.konsol("M50", "Cihaz OSD ayarı yazıldı (kanal %s)" % k.get("kanal"), "basari")
        # --- v2.4.188: SDK'nın geri kalanı (açı, ön ayar, tarama, takip yeteneği) ---
        elif komut == "m50_aci_oku":
            await self._m50_kopruye(websocket, "aci_oku", {}, k)
        elif komut == "m50_onayar_liste":
            await self._m50_kopruye(websocket, "onayar_liste", {}, k)
        elif komut == "m50_onayar_kaydet":
            await self._m50_kopruye(websocket, "onayar_kaydet", {
                "no": k.get("no"), "ad": k.get("ad"), "hiz": k.get("hiz", 5)}, k)
        elif komut == "m50_onayar_cagir":
            await self._m50_kopruye(websocket, "onayar_cagir", {"no": k.get("no")}, k)
        elif komut == "m50_onayar_sil":
            await self._m50_kopruye(websocket, "onayar_sil", {"no": k.get("no")}, k)
        elif komut == "m50_onayar_hepsini_sil":
            await self._m50_kopruye(websocket, "onayar_hepsini_sil", {}, k)
        elif komut == "m50_tarama":
            await self._m50_kopruye(websocket, "tarama", {
                "tur": k.get("tur"), "kontrol": k.get("kontrol"),
                "yol": k.get("yol", 0)}, k)
        elif komut == "m50_takip_yetenek":
            await self._m50_kopruye(websocket, "takip_yetenek", {
                "kanal": k.get("kanal"), "etkin": bool(k.get("etkin", True))}, k)
        elif komut == "portlar":
            await websocket.send(json.dumps(
                {"tip": "portlar",
                 "portlar": self.dron.portlari_listele()}))

        elif komut == "angajman_baslat":
            # İnsan onaylı hedef-bazlı angajman. Görüntü kipinde istemcinin
            # kaynak bağlamı sunucu deposuyla yeniden doğrulanmadan motor
            # çağrılmaz; ``saldiran_sysid`` her durumda zorunludur.
            try:
                saldiran = int(k.get("saldiran_sysid", 0))
                hedef_tip = str(k.get("hedef_tip", "")).strip().lower()
                hedef_id = k.get("hedef_id")
                param = dict(self.angajman.param)
                param["gudum_hz"] = max(1.0, min(4.0, float(
                    k.get("gudum_hz", param.get("gudum_hz", 2)))))
                param["yakalama_mesafe"] = float(
                    k.get("yakalama_mesafe",
                          param.get("yakalama_mesafe", 2.0)))
                if "gorev_dikkate" in k:
                    param["gorev_dikkate"] = bool(k.get("gorev_dikkate"))
                if "ongoru" in k:
                    param["ongoru"] = bool(k.get("ongoru"))

                _baglam = None
                _gerekce = ""
                _basladi = False
                _beklenen_kip = ("goruntu" if hedef_tip == "goruntu"
                                  else "telemetri")
                _istenen_kip = str(k.get("angajman_kipi") or "").strip().lower()

                # İş 108 güvenlik kapısı: istemcideki onay penceresi tek başına
                # yeterli değildir. Her başlatma isteği açık insan onayı ve
                # hedef türüyle uyuşan ayrı kip bilgisini taşımak zorundadır.
                _angajman_pilot = self._pilot_bilgi(websocket) or {}
                if _angajman_pilot.get("rol") != "yonetici":
                    _gerekce = "Angajmanı yalnızca yönetici başlatabilir."
                elif k.get("operator_onayi") is not True:
                    _gerekce = "Açık operatör onayı olmadan angajman başlatılamaz."
                elif hedef_tip not in ("radar", "dron", "goruntu"):
                    _gerekce = "Angajman hedef türü geçersiz."
                elif _istenen_kip != _beklenen_kip:
                    _gerekce = "Angajman kipi hedef kaynağıyla uyuşmuyor."
                elif saldiran <= 0:
                    _gerekce = "İcra dronu geçersiz."
                elif saldiran in getattr(self.angajman, "_aktif", {}):
                    _gerekce = ("Bu dronda zaten etkin bir angajman var; "
                                 "önce mevcut angajmanı iptal edin.")

                # Her iki kip için de aynı taze telemetri ve firma sahipliği
                # kapısı geçerlidir. Görüntü kipinin ek kaynak/kalibrasyon
                # kontrolleri aşağıda ayrıca uygulanır.
                _icra = None
                _icra_uid = ""
                _firma_id = self._ws_firma_id(websocket)
                if not _gerekce:
                    with self.kilit:
                        _icra = dict(self.dron.dronlar.get(int(saldiran)) or {})
                    try:
                        _icra_son = float((_icra or {}).get("son_mesaj") or 0.0)
                    except (TypeError, ValueError):
                        _icra_son = 0.0
                    if not _icra:
                        _gerekce = "İcra dronu bağlı değil."
                    elif (_icra_son <= 0 or time.time() - _icra_son > 8.0):
                        _gerekce = "İcra dronu telemetrisi bayat."
                    else:
                        _icra_uid = str(
                            _icra.get("uid") or self._dron_uid(saldiran) or ""
                        ).strip()
                        if not _icra_uid:
                            _gerekce = "İcra dronunun kalıcı UID bilgisi yok."
                _izinli_dronlar = []
                if not _gerekce and _firma_id:
                    try:
                        from . import veritabani as _vt_angajman
                        _izinli_dronlar = (
                            _vt_angajman.dron_kaynaklari_listele(_firma_id) or [])
                    except BaseException:
                        _izinli_dronlar = []
                    if not any(
                            str(d.get("uid") or "").strip() == _icra_uid
                            for d in _izinli_dronlar if isinstance(d, dict)):
                        _gerekce = "İcra dronu bu firmaya ait değil."

                if not _gerekce and hedef_tip == "dron":
                    try:
                        _hedef_sysid = int(hedef_id)
                    except (TypeError, ValueError):
                        _hedef_sysid = 0
                    if _hedef_sysid <= 0 or _hedef_sysid == saldiran:
                        _gerekce = "Telemetri hedef dronu geçersiz."
                    else:
                        with self.kilit:
                            _hedef_dron = dict(
                                self.dron.dronlar.get(_hedef_sysid) or {})
                        try:
                            _hedef_son = float(
                                (_hedef_dron or {}).get("son_mesaj") or 0.0)
                        except (TypeError, ValueError):
                            _hedef_son = 0.0
                        if (not _hedef_dron or _hedef_son <= 0 or
                                time.time() - _hedef_son > 8.0):
                            _gerekce = "Hedef dron telemetrisi bayat veya bağlantı yok."
                        elif _firma_id:
                            _hedef_uid = str(
                                _hedef_dron.get("uid") or
                                self._dron_uid(_hedef_sysid) or ""
                            ).strip()
                            if not _hedef_uid or not any(
                                    str(d.get("uid") or "").strip() == _hedef_uid
                                    for d in _izinli_dronlar
                                    if isinstance(d, dict)):
                                _gerekce = "Hedef dron bu firmaya ait değil."

                if not _gerekce and hedef_tip == "radar":
                    try:
                        _radar_id = int(hedef_id)
                    except (TypeError, ValueError):
                        _radar_id = 0
                    if _radar_id <= 0:
                        _gerekce = "Telemetri radar hedefi geçersiz."

                if not _gerekce and hedef_tip == "goruntu":
                    _baglam, _gerekce = self._goruntu_angajman_dogrula(
                        websocket, k, saldiran, hedef_id)
                    if _baglam:
                        # Bu iç alan istemciden kabul edilmez; güdüm döngüsünün
                        # her hedef yenilemesini aynı firma kapsamında tutar.
                        param["_goruntu_firma_id"] = _baglam.get("firma_id")

                if not _gerekce:
                    _sonuc = self.angajman.baslat(
                        saldiran, hedef_tip, hedef_id, param)
                    if isinstance(_sonuc, tuple):
                        _basladi, _gerekce = _sonuc
                    else:
                        _basladi, _gerekce = True, ""

                _durum = {"saldiran_sysid": saldiran,
                          "hedef_tip": hedef_tip,
                          "angajman_kipi": _beklenen_kip,
                          "hedef_id": hedef_id,
                          "aktif": bool(_basladi),
                          "gerekce": str(_gerekce or "")}
                _olay = {"tip": "angajman", "durum": _durum}
                _firma = self._ws_firma_id(websocket)
                _olay_turu = ("GORUNTU_ANGAJMAN" if hedef_tip == "goruntu"
                              else "TELEMETRI_ANGAJMAN")
                self._pilot_log(
                    websocket, _olay_turu,
                    "baslat_onay" if _basladi else "baslat_ret",
                    {"hedef_id": str(hedef_id or "")[:200],
                     "hedef_tip": hedef_tip,
                     "angajman_kipi": _beklenen_kip,
                     "saldiran_sysid": saldiran,
                     "gerekce": str(_gerekce or "")[:300]})
                self.konsol(
                    "ANGAJMAN",
                    "%s angajmani %s: hedef=%s icra=D%s%s" % (
                        "Goruntu" if hedef_tip == "goruntu" else "Telemetri",
                        "ONAY" if _basladi else "RET", hedef_id, saldiran,
                        (" gerekce=" + str(_gerekce)) if _gerekce else ""),
                    "basari" if _basladi else "uyari")
                if _firma is not None:
                    await self._firmaya_gonder(_firma, _olay)
                else:
                    await self._duyur(_olay)
            except (TypeError, ValueError) as e:
                _gerekce = "Başlatma isteği geçersiz: %s" % e
                self.konsol("ANGAJMAN", _gerekce, "hata")
                await websocket.send(json.dumps({
                    "tip": "angajman", "durum": {
                        "saldiran_sysid": 0, "hedef_tip": str(k.get("hedef_tip") or ""),
                        "hedef_id": k.get("hedef_id"), "aktif": False,
                        "gerekce": _gerekce}}, ensure_ascii=False))

        elif komut == "yerel_angajman_baslat":
            # ----------------------------------------------------------
            # v2.5.21: YEREL AI HEDEFINE ANGAJMAN
            # ----------------------------------------------------------
            # Goruntu Koprusu (BRDIMG) yerine YEREL kalibreli kameranin
            # AI takibinden dogan hedefe angajman. Kopruye ozgu tam-ekran
            # secim echo'suna (`_goruntu_angajman_dogrula`) baglanmaz;
            # ayni angajman MOTORUNU (`self.angajman.baslat`) cagirir.
            #
            # Guvenlik kapilari (hepsi burada, motora girmeden ONCE):
            #   1. Rol: yalniz yonetici.
            #   2. Acik operator onayi (`operator_onayi is True`).
            #   3. hedef_id yerel sentetik ornek_id tasimali
            #      (yerel_hedef.YEREL_ORNEK_TABAN); kopru hedefi taklit
            #      edilemez.
            #   4. Hedef depoda COZULMUS ve `konum_guvenilir` olmali
            #      (kalibrasyon + taze veri). Aksi halde ret.
            #   5. Icra dronu bagli ve telemetrisi taze (<8 sn).
            #   6. Kamera tipi 'dron' ise: icra dronu, kameranin uzerinde
            #      oldugu dronla AYNI olmali (hareketli kamera hedefi ancak
            #      kendi platformunun guduMu icin gecerlidir).
            _ygerekce = ""
            _ybasladi = False
            _yhedef_id = str(k.get("hedef_id") or "")
            try:
                _ysaldiran = int(k.get("saldiran_sysid", 0))
            except (TypeError, ValueError):
                _ysaldiran = 0
            _ypilot = self._pilot_bilgi(websocket) or {}
            _yfirma = self._ws_firma_id(websocket)

            from .yerel_hedef import YEREL_ORNEK_TABAN as _YOT
            _yoid = _ykam = _yiz = 0
            try:
                _yp = _yhedef_id.split(":")
                if len(_yp) == 3:
                    _yoid, _ykam, _yiz = int(_yp[0]), int(_yp[1]), int(_yp[2])
            except (TypeError, ValueError):
                _yoid = 0

            if _ypilot.get("rol") != "yonetici":
                _ygerekce = "Angajmani yalnizca yonetici baslatabilir."
            elif k.get("operator_onayi") is not True:
                _ygerekce = "Acik operator onayi olmadan angajman baslatilamaz."
            elif _yoid < _YOT:
                _ygerekce = "Gecersiz yerel hedef kimligi."
            elif _ysaldiran <= 0:
                _ygerekce = "Icra dronu gecersiz."
            elif _ysaldiran in getattr(self.angajman, "_aktif", {}):
                _ygerekce = ("Bu dronda zaten etkin angajman var; once "
                             "iptal edin.")

            _ycozulen = None
            if not _ygerekce:
                try:
                    from . import hedef_deposu as _hd_yerel
                    # v2.4.164: yerel hedefler firma_id=None ile yazilir.
                    _ycozulen = _hd_yerel.DEPO.hedef_bul(
                        _yoid, _ykam, _yiz, firma_id=None)
                except Exception:
                    _ycozulen = None
                if not _ycozulen:
                    _ygerekce = "Yerel hedef bulunamadi, bayat veya kayip."
                elif not _ycozulen.get("konum_guvenilir"):
                    _ygerekce = (str(_ycozulen.get("konum_gerekce") or
                                     "Hedef konumu guvenilir degil."))

            _yicra_uid = ""
            if not _ygerekce:
                with self.kilit:
                    _yicra = dict(self.dron.dronlar.get(_ysaldiran) or {})
                try:
                    _yicra_son = float((_yicra or {}).get("son_mesaj") or 0.0)
                except (TypeError, ValueError):
                    _yicra_son = 0.0
                if not _yicra:
                    _ygerekce = "Icra dronu bagli degil."
                elif _yicra_son <= 0 or time.time() - _yicra_son > 8.0:
                    _ygerekce = "Icra dronu telemetrisi bayat."
                else:
                    _yicra_uid = str(_yicra.get("uid") or
                                     self._dron_uid(_ysaldiran) or "").strip()

            # Kamera tipi 'dron' ise same-drone kurali.
            if not _ygerekce and str(_ycozulen.get("poz_kaynak") or
                                     "").lower() == "dron":
                _ykaynak_uid = ""
                try:
                    _ykam_kayit = self.kameralar.bul(_ykam) if self.kameralar \
                        else None
                    _ykaynak_uid = str((_ykam_kayit or {}).get("dron_uid")
                                       or "").strip()
                except Exception:
                    _ykaynak_uid = ""
                # v2.4.164: Kullanici istegi — dron kamerasinin telemetrisiyle
                # hedef konumu tahmin edilir, icra icin HERHANGI bir bagli dron
                # secilebilir. Eskiden icra dronu kameranin dronuyla ayni
                # olmak zorundaydi. Farkliysa yalniz bilgi amacli kaydedilir.
                if _yicra_uid and _ykaynak_uid and _yicra_uid != _ykaynak_uid:
                    self.konsol("ANGAJMAN",
                                f"Goruntu hedefi {_ykaynak_uid} kamerasindan "
                                f"cozuluyor; icra dronu D{_ysaldiran}", "bilgi")

            if not _ygerekce:
                _yparam = dict(self.angajman.param)
                try:
                    _yparam["gudum_hz"] = max(1.0, min(4.0, float(
                        k.get("gudum_hz", _yparam.get("gudum_hz", 2)))))
                except (TypeError, ValueError):
                    pass
                # v2.4.164: panelden gelen angajman ayarlari
                for _yk, _ytur in (("yakalama_mesafe", float),
                                   ("ongoru", bool), ("gorev_dikkate", bool),
                                   ("goruntu_asgari_irtifa", float),
                                   ("takip_mesafe", float)):
                    if _yk in k:
                        try:
                            _yparam[_yk] = _ytur(k.get(_yk))
                        except (TypeError, ValueError):
                            pass
                # v2.4.173: "takip" kipi — hedefe carpmadan, secilen
                # mesafeyi koruyarak izler (golge ucusu).
                if str(k.get("mod") or "").lower() == "takip":
                    _yparam["mod"] = "takip"
                _ysonuc = self.angajman.baslat(
                    _ysaldiran, "goruntu", _yhedef_id, _yparam)
                if isinstance(_ysonuc, tuple):
                    _ybasladi, _ygerekce = _ysonuc
                else:
                    _ybasladi = bool(_ysonuc)

            self._pilot_log(
                websocket, "GORUNTU_ANGAJMAN",
                "yerel_baslat_onay" if _ybasladi else "yerel_baslat_ret",
                {"hedef_id": _yhedef_id[:200], "kamera": _ykam,
                 "saldiran_sysid": _ysaldiran,
                 "gerekce": str(_ygerekce or "")[:300]})
            self.konsol(
                "ANGAJMAN",
                "Yerel angajman %s: hedef=%s icra=D%s%s" % (
                    "ONAY" if _ybasladi else "RET", _yhedef_id, _ysaldiran,
                    (" gerekce=" + str(_ygerekce)) if _ygerekce else ""),
                "basari" if _ybasladi else "uyari")
            _yolay = {"tip": "angajman", "durum": {
                "saldiran_sysid": _ysaldiran, "hedef_tip": "goruntu",
                "angajman_kipi": "goruntu", "hedef_id": _yhedef_id,
                "aktif": bool(_ybasladi), "gerekce": str(_ygerekce or "")}}
            if _yfirma is not None:
                await self._firmaya_gonder(_yfirma, _yolay)
            else:
                await self._duyur(_yolay)

        elif komut == "angajman_iptal":
            saldiran = int(k.get("saldiran_sysid", 0))
            self.angajman.durdur(saldiran)
            _iptal_olayi = {"tip": "angajman", "durum": {
                "saldiran_sysid": saldiran, "aktif": False}}
            self._pilot_log(websocket, "ANGAJMAN", "iptal_onay",
                            {"saldiran_sysid": saldiran})
            _firma = self._ws_firma_id(websocket)
            if _firma is not None:
                await self._firmaya_gonder(_firma, _iptal_olayi)
            else:
                await self._duyur(_iptal_olayi)

        elif komut == "angajman_ayar":
            # v2.4.43: kesisme ongoru ayarlarini KALICI kaydet.
            # Devam eden angajmanlar etkilenmez (baslat() param'i kopyalar);
            # yalniz bundan sonraki angajmanlar bu ayarla baslar.
            try:
                p = self.angajman.param
                if "gudum_hz" in k:
                    p["gudum_hz"] = max(1, min(4, int(float(k["gudum_hz"]))))
                if "yakalama_mesafe" in k:
                    p["yakalama_mesafe"] = max(0.5, min(100.0,
                                                        float(k["yakalama_mesafe"])))
                if "takip_mesafe" in k:
                    p["takip_mesafe"] = max(5.0, min(500.0,
                                                     float(k["takip_mesafe"])))
                if "ongoru" in k:
                    p["ongoru"] = bool(k["ongoru"])
                if "gorev_dikkate" in k:
                    p["gorev_dikkate"] = bool(k["gorev_dikkate"])
                self.angajman_ayar_kaydet()
                await websocket.send(json.dumps({
                    "tip": "angajman_ayar_sonuc", "basari": True,
                    "ayar": {
                        "gudum_hz": p.get("gudum_hz"),
                        "yakalama_mesafe": p.get("yakalama_mesafe"),
                        "ongoru": bool(p.get("ongoru", True)),
                        "gorev_dikkate": bool(p.get("gorev_dikkate", True)),
                    }}))
            except (TypeError, ValueError) as e:
                self.konsol("ANGAJMAN", f"Ayar kaydedilemedi: {e}", "hata")
                await websocket.send(json.dumps({
                    "tip": "angajman_ayar_sonuc", "basari": False,
                    "mesaj": str(e)}))

        elif komut == "takip_baslat":
            # {"tip":"takip_baslat","takipci_sysid":2,"hedef_sysid":1,
            #  "irtifa_fark":-10,"mesafe":20}
            if self.dron_takip:
                try:
                    self.dron_takip.baslat(
                        int(k.get("takipci_sysid", 0)),
                        int(k.get("hedef_sysid", 0)),
                        float(k.get("irtifa_fark", 0)),
                        float(k.get("mesafe", 0)))
                except (TypeError, ValueError) as e:
                    self.konsol("TAKIP", f"Baslat hatasi: {e}", "hata")
                await self._duyur({"tip": "dron_takip",
                                   "takipler": self.dron_takip.durum()})

        elif komut == "takip_iptal":
            # {"tip":"takip_iptal","sysid":1}  (takipci VEYA hedef sysid)
            if self.dron_takip:
                try:
                    self.dron_takip.durdur(int(k.get("sysid", 0)))
                except (TypeError, ValueError):
                    pass
                await self._duyur({"tip": "dron_takip",
                                   "takipler": self.dron_takip.durum()})

        # ---- v2.4.3: Sürü uçuş komutları ----
        elif komut == "suru_kur":
            # {"tip":"suru_kur","master_sysid":1,
            #  "slaves":[{"sysid":2,"x":5,"y":10,"z":0}]}
            if self.suru:
                try:
                    ok = self.suru.kur(
                        int(k.get("master_sysid", 0)),
                        k.get("slaves", []))
                    await self._duyur({"tip": "suru_durum",
                                       "suru": self.suru.durum()})
                except (TypeError, ValueError) as e:
                    self.konsol("SÜRÜ", f"Kur hatası: {e}", "hata")
        elif komut == "suru_dagit":
            if self.suru:
                self.suru.dagit()
                await self._duyur({"tip": "suru_durum", "suru": None})
        elif komut == "suru_cikar":
            # {"tip":"suru_cikar","sysid":2}
            if self.suru:
                self.suru.cikar(int(k.get("sysid", 0)))
                await self._duyur({"tip": "suru_durum",
                                   "suru": self.suru.durum()})

        elif komut == "dron_komut":
            # {"tip":"dron_komut","sysid":1,"aksiyon":"takeoff","irtifa":15}
            # goto: {...,"aksiyon":"goto","lat":39.9,"lon":32.8}
            sysid = int(k.get("sysid", 0))
            aksiyon = str(k.get("aksiyon", ""))
            irtifa = k.get("irtifa")
            if sysid and aksiyon:
                # v2.1.8: DJI dronlari (sanal sysid >= 1000) kopruden yonetilir
                if self.dji_kopru and self.dji_kopru.dji_mi(sysid):
                    if aksiyon == "goto":
                        self.dji_kopru.goto_gonder(sysid, k.get("lat"),
                                                   k.get("lon"))
                    elif aksiyon == "param":
                        self.dji_kopru.param_yaz(sysid, k.get("ad"),
                                                 k.get("deger"))
                    elif aksiyon == "set_home":
                        # v2.4.42: DJI koprusunde DO_SET_HOME karsiligi
                        # YOKTUR (DJI SDK HOME'u kendi kalkis noktasindan
                        # belirler). Komutu genel `komut()` yoluna
                        # dusurmek onu SESSIZCE yutar; operator HOME'un
                        # ayarlandigini sanar. Bu yuzden acik hata
                        # bildirilir.
                        await websocket.send(json.dumps({
                            "tip": "set_home_sonuc", "sysid": sysid,
                            "basari": False,
                            "sebep": "DJI araçlarında HOME noktası "
                                     "GCS'den ayarlanamaz"}))
                    else:
                        self.dji_kopru.komut(sysid, aksiyon, irtifa)
                elif aksiyon == "param":
                    # {"aksiyon":"param","ad":"hareket_hizi","deger":5}
                    # v2.4.38: Bu dal ARTIK 'self.dron.master' kapisinin
                    # ARKASINDA DEGIL. master property'si yalnizca durumu
                    # "bagli" olan bir baglanti varsa dolu doner; link
                    # yeniden kurulurken ("baglaniyor") bosalir ve komut
                    # hic gonderilmezdi. param_ayarla kendi icinde
                    # master_bul(sysid) kullaniyor - Parametreler
                    # ekraninin (param_yaz) yoluyla ayni davranis.
                    basari, p_ad, ham = self.dron.param_ayarla(
                        sysid, k.get("ad"), k.get("deger"))
                    # v2.4.21: kisayol parametresi de kalici tabloya ve
                    # degisiklik gecmisine yazilir
                    # v2.4.38: YALNIZ BASARILI yazmada kaydedilir
                    # (eskiden kosulsuz cagriliyordu: yazma basarisiz
                    # olsa bile "yazildi" kaydi dusuyordu).
                    # NOT: UI anahtari ("hareket_hizi") gonderilir;
                    # _param_kalici_kaydet zaten PARAM_HARITASI ile
                    # gercek ada ve ham degere cevirir. p_ad/ham
                    # gondermek CIFTE donusume yol acardi
                    # (WPNAV_SPEED harita disi oldugu icin ham deger
                    # oldugu gibi yazilirdi - bu dogru olsa da UI
                    # anahtari yolu tek dogruluk kaynagini korur).
                    if basari:
                        self._param_kalici_kaydet(
                            websocket, sysid, k.get("ad"),
                            k.get("deger"))
                    # v2.4.38: arayuze sonuc bildir - kullanici artik
                    # sessiz basarisizlik yerine onay/hata goruyor
                    await websocket.send(json.dumps({
                        "tip": "param_yazildi", "sysid": sysid,
                        "ad": p_ad or str(k.get("ad") or ""),
                        "ui_ad": str(k.get("ad") or ""),
                        "deger": ham if basari else k.get("deger"),
                        "basari": bool(basari)}))
                elif aksiyon == "set_home":
                    # v2.4.42: HOME ayarlama. `param` dali gibi bu da
                    # `self.dron.master` kapisinin ARKASINDA DEGILDIR:
                    # master property'si yalnizca durumu "bagli" olan bir
                    # baglanti varsa dolu doner ve link yeniden kurulurken
                    # bosalir; set_home_gonder kendi icinde
                    # master_bul(sysid) kullanir ve baglanti yoksa bunu
                    # ACIK sebeple bildirir.
                    #
                    # lat/lon YOKSA aracin mevcut konumu HOME olur
                    # (Islemler menusu); VARSA belirtilen konum kullanilir
                    # (haritada SHIFT + tik). Iki kip ayni MAVLink
                    # komutunun param1 degeriyle secilir.
                    _lat = k.get("lat")
                    _lon = k.get("lon")
                    basari, sebep = self.dron.set_home_gonder(
                        sysid,
                        _lat if _lat is not None else None,
                        _lon if _lon is not None else None)
                    await websocket.send(json.dumps({
                        "tip": "set_home_sonuc", "sysid": sysid,
                        "basari": bool(basari), "sebep": sebep,
                        "mevcut_konum": _lat is None or _lon is None}))
                elif self.dron.master:
                    if aksiyon == "goto":
                        self.dron.goto_gonder(sysid, k.get("lat"),
                                              k.get("lon"))
                    else:
                        self.dron.komut_gonder(sysid, aksiyon, irtifa)
                        # v2.4.3: master takeoff -> slave'lere senkron takeoff
                        if (aksiyon == "takeoff" and self.suru
                                and self.suru.durum()
                                and self.suru.durum().get(
                                    "master_sysid") == sysid):
                            self.suru.master_takeoff(irtifa)
                else:
                    self.konsol("KOMUT",
                                f"sysid={sysid} {aksiyon} gonderilemedi: "
                                "seri baglanti yok", "hata")

        elif komut == "dron_renk_kaydet":
            # v2.4.202: {"tip":"dron_renk_kaydet","sysid":7,"renk":"#ff8800"}
            sysid = int(k.get("sysid", 0))
            renk = str(k.get("renk", "")).strip()
            if sysid and renk:
                if self.dron.dron_renk_kaydet(sysid, renk):
                    self.konsol("DRON", "Dron %s rengi %s olarak kaydedildi" % (sysid, renk), "basari")
                else:
                    await self._uyari_gonder(websocket, "DRON",
                        "Renk kaydedilemedi: dron kaydi henuz yok (UID alinmadi) ya da renk gecersiz.", "hata")
        elif komut == "dron_isim_kaydet":
            # {"tip":"dron_isim_kaydet","sysid":7,"isim":"Kartal-1"}
            sysid = int(k.get("sysid", 0))
            isim = str(k.get("isim", "")).strip()
            if sysid and isim:
                self.dron.dron_isim_kaydet(sysid, isim)
                # Guncel dron listesini hemen yayinla
                await self._duyur({"tip": "dron_isim_guncellendi",
                                   "sysid": sysid, "isim": isim})

        elif komut == "kalkis_kontrol":
            # v2.4.41: Kalkis oncesi kontrol listesi kaydi + takeoff.
            #   {"tip":"kalkis_kontrol","sysid":7,"irtifa":15,
            #    "maddeler":[{"anahtar":..,"soru":..,"cevap":true,..}]}
            #
            # TASARIM: kayit ve takeoff AYNI islemde yapilir. Kayit
            # yazilamazsa takeoff GONDERILMEZ; boylece "kaydi olmayan
            # kalkis" durumu olusamaz. Istemci tarih/saat ve pilot
            # kimligi GONDERMEZ, ikisi de burada damgalanir.
            sysid = int(k.get("sysid", 0))
            maddeler = k.get("maddeler") or []
            try:
                irtifa = float(k.get("irtifa") or 0)
            except (TypeError, ValueError):
                irtifa = 0.0
            hata = ""
            kontrol_id = None
            if not sysid or not maddeler:
                hata = "Eksik istek (sysid veya madde listesi yok)"
            else:
                # Sunucu tarafi dogrulama: TUM zorunlu maddeler EVET
                # olmali. Istemcideki pasif dugme yeterli guvence degil
                # (elle WS mesaji gonderilebilir).
                zorunlu = [m for m in maddeler
                           if m.get("zorunlu", True)]
                eksik = [m for m in zorunlu if m.get("cevap") is not True]
                if not zorunlu:
                    hata = "Kontrol listesi bos"
                elif eksik:
                    hata = (f"{len(eksik)} zorunlu madde onaylanmadi; "
                            "kalkis reddedildi")
            if not hata:
                p = self._pilot_bilgi(websocket) or {}
                d = {}
                try:
                    d = self.dron.dronlar.get(sysid) or {}
                except (AttributeError, TypeError):
                    d = {}
                try:
                    from . import veritabani as _vt
                    dron_id = _vt.dron_id_bul(
                        sysid=sysid, uid=self._dron_uid(sysid))
                    oturum_id = _vt.acik_oturum_bul(
                        sysid=sysid, dron_id=dron_id)
                    kontrol_id = _vt.kalkis_kontrol_kaydet(
                        sysid, maddeler, dron_id=dron_id,
                        oturum_id=oturum_id,
                        pilot_eposta=p.get("eposta", ""),
                        pilot_isim=p.get("ad_soyad", ""),
                        arac_tipi=int(d.get("arac_tipi") or 0),
                        arac_tipi_ad=str(d.get("tip") or ""),
                        hedef_irtifa=irtifa)
                except Exception as e:
                    hata = f"Kalkis kaydi yazilamadi: {e}"
                    self.konsol("KALKIS", hata, "hata")
            if not hata:
                # Kayit yazildi -> takeoff komutu gonderilir
                gonderildi = False
                gonder_hata = ""
                try:
                    if self.dji_kopru and self.dji_kopru.dji_mi(sysid):
                        self.dji_kopru.komut(sysid, "takeoff", irtifa)
                        gonderildi = True
                    elif self.dron.master:
                        self.dron.komut_gonder(sysid, "takeoff", irtifa)
                        gonderildi = True
                        if (self.suru and self.suru.durum()
                                and self.suru.durum().get(
                                    "master_sysid") == sysid):
                            self.suru.master_takeoff(irtifa)
                    else:
                        gonder_hata = ("Telemetri baglantisi yok; "
                                       "kalkis komutu gonderilemedi")
                except Exception as e:
                    gonder_hata = f"Kalkis komutu hatasi: {e}"
                try:
                    from . import veritabani as _vt
                    _vt.kalkis_kontrol_takeoff_isaretle(
                        kontrol_id, gonderildi, gonder_hata)
                except Exception as e:
                    self.konsol("KALKIS",
                                f"takeoff isareti yazilamadi: {e}",
                                "uyari")
                if gonderildi:
                    self._pilot_log(
                        websocket, "ucus", "kalkis_kontrol",
                        {"sysid": sysid, "kontrol_id": kontrol_id,
                         "irtifa": irtifa,
                         "madde": len(maddeler)})
                    self.konsol(
                        "KALKIS",
                        f"sysid={sysid} kontrol listesi onaylandi "
                        f"(kayit #{kontrol_id}), takeoff {irtifa:.0f} m")
                else:
                    hata = gonder_hata or "Kalkis komutu gonderilemedi"
            await websocket.send(json.dumps({
                "tip": "kalkis_kontrol_sonuc", "sysid": sysid,
                "basari": not hata, "hata": hata,
                "kontrol_id": kontrol_id}))

        elif komut == "arm_check":
            # v2.4.19: {"tip":"arm_check","sysid":7}
            # Dronun uctan uca kalkis hazirlik raporu (sensor sagligi,
            # EKF, GPS, batarya, titresim, prearm) + son STATUSTEXT'ler.
            sysid = int(k.get("sysid", 0))
            if sysid:
                rapor = self.dron.arm_check_raporu(sysid)
                # ARM ile ilgili kritik parametreler (varsa onbellekten)
                rapor["parametreler"] = self._arm_check_parametreleri(sysid)
                await websocket.send(json.dumps({
                    "tip": "arm_check_rapor", **rapor}))

        elif komut == "motor_test":
            # v2.5.0: {"tip":"motor_test","sysid":7,"motor":1,"tip_no":0,
            #          "deger":5,"sure":2,"adet":0,"sira":0}
            # DIKKAT: govdedeki test tipi alani "tip_no"; "tip" alani
            # WS mesaj tipi icin ayrilmistir.
            sysid = int(k.get("sysid", 0))
            if not sysid:
                pass
            elif self.dji_kopru and self.dji_kopru.dji_mi(sysid):
                # DJI SDK motor testi sunmaz. Sessizce yutmak operatore
                # testin yapildigi izlenimini verirdi.
                await websocket.send(json.dumps({
                    "tip": "motor_test_sonuc", "sysid": sysid,
                    "basari": False,
                    "sebep": "DJI araclarinda motor testi yapilamaz"}))
            else:
                basari, sebep = self.dron.motor_test_gonder(
                    sysid,
                    k.get("motor", 1), k.get("tip_no", 0),
                    k.get("deger", 5), k.get("sure", 2),
                    k.get("adet", 0), k.get("sira", 0))
                await websocket.send(json.dumps({
                    "tip": "motor_test_sonuc", "sysid": sysid,
                    "basari": bool(basari), "sebep": sebep}))
        elif komut == "motor_test_dur":
            # v2.5.0: {"tip":"motor_test_dur","sysid":7}
            sysid = int(k.get("sysid", 0))
            if sysid and not (self.dji_kopru
                              and self.dji_kopru.dji_mi(sysid)):
                basari, sebep = self.dron.motor_test_durdur(sysid)
                await websocket.send(json.dumps({
                    "tip": "motor_test_sonuc", "sysid": sysid,
                    "basari": bool(basari), "sebep": sebep,
                    "durduruldu": True}))
        elif komut == "ivme_yon_onay":
            # v2.5.0: {"tip":"ivme_yon_onay","sysid":7,"yon_kod":1}
            # Alti yonlu ivme kalibrasyonunda her yon yerlestirildikten
            # sonra araca onay gonderir. Ayri uc kullanilmasinin
            # gerekcesi: komut_gonder imzasi yon kodu tasiyamiyor ve
            # dokuz cagri yeri var (imza korunuyor).
            sysid = int(k.get("sysid", 0))
            if not sysid:
                pass
            elif self.dji_kopru and self.dji_kopru.dji_mi(sysid):
                await websocket.send(json.dumps({
                    "tip": "ivme_yon_onay_sonuc", "sysid": sysid,
                    "basari": False,
                    "sebep": "DJI araclarinda ivme kalibrasyonu "
                             "yapilamaz"}))
            else:
                basari, sebep = self.dron.ivme_yon_onay(
                    sysid, k.get("yon_kod", 1))
                await websocket.send(json.dumps({
                    "tip": "ivme_yon_onay_sonuc", "sysid": sysid,
                    "yon_kod": k.get("yon_kod", 1),
                    "basari": bool(basari), "sebep": sebep}))
        elif komut == "kalib_mesajlari":
            # v2.5.0: {"tip":"kalib_mesajlari","sysid":7}
            # Kalibrasyon penceresi acikken duzenli cagrilir; oturum
            # baslangicindan sonraki STATUSTEXT satirlarini dondurur.
            sysid = int(k.get("sysid", 0))
            if sysid:
                await websocket.send(json.dumps({
                    "tip": "kalib_mesaj_listesi", "sysid": sysid,
                    **self.dron.kalib_mesajlari(sysid)}))
        elif komut == "ilk_ayar_ongoru":
            # v2.5.0: {"tip":"ilk_ayar_ongoru","sysid":7,
            #          "cap_inc":10,"hucre":4}
            # YAZMA YAPMAZ: yalniz hesaplar ve dondurur.
            sysid = int(k.get("sysid", 0))
            ongoru = self.dron.ilk_ayar_ongoru(
                k.get("cap_inc"), k.get("hucre", 4))
            if ongoru is None:
                await websocket.send(json.dumps({
                    "tip": "ilk_ayar_ongorusu", "sysid": sysid,
                    "basari": False,
                    "sebep": "Pervane capi 3-60 inc, hucre sayisi "
                             "2-14 araliginda olmali"}))
            else:
                await websocket.send(json.dumps({
                    "tip": "ilk_ayar_ongorusu", "sysid": sysid,
                    "basari": True, **ongoru}))
        elif komut == "ilk_ayar_uygula":
            # v2.5.0: {"tip":"ilk_ayar_uygula","sysid":7,
            #          "parametreler":{...}}
            sysid = int(k.get("sysid", 0))
            if not sysid:
                pass
            elif self.dji_kopru and self.dji_kopru.dji_mi(sysid):
                await websocket.send(json.dumps({
                    "tip": "ilk_ayar_sonuc", "sysid": sysid,
                    "yazilan": 0,
                    "hatalar": ["DJI araclarinda PID ayari "
                                "yapilamaz"]}))
            else:
                import asyncio as _aio
                loop = _aio.get_event_loop()
                yazilan, hatalar = await loop.run_in_executor(None, _db_iade_ederek, self.dron.ilk_ayar_uygula, sysid,
                    k.get("parametreler"))
                # Kalici parametre tablosuna da yazilir (kim, ne zaman,
                # eski -> yeni). param_yaz dalinin sozlesmesiyle ayni.
                if yazilan:
                    for _ad, _dg in (k.get("parametreler") or {}).items():
                        _ad = str(_ad).strip().upper()
                        if _ad in self.dron.ILK_AYAR_ALANLAR:
                            try:
                                self._param_kalici_kaydet(
                                    websocket, sysid, _ad, _dg)
                            except Exception:
                                pass
                await websocket.send(json.dumps({
                    "tip": "ilk_ayar_sonuc", "sysid": sysid,
                    "yazilan": int(yazilan), "hatalar": hatalar}))
        elif komut == "voltaj_kalibrasyon":
            # Multimetre ile olculen gercek voltajdan BATT_VOLT_MULT
            # hesaplanir. Parametre okuma bloklayabildiginden WS dongusunde
            # degil, is parcaciginda calisir.
            sysid = int(k.get("sysid", 0))
            if not sysid:
                sonuc = {"basari": False, "sebep": "Gecerli dron secin."}
            elif self.dji_kopru and self.dji_kopru.dji_mi(sysid):
                sonuc = {"basari": False,
                         "sebep": "DJI araclarinda ArduPilot batarya parametresi yok."}
            else:
                import asyncio as _aio
                loop = _aio.get_event_loop()
                try:
                    sonuc = await loop.run_in_executor(None, _db_iade_ederek, self.dron.batarya_voltaj_kalibre_et,
                        sysid, k.get("gercek_voltaj"))
                except Exception as e:
                    self.konsol("PARAM", f"Voltaj kalibrasyonu hatasi: {e}", "hata")
                    sonuc = {"basari": False, "sebep": str(e)}
            if sonuc.get("basari"):
                try:
                    self._param_kalici_kaydet(
                        websocket, sysid, "BATT_VOLT_MULT", sonuc["yeni_carpan"])
                except Exception:
                    pass
            await websocket.send(json.dumps({
                "tip": "voltaj_kalibrasyon_sonuc", "sysid": sysid, **sonuc}))
        elif komut == "dron_mesajlari":
            # v2.4.19: {"tip":"dron_mesajlari","sysid":7,"adet":120}
            sysid = int(k.get("sysid", 0))
            if sysid:
                await websocket.send(json.dumps({
                    "tip": "dron_mesaj_listesi", "sysid": sysid,
                    "mesajlar": self.dron.mesaj_listesi(
                        sysid, int(k.get("adet", 120)))}))

        elif komut == "dron_mesaj_temizle":
            # v2.4.19: {"tip":"dron_mesaj_temizle","sysid":7}
            sysid = int(k.get("sysid", 0))
            if sysid:
                self.dron.mesajlari_temizle(sysid)
                await websocket.send(json.dumps({
                    "tip": "dron_mesaj_listesi", "sysid": sysid,
                    "mesajlar": []}))

        elif komut == "dron_konsol_gecmis":
            # v2.4.45: {"tip":"dron_konsol_gecmis","sysid":7,"adet":200}
            # Dronun panelinin altindaki acilir kapanir haberlesme
            # konsolunun gecmisi. Tampon panel kapaliyken de doldugu icin
            # kullanici konsolu ilk actiginda gecmis hazir gelir.
            sysid = int(k.get("sysid", 0))
            if sysid:
                await websocket.send(json.dumps({
                    "tip": "dron_konsol_gecmis", "sysid": sysid,
                    "satirlar": self.dron.konsol_gecmis(
                        sysid, int(k.get("adet", 0)) or None)}))

        elif komut == "dron_konsol_temizle":
            # v2.4.45: {"tip":"dron_konsol_temizle","sysid":7}
            sysid = int(k.get("sysid", 0))
            if sysid:
                self.dron.konsol_temizle(sysid)
                await websocket.send(json.dumps({
                    "tip": "dron_konsol_gecmis", "sysid": sysid,
                    "satirlar": []}))

        elif komut == "kamera_konsol_gecmis":
            # v2.4.189: {"tip":"kamera_konsol_gecmis","id":3,"adet":200}
            kk = getattr(self, "kamera_konsol", None)
            kid = int(k.get("id", 0) or 0)
            if kk is not None and kid:
                await websocket.send(json.dumps({
                    "tip": "kamera_konsol_gecmis", "id": kid,
                    "satirlar": kk.gecmis(kid, int(k.get("adet", 0)) or None)}))

        elif komut == "kamera_konsol_temizle":
            kk = getattr(self, "kamera_konsol", None)
            kid = int(k.get("id", 0) or 0)
            if kk is not None and kid:
                kk.temizle(kid)
                await websocket.send(json.dumps({
                    "tip": "kamera_konsol_gecmis", "id": kid, "satirlar": []}))

        elif komut == "rota_ucus_param":
            # v2.4.21: harita rota cizimi icin sabit kanat donus
            # parametreleri. Once kalici parametre tablosu okunur
            # (drona istek yok); eksikse tek tek PARAM_REQUEST_READ.
            #   {"tip":"rota_ucus_param","sysid":7}
            sysid = int(k.get("sysid", 0))
            if sysid:
                istenen = [
                    "ROLL_LIMIT_DEG", "LIM_ROLL_CD",
                    "AIRSPEED_CRUISE", "TRIM_ARSPD_CM",
                    "WP_LOITER_RAD", "WP_RADIUS",
                    "NAVL1_PERIOD", "NAVL1_DAMPING",
                    "WPNAV_SPEED", "WPNAV_RADIUS",
                ]
                bulunan = {}
                try:
                    from . import veritabani as _vt
                    onbellek, _tp, _ts = _vt.param_cache_oku(
                        sysid, uid=self._dron_uid(sysid))
                    for ad in istenen:
                        if ad in onbellek:
                            bulunan[ad] = onbellek[ad]
                except Exception as e:
                    self.konsol("PARAM", f"rota param onbellek: {e}",
                                "uyari")
                # Onbellekte hicbiri yoksa drondan tek tek oku
                eksik = [a for a in istenen if a not in bulunan]
                if eksik and not (self.dji_kopru
                                  and self.dji_kopru.dji_mi(sysid)):
                    import asyncio as _aio
                    loop = _aio.get_event_loop()
                    try:
                        taze = await loop.run_in_executor(None, _db_iade_ederek, self.dron.param_coklu_oku, sysid, eksik)
                        bulunan.update(taze or {})
                    except Exception as e:
                        self.konsol("PARAM", f"rota param okuma: {e}",
                                    "uyari")
                await websocket.send(json.dumps({
                    "tip": "rota_ucus_param", "sysid": sysid,
                    "parametreler": bulunan}))

        elif komut == "param_ara":
            # {"tip":"param_ara","sysid":7,"filtre":"WPNAV"}
            sysid = int(k.get("sysid", 0))
            filtre = str(k.get("filtre", ""))
            if sysid:
                import asyncio as _aio
                loop = _aio.get_event_loop()
                if self.dji_kopru and self.dji_kopru.dji_mi(sysid):
                    sonuc = await loop.run_in_executor(None, _db_iade_ederek, self.dji_kopru.param_ara, sysid, filtre)
                else:
                    sonuc = await loop.run_in_executor(None, _db_iade_ederek, self.dron.param_ara, sysid, filtre)
                await websocket.send(json.dumps({
                    "tip": "param_listesi", "sysid": sysid,
                    "filtre": filtre, "parametreler": sonuc}))

        elif komut == "param_tumu":
            # v2.4.15: {"tip":"param_tumu","sysid":7}
            # v2.4.17: {"tip":"param_tumu","sysid":7,"taze":true}
            # taze=false/yok: SADECE DB onbellegi okunur — drona istek
            # gonderilmez. Onbellek bossa bos liste doner ve arayuz
            # kullaniciyi TUMUNU AL dugmesine yonlendirir.
            # taze=true: drondan tam okuma + onbellege kayit.
            sysid = int(k.get("sysid", 0))
            taze = bool(k.get("taze"))
            if sysid and not taze:
                from . import veritabani as _vt
                c_par, c_top, c_ts = _vt.param_cache_oku(sysid)
                await websocket.send(json.dumps({
                    "tip": "param_listesi", "sysid": sysid,
                    "filtre": "", "tam": True,
                    "kaynak": "cache", "okuma_ts": c_ts,
                    "toplam": int(c_top or len(c_par)),
                    "hata": None,
                    "parametreler": c_par}))
                return
            if sysid:
                import asyncio as _aio
                loop = _aio.get_event_loop()

                def _ilerleme_gonder(alinan, toplam):
                    # Thread baglamindan WS'e guvenli gonderim
                    veri = json.dumps({
                        "tip": "param_ilerleme", "sysid": sysid,
                        "alinan": int(alinan), "toplam": int(toplam)})
                    try:
                        _aio.run_coroutine_threadsafe(
                            websocket.send(veri), loop)
                    except Exception:
                        pass

                sonuc, toplam, p_hata = {}, 0, None
                try:
                    if self.dji_kopru and self.dji_kopru.dji_mi(sysid):
                        # DJI koprusunde index takibi yok — mevcut tam okuma
                        sonuc = await loop.run_in_executor(None, _db_iade_ederek, self.dji_kopru.param_ara, sysid, "")
                        toplam = len(sonuc)
                        if not sonuc:
                            p_hata = "DJI koprusunden parametre alinamadi."
                    else:
                        sonuc, toplam, p_hata = await loop.run_in_executor(None, _db_iade_ederek, self.dron.param_tumu_oku, sysid,
                            _ilerleme_gonder)
                except Exception as e:
                    # v2.4.16: okuma hatasi WS isleyicisini oldurmesin —
                    # hatayi arayuze tasi (popup sonsuz beklemesin)
                    p_hata = f"Parametre okuma hatasi: {e}"
                    self.konsol("PARAM", p_hata, "hata")
                okuma_ts = 0
                if sonuc:
                    # v2.4.17: basarili tam okuma — onbellege kaydet
                    try:
                        from . import veritabani as _vt
                        _p = self._pilot_bilgi(websocket) or {}
                        _vt.param_cache_kaydet(
                            sysid, sonuc, int(toplam or len(sonuc)),
                            uid=self._dron_uid(sysid), kaynak="dron",
                            eposta=_p.get("eposta", ""),
                            isim=_p.get("ad_soyad", ""))
                        okuma_ts = time.time()
                    except Exception as e:
                        self.konsol("PARAM",
                                    f"Onbellek kayit hatasi: {e}", "uyari")
                await websocket.send(json.dumps({
                    "tip": "param_listesi", "sysid": sysid,
                    "filtre": "", "tam": True,
                    "kaynak": "dron", "okuma_ts": okuma_ts,
                    "toplam": int(toplam or len(sonuc)),
                    "hata": p_hata,
                    "parametreler": sonuc}))

        elif komut == "param_yaz":
            # {"tip":"param_yaz","sysid":7,"ad":"WPNAV_SPEED","deger":500}
            sysid = int(k.get("sysid", 0))
            ad = str(k.get("ad", "")).strip()
            deger = k.get("deger")
            if sysid and ad and deger is not None:
                import asyncio as _aio
                loop = _aio.get_event_loop()
                if self.dji_kopru and self.dji_kopru.dji_mi(sysid):
                    ok = await loop.run_in_executor(None, _db_iade_ederek, self.dji_kopru.param_yaz, sysid, ad, deger)
                else:
                    ok = await loop.run_in_executor(None, _db_iade_ederek, self.dron.param_tek_yaz, sysid, ad, deger)
                if ok:
                    # v2.4.17: onbellekteki degeri de guncelle
                    # v2.4.21: kalici parametre tablosu + degisiklik
                    # gecmisi (kim, ne zaman, eski -> yeni)
                    self._param_kalici_kaydet(websocket, sysid, ad, deger)
                await websocket.send(json.dumps({
                    "tip": "param_yazildi", "sysid": sysid,
                    "ad": ad, "deger": deger, "basari": bool(ok)}))
        elif komut == "param_gecmis":
            # v2.4.21: {"tip":"param_gecmis","sysid":7,
            #           "ad":"WPNAV_SPEED","limit":200}
            # Parametre degisiklik gecmisi: eski -> yeni, tarih, kim.
            sysid = int(k.get("sysid", 0))
            ad = str(k.get("ad", "")).strip()
            limit = int(k.get("limit", 200) or 200)
            kayitlar, dron_id = [], None
            if sysid:
                from . import veritabani as _vt
                dron_id = _vt.dron_id_bul(sysid=sysid,
                                          uid=self._dron_uid(sysid))
                if dron_id:
                    kayitlar = _vt.param_gecmisi_oku(dron_id, ad=ad,
                                                     limit=limit)
            await websocket.send(json.dumps({
                "tip": "param_gecmis_listesi", "sysid": sysid,
                "ad": ad, "dron_id": dron_id, "kayitlar": kayitlar}))

        elif komut == "dron_kayit_listesi":
            # v2.4.21: kayitli dronlar (kimlik, ilk kayit, kaydeden pilot)
            from . import veritabani as _vt
            await websocket.send(json.dumps({
                "tip": "dron_kayit_listesi",
                "dronlar": _vt.dron_kayitlari_listele(
                    firma_id=self._ws_firma_id(websocket))}))

        elif komut == "log_listesi":
            # {"tip":"log_listesi","sysid":7}
            sysid = int(k.get("sysid", 0))
            if sysid and self.dji_kopru and self.dji_kopru.dji_mi(sysid):
                self.konsol("DJI", "DJI dronlarda dataflash log yok; "
                            "medya DJI uygulamasindan alinir.", "uyari")
                await websocket.send(json.dumps({
                    "tip": "log_listesi", "sysid": sysid,
                    "basari": False, "loglar": []}))
            elif sysid:
                import asyncio as _aio
                loop = _aio.get_event_loop()
                loglar = await loop.run_in_executor(None, _db_iade_ederek, self.dron.log_listesi, sysid)
                await websocket.send(json.dumps({
                    "tip": "log_listesi", "sysid": sysid,
                    "basari": loglar is not None,
                    "loglar": loglar or []}))
        elif komut == "log_indir":
            # {"tip":"log_indir","sysid":7,"log_id":3,"boyut":123456}
            sysid = int(k.get("sysid", 0))
            log_id = int(k.get("log_id", 0))
            boyut = int(k.get("boyut", 0))
            if sysid and log_id >= 0 and boyut > 0:
                import asyncio as _aio
                import os as _os
                from .sabitler import LOG_KLASORU
                loop = _aio.get_event_loop()
                ad = "D%d_LOG_%d.bin" % (sysid, log_id)
                hedef = _os.path.join(LOG_KLASORU, ad)

                def _ilerle(alinan, toplam,
                            _ws=websocket, _s=sysid, _l=log_id):
                    _aio.run_coroutine_threadsafe(
                        _ws.send(json.dumps({
                            "tip": "log_ilerleme", "sysid": _s,
                            "log_id": _l, "alinan": alinan,
                            "toplam": toplam})), loop)

                ok = await loop.run_in_executor(None, _db_iade_ederek, lambda: self.dron.log_indir(
                        sysid, log_id, boyut, hedef, _ilerle))
                cevap = {"tip": "log_indirildi", "sysid": sysid,
                         "log_id": log_id, "basari": bool(ok)}
                if ok:
                    cevap["dosya"] = "/loglar/" + ad
                else:
                    # v2.4.23: kullanici durdurduysa ayri isaretle
                    durum = (self.dron.log_ilerleme.get(sysid) or {})
                    if durum.get("durum") == "iptal":
                        cevap["iptal"] = True
                        cevap["hata"] = "kullanici durdurdu"
                    else:
                        cevap["hata"] = "indirme basarisiz"
                await websocket.send(json.dumps(cevap))

        elif komut == "log_indir_iptal":
            # v2.4.23: {"tip":"log_indir_iptal","sysid":7}
            sysid = int(k.get("sysid", 0))
            if sysid:
                self.dron.log_indirme_iptal(sysid)

        elif komut == "tile_cache_bilgi":
            from . import tile_cache
            b = tile_cache.cache_bilgi()
            b["tip"] = "tile_cache_bilgi"
            b["indirme"] = tile_cache.indirme_durumu
            await websocket.send(json.dumps(b))
        elif komut == "tile_cache_temizle":
            from . import tile_cache
            b = tile_cache.cache_temizle()
            b["tip"] = "tile_cache_bilgi"
            b["indirme"] = tile_cache.indirme_durumu
            await websocket.send(json.dumps(b))
        elif komut == "tile_cache_indir":
            # {"tip":"tile_cache_indir","kaynak":"esri","lat1":..,"lon1":..,
            #  "lat2":..,"lon2":..,"z1":10,"z2":15}
            from . import tile_cache
            import threading as _th
            import asyncio as _aio
            if tile_cache.indirme_durumu.get("aktif"):
                await websocket.send(json.dumps(
                    {"tip": "hata",
                     "mesaj": "Tile indirme zaten suruyor"}))
            else:
                kaynak = k.get("kaynak", "esri")
                l1 = float(k.get("lat1")); o1 = float(k.get("lon1"))
                l2 = float(k.get("lat2")); o2 = float(k.get("lon2"))
                z1 = int(k.get("z1", 10)); z2 = int(k.get("z2", 15))
                dongu = _aio.get_event_loop()

                def _tilerle(inen, toplam, hata, _ws=websocket):
                    _aio.run_coroutine_threadsafe(
                        _ws.send(json.dumps(
                            {"tip": "tile_cache_ilerleme", "inen": inen,
                             "toplam": toplam, "hata": hata})), dongu)

                _th.Thread(target=tile_cache.bolge_indir,
                           args=(kaynak, l1, o1, l2, o2, z1, z2, _tilerle),
                           daemon=True).start()
                sayi = tile_cache.bolge_tile_sayisi(l1, o1, l2, o2, z1, z2)
                await websocket.send(json.dumps(
                    {"tip": "tile_cache_ilerleme", "inen": 0,
                     "toplam": sayi, "hata": 0}))
        elif komut == "tile_cache_on_olcum":
            # FAZ18-IS31-ONOLCUM: indirme ONCESI tahmin.
            # Kullanici "Gorunen Bolgeyi Indir" dediginde 20 bin
            # karo (69 dk) isteyebiliyordu ve bunu goremiyordu.
            from . import tile_cache
            try:
                oz = tile_cache.bolge_on_olcum(
                    k.get("kaynak", "esri"),
                    float(k.get("lat1")), float(k.get("lon1")),
                    float(k.get("lat2")), float(k.get("lon2")),
                    int(k.get("z1", 10)), int(k.get("z2", 16)))
                oz["tip"] = "tile_cache_on_olcum"
                await websocket.send(json.dumps(oz))
            except BaseException as e:
                await websocket.send(json.dumps(
                    {"tip": "hata",
                     "mesaj": "On olcum yapilamadi: %s" % e}))
        elif komut == "tile_cache_iptal":
            from . import tile_cache
            tile_cache.indirme_iptal()
            await websocket.send(json.dumps({"tip": "tile_cache_ilerleme",
                                             "iptal": True}))

        elif komut == "kaynak_olcum":
            # v2.4.34: Sistem Kaynaklari widget'i icin sunucu tarafi
            # olcumu. Tarayici kendi FPS/bellek degerlerini kendi olcer;
            # buradan gelen deger ISLETIM SISTEMI gerceğidir.
            #
            # Istege bagli (widget acikken ~1 Hz) cagrilir; yayin
            # dongusune EKLENMEZ. Widget kapaliyken sifir maliyet olmasi
            # gerekir, aksi halde izleme araci kendisi yuk kaynagi olur.
            from . import kaynak_olcum
            try:
                oz = kaynak_olcum.olc()
            except Exception as e:
                oz = {"hazir": False, "hata": str(e)}
            oz["tip"] = "kaynak_olcum"
            await websocket.send(json.dumps(oz))
        elif komut in ("takipci_ayar", "filtre_ayar"):
            # Tek alan guncelleme: {"alan":"M","deger":3}
            alan = k.get("alan", "")
            deger = k.get("deger")
            ta = self.takipci.ayar
            if alan and deger is not None and hasattr(ta, alan):
                if alan in ("tip_filtre", "durum_filtre"):
                    setattr(ta, alan, set(deger) if deger else set())
                else:
                    tip = type(getattr(ta, alan))
                    try:
                        setattr(ta, alan, tip(deger))
                    except (TypeError, ValueError):
                        pass
                self.takipci_ayar_kaydet()
                if komut == "takipci_ayar":
                    self.konsol("TAKIPCI",
                                f"Ayar guncellendi: {alan}={deger}")

        elif komut == "siniflandirma_ayar":
            # Tek alan guncelleme: {"alan":"hassasiyet","deger":40}
            alan = k.get("alan", "")
            deger = k.get("deger")
            sa = self.takipci.siniflandirici.ayar
            if alan in ("acik", "hassasiyet", "min_ornek",
                        "histerezis") and deger is not None:
                sa.from_dict({alan: deger})
                self.siniflandirma_ayar_kaydet()
                self.konsol("SINIF",
                            f"Siniflandirma ayari: {alan}={deger}")
            # Guncel durumu isteyen/degistiren istemciye geri bildir
            await websocket.send(json.dumps({
                "tip": "siniflandirma_durum",
                "ayar": sa.to_dict(),
            }))

        elif komut == "izleri_temizle":
            self.takipci.izleri_temizle()
            self.konsol("TAKIPCI", "Tum izler temizlendi.", "uyari")

        elif komut == "iz_sil":
            iz_id = k.get("id")
            try:
                iz_id = int(iz_id)
            except (TypeError, ValueError):
                iz_id = None
            if iz_id is not None and self.takipci.iz_sil(iz_id):
                self.konsol("TAKIPCI",
                            f"Iz R{iz_id} operator tarafindan kaldirildi.",
                            "uyari")

        # ---- UCUS GECMISI (DRON HISTORY) ----
        elif komut == "dron_gecmis_liste":
            if self.ucus_gecmisi:
                # v2.1.8: kullaniciya gore filtre — yonetici tum ucuslari,
                # digerleri yalnizca kendi ucuslarini gorur
                p = self._pilot_bilgi(websocket) or {}
                await websocket.send(json.dumps({
                    "tip": "dron_gecmis_liste",
                    "dronlar": self.ucus_gecmisi.dron_listesi(
                        eposta=p.get("eposta", ""),
                        yonetici=(p.get("rol") == "yonetici"),
                        firma_id=self._ws_firma_id(websocket)),
                }))

        elif komut == "ucus_oku":
            if self.ucus_gecmisi:
                # v2.4.64: SAHIPLIK DENETIMI. Listeyi suzmek YETMEZ;
                # suzgec yalnizca gorunurlugu kisitlar, erisimi degil.
                # Bu denetim olmadan kimligi bilinen (veya denenen) bir
                # ucus, pilotun listesinde gorunmese bile acilabilirdi.
                p = self._pilot_bilgi(websocket) or {}
                _izin, _sebep = self.ucus_gecmisi.sahip_mi(
                    k.get("id", ""), p.get("eposta", ""),
                    yonetici=(p.get("rol") == "yonetici"))
                if not _izin:
                    self.konsol(
                        "IZIN",
                        f"Ucus okuma reddedildi ({_sebep}): "
                        f"{p.get('eposta', '?')} -> {k.get('id', '')}",
                        "uyari")
                    await self._hata_bildir(
                        websocket, "HISTORY",
                        "Bu ucus kaydina erisim yetkiniz yok")
                    return
                ucus = self.ucus_gecmisi.ucus_oku(k.get("id", ""))
                # v2.4.2: ucusa bagli AI tespitleri (timeline isaretleri)
                tespitler = []
                if ucus and self.ai_yonetici:
                    try:
                        tespitler = self.ai_yonetici.ucus_tespitleri(
                            k.get("id", ""))
                    except Exception:
                        tespitler = []
                # v2.4.41: o ucusa ait kalkis kontrol listesi kaydi.
                # Imzali ucus raporunda "pilot hangi soruya ne cevap
                # verdi" bolumu bu veriden basilir. Hata durumunda bos
                # kalir; rapor yine uretilir (denetim izi zorunlu degil,
                # ornegin v2.4.41 oncesi ucuslarda kayit yoktur).
                kalkis = []
                goruntu_kareleri = []
                if ucus:
                    try:
                        # v2.4.42 duzeltme: modul bu kapsamda global degil,
                        # yerel import zorunlu (dosyadaki diger dallarda da
                        # ayni desen kullaniliyor).
                        from . import veritabani as _vt
                        kalkis = _vt.kalkis_kontrol_araligi(
                            ucus.get("dron_id"), ucus.get("baslangic"),
                            ucus.get("bitis"))
                    except Exception as e:
                        self.konsol("HISTORY",
                                    f"Kalkis kontrolu okunamadi: {e}",
                                    "hata")
                        kalkis = []
                    # IS99: Drona bağlı yerel kameradan açık yönetici izniyle
                    # gelen en fazla 1 FPS küçük kareler. Uçuş sahipliği
                    # yukarıda doğrulandı; sorgu ayrıca firma+dron+zaman
                    # kapsamını uygular ve yalnız süreli imzalı URL döndürür.
                    try:
                        bas = float(ucus.get("baslangic") or 0)
                        bit = float(ucus.get("bitis") or time.time())
                        did = int(ucus.get("dron_id") or 0)
                        fid = self._ws_firma_id(websocket)
                        if fid and did > 0 and bit >= bas > 0:
                            goruntu_kareleri = goruntu_gecmisi.listele(
                                fid, did, bas, bit, limit=5000)
                    except Exception as e:
                        self.konsol("HISTORY",
                                    f"Goruntu gecmisi okunamadi: {e}",
                                    "hata")
                        goruntu_kareleri = []
                await websocket.send(json.dumps({
                    "tip": "ucus_veri",
                    "ucus": ucus,
                    "tespitler": tespitler,
                    "kalkis_kontrolleri": kalkis,
                    "goruntu_kareleri": goruntu_kareleri,
                }))

        elif komut == "ucus_sil":
            if self.ucus_gecmisi:
                # v2.4.64: SAHIPLIK DENETIMI. Silme geri alinamaz
                # (telemetri_aralik_sil gercekten veri siler), bu yuzden
                # denetim silme cagrisindan ONCE yapilir.
                p = self._pilot_bilgi(websocket) or {}
                _izin, _sebep = self.ucus_gecmisi.sahip_mi(
                    k.get("id", ""), p.get("eposta", ""),
                    yonetici=(p.get("rol") == "yonetici"))
                if not _izin:
                    self.konsol(
                        "IZIN",
                        f"Ucus silme reddedildi ({_sebep}): "
                        f"{p.get('eposta', '?')} -> {k.get('id', '')}",
                        "uyari")
                    await self._hata_bildir(
                        websocket, "HISTORY",
                        "Bu ucus kaydini silme yetkiniz yok")
                    return
                self.ucus_gecmisi.ucus_sil(k.get("id", ""))
                self._pilot_log(websocket, "gecmis", "ucus_sil",
                                {"id": k.get("id", "")})
                await websocket.send(json.dumps({
                    "tip": "dron_gecmis_liste",
                    "dronlar": self.ucus_gecmisi.dron_listesi(
                        eposta=p.get("eposta", ""),
                        yonetici=(p.get("rol") == "yonetici"),
                        firma_id=self._ws_firma_id(websocket)),
                }))
        elif komut == "gecmis_tumunu_sil":
            # v2.1.8: TUM ucus gecmisini sil — yalnizca yonetici
            if self.ucus_gecmisi:
                p = self._pilot_bilgi(websocket) or {}
                if p.get("rol") != "yonetici":
                    self.konsol("IZIN", "Gecmis silme reddedildi "
                                f"(yonetici degil): {p.get('eposta', '?')}",
                                "uyari")
                    return
                adet = self.ucus_gecmisi.tumunu_sil()
                self.konsol("HISTORY", f"TUM ucus gecmisi silindi "
                            f"({adet} telemetri ornegi, "
                            f"{p.get('eposta', '?')}).", "uyari")
                self._pilot_log(websocket, "gecmis", "tumunu_sil",
                                {"adet": adet})
                await websocket.send(json.dumps({
                    "tip": "dron_gecmis_liste",
                    "dronlar": self.ucus_gecmisi.dron_listesi(
                        eposta=p.get("eposta", ""), yonetici=True,
                        firma_id=self._ws_firma_id(websocket)),
                }))

        elif komut == "manuel_anahtar":
            # {"tip":"manuel_anahtar","sysid":1,"acik":true}
            if self.manuel_kontrol:
                self.manuel_kontrol.anahtar(
                    k.get("sysid", 0), bool(k.get("acik")))
                await websocket.send(json.dumps({
                    "tip": "manuel_durum",
                    **self.manuel_kontrol.durum(),
                }))

        elif komut == "manuel_eksen":
            # {"tip":"manuel_eksen","vx":1,"vy":0,"vz":0,"yaw":0,
            #  "ham":{"vx":..,"vy":..,"vz":..,"yaw":..}}
            # v2.4.50: `ham` alani tarayici joystick'inin ISLENMEMIS
            # eksenleridir. Arayuz artik olu bolge UYGULAMAZ; islem
            # sunucuda pilot tercihine gore yapilir. Boylece ters
            # cevirme/olu bolge/kalibrasyon tek yerde toplanir ve
            # arayuz ile sunucu arasinda tutarsizlik olusmaz.
            if self.manuel_kontrol:
                self.manuel_kontrol.eksen_guncelle(
                    k.get("vx", 0), k.get("vy", 0),
                    k.get("vz", 0), k.get("yaw", 0),
                    ham=k.get("ham"))

        elif komut == "manuel_durum":
            if self.manuel_kontrol:
                await websocket.send(json.dumps({
                    "tip": "manuel_durum",
                    **self.manuel_kontrol.durum(),
                }))

        # ---- v2.4.50: PILOT JOYSTICK TERCIHI --------------------------
        elif komut == "joystick_tercih":
            # {"tip":"joystick_tercih"} -> etkin pilotun tercihi
            await self._joystick_tercih_gonder(websocket)

        elif komut == "joystick_tercih_yaz":
            # {"tip":"joystick_tercih_yaz","tercih":{...}}
            # KISISEL ayardir: her pilot kendi tercihini degistirebilir,
            # yonetici sarti YOKTUR. Baska bir pilotun ayarina
            # dokunulamaz cunku anahtar oturumun e-postasidir.
            await self._joystick_tercih_yaz(websocket, k)

        elif komut == "joystick_kalibre":
            # {"tip":"joystick_kalibre","kaynak":"gamepad|pygame",
            #  "ham":{...}}  ham verilmezse sunucudaki son deger okunur
            await self._joystick_kalibre(websocket, k)

        elif komut == "joystick_ham":
            # {"tip":"joystick_ham"} -> canli ham eksenler (kalibrasyon
            # penceresi bunu periyodik okur ve cubugun gercek merkezini
            # gosterir)
            if self.manuel_kontrol:
                await websocket.send(json.dumps({
                    "tip": "joystick_ham",
                    "pygame": self.manuel_kontrol.ham_joystick(),
                    "gamepad": self.manuel_kontrol.tarayici_ham(),
                }))

        # ---- v2.4.44: YER ISTASYONU 2 (ESP32-S3 kontrol paneli) -------
        # v2.4.59: MERKEZ KIPINDE tum bu eylemler KOPRU MAKINESINDE
        # calisir (bkz. `_gcsdual_kopru_cagir`). Canta pilotun
        # makinesine takilidir; merkez sunucusunun seri portu yoktur.
        # Lokal kurulumda `self.istasyon2` yolu birebir korunur.
        elif komut == "istasyon2_portlar":
            # Seri port listesi. Dron portlarindan AYRI bir listeleyici
            # kullanilir: Istasyon2.portlari_listele() ESP32 UART kopru
            # adaylarini (CP210x/CH34x/FTDI) basa alir ve `aday` bayragi
            # koyar. Kart iki port olarak gorunur ve yanlis olani secmek
            # sessiz basarisizliga yol acar; bu isaret onu onler.
            if self._merkez_kipinde():
                _v, _h = await self._gcsdual_kopru_cagir(
                    websocket, "gcsdual_portlar",
                    {"tumu": bool(k.get("tumu"))},
                    istenen_kopru=k.get("kopru_ornek_id"))
                await websocket.send(json.dumps({
                    "tip": "istasyon2_portlar",
                    "portlar": (_v or {}).get("portlar") or [],
                    "kopru": True, "hata": _h or ""}))
            else:
                from .istasyon2 import Istasyon2 as _I2
                await websocket.send(json.dumps({
                    "tip": "istasyon2_portlar",
                    "portlar": _I2.portlari_listele()}))

        elif komut == "istasyon2_baglan":
            if self._merkez_kipinde():
                _v, _h = await self._gcsdual_kopru_cagir(
                    websocket, "gcsdual_baglan",
                    {"port": str(k.get("port", ""))},
                    istenen_kopru=k.get("kopru_ornek_id"))
                await websocket.send(json.dumps({
                    "tip": "istasyon2_sonuc", "islem": "baglan",
                    "basari": bool(_v is not None), "sebep": _h or "",
                    "kopru": True}))
            elif self.istasyon2:
                basari, sebep = self.istasyon2.baglan(k.get("port", ""))
                await websocket.send(json.dumps({
                    "tip": "istasyon2_sonuc", "islem": "baglan",
                    "basari": bool(basari), "sebep": str(sebep)}))
            else:
                await websocket.send(json.dumps({
                    "tip": "istasyon2_sonuc", "islem": "baglan",
                    "basari": False,
                    "sebep": "Istasyon 2 modulu yuklenmedi"}))

        elif komut == "istasyon2_kes":
            if self._merkez_kipinde():
                _v, _h = await self._gcsdual_kopru_cagir(
                    websocket, "gcsdual_kes", {},
                    istenen_kopru=k.get("kopru_ornek_id"))
                await websocket.send(json.dumps({
                    "tip": "istasyon2_sonuc", "islem": "kes",
                    "basari": bool(_v is not None), "sebep": _h or "",
                    "kopru": True}))
            elif self.istasyon2:
                self.istasyon2.kes()
                await websocket.send(json.dumps({
                    "tip": "istasyon2_sonuc", "islem": "kes",
                    "basari": True, "sebep": ""}))

        elif komut == "istasyon2_led":
            # {"tip":"istasyon2_led","kanal":"P3","acik":true}
            # kanal "ALL" da olabilir. P8-P11/T1/T2 icin firmware komutu
            # SESSIZCE yok sayar (LED cikisi yok) - burada engellenmez,
            # panelin gercek davranisi arayuzde gorunur olsun.
            if self._merkez_kipinde():
                _kanal = str(k.get("kanal", "")).upper()
                _v, _h = await self._gcsdual_kopru_cagir(
                    websocket, "gcsdual_led",
                    {"kanal": _kanal, "acik": bool(k.get("acik"))},
                    istenen_kopru=k.get("kopru_ornek_id"))
                # PING de yanit dondurur: v2.4.45'te lokal yolda PING
                # sessiz kaliyordu ve pilot komutun gittigini
                # goremiyordu. Kopru yolunda bu ayrim yapilmaz.
                await websocket.send(json.dumps({
                    "tip": "istasyon2_sonuc", "islem": "led",
                    "kanal": _kanal, "acik": bool(k.get("acik")),
                    "basari": bool(_v is not None), "sebep": _h or "",
                    "kopru": True}))
            elif self.istasyon2:
                if str(k.get("kanal", "")).upper() == "PING":
                    self.istasyon2.ping()
                    return
                basari, sebep = self.istasyon2.led(
                    k.get("kanal", ""), bool(k.get("acik")))
                # v2.4.45: BASARI halinde de yanit doner. Onceden yalniz
                # hata donuyordu; arayuz "komut gitti" geri bildirimini
                # hic alamiyordu ve LED dugmesi sessiz kaliyordu.
                await websocket.send(json.dumps({
                    "tip": "istasyon2_sonuc", "islem": "led",
                    "kanal": str(k.get("kanal", "")).upper(),
                    "acik": bool(k.get("acik")),
                    "basari": bool(basari), "sebep": str(sebep or "")}))

        elif komut == "istasyon2_kalibre":
            if self._merkez_kipinde():
                _sil = bool(k.get("sil"))
                _v, _h = await self._gcsdual_kopru_cagir(
                    websocket, "gcsdual_kalibre", {"sil": _sil},
                    istenen_kopru=k.get("kopru_ornek_id"))
                await websocket.send(json.dumps({
                    "tip": "istasyon2_sonuc",
                    "islem": "kalibre_sil" if _sil else "kalibre",
                    "basari": bool(_v is not None), "sebep": _h or "",
                    "kopru": True}))
            elif self.istasyon2:
                # v2.4.45: kalibrasyon da yanit doner (onceden sessizdi).
                # Pilot "Kalibre Et"e bastiginda onay gormeli.
                if k.get("sil"):
                    self.istasyon2.kalibrasyon_sil()
                    await websocket.send(json.dumps({
                        "tip": "istasyon2_sonuc", "islem": "kalibre_sil",
                        "basari": True, "sebep": ""}))
                else:
                    sonuc = self.istasyon2.kalibre_et()
                    if isinstance(sonuc, tuple) and len(sonuc) == 2:
                        basari, sebep = bool(sonuc[0]), str(sonuc[1] or "")
                    else:
                        basari, sebep = True, ""
                    await websocket.send(json.dumps({
                        "tip": "istasyon2_sonuc", "islem": "kalibre",
                        "basari": basari, "sebep": sebep}))

        elif komut == "istasyon2_ayar":
            # Panelde dron secici YOK: ucus eylemleri joystick kontrolu
            # ACIK olan tum dronlara gider (_ist2_manuel_dronlar).
            # Bu yuzden hedef sysid ayari da yoktur.
            #
            # v2.4.59: merkez kipinde "otomatik baglan" ayari cantanin
            # bulundugu makinede anlamlidir. Kapatma istegi kopruye
            # `gcsdual_kes` olarak gider; acma istegi `gcsdual_baglan`.
            # Merkezde ayar dosyasina yazmak ETKISIZ olurdu ve pilot
            # anahtarin bozuk oldugunu dusunurdu.
            if self._merkez_kipinde():
                if "otomatik" in k:
                    _ac = bool(k.get("otomatik"))
                    await self._gcsdual_kopru_cagir(
                        websocket,
                        "gcsdual_baglan" if _ac else "gcsdual_kes",
                        {} if not _ac else {"port": str(k.get("port", ""))},
                        istenen_kopru=k.get("kopru_ornek_id"))
            elif self.istasyon2:
                self.istasyon2.ayar_yaz(k)

        elif komut == "istasyon2_durum":
            if self._merkez_kipinde():
                _v, _h = await self._gcsdual_kopru_cagir(
                    websocket, "gcsdual_durum", {},
                    istenen_kopru=k.get("kopru_ornek_id"),
                    zaman_asimi=6.0)
                _paket = {
                    "tip": "istasyon2_durum",
                    "manuel_dronlar": self._ist2_manuel_dronlar(),
                    "kopru": True,
                }
                if _v is None:
                    # `yok` bayragi ARAYUZUN paneli "canta baglanmadi"
                    # olarak cizmesini saglar. Hata metni gorunur
                    # kalir: pilot GroundGCC Sunucusu'nu baslatmasi
                    # gerektigini okumali.
                    _paket.update({"bagli": False, "yok": True,
                                   "hata": _h or ""})
                else:
                    _v.pop("tip", None)
                    _v.pop("tamam", None)
                    _paket.update(_v)
                await websocket.send(json.dumps(_paket))
            elif self.istasyon2:
                await websocket.send(json.dumps({
                    "tip": "istasyon2_durum",
                    "manuel_dronlar": self._ist2_manuel_dronlar(),
                    **self.istasyon2.durum()}))
            else:
                await websocket.send(json.dumps({
                    "tip": "istasyon2_durum", "bagli": False,
                    "yok": True, "hata": "modul yuklenmedi"}))

        elif komut == "giris":
            eposta = str(k.get("eposta", "")).strip().lower()
            sifre = str(k.get("sifre", ""))
            # KK_APP_BAGLA_v1: kaba kuvvet denetimi. Parola DOGRULANMADAN once
            # calisir; bloklu istemci hic dogrulama yapmadan reddedilir.
            # Boylece kilitli hesapta parola karsilastirma maliyeti de
            # olusmaz (kaynak tuketme saldirisina karsi).
            if await self._kk_ws_denetle(websocket, "ws:giris", k):
                return
            kul, _mk_hata = self._kimlik_dogrula(eposta, sifre)
            if kul:
                self.konsol("AUTH",
                            f"Giris basarili: {kul['ad_soyad']} ({eposta})",
                            "basari")
                # v2.1.7: websocket -> pilot eslemesi (tum loglar bu
                # pilotun etiketiyle kaydedilir)
                self._ws_pilot[id(websocket)] = kul
                # v2.4.53 Faz 3: firma izolasyonu. Merkezde calisan
                # ornek cok firmali oldugu icin oturumun firma_id'si
                # saklanir; veri sorgulari bu deger ile filtrelenir.
                try:
                    if kul.get("firma_id"):
                        self._ws_firma[id(websocket)] = int(
                            kul["firma_id"])
                except Exception:
                    pass
                # v2.3.0: giris denemesi istemci ayrintilariyla loglanir
                self._giris_logla(websocket, eposta,
                                  kul.get("ad_soyad", ""), True, "")
                # KK_APP_BAGLA_v1: basarili giris sayaclari SIFIRLAR. Aksi
                # halde gun icinde birikmis hatalar mesru kullaniciyi
                # sonradan kilitler.
                self._kk_ws_sonuc(websocket, "ws:giris", k, True)
                # v2.4.50: pilotun joystick tercihini ANINDA etkin yap.
                # Giris sirasinda yuklenmezse ayar kayitli olsa bile
                # etkisiz kalir; kullanici bunu "ayar duruyor ama ise
                # yaramiyor" olarak yasar.
                try:
                    self._joystick_tercih_uygula(websocket)
                except Exception:
                    pass
                cevap = {"tip": "giris_sonuc", "basarili": True,
                         "kullanici": kul}
                # BULGU_10a: istemci artik parola saklamaz; otomatik
                # giris icin OTURUM JETONU kullanir. Uretim basarisiz
                # olursa alan gonderilmez ve istemci elle girise duser:
                # islev kaybi olur ama GUVENLIK kaybi olmaz.
                try:
                    _jt = self._jeton_uret(eposta, "app otomatik giris")
                    if _jt:
                        cevap["jeton"] = _jt
                except Exception:
                    pass
                # v2.4.53 Faz 4: arayuz giris yapan kurumun kimligini
                # (unvan + logo) ust duzey alanlardan okur. `kullanici`
                # sozlugu ic alanlarini degistirmemek icin AYRI alanlar
                # gonderilir; boylece mevcut arayuz kodu bozulmaz.
                try:
                    _f = self._firma_kimligi(websocket)
                    if _f:
                        cevap["firma"] = _f
                except Exception:
                    pass
                if self.pilot:
                    cevap["izinler"] = self.pilot.rol_izinleri(
                        kul.get("rol"))
                    cevap["okunmamis"] = self.pilot.okunmamis_sayi(eposta)
                    self.pilot.log_yaz(eposta, kul.get("ad_soyad", ""),
                                       "oturum", "giris", {})
                # v2.4.32: header mesaj ikonu ilk cizimde kirmizi
                # olabilmeli; sayac giris yanitinda gonderilir.
                if self.mesajlar:
                    cevap["mesaj_okunmamis"] = \
                        self.mesajlar.okunmamis_sayi(eposta)
                await websocket.send(json.dumps(cevap))
                # Diger pilotlara "cevrimici oldu" bildirimi.
                # Eslemeye YAZILDIKTAN sonra duyurulur, aksi halde
                # kendi listesinde kendisi cevrimdisi gorunur.
                await self._pilot_durum_duyur(eposta, True)
            else:
                self.konsol("AUTH", f"Giris basarisiz: {eposta}", "uyari")
                # v2.3.0: basarisiz denemeler de loglanir
                self._giris_logla(websocket, eposta, "", False,
                                  "eposta_veya_sifre_hatali")
                # KK_APP_BAGLA_v1
                self._kk_ws_sonuc(websocket, "ws:giris", k, False)
                await websocket.send(json.dumps(
                    {"tip": "giris_sonuc", "basarili": False,
                     "hata": (_mk_hata or
                              "E-posta veya sifre hatali.")}))

        elif komut == "jeton_giris":
            # BULGU_10a: parolasiz otomatik giris. Basarili akis `giris`
            # ile AYNI yaniti uretir, boylece arayuz tek bir
            # `giris_sonuc` isleyicisi kullanmaya devam eder.
            # KK_APP_BAGLA_v1: sizdirilmis jeton listesiyle deneme yapilabilir.
            # Mesru istemci jetonu BIR kez gonderir; 8 basarisiz jeton
            # denemesi normal akista olusmaz.
            if await self._kk_ws_denetle(websocket, "ws:jeton_giris", k):
                return
            _jt = str(k.get("jeton", ""))
            kul = self._jeton_dogrula(_jt)
            if kul:
                eposta = str(kul.get("eposta", "")).strip().lower()
                self.konsol("AUTH",
                            f"Jeton ile giris: "
                            f"{kul.get('ad_soyad', '')} ({eposta})",
                            "basari")
                self._ws_pilot[id(websocket)] = kul
                try:
                    if kul.get("firma_id"):
                        self._ws_firma[id(websocket)] = int(
                            kul["firma_id"])
                except Exception:
                    pass
                self._giris_logla(websocket, eposta,
                                  kul.get("ad_soyad", ""), True, "jeton")
                # KK_APP_BAGLA_v1
                self._kk_ws_sonuc(websocket, "ws:jeton_giris", k, True)
                try:
                    self._joystick_tercih_uygula(websocket)
                except Exception:
                    pass
                cevap = {"tip": "giris_sonuc", "basarili": True,
                         "kullanici": kul}
                # FAZ20-OFFLINE-KAMERA-OTURUM: Doğrulanmış mevcut jeton,
                # URL yerine yalnız aynı-origin HTTP Authorization başlığında
                # kullanılarak HttpOnly MJPEG çerezine dönüştürülür. Yeni
                # jeton üretilmez; ömür/iptal tek doğruluk kaynağında kalır.
                cevap["jeton"] = _jt
                try:
                    _f = self._firma_kimligi(websocket)
                    if _f:
                        cevap["firma"] = _f
                except Exception:
                    pass
                if self.pilot:
                    cevap["izinler"] = self.pilot.rol_izinleri(
                        kul.get("rol"))
                    cevap["okunmamis"] = self.pilot.okunmamis_sayi(eposta)
                    self.pilot.log_yaz(eposta, kul.get("ad_soyad", ""),
                                       "oturum", "jeton_giris", {})
                if self.mesajlar:
                    cevap["mesaj_okunmamis"] = \
                        self.mesajlar.okunmamis_sayi(eposta)
                await websocket.send(json.dumps(cevap))
                await self._pilot_durum_duyur(eposta, True)
            else:
                # Gecersiz/suresi gecmis jeton: istemci onu SILMELI.
                # `jeton_gecersiz` alani bunu bildirir; aksi halde
                # istemci 800 ms'de bir bosuna dener ve gunlugu kirletir.
                # KK_APP_BAGLA_v1
                self._kk_ws_sonuc(websocket, "ws:jeton_giris", k, False)
                await websocket.send(json.dumps(
                    {"tip": "giris_sonuc", "basarili": False,
                     "jeton_gecersiz": True,
                     "hata": "Oturum s\u00fcresi doldu, "
                             "tekrar giri\u015f yap\u0131n."}))

        elif komut == "kullanici_liste":
            await websocket.send(json.dumps(
                {"tip": "kullanici_liste",
                 "kullanicilar": self.kullanicilar.listesi_guvenli()}))

        # ------------------------------------------------------------
        # v2.4.32: PILOT LISTESI + MESAJLASMA
        #
        # Tumu oturum zorunludur. Alici/gonderen ISTEMCIDEN ALINMAZ;
        # gonderen daima `_ws_pilot` eslemesinden okunur, aksi halde
        # bir istemci baskasi adina mesaj yazabilir.
        # ------------------------------------------------------------
        elif komut == "pilot_liste":
            _p = self._pilot_bilgi(websocket)
            if not _p:
                await websocket.send(json.dumps(
                    {"tip": "pilot_liste", "pilotlar": [],
                     "hata": "Oturum gerekli."}))
            else:
                _ben = str(_p.get("eposta", "")).lower()
                await websocket.send(json.dumps(
                    {"tip": "pilot_liste",
                     "ben": _ben,
                     "pilotlar": self._pilot_listesi(_ben)}))

        elif komut == "kopru_liste":
            # v2.4.53 Faz 7: Baglanti Yoneticisi dron/AI/video
            # baglantilarini KOPRU basina gruplar. Liste merkez
            # veritabanindan gelir; yalniz oturumun firmasi.
            _fid = self._ws_firma_id(websocket)
            _kopruler = []
            _hata = ""
            # v2.4.183 OLCULEN KUSUR: `_fid is None` KOSULSUZ "Oturum
            # gerekli" donuyordu — ama YEREL/offline kurulumda firma_id
            # HICBIR ZAMAN atanmaz (tek kiracili kurulum, oturum acik
            # olsa BILE None kalir). Asagidaki `else` dalinin kendisi
            # zaten bu durumu doğru ele aliyordu ("Yerel kurulumda kopru
            # kavrami yoktur: bos liste doner") ama bu satir oraya HIC
            # ULASILMASINI engelliyordu. Sonuc: her yerel kurulumda
            # Baglanti Yoneticisi/M50 saha makinesi secici konsola surekli
            # "[KOPRU] liste hatasi: Oturum gerekli" yaziyor VE M50 panel
            # kopru secicisi (birden fazla saha koprusu varsa) hic
            # dolmuyordu. Artik yalniz GERCEKTEN merkez kipindeyken
            # (coklu kiracili/bulut kurulum) firma_id zorunlu tutulur.
            if self._merkez_kipinde() and _fid is None:
                _hata = "Oturum gerekli."
            else:
                try:
                    from . import merkez_kimlik as _mk
                    if _mk.etkin():
                        _kopruler = _mk.firma_kopruleri(_fid)
                        # Servis durumlari (Dron/AI/Video) kopru
                        # makinesinde yasar: yalniz CEVRIMICI
                        # kopruye sorulur. Cevrimdisi kopruye sorgu
                        # denemek her istegi zaman asimina kadar
                        # bekletir ve panel donar.
                        #
                        # Sorgular PARALEL yapilir: sirayla sorulsa
                        # 10 koprulu bir firmada panel 50 sn donar.
                        # Ayrica bu cagrilar SENKRON HTTP oldugu icin
                        # asyncio dongusu disinda (is parcaciginda)
                        # calistirilir; yoksa TUM arayuz WS trafigi
                        # sorgu suresince durur.
                        _hedef = [_k for _k in _kopruler
                                  if _k.get("cevrimici")]
                        for _k in _kopruler:
                            _k["servisler"] = None
                            _k["servis_hata"] = ""
                        if _hedef:
                            def _servis_cek(_liste=_hedef, _f=_fid):
                                import concurrent.futures as _cf

                                def _bir(_kk):
                                    return _kk, _mk.kopruye_sor(
                                        _kk["ornek_id"], _f,
                                        "servis_durum", zaman_asimi=5.0)

                                _n = min(8, len(_liste))
                                with _cf.ThreadPoolExecutor(_n) as _h2:
                                    return list(_h2.map(_bir, _liste))

                            for _kk, (_v, _h) in await _db_is_parcasi(
                                    _servis_cek):
                                _kk["servisler"] = (
                                    (_v or {}).get("servisler")
                                    if _v else None)
                                _kk["servis_hata"] = _h or ""
                    else:
                        # Yerel kurulumda kopru kavrami yoktur:
                        # bos liste doner, arayuz grup cizmez.
                        _kopruler = []
                except Exception as _e:
                    _hata = str(_e)
                    print(f"[KOPRU] Liste okunamadi: {_e}")
            # v2.4.55: arayuz, baglanti eklerken kopru secimini merkez
            # kipinde ZORUNLU kilar. Bu karar sunucudan bildirilir;
            # arayuzun "liste bos degilse merkezdeyim" gibi bir
            # cikarim yapmasi yanlis olurdu, cunku hicbir kopru
            # kaydolmamis bir merkez de merkezdir.
            await websocket.send(json.dumps(
                {"tip": "kopru_liste", "kopruler": _kopruler,
                 "merkez_kipi": self._merkez_kipinde(),
                 "hata": _hata}))

        elif komut == "mesaj_gonder":
            _p = self._pilot_bilgi(websocket)
            if not (_p and self.mesajlar):
                await websocket.send(json.dumps(
                    {"tip": "mesaj_sonuc", "basarili": False,
                     "hata": "Oturum gerekli."}))
            else:
                _g = str(_p.get("eposta", "")).lower()
                _mesaj, _hata = self.mesajlar.gonder(
                    _g, k.get("alici", ""), k.get("metin", ""))
                if not _mesaj:
                    await websocket.send(json.dumps(
                        {"tip": "mesaj_sonuc", "basarili": False,
                         "hata": _hata}))
                else:
                    _mesaj["gonderen_ad"] = _p.get("ad_soyad", "") or _g
                    _paket = {"tip": "mesaj_yeni", "mesaj": _mesaj}
                    # Gonderenin TUM sekmelerine de gider: ayni pilot
                    # baska sekmede sohbeti acik tutuyor olabilir.
                    await self._pilota_gonder(_g, _paket)
                    _a = _mesaj["alici"]
                    _ulasti = await self._pilota_gonder(_a, _paket)
                    if _ulasti:
                        # Alici cevrimici: header sayacini tazelemesi icin
                        await self._pilota_gonder(_a, {
                            "tip": "mesaj_okunmamis_sayi",
                            "sayi": self.mesajlar.okunmamis_sayi(_a)})
                    await websocket.send(json.dumps(
                        {"tip": "mesaj_sonuc", "basarili": True,
                         "id": _mesaj["id"]}))

        elif komut == "mesaj_gecmis":
            _p = self._pilot_bilgi(websocket)
            if not (_p and self.mesajlar):
                await websocket.send(json.dumps(
                    {"tip": "mesaj_gecmis", "karsi": "", "mesajlar": [],
                     "hata": "Oturum gerekli."}))
            else:
                _ben = str(_p.get("eposta", "")).lower()
                _karsi = str(k.get("karsi", "")).strip().lower()
                await websocket.send(json.dumps(
                    {"tip": "mesaj_gecmis", "karsi": _karsi,
                     "mesajlar": self.mesajlar.gecmis(
                         _ben, _karsi, k.get("limit", 200))}))

        elif komut == "mesaj_okundu":
            _p = self._pilot_bilgi(websocket)
            if _p and self.mesajlar:
                _ben = str(_p.get("eposta", "")).lower()
                _karsi = (None if k.get("tumu")
                          else str(k.get("karsi", "")).strip().lower())
                self.mesajlar.okundu_isaretle(_ben, _karsi)
                # Ayni pilotun tum sekmeleri sayaci esitler
                await self._pilota_gonder(_ben, {
                    "tip": "mesaj_okunmamis_sayi",
                    "sayi": self.mesajlar.okunmamis_sayi(_ben),
                    "okundu_karsi": _karsi or ""})

        elif komut == "mesaj_okunmamis":
            _p = self._pilot_bilgi(websocket)
            if not (_p and self.mesajlar):
                await websocket.send(json.dumps(
                    {"tip": "mesaj_okunmamis", "liste": [], "sayi": 0}))
            else:
                _ben = str(_p.get("eposta", "")).lower()
                _liste, _sayi = self.mesajlar.okunmamis_ozet(_ben)
                await websocket.send(json.dumps(
                    {"tip": "mesaj_okunmamis",
                     "liste": _liste, "sayi": _sayi}))

        elif komut == "kullanici_guncelle":
            # {eposta, alanlar:{rol, aktif, sifre, ad_soyad, unvan}}
            yetkili = self.kullanicilar.bul(str(k.get("yetkili", "")))
            hedef = str(k.get("eposta", "")).strip().lower()
            alanlar = dict(k.get("alanlar", {}) or {})
            yonetici_mi = bool(yetkili and yetkili.get("rol") == "yonetici")
            kendisi_mi = bool(yetkili and
                              yetkili.get("eposta", "").lower() == hedef)
            # v2.4.65 TEK KAPI: uyelik yonetimi (baska kullaniciya
            # dokunmak, rol/aktif degistirmek) YALNIZCA kurumsal
            # panelden yapilir. Bu ucta ARTIK yalnizca kisinin KENDI
            # ad_soyad/unvan/sifre alanlari guncellenebilir.
            #
            # NEDEN: iki ayri kullanici tablosu var. Bu uc yerel
            # `goktungu_app.kullanicilar` tablosuna yazar; ancak /app/
            # GOKTUNGU_MERKEZ_KIMLIK=1 ile MERKEZ tablosundan dogrular.
            # Yerel tabloya yazilan kullanici hicbir zaman giris
            # YAPAMAZ (olculdu: fatih.gemi olayi). Ayrica koltuk ve
            # faturalandirma denetimi merkezde oldugu icin buradaki
            # yazma kapisi faturalandirmayi atlatan ikinci kapi olur.
            if not kendisi_mi:
                await websocket.send(json.dumps(
                    {"tip": "kullanici_islem", "basarili": False,
                     "hata": "Uyelik yonetimi kurumsal panelden "
                             "yapilir.",
                     "yonlendir": "/company/"}))
                return
            # Rol ve aktiflik bu uctan ASLA degistirilemez (yonetici
            # dahil). Sessizce dusurulmez; islem reddedilir ki
            # kullanici nereye gitmesi gerektigini ogrensin.
            if ("rol" in alanlar) or ("aktif" in alanlar):
                await websocket.send(json.dumps(
                    {"tip": "kullanici_islem", "basarili": False,
                     "hata": "Rol ve uyelik durumu kurumsal "
                             "panelden yonetilir.",
                     "yonlendir": "/company/"}))
                return
            bulundu = self.kullanicilar.guncelle(hedef, alanlar)
            self.konsol("AUTH",
                        f"Kullanici guncellendi: {hedef}" if bulundu
                        else f"Kullanici bulunamadi: {hedef}",
                        "basari" if bulundu else "uyari")
            guncel = None
            if bulundu:
                self._pilot_log(websocket, "kullanici",
                                "kullanici_guncelle",
                                {"hedef": hedef,
                                 "alanlar": [a for a in alanlar
                                             if a != "sifre"]})
                # Kendi bilgisi degistiyse guncel kaydi da gonder
                guncel = self.kullanicilar.bul(hedef) or {}
                guncel.pop("sifre", None)
                # Oturumdaki pilot kaydini tazele
                for wid, p in self._ws_pilot.items():
                    if p.get("eposta", "").lower() == hedef:
                        p.update(guncel)
            await websocket.send(json.dumps(
                {"tip": "kullanici_islem", "basarili": bulundu,
                 "eposta": hedef, "guncel": guncel,
                 "kullanicilar": self.kullanicilar.listesi_guvenli()}))
        elif komut == "kullanici_ekle":
            # v2.4.65 TEK KAPI: kullanici olusturma bu uctan KALDIRILDI.
            # Uyelik ekleme YALNIZCA kurumsal panelden yapilir; boylece
            # (a) kayit merkez tablosuna gider ve kullanici gercekten
            # giris yapabilir, (b) pilot koltuk siniri ve faturalandirma
            # denetimi atlanamaz.
            eposta = str(k.get("eposta", "")).strip().lower()
            self.konsol("AUTH",
                        "Kullanici ekleme istegi reddedildi (tek kapi): "
                        f"{eposta} -> kurumsal panel",
                        "uyari")
            await websocket.send(json.dumps(
                {"tip": "kullanici_islem", "basarili": False,
                 "islem": "ekle", "eposta": eposta,
                 "hata": "Uyelik ekleme kurumsal panelden yapilir.",
                 "yonlendir": "/company/"}))

        elif komut == "avatar_yukle":
            # v2.3.3: profil fotografi yukleme
            # {yetkili, eposta, veri: "data:image/png;base64,..."}
            # Kendi fotografini herkes, baskasininkini yalniz yonetici
            # degistirebilir. Dosya avatars/ klasorune yazilir, DB'ye
            # goreli yol kaydedilir. Bos veri = fotografi kaldir.
            import base64 as _b64
            import re as _re
            yetkili = self.kullanicilar.bul(str(k.get("yetkili", "")))
            hedef = str(k.get("eposta", "")).strip().lower()
            yonetici_mi = bool(yetkili and yetkili.get("rol") == "yonetici")
            kendisi_mi = bool(yetkili and
                              yetkili.get("eposta", "").lower() == hedef)
            if not (yonetici_mi or kendisi_mi):
                await websocket.send(json.dumps(
                    {"tip": "kullanici_islem", "basarili": False,
                     "islem": "avatar", "hata": "Yetkisiz islem."}))
                return
            veri = str(k.get("veri", ""))
            yol = ""
            hata = None
            if veri:
                es = _re.match(
                    r"^data:image/(png|jpeg|jpg|webp);base64,(.+)$",
                    veri, _re.DOTALL)
                if not es:
                    hata = "Desteklenmeyen resim bicimi."
                else:
                    try:
                        ham = _b64.b64decode(es.group(2))
                    except Exception:
                        ham = b""
                    if not ham:
                        hata = "Resim verisi cozulemedi."
                    elif len(ham) > 2 * 1024 * 1024:
                        hata = "Resim 2 MB'dan buyuk olamaz."
                    else:
                        uzanti = {"jpeg": "jpg"}.get(
                            es.group(1), es.group(1))
                        guvenli = _re.sub(r"[^a-z0-9]+", "_",
                                          hedef.split("@")[0]) or "kul"
                        dosya = f"{guvenli}_{int(time.time())}.{uzanti}"
                        # v2.4.52: avatarlar VERI kokune yazilir
                        # (kullanici verisi), HTTP'den ise web koku
                        # uzerinden okunur. Iki dizin ayri oldugu icin
                        # GoktunguHttpHandler `/avatars/` istegini ozel
                        # olarak esler (bkz. translate_path).
                        klasor = AVATAR_KLASORU
                        os.makedirs(klasor, exist_ok=True)
                        # Ayni kullanicinin eski yuklemesini temizle
                        try:
                            for eski in os.listdir(klasor):
                                if eski.startswith(guvenli + "_"):
                                    os.remove(os.path.join(klasor, eski))
                        except Exception:
                            pass
                        with open(os.path.join(klasor, dosya), "wb") as f:
                            f.write(ham)
                        yol = "avatars/" + dosya
            if hata:
                await websocket.send(json.dumps(
                    {"tip": "kullanici_islem", "basarili": False,
                     "islem": "avatar", "eposta": hedef, "hata": hata}))
                return
            bulundu = self.kullanicilar.guncelle(hedef, {"avatar": yol})
            self.konsol("AUTH",
                        f"Profil fotografi guncellendi: {hedef}" if bulundu
                        else f"Kullanici bulunamadi: {hedef}",
                        "basari" if bulundu else "uyari")
            guncel = None
            if bulundu:
                self._pilot_log(websocket, "kullanici", "avatar_yukle",
                                {"hedef": hedef, "dosya": yol})
                guncel = self.kullanicilar.bul(hedef) or {}
                guncel.pop("sifre", None)
                for wid, p in self._ws_pilot.items():
                    if p.get("eposta", "").lower() == hedef:
                        p.update(guncel)
            await websocket.send(json.dumps(
                {"tip": "kullanici_islem", "basarili": bulundu,
                 "islem": "avatar", "eposta": hedef, "guncel": guncel,
                 "kullanicilar": self.kullanicilar.listesi_guvenli()}))

        # ---- v2.1.7: ROL YONETIMI ----
        elif komut == "rol_listesi" and self.pilot:
            from .veritabani import IZIN_SEMASI
            await websocket.send(json.dumps({
                "tip": "rol_listesi",
                "sema": IZIN_SEMASI,
                "roller": {ad: self.pilot.rol_izinleri(ad)
                           for ad in self.pilot.roller()}}))

        elif komut in ("rol_kaydet", "rol_ekle", "rol_sil") and self.pilot:
            # v2.4.65 TEK KAPI: rol yonetimi (izin duzenleme, rol ekleme
            # ve silme) bu uctan KALDIRILDI. Roller kurumsal panelden
            # yonetilir; boylece rol tanimi ile merkezdeki uyelik kaydi
            # ayrisamaz. Okuma ucu (rol_listesi) KALIR: arayuz izin
            # semasini gostermek icin ona ihtiyac duyar.
            rol_adi = str(k.get("rol", "")).strip().lower()
            self.konsol("IZIN",
                        f"Rol islemi reddedildi (tek kapi): {komut} "
                        f"{rol_adi} -> kurumsal panel",
                        "uyari")
            from .veritabani import IZIN_SEMASI
            await websocket.send(json.dumps({
                "tip": "rol_islem", "basarili": False,
                "hata": "Rol yonetimi kurumsal panelden yapilir.",
                "yonlendir": "/company/",
                "sema": IZIN_SEMASI,
                "roller": {ad: self.pilot.rol_izinleri(ad)
                           for ad in self.pilot.roller()}}))

        # ---- v2.1.7: PILOT LOG (program gecmisi) ----
        elif komut == "pilot_log_listesi" and self.pilot:
            # {"tip":"pilot_log_listesi","eposta":"..."} — yonetici
            # herkesinkini, kullanici yalniz kendisininkini gorebilir
            p = self._pilot_bilgi(websocket) or {}
            istenen = str(k.get("eposta", "")).strip().lower()
            if p.get("rol") != "yonetici":
                istenen = p.get("eposta", "").lower()
            await websocket.send(json.dumps({
                "tip": "pilot_log_listesi", "eposta": istenen,
                "kayitlar": self.pilot.log_listesi(istenen)}))

        # ---- v2.1.7: MERKEZI UYARILAR ----
        elif komut == "uyari_listesi" and self.pilot:
            p = self._pilot_bilgi(websocket) or {}
            istenen = str(k.get("eposta", "")).strip().lower()
            if not istenen or p.get("rol") != "yonetici":
                istenen = p.get("eposta", "").lower()
            liste, okunmamis = self.pilot.uyari_listesi(istenen)
            await websocket.send(json.dumps({
                "tip": "uyari_listesi", "eposta": istenen,
                "uyarilar": liste, "okunmamis": okunmamis}))

        elif komut == "uyari_okundu" and self.pilot:
            p = self._pilot_bilgi(websocket) or {}
            ep = p.get("eposta", "").lower()
            if ep:
                self.pilot.uyari_okundu(ep)
            await websocket.send(json.dumps({
                "tip": "uyari_sayi", "okunmamis": 0}))

        elif komut == "lokasyon_liste":
            await websocket.send(json.dumps(
                {"tip": "lokasyon_liste",
                 "lokasyonlar": self.lokasyonlar.yukle()}))

        elif komut == "lokasyon_ekle":
            liste = self.lokasyonlar.ekle(k.get("ad"), k.get("lat"),
                                          k.get("lon"),
                                          k.get("adres", ""))
            if liste is not None:
                self.konsol("LOK",
                            f"Lokasyon eklendi: {str(k.get('ad'))[:60]}",
                            "basari")
                await self._duyur({"tip": "lokasyon_liste",
                                   "lokasyonlar": liste})

        elif komut == "lokasyon_duzenle":
            try:
                lok_id = int(k.get("id"))
            except (TypeError, ValueError):
                return
            liste = self.lokasyonlar.duzenle(
                lok_id, k.get("ad"), adres=k.get("adres"),
                lat=k.get("lat"), lon=k.get("lon"))
            if liste is not None:
                self.konsol("LOK",
                            f"Lokasyon adi guncellendi: #{lok_id}",
                            "basari")
                await self._duyur({"tip": "lokasyon_liste",
                                   "lokasyonlar": liste})

        elif komut == "lokasyon_sil":
            try:
                lok_id = int(k.get("id"))
            except (TypeError, ValueError):
                return
            liste = self.lokasyonlar.sil(lok_id)
            self.konsol("LOK", f"Lokasyon silindi: #{lok_id}", "basari")
            await self._duyur({"tip": "lokasyon_liste",
                               "lokasyonlar": liste})

        elif komut == "rota_listele" and self.rotalar:
            await websocket.send(json.dumps(
                {"tip": "rota_listesi",
                 "rotalar": self.rotalar.rota_listele()}))
        elif komut == "rota_kaydet" and self.rotalar:
            rota_id = k.get("id")
            if rota_id is None:
                yeni_id, liste = self.rotalar.rota_ekle(
                    k.get("isim"), k.get("irtifa"), k.get("hiz"),
                    noktalar=k.get("noktalar"), meta=k.get("meta"))
                if yeni_id is not None:
                    self.konsol("ROTA",
                                f"Rota olusturuldu: "
                                f"{str(k.get('isim'))[:60]} (#{yeni_id})",
                                "basari")
                    await self._duyur(
                        {"tip": "rota_listesi", "yeni_id": yeni_id,
                         "rotalar": self.rotalar.rota_listele()})
                else:
                    self.konsol("ROTA", "Rota olusturulamadi "
                                "(gecersiz parametre)", "hata")
            else:
                try:
                    rota_id = int(rota_id)
                except (TypeError, ValueError):
                    return
                liste = self.rotalar.rota_guncelle(
                    rota_id, isim=k.get("isim"),
                    irtifa_varsayilan=k.get("irtifa"),
                    hiz_varsayilan=k.get("hiz"),
                    noktalar=k.get("noktalar"),
                    gorunur=k.get("gorunur"),
                    meta=k.get("meta"))
                if liste is not None:
                    self.konsol("ROTA", f"Rota guncellendi: #{rota_id}",
                                "basari")
                    await self._duyur(
                        {"tip": "rota_listesi",
                         "rotalar": self.rotalar.rota_listele()})
                else:
                    self.konsol("ROTA",
                                f"Rota guncellenemedi: #{rota_id}", "hata")
        elif komut == "rota_tek_goster" and self.rotalar:
            # Yalniz verilen rotayi gorunur yap, digerlerini gizle
            try:
                rota_id = int(k.get("id"))
            except (TypeError, ValueError):
                return
            liste = None
            for r in self.rotalar.rota_listele():
                hedef = (r["id"] == rota_id)
                if bool(r.get("gorunur", True)) != hedef:
                    liste = self.rotalar.rota_guncelle(
                        r["id"], gorunur=hedef)
            await self._duyur({"tip": "rota_listesi",
                               "rotalar": self.rotalar.rota_listele()})

        elif komut == "gorev_yukle_baslat" and self.gorev and self.rotalar:
            # {"tip":"gorev_yukle_baslat","sysid":1,"rota_id":2}
            try:
                sysid = int(k.get("sysid"))
                rota_id = int(k.get("rota_id"))
            except (TypeError, ValueError):
                return
            rota = next((r for r in self.rotalar.rota_listele()
                         if r["id"] == rota_id), None)
            if rota is None:
                self.konsol("GOREV", f"Rota bulunamadi: #{rota_id}",
                            "hata")
            else:
                self.gorev.yukle_ve_baslat(sysid, rota)

        elif komut == "guncelleme_durum":
            # v2.5.18: Durum alma yalniz salt-okunur ozet doner.
            # Uzak denetim hicbir zaman UI/telemetri dongusunu bekletmez.
            yonetici = getattr(self, "guncelleme", None)
            if yonetici is None:
                await self._duyur({"tip": "guncelleme_durum",
                                   "hata": "Guncelleme yoneticisi hazir degil"})
            else:
                durum = yonetici.durum()
                if not durum.get("kontrol_edildi"):
                    yonetici.denetle_arka_planda()
                await self._duyur({"tip": "guncelleme_durum", "durum": durum})
        elif komut == "guncelleme_denete":
            yonetici = getattr(self, "guncelleme", None)
            basladi = bool(yonetici and yonetici.denetle_arka_planda())
            await self._duyur({"tip": "guncelleme_sonuc", "islem": "denetle",
                               "basari": basladi,
                               "bilgi": "Surum denetimi baslatildi" if basladi else
                                        "Surum denetimi zaten calisiyor veya hazir degil"})
        elif komut == "guncelleme_servis_yenile":
            # v2.4.163: eski gozetmeni (ilerleme gostermeyen) yenilemek icin
            yonetici = getattr(self, "guncelleme", None)
            basari, bilgi = (yonetici.servisi_yeniden_baslat()
                             if yonetici and hasattr(yonetici, "servisi_yeniden_baslat")
                             else (False, "Guncelleme yoneticisi hazir degil"))
            await self._duyur({"tip": "guncelleme_sonuc", "islem": "servis",
                               "basari": bool(basari), "bilgi": str(bilgi)})
        elif komut in ("guncelleme_uygula", "guncelleme_indir", "guncelleme_kur"):
            # v2.5.30: Dosya tabanli model — tek adim. Calisan surec kendi
            # kodunu degistirmez; gozetmen icin tetik dosyasi yazilir, o da
            # uygulamayi durdurup dosyalari atomik yerlestirip yeniden baslatir.
            # (Eski indir/kur komutlari geriye donuk uyum icin ayni yola gider.)
            yonetici = getattr(self, "guncelleme", None)
            basari, bilgi = (yonetici.guncelle_baslat()
                             if yonetici and hasattr(yonetici, "guncelle_baslat")
                             else (False, "Guncelleme yoneticisi hazir degil"))
            await self._duyur({"tip": "guncelleme_sonuc", "islem": "uygula",
                               "basari": bool(basari), "bilgi": str(bilgi)})
        elif komut == "gorev_yukle" and self.gorev and self.rotalar:
            # v2.4.20: {"tip":"gorev_yukle","sysid":1,"rota_id":2}
            # Gorevi YALNIZCA drona yukler; ucusu baslatmaz.
            try:
                sysid = int(k.get("sysid"))
                rota_id = int(k.get("rota_id"))
            except (TypeError, ValueError):
                return
            rota = next((r for r in self.rotalar.rota_listele()
                         if r["id"] == rota_id), None)
            if rota is None:
                self.konsol("GOREV", f"Rota bulunamadi: #{rota_id}",
                            "hata")
                await self._duyur({"tip": "gorev_yukle_sonuc",
                                   "sysid": sysid, "basari": False,
                                   "bilgi": "rota_yok"})
            else:
                # v2.4.35: gorev durdurulunca ne yapilacagi yukleme
                # aninda secilir (ilaclama gibi operasyonlarda bir
                # gorevde birkac kez batarya degisimi olabilir).
                davranis = str(k.get("durdurma_davranisi")
                               or "bekle").strip()
                if davranis not in ("bekle", "basa_don"):
                    davranis = "bekle"
                basari = self.gorev.yukle(sysid, rota,
                                          durdurma_davranisi=davranis)
                await self._duyur({"tip": "gorev_yukle_sonuc",
                                   "sysid": sysid,
                                   "basari": bool(basari),
                                   "rota_id": rota_id,
                                   "durdurma_davranisi": davranis,
                                   "bilgi": rota.get("isim", "?")})

        elif komut == "gorev_baslat" and self.gorev:
            # v2.4.20: {"tip":"gorev_baslat","sysid":1}
            # Drona YUKLENMIS gorevi baslatir (ARM + AUTO + START).
            # v2.4.145: performans_test yalnız sabit kanat telemetri
            # analiz etiketidir; kontrol parametresi veya uçuş komutu değildir.
            # v2.4.147: sitl_dalis bu katmanda yalnız iletilir; gerçek/sanal
            # ayrımı ve etkin süreç denetimi GorevYoneticisi'nde zorunludur.
            try:
                sysid = int(k.get("sysid"))
            except (TypeError, ValueError):
                return
            basari, bilgi = self.gorev.baslat(
                sysid, performans_test=k.get("performans_test"),
                sitl_dalis=k.get("sitl_dalis"))
            await self._duyur({"tip": "gorev_baslat_sonuc",
                               "sysid": sysid,
                               "basari": bool(basari),
                               "bilgi": str(bilgi)})

        elif komut == "gorev_durdur" and self.gorev:
            # v2.4.35: durdur() artik (basari, mesaj) DONUYOR. Mod gecisi
            # telemetriden dogrulanir; dogrulanamazsa gorev duraklamamis
            # sayilir ve arayuze bildirilir (sessiz basarisizlik yerine).
            try:
                sysid = int(k.get("sysid"))
            except (TypeError, ValueError):
                return
            basari, bilgi = self.gorev.durdur(sysid)
            await self._duyur({"tip": "gorev_durdur_sonuc",
                               "sysid": sysid,
                               "basari": bool(basari),
                               "bilgi": str(bilgi)})

        elif komut == "gorev_devam" and self.gorev:
            try:
                sysid = int(k.get("sysid"))
            except (TypeError, ValueError):
                return
            basari, bilgi = self.gorev.devam(sysid)
            await self._duyur({"tip": "gorev_devam_sonuc",
                               "sysid": sysid,
                               "basari": bool(basari),
                               "bilgi": str(bilgi)})

        elif komut == "gorev_surdur" and self.gorev:
            # v2.4.35: batarya degisimi sonrasi yarim kalmis gorevi
            # kaldigi noktadan surdurur (MISSION_SET_CURRENT + AUTO).
            try:
                sysid = int(k.get("sysid"))
            except (TypeError, ValueError):
                return
            basari, bilgi = self.gorev.surdur(sysid)
            await self._duyur({"tip": "gorev_surdur_sonuc",
                               "sysid": sysid,
                               "basari": bool(basari),
                               "bilgi": str(bilgi)})

        elif komut == "gorev_iptal" and self.gorev:
            # v2.4.18: Gorev tamamen iptal edilir (BRAKE/LOITER +
            # drondaki mission listesi temizlenir)
            try:
                sysid = int(k.get("sysid"))
            except (TypeError, ValueError):
                return
            basari, bilgi = self.gorev.iptal(sysid)
            await self._duyur({"tip": "gorev_iptal_sonuc",
                               "sysid": sysid,
                               "basari": bool(basari),
                               "bilgi": str(bilgi)})

        elif komut == "rota_sil" and self.rotalar:
            try:
                rota_id = int(k.get("id"))
            except (TypeError, ValueError):
                return
            liste = self.rotalar.rota_sil(rota_id)
            if liste is not None:
                self.konsol("ROTA", f"Rota silindi: #{rota_id}", "uyari")
                await self._duyur(
                    {"tip": "rota_listesi",
                     "rotalar": self.rotalar.rota_listele()})
        elif komut == "goruntu_son_kareler":
            dronlar, kareler, hata = await self._goruntu_son_kareler(websocket)
            await websocket.send(json.dumps({
                "tip": "goruntu_son_kareler",
                "basarili": not bool(hata), "hata": hata,
                "dronlar": dronlar, "kareler": kareler,
            }, ensure_ascii=False))

        elif komut == "goruntu_kamera_kaynaklari":
            kopruler, hata = await self._goruntu_kamera_kaynaklari(
                websocket, k.get("ornek_id"))
            await websocket.send(json.dumps({
                "tip": "goruntu_kamera_kaynaklari",
                "basarili": not bool(hata), "hata": hata,
                "kopruler": kopruler,
                "istek_sysid": k.get("istek_sysid"),
                "dron_uid": str(k.get("dron_uid") or "")[:160],
            }, ensure_ascii=False))

        elif komut == "goruntu_kamera_dron_bagla":
            basarili, hata, kameralar = await self._goruntu_kamera_dron_bagla(
                websocket, k)
            await websocket.send(json.dumps({
                "tip": "goruntu_kamera_bag_sonuc",
                "basarili": basarili, "hata": hata,
                "ornek_id": k.get("ornek_id"),
                "kamera_id": k.get("kamera_id"),
                "dron_uid": str(k.get("dron_uid") or "")[:160],
                "kameralar": kameralar,
                "istek_sysid": k.get("istek_sysid"),
            }, ensure_ascii=False))

        elif komut == "kamera_listele" and self.kameralar:
            await websocket.send(json.dumps(
                {"tip": "kamera_listesi",
                 "kameralar": self.kameralar.listele(
                     firma_id=self._ws_firma_id(websocket))}))

        elif komut == "kamera_cihazlari" and self.video_proxy:
            # v2.4.7: DONANIM protokolu icin SUNUCU makinesindeki yerel
            # kamera cihazlari (indeks tabanli; AI boru hattina girer)
            cihazlar = await _db_is_parcasi(
                self.video_proxy.cihaz_listesi)
            await websocket.send(json.dumps(
                {"tip": "kamera_cihazlari", "cihazlar": cihazlar}))

        elif komut == "kamera_kaydet" and self.kameralar:
            # v2.4.181: 'm50' kamerasinda kullanici URL yazmaz — kanal
            # (gorunur/termal) secer, ag/kimlik bilgisi TUM M50 alt
            # yapisina (mevcut m50_baglan akisi) devredilir. Kamera
            # kaydinda yalniz sentinel "m50:<kanal>" saklanir (dji:<sysid>
            # ile ayni desen); gercek RTSP asla DB'ye yazilmaz.
            if str(k.get("protokol") or "").strip().lower() == "m50":
                _m50_kanal = str(k.get("m50_kanal") or "").strip().lower()
                if _m50_kanal not in ("gorunur", "termal"):
                    await self._hata_bildir(
                        websocket, "KAMERA",
                        "M50 kamerasi icin kanal (gorunur/termal) secilmelidir")
                    return
                k = dict(k)
                # v2.4.191: coklu EO — url 'm50:<eo_id>:<kanal>'.
                try:
                    _eo_id = int(k.get("eo_id") or 0)
                except (TypeError, ValueError):
                    _eo_id = 0
                if _eo_id <= 0:
                    _eo = getattr(self, "eo", None)
                    _eo_id = _eo.birincil_id() if _eo is not None else 1
                k["eo_id"] = _eo_id
                k["url"] = "m50:%d:%s" % (_eo_id, _m50_kanal)
                _m50_ip = str(k.get("m50_ip") or "").strip()
                _m50_kul = str(k.get("m50_kullanici") or "").strip()
                _m50_par = str(k.get("m50_parola") or "")
                if _m50_ip or _m50_kul or _m50_par:
                    # Kismi doldurulmus kimlik bilgisi sessizce yok
                    # sayilmaz: ya hepsi eksiksiz girilir ya hic girilmez.
                    try:
                        import ipaddress
                        ipaddress.ip_address(_m50_ip)
                        _m50_ip_gecerli = True
                    except (ValueError, TypeError):
                        _m50_ip_gecerli = False
                    try:
                        _m50_port = int(k.get("m50_port"))
                    except (TypeError, ValueError):
                        _m50_port = 0
                    if not (_m50_ip and _m50_kul and _m50_par and
                            _m50_ip_gecerli and 0 < _m50_port < 65536):
                        await self._hata_bildir(
                            websocket, "KAMERA",
                            "M50 baglantisi icin gecerli IP, port, "
                            "kullanici adi ve parola birlikte girilmelidir")
                        return
                    await self._m50_kopruye(websocket, "baglan", {
                        "ip": _m50_ip, "port": _m50_port,
                        "kullanici": _m50_kul, "parola": _m50_par,
                        "zaman_asimi": 5000,
                    }, k)
            kam_id = k.get("id")
            _fid = self._ws_firma_id(websocket)
            # v2.4.56: kamera hangi kopru makinesinde? Merkez kipinde
            # kopru zorunludur — aksi halde merkez sunucusu kameraya
            # dogrudan ulasmaya calisir ve kullanicinin yerel agindaki
            # kamera erisilemez olur (uctan uca olculdu, bkz.
            # HATA_KOPRU_BAGLANTI.md).
            _kopru = k.get("kopru_ornek_id")
            if kam_id is None:
                if self._merkez_kipinde() and not _kopru:
                    await self._hata_bildir(
                        websocket, "KAMERA",
                        "Kamera icin kopru secilmelidir")
                    return
                if _kopru and not self._kopru_sahibi_mi(_kopru, _fid):
                    await self._hata_bildir(
                        websocket, "KAMERA", "Kopru bulunamadi")
                    return
                yeni_id, liste = self.kameralar.ekle(
                    k.get("isim"), k.get("protokol"), k.get("url"),
                    k.get("lokasyon_id"), k.get("ai_gorevler", ""),
                    firma_id=_fid, kopru_ornek_id=_kopru,
                    ai_hassasiyet=k.get("ai_hassasiyet", ""),
                    fps=k.get("fps"), genislik=k.get("genislik"))
                if yeni_id is not None:
                    _dron_uid = str(k.get("dron_uid") or "").strip()[:80]
                    if _dron_uid:
                        self.kameralar.dron_bagla(yeni_id, _dron_uid)
                        liste = self.kameralar.listele(firma_id=_fid)
                    # v2.5.21: yerel AI angajman kalibrasyonu (kamera tipi
                    # + sabit/dron konum-aci alanlari). Kalibrasyon eksikse
                    # kalibre=0 kalir ve hedef angajmana ALINAMAZ.
                    _kl = self.kameralar.kalibrasyon_kaydet(
                        yeni_id, k, firma_id=_fid)
                    if _kl is not None:
                        liste = _kl
                    self.konsol("KAMERA",
                                f"Kamera eklendi: "
                                f"{str(k.get('isim'))[:60]} (#{yeni_id})",
                                "basari")
                    # v2.4.61: kayit SAHAYA da iletilir. Kopru kamerayi
                    # kendi defterinde bulamazsa akisi acamaz; kayit
                    # yalniz merkezde kalirsa "kaydettim ama goruntu
                    # gelmiyor" durumu dogar.
                    await self._kamera_sahaya_ilet(websocket, yeni_id)
                    await self._kamera_listesi_duyur(yeni_id)
                    # v2.4.8: AI gorevleri seciliyse izlemeyi otomatik
                    # baslat (kullanicinin ayrica baslatmasi gerekmez).
                    await self._ai_izleme_esitle(yeni_id)
                else:
                    self.konsol("KAMERA", "Kamera eklenemedi "
                                "(gecersiz parametre)", "hata")
            else:
                try:
                    kam_id = int(kam_id)
                except (TypeError, ValueError):
                    return
                if _kopru and not self._kopru_sahibi_mi(_kopru, _fid):
                    await self._hata_bildir(
                        websocket, "KAMERA", "Kopru bulunamadi")
                    return
                # v2.5.27: Kaynak (url/protokol) değişti mi? Değişmediyse
                # (ör. yalnız AI ayarı/hassasiyet değişikliği) canlı yayını
                # DURDURMA. Aksi halde her AI ayar değişiminde webcam
                # (cv2.VideoCapture) durdurulup yeniden açılıyor; Windows'ta
                # bu hızlı aç-kapa yerel bellek bozulmasına (0xC0000374)
                # yol açıp Merkez'i çökertiyordu.
                _eski_kam = self.kameralar.bul(kam_id) or {}
                _eski_url = str(_eski_kam.get("url") or "")
                _eski_prot = str(_eski_kam.get("protokol") or "")
                _eski_fps = _eski_kam.get("fps")
                _eski_gen = _eski_kam.get("genislik")
                liste = self.kameralar.guncelle(
                    kam_id, k.get("isim"), k.get("protokol"),
                    k.get("url"), k.get("lokasyon_id"),
                    k.get("ai_gorevler", ""),
                    firma_id=_fid, kopru_ornek_id=_kopru,
                    ai_hassasiyet=k.get("ai_hassasiyet", None),
                    fps=k.get("fps"), genislik=k.get("genislik"))
                if liste is not None:
                    # v2.4.193: FPS tavani da "kaynak degisti" sayilir;
                    # yeni hiz ancak yayin yeniden kurulunca uygulanir.
                    _fps_degisti = False
                    if k.get("fps") is not None:
                        try:
                            _fps_degisti = (int(k.get("fps")) !=
                                            int(_eski_fps or 15))
                        except (TypeError, ValueError):
                            _fps_degisti = False
                    # v2.4.207: cikti genisligi de yayini yeniden kurar
                    if k.get("genislik") is not None:
                        try:
                            if int(k.get("genislik")) != int(_eski_gen or 960):
                                _fps_degisti = True
                        except (TypeError, ValueError):
                            pass
                    _kaynak_degisti = (str(k.get("url") or "") != _eski_url or
                                       str(k.get("protokol") or "") != _eski_prot or
                                       _fps_degisti)
                    _dron_uid = str(k.get("dron_uid") or "").strip()[:80]
                    self.kameralar.dron_bagla(kam_id, _dron_uid)
                    # v2.5.21: yerel AI angajman kalibrasyonunu guncelle.
                    # v2.4.161: YALNIZ istek kalibrasyon tasiyorsa. AI ayar
                    # paneli kalibrasyon gondermez; eskiden her AI ayar
                    # degisikligi kalibrasyonu silip kalibre=0 yapiyordu.
                    if "kamera_tipi" in k:
                        self.kameralar.kalibrasyon_kaydet(kam_id, k, firma_id=_fid)
                    liste = self.kameralar.listele(firma_id=_fid)
                    # URL/protokol DEĞİŞTİYSE aktif proxy'yi kapat; aksi halde
                    # (AI-only değişiklik) capture'a DOKUNMA (bkz. yukarıdaki not).
                    if self.video_proxy and _kaynak_degisti:
                        self.video_proxy.yayin_durdur(kam_id)
                    self.konsol("KAMERA",
                                f"Kamera guncellendi: #{kam_id}", "basari")
                    # v2.4.61: guncel kaydi sahaya ilet (URL/protokol
                    # degismis olabilir; eski kayitla akis acilirsa
                    # kullanici degisikligin uygulanmadigini sanar).
                    await self._kamera_sahaya_ilet(websocket, kam_id)
                    await self._kamera_listesi_duyur()
                    # v2.4.8: AI gorevlerine gore izlemeyi esitle
                    # (gorev secildiyse baslat/yenile, bosaldiysa durdur).
                    await self._ai_izleme_esitle(kam_id)
                else:
                    self.konsol("KAMERA",
                                f"Kamera guncellenemedi: #{kam_id}",
                                "hata")

        elif komut == "kamera_sil" and self.kameralar:
            try:
                kam_id = int(k.get("id"))
            except (TypeError, ValueError):
                return
            liste = self.kameralar.sil(
                kam_id, firma_id=self._ws_firma_id(websocket))
            if liste is not None:
                if self.video_proxy:
                    self.video_proxy.yayin_durdur(kam_id)
                # v2.4.8: silinen kameranin AI izlemesini de durdur
                if self.ai_yonetici:
                    try:
                        await _db_is_parcasi(
                            self.ai_yonetici.izleme_durdur, kam_id)
                        await self._duyur(
                            {"tip": "ai_izleme_listesi",
                             "izlemeler":
                                 self.ai_yonetici.izleme_listesi()})
                    except Exception:
                        pass
                self.konsol("KAMERA", f"Kamera silindi: #{kam_id}",
                            "uyari")
                await self._kamera_listesi_duyur()

        elif komut == "kamera_dron_bagla" and self.kameralar:
            # v2.4.2: {"tip":"kamera_dron_bagla","id":N,"dron_uid":".."}
            # dron_uid bos string -> kamera-dron bagi cozulur.
            try:
                kam_id = int(k.get("id"))
            except (TypeError, ValueError):
                return
            uid = str(k.get("dron_uid") or "")
            liste = self.kameralar.dron_bagla(kam_id, uid)
            if liste is not None:
                if uid:
                    self.konsol("KAMERA",
                                f"Kamera #{kam_id} drona baglandi"
                                f" ({uid[:40]})", "basari")
                else:
                    self.konsol("KAMERA",
                                f"Kamera #{kam_id} dron bagi cozuldu",
                                "uyari")
                await self._duyur(
                    {"tip": "kamera_listesi", "kameralar": liste})

        elif komut == "dji_cihazlar":
            # {"tip":"dji_cihazlar"} -> bagli DJI dronlarin listesi
            cihazlar = (self.dji_kopru.cihazlar()
                        if self.dji_kopru else [])
            await websocket.send(json.dumps(
                {"tip": "dji_cihazlar", "cihazlar": cihazlar}))

        elif komut == "kamera_proxy_durdur" and self.video_proxy:
            # Istemci izlemeyi durdurdu; RTSP/RTP kaynak surecini kapat
            try:
                kam_id = int(k.get("id"))
            except (TypeError, ValueError):
                return
            self.video_proxy.yayin_durdur(kam_id)

        # ==============================================================
        # v2.4.0: AI KATMANI KOMUTLARI
        # ==============================================================
        elif komut == "ai_sunucu_listele" and self.ai_yonetici:
            await websocket.send(json.dumps(
                {"tip": "ai_sunucu_listesi",
                 "sunucular": self.ai_yonetici.listele(
                     firma_id=self._ws_firma_id(websocket))}))

        elif komut == "ai_sunucu_kaydet" and self.ai_yonetici:
            if not await self._izin_var(websocket, "ai",
                                        "sunucu_yonetimi",
                                        "AI sunucu kaydi"):
                return
            # v2.4.45: SSH alanlari yalniz istemci gonderirse yazilir.
            # `ssh_sifre_koru` ise: sifre alani bos gonderildiginde
            # kayitli sifre SILINMEZ (duzenleme ekrani sifreyi bos
            # gosterir; kullanici sifreyi degistirmek istemiyorsa
            # bos birakip kaydedebilmelidir).
            _ssh = None
            if isinstance(k.get("ssh"), dict):
                _ssh = dict(k["ssh"])
                if not (_ssh.get("sifre") or "").strip() \
                        and _ssh.get("sifre_koru"):
                    try:
                        _eski = self.ai_yonetici._sunucu_kaydi(k.get("id"))
                    except Exception:
                        _eski = None
                    if _eski:
                        _ssh["sifre"] = _eski.get("ssh_sifre") or ""
                _ssh.pop("sifre_koru", None)
            # v2.4.56: AI bilgisayari hangi kopru makinesinde? Merkez
            # kipinde kopru zorunludur; aksi halde merkez sunucusu
            # kullanicinin yerel agindaki AI bilgisayarina dogrudan
            # ulasmaya calisir ve hicbir zaman erisemez.
            _fid = self._ws_firma_id(websocket)
            _kopru = k.get("kopru_ornek_id")
            if k.get("id") is None and self._merkez_kipinde() and not _kopru:
                await self._hata_bildir(
                    websocket, "AI", "AI bilgisayari icin kopru secilmelidir")
                return
            if _kopru and not self._kopru_sahibi_mi(_kopru, _fid):
                await self._hata_bildir(websocket, "AI", "Kopru bulunamadi")
                return
            if k.get("id") is not None and not self.ai_yonetici.sahibi_mi(
                    k.get("id"), _fid):
                await self._hata_bildir(
                    websocket, "AI", "AI bilgisayari bulunamadi")
                return
            liste = self.ai_yonetici.kaydet(
                k.get("id"), k.get("ad"),
                k.get("sunucu_tip") or k.get("tip"), k.get("host"),
                k.get("port"), k.get("kapasite"), k.get("notlar", ""),
                ssh=_ssh, firma_id=_fid, kopru_ornek_id=_kopru)
            if liste is not None:
                self._pilot_log(websocket, "ai", "ai_sunucu_kaydet",
                                str(k.get("ad"))[:60])
                self.konsol("AI", f"AI sunucusu kaydedildi:"
                            f" {str(k.get('ad'))[:60]}", "basari")
                await self._ai_sunucu_listesi_duyur()

        elif komut == "ai_sunucu_sil" and self.ai_yonetici:
            if not await self._izin_var(websocket, "ai",
                                        "sunucu_yonetimi",
                                        "AI sunucu silme"):
                return
            try:
                liste = self.ai_yonetici.sil(
                    int(k.get("id")),
                    firma_id=self._ws_firma_id(websocket))
            except (TypeError, ValueError):
                return
            if liste is None:
                await self._hata_bildir(
                    websocket, "AI", "AI bilgisayari bulunamadi")
                return
            self.konsol("AI", f"AI sunucusu silindi: #{k.get('id')}",
                        "basari")
            await self._ai_sunucu_listesi_duyur()

        # --------------------------------------------------------------
        # v2.4.45: AI bilgisayarini SSH ile uzaktan baslatma + konsol
        # --------------------------------------------------------------
        elif komut == "ai_ssh_baslat" and self.ai_yonetici:
            if not await self._izin_var(websocket, "ai",
                                        "sunucu_yonetimi",
                                        "AI sunucusu SSH baslatma"):
                return
            if self.ai_ssh is None:
                await websocket.send(json.dumps(
                    {"tip": "ai_ssh_durum", "sunucu_id": k.get("id"),
                     "calisiyor": False,
                     "hata": "SSH yoneticisi kullanilamiyor."}))
                return
            try:
                kayit = self.ai_yonetici._sunucu_kaydi(int(k.get("id")))
            except (TypeError, ValueError):
                return
            if not kayit:
                await websocket.send(json.dumps(
                    {"tip": "ai_ssh_durum", "sunucu_id": k.get("id"),
                     "calisiyor": False,
                     "hata": "AI bilgisayari bulunamadi."}))
                return
            # Kayitli sifre varsa kullanilir; istemci gecici sifre de
            # gonderebilir (kaydedilmez).
            sifre = str(k.get("sifre") or kayit.get("ssh_sifre") or "")

            # KOPRUYE BAGLI KAYIT: SSH oturumu KOPRU makinesinde acilir.
            #
            # Kullanicinin AI bilgisayarlari ozel agdadir (192.168.1.x).
            # GOKTUNGU merkezde kostugu icin merkez sunucusu bu adrese
            # hicbir kosulda erisemez; burada acilan SSH "Connection
            # timed out" ile biter. Kaydin sahibi kopru ise komut o
            # makineye gonderilir.
            if self._kopru_uzerinde_mi(kayit):
                sonuc, hata = await self._kopruye_sor_async(
                    kayit.get("kopru_ornek_id"), websocket,
                    "ai_ssh_baslat",
                    {"kayit": self._ai_kayit_kopruye(kayit),
                     "sifre": sifre})
                self._pilot_log(websocket, "ai", "ai_ssh_baslat",
                                str(kayit.get("ad"))[:60])
                if hata or not (sonuc or {}).get("tamam"):
                    await websocket.send(json.dumps(
                        {"tip": "ai_ssh_durum", "sunucu_id": kayit["id"],
                         "calisiyor": False,
                         "hata": hata or (sonuc or {}).get("hata")
                         or "Kopru SSH oturumunu baslatamadi."}))
                else:
                    await websocket.send(json.dumps(
                        {"tip": "ai_ssh_durum", "sunucu_id": kayit["id"],
                         "calisiyor": True, "hata": ""}))
                return

            ok, hata = await asyncio.get_running_loop().run_in_executor(None, _db_iade_ederek, self.ai_ssh.baslat, kayit, sifre)
            self._pilot_log(websocket, "ai", "ai_ssh_baslat",
                            str(kayit.get("ad"))[:60])
            if not ok:
                await websocket.send(json.dumps(
                    {"tip": "ai_ssh_durum", "sunucu_id": kayit["id"],
                     "calisiyor": False, "hata": hata}))

        elif komut == "ai_ssh_durdur" and self.ai_yonetici:
            if not await self._izin_var(websocket, "ai",
                                        "sunucu_yonetimi",
                                        "AI sunucusu SSH durdurma"):
                return
            try:
                sid = int(k.get("id"))
            except (TypeError, ValueError):
                return
            kayit = self.ai_yonetici._sunucu_kaydi(sid)
            if kayit and self._kopru_uzerinde_mi(kayit):
                sonuc, hata = await self._kopruye_sor_async(
                    kayit.get("kopru_ornek_id"), websocket,
                    "ai_ssh_durdur", {"id": sid})
                self._pilot_log(websocket, "ai", "ai_ssh_durdur", str(sid))
                if hata or not (sonuc or {}).get("tamam"):
                    await websocket.send(json.dumps(
                        {"tip": "ai_ssh_durum", "sunucu_id": sid,
                         "calisiyor": False,
                         "hata": hata or (sonuc or {}).get("hata")
                         or "Calisan oturum yok."}))
                else:
                    await websocket.send(json.dumps(
                        {"tip": "ai_ssh_durum", "sunucu_id": sid,
                         "calisiyor": False, "hata": ""}))
                return
            if self.ai_ssh is None:
                return
            ok, hata = self.ai_ssh.durdur(sid)
            self._pilot_log(websocket, "ai", "ai_ssh_durdur", str(sid))
            if not ok:
                await websocket.send(json.dumps(
                    {"tip": "ai_ssh_durum", "sunucu_id": sid,
                     "calisiyor": False, "hata": hata}))

        elif komut == "ai_ssh_gecmis":
            # Konsol penceresi acildiginda gecmisi ister (tampon).
            try:
                sid = int(k.get("id"))
            except (TypeError, ValueError):
                return
            kayit = (self.ai_yonetici._sunucu_kaydi(sid)
                     if self.ai_yonetici else None)
            if kayit and self._kopru_uzerinde_mi(kayit):
                # Satirlar KOPRUDE tutulur ve buradan CEKILIR. Kopru
                # kendiliginden satir itmez: konsol penceresi kapaliyken
                # bant genisligi harcanmamalidir.
                sonuc, hata = await self._kopruye_sor_async(
                    kayit.get("kopru_ornek_id"), websocket,
                    "ai_ssh_gecmis", {"id": sid})
                if hata:
                    await websocket.send(json.dumps(
                        {"tip": "ai_ssh_gecmis", "sunucu_id": sid,
                         "calisiyor": False, "satirlar": [],
                         "hata": hata}))
                    return
                d = dict(sonuc or {})
                d["tip"] = "ai_ssh_gecmis"
                d["sunucu_id"] = sid
                await websocket.send(json.dumps(d))
                return
            if self.ai_ssh is None:
                await websocket.send(json.dumps(
                    {"tip": "ai_ssh_gecmis", "sunucu_id": sid,
                     "calisiyor": False, "satirlar": []}))
                return
            d = self.ai_ssh.gecmis(sid)
            d["tip"] = "ai_ssh_gecmis"
            await websocket.send(json.dumps(d))

        elif komut == "ai_izleme_baslat" and self.ai_yonetici:
            if not await self._izin_var(websocket, "ai",
                                        "izleme",
                                        "AI izleme baslatma"):
                return
            kamera = (self.kameralar.bul(k.get("kamera_id"))
                      if self.kameralar else None)
            if not kamera:
                return
            # v2.4.7: TUM kaynaklar (webcam/DONANIM dahil) ana sunucunun
            # MJPEG proxy'sinden (8801) okunur — isci 'gcs_proxy'
            # protokoluyle /kamera/<id> yolunu kendi ana_url hostuna
            # gore cozer. Boylece tek FFmpeg/yakalama sureci calisir.
            sonuc = self.ai_yonetici.izleme_baslat(
                kamera["id"], "/kamera/%s" % kamera["id"], "gcs_proxy",
                gorevler=kamera.get("ai_gorevler", "") or "")
            if sonuc.get("tamam"):
                self._pilot_log(websocket, "ai", "ai_izleme_baslat",
                                f"kamera #{kamera['id']}")
            else:
                self.konsol("AI", f"Izleme baslatilamadi:"
                            f" {sonuc.get('hata', '')}", "hata")
            await self._duyur(
                {"tip": "ai_izleme_listesi",
                 "izlemeler": self.ai_yonetici.izleme_listesi()})

        elif komut == "ai_izleme_durdur" and self.ai_yonetici:
            if not await self._izin_var(websocket, "ai",
                                        "izleme",
                                        "AI izleme durdurma"):
                return
            try:
                self.ai_yonetici.izleme_durdur(int(k.get("kamera_id")))
            except (TypeError, ValueError):
                return
            self._pilot_log(websocket, "ai", "ai_izleme_durdur",
                            f"kamera #{k.get('kamera_id')}")
            await self._duyur(
                {"tip": "ai_izleme_listesi",
                 "izlemeler": self.ai_yonetici.izleme_listesi()})

        elif komut == "ai_izleme_listele" and self.ai_yonetici:
            await websocket.send(json.dumps(
                {"tip": "ai_izleme_listesi",
                 "izlemeler": self.ai_yonetici.izleme_listesi()}))

        # --- v2.4.2: Hedef takibi (tracking) + dron angajmani ---
        elif komut == "ai_track_baslat" and self.ai_yonetici:
            if not await self._izin_var(websocket, "ai",
                                        "izleme",
                                        "AI hedef takibi"):
                return
            try:
                kamera_id = int(k.get("kamera_id", 0))
                sysid = int(k.get("sysid", 0))
            except (TypeError, ValueError):
                return
            tur = str(k.get("tur", ""))
            kutu = k.get("kutu") or None
            # v2.4.173: istemci secim ani (ayni makine saati) — isci
            # kutuyu O ANIN karesine oturtup bugune "sarar" (hizli
            # hedefte kutunun geriden gelmesini onler).
            try:
                sec_ts = float(k.get("ts") or 0) or None
            except (TypeError, ValueError):
                sec_ts = None
            # v2.4.174 OLCULEN KUSUR: `track_baslat` -> `_http()` AI
            # iscisine SENKRON urllib istegi atar (zamanasimi 6 sn).
            # Dogrudan cagrilinca bu coroutine asyncio DONGUSUNU BLOKE
            # ediyordu; isci yavas cevap verirse (CSRT sarma, meşgul CPU)
            # TUM istemcilerin telemetri/WS trafigi donuyordu. Ayri
            # is parcacigina alindi; sunucu artik hicbir sekilde kilitlenmez.
            sonuc = await asyncio.to_thread(
                self.ai_yonetici.track_baslat, kamera_id, tur, kutu, sec_ts)
            if sonuc.get("tamam"):
                self._pilot_log(websocket, "ai", "ai_track_baslat",
                                f"kamera #{kamera_id} tur={tur}"
                                f" dron={sysid}")
                # IS93-ANGAJMAN-GORUNTU: `ai_takip` angajman cagrisi KALDIRILDI.
                # Gerekce (olculdu, is_merkez/BULGU_AI_TAKIP.md):
                #   1. `ai_yonetici` Is 71'de bos omurgaya cevrildi;
                #      `son_takip_konum` None donuyor ve angajman.py
                #      icindeki unpack TypeError firlatiyordu. Hata
                #      `except` ile yutuluyor, dal sessizce olu kaliyordu.
                #   2. Calissaydi bile hedef konumu olarak KAMERANIN
                #      konumunu donduruyordu (+15 m). Saldiran dron
                #      hedefe degil kameranin diregine ucardi.
                # Yerine: Goruntu Koprusu hedefleri `goruntu` tipiyle
                # angajmana girer; konum merkezde kalibrasyondan cozulur.
                if sysid:
                    self.konsol("AI",
                                "Kamera takibinden dogrudan angajman"
                                " kaldirildi. Goruntu Koprusu hedef"
                                " listesinden angajman baslatin.",
                                "uyari")
            else:
                self.konsol("AI", f"Takip baslatilamadi:"
                            f" {sonuc.get('hata', '')}", "hata")
            await websocket.send(json.dumps(
                {"tip": "ai_takip_sonuc", "kamera_id": kamera_id,
                 "tamam": bool(sonuc.get("tamam")),
                 "hata": sonuc.get("hata", "")}))

        elif komut == "ai_track_durdur" and self.ai_yonetici:
            if not await self._izin_var(websocket, "ai",
                                        "izleme",
                                        "AI hedef takibi durdurma"):
                return
            try:
                kamera_id = int(k.get("kamera_id", 0))
            except (TypeError, ValueError):
                return
            # v2.4.174: ai_track_baslat ile ayni gerekce — senkron HTTP
            # cagrisi asyncio dongusunu bloklamasin.
            await asyncio.to_thread(self.ai_yonetici.track_durdur, kamera_id)
            sysid = k.get("sysid")
            if sysid and self.angajman:
                try:
                    self.angajman.durdur(int(sysid))
                    await self._duyur({"tip": "angajman", "durum": {
                        "saldiran_sysid": int(sysid), "aktif": False}})
                except (TypeError, ValueError):
                    pass
            self._pilot_log(websocket, "ai", "ai_track_durdur",
                            f"kamera #{kamera_id}")

        # --- Kutuphane: Kisiler ---
        elif komut == "kisi_listele" and self.kisiler:
            await websocket.send(json.dumps(
                {"tip": "kisi_listesi",
                 "kisiler": self.kisiler.listele()}))

        elif komut == "kisi_kaydet" and self.kisiler:
            if not await self._izin_var(websocket, "ai",
                                        "kutuphane_yonetimi", "Kisi kaydi"):
                return
            liste = self.kisiler.kaydet(k.get("id"), k.get("ad"),
                                        k.get("seviye"),
                                        k.get("notlar", ""))
            if liste is not None:
                self._pilot_log(websocket, "ai", "kisi_kaydet",
                                str(k.get("ad"))[:60])
                if self.ai_yonetici:
                    self.ai_yonetici.yuz_onbellek_sifirla()
                await self._duyur({"tip": "kisi_listesi",
                                   "kisiler": liste})

        elif komut == "kisi_sil" and self.kisiler:
            if not await self._izin_var(websocket, "ai",
                                        "kutuphane_yonetimi", "Kisi silme"):
                return
            try:
                liste = self.kisiler.sil(int(k.get("id")))
            except (TypeError, ValueError):
                return
            if self.ai_yonetici:
                self.ai_yonetici.yuz_onbellek_sifirla()
            await self._duyur({"tip": "kisi_listesi", "kisiler": liste})

        elif komut == "kisi_yuz_ekle" and self.kisiler:
            if not await self._izin_var(websocket, "ai",
                                        "kutuphane_yonetimi",
                                        "Yuz kaydi ekleme"):
                return
            foto = k.get("foto_b64", "")
            embedding = ""
            hata = ""
            if self.ai_yonetici:
                sonuc = self.ai_yonetici.embed_hesapla(foto)
                if sonuc.get("tamam"):
                    embedding = sonuc.get("embedding", "")
                else:
                    hata = sonuc.get("hata", "")
            if not embedding:
                await websocket.send(json.dumps(
                    {"tip": "kisi_yuz_sonuc", "tamam": False,
                     "hata": hata or "Yuz embeddingi hesaplanamadi"}))
                return
            try:
                liste = self.kisiler.yuz_ekle(int(k.get("kisi_id")),
                                              foto, embedding)
            except (TypeError, ValueError):
                return
            if liste is None:
                await websocket.send(json.dumps(
                    {"tip": "kisi_yuz_sonuc", "tamam": False,
                     "hata": "Fotograf kaydedilemedi"}))
                return
            if self.ai_yonetici:
                self.ai_yonetici.yuz_onbellek_sifirla()
            self._pilot_log(websocket, "ai", "kisi_yuz_ekle",
                            f"kisi #{k.get('kisi_id')}")
            await websocket.send(json.dumps(
                {"tip": "kisi_yuz_sonuc", "tamam": True}))
            await self._duyur({"tip": "kisi_listesi", "kisiler": liste})

        elif komut == "kisi_yuz_sil" and self.kisiler:
            if not await self._izin_var(websocket, "ai",
                                        "kutuphane_yonetimi",
                                        "Yuz kaydi silme"):
                return
            try:
                liste = self.kisiler.yuz_sil(int(k.get("yuz_id")))
            except (TypeError, ValueError):
                return
            if self.ai_yonetici:
                self.ai_yonetici.yuz_onbellek_sifirla()
            await self._duyur({"tip": "kisi_listesi", "kisiler": liste})

        # --- Kutuphane: Araclar ---
        elif komut == "arac_listele" and self.araclar:
            await websocket.send(json.dumps(
                {"tip": "arac_listesi",
                 "araclar": self.araclar.listele()}))

        elif komut == "arac_kaydet" and self.araclar:
            if not await self._izin_var(websocket, "ai",
                                        "kutuphane_yonetimi", "Arac kaydi"):
                return
            liste = self.araclar.kaydet(
                k.get("id"), k.get("plaka"), k.get("marka", ""),
                k.get("model", ""), k.get("renk", ""),
                k.get("seviye", ""), k.get("notlar", ""))
            if liste is not None:
                self._pilot_log(websocket, "ai", "arac_kaydet",
                                str(k.get("plaka"))[:20])
                if self.ai_yonetici:
                    self.ai_yonetici.yuz_onbellek_sifirla()
                await self._duyur({"tip": "arac_listesi",
                                   "araclar": liste})

        elif komut == "arac_sil" and self.araclar:
            if not await self._izin_var(websocket, "ai",
                                        "kutuphane_yonetimi", "Arac silme"):
                return
            try:
                liste = self.araclar.sil(int(k.get("id")))
            except (TypeError, ValueError):
                return
            if self.ai_yonetici:
                self.ai_yonetici.yuz_onbellek_sifirla()
            await self._duyur({"tip": "arac_listesi", "araclar": liste})

        # --- Tespit gecmisi + kayitsizlar ---
        elif komut == "ai_tespit_gecmis" and self.ai_yonetici:
            await websocket.send(json.dumps(
                {"tip": "ai_tespit_gecmisi",
                 "tespitler": self.ai_yonetici.gecmis(
                     baslangic=k.get("baslangic"),
                     bitis=k.get("bitis"),
                     kamera_id=k.get("kamera_id"),
                     tur=k.get("tur"),
                     kisi_id=k.get("kisi_id"),
                     sadece_kayitsiz=bool(k.get("sadece_kayitsiz")),
                     limit=k.get("limit", 200))}))

        elif komut == "ai_tespit_islem" and self.ai_yonetici:
            if not await self._izin_var(websocket, "ai",
                                        "tespit_yonetimi",
                                        "Tespit isleme"):
                return
            islem = k.get("islem", "")
            try:
                tespit_id = int(k.get("tespit_id"))
            except (TypeError, ValueError):
                return
            if islem == "kisi_ata":
                self.ai_yonetici.tespit_kisi_ata(tespit_id,
                                                 k.get("kisi_id"))
            elif islem == "arac_ata":
                self.ai_yonetici.tespit_arac_ata(tespit_id,
                                                 k.get("arac_id"))
            elif islem == "yoksay":
                self.ai_yonetici.tespit_islenmis(tespit_id)
            await websocket.send(json.dumps(
                {"tip": "ai_tespit_islem_sonuc", "tamam": True,
                 "tespit_id": tespit_id, "islem": islem}))

        elif komut == "kayit_baslat":
            ad = self.kayit.kayit_baslat()
            self.konsol("KAYIT", f"Radar kaydi basladi: {ad}", "basari")

        elif komut == "kayit_durdur":
            ozet = self.kayit.ozet()
            self.kayit.kayit_durdur()
            self.konsol("KAYIT",
                        f"Kayit durduruldu: {ozet['dosya']} "
                        f"({ozet['kare']} kare, {ozet['sure']:.0f} sn)",
                        "basari")
            await websocket.send(json.dumps(
                {"tip": "kayit_listesi", "kayitlar": self.kayit.listesi()}))

        elif komut == "kayit_liste":
            await websocket.send(json.dumps(
                {"tip": "kayit_listesi", "kayitlar": self.kayit.listesi()}))

        elif komut == "kayit_sil":
            self.kayit.sil(k.get("dosya", ""))
            await websocket.send(json.dumps(
                {"tip": "kayit_listesi", "kayitlar": self.kayit.listesi()}))

        elif komut == "replay_baslat":
            await self.kayit.replay_baslat(k.get("dosya", ""),
                                           k.get("hiz", 1.0),
                                           self.istemciler)

        elif komut == "replay_durdur":
            self.kayit.replay_durdur()

        elif komut == "replay_hiz":
            self.kayit.replay_hiz(k.get("hiz", 1.0))

        elif komut == "etiket_ekle" and self.etiket:
            ok, mesaj = self.etiket.ekle(
                k.get("dosya", ""), k.get("iz_id"), k.get("sinif", ""),
                guven=k.get("guven", "kesin"),
                kaynak=k.get("kaynak", "operator"),
                notlar=k.get("notlar", ""),
                baslangic_t=k.get("baslangic_t"),
                bitis_t=k.get("bitis_t"))
            self.konsol("ETIKET", mesaj, "basari" if ok else "hata")
            await websocket.send(json.dumps({
                "tip": "etiket_listesi",
                "dosya": os.path.basename(str(k.get("dosya", ""))),
                "etiketler": self.etiket.dosya_etiketleri(
                    k.get("dosya", "")),
                "ozet": self.etiket.ozet()}))

        elif komut == "etiket_sil" and self.etiket:
            ok, mesaj = self.etiket.sil(k.get("dosya", ""), k.get("iz_id"))
            self.konsol("ETIKET", mesaj, "uyari" if ok else "hata")
            await websocket.send(json.dumps({
                "tip": "etiket_listesi",
                "dosya": os.path.basename(str(k.get("dosya", ""))),
                "etiketler": self.etiket.dosya_etiketleri(
                    k.get("dosya", "")),
                "ozet": self.etiket.ozet()}))

        elif komut == "etiket_liste" and self.etiket:
            await websocket.send(json.dumps({
                "tip": "etiket_listesi",
                "dosya": os.path.basename(str(k.get("dosya", ""))),
                "etiketler": self.etiket.dosya_etiketleri(
                    k.get("dosya", "")),
                "ozet": self.etiket.ozet()}))

        elif komut == "tema":
            t = k.get("tema")
            if t in ("koyu", "acik"):
                yeni = self.ayarlar.kaydet({"tema": t})
                await self._duyur({"tip": "ayarlar", "ayarlar": self.ayarlar.yayin(yeni)})

        elif komut == "ayar_kaydet":
            try:
                lat = float(k["lat"])
                lon = float(k["lon"])
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError("aralik disi")
            except (KeyError, TypeError, ValueError):
                return
            yeni = self.ayarlar.kaydet(
                {"merkez_lat": lat, "merkez_lon": lon})
            await self._duyur({"tip": "ayarlar", "ayarlar": self.ayarlar.yayin(yeni)})
        elif komut == "servis_durum":
            # v2.4.49: {"tip":"servis_durum"}
            # Program Ayarlari servis bolumu bunu acilista ve her
            # eylemden sonra cagirir. OKUMA islemidir; her rol
            # gorebilir (bilgi gostermek zarar vermez), ancak EYLEM
            # komutlari yalniz yoneticiye aciktir.
            #
            # v2.4.57 MERKEZ KIPI: merkezde servis yonetimi ARAYUZE
            # KAPALIDIR. `goktungu-app` birimi operatorun sunucusunda
            # calisir ve tum firmalar TEK surece baglidir; bir firmanin
            # yoneticisinin "Durdur" demesi butun kiracilarin ucusunu
            # keser. Program Ayarlari menusu de bu yuzden merkezde
            # gizlendi (bkz. js/program_ayar.js); bu dal, menu gizlemesi
            # atlansa bile komutun etkisiz kalmasini saglar.
            #
            # `destekli: False` donulur: arayuzun ZATEN bildigi ve
            # dogru isledigi yanit bicimi bu (bolum cizilmez, guc
            # dugmeleri gizli kalir). Yeni bir yanit tipi eklemek
            # istemci tarafinda ele alinmayan dal yaratirdi.
            if self._merkez_kipinde():
                await websocket.send(json.dumps(
                    {"tip": "servis_durum", "destekli": False,
                     "merkez_kipi": True,
                     "hata": "Bu GOKTUNGU ornegi merkezde calisiyor. "
                             "Servis yonetimi merkez operatoru "
                             "tarafindan yapilir."}))
                return
            if self.servis is None:
                await websocket.send(json.dumps(
                    {"tip": "servis_durum", "destekli": False,
                     "hata": "Servis yonetimi bu isletim sisteminde "
                             "kullanilamaz (systemd gerekir)."}))
                return
            p = self._pilot_bilgi(websocket) or {}
            ozet = await asyncio.get_running_loop().run_in_executor(None, _db_iade_ederek, self.servis.ozet)
            ozet["tip"] = "servis_durum"
            ozet["destekli"] = True
            # Arayuz dugmeleri buna gore etkin/pasif olur: yonetici
            # degilse eylem dugmeleri hic etkinlesmez.
            ozet["yetkili"] = (p.get("rol") == "yonetici")
            await websocket.send(json.dumps(ozet))
        elif komut == "servis_gunluk":
            # v2.4.49: {"tip":"servis_gunluk","satir":80}
            if self.servis is None:
                return
            p = self._pilot_bilgi(websocket) or {}
            if p.get("rol") != "yonetici":
                # Gunluk sistem ayrintilari icerir; yoneticiye ozel.
                await websocket.send(json.dumps(
                    {"tip": "servis_gunluk", "basarili": False,
                     "hata": "Servis gunlugunu yalnizca yonetici "
                             "gorebilir."}))
                return
            try:
                satir = max(10, min(int(k.get("satir") or 80), 500))
            except (TypeError, ValueError):
                satir = 80
            # servis.gunluk() -> {"tamam":bool,"satirlar":[...],"hata":str}
            g = await asyncio.get_running_loop().run_in_executor(None, _db_iade_ederek, self.servis.gunluk, satir)
            await websocket.send(json.dumps(
                {"tip": "servis_gunluk",
                 "basarili": bool(g.get("tamam")),
                 "satirlar": g.get("satirlar") or [],
                 "hata": g.get("hata", "")}))
        elif komut == "servis_eylem":
            # v2.4.49: {"tip":"servis_eylem","ad":"baslat|durdur|
            #            yeniden|etkinlestir|devredisi"}
            #
            # v2.4.57: merkezde REDDEDILIR. Rol denetimi yetmez —
            # merkezde her firmanin kendi yoneticisi vardir ve hepsi
            # ayni surece baglidir; birinin servisi durdurmasi digerlerini
            # yerde birakir.
            if self._merkez_kipinde():
                self.konsol("IZIN", "Servis eylemi merkez kipinde "
                            "reddedildi.", "uyari")
                await websocket.send(json.dumps(
                    {"tip": "servis_sonuc", "basarili": False,
                     "merkez_kipi": True,
                     "hata": "Merkezde servis yonetimi arayuzden "
                             "yapilamaz; merkez operatoru yonetir."}))
                return
            #
            # KRITIK: IZIN_HARITASI denetimi burada YETMEZ. pilot.py
            # izin_var() tanimsiz izni varsayilan True kabul eder
            # (satir 214), yani yeni 'sistem.servis' grubu her role acik
            # olurdu. Servisi durdurmak TUM ucuslari keser; bu yuzden
            # acik rol denetimi zorunludur (sirket_kaydet ile ayni desen).
            p = self._pilot_bilgi(websocket) or {}
            if p.get("rol") != "yonetici":
                self.konsol("IZIN", "Servis eylemi reddedildi "
                            f"(yonetici degil): {p.get('eposta', '?')}",
                            "uyari")
                await websocket.send(json.dumps(
                    {"tip": "servis_sonuc", "basarili": False,
                     "hata": "Servisi yalnizca yonetici yonetebilir."}))
                return
            if self.servis is None:
                await websocket.send(json.dumps(
                    {"tip": "servis_sonuc", "basarili": False,
                     "hata": "Servis yonetimi bu isletim sisteminde "
                             "kullanilamaz (systemd gerekir)."}))
                return
            ad = str(k.get("ad") or "").strip()
            # Arayuz 'yeniden' der; servis.py anahtari 'yeniden_baslat'.
            if ad == "yeniden":
                ad = "yeniden_baslat"
            loop = asyncio.get_running_loop()
            # KENDINI DURDURMA SORUNU: 'durdur' ve 'yeniden' komutlari bu
            # surecin kendisini oldurur. systemctl'i dogrudan cagirirsak
            # yanit gonderilmeden once SIGTERM gelir ve arayuz sonucu hic
            # gormez ("baglanti koptu" der, islem basarili miydi
            # bilinmez). Bu yuzden once yaniti gonderip eylemi kisa bir
            # gecikmeyle arka planda kosturuyoruz.
            if ad in ("durdur", "yeniden_baslat"):
                hazir, neden = await loop.run_in_executor(None, _db_iade_ederek, self.servis.eylem_hazir, ad)
                if not hazir:
                    await websocket.send(json.dumps(
                        {"tip": "servis_sonuc", "basarili": False,
                         "ad": ad, "hata": neden}))
                    return
                bekleniyor = ("Servis durduruluyor; arayuz baglantisi "
                              "kesilecek.") if ad == "durdur" else (
                    "Servis yeniden baslatiliyor; arayuz birkac saniye "
                    "icinde kendini toparlayacak.")
                # NEDEN: bu surec 1 saniye sonra oldurulecek. Telemetri
                # tamponu diske yazilmadan olurse son dakikanin verisi
                # kaybolur; SIGTERM yolu bunu yapiyor ama 'stop' once
                # geldiginde sirayi garanti etmek icin burada da isaretlenir.
                await websocket.send(json.dumps(
                    {"tip": "servis_sonuc", "basarili": True, "ad": ad,
                     "beklemede": True, "ileti": bekleniyor}))
                self.konsol("SERVIS",
                            f"{p.get('eposta', '?')} servisi '{ad}' "
                            "istedi; eylem 1 saniye sonra uygulanacak.")
                await loop.run_in_executor(None, _db_iade_ederek, self.servis.gecikmeli_eylem, ad, 1.0)
                return
            # servis.eylem() SOZLUK doner: {"tamam":bool,"hata":str,...}
            son = await loop.run_in_executor(None, _db_iade_ederek, self.servis.eylem, ad)
            basarili = bool(son.get("tamam"))
            ileti = son.get("hata") or son.get("cikti") or "Uygulandi."
            self.konsol("SERVIS",
                        f"{p.get('eposta', '?')} -> {ad}: {ileti}",
                        "bilgi" if basarili else "uyari")
            ozet = await loop.run_in_executor(None, _db_iade_ederek, self.servis.ozet)
            ozet.update({"tip": "servis_sonuc", "basarili": basarili,
                         "ad": ad, "ileti": ileti, "destekli": True,
                         "yetkili": True})
            await websocket.send(json.dumps(ozet))
        elif komut in ("merkez_dogrula", "merkez_sunucular"):
            # v2.4.53: Kullanici istegi (birebir): "kullanici sisteme
            # baglanti yoneticisi bolumunde bir baglanti ekleyeceginde
            # sistem acik olan sunuculari gostersin ve kullanici secsin".
            #
            # Merkeze cagriyi TARAYICI DEGIL sunucu yapar. Neden:
            #  1) Merkez hesabinin sifresi tarayiciya hic inmez
            #     (arayuz kodu paylasilan bir dosyadir, sir tasiyamaz).
            #  2) Iletisim tek yonlu client->server modelinde kalir;
            #     tarayicidan merkeze ayri bir kanal acmak CORS/TLS
            #     yuzeyini gereksiz genisletirdi.
            #
            # KRITIK: IZIN_HARITASI denetimi burada YETMEZ — pilot.py
            # izin_var() tanimsiz izni True kabul eder. Merkez hesabi
            # sirket capinda bir kimliktir; acik rol denetimi zorunlu
            # (servis_eylem ile ayni desen).
            p = self._pilot_bilgi(websocket) or {}
            yanit_tipi = ("merkez_dogrula_sonuc"
                          if komut == "merkez_dogrula"
                          else "merkez_sunucular")
            if p.get("rol") != "yonetici":
                self.konsol("IZIN", "Merkez sorgusu reddedildi "
                            f"(yonetici degil): {p.get('eposta', '?')}",
                            "uyari")
                await websocket.send(json.dumps(
                    {"tip": yanit_tipi, "basarili": False, "sunucular": [],
                     "hata": "Merkez sunucu ayarlarini yalnizca yonetici "
                             "kullanabilir."}))
                return
            try:
                from . import merkez as _merkez
            except Exception as e:  # modul eksikse arayuz NEDEN'i gormeli
                await websocket.send(json.dumps(
                    {"tip": yanit_tipi, "basarili": False, "sunucular": [],
                     "hata": f"Merkez modulu yuklenemedi: {e}"}))
                return
            # Ayarlar sunucuda saklanir; arayuzden gelen gecici degerler
            # (sihirbaz sinama akisi) ayarlarin UZERINE yazilmadan
            # kullanilir — boylece kullanici kaydetmeden once sinayabilir.
            yap = _merkez.ayar_coz(self.ayarlar.yukle())
            for arayuz_ad, ayar_ad in (("adres", "adres"),
                                       ("eposta", "eposta"),
                                       ("sifre", "sifre")):
                deger = str(k.get(arayuz_ad) or "").strip()
                if deger:
                    yap[ayar_ad] = deger
            loop = asyncio.get_running_loop()
            if komut == "merkez_dogrula":
                veri, hata = await loop.run_in_executor(None, _db_iade_ederek, _merkez.dogrula, yap)
                kul = (veri or {}).get("kullanici") or {}
                if hata:
                    self.konsol("MERKEZ", f"Dogrulama basarisiz: {hata}",
                                "uyari")
                else:
                    self.konsol("MERKEZ", "Dogrulandi: "
                                f"{kul.get('eposta', '?')} / "
                                f"{kul.get('firma_unvan', '?')}", "basari")
                await websocket.send(json.dumps(
                    {"tip": yanit_tipi, "basarili": not hata,
                     "hata": hata or "", "kullanici": kul,
                     "adres": yap.get("adres", "")}))
                return
            liste, hata = await loop.run_in_executor(None, _db_iade_ederek, _merkez.acik_sunucular, yap)
            if hata:
                self.konsol("MERKEZ", f"Acik sunucu listesi alinamadi: "
                            f"{hata}", "uyari")
            else:
                self.konsol("MERKEZ", f"{len(liste or [])} acik sunucu "
                            "listelendi.", "bilgi")
            await websocket.send(json.dumps(
                {"tip": yanit_tipi, "basarili": not hata,
                 "hata": hata or "", "sunucular": liste or [],
                 "adres": yap.get("adres", "")}))
        elif komut in ("merkez_kayit", "merkez_kopru_durum"):
            # v2.4.53 Faz 12-13: Bu GCS kurulumunu merkeze SUNUCU olarak
            # kaydeder ve kopru ajaninin durumunu bildirir.
            #
            # NEDEN AYRI KOMUT: `merkez_dogrula` yalniz hesabi sinar;
            # kayit ise merkezde kalici bir satir ve TEK SEFERLIK bir sir
            # uretir. Bu yuzden kazara tetiklenmemesi gerekir: arayuz
            # ayri bir dugme ve onay ile cagirir.
            #
            # KRITIK: donen `gizli` arayuze GONDERILMEZ. Merkez sirri bir
            # daha vermez; sir yalniz veri/kopru.json icinde yasar ve
            # arayuze `merkez.kimlik_ozet()` maskesi gider (merkez_sifre
            # maskesiyle ayni ilke).
            p = self._pilot_bilgi(websocket) or {}
            if p.get("rol") != "yonetici":
                self.konsol("IZIN", "Merkez kaydi reddedildi "
                            f"(yonetici degil): {p.get('eposta', '?')}",
                            "uyari")
                await websocket.send(json.dumps(
                    {"tip": "merkez_kayit_sonuc", "basarili": False,
                     "hata": "Merkez kaydini yalnizca yonetici "
                             "yapabilir."}))
                return
            try:
                from . import merkez as _merkez
            except Exception as e:
                await websocket.send(json.dumps(
                    {"tip": "merkez_kayit_sonuc", "basarili": False,
                     "hata": f"Merkez modulu yuklenemedi: {e}"}))
                return
            if komut == "merkez_kopru_durum":
                await websocket.send(json.dumps(
                    {"tip": "merkez_kopru_durum", "basarili": True,
                     "hata": "", "kimlik": _merkez.kimlik_ozet(),
                     "kopru": self._kopru_durum_ozet()}))
                return
            yap = _merkez.ayar_coz(self.ayarlar.yukle())
            for arayuz_ad in ("adres", "eposta", "sifre"):
                deger = str(k.get(arayuz_ad) or "").strip()
                if deger:
                    yap[arayuz_ad] = deger
            ad = str(k.get("ad") or "").strip() or None
            aciklama = str(k.get("aciklama") or "").strip() or None
            yenile = bool(k.get("yenile"))
            # Surum tek kaynaktan okunur: js/surum.js -> goktungu.__version__
            # (iki ayri sabit tutmak v2.4.49'da yanlis surum bildirmisti).
            try:
                from . import __version__ as _gcs_surum
                surum = str(_gcs_surum or "")
            except Exception:
                surum = ""
            loop = asyncio.get_running_loop()
            veri, hata = await loop.run_in_executor(None, _db_iade_ederek, functools.partial(
                    _merkez.sunucu_kayit, yap, ad=ad, surum=surum,
                    aciklama=aciklama, yenile=yenile))
            if hata:
                self.konsol("MERKEZ", f"Sunucu kaydi basarisiz: {hata}",
                            "uyari")
            else:
                self.konsol("MERKEZ", "Sunucu kaydi tamam: "
                            f"{(veri or {}).get('ad', '?')} "
                            f"(ornek {(veri or {}).get('ornek_id', '?')})",
                            "basari")
                # Kayit tamamsa kopru ajani hemen baglanabilir.
                try:
                    await self._kopru_yeniden_kur()
                except Exception as e:
                    self.konsol("KOPRU", f"Ajan baslatilamadi: {e}", "uyari")
            await websocket.send(json.dumps(
                {"tip": "merkez_kayit_sonuc", "basarili": not hata,
                 "hata": hata or "", "kimlik": _merkez.kimlik_ozet(),
                 "kopru": self._kopru_durum_ozet()}))
        elif komut == "makine_kapat":
            # v2.4.49: {"tip":"makine_kapat","ad":"kapat|yeniden"}
            # Kullanici istegi: "kullanici menusu altinda bilgisayari
            # kapat dugmesi olsun, basinca eminmisiniz desin evet derse
            # bilgisayari kapatsin". Onay ARAYUZDE alinir; burada son
            # yetki denetimi yapilir.
            #
            # v2.4.57: merkezde REDDEDILIR. Bu dugme, saha bilgisayari
            # basinda oturan pilotun kendi makinesini kapatmasi icin
            # tasarlandi. Merkezde "bilgisayar" tum kiracilarin sunucusu
            # olur; bir firmanin yoneticisi butun sistemi kapatabilirdi.
            if self._merkez_kipinde():
                self.konsol("IZIN", "Makine kapatma merkez kipinde "
                            "reddedildi.", "uyari")
                await websocket.send(json.dumps(
                    {"tip": "makine_sonuc", "basarili": False,
                     "merkez_kipi": True,
                     "hata": "Merkezde sunucu kapatma arayuzden "
                             "yapilamaz; merkez operatoru yonetir."}))
                return
            p = self._pilot_bilgi(websocket) or {}
            if p.get("rol") != "yonetici":
                self.konsol("IZIN", "Makine kapatma reddedildi "
                            f"(yonetici degil): {p.get('eposta', '?')}",
                            "uyari")
                await websocket.send(json.dumps(
                    {"tip": "makine_sonuc", "basarili": False,
                     "hata": "Bilgisayari yalnizca yonetici "
                             "kapatabilir."}))
                return
            if self.servis is None:
                await websocket.send(json.dumps(
                    {"tip": "makine_sonuc", "basarili": False,
                     "hata": "Guc yonetimi bu isletim sisteminde "
                             "kullanilamaz."}))
                return
            # servis.guc() anahtarlari: "kapat" | "yenidenbaslat"
            ad = str(k.get("ad") or "kapat").strip()
            if ad in ("yeniden", "yeniden_baslat"):
                ad = "yenidenbaslat"
            if ad not in ("kapat", "yenidenbaslat"):
                await websocket.send(json.dumps(
                    {"tip": "makine_sonuc", "basarili": False,
                     "hata": f"Bilinmeyen guc eylemi: {ad}"}))
                return
            loop = asyncio.get_running_loop()
            hazir, neden = await loop.run_in_executor(None, _db_iade_ederek, self.servis.guc_hazir, ad)
            if not hazir:
                # Yetki yoksa ONCEDEN soyle. Aksi halde operator onay
                # verir, hicbir sey olmaz ve nedenini bilemez.
                await websocket.send(json.dumps(
                    {"tip": "makine_sonuc", "basarili": False,
                     "ad": ad, "hata": neden}))
                return
            # UCUS GUVENLIGI: havada dron varken makineyi kapatmak
            # baglantiyi keser. Karar operatorde ama uyari SAYIYLA
            # verilir; arayuz bunu onay penceresinde gosterir.
            ucan = 0
            try:
                # dron.dronlar: sysid -> telemetri sozlugu. Irtifa alani
                # 'alt_rel' (dron.py:509); 'rel_alt' DIYE BIR ALAN YOK.
                with self.dron.kilit:
                    kayitlar = list(self.dron.dronlar.values())
                for d in kayitlar:
                    if d.get("armed") or (d.get("alt_rel") or 0) > 1.0:
                        ucan += 1
            except Exception:
                ucan = 0
            ileti = ("Bilgisayar kapatiliyor." if ad == "kapat"
                     else "Bilgisayar yeniden baslatiliyor.")
            self.konsol("SERVIS",
                        f"{p.get('eposta', '?')} makineyi '{ad}' istedi"
                        + (f"; DIKKAT: {ucan} dron havada!" if ucan
                           else ""),
                        "uyari" if ucan else "bilgi")
            await websocket.send(json.dumps(
                {"tip": "makine_sonuc", "basarili": True, "ad": ad,
                 "ileti": ileti, "ucan": ucan}))
            # Yanit gonderildikten SONRA guc komutu verilir (kendini
            # durdurma sorununun ayni cozumu).
            await loop.run_in_executor(None, _db_iade_ederek, self.servis.guc, ad, 2.0)
        elif komut in ("pg_durum", "pg_dene", "pg_olustur",
                       "pg_kur", "pg_goc"):
            # v2.4.51: PostgreSQL ilk kurulum / goc sihirbazi.
            #
            # KRITIK TASARIM KARARI - bu komutlar GIRIS ONCESI calisir.
            # Veritabani yapilandirilmamisken kullanici dogrulanamaz
            # (kullanicilar tablosu PostgreSQL'de), bu yuzden sihirbaz
            # kimlik dogrulamasi olmadan erisilebilir olmak ZORUNDA.
            #
            # Bu bir guvenlik riski yaratir: yapilandirilmamis bir
            # sunucuya agdan baglanan herkes veritabani bilgisi
            # girebilir. Riski KAPI DENETIMI ile sinirliyoruz:
            # yapilandirma tamamlandiktan sonra bu komutlar kapanir.
            #
            # IZIN_HARITASI'na EKLENMEZ: pilot.py izin_var() tanimsiz
            # izni varsayilan True kabul eder; ayrica henuz kullanici
            # yoktur. Denetim burada aciktir.
            await self._pg_sihirbaz(websocket, komut, k)
        elif komut == "yonetici_kur":
            # v2.4.68: KULLANICININ KENDI YONETICI HESABI
            #
            # OLCULEN KUSUR (2026-08-16, kullanicinin bildirimi):
            # "hala merkez yazilima kendi sifremle giremiyorum, en
            #  azindan sihirbazda bana sorsun kullanici adi sifreyi,
            #  merkezden bagimsiz olarak"
            #
            # Temiz kurulumda `_ilk_yonetici_guvence()` rastgele
            # sifreli `kurulum@yerel` hesabini acar; sifre yalnizca
            # konsola ve `ilk_giris.txt`e yazilir. SERVIS olarak
            # kurulunca konsol gorunmez -> kullanici KILITLI kalir.
            #
            # NEDEN GIRIS ONCESI ERISILEBILIR:
            # Tam olarak `pg_kur` ile ayni gerekce -- bu komut
            # kullanici HENUZ giris yapamazken calismak zorundadir;
            # zaten amaci giris yapilabilir hale getirmektir.
            #
            # KAPI DENETIMI (`_yonetici_kur` icinde DEGIL, burada):
            # Yerel `kullanicilar` tablosunda `kurulum@yerel` DISINDA
            # gercek bir hesap varsa komut REDDEDILIR. Aksi halde agdan
            # baglanan herkes yonetici hesabinin sifresini degistirip
            # calisan bir kurulumu ele gecirebilirdi. Kurulum penceresi
            # yalnizca ilk yonetici olusana kadar aciktir.
            if self._kurulum_penceresi_acik():
                await self._yonetici_kur(websocket, k)
            else:
                await websocket.send(json.dumps(
                    {"tip": "yonetici_kur_sonuc", "basarili": False,
                     "hata": "Kurulum tamamlanmis: yonetici hesabi "
                             "yalnizca Kullanicilar bolumunden "
                             "degistirilebilir.",
                     "eposta": "", "degistirildi": False,
                     "kapali": True}))
        elif komut == "lisans_yenile":
            await self._lisans_yenile(websocket, k)
        elif komut == "merkez_esitle":
            # v2.4.66: MERKEZ KULLANICI ESITLEMESI
            #
            # OLCULEN KUSUR (2026-08-16): Merkez Uygulama kurulumunda
            # yerel `kullanicilar` tablosu bos kaliyor, bu yuzden
            # `_ilk_yonetici_guvence()` devreye girip GOMULU bir hesap
            # yaratiyordu (`gokkubbe2026`). Firmanin /company/
            # panelinde tanimladigi sifre GECERSIZ kaliyordu.
            #
            # Bu komut merkezdeki gercek kullanici listesini bir kez
            # ceker ve yerel tabloya yazar (sifre ozetleri dahil).
            #
            # NEDEN GIRIS ONCESI ERISILEBILIR:
            # Kurulumdan hemen sonra yerelde yalnizca rastgele sifreli
            # `kurulum@yerel` hesabi vardir. Musteri bu hesapla giris
            # yapmak zorunda kalmadan kendi kurumsal hesabina
            # gecebilmelidir. Ayrica komut, MERKEZE dogru e-posta ve
            # sifre verilmeden hicbir sey yapmaz: gercek kapi merkez
            # sunucudadir (oturum + firma_yonetici + merkez_lisans).
            # Yani burada kimlik istemek ikinci bir kapi olurdu, kilit
            # zaten merkezde.
            await self._merkez_esitle(websocket, k)
        elif komut in ("dji_belirtec_durum", "dji_belirtec_uret",
                       "dji_belirtec_sil"):
            # BULGU_07: DJI KOPRU BELIRTEC YONETIMI
            #
            # GDP protokolu (8790) artik `merhaba` mesajinda belirtec
            # ister (bkz. dji_kopru.py). Android kopru uygulamasi bu
            # belirteci ayar ekranindan alir; kullanici belirteci BURADAN
            # kopyalar. Bu uc olmadan kimlik dogrulama kullanilamaz.
            #
            # YALNIZCA YONETICI: belirtec, DJI dronunu bu kuruluma
            # baglama yetkisi verir. Pilot rolune acik olsa bir pilot
            # kendi cihazini baglayip telemetri akisina girebilirdi.
            await self._dji_belirtec_komut(websocket, komut, k)
        elif komut in ("hedef_liste", "angajman_liste",
                       "angajman_ekle", "angajman_karar"):
            # IS91/92: Goruntu Koprusu hedef verisi ve angajman
            # kuyrugu. Hedef LISTESI okuma her pilota acik; KARAR
            # yalnizca yoneticide (yetki denetimi metot icinde).
            await self._hedef_komut(websocket, komut, k)
        elif komut in ("kopru_kimlik_liste", "kopru_kimlik_uret",
                       "kopru_kimlik_sil"):
            # v2.4.67: KAPALI DEVRE KOPRU KIMLIK YONETIMI
            #
            # Kopru yazilimi yerel merkeze baglanmak icin bir kurulum
            # kimligi (uid + sir) ister. Bulutta bu kimlik /company/
            # panelinden uretilir; kapali devre kurulumda internet ve
            # dolayisiyla o panel YOKTUR. Bu yuzden kimlik yerel Merkez
            # Uygulama arayuzunden uretilir.
            #
            # YALNIZCA YONETICI: kimlik, kopru makinesinin seri
            # portlarina komut gonderme yetkisi verir; pilot rolune
            # aciksa bir pilot kendi makinesini merkeze bagli gosterip
            # baska pilotlarin dronlarina komut gonderebilir.
            await self._kopru_kimlik_komut(websocket, komut, k)
        elif komut == "sirket_kaydet":
            # v2.4.41: {"tip":"sirket_kaydet","sirket":{...}}
            # Sirket kimlik bilgileri (antetli ucus raporunun kaynagi).
            # YALNIZCA yonetici yazabilir; program_ayar_yaz ile ayni
            # izin deseni.
            p = self._pilot_bilgi(websocket) or {}
            if p.get("rol") != "yonetici":
                self.konsol("IZIN", "Sirket bilgisi reddedildi "
                            f"(yonetici degil): {p.get('eposta', '?')}",
                            "uyari")
                await websocket.send(json.dumps(
                    {"tip": "sirket_sonuc", "basarili": False,
                     "hata": "Sirket bilgilerini yalnizca yonetici "
                             "degistirebilir."}))
                return
            s = k.get("sirket") or {}
            unvan = str(s.get("unvan") or "").strip()
            adres = str(s.get("adres") or "").strip()
            telefon = str(s.get("telefon") or "").strip()
            if not unvan or not adres or not telefon:
                await websocket.send(json.dumps(
                    {"tip": "sirket_sonuc", "basarili": False,
                     "hata": "Unvan, adres ve telefon zorunludur."}))
                return
            logo_veri = str(s.get("logo_veri") or "")
            # Logo data URI boyut siniri: ayarlar tablosuna JSON olarak
            # yazildigi icin cok buyuk veri tum ayar yuklemesini
            # yavaslatir. 512 KB base64 ~ 384 KB PNG; fazlasi reddedilir.
            if logo_veri and len(logo_veri) > 512 * 1024:
                await websocket.send(json.dumps(
                    {"tip": "sirket_sonuc", "basarili": False,
                     "hata": "Logo cok buyuk (en cok ~380 KB PNG)."}))
                return
            mevcut = (self.ayarlar.yukle().get("sirket") or {})
            kayit = {
                "unvan": unvan[:200],
                "adres": adres[:400],
                "telefon": telefon[:60],
                "eposta": str(s.get("eposta") or "").strip()[:120],
                "vergi_no": str(s.get("vergi_no") or "").strip()[:40],
                "web": str(s.get("web") or "").strip()[:120],
                "logo_veri": logo_veri or mevcut.get("logo_veri", ""),
                "kurulum_ts": mevcut.get("kurulum_ts") or time.time(),
                "guncelleme_ts": time.time(),
                "kuran": mevcut.get("kuran") or p.get("eposta", ""),
                "guncelleyen": p.get("eposta", ""),
            }
            yeni = self.ayarlar.kaydet({"sirket": kayit})
            self.konsol("SIRKET", f"Sirket bilgileri kaydedildi: {unvan} "
                        f"({p.get('eposta', '?')})", "basari")
            self._pilot_log(websocket, "ayar", "sirket_kaydet",
                            {"unvan": unvan})
            await websocket.send(json.dumps(
                {"tip": "sirket_sonuc", "basarili": True, "hata": ""}))
            await self._duyur({"tip": "ayarlar", "ayarlar": self.ayarlar.yayin(yeni)})

        elif komut == "program_ayar_yaz":
            # {"tip":"program_ayar_yaz","radar_arayuz":true|false}
            # Program ayarlarini YALNIZCA yonetici degistirebilir;
            # ayar sunucuda saklanir ve tum istemcilere duyurulur.
            p = self._pilot_bilgi(websocket) or {}
            if p.get("rol") != "yonetici":
                self.konsol("IZIN", "Program ayari reddedildi "
                            f"(yonetici degil): {p.get('eposta', '?')}",
                            "uyari")
                await websocket.send(json.dumps(
                    {"tip": "program_ayar_sonuc", "basarili": False,
                     "hata": "Program ayarlarini yalnizca yonetici "
                             "degistirebilir."}))
                return
            # v2.4.45: birden fazla program ayari tek komutla yazilabilir.
            # Eski istemciler yalniz `radar_arayuz` gonderir; yeni
            # istemciler GCCDUAL (Yer Kontrol Istasyonu Dual) anahtarini
            # ve seri port adresini de gonderebilir.
            yaz = {}
            if "radar_arayuz" in k:
                yaz["radar_arayuz"] = bool(k.get("radar_arayuz"))
            if "istasyon2_arayuz" in k:
                yaz["istasyon2_arayuz"] = bool(k.get("istasyon2_arayuz"))
            if "istasyon2_port" in k:
                # Bos dize gecerlidir: "port tanimsiz" anlamina gelir
                yaz["istasyon2_port"] = str(k.get("istasyon2_port") or "")
            if "istasyon2_otomatik" in k:
                yaz["istasyon2_otomatik"] = bool(k.get("istasyon2_otomatik"))
            # v2.4.53: merkez sunucu hesabi. Sifre ayarlarda saklanir
            # cunku merkeze her cagrida kimlik gonderilir (merkez tek
            # yonlu iletisim modelinde oturum tutmaz). Bos sifre gelirse
            # ESKI sifre korunur: kullanici adresi duzeltirken sifresinin
            # sessizce silinmesi kabul edilemez.
            if "merkez_etkin" in k:
                yaz["merkez_etkin"] = bool(k.get("merkez_etkin"))
            if "merkez_adres" in k:
                yaz["merkez_adres"] = str(k.get("merkez_adres") or "").strip()
            if "merkez_eposta" in k:
                yaz["merkez_eposta"] = str(
                    k.get("merkez_eposta") or "").strip()
            if "merkez_sifre" in k:
                yeni_sifre = str(k.get("merkez_sifre") or "")
                if yeni_sifre:
                    yaz["merkez_sifre"] = yeni_sifre
            if not yaz:
                return
            yeni = self.ayarlar.kaydet(yaz)
            if "radar_arayuz" in yaz:
                self.konsol("AYAR", "C20 RADAR arayuzu "
                            f"{'ACILDI' if yaz['radar_arayuz'] else 'KAPATILDI'} "
                            f"({p.get('eposta', '?')})", "basari")
            if "istasyon2_arayuz" in yaz:
                acikG = yaz["istasyon2_arayuz"]
                self.konsol("AYAR", "GCCDUAL (Yer Kontrol Istasyonu Dual) "
                            f"{'ACILDI' if acikG else 'KAPATILDI'} "
                            f"({p.get('eposta', '?')})", "basari")
                # Arayuz kapatildiysa acik seri baglanti da kapatilir:
                # kapali bir cihazin komut uretmesi kabul edilemez.
                if not acikG and self.istasyon2 is not None:
                    try:
                        self.istasyon2.kes()
                    except Exception:
                        pass
            if "istasyon2_port" in yaz:
                self.konsol("AYAR", "GCCDUAL portu: "
                            f"{yaz['istasyon2_port'] or '(tanimsiz)'}",
                            "bilgi")
            if "merkez_etkin" in yaz:
                self.konsol("MERKEZ", "Merkez sunucu senkronizasyonu "
                            f"{'ACILDI' if yaz['merkez_etkin'] else 'KAPATILDI'}"
                            f" ({p.get('eposta', '?')})", "basari")
            if "merkez_adres" in yaz:
                self.konsol("MERKEZ", "Merkez adresi: "
                            f"{yaz['merkez_adres'] or '(tanimsiz)'}", "bilgi")
            # Sifre ASLA gunluge yazilmaz; denetim kaydinda da maskelenir.
            gunluk = {a: ("***" if a == "merkez_sifre" else d)
                      for a, d in yaz.items()}
            self._pilot_log(websocket, "ayar", "program_ayar", gunluk)
            # v2.4.53: merkez ayari degistiyse kopru ajanini uyarla.
            # Yeniden BASLATMA gerekmez: kullanici ayari kapatinca
            # baglantinin acik kalmasi (veya acinca elle baslatma
            # gerekmesi) sessiz kusur olurdu.
            if any(a in yaz for a in ("merkez_etkin", "merkez_adres",
                                      "merkez_eposta", "merkez_sifre")):
                if yaz.get("merkez_etkin") is False:
                    if self.kopru is not None:
                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(None, _db_iade_ederek, self.kopru.durdur)
                        self.konsol("KOPRU", "Merkez kapatildi; ajan "
                                    "durduruldu.", "bilgi")
                else:
                    await self._kopru_yeniden_kur()
                await self._duyur({"tip": "merkez_kopru_durum",
                                   "basarili": True, "hata": "",
                                   "kopru": self._kopru_durum_ozet()})
            await self._duyur({"tip": "ayarlar", "ayarlar": self.ayarlar.yayin(yeni)})

    # ------------------------------------------------------------------
    # Telemetri yayin dongusu
    # ------------------------------------------------------------------
    async def yayin_dongusu(self):
        while True:
            # IS99: Görüntü geçmişi saklama süresi temizliği, yeni bir
            # zamanlayıcı/thread açmadan mevcut sürekli App döngüsünde ve
            # istemci bağlı olmasa da saatlik çalışır. Ağır dosya/DB işi
            # asyncio döngüsünü bloke etmemesi için iş parçacığına bırakılır.
            _bakim_simdi = time.time()
            if (_bakim_simdi - getattr(self, "_IS99_GORUNTU_BAKIM_SON", 0.0)) >= 3600.0:
                self._IS99_GORUNTU_BAKIM_SON = _bakim_simdi
                try:
                    await _db_is_parcasi(goruntu_gecmisi.bakim_yap, True)
                except Exception as _e_is99:
                    self.konsol("GORUNTU", "Görüntü geçmişi bakımı başarısız: " +
                                str(_e_is99), "uyari")
            if self.istemciler:
                simdi = time.time()
                # Betaflight Köprü oturumları yalnız durum/tanı bilgisiyle
                # güncellenir; MAVLink telemetri paketine dönüştürülmez.
                self._betaflight_kopru_durumlarini_yenile()
                # v2.4.59: MERKEZ KIPINDE radar verisi kopruden gelir.
                # Cagri KILIT BLOGUNUN DISINDA yapilir: vekil kendi
                # kilidini alir ve `threading.Lock` yeniden girisli
                # DEGILDIR; blok icinde cagrilirsa yayin dongusu
                # kilitlenir. Vekil degilse (lokal kurulum) bu nitelik
                # yoktur ve hicbir sey yapilmaz.
                _cek = getattr(self.radar, "cek_gerekirse", None)
                if _cek is not None:
                    try:
                        await _db_is_parcasi(_cek)
                    except Exception:
                        # Radar beslemesi butun telemetriyi durdurmaz.
                        pass
                # M50 yalnız saha Köprüsünden arındırılmış durum çeker;
                # hata telemetri döngüsünü veya diğer sistemleri durdurmaz.
                #
                # KUSUR (v2.4.184-185): köprüsüz (doğrudan) mod aktifken
                # bu döngü YİNE DE her turda bridge'i aramaya çalışıyordu
                # (`m50._cek` her zaman `_m50_kopru_durum_cek`e sabitti);
                # köprü bulunamayınca `_kopru_hatasi()` durumu "hata"ya
                # çeviriyor, `_m50_yerelden()`in az önce yazdığı "bağlı"
                # durumunu SANİYEDE BİR eziyordu. Kullanıcı gerçekten
                # bağlansa bile arayüz hep "bağlı değil" görüyordu. Artık
                # doğrudan mod kullanılabilirken köprü sorgusu hiç
                # yapılmaz; durum yalnız `_m50_yerelden()` çağrılarıyla
                # güncellenir.
                # v2.4.191: coklu EO — her cihaz icin yerel->vekil aktarimi
                # (veya kopru cekimi). `eo` yoksa eski tek cift kullanilir.
                _eo = getattr(self, "eo", None)
                _eo_ciftler = ([(_eo.vekiller.get(i), _eo.yereller.get(i))
                                for i in sorted(_eo.vekiller)] if _eo is not None
                               else [(self.m50, getattr(self, "m50_yerel", None))])
                for _v, _y in _eo_ciftler:
                    if _y is not None and _y.kullanilabilir():
                        if _v is not None:
                            try:
                                await _db_is_parcasi(
                                    (lambda v=_v, y=_y: v._uygula(y._durum_paketi())))
                            except Exception:
                                pass
                    else:
                        _m50_cek = getattr(_v, "cek_gerekirse", None)
                        if _m50_cek is not None:
                            try:
                                await _db_is_parcasi(_m50_cek)
                            except Exception:
                                pass
                try:
                    eo_cihazlar = _eo.paketler() if _eo is not None else []
                except Exception:
                    eo_cihazlar = []
                # `M50Vekili.paket()` aynı ortak kilidi alır; bu nedenle
                # kopyayı telemetri ana kilidine girmeden önce oluştururuz.
                # Aksi halde `threading.Lock` yeniden girişsiz olduğu için
                # bütün Merkez telemetrisi kilitlenirdi.
                m50_paket = (self.m50.paket() if self.m50 is not None else {
                    "m50_durum": {"tur": "m50", "durum": "kapali",
                                   "bagli": False, "hata": "M50 vekili kurulu değil"},
                    "m50_ayarlar": {}, "m50_video": {}, "m50_takip": {},
                })
                with self.kilit:
                    paket = []
                    for d in self.dron.dronlar.values():
                        kopya = dict(d)
                        kopya["baglanti"] = (simdi - d["son_mesaj"]) < 8.0
                        # v2.4.32: arayuzun dronu bagli oldugu baglantinin
                        # altinda gruplayabilmesi icin baglanti kimligi.
                        # NOT: `baglanti` alani BOOLEAN'dir (canli mi),
                        # kimlik degildir; bu nedenle ayri ad kullanilir.
                        try:
                            _bid = self.dron.sysid_baglanti.get(
                                d.get("sysid"))
                            kopya["baglanti_id"] = (
                                str(_bid) if _bid is not None else "")
                        except Exception:
                            kopya["baglanti_id"] = ""
                        # v2.4.19: "Ucusa Hazir" gostergesi ozeti
                        try:
                            kopya["hazirlik"] = self.dron.hazirlik_ozeti(
                                kopya)
                        except Exception:
                            kopya["hazirlik"] = {"hazir": None,
                                                 "kritik": 0, "uyari": 0,
                                                 "sebep": ""}
                        paket.append(kopya)
                    baglanti_durumlari = {
                        str(bid): {"durum": c.get("durum", "kapali"),
                                   "hata": c.get("hata", "")}
                        for bid, c in self.dron.baglantilar.items()}
                    if self.dji_kopru:  # DJI kopru dinleyici durumlari
                        baglanti_durumlari.update(self.dji_kopru.durumlar())
                    if self.betaflight:
                        baglanti_durumlari.update(self.betaflight.durumlar())
                    baglanti_durumlari.update(dict(self._betaflight_kopruleri))
                    radar = dict(self.radar.durum)
                    radar["ayarlar"] = dict(self.radar.radar_ayarlar)
                    m50 = m50_paket
                # v2.4.190: coklu radar listesi (kilit DISINDA: durumlar()
                # kendi icinde kilit alir; Lock yeniden girisli degil).
                try:
                    radarlar = (self.radar.durumlar()
                                if hasattr(self.radar, "durumlar") else [radar])
                except Exception:
                    radarlar = [radar]
                with self.kilit:
                    r_hedefler_ham = []
                    for h in self.radar.hedefler.values():
                        if simdi - h["son"] <= RADAR_IZ_ZAMANASIMI:
                            r_hedefler_ham.append(dict(h))

                # Takipci motorunu islet (radar plotlari -> islenmis izler)
                rlat, rlon = self.radar.radar_konum()
                if rlat is None:
                    rlat, rlon = 0.0, 0.0
                if r_hedefler_ham:
                    radar_izler = self.takipci.isle(
                        r_hedefler_ham, simdi, rlat, rlon)
                    self._takipci_son_isle = simdi
                elif (simdi - self._takipci_son_isle) >= 1.0:
                    # Radar verisi gelmese bile denetim (SUZULEN yurut)
                    radar_izler = self.takipci.denetim(simdi, rlat, rlon)
                    self._takipci_son_isle = simdi
                else:
                    # Ara karelerde mevcut durumu gonder (isle cagirmadan)
                    radar_izler = []
                    for iz in self.takipci.izler.values():
                        if iz.durum in self.takipci.ayar.durum_filtre:
                            radar_izler.append(iz.to_dict(rlat, rlon))

                # Yetim izler
                yetimler = self.takipci.yetim_listesi(simdi)

                konsol_satirlar = self.konsol.tum_satirlar()

                # Gorev durumu (yukleme zamanasimi denetimi + paket)
                if self.gorev:
                    self.gorev.denetim()
                    gorev_durum = self.gorev.durum_paketi()
                    # v2.4.35: batarya degisimi gibi kesintiler sonrasi
                    # yarim kalmis gorevler. Yalnizca dron SU AN cevrimici
                    # VE aktif gorev kaydi YOK ise onerilir.
                    gorev_surdurulebilir = self.gorev.surdurulebilir_paketi()
                else:
                    gorev_durum = {}
                    gorev_surdurulebilir = {}

                # v2.4.21: renk atamasi + KESINTISIZ telemetri kaydi.
                # Eski takeoff/land tabanli ucus kaydi kaldirildi; dron
                # bagli oldugu surece telemetri yazilir, ucuslar
                # v_ucuslar VIEW'u ile tespit edilir.
                if self.ucus_gecmisi:
                    dron_renkler = self.ucus_gecmisi.renk_haritasi(paket)
                else:
                    dron_renkler = {}
                self._telemetri_kaydet(paket, simdi)

                # Aktif kayit varsa bu kareyi dosyaya yaz
                self.kayit.kare_yaz(radar, radar_izler, yetimler)

                # Replay aktifken canli radar verisi bastirilir (harita
                # replay verisini gosterir); dron/seri/konsol canli akar
                dron_takipler = (self.dron_takip.durum()
                                 if self.dron_takip else [])
                suru_durum = self.suru.durum() if self.suru else None
                angajman_durum = self.angajman.durum_paketi()
                if self.kayit.replay_durum["aktif"]:
                    veri = json.dumps({
                        "tip": "telemetri",
                        "dronlar": paket,
                        "dron_renkler": dron_renkler,
                        "baglanti_durumlari": baglanti_durumlari,
                        "takipci_ayarlar": self.takipci.ayar.to_dict(),
                        "konsol": konsol_satirlar,
                        "kayit_durum": self.kayit.ozet(),
                        "replay_durum": dict(self.kayit.replay_durum),
                        "gorev_durum": gorev_durum,
                        "gorev_surdurulebilir": gorev_surdurulebilir,
                        "dron_takipler": dron_takipler,
                        "suru": suru_durum,
                        "angajmanlar": angajman_durum,
                        "m50": m50,
                        "eo_cihazlar": eo_cihazlar,
                    })
                else:
                    veri = json.dumps({
                        "tip": "telemetri",
                        "dronlar": paket,
                        "dron_renkler": dron_renkler,
                        "baglanti_durumlari": baglanti_durumlari,
                        "radar": radar,
                        "radarlar": radarlar,
                        "radar_izler": radar_izler,
                        "yetim_izler": yetimler,
                        "takipci_ayarlar": self.takipci.ayar.to_dict(),
                        "konsol": konsol_satirlar,
                        "kayit_durum": self.kayit.ozet(),
                        "replay_durum": dict(self.kayit.replay_durum),
                        "gorev_durum": gorev_durum,
                        "gorev_surdurulebilir": gorev_surdurulebilir,
                        "dron_takipler": dron_takipler,
                        "suru": suru_durum,
                        "angajmanlar": angajman_durum,
                        "m50": m50,
                        "eo_cihazlar": eo_cihazlar,
                    })
                # ---- IS94_TELEMETRI_KISMA ----------------------
                # OLCULEN KUSUR: paket bosta TAMAMEN SABIT (0/141
                # degisim, 30 sn'de 866 KB). Tuketmeyen istemcide bu
                # akis `websockets` okuma kuyrugunu sisiriyor, pong
                # isleyicisi verinin arkasinda kaliyor ve baglanti
                # 45. sn'de 1006 ile SESSIZCE dusuyor.
                # Olcum: is_merkez/olcum_telemetri_degisim.py
                #
                # UC AYRI DURUM:
                #  a) YENI istemci  -> HER ZAMAN tam paket alir. Yoksa
                #     paket degismedigi surece BOS EKRAN gorur.
                #  b) Veri degisti  -> herkese gonderilir.
                #  c) Veri ayni     -> yalnizca sessizlik tavani
                #     dolduysa gonderilir. Tavan gerekli: NAT/LTE ara
                #     kutulari tamamen sessiz baglantiyi dusurur.
                _simdi_g = time.time()
                _onceki = getattr(self, "_IS94_SON_VERI", None)
                _son_gonderim = getattr(self, "_IS94_SON_ZAMAN", 0.0)
                _gorulen = getattr(self, "_IS94_GORULEN", None)
                if _gorulen is None:
                    _gorulen = set()
                    self._IS94_GORULEN = _gorulen
                _hepsi = list(self.istemciler)
                _yeni = [w for w in _hepsi if id(w) not in _gorulen]
                _degisti = (veri != _onceki)
                _tavan_doldu = (_simdi_g - _son_gonderim) >= IS94_SESSIZLIK_TAVANI
                if _degisti or _tavan_doldu:
                    _alicilar = _hepsi
                    self._IS94_SON_ZAMAN = _simdi_g
                else:
                    _alicilar = _yeni
                if _alicilar:
                    await asyncio.gather(
                        *(ws.send(veri) for ws in _alicilar),
                        return_exceptions=True)
                self._IS94_SON_VERI = veri
                # Ayrilan istemcileri kumeden dus: `id()` yeniden
                # kullanilabilir, birikirse yeni istemci "gorulmus"
                # sayilip BOS EKRAN gorur.
                _canli = {id(w) for w in _hepsi}
                self._IS94_GORULEN = _canli
                # ---- /IS94_TELEMETRI_KISMA ---------------------
            else:
                # Istemci yokken birikmis durumu unut: sonraki ilk
                # istemci tam paket almali.
                self._IS94_SON_VERI = None
                self._IS94_GORULEN = set()
            await asyncio.sleep(1.0 / YAYIN_HZ)

    # ------------------------------------------------------------------
    # Sunucu ana dongusu
    # ------------------------------------------------------------------
    async def calistir(self):
        import websockets
        import logging

        # websockets kutuphanesinin handshake hatalarinda tam traceback
        # basmasini engelle: WS portuna WS-olmayan bir istemci baglaninca
        # (ornegin GDP koprusu icin 8790 yerine yanlislikla 8765 girilmesi,
        # port tarayicilar, saglik kontrolleri) konsol traceback seline
        # donuyordu. Tek satirlik anlasilir uyariya cevrilir.
        class _WsHataSuzgeci(logging.Filter):
            _son = {}

            def filter(self, kayit):
                msg = str(kayit.getMessage())
                if ("opening handshake failed" in msg
                        or "did not receive a valid HTTP request" in msg
                        or "connection closed while reading" in msg
                        or "line without CRLF" in msg):
                    # ayni uyariyi 10 sn'de bir kez bas (sel onleme)
                    simdi = time.time()
                    if simdi - self._son.get("t", 0) > 10:
                        self._son["t"] = simdi
                        print("[WS] Uyari: WebSocket portuna gecersiz "
                              "(WS-olmayan) bir baglanti denemesi geldi ve "
                              "reddedildi. DJI koprusu/OSDK adaptoru "
                              "kullaniyorsaniz GCS port ayarinin WebSocket "
                              "portu degil, DJI baglantisinin KOPRU portu "
                              "(varsayilan 8790) oldugundan emin olun.")
                    return False
                return True

        for _ad in ("websockets", "websockets.server"):
            _lg = logging.getLogger(_ad)
            _lg.addFilter(_WsHataSuzgeci())
            # Not: seviye CRITICAL yapilirsa kayitlar filtreye hic
            # ugramaz ve tek satirlik uyari da basilamaz; ERROR birak.
            _lg.setLevel(logging.ERROR)

        # Adres: ayarlardan oku (varsayilan sabiti geriye donuk korur)
        adres = self.ayarlar.yukle().get("ws_adres", WS_ADRES)
        # v2.4.0: thread'lerden gelen yayinlar icin dongu referansi
        self._loop = asyncio.get_running_loop()
        # v2.4.33: harita onbellek ozetini durum cubuguna yayinla
        self._tile_ozet_kur()
        son_hata = None
        # WSS (guvenli WebSocket): HTTPS uzerinden acilan arayuz icin
        #
        # v2.4.57: MERKEZ KIPINDE hic denenmez. Merkezde 9443 portu KOPRU
        # WSS dinleyicisine aittir (saha kopruleri oraya baglanir); GCS'nin
        # ayni portu istemesi her acilista "address already in use" hatasi
        # uretiyordu. Uzerine, merkezde arayuz zaten 443 uzerinden /app/ws
        # tuneliyle konusur, yani bu dinleyicinin karsiligi da yoktur.
        # Kullanicinin kendi sunucusunda WSS eskisi gibi acilir.
        ctx = None if self._merkez_kipinde() else ssl_baglami()
        wss_sunucu = None
        if ctx is not None:
            try:
                wss_sunucu = await websockets.serve(
                    self.ws_baglanti, adres, WSS_PORT, ssl=ctx,
                    ping_interval=20, ping_timeout=40, close_timeout=5)
                print(f"[WS] Guvenli WebSocket hazir: "
                      f"wss://{adres}:{WSS_PORT}")
            except OSError as e:
                print(f"[WS] WSS portu {WSS_PORT} acilamadi ({e}); "
                      f"yalniz ws:// kullanilabilir.")
        for port in WS_PORTLAR:
            try:
                async with websockets.serve(
                        self.ws_baglanti, adres, port,
                        ping_interval=20, ping_timeout=40, close_timeout=5):
                    # v2.4.49: gercekte alinan WS portunu kaydet (bkz.
                    # HttpSunucusu.aktif_port aciklamasi).
                    self.aktif_ws_port = port
                    print(f"[WS] WebSocket hazir: ws://{adres}:{port}")
                    # v2.4.67: KOPRU KABUL UCU. Yerel (kapali devre)
                    # kurulumda kopruler bu dinleyicinin `/kopru`
                    # yoluna baglanir.
                    #
                    # Bayat kayit temizligi BURADA yapilir: onceki
                    # surec cokerse `cevrimici` bayragi TRUE kalir ve
                    # panel var olmayan bir kopruyu bagli gosterir;
                    # operator komutun gittigini sanir.
                    if not self._merkez_kipinde():
                        try:
                            from . import kopru_kabul as _kk
                            await _db_is_parcasi(_kk.bayat_temizle)
                            _n = len(_kk.kopru_listesi())
                            print(f"[KOPRU] Kabul ucu hazir: "
                                  f"ws://{adres}:{port}/kopru "
                                  f"({_n} kayitli kurulum)")
                        except Exception as e:
                            print(f"[KOPRU] Kabul ucu hazirlanamadi: {e}")
                    # v2.4.53: MERKEZ KOPRUSU. WS portu acildiktan SONRA
                    # baslatilir: ajanin ilk isi merkeze dron/port sormak
                    # olabilir ve bu bilgiler ancak sunucu ayakta anlamli
                    # olur. Kayit yoksa sessizce atlanir.
                    try:
                        await self._kopru_yeniden_kur()
                    except Exception as e:
                        print(f"[KOPRU] Ajan baslatilamadi: {e}")
                    await self.yayin_dongusu()
                return
            except OSError as e:
                son_hata = e
                print(f"[WS] Port {port} kullanilamiyor ({e}), "
                      f"siradaki deneniyor...")
        print(f"[WS] HATA: Hicbir WebSocket portu acilamadi: {son_hata}")
        if wss_sunucu is not None:
            wss_sunucu.close()


class HttpSunucusu:
    """index.html ve statik dosyalari sunan basit HTTP sunucusu.

    v2.4.52: kok dizin artik `WEB_KOKU` (yeni yapida
    `<kok>/assets/web`, eski duz yapida proje koku). `PROJE_KOKU`
    KULLANILMAZ: yeni yapida orada `index.html` yoktur; sunucu
    ayakta gorunur ama arayuz BOS gelir (sessiz kusur).
    """
    def __init__(self, klasor=None, adres=HTTP_ADRES,
                 ai_yonetici=None, ws_sunucu=None,
                 video_proxy=None):
        if klasor is None:
            klasor = WEB_KOKU
        self.klasor = klasor
        self.adres = adres
        self.ai_yonetici = ai_yonetici   # v2.4.0: POST /ai/tespit icin
        # IS9B-OTURUM-DEVRI: `/api/oturum/devir` ucu App oturum jetonu
        # uretmek zorundadir ve jeton uretimi (`_jeton_uret`) bir
        # WSSunucusu yontemidir. HTTP katmaninda YENIDEN YAZILMASI
        # ikinci bir dogruluk kaynagi yaratirdi: jeton omru, ozetleme
        # ve suresi gecmis kayit temizligi iki yerde ayri yasar ve
        # zamanla ayrisirlar. Tek kaynak korunur, ornek gecirilir.
        self.ws_sunucu = ws_sunucu
        # FAZ19-IS60B: `/kamera/<id>` MJPEG yolu icin video
        # saglayicisi. Merkez kipinde tarayici 8801'e ULASAMAZ
        # (port dinlenmiyor + sayfa https, 8801 http). Video bu
        # yuzden AYNI ORIGIN uzerinden, `/tile/` karo vekiliyle
        # ayni kalipta sunulur.
        self.video_proxy = video_proxy
        # FAZ20-OFFLINE-KAMERA-OTURUM: Canlı MJPEG ucu, açık bir LAN
        # adresinden yalnız kamera kimliği tahmin edilerek izlenemez. Ham
        # değer bellek dışında tutulmaz; depoda yalnız SHA-256 özeti ve
        # kısa sonlanma zamanı vardır. Bu yetenek çerezi kullanıcı parolası,
        # RTSP adresi veya cihaz kimliği içermez.
        self._kamera_oturum_kilit = threading.Lock()
        self._kamera_oturumlar = {}
        self._kamera_oturum_sure = 4 * 60 * 60
        # v2.4.49: henuz baglanilmadi; `calistir()` gercek portu yazar.
        # None ile baslatilir cunku "8000 varsayimi" yanlis porta
        # yonlendirir (bkz. calistir icindeki aciklama).
        self.aktif_port = None

    def _kamera_oturum_ac(self, kullanici):
        """Kullanıcı doğrulandıktan sonra tek amaçlı MJPEG oturumu üretir.

        Jeton, WebSocket/HTTP kimlik jetonundan bağımsızdır; çerezden çalınsa
        bile yalnız kısa süreli kamera okuma yetkisi verir. Kullanıcı verisi
        veya düz oturum değeri günlüğe ya da kalıcı depoya yazılmaz.
        """
        if not kullanici:
            return None
        ham = secrets.token_urlsafe(32)
        ozet = hashlib.sha256(ham.encode("utf-8")).hexdigest()
        simdi = time.time()
        with self._kamera_oturum_kilit:
            # Her üretimde süre geçen kayıtlar temizlenir. Böylece geçerli
            # kullanıcıyla yapılan tekrarlı girişler bellek tüketemez.
            self._kamera_oturumlar = {
                k: v for k, v in self._kamera_oturumlar.items()
                if float(v or 0) > simdi
            }
            # Geçerli kullanıcı bile olsa uç tekrar çağrılabilir; sabit üst
            # sınır oturum deposunu denetlenebilir tutar. En eski yetenek
            # çerezi erken biter, yeni çerez geçerli kalır.
            while len(self._kamera_oturumlar) >= 2048:
                self._kamera_oturumlar.pop(next(iter(self._kamera_oturumlar)), None)
            self._kamera_oturumlar[ozet] = simdi + self._kamera_oturum_sure
        return ham

    def _kamera_oturum_gecerli(self, ham):
        """Kamera çerezini özetle doğrular; hata halinde kapalıdır."""
        if not isinstance(ham, str) or not ham or len(ham) > 256:
            return False
        ozet = hashlib.sha256(ham.encode("utf-8")).hexdigest()
        simdi = time.time()
        with self._kamera_oturum_kilit:
            son = self._kamera_oturumlar.get(ozet)
            if son is None or float(son) <= simdi:
                if son is not None:
                    self._kamera_oturumlar.pop(ozet, None)
                return False
            return True

    def calistir(self):
        """HTTP sunucusunu (bloklayarak) calistirir; thread'de kosulur."""
        from . import tile_cache
        _ai = self.ai_yonetici
        # IS9B-OTURUM-DEVRI: devir ucu icin WS ornegi kapanisa alinir.
        _wss = self.ws_sunucu
        # FAZ19-IS60B: `/kamera/<id>` dali icin video saglayicisi.
        _vp = self.video_proxy
        # IS97: merkezden gelen hedefler aynı süreçteki TEKİL depoya yazılır.
        # Yeni bir DronYonetici/HedefDeposu örneği oluşturulmaz.
        try:
            from . import hedef_deposu as _hd_is97
            if _wss is not None:
                _hd_is97.DEPO.dron_yonetici_ata(_wss.dron)
        except BaseException as _e_is97:
            print("[IS97] Hedef deposu dron baglantisi kurulamadi: %s" %
                  _e_is97)

        class GoktunguHttpHandler(http.server.SimpleHTTPRequestHandler):
            """Statik dosyalar + /tile/ proxy + /ai/tespit bildirimi."""
            def log_message(self, *a, **k):
                pass

            def list_directory(self, path):
                """Dizin listelemesi KAPALI (BULGU_04).

                Varsayilan `SimpleHTTPRequestHandler` istenen dizinin
                icerigini HTML olarak dokuyordu; olculen vaka:
                /app/veri/ istegi `pg.json` baglantisini gosteriyordu
                ve dosya veritabani parolasini iceriyordu. Saldirganin
                dosya adi tahmin etmesi gerekmiyordu.

                index.html sunumu ETKILENMEZ: `send_head` once
                `index.html` arar, bulursa buraya hic gelmez.
                """
                self.send_error(404, "Bulunamadi")
                return None

            def translate_path(self, path):
                """v2.4.52: web koku disindaki dizinleri esler.

                Yeni klasor yapisinda HTTP koku `assets/web`, kullanici
                verisi ise `veri/` altindadir. Arayuz avatarlari
                `avatars/<dosya>` olarak ister (bu yol veritabaninda
                kayitli; degistirilirse mevcut kayitlar bozulur).
                Bu yuzden istek yolu KORUNUR ve dosya sistemi tarafinda
                gercek konuma cevrilir.

                Eski duz yapida bu klasorler zaten web kokunun
                altindadir; esleme yine dogru dosyayi verir, dolayisiyla
                iki yapida da tek kod yolu calisir.

                OLCULEN KUSUR (v2.4.52): ilk yazimda yalnizca
                `/avatars/` eslenmisti. `ai_kutuphane.js` yuz
                fotograflarini `im.src = "/" + y.dosya` ile
                `/ai_yuzler/...` olarak ister (uc yerde). Yeni yapida
                bu istekler 404 donuyordu ve KONSOLA HICBIR HATA
                DUSMUYORDU: AI yuz kutuphanesindeki butun fotograflar
                sessizce kirik gorunuyordu. Bu yuzden esleme tek tek
                yol yazmak yerine listeden uretilir.
                """
                temiz = path.split("?", 1)[0].split("#", 1)[0]
                for onek, klasor in _VERI_ESLEME:
                    if temiz.startswith(onek):
                        ad = os.path.basename(temiz)
                        # Dizin gezinmesini engelle: yalnizca dosya adi.
                        if ad and ad not in (".", ".."):
                            return os.path.join(klasor, ad)
                return super().translate_path(path)

            def end_headers(self):
                # v2.4.24: HTML dosyalari ASLA onbelleklenmez.
                #
                # Alt kaynaklar (js/css) `?v=SURUM` etiketi ile
                # onbellekten korunur; ancak etiketleri iceren HTML'in
                # kendisi onbellege dustugunde tarayici ESKI etiketleri
                # okur ve guncellemeler hic gorunmez. Olculen vaka:
                # sunucu 2.4.24 verirken sayfa 2.4.23 gosteriyordu ve
                # yalnizca elle sert yenileme ile duzeliyordu.
                try:
                    yol = self.path.split("?")[0]
                    if (yol.endswith(".html") or yol.endswith("/")
                            or yol == ""):
                        self.send_header("Cache-Control",
                                         "no-store, must-revalidate")
                        self.send_header("Pragma", "no-cache")
                        self.send_header("Expires", "0")
                except Exception:
                    pass
                super().end_headers()

            # ---------------------------------------------------------
            # IS9B-OTURUM-DEVRI: GET /api/oturum/devir
            # ---------------------------------------------------------
            def _devir_yanit(self, sozluk, kod=200, ek_basliklar=None):
                """JSON yanit yazar. Onbellek KAPALIDIR.

                Devir yaniti bir OTURUM JETONU tasir; ara onbellek veya
                tarayici onbellegi bunu saklarsa jeton baska bir
                kullaniciya sunulabilir. `no-store` bu yuzden zorunlu.
                """
                govde = json.dumps(sozluk, ensure_ascii=False).encode(
                    "utf-8")
                self.send_response(kod)
                self.send_header("Content-Type",
                                 "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(govde)))
                self.send_header("Cache-Control",
                                 "no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                for baslik, deger in (ek_basliklar or []):
                    self.send_header(str(baslik), str(deger))
                self.end_headers()
                if self.command != "HEAD":
                    try:
                        self.wfile.write(govde)
                    except BrokenPipeError:
                        pass

            @staticmethod
            def _cerez_oku(ham, ad):
                """`Cookie` basligindan tek bir cerezi ayiklar.

                `http.cookies` KULLANILMAZ: bozuk veya standart disi bir
                cerez tum basligin ayristirilmasini dusurebilir ve
                aradigimiz cerez okunamaz hale gelir. Elle ayirma, diger
                cerezlerin bicimine bagimsiz kalir.
                """
                for parca in str(ham or "").split(";"):
                    p = parca.strip()
                    if not p or "=" not in p:
                        continue
                    a, _, d = p.partition("=")
                    if a.strip() == ad:
                        import urllib.parse as _up
                        return _up.unquote(d.strip())
                return None

            def _kk_http_denetle(self, uc):
                """KK_APP_DEVIR_v1: HTTP ucu icin kaba kuvvet denetimi.

                Bloklu ise 429 + `Retry-After` yazar ve True doner.

                ES ADRESI: HTTP tarafinda `self.client_address[0]`
                vekil bacagini (`127.0.0.1`) gosterir. WS tarafiyla
                AYNI sozlesme uygulanir: es yerelse ve
                `X-Forwarded-For` varsa basliktaki ilk adres alinir,
                cunku o basligi kendi birinci katman vekilimiz yazar
                ve istemciden geleni ATAR.
                """
                if _KK is None:
                    return False
                try:
                    es = str(self.client_address[0] or "")
                except Exception:
                    return False
                if not es:
                    return False
                try:
                    if _KK.yerel_mi(es):
                        ileri = str(self.headers.get("X-Forwarded-For")
                                    or self.headers.get("X-Real-IP") or "")
                        if ileri:
                            es = ileri.split(",")[0].strip()
                except Exception:
                    pass
                try:
                    engel = _KK.denetle(es, uc, "")
                except Exception:
                    return False
                if not engel:
                    return False
                kalan, sebep = engel
                govde = __import__("json").dumps({
                    "tamam": False,
                    "hata": ("Cok fazla deneme. %d saniye sonra "
                             "yeniden deneyin." % int(kalan)),
                    "kilit": True, "kalan": int(kalan), "sebep": sebep,
                }).encode("utf-8")
                try:
                    self.send_response(429)
                    self.send_header("Content-Type",
                                     "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(govde)))
                    self.send_header("Retry-After", str(int(kalan)))
                    self.end_headers()
                    self.wfile.write(govde)
                except Exception:
                    pass
                return True

            def _kk_http_sonuc(self, uc, basarili):
                """KK_APP_DEVIR_v1: HTTP ucu sonucunu sayaclara yazar."""
                if _KK is None:
                    return
                try:
                    es = str(self.client_address[0] or "")
                    if _KK.yerel_mi(es):
                        ileri = str(self.headers.get("X-Forwarded-For")
                                    or self.headers.get("X-Real-IP") or "")
                        if ileri:
                            es = ileri.split(",")[0].strip()
                    if not es:
                        return
                    if basarili:
                        _KK.basarili(es, uc, "")
                    else:
                        _KK.basarisiz(es, uc, "")
                except Exception:
                    pass

            def _oturum_devir(self):
                """Kurumsal panel oturumunu App oturumuna devreder.

                AKIS:
                  1. `goktungu_firma` cerezini oku
                  2. Merkez `kullanici_oturumlari` tablosunda dogrula
                  3. App oturum jetonu uret (WSSunucusu._jeton_uret)
                  4. {tamam, eposta, jeton} dondur

                MERKEZ UYGULAMA KORUMASI: kapali devre kurulumda
                (`merkez_kipinde()` yanlis) uc 404 doner. Boylece
                lisansli firmanin kendi kurulumunda merkez
                veritabanina hic sorulmaz ve uc yuzeyi genislemez.

                GUVENLIK: bu uc PAROLA KABUL ETMEZ ve parametre
                ALMAZ. Tek girdisi tarayicinin gonderdigi cerezdir;
                cerez `HttpOnly` oldugu icin sayfa betikleri onu
                okuyamaz, yalnizca tarayici tasir.
                """
                try:
                    from . import merkez_kimlik as _mk
                except Exception:
                    self.send_error(404, "Bulunamadi")
                    return None
                # Kapali devre: uc HIC var olmaz.
                try:
                    if not _mk.merkez_kipinde():
                        self.send_error(404, "Bulunamadi")
                        return None
                except Exception:
                    self.send_error(404, "Bulunamadi")
                    return None
                # KK_APP_DEVIR_v1: kaynak tuketme korumasi. Kapali devre
                # denetiminden SONRA gelir; kapali devrede uc 404
                # doner ve sayac hic kirlenmez.
                if self._kk_http_denetle("/api/oturum/devir"):
                    return None
                jeton = self._cerez_oku(self.headers.get("Cookie"),
                                        "goktungu_firma")
                if not jeton:
                    self._devir_yanit(
                        {"tamam": False, "hata": "Kurumsal oturum yok"},
                        200)
                    return None
                kul, hata = _mk.oturum_coz(jeton)
                if not kul:
                    # KK_APP_DEVIR_v1: gecersiz cerez = basarisiz deneme.
                    # `jeton yok` durumu SAYILMAZ (yukarida ayri dal):
                    # cerezi hic olmayan mesru ziyaretci her sayfa
                    # acilisinda bir kez ugrar ve cezalandirilmamali.
                    self._kk_http_sonuc("/api/oturum/devir", False)
                    self._devir_yanit(
                        {"tamam": False,
                         "hata": str(hata or "Oturum gecersiz")}, 200)
                    return None
                eposta = str(kul.get("eposta") or "").strip().lower()
                if _wss is None:
                    # WS ornegi gecirilmemis: jeton uretilemez. 503
                    # doner cunku bu bir YAPILANDIRMA eksigidir,
                    # kullanicinin kimlik sorunu DEGILDIR.
                    self._devir_yanit(
                        {"tamam": False,
                         "hata": "Oturum devri yapilandirilmamis"}, 503)
                    return None
                try:
                    app_jeton = _wss._jeton_uret(eposta, "panel devri")
                except Exception as e:
                    self._devir_yanit(
                        {"tamam": False,
                         "hata": "Jeton uretilemedi: %s" % e}, 500)
                    return None
                if not app_jeton:
                    self._devir_yanit(
                        {"tamam": False,
                         "hata": "Jeton uretilemedi"}, 500)
                    return None
                # KK_APP_DEVIR_v1
                self._kk_http_sonuc("/api/oturum/devir", True)
                self._devir_yanit({"tamam": True, "eposta": eposta,
                                   "jeton": app_jeton}, 200)
                return None

            def _ic_yetkili(self):
                """Merkez→App iç kanalında eş ve paylaşılan sır denetimi."""
                import hmac
                import ipaddress
                try:
                    es = str(self.client_address[0] or "")
                    if not ipaddress.ip_address(es).is_loopback:
                        self._devir_yanit(
                            {"tamam": False, "hata": "yalniz loopback"}, 403)
                        return False
                except BaseException:
                    self._devir_yanit(
                        {"tamam": False, "hata": "gecersiz es"}, 403)
                    return False
                beklenen = str(os.environ.get("GOKTUNGU_IC_ANAHTAR") or "")
                gelen = str(self.headers.get("X-Ic-Anahtar") or "")
                if (len(beklenen) < 24 or
                        not hmac.compare_digest(gelen, beklenen)):
                    self._devir_yanit(
                        {"tamam": False, "hata": "ic kanal yetkisiz"}, 403)
                    return False
                return True

            def _ic_json_oku(self, sinir=512 * 1024):
                """Sınırlı JSON gövdesi okur; büyük/bozuk gövdeyi reddeder."""
                try:
                    boy = int(self.headers.get("Content-Length", "-1"))
                except (TypeError, ValueError):
                    boy = -1
                if boy < 0:
                    self._devir_yanit(
                        {"tamam": False, "hata": "Content-Length gerekli"},
                        411)
                    return None
                if boy > int(sinir):
                    self._devir_yanit(
                        {"tamam": False, "hata": "govde cok buyuk"}, 413)
                    return None
                tur = str(self.headers.get("Content-Type") or "")
                if tur and not tur.lower().startswith("application/json"):
                    self._devir_yanit(
                        {"tamam": False, "hata": "JSON gerekli"}, 415)
                    return None
                try:
                    veri = json.loads(self.rfile.read(boy) or b"{}")
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._devir_yanit(
                        {"tamam": False, "hata": "bozuk JSON"}, 400)
                    return None
                if not isinstance(veri, dict):
                    self._devir_yanit(
                        {"tamam": False, "hata": "JSON nesnesi gerekli"},
                        400)
                    return None
                return veri

            @staticmethod
            def _ic_sayi(deger, varsayilan=0.0):
                import math as _math
                try:
                    sonuc = float(deger)
                    return sonuc if _math.isfinite(sonuc) else varsayilan
                except (TypeError, ValueError):
                    return varsayilan

            def _ic_kamera_kaynaklari(self):
                """Doğrulanmış firma için kesin sahipli lokasyon/dron listesi."""
                if not self._ic_yetkili():
                    return None
                veri = self._ic_json_oku(16 * 1024)
                if veri is None:
                    return None
                try:
                    firma_id = int(veri.get("firma_id"))
                    if firma_id <= 0:
                        raise ValueError
                except (TypeError, ValueError):
                    self._devir_yanit(
                        {"tamam": False, "hata": "firma_id gerekli"}, 400)
                    return None
                if _wss is None:
                    self._devir_yanit(
                        {"tamam": False, "hata": "canli App baglantisi yok"},
                        503)
                    return None
                try:
                    from . import veritabani as _vti
                    lok_ham = _wss.lokasyonlar.yukle(firma_id)
                    dron_ham = _vti.dron_kaynaklari_listele(firma_id)
                    simdi = time.time()
                    canli = {}
                    with _wss.dron.kilit:
                        for d in _wss.dron.dronlar.values():
                            uid = str((d or {}).get("uid") or "").strip()
                            if not uid:
                                continue
                            son = self._ic_sayi(d.get("son_mesaj"), 0.0)
                            canli[uid] = {
                                "bagli": bool(son and simdi - son <= 8.0),
                                "son_gorulme": son,
                            }
                    lokasyonlar = []
                    for x in lok_ham[:500]:
                        lat = self._ic_sayi(x.get("lat"), None)
                        lon = self._ic_sayi(x.get("lon"), None)
                        if lat is None or lon is None:
                            continue
                        lokasyonlar.append({
                            "id": str(x.get("id") or "")[:120],
                            "ad": str(x.get("ad") or "")[:160],
                            "lat": lat, "lon": lon,
                            "yukseklik": self._ic_sayi(
                                x.get("yukseklik"), 0.0),
                        })
                    dronlar = []
                    for x in dron_ham[:500]:
                        uid = str(x.get("uid") or "").strip()[:120]
                        if not uid:
                            continue
                        c = canli.get(uid) or {}
                        son_db = self._ic_sayi(
                            x.get("son_gorulme_ts"), 0.0)
                        son = max(son_db,
                                  self._ic_sayi(c.get("son_gorulme"), 0.0))
                        dronlar.append({
                            "uid": uid,
                            "ad": str(x.get("isim") or uid)[:160],
                            "bagli": bool(c.get("bagli")),
                            "son_gorulme": son,
                        })
                except BaseException as e:
                    print("[IS97] Kaynak snapshot hatasi: %s" % e)
                    self._devir_yanit(
                        {"tamam": False, "hata": "kaynaklar okunamadi"},
                        500)
                    return None
                self._devir_yanit({
                    "tamam": True, "zaman": time.time(),
                    "lokasyonlar": lokasyonlar, "dronlar": dronlar,
                }, 200)
                return None

            def _ic_hedef_al(self):
                """Doğrulanmış merkez oturum bağlamındaki hedefi tekil depoya yazar."""
                if not self._ic_yetkili():
                    return None
                veri = self._ic_json_oku(512 * 1024)
                if veri is None:
                    return None
                try:
                    firma_id = int(veri.get("firma_id"))
                    ornek_id = int(veri.get("ornek_id"))
                    if firma_id <= 0 or ornek_id <= 0:
                        raise ValueError
                except (TypeError, ValueError):
                    self._devir_yanit(
                        {"tamam": False,
                         "hata": "firma_id ve ornek_id gerekli"}, 400)
                    return None
                paket = veri.get("paket")
                if not isinstance(paket, dict) or paket.get("tur") != "hedef":
                    self._devir_yanit(
                        {"tamam": False, "hata": "hedef paketi gerekli"},
                        400)
                    return None
                try:
                    from . import hedef_deposu as _hd
                    tamam = _hd.DEPO.yaz(
                        ornek_id,
                        str(veri.get("kopru_ad") or "")[:160],
                        paket, firma_id=firma_id,
                        kurulum_uid=str(veri.get("kurulum_uid") or "")[:160])
                except BaseException as e:
                    print("[IS97] Ic hedef aktarim hatasi: %s" % e)
                    tamam = False
                # IS99: Aday olayı ham HTTP gövdesinden kurulmaz. Yazılan
                # hedef, firma kapsamlı depodan köprü:kamera:iz anahtarıyla
                # yeniden okunur; yalnız taze ``yerel_secili`` iz yöneticinin
                # App ekranında tek-seferlik angajman adayı olur.
                aday_sayisi = 0
                if tamam and _wss is not None:
                    try:
                        for kamera in (paket.get("kameralar") or [])[:64]:
                            if not isinstance(kamera, dict):
                                continue
                            kid = kamera.get("kamera")
                            for ham_hedef in (kamera.get("hedefler") or [])[:128]:
                                if (not isinstance(ham_hedef, dict) or
                                        not ham_hedef.get("yerel_secili")):
                                    continue
                                baglam = _hd.DEPO.hedef_baglam_bul(
                                    ornek_id, kid, ham_hedef.get("iz"), firma_id)
                                if baglam and _wss.goruntu_angajman_adayi_yayinla(
                                        firma_id, baglam):
                                    aday_sayisi += 1
                    except BaseException as e:
                        print("[IS99] Angajman adayi yayin hatasi: %s" %
                              type(e).__name__)
                self._devir_yanit(
                    {"tamam": bool(tamam), "aday_sayisi": aday_sayisi,
                     "hata": None if tamam else "hedef reddedildi"},
                    200 if tamam else 400)
                return None

            def _ic_goruntu_kare_al(self):
                """IS99: Merkezden yalnız loopback+sır ile geçmiş karesi alır."""
                if not self._ic_yetkili():
                    return None
                veri = self._ic_json_oku(192 * 1024)
                if veri is None:
                    return None
                try:
                    firma_id = int(veri.get("firma_id"))
                    ornek_id = int(veri.get("ornek_id"))
                    if firma_id <= 0 or ornek_id <= 0:
                        raise ValueError
                except (TypeError, ValueError):
                    self._devir_yanit(
                        {"tamam": False, "hata": "firma/ornek gerekli"}, 400)
                    return None
                paket = veri.get("paket")
                try:
                    kayit, hata = goruntu_gecmisi.kaydet(
                        firma_id, ornek_id,
                        str(veri.get("kurulum_uid") or "")[:160], paket)
                except BaseException as e:
                    print("[IS99] Gecmis kare saklama hatasi: %s" %
                          type(e).__name__)
                    kayit, hata = None, "kare saklanamadi"
                if not kayit:
                    self._devir_yanit(
                        {"tamam": False, "hata": hata or "kare reddedildi"},
                        400)
                    return None
                kayit["url"] = goruntu_gecmisi.url_uret(kayit, 90)
                if _wss is not None:
                    try:
                        _wss.goruntu_kare_yayinla(firma_id, kayit)
                    except BaseException as e:
                        print("[IS99] Gecmis kare yayin hatasi: %s" %
                              type(e).__name__)
                self._devir_yanit({"tamam": True, "id": kayit["id"]}, 200)
                return None

            def _goruntu_kare_sun(self):
                """Kısa ömürlü HMAC URL ile tek geçmiş JPEG'ini sunar."""
                try:
                    q = urllib.parse.parse_qs(
                        urllib.parse.urlsplit(self.path).query)
                    ham, hata = goruntu_gecmisi.dosya_oku(
                        (q.get("id") or [""])[0],
                        (q.get("firma") or [""])[0],
                        (q.get("son") or [""])[0],
                        (q.get("imza") or [""])[0])
                except BaseException:
                    ham, hata = None, "gecersiz istek"
                if ham is None:
                    self.send_error(404, "Kare bulunamadi")
                    return None
                etag = '"sha256-' + __import__("hashlib").sha256(ham).hexdigest() + '"'
                if self.headers.get("If-None-Match") == etag:
                    self.send_response(304)
                    self.send_header("ETag", etag)
                    self.send_header("Cache-Control", "private, max-age=15")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("Referrer-Policy", "no-referrer")
                    self.end_headers()
                    return None
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(ham)))
                self.send_header("ETag", etag)
                self.send_header("Cache-Control", "private, max-age=15")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Security-Policy", "default-src 'none'")
                self.end_headers()
                if self.command != "HEAD":
                    try:
                        self.wfile.write(ham)
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                return None

            # ---------------------------------------------------------
            # IS96: GET/HEAD /api/app/sirket_logo
            # ---------------------------------------------------------
            def _sirket_logo_sun(self):
                """Firma logosunu WS paketinden ayri ve onbellekli sunar."""
                try:
                    ayar_yonetici = getattr(_wss, "ayarlar", None)
                    logo = (ayar_yonetici.sirket_logo()
                            if ayar_yonetici is not None else None)
                except BaseException as e:
                    # Ham logo veya ayrintili cozumleme verisi gunluge girmez.
                    print("[IS96] Sirket logosu okunamadi: %s" % type(e).__name__)
                    logo = None
                if logo is None:
                    self.send_error(404, "Logo bulunamadi")
                    return None

                ham, mime, ozet = logo
                etag = '"sha256-' + ozet + '"'
                surum = ""
                if "?" in self.path:
                    for parca in self.path.split("?", 1)[1].split("&"):
                        if parca.startswith("v="):
                            surum = parca[2:]
                            break
                kalici = surum == ozet[:16]
                onbellek = ("public, max-age=31536000, immutable"
                            if kalici else
                            "public, max-age=0, must-revalidate")

                if self.headers.get("If-None-Match") == etag:
                    self.send_response(304)
                    self.send_header("ETag", etag)
                    self.send_header("Cache-Control", onbellek)
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    return None

                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(ham)))
                self.send_header("ETag", etag)
                self.send_header("Cache-Control", onbellek)
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                if self.command != "HEAD":
                    try:
                        self.wfile.write(ham)
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                return None

            def _istemci_yerel_kip(self):
                """Kopru HTTP uyumluluk yuzeyini yalniz yerel Merkezde acar."""
                try:
                    from . import merkez_kimlik as _mk_istemci
                    return not bool(_mk_istemci.merkez_kipinde())
                except Exception:
                    return False

            def _istemci_kullanici_dogrula(self, veri, uc):
                """Parolayi tek dogruluk kaynagi olan WSSunucusu ile dogrular."""
                if _wss is None:
                    self._devir_yanit(
                        {"tamam": False,
                         "hata": "Yerel kimlik dogrulama hazir degil"}, 503)
                    return None
                eposta = str((veri or {}).get("eposta") or "").strip().lower()
                sifre = str((veri or {}).get("sifre") or "")
                if (not eposta or "@" not in eposta or len(eposta) > 254 or
                        not sifre or len(sifre) > 1024):
                    self._kk_http_sonuc(uc, False)
                    self._devir_yanit(
                        {"tamam": False,
                         "hata": "E-posta veya sifre hatali"}, 401)
                    return None
                try:
                    kul, hata = _wss._kimlik_dogrula(eposta, sifre)
                except Exception:
                    self._devir_yanit(
                        {"tamam": False,
                         "hata": "Yerel kimlik dogrulama kullanilamiyor"},
                        503)
                    return None
                if not kul:
                    self._kk_http_sonuc(uc, False)
                    self._devir_yanit(
                        {"tamam": False,
                         "hata": str(hata or "E-posta veya sifre hatali")},
                        401)
                    return None
                self._kk_http_sonuc(uc, True)
                sonuc = dict(kul)
                sonuc.pop("sifre", None)
                sonuc["eposta"] = eposta
                sonuc["rol"] = str(sonuc.get("rol") or "kullanici")
                # Kapali devre Merkez tek kuruma aittir. Yerel kullanici
                # tablosunda firma sutunu bulunmadigi icin kararlı yerel
                # firma kimligi uretilir; parola veya ozet ASLA donmez.
                sonuc["firma_id"] = int(sonuc.get("firma_id") or 1)
                sonuc["firma_kisa_ad"] = str(
                    sonuc.get("firma_kisa_ad") or "Yerel Merkez")
                sonuc["firma_unvan"] = str(
                    sonuc.get("firma_unvan") or sonuc["firma_kisa_ad"])
                return sonuc

            def _kamera_istegi_ayni_origin_mi(self):
                """Kimlikli kamera uçları için tarayıcı origin eşitliğini ister.

                Bu kontrol CORS yerine geçmez; `Authorization` başlığıyla
                birlikte çapraz kaynaklı form/fetch isteklerini reddeden ikinci
                katmandır. Host/origin uymazsa başarısız-kapalı davranır.
                """
                origin = str(self.headers.get("Origin") or "").strip()
                host = str(self.headers.get("Host") or "").strip()
                if not origin or not host or len(origin) > 512 or len(host) > 512:
                    return False
                try:
                    ayrik = urllib.parse.urlsplit(origin)
                    return (ayrik.scheme in ("http", "https") and
                            bool(ayrik.netloc) and
                            hmac.compare_digest(ayrik.netloc, host))
                except Exception:
                    return False

            def _kamera_guvenli_ulasim_mi(self):
                """Uzaktaki istemciye yalnız TLS ile kamera çerezi verir."""
                try:
                    es = ipaddress.ip_address(str(self.client_address[0]))
                    if es.is_loopback:
                        # Yerel http://127.0.0.1 kapalı devre kurulum için
                        # desteklenir. Bu trafik makine dışına çıkmaz.
                        return True
                    return isinstance(self.connection, ssl.SSLSocket)
                except Exception:
                    return False

            def _istemci_kamera_oturum(self):
                """POST /api/istemci/kamera_oturum — HttpOnly MJPEG yetkisi."""
                if not self._istemci_yerel_kip():
                    self.send_error(404, "Bulunamadi")
                    return None
                uc = "/api/istemci/kamera_oturum"
                if self._kk_http_denetle(uc):
                    return None
                if (not self._kamera_istegi_ayni_origin_mi() or
                        not self._kamera_guvenli_ulasim_mi()):
                    self._kk_http_sonuc(uc, False)
                    self._devir_yanit({"tamam": False,
                                       "hata": "Kamera oturum istegi reddedildi"},
                                      403)
                    return None
                yetki = str(self.headers.get("Authorization") or "")
                if not yetki.startswith("Bearer ") or len(yetki) > 512:
                    self._kk_http_sonuc(uc, False)
                    self._devir_yanit({"tamam": False,
                                       "hata": "Kamera oturum kimligi gerekli"},
                                      401)
                    return None
                try:
                    kullanici = (_wss._jeton_dogrula(yetki[7:].strip())
                                if _wss is not None else None)
                except Exception:
                    kullanici = None
                if not kullanici:
                    self._kk_http_sonuc(uc, False)
                    self._devir_yanit({"tamam": False,
                                       "hata": "Kamera oturum kimligi gecersiz"},
                                      401)
                    return None
                ham = self.server.goktungu_http._kamera_oturum_ac(kullanici)
                if not ham:
                    self._devir_yanit({"tamam": False,
                                       "hata": "Kamera oturumu olusturulamadi"},
                                      503)
                    return None
                self._kk_http_sonuc(uc, True)
                cerez = ("goktungu_kamera=" + ham +
                         "; Path=/kamera/; HttpOnly; SameSite=Strict; Max-Age=" +
                         str(self.server.goktungu_http._kamera_oturum_sure))
                # Ters vekil TLS sonlandırsa bile tarayıcıya güvenli işaretli
                # çerez gönderilir. Yerel http://127.0.0.1 kurulumu ise
                # `Secure` almadan çalışır; LAN üzerinde düz HTTP zaten red.
                if (str(self.headers.get("X-Forwarded-Proto") or "").split(
                        ",", 1)[0].strip().lower() == "https" or
                        isinstance(self.connection, ssl.SSLSocket)):
                    cerez += "; Secure"
                self._devir_yanit({"tamam": True}, 200,
                                  [("Set-Cookie", cerez)])
                return None

            def _istemci_giris(self):
                """POST /api/istemci/giris — Köprü 1.7.9 yerel giriş ucu."""
                if not self._istemci_yerel_kip():
                    self.send_error(404, "Bulunamadi")
                    return None
                uc = "/api/istemci/giris"
                if self._kk_http_denetle(uc):
                    return None
                veri = self._ic_json_oku(sinir=16 * 1024)
                if veri is None:
                    return None
                kul = self._istemci_kullanici_dogrula(veri, uc)
                if not kul:
                    return None
                self._devir_yanit({"tamam": True, "kullanici": kul}, 200)
                return None

            def _istemci_sunucu_kayit(self):
                """POST /api/istemci/sunucu_kayit — tek seferlik gizli uretir."""
                if not self._istemci_yerel_kip():
                    self.send_error(404, "Bulunamadi")
                    return None
                uc = "/api/istemci/sunucu_kayit"
                if self._kk_http_denetle(uc):
                    return None
                veri = self._ic_json_oku(sinir=32 * 1024)
                if veri is None:
                    return None
                kul = self._istemci_kullanici_dogrula(veri, uc)
                if not kul:
                    return None

                yenile = bool(veri.get("yenile"))
                if yenile and str(kul.get("rol") or "").lower() != "yonetici":
                    self._devir_yanit(
                        {"tamam": False,
                         "hata": "Kimlik yenileme icin yonetici yetkisi gerekli"},
                        403)
                    return None

                ad = str(veri.get("ad") or "").strip()
                makine = str(veri.get("makine_adi") or "").strip()
                platform = str(veri.get("platform") or "").strip()
                surum = str(veri.get("surum") or "").strip()
                urun = str(veri.get("urun") or "kopru").strip().lower()
                aciklama = str(veri.get("aciklama") or "").strip()
                eski_uid = str(veri.get("kurulum_uid") or "").strip()
                if (not ad or len(ad) > 160 or len(makine) > 255 or
                        len(platform) > 80 or len(surum) > 40 or
                        len(aciklama) > 1000 or len(eski_uid) > 160):
                    self._devir_yanit(
                        {"tamam": False,
                         "hata": "Sunucu kayit alanlari gecersiz"}, 400)
                    return None
                try:
                    from . import kopru_kabul as _kkabul_istemci
                    sonuc, hata, kod = _kkabul_istemci.istemci_sunucu_kaydet(
                        ad=ad, aciklama=aciklama, makine_adi=makine,
                        platform=platform, surum=surum, urun=urun,
                        yenile=yenile, eski_uid=eski_uid)
                except Exception:
                    self._devir_yanit(
                        {"tamam": False,
                         "hata": "Yerel sunucu kaydi olusturulamadi"}, 500)
                    return None
                if hata:
                    govde = dict(sonuc or {})
                    govde.update({"tamam": False, "hata": str(hata)})
                    self._devir_yanit(govde, int(kod or 400))
                    return None
                sonuc = dict(sonuc or {})
                sonuc.update({
                    "tamam": True,
                    "firma_id": int(kul.get("firma_id") or 1),
                    "firma_kisa_ad": str(
                        kul.get("firma_kisa_ad") or "Yerel Merkez"),
                })
                self._devir_yanit(sonuc, 200)
                return None

            # v2.4.166: "dosya" protokolu icin video yukleme ucu.
            # Kimlik: canli kamera goruntusuyle ayni HttpOnly cerez
            # (goktungu_kamera; girisle uretilir). Dosya adi X-Dosya-Ad
            # basligindan gelir; yalniz taban ad + guvenli karakterler +
            # video uzantisi kabul edilir (yol gezinme engeli). Icerik
            # parcali okunup diske yazilir (bellek tasmasi engeli).
            _VIDEO_UZANTILAR = (".mp4", ".m4v", ".mov", ".avi", ".mkv",
                                ".webm", ".ts")
            _VIDEO_AZAMI_BAYT = 512 * 1024 * 1024

            def _ai_hata_bildir(self, kaynak, exc):
                """v2.4.179: AI ucu (/ai/tespit,/ai/kutular,/ai/takip) hata
                verince hem log dosyasina (traceback + flush) hem de
                CANLI CALISAN arayuz KONSOL paneline (WS uzerinden aninda)
                yazar. Log dosyasi export/tamponlama belirsizligine karsi
                ikinci, BAGIMSIZ bir gorunurluk yolu — kullanici hatayi
                dosya disa aktarmadan doğrudan ekrandan okuyabilir."""
                import traceback as _tb
                iz = _tb.format_exc()
                print(f"[AI] {kaynak} isleme hatasi: {exc}\n{iz}", flush=True)
                try:
                    son_satir = [s for s in iz.strip().splitlines() if s][-1]
                except IndexError:
                    son_satir = str(exc)
                try:
                    self.server.goktungu_http.konsol(
                        "AI", f"{kaynak} isleme hatasi: {exc} ({son_satir})",
                        "hata")
                except Exception:
                    pass

            def _kamera_video_yukle(self):
                ham = self._cerez_oku(self.headers.get("Cookie"),
                                      "goktungu_kamera")
                if not self.server.goktungu_http._kamera_oturum_gecerli(ham):
                    self.send_error(401, "Kamera oturumu gerekli")
                    return
                try:
                    boy = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    boy = 0
                if boy <= 0:
                    self.send_error(400, "Bos govde")
                    return
                if boy > self._VIDEO_AZAMI_BAYT:
                    self.send_error(413, "Dosya cok buyuk (ust sinir 512 MB)")
                    return
                from urllib.parse import unquote
                ad = os.path.basename(
                    unquote(self.headers.get("X-Dosya-Ad") or ""))
                ad = re.sub(r"[^A-Za-z0-9._-]+", "_", ad).strip("._")
                kok_ad, uzanti = os.path.splitext(ad)
                if not kok_ad or uzanti.lower() not in self._VIDEO_UZANTILAR:
                    self.send_error(
                        415, "Yalniz video dosyalari"
                             " (mp4/m4v/mov/avi/mkv/webm/ts)")
                    return
                klasor = _veri_yolu("kamera_videolar")
                os.makedirs(klasor, exist_ok=True)
                hedef = os.path.join(klasor, ad)
                if os.path.exists(hedef):
                    ad = "%s_%d%s" % (kok_ad[:80], int(time.time()),
                                      uzanti.lower())
                    hedef = os.path.join(klasor, ad)
                gecici = hedef + ".yukleniyor"
                kalan = boy
                try:
                    with open(gecici, "wb") as f:
                        while kalan > 0:
                            parca = self.rfile.read(min(256 * 1024, kalan))
                            if not parca:
                                break
                            f.write(parca)
                            kalan -= len(parca)
                    if kalan > 0:
                        os.remove(gecici)
                        self.send_error(400, "Eksik govde")
                        return
                    os.replace(gecici, hedef)
                except OSError as e:
                    try:
                        os.remove(gecici)
                    except OSError:
                        pass
                    self.send_error(500, "Yazilamadi: %s" % e)
                    return
                govde = json.dumps({"tamam": True, "dosya": ad}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(govde)))
                self.end_headers()
                self.wfile.write(govde)

            def do_POST(self):
                yol = self.path.split("?", 1)[0]
                if yol == "/api/istemci/giris":
                    return self._istemci_giris()
                # v2.4.166: "dosya" kamera kaynagi icin video yukleme
                if yol == "/api/kamera/video_yukle":
                    return self._kamera_video_yukle()
                if yol == "/api/istemci/kamera_oturum":
                    return self._istemci_kamera_oturum()
                if yol == "/api/istemci/sunucu_kayit":
                    return self._istemci_sunucu_kayit()
                if yol == "/api/ic/kamera_kaynaklari":
                    return self._ic_kamera_kaynaklari()
                if yol == "/api/ic/hedef":
                    return self._ic_hedef_al()
                if yol == "/api/ic/goruntu_kare":
                    return self._ic_goruntu_kare_al()
                # v2.4.0: AI iscilerinden tespit bildirimi
                if self.path == "/ai/tespit" and _ai is not None:
                    try:
                        boy = int(self.headers.get("Content-Length", 0))
                        if boy > 32 * 1024 * 1024:
                            self.send_error(413)
                            return
                        veri = json.loads(self.rfile.read(boy) or b"{}")
                        _ai.tespit_isle(veri)
                        govde = b'{"tamam": true}'
                        self.send_response(200)
                        self.send_header("Content-Type",
                                         "application/json")
                        self.send_header("Content-Length",
                                         str(len(govde)))
                        self.end_headers()
                        self.wfile.write(govde)
                    except Exception as e:
                        # v2.4.179 OLCULEN KUSUR: print() cikisi log
                        # dosyasina bazi kurulumlarda GECIKMELI/HIC
                        # dusmuyordu (2.4.178'deki flush=True bile
                        # yetmedi — muhtemelen servis sarmalayicisi
                        # kendi tamponlamasini yapiyor). `self.konsol`
                        # ise ZATEN CANLI CALISAN bir yol: arayuzdeki
                        # "KONSOL" paneline WS uzerinden ANINDA duser,
                        # dosya disa aktarimi/tamponlama belirsizligine
                        # HIC bagli degildir.
                        self._ai_hata_bildir("Tespit", e)
                        try:
                            self.send_error(500)
                        except Exception:
                            pass
                    finally:
                        # v2.4.177 OLCULEN KOK NEDEN: `veritabani.baglanti()`
                        # BU IS PARCASINA (thread) ozel KALICI baglanti
                        # dondurur; ThreadingHTTPServer HER ISTEK icin YENI
                        # bir thread acar ve istek bitince thread OLUR.
                        # Baglanti burada HAVUZA IADE EDILMEZSE, thread
                        # olduğunde baglanti YETIM kalir (sizinti). Bu uc
                        # DB'ye dokunuyorsa (tespit_isle -> INSERT) havuz
                        # (varsayilan 10) dakikalar icinde dolar; sonraki
                        # TUM /ai/* istekleri "PostgreSQL baglanti havuzu
                        # dolu" ile 500 doner — AI takip/tespit sessizce
                        # sunucuya hic ulasmaz.
                        try:
                            from . import veritabani as _vt
                            _vt.baglanti_kapat()
                        except Exception:
                            pass
                    return
                # v2.4.7: AI iscilerinden canli tespit kutulari
                # (anotasyonlu MJPEG icin) — yuz eslesme adiyla
                # zenginlestirilip video proxy'sine islenir
                if self.path == "/ai/kutular" and _ai is not None:
                    try:
                        boy = int(self.headers.get("Content-Length", 0))
                        veri = json.loads(self.rfile.read(boy) or b"{}")
                        _ai.kutular_isle(veri)
                        govde = b'{"tamam": true}'
                        self.send_response(200)
                        self.send_header("Content-Type",
                                         "application/json")
                        self.send_header("Content-Length",
                                         str(len(govde)))
                        self.end_headers()
                        self.wfile.write(govde)
                    except Exception as e:
                        self._ai_hata_bildir("Kutu", e)
                        try:
                            self.send_error(500)
                        except Exception:
                            pass
                    finally:
                        # v2.4.177: bkz. /ai/tespit ustundeki not — "yuz"/
                        # "plaka" eslesmesi DB'ye dokunabilir.
                        try:
                            from . import veritabani as _vt
                            _vt.baglanti_kapat()
                        except Exception:
                            pass
                    return
                # v2.4.2: AI iscilerinden takip (tracking) konum bildirimi
                if self.path == "/ai/takip" and _ai is not None:
                    try:
                        boy = int(self.headers.get("Content-Length", 0))
                        veri = json.loads(self.rfile.read(boy) or b"{}")
                        _ai.takip_isle(veri)
                        govde = b'{"tamam": true}'
                        self.send_response(200)
                        self.send_header("Content-Type",
                                         "application/json")
                        self.send_header("Content-Length",
                                         str(len(govde)))
                        self.end_headers()
                        self.wfile.write(govde)
                    except Exception as e:
                        self._ai_hata_bildir("Takip", e)
                        try:
                            self.send_error(500)
                        except Exception:
                            pass
                    finally:
                        # v2.4.177 OLCULEN KOK NEDEN: `takip_isle` her
                        # cagrida `_kamera_dron_uid()` ile DB'ye dokunur
                        # (kameranin bagli dron_uid'i icin SELECT). Takip
                        # artik AYRI iplikte en TAZE kareyle calistigi
                        # icin bu uc saniyede birkac kez tetiklenebiliyor;
                        # baglanti HER SEFERINDE sizarsa havuz (10) SANIYELER
                        # icinde dolup tasiyor, tum "Angaje Ol/Takip Et"
                        # dugmelerinin dayandigi ai_takip yayinini kalici
                        # olarak susturuyordu. Olculen: ai_isci.log'da
                        # ardisik "Takip bildirilemedi: HTTP Error 500".
                        try:
                            from . import veritabani as _vt
                            _vt.baglanti_kapat()
                        except Exception:
                            pass
                    return
                self.send_error(404)

            def do_HEAD(self):
                """HEAD de engelden gecer ve IS96 logo ucunu destekler."""
                yol = self.path.split("?", 1)[0]
                if yol == "/api/app/sirket_logo":
                    return self._sirket_logo_sun()
                if yol == "/api/app/goruntu_kare":
                    return self._goruntu_kare_sun()
                if _statik_engelli_mi(self.path):
                    self.send_error(404, "Bulunamadi")
                    return None
                return super().do_HEAD()

            def do_GET(self):
                try:
                    if self.path.startswith("/tile/"):
                        return self._tile_sun()
                    # FAZ19-IS60B: MJPEG video, AYNI ORIGIN.
                    # `/tile/` SONRASI, statik sizinti
                    # engelinden ONCE: engel `/kamera/3`u
                    # statik dosya sanip 404 dondururdu.
                    if self.path.startswith("/kamera/"):
                        ham = self._cerez_oku(self.headers.get("Cookie"),
                                               "goktungu_kamera")
                        if not (self.server.goktungu_http._kamera_oturum_gecerli(ham)
                                or self._yerel_ai_isci_mi()):
                            self.send_error(401, "Kamera oturumu gerekli")
                            return None
                        return self._kamera_mjpeg_sun()
                    # IS9B-OTURUM-DEVRI: kurumsal panelden App'e
                    # oturum devri. `/tile/` SONRASI, statik engelden
                    # ONCE gelir: `/api/` onegi statik sunumda karsilik
                    # bulmaz ve engel denetimi bosuna kosardi.
                    if self.path.split("?")[0] == "/api/oturum/devir":
                        return self._oturum_devir()
                    # IS96: firma logosu statik dosya degildir; ayni surecte
                    # calisan tekil AyarYoneticisi tarafindan uretilir.
                    if self.path.split("?", 1)[0] == "/api/app/sirket_logo":
                        return self._sirket_logo_sun()
                    if self.path.split("?", 1)[0] == "/api/app/goruntu_kare":
                        return self._goruntu_kare_sun()
                    # SIZINTI ENGELI (BULGU_04): kaynak kod, `veri/`,
                    # sertifika ve yedek dosyalari statik sunumdan
                    # cikarilir. `/tile/` ONCE gelir: karo vekili
                    # dosya sistemine dokunmaz, onbellekten okur.
                    if _statik_engelli_mi(self.path):
                        self.send_error(404, "Bulunamadi")
                        return None
                    # v2.4.32: ikinci ekran ucus duvari.
                    # /flight ve /flight/ adresleri flight.html'e eslenir.
                    # Boylece kullanici tarayiciya yalnizca /flight yazar;
                    # uzantiya gerek kalmaz. Sorgu dizesi korunur.
                    yol = self.path.split("?")[0].rstrip("/")
                    # v2.4.192 (kullanici bildirimi: "yardim gelmiyor",
                    # 404): paket yerel /yardim/ sayfasi tasimiyor.
                    # Yerel kopya varsa o sunulur; yoksa cevrimici Destek
                    # Merkezi'ne yonlendirilir (kapali devrede bile
                    # tarayici internete cikabiliyorsa yardim acilir).
                    if yol == "/yardim" or yol.startswith("/yardim/"):
                        _kok = getattr(self, "directory", None) or os.getcwd()
                        if not os.path.isfile(os.path.join(_kok, "yardim",
                                                           "index.html")):
                            self.send_response(302)
                            self.send_header("Location",
                                             "https://support.goktungu.com/")
                            self.end_headers()
                            return None
                    if yol == "/flight":
                        kalan = self.path.split("?", 1)
                        self.path = "/flight.html"
                        if len(kalan) == 2:
                            self.path += "?" + kalan[1]
                    # v2.4.41 DUZELTME: indirilen dataflash log dosyalari
                    # diskte `dron_loglari/` altinda duruyor, ama WS cevabi
                    # arayuze `/loglar/<ad>` adresini veriyordu (bkz.
                    # log_indir komutu). Bu onek icin HTTP tarafinda esleme
                    # OLMADIGI icin indirme baglantisi 404 donuyordu:
                    # indirme motoru calisiyor, kirilan yalniz son adim.
                    # Olculdu: /dron_loglari/x.bin -> 200, /loglar/x.bin -> 404.
                    # WS cevabini degistirmek yerine burada esleme yapiyoruz;
                    # boylece eski arayuzden gelen istekler de calisir.
                    elif yol.startswith("/loglar/"):
                        self.path = "/dron_loglari/" + self.path[len("/loglar/"):]
                    # v2.4.66: KURUMSAL PANEL YONLENDIRMESI.
                    #
                    # OLCULEN KUSUR: Merkez Uygulama kurulumunda
                    # `/company/` 404 veriyordu; musteri ne pilot
                    # yonetimine ne kopru indirmesine erisemiyordu.
                    #
                    # NEDEN YONLENDIRME, NEDEN YEREL SERVIS DEGIL:
                    # panel 23 ayri `/api/firma/...` ucu cagirir
                    # (olculdu). GCS sunucusunda `/api/firma` yolu HIC
                    # yoktur - panel dosyalari pakete konsa acilir ama
                    # tek satir veri gelmez. Uclari burada yeniden
                    # yazmak kod ikizlemesi olur ve abonelik/odeme
                    # mantigini iki yere dagitir.
                    #
                    # Merkez adresi lisans dosyasindan DEGIL ayardan
                    # okunur: lisans imza sozlesmesi degismesin diye
                    # (degisirse dagitilmis tum lisanslar gecersiz olur).
                    elif yol == "/company" or yol.startswith("/company/"):
                        hedef = _merkez_panel_adresi()
                        if hedef:
                            self.send_response(302)
                            self.send_header("Location", hedef)
                            self.end_headers()
                            return None
                        # Merkez adresi tanimli degil (kapali devre):
                        # panele erisim yok, kullaniciyi bilgilendir.
                        return self._company_yok()
                    return super().do_GET()
                except (ConnectionAbortedError, ConnectionResetError,
                        BrokenPipeError):
                    # Istemci istegi iptal etti (harita kaydirma sirasinda
                    # gorunmez kalan karolar vb.) - zararsiz, sessiz gec.
                    pass

            def _company_yok(self):
                """Merkez adresi tanimsizken `/company/` icin aciklama.

                Bos 404 yerine eyleme cevrilebilir metin doner: kullanici
                panelin neden acilmadigini ve nereden ayarlayacagini
                ogrenir. Kapali devre kurulum GECERLI bir durumdur,
                kusur degildir.
                """
                govde = (
                    "<!doctype html><meta charset='utf-8'>"
                    "<title>Kurumsal Panel</title>"
                    "<style>body{background:#0b0e11;color:#cfd8e3;"
                    "font-family:system-ui,sans-serif;margin:0;"
                    "display:flex;align-items:center;"
                    "justify-content:center;height:100vh}"
                    "div{max-width:560px;padding:32px;line-height:1.7}"
                    "h1{font-size:20px;margin:0 0 16px;color:#35d0ff}"
                    "code{background:#161b22;padding:2px 6px;"
                    "border-radius:4px}</style>"
                    "<div><h1>Kurumsal Panel yapilandirilmadi</h1>"
                    "<p>Kurumsal panel (pilot yonetimi, kopru ve "
                    "Merkez Uygulama indirmeleri) merkez sunucuda "
                    "calisir. Bu kurulumda merkez sunucu adresi "
                    "tanimli degil.</p>"
                    "<p>Tanimlamak icin: <code>Program Ayarlari &rarr; "
                    "Merkez Sunucu</code> bolumune adresi girin "
                    "(ornek: <code>goktungu.com</code>).</p>"
                    "<p>Kapali devre (internetsiz) kullanimda bu panel "
                    "gerekmez; kullanici yonetimi icin "
                    "<code>Kullanici &rarr; Kullanicilar</code> "
                    "menusunu kullanin.</p></div>")
                ham = govde.encode("utf-8")
                self.send_response(503)
                self.send_header("Content-Type",
                                 "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(ham)))
                self.end_headers()
                try:
                    self.wfile.write(ham)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return None

            def handle_one_request(self):
                try:
                    super().handle_one_request()
                except (ConnectionAbortedError, ConnectionResetError,
                        BrokenPipeError):
                    self.close_connection = True

            def _yerel_ai_isci_mi(self):
                """v2.4.153: GRCOFF yerel AI iscisi canli yayini okuyabilir.

                Kosullarin HEPSI gerekir: istek geri donus (loopback)
                adresinden gelir; `X-Goktungu-AI-Isci` basligi, Merkez'in
                veri dizininde urettigi en az 32 karakterlik isci anahtariyla
                sabit-zamanli eslesir. Anahtar yalniz GRCOFF'ta (main.py
                _yerel_ai_bekci) ortama konur; GRCON'da tanimsizdir, bu yol
                orada her zaman kapalidir.
                """
                beklenen = os.environ.get("GOKTUNGU_AI_ISCI_JETON") or ""
                gelen = self.headers.get("X-Goktungu-AI-Isci") or ""
                if len(beklenen) < 32 or not gelen:
                    return False
                if str(self.client_address[0]) not in (
                        "127.0.0.1", "::1", "::ffff:127.0.0.1"):
                    return False
                return hmac.compare_digest(gelen.encode("utf-8"),
                                           beklenen.encode("utf-8"))

            def _kamera_mjpeg_sun(self):
                """`/kamera/<id>` MJPEG akisini AYNI ORIGIN uzerinden sunar.

                FAZ19-IS60B — NEDEN BURADA: merkez kipinde tarayici
                `https://goktungu.com:8801/kamera/<id>` istiyordu.
                8801 merkez sunucuda dinlenmiyor (guvenlik duvari da
                kapali) => ERR_CONNECTION_TIMED_OUT. Ustelik sayfa
                https, 8801 http: duvar acilsa bile tarayici karisik
                icerigi engellerdi.

                `/tile/` karo vekili ayni sorunu coktan cozmus ve
                calisiyor. Video ayni yolu izler; merkezin `_app_vekil`
                katmani istegi 127.0.0.1:18000'e tasir.

                Govde `video_proxy.mjpeg_yaz`da: 8801 sunucusu ile TEK
                KOD paylasilir. Kopya olsaydi ilk kare bekleme /
                makine okunabilir gerekce / bozuk boru duzeltmeleri
                bir tarafta unutulurdu.
                """
                if _vp is None:
                    # Video saglayicisi gecirilmemis: sessiz 404 yerine
                    # acik gerekce, operatorun sorunu gormesi icin.
                    from . import video_proxy as _vpm
                    _vpm.mjpeg_gerekce_yaz(
                        self, 503,
                        "video saglayicisi baglanmamis "
                        "(HttpSunucusu video_proxy=None)")
                    return
                parca = self.path.split("?")[0].strip("/").split("/")
                if len(parca) != 2:
                    self.send_error(404)
                    return
                try:
                    kid = int(parca[1])
                except ValueError:
                    self.send_error(404)
                    return
                from . import video_proxy as _vpm
                _vpm.mjpeg_yaz(self, kid, _vp, print)

            def _tile_sun(self):
                # /tile/<kaynak>/<z>/<x>/<y>  (uzanti yok sayilir)
                parca = self.path.split("?")[0].strip("/").split("/")
                if len(parca) != 5:
                    self.send_error(404)
                    return
                _etiket, kaynak, z, x, y = parca
                y = y.split(".")[0]
                try:
                    z, x, y = int(z), int(x), int(y)
                except ValueError:
                    self.send_error(404)
                    return
                veri, mime = tile_cache.tile_getir(kaynak, z, x, y)
                if veri is None:
                    # FAZ18-IS31-KARO404: eskiden burada 68 baytlik
                    # 1x1 seffaf PNG **HTTP 200 ile** donuyordu.
                    #
                    # NEDEN YANLISTI: Cesium 200 alip icerigi gecerli
                    # goruntu sanmaya calisiyor, cozemeyince belirsiz
                    # "Failed to obtain image tile" yaziyordu. Ayrica
                    # tarayici/ara katman yer tutucuyu gecerli karo
                    # sanip onbellege alabiliyordu; gercek bir ariza
                    # da sessizce siyah kare olarak goruluyordu.
                    #
                    # DOGRUSU 404: Cesium eksik karoyu duzgun karsilar,
                    # kendi seffaf yer tutucusunu kullanir ve gereksiz
                    # hata uretmez. Okyanus/kutup gibi upstream'de
                    # gercekten karo OLMAYAN bolgeler icin de dogru
                    # anlamdir.
                    self.send_error(404, "Karo yok")
                    return
                else:
                    self.send_response(200)
                    self.send_header("Content-Type", mime)
                    self.send_header("Cache-Control",
                                     "public, max-age=86400")
                self.send_header("Content-Length", str(len(veri)))
                self.end_headers()
                self.wfile.write(veri)

        handler = functools.partial(GoktunguHttpHandler,
                                    directory=self.klasor)
        socketserver.TCPServer.allow_reuse_address = True

        # HTTPS: kendinden imzali sertifika ile ayri thread'de 8443
        ctx = ssl_baglami()
        if ctx is not None:
            import threading

            def _https_calistir():
                try:
                    with socketserver.ThreadingTCPServer(
                            (self.adres, HTTPS_PORT), handler) as httpsd:
                        httpsd.socket = ctx.wrap_socket(
                            httpsd.socket, server_side=True)
                        httpsd.goktungu_http = self
                        print(f"[HTTPS] Guvenli arayuz: "
                              f"https://{self.adres}:{HTTPS_PORT}")
                        httpsd.serve_forever()
                except OSError as e:
                    print(f"[HTTPS] Port {HTTPS_PORT} acilamadi ({e}); "
                          f"yalniz http:// kullanilabilir.")

            threading.Thread(target=_https_calistir,
                             daemon=True,
                             name="https-sunucu").start()

        for port in HTTP_PORTLAR:
            try:
                with socketserver.ThreadingTCPServer((self.adres, port),
                                                     handler) as httpd:
                    httpd.daemon_threads = True
                    # v2.4.49: gercekte alinan portu kaydet. Portlar
                    # sirayla denendigi icin (HTTP_PORTLAR) 8000 dolu
                    # oldugunda sessizce 8080'e dusulur; kiosk betigi ve
                    # servis durum sorgusu bu degeri okumak zorundadir,
                    # aksi halde yanlis porta baglanir.
                    self.aktif_port = port
                    # Handler, kamera oturum deposuna yalnız bu tekil HTTP
                    # sunucu örneği üzerinden erişir; global durum yoktur.
                    httpd.goktungu_http = self
                    print(f"[HTTP] Harita arayuzu: http://{self.adres}:{port}")
                    httpd.serve_forever()
                return
            except OSError as e:
                print(f"[HTTP] Port {port} kullanilamiyor ({e}), "
                      f"siradaki deneniyor...")
        print("[HTTP] HATA: Hicbir HTTP portu acilamadi. "
              "Windows'ta rezerve portlari gormek icin:\n"
              "  netsh interface ipv4 show excludedportrange protocol=tcp")
