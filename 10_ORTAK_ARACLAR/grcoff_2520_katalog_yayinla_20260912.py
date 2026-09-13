#!/usr/bin/env python3
"""GRCOFF 2.5.20 Linux/Windows paketlerini güvenli biçimde kataloglar.

Bu betik üretim sunucusunda root olarak çalıştırılmak üzere tasarlanmıştır.
Yalnız gcs/2.5.20 tam paketlerini ekler; önce SHA-256 değerlerini sabitlerle
karşılaştırır, katalog satırlarını yedekler, Ed25519 imzasını doğrular ve
app_surum alanını kesin kimliklerle 2.4.150 olarak kaydeder.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/opt/goktungu/merkez/python")
import mk_db  # noqa: E402
import mk_depo  # noqa: E402

URUN = "gcs"
PAKET_SURUM = "2.5.20"
APP_SURUM = "2.4.150"
ASGARI_SURUM = "2.4.149"
STAGING = Path("/opt/goktungu/merkez/yayin_staging/grcoff_2520_20260912")
DEPO_DIR = Path("/opt/goktungu/merkez/depo/gcs") / PAKET_SURUM
BEKLENEN = {
    "linux": {
        "ad": "goktungu-merkez_2.5.20_all.deb",
        "sha256": "c0c29384b6231a3924316cc3b1c26e36d800f66f41808e543117b8fabe3aef79",
        "notlar": (
            "GRCOFF 2.5.20 / App 2.4.150: köprüsüz yerel kamera yönetimi, "
            "ortak yüzen görüntü penceresi, dron-kamera ilişkilendirmesi, "
            "yalnız İnsan/Kara Araç/Hava Araç sınıflı yerel AI ve salt-okunur "
            "pasif takip verisi dinleyicisi."
        ),
    },
    "windows": {
        "ad": "GOKTUNGU-Merkez-Setup-2.5.20.exe",
        "sha256": "aa2a5a5fe4ef81887ff63e380ac36d107e4f2e0405f3aaefba6cc2c1c635d62e",
        "notlar": (
            "GRCOFF 2.5.20 / App 2.4.150: köprüsüz yerel kamera yönetimi, "
            "ortak yüzen görüntü penceresi, dron-kamera ilişkilendirmesi, "
            "yalnız İnsan/Kara Araç/Hava Araç sınıflı yerel AI ve salt-okunur "
            "pasif takip verisi dinleyicisi."
        ),
    },
}


def fail(message: str) -> None:
    raise RuntimeError(message)


def satir_kimligi(kayit: dict, platform: str, sha256: str) -> None:
    zorunlu = {
        "urun": URUN,
        "surum": PAKET_SURUM,
        "platform": platform,
        "paket_tur": "tam",
        "sha256": sha256,
    }
    for alan, deger in zorunlu.items():
        if str(kayit.get(alan)) != deger:
            fail(f"katalog kimligi uyusmuyor: {alan}={kayit.get(alan)!r}")


def main() -> None:
    if os.geteuid() != 0:
        fail("betik root olarak calistirilmalidir")
    if not STAGING.is_dir():
        fail(f"staging dizini bulunamadi: {STAGING}")

    # Her iki dosyayı da katalogdan ÖNCE bit düzeyinde doğrula.
    preflight = {}
    for platform, bilgi in BEKLENEN.items():
        yol = STAGING / bilgi["ad"]
        if not yol.is_file():
            fail(f"staging paketi yok: {yol}")
        sha256, boyut = mk_depo.dosya_ozeti(str(yol))
        if sha256 != bilgi["sha256"]:
            fail(f"SHA-256 uyusmuyor ({platform}): {sha256}")
        if boyut <= 0:
            fail(f"paket bos ({platform})")
        preflight[platform] = {"yol": str(yol), "sha256": sha256, "boyut": boyut}

    # Yeni sürüm yanlışlıkla daha önce etkin yayımlanmışsa üzerine yazma.
    mevcut = mk_db.sorgu(
        "SELECT surum_id, platform, sha256, etkin FROM surumler "
        "WHERE urun=%s AND surum=%s AND paket_tur='tam' ORDER BY surum_id",
        (URUN, PAKET_SURUM),
    )
    if any(bool(s.get("etkin")) for s in mevcut):
        fail("2.5.20 için etkin katalog kaydı zaten bulunuyor")

    zaman = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    yedek = Path(f"/opt/goktungu/yedek/grcoff_2520_katalog_{zaman}")
    yedek.mkdir(mode=0o700, parents=True, exist_ok=False)
    with (yedek / "surumler_2520_once.json").open("w", encoding="utf-8") as dosya:
        json.dump(mevcut, dosya, ensure_ascii=False, indent=2, default=str)
        dosya.write("\n")
    os.chmod(yedek / "surumler_2520_once.json", 0o600)

    kayitlar = {}
    try:
        for platform, bilgi in BEKLENEN.items():
            kayit = mk_depo.paket_ekle(
                URUN,
                PAKET_SURUM,
                preflight[platform]["yol"],
                platform=platform,
                kanal="kararli",
                paket_tur="tam",
                asgari_surum=ASGARI_SURUM,
                notlar=bilgi["notlar"],
            )
            satir_kimligi(kayit, platform, bilgi["sha256"])
            kayitlar[platform] = kayit

        # paket_ekle app_surum almadığı için yalnız az önce eklenen kesin satırları güncelle.
        for platform, kayit in kayitlar.items():
            sonuc = mk_db.tek(
                "UPDATE surumler SET app_surum=%s "
                "WHERE surum_id=%s AND urun=%s AND surum=%s AND platform=%s "
                "AND paket_tur='tam' AND sha256=%s "
                "RETURNING surum_id, urun, surum, platform, paket_tur, sha256, app_surum, imza, dosya_ad, dosya_boyut, etkin",
                (
                    APP_SURUM,
                    kayit["surum_id"],
                    URUN,
                    PAKET_SURUM,
                    platform,
                    BEKLENEN[platform]["sha256"],
                ),
            )
            if not sonuc or sonuc["app_surum"] != APP_SURUM:
                fail(f"app_surum kaydi basarisiz ({platform})")
            if not mk_depo.imza_dogrula(
                sonuc["urun"],
                sonuc["surum"],
                sonuc["platform"],
                sonuc["paket_tur"],
                sonuc["sha256"],
                int(sonuc["dosya_boyut"]),
                sonuc["imza"],
            ):
                fail(f"Ed25519 imza dogrulamasi basarisiz ({platform})")
            dosya = DEPO_DIR / sonuc["dosya_ad"]
            dosya_sha, dosya_boyut = mk_depo.dosya_ozeti(str(dosya))
            if dosya_sha != sonuc["sha256"] or dosya_boyut != int(sonuc["dosya_boyut"]):
                fail(f"depo dosyasi/katalog uyusmazligi ({platform})")

        DEPO_DIR.chmod(0o755)
        os.chown(DEPO_DIR, 0, 0)
        for bilgi in BEKLENEN.values():
            os.chmod(DEPO_DIR / bilgi["ad"], 0o644)

        sonuc = {
            "durum": "tamam",
            "yedek": str(yedek),
            "depo": str(DEPO_DIR),
            "kayitlar": kayitlar,
            "preflight": preflight,
        }
        print(json.dumps(sonuc, ensure_ascii=False, indent=2, default=str))
    except Exception:
        # Kısmi başarısızlıkta yeni satırları görünmez yap; 2.5.19 korunur.
        for platform, bilgi in BEKLENEN.items():
            try:
                mk_db.calistir(
                    "UPDATE surumler SET etkin=FALSE WHERE urun=%s AND surum=%s "
                    "AND platform=%s AND paket_tur='tam' AND sha256=%s",
                    (URUN, PAKET_SURUM, platform, bilgi["sha256"]),
                )
            except Exception:
                pass
        raise


if __name__ == "__main__":
    main()
