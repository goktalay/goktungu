# -*- coding: utf-8 -*-
"""EtiketYoneticisi: ML egitim verisi icin iz etiketleri (Faz 2).

Etiketler kayitlar/etiketler.csv dosyasinda tutulur. Her satir bir izin
bir kayit dosyasindaki sinif etiketini temsil eder:

    kayit_dosyasi,iz_id,baslangic_t,bitis_t,sinif,guven,kaynak,notlar

- sinif : DRON | KUS | INSAN | ARAC | KLUTTER
- guven : kesin | yuksek | dusuk (egitimde yalniz kesin+yuksek kullanilir)
- kaynak: operator | dataflash_eslesme | gozlemci | senaryo
"""
import csv
import os
import threading
import time

from .sabitler import KAYIT_KLASORU

ETIKET_DOSYASI = "etiketler.csv"
ETIKET_ALANLAR = ["kayit_dosyasi", "iz_id", "baslangic_t", "bitis_t",
                  "sinif", "guven", "kaynak", "notlar"]
GECERLI_SINIFLAR = {"DRON", "KUS", "INSAN", "ARAC", "KLUTTER"}
GECERLI_GUVEN = {"kesin", "yuksek", "dusuk"}


class EtiketYoneticisi:
    """Iz etiketlerinin CSV dosyasi uzerinde okuma/yazma islemleri."""

    def __init__(self, konsol, klasor=KAYIT_KLASORU):
        self.konsol = konsol
        self.klasor = klasor
        self._kilit = threading.Lock()

    @property
    def yol(self):
        return os.path.join(self.klasor, ETIKET_DOSYASI)

    # ------------------------------------------------------------------
    def yukle(self) -> list:
        """Tum etiketleri liste olarak dondurur."""
        with self._kilit:
            return self._oku()

    def _oku(self) -> list:
        if not os.path.isfile(self.yol):
            return []
        try:
            with open(self.yol, encoding="utf-8", newline="") as f:
                return [dict(satir) for satir in csv.DictReader(f)]
        except Exception as e:
            self.konsol("ETIKET", f"Okuma hatasi: {e}", "hata")
            return []

    def _yaz(self, etiketler: list):
        os.makedirs(self.klasor, exist_ok=True)
        gecici = self.yol + ".tmp"
        with open(gecici, "w", encoding="utf-8", newline="") as f:
            y = csv.DictWriter(f, fieldnames=ETIKET_ALANLAR)
            y.writeheader()
            for e in etiketler:
                y.writerow({a: e.get(a, "") for a in ETIKET_ALANLAR})
        os.replace(gecici, self.yol)

    # ------------------------------------------------------------------
    def ekle(self, kayit_dosyasi, iz_id, sinif, guven="kesin",
             kaynak="operator", notlar="", baslangic_t=None, bitis_t=None):
        """Yeni etiket ekler; ayni (dosya, iz_id) varsa gunceller.

        Dondurulen deger: (basarili, mesaj)
        """
        sinif = str(sinif or "").upper().strip()
        guven = str(guven or "kesin").lower().strip()
        if sinif not in GECERLI_SINIFLAR:
            return False, f"Gecersiz sinif: {sinif}"
        if guven not in GECERLI_GUVEN:
            return False, f"Gecersiz guven: {guven}"
        try:
            iz_id = int(iz_id)
        except (TypeError, ValueError):
            return False, "Gecersiz iz id"
        kayit_dosyasi = os.path.basename(str(kayit_dosyasi or ""))
        # v2.3.0: radar kayitlari SQLite'ta uzantisiz adla tutulur;
        # eski .jsonl adlari da kabul edilir (geriye uyum)
        if not kayit_dosyasi:
            return False, "Gecersiz kayit dosyasi"

        yeni = {
            "kayit_dosyasi": kayit_dosyasi,
            "iz_id": str(iz_id),
            "baslangic_t": ("" if baslangic_t is None
                            else f"{float(baslangic_t):.3f}"),
            "bitis_t": ("" if bitis_t is None else f"{float(bitis_t):.3f}"),
            "sinif": sinif,
            "guven": guven,
            "kaynak": str(kaynak or "operator"),
            "notlar": str(notlar or "").replace("\n", " ")[:200],
        }
        with self._kilit:
            etiketler = self._oku()
            guncellendi = False
            for e in etiketler:
                if (e["kayit_dosyasi"] == kayit_dosyasi
                        and e["iz_id"] == str(iz_id)):
                    e.update(yeni)
                    guncellendi = True
                    break
            if not guncellendi:
                etiketler.append(yeni)
            try:
                self._yaz(etiketler)
            except Exception as hata:
                return False, f"Yazma hatasi: {hata}"
        islem = "guncellendi" if guncellendi else "eklendi"
        return True, f"Etiket {islem}: {kayit_dosyasi} iz {iz_id} -> {sinif}"

    def sil(self, kayit_dosyasi, iz_id):
        """Etiketi siler."""
        kayit_dosyasi = os.path.basename(str(kayit_dosyasi or ""))
        with self._kilit:
            etiketler = self._oku()
            kalan = [e for e in etiketler
                     if not (e["kayit_dosyasi"] == kayit_dosyasi
                             and e["iz_id"] == str(iz_id))]
            if len(kalan) == len(etiketler):
                return False, "Etiket bulunamadi"
            try:
                self._yaz(kalan)
            except Exception as hata:
                return False, f"Yazma hatasi: {hata}"
        return True, f"Etiket silindi: {kayit_dosyasi} iz {iz_id}"

    def dosya_etiketleri(self, kayit_dosyasi) -> dict:
        """Bir kayit dosyasinin etiketlerini {iz_id: etiket} olarak verir."""
        kayit_dosyasi = os.path.basename(str(kayit_dosyasi or ""))
        sonuc = {}
        for e in self.yukle():
            if e["kayit_dosyasi"] == kayit_dosyasi:
                sonuc[e["iz_id"]] = e
        return sonuc

    def ozet(self) -> dict:
        """Sinif basina etiket sayilari (arayuz gosterimi icin)."""
        sayilar = {s: 0 for s in sorted(GECERLI_SINIFLAR)}
        etiketler = self.yukle()
        for e in etiketler:
            if e.get("sinif") in sayilar:
                sayilar[e["sinif"]] += 1
        return {"toplam": len(etiketler), "siniflar": sayilar}
