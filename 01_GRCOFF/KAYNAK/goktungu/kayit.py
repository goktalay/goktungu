# -*- coding: utf-8 -*-
"""KayitYoneticisi: radar verisi kaydi ve tekrar oynatma (replay).

v2.3.0: JSONL dosyalari yerine SQLite (gcs.db):
  - radar_kayitlar : kayit metaverisi (ad, baslangic, kare, sure)
  - radar_kareler  : her kayit karesi (t, veri JSON)
Eski gcs_kayitlari/*.jsonl dosyalari ilk calistirmada otomatik
aktarilir ve klasor gcs_kayitlari.eski olarak yeniden adlandirilir.

Kayit: yayin dongusu her karede kare_yaz() cagirir; aktif kayit varsa
anlik radar durumu + islenmis izler + yetim izler DB'ye eklenir.
Replay: kayit zaman cizelgesine sadik kalinarak istemcilere canli
telemetriyle ayni formatta ('replay': True isaretli) yayinlanir.
"""
import asyncio
import json
import os
import threading
import time

from .sabitler import KAYIT_KLASORU
from . import veritabani


def _tablolar():
    with veritabani.baglanti() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS radar_kayitlar (
                ad          TEXT PRIMARY KEY,
                baslangic   REAL NOT NULL DEFAULT 0,
                bitis       REAL,
                kare        INTEGER NOT NULL DEFAULT 0,
                sure        REAL NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS radar_kareler (
                kayit_ad    TEXT NOT NULL,
                sira        INTEGER NOT NULL,
                t           REAL NOT NULL,
                veri        TEXT NOT NULL DEFAULT '{}',
                PRIMARY KEY (kayit_ad, sira)
            );
        """)


class KayitYoneticisi:

    def __init__(self, konsol, klasor=KAYIT_KLASORU):
        self.konsol = konsol
        self.klasor = klasor
        self._kilit = threading.Lock()
        veritabani.tablolari_olustur()
        _tablolar()
        self._jsonl_goc()
        self.kayit_durum = {
            "aktif": False,         # kayit suruyor mu
            "dosya": "",            # aktif kayit adi
            "baslangic": None,      # kayit baslama ani (epoch)
            "kare": 0,              # yazilan kare sayisi
        }
        self.replay_durum = {
            "aktif": False,         # replay suruyor mu
            "dosya": "",            # oynatilan kayit adi
            "hiz": 1.0,             # oynatma hizi carpani
            "ilerleme": 0,          # 0-100
            "sure": 0.0,            # kaydin toplam suresi (sn)
            "konum": 0.0,           # anlik oynatma konumu (sn)
        }
        self.replay_iptal = threading.Event()
        self.replay_gorev = None    # asyncio task

    # ------------------------------------------------------------------
    # Eski JSONL kayitlarinin tek seferlik SQLite gocu
    # ------------------------------------------------------------------
    def _jsonl_goc(self):
        if not os.path.isdir(self.klasor):
            return
        aktarilan = 0
        try:
            with veritabani.baglanti() as con:
                for ad in sorted(os.listdir(self.klasor)):
                    if not ad.endswith(".jsonl"):
                        continue
                    var = con.execute(
                        "SELECT 1 FROM radar_kayitlar WHERE ad=?",
                        (ad,)).fetchone()
                    if var:
                        continue
                    yol = os.path.join(self.klasor, ad)
                    sira = 0
                    ilk_t = son_t = None
                    try:
                        with open(yol, encoding="utf-8") as f:
                            for satir in f:
                                satir = satir.strip()
                                if not satir:
                                    continue
                                try:
                                    kare = json.loads(satir)
                                    t = float(kare.get("t") or 0)
                                except (ValueError, TypeError):
                                    continue
                                con.execute(
                                    "INSERT OR REPLACE INTO radar_kareler"
                                    " (kayit_ad, sira, t, veri)"
                                    " VALUES (?,?,?,?)",
                                    (ad, sira, t, satir))
                                if ilk_t is None:
                                    ilk_t = t
                                son_t = t
                                sira += 1
                    except OSError:
                        continue
                    if sira:
                        con.execute(
                            "INSERT OR REPLACE INTO radar_kayitlar"
                            " (ad, baslangic, bitis, kare, sure)"
                            " VALUES (?,?,?,?,?)",
                            (ad, ilk_t or 0, son_t, sira,
                             round((son_t - ilk_t), 1)
                             if (ilk_t and son_t) else 0))
                        aktarilan += 1
        except Exception as e:
            self.konsol("KAYIT", f"JSONL goc hatasi: {e}", "hata")
            return
        if aktarilan:
            self.konsol("KAYIT",
                        f"gcs_kayitlari -> gcs.db aktarildi "
                        f"({aktarilan} kayit).")
        try:
            os.replace(self.klasor, self.klasor + ".eski")
        except OSError:
            pass

    # ------------------------------------------------------------------
    # KAYIT
    # ------------------------------------------------------------------
    def kayit_baslat(self):
        """Yeni kayit acar; kayit adini dondurur."""
        with self._kilit:
            if self.kayit_durum["aktif"]:
                return self.kayit_durum["dosya"]
            ad = "radar_" + time.strftime("%Y%m%d_%H%M%S")
            simdi = time.time()
            try:
                with veritabani.baglanti() as con:
                    con.execute(
                        "INSERT OR REPLACE INTO radar_kayitlar"
                        " (ad, baslangic, kare, sure) VALUES (?,?,0,0)",
                        (ad, simdi))
            except Exception as e:
                self.konsol("KAYIT", f"Kayit acilamadi: {e}", "hata")
                return ""
            self.kayit_durum.update(aktif=True, dosya=ad,
                                    baslangic=simdi, kare=0)
            return ad

    def kayit_durdur(self):
        """Aktif kaydi kapatir."""
        with self._kilit:
            if not self.kayit_durum["aktif"]:
                return
            ad = self.kayit_durum["dosya"]
            try:
                with veritabani.baglanti() as con:
                    con.execute(
                        "UPDATE radar_kayitlar SET bitis=?, kare=?,"
                        " sure=COALESCE((SELECT MAX(t)-MIN(t) FROM"
                        " radar_kareler WHERE kayit_ad=?),0)"
                        " WHERE ad=?",
                        (time.time(), self.kayit_durum["kare"], ad, ad))
            except Exception:
                pass
            self.kayit_durum.update(aktif=False, dosya="",
                                    baslangic=None, kare=0)

    def kare_yaz(self, radar, radar_izler, yetimler):
        """Yayin dongusunden cagrilir; anlik radar verisini DB'ye ekler.
        Bos kareler (iz yok) de zaman cizelgesinin dogru oynatilmasi icin
        tutulur."""
        with self._kilit:
            if not self.kayit_durum["aktif"]:
                return
            try:
                t = time.time()
                veri = json.dumps({
                    "t": t,
                    "radar": radar,
                    "radar_izler": radar_izler,
                    "yetim_izler": yetimler,
                }, ensure_ascii=False)
                with veritabani.baglanti() as con:
                    con.execute(
                        "INSERT INTO radar_kareler"
                        " (kayit_ad, sira, t, veri) VALUES (?,?,?,?)",
                        (self.kayit_durum["dosya"],
                         self.kayit_durum["kare"], t, veri))
                self.kayit_durum["kare"] += 1
            except Exception as e:
                self.konsol("KAYIT", f"Yazma hatasi: {e}", "hata")

    def ozet(self):
        """Yayina eklenen hafif kayit durumu ozeti."""
        with self._kilit:
            return {
                "aktif": self.kayit_durum["aktif"],
                "dosya": self.kayit_durum["dosya"],
                "sure": round(time.time() - self.kayit_durum["baslangic"], 1)
                        if self.kayit_durum["baslangic"] else 0.0,
                "kare": self.kayit_durum["kare"],
            }

    def listesi(self):
        """Kayitli radar kayitlarini metaverileriyle dondurur."""
        sonuc = []
        try:
            with veritabani.baglanti() as con:
                for r in con.execute(
                        "SELECT k.ad, k.kare, k.sure,"
                        " (SELECT COALESCE(SUM(LENGTH(veri)),0)"
                        "  FROM radar_kareler WHERE kayit_ad=k.ad) AS boyut"
                        " FROM radar_kayitlar k ORDER BY k.ad DESC"):
                    sonuc.append({
                        "ad": r["ad"], "boyut": r["boyut"],
                        "kare": r["kare"], "sure": r["sure"],
                        "aktif": (self.kayit_durum["aktif"] and
                                  self.kayit_durum["dosya"] == r["ad"]),
                    })
        except Exception:
            pass
        return sonuc

    def sil(self, dosya_adi):
        """Kaydi siler (aktif kayit silinemez)."""
        ad = os.path.basename(str(dosya_adi or ""))
        # Geriye uyum: eski istemciler .jsonl uzantili ad gonderebilir
        if ad.endswith(".jsonl"):
            ad_alt = ad[:-6]
        else:
            ad_alt = ad
        if self.kayit_durum["aktif"] and \
                self.kayit_durum["dosya"] in (ad, ad_alt):
            return
        try:
            with veritabani.baglanti() as con:
                con.execute("DELETE FROM radar_kareler WHERE kayit_ad IN (?,?)",
                            (ad, ad_alt))
                cur = con.execute(
                    "DELETE FROM radar_kayitlar WHERE ad IN (?,?)",
                    (ad, ad_alt))
                if cur.rowcount:
                    self.konsol("KAYIT", f"Kayit silindi: {ad_alt}", "uyari")
        except Exception as e:
            self.konsol("KAYIT", f"Silme hatasi: {e}", "hata")

    # ------------------------------------------------------------------
    # REPLAY
    # ------------------------------------------------------------------
    def _kareleri_oku(self, ad):
        kareler = []
        try:
            with veritabani.baglanti() as con:
                for r in con.execute(
                        "SELECT veri FROM radar_kareler WHERE kayit_ad=?"
                        " ORDER BY sira", (ad,)):
                    try:
                        kareler.append(json.loads(r["veri"]))
                    except (ValueError, TypeError):
                        continue
        except Exception as e:
            self.konsol("REPLAY", f"Kayit okunamadi: {e}", "hata")
        return kareler

    async def replay_dongusu(self, dosya_adi, hiz, istemciler):
        """Kaydi zaman cizelgesine sadik kalarak istemcilere yayinlar.
        Yayin formati canli telemetriyle ayni; 'replay' alani True
        isaretlenir."""
        kareler = self._kareleri_oku(dosya_adi)
        if len(kareler) < 1:
            self.konsol("REPLAY", "Kayit bos.", "uyari")
            self.replay_durum.update(aktif=False)
            return
        t0 = kareler[0]["t"]
        toplam = kareler[-1]["t"] - t0
        self.replay_durum.update(aktif=True, dosya=dosya_adi, hiz=hiz,
                                 ilerleme=0, sure=round(toplam, 1), konum=0.0)
        self.konsol("REPLAY", f"Oynatma basladi: {dosya_adi} "
                    f"({len(kareler)} kare, {toplam:.0f} sn, {hiz}x)",
                    "basari")
        onceki_t = t0
        for kare in kareler:
            if self.replay_iptal.is_set():
                break
            bekle = (kare["t"] - onceki_t) / max(self.replay_durum["hiz"], 0.1)
            if bekle > 0:
                await asyncio.sleep(min(bekle, 5.0))
            onceki_t = kare["t"]
            konum = kare["t"] - t0
            self.replay_durum["konum"] = round(konum, 1)
            self.replay_durum["ilerleme"] = (int(konum * 100 / toplam)
                                             if toplam else 100)
            veri = json.dumps({
                "tip": "telemetri",
                "replay": True,
                "replay_durum": dict(self.replay_durum),
                "dronlar": [],
                "seri": {},
                "radar": kare.get("radar", {}),
                "radar_izler": kare.get("radar_izler", []),
                "yetim_izler": kare.get("yetim_izler", []),
            })
            await asyncio.gather(
                *(w.send(veri) for w in list(istemciler)),
                return_exceptions=True)
        bitti_mi = not self.replay_iptal.is_set()
        self.replay_durum.update(aktif=False,
                                 ilerleme=100 if bitti_mi else
                                 self.replay_durum["ilerleme"])
        self.konsol("REPLAY", "Oynatma " +
                    ("tamamlandi." if bitti_mi else "durduruldu."),
                    "basari" if bitti_mi else "uyari")
        # Bitis bildirimi (frontend canli moda doner)
        son = json.dumps({"tip": "replay_bitti"})
        await asyncio.gather(
            *(w.send(son) for w in list(istemciler)),
            return_exceptions=True)

    async def replay_baslat(self, dosya_adi, hiz, istemciler):
        """Var olan replay'i durdurup yeni replay gorevini baslatir."""
        ad = os.path.basename(str(dosya_adi or ""))
        if ad.endswith(".jsonl"):     # geriye uyum
            ad = ad[:-6]
        try:
            hiz = float(hiz)
        except (TypeError, ValueError):
            hiz = 1.0
        hiz = min(max(hiz, 0.25), 16.0)
        if self.replay_durum["aktif"]:
            self.replay_iptal.set()
            if self.replay_gorev:
                try:
                    await self.replay_gorev
                except Exception:
                    pass
        var = None
        try:
            with veritabani.baglanti() as con:
                var = con.execute(
                    "SELECT 1 FROM radar_kayitlar WHERE ad=?", (ad,)
                ).fetchone()
        except Exception:
            pass
        if var:
            self.replay_iptal.clear()
            self.replay_gorev = asyncio.ensure_future(
                self.replay_dongusu(ad, hiz, istemciler))
        else:
            self.konsol("REPLAY", f"Kayit bulunamadi: {ad}", "hata")

    def replay_durdur(self):
        if self.replay_durum["aktif"]:
            self.replay_iptal.set()

    def replay_hiz(self, hiz):
        try:
            self.replay_durum["hiz"] = min(max(float(hiz), 0.25), 16.0)
        except (TypeError, ValueError):
            pass
