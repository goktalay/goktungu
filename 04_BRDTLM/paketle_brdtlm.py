#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""GOKTUNGU BRDTLM — dagitim paketi ince sarmalayicisi (Faz 5).

## NE YAPAR

BRDTLM (telemetri/cihaz koprusu) urununu, BRDIMG ile PAYLASILAN cekirdek
kaynaktan (../03_BRDIMG/ORTAK_KOPRU_KAYNAGI) uretir. Ayri bir kaynak
agaci KOPYALANMAZ; yalnizca urun profili degistirilerek paket kimligi
(paket adi, servis adi, ikon adi, panel portu, kurulum dizini) BRDTLM'e
ozgu kilinir ve `GOKTUNGU_KOPRU_URUN=brdtlm` gomulur.

    BRDTLM = dron (ArduPilot/Betaflight) + M50 + radar + GroundGCC
    BRDIMG = video + ai

## NEDEN SARMALAYICI (ayri kaynak degil)

Cekirdek tek kaynaktan yururse (servisler.py, servis_dron.py, panel...),
bir kusur iki urunde birden duzelir. Iki ayri kopya, birinde duzeltilen
hatanin otekinde yasamasina yol acardi. Bu sarmalayici, mevcut
ureticileri (deb_uret.py, setup.nsi) BRDTLM parametreleriyle CAGIRIR.

## KULLANIM

    python3.11 paketle_brdtlm.py --deb    # Ubuntu .deb (goktungu-kopru-tlm)
    python3.11 paketle_brdtlm.py --win    # Windows setup.exe (makensis)
    python3.11 paketle_brdtlm.py          # arac bulunan her platform icin

.deb icin `deb_uret.py --urun brdtlm`, Windows icin ise `makensis` uygun
`-D` tanimlariyla cagrilir. Her iki uretici de ORTAK kaynak dizininde
calistirilir (goreli `File`/yol tanimlari orada cozulur).

## GERIYE UYUMLULUK

Bu betik yalnizca BRDTLM uretir; BRDIMG cikti yolu (deb_uret.py'nin
varsayilani ve `-D` verilmeden derlenen setup.nsi) DEGISMEZ, BYTE-AYNI
kalir.
"""
import argparse
import os
import shutil
import subprocess
import sys

BU_DIZIN = os.path.dirname(os.path.abspath(__file__))
# KAYNAK_KONUMU.txt'te belgelenen paylasilan cekirdek.
ORTAK = os.path.abspath(os.path.join(
    BU_DIZIN, "..", "03_BRDIMG", "ORTAK_KOPRU_KAYNAGI"))

URUN_PROFIL = "brdtlm"

# Windows setup.nsi'nin `!ifndef` ile korunan tanimlarina karsilik gelen
# BRDTLM degerleri. `SERVIS_ADI`, servis_win.py'nin brdtlm profilinde
# kaydettigi servis adiyla (`GoktunguKopruTlm`) BIREBIR ayni olmalidir;
# aksi halde setup.nsi'deki `net stop/start` yanlis servisi hedefler.
WIN_TANIMLARI = {
    "URUN": "GOKTUNGU Kopru Telemetri",
    "URUN_KISA": "GOKTUNGU Kopru TLM",
    "SERVIS_ADI": "GoktunguKopruTlm",
    "PANEL_URL": "http://127.0.0.1:8791/",
    "KAYIT_ANAHTAR":
        "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\GoktunguKopruTlm",
    "AYAR_ANAHTAR": "Software\\VEILOX\\GoktunguKopruTlm",
    "CIKTI_AD": "GOKTUNGU-Kopru-TLM-Setup",
    "KURULUM_DIZIN": "$PROGRAMFILES64\\Goktungu\\KopruTlm",
    "URUN_PROFIL": URUN_PROFIL,
}


def _surum():
    """Cekirdegin tek surum kaynagi: kopru.surumler.KOPRU_SURUM."""
    sys.path.insert(0, ORTAK)
    from kopru.surumler import KOPRU_SURUM
    return KOPRU_SURUM


def deb_uret():
    """Ubuntu .deb paketini uretir (deb_uret.py --urun brdtlm)."""
    betik = os.path.join(ORTAK, "deb_uret.py")
    print("[BRDTLM] .deb uretiliyor: %s --urun %s" % (betik, URUN_PROFIL))
    r = subprocess.run(
        [sys.executable, betik, "--urun", URUN_PROFIL], cwd=ORTAK)
    return r.returncode


def win_uret():
    """Windows setup.exe'sini uretir (makensis -D... setup.nsi).

    `makensis` bulunamazsa, kullanilacak komut ekrana yazilir ve hata
    kodu dondurulur; boylece Windows/NSIS bulunan bir makinede aynen
    calistirilabilir.
    """
    surum = _surum()
    komut = ["makensis", "-DSURUM=%s" % surum]
    for ad, deger in WIN_TANIMLARI.items():
        komut.append("-D%s=%s" % (ad, deger))
    komut.append("setup.nsi")
    makensis = shutil.which("makensis")
    if not makensis:
        print("[BRDTLM] makensis bulunamadi. Windows/NSIS makinesinde, "
              "ORTAK kaynak dizininde su komutu calistirin:")
        print("    cd %s" % ORTAK)
        print("    " + " ".join(
            (a if " " not in a else '"%s"' % a) for a in komut))
        return 2
    print("[BRDTLM] setup.exe uretiliyor (makensis)...")
    r = subprocess.run(komut, cwd=ORTAK)
    return r.returncode


def main(argv=None):
    ap = argparse.ArgumentParser(description="BRDTLM paketleyici (sarmalayici)")
    ap.add_argument("--deb", action="store_true", help="Ubuntu .deb uret")
    ap.add_argument("--win", action="store_true",
                    help="Windows setup.exe uret (makensis)")
    a = ap.parse_args(argv)

    if not os.path.isdir(ORTAK):
        print("HATA: ortak kaynak bulunamadi: %s" % ORTAK, file=sys.stderr)
        return 1

    yapilacak_deb = a.deb or not (a.deb or a.win)
    yapilacak_win = a.win or not (a.deb or a.win)

    kod = 0
    if yapilacak_deb:
        kod = deb_uret() or kod
    if yapilacak_win:
        kod = win_uret() or kod
    return kod


if __name__ == "__main__":
    sys.exit(main())
