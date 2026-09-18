#!/usr/bin/env python3
"""GOKTUNGU Merkez Uygulamasi — Windows setup.exe ureticisi.

NE YAPAR
  1. Surumu `js/surum.js` defterinden okur (elle yazmak surum kaymasina
     yol acar; .deb ve zip ayni kaynagi kullaniyor).
  2. NSIS'in zorunlu istedigi `dagitim/LISANS.txt` dosyasini uretir.
     Bu dosya hicbir betik tarafindan uretilmiyordu; derleme onsuz
     durur.
  3. Girdilerin HEPSININ yerinde oldugunu derlemeden ONCE olcer:
       dagitim/agac/assets, gomulu_merkez/calisma, varliklar/goktungu.ico,
       main.py, servis_merkez_win.py
     Eksik girdiyle derlemeye girmek, NSIS'in anlasilmaz hata
     yiginlariyla donmesine yol acar.
  4. `makensis` ile derler ve uretilen .exe'yi olcer.

NEDEN AYRI BETIK
  `paketle_merkez.py` platformdan bagimsiz agaci uretir; bu betik
  yalnizca Windows kabugunu kurar. Ayrik tutmak, .deb tarafinin
  Windows girdilerinden etkilenmemesini saglar.

KOSUM
  python3.11 paketle_merkez.py --agac-birak --arsiv-yok
  python3.11 gomulu_merkez_hazirla.py        # bir kez yeter
  python3.11 setup_merkez_uret.py
"""
import os
import re
import shutil
import subprocess
import sys

KOK = os.path.dirname(os.path.abspath(__file__))
DAGITIM = os.path.join(KOK, "dagitim")
AGAC = os.path.join(DAGITIM, "agac")
GOMULU = os.path.join(KOK, "gomulu_merkez", "calisma")
NSI = os.path.join(KOK, "setup_merkez.nsi")
# Kurulum sürümü ile gömülü web/App sürümü bilinçli olarak ayrıdır.
def _paket_surum_oku(ad: str) -> str:
    """Surum alanini goktungu/paket_surum.py'den okur (TEK KAYNAK).

    Paket ice ALINMAZ (goktungu/__init__ calisma zamani yan etkileri);
    satir duzenli ifadeyle okunur.
    """
    yol = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "goktungu", "paket_surum.py")
    with open(yol, encoding="utf-8") as f:
        m = re.search(r'^' + ad + r'\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"',
                      f.read(), re.M)
    if not m:
        raise SystemExit("HATA: goktungu/paket_surum.py icinde %s yok" % ad)
    return m.group(1)


PAKET_SURUM = _paket_surum_oku("PAKET_SURUM")
UYGULAMA_SURUM = _paket_surum_oku("UYGULAMA_SURUM")

LISANS_METNI = """GOKTUNGU MERKEZ UYGULAMASI — SON KULLANICI LISANS SOZLESMESI

Bu yazilim VEILOX Savunma Anonim Sirketi tarafindan gelistirilmistir ve
telif haklari sirkete aittir.

1. LISANSIN KAPSAMI
   Merkez Uygulamasi lisansi, tek seferlik bedel karsiliginda satin
   alinir ve lisansi alan tuzel kisiye SINIRSIZ kullanim hakki verir.
   Kullanim; pilot koltuk sayisi, ucus sayisi veya sure ile
   sinirlandirilmaz.

2. LISANS BELGESI
   Yazilim, kurumsal panelden indirilen imzali `merkez_lisans.json`
   belgesi ile etkinlesir. Belge, lisansi alan sirkete ozeldir ve
   Ed25519 ile imzalanmistir. Belgenin uzerinde yapilan her turlu
   degisiklik lisansi gecersiz kilar.

3. KAPALI DEVRE KULLANIM
   Yazilim, VEILOX merkez sunucusuna baglanmaksizin (kapali devre)
   calisabilir. Lisans dogrulamasi tamamen yerelde yapilir; dogrulama
   icin internet baglantisi gerekmez.

4. RADAR VE GCCDUAL MODULLERI
   Bu moduller lisans belgesinde tanimli oldugu olcude etkinlesir.
   Belgede tanimli olmayan modullerin etkinlestirilmesi icin VEILOX ile
   iletisime gecilmelidir.

5. UCUNCU TARAF BILESENLER
   Yazilim; Python, OpenCV, NumPy, psycopg2, pymavlink, CesiumJS ve
   ArduPilot SITL gibi acik kaynak bilesenler icerir. Bu bilesenler
   kendi lisanslari altinda dagitilir.

6. VERI SORUMLULUGU
   Ucus kayitlari, telemetri ve video verileri musterinin kendi
   PostgreSQL sunucusunda tutulur. Verilerin yedeklenmesi ve
   guvenliginden musteri sorumludur.

7. GARANTI KAPSAMI DISI
   Yazilim "oldugu gibi" saglanir. Hava araci operasyonlarinda nihai
   sorumluluk pilotta ve isletmecidedir.

VEILOX Savunma Anonim Sirketi
Sincan, Ankara, Turkiye
"""


def surum_oku():
    """Surumu `js/surum.js` icindeki `GCS_SURUM` degiskeninden okur.

    OLCULEN KUSUR (2026-08-16): bu islev once `surum: "x.y.z"` deseni
    ariyordu, ancak defter kayitlari `s: "2.4.66"` biciminde tutulur --
    desen HICBIR ZAMAN eslesmiyordu.  Devreye giren yedek desen ise
    dosyadaki ILK uc haneli sayi dizisini aliyordu; yani hata vermeden
    yanlis surum donebilirdi (sessiz kusur).  Su an dogru sonuc
    veriyor olmasi yalnizca `GCS_SURUM` satirinin dosya basinda
    bulunmasina bagli bir tesadufu; satir defterin altina tasinsa ya
    da basa baska bir surum dizesi girse Windows kurulumu sessizce
    yanlis surum etiketiyle cikardi.

    `deb_merkez_uret.py` ayni dosyadan `GCS_SURUM`'u okur.  Iki uretici
    ayni kaynagi okumazsa Windows ve Ubuntu paketleri FARKLI surumle
    cikar; bu yuzden burada da tek dogruluk kaynagi kullanilir ve
    yedek desene DUSULMEZ.
    """
    yol = os.path.join(KOK, "js", "surum.js")
    with open(yol, encoding="utf-8") as f:
        metin = f.read()
    m = re.search(r'GCS_SURUM\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"', metin)
    if not m:
        raise SystemExit(
            "KUSUR: js/surum.js icinde GCS_SURUM bulunamadi. "
            "Sessizce yanlis surum uretmemek icin durdu.")
    surum = m.group(1)

    # Defterin en yeni kaydi ile ayni olmali; ayrisirsa surum
    # yukseltmesi yarim kalmis demektir (etiket guncellenmis ama
    # deftere kayit girilmemis ya da tersi).
    d = re.search(r'\bsurum:\s*"([0-9]+\.[0-9]+\.[0-9]+)"', metin)
    if d and d.group(1) != surum:
        raise SystemExit(
            f"KUSUR: GCS_SURUM={surum} ama defterin en yeni kaydi "
            f"{d.group(1)}. Surum yukseltmesi yarim kalmis.")
    return surum


def girdi_olc(surum):
    """Derlemeden ONCE tum girdileri olcer. Eksikleri liste doner."""
    eksik = []

    if not os.path.isdir(os.path.join(AGAC, "assets")):
        eksik.append("dagitim/agac/assets YOK — once: "
                     "python3.11 paketle_merkez.py --agac-birak --arsiv-yok")
    else:
        for alt in ("web", "python"):
            if not os.path.isdir(os.path.join(AGAC, "assets", alt)):
                eksik.append(f"dagitim/agac/assets/{alt} YOK")

    if not os.path.isdir(GOMULU):
        eksik.append("gomulu_merkez/calisma YOK — once: "
                     "python3.11 gomulu_merkez_hazirla.py")
    else:
        # Gomulu calisma zamaninin ise yarar oldugunu olc
        for gerek in ("python.exe", "python311.dll"):
            if not os.path.exists(os.path.join(GOMULU, gerek)):
                eksik.append(f"gomulu_merkez/calisma/{gerek} YOK")
        lib = os.path.join(GOMULU, "Lib", "site-packages")
        if not os.path.isdir(lib):
            eksik.append("gomulu calisma zamaninda site-packages YOK")
        else:
            for paket in ("psycopg2", "cv2", "numpy", "pymavlink",
                          "websockets", "serial"):
                if not os.path.exists(os.path.join(lib, paket)):
                    eksik.append(f"gomulu calisma zamaninda {paket} YOK")

    for dosya in ("main.py", "servis_merkez_win.py",
                  os.path.join("varliklar", "goktungu.ico")):
        if not os.path.exists(os.path.join(KOK, dosya)):
            eksik.append(f"{dosya} YOK")

    if not os.path.exists(NSI):
        eksik.append("setup_merkez.nsi YOK")

    if not shutil.which("makensis"):
        eksik.append("makensis kurulu degil (sudo apt-get install nsis)")

    return eksik


def agac_yenile(surum):
    """`dagitim/agac`i sifirdan uretir ve istenen surumu tasidigini olcer.

    Agac uretimi ve tazelik olcumu `deb_merkez_uret.py` icinde tanimli;
    ikinci bir kopya tutmak iki kaynak demektir.  Bu yuzden o modul ice
    alinip yeniden kullanilir.
    """
    sys.path.insert(0, KOK)
    try:
        import deb_merkez_uret as dmu
    except Exception as e:                                   # noqa: BLE001
        print(f"  KUSUR: deb_merkez_uret ice alinamadi: {e!r}")
        return False

    if os.path.isdir(AGAC):
        print("  onceki paket agaci siliniyor (bayat agac tuzagi)")
        shutil.rmtree(AGAC)

    print("  paket agaci uretiliyor: paketle_merkez.py --agac-birak")
    r = subprocess.run(
        [sys.executable, os.path.join(KOK, "paketle_merkez.py"),
         "--agac-birak", "--arsiv-yok", "--ai-dahil"],
        capture_output=True, text=True)
    if r.returncode != 0:
        print("  KUSUR: paket agaci uretilemedi")
        print((r.stdout or "")[-3000:])
        print((r.stderr or "")[-2000:])
        return False

    eksik = dmu.agac_tazelik_olc(AGAC, surum)
    if eksik:
        print("  KUSUR: paket agaci istenen surumu tasimiyor:")
        for e in eksik:
            print(f"    - {e}")
        return False
    print(f"  agac tazeligi dogrulandi: {surum}")
    return True


def lisans_yaz():
    os.makedirs(DAGITIM, exist_ok=True)
    yol = os.path.join(DAGITIM, "LISANS.txt")
    # NSIS lisans sayfasi Windows satir sonu bekler
    with open(yol, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(LISANS_METNI)
    return yol


def derle(surum):
    cikti = os.path.join(DAGITIM, f"GOKTUNGU-Merkez-Setup-{surum}.exe")
    if os.path.exists(cikti):
        os.remove(cikti)
    komut = ["makensis", "-V2", f"-DSURUM={surum}", NSI]
    print(f"  derleniyor: {' '.join(komut)}")
    sonuc = subprocess.run(komut, cwd=KOK, capture_output=True, text=True,
                           timeout=1800)
    if sonuc.returncode != 0:
        print("  --- makensis cikti ---")
        print((sonuc.stdout or "")[-3000:])
        print((sonuc.stderr or "")[-2000:])
        return None
    return cikti if os.path.exists(cikti) else None


def main():
    print("=" * 64)
    print(" GOKTUNGU MERKEZ — WINDOWS SETUP URETIMI")
    print("=" * 64)

    uygulama_surumu = surum_oku()
    if uygulama_surumu != UYGULAMA_SURUM:
        raise SystemExit(
            f"KUSUR: GCS_SURUM={uygulama_surumu}; beklenen uygulama sürümü "
            f"{UYGULAMA_SURUM}.")
    surum = PAKET_SURUM
    print(f"  paket sürümü: {surum}; gömülü uygulama sürümü: {uygulama_surumu}")

    # OLCULEN KUSUR (2026-08-16): bu betik `dagitim/agac` dizinini
    # yalnizca VAR MI diye olcuyordu, TAZE MI diye olcmuyordu.
    # v2.4.65'ten kalan agacla "2.4.66 etiketli, 2.4.65 icerikli" bir
    # setup.exe uretildi (ayni bayat agaci .deb de kullandi).  Agac
    # artik her kosumda yeniden uretilir ve icerigi dogrulanir.
    if not agac_yenile(uygulama_surumu):
        sys.exit(1)

    eksik = girdi_olc(surum)
    if eksik:
        print("  GIRDI EKSIK — derlemeye girilmedi:")
        for e in eksik:
            print(f"    - {e}")
        sys.exit(1)
    print("  girdiler tam")

    yol = lisans_yaz()
    print(f"  LISANS.txt uretildi: {os.path.getsize(yol)} bayt")

    exe = derle(surum)
    if not exe:
        print("  KUSUR: setup.exe uretilemedi")
        sys.exit(1)

    mb = os.path.getsize(exe) / (1024 * 1024)
    print(f"  URETILDI: {os.path.basename(exe)}  ({mb:.1f} MB)")

    # Uretilen dosyanin gercekten PE calistirilabiliri oldugunu olc
    with open(exe, "rb") as f:
        bas = f.read(2)
    if bas != b"MZ":
        print(f"  KUSUR: uretilen dosya PE degil (bas={bas!r})")
        sys.exit(1)
    print("  PE imzasi dogrulandi (MZ)")

    print("=" * 64)


if __name__ == "__main__":
    main()
