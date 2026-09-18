#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GOKTUNGU v2.4.44 arayuz butunluk denetimi.

Kurulum sonrasi yamanin eksiksiz uygulandigini dogrular. Tarayici
gerektirmez; kaynak dosyalarin gercek icerigini olcer.

Kullanim:  python3 sinav_2444_arayuz.py   (kurulum kokunde)
Cikis kodu 0 = tum denetimler gecti, 1 = eksik var.
"""
import os
import re
import sys

def _kok_bul():
    """Kurulum kokunu bulur.

    Betik hem kurulum kokunde (yaninda main.py varken) hem de gelistirme
    agacinda (bir ust dizinde) calistirilabilir. `main.py` + `js/` ikilisi
    kokun olcutudur; yalniz __file__ dizinine guvenmek, betigi goktungu/
    dizininin disinda tutan gelistirme duzeninde her denetimi bosa
    dusurur.
    """
    bu = os.path.dirname(os.path.abspath(__file__))
    for aday in (bu, os.path.join(bu, "goktungu"), os.getcwd()):
        if (os.path.exists(os.path.join(aday, "main.py"))
                and os.path.isdir(os.path.join(aday, "js"))):
            return aday
    return bu


KOK = _kok_bul()

_gecti = 0
_kaldi = []


def oku(gorece):
    y = os.path.join(KOK, gorece)
    if not os.path.exists(y):
        return None
    with open(y, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def denet(ad, kosul, kanit=""):
    global _gecti
    if kosul:
        _gecti += 1
        print("[GECTI    ] %s%s" % (ad, ("  ->  " + kanit) if kanit else ""))
    else:
        _kaldi.append(ad)
        print("[BASARISIZ] %s%s" % (ad, ("  ->  " + kanit) if kanit else ""))


def main():
    print("=" * 70)
    print("GOKTUNGU v2.4.44 ARAYUZ BUTUNLUK DENETIMI")
    print("=" * 70)

    # ---------------------------------------------------------------
    print("\n--- 1. Surum etiketleri ---")
    surum = oku("js/surum.js") or ""
    def _sur(m):
        """"2.4.44" -> (2,4,44) karsilastirilabilir demet."""
        return tuple(int(x) for x in m.split("."))

    m = re.search(r'GCS_SURUM\s*=\s*"([0-9.]+)"', surum)
    sv = m.group(1) if m else "0"
    denet("js/surum.js surumu >= 2.4.44",
          bool(m) and _sur(sv) >= (2, 4, 44), sv)
    denet("js/surum.js surum gecmisinde 2.4.44 kaydi", 's: "2.4.44"' in surum)
    init = oku("goktungu/__init__.py") or ""
    mi = re.search(r'_SON_BILINEN\s*=\s*"([0-9.]+)"', init)
    iv = mi.group(1) if mi else "0"
    denet("goktungu/__init__.py surumu >= 2.4.44",
          bool(mi) and _sur(iv) >= (2, 4, 44), iv)
    idx = oku("index.html") or ""
    etiketler = sorted(set(re.findall(r"\?v=v(24\d\d)", idx)))
    denet("index.html onbellek etiketleri tek ve >= v2444",
          len(etiketler) == 1 and int(etiketler[0]) >= 2444,
          "etiketler: " + ", ".join("v" + e for e in etiketler))

    # ---------------------------------------------------------------
    print("\n--- 2. Backend modulu (goktungu/istasyon2.py) ---")
    ist2 = oku("goktungu/istasyon2.py")
    denet("goktungu/istasyon2.py mevcut", ist2 is not None)
    ist2 = ist2 or ""
    denet("baud 115200", "BAUD = 115200" in ist2)
    denet("11 buton tanimi (P1..P11)",
          'BUTONLAR = ["P%d" % i for i in range(1, 12)]' in ist2)
    denet("7 LED tanimi (P1..P7)",
          'LEDLI = ["P%d" % i for i in range(1, 8)]' in ist2)
    denet("4 panel eksen tanimi",
          '"J1_X", "J1_Y", "J2_X", "J2_Y"' in ist2)
    denet("T2 metin degerleri", 'T2_DEGERLERI = ("UP", "CENTER", "DOWN")'
          in ist2)
    denet("PONG duz metin olarak ayrilir",
          "PONG" in ist2 and "json.loads" in ist2)
    denet("varsayilan port /dev/ttyACM0", '"/dev/ttyACM0"' in ist2)
    denet("otomatik baglanma islevi", "def otomatik_baslat" in ist2)
    denet("yayin hiz siniri (20 Hz)", "YAYIN_ARALIK" in ist2)
    denet("ek dron joystick adaylari", "EK_EKSEN_ADAYLARI" in ist2)
    denet("kalibrasyon islevi", "def kalibre" in ist2)

    print("    Kanal eslemesi (kullanici tanimi):")
    for kanal, eylem in (("P1", "arm_disarm"), ("P2", "takeoff_land"),
                         ("P3", "rtl"), ("P4", "mod_guided"),
                         ("P5", "mod_althold"), ("P6", "mod_auto"),
                         ("P8", "harita_kaynak"),
                         ("P9", "kullanici_konum"),
                         ("P10", "hepsini_kapsa"), ("P11", "nokta_gez")):
        denet("  %s -> %s" % (kanal, eylem),
              re.search(r'"%s":\s*"%s"' % (kanal, eylem), ist2) is not None)
    denet("  T1 -> patlat_onay",
          re.search(r'"T1":\s*"patlat_onay"', ist2) is not None)
    denet("  T2 UP -> harita_zoom_in",
          '"T2_UP": "harita_zoom_in"' in ist2)
    denet("  T2 DOWN -> harita_zoom_out",
          '"T2_DOWN": "harita_zoom_out"' in ist2)
    denet("  T2 CENTER -> harita_zoom_dur",
          '"T2_CENTER": "harita_zoom_dur"' in ist2)
    denet("  T1 patlatma LED'i P7", 'PATLAT_LED = "P7"' in ist2)

    # ---------------------------------------------------------------
    print("\n--- 3. Sunucu baglantilari (goktungu/sunucu.py) ---")
    sun = oku("goktungu/sunucu.py") or ""
    denet("Istasyon2 sinifi ice alindi", "istasyon2" in sun.lower())
    for komut in ("istasyon2_baglan", "istasyon2_kes", "istasyon2_led",
                  "istasyon2_durum", "istasyon2_kalibre",
                  "istasyon2_portlar", "istasyon2_ayar"):
        denet("  WS komutu %s" % komut, '"%s"' % komut in sun)
    denet("ucus eylem isleyicisi", "_ist2_ucus_eylem" in sun)
    denet("harita eylemleri arayuze yayinlanir",
          "IST2_HARITA_EYLEMLERI" in sun)
    denet("mod eylem haritasi (arac tipine gore)",
          "IST2_MOD_EYLEM" in sun)
    denet("joystick kontrolu acik dron suzgeci",
          "_ist2_manuel_dronlar" in sun)
    denet("eylem sonucu arayuze bildirilir",
          "istasyon2_eylem_sonuc" in sun)

    man = oku("goktungu/manuel_kontrol.py") or ""
    denet("manuel_kontrol.py istasyon2_eksen()",
          "def istasyon2_eksen" in man)

    mainpy = oku("main.py") or ""
    denet("main.py Istasyon2 kurulumu", "Istasyon2(" in mainpy)
    denet("main.py otomatik baglanma cagrisi",
          "otomatik_baslat" in mainpy)

    # ---------------------------------------------------------------
    print("\n--- 4. Arayuz modulu (js/istasyon2.js) ---")
    js = oku("js/istasyon2.js")
    denet("js/istasyon2.js mevcut", js is not None)
    js = js or ""
    denet("panel acma islevi", "function istasyon2Ac" in js)
    denet("durum isleyicisi", "window.istasyon2DurumIsle" in js)
    denet("eylem isleyicisi", "window.istasyon2EylemIsle" in js)
    denet("eylem sonucu isleyicisi", "window.istasyon2EylemSonucIsle" in js)
    denet("harita 3B kontrolu (requestAnimationFrame)",
          "requestAnimationFrame" in js)
    denet("dondurme hizi tanimi", "I2_DONME_HIZ" in js)
    denet("egim hizi tanimi", "I2_EGIM_HIZ" in js)
    denet("kaydirma orani tanimi", "I2_KAYMA_ORAN" in js)
    denet("zoom orani tanimi", "I2_ZOOM_ORAN" in js)
    denet("olu bolge", "I2_OLU" in js)
    denet("arka plan sekmesi kamerayi surmez", "document.hidden" in js)
    denet("patlatma onay penceresi", "function i2PatlatOnay" in js)
    denet("nokta gezme (P11)", "function i2NoktayaGit" in js)
    denet("harita kaynak sirasi (P8)", "haritaKaynakSirala" in js)
    denet("kullanici konumu (P9)", "haritaKonumumaGit" in js)
    denet("tumunu kapsa (P10)", "haritaTumunuSigdir" in js)
    denet("joystick canvas gorseli", "function i2JoyCiz" in js)
    denet("dil tazeleme kancasi", "window.istasyon2DilTazele" in js)

    # ---------------------------------------------------------------
    print("\n--- 5. Arayuz baglantilari ---")
    har = oku("js/harita.js") or ""
    denet("harita.js haritaKaynakSirala dis acimi",
          "window.haritaKaynakSirala" in har)
    denet("harita.js haritaKaynakListesi dis acimi",
          "window.haritaKaynakListesi" in har)

    ws = oku("js/ws.js") or ""
    for tip in ("istasyon2_durum", "istasyon2_eylem",
                "istasyon2_eylem_sonuc", "istasyon2_portlar",
                "istasyon2_sonuc"):
        denet("  ws.js yonlendirme %s" % tip,
              'm.tip === "%s"' % tip in ws)

    mb = oku("js/menubar.js") or ""
    denet("menubar.js mbIstasyon2 baglantisi", "mbIstasyon2" in mb)
    denet("index.html menu ogesi", 'id="mbIstasyon2"' in idx)
    denet("index.html script etiketi",
          bool(re.search(r"js/istasyon2\.js\?v=v24\d\d", idx)))

    css = oku("css/stil.css") or ""
    for sinif in (".i2-popup", ".i2-btn-izgara", ".i2-tus-ledli",
                  ".i2-tus-led-acik", ".i2-kol-acik", ".i2-joy-dron",
                  ".i2-onay-kap", ".i2-akis", ".i2-resize"):
        denet("  css %s" % sinif, sinif in css)

    i18n = oku("js/i18n.js") or ""
    anahtarlar = ["mbIstasyon2", "i2Baslik", "i2Port", "i2Otomatik",
                  "i2Bagli", "i2Kopuk", "i2Kalibre", "i2Butonlar",
                  "i2Toggle", "i2Led", "i2Joystick", "i2Akis",
                  "i2PatlatBaslik", "i2PatlatSoru", "i2PatlatEvet",
                  "i2JoystickKapali", "i2NoktaYok", "i2HaritaKaynak"]
    eksik_tr = [a for a in anahtarlar if ("%s:" % a) not in i18n]
    denet("i18n anahtarlari mevcut", not eksik_tr,
          ("eksik: " + ", ".join(eksik_tr)) if eksik_tr
          else "%d anahtar" % len(anahtarlar))
    # TR ve EN bloklarinda ayni anahtarlar var mi
    if "  EN: {" in i18n:
        tr_blok, en_blok = i18n.split("  EN: {", 1)
        tr = set(re.findall(r"^\s{4}(i2[A-Za-z0-9]+|mbIstasyon2):",
                            tr_blok, re.M))
        en = set(re.findall(r"^\s{4}(i2[A-Za-z0-9]+|mbIstasyon2):",
                           en_blok, re.M))
        denet("i18n TR/EN anahtar sayisi esit",
              tr == en and len(tr) > 30,
              "TR=%d EN=%d" % (len(tr), len(en)))
    denet("i18n dil tazeleme kancasi",
          "istasyon2DilTazele" in i18n)

    # ---------------------------------------------------------------
    print("\n--- 6. Python soz dizimi ---")
    # py_compile yerine compile(): disk yazmaz, /dev/null sorunu olmaz
    for dosya in ("goktungu/istasyon2.py", "goktungu/sunucu.py",
                  "goktungu/manuel_kontrol.py", "main.py"):
        kaynak = oku(dosya)
        if kaynak is None:
            denet("  %s derlenebilir" % dosya, False, "dosya yok")
            continue
        try:
            compile(kaynak, dosya, "exec")
            denet("  %s derlenebilir" % dosya, True)
        except SyntaxError as e:
            denet("  %s derlenebilir" % dosya, False,
                  "satir %s: %s" % (e.lineno, e.msg))

    # ---------------------------------------------------------------
    print("\n" + "=" * 70)
    print("SONUC: %d GECTI / %d KALDI" % (_gecti, len(_kaldi)))
    if _kaldi:
        print("\nEksik denetimler:")
        for k in _kaldi:
            print("  - " + k)
    print("=" * 70)
    return 1 if _kaldi else 0


if __name__ == "__main__":
    sys.exit(main())
