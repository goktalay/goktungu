#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MERKEZ UYGULAMA — gomulu Windows Python calisma zamanini hazirlar.

NE ISE YARAR
    Merkez Uygulama (5.000 $ tek seferlik) satin alan sirket, Windows
    makinesine Python KURMAK ZORUNDA KALMADAN yazilimi kurabilsin.
    Python 3.11.9 gomulu dagitimi + tum zorunlu tekerlekler kurulum
    paketinin icine girer.

KOPRUNUN `gomulu_hazirla.py` DOSYASINDAN FARKLARI (hepsi OLCULDU)

  1. `psycopg2-binary` EKLENDI  ← EN KRITIK
     `goktungu/veritabani.py:121` KIP = "postgresql" ve `goktungu/pg.py:44`
     dogrudan `import psycopg2` yapar. Paket yoksa `pg.VAR = False`
     olur ve VERITABANI HIC ACILMAZ.

     Bu bagimlilik `requirements.txt`'te de EKSIKTI (v2.4.65'te
     eklendi). Gelistirme makinelerinde elle kurulu oldugu icin
     gorulmemis; temiz makinede yazilim acilmiyordu. Merkez Uygulama
     tam olarak "temiz makinede kurulum" senaryosudur.

  2. `pymavlink` EKLENDI
     Kopru MAVLink'i ayristirmaz, yalniz baytlari aktarir. Merkez
     Uygulama dronu KENDISI yonetir; `pymavlink` olmadan hicbir dron
     baglantisi kurulamaz.

  3. `cv2/data` AYIKLANMAZ  ← koprude ayiklaniyor
     Koprude `CascadeClassifier` hic kullanilmiyor. Merkez Uygulamada
     `ai_sunucu.py:492` plaka tespiti icin KULLANIR.

     Olculen durum: `ai_modeller/` icinde yalniz iki ONNX var; plaka
     cascade dosyasi (`haarcascade_russian_plate_number.xml`) YOK ve
     `MODEL_KAYNAKLARI` otomatik indirme sozlugunde de listelenmemis.
     Kod bu durumda kontur yontemine duser ve `plaka=YOK` yazar
     (sessiz degil, ama yetenek dusuk).

     Kullanici KAPALI DEVRE calisma istedi; internetten indirme bir
     cozum degil. Bu yuzden cascade wheel icinden alinip
     `ai_modeller/` altina KOPYALANIR.

  4. `numpy/f2py` ve test dizinleri AYIKLANIR
     Kodda hic gecmedigi dogrulandi (grep: sifir sonuc).

KULLANIM
    python3 gomulu_merkez_hazirla.py

    Uretilen agac: gomulu_merkez/calisma/
    `paketle_merkez.py --windows` bunu setup icine gomer.
"""
from __future__ import annotations

import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

KOK = Path(__file__).resolve().parent
GOMULU = KOK / "gomulu_merkez"
CALISMA = GOMULU / "calisma"

PY_SURUM = "3.11.9"
PY_ZIP = f"python-{PY_SURUM}-embed-amd64.zip"
PY_URL = f"https://www.python.org/ftp/python/{PY_SURUM}/{PY_ZIP}"

# Boyutlar GERCEKTEN indirilerek olculdu (bkz. OLCUM_MERKEZ_BAGIMLILIK.md).
# Kullanici boyut kisiti olmadigini acikca belirtti: "boyut önemli değil".
TEKERLEKLER = [
    ("websockets", "12.0",
     "websockets-12.0-cp311-cp311-win_amd64.whl"),                  # 0,1 MB
    ("pyserial", "3.5",
     "pyserial-3.5-py2.py3-none-any.whl"),                          # 0,1 MB
    ("pywin32", "306",
     "pywin32-306-cp311-cp311-win_amd64.whl"),                      # 8,8 MB
    # PostgreSQL surucusu — MERKEZ ICIN ZORUNLU (kopruda yok)
    ("psycopg2-binary", "2.9.9",
     "psycopg2_binary-2.9.9-cp311-cp311-win_amd64.whl"),            # 1,1 MB
    # MAVLink ayristirma — MERKEZ ICIN ZORUNLU (kopruda yok)
    ("pymavlink", "2.4.41",
     "pymavlink-2.4.41-py3-none-any.whl"),                          # 11,1 MB
    ("numpy", "1.26.4",
     "numpy-1.26.4-cp311-cp311-win_amd64.whl"),                     # 15,1 MB
    ("opencv-python-headless", "4.10.0.84",
     "opencv_python_headless-4.10.0.84-cp37-abi3-win_amd64.whl"),   # 37,0 MB
]

# Kodda KULLANILMADIGI dogrulanan agir bilesenler.
#
# DIKKAT: buraya bir sey eklemeden once kodda gecmedigi grep ile
# DOGRULANMALIDIR. Eksik bilesen sahada `ImportError` olarak cikar ve
# teshisi zordur. `cv2/data` bilincli olarak BURADA YOK (yukaridaki
# 3. maddeye bakin).
AYIKLANACAK = [
    "pythonwin",          # pywin32 GUI IDE; servis pencere acmaz (~9 MB)
    "PyWin32.chm",        # yardim dosyasi (~3 MB)
    "adodbapi",           # pywin32 veritabani eklentisi; kullanilmiyor
    "isapi",              # pywin32 IIS eklentisi; kullanilmiyor
    "numpy/f2py",         # Fortran arayuz ureteci; grep: sifir sonuc
    "numpy/tests",
    "numpy/core/tests",
    "numpy/typing/tests",
    "numpy/testing/tests",
    "numpy/random/tests",
    "numpy/polynomial/tests",
    "numpy/ma/tests",
    "numpy/lib/tests",
    "numpy/linalg/tests",
    "numpy/fft/tests",
    "numpy/distutils/tests",
]

# Plaka tespiti icin gereken cascade; OpenCV wheel'inin icinde gelir.
PLAKA_CASCADE = "haarcascade_russian_plate_number.xml"


def yaz(m: str) -> None:
    print(m, flush=True)


def indir(url: str, hedef: Path) -> None:
    if hedef.exists() and hedef.stat().st_size > 0:
        yaz(f"  [atlandi] {hedef.name} (zaten var)")
        return
    yaz(f"  [indiriliyor] {url}")
    hedef.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=300) as y:
        veri = y.read()
    hedef.write_bytes(veri)
    yaz(f"  [tamam] {hedef.name} ({len(veri) // 1024} KB)")


def pypi_url(ad: str, surum: str, dosya: str) -> str:
    api = f"https://pypi.org/pypi/{ad}/{surum}/json"
    with urllib.request.urlopen(api, timeout=120) as y:
        veri = json.load(y)
    for k in veri.get("urls", []):
        if k.get("filename") == dosya:
            return str(k["url"])
    mevcut = [k.get("filename") for k in veri.get("urls", [])]
    raise SystemExit(f"{ad} {surum}: {dosya} bulunamadi. Mevcut: {mevcut}")


def python_ac() -> None:
    """Gomulu Python'u calisma dizinine acar ve `._pth`'i duzenler."""
    zip_yolu = GOMULU / PY_ZIP
    indir(PY_URL, zip_yolu)

    if CALISMA.exists():
        shutil.rmtree(CALISMA)
    CALISMA.mkdir(parents=True)

    with zipfile.ZipFile(zip_yolu) as z:
        z.extractall(CALISMA)
    yaz(f"  [tamam] gomulu python acildi: {CALISMA}")

    # KRITIK: `._pth` varsa CPython "isolated" kipe gecer; PYTHONPATH ve
    # calisma dizini YOK SAYILIR. sys.path yalniz `._pth` icerigidir.
    #
    # MERKEZ UYGULAMA DIZIN DUZENI (koprudEN FARKLI!):
    #   ...\Goktungu\Merkez\                    <- kurulum koku (main.py)
    #   ...\Goktungu\Merkez\assets\python\      <- `goktungu` paketi BURADA
    #   ...\Goktungu\Merkez\python\             <- `._pth` burada
    #
    # Yani `goktungu` paketi iki ust dizinin altindaki `assets\python`
    # icindedir. Koprude paket dogrudan kurulum kokundeydi ve `..`
    # yetiyordu; burada `..\assets\python` de gerekir. Yazilmazsa:
    #   ModuleNotFoundError: No module named 'goktungu'
    pth = CALISMA / "python311._pth"
    if not pth.exists():
        raise SystemExit(
            "python311._pth bulunamadi - gomulu dagitim beklenmeyen bicimde")

    satirlar = pth.read_text(encoding="utf-8").splitlines()
    yeni: list[str] = []
    for s in satirlar:
        if s.strip() in ("#import site", "# import site"):
            continue
        yeni.append(s)

    mevcut = [s.strip() for s in yeni]
    nokta = next((i for i, s in enumerate(yeni) if s.strip() == "."), -1)
    ekle_sonra = nokta if nokta >= 0 else len(yeni) - 1

    # Kurulum koku (main.py) ve `goktungu` paketinin dizini.
    for yol in ("..", "..\\assets\\python"):
        if yol not in mevcut:
            ekle_sonra += 1
            yeni.insert(ekle_sonra, yol)

    if "Lib\\site-packages" not in mevcut:
        yeni.append("Lib\\site-packages")
    if "import site" not in mevcut:
        yeni.append("import site")

    pth.write_text("\n".join(yeni) + "\n", encoding="utf-8")
    yaz(f"  [tamam] {pth.name} duzenlendi")
    yaz("           icerik: " + " | ".join(y for y in yeni if y.strip()))


def tekerlekler_ac() -> None:
    sp = CALISMA / "Lib" / "site-packages"
    sp.mkdir(parents=True, exist_ok=True)
    for ad, surum, dosya in TEKERLEKLER:
        whl = GOMULU / "teker" / dosya
        if not whl.exists():
            indir(pypi_url(ad, surum, dosya), whl)
        with zipfile.ZipFile(whl) as z:
            z.extractall(sp)
        yaz(f"  [tamam] {ad} {surum} -> site-packages")


def plaka_cascade_kopyala() -> bool:
    """OpenCV wheel'indeki plaka cascade'ini `ai_modeller/` altina kopyalar.

    NEDEN: `ai_sunucu.py:492` bu dosyayi `ai_modeller/` altinda arar,
    ama depoda YOKTUR ve `MODEL_KAYNAKLARI` otomatik indirme sozlugunde
    de listelenmemistir. Kullanici KAPALI DEVRE calisma istedigi icin
    internetten indirmek cozum degil. Dosya OpenCV wheel'inin icinde
    zaten geliyor; kopyalamak bedava.
    """
    kaynak = CALISMA / "Lib" / "site-packages" / "cv2" / "data" / PLAKA_CASCADE
    if not kaynak.exists():
        yaz(f"  [UYARI] {PLAKA_CASCADE} wheel icinde bulunamadi; "
            f"plaka tespiti kontur yontemine dusecek")
        return False
    hedef_dizin = KOK / "ai_modeller"
    hedef_dizin.mkdir(parents=True, exist_ok=True)
    hedef = hedef_dizin / PLAKA_CASCADE
    shutil.copy2(kaynak, hedef)
    yaz(f"  [tamam] {PLAKA_CASCADE} -> ai_modeller/ "
        f"({hedef.stat().st_size // 1024} KB)")
    return True


def ayikla() -> None:
    sp = CALISMA / "Lib" / "site-packages"
    toplam = 0
    for gol in AYIKLANACAK:
        hedef = sp / gol
        if not hedef.exists():
            continue
        if hedef.is_dir():
            boyut = sum(f.stat().st_size
                        for f in hedef.rglob("*") if f.is_file())
            shutil.rmtree(hedef)
        else:
            boyut = hedef.stat().st_size
            hedef.unlink()
        toplam += boyut
        yaz(f"  [ayiklandi] {gol} ({boyut // (1024 * 1024)} MB)")
    yaz(f"  [tamam] toplam {toplam // (1024 * 1024)} MB geri kazanildi")


def _boyut(yol: Path) -> int:
    return sum(f.stat().st_size for f in yol.rglob("*") if f.is_file())


def sinav() -> int:
    """Uretilen calisma zamanini denetler."""
    gecti = 0
    kaldi = 0

    def dene(ad: str, kosul: bool, ayrinti: str = "") -> None:
        nonlocal gecti, kaldi
        if kosul:
            gecti += 1
            yaz(f"  [GECTI] {ad}")
        else:
            kaldi += 1
            yaz(f"  [KALDI] {ad} {ayrinti}")

    dene("python.exe var", (CALISMA / "python.exe").exists())
    dene("python311.dll var", (CALISMA / "python311.dll").exists())
    dene("python311.zip var", (CALISMA / "python311.zip").exists())
    dene("_socket.pyd var", (CALISMA / "_socket.pyd").exists())
    dene("_ssl.pyd var", (CALISMA / "_ssl.pyd").exists())

    pth = CALISMA / "python311._pth"
    icerik = pth.read_text(encoding="utf-8") if pth.exists() else ""
    satir = [s.strip() for s in icerik.splitlines()]
    dene("._pth: import site etkin", "import site" in icerik)
    dene("._pth: site-packages yolu", "Lib\\site-packages" in icerik)
    dene("._pth: kurulum koku (..)", ".." in satir,
         "- main.py yanindaki moduller bulunamaz!")
    # MERKEZ ICIN KRITIK: `goktungu` paketi `assets\python` altindadir.
    dene("._pth: assets\\python yolu", "..\\assets\\python" in satir,
         "- 'goktungu' paketi ice alinamaz, yazilim HIC acilmaz!")

    sp = CALISMA / "Lib" / "site-packages"
    dene("websockets acildi", (sp / "websockets" / "__init__.py").exists())
    dene("serial acildi", (sp / "serial" / "__init__.py").exists())
    dene("numpy acildi", (sp / "numpy" / "__init__.py").exists())
    dene("cv2 acildi", (sp / "cv2" / "__init__.py").exists())

    # MERKEZ ICIN ZORUNLU IKI PAKET
    dene("psycopg2 acildi", (sp / "psycopg2" / "__init__.py").exists(),
         "- PostgreSQL acilamaz, yazilim HIC calismaz!")
    dene("pymavlink acildi", (sp / "pymavlink" / "__init__.py").exists(),
         "- hicbir dron baglantisi kurulamaz!")

    # psycopg2 kendi libpq DLL'ini tasir; ayiklanmamalidir.
    dene("psycopg2 DLL'leri var",
         any((sp / "psycopg2").glob("*.pyd"))
         or any((sp / "psycopg2_binary.libs").glob("*.dll"))
         if (sp / "psycopg2").exists() else False,
         "- PostgreSQL baglantisi kurulamaz!")

    dene("win32serviceutil acildi",
         (sp / "win32" / "lib" / "win32serviceutil.py").exists())
    dene("win32service.pyd acildi",
         (sp / "win32" / "win32service.pyd").exists())
    dene("pywin32 DLL'leri acildi",
         (sp / "pywin32_system32" / "pywintypes311.dll").exists()
         and (sp / "pywin32_system32" / "pythoncom311.dll").exists())
    dene("pywin32.pth var", (sp / "pywin32.pth").exists())

    dene("opencv ffmpeg DLL var",
         any(sp.glob("cv2/opencv_videoio_ffmpeg*.dll")),
         "- OpenCV ile RTSP/MJPEG acilamaz!")
    # Koprude ayiklanir, MERKEZDE AYIKLANMAZ: plaka tespiti kullanir.
    dene("cv2/data KORUNDU (plaka tespiti)",
         (sp / "cv2" / "data" / PLAKA_CASCADE).exists(),
         "- plaka tespiti kontur yontemine duser!")
    dene("plaka cascade ai_modeller'e kopyalandi",
         (KOK / "ai_modeller" / PLAKA_CASCADE).exists(),
         "- kapali devre kurulumda plaka tespiti calismaz!")

    dene("ayiklama yapildi (pythonwin yok)",
         not (sp / "pythonwin").exists())

    yaz("")
    yaz(f"  SONUC: {gecti} gecti, {kaldi} kaldi")
    return kaldi


def main() -> None:
    yaz("=" * 66)
    yaz(" MERKEZ UYGULAMA — gomulu Windows Python calisma zamani")
    yaz("=" * 66)

    yaz("\n--- 1. Gomulu Python ---")
    python_ac()

    yaz("\n--- 2. Tekerlekler ---")
    tekerlekler_ac()

    yaz("\n--- 3. Plaka cascade (kapali devre icin) ---")
    plaka_cascade_kopyala()

    yaz("\n--- 4. Kullanilmayan bilesenleri ayikla ---")
    ayikla()

    yaz("\n--- 5. Sinav ---")
    kaldi = sinav()

    yaz("")
    yaz(f"  Calisma zamani boyutu: {_boyut(CALISMA) / (1024 * 1024):.1f} MB")
    yaz(f"  Dizin: {CALISMA}")
    yaz("=" * 66)

    if kaldi:
        raise SystemExit(f"{kaldi} olcum kaldi — calisma zamani KULLANILMAZ")


if __name__ == "__main__":
    sys.exit(main() or 0)
