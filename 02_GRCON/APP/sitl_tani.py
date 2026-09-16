#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GOKTUNGU v2.4.48 — SITL TANILAMA ARACI

Kullanim (GOKTUNGU kurulum klasorunde):
    python3 sitl_tani.py

Ne yapar: sanal dron (SITL) calistirilamamasinin nedenini adim adim
olcer ve NE YAPILACAGINI yazar. Hicbir sey degistirmez; yalniz izin
onarimi (chmod +x) yapar, o da acikca bildirilir.

Neden var: `[Errno 13] Permission denied` ve `[Errno 8] Exec format
error` gibi hatalar ciplak halde nedeni gostermez. Bu arac dosyanin
gercek bicimini, mimarisini, boyutunu ve parmak izini okuyup hangi
katmanda kirildigini soyler.

v2.4.47: arac MIMARIYE DUYARLI hale getirildi. Onceki surumde her Linux
makinede `arducopter` dosyasi araniyordu; aarch64 bir makinede bu dosya
x86-64 oldugu icin "mimari uygun degil" deyip cozum olarak INDIRME
oneriyordu - oysa ArduPilot aarch64 SITL yayinlamaz (olculdu: HTTP 404).
Artik makineye gore dogru dosya adi aranir ve dogru cozum yazilir.

v2.4.48: Windows tarafi Linux tarafiyla ayni titizlige getirildi.
Onceden PE dosyalari icin yalnizca "MZ ile basliyor" deniyordu; hangi
MIMARI oldugu HIC okunmuyordu. Bu, Windows'ta Linux'takine denk bir kor
noktaydi: mimarisi uymayan bir PE dosyasi "gecti" raporlanir, sonra
surec 0xC000007B ile aninda kapanirdi. Artik PE'nin COFF Machine alani
okunur ve x64/ARM64/x86 ayirt edilir. Ayrica ArduPilot dagitimindaki
bes DLL'in 32-BIT oldugu ve import zincirinde HIC bulunmadigi olculdu;
bunlar artik "eksik olabilir" diye raporlanmaz (64-bit surece 32-bit DLL
yuklenemez, dolayisiyla eksiklikleri bir kusur degildir).
"""
import hashlib
import os
import platform
import subprocess
import sys

# Mimariye ozgu ikili soneki. Bu mimarilerde ArduPilot hazir SITL
# YAYINLAMAZ; ikililer GOKTUNGU paketine gomulu gelir.
MIMARI_SONEK = {
    "aarch64": "_aarch64",
    "arm64": "_aarch64",
}

# Paketle birlikte gelen SAGLAM dosyalarin olculmus parmak izleri.
# Kullanicinin kopyasi bunlardan farkliysa dosya tasima sirasinda
# bozulmus demektir.
BEKLENEN = {
    "arducopter": (
        7230968,
        "c67d78a1dbbf0fcad233080b2144445fb93f8d9675a4388ace7eaff72451341a"),
    "arduplane": (
        7181296,
        "280a1d5da03420d91a5c0d2c8fb3c58dd8556f1069804e26268279e4346d8f40"),
    "arducopter_aarch64": (
        6926016,
        "91615e4f7cd235cb1f8268d2d87a0b35c5303384796cb0f4e2557e24f5d1ab1b"),
    "arduplane_aarch64": (
        6819656,
        "306857451f2577b0f18458bb26c41e5958c3084bf88c594c6dba064e2ee8090e"),
}

ELF_MAKINE = {
    0x03: "i386 (32-bit x86)",
    0x28: "ARM (32-bit)",
    0x3e: "x86-64",
    0xb7: "AArch64 (64-bit ARM)",
    0xf3: "RISC-V",
}

# PE (Windows) COFF Machine alani. Linux tarafinda ELF makine alani
# okunuyordu ama Windows tarafinda bu bilgi hic okunmuyordu.
PE_MAKINE = {
    0x014c: "Windows x86 (32-bit)",
    0x8664: "Windows x64",
    0xaa64: "Windows ARM64",
    0x01c0: "Windows ARM (32-bit)",
    0x01c4: "Windows ARM Thumb-2 (32-bit)",
    0x0200: "Windows Itanium",
}

# Hangi Windows makinesi hangi PE mimarisini calistirabilir.
# Onemli asimetri: ARM64 Windows x64 ikilileri EMULE EDER (Windows 11
# 22000+ ve Windows 10 ARM64 icin gecerlidir), ama x64 Windows ARM64
# ikilisini calistiramaz. Bu yuzden Windows ARM64 icin ayri ikili
# GEREKMEZ; pakete gomulu x64 dosyalari orada da calisir.
PE_UYUM = {
    "amd64": {0x8664, 0x014c},
    "x86_64": {0x8664, 0x014c},
    "arm64": {0xaa64, 0x8664, 0x014c, 0x01c0, 0x01c4},
    "aarch64": {0xaa64, 0x8664, 0x014c, 0x01c0, 0x01c4},
    "x86": {0x014c},
    "i686": {0x014c},
}

# SITL x64 ikilisinin GERCEKTEN istedigi kutuphaneler. `objdump -p` ile
# import tablosu okunarak olculdu, tahmin edilmedi.
DLL_ZORUNLU = (
    "cygwin1.dll", "cyggcc_s-seh-1.dll", "cygstdc++-6.dll",
    "cygiconv-2.dll", "cygintl-8.dll",
)

# ArduPilot dagitiminda bulunur ama SITL x64 icin KULLANILMAZ:
# hicbiri import zincirinde yok ve hepsi PE32 / Intel 80386 (32-bit).
# 64-bit surece 32-bit DLL yuklenemez, dolayisiyla eksiklikleri kusur
# DEGILDIR ve uyari uretmemelidir.
DLL_KULLANILMAZ = (
    "cygatomic-1.dll", "cyggcc_s-1.dll", "cyggomp-1.dll",
    "cygquadmath-0.dll", "cygssp-0.dll",
)

GECTI = 0
KALDI = 0


def olc(baslik, tamam, ayrinti=""):
    global GECTI, KALDI
    if tamam:
        GECTI += 1
        isaret = "GECTI"
    else:
        KALDI += 1
        isaret = "KALDI"
    print("[%s] %s" % (isaret, baslik))
    if ayrinti:
        for satir in str(ayrinti).splitlines():
            print("        " + satir)


def baslik(m):
    print()
    print("=" * 66)
    print(m)
    print("=" * 66)


def mimari_sonek():
    return MIMARI_SONEK.get((platform.machine() or "").lower(), "")


def bicim_oku(yol):
    """Dosyanin ilk baytlarindan bicim/mimari cikarir."""
    try:
        with open(yol, "rb") as f:
            bas = f.read(64)
    except OSError as e:
        return {"bicim": "okunamadi", "hata": str(e)}
    if bas[:4] == b"\x7fELF":
        kucuk = (bas[5] == 1)
        mak = int.from_bytes(bas[18:20], "little" if kucuk else "big")
        return {"bicim": "ELF (Linux)", "makine": mak,
                "makine_ad": ELF_MAKINE.get(mak, hex(mak)),
                "bit": {1: 32, 2: 64}.get(bas[4])}
    if bas[:2] == b"MZ":
        # v2.4.48: PE basligini gercekten cozup mimariyi oku.
        # e_lfanew (0x3c) PE imzasinin ofsetini verir; hemen ardindaki
        # 2 bayt COFF Machine alanidir.
        try:
            with open(yol, "rb") as f:
                bas2 = f.read(1024)
            lfa = int.from_bytes(bas2[0x3c:0x40], "little")
            if 0 < lfa <= len(bas2) - 6 and bas2[lfa:lfa + 4] == b"PE\0\0":
                mak = int.from_bytes(bas2[lfa + 4:lfa + 6], "little")
                return {"bicim": "PE (Windows)", "makine": mak,
                        "makine_ad": PE_MAKINE.get(mak, hex(mak)),
                        "bit": 64 if mak in (0x8664, 0xaa64, 0x0200) else 32}
        except OSError:
            pass
        return {"bicim": "PE (Windows)", "makine_ad": "Windows (mimari okunamadi)"}
    if bas[:4] in (b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe",
                   b"\xca\xfe\xba\xbe"):
        return {"bicim": "Mach-O (macOS)", "makine_ad": "macOS"}
    if bas[:2] == b"#!":
        return {"bicim": "betik", "makine_ad": "betik"}
    try:
        m = bas.decode("utf-8")
        if m.strip() and all((c.isprintable() or c in "\r\n\t") for c in m):
            return {"bicim": "METIN (ikili degil)", "ornek": m[:100]}
    except UnicodeDecodeError:
        pass
    return {"bicim": "bilinmiyor"}


def main():
    kok = os.path.dirname(os.path.abspath(__file__))
    # Kurulum kokunde mi yoksa goktungu/ alt klasorunde mi calistirildi
    aday = [os.path.join(kok, "sitl"), os.path.join(kok, "goktungu", "sitl")]
    sitl_dizin = next((a for a in aday if os.path.isdir(a)), None)

    windows = platform.system().lower().startswith("win")
    sonek = mimari_sonek()

    baslik("GOKTUNGU v2.4.48 - SITL TANILAMA")
    print("Makine     : %s %s" % (platform.system(), platform.machine()))
    print("Python     : %s" % sys.version.split()[0])
    print("Calisilan  : %s" % kok)
    print("SITL dizini: %s" % (sitl_dizin or "BULUNAMADI"))
    if sonek:
        print("Mimari notu: bu makine icin ikili soneki '%s'" % sonek)
        print("             (ArduPilot bu mimari icin hazir SITL")
        print("              yayinlamaz; ikililer pakete gomuludur)")

    # ---- 1. Klasor var mi ----
    baslik("1. SITL KLASORU")
    olc("sitl/ klasoru bulundu", bool(sitl_dizin),
        "" if sitl_dizin else
        "Klasor yok. 'goktungu-sitl-2.4.47.tar.gz' arsivini kurulum\n"
        "klasorune acin:  tar xzf goktungu-sitl-2.4.47.tar.gz")
    if not sitl_dizin:
        return ozet()

    icerik = sorted(os.listdir(sitl_dizin))
    print("Klasor icerigi (%d dosya):" % len(icerik))
    for ad in icerik:
        y = os.path.join(sitl_dizin, ad)
        if os.path.isfile(y):
            print("   %-24s %10d bayt" % (ad, os.path.getsize(y)))

    # ---- 2. Bu makine icin gerekli ikililer ----
    # v2.4.47: dosya adi MIMARIYE gore secilir. aarch64 makinede
    # `arducopter` dosyasini aramak yanlis teshise yol acar.
    baslik("2. BU MAKINE ICIN GEREKLI IKILILER")
    if windows:
        gerekli = ["ArduCopter.elf", "ArduPlane.elf"]
    else:
        gerekli = ["arducopter" + sonek, "arduplane" + sonek]
    print("Aranan dosyalar: %s" % ", ".join(gerekli))
    eksik_ikili = []
    for ad in gerekli:
        y = os.path.join(sitl_dizin, ad)
        varsa = os.path.isfile(y)
        if not varsa:
            eksik_ikili.append(ad)
        ek = ""
        if not varsa:
            if sonek:
                ek = ("Beklenen konum: %s\n"
                      "Bu mimari icin ikili INDIRILEMEZ (ArduPilot\n"
                      "yayinlamaz). 'goktungu-sitl-2.4.47.tar.gz' arsivini\n"
                      "kurulum klasorune acin; icinde bu dosya hazirdir." % y)
            else:
                ek = "Beklenen konum: %s" % y
        olc("%s var" % ad, varsa, ek)

    # aarch64 makinede yalnizca x86 dosyalari varsa bunu ACIKCA soyle:
    # kullanicinin gordugu hata tam bu durumdan cikiyordu.
    if sonek and eksik_ikili:
        x86_var = [a for a in ("arducopter", "arduplane")
                   if os.path.isfile(os.path.join(sitl_dizin, a))]
        if x86_var:
            print()
            print("TESHIS: Klasorde %s dosyalari var ama bunlar x86-64"
                  % ", ".join(x86_var))
            print("        icin derlenmis; bu makine %s."
                  % platform.machine())
            print("        Cozum: 'goktungu-sitl-2.4.47.tar.gz' arsivini acin.")

    # ---- 3. Bicim ve mimari ----
    baslik("3. BICIM VE MIMARI")
    benim = (platform.machine() or "").lower()
    uyum = {
        "x86_64": {0x3e, 0x03}, "amd64": {0x3e, 0x03},
        "i686": {0x03}, "i386": {0x03},
        "aarch64": {0xb7}, "arm64": {0xb7},
        "armv7l": {0x28}, "armv6l": {0x28},
    }.get(benim)
    # Klasordeki TUM ikilileri raporla; kullanici hangi dosyanin ne
    # oldugunu gorebilsin. Ancak GECTI/KALDI yalniz GEREKLI dosyalar icin.
    incelenecek = [a for a in icerik
                   if os.path.isfile(os.path.join(sitl_dizin, a))
                   and not a.lower().endswith(".dll")]
    for ad in incelenecek:
        y = os.path.join(sitl_dizin, ad)
        b = bicim_oku(y)
        isaret = " <- bu makine icin" if ad in gerekli else ""
        print("%-24s -> %s / %s%s"
              % (ad, b.get("bicim"), b.get("makine_ad", "-"), isaret))
    print()
    for ad in gerekli:
        y = os.path.join(sitl_dizin, ad)
        if not os.path.isfile(y):
            continue
        b = bicim_oku(y)
        if windows:
            pe = (b.get("bicim") == "PE (Windows)")
            olc("%s Windows ikilisi" % ad, pe,
                "" if pe else
                "Bu dosya Windows'ta calismaz. Windows icin ArduCopter.elf\n"
                "ve ArduPlane.elf gereklidir (icerikleri PE32+'dir).")
            # v2.4.48: PE olmasi YETMEZ, mimarisi de uymalidir. Onceden
            # bu denetim yoktu ve mimarisi uymayan dosya "gecti" sayilirdi.
            pu = PE_UYUM.get(benim)
            if pe and pu is not None and b.get("makine") is not None:
                ok = b.get("makine") in pu
                olc("%s mimarisi bu Windows'a uygun" % ad, ok,
                    "" if ok else
                    "Dosya %s icin derlenmis, bu makine %s.\n"
                    "Boyle bir surec 0xC000007B (STATUS_INVALID_IMAGE_FORMAT)\n"
                    "ile aninda kapanir. 'goktungu-sitl' arsivini yeniden acin;\n"
                    "Windows ARM64 makineler x64 ikililerini emule ettigi\n"
                    "icin ayri bir ARM64 dosyasi GEREKMEZ."
                    % (b.get("makine_ad"), benim))
            continue
        elf = b.get("bicim") == "ELF (Linux)"
        olc("%s Linux ELF ikilisi" % ad, elf,
            "" if elf else
            "Bu dosya Linux'ta calismaz (bicim: %s). Linux icin uzantisiz\n"
            "'arducopter%s' / 'arduplane%s' dosyalari gereklidir."
            % (b.get("bicim"), sonek, sonek))
        if elf and uyum is not None:
            ok = b.get("makine") in uyum
            if sonek:
                cozum = ("Dosya %s icin derlenmis, bu makine %s.\n"
                         "Bu mimari icin ikili indirilemez; pakete gomulu\n"
                         "gelir. 'goktungu-sitl-2.4.47.tar.gz' arsivini kurulum\n"
                         "klasorune acin."
                         % (b.get("makine_ad"), benim))
            else:
                cozum = ("Dosya %s icin derlenmis, bu makine %s.\n"
                         "GOKTUNGU sanal dron eklerken uygun ikiliyi indirip\n"
                         "yerlestirmeyi dener (internet erisimi gerekir)."
                         % (b.get("makine_ad"), benim))
            olc("%s mimarisi bu makineye uygun" % ad, ok,
                "" if ok else cozum)

    # ---- 4. Boyut ve parmak izi ----
    baslik("4. DOSYA BUTUNLUGU")
    if windows:
        print("Windows ikilileri icin parmak izi karsilastirmasi yapilmaz.")
    else:
        olculen = 0
        for ad in gerekli:
            bek = BEKLENEN.get(ad)
            y = os.path.join(sitl_dizin, ad)
            if not bek or not os.path.isfile(y):
                continue
            bek_boyut, bek_hash = bek
            olculen += 1
            boyut = os.path.getsize(y)
            olc("%s boyutu dogru" % ad, boyut == bek_boyut,
                "" if boyut == bek_boyut else
                "Beklenen %d bayt, bulunan %d bayt. Dosya yarim\n"
                "kopyalanmis olabilir; arsivi yeniden acin."
                % (bek_boyut, boyut))
            if bek_hash.startswith("__"):
                continue          # parmak izi paketleme sirasinda doldurulur
            h = hashlib.sha256()
            with open(y, "rb") as f:
                for blok in iter(lambda: f.read(1 << 20), b""):
                    h.update(blok)
            ayni = h.hexdigest() == bek_hash
            olc("%s icerigi bozulmamis" % ad, ayni,
                "" if ayni else
                "SHA-256 uyusmuyor.\n  beklenen: %s\n  bulunan : %s\n"
                "Dosya tasima sirasinda bozulmus. Arsivi yeniden acin."
                % (bek_hash, h.hexdigest()))
        if not olculen:
            print("Bu makine icin gerekli ikili bulunamadi; butunluk")
            print("olcumu yapilamadi (2. bolume bakin).")

    # ---- 5. Calistirma izni ----
    baslik("5. CALISTIRMA IZNI")
    if windows:
        print("Windows'ta calistirma izni biti yoktur; bu adim atlanir.")
        print("Windows karsiligi DOSYA BLOKESIDIR: internetten inen")
        print("dosyalar bloke gelir ve calistirilamaz. Kaldirmak icin:")
        print("  Get-ChildItem sitl\\* | Unblock-File")
    else:
        for ad in gerekli:
            y = os.path.join(sitl_dizin, ad)
            if not os.path.isfile(y):
                continue
            varsa = os.access(y, os.X_OK)
            if not varsa:
                try:
                    os.chmod(y, os.stat(y).st_mode | 0o111)
                    varsa = os.access(y, os.X_OK)
                    ek = ("Izin yoktu, ONARILDI." if varsa else
                          "chmod calisti ama izin yine yok: dosya sistemi\n"
                          "'noexec' ile baglanmis olabilir. Klasoru yerel\n"
                          "diske tasiyin.")
                except OSError as e:
                    ek = "Izin verilemedi: %s\nElle: chmod +x '%s'" % (e, y)
            else:
                ek = ""
            olc("%s calistirilabilir" % ad, varsa, ek)

    # ---- 6. Gercek calistirma ----
    baslik("6. GERCEK CALISTIRMA DENEMESI")
    ikili = os.path.join(
        sitl_dizin, "ArduCopter.elf" if windows else "arducopter" + sonek)
    if not os.path.isfile(ikili):
        olc("ikili calistirildi", False,
            "Dosya yok, deneme yapilamadi: %s" % ikili)
    else:
        try:
            s = subprocess.run([ikili, "--help"], capture_output=True,
                               timeout=25)
            cikti = ((s.stdout or b"") + (s.stderr or b"")).decode(
                "utf-8", "replace")
            calisti = ("--model" in cikti) or ("--home" in cikti) \
                or ("--wipe" in cikti) or ("speedup" in cikti)
            olc("ikili gercekten calisti", calisti,
                "Cikis kodu: %d\nIlk satir: %s"
                % (s.returncode, cikti.splitlines()[0] if cikti else "(bos)"))
        except PermissionError as e:
            olc("ikili gercekten calisti", False,
                "Izin reddedildi: %s\nElle: chmod +x '%s'" % (e, ikili))
        except OSError as e:
            no = getattr(e, "errno", None)
            ek = ""
            if no == 8:
                ek = ("\nErrno 8 = dosya bu makinede calistirilabilir bir\n"
                      "ikili degil. Yukaridaki 2. ve 3. bolumlere bakin.")
            olc("ikili gercekten calisti", False, "%s%s" % (e, ek))
        except subprocess.TimeoutExpired:
            olc("ikili gercekten calisti", False,
                "25 saniyede yanit vermedi.")

    # ---- 7. Windows DLL ----
    if windows:
        baslik("7. CYGWIN KUTUPHANELERI")
        var = {a.lower() for a in icerik}
        for d in DLL_ZORUNLU:
            olc("%s var" % d, d.lower() in var,
                "" if d.lower() in var else
                "Bu DLL olmadan SITL 0xC0000135 ile aninda kapanir.")

        # v2.4.48: DLL'in VAR olmasi yetmez, mimarisi de ikiliyle ayni
        # olmalidir. 64-bit surece 32-bit DLL yuklenemez; sonuc yine
        # surecin main'e hic girmeden dusmesidir ama cikis kodu farklidir
        # (0xC000007B, 0xC0000135 degil). ArduPilot'un sitl klasoru iki
        # mimariyi BIR ARADA dagittigi icin bu durum gercekten olusabilir.
        ikili_pe = os.path.join(sitl_dizin, "ArduCopter.elf")
        ib = bicim_oku(ikili_pe) if os.path.isfile(ikili_pe) else {}
        imak = ib.get("makine")
        if imak:
            print()
            print("Ikili mimarisi: %s" % ib.get("makine_ad"))
            for d in DLL_ZORUNLU:
                y = os.path.join(sitl_dizin, d)
                if not os.path.isfile(y):
                    continue
                db = bicim_oku(y)
                dmak = db.get("makine")
                if dmak is None:
                    continue
                olc("%s mimarisi ikiliyle ayni" % d, dmak == imak,
                    "" if dmak == imak else
                    "DLL %s, ikili ise %s. Bu esitsizlik 0xC000007B\n"
                    "uretir. DLL'leri baska bir kaynaktan kopyalamayin;\n"
                    "'goktungu-sitl' arsivini bu klasore yeniden acin."
                    % (db.get("makine_ad"), ib.get("makine_ad")))

        # Bilgilendirme: bu bes dosya pakette olabilir ama KULLANILMAZ.
        # Eksikligi kusur degildir; onceki surumlerde "eksik olabilir"
        # diye raporlanip kullaniciyi olmayan bir sorunla ugrastiriyordu.
        kul_var = [d for d in DLL_KULLANILMAZ if d.lower() in var]
        print()
        print("Not: asagidaki dosyalar ArduPilot dagitiminda bulunur ama")
        print("     SITL x64 icin KULLANILMAZ (hepsi 32-bit ve import")
        print("     zincirinde yok). Eksik olmalari bir kusur DEGILDIR:")
        print("     %s" % ", ".join(DLL_KULLANILMAZ))
        if kul_var:
            print("     (bu kurulumda mevcut: %s)" % ", ".join(kul_var))

    return ozet()


def ozet():
    baslik("OZET")
    print("GECTI: %d    KALDI: %d" % (GECTI, KALDI))
    if KALDI == 0:
        print()
        print("SITL kurulumu saglam gorunuyor. Sanal dron eklemeyi\n"
              "yeniden deneyin. Sorun surerse konsol ciktisini paylasin.")
    else:
        print()
        print("Yukarida KALDI olarak isaretlenen maddelerdeki yonlendirmeyi\n"
              "uygulayin. Bu ciktinin tamamini paylasmak en hizli yoldur.")
    return 0 if KALDI == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
