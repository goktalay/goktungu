# -*- coding: utf-8 -*-
"""GÖKTUNGU — VİDEO KAYDI (v2.4.210).

Kullanıcı isteği: M50 canlı görüntü penceresinde "Video kayıt seçeneği".

Kaynak, Merkez'in kendi MJPEG vekilidir (`VideoProxy.yayin_al`): kayıt
SÜREÇ İÇİ kare aboneliğiyle yapılır (mjpeg_yaz ile aynı `kosul`/`son_kare`
deseni). Böylece kayıt, operatörün gördüğü kareyle (AI anotasyonları dahil)
birebir aynıdır ve cihaza ikinci bir RTSP oturumu açılmaz.

v2.4.211 ÖLÇÜLEN KUSUR: ilk sürüm `http://127.0.0.1:8801/kamera/<id>`
adresine bağlanıyordu; vekil bu kurulumda AYRI 8801 dinleyicisi
açmıyor (canlı yayın aynı-origin HTTP yolunda), sonuç
"[WinError 10061] bağlantı reddedildi" idi. Ağ hiç kullanılmaz artık.

ffmpeg'e BAĞIMLI DEĞİLDİR (Windows kurulumlarında ffmpeg bulunmayabilir;
bkz. video_proxy.py v2.4.167). Kareler OpenCV `VideoWriter` (MJPG, .avi)
ile yazılır. OpenCV yoksa kayıt başlatılamaz ve anlamlı hata döner.

Dosyalar veri kökünde `kayitlar/video/` altına düşer:
    <etiket>_<YYYYmmdd_HHMMSS>.avi
"""
from __future__ import annotations

import os
import re
import threading
import time
from typing import Any, Dict, Optional

try:
    import cv2  # type: ignore
    import numpy as _np  # type: ignore
except Exception:  # pragma: no cover - ortama bagli
    cv2 = None
    _np = None


class _Kayit:
    def __init__(self, kamera_id: int, yayin, dosya: str, fps: float,
                 etiket: str, konsol):
        self.kamera_id = int(kamera_id)
        self.yayin = yayin
        self.dosya = dosya
        self.fps = max(1.0, min(30.0, float(fps or 15)))
        self.etiket = etiket
        self.konsol = konsol
        self.baslangic = time.time()
        self.kare = 0
        self.hata = ""
        self.calisiyor = True
        self._dur = False      # durdurma istegi; `calisiyor` yalniz dosya kapaninca duser
        self._is = threading.Thread(target=self._dongu, daemon=True,
                                    name="video-kayit-%d" % self.kamera_id)
        self._is.start()

    def durdur(self) -> None:
        self._dur = True
        with self.yayin.kosul:
            self.yayin.kosul.notify_all()
        # Dosya kapanana kadar (en fazla 4 sn) bekle: donen durum kesindir.
        try:
            self._is.join(4.0)
        except Exception:
            pass

    def _dongu(self) -> None:
        yazici = None
        y = self.yayin
        try:
            y.izleyici_ekle()
        except Exception:
            pass
        try:
            if not y.ilk_kare_bekle(12.0):
                self.hata = y.hata or "kaynak kare uretmedi (zaman asimi)"
                return
            son_no = 0
            son_yazim = 0.0
            bos_sayac = 0
            while not self._dur and (y.calisiyor or y.son_kare):
                with y.kosul:
                    if y.kare_no == son_no:
                        y.kosul.wait(timeout=2.0)
                    jpg = y.son_kare
                    no = y.kare_no
                if jpg is None or no == son_no:
                    bos_sayac += 1
                    if not y.calisiyor or bos_sayac > 30:   # ~60 sn kare yok
                        self.hata = self.hata or "kaynak kare uretmiyor"
                        break
                    continue
                bos_sayac = 0
                son_no = no
                simdi = time.time()
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
                        self.hata = "kayit dosyasi acilamadi (VideoWriter MJPG)"
                        break
                    self._boyut = (w, h)
                elif kare.shape[1] != self._boyut[0] or kare.shape[0] != self._boyut[1]:
                    kare = cv2.resize(kare, self._boyut)
                yazici.write(kare)
                self.kare += 1
                son_yazim = simdi
        except Exception as exc:
            self.hata = "%s: %s" % (type(exc).__name__, exc)
        finally:
            # Once dosya kapatilir (baslik/indeks yazilir), SONRA durum
            # "bitti"ye ceker: durum() calisiyor=False gordugunde dosya hazirdir.
            try:
                if yazici is not None:
                    yazici.release()
            except Exception:
                pass
            try:
                y.izleyici_cikar()
            except Exception:
                pass
            self.calisiyor = False
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

    def __init__(self, konsol=None, veri_koku: str = ".", proxy=None):
        self.konsol = konsol
        self.dizin = os.path.join(str(veri_koku or "."), "kayitlar", "video")
        self.proxy = proxy          # VideoProxy (surec ici kare kaynagi)
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
        if self.proxy is None:
            return {"tamam": False, "hata": "video vekili yok"}
        try:
            y = self.proxy.yayin_al(kid)     # kilit disinda: kaynak acmak surebilir
        except Exception as exc:
            y = None
            hata = "%s: %s" % (type(exc).__name__, exc)
        else:
            hata = ""
        if y is None:
            try:
                hata = hata or self.proxy.son_hata(kid) or "kaynak acilamadi"
            except Exception:
                hata = hata or "kaynak acilamadi"
            return {"tamam": False, "hata": hata}
        with self._kilit:
            mevcut = self._kayitlar.get(kid)
            if mevcut and mevcut.calisiyor:
                return {"tamam": True, "zaten": True, "kayit": mevcut.durum()}
            k = _Kayit(kid, y, dosya, fps, etiket, self.konsol)
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
