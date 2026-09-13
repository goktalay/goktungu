#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GOKTUNGU v2.4.46 — SITL CALISTIRILABILIRLIK SINAVI

Kullanim (kurulum kokunde ya da gelistirme dizininde):
    python3 sinav_2446_sitl.py

Neyi olcer: sanal dronun calistirilamamasina yol acan IKI kusurun
kalici olarak kapandigini.

  Kusur 1 (kullanici bildirdi): [Errno 13] Permission denied
     '/home/mkaderoglu/goktungu/sitl/arducopter'
     -> Dosya vardi, DLL sorunu yoktu; +x biti yoktu. Izin biti dosyada
        tasinmaz, dosya sisteminde durur; Windows/OneDrive/NTFS uzerinden
        kopyalamak ya da arsivi elle acmak biti dusurur.

  Kusur 2 (kullanici bildirdi, izin duzeltmesinden SONRA):
     [Errno 8] Exec format error
     -> Dosya bu makinede calistirilabilir bir ikili degil: yanlis
        isletim sistemi bicimi, yanlis mimari ya da bozuk dosya.

Sinav bunlarin her ikisinin de SUREC BASLATILMADAN once yakalandigini,
kullaniciya anlasilir gerekce verildigini ve mumkun oldugunda kendi
kendine onarildigini olcer. Gercek dosyalar uzerinde calisir; taklit
(mock) kullanilmaz.
"""
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile

GECTI = 0
KALDI = 0
BASARISIZLAR = []


def olc(baslik, kosul, ayrinti=""):
    global GECTI, KALDI
    if kosul:
        GECTI += 1
        print("[GECTI] %s" % baslik)
    else:
        KALDI += 1
        BASARISIZLAR.append(baslik)
        print("[KALDI] %s" % baslik)
        if ayrinti:
            print("        %s" % str(ayrinti)[:300])


def bolum(m):
    print()
    print("--- %s " % m + "-" * max(0, 58 - len(m)))


def kok_bul():
    """Hem kurulum kokunde hem gelistirme dizininde calisabilmeli."""
    burasi = os.path.dirname(os.path.abspath(__file__))
    for aday in (burasi, os.path.join(burasi, "goktungu")):
        if os.path.isfile(os.path.join(aday, "goktungu", "sitl.py")):
            return aday
    return burasi


KOK = kok_bul()
sys.path.insert(0, KOK)
from goktungu import sitl  # noqa: E402


def sahte_ikili(dizin, ad, kaynak=None, icerik=None):
    """Deneme icin bir dosya olusturur."""
    y = os.path.join(dizin, ad)
    if kaynak:
        shutil.copy(kaynak, y)
    else:
        with open(y, "wb") as f:
            f.write(icerik or b"")
    return y


def main():
    print("=" * 66)
    print("GOKTUNGU v2.4.46 — SITL CALISTIRILABILIRLIK SINAVI")
    print("=" * 66)
    print("Kok        : %s" % KOK)
    print("Makine     : %s %s" % (platform.system(), platform.machine()))
    windows = platform.system().lower().startswith("win")
    gercek_dizin = sitl.SITL_KLASORU
    gercek_kopter = os.path.join(gercek_dizin,
                                 "ArduCopter.elf" if windows
                                 else "arducopter")

    # ------------------------------------------------------------------
    bolum("1. MODUL SOZLESMESI")
    for ad in ("izin_onar", "izin_onar_klasor", "ikili_bicimi",
               "bicim_denetle", "hazir_mi", "dll_denetle"):
        olc("sitl.%s() var" % ad, callable(getattr(sitl, ad, None)))
    olc("SitlYoneticisi._mimari_kurtar() var",
        callable(getattr(sitl.SitlYoneticisi, "_mimari_kurtar", None)))
    olc("IKILI_IZIN sabiti 0o755", getattr(sitl, "IKILI_IZIN", None) == 0o755)
    olc("ELF_MAKINE tablosu x86-64 iceriyor",
        0x3e in getattr(sitl, "ELF_MAKINE", {}))
    olc("ELF_MAKINE tablosu AArch64 iceriyor",
        0xb7 in getattr(sitl, "ELF_MAKINE", {}))
    olc("MAKINE_UYUM tablosu bu makineyi taniyor ya da bilincli atliyor",
        isinstance(getattr(sitl, "MAKINE_UYUM", None), dict))
    olc("ARM indirme adresi tanimli",
        bool((sitl.INDIRME.get("linux_arm") or {}).get("arducopter")))

    # ------------------------------------------------------------------
    bolum("2. GERCEK KURULUM DOSYALARI")
    olc("sitl/ klasoru var", os.path.isdir(gercek_dizin), gercek_dizin)
    if os.path.isdir(gercek_dizin):
        olc("beklenen ikili var", os.path.isfile(gercek_kopter),
            gercek_kopter)
        if os.path.isfile(gercek_kopter):
            b = sitl.ikili_bicimi(gercek_kopter)
            olc("ikili bicimi bu isletim sistemine uygun",
                b.get("bicim") == ("pe" if windows else "elf"),
                b.get("bicim"))
            uygun, neden = sitl.bicim_denetle(gercek_kopter)
            olc("bicim_denetle gercek ikiliyi kabul etti", uygun, neden)
            if not windows:
                olc("ikili calistirilabilir (izin)",
                    os.access(gercek_kopter, os.X_OK))
        # Windows ikilileri Linux'ta REDDEDILMELI (ve tersi)
        karsi = os.path.join(gercek_dizin,
                             "arducopter" if windows else "ArduCopter.elf")
        if os.path.isfile(karsi):
            uygun, neden = sitl.bicim_denetle(karsi)
            olc("diger isletim sisteminin ikilisi reddedildi", not uygun,
                "beklenen: red, alinan: kabul")
            olc("red gerekcesi isletim sistemini adiyla soyluyor",
                (not uygun) and any(
                    k in (neden or "").lower()
                    for k in ("windows", "linux", "macos")))

    # ------------------------------------------------------------------
    bolum("3. IZIN ONARIMI (Errno 13 kusuru)")
    if windows:
        print("  Windows'ta calistirma izni biti yok; bolum atlandi.")
    else:
        gec = tempfile.mkdtemp(prefix="sinav2446_izin_")
        try:
            y = sahte_ikili(gec, "arducopter", kaynak=gercek_kopter) \
                if os.path.isfile(gercek_kopter) else \
                sahte_ikili(gec, "arducopter", icerik=b"\x7fELF" + b"\0" * 60)
            os.chmod(y, 0o644)
            olc("baslangicta izin yok (deneme kurulumu)",
                not os.access(y, os.X_OK))
            ok, ileti = sitl.izin_onar(y)
            olc("izin_onar() basarili dondu", ok, ileti)
            olc("dosya artik calistirilabilir", os.access(y, os.X_OK))
            olc("onarim bildirildi (sessiz degil)", bool(ileti), "ileti bos")
            kip = stat.S_IMODE(os.stat(y).st_mode)
            olc("izin biti gercekten eklendi (0o111)", kip & 0o111 == 0o111,
                oct(kip))
            # Ikinci cagri: zaten izinliyken sessiz olmali
            ok2, ileti2 = sitl.izin_onar(y)
            olc("izinli dosyada ikinci cagri sessiz", ok2 and not ileti2,
                repr(ileti2))
            # Klasor bazli onarim
            y2 = sahte_ikili(gec, "arduplane", kaynak=y)
            os.chmod(y2, 0o600)
            eski = sitl.SITL_KLASORU
            sitl.SITL_KLASORU = gec
            try:
                onarilan, basarisiz = sitl.izin_onar_klasor()
            finally:
                sitl.SITL_KLASORU = eski
            olc("izin_onar_klasor() ikiliyi onardi", onarilan >= 1,
                "onarilan=%d" % onarilan)
            olc("izin_onar_klasor() basarisiz birakmadi", not basarisiz,
                basarisiz)
            olc("klasor onarimindan sonra calistirilabilir",
                os.access(y2, os.X_OK))
            # DLL dosyalarina +x verilmemeli (Linux'ta anlamsiz)
            dll = sahte_ikili(gec, "cygwin1.dll", icerik=b"MZ" + b"\0" * 100)
            os.chmod(dll, 0o644)
            eski = sitl.SITL_KLASORU
            sitl.SITL_KLASORU = gec
            try:
                sitl.izin_onar_klasor()
            finally:
                sitl.SITL_KLASORU = eski
            olc("DLL dosyasina gereksiz +x verilmedi",
                not os.access(dll, os.X_OK))
        finally:
            shutil.rmtree(gec, ignore_errors=True)

    # ------------------------------------------------------------------
    bolum("4. BICIM DENETIMI (Errno 8 kusuru)")
    gec = tempfile.mkdtemp(prefix="sinav2446_bicim_")
    try:
        # a) HTML hata sayfasi olarak inmis dosya
        y = sahte_ikili(gec, "arducopter",
                        icerik=b"<!DOCTYPE html><html>404</html>\n")
        uygun, neden = sitl.bicim_denetle(y)
        olc("HTML olarak inmis dosya reddedildi", not uygun)
        olc("red gerekcesi bozulmayi/boyutu soyluyor",
            any(k in (neden or "").lower()
                for k in ("bozuk", "bayt", "metin")), neden)

        # b) git-lfs isaretcisi
        y = sahte_ikili(
            gec, "arducopter",
            icerik=b"version https://git-lfs.github.com/spec/v1\n"
                   b"oid sha256:deadbeef\nsize 7230968\n")
        uygun, _ = sitl.bicim_denetle(y)
        olc("git-lfs isaretcisi reddedildi", not uygun)

        # c) Yarim inmis gercek ELF (dogru sihirli sayi, kucuk boyut)
        if os.path.isfile(gercek_kopter):
            with open(gercek_kopter, "rb") as f:
                bas = f.read(4096)
            y = sahte_ikili(gec, "arducopter", icerik=bas)
            uygun, neden = sitl.bicim_denetle(y)
            olc("yarim inmis ELF reddedildi (sihirli sayi dogru olsa da)",
                not uygun, neden)

        # d) Bicim okuma dogrulugu
        b = sitl.ikili_bicimi(
            sahte_ikili(gec, "pe_ornek",
                        icerik=b"MZ" + b"\0" * 200))
        olc("PE sihirli sayisi taniniyor", b.get("bicim") == "pe")
        b = sitl.ikili_bicimi(
            sahte_ikili(gec, "macho_ornek",
                        icerik=b"\xcf\xfa\xed\xfe" + b"\0" * 200))
        olc("Mach-O sihirli sayisi taniniyor", b.get("bicim") == "macho")
        b = sitl.ikili_bicimi(
            sahte_ikili(gec, "betik_ornek",
                        icerik=b"#!/bin/sh\necho x\n"))
        olc("betik dosyasi taniniyor", b.get("bicim") == "betik")
        b = sitl.ikili_bicimi(os.path.join(gec, "yok_boyle_dosya"))
        olc("okunamayan dosya bildiriliyor", b.get("bicim") == "okunamadi")

        # e) ELF basligi cozumleme: e_machine dogru okunuyor mu
        elf = bytearray(64)
        elf[0:4] = b"\x7fELF"
        elf[4] = 2          # 64-bit
        elf[5] = 1          # LSB
        elf[18:20] = (0xb7).to_bytes(2, "little")   # AArch64
        b = sitl.ikili_bicimi(sahte_ikili(gec, "aarch64_ornek",
                                          icerik=bytes(elf)))
        olc("ELF e_machine dogru okundu (AArch64)", b.get("makine") == 0xb7,
            b.get("makine_ad"))
        olc("ELF bit genisligi okundu", b.get("bit") == 64)
    finally:
        shutil.rmtree(gec, ignore_errors=True)

    # ------------------------------------------------------------------
    bolum("5. MIMARI UYUSMAZLIGI")
    benim = (platform.machine() or "").lower()
    if windows:
        print("  Windows tek mimari desteklidir; bolum atlandi.")
    elif benim not in sitl.MAKINE_UYUM:
        print("  Bu makine (%s) uyum tablosunda yok; bilincli olarak "
              "engellenmiyor." % benim)
    else:
        gec = tempfile.mkdtemp(prefix="sinav2446_mim_")
        try:
            # Bu makineye UYMAYAN bir mimari sec
            kabul = sitl.MAKINE_UYUM[benim]
            yabanci = next(m for m in (0x3e, 0xb7, 0x28, 0x03)
                           if m not in kabul)
            elf = bytearray(2 * 1024 * 1024)   # boyut denetimini gecsin
            elf[0:4] = b"\x7fELF"
            elf[4] = 2
            elf[5] = 1
            elf[18:20] = yabanci.to_bytes(2, "little")
            y = sahte_ikili(gec, "arducopter", icerik=bytes(elf))
            uygun, neden = sitl.bicim_denetle(y)
            olc("yabanci mimari ikilisi reddedildi", not uygun)
            olc("red gerekcesi hem dosyanin hem makinenin mimarisini yaziyor",
                (not uygun) and benim in (neden or "").lower()
                and "mimari" in (neden or "").lower(), neden)
            # Kendi mimarimize uyan ikili kabul edilmeli
            elf[18:20] = sorted(kabul)[0].to_bytes(2, "little")
            y2 = sahte_ikili(gec, "arduplane", icerik=bytes(elf))
            uygun2, neden2 = sitl.bicim_denetle(y2)
            olc("kendi mimarisine uyan ikili kabul edildi", uygun2, neden2)
        finally:
            shutil.rmtree(gec, ignore_errors=True)

    # ------------------------------------------------------------------
    bolum("6. ACILIS HAZIRLIK DENETIMI (hazir_mi)")
    hazir, eksik, ayrinti = sitl.hazir_mi()
    olc("gercek kurulumda hazir_mi() True", hazir, ayrinti)
    olc("hazir_mi() eksik listesi bos", not eksik, eksik)
    olc("hazir_mi() ayrinti metni klasoru bildiriyor",
        bool(ayrinti) and sitl.SITL_KLASORU in str(ayrinti), ayrinti)

    # Bozuk kurulumda False donmeli — v2.4.45'te bu ADIM YOKTU ve
    # acilista "SITL hazir" yazip kullaniciyi yanlis bilgilendiriyordu.
    gec = tempfile.mkdtemp(prefix="sinav2446_hazir_")
    try:
        os.makedirs(os.path.join(gec, "sitl"), exist_ok=True)
        for ad in (("ArduCopter.elf", "ArduPlane.elf") if windows
                   else ("arducopter", "arduplane")):
            sahte_ikili(os.path.join(gec, "sitl"), ad,
                        icerik=b"<html>404</html>")
        eski = sitl.SITL_KLASORU
        sitl.SITL_KLASORU = os.path.join(gec, "sitl")
        try:
            h2, e2, a2 = sitl.hazir_mi()
        finally:
            sitl.SITL_KLASORU = eski
        olc("bozuk kurulumda hazir_mi() False", h2 is False, a2)
        olc("bozuk kurulumda gerekce anlasilir",
            bool(a2) and len(str(a2)) > 40, a2)
    finally:
        shutil.rmtree(gec, ignore_errors=True)

    # ------------------------------------------------------------------
    bolum("7. GERCEK SUREC CALISTIRMA")
    if os.path.isfile(gercek_kopter) and not windows:
        try:
            s = subprocess.run([gercek_kopter, "--help"],
                               capture_output=True, timeout=30)
            cikti = (s.stdout or b"").decode("utf-8", "replace")
            olc("gercek SITL ikilisi calisti (cikis kodu 0)",
                s.returncode == 0, "cikis=%d" % s.returncode)
            olc("cikti SITL argumanlarini iceriyor",
                "--model" in cikti and "--home" in cikti)
        except Exception as e:
            olc("gercek SITL ikilisi calisti", False, e)
    else:
        print("  Bu ortamda gercek calistirma denemesi atlandi.")

    # ------------------------------------------------------------------
    bolum("8. TANILAMA ARACI")
    tani = os.path.join(KOK, "sitl_tani.py")
    if not os.path.isfile(tani):
        tani = os.path.join(os.path.dirname(KOK), "sitl_tani.py")
    olc("sitl_tani.py paketle geliyor", os.path.isfile(tani), tani)
    if os.path.isfile(tani):
        try:
            s = subprocess.run([sys.executable, tani], capture_output=True,
                               timeout=180, cwd=os.path.dirname(tani))
            cikti = (s.stdout or b"").decode("utf-8", "replace")
            olc("tanilama araci sonuna kadar kostu", "OZET" in cikti)
            olc("tanilama araci saglam kurulumda KALDI vermedi",
                "KALDI: 0" in cikti,
                [x for x in cikti.splitlines() if "KALDI]" in x][:3])
        except Exception as e:
            olc("tanilama araci kostu", False, e)

    # ------------------------------------------------------------------
    print()
    print("=" * 66)
    print("SONUC: %d GECTI / %d KALDI" % (GECTI, KALDI))
    if BASARISIZLAR:
        print("Basarisiz olcumler:")
        for b in BASARISIZLAR:
            print("  - %s" % b)
    print("=" * 66)
    return 0 if KALDI == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
