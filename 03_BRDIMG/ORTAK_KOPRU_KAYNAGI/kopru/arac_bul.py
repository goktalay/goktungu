"""Dis araclari (ffmpeg) ve opsiyonel paketleri (OpenCV) BULUR.

## NEDEN BU MODUL VAR

Kullanici Windows'ta ffmpeg'i kurmus olmasina ragmen kopru paneli
"ffmpeg BULUNAMADI" yaziyordu. Sebep bir kurulum eksigi DEGIL, arama
yonteminin dar olmasiydi:

`shutil.which("ffmpeg")` YALNIZCA `PATH` ortam degiskenine bakar.
Kopru Windows'ta **servis** olarak, `LocalSystem` hesabiyla kosar.
Servis surecinin PATH'i, oturum acmis kullanicinin PATH'i DEGILDIR:

  * `winget install Gyan.FFmpeg` araci **kullanici profiline** kurar
    (`%LOCALAPPDATA%\\Microsoft\\WinGet\\Links`). Bu dizin kullanicinin
    PATH'ine eklenir, `LocalSystem`'in PATH'ine EKLENMEZ.
  * Kullanici PATH'e elle bir dizin eklediyse, calisan servis surecine
    bu degisiklik YANSIMAZ (surec kendi ortamini baslangicta alir);
    servis yeniden baslatilmadan gorunmez.
  * `choco`/`scoop` gibi araclar da kullanici kapsamina kurabilir.

Ayni sinif sorun OpenCV'de de vardir: kullanici `pip install` dedigi
Python ile servisin kostugu Python AYNI OLMAYABILIR. Windows
kurulumunda servis, paketle gelen gomulu Python'u kullanir; kullanici
ise sistemdeki Python'a kurar. `import cv2` bu yuzden basarisiz olur.

## YAKLASIM

1. Once `PATH` (`shutil.which`) — normal durum, hizli.
2. Sonra platforma ozgu YAYGIN KURULUM KONUMLARI taranir. Bu bir
   "tahmin" degildir; her konum belirli bir kurulum aracinin
   belgelenmis hedefidir (asagidaki tabloya bakin).
3. Bulunan yol **calistirilarak** dogrulanir (`-version`). Var olan
   ama bozuk/eksik bir dosyayi "bulundu" saymak, kullaniciyi yanlis
   yone gonderir; bu daha kotudur.

Bulunan yol onbelleklenir: her akis acilisinda diskte arama yapmak
gereksiz gecikme yaratir.

## OPENCV ICIN AYRIM

OpenCV bir dis PROGRAM degil, Python PAKETIDIR; disk taramasiyla
"bulunup" calistirilamaz. Bu yuzden yalnizca `import` denenir, ancak
basarisizlik nedeni ayirt edilir: paket yok mu, yoksa var ama yuklenemiyor
mu (ornegin eksik DLL). Ikisi farkli cozum gerektirir.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

# Bulunan yollar surec omru boyunca onbelleklenir.
_onbellek: dict = {}


def _windows_mu() -> bool:
    return os.name == "nt" or sys.platform.startswith("win")


def _ffmpeg_adaylari() -> list:
    """ffmpeg icin yaygin kurulum konumlari (platforma gore).

    Her aday, belirli bir kurulum aracinin BELGELENMIS hedefidir:

    | Konum | Kurulum araci |
    |---|---|
    | `%LOCALAPPDATA%\\Microsoft\\WinGet\\Links` | winget (kullanici) |
    | `%LOCALAPPDATA%\\Microsoft\\WinGet\\Packages\\*` | winget (gercek ikili) |
    | `C:\\ProgramData\\chocolatey\\bin` | choco |
    | `%USERPROFILE%\\scoop\\shims` | scoop |
    | `C:\\ffmpeg\\bin` | elle kurulum (yaygin gelenek) |
    | `C:\\Program Files\\ffmpeg\\bin` | elle kurulum |
    | `/usr/bin`, `/usr/local/bin`, `/snap/bin` | apt / kaynak / snap |
    """
    adlar = ["ffmpeg.exe"] if _windows_mu() else ["ffmpeg"]
    dizinler: list = []

    if _windows_mu():
        yerel = os.environ.get("LOCALAPPDATA", "")
        prof = os.environ.get("USERPROFILE", "")
        pfiles = os.environ.get("ProgramFiles", r"C:\Program Files")
        pdata = os.environ.get("ProgramData", r"C:\ProgramData")
        if yerel:
            dizinler.append(os.path.join(
                yerel, "Microsoft", "WinGet", "Links"))
            # winget paket dizinleri: Gyan.FFmpeg_<hash>\ffmpeg-*\bin
            paketler = os.path.join(yerel, "Microsoft", "WinGet", "Packages")
            dizinler.extend(_winget_bin_dizinleri(paketler))
        dizinler.append(os.path.join(pdata, "chocolatey", "bin"))
        if prof:
            dizinler.append(os.path.join(prof, "scoop", "shims"))
        dizinler.append(r"C:\ffmpeg\bin")
        dizinler.append(os.path.join(pfiles, "ffmpeg", "bin"))
        # Kopru kendi dizinine gomulu ffmpeg konabilir (ileride)
        dizinler.append(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "arac"))
    else:
        dizinler.extend(["/usr/bin", "/usr/local/bin", "/snap/bin",
                         "/opt/ffmpeg/bin", "/var/lib/snapd/snap/bin"])

    adaylar = []
    for d in dizinler:
        if not d:
            continue
        for ad in adlar:
            adaylar.append(os.path.join(d, ad))
    return adaylar


def _winget_bin_dizinleri(kok: str) -> list:
    """winget Packages altindaki ffmpeg `bin` dizinlerini bulur.

    winget surumu dizin adina gomer (`ffmpeg-7.1-full_build`), bu
    yuzden sabit yol yazilamaz; bir seviye taranir.
    """
    bulunan: list = []
    try:
        if not os.path.isdir(kok):
            return bulunan
        for ad in os.listdir(kok):
            if "ffmpeg" not in ad.lower():
                continue
            paket = os.path.join(kok, ad)
            try:
                for alt in os.listdir(paket):
                    b = os.path.join(paket, alt, "bin")
                    if os.path.isdir(b):
                        bulunan.append(b)
            except OSError:
                continue
    except OSError:
        pass
    return bulunan


def _calisiyor_mu(yol: str) -> bool:
    """Bulunan ikilinin GERCEKTEN calistigini dogrular.

    Var olan ama bozuk (eksik DLL, yanlis mimari, 0 bayt) bir dosyayi
    "bulundu" saymak kullaniciyi yanlis teshise gonderir.
    """
    try:
        ek = {}
        if _windows_mu():
            # Servis kipinde konsol penceresi acilmasin
            ek["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        c = subprocess.run([yol, "-version"], capture_output=True,
                           timeout=10, **ek)
        return c.returncode == 0 and b"ffmpeg version" in (
            c.stdout or b"") + (c.stderr or b"")
    except (OSError, subprocess.SubprocessError):
        return False


def ffmpeg_yolu(yeniden: bool = False):
    """ffmpeg'in tam yolunu dondurur; bulunamazsa None.

    `yeniden=True` onbellegi atlar (kullanici ffmpeg'i kurduktan sonra
    servisi yeniden baslatmadan "yeniden dene" diyebilsin).
    """
    if not yeniden and "ffmpeg" in _onbellek:
        return _onbellek["ffmpeg"]

    yol = shutil.which("ffmpeg")
    if yol and _calisiyor_mu(yol):
        _onbellek["ffmpeg"] = yol
        return yol

    for aday in _ffmpeg_adaylari():
        if os.path.isfile(aday) and _calisiyor_mu(aday):
            _onbellek["ffmpeg"] = aday
            return aday

    _onbellek["ffmpeg"] = None
    return None


def ffmpeg_komutu() -> str:
    """ffmpeg calistirmak icin kullanilacak komut/yol.

    Bulunamazsa duz `"ffmpeg"` doner: bu durumda `Popen`
    `FileNotFoundError` atar ve cagiran taraf kurulum metnini yazar.
    Sessizce basarisiz olmaktan iyidir.
    """
    return ffmpeg_yolu() or "ffmpeg"


def ffmpeg_surumu() -> str:
    """Kisa surum dizesi (ornegin '7.1'); bulunamazsa bos dize."""
    yol = ffmpeg_yolu()
    if not yol:
        return ""
    try:
        ek = {}
        if _windows_mu():
            ek["creationflags"] = 0x08000000
        c = subprocess.run([yol, "-version"], capture_output=True,
                           timeout=10, **ek)
        ilk = (c.stdout or c.stderr or b"").decode(
            "utf-8", "replace").splitlines()
        if ilk:
            parca = ilk[0].split()
            if len(parca) >= 3:
                return parca[2]
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def opencv_durum() -> dict:
    """OpenCV durumunu AYIRT EDEREK dondurur.

    Doner: {"var": bool, "surum": str, "sebep": str, "python": str}

    `sebep` degerleri:
      * ""              -> sorun yok
      * "paket_yok"     -> hic kurulu degil (pip install gerekir)
      * "yuklenemedi"   -> kurulu ama import patliyor (eksik DLL vb.)

    Bu ayrim onemlidir: ilki icin kurulum, ikincisi icin onarim
    gerekir. Ikisini "OpenCV yok" diye birlestirmek, kullaniciyi
    zaten kurulu olan paketi tekrar kurmaya yonlendirir.
    """
    sonuc = {"var": False, "surum": "", "sebep": "",
             "python": sys.executable or ""}
    try:
        import cv2  # noqa: F401
        sonuc["var"] = True
        sonuc["surum"] = getattr(cv2, "__version__", "")
        return sonuc
    except ModuleNotFoundError:
        sonuc["sebep"] = "paket_yok"
        return sonuc
    except Exception:
        # ImportError (DLL), OSError, hatta bazi surumlerde AttributeError
        sonuc["sebep"] = "yuklenemedi"
        return sonuc


def kurulum_metni(arac: str) -> str:
    """Platforma UYGUN tek satirlik kurulum komutu.

    Onceki surum her iki platformun komutunu birlikte yaziyordu;
    kullanici hangisinin kendisine ait oldugunu ayirmak zorunda
    kaliyordu. Artik yalniz calisan platformun komutu yazilir.
    """
    if arac == "ffmpeg":
        if _windows_mu():
            return ("winget install --scope machine Gyan.FFmpeg")
        return "sudo apt install -y ffmpeg"
    if arac == "opencv":
        if _pip_var_mi():
            yorumlayici = sys.executable or "python3"
            return f'"{yorumlayici}" -m pip install '\
                   "opencv-python-headless numpy"
        # pip YOK: komut vermek yanlis yonlendirme olur.
        return "kopru paketini yeniden kurun (OpenCV pakete gomulu gelir)"
    return ""


def servis_yeniden_baslat_komutu() -> str:
    """Kopru servisini yeniden baslatma komutu (platforma gore)."""
    if _windows_mu():
        return "sc stop GoktunguKopru && sc start GoktunguKopru"
    return "sudo systemctl restart goktungu-kopru"


def kurulum_yonergesi(arac: str) -> list:
    """KOPYALANABILIR, adim adim kurulum yonergesi dondurur.

    ## NEDEN LISTE, NEDEN BU KADAR AYRINTI

    Kullanici hakli bir itirazda bulundu: konumlari taramak tek basina
    yetmez -- "kullanamayacaksa sorun; senin ENV'ine nasil kuracagim,
    konsolda yardim olarak onu yaz".

    Gercekten de bulucu yalnizca ZATEN dogru yere kurulmus bir araci
    bulabilir. Arac hic yoksa ya da yalnizca kullanici profilinde
    varsa, kullanicinin **servisin gordugu yere** kurmasi gerekir.
    Genel "pip install opencv-python" ya da "winget install ffmpeg"
    metni bu durumda ISE YARAMAZ; kullanici komutu calistirir, panel
    yine "BULUNAMADI" der ve teshis dongusu basa doner.

    Bu yuzden yonerge SURECIN KENDI ORTAMINI kullanir:
      * OpenCV icin `sys.executable` -- yani servisin o an kostugu
        Python. Baska bir Python'a kurmak sorunu cozmez.
      * ffmpeg icin makine kapsami (`--scope machine`) ya da
        LocalSystem'in de gordugu sabit bir dizin.
      * Her iki durumda servisin YENIDEN BASLATILMASI gerekir:
        calisan surec ortam degiskenlerini baslangicta alir, sonradan
        yapilan PATH degisikligi o surece YANSIMAZ.
    """
    yeniden = servis_yeniden_baslat_komutu()

    if arac == "ffmpeg":
        if _windows_mu():
            return [
                "ffmpeg'i SERVIS HESABININ gordugu yere kurmalisiniz.",
                "Kopru LocalSystem olarak kosar; winget'in kullanici "
                "profiline kurdugu ffmpeg bu hesapta GORUNMEZ.",
                "",
                "SECENEK 1 - makine kapsaminda kurun (Yonetici "
                "PowerShell):",
                "    winget install --scope machine Gyan.FFmpeg",
                "",
                "SECENEK 2 - elle kopyalayin (en kesin yol):",
                "    1) ffmpeg'i indirin: https://www.gyan.dev/ffmpeg/builds/",
                r"    2) ffmpeg.exe dosyasini C:\ffmpeg\bin altina koyun",
                r"       (tam yol: C:\ffmpeg\bin\ffmpeg.exe)",
                "    3) Kopru bu dizini kendiliginden tarar; PATH "
                "ayarlamaniz GEREKMEZ.",
                "",
                "Ardindan servisi yeniden baslatin (Yonetici):",
                "    " + yeniden,
            ]
        return [
            "ffmpeg'i sistem genelinde kurun:",
            "    " + kurulum_metni("ffmpeg"),
            "",
            "Ardindan servisi yeniden baslatin:",
            "    " + yeniden,
        ]

    if arac == "opencv":
        yorumlayici = sys.executable or "python3"

        # ## EN ONEMLI AYRIM: pip VAR MI?
        #
        # Windows kurulumunda kopru GOMULU Python ile gelir ve gomulu
        # dagitimda pip YOKTUR (ensurepip de yok -- olculdu). Bu
        # ortamda "python.exe -m pip install ..." komutu
        # "No module named pip" ile duser.
        #
        # Kullaniciya CALISMAYAN bir komut vermek, hic komut
        # vermemekten DAHA KOTUDUR: komutu calistirir, hata alir,
        # sorunun kendisinde oldugunu sanir ve teshis dongusu basa
        # doner. Bu yuzden pip yoksa tamamen farkli bir yol anlatilir.
        if not _pip_var_mi():
            return [
                "OpenCV bu kuruluma GOMULU gelir; elle kurulmasi",
                "gerekmez ve gomulu Python'da pip BULUNMADIGI icin",
                "'pip install' komutu CALISMAZ.",
                "",
                "Eksik olmasi, kurulum paketinin eski oldugunu ya da",
                "kurulumun eksik tamamlandigini gosterir.",
                "",
                "COZUM - kopru yazilimini yeniden kurun:",
                "    1) Merkez indirme sayfasindan son surumu indirin",
                "       https://goktungu.com/#istemciler",
                "    2) Kurulumu calistirin (mevcut kurulumun uzerine",
                "       kurulabilir; ayarlariniz korunur)",
                "",
                "Bu arada AG kameralari (RTSP/MJPEG/HTTP) normal",
                "calismaya devam eder; yalnizca USB kamera ve AI kutu",
                "cizimi devre disidir.",
                "",
                "Servisin Python yolu (destek icin):",
                "    " + yorumlayici,
            ]

        # pip VAR (Ubuntu .deb kurulumu ya da elle calistirma):
        # dogru Python'a kurulmasi kritiktir.
        satirlar = [
            "OpenCV, SERVISIN KULLANDIGI Python'a kurulmalidir.",
            "Baska bir Python'a kurmak sorunu COZMEZ.",
            "",
            "Servisin Python yolu:",
            "    " + yorumlayici,
            "",
            "Kurulum komutu (bu tam yolu kullanin):",
            "    " + kurulum_metni("opencv"),
        ]
        if not _windows_mu():
            # Ubuntu'da servis 'goktungu-kopru' kullanicisiyla kosar;
            # kullanicinin kendi ev dizinine kurmasi ise yaramaz.
            satirlar += [
                "",
                "NOT: sudo ile kurun; servis kendi kullanicisiyla",
                "(goktungu-kopru) kosar ve sizin ev dizininizdeki",
                "paketleri GORMEZ:",
                "    sudo " + kurulum_metni("opencv"),
            ]
        satirlar += [
            "",
            "Ardindan servisi yeniden baslatin:",
            "    " + yeniden,
        ]
        return satirlar

    return []


def eksik_arac_ozeti(arac: str) -> str:
    """Tek satirlik ozet (istemciye/hata alanina yazilmak icin).

    Panel konsolu cok satirli yonergeyi `kurulum_yonergesi()` ile
    yazar; bu fonksiyon ise hata alani gibi TEK SATIR bekleyen yerler
    icindir. Ikisi ayni bilgiyi tasir, bicimi farklidir.
    """
    if arac == "ffmpeg":
        if _windows_mu() and _servis_kipi_mi():
            return ("ffmpeg bulunamadi: kopru servis hesabi (LocalSystem) "
                    "gormuyor. Cozum: 'winget install --scope machine "
                    r"Gyan.FFmpeg' veya ffmpeg.exe'yi C:\ffmpeg\bin "
                    "altina koyup servisi yeniden baslatin.")
        return "ffmpeg kurulu degil - kurulum: " + kurulum_metni("ffmpeg")
    if arac == "opencv":
        d = opencv_durum()
        if d["sebep"] == "yuklenemedi":
            return ("OpenCV kurulu ama yuklenemiyor (eksik sistem "
                    "kutuphanesi olabilir). Python: " + d["python"])
        if not _pip_var_mi():
            return ("OpenCV eksik - bu kuruluma gomulu gelmeliydi. "
                    "Kopru yazilimini merkez indirme sayfasindan "
                    "yeniden kurun (gomulu Python'da pip yoktur, "
                    "'pip install' CALISMAZ).")
        return ("OpenCV kurulu degil - servisin Python'una kurun: "
                + kurulum_metni("opencv"))
    return ""


def _pip_var_mi() -> bool:
    """Surecin Python'unda pip KULLANILABILIR mi.

    Windows kurulumundaki gomulu Python dagitiminda pip yoktur
    (`ensurepip` de yok). Bu durumda kullaniciya `pip install`
    yonergesi vermek yanlis yonlendirmedir; farkli bir cozum
    anlatilmalidir.

    Ice alma denemesi yapilir, `pip --version` KOSULMAZ: alt surec
    baslatmak yavastir ve bu bilgi her uyari yazimda gerekir.
    """
    if "pip" in _onbellek:
        return bool(_onbellek["pip"])
    try:
        import importlib.util
        var = importlib.util.find_spec("pip") is not None
    except Exception:
        var = False
    _onbellek["pip"] = var
    return var


def tani() -> dict:
    """Panel/merkez icin tam tani bilgisi."""
    y = ffmpeg_yolu()
    ocv = opencv_durum()
    return {
        "ffmpeg": bool(y),
        "ffmpeg_yolu": y or "",
        "ffmpeg_surum": ffmpeg_surumu(),
        "opencv": ocv["var"],
        "opencv_surum": ocv["surum"],
        "opencv_sebep": ocv["sebep"],
        "python": sys.executable or "",
        "servis_kipi": _servis_kipi_mi(),
        "pip": _pip_var_mi(),
    }


def _servis_kipi_mi() -> bool:
    """Surec bir Windows servisi olarak mi kosuyor (tahmini).

    Kesin tespit SCM sorgusu gerektirir; burada PATH'te kullanici
    profili dizinlerinin BULUNMAMASI gostergesi kullanilir. Yalnizca
    tani metnini zenginlestirmek icindir, mantik buna dayanmaz.
    """
    if not _windows_mu():
        return False
    prof = (os.environ.get("USERPROFILE") or "").lower()
    yol = (os.environ.get("PATH") or "").lower()
    if not prof:
        return True
    return prof not in yol
