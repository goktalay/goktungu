"""GRCOFF kurulum paketi (katalog) surumu - TEK KAYNAK.

Uygulama surumu (GCS_SURUM, js/surum.js) ile AYNI DEGILDIR: katalogdaki
paket 2.5.x, uygulama 2.4.x ilerler. Bu deger:
  * main.py'de GuncellemeYoneticisi'ne "mevcut surum" olarak verilir,
  * deb_merkez_uret.py ve setup_merkez_uret.py tarafindan paket adi/NSIS
    SURUM olarak okunur.

OLCULEN KUSUR (2.5.19-2.5.21): main.py surumu "2.5.19" diye SABIT
yaziyordu; 2.5.20 ve 2.5.21 kurulumlari kendini 2.5.19 sanip "YENI SURUM
HAZIR" uyarisini kalici gosteriyordu. Build betikleri de kendi sabitlerini
tasiyordu. Uc kopya tek kaynaga indirildi.
"""
PAKET_SURUM = "2.5.99"

# Bu paketin tasidigi uygulama surumu (js/surum.js GCS_SURUM ile ESLESMELI).
# Build betikleri eslesmezse durur (bayat agac / yanlis eslesme kapisi).
UYGULAMA_SURUM = "2.4.229"
