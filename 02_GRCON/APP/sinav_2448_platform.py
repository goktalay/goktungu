#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GOKTUNGU v2.4.48 - ISLETIM SISTEMI + MIMARI MATRIS SINAVI

Amac: sanal dron (SITL) desteginin Windows ve Linux'un yaygin
mimarilerinde calistigini, calismayacagi bilesimlerde ise SESSIZ
gecmedigini olcmek.

Neden bu sinav var:
  v2.4.45 -> Windows'ta 0xC0000135 (eksik DLL)
  v2.4.46 -> Linux'ta Errno 13 (izin), ardindan Errno 8 (bicim)
  v2.4.47 -> aarch64'te mimari uyusmazligi
Her seferinde kusur BASKA bir hucrede cikti. Tek tek duzeltmek yerine
matrisin TAMAMI olculur; boylece bir sonraki hucre kullanicinin
makinesinde degil burada gorunur.

Olcum ilkesi: platform.system/platform.machine yamalanarak her hucre
taklit edilir. Bu, gercek makine olmadan da mantigi olcmenin tek yolu.
Gercek CALISTIRMA dogrulamasi ayrica yapilir (Linux'ta dogal, Windows
icin wine ile Cloud Computer uzerinde).

Kullanim: kurulum kokunde `python3 sinav_2448_platform.py`
"""

from __future__ import annotations

import os
import platform
import shutil
import struct
import sys

KOK = os.path.dirname(os.path.abspath(__file__))
if KOK not in sys.path:
    sys.path.insert(0, KOK)

GECICI = os.path.join("/tmp", "sinav2448")

_gecti = 0
_kaldi = 0
_kaldi_liste: list[str] = []


def olc(ad, kosul, ayrinti=""):
    global _gecti, _kaldi
    if kosul:
        _gecti += 1
        print("  [OK]   %s" % ad)
    else:
        _kaldi += 1
        _kaldi_liste.append(ad + ((" - " + ayrinti) if ayrinti else ""))
        print("  [KALDI] %s%s" % (ad, (" - " + ayrinti) if ayrinti else ""))


def pe_uret(yol, makine, boyut=8 * 1024 * 1024):
    """Verilen COFF Machine degeriyle en kucuk gecerli PE dosyasi uretir.

    Gercek PE degil; yalnizca bicim/mimari okuyucusunu olcmek icin
    yeterli baslik tasir. Boyut, "cok kucuk dosya bozuktur" denetimini
    tetiklememesi icin 8 MB.
    """
    d = bytearray(boyut)
    d[0:2] = b"MZ"
    lfa = 0x80
    struct.pack_into("<I", d, 0x3C, lfa)
    d[lfa:lfa + 4] = b"PE\0\0"
    struct.pack_into("<H", d, lfa + 4, makine)
    with open(yol, "wb") as f:
        f.write(bytes(d))


def elf_uret(yol, makine, bit=2, boyut=8 * 1024 * 1024):
    """Verilen e_machine degeriyle en kucuk gecerli ELF dosyasi uretir."""
    d = bytearray(boyut)
    d[0:4] = b"\x7fELF"
    d[4] = bit          # EI_CLASS: 1=32, 2=64
    d[5] = 1            # EI_DATA: little endian
    struct.pack_into("<H", d, 18, makine)
    with open(yol, "wb") as f:
        f.write(bytes(d))


class Taklit:
    """platform.system/machine gecici olarak degistirir."""

    def __init__(self, sistem, makine):
        self.sistem = sistem
        self.makine = makine

    def __enter__(self):
        self._s = platform.system
        self._m = platform.machine
        platform.system = lambda: self.sistem
        platform.machine = lambda: self.makine
        return self

    def __exit__(self, *a):
        platform.system = self._s
        platform.machine = self._m
        return False


def main():
    print("=" * 70)
    print("GOKTUNGU v2.4.48 - ISLETIM SISTEMI + MIMARI MATRIS SINAVI")
    print("=" * 70)
    print("Kok: %s" % KOK)
    print("Bu makine: %s / %s" % (platform.system(), platform.machine()))
    print()

    try:
        from goktungu import sitl
    except Exception as e:
        print("SITL modulu ice alinamadi: %s" % e)
        return 1

    shutil.rmtree(GECICI, ignore_errors=True)
    os.makedirs(GECICI, exist_ok=True)

    # ------------------------------------------------------------------
    print("--- 1) SABIT TABLOLAR ---")
    # ------------------------------------------------------------------
    olc("PE_MAKINE tablosu var", hasattr(sitl, "PE_MAKINE"))
    olc("PE_UYUM tablosu var", hasattr(sitl, "PE_UYUM"))
    pm = getattr(sitl, "PE_MAKINE", {})
    olc("PE x64 (0x8664) taniniyor", 0x8664 in pm)
    olc("PE ARM64 (0xAA64) taniniyor", 0xAA64 in pm)
    olc("PE x86 (0x014c) taniniyor", 0x014C in pm)
    olc("PE ARM32 (0x01c4) taniniyor", 0x01C4 in pm)

    pu = getattr(sitl, "PE_UYUM", {})
    olc("amd64 x64 PE kabul eder", 0x8664 in pu.get("amd64", set()))
    olc("amd64 ARM64 PE KABUL ETMEZ", 0xAA64 not in pu.get("amd64", set()),
        "x64 Windows ARM64 ikilisini calistiramaz")
    olc("arm64 x64 PE kabul eder (emulasyon)",
        0x8664 in pu.get("arm64", set()))
    olc("arm64 ARM64 PE kabul eder", 0xAA64 in pu.get("arm64", set()))

    mu = getattr(sitl, "MAKINE_UYUM", {})
    olc("ELF x86_64 -> 0x3e", 0x3E in mu.get("x86_64", set()))
    olc("ELF aarch64 -> 0xb7", 0xB7 in mu.get("aarch64", set()))
    olc("ELF aarch64 ARM32 (0x28) de kabul",
        0x28 in mu.get("aarch64", set()))
    olc("ELF x86_64 aarch64 KABUL ETMEZ",
        0xB7 not in mu.get("x86_64", set()))

    olc("WINDOWS_DLL_KULLANILMAZ kategorisi var",
        hasattr(sitl, "WINDOWS_DLL_KULLANILMAZ"))
    olc("Zorunlu DLL sayisi 5", len(sitl.WINDOWS_DLL_ZORUNLU) == 5,
        str(len(sitl.WINDOWS_DLL_ZORUNLU)))
    for d in ("cygwin1.dll", "cyggcc_s-seh-1.dll", "cygstdc++-6.dll",
              "cygiconv-2.dll", "cygintl-8.dll"):
        olc("Zorunlu DLL listesinde: %s" % d,
            d in sitl.WINDOWS_DLL_ZORUNLU)
    for d in ("cygatomic-1.dll", "cyggomp-1.dll", "cygquadmath-0.dll"):
        olc("Kullanilmaz kategoride: %s" % d,
            d in getattr(sitl, "WINDOWS_DLL_KULLANILMAZ", ()))

    # ------------------------------------------------------------------
    print()
    print("--- 2) CIKIS KODU ESLEMESI ---")
    # ------------------------------------------------------------------
    wc = getattr(sitl, "WINDOWS_CIKIS_KODU", {})
    olc("0xC0000135 (3221225781) eslendi", 3221225781 in wc)
    olc("0xC0000135 imzali (-1073741515) eslendi", -1073741515 in wc)
    olc("0xC0000139 (3221225785) DOGRU deger eslendi", 3221225785 in wc,
        "onceki surumde 3221225595 yaziliydi, o aslinda 0xC000007B")
    olc("0xC000007B (3221225595) eslendi", 3221225595 in wc)
    a135 = sitl.cikis_kodu_acikla(3221225781) or ""
    a07b = sitl.cikis_kodu_acikla(3221225595) or ""
    olc("0xC0000135 aciklamasi 'DLL' diyor", "DLL" in a135)
    olc("0xC000007B aciklamasi mimari/bicim diyor",
        ("mimari" in a07b.lower()) or ("bicim" in a07b.lower()),
        a07b[:60])
    olc("0xC0000135 ve 0xC000007B AYRI aciklamalar",
        a135 != a07b)

    # ------------------------------------------------------------------
    print()
    print("--- 3) PE MIMARI OKUMA ---")
    # ------------------------------------------------------------------
    pe_uret(os.path.join(GECICI, "x64.elf"), 0x8664)
    pe_uret(os.path.join(GECICI, "arm64.elf"), 0xAA64)
    pe_uret(os.path.join(GECICI, "x86.elf"), 0x014C)

    b = sitl.ikili_bicimi(os.path.join(GECICI, "x64.elf"))
    olc("PE bicimi taniniyor", b.get("bicim") == "pe")
    olc("PE makine alani okunuyor (x64)", b.get("makine") == 0x8664,
        str(b.get("makine")))
    olc("PE makine adi cozuluyor", b.get("makine_ad") == "Windows x64",
        str(b.get("makine_ad")))
    olc("PE bit sayisi 64", b.get("bit") == 64)

    b = sitl.ikili_bicimi(os.path.join(GECICI, "arm64.elf"))
    olc("PE ARM64 makine okunuyor", b.get("makine") == 0xAA64)
    b = sitl.ikili_bicimi(os.path.join(GECICI, "x86.elf"))
    olc("PE x86 bit sayisi 32", b.get("bit") == 32)

    # ------------------------------------------------------------------
    print()
    print("--- 4) WINDOWS MIMARI UYUM MATRISI ---")
    # ------------------------------------------------------------------
    matris = [
        ("AMD64", "x64.elf", True, "x64 ikili x64 Windows"),
        ("AMD64", "arm64.elf", False, "ARM64 ikili x64 Windows -> RED"),
        ("AMD64", "x86.elf", True, "32-bit ikili x64 Windows (WOW64)"),
        ("ARM64", "x64.elf", True, "x64 ikili ARM64 Windows (emulasyon)"),
        ("ARM64", "arm64.elf", True, "ARM64 ikili ARM64 Windows"),
        ("ARM64", "x86.elf", True, "32-bit ikili ARM64 Windows"),
    ]
    for mak, dosya, beklenen, aciklama in matris:
        with Taklit("Windows", mak):
            uygun, ileti = sitl.bicim_denetle(os.path.join(GECICI, dosya))
        olc("Windows %s + %s -> %s (%s)"
            % (mak, dosya, "KABUL" if beklenen else "RED", aciklama),
            uygun == beklenen, (ileti or "")[:70])

    # Ret iletisinin YOL GOSTERDIGINI olc: yalnizca "uygun degil" demek
    # kullaniciyi bosluga birakir.
    with Taklit("Windows", "AMD64"):
        _u, ileti = sitl.bicim_denetle(os.path.join(GECICI, "arm64.elf"))
    ileti = ileti or ""
    olc("RED iletisi dosya mimarisini yaziyor", "ARM64" in ileti)
    olc("RED iletisi makine mimarisini yaziyor", "amd64" in ileti.lower())
    olc("RED iletisi 0xC000007B kodunu veriyor", "C000007B" in ileti.upper())
    olc("RED iletisi cozum yolu soyluyor",
        ("goktungu-sitl" in ileti) or ("arsiv" in ileti.lower()))

    # ------------------------------------------------------------------
    print()
    print("--- 5) LINUX MIMARI UYUM MATRISI ---")
    # ------------------------------------------------------------------
    elf_uret(os.path.join(GECICI, "x86_64.bin"), 0x3E)
    elf_uret(os.path.join(GECICI, "aarch64.bin"), 0xB7)
    elf_uret(os.path.join(GECICI, "arm32.bin"), 0x28, bit=1)

    lmatris = [
        ("x86_64", "x86_64.bin", True, "x86-64 ikili x86-64 Linux"),
        ("x86_64", "aarch64.bin", False, "aarch64 ikili x86-64 Linux -> RED"),
        ("aarch64", "aarch64.bin", True, "aarch64 ikili aarch64 Linux"),
        ("aarch64", "x86_64.bin", False, "x86-64 ikili aarch64 Linux -> RED"),
        ("aarch64", "arm32.bin", True, "ARM32 ikili aarch64 Linux"),
    ]
    for mak, dosya, beklenen, aciklama in lmatris:
        with Taklit("Linux", mak):
            uygun, ileti = sitl.bicim_denetle(os.path.join(GECICI, dosya))
        olc("Linux %s + %s -> %s (%s)"
            % (mak, dosya, "KABUL" if beklenen else "RED", aciklama),
            uygun == beklenen, (ileti or "")[:70])

    # Isletim sistemi carprazi: PE dosyasi Linux'ta, ELF dosyasi Windows'ta
    with Taklit("Linux", "x86_64"):
        u1, i1 = sitl.bicim_denetle(os.path.join(GECICI, "x64.elf"))
    olc("Linux'ta PE dosyasi REDDEDILIR", not u1)
    olc("PE-Linux iletisi '.elf uzantili ama PE' aciklamasi yapiyor",
        "PE" in (i1 or "") and "Linux" in (i1 or ""))
    with Taklit("Windows", "AMD64"):
        u2, i2 = sitl.bicim_denetle(os.path.join(GECICI, "x86_64.bin"))
    olc("Windows'ta ELF dosyasi REDDEDILIR", not u2)

    # ------------------------------------------------------------------
    print()
    print("--- 6) IKILI ADAY SIRASI (mimariye duyarli) ---")
    # ------------------------------------------------------------------
    with Taklit("Linux", "aarch64"):
        ad = sitl.ikili_adaylari("arducopter")
    olc("aarch64'te _aarch64 sonekli aday ILK",
        bool(ad) and ad[0].endswith("arducopter_aarch64"),
        str(ad[:2]))
    olc("aarch64'te soneksiz ad da aday", any(
        a.endswith("/arducopter") for a in ad))
    with Taklit("Linux", "x86_64"):
        ad = sitl.ikili_adaylari("arducopter")
    olc("x86_64'te soneksiz ad ILK",
        bool(ad) and ad[0].endswith("/arducopter"), str(ad[:2]))
    olc("x86_64'te _aarch64 adayi YOK",
        not any("_aarch64" in a for a in ad))
    with Taklit("Windows", "AMD64"):
        ad = sitl.ikili_adaylari("arducopter")
    olc("Windows'ta ArduCopter.elf ILK",
        bool(ad) and ad[0].endswith("ArduCopter.elf"), str(ad[:1]))
    with Taklit("Windows", "ARM64"):
        ad = sitl.ikili_adaylari("arduplane")
    olc("Windows ARM64'te de ArduPlane.elf (emulasyon)",
        bool(ad) and ad[0].endswith("ArduPlane.elf"), str(ad[:1]))

    # ------------------------------------------------------------------
    print()
    print("--- 7) DLL EKSIK / MIMARI DENETIMI ---")
    # ------------------------------------------------------------------
    olc("dll_mimari_denetle islevi var",
        hasattr(sitl, "dll_mimari_denetle"))

    da = os.path.join(GECICI, "dllA")
    os.makedirs(da, exist_ok=True)
    pe_uret(os.path.join(da, "ArduCopter.elf"), 0x8664)
    for d in sitl.WINDOWS_DLL_ZORUNLU:
        pe_uret(os.path.join(da, d), 0x8664, 200000)
    with Taklit("Windows", "AMD64"):
        ez, ee = sitl.dll_denetle(os.path.join(da, "ArduCopter.elf"))
        uy = sitl.dll_mimari_denetle(os.path.join(da, "ArduCopter.elf"))
    olc("Tam kurulumda eksik zorunlu DLL yok", ez == [], str(ez))
    olc("Tam kurulumda mimari uyusmazligi yok", uy == [], str(uy))
    olc("Kullanilmaz DLL'ler EKSIK diye raporlanmiyor", ee == [], str(ee))

    db = os.path.join(GECICI, "dllB")
    os.makedirs(db, exist_ok=True)
    pe_uret(os.path.join(db, "ArduCopter.elf"), 0x8664)
    for i, d in enumerate(sitl.WINDOWS_DLL_ZORUNLU):
        pe_uret(os.path.join(db, d), 0x014C if i == 2 else 0x8664, 200000)
    with Taklit("Windows", "AMD64"):
        uy = sitl.dll_mimari_denetle(os.path.join(db, "ArduCopter.elf"))
    olc("32-bit DLL 64-bit ikiliyle uyusmaz olarak yakalaniyor",
        len(uy) == 1, str(uy))
    olc("Uyusmaz kaydi dosya adini veriyor",
        bool(uy) and uy[0][0] == sitl.WINDOWS_DLL_ZORUNLU[2], str(uy))
    olc("Uyusmaz kaydi iki mimariyi de veriyor",
        bool(uy) and "32-bit" in uy[0][1] and "x64" in uy[0][2], str(uy))

    dc = os.path.join(GECICI, "dllC")
    os.makedirs(dc, exist_ok=True)
    pe_uret(os.path.join(dc, "ArduCopter.elf"), 0x8664)
    for d in sitl.WINDOWS_DLL_ZORUNLU[:3]:
        pe_uret(os.path.join(dc, d), 0x8664, 200000)
    with Taklit("Windows", "AMD64"):
        ez, _ee = sitl.dll_denetle(os.path.join(dc, "ArduCopter.elf"))
    olc("Eksik zorunlu DLL'ler saptaniyor", len(ez) == 2, str(ez))
    olc("Linux'ta DLL denetimi calismaz (bos doner)",
        sitl.dll_denetle(os.path.join(dc, "ArduCopter.elf")) == ([], []))
    olc("Linux'ta DLL mimari denetimi bos doner",
        sitl.dll_mimari_denetle(os.path.join(dc, "ArduCopter.elf")) == [])

    # ------------------------------------------------------------------
    print()
    print("--- 8) PAKETE GOMULU DOSYALARIN GERCEK KAPSAMI ---")
    # ------------------------------------------------------------------
    sk = sitl.SITL_KLASORU
    olc("sitl klasoru var", os.path.isdir(sk), sk)

    beklenen_dosyalar = {
        "arducopter": ("elf", 0x3E, "Linux x86-64 multirotor"),
        "arduplane": ("elf", 0x3E, "Linux x86-64 sabit kanat"),
        "arducopter_aarch64": ("elf", 0xB7, "Linux ARM64 multirotor"),
        "arduplane_aarch64": ("elf", 0xB7, "Linux ARM64 sabit kanat"),
        "ArduCopter.elf": ("pe", 0x8664, "Windows x64 multirotor"),
        "ArduPlane.elf": ("pe", 0x8664, "Windows x64 sabit kanat"),
    }
    for ad, (bek_bicim, bek_mak, aciklama) in beklenen_dosyalar.items():
        y = os.path.join(sk, ad)
        varmi = os.path.isfile(y)
        olc("Gomulu: %s (%s)" % (ad, aciklama), varmi)
        if not varmi:
            continue
        b = sitl.ikili_bicimi(y)
        olc("  %s bicimi %s" % (ad, bek_bicim),
            b.get("bicim") == bek_bicim, str(b.get("bicim")))
        olc("  %s mimarisi dogru" % ad, b.get("makine") == bek_mak,
            "%s beklenen %s" % (b.get("makine"), hex(bek_mak)))
        olc("  %s boyutu makul (>1 MB)" % ad,
            os.path.getsize(y) > 1024 * 1024,
            str(os.path.getsize(y)))

    for d in sitl.WINDOWS_DLL_ZORUNLU:
        y = os.path.join(sk, d)
        olc("Gomulu zorunlu DLL: %s" % d, os.path.isfile(y))
        if os.path.isfile(y):
            b = sitl.ikili_bicimi(y)
            olc("  %s x64 (ikiliyle ayni mimari)" % d,
                b.get("makine") == 0x8664, str(b.get("makine_ad")))

    # ------------------------------------------------------------------
    print()
    print("--- 9) GERCEK CALISTIRMA (bu makinede dogal olarak) ---")
    # ------------------------------------------------------------------
    import subprocess
    benim = (platform.machine() or "").lower()
    sonek = sitl.MIMARI_SONEK.get(benim, "")
    dogal = os.path.join(sk, "arducopter" + sonek)
    if os.path.isfile(dogal):
        uygun, _n = sitl.bicim_denetle(dogal)
        olc("Bu makinenin dogal ikilisi bicim denetimini geciyor", uygun)
        ok, _i = sitl.izin_onar(dogal)
        olc("Bu makinenin dogal ikilisi calistirilabilir izinde", ok)
        try:
            p = subprocess.run([dogal, "--help"], capture_output=True,
                               timeout=30)
            cikti = (p.stdout or b"") + (p.stderr or b"")
            olc("Dogal ikili GERCEKTEN calisiyor (--help)",
                p.returncode != 126 and len(cikti) > 0,
                "kod=%s cikti=%d bayt" % (p.returncode, len(cikti)))
            olc("Cikti ArduPilot SITL'e ait gorunuyor",
                any(k in cikti.lower() for k in
                    (b"sitl", b"ardupilot", b"wipe", b"model", b"speedup")),
                cikti[:80].decode("utf-8", "replace"))
        except Exception as e:
            olc("Dogal ikili GERCEKTEN calisiyor (--help)", False, str(e))
    else:
        olc("Bu makine icin dogal ikili pakette var", False, dogal)

    # Ters yon: bu makinede calismayacak ikili GERCEKTEN reddediliyor mu
    ters = ("arducopter" if sonek else "arducopter_aarch64")
    ty = os.path.join(sk, ters)
    if os.path.isfile(ty) and ters != ("arducopter" + sonek):
        uygun, ileti = sitl.bicim_denetle(ty)
        olc("Bu makineye UYMAYAN ikili reddediliyor (%s)" % ters,
            not uygun, (ileti or "")[:70])
        olc("Ret iletisi cozum yolu iceriyor",
            bool(ileti) and ("goktungu-sitl" in ileti or
                             "sitl_tani" in ileti or
                             "firmware" in ileti))

    # Windows ikilisi bu Linux makinesinde reddedilmeli
    wy = os.path.join(sk, "ArduCopter.elf")
    if os.path.isfile(wy) and not sitl._windows_mu():
        uygun, ileti = sitl.bicim_denetle(wy)
        olc("Windows .elf dosyasi Linux'ta reddediliyor", not uygun)
        olc("Ileti '.elf ama PE' yanilgisini aciklıyor",
            "PE" in (ileti or ""))

    # ------------------------------------------------------------------
    print()
    print("--- 10) TANILAMA ARACI ---")
    # ------------------------------------------------------------------
    tani = os.path.join(KOK, "sitl_tani.py")
    olc("sitl_tani.py kurulum kokunde", os.path.isfile(tani))
    if os.path.isfile(tani):
        icerik = open(tani, encoding="utf-8", errors="replace").read()
        olc("Tanilama isletim sistemini raporluyor",
            "platform.system" in icerik)
        olc("Tanilama mimariyi raporluyor", "platform.machine" in icerik)
        olc("Tanilama PE mimarisini de okuyor",
            "PE_MAKINE" in icerik or "0x8664" in icerik)
        olc("Tanilama kullanilmaz DLL kategorisini biliyor",
            "KULLANILMAZ" in icerik)

    # ------------------------------------------------------------------
    print()
    print("=" * 70)
    print("SONUC: %d gecti / %d kaldi" % (_gecti, _kaldi))
    if _kaldi_liste:
        print()
        print("KALAN MADDELER:")
        for k in _kaldi_liste:
            print("  - %s" % k)
    print("=" * 70)
    shutil.rmtree(GECICI, ignore_errors=True)
    return 0 if _kaldi == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
