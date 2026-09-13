#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LED tanisi: durum ozetinde LED alani hangi adla ve hangi degerle donuyor.

Kullanim:
    sudo /opt/goktungu/kopru/.venv/bin/python tani_led.py /tmp/canli2/uc_a
"""

import json
import sys
import time

KURULUM = "/opt/goktungu/kopru"
if KURULUM not in sys.path:
    sys.path.insert(0, KURULUM)


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "/tmp/canli2/uc_a"
    from kopru import uygulama as U

    app = U.Uygulama()
    ey = app._ajan_islevleri()

    app.servisler.durdur("gcsdual")
    time.sleep(1)
    app.servisler.baslat("gcsdual")
    time.sleep(5)

    d = ey["gcsdual_baglan"]({"port": port})
    print("baglan:", d.get("tamam"), d.get("hata"))
    time.sleep(4)

    d = ey["gcsdual_durum"](None)
    print("\n--- LED ONCESI ---")
    print("ust duzey anahtarlar:", sorted(d.keys()))
    for ad in ("leds", "led", "ledler"):
        if ad in d:
            print("  %-8s = %s" % (ad, d.get(ad)))
    if isinstance(d.get("durum"), dict):
        print("  durum.leds =", (d["durum"] or {}).get("leds"))

    print("\n--- LED P4 ON gonderiliyor ---")
    r = ey["gcsdual_led"]({"kanal": "P4", "acik": True})
    print("led yaniti:", json.dumps(r, ensure_ascii=False)[:200])

    for bekle in (0.5, 1.5, 3.0, 5.0):
        time.sleep(bekle if bekle == 0.5 else 1.0)
        d = ey["gcsdual_durum"](None)
        leds = d.get("leds") or d.get("led") or {}
        ic = (d.get("durum") or {}).get("leds") if isinstance(
            d.get("durum"), dict) else None
        print("  t=%4.1fs  leds.P4=%s   durum.leds.P4=%s" % (
            bekle, leds.get("P4"), (ic or {}).get("P4") if ic else None))

    ey["gcsdual_kes"](None)
    app.servisler.durdur("gcsdual")
    return 0


if __name__ == "__main__":
    sys.exit(main())
