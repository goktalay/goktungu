#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GOKTUNGU KOPRU — Windows Servis Denetim Yoneticisi (SCM) servisi.

## NEDEN AYRI DOSYA

v1.3.0'da kopru Gorev Zamanlayici gorevi olarak calisiyordu. Kullanici
GERCEK SERVIS istedi: `services.msc` listesinde gorunmeli, Baslangic
Turu "Otomatik" olmali, "Baslat / Durdur / Yeniden Baslat" dugmeleri
Windows'un kendi arayuzunden calismali.

Gorev Zamanlayici bunu saglamaz. SCM servisi olmak icin surecin
`StartServiceCtrlDispatcher` cagrisiyla SCM'ye baglanmasi ve denetim
isteklerine (SERVICE_CONTROL_STOP vb.) yanit vermesi gerekir. pywin32
bu protokolu `win32serviceutil.ServiceFramework` ile sarar.

## NEDEN main.py DOGRUDAN SERVIS OLAMAZ

`main.py` bir konsol uygulamasidir: `signal.SIGINT/SIGTERM` bekler,
`while` dongusunde durur ve `webbrowser.open` cagirir. SCM ise
- SIGTERM GONDERMEZ, `SvcStop` metodunu cagirir,
- surecin 30 saniye icinde SERVICE_STOPPED bildirmesini bekler,
- masaustu oturumu OLMADAN calistigi icin tarayici acamaz.

Bu dosya araya girer: SCM protokolunu ustlenir, koprunun kendi
bilesenlerini (Uygulama + Panel) dogrudan cagirir ve durdurma
istegini olay nesnesine cevirir.

## TASARIM KARARI: main() cagirmak yerine bilesenler dogrudan

`main.main(["--tarayici-yok"])` cagirmak cazip gorunur ancak
`main()` icindeki `while not _DUR.is_set()` dongusu ve sinyal
kaydi servis baglaminda yanlistir: SCM `SvcStop` ile ayri bir is
parcacigindan durdurur, sinyal hic gelmez. Ayrica `main()` hata
durumunda `sys.exit` benzeri donus kodlari uretir; SCM'de bunlar
servis hata kodu olarak raporlanmalidir.

Bu yuzden servis, `Uygulama` ve `Panel` nesnelerini kendisi kurar.

## GUNLUK

Servis olarak calisirken `stdout` hicbir yere gitmez. Iki hedefe
yazilir:
1. Windows Olay Gunlugu (`servicemanager.LogInfoMsg`) — operatorun
   Olay Goruntuleyici'de gorecegi yer,
2. `%ProgramData%\\Goktungu\\Kopru\\gunluk\\servis.log` — ayrintili akis.

Kullanim (kurulum betigi tarafindan):
    python.exe servis_win.py install    # SCM'ye kaydet
    python.exe servis_win.py start
    python.exe servis_win.py stop
    python.exe servis_win.py remove
"""

from __future__ import annotations

import os
import sys
import threading
import time
import traceback

# Servis, kurulum dizininden calisir; `kopru` paketi bulunmali.
_BU_DIZIN = os.path.dirname(os.path.abspath(__file__))
if _BU_DIZIN not in sys.path:
    sys.path.insert(0, _BU_DIZIN)

# pywin32 iceri alimlari: servis disinda (ornegin Linux'ta sinav
# sirasinda) bu dosyanin ice alinabilmesi icin korumali yapilir.
try:
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil

    _PYWIN32 = True
except ImportError:  # pragma: no cover - Windows disi
    _PYWIN32 = False

    class _Sahte:
        """Windows disinda ice alma hatasi vermemek icin yer tutucu."""

        ServiceFramework = object

    win32serviceutil = _Sahte()  # type: ignore[assignment]


# ---------------------------------------------------------------------
# URUN PROFILI (Faz 5)
# ---------------------------------------------------------------------
# Ayni cekirdek iki AYRI Windows servisi olarak kurulabilir (BRDIMG /
# BRDTLM). Urun; once `GOKTUNGU_KOPRU_URUN` ortam degiskeninden, o bos
# ise kurulum dizinindeki `URUN` dosyasindan belirlenir (BRDTLM setup'i
# bu dosyayi yazar). Belirlenirse ortam degiskeni de sabitlenir; boylece
# hem servis sureci hem de baslattigi alt servisler ayni profili gorur.
#
# GERIYE UYUMLULUK — KRITIK: ne degisken ne dosya varsa `_URUN` bos
# kalir; servis adi ve kimligi mevcut BRDIMG degerlerinde kalir ve
# os.environ'a DOKUNULMAZ. BRDIMG servis davranisi degismez.


def _urun_belirle():
    u = str(os.environ.get("GOKTUNGU_KOPRU_URUN") or "").strip().lower()
    if not u:
        try:
            yol = os.path.join(_BU_DIZIN, "URUN")
            if os.path.isfile(yol):
                with open(yol, "r", encoding="utf-8") as f:
                    u = f.read().strip().lower()
        except Exception:
            u = ""
    return u


_URUN = _urun_belirle()
if _URUN and _URUN != "brdimg":
    # Alt servisler os.environ'i miras alir; profil suzgeci orada da
    # etkin olsun. `setdefault`: degisken zaten verilmisse ezme.
    os.environ.setdefault("GOKTUNGU_KOPRU_URUN", _URUN)

if _URUN == "brdtlm":
    SERVIS_ADI = "GoktunguKopruTlm"
    SERVIS_GORUNEN_AD = "GOKTUNGU Kopru (Telemetri)"
    SERVIS_ACIKLAMA = (
        "GOKTUNGU saha telemetri/cihaz koprusu: yerel dron (ArduPilot / "
        "Betaflight), M50 elektro-optik, radar ve GroundGCC servislerini "
        "yonetir ve telemetriyi GOKTUNGU merkezine aktarir. "
        "Yerel panel: http://127.0.0.1:8791/"
    )
else:
    SERVIS_ADI = "GoktunguKopru"
    SERVIS_GORUNEN_AD = "GOKTUNGU Kopru Yazilimi"
    SERVIS_ACIKLAMA = (
        "GOKTUNGU saha kopru yazilimi: yerel dron, AI, video, GroundGCC ve "
        "radar servislerini yonetir ve telemetriyi GOKTUNGU merkezine "
        "aktarir. Yerel panel: http://127.0.0.1:8790/"
    )


def _gunluk_dosyasi() -> str:
    """Servis gunlugunun tam yolu.

    `ayar.veri_dizini()` kullanilir; boylece gunluk, ayarlarla ayni
    yerde (Windows'ta ProgramData veya APPDATA) toplanir ve kurulum
    dizininden ayri kalir.
    """
    try:
        from kopru import ayar as ayar_mod

        kok = os.path.join(ayar_mod.veri_dizini(), "gunluk")
    except Exception:
        kok = os.path.join(
            os.environ.get("PROGRAMDATA") or os.path.expanduser("~"),
            "Goktungu", "Kopru", "gunluk")
    os.makedirs(kok, exist_ok=True)
    return os.path.join(kok, "servis.log")


class _Yazici:
    """Servis gunluk yazicisi: dosya + Windows Olay Gunlugu.

    Olay gunlugune YALNIZ onemli olaylar yazilir (baslama, durma,
    hata). Her telemetri satirini Olay Gunlugu'ne yazmak, olay
    gunlugunu bogar ve operatorun gercek hatalari gormesini
    engeller.
    """

    def __init__(self) -> None:
        self.yol = _gunluk_dosyasi()
        self._kilit = threading.Lock()

    def yaz(self, etiket: str, metin: str, seviye: str = "bilgi") -> None:
        im = {"bilgi": "", "basari": "[OK] ", "uyari": "[UYARI] ",
              "hata": "[HATA] "}.get(seviye, "")
        satir = "%s [%s] %s%s" % (
            time.strftime("%Y-%m-%d %H:%M:%S"), etiket, im, metin)
        with self._kilit:
            try:
                # Gunluk dosyasi sinirsiz buyuyemez: 5 MB'i asinca
                # tek yedek olarak dondurulur. Servis aylarca
                # calisir; sinirsiz dosya diski doldurur ve asil
                # kusur bu olur.
                if (os.path.exists(self.yol)
                        and os.path.getsize(self.yol) > 5 * 1024 * 1024):
                    yedek = self.yol + ".1"
                    try:
                        if os.path.exists(yedek):
                            os.remove(yedek)
                        os.replace(self.yol, yedek)
                    except OSError:
                        pass
                with open(self.yol, "a", encoding="utf-8") as f:
                    f.write(satir + "\n")
            except Exception:
                pass
        if seviye in ("hata", "uyari") and _PYWIN32:
            try:
                if seviye == "hata":
                    servicemanager.LogErrorMsg(satir)
                else:
                    servicemanager.LogWarningMsg(satir)
            except Exception:
                pass


class GoktunguKopruServisi(win32serviceutil.ServiceFramework):  # type: ignore[misc]
    """SCM servisi olarak kopru yazilimi."""

    _svc_name_ = SERVIS_ADI
    _svc_display_name_ = SERVIS_GORUNEN_AD
    _svc_description_ = SERVIS_ACIKLAMA

    def __init__(self, args) -> None:
        win32serviceutil.ServiceFramework.__init__(self, args)
        # SCM durdurma istegini bu olayla is parcaciklari arasi
        # tasiyoruz. `threading.Event` yerine Windows olay nesnesi
        # kullanilir: `SvcStop` SCM'nin ayri bir is parcacigindan
        # cagrilir ve bekleme WaitForSingleObject ile yapilir.
        self._dur_olayi = win32event.CreateEvent(None, 0, 0, None)
        self._g = _Yazici()
        self._uyg = None
        self._panel = None

    # -- SCM denetim isleyicileri ------------------------------------
    def SvcStop(self) -> None:
        """SCM 'Durdur' dedi.

        Once SERVICE_STOP_PENDING bildirilir: kapanis birkac saniye
        surer ve bu bildirim yapilmazsa Windows 'servis istege
        zamaninda yanit vermedi' hatasi verir.
        """
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self._g.yaz("SERVIS", "Durdurma istegi alindi", "bilgi")
        win32event.SetEvent(self._dur_olayi)

    def SvcDoRun(self) -> None:
        """Servis govdesi."""
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
            # Cikis kodu 1 ile durursa SCM kurtarma politikasi
            # (yeniden baslat) devreye girer.
            self.ReportServiceStatus(win32service.SERVICE_STOPPED,
                                     win32ExitCode=1)
            return
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)

    # -- Asil is ------------------------------------------------------
    def _yorumlayiciyi_sabitle(self) -> None:
        """Alt servislerin kullanacagi Python yolunu ortama yaz.

        ## KUSUR-ALTSERVIS-140

        Servis olarak calisirken sureci pywin32'nin
        `pythonservice.exe` barindiricisi baslatir ve `sys.executable`
        O DOSYAYI gosterir. Alt servisler onunla baslatilirsa
        barindirici kendi kullanim metnini basip cikis kodu 2 ile
        sonlanir: bes servis de hic ayaga kalkmaz.

        `servisler.yorumlayici_yolu()` bunu kendisi de cozer; burada
        ortam degiskenini ayrica yazmanin iki faydasi var:
        1. Cozumleme servis basinda BIR KEZ yapilir ve gunluge dusuru-
           lur; sahada "hangi python kullanildi" sorusu belgelenir.
        2. Ortam degiskeni alt sureclere miras gecer; kopru disinda
           calisan yardimci araclar da ayni yorumlayiciyi gorur.
        """
        from kopru import servisler as servisler_mod

        try:
            yol = servisler_mod.yorumlayici_yolu()
        except RuntimeError as e:
            self._g.yaz("PYTHON", str(e), "hata")
            raise
        os.environ["GOKTUNGU_KOPRU_PYTHON"] = yol
        if yol != sys.executable:
            # Beklenen durum: barindirici yerine gercek yorumlayici.
            self._g.yaz("PYTHON", "Alt servisler icin yorumlayici: %s "
                                  "(surec ikilisi: %s)"
                        % (yol, sys.executable), "bilgi")
        else:
            self._g.yaz("PYTHON", "Alt servisler icin yorumlayici: %s"
                        % yol, "bilgi")

    def _calis(self) -> None:
        from kopru import ayar as ayar_mod
        from kopru import kilit as kilit_mod
        from kopru.panel import Panel
        from kopru.uygulama import Uygulama

        self._g.yaz("SERVIS", "GOKTUNGU Kopru %s baslatiliyor"
                    % ayar_mod.SURUM, "basari")
        self._g.yaz("VERI", "Ayar dizini: %s" % ayar_mod.veri_dizini())
        self._yorumlayiciyi_sabitle()

        # Tek ornek kilidi: kullanici hem servisi hem masaustu
        # kisayolunu calistirirsa iki surec ayni merkez kimligini
        # kullanir ve merkez baglantisi surekli dusurulur.
        try:
            kilit_mod.al()
        except Exception as e:
            self._g.yaz("SERVIS", "Baska bir kopru ornegi calisiyor: %s"
                        % e, "hata")
            raise

        self._uyg = Uygulama(gunluk=self._g.yaz)
        self._panel = Panel(self._uyg, arayuz=None, port=None)
        try:
            adres = self._panel.baslat()
        except OSError as e:
            self._g.yaz("PANEL", "Panel portu acilamadi: %s" % e, "hata")
            self._g.yaz("PANEL", "Portu degistirmek icin ayar.json "
                                 "icindeki panel_port alanini duzenleyin",
                        "bilgi")
            kilit_mod.birak()
            raise
        self._g.yaz("PANEL", "Yerel panel hazir: %s" % adres, "basari")

        if ayar_mod.kimlik_var():
            tamam, hata = self._uyg.ajan_baslat()
            if not tamam:
                self._g.yaz("KOPRU", "Ajan baslatilamadi: %s" % hata,
                            "uyari")
        else:
            self._g.yaz("KOPRU", "Merkez kaydi yok. Panele girip "
                                 "'Bu bilgisayari merkeze kaydet' "
                                 "dugmesini kullanin.", "uyari")

        self._uyg.acilista_servisleri_baslat()

        # SCM'ye 'calisiyorum' bildir; bu satirdan once bildirilirse
        # panel henuz hazir olmadigi halde servis 'Calisiyor' gorunur
        # ve operator kisayola basip bos sayfa gorur.
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        self._g.yaz("SERVIS", "Servis calisiyor", "basari")

        # Durdurma istegine kadar bekle. Zaman asimi yok: olay
        # gelene kadar blokla (INFINITE), bosa CPU harcamaz.
        win32event.WaitForSingleObject(self._dur_olayi,
                                       win32event.INFINITE)

        self._g.yaz("SERVIS", "Kapatiliyor...", "bilgi")
        try:
            self._uyg.kapat()
        except Exception as e:
            self._g.yaz("SERVIS", "Uygulama kapatilirken: %s" % e, "uyari")
        try:
            self._panel.durdur()
        except Exception as e:
            self._g.yaz("SERVIS", "Panel kapatilirken: %s" % e, "uyari")
        try:
            kilit_mod.birak()
        except Exception:
            pass
        self._g.yaz("SERVIS", "Servis durdu", "basari")


def main(argv=None) -> int:
    """Servis komut satiri.

    Argumansiz cagrildiginda SCM baglanti noktasi olarak davranir;
    `install/start/stop/remove` verilirse pywin32'nin kendi yonetim
    kabugu kullanilir.
    """
    if not _PYWIN32:
        sys.stderr.write(
            "Bu dosya yalniz Windows'ta, pywin32 kurulu ortamda "
            "calisir.\n")
        return 3

    argv = list(sys.argv if argv is None else argv)
    if len(argv) == 1:
        # SCM tarafindan baslatildi.
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(GoktunguKopruServisi)
        servicemanager.StartServiceCtrlDispatcher()
        return 0

    win32serviceutil.HandleCommandLine(GoktunguKopruServisi, argv=argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
