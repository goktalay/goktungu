# -*- coding: utf-8 -*-
"""GOKTUNGU AI Islem Sunucusu (bagimsiz isci sureci).

Windows/Linux uzerinde CPU ile calisan goruntu isleme iscisidir.
NVIDIA tabanli sunucular (or. ASUS Ascent GX10) ayni HTTP API'yi
uygulayarak sisteme eklenir; GCS ana sunucusu yuke gore gorevleri
iscilere dagitir.

Calistirma:
    python ai_sunucu.py --port 8900 --ana http://127.0.0.1:8000

HTTP JSON API:
    GET  /durum   -> {ad, tip, yuk, kapasite, akislar: [...]}
    POST /izle    -> {kamera_id, url, protokol} akisi isleme al
    POST /durdur  -> {kamera_id} akisi birak
    POST /embed   -> {foto_b64} tek karede yuz embeddingi hesapla

Tespit bildirimi: ana sunucuya HTTP POST /ai/tespit (JSON).
Kayitlar: ai_kayitlar/YYYYMMDD/ altina JPEG + MP4 (3 sn klip).
"""
import argparse
import base64
import collections
import json
import re
import os
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import numpy as np
except ImportError:
    raise SystemExit(
        "numpy gerekli: pip install numpy\n"
        "(Ubuntu 23.04+: pip3 install --break-system-packages numpy)")

try:
    import cv2
except ImportError:
    raise SystemExit(
        "OpenCV gerekli: pip install opencv-python-headless\n"
        "(Ubuntu 23.04+: pip3 install --break-system-packages"
        " opencv-python-headless)")

# v2.4.170: ONNX Runtime istege bagli — varsa YOLO cikarimi onunla yapilir.
# Windows'ta onnxruntime-directml paketi TUM DX12 GPU'larda (NVIDIA/AMD/
# Intel) donanim hizlandirmasi verir; CUDA kurulumu gerekmez. Yoksa
# cv2.dnn (CPU) yoluna dusulur.
try:
    import onnxruntime as _ort
except ImportError:
    _ort = None

# v2.4.52: klasor yapisi degisti. Bu betik artik `assets/python/`
# altinda durur, ancak modelleri ve kayitlari PROJE KOKUNDEKI `veri/`
# dizininde arar. Kendi dizinini kok saymak SESSIZ bir kusur uretirdi:
# modeller `assets/python/ai_modeller` altinda aranir, bulunamayinca
# otomatik indirme tetiklenir ve kullanicinin mevcut modelleri
# yok sayilir (yuz/plaka tespiti calismaz veya bant tuketir).
_BU_DIZIN = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(_BU_DIZIN) == "python" and \
        os.path.basename(os.path.dirname(_BU_DIZIN)) == "assets":
    # YENI yapi: <kok>/assets/python/ai_sunucu.py
    KOK = os.path.dirname(os.path.dirname(_BU_DIZIN))
    _VERI = os.path.join(KOK, "veri")
else:
    # ESKI duz yapi: <kok>/ai_sunucu.py
    KOK = _BU_DIZIN
    _VERI = KOK


def _ai_yolu(ad):
    """`veri/<ad>` dondurur; yoksa eski konuma (`<kok>/<ad>`) duser."""
    yeni = os.path.join(_VERI, ad)
    if _VERI != KOK and not os.path.isdir(yeni):
        eski = os.path.join(KOK, ad)
        if os.path.isdir(eski):
            return eski
    return yeni


# v2.4.162: Kod ozeti — Merkez, calisan iscinin diskteki ai_sunucu.py ile
# ayni kodu calistirip calistirmadigini bununla anlar. Guncellemeden sonra
# eski kodla kalan (ayri oturumda yasayan) isci boylece yenilenir.
def _kod_ozeti():
    import hashlib as _h
    try:
        with open(os.path.abspath(__file__), "rb") as _f:
            return _h.sha256(_f.read()).hexdigest()
    except OSError:
        return ""


KOD_OZETI = _kod_ozeti()

MODEL_KLASORU = _ai_yolu("ai_modeller")
KAYIT_KLASORU = _ai_yolu("ai_kayitlar")

# v2.4.153: Kurulumda (Windows servisi / Linux systemd) program dizini
# YAZMAYA KAPALIDIR; veri koku GOKTUNGU_VERI_KOKU ile verilir. Kayitlar
# daima oraya yazilir. Modeller once veri kokunde aranir (kullanici
# guncel model koyabilsin), yoksa paketle gelen salt-okunur dizin kullanilir.
_KURULUM_VERI = (os.environ.get("GOKTUNGU_VERI_KOKU") or "").strip()
if _KURULUM_VERI:
    KAYIT_KLASORU = os.path.join(_KURULUM_VERI, "ai_kayitlar")
    if os.path.isdir(os.path.join(_KURULUM_VERI, "ai_modeller")):
        MODEL_KLASORU = os.path.join(_KURULUM_VERI, "ai_modeller")

# v2.4.168: Istege bagli YOLO ONNX hava araci modeli. Bu dosya varsa
# hava_araci tespiti MOG2 (hareket) yerine gercek nesne tanima modeliyle
# yapilir — hareketli kamera goruntusunde de calisir. Tek sinifli
# (drone) veya cok sinifli YOLOv5/8 ONNX ciktisi desteklenir.
YOLO_HAVA = os.path.join(MODEL_KLASORU, "hava_araci.onnx")

YUNET = os.path.join(MODEL_KLASORU, "face_detection_yunet_2023mar.onnx")
SFACE = os.path.join(MODEL_KLASORU, "face_recognition_sface_2021dec.onnx")
PLAKA_CASCADE = os.path.join(MODEL_KLASORU,
                             "haarcascade_russian_plate_number.xml")

# v2.4.5: Model dosyalari eksik/bozuksa resmi opencv_zoo deposundan
# otomatik indirilir (OneDrive placeholder / eksik zip cikarma durumlari).
MODEL_KAYNAKLARI = {
    YUNET: (
        "https://github.com/opencv/opencv_zoo/raw/main/models/"
        "face_detection_yunet/face_detection_yunet_2023mar.onnx",
        200000),   # beklenen asgari boyut (bayt)
    SFACE: (
        "https://github.com/opencv/opencv_zoo/raw/main/models/"
        "face_recognition_sface/face_recognition_sface_2021dec.onnx",
        35000000),
}


def model_indir(yol):
    """Model dosyasini resmi kaynaktan indirir; basariliysa True."""
    kaynak = MODEL_KAYNAKLARI.get(yol)
    if not kaynak:
        return False
    url, asgari = kaynak
    try:
        import urllib.request
        print(f"[AI] Model indiriliyor: {os.path.basename(yol)} ...")
        os.makedirs(MODEL_KLASORU, exist_ok=True)
        gecici = yol + ".indiriliyor"
        try:
            urllib.request.urlretrieve(url, gecici)
        except Exception as ssl_hata:
            # v2.4.6: Windows kurumsal ag / SSL sertifika sorunlarinda
            # dogrulamasiz ikinci deneme
            import ssl
            print(f"[AI] Indirme hatasi ({ssl_hata}); SSL dogrulamasiz"
                  " tekrar deneniyor...")
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(url, context=ctx,
                                        timeout=120) as kaynak_f, \
                    open(gecici, "wb") as hedef_f:
                while True:
                    parca = kaynak_f.read(1024 * 256)
                    if not parca:
                        break
                    hedef_f.write(parca)
        if os.path.getsize(gecici) < asgari:
            os.remove(gecici)
            print(f"[AI] Indirilen dosya eksik gorunuyor: {yol}")
            return False
        if os.path.exists(yol):
            os.remove(yol)
        os.rename(gecici, yol)
        print(f"[AI] Model indirildi: {os.path.basename(yol)} "
              f"({os.path.getsize(yol)} bayt)")
        return True
    except Exception as e:
        print(f"[AI] Model indirilemedi ({os.path.basename(yol)}): {e}")
        return False


def model_yukle(yol, yukleyici, adi):
    """Modeli yukler; bozuksa yeniden indirip dener; olmazsa None.

    OneDrive 'yalnizca bulutta' placeholder dosyalari ve yarim zip
    cikarma durumlarinda dosya diskte gorunur ama okunamaz — bu
    durumda islem coker(di). Artik hata yakalanir, dosya yeniden
    indirilir, yine olmazsa ilgili gorev devre disi kalir ve isci
    diger gorevlerle calismaya devam eder.
    """
    if not os.path.exists(yol):
        if not model_indir(yol):
            print(f"[AI] Uyari: {adi} modeli yok — gorev devre disi.")
            return None
    try:
        return yukleyici(yol)
    except Exception as e:
        print(f"[AI] {adi} modeli okunamadi ({e}); yeniden indiriliyor...")
        if model_indir(yol):
            try:
                return yukleyici(yol)
            except Exception as e2:
                print(f"[AI] {adi} modeli indirme sonrasi da okunamadi: {e2}")
        print(f"[AI] Uyari: {adi} devre disi — diger gorevler calisir.")
        return None

# Plaka OCR: pytesseract varsa kullanilir, yoksa tespit-yalniz calisir
try:
    import pytesseract
    OCR_VAR = True
except ImportError:
    OCR_VAR = False
# GRCOFF pasif yerel görüntü işleme kabul listesi.
# v2.4.165: Sistem C-UAS (Karşı-İHA) odaklıdır; yalnız hava araçları tespit
# edilir ve angaje olunur. İnsan/yüz/kara aracı tespiti kaldırıldı.
IZINLI_SINIFLAR = frozenset(("hava_araci",))

# v2.4.169: Hava araci ALT SINIFLARI (yalniz cok sinifli YOLO modeliyle
# anlamli). Her biri ayri ac/kapat (gorev) + hassasiyet tasir. Takip ve
# angajman icin tur DAIMA "hava_araci"dir; alt sinif yalniz tespit
# suzgeci ve etikettir. KURAL: gorevlerde hic alt sinif yoksa TUM
# siniflar acik sayilir (tek sinifli model / eski kayit uyumu); en az
# bir alt sinif varsa yalniz secililer tespit edilir.
ALT_SINIFLAR = frozenset(("drone", "ucak", "helikopter", "kus"))

# Model sinif adi -> kanonik alt sinif anahtari ("_yok" = daima atla).
_SINIF_ESLE = (
    ("background", "_yok"), ("arkaplan", "_yok"),
    ("drone", "drone"), ("iha", "drone"), ("uav", "drone"),
    ("copter", "drone"), ("quad", "drone"), ("shahed", "drone"),
    ("airplane", "ucak"), ("plane", "ucak"), ("ucak", "ucak"),
    ("jet", "ucak"), ("aircraft", "ucak"), ("fixed", "ucak"),
    ("helicopter", "helikopter"), ("heli", "helikopter"),
    ("bird", "kus"), ("kus", "kus"),
)


def sinif_anahtari(ad):
    a = str(ad or "").strip().lower()
    for parca, anahtar in _SINIF_ESLE:
        if parca in a:
            return anahtar
    return ""


def gorevleri_sinirla(gorevler):
    gecerli = IZINLI_SINIFLAR | ALT_SINIFLAR
    if gorevler is None:
        return set(IZINLI_SINIFLAR)
    if isinstance(gorevler, str):
        gorevler = gorevler.replace(";", ",").split(",")
    return {str(g).strip().lower() for g in (gorevler or [])
            if str(g).strip().lower() in gecerli}


# v2.5.24: Sınıf başına hassasiyet. UI 10..90; 50 = mevcut davranış.
# k = 50/s -> alan/eşik ölçeği; s=50 iken k=1.0 (regresyon yok).
_HASSAS_VARSAYILAN = 50
def hassasiyet_coz(deger):
    """Dict/JSON -> {sinif: 10..90}. Eksik alan varsayılan 50."""
    if isinstance(deger, str):
        try:
            deger = json.loads(deger) if deger.strip() else {}
        except (ValueError, TypeError):
            deger = {}
    out = {}
    for k in IZINLI_SINIFLAR | ALT_SINIFLAR:
        try:
            v = int(round(float((deger or {}).get(k))))
        except (TypeError, ValueError):
            v = _HASSAS_VARSAYILAN
        out[k] = min(90, max(10, v))
    return out


def takip_ayar_coz(deger):
    """v2.4.173: ai_hassasiyet JSON'undan takip ayarlari.

    takip_yontem: "csrt" (hassas, varsayilan) / "kcf" (hizli) / "mil"
    takip_tolerans: hedef kaybolunca takibin birakildigi sure (sn, 1-30)
    """
    if isinstance(deger, str):
        try:
            deger = json.loads(deger) if deger.strip() else {}
        except (ValueError, TypeError):
            deger = {}
    d = deger or {}
    yontem = str(d.get("takip_yontem") or "").lower()
    if yontem not in ("csrt", "kcf", "mil"):
        yontem = ""
    try:
        tol = float(d.get("takip_tolerans"))
    except (TypeError, ValueError):
        tol = 5.0
    return {"yontem": yontem, "tolerans_sn": min(30.0, max(1.0, tol))}


class AkisIsleyici(threading.Thread):
    """Tek kamera akisini okuyan ve tespit yapan is parcacigi."""

    def __init__(self, isci, kamera_id, url, protokol, gorevler=None,
                 hassasiyet=None):
        super().__init__(daemon=True)
        self.isci = isci
        self.kamera_id = int(kamera_id)
        self.url = url
        self.protokol = protokol
        # GRCOFF 2.5.20: yalnız insan, kara_araci, hava_araci.
        # Boş görev listesi varsayılan olarak bu üç sınıfı kullanır.
        self.gorevler = gorevleri_sinirla(gorevler)
        self.hassasiyet = hassasiyet_coz(hassasiyet)
        self.takip_ayar = takip_ayar_coz(hassasiyet)
        # sınıf ölçeği: s=50 -> 1.0 (nötr). Daha yüksek s -> daha küçük k.
        self._olcek = {k: (50.0 / max(10, v)) for k, v in self.hassasiyet.items()}
        # hareket tespiti icin arka plan cikarici (hava/kara araci)
        self.arka_plan = None
        self.calisiyor = True
        self.son_kare_ts = 0.0
        self.hata = ""
        # 3 saniyelik halka tampon (kare, ts) — fps tahminiyle boyutlanir
        self.tampon = collections.deque(maxlen=90)
        # ayni kisi/plakayi tekrar tekrar bildirmemek icin sogutma
        self._sogutma = {}   # anahtar -> son bildirim ts
        # v2.4.2: hedef takibi (tracking) — angajman icin
        self.takip = None        # {tur, kutu[x,y,w,h], tracker, son_ts}
        self.takip_kilit = threading.Lock()

    def durdur(self):
        self.calisiyor = False

    def video_fps(self):
        """Halka tampondan olculen gercek video kare hizi."""
        try:
            k = list(self.tampon)
            if len(k) >= 2:
                sure = k[-1][1] - k[0][1]
                if sure > 0.2:
                    return (len(k) - 1) / sure
        except Exception:
            pass
        return 0.0

    # ------------------------------------------------------------------
    def run(self):
        while self.calisiyor:
            try:
                self._akisi_isle()
            except Exception as e:
                self.hata = str(e)[:200]
            if self.calisiyor:
                time.sleep(3.0)   # kopan akisa yeniden baglanma araligi

    def _url_coz(self):
        """v2.4.7: 'gcs_proxy' protokolunde akis, ana sunucunun MJPEG
        proxy'sinden (port 8801) okunur — webcam/DONANIM dahil tum
        kaynaklar tek yoldan gelir. url '/kamera/<id>' bicimindedir."""
        if self.protokol == "gcs_proxy":
            # v2.4.153: Ayri MJPEG dinleyicisi (8801/8811) guvenlik
            # gerekcesiyle KALDIRILDI (video_proxy.calistir). Canli yayin
            # yalniz Merkez HTTP'nin `/kamera/<id>` yolundadir; isci oraya
            # yerel isci anahtariyla (X-Goktungu-AI-Isci) baglanir.
            # Yol YALNIZ `/kamera/<sayi>` olabilir: aksi halde
            # `@baska-sunucu/...` gibi bir yol, anahtar basligini
            # disaridaki bir sunucuya gonderirdi.
            if not re.fullmatch(r"/kamera/[0-9]{1,9}", str(self.url or "")):
                raise ValueError("gecersiz gcs_proxy yolu")
            return self.isci.ana_url.rstrip("/") + self.url
        return self.url

    def _akisi_isle(self):
        url = self._url_coz()
        if self.protokol == "gcs_proxy":
            # Merkez MJPEG verir; baslik (isci anahtari) gondermek ve
            # Windows'ta FFMPEG'siz OpenCV farklarindan kacinmak icin saf
            # Python MJPEG okuyucu kullanilir.
            self._akisi_isle_mjpeg(url)
            return
        cap = cv2.VideoCapture(url)
        if not cap.isOpened():
            # v2.4.9: bazi Windows OpenCV kurulumlarinda HTTP/MJPEG
            # akislari VideoCapture ile acilamiyor (FFMPEG eksik).
            # Saf-Python MJPEG okuyucu ile devam et.
            try:
                cap.release()
            except Exception:
                pass
            if url.startswith("http"):
                self._akisi_isle_mjpeg(url)
                return
            self.hata = "Akis acilamadi"
            return
        self.hata = ""
        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        if not (1 <= fps <= 120):
            fps = 15.0
        self.tampon = collections.deque(maxlen=int(fps * 3) or 45)
        sayac = 0
        # islem yuku: her N karede bir analiz (CPU dostu)
        analiz_adimi = max(1, int(fps / 5))
        while self.calisiyor:
            ok, kare = cap.read()
            if not ok:
                self.hata = "Akis koptu"
                break
            ts = time.time()
            self.son_kare_ts = ts
            self.tampon.append((kare, ts))
            sayac += 1
            # v2.4.174 OLCULEN KUSUR: CSRT tracker.update() zayif CPU'da
            # 100-500ms surebilir; BURADA (okuma dongusunde) senkron
            # cagrilinca video okuma hizini kendisi bogar (video_fps
            # dustukce takip de kendi kendini yavaslatir - kisir dongu).
            # Takip artik AYRI iplikte, en son kareyi isleyerek surer.
            if self.takip is not None:
                self._takip_kuyrukla(kare, ts)
            # v2.4.175 OLCULEN KUSUR: YOLO tespiti de bu 5Hz orneklemeye
            # (analiz_adimi) tabiydi; GPU cikarimi 100ms altinda bitse
            # bile hedef en fazla ~5 Hz guncelleniyor, hizli ucan hedef
            # "sureksiz takip ediliyor" gibi gorunuyordu. YOLO artik HER
            # karede beslenir; kendi ozel iplik+kuyruk deseni (en TAZE
            # kareyi isler) zaten dogal hiz sinirini kendisi koyar.
            self.isci.kare_yolo_besle(self, kare, ts)
            if sayac % analiz_adimi == 0:
                try:
                    self.isci.kare_analiz(self, kare, ts)
                except Exception as e:
                    self.hata = ("analiz: " + str(e))[:200]
        cap.release()

    def _akisi_isle_mjpeg(self, url):
        """v2.4.9: VideoCapture'siz saf-Python MJPEG okuyucu.
        multipart/x-mixed-replace akisindan JPEG karelerini ayiklar;
        OpenCV'nin FFMPEG destegi olmayan kurulumlarda geri cekilme."""
        basliklar = {"User-Agent": "goktungu-ai"}
        _jeton = os.environ.get("GOKTUNGU_AI_ISCI_JETON") or ""
        if _jeton and self.protokol == "gcs_proxy":
            basliklar["X-Goktungu-AI-Isci"] = _jeton
        istek = urllib.request.Request(url, headers=basliklar)
        try:
            akis = urllib.request.urlopen(istek, timeout=10)
        except Exception as e:
            self.hata = ("Akis acilamadi: " + str(e))[:200]
            return
        self.hata = ""
        fps = 10.0
        self.tampon = collections.deque(maxlen=int(fps * 3))
        tampon = b""
        sayac = 0
        analiz_adimi = max(1, int(fps / 5))
        son_veri_ts = time.time()
        try:
            while self.calisiyor:
                parca = akis.read(16384)
                if not parca:
                    if time.time() - son_veri_ts > 10:
                        self.hata = "Akis koptu"
                        break
                    time.sleep(0.05)
                    continue
                son_veri_ts = time.time()
                tampon += parca
                if len(tampon) > 8 * 1024 * 1024:
                    tampon = tampon[-1024 * 1024:]
                while True:
                    a = tampon.find(b"\xff\xd8")
                    if a < 0:
                        break
                    b = tampon.find(b"\xff\xd9", a + 2)
                    if b < 0:
                        break
                    jpg = tampon[a:b + 2]
                    tampon = tampon[b + 2:]
                    kare = cv2.imdecode(
                        np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
                    if kare is None:
                        continue
                    ts = time.time()
                    self.son_kare_ts = ts
                    self.tampon.append((kare, ts))
                    sayac += 1
                    # v2.4.174: takip AYRI iplikte (bkz. yukarıdaki not)
                    if self.takip is not None:
                        self._takip_kuyrukla(kare, ts)
                    # v2.4.175: YOLO her karede beslenir (bkz. yukarıdaki not)
                    self.isci.kare_yolo_besle(self, kare, ts)
                    if sayac % analiz_adimi == 0:
                        try:
                            self.isci.kare_analiz(self, kare, ts)
                        except Exception as e:
                            self.hata = ("analiz: " + str(e))[:200]
        finally:
            try:
                akis.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Hedef takibi (tracking): angajman destegi
    # ------------------------------------------------------------------
    @staticmethod
    def _tracker_olustur(yontem=""):
        """Kullanilabilir bir OpenCV tracker dondurur (surum uyumlu).

        v2.4.173: `yontem` ("csrt"/"kcf"/"mil") verilirse o once denenir;
        yoksa CSRT (hassas) > KCF (hizli) > MIL sirasi.
        """
        sira = ["TrackerCSRT", "TrackerKCF", "TrackerMIL"]
        istenen = {"csrt": "TrackerCSRT", "kcf": "TrackerKCF",
                   "mil": "TrackerMIL"}.get(str(yontem or "").lower())
        if istenen in sira:
            sira.remove(istenen)
            sira.insert(0, istenen)
        for ad in sira:
            olusturucu = getattr(cv2, ad + "_create", None)
            if olusturucu is None and hasattr(cv2, "legacy"):
                olusturucu = getattr(cv2.legacy, ad + "_create", None)
            if olusturucu is None:
                sinif = getattr(cv2, ad, None)
                if sinif is not None and hasattr(sinif, "create"):
                    olusturucu = sinif.create
            if olusturucu:
                try:
                    return olusturucu(), ad.replace("Tracker", "")
                except Exception:
                    continue
        return None, ""

    def takip_baslat(self, tur, kutu=None, sec_ts=None):
        """Yalnız izinli sınıfta manuel pasif görüntü takibini başlatır.

        v2.4.173 GECIKME DUZELTMESI: `sec_ts` (istemci secim ani; Merkez
        ile ayni makine saati) verilirse kutu, halka tampondaki O ANIN
        karesine oturtulur ve tracker oradan BUGUNE kadar tampondaki
        karelerle "sarilir". Boylece goruntu boru hatti gecikmesi (0.5-2
        sn) yuzunden kutunun hedefin gerisinde baslamasi onlenir.
        """
        tur = str(tur or "").strip().lower()
        if tur not in IZINLI_SINIFLAR:
            return {"tamam": False,
                    "hata": "yalnız hava_araci takip edilebilir (C-UAS modu)"}
        with self.takip_kilit:
            if not self.tampon:
                return {"tamam": False, "hata": "akista kare yok"}
            kareler = list(self.tampon)
            baslangic = len(kareler) - 1
            try:
                sec = float(sec_ts) if sec_ts else 0.0
            except (TypeError, ValueError):
                sec = 0.0
            if sec and kareler[0][1] <= sec <= kareler[-1][1] + 1.0:
                baslangic = min(range(len(kareler)),
                                key=lambda i: abs(kareler[i][1] - sec))
            kare = kareler[baslangic][0]
            h, w = kare.shape[:2]
            if kutu and len(kutu) == 4:
                x, y, gw, gh = [int(v) for v in kutu]
            else:
                # kutu bilinmiyorsa kare merkezinde orta boy pencere
                gw, gh = w // 4, h // 4
                x, y = (w - gw) // 2, (h - gh) // 2
            x = max(0, min(x, w - 8)); y = max(0, min(y, h - 8))
            gw = max(8, min(gw, w - x)); gh = max(8, min(gh, h - y))
            yontem = str((self.takip_ayar or {}).get("yontem") or "")
            tracker, tracker_ad = self._tracker_olustur(yontem)
            sarilan = 0
            if tracker is not None:
                try:
                    tracker.init(kare, (x, y, gw, gh))
                    # v2.4.174 OLCULEN KUSUR: bu dongu HTTP istek
                    # ipliginde SENKRON calisir ve cagiran taraf (sunucu.py
                    # WS isleyicisi) asyncio dongusunu BLOKE eder. CSRT
                    # zayif CPU'da kare basina 100-500ms surebilir; onceki
                    # limitsiz surum 45 kareye kadar sararak SANIYELER
                    # suren donmaya (ve "secim cok yavas basliyor"
                    # sikayetine) yol aciyordu. Sarma artik SIKI bir zaman
                    # butcesiyle sinirli — bulunabildigi kadar sarilir,
                    # kalan fark canli _takip_dongu ile birkac karede
                    # kapanir (gorsel gecikme onemsizdir, YANIT HIZI onemli).
                    SARMA_BUTCE_SN = 0.12
                    sarma_basi = time.time()
                    for i in range(baslangic + 1, len(kareler)):
                        if time.time() - sarma_basi > SARMA_BUTCE_SN:
                            break
                        ok, k2 = tracker.update(kareler[i][0])
                        sarilan += 1
                        if ok:
                            x, y, gw, gh = [int(v) for v in k2]
                except Exception:
                    tracker = None
            self.takip = {"tur": tur, "kutu": [x, y, gw, gh],
                          "tracker": tracker, "son_ts": time.time(),
                          "son_basarili_ts": time.time(),
                          "kayip_sayac": 0}
            return {"tamam": True, "tracker": tracker is not None,
                    "yontem": tracker_ad,
                    "sarilan_kare": sarilan,
                    "kutu": [x, y, gw, gh]}

    def takip_durdur(self):
        with self.takip_kilit:
            self.takip = None
        return {"tamam": True}

    # v2.4.174: CSRT/KCF/MIL guncellemesi zayif CPU'da 100-500ms surebilir.
    # Okuma dongusunde senkron cagrilirsa video okuma hizini kendisi
    # dusurur (video_fps dusunce takip de yavaslar - kisir dongu). Takip
    # artik AYRI iplikte, en SON kareyi isler; eski kuyruklu kareler
    # birikmez (her zaman en taze kareyle calisir).
    def _takip_kuyrukla(self, kare, ts):
        self._takip_son_kare = (kare, ts)
        iplik = getattr(self, "_takip_iplik", None)
        if iplik is None or not iplik.is_alive():
            iplik = threading.Thread(target=self._takip_dongu, daemon=True)
            self._takip_iplik = iplik
            iplik.start()

    def _takip_dongu(self):
        while self.calisiyor and self.takip is not None:
            veri = getattr(self, "_takip_son_kare", None)
            if veri is None:
                time.sleep(0.02)
                continue
            self._takip_son_kare = None
            kare, ts = veri
            try:
                self._takip_guncelle(kare, ts)
            except Exception as e:
                self.hata = ("takip: " + str(e))[:200]

    def _takip_guncelle(self, kare, ts):
        """Tracker'i yeni kare ile gunceller, konumu ana sunucuya bildirir."""
        with self.takip_kilit:
            tk = self.takip
            if tk is None:
                return
            h, w = kare.shape[:2]
            basarili = False
            if tk["tracker"] is not None:
                try:
                    ok, kutu = tk["tracker"].update(kare)
                    if ok:
                        tk["kutu"] = [int(v) for v in kutu]
                        tk["kayip_sayac"] = 0
                        tk["son_basarili_ts"] = ts
                        basarili = True
                except Exception:
                    pass
            if not basarili:
                tk["kayip_sayac"] += 1
                # v2.4.173: kayip toleransi ZAMAN bazli ve ayarlanabilir
                # (takip_tolerans, sn) — eskiden sabit ~150 cagriydi.
                tol = float((self.takip_ayar or {}).get("tolerans_sn")
                            or 5.0)
                if ts - float(tk.get("son_basarili_ts") or ts) > tol:
                    self.takip = None
                    self.isci.takip_bildir(self, None, ts, kayip=True)
                    return
                # v2.4.176 OLCULEN KUSUR: CSRT/KCF gibi korelasyon
                # tabanli izleyiciler DUSUK KONTRASTLI FON (ozellikle
                # duz gokyuzu) uzerinde TEK KARELIK "ok=False" donmesi
                # cok sik yasar — bu GERCEK kayip DEGILDIR (yukaridaki
                # tolerans penceresi tam da bunu tolere etmek icindir).
                # ONCEKI SURUM her tek-kare basarisizliginda "kayip:true"
                # BILDIRIYORDU; Merkez bunu ALDIGINDA takip kaydini HEMEN
                # SILIYORDU (self.takipler.pop), tarayici dugmeleri
                # "Hedef Sec"e donduruyordu — VE CSRT bir sonraki karede
                # toparlansa BILE Merkez'deki kayit zaten silindigi icin
                # "aktif tekrar basladi" bildirimi HICBIR ZAMAN gitmiyordu
                # (kalici, sessiz kilitlenme). Tolerans icindeyken HICBIR
                # SEY bildirilmez; son bilinen kutu/aktif durum korunur.
                return
            # bildirimi ~5 Hz ile sinirla
            if ts - tk["son_ts"] < 0.2:
                return
            tk["son_ts"] = ts
            x, y, gw, gh = tk["kutu"]
            merkez = ((x + gw / 2) / w, (y + gh / 2) / h)
        self.isci.takip_bildir(self, {
            "tur": tk["tur"], "kutu": [x, y, gw, gh],
            "merkez": [round(merkez[0], 4), round(merkez[1], 4)],
            "kare_boyutu": [int(w), int(h)],
            "kayip": False,
        }, ts)

    # ------------------------------------------------------------------
    def sogutma_gecti(self, anahtar, saniye=10.0):
        """Ayni tespit icin en az `saniye` araligi zorunlu kilar."""
        son = self._sogutma.get(anahtar, 0.0)
        simdi = time.time()
        if simdi - son < saniye:
            return False
        self._sogutma[anahtar] = simdi
        return True

    def klip_yaz(self, dosya_yolu):
        """Halka tampondaki son ~3 sn kareyi MP4 olarak yazar."""
        kareler = list(self.tampon)
        if not kareler:
            return False
        h, w = kareler[0][0].shape[:2]
        # sure / kare sayisindan fps turet
        sure = max(0.5, kareler[-1][1] - kareler[0][1])
        fps = max(5.0, min(30.0, len(kareler) / sure))
        vw = cv2.VideoWriter(dosya_yolu,
                             cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
        if not vw.isOpened():
            return False
        for kare, _ in kareler:
            vw.write(kare)
        vw.release()
        return True


class AIIsci:
    """Yuz tespit/tanima + plaka tespit motoru ve gorev yonetimi."""

    def __init__(self, ad, tip, kapasite, ana_url):
        self.ad = ad
        self.tip = tip
        self.kapasite = kapasite
        self.ana_url = ana_url.rstrip("/")
        self.akislar = {}     # kamera_id -> AkisIsleyici
        self.kilit = threading.Lock()
        os.makedirs(KAYIT_KLASORU, exist_ok=True)

        # v2.4.181 OLCULEN KOK NEDEN (iki kamera ayni anda calismiyordu):
        # `self.ort`/`self.yolo` TEK bir isci-seviyesi model nesnesidir,
        # TUM kameralar arasinda PAYLASILIR (her kameranin kendi
        # `_yolo_dongu` ipligi olsa da, hepsi AYNI oturumu cagirir).
        # ONNX Runtime DirectML (GPU) EP ve cv2.dnn.Net, AYNI oturum/ag
        # nesnesine ES ZAMANLI (concurrent) `run()`/`forward()` cagrisini
        # GUVENLI SAYMAZ — iki kamera birden kare beslediginde çakışan
        # cagrilar cikarimi bozabilir/coker, isci "yeniden dagitim"
        # mantigi da bunu bir kameranin digerini "kapattigi" gibi
        # gosterebilir. Cikarimin kendisi (~50-150ms) kisa oldugu icin
        # kilitleme, kare okuma/takip/video akisini ETKILEMEDEN yalniz
        # GPU/CPU cagrisini sıraya sokar.
        self._yolo_cikarim_kilit = threading.Lock()

        # C-UAS modu: hava_araci tespiti. Oncelik YOLO ONNX modeli
        # (varsa; hareketli kamerada da calisir), yoksa MOG2 hareket
        # tespiti (yalniz sabit kamera). Yuz/insan/plaka kaldirildi.
        self.yolo = None
        self.ort = None          # ONNX Runtime oturumu (GPU/CPU)
        self.ort_girdi = None
        self.ort_saglayici = ""
        # v2.4.169: cok sinifli model destegi — modelin yanindaki
        # "hava_araci.siniflar.txt" (satir basina bir ad, model sinif
        # sirasiyla) varsa tespit etiketi tipi gosterir: "SABIT KANAT %87",
        # "MINI DRON %92" gibi. Boru hatti (takip/angajman) icin tur yine
        # "hava_araci"dir; siniflandirma yalniz gosterim/kayit icindir.
        self.yolo_siniflar = []
        if os.path.exists(YOLO_HAVA):
            # v2.4.170: Once ONNX Runtime (GPU: CUDA > DirectML; yoksa
            # ORT-CPU da cv2.dnn'den hizlidir), olmazsa cv2.dnn.
            if _ort is not None:
                try:
                    mevcut = _ort.get_available_providers()
                    sira = [s for s in ("CUDAExecutionProvider",
                                        "DmlExecutionProvider",
                                        "CPUExecutionProvider")
                            if s in mevcut]
                    self.ort = _ort.InferenceSession(YOLO_HAVA,
                                                     providers=sira)
                    self.ort_girdi = self.ort.get_inputs()[0].name
                    self.ort_saglayici = (self.ort.get_providers()
                                          or ["?"])[0]
                    gpu = self.ort_saglayici != "CPUExecutionProvider"
                    print(f"[AI] Hava araci YOLO modeli yuklendi "
                          f"(ONNX Runtime, {self.ort_saglayici}, "
                          f"GPU={'EVET' if gpu else 'HAYIR'}): {YOLO_HAVA}")
                except Exception as e:
                    self.ort = None
                    print(f"[AI] ONNX Runtime yuklenemedi ({e});"
                          " cv2.dnn denenecek.")
            if self.ort is None:
                try:
                    self.yolo = cv2.dnn.readNetFromONNX(YOLO_HAVA)
                    print(f"[AI] Hava araci YOLO modeli yuklendi"
                          f" (cv2.dnn, CPU): {YOLO_HAVA}")
                except Exception as e:
                    self.yolo = None
                    print(f"[AI] YOLO modeli okunamadi ({e}); MOG2 hareket"
                          " tespiti kullanilacak.")
            sinif_dosya = os.path.splitext(YOLO_HAVA)[0] + ".siniflar.txt"
            if ((self.ort is not None or self.yolo is not None)
                    and os.path.exists(sinif_dosya)):
                try:
                    with open(sinif_dosya, encoding="utf-8") as f:
                        self.yolo_siniflar = [s.strip() for s in f
                                              if s.strip()]
                    print(f"[AI] Hava araci siniflari: "
                          f"{', '.join(self.yolo_siniflar[:12])}")
                except OSError:
                    self.yolo_siniflar = []
        else:
            print(f"[AI] YOLO modeli yok ({YOLO_HAVA}); MOG2 hareket"
                  " tespiti kullanilacak (sabit kamera onerilir).")
        print(f"[AI] Isci kod ozeti: {KOD_OZETI[:12]} pid={os.getpid()}")
        print(f"[AI] Isci hazir: {self.ad} ({self.tip}) mod=C-UAS "
              f"dedektor={self._dedektor_adi()}")

    def _dedektor_adi(self):
        if self.ort is not None:
            return ("YOLO-GPU" if self.ort_saglayici
                    != "CPUExecutionProvider" else "YOLO-ORT")
        return "YOLO" if self.yolo is not None else "MOG2"

    # ------------------------------------------------------------------
    # Gorev yonetimi
    # ------------------------------------------------------------------
    def izle(self, kamera_id, url, protokol, gorevler=None,
             hassasiyet=None):
        with self.kilit:
            kamera_id = int(kamera_id)
            if kamera_id in self.akislar:
                mevcut = self.akislar[kamera_id]
                if gorevler is not None:
                    mevcut.gorevler = gorevleri_sinirla(gorevler)
                if hassasiyet is not None:
                    mevcut.hassasiyet = hassasiyet_coz(hassasiyet)
                    mevcut.takip_ayar = takip_ayar_coz(hassasiyet)
                    mevcut._olcek = {k: (50.0 / max(10, v))
                                     for k, v in mevcut.hassasiyet.items()}
                return {"tamam": True, "mesaj": "zaten izleniyor"}
            if len(self.akislar) >= self.kapasite:
                return {"tamam": False, "hata": "kapasite dolu"}
            isleyici = AkisIsleyici(self, kamera_id, url, protokol,
                                    gorevler, hassasiyet)
            self.akislar[kamera_id] = isleyici
            isleyici.start()
            return {"tamam": True}

    def durdur(self, kamera_id):
        with self.kilit:
            isleyici = self.akislar.pop(int(kamera_id), None)
        if isleyici:
            isleyici.durdur()
        return {"tamam": True}

    def durum(self):
        with self.kilit:
            akislar = [{
                "kamera_id": a.kamera_id,
                "canli": (time.time() - a.son_kare_ts) < 5.0,
                "hata": a.hata,
            } for a in self.akislar.values()]
        return {"ad": self.ad, "tip": self.tip,
                "kapasite": self.kapasite,
                "yuk": len(akislar), "akislar": akislar,
                "ocr": False,
                "yuz_destegi": False,
                "siniflar": sorted(IZINLI_SINIFLAR),
                "dedektor": self._dedektor_adi().lower(),
                "saglayici": self.ort_saglayici,
                "kod_ozeti": KOD_OZETI, "pid": os.getpid(),
                "ana_url": self.ana_url}

    # ------------------------------------------------------------------
    # Analiz
    # ------------------------------------------------------------------
    def kare_yolo_besle(self, akis, kare, ts):
        """v2.4.175: YOLO icin HER karede cagrilir (5Hz orneklemeye tabi
        DEGILDIR) — hizli ucan hedefte sureksiz gorunen takibin sebebiydi.
        `_yolo_kuyrukla` ucuzdur (yalniz en son kareyi saklar); gercek
        cikarim ayri iplikte kendi hizinda calisir, okuma dongusunu
        etkilemez."""
        if self.ort is None and self.yolo is None:
            return
        if "hava_araci" not in (akis.gorevler & IZINLI_SINIFLAR):
            return
        self._yolo_kuyrukla(akis, kare, ts)

    def kare_analiz(self, akis, kare, ts):
        # GRCOFF 2.5.35 C-UAS: yalnız hava aracı (IHA/drone) tespiti.
        # v2.4.175: YOLO artik `kare_yolo_besle` ile HER karede ayrica
        # beslenir; burada YALNIZ MOG2 (model yoksa) ve "gorev kapali"
        # temizligi kalir — 5Hz ornekleme MOG2 icin hala uygundur (CPU
        # dostu; hareket algoritmasi ayri iplige alinmadi).
        g = akis.gorevler & IZINLI_SINIFLAR
        if "hava_araci" not in g:
            akis.canli_kutular = []
            try:
                h, w = kare.shape[:2]
                self._kutulari_bildir(akis, w, h, ts)
            except Exception:
                pass
            return
        if self.ort is not None or self.yolo is not None:
            return   # YOLO yolu tamamen kare_yolo_besle uzerinden isler
        akis.canli_kutular = []
        _t0 = time.time()
        self._hareket_analiz(akis, kare, ts)
        self._olcum_guncelle(akis, ts, (time.time() - _t0) * 1000.0)
        try:
            h, w = kare.shape[:2]
            self._kutulari_bildir(akis, w, h, ts)
        except Exception:
            pass

    @staticmethod
    def _olcum_guncelle(akis, ts, sure_ms):
        """Cikarim suresi (ms) ve analiz dongusu (Hz) EMA olcumleri."""
        eski = getattr(akis, "_cikarim_ms", 0.0)
        akis._cikarim_ms = sure_ms if not eski else 0.7 * eski + 0.3 * sure_ms
        onceki = getattr(akis, "_analiz_onceki_ts", 0.0)
        akis._analiz_onceki_ts = ts
        if onceki and ts > onceki:
            hz = 1.0 / (ts - onceki)
            e = getattr(akis, "_analiz_hz", 0.0)
            akis._analiz_hz = hz if not e else 0.7 * e + 0.3 * hz

    def _yolo_kuyrukla(self, akis, kare, ts):
        """Son kareyi cikarim ipligine birakir (eski bekleyen atilir)."""
        akis._yolo_kare = (kare, ts)
        iplik = getattr(akis, "_yolo_iplik", None)
        if iplik is None or not iplik.is_alive():
            iplik = threading.Thread(target=self._yolo_dongu,
                                     args=(akis,), daemon=True)
            akis._yolo_iplik = iplik
            iplik.start()

    def _yolo_dongu(self, akis):
        while akis.calisiyor:
            veri = getattr(akis, "_yolo_kare", None)
            if veri is None:
                time.sleep(0.05)
                continue
            akis._yolo_kare = None
            kare, ts = veri
            try:
                self._yolo_analiz(akis, kare, ts)
                h, w = kare.shape[:2]
                self._kutulari_bildir(akis, w, h, ts)
            except Exception as e:
                if akis.sogutma_gecti("yolo_dongu_hata", saniye=60.0):
                    print(f"[AI] YOLO islem hatasi: {e}")

    def _kutulari_bildir(self, akis, kaynak_w, kaynak_h, ts):
        """Canli tespit kutularini ana sunucuya POST /ai/kutular ile
        gonderir (v2.4.7). Sogutmadan bagimsizdir; bos liste de
        gonderilir ki eski kutular temizlensin."""
        kutular = getattr(akis, "canli_kutular", None) or []
        # bos liste ard arda gonderilmesin (bant genisligi) — ama durum
        # bilgisi (dedektor/GPU/fps) icin ~2 sn'de bir kalp atisi gider.
        if not kutular and not getattr(akis, "_son_kutu_vardi", False):
            if ts - getattr(akis, "_durum_ts", 0.0) < 2.0:
                return
        akis._durum_ts = ts
        akis._son_kutu_vardi = bool(kutular)
        for k in kutular:
            k["kaynak_w"], k["kaynak_h"] = int(kaynak_w), int(kaynak_h)
        govde = {"kamera_id": akis.kamera_id, "ts": ts,
                 "isci": self.ad, "kutular": kutular,
                 "durum": {
                     "dedektor": self._dedektor_adi(),
                     "saglayici": self.ort_saglayici,
                     "cikarim_ms": int(getattr(akis, "_cikarim_ms", 0) or 0),
                     "analiz_hz": round(
                         getattr(akis, "_analiz_hz", 0.0) or 0.0, 1),
                     "video_fps": round(akis.video_fps(), 1),
                 }}
        try:
            istek = urllib.request.Request(
                self.ana_url + "/ai/kutular",
                data=json.dumps(govde).encode(),
                headers={"Content-Type": "application/json"})
            urllib.request.urlopen(istek, timeout=2).read()
        except Exception:
            pass   # canli kutu bildirimi kritik degil

    @staticmethod
    def _canli_kutu_ekle(akis, x, y, w, h, tur, etiket="",
                         embedding=None):
        """Analizde bulunan kutuyu canli listeye ekler (v2.4.7)."""
        kutu = {"x": int(x), "y": int(y), "w": int(w), "h": int(h),
                "tur": tur, "etiket": etiket or ""}
        if embedding is not None:
            try:
                kutu["embedding"] = base64.b64encode(
                    np.asarray(embedding,
                               dtype=np.float32).tobytes()).decode()
            except Exception:
                pass
        if not hasattr(akis, "canli_kutular") or akis.canli_kutular is None:
            akis.canli_kutular = []
        akis.canli_kutular.append(kutu)

    def _yuz_analiz(self, akis, kare, ts):
        if self.yuz_tespit is None:
            return
        h, w = kare.shape[:2]
        self.yuz_tespit.setInputSize((w, h))
        _, yuzler = self.yuz_tespit.detect(kare)
        if yuzler is None:
            return
        for yuz in yuzler:
            x, y, gw, gh = [int(v) for v in yuz[:4]]
            guven = float(yuz[-1])
            if guven < 0.8 or gw < 40 or gh < 40:
                continue
            embedding = None
            if self.yuz_tanima is not None:
                try:
                    hizali = self.yuz_tanima.alignCrop(kare, yuz)
                    embedding = self.yuz_tanima.feature(hizali).flatten()
                except Exception:
                    embedding = None
            # v2.4.7: canli kutu (sogutmasiz) — isim eslesmesi ana sunucuda
            self._canli_kutu_ekle(akis, x, y, gw, gh, "yuz",
                                  embedding=embedding)
            # kaba konum anahtari ile sogutma (ayni yuz surekli bildirilmesin)
            anahtar = f"yuz_{x // 80}_{y // 80}"
            if not akis.sogutma_gecti(anahtar):
                continue
            x0, y0 = max(0, x - 20), max(0, y - 20)
            kirp = kare[y0:min(h, y + gh + 20), x0:min(w, x + gw + 20)]
            self._tespit_bildir(akis, "yuz", kare, kirp, ts,
                                guven=guven, embedding=embedding)

    @staticmethod
    def _kontur_plaka_adaylari(gri):
        """Cascade yokken (OpenCV 5) kontur tabanli plaka adaylari.

        Kenar cikarimi + dikdortgen kontur analizi: en-boy orani
        2-6 arasi, yeterince buyuk yatay dikdortgenler aday sayilir.
        """
        kenar = cv2.Canny(gri, 80, 200)
        kenar = cv2.dilate(kenar, np.ones((3, 3), np.uint8))
        konturlar, _ = cv2.findContours(kenar, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)
        adaylar = []
        for c in konturlar:
            x, y, gw, gh = cv2.boundingRect(c)
            if gw < 70 or gh < 18 or gh > 120:
                continue
            oran = gw / float(gh)
            if not (2.0 <= oran <= 6.5):
                continue
            # doluluk: kontur alani / dikdortgen alani (gurultu filtresi)
            if cv2.contourArea(c) / float(gw * gh) < 0.35:
                continue
            adaylar.append((x, y, gw, gh))
        # en buyuk 3 aday yeterli
        adaylar.sort(key=lambda r: r[2] * r[3], reverse=True)
        return adaylar[:3]

    def _plaka_analiz(self, akis, kare, ts):
        gri = cv2.cvtColor(kare, cv2.COLOR_BGR2GRAY)
        if self.plaka_cascade is not None:
            plakalar = self.plaka_cascade.detectMultiScale(
                gri, scaleFactor=1.1, minNeighbors=6, minSize=(60, 20))
        else:
            # OpenCV 5: kontur tabanli aday tespiti (yalniz OCR varsa
            # anlamli — OCR yoksa gurultu bildirmemek icin cik)
            if not OCR_VAR:
                return
            plakalar = self._kontur_plaka_adaylari(gri)
        h, w = kare.shape[:2]
        for (x, y, gw, gh) in plakalar:
            kirp = kare[y:y + gh, x:x + gw]
            metin = ""
            if OCR_VAR:
                try:
                    buyuk = cv2.resize(kirp, None, fx=2.5, fy=2.5,
                                       interpolation=cv2.INTER_CUBIC)
                    g = cv2.cvtColor(buyuk, cv2.COLOR_BGR2GRAY)
                    g = cv2.threshold(
                        g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
                    ham = pytesseract.image_to_string(
                        g, config="--psm 7 -c tessedit_char_whitelist="
                                  "ABCDEFGHIJKLMNOPRSTUVYZ0123456789")
                    metin = "".join(c for c in ham if c.isalnum()).upper()
                except Exception:
                    metin = ""
            if metin and len(metin) < 5:
                metin = ""   # gurultu
            # kontur yonteminde OCR metni yoksa bildirme (yanlis pozitif)
            if self.plaka_cascade is None and not metin:
                continue
            self._canli_kutu_ekle(akis, x, y, gw, gh, "plaka",
                                  etiket=metin)
            anahtar = "plaka_" + (metin or f"{x // 80}_{y // 80}")
            if not akis.sogutma_gecti(anahtar, saniye=15.0):
                continue
            x0, y0 = max(0, x - 15), max(0, y - 15)
            genis = kare[y0:min(h, y + gh + 15), x0:min(w, x + gw + 15)]
            self._tespit_bildir(akis, "plaka", kare, genis, ts,
                                guven=0.6, plaka_metin=metin)

    # ------------------------------------------------------------------
    # v2.4.168: YOLO ONNX hava araci tespiti (model varsa)
    # ------------------------------------------------------------------
    def _yolo_analiz(self, akis, kare, ts):
        """YOLOv5/8 ONNX ciktisiyla hava araci tespiti.

        MOG2'den farki: hareketli kamera goruntusunde de calisir (nesne
        gorunumden taninir, hareketten degil). v2.4.175: artik HER karede
        beslenir (`kare_yolo_besle`); gercek hiz siniri kendi cikarim
        suresidir (GPU'da ~50-150ms -> dogal olarak ~6-15 Hz; zayif CPU'da
        daha dusuk). Kuyruk deseni (en TAZE kareyi isler) video okuma
        dongusunu asla yavaslatmaz.
        """
        # Kuyruk zaten serilestirir (tek cikarim ipligi calisir); yalnizca
        # patolojik "ayni ts ile art arda cagri" durumuna karsi cok kucuk
        # bir alt sinir (pratikte cikarim suresi bunun cok uzerindedir).
        if ts - getattr(akis, "_yolo_son", 0.0) < 0.03:
            return
        akis._yolo_son = ts
        akis.canli_kutular = []
        h, w = kare.shape[:2]
        BOY = 640
        olcek = min(BOY / float(w), BOY / float(h))
        nw, nh = max(1, int(w * olcek)), max(1, int(h * olcek))
        tuval = np.full((BOY, BOY, 3), 114, np.uint8)
        tuval[:nh, :nw] = cv2.resize(kare, (nw, nh))
        blob = cv2.dnn.blobFromImage(tuval, 1.0 / 255.0, (BOY, BOY),
                                     swapRB=True, crop=False)
        try:
            _t0 = time.time()
            # v2.4.181: `self.ort`/`self.yolo` isci-seviyesinde TEK ve
            # PAYLASILMIS bir oturumdur (bkz. yukaridaki not) — birden
            # fazla kamera aktifken kendi `_yolo_dongu` ipliklerinden
            # ES ZAMANLI cagrilabilir. DirectML (GPU) EP ve cv2.dnn.Net
            # ayni oturuma/aga concurrent run()/forward() cagrisini
            # guvenli saymaz; kilit yalnizca bu kisa cagriyi (~50-150ms)
            # sıraya sokar, kare okuma/takip/video akisini etkilemez.
            with self._yolo_cikarim_kilit:
                if self.ort is not None:
                    cikti = self.ort.run(None, {self.ort_girdi: blob})[0]
                else:
                    self.yolo.setInput(blob)
                    cikti = self.yolo.forward()
            self._olcum_guncelle(akis, ts, (time.time() - _t0) * 1000.0)
        except Exception as e:
            if akis.sogutma_gecti("yolo_hata", saniye=60.0):
                print(f"[AI] YOLO cikarimi basarisiz: {e}")
            return
        # Bicim normalizasyonu: (1,C,N) veya (1,N,C) -> (N, C)
        if cikti.ndim == 3:
            cikti = cikti[0]
        if cikti.ndim != 2:
            return
        if cikti.shape[0] < cikti.shape[1]:
            cikti = cikti.T
        sutun = cikti.shape[1]
        if sutun < 5:
            return
        # v2.4.169: SINIF BAZLI ac/kapat + hassasiyet.
        # - Alt sinif esigi kendi hassasiyetinden turetilir (s=50 -> 0.35).
        # - Gorevlerde en az bir alt sinif SECILIYSE yalniz seciler gecer;
        #   hic secilmemisse tum siniflar acik (eski davranis / tek sinif).
        _olcek = getattr(akis, "_olcek", {})

        def _esik(anahtar):
            kk = _olcek.get(anahtar) or _olcek.get("hava_araci", 1.0)
            return max(0.10, min(0.90, 0.35 * min(1.5, kk)))

        alt_secili = akis.gorevler & ALT_SINIFLAR
        esik_taban = 0.10   # aday toplama esigi; sinif esigi sonra uygulanir
        kutular, puanlar, sinif_no = [], [], []
        for satir in cikti:
            # YOLOv8/12: [cx,cy,w,h, sinif_puanlari...]
            # YOLOv5:    [cx,cy,w,h, nesnelik, sinif_puanlari...]
            # Iki bicim icin de en yuksek guven sutunu kullanilir; v5'te
            # bu hafif iyimserdir, esik + NMS ile dengelenir.
            vec = satir[4:]
            puan = float(vec.max())
            if puan < esik_taban:
                continue
            cx, cy, bw, bh = (float(v) for v in satir[:4])
            x = int((cx - bw / 2.0) / olcek)
            y = int((cy - bh / 2.0) / olcek)
            gw, gh = int(bw / olcek), int(bh / olcek)
            if gw < 6 or gh < 6:
                continue
            kutular.append([x, y, gw, gh])
            puanlar.append(puan)
            sinif_no.append(int(vec.argmax()))
        if not kutular:
            return
        sec = cv2.dnn.NMSBoxes(kutular, puanlar, esik_taban, 0.45)
        if sec is None or len(sec) == 0:
            return
        for i in np.array(sec).flatten():
            x, y, gw, gh = kutular[int(i)]
            x = max(0, min(x, w - 4)); y = max(0, min(y, h - 4))
            gw = max(4, min(gw, w - x)); gh = max(4, min(gh, h - y))
            puan = puanlar[int(i)]
            si = sinif_no[int(i)]
            ad_ham = (self.yolo_siniflar[si]
                      if si < len(self.yolo_siniflar) else "IHA")
            anahtar = sinif_anahtari(ad_ham)
            if anahtar == "_yok":
                continue        # "background" vb. gercek nesne degil
            if anahtar and alt_secili and anahtar not in akis.gorevler:
                continue        # bu sinif kullanici tarafindan KAPALI
            if puan < _esik(anahtar):
                continue        # sinifin kendi hassasiyet esigi
            # cv2.putText Turkce karakter cizemez -> ASCII'ye indirgenir
            ad = (ad_ham.upper().replace("İ", "I").replace("Ş", "S")
                  .replace("Ğ", "G").replace("Ü", "U").replace("Ö", "O")
                  .replace("Ç", "C"))[:24]
            self._canli_kutu_ekle(akis, x, y, gw, gh, "hava_araci",
                                  etiket="%s %%%d" % (ad, int(puan * 100)))
            anahtar = f"hava_araci_{x // 120}_{y // 120}"
            if not akis.sogutma_gecti(anahtar, saniye=6.0):
                continue
            x0, y0 = max(0, x - 20), max(0, y - 20)
            kirp = kare[y0:min(h, y + gh + 20), x0:min(w, x + gw + 20)]
            self._tespit_bildir(akis, "hava_araci", kare, kirp, ts,
                                guven=puan)

    # ------------------------------------------------------------------
    # C-UAS: Hareket tabanli hava araci (IHA/drone) tespiti
    # ------------------------------------------------------------------
    # CPU iscide arka plan cikarma (MOG2) + blob analizi kullanilir:
    #  - hava_araci: karenin ust bolgesinde (gokyuzu), kompakt, kucuk-orta
    #    boyutlu hizli nesneler (dron/IHA profili) — ONCELIKLI GOREV
    #  - kara_araci: alt bolgede, genis/yatay, buyuk nesneler (arac profili)
    # NVIDIA iscilerde ayni API korunarak YOLO benzeri modellerle
    # degistirilebilir (tur adlari ve bildirim semasi aynidir).
    def _hareket_analiz(self, akis, kare, ts):
        if akis.arka_plan is None:
            akis.arka_plan = cv2.createBackgroundSubtractorMOG2(
                history=200, varThreshold=32, detectShadows=False)
            return   # ilk kare: model isiniyor
        h, w = kare.shape[:2]
        maske = akis.arka_plan.apply(kare)
        maske = cv2.medianBlur(maske, 5)
        maske = cv2.dilate(maske, np.ones((5, 5), np.uint8))
        kare_alani = float(h * w)
        # v2.4.168 KAMERA HAREKETI KORUMASI (olculen kusur): MOG2 SABIT
        # kamera varsayar. Kamera hareket ederken (dron kamerasindan
        # kayit, pan/titresim) TUM sahne "hareketli" gorunur ve her arazi
        # parcasi hava araci sanilirdi. Kare genelinde on-plan orani
        # yuksekse bu kare kamera hareketidir; tespit ATLANIR.
        on_plan = cv2.countNonZero(maske) / kare_alani
        if on_plan > 0.06:
            if akis.sogutma_gecti("kamera_hareket_uyari", saniye=30.0):
                print("[AI] kam=%s: karenin %%%d'i hareketli — kamera "
                      "hareketli/titresimli goruntu; MOG2 tespiti bu "
                      "karelerde atlanir (sabit kamera onerilir)"
                      % (akis.kamera_id, int(on_plan * 100)))
            return
        konturlar, _ = cv2.findContours(maske, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)
        gri = cv2.cvtColor(kare, cv2.COLOR_BGR2GRAY)
        # v2.5.24: sınıf başına alan alt-sınır ölçeği (s=50 -> k=1.0 nötr;
        # yüksek hassasiyet -> daha küçük alt sınır -> daha çok tespit).
        _kh = getattr(akis, "_olcek", {}).get("hava_araci", 1.0)
        for c in konturlar:
            x, y, gw, gh = cv2.boundingRect(c)
            alan = gw * gh
            oran = gw / float(gh) if gh else 0
            merkez_y = y + gh / 2.0
            # Hava aracı (IHA/drone): karenin üst %70'inde, kompakt, hızlı hareket
            # Üst sınır genişletildi (%55 -> %70): alçak irtifadaki dronlar da yakalansın
            if not (merkez_y < h * 0.70
                    and 0.0003 * _kh * kare_alani < alan < 0.08 * kare_alani
                    and 0.3 <= oran <= 4.0):
                continue
            # doluluk filtresi: cok seyrek konturlar gurultudur
            if cv2.contourArea(c) / float(alan) < 0.25:
                continue
            # v2.4.168 GOKYUZU/FON TEKDUZELIGI: dron kompakt bir cisim
            # olarak goreceli DUZ bir fon (gokyuzu, bulut) onunde belirir.
            # Aday kutunun genis cevresi cok dokuluysa (arazi, agac, bina)
            # bu bir yer nesnesi/parallaks artigidir; reddedilir.
            px0, py0 = max(0, x - gw), max(0, y - gh)
            px1, py1 = min(w, x + 2 * gw), min(h, y + 2 * gh)
            pencere = gri[py0:py1, px0:px1]
            if pencere.size and float(pencere.std()) > 26.0:
                continue
            self._canli_kutu_ekle(akis, x, y, gw, gh, "hava_araci")
            anahtar = f"hava_araci_{x // 120}_{y // 120}"
            if not akis.sogutma_gecti(anahtar, saniye=6.0):
                continue
            x0, y0 = max(0, x - 20), max(0, y - 20)
            kirp = kare[y0:min(h, y + gh + 20), x0:min(w, x + gw + 20)]
            self._tespit_bildir(akis, "hava_araci", kare, kirp, ts, guven=0.55)

    # ------------------------------------------------------------------
    # Takip (tracking) bildirimi — angajman koprusu
    # ------------------------------------------------------------------
    def takip_bildir(self, akis, veri, ts, kayip=False):
        """Takip konumunu ana sunucuya POST /ai/takip ile bildirir."""
        govde = {"kamera_id": akis.kamera_id, "ts": ts,
                 "isci": self.ad, "kayip": bool(kayip)}
        if veri:
            govde.update(veri)
        try:
            istek = urllib.request.Request(
                self.ana_url + "/ai/takip",
                data=json.dumps(govde).encode(),
                headers={"Content-Type": "application/json"})
            urllib.request.urlopen(istek, timeout=3).read()
        except Exception as e:
            print(f"[AI] Takip bildirilemedi: {e}")

    # ------------------------------------------------------------------
    # Kayit + bildirim
    # ------------------------------------------------------------------
    def _tespit_bildir(self, akis, tur, kare, kirp, ts,
                       guven=0.0, embedding=None, plaka_metin=""):
        gun = time.strftime("%Y%m%d", time.localtime(ts))
        klasor = os.path.join(KAYIT_KLASORU, gun)
        os.makedirs(klasor, exist_ok=True)
        kok_ad = f"k{akis.kamera_id}_{tur}_{int(ts * 1000)}"

        foto_yol = os.path.join(klasor, kok_ad + ".jpg")
        cv2.imwrite(foto_yol, kirp if kirp.size else kare,
                    [cv2.IMWRITE_JPEG_QUALITY, 88])

        klip_yol = os.path.join(klasor, kok_ad + ".mp4")
        klip_ok = akis.klip_yaz(klip_yol)

        # kucuk onizleme (alt panel akisi icin base64)
        try:
            oniz = kirp if kirp.size else kare
            oh, ow = oniz.shape[:2]
            olcek = 96.0 / max(oh, ow)
            if olcek < 1.0:
                oniz = cv2.resize(oniz, (int(ow * olcek), int(oh * olcek)))
            _, jpg = cv2.imencode(".jpg", oniz,
                                  [cv2.IMWRITE_JPEG_QUALITY, 80])
            oniz_b64 = base64.b64encode(jpg.tobytes()).decode()
        except Exception:
            oniz_b64 = ""

        veri = {
            "kamera_id": akis.kamera_id,
            "tur": tur,
            "ts": ts,
            "guven": round(float(guven), 3),
            "foto": os.path.relpath(foto_yol, KOK).replace(os.sep, "/"),
            "klip": (os.path.relpath(klip_yol, KOK).replace(os.sep, "/")
                     if klip_ok else ""),
            "plaka_metin": plaka_metin,
            "embedding": (base64.b64encode(
                np.asarray(embedding, dtype=np.float32).tobytes()).decode()
                if embedding is not None else ""),
            "onizleme_b64": oniz_b64,
            "isci": self.ad,
        }
        try:
            istek = urllib.request.Request(
                self.ana_url + "/ai/tespit",
                data=json.dumps(veri).encode(),
                headers={"Content-Type": "application/json"})
            urllib.request.urlopen(istek, timeout=5).read()
        except Exception as e:
            print(f"[AI] Tespit bildirilemedi: {e}")

    # ------------------------------------------------------------------
    def embed_hesapla(self, foto_b64):
        """Tek fotograftan yuz embeddingi cikarir (kutuphane kaydi icin)."""
        if self.yuz_tespit is None or self.yuz_tanima is None:
            # v2.4.6: eski kisa mesaj korunuyor (ana sunucu bunu taniyor)
            return {"tamam": False, "hata": "modeller yuklu degil",
                    "detay": "Yuz modelleri (YuNet/SFace) yuklenemedi."
                             " ai_modeller/ klasorunu kontrol edin veya"
                             " 'python ai_sunucu.py --model-kontrol'"
                             " calistirin."}
        try:
            ham = base64.b64decode(foto_b64.split(",")[-1])
            dizi = np.frombuffer(ham, dtype=np.uint8)
            kare = cv2.imdecode(dizi, cv2.IMREAD_COLOR)
            if kare is None:
                return {"tamam": False, "hata": "resim okunamadi"}
            h, w = kare.shape[:2]
            # cok buyuk resimleri kucult (hiz + YuNet stabilitesi)
            if max(h, w) > 1280:
                olcek = 1280.0 / max(h, w)
                kare = cv2.resize(kare, (int(w * olcek), int(h * olcek)))
                h, w = kare.shape[:2]
            self.yuz_tespit.setInputSize((w, h))
            _, yuzler = self.yuz_tespit.detect(kare)
            if yuzler is None or len(yuzler) == 0:
                return {"tamam": False, "hata": "yuz bulunamadi"}
            # en buyuk yuzu al
            yuz = max(yuzler, key=lambda f: f[2] * f[3])
            hizali = self.yuz_tanima.alignCrop(kare, yuz)
            emb = self.yuz_tanima.feature(hizali).flatten()
            return {"tamam": True,
                    "embedding": base64.b64encode(
                        np.asarray(emb, dtype=np.float32).tobytes()).decode(),
                    "yuz_sayisi": int(len(yuzler))}
        except Exception as e:
            return {"tamam": False, "hata": str(e)[:200]}


def http_sunucu(isci, port, dinle="0.0.0.0"):
    class Istek(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, veri, kod=200):
            govde = json.dumps(veri).encode()
            try:
                self.send_response(kod)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(govde)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(govde)
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError):
                # v2.4.159: Loopback sağlık yoklamasında istemci yanıtı
                # okuyup bağlantıyı kapatınca yazma sıfırlanabilir (WinError
                # 10054). Zararsız; sessiz geç (log kirlenmesin).
                pass

        def do_GET(self):
            if self.path.startswith("/durum"):
                self._json(isci.durum())
            else:
                self._json({"hata": "bilinmeyen yol"}, 404)

        def do_POST(self):
            try:
                boy = int(self.headers.get("Content-Length", 0))
                veri = json.loads(self.rfile.read(boy) or b"{}")
            except (ValueError, json.JSONDecodeError):
                self._json({"hata": "gecersiz JSON"}, 400)
                return
            if self.path == "/takip_baslat":
                kamera_id = int(veri.get("kamera_id", 0))
                with isci.kilit:
                    akis = isci.akislar.get(kamera_id)
                if akis is None:
                    self._json({"tamam": False,
                                "hata": "kamera izlenmiyor"})
                else:
                    self._json(akis.takip_baslat(veri.get("tur", ""),
                                                 veri.get("kutu"),
                                                 veri.get("ts")))
            elif self.path == "/takip_durdur":
                kamera_id = int(veri.get("kamera_id", 0))
                with isci.kilit:
                    akis = isci.akislar.get(kamera_id)
                self._json(akis.takip_durdur() if akis
                           else {"tamam": True})
            elif self.path == "/izle":
                # v2.4.162: bos gorev listesi = HIC gorev (None'a
                # cevrilmez; None "tum siniflar" anlamina geliyordu).
                gorevler = veri.get("gorevler")
                if gorevler is None:
                    gorevler = []
                if isinstance(gorevler, str):
                    gorevler = [g.strip() for g in gorevler.split(",")
                                if g.strip()]
                self._json(isci.izle(veri.get("kamera_id"),
                                     veri.get("url", ""),
                                     veri.get("protokol", ""),
                                     gorevler,
                                     veri.get("hassasiyet")))
            elif self.path == "/durdur":
                self._json(isci.durdur(veri.get("kamera_id")))
            elif self.path == "/embed":
                self._json(isci.embed_hesapla(veri.get("foto_b64", "")))
            else:
                self._json({"hata": "bilinmeyen yol"}, 404)

    srv = ThreadingHTTPServer((dinle, port), Istek)
    print(f"[AI] HTTP API dinleniyor: {dinle}:{port}")
    srv.serve_forever()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="GOKTUNGU AI islem iscisi")
    p.add_argument("--port", type=int, default=8900)
    p.add_argument("--ad", default="CPU AI Sunucusu")
    p.add_argument("--tip", default="cpu", choices=["cpu", "nvidia"])
    p.add_argument("--kapasite", type=int, default=4,
                   help="es zamanli islenebilir akis sayisi")
    # v2.4.153: GRCOFF yerel iscisi --dinle 127.0.0.1 ile baslar; ayri AI
    # bilgisayarinda calisan eski tip isci icin varsayilan degismedi.
    p.add_argument("--dinle", default="0.0.0.0",
                   help="dinlenecek adres (yerel isci: 127.0.0.1)")
    p.add_argument("--ana", default="http://127.0.0.1:8000",
                   help="GCS ana sunucu adresi (tespit bildirimi)")
    p.add_argument("--model-kontrol", action="store_true",
                   help="model dosyalarini dogrula/indir ve cik")
    args = p.parse_args()
    if args.model_kontrol:
        # v2.4.6: model dosyalarini dogrular, eksik/bozuksa indirir
        print(f"[AI] Model klasoru: {MODEL_KLASORU}")
        sonuclar = []
        for yol, yukleyici, adi in (
                (YUNET, lambda y: cv2.FaceDetectorYN.create(
                    y, "", (320, 320), 0.7, 0.3, 5000),
                 "Yuz tespit (YuNet)"),
                (SFACE, lambda y: cv2.FaceRecognizerSF.create(y, ""),
                 "Yuz tanima (SFace)")):
            model = model_yukle(yol, yukleyici, adi)
            durum_txt = "TAMAM" if model is not None else "BASARISIZ"
            boyut = (os.path.getsize(yol)
                     if os.path.exists(yol) else 0)
            print(f"[AI] {adi}: {durum_txt} ({boyut} bayt)")
            sonuclar.append(model is not None)
        raise SystemExit(0 if all(sonuclar) else 1)
    isci = AIIsci(args.ad, args.tip, args.kapasite, args.ana)
    http_sunucu(isci, args.port, args.dinle)
