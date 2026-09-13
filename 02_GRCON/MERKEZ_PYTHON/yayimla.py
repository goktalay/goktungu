#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""GÖKTUNGU MERKEZ — paket yayimlama araci.

Kullanim (merkez sunucuda):

    python3.11 yayimla.py --urun gcs --surum 2.4.52 \
        --dosya /root/goktungu-guncelleme-2.4.52.tar.gz \
        --paket-tur guncelleme --platform ortak --kanal kararli \
        --asgari-surum 2.4.24 --notlar "Panel resize + PG havuz duzeltmesi"

    python3.11 yayimla.py --liste
    python3.11 yayimla.py --anahtar          # acik anahtari yazdirir
    python3.11 yayimla.py --dogrula 3        # surum_id imzasini dogrular
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mk_ayar  # noqa: E402
import mk_db  # noqa: E402
import mk_depo as depo  # noqa: E402


def _boyut(b: int) -> str:
    x = float(b or 0)
    for birim in ("B", "KB", "MB", "GB"):
        if x < 1024 or birim == "GB":
            return f"{x:.1f} {birim}"
        x /= 1024
    return f"{x:.1f} GB"


def liste_yaz(urun: str | None = None) -> None:
    kayitlar = depo.liste(urun)
    if not kayitlar:
        print("Depo bos.")
        return
    print(f"{'ID':>4}  {'URUN':<8} {'SURUM':<10} {'PLATFORM':<12} "
          f"{'KANAL':<9} {'TUR':<11} {'BOYUT':>10}  {'ETKIN':<6} DOSYA")
    print("-" * 110)
    for k in kayitlar:
        isaret = "evet" if k["etkin"] else "HAYIR"
        eksik = "" if k["dosya_var"] else "  [DOSYA YOK]"
        print(f"{k['surum_id']:>4}  {k['urun']:<8} {k['surum']:<10} "
              f"{k['platform']:<12} {k['kanal']:<9} {k['paket_tur']:<11} "
              f"{_boyut(k['dosya_boyut']):>10}  {isaret:<6} "
              f"{k['dosya_ad']}{eksik}")


def dogrula(surum_id: int) -> int:
    k = mk_db.tek(
        "SELECT urun, surum, platform, paket_tur, sha256, dosya_boyut, imza, "
        "       dosya_ad FROM surumler WHERE surum_id=%s", (surum_id,))
    if not k:
        print(f"[HATA] surum_id={surum_id} bulunamadi")
        return 1
    yol = depo.paket_yolu(k["urun"], k["surum"], k["dosya_ad"])
    if not os.path.isfile(yol):
        print(f"[HATA] paket dosyasi yok: {yol}")
        return 1
    ozet, boyut = depo.dosya_ozeti(yol)
    if ozet != k["sha256"]:
        print(f"[HATA] SHA-256 uyusmuyor\n  kayit: {k['sha256']}\n  dosya: {ozet}")
        return 1
    if boyut != k["dosya_boyut"]:
        print(f"[HATA] boyut uyusmuyor: kayit={k['dosya_boyut']} dosya={boyut}")
        return 1
    if not k["imza"]:
        print("[HATA] imza yok")
        return 1
    tamam = depo.imza_dogrula(k["urun"], k["surum"], k["platform"],
                              k["paket_tur"], k["sha256"], k["dosya_boyut"],
                              k["imza"])
    print(("[TAMAM] " if tamam else "[HATA] ") +
          f"imza {'gecerli' if tamam else 'GECERSIZ'} — "
          f"{k['urun']} {k['surum']} ({k['platform']}/{k['paket_tur']})")
    return 0 if tamam else 1


def main() -> int:
    a = argparse.ArgumentParser(description="GÖKTUNGU MERKEZ paket yayimlama")
    a.add_argument("--urun")
    a.add_argument("--surum")
    a.add_argument("--dosya")
    a.add_argument("--platform", default="ortak")
    a.add_argument("--kanal", default="kararli")
    a.add_argument("--paket-tur", default="guncelleme",
                   choices=list(depo.PAKET_TURLERI))
    a.add_argument("--asgari-surum")
    a.add_argument("--notlar")
    a.add_argument("--liste", action="store_true")
    a.add_argument("--anahtar", action="store_true")
    a.add_argument("--anahtar-uret", action="store_true")
    a.add_argument("--dogrula", type=int)
    a.add_argument("--devre-disi", type=int)
    a.add_argument("--etkinlestir", type=int)
    n = a.parse_args()

    mk_ayar.ayar_oku()

    if n.anahtar_uret:
        s = depo.anahtar_uret()
        print(("Yeni anahtar uretildi." if s["olustu"] else
               "Anahtar zaten var (ezilmedi)."))
        print(f"  gizli: {s['gizli']}")
        print(f"  acik : {s['acik']}")
        print(f"  acik anahtar (base64, istemciye gomulecek):\n  {s['acik_b64']}")
        return 0

    if n.anahtar:
        ab = depo.acik_anahtar_b64()
        if not ab:
            print("[HATA] acik anahtar okunamadi; --anahtar-uret ile uretin")
            return 1
        print(ab)
        return 0

    if n.liste:
        liste_yaz(n.urun)
        return 0

    if n.dogrula:
        return dogrula(n.dogrula)

    if n.devre_disi:
        ok = depo.paket_devre_disi(n.devre_disi)
        print("devre disi birakildi" if ok else "[HATA] bulunamadi")
        return 0 if ok else 1

    if n.etkinlestir:
        ok = depo.paket_etkinlestir(n.etkinlestir)
        print("etkinlestirildi" if ok else "[HATA] bulunamadi")
        return 0 if ok else 1

    if not (n.urun and n.surum and n.dosya):
        a.print_help()
        return 2

    try:
        k = depo.paket_ekle(n.urun, n.surum, n.dosya,
                            platform=n.platform, kanal=n.kanal,
                            paket_tur=n.paket_tur,
                            asgari_surum=n.asgari_surum, notlar=n.notlar)
    except Exception as e:
        print(f"[HATA] {e}")
        return 1

    print(f"[TAMAM] yayimlandi: {k['urun']} {k['surum']} "
          f"({k['platform']}/{k['paket_tur']}/{k['kanal']})")
    print(f"  surum_id : {k['surum_id']}")
    print(f"  boyut    : {_boyut(k['dosya_boyut'])}")
    print(f"  sha256   : {k['sha256']}")
    print(f"  imza     : {k['imza'][:44]}…")
    print(f"  indirme  : /indir/{k['urun']}/{k['surum']}/{k['dosya_ad']}")
    return dogrula(int(k["surum_id"]))


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        try:
            mk_db.havuz_kapat()
        except Exception:
            pass
