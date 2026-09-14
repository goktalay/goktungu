# -*- coding: utf-8 -*-
"""GÖKTUNGU — ÇOKLU ELEKTRO-OPTİK (M50) YÖNETİCİSİ (v2.4.191, Faz B).

Radar tarafındaki `radarlar.py` ile aynı desen: `eo_cihazlar` tablosu
(isim, tür, ip, port, kayıtlı konum, köprü örneği) + cihaz başına bir
çift nesne: `M50Vekili` (arındırılmış durum / telemetri yüzü) ve
`M50YerelServisi` (köprüsüz SDK sürücüsü). Kimlik bilgisi (kullanıcı
adı/parola) yerel servisin kendi ayar anahtarında yaşar (eo başına
`m50_yerel_<id>`); 1 numaralı cihaz eski `m50_yerel` anahtarını
devralır.

GERİYE UYUM: `sunucu.py` `self.m50` / `self.m50_yerel` olarak BİRİNCİL
cihazın nesnelerini görmeye devam eder; `eo_id` taşıyan komutlar
`istemci(eo_id)` ile hedeflenir. Kamera kaydı `m50:<eo_id>:<kanal>`
biçimini alır; eski `m50:<kanal>` 1 numaralı cihaz sayılır.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional, Tuple

from .veritabani import baglanti


class EOKayitlari:
    ALANLAR = ("isim", "tur", "ip", "port", "lat", "lon", "kopru_ornek_id",
               "otomatik_baglan")

    @staticmethod
    def _temiz(kayit: Dict[str, Any]) -> Dict[str, Any]:
        s: Dict[str, Any] = {}
        s["isim"] = str(kayit.get("isim") or "").strip()[:64] or "M50"
        s["tur"] = str(kayit.get("tur") or "m50").strip().lower()[:16] or "m50"
        s["ip"] = str(kayit.get("ip") or "").strip()[:64]
        try:
            s["port"] = int(kayit.get("port") or 39020)
        except (TypeError, ValueError):
            s["port"] = 39020
        if not (0 < s["port"] < 65536):
            s["port"] = 39020
        for a in ("lat", "lon"):
            v = kayit.get(a)
            try:
                s[a] = float(v) if v not in (None, "") else None
            except (TypeError, ValueError):
                s[a] = None
        try:
            k = kayit.get("kopru_ornek_id")
            s["kopru_ornek_id"] = int(k) if k not in (None, "", 0, "0") else None
        except (TypeError, ValueError):
            s["kopru_ornek_id"] = None
        s["otomatik_baglan"] = 1 if kayit.get("otomatik_baglan", 1) else 0
        return s

    def listele(self):
        with baglanti() as con:
            rows = con.execute("SELECT * FROM eo_cihazlar ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def bul(self, eo_id):
        with baglanti() as con:
            r = con.execute("SELECT * FROM eo_cihazlar WHERE id=?",
                            (int(eo_id),)).fetchone()
        return dict(r) if r else None

    def ekle(self, kayit: Dict[str, Any]) -> int:
        s = self._temiz(kayit)
        with baglanti() as con:
            cur = con.execute(
                "INSERT INTO eo_cihazlar (isim, tur, ip, port, lat, lon, "
                "kopru_ornek_id, otomatik_baglan) VALUES (?,?,?,?,?,?,?,?)",
                tuple(s[a] for a in self.ALANLAR))
            return int(cur.lastrowid)

    def guncelle(self, eo_id, kayit: Dict[str, Any]) -> bool:
        mevcut = self.bul(eo_id)
        if not mevcut:
            return False
        birlesik = dict(mevcut)
        birlesik.update({k: v for k, v in kayit.items() if k in self.ALANLAR})
        s = self._temiz(birlesik)
        with baglanti() as con:
            con.execute(
                "UPDATE eo_cihazlar SET isim=?, tur=?, ip=?, port=?, lat=?, lon=?, "
                "kopru_ornek_id=?, otomatik_baglan=? WHERE id=?",
                tuple(s[a] for a in self.ALANLAR) + (int(eo_id),))
        return True

    def sil(self, eo_id) -> None:
        with baglanti() as con:
            con.execute("DELETE FROM eo_cihazlar WHERE id=?", (int(eo_id),))

    def ilk_kaydi_garanti_et(self) -> None:
        """Tablo boşsa 'M50 1' üretir (eski tek-cihaz kurulumu)."""
        if self.listele():
            return
        with baglanti() as con:
            con.execute(
                "INSERT INTO eo_cihazlar (id, isim, tur, ip, port, lat, lon, "
                "kopru_ornek_id, otomatik_baglan) VALUES (1,'M50 1','m50','',39020,"
                "NULL,NULL,NULL,1)")


def kamera_url_coz(url: str) -> Tuple[Optional[int], str]:
    """'m50:<kanal>' -> (None, kanal); 'm50:<eo_id>:<kanal>' -> (eo_id, kanal)."""
    parcalar = str(url or "").split(":")
    if len(parcalar) >= 3:
        try:
            return int(parcalar[1]), parcalar[2].strip().lower()
        except (TypeError, ValueError):
            return None, parcalar[-1].strip().lower()
    if len(parcalar) == 2:
        return None, parcalar[1].strip().lower()
    return None, ""


class EOYoneticisi:
    def __init__(self, konsol, ayarlar, kilit, kayitlar: EOKayitlari,
                 vekil_fabrikasi, yerel_fabrikasi):
        self.konsol = konsol
        self.ayarlar = ayarlar
        self.kilit = kilit
        self.kayitlar = kayitlar
        self._vekil_fabrika = vekil_fabrikasi
        self._yerel_fabrika = yerel_fabrikasi
        self.vekiller: Dict[int, Any] = {}
        self.yereller: Dict[int, Any] = {}
        # v2.4.192 (Faz C): köprü beslemesi — tek HTTP, cihaz başına dağıtım
        self._kopru_cek = None
        self._kopru_kilit = threading.Lock()
        self._kopru_son = (None, "")
        self._kopru_ts = 0.0
        self.tazele()

    # ---------------- merkez kipi: köprü beslemesi (Faz C) ----------------
    @property
    def _cek(self):
        return self._kopru_cek

    @_cek.setter
    def _cek(self, f):
        self._kopru_cek = f
        for eid, v in self.vekiller.items():
            if hasattr(v, "_cek"):
                v._cek = self._cek_icin(eid)

    def _cek_icin(self, eid):
        def cek():
            return self._kopru_alt_paket(int(eid))
        return cek

    def _kopru_paket(self):
        simdi = time.time()
        with self._kopru_kilit:
            if simdi - self._kopru_ts < 0.4:
                return self._kopru_son
            f = self._kopru_cek
            if f is None:
                sonuc = (None, "M50 saha Köprüsü yapılandırılmadı")
            else:
                try:
                    sonuc = f()
                except Exception as e:
                    sonuc = (None, "%s: %s" % (type(e).__name__, e))
            self._kopru_son = sonuc
            self._kopru_ts = simdi
            return sonuc

    def _kopru_alt_paket(self, eid: int):
        paket, hata = self._kopru_paket()
        if hata or not isinstance(paket, dict):
            return None, hata or "M50 saha Köprüsü yanıt vermedi"
        cihazlar = paket.get("eo_cihazlar")
        if isinstance(cihazlar, dict):
            alt = cihazlar.get(str(eid))
            if isinstance(alt, dict):
                return alt, ""
            return None, ("Saha Köprüsü %d numaralı M50'yi bildirmiyor; "
                          "bu cihaza 'Bağlan' verin." % eid)
        if eid == self.birincil_id():
            return paket, ""          # eski köprü (<1.7.19): tek cihaz
        return None, ("Saha Köprüsü çoklu M50 desteklemiyor "
                      "(Köprü 1.7.19+ gerekir).")

    # ---------------- kayıt/istemci ----------------
    def tazele(self) -> None:
        kayitlar = {int(k["id"]): k for k in self.kayitlar.listele()}
        for eid in list(self.vekiller):
            if eid not in kayitlar and eid != 1:
                y = self.yereller.pop(eid, None)
                if y is not None:
                    try:
                        y.uygula("kes", {})
                    except Exception:
                        pass
                self.vekiller.pop(eid, None)
        for eid, k in kayitlar.items():
            if eid not in self.vekiller:
                self.vekiller[eid] = self._vekil_fabrika(k)
                self.yereller[eid] = self._yerel_fabrika(k)
                if self._kopru_cek is not None and hasattr(self.vekiller[eid], "_cek"):
                    self.vekiller[eid]._cek = self._cek_icin(eid)
            v = self.vekiller[eid]
            v.isim = k.get("isim") or ("M50 %d" % eid)
            v.eo_id = eid
            v.kayit_konum = (k.get("lat"), k.get("lon"))

    def _kimlik(self, eo_id) -> int:
        try:
            eid = int(eo_id) if eo_id not in (None, "") else 0
        except (TypeError, ValueError):
            eid = 0
        return eid if eid > 0 else self.birincil_id()

    def birincil_id(self) -> int:
        return min(self.vekiller) if self.vekiller else 1

    def vekil(self, eo_id=None):
        return self.vekiller.get(self._kimlik(eo_id))

    def yerel(self, eo_id=None):
        return self.yereller.get(self._kimlik(eo_id))

    # ---------------- geriye uyumlu yüz (birincil) ----------------
    @property
    def m50(self):
        return self.vekiller.get(self.birincil_id())

    @property
    def m50_yerel(self):
        return self.yereller.get(self.birincil_id())

    # video_proxy: 'm50:<eo>:<kanal>' çözümü
    def rtsp_url(self, kanal, eo_id=None):
        v = self.vekil(eo_id)
        return v.rtsp_url(kanal) if v is not None else None

    def m50_kamera_id_bul(self):
        return None

    # ---------------- telemetri ----------------
    def paketler(self) -> list:
        cikti = []
        kayitlar = {int(k["id"]): k for k in self.kayitlar.listele()}
        for eid in sorted(self.vekiller):
            v = self.vekiller[eid]
            k = kayitlar.get(eid, {})
            try:
                p = v.paket()
            except Exception:
                p = {}
            d = dict(p.get("m50_durum") or {})
            konum = d.get("konum") if isinstance(d.get("konum"), dict) else None
            if not konum and k.get("lat") is not None and k.get("lon") is not None:
                konum = {"lat": float(k["lat"]), "lon": float(k["lon"]),
                         "alt": None, "kaynak": "kayit"}
            p.update({"eo_id": eid, "isim": k.get("isim") or ("M50 %d" % eid),
                      "tur": k.get("tur") or "m50",
                      "kayit_ip": k.get("ip") or "", "kayit_port": k.get("port") or 39020,
                      "kayit_lat": k.get("lat"), "kayit_lon": k.get("lon"),
                      "konum": konum, "kopru_ornek_id": k.get("kopru_ornek_id"),
                      "otomatik_baglan": bool(k.get("otomatik_baglan")),
                      # v2.4.199: arayuz Elektro-Optik menusunu bu bayrakla
                      # acar. Onceden menu yalniz "bir Kopru'de m50 servisi
                      # calisiyor" bilgisine bagliydi; koprusuz (dogrudan
                      # SDK) kurulumda bayrak hic gelmiyor, menu gizli
                      # kaliyordu (kullanici bildirimi).
                      "yerel_sdk": bool(self.yereller.get(eid) is not None
                                        and self.yereller[eid].kullanilabilir())})
            cikti.append(p)
        return cikti
