# -*- coding: utf-8 -*-
"""KuralSiniflandirici: kural tabanli hedef sinif atamasi (Faz 1).

C20 radar iz verisinden (kinematik + RCS/SNR) hedef sinifini kestirir.
Literatur temeli:
- Liu, Xu, Chen (IEEE Access 2021, DOI:10.1109/ACCESS.2021.3130231):
  iz hareket ozniteliklerinden Random Forest ile kus/dron ayrimi.
- Mehta ve ark. (NATO STO-MP-MSG-SET-183): 500m+ mesafede micro-Doppler
  calismaz; iz tabanli oznitelikler (hiz/ivme/donus istatistikleri) kullanilir.
  Kuslar dronlardan belirgin daha degisken ucar (manevra frekansi yuksek).

Yontem: her sinif icin fizik tabanli zarf (min-maks araligi) puanlamasi.
Oznitelik degeri zarfin icindeyse tam puan, disindaysa MUTLAK olcekli
mesafeyle azalan puan verilir. Agirlikli toplam skor en yuksek sinif aday
olur; su kosullarin TUMU saglanirsa karar verilir:
  1. En iyi skor >= guven esigi
  2. En iyi ile ikinci skor arasindaki fark >= ayrim marji
  3. Ardisik `histerezis` karede ayni aday (kararlilik)
Aksi halde iz BELIRSIZ isaretlenir / mevcut tip korunur.

Hassasiyet ayari (0-100): kullanicinin tek kaydiraci. Dusuk hassasiyet
muhafazakar davranir (yuksek esik + genis marj — az ama emin karar),
yuksek hassasiyet agresif davranir (dusuk esik — cok karar, hata riski).

ML modeli (Faz 3) devreye girdiginde ayni arayuz korunacak; model dosyasi
yoksa bu kural tabanli siniflandirici yedek katman olarak calisir.
"""
import math
from dataclasses import dataclass


# Sinif zarflari: oznitelik -> (min, maks) "rahat" araligi.
# Puanlama zarf disinda MUTLAK olcekle azalir (bkz. OZNITELIK_OLCEK).
SINIF_ZARFLARI = {
    "DRON": {
        "hiz":       (3.0, 30.0),    # m/s (multirotor + sabit kanat kucuk IHA)
        "irtifa":    (20.0, 1000.0), # m (yerden) — yer seviyesi dron sayilmaz
        "dikey_hiz": (0.0, 12.0),    # |vz| m/s
        "rcs":       (0.005, 0.6),   # m2 (kucuk IHA tipik 0.01-0.5)
        "hiz_std":   (0.0, 1.8),     # m/s — dronlar kararli seyir yapar
    },
    "KUS": {
        "hiz":       (2.0, 22.0),
        "irtifa":    (0.0, 400.0),
        "dikey_hiz": (0.0, 6.0),
        "rcs":       (0.0005, 0.5),  # kus RCS'i dronla ortusur
        "hiz_std":   (1.5, 8.0),     # kuslar degisken/manevrali ucar
    },
    "INSAN": {
        "hiz":       (0.2, 3.5),
        "irtifa":    (0.0, 8.0),     # yer hedefi
        "dikey_hiz": (0.0, 1.0),
        "rcs":       (0.3, 2.5),
        "hiz_std":   (0.0, 1.5),
    },
    "ARAC": {
        "hiz":       (4.5, 45.0),   # yaya hizindan net ayrim (>16 km/h)
        "irtifa":    (0.0, 8.0),    # yer hedefi
        "dikey_hiz": (0.0, 1.5),
        "rcs":       (3.0, 200.0),  # binek arac tipik 5-20 m2
        "hiz_std":   (0.0, 3.0),
    },
}

# Zarf disi cezanin MUTLAK olcegi (oznitelik birimi cinsinden).
# _zarf_puani = exp(-sapma / olcek). Onceki surumde sapma zarf genisligine
# oranlaniyordu; genis zarflar (orn. DRON irtifa 10-1200m) fiilen cezasiz
# kaliyordu — DRON yanliliginin kok nedeni buydu.
OZNITELIK_OLCEK = {
    "hiz":       2.0,   # m/s   — zarftan 2 m/s uzakta puan ~0.37
    "irtifa":    15.0,  # m     — zarftan 15 m uzakta puan ~0.37
    "dikey_hiz": 1.0,   # m/s
    "rcs":       0.15,  # m2
    "hiz_std":   0.8,   # m/s
}

# Oznitelik agirliklari (toplam 1.0). Irtifa ve RCS en ayirt edici;
# hiz_std kus/dron ayriminin anahtari (NATO SET-183 bulgusu).
OZNITELIK_AGIRLIK = {
    "hiz":       0.15,
    "irtifa":    0.30,
    "dikey_hiz": 0.10,
    "rcs":       0.25,
    "hiz_std":   0.20,
}

# RCS olcumu olmayan izlerde karar guvenilirligi duser; skor bu katsayiyla
# carpilir ki eksik veriyle agresif DRON atamasi yapilmasin.
RCS_YOK_KATSAYI = 0.85


def hassasiyet_esikleri(hassasiyet: int):
    """Hassasiyet (0-100) -> (guven_esigi, ayrim_marji).

    0   = en muhafazakar: esik 0.90, marj 0.20 (neredeyse hic karar vermez)
    50  = dengeli:        esik 0.725, marj 0.115
    100 = en agresif:     esik 0.55, marj 0.03
    """
    h = max(0, min(100, int(hassasiyet))) / 100.0
    guven_esigi = 0.90 - 0.35 * h
    ayrim_marji = 0.20 - 0.17 * h
    return round(guven_esigi, 3), round(ayrim_marji, 3)


@dataclass
class SiniflandirmaAyarlar:
    """Kural tabanli siniflandirici ayarlari."""
    acik: bool = True
    hassasiyet: int = 40      # 0-100; kullanicinin ana ayari (vars. temkinli)
    min_ornek: int = 8        # karar icin gereken asgari oznitelik ornegi
    histerezis: int = 5       # sinif degisimi icin gereken ardisik ayni karar

    @property
    def guven_esigi(self) -> float:
        return hassasiyet_esikleri(self.hassasiyet)[0]

    @property
    def ayrim_marji(self) -> float:
        return hassasiyet_esikleri(self.hassasiyet)[1]

    def to_dict(self):
        return {
            "acik": self.acik,
            "hassasiyet": self.hassasiyet,
            "min_ornek": self.min_ornek,
            "histerezis": self.histerezis,
        }

    def from_dict(self, d: dict):
        d = dict(d or {})
        # Geriye uyum: eski kayitlarda guven_esigi olabilir -> hassasiyete cevir
        if "guven_esigi" in d and "hassasiyet" not in d:
            try:
                ge = float(d["guven_esigi"])
                d["hassasiyet"] = int(round((0.90 - ge) / 0.35 * 100))
            except (TypeError, ValueError):
                pass
        d.pop("guven_esigi", None)
        for k, v in d.items():
            if hasattr(self, k) and not isinstance(
                    getattr(type(self), k, None), property):
                tip = type(getattr(self, k))
                try:
                    setattr(self, k, tip(v))
                except (TypeError, ValueError):
                    pass
        self.hassasiyet = max(0, min(100, self.hassasiyet))


def _zarf_puani(deger: float, zarf: tuple, olcek: float) -> float:
    """Degerin zarfa uyum puani [0..1].

    Zarf icinde 1.0; disinda MUTLAK mesafeyle (oznitelik biriminde,
    `olcek` ile normalize) ustel azalir. Zarf genisliginden bagimsizdir —
    genis zarflar ceza avantaji kazanamaz.
    """
    alt, ust = zarf
    if alt <= deger <= ust:
        return 1.0
    sapma = (alt - deger) if deger < alt else (deger - ust)
    return math.exp(-sapma / max(olcek, 1e-6))


class KuralSiniflandirici:
    """Fizik zarflari + agirlikli skor + marj + histerezis ile siniflandirma."""

    def __init__(self, ayar: SiniflandirmaAyarlar = None):
        self.ayar = ayar or SiniflandirmaAyarlar()

    # ------------------------------------------------------------------
    def oznitelik_cikar(self, iz) -> dict:
        """Iz tamponlarindan oznitelik vektoru uretir (yetersizse None)."""
        n = len(iz.oz_hiz)
        if n < self.ayar.min_ornek:
            return None
        hizlar = list(iz.oz_hiz)
        ort_hiz = sum(hizlar) / n
        var_hiz = sum((h - ort_hiz) ** 2 for h in hizlar) / n
        dikeyler = [abs(v) for v in iz.oz_dikey_hiz]
        rcsler = [r for r in iz.oz_rcs if r > 0.0]
        return {
            "hiz": ort_hiz,
            "hiz_std": math.sqrt(var_hiz),
            "dikey_hiz": sum(dikeyler) / len(dikeyler) if dikeyler else 0.0,
            "irtifa": max(0.0, iz.kf_z.x),
            "rcs": (sum(rcsler) / len(rcsler)) if rcsler else -1.0,
        }

    def skorla(self, oz: dict) -> dict:
        """Her sinif icin agirlikli zarf skoru [0..1] dondurur."""
        rcs_var = oz.get("rcs") is not None and oz["rcs"] >= 0
        skorlar = {}
        for sinif, zarflar in SINIF_ZARFLARI.items():
            toplam, agirlik_toplam = 0.0, 0.0
            for ad, zarf in zarflar.items():
                deger = oz.get(ad)
                if deger is None or (ad == "rcs" and deger < 0):
                    continue
                w = OZNITELIK_AGIRLIK[ad]
                toplam += w * _zarf_puani(deger, zarf, OZNITELIK_OLCEK[ad])
                agirlik_toplam += w
            skor = (toplam / agirlik_toplam) if agirlik_toplam else 0.0
            if not rcs_var:
                skor *= RCS_YOK_KATSAYI  # eksik veriyle temkinli ol
            skorlar[sinif] = skor
        return skorlar

    def siniflandir(self, iz) -> None:
        """Izin sinifini gunceller (iz.tip / iz.tip_guven / iz.tip_kaynak).

        Takipci.isle() her karede cagirir. Karar kosullari:
        skor >= guven_esigi VE (en iyi - ikinci) >= ayrim_marji VE
        ardisik `histerezis` karede ayni aday.
        """
        a = self.ayar
        if not a.acik:
            return
        # Radar gecerli bir tip verdiyse dokunma (radar bilgisi oncelikli)
        if iz.tip_kaynak == "radar" and iz.tip not in ("TANIMSIZ", "BELIRSIZ"):
            return

        oz = self.oznitelik_cikar(iz)
        if oz is None:
            return  # veri yetersiz; mevcut tip korunur

        # Hareket kapisi: cok yavas (<1 m/s) ve RCS olcumu olmayan izler
        # buyuk olasilikla klutter/duragan yansimadir — karar verilmez.
        if oz["hiz"] < 1.0 and oz["rcs"] < 0:
            return

        skorlar = self.skorla(oz)
        sirali = sorted(skorlar.items(), key=lambda kv: kv[1], reverse=True)
        aday, guven = sirali[0]
        ikinci = sirali[1][1] if len(sirali) > 1 else 0.0

        # Karar icin hem yeterli guven hem siniflar arasi ayrim gerekir.
        if guven < a.guven_esigi or (guven - ikinci) < a.ayrim_marji:
            aday = "BELIRSIZ"

        # Histerezis
        if aday == iz.sinif_aday:
            iz.sinif_sayac += 1
        else:
            iz.sinif_aday = aday
            iz.sinif_sayac = 1

        if iz.sinif_sayac >= a.histerezis and iz.tip != aday:
            iz.tip = aday
            iz.tip_kaynak = "kural"
        if iz.tip == aday:
            iz.tip_guven = round(guven, 2)
