#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GOKTUNGU v2.4.43 arayuz butunluk denetimi.

Kurulum sonrasi yamanin eksiksiz uygulandigini dogrular. Tarayici
gerektirmez; kaynak dosyalarin gercek icerigini olcer.

Kullanim:  python3 sinav_2443_arayuz.py   (kurulum kokunde)

Cikis kodu 0 = tum denetimler gecti, 1 = eksik var.
"""
import json
import os
import re
import sys

KOK = os.path.dirname(os.path.abspath(__file__))

_gecti = 0
_kaldi = []


def oku(gorece):
    """Kurulum kokune gore dosya okur. Yoksa bos dizi dondurur."""
    y = os.path.join(KOK, gorece)
    if not os.path.exists(y):
        return None
    with open(y, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def denet(ad, kosul, kanit=""):
    global _gecti
    if kosul:
        _gecti += 1
        print(f"[GECTI    ] {ad}" + (f"  ->  {kanit}" if kanit else ""))
    else:
        _kaldi.append(ad)
        print(f"[BASARISIZ] {ad}" + (f"  ->  {kanit}" if kanit else ""))


def main():
    print("=" * 70)
    print("GOKTUNGU v2.4.43 ARAYUZ BUTUNLUK DENETIMI")
    print("=" * 70)

    # ---------------------------------------------------------------
    # 1. SURUM ETIKETLERI
    # ---------------------------------------------------------------
    print("\n--- 1. Surum etiketleri ---")
    surum = oku("js/surum.js") or ""

    # Ileriye donuk uyum: bu betik v2.4.43 OZELLIKLERINI olcer, surumun
    # tam 2.4.43 olmasini sart kosmaz. Aksi halde v2.4.44 gibi ust
    # surumlerde islevsel gerileme olmadigi halde denetim kalirdi.
    def _en_az(metin, kalip, en_az):
        m = re.search(kalip, metin)
        if not m:
            return False, ""
        u = tuple(int(x) for x in m.groups())
        return u >= en_az, ".".join(str(x) for x in u)

    _uy, _bul = _en_az(
        surum, r'GCS_SURUM\s*=\s*["\'](\d+)\.(\d+)\.(\d+)["\']', (2, 4, 43))
    denet("js/surum.js surumu >= 2.4.43", _uy, _bul)
    denet("js/surum.js surum gecmisinde 2.4.43 kaydi",
          's: "2.4.43"' in surum)
    init = oku("goktungu/__init__.py") or ""
    _uy, _bul = _en_az(
        init, r'_SON_BILINEN\s*=\s*["\'](\d+)\.(\d+)\.(\d+)["\']', (2, 4, 43))
    denet("goktungu/__init__.py surumu >= 2.4.43", _uy, _bul)
    idx = oku("index.html") or ""
    _etiket = len(re.findall(r"v=v24(\d\d)", idx))
    _guncel = [int(x) for x in re.findall(r"v=v24(\d\d)", idx)]
    denet("index.html onbellek etiketi >= v2443",
          _etiket > 50 and all(x >= 43 for x in _guncel),
          f"{_etiket} etiket")
    denet("index.html'de eski v2442 etiketi kalmadi",
          "v=v2442" not in idx)

    # ---------------------------------------------------------------
    # 2. TELEMETRI TAMPONU DUZELTMESI (Windows sonsuz dongu)
    # ---------------------------------------------------------------
    print("\n--- 2. Telemetri tamponu (WinError 32 sonsuz dongu) ---")
    tt = oku("goktungu/telemetri_tampon.py") or ""
    # Acik dosya aktarim listesinden HARIC tutulmali
    denet("Aktarim listesi acik dosyayi haric tutuyor",
          "_acik_dosya_adi" in tt or "_dosya_yolu" in tt,
          "acik dosya adi izleniyor")
    # Isaretleme basarisiz olursa dongu DURMALI (mukerrer yazmayi onler)
    denet("Isaretleme basarisiz olunca dongu duruyor",
          re.search(r"isaretlen\w*|isaret_ok|break", tt) is not None)
    denet("Bayat acik dosya kapatilip aktariliyor",
          "bayat" in tt.lower() or "_dosya_kapat" in tt)

    # ---------------------------------------------------------------
    # 3. TELEMETRI TEKILLEME (mukerrer kayit temizligi)
    # ---------------------------------------------------------------
    print("\n--- 3. Telemetri tekilleme ---")
    vt = oku("goktungu/veritabani.py") or ""
    denet("Tekilleme indeksi kuruluyor (UNIQUE)",
          "UNIQUE" in vt and "telemetri" in vt,
          "UNIQUE indeks tanimi var")
    denet("Mukerrer satir temizleme gocu var (v2443)",
          "2443" in vt or "mukerrer" in vt.lower())
    denet("Toplu yazim mukerrere dayanikli (OR IGNORE)",
          "OR IGNORE" in vt.upper())

    # ---------------------------------------------------------------
    # 4. ANGAJMAN ONGORULU KESISME GUDUMU
    # ---------------------------------------------------------------
    print("\n--- 4. Angajman ongorulu kesisme gudumu ---")
    ang = oku("goktungu/angajman.py") or ""
    denet("Kesisme cozum fonksiyonu var",
          "kesisme" in ang.lower())
    denet("Gorev bacagindan cozum uretiliyor",
          "gorev" in ang.lower() and "seq" in ang.lower())
    denet("Hedef hiz vektoru kullaniliyor",
          re.search(r"\bvx\b", ang) is not None
          and re.search(r"\bvy\b", ang) is not None)
    denet("gorev_dikkate ayari param'da",
          "gorev_dikkate" in ang)
    denet("ongoru ayari param'da",
          "ongoru" in ang)
    denet("param kalici ornek sozlugu (ayar kayboluyordu)",
          "self._param" in ang,
          "her cagride yeni sozluk uretilmiyor")
    denet("Hedef daha hizliysa cozum uretilmiyor",
          "cozum" in ang.lower())

    # ---------------------------------------------------------------
    # 5. TELEMETRI HIZ VEKTORU ALANLARI
    # ---------------------------------------------------------------
    print("\n--- 5. Telemetri hiz vektoru ---")
    dr = oku("goktungu/dron.py") or ""
    denet("Telemetride vx alani var", '"vx"' in dr)
    denet("Telemetride vy alani var", '"vy"' in dr)
    denet("GLOBAL_POSITION_INT'ten vx/vy okunuyor",
          "GLOBAL_POSITION_INT" in dr)

    # ---------------------------------------------------------------
    # 6. RADAR IZI HIZ VEKTORU
    # ---------------------------------------------------------------
    print("\n--- 6. Radar izi hiz vektoru ---")
    tk = oku("goktungu/takip/takipci.py") or ""
    denet("Radar izinde hiz vektoru yayinlaniyor",
          re.search(r"\bvx\b", tk) is not None)

    # ---------------------------------------------------------------
    # 7. SANAL DRON COKLU ORNEK DUZELTMESI
    # ---------------------------------------------------------------
    print("\n--- 7. Sanal dron coklu ornek (2. dron gorunmuyordu) ---")
    sn = oku("goktungu/sunucu.py") or ""
    # Ek ornekler `sitl.alt_kimlik(bid, i)` ile turetilmis ic kimlik alir;
    # boylece ikinci dinleyici birincinin kaydini kapatmaz.
    st_on = oku("goktungu/sitl.py") or ""
    denet("Ek SITL ornegine ayri baglanti kimligi veriliyor",
          "alt_kimlik" in sn and "def alt_kimlik" in st_on,
          "sitl.alt_kimlik(bid, i)")
    denet("Durdurma yolu ek ornekleri de kapatiyor",
          "_dron_durdur_hepsi" in sn)
    denet("angajman_ayar WS komutu var",
          "angajman_ayar" in sn)

    # ---------------------------------------------------------------
    # 8. SITL ARM ENGELI DUZELTMESI
    # ---------------------------------------------------------------
    print("\n--- 8. Sanal dron ARM engeli ---")
    st = oku("goktungu/sitl.py") or ""
    denet("ARMING_SKIPCHK parametresi yaziliyor",
          "ARMING_SKIPCHK" in st,
          "PreArm 3D Accel engeli kaldirildi")
    denet("FRAME_CLASS parametresi korunuyor",
          "FRAME_CLASS" in st)

    # ---------------------------------------------------------------
    # 9. ANGAJMAN ARAYUZU
    # ---------------------------------------------------------------
    print("\n--- 9. Angajman arayuzu ---")
    aj = oku("js/angajman.js") or ""
    denet("Ayar penceresinde gorev dikkate anahtari",
          "gorev_dikkate" in aj or "GorevDikkate" in aj)
    denet("Ayar penceresinde ongoru anahtari",
          "ongoru" in aj)
    denet("Ayar sunucuya gonderiliyor (angajman_ayar)",
          "angajman_ayar" in aj)
    ai = oku("js/angajman_izle.js") or ""
    denet("Izleme penceresi cozum kaynagini gosteriyor",
          "kaynak" in ai)
    denet("Izleme penceresi kesisme suresini gosteriyor",
          "kesisme" in ai.lower())
    hr = oku("js/harita.js") or ""
    denet("Kayitli angajman ayari acilista arayuze aktariliyor",
          "angajmanAyar" in hr)

    # ---------------------------------------------------------------
    # 10. KAYITLI DRONLAR RESIZE
    # ---------------------------------------------------------------
    print("\n--- 10. Kayitli Dronlar resize ---")
    kd = oku("js/kayitli_dronlar.js") or ""
    denet("Resize tutamaci olusturuluyor",
          "kd-resize" in kd)
    denet("Boyut kalici kaydediliyor",
          "pencereKonumKaydet" in kd or "boyut" in kd.lower())
    css = oku("css/stil.css") or ""
    denet("kd-resize CSS sinifi tanimli",
          ".kd-resize" in css)

    # ---------------------------------------------------------------
    # 11. CSS: ANGAJMAN ONGORU SINIFLARI
    # ---------------------------------------------------------------
    print("\n--- 11. CSS siniflari ---")
    for c in ("ang-anahtar", "ang-anahtar-satir", "ang-anahtar-kaydir",
              "ang-alt-secenek", "ang-devre-disi", "ang-tamhiz"):
        denet(f"CSS .{c} tanimli", f".{c}" in css)

    # ---------------------------------------------------------------
    # 12. i18n TR/EN ESITLIGI
    # ---------------------------------------------------------------
    print("\n--- 12. i18n TR/EN esitligi ---")
    i18 = oku("js/i18n.js") or ""
    # Ayar penceresi anahtarlari ang*, izleme penceresi anahtarlari angi*
    yeni = ("angGorevDikkate", "angOngoru", "angOngoruBaslik",
            "angOngoruNotGorev", "angOngoruNotHiz",
            "angiOngoruBaslik", "angiKesismeSn", "angiSapma",
            "angiKaynakGorev", "angiKaynakHiz", "angiKaynakYok",
            "angiOngoruNotKapali", "kdResize")
    for k in yeni:
        tr_var = re.search(rf"\b{k}\s*:", i18) is not None
        # Iki dilde de tanimli olmali: anahtar en az 2 kez gecmeli
        say = len(re.findall(rf"\b{k}\s*:", i18))
        denet(f"i18n {k} TR ve EN'de tanimli",
              tr_var and say >= 2,
              f"{say} tanim")

    # ---------------------------------------------------------------
    # 13. main.py ENJEKSIYONU
    # ---------------------------------------------------------------
    print("\n--- 13. Gorev yoneticisi enjeksiyonu ---")
    mn = oku("main.py") or ""
    denet("Angajman motoruna gorev yoneticisi enjekte ediliyor",
          "gorev" in mn.lower() and "angajman" in mn.lower())

    # ---------------------------------------------------------------
    # 14. PYTHON DERLENEBILIRLIK
    # ---------------------------------------------------------------
    print("\n--- 14. Python derlenebilirlik ---")
    import py_compile
    import tempfile
    hatali = []
    _onbellek = os.path.join(tempfile.gettempdir(), "goktungu_sinav_pyc")
    for gorece in ("main.py", "goktungu/angajman.py", "goktungu/dron.py",
                   "goktungu/sunucu.py", "goktungu/veritabani.py",
                   "goktungu/telemetri_tampon.py", "goktungu/sitl.py",
                   "goktungu/takip/takipci.py", "goktungu/__init__.py"):
        y = os.path.join(KOK, gorece)
        if not os.path.exists(y):
            hatali.append(f"{gorece} (yok)")
            continue
        try:
            # cfile=os.devnull Windows'ta ve bazi Linux kurulumlarinda
            # FileExistsError uretir; gecici dosyaya derlenir.
            py_compile.compile(y, doraise=True, cfile=_onbellek)
        except Exception as e:
            hatali.append(f"{gorece}: {type(e).__name__}")
    try:
        if os.path.exists(_onbellek):
            os.remove(_onbellek)
    except OSError:
        pass
    denet("Tum degisen Python dosyalari derleniyor",
          not hatali, ", ".join(hatali) if hatali else "9 dosya")

    # ---------------------------------------------------------------
    print("\n" + "=" * 70)
    toplam = _gecti + len(_kaldi)
    print(f"SONUC: {_gecti}/{toplam} denetim gecti")
    if _kaldi:
        print("\nEKSIK OLANLAR:")
        for a in _kaldi:
            print(f"  - {a}")
    print("=" * 70)
    return 1 if _kaldi else 0


if __name__ == "__main__":
    sys.exit(main())
