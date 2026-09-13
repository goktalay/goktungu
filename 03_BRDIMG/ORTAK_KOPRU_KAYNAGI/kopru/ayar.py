# -*- coding: utf-8 -*-
"""KOPRU YAZILIMI — ayar ve kimlik saklama.

## NEDEN AYRI BIR MODUL

Kopru yazilimi kullanicinin BILGISAYARINDA calisir. Iki tur bilgi tutar
ve bunlarin guvenlik gereksinimleri BIRBIRINDEN FARKLIDIR:

1) AYARLAR (`ayar.json`) — merkez adresi, yerel panel portu, servis
   tanimlari. Gizli degildir; kullanici duzenleyebilir.

2) KIMLIK (`kimlik.json`) — merkezin urettigi `kurulum_uid` ve `gizli`.
   Bu ikili, bu kuruluma merkez adina konusma yetkisi verir. Dosya
   izinleri 0600 yapilir ve `gizli` HICBIR ZAMAN panele gonderilmez
   (panel yalniz `gizli_var: true/false` gorur).

Ayni dosyada tutulsalardi, ayar dosyasini kullaniciyla paylasmak
(destek talebi, hata bildirimi) gizli anahtari sizdirirdi.

## NEDEN PostgreSQL DEGIL

Kullanici talimati "her veri PostgreSQL'de" GCS ve merkez icin
gecerlidir. Kopru yazilimi, PostgreSQL kurulumu OLMAYAN bir dizustu
bilgisayarinda da tek basina calismalidir: gorevi zaten telemetriyi
merkezdeki PostgreSQL'e TASIMAKTIR. Kendi calismasi icin veritabani
sart kosmak, aracin var olma amacini ortadan kaldirirdi. Bu yuzden
yalniz iki kucuk JSON dosyasi kullanilir; ucus verisi burada
TUTULMAZ, merkeze aktarilir (bkz. kuyruk.py).
"""
import json
import os
import platform
import socket
import stat

# KOPRU SURUMU — tek kaynak `surumler.py`.
#
# NEDEN sabit yazilmiyor: onceden burada elle "2.4.53" yaziliydi, yani
# MERKEZ GCS'nin surum numarasi. Kopru merkeze o numarayi bildirdigi icin
# `guncelleme_kontrol("kopru", "2.4.53")` cagrisinda depodaki gercek kopru
# surumu (1.1.0) ile 2.4.53 kiyaslaniyor, kopru kendini kalici olarak
# "guncel" saniyor ve GUNCELLEME HIC INMIYORDU. Istenen iki hatli surum
# yonetimi (merkez hatti + kopru hatti) bu yuzden fiilen tek hatta
# dusmustu; merkez panelinde saha koprulari da yanlis surumle listeleniyordu.
#
# Ithalat yonu ayar.py -> surumler.py'dir. surumler.py hicbir modul ice
# aktarmaz (yalniz veri sozlukleri ve saf islevler), bu yuzden dairesel
# ithalat olusmaz.
from .surumler import KOPRU_SURUM as SURUM
VARSAYILAN_MERKEZ = "wss://goktungu.com/kopru"   # 443: her agda gecer
VARSAYILAN_MERKEZ_HTTP = "https://goktungu.com"
VARSAYILAN_PANEL_PORT = 8790


def veri_dizini():
    """Kullanici verisi icin platforma uygun dizin.

    Program dizinine yazmak, `C:\\Program Files` altina kurulumda
    yonetici izni gerektirir ve servis olarak calisirken basarisiz
    olur; bu yuzden ayri bir veri dizini kullanilir.

    ## WINDOWS: NEDEN %APPDATA% DEGIL ProgramData

    v1.4.0'dan once `%APPDATA%` kullaniliyordu. Kopru GERCEK BIR
    WINDOWS SERVISI olarak `LocalSystem` hesabiyla calistiginda bu
    yol
        C:\\Windows\\System32\\config\\systemprofile\\AppData\\Roaming
    altina duser. Sonuclari:

    1. Kullanici merkez kimligini goremez, yedekleyemez, destek
       talebinde paylasamaz.
    2. Panelden (kullanici oturumunda tarayici) yapilan kayit ile
       servisin okudugu kimlik AYRI DOSYALAR olur; kullanici
       "merkeze kaydettim ama kopru hala kayitsiz diyor" durumuna
       duser.
    3. Servis kaldirilip elle calistirildiginda ayarlar kaybolmus
       gorunur.

    `%PROGRAMDATA%` (C:\\ProgramData) makine genelinde ortak alandir:
    hem `LocalSystem` hem oturum acmis kullanici ayni yolu gorur.
    Kurulum programi bu dizini olusturur ve yazma izni verir.

    Eski kurulumdan gecis: ProgramData altinda kimlik YOKSA ve
    `%APPDATA%` altinda VARSA, eski dizin kullanilmaya devam eder.
    Aksi halde v1.3.0 kullanicisi yukseltmeden sonra merkez kaydini
    bastan yapmak zorunda kalirdi.
    """
    ozel = os.environ.get("GOKTUNGU_KOPRU_VERI")
    if ozel:
        kok = ozel
    elif os.name == "nt":
        yeni = os.path.join(
            os.environ.get("PROGRAMDATA") or r"C:\ProgramData",
            "Goktungu", "Kopru")
        eski = os.path.join(os.environ.get("APPDATA")
                            or os.path.expanduser("~"), "goktungu-kopru")
        # Gecis kurali: yeni yerde kimlik yok ama eskide varsa eskiyi
        # kullan. Boylece yukseltme merkez kaydini kaybetmez.
        if (not os.path.exists(os.path.join(yeni, "kimlik.json"))
                and os.path.exists(os.path.join(eski, "kimlik.json"))):
            kok = eski
        else:
            kok = yeni
    else:
        kok = os.path.join(
            os.environ.get("XDG_CONFIG_HOME")
            or os.path.join(os.path.expanduser("~"), ".config"),
            "goktungu-kopru")
    os.makedirs(kok, exist_ok=True)
    return kok


def _yol(ad):
    return os.path.join(veri_dizini(), ad)


def _oku(yol, varsayilan):
    try:
        with open(yol, "r", encoding="utf-8") as f:
            v = json.load(f)
        return v if isinstance(v, dict) else dict(varsayilan)
    except Exception:
        return dict(varsayilan)


def _yaz(yol, veri, gizli=False):
    """Atomik yazim: gecici dosya + os.replace.

    Dogrudan yazimda, yazim sirasinda elektrik kesilirse dosya yarim
    kalir ve bir sonraki acilista kimlik OKUNAMAZ; kullanici merkez
    kaydini bastan yapmak zorunda kalir.
    """
    gecici = yol + ".yeni"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(gecici, yol)
    if gizli:
        try:
            os.chmod(yol, stat.S_IRUSR | stat.S_IWUSR)   # 0600
        except Exception:
            pass       # Windows'ta chmod sinirlidir; hata degil


# ---------------------------------------------------------------------
# AYARLAR
# ---------------------------------------------------------------------
AYAR_VARSAYILAN = {
    "merkez_adres": VARSAYILAN_MERKEZ,
    "merkez_http": VARSAYILAN_MERKEZ_HTTP,
    "panel_port": VARSAYILAN_PANEL_PORT,
    # KULLANICI ISTEGI (2026-08-15): panel aga acik olacak. Saha
    # kurulumunda kopru makinesi genellikle ekransizdir; yalniz o
    # makinenin basinda erisilebilen bir panel kullanilamiyordu.
    # Yikici uc noktalar (merkeze kayit, ayar yazma) buna karsilik
    # yalniz yerel istege aciktir; bkz. `panel.py` madde 1 ve 6.
    "panel_arayuz": "0.0.0.0",
    "sertifika_dogrulama": True,
    "acilista_baslat": {"dron": False, "ai": False, "video": False},
    # v1.5.6 — MERKEZ SUNUCU SECIMI
    #
    # Merkez Uygulama (5.000 $ tek seferlik) satin alan sirket, GOKTUNGU
    # merkezini KENDI sunucusunda calistirir. Kopru varsayilan olarak
    # GOKTUNGU bulutuna baglanir; secim sorulmazsa o sirketin telemetrisi
    # yanlis yere, GOKTUNGU bulutuna akmaya devam ederdi.
    #
    # Soru giris SONRASI sorulur (firma lisansi ancak o zaman bilinir),
    # yalniz `yonetici` rolune ve yalniz BIR KEZ. Karar burada saklanir;
    # Ayarlar penceresinden her zaman degistirilebilir.
    "merkez_secim_yapildi": False,
    "merkez_secim_ts": 0,
    "merkez_kendi": False,
}


# ADRES GOCU (2026-08-13): 9443 -> portsuz (443).
# NEDEN: onceki surumler merkez adresini `:9443` ile DISKE yazdi.
# Kullanicinin elle verdigi ayar ustun oldugu icin bu kayit, kurulum
# 9443'un kapali oldugu bir aga (mobil operator, kurum guvenlik
# duvari) tasindiginda baglantiyi kalici olarak engeller. Bu yuzden
# YALNIZCA bizim ontanimli alan adimiz + 9443 kalibi portsuza tasinir;
# kullanicinin kendi sunucusuna yazdigi adres ASLA degistirilmez.
_GOC_ESKI = "wss://gozcu.veilox.com.tr:9443/kopru"

# ALAN ADI GOCU (2026-08-17): gozcu.veilox.com.tr -> goktungu.com
# NEDEN: 1.6.0 ve oncesi kurulumlar merkez adresini ESKI ALAN ADI ile
# DISKE yazdi.  Yalnizca varsayilani degistirmek bu kurulumlari eski
# adreste birakir; kullanici "guncelledim ama hala eski adres" der.
#
# NEDEN 301 YETMEZ: eski alan adi yeni adrese HTTP 301 ile yonleniyor
# ama WebSocket EL SIKISMASI YONLENDIRMEYI IZLEMEZ.  Bugun calisiyor
# gorunmesi eski alan adinin AYAKTA olmasindandir; kapatildigi gun
# kopru SESSIZCE baglanamaz hale gelir.
#
# SINIR: yalniz BIZIM ontanimli alan adimiz tasinir.  Kullanicinin
# kendi sunucusuna yazdigi adres (kapali devre kurulum, kendi merkez
# uygulamasi) ASLA degistirilmez.
_GOC_ALAN_ESKI = ("wss://gozcu.veilox.com.tr/kopru",
                  "wss://gozcu.veilox.com.tr:9443/kopru")
_GOC_ALAN_HTTP_ESKI = ("https://gozcu.veilox.com.tr",
                       "https://gozcu.veilox.com.tr/")

# PANEL ARAYUZ GOCU (2026-08-15): 127.0.0.1 -> 0.0.0.0.
# NEDEN: `panel_arayuz` ayar dosyasina YAZILI gelir. Varsayilani
# degistirmek yalniz YENI kurulumlari etkiler; mevcut kurulumlar
# yukseltmeden sonra da yerelde kalir ve kullanici "guncelledim ama
# hala 127.0.0.1" der. Bu yuzden ESKI VARSAYILAN degeri tasinir.
#
# SINIR: yalniz eski varsayilanin BIREBIR kendisi tasinir. Kullanici
# bilerek baska bir adres yazdiysa (ornegin tek bir NIC'e baglamak
# icin 192.168.1.50) o deger ASLA degistirilmez. Yerelde kalmak
# isteyen kullanici `localhost` ya da `::1` yazabilir; bu degerler de
# gocten etkilenmez.
_PANEL_ARAYUZ_ESKI = "127.0.0.1"
_PANEL_ARAYUZ_YENI = "0.0.0.0"


def ayar_oku():
    a = _oku(_yol("ayar.json"), AYAR_VARSAYILAN)
    for k, v in AYAR_VARSAYILAN.items():
        a.setdefault(k, v)
    degisti = False
    if str(a.get("merkez_adres") or "").strip() in _GOC_ALAN_ESKI:
        a["merkez_adres"] = VARSAYILAN_MERKEZ
    if str(a.get("merkez_http") or "").strip() in _GOC_ALAN_HTTP_ESKI:
        a["merkez_http"] = VARSAYILAN_MERKEZ_HTTP
        degisti = True
    if str(a.get("panel_arayuz") or "").strip() == _PANEL_ARAYUZ_ESKI:
        a["panel_arayuz"] = _PANEL_ARAYUZ_YENI
        degisti = True
    if degisti:
        with __import__("contextlib").suppress(Exception):
            ayar_yaz(a)
    return a


def ayar_yaz(veri):
    _yaz(_yol("ayar.json"), veri)
    return veri


def ayar_guncelle(**alanlar):
    a = ayar_oku()
    a.update({k: v for k, v in alanlar.items() if v is not None})
    return ayar_yaz(a)


# ---------------------------------------------------------------------
# KIMLIK
# ---------------------------------------------------------------------
KIMLIK_VARSAYILAN = {
    "kurulum_uid": "",
    "gizli": "",
    "ornek_id": None,
    "ad": "",
    "firma_id": None,
    "firma_kisa_ad": "",
    "eposta": "",
}


def kimlik_oku():
    k = _oku(_yol("kimlik.json"), KIMLIK_VARSAYILAN)
    for a, v in KIMLIK_VARSAYILAN.items():
        k.setdefault(a, v)
    # Kayit sirasinda merkezden gelen kopru adresi de kimlik dosyasina
    # yazilir; ayni goc burada da uygulanir (bkz. `_GOC_ESKI`).
    if str(k.get("merkez_adres") or "").strip() in _GOC_ALAN_ESKI:
        k["merkez_adres"] = VARSAYILAN_MERKEZ
    if str(k.get("merkez_http") or "").strip() in _GOC_ALAN_HTTP_ESKI:
        k["merkez_http"] = VARSAYILAN_MERKEZ_HTTP
        with __import__("contextlib").suppress(Exception):
            kimlik_yaz(k)
    return k


def kimlik_yaz(veri):
    _yaz(_yol("kimlik.json"), veri, gizli=True)
    return veri


def kimlik_sil():
    try:
        os.remove(_yol("kimlik.json"))
    except FileNotFoundError:
        pass


def kimlik_var():
    k = kimlik_oku()
    return bool(k.get("kurulum_uid") and k.get("gizli"))


def kimlik_maskeli():
    """Panele gonderilebilir kimlik ozeti — `gizli` ICERMEZ."""
    k = kimlik_oku()
    return {
        "kurulum_uid": k.get("kurulum_uid") or "",
        "gizli_var": bool(k.get("gizli")),
        "ornek_id": k.get("ornek_id"),
        "ad": k.get("ad") or "",
        "firma_id": k.get("firma_id"),
        "firma_kisa_ad": k.get("firma_kisa_ad") or "",
        "eposta": k.get("eposta") or "",
    }


# ---------------------------------------------------------------------
# MAKINE KIMLIGI
# ---------------------------------------------------------------------
def makine_adi():
    try:
        return socket.gethostname()
    except Exception:
        return "bilinmeyen"


def platform_adi():
    try:
        return "%s %s" % (platform.system(), platform.release())
    except Exception:
        return os.name
