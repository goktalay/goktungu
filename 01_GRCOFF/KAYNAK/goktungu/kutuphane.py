# -*- coding: utf-8 -*-
"""AI Kutuphanesi: Kisiler (yuz kayitlari) ve Araclar (plaka) (v2.4.0).

Seviyeler: GUVENLI / GUVENSIZ / ARANILAN (UI: yesil/turuncu/kirmizi).
Yuz kayitlari: fotograf dosyasi ai_yuzler/ klasorune yazilir,
SFace embeddingi (base64 float32) kisi_yuzler.embedding'e saklanir.
"""
import base64
import os
import time

from . import veritabani
from .sabitler import PROJE_KOKU, _veri_yolu

SEVIYELER = ("GUVENLI", "GUVENSIZ", "ARANILAN")
YUZ_KLASORU = _veri_yolu("ai_yuzler")


def _yuz_dosya_yolu(gorel):
    """Veritabaninda kayitli goreli yuz yolunu diskteki yola cevirir.

    v2.4.52: klasor yapisi degisti. Veritabaninda yol
    `ai_yuzler/kisiN_....jpg` bicimindedir ve BU BICIM DEGISTIRILEMEZ:
    ayni deger arayuze de gonderilir ve mevcut kayitlarda yazilidir.
    Degistirmek eski kayitlarin fotograflarini erisilemez yapardi.

    Bu yuzden cozumleme calisma aninda yapilir ve iki konum da
    denenir (yeni `veri/ai_yuzler`, eski `<kok>/ai_yuzler`). Dosya
    silme islemi yanlis konuma bakarsa sessizce hicbir sey silmez:
    kayit veritabanindan gider, dosya diskte SONSUZA KADAR kalir.
    """
    if not gorel:
        return None
    ad = os.path.basename(str(gorel).replace("\\", "/"))
    if not ad or ad in (".", ".."):
        return None
    yeni = os.path.join(YUZ_KLASORU, ad)
    if os.path.isfile(yeni):
        return yeni
    eski = os.path.join(PROJE_KOKU, str(gorel).replace("\\", "/"))
    if os.path.isfile(eski):
        return eski
    return yeni


def _seviye(deger):
    deger = (deger or "").strip().upper()
    return deger if deger in SEVIYELER else "GUVENLI"


class KisiYoneticisi:
    """Kisi CRUD + yuz kayitlari."""

    def listele(self):
        with veritabani.baglanti() as con:
            kisiler = [dict(r) for r in con.execute(
                "SELECT * FROM kisiler ORDER BY ad").fetchall()]
            yuzler = con.execute(
                "SELECT id, kisi_id, dosya FROM kisi_yuzler"
                " ORDER BY id").fetchall()
        yuz_haritasi = {}
        for y in yuzler:
            yuz_haritasi.setdefault(y["kisi_id"], []).append(
                {"id": y["id"], "dosya": y["dosya"]})
        for k in kisiler:
            k["yuzler"] = yuz_haritasi.get(k["id"], [])
        return kisiler

    def kaydet(self, kisi_id, ad, seviye, notlar=""):
        ad = (ad or "").strip()[:80]
        if not ad:
            return None
        with veritabani.baglanti() as con:
            if kisi_id:
                con.execute(
                    "UPDATE kisiler SET ad=?, seviye=?, notlar=?"
                    " WHERE id=?",
                    (ad, _seviye(seviye), (notlar or "")[:400],
                     int(kisi_id)))
            else:
                con.execute(
                    "INSERT INTO kisiler (ad, seviye, notlar, olusturma)"
                    " VALUES (?,?,?,?)",
                    (ad, _seviye(seviye), (notlar or "")[:400],
                     time.time()))
        return self.listele()

    def sil(self, kisi_id):
        kisi_id = int(kisi_id)
        # yuz fotograflarini diskten temizle
        with veritabani.baglanti() as con:
            dosyalar = [r["dosya"] for r in con.execute(
                "SELECT dosya FROM kisi_yuzler WHERE kisi_id=?",
                (kisi_id,)).fetchall()]
            con.execute("DELETE FROM kisi_yuzler WHERE kisi_id=?",
                        (kisi_id,))
            con.execute("DELETE FROM kisiler WHERE id=?", (kisi_id,))
        for d in dosyalar:
            yol = _yuz_dosya_yolu(d)
            if d and yol and os.path.isfile(yol):
                try:
                    os.remove(yol)
                except OSError:
                    pass
        return self.listele()

    # ------------------------------------------------------------------
    def yuz_ekle(self, kisi_id, foto_b64, embedding_b64):
        """Fotografi diske yazar, embeddingi DB'ye kaydeder."""
        kisi_id = int(kisi_id)
        try:
            ham = base64.b64decode(foto_b64.split(",")[-1])
        except Exception:
            return None
        if not ham or len(ham) > 8 * 1024 * 1024:
            return None
        os.makedirs(YUZ_KLASORU, exist_ok=True)
        dosya = f"kisi{kisi_id}_{int(time.time() * 1000)}.jpg"
        with open(os.path.join(YUZ_KLASORU, dosya), "wb") as f:
            f.write(ham)
        gorel = "ai_yuzler/" + dosya
        with veritabani.baglanti() as con:
            con.execute(
                "INSERT INTO kisi_yuzler (kisi_id, dosya, embedding,"
                " olusturma) VALUES (?,?,?,?)",
                (kisi_id, gorel, embedding_b64 or "", time.time()))
        return self.listele()

    def yuz_sil(self, yuz_id):
        yuz_id = int(yuz_id)
        with veritabani.baglanti() as con:
            r = con.execute("SELECT dosya FROM kisi_yuzler WHERE id=?",
                            (yuz_id,)).fetchone()
            con.execute("DELETE FROM kisi_yuzler WHERE id=?", (yuz_id,))
        if r and r["dosya"]:
            yol = _yuz_dosya_yolu(r["dosya"])
            if yol and os.path.isfile(yol):
                try:
                    os.remove(yol)
                except OSError:
                    pass
        return self.listele()


class AracYoneticisi:
    """Arac CRUD (plaka/marka/model/renk/seviye)."""

    def listele(self):
        with veritabani.baglanti() as con:
            return [dict(r) for r in con.execute(
                "SELECT * FROM araclar ORDER BY plaka").fetchall()]

    def kaydet(self, arac_id, plaka, marka="", model="", renk="",
               seviye="GUVENLI", notlar=""):
        plaka = "".join(c for c in (plaka or "").upper()
                        if c.isalnum() or c == " ").strip()[:20]
        if not plaka:
            return None
        degerler = (plaka, (marka or "").strip()[:40],
                    (model or "").strip()[:40],
                    (renk or "").strip()[:30], _seviye(seviye),
                    (notlar or "")[:400])
        with veritabani.baglanti() as con:
            if arac_id:
                con.execute(
                    "UPDATE araclar SET plaka=?, marka=?, model=?,"
                    " renk=?, seviye=?, notlar=? WHERE id=?",
                    degerler + (int(arac_id),))
            else:
                con.execute(
                    "INSERT INTO araclar (plaka, marka, model, renk,"
                    " seviye, notlar, olusturma) VALUES (?,?,?,?,?,?,?)",
                    degerler + (time.time(),))
        return self.listele()

    def sil(self, arac_id):
        with veritabani.baglanti() as con:
            con.execute("DELETE FROM araclar WHERE id=?", (int(arac_id),))
        return self.listele()
