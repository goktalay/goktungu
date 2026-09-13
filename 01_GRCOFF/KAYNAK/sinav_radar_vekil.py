# -*- coding: utf-8 -*-
"""SINAV — MERKEZ RADAR VEKILI.

Kullanici sikayeti:

    "radarda da ayni sorun var, radarin kopru yazilimi calisiyor ama
     sistem radari sunucuda ariyor"

Bu sinav merkez tarafini olcer: vekil kopruden gelen veriyi dogru
uyguluyor mu, SAAT FARKI duzeltmesi calisiyor mu, kopru koptugunda
haritada HAYALET iz kaliyor mu, ve `RadarIstemcisi` yuzu birebir
korunuyor mu (takipci motoru ile angajman ayni uyeleri okur).
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from goktungu.radar_vekil import (            # noqa: E402
    CEKME_ARALIK_SN, KOPMA_TOLERANS_SN, RadarVekili,
)

GECTI = 0
KALDI = 0


def olc(ad, kosul, ayrinti=None):
    global GECTI, KALDI
    if kosul:
        GECTI += 1
        print("  OK    %s" % ad)
    else:
        KALDI += 1
        print("  KALDI %s%s" % (ad, "" if ayrinti is None
                                 else "  -> %r" % (ayrinti,)))


def bolum(ad):
    print("--- %s ---" % ad)


class SahteKonsol:
    def __init__(self):
        self.satirlar = []

    def __call__(self, etiket, mesaj, tur=None):
        self.satirlar.append((etiket, mesaj))


class SahteAyar:
    def __init__(self, veri=None):
        self.veri = veri or {}

    def yukle(self):
        return dict(self.veri)


import threading                            # noqa: E402


def vekil_kur(cek=None, ayar=None):
    return RadarVekili(SahteKonsol(), SahteAyar(ayar or {}),
                       threading.Lock(), cek=cek)


def kopru_paketi(izler=None, durum=None, ayarlar=None):
    return {
        "radar_durum": durum or {
            "durum": "bagli", "ip": "192.168.8.168", "port": 5001,
            "lat": 39.925533, "lon": 32.866287, "hata": "",
        },
        "radar_ayarlar": ayarlar or {
            "frekans": 0, "calisma_modu": "tarama2", "kaynak": "radar",
        },
        "izler": izler if izler is not None else [],
    }


def main():
    print("=" * 70)
    print("SINAV — MERKEZ RADAR VEKILI")
    print("=" * 70)

    # ------------------------------------------------------------------
    bolum("1. RadarIstemcisi yuzu birebir korunuyor")
    v = vekil_kur()
    # sunucu.py + angajman.py bu uyeleri kullanir; biri eksikse merkez
    # kipi ACILISTA coker.
    for uye in ("durum", "radar_ayarlar", "hedefler", "ayar_kuyruk",
                "radar_konum", "baglan", "kes", "ayar_yukle"):
        olc("uye var: %s" % uye, hasattr(v, uye))
    for alan in ("durum", "ip", "port", "hata", "lat", "lon",
                 "son_veri_ani", "veri_hizi", "crc_hata"):
        olc("durum alani var: %s" % alan, alan in v.durum)
    olc("baslangicta iz yok", v.hedefler == {})

    # ------------------------------------------------------------------
    bolum("2. Merkezden yerel TCP baglantisi DENENMEZ")
    # Kok neden buydu: merkez sahadaki 192.168.8.x adresine baglanmaya
    # calisiyordu. Vekil bunu asla yapmamalidir.
    olc("baglan() False doner (yerel deneme yok)",
        v.baglan("192.168.8.168", 5001) is False)
    olc("kes() False doner", v.kes() is False)
    olc("gunluge aciklama yazildi",
        any("kopru" in m.lower() for _, m in v.konsol.satirlar))

    # ------------------------------------------------------------------
    bolum("3. Kopru verisi uygulaniyor")
    izler = [
        {"id": 11, "lat": 39.93, "lon": 32.87, "yas_sn": 0.2,
         "hiz": 12.0, "menzil": 900.0},
        {"id": 12, "lat": 39.94, "lon": 32.88, "yas_sn": 1.0,
         "hiz": 30.0, "menzil": 1500.0},
    ]
    v = vekil_kur(cek=lambda: (kopru_paketi(izler), None))
    v.cek_gerekirse()
    olc("durum kopruden geldi", v.durum.get("durum") == "bagli",
        v.durum.get("durum"))
    olc("radar ip kopruden geldi",
        v.durum.get("ip") == "192.168.8.168", v.durum.get("ip"))
    olc("RTK konumu geldi", v.durum.get("lat") == 39.925533)
    olc("ayarlar geldi",
        v.radar_ayarlar.get("calisma_modu") == "tarama2",
        v.radar_ayarlar.get("calisma_modu"))
    olc("2 iz haritaya girdi", len(v.hedefler) == 2, len(v.hedefler))
    olc("iz kimlikleri korundu", set(v.hedefler) == {11, 12})
    olc("iz alanlari korundu",
        v.hedefler.get(11, {}).get("menzil") == 900.0)

    # ------------------------------------------------------------------
    bolum("4. SAAT FARKI duzeltmesi (kritik)")
    # Kopru izleri KENDI saatiyle damgalar. Saha makinesinin saati
    # merkezden 3 saat ileri olsun: mutlak damga tasinsaydi merkez
    # butun izleri "gelecekten" ya da "cok eski" sayardi.
    simdi = time.time()
    for kid, iz in v.hedefler.items():
        olc("iz %d merkez saatiyle damgalandi" % kid,
            abs(iz["son"] - simdi) < 5.0, iz["son"] - simdi)
    olc("yas_sn farki korundu (11 daha taze)",
        v.hedefler[11]["son"] > v.hedefler[12]["son"])
    olc("yas_sn alani icerde birakilmadi",
        "yas_sn" not in v.hedefler[11])

    # saha saati 3 saat ILERI olsa bile merkez izleri taze gorur
    gelecek = time.time() + 3 * 3600
    izler_ileri = [{"id": 21, "lat": 39.9, "lon": 32.8, "yas_sn": 0.5,
                    "son": gelecek}]
    v2 = vekil_kur(cek=lambda: (kopru_paketi(izler_ileri), None))
    v2.cek_gerekirse()
    iz = v2.hedefler.get(21, {})
    olc("saha saati 3 sa ILERI olsa da iz merkez saatinde",
        iz and abs(iz["son"] - time.time()) < 5.0,
        None if not iz else iz["son"] - time.time())
    # ayni sekilde 3 saat GERI
    gecmis = time.time() - 3 * 3600
    izler_geri = [{"id": 22, "lat": 39.9, "lon": 32.8, "yas_sn": 0.5,
                   "son": gecmis}]
    v3 = vekil_kur(cek=lambda: (kopru_paketi(izler_geri), None))
    v3.cek_gerekirse()
    iz = v3.hedefler.get(22, {})
    olc("saha saati 3 sa GERI olsa da iz taze",
        iz and abs(iz["son"] - time.time()) < 5.0,
        None if not iz else iz["son"] - time.time())

    # ------------------------------------------------------------------
    bolum("5. Radar susunca iz listesi bosalir (hayalet iz yok)")
    kutu = {"izler": izler}
    v = vekil_kur(cek=lambda: (kopru_paketi(kutu["izler"]), None))
    v.cek_gerekirse()
    olc("izler var", len(v.hedefler) == 2)
    kutu["izler"] = []                       # radar sustu
    v._son_cekme = 0.0                       # araligi atla
    v.cek_gerekirse()
    olc("kopru bos liste verince harita bosaldi",
        v.hedefler == {}, len(v.hedefler))

    # ------------------------------------------------------------------
    bolum("6. Kopru KOPUNCA hayalet iz kalmaz")
    durumlar = {"hata": False}

    def cek_kopan():
        if durumlar["hata"]:
            return None, "baglanti yok"
        return kopru_paketi(izler), None

    v = vekil_kur(cek=cek_kopan)
    v.cek_gerekirse()
    olc("kopma oncesi izler var", len(v.hedefler) == 2)
    durumlar["hata"] = True
    v._son_cekme = 0.0
    v.cek_gerekirse()
    # Tolerans icinde: gecici yavaslik haritayi bosaltmamalidir
    olc("kisa kesintide izler KORUNUR (tolerans)",
        len(v.hedefler) == 2, len(v.hedefler))
    olc("kisa kesintide durum 'bagli' kalir",
        v.durum.get("durum") == "bagli", v.durum.get("durum"))
    # Tolerans asilinca izler silinmeli
    v._son_basarili = time.time() - (KOPMA_TOLERANS_SN + 1.0)
    v._son_cekme = 0.0
    v.cek_gerekirse()
    olc("tolerans asilinca durum 'hata'",
        v.durum.get("durum") == "hata", v.durum.get("durum"))
    olc("tolerans asilinca izler SILINDI (hayalet yok)",
        v.hedefler == {}, len(v.hedefler))
    olc("hata mesaji tasindi",
        "baglanti yok" in (v.durum.get("hata") or ""),
        v.durum.get("hata"))

    # ------------------------------------------------------------------
    bolum("7. Kopru yapilandirilmadiysa panel 'kapali' gorur")
    v = vekil_kur(cek=None)
    v.cek_gerekirse()
    olc("durum 'kapali'", v.durum.get("durum") == "kapali",
        v.durum.get("durum"))
    olc("iz yok", v.hedefler == {})

    # ------------------------------------------------------------------
    bolum("8. Cekme telemetri dongusunu BLOKLAMAZ")
    v = vekil_kur(cek=lambda: (kopru_paketi(izler), None))
    v.cek_gerekirse()
    t0 = time.time()
    for _ in range(500):                     # dongu hizli doner
        v.cek_gerekirse()
    sure = time.time() - t0
    olc("500 cagri < 0.2 sn (aralik uygulaniyor)", sure < 0.2,
        round(sure, 4))

    sayac = {"n": 0}

    def cek_sayan():
        sayac["n"] += 1
        return kopru_paketi(izler), None

    v = vekil_kur(cek=cek_sayan)
    for _ in range(50):
        v.cek_gerekirse()
    olc("cekme araligi kopruyu bogmadi (tek cagri)",
        sayac["n"] == 1, sayac["n"])
    time.sleep(CEKME_ARALIK_SN + 0.05)
    v.cek_gerekirse()
    olc("aralik gecince yeniden cekildi", sayac["n"] == 2, sayac["n"])

    # ------------------------------------------------------------------
    bolum("9. Cekme HIC cokmez (telemetri dongusu korunur)")

    def cek_patlayan():
        raise RuntimeError("beklenmeyen")

    v = vekil_kur(cek=cek_patlayan)
    try:
        v.cek_gerekirse()
        olc("istisna yutuldu", True)
    except Exception as e:
        olc("istisna yutuldu", False, e)
    olc("durum hata olarak isaretlendi",
        v.durum.get("durum") in ("hata", "kapali"), v.durum.get("durum"))

    # bozuk paket bicimleri
    for bozuk in (None, [], "metin", {"izler": "bozuk"},
                  {"radar_durum": "bozuk", "izler": [1, 2]},
                  {"izler": [{"lat": 1}]}):
        v = vekil_kur(cek=lambda b=bozuk: (b, None))
        try:
            v.cek_gerekirse()
            olc("bozuk paket cokmedi: %.20r" % (bozuk,), True)
        except Exception as e:
            olc("bozuk paket cokmedi: %.20r" % (bozuk,), False, e)

    # ------------------------------------------------------------------
    bolum("10. radar_konum(): RTK once, yoksa merkez ayari")
    v = vekil_kur(cek=lambda: (kopru_paketi(izler), None),
                  ayar={"merkez_lat": 41.0, "merkez_lon": 29.0})
    v.cek_gerekirse()
    olc("RTK varsa RTK kullanilir", v.radar_konum() == (39.925533,
                                                        32.866287),
        v.radar_konum())
    v = vekil_kur(cek=lambda: (kopru_paketi(
        izler, durum={"durum": "bagli", "lat": None, "lon": None}), None),
        ayar={"merkez_lat": 41.0, "merkez_lon": 29.0})
    v.cek_gerekirse()
    olc("RTK yoksa merkez ayari kullanilir",
        v.radar_konum() == (41.0, 29.0), v.radar_konum())
    v = vekil_kur(cek=None, ayar={})
    olc("hic konum yoksa (None, None)", v.radar_konum() == (None, None),
        v.radar_konum())

    # ------------------------------------------------------------------
    bolum("11. Eski kopru surumu alan gondermezse cokmez")
    # Kopru v1.4.2 ise 'radar_ayarlar' hic gondermeyebilir.
    v = vekil_kur(cek=lambda: ({"radar_durum": {"durum": "bagli"}}, None))
    try:
        v.cek_gerekirse()
        olc("eksik alanli paket cokmedi", True)
    except Exception as e:
        olc("eksik alanli paket cokmedi", False, e)
    olc("durum yine de guncellendi", v.durum.get("durum") == "bagli")
    olc("ayar alanlari korundu", "frekans" in v.radar_ayarlar)

    print("=" * 70)
    print("SONUC: %d gecti, %d kaldi" % (GECTI, KALDI))
    print("=" * 70)
    return 0 if KALDI == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
