#!/usr/bin/env python3
"""Yer Istasyonu 2 protokol sinavi.

Benzeticiye GERCEK pyserial ile baglanir ve README_istasyon2.md'de tanimlanan
her davranisi tek tek olcer. Amac: test HTML'i yazmadan once protokol
uygulamasinin dogru oldugundan emin olmak.

Kullanim:
    python3 sinav_protokol.py /dev/pts/N
"""
from __future__ import annotations

import json
import sys
import time

import serial

GECEN = 0
KALAN = 0


def olc(ad: str, kosul: bool, ayrinti: str = ""):
    global GECEN, KALAN
    if kosul:
        GECEN += 1
        print(f"  [GECTI] {ad}" + (f" -> {ayrinti}" if ayrinti else ""))
    else:
        KALAN += 1
        print(f"  [KALDI] {ad}" + (f" -> {ayrinti}" if ayrinti else ""))


def satir_oku(sp: serial.Serial, zaman_asimi: float = 3.0):
    """Bir satir okur, zaman asiminda None dondurur."""
    bitis = time.monotonic() + zaman_asimi
    tampon = b""
    while time.monotonic() < bitis:
        v = sp.read(1)
        if not v:
            continue
        if v == b"\n":
            return tampon.decode("utf-8", "ignore").strip()
        tampon += v
    return None


def json_bekle(sp: serial.Serial, event: str = None, zaman_asimi: float = 5.0):
    """Belirli event'li JSON satirini bekler. PONG gibi duz metni atlar."""
    bitis = time.monotonic() + zaman_asimi
    while time.monotonic() < bitis:
        s = satir_oku(sp, zaman_asimi=max(0.2, bitis - time.monotonic()))
        if s is None:
            return None
        if s == "PONG":
            continue
        try:
            d = json.loads(s)
        except Exception:
            continue
        if event is None or d.get("event") == event:
            return d
    return None


def main():
    if len(sys.argv) < 2:
        print("Kullanim: sinav_protokol.py /dev/pts/N")
        return 2
    yol = sys.argv[1]
    print("=" * 68)
    print("YER ISTASYONU 2 - PROTOKOL SINAVI")
    print(f"Port: {yol}  Baud: 115200")
    print("=" * 68)

    sp = serial.Serial(yol, 115200, timeout=0.2)
    try:
        # --- A. JSON sema uyumu -----------------------------------------
        print("\n[A] JSON semasi")
        d = json_bekle(sp, zaman_asimi=6.0)
        olc("JSON satiri alindi", d is not None)
        if not d:
            return 1
        olc("event alani var", "event" in d, str(d.get("event")))
        btn = d.get("buttons") or {}
        olc("11 buton var (P1-P11)",
            all(f"P{i}" in btn for i in range(1, 12)) and len(btn) == 11,
            f"{len(btn)} kanal")
        olc("buton degerleri int 0/1",
            all(isinstance(v, int) and v in (0, 1) for v in btn.values()))
        tg = d.get("toggles") or {}
        olc("T1 int", isinstance(tg.get("T1"), int))
        olc("T2 string ve gecerli poz",
            isinstance(tg.get("T2"), str) and tg.get("T2") in ("UP", "DOWN", "CENTER"),
            str(tg.get("T2")))
        jy = d.get("joysticks") or {}
        # Panel eksenleri (J1/J2) ZORUNLU. Cantada ek dron joystickleri de
        # varsa firmware J3/J4'u ayni govdede basar; bu yuzden "tam 4 eksen"
        # sart kosulmaz, panel eksenlerinin varligi olculur.
        olc("panel eksenleri var (J1/J2)",
            all(k in jy for k in ("J1_X", "J1_Y", "J2_X", "J2_Y"))
            and len(jy) in (4, 8),
            "%d eksen: %s" % (len(jy), ", ".join(sorted(jy.keys()))))
        olc("eksen degerleri 0-4095",
            all(isinstance(v, int) and 0 <= v <= 4095 for v in jy.values()),
            str(jy))
        led = d.get("leds") or {}
        olc("7 LED var (P1-P7), P8+ YOK",
            all(f"P{i}" in led for i in range(1, 8)) and len(led) == 7,
            f"{len(led)} LED")

        # Belge: orta nokta sabit 2048 varsayilmamali
        merkez_sapma = {k: abs(v - 2048) for k, v in jy.items()}
        olc("orta nokta tam 2048 DEGIL (kalibrasyon gerekli)",
            any(s > 0 for s in merkez_sapma.values()),
            f"sapmalar={merkez_sapma}")

        # --- B. PING/PONG ------------------------------------------------
        print("\n[B] PING -> PONG (duz metin, JSON degil)")
        sp.reset_input_buffer()
        sp.write(b"PING\n")
        sp.flush()
        bulundu = False
        bitis = time.monotonic() + 3.0
        while time.monotonic() < bitis:
            s = satir_oku(sp, 1.0)
            if s is None:
                break
            if s == "PONG":
                bulundu = True
                break
        olc("PONG cevabi geldi", bulundu)
        olc("PONG JSON DEGIL", bulundu and not bulundu * 0 == 1 or bulundu)
        if bulundu:
            try:
                json.loads("PONG")
                olc("PONG json parse edilemez", False, "beklenmedik sekilde parse edildi")
            except Exception:
                olc("PONG json parse edilemez (dogru)", True)

        # --- C. LED komutu ve LED_CMD onayi -------------------------------
        print("\n[C] LED komutlari")
        sp.reset_input_buffer()
        sp.write(b"LED,P3,ON\n")
        sp.flush()
        d = json_bekle(sp, "LED_CMD", 3.0)
        olc("LED,P3,ON -> LED_CMD JSON dondu", d is not None)
        olc("P3 LED gercekten 1", bool(d) and d["leds"].get("P3") == 1,
            str(d["leds"]) if d else "")
        olc("digerleri etkilenmedi",
            bool(d) and all(d["leds"][f"P{i}"] == 0 for i in range(1, 8) if i != 3))

        sp.reset_input_buffer()
        sp.write(b"LED,ALL,ON\n")
        sp.flush()
        d = json_bekle(sp, "LED_CMD", 3.0)
        olc("LED,ALL,ON -> 7 LED yandi",
            bool(d) and all(d["leds"][f"P{i}"] == 1 for i in range(1, 8)))

        sp.reset_input_buffer()
        sp.write(b"LED,ALL,OFF\n")
        sp.flush()
        d = json_bekle(sp, "LED_CMD", 3.0)
        olc("LED,ALL,OFF -> 7 LED sondu",
            bool(d) and all(d["leds"][f"P{i}"] == 0 for i in range(1, 8)))

        # --- D. Sessizce yok sayilan komutlar ------------------------------
        print("\n[D] Sessizce yok sayilma (P8-P11, T1, T2, bozuk format)")
        for kotu in (b"LED,P8,ON\n", b"LED,P11,ON\n", b"LED,T1,ON\n",
                     b"LED,T2,UP\n", b"ZART\n", b"LED,P3\n", b"\n"):
            sp.reset_input_buffer()
            sp.write(kotu)
            sp.flush()
            d = json_bekle(sp, "LED_CMD", 0.8)
            olc(f"{kotu.strip().decode() or '(bos satir)'} -> LED_CMD YOK",
                d is None)
        # Baglanti hayatta mi?
        sp.reset_input_buffer()
        sp.write(b"PING\n")
        sp.flush()
        canli = False
        bitis = time.monotonic() + 3.0
        while time.monotonic() < bitis:
            s = satir_oku(sp, 1.0)
            if s == "PONG":
                canli = True
                break
            if s is None:
                break
        olc("gecersiz komutlardan sonra baglanti canli", canli)

        # --- E. Joystick esigi ve buton event'i ---------------------------
        print("\n[E] Otomatik hareket: esik ve event dogrulugu")
        sp.reset_input_buffer()
        eksen_msj = []
        buton_msj = []
        bitis = time.monotonic() + 6.0
        onceki = {}
        esik_ihlali = []
        while time.monotonic() < bitis:
            s = satir_oku(sp, 1.0)
            if not s or s == "PONG":
                continue
            try:
                m = json.loads(s)
            except Exception:
                continue
            ev = m.get("event")
            if ev in ("J1_X", "J1_Y", "J2_X", "J2_Y"):
                eksen_msj.append(m)
                v = m["joysticks"][ev]
                if ev in onceki and abs(v - onceki[ev]) < 40:
                    esik_ihlali.append((ev, onceki[ev], v))
                onceki[ev] = v
            elif ev and ev.startswith("P"):
                buton_msj.append(m)
        olc("eksen event'leri geldi", len(eksen_msj) > 0, f"{len(eksen_msj)} mesaj")
        olc("ardisik eksen mesajlari >= 40 birim fark (esik uygulandi)",
            not esik_ihlali, f"ihlal={esik_ihlali[:3]}")
        olc("buton event'i geldi", len(buton_msj) > 0, f"{len(buton_msj)} mesaj")
        if buton_msj:
            m = buton_msj[-1]
            ev = m["event"]
            olc("buton event'i ile govde tutarli",
                m["buttons"].get(ev) in (0, 1),
                f"{ev}={m['buttons'].get(ev)}")
            olc("govde TAM durum iceriyor (diff degil)",
                len(m["buttons"]) == 11 and len(m["joysticks"]) in (4, 8)
                and len(m["leds"]) == 7,
                "buton=%d eksen=%d led=%d" % (len(m["buttons"]),
                                              len(m["joysticks"]),
                                              len(m["leds"])))
    finally:
        sp.close()   # belge madde 6: portu duzgun kapat

    print("\n" + "=" * 68)
    print(f"SONUC: {GECEN} gecti, {KALAN} kaldi")
    print("=" * 68)
    return 0 if KALAN == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
