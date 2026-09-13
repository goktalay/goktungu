# -*- coding: utf-8 -*-
"""RotaYoneticisi: rota kayitlarini SQLite'ta saklar.

Mevcut gcs_rotalar.json varsa ilk calistirmada otomatik aktarilir.
"""
import json
import math
import threading

from .sabitler import PROJE_KOKU, _veri_yolu
from .veritabani import baglanti, tablolari_olustur

import os
DOSYA_ESKI = _veri_yolu("gcs_rotalar.json")

_R_DUNYA = 6371000.0


def _haversine(lat1, lon1, lat2, lon2):
    """Iki koordinat arasi buyuk daire mesafesi (m)."""
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (math.sin(df / 2) ** 2
         + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2)
    return 2 * _R_DUNYA * math.asin(math.sqrt(a))


def _aci_dogrula(deger):
    """Nokta yonelim acisini (yaw/heading) dogrular.

    v2.4.23: Rota parametre duzenleme ile eklendi.
    Kabul: 0-359.9 derece (pusula, 0=kuzey) veya -1 (otomatik/serbest).
    Gecersiz / bos deger -> None (alan hic yazilmaz, geriye uyumlu).
    """
    if deger is None or deger == "":
        return None
    try:
        a = float(deger)
    except (TypeError, ValueError):
        return None
    if a < 0:
        return -1.0                      # otomatik: rota yonune bak
    return round(a % 360.0, 1)


def _nokta_dogrula(n):
    """Tek nokta sozlugunu dogrular; temiz kopya veya None dondurur."""
    try:
        lat = float(n.get("lat"))
        lon = float(n.get("lon"))
        irtifa = float(n.get("irtifa"))
        hiz = float(n.get("hiz"))
    except (TypeError, ValueError, AttributeError):
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    temiz = {"lat": round(lat, 7), "lon": round(lon, 7),
             "irtifa": round(max(1.0, min(2000.0, irtifa)), 1),
             "hiz": round(max(0.5, min(83.3, hiz)), 1)}  # v2.4.13: 300 km/h
    # v2.4.23: nokta bazli yonelim acisi (opsiyonel)
    aci = _aci_dogrula(n.get("aci"))
    if aci is not None:
        temiz["aci"] = aci
    # v2.4.23: bekleme suresi (saniye) — opsiyonel, ilaclama/foto icin
    try:
        bekle = float(n.get("bekle"))
    except (TypeError, ValueError):
        bekle = None
    if bekle is not None and bekle > 0:
        temiz["bekle"] = round(min(600.0, bekle), 1)
    return temiz


def _satir_sozluk(row):
    """SQLite Row'u frontend uyumlu dict'e donusturur."""
    r = dict(row)
    r["noktalar"] = json.loads(r.get("noktalar") or "[]")
    r["gorunur"] = bool(r.get("gorunur", 1))
    # v2.4.5: rota tipi meta verisi (serbest form vb.)
    try:
        r["meta"] = json.loads(r.get("meta") or "null") or None
    except (ValueError, TypeError):
        r["meta"] = None
    # Eski alan adlariyla uyumluluk (sunucu.py ve gorev.py icin)
    r["irtifa_varsayilan"] = r.pop("irtifa", 50.0)
    r["hiz_varsayilan"] = r.pop("hiz", 10.0)
    return r


class RotaYoneticisi:

    def __init__(self):
        tablolari_olustur()
        self._kilit = threading.Lock()
        self._json_goc()

    # ------------------------------------------------------------------
    # JSON → SQLite gocu
    # ------------------------------------------------------------------
    def _json_goc(self):
        with baglanti() as con:
            if con.execute(
                    "SELECT COUNT(*) FROM rotalar").fetchone()[0] > 0:
                return
        if not os.path.isfile(DOSYA_ESKI):
            return
        try:
            with open(DOSYA_ESKI, "r", encoding="utf-8") as f:
                liste = json.load(f).get("rotalar", [])
        except Exception:
            return
        with baglanti() as con:
            for r in liste:
                con.execute(
                    "INSERT OR IGNORE INTO rotalar "
                    "(id, isim, irtifa, hiz, gorunur, noktalar) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        r["id"],
                        r["isim"],
                        r.get("irtifa_varsayilan", 50.0),
                        r.get("hiz_varsayilan", 10.0),
                        1 if r.get("gorunur", True) else 0,
                        json.dumps(r.get("noktalar", []),
                                   ensure_ascii=False),
                    ),
                )
        print(f"[ROTA] gcs_rotalar.json -> gcs.db aktarildi "
              f"({len(liste)} kayit).")

    # ------------------------------------------------------------------
    @staticmethod
    def mesafe(rota):
        """Rota noktalari boyunca toplam yatay mesafe (m)."""
        n = rota.get("noktalar", [])
        toplam = 0.0
        for i in range(1, len(n)):
            toplam += _haversine(n[i-1]["lat"], n[i-1]["lon"],
                                 n[i]["lat"], n[i]["lon"])
        return round(toplam, 1)

    def rota_listele(self):
        with baglanti() as con:
            rows = con.execute(
                "SELECT * FROM rotalar ORDER BY id"
            ).fetchall()
        sonuc = []
        for row in rows:
            r = _satir_sozluk(row)
            r["mesafe_m"] = self.mesafe(r)
            sonuc.append(r)
        return sonuc

    @staticmethod
    def _meta_temizle(meta):
        """Meta sozlugunu dogrular; JSON metni veya '' dondurur."""
        if not isinstance(meta, dict):
            return ""
        try:
            metin = json.dumps(meta, ensure_ascii=False)
        except (TypeError, ValueError):
            return ""
        return metin if len(metin) <= 100000 else ""

    def rota_ekle(self, isim, irtifa_varsayilan, hiz_varsayilan,
                  noktalar=None, meta=None):
        isim = (isim or "").strip()[:60]
        if not isim:
            return None, None
        try:
            irtifa = max(1.0, min(2000.0, float(irtifa_varsayilan)))
            hiz = max(0.5, min(83.3, float(hiz_varsayilan)))  # 300 km/h
        except (TypeError, ValueError):
            return None, None
        temiz = []
        for n in (noktalar or []):
            tn = _nokta_dogrula(n)
            if tn is not None:
                temiz.append(tn)
        with self._kilit:
            with baglanti() as con:
                cur = con.execute(
                    "INSERT INTO rotalar "
                    "(isim, irtifa, hiz, gorunur, noktalar, meta) "
                    "VALUES (?,?,?,1,?,?)",
                    (isim, round(irtifa, 1), round(hiz, 1),
                     json.dumps(temiz, ensure_ascii=False),
                     self._meta_temizle(meta)),
                )
                yeni_id = cur.lastrowid
        return yeni_id, self.rota_listele()

    def rota_guncelle(self, rota_id, isim=None, irtifa_varsayilan=None,
                      hiz_varsayilan=None, noktalar=None, gorunur=None,
                      meta=None):
        with self._kilit:
            with baglanti() as con:
                row = con.execute(
                    "SELECT * FROM rotalar WHERE id = ?",
                    (rota_id,)
                ).fetchone()
                if not row:
                    return None
                r = dict(row)
                if isim is not None:
                    isim = str(isim).strip()[:60]
                    if not isim:
                        return None
                    r["isim"] = isim
                if irtifa_varsayilan is not None:
                    try:
                        r["irtifa"] = round(
                            max(1.0, min(2000.0,
                                         float(irtifa_varsayilan))), 1)
                    except (TypeError, ValueError):
                        return None
                if hiz_varsayilan is not None:
                    try:
                        r["hiz"] = round(
                            max(0.5, min(83.3,
                                         float(hiz_varsayilan))), 1)
                    except (TypeError, ValueError):
                        return None
                if noktalar is not None:
                    temiz = []
                    for n in noktalar:
                        tn = _nokta_dogrula(n)
                        if tn is None:
                            return None
                        temiz.append(tn)
                    r["noktalar"] = json.dumps(temiz, ensure_ascii=False)
                if gorunur is not None:
                    r["gorunur"] = 1 if gorunur else 0
                if meta is not None:
                    r["meta"] = self._meta_temizle(meta)
                con.execute(
                    "UPDATE rotalar "
                    "SET isim=?, irtifa=?, hiz=?, gorunur=?, noktalar=?,"
                    " meta=? WHERE id=?",
                    (r["isim"], r["irtifa"], r["hiz"],
                     r["gorunur"], r["noktalar"], r.get("meta") or "",
                     rota_id),
                )
        return self.rota_listele()

    def rota_sil(self, rota_id):
        with self._kilit:
            with baglanti() as con:
                cur = con.execute(
                    "DELETE FROM rotalar WHERE id = ?", (rota_id,)
                )
                if cur.rowcount == 0:
                    return None
        return self.rota_listele()
