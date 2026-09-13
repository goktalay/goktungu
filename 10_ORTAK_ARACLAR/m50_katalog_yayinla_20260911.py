#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""M50/offline kamera sürümlerini üretim güncelleme deposuna imzalı kaydeder.

Yalnız yeni altı kayıt hedeflenir. Hata halinde bu yordamın eklediği kayıtlar
etkisizleştirilir; daha eski katalog kayıtlarına dokunulmaz.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

MERKEZ_KOKU = "/opt/goktungu/merkez/python"
PAKET_KOKU = "/opt/goktungu/yayin_staging/m50_offline_20260911_1515/paketler"
sys.path.insert(0, MERKEZ_KOKU)

import mk_depo  # noqa: E402

PAKETLER = (
    ("gcs", "2.5.19", "linux", "goktungu-merkez_2.5.19_all.deb",
     "M50 kontrol vekili ve offline Merkezde Köprüsüz, oturum korumalı canlı kamera yayını."),
    ("gcs", "2.5.19", "windows", "GOKTUNGU-Merkez-Setup-2.5.19.exe",
     "M50 kontrol vekili ve offline Merkezde Köprüsüz, oturum korumalı canlı kamera yayını."),
    ("kopru", "1.7.14", "linux", "goktungu-kopru_1.7.14_all.deb",
     "M50 için güvenli saha Köprüsü kontrol katmanı; SDK yalnız Windows x64 koşulunda kullanılır."),
    ("kopru", "1.7.14", "windows", "GOKTUNGU-Kopru-Setup-1.7.14.exe",
     "M50 için güvenli saha Köprüsü kontrol katmanı; SDK yalnız Windows x64 koşulunda kullanılır."),
    ("video", "1.3.8", "linux", "goktungu_goruntu_1.3.8_all.deb",
     "M50 görünür ve termal RTSP(S) kaynak türleri için yerel Görüntü Köprüsü desteği."),
    ("video", "1.3.8", "windows", "GOKTUNGU-Goruntu-Setup-1.3.8.exe",
     "M50 görünür ve termal RTSP(S) kaynak türleri için yerel Görüntü Köprüsü desteği."),
)


def ana() -> int:
    eklenen: list[dict] = []
    try:
        for urun, surum, platform, dosya_ad, notlar in PAKETLER:
            kaynak = os.path.join(PAKET_KOKU, dosya_ad)
            kayit = mk_depo.paket_ekle(
                urun, surum, kaynak, platform=platform, kanal="kararli",
                paket_tur="tam", notlar=notlar,
            )
            if not kayit:
                raise RuntimeError(f"bos katalog kaydi: {urun}/{platform}")
            if not mk_depo.imza_dogrula(
                kayit["urun"], kayit["surum"], kayit["platform"],
                kayit["paket_tur"], kayit["sha256"], kayit["dosya_boyut"],
                kayit["imza"],
            ):
                raise RuntimeError(f"imza dogrulanamadi: {urun}/{platform}")
            eklenen.append(kayit)

        sonuc = []
        for urun, surum, platform, dosya_ad, _ in PAKETLER:
            son = mk_depo.son_surum(
                urun, platform=platform, kanal="kararli", paket_tur="tam")
            if not son or son.get("surum") != surum or son.get("dosya_ad") != dosya_ad:
                raise RuntimeError(f"son surum gorunurlugu basarisiz: {urun}/{platform}")
            if not mk_depo.imza_dogrula(
                son["urun"], son["surum"], son["platform"], son["paket_tur"],
                son["sha256"], son["dosya_boyut"], son["imza"],
            ):
                raise RuntimeError(f"son surum imzasi gecersiz: {urun}/{platform}")
            sonuc.append({
                "urun": urun, "surum": surum, "platform": platform,
                "surum_id": son["surum_id"], "dosya": dosya_ad,
                "sha256": son["sha256"], "boyut": son["dosya_boyut"],
            })
        print(json.dumps({"durum": "basarili", "paketler": sonuc}, ensure_ascii=False))
        return 0
    except Exception:
        for kayit in reversed(eklenen):
            try:
                mk_depo.paket_devre_disi(int(kayit["surum_id"]))
                dosya = Path(mk_depo.paket_yolu(
                    kayit["urun"], kayit["surum"], kayit["dosya_ad"]))
                if dosya.is_file():
                    dosya.unlink()
                if dosya.parent.is_dir() and not any(dosya.parent.iterdir()):
                    dosya.parent.rmdir()
            except Exception:
                pass
        raise


if __name__ == "__main__":
    raise SystemExit(ana())
