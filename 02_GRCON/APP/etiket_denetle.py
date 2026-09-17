#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GRCOFF — ÖNBELLEK ETİKETİ DENETİMİ (v2.4.221).

ÖLÇÜLEN KUSUR (2.4.219, kullanıcı konsolu): kameralar.js değişmiş ama
index.html'deki `?v=` etiketi güncellenmemişti; tarayıcı bir yıl
önbelleklenen ESKİ dosyayı kullandı ve modül yüklenirken çöktü ("Yeni
Kamera" çalışmadı). Aynı kusur surum.js'de sürekli vardı (etiket v24164).

Bu betik, son yayınlanan depo ağacına (depo/GUNCEL) göre İÇERİĞİ DEĞİŞEN
her js/css dosyasının index.html etiketinin de değişmiş olmasını ister.
Değişmemiş etiket = HATA (çıkış kodu 1). Yayın zincirinde derlemeden ÖNCE
çalıştırılır.

Kullanım:  python3.11 etiket_denetle.py [--depo /opt/goktungu/merkez/depo/gcs_dosya]
"""
from __future__ import annotations

import argparse
import filecmp
import os
import re
import sys

KOK = os.path.dirname(os.path.abspath(__file__))


def etiketler(index_yolu: str) -> dict:
    with open(index_yolu, encoding="utf-8") as f:
        m = f.read()
    return {yol: tag for yol, tag in re.findall(r'(?:src|href)="((?:js|css)/[^"?]+)\?v=([^"]+)"', m)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--depo", default="/opt/goktungu/merkez/depo/gcs_dosya")
    a = ap.parse_args()
    try:
        with open(os.path.join(a.depo, "GUNCEL"), encoding="utf-8") as f:
            eski_surum = f.read().strip()
    except OSError:
        print("[ETIKET] depo/GUNCEL yok; denetim atlandi")
        return 0
    eski_web = os.path.join(a.depo, eski_surum, "assets", "web")
    if not os.path.isdir(eski_web):
        print("[ETIKET] eski web agaci yok (%s); denetim atlandi" % eski_web)
        return 0
    yeni_tag = etiketler(os.path.join(KOK, "index.html"))
    eski_tag = etiketler(os.path.join(eski_web, "index.html"))
    hatalar = []
    for yol, tag in yeni_tag.items():
        yeni_dosya = os.path.join(KOK, *yol.split("/"))
        eski_dosya = os.path.join(eski_web, *yol.split("/"))
        if not (os.path.isfile(yeni_dosya) and os.path.isfile(eski_dosya)):
            continue
        if filecmp.cmp(yeni_dosya, eski_dosya, shallow=False):
            continue
        if eski_tag.get(yol) == tag:
            hatalar.append("%s degisti ama etiket ayni (?v=%s)" % (yol, tag))
    if hatalar:
        print("[ETIKET] KUSUR — tarayici eski dosyayi onbellekten kullanir:")
        for h in hatalar:
            print("   - " + h)
        return 1
    print("[ETIKET] TAMAM (%s'e gore %d dosya kontrol edildi)" % (eski_surum, len(yeni_tag)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
