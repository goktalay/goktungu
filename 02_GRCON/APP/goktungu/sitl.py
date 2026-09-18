# -*- coding: utf-8 -*-
"""SITL surec yoneticisi (v2.4.39).

Kullanici karari: "sanal dron olusturdugumuzda aslinda her dronda SITL
olusturacagiz". Yani sanal dron bir taklit DEGIL; her sanal dron gercek bir
ArduPilot SITL surecidir (arducopter / arduplane). Bunun sonucu:

  * Parametreler gercek: WPNAV_SPEED, FRAME_CLASS, ARMING_CHECK ... hepsi
    gercek ucus yaziliminin parametre agacindan gelir.
  * ARM denetimleri gercek: "PreArm: 3D Accel calibration needed" gibi
    mesajlari SITL kendisi uretir (olculdu). v2.4.37'de duzelttigimiz ARM
    CHECK listesi boylece gercek firmware'e karsi sinanabilir.
  * Ucus modlari, gorev davranisi ve angajman gercek koda karsi calisir.

Bu modulun sorumlulugu YALNIZCA surec yasam dongusu: ikili dosyayi bulmak,
bos port blogu secmek, sureci baslatmak/durdurmak, cikis nedenini
raporlamak. MAVLink tarafinda hicbir ozel dal yok: SITL bir TCP portunda
SERIAL0'i dinler, DronYoneticisi.dinle() ona normal bir TCP baglantisi gibi
baglanir (BaglantiYoneticisi.mavutil_url -> "tcp:127.0.0.1:<port>").

Olculmus tuzaklar (ayrintili gerekce: NOT_SITL_2439.md):

  A. `--defaults /dev/null` SITL'i "PANIC: Failed to load defaults" ile
     COKERTIR. Her ornek icin gercek bir .parm dosyasi yazilir.
  B. SITL taban porttan itibaren BIR PORT BLOGU baglar (SERIAL0=base,
     SERIAL1=base+2, SERIAL2=base+3...). Blogun herhangi bir uyesi doluysa
     "bind failed - Address already in use" + cikis kodu 1. Bu yuzden tek
     port degil BLOK bosluk denetlenir.
  C. `--base-port` argumani `-I/--instance`'DAN ONCE gelmeli.
  D. SITL ayaga kalkmasi ~10-14 sn surer ve SERIAL0'a istemci baglanana
     kadar "Waiting for connection ...." der. Baglanma yeniden denemeli
     olmali; bu isi cagirici (dron.dinle) yapar.
  E. Her ornek kendi calisma dizinine ihtiyac duyar: eeprom.bin, loglar.
     Ayni dizinde iki ornek calistirilamaz.
"""
import os
import platform
import socket
import subprocess
import threading
import time

from .sabitler import PROJE_KOKU, _veri_alt_yolu

# SITL ikililerinin arandigi/indirildigi yer
# v2.4.52: veri kokune tasindi. `_veri_yolu` gecis kuralini uygular:
# yeni konumda yoksa ve eski konumda varsa ESKI konum dondurulur,
# boylece v2.4.51 kurulumundaki indirilmis ikililer kaybolmaz.
SITL_KLASORU = _veri_alt_yolu("sitl")
# Her sanal baglantinin kendi calisma dizini (eeprom, log)
# NOT: eski yapida bu yol <kok>/veri/sitl idi; yeni yapida VERI_KOKU
# zaten <kok>/veri oldugu icin "sitl" iki kez gecmemeli. Bu yuzden
# ikili dizin adi ayri tutulur: <kok>/veri/sitl_calisma
CALISMA_KOKU = _veri_alt_yolu("sitl_calisma")

# Dron tipi -> (ikili adi, --model degeri)
# Interceptor bir MAV_TYPE degil; angajman.py tarafindan yonetilen bir ROL.
# Bu yuzden multirotor ile ayni ikiliyi kullanir, ayrimi arac_sinifi yapar.
TIP_ESLEME = {
    "multirotor": ("arducopter", "+"),
    "interceptor": ("arducopter", "+"),
    "sabit_kanat": ("arduplane", "plane"),
    # FAZ18-TIP-KATALOG: sihirbazin resimli tip secimi icin katalog
    # genisletildi. Olculdu (2026-08-18): helikopter ve hexarotor AYNI
    # `arducopter` ikilisini kullanir, yalnizca `--model` degeri degisir;
    # ek indirme GEREKMEZ. ArduPilot dagitiminda `Heli/stable/
    # SITL_x86_64_linux_gnu/` KLASORU YOKTUR (HTTP 404 olculdu), yani
    # helikopter icin ayri ikili aramak bos yoldur.
    #
    # VTOL (quadplane) `arduplane` ikilisini kullanir; sabit_kanat ile
    # ayni indirmeyi paylasir.
    "helikopter": ("arducopter", "heli"),
    "hexarotor": ("arducopter", "hexa"),
    "vtol": ("arduplane", "quadplane"),
}

# Indirme adresleri (2026-08-08'de dogrulandi; bkz. NOT_SITL_2439.md)
INDIRME = {
    "linux": {
        "arducopter": "https://firmware.ardupilot.org/Copter/stable/"
                      "SITL_x86_64_linux_gnu/arducopter",
        "arduplane": "https://firmware.ardupilot.org/Plane/stable/"
                     "SITL_x86_64_linux_gnu/arduplane",
    },
    # v2.4.46: ARM Linux (Raspberry Pi, ARM SBC'ler). Pakete GOMULU ikili
    # x86-64'tur; ARM bir makinede o dosya `Errno 8 Exec format error`
    # verir. O durumda dogru ikili buradan cekilir.
    #
    # DIKKAT - olculdu (2026-08-10): ArduPilot firmware sunucusunda
    # `SITL_arm64_linux_gnu` KLASORU YOKTUR (HTTP 404). Var olan tek ARM
    # secenegi `SITL_arm_linux_gnueabihf` ve icerigi 32-bit ARM EABI5
    # ELF'tir. 64-bit ARM (aarch64) cekirdekler 32-bit ARM ikililerini
    # genellikle calistirir, ancak dagitimda 32-bit calisma zamani
    # kutuphaneleri gerekebilir; ikili statik oldugu icin bu risk kucuk.
    "linux_arm": {
        "arducopter": "https://firmware.ardupilot.org/Copter/stable/"
                      "SITL_arm_linux_gnueabihf/arducopter",
        "arduplane": "https://firmware.ardupilot.org/Plane/stable/"
                     "SITL_arm_linux_gnueabihf/arduplane",
    },
    # Windows ikilileri .elf uzantili olmasina ragmen PE32+ Windows
    # calistirilabilir dosyalaridir (olculdu) ve Cygwin DLL'lerine baglidir.
    "windows": {
        "arducopter": "https://firmware.ardupilot.org/Tools/MissionPlanner/"
                      "sitl/ArduCopter.elf",
        "arduplane": "https://firmware.ardupilot.org/Tools/MissionPlanner/"
                     "sitl/ArduPlane.elf",
    },
}
# ----------------------------------------------------------------------
# v2.4.45: Windows'ta 0xC0000135 (STATUS_DLL_NOT_FOUND) kusuru
# ----------------------------------------------------------------------
# Kullanicidan gelen belirti:
#   [SITL] SITL hemen sonlandi (cikis kodu 3221225781)
# 3221225781 = 0xC0000135 = STATUS_DLL_NOT_FOUND. Surec `main`'e hic
# girmez; yukleyici DLL'i bulamayinca oldurur. Bu yuzden sitl.log BOS
# kalir ve kullanici hicbir ipucu gormez.
#
# Kok neden: Windows SITL ikilisi Cygwin'e baglidir ve v2.4.44'e kadar
# DLL'ler yalnizca `indir()` cagrildiginda, TAHMIN edilmis bir ad
# listesiyle cekiliyordu. Kullanici tam paketi actiginda ikili vardi,
# DLL yoktu -> yukleyici hatasi.
#
# v2.4.45 cozumu iki katmanli:
#   1. sitl/ klasoru PAKETE GOMULUR (kullanici istegi: "gerekli tum
#      dosyalari sisteme bir kere indir, sunucuyu baslatmadan once SITL
#      dosyalari zaten sistemde olsun"). Calisma aninda indirme YOK.
#   2. Baslatmadan ONCE DLL denetimi yapilir; eksik varsa surec hic
#      baslatilmaz ve kullaniciya hangi dosyanin eksik oldugu yazilir.
#
# Asagidaki liste TAHMIN DEGIL: indirilen PE dosyalarinin import
# tablosu okunarak olculdu (bkz. DURUM_2445.md).
#   ArduCopter.elf -> cygwin1.dll, cyggcc_s-seh-1.dll, cygstdc++-6.dll,
#                     KERNEL32.dll, WINMM.dll
#   cygstdc++-6.dll -> cygiconv-2.dll, cygintl-8.dll (gecisli)
# KERNEL32/WINMM Windows'un kendi DLL'leridir.
WINDOWS_DLL_ZORUNLU = (
    "cygwin1.dll",
    "cyggcc_s-seh-1.dll",
    "cygstdc++-6.dll",
    "cygiconv-2.dll",
    "cygintl-8.dll",
)
# v2.4.48 DUZELTMESI: Bu bes dosya ArduPilot dagitiminda bulunur ve
# pakete girer, ancak olculdugunde ikisi de dogru cikti:
#   1. Hicbiri import zincirinde YOK (objdump -p ile dogrulandi)
#   2. Hepsi PE32 / Intel 80386, yani 32-BIT
# 64-bit bir surece 32-bit DLL YUKLENEMEZ. Dolayisiyla bunlar "ileride
# gerekebilecek yedek" degildir; SITL x64 ikilisi icin kullanilmalari
# teknik olarak imkansizdir. Onceki surumlerde "EK" adiyla tutuluyor ve
# tanilamada "eksik olabilir" diye raporlaniyorlardi; bu, olmayan bir
# sorunu varmis gibi gostererek kullaniciyi yanlis yone sevk eder.
# Artik ayri kategoride ve eksiklikleri hicbir kosulda uyari uretmez.
WINDOWS_DLL_KULLANILMAZ = (
    "cygatomic-1.dll", "cyggcc_s-1.dll", "cyggomp-1.dll",
    "cygquadmath-0.dll", "cygssp-0.dll",
)
# Geriye uyumluluk: eski ad disaridan kullanilabiliyordu.
WINDOWS_DLL_EK = WINDOWS_DLL_KULLANILMAZ
WINDOWS_DLL = WINDOWS_DLL_ZORUNLU + WINDOWS_DLL_KULLANILMAZ
DLL_TABAN = "https://firmware.ardupilot.org/Tools/MissionPlanner/sitl/"

# Windows yukleyici hata kodlari -> anlasilir aciklama. Cikis kodu
# imzasiz 32-bit olarak da gelebilir, iki bicim de eslenir.
WINDOWS_CIKIS_KODU = {
    3221225781: ("Eksik DLL (0xC0000135)",
                 "SITL ikilisi Cygwin kutuphanelerine baglidir ve "
                 "bunlar ikilinin yaninda bulunamadi."),
    -1073741515: ("Eksik DLL (0xC0000135)",
                  "SITL ikilisi Cygwin kutuphanelerine baglidir ve "
                  "bunlar ikilinin yaninda bulunamadi."),
    # v2.4.48 DUZELTMESI: Onceki surumde 0xC0000139 icin 3221225595 /
    # -1073741701 yaziliydi; bu degerler YANLISTI. Hesaplandiginda:
    #   0xC0000139 = 3221225785 / -1073741511
    #   0xC000007B = 3221225595 / -1073741701
    # Yani "Bozuk DLL" olarak etiketlenen sayilar aslinda
    # STATUS_INVALID_IMAGE_FORMAT kodlariydi. Sonuc: mimarisi uymayan bir
    # ikili calistirildiginda kullaniciya "karisik DLL surumleri" denip
    # yanlis yone gonderiliyordu. Iki kod artik ayri ve dogru.
    3221225785: ("Bozuk DLL (0xC0000139)",
                 "Bir DLL bulundu ancak beklenen islevi icermiyor; "
                 "karisik surumler olabilir."),
    -1073741511: ("Bozuk DLL (0xC0000139)",
                  "Bir DLL bulundu ancak beklenen islevi icermiyor; "
                  "karisik surumler olabilir."),
    3221225595: ("Uyumsuz ikili bicimi (0xC000007B)",
                 "Ikilinin ya da bagimli bir DLL'in mimarisi bu "
                 "Windows'a uymuyor (ornegin ARM64 dosya x64 makinede, "
                 "ya da 32-bit DLL 64-bit surecte)."),
    -1073741701: ("Uyumsuz ikili bicimi (0xC000007B)",
                  "Ikilinin ya da bagimli bir DLL'in mimarisi bu "
                  "Windows'a uymuyor (ornegin ARM64 dosya x64 makinede, "
                  "ya da 32-bit DLL 64-bit surecte)."),
    3221225477: ("Erisim ihlali (0xC0000005)", "SITL cokme yasadi."),
    -1073741819: ("Erisim ihlali (0xC0000005)", "SITL cokme yasadi."),
}


# ----------------------------------------------------------------------
# CALISTIRMA IZNI ONARIMI (v2.4.46)
# ----------------------------------------------------------------------
# Kullanicidan gelen hata:
#   [SITL] SITL baslatilamadi:
#     [Errno 13] Permission denied: '/home/mkaderoglu/goktungu/sitl/arducopter'
#
# Kok neden: dosya vardi, DLL sorunu da yoktu; yalnizca +x biti yoktu.
# Izin biti dosyanin KENDISINDE tasinmaz - dosya sistemine baglidir.
# Kaybolma yollari (hepsi gercek ve sik):
#   * Windows/OneDrive/NTFS uzerinden kopyalama: NTFS'te execute biti
#     yoktur, ext4'e gecirilirken 0644 olur
#   * Arsivi kurulum betigi yerine elle acmak (chmod adimi hic kosmaz)
#   * FAT32/exFAT USB bellek uzerinden tasima
#   * `cp` yerine dosya yoneticisiyle surukleyip birakma
#
# Bu yuzden izni YALNIZ kurulum betigine birakmak yetersizdir: kullanici
# dosyalari daha sonra baska bir yolla tasidiginda kusur geri gelir.
# Cozum, calistirma anindan once modulun izni KENDISININ onarmasi.
# `chmod` bile basarisiz olursa (salt okunur bagli dosya sistemi, sahibi
# baska kullanici) hata metni ne yapilacagini SOYLER.
IKILI_IZIN = 0o755


# ----------------------------------------------------------------------
# IKILI BICIM / MIMARI DENETIMI (v2.4.46)
# ----------------------------------------------------------------------
# Kullanicidan gelen ikinci hata (izin duzeltildikten SONRA):
#   SITL baslatilamadi: [Errno 8] Exec format error:
#     '/home/mkaderoglu/goktungu/sitl/arducopter'
#
# Errno 8 (ENOEXEC) cekirdegin dosyayi bir calistirilabilir olarak
# tanimadigini soyler. Uc gercek nedeni vardir ve UCU ICIN VERILECEK
# OGUT FARKLIDIR:
#   1. Yanlis isletim sistemi bicimi (Linux'ta PE/Windows ikilisi)
#   2. Yanlis mimari (x86-64 ikili ARM makinede, ya da tersi)
#   3. Dosya bozuk / yarim inmis / metne cevrilmis (OneDrive, git-lfs
#      isaretcisi, HTML hata sayfasi olarak inmis)
#
# Ciplak `Errno 8` bunlarin hicbirini ayirt etmez. Bu yuzden surec
# baslatilmadan ONCE dosyanin ilk baytlari (sihirli sayi) okunur ve
# gercekten bu makinede calisabilir bir ikili olup olmadigi OLCULUR.
#
# Olculmus referans (paketteki dosya, bkz. DURUM_2445.md):
#   7f 45 4c 46 02 01 01 03 ... 02 00 3e 00
#   \x7fELF | 64-bit | LSB | ... | e_machine=0x3e (EM_X86_64)

# ELF e_machine -> okunabilir ad (yalniz ilgili olanlar)
ELF_MAKINE = {
    0x03: "i386 (32-bit x86)",
    0x28: "ARM (32-bit)",
    0x3e: "x86-64",
    0xb7: "AArch64 (64-bit ARM)",
    0xf3: "RISC-V",
}

# platform.machine() ciktisi -> kabul edilebilir ELF e_machine degerleri.
# Cok esleme bilincli: x86_64 cekirdek 32-bit x86 ikilileri de calistirir
# (ia32 destegi acikken), aarch64 cekirdek 32-bit ARM ikililerini
# calistirir. Ters yon CALISMAZ ve hata verilmelidir.
MAKINE_UYUM = {
    "x86_64": {0x3e, 0x03},
    "amd64": {0x3e, 0x03},
    "i686": {0x03},
    "i386": {0x03},
    "aarch64": {0xb7, 0x28},
    "arm64": {0xb7, 0x28},
    "armv7l": {0x28},
    "armv6l": {0x28},
}

# ----------------------------------------------------------------------
# v2.4.48: WINDOWS TARAFI ICIN AYNI OLCUM
# ----------------------------------------------------------------------
# PE (Windows) dosyalarinin mimarisi COFF basligindaki Machine alanindadir.
# Bu degerler Microsoft PE belgelendirmesinden alinmistir.
PE_MAKINE = {
    0x8664: "Windows x64",
    0x014c: "Windows x86 (32-bit)",
    0xAA64: "Windows ARM64",
    0x01c4: "Windows ARM (32-bit)",
    0x0200: "Windows Itanium",
}

# platform.machine() (Windows'ta AMD64 / ARM64) -> kabul edilen PE Machine
# degerleri. Esleme SIMETRIK DEGILDIR ve bu bilinclidir:
#
#   * ARM64 Windows, x64 ve x86 PE ikililerini isletim sistemi duzeyinde
#     EMULE eder (Win10 ARM64 x86, Win11 ARM64 x64/Prism). Bu yuzden
#     ArduPilot'un x64 SITL ikilisi Surface Pro X gibi cihazlarda
#     calisir ve ayri bir ARM64 ikili GEREKMEZ.
#   * Ters yon CALISMAZ: x64 Windows bir ARM64 PE'yi calistiramaz.
#     Bu durumda surec 0xC000007B (STATUS_INVALID_IMAGE_FORMAT) ile
#     duser ve neden hicbir yerde yazmaz. Bu yuzden reddedilir.
#   * x64 Windows 32-bit PE'yi WOW64 ile calistirir; kabul edilir.
PE_UYUM = {
    "amd64": {0x8664, 0x014c},
    "x86_64": {0x8664, 0x014c},
    "x86": {0x014c},
    "i686": {0x014c},
    "arm64": {0xAA64, 0x8664, 0x014c, 0x01c4},
    "aarch64": {0xAA64, 0x8664, 0x014c, 0x01c4},
}


def ikili_bicimi(yol):
    """Dosyanin ilk baytlarindan bicimini cikarir.

    Donus sozlugu: {"bicim": "elf"|"pe"|"macho"|"metin"|"bilinmiyor",
                    "makine": int|None, "makine_ad": str|None,
                    "bit": 32|64|None, "ilk": bytes}

    Dosya okunamazsa bicim "okunamadi" doner.
    """
    try:
        with open(yol, "rb") as f:
            bas = f.read(64)
    except OSError as e:
        return {"bicim": "okunamadi", "makine": None, "makine_ad": None,
                "bit": None, "ilk": b"", "hata": str(e)}
    if bas[:4] == b"\x7fELF":
        bit = {1: 32, 2: 64}.get(bas[4] if len(bas) > 4 else 0)
        mak = None
        if len(bas) >= 20:
            # e_machine: offset 18, 2 bayt, endian EI_DATA'ya bagli
            kucuk = (bas[5] == 1)
            mak = int.from_bytes(bas[18:20], "little" if kucuk else "big")
        return {"bicim": "elf", "makine": mak,
                "makine_ad": ELF_MAKINE.get(mak, mak and hex(mak)),
                "bit": bit, "ilk": bas[:20]}
    if bas[:2] == b"MZ":
        # v2.4.48: PE dosyasinin MIMARISI de okunur. Onceden yalnizca "MZ"
        # imzasina bakiliyordu ve Windows'ta her PE kosulsuz kabul
        # ediliyordu. Bu, ters yonlu uyusmazligi sessizce geciriyordu:
        # ARM64 icin derlenmis bir PE x64 Windows'a konursa dosya kabul
        # edilir, calistirma aninda 0xC000007B ile coker ve neden
        # gorunmez. PE yapisinda mimari COFF basligindadir:
        #   0x3c -> e_lfanew (PE imzasinin ofseti)
        #   +0   -> "PE\0\0"
        #   +4   -> Machine (2 bayt, little endian)
        pmak = None
        try:
            with open(yol, "rb") as f:
                tam = f.read(4096)
            if len(tam) >= 0x40:
                lfa = int.from_bytes(tam[0x3c:0x40], "little")
                if 0 < lfa <= len(tam) - 6 and tam[lfa:lfa + 4] == b"PE\0\0":
                    pmak = int.from_bytes(tam[lfa + 4:lfa + 6], "little")
        except OSError:
            pmak = None
        return {"bicim": "pe", "makine": pmak,
                "makine_ad": PE_MAKINE.get(pmak, "Windows"),
                "bit": {0x8664: 64, 0xAA64: 64, 0x014c: 32,
                        0x01c4: 32}.get(pmak),
                "ilk": bas[:20]}
    if bas[:4] in (b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe",
                   b"\xca\xfe\xba\xbe"):
        return {"bicim": "macho", "makine": None, "makine_ad": "macOS",
                "bit": None, "ilk": bas[:20]}
    # Betik dosyasi da gecerli olabilir (#!/bin/sh ...) - cekirdek onu
    # calistirir, bu yuzden hata sayilmaz.
    if bas[:2] == b"#!":
        return {"bicim": "betik", "makine": None, "makine_ad": "betik",
                "bit": None, "ilk": bas[:20]}
    # Yazdirilabilir karakterlerden olusuyorsa metindir: en sik gorulen
    # bozulma bicimi (HTML hata sayfasi, git-lfs isaretcisi, OneDrive
    # yer tutucusu).
    try:
        metin = bas.decode("utf-8")
        if metin.strip() and all(
                (c.isprintable() or c in "\r\n\t") for c in metin):
            return {"bicim": "metin", "makine": None, "makine_ad": None,
                    "bit": None, "ilk": bas[:20],
                    "ornek": metin[:120]}
    except UnicodeDecodeError:
        pass
    return {"bicim": "bilinmiyor", "makine": None, "makine_ad": None,
            "bit": None, "ilk": bas[:20]}


def bicim_denetle(yol):
    """Ikilinin BU makinede calisabilir bicimde olup olmadigini olcer.

    Donus: (uygun, ileti). `uygun` False ise `ileti` kullaniciya
    gosterilecek, ne oldugunu ve ne yapilacagini SOYLEYEN bir metindir.

    Bu islev `Errno 8`i onlemek icin vardir: cekirdege sormak yerine
    dosyayi kendimiz okuyup nedeni adiyla bildiririz.
    """
    b = ikili_bicimi(yol)
    bicim = b.get("bicim")
    ad = os.path.basename(yol)

    if bicim == "okunamadi":
        return False, ("SITL ikilisi okunamadi (%s): %s"
                       % (ad, b.get("hata")))

    # Boyut denetimi: gercek SITL ikilisi 7 MB'in uzerindedir. Cok kucuk
    # dosya yarim inmis ya da yer tutucudur.
    try:
        boyut = os.path.getsize(yol)
    except OSError:
        boyut = -1
    if 0 <= boyut < 1024 * 1024:
        return False, (
            "SITL ikilisi bozuk gorunuyor: %s yalnizca %d bayt. "
            "Gercek ikili 7 MB'in uzerindedir; dosya yarim inmis ya da "
            "yer tutucu (OneDrive/git-lfs) olabilir. 'goktungu-sitl' "
            "arsivini yeniden acin." % (ad, boyut))

    if bicim == "metin":
        return False, (
            "SITL ikilisi bir ikili dosya degil, METIN icermekte: %s. "
            "Bu genellikle dosyanin bir hata sayfasi olarak indigini ya "
            "da bulut eslemesi (OneDrive/Drive) tarafindan yer tutucuya "
            "cevrildigini gosterir. Ilk satir: %r. 'goktungu-sitl' "
            "arsivini yeniden acin."
            % (ad, (b.get("ornek") or "").strip()[:80]))

    if _windows_mu():
        if bicim == "pe":
            # v2.4.48: PE olmasi YETMEZ, mimarisi de uymalidir. Onceden
            # kosulsuz kabul ediliyordu; ARM64 icin derlenmis bir PE x64
            # Windows'a konsa sessizce geciyor ve surec 0xC000007B ile
            # duserek nedenini hicbir yere yazmiyordu.
            pmak = b.get("makine")
            benim_w = (platform.machine() or "").lower()
            kabul_w = PE_UYUM.get(benim_w)
            if pmak is None or kabul_w is None:
                # Makine alani okunamadi ya da Windows mimarisi taninmadi:
                # engellemek yanlis pozitif riski tasir, cekirdege birakilir.
                return True, None
            if pmak in kabul_w:
                return True, None
            return False, (
                "SITL ikilisi bu Windows makinesinin mimarisine uygun "
                "degil. Dosya: %s (%s icin derlenmis), bu makine: %s. "
                "Windows ARM64 makineler x64 ikilileri emulasyonla "
                "calistirir, ancak TERSI mumkun degildir: x64 bir Windows "
                "ARM64 ikilisini calistiramaz (0xC000007B). Dogru dosya "
                "ArduPilot'un x64 SITL dagitimidir; 'goktungu-sitl' arsivini "
                "'%s' klasorune yeniden acin."
                % (ad, b.get("makine_ad") or "bilinmeyen mimari",
                   benim_w, SITL_KLASORU))
        return False, (
            "SITL ikilisi bu isletim sistemine ait degil: %s bir %s "
            "dosyasi, Windows ise PE (.exe) bicimi bekler. Windows icin "
            "ArduCopter.elf / ArduPlane.elf dosyalari gereklidir."
            % (ad, {"elf": "Linux (ELF)", "macho": "macOS (Mach-O)"}
               .get(bicim, bicim)))

    # Linux / macOS
    if bicim == "betik":
        return True, None
    if bicim == "pe":
        return False, (
            "SITL ikilisi bir WINDOWS dosyasi (%s), bu makine ise Linux. "
            "Windows SITL dosyalari '.elf' uzantili olsa da icerikleri "
            "PE32+ Windows ikilisidir ve Linux'ta calismaz. Linux icin "
            "uzantisiz 'arducopter' / 'arduplane' dosyalari gereklidir; "
            "'goktungu-sitl' arsivi ikisini de icerir." % ad)
    if bicim == "macho":
        return False, (
            "SITL ikilisi bir macOS dosyasi (%s), bu makine ise Linux."
            % ad)
    if bicim != "elf":
        return False, (
            "SITL ikilisinin bicimi taninmadi (%s). Dosya bozuk olabilir; "
            "'goktungu-sitl' arsivini yeniden acin." % ad)

    # ELF: mimari uyumu
    mak = b.get("makine")
    benim = (platform.machine() or "").lower()
    kabul = MAKINE_UYUM.get(benim)
    if kabul is None:
        # Bilinmeyen makine adi: engellemek yerine cekirdege birakiyoruz.
        # Yanlis pozitif, calisan bir kurulumu bloke etmekten kotudur.
        return True, None
    if mak in kabul:
        return True, None
    # v2.4.47: Cozum yolu MIMARIYE gore degisir; tek bir genel ileti
    # kullaniciyi yanlis yone gonderir.
    #   * aarch64 -> ArduPilot ikili YAYINLAMIYOR (HTTP 404). Indirme
    #     onerisi burada YANLIS olur; dogru yol pakete gomulu
    #     `*_aarch64` dosyasidir.
    #   * digerleri -> firmware.ardupilot.org'dan indirilebilir.
    sonek = MIMARI_SONEK.get(benim, "")
    if sonek:
        cozum = ("Bu mimari icin ArduPilot hazir ikili yayinlamaz; gereken "
                 "dosya pakete gomuludur: %s%s. 'goktungu-sitl' arsivini '%s' "
                 "klasorune acin. Tanilama: python3 sitl_tani.py"
                 % ("arducopter" if "copter" in ad.lower() else "arduplane",
                    sonek, SITL_KLASORU))
    else:
        cozum = ("Dogru ikiliyi indirmek icin Baglanti Yoneticisi'nde sanal "
                 "dron eklerken 'SITL indir' secenegini kullanin ya da su "
                 "adresten uygun surumu alip '%s' klasorune koyun: "
                 "firmware.ardupilot.org" % SITL_KLASORU)
    return False, (
        "SITL ikilisi bu makinenin mimarisine uygun degil. Dosya: %s "
        "(%s icin derlenmis), bu makine: %s. %s"
        % (ad, b.get("makine_ad") or "bilinmeyen mimari", benim, cozum))


def izin_onar(yol):
    """Ikilinin calistirma iznini olcer, eksikse onarmayi dener.

    Donus: (tamam, ileti). `tamam` True ise ikili calistirilabilir.
    `ileti` bilgilendirme (onarildi) ya da hata gerekcesi olabilir;
    tamam=True iken de dolu gelebilir, cagirici konsola yazar.

    Windows'ta execute biti kavrami yoktur; os.access(X_OK) orada dosya
    varligina indirgenir. Bu nedenle Windows'ta onarim denenmez.
    """
    if not yol:
        return False, "SITL ikili yolu bos."
    if _windows_mu():
        return True, None
    if os.access(yol, os.X_OK):
        return True, None
    # Once izni onarmayi dene
    try:
        mevcut = os.stat(yol).st_mode
        os.chmod(yol, mevcut | 0o111)   # sahip+grup+diger icin +x
    except OSError as e:
        return False, (
            "SITL ikilisi calistirilabilir degil ve izin duzeltilemedi: "
            "%s (%s). Su komutu elle kosturun:  chmod +x '%s'"
            % (yol, e, yol))
    if os.access(yol, os.X_OK):
        return True, (
            "SITL ikilisinde calistirma izni yoktu, onarildi: %s" % yol)
    # chmod hata vermedi ama izin hala yok: dosya sistemi `noexec` ile
    # baglanmis olabilir. Bu, /tmp ve bazi USB bagalamalarinda gorulur
    # ve chmod sessizce basarili olur.
    return False, (
        "SITL ikilisi calistirilamiyor: %s. Izin verildi ancak dosya "
        "sistemi calistirmaya izin vermiyor olabilir ('noexec' ile "
        "baglanmis bir bolum, USB bellek ya da ag suruculeri). "
        "SITL klasorunu yerel diske (ornegin ana dizininize) tasiyin."
        % yol)


def izin_onar_klasor(klasor=None):
    """SITL klasorundeki TUM ikililerin iznini onarir.

    Acilista bir kez cagrilir. Tek tek onarmayi beklemek yerine hepsini
    birden duzeltmek, kullanicinin sabit kanat denemesinde ayni kusura
    yeniden carpmasini onler.

    Donus: (onarilan_sayi, basarisizlar). Windows'ta (0, []).
    """
    if _windows_mu():
        return 0, []
    kok = klasor or SITL_KLASORU
    onarilan = 0
    basarisiz = []
    try:
        adlar = sorted(os.listdir(kok))
    except OSError:
        return 0, []
    for ad in adlar:
        yol = os.path.join(kok, ad)
        if not os.path.isfile(yol):
            continue
        # DLL'ler Linux'ta calistirilmaz; yalnizca ikilileri hedefle.
        if ad.lower().endswith(".dll"):
            continue
        if os.access(yol, os.X_OK):
            continue
        try:
            os.chmod(yol, os.stat(yol).st_mode | 0o111)
        except OSError as e:
            basarisiz.append("%s (%s)" % (ad, e))
            continue
        if os.access(yol, os.X_OK):
            onarilan += 1
        else:
            basarisiz.append("%s (dosya sistemi noexec olabilir)" % ad)
    return onarilan, basarisiz


def dll_denetle(ikili_yolu):
    """Windows SITL ikilisinin yanindaki DLL'leri denetler.

    Donus: (eksik_zorunlu, eksik_ek). Windows disinda ikisi de bos.

    Neden gerekli: DLL eksikse surec `main`'e hic girmez, sitl.log bos
    kalir ve tek ipucu 0xC0000135 sayisi olur. Baslatmadan once
    denetleyip adini yazmak, kullaniciyi tahminden kurtarir.

    v2.4.48: Ikinci donus degeri artik DAIMA bostur. Onceden
    WINDOWS_DLL_EK icindeki bes dosyanin eksikligi "ek eksik" olarak
    bildiriliyordu; oysa o dosyalar 32-bit ve import zincirinde hic yok,
    yani 64-bit SITL surecinde kullanilmalari imkansiz. Eksikliklerini
    raporlamak olmayan bir sorunu varmis gibi gosteriyordu. Donus imzasi
    cagiricilar bozulmasin diye korundu.
    """
    if not _windows_mu() or not ikili_yolu:
        return [], []
    dizin = os.path.dirname(os.path.abspath(ikili_yolu))
    try:
        var = {a.lower() for a in os.listdir(dizin)}
    except OSError:
        return list(WINDOWS_DLL_ZORUNLU), []
    eksik_z = [d for d in WINDOWS_DLL_ZORUNLU if d.lower() not in var]
    return eksik_z, []


def dll_mimari_denetle(ikili_yolu):
    """Zorunlu DLL'lerin MIMARISININ ikiliyle uyustugunu olcer.

    Donus: uyusmayanlarin listesi [(dosya, dll_mimari_ad, ikili_mimari_ad)].
    Windows disinda ya da olculemezse bos liste.

    Neden ayri bir denetim: DLL'in VAR olmasi yetmez, ayni mimaride de
    olmasi gerekir. 64-bit bir surece 32-bit DLL yuklenemez ve sonuc yine
    surecin `main`'e hic girmeden dusmesidir - ama bu kez cikis kodu
    0xC0000135 degil 0xC000007B olur. Iki kodu ayirt etmeyen bir tanilama
    kullaniciyi "eksik dosya" aramaya gonderir; oysa dosya yerindedir,
    yalnizca yanlis mimaridedir. Bu kusur bicimi Cygwin dagitimlarinda
    gercektir: ArduPilot sitl klasoru 32-bit ve 64-bit DLL'leri BIR ARADA
    dagitir (olculdu: 5 dosya PE32 Intel 80386, 5 dosya PE32+ x86-64).
    """
    if not _windows_mu() or not ikili_yolu:
        return []
    try:
        ib = ikili_bicimi(ikili_yolu)
    except Exception:
        return []
    imak = ib.get("makine")
    if not imak:
        return []
    dizin = os.path.dirname(os.path.abspath(ikili_yolu))
    uyusmaz = []
    for dll in WINDOWS_DLL_ZORUNLU:
        yol = os.path.join(dizin, dll)
        if not os.path.isfile(yol):
            continue  # eksiklik dll_denetle()'nin isi
        try:
            db = ikili_bicimi(yol)
        except Exception:
            continue
        dmak = db.get("makine")
        if dmak and dmak != imak:
            uyusmaz.append((dll,
                            PE_MAKINE.get(dmak, hex(dmak)),
                            PE_MAKINE.get(imak, hex(imak))))
    return uyusmaz


def cikis_kodu_acikla(kod):
    """Surec cikis kodunu okunabilir bir aciklamaya cevirir."""
    try:
        k = int(kod)
    except (TypeError, ValueError):
        return None
    eslesme = WINDOWS_CIKIS_KODU.get(k)
    if eslesme:
        return "%s - %s" % eslesme
    if k == 1:
        return ("Cikis kodu 1 - genellikle port cakismasi "
                "(bind failed - Address already in use) ya da "
                "gecersiz parametre dosyasi.")
    return None


def _windows_mu():
    return platform.system().lower().startswith("win")


# ----------------------------------------------------------------------
# v2.4.47: MIMARIYE GORE IKILI SONEKI
# ----------------------------------------------------------------------
# Kullanicidan gelen belirti (v2.4.46 tanilamasi dogru teshis koydu):
#   SITL baslatilamadi - dosya bu makinede calistirilabilir bir ikili degil:
#   .../sitl/arducopter (bulunan bicim: elf, mimari: ARM (32-bit);
#   bu makine: aarch64)
#
# Kok neden iki katmanliydi:
#   1. `goktungu/sitl/arducopter` PAKETE GOMULU dosyadir ve x86-64'tur.
#      aarch64 bir makinede calismaz.
#   2. v2.4.46'nin kurtarma yolu aarch64'te `SITL_arm_linux_gnueabihf`
#      (32-BIT ARM) ikilisini indirdi, cunku ArduPilot dagitiminda
#      aarch64 SITL YOKTUR (olculdu: SITL_arm64_linux_gnu -> HTTP 404).
#      32-bit ARM ikilisi de aarch64'te calismadi.
#
# Cozum: aarch64 ikilileri ArduPilot kaynagindan capraz derlenip
# (`--static`, sifir dinamik bagimlilik) `_aarch64` sonekiyle pakete
# GOMULDU. Mevcut x86-64 dosyalarina DOKUNULMADI; boylece tek paket her
# iki mimariyi tasir ve x86 kurulumlar bozulmaz.
#
# platform.machine() -> ikili adi soneki. Sonek YOKSA (x86_64) bos dizge.
MIMARI_SONEK = {
    "aarch64": "_aarch64",
    "arm64": "_aarch64",
}


def _mimari_sonek():
    """Bu makine icin SITL ikili sonekini dondurur ('' ya da '_aarch64')."""
    return MIMARI_SONEK.get((platform.machine() or "").lower(), "")


def ikili_adaylari(ikili):
    """`ikili` icin aranacak dosya yollarini sirayla dondurur.

    Sira bilinclidir: kullanicinin kendi derledigi ya da Mission Planner ile
    gelen ikili varsa onu kullanmak, yeniden indirmekten iyidir.

    v2.4.47: Linux'ta MIMARIYE ozgu dosya ONCE denenir. Onceden yalnizca
    `arducopter` araniyordu; aarch64 makinede bu dosya x86-64 oldugu icin
    bulunuyor, "hazir" sayiliyor ve calistirma aninda `Errno 8` veriyordu.
    """
    adaylar = []
    if _windows_mu():
        ad = "ArduCopter.elf" if ikili == "arducopter" else "ArduPlane.elf"
        adaylar.append(os.path.join(SITL_KLASORU, ad))
        yerel = os.environ.get("LOCALAPPDATA")
        if yerel:
            adaylar.append(os.path.join(yerel, "Mission Planner", "sitl", ad))
        pf = os.environ.get("PROGRAMFILES(X86)") or os.environ.get(
            "PROGRAMFILES")
        if pf:
            adaylar.append(os.path.join(pf, "Mission Planner", "sitl", ad))
    else:
        sonek = _mimari_sonek()
        if sonek:
            # Mimariye ozgu dosya once. Bulunamazsa sonek'siz ada dusulur;
            # kullanici kendi derledigi ikiliyi o adla koymus olabilir.
            adaylar.append(os.path.join(SITL_KLASORU, ikili + sonek))
        adaylar.append(os.path.join(SITL_KLASORU, ikili))
    return adaylar


def ikili_bul(tip, ayar_yolu=None):
    """Tip icin SITL ikilisini bulur.

    Donus: (yol, model, hata). Bulunamazsa yol None ve hata kullaniciya
    gosterilebilir bir metindir. Sessiz basarisizlik YOK: v2.4.38'de tam
    bunu duzelttik, komutun sessizce dusmesi en pahali kusur tipi.
    """
    ikili, model = TIP_ESLEME.get(
        str(tip or "").lower(), TIP_ESLEME["multirotor"])

    # 1) Kullanicinin ayarlardan verdigi acik yol
    if ayar_yolu:
        y = str(ayar_yolu).strip()
        if y and os.path.isdir(y):
            for ad in (ikili, ikili + ".exe",
                       "ArduCopter.elf" if ikili == "arducopter"
                       else "ArduPlane.elf"):
                t = os.path.join(y, ad)
                if os.path.isfile(t):
                    return t, model, None
        elif y and os.path.isfile(y):
            return y, model, None

    # 2) Bilinen konumlar
    #
    # v2.4.47: Aday YALNIZ var oldugu icin secilmez; bu makinede
    # CALISTIRILABILIR olup olmadigi da olculur. Onceden ilk var olan
    # dosya donuyordu: aarch64 makinede x86-64 `arducopter` bulunuyor,
    # "hazir" sayiliyor ve hata ancak calistirma aninda (`Errno 8`)
    # ortaya cikiyordu. Simdi uymayan aday ATLANIR ve sonraki denenir.
    uymayan = []
    for aday in ikili_adaylari(ikili):
        if not os.path.isfile(aday):
            continue
        uygun, neden = bicim_denetle(aday)
        if uygun:
            return aday, model, None
        uymayan.append((aday, neden))

    # 3) PATH (kaynaktan derlemis kullanici)
    from shutil import which
    p = which(ikili)
    if p:
        uygun, neden = bicim_denetle(p)
        if uygun:
            return p, model, None
        uymayan.append((p, neden))

    # Dosya VAR ama hicbiri bu makinede calismiyor: bu, "bulunamadi"dan
    # tamamen farkli bir durumdur ve cozumu de farklidir. Ayni iletiyi
    # vermek kullaniciyi yanlis yone gonderir.
    if uymayan:
        yol, neden = uymayan[0]
        return None, model, (
            "SITL ikilisi var ama bu makinede calistirilamiyor: %s (%s). "
            "Mimari: %s. Bu surumde aarch64 icin `%s%s` dosyasi pakete "
            "gomuludur; 'goktungu-sitl' arsivini yeniden acin ya da kurulum "
            "betigini tekrar kosturun."
            % (yol, neden, platform.machine() or "bilinmiyor",
               ikili, _mimari_sonek() or "")
        )

    return None, model, (
        f"SITL ikilisi bulunamadi: {ikili}. "
        f"Sanal dron gercek ArduPilot SITL surecidir; ikili dosya gerekir. "
        f"Beklenen konum: "
        f"{os.path.join(SITL_KLASORU, ikili + _mimari_sonek())}"
    )


def _port_bos_mu(port):
    """Tek bir TCP portunun bagli olup olmadigini olcer."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("0.0.0.0", port))
        return True
    except OSError:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def blok_bos_mu(taban, genislik=10):
    """Taban porttan itibaren BLOGUN tamami bos mu?

    SITL yalniz SERIAL0'i degil SERIAL1 (taban+2) ve SERIAL2 (taban+3)
    portlarini da baglar; birinin dolu olmasi sureci oldurur (olculdu).
    """
    for p in range(taban, taban + genislik):
        if not _port_bos_mu(p):
            return False
    return True


def bos_taban_port(baslangic, adim=10, deneme=50, kullanilan=()):
    """Bos bir port BLOGU'nun taban portunu dondurur."""
    p = int(baslangic)
    for _ in range(deneme):
        if p not in kullanilan and blok_bos_mu(p, adim):
            return p
        p += adim
    return None


class SitlYoneticisi:
    """Sanal baglanti id'si -> SITL sureci eslemesini tutar."""

    def __init__(self, konsol, ayarlar=None):
        self.konsol = konsol
        self._ayarlar = ayarlar
        self._kilit = threading.Lock()
        self._surecler = {}     # bid -> subprocess.Popen
        self._bilgi = {}        # bid -> {"port":.., "tip":.., "dizin":..}
        # v2.4.252 (IS150): PANIC gozcusu KALDIRILDI (kullanici istegi). SITL
        # panigi (GPS'siz GUIDED / gecersiz irtifa) artik kaynakta onlenir:
        # makro API'si irtifa<=0 hedefini ve konumsuz GUIDED'i reddeder.
        # Otomatik yeniden baslatma yok; sanal dron paniklerse Baglanti
        # Yoneticisi'nden elle baslatilir.

    # ------------------------------------------------------------------
    def _ayar_yolu(self):
        if not self._ayarlar:
            return None
        try:
            # AyarYoneticisi'nin okuma metodu yukle() (oku() YOK — bu
            # yanlis ad sessizce Exception'a dusup ozel yolu yok saydirirdi)
            return (self._ayarlar.yukle() or {}).get("sitl_yolu")
        except Exception:
            return None

    # ------------------------------------------------------------------
    def _mimari_kurtar(self, tip):
        """Mimari uyusmazliginda dogru ikiliyi indirip kurtarmayi dener.

        Donus: (yeni_yol | None, ileti). Basarisizsa yeni_yol None'dur ve
        ileti nedeni anlatir.

        Neden gerekli: pakete GOMULU ikili x86-64'tur. Kullanici ARM bir
        makinede (Raspberry Pi, ARM sunucu) calistirirsa `Errno 8` alir ve
        elinde hicbir cozum yolu olmaz - dosyayi kendisi bulup indirmesi
        beklenemez. Bu islev makinenin mimarisine uygun ikiliyi cekip
        `sitl/` klasorune yerlestirir. Bir kez yapilir; sonraki
        calistirmalarda dosya zaten dogrudur.

        Yalniz Linux'ta cagrilir (Windows'ta tek mimari destegi vardir).

        v2.4.47 - iki degisiklik:
          * aarch64'te ONCE pakete gomulu `*_aarch64` dosyasi denenir.
            Indirme YOLU YOKTUR: ArduPilot dagitiminda aarch64 SITL
            bulunmaz (olculdu, HTTP 404). v2.4.46 bu yuzden 32-bit ARM
            ikilisi indirip kullaniciyi ayni hataya ikinci kez dusurdu.
          * Indirilen/secilen dosya, mimariye ozgu ADA yazilir; x86-64
            dosyasinin uzerine yazip x86 kurulumlari bozmaz.
        """
        makine = (platform.machine() or "").lower()
        ikili, _model = TIP_ESLEME.get(
            str(tip or "").lower(), TIP_ESLEME["multirotor"])
        sonek = _mimari_sonek()

        # 1) Mimariye ozgu GOMULU dosya. En hizli ve en guvenilir yol;
        #    ag erisimi gerektirmez. aarch64 icin tek gecerli yol budur.
        if sonek:
            gomulu = os.path.join(SITL_KLASORU, ikili + sonek)
            if os.path.isfile(gomulu):
                uygun, neden = bicim_denetle(gomulu)
                if uygun:
                    return gomulu, ("Mimariye uygun gomulu SITL ikilisi "
                                    "kullanildi: %s" % gomulu)
                # Dosya var ama bozuk/uyumsuz: sessizce gecmek yanlis olur.
                self.konsol("SITL",
                            "Gomulu %s dosyasi kullanilamadi: %s"
                            % (ikili + sonek, neden))

        if makine in ("x86_64", "amd64", "i686", "i386"):
            # x86 makinede gomulu ikili dogru olmaliydi; demek ki dosya
            # bozuk. Yeniden indirmek bunu da onarir.
            anahtar = "linux"
        elif makine in ("armv7l", "armv6l"):
            anahtar = "linux_arm"
        elif makine in ("aarch64", "arm64"):
            # ArduPilot aarch64 SITL YAYINLAMIYOR. 32-bit ARM ikilisini
            # indirmek COZUM DEGILDIR (v2.4.46'da denendi, ayni hata).
            return None, (
                "Bu makine aarch64 (64-bit ARM) ve pakete gomulu "
                "`%s%s` dosyasi bulunamadi. ArduPilot dagitiminda "
                "aarch64 SITL ikilisi YOKTUR, bu yuzden indirilemez. "
                "'goktungu-sitl' arsivini kurulum klasorune acin; icinde "
                "aarch64 ikilileri hazirdir. Tanilama icin: "
                "python3 sitl_tani.py"
                % (ikili, sonek or "_aarch64"))
        else:
            return None, (
                "Bu makine mimarisi (%s) icin hazir SITL ikilisi yok. "
                "ArduPilot kaynagindan kendiniz derlemeniz gerekir."
                % makine)
        url = (INDIRME.get(anahtar) or {}).get(ikili)
        if not url:
            return None, ("'%s' mimarisi icin %s indirme adresi tanimli "
                          "degil." % (makine, ikili))
        self.konsol("SITL",
                    "Makine mimarisi %s; uygun SITL ikilisi indiriliyor "
                    "(%s). Bu bir kez yapilir." % (makine, ikili))
        # Mimariye ozgu ada yaz; x86-64 dosyasinin uzerine YAZMA.
        hedef = os.path.join(SITL_KLASORU, ikili + sonek)
        gecici = hedef + ".indiriliyor"
        import urllib.request
        try:
            os.makedirs(SITL_KLASORU, exist_ok=True)
            with urllib.request.urlopen(url, timeout=300) as r, \
                    open(gecici, "wb") as f:
                while True:
                    blok = r.read(262144)
                    if not blok:
                        break
                    f.write(blok)
        except Exception as e:
            # Yarim dosya birakmak, sonraki denemede "var" gorunup
            # denetimi yanlis gecirir.
            try:
                if os.path.exists(gecici):
                    os.remove(gecici)
            except OSError:
                pass
            return None, ("Uygun SITL ikilisi indirilemedi: %s. Internet "
                          "erisimini denetleyin." % e)
        # Indirilen dosyayi kabul etmeden ONCE dogrula: yanlis dosyayi
        # yerine koymak, kullaniciyi ayni hataya ikinci kez dusurur.
        uygun, neden = bicim_denetle(gecici)
        if not uygun:
            try:
                os.remove(gecici)
            except OSError:
                pass
            return None, ("Indirilen SITL ikilisi de uygun degil: %s"
                          % neden)
        try:
            os.replace(gecici, hedef)
            os.chmod(hedef, IKILI_IZIN)
        except OSError as e:
            return None, ("Indirilen ikili yerine konamadi: %s" % e)
        return hedef, ("Uygun SITL ikilisi kuruldu: %s" % hedef)

    @staticmethod
    def alt_kimlik(bid, sira):
        """Ayni sanal kayit altindaki ek ornekler icin ic kimlik uretir.

        Adet > 1 oldugunda tek bir baglanti kaydi birden fazla SITL sureci
        dogurur. Surecler bid'e gore saklandigindan ikinci ornek birinciyi
        sozlukte EZER; sonra durdur() yalniz son sureci oldurur ve digeri
        zombi olarak port blogunu tutmaya devam ederdi. Bu yuzden ek
        ornekler cakismayan turetilmis kimlikler alir.

        Kimlikler bid ile ayni araliga dusmemeli: 1_000_000 tabani, gercek
        baglanti id'lerinin (AUTOINCREMENT) asla ulasmayacagi bir bolge.
        """
        return 1_000_000 + (int(bid) * 100) + int(sira)

    def alt_kimlikler(self, bid):
        """Bir kayda ait TUM ic kimlikleri (ana + ek ornekler) dondurur."""
        bid = int(bid)
        taban = self.alt_kimlik(bid, 0)
        with self._kilit:
            hepsi = list(self._surecler.keys())
        return [bid] + [k for k in hepsi
                        if taban <= k < taban + 100]

    # MAVLink sysid alani 8 bittir: gecerli aralik 1..255 (0 ayrilmis).
    # Gercek dronlar tipik olarak 1..20 araligindadir (ArduPilot varsayilani
    # 1), bu yuzden sanal araclar 100+ bolgesinden secilir; boylece ayni GCS
    # oturumunda gercek bir dronla sanal bir dron cakismaz.
    SANAL_SYSID_TABAN = 100
    SANAL_SYSID_UST = 255

    def sysid_uret(self, bid, sira=0):
        """Bir sanal ornek icin KURULUM GENELINDE benzersiz sysid uretir.

        v2.4.40 kusuru (olculdu, NOT_SITL_SYSID_2440.md): sysid kayit-ici
        sayaçtan (`i + 1`) turetiliyordu ve `adet == 1` iken hic verilmiyordu.
        Sonuc: iki ayri sanal baglantinin ikisi de SITL varsayilani olan
        MAV_SYSID=1 ile yayin yapiyor, DronYoneticisi dronlari sysid'e gore
        sozlukte tuttugu icin ikinci arac birincisini eziyor ve kullanici tek
        dron goruyordu.

        Cozum: sysid baglanti kaydi id'sinden (AUTOINCREMENT, kurulum
        genelinde benzersiz) turetilir:

            taban + (bid * 10) + sira

        `bid * 10` her kayda kendi 10'luk blogunu verir; adet en cok 10
        oldugu icin ornekler blok icinde cakismaz.

        Aralik tasmasi sessizce sarmalanamaz (sarmalama gizli cakisma
        uretir): 255 asilirsa deger araliga katlanir ve o an KULLANIMDA olan
        sysid'ler atlanarak ilk bos degere yerlesir.
        """
        taban = self.SANAL_SYSID_TABAN
        genislik = self.SANAL_SYSID_UST - taban + 1  # 100..255 -> 156 yuva
        ham = taban + (int(bid) * 10) + int(sira)
        if ham <= self.SANAL_SYSID_UST:
            aday = ham
        else:
            aday = taban + ((ham - taban) % genislik)

        with self._kilit:
            kullanilan = {(v or {}).get("sysid")
                          for v in self._bilgi.values()}
        kullanilan.discard(None)
        if aday not in kullanilan:
            return aday
        # Katlanma sonrasi cakisma: araligi tarayip ilk bos yuvayi al.
        for k in range(genislik):
            alt = taban + ((aday - taban + k + 1) % genislik)
            if alt not in kullanilan:
                return alt
        # 156 sanal aracin tamami dolu — pratikte imkansiz, ama sessiz
        # cakisma yerine aciklanabilir bir deger dondurulur.
        return aday

    def calisiyor_mu(self, bid):
        with self._kilit:
            p = self._surecler.get(int(bid))
        return bool(p and p.poll() is None)

    def bilgi(self, bid):
        with self._kilit:
            return dict(self._bilgi.get(int(bid)) or {})

    def sysid_bilgi(self, sysid):
        """Yalnız canlı bir SITL sürecine ait sysid bilgisini döndürür.

        Bu sorgu hem süreç sözlüğünü hem de kayıt bilgisini aynı kilit altında
        denetler. Böylece bir süreç durdurulurken eski bir ``_bilgi`` kaydıyla
        yanlışlıkla yetkilendirme yapılamaz. Dönüş değeri salt-okunur kopyadır;
        eşleşme yoksa, süreç sonlanmışsa veya sysid geçersizse boş sözlüktür.
        """
        try:
            sysid = int(sysid)
        except (TypeError, ValueError):
            return {}
        with self._kilit:
            for bid, bilgi in self._bilgi.items():
                if int((bilgi or {}).get("sysid") or -1) != sysid:
                    continue
                surec = self._surecler.get(bid)
                if surec is None or surec.poll() is not None:
                    return {}
                sonuc = dict(bilgi or {})
                sonuc["bid"] = int(bid)
                sonuc["calisiyor"] = True
                return sonuc
        return {}

    def durum_ozeti(self):
        """Arayuze gonderilecek ozet: hangi sanal baglanti calisiyor."""
        with self._kilit:
            ozet = {}
            for bid, p in self._surecler.items():
                ozet[str(bid)] = {
                    "calisiyor": p.poll() is None,
                    "port": (self._bilgi.get(bid) or {}).get("port"),
                    "tip": (self._bilgi.get(bid) or {}).get("tip"),
                }
        return ozet

    # ------------------------------------------------------------------
    def baslat(self, bid, tip, lat, lon, taban_port, sysid=None, irtifa=None,
               sira=0):
        """SITL surecini baslatir.

        Donus: (port, hata). Basarisizsa port None.

        `sysid` verilmezse burada URETILIR (None ile calistirmak SITL'i
        varsayilan MAV_SYSID=1'e dusurur ve coklu sanal dronda telemetri
        cakismasina yol acar). Boylece kusur cagirici tarafinda tekrar
        edilemez: modul asla sysid'siz surec baslatmaz.
        """
        bid = int(bid)
        if not sysid:
            sysid = self.sysid_uret(bid, sira)
        if self.calisiyor_mu(bid):
            return self.bilgi(bid).get("port"), None

        yol, model, hata = ikili_bul(tip, self._ayar_yolu())
        if not yol:
            return None, hata

        # v2.4.45: DLL denetimi surec baslatilmadan ONCE.
        # DLL eksikken Popen basarili olur, surec 0xC0000135 ile aninda
        # oldurulur ve sitl.log bos kalir -> kullanici hicbir sey
        # ogrenemez. Onceden denetleyip adini yaziyoruz.
        # v2.4.46: CALISTIRMA IZNI, DLL denetiminden ONCE.
        # Kullanicidan gelen hata `[Errno 13] Permission denied` idi.
        # Popen bu durumda OSError atar; hata metni dosya adini verir ama
        # NE YAPILACAGINI soylemez. Burada izni once onarmayi deniyoruz;
        # onarilabiliyorsa kullanici hicbir sey yapmadan ucusa devam eder.
        izin_ok, izin_ileti = izin_onar(yol)
        if izin_ileti:
            self.konsol("SITL", izin_ileti,
                        "uyari" if izin_ok else "hata")
        if not izin_ok:
            return None, izin_ileti

        # v2.4.46: BICIM/MIMARI DENETIMI.
        # Izin verildikten sonra kullanici `[Errno 8] Exec format error`
        # aldi. O hata ciplak halde uc ayri nedeni ayirt etmez; burada
        # dosyayi kendimiz okuyup nedeni adiyla bildiriyoruz.
        # Mimari uyusmazliginda yalniz hata vermek yetmez: dogru ikiliyi
        # indirip kurtarmayi DENERIZ, cunku kullanicinin elinde baska bir
        # cozum yolu yok.
        bicim_ok, bicim_ileti = bicim_denetle(yol)
        if not bicim_ok:
            self.konsol("SITL", bicim_ileti, "hata")
            kurtarildi = False
            if not _windows_mu():
                yeni_yol, kurtar_ileti = self._mimari_kurtar(tip)
                if yeni_yol:
                    self.konsol("SITL", kurtar_ileti, "basari")
                    yol = yeni_yol
                    kurtarildi = True
                elif kurtar_ileti:
                    self.konsol("SITL", kurtar_ileti, "uyari")
            if not kurtarildi:
                return None, bicim_ileti

        eksik_z, eksik_e = dll_denetle(yol)
        if eksik_z:
            return None, (
                "SITL baslatilamaz: Cygwin kutuphaneleri eksik (%s). "
                "Bu dosyalar '%s' klasorunde, ikilinin yaninda "
                "bulunmalidir. Tam paketi yeniden kurun ya da "
                "goktungu-sitl arsivini bu klasore acin."
                % (", ".join(eksik_z), os.path.dirname(yol)))
        if eksik_e:
            self.konsol("SITL",
                        "Istege bagli DLL yok (%s) - baslatma denenecek"
                        % ", ".join(eksik_e), "uyari")

        # v2.4.48: DLL'ler VAR ama mimarileri uymuyor olabilir. Bu, eksik
        # DLL'den ayri bir kusurdur ve farkli cikis kodu uretir
        # (0xC000007B, 0xC0000135 degil). Ayirt etmemek kullaniciyi var
        # olan bir dosyayi aramaya gonderir. ArduPilot'un sitl klasoru
        # 32-bit ve 64-bit DLL'leri bir arada dagittigi icin bu durum
        # gercekten olusabilir: yanlis dosya kopyalanmasi yeter.
        dll_uyusmaz = dll_mimari_denetle(yol)
        if dll_uyusmaz:
            satir = "; ".join(
                "%s: %s (ikili: %s)" % (d, dm, im)
                for d, dm, im in dll_uyusmaz)
            return None, (
                "SITL baslatilamaz: Cygwin kutuphanelerinin mimarisi "
                "ikiliyle uyusmuyor (%s). Dosyalar yerinde ama yanlis "
                "mimaride; boyle bir surec 0xC000007B ile aninda kapanir. "
                "'goktungu-sitl' arsivini '%s' klasorune yeniden acin ve "
                "DLL'leri baska bir kaynaktan kopyalamayin."
                % (satir, os.path.dirname(yol)))

        # Tuzak B: BLOK bosluk denetimi. Kayitli port dolu olabilir
        # (baska bir surec kapmis olabilir), o zaman kaydirilir.
        with self._kilit:
            mesgul = {(v or {}).get("port") for v in self._bilgi.values()}
        port = bos_taban_port(int(taban_port), kullanilan=mesgul)
        if port is None:
            return None, ("Bos SITL port blogu bulunamadi. "
                          "Calisan sanal dronlari durdurup yeniden deneyin.")

        # Tuzak E: her ornek kendi dizini
        dizin = os.path.join(CALISMA_KOKU, str(bid))
        try:
            os.makedirs(dizin, exist_ok=True)
        except OSError as e:
            return None, f"SITL calisma dizini olusturulamadi: {e}"

        # Tuzak A: gercek bir defaults dosyasi ZORUNLU
        parm = os.path.join(dizin, "varsayilan.parm")
        try:
            with open(parm, "w", encoding="utf-8") as f:
                # FRAME_CLASS multirotor icin anlamli; plane'de yok sayilir.
                f.write("FRAME_CLASS 1\n")
                # Sanal dronda GCS heartbeat kaybi yuzunden failsafe
                # tetiklenmesi test akisini bozar.
                f.write("FS_GCS_ENABLE 0\n")
                # MAV_SYSID hem komut satirinda hem varsayilan parametre
                # dosyasinda verilir. Gerekcesi: `--sysid` yalnizca surecin
                # o anki calismasini etkiler, eeprom.bin'de kalici bir
                # MAV_SYSID varsa (onceki bir calistirmadan) firmware onu
                # okuyabilir. Ikisini birlikte yazmak degeri her iki yoldan
                # da sabitler.
                f.write("MAV_SYSID %d\n" % int(sysid))
                # ------------------------------------------------------
                # v2.4.43: sanal dron ARM EDILEMIYORDU
                # ------------------------------------------------------
                # Belirti (olculdu, /tmp/goktungu43.log):
                #   [DRON] [230] PreArm: 3D Accel calibration needed
                # Sanal dron ARM edilemiyor -> AUTO moda gecemiyor ->
                # gorev ucusu ve ANGAJMAN DENEMESI yapilamiyor. Sanal
                # dronun tek varlik sebebi bu oldugu icin urun kusuru.
                #
                # Kok neden: SITL'de ivmeolcer benzetilmis, kalibrasyon
                # kaydi yok; firmware "hic kalibre edilmemis" diyor.
                #
                # Yanlis yollar (ikisi de OLCULDU, ISE YARAMADI):
                #  - `ARMING_CHECK 0`: bu firmware'de boyle bir parametre
                #    YOK. `--defaults` bilinmeyen satiri sessizce gecer,
                #    bu yuzden "yazdim, oldu" sanilir. Canli parametre
                #    listesinde ARMING_CHECK bulunmuyor.
                #  - `INS_ACC*OFFS/SCAL` + `COMPASS_OFS_*` yazmak:
                #    degerler firmware'e giriyor (okundu: 0.001/1.001)
                #    ama PreArm hala reddediyor.
                #
                # Dogru yol: `ARMING_SKIPCHK` bit maskesi. Maske daraltma
                # olcumu: 8 -> RED, 16 -> ARMED, 24/26/30 -> ARMED.
                # Gereken TEK bit 16 (INS denetimi); daha genis maske
                # gereksiz yere GPS/pusula denetimlerini de kapatirdi.
                #
                # Bu gevsetme YALNIZ SITL icindir; gercek ucusta dron
                # parametreleri otopilotun kendi eepromundan gelir ve bu
                # dosya hic kullanilmaz.
                f.write("ARMING_SKIPCHK 16\n")
                # ------------------------------------------------------
                # v2.4.239: SITL DATAFLASH KAYDI KAPALI
                # ------------------------------------------------------
                # Olcum (2026-09-17, GRCON sunucusu): sanal dron 26'nin
                # calisma dizininde logs/00000010.BIN 43 GB'a ulasti;
                # disk (138 GB) doldu, PostgreSQL "No space left on
                # device" PANIC ile kurtarma dongusune girdi. SITL'in
                # .BIN uretmesi urun icin degersizdir (analiz icin GCS'in
                # kendi telemetri kaydi var); backend tipi 0 = kayit yok.
                # LOG_DISARMED 0 ayrica motor kapaliyken yazimi keser
                # (varsayilan zaten 0, kalici eeprom'a karsi sabitlenir).
                f.write("LOG_BACKEND_TYPE 0\n")
                f.write("LOG_DISARMED 0\n")
        except OSError as e:
            return None, f"SITL varsayilan parametre dosyasi yazilamadi: {e}"
        # v2.4.239: onceki calistirmalardan kalan dataflash kayitlari
        # (logs/*.BIN) baslangicta silinir; eski surumlerde uretilmis
        # dosyalar aksi halde diskte sonsuza dek kalir.
        try:
            _logs = os.path.join(dizin, "logs")
            if os.path.isdir(_logs):
                for _ad in os.listdir(_logs):
                    if _ad.upper().endswith(".BIN"):
                        try:
                            os.remove(os.path.join(_logs, _ad))
                        except OSError:
                            pass
        except OSError:
            pass

        yuk = float(irtifa if irtifa is not None else 100.0)
        komut = [
            yol,
            "--model", model,
            "--home", f"{float(lat):.7f},{float(lon):.7f},{yuk:.1f},0",
            # Tuzak C: --base-port, -I'dan ONCE
            "--base-port", str(port),
            "--defaults", parm,
        ]
        # v2.4.40: sysid ARTIK ZORUNLU. Onceden `if sysid:` idi ve cagirici
        # tek dron durumunda None gecirdigi icin SITL kendi varsayilanini
        # (MAV_SYSID=1) kullaniyordu -> iki sanal dron ayni sysid ile yayin
        # yapip birbirini eziyordu. Argumanin gercekten etkili oldugu ham
        # MAVLink baytlari okunarak olculdu (NOT_SITL_SYSID_2440.md).
        komut += ["--sysid", str(int(sysid))]

        try:
            log = open(os.path.join(dizin, "sitl.log"), "w", encoding="utf-8")
        except OSError:
            log = subprocess.DEVNULL

        try:
            kw = {"cwd": dizin, "stdout": log, "stderr": subprocess.STDOUT,
                  "stdin": subprocess.DEVNULL}
            if _windows_mu():
                # Konsol penceresi acilmasin
                kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
            else:
                kw["start_new_session"] = True
            p = subprocess.Popen(komut, **kw)
        except PermissionError as e:
            # v2.4.46: Buraya dusmek artik beklenmez (izin_onar yukarida
            # calisti) ama savunma katmani olarak duruyor: dosya sistemi
            # noexec ise chmod basarili olur, Popen yine reddedilir.
            return None, (
                "SITL baslatilamadi - calistirma izni reddedildi: %s. "
                "Izin onarimi denendi ancak yetmedi. Bu genellikle SITL "
                "klasorunun 'noexec' ile baglanmis bir bolumde (USB "
                "bellek, ag surucusu, bazi kurulumda /tmp) durdugunu "
                "gosterir. Klasoru yerel diske tasiyin ya da elle "
                "'chmod +x %s' kosturun. Ayrinti: %s"
                % (yol, yol, e))
        except OSError as e:
            # v2.4.46: ENOEXEC (Errno 8) buraya artik dusmemeli
            # (bicim_denetle yukarida calisti) ama savunma katmani olarak
            # duruyor ve ciplak errno yerine nedeni yaziyor.
            if getattr(e, "errno", None) == 8:
                _b = ikili_bicimi(yol)
                return None, (
                    "SITL baslatilamadi - dosya bu makinede "
                    "calistirilabilir bir ikili degil: %s (bulunan bicim: "
                    "%s, mimari: %s; bu makine: %s). 'goktungu-sitl' "
                    "arsivini yeniden acin. Ayrinti: %s"
                    % (yol, _b.get("bicim"),
                       _b.get("makine_ad") or "bilinmiyor",
                       platform.machine(), e))
            return None, f"SITL baslatilamadi: {e}"

        # Erken cokme yakalama: --defaults hatasi ya da port cakismasi
        # saniyeler icinde olur (olculdu). Sessizce "basladi" demek yerine
        # burada yakalayip nedeni logdan okuyoruz.
        time.sleep(2.0)
        if p.poll() is not None:
            # v2.4.45: ciplak cikis kodu yerine anlasilir tanilama.
            # Kullanicidan gelen "cikis kodu 3221225781" tek basina hicbir
            # sey anlatmiyordu; log da bos kaldigi icin cikmaz sokak.
            try:
                log.close()
            except Exception:
                pass
            log_yolu = os.path.join(dizin, "sitl.log")
            son = ""
            try:
                with open(log_yolu, "r", encoding="utf-8",
                          errors="replace") as lf:
                    satirlar = [s.strip() for s in lf.readlines() if s.strip()]
                son = " | ".join(satirlar[-3:])
            except OSError:
                son = ""
            aciklama = cikis_kodu_acikla(p.returncode)
            parcalar = ["SITL hemen sonlandi (cikis kodu %s)."
                        % p.returncode]
            if aciklama:
                parcalar.append(aciklama)
            if son:
                parcalar.append("Log: " + son)
            else:
                parcalar.append(
                    "Log bos - surec baslamadan once yukleyici tarafindan "
                    "durduruldu.")
                eksik_z2, _ = dll_denetle(yol)
                if eksik_z2:
                    parcalar.append("Eksik DLL: " + ", ".join(eksik_z2))
            parcalar.append("Ayrinti: " + log_yolu)
            return None, " ".join(parcalar)

        with self._kilit:
            self._surecler[bid] = p
            # sysid ve konum bilgi sozlugunde tutulur: adet>1 durumunda
            # hangi ornegin hangi arac oldugunu ayirt etmenin baska yolu
            # yok (surecler ayni ikiliyi calistirir).
            self._bilgi[bid] = {"port": port, "tip": tip, "dizin": dizin,
                                "pid": p.pid, "ikili": yol,
                                "sysid": int(sysid) if sysid else None,
                                "lat": float(lat), "lon": float(lon)}
        self.konsol("SITL",
                    f"Sanal dron basladi: {tip} tcp:127.0.0.1:{port} "
                    f"(pid {p.pid})", "basari")
        return port, None

    # ------------------------------------------------------------------
    def durdur(self, bid):
        """Kayda ait TUM SITL sureclerini durdurur.

        Adet > 1 ise bir kayit birden fazla surec dogurur; yalniz anasini
        oldurmek digerlerini zombi birakir ve port bloklari bir daha
        kullanilamaz (olculdu: SITL blok dolu oldugunda cikis kodu 1).
        """
        bid = int(bid)
        idler = self.alt_kimlikler(bid)
        sonuc = False
        for k in idler:
            if self._tek_durdur(k):
                sonuc = True
        return sonuc

    def _tek_durdur(self, bid):
        """Tek bir SITL surecini durdurur. Zombi surec portu tutmaya devam eder."""
        bid = int(bid)
        with self._kilit:
            p = self._surecler.pop(bid, None)
            self._bilgi.pop(bid, None)
        if not p:
            return False
        if p.poll() is None:
            try:
                p.terminate()
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait(timeout=5)
            except Exception:
                pass
        self.konsol("SITL", f"Sanal dron durduruldu: id={bid}")
        return True

    def tumunu_durdur(self):
        with self._kilit:
            idler = list(self._surecler.keys())
        for bid in idler:
            try:
                self.durdur(bid)
            except Exception:
                pass

    # ------------------------------------------------------------------
    def artiklari_temizle(self):
        """Onceki oturumdan kalmis SITL sureclerini oldurur.

        Neden gerekli: sunucu cokerse ya da kullanici sureci sonlandirmadan
        kapatirsa SITL yasamaya devam eder ve port BLOGUNU tutar. Yeni
        oturumda ayni kayit baslatilmak istendiginde "Address already in
        use" ile hemen coker; kullanici icin sebebi anlasilmaz bir hata
        olur. Bu yuzden acilista temizlenir.

        Yalnizca BIZIM calisma kokumuz (`veri/sitl/`) altinda calisan
        surecler oldurulur; kullanicinin elle baslattigi ya da Mission
        Planner'in kendi SITL'i etkilenmez.
        """
        if not os.path.isdir(CALISMA_KOKU):
            return 0
        sayi = 0
        if _windows_mu():
            # Windows'ta komut satirini guvenilir okumak WMI gerektirir;
            # bunun yerine ikili adina gore sonlandirmak fazla genis olur
            # (Mission Planner SITL'ini de oldurebilir). Bu yuzden Windows'ta
            # temizlik YAPILMAZ; port cakismasi olursa blok kaydirma
            # (bos_taban_port) devreye girer ve baslatma yine calisir.
            return 0
        try:
            for pid_dizin in os.listdir("/proc"):
                if not pid_dizin.isdigit():
                    continue
                try:
                    with open(f"/proc/{pid_dizin}/cmdline", "rb") as f:
                        cmd = f.read().decode("utf-8", "ignore")
                except OSError:
                    continue
                if CALISMA_KOKU not in cmd:
                    continue
                if "arducopter" not in cmd and "arduplane" not in cmd:
                    continue
                try:
                    os.kill(int(pid_dizin), 15)
                    sayi += 1
                except OSError:
                    pass
        except OSError:
            return sayi
        if sayi:
            self.konsol("SITL",
                        f"Onceki oturumdan {sayi} artik surec temizlendi",
                        "uyari")
        return sayi


# ----------------------------------------------------------------------
# Hazirlik denetimi (v2.4.45)
# ----------------------------------------------------------------------
def hazir_mi():
    """SITL'in calisabilir durumda olup olmadigini olcer.

    Donus: (hazir, eksikler, ayrinti). Acilista cagrilir; kullanici
    sanal dron olusturmaya calismadan ONCE eksigi ogrensin diye.

    Kullanici karari (v2.4.45): "gerekli tum dosyalari sisteme bir kere
    indir, sunucuyu baslatmadan once SITL dosyalari zaten sistemde
    olsun". Yani normal akista bu islev daima True donmelidir; False
    donmesi kurulumun eksik oldugunu gosterir.
    """
    eksikler = []
    for ikili in ("arducopter", "arduplane"):
        bulundu = any(os.path.isfile(a) for a in ikili_adaylari(ikili))
        if not bulundu:
            eksikler.append(
                "ArduCopter.elf" if (ikili == "arducopter" and _windows_mu())
                else ("ArduPlane.elf" if _windows_mu() else ikili))
    if _windows_mu():
        yol, _m, _h = ikili_bul("multirotor")
        if yol:
            eksik_z, _e = dll_denetle(yol)
            eksikler.extend(eksik_z)
    if eksikler:
        return False, eksikler, (
            "SITL kurulumu eksik: %s. Beklenen klasor: %s"
            % (", ".join(eksikler), SITL_KLASORU))

    # v2.4.46: DOSYA VARLIGI YETMEZ - CALISTIRILABILIR OLMALI.
    # v2.4.45'te bu islev yalnizca `os.path.isfile` bakiyordu ve acilista
    # "SITL hazir" yaziyordu; kullanici sanal dron eklemeye calistiginda
    # ise `[Errno 13] Permission denied` aliyordu. Yani hazirlik denetimi
    # kullaniciyi YANLIS bilgilendiriyordu. Onarim burada yapilir ki
    # kusur sanal dron denemesine kadar beklemeden acilista cozulsun.
    onarilan, basarisiz = izin_onar_klasor()
    if basarisiz:
        return False, basarisiz, (
            "SITL ikililerine calistirma izni verilemedi: %s. "
            "Klasor: %s. Elle su komutu kosturun:  chmod +x '%s'/*"
            % (", ".join(basarisiz), SITL_KLASORU,
               SITL_KLASORU.rstrip(os.sep)))

    # v2.4.46: BICIM/MIMARI DENETIMI ACILISTA.
    # v2.4.45'te bu islev dosya varligina bakiyordu ve "SITL hazir"
    # diyordu; kullanici sanal dron eklemeye calistiginda `Errno 8`
    # aliyordu. Yani acilis raporu yine YANLIS bilgilendiriyordu. Bu
    # denetim ayni kusurun ikinci bicimini de acilista yakalar.
    #
    # v2.4.47: Adaylarin TAMAMI denenir. Onceden yalnizca ILK var olan
    # dosya olculuyordu; aarch64 makinede aday sirasi
    # [arducopter_aarch64, arducopter] oldugundan, aarch64 dosyasi yoksa
    # x86-64 dosyasi olculup acilista hata veriliyordu - oysa asil sorun
    # "mimariye ozgu dosya eksik"tir ve cozumu farklidir. Ayrica hicbir
    # aday uymuyorsa ileti artik hangi dosyanin BEKLENDIGINI soyler.
    for ikili in ("arducopter", "arduplane"):
        varolan = [a for a in ikili_adaylari(ikili) if os.path.isfile(a)]
        if not varolan:
            continue
        uyan = None
        ilk_neden = None
        for a in varolan:
            uygun, neden = bicim_denetle(a)
            if uygun:
                uyan = a
                break
            if ilk_neden is None:
                ilk_neden = (a, neden)
        if uyan is None and ilk_neden:
            a, neden = ilk_neden
            _snk = _mimari_sonek()
            ek_ipucu = ""
            if _snk:
                ek_ipucu = (" Bu makine icin beklenen dosya: %s. "
                            "'goktungu-sitl' arsivini kurulum klasorune "
                            "acin." % (ikili + _snk))
            return False, [os.path.basename(a)], neden + ek_ipucu

    ek = ""
    if onarilan:
        ek = " (%d ikilide calistirma izni onarildi)" % onarilan
    _snk = _mimari_sonek()
    if _snk:
        ek += " [mimari: %s, ikili soneki: %s]" % (
            platform.machine() or "?", _snk)
    return True, [], "SITL hazir: " + SITL_KLASORU + ek


# ----------------------------------------------------------------------
# Indirme yardimcisi
# ----------------------------------------------------------------------
# v2.4.45: Normal kurulumda buna GEREK YOKTUR - sitl/ klasoru tam pakete
# gomulur. Bu islev yalnizca iki durumda kullanilir:
#   * kullanici guncelleme paketiyle geldi ve ayri SITL arsivini acmadi
#   * ikili guncellemek isteniyor
# Windows'ta ZORUNLU DLL'lerden biri inemezse artik sessiz uyari degil
# HATA doner: yarim indirme 0xC0000135'e yol acar ve kullanici sebebini
# anlamaz (v2.4.44'te tam bu oldu).
def indir(tip, konsol=None, zaman_asimi=300, ilerleme=None):
    """SITL ikilisini (ve Windows'ta gerekli DLL'leri) indirir."""
    ikili, _model = TIP_ESLEME.get(
        str(tip or "").lower(), TIP_ESLEME["multirotor"])
    # v2.4.46: MIMARIYE DUYARLI SECIM. Onceden her Linux makinede
    # x86-64 ikilisi iniyordu; ARM bir makinede bu dosya indirilir,
    # "Hazir" yazilir ve calistirma aninda `Errno 8` verirdi.
    #
    # v2.4.47: aarch64 ayri ele alinir. ArduPilot aarch64 SITL
    # YAYINLAMADIGI icin (olculdu: HTTP 404) indirilecek bir adres YOK.
    # Bu mimaride tek gecerli kaynak pakete gomulu `*_aarch64` dosyasidir.
    if _windows_mu():
        isletim = "windows"
    else:
        _mak = (platform.machine() or "").lower()
        if _mak in ("aarch64", "arm64"):
            gomulu = os.path.join(SITL_KLASORU, ikili + "_aarch64")
            if os.path.isfile(gomulu):
                uygun, neden = bicim_denetle(gomulu)
                if uygun:
                    if not _windows_mu():
                        try:
                            os.chmod(gomulu, IKILI_IZIN)
                        except OSError:
                            pass
                    return True, ("Mimariye uygun SITL ikilisi zaten "
                                  "pakete gomulu: %s" % gomulu)
                return False, ("Gomulu aarch64 SITL ikilisi kullanilamaz "
                               "durumda: %s. 'goktungu-sitl' arsivini "
                               "yeniden acin." % neden)
            return False, (
                "Bu makine aarch64 (64-bit ARM). ArduPilot dagitiminda "
                "aarch64 SITL ikilisi YOKTUR, bu yuzden indirilemez. "
                "Gereken dosya pakete gomuludur: %s. 'goktungu-sitl' "
                "arsivini kurulum klasorune acin."
                % (ikili + "_aarch64"))
        isletim = ("linux_arm"
                   if _mak in ("armv7l", "armv6l")
                   else "linux")
    url = (INDIRME.get(isletim) or {}).get(ikili)
    if not url:
        return False, (
            "Bu makine icin hazir SITL ikilisi yok (isletim=%s, "
            "mimari=%s). ArduPilot kaynagindan derlemeniz gerekir."
            % (isletim, platform.machine()))
    try:
        os.makedirs(SITL_KLASORU, exist_ok=True)
    except OSError as e:
        return False, f"SITL klasoru olusturulamadi: {e}"

    import urllib.request
    hedef = ikili_adaylari(ikili)[0]

    def _cek(u, h, bildir=False):
        # FAZ18-ILERLEME: cagirici `ilerleme(inen, toplam)` verirse her
        # blok sonrasi cagrilir. Olculdu (2026-08-18): ArduPilot firmware
        # sunucusu `Content-Length` DONDURUR (arducopter 7230968,
        # arduplane 7181296), bu yuzden kesin yuzde hesaplanabilir;
        # belirsiz cubuga gerek yoktur. Baslik yine de yoksa `toplam` 0
        # gecer ve cagirici belirsiz gosterge cizer.
        #
        # KISMA BURADA YAPILMAZ. Bu katman WS'i bilmez; kisma sunucu
        # katmaninin isidir (katman ayrimi). Burada kisma yapilsa iki
        # farkli cagirici iki farkli kisma isterse cozum kalmaz.
        with urllib.request.urlopen(u, timeout=zaman_asimi) as r, \
                open(h, "wb") as f:
            toplam = 0
            if bildir and ilerleme:
                try:
                    toplam = int(r.headers.get("Content-Length") or 0)
                except (TypeError, ValueError):
                    toplam = 0
            inen = 0
            while True:
                blok = r.read(262144)
                if not blok:
                    break
                f.write(blok)
                inen += len(blok)
                if bildir and ilerleme:
                    try:
                        ilerleme(inen, toplam)
                    except BaseException:
                        # Geri cagirma kusuru INDIRMEYI DUSURMEZ.
                        # Ilerleme gostergesi suslemedir; indirme asil
                        # istir. Ters kurgu (gosterge kusuru indirmeyi
                        # iptal etsin) kullaniciyi cozumsuz birakir.
                        pass

    try:
        if konsol:
            konsol("SITL", f"Indiriliyor: {url}")
        _cek(url, hedef, bildir=True)
        # v2.4.46: Inen dosyayi KABUL ETMEDEN once dogrula. Yarim inmis
        # ya da hata sayfasi olarak inmis dosya "Hazir" yazilip calisma
        # aninda `Errno 8` verirdi.
        _uygun, _neden = bicim_denetle(hedef)
        if not _uygun:
            try:
                os.remove(hedef)
            except OSError:
                pass
            return False, ("Inen SITL ikilisi kullanilabilir degil: %s"
                           % _neden)
        if not _windows_mu():
            os.chmod(hedef, IKILI_IZIN)
        else:
            # Cygwin DLL'leri olmadan Windows ikilisi calismaz.
            # v2.4.45: ZORUNLU olanlar inemezse islem BASARISIZ sayilir.
            # Onceden yalnizca uyari yaziliyordu; kullanici "indirildi"
            # sanip sanal dron baslatiyor ve 0xC0000135 aliyordu.
            basarisiz_z = []
            for dll in WINDOWS_DLL:
                dh = os.path.join(SITL_KLASORU, dll)
                if os.path.isfile(dh) and os.path.getsize(dh) > 0:
                    continue
                try:
                    _cek(DLL_TABAN + dll, dh)
                except Exception as e:
                    # Yarim/bos dosya birakmak, sonraki denemede "var"
                    # gorunup denetimi yanlis gecirir.
                    try:
                        if os.path.isfile(dh):
                            os.remove(dh)
                    except OSError:
                        pass
                    if dll in WINDOWS_DLL_ZORUNLU:
                        basarisiz_z.append(dll)
                    if konsol:
                        konsol("SITL", f"DLL indirilemedi ({dll}): {e}",
                               "hata" if dll in WINDOWS_DLL_ZORUNLU
                               else "uyari")
            if basarisiz_z:
                return False, (
                    "Zorunlu Cygwin kutuphaneleri indirilemedi (%s). "
                    "Bunlar olmadan SITL 0xC0000135 hatasiyla aninda "
                    "kapanir. Internet erisimini denetleyin ya da tam "
                    "paketi kurun." % ", ".join(basarisiz_z))
    except Exception as e:
        return False, f"Indirme basarisiz: {e}"
    if konsol:
        konsol("SITL", f"Hazir: {hedef}", "basari")
    return True, None
