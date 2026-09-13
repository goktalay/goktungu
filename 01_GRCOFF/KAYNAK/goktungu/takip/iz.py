# -*- coding: utf-8 -*-
"""Iz: tek hedef izi (Kalman durumu + M-of-N penceresi + gecmis)."""
import math
from collections import deque
from typing import Optional

from .ayarlar import TakipciAyarlar
from .kalman import KalmanEksen


class Iz:
    """Tek hedef izi."""

    __slots__ = (
        "id", "durum", "kf_x", "kf_y", "kf_z",
        "pencere", "bip_calindi", "suzulme_basi",
        "eski_idler", "iz_gecmisi", "son_guncelleme",
        "son_plot", "tip", "snr", "rcs",
        # Siniflandirma (Faz 1): oznitelik tamponlari + karar durumu
        "oz_hiz", "oz_dikey_hiz", "oz_rcs", "oz_snr",
        "tip_guven", "tip_kaynak", "sinif_aday", "sinif_sayac",
    )

    def __init__(self, plot: dict, ayar: TakipciAyarlar, simdi: float):
        self.id = plot["id"]
        self.durum = "ADAY"
        Q, R = ayar.KF_Q, ayar.KF_R
        # ENU konumu (metre cinsinden; radar merkezine göre)
        ex, ey, ez = self._enu(plot)
        self.kf_x = KalmanEksen(ex, plot.get("vx", 0.0), Q, R)
        self.kf_y = KalmanEksen(ey, plot.get("vy", 0.0), Q, R)
        self.kf_z = KalmanEksen(ez, plot.get("vz_ms", 0.0), Q, R)
        self.pencere = [True]
        self.bip_calindi = False
        self.suzulme_basi: Optional[float] = None
        self.eski_idler: list = []
        self.iz_gecmisi: list = []  # [{lat, lon, yuk, t}]
        self.son_guncelleme = simdi
        self.son_plot = plot
        self.tip = plot.get("tip", "TANIMSIZ")
        self.snr = plot.get("snr", 0.0)
        self.rcs = plot.get("rcs", 0.0)
        # Siniflandirma oznitelik tamponlari (son 30 ornek)
        self.oz_hiz = deque(maxlen=30)
        self.oz_dikey_hiz = deque(maxlen=30)
        self.oz_rcs = deque(maxlen=30)
        self.oz_snr = deque(maxlen=30)
        self.tip_guven = 0.0        # kural/ML guven skoru [0..1]
        self.tip_kaynak = "radar"   # radar | kural | ml
        self.sinif_aday = None      # histerezis aday sinifi
        self.sinif_sayac = 0        # ardisik ayni karar sayaci
        self._oznitelik_ekle(plot)
        # İlk iz noktası
        self._gecmis_ekle(plot, simdi)

    @staticmethod
    def _enu(plot: dict):
        """Plot'tan ENU (m) koordinatları çıkar. x=doğu, y=kuzey."""
        # Radar merkezine göre x/y (C20 formatı: x=doğu, y=kuzey)
        return plot.get("x", 0.0), plot.get("y", 0.0), plot.get("z", 0.0)

    def _oznitelik_ekle(self, plot: dict):
        """Siniflandirma oznitelik tamponlarina yeni ornek ekler."""
        vx = plot.get("vx", 0.0)
        vy = plot.get("vy", 0.0)
        vz = plot.get("vz", plot.get("vz_ms", 0.0))
        self.oz_hiz.append(math.sqrt(vx * vx + vy * vy + vz * vz))
        self.oz_dikey_hiz.append(vz)
        self.oz_rcs.append(plot.get("rcs", 0.0))
        self.oz_snr.append(plot.get("snr", 0.0))

    def _gecmis_ekle(self, plot: dict, simdi: float):
        """İz geçmişine nokta ekler (2 m minimum adım)."""
        lat = plot.get("lat")
        lon = plot.get("lon")
        yuk = plot.get("yukseklik", 0.0)
        if lat is None or lon is None:
            return
        if self.iz_gecmisi:
            son = self.iz_gecmisi[-1]
            dlat = (lat - son["lat"]) * 111320.0
            dlon = (lon - son["lon"]) * 111320.0 * math.cos(math.radians(lat))
            if dlat * dlat + dlon * dlon < 4.0:  # < 2 m
                return
        self.iz_gecmisi.append({"lat": lat, "lon": lon, "yuk": yuk, "t": simdi})
        # Azami 240 nokta
        if len(self.iz_gecmisi) > 240:
            self.iz_gecmisi.pop(0)

    def guncelle(self, plot: dict, ayar: TakipciAyarlar, simdi: float):
        """Yeni plot ile izi günceller."""
        dt = simdi - self.son_guncelleme
        if dt <= 0:
            dt = 0.1
        # Kalman tahmin + düzelt
        self.kf_x.tahmin(dt)
        self.kf_y.tahmin(dt)
        self.kf_z.tahmin(dt)
        ex, ey, ez = self._enu(plot)
        self.kf_x.duzelt(ex)
        self.kf_y.duzelt(ey)
        self.kf_z.duzelt(ez)
        # Pencere güncelle
        self.pencere.append(True)
        if len(self.pencere) > ayar.N:
            self.pencere.pop(0)
        # Durum geçişi
        self._durum_guncelle(ayar)
        # Meta güncelle
        self.son_guncelleme = simdi
        self.son_plot = plot
        radar_tip = plot.get("tip", "TANIMSIZ")
        if radar_tip not in ("TANIMSIZ", "BELIRSIZ"):
            # Radar gecerli bir tip verdi → radar bilgisi onceliklidir
            self.tip = radar_tip
            self.tip_kaynak = "radar"
        elif self.tip_kaynak == "radar":
            # Radar tip vermiyor ve kural karari da yok → TANIMSIZ kal
            self.tip = radar_tip
        # tip_kaynak kural/ml ise siniflandirici karari korunur
        self.snr = plot.get("snr", self.snr)
        self.rcs = plot.get("rcs", self.rcs)
        self._oznitelik_ekle(plot)
        self.suzulme_basi = None
        self._gecmis_ekle(plot, simdi)

    def tahmin_yuru(self, simdi: float):
        """Plot gelmeden Kalman tahmini yürütür (SÜZÜLEN)."""
        dt = simdi - self.son_guncelleme
        if dt <= 0:
            return
        self.kf_x.tahmin(dt)
        self.kf_y.tahmin(dt)
        self.kf_z.tahmin(dt)
        self.son_guncelleme = simdi

    def pencere_bos(self, ayar: TakipciAyarlar):
        """Pencereye False ekler (bu taramada plot gelmedi)."""
        self.pencere.append(False)
        if len(self.pencere) > ayar.N:
            self.pencere.pop(0)

    def _durum_guncelle(self, ayar: TakipciAyarlar):
        """M-of-N kuralına göre durum geçişi."""
        if self.durum == "SILINDI":
            return
        gorulen = sum(self.pencere)
        if self.durum == "ADAY":
            if gorulen >= ayar.M:
                self.durum = "TEYITLI"
        elif self.durum == "SUZULEN":
            # Plot geldi → TEYİTLİ'ye dön
            self.durum = "TEYITLI"
            self.suzulme_basi = None

    def hiz(self) -> float:
        """Kalman kestirimi toplam hız (m/s)."""
        return math.sqrt(self.kf_x.v ** 2 + self.kf_y.v ** 2 + self.kf_z.v ** 2)

    def konum_enu(self):
        """Kalman filtreli ENU konumu."""
        return self.kf_x.x, self.kf_y.x, self.kf_z.x

    def to_dict(self, radar_lat: float, radar_lon: float) -> dict:
        """Frontend'e gönderilecek iz sözlüğü."""
        ex, ey, ez = self.konum_enu()
        # ENU → lat/lon (yaklaşık)
        lat = radar_lat + ey / 111320.0
        lon = radar_lon + ex / (111320.0 * math.cos(math.radians(radar_lat)))
        yuk = max(0.0, ez)
        mesafe = math.sqrt(ex * ex + ey * ey + ez * ez)
        azimut = (math.degrees(math.atan2(ex, ey)) + 360.0) % 360.0
        return {
            "id": self.id,
            "lat": lat,
            "lon": lon,
            "yukseklik": yuk,
            "mesafe": mesafe,
            "azimut": azimut,
            "hiz": self.hiz(),
            "snr": self.snr,
            "rcs": self.rcs,
            "tip": self.tip,
            "tip_guven": self.tip_guven,
            "tip_kaynak": self.tip_kaynak,
            "durum": self.durum,
            "eski_idler": list(self.eski_idler),
            "iz_gecmisi": [[p["lat"], p["lon"], p["yuk"]] for p in self.iz_gecmisi[-60:]],
            "bip": False,  # dışarıda ayarlanır
        }
