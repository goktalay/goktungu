#!/usr/bin/env python3
"""v2.4.45 SITL hazirlik ve DLL denetimi sinavi.

Windows'a ozgu kod yolunu Linux'ta sinamak icin `platform.system()`
yamalanir. Bu mesru bir olcum yontemidir: denetlenen mantik dosya
sisteminde DLL arama mantigidir, isletim sistemi cagrisi degil.
"""
import os
import shutil
import sys
import tempfile

KOK = os.path.dirname(os.path.abspath(__file__))
for aday in (os.path.join(KOK, "goktungu"), KOK, "/tmp/k1/hedef"):
    if os.path.isdir(os.path.join(aday, "goktungu")):
        sys.path.insert(0, aday)
        break

from goktungu import sitl  # noqa: E402

GECTI = 0
KALDI = 0


def olc(ad, kosul, ayrinti=""):
    global GECTI, KALDI
    if kosul:
        GECTI += 1
        print(f"  [GECTI] {ad}")
    else:
        KALDI += 1
        print(f"  [KALDI] {ad}" + (f" -> {ad and ayrinti}" if ayrinti else ""))


class WindowsTaklit:
    """platform.system() -> 'Windows' yapar."""

    def __enter__(self):
        self._eski = sitl.platform.system
        sitl.platform.system = lambda: "Windows"
        return self

    def __exit__(self, *a):
        sitl.platform.system = self._eski


def main():
    print("=" * 68)
    print("v2.4.45 SITL HAZIRLIK / DLL SINAVI")
    print("=" * 68)

    # ---- 1) Gercek kurulumda hazir mi ----
    print("\n[1] Kurulu SITL klasoru")
    hazir, eksik, ayrinti = sitl.hazir_mi()
    olc("hazir_mi() True donuyor", hazir, ayrinti)
    olc("eksik listesi bos", eksik == [], str(eksik))
    olc("ArduCopter.elf var (windows ikilisi pakette)",
        os.path.isfile(os.path.join(sitl.SITL_KLASORU, "ArduCopter.elf")))
    olc("ArduPlane.elf var",
        os.path.isfile(os.path.join(sitl.SITL_KLASORU, "ArduPlane.elf")))
    olc("linux arducopter var ve calistirilabilir",
        os.access(os.path.join(sitl.SITL_KLASORU, "arducopter"), os.X_OK))
    olc("linux arduplane var ve calistirilabilir",
        os.access(os.path.join(sitl.SITL_KLASORU, "arduplane"), os.X_OK))

    # ---- 2) Zorunlu DLL listesi olculmus listeyle ayni ----
    print("\n[2] Zorunlu DLL listesi (PE import tablosundan olculdu)")
    beklenen = {"cygwin1.dll", "cyggcc_s-seh-1.dll", "cygstdc++-6.dll",
                "cygiconv-2.dll", "cygintl-8.dll"}
    olc("WINDOWS_DLL_ZORUNLU olculmus liste ile birebir",
        set(sitl.WINDOWS_DLL_ZORUNLU) == beklenen,
        str(set(sitl.WINDOWS_DLL_ZORUNLU) ^ beklenen))
    for d in sorted(beklenen):
        olc(f"{d} sitl/ icinde mevcut",
            os.path.isfile(os.path.join(sitl.SITL_KLASORU, d)))

    # ---- 3) DLL denetimi: tam klasor ----
    print("\n[3] dll_denetle - tam klasor (Windows taklidi)")
    with WindowsTaklit():
        yol = os.path.join(sitl.SITL_KLASORU, "ArduCopter.elf")
        ez, ee = sitl.dll_denetle(yol)
        olc("eksik zorunlu DLL yok", ez == [], str(ez))
        olc("eksik ek DLL yok", ee == [], str(ee))

    # ---- 4) DLL denetimi: eksik klasor ----
    print("\n[4] dll_denetle - eksik klasor")
    gecici = tempfile.mkdtemp(prefix="sitl_eksik_")
    try:
        shutil.copy(os.path.join(sitl.SITL_KLASORU, "ArduCopter.elf"),
                    os.path.join(gecici, "ArduCopter.elf"))
        # yalniz cygwin1.dll konur, digerleri eksik
        shutil.copy(os.path.join(sitl.SITL_KLASORU, "cygwin1.dll"),
                    os.path.join(gecici, "cygwin1.dll"))
        with WindowsTaklit():
            ez, ee = sitl.dll_denetle(os.path.join(gecici, "ArduCopter.elf"))
            olc("eksik zorunlu DLL tespit edildi", len(ez) == 4, str(ez))
            olc("cygwin1.dll eksik sayilmadi", "cygwin1.dll" not in ez)
            olc("cygstdc++-6.dll eksik olarak bildirildi",
                "cygstdc++-6.dll" in ez)
    finally:
        shutil.rmtree(gecici, ignore_errors=True)

    # ---- 5) Cikis kodu aciklamalari ----
    print("\n[5] Windows cikis kodu tanilamasi")
    a1 = sitl.cikis_kodu_acikla(3221225781)
    olc("3221225781 -> 0xC0000135 aciklamasi",
        a1 and "0xC0000135" in a1, str(a1))
    a2 = sitl.cikis_kodu_acikla(-1073741515)
    olc("imzali bicim (-1073741515) de eslesiyor",
        a2 and "0xC0000135" in a2, str(a2))
    # v2.4.48 DUZELTMESI: bu madde v2.4.45'te YANLIS yazilmisti ve kod
    # dogrulandiginda sinav kaliyordu. Gercek degerler:
    #   0xC000007B = 3221225595 (STATUS_INVALID_IMAGE_FORMAT)
    #   0xC0000139 = 3221225785 (STATUS_ENTRYPOINT_NOT_FOUND)
    # Onceki tabloda 3221225595 "Bozuk DLL (0xC0000139)" olarak
    # etiketliydi; mimarisi uymayan ikili calistirildiginda kullaniciya
    # "karisik DLL surumleri" denip yanlis yone gonderiliyordu.
    a3 = sitl.cikis_kodu_acikla(3221225595)
    olc("3221225595 -> 0xC000007B (uyumsuz ikili bicimi)",
        a3 and "0xC000007B" in a3, str(a3))
    a3b = sitl.cikis_kodu_acikla(3221225785)
    olc("3221225785 -> 0xC0000139 (bozuk DLL)",
        a3b and "0xC0000139" in a3b, str(a3b))
    a3c = sitl.cikis_kodu_acikla(-1073741701)
    olc("imzali -1073741701 -> 0xC000007B",
        a3c and "0xC000007B" in a3c, str(a3c))
    a4 = sitl.cikis_kodu_acikla(1)
    olc("cikis kodu 1 -> port cakismasi aciklamasi",
        a4 and "port" in a4.lower(), str(a4))
    olc("bilinmeyen kod None dondurur",
        sitl.cikis_kodu_acikla(0) is None)
    olc("gecersiz girdi None dondurur",
        sitl.cikis_kodu_acikla("abc") is None)

    # ---- 6) baslat() DLL eksikken surec BASLATMAZ ----
    print("\n[6] baslat() eksik DLL ile surec baslatmiyor")
    gecici2 = tempfile.mkdtemp(prefix="sitl_bos_")
    try:
        shutil.copy(os.path.join(sitl.SITL_KLASORU, "ArduCopter.elf"),
                    os.path.join(gecici2, "ArduCopter.elf"))
        satirlar = []

        def konsol(etiket, mesaj, seviye="bilgi"):
            satirlar.append((etiket, mesaj, seviye))

        class AyarTaklit:
            def yukle(self):
                return {"sitl_yolu": gecici2}

        y = sitl.SitlYoneticisi(konsol, AyarTaklit())
        with WindowsTaklit():
            port, hata = y.baslat(9901, "multirotor", 39.9, 32.8, 5900)
        olc("port None (baslatilmadi)", port is None, str(port))
        olc("hata metni 'Cygwin' iceriyor",
            hata and "Cygwin" in hata, str(hata))
        olc("hata metni eksik DLL adini veriyor",
            hata and "cygstdc++-6.dll" in hata, str(hata))
        olc("hata metni klasor yolunu veriyor",
            hata and gecici2 in hata, str(hata))
        olc("surec sozlugu bos kaldi", not y.calisiyor_mu(9901))
    finally:
        shutil.rmtree(gecici2, ignore_errors=True)

    # ---- 7) hazir_mi eksik kurulumda False ----
    print("\n[7] hazir_mi() eksik kurulumda False")
    eski_kok = sitl.SITL_KLASORU
    gecici3 = tempfile.mkdtemp(prefix="sitl_yok_")
    try:
        sitl.SITL_KLASORU = gecici3
        hazir2, eksik2, ayr2 = sitl.hazir_mi()
        olc("hazir_mi() False", hazir2 is False, str(hazir2))
        olc("eksik listesi dolu", len(eksik2) >= 2, str(eksik2))
        olc("ayrinti beklenen klasoru yaziyor", gecici3 in ayr2, ayr2)
    finally:
        sitl.SITL_KLASORU = eski_kok
        shutil.rmtree(gecici3, ignore_errors=True)

    print("\n" + "=" * 68)
    print(f"SONUC: {GECTI} gecti, {KALDI} kaldi")
    print("=" * 68)
    return 0 if KALDI == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
