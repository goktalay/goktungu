#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GRCOFF dosya tabanlı güncelleme yayını: depo + imzalı manifest üretir.

Verilen paket ağacından (install kökü layout'u) YÖNETİLEN dosyaları
depo/gcs_dosya/<app_surum>/ altına kopyalar, her dosyanın sha256'sını
alır, bir önceki yayına göre silinecekleri hesaplar, manifesti Ed25519
ile imzalar ve GUNCEL işaretçisini günceller.

Kullanım:
  python3.11 dosya_manifest_yayinla.py <agac> [--depo <kok>]
    <agac>  : paketle_merkez --agac-birak çıktısı (install kökü)
    --depo  : varsayılan /opt/goktungu/merkez/depo/gcs_dosya
"""
import hashlib
import json
import os
import re
import shutil
import sys
import time

sys.path.insert(0, "/opt/goktungu/merkez/python")
import mk_depo  # noqa: E402  (Ed25519 imza; açık anahtar pakete gömülü ile eşleşir)

URUN = "gcs"
YONETILEN_KOKLER = ("assets", "ai_modeller")
YONETILEN_DOSYALAR = ("main.py", "requirements.txt", "goktungu_guncelleyici.py")
VARSAYILAN_DEPO = "/opt/goktungu/merkez/depo/gcs_dosya"


def _govde_bayt(govde: dict) -> bytes:
    # goktungu/lisans.govde_bayt ile BİREBİR aynı kanonik biçim.
    return json.dumps(govde, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _surum_oku(agac: str) -> str:
    for aday in (os.path.join(agac, "assets", "web", "js", "surum.js"),
                 os.path.join(agac, "js", "surum.js")):
        try:
            with open(aday, encoding="utf-8") as f:
                m = re.search(r'GCS_SURUM\s*=\s*["\']([0-9][0-9.]*)["\']',
                              f.read(2048))
            if m:
                return m.group(1)
        except OSError:
            continue
    sys.exit("HATA: surum.js/GCS_SURUM okunamadı")


def _yonetilen_dosyalar(agac: str):
    """(bagil, tam_yol) listesi: yalnız yönetilen kök ve dosyalar."""
    cikti = []
    for ad in YONETILEN_DOSYALAR:
        t = os.path.join(agac, ad)
        if os.path.isfile(t):
            cikti.append((ad, t))
    for kok in YONETILEN_KOKLER:
        taban = os.path.join(agac, kok)
        for dizin, _, dosyalar in os.walk(taban):
            for d in dosyalar:
                tam = os.path.join(dizin, d)
                bagil = os.path.relpath(tam, agac).replace(os.sep, "/")
                cikti.append((bagil, tam))
    return sorted(cikti)


def _sha256(yol: str) -> tuple:
    h = hashlib.sha256()
    n = 0
    with open(yol, "rb") as f:
        for blok in iter(lambda: f.read(262144), b""):
            h.update(blok)
            n += len(blok)
    return h.hexdigest(), n


def _onceki_manifest(depo: str):
    try:
        with open(os.path.join(depo, "GUNCEL"), encoding="utf-8") as f:
            eski = f.read().strip()
        with open(os.path.join(depo, eski, "MANIFEST.imzali.json"),
                  encoding="utf-8") as f:
            return json.load(f).get("manifest", {})
    except (OSError, ValueError):
        return {}


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    agac = os.path.abspath(sys.argv[1])
    depo = VARSAYILAN_DEPO
    if "--depo" in sys.argv:
        depo = os.path.abspath(sys.argv[sys.argv.index("--depo") + 1])
    if not os.path.isdir(agac):
        sys.exit("HATA: agac yok: %s" % agac)

    surum = _surum_oku(agac)
    hedef_dir = os.path.join(depo, surum)
    dosyalar = _yonetilen_dosyalar(agac)
    if not dosyalar:
        sys.exit("HATA: yönetilen dosya bulunamadı")

    # Kopyala + sha256
    if os.path.exists(hedef_dir):
        shutil.rmtree(hedef_dir)
    os.makedirs(hedef_dir, exist_ok=True)
    manifest_dosyalar = []
    for bagil, tam in dosyalar:
        sha, boyut = _sha256(tam)
        hedef = os.path.join(hedef_dir, *bagil.split("/"))
        os.makedirs(os.path.dirname(hedef), exist_ok=True)
        shutil.copy2(tam, hedef)
        manifest_dosyalar.append({"yol": bagil, "sha256": sha, "boyut": boyut})

    # Silinecekler: önceki yayında olup bunda olmayanlar
    eski = _onceki_manifest(depo)
    eski_yollar = {d["yol"] for d in eski.get("dosyalar", [])}
    yeni_yollar = {d["yol"] for d in manifest_dosyalar}
    silinecekler = sorted(eski_yollar - yeni_yollar)

    manifest = {
        "urun": URUN,
        "surum": surum,
        "acik_anahtar": mk_depo.acik_anahtar_b64(),
        "olusturma": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dosyalar": manifest_dosyalar,
        "silinecekler": silinecekler,
    }
    imza = mk_depo.veri_imzala(_govde_bayt(manifest))
    with open(os.path.join(hedef_dir, "MANIFEST.imzali.json"), "w",
              encoding="utf-8") as f:
        json.dump({"manifest": manifest, "imza": imza}, f,
                  ensure_ascii=False, indent=1)

    # İzinler (servis hesabı okuyabilmeli) + GUNCEL işaretçisi
    for kokd, dizinler, dsylar in os.walk(hedef_dir):
        os.chmod(kokd, 0o755)
        for d in dsylar:
            os.chmod(os.path.join(kokd, d), 0o644)
    with open(os.path.join(depo, "GUNCEL"), "w", encoding="utf-8") as f:
        f.write(surum + "\n")
    os.chmod(os.path.join(depo, "GUNCEL"), 0o644)

    print(json.dumps({
        "surum": surum, "depo": hedef_dir,
        "dosya_sayisi": len(manifest_dosyalar),
        "toplam_bayt": sum(d["boyut"] for d in manifest_dosyalar),
        "silinecek": len(silinecekler),
        "imza": imza[:16] + "...",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
