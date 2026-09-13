# -*- coding: utf-8 -*-
"""KonsolLog: backend'in onemli geri bildirimlerini arayuz konsoluna akitir.

log(kaynak, mesaj, seviye) -> tampona ekler; yayin dongusu her turda
birikmis yeni satirlari 'konsol' alaninda istemcilere gonderir.
"""
import collections
import threading
import time


class KonsolLog:
    """Dairesel tamponlu, thread-guvenli konsol log sistemi."""

    def __init__(self, kapasite=200):
        # arayuze ilk baglanan gecmisi de alir
        self._tampon = collections.deque(maxlen=kapasite)
        self._sira = 0    # artan satir no (istemci ayni satiri iki kez basmasin)
        self._kilit = threading.Lock()

    def log(self, kaynak, mesaj, seviye="bilgi"):
        """Konsola satir ekle. seviye: bilgi | uyari | hata | basari"""
        with self._kilit:
            self._sira += 1
            self._tampon.append({
                "no": self._sira,
                "t": time.time(),
                "kaynak": kaynak,
                "mesaj": mesaj,
                "seviye": seviye,
            })
        print(f"[{kaynak}] {mesaj}")

    # Fonksiyon gibi cagrilabilir: konsol("KAYNAK", "mesaj", "seviye")
    __call__ = log

    def yeni_satirlar(self, son_no):
        """son_no'dan buyuk numarali satirlari dondurur."""
        with self._kilit:
            return [s for s in self._tampon if s["no"] > son_no]

    def tum_satirlar(self):
        """Tampondaki tum satirlarin kopyasini dondurur (yayin icin)."""
        with self._kilit:
            return list(self._tampon)

    @property
    def son_sira(self):
        with self._kilit:
            return self._sira
