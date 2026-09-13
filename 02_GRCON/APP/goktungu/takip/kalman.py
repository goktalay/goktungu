# -*- coding: utf-8 -*-
"""KalmanEksen: 2x2 CV Kalman filtresi (tek eksen)."""


class KalmanEksen:
    """2x2 Constant-Velocity Kalman filtresi, tek eksen (x veya y)."""

    __slots__ = ("x", "v", "Pxx", "Pxv", "Pvv", "Q", "R")

    def __init__(self, x0: float, v0: float, Q: float, R: float):
        self.x = x0
        self.v = v0
        self.Pxx = R       # başlangıç belirsizliği = ölçüm gürültüsü
        self.Pxv = 0.0
        self.Pvv = Q * 10  # hız belirsizliği başlangıçta yüksek
        self.Q = Q
        self.R = R

    def tahmin(self, dt: float):
        """Zaman adımı tahmini (prediction)."""
        # x = x + v*dt
        self.x += self.v * dt
        # P = F P F' + Q_d
        self.Pxx += 2 * dt * self.Pxv + dt * dt * self.Pvv + self.Q * dt * dt
        self.Pxv += dt * self.Pvv + self.Q * dt
        self.Pvv += self.Q

    def duzelt(self, olcum: float):
        """Ölçüm düzeltmesi (update)."""
        S = self.Pxx + self.R
        if S < 1e-12:
            S = 1e-12
        Kx = self.Pxx / S
        Kv = self.Pxv / S
        yenilik = olcum - self.x
        self.x += Kx * yenilik
        self.v += Kv * yenilik
        Pxx_eski = self.Pxx
        Pxv_eski = self.Pxv
        self.Pxx -= Kx * Pxx_eski
        self.Pxv -= Kx * Pxv_eski
        self.Pvv -= Kv * Pxv_eski
