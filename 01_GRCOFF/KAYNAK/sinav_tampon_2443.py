#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.4.43 — TELEMETRI TAMPONU SONSUZ DONGU SINAVI

Kullanici hatasi (Windows, 2026-08-09):

    [TEL] tel_20260809_0443.jsonl isaretlenemedi: [WinError 32] ...
    [TEL] 17 telemetri ornegi 1 dosyadan aktarildi
    ... (sonsuz tekrar)

Bu betik hatayi Linux'ta YENIDEN URETIR. Windows'un "acik dosya
yeniden adlandirilamaz" davranisi POSIX'te yoktur; bu yuzden
`os.replace` yamalanip Windows gibi davranmasi saglanir. Boylece
duzeltmeyi gercek isletim sistemi olmadan OLCEBILIRIZ.

Olculen 3 sey:
  A. ESKI KUSUR: acik dosya bayatladiginda aktarilmaya calisiliyor mu?
  B. DONGU: isaretleme basarisizsa ayni ornekler tekrar tekrar
     veritabanina yaziliyor mu?
  C. DUZELTME: acik dosya haric tutuluyor ve isaretleme hatasinda
     aktarim sayilmayip karantinaya gidiliyor mu?
"""
import os
import shutil
import sys
import tempfile
import time

KOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "goktungu")
sys.path.insert(0, KOK)

from goktungu import telemetri_tampon as tt   # noqa: E402

GECEN = 0
KALAN = 0


def olc(ad, kosul, ayrinti=""):
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print("  [GECTI]  " + ad + ((" — " + ayrinti) if ayrinti else ""))
    else:
        KALAN += 1
        print("  [KALDI]  " + ad + ((" — " + ayrinti) if ayrinti else ""))


class WindowsTaklidi:
    """`os.replace`i Windows gibi davranmaya zorlar.

    Windows, baska bir tanitici tarafindan acik tutulan dosyayi yeniden
    adlandirmayi WinError 32 ile reddeder. POSIX buna izin verir.
    """

    def __init__(self, acik_yollar):
        self.acik_yollar = acik_yollar
        self._gercek = os.replace
        self.engellenen = 0

    def __enter__(self):
        def yamali(src, dst, *a, **k):
            if os.path.abspath(src) in self.acik_yollar:
                self.engellenen += 1
                raise OSError(
                    32, "Dosya baska bir islem tarafindan kullanildigindan "
                        "bu islem dosyaya erisemiyor")
            return self._gercek(src, dst, *a, **k)
        os.replace = yamali
        return self

    def __exit__(self, *a):
        os.replace = self._gercek
        return False


def tampon_kur(dizin):
    kayitlar = []

    def konsol(etiket, mesaj, tur="bilgi"):
        kayitlar.append((tur, mesaj))

    t = tt.TelemetriTampon(dizin, konsol)
    return t, kayitlar


def ornek(i, ts):
    return {"dron_id": 1, "oturum_id": 1, "ts": ts, "lat": 39.9 + i * 1e-5,
            "lon": 32.8, "alt_rel": 10.0 + i, "groundspeed": 5.0,
            "heading": 90.0, "mod": "GUIDED", "armed": 1}


def main():
    print("=" * 68)
    print("v2.4.43 TELEMETRI TAMPONU SINAVI")
    print("=" * 68)

    # ==============================================================
    print("\n[1] BAYAT ACIK DOSYA: aktarim listesinden cikarilmali")
    # ==============================================================
    dizin = tempfile.mkdtemp(prefix="tt43_")
    try:
        t, kayitlar = tampon_kur(dizin)

        # Gecmis bir dakikaya 17 ornek yaz (kullanici logundaki sayi)
        gecmis = time.time() - 300          # 5 dakika once
        for i in range(17):
            t.ekle(ornek(i, gecmis + i * 0.1), simdi=gecmis)

        acik_yol = os.path.abspath(t._dosya_yolu)
        olc("Dosya yazma sonrasi ACIK tutuluyor",
            t._dosya is not None,
            "acik: " + os.path.basename(acik_yol))

        # Telemetri akisi DURDU: `ekle` bir daha cagrilmiyor.
        # Simdi aktarim turu geliyor (dakika ilerledi).
        simdi = time.time()
        bekleyen = t.bekleyen_dosyalar(simdi)

        # DUZELTME: bayat acik dosya kapatilmali, sonra aktarilabilir olmali
        olc("Bayat acik dosya KAPATILDI",
            t._dosya is None,
            "kapandi" if t._dosya is None else "HALA ACIK")
        olc("Kapatildiktan sonra aktarim listesine girdi",
            os.path.basename(acik_yol) in bekleyen,
            "bekleyen=%r" % bekleyen)

        # Windows taklidi: dosya HALA acik olsaydi ne olurdu?
        yazilan_turlar = []

        def yazici(satirlar):
            yazilan_turlar.append(len(satirlar))
            return len(satirlar)

        ozet = t.aktar(yazici, simdi=simdi)
        olc("Aktarim basarili (dosya kapali oldugu icin)",
            ozet["satir"] == 17 and ozet["hata"] == 0,
            "satir=%d hata=%d" % (ozet["satir"], ozet["hata"]))
        olc("Dosya .aktarildi olarak isaretlendi",
            os.path.exists(acik_yol + tt.AKTARILDI_UZANTI),
            "isaret var" if os.path.exists(acik_yol + tt.AKTARILDI_UZANTI)
            else "ISARET YOK")

        # Ikinci tur: ayni dosya TEKRAR aktarilmamali
        ozet2 = t.aktar(yazici, simdi=simdi + 60)
        olc("Ikinci turda TEKRAR aktarilmadi",
            ozet2["satir"] == 0,
            "ikinci tur satir=%d" % ozet2["satir"])
        olc("Veritabanina toplam 17 satir yazildi (mukerrer YOK)",
            sum(yazilan_turlar) == 17,
            "toplam yazilan=%d, tur sayisi=%d"
            % (sum(yazilan_turlar), len(yazilan_turlar)))
    finally:
        shutil.rmtree(dizin, ignore_errors=True)

    # ==============================================================
    print("\n[2] WINDOWS TAKLIDI: isaretleme basarisizsa dongu OLMAMALI")
    # ==============================================================
    dizin = tempfile.mkdtemp(prefix="tt43w_")
    try:
        t, kayitlar = tampon_kur(dizin)
        gecmis = time.time() - 300
        for i in range(17):
            t.ekle(ornek(i, gecmis + i * 0.1), simdi=gecmis)
        hedef = os.path.abspath(t._dosya_yolu)

        yazilan_turlar = []

        def yazici(satirlar):
            yazilan_turlar.append(len(satirlar))
            return len(satirlar)

        # os.replace HER ZAMAN WinError 32 verecek (dosya acik gibi)
        with WindowsTaklidi({hedef}) as wt:
            turlar = []
            for tur in range(8):
                ozet = t.aktar(yazici, simdi=time.time() + tur * 60)
                turlar.append(ozet["satir"])

        olc("Isaretleme engellendi (Windows taklidi calisti)",
            wt.engellenen > 0,
            "engellenen replace=%d" % wt.engellenen)

        # DUZELTME: hicbir turda "aktarildi" SAYILMAMALI
        olc("Hicbir turda aktarim SAYILMADI",
            all(s == 0 for s in turlar),
            "tur bazinda sayilan satir=%r" % turlar)

        # KRITIK: MAKS_DENEME'den fazla DB yazmasi OLMAMALI
        olc("DB yazma denemesi MAKS_DENEME ile sinirli (sonsuz dongu YOK)",
            len(yazilan_turlar) <= tt.MAKS_DENEME,
            "DB yazma turu=%d, MAKS_DENEME=%d"
            % (len(yazilan_turlar), tt.MAKS_DENEME))

        olc("Dosya karantinaya alindi",
            t.sayac["karantina"] >= 1,
            "karantina=%d" % t.sayac["karantina"])

        olc("Dosya KORUNDU (veri kaybi yok)",
            os.path.exists(hedef),
            "dosya var" if os.path.exists(hedef) else "DOSYA KAYIP")

        karantina_log = [m for tur, m in kayitlar
                         if "karantinaya alindi" in m]
        olc("Karantina nedeni loglandi",
            len(karantina_log) >= 1,
            karantina_log[0][:70] if karantina_log else "log YOK")
    finally:
        shutil.rmtree(dizin, ignore_errors=True)

    # ==============================================================
    print("\n[3] ACIK DOSYAYA DOKUNULMUYOR: gecerli dakika korunmali")
    # ==============================================================
    dizin = tempfile.mkdtemp(prefix="tt43c_")
    try:
        t, kayitlar = tampon_kur(dizin)
        simdi = time.time()
        for i in range(5):
            t.ekle(ornek(i, simdi + i * 0.1), simdi=simdi)
        acik = os.path.basename(t._dosya_yolu)

        bekleyen = t.bekleyen_dosyalar(simdi)
        olc("Gecerli dakikanin ACIK dosyasi aktarilmiyor",
            acik not in bekleyen,
            "acik=%s bekleyen=%r" % (acik, bekleyen))
        olc("Acik dosya kapatilmadi (yazma surüyor)",
            t._dosya is not None,
            "acik kaldi" if t._dosya is not None else "GEREKSIZ KAPATILDI")

        # Yazma devam edebilmeli
        ok = t.ekle(ornek(99, simdi + 1), simdi=simdi)
        olc("Aktarim turundan sonra yazma devam ediyor", ok is True)
    finally:
        shutil.rmtree(dizin, ignore_errors=True)

    # ==============================================================
    print("\n[4] KAPANIS: kapat() acik dosyayi serbest birakmali")
    # ==============================================================
    dizin = tempfile.mkdtemp(prefix="tt43k_")
    try:
        t, _ = tampon_kur(dizin)
        simdi = time.time()
        t.ekle(ornek(0, simdi), simdi=simdi)
        olc("Kapanis oncesi dosya acik", t._dosya is not None)
        t.kapat()
        olc("kapat() sonrasi dosya serbest", t._dosya is None)
        olc("kapat() sonrasi yol temizlendi", t._dosya_yolu == "")
    finally:
        shutil.rmtree(dizin, ignore_errors=True)

    print("\n" + "=" * 68)
    print("SONUC: %d gecti, %d kaldi (toplam %d)"
          % (GECEN, KALAN, GECEN + KALAN))
    print("=" * 68)
    return 0 if KALAN == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
