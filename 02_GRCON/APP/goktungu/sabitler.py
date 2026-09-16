# -*- coding: utf-8 -*-
"""GOKTUNGU sabitleri.

Port listeleri, SYSID siniflandirma tablosu, C20 protokol sabitleri ve
dosya yollari tek merkezde tutulur.
"""
import os

# ======================================================================
# YOL COZUMLEME (v2.4.52'de YENIDEN YAZILDI)
# ======================================================================
# v2.4.52'de klasor yapisi degisti (kullanici istegi):
#
#   ONCE (duz)                 SONRA (v2.4.52+)
#   ----------                 ----------------
#   main.py                    main.py
#   index.html js/ css/ lib/   assets/web/
#   goktungu/ ai_sunucu.py        assets/python/
#   veri/ harita_cache/ ...    veri/
#
# KRITIK AYRIM: v2.4.51'de `PROJE_KOKU` tek basina UC anlami
# tasiyordu ve 35 yerde kullaniliyordu:
#   (a) VERI koku      — ayarlar, ucus kayitlari, sertifika, onbellek
#   (b) WEB koku       — HTTP sunucusunun servis ettigi dizin
#   (c) paket koku     — `js/surum.js` okuma
# Yeni yapida bunlar AYRI DIZINLER oldugu icin tek sabit yetmez.
# Uc sabit tanimlanir; eski `PROJE_KOKU` adi VERI koku olarak korunur
# (30 cagri yeri degismez).
#
# `goktungu/` paketi:  <kok>/assets/python/goktungu/  (yeni)
#                   <kok>/goktungu/               (eski)
# Paketin iki ust dizini yeni yapida `<kok>/assets`, bu yuzden
# yapinin hangisi oldugu DOSYA VARLIGIYLA olculur, varsayilmaz.

_PAKET_DIZIN = os.path.dirname(os.path.abspath(__file__))      # .../goktungu
_UST1 = os.path.dirname(_PAKET_DIZIN)                          # .../python | <kok>
_UST2 = os.path.dirname(_UST1)                                 # .../assets | ust
_UST3 = os.path.dirname(_UST2)                                 # <kok>      | ust

if os.path.basename(_UST1) == "python" and \
        os.path.basename(_UST2) == "assets":
    # YENI yapi: <kok>/assets/python/goktungu
    PROJE_KOKU = _UST3
    ASSETS_KOKU = _UST2
    YAPI = "assets"
else:
    # ESKI duz yapi: <kok>/goktungu
    PROJE_KOKU = _UST1
    ASSETS_KOKU = os.path.join(_UST1, "assets")
    YAPI = "duz"

# WEB koku: HTTP sunucusunun servis ettigi dizin (index.html burada).
# Yeni yapida assets/web, eski yapida proje koku.
if YAPI == "assets":
    WEB_KOKU = os.path.join(ASSETS_KOKU, "web")
else:
    WEB_KOKU = PROJE_KOKU
# Gecis donemi guvenligi: beklenen dizinde index.html yoksa digerine
# duser. Yanlis kokle HTTP sunucusu bos sayfa servis eder ve bu
# SESSIZ bir kusurdur (sunucu ayakta, arayuz bos).
if not os.path.isfile(os.path.join(WEB_KOKU, "index.html")):
    for _aday in (os.path.join(ASSETS_KOKU, "web"), PROJE_KOKU):
        if os.path.isfile(os.path.join(_aday, "index.html")):
            WEB_KOKU = _aday
            break

# VERI koku: kullanici verisi (ucus kayitlari, ayarlar, onbellek).
# YENI yapida <kok>/veri altinda TOPLANIR; boylece dagitilan paket
# yalnizca main.py + assets/ icerir. ESKI yapida dagilmis haldedir ve
# oldugu yerde birakilir (mevcut kurulumun verisi kaybolmasin).
if YAPI == "assets":
    VERI_KOKU = os.path.join(PROJE_KOKU, "veri")
else:
    VERI_KOKU = PROJE_KOKU

# v2.4.65: `GOKTUNGU_VERI_KOKU` ile veri dizini TASINABILIR.
#
# ## NEDEN GEREKLI (Merkez Uygulama kurulumu)
#
# Merkez Uygulama `C:\Program Files\Goktungu\Merkez` altina kurulur ve
# Windows servisi olarak LocalSystem hesabiyla kosar. Program Files
# dizini YAZMAYA KAPALIDIR (UAC sanallastirmasi 64-bit servislerde
# islemez). Veri koku oraya sabitlenirse:
#   * ucus kayitlari yazilamaz,
#   * `pg.json` yazilamaz -> PostgreSQL sihirbazi HER ACILISTA basa
#     doner (kullanici bilgileri kaydedilemedigi icin),
#   * `merkez_lisans.json` okunamaz/yazilamaz -> 5.000 $ odemis
#     musteri yazilimi lisanssiz gorur.
#
# Kopru ayni sorunu `C:\ProgramData\Goktungu\Kopru` kullanarak cozdu;
# burada da kurulum programi `GOKTUNGU_VERI_KOKU`'nu
# `C:\ProgramData\Goktungu\Merkez` olarak yazar.
#
# Ortam degiskeni YOKSA davranis birebir eskisi gibidir: mevcut
# kurulumlar ve konsoldan elle calistirma etkilenmez.
_ham_veri_koku = (os.environ.get("GOKTUNGU_VERI_KOKU") or "").strip()
if _ham_veri_koku:
    try:
        os.makedirs(_ham_veri_koku, exist_ok=True)
        # Yazilabilirlik SINANIR, varsayilmaz: yazilamayan bir dizine
        # gecmek, sabit kokte kalmaktan daha kotudur (sessizce veri
        # kaybi yerine ilk yazmada catlak).
        _deneme = os.path.join(_ham_veri_koku, ".yazma_denemesi")
        with open(_deneme, "w", encoding="utf-8") as _f:
            _f.write("ok")
        os.remove(_deneme)
        VERI_KOKU = _ham_veri_koku
    except Exception as _e:
        # Sessiz kalmaz: sahada "ayarlarim kaydedilmiyor" teshisi
        # bu satir olmadan cok zordur.
        print("[SABIT] GOKTUNGU_VERI_KOKU kullanilamadi (%s): %s. "
              "Varsayilan veri koku kullanilacak: %s"
              % (_ham_veri_koku, _e, VERI_KOKU))


def _veri_yolu(*parcalar):
    """Kullanici verisi icin yol uretir.

    Yeni yapida <kok>/veri/... , eski yapida <kok>/... dondurur.
    GECIS: yeni konumda dosya YOKSA ve eski konumda VARSA, eski
    konum dondurulur. Boylece v2.4.51 kurulumu uzerine yama
    uygulandiginda kullanicinin ayarlari/ucus kayitlari kaybolmaz;
    goc betigi calismadan once de program dogru dosyayi okur.
    """
    yeni = os.path.join(VERI_KOKU, *parcalar)
    if VERI_KOKU != PROJE_KOKU:
        eski = os.path.join(PROJE_KOKU, *parcalar)
        if not os.path.exists(yeni) and os.path.exists(eski):
            return eski
    return yeni


def _veri_alt_yolu(*parcalar):
    """v2.4.51'de ZATEN `veri/` altinda olan dosyalar icin yol uretir.

    `_veri_yolu`'ndan FARKI ve neden ayri bir islev gerektigi:

    v2.4.51 kurulumunda veri iki yere dagilmisti:
      (a) proje kokunde: `gcs_ayarlar.json`, `gcs.db`, `avatars/` ...
      (b) `veri/` altinda: `pg.json`, `calisma.json`, `sitl/`,
          `telemetri_tampon/`, `gorev_durum.json`

    Yeni yapida her ikisi de `<kok>/veri/...` altinda toplanir. Ancak
    ESKI yapida calisirken (yama uygulanmadan once, ya da kullanici
    dosyalari elle tasimadiysa) iki grubun eski konumu FARKLIDIR:
    (a) grubu kokte, (b) grubu `veri/` altinda aranmalidir.

    Tek kural iki grubu birden karsilamaz. `_veri_yolu` (a) grubu
    icindir; bu islev (b) grubu icindir. Karistirilirsa olusan kusur
    SESSIZDIR: ornegin `pg.json` bulunamayinca `yapilandirildi()`
    False doner ve kurulum sihirbazi HER ACILISTA yeniden cikar —
    kullanici kurulumu tamamladigini sanir, program aksini dusunur.
    """
    if VERI_KOKU != PROJE_KOKU:
        # YENI yapi: VERI_KOKU zaten <kok>/veri, dogrudan ekle
        return os.path.join(VERI_KOKU, *parcalar)
    # ESKI duz yapi: dosya <kok>/veri/... altindaydi
    return os.path.join(PROJE_KOKU, "veri", *parcalar)

# Dinleme adresi: '0.0.0.0' tum ag arayuzlerinden (LAN) erisime acar.
# Yalniz lokale kapatmak icin gcs_ayarlar.json'a  "ws_adres": "127.0.0.1"  yazin.
WS_ADRES = "0.0.0.0"
HTTP_ADRES = "0.0.0.0"

# Port rezerve/dolu ise siradaki aday denenir (WinError 10013 cozumu)
WS_PORTLAR = [8765, 8766, 8777, 9765]
HTTP_PORTLAR = [8000, 8080, 8888, 9000, 5500]


def _ortam_port_listesi(anahtar, varsayilan):
    """Ortam degiskeni ile port zorlamasi.

    NEDEN GEREKLI: GCS merkez sunucuda (/app/) ters vekil arkasinda
    calisir. Vekil, GCS'nin hangi porta dustugunu tahmin edemez;
    aday listesinden ilk bos olani secilirse vekil yanlis porta
    baglanir ve kullanici BOS SAYFA gorur. Merkezde port SABIT
    olmalidir.

    Kullanim: GOKTUNGU_HTTP_PORT=18000 GOKTUNGU_WS_PORT=18765 python3 main.py
    Deger verilirse aday listesi TEK elemana indirilir; port doluysa
    sessizce baska porta dusmek yerine hata verilmesi DOGRU davranistir,
    cunku vekil o portu bekler.
    """
    import os as _os
    ham = (_os.environ.get(anahtar) or "").strip()
    if not ham:
        return varsayilan
    try:
        p = int(ham)
    except ValueError:
        return varsayilan
    if not (1 <= p <= 65535):
        return varsayilan
    return [p]


WS_PORTLAR = _ortam_port_listesi("GOKTUNGU_WS_PORT", WS_PORTLAR)
HTTP_PORTLAR = _ortam_port_listesi("GOKTUNGU_HTTP_PORT", HTTP_PORTLAR)

# HTTPS/WSS: kendinden imzali sertifika ile guvenli erisim (LAN)
HTTPS_PORT = 8443
WSS_PORT = 9443
YAYIN_HZ = 5

# Dosya yollari (v2.4.52: `_veri_yolu()` uzerinden — bkz. yukarisi)
AYAR_DOSYASI = _veri_yolu("gcs_ayarlar.json")
KULLANICI_DOSYASI = _veri_yolu("kullanicilar.json")
LOKASYON_DOSYASI = _veri_yolu("lokasyonlar.json")
DRON_DOSYASI = _veri_yolu("gcs_dronlar.json")
KAYIT_KLASORU = _veri_yolu("kayitlar")
LOG_KLASORU = _veri_yolu("dron_loglari")  # indirilen dataflash loglar
HARITA_CACHE = _veri_yolu("harita_cache")  # offline tile onbellegi
SERTIFIKA_KLASORU = _veri_yolu("sertifika")  # HTTPS/WSS sertifikasi
# v2.4.52: avatar klasoru HTTP'den de okunur; sunucu web kokunden
# servis eder, buraya YAZAR (bkz. sunucu.py avatar yukleme).
AVATAR_KLASORU = _veri_yolu("avatars")
# ----------------------------------------------------------------------
# HARITA TILE KAYNAKLARI (offline cache proxy'si icin)
# Frontend /tile/<kaynak>/<z>/<x>/<y> ister; sunucu once diskteki
# onbellege bakar, yoksa asagidaki sablondan indirir ve kaydeder.
# {s} alt alan listeden sirayla secilir; bing icin quadkey hesaplanir.
# ----------------------------------------------------------------------
TILE_KAYNAKLARI = {
    "esri": {
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "uzanti": ".jpg"},
    "esri_sokak": {
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        "uzanti": ".jpg"},
    "esri_topo": {
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
        "uzanti": ".jpg"},
    "google": {
        "url": "https://mt{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        "s": ["0", "1", "2", "3"], "uzanti": ".jpg"},
    "google_hibrit": {
        "url": "https://mt{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
        "s": ["0", "1", "2", "3"], "uzanti": ".jpg"},
    "google_yol": {
        "url": "https://mt{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
        "s": ["0", "1", "2", "3"], "uzanti": ".png"},
    "google_arazi": {
        "url": "https://mt{s}.google.com/vt/lyrs=p&x={x}&y={y}&z={z}",
        "s": ["0", "1", "2", "3"], "uzanti": ".png"},
    "bing": {
        "url": "https://ecn.t{s}.tiles.virtualearth.net/tiles/a{q}.jpeg?g=14891",
        "s": ["0", "1", "2", "3"], "quadkey": True, "uzanti": ".jpg"},
    "osm": {
        "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "uzanti": ".png"},
    "otm": {
        "url": "https://tile.opentopomap.org/{z}/{x}/{y}.png",
        "uzanti": ".png"},
    "carto_acik": {
        "url": "https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
        "uzanti": ".png"},
    "carto_koyu": {
        "url": "https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
        "uzanti": ".png"},
}

# ----------------------------------------------------------------------
# SYSID SINIFLANDIRMA TABLOSU
# Dronun SYSID_THISMAV degeri hangi tipe karsilik geliyor?
# Istenirse gcs_ayarlar.json icine "sysid_tablosu": {"61": "YENITIP"}
# yazilarak yeniden baslatmadan dosya uzerinden genisletilebilir.
# ----------------------------------------------------------------------
SYSID_TABLOSU = {
    21: "INTERCEPTOR",
    31: "INTERCEPTOR",
    41: "KAMIKAZE",
    51: "KAMIKAZE",
}

# ----------------------------------------------------------------------
# C20 RADAR PROTOKOL SABITLERI
# ----------------------------------------------------------------------
RADAR_VARSAYILAN_IP = "192.168.8.186"
RADAR_VARSAYILAN_PORT = 5001
RADAR_IZ_ZAMANASIMI = 3.0     # sn: yenilenmeyen iz silinir

C20_HEARTBEAT        = 0x00000001
C20_LOGIN            = 0x00000002
C20_SETREG           = 0x00000040
C20_GETREG           = 0x00000041
C20_UPLOAD_TARGET_V3 = 0x00030001
C20_UPLOAD_TRACK_V3  = 0x00030002
C20_REQUEST_RTK      = 0x00010005
C20_UPLOAD_RTK       = 0x00010006
# v2.4.227: protokol dokumani 2.2 — JSON yapilandirma ve secili iz listesi
C20_SETJSON          = 0x00000080
C20_GETJSON          = 0x00000081
C20_SETSELECT        = 0x00000082
C20_GETSELECT        = 0x00000083

C20_HEDEF_TIPLERI = {
    0: "BELIRSIZ", 1: "INSAN", 2: "ARAC",
    3: "DRON", 4: "KUS", 5: "TANIMSIZ",
}

# WORKING_MODE kombinasyonlari (dokuman 2.4.2): (hiz<<8)|mod
C20_MOD_KODLARI = {
    "bekleme": 0x0000, "tarama1": 0x0401,
    "tarama2": 0x0101, "tarama4": 0x0201,
}
C20_MOD_ADLARI = {v: k for k, v in C20_MOD_KODLARI.items()}

# RTK tamam sayilmadan once alinacak ornek sayisi
RTK_HEDEF_ORNEK = 20
