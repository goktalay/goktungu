# -*- coding: utf-8 -*-
"""v2.4.53 — köprü ajanı canlı denemesi (gerçek merkeze bağlanır).

`veri/kopru.json` içindeki kurulum kimliğiyle merkeze ters WSS bağlantısı
kurar, nabız gönderir ve merkezin sorduğu eylemlere sahte GCS verisiyle
yanıt verir. Merkez admin panelinde bu kurulumun ÇEVRIMIÇI görünmesi ve
`acik_sunucular` listesine düşmesi beklenir.

Çalıştırma:

    python3 dene_kopru_2453.py [saniye]
"""
import os
import sys
import time

KOK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KOK)
os.chdir(KOK)

from goktungu import kopru as K       # noqa: E402
from goktungu import merkez as M      # noqa: E402


def main():
    sure = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    kimlik = M.kimlik_oku()
    if not (kimlik.get("kurulum_uid") and kimlik.get("gizli")):
        print("HATA: veri/kopru.json içinde kurulum kimliği yok. "
              "Önce dene_kayit_2453.py çalıştırın.")
        return 1
    print(f"Kurulum: {kimlik.get('ad')} (ornek {kimlik.get('ornek_id')})")
    print(f"Adres  : {kimlik.get('merkez_adres')}")

    ajan = K.KopruAjani(
        kimlik,
        islevler={
            "dron_sayisi": lambda v: 2,
            "dron_liste": lambda v: {"dronlar": [
                {"sysid": 1, "ad": "SITL-1", "tip": "MULTIROTOR",
                 "mod": "GUIDED", "armed": False, "cevrimici": True,
                 "lat": 39.9334, "lon": 32.8597, "alt_rel": 0.0},
                {"sysid": 2, "ad": "SITL-2", "tip": "SABIT_KANAT",
                 "mod": "AUTO", "armed": True, "cevrimici": True,
                 "lat": 39.95, "lon": 32.86, "alt_rel": 120.0},
            ], "adet": 2},
            "port_liste": lambda v: {"portlar": [
                {"port": "/dev/ttyACM0", "aciklama": "GCCDUAL"},
                {"port": "/dev/ttyUSB0", "aciklama": "RFD900X"}], "adet": 2},
            "servis_durum": lambda v: {"destekli": True, "durum": "aktif",
                                       "servis": "goktungu"},
            "sistem_bilgi": lambda v: {"surum": kimlik.get("surum"),
                                       "platform": kimlik.get("platform"),
                                       "makine_adi": kimlik.get("makine_adi")},
            "yetenekler": lambda v: {"dron": True, "video": True,
                                     "ai": False, "radar": True,
                                     "sitl": True, "servis": True},
            "durum": lambda v: {"istemci_sayisi": 1},
        },
        gunluk=lambda etiket, metin, sev="bilgi": print(
            f"[{etiket}/{sev}] {metin}"))

    basarili, hata = ajan.baslat()
    if not basarili:
        print(f"BASLATILAMADI: {hata}")
        return 1
    bas = time.time()
    try:
        while time.time() - bas < sure:
            time.sleep(3)
            d = ajan.durum()
            print(f"  bagli={d['bagli']} ornek={d['ornek_id']} "
                  f"kanal={d['kanal']} deneme={d['deneme']} "
                  f"hata={d['son_hata']!r}")
            if d["bagli"] and time.time() - bas > 8:
                # Bağlantı kurulduysa merkezden sorgu yapılabilmesi için
                # yeterli süre bekleyip çıkılır (dış betik sorgular).
                pass
    except KeyboardInterrupt:
        pass
    finally:
        ajan.durdur()
    d = ajan.durum()
    print("\nSONUC:", "GECTI" if d["ornek_id"] else "BASARISIZ")
    return 0 if d["ornek_id"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
