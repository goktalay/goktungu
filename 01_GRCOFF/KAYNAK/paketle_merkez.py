#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""paketle_merkez: MERKEZ UYGULAMA dagitim paketi ureticisi.

Merkez Uygulama, 5.000 $ tek seferlik lisansla satilan TAM GOKTUNGU
kurulumudur. Kopru yaziliminin (`~/goktungu_kopru/paketle.py`) beyaz liste
desenini izler ama icerigi tamamen farklidir.

=====================================================================
NEDEN BEYAZ LISTE (kara liste DEGIL)
=====================================================================
Gelistirme dizininde 90 dosya var ve bunlarin 60'i sinav/tani betigi
(`sinav_*`, `dene_*`, `olc_*`, `dogrula_*`, `kontrol_*`, `test_*`).
Kara liste kullanmak, yarin eklenecek `arastir_yeni.py`nin sessizce
musteri paketine girmesi anlamina gelir. Beyaz listede yeni dosya
UNUTULUR ama SIZMAZ; ikisi arasinda ikincisi tercih edilir.

Ayni gerekce `veri/`, `sertifika/`, `avatars/` icin daha da agirdir:
bunlar baska kurumun ucus kayitlarini, TLS ozel anahtarini ve kullanici
gorsellerini tasir.

=====================================================================
DUZ -> assets/ YOL ESLEMESI (kullanici istegi)
=====================================================================
Kullanici acikca istedi: "klasorde sadece main.py ve assets klasoru
kalsin, assets klasoru icinde de sadece web ve python klasoru kalsin".

Gelistirme dizini hala DUZ yapida (`goktungu/`, `js/`, `css/` kokte).
`goktungu/sabitler.py` iki yapiyi da destekliyor ve ayrimi DOSYA VARLIGIYLA
olcuyor (varsaymiyor): `goktungu/` paketinin iki ust dizini `assets/python`
ise YENI yapi.

    <kok>/main.py
    <kok>/assets/python/goktungu/      <- goktungu/
    <kok>/assets/python/ai_sunucu.py
    <kok>/assets/web/index.html     <- index.html
    <kok>/assets/web/js/ css/ lib/ pwa/ ...
    <kok>/veri/                     <- CALISMA ANINDA olusur

KRITIK TUZAK: `sabitler.py` ve `mk_ayar.py` yollari `__file__` uzerinden
hesaplar (`dirname(dirname(abspath(__file__)))`). Bu, canli sunucuda
somut olarak yakalandi: modulleri yanlis derinlikte bir dizine koyunca
veri koku `/tmp/veri` oldu ve orada YENI bir imza anahtari uretildi.

Pakette ayni tuzak gecerli. `goktungu/` bir seviye yukari ya da asagi
kayarsa:
  - `WEB_KOKU` yedege duser -> HTTP sunucusu ayakta gorunur ama BOS
    sayfa servis eder (sessiz kusur)
  - veri koku kayar -> lisans dosyasi bulunamaz, sema sihirbazi her
    acilista yeniden acilir

Bu yuzden dogrulama yalniz dosya varligini degil, YOLLARIN DOGRU
COZULDUGUNU de olcer (`--dogrula` asamasi 4).

=====================================================================
SURUM TEK KAYNAKTAN OKUNUR
=====================================================================
`js/surum.js` -> `const GCS_SURUM = "2.4.64"`. Python tarafinda sürüm
sabiti YOK ve BILEREK eklenmedi: ikinci bir surum kaynagi acmak, koprude
zaten giderilen kusuru ("iki ayri surum kaynagi olur, biri unutulur,
paket yanlis surumle yayinlanir") GCS'e tasimak olurdu.

Okuma basarisiz olursa paket URETILMEZ. Sessizce varsayilana dusmek,
yanlis surum etiketiyle musteriye paket gitmesi demektir.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

KOK = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------
# BEYAZ LISTE
# ---------------------------------------------------------------------
# Python tarafi: assets/python/ altina gider.
PYTHON_DIZIN = ("goktungu",)
PYTHON_DOSYA = ("ai_sunucu.py", "track_verisi_dinleyici.py")

# Web tarafi: assets/web/ altina gider.
WEB_DIZIN = ("js", "css", "lib", "pwa", "istasyon2")
# KURUMSAL PANEL PAKETE KONMAZ - BILINCLI KARAR (v2.4.66).
#
# Ilk yaklasim `company/` dizinini merkez_web'den pakete kopyalamakti;
# GERI ALINDI. Olculen neden: panel 23 ayri `/api/firma/...` ucu cagirir
# ve bu uclarin HICBIRI GCS sunucusunda yoktur (`/api/firma` yolu kaynak
# agacinda 0 kez gecer). Dosyalari pakete koymak paneli acar ama tek
# satir veri gelmez - sessiz kusur, 404'ten daha kotu.
#
# Bunun yerine `sunucu.py` icindeki do_GET `/company/` istegini merkez
# sunucuya 302 ile yonlendirir; panel orada tam islevli calisir.
# `admin/` de girmez: ust yonetici (sistem yoneticisi) panelidir.
WEB_DOSYA = (
    "index.html", "flight.html", "video.html",
    "manifest.json", "sw.js", "rapor_i18n.json",
    "dron.glb",
    "logo.png", "goktungu.webp", "goktungu_acik.webp",
)

# Kok dizinde kalanlar.
KOK_DOSYA = ("main.py", "requirements.txt", "goktungu_guncelleyici.py",
             "jetson_ai_kur.sh")   # v2.4.218: Jetson GPU kurulum betigi (Linux)

# AI modelleri: `--ai-dahil` ile eklenir (38,7 MB).
AI_MODEL_DIZIN = "ai_modeller"

# Hicbir kosulda girmeyecekler (beyaz listede olsalar bile ayiklanir).
YASAK_DESEN = (
    re.compile(r"__pycache__"),
    re.compile(r"\.pyc$"),
    re.compile(r"^sinav_"),
    re.compile(r"^dene_"),
    re.compile(r"^olc_"),
    re.compile(r"^dogrula_"),
    re.compile(r"^kontrol_"),
    re.compile(r"^test_"),
    re.compile(r"^canli_"),
    re.compile(r"\.log$"),
    re.compile(r"^\."),
)


def yasak(ad):
    """Dosya ADI (yol degil) yasak desenlerden birine uyuyor mu."""
    return any(d.search(ad) for d in YASAK_DESEN)


def surum_oku():
    """Surumu js/surum.js'ten okur. Basarisizsa None doner."""
    yol = os.path.join(KOK, "js", "surum.js")
    try:
        with open(yol, "r", encoding="utf-8") as f:
            metin = f.read()
    except OSError:
        return None
    m = re.search(r'GCS_SURUM\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"', metin)
    return m.group(1) if m else None


def _kopyala_dizin(kaynak, hedef, sayac):
    """Dizini yasak desenleri ayiklayarak kopyalar."""
    for kok, dizinler, dosyalar in os.walk(kaynak):
        # Yasak dizinleri gezinti agacindan CIKAR (icine girmeyelim).
        dizinler[:] = [d for d in dizinler if not yasak(d)]
        bagil = os.path.relpath(kok, kaynak)
        hedef_kok = hedef if bagil == "." else os.path.join(hedef, bagil)
        os.makedirs(hedef_kok, exist_ok=True)
        for ad in dosyalar:
            if yasak(ad):
                continue
            shutil.copy2(os.path.join(kok, ad),
                         os.path.join(hedef_kok, ad))
            sayac[0] += 1


def agac_kur(hedef, ai_dahil):
    """Paket agacini `hedef` altinda YENI (assets/) yapida kurar."""
    sayac = [0]
    py_kok = os.path.join(hedef, "assets", "python")
    web_kok = os.path.join(hedef, "assets", "web")
    os.makedirs(py_kok, exist_ok=True)
    os.makedirs(web_kok, exist_ok=True)

    for d in PYTHON_DIZIN:
        k = os.path.join(KOK, d)
        if not os.path.isdir(k):
            raise SystemExit(f"[KUSUR] zorunlu dizin yok: {d}")
        _kopyala_dizin(k, os.path.join(py_kok, d), sayac)

    for ad in PYTHON_DOSYA:
        k = os.path.join(KOK, ad)
        if not os.path.isfile(k):
            raise SystemExit(f"[KUSUR] zorunlu dosya yok: {ad}")
        shutil.copy2(k, os.path.join(py_kok, ad))
        sayac[0] += 1

    for d in WEB_DIZIN:
        k = os.path.join(KOK, d)
        if not os.path.isdir(k):
            raise SystemExit(f"[KUSUR] zorunlu dizin yok: {d}")
        _kopyala_dizin(k, os.path.join(web_kok, d), sayac)

    for ad in WEB_DOSYA:
        k = os.path.join(KOK, ad)
        if not os.path.isfile(k):
            raise SystemExit(f"[KUSUR] zorunlu dosya yok: {ad}")
        shutil.copy2(k, os.path.join(web_kok, ad))
        sayac[0] += 1

    for ad in KOK_DOSYA:
        k = os.path.join(KOK, ad)
        if not os.path.isfile(k):
            raise SystemExit(f"[KUSUR] zorunlu dosya yok: {ad}")
        shutil.copy2(k, os.path.join(hedef, ad))
        sayac[0] += 1

    if ai_dahil:
        k = os.path.join(KOK, AI_MODEL_DIZIN)
        if not os.path.isdir(k):
            raise SystemExit(f"[KUSUR] --ai-dahil istendi ama "
                             f"{AI_MODEL_DIZIN}/ yok")
        _kopyala_dizin(k, os.path.join(hedef, AI_MODEL_DIZIN), sayac)

    # Calisma dizinleri BOS olarak olusturulur; icerik ASLA kopyalanmaz.
    # `veri/` lisans dosyasinin ve semanin evidir.
    for d in ("veri",):
        os.makedirs(os.path.join(hedef, d), exist_ok=True)

    return sayac[0]


def dogrula(kok, ai_dahil):
    """Kurulan agaci OLCER. Hata listesi doner (bos = saglam)."""
    hata = []

    def olmali(bagil, dizin=False):
        y = os.path.join(kok, bagil)
        var = os.path.isdir(y) if dizin else os.path.isfile(y)
        if not var:
            hata.append(f"eksik: {bagil}")

    def olmamali(bagil):
        y = os.path.join(kok, bagil)
        if os.path.exists(y):
            hata.append(f"SIZDI: {bagil}")

    # --- 1. Zorunlu yapi ---
    olmali("main.py")
    olmali("assets/python/goktungu/sunucu.py")
    olmali("assets/python/goktungu/lisans.py")
    olmali("assets/python/goktungu/sabitler.py")
    olmali("assets/python/ai_sunucu.py")
    olmali("assets/python/track_verisi_dinleyici.py")
    olmali("assets/web/index.html")
    olmali("assets/web/js/surum.js")
    olmali("assets/web/js/program_ayar.js")
    olmali("assets/web/css", dizin=True)
    olmali("assets/web/lib", dizin=True)
    olmali("assets/web/pwa", dizin=True)
    olmali("assets/web/istasyon2", dizin=True)

    # --- 2. Sizmamasi gerekenler ---
    # Bunlar OLCULUR, varsayilmaz: her biri gercek bir gizlilik ya da
    # tasinabilirlik kusuru.
    olmamali("sertifika")          # TLS ozel anahtari
    olmamali("avatars")            # kullanici gorselleri
    olmamali("dron_loglari")       # baska kurumun ucus kaydi
    olmamali("ai_kayitlar")
    olmamali("ai_yuzler")
    olmamali("harita_cache")
    olmamali("sitl")               # mimariye bagli ikili (ARM/x86 kazasi)
    olmamali("araclar")            # yalniz sinav betigi
    # Ust yonetici paneli musteri kurulumuna GIRMEMELI.
    olmamali("assets/web/admin")
    olmamali("assets/python/goktungu/__pycache__")

    if not ai_dahil:
        olmamali(AI_MODEL_DIZIN)
    else:
        olmali(f"{AI_MODEL_DIZIN}/face_recognition_sface_2021dec.onnx")

    # --- 3. Sinav/tani betigi sizmasi ---
    for gezi_kok, _dizinler, dosyalar in os.walk(kok):
        for ad in dosyalar:
            if yasak(ad):
                bagil = os.path.relpath(os.path.join(gezi_kok, ad), kok)
                hata.append(f"SIZDI (yasak desen): {bagil}")

    # --- 4. YOLLAR DOGRU COZULUYOR MU (en kritik olcum) ---
    # Dosya varligi YETMEZ: `sabitler.py` yollari `__file__` uzerinden
    # hesaplar. Agac dogru gorunup yanlis derinlikte olabilir; o zaman
    # WEB_KOKU yedege duser ve HTTP sunucusu BOS sayfa servis eder.
    # Bu yuzden moduller GERCEKTEN ice aktarilip yollar sorulur.
    betik = (
        "import json, os, sys\n"
        "kok = sys.argv[1]\n"
        "sys.path.insert(0, os.path.join(kok, 'assets', 'python'))\n"
        "from goktungu import sabitler as s\n"
        "cikti = {}\n"
        "for ad in ('WEB_KOKU', 'PROJE_KOKU', 'VERI_KOKU'):\n"
        "    cikti[ad] = str(getattr(s, ad, ''))\n"
        "print(json.dumps(cikti))\n"
    )
    try:
        ck = subprocess.run([sys.executable, "-c", betik, kok],
                            capture_output=True, text=True, timeout=90)
        if ck.returncode != 0:
            hata.append(f"yol cozumu CALISMADI: {ck.stderr.strip()[:200]}")
        else:
            yollar = json.loads(ck.stdout.strip().splitlines()[-1])
            web = yollar.get("WEB_KOKU", "")
            bek_web = os.path.join(kok, "assets", "web")
            if os.path.realpath(web) != os.path.realpath(bek_web):
                hata.append(f"WEB_KOKU yanlis cozuldu: {web} "
                            f"(beklenen {bek_web})")
            if not os.path.isfile(os.path.join(web, "index.html")):
                hata.append("WEB_KOKU altinda index.html YOK "
                            "(bos sayfa servis edilir)")
    except Exception as e:
        hata.append(f"yol cozumu olculemedi: {e}")

    # --- 5. Lisans modulu GOMULU ANAHTARLA calisiyor mu ---
    #
    # KRITIK: `yetki_ozeti()` cagirmak YETMEZ. Lisans dosyasi yokken o
    # islev acik anahtari HIC KULLANMAZ. Yani bozuk bir anahtarla
    # uretilen paket bu olcumu gecer, musteri lisansini koydugunda
    # GECERLI lisans reddedilir ve 5.000 $ odemis musteri yazilimi
    # acamaz. Kontrol deneyi bu kor noktayi somut olarak yakaladi.
    #
    # Bu yuzden gomulu anahtarin GERCEK BIR IMZAYI dogruladigi olculur.
    # Asagidaki govde+imza cifti, merkezin gizli anahtariyla uretilmis
    # ve canli olarak dogrulanmis sabit bir ornektir (bkz.
    # canli_lisans_uctan_uca.py). Gizli anahtar burada YOK; yalnizca
    # onun urettigi imza var.
    betik2 = (
        "import json, os, sys\n"
        "kok = sys.argv[1]\n"
        "sys.path.insert(0, os.path.join(kok, 'assets', 'python'))\n"
        "from goktungu import lisans\n"
        "assert len(lisans.ACIK_ANAHTAR_B64) > 40, 'anahtar bos'\n"
        "o = lisans.yetki_ozeti()\n"
        "assert o['lisansli'] is False, 'lisanssiz kurulum lisansli sandi'\n"
        "assert o['kaynak'] == 'merkez', 'kaynak yanlis'\n"
        "g = json.loads(sys.argv[2])\n"
        "im = sys.argv[3]\n"
        "ham = lisans.govde_bayt(g)\n"
        "assert lisans.imza_dogrula(ham, im), "
        "'GOMULU ANAHTAR gercek imzayi dogrulamiyor'\n"
        "bozuk = im[:-6] + ('AAAAAA' if im[-6:] != 'AAAAAA' else 'BBBBBB')\n"
        "assert not lisans.imza_dogrula(ham, bozuk), "
        "'bozuk imza KABUL edildi'\n"
        "g2 = json.loads(sys.argv[2])\n"
        "g2['yetkiler']['radar'] = not g2['yetkiler']['radar']\n"
        "assert not lisans.imza_dogrula(lisans.govde_bayt(g2), im), "
        "'yetki kurcalamasi KABUL edildi'\n"
        "print('LISANS_OK')\n"
    )
    try:
        ck2 = subprocess.run([sys.executable, "-c", betik2, kok,
                              json.dumps(ORNEK_GOVDE), ORNEK_IMZA_B64],
                             capture_output=True, text=True, timeout=90)
        if "LISANS_OK" not in ck2.stdout:
            hata.append(f"lisans modulu pakette CALISMIYOR: "
                         f"{(ck2.stderr or ck2.stdout).strip()[:200]}")
    except Exception as e:
        hata.append(f"lisans modulu olculemedi: {e}")

    return hata


# ---------------------------------------------------------------------
# GOMULU ANAHTAR DOGRULAMA ORNEGI
# ---------------------------------------------------------------------
# Merkezin GERCEK gizli anahtariyla uretilmis govde+imza cifti.
# `canli_lisans_uctan_uca.py` ile canli merkezde uretildi ve hem
# `cryptography` hem saf Python yolunda dogrulandi.
#
# Buradaki amac paketin gomulu ACIK anahtarinin ise yarar oldugunu
# kanitlamak. Gizli anahtar merkezde kalir, bu dosyada YOKTUR.
ORNEK_GOVDE = {
    "surum": 1,
    "firma_id": 1,
    "firma_unvan": "VEILOX Savunma Teknolojileri A.S.",
    "lisans_uid": "PKTDOGRULAMA01",
    "yetkiler": {"sinirsiz": True, "ai": True,
                 "radar": True, "gccdual": True},
}
# Uretim: merkez sunucuda `imza_ornek_uret.py` (bkz. ~/merkez_calisma/).
# Anahtar: ZDnJD1vKUwNUkfAx84JcGoRHsU3Vwyh4s/CHzZXCVRo=
# Imza kokü: /opt/goktungu/merkez/veri/imza  |  Kanonik govde: 171 bayt
ORNEK_IMZA_B64 = (
    "WFJ9qDt6hZw8vEoRRigZwQhw22hHBvepaKwrrloEHQnT7uGlV77R+NVAwbU/Y0ZIhGlu"
    "dB9bEhZ8cpuAb7WADg=="
)


def pycache_temizle(kok):
    """Ice aktarmanin urettigi __pycache__ dizinlerini siler.

    NEDEN GEREKLI: `dogrula()` yol cozumu ve lisans olcumu icin
    moduleri GERCEKTEN ice aktarir; Python bu sirada `.pyc` yazar.
    Arsivleme dogrulamadan SONRA yapildigi icin, temizlenmezse
    musteriye giden pakete `.pyc` dosyalari girer.

    Bu, paketleyicinin kendi dogrulamasi tarafindan yakalandi:
    arsiv acilip olculdugunde 4 sizma bildirildi.
    """
    n = 0
    for gezi_kok, dizinler, _d in os.walk(kok):
        for d in list(dizinler):
            if d == "__pycache__":
                shutil.rmtree(os.path.join(gezi_kok, d), ignore_errors=True)
                dizinler.remove(d)
                n += 1
    return n


def _boyut(yol):
    t = 0
    for k, _d, dosyalar in os.walk(yol):
        for ad in dosyalar:
            try:
                t += os.path.getsize(os.path.join(k, ad))
            except OSError:
                pass
    return t


def _mb(b):
    return f"{b / (1024 * 1024):.1f} MB"


def arsiv_uret(agac, cikti_dizin, surum, ai_dahil):
    """zip (Windows) ve tar.gz (Linux) uretir; SHA-256 ozetlerini doner."""
    os.makedirs(cikti_dizin, exist_ok=True)
    etiket = f"{surum}{'-ai' if ai_dahil else ''}"
    ozet = {}

    zip_yol = os.path.join(cikti_dizin, f"GOKTUNGU-Merkez-{etiket}.zip")
    with zipfile.ZipFile(zip_yol, "w", zipfile.ZIP_DEFLATED) as z:
        for kok, _d, dosyalar in os.walk(agac):
            for ad in dosyalar:
                tam = os.path.join(kok, ad)
                z.write(tam, os.path.relpath(tam, agac))
    ozet[zip_yol] = _sha256(zip_yol)

    tar_yol = os.path.join(cikti_dizin, f"GOKTUNGU-Merkez-{etiket}.tar.gz")
    with tarfile.open(tar_yol, "w:gz") as t:
        t.add(agac, arcname="goktungu")
    ozet[tar_yol] = _sha256(tar_yol)

    return ozet


def _sha256(yol):
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def arsiv_dogrula(arsiv, ai_dahil):
    """Uretilen arsivi GERCEKTEN acar ve dogrular.

    Kopru paketleyicisinin dersi: arsivi yazmak basarili gorunup icerik
    eksik olabilir. Tek guvenilir olcum acip bakmaktir.
    """
    hata = []
    with tempfile.TemporaryDirectory() as gecici:
        if arsiv.endswith(".zip"):
            with zipfile.ZipFile(arsiv) as z:
                z.extractall(gecici)
            kok = gecici
        else:
            with tarfile.open(arsiv) as t:
                t.extractall(gecici)
            kok = os.path.join(gecici, "goktungu")
        # Acilan agacta once SIZMA olculur (henuz ice aktarma yapilmadi,
        # yani gorulen her __pycache__ GERCEKTEN arsivden gelmistir).
        hata = dogrula(kok, ai_dahil)
    return hata


def main():
    ap = argparse.ArgumentParser(
        description="MERKEZ UYGULAMA dagitim paketi ureticisi")
    ap.add_argument("--ai-dahil", action="store_true",
                    help="AI modellerini pakete gomer (+38,7 MB); "
                         "kapali devre musteri icin gerekli")
    ap.add_argument("--cikti", default=os.path.join(KOK, "dagitim"),
                    help="arsivlerin yazilacagi dizin")
    ap.add_argument("--sadece-dogrula", action="store_true",
                    help="agaci kurar ve olcer, arsiv uretmez")
    # --agac-birak: dogrulanmis agaci `dagitim/agac/` altina BIRAKIR.
    # deb_merkez_uret.py bunu kullanir; boylece paket icerigi TEK
    # beyaz listeden gelir. Iki ayri liste tutulsa biri guncellenmeyi
    # unutulur ve zip ile .deb ayrisir.
    ap.add_argument("--agac-birak", action="store_true",
                    help="dogrulanmis agaci dagitim/agac/ altina birakir "
                         "(deb ureticisi bunu kullanir)")
    ap.add_argument("--arsiv-yok", action="store_true",
                    help="zip/tar.gz uretmez; --agac-birak ile birlikte "
                         "kullanilir")
    a = ap.parse_args()

    surum = surum_oku()
    if not surum:
        # Sessizce varsayilana DUSULMEZ: yanlis surum etiketiyle
        # musteriye paket gitmesi, paket uretilmemesinden kotudur.
        raise SystemExit("[KUSUR] surum js/surum.js'ten okunamadi; "
                         "paket URETILMEDI")

    print("=" * 66)
    print(f" MERKEZ UYGULAMA PAKETI  v{surum}"
          f"{'  (AI modelleri DAHIL)' if a.ai_dahil else ''}")
    print("=" * 66)

    with tempfile.TemporaryDirectory() as gecici:
        agac = os.path.join(gecici, "goktungu")
        os.makedirs(agac)
        n = agac_kur(agac, a.ai_dahil)
        print(f"  [OK] {n} dosya kopyalandi, agac boyutu {_mb(_boyut(agac))}")

        hata = dogrula(agac, a.ai_dahil)
        if hata:
            print(f"  [KUSUR] agac dogrulamasi {len(hata)} sorun buldu:")
            for h in hata[:30]:
                print(f"     - {h}")
            raise SystemExit(1)
        print("  [OK] agac dogrulandi (yapi, sizma, yol cozumu, lisans)")

        # Dogrulama moduleri ice aktardi ve __pycache__ uretti; ARSIVDEN
        # ONCE temizlenmeli. Aksi halde musteri paketine .pyc girer.
        n_pyc = pycache_temizle(agac)
        if n_pyc:
            print(f"  [OK] dogrulamanin urettigi {n_pyc} __pycache__ "
                  f"dizini temizlendi")

        # Agaci birakma ARSIVDEN ONCE yapilir: arsiv uretimi basarisiz
        # olsa bile .deb ureticisi calisabilir durumda kalir.
        if a.agac_birak:
            hedef = os.path.join(a.cikti, "agac")
            if os.path.isdir(hedef):
                shutil.rmtree(hedef)
            os.makedirs(os.path.dirname(hedef), exist_ok=True)
            shutil.copytree(agac, hedef)
            # Kopyalama sirasinda yeni __pycache__ olusmaz, ancak
            # kaynakta kalmis olabilecekler icin yine temizle: .deb
            # sinavi "__pycache__ pakete GIRMEMIS" olcumu yapiyor.
            n2 = pycache_temizle(hedef)
            print(f"  [OK] agac birakildi: {hedef}"
                  + (f" ({n2} __pycache__ temizlendi)" if n2 else ""))

        if a.sadece_dogrula or a.arsiv_yok:
            gerekce = ("--sadece-dogrula" if a.sadece_dogrula
                       else "--arsiv-yok")
            print(f"  [BILGI] {gerekce}: arsiv uretilmedi")
            return

        ozetler = arsiv_uret(agac, a.cikti, surum, a.ai_dahil)
        for yol, sha in ozetler.items():
            print(f"  [OK] {os.path.basename(yol)}  "
                  f"{_mb(os.path.getsize(yol))}")
            print(f"       sha256 {sha}")

        # Uretilen her arsiv ACILIP dogrulanir.
        for yol in ozetler:
            h = arsiv_dogrula(yol, a.ai_dahil)
            if h:
                print(f"  [KUSUR] {os.path.basename(yol)} acildiginda "
                      f"{len(h)} sorun:")
                for x in h[:20]:
                    print(f"     - {x}")
                raise SystemExit(1)
            print(f"  [OK] {os.path.basename(yol)} acilip dogrulandi")

    print("=" * 66)
    print(" SONUC: paketler uretildi ve dogrulandi")
    print("=" * 66)


if __name__ == "__main__":
    main()
