# -*- coding: utf-8 -*-
"""GÖKTUNGU MERKEZ — canlı kamera karesi köprüsü (FAZ19-IS60).

## SORUN

Kamera kullanıcının sahasındaki makinededir; GÖKTUNGU merkezde çalışır.
Köprü kareyi üretir ama tarayıcı onu göremez: arayüz
`window.location.hostname + ":8801"` adresine bağlanır ve merkez kipinde
o adreste hiçbir servis yoktur (`VideoVekili.calistir()` bilinçli olarak
boş döner). Ölçüldü: köprü günlüğünde `Izleyici kalmadi` — yani akışı
tüketen hiç kimse yok.

## NEDEN BU MODÜL AYRI

`mk_akis` bir MAVLink kanalıdır: **iki yönlüdür** (GCS komut yazar),
donanım bağlantısı taşır ve kesinti tamponu tutar. Video ise
**tek yönlüdür** ve tamponlanmamalıdır. Bunları tek sınıfta birleştirmek
MAVLink yolunu kırılganlaştırırdı; ayrı tutmanın bedeli ise küçük bir
kod tekrarıdır.

## NEDEN TAMPON YOK

`mk_akis` köprüden gelen byte'ları GCS bağlanana kadar biriktirir; orada
DOĞRUDUR, çünkü ilk HEARTBEAT kaybolursa bağlantı hiç kurulmaz.
Video için TERSİ geçerlidir: gecikmiş kare, operatörü geçmiş görüntüye
bakarak karar vermeye iter. App henüz dinlemiyorsa kare ATILIR.

## PORT SAHİPLİĞİ

`mk_akis`'te ölçülmüş bir kusur vardı: merkez kendi portunu bildiriyor,
GCS aynı portu bind etmeye çalışıp `[Errno 98] Address already in use`
alıyordu. Çözüm, App'in portu ÖNCE kendisinin bind etmesi ve merkeze
bildirmesiydi. Burada aynı yol izlenir — o tuzağa ikinci kez düşmemek
için `app_port` ZORUNLUDUR.
"""
from __future__ import annotations

import base64
import contextlib
import socket
import threading
import time
from typing import Any

YEREL_ADRES = "127.0.0.1"

# Eş zamanlı canlı kamera tavanı (merkez geneli). Köprü tarafında da
# `EN_FAZLA_CANLI = 2` sınırı vardır; buradaki sınır merkezi korur:
# hatalı bir istemci döngüsü yüzlerce kanal açamaz.
GENEL_ENUST_KANAL = 64

# Bir örneğin aynı anda açabileceği canlı kamera sayısı.
ORNEK_BASINA_ENUST_KANAL = 4

# Kanal bu süre boyunca köprüden hiç kare görmezse terk edilmiş sayılır.
# 60 sn seçildi: köprü 10 fps gönderir, 60 saniye sessizlik akışın
# gerçekten durduğu anlamına gelir. `mk_akis`'teki 900 sn burada
# fazlaydı — video kanalı MAVLink kanalı kadar uzun ömürlü değildir.
TERK_ZAMAN_ASIMI_SN = 60.0

# Tek karenin kabul edilen en büyük boyutu. Köprü tarafında
# `TASIMA_TAVANI = 60 KB` uygulanır; buradaki tavan biraz yüksek
# tutuldu ki eski bir köprü sürümünden gelen kare sessizce düşmesin,
# ama UDP datagram sınırının (65507) altında kalsın.
KARE_ENUST_BYTE = 63 * 1024


class VideoKanali:
    """Tek bir canlı kameranın merkez tarafı UDP ucu."""

    __slots__ = ("ornek_id", "kamera_id", "soket", "app_es", "acilma_ts",
                 "kare_sayisi", "byte_sayisi", "dusen_kare", "son_kare_ts",
                 "son_hata")

    def __init__(self, ornek_id: int, kamera_id: int):
        self.ornek_id = int(ornek_id)
        self.kamera_id = int(kamera_id)
        self.soket: socket.socket | None = None
        self.app_es: tuple[str, int] | None = None
        self.acilma_ts = time.time()
        self.kare_sayisi = 0
        self.byte_sayisi = 0
        self.dusen_kare = 0
        self.son_kare_ts = 0.0
        self.son_hata = ""

    def ozet(self) -> dict[str, Any]:
        return {
            "ornek_id": self.ornek_id,
            "kamera_id": self.kamera_id,
            "app_port": int(self.app_es[1]) if self.app_es else 0,
            "kare": self.kare_sayisi,
            "byte": self.byte_sayisi,
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

    # ------------------------------------------------------------------
    def kanal(self, ornek_id: int, kamera_id: int) -> VideoKanali | None:
        with self._kilit:
            return self._kanallar.get((int(ornek_id), int(kamera_id)))

    def kanal_ac(self, ornek_id: int, kamera_id: int,
                 app_port: int) -> tuple[dict | None, str | None]:
        """App'in bind ettiği porta yazacak UDP ucunu ayırır.

        `app_port` ZORUNLUDUR. Merkezin kendi portunu bildirip App'in onu
        bind etmesini beklemek, `mk_akis`'te ölçülmüş
        `Address already in use` kusurunun ta kendisidir.
        """
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
        # Aynı kamera yeniden açılıyorsa (kullanıcı kapat→aç yaptıysa)
        # eskisi temiz kapatılır; aksi halde iki soket aynı akışı yazar
        # ve tarayıcı karışık kare sırası görür.
        if eski is not None:
            self.kanal_kapat(oid, kid)
        k = VideoKanali(oid, kid)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Port 0: çekirdek boş port seçer. Sabit aralık kullanmak
            # iki kanalın çakışmasına yol açar.
            s.bind((YEREL_ADRES, 0))
            # Gönderim tamponu bir karenin en az iki katı olmalı; aksi
            # halde yoğun anlarda `sendto` bloke olur ve WSS okuma
            # döngüsünü yavaşlatır.
            with contextlib.suppress(OSError):
                s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1 << 20)
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
        """Köprüden gelen kareyi App'in UDP portuna yazar.

        WSS röle döngüsünde çağrılır; ASLA istisna fırlatmaz. Bir kare
        yüzünden köprü oturumunun kopması kabul edilemez.

        Kanal açık değilse kare ATILIR: App izleyiciyi kapattıktan sonra
        köprüden yolda olan kareler gelmeye devam eder ve bu normaldir.
        """
        k = self.kanal(ornek_id, kamera_id)
        if k is None or k.soket is None or k.app_es is None:
            return 0
        try:
            # validate=True ZORUNLU. `False` ile geçersiz karakterler
            # SESSİZCE atlanır; bozuk veri geçerli sanılıp App'e yazılır,
            # tarayıcı bozuk görüntü gösterir ve operatör nedeni asla
            # anlayamaz. Ölçüldü: 3000 baytlık geçersiz girdi sessizce
            # 2250 baytlık çöpe dönüştü ve zincirin sonuna kadar taşındı.
            veri = base64.b64decode(veri_b64 or "", validate=True)
        except Exception as e:
            k.dusen_kare += 1
            k.son_hata = f"Kare çözülemedi (base64): {type(e).__name__}"
            return 0
        if not veri:
            return 0
        # JPEG imzası. Köprü her zaman JPEG yollar; imza tutmuyorsa
        # taşıma katmanında uyumsuzluk vardır. Sessizce geçirmek
        # yukarıdakiyle aynı teşhis edilemez duruma yol açar.
        if veri[:2] != b"\xff\xd8":
            k.dusen_kare += 1
            k.son_hata = "Kare JPEG değil (köprü sürümü uyumsuz olabilir)"
            return 0
        if len(veri) > KARE_ENUST_BYTE:
            # Tek datagrama sığmaz. Köprü tarafında zaten küçültülmüş
            # olmalıydı; buraya düşüyorsa köprü eskidir. Kareyi atmak,
            # `Message too long` ile akışı durdurmaktan iyidir.
            k.dusen_kare += 1
            k.son_hata = (f"Kare çok büyük ({len(veri)} bayt); "
                          "köprüyü güncelleyin")
            return 0
        try:
            n = k.soket.sendto(veri, k.app_es)
        except Exception as e:
            k.dusen_kare += 1
            k.son_hata = f"{type(e).__name__}: {e}"
            return 0
        k.kare_sayisi += 1
        k.byte_sayisi += n
        k.son_kare_ts = time.time()
        return n

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
