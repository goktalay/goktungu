#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GOKTUNGU v2.4.47 — MIMARI (aarch64) SITL SINAVI

Kullanim (kurulum kokunde ya da gelistirme dizininde):
    python3 sinav_2447_mimari.py

Neyi olcer: kullanicinin aarch64 makinesinde sanal dronun
calistirilamamasina yol acan kusur zincirinin kapandigini.

Kusur zinciri (kullanici tarafindan sirayla bildirildi):
  1. v2.4.45 -> [Errno 13] Permission denied
        Dosya vardi, +x biti yoktu.            (v2.4.46'da kapatildi)
  2. v2.4.46 -> [Errno 8] Exec format error
        Izin duzelince cekirdek dosyayi calistirmayi denedi ve dosyanin
        KENDISINE itiraz etti.                  (teshis v2.4.46'da eklendi)
  3. v2.4.46 kurtarma yolu -> ayni hata IKINCI KEZ
        `_mimari_kurtar` aarch64'te `SITL_arm_linux_gnueabihf` (32-BIT
        ARM) ikilisini indirdi, cunku ArduPilot dagitiminda aarch64 SITL
        YOKTUR (olculdu: SITL_arm64_linux_gnu -> HTTP 404). 32-bit ARM
        ikilisi de aarch64'te calismadi.

v2.4.47 cozumu: aarch64 ikilileri ArduPilot kaynagindan capraz derlenip
(`--static`, sifir dinamik bagimlilik) `_aarch64` sonekiyle pakete
gomuldu; secim mantigi mimariye duyarli hale getirildi.

Sinav gercek dosyalar uzerinde calisir. `platform.machine()` yalnizca
BU MAKINEDE bulunmayan mimarilerin davranisini olcmek icin yamalanir;
dosya bicimi/mimari olcumleri her zaman gercek dosyalardan yapilir.
"""
import importlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile

GECTI = 0
KALDI = 0
BASARISIZLAR = []


def olc(baslik, kosul, ayrinti=""):
    global GECTI, KALDI
    if kosul:
        GECTI += 1
        print("[GECTI] %s" % baslik)
    else:
        KALDI += 1
        BASARISIZLAR.append(baslik)
        print("[KALDI] %s" % baslik)
        if ayrinti:
            print("        %s" % str(ayrinti)[:300])


def bolum(m):
    print()
    print("--- %s " % m + "-" * max(0, 58 - len(m)))


def kok_bul():
    """Hem kurulum kokunde hem gelistirme dizininde calisabilmeli."""
    burasi = os.path.dirname(os.path.abspath(__file__))
    for aday in (burasi, os.path.join(burasi, "goktungu")):
        if os.path.isfile(os.path.join(aday, "goktungu", "sitl.py")):
            return aday
    return burasi


KOK = kok_bul()
sys.path.insert(0, KOK)
from goktungu import sitl  # noqa: E402

SITL_DIZIN = sitl.SITL_KLASORU
_GERCEK_MAKINE = platform.machine


def _yamala(deger):
    """platform.machine'i yamalayip sitl modulunu yeniden yukler.

    Modul seviyesindeki sonek tablosu ice alma aninda okunmadigi icin
    reload sart degil; ancak `MIMARI_SONEK` disinda makineye bagli baska
    modul sabiti eklenirse bu yaklasim onu da kapsar.
    """
    platform.machine = lambda: deger
    importlib.reload(sitl)


def _geri():
    platform.machine = _GERCEK_MAKINE
    importlib.reload(sitl)


# ======================================================================
bolum("1. Pakete gomulu aarch64 ikilileri")
# ======================================================================
# Kok gereksinim: ArduPilot aarch64 SITL yayinlamadigi icin (olculdu,
# HTTP 404) bu dosyalar PAKETTE bulunmak ZORUNDADIR. Calisma aninda
# indirilemezler.
AARCH64_IKILILER = ("arducopter_aarch64", "arduplane_aarch64")

for ad in AARCH64_IKILILER:
    yol = os.path.join(SITL_DIZIN, ad)
    var = os.path.isfile(yol)
    olc("%s pakete gomulu" % ad, var, yol)
    if not var:
        continue
    b = sitl.ikili_bicimi(yol)
    olc("%s ELF bicimi" % ad, b.get("bicim") == "elf", b.get("bicim"))
    olc("%s 64-bit" % ad, b.get("bit") == 64, b.get("bit"))
    olc("%s mimarisi AArch64 (0xb7)" % ad, b.get("makine") == 0xb7,
        "%s / %s" % (b.get("makine"), b.get("makine_ad")))
    # Boyut esigi: yer tutucu / yarim inmis dosyayi yakalar.
    boyut = os.path.getsize(yol)
    olc("%s boyutu makul (>5 MB)" % ad, boyut > 5 * 1024 * 1024,
        "%d bayt" % boyut)

# Statik baglama: kullanicinin dagitiminin glibc surumu bilinmiyor.
# Dinamik baglanmis ikili GLIBC_2.38 istiyordu ve eski dagitimlarda
# calismazdi; bu yuzden statiklik OLCULUR, varsayilmaz.
for ad in AARCH64_IKILILER:
    yol = os.path.join(SITL_DIZIN, ad)
    if not os.path.isfile(yol):
        continue
    try:
        cikti = subprocess.run(["file", "-b", yol], capture_output=True,
                               text=True, timeout=30).stdout
    except Exception as e:
        cikti = "file kosturulamadi: %s" % e
    olc("%s statik baglanmis" % ad, "statically linked" in cikti,
        cikti.strip()[:160])

# ======================================================================
bolum("2. x86-64 ikilileri korundu (gerileme)")
# ======================================================================
# Kritik: aarch64 destegi eklenirken mevcut x86 kurulumlarin bozulmamasi
# gerekir. Bu yuzden yeni dosyalar SONEKLE eklendi, eskiler DEGISTIRILMEDI.
for ad in ("arducopter", "arduplane"):
    yol = os.path.join(SITL_DIZIN, ad)
    var = os.path.isfile(yol)
    olc("%s (x86-64) hala mevcut" % ad, var, yol)
    if var:
        b = sitl.ikili_bicimi(yol)
        olc("%s hala x86-64 (0x3e)" % ad, b.get("makine") == 0x3e,
            b.get("makine_ad"))

# Windows dosyalari da dokunulmamis olmali.
for ad in ("ArduCopter.elf", "ArduPlane.elf"):
    yol = os.path.join(SITL_DIZIN, ad)
    var = os.path.isfile(yol)
    olc("%s (Windows PE) hala mevcut" % ad, var, yol)
    if var:
        olc("%s hala PE bicimi" % ad,
            sitl.ikili_bicimi(yol).get("bicim") == "pe")

# ======================================================================
bolum("3. Mimari sonek tablosu")
# ======================================================================
olc("MIMARI_SONEK tanimli", hasattr(sitl, "MIMARI_SONEK"))
olc("_mimari_sonek() tanimli", hasattr(sitl, "_mimari_sonek"))
if hasattr(sitl, "MIMARI_SONEK"):
    olc("aarch64 -> _aarch64",
        sitl.MIMARI_SONEK.get("aarch64") == "_aarch64")
    olc("arm64 -> _aarch64 (macOS/BSD adlandirmasi)",
        sitl.MIMARI_SONEK.get("arm64") == "_aarch64")
    olc("x86_64 tabloda YOK (sonek almamali)",
        "x86_64" not in sitl.MIMARI_SONEK)
    # 32-bit ARM'in soneki OLMAMALI: onun ArduPilot dagitiminda ikilisi
    # vardir ve sonek'siz ada indirilir.
    olc("armv7l tabloda YOK", "armv7l" not in sitl.MIMARI_SONEK)

# ======================================================================
bolum("4. aarch64 makinede secim (taklit mimari)")
# ======================================================================
try:
    _yamala("aarch64")
    olc("aarch64: sonek _aarch64", sitl._mimari_sonek() == "_aarch64")

    adaylar = sitl.ikili_adaylari("arducopter")
    olc("aarch64: en az 2 aday", len(adaylar) >= 2, adaylar)
    olc("aarch64: ILK aday _aarch64 sonekli",
        adaylar and adaylar[0].endswith("arducopter_aarch64"), adaylar)
    olc("aarch64: yedek aday sonek'siz (kullanici kendi derlemis olabilir)",
        len(adaylar) >= 2 and adaylar[1].endswith(os.sep + "arducopter"),
        adaylar)

    yol, model, hata = sitl.ikili_bul("multirotor")
    olc("aarch64: ikili_bul aarch64 dosyasini secti",
        bool(yol) and yol.endswith("_aarch64"), yol)
    olc("aarch64: ikili_bul hata dondurmedi", hata is None, hata)
    olc("aarch64: model dogru", model == "+", model)

    # Sabit kanat da secilmeli; yalniz copter duzeltmek yarim is olur.
    yolp, modelp, hatap = sitl.ikili_bul("sabit_kanat")
    olc("aarch64: sabit kanat da aarch64 dosyasini secti",
        bool(yolp) and yolp.endswith("arduplane_aarch64"), yolp)
    olc("aarch64: sabit kanat hatasiz", hatap is None, hatap)

    ok, eksik, ileti = sitl.hazir_mi()
    olc("aarch64: hazir_mi True", ok is True, ileti)
    olc("aarch64: acilis iletisi mimariyi bildiriyor",
        "aarch64" in (ileti or ""), ileti)
    olc("aarch64: acilis iletisi ikili sonekini bildiriyor",
        "_aarch64" in (ileti or ""), ileti)
finally:
    _geri()

# ======================================================================
bolum("5. x86_64 makinede secim (gerileme, taklit mimari)")
# ======================================================================
try:
    _yamala("x86_64")
    olc("x86_64: sonek bos", sitl._mimari_sonek() == "")
    adaylar = sitl.ikili_adaylari("arducopter")
    olc("x86_64: tek aday", len(adaylar) == 1, adaylar)
    olc("x86_64: aday sonek'siz",
        adaylar and adaylar[0].endswith(os.sep + "arducopter"), adaylar)
    yol, model, hata = sitl.ikili_bul("multirotor")
    olc("x86_64: x86 ikilisi secildi",
        bool(yol) and yol.endswith(os.sep + "arducopter"), yol)
    olc("x86_64: hatasiz", hata is None, hata)
    ok, eksik, ileti = sitl.hazir_mi()
    olc("x86_64: hazir_mi True", ok is True, ileti)
    olc("x86_64: ileti gereksiz sonek bilgisi yazmiyor",
        "_aarch64" not in (ileti or ""), ileti)
finally:
    _geri()

# ======================================================================
bolum("6. aarch64'te dosya EKSIK: anlasilir hata (en kritik senaryo)")
# ======================================================================
# Kullanicinin yasadigi durum tam buydu: klasorde x86-64 `arducopter`
# vardi, aarch64 dosyasi yoktu. Beklenen davranis: net gerekce, dogru
# cozum yolu ve 32-bit ARM indirmeye CALISMAMAK.
gecici = tempfile.mkdtemp(prefix="goktungu_2447_")
try:
    for ad in ("arducopter", "arduplane"):
        k = os.path.join(SITL_DIZIN, ad)
        if os.path.isfile(k):
            shutil.copy2(k, gecici)

    _yamala("aarch64")
    _eski_klasor = sitl.SITL_KLASORU
    sitl.SITL_KLASORU = gecici
    try:
        yol, model, hata = sitl.ikili_bul("multirotor")
        olc("eksik: uyumsuz ikili SECILMEDI", yol is None, yol)
        olc("eksik: hata 'var ama calismiyor' ayrimini yapiyor",
            bool(hata) and "var ama" in hata, hata)
        olc("eksik: hata beklenen dosya adini soyluyor",
            bool(hata) and "arducopter_aarch64" in hata, hata)
        olc("eksik: hata cozum yolunu soyluyor (goktungu-sitl arsivi)",
            bool(hata) and "goktungu-sitl" in hata, hata)
        olc("eksik: hata makine mimarisini yaziyor",
            bool(hata) and "aarch64" in hata, hata)
        # YANLIS yonlendirme olmamali: bu mimaride indirme secenegi YOK.
        olc("eksik: hata 'SITL indir' onerisi VERMIYOR",
            bool(hata) and "SITL indir" not in hata, hata)

        ok, eksik, ileti = sitl.hazir_mi()
        olc("eksik: hazir_mi False (yanlis 'hazir' demiyor)", ok is False,
            ileti)
        olc("eksik: acilis iletisi beklenen dosyayi soyluyor",
            "arducopter_aarch64" in (ileti or ""), ileti)
        olc("eksik: acilis iletisi tanilama aracini soyluyor",
            "sitl_tani" in (ileti or "") or "goktungu-sitl" in (ileti or ""),
            ileti)

        # indir(): ag erisimi olsa bile 32-bit ARM CEKMEMELI.
        basarili, ind_ileti = sitl.indir("multirotor")
        olc("eksik: indir() basarisiz dondu", basarili is False, ind_ileti)
        olc("eksik: indir() aarch64 ikilisinin YAYINLANMADIGINI soyluyor",
            "aarch64" in (ind_ileti or "")
            and ("YOKTUR" in (ind_ileti or "")
                 or "indirilemez" in (ind_ileti or "")), ind_ileti)
        artiklar = [a for a in os.listdir(gecici)
                    if a.endswith(".indiriliyor")]
        olc("eksik: indir() yarim dosya BIRAKMADI", not artiklar, artiklar)
        # En onemlisi: 32-bit ARM ikilisi indirilip yerine KONMAMIS olmali.
        yeni = os.path.join(gecici, "arducopter_aarch64")
        if os.path.isfile(yeni):
            b = sitl.ikili_bicimi(yeni)
            olc("eksik: konulan dosya 32-bit ARM DEGIL",
                b.get("makine") != 0x28, b.get("makine_ad"))
        else:
            olc("eksik: 32-bit ARM ikilisi indirilmedi", True)
    finally:
        sitl.SITL_KLASORU = _eski_klasor
        _geri()
finally:
    shutil.rmtree(gecici, ignore_errors=True)

# ======================================================================
bolum("7. GERCEK calistirma: aarch64 ikilisi gercekten kosuyor mu")
# ======================================================================
# Bu bolum en pahali kusur tipini yakalar: dosya dogru gorunur, bicim
# denetimi gecer, ama gerceklikte calismaz. Sandbox x86-64 oldugu icin
# aarch64 ikilisi qemu-aarch64-static ile kosturulur. Kullanicinin
# makinesinde qemu GEREKMEZ - orada cekirdek dogrudan calistirir.
qemu = shutil.which("qemu-aarch64-static") or shutil.which("qemu-aarch64")
gercek_aarch64 = (_GERCEK_MAKINE() or "").lower() in ("aarch64", "arm64")

for ad, arac in (("arducopter_aarch64", "copter"),
                 ("arduplane_aarch64", "plane")):
    yol = os.path.join(SITL_DIZIN, ad)
    if not os.path.isfile(yol):
        olc("%s calistirma denemesi" % ad, False, "dosya yok")
        continue
    if gercek_aarch64:
        komut = [yol, "--help"]
    elif qemu:
        komut = [qemu, yol, "--help"]
    else:
        print("[ATLA ] %s calistirma: qemu yok, bu makine x86-64" % ad)
        continue
    try:
        s = subprocess.run(komut, capture_output=True, text=True,
                           timeout=120)
        cikti = (s.stdout or "") + (s.stderr or "")
    except Exception as e:
        cikti = "kosturulamadi: %s" % e
    # ArduPilot SITL --help ile parametre listesini basar.
    olc("%s GERCEKTEN kosuyor (--help yanit verdi)" % ad,
        "--wipe" in cikti or "speedup" in cikti, cikti.strip()[:200])

# ======================================================================
bolum("8. Gercek MAVLink telemetrisi (aarch64 ikilisi)")
# ======================================================================
# `--help` yanit vermek ile GERCEK bir ucus benzetimi yurutup MAVLink
# basmak ayni sey degildir; ikincisi olculmezse kusur sahada gorulur.
kopter = os.path.join(SITL_DIZIN, "arducopter_aarch64")
if not os.path.isfile(kopter):
    olc("aarch64 telemetri sinavi", False, "ikili yok")
elif not (gercek_aarch64 or qemu):
    print("[ATLA ] aarch64 telemetri: qemu yok, bu makine x86-64")
else:
    import socket
    import time
    calisma = tempfile.mkdtemp(prefix="goktungu_2447_ucus_")
    taban = 15920
    dinleme = taban + 1
    onek = [] if gercek_aarch64 else [qemu]
    komut = onek + [
        kopter, "--model", "+", "--home", "39.925,32.836,100,0",
        "--base-port", str(taban),
        "--serial0", "udpclient:127.0.0.1:%d" % dinleme,
        "--sysid", "123",
    ]
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.settimeout(1.0)
    p = None
    try:
        s.bind(("127.0.0.1", dinleme))
        gunluk = open(os.path.join(calisma, "sitl.log"), "w")
        p = subprocess.Popen(komut, cwd=calisma, stdout=gunluk,
                             stderr=subprocess.STDOUT)
        paket = 0
        sysid = None
        t0 = time.time()
        while time.time() - t0 < 90:
            try:
                d, _ = s.recvfrom(4096)
            except socket.timeout:
                if p.poll() is not None:
                    break
                continue
            if d[:1] == b"\xfd":          # MAVLink 2
                paket += 1
                sysid = d[5]
            elif d[:1] == b"\xfe":        # MAVLink 1
                paket += 1
                sysid = d[3]
            if paket >= 20:
                break
        olc("aarch64: surec ayakta kaldi", p.poll() is None,
            "cikis kodu: %s" % p.poll())
        olc("aarch64: MAVLink telemetrisi geldi (>=20 paket)", paket >= 20,
            "%d paket" % paket)
        # sysid dogrulamasi: sanal dronlarin benzersiz sysid almasi
        # angajman denemelerinin dogru calismasi icin sarttir.
        olc("aarch64: sysid dogru iletildi (123)", sysid == 123,
            "sysid=%s" % sysid)
    except Exception as e:
        olc("aarch64 telemetri sinavi", False, e)
    finally:
        try:
            s.close()
        except Exception:
            pass
        if p is not None:
            try:
                p.terminate()
                p.wait(timeout=15)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        shutil.rmtree(calisma, ignore_errors=True)

# ======================================================================
bolum("9. Izin onarimi aarch64 dosyalarini da kapsiyor (v2.4.46 gerileme)")
# ======================================================================
if platform.system().lower().startswith("win"):
    print("[ATLA ] Windows'ta POSIX calistirma biti yoktur")
else:
    gecici2 = tempfile.mkdtemp(prefix="goktungu_2447_izin_")
    try:
        kopyalanan = []
        for ad in AARCH64_IKILILER:
            k = os.path.join(SITL_DIZIN, ad)
            if os.path.isfile(k):
                shutil.copy2(k, gecici2)
                os.chmod(os.path.join(gecici2, ad), 0o644)
                kopyalanan.append(ad)
        olc("izin: aarch64 dosyalari kopyalandi", bool(kopyalanan),
            kopyalanan)
        onarilan, basarisiz = sitl.izin_onar_klasor(gecici2)
        olc("izin: onarim basarisizlik vermedi", not basarisiz, basarisiz)
        olc("izin: aarch64 dosyalari onarildi",
            onarilan >= len(kopyalanan),
            "onarilan=%d, beklenen>=%d" % (onarilan, len(kopyalanan)))
        for ad in kopyalanan:
            olc("izin: %s artik calistirilabilir" % ad,
                os.access(os.path.join(gecici2, ad), os.X_OK))
    finally:
        shutil.rmtree(gecici2, ignore_errors=True)

# ======================================================================
bolum("10. Tanilama araci aarch64'u biliyor")
# ======================================================================
tani = os.path.join(KOK, "sitl_tani.py")
if not os.path.isfile(tani):
    tani = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "sitl_tani.py")
olc("sitl_tani.py mevcut", os.path.isfile(tani), tani)
if os.path.isfile(tani):
    try:
        s = subprocess.run([sys.executable, tani], capture_output=True,
                           text=True, timeout=300)
        cikti = (s.stdout or "") + (s.stderr or "")
    except Exception as e:
        cikti = "kosturulamadi: %s" % e
    olc("tanilama: mimari bildiriyor",
        "mimari" in cikti.lower() or "machine" in cikti.lower(),
        cikti[:200])
    olc("tanilama: aarch64 dosyalarini goruyor",
        "arducopter_aarch64" in cikti, cikti[:200])
    olc("tanilama: cokmeden tamamlandi",
        "Traceback" not in cikti, cikti[-300:])

# ======================================================================
print()
print("=" * 64)
print("SONUC: %d GECTI / %d KALDI" % (GECTI, KALDI))
if BASARISIZLAR:
    print()
    print("Kalanlar:")
    for b in BASARISIZLAR:
        print("  - %s" % b)
print("=" * 64)
sys.exit(1 if KALDI else 0)
