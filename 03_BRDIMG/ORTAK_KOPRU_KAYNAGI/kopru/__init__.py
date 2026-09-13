# -*- coding: utf-8 -*-
"""GOKTUNGU KOPRU YAZILIMI.

Kullanicinin bilgisayarina kurulan KUCUK araci yazilim. Gorevleri:

  1) Yerel web paneli acmak (merkez kimligiyle giris)
  2) Uc servisi yonetmek: Dron / AI / Video (baslat, durdur, konsol)
  3) Merkeze kalici ters WebSocket baglantisi tutmak
  4) Telemetriyi yerel tamponda biriktirip merkez PostgreSQL'e aktarmak

GOKTUNGU yer kontrol ARAYUZU bu pakette YOKTUR; o merkezde
`https://goktungu.com/app/` altinda calisir. Ayrim bilincli:
kullanici 36 MB'lik GCS yerine yalniz kopruyu indirir ve harita,
gorev, dron panelleri her zaman merkezdeki GUNCEL surumdur.
"""
from .ayar import SURUM

__all__ = ["SURUM"]
