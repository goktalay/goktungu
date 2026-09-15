# -*- coding: utf-8 -*-
"""VideoProxy: RTSP/RTP yayinlarini FFmpeg ile MJPEG'e cevirip HTTP'de sunar.

Web tarayicilari RTSP/RTP yayinlarina dogrudan baglanamaz. Bu modul her
aktif kamera icin bir FFmpeg alt sureci baslatir; surecin urettigi JPEG
kareleri multipart/x-mixed-replace (MJPEG) olarak HTTP uzerinden yayinlar.

    GET /kamera/<id>  ->  multipart/x-mixed-replace MJPEG akisi

Ayni kaynak icin tek FFmpeg sureci calisir; kareyi son alan tum HTTP
istemcilerine dagitan basit bir fan-out yapisi vardir. Hicbir izleyici
kalmadiginda surec otomatik sonlandirilir (30 sn bekleme sonrasi).
"""
import http.server
import json
import os
import shutil as _shutil
import socketserver
import subprocess
import threading
import time

# v2.5.27: Aynı yerel kamera cihazının (cv2.VideoCapture) açılışı ve
# release'i ASLA çakışmamalı — Windows DShow/MSMF eşzamanlı aç/kapada
# yerel bellek bozulması üretir (0xC0000374). Tüm donanım aç/bırak
# işlemleri bu tek kilit altında serileştirilir.
_DONANIM_KILIDI = threading.Lock()

try:
    import cv2
    import numpy as np
except ImportError:          # anotasyon/donanim istege bagli
    cv2 = None
    np = None


def _port_oku(anahtar, varsayilan):
    """Ortam degiskeniyle port kaydirma (v2.4.65).

    NEDEN GEREKLI: kullanici acikca istedi — "isteyen sirket yoneticisi
    ayni bilgisayara ister merkez yazilimini isterse ayni anda kopru
    yazilimini calistirabilir".

    Kopru de MJPEG vekilini 8801'de acar (`kopru/video_vekil.py`).
    Ikisi ayni makinede calisirsa ikinci baglama BASARISIZ olur ve
    kullanici bunu daha once yasadi:
        "[HTTPS] Port 8443 acilamadi ([WinError 10013] ...)"

    Bu yuzden Merkez Uygulama paketi portlarini kaydirir; kopru
    varsayilanda kalir. Gecersiz deger sessizce yok sayilir: yanlis
    yazilmis bir ortam degiskeni yuzunden video hic acilmamasi,
    varsayilana donmekten kotudur.
    """
    ham = (os.environ.get(anahtar) or "").strip()
    if not ham:
        return varsayilan
    try:
        p = int(ham)
    except ValueError:
        return varsayilan
    return p if 1 <= p <= 65535 else varsayilan


VIDEO_PROXY_PORT = _port_oku("GOKTUNGU_VIDEO_PORT", 8801)

# Tespit turu -> cerceve rengi (BGR) — C-UAS: yalniz hava araci + takip
_TUR_RENK = {
    "hava_araci": (255, 120, 60),
    "takip": (0, 0, 255),        # v2.4.164: takip cercevesi TAM KIRMIZI (BGR)
}

_TUR_AD = {
    "hava_araci": "HAVA ARACI",
    "takip": "TAKIP",
}


class AnotasyonDeposu:
    """AI iscilerinden gelen canli tespit kutularini tutar.

    Kutular kamera bazinda saklanir; belirli bir suredir yenilenmeyen
    kutular gecersiz sayilir (akista donuk kalmamalari icin).
    """

    # v2.4.169: YOLO cikarimi CPU'da saniyeler surebilir; kutular bir
    # sonraki cikarima kadar ekranda kalmali (eskiden 1.5 sn'de siliniyor,
    # yavas makinede surekli yanip sonuyordu).
    GECERLILIK_SN = 6.0

    def __init__(self):
        self._veri = {}          # kamera_id -> {"kutular": [...], "ts": t}
        self._kilit = threading.Lock()

    def guncelle(self, kamera_id, kutular):
        """kutular: [{x,y,w,h,tur,etiket}] — kaynak karesi pikselinde."""
        with self._kilit:
            self._veri[int(kamera_id)] = {
                "kutular": list(kutular or []), "ts": time.time()}

    def al(self, kamera_id):
        with self._kilit:
            k = self._veri.get(int(kamera_id))
        if not k or time.time() - k["ts"] > self.GECERLILIK_SN:
            return []
        return k["kutular"]

    def temizle(self, kamera_id):
        with self._kilit:
            self._veri.pop(int(kamera_id), None)


def _kutulari_ciz(kare_jpg, kutular):
    """JPEG kareyi cozer, tespit cerceve + etiketlerini cizer, yeniden
    JPEG kodlar. Hata durumunda orijinal kareyi dondurur."""
    if cv2 is None or not kutular:
        return kare_jpg
    try:
        dizi = np.frombuffer(kare_jpg, dtype=np.uint8)
        kare = cv2.imdecode(dizi, cv2.IMREAD_COLOR)
        if kare is None:
            return kare_jpg
        kh, kw = kare.shape[:2]
        for k in kutular:
            try:
                x, y = int(k.get("x", 0)), int(k.get("y", 0))
                w, h = int(k.get("w", 0)), int(k.get("h", 0))
                # kaynak cozunurlugu farkli olabilir -> oranla olcekle
                sw, sh = k.get("kaynak_w", 0), k.get("kaynak_h", 0)
                if sw and sh and (sw != kw or sh != kh):
                    ox, oy = kw / float(sw), kh / float(sh)
                    x, y = int(x * ox), int(y * oy)
                    w, h = int(w * ox), int(h * oy)
                if w <= 0 or h <= 0:
                    continue
                tur = k.get("tur", "")
                renk = _TUR_RENK.get(tur, (200, 200, 200))
                cv2.rectangle(kare, (x, y), (x + w, y + h), renk,
                              4 if tur == "takip" else 2)
                # kose vurgulari (hedef cercevesi gorunumu)
                u = max(6, min(w, h) // 6)
                for (cx, cy, dx, dy) in ((x, y, 1, 1), (x + w, y, -1, 1),
                                         (x, y + h, 1, -1),
                                         (x + w, y + h, -1, -1)):
                    cv2.line(kare, (cx, cy), (cx + dx * u, cy), renk, 3)
                    cv2.line(kare, (cx, cy), (cx, cy + dy * u), renk, 3)
                etiket = (k.get("etiket") or "").strip() or \
                    _TUR_AD.get(tur, tur.upper())
                if etiket:
                    (tw, th), tb = cv2.getTextSize(
                        etiket, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
                    ey = y - 8 if y - th - 12 > 0 else y + h + th + 10
                    cv2.rectangle(kare, (x, ey - th - 6),
                                  (x + tw + 10, ey + tb - 2), renk, -1)
                    cv2.putText(kare, etiket, (x + 5, ey),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                                (255, 255, 255), 2, cv2.LINE_AA)
            except Exception:
                continue
        ok, jpg = cv2.imencode(".jpg", kare,
                               [cv2.IMWRITE_JPEG_QUALITY, 80])
        return jpg.tobytes() if ok else kare_jpg
    except Exception:
        return kare_jpg

_JPEG_BASI = b"\xff\xd8"
_JPEG_SONU = b"\xff\xd9"

SINIR = b"--goktunguframe"


class _Yayin:
    """Tek kaynak icin FFmpeg sureci (veya OpenCV yakalama) + fan-out."""

    def __init__(self, kamera_id, url, protokol, konsol=None,
                 anotasyon=None, fps=15, genislik=960):
        self.kamera_id = kamera_id
        # v2.4.207: cikti genisligi tavani (kamera kaydi `genislik`);
        # ffmpeg scale ve OpenCV yeniden boyutlandirma bunu kullanir.
        try:
            self.genislik = max(160, min(3840, int(genislik or 960)))
        except (TypeError, ValueError):
            self.genislik = 960
        self.url = url
        self.protokol = protokol
        # v2.4.193 (Faz D): kare hizi tavani kamera kaydindan gelir.
        # Onceden UC ayri yerde sabit 15 yaziyordu (ffmpeg -r, donanim
        # dongusu, OpenCV geri cekilmesi); ucu de bu alani kullanir.
        try:
            self.fps = max(1, min(30, int(fps or 15)))
        except (TypeError, ValueError):
            self.fps = 15
        self.konsol = konsol
        self.anotasyon = anotasyon   # AnotasyonDeposu (opsiyonel)
        self.surec = None
        self.son_kare = None
        self.kare_no = 0
        self.kosul = threading.Condition()
        self.calisiyor = False
        self.izleyiciler = 0
        self.hata = None
        self._son_izleyici_zamani = time.time()

    # ------------------------------------------------------------------
    def baslat(self):
        if self.calisiyor:
            return True
        # v2.4.7: DONANIM (yerel kamera cihazi) OpenCV ile acilir
        if self.protokol == "donanim":
            if cv2 is None:
                self.hata = "opencv kurulu degil"
                return False
            self.calisiyor = True
            self.hata = None
            threading.Thread(target=self._oku_opencv, daemon=True).start()
            threading.Thread(target=self._bekci, daemon=True).start()
            return True
        # v2.4.166: "dosya" — sunucuya yuklenmis video dosyasi, dongulu
        # test yayini. url YALNIZ dosya adidir; yol daima veri kokundeki
        # kamera_videolar klasorune cozulur (yol gezinme engeli).
        # DIKKAT: self.url DEGISTIRILMEZ — yayin_al `y.url != url`
        # kiyasi yapar; degistirilse yayin her istekte yeniden baslardi.
        girdi = self.url
        if self.protokol == "dosya":
            from .sabitler import _veri_yolu
            ad = os.path.basename(str(self.url or "").strip())
            yol = _veri_yolu("kamera_videolar", ad) if ad else ""
            if not ad or not os.path.isfile(yol):
                self.hata = "video dosyasi bulunamadi: %s" % (ad or "(bos)")
                return False
            girdi = yol
        # v2.4.167: ffmpeg YOKSA OpenCV geri cekilmesi. opencv-python
        # tekerlegi kendi FFMPEG cozucusunu tasir; RTSP/HTTP/MJPEG/dosya
        # kaynaklari ffmpeg ikilisi kurulmadan da okunabilir. (Olculen
        # kusur: Windows kurulumunda ffmpeg yok; VLC RTSP'yi oynatirken
        # GRCOFF 503 donduruyordu.)
        if (cv2 is not None and _shutil.which("ffmpeg") is None
                and self.protokol in ("rtsp", "rtp", "mjpeg", "hls",
                                      "http", "dosya")):
            self.calisiyor = True
            self.hata = None
            threading.Thread(target=self._oku_opencv_kaynak,
                             args=(girdi, self.protokol == "dosya"),
                             daemon=True).start()
            threading.Thread(target=self._bekci, daemon=True).start()
            return True
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
        if self.protokol == "rtsp":
            cmd += ["-rtsp_transport", "tcp"]
        # v2.4.33: UZAK MJPEG KAYNAKLARINDA ILK KARE GECIKMESI
        # ------------------------------------------------------------
        # Olculen kusur: 1920x1080 bir Axis MJPEG kaynaginda ffmpeg'in
        # ilk kareyi uretmesi 3-7 sn suruyordu (mpjpeg demuxer'inin
        # varsayilan 5 sn'lik analiz suresi). Bu sure boyunca proxy
        # bos govdeli bir 200 yaniti tutuyor, tarayici da <img> icin
        # `error` olayini atesleyip "YAYIN ALINAMIYOR" gosteriyordu.
        #
        # mpjpeg akisinda her kare bagimsiz bir JPEG'dir; demuxer'in
        # uzun analiz yapmasina gerek yoktur. probesize/analyzeduration
        # dusurulerek ilk kare ~0.5 sn'ye iner.
        if self.protokol == "mjpeg":
            cmd += ["-probesize", "32768",
                    "-analyzeduration", "0",
                    "-use_wallclock_as_timestamps", "1"]
        # v2.4.10: HTTP video / HLS gibi dosya-tabanli kaynaklar gercek
        # zamanli okunur (-re) ve sonsuza dek dongulenir (-stream_loop):
        # boylece MP4 kaynagi da canli kamera gibi AI boru hattindan
        # kesintisiz akar.
        if self.protokol in ("http", "hls", "dosya"):
            cmd += ["-re", "-stream_loop", "-1"]
        else:
            # Dusuk gecikme secenekleri (canli kaynaklar)
            cmd += ["-fflags", "nobuffer", "-flags", "low_delay"]
        cmd += ["-i", girdi,
                "-an",                       # ses yok
                "-vf", "scale='min(%d,iw)':-2" % self.genislik,  # bant genisligi icin sinirla
                "-q:v", "7",
                "-r", str(self.fps),
                "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1"]
        try:
            self.surec = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                bufsize=0)
        except FileNotFoundError:
            # v2.4.34: eyleme donuk metin. Onceki "ffmpeg bulunamadi"
            # istemciye HIC ulasmiyordu; artik ulasiyor, dolayisiyla
            # kullanicinin ne yapacagini da soylemesi gerekiyor.
            self.hata = ("ffmpeg kurulu degil - kurulum: "
                         "winget install Gyan.FFmpeg (Windows) / "
                         "sudo apt install ffmpeg (Linux)")
            return False
        self.calisiyor = True
        self.hata = None
        threading.Thread(target=self._oku, daemon=True).start()
        threading.Thread(target=self._hata_oku, daemon=True).start()
        threading.Thread(target=self._bekci, daemon=True).start()
        return True

    # ------------------------------------------------------------------
    def ilk_kare_bekle(self, sure=12.0):
        """Ilk kare uretilene kadar bekler (v2.4.33).

        Doner: True (kare hazir) / False (sure doldu veya surec oldu).

        NEDEN: `baslat()` ffmpeg'i Popen ile baslatip HEMEN doner; ilk
        kare 0.5-7 sn sonra gelir. Onceki surumde proxy bu bilgiyi
        beklemeden 200 OK + multipart basliklarini yaziyordu, govde ise
        saniyelerce bos kaliyordu. Chromium bu durumda <img> icin
        `error` atesliyor ve kutu kalici olarak "YAYIN ALINAMIYOR"
        durumuna dusuyordu. Ilk kare beklenip sonra yanit yazilinca
        tarayici ya gercek goruntu ya da net bir 503 aliyor.
        """
        bitis = time.time() + float(sure)
        while time.time() < bitis:
            with self.kosul:
                if self.son_kare is not None:
                    return True
                # Surec oldu ve hic kare uretilmediyse beklemenin anlami yok
                if not self.calisiyor:
                    return self.son_kare is not None
                self.kosul.wait(timeout=0.25)
        with self.kosul:
            return self.son_kare is not None

    def durdur(self):
        self.calisiyor = False
        if self.surec:
            try:
                self.surec.terminate()
                self.surec.wait(timeout=3)
            except Exception:
                try:
                    self.surec.kill()
                except Exception:
                    pass
            self.surec = None
        with self.kosul:
            self.kosul.notify_all()

    # ------------------------------------------------------------------
    def _oku_opencv(self):
        """DONANIM: yerel kamera cihazini OpenCV ile okur (v2.4.7).

        url alani sayisal cihaz indeksidir ('0', '1'...). Browser
        deviceId (eski kayitlarda uzun hex) gelirse 0 varsayilir.
        """
        try:
            indeks = int(str(self.url).strip())
        except (TypeError, ValueError):
            indeks = 0
        # v2.4.9: Windows'ta MSMF backend'i bazi webcam'lerde takilir;
        # DSHOW ile de dene. Linux/mac varsayilan backend kullanir.
        cap = None
        import sys as _sys
        adaylar = ([cv2.CAP_DSHOW, cv2.CAP_ANY]
                   if _sys.platform.startswith("win") else [cv2.CAP_ANY])
        with _DONANIM_KILIDI:
            for be in adaylar:
                try:
                    cap = cv2.VideoCapture(indeks, be)
                except Exception:
                    cap = cv2.VideoCapture(indeks)
                if cap.isOpened():
                    break
                try:
                    cap.release()
                except Exception:
                    pass
                cap = None
        if cap is None or not cap.isOpened():
            self.hata = "cihaz acilamadi (indeks %s)" % indeks
            self.calisiyor = False
            with self.kosul:
                self.kosul.notify_all()
            if self.konsol:
                self.konsol("[VIDEO] Donanim cihazi acilamadi "
                            "(kamera %s, indeks %s)"
                            % (self.kamera_id, indeks))
            return
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
        onceki = 0.0
        while self.calisiyor:
            ok, kare = cap.read()
            if not ok:
                self.hata = "cihaz karesi okunamadi"
                break
            # Kamera kaydindaki tavana gore sinirla (v2.4.193)
            simdi = time.time()
            if simdi - onceki < 1.0 / self.fps:
                continue
            onceki = simdi
            okk, jpg = cv2.imencode(".jpg", kare,
                                    [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not okk:
                continue
            self._kare_yayinla(jpg.tobytes())
        with _DONANIM_KILIDI:
            try:
                cap.release()
            except Exception:
                pass
        self.calisiyor = False
        with self.kosul:
            self.kosul.notify_all()

    def _oku_opencv_kaynak(self, girdi, dongulu):
        """v2.4.167: ffmpeg ikilisi yokken RTSP/HTTP/MJPEG/dosya kaynagini
        OpenCV (kendi FFMPEG arka ucu) ile okur.

        `dongulu=True` ("dosya" protokolu): EOF'ta basa sarilir ve okuma
        dosya FPS'ine gore hizlanmadan (gercek zamanli) ilerletilir.
        Canli kaynaklar koptugunda 3 sn arayla yeniden baglanilir.
        Cikti ffmpeg yoluyla ayni: en cok 15 fps, genislik <= 960.
        """
        CIKTI_FPS = float(self.fps)
        while self.calisiyor:
            cap = None
            try:
                cap = cv2.VideoCapture(girdi)
            except Exception:
                cap = None
            if cap is None or not cap.isOpened():
                self.hata = "kaynak acilamadi (OpenCV): baglanti kurulamadi"
                try:
                    if cap is not None:
                        cap.release()
                except Exception:
                    pass
                if not self.calisiyor:
                    break
                # dosyada yeniden denemenin anlami yok; canli kaynakta var
                if dongulu:
                    break
                time.sleep(3.0)
                continue
            self.hata = None
            fps = 0.0
            try:
                fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
            except Exception:
                fps = 0.0
            dosya_fps = fps if 1.0 <= fps <= 60.0 else 25.0
            onceki_yayin = 0.0
            while self.calisiyor:
                ok, kare = cap.read()
                if not ok:
                    if dongulu:
                        try:
                            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            ok, kare = cap.read()
                        except Exception:
                            ok = False
                        if not ok:
                            break   # dosya okunamaz oldu -> yeniden ac
                    else:
                        self.hata = "kaynak koptu; yeniden baglaniliyor"
                        break
                if dongulu:
                    # dosya gercek zamanli aksin (yoksa saniyeler icinde biter)
                    time.sleep(1.0 / dosya_fps)
                simdi = time.time()
                if simdi - onceki_yayin < 1.0 / CIKTI_FPS:
                    continue
                onceki_yayin = simdi
                try:
                    h, w = kare.shape[:2]
                    if w > self.genislik:
                        olcek = float(self.genislik) / w
                        kare = cv2.resize(kare, (self.genislik, int(h * olcek)))
                    okk, jpg = cv2.imencode(".jpg", kare,
                                            [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if okk:
                        self._kare_yayinla(jpg.tobytes())
                except Exception:
                    continue
            try:
                cap.release()
            except Exception:
                pass
            if not self.calisiyor:
                break
            time.sleep(3.0)
        self.calisiyor = False
        with self.kosul:
            self.kosul.notify_all()

    def _kare_yayinla(self, kare):
        """Kareyi (varsa anotasyonla) izleyicilere yayinlar."""
        if self.anotasyon is not None:
            kutular = self.anotasyon.al(self.kamera_id)
            if kutular:
                kare = _kutulari_ciz(kare, kutular)
        with self.kosul:
            self.son_kare = kare
            self.kare_no += 1
            self.kosul.notify_all()

    def _oku(self):
        """FFmpeg stdout'undan JPEG karelerini ayiklar."""
        tampon = b""
        while self.calisiyor and self.surec and self.surec.stdout:
            try:
                parca = self.surec.stdout.read(65536)
            except Exception:
                break
            if not parca:
                break
            tampon += parca
            while True:
                bas = tampon.find(_JPEG_BASI)
                if bas < 0:
                    tampon = b""
                    break
                son = tampon.find(_JPEG_SONU, bas + 2)
                if son < 0:
                    if bas > 0:
                        tampon = tampon[bas:]
                    break
                kare = tampon[bas:son + 2]
                tampon = tampon[son + 2:]
                self._kare_yayinla(kare)
        self.calisiyor = False
        with self.kosul:
            self.kosul.notify_all()

    def _hata_oku(self):
        """FFmpeg stderr'ini okur; son hata satirini saklar."""
        surec = self.surec
        if not surec or not surec.stderr:
            return
        for satir in iter(surec.stderr.readline, b""):
            s = satir.decode("utf-8", "replace").strip()
            if s:
                self.hata = s[-200:]
        # surec bitti
        if self.kare_no == 0 and self.konsol and self.hata:
            self.konsol("[VIDEO] Kaynak hatasi (kamera %s): %s"
                        % (self.kamera_id, self.hata))

    def _bekci(self):
        """Izleyici kalmadiysa 30 sn sonra sureci kapatir."""
        while self.calisiyor:
            time.sleep(5)
            if self.izleyiciler <= 0 and \
                    time.time() - self._son_izleyici_zamani > 30:
                if self.konsol:
                    self.konsol("[VIDEO] Izleyici kalmadi, kaynak "
                                "kapatildi (kamera %s)" % self.kamera_id)
                self.durdur()
                break

    # ------------------------------------------------------------------
    def izleyici_ekle(self):
        self.izleyiciler += 1
        self._son_izleyici_zamani = time.time()

    def izleyici_cikar(self):
        self.izleyiciler = max(0, self.izleyiciler - 1)
        self._son_izleyici_zamani = time.time()


class VideoProxy:
    """RTSP/RTP -> MJPEG proxy HTTP sunucusu (port 8801)."""

    def __init__(self, kameralar, konsol=None, port=VIDEO_PROXY_PORT):
        self.kameralar = kameralar
        self.konsol = konsol or (lambda *a: None)
        self.port = port
        self.yayinlar = {}          # kamera_id -> _Yayin
        self._kilit = threading.Lock()
        self.dji_kopru = None       # v2.1.8: main.py baglar
        self.m50_vekil = None       # v2.4.181: main.py baglar (M50Vekili)
        self.anotasyon = AnotasyonDeposu()  # v2.4.7: AI tespit kutulari
        # v2.4.34: kamera_id -> son basarisizlik gerekcesi (istemciye iletilir)
        self._son_hatalar = {}

    # ------------------------------------------------------------------
    @staticmethod
    def cihaz_listesi(en_fazla=6):
        """Sunucu makinesindeki yerel kamera cihazlarini tarar (v2.4.7)."""
        cihazlar = []
        if cv2 is None:
            return cihazlar
        for i in range(en_fazla):
            cap = cv2.VideoCapture(i)
            try:
                if cap.isOpened():
                    ok, _ = cap.read()
                    if ok:
                        cihazlar.append({"indeks": i,
                                         "ad": "Kamera %d" % i})
            except Exception:
                pass
            finally:
                cap.release()
        return cihazlar

    def _url_coz(self, kam):
        """Kamera kaydinin gercek akis URL'sini dondurur.

        'dji' protokolunde url 'dji:<sysid>' bicimindedir; gercek MJPEG
        adresi Android kopru uygulamasinin bildirdigi video_url'dir.
        'm50' protokolunde url 'm50:<kanal>' (gorunur/termal) bicimindedir;
        gercek RTSP adresi M50 saha Koprusunun bildirdigi (kimlik bilgisiz)
        yerel yeniden yayindir — kamera kaydinda ASLA saklanmaz, her
        acilista taze okunur (bkz. M50Vekili.rtsp_url).
        """
        url = kam["url"]
        if kam.get("protokol") == "dji" and self.dji_kopru:
            try:
                sysid = int(str(url).split(":", 1)[1])
            except (IndexError, ValueError):
                return None
            gercek = self.dji_kopru.video_url(sysid)
            return gercek or None
        if kam.get("protokol") == "m50" and self.m50_vekil:
            # v2.4.191: 'm50:<eo_id>:<kanal>' (coklu EO) veya eski 'm50:<kanal>'.
            parcalar = str(url).split(":")
            eo_id = None
            kanal = ""
            if len(parcalar) >= 3:
                try:
                    eo_id = int(parcalar[1])
                except (TypeError, ValueError):
                    eo_id = None
                kanal = parcalar[2]
            elif len(parcalar) == 2:
                kanal = parcalar[1]
            # v2.4.204: yakalama icin KIMLIKLI adres (varsa); arayuze/
            # telemetriye giden arindirilmis adres degismez.
            if hasattr(self.m50_vekil, "rtsp_url_yakalama"):
                try:
                    return self.m50_vekil.rtsp_url_yakalama(kanal, eo_id)
                except Exception:
                    pass
            try:
                return self.m50_vekil.rtsp_url(kanal, eo_id)
            except TypeError:
                return self.m50_vekil.rtsp_url(kanal)
        return url

    # ------------------------------------------------------------------
    def son_hata(self, kamera_id):
        """Kamera icin en son basarisizlik gerekcesini dondurur (v2.4.34).

        `yayin_al` None dondugunde gerekce KAYBOLUYORDU: `_Yayin.baslat()`
        hatayi kendi ornegine yaziyor, ornek de atilan degere gidiyordu.
        Gerekce burada saklanir ki HTTP katmani istemciye net bir metin
        (ornegin "ffmpeg kurulu degil") iletebilsin.
        """
        with self._kilit:
            return self._son_hatalar.get(int(kamera_id))

    def yayin_al(self, kamera_id):
        """Kamera icin (gerekirse baslatarak) yayin nesnesi dondurur."""
        kam = self.kameralar.bul(kamera_id)
        if not kam:
            self._hata_yaz(kamera_id, "kamera kaydi bulunamadi")
            return None
        url = self._url_coz(kam)
        if not url:
            if kam.get("protokol") == "dji":
                gerekce = "DJI kopru henuz video adresi bildirmedi"
            elif kam.get("protokol") == "m50":
                gerekce = ("M50 saha Koprusu henuz bu kanal icin RTSP "
                          "adresi bildirmedi (M50 baglantisi/ayarlari "
                          "kontrol edilmeli)")
            else:
                gerekce = "kaynak adresi bos"
            self._hata_yaz(kamera_id, gerekce)
            return None
        # v2.4.181: 'm50' cozulmus URL'si duz bir RTSP adresidir; _Yayin'e
        # gercek protokol ("rtsp") verilir ki -rtsp_transport tcp gibi
        # rtsp'ye ozgu ffmpeg secenekleri uygulansin.
        fiili_protokol = "rtsp" if kam.get("protokol") == "m50" else kam["protokol"]
        # v2.4.193: FPS tavani DEGISTIYSE de yayin yeniden kurulur;
        # yoksa operator degeri kaydeder ama akis eski hizda kalir ve
        # ayarin islemedigini sanir.
        try:
            istenen_fps = max(1, min(30, int(kam.get("fps") or 15)))
        except (TypeError, ValueError):
            istenen_fps = 15
        try:
            istenen_gen = max(160, min(3840, int(kam.get("genislik") or 960)))
        except (TypeError, ValueError):
            istenen_gen = 960
        with self._kilit:
            y = self.yayinlar.get(kamera_id)
            if y and (not y.calisiyor or y.url != url
                      or getattr(y, "fps", 15) != istenen_fps
                      or getattr(y, "genislik", 960) != istenen_gen):
                y.durdur()
                y = None
            if y is None:
                y = _Yayin(kamera_id, url, fiili_protokol,
                           self.konsol, anotasyon=self.anotasyon,
                           fps=istenen_fps, genislik=istenen_gen)
                if not y.baslat():
                    self._son_hatalar[int(kamera_id)] = (
                        y.hata or "kaynak baslatilamadi")
                    return None
                self._son_hatalar.pop(int(kamera_id), None)
                self.yayinlar[kamera_id] = y
                # v2.4.204: adreste kimlik varsa gunluge MASKELI yazilir.
                import re as _re
                self.konsol("[VIDEO] Kaynak acildi (kamera %s): %s"
                            % (kamera_id, _re.sub(r"//[^/@]+@", "//***:***@", str(url))))
            return y

    def _hata_yaz(self, kamera_id, gerekce):
        with self._kilit:
            self._son_hatalar[int(kamera_id)] = gerekce

    def yayin_durdur(self, kamera_id):
        with self._kilit:
            y = self.yayinlar.pop(kamera_id, None)
        if y:
            y.durdur()
            self.konsol("[VIDEO] Kaynak durduruldu (kamera %s)" % kamera_id)

    def hepsini_durdur(self):
        with self._kilit:
            yayinlar = list(self.yayinlar.values())
            self.yayinlar.clear()
        for y in yayinlar:
            y.durdur()

    # ------------------------------------------------------------------
    def calistir(self):
        """HTTP sunucusunu (bloklayarak) calistirir; thread'de kosulur."""
        proxy = self

        class Istek(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a, **k):
                pass

            def do_GET(self):
                yol = self.path.split("?")[0].strip("/")
                parcalar = yol.split("/")
                if len(parcalar) == 2 and parcalar[0] == "kamera":
                    try:
                        kid = int(parcalar[1])
                    except ValueError:
                        self.send_error(404)
                        return
                    self._mjpeg(kid)
                    return
                self.send_error(404)

            def _gerekce_yaz(self, kod, gerekce):
                """503/404 yanitini MAKINE OKUNABILIR gerekceyle dondurur.

                v2.4.34 — NEDEN: onceki surumde tum basarisizliklar
                istemciye ayni genel hatayla gidiyordu; tarayici yalnizca
                "YAYIN ALINAMIYOR" gosteriyordu. Kullanici bir saatini
                ffmpeg'in kurulu olmadigini bulmaya harcadi — oysa proxy
                bunu `_Yayin.hata` alaninda BILIYORDU. Artik gerekce JSON
                govdesinde ve `X-Goktungu-Hata` basliginda dondurulur;
                istemci bunu okuyup kutuya net metin yazar.
                """
                govde = json.dumps({"hata": gerekce}).encode("utf-8")
                try:
                    self.send_response(kod)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(govde)))
                    self.send_header("X-Goktungu-Hata", gerekce)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header(
                        "Access-Control-Expose-Headers", "X-Goktungu-Hata")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    self.wfile.write(govde)
                except Exception:
                    pass

            def _mjpeg(self, kid):
                y = proxy.yayin_al(kid)
                if y is None:
                    gerekce = proxy.son_hata(kid) or "kaynak acilamadi"
                    self._gerekce_yaz(503, gerekce)
                    proxy.konsol("[VIDEO] Kamera %s acilamadi: %s"
                                 % (kid, gerekce))
                    return
                # v2.4.33: ILK KARE BEKLENIR, SONRA 200 YAZILIR
                # ----------------------------------------------------
                # Onceki surumde basliklar hemen yazilip govde 3-7 sn
                # bos kaliyordu (uzak MJPEG kaynaklarinda ffmpeg'in ilk
                # kare gecikmesi). Tarayici bos govdeli multipart
                # yanitinda <img> icin `error` atesliyor ve kutu kalici
                # olarak "YAYIN ALINAMIYOR" durumunda kaliyordu.
                #
                # Artik ilk kare beklenir:
                #  - kare geldiyse 200 + multipart akisi
                #  - gelmediyse 503 + ffmpeg'in gercek hata metni
                # Boylece istemci ya goruntu ya da net bir gerekce alir.
                y.izleyici_ekle()
                if not y.ilk_kare_bekle(12.0):
                    y.izleyici_cikar()
                    gerekce = y.hata or "kaynak kare uretmedi (zaman asimi)"
                    self._gerekce_yaz(503, gerekce)
                    # NOT: VideoProxy.konsol her zaman cagrilabilir
                    # (varsayilan no-op lambda), kontrol gereksiz.
                    proxy.konsol(
                        "[VIDEO] Kamera %s yayin alinamadi: %s"
                        % (kid, gerekce))
                    return
                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "multipart/x-mixed-replace; boundary=goktunguframe")
                self.send_header("Cache-Control", "no-cache, private")
                self.send_header("Pragma", "no-cache")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Connection", "close")
                self.end_headers()
                son_no = 0
                try:
                    baslangic = time.time()
                    while y.calisiyor or y.son_kare:
                        with y.kosul:
                            if y.kare_no == son_no:
                                y.kosul.wait(timeout=2.0)
                            kare = y.son_kare
                            no = y.kare_no
                        if kare is None:
                            # Kaynak henuz kare uretmedi
                            if not y.calisiyor:
                                break
                            if time.time() - baslangic > 15:
                                break   # 15 sn'de kare yoksa vazgec
                            continue
                        if no == son_no:
                            if not y.calisiyor:
                                break
                            continue
                        son_no = no
                        self.wfile.write(
                            SINIR + b"\r\n"
                            b"Content-Type: image/jpeg\r\n"
                            b"Content-Length: " +
                            str(len(kare)).encode() + b"\r\n\r\n")
                        self.wfile.write(kare)
                        self.wfile.write(b"\r\n")
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    y.izleyici_cikar()

        class Sunucu(socketserver.ThreadingTCPServer):
            allow_reuse_address = True
            daemon_threads = True

        # Canlı yayın güncel Merkez HTTP sunucusunun `/kamera/<id>`
        # yolundan verilir. Ayrı 8801 dinleyicisi; port çakışması, HTTPS
        # karma içerik ve offline kurulumda gereksiz güvenlik yüzeyi yarattığı
        # için açılmaz. Yukarıdaki eski istek sınıfı paket uyumluluğu için
        # korunur; ortak yayın gövdesi aşağıdaki `mjpeg_yaz`dadır.
        self.konsol("[VIDEO] Canli kamera yayini ayni-origin HTTP yolunda hazir.")
        return None


def mjpeg_gerekce_yaz(istek, kod, gerekce):
    """Canlı yayın hatasını güvenli, makine-okunabilir HTTP yanıtıyla yazar."""
    metin = str(gerekce or "kaynak acilamadi").replace("\r", " ").replace("\n", " ")[:400]
    govde = json.dumps({"hata": metin}, ensure_ascii=False).encode("utf-8")
    # v2.4.167 OLCULEN KUSUR: HTTP basliklari latin-1 ile kodlanir; gerekce
    # "—" gibi bir karakter tasiyinca send_header UnicodeEncodeError firlatir
    # ve istemciye HICBIR gerekce ulasmazdi (bos "YAYIN ALINAMIYOR").
    metin = metin.encode("latin-1", "replace").decode("latin-1")
    try:
        istek.send_response(int(kod))
        istek.send_header("Content-Type", "application/json; charset=utf-8")
        istek.send_header("Content-Length", str(len(govde)))
        istek.send_header("X-Goktungu-Hata", metin)
        istek.send_header("Cache-Control", "no-store")
        istek.send_header("Connection", "close")
        istek.end_headers()
        istek.wfile.write(govde)
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass


def mjpeg_yaz(istek, kamera_id, proxy, gunluk=print):
    """`/kamera/<id>` için tek kaynak/fan-out MJPEG gövdesini yazar.

    Bu yordam hem offline Merkez hem de merkezi HTTP vekili tarafından
    kullanılır. Başlık, yalnız ilk kare üretildikten sonra yazılır; böylece
    istemci boş akışı canlı yayın sanmaz. Kaynak veya izleyici hatası başka
    kamera yayınlarını etkilemez.
    """
    try:
        kid = int(kamera_id)
    except (TypeError, ValueError):
        mjpeg_gerekce_yaz(istek, 404, "gecersiz kamera kimligi")
        return
    y = proxy.yayin_al(kid)
    # v2.5.25 KRITIK: Bu istek uzun ömürlü bir MJPEG akış iş parçacığıdır.
    # `yayin_al` -> `kameralar.bul` DB'ye dokunur ve bu iş parçacığına havuzdan
    # bir bağlantı ödünç verir; akış boyunca (dakikalar) elde tutulursa havuz
    # (HAVUZ_MAKS=10) birkaç kamerada/AI işçisinde dolar ve sunucu çöker
    # ("PostgreSQL baglanti havuzu dolu"). Bundan sonra DB'ye dokunulmadığı
    # için bağlantıyı HEMEN havuza iade et.
    try:
        from . import veritabani as _vt
        _vt.baglanti_kapat()
    except Exception:
        pass
    if y is None:
        gerekce = proxy.son_hata(kid) or "kaynak acilamadi"
        mjpeg_gerekce_yaz(istek, 503, gerekce)
        try:
            gunluk("[VIDEO] Kamera %s acilamadi: %s" % (kid, gerekce))
        except Exception:
            pass
        return
    y.izleyici_ekle()
    try:
        if not y.ilk_kare_bekle(12.0):
            gerekce = y.hata or "kaynak kare uretmedi (zaman asimi)"
            mjpeg_gerekce_yaz(istek, 503, gerekce)
            try:
                gunluk("[VIDEO] Kamera %s yayin alinamadi: %s" % (kid, gerekce))
            except Exception:
                pass
            return
        istek.send_response(200)
        istek.send_header("Content-Type", "multipart/x-mixed-replace; boundary=goktunguframe")
        istek.send_header("Cache-Control", "no-store, private")
        istek.send_header("Pragma", "no-cache")
        istek.send_header("Connection", "close")
        istek.end_headers()
        son_no = 0
        baslangic = time.time()
        while y.calisiyor or y.son_kare:
            with y.kosul:
                if y.kare_no == son_no:
                    y.kosul.wait(timeout=2.0)
                kare = y.son_kare
                no = y.kare_no
            if kare is None:
                if not y.calisiyor or time.time() - baslangic > 15.0:
                    break
                continue
            if no == son_no:
                if not y.calisiyor:
                    break
                continue
            son_no = no
            istek.wfile.write(
                SINIR + b"\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(kare)).encode() + b"\r\n\r\n")
            istek.wfile.write(kare)
            istek.wfile.write(b"\r\n")
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass
    finally:
        y.izleyici_cikar()


def mjpeg_sunucusu_kos(*_args, **_kwargs):
    """Eski çağrılar için uyumluluk kancası; ayrı HTTP dinleyicisi açılmaz."""
    return None


def cihaz_listesi(en_fazla=6):
    """Yerel kamera cihazlarını güvenli sınırla listeler."""
    return VideoProxy.cihaz_listesi(en_fazla)
