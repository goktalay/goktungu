#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GOKTUNGU — Drone GCS Angajman Sistemi | Giris noktasi.

Kullanim:
    python3 main.py

Bilesenler (goktungu/ paketi, her sinif kendi dosyasinda):
    KonsolLog           goktungu/konsol.py        merkezi log tamponu
    AyarYoneticisi      goktungu/ayarlar.py       gcs_ayarlar.json
    KullaniciYoneticisi goktungu/kullanicilar.py  auth + kullanici DB
    LokasyonYoneticisi  goktungu/lokasyonlar.py   kayitli lokasyonlar
    RotaYoneticisi      goktungu/rotalar.py       ucus rotalari (gcs_rotalar.json)
    KayitYoneticisi     goktungu/kayit.py         radar kaydi + replay
    DronYoneticisi      goktungu/dron.py          MAVLink telemetri + komut
    RadarIstemcisi      goktungu/radar.py         C20 protokolu + saglik
    AngajmanYoneticisi  goktungu/angajman.py      interceptor gudumu
    Takipci             goktungu/takip/           GNN + Kalman iz takibi
    WSSunucusu          goktungu/sunucu.py        WebSocket komut + yayin
    HttpSunucusu        goktungu/sunucu.py        statik dosya sunucusu

Bagimliliklar: bkz. requirements.txt (websockets, opencv-python,
numpy, pymavlink, pyserial; opsiyonel: pygame)
"""
import asyncio
import os
import sys
import threading
import socket
import subprocess
import time
import shutil

# ==================================================================
# YOL COZUMLEME (v2.4.52'de EKLENDI)
# ==================================================================
# v2.4.52'de klasor yapisi degisti (kullanici istegi):
#
#   ONCE                      SONRA
#   ----                      -----
#   main.py                   main.py
#   index.html  js/  css/     assets/web/     (HTTP'den servis edilen)
#   goktungu/  ai_sunucu.py      assets/python/  (Python kodu)
#   veri/ harita_cache/ ...   veri/           (calisma zamani verisi)
#
# Bu blok `goktungu` paketini bulunabilir kilar. `main.py` calisma
# dizininden BAGIMSIZ olmalidir: servis (`systemd`) farkli bir
# `WorkingDirectory` ile baslatabilir, kiosk betigi baska dizinden
# cagirabilir. Bu yuzden yol HER ZAMAN `__file__` uzerinden
# hesaplanir, `os.getcwd()` uzerinden ASLA.
#
# GERIYE UYUMLULUK: eski duz yapida (`goktungu/` kokte) da calisir.
# Boylece v2.4.51 kurulumu uzerine yama uygulanirken, klasor gocu
# yapilmadan once bile program acilabilir.
PROJE_KOKU = os.path.dirname(os.path.abspath(__file__))
_PY_KOKU = os.path.join(PROJE_KOKU, "assets", "python")
if os.path.isdir(os.path.join(_PY_KOKU, "goktungu")):
    # YENI yapi (v2.4.52+)
    if _PY_KOKU not in sys.path:
        sys.path.insert(0, _PY_KOKU)
elif os.path.isdir(os.path.join(PROJE_KOKU, "goktungu")):
    # ESKI duz yapi (v2.4.51 ve oncesi)
    if PROJE_KOKU not in sys.path:
        sys.path.insert(0, PROJE_KOKU)
else:
    print("=" * 62)
    print("[HATA] `goktungu` Python paketi bulunamadi.")
    print(f"  Arandi: {os.path.join(_PY_KOKU, 'goktungu')}")
    print(f"          {os.path.join(PROJE_KOKU, 'goktungu')}")
    print("  Kurulum eksik veya bozuk. Paketi yeniden acin.")
    print("=" * 62)
    raise SystemExit(1)


def _harici_arac_kontrol():
    """v2.4.34: Harici (pip disi) ikili araclari acilista dogrular.

    NEDEN EKLENDI: ffmpeg kurulu olmadiginda kamera onizlemeleri
    yalnizca "YAYIN ALINAMIYOR" gosteriyordu; ne konsolda ne arayuzde
    gercek gerekce goruluyordu. Sunucu bunu acilista BILEBILIR
    (shutil.which tek cagri), dolayisiyla kullaniciyi ilk saniyede
    uyarmalidir — kamera acmayi denedikten sonra degil.

    ffmpeg zorunlu degildir: MAVLink telemetri, radar ve harita
    ffmpeg'siz sorunsuz calisir. Yalnizca RTSP/MJPEG/HTTP video
    kaynaklari ffmpeg'e baglidir, bu yuzden UYARI seviyesindedir.
    """
    # NOT: `sys` modul duzeyinde ice alinmamis (yalniz 300. satirda
    # yerel olarak); burada da yerel ice alim sart, aksi halde
    # NameError olur.
    import shutil
    import sys
    if shutil.which("ffmpeg"):
        return
    print("[UYARI] ffmpeg bulunamadi - KAMERA YAYINLARI CALISMAZ "
          "(RTSP/MJPEG/HTTP video).")
    print("        Telemetri, radar ve harita etkilenmez.")
    if sys.platform.startswith("win"):
        print("        Kurulum: winget install Gyan.FFmpeg")
        print("        (kurulumdan sonra terminali yeniden acin)")
    else:
        print("        Kurulum: sudo apt install ffmpeg")


def _bagimlilik_kontrol():
    """v2.4.11: Zorunlu/opsiyonel Python paketlerini acilista dogrular.

    Eksik ZORUNLU paket varsa anlasilir bir mesaj + kurulum komutu
    yazdirip cikar (calisma ortasinda ModuleNotFoundError yerine).
    """
    import importlib.util as iu
    zorunlu = [
        ("websockets", "websockets", "WebSocket sunucusu (arayuz iletisimi)"),
        ("cv2", "opencv-python", "video proxy + AI goruntu isleme"),
        ("numpy", "numpy", "goruntu/sinyal islemleri"),
        ("pymavlink", "pymavlink", "MAVLink dron telemetri/komut"),
        ("serial", "pyserial", "seri port (radar/dron baglantisi)"),
    ]
    opsiyonel = [
        ("pygame", "pygame", "fiziksel joystick (manuel kontrol)"),
        # v2.4.34: Sistem Kaynaklari widget'i sunucu olcumu.
        # Yoksa Linux'ta /proc yedek yolu kullanilir; Windows'ta widget
        # yalniz tarayici olcumlerini gosterir. GCS her durumda calisir.
        ("psutil", "psutil", "sunucu CPU/RAM olcumu (Kaynaklar widget'i)"),
    ]
    eksik = [(m, p, a) for m, p, a in zorunlu if iu.find_spec(m) is None]
    for m, p, a in opsiyonel:
        if iu.find_spec(m) is None:
            print(f"[UYARI] Opsiyonel paket yok: {p} ({a}) - "
                  f"gerekirse: pip3 install {p}")
    _harici_arac_kontrol()
    if not eksik:
        return
    print("=" * 62)
    print("[HATA] Eksik Python paketleri var - GCS baslatilamiyor:")
    for m, p, a in eksik:
        print(f"  - {p:<16} {a}")
    pkts = " ".join(p for _, p, _ in eksik)
    print()
    print("Kurulum (once bunu deneyin):")
    print(f"  pip3 install {pkts}")
    print()
    print("Ubuntu 23.04+ 'externally-managed-environment' hatasi verirse:")
    print(f"  pip3 install --break-system-packages {pkts}")
    print("  # veya sanal ortam:")
    print("  #   python3 -m venv venv")
    print(f"  #   ./venv/bin/pip install -r requirements.txt")
    print("  #   ./venv/bin/python main.py")
    print("=" * 62)
    raise SystemExit(1)


_bagimlilik_kontrol()

from goktungu.konsol import KonsolLog
from goktungu.ayarlar import AyarYoneticisi
from goktungu.kullanicilar import KullaniciYoneticisi
from goktungu.lokasyonlar import LokasyonYoneticisi
from goktungu.kayit import KayitYoneticisi
from goktungu.etiket import EtiketYoneticisi
from goktungu.rotalar import RotaYoneticisi
from goktungu.baglantilar import BaglantiYoneticisi
from goktungu.betaflight_msp import BetaflightMspYonetici
from goktungu.kameralar import KameraYoneticisi
from goktungu.video_proxy import VideoProxy
from goktungu.gorev import GorevYoneticisi
from goktungu.dron import DronYoneticisi
from goktungu.radar import RadarIstemcisi
from goktungu.angajman import AngajmanYoneticisi
from goktungu.takip import Takipci
from goktungu.ucus_gecmisi import UcusGecmisi
from goktungu.manuel_kontrol import ManuelKontrol
from goktungu.istasyon2 import Istasyon2
from goktungu.takip_dron import DronTakipYoneticisi
from goktungu.suru import SuruYoneticisi
from goktungu.udp_yayin import UdpYayinYoneticisi
from goktungu.pilot import PilotYoneticisi
from goktungu.mesajlar import MesajYoneticisi
from goktungu.dji_kopru import DjiKopruYoneticisi
from goktungu.sunucu import WSSunucusu, HttpSunucusu
from goktungu.ai_yonetici import AIYonetici
from goktungu.kutuphane import KisiYoneticisi, AracYoneticisi


class _PgKipiAtla(Exception):
    """v2.4.51: PG kipinde SQLite'a ozgu adimlari atlamak icin.

    Kontrol akisi icin ozel bir istisna kullanilir; boylece atlanan
    adimin `except Exception` dalina dusup "hata" olarak
    gunluklenmesi onlenir.
    """


def uygulama_kur():
    """Tum bilesenleri olusturur ve birbirine baglar (kompozisyon koku).

    Returns:
        (ws_sunucu, http_sunucu) cifti
    """
    # --- Cekirdek: log + ayar kaliciligi + paylasilan kilit ---
    konsol = KonsolLog()

    # --- v2.4.51: POSTGRESQL KIPI (butunluk denetiminden ONCE) ---
    # Kullanici istegi: "sqlite'a donmeyecegiz, lutfen her veriyi
    # postgresql'e cevir". Yapilandirma dosyasi varsa TUM veri
    # katmani PostgreSQL'e yonlendirilir; SQLite dosyasina hic
    # dokunulmaz.
    #
    # SIRA KRITIKTIR: pg kipi acilmadan once KullaniciYoneticisi gibi
    # siniflar kurucularinda `tablolari_olustur()` cagirir; kip
    # sonradan acilirsa bu cagrilar SQLite dosyasina gider ve iki
    # ayri sema olusur.
    #
    # Yapilandirma YOKSA sunucu normal baslar ve arayuz acilista
    # sihirbazi gosterir (js/pg_sihirbaz.js). Sunucunun ayakta olmasi
    # ZORUNLUDUR: sihirbaz WS uzerinden konusur.
    _pg_kipi = False
    try:
        from goktungu import pg as _pg
        from goktungu import veritabani as _vtpg
        if _pg.dosya_var() and _pg.dosyadan_yukle():
            if not _pg.VAR:
                # Yapilandirma var ama surucu yok: SQLite'a dusulmez,
                # cunku veri PG'de. Kullaniciya kurulum komutu verilir
                # ve sihirbaz yine acilir (surucu_var=false bildirilir).
                _vtpg.kip_ayarla("sqlite")
                konsol("PG", "PostgreSQL yapilandirmasi var ama surucu "
                       "(psycopg2) kurulu degil. Kurmak icin: "
                       "pip3 install psycopg2-binary", "hata")
            else:
                _vtpg.kip_ayarla("postgresql")
                _pg_kipi = True
                _y = _pg.yapilandirma_oku() or {}
                konsol("PG", "PostgreSQL kipi ACIK: %s@%s:%s/%s"
                       % (_y.get("user", "?"), _y.get("host", "?"),
                          _y.get("port", "?"), _y.get("dbname", "?")),
                       "basari")
                # Sema guncel mi?
                #
                # IKI AYRI DAVRANIS (v2.4.54):
                #
                # LOKAL KURULUM -- goc BURADA UYGULANMAZ. Kullanici
                #   istegi: "eger daha once kurulum yapildiysa ilk
                #   acilista veri tabaninda tablolarda bir guncelleme
                #   varsa sihirbaz acilsin". Onay ve ilerleme bildirimi
                #   arayuzden yurutulur (pg_goc komutu). Veritabani
                #   kurumun kendi sunucusundadir; sahibi odur.
                #
                # MERKEZ ORNEGI -- goc BURADA UYGULANIR.
                #   Kullanici istegi (birebir): "merkez guncellemesini
                #   sen yap neden kullaniciya yaptiriyorsun".
                #   Merkezdeki ornek COK KIRACILIDIR; semayi bir pilotun
                #   tarayici dugmesine baglamak (a) tum kiracilari
                #   etkileyen bir islemi tek kiracinin pilotuna verir,
                #   (b) goc suresince baska kurumlarin ucusunu keser,
                #   (c) hata cikarsa pilot cozemez.
                #
                #   OLCULEN KUSUR (HATA_GOC_SIHIRBAZI.md): merkezde
                #   `kopru_gruplama` adimi bekliyordu; sihirbaz acildi ve
                #   "yonetici olarak giris yapin" hatasiyla %0'da
                #   sikisti. Cunku sihirbaz giris ekranindan ONCE acilir,
                #   oturum henuz bostur ve yonetici denetimi kapanir.
                try:
                    from goktungu import goc as _goc
                    _merkez = False
                    try:
                        from goktungu import merkez_kimlik as _mkk
                        _merkez = _mkk.merkez_kipinde()
                    except Exception:
                        _merkez = False

                    _d = _goc.GocMotoru().durum()
                    if not _d.get("guncel"):
                        _bekleyen = _d.get("bekleyen", [])
                        if _merkez:
                            konsol("GOC", "Merkez kipi: sema guncel degil "
                                   "(v%s -> v%s, %s bekleyen adim). "
                                   "Goc SUNUCU TARAFINDA uygulaniyor "
                                   "(pilota sihirbaz gosterilmez)."
                                   % (_d.get("sema_surumu"),
                                      _d.get("hedef_surum"),
                                      len(_bekleyen)), "uyari")
                            for _a in _bekleyen:
                                konsol("GOC", "  bekleyen: %s (v%s) %s"
                                       % (_a.get("ad"), _a.get("surum"),
                                          _a.get("aciklama") or ""), "bilgi")

                            def _goc_ilerleme(y, ileti, ad=""):
                                konsol("GOC", "%5.1f%% %s%s"
                                       % (y, ileti,
                                          " [%s]" % ad if ad else ""),
                                       "bilgi")

                            _s = _goc.GocMotoru(konsol=lambda m: konsol(
                                "GOC", str(m), "bilgi")).calistir(
                                    _goc_ilerleme)
                            if _s.get("tamam"):
                                konsol("GOC", "Merkez semasi guncellendi "
                                       "(%s adim uygulandi)."
                                       % _s.get("uygulanan"), "basari")
                            else:
                                # Goc basarisiz: sunucu YINE de baslar.
                                # Durdurmak, semasi kismen guncel bir
                                # merkezi tamamen erisilemez yapardi;
                                # calisan kiracilar da kaybedilirdi.
                                # Operator gunlukten gorur ve mudahale
                                # eder; pilota sihirbaz cikmaz.
                                konsol("GOC", "Merkez semasi "
                                       "GUNCELLENEMEDI: %s -- operator "
                                       "mudahalesi gerekiyor."
                                       % _s.get("hata"), "hata")
                        else:
                            konsol("PG", "Veritabani semasi guncel degil "
                                   "(v%s -> v%s, %s bekleyen adim). "
                                   "Arayuzde guncelleme sihirbazi "
                                   "acilacak."
                                   % (_d.get("sema_surumu"),
                                      _d.get("hedef_surum"),
                                      len(_bekleyen)), "uyari")
                except Exception as _eg:
                    konsol("PG", f"Sema surumu okunamadi: {_eg}",
                           "uyari")
        else:
            # Yapilandirma YOK: veri katmani henuz kullanilamaz. Kip
            # SQLite'a alinir ki acilistaki tablo olusturma cagrilari
            # baglanti hatasiyla patlamasin; sihirbaz tamamlandiginda
            # sunucu kipi PG'ye cevirir (pg_kur komutu).
            _vtpg.kip_ayarla("sqlite")
            konsol("PG", "PostgreSQL yapilandirmasi yok. Arayuz "
                   "acilista kurulum sihirbazini gosterecek.", "uyari")
    except Exception as _epg:
        konsol("PG", f"PostgreSQL kipi acilamadi: {_epg}", "hata")
        try:
            from goktungu import veritabani as _vtx
            _vtx.kip_ayarla("sqlite")
        except Exception:
            pass

    # --- v2.4.25: VERITABANI BUTUNLUK DENETIMI (ilk is) ---
    # Kullanici sahada `database disk image is malformed` aldi ve
    # telemetri diske HIC yazilamadi (bkz. db_onarim.py bas yorumu).
    # Denetim TUM yoneticilerden ONCE yapilmali: KullaniciYoneticisi
    # gibi siniflar kurucularinda `tablolari_olustur()` cagirir ve
    # bozuk dosyada bu cagri da basarisiz olur.
    #
    # `quick_check` kullanilir; 4 MB dosyada milisaniyeler surer.
    # Saglam veritabaninda HICBIR SEY yapilmaz (test 9 ile dogrulandi).
    # v2.4.51: PG kipinde bu denetim ATLANIR. `quick_check` bir SQLite
    # pragmasidir; PostgreSQL'de karsiligi yoktur ve sunucu tarafi
    # butunlugu kendi WAL/checkpoint mekanizmasiyla korur. Ayrica
    # denetim SQLite dosyasini acar; PG kipinde o dosya artik hicbir
    # veri barindirmadigi icin denetimin sonucu anlamsiz olurdu.
    try:
        if _pg_kipi:
            raise _PgKipiAtla()
        from goktungu import db_onarim as _dbo
        from goktungu import veritabani as _vtd
        _sonuc = _dbo.acilis_denetimi(_vtd.DOSYA, konsol)
        if _sonuc.get("onarildi"):
            konsol("DB", "Veritabani onarildi (yontem: %s). Telemetri "
                   "gecmisi sifirlandi, diger veriler korundu."
                   % _sonuc.get("yontem"), "uyari")
        elif not _sonuc.get("saglam"):
            konsol("DB", "Veritabani ONARILAMADI: %s"
                   % _sonuc.get("mesaj"), "hata")
    except _PgKipiAtla:
        pass
    except Exception as _edb:
        konsol("DB", "Butunluk denetimi yapilamadi: %s" % _edb, "uyari")

    ayarlar = AyarYoneticisi(konsol)
    kilit = threading.Lock()   # dron/radar/angajman/sunucu ortak kilidi

    # --- Veri yoneticileri ---
    kullanicilar = KullaniciYoneticisi()
    pilot = PilotYoneticisi(konsol)  # v2.1.7: pilot log + rol/izin + uyari
    mesajlar = MesajYoneticisi(konsol)  # v2.4.32: pilotlar arasi mesajlasma
    lokasyonlar = LokasyonYoneticisi()
    kayit = KayitYoneticisi(konsol)
    etiket = EtiketYoneticisi(konsol)
    rotalar = RotaYoneticisi()
    baglantilar = BaglantiYoneticisi(konsol)
    kameralar = KameraYoneticisi()
    # v2.4.61 VIDEO TOPOLOJI DUZELTMESI
    # ------------------------------------------------------------------
    # Radar/GCCDUAL icin bildirilen kusurun AYNISI kamera zincirinde de
    # vardi: "GCS icinde kopru kurulu olan makinede porta baglanmali,
    # sanirim su an sunucu da ariyor portu".
    #
    # Kameralar sahadaki OZEL agda durur (rtsp://192.168.1.50/... ya da
    # USB indeksi). Merkez sunucu bu adreslere ulasamaz; onceki surumde
    # `VideoProxy` merkezde acildigi icin yalniz genel internete acik
    # kameralar calisiyordu (kullanicinin ekledigi 97.76.27.170 bu
    # yuzden geliyordu). Ayrica `cihaz_listesi()` merkezde tarandigi
    # icin USB kamera listesi HER ZAMAN bostu.
    #
    # Merkez kipinde akis SAHADA acilir; merkez yalniz durumu ceker.
    # LOKAL KURULUM DEGISMEZ.
    # FAZ19-IS73-ROZET-GUNLUK-SOKUM
    # Video katmani sistemden soküldü (IS71). Merkez/lokal kip
    # ayrimi kaldirildi: her iki kipte de bos omurga kurulur.
    # Saha vekili acilista konsola "kamera akisi aktarilir" basiyordu;
    # islev yokken konusan kod kafa karistirir.
    video_proxy = VideoProxy(
        kameralar, konsol=lambda m: konsol("KAMERA", m))
    # --- Donanim katmani ---
    dron = DronYoneticisi(konsol, ayarlar, kilit)
    dji_kopru = DjiKopruYoneticisi(konsol, dron, kilit)  # v2.1.8: DJI GDP
    # v2.4.142: Betaflight yalnız MSP salt-okunur tanı/telemetri
    # oturumları için ayrı yöneticidir; MAVLink DronYoneticisi'ne veri
    # ya da uçuş komutu enjekte etmez.
    betaflight = BetaflightMspYonetici(konsol=konsol)
    # GUVENLIK (BULGU_07): GDP belirtec dogrulamasi icin
    # ayar erisimi. Kurucu imzasi degistirilmedi.
    dji_kopru.ayarlar = ayarlar
    video_proxy.dji_kopru = dji_kopru  # dji:<sysid> kamera URL cozumu
    # v2.4.59 RADAR TOPOLOJI DUZELTMESI
    # ------------------------------------------------------------------
    # Kullanici bildirimi: "radarda da ayni sorun var, radarin kopru
    # yazilimi calisiyor ama sistem radari sunucuda ariyor".
    #
    # Radar donanimi sahadaki OZEL agda (192.168.8.x) durur; merkez
    # sunucu bu adrese ulasamaz ve `RadarIstemcisi` sonsuza kadar
    # "timed out" verir. Bu yuzden MERKEZ kipinde C20 oturumu kurmayi
    # hic denemeyen, veriyi kopruden ceken vekil kullanilir.
    #
    # LOKAL KURULUM DEGISMEZ: kip merkez degilse birebir eski nesne.
    try:
        from goktungu import merkez_kimlik as _mk_radar
        _radar_merkez = _mk_radar.merkez_kipinde()
    except Exception:
        _radar_merkez = False
    if _radar_merkez:
        from goktungu.radar_vekil import RadarVekili
        # `cek` geri cagrisi WSSunucusu kuruldugunda baglanir: kopru
        # secimi oturum/firma baglami gerektirir ve o baglam sunucuda
        # durur.
        radar = RadarVekili(konsol, ayarlar, kilit)
        konsol("RADAR", "Merkez kipi: radar oturumu saha koprusunde "
                        "kurulur; merkezde yerel baglanti denenmez.",
               "bilgi")
    else:
        radar = RadarIstemcisi(konsol, ayarlar, kilit)

    # M50 HVS SDK yalnız Windows x64 SAHA Köprüsünde yüklenir. GCS/Merkez
    # süreci, yerel kipte dahi cihaz DLL'si açmaz; M50 durumu ve izinli
    # komutlar ortak Köprü kanalı üzerinden vekil edilir.
    from goktungu.m50_vekil import M50Vekili
    m50 = M50Vekili(konsol, kilit)
    konsol("M50", "M50 elektro-optik oturumu saha Köprüsünde kurulur; "
                  "Merkezde SDK/DLL yüklenmez.", "bilgi")

    # --- Islem katmani ---
    takipci = Takipci()
    # IS93-ANGAJMAN-GORUNTU: goruntu hedefi konumu hedef deposundan
    # cozulur. Depo baglanmazsa goruntu angajmani REDDEDILIR
    # (cokme degil, gorunur ret).
    from goktungu import hedef_deposu as _hd93
    angajman = AngajmanYoneticisi(konsol, dron, kilit, takipci=takipci, radar=radar,
                                  hedef_deposu=_hd93.DEPO)
    # v2.5.21: hareketli (drona takili) kamera hedefi, dronun canli
    # MAVLink pozundan cozulur; depo bunun icin DronYoneticisi'ne
    # ihtiyac duyar. Ikinci ornek olusturulmaz, mevcut dron enjekte edilir.
    try:
        _hd93.DEPO.dron_yonetici_ata(dron)
    except Exception as _e_hd:
        konsol("HEDEF", f"Hedef deposu dron baglanamadi: {_e_hd}", "uyari")
    gorev = GorevYoneticisi(dron, konsol, kilit)
    ucus_gecmisi = UcusGecmisi(konsol)   # dron renkleri + ucus kayitlari
    manuel_kontrol = ManuelKontrol(dron, konsol, dji_kopru=dji_kopru)  # WASD/joystick
    # v2.4.44: Yer Istasyonu 2 (ESP32-S3 kontrol paneli). AYRI BIR PYTHON
    # SURECI GEREKMEZ: seri port bu surecin icinde bir is parcaciginda
    # okunur. `_duyur`/`_eylem` geri cagrilari WSSunucusu kurucusunda
    # baglanir, baglanti da sunucu kurulduktan SONRA baslatilir.
    istasyon2 = Istasyon2(konsol, ayarlar, manuel_kontrol=manuel_kontrol)
    dron_takip = DronTakipYoneticisi(konsol, dron, kilit)  # dron-dron takip
    suru = SuruYoneticisi(konsol, dron, kilit)  # v2.4.3: sürü uçuş
    # Mission Planner koprusu: her dron icin 9000+sysid UDP MAVLink yayini
    udp_yayin = UdpYayinYoneticisi(dron, konsol)
    dron.udp_yayin = udp_yayin

    # --- Kancalar (bagimliliklari tersine cevirmeden gevsek baglanti) ---
    # Seri baglanti kesilince aktif angajman + dron takipleri durdurulur
    def _kes_kancasi():
        angajman.sessiz_durdur()
        dron_takip.sessiz_durdur()
        suru.sessiz_durdur()
    dron.kes_kancasi = _kes_kancasi
    # Radar baglantisi kesilince takipci izleri temizlenir
    radar.kes_kancasi = takipci.izleri_temizle
    # v2.4.45: DRON BASINA HABERLESME KONSOLU
    # Dronun MAVLink/KOMUT/STATUS satirlari artik GENEL konsola degil
    # dronun kendi tamponuna yaziliyor. Bu kanca yeni satirlari arayuze
    # iletir; arayuz satiri ilgili dron kartinin altindaki acilir kapanir
    # konsola ekler. Kanca sunucu kuruldugu ANDA baglanamaz (sunucu
    # nesnesi asagida olusuyor), bu yuzden asagida sunucu kurulumundan
    # sonra atanir — buraya yalniz yer tutucu birakildi.
    # MISSION_* mesajlari gorev yoneticisine iletilir
    dron.gorev_kancasi = gorev.mesaj_isle
    # v2.4.43: angajman motoru, hedef dron GOREVDEYSE onun siradaki
    # rota noktasini okuyup kesisme noktasini oradan turetir. Enjeksiyon
    # kurucuya DEGIL buraya konur: gorev yoneticisi angajmandan SONRA
    # olusturuluyor (satir 193-194) ve sirayi degistirmek diger
    # kancalari kirar.
    angajman.gorev = gorev
    # v2.4.21: kalici dron kimlik kaydinda renk atamasi icin
    dron.ucus_gecmisi = ucus_gecmisi
    dji_kopru.ucus_gecmisi = ucus_gecmisi
    # v2.4.21: onceki calistirmadan kalmis acik oturumlari kapat
    try:
        from goktungu import veritabani as _vt21
        _kapanan = _vt21.acik_oturumlari_kapat()
        if _kapanan:
            konsol("DB", f"{_kapanan} yarim kalmis dron oturumu "
                   "kapatildi.")
    except Exception as _e21:
        konsol("DB", f"Oturum temizleme hatasi: {_e21}", "uyari")

    # --- v2.4.0: AI katmani (sunucular + kutuphane) ---
    # v2.4.61 AI TOPOLOJI DUZELTMESI
    # ------------------------------------------------------------------
    # OLCULEN KUSUR: `ai_izleme_baslat` merkezden
    # `http://{saha AI}:8900/izle` cagiriyordu. AI bilgisayarlari saha
    # agindadir (ornegin 192.168.1.100); merkez o adrese erisemez ve
    # her istek zaman asimina duserdi. Saglik yoklamasi da ayni yolu
    # kullandigi icin AI sunucusu merkezde surekli "yanit vermiyor"
    # gorunurdu. Ustelik isciye verilen akis adresi MERKEZIN 8801
    # vekilini gosteriyordu; isci ona da erisemezdi — zincir iki
    # noktadan birden kopuyordu.
    #
    # Merkez kipinde atama ve yoklama SAHADA yapilir.
    # LOKAL KURULUM DEGISMEZ.
    # FAZ19-IS73: AI katmani soküldü (IS71). Kip ayrimi kaldirildi.
    ai_yonetici = AIYonetici(konsol, ayarlar)
    # v2.4.2: drona bagli kamera tespitlerini aktif ucus kaydina
    # baglayabilmek icin ucus gecmisi referansi
    ai_yonetici.ucus_gecmisi = ucus_gecmisi
    # v2.4.7: canli tespit kutulari MJPEG uzerine cizilir
    ai_yonetici.video_proxy = video_proxy
    # v2.4.8: acilista ai_gorevler'i dolu kameralar otomatik izlemeye alinir
    ai_yonetici.kameralar = kameralar
    # v2.4.2: angajman motoru "ai_takip" hedef tipi icin AI koprusu
    angajman.ai_yonetici = ai_yonetici
    # v2.5.21: YEREL HEDEF BESLEME KOLU
    # ------------------------------------------------------------------
    # Yerel AI takip olayini (piksel) cografi hedefe cevirip HedefDeposu'ya
    # yazar; boylece operator-onayli angajman zinciri yerel AI ile de
    # calisir. NDJSON sozlesme akisindan BAGIMSIZDIR (bkz. yerel_hedef.py).
    # Besleyici `ai_yonetici.hedef_besleyici`ye baglanir; `takip_isle`
    # olayi hem NDJSON'a yazar (degismez) hem de bu besleyiciye iletir.
    from goktungu.yerel_hedef import YerelHedefBesleyici
    hedef_besleyici = YerelHedefBesleyici(konsol, kameralar, _hd93.DEPO,
                                          dron=dron)
    ai_yonetici.hedef_besleyici = hedef_besleyici
    kisiler = KisiYoneticisi()
    araclar = AracYoneticisi()

    # --- Sunucu katmani ---
    ws_sunucu = WSSunucusu(konsol, ayarlar, kullanicilar, lokasyonlar,
                           kayit, dron, radar, angajman, takipci,
                           m50=m50, etiket=etiket, rotalar=rotalar, gorev=gorev,
                           baglantilar=baglantilar, kameralar=kameralar,
                           video_proxy=video_proxy,
                           ucus_gecmisi=ucus_gecmisi,
                           manuel_kontrol=manuel_kontrol,
                           dron_takip=dron_takip,
                           suru=suru,
                           pilot=pilot, mesajlar=mesajlar,
                           dji_kopru=dji_kopru,
                           ai_yonetici=ai_yonetici,
                           kisiler=kisiler, araclar=araclar,
                           istasyon2=istasyon2)
    # v2.4.39: sanal dron = gercek ArduPilot SITL sureci
    from goktungu.sitl import SitlYoneticisi
    ws_sunucu.sitl = SitlYoneticisi(konsol, ayarlar)
    # v2.4.147: Sanal dalış profili yalnız bu canlı SITL yöneticisinin
    # sysid eşleşmesiyle yetkilendirilir. UI/WS verisi tek başına yeterli
    # değildir; görev katmanı süreç türü ve canlılığını burada sorgular.
    gorev.sitl = ws_sunucu.sitl
    # v2.5.18: Guncelleme denetimi arka planda yapilir; ana telemetri
    # dongusu veya acilis bu uzak HTTP istegini ASLA beklemez.
    # v2.5.30: Dosya tabanli (artimli) guncelleme. Eski .exe modeli
    # (guncelleme.py) yerine calisan surec ICINDEN yalniz DENETLER; asil
    # guncellemeyi arka plandaki gozetmen tetik dosyasiyla uygular.
    from goktungu.guncelleme_dosya import DosyaGuncellemeYoneticisi
    from goktungu.sabitler import VERI_KOKU, PROJE_KOKU
    from goktungu.paket_surum import UYGULAMA_SURUM
    ws_sunucu.guncelleme = DosyaGuncellemeYoneticisi(
        "gcs", UYGULAMA_SURUM, VERI_KOKU, kok=PROJE_KOKU, gunluk=konsol)
    ws_sunucu.guncelleme.denetle_arka_planda()
    ws_sunucu.betaflight = betaflight
    # Onceki oturumdan kalmis SITL surecleri portlari tutmaya devam eder
    # ve yeni baslatmalar "port dolu" diye basarisiz olur. Kayitli sanal
    # baglantilar acilista otomatik BASLATILMAZ (kullanici istemeden
    # simulator surecleri acmak dogru degil), yalniz artiklar temizlenir.
    try:
        ws_sunucu.sitl.artiklari_temizle()
    except Exception as _h:
        print(f"[SITL] Artik temizligi atlandi: {_h}")
    # v2.4.45: SITL dosyalari ARTIK PAKETE GOMULUDUR (kullanici istegi:
    # "gerekli tum dosyalari sisteme bir kere indir, sunucuyu baslatmadan
    # once SITL dosyalari zaten sistemde olsun"). Calisma aninda indirme
    # yok; bunun karsiligi olarak acilista dosyalarin varligi DENETLENIR.
    # Boylece eksiklik, kullanici sanal dron olusturmayi deneyip
    # 0xC0000135 alana kadar gizli kalmaz.
    #
    # v2.4.57: MERKEZ KIPINDE denetim ATLANIR. Sanal dron (SITL) bir
    # gelistirme/egitim aracidir ve pilotun makinesinde kosar; merkezde
    # baslatilmasi hem anlamsiz hem de sakincalidir (tum kiracilarin
    # paylastigi surecte islemci tuketir). Denetimin merkezde tek etkisi
    # her acilista iki satir uyari yazmakti; uyarinin isaret ettigi
    # eylem (arsivi ac, chmod ver) da merkez operatorunun isi degildir.
    try:
        from goktungu import merkez_kimlik as _mk_sitl
        _merkez_sitl = _mk_sitl.merkez_kipinde()
    except Exception:
        _merkez_sitl = False
    try:
        from goktungu import sitl as _sitl_mod
        if _merkez_sitl:
            _hazir, _eksik, _ayrinti = True, [], (
                "Merkez kipi: sanal dron denetimi atlandi "
                "(SITL pilotun makinesinde kosar).")
        else:
            _hazir, _eksik, _ayrinti = _sitl_mod.hazir_mi()
        if _hazir:
            konsol("SITL", _ayrinti)
        else:
            konsol("SITL", _ayrinti, "uyari")
            # v2.4.46: Iki ayri eksiklik tipi var ve verilecek ogut
            # farkli. DOSYA eksikse arsiv acilmali; IZIN eksikse chmod
            # gerekir. Tek tip ogut vermek kullaniciyi yanlis yone
            # gonderir - v2.4.45'te tam bu oldu: kullanici arsivi dogru
            # acmisti, eksik olan calistirma izniydi ve konsol ona
            # "paketi yeniden kurun" diyordu.
            _metin = " ".join(
                [str(x) for x in (list(_eksik or []) + [_ayrinti or ""])]
            ).lower()
            if "izin" in _metin or "noexec" in _metin:
                konsol("SITL",
                       "Sanal dron kullanilamaz: SITL ikilileri "
                       "calistirilabilir degil. Kurulum klasorunde su "
                       "komutu kosturun:  chmod +x sitl/*", "uyari")
            else:
                konsol("SITL",
                       "Sanal dron kullanilamaz. Tam paketi kurun ya da "
                       "goktungu-sitl arsivini sitl/ klasorune acin.",
                       "uyari")
    except Exception as _h:
        print(f"[SITL] Hazirlik denetimi atlandi: {_h}")

    # AI tespit/durum yayinlari (isci thread'lerinden) WS'e koprulenir
    ai_yonetici.duyuru_cb = ws_sunucu.duyur_threadden

    # v2.4.45: DRON BASINA HABERLESME KONSOLU
    # dron.dkonsol() cagrisi MAVLink okuma thread'inden gelir; bu yuzden
    # duyur_threadden kullanilir (asyncio dongusune guvenli aktarim).
    def _dron_konsol_kancasi(sysid, kayit):
        ws_sunucu.duyur_threadden({"tip": "dron_konsol_satir",
                                   "sysid": sysid, "satir": kayit})
    dron.konsol_kancasi = _dron_konsol_kancasi

    # v2.4.45: AI bilgisayarlarini SSH ile uzaktan baslatma + canli konsol
    # (kullanici istegi: play dugmesi SSH ile baglanip sunucuyu baslatsin,
    #  consol dugmesi SSH ciktilarini gostersin).
    # FAZ19-IS73: AI-SSH kurulumu kaldirildi. ai_ssh.py IS71'de
    # bos omurgaya cevrildi; nesne kurmak gereksizdi ve acilista
    # "SSH istemcisi bulunamadi" UYARISI basiyordu.

    # v2.4.49: SERVIS VE GUC YONETIMI
    # Kullanici istegi: "linux makinemde servis olarak olusturmak
    # istiyorum", "arayuzde servisi durdurup baslatabilecegim program
    # ayarlarinda bir bolum olsun", "kullanici menusu altinda
    # bilgisayari kapat dugmesi olsun".
    #
    # Servis yoneticisi systemd ile konusur. Sunucu SERVIS OLARAK
    # calismasa da modul yuklenir; boylece arayuz "kurulu degil" durumunu
    # gosterip kurulum komutunu soyleyebilir.
    #
    # v2.4.57: MERKEZ KIPINDE servis yoneticisi HIC KURULMAZ. Sebep
    # olculdu ve iki katmanli: (a) merkezde Program Ayarlari menusu
    # kaldirildi, dolayisiyla durumu gosterecek arayuz yok; (b) merkez
    # zaten `goktungu-app` systemd birimiyle isletiliyor, yani "kurulu
    # degil" iletisi YANLIS bilgi veriyordu. Uclusu: merkezde tum
    # kiracilar tek surece baglidir; kapatma yetkisi olcumu ve
    # onerilen `servis_kur.sh` komutu operatorun isidir, pilotun degil.
    try:
        from goktungu import merkez_kimlik as _mk_servis
        _merkez_kipi = _mk_servis.merkez_kipinde()
    except Exception:
        _merkez_kipi = False

    if _merkez_kipi:
        konsol("SERVIS",
               "Merkez kipi: servis yonetimi arayuzden kaldirildi "
               "(merkez systemd ile isletilir).", "bilgi")
    else:
        try:
            from goktungu.servis import ServisYoneticisi
            ws_sunucu.servis = ServisYoneticisi(konsol)
            _kip = ws_sunucu.servis.kip_olc(tazele=True)
            _d = ws_sunucu.servis.durum()
            if _d.get("kurulu"):
                konsol("SERVIS",
                       f"systemd birimi ({_kip}): {_d.get('ozet', '?')}")
            else:
                # Servis kurulu degil: bu bir HATA DEGIL, yalniz bilgi.
                # Kurulum komutunu simdi soylemek, kullanicinin arayuzde
                # bos bir panel gorup ne yapacagini bilememesini onler.
                konsol("SERVIS",
                       "systemd birimi kurulu degil. Acilista otomatik "
                       "baslatma icin: sudo bash servis_kur.sh")
            # Kapatma yetkisi acilista olculur; arayuz dugmeyi buna gore
            # etkin/pasif gosterir. Yetkisiz durumda dugmeyi etkin
            # gostermek, basildiginda hicbir sey olmamasi demektir.
            _gh, _gn = ws_sunucu.servis.guc_hazir("kapat")
            if not _gh:
                konsol("SERVIS",
                       "Bilgisayari kapatma yetkisi yok; menudeki dugme "
                       "pasif olacak. Yetki: sudo bash servis_kur.sh --izin",
                       "uyari")
        except Exception as _h:
            print(f"[SERVIS] Kurulum atlandi: {_h}")

    from goktungu.sabitler import HTTP_ADRES
    http_sunucu = HttpSunucusu(
        adres=ayarlar.yukle().get("http_adres", HTTP_ADRES),
        ai_yonetici=ai_yonetici,
        # IS9B-OTURUM-DEVRI: `/api/oturum/devir` ucu App oturum jetonu
        # uretmek icin WS sunucusunun jeton altyapisini kullanir.
        ws_sunucu=ws_sunucu,
        # FAZ19-IS60B: `/kamera/<id>` MJPEG yolu AYNI ORIGIN
        # uzerinden sunulur. Merkez kipinde tarayici 8801'e
        # ulasamiyordu (port dinlenmiyor + https/http karisimi).
        # `video_proxy` yukarida (satir ~404) zaten kurulmus:
        # merkez kipinde VideoVekili, yerel kipte VideoProxy.
        # Ikisi de `yayin_al`/`son_hata` tasir.
        video_proxy=video_proxy)

    # --- Video proxy (RTSP/RTP -> MJPEG) arka plan thread'inde ---
    threading.Thread(target=video_proxy.calistir, daemon=True).start()

    # --- Kayitli ayarlari yukle ---
    radar.ayar_yukle()                 # radar merkez yonu ofseti
    ws_sunucu.takipci_ayar_yukle()     # takipci/filtre ayarlari
    ws_sunucu.siniflandirma_ayar_yukle()  # kural tabanli siniflandirici

    # --- DJI koprusu: kayitli 'dji' baglantilarini acilista otomatik baslat ---
    try:
        dji_kayitlar = [b for b in baglantilar.listele()
                        if b.get("tur") == "dji"]
        for b in dji_kayitlar:
            dji_kopru.dinle(b)
        if not dji_kayitlar and not _merkez_kipi:
            print("[DJI] Kayitli DJI baglantisi yok; kopru portu (8790) kapali.")
            print("[DJI] Acmak icin: Baglanti Yoneticisi -> Yeni DJI Baglanti "
                  "-> Kaydet (acilista otomatik baslar).")
    except Exception as h:
        print(f"[DJI] Otomatik baslatma hatasi: {h}")

    # --- v2.4.44: Yer Istasyonu 2 panelini otomatik bagla ---
    # Ayarlardaki port (varsayilan /dev/ttyACM0) ile baglanmayi dener.
    # Port takili degilse PROGRAM NORMAL ACILIR; modul 2 sn'de bir
    # yeniden dener ve konsola yalniz ILK denemede uyari yazar.
    #
    # v2.4.57: MERKEZ KIPINDE hic denenmez. GCCDUAL cantasi fiziksel bir
    # aygittir ve SAHA bilgisayarina takilir; merkez sunucusunun seri
    # portu yoktur. Eski davranis merkezde iki sorun uretiyordu: acilista
    # "Port acilamadi (/dev/ttyACM0)" hatasi ve ardindan 2 saniyede bir
    # sonsuza kadar yeniden deneme. Merkezde bu yetenegin tek dogru
    # kaynagi kopru yaziliminda calisan GroundGCC servisidir.
    if _merkez_kipi:
        konsol("IST2",
               "Merkez kipi: GCCDUAL baglantisi denenmiyor "
               "(aygit kopru makinesinde, menu kopru servisine bagli).",
               "bilgi")
    else:
        try:
            istasyon2.otomatik_baslat()
        except Exception as _ei2:
            print(f"[IST2] Otomatik baslatma atlandi: {_ei2}")

    # --- v2.4.0: AI islem katmani ---
    ai_yonetici.baslat()   # saglik yoklama + kalici gorevleri geri yukle
    # v2.4.153: GRCOFF (offline Merkez) ayni zamanda AI sunucusudur. Yerel
    # isci baslatilir ve kaydedilir. GRCON (merkez kipi) AI'yi Goruntu
    # Koprusunde yapar; orada yerel isci ASLA calistirilmaz.
    if not _merkez_kipi:
        threading.Thread(target=_yerel_ai_bekci,
                         args=(ai_yonetici, http_sunucu),
                         name="yerel-ai-bekci", daemon=True).start()
    # http_sunucu gecirilir: isci ANA ADRESI gercek porttan turetir
    # (sabit 8000 varsayimi, port 8080'e dustugunde AI'yi sessizce
    # devre disi birakiyordu).
    # FAZ19-IS73B: yerel AI iscisi kaldirildi (AI katmani soküldü).

    return ws_sunucu, http_sunucu


# FAZ19-IS73B-YEREL-AI-ISCI-SOKUM
# `_yerel_ai_isci_baslat` kaldirildi. Fonksiyon `ai_sunucu.py`
# betigini alt surec olarak baslatiyordu; o betik IS71'de
# silindi. Merkez kipinde zaten erken donuyordu ama her acilista
# gunluge "[AI] Merkez kipi: yerel isci baslatilmadi" basiyordu.
# Islev yokken konusan kod, sistemde AI varmis izlenimi verir.


# FAZ20-GRCOFF-YEREL-AI
# Offline Merkezde AI işçisi aynı makinede başlar; GRCON/çevrimiçi kipte
# kesinlikle çalıştırılmaz. İşçi yalnız 127.0.0.1:8900 dinler ve görüntü
# ya da kimlik bilgisini haricî bir köprü/sunucuya taşımaz.
_yerel_ai_isci = None
_yerel_ai_gunluk = None

AI_ISCI_ADI = "GRCOFF Yerel AI"

# veritabani._varsayilan_ai_sunuculari() v2.4.0-2.4.152 arasi her yerel
# kurulumda bu iki ORNEK kaydi tohumluyordu. GRCOFF'ta ikisi de hayalettir
# (192.168.1.100 ornek adres; 127.0.0.1:8900 artik kullanilmayan port) ve
# arayuzde surekli "yanit vermiyor" gorunur. Kullanici adres/notu
# degistirdiyse kayit KORUNUR.
_AI_TOHUM_YER_TUTUCULARI = {
    ("ASUS Ascent GX10", "192.168.1.100", 8900),
    ("CPU AI Sunucusu (Yerel)", "127.0.0.1", 8900),
}
_AI_TOHUM_NOT_ONEKLERI = ("NVIDIA GB10 Grace Blackwell tabanli AI islem sunucusu.",
                          "Ana sunucu ile ayni makinede calisan CPU tabanli isci")


def _yerel_ai_portu():
    """v2.4.153: Kurulum AI portunu kaydirir (GOKTUNGU_AI_PORT=8910)."""
    try:
        return int(os.environ.get("GOKTUNGU_AI_PORT") or 8900)
    except ValueError:
        return 8900


def _yerel_ai_betigi():
    """Isci betiginin yolu. Pakette assets/python altinda, kaynakta kokte."""
    kok = os.path.dirname(os.path.abspath(__file__))
    for yol in (os.path.join(kok, "assets", "python", "ai_sunucu.py"),
                os.path.join(kok, "ai_sunucu.py")):
        if os.path.isfile(yol):
            return yol
    return None


def _yerel_ai_dinliyor(port=8900):
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.8) as soket:
            soket.sendall(b"GET /durum HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n")
            return b" 200 " in soket.recv(96)
    except OSError:
        return False

def _yerel_ai_isci_baslat(http_sunucu, ai_port=8900):
    global _yerel_ai_isci, _yerel_ai_gunluk
    try:
        from goktungu import merkez_kimlik
        if merkez_kimlik.merkez_kipinde():
            print("[AI] GRCON kipi: GRCOFF yerel AI işçisi başlatılmadı.")
            return
    except Exception:
        pass
    if _yerel_ai_dinliyor(ai_port):
        print(f"[AI] GRCOFF yerel AI işçisi zaten çalışıyor (127.0.0.1:{ai_port}).")
        return
    for _ in range(30):
        port = getattr(http_sunucu, "aktif_port", None)
        if port:
            break
        time.sleep(0.2)
    else:
        print("[AI] GRCOFF yerel AI işçisi başlatılmadı: HTTP portu alınamadı.")
        return
    try:
        from goktungu.sabitler import _veri_alt_yolu
        gunluk_yolu = _veri_alt_yolu("ai_isci.log")
        os.makedirs(os.path.dirname(gunluk_yolu), exist_ok=True)
        _yerel_ai_gunluk = open(gunluk_yolu, "a", encoding="utf-8")
        betik = _yerel_ai_betigi()
        if not betik:
            print("[AI] GRCOFF yerel AI işçisi başlatılamadı: ai_sunucu.py bulunamadı.")
            return
        tip = "nvidia" if shutil.which("nvidia-smi") else "cpu"
        komut = [sys.executable, betik, "--port", str(int(ai_port)), "--dinle", "127.0.0.1", "--ad", AI_ISCI_ADI,
                 "--tip", tip, "--kapasite", "4", "--ana", f"http://127.0.0.1:{int(port)}"]
        _yerel_ai_isci = subprocess.Popen(
            komut, cwd=os.path.dirname(betik), stdout=_yerel_ai_gunluk,
            stderr=subprocess.STDOUT, start_new_session=True)
        print(f"[AI] GRCOFF yerel AI işçisi başlatıldı ({tip}, pid={_yerel_ai_isci.pid}).")
    except Exception as e:
        print(f"[AI] GRCOFF yerel AI işçisi başlatılamadı: {e}")

def _yerel_ai_jetonu():
    """Yerel isci anahtarini hazirlar ve ortama koyar (isci miras alir).

    Anahtar veri dizininde KALICIDIR (0600): Merkez beklenmedik kapanip
    yeniden acildiginda hala calisan eski isci ayni anahtarla yayini
    okumaya devam eder. Yalniz loopback'ten gelen isteklerde gecerlidir
    (sunucu.py::_yerel_ai_isci_mi).
    """
    import secrets
    from goktungu.sabitler import _veri_alt_yolu
    yol = _veri_alt_yolu("ai_isci_anahtari")
    jeton = ""
    try:
        with open(yol, "r", encoding="utf-8") as f:
            jeton = f.read().strip()
    except OSError:
        pass
    if len(jeton) < 32:
        jeton = secrets.token_urlsafe(32)
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        gecici = yol + ".yeni"
        with open(gecici, "w", encoding="utf-8") as f:
            f.write(jeton)
        try:
            os.chmod(gecici, 0o600)
        except OSError:
            pass
        os.replace(gecici, yol)
    os.environ["GOKTUNGU_AI_ISCI_JETON"] = jeton
    return jeton


def _yerel_ai_kaydet(ai_yonetici, ai_port):
    """Yerel isciyi AI yoneticisine tanitir (tekillik: host+port).

    Port degismisse (or. 8900 -> 8910) eski yerel kayit silinir; aksi
    halde arayuzde surekli "yanit vermiyor" gorunen hayalet bir sunucu kalir.
    """
    tip = "nvidia" if shutil.which("nvidia-smi") else "cpu"
    for k in ai_yonetici.listele():
        if (k.get("ad"), str(k.get("host")), int(k.get("port") or 0)) in _AI_TOHUM_YER_TUTUCULARI \
                and str(k.get("notlar") or "").startswith(_AI_TOHUM_NOT_ONEKLERI):
            ai_yonetici.sil(k["id"])
            print(f"[AI] Kullanılmayan örnek AI kaydı kaldırıldı: {k.get('ad')}", flush=True)
            continue
        if (k.get("ad") == AI_ISCI_ADI
                and str(k.get("host")) in ("127.0.0.1", "localhost")
                and int(k.get("port") or 0) != int(ai_port)):
            ai_yonetici.sil(k["id"])
    ai_yonetici.kaydet(None, AI_ISCI_ADI, tip, "127.0.0.1", int(ai_port), 4,
                       notlar="GRCOFF Merkez ile birlikte otomatik başlar")


def _yerel_ai_gorevleri_esitle(ai_yonetici, son_deneme):
    """AI gorevi secili ama iscide akisi olmayan kameralari izlemeye alir.

    Kamera, isci henuz ayaga kalkmadan kaydedildiyse veya isci yeniden
    basladiysa gorev kaybolur; kullanici kamerayi yeniden kaydetmek
    zorunda kalmamali. Ayni kamera 30 sn'de bir kereden sik denenmez.
    """
    if ai_yonetici.kameralar is None or ai_yonetici._en_az_yuklu() is None:
        return
    iscide = set()
    for s in list(ai_yonetici.saglik.values()):
        for ak in ((s.get("son_durum") or {}).get("akislar") or []):
            try:
                iscide.add(int(ak.get("kamera_id")))
            except (TypeError, ValueError):
                pass
    simdi = time.time()
    for kam in ai_yonetici.kameralar.listele():
        gorevler = (kam.get("ai_gorevler") or "").strip()
        kid = int(kam["id"])
        if not gorevler or kid in iscide:
            continue
        if simdi - son_deneme.get(kid, 0) < 30:
            continue
        son_deneme[kid] = simdi
        sonuc = ai_yonetici.izleme_baslat(kid, "/kamera/%s" % kid,
                                          "gcs_proxy", gorevler)
        if not sonuc.get("tamam"):
            print(f"[AI] Kamera #{kid} izlemesi başlatılamadı: "
                  f"{sonuc.get('hata', '')}", flush=True)


def _yerel_ai_bekci(ai_yonetici, http_sunucu):
    """v2.4.153: GRCOFF'ta Merkez ayni zamanda AI sunucusudur.

    Isciyi baslatir, AI yoneticisine kaydeder, dusen isciyi artan
    beklemeyle yeniden baslatir ve gorevli kameralari izlemeye alir.
    """
    ai_port = _yerel_ai_portu()
    try:
        _yerel_ai_jetonu()
    except Exception as e:
        print(f"[AI] Yerel AI işçi anahtarı hazırlanamadı: {e}", flush=True)
    try:
        _yerel_ai_kaydet(ai_yonetici, ai_port)
    except Exception as e:
        print(f"[AI] Yerel AI işçisi kaydedilemedi: {e}", flush=True)
    deneme, son_baslatma, son_deneme = 0, 0.0, {}
    while True:
        try:
            if _yerel_ai_dinliyor(ai_port):
                deneme = 0
                # v2.4.158: AI izleme ARTIK otomatik başlatılmaz. Kullanıcı
                # kamerayı "Başlat" ile açtığında izleme başlar, "Durdur" ile
                # durur (manuel kontrol). Gözetmen yalnız işçiyi ayakta tutar.
            else:
                surec_var = (_yerel_ai_isci is not None
                             and _yerel_ai_isci.poll() is None)
                bekle = min(300, 15 * (2 ** deneme))
                if not surec_var and time.time() - son_baslatma >= bekle:
                    if deneme:
                        print("[AI] Yerel AI işçisi yanıt vermiyor; yeniden "
                              f"başlatılıyor (deneme {deneme + 1}).", flush=True)
                    _yerel_ai_isci_baslat(http_sunucu, ai_port)
                    son_baslatma = time.time()
                    deneme += 1
        except Exception as e:
            print(f"[AI] Yerel AI bekçisi: {e}", flush=True)
        time.sleep(10)


def _yerel_ai_isci_durdur():
    global _yerel_ai_isci, _yerel_ai_gunluk
    try:
        if _yerel_ai_isci and _yerel_ai_isci.poll() is None:
            _yerel_ai_isci.terminate()
            try:
                _yerel_ai_isci.wait(timeout=8)
            except subprocess.TimeoutExpired:
                _yerel_ai_isci.kill()
            print("[AI] GRCOFF yerel AI işçisi durduruldu.", flush=True)
    except Exception as e:
        print(f"[AI] Yerel işçi kapanışı atlandı: {e}", flush=True)
    finally:
        _yerel_ai_isci = None
        if _yerel_ai_gunluk:
            try:
                _yerel_ai_gunluk.close()
            except Exception:
                pass
            _yerel_ai_gunluk = None

def _port_dosyasi_yaz(ws_sunucu, http_sunucu):
    """v2.4.49: gercekte alinan portlari `veri/calisma.json`'a yazar.

    NEDEN GEREKLI: HTTP_PORTLAR = [8000, 8080, 8888, 9000, 5500] ve
    WS_PORTLAR = [8765, 8766, 8777, 9765] sirayla denenir. 8000 dolu
    ise sunucu SESSIZCE 8080'e duser. Kiosk betigi tarayiciyi hangi
    adrese yonlendirecegini bilemez; 8000 varsayarsa BOS SAYFA acar ve
    operator iki ekranda da hicbir sey gormez.

    Portlar arka plan thread'inde ve asyncio dongusunde asenkron olarak
    baglanir; bu yuzden burada kisa bir bekleme ile yoklanir. Bekleme
    sinirlidir (2 sn): baglanma basarisiz olsa bile servis yine
    baslamalidir, yalnizca kiosk varsayilan porta duser.

    Dosya ayrica PID ve baslangic zamani icerir; servis panelinin
    "gercekten bu surec mi calisiyor" sorusunu yanitlar.
    """
    import json
    import os
    import time as _t
    from goktungu.sabitler import PROJE_KOKU, HTTP_PORTLAR, WS_PORTLAR

    # Portlarin baglanmasini bekle (en fazla 20 sn, 50 ms adimlarla).
    #
    # OLCULEN DAVRANIS: WS portu `asyncio.run(ws_sunucu.calistir())`
    # icinde baglanir; bu cagri main() icinde bu islevden SONRA gelir.
    # Dolayisiyla bu islev ANA THREAD'de cagrilirsa WS portu asla
    # gorulemez ve daima tahmin yazilir. Bu yuzden `main()` bu islevi
    # ayri bir thread'de baslatir ve burada beklemek guvenlidir.
    #
    # 20 sn secildi: SITL hazirlik denetimi, veritabani gocu ve
    # sertifika uretimi acilisi yavaslatabilir. Sure asilirsa tahmin
    # yazilir; servis yine baslar.
    _son = _t.time() + 20.0
    while _t.time() < _son:
        if (getattr(http_sunucu, "aktif_port", None)
                and getattr(ws_sunucu, "aktif_ws_port", None)):
            break
        _t.sleep(0.05)

    # Baglanamadiysa listenin ILK portunu yaz; bu bir tahmindir ve
    # dosyada `kesin: false` ile isaretlenir, boylece kiosk betigi
    # gerekirse yoklama yapabilir.
    hp = getattr(http_sunucu, "aktif_port", None)
    wp = getattr(ws_sunucu, "aktif_ws_port", None)
    kesin = bool(hp and wp)

    veri = {
        "surum": __import__("goktungu").__version__,
        "pid": os.getpid(),
        "baslangic": round(_t.time(), 2),
        "http_port": int(hp or HTTP_PORTLAR[0]),
        "ws_port": int(wp or WS_PORTLAR[0]),
        "kesin": kesin,
    }
    # v2.4.133 / İş 107: `calisma.json` tarihsel olarak `veri/`
    # altinda kalan bir durum dosyasidir. Ham VERI_KOKU ile birlestirmek
    # eski duz kurulumda App kokune yazar ve systemd servis hesabinda
    # `calisma.json.yeni` Permission denied uretir. `_veri_alt_yolu`
    # hem eski (<kok>/veri) hem yeni tasinabilir veri kokunu dogru cozer.
    # Dosya PG'ye tasinmaz: kiosk ve servis paneli sunucu kapaliyken de okur.
    from goktungu.sabitler import _veri_alt_yolu
    hedef = _veri_alt_yolu("calisma.json")
    os.makedirs(os.path.dirname(hedef), exist_ok=True)
    # Atomik yazim: yarim yazilmis JSON'u kiosk betigi okuyamaz.
    gecici = hedef + ".yeni"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=2)
    os.replace(gecici, hedef)
    print(f"[GCS] Calisma bilgisi yazildi: http={veri['http_port']} "
          f"ws={veri['ws_port']} pid={veri['pid']}"
          + ("" if kesin else "  (TAHMIN — portlar henuz baglanmadi)"))


def _kapanis_temizligi(ws_sunucu):
    """v2.4.49: cikis yolundan bagimsiz ortak temizlik.

    SITL surecleri ayri islemlerdir; sunucu kapanirken kendiliginden
    olmezler. Kalirlarsa tuttuklari port bloklari bir sonraki oturumda
    "port dolu" hatasi verir. Bu islev hem Ctrl+C (finally) hem de
    SIGTERM (sinyal isleyicisi) yolundan cagrilir.

    Her adim ayri ayri korunur: birinin basarisizligi digerini
    engellememelidir, cunku amac kapanisi TAMAMLAMAKTIR.
    """
    _yerel_ai_isci_durdur()
    try:
        if getattr(ws_sunucu, "sitl", None):
            ws_sunucu.sitl.tumunu_durdur()
            print("[SITL] Tum SITL surecleri durduruldu.", flush=True)
    except Exception as e:
        print(f"[SITL] Kapanis temizligi atlandi: {e}", flush=True)

    # v2.4.49: calisma.json bayat kalmasin. Servis panelinin ve kiosk
    # betiginin "calisiyor" sanmasini onler.
    try:
        import os as _os
        from goktungu.sabitler import _veri_alt_yolu
        _d = _veri_alt_yolu("calisma.json")
        if _os.path.exists(_d):
            _os.remove(_d)
    except Exception:
        pass                  # kritik degil; sessiz gec


def _sigterm_kur(ws_sunucu):
    """v2.4.49: SIGTERM/SIGHUP alindiginda temizleyip HEMEN cikar.

    NEDEN EKLENDI: systemd `systemctl stop` ile SIGTERM gonderir.
    Python'da SIGTERM varsayilani sureci ANINDA oldurur; bu durumda
    main() icindeki `finally` blogu HIC CALISMAZ ve baslatilan SITL
    (arducopter) surecleri yetim kalir.

    NEDEN `raise KeyboardInterrupt` YETMEDI (py-spy ile olculdu):
    KeyboardInterrupt yukseltmek sureci kapatmadi. Yigin izi kapanisin
    nerede takildigini gosterdi:

        _cancel_all_tasks (asyncio/runners.py:205)
        close (asyncio/runners.py:70)
        run (asyncio/runners.py:193)

    `asyncio.run()` cikarken bekleyen TUM gorevleri iptal edip
    bitmelerini bekler. websockets sunucusu ve yayin dongusu bu iptali
    tamamlamadigi icin `run_until_complete` sonsuz bekledi; surec
    "SIGTERM alindi" yazip ayakta kaldi. systemd bu durumda
    `TimeoutStopSec` (varsayilan 90 sn) bekler, sonra SIGKILL atar —
    ve SIGKILL hicbir temizlik calistirmaz. Yani SITL surecleri yine
    yetim kalirdi.

    COZUM: temizligi sinyal isleyicisinin KENDISI yapar, ardindan
    `os._exit()` ile asyncio kapanis protokolunu tamamen atlar.
    `os._exit()` normalde kacinilmasi gereken bir cagridir cunku
    `finally`/`atexit` atlanir; burada guvenlidir, cunku kritik
    temizlik (SITL durdurma) ondan ONCE elle yapilir.

    Cikis kodu 0'dir: `systemctl stop` sonrasi servisin `failed`
    gorunmemesi icin. SIGTERM ile kapanmak bir hata degildir.
    """
    import os
    import signal

    _kapandi = {"evet": False}

    def _kapat(imza, cerceve):
        # Ikinci sinyal gelirse temizligi tekrarlamayip aninda cik;
        # aksi halde `systemctl stop` iki kez sinyal gonderdiginde
        # temizlik ortasinda yeniden girilebilir.
        if _kapandi["evet"]:
            os._exit(0)
        _kapandi["evet"] = True

        ad = {getattr(signal, "SIGTERM", None): "SIGTERM",
              getattr(signal, "SIGHUP", None): "SIGHUP"}.get(imza, str(imza))
        print(f"\n[GCS] {ad} alindi; duzgun kapatiliyor.", flush=True)
        _kapanis_temizligi(ws_sunucu)
        print("[GCS] Kapandi.", flush=True)
        # stdout'u bosalt; os._exit tamponu bosaltmaz ve journal'a
        # yazilan son satirlar kaybolur.
        try:
            import sys as _s
            _s.stdout.flush()
            _s.stderr.flush()
        except Exception:
            pass
        os._exit(0)

    for _ad in ("SIGTERM", "SIGHUP"):
        _im = getattr(signal, _ad, None)
        if _im is None:
            continue          # Windows'ta SIGHUP yok
        try:
            signal.signal(_im, _kapat)
        except (ValueError, OSError, RuntimeError) as e:
            # Ana thread disinda cagrilirsa ValueError verir; servis
            # yine calisir, yalnizca temizlik garantisi zayiflar.
            print(f"[GCS] {_ad} yakalanamadi ({e}); "
                  "kapanista SITL temizligi garanti degil.")


def main():
    ws_sunucu, http_sunucu = uygulama_kur()

    # v2.4.49: sinyal kancasi ws_sunucu kurulduktan SONRA takilir,
    # cunku temizlik icin ona ihtiyac var. Kurulum sirasinda gelen
    # SIGTERM varsayilan davranisla (ani olum) islenir; o asamada
    # henuz SITL baslatilmadigi icin temizlenecek bir sey yoktur.
    _sigterm_kur(ws_sunucu)

    # HTTP sunucusu arka plan thread'inde calisir
    threading.Thread(target=http_sunucu.calistir, daemon=True).start()

    # v2.4.153: Yerel AI isci baslatma buradan KALDIRILDI; uygulama_kur()
    # icindeki `_yerel_ai_bekci` yapar. Iki yol birlikte kalinca ayni anda
    # iki isci sureci aciliyordu (olculdu: art arda iki pid).

    # v2.4.49: servis kipinde gercek portlari diske yaz. Portlar sirayla
    # denendigi icin (HTTP_PORTLAR/WS_PORTLAR) hangi portun alindigi
    # ancak baglandiktan sonra bilinir. Kiosk betigi bu dosyayi okur;
    # aksi halde 8000 varsayar ve sunucu 5500'e dustuyse bos sayfa acar.
    #
    # AYRI THREAD'DE calisir: WS portu asagidaki `asyncio.run` icinde
    # baglanir, yani ana thread'de beklemek imkansizdir (olculdu:
    # daima `kesin: false` yaziliyordu). daemon=True cunku yazim
    # basarisiz olsa bile kapanisi geciktirmemelidir.
    def _port_yaz_gorevi():
        try:
            _port_dosyasi_yaz(ws_sunucu, http_sunucu)
        except Exception as _p:
            print(f"[GCS] Port dosyasi yazilamadi: {_p}")

    threading.Thread(target=_port_yaz_gorevi, daemon=True,
                     name="port-yaz").start()

    # WebSocket sunucusu + telemetri yayini ana asyncio dongusunde
    try:
        asyncio.run(ws_sunucu.calistir())
    except KeyboardInterrupt:
        print("\n[GCS] Kapatiliyor.")
    finally:
        # v2.4.39/v2.4.49: SITL surecleri ayri islemlerdir; sunucu
        # kapanirken otomatik olarak olmezler. Ctrl+C yolunda temizlik
        # buradan calisir; SIGTERM yolunda sinyal isleyicisi kendisi
        # cagirir (bkz. _sigterm_kur aciklamasi).
        _kapanis_temizligi(ws_sunucu)


if __name__ == "__main__":
    main()
