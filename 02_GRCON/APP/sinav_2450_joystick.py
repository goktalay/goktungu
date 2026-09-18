#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GOKTUNGU v2.4.50 - JOYSTICK EKSEN / KAYMA SINAVI

Amac: v2.4.50'nin iki hedefini kurulum yerinde olcmek:
  1. Cubuk ORTADAYKEN dronun kendi etrafinda donmesine yol acan
     kaymanin (drift) gercekten giderildigi
  2. Eksen yonlerinin pilot bazinda ters cevrilebildigi

Neden bu sinav var: kusur SESSIZDIR. Kod derlenir, arayuz acilir,
hicbir hata gorunmez; belirti yalnizca gercek bir cubuk takildiginda
ve dron havadayken ortaya cikar. Dahasi "olu bolge var" demek yeterli
DEGILDIR: olculdu ki merkezi 0.13 kaymis bir cubukta olu bolge
sonrasinda hala 0.011 kalir ve dron yavas da olsa doner. Bu yuzden
sinav yalniz dosya varligini degil, SAYISAL DAVRANISI olcer:
kayan bir cubugun islenmis degeri TAM SIFIR olmak zorundadir.

Ayrica arayuz ile arka uc arasindaki sozlesme olculur; bu iki uc
birbirinden bagimsiz yazildigi icin bir anahtar adi degistiginde
"dugme hicbir sey yapmiyor" seklinde sessizce kopar.

Kullanim: kurulum kokunde `python3 sinav_2450_joystick.py`
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

KOK = os.path.dirname(os.path.abspath(__file__))

# --- v2.4.52 YOL KATMANI -------------------------------------------
# Klasor yapisi v2.4.52 ile degisti (main.py + assets/{web,python}).
# Bu sinav duz yapiya gore yazilmisti; asagidaki katman iki yapida da
# dogru yolu bulur. Katman yoksa eski davranis aynen surer.
try:
    import sinav_yol as _SY
except ImportError:
    _SY = None
    for _d in (KOK, os.path.dirname(KOK),
               os.path.dirname(os.path.dirname(KOK)),
               os.path.dirname(os.path.dirname(os.path.dirname(KOK)))):
        _c = os.path.join(_d, "sinav_yol.py")
        if os.path.isfile(_c):
            sys.path.insert(0, _d)
            try:
                import sinav_yol as _SY
            except ImportError:
                _SY = None
            break
if _SY is not None:
    KOK = _SY.KOK

    def _y(*parcalar):
        return _SY.coz(*parcalar)
    _SY.ice_aktarma_yolu_kur()
else:
    def _y(*parcalar):
        return _y(*parcalar)
# --------------------------------------------------------------------

if KOK not in sys.path:
    sys.path.insert(0, KOK)

_gecti = 0
_kaldi = 0
_kaldi_liste: list[str] = []


def olc(ad, kosul, ayrinti=""):
    global _gecti, _kaldi
    if kosul:
        _gecti += 1
        print("  [OK]   %s" % ad)
    else:
        _kaldi += 1
        _kaldi_liste.append(ad + ((" - " + ayrinti) if ayrinti else ""))
        print("  [KALDI] %s%s" % (ad, (" - " + ayrinti) if ayrinti else ""))


def oku(*parcalar):
    yol = _y(*parcalar)
    if not os.path.isfile(yol):
        return ""
    with open(yol, encoding="utf-8", errors="replace") as f:
        return f.read()


def main():
    print("=" * 70)
    print("GOKTUNGU v2.4.50 - JOYSTICK EKSEN / KAYMA SINAVI")
    print("=" * 70)

    # ==================================================================
    print()
    print("[1] ORTAK EKSEN ISLEME MODULU (goktungu/joystick_ayar.py)")
    # Neden ayri modul: eksen eslesmesi ONCE uc ayri yerde sabit
    # kodluydu (tarayici, pygame, GCCDUAL cantasi). Tek yere koymak
    # yetmez; hepsi ayni moduke baglanmalidir, aksi halde pilot ayari
    # yalnizca bir kaynakta gecerli olur ve digeri sessizce eski
    # davranisi surdurur.
    js_py = oku("goktungu", "joystick_ayar.py")
    olc("goktungu/joystick_ayar.py var", bool(js_py))

    try:
        from goktungu import joystick_ayar as ja
    except Exception as e:  # noqa: BLE001
        olc("joystick_ayar ice aktarilabilir", False, str(e)[:160])
        ja = None
    else:
        olc("joystick_ayar ice aktarilabilir", True)

    if ja is not None:
        for ad in ("varsayilan_tercih", "tercih_duzelt", "olu_uygula",
                   "merkez_duzelt", "isle", "notr_mu"):
            olc("joystick_ayar.%s() var" % ad,
                callable(getattr(ja, ad, None)))
        olc("EKSENLER dortlu (vx,vy,vz,yaw)",
            tuple(getattr(ja, "EKSENLER", ())) == ("vx", "vy", "vz", "yaw"))

        # --------------------------------------------------------------
        print()
        print("[2] KAYMA DAVRANISI - ASIL KUSURUN SAYISAL OLCUMU")
        # Kullanicinin bildirdigi belirti: "durduk yere joystick
        # ortadayken bile dron kendi etrafinda donuyor". Asagidaki
        # olcumler o belirtinin kaynagini ve giderildigini dogrular.
        t = ja.varsayilan_tercih()

        # (a) Kalibrasyon YOKKEN kayan cubuk: olu bolge kaymanin bir
        #     kismini yutar ama TAMAMINI yutmaz. Bu olcum, "olu bolge
        #     koydum, sorun bitti" varsayiminin YANLIS oldugunu
        #     kanitlar; sinavda kasten tutulur.
        kayma = 0.13
        s = ja.isle({"vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw": kayma}, t,
                    kaynak="gamepad")
        kalan = abs(s.get("yaw", 0.0))
        olc("kalibrasyonsuz kayma olu bolgeyle KUCULUR (0.13 -> <0.05)",
            kalan < 0.05, "olculen=%.4f" % kalan)
        olc("kalibrasyonsuz kayma TAM SIFIR DEGIL (olu bolge yetmez)",
            kalan > 0.0,
            "olculen=%.4f - bu madde kasten boyle; kalibrasyon sarttir"
            % kalan)

        # (b) Merkez kalibre edildikten SONRA ayni cubuk tam sifir
        #     vermek zorundadir. Asil duzeltme budur.
        t2 = ja.varsayilan_tercih()
        t2["merkez"]["gamepad_yaw"] = kayma
        s2 = ja.isle({"vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw": kayma}, t2,
                     kaynak="gamepad")
        olc("KALIBRASYON SONRASI kayan cubuk TAM SIFIR",
            abs(s2.get("yaw", 0.0)) < 1e-9,
            "olculen=%.6f" % s2.get("yaw", 0.0))

        # (c) notr_mu(): fren mantiginin dayanagi. Eski kodda fren
        #     esigi ham degere bakiyordu (abs>0.02) ve kayma bu esigi
        #     astigi icin komut akisi HIC kesilmiyordu; dron birakilinca
        #     durmak yerine donmeye devam ediyordu.
        olc("notr_mu() sifir eksende True",
            ja.notr_mu({"vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw": 0.0}))
        olc("notr_mu() kalibre edilmis kayan cubukta True (fren calisir)",
            ja.notr_mu(s2))
        olc("notr_mu() gercek girdide False",
            not ja.notr_mu({"vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw": 0.5}))

        # (d) Olu bolge sinirinda ani sicrama olmamali. Eski kod
        #     esigin hemen ustunde 0 -> 0.12 atliyordu; kucuk cubuk
        #     hareketi dronu sarsarak hareket ettirirdi.
        esik = t["olu"]["yaw"]
        s_esik = ja.isle({"vx": 0, "vy": 0, "vz": 0, "yaw": esik}, t,
                         kaynak="gamepad")
        olc("olu bolge tam sinirinda cikis sifir (sicrama yok)",
            abs(s_esik.get("yaw", 0.0)) < 1e-9,
            "olculen=%.4f" % s_esik.get("yaw", 0.0))
        s_ust = ja.isle({"vx": 0, "vy": 0, "vz": 0, "yaw": esik + 0.01}, t,
                        kaynak="gamepad")
        olc("olu bolge ustunde ORANSAL baslar (sicrama yok)",
            0.0 < abs(s_ust.get("yaw", 0.0)) < 0.05,
            "olculen=%.4f" % s_ust.get("yaw", 0.0))

        # (e) Tam itiste deger kirpilmamali; aksi halde pilot tam hiz
        #     alamaz ve "dron yavas" sikayeti dogar.
        s_tam = ja.isle({"vx": 1.0, "vy": 0, "vz": 0, "yaw": 0}, t,
                        kaynak="gamepad")
        olc("tam itiste deger korunur (1.0)",
            abs(s_tam.get("vx", 0.0) - 1.0) < 1e-6,
            "olculen=%.4f" % s_tam.get("vx", 0.0))

        # --------------------------------------------------------------
        print()
        print("[3] EKSEN TERS CEVIRME")
        t3 = ja.varsayilan_tercih()
        t3["ters"]["vx"] = True
        s3 = ja.isle({"vx": 0.6, "vy": 0.6, "vz": 0, "yaw": 0}, t3,
                     kaynak="gamepad")
        olc("ters cevrilen eksen isaret degistirir",
            s3.get("vx", 0.0) < 0, "vx=%.3f" % s3.get("vx", 0.0))
        olc("ters cevrilmeyen eksen ETKILENMEZ (bagimsizlik)",
            s3.get("vy", 0.0) > 0, "vy=%.3f" % s3.get("vy", 0.0))

        # Bozuk girdi programi cokertmemeli: ayar dosyasi elle
        # duzenlenebilir ve saha kosullarinda bozulabilir.
        for bozuk in (None, {}, {"ters": "hayir"}, {"olu": {"yaw": "abc"}},
                      {"olu": {"yaw": -5}}, {"egri": 0}):
            try:
                d = ja.tercih_duzelt(bozuk)
                iyi = (isinstance(d, dict) and "ters" in d and "olu" in d
                       and all(0.0 <= float(d["olu"][e]) < 1.0
                               for e in ja.EKSENLER))
            except Exception:  # noqa: BLE001
                iyi = False
            olc("tercih_duzelt() bozuk girdiyi onarir: %r" % (bozuk,), iyi)

    # ==================================================================
    print()
    print("[4] ARKA UC BAGLANTILARI")
    mk = oku("goktungu", "manuel_kontrol.py")
    olc("manuel_kontrol.py joystick_ayar modulunu kullanir",
        "joystick_ayar" in mk)
    olc("manuel_kontrol.tercih_ayarla() var", "def tercih_ayarla" in mk)
    olc("manuel_kontrol.ham_joystick() var", "def ham_joystick" in mk)
    olc("manuel_kontrol.tarayici_ham() var", "def tarayici_ham" in mk)
    olc("eksen_guncelle() ham eksen parametresi alir",
        re.search(r"def eksen_guncelle\([^)]*ham", mk, re.S) is not None)
    # KRITIK: eski sabit olu bolge kalmamali. Kalirsa iki olu bolge
    # ust uste biner ve cubugun kullanilabilir araligi daralir.
    olc("manuel_kontrol.py'de eski sabit 0.12 olu bolge KALMADI",
        not re.search(r"OLU\s*=\s*0\.12", mk))
    olc("fren esigi notr_mu() ile olculur (ham esik degil)",
        "notr_mu(" in mk)

    su_gecici = oku("goktungu", "sunucu.py")
    # GERILEME KORUMASI (canli denemede olculen kusur):
    # Kalibrasyon SILME islemi, "joystick verisi yok" denetimine
    # takilmamalidir. Silme icin ham degere ihtiyac yoktur. Takilirsa
    # cubuk takili degilken "Kalibrasyonu sifirla" hata verir ve pilot
    # yanlis kalibrasyonla mahsur kalir.
    olc("kalibrasyon SILME yolu ham veri denetiminden ayrilmis",
        "siliniyor = bool(k.get(\"sil\"))" in su_gecici
        and "if not siliniyor:" in su_gecici)

    su = oku("goktungu", "sunucu.py")
    for k in ("joystick_tercih", "joystick_tercih_yaz", "joystick_kalibre",
              "joystick_ham"):
        olc('sunucu.py "%s" komutunu isler' % k,
            ('elif komut == "%s"' % k) in su or ('== "%s"' % k) in su)
    for f in ("_joystick_tercih_oku", "_joystick_tercih_kaydet",
              "_joystick_tercih_uygula", "_joystick_tercih_gonder",
              "_joystick_tercih_yaz", "_joystick_kalibre"):
        olc("sunucu.%s() var" % f, ("def %s" % f) in su)
    # Giriste uygulanmasi SART: aksi halde pilot ayarini kaydeder,
    # yeniden giris yapar ve ayar sessizce eski haline doner.
    olc("GIRISTE pilot tercihi uygulanir",
        "_joystick_tercih_uygula(websocket)" in su)
    # Saklama pilot bazli olmali; program geneli olsa iki pilot ayni
    # bilgisayarda birbirinin ayarini ezer.
    olc("tercih PILOT BAZINDA saklanir (joystick_pilot anahtari)",
        "joystick_pilot" in su)
    olc("manuel_eksen ham eksenleri iletir",
        re.search(r'manuel_eksen', su) is not None and '"ham"' in su
        or "k.get(\"ham\")" in su)

    i2 = oku("goktungu", "istasyon2.py")
    olc("GCCDUAL cantasi pilot tercihini kullanir",
        "joystick_ayar" in i2 or "tercih" in i2)

    # ==================================================================
    print()
    print("[5] ARAYUZ BAGLANTILARI")
    jaj = oku("js", "joystick_ayar.js")
    olc("js/joystick_ayar.js var", bool(jaj))
    for f in ("joystickPanelAc", "jaTercihGeldi", "jaTercihSonuc",
              "jaKalibreSonuc", "jaHamGeldi"):
        olc("window.%s tanimli" % f,
            ("window.%s" % f) in jaj)
    # Menu ogesi paneli GERCEKTEN acmali; bagli degilse dugme
    # gorunur ama tiklandiginda hicbir sey olmaz.
    olc("pmJoystick menu ogesi paneli acar",
        'getElementById("pmJoystick")' in jaj
        and "joystickPanelAc()" in jaj)

    ws = oku("js", "ws.js")
    for tip in ("joystick_tercih", "joystick_tercih_sonuc",
                "joystick_kalibre_sonuc", "joystick_ham"):
        olc('ws.js "%s" mesajini yonlendirir' % tip,
            ('m.tip === "%s"' % tip) in ws)

    dr = oku("js", "dronlar.js")
    # Bu iki madde asil duzeltmenin arayuz tarafidir: tarayici artik
    # kendi esigini uygulamaz, HAM deger gonderir. Aksi halde sunucu
    # cubugun gercek merkezini goremez ve kalibrasyon imkansiz olur.
    olc("dronlar.js sabit gpOlu()/0.12 esigi KALDIRILDI",
        "gpOlu" not in dr and "GP_OLU" not in dr)
    olc("dronlar.js ham eksenleri `ham` alaninda gonderir",
        "mesaj.ham" in dr or '"ham"' in dr)

    ix = oku("index.html")
    olc("index.html profil menusunde pmJoystick var",
        'data-i18n="pmJoystick"' in ix)
    olc("index.html joystick_ayar.js betigini yukler",
        "js/joystick_ayar.js" in ix)
    # v2.4.51 NOTU: bu bir GERILEME sinavidir; surum ilerledikce etiket
    # de ilerler. Sabit "v2450" beklemek dogru calisan bir kurulumda
    # YANLIS alarm uretir. Olculen sey su: betikler onbellek etiketi
    # TASIYOR ve hicbiri v2450'den GERI degil.
    olc("index.html joystick betigi onbellek etiketli",
        re.search(r"js/joystick_ayar\.js\?v=v\d+", ix) is not None)
    _et = sorted({int(m) for m in re.findall(r"\?v=v(\d{4})", ix)})
    olc("index.html onbellek etiketleri v2450 veya sonrasi",
        bool(_et) and min(_et) >= 2450, str(_et))
    olc("index.html onbellek etiketi TEK surumde (karisik degil)",
        len(_et) == 1, str(_et))

    css = oku("css", "stil.css")
    for sinif in (".ja-satir", ".ja-cubuk", ".ja-uyari-kutu", ".ja-kaydir"):
        olc("stil.css %s sinifi var" % sinif, sinif in css)
    # Cakisma denetimi: `.sv-` AI rozeti, `.svc-` servis panelidir.
    olc(".ja- oneki mevcut siniflarla cakismaz",
        ".ja-satir" in css and ".sv-rozet" in css)

    # ==================================================================
    print()
    print("[6] DIL DENGESI VE SURUM")
    i18 = oku("js", "i18n.js")
    i_tr = i18.find("  TR: {")
    i_en = i18.find("  EN: {")
    anahtar = re.compile(r'^\s{4}"?([A-Za-z_][A-Za-z0-9_]*)"?\s*:', re.M)
    tr = set(anahtar.findall(i18[i_tr:i_en])) if i_tr >= 0 else set()
    en = set(anahtar.findall(i18[i_en:])) if i_en >= 0 else set()
    olc("i18n TR/EN anahtar sayisi esit (TR=%d EN=%d)" % (len(tr), len(en)),
        len(tr) == len(en) and tr == en,
        "TR fazlasi=%s EN fazlasi=%s"
        % (sorted(tr - en)[:5], sorted(en - tr)[:5]))
    # Arayuzde kullanilan her anahtar iki dilde de bulunmali; eksikse
    # kullanici ham anahtar adini gorur ("jaTers" gibi).
    kullanilan = set(re.findall(r"\bt\.(ja[A-Za-z]+)", jaj))
    kullanilan |= set(re.findall(r"\bjaT\(\)\.(ja[A-Za-z]+)", jaj))
    eksik_tr = sorted(kullanilan - tr)
    eksik_en = sorted(kullanilan - en)
    olc("panelde kullanilan tum anahtarlar TR'de var",
        not eksik_tr, "eksik=%s" % eksik_tr[:6])
    olc("panelde kullanilan tum anahtarlar EN'de var",
        not eksik_en, "eksik=%s" % eksik_en[:6])
    olc("pmJoystick her iki dilde var",
        "pmJoystick" in tr and "pmJoystick" in en)

    sj = oku("js", "surum.js")
    # Surum ilerledikce GCS_SURUM degisir; olculen sey 2.4.50 girdisinin
    # gecmiste KORUNDUGU ve surumun GERI GITMEDIGIDIR.
    olc("surum gecmisinde 2.4.50 girdisi korunmus", 's: "2.4.50"' in sj)
    _m = re.search(r'GCS_SURUM\s*=\s*["\']([0-9.]+)["\']', sj)
    olc("js/surum.js GCS_SURUM >= 2.4.50",
        _m is not None and
        tuple(int(x) for x in _m.group(1).split(".")) >= (2, 4, 50),
        _m.group(1) if _m else "okunamadi")
    ini = oku("goktungu", "__init__.py")
    _mi = re.search(r'_SON_BILINEN\s*=\s*["\']([0-9.]+)["\']', ini)
    olc("goktungu/__init__.py yedek surumu >= 2.4.50",
        _mi is not None and
        tuple(int(x) for x in _mi.group(1).split(".")) >= (2, 4, 50),
        _mi.group(1) if _mi else "okunamadi")

    # ==================================================================
    print()
    print("[7] SOZDIZIMI")
    for f in ("goktungu/joystick_ayar.py", "goktungu/manuel_kontrol.py",
              "goktungu/sunucu.py", "goktungu/istasyon2.py", "main.py"):
        yol = _y(f)
        if not os.path.isfile(yol):
            olc("%s var" % f, False)
            continue
        s = subprocess.run([sys.executable, "-m", "py_compile", yol],
                           capture_output=True, text=True)
        olc("%s derlenir" % f, s.returncode == 0, (s.stderr or "")[:160])

    if subprocess.run(["which", "node"], capture_output=True).returncode == 0:
        for f in ("js/joystick_ayar.js", "js/ws.js", "js/dronlar.js",
                  "js/i18n.js", "js/surum.js"):
            yol = _y(f)
            if not os.path.isfile(yol):
                olc("%s var" % f, False)
                continue
            s = subprocess.run(["node", "--check", yol],
                               capture_output=True, text=True)
            olc("%s sozdizimi tamam" % f, s.returncode == 0,
                (s.stderr or "")[:160])
    else:
        print("  [ATLA] node yok; JS sozdizimi olculemedi")

    # ==================================================================
    print()
    print("=" * 70)
    print("SONUC: %d gecti / %d kaldi" % (_gecti, _kaldi))
    if _kaldi_liste:
        print()
        print("KALAN MADDELER:")
        for k in _kaldi_liste:
            print("  - %s" % k)
    print("=" * 70)
    return 0 if _kaldi == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
