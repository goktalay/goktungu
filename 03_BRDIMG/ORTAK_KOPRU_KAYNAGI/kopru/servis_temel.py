# -*- coding: utf-8 -*-
"""KOPRU YAZILIMI — servislerin ortak temeli.

Uc servis (Dron / AI / Video) AYRI SURECLER olarak calisir ama ayni
iskeleti paylasir:

  * stdout'a satir satir, tamponlanmadan yazar (panel konsolu canli
    aksin diye)
  * SIGTERM aldiginda kaynaklarini kapatip cikar (kopru "durdur"
    dedigi anda temiz sonlanma)
  * cokme durumunda cikis kodu ve son hata satiri konsola dusar

Bu iskelet ORTAK yazilmistir cunku uc yerde tekrarlanan sonlandirma
mantigi, birinde duzeltilen bir kusurun diger ikisinde yasamaya devam
etmesine yol acar.
"""
import json
import os
import signal
import sys
import tempfile
import threading
import time


class Servis:
    ad = "temel"
    baslik = "Servis"

    def __init__(self):
        self._dur = threading.Event()
        self.baslama_ts = time.time()

    # -----------------------------------------------------------------
    def yaz(self, metin, seviye="bilgi"):
        im = {"bilgi": "", "basari": "[OK] ", "uyari": "[UYARI] ",
              "hata": "[HATA] "}.get(seviye, "")
        # `flush=True` zorunludur: alt surec ciktisi tamponlanirsa panel
        # konsolu bos gorunur ve kullanici servisin dondugunu sanir.
        print("%s %s%s" % (time.strftime("%H:%M:%S"), im, metin), flush=True)

    def durdur_istendi(self):
        return self._dur.is_set()

    def bekle(self, sn):
        """Kesintiye duyarli bekleme.

        `time.sleep` kullanilsaydi, durdurma istegi uykunun bitmesini
        beklerdi; 30 sn'lik bir uykuda kullanici paneli 30 sn boyunca
        "durduruluyor" gorurdu.
        """
        return self._dur.wait(sn)

    # -----------------------------------------------------------------
    def durum_yaz(self, **olcumler):
        """Olcumleri kopru panelinin okuyabilecegi dosyaya yazar.

        Panel bu servisi ALT SUREC olarak baslatir; surecler arasi bellek
        paylasimi olmadigi icin olcumler (etkin dron sayisi, kuyruk boyu,
        kare hizi) dosya araciligiyla aktarilir.

        ATOMIK YAZMA zorunludur: panel saniyede bir okur. Dosyaya dogrudan
        yazilsaydi, okuma tam yazma anina denk geldiginde YARIM JSON
        okunur ve panel gecersiz veri yuzunden olcumu 0 gosterirdi.
        """
        yol = os.environ.get("GOKTUNGU_KOPRU_DURUM_DOSYASI")
        if not yol:
            return False
        veri = dict(olcumler)
        veri["ts"] = time.time()
        veri["servis"] = self.ad
        try:
            dizin = os.path.dirname(yol) or "."
            os.makedirs(dizin, exist_ok=True)
            gecici = None
            with tempfile.NamedTemporaryFile(
                    "w", encoding="utf-8", dir=dizin, delete=False,
                    prefix=".durum_", suffix=".tmp") as f:
                gecici = f.name
                json.dump(veri, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            # os.replace atomiktir ve Windows'ta da var olan hedefin
            # uzerine yazar (os.rename Windows'ta hata verir).
            os.replace(gecici, yol)
            return True
        except Exception:
            # Olcum yazimi ASLA servisi dusurmemelidir: dron ucusu bir
            # istatistik dosyasi yuzunden kesilemez.
            try:
                if gecici and os.path.exists(gecici):
                    os.remove(gecici)
            except Exception:
                pass
            return False

    # -----------------------------------------------------------------
    def hazirla(self):
        """Alt siniflar gerekiyorsa gecersiz kilar."""

    def dongu(self):
        raise NotImplementedError

    def kapat(self):
        """Alt siniflar kaynak kapatmak icin gecersiz kilar."""

    # -----------------------------------------------------------------
    def kos(self):
        def _sinyal(*_):
            self.yaz("Sonlandirma sinyali alindi", "uyari")
            self._dur.set()

        for s in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(s, _sinyal)
            except Exception:
                pass

        self.yaz("%s baslatiliyor (pid %d)" % (self.baslik, os.getpid()))
        try:
            self.hazirla()
            self.dongu()
        except KeyboardInterrupt:
            self._dur.set()
        except Exception as e:
            # Cokme izini KONSOLA yaz: kullanici panelde gorecek. Yalniz
            # stderr'e dusen bir yigin izi, alt surec sonlandiginda
            # kaybolur ve teshis imkansizlasir.
            import traceback
            self.yaz("Beklenmeyen hata: %s: %s" % (type(e).__name__, e),
                     "hata")
            for satir in traceback.format_exc().splitlines():
                self.yaz("  " + satir, "hata")
            self.kapat()
            return 1
        self.kapat()
        self.yaz("%s sonlandi" % self.baslik, "bilgi")
        return 0


def calistir(sinif):
    sys.exit(sinif().kos())
