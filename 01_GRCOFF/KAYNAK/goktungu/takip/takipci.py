# -*- coding: utf-8 -*-
"""Takipci: radar hedef takipci motoru (GNN + M-of-N + Kalman)."""
import math
from typing import Optional

from .ayarlar import TakipciAyarlar
from .iz import Iz
from .iliskilendirme import _mahalanobis2, _metrik_kapi, _oklid_mesafe, _atama_coz
from .siniflandirma import KuralSiniflandirici, SiniflandirmaAyarlar


class Takipci:
    """Radar hedef takipçi motoru."""

    def __init__(self, ayar: Optional[TakipciAyarlar] = None,
                 sinif_ayar: Optional[SiniflandirmaAyarlar] = None):
        self.ayar = ayar or TakipciAyarlar()
        self.izler: dict = {}          # id -> Iz
        self.yetim_izler: list = []    # silinen izlerin geçmişi
        self._bip_kuyruk: list = []    # bu turda bip çalacak id'ler
        self.siniflandirici = KuralSiniflandirici(sinif_ayar)

    def isle(self, plotlar: list, simdi: float, radar_lat: float, radar_lon: float) -> list:
        """Ham plotları işler, işlenmiş iz listesi döndürür.

        Args:
            plotlar: C20'den gelen ham hedef listesi (konumlandırılmış)
            simdi: zaman damgası (time.time())
            radar_lat, radar_lon: radar merkez konumu

        Returns:
            İşlenmiş iz listesi (frontend'e gönderilecek dict'ler)
        """
        self._bip_kuyruk.clear()

        # 1) Ham filtre (plotlara uygulanır; durum filtresi hariç)
        filtreli_plotlar = [p for p in plotlar if self._ham_filtre(p)]

        # 2) ID eşleştirme
        eslesen_izler = set()    # bu turda plot alan iz ID'leri
        eslesen_plotlar = set()  # eşleşen plot indeksleri
        for i, p in enumerate(filtreli_plotlar):
            pid = p["id"]
            if pid in self.izler:
                self.izler[pid].guncelle(p, self.ayar, simdi)
                eslesen_izler.add(pid)
                eslesen_plotlar.add(i)

        # 3) GNN: eşleşmemiş plotlar × plot alamayan izler
        if self.ayar.gnn_acik:
            self._gnn_atama(filtreli_plotlar, eslesen_izler, eslesen_plotlar, simdi)

        # 4) Kalan plotlar → yeni ADAY
        for i, p in enumerate(filtreli_plotlar):
            if i not in eslesen_plotlar:
                yeni = Iz(p, self.ayar, simdi)
                # Yeni iz ilk gözlemini aldı → M-of-N kontrolü (M=1 ise hemen TEYİTLİ)
                yeni._durum_guncelle(self.ayar)
                self.izler[yeni.id] = yeni
                eslesen_izler.add(yeni.id)   # bu turda plot aldı sayılır

        # 5) Plot alamayan izler: pencere-0 / SÜZÜLEN / SİLİNDİ
        for iz_id, iz in list(self.izler.items()):
            if iz_id in eslesen_izler:
                continue
            if iz.durum == "SILINDI":
                continue
            # Bu turda plot gelmedi
            iz.pencere_bos(self.ayar)
            if iz.durum == "TEYITLI":
                iz.durum = "SUZULEN"
                iz.suzulme_basi = simdi
                iz.tahmin_yuru(simdi)
            elif iz.durum == "SUZULEN":
                iz.tahmin_yuru(simdi)
                # Süre doldu mu?
                if iz.suzulme_basi and (simdi - iz.suzulme_basi) > self.ayar.iz_gorunme_suresi:
                    iz.durum = "SILINDI"
            elif iz.durum == "ADAY":
                # ADAY penceresi dolmadan kaybolursa sil
                if len(iz.pencere) >= self.ayar.N and sum(iz.pencere) < self.ayar.M:
                    iz.durum = "SILINDI"

        # 5.5) Sınıflandırma: bu turda plot alan izler için tip kestirimi
        if self.siniflandirici.ayar.acik:
            for iz_id in eslesen_izler:
                iz = self.izler.get(iz_id)
                if iz is not None and iz.durum != "SILINDI":
                    self.siniflandirici.siniflandir(iz)

        # 6) Bip kontrolü (ADAY → TEYİTLİ geçişi)
        for iz in self.izler.values():
            if iz.durum == "TEYITLI" and not iz.bip_calindi:
                iz.bip_calindi = True
                self._bip_kuyruk.append(iz.id)

        # 7) Silinen izleri yetime taşı
        for iz_id in list(self.izler.keys()):
            if self.izler[iz_id].durum == "SILINDI":
                iz = self.izler.pop(iz_id)
                if iz.iz_gecmisi:
                    self.yetim_izler.append({
                        "id": iz.id,
                        "gecmis": iz.iz_gecmisi,
                        "silme_zamani": simdi,
                    })
        # Yetim limiti 100, eski olanları sil
        while len(self.yetim_izler) > 100:
            self.yetim_izler.pop(0)
        # Süresi dolan yetimleri sil
        self.yetim_izler = [
            y for y in self.yetim_izler
            if (simdi - y["silme_zamani"]) <= self.ayar.iz_gorunme_suresi
        ]

        # 8) Çıkış listesi oluştur (durum filtresi burada uygulanır)
        sonuc = []
        for iz in self.izler.values():
            if iz.durum not in self.ayar.durum_filtre:
                continue
            d = iz.to_dict(radar_lat, radar_lon)
            if iz.id in self._bip_kuyruk:
                d["bip"] = True
            sonuc.append(d)

        return sonuc

    def denetim(self, simdi: float, radar_lat: float, radar_lon: float) -> list:
        """1 sn'lik denetim döngüsü: radar verisi gelmese bile SÜZÜLEN izleri yürütür."""
        for iz in list(self.izler.values()):
            if iz.durum == "SUZULEN":
                iz.tahmin_yuru(simdi)
                if iz.suzulme_basi and (simdi - iz.suzulme_basi) > self.ayar.iz_gorunme_suresi:
                    iz.durum = "SILINDI"
        # Silinen izleri yetime taşı
        for iz_id in list(self.izler.keys()):
            if self.izler[iz_id].durum == "SILINDI":
                iz = self.izler.pop(iz_id)
                if iz.iz_gecmisi:
                    self.yetim_izler.append({
                        "id": iz.id,
                        "gecmis": iz.iz_gecmisi,
                        "silme_zamani": simdi,
                    })
        while len(self.yetim_izler) > 100:
            self.yetim_izler.pop(0)
        self.yetim_izler = [
            y for y in self.yetim_izler
            if (simdi - y["silme_zamani"]) <= self.ayar.iz_gorunme_suresi
        ]
        # Çıkış
        sonuc = []
        for iz in self.izler.values():
            if iz.durum not in self.ayar.durum_filtre:
                continue
            sonuc.append(iz.to_dict(radar_lat, radar_lon))
        return sonuc

    def izleri_temizle(self):
        """Tüm izleri ve yetimleri siler."""
        self.izler.clear()
        self.yetim_izler.clear()

    def iz_sil(self, iz_id) -> bool:
        """Tek bir izi (ve varsa yetim kaydini) siler.
        Operator 'Hedefi Kaldir' dediginde cagrilir."""
        silindi = False
        if iz_id in self.izler:
            del self.izler[iz_id]
            silindi = True
        if iz_id in self.yetim_izler:
            del self.yetim_izler[iz_id]
            silindi = True
        return silindi

    def iz_al(self, iz_id) -> Optional[dict]:
        """Belirli bir iz ID'sinin guncel konum bilgisini dondurur."""
        iz = self.izler.get(iz_id)
        if iz is None:
            return None
        # Basit konum verisi (radar merkezine gore ENU -> lat/lon donusumu
        # burada yapilmaz; son_plot'tan alinir)
        sp = iz.son_plot
        if sp:
            # v2.4.43: Kalman kestirimi HIZ VEKTORU de verilir.
            # Skaler hiz (iz.hiz()) angajman ongorusu icin yetersizdir:
            # kesisme cozumu hedefin YONUNU da gerektirir. Eksen duzeni
            # ENU: vx=dogu, vy=kuzey, vz=yukari (m/s).
            try:
                vx = float(iz.kf_x.v)
                vy = float(iz.kf_y.v)
                vz = float(iz.kf_z.v)
            except Exception:
                vx = vy = vz = 0.0
            return {"lat": sp.get("lat"), "lon": sp.get("lon"),
                    "yukseklik": sp.get("yukseklik", 0),
                    "vx": vx, "vy": vy, "vz": vz}
        return None

    def yetim_listesi(self, simdi: float) -> list:
        """Frontend'e gönderilecek yetim iz geçmişleri."""
        return [
            {"id": y["id"], "gecmis": [[p["lat"], p["lon"], p["yuk"]] for p in y["gecmis"][-60:]]}
            for y in self.yetim_izler
        ]

    # ------------------------------------------------------------------
    # ÖZEL YARDIMCILAR
    # ------------------------------------------------------------------

    def _ham_filtre(self, p: dict) -> bool:
        """Ham plota filtre uygular (durum filtresi hariç)."""
        a = self.ayar
        # Yükseklik
        yuk = p.get("yukseklik", 0.0)
        if yuk < a.yukseklik_min or yuk > a.yukseklik_maks:
            return False
        # RCS
        if a.rcs_min >= 0 and a.rcs_maks >= 0:
            rcs = p.get("rcs", 0.0)
            if rcs < a.rcs_min or rcs > a.rcs_maks:
                return False
        # Hız
        if a.hiz_min >= 0 and a.hiz_maks >= 0:
            hiz = p.get("hiz", 0.0)
            if hiz < a.hiz_min or hiz > a.hiz_maks:
                return False
        # Azimut
        if a.azimut_min >= 0 and a.azimut_maks >= 0:
            azm = p.get("azimut", 0.0)
            if a.azimut_min <= a.azimut_maks:
                if azm < a.azimut_min or azm > a.azimut_maks:
                    return False
            else:  # wrap-around (örn. 350-10)
                if azm < a.azimut_min and azm > a.azimut_maks:
                    return False
        # Tip
        if a.tip_filtre:
            if p.get("tip", "TANIMSIZ") not in a.tip_filtre:
                return False
        return True

    def _gnn_atama(self, plotlar, eslesen_izler, eslesen_plotlar, simdi):
        """GNN kapılama + atama: eşleşmemiş plotlar × plot alamayan izler."""
        INF = float("inf")
        # Aday izler: SÜZÜLEN veya TEYİTLİ olup bu turda plot almamış
        aday_izler = []
        for iz_id, iz in self.izler.items():
            if iz_id in eslesen_izler:
                continue
            if iz.durum in ("TEYITLI", "SUZULEN"):
                aday_izler.append(iz)

        # Aday plotlar: eşleşmemiş
        aday_plotlar = []
        aday_plot_idx = []
        for i, p in enumerate(plotlar):
            if i in eslesen_plotlar:
                continue
            aday_plotlar.append(p)
            aday_plot_idx.append(i)

        if not aday_izler or not aday_plotlar:
            return

        # Maliyet matrisi
        n_iz = len(aday_izler)
        n_plot = len(aday_plotlar)
        maliyet = [[INF] * n_plot for _ in range(n_iz)]

        for i, iz in enumerate(aday_izler):
            kapi = _metrik_kapi(iz, simdi, self.ayar)
            for j, p in enumerate(aday_plotlar):
                # Metrik kapı
                oklid = _oklid_mesafe(iz, p)
                if oklid > kapi:
                    continue
                # Mahalanobis kapı
                d2 = _mahalanobis2(iz, p, self.ayar)
                if d2 > self.ayar.GNN_GAMA:
                    continue
                maliyet[i][j] = d2

        # Atama çöz
        atama = _atama_coz(maliyet)

        # Devralma uygula
        for i, j in enumerate(atama):
            if j < 0:
                continue
            iz = aday_izler[i]
            plot = aday_plotlar[j]
            plot_orijinal_idx = aday_plot_idx[j]
            # İz devralma
            self._iz_devral(iz, plot, simdi)
            eslesen_izler.add(iz.id)
            eslesen_plotlar.add(plot_orijinal_idx)

    def _iz_devral(self, iz: Iz, plot: dict, simdi: float):
        """İzi yeni plot ID'sine devreder."""
        eski_id = iz.id
        yeni_id = plot["id"]

        # Eski ID'yi kaydet
        if eski_id != yeni_id:
            iz.eski_idler.append(eski_id)
            # izler dict'inde taşı
            if eski_id in self.izler:
                del self.izler[eski_id]
            iz.id = yeni_id
            self.izler[yeni_id] = iz

        # İzi güncelle (Kalman düzelt + pencere + durum)
        iz.guncelle(plot, self.ayar, simdi)
        # SÜZÜLEN ise TEYİTLİ'ye dön (guncelle zaten yapar)
        # bipCalindi korunur → tekrar bip çalmaz
