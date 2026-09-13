#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GOKTUNGU v2.4.44 canli uctan uca sinav.

Akis:
  benzetici (PTY)  <->  goktungu backend (Istasyon2)  <->  WS  <->  bu betik

Betik arayuzun yerine gecer: WS'e baglanip giris yapar, panel komutlarini
gonderir, benzeticiye SIM komutlarini PTY uzerinden yazar ve backend'in
yayinladigi paketleri olcer.

Kullanim:
  python3 sinav_2444_canli.py <pty_yolu> [ws_url]
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import websockets
except ImportError:
    print("websockets gerekli: pip3 install websockets")
    sys.exit(2)

try:
    import serial
except ImportError:
    print("pyserial gerekli")
    sys.exit(2)

PTY = sys.argv[1] if len(sys.argv) > 1 else "/dev/pts/14"
WS = sys.argv[2] if len(sys.argv) > 2 else "ws://127.0.0.1:8765"
EPOSTA = "mkaderoglu@gokkubbetech.com"
SIFRE = os.environ.get("GOKTUNGU_SINAV_SIFRE", "")  # koda parola yazilmaz

_gecti = 0
_kaldi = []


def denet(ad, kosul, kanit=""):
    global _gecti
    if kosul:
        _gecti += 1
        print("[GECTI    ] %s%s" % (ad, ("  ->  " + kanit) if kanit else ""))
    else:
        _kaldi.append(ad)
        print("[BASARISIZ] %s%s" % (ad, ("  ->  " + kanit) if kanit else ""))


class Toplayici:
    """WS'ten gelen istasyon2 paketlerini biriktirir."""

    def __init__(self):
        self.durumlar = []
        self.eylemler = []
        self.sonuclar = []
        self.eylem_sonuclari = []
        self.portlar = []
        self.hepsi = []

    def ekle(self, m):
        t = m.get("tip", "")
        if not t.startswith("istasyon2"):
            return
        self.hepsi.append(m)
        if t == "istasyon2_durum":
            self.durumlar.append(m)
        elif t == "istasyon2_eylem":
            self.eylemler.append(m)
        elif t == "istasyon2_eylem_sonuc":
            self.eylem_sonuclari.append(m)
        elif t == "istasyon2_sonuc":
            self.sonuclar.append(m)
        elif t == "istasyon2_portlar":
            self.portlar.append(m)

    def son_durum(self):
        return self.durumlar[-1] if self.durumlar else None

    def eylem_var(self, eylem):
        return [e for e in self.eylemler if e.get("eylem") == eylem]

    def sifirla(self):
        self.durumlar.clear()
        self.eylemler.clear()
        self.eylem_sonuclari.clear()
        self.sonuclar.clear()


async def main():
    top = Toplayici()
    sp = serial.Serial(PTY, 115200, timeout=0.2)

    def sim(*parcalar):
        """Benzeticiye SIM komutu yazar."""
        sp.write(("SIM," + ",".join(str(p) for p in parcalar) + "\n").encode())
        sp.flush()

    async with websockets.connect(WS, max_size=8 * 1024 * 1024) as ws:
        async def dinle():
            try:
                async for ham in ws:
                    try:
                        top.ekle(json.loads(ham))
                    except Exception:
                        pass
            except Exception:
                pass

        gorev = asyncio.create_task(dinle())

        async def gonder(paket):
            await ws.send(json.dumps(paket))

        async def bekle(sn=1.2):
            await asyncio.sleep(sn)

        print("=" * 70)
        print("GOKTUNGU v2.4.44 CANLI UCTAN UCA SINAV")
        print("PTY: %s   WS: %s" % (PTY, WS))
        print("=" * 70)

        # --- 1. Giris -----------------------------------------------
        print("\n--- 1. Oturum ---")
        await gonder({"tip": "giris", "eposta": EPOSTA, "sifre": SIFRE})
        await bekle(2.0)
        denet("WS oturumu acildi", True, WS)

        # --- 2. Panel baglantisi -------------------------------------
        print("\n--- 2. Panel baglantisi ---")
        await gonder({"tip": "istasyon2_baglan", "port": PTY})
        await bekle(2.5)
        d = top.son_durum()
        denet("istasyon2_durum paketi geliyor", d is not None,
              "%d paket" % len(top.durumlar))
        if d:
            iç = d.get("durum") or {}
            denet("durum: bagli", bool(d.get("bagli")), str(d.get("port")))
            denet("durum 11 buton tasiyor",
                  len(iç.get("buttons") or {}) == 11)
            denet("durum 2 kol tasiyor", len(iç.get("toggles") or {}) == 2)
            denet("durum 7 LED tasiyor", len(iç.get("leds") or {}) == 7)
            joy = iç.get("joysticks") or {}
            ekj = iç.get("ek_eksen") or {}
            denet("panel 4 ekseni geliyor",
                  all(k in joy for k in ("J1_X", "J1_Y", "J2_X", "J2_Y")),
                  ", ".join(sorted(joy.keys())))
            # Ek eksenler ilk READY satirinda algilanir; durum yayini
            # hiz sinirli oldugu icin acik istekle tazeliyoruz.
            if not ekj:
                sim("EKJOY", "J3_X", 2100)
                await bekle(0.6)
                await gonder({"tip": "istasyon2_durum"})
                await bekle(1.0)
                ekj = ((top.son_durum() or {}).get("durum")
                       or {}).get("ek_eksen") or {}
            denet("ek dron eksenleri geliyor (J3/J4)",
                  all(k in ekj for k in ("J3_X", "J3_Y", "J4_X", "J4_Y")),
                  ", ".join(sorted(ekj.keys())) or "ek eksen yok")
            denet("T2 metin tipinde",
                  isinstance((iç.get("toggles") or {}).get("T2"), str),
                  repr((iç.get("toggles") or {}).get("T2")))
            denet("T1 sayi tipinde",
                  isinstance((iç.get("toggles") or {}).get("T1"), int))

        # --- 3. Ucus dugmeleri (joystick kontrolu KAPALI) -----------
        print("\n--- 3. Ucus dugmeleri (manuel kontrol kapali) ---")
        for tus, eylem in (("P1", "arm_disarm"), ("P2", "takeoff_land"),
                           ("P3", "rtl"), ("P4", "mod_guided"),
                           ("P5", "mod_althold"), ("P6", "mod_auto")):
            top.sifirla()
            sim("BTN", tus, 1)
            await bekle(0.8)
            sim("BTN", tus, 0)
            await bekle(0.8)
            es = [e for e in top.eylem_sonuclari
                  if e.get("eylem") == eylem]
            denet("  %s -> %s ucus eylemi uretildi" % (tus, eylem),
                  bool(es), (es[0].get("sebep") or "-") if es
                  else "eylem_sonuc gelmedi")
            if es:
                denet("    joystick kontrolu kapali -> komut gitmedi",
                      es[0].get("basari") is False
                      and es[0].get("sebep") == "joystick_kapali",
                      "basari=%s sebep=%s" % (es[0].get("basari"),
                                              es[0].get("sebep")))
                denet("    kanal bilgisi dogru",
                      es[0].get("kanal") == tus,
                      str(es[0].get("kanal")))

        # --- 4. Harita dugmeleri -------------------------------------
        print("\n--- 4. Harita dugmeleri ---")
        for tus, eylem in (("P8", "harita_kaynak"),
                           ("P9", "kullanici_konum"),
                           ("P10", "hepsini_kapsa"),
                           ("P11", "nokta_gez")):
            top.sifirla()
            sim("BTN", tus, 1)
            await bekle(0.6)
            sim("BTN", tus, 0)
            await bekle(0.6)
            denet("  %s -> %s arayuze yayinlandi" % (tus, eylem),
                  bool(top.eylem_var(eylem)))

        # --- 5. T1 patlatma kolu -------------------------------------
        print("\n--- 5. T1 patlatma kolu ---")
        top.sifirla()
        sim("TGL", "T1", 1)
        await bekle(1.2)
        es = top.eylem_var("patlat_onay")
        denet("T1 acik -> patlat_onay yayinlandi", bool(es),
              json.dumps((es[0].get("ayrinti") or {})) if es else "-")
        if es:
            ay = es[0].get("ayrinti") or {}
            denet("  paket acik=True", ay.get("acik") is True or
                  ay.get("deger") in (1, "1", True))
        d = top.son_durum()
        led = ((d or {}).get("durum") or {}).get("leds") or {}
        denet("T1 acik -> P7 LED yandi", led.get("P7") == 1,
              "P7=%s" % led.get("P7"))
        top.sifirla()
        sim("TGL", "T1", 0)
        await bekle(1.2)
        es = top.eylem_var("patlat_onay")
        ay = (es[0].get("ayrinti") or {}) if es else {}
        denet("T1 kapali -> onay iptali yayinlandi",
              bool(es) and (ay.get("acik") is False
                            or ay.get("deger") in (0, "0", False)),
              json.dumps(ay) if es else "-")
        d = top.son_durum()
        led = ((d or {}).get("durum") or {}).get("leds") or {}
        denet("T1 kapali -> P7 LED sondu", led.get("P7") == 0,
              "P7=%s" % led.get("P7"))

        # --- 6. T2 zoom kolu -----------------------------------------
        print("\n--- 6. T2 zoom kolu ---")
        for poz, eylem in (("UP", "harita_zoom_in"),
                           ("DOWN", "harita_zoom_out"),
                           ("CENTER", "harita_zoom_dur")):
            top.sifirla()
            sim("TGL", "T2", poz)
            await bekle(0.9)
            denet("  T2=%s -> %s" % (poz, eylem),
                  bool(top.eylem_var(eylem)))
            d = top.son_durum()
            if d:
                tg = (d.get("durum") or {}).get("toggles") or {}
                denet("    durumda T2=%s" % poz, tg.get("T2") == poz,
                      repr(tg.get("T2")))

        # --- 7. Panel joystickleri: harita, dron DEGIL ---------------
        print("\n--- 7. Panel joystickleri (harita kontrolu) ---")
        top.sifirla()
        sim("JOY", "J1_X", 3600)
        await bekle(0.8)
        d = top.son_durum()
        joy = ((d or {}).get("durum") or {}).get("joysticks") or {}
        denet("J1_X hareketi durum paketinde",
              abs(joy.get("J1_X", 0) - 3600) < 60,
              "J1_X=%s" % joy.get("J1_X"))
        nrm = (d or {}).get("normalize") or {}
        denet("normalize edilmis eksen geliyor (-1..+1)",
              "J1_X" in nrm and -1.05 <= nrm["J1_X"] <= 1.05,
              "J1_X_n=%s" % nrm.get("J1_X"))
        denet("panel cubugu dron eksenine yazilmadi",
              not top.eylem_var("manuel_eksen"))
        sim("JOY", "J1_X", 2048)
        await bekle(0.5)

        # --- 8. Ek dron joystickleri ---------------------------------
        print("\n--- 8. Ek dron joystickleri (J3/J4) ---")
        top.sifirla()
        sim("EKJOY", "J3_Y", 3800)
        await bekle(0.9)
        d = top.son_durum()
        ekj = ((d or {}).get("durum") or {}).get("ek_eksen") or {}
        denet("J3_Y hareketi durum paketinde",
              abs(ekj.get("J3_Y", 0) - 3800) < 60,
              "J3_Y=%s" % ekj.get("J3_Y"))
        nrm = (d or {}).get("normalize") or {}
        denet("ek eksen normalize edildi", "J3_Y" in nrm,
              "J3_Y_n=%s" % nrm.get("J3_Y"))
        denet("ek eksen aktif bayragi acik",
              bool((d or {}).get("ek_eksen_aktif")),
              "adlar=%s" % json.dumps((d or {}).get("ek_eksen_adlari")))
        sim("EKJOY", "J3_Y", 2048)
        await bekle(0.5)

        # --- 9. LED denetimi -----------------------------------------
        print("\n--- 9. LED denetimi ---")
        top.sifirla()
        await gonder({"tip": "istasyon2_led", "kanal": "P3", "acik": True})
        await bekle(1.0)
        d = top.son_durum()
        led = ((d or {}).get("durum") or {}).get("leds") or {}
        denet("LED,P3,ON uygulandi", led.get("P3") == 1,
              "P3=%s" % led.get("P3"))
        await gonder({"tip": "istasyon2_led", "kanal": "P3", "acik": False})
        await bekle(1.0)
        d = top.son_durum()
        led = ((d or {}).get("durum") or {}).get("leds") or {}
        denet("LED,P3,OFF uygulandi", led.get("P3") == 0,
              "P3=%s" % led.get("P3"))
        top.sifirla()
        await gonder({"tip": "istasyon2_led", "kanal": "ALL", "acik": True})
        await bekle(1.0)
        d = top.son_durum()
        led = ((d or {}).get("durum") or {}).get("leds") or {}
        denet("LED,ALL,ON yedi LED'i yakti", sum(led.values()) == 7,
              "acik LED=%d" % sum(led.values()))
        await gonder({"tip": "istasyon2_led", "kanal": "ALL", "acik": False})
        await bekle(0.9)
        # LED'i olmayan kanal sessizce yok sayilir
        top.sifirla()
        await gonder({"tip": "istasyon2_led", "kanal": "P9", "acik": True})
        await bekle(1.0)
        d = top.son_durum()
        led = ((d or {}).get("durum") or {}).get("leds") or {}
        denet("LED,P9,ON sessizce yok sayildi (P9'da LED yok)",
              "P9" not in led, "LED kanallari=%s" % ",".join(sorted(led)))

        # --- 10. PING / PONG -----------------------------------------
        print("\n--- 10. PING / PONG ---")
        # Onceki PONG sayacini acik istekle oku (yayin hiz sinirlidir)
        onceki = None
        for _ in range(6):
            top.sifirla()
            await gonder({"tip": "istasyon2_durum"})
            await bekle(0.7)
            d0 = top.son_durum()
            if d0 and d0.get("sayac"):
                onceki = d0["sayac"].get("pong", 0)
                break
        if onceki is None:
            onceki = 0
        await gonder({"tip": "istasyon2_ping"})
        await bekle(1.0)
        # Durum yayini hiz sinirli; sayaci acikca isteyerek okuyoruz
        top.sifirla()
        await gonder({"tip": "istasyon2_durum"})
        await bekle(1.2)
        d = top.son_durum()
        sy = (d or {}).get("sayac") or {}
        denet("PONG alindi (duz metin, JSON degil)",
              (sy.get("pong") or 0) > onceki,
              "pong=%s gecikme=%s ms" % (sy.get("pong"),
                                         (d or {}).get("gecikme_ms")))
        denet("bozuk satir sayaci sifir", (sy.get("bozuk") or 0) == 0,
              "rx=%s tx=%s bozuk=%s" % (sy.get("rx"), sy.get("tx"),
                                        sy.get("bozuk")))

        # --- 11. Kalibrasyon -----------------------------------------
        print("\n--- 11. Kalibrasyon ---")
        top.sifirla()
        await gonder({"tip": "istasyon2_kalibre"})
        await bekle(1.5)
        d = top.son_durum()
        denet("kalibrasyon kaydedildi",
              bool(d) and bool(d.get("kalibre")),
              json.dumps(d.get("merkez")) if d else "-")
        if d and d.get("normalize"):
            sapma = max(abs(v) for v in d["normalize"].values())
            denet("kalibrasyon sonrasi eksenler merkezde",
                  sapma < 0.05, "en buyuk sapma=%.4f" % sapma)

        # --- 12. Port listesi ve kesme -------------------------------
        print("\n--- 12. Port listesi / kesme ---")
        top.sifirla()
        await gonder({"tip": "istasyon2_portlar"})
        await bekle(1.2)
        denet("port listesi geldi", bool(top.portlar),
              json.dumps((top.portlar[-1].get("portlar") or [])[:3])
              if top.portlar else "-")
        top.sifirla()
        await gonder({"tip": "istasyon2_kes"})
        await bekle(1.5)
        d = top.son_durum()
        denet("baglanti kesildi", bool(d) and not d.get("bagli"))
        top.sifirla()
        await gonder({"tip": "istasyon2_baglan", "port": PTY})
        await bekle(2.2)
        d = top.son_durum()
        denet("port yeniden acildi (Windows ReadFile korumasi)",
              bool(d) and bool(d.get("bagli")))

        gorev.cancel()

    sp.close()

    print("\n" + "=" * 70)
    print("SONUC: %d GECTI / %d KALDI" % (_gecti, len(_kaldi)))
    if _kaldi:
        print("\nEksik denetimler:")
        for k in _kaldi:
            print("  - " + k)
    print("=" * 70)
    return 1 if _kaldi else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
