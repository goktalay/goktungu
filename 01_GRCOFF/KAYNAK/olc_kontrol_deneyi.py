#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""KONTROL DENEYI — sinav_ucus_sahipligi.py gercekten kusuru yakaliyor mu?

Neden gerekli: bir sinavin "gecti" demesi, sinavin BIR SEY olctugunu
kanitlamaz. Yanlis yere bakan bir sinav da gecer. Bu betik eski kusurlu
davranisi bilerek geri getirir ve sinavin KALDI demesini bekler.

Uc kusur ayri ayri taklit edilir:
  A) ucus_listesi: sahipsiz ucuslari herkese goster (asil kullanici sikayeti)
  B) sunucu ucus_sil: sahiplik denetimini kaldir (yetki yukseltme)
  C) ucus_sahibi_detay: takeoff_gonderildi kosulunu kaldir (yanlis sahip)

Her adimda dosya yedeklenir, kusur enjekte edilir, sinav kosulur,
dosya geri yuklenir. Sonunda saglam halin 0 kaldi verdigi teyit edilir.
"""
import shutil
import subprocess
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent
SINAV = KOK / "sinav_ucus_sahipligi.py"

DENEYLER = [
    {
        "ad": "A) sahipsiz ucuslar herkese acik (kullanici sikayeti)",
        "dosya": KOK / "goktungu" / "veritabani.py",
        "bul": "    if not yonetici:",
        "koy": "    if not yonetici and False:",
        "beklenen_izler": [
            "SAHIPSIZ ucus pilota GORUNMUYOR",
            "pilot YALNIZ kendi ucusunu goruyor",
        ],
    },
    {
        "ad": "B) ucus_sil sahiplik denetimi kaldirildi (yetki yukseltme)",
        "dosya": KOK / "goktungu" / "sunucu.py",
        "bul": None,   # asagida ozel islenir
        "koy": None,
        "beklenen_izler": ["ucus_sil: sahip_mi denetimi var"],
    },
    {
        # ONEMLI: hedef, sahiplik SQL'indeki ORDER BY ifadesidir.
        # Yalniz "takeoff_gonderildi" aramak YETMEZ; bu ad dosyada
        # bircok yerde geciyor ve replace(...,1) ilk geciste duruyordu,
        # o gecis sahiplik sorgusu olmadigi icin sorgu hic bozulmuyor,
        # deney de yanlis olarak "sinav yakalamadi" diyordu.
        "ad": "C) sahiplik siralamasi bozuldu (yanlis sahip)",
        "dosya": KOK / "goktungu" / "veritabani.py",
        "bul": "ORDER BY takeoff_gonderildi DESC",
        "koy": "ORDER BY",
        "beklenen_izler": [
            "DAVRANIS: sahip = takeoff'u VEREN pilot",
            "takeoff_gonderildi kosulu var",
        ],
    },
]


def sinav_kos():
    r = subprocess.run([sys.executable, str(SINAV)],
                       capture_output=True, text=True, timeout=600)
    return r.returncode, r.stdout


def kaldi_satirlari(cikti):
    return [s.strip() for s in cikti.splitlines() if "KALDI" in s]


print("=" * 68)
print("KONTROL DENEYI — sinav gercekten kusuru yakaliyor mu?")
print("=" * 68)

# Once saglam hal
kod, cikti = sinav_kos()
print(f"\n[SAGLAM HAL] cikis kodu={kod}")
if kod != 0:
    print("  HATA: saglam hal gecmeliydi. Kalanlar:")
    for s in kaldi_satirlari(cikti):
        print(f"    {s}")
    sys.exit(1)
print("  OK — saglam hal 0 kaldi")

basarili = 0
basarisiz = 0

for d in DENEYLER:
    dosya = d["dosya"]
    yedek = dosya.with_suffix(dosya.suffix + ".kontrol_yedek")
    shutil.copy2(dosya, yedek)
    try:
        metin = dosya.read_text(encoding="utf-8")

        if d["ad"].startswith("B"):
            # ucus_sil dalindaki sahip_mi blogunu devre disi birak:
            # 'sahip_mi' cagrisini farkli bir ada cevir (yalniz ucus_sil dalinda)
            idx = metin.find('komut == "ucus_sil"')
            if idx < 0:
                print(f"\n[{d['ad']}] ATLANDI — dal bulunamadi")
                continue
            pencere = metin[idx:idx + 2000]
            yeni_pencere = pencere.replace("sahip_mi", "SAHIPLIK_YOK", 1)
            metin_yeni = metin[:idx] + yeni_pencere + metin[idx + 2000:]
        else:
            if d["bul"] not in metin:
                print(f"\n[{d['ad']}] ATLANDI — hedef bulunamadi")
                continue
            metin_yeni = metin.replace(d["bul"], d["koy"], 1)

        dosya.write_text(metin_yeni, encoding="utf-8")
        kod2, cikti2 = sinav_kos()
        kalanlar = kaldi_satirlari(cikti2)

        print(f"\n[{d['ad']}]")
        print(f"  cikis kodu={kod2}, kalan olcum={len(kalanlar)}")

        if kod2 == 0:
            print("  BASARISIZ — sinav kusuru YAKALAMADI (yanlis yere bakiyor)")
            basarisiz += 1
        else:
            yakalandi = any(
                any(iz in s for iz in d["beklenen_izler"]) for s in kalanlar)
            for s in kalanlar[:4]:
                print(f"    {s}")
            if yakalandi:
                print("  BASARILI — beklenen olcum kaldi")
                basarili += 1
            else:
                print("  KISMI — kusur yakalandi ama beklenen olcum degil")
                basarili += 1
    finally:
        shutil.copy2(yedek, dosya)
        yedek.unlink()

# Geri yukleme dogrulamasi
kod3, cikti3 = sinav_kos()
print(f"\n[GERI YUKLEME] cikis kodu={kod3}")
if kod3 != 0:
    print("  HATA: dosyalar bozuk kaldi!")
    for s in kaldi_satirlari(cikti3):
        print(f"    {s}")
    sys.exit(1)
print("  OK — kaynak saglam, 0 kaldi")

print("\n" + "=" * 68)
print(f"SONUC: {basarili} deney kusuru yakaladi, {basarisiz} yakalamadi")
print("=" * 68)
sys.exit(0 if basarisiz == 0 else 1)
