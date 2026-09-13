#!/usr/bin/env python3
"""GRCOFF 2.5.27 Linux/Windows paketlerini güvenli biçimde kataloglar.

Bu betik ÜRETİM sunucusunda (AlmaLinux; katalog/dağıtım hostu) root olarak
çalıştırılmak üzere tasarlanmıştır. 2.5.20 yayın aracının birebir güvenlik
desenini izler: yalnız gcs/2.5.27 tam paketlerini ekler; önce SHA-256
değerlerini SABİTLERLE karşılaştırır, katalog satırlarını yedekler, Ed25519
imzasını doğrular ve app_surum alanını 2.4.157 olarak kaydeder.

Paketler bu hostta Docker (debian:12) kapsayicisinda uretildi; SHA-256
degerleri o build ciktisindan girildi.

=====================================================================
KULLANIM SIRASI (resmi yol)
=====================================================================
1. Paketler Docker (debian:12) kapsayicisinda, bu teslimdeki DEĞİŞTİRİLMİŞ kaynaktan
   (01_GRCOFF/KAYNAK) üretilir:
       python3.11 deb_merkez_uret.py        # -> goktungu-merkez_2.5.27_all.deb
       python3.11 setup_merkez_uret.py      # -> GOKTUNGU-Merkez-Setup-2.5.27.exe
   (Sürüm js/surum.js -> GCS_SURUM=2.4.157'den okunur; paket adı 2.5.27
   PAKET_SURUM ile verilir — build script argümanına bakın.)
2. Build kutusu her iki dosyanın SHA-256'sını raporlar:
       sha256sum goktungu-merkez_2.5.27_all.deb GOKTUNGU-Merkez-Setup-2.5.27.exe
3. Bu değerler aşağıdaki BEKLENEN["linux"]["sha256"] ve
   BEKLENEN["windows"]["sha256"] alanlarına GİRİLİR (placeholder kaldıkça
   betik çalışmayı reddeder — kör yayın yok).
4. İki dosya bu hostta STAGING dizinine kopyalanır.
5. Betik root ile çalıştırılır; yayın + imza doğrulaması + izin ayarı yapılır.
6. Yayından sonra güncelleme ucu ve müşteri panelinde 2.5.27 doğrulanır.
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
PAKET_SURUM = "2.5.27"
APP_SURUM = "2.4.157"
# BILINCLI OLARAK BOS: guncelleme_kontrol istemcinin bildirdigi PAKET
# surumunu asgari_surum ile kiyaslar. 2.5.20/2.5.21 kurulumlari sabit
# kusur yuzunden kendini "2.5.19" bildirir; asgari 2.5.21 verilirse bu
# kurulumlar 2.5.27'ye HIC guncellenemezdi.
ASGARI_SURUM = None
STAGING = Path("/root/grcoff_2527_build/src/dagitim")
DEPO_DIR = Path("/opt/goktungu/merkez/depo/gcs") / PAKET_SURUM

# Build kutusu SHA-256'larını raporlayınca doldurun. Placeholder kaldıkça
# betik çalışmaz (bkz. main()).
SHA_PLACEHOLDER = "DOLDURUN"

_NOT = (
    "GRCOFF 2.5.27 / App 2.4.157: AI ayarı değiştirilince oluşan çökme "
    "(0xC0000374) giderildi + dosya tabanlı arka plan güncelleme servisi. "
    "Dosya bazlı güncellemeye geçiş için BİR KERELİK kurulum; sonraki "
    "güncellemeler otomatik ve AV dostudur."
)

BEKLENEN = {
    "linux": {
        "ad": "goktungu-merkez_2.5.27_all.deb",
        "sha256": "8055ab7e25cd16d661d824cbed1a1cb2a3e772f7a88f24f1c74dd9182ad26a1e",
        "notlar": _NOT,
    },
    "windows": {
        "ad": "GOKTUNGU-Merkez-Setup-2.5.27.exe",
        "sha256": "792ed439b855c97c49f41c7935d41205727580da9f38fbdc88bde873fc129b96",
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
    # Kör yayın yasağı: SHA-256 sabitleri build kutusundan girilmeden çalışma.
    for platform, bilgi in BEKLENEN.items():
        if bilgi["sha256"] == SHA_PLACEHOLDER or len(bilgi["sha256"]) != 64:
            fail(f"{platform} SHA-256 girilmemis; build kutusu ozetini "
                 f"BEKLENEN['{platform}']['sha256'] alanina yazin")
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
        fail(f"{PAKET_SURUM} için etkin katalog kaydı zaten bulunuyor")

    zaman = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    yedek = Path(f"/opt/goktungu/yedek/grcoff_2527_katalog_{zaman}")
    yedek.mkdir(mode=0o700, parents=True, exist_ok=False)
    with (yedek / "surumler_2527_once.json").open("w", encoding="utf-8") as dosya:
        json.dump(mevcut, dosya, ensure_ascii=False, indent=2, default=str)
        dosya.write("\n")
    os.chmod(yedek / "surumler_2527_once.json", 0o600)

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

        # paket_ekle app_surum almadığı için yalnız az önce eklenen satırları güncelle.
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
        # Kısmi başarısızlıkta yeni satırları görünmez yap; 2.5.22 korunur.
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
