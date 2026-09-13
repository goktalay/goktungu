# -*- coding: utf-8 -*-
"""TakipciAyarlar: takipci motor ayarlari."""
from dataclasses import dataclass, field


@dataclass
class TakipciAyarlar:
    """Takipçi motor ayarları (sunucu başlangıcında gcs_ayarlar.json'dan yüklenir)."""
    M: int = 3
    N: int = 5
    gnn_acik: bool = True
    iz_gorunme_suresi: int = 60       # saniye (SÜZÜLEN → SİLİNDİ eşiği)

    # Filtreler (ham plota uygulanır; -1/-1 = kapalı)
    yukseklik_min: float = -100.0
    yukseklik_maks: float = 3000.0
    rcs_min: float = -1.0
    rcs_maks: float = -1.0
    hiz_min: float = -1.0
    hiz_maks: float = -1.0
    azimut_min: float = -1.0
    azimut_maks: float = -1.0
    tip_filtre: set = field(default_factory=set)          # boş = tümü geçer
    durum_filtre: set = field(default_factory=lambda: {"ADAY", "TEYITLI", "SUZULEN"})

    # Kalman sabitleri
    KF_Q: float = 4.0
    KF_R: float = 225.0

    # GNN sabitleri
    GNN_GAMA: float = 9.21
    GNN_KAPI_MIN: float = 150.0
    GNN_KAPI_MAKS_TABAN: float = 500.0

    def to_dict(self):
        d = {}
        for k in ("M", "N", "gnn_acik", "iz_gorunme_suresi",
                  "yukseklik_min", "yukseklik_maks",
                  "rcs_min", "rcs_maks", "hiz_min", "hiz_maks",
                  "azimut_min", "azimut_maks",
                  "KF_Q", "KF_R", "GNN_GAMA", "GNN_KAPI_MIN", "GNN_KAPI_MAKS_TABAN"):
            d[k] = getattr(self, k)
        d["tip_filtre"] = sorted(self.tip_filtre)
        d["durum_filtre"] = sorted(self.durum_filtre)
        return d

    def from_dict(self, d: dict):
        """JSON dict'ten ayarları yükler."""
        for k, v in d.items():
            if k in ("tip_filtre", "durum_filtre"):
                setattr(self, k, set(v) if v else set())
            elif hasattr(self, k):
                tip = type(getattr(self, k))
                try:
                    setattr(self, k, tip(v))
                except (TypeError, ValueError):
                    pass
