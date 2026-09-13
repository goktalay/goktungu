# -*- coding: utf-8 -*-
"""Takip paketi birim testleri: python3 -m goktungu.takip.testler ile kosar."""
import time

from .ayarlar import TakipciAyarlar
from .kalman import KalmanEksen
from .takipci import Takipci
from .iliskilendirme import _atama_coz


def _birim_testleri():
    """Doğrudan çalıştırıldığında birim testlerini koşar."""
    import sys

    print("=" * 60)
    print("TAKİPCİ BİRİM TESTLERİ")
    print("=" * 60)
    hatalar = 0

    # --- Test 1: Kalman filtresi ---
    print("\n[1] Kalman filtresi...")
    kf = KalmanEksen(0.0, 10.0, 4.0, 225.0)
    kf.tahmin(1.0)
    assert abs(kf.x - 10.0) < 0.01, f"Tahmin hatası: {kf.x}"
    kf.duzelt(12.0)
    assert abs(kf.x - 12.0) < 5.0, f"Düzeltme hatası: {kf.x}"
    print("   OK: Kalman tahmin+düzelt çalışıyor")

    # --- Test 2: M-of-N durum makinesi ---
    print("\n[2] M-of-N durum makinesi...")
    ayar = TakipciAyarlar(M=3, N=5)
    t = Takipci(ayar)
    # 5 ardışık plot → ADAY → TEYİTLİ
    for i in range(5):
        sonuc = t.isle([{
            "id": 100, "x": 1000.0, "y": 2000.0, "z": 150.0,
            "vx": 10.0, "vy": 5.0, "vz_ms": 0.0,
            "lat": 40.0 + i * 0.0001, "lon": 33.0, "yukseklik": 150.0,
            "mesafe": 2236.0, "azimut": 26.6, "hiz": 11.2,
            "snr": 30.0, "rcs": 0.5, "tip": "DRON",
        }], time.time() + i, 40.0, 33.0)
    assert 100 in t.izler, "İz oluşmadı"
    assert t.izler[100].durum == "TEYITLI", f"Durum: {t.izler[100].durum}"
    assert t.izler[100].bip_calindi, "Bip çalınmadı"
    print("   OK: 3/5 sonra TEYİTLİ, bip çalındı")

    # --- Test 3: SÜZÜLEN ---
    print("\n[3] SÜZÜLEN (coasting)...")
    ayar3 = TakipciAyarlar(M=1, N=1, iz_gorunme_suresi=5)
    t3 = Takipci(ayar3)
    t0 = time.time()
    t3.isle([{
        "id": 200, "x": 500.0, "y": 500.0, "z": 100.0,
        "vx": 10.0, "vy": 0.0, "vz_ms": 0.0,
        "lat": 40.0, "lon": 33.0, "yukseklik": 100.0,
        "mesafe": 707.0, "azimut": 45.0, "hiz": 10.0,
        "snr": 25.0, "rcs": 0.3, "tip": "DRON",
    }], t0, 40.0, 33.0)
    assert t3.izler[200].durum == "TEYITLI"
    # Boş tur → SÜZÜLEN
    t3.isle([], t0 + 1, 40.0, 33.0)
    assert t3.izler[200].durum == "SUZULEN", f"Durum: {t3.izler[200].durum}"
    # Süre dolunca SİLİNDİ
    t3.denetim(t0 + 7, 40.0, 33.0)
    assert 200 not in t3.izler, "İz silinmedi"
    assert len(t3.yetim_izler) == 1, "Yetim oluşmadı"
    print("   OK: SÜZÜLEN → SİLİNDİ → yetim")

    # --- Test 4: GNN iz devralma ---
    print("\n[4] GNN iz devralma (ID kopması)...")
    ayar4 = TakipciAyarlar(M=1, N=1, gnn_acik=True, iz_gorunme_suresi=30)
    t4 = Takipci(ayar4)
    t0 = time.time()
    # İlk iz
    t4.isle([{
        "id": 501, "x": 3000.0, "y": 0.0, "z": 150.0,
        "vx": 15.0, "vy": 0.0, "vz_ms": 0.0,
        "lat": 40.0, "lon": 33.027, "yukseklik": 150.0,
        "mesafe": 3000.0, "azimut": 90.0, "hiz": 15.0,
        "snr": 36.0, "rcs": 0.5, "tip": "DRON",
    }], t0, 40.0, 33.0)
    assert t4.izler[501].durum == "TEYITLI"
    # Plot kaybolur → SÜZÜLEN
    t4.isle([], t0 + 2, 40.0, 33.0)
    assert t4.izler[501].durum == "SUZULEN"
    # Yeni ID ile aynı konumda döner
    t4.isle([{
        "id": 601, "x": 3030.0, "y": 0.0, "z": 150.0,
        "vx": 15.0, "vy": 0.0, "vz_ms": 0.0,
        "lat": 40.0, "lon": 33.0272, "yukseklik": 150.0,
        "mesafe": 3030.0, "azimut": 90.0, "hiz": 15.0,
        "snr": 36.0, "rcs": 0.5, "tip": "DRON",
    }], t0 + 4, 40.0, 33.0)
    assert 601 in t4.izler, "Devralma gerçekleşmedi"
    assert 501 not in t4.izler, "Eski iz hâlâ var"
    assert 501 in t4.izler[601].eski_idler, f"eskiIdler: {t4.izler[601].eski_idler}"
    assert t4.izler[601].bip_calindi, "Bip durumu korunmadı"
    assert t4.izler[601].durum == "TEYITLI", f"Durum: {t4.izler[601].durum}"
    print("   OK: 501→SÜZÜLEN→601 devralındı, bip korundu, eskiIdler=[501]")

    # --- Test 5: Atama çözücü ---
    print("\n[5] Atama çözücü (Macar)...")
    assert _atama_coz([[5.0]]) == [0]
    assert _atama_coz([[1, 10], [10, 1]]) == [0, 1]
    assert _atama_coz([[10, 1], [1, 10]]) == [1, 0]
    INF = float("inf")
    assert _atama_coz([[INF, INF], [INF, INF]]) == [-1, -1]
    # 3x3
    r = _atama_coz([[10, 1, 5], [1, 10, 5], [5, 5, 1]])
    assert r == [1, 0, 2], f"3x3 sonuç: {r}"
    print("   OK: Tüm atama testleri geçti")

    # --- Test 6: Ham filtre ---
    print("\n[6] Ham filtre...")
    ayar6 = TakipciAyarlar(yukseklik_min=0, yukseklik_maks=500, tip_filtre={"DRON"})
    t6 = Takipci(ayar6)
    p_gecen = {"id": 1, "x": 0, "y": 0, "z": 100, "vx": 0, "vy": 0, "vz_ms": 0,
               "lat": 40, "lon": 33, "yukseklik": 100, "mesafe": 0, "azimut": 0,
               "hiz": 0, "snr": 20, "rcs": 0.1, "tip": "DRON"}
    p_yuksek = dict(p_gecen, id=2, yukseklik=600, z=600)
    p_tip = dict(p_gecen, id=3, tip="KUS")
    assert t6._ham_filtre(p_gecen) is True
    assert t6._ham_filtre(p_yuksek) is False
    assert t6._ham_filtre(p_tip) is False
    print("   OK: Filtreler doğru çalışıyor")

    # --- Test 7: Kural tabanlı sınıflandırma ---
    print("\n[7] Kural tabanlı sınıflandırma...")
    t7 = Takipci(TakipciAyarlar(M=1, N=5))
    t0 = time.time()

    def plot_uret(pid, z, vx, vy, vz, rcs, sapma=0.0, k=0):
        """Simülasyon plotu: sapma>0 hız değişkenliği (kuş manevrası) katar."""
        f = 1.0 + sapma * ((-1) ** k)
        return {"id": pid, "x": 100.0 + k * vx, "y": 100.0 + k * vy,
                "z": z, "vx": vx * f, "vy": vy * f, "vz": vz,
                "vz_ms": vz, "lat": 40.0 + k * 0.0001, "lon": 33.0,
                "yukseklik": z, "mesafe": 200.0, "azimut": 45.0,
                "hiz": 10.0, "snr": 15.0, "rcs": rcs, "tip": "TANIMSIZ"}

    # DRON profili: 80 m irtifa, 12 m/s kararlı seyir, RCS 0.05 m2
    for k in range(12):
        t7.isle([plot_uret(101, 80.0, 12.0, 0.0, 1.0, 0.05, 0.02, k)],
                t0 + k, 40.0, 33.0)
    iz_dron = t7.izler[101]
    assert iz_dron.tip == "DRON", f"DRON bekleniyordu: {iz_dron.tip}"
    assert iz_dron.tip_kaynak == "kural", f"kaynak: {iz_dron.tip_kaynak}"
    print(f"   OK: DRON profili -> {iz_dron.tip} (güven={iz_dron.tip_guven})")

    # İNSAN profili: yer hedefi, 1.5 m/s, RCS 1.0 m2
    for k in range(12):
        t7.isle([plot_uret(102, 1.5, 1.5, 0.0, 0.0, 1.0, 0.05, k)],
                t0 + k, 40.0, 33.0)
    iz_insan = t7.izler[102]
    assert iz_insan.tip == "INSAN", f"INSAN bekleniyordu: {iz_insan.tip}"
    print(f"   OK: INSAN profili -> {iz_insan.tip} (güven={iz_insan.tip_guven})")

    # ARAÇ profili: yer hedefi, 15 m/s, RCS 10 m2
    for k in range(12):
        t7.isle([plot_uret(103, 1.0, 15.0, 0.0, 0.0, 10.0, 0.02, k)],
                t0 + k, 40.0, 33.0)
    iz_arac = t7.izler[103]
    assert iz_arac.tip == "ARAC", f"ARAC bekleniyordu: {iz_arac.tip}"
    print(f"   OK: ARAC profili -> {iz_arac.tip} (güven={iz_arac.tip_guven})")

    # Radar tipi önceliği: radar geçerli tip verirse kural ezmez
    for k in range(12):
        p = plot_uret(104, 50.0, 10.0, 0.0, 0.0, 0.05, 0.02, k)
        p["tip"] = "KUS"
        t7.isle([p], t0 + k, 40.0, 33.0)
    iz_radar = t7.izler[104]
    assert iz_radar.tip == "KUS" and iz_radar.tip_kaynak == "radar", \
        f"Radar tipi korunmalıydı: {iz_radar.tip}/{iz_radar.tip_kaynak}"
    print("   OK: Radar tipi önceliği korunuyor")

    # Yetersiz veri: tek örnekle karar verilmemeli
    t7.isle([plot_uret(105, 80.0, 12.0, 0.0, 1.0, 0.05)], t0, 40.0, 33.0)
    iz_az = t7.izler[105]
    assert iz_az.tip == "TANIMSIZ", f"TANIMSIZ kalmalıydı: {iz_az.tip}"
    print("   OK: Yetersiz veri -> TANIMSIZ korunuyor")

    # Sınıflandırıcı kapalıyken dokunulmamalı
    t8 = Takipci(TakipciAyarlar(M=1, N=5))
    t8.siniflandirici.ayar.acik = False
    for k in range(12):
        t8.isle([plot_uret(106, 80.0, 12.0, 0.0, 1.0, 0.05, 0.02, k)],
                t0 + k, 40.0, 33.0)
    assert t8.izler[106].tip == "TANIMSIZ", "Kapalıyken tip değişmemeli"
    print("   OK: Kapalıyken tip değişmiyor")

    print("\n" + "=" * 60)
    print(f"TÜM TESTLER BAŞARILI (hata: {hatalar})")
    print("=" * 60)


if __name__ == "__main__":
    _birim_testleri()
