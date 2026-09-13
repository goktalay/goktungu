# -*- coding: utf-8 -*-
"""PilotYoneticisi: pilot loglama, rol/izin sistemi ve merkezi uyarilar.

v2.1.7 ile eklendi.

- pilot_log : oturum acan pilotun yaptigi tum dron/radar/kamera/rota
  degisikliklerinin kalici kaydi (kim, ne zaman, ne yapti).
- roller    : rol adina bagli izin sozlugu {grup: {izin: bool}}.
  Yonetici rolu her zaman tam yetkilidir (DB'deki kaydi ne olursa
  olsun izin kontrolunde otomatik gecer).
- uyarilar  : merkezi uyari sistemi; izin reddi ve sistem uyarilari
  kullanici bazinda birikir, okunmamis sayaci arayuzde gosterilir.
"""
import json
import threading
import time

from .veritabani import baglanti, IZIN_SEMASI, tum_izinler


class PilotYoneticisi:

    def __init__(self, konsol=None):
        self.konsol = konsol or (lambda *a, **k: None)
        self._kilit = threading.Lock()
        # Rol izinleri onbellegi: {rol_adi: {grup: {izin: bool}}}
        self._rol_cache = None

    # ------------------------------------------------------------------
    # PILOT LOG
    # ------------------------------------------------------------------
    def log_yaz(self, eposta, isim, kategori, islem, detay=None):
        """Pilot islemini kalici olarak kaydeder."""
        try:
            with baglanti() as con:
                con.execute(
                    "INSERT INTO pilot_log "
                    "(ts, eposta, isim, kategori, islem, detay) "
                    "VALUES (?,?,?,?,?,?)",
                    (time.time(), (eposta or "").lower(), isim or "",
                     kategori or "", islem or "",
                     json.dumps(detay or {}, ensure_ascii=False)),
                )
        except Exception as e:
            self.konsol("PILOT", f"Log yazilamadi: {e}", "hata")

    def log_listesi(self, eposta=None, limit=300):
        """Pilot log kayitlarini (en yeni once) dondurur.

        eposta verilirse yalniz o pilotun kayitlari, verilmezse tumu.
        """
        limit = max(1, min(int(limit or 300), 1000))
        with baglanti() as con:
            if eposta:
                rows = con.execute(
                    "SELECT id, ts, eposta, isim, kategori, islem, detay "
                    "FROM pilot_log WHERE eposta = ? "
                    "ORDER BY ts DESC LIMIT ?",
                    ((eposta or "").lower(), limit)).fetchall()
            else:
                rows = con.execute(
                    "SELECT id, ts, eposta, isim, kategori, islem, detay "
                    "FROM pilot_log ORDER BY ts DESC LIMIT ?",
                    (limit,)).fetchall()
        sonuc = []
        for r in rows:
            k = dict(r)
            try:
                k["detay"] = json.loads(k.get("detay") or "{}")
            except (TypeError, ValueError):
                k["detay"] = {}
            sonuc.append(k)
        return sonuc

    # ------------------------------------------------------------------
    # ROLLER / IZINLER
    # ------------------------------------------------------------------
    @staticmethod
    def _metin(deger):
        """BLOB olarak saklanmis metni `str`e cevirir.

        ## v2.4.27 SAVUNMA KATMANI

        v2.4.25 onarimi tum metin kolonlarini BLOB'a cevirdi. v2.4.26
        gocu bunlari geri duzeltir, ancak `roller.ad` gibi UNIQUE
        kolonlarda ayni mantiksal anahtarin hem bayt hem metin kopyasi
        bulundugunda goc `UNIQUE constraint failed` aliyor ve bayt satiri
        oldugu gibi birakiyordu. Geride kalan bayt deger burada sozluk
        ANAHTARI olarak kullanildigi icin `rol_listesi` komutu her
        cagrildiginda cokuyordu:

            [WS] Komut hatasi (rol_listesi): keys must be str, int,
                 float, bool or None, not bytes

        Asil duzeltme `db_onarim._yinelenen_sil` icindedir: cakisan bayt
        satir silinir, guncel metin satir korunur. Buradaki donusum
        IKINCI KATMANDIR; goc calismazsa (salt okunur dosya, izin
        hatasi) rol yonetimi yine de acilir.
        """
        if isinstance(deger, bytes):
            try:
                return deger.decode("utf-8")
            except UnicodeDecodeError:
                return deger.decode("utf-8", errors="replace")
        if deger is None:
            return ""
        return deger if isinstance(deger, str) else str(deger)

    def _roller_yukle(self):
        with baglanti() as con:
            rows = con.execute("SELECT ad, izinler FROM roller").fetchall()
        roller = {}
        for r in rows:
            ad = self._metin(r["ad"]).strip().lower()
            if not ad:
                continue
            try:
                izin = json.loads(self._metin(r["izinler"]) or "{}")
            except (TypeError, ValueError):
                izin = {}
            # Ayni ad iki satirda bulunuyorsa (bayt + metin kalintisi)
            # bos olmayan kayit tercih edilir.
            if ad in roller and not isinstance(izin, dict):
                continue
            if not isinstance(izin, dict):
                izin = {}
            if ad in roller and not izin:
                continue
            roller[ad] = izin
        return roller

    def roller(self):
        """Tum roller + izinleri (onbellekli)."""
        with self._kilit:
            if self._rol_cache is None:
                self._rol_cache = self._roller_yukle()
            return {ad: json.loads(json.dumps(iz))
                    for ad, iz in self._rol_cache.items()}

    def rol_izinleri(self, rol_adi):
        """Bir rolun izin sozlugunu dondurur (yoksa tam izinli)."""
        r = self.roller().get((rol_adi or "").lower())
        if r is None:
            # Bilinmeyen rol: mevcut davranisi bozmamak icin tam izin
            return tum_izinler(True)
        # Semadaki eksik alanlari tamamla (yeni izinler eklendiginde
        # eski kayitlar acik varsayilir)
        tam = tum_izinler(True)
        for g, izinler in tam.items():
            for i in izinler:
                if g in r and i in r[g]:
                    tam[g][i] = bool(r[g][i])
        return tam

    def rol_kaydet(self, rol_adi, izinler):
        """Rol izinlerini gunceller/olusturur; sema disi alanlar atilir."""
        ad = (rol_adi or "").strip().lower()
        if not ad:
            return False
        temiz = {}
        for g, liste in IZIN_SEMASI.items():
            gi = (izinler or {}).get(g, {}) or {}
            temiz[g] = {i: bool(gi.get(i, True)) for i in liste}
        with self._kilit:
            with baglanti() as con:
                con.execute(
                    "INSERT INTO roller (ad, izinler) VALUES (?,?) "
                    "ON CONFLICT(ad) DO UPDATE SET izinler = excluded.izinler",
                    (ad, json.dumps(temiz)))
            self._rol_cache = None
        return True

    def rol_ekle(self, rol_adi):
        """Yeni rol olusturur (tum izinler acik baslar).

        Donus: (basarili, hata_kodu). Var olan rol icin 'rol_var'.
        """
        ad = (rol_adi or "").strip().lower()
        if not ad or len(ad) > 32:
            return False, "gecersiz_ad"
        if ad in self.roller():
            return False, "rol_var"
        with self._kilit:
            with baglanti() as con:
                con.execute(
                    "INSERT OR IGNORE INTO roller (ad, izinler) VALUES (?,?)",
                    (ad, json.dumps(tum_izinler(True))))
            self._rol_cache = None
        return True, ""

    def rol_sil(self, rol_adi):
        """Rol siler. Korumalar:

        - 'yonetici' ve 'kullanici' (varsayilan) rolleri silinemez.
        - Bir kullaniciya atanmis rol silinemez ('rol_kullanimda').
        Donus: (basarili, hata_kodu).
        """
        ad = (rol_adi or "").strip().lower()
        if ad in ("yonetici", "kullanici"):
            return False, "rol_korumali"
        if ad not in self.roller():
            return False, "rol_yok"
        with self._kilit:
            with baglanti() as con:
                sayi = con.execute(
                    "SELECT COUNT(*) FROM kullanicilar "
                    "WHERE LOWER(rol) = ?", (ad,)).fetchone()[0]
                if int(sayi) > 0:
                    return False, "rol_kullanimda"
                con.execute("DELETE FROM roller WHERE ad = ?", (ad,))
            self._rol_cache = None
        return True, ""

    def izin_var(self, rol_adi, grup, izin):
        """Rolun ilgili iznini kontrol eder. Yonetici daima True."""
        if (rol_adi or "").lower() == "yonetici":
            return True
        return bool(self.rol_izinleri(rol_adi).get(grup, {}).get(izin, True))

    # ------------------------------------------------------------------
    # UYARILAR
    # ------------------------------------------------------------------
    def uyari_ekle(self, eposta, kategori, mesaj):
        """Merkezi uyari kaydi olusturur; kayit sozlugunu dondurur."""
        ts = time.time()
        try:
            with baglanti() as con:
                cur = con.execute(
                    "INSERT INTO uyarilar (ts, eposta, kategori, mesaj, okundu) "
                    "VALUES (?,?,?,?,0)",
                    (ts, (eposta or "").lower(), kategori or "", mesaj or ""))
                uid = cur.lastrowid
        except Exception as e:
            self.konsol("UYARI", f"Uyari yazilamadi: {e}", "hata")
            return None
        return {"id": uid, "ts": ts, "eposta": (eposta or "").lower(),
                "kategori": kategori or "", "mesaj": mesaj or "",
                "okundu": 0}

    def uyari_listesi(self, eposta, limit=200):
        """Kullanicinin uyarilari (en yeni once) + okunmamis sayisi."""
        limit = max(1, min(int(limit or 200), 1000))
        ep = (eposta or "").lower()
        with baglanti() as con:
            rows = con.execute(
                "SELECT id, ts, kategori, mesaj, okundu FROM uyarilar "
                "WHERE eposta = ? ORDER BY ts DESC LIMIT ?",
                (ep, limit)).fetchall()
            okunmamis = con.execute(
                "SELECT COUNT(*) FROM uyarilar "
                "WHERE eposta = ? AND okundu = 0", (ep,)).fetchone()[0]
        return [dict(r) for r in rows], int(okunmamis)

    def uyari_okundu(self, eposta):
        """Kullanicinin tum uyarilarini okundu isaretler."""
        with baglanti() as con:
            con.execute(
                "UPDATE uyarilar SET okundu = 1 "
                "WHERE eposta = ? AND okundu = 0",
                ((eposta or "").lower(),))

    def okunmamis_sayi(self, eposta):
        with baglanti() as con:
            return int(con.execute(
                "SELECT COUNT(*) FROM uyarilar "
                "WHERE eposta = ? AND okundu = 0",
                ((eposta or "").lower(),)).fetchone()[0])
