#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.4.43 — TELEMETRI TEKILLEME GOCU SINAVI

Olculen:
  A. Mukerrer satirlar iceren ESKI bir veritabaninda goc calisiyor mu?
     (CREATE UNIQUE INDEX mukerrerler yuzunden basarisiz olmali; bu
      yuzden once temizlik yapilmali)
  B. Temizlikten sonra tekilleme indeksi kuruluyor mu?
  C. `telemetri_toplu_yaz` mukerreri sessizce atliyor ve GERCEK eklenen
     sayiyi donduruyor mu?
  D. Goc idempotent mi (ikinci acilista tekrar calismiyor)?
  E. Mesru veri KORUNUYOR mu (ayni ts farkli dron, farkli ts ayni dron)?
"""
import os
import shutil
import sqlite3
import sys
import tempfile

KOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "goktungu")
sys.path.insert(0, KOK)

GECEN = 0
KALAN = 0


def olc(ad, kosul, ayrinti=""):
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print("  [GECTI]  " + ad + ((" — " + ayrinti) if ayrinti else ""))
    else:
        KALAN += 1
        print("  [KALDI]  " + ad + ((" — " + ayrinti) if ayrinti else ""))


def main():
    global GECEN, KALAN
    print("=" * 68)
    print("v2.4.43 TELEMETRI TEKILLEME GOCU SINAVI")
    print("=" * 68)

    dizin = tempfile.mkdtemp(prefix="tk43_")
    db_yol = os.path.join(dizin, "gcs.db")
    try:
        # --- Onceki surumun urettigi durumu KUR ------------------------
        # `veritabani` modulu import edilmeden ham SQLite ile eski sema
        # kurulur ve mukerrer satirlar eklenir.
        import importlib
        os.environ["GOKTUNGU_VERI_DIZIN"] = dizin
        vt = importlib.import_module("goktungu.veritabani")
        vt.DOSYA = db_yol

        # Sema kur (goc DAHIL calisir; henuz mukerrer yok)
        vt.tablolari_olustur()
        olc("Temiz veritabaninda sema kuruldu", os.path.exists(db_yol))

        # Goc isaretini KALDIR ve tekilleme indeksini DUS: v2.4.42
        # durumunu birebir taklit ediyoruz.
        with sqlite3.connect(db_yol) as con:
            con.execute("DELETE FROM ayarlar WHERE anahtar='goc_v2443'")
            con.execute("DROP INDEX IF EXISTS ux_telemetri_dron_ts")
            # Dron kaydi (FK icin)
            con.execute(
                "INSERT INTO dronlar (uid, isim, ilk_kayit_ts,"
                " son_gorulme_ts) VALUES ('fp:test', 'Sinav', 0, 0)")
            dron_id = con.execute(
                "SELECT id FROM dronlar WHERE uid='fp:test'").fetchone()[0]

            # 17 ozgun ornek — kullanici logundaki sayi
            for i in range(17):
                con.execute(
                    "INSERT INTO telemetri (dron_id, ts, lat, lon, irtifa,"
                    " mod, armed) VALUES (?,?,?,?,?,?,?)",
                    (dron_id, 1000.0 + i * 0.1, 39.9, 32.8, 10.0 + i,
                     "GUIDED", 1))
            # AYNI 17 ornek 3 KEZ daha (sonsuz dongunun urettigi durum)
            for tur in range(3):
                for i in range(17):
                    con.execute(
                        "INSERT INTO telemetri (dron_id, ts, lat, lon,"
                        " irtifa, mod, armed) VALUES (?,?,?,?,?,?,?)",
                        (dron_id, 1000.0 + i * 0.1, 39.9, 32.8, 10.0 + i,
                         "GUIDED", 1))
            # MESRU veri: ayni ts, FARKLI dron
            con.execute(
                "INSERT INTO dronlar (uid, isim, ilk_kayit_ts,"
                " son_gorulme_ts) VALUES ('fp:test2', 'Sinav2', 0, 0)")
            dron2 = con.execute(
                "SELECT id FROM dronlar WHERE uid='fp:test2'").fetchone()[0]
            con.execute(
                "INSERT INTO telemetri (dron_id, ts, lat, lon, irtifa,"
                " mod, armed) VALUES (?,?,?,?,?,?,?)",
                (dron2, 1000.0, 40.0, 33.0, 5.0, "LOITER", 0))

        with sqlite3.connect(db_yol) as con:
            toplam = con.execute("SELECT COUNT(*) FROM telemetri").fetchone()[0]
        olc("Mukerrer durum kuruldu (v2.4.42 taklidi)",
            toplam == 17 * 4 + 1,
            "toplam satir=%d (beklenen 69)" % toplam)

        # Indeksin GERCEKTEN kurulamadigini kanitla
        try:
            with sqlite3.connect(db_yol) as con:
                con.execute("CREATE UNIQUE INDEX ux_test"
                            " ON telemetri (dron_id, ts)")
            indeks_hatasi = None
        except sqlite3.IntegrityError as e:
            indeks_hatasi = str(e)
        olc("Temizlik OLMADAN tekilleme kurulamiyor (kanit)",
            indeks_hatasi is not None,
            (indeks_hatasi or "HATA BEKLENIYORDU")[:52])

        # --- GOCU CALISTIR ---------------------------------------------
        vt._v2443_goc()

        with sqlite3.connect(db_yol) as con:
            kalan = con.execute("SELECT COUNT(*) FROM telemetri").fetchone()[0]
            idx = con.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
                " AND name='ux_telemetri_dron_ts'").fetchone()
            isaret = con.execute(
                "SELECT deger FROM ayarlar WHERE anahtar='goc_v2443'"
            ).fetchone()

        olc("Mukerrerler silindi, ozgun satirlar korundu",
            kalan == 18,
            "kalan=%d (beklenen 18: 17 ozgun + 1 mesru farkli dron)" % kalan)
        olc("Tekilleme indeksi kuruldu", idx is not None,
            idx[0] if idx else "INDEKS YOK")
        olc("Goc isareti birakildi",
            isaret is not None and str(isaret[0]) == "1")

        # MESRU verinin korundugunu dogrula
        with sqlite3.connect(db_yol) as con:
            mesru = con.execute(
                "SELECT COUNT(*) FROM telemetri WHERE ts=1000.0").fetchone()[0]
        olc("Ayni ts + FARKLI dron mesru kaydi korundu",
            mesru == 2, "ts=1000.0 satir sayisi=%d (beklenen 2)" % mesru)

        # --- OR IGNORE davranisi --------------------------------------
        with sqlite3.connect(db_yol) as con:
            dron_id = con.execute(
                "SELECT id FROM dronlar WHERE uid='fp:test'").fetchone()[0]

        alan_sira = vt.TELEMETRI_ALANLARI

        def satir_yap(d_id, ts, irtifa):
            d = {"dron_id": d_id, "ts": ts, "lat": 39.9, "lon": 32.8,
                 "irtifa": irtifa, "mod": "GUIDED", "armed": 1}
            return tuple(d.get(a) for a in alan_sira)

        # 3 mukerrer (ts 1000.0, 1000.1, 1000.2) + 2 YENI
        grup = [satir_yap(dron_id, 1000.0, 10.0),
                satir_yap(dron_id, 1000.1, 11.0),
                satir_yap(dron_id, 1000.2, 12.0),
                satir_yap(dron_id, 2000.0, 50.0),
                satir_yap(dron_id, 2000.1, 51.0)]
        eklenen = vt.telemetri_toplu_yaz(grup)
        olc("Mukerrer + yeni karisik grup HATA VERMEDI (OR IGNORE)",
            True, "cagri basarili")
        olc("Yalniz YENI satirlar eklendi ve dogru sayildi",
            eklenen == 2,
            "donen eklenen=%d (beklenen 2)" % eklenen)

        with sqlite3.connect(db_yol) as con:
            son = con.execute("SELECT COUNT(*) FROM telemetri").fetchone()[0]
        olc("Toplam satir dogru (mukerrer birikmedi)",
            son == 20, "toplam=%d (beklenen 20)" % son)

        # Ayni grubu TEKRAR yaz: hicbir sey eklenmemeli
        eklenen2 = vt.telemetri_toplu_yaz(grup)
        olc("Ayni grup ikinci kez yazildiginda 0 satir eklendi",
            eklenen2 == 0, "eklenen=%d" % eklenen2)

        # --- Idempotentlik --------------------------------------------
        vt._v2443_goc()
        with sqlite3.connect(db_yol) as con:
            son2 = con.execute("SELECT COUNT(*) FROM telemetri").fetchone()[0]
        olc("Goc ikinci calistirmada veriyi degistirmedi",
            son2 == son, "once=%d sonra=%d" % (son, son2))
    finally:
        try:
            vt.tum_baglantilari_kapat(True)
        except Exception:
            pass
        shutil.rmtree(dizin, ignore_errors=True)

    print("\n" + "=" * 68)
    print("SONUC: %d gecti, %d kaldi (toplam %d)"
          % (GECEN, KALAN, GECEN + KALAN))
    print("=" * 68)
    return 0 if KALAN == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
