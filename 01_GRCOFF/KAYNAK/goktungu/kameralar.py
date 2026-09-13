# -*- coding: utf-8 -*-
"""KameraYoneticisi: kamera kayitlarini SQLite'ta saklar.

Mevcut gcs_kameralar.json varsa ilk calistirmada otomatik aktarilir.
"""
import json
import math
import threading

from .sabitler import PROJE_KOKU, _veri_yolu
from .veritabani import baglanti, tablolari_olustur

import os
DOSYA_ESKI = _veri_yolu("gcs_kameralar.json")

GECERLI_PROTOKOLLER = ("rtsp", "rtp", "mjpeg", "hls", "http", "donanim",
                       "dji")
PROXY_GEREKTIREN = ("rtsp", "rtp")


class KameraYoneticisi:

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
                    "SELECT COUNT(*) FROM kameralar").fetchone()[0] > 0:
                return
        if not os.path.isfile(DOSYA_ESKI):
            return
        try:
            with open(DOSYA_ESKI, "r", encoding="utf-8") as f:
                liste = json.load(f).get("kameralar", [])
        except Exception:
            return
        with baglanti() as con:
            for k in liste:
                con.execute(
                    "INSERT OR IGNORE INTO kameralar "
                    "(id, isim, protokol, url) VALUES (?,?,?,?)",
                    (k["id"], k["isim"],
                     k.get("protokol", "http"), k.get("url", "")),
                )
        print(f"[KAMERA] gcs_kameralar.json -> gcs.db aktarildi "
              f"({len(liste)} kayit).")

    # ------------------------------------------------------------------
    @staticmethod
    def _dogrula(isim, protokol, url):
        isim = (isim or "").strip()[:60]
        protokol = (protokol or "").strip().lower()
        url = (url or "").strip()[:500]
        if not isim or not url:
            return None
        if protokol not in GECERLI_PROTOKOLLER:
            return None
        return isim, protokol, url

    # ------------------------------------------------------------------
    # v2.4.56: firma izolasyonu + kopru gruplamasi
    # ------------------------------------------------------------------
    # `firma_id=None` -> suzgec UYGULANMAZ. Ic cagrilar (AI gorev
    # dagitimi, acilis taramasi, video proxy) tum kameralari gormeye
    # devam eder; lokal kurulum davranisi birebir korunur.
    @staticmethod
    def _firma_suzgeci(firma_id):
        if not firma_id:
            return "", ()
        return " WHERE (firma_id = ? OR firma_id IS NULL)", (int(firma_id),)

    def listele(self, firma_id=None):
        kosul, par = self._firma_suzgeci(firma_id)
        with baglanti() as con:
            rows = con.execute(
                "SELECT * FROM kameralar" + kosul + " ORDER BY id", par
            ).fetchall()
        return [dict(r) for r in rows]

    def sahibi_mi(self, kamera_id, firma_id) -> bool:
        """Kayit bu firmaya mi ait (veya firmasiz eski kayit mi)."""
        if not firma_id:
            return True
        with baglanti() as con:
            r = con.execute("SELECT firma_id FROM kameralar WHERE id=?",
                            (int(kamera_id),)).fetchone()
        if not r:
            return False
        mevcut = dict(r).get("firma_id")
        return mevcut is None or int(mevcut) == int(firma_id)

    def bul(self, kamera_id):
        with baglanti() as con:
            row = con.execute(
                "SELECT * FROM kameralar WHERE id = ?", (int(kamera_id),)
            ).fetchone()
        return dict(row) if row else None

    # v2.4.2: kamera basina AI gorev anahtarlari
    GECERLI_AI_GOREVLER = ("yuz", "plaka", "hava_araci", "insan",
                           "kara_araci")

    @classmethod
    def _ai_gorevler(cls, deger):
        """CSV/list AI gorev degerini dogrulanmis CSV'ye cevirir."""
        if isinstance(deger, (list, tuple)):
            parcalar = [str(p) for p in deger]
        else:
            parcalar = str(deger or "").split(",")
        temiz = []
        for p in parcalar:
            p = p.strip().lower()
            if p in cls.GECERLI_AI_GOREVLER and p not in temiz:
                temiz.append(p)
        return ",".join(temiz)

    @staticmethod
    def _lokasyon_id(deger):
        """lokasyon_id degerini dogrular (None veya pozitif int)."""
        try:
            v = int(deger)
            return v if v > 0 else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _ai_hassasiyet(deger):
        """Sınıf başına hassasiyeti dogrulanmis JSON dizeye cevirir.

        Yalniz insan/yuz/kara_araci/hava_araci anahtarlari, 10-90 araligi.
        Gecersiz/eksik alan tamamen atlanir (isci varsayilani 50 uygular).
        """
        import json as _j
        if isinstance(deger, str):
            try:
                deger = _j.loads(deger) if deger.strip() else {}
            except (ValueError, TypeError):
                return ""
        if not isinstance(deger, dict):
            return ""
        temiz = {}
        # v2.4.161: "yuz" (yakin cekim yuz tespiti) ayri gorev/hassasiyet.
        for k in ("insan", "yuz", "kara_araci", "hava_araci"):
            try:
                v = int(round(float(deger[k])))
            except (KeyError, TypeError, ValueError):
                continue
            if 10 <= v <= 90:
                temiz[k] = v
        return _j.dumps(temiz, separators=(",", ":")) if temiz else ""

    def ekle(self, isim, protokol, url, lokasyon_id=None,
             ai_gorevler="", firma_id=None, kopru_ornek_id=None,
             ai_hassasiyet=""):
        d = self._dogrula(isim, protokol, url)
        if d is None:
            return None, None
        isim, protokol, url = d
        lok = self._lokasyon_id(lokasyon_id)
        gorevler = self._ai_gorevler(ai_gorevler)
        hassas = self._ai_hassasiyet(ai_hassasiyet)
        fid = int(firma_id) if firma_id else None
        kopru = self._lokasyon_id(kopru_ornek_id)   # ayni dogrulama
        with self._kilit:
            with baglanti() as con:
                cur = con.execute(
                    "INSERT INTO kameralar (isim, protokol, url, "
                    "lokasyon_id, ai_gorevler, firma_id, kopru_ornek_id, "
                    "ai_hassasiyet) VALUES (?,?,?,?,?,?,?,?)",
                    (isim, protokol, url, lok, gorevler, fid, kopru, hassas),
                )
                yeni_id = cur.lastrowid
        return yeni_id, self.listele(firma_id)

    def guncelle(self, kamera_id, isim, protokol, url, lokasyon_id=None,
                 ai_gorevler="", firma_id=None, kopru_ornek_id=None,
                 ai_hassasiyet=None):
        d = self._dogrula(isim, protokol, url)
        if d is None:
            return None
        if not self.sahibi_mi(kamera_id, firma_id):
            return None
        isim, protokol, url = d
        lok = self._lokasyon_id(lokasyon_id)
        gorevler = self._ai_gorevler(ai_gorevler)
        kopru = self._lokasyon_id(kopru_ornek_id)
        with self._kilit:
            with baglanti() as con:
                if ai_hassasiyet is None:
                    # Eski istemci alanı göndermez: mevcut değeri KORU.
                    cur = con.execute(
                        "UPDATE kameralar "
                        "SET isim=?, protokol=?, url=?, lokasyon_id=?, "
                        "ai_gorevler=?, kopru_ornek_id=? WHERE id=?",
                        (isim, protokol, url, lok, gorevler, kopru,
                         int(kamera_id)),
                    )
                else:
                    cur = con.execute(
                        "UPDATE kameralar "
                        "SET isim=?, protokol=?, url=?, lokasyon_id=?, "
                        "ai_gorevler=?, kopru_ornek_id=?, ai_hassasiyet=? "
                        "WHERE id=?",
                        (isim, protokol, url, lok, gorevler, kopru,
                         self._ai_hassasiyet(ai_hassasiyet), int(kamera_id)),
                    )
                if cur.rowcount == 0:
                    return None
        return self.listele(firma_id)

    def sil(self, kamera_id, firma_id=None):
        if not self.sahibi_mi(kamera_id, firma_id):
            return None
        with self._kilit:
            with baglanti() as con:
                cur = con.execute(
                    "DELETE FROM kameralar WHERE id = ?", (int(kamera_id),)
                )
                if cur.rowcount == 0:
                    return None
        return self.listele(firma_id)

    # ------------------------------------------------------------------
    # v2.5.21: Yerel AI angajman kalibrasyonu (iki kamera tipi)
    # ------------------------------------------------------------------
    GECERLI_KAMERA_TIPLERI = ("sabit", "dron")

    @staticmethod
    def _f(deger):
        """None/gecersizde None; aksi halde sonlu float."""
        try:
            v = float(deger)
        except (TypeError, ValueError):
            return None
        return v if math.isfinite(v) else None

    @classmethod
    def _kalibrasyon_dogrula(cls, veri):
        """Kamera kalibrasyon girisini dogrular ve alan sozlugu doner.

        `kalibre` ancak SECILEN tip icin gerekli tum alanlar gecerliyse 1
        olur. Eksik/gecersiz kalibrasyon = 0; boylece yerel hedef cozumu
        (yerel_hedef.py) "sessiz yanlis konum" yerine acik ret uretir.

        Iki tip:
          'sabit' -> lat/lon/kam_yukseklik/yon/tilt/fov_yatay/fov_dikey
          'dron'  -> dron_uid + fov + montaj_pan/tilt/roll
        """
        tip = str(veri.get("kamera_tipi") or "sabit").strip().lower()
        if tip not in cls.GECERLI_KAMERA_TIPLERI:
            tip = "sabit"
        lat = cls._f(veri.get("lat"))
        lon = cls._f(veri.get("lon"))
        H = cls._f(veri.get("kam_yukseklik"))
        yon = cls._f(veri.get("yon"))
        tilt = cls._f(veri.get("tilt"))
        fov_y = cls._f(veri.get("fov_yatay"))
        fov_d = cls._f(veri.get("fov_dikey"))
        mpan = cls._f(veri.get("montaj_pan"))
        mtilt = cls._f(veri.get("montaj_tilt"))
        mroll = cls._f(veri.get("montaj_roll"))

        def _koord(la, lo):
            return (la is not None and lo is not None and
                    -90.0 <= la <= 90.0 and -180.0 <= lo <= 180.0)

        def _fov(f):
            return f is not None and 0.0 < f < 180.0

        kalibre = 0
        if tip == "sabit":
            if (_koord(lat, lon) and H is not None and H >= 0 and
                    yon is not None and tilt is not None and
                    _fov(fov_y) and _fov(fov_d)):
                kalibre = 1
        else:  # dron
            uid = str(veri.get("dron_uid") or "").strip()
            if (uid and _fov(fov_y) and _fov(fov_d) and
                    None not in (mpan, mtilt, mroll)):
                kalibre = 1

        return {
            "kamera_tipi": tip,
            "lat": lat, "lon": lon, "kam_yukseklik": H,
            "yon": yon, "tilt": tilt,
            "fov_yatay": fov_y, "fov_dikey": fov_d,
            "montaj_pan": mpan, "montaj_tilt": mtilt, "montaj_roll": mroll,
            "kalibre": kalibre,
        }

    def kalibrasyon_kaydet(self, kamera_id, veri, firma_id=None):
        """Kamera kalibrasyon alanlarini gunceller. Guncel liste veya None."""
        if not self.sahibi_mi(kamera_id, firma_id):
            return None
        a = self._kalibrasyon_dogrula(veri if isinstance(veri, dict) else {})
        with self._kilit:
            with baglanti() as con:
                cur = con.execute(
                    "UPDATE kameralar SET kamera_tipi=?, lat=?, lon=?, "
                    "kam_yukseklik=?, yon=?, tilt=?, fov_yatay=?, "
                    "fov_dikey=?, montaj_pan=?, montaj_tilt=?, "
                    "montaj_roll=?, kalibre=? WHERE id=?",
                    (a["kamera_tipi"], a["lat"], a["lon"], a["kam_yukseklik"],
                     a["yon"], a["tilt"], a["fov_yatay"], a["fov_dikey"],
                     a["montaj_pan"], a["montaj_tilt"], a["montaj_roll"],
                     a["kalibre"], int(kamera_id)))
                if cur.rowcount == 0:
                    return None
        return self.listele(firma_id)

    def dron_bagla(self, kamera_id, dron_uid):
        """v2.4.2: Kamerayi drona baglar (dron_uid '' -> bagi cozer).

        Bir drona ayni anda tek kamera baglanabilir: ayni dron_uid'ye
        bagli eski kayitlar once cozulur.  Basarida guncel liste,
        hatada None doner.
        """
        uid = str(dron_uid or "").strip()[:80]
        with self._kilit:
            with baglanti() as con:
                if uid:
                    # ayni drona bagli eski kameralari coz
                    con.execute(
                        "UPDATE kameralar SET dron_uid='' "
                        "WHERE dron_uid=?", (uid,))
                cur = con.execute(
                    "UPDATE kameralar SET dron_uid=? WHERE id=?",
                    (uid, int(kamera_id)),
                )
                if cur.rowcount == 0:
                    return None
        return self.listele()
