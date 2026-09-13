"""MesajYoneticisi: sirket ici pilotlar arasi canli mesajlasma.

v2.4.32 ile eklendi.

Tasarim notlari
---------------
- `uyarilar` tablosu tek yonludur (yalnizca alici tasir), sohbet icin
  kullanilamaz. Bu nedenle ayri `mesajlar` tablosu kullanilir.
- Sohbet, normalize edilmis bir anahtar yerine iki yonlu sorguyla
  cozulur: (gonderen=A AND alici=B) OR (gonderen=B AND alici=A).
  Boylece gonderen yonu kaybolmaz ve ek kolon/goc gerekmez.
- Okundu isareti YALNIZCA alicinin kendi kayitlarina uygulanir;
  bir kullanici karsi tarafin okundu durumunu degistiremez.
- Metin uzunlugu sunucu tarafinda kirpilir (istemciye guvenilmez).
"""
import time

from .veritabani import baglanti

# Tek mesaj icin ust sinir. Telemetri agirlikli bir sistemde
# mesajlasma kanalinin buyuk yuk tasimasi istenmez.
MAX_UZUNLUK = 4000


class MesajYoneticisi:

    def __init__(self, konsol=None):
        self.konsol = konsol or (lambda *a, **k: None)

    # ------------------------------------------------------------------
    # YARDIMCILAR
    # ------------------------------------------------------------------
    @staticmethod
    def _ep(deger):
        return str(deger or "").strip().lower()

    @staticmethod
    def _satir(r):
        return {
            "id": int(r["id"]),
            "ts": float(r["ts"]),
            "gonderen": r["gonderen"] or "",
            "alici": r["alici"] or "",
            "metin": r["metin"] or "",
            "okundu": bool(r["okundu"]),
        }

    # ------------------------------------------------------------------
    # GONDER
    # ------------------------------------------------------------------
    def gonder(self, gonderen, alici, metin):
        """Mesaji kaydeder; (mesaj_dict, hata) dondurur."""
        g = self._ep(gonderen)
        a = self._ep(alici)
        m = str(metin or "").strip()
        if not g:
            return None, "Oturum bulunamadi."
        if not a:
            return None, "Alici belirtilmedi."
        if g == a:
            return None, "Kendinize mesaj gonderemezsiniz."
        if not m:
            return None, "Mesaj bos olamaz."
        if len(m) > MAX_UZUNLUK:
            m = m[:MAX_UZUNLUK]

        ts = time.time()
        try:
            with baglanti() as con:
                # Alici gercekten kayitli bir kullanici mi? Aksi halde
                # veritabaninda erisilemez mesaj birikir.
                var = con.execute(
                    "SELECT 1 FROM kullanicilar WHERE eposta = ?",
                    (a,)).fetchone()
                if not var:
                    return None, "Alici bulunamadi."
                imlec = con.execute(
                    "INSERT INTO mesajlar (ts, gonderen, alici, metin, okundu) "
                    "VALUES (?,?,?,?,0)", (ts, g, a, m))
                yeni_id = int(imlec.lastrowid or 0)
        except Exception as e:
            self.konsol("MESAJ", f"Mesaj yazilamadi: {e}", "hata")
            return None, "Mesaj kaydedilemedi."

        return {"id": yeni_id, "ts": ts, "gonderen": g, "alici": a,
                "metin": m, "okundu": False}, ""

    # ------------------------------------------------------------------
    # SOHBET GECMISI
    # ------------------------------------------------------------------
    def gecmis(self, kullanici, karsi, limit=200):
        """Iki kullanici arasindaki mesajlar (eskiden yeniye)."""
        k = self._ep(kullanici)
        c = self._ep(karsi)
        limit = max(1, min(int(limit or 200), 1000))
        if not k or not c:
            return []
        try:
            with baglanti() as con:
                # En YENI `limit` kayit alinir, sonra eskiden yeniye
                # cevrilir. Ters siralamadan sonra Python tarafinda
                # cevirmek, uzun sohbetlerde dogru pencereyi verir.
                rows = con.execute(
                    "SELECT id, ts, gonderen, alici, metin, okundu "
                    "FROM mesajlar "
                    "WHERE (gonderen = ? AND alici = ?) "
                    "   OR (gonderen = ? AND alici = ?) "
                    "ORDER BY ts DESC, id DESC LIMIT ?",
                    (k, c, c, k, limit)).fetchall()
        except Exception as e:
            self.konsol("MESAJ", f"Gecmis okunamadi: {e}", "hata")
            return []
        return [self._satir(r) for r in reversed(rows)]

    # ------------------------------------------------------------------
    # OKUNMAMISLAR
    # ------------------------------------------------------------------
    def okunmamis_sayi(self, kullanici):
        k = self._ep(kullanici)
        if not k:
            return 0
        try:
            with baglanti() as con:
                n = con.execute(
                    "SELECT COUNT(*) FROM mesajlar "
                    "WHERE alici = ? AND okundu = 0", (k,)).fetchone()[0]
            return int(n or 0)
        except Exception:
            return 0

    def okunmamis_ozet(self, kullanici, limit=50):
        """Okunmamis mesajlari gonderene gore gruplar.

        Header ikonunun altindaki kucuk panel bunu kullanir: her
        gonderen icin son mesaj ve sayac.
        """
        k = self._ep(kullanici)
        if not k:
            return [], 0
        limit = max(1, min(int(limit or 50), 200))
        try:
            with baglanti() as con:
                rows = con.execute(
                    "SELECT m.gonderen, "
                    "       COUNT(*) AS sayi, "
                    "       MAX(m.ts) AS son_ts "
                    "FROM mesajlar m "
                    "WHERE m.alici = ? AND m.okundu = 0 "
                    "GROUP BY m.gonderen "
                    "ORDER BY son_ts DESC LIMIT ?", (k, limit)).fetchall()
                liste = []
                for r in rows:
                    g = r["gonderen"] or ""
                    # Gonderenin adi ve o gonderenden gelen SON okunmamis
                    # mesajin metni. Ayri sorgu, cunku GROUP BY ile
                    # birlikte metin secmek SQLite'ta belirsizdir.
                    son = con.execute(
                        "SELECT id, metin, ts FROM mesajlar "
                        "WHERE alici = ? AND gonderen = ? AND okundu = 0 "
                        "ORDER BY ts DESC, id DESC LIMIT 1",
                        (k, g)).fetchone()
                    kul = con.execute(
                        "SELECT ad_soyad, unvan FROM kullanicilar "
                        "WHERE eposta = ?", (g,)).fetchone()
                    liste.append({
                        "gonderen": g,
                        "ad_soyad": (kul["ad_soyad"] if kul else "") or g,
                        "unvan": (kul["unvan"] if kul else "") or "",
                        "sayi": int(r["sayi"] or 0),
                        "ts": float(r["son_ts"] or 0),
                        "metin": (son["metin"] if son else "") or "",
                        "mesaj_id": int(son["id"]) if son else 0,
                    })
        except Exception as e:
            self.konsol("MESAJ", f"Okunmamis ozet alinamadi: {e}", "hata")
            return [], 0
        return liste, sum(x["sayi"] for x in liste)

    def sohbet_okunmamislari(self, kullanici):
        """{karsi_eposta: okunmamis_sayi} — pilot listesi rozetleri."""
        k = self._ep(kullanici)
        if not k:
            return {}
        try:
            with baglanti() as con:
                rows = con.execute(
                    "SELECT gonderen, COUNT(*) AS sayi FROM mesajlar "
                    "WHERE alici = ? AND okundu = 0 "
                    "GROUP BY gonderen", (k,)).fetchall()
            return {(r["gonderen"] or ""): int(r["sayi"] or 0) for r in rows}
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # OKUNDU ISARETLEME
    # ------------------------------------------------------------------
    def okundu_isaretle(self, kullanici, karsi=None):
        """Alicinin okunmamislarini okundu yapar.

        `karsi` verilirse yalniz o kisiden gelenler, verilmezse tumu.
        Yalnizca `alici = kullanici` olan satirlar guncellenir; boylece
        bir kullanici karsi tarafin okundu durumunu degistiremez.
        """
        k = self._ep(kullanici)
        if not k:
            return 0
        c = self._ep(karsi)
        ts = time.time()
        try:
            with baglanti() as con:
                if c:
                    imlec = con.execute(
                        "UPDATE mesajlar SET okundu = 1, okundu_ts = ? "
                        "WHERE alici = ? AND gonderen = ? AND okundu = 0",
                        (ts, k, c))
                else:
                    imlec = con.execute(
                        "UPDATE mesajlar SET okundu = 1, okundu_ts = ? "
                        "WHERE alici = ? AND okundu = 0", (ts, k))
                return int(imlec.rowcount or 0)
        except Exception as e:
            self.konsol("MESAJ", f"Okundu isaretlenemedi: {e}", "hata")
            return 0

    # ------------------------------------------------------------------
    # BAKIM
    # ------------------------------------------------------------------
    def eski_temizle(self, gun=90):
        """Belirtilen gunden eski OKUNMUS mesajlari siler."""
        try:
            esik = time.time() - max(1, int(gun)) * 86400.0
            with baglanti() as con:
                imlec = con.execute(
                    "DELETE FROM mesajlar WHERE okundu = 1 AND ts < ?",
                    (esik,))
                return int(imlec.rowcount or 0)
        except Exception:
            return 0
