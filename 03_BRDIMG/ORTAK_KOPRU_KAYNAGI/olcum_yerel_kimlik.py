#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""Yerel istekte kayitli kurulumun kimligi gorunuyor mu?

Amac: guvenlik degisikliginin (anonim + agdan gelen istekte kimlik
maskeleme) YEREL istekleri kisitlamadigini kanitlamak.

sinav_panel.py satir 107 "kurulum kimligi gorunur" olcumu bu makinede
kaliyordu. Iki olasilik vardi:
  (a) guvenlik degisikligi yerel istekleri de kisitliyor  -> GERCEK KUSUR
  (b) bu makinedeki kopru merkeze kayitli degil           -> ORTAM KOSULU

Bu olcum kayitli bir kurulumu taklit edip (a) mi (b) mi oldugunu
kesinlestirir.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

KOK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KOK)

_gecti = 0
_kaldi = 0


def bak(ad: str, kosul: bool, ek: object = "") -> bool:
    global _gecti, _kaldi
    if kosul:
        _gecti += 1
        print("  [OK] %s %s" % (ad, ek))
    else:
        _kaldi += 1
        print("  [XX] %s %s" % (ad, ek))
    return bool(kosul)


def bos_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def istek(taban: str, yol: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(taban + yol, timeout=15) as y:
            return y.status, json.loads(y.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"hata": str(e)}


def main() -> int:
    veri = tempfile.mkdtemp(prefix="olcum_kimlik_")
    os.environ["GOKTUNGU_KOPRU_VERI"] = veri
    os.environ["GOKTUNGU_KOPRU_VERI_DIZIN"] = veri

    from kopru import ayar as ayar_mod

    # Kayitli bir kurulumu taklit et: kimlik dosyasini yaz.
    kimlik = {
        "kurulum_uid": "OLCUM-UID-1234",
        "gizli": "gizli-deger-sizmamali",
        "ornek_id": 77,
        "ad": "Olcum Kullanici",
        "firma_id": 5,
        "firma_kisa_ad": "OLCUMFIRMA",
        "eposta": "olcum@ornek.local",
    }
    yol = os.path.join(veri, "kimlik.json")
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(kimlik, f)

    print("[1] Kimlik dosyasi okunuyor mu")
    try:
        k = ayar_mod.kimlik_oku()
    except Exception as e:
        k = {}
        print("  (kimlik_oku hata: %s)" % e)
    bak("kurulum_uid okundu", k.get("kurulum_uid") == "OLCUM-UID-1234",
        k.get("kurulum_uid"))

    from kopru import uygulama as uyg_mod
    from kopru import panel as panel_mod

    port = bos_port()
    u = uyg_mod.Uygulama()
    p = panel_mod.Panel(u, port=port, arayuz="0.0.0.0")
    p.baslat()
    time.sleep(1.5)

    ip = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    try:
        print("\n[2] YEREL istek (127.0.0.1) — kimlik GORUNMELI")
        kod, d = istek("http://127.0.0.1:%d" % port, "/api/durum")
        bak("durum ucu 200", kod == 200, kod)
        km = d.get("kimlik") or {}
        bak("kurulum_uid gorunur (yerel)",
            km.get("kurulum_uid") == "OLCUM-UID-1234", km.get("kurulum_uid"))
        bak("ad gorunur (yerel)", km.get("ad") == "Olcum Kullanici",
            km.get("ad"))
        bak("firma_kisa_ad gorunur (yerel)",
            km.get("firma_kisa_ad") == "OLCUMFIRMA", km.get("firma_kisa_ad"))
        bak("gizli deger SIZMIYOR (yerel)",
            "gizli-deger-sizmamali" not in json.dumps(d))
        bak("gizli_var bildirilir", km.get("gizli_var") is True,
            km.get("gizli_var"))

        if ip:
            print("\n[3] AGDAN istek (%s) — kimlik MASKELENMELI" % ip)
            kod, d2 = istek("http://%s:%d" % (ip, port), "/api/durum")
            bak("durum ucu 200 (agdan)", kod == 200, kod)
            km2 = d2.get("kimlik") or {}
            bak("kurulum_uid SIZMIYOR (agdan)",
                not km2.get("kurulum_uid"), repr(km2.get("kurulum_uid")))
            bak("eposta SIZMIYOR (agdan)",
                "olcum@ornek.local" not in json.dumps(d2))
            bak("firma_kisa_ad SIZMIYOR (agdan)",
                "OLCUMFIRMA" not in json.dumps(d2))
            bak("gizli deger SIZMIYOR (agdan)",
                "gizli-deger-sizmamali" not in json.dumps(d2))
            bak("gizli_var yine bildirilir (giris ekrani icin)",
                km2.get("gizli_var") is True, km2.get("gizli_var"))
        else:
            print("\n[3] LAN IP bulunamadi, agdan olcum atlandi")
    finally:
        try:
            p.durdur()
        except Exception:
            pass
        shutil.rmtree(veri, ignore_errors=True)

    print("\nSONUC: %d gecti, %d kaldi" % (_gecti, _kaldi))
    return 0 if _kaldi == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
