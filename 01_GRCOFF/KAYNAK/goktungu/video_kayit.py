# -*- coding: utf-8 -*-
"""GÖKTUNGU — VİDEO KAYDI (v2.4.210).

Kullanıcı isteği: M50 canlı görüntü penceresinde "Video kayıt seçeneği".

Kaynak, Merkez'in kendi MJPEG vekili (`/kamera/<id>`, port 8801)'dir:
böylece kayıt, operatörün gördüğü kareyle (AI anotasyonları dahil)
birebir aynıdır ve cihaza ikinci bir RTSP oturumu açılmaz.

ffmpeg'e BAĞIMLI DEĞİLDİR (Windows kurulumlarında ffmpeg bulunmayabilir;
bkz. video_proxy.py v2.4.167). Kare akışı Python'da ayrıştırılır (JPEG
SOI/EOI), OpenCV `VideoWriter` (MJPG, .avi) ile yazılır. OpenCV yoksa
kayıt başlatılamaz ve anlamlı hata döner.

Dosyalar veri kökünde `kayitlar/video/` altına düşer:
    <etiket>_<YYYYmmdd_HHMMSS>.avi
"""
from __future__ import annotations

import os
import re
import threading
import time
import urllib.request
from typing import Any, Dict, Optional

try:
    import cv2  # type: ignore
    import numpy as _np  # type: ignore
except Exception:  # pragma: no cover - ortama bagli
    cv2 = None
    _np = None


class _Kayit:
    def __init__(self, kamera_id: int, url: str, dosya: str, fps: float,
                 etiket: str, konsol):
        self.kamera_id = int(kamera_id)
        self.url = url
        self.dosya = dosya
        self.fps = max(1.0, min(30.0, float(fps or 15)))
        self.etiket = etiket
        self.konsol = konsol
        self.baslangic = time.time()
        self.kare = 0
        self.hata = ""
        self.calisiyor = True
        self._is = threading.Thread(target=self._dongu, daemon=True,
                                    name="video-kayit-%d" % self.kamera_id)
        self._is.start()

    def durdur(self) -> None:
        self.calisiyor = False

    def _dongu(self) -> None:
        yazici = None
        try:
            istek = urllib.request.Request(self.url, headers={"User-Agent": "goktungu-kayit"})
            with urllib.request.urlopen(istek, timeout=15) as akis:
                tampon = b""
                son_yazim = 0.0
                while self.calisiyor:
                    parca = akis.read(65536)
                    if not parca:
                        break
                    tampon += parca
                    while True:
                        bas = tampon.find(b"\xff\xd8")
                        if bas < 0:
                            tampon = tampon[-2:]
                            break
                        son = tampon.find(b"\xff\xd9", bas + 2)
                        if son < 0:
                            tampon = tampon[bas:]
                            break
                        jpg = tampon[bas:son + 2]
                        tampon = tampon[son + 2:]
                        simdi = time.time()
                        # Vekil zaten fps tavanina gore yayinlar; yine de
                        # yaziciya verilen hizi asmamak icin seyrelt.
                        if simdi - son_yazim < 1.0 / self.fps * 0.9:
                            continue
                        kare = cv2.imdecode(_np.frombuffer(jpg, dtype=_np.uint8), cv2.IMREAD_COLOR)
                        if kare is None:
                            continue
                        if yazici is None:
                            h, w = kare.shape[:2]
                            yazici = cv2.VideoWriter(self.dosya, cv2.VideoWriter_fourcc(*"MJPG"),
                                                     self.fps, (w, h))
                            if not yazici.isOpened():
                                self.hata = "kayit dosyasi acilamadi"
                                self.calisiyor = False
                                break
                            self._boyut = (w, h)
                        else:
                            if kare.shape[1] != self._boyut[0] or kare.shape[0] != self._boyut[1]:
                                kare = cv2.resize(kare, self._boyut)
                        yazici.write(kare)
                        self.kare += 1
                        son_yazim = simdi
        except Exception as exc:
            self.hata = "%s: %s" % (type(exc).__name__, exc)
        finally:
            self.calisiyor = False
            try:
                if yazici is not None:
                    yazici.release()
            except Exception:
                pass
            if self.konsol:
                self.konsol("KAYIT", "Video kaydi bitti: %s (%d kare%s)"
                            % (os.path.basename(self.dosya), self.kare,
                               (", hata: " + self.hata) if self.hata else ""),
                            "uyari" if self.hata else "bilgi")

    def durum(self) -> Dict[str, Any]:
        try:
            boyut = os.path.getsize(self.dosya)
        except OSError:
            boyut = 0
        return {"kamera_id": self.kamera_id, "dosya": os.path.basename(self.dosya),
                "yol": self.dosya, "etiket": self.etiket, "baslangic": self.baslangic,
                "sure_sn": round(time.time() - self.baslangic, 1), "kare": self.kare,
                "boyut": boyut, "calisiyor": self.calisiyor, "hata": self.hata}


class VideoKaydedici:
    """Kamera başına tek kayıt; vekil akışından dosyaya yazar."""

    def __init__(self, konsol=None, veri_koku: str = ".", port: int = 8801):
        self.konsol = konsol
        self.dizin = os.path.join(str(veri_koku or "."), "kayitlar", "video")
        self.port = int(port or 8801)
        self._kayitlar: Dict[int, _Kayit] = {}
        self._kilit = threading.Lock()

    @staticmethod
    def _temiz_etiket(etiket: str) -> str:
        e = re.sub(r"[^0-9A-Za-z_.-]+", "_", str(etiket or "kamera")).strip("_")
        return (e or "kamera")[:48]

    def baslat(self, kamera_id: int, etiket: str = "", fps: float = 15.0) -> Dict[str, Any]:
        if cv2 is None or _np is None:
            return {"tamam": False, "hata": "OpenCV yok; video kaydi kullanilamaz"}
        try:
            kid = int(kamera_id)
        except (TypeError, ValueError):
            return {"tamam": False, "hata": "kamera_id gecersiz"}
        with self._kilit:
            mevcut = self._kayitlar.get(kid)
            if mevcut and mevcut.calisiyor:
                return {"tamam": True, "zaten": True, "kayit": mevcut.durum()}
            try:
                os.makedirs(self.dizin, exist_ok=True)
            except OSError as exc:
                return {"tamam": False, "hata": "kayit dizini olusturulamadi: %s" % exc}
            ad = "%s_%s.avi" % (self._temiz_etiket(etiket or ("kamera_%d" % kid)),
                                time.strftime("%Y%m%d_%H%M%S"))
            dosya = os.path.join(self.dizin, ad)
            url = "http://127.0.0.1:%d/kamera/%d?kayit=1" % (self.port, kid)
            k = _Kayit(kid, url, dosya, fps, etiket, self.konsol)
            self._kayitlar[kid] = k
        if self.konsol:
            self.konsol("KAYIT", "Video kaydi basladi: %s" % ad, "basari")
        return {"tamam": True, "kayit": k.durum()}

    def durdur(self, kamera_id: int) -> Dict[str, Any]:
        try:
            kid = int(kamera_id)
        except (TypeError, ValueError):
            return {"tamam": False, "hata": "kamera_id gecersiz"}
        with self._kilit:
            k = self._kayitlar.get(kid)
        if not k:
            return {"tamam": False, "hata": "aktif kayit yok"}
        k.durdur()
        return {"tamam": True, "kayit": k.durum()}

    def durumlar(self) -> Dict[str, Any]:
        with self._kilit:
            olu = [kid for kid, k in self._kayitlar.items()
                   if not k.calisiyor and time.time() - k.baslangic > 3600]
            for kid in olu:
                self._kayitlar.pop(kid, None)
            return {str(kid): k.durum() for kid, k in self._kayitlar.items()}

    def hepsini_durdur(self) -> None:
        with self._kilit:
            for k in self._kayitlar.values():
                k.durdur()
