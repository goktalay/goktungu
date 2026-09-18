# -*- coding: utf-8 -*-
"""GÖKTUNGU MERKEZ — canlı kamera karesi köprüsü (IS140, eski FAZ19-IS60).

## SORUN

Kamera kullanıcının sahasındaki makinededir; GÖKTUNGU merkezde çalışır.
Merkez sunucu ile köprü ayrı ağlarda ve ayrı IP'lerdedir; köprüye içeri
doğru bağlantı kurulamaz. Köprünün merkeze açık tek yolu kendi WSS ajan
bağlantısıdır. Bu modül köprüden `{"tur":"video_kare"}` ile gelen JPEG
karelerini merkezde çalışan GRCON uygulamasının (App) UDP portuna teslim
eder; App bunları `/app/kamera/<id>` MJPEG akışı olarak tarayıcıya sunar.

2026-09-17 (IS140): IS71'de kaldırılan modül geri getirildi ve BÜYÜK KARE
desteği eklendi. Önceki sürüm 63 KB üstünü düşürüyordu (UDP datagram
sınırı). Artık büyük kareler parçalanır:

    GKVK + kare_no(uint32) + parca_no(uint16) + parca_sayisi(uint16) + veri

App tarafı (`saha_vekil.KareBirlestirici`) parçaları birleştirir. 60000
bayt ve altındaki kareler eski biçimde (ham JPEG datagram) gider; böylece
eski App sürümleri küçük karelerle çalışmaya devam eder.

## NEDEN TAMPON YOK

Video tek yönlüdür ve tamponlanmamalıdır: gecikmiş kare operatörü
geçmiş görüntüye bakarak karar vermeye iter. App henüz dinlemiyorsa
kare ATILIR.

## PORT SAHİPLİĞİ

App portu ÖNCE kendisi bind eder ve merkeze bildirir; `app_port`
ZORUNLUDUR (mk_akis'te ölçülmüş `Address already in use` kusuru).
"""
from __future__ import annotations

import base64
import contextlib
import socket
import struct
import threading
import time
from typing import Any

YEREL_ADRES = "127.0.0.1"

# Eş zamanlı canlı kamera tavanı (merkez geneli).
GENEL_ENUST_KANAL = 64
# Bir örneğin aynı anda açabileceği canlı kamera sayısı.
ORNEK_BASINA_ENUST_KANAL = 4
# Kanal bu süre boyunca köprüden hiç kare görmezse terk edilmiş sayılır.
TERK_ZAMAN_ASIMI_SN = 60.0
# Tek karenin kabul edilen en büyük boyutu (parçalanarak taşınır).
KARE_ENUST_BYTE = 4 * 1024 * 1024
# Parça yükü: UDP datagram tavanının (65507) güvenli altında.
PARCA_BYTE = 60000
KARE_MAGIC = b"GKVK"
BASLIK_BICIM = "!IHH"
BASLIK_BOY = 4 + struct.calcsize(BASLIK_BICIM)
KALDIRILDI_MESAJ = ""


def kare_parcala(veri: bytes, kare_no: int) -> list[bytes]:
    """Kareyi datagramlara böler. Küçük kare ham JPEG olarak tek parça."""
    if len(veri) <= PARCA_BYTE:
        return [veri]
    parcalar = [veri[i:i + PARCA_BYTE] for i in range(0, len(veri), PARCA_BYTE)]
    say = len(parcalar)
    return [KARE_MAGIC + struct.pack(BASLIK_BICIM, kare_no & 0xFFFFFFFF, i, say) + p
            for i, p in enumerate(parcalar)]


class VideoKanali:
    """Tek bir canlı kameranın merkez tarafı UDP ucu."""

    __slots__ = ("ornek_id", "kamera_id", "soket", "app_es", "acilma_ts",
                 "kare_sayisi", "byte_sayisi", "dusen_kare", "son_kare_ts",
                 "son_hata", "parca_sayisi")

    def __init__(self, ornek_id: int, kamera_id: int):
        self.ornek_id = int(ornek_id)
        self.kamera_id = int(kamera_id)
        self.soket: socket.socket | None = None
        self.app_es: tuple[str, int] | None = None
        self.acilma_ts = time.time()
        self.kare_sayisi = 0
        self.byte_sayisi = 0
        self.dusen_kare = 0
        self.parca_sayisi = 0
        self.son_kare_ts = 0.0
        self.son_hata = ""

    def ozet(self) -> dict[str, Any]:
        return {
            "ornek_id": self.ornek_id,
            "kamera_id": self.kamera_id,
            "app_port": int(self.app_es[1]) if self.app_es else 0,
            "kare": self.kare_sayisi,
            "byte": self.byte_sayisi,
            "parca": self.parca_sayisi,
            "dusen": self.dusen_kare,
            "yas_sn": round(time.time() - self.acilma_ts, 1),
            "son_kare_once_sn": (round(time.time() - self.son_kare_ts, 1)
                                 if self.son_kare_ts else None),
            "son_hata": self.son_hata,
        }


class VideoKopruleyici:
    """Köprüden gelen kareleri App sürecine UDP ile teslim eder."""

    def __init__(self):
        self._kanallar: dict[tuple[int, int], VideoKanali] = {}
        self._kilit = threading.Lock()
        self._sayac = 0

    # ------------------------------------------------------------------
    def kanal(self, ornek_id: int, kamera_id: int) -> VideoKanali | None:
        with self._kilit:
            return self._kanallar.get((int(ornek_id), int(kamera_id)))

    def kanal_ac(self, ornek_id: int, kamera_id: int,
                 app_port: int) -> tuple[dict | None, str | None]:
        """App'in bind ettiği porta yazacak UDP ucunu ayırır (`app_port` zorunlu)."""
        oid, kid = int(ornek_id), int(kamera_id)
        try:
            ap = int(app_port or 0)
        except Exception:
            ap = 0
        if ap <= 0 or ap > 65535:
            return None, "app_port zorunlu (App portu kendisi bind eder)"
        with self._kilit:
            if len(self._kanallar) >= GENEL_ENUST_KANAL:
                return None, "Merkez canlı video kanalı sınırı aşıldı"
            ornek_sayi = sum(1 for k in self._kanallar if k[0] == oid)
            eski = self._kanallar.get((oid, kid))
            if eski is None and ornek_sayi >= ORNEK_BASINA_ENUST_KANAL:
                return None, ("Bu sunucu için eş zamanlı canlı kamera "
                              f"sınırı aşıldı ({ORNEK_BASINA_ENUST_KANAL})")
        if eski is not None:
            self.kanal_kapat(oid, kid)
        k = VideoKanali(oid, kid)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.bind((YEREL_ADRES, 0))
            with contextlib.suppress(OSError):
                s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 << 20)
        except Exception as e:
            with contextlib.suppress(Exception):
                s.close()
            return None, f"UDP portu ayrılamadı: {e}"
        k.soket = s
        k.app_es = (YEREL_ADRES, ap)
        with self._kilit:
            self._kanallar[(oid, kid)] = k
        return k.ozet(), None

    def kanal_kapat(self, ornek_id: int, kamera_id: int) -> bool:
        oid, kid = int(ornek_id), int(kamera_id)
        with self._kilit:
            k = self._kanallar.pop((oid, kid), None)
        if k is None:
            return False
        if k.soket is not None:
            with contextlib.suppress(Exception):
                k.soket.close()
        return True

    def ornek_kapat(self, ornek_id: int) -> int:
        """Bir örneğin tüm kanallarını kapatır (köprü ayrıldığında)."""
        oid = int(ornek_id)
        with self._kilit:
            anahtarlar = [a for a in self._kanallar if a[0] == oid]
        for _, kid in anahtarlar:
            self.kanal_kapat(oid, kid)
        return len(anahtarlar)

    # ------------------------------------------------------------------
    def kopruden_geldi(self, ornek_id: int, kamera_id: int,
                       veri_b64: str) -> int:
        """Köprüden gelen kareyi (gerekirse parçalayarak) App'e yazar.

        WSS röle döngüsünde çağrılır; ASLA istisna fırlatmaz. Kanal açık
        değilse kare ATILIR (App izleyiciyi kapattıktan sonra yolda olan
        kareler normaldir).
        """
        k = self.kanal(ornek_id, kamera_id)
        if k is None or k.soket is None or k.app_es is None:
            return 0
        try:
            veri = base64.b64decode(veri_b64 or "", validate=True)
        except Exception as e:
            k.dusen_kare += 1
            k.son_hata = f"Kare çözülemedi (base64): {type(e).__name__}"
            return 0
        if not veri:
            return 0
        if veri[:2] != b"\xff\xd8":
            k.dusen_kare += 1
            k.son_hata = "Kare JPEG değil (köprü sürümü uyumsuz olabilir)"
            return 0
        if len(veri) > KARE_ENUST_BYTE:
            k.dusen_kare += 1
            k.son_hata = f"Kare çok büyük ({len(veri)} bayt); genişliği düşürün"
            return 0
        self._sayac += 1
        toplam = 0
        try:
            for p in kare_parcala(veri, self._sayac):
                toplam += k.soket.sendto(p, k.app_es)
                k.parca_sayisi += 1
        except Exception as e:
            k.dusen_kare += 1
            k.son_hata = f"{type(e).__name__}: {e}"
            return 0
        k.kare_sayisi += 1
        k.byte_sayisi += toplam
        k.son_kare_ts = time.time()
        if self._sayac % 500 == 0:
            with contextlib.suppress(Exception):
                self.terk_edilenleri_topla()
        return toplam

    # ------------------------------------------------------------------
    def terk_edilenleri_topla(self) -> int:
        """Uzun süre kare görmeyen kanalları kapatır."""
        simdi = time.time()
        with self._kilit:
            adaylar = [
                (a, k) for a, k in self._kanallar.items()
                if simdi - (k.son_kare_ts or k.acilma_ts) > TERK_ZAMAN_ASIMI_SN
            ]
        for (oid, kid), _ in adaylar:
            self.kanal_kapat(oid, kid)
        return len(adaylar)

    def durum(self, ornek_id: int | None = None) -> list[dict[str, Any]]:
        with self._kilit:
            kanallar = list(self._kanallar.values())
        if ornek_id is not None:
            oid = int(ornek_id)
            kanallar = [k for k in kanallar if k.ornek_id == oid]
        return [k.ozet() for k in kanallar]


# Merkez genelinde tek örnek (`mk_akis.AKIS` ile aynı kalıp).
VIDEO = VideoKopruleyici()
