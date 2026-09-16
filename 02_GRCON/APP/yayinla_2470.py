#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MERKEZ UYGULAMA (urun='gcs') 2.4.70 — depo yayimlama.

GOKTUNGU marka gecisi surumu.

API sozlesmesi (dogrulandi, /opt/goktungu/merkez/python/mk_depo.py):
  paket_ekle(urun, surum, kaynak_yol, *, platform, kanal, paket_tur,
             asgari_surum, notlar, yonetici_id) -> dict
  son_surum(urun, *, platform="ortak") -> dict
  URUNLER      = ("gcs","sunucu","dron","video","radar","ai","kopru")
  PLATFORMLAR  = ("ortak","linux","windows","linux-arm64")
  KANALLAR     = ("kararli","beta","deneysel")
  PAKET_TURLERI= ("tam","guncelleme")

`gcs` urunu GENEL_GIZLI_URUNLER ve LISANSLI_URUNLER icindedir: tanitim
sayfasinin genel katalogunda gorunmez, yalniz lisansli sirketlerin
kurumsal panelinde listelenir. Bu dogru davranistir — Merkez Uygulama
5.000 $ lisansli urundur.

Debian dosya adi bilincli olarak `goktungu-merkez_...deb` kalir: Debian
paket adi degisirse `apt` yukseltme yerine ikinci paket kurar ve iki
servis cakisir.
"""
import os
import sys

sys.path.insert(0, '/opt/goktungu/merkez/python')

import mk_depo  # noqa: E402

SURUM = '2.4.70'
URUN = 'gcs'
DAGITIM = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dagitim')

PAKETLER = [
    ('windows', f'GOKTUNGU-Merkez-Setup-{SURUM}.exe'),
    ('linux', f'goktungu-merkez_{SURUM}_all.deb'),
]

NOTLAR = (
    'GOKTUNGU marka gecisi: urun adi GOKTUNGU -> GOKTUNGU. '
    'Firma logolari (veilox.png, novixair.png, gokkubbe.png) kurulum '
    'paketinden cikarildi; yalniz GOKTUNGU urun logosu ve mavi ikon kaldi. '
    'Baslat menusu klasoru GOKTUNGU -> GOKTUNGU, kaldirmada eski klasor de '
    'temizleniyor. PWA tamamlandi: manifest.json ve sw.js eklendi. '
    'Servis adi GoktunguMerkez, Debian paket adi goktungu-merkez, kayit '
    'anahtarlari ve kurulum dizinleri KORUNDU (yukseltme yolu bozulmaz).'
)


def main():
    print('=' * 66)
    print(f'MERKEZ UYGULAMA (gcs) {SURUM} — depo yayimlama')
    print('=' * 66)

    eklendi = 0
    for platform, ad in PAKETLER:
        yol = os.path.join(DAGITIM, ad)
        print(f'\n== {platform} ==')
        print(f'  kaynak: {yol}')
        if not os.path.isfile(yol):
            print('  [KUSUR] dosya bulunamadi')
            continue
        try:
            sonuc = mk_depo.paket_ekle(
                URUN,
                SURUM,
                yol,
                platform=platform,
                kanal='kararli',
                paket_tur='tam',
                notlar=NOTLAR,
            )
        except Exception as hata:  # noqa: BLE001
            print(f'  [HATA] {type(hata).__name__}: {hata}')
            continue
        print(f'  [OK] eklendi: {sonuc.get("dosya_ad")}')
        print(f'       boyut  : {sonuc.get("dosya_boyut"):,} bayt')
        sha = sonuc.get('sha256') or ''
        print(f'       sha256 : {sha[:20]}...')
        imza = sonuc.get('imza') or ''
        print(f'       imza   : {imza[:20]}...' if imza else '       imza   : YOK')
        eklendi += 1

    print()
    print('=' * 66)
    print('KATALOG DOGRULAMASI')
    print('=' * 66)
    gecti = kaldi = 0
    for platform, _ in PAKETLER:
        k = mk_depo.son_surum(URUN, platform=platform)
        bulunan = k.get('surum') if k else None
        if bulunan == SURUM:
            print(f'  [OK] {platform:8s} -> {bulunan}')
            gecti += 1
        else:
            print(f'  [KUSUR] {platform:8s} -> {bulunan} (beklenen {SURUM})')
            kaldi += 1

    print()
    print(f'SONUC: {eklendi} paket eklendi, katalog {gecti} gecti / {kaldi} kusur')
    return 0 if kaldi == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
