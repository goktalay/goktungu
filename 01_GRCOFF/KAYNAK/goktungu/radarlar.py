# -*- coding: utf-8 -*-
"""GÖKTUNGU — ÇOKLU RADAR YÖNETİCİSİ (v2.4.190, Faz A).

Kullanıcı isteği: "3 radar, 4 elektro-optik takıp gelecek tehditleri
harita üzerinden takip edebilmeliyiz." Bu modül tek `RadarIstemcisi`
yerine N radarı yönetir ve ÜÇ iş yapar:

1. KAYIT: `radarlar` tablosu (isim, ip, port, kurulu lat/lon, merkez
   yönü, köprü örneği). Eski tek radar ayarı ilk açılışta "Radar 1"
   olarak taşınır.
2. İSTEMCİ: her kayıt için bir `RadarIstemcisi` (yerel kip) ya da
   `RadarVekili` (merkez kipi; Faz C'ye kadar yalnız 1 numaralı radar
   köprüden beslenir).
3. FÜZYON ÇERÇEVESİ: takipçi (`takip/takipci.py`) izleri tek bir ENU
   düzleminde tutar. Ortak orijin MERKEZ KONUMUDUR; her radarın plotu
   kendi konumundan (RTK / kurulu) merkez orijinine ötelenir ve hedef
   kimliği `radar_id * 1_000_000 + hedef_id` olarak ayrıştırılır. İki
   radarın gördüğü aynı hedefi GNN ataması birleştirir.

GERİYE UYUM (bilinçli): `sunucu.py`, `angajman.py`, `kayit.py` tek
`self.radar` nesnesini `durum / hedefler / radar_ayarlar / ayar_kuyruk /
radar_konum() / baglan() / kes() / kes_kancasi / ayar_yukle()` yüzüyle
kullanıyor. Bu sınıf AYNI yüzü verir: `durum`/`radar_ayarlar`/
`ayar_kuyruk` "birincil" (en küçük kimlikli) radara, `hedefler` ise
MERKEZ ÇERÇEVESİNE ötelenmiş BİRLEŞİK sözlüğe eşlenir. Böylece
angajman zinciri değişmeden çok radarla çalışır.
"""
from __future__ import annotations

import math
import threading
import time
from typing import Any, Dict, Optional

from .veritabani import baglanti

KIMLIK_CARPANI = 1_000_000


def hedef_kimligi(radar_id: int, hedef_id: int) -> int:
    return int(radar_id) * KIMLIK_CARPANI + int(hedef_id)


def kimlik_coz(kimlik: int):
    """(radar_id, hedef_id); ayrıştırılmamış eski kimlikte (0, kimlik)."""
    try:
        k = int(kimlik)
    except (TypeError, ValueError):
        return 0, kimlik
    return divmod(k, KIMLIK_CARPANI) if k >= KIMLIK_CARPANI else (0, k)


# ---------------------------------------------------------------------
# Kayıtlar (DB)
# ---------------------------------------------------------------------
class RadarKayitlari:
    ALANLAR = ("isim", "ip", "port", "lat", "lon", "merkez_yonu",
               "kopru_ornek_id", "otomatik_baglan")

    @staticmethod
    def _temiz(kayit: Dict[str, Any]) -> Dict[str, Any]:
        s: Dict[str, Any] = {}
        s["isim"] = str(kayit.get("isim") or "").strip()[:64] or "Radar"
        s["ip"] = str(kayit.get("ip") or "").strip()[:64]
        try:
            s["port"] = int(kayit.get("port") or 5001)
        except (TypeError, ValueError):
            s["port"] = 5001
        if not (0 < s["port"] < 65536):
            s["port"] = 5001
        for a in ("lat", "lon"):
            v = kayit.get(a)
            try:
                s[a] = float(v) if v not in (None, "") else None
            except (TypeError, ValueError):
                s[a] = None
        try:
            s["merkez_yonu"] = float(kayit.get("merkez_yonu") or 0.0) % 360.0
        except (TypeError, ValueError):
            s["merkez_yonu"] = 0.0
        try:
            k = kayit.get("kopru_ornek_id")
            s["kopru_ornek_id"] = int(k) if k not in (None, "", 0, "0") else None
        except (TypeError, ValueError):
            s["kopru_ornek_id"] = None
        s["otomatik_baglan"] = 1 if kayit.get("otomatik_baglan") else 0
        return s

    def listele(self, firma_id=None):
        """v2.4.231: merkez kipinde firma izolasyonu — `firma_id` verilirse
        yalniz o firmanin (ve sahipsiz eski) kayitlari doner."""
        with baglanti() as con:
            if firma_id:
                rows = con.execute(
                    "SELECT * FROM radarlar WHERE (firma_id = ? OR firma_id IS NULL) "
                    "ORDER BY id", (int(firma_id),)).fetchall()
            else:
                rows = con.execute("SELECT * FROM radarlar ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def firma_ata(self, radar_id, firma_id) -> None:
        if not firma_id:
            return
        with baglanti() as con:
            con.execute("UPDATE radarlar SET firma_id=? WHERE id=?",
                        (int(firma_id), int(radar_id)))

    def bul(self, radar_id):
        with baglanti() as con:
            r = con.execute("SELECT * FROM radarlar WHERE id=?",
                            (int(radar_id),)).fetchone()
        return dict(r) if r else None

    def ekle(self, kayit: Dict[str, Any]) -> int:
        s = self._temiz(kayit)
        with baglanti() as con:
            cur = con.execute(
                "INSERT INTO radarlar (isim, ip, port, lat, lon, merkez_yonu, "
                "kopru_ornek_id, otomatik_baglan) VALUES (?,?,?,?,?,?,?,?)",
                tuple(s[a] for a in self.ALANLAR))
            return int(cur.lastrowid)

    def guncelle(self, radar_id, kayit: Dict[str, Any]) -> bool:
        mevcut = self.bul(radar_id)
        if not mevcut:
            return False
        birlesik = dict(mevcut)
        birlesik.update({k: v for k, v in kayit.items() if k in self.ALANLAR})
        s = self._temiz(birlesik)
        with baglanti() as con:
            con.execute(
                "UPDATE radarlar SET isim=?, ip=?, port=?, lat=?, lon=?, "
                "merkez_yonu=?, kopru_ornek_id=?, otomatik_baglan=? WHERE id=?",
                tuple(s[a] for a in self.ALANLAR) + (int(radar_id),))
        return True

    def sil(self, radar_id) -> None:
        with baglanti() as con:
            con.execute("DELETE FROM radarlar WHERE id=?", (int(radar_id),))

    def eski_ayardan_goc(self, ayarlar) -> None:
        """Tablo boşsa eski tek-radar kurulumundan 'Radar 1' üretir."""
        if self.listele():
            return
        try:
            a = ayarlar.yukle()
        except Exception:
            a = {}
        my = 0.0
        try:
            my = float(a.get("radar_merkez_yonu", 0.0)) % 360.0
        except (TypeError, ValueError):
            pass
        with baglanti() as con:
            con.execute(
                "INSERT INTO radarlar (id, isim, ip, port, lat, lon, merkez_yonu, "
                "kopru_ornek_id, otomatik_baglan) VALUES (1,'Radar 1','',5001,"
                "NULL,NULL,?,NULL,0)", (my,))


# ---------------------------------------------------------------------
# Yönetici (facade)
# ---------------------------------------------------------------------
class RadarYoneticisi:
    def __init__(self, konsol, ayarlar, kilit, kayitlar: RadarKayitlari,
                 istemci_fabrikasi, birincil_istemci=None):
        """
        istemci_fabrikasi(kayit) -> RadarIstemcisi/RadarVekili benzeri nesne
        birincil_istemci: verilirse 1 numaralı radar için hazır nesne
            (merkez kipinde RadarVekili — Faz C'ye kadar tek köprü yolu).
        """
        self.konsol = konsol
        self.ayarlar = ayarlar
        self.kilit = kilit
        self.kayitlar = kayitlar
        self._fabrika = istemci_fabrikasi
        self.istemciler: Dict[int, Any] = {}
        self._kes_kancasi = None
        self._birlesik_hedefler: Dict[int, Dict[str, Any]] = {}
        self._birlesik_ts = 0.0
        self._merkez_konum = None
        self._merkez_ts = 0.0
        self._kopru_cek = None
        self._kopru_kilit = threading.Lock()
        self._kopru_son = (None, "")
        self._kopru_ts = 0.0
        if birincil_istemci is not None:
            self.istemciler[1] = birincil_istemci
        self.tazele()

    # ---------------- kayıt/istemci eşlemesi ----------------
    def tazele(self) -> None:
        """DB kayıtlarıyla istemci sözlüğünü eşitler (silinen kesilir)."""
        kayitlar = {int(k["id"]): k for k in self.kayitlar.listele()}
        for rid in list(self.istemciler):
            # v2.4.232: 1 numara icin istisna kaldirildi — kaydi silinen her
            # radarin istemcisi/vekili dusurulur.
            if rid not in kayitlar:
                try:
                    self.istemciler[rid].kes()
                except Exception:
                    pass
                self.istemciler.pop(rid, None)
        for rid, k in kayitlar.items():
            ist = self.istemciler.get(rid)
            if ist is None:
                ist = self._fabrika(k)
                ist.kes_kancasi = self._kes_kancasi
                self.istemciler[rid] = ist
                if self._kopru_cek is not None and hasattr(ist, "_cek"):
                    ist._cek = self._cek_icin(rid)
            # Kayıt değişmiş olabilir: konum/yön/isim tazele
            try:
                ist.konum_yedek = (k.get("lat"), k.get("lon"))
                ist.isim = k.get("isim") or ""
                with self.kilit:
                    if "merkez_yonu" in ist.radar_ayarlar:
                        ist.radar_ayarlar["merkez_yonu"] = float(k.get("merkez_yonu") or 0.0)
            except Exception:
                pass

    def istemci(self, radar_id=None):
        rid = self._kimlik(radar_id)
        return self.istemciler.get(rid)

    def _kimlik(self, radar_id) -> int:
        try:
            rid = int(radar_id) if radar_id not in (None, "") else 0
        except (TypeError, ValueError):
            rid = 0
        if rid <= 0:
            rid = self.birincil_id()
        return rid

    def birincil_id(self) -> int:
        return min(self.istemciler) if self.istemciler else 1

    # ---------------- geriye uyumlu yüz ----------------
    @property
    def durum(self):
        ist = self.istemciler.get(self.birincil_id())
        return ist.durum if ist is not None else {
            "durum": "kapali", "ip": "", "port": 0, "hata": "", "lat": None,
            "lon": None, "hdt": None, "rtk_durum": "", "rtk_ilerleme": 0}

    @property
    def radar_ayarlar(self):
        ist = self.istemciler.get(self.birincil_id())
        return ist.radar_ayarlar if ist is not None else {}

    @property
    def ayar_kuyruk(self):
        ist = self.istemciler.get(self.birincil_id())
        return ist.ayar_kuyruk if ist is not None else []

    @property
    def kes_kancasi(self):
        return self._kes_kancasi

    @kes_kancasi.setter
    def kes_kancasi(self, f):
        self._kes_kancasi = f
        for ist in self.istemciler.values():
            ist.kes_kancasi = f

    # ---------------- merkez kipi: köprü beslemesi (v2.4.192, Faz C) ----
    # `sunucu.py` tek bir `_cek` (tüm radarların paketini döndüren
    # `_radar_kopru_durum_cek`) bağlar. Yönetici bu çağrıyı 0.4 sn
    # önbellekle TEK HTTP isteğine indirir ve her vekile `radarlar[id]`
    # alt paketini veren bir kapanış dağıtır; böylece 3 radar için 3
    # ayrı köprü sorgusu yapılmaz.
    @property
    def _cek(self):
        if not any(hasattr(i, "_cek") for i in self.istemciler.values()):
            return "YOK"          # yerel kurulum: vekil yok
        return self._kopru_cek

    @_cek.setter
    def _cek(self, f):
        self._kopru_cek = f
        self._cek_dagit()

    def _cek_dagit(self) -> None:
        if self._kopru_cek is None:
            return
        for rid, ist in self.istemciler.items():
            if hasattr(ist, "_cek"):
                ist._cek = self._cek_icin(rid)

    def _cek_icin(self, rid):
        def cek():
            return self._kopru_alt_paket(int(rid))
        return cek

    def _kopru_paket(self):
        simdi = time.time()
        with self._kopru_kilit:
            if simdi - self._kopru_ts < 0.4:
                return self._kopru_son
            f = self._kopru_cek
            if f is None:
                sonuc = (None, "Kopru baglantisi yapilandirilmadi")
            else:
                try:
                    sonuc = f()
                except Exception as e:
                    sonuc = (None, "%s: %s" % (type(e).__name__, e))
            self._kopru_son = sonuc
            self._kopru_ts = simdi
            return sonuc

    def _kopru_alt_paket(self, rid: int):
        paket, hata = self._kopru_paket()
        if hata or not isinstance(paket, dict):
            return None, hata or "Kopru yanit vermedi"
        radarlar = paket.get("radarlar")
        if isinstance(radarlar, dict):
            alt = radarlar.get(str(rid))
            if isinstance(alt, dict):
                return alt, ""
            return None, ("Saha Koprusu %d numarali radari bildirmiyor; "
                          "bu radara 'Baglan' verin." % rid)
        # Eski köprü (<1.7.19): yalnız tek radar taşır.
        if rid == self.birincil_id():
            return paket, ""
        return None, ("Saha Koprusu coklu radar desteklemiyor "
                      "(Kopru 1.7.19+ gerekir).")

    def cek_gerekirse(self):
        for ist in self.istemciler.values():
            f = getattr(ist, "cek_gerekirse", None)
            if f is not None:
                f()

    def ayar_yukle(self):
        for ist in self.istemciler.values():
            try:
                ist.ayar_yukle()
            except Exception:
                pass
        # Kayıttaki merkez yönü DB'de yaşar; ayar dosyasını ezmesin.
        self.tazele()

    def radar_konum(self):
        """Ortak izleme orijini: MERKEZ konumu (füzyon çerçevesi).
        Telemetri döngüsü her turda sorduğu için 2 sn önbelleklenir
        (ayarlar.yukle() veritabanına gider)."""
        simdi = time.time()
        if simdi - self._merkez_ts < 2.0 and self._merkez_konum is not None:
            return self._merkez_konum
        try:
            a = self.ayarlar.yukle()
            konum = (float(a["merkez_lat"]), float(a["merkez_lon"]))
        except (KeyError, TypeError, ValueError):
            ist = self.istemciler.get(self.birincil_id())
            konum = ist.radar_konum() if ist is not None else (None, None)
        self._merkez_konum = konum
        self._merkez_ts = simdi
        return konum

    def baglan(self, ip, port, radar_id=None):
        rid = self._kimlik(radar_id)
        ist = self.istemciler.get(rid)
        if ist is None:
            return False
        try:
            self.kayitlar.guncelle(rid, {"ip": ip, "port": port})
        except Exception:
            pass
        ist.baglan(ip, port)
        return True

    def kes(self, radar_id=None):
        if radar_id is None:
            for ist in self.istemciler.values():
                ist.kes()
            return
        ist = self.istemciler.get(self._kimlik(radar_id))
        if ist is not None:
            ist.kes()

    # ---------------- füzyon ----------------
    @property
    def hedefler(self) -> Dict[int, Dict[str, Any]]:
        """Merkez çerçevesine ötelenmiş, kimliği ayrıştırılmış birleşik
        plot sözlüğü. Telemetri döngüsü ~0.5 s'de bir sorar; aynı turda
        tekrar sorulursa önbellekten döner.

        KİLİT ALINMAZ (bilinçli): çağıran telemetri döngüsü zaten
        `self.kilit` içindedir ve Lock yeniden girişli değildir; burada
        tekrar alınsa kilitlenirdi. `dict(...)` kopyası CPython'da GIL
        altında atomiktir; okuma thread'inin eşzamanlı yazımı yalnız
        bir sonraki turda görünür.
        """
        simdi = time.time()
        if simdi - self._birlesik_ts < 0.05:
            return self._birlesik_hedefler
        mlat, mlon = self.radar_konum()
        birlesik: Dict[int, Dict[str, Any]] = {}
        for rid, ist in list(self.istemciler.items()):
            try:
                rlat, rlon = ist.radar_konum()
            except Exception:
                rlat = rlon = None
            if mlat is not None and rlat is not None:
                dy = (rlat - mlat) * 111320.0
                dx = (rlon - mlon) * 111320.0 * math.cos(math.radians(mlat))
            else:
                dx = dy = 0.0
            try:
                hedefler = list(dict(ist.hedefler).items())
            except Exception:
                continue
            for hid, h in hedefler:
                p = dict(h)
                try:
                    hid_i = int(hid)
                except (TypeError, ValueError):
                    continue
                p["id"] = hedef_kimligi(rid, hid_i)
                p["radar_id"] = rid
                p["radar_hedef_id"] = hid_i
                if "x" in p:
                    p["x"] = float(p.get("x", 0.0)) + dx
                if "y" in p:
                    p["y"] = float(p.get("y", 0.0)) + dy
                birlesik[p["id"]] = p
        self._birlesik_hedefler = birlesik
        self._birlesik_ts = simdi
        return birlesik

    # ---------------- telemetri ----------------
    def durumlar(self) -> list:
        cikti = []
        kayitlar = {int(k["id"]): k for k in self.kayitlar.listele()}
        for rid in sorted(self.istemciler):
            ist = self.istemciler[rid]
            k = kayitlar.get(rid, {})
            # Kilitsiz kopya (bkz. hedefler): cagiran taraf kilit
            # tutuyor olabilir.
            d = dict(ist.durum)
            d["ayarlar"] = dict(ist.radar_ayarlar)
            try:
                lat, lon = ist.radar_konum()
            except Exception:
                lat = lon = None
            d.update({"radar_id": rid, "isim": k.get("isim") or getattr(ist, "isim", "") or ("Radar %d" % rid),
                      "kayit_ip": k.get("ip") or "", "kayit_port": k.get("port") or 5001,
                      "kayit_lat": k.get("lat"), "kayit_lon": k.get("lon"),
                      "konum_lat": lat, "konum_lon": lon,
                      "kopru_ornek_id": k.get("kopru_ornek_id"),
                      "firma_id": k.get("firma_id"),   # v2.4.231: telemetri firma suzgeci
                      "otomatik_baglan": bool(k.get("otomatik_baglan"))})
            cikti.append(d)
        return cikti
