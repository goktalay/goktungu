"""v2.4.46: izni dusurulmus SITL kurulumunda gercek sanal dron kalkisi.

Gercek WS sozlesmesi (sunucu.py'den okundu):
  giris        -> giris_sonuc {basarili}
  baglanti_ekle-> hata varsa baglanti_hata, her durumda baglanti_listesi
  baglanti_listesi {baglantilar:[...]}
  dron_listesi {dronlar:[...]}
"""
import os
import json, sys, time
from websockets.sync.client import connect

G = K = 0
def olc(ad, ok, ek=""):
    global G, K
    print("[%s] %s%s" % ("GECTI" if ok else "KALDI", ad,
                         ("  -> " + str(ek)[:220]) if ek else ""))
    if ok: G += 1
    else: K += 1

kutu = []
izin_hatasi = bicim_hatasi = onarim = False
konsol = []

def em(ws, sure):
    global izin_hatasi, bicim_hatasi, onarim
    son = time.time() + sure
    while time.time() < son:
        try:
            m = json.loads(ws.recv(timeout=2))
        except Exception:
            continue
        kutu.append(m)
        # Gercek sozlesme: konsol satirlari AYRI mesaj degil,
        # telemetri yayininin "konsol" dizisi icinde gelir:
        #   {"tip":"telemetri","konsol":[{"kaynak":"SITL","mesaj":"..."}]}
        for sat in (m.get("konsol") or []):
            if not isinstance(sat, dict):
                continue
            s_ = "%s %s" % (sat.get("kaynak") or "", sat.get("mesaj") or "")
            low = s_.lower()
            if s_.strip():
                konsol.append(s_[:200])
            if "permission denied" in low or "errno 13" in low:
                izin_hatasi = True
            if "exec format" in low or "errno 8" in low:
                bicim_hatasi = True
            if "calistirma izni" in low and "onar" in low:
                onarim = True

def son(tip):
    for m in reversed(kutu):
        if m.get("tip") == tip:
            return m
    return None

with connect("ws://127.0.0.1:8765", open_timeout=20, max_size=None) as ws:
    ws.send(json.dumps({"tip": "giris",
                        "eposta": "mkaderoglu@gokkubbetech.com",
                        "sifre": os.environ.get("GOKTUNGU_SINAV_SIFRE", "")}))
    em(ws, 8)
    g = son("giris_sonuc")
    olc("sisteme giris", bool(g and g.get("basarili")), str(g)[:120])

    isim = "IZIN46_%d" % (int(time.time()) % 100000)
    ws.send(json.dumps({"tip": "baglanti_ekle", "isim": isim, "tur": "sanal",
                        "port": "0", "sanal_tip": "multirotor",
                        "lat": 39.925, "lon": 32.836, "adet": 1}))
    em(ws, 6)
    bh = son("baglanti_hata")
    olc("baglanti_hata alinmadi", bh is None, str(bh)[:200])
    # NOT: "baglanti_listele" diye bir komut YOK (sunucu.py'de yok).
    # Liste giris sonrasi kendiliginden gelir ve baglanti_ekle sonrasi
    # _baglanti_listesi_duyur() ile yeniden yayinlanir. Bu yuzden
    # ekleme sonrasi gelen SON baglanti_listesi mesajina bakariz.
    em(ws, 6)
    bl = son("baglanti_listesi")
    kayit = None
    for b in ((bl or {}).get("baglantilar") or []):
        if b.get("isim") == isim:
            kayit = b
    olc("sanal dron kaydi olusturuldu", bool(kayit),
        "listede %d kayit var" % len((bl or {}).get("baglantilar") or []))

    # SITL sureci kayit eklemekle DEGIL, baglanti_baslat komutuyla
    # ayaga kalkar (sunucu.py: _sanal_baslat yalniz baglanti_baslat ve
    # baglanti_guncelle yollarindan cagrilir).
    sysid = None
    if kayit:
        kutu.clear()
        ws.send(json.dumps({"tip": "baglanti_baslat",
                            "id": kayit.get("id")}))
        son_t = time.time() + 180
        while time.time() < son_t and not sysid:
            em(ws, 10)
            # Gercek yapi: {"tip":"telemetri","dronlar":[{...}]}
            for m in [x for x in kutu if x.get("tip") == "telemetri"]:
                for d in (m.get("dronlar") or []):
                    if isinstance(d, dict) and d.get("sysid") and d.get("mod"):
                        sysid = d.get("sysid")
        olc("SITL kalkti ve telemetri geldi", bool(sysid),
            "sysid=%s" % sysid)

olc("izin hatasi ALINMADI (Errno 13)", not izin_hatasi)
olc("bicim hatasi ALINMADI (Errno 8)", not bicim_hatasi)
olc("izin onarimi konsolda bildirildi", onarim,
    "konsol son 5: %s" % konsol[-5:])

print()
print("SONUC: %d GECTI / %d KALDI" % (G, K))
sys.exit(0 if K == 0 else 1)
