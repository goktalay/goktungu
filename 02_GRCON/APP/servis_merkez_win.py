#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MERKEZ UYGULAMA — Windows servisi (pywin32).

Kullanici istegi (kopru icin soylenmisti, merkez icin de gecerli):
"bildigin kurulum setup programi, exe olarak" + "servis olarak
calismasini istemistim".

## NEDEN main.py'YI ALT SUREC OLARAK YONETIR

Kopru servisi (`goktungu_kopru/servis_win.py`) kendi `Uygulama` ve `Panel`
siniflarini SUREC ICINDE kurar. Merkez Uygulamada bu YAPILAMAZ:

  * `main.py` bir konsol uygulamasidir; sonunda
    `asyncio.run(ws_sunucu.calistir())` ile ana donguyu ELE GECIRIR.
  * Kapanis yolu `signal.SIGTERM/SIGHUP` isleyicilerine baglidir
    (main.py:1012). Windows servisinde bu sinyaller GELMEZ; SCM
    `SvcStop` cagirir.
  * `main.py` icinde 20 saniyeye kadar port yoklamasi, veritabani gocu,
    SITL hazirlik denetimi ve sertifika uretimi vardir. Bunlari servis
    surecine tasimak, SCM'nin 30 saniyelik baslatma penceresini
    doldurma riskini getirir; servis "yanit vermiyor" diye isaretlenir.

Bu yuzden servis `main.py`'yi AYRI BIR SUREC olarak baslatir ve
yasam dongusunu yonetir. Kazanc: `main.py` hic degismez, konsoldan
elle calistirma yolu birebir ayni kalir (teshis kolayligi).

## KAPANIS

Alt surec once nazikce kapatilir (`CTRL_BREAK_EVENT`), boylece
`main.py`'nin kendi temizleme yolu (telemetri tamponunu bosaltma,
veritabani baglantilarini kapatma) CALISIR. Yanit vermezse
`terminate()`, o da olmazsa `kill()` uygulanir.

CTRL_BREAK secildi (CTRL_C degil): `CREATE_NEW_PROCESS_GROUP` ile
baslatilan bir surece CTRL_C_EVENT gonderilemez -- Windows bunu
sessizce yok sayar ve servis kapanmada takilir.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import traceback

KOK = os.path.dirname(os.path.abspath(__file__))

try:
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil
    _PYWIN32 = True
except ImportError:                                   # pragma: no cover
    _PYWIN32 = False

    class _Sahte:
        """pywin32 yoksa modul ice alinabilsin; main() acik hata verir."""

        class ServiceFramework:                       # type: ignore[misc]
            pass

    win32serviceutil = _Sahte()                       # type: ignore[assignment]

SERVIS_ADI = "GoktunguMerkez"
SERVIS_GORUNEN_AD = "GOKTUNGU Merkez Uygulamasi"
SERVIS_ACIKLAMA = (
    "GOKTUNGU yer kontrol istasyonu merkez uygulamasi. Yerel web arayuzunu "
    "ve dron/AI/video islemlerini yurutur. Kapali devre calisabilir."
)

# main.py'nin kapanmasi icin taninan sure.
#
# 25 sn secildi: `main.py` kapanista telemetri tamponunu bosaltir ve
# PostgreSQL baglantilarini kapatir. Windows SCM varsayilan olarak
# 30 sn bekler; 25 sn nazik kapanisa yer birakir, kalan 5 sn zorla
# sonlandirma ve gunluk yazimi icindir.
KAPANIS_SURESI = 25.0


def _veri_dizini() -> str:
    """Gunluk dizini. Servis LocalSystem hesabiyla kosar.

    %APPDATA% System32 altina duser ve kullanici gunlugu goremez;
    ProgramData ortak alandir, hem servis hem kullanici erisebilir.
    Kopru kurulumunda ayni yaklasim kullanildi.
    """
    taban = os.environ.get("ProgramData") or r"C:\ProgramData"
    yol = os.path.join(taban, "Goktungu", "Merkez")
    try:
        os.makedirs(yol, exist_ok=True)
    except Exception:
        yol = KOK
    return yol


class _Yazici:
    """Hem Windows Olay Gunlugu'ne hem dosyaya yazar.

    NEDEN IKISI: Olay Gunlugu kisa iletiler icin uygundur ve uzaktan
    okunabilir; ancak Python yigin izleri oraya sigmaz ve bicimi bozulur.
    Dosya gunlugu sahada teshis icin gereklidir.
    """

    def __init__(self) -> None:
        self._yol = os.path.join(_veri_dizini(), "servis.log")

    def yaz(self, etiket: str, metin: str, seviye: str = "bilgi") -> None:
        satir = "%s [%s] %s" % (
            time.strftime("%Y-%m-%d %H:%M:%S"), etiket, metin)
        try:
            with open(self._yol, "a", encoding="utf-8") as f:
                f.write(satir + "\n")
        except Exception:
            pass
        if not _PYWIN32:
            return
        try:
            if seviye == "hata":
                servicemanager.LogErrorMsg(satir)
            elif seviye == "uyari":
                servicemanager.LogWarningMsg(satir)
            else:
                servicemanager.LogInfoMsg(satir)
        except Exception:
            pass


def _yorumlayici() -> str:
    """main.py'yi baslatacak GERCEK Python yolunu bulur.

    ## KUSUR-ALTSERVIS-140 (kopruden devralinan olculmus kusur)

    Servis olarak calisirken sureci pywin32'nin `pythonservice.exe`
    barindiricisi baslatir ve `sys.executable` O DOSYAYI gosterir.
    `main.py` onunla baslatilirsa barindirici kendi kullanim metnini
    basip cikis kodu 2 ile sonlanir: yazilim HIC ayaga kalkmaz ve
    kullanici yalnizca "servis baslatildi ama panel yok" gorur.
    """
    aday = sys.executable or ""
    if aday and os.path.basename(aday).lower() not in (
            "pythonservice.exe", "pythonservicew.exe"):
        return aday
    # Kurulum duzeni: ...\Goktungu\Merkez\python\python.exe
    for y in (os.path.join(KOK, "python", "python.exe"),
              os.path.join(KOK, "python", "pythonw.exe")):
        if os.path.isfile(y):
            return y
    raise RuntimeError(
        "Python yorumlayicisi bulunamadi. Beklenen: %s"
        % os.path.join(KOK, "python", "python.exe"))


class GoktunguMerkezServisi(win32serviceutil.ServiceFramework):  # type: ignore[misc]
    """SCM baglanti noktasi."""

    _svc_name_ = SERVIS_ADI
    _svc_display_name_ = SERVIS_GORUNEN_AD
    _svc_description_ = SERVIS_ACIKLAMA

    def __init__(self, args) -> None:
        win32serviceutil.ServiceFramework.__init__(self, args)
        self._dur_olayi = win32event.CreateEvent(None, 0, 0, None)
        self._surec: subprocess.Popen | None = None
        self._g = _Yazici()

    # -- SCM cagrilari ------------------------------------------------
    def SvcStop(self) -> None:
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self._g.yaz("SERVIS", "Durdurma istegi alindi", "bilgi")
        win32event.SetEvent(self._dur_olayi)

    def SvcDoRun(self) -> None:
        try:
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, ""))
        except Exception:
            pass
        try:
            self._calis()
        except Exception:
            self._g.yaz("SERVIS", "Beklenmeyen hata:\n%s"
                        % traceback.format_exc(), "hata")
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)
            return
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)

    # -- Asil is ------------------------------------------------------
    def _calis(self) -> None:
        # v2.5.26: Servis artık ana uygulamayı DOĞRUDAN değil, arka plan
        # güncelleyici (gözetmen) üzerinden çalıştırır. Gözetmen main.py'yi
        # başlatır, çökerse yeniden başlatır ve dosya tabanlı güncellemeyi
        # uygular. Böylece güncellemeler imzasız .exe indirmez (AV dostu).
        ana = os.path.join(KOK, "goktungu_guncelleyici.py")
        if not os.path.isfile(ana):
            self._g.yaz("SERVIS", "guncelleyici bulunamadi: %s" % ana, "hata")
            raise RuntimeError("main.py yok")

        try:
            py = _yorumlayici()
        except RuntimeError as e:
            self._g.yaz("PYTHON", str(e), "hata")
            raise
        self._g.yaz("PYTHON", "Yorumlayici: %s (surec ikilisi: %s)"
                    % (py, sys.executable), "bilgi")

        gunluk_yolu = os.path.join(_veri_dizini(), "merkez_cikti.log")
        gunluk = open(gunluk_yolu, "ab")
        self._g.yaz("SERVIS", "Uygulama ciktisi: %s" % gunluk_yolu, "bilgi")

        ortam = os.environ.copy()
        # Kopru ile AYNI MAKINEDE calisabilmek icin portlari kaydir.
        #
        # Kullanici istegi (birebir): "isteyen sirket yoneticisi ayni
        # bilgisayara ister merkez yazilimini isterse ayni anda kopru
        # yazilimini calistirabilir ona gore organize et".
        #
        # OLCULEN CAKISMA (bkz. OLCUM_PORT_CAKISMASI.md):
        #   MJPEG vekili : GCS 8801 <-> kopru 8801
        #   AI iscisi    : GCS 8900 <-> kopru 8900
        # Ikisi ayni anda kosarsa ikinci baglama basarisiz olur.
        #
        # Yalniz DEGER ATANMAMISSA yazilir: yonetici ayar.json veya
        # servis ortamindan kendi degerini vermisse ona dokunulmaz.
        # Degisken adlari KODDAN okundu, tahmin edilmedi:
        #   goktungu/video_proxy.py:57 -> _port_oku("GOKTUNGU_VIDEO_PORT", 8801)
        #   main.py:807             -> os.environ.get("GOKTUNGU_AI_PORT")
        ortam.setdefault("GOKTUNGU_VIDEO_PORT", "8811")
        ortam.setdefault("GOKTUNGU_AI_PORT", "8910")
        # Alt surec `main.py`'nin kendi kapanis yolunu kullanabilsin.
        ortam.setdefault("PYTHONUNBUFFERED", "1")

        # CREATE_NEW_PROCESS_GROUP: CTRL_BREAK_EVENT gonderebilmek icin
        # ZORUNLUDUR. Grup olusturulmazsa sinyal servis surecinin
        # kendisini de vurur ve servis kendi kendini oldurur.
        bayrak = 0
        if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            bayrak |= subprocess.CREATE_NEW_PROCESS_GROUP
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            bayrak |= subprocess.CREATE_NO_WINDOW

        self._surec = subprocess.Popen(
            [py, ana], cwd=KOK, env=ortam,
            stdout=gunluk, stderr=subprocess.STDOUT,
            creationflags=bayrak)
        self._g.yaz("SERVIS", "main.py baslatildi (PID %d)"
                    % self._surec.pid, "basari")

        # SCM'ye 'calisiyorum' bildir.
        #
        # Alt surec ayaga kalkarken kisa bir dogrulama penceresi taninir:
        # main.py aninda coktuyse (or. eksik bagimlilik) servisi
        # "Calisiyor" gostermek yanlis olur; operator kisayola basar ve
        # bos sayfa gorur. 3 sn icinde olen surec kusurlu sayilir.
        time.sleep(3.0)
        if self._surec.poll() is not None:
            kod = self._surec.returncode
            self._g.yaz("SERVIS",
                        "main.py hemen sonlandi (cikis kodu %s). "
                        "Ayrinti: %s" % (kod, gunluk_yolu), "hata")
            raise RuntimeError("main.py cikis kodu %s" % kod)

        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        self._g.yaz("SERVIS", "Servis calisiyor", "basari")

        # Durdurma istegi VEYA alt surecin olumu beklenir.
        #
        # Alt surec cokerse servis de durmalidir; aksi halde SCM
        # "Calisiyor" gosterir ama yazilim yoktur. `sc failure` ile
        # kurulan kurtarma politikasi ancak servis DURURSA devreye
        # girer, bu yuzden burada donguden cikmak gerekir.
        while True:
            sonuc = win32event.WaitForSingleObject(self._dur_olayi, 2000)
            if sonuc == win32event.WAIT_OBJECT_0:
                break                      # durdurma istegi
            if self._surec.poll() is not None:
                self._g.yaz("SERVIS",
                            "main.py beklenmedik bicimde sonlandi "
                            "(cikis kodu %s); servis duruyor ki kurtarma "
                            "politikasi devreye girsin"
                            % self._surec.returncode, "hata")
                try:
                    gunluk.close()
                except Exception:
                    pass
                return

        self._g.yaz("SERVIS", "Kapatiliyor...", "bilgi")
        self._alt_sureci_kapat()
        try:
            gunluk.close()
        except Exception:
            pass
        self._g.yaz("SERVIS", "Servis durdu", "basari")

    def _alt_sureci_kapat(self) -> None:
        """Alt sureci once nazikce, sonra zorla kapatir."""
        p = self._surec
        if p is None or p.poll() is not None:
            return

        # 1) Nazik: CTRL_BREAK_EVENT. `main.py`'nin kendi temizleme
        #    yolunu (telemetri tamponu, veritabani) calistirir.
        try:
            if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
                import signal as _s
                p.send_signal(_s.CTRL_BREAK_EVENT)   # type: ignore[attr-defined]
                self._g.yaz("SERVIS", "CTRL_BREAK gonderildi", "bilgi")
        except Exception as e:
            self._g.yaz("SERVIS", "CTRL_BREAK gonderilemedi: %s" % e, "uyari")

        son = time.time() + KAPANIS_SURESI
        while time.time() < son:
            if p.poll() is not None:
                self._g.yaz("SERVIS", "Uygulama nazikce kapandi "
                                      "(cikis kodu %s)" % p.returncode,
                            "basari")
                return
            # SCM'ye "hala kapaniyorum" bildir; aksi halde 30 sn sonra
            # servis "yanit vermiyor" diye isaretlenir.
            try:
                self.ReportServiceStatus(
                    win32service.SERVICE_STOP_PENDING, waitHint=5000)
            except Exception:
                pass
            time.sleep(0.5)

        # 2) Zorla: terminate()
        self._g.yaz("SERVIS", "Uygulama %d sn icinde kapanmadi; "
                              "zorla sonlandiriliyor" % int(KAPANIS_SURESI),
                    "uyari")
        try:
            p.terminate()
            p.wait(timeout=5)
            return
        except Exception:
            pass

        # 3) Son care: kill()
        try:
            p.kill()
            self._g.yaz("SERVIS", "Uygulama zorla sonlandirildi", "uyari")
        except Exception as e:
            self._g.yaz("SERVIS", "Uygulama sonlandirilamadi: %s" % e, "hata")


def main(argv=None) -> int:
    """Servis komut satiri.

    Argumansiz cagrildiginda SCM baglanti noktasi olarak davranir;
    `install/start/stop/remove` verilirse pywin32 yonetim kabugu
    kullanilir.
    """
    if not _PYWIN32:
        sys.stderr.write(
            "pywin32 kurulu degil; Windows servisi kullanilamaz.\n"
            "Kurulum paketi pywin32'yi gomulu Python icinde tasir.\n")
        return 2

    argv = list(sys.argv if argv is None else argv)
    if len(argv) == 1:
        try:
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(GoktunguMerkezServisi)
            servicemanager.StartServiceCtrlDispatcher()
            return 0
        except Exception:
            # SCM baglanti noktasi degil (elle calistirilmis): yardim bas.
            win32serviceutil.HandleCommandLine(GoktunguMerkezServisi)
            return 0
    win32serviceutil.HandleCommandLine(GoktunguMerkezServisi, argv=argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
