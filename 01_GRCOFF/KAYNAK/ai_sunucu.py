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
# v2.4.161: "yuz" = yakin cekim yuz tespiti (ayri ac/kapat gorevi). Tam
# beden "insan" (HOG/yaya) ile BAGIMSIZ acilip kapanir; tespit YINE "insan"
# olarak bildirilir (kullanici istegi: "en azindan insan demeli"). Kimlik
# TANIMA yapilmaz — yalniz varlik.
IZINLI_SINIFLAR = frozenset(("insan", "yuz", "kara_araci", "hava_araci"))


def gorevleri_sinirla(gorevler):
    if gorevler is None:
        return set(IZINLI_SINIFLAR)
    if isinstance(gorevler, str):
        gorevler = gorevler.replace(";", ",").split(",")
    return {str(g).strip().lower() for g in (gorevler or [])
            if str(g).strip().lower() in IZINLI_SINIFLAR}


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
    for k in IZINLI_SINIFLAR:
        try:
            v = int(round(float((deger or {}).get(k))))
        except (TypeError, ValueError):
            v = _HASSAS_VARSAYILAN
        out[k] = min(90, max(10, v))
    return out


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
            # aktif hedef takibi: her karede tracker guncelle
            if self.takip is not None:
                try:
                    self._takip_guncelle(kare, ts)
                except Exception as e:
                    self.hata = ("takip: " + str(e))[:200]
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
                    if self.takip is not None:
                        try:
                            self._takip_guncelle(kare, ts)
                        except Exception as e:
                            self.hata = ("takip: " + str(e))[:200]
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
    def _tracker_olustur():
        """Kullanilabilir bir OpenCV tracker dondurur (surum uyumlu)."""
        for ad in ("TrackerCSRT", "TrackerKCF", "TrackerMIL"):
            olusturucu = getattr(cv2, ad + "_create", None)
            if olusturucu is None and hasattr(cv2, "legacy"):
                olusturucu = getattr(cv2.legacy, ad + "_create", None)
            if olusturucu is None:
                sinif = getattr(cv2, ad, None)
                if sinif is not None and hasattr(sinif, "create"):
                    olusturucu = sinif.create
            if olusturucu:
                try:
                    return olusturucu()
                except Exception:
                    continue
        return None

    def takip_baslat(self, tur, kutu=None):
        """Yalnız izinli sınıfta manuel pasif görüntü takibini başlatır."""
        tur = str(tur or "").strip().lower()
        if tur not in IZINLI_SINIFLAR:
            return {"tamam": False,
                    "hata": "yalnız insan, kara_araci veya hava_araci seçilebilir"}
        with self.takip_kilit:
            if not self.tampon:
                return {"tamam": False, "hata": "akista kare yok"}
            kare = self.tampon[-1][0]
            h, w = kare.shape[:2]
            if kutu and len(kutu) == 4:
                x, y, gw, gh = [int(v) for v in kutu]
            else:
                # kutu bilinmiyorsa kare merkezinde orta boy pencere
                gw, gh = w // 4, h // 4
                x, y = (w - gw) // 2, (h - gh) // 2
            x = max(0, min(x, w - 8)); y = max(0, min(y, h - 8))
            gw = max(8, min(gw, w - x)); gh = max(8, min(gh, h - y))
            tracker = self._tracker_olustur()
            if tracker is not None:
                try:
                    tracker.init(kare, (x, y, gw, gh))
                except Exception:
                    tracker = None
            self.takip = {"tur": tur, "kutu": [x, y, gw, gh],
                          "tracker": tracker, "son_ts": time.time(),
                          "kayip_sayac": 0}
            return {"tamam": True, "tracker": tracker is not None,
                    "kutu": [x, y, gw, gh]}

    def takip_durdur(self):
        with self.takip_kilit:
            self.takip = None
        return {"tamam": True}

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
                        basarili = True
                except Exception:
                    pass
            if not basarili:
                tk["kayip_sayac"] += 1
                # ~5 sn kayip -> takibi birak (fps*5 kare degil, cagri bazli)
                if tk["kayip_sayac"] > 150:
                    self.takip = None
                    self.isci.takip_bildir(self, None, ts, kayip=True)
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
            "kayip": not basarili and tk["kayip_sayac"] > 0,
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

        self.yuz_tespit = None
        self.yuz_tanima = None
        self.plaka_cascade = None
        # v2.4.2: HOG insan dedektoru (OpenCV yerlesik, model dosyasiz)
        # v2.4.5: OpenCV 5.x'te HOGDescriptor kaldirildi — bu durumda
        # insan tespiti hareket tabanli (MOG2 dikey blob) yontemine duser.
        try:
            self.insan_hog = cv2.HOGDescriptor()
            self.insan_hog.setSVMDetector(
                cv2.HOGDescriptor_getDefaultPeopleDetector())
        except Exception:
            self.insan_hog = None
            print("[AI] Uyari: HOGDescriptor yok (OpenCV 5); insan"
                  " tespiti hareket tabanli yonteme dusuruldu.")
        self.yuz_tespit = model_yukle(
            YUNET,
            lambda y: cv2.FaceDetectorYN.create(y, "", (320, 320),
                                                0.7, 0.3, 5000),
            "Yuz tespit (YuNet)")
        self.yuz_tanima = model_yukle(
            SFACE,
            lambda y: cv2.FaceRecognizerSF.create(y, ""),
            "Yuz tanima (SFace)")
        # OpenCV 5.x'te CascadeClassifier kaldirildi; 4.x'te calisir.
        if (os.path.exists(PLAKA_CASCADE)
                and hasattr(cv2, "CascadeClassifier")):
            try:
                self.plaka_cascade = cv2.CascadeClassifier(PLAKA_CASCADE)
                if self.plaka_cascade.empty():
                    self.plaka_cascade = None
                    print("[AI] Uyari: plaka cascade dosyasi okunamadi;"
                          " plaka tespiti kontur yontemine dusuruldu.")
            except Exception as e:
                self.plaka_cascade = None
                print(f"[AI] Uyari: plaka cascade yuklenemedi ({e});"
                      " kontur yontemi kullanilacak.")
        elif not hasattr(cv2, "CascadeClassifier"):
            print("[AI] Uyari: OpenCV 5 CascadeClassifier icermiyor;"
                  " plaka tespiti kontur yontemine dusuruldu.")
        print(f"[AI] Isci kod ozeti: {KOD_OZETI[:12]} pid={os.getpid()}")
        print(f"[AI] Isci hazir: {self.ad} ({self.tip}) "
              f"yuz={'VAR' if self.yuz_tespit else 'YOK'} "
              f"tanima={'VAR' if self.yuz_tanima else 'YOK'} "
              f"plaka={'VAR' if self.plaka_cascade is not None else 'YOK'} "
              f"ocr={'VAR' if OCR_VAR else 'YOK'}")

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
                "kod_ozeti": KOD_OZETI, "pid": os.getpid()}

    # ------------------------------------------------------------------
    # Analiz
    # ------------------------------------------------------------------
    def kare_analiz(self, akis, kare, ts):
        # GRCOFF 2.5.20: yüz, plaka ve diğer sınıflar aktif akışta yoktur.
        g = akis.gorevler & IZINLI_SINIFLAR
        akis.canli_kutular = []
        if "insan" in g:
            self._insan_analiz(akis, kare, ts)
        # v2.4.161: Yakin cekim yuz tespiti AYRI gorev ("yuz"); tam beden
        # "insan" (HOG/yaya) ile bagimsiz. Ikisi de acikken hem uzaktaki
        # yaya hem yakindaki kisi yakalanir.
        if "yuz" in g:
            self._insan_yuzden(akis, kare, ts)
        if "hava_araci" in g or "kara_araci" in g or (
                "insan" in g and self.insan_hog is None):
            self._hareket_analiz(akis, kare, ts)
        try:
            h, w = kare.shape[:2]
            self._kutulari_bildir(akis, w, h, ts)
        except Exception:
            pass

    def _kutulari_bildir(self, akis, kaynak_w, kaynak_h, ts):
        """Canli tespit kutularini ana sunucuya POST /ai/kutular ile
        gonderir (v2.4.7). Sogutmadan bagimsizdir; bos liste de
        gonderilir ki eski kutular temizlensin."""
        kutular = getattr(akis, "canli_kutular", None) or []
        # bos liste ard arda gonderilmesin (bant genisligi)
        if not kutular and not getattr(akis, "_son_kutu_vardi", False):
            return
        akis._son_kutu_vardi = bool(kutular)
        for k in kutular:
            k["kaynak_w"], k["kaynak_h"] = int(kaynak_w), int(kaynak_h)
        govde = {"kamera_id": akis.kamera_id, "ts": ts,
                 "isci": self.ad, "kutular": kutular}
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
    # v2.4.2: Insan tespiti (HOG tam-vucut dedektoru)
    # ------------------------------------------------------------------
    def _insan_analiz(self, akis, kare, ts):
        # v2.4.161: Tam beden (HOG/yaya) tespiti. Yakın çekim yüz tespiti
        # artık AYRI "yuz" görevidir (bkz. kare_analiz + _insan_yuzden);
        # burada çağrılmaz. Böylece yaya ve yakın-yüz bağımsız açılıp kapanır.
        if self.insan_hog is None:
            # OpenCV 5: HOG yok — tam beden hareket blob'u _hareket_analiz'de.
            return
        h, w = kare.shape[:2]
        # HOG icin kucult (hiz): genislik ~640
        olcek = 640.0 / w if w > 640 else 1.0
        kucuk = (cv2.resize(kare, (int(w * olcek), int(h * olcek)))
                 if olcek < 1.0 else kare)
        try:
            kutular, agirliklar = self.insan_hog.detectMultiScale(
                kucuk, winStride=(8, 8), padding=(8, 8), scale=1.05)
        except Exception:
            return
        # v2.5.24: insan hassasiyeti -> güven eşiği (s=50 iken 0.6, nötr)
        _k_insan = getattr(akis, "_olcek", {}).get("insan", 1.0)
        _esik_insan = max(0.2, min(0.9, 0.6 * min(1.5, _k_insan)))
        for i, (x, y, gw, gh) in enumerate(kutular):
            guven = float(agirliklar[i]) if len(agirliklar) > i else 0.0
            if guven < _esik_insan:
                continue
            # orijinal olcege don
            x, y, gw, gh = (int(x / olcek), int(y / olcek),
                            int(gw / olcek), int(gh / olcek))
            self._canli_kutu_ekle(akis, x, y, gw, gh, "insan")
            anahtar = f"insan_{x // 100}_{y // 100}"
            if not akis.sogutma_gecti(anahtar, saniye=12.0):
                continue
            x0, y0 = max(0, x - 15), max(0, y - 15)
            kirp = kare[y0:min(h, y + gh + 15), x0:min(w, x + gw + 15)]
            self._tespit_bildir(akis, "insan", kare, kirp, ts,
                                guven=min(1.0, guven / 2.0))

    def _insan_yuzden(self, akis, kare, ts):
        """Yakın çekimde YuNet yüz tespitiyle 'insan' üretir.

        GİZLİLİK: Bu yol yalnız VARLIK tespitidir — yüz TANIMA (kimlik)
        YAPMAZ; embedding/isim çıkarılmaz, hariçe taşınmaz. Amaç tam-beden
        HOG'un göremediği yakın/üst-beden kadrajında kişiyi yakalamaktır.
        """
        if self.yuz_tespit is None:
            return
        h, w = kare.shape[:2]
        # v2.4.161: "yuz" gorevinin kendi hassasiyeti (insan'dan bagimsiz).
        k = getattr(akis, "_olcek", {}).get("yuz", 1.0)
        esik = max(0.30, min(0.95, 0.7 * min(1.5, k)))
        asgari = max(18, int(36 * min(1.5, k)))
        # YuNet cok BUYUK yuzde (yakin cekim, kadrajin yarisindan fazlasi)
        # zayiflar; tam cozunurlukte bulamazsa kucultulmus karede de dener.
        yuzler = None
        for olcek in (1.0, 0.5):
            try:
                if olcek != 1.0:
                    kk = cv2.resize(kare, (max(1, int(w * olcek)),
                                           max(1, int(h * olcek))))
                    self.yuz_tespit.setInputSize((kk.shape[1], kk.shape[0]))
                    _, bulunan = self.yuz_tespit.detect(kk)
                    if bulunan is not None and len(bulunan):
                        bulunan = bulunan.copy()
                        bulunan[:, :4] /= olcek   # koordinatları orijinale ölçekle
                else:
                    self.yuz_tespit.setInputSize((w, h))
                    _, bulunan = self.yuz_tespit.detect(kare)
            except Exception:
                bulunan = None
            if bulunan is not None and len(bulunan):
                yuzler = bulunan
                break
        # Teşhis (kısıtlı): kaç aday, en iyi güven — log'dan görülebilsin.
        if akis.sogutma_gecti("yuz_teshis", saniye=8.0):
            try:
                _n = 0 if yuzler is None else len(yuzler)
                _iyi = (max(float(y[-1]) for y in yuzler) if _n else 0.0)
                print("[AI] yuz tespit: %d aday, en_iyi=%.2f (esik=%.2f) kam=%s"
                      % (_n, _iyi, esik, akis.kamera_id))
            except Exception:
                pass
        if yuzler is None:
            return
        for yuz in yuzler:
            x, y, gw, gh = [int(v) for v in yuz[:4]]
            guven = float(yuz[-1])
            if guven < esik or gw < asgari or gh < asgari:
                continue
            # Yüzden kaba bir gövde kutusu kestir (yüz ~ gövdenin üst kısmı):
            # genişliği yanlara, yüksekliği aşağı doğru genişlet, kareye kırp.
            bx = max(0, int(x - gw * 0.6))
            by = max(0, int(y - gh * 0.3))
            bw = min(w - bx, int(gw * 2.2))
            bh = min(h - by, int(gh * 4.5))
            self._canli_kutu_ekle(akis, bx, by, bw, bh, "insan")
            anahtar = f"insan_yuz_{x // 100}_{y // 100}"
            if not akis.sogutma_gecti(anahtar, saniye=12.0):
                continue
            kirp = kare[by:by + bh, bx:bx + bw]
            self._tespit_bildir(akis, "insan", kare, kirp, ts,
                                guven=min(1.0, guven))

    # ------------------------------------------------------------------
    # v2.4.2: Hareket tabanli hava araci / kara araci tespiti
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
        konturlar, _ = cv2.findContours(maske, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)
        kare_alani = float(h * w)
        # v2.5.24: sınıf başına alan alt-sınır ölçeği (s=50 -> k=1.0 nötr;
        # yüksek hassasiyet -> daha küçük alt sınır -> daha çok tespit).
        _olc = getattr(akis, "_olcek", {})
        _kh = _olc.get("hava_araci", 1.0)
        _kk = _olc.get("kara_araci", 1.0)
        _ki = _olc.get("insan", 1.0)
        for c in konturlar:
            x, y, gw, gh = cv2.boundingRect(c)
            alan = gw * gh
            oran = gw / float(gh) if gh else 0
            merkez_y = y + gh / 2.0
            tur = None
            if ("hava_araci" in akis.gorevler
                    and merkez_y < h * 0.55
                    and 0.0004 * _kh * kare_alani < alan < 0.06 * kare_alani
                    and 0.5 <= oran <= 3.5):
                tur = "hava_araci"
            elif ("kara_araci" in akis.gorevler
                    and merkez_y >= h * 0.45
                    and 0.008 * _kk * kare_alani < alan < 0.5 * kare_alani
                    and 1.1 <= oran <= 4.5):
                tur = "kara_araci"
            elif ("insan" in akis.gorevler and self.insan_hog is None
                    and merkez_y >= h * 0.35
                    and 0.002 * _ki * kare_alani < alan < 0.15 * kare_alani
                    and 0.2 <= oran <= 0.75):
                # OpenCV 5 HOG geri cekilmesi: dikey (boy > en) hareketli
                # bloblar insan adayi sayilir
                tur = "insan"
            if tur is None:
                continue
            # doluluk filtresi: cok seyrek konturlar gurultudur
            if cv2.contourArea(c) / float(alan) < 0.3:
                continue
            self._canli_kutu_ekle(akis, x, y, gw, gh, tur)
            anahtar = f"{tur}_{x // 120}_{y // 120}"
            sogutma = 8.0 if tur == "hava_araci" else 15.0
            if not akis.sogutma_gecti(anahtar, saniye=sogutma):
                continue
            x0, y0 = max(0, x - 20), max(0, y - 20)
            kirp = kare[y0:min(h, y + gh + 20), x0:min(w, x + gw + 20)]
            self._tespit_bildir(akis, tur, kare, kirp, ts, guven=0.55)

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
                                                 veri.get("kutu")))
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
