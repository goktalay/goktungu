"""LokasyonYoneticisi: lokasyonlari yerel veritabaninda saklar.

Mevcut lokasyonlar.json varsa ilk calistirmada otomatik aktarilir.
Is 97: firma_id verilen islemler yalniz o firmaya ait kayitlari gorur ve
degistirir. Eski cagri yerleri icin firma_id=None geriye uyumludur.
"""
import json
import os
import threading

from .sabitler import LOKASYON_DOSYASI
from .veritabani import baglanti, tablolari_olustur


def _firma_id(deger):
    try:
        sonuc = int(deger)
        return sonuc if sonuc > 0 else None
    except (TypeError, ValueError):
        return None


class LokasyonYoneticisi:

    def __init__(self):
        tablolari_olustur()
        self._kilit = threading.Lock()
        self._json_goc()

    # ------------------------------------------------------------------
    # JSON -> veritabani gocu
    # ------------------------------------------------------------------
    def _json_goc(self):
        with baglanti() as con:
            if con.execute(
                    "SELECT COUNT(*) FROM lokasyonlar").fetchone()[0] > 0:
                return
        if not os.path.isfile(LOKASYON_DOSYASI):
            return
        try:
            with open(LOKASYON_DOSYASI, "r", encoding="utf-8") as f:
                liste = json.load(f).get("lokasyonlar", [])
        except Exception:
            return
        with baglanti() as con:
            for lok in liste:
                if "id" in lok:
                    con.execute(
                        "INSERT OR IGNORE INTO lokasyonlar "
                        "(id, ad, lat, lon, firma_id) VALUES (?,?,?,?,?)",
                        (lok["id"], lok["ad"], lok["lat"], lok["lon"],
                         _firma_id(lok.get("firma_id"))),
                    )
                else:
                    con.execute(
                        "INSERT INTO lokasyonlar "
                        "(ad, lat, lon, firma_id) VALUES (?,?,?,?)",
                        (lok["ad"], lok["lat"], lok["lon"],
                         _firma_id(lok.get("firma_id"))),
                    )
        print(f"[LOK] lokasyonlar.json -> gcs.db aktarildi "
              f"({len(liste)} kayit).")

    # ------------------------------------------------------------------
    def yukle(self, firma_id=None):
        fid = _firma_id(firma_id)
        with baglanti() as con:
            if fid is None:
                rows = con.execute(
                    "SELECT * FROM lokasyonlar ORDER BY id"
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM lokasyonlar WHERE firma_id=? ORDER BY id",
                    (fid,),
                ).fetchall()
        return [dict(r) for r in rows]

    def ekle(self, ad, lat, lon, adres="", firma_id=None):
        ad = (ad or "").strip()[:60]
        adres = (adres or "").strip()[:200]
        fid = _firma_id(firma_id)
        if not ad:
            return None
        try:
            lat = float(lat)
            lon = float(lon)
        except (TypeError, ValueError):
            return None
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return None
        with self._kilit:
            with baglanti() as con:
                con.execute(
                    "INSERT INTO lokasyonlar "
                    "(ad, lat, lon, adres, firma_id) VALUES (?,?,?,?,?)",
                    (ad, round(lat, 7), round(lon, 7), adres, fid),
                )
        return self.yukle(fid)

    def duzenle(self, lok_id, yeni_ad, adres=None, lat=None, lon=None,
                firma_id=None):
        """Ad zorunlu; adres/lat/lon verilirse birlikte guncellenir."""
        yeni_ad = (yeni_ad or "").strip()[:60]
        fid = _firma_id(firma_id)
        if not yeni_ad:
            return None
        alanlar, degerler = ["ad = ?"], [yeni_ad]
        if adres is not None:
            alanlar.append("adres = ?")
            degerler.append((adres or "").strip()[:200])
        try:
            if lat is not None and lon is not None:
                lat, lon = float(lat), float(lon)
                if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                    alanlar.append("lat = ?")
                    degerler.append(round(lat, 7))
                    alanlar.append("lon = ?")
                    degerler.append(round(lon, 7))
        except (TypeError, ValueError):
            pass
        degerler.append(lok_id)
        sorgu = (f"UPDATE lokasyonlar SET {', '.join(alanlar)} WHERE id = ?")
        if fid is not None:
            sorgu += " AND firma_id = ?"
            degerler.append(fid)
        with self._kilit:
            with baglanti() as con:
                cur = con.execute(sorgu, degerler)
                if cur.rowcount == 0:
                    return None
        return self.yukle(fid)

    def sil(self, lok_id, firma_id=None):
        fid = _firma_id(firma_id)
        sorgu = "DELETE FROM lokasyonlar WHERE id = ?"
        degerler = [lok_id]
        if fid is not None:
            sorgu += " AND firma_id = ?"
            degerler.append(fid)
        with self._kilit:
            with baglanti() as con:
                con.execute(sorgu, degerler)
        return self.yukle(fid)
