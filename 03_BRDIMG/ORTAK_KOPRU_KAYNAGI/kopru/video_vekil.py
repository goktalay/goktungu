# -*- coding: utf-8 -*-
"""KOPRU YAZILIMI - VIDEO VEKILI (MERKEZDEN TASINDI).

RTSP/RTP/MJPEG/HTTP/USB kaynaklarini FFmpeg (veya OpenCV) ile MJPEG'e
cevirip HTTP uzerinden sunar.

    GET /kamera/<id>  ->  multipart/x-mixed-replace MJPEG akisi

Ayni kaynak icin tek FFmpeg sureci calisir; kareyi son alan tum HTTP
istemcilerine dagitan basit bir fan-out yapisi vardir. Hicbir izleyici
kalmadiginda surec otomatik sonlandirilir (30 sn bekleme sonrasi).

## NEDEN MERKEZDE DEGIL KOPRUDE

Kullanicinin kamerasi SAHADAKI yerel agda durur (ornegin 192.168.1.50)
ya da dogrudan USB ile saha bilgisayarina takilidir. Merkez sunucu bir
veri merkezindedir: ne o ozel ag adresine ne de USB aygitina erisebilir.
Akisi merkezde acmak tanim geregi basarisizdir.

Onceki surumde bu modul MERKEZDE kosuyordu ve yalnizca genel internete
acik kameralar calisiyordu (kullanicinin ekledigi 97.76.27.170 adresinin
gelmesi bu yuzdendi); saha agindaki ve USB kameralar hicbir zaman
gelmedi.

## BU DOSYA TASINDI, YENIDEN YAZILMADI

Kaynak: merkezdeki `goktungu/video_proxy.py`. Kanitlanmis kod (ilk kare
bekleme, ffmpeg secenekleri, hata gerekcesi iletimi, fan-out) korunur.
Radar protokolu tasinirken izlenen yol ile aynidir: sahada calismasi
gereken kod yeniden yazilmaz, tasinir.

## MERKEZDEKI SURUMDEN TEK ANLAMLI FARK

Merkezde kamera kayitlari veritabanindan okunuyordu
(`self.kameralar.bul(id)`). Sahada veritabani YOKTUR; kayitlar merkezden
komut kanaliyla gelir ve `KameraDefteri` adli bellek ici sozlukte
tutulur. `bul()` arayuzu ayni birakildigi icin `_Yayin` ve HTTP katmani
HIC degismedi.

## OPENCV ISTEGE BAGLIDIR

`cv2` bulunmazsa modul YINE calisir: ffmpeg yolu (RTSP/MJPEG/HTTP/HLS)
tamamen islevseldir. OpenCV yalnizca USB/DONANIM kamera yakalama ve AI
tespit kutularinin kare uzerine cizilmesi icin gereklidir. Bu yuzden
eksikligi HATA degil EKSIK YETENEK olarak bildirilir; kullaniciya
kurulum komutu yazilir.
"""
import http.server
import json
import socketserver
import subprocess
import threading
import time

from . import arac_bul

try:
    import cv2
    import numpy as np
except ImportError:          # anotasyon/donanim istege bagli
    cv2 = None
    np = None

VIDEO_PROXY_PORT = 8801

# Tespit turu -> cerceve rengi (BGR)
_TUR_RENK = {
    "yuz": (80, 200, 60),
    "plaka": (60, 170, 255),
    "insan": (60, 120, 255),
    "hava_araci": (255, 120, 60),
    "kara_araci": (60, 220, 220),
    "takip": (0, 60, 255),
}

_TUR_AD = {
    "yuz": "KISI",
    "plaka": "PLAKA",
    "insan": "INSAN",
    "hava_araci": "HAVA ARACI",
    "kara_araci": "KARA ARACI",
    "takip": "TAKIP",
}


class KameraDefteri:
    """Merkezden bildirilen kamera kayitlarini bellekte tutar.

    ## NEDEN VERITABANI DEGIL

    Merkezdeki surum kamera kaydini PostgreSQL'den okuyordu. Kopru saha
    makinesinde kosar ve orada veritabani yoktur; olmasi da istenmez
    (kayitlarin tek dogruluk kaynagi merkezdir, sahada ikinci bir kopya
    tutmak iki kaydin ayrismasina yol acar).

    Bu yuzden defter YALNIZCA merkezin bildirdigi kayitlari yansitir.
    Servis yeniden basladiginda bos baslar; merkez akis istedigi anda
    kaydi komutla birlikte gonderir. Boylece "sahada eski kamera kaydi
    kaldi" durumu hic olusmaz.
    """

    def __init__(self):
        self._veri = {}
        self._kilit = threading.Lock()

    def yaz(self, kayit):
        """Tek kamera kaydini ekler/guenceller. Doner: normalize kayit."""
        if not isinstance(kayit, dict):
            return None
        try:
            kid = int(kayit.get("id"))
        except (TypeError, ValueError):
            return None
        k = {
            "id": kid,
            "isim": str(kayit.get("isim") or ""),
            "protokol": str(kayit.get("protokol") or "").lower(),
            "url": str(kayit.get("url") or ""),
            "ai_gorevler": str(kayit.get("ai_gorevler") or ""),
        }
        with self._kilit:
            self._veri[kid] = k
        return dict(k)

    def bul(self, kamera_id):
        try:
            kid = int(kamera_id)
        except (TypeError, ValueError):
            return None
        with self._kilit:
            k = self._veri.get(kid)
            return dict(k) if k else None

    def sil(self, kamera_id):
        try:
            kid = int(kamera_id)
        except (TypeError, ValueError):
            return False
        with self._kilit:
            return self._veri.pop(kid, None) is not None

    def listele(self):
        with self._kilit:
            return [dict(v) for v in self._veri.values()]


class AnotasyonDeposu:
    """AI iscilerinden gelen canli tespit kutularini tutar.

    Kutular kamera bazinda saklanir; belirli bir suredir yenilenmeyen
    kutular gecersiz sayilir (akista donuk kalmamalari icin).
    """

    GECERLILIK_SN = 1.5

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
                cv2.rectangle(kare, (x, y), (x + w, y + h), renk, 2)
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
                 anotasyon=None):
        self.kamera_id = kamera_id
        self.url = url
        self.protokol = protokol
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
                # v2.1.0: "opencv kurulu degil" metni istemciye
                # ulasiyordu ama NE YAPILACAGINI soylemiyordu. Servis
                # kendi Python'uyla kosar; kullanicinin baska bir
                # Python'a kurmasi sorunu cozmez.
                self.hata = arac_bul.eksik_arac_ozeti("opencv")
                return False
            self.calisiyor = True
            self.hata = None
            threading.Thread(target=self._oku_opencv, daemon=True).start()
            threading.Thread(target=self._bekci, daemon=True).start()
            return True
        # v2.1.0: cıplak "ffmpeg" adi PATH'e baglidir; kopru Windows'ta
        # LocalSystem hesabiyla servis olarak kostugu icin kullanicinin
        # winget ile kurdugu ffmpeg o PATH'te GORUNMEZ. arac_bul yaygin
        # kurulum konumlarini da tarar ve tam yolu dondurur.
        cmd = [arac_bul.ffmpeg_komutu(), "-hide_banner",
               "-loglevel", "error"]
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
        if self.protokol in ("http", "hls"):
            cmd += ["-re", "-stream_loop", "-1"]
        else:
            # Dusuk gecikme secenekleri (canli kaynaklar)
            cmd += ["-fflags", "nobuffer", "-flags", "low_delay"]
        cmd += ["-i", self.url,
                "-an",                       # ses yok
                "-vf", "scale='min(960,iw)':-2",  # bant genisligi icin sinirla
                "-q:v", "7",
                "-r", "15",
                "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1"]
        try:
            self.surec = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                bufsize=0)
        except FileNotFoundError:
            # v2.4.34: eyleme donuk metin. Onceki "ffmpeg bulunamadi"
            # istemciye HIC ulasmiyordu; artik ulasiyor, dolayisiyla
            # kullanicinin ne yapacagini da soylemesi gerekiyor.
            # v2.1.0: platforma UYGUN komut yazilir; ayrica servis
            # kipinde "kurulu ama servis gormuyor" ayrimi yapilir --
            # kullaniciyi zaten kurdugu paketi tekrar kurmaya
            # yonlendirmek yanlis teshise gotururdu.
            self.hata = arac_bul.eksik_arac_ozeti("ffmpeg")
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
            # 15 fps sinirla
            simdi = time.time()
            if simdi - onceki < 1.0 / 15:
                continue
            onceki = simdi
            okk, jpg = cv2.imencode(".jpg", kare,
                                    [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not okk:
                continue
            self._kare_yayinla(jpg.tobytes())
        cap.release()
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

    def __init__(self, kameralar=None, konsol=None, port=VIDEO_PROXY_PORT):
        # Sahada kamera kayitlari merkezden gelir; varsayilan olarak bos
        # bir defter kurulur (bkz. KameraDefteri).
        self.kameralar = (kameralar if kameralar is not None
                          else KameraDefteri())
        self.konsol = konsol or (lambda *a: None)
        self.port = port
        self.yayinlar = {}          # kamera_id -> _Yayin
        self._kilit = threading.Lock()
        self.dji_kopru = None       # v2.1.8: main.py baglar
        self.anotasyon = AnotasyonDeposu()  # v2.4.7: AI tespit kutulari
        # v2.4.34: kamera_id -> son basarisizlik gerekcesi (istemciye iletilir)
        self._son_hatalar = {}

    # ------------------------------------------------------------------
    @staticmethod
    def cihaz_listesi(en_fazla=6):
        """BU MAKINEDEKI yerel kamera cihazlarini tarar.

        ## NEDEN SAHADA TARANIR

        Merkezdeki surum ayni islevi merkez sunucuda kosuyordu ve oradaki
        yorum da bunu aciktan soyluyordu ("Sunucu makinesindeki yerel
        kamera cihazlarini tarar"). Merkez sunucuda kamera aygiti YOKTUR;
        liste her zaman BOS donuyordu. Operator, cantasina ya da saha
        bilgisayarina takili USB kamerayi listede hic goremiyordu.

        Tarama artik kopru makinesinde yapilir; yani aygitin gercekten
        bulundugu yerde.
        """
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

    @staticmethod
    def opencv_var():
        """USB/DONANIM kamera ve anotasyon cizimi icin OpenCV var mi."""
        return cv2 is not None

    def _url_coz(self, kam):
        """Kamera kaydinin gercek akis URL'sini dondurur.

        'dji' protokolunde url 'dji:<sysid>' bicimindedir; gercek MJPEG
        adresi Android kopru uygulamasinin bildirdigi video_url'dir.
        """
        url = kam["url"]
        if kam.get("protokol") == "dji" and self.dji_kopru:
            try:
                sysid = int(str(url).split(":", 1)[1])
            except (IndexError, ValueError):
                return None
            gercek = self.dji_kopru.video_url(sysid)
            return gercek or None
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
            self._hata_yaz(
                kamera_id,
                "DJI kopru henuz video adresi bildirmedi"
                if kam.get("protokol") == "dji" else "kaynak adresi bos")
            return None
        with self._kilit:
            y = self.yayinlar.get(kamera_id)
            if y and (not y.calisiyor or y.url != url):
                y.durdur()
                y = None
            if y is None:
                y = _Yayin(kamera_id, url, kam["protokol"],
                           self.konsol, anotasyon=self.anotasyon)
                if not y.baslat():
                    self._son_hatalar[int(kamera_id)] = (
                        y.hata or "kaynak baslatilamadi")
                    return None
                self._son_hatalar.pop(int(kamera_id), None)
                self.yayinlar[kamera_id] = y
                self.konsol("[VIDEO] Kaynak acildi (kamera %s): %s"
                            % (kamera_id, url))
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

        with Sunucu(("0.0.0.0", self.port), Istek) as srv:
            self.konsol("[VIDEO] MJPEG proxy sunucusu basladi (port %s)"
                        % self.port)
            srv.serve_forever()
