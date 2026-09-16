#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""kontrol_paket_merkez: paketleyici DOGRULAMASININ kusur yakaladigini olcer.

`paketle_merkez.dogrula()` "sorun yok" diyor. Ama bu, dogrulamanin
saglam oldugunu DEGIL, ya saglam oldugunu ya da hicbir sey olcmedigini
gosterir. Ayrimi ancak KASITLI KUSUR enjekte ederek yapabiliriz.

Yontem: saglam bir paket agaci kurulur, sonra her enjeksiyon agacin
KOPYASINA uygulanir ve `dogrula()` yeniden cagrilir. Yakalamazsa
dogrulamada KOR NOKTA var.

Her enjeksiyon GERCEK bir kusuru temsil eder; "dogrulama patlasin diye"
uydurulmus bozma yoktur:

  - sertifika/ sizmasi      -> TLS ozel anahtari musteriye gider
  - veri/ icerigi sizmasi   -> baska kurumun ucus kaydi gider
  - sinav betigi sizmasi    -> ic tani araclari musteriye gider
  - assets derinligi kayar  -> BOS sayfa servis edilir (sessiz kusur)
  - lisans.py eksik         -> 5.000 $ lisans hic dogrulanmaz
  - gomulu anahtar bozuk    -> gecerli lisans reddedilir
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paketle_merkez as PM  # noqa: E402

gecti = 0
kacti = []


def _pycache_temizle(agac):
    """Olcum sirasinda uretilen __pycache__'i siler.

    KRITIK: `dogrula()` moduleri GERCEKTEN ice aktarir (yol cozumu ve
    lisans olcumu icin). Ice aktarma __pycache__ uretir. Ilk kosumda
    bu, HER enjeksiyonun "SIZDI: __pycache__" gerekcesiyle yakalanmis
    GORUNMESINE yol acti: 29/29 basari yaniltici cikti, enjeksiyonlarin
    kendisi olculmemis olabilirdi.
    """
    for kok, dizinler, _d in os.walk(agac):
        for d in list(dizinler):
            if d == "__pycache__":
                shutil.rmtree(os.path.join(kok, d), ignore_errors=True)


def olc(ad, bozan, bekle, ai_dahil=False):
    """Agacin kopyasina `bozan` uygular, dogrulama yakaliyor mu olcer.

    `bekle`: yakalama gerekcesinde BULUNMASI gereken metin. Sadece
    "hata listesi bos degil" demek YETMEZ; dogrulamanin ENJEKSIYONU
    yakaladigini, baska bir yan etkiyi degil, kanitlamak gerekir.
    """
    global gecti
    with tempfile.TemporaryDirectory() as gecici:
        agac = os.path.join(gecici, "goktungu")
        shutil.copytree(SAGLAM, agac)
        _pycache_temizle(agac)
        bozan(agac)
        hata = PM.dogrula(agac, ai_dahil)
        # Ice aktarmanin urettigi __pycache__ satirlarini AYIKLA:
        # bunlar olcumun yan etkisidir, enjeksiyonun sonucu degildir.
        hata = [h for h in hata if "__pycache__" not in h]
        eslesen = [h for h in hata if bekle.lower() in h.lower()]
        if eslesen:
            gecti += 1
            print(f"  [YAKALADI] {ad}")
            print(f"             -> {eslesen[0][:88]}")
        elif hata:
            # Yakaladi ama BASKA sebeple: enjeksiyon dogrulanmis sayilmaz.
            kacti.append(f"{ad} (yanlis gerekce: {hata[0][:60]})")
            print(f"  [KACTI]    {ad}")
            print(f"             -> beklenen '{bekle}', gelen: {hata[0][:70]}")
        else:
            kacti.append(ad)
            print(f"  [KACTI]    {ad}")


print("=" * 66)
print(" KONTROL DENEYI — PAKET DOGRULAMASI KUSUR YAKALIYOR MU")
print("=" * 66)

_tmp = tempfile.mkdtemp()
SAGLAM = os.path.join(_tmp, "goktungu")
os.makedirs(SAGLAM)
print("--- Saglam agac kuruluyor ---")
n = PM.agac_kur(SAGLAM, False)
temel = PM.dogrula(SAGLAM, False)
if temel:
    print(f"  [DUR] saglam agac dogrulamayi GECMIYOR: {temel[:3]}")
    sys.exit(1)
print(f"  [OK] {n} dosya, dogrulama temiz — enjeksiyona hazir")

print("--- 1. GIZLILIK: sizmamasi gereken varliklar ---")


def _diz(agac, ad, dosya="x.txt", icerik="gizli"):
    d = os.path.join(agac, ad)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, dosya), "w") as f:
        f.write(icerik)


olc("sertifika/ sizdi (TLS ozel anahtari)",
    lambda a: _diz(a, "sertifika", "anahtar.pem", "-----BEGIN KEY-----"),
    "SIZDI: sertifika")
olc("avatars/ sizdi (kullanici gorselleri)",
    lambda a: _diz(a, "avatars", "1.png"), "SIZDI: avatars")
olc("dron_loglari/ sizdi (baska kurumun ucus kaydi)",
    lambda a: _diz(a, "dron_loglari", "ucus.bin"), "SIZDI: dron_loglari")
olc("ai_kayitlar/ sizdi",
    lambda a: _diz(a, "ai_kayitlar", "k.jpg"), "SIZDI: ai_kayitlar")
olc("ai_yuzler/ sizdi (biyometrik veri)",
    lambda a: _diz(a, "ai_yuzler", "yuz.dat"), "SIZDI: ai_yuzler")
olc("harita_cache/ sizdi",
    lambda a: _diz(a, "harita_cache", "t.png"), "SIZDI: harita_cache")
olc("sitl/ sizdi (mimariye bagli ikili)",
    lambda a: _diz(a, "sitl", "arducopter"), "SIZDI: sitl")
olc("araclar/ sizdi (yalniz sinav betigi)",
    lambda a: _diz(a, "araclar", "sinav_x.py"), "SIZDI: araclar")

print("--- 2. IC ARAC SIZMASI: sinav/tani betikleri ---")


def _dosya(agac, bagil, icerik="# ic arac\n"):
    y = os.path.join(agac, bagil)
    os.makedirs(os.path.dirname(y), exist_ok=True)
    with open(y, "w") as f:
        f.write(icerik)


olc("kokte sinav_ betigi sizdi",
    lambda a: _dosya(a, "sinav_gizli.py"), "sinav_gizli.py")
olc("assets/python altinda dene_ betigi sizdi",
    lambda a: _dosya(a, "assets/python/dene_bir.py"), "dene_bir.py")
olc("goktungu/ icinde olc_ betigi sizdi",
    lambda a: _dosya(a, "assets/python/goktungu/olc_tani.py"), "olc_tani.py")
olc("web altinda kontrol_ betigi sizdi",
    lambda a: _dosya(a, "assets/web/kontrol_x.py"), "kontrol_x.py")
olc(".pyc dosyasi sizdi",
    lambda a: _dosya(a, "assets/web/js/onbellek.pyc"), "onbellek.pyc")
olc(".log dosyasi sizdi",
    lambda a: _dosya(a, "ai_isci.log"), "ai_isci.log")

print("--- 3. YAPI EKSIKLIGI: zorunlu dosyalar ---")


def _sil(agac, bagil):
    y = os.path.join(agac, bagil)
    if os.path.isdir(y):
        shutil.rmtree(y)
    elif os.path.exists(y):
        os.remove(y)


olc("main.py eksik", lambda a: _sil(a, "main.py"), "eksik: main.py")
olc("lisans.py eksik (5.000 $ lisans hic dogrulanmaz)",
    lambda a: _sil(a, "assets/python/goktungu/lisans.py"),
    "eksik: assets/python/goktungu/lisans.py")
olc("sunucu.py eksik", lambda a: _sil(a, "assets/python/goktungu/sunucu.py"),
    "eksik: assets/python/goktungu/sunucu.py")
olc("index.html eksik", lambda a: _sil(a, "assets/web/index.html"),
    "assets/web/index.html")
olc("js/surum.js eksik", lambda a: _sil(a, "assets/web/js/surum.js"),
    "eksik: assets/web/js/surum.js")
olc("lib/ eksik (harita cizilmez)", lambda a: _sil(a, "assets/web/lib"),
    "eksik: assets/web/lib")
olc("istasyon2/ eksik (GCCDUAL)", lambda a: _sil(a, "assets/web/istasyon2"),
    "eksik: assets/web/istasyon2")
olc("ai_sunucu.py eksik", lambda a: _sil(a, "assets/python/ai_sunucu.py"),
    "eksik: assets/python/ai_sunucu.py")

print("--- 4. YOL COZUMU: assets derinligi (sessiz kusur) ---")


def _derinlik_kaydir(agac):
    """goktungu/ paketini bir seviye yukari tasir.

    Dosyalar hala 'var' ama `sabitler.py` __file__ uzerinden hesap
    yaptigi icin WEB_KOKU yedege duser: HTTP sunucusu ayakta gorunur,
    BOS sayfa servis eder. Bu tam olarak canli sunucuda yakalanan
    tuzagin paket karsiligidir.
    """
    shutil.move(os.path.join(agac, "assets", "python", "goktungu"),
                os.path.join(agac, "goktungu"))


olc("goktungu/ bir seviye yukari kaydi (BOS sayfa)", _derinlik_kaydir,
    "eksik: assets/python/goktungu/sunucu.py")


def _web_kaydir(agac):
    """web icerigi assets/web yerine assets/ altina kondu."""
    kaynak = os.path.join(agac, "assets", "web")
    hedef = os.path.join(agac, "assets", "web_yanlis")
    shutil.move(kaynak, hedef)


olc("assets/web/ yanlis adla kuruldu", _web_kaydir,
    "assets/web/index.html")


def _index_bos(agac):
    """index.html SILINMEDI ama WEB_KOKU altindan cikarildi.

    Yapi olcumu 'index.html eksik' der; ama asil onemlisi 4. asamanin
    da bunu bagimsiz yakalamasi: dosya varligi ile yol cozumu AYRI
    sorulardir.
    """
    os.remove(os.path.join(agac, "assets", "web", "index.html"))


olc("WEB_KOKU altinda index.html yok", _index_bos,
    "index.html")

print("--- 5. LISANS MODULU: gomulu anahtar ve davranis ---")


def _anahtar_boz(agac):
    """Gomulu acik anahtari bozar.

    Sonuc: merkezin urettigi GECERLI lisans reddedilir. Musteri 5.000 $
    odemis ve yazilim yetkilerini hic acmaz. Paket 'saglam' gorunur.
    """
    y = os.path.join(agac, "assets", "python", "goktungu", "lisans.py")
    with open(y, "r", encoding="utf-8") as f:
        m = f.read()
    m = m.replace('ACIK_ANAHTAR_B64 = "', 'ACIK_ANAHTAR_B64 = "X')
    with open(y, "w", encoding="utf-8") as f:
        f.write(m)


olc("gomulu acik anahtar bozuldu", _anahtar_boz, "lisans")


def _anahtar_bosalt(agac):
    y = os.path.join(agac, "assets", "python", "goktungu", "lisans.py")
    with open(y, "r", encoding="utf-8") as f:
        m = f.read()
    import re as _re
    m = _re.sub(r'ACIK_ANAHTAR_B64 = "[^"]*"',
                'ACIK_ANAHTAR_B64 = ""', m)
    with open(y, "w", encoding="utf-8") as f:
        f.write(m)


olc("gomulu acik anahtar BOS", _anahtar_bosalt, "lisans")


def _lisansli_yalan(agac):
    """Lisans dosyasi yokken `lisansli: True` doner.

    Bu, ust sinirin lisanssiz kurulumda da uygulanmasi demektir:
    kullanicinin sahada v2.4.24 ile ucan kurulumunda radar ve GCCDUAL
    menuleri KAYBOLUR. Dogrudan gerileme.
    """
    y = os.path.join(agac, "assets", "python", "goktungu", "lisans.py")
    with open(y, "r", encoding="utf-8") as f:
        m = f.read()
    m = m.replace('"lisansli": False,', '"lisansli": True,')
    with open(y, "w", encoding="utf-8") as f:
        f.write(m)


olc("lisanssiz kurulum 'lisansli' sandi (gerileme)", _lisansli_yalan,
    "lisans")

print("--- 6. AI MODELLERI: --ai-dahil sozlesmesi ---")


def _ai_sok(agac):
    """--ai-dahil ISTENMEDIGI halde 38,7 MB model pakete girdi."""
    _diz(agac, "ai_modeller", "face_recognition_sface_2021dec.onnx", "x")


olc("ai_modeller/ istenmedigi halde sizdi", _ai_sok,
    "SIZDI: ai_modeller")

shutil.rmtree(_tmp, ignore_errors=True)

print("=" * 66)
toplam = gecti + len(kacti)
print(f" SONUC: {toplam} enjeksiyon, {gecti} YAKALANDI, "
      f"{len(kacti)} KACTI")
if kacti:
    print(" KOR NOKTALAR:")
    for a in kacti:
        print(f"   - {a}")
print("=" * 66)
sys.exit(1 if kacti else 0)
