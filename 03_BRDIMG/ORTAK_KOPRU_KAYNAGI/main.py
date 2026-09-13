#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GOKTUNGU KOPRU YAZILIMI — giris noktasi.

Kullanim:
    python3 main.py                 # paneli ac ve tarayiciyi baslat
    python3 main.py --tarayici-yok  # servis olarak calisirken
    python3 main.py --port 8791     # bu calisma icin baska port

Kullanici istegi geregi bu program KONSOL UYGULAMASI DEGILDIR: yerel
bir web paneli acar ve tarayicida gosterir. Konsol yalniz gunluk akisi
icindir; kullanici hicbir komut yazmaz.
"""
import argparse
import os
import signal
import sys
import threading
import time
import webbrowser

# --- PYTHON SURUM DENETIMI ------------------------------------------
# Ice aktarimlardan ONCE yapilir: eski Python'da sozdizimi hatasi
# verebilecek bir modul yuklenmeden once anlasilir mesaj vermek
# gerekir. "SyntaxError: invalid syntax" goren kullanici sorunun
# Python surumu oldugunu anlamaz.
# ASGARI 3.10 SECILDI (3.11 DEGIL). Gerekce: Ubuntu 22.04 LTS'nin
# varsayilan python3'u 3.10'dur ve .deb paketinin kurulum sonrasi
# betigi sanal ortami `python3` ile kurar. Asgari 3.11 iken servis
# her acilista "surum yetersiz" diyerek cikiyor, systemd 10 kez
# yeniden deniyor ve kurulum sessizce ise yaramaz bir servis
# birakiyordu — bu kusur gercek .deb kurulumunda OLCULDU.
#
# 3.10 guvenli: kaynak agacinda 3.11'e ozgu hicbir ozellik yok
# (ExceptionGroup, except*, TaskGroup, tomllib, StrEnum, Self,
# asyncio.timeout taramasi bos dondu) ve kopru 3.10 sanal ortaminda
# uctan uca calistirilip panelin HTTP 200 dondurdugu dogrulandi.
ASGARI_PYTHON = (3, 10)
if sys.version_info < ASGARI_PYTHON:
    sys.stderr.write(
        "\n" + "=" * 62 + "\n"
        " GOKTUNGU KOPRU — PYTHON SURUMU YETERSIZ\n"
        + "=" * 62 + "\n"
        " Gereken : Python %d.%d veya ustu\n"
        " Bulunan : Python %d.%d.%d  (%s)\n\n"
        " Kurulum paketleri uygun surumu bulur.\n"
        " Elle kurulum icin: https://www.python.org/downloads/\n"
        % (ASGARI_PYTHON[0], ASGARI_PYTHON[1],
           sys.version_info[0], sys.version_info[1],
           sys.version_info[2], sys.executable))
    sys.exit(3)

# Paket ice aktarimi: dosya nereden calistirilirsa calistirilsin
# `kopru` paketi bulunmalidir.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kopru import ayar as ayar_mod          # noqa: E402
from kopru import kilit as kilit_mod         # noqa: E402
from kopru.panel import Panel                # noqa: E402
from kopru.uygulama import Uygulama          # noqa: E402

_DUR = threading.Event()


def _gunluk(etiket, metin, seviye="bilgi"):
    im = {"bilgi": "", "basari": "[OK] ", "uyari": "[UYARI] ",
          "hata": "[HATA] "}.get(seviye, "")
    print("%s [%s] %s%s" % (time.strftime("%H:%M:%S"), etiket, im, metin),
          flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="GOKTUNGU Kopru Yazilimi %s" % ayar_mod.SURUM)
    ap.add_argument("--port", type=int, default=None,
                    help="Yerel panel portu (varsayilan: ayardan)")
    ap.add_argument("--arayuz", default=None,
                    help="Panelin baglanacagi adres (varsayilan 0.0.0.0; "
                         "yalniz bu bilgisayar icin 127.0.0.1)")
    ap.add_argument("--tarayici-yok", action="store_true",
                    help="Tarayiciyi acmaz (servis kipi)")
    a = ap.parse_args(argv)

    print("=" * 62)
    print(" GOKTUNGU KOPRU YAZILIMI  %s" % ayar_mod.SURUM)
    print(" Gokkubbe Teknoloji Anonim Sirketi")
    print("=" * 62)

    # Tek ornek kilidi: iki kopru sureci ayni merkez kimligini
    # kullanirsa merkez baglantisi sonsuz dusurme dongusune girer
    # (bkz. kopru/kilit.py). Panelden ONCE alinir; ikinci ornegin
    # yarim bir panel acmasi kullaniciyi yanlis yonlendirir.
    try:
        kilit_mod.al()
    except kilit_mod.KilitMesgul as e:
        _gunluk("KOPRU", str(e), "hata")
        return 4

    uyg = Uygulama(gunluk=_gunluk)
    panel = Panel(uyg, arayuz=a.arayuz, port=a.port)
    try:
        adres = panel.baslat()
    except OSError as e:
        # En sik karsilasilan kurulum hatasi: port dolu. Kullaniciya ne
        # yapacagini SOYLE; ciplak yigin izi hicbir sey anlatmaz.
        _gunluk("PANEL", "Panel portu acilamadi: %s" % e, "hata")
        _gunluk("PANEL", "Baska bir port denemek icin: "
                         "python3 main.py --port 8791", "bilgi")
        return 2

    _gunluk("PANEL", "Panel hazir: %s" % adres, "basari")
    if panel.arayuz not in ("127.0.0.1", "localhost", "::1"):
        # Kullaniciya "0.0.0.0" yazmak ise yaramaz: o adres tarayiciya
        # girilemez. Tarayiciya GERCEKTEN girilebilecek adresler
        # listelenir.
        for adr in panel.erisim_adresleri():
            _gunluk("PANEL", "Erisim adresi: %s" % adr, "bilgi")
        _gunluk("PANEL",
                "Panel aga acik (%s). Ayni agdaki herkes panel sayfasini "
                "gorebilir; servisleri yonetmek icin merkez girisi "
                "zorunludur, merkeze kayit ve ayar yazma ise yalniz bu "
                "bilgisayardan yapilabilir." % panel.arayuz, "uyari")
        _gunluk("PANEL",
                "Erisimi tek bir aga sinirlamak icin: sudo ufw allow from "
                "192.168.0.0/16 to any port %d proto tcp" % panel.port,
                "bilgi")
        _gunluk("PANEL",
                "Yalniz bu bilgisayardan erisim icin panel ayarlarinda "
                "'Panel arayuzu' alanina 127.0.0.1 yazin.", "bilgi")
    _gunluk("VERI", "Ayar ve gunluk dizini: %s" % ayar_mod.veri_dizini())

    if ayar_mod.kimlik_var():
        tamam, hata = uyg.ajan_baslat()
        if not tamam:
            _gunluk("KOPRU", "Ajan baslatilamadi: %s" % hata, "uyari")
    else:
        _gunluk("KOPRU", "Merkez kaydi yok. Panelden giris yapip "
                         "'Bu bilgisayari merkeze kaydet' dugmesini "
                         "kullanin.", "uyari")

    uyg.acilista_servisleri_baslat()
    # Ag erisimi veya katalog gecikirse panelin acilisini engellemez.
    uyg.guncelleme.denetle_arka_planda()

    if not a.tarayici_yok:
        # Tarayici acilisi ayri is parcaciginda: bazi masaustlerinde
        # `webbrowser.open` saniyelerce bloke olur ve panel gecikir.
        threading.Thread(target=lambda: webbrowser.open(adres),
                         daemon=True).start()

    def _kapat(*_):
        _DUR.set()

    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(s, _kapat)
        except Exception:
            pass

    try:
        while not _DUR.is_set():
            _DUR.wait(1.0)
    except KeyboardInterrupt:
        pass
    _gunluk("KOPRU", "Kapatiliyor...", "bilgi")
    uyg.kapat()
    panel.durdur()
    kilit_mod.birak()
    return 0


if __name__ == "__main__":
    sys.exit(main())
