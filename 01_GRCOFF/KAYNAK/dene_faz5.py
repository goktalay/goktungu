#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.4.51 Faz 5 olcumu: gorev durumu + karo deposu + tampon defteri.

Gercek PostgreSQL uzerinde KOD YOLLARINI calistirir; statik denetim
degil DAVRANIS olcumudur.
"""
import json
import os
import shutil
import sys
import tempfile
import time

KOK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(KOK, "goktungu"))

PG = dict(host="127.0.0.1", port=5432, veritabani="goktungu",
          kullanici="goktungu", sifre="goktungu2451")

T = [0, 0]


def ol(ad, kosul, ayrinti=""):
    if kosul:
        T[0] += 1
        print(f"  [TAMAM] {ad}")
    else:
        T[1] += 1
        print(f"  [KALDI] {ad}" + (f" -> {ayrinti}" if ayrinti else ""))


def bolum(s):
    print(f"\n{'=' * 62}\n{s}\n{'=' * 62}")


def main():
    from goktungu import pg
    from goktungu import veritabani as vt

    pg.yapilandir(**PG)
    vt.kip_ayarla("postgresql")
    vt.tablolari_olustur()

    # ============================================================
    bolum("1) GOREV DURUMU — PostgreSQL'e tasindi mi")
    # ============================================================
    with vt.baglanti() as con:
        con.execute("DELETE FROM gorev_durum")

    import types

    class SahteGorev:
        """gorev.py'nin kalici depo yollarini izole calistirir."""
        _diske_yaz = None      # asagida baglanacak
        _diskten_yukle = None

    from goktungu import gorev as gmod

    g = object.__new__(gmod.GorevYoneticisi)
    g.surdurulebilir = {}
    g._durum_yaz_kilidi = __import__("threading").Lock()
    g._son_yazim = 0.0
    g.konsol = lambda *a, **k: None

    # Yazma
    g.surdurulebilir = {7: {"dron_uid": "D7", "seq": 12, "toplam": 40},
                        9: {"dron_uid": "D9", "seq": 3, "toplam": 10}}
    g._diske_yaz(zorla=True)
    with vt.baglanti() as con:
        n = con.execute("SELECT COUNT(*) FROM gorev_durum").fetchone()[0]
    ol("gorev durumu PG'ye yazildi (2 kayit)", n == 2, f"n={n}")

    # Okuma
    g2 = object.__new__(gmod.GorevYoneticisi)
    g2.surdurulebilir = {}
    g2._durum_yaz_kilidi = __import__("threading").Lock()
    g2._son_yazim = 0.0
    g2.konsol = lambda *a, **k: None
    g2._diskten_yukle()
    ol("gorev durumu PG'den okundu",
       set(g2.surdurulebilir.keys()) == {7, 9},
       f"anahtarlar={list(g2.surdurulebilir.keys())}")
    ol("gorev durumu icerigi korundu",
       (g2.surdurulebilir.get(7) or {}).get("seq") == 12,
       f"seq={(g2.surdurulebilir.get(7) or {}).get('seq')}")

    # KRITIK: tamamlanan gorev PG'den SILINMELI
    g.surdurulebilir = {7: {"dron_uid": "D7", "seq": 40, "toplam": 40}}
    g._diske_yaz(zorla=True)
    with vt.baglanti() as con:
        kalan = [r[0] for r in con.execute(
            "SELECT sysid FROM gorev_durum").fetchall()]
    ol("tamamlanan gorev PG'den silindi (sysid 9 gitti)",
       kalan == [7], f"kalan={kalan}")

    # ============================================================
    bolum("2) HARITA KAROSU — iki katmanli depo")
    # ============================================================
    from goktungu import tile_cache as tc

    with vt.baglanti() as con:
        con.execute("DELETE FROM harita_karo")

    ol("PG karo yolu hazir", tc._pg_hazir(), "pg_hazir False")

    ornek = bytes(range(256)) * 40          # 10240 bayt ikili
    tc._pg_karo_yaz("osm", 12, 100, 200, ornek)
    geri = tc._pg_karo_oku("osm", 12, 100, 200)
    ol("karo PG'ye yazildi ve geri okundu", geri is not None)
    ol("karo ikili icerigi bayt-bire-bir dogru", geri == ornek,
       f"uzunluk={len(geri) if geri else 0} beklenen={len(ornek)}")

    yok = tc._pg_karo_oku("osm", 12, 999, 999)
    ol("olmayan karo None donuyor", yok is None)

    # KRITIK: PG yolu kapaliyken harita kararmamali
    tc._pg_karo_kapali = True
    ol("PG kapaliyken _pg_hazir False", not tc._pg_hazir())
    ol("PG kapaliyken okuma None (harita disk/internete duser)",
       tc._pg_karo_oku("osm", 12, 100, 200) is None)
    tc._pg_karo_kapali = False

    # ============================================================
    bolum("3) TELEMETRI TAMPON DEFTERI")
    # ============================================================
    from goktungu import telemetri_tampon as tt

    with vt.baglanti() as con:
        con.execute("DELETE FROM telemetri_tampon_kayit")

    gecici = tempfile.mkdtemp(prefix="tt51_")
    try:
        tmp = tt.TelemetriTampon(dizin=gecici, konsol=lambda *a, **k: None)
        tmp._defter_yaz("tel_20260811_1200.jsonl", 60, "aktarildi", 0, "",
                        time.time())
        with vt.baglanti() as con:
            s = con.execute(
                "SELECT satir, durum FROM telemetri_tampon_kayit"
                " WHERE dosya=?",
                ("tel_20260811_1200.jsonl",)).fetchone()
        ol("tampon defteri PG'ye yazildi", s is not None)
        ol("defter satir sayisi dogru", s and s[0] == 60,
           f"satir={s[0] if s else None}")
        ol("defter durumu dogru", s and s[1] == "aktarildi")

        # Ayni dosya yeniden aktarilirsa UZERINE yazilmali (mukerrer yok)
        tmp._defter_yaz("tel_20260811_1200.jsonl", 61, "aktarildi", 1, "",
                        time.time())
        with vt.baglanti() as con:
            n = con.execute(
                "SELECT COUNT(*) FROM telemetri_tampon_kayit"
                " WHERE dosya=?",
                ("tel_20260811_1200.jsonl",)).fetchone()[0]
            s2 = con.execute(
                "SELECT satir FROM telemetri_tampon_kayit WHERE dosya=?",
                ("tel_20260811_1200.jsonl",)).fetchone()
        ol("defter mukerrer kayit acmiyor", n == 1, f"n={n}")
        ol("defter uzerine yaziyor", s2 and s2[0] == 61,
           f"satir={s2[0] if s2 else None}")

        # KRITIK: defter yazilamasa bile aktarim SURMELI
        tmp._defter_kapali = True
        try:
            tmp._defter_yaz("x.jsonl", 1, "aktarildi", 0, "", time.time())
            ol("defter kapaliyken hata firlatmiyor", True)
        except Exception as e:
            ol("defter kapaliyken hata firlatmiyor", False, str(e))
    finally:
        shutil.rmtree(gecici, ignore_errors=True)

    # ============================================================
    bolum("SONUC")
    # ============================================================
    print(f"  TAMAM: {T[0]}   KALDI: {T[1]}")
    return 0 if T[1] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
