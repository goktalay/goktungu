#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""GOKTUNGU Kopru Yazilimi — dagitim paketi ureticisi.

NE YAPAR
    Gelistirme dizininden PLATFORMA GORE AYRI, temiz dagitim arsivleri
    uretir ve her arsivin icerigini gercekten acarak dogrular.

        goktungu-kopru-<surum>-windows.zip     (kur.bat, kaldir.bat, .ico)
        goktungu-kopru-<surum>-linux.tar.gz    (kur.sh, kaldir.sh, hicolor)

NEDEN AYRI PAKET (v1.3.0'da degisti)
    Onceden tek bir tar.gz iki isletim sisteminin betiklerini de
    tasiyordu. Iki somut sorun uretiyordu:

    1. Windows'ta `.tar.gz` yerlesik olarak CIFT TIKLAMAYLA acilmaz.
       Kullanici 7-Zip aramak zorunda kaliyor ve "indirdim ama
       acamiyorum" noktasinda takiliyordu. `.zip` Windows Gezgini'nde
       dogrudan acilir.
    2. Linux paketinde `kur.bat` bulunmasi (ve tersi) kullaniciya hangi
       dosyayi calistiracagini SORDURUYORDU. Kurulumda en sik yapilan
       hata yanlis betigi calistirmaktir.

    Ortak Python cekirdegi (kopru/, web/, main.py) TEK kaynaktan
    uretilir; iki paket arasinda kod farki YOKTUR. Yalnizca kurulum
    katmani ve ikon bicimi ayrisir.

NE YAPMAZ — IMZALAMAZ.
    Merkezde Ed25519 imza altyapisi ZATEN var (`mk_depo.py`: anahtar_uret,
    imzala, imza_dogrula, paket_ekle) ve acik anahtar
    `/api/genel/imza_anahtari` ucundan yayinlaniyor. Burada ikinci bir
    imza zinciri kursaydik iki ayri anahtar hiyerarsisi dogardi; istemci
    hangi anahtarin gecerli oldugunu bilemez ve imzanin guvence degeri
    sifira duserdi. Imzayi paketi depoya alan taraf (merkez) atar.

    Merkezin imza baglami paket dosyasinin sha256'sini DE kapsadigi icin
    (urun|surum|platform|paket_tur|sha256|boyut) burada uretilen arsiv
    bit duzeyinde ne ise merkez tam onu imzalar. Bu yuzden bu betigin tek
    isi arsivleri dogru ve tekrarlanabilir uretmektir.

NEDEN AYRI BETIK
    Gelistirme dizini 28 MB (.venv) + 14 MB (__pycache__) tasiyor ve
    icinde sinav betikleri var. Bunlar kullaniciya inen pakete girmemeli:
      - .venv makineye ozgudur, baska makinede calismaz (mutlak yollar)
      - __pycache__ eski Python surumune ait olabilir, sessiz hatalar uretir
      - sinav betikleri kullanicinin isine yaramaz; kotu niyetli okuyucuya
        ic uc adreslerini ve sinav hesaplarini gosterir

KULLANIM
    python3.11 paketle.py                    # ./dagitim altina ikisini uret
    python3.11 paketle.py --cikti /tmp       # baska dizine yaz
    python3.11 paketle.py --platform windows # yalniz birini uret
"""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import shutil
import sys
import tarfile
import tempfile
import zipfile

KOK = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- surum
# Surum kopru paketinin KENDI defterinden okunur (surumler.py). Elle
# yazmak Faz 8'de giderilen kusurun aynisini geri getirirdi: iki ayri
# surum kaynagi olur, biri unutulur, paket yanlis surumle yayinlanir.
sys.path.insert(0, KOK)
from kopru.surumler import KOPRU_SURUM  # noqa: E402

# ------------------------------------------------------- paket icerigi
# BEYAZ LISTE yaklasimi (kara liste degil).
#
# Kara liste ("sunlari disla") tehlikelidir: yeni bir gelistirme artigi
# olustugunda sessizce pakete girer. Beyaz listede yeni bir kaynak dosya
# eklendiginde paket EKSIK cikar ve dogrulama basarisiz olur — yani hata
# sessiz kalmaz, gurultu yapar. Sessiz fazlalik, gurultulu eksiklikten
# daha tehlikelidir.
DIZINLER = ("kopru", "web")
# Bu dizinlerde YALNIZ su uzantilar pakete girer.
IZINLI_UZANTI = {
    "kopru": {".py"},
    "web": {".html", ".css", ".js", ".png", ".svg", ".ico"},
}

# Platforma ozgu kurulum katmani.
#
# `varliklar` alt yollari ACIKCA listelenir: Windows paketine 8 adet
# PNG koymak, Linux paketine .ico koymak gereksiz yuk ve karisiklik
# yaratir. Kurulum betikleri tam bu yollari bekler.
PLATFORM = {
    "windows": {
        "arsiv": "zip",
        "kok_dosyalar": ("main.py", "kur.bat", "kaldir.bat"),
        "varlik_uzanti": {".ico"},
        "calisir": frozenset(),          # Windows'ta kip biti anlamsiz
        "yasak_ek": ("kur.sh", "kaldir.sh"),
    },
    "linux": {
        "arsiv": "targz",
        # `tani_sifirla.sh` YALNIZ Linux paketinde: servis olusmadiginda
        # kullanicinin elinde tani araci bulunmali. Disaridan indirmesi
        # gerekirse tam o anda (panel yok, servis yok) en zor durumda
        # kalir. Windows'ta karsiligi services.msc ve kaldir.bat'tir.
        "kok_dosyalar": ("main.py", "kur.sh", "kaldir.sh",
                         "tani_sifirla.sh"),
        "varlik_uzanti": {".png", ".svg"},
        "calisir": frozenset({"kur.sh", "kaldir.sh", "tani_sifirla.sh"}),
        "yasak_ek": ("kur.bat", "kaldir.bat"),
    },
}

# Pakette KESINLIKLE bulunmamasi gerekenler — uretim sonrasi denetlenir.
YASAK_PARCA = (
    ".venv/",
    "__pycache__/",
    ".pyc",
    "sinav_",
    "canli_",
    ".git/",
    "paketle.py",
    "olcum_",
    "yayinla_",
)

# Her iki pakette bulunmasi ZORUNLU ortak dosyalar.
ZORUNLU_ORTAK = (
    "main.py", "SURUM",
    "kopru/__init__.py", "kopru/ayar.py", "kopru/ajan.py",
    "kopru/akis.py", "kopru/kilit.py", "kopru/merkez.py",
    "kopru/ai_ssh.py",
    "kopru/panel.py", "kopru/servisler.py", "kopru/surumler.py",
    "kopru/servis_temel.py", "kopru/servis_dron.py", "kopru/servis_ai.py",
    "kopru/servis_video.py", "kopru/servis_radar.py",
    "kopru/servis_gcsdual.py", "kopru/uygulama.py",
    # SAHADA KOSAN protokol/vekil modulleri.
    #
    # Listeye EKLENMESI zorunludur: bunlar olmadan paket sessizce
    # kurulur, panel acilir, servisler "calisiyor" gorunur -- ama radar
    # baglanmaz ve kamera akisi acilmaz. Kusur ancak sahada, cihaz
    # basindayken gorulur. Bir kez yasandi: `radar_c20.py` bu listede
    # olmadigi halde pakete girmisti; girmesi `kopru/*.py` supurmesinin
    # yan etkisiydi, guvence degildi.
    "kopru/servis_kanal.py", "kopru/radar_c20.py",
    "kopru/m50_hvs.py", "kopru/servis_m50.py",
    "kopru/video_vekil.py",
    "web/index.html", "web/stil.css", "web/uygulama.js",
    #
    # `web/tema.js` -- gunduz/gece dongusu. Ayni tuzak: dosya listede
    # olmazsa index.html'deki tema dugmesi GORUNUR ama tiklanınca hicbir
    # sey olmaz (betik 404). Panel calisiyor gorunur, kusur ancak
    # kullanici dugmeye bastiginda ortaya cikar.
    "web/tema.js",
)

SABIT_ZAMAN = 1755100800  # tekrarlanabilirlik icin sabit mtime


def _renk(s: str, k: str) -> str:
    if not sys.stdout.isatty():
        return s
    return {"y": "\033[32m", "k": "\033[31m", "s": "\033[33m"}.get(k, "") + s + "\033[0m"


def toplanacak_dosyalar(platform: str) -> list[tuple[str, str]]:
    """(kaynak_mutlak, arsiv_ici_goreli) ciftlerini dondurur."""
    p = PLATFORM[platform]
    cift: list[tuple[str, str]] = []

    for ad in p["kok_dosyalar"]:
        tam = os.path.join(KOK, ad)
        if not os.path.isfile(tam):
            raise FileNotFoundError(f"paket icerigi eksik: {ad}")
        cift.append((tam, ad))

    for d in DIZINLER:
        kok_d = os.path.join(KOK, d)
        if not os.path.isdir(kok_d):
            raise FileNotFoundError(f"paket dizini eksik: {d}/")
        izinli = IZINLI_UZANTI[d]
        for dizin, altlar, dosyalar in os.walk(kok_d):
            # __pycache__ / .venv gibi dizinlere hic inmiyoruz.
            altlar[:] = [a for a in altlar if a not in ("__pycache__", ".venv", ".git")]
            for f in sorted(dosyalar):
                if os.path.splitext(f)[1].lower() not in izinli:
                    continue
                tam = os.path.join(dizin, f)
                cift.append((tam, os.path.relpath(tam, KOK)))

    # Ikonlar: platforma uygun bicim.
    varlik_kok = os.path.join(KOK, "varliklar")
    if os.path.isdir(varlik_kok):
        uz = p["varlik_uzanti"]
        for dizin, altlar, dosyalar in os.walk(varlik_kok):
            altlar[:] = [a for a in altlar if a not in ("__pycache__", ".git")]
            for f in sorted(dosyalar):
                if os.path.splitext(f)[1].lower() not in uz:
                    continue
                tam = os.path.join(dizin, f)
                cift.append((tam, os.path.relpath(tam, KOK)))

    return sorted(cift, key=lambda c: c[1])


def _surum_dosyasi(dizin: str) -> str:
    """Pakete SURUM dosyasi uretir ve yolunu dondurur.

    Kurulum betikleri ve kullanici, arsivi actiktan sonra hangi surumu
    aldigini kod okumadan gormek zorunda. Destek istegi geldiginde ilk
    sorulan sey de bu. Kurulum betigi ayrica yukseltmede eski/yeni
    surum kiyaslamasi icin bu dosyayi okur.
    """
    yol = os.path.join(dizin, "SURUM")
    with io.open(yol, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"{KOPRU_SURUM}\n")
    return yol


def paket_uret(platform: str, cikti_dizin: str) -> str:
    p = PLATFORM[platform]
    dosyalar = toplanacak_dosyalar(platform)
    kok_ad = f"goktungu-kopru-{KOPRU_SURUM}"
    uzanti = "zip" if p["arsiv"] == "zip" else "tar.gz"
    hedef = os.path.join(cikti_dizin, f"{kok_ad}-{platform}.{uzanti}")
    os.makedirs(cikti_dizin, exist_ok=True)

    gecici = tempfile.mkdtemp(prefix="kopru_paket_")
    try:
        surum_yolu = _surum_dosyasi(gecici)
        tum = [(surum_yolu, "SURUM")] + list(dosyalar)

        if p["arsiv"] == "zip":
            # ZIP_DEFLATED: Windows Gezgini bunu yerlesik acar.
            # date_time sabit: tekrarlanabilirlik (bkz. tar filtresi).
            with zipfile.ZipFile(hedef, "w", zipfile.ZIP_DEFLATED,
                                 compresslevel=9) as z:
                for kaynak, gor in tum:
                    bilgi = zipfile.ZipInfo(f"{kok_ad}/{gor}",
                                            date_time=(2026, 8, 14, 0, 0, 0))
                    bilgi.compress_type = zipfile.ZIP_DEFLATED
                    bilgi.external_attr = 0o644 << 16
                    with io.open(kaynak, "rb") as f:
                        z.writestr(bilgi, f.read())
        else:
            calisir = p["calisir"]

            def _duzelt(ti: tarfile.TarInfo) -> tarfile.TarInfo:
                # TEKRARLANABILIRLIK: sahiplik ve zaman damgasini sabitle.
                # Aksi halde ayni kaynaktan uretilen iki arsiv farkli
                # sha256 verir; merkezin imzasi dosya ozetini kapsadigi
                # icin "ayni paket mi" sorusu yanitlanamaz hale gelir.
                ti.uid = ti.gid = 0
                ti.uname = ti.gname = "root"
                ti.mtime = SABIT_ZAMAN
                temel = os.path.basename(ti.name)
                if ti.isdir():
                    ti.mode = 0o755
                elif temel in calisir:
                    ti.mode = 0o755
                else:
                    ti.mode = 0o644
                return ti

            with tarfile.open(hedef, "w:gz", format=tarfile.GNU_FORMAT) as tar:
                for kaynak, gor in tum:
                    tar.add(kaynak, arcname=f"{kok_ad}/{gor}", filter=_duzelt)
    finally:
        shutil.rmtree(gecici, ignore_errors=True)

    return hedef


class _Arsiv:
    """zip ve tar.gz uzerinde ayni dogrulama kodunu calistirmak icin
    ince sarmalayici. Iki ayri dogrulama islevi yazmak, birinde
    duzeltilen kusurun otekinde kalmasina yol acar."""

    def __init__(self, yol: str):
        self.zip = yol.endswith(".zip")
        self._t = zipfile.ZipFile(yol) if self.zip else tarfile.open(yol, "r:gz")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self._t.close()

    def adlar(self) -> list[str]:
        return self._t.namelist() if self.zip else self._t.getnames()

    def oku(self, ad: str) -> str:
        if self.zip:
            return self._t.read(ad).decode("utf-8", errors="replace")
        f = self._t.extractfile(ad)
        return f.read().decode("utf-8", errors="replace") if f else ""

    def kip(self, ad: str) -> int:
        if self.zip:
            return (self._t.getinfo(ad).external_attr >> 16) & 0o777
        return self._t.getmember(ad).mode

    def metin_dosyalari(self):
        for ad in self.adlar():
            if ad.endswith((".py", ".sh", ".bat")):
                yield ad, self.oku(ad)


def dogrula(arsiv: str, platform: str) -> tuple[int, int]:
    """Uretilen arsivi ACARAK dogrular. (gecti, kaldi) dondurur."""
    gecti = kaldi = 0
    p = PLATFORM[platform]

    def kontrol(ad: str, kosul: bool, ayrinti: str = "") -> None:
        nonlocal gecti, kaldi
        if kosul:
            gecti += 1
            print(f"  {_renk('[OK]', 'y')} {ad}")
        else:
            kaldi += 1
            print(f"  {_renk('[KALDI]', 'k')} {ad}" + (f" — {ayrinti}" if ayrinti else ""))

    kok_ad = f"goktungu-kopru-{KOPRU_SURUM}"

    with _Arsiv(arsiv) as a:
        adlar = a.adlar()

        kontrol("arsiv tek kok dizine sariliyor",
                all(x == kok_ad or x.startswith(kok_ad + "/") for x in adlar),
                "kok dizin disinda uye var")

        for yasak in YASAK_PARCA:
            bulunan = [x for x in adlar if yasak in x]
            kontrol(f"yasak icerik yok: {yasak}", not bulunan,
                    f"bulundu: {bulunan[:3]}")

        # PLATFORM AYRIMI: oteki isletim sisteminin betigi bulunmamali.
        # Kullanicinin yanlis betigi calistirmasi kurulumda en sik
        # yapilan hatadir.
        for yasak in p["yasak_ek"]:
            kontrol(f"oteki platformun betigi yok: {yasak}",
                    f"{kok_ad}/{yasak}" not in adlar)

        eksik = [z for z in ZORUNLU_ORTAK if f"{kok_ad}/{z}" not in adlar]
        kontrol(f"zorunlu {len(ZORUNLU_ORTAK)} ortak dosyanin hepsi var",
                not eksik, f"eksik: {eksik}")

        for ad in p["kok_dosyalar"]:
            kontrol(f"kurulum betigi pakette: {ad}",
                    f"{kok_ad}/{ad}" in adlar)

        # BES SERVIS: kullanici istegi. Biri eksik olsa panel menusu yarim
        # kalir ve kullanici nedenini anlamaz.
        for s in ("dron", "ai", "video", "radar", "gcsdual"):
            kontrol(f"servis modulu pakette: {s}",
                    f"{kok_ad}/kopru/servis_{s}.py" in adlar)

        # IKON: kullanici acikca istedi ("setup ve kisayol ikonu GOKTUNGU'nun
        # mavi ikonu olmali"). Ikon pakete girmezse kurulum sessizce genel
        # bir sistem ikonuna duser ve kusur ancak kullanici masaustune
        # bakinca gorulur.
        if platform == "windows":
            kontrol("Windows ikonu pakette (goktungu.ico)",
                    f"{kok_ad}/varliklar/goktungu.ico" in adlar)
        else:
            png = [x for x in adlar if x.startswith(f"{kok_ad}/varliklar/hicolor/")
                   and x.endswith("/goktungu-kopru.png")]
            kontrol("Linux ikonlari pakette (hicolor, en az 6 boyut)",
                    len(png) >= 6, f"bulunan: {len(png)}")
            kontrol("48x48 ikon var (menu icin zorunlu)",
                    f"{kok_ad}/varliklar/hicolor/48x48/apps/goktungu-kopru.png" in adlar)

        for temel in p["calisir"]:
            ad = f"{kok_ad}/{temel}"
            if ad in adlar:
                kontrol(f"{temel} calisir (0755)", a.kip(ad) == 0o755,
                        f"kip={oct(a.kip(ad))}")

        icerik = a.oku(f"{kok_ad}/SURUM").strip()
        kontrol(f"SURUM dosyasi defterle ayni ({KOPRU_SURUM})",
                icerik == KOPRU_SURUM, f"dosyada: {icerik!r}")

        # Faz 8 kusurunun geri gelmemesi: ayar.py surumu elle yazmamali.
        ayar_kaynak = a.oku(f"{kok_ad}/kopru/ayar.py")
        kontrol("ayar.py surumu surumler.py'den okuyor",
                "from .surumler import KOPRU_SURUM as SURUM" in ayar_kaynak,
                "elle yazilmis SURUM sabiti geri gelmis olabilir")

        # main.py Python surum denetimi ICE AKTARIMLARDAN ONCE olmali.
        main_kaynak = a.oku(f"{kok_ad}/main.py")
        yer_denetim = main_kaynak.find("version_info")
        yer_ithal = main_kaynak.find("from kopru")
        kontrol("main.py surum denetimi kopru ithalatindan once",
                yer_denetim >= 0 and (yer_ithal < 0 or yer_denetim < yer_ithal),
                "denetim sonraya kaymis; eski Python'da ciplak SyntaxError verir")

        # v1.2.1 KUSURUNUN GERI GELMEMESI: `chcp 65001` uretilen
        # baslaticiyi bozuyordu (UTF-8 bayt / ANSI cozumleme uyusmazligi).
        if platform == "windows":
            bat = a.oku(f"{kok_ad}/kur.bat")
            # ACIKLAMA SATIRLARI DISLANIR: kusurun NEDENI dosyanin
            # basinda `REM NEDEN chcp YOK` olarak belgelenmis durumda.
            # Ham metinde arama yapmak bu aciklamayi kusur sayar ve
            # gelistiriciyi belgeyi silmeye zorlar — yanlis tesvik.
            bat_komut = "\n".join(
                s for s in bat.splitlines()
                if not s.strip().upper().startswith("REM"))
            kontrol("kur.bat `chcp` kullanmiyor (v1.2.1 kusuru)",
                    "chcp" not in bat_komut.lower())
            kontrol("kur.bat Program Files altina kuruyor",
                    "%ProgramFiles%\\Goktungu\\Kopru" in bat)
            kontrol("kur.bat servis (gorev) kaydediyor",
                    "schtasks /Create" in bat and "ONSTART" in bat)
            kontrol("kur.bat yonetici yetkisi denetliyor",
                    "net session" in bat)
            kontrol("kur.bat veri dizinini ProgramData'ya yonlendiriyor",
                    "GOKTUNGU_KOPRU_VERI" in bat)
            kontrol("kur.bat yerinde yukseltme yapiyor",
                    "YUKSELTME" in bat and "schtasks /End" in bat)
            kontrol("kur.bat kisayollara GOKTUNGU ikonunu veriyor",
                    "goktungu.ico" in bat and "IconLocation" in bat)
        else:
            sh = a.oku(f"{kok_ad}/kur.sh")
            kontrol("kur.sh /opt altina kuruyor",
                    "/opt/goktungu/kopru" in sh)
            kontrol("kur.sh systemd kullanici servisi kuruyor",
                    "systemctl --user enable" in sh)
            kontrol("kur.sh masaustu girdisi olusturuyor",
                    ".desktop" in sh and "Type=Application" in sh)
            kontrol("kur.sh ikonlari hicolor temasina kuruyor",
                    "hicolor" in sh and "gtk-update-icon-cache" in sh)
            kontrol("kur.sh yerinde yukseltme yapiyor",
                    "YUKSELTME" in sh and "systemctl --user stop" in sh)
            kontrol("kur.sh root ile calistirmayi reddediyor",
                    'id -u' in sh)

        # Gelistirme makinesine ozgu mutlak yol kacagi kurulumu sessizce
        # bozar: betik kendi gelistirme dizinini arar, bulamaz, hata verir.
        kacak: list[str] = []
        for ad, metin in a.metin_dosyalari():
            for iz in ("/home/ubuntu/goktungu_kopru", "/mnt/2vz6isal"):
                if iz in metin:
                    kacak.append(f"{ad}:{iz}")
        kontrol("gelistirme makinesine ozgu mutlak yol yok", not kacak,
                f"{kacak[:3]}")

    return gecti, kaldi


def main() -> int:
    ap = argparse.ArgumentParser(description="GOKTUNGU Kopru dagitim paketi ureticisi")
    ap.add_argument("--cikti", default=os.path.join(KOK, "dagitim"),
                    help="arsivlerin yazilacagi dizin (varsayilan: ./dagitim)")
    ap.add_argument("--platform", choices=("windows", "linux", "hepsi"),
                    default="hepsi", help="uretilecek paket (varsayilan: hepsi)")
    a = ap.parse_args()

    print("=" * 66)
    print(f" GOKTUNGU KOPRU — DAGITIM PAKETLERI  v{KOPRU_SURUM}")
    print("=" * 66)

    hedefler = ["windows", "linux"] if a.platform == "hepsi" else [a.platform]
    toplam_gecti = toplam_kaldi = 0
    uretilen: list[tuple[str, str, int, str]] = []

    for plat in hedefler:
        print(f"\n{'=' * 66}")
        print(f" PLATFORM: {plat.upper()}")
        print("=" * 66)
        try:
            arsiv = paket_uret(plat, a.cikti)
        except (FileNotFoundError, OSError) as e:
            print(_renk(f"[HATA] paket uretilemedi: {e}", "k"))
            return 1

        boyut = os.path.getsize(arsiv)
        with io.open(arsiv, "rb") as f:
            sha = hashlib.sha256(f.read()).hexdigest()

        print(f"\nArsiv : {arsiv}")
        print(f"Boyut : {boyut:,} bayt")
        print(f"SHA256: {sha}")

        print("\n--- ICERIK DOGRULAMASI (arsiv gercekten aciliyor) ---")
        g, k = dogrula(arsiv, plat)
        toplam_gecti += g
        toplam_kaldi += k
        uretilen.append((plat, arsiv, boyut, sha))

    print("\n" + "=" * 66)
    if toplam_kaldi:
        print(_renk(f" SONUC: {toplam_gecti} gecti, {toplam_kaldi} KALDI"
                    " — paketler yayinlanmamali", "k"))
        return 2
    print(_renk(f" SONUC: {toplam_gecti} gecti, 0 kaldi", "y"))
    print("=" * 66)

    print("\nUretilen paketler:")
    for plat, yol, boyut, sha in uretilen:
        print(f"  {plat:8s} {os.path.basename(yol):46s} {boyut:>9,} bayt")

    print("\nSonraki adim (merkezde; imzayi merkez atar):")
    for plat, yol, _, _ in uretilen:
        print(f"  mk_depo.paket_ekle('kopru', '{KOPRU_SURUM}',")
        print(f"                     '{os.path.basename(yol)}',")
        print(f"                     platform='{plat}', paket_tur='tam')")
    return 0


if __name__ == "__main__":
    sys.exit(main())
