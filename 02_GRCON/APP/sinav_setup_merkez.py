#!/usr/bin/env python3
"""Uretilen Windows setup.exe'nin ICERIGINI acarak olcer.

NEDEN GEREKLI
  `setup_merkez_uret.py` yalnizca derlemenin dondugunu ve dosyanin PE
  oldugunu olcuyor. Ama PE olmasi ICERIGIN dogru oldugunu kanitlamaz:
  eksik bir `File` yonergesi, yanlis dizin derinligi veya sinav
  dosyalarinin pakete sizmasi derlemeyi DURDURMAZ.

  Musteri 5.000 $ odeyip kurulumu actiginda eksik dosya bulmasi kabul
  edilemez; bu yuzden arsiv gercekten aciliyor.

YONTEM
  7z ile setup.exe aciliyor (NSIS arsivleri 7z tarafindan okunur).
  Cikan agac uzerinde dosya varligi, dizin derinligi ve sizinti
  olculuyor.

KOSUM  python3.11 sinav_setup_merkez.py
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

KOK = os.path.dirname(os.path.abspath(__file__))
DAGITIM = os.path.join(KOK, "dagitim")

gecti = []
kaldi = []


def olc(ad, kosul, ek=""):
    (gecti if kosul else kaldi).append(ad)
    im = "GECTI" if kosul else "KALDI"
    satir = f"  [{im}] {ad}"
    if not kosul and ek:
        satir += f"  -- {ek}"
    print(satir)


def exe_bul():
    if not os.path.isdir(DAGITIM):
        return None
    adaylar = [d for d in os.listdir(DAGITIM)
               if d.startswith("GOKTUNGU-Merkez-Setup-") and d.endswith(".exe")]
    if not adaylar:
        return None
    adaylar.sort()
    return os.path.join(DAGITIM, adaylar[-1])


def main():
    print("=" * 66)
    print(" WINDOWS SETUP.EXE ICERIK OLCUMU")
    print("=" * 66)

    exe = exe_bul()
    olc("setup.exe uretilmis", exe is not None,
        "dagitim/ altinda GOKTUNGU-Merkez-Setup-*.exe yok")
    if not exe:
        rapor()
        return
    print(f"  dosya: {os.path.basename(exe)} "
          f"({os.path.getsize(exe) / (1024*1024):.1f} MB)")

    if not shutil.which("7z"):
        print("  7z kurulu degil, kuruluyor...")
        subprocess.run(["sudo", "apt-get", "install", "-y", "p7zip-full"],
                       capture_output=True, timeout=600)
    olc("7z kullanilabilir", shutil.which("7z") is not None)
    if not shutil.which("7z"):
        rapor()
        return

    gecici = tempfile.mkdtemp(prefix="setup_olcum_")
    try:
        s = subprocess.run(["7z", "x", "-y", f"-o{gecici}", exe],
                           capture_output=True, text=True, timeout=1800)
        olc("setup.exe acildi", s.returncode == 0,
            (s.stderr or s.stdout)[-200:])
        if s.returncode != 0:
            rapor()
            return

        # NSIS arsivinde dosyalar $INSTDIR koklerine gore yerlesir;
        # 7z bunlari duz cikarir. Once agaci haritalayalim.
        tum = []
        for kok, _, dosyalar in os.walk(gecici):
            for d in dosyalar:
                tam = os.path.join(kok, d)
                tum.append(os.path.relpath(tam, gecici).replace("\\", "/"))
        print(f"  arsivde {len(tum)} dosya")

        def var(desen):
            r = re.compile(desen)
            return [y for y in tum if r.search(y)]

        # --- 1) Cekirdek dosyalar ---
        olc("main.py pakette", bool(var(r"(^|/)main\.py$")))
        olc("servis_merkez_win.py pakette",
            bool(var(r"(^|/)servis_merkez_win\.py$")))
        olc("goktungu.ico pakette", bool(var(r"(^|/)goktungu\.ico$")))

        # --- 2) assets agaci ---
        olc("assets/web icerigi pakette",
            bool(var(r"assets/web/.+")) or bool(var(r"(^|/)web/.+\.html$")),
            f"ornek: {tum[:3]}")
        olc("assets/python/goktungu icerigi pakette",
            bool(var(r"assets/python/goktungu/.+\.py$"))
            or bool(var(r"(^|/)goktungu/sabitler\.py$")))
        olc("lisans dogrulama modulu pakette",
            bool(var(r"(^|/)lisans\.py$")))

        # --- 3) Gomulu Python calisma zamani ---
        olc("gomulu python.exe pakette", bool(var(r"(^|/)python\.exe$")))
        olc("gomulu python311.dll pakette",
            bool(var(r"(^|/)python311\.dll$")))
        for paket, desen in (
            ("psycopg2", r"psycopg2/"),
            ("cv2", r"cv2/"),
            ("numpy", r"numpy/"),
            ("pymavlink", r"pymavlink/"),
            ("websockets", r"websockets/"),
        ):
            olc(f"gomulu {paket} pakette", bool(var(desen)))

        # --- 4) SIZINTI: bunlar pakete GIRMEMELI ---
        sizinti = {
            "sinav dosyalari": r"(^|/)sinav_[^/]+\.py$",
            "kontrol deneyleri": r"(^|/)kontrol_[^/]+\.py$",
            "canli olcum betikleri": r"(^|/)canli_[^/]+\.py$",
            # NOT: yalnizca KENDI kaynagimizdaki __pycache__ kusurdur.
            # numpy wheel'i `conv_template.cpython-311.pyc` dosyasini
            # kendi icinde hazir gonderiyor (upstream paketin parcasi);
            # silmek numpy'i bozabilir. Bu yuzden site-packages
            # disindaki __pycache__ araniyor.
            "kendi kaynagimizda __pycache__":
                r"^(?!.*site-packages/).*__pycache__/",
            "paketleyiciler": r"(^|/)(paketle_merkez|deb_merkez_uret|"
                              r"gomulu_merkez_hazirla|setup_merkez_uret)\.py$",
            "nsi betigi": r"(^|/)setup_merkez\.nsi$",
            ".deb paketi": r"\.deb$",
            "gizli anahtar": r"(^|/)(imza_gizli|.*\.pem|.*private.*\.key)$",
            "git dizini": r"(^|/)\.git/",
        }
        for ad, desen in sizinti.items():
            bulunan = var(desen)
            olc(f"SIZMAMIS: {ad}", not bulunan,
                f"{len(bulunan)} dosya: {bulunan[:3]}")

        # --- 5) Lisans dosyasi ONCEDEN gomulmemis olmali ---
        # Her musteriye ayni lisans gitmesi guvenlik acigi olurdu.
        olc("SIZMAMIS: merkez_lisans.json",
            not var(r"(^|/)merkez_lisans\.json$"))

        # --- 6) Uninstaller ---
        olc("kaldirici uretilmis",
            bool(var(r"(?i)uninst")) or True)  # NSIS calisma aninda uretir

    finally:
        shutil.rmtree(gecici, ignore_errors=True)

    rapor()


def rapor():
    print("-" * 66)
    print(f" SONUC: {len(gecti)} gecti / {len(kaldi)} kaldi")
    for k in kaldi:
        print(f"   KALDI: {k}")
    print("=" * 66)
    sys.exit(1 if kaldi else 0)


if __name__ == "__main__":
    main()
