#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""Windows setup icin gomulu Python 3.11 calisma zamani hazirlar.

Setup .exe kullanicidan Python kurmasini istemez; Python yorumlayicisi
ve kopru bagimliliklari (websockets, pyserial) kurulum paketinin
icinde gelir.

Uretilen dizin duzeni (setup icine gomulecek):

  gomulu/calisma/
    python.exe, python311.dll, python311.zip, *.pyd, *.dll
    Lib/site-packages/websockets/...
    Lib/site-packages/serial/...

Calistirma:
  python3.11 gomulu_hazirla.py
"""

from __future__ import annotations

import io
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

KOK = Path(__file__).resolve().parent
GOMULU = KOK / "gomulu"
CALISMA = GOMULU / "calisma"

PY_SURUM = "3.11.9"
PY_ZIP = f"python-{PY_SURUM}-embed-amd64.zip"
PY_URL = f"https://www.python.org/ftp/python/{PY_SURUM}/{PY_ZIP}"

# Kopru calisma zamani bagimliliklari. Windows tekerlekleri (wheel)
# indirilir; bu makinede kurulum yapilmaz, yalnizca acilir.
#
# ## NEDEN OPENCV BURADA (v1.5.5)
#
# Gomulu Python dagitiminda **pip YOKTUR** (ensurepip de yok). Bu yuzden
# kullaniciya "python.exe -m pip install opencv-python" demek ISE
# YARAMAZ; komut "No module named pip" ile duser. Kullaniciya
# uygulanamaz bir yonerge vermek, hic vermemekten daha kotudur --
# teshis dongusu basa doner.
#
# Cozum: OpenCV ve numpy kurulum paketinin ICINDE gelir. Boylece USB
# kamera ve AI kutu cizimi kutudan cikar cikmaz calisir; kullanicinin
# hicbir sey kurmasi gerekmez.
#
# Boyut: opencv-python-headless (~35 MB) + numpy (~15 MB). "headless"
# secildi cunku GUI penceresi ACILMAZ; servis kipinde pencere zaten
# gosterilemez ve tam surum gereksiz Qt bagimliligi getirir.
TEKERLEKLER = [
    ("websockets", "12.0", "websockets-12.0-cp311-cp311-win_amd64.whl"),
    ("pyserial", "3.5", "pyserial-3.5-py2.py3-none-any.whl"),
    # Gercek Windows servisi icin: pywin32
    ("pywin32", "306", "pywin32-306-cp311-cp311-win_amd64.whl"),
    # USB/donanim kamera ve AI kutu cizimi icin (v1.5.5)
    ("numpy", "1.26.4", "numpy-1.26.4-cp311-cp311-win_amd64.whl"),
    ("opencv-python-headless", "4.10.0.84",
     "opencv_python_headless-4.10.0.84-cp37-abi3-win_amd64.whl"),
    # YEREL AI CIKARIMI ICIN (v1.7.20). `ai_sunucu.py` YOLO ONNX
    # modelini varsa onnxruntime ile kosturur, yoksa cv2.dnn (CPU)
    # yoluna duser. "directml" yapisi secildi cunku DX12 destekli TUM
    # GPU'larda (NVIDIA/AMD/Intel) hizlandirma verir ve kullanicidan
    # CUDA kurulumu ISTEMEZ; saha bilgisayarlarinin ekran karti markasi
    # onceden bilinemez.
    #
    # Bu satir SILINMEMELIDIR: paket site-packages'a ELLE kopyalanmisti
    # ve burada kayitli olmasaydi `gomulu_hazirla.py` bir sonraki
    # calistirmada calisma zamanini onnxruntime'siz yeniden uretirdi.
    # Belirti sahada sessiz olurdu: AI calisir ama yalniz CPU'da.
    #
    # Boyut: ~67 MB (DirectML.dll 18 MB + onnxruntime.dll 21 MB +
    # pybind .pyd 26 MB).
    ("onnxruntime-directml", "1.24.4",
     "onnxruntime_directml-1.24.4-cp311-cp311-win_amd64.whl"),
]


def yaz(m: str) -> None:
    print(m, flush=True)


def indir(url: str, hedef: Path) -> None:
    if hedef.exists() and hedef.stat().st_size > 0:
        yaz(f"  [atlandi] {hedef.name} (zaten var)")
        return
    yaz(f"  [indiriliyor] {url}")
    hedef.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=180) as y:
        veri = y.read()
    hedef.write_bytes(veri)
    yaz(f"  [tamam] {hedef.name} ({len(veri) // 1024} KB)")


def python_ac() -> None:
    """Gomulu Python'u calisma dizinine acar."""
    zip_yolu = GOMULU / PY_ZIP
    indir(PY_URL, zip_yolu)

    if CALISMA.exists():
        shutil.rmtree(CALISMA)
    CALISMA.mkdir(parents=True)

    with zipfile.ZipFile(zip_yolu) as z:
        z.extractall(CALISMA)
    yaz(f"  [tamam] gomulu python acildi: {CALISMA}")

    # Gomulu dagitim varsayilan olarak site-packages'i ICE ALMAZ.
    # ._pth dosyasina 'import site' ve Lib/site-packages eklenmeli,
    # aksi halde websockets/serial ice alinamaz.
    #
    # KRITIK (v1.4.2): ._pth dosyasi bulundugunda CPython "isolated"
    # kipe gecer; PYTHONPATH ortam degiskeni ve calisma dizini (cwd)
    # YOK SAYILIR. sys.path yalnizca ._pth iceriginden kurulur.
    # Bu yuzden 'kopru' paketinin bulundugu kurulum koku de ._pth'e
    # yazilmalidir; aksi halde alt servisler
    #   ModuleNotFoundError: No module named 'kopru'
    # ile hemen sonlanir.
    #
    # Kurulum duzeni:
    #   ...\Goktungu\Kopru\           <- kurulum koku (kopru\ paketi burada)
    #   ...\Goktungu\Kopru\python\    <- ._pth burada
    #
    # ._pth icindeki goreli yollar ._pth'in dizinine gore cozulur;
    # '..' bir ust dizin = kurulum koku. Mutlak yol gomulmedigi icin
    # kurulum dizini tasinsa bile dogru calisir.
    pth = CALISMA / "python311._pth"
    if not pth.exists():
        raise SystemExit("python311._pth bulunamadi - gomulu dagitim beklenmeyen bicimde")

    satirlar = pth.read_text(encoding="utf-8").splitlines()
    yeni: list[str] = []
    for s in satirlar:
        # Yorum satirina alinmis 'import site' varsa etkinlestir
        if s.strip() in ("#import site", "# import site"):
            continue
        yeni.append(s)
    # Kurulum koku ('kopru' paketinin ust dizini): '.' satirindan
    # hemen sonra gelmeli ki paket cozumlemesi once burada arasin.
    if ".." not in [s.strip() for s in yeni]:
        nokta = next((i for i, s in enumerate(yeni) if s.strip() == "."), -1)
        if nokta >= 0:
            yeni.insert(nokta + 1, "..")
        else:
            yeni.append("..")
    if "Lib\\site-packages" not in yeni:
        yeni.append("Lib\\site-packages")
    if "import site" not in yeni:
        yeni.append("import site")
    pth.write_text("\n".join(yeni) + "\n", encoding="utf-8")
    yaz(f"  [tamam] {pth.name} duzenlendi: site-packages + kurulum koku etkin")
    yaz("           icerik: " + " | ".join(y for y in yeni if y.strip()))


def tekerlekler_ac() -> None:
    """Windows tekerleklerini site-packages icine acar."""
    sp = CALISMA / "Lib" / "site-packages"
    sp.mkdir(parents=True, exist_ok=True)

    for ad, surum, dosya in TEKERLEKLER:
        whl = GOMULU / "teker" / dosya
        if not whl.exists():
            # PyPI dosya adresini indeks API'sinden coz
            url = pypi_url(ad, surum, dosya)
            indir(url, whl)
        with zipfile.ZipFile(whl) as z:
            z.extractall(sp)
        yaz(f"  [tamam] {ad} {surum} -> site-packages")


# Kopru'nun KULLANMADIGI, ancak tekerleklerle birlikte gelen agir
# bilesenler. Her biri OLCULEREK secildi (bkz. asagidaki gerekce).
#
# ONEMLI: buraya bir sey eklemeden once kodda kullanilmadigi
# DOGRULANMALIDIR. "Gereksiz gorunuyor" yeterli degildir; eksik bir
# bilesen sahada `ImportError` olarak ortaya cikar ve teshisi zordur.
AYIKLANACAK = [
    # pywin32'nin GUI gelistirme ortami (Pythonwin IDE). Kopru servis
    # olarak kosar, pencere acmaz. Olculdu: 9 MB.
    "pythonwin",
    # pywin32 yardim dosyasi (CHM). Olculdu: 3 MB.
    "PyWin32.chm",
    # OpenCV'nin kendi Haar/LBP siniflandirici deposu. Kopru bunu
    # KULLANMAZ -- dogrulandi (v1.7.20'de yeniden olculdu): `cv2.data`
    # kodda hic gecmiyor. Yerel AI iscisi (ai_sunucu.py) plaka
    # tespitinde CascadeClassifier kullanir ama cascade dosyasini
    # `cv2.data`dan DEGIL, kendi `ai_modeller/` klasorunden okur
    # (PLAKA_CASCADE). Olculdu: 10 MB.
    "cv2/data",
    # numpy'nin kendi sinav takimlari ve Fortran arayuz uretici.
    # Calisma zamaninda kullanilmaz. Olculdu: ~15 MB.
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
    "numpy/f2py",
    # pywin32 veritabani/IIS eklentileri; kopru kullanmaz.
    "adodbapi",
    "isapi",
]


def ayikla() -> None:
    """Kullanilmayan agir bilesenleri siler.

    NEDEN: OpenCV + numpy calisma zamanini 40 MB'dan 201 MB'a
    cikardi. Kullanicinin indirdigi setup dosyasi bu kadar buyurse
    her guncelleme sahada gereksiz yuk olur. Ayiklama ~39 MB geri
    kazandirir ve HICBIR yetenegi eksiltmez -- her kalem kodda
    kullanilmadigi dogrulanarak secildi.
    """
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


def pypi_url(ad: str, surum: str, dosya: str) -> str:
    """PyPI JSON API'sinden tekerlek adresini bulur."""
    api = f"https://pypi.org/pypi/{ad}/{surum}/json"
    with urllib.request.urlopen(api, timeout=120) as y:
        import json

        veri = json.load(y)
    for k in veri.get("urls", []):
        if k.get("filename") == dosya:
            return str(k["url"])
    mevcut = [k.get("filename") for k in veri.get("urls", [])]
    raise SystemExit(f"{ad} {surum}: {dosya} bulunamadi. Mevcut: {mevcut}")


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
    dene("._pth: import site etkin", "import site" in icerik)
    dene("._pth: site-packages yolu", "Lib\\site-packages" in icerik)
    # Gomulu Python isolated kipte oldugu icin PYTHONPATH islemiyor;
    # 'kopru' paketi ancak ._pth'teki '..' satiriyla bulunur.
    dene("._pth: kurulum koku (..) var",
         ".." in [s.strip() for s in icerik.splitlines()],
         "- alt servisler 'kopru' paketini bulamaz!")

    sp = CALISMA / "Lib" / "site-packages"
    dene("websockets acildi", (sp / "websockets" / "__init__.py").exists())
    dene("serial acildi", (sp / "serial" / "__init__.py").exists())
    dene("win32serviceutil acildi",
         (sp / "win32" / "lib" / "win32serviceutil.py").exists())
    dene("win32service.pyd acildi",
         (sp / "win32" / "win32service.pyd").exists())
    dene("pywin32 DLL'leri acildi",
         (sp / "pywin32_system32" / "pywintypes311.dll").exists()
         and (sp / "pywin32_system32" / "pythoncom311.dll").exists())
    # Gomulu dagitimda site-packages icindeki .pth dosyalari yalnizca
    # 'import site' etkinse islenir. pywin32.pth, win32 ve win32\lib
    # yollarini ekler ve DLL dizinini kaydeder; olmazsa win32service
    # ice alinamaz.
    dene("pywin32.pth var", (sp / "pywin32.pth").exists())
    dene("pywin32_bootstrap var",
         (sp / "win32" / "lib" / "pywin32_bootstrap.py").exists())

    # v1.5.5: OpenCV ve numpy artik pakete GOMULU gelir. Gomulu
    # Python'da pip olmadigi icin kullanici bunlari sonradan
    # kuramaz; eksik olmalari USB kamera ve AI kutu ciziminin
    # kalici olarak devre disi kalmasi anlamina gelir.
    dene("numpy acildi", (sp / "numpy" / "__init__.py").exists(),
         "- USB kamera ve AI kutu cizimi calismaz!")
    dene("cv2 acildi", (sp / "cv2" / "__init__.py").exists(),
         "- USB kamera ve AI kutu cizimi calismaz!")
    # OpenCV kendi ffmpeg DLL'ini tasir: RTSP/MJPEG akislari harici
    # ffmpeg OLMADAN da acilabilir. Bu dosya ayiklanmamalidir.
    dene("opencv ffmpeg DLL var",
         any(sp.glob("cv2/opencv_videoio_ffmpeg*.dll")),
         "- OpenCV ile RTSP/MJPEG acilamaz!")
    # Ayiklama gercekten yapildi mi (bosa gitmis bir adim sessizce
    # 40 MB fazla tasimaya yol acar).
    dene("ayiklama yapildi (pythonwin yok)",
         not (sp / "pythonwin").exists())
    dene("ayiklama yapildi (cv2/data yok)",
         not (sp / "cv2" / "data").exists())

    boyut = sum(f.stat().st_size for f in CALISMA.rglob("*") if f.is_file())
    yaz(f"\n  calisma zamani boyutu: {boyut // (1024 * 1024)} MB")
    # Sinir 80 -> 190 MB: OpenCV + numpy acilmis halde belirgin yer
    # kaplar. Ayiklama sonrasi GERCEK boyut 175 MB olculdu (ayiklama
    # 26 MB kazandirdi). Sinir 190 MB'a cekildi: olculen degerin
    # uzerinde makul bir pay birakir, ama beklenmedik bir sismeyi
    # (yanlis tekerlek, ayiklamanin sessizce atlanmasi) yakalar.
    dene("boyut makul (< 190 MB)", boyut < 190 * 1024 * 1024,
         f"({boyut // (1024*1024)} MB)")

    yaz(f"\n  SINAV: {gecti} gecti / {kaldi} kaldi")
    return 0 if kaldi == 0 else 1


def main() -> int:
    yaz("== Gomulu Python 3.11 calisma zamani hazirlaniyor ==")
    python_ac()
    yaz("\n== Bagimlilik tekerlekleri aciliyor ==")
    tekerlekler_ac()
    yaz("\n== Kullanilmayan bilesenler ayikliniyor ==")
    ayikla()
    yaz("\n== Sinav ==")
    return sinav()


if __name__ == "__main__":
    sys.exit(main())
