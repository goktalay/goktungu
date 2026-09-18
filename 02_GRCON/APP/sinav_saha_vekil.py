# -*- coding: utf-8 -*-
"""SINAV — MERKEZ VIDEO ve AI VEKILLERI.

Denetimde olculen kusur (bkz. `/home/ubuntu/DENETIM_VIDEO_AI_KOPRU.md`):

  * `kamera_cihazlari` MERKEZDE `cv2.VideoCapture(0..5)` tariyordu;
    merkez sunucuda kamera aygiti olmadigi icin liste HER ZAMAN bostu.
  * Kamera akisini MERKEZ sureci aciyordu; saha agindaki kameralara
    erisilemezdi.
  * `ai_izleme_baslat` MERKEZDEN saha AI bilgisayarina HTTP istegi
    atiyordu; erisilemezdi ve istek zaman asimina dusuyordu.

Bu sinav MERKEZ tarafini olcer: vekiller kopruye dogru komutu mu
gonderiyor, kopruden gelen ozeti dogru mu uyguluyor, kopru koptugunda
merkez "hazir" gormeye devam ediyor mu, ve MERKEZDE kamera aygiti
aramaya donuluyor mu.

## OLCUM ILKESI

Vekillerin `_komut` geri cagrisi SAHTE ile degistirilir ve GONDERILEN
komutlar kaydedilir. Kritik olcum sudur: merkez artik kendisi baglanti
kurmaya CALISMAMALI, komutu kopruye GONDERMELI. Yalnizca donusu olcmek
yeterli olmazdi — eski kusurlu kod da "bos liste" donduruyordu ve bu
"hata yok" gibi gorunuyordu.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from goktungu.saha_vekil import (            # noqa: E402
    CEKME_ARALIK_SN, KOPMA_TOLERANS_SN, AiVekili, VideoVekili,
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

    def metin(self):
        return " | ".join("%s:%s" % (e, m) for e, m in self.satirlar)


class SahteKilit:
    """Gercek kilit yerine sayan kilit: kilit kullanimi da olculur."""

    def __init__(self):
        self.giris = 0

    def __enter__(self):
        self.giris += 1
        return self

    def __exit__(self, *a):
        return False


class SahteKameralar:
    def __init__(self, kayitlar=None):
        self.kayitlar = kayitlar or {}

    def bul(self, kid):
        return self.kayitlar.get(int(kid))


class KomutKayitci:
    """Kopruye giden komutlari kaydeder ve hazir yanit dondurur."""

    def __init__(self, yanitlar=None, hata=""):
        self.cagrilar = []
        self.yanitlar = yanitlar or {}
        self.hata = hata

    def __call__(self, eylem, veri=None):
        self.cagrilar.append((eylem, dict(veri or {})))
        if self.hata:
            return None, self.hata
        return self.yanitlar.get(eylem, {}), ""

    def eylemler(self):
        return [e for e, _v in self.cagrilar]

    def son(self, eylem):
        for e, v in reversed(self.cagrilar):
            if e == eylem:
                return v
        return None


def video_paketi(akislar=None, hazir=True, etkin=None):
    ak = akislar if akislar is not None else [
        {"id": 7, "calisiyor": True, "izleyici": 2, "kare_no": 120,
         "protokol": "mjpeg", "hata": ""},
    ]
    return {
        "video_akislar": ak,
        "video_etkin": len([a for a in ak if a.get("calisiyor")])
        if etkin is None else etkin,
        "video_hatalar": {},
        "video_port": 8801,
        "video_hazir": hazir,
        "video_vekil_hata": "",
        "ffmpeg": True,
        "opencv": False,
        "kameralar": [{"id": 7, "isim": "Saha", "protokol": "mjpeg",
                       "url": "rtsp://192.168.8.20/live"}],
    }


def ai_paketi(cevrimici=1, gorevler=None):
    return {
        "ai_sunucular": [
            {"id": 1, "ad": "isci-1", "host": "192.168.8.50",
             "port": 8900, "cevrimici": cevrimici >= 1, "yuk": 1,
             "kapasite": 2},
        ],
        "ai_gorevler": gorevler if gorevler is not None else [
            {"kamera_id": 7, "sunucu_id": 1, "ad": "isci-1"},
        ],
        "ai_hazir": cevrimici >= 1,
        "ai_sunucu_sayisi": 1,
        "ai_cevrimici": cevrimici,
        "hizlandirici": "cuda",
    }


def main():
    print("=" * 66)
    print("SINAV — MERKEZ VIDEO ve AI VEKILLERI")
    print("=" * 66)

    # =================================================================
    bolum("1. VIDEO VEKILI MERKEZDE KAMERA ARAMIYOR")
    # =================================================================
    konsol = SahteKonsol()
    kilit = SahteKilit()
    kayitci = KomutKayitci({
        "video_cihazlar": {"cihazlar": [{"indeks": 0, "ad": "USB Kamera"}],
                           "opencv": True, "gerekce": ""},
    })
    vv = VideoVekili(konsol, kilit, cek=lambda: (video_paketi(), ""),
                     komut=kayitci)

    olc("yayin_al merkezde DAIMA None (merkez kare uretmez)",
        vv.yayin_al(7) is None, vv.yayin_al(7))

    cihazlar = vv.cihaz_listesi(6)
    olc("cihaz taramasi kopruye GONDERILDI",
        "video_cihazlar" in kayitci.eylemler(), kayitci.eylemler())
    olc("cihaz taramasi en_fazla parametresini iletiyor",
        (kayitci.son("video_cihazlar") or {}).get("en_fazla") == 6,
        kayitci.son("video_cihazlar"))
    olc("sahadan gelen cihaz listesi merkeze aktariliyor",
        len(cihazlar) == 1 and cihazlar[0].get("ad") == "USB Kamera",
        cihazlar)

    # =================================================================
    bolum("2. OPENCV YOKSA YANILTICI 'KAMERA YOK' DEMIYOR")
    # =================================================================
    konsol2 = SahteKonsol()
    kayitci2 = KomutKayitci({
        "video_cihazlar": {"cihazlar": [], "opencv": False,
                           "gerekce": "OpenCV kurulu degil"},
    })
    vv2 = VideoVekili(konsol2, SahteKilit(), cek=None, komut=kayitci2)
    liste = vv2.cihaz_listesi()
    olc("OpenCV yoksa liste bos", liste == [], liste)
    olc("OpenCV eksikligi EYLEME DONUK metinle bildiriliyor",
        "opencv" in konsol2.metin().lower()
        and "pip install" in konsol2.metin().lower(), konsol2.metin())

    # =================================================================
    bolum("3. AKIS ACMA SAHAYA GIDIYOR, GEREKCE GERI DONUYOR")
    # =================================================================
    kayitci3 = KomutKayitci({
        "video_akis_baslat": {"acildi": True, "gerekce": "", "id": 7,
                              "yol": "/kamera/7", "port": 8801},
    })
    vv3 = VideoVekili(SahteKonsol(), SahteKilit(), cek=None,
                      komut=kayitci3)
    acildi, gerekce = vv3.yayin_baslat(7, {"id": 7, "url": "rtsp://x"},
                                       bekle=9.0)
    olc("akis acma kopruye GONDERILDI",
        "video_akis_baslat" in kayitci3.eylemler(), kayitci3.eylemler())
    olc("akis acma basarili donuyor", acildi is True and gerekce == "",
        (acildi, gerekce))
    v = kayitci3.son("video_akis_baslat") or {}
    olc("akis acmada kamera kaydi da iletiliyor",
        isinstance(v.get("kamera"), dict) and v["kamera"].get("id") == 7,
        v)
    olc("akis acmada bekleme suresi iletiliyor",
        abs(float(v.get("bekle") or 0) - 9.0) < 0.01, v)

    kayitci4 = KomutKayitci({
        "video_akis_baslat": {"acildi": False,
                              "gerekce": "kaynak kare uretmedi"},
    })
    vv4 = VideoVekili(SahteKonsol(), SahteKilit(), cek=None,
                      komut=kayitci4)
    acildi, gerekce = vv4.yayin_baslat(7)
    olc("basarisiz akis SESSIZ kalmiyor, gerekce donuyor",
        acildi is False and "kare uretmedi" in gerekce,
        (acildi, gerekce))

    # Kopru komutu yoksa: merkez kendi basina baglanmaya CALISMAMALI.
    vv5 = VideoVekili(SahteKonsol(), SahteKilit(), cek=None, komut=None)
    acildi, gerekce = vv5.yayin_baslat(7)
    olc("kopru baglantisi yoksa akis acilmaya CALISILMIYOR",
        acildi is False and "baglanti" in gerekce.lower(),
        (acildi, gerekce))
    olc("kopru baglantisi yoksa cihaz listesi bos donuyor",
        vv5.cihaz_listesi() == [], vv5.cihaz_listesi())

    # =================================================================
    bolum("4. KOPRU OZETI DOGRU UYGULANIYOR")
    # =================================================================
    vv.cek_gerekirse(zorla=True)
    d = vv.durum()
    olc("akis listesi uygulandi", len(d.get("akislar") or []) == 1, d)
    olc("akis calisiyor bilgisi korundu",
        (d["akislar"][0] or {}).get("calisiyor") is True, d)
    olc("kare sayaci korundu",
        int((d["akislar"][0] or {}).get("kare_no") or 0) == 120, d)
    olc("hazir bilgisi uygulandi", d.get("hazir") is True, d)
    olc("etkin akis sayisi uygulandi", d.get("etkin") == 1, d)
    olc("saha vekil portu uygulandi", d.get("port") == 8801, d)
    olc("ffmpeg gorunurlugu uygulandi", d.get("ffmpeg") is True, d)
    olc("opencv gorunurlugu uygulandi", d.get("opencv") is False, d)

    # =================================================================
    bolum("5. KOPRU KOPUNCA HAYALET AKIS KALMIYOR")
    # =================================================================
    durumlar = {"kopuk": False}

    def cek_kopan():
        if durumlar["kopuk"]:
            return None, "Kopru yanit vermiyor"
        return video_paketi(), ""

    konsol6 = SahteKonsol()
    vv6 = VideoVekili(konsol6, SahteKilit(), cek=cek_kopan,
                      komut=KomutKayitci())
    vv6.cek_gerekirse(zorla=True)
    olc("kopma oncesi akis var", len(vv6.durum()["akislar"]) == 1,
        vv6.durum())

    durumlar["kopuk"] = True
    vv6.cek_gerekirse(zorla=True)
    olc("tek basarisiz cekme listeyi HEMEN bosaltmiyor (tolerans)",
        len(vv6.durum()["akislar"]) == 1, vv6.durum())

    # Tolerans suresi gecmis gibi davranilir.
    vv6._son_basarili = time.time() - (KOPMA_TOLERANS_SN + 1.0)
    vv6.cek_gerekirse(zorla=True)
    d = vv6.durum()
    olc("tolerans asilinca akislar bosaltiliyor",
        len(d.get("akislar") or []) == 0, d)
    olc("kopmada hazir False", d.get("hazir") is False, d)
    olc("kopmada etkin 0", d.get("etkin") == 0, d)
    olc("kopma gerekcesi durumda gorunuyor",
        "yanit vermiyor" in (d.get("hata") or ""), d)
    olc("kopma kullaniciya bildirildi",
        "yanit vermiyor" in konsol6.metin(), konsol6.metin())

    # =================================================================
    bolum("6. CEKME ISTISNA FIRLATMIYOR (yayin durmasin)")
    # =================================================================
    def cek_patlayan():
        raise RuntimeError("beklenmeyen")

    vv7 = VideoVekili(SahteKonsol(), SahteKilit(), cek=cek_patlayan,
                      komut=KomutKayitci())
    patladi = False
    try:
        vv7.cek_gerekirse(zorla=True)
    except Exception:
        patladi = True
    olc("cekmede istisna DISARI CIKMIYOR", not patladi)

    bozuk = {"paket": {"video_akislar": "liste-degil"}}
    vv8 = VideoVekili(SahteKonsol(), SahteKilit(),
                      cek=lambda: (bozuk["paket"], ""),
                      komut=KomutKayitci())
    patladi = False
    try:
        vv8.cek_gerekirse(zorla=True)
    except Exception:
        patladi = True
    olc("bozuk paket istisna FIRLATMIYOR", not patladi)

    # Cekme araligi: her cagri kopruye gitmemeli (merkez bogulmasin).
    sayac = {"n": 0}

    def cek_sayan():
        sayac["n"] += 1
        return video_paketi(), ""

    vv9 = VideoVekili(SahteKonsol(), SahteKilit(), cek=cek_sayan,
                      komut=KomutKayitci())
    for _ in range(5):
        vv9.cek_gerekirse()
    olc("cekme araligi uygulaniyor (5 cagri, 1 cekme)",
        sayac["n"] == 1, sayac["n"])
    olc("cekme araligi makul (<= 5 sn)", CEKME_ARALIK_SN <= 5.0,
        CEKME_ARALIK_SN)

    # =================================================================
    bolum("7. ANOTASYON SAHAYA GIDIYOR (kare merkeze gelmiyor)")
    # =================================================================
    kayitci10 = KomutKayitci()
    vv10 = VideoVekili(SahteKonsol(), SahteKilit(), cek=None,
                       komut=kayitci10)
    vv10.anotasyon_guncelle(7, [{"x": 1, "y": 2, "w": 3, "h": 4}])
    olc("anotasyon kopruye GONDERILDI",
        "video_anotasyon" in kayitci10.eylemler(), kayitci10.eylemler())
    v = kayitci10.son("video_anotasyon") or {}
    olc("anotasyon kutulari iletiliyor",
        isinstance(v.get("kutular"), list) and len(v["kutular"]) == 1, v)

    vv10.yayin_durdur(7)
    olc("akis durdurma kopruye GONDERILDI",
        "video_akis_durdur" in kayitci10.eylemler(),
        kayitci10.eylemler())

    # =================================================================
    bolum("8. AI VEKILI IZLEMEYI SAHADAN ATIYOR")
    # =================================================================
    kayitci11 = KomutKayitci({
        "ai_izleme_baslat": {"atandi": True, "sunucu": "isci-1"},
    })
    kameralar = SahteKameralar({7: {"isim": "Saha", "protokol": "mjpeg",
                                    "url": "rtsp://192.168.8.20/live",
                                    "ai_gorevler": "insan"}})
    av = AiVekili(SahteKonsol(), SahteKilit(),
                  cek=lambda: (ai_paketi(), ""), komut=kayitci11)
    av.kameralar = kameralar

    sonuc = av.izleme_baslat(7, "http://merkez:8801/kamera/7", "gcs_proxy",
                             "insan")
    olc("izleme atama kopruye GONDERILDI",
        "ai_izleme_baslat" in kayitci11.eylemler(), kayitci11.eylemler())
    olc("izleme atama basarili donuyor", sonuc.get("tamam") is True,
        sonuc)
    v = kayitci11.son("ai_izleme_baslat") or {}
    olc("kopruye kamera_id iletiliyor", v.get("kamera_id") == 7, v)
    olc("kopruye AI gorev listesi iletiliyor",
        v.get("gorevler") == "insan", v)
    # KRITIK: merkezin urettigi adres kopruye GONDERILMEMELI.
    olc("MERKEZ akis adresi kopruye GONDERILMIYOR (saha kendi uretir)",
        "url" not in v, v)
    olc("kamera kaydi kopruye iletiliyor (defterde bulunabilsin)",
        isinstance(v.get("kamera"), dict)
        and v["kamera"].get("url") == "rtsp://192.168.8.20/live", v)

    sonuc = av.izleme_durdur(7)
    olc("izleme durdurma kopruye GONDERILDI",
        "ai_izleme_durdur" in kayitci11.eylemler(), kayitci11.eylemler())
    olc("izleme durdurma basarili donuyor", sonuc.get("tamam") is True,
        sonuc)

    # =================================================================
    bolum("9. AI ATAMA BASARISIZLIGI GEREKCELI DONUYOR")
    # =================================================================
    kayitci12 = KomutKayitci({
        "ai_izleme_baslat": {"atandi": False,
                             "gerekce": "Hicbir AI sunucusu cevrimici "
                                        "degil (2 tanimli)"},
    })
    av2 = AiVekili(SahteKonsol(), SahteKilit(), cek=None, komut=kayitci12)
    sonuc = av2.izleme_baslat(7, "u", "p")
    olc("atanamayan izleme tamam=False donuyor",
        sonuc.get("tamam") is False, sonuc)
    olc("atanamama GEREKCESI donuyor",
        "cevrimici degil" in (sonuc.get("hata") or ""), sonuc)

    av3 = AiVekili(SahteKonsol(), SahteKilit(), cek=None, komut=None)
    sonuc = av3.izleme_baslat(7, "u", "p")
    olc("kopru yoksa izleme atanmaya CALISILMIYOR",
        sonuc.get("tamam") is False
        and "baglanti" in (sonuc.get("hata") or "").lower(), sonuc)

    sonuc = av3.izleme_baslat("gecersiz", "u", "p")
    olc("gecersiz kamera kimligi yakalaniyor",
        sonuc.get("tamam") is False, sonuc)

    # =================================================================
    bolum("10. AI KOPRU OZETI VE KOPMA")
    # =================================================================
    av.cek_gerekirse(zorla=True)
    olc("isci listesi uygulandi", len(av.sunucu_durumlari()) == 1,
        av.sunucu_durumlari())
    olc("gorev listesi uygulandi", len(av.izleme_listesi()) == 1,
        av.izleme_listesi())
    d = av.durum()
    olc("ai hazir uygulandi", d.get("hazir") is True, d)
    olc("cevrimici isci sayisi uygulandi", d.get("cevrimici") == 1, d)
    olc("hizlandirici bilgisi uygulandi", d.get("hizlandirici") == "cuda",
        d)

    kopuk2 = {"k": False}

    def cek_ai_kopan():
        if kopuk2["k"]:
            return None, "Saha makinesi yanit vermedi"
        return ai_paketi(), ""

    konsol13 = SahteKonsol()
    av4 = AiVekili(konsol13, SahteKilit(), cek=cek_ai_kopan,
                   komut=KomutKayitci())
    av4.cek_gerekirse(zorla=True)
    olc("kopma oncesi isci var", len(av4.sunucu_durumlari()) == 1)
    kopuk2["k"] = True
    av4._son_basarili = time.time() - (KOPMA_TOLERANS_SN + 1.0)
    av4.cek_gerekirse(zorla=True)
    d = av4.durum()
    olc("kopmada isci listesi bosaltiliyor",
        len(av4.sunucu_durumlari()) == 0, av4.sunucu_durumlari())
    olc("kopmada gorev listesi bosaltiliyor",
        len(av4.izleme_listesi()) == 0, av4.izleme_listesi())
    olc("kopmada ai_hazir False", d.get("hazir") is False, d)
    olc("kopmada cevrimici 0", d.get("cevrimici") == 0, d)
    olc("kopma gerekcesi durumda", "yanit vermedi" in (d.get("hata") or ""),
        d)

    # Ayni hata tekrar tekrar gunluge yazilmamali.
    onceki = len(konsol13.satirlar)
    for _ in range(3):
        av4._son_basarili = time.time() - (KOPMA_TOLERANS_SN + 1.0)
        av4.cek_gerekirse(zorla=True)
    olc("ayni hata gunluge TEKRAR yazilmiyor",
        len(konsol13.satirlar) == onceki, konsol13.satirlar)

    # =================================================================
    bolum("11. MERKEZ KIPINDE YEREL ISCI/VEKIL BASLATILMIYOR")
    # =================================================================
    konsol14 = SahteKonsol()
    vv14 = VideoVekili(konsol14, SahteKilit(), cek=None, komut=None)
    vv14.calistir()
    olc("video vekili merkezde yerel akis vekili ACMIYOR",
        "merkez" in konsol14.metin().lower(), konsol14.metin())

    konsol15 = SahteKonsol()
    av15 = AiVekili(konsol15, SahteKilit(), cek=None, komut=None)
    av15.baslat()
    olc("ai vekili merkezde yoklama BASLATMIYOR",
        "merkez" in konsol15.metin().lower(), konsol15.metin())
    av15.kapat()
    olc("ai vekili kapat() istisna firlatmiyor", True)

    # =================================================================
    print("=" * 66)
    print("SONUC: %d gecti, %d kaldi" % (GECTI, KALDI))
    print("=" * 66)
    return 1 if KALDI else 0


if __name__ == "__main__":
    sys.exit(main())
