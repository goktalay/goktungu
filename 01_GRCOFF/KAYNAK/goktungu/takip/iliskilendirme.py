# -*- coding: utf-8 -*-
"""GNN iliskilendirme yardimcilari: kapilama metrikleri ve Macar atama cozucusu."""
import math

from .ayarlar import TakipciAyarlar
from .iz import Iz


def _mahalanobis2(iz: Iz, plot: dict, ayar: TakipciAyarlar) -> float:
    """Mahalanobis mesafesi karesi (S köşegen varsayımı)."""
    ex, ey, _ = Iz._enu(plot)
    dx = ex - iz.kf_x.x
    dy = ey - iz.kf_y.x
    Sx = iz.kf_x.Pxx + ayar.KF_R
    Sy = iz.kf_y.Pxx + ayar.KF_R
    if Sx < 1e-6:
        Sx = 1e-6
    if Sy < 1e-6:
        Sy = 1e-6
    return dx * dx / Sx + dy * dy / Sy


def _metrik_kapi(iz: Iz, simdi: float, ayar: TakipciAyarlar) -> float:
    """Dinamik metrik kapı (metre)."""
    hiz = iz.hiz()
    t_kayip = simdi - iz.son_guncelleme if iz.suzulme_basi else 0.0
    ust = max(ayar.GNN_KAPI_MAKS_TABAN, hiz * t_kayip + 300.0)
    return max(ayar.GNN_KAPI_MIN, min(ust, 20000.0))


def _oklid_mesafe(iz: Iz, plot: dict) -> float:
    """ENU düzleminde Öklid mesafesi (m)."""
    ex, ey, _ = Iz._enu(plot)
    dx = ex - iz.kf_x.x
    dy = ey - iz.kf_y.x
    return math.sqrt(dx * dx + dy * dy)


def _atama_coz(maliyet: list) -> list:
    """Küresel atama çözücüsü (Macar algoritması).
    maliyet[i][j] = iz i'nin plot j'ye maliyeti (Infinity = kapı dışı).
    Dönüş: atama[i] = j veya -1."""
    n = len(maliyet)
    if n == 0:
        return []
    m = len(maliyet[0]) if n > 0 else 0
    if m == 0:
        return [-1] * n

    INF = float("inf")

    # n=1
    if n == 1:
        en_iyi = -1
        en_iyi_m = INF
        for j in range(m):
            if maliyet[0][j] < en_iyi_m:
                en_iyi_m = maliyet[0][j]
                en_iyi = j
        return [en_iyi if en_iyi_m < INF else -1]

    # n=2, m>=2: permütasyon
    if n == 2 and m <= 4:
        en_iyi = [-1, -1]
        en_iyi_toplam = INF
        for j1 in range(m):
            if maliyet[0][j1] >= INF:
                continue
            for j2 in range(m):
                if j2 == j1:
                    continue
                if maliyet[1][j2] >= INF:
                    continue
                toplam = maliyet[0][j1] + maliyet[1][j2]
                if toplam < en_iyi_toplam:
                    en_iyi_toplam = toplam
                    en_iyi = [j1, j2]
        return en_iyi

    # Genel: Macar algoritması (potansiyel yöntemi)
    # Kare matris yap (n x n, fazla sütun/satır INF ile doldur)
    boyut = max(n, m)
    C = [[INF] * boyut for _ in range(boyut)]
    for i in range(n):
        for j in range(m):
            C[i][j] = maliyet[i][j] if maliyet[i][j] < INF else 1e18

    u = [0.0] * (boyut + 1)
    v = [0.0] * (boyut + 1)
    p = [0] * (boyut + 1)
    way = [0] * (boyut + 1)

    for i in range(1, boyut + 1):
        p[0] = i
        j0 = 0
        minv = [INF] * (boyut + 1)
        used = [False] * (boyut + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = INF
            j1 = -1
            for j in range(1, boyut + 1):
                if used[j]:
                    continue
                cur = C[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            if j1 == -1:
                break
            for j in range(boyut + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            p[j0] = p[way[j0]]
            j0 = way[j0]

    # Sonuç: p[j] = i (1-indexed)
    atama = [-1] * n
    for j in range(1, boyut + 1):
        i_idx = p[j] - 1
        j_idx = j - 1
        if i_idx < n and j_idx < m:
            if maliyet[i_idx][j_idx] < INF:
                atama[i_idx] = j_idx
    return atama
