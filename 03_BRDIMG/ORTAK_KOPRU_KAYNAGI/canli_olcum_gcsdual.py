#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KURULU kopru uzerinde GCCDUAL eylemlerinin CANLI olcumu.

Kaynak agacini DEGIL, `/opt/goktungu/kopru` altina kurulmus paketi olcer.
Sanal canta (`canli_canta.py` + socat) gercek seri port gibi davranir.

Kullanim (kurulu koprunun venv'i ile, root):
    sudo /opt/goktungu/kopru/.venv/bin/python canli_olcum_gcsdual.py /tmp/canli2/uc_a \
        --gunluk /tmp/canli2/canta.log
"""

import argparse
import os
import sys
import time

KURULUM = "/opt/goktungu/kopru"
if KURULUM not in sys.path:
    sys.path.insert(0, KURULUM)

GECTI = 0
KALDI = 0


def olc(baslik, kosul, ayrinti=""):
    global GECTI, KALDI
    if kosul:
        GECTI += 1
        print("  [GECTI] %s" % baslik)
    else:
        KALDI += 1
        print("  [KALDI] %s%s" % (baslik, ("  -> " + str(ayrinti)) if ayrinti else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port", help="sanal cantanin KOPRU tarafi ucu")
    ap.add_argument("--gunluk", default="", help="canta gunluk dosyasi")
    a = ap.parse_args()

    from kopru import uygulama as U

    app = U.Uygulama()
    ey = app._ajan_islevleri()

    def gunluk_oku():
        if not a.gunluk or not os.path.exists(a.gunluk):
            return ""
        try:
            with open(a.gunluk, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception:
            return ""

    print("=" * 66)
    print(" CANLI OLCUM — KURULU KOPRU (%s)" % KURULUM)
    print("=" * 66)

    # ---------------------------------------------------------------
    print("\n[1] Servis KAPALIYKEN panel ne gorur")
    app.servisler.durdur("gcsdual")
    time.sleep(1.5)
    d = ey["gcsdual_durum"](None)
    olc("kapali servis basarili DONMEZ", d.get("tamam") is False, d)
    h = str(d.get("hata") or "")
    olc("hata metni servisi adiyla soyluyor", "GroundGCC" in h, h)
    olc("hata metni ne yapilacagini soyluyor",
        "baslat" in h.lower(), h)

    # Port listesi de ayni acik hatayi vermeli (sessiz bos liste DEGIL)
    d = ey["gcsdual_portlar"]({"tumu": True})
    olc("servis kapaliyken port listesi sessiz bos DONMEZ",
        d.get("tamam") is False and bool(d.get("hata")), d)

    # ---------------------------------------------------------------
    print("\n[2] Servisi baslat")
    t, hata = app.servisler.baslat("gcsdual")
    olc("gcsdual servisi basladi", t is True, hata)
    time.sleep(5)
    dl = [s for s in app.servisler.durum() if s.get("ad") == "gcsdual"]
    olc("servis durum olcumunde CALISIYOR",
        bool(dl) and dl[0].get("calisiyor") is True, dl)

    # ---------------------------------------------------------------
    print("\n[3] Port envanteri SAHA makinesinden")
    d = ey["gcsdual_portlar"]({"tumu": True})
    olc("port listesi basarili", d.get("tamam") is True, d.get("hata"))
    portlar = d.get("portlar") or []
    olc("port listesi bos degil", len(portlar) > 0, len(portlar))
    ilk = portlar[0] if portlar else {}
    olc("port kaydinda aygit alani var",
        isinstance(ilk, dict) and bool(ilk.get("aygit") or ilk.get("port")), ilk)

    # ---------------------------------------------------------------
    print("\n[4] Sanal cantaya BAGLAN")
    d = ey["gcsdual_baglan"]({"port": a.port})
    olc("baglan komutu basarili", d.get("tamam") is True, d.get("hata"))
    time.sleep(4)
    d = ey["gcsdual_durum"](None)
    olc("durum: BAGLI", d.get("bagli") is True, d)
    olc("durum: dogru port", str(d.get("port")) == a.port, d.get("port"))

    # ---------------------------------------------------------------
    print("\n[5] Canli veri akisi ve sayaclar")
    s1 = dict(d.get("sayac") or {})
    time.sleep(3)
    d = ey["gcsdual_durum"](None)
    s2 = dict(d.get("sayac") or {})
    olc("rx sayaci ARTIYOR (canta verisi geliyor)",
        int(s2.get("rx", 0)) > int(s1.get("rx", 0)), (s1, s2))
    # GERCEK SOZLESME (js/istasyon2.js 676-678): buton/kol/eksen
    # tablolari `durum` sarmalayicisinin ICINDE tasinir.
    ic = d.get("durum") if isinstance(d.get("durum"), dict) else {}
    btn = (ic or {}).get("buttons") or d.get("buttons") or {}
    olc("buton tablosu geldi", isinstance(btn, dict) and len(btn) > 0,
        list(btn)[:4])
    olc("11 buton tam geldi (P1..P11)", len(btn) == 11, sorted(btn))
    # GERCEK PROTOKOL: eksenler `joysticks` alanindadir (`axes` DEGIL).
    eks = (ic or {}).get("joysticks") or d.get("joysticks") or {}
    kol = (ic or {}).get("toggles") or {}
    olc("kol tablosu geldi (T1/T2)", "T1" in kol and "T2" in kol, kol)
    olc("T2 STRING bicimde", isinstance(kol.get("T2"), str), kol.get("T2"))
    olc("eksen adlari J1_X bicimi", "J1_X" in eks, list(eks)[:6])
    olc("ek dron cubuklari saptandi (J3/J4)",
        "J3_X" in eks and "J4_X" in eks, list(eks))
    nrm = d.get("normalize") or {}
    olc("normalize edilmis eksen degeri var", "J1_X" in nrm, list(nrm)[:4])
    olc("normalize deger araligi -1..1",
        all(-1.0001 <= float(v) <= 1.0001 for v in nrm.values()), nrm)

    # ---------------------------------------------------------------
    print("\n[6] Canlilik: cantanin PONG yaniti olculuyor")
    # PING_ARALIK=5s -> en az bir yoklama turu bekle
    time.sleep(7)
    d = ey["gcsdual_durum"](None)
    s3 = dict(d.get("sayac") or {})
    log = gunluk_oku()
    olc("canta PONG gonderdi (gunluk kaniti)",
        "PONG" in log, log[-200:])
    olc("pong sayaci ARTTI", int(s3.get("pong", 0)) > 0, s3)
    olc("gecikme olculdu (>=0 ms, alan var)",
        d.get("gecikme_ms") is not None, d.get("gecikme_ms"))
    olc("baglanti PONG sonrasi hala BAGLI", d.get("bagli") is True, d)

    # ---------------------------------------------------------------
    print("\n[7] LED komutu cantaya ULASIYOR")
    onceki = gunluk_oku()
    d = ey["gcsdual_led"]({"kanal": "P4", "acik": True})
    olc("led komutu basarili", d.get("tamam") is True, d.get("hata"))
    time.sleep(2)
    yeni = gunluk_oku()[len(onceki):]
    # GERCEK PROTOKOL: `LED,P4,ON` (virgullu), `LED P4 1` DEGIL.
    olc("canta LED satirini ALDI", "LED,P4" in yeni, yeni[:200])
    olc("LED ON gonderildi", "LED,P4,ON" in yeni, yeni[:200])
    time.sleep(1.5)
    d = ey["gcsdual_durum"](None)
    # GERCEK ARAYUZ YOLU (js/istasyon2.js satir 676-679):
    #   const dr = d.durum || {};  const led = dr.leds || {};
    # LED'ler `durum` sarmalayicisinin ICINDEDIR, ust duzeyde DEGIL.
    ic = d.get("durum") if isinstance(d.get("durum"), dict) else {}
    ledd = (ic or {}).get("leds") or {}
    olc("panel LED durumunu izliyor (durum.leds)",
        int(ledd.get("P4", 0)) == 1, ledd)
    olc("LED tablosu 7 kanal (P1..P7)", len(ledd) == 7, sorted(ledd))
    olc("diger LED'ler etkilenmedi",
        all(int(ledd.get(p, 0)) == 0 for p in ledd if p != "P4"), ledd)

    # LED kapat
    onceki = gunluk_oku()
    ey["gcsdual_led"]({"kanal": "P4", "acik": False})
    time.sleep(2)
    yeni = gunluk_oku()[len(onceki):]
    olc("LED kapatma cantaya ulasti", "LED,P4,OFF" in yeni, yeni[:200])
    time.sleep(1.5)
    d = ey["gcsdual_durum"](None)
    ic = d.get("durum") if isinstance(d.get("durum"), dict) else {}
    ledd = (ic or {}).get("leds") or {}
    olc("LED kapatma panele yansidi", int(ledd.get("P4", 0)) == 0, ledd)

    # ALL kanali: firmware `LED,ALL,ON` kabul eder.
    onceki = gunluk_oku()
    ey["gcsdual_led"]({"kanal": "ALL", "acik": True})
    time.sleep(2)
    yeni = gunluk_oku()[len(onceki):]
    olc("ALL kanali cantaya ulasti", "LED,ALL,ON" in yeni, yeni[:200])
    d = ey["gcsdual_durum"](None)
    ic = d.get("durum") if isinstance(d.get("durum"), dict) else {}
    ledd = (ic or {}).get("leds") or {}
    olc("ALL ile 7 LED birlikte yandi",
        all(int(ledd.get("P%d" % i, 0)) == 1 for i in range(1, 8)), ledd)
    ey["gcsdual_led"]({"kanal": "ALL", "acik": False})
    time.sleep(2)

    # ---------------------------------------------------------------
    print("\n[8] Kalibrasyon saha makinesinde uygulaniyor")
    d = ey["gcsdual_kalibre"]({"sil": False})
    olc("kalibre komutu basarili", d.get("tamam") is True, d.get("hata"))
    time.sleep(1)
    d = ey["gcsdual_durum"](None)
    olc("kalibrasyon durumu bildiriliyor",
        d.get("kalibre") is not None, d.get("kalibre"))

    # ---------------------------------------------------------------
    print("\n[9] KES komutu")
    d = ey["gcsdual_kes"](None)
    olc("kes komutu basarili", d.get("tamam") is True, d.get("hata"))
    time.sleep(2)
    d = ey["gcsdual_durum"](None)
    olc("kes sonrasi BAGLI DEGIL", d.get("bagli") is False, d)
    time.sleep(4)
    d = ey["gcsdual_durum"](None)
    olc("KES kalici: kendiliginden geri baglanmiyor",
        d.get("bagli") is False, d)

    # ---------------------------------------------------------------
    print("\n[10] Var olmayan port: acik hata")
    d = ey["gcsdual_baglan"]({"port": "/dev/yok_boyle_bir_port"})
    olc("var olmayan port basarisiz DONER",
        d.get("tamam") is False or d.get("bagli") is False, d)

    app.servisler.durdur("gcsdual")

    print("\n" + "=" * 66)
    print(" SONUC: %d gecti / %d kaldi" % (GECTI, KALDI))
    print("=" * 66)
    return 1 if KALDI else 0


if __name__ == "__main__":
    sys.exit(main())
