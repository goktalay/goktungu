#!/usr/bin/env python3
"""GRCOFF 2.5.121 Linux/Windows paketlerini güvenli biçimde kataloglar.

2.5.55 yayın aracının birebir güvenlik desenini izler. 2.5.121 içeriği:
Türkbey yeni logo/ikon (tema uyumlu).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/opt/goktungu/merkez/python")
import mk_db  # noqa: E402
import mk_depo  # noqa: E402

URUN = "gcs"
PAKET_SURUM = "2.5.121"
APP_SURUM = "2.4.250"
ASGARI_SURUM = None
STAGING = Path("/root/grcoff_2528_build/src/dagitim")
DEPO_DIR = Path("/opt/goktungu/merkez/depo/gcs") / PAKET_SURUM

SHA_PLACEHOLDER = "DOLDURUN"

_NOT = (
    "GRCOFF 2.5.121 / App 2.4.250: Widget baslatici gece/gunduz temasina uyar (menu acilirlariyla ayni "
    "tema degiskenleri); acik temada okunmama hatasi giderildi."
)

BEKLENEN = {
    "linux": {
        "ad": "goktungu-merkez_2.5.121_all.deb",
        "sha256": "ba35546c24feefb752eab1b90ef18627d7bc0332ea721df8609f0a7f9bf3c26b",
        "notlar": _NOT,
    },
    "windows": {
        "ad": "GOKTUNGU-Merkez-Setup-2.5.121.exe",
        "sha256": "0b432eb8773632eb43ae817c21f5544c8c654cac3122a328cfece07a01e2d5d2",
        "notlar": _NOT,
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
    for platform, bilgi in BEKLENEN.items():
        if bilgi["sha256"] == SHA_PLACEHOLDER or len(bilgi["sha256"]) != 64:
            fail(f"{platform} SHA-256 girilmemis")
    if not STAGING.is_dir():
        fail(f"staging dizini bulunamadi: {STAGING}")

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

    mevcut = mk_db.sorgu(
        "SELECT surum_id, platform, sha256, etkin FROM surumler "
        "WHERE urun=%s AND surum=%s AND paket_tur='tam' ORDER BY surum_id",
        (URUN, PAKET_SURUM),
    )
    if any(bool(s.get("etkin")) for s in mevcut):
        fail(f"{PAKET_SURUM} için etkin katalog kaydı zaten bulunuyor")

    zaman = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    yedek = Path(f"/opt/goktungu/yedek/grcoff_2574_katalog_{zaman}")
    yedek.mkdir(mode=0o700, parents=True, exist_ok=False)
    with (yedek / "surumler_2574_once.json").open("w", encoding="utf-8") as dosya:
        json.dump(mevcut, dosya, ensure_ascii=False, indent=2, default=str)
        dosya.write("\n")
    os.chmod(yedek / "surumler_2574_once.json", 0o600)

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
