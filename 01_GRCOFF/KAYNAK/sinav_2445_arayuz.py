#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GOKTUNGU v2.4.45 butunluk denetimi.

Kurulum sonrasi yamanin eksiksiz uygulandigini dogrular. Tarayici
gerektirmez; kaynak dosyalarin gercek icerigini olcer.

Kapsam:
  1. Surum etiketleri
  2. SITL duzeltmesi (gomulu dosyalar + DLL on denetimi)
  3. Tek SANAL DRON grubu
  4. GCCDUAL (Goktungu menusu + Program Ayarlari anahtari)
  5. AI bilgisayarlari SSH + canli konsol
  6. Dron panelinde haberlesme konsolu
  7. Ucus duvarinda tam ekran
  8. i18n dengesi
  9. Soz dizimi

Kullanim:  python3 sinav_2445_arayuz.py   (kurulum kokunde)
Cikis kodu 0 = tum denetimler gecti, 1 = eksik var.
"""
import os
import re
import sys


def _kok_bul():
    """Kurulum kokunu bulur (main.py + js/ ikilisi olcuttur)."""
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


def _surum_demet(m):
    return tuple(int(x) for x in m.split("."))


def main():
    print("=" * 70)
    print("GOKTUNGU v2.4.45 BUTUNLUK DENETIMI")
    print("KOK: %s" % KOK)
    print("=" * 70)

    # ---------------------------------------------------------------
    print("\n--- 1. Surum etiketleri ---")
    surum = oku("js/surum.js") or ""
    m = re.search(r'GCS_SURUM\s*=\s*"([0-9.]+)"', surum)
    sv = m.group(1) if m else "0"
    denet("js/surum.js surumu >= 2.4.45",
          bool(m) and _surum_demet(sv) >= (2, 4, 45), sv)
    denet("surum gecmisinde 2.4.45 kaydi", 's: "2.4.45"' in surum)
    denet("surum gecmisi 2.4.45 maddeleri >= 10",
          surum.count('s: "2.4.45"') == 1
          and len(re.findall(r'"[^"]{40,}"',
                             surum.split('s: "2.4.45"')[1]
                             .split('s: "2.4.44"')[0])) >= 10)
    init = oku("goktungu/__init__.py") or ""
    mi = re.search(r'_SON_BILINEN\s*=\s*"([0-9.]+)"', init)
    iv = mi.group(1) if mi else "0"
    denet("goktungu/__init__.py surumu >= 2.4.45",
          bool(mi) and _surum_demet(iv) >= (2, 4, 45), iv)
    for dosya in ("index.html", "flight.html", "video.html"):
        s = oku(dosya) or ""
        etk = sorted(set(re.findall(r"\?v=v(24\d\d)", s)))
        denet("%s onbellek etiketi tek ve >= v2445" % dosya,
              len(etk) == 1 and int(etk[0]) >= 2445,
              "etiket: " + ", ".join("v" + e for e in etk))

    # ---------------------------------------------------------------
    print("\n--- 2. SITL duzeltmesi (Windows 0xC0000135) ---")
    sitl = oku("goktungu/sitl.py") or ""
    denet("WINDOWS_DLL_ZORUNLU listesi var", "WINDOWS_DLL_ZORUNLU" in sitl)
    for dll in ("cygwin1.dll", "cyggcc_s-seh-1.dll", "cygstdc++-6.dll",
                "cygiconv-2.dll", "cygintl-8.dll"):
        denet("  zorunlu DLL listede: %s" % dll, dll in sitl)
    denet("WINDOWS_CIKIS_KODU sozlugu var", "WINDOWS_CIKIS_KODU" in sitl)
    denet("0xC0000135 (3221225781) tanimli",
          "3221225781" in sitl or "0xC0000135" in sitl.upper())
    denet("dll_denetle() islevi var", "def dll_denetle" in sitl)
    denet("cikis_kodu_acikla() islevi var", "def cikis_kodu_acikla" in sitl)
    denet("hazir_mi() islevi var", "def hazir_mi" in sitl)
    denet("baslat() icinde ON DLL denetimi",
          bool(re.search(r"def baslat\(.*?dll_denetle", sitl, re.S)))
    denet("indir() zorunlu DLL inemezse hata dondurur",
          "zorunlu" in sitl.lower() and "def indir" in sitl)

    # Gomulu dosyalar (sitl.py SITL_KLASORU = <kok>/sitl, DUZ yapi)
    sitl_dizin = os.path.join(KOK, "sitl")

    def _s(ad):
        return os.path.join(sitl_dizin, ad)

    denet("sitl/ klasoru mevcut", os.path.isdir(sitl_dizin))
    denet("sitl/ArduCopter.elf gomulu (Windows)", os.path.exists(_s("ArduCopter.elf")),
          "%.1f MB" % (os.path.getsize(_s("ArduCopter.elf")) / 1048576.0)
          if os.path.exists(_s("ArduCopter.elf")) else "yok")
    denet("sitl/ArduPlane.elf gomulu (Windows)", os.path.exists(_s("ArduPlane.elf")))
    eksik_dll = [d for d in ("cygwin1.dll", "cyggcc_s-seh-1.dll",
                             "cygstdc++-6.dll", "cygiconv-2.dll",
                             "cygintl-8.dll")
                 if not os.path.exists(_s(d))]
    denet("zorunlu DLL'ler gomulu", not eksik_dll,
          ("eksik: " + ", ".join(eksik_dll)) if eksik_dll else "5/5")
    tum_dll = [f for f in os.listdir(sitl_dizin)
               if f.lower().endswith(".dll")] if os.path.isdir(sitl_dizin) else []
    denet("tum Cygwin DLL'leri gomulu (>=10)", len(tum_dll) >= 10,
          "%d DLL" % len(tum_dll))
    denet("sitl/arducopter gomulu (Linux)", os.path.exists(_s("arducopter")))
    denet("sitl/arduplane gomulu (Linux)", os.path.exists(_s("arduplane")))
    # v2.4.62: OLCUM GUNCELLENDI. Bu satir v2.4.51 yapisini bekliyordu
    # (`os.path.join(PROJE_KOKU, "sitl")`). v2.4.52'de SITL ikilileri
    # veri kokune tasindi ve yol artik `_veri_alt_yolu("sitl")` ile
    # uretiliyor; bu, eski konumda dosya varsa ESKI konumu donduren
    # gecis kuralini da uygular. Olcum eski metni aradigi icin dogru
    # kodda KALIYORDU — yani sinav gercek bir kusuru degil, kendi
    # eskimisligini bildiriyordu.
    denet("SITL_KLASORU veri kokunden uretiliyor (v2.4.52+)",
          'SITL_KLASORU = _veri_alt_yolu("sitl")' in sitl)
    denet("SITL calisma dizini ikiliden AYRI (sitl_calisma)",
          'CALISMA_KOKU = _veri_alt_yolu("sitl_calisma")' in sitl)
    mainpy = oku("main.py") or ""
    denet("main.py acilista hazir_mi() denetimi", "hazir_mi()" in mainpy)

    # ---------------------------------------------------------------
    print("\n--- 3. Tek SANAL DRON grubu ---")
    seri = oku("js/seri.js") or ""
    denet("BAG_SANAL sabiti", 'BAG_SANAL' in seri and '__sanal__' in seri)
    denet("bagSanalUstGrupCiz() islevi", "function bagSanalUstGrupCiz" in seri
          or "bagSanalUstGrupCiz =" in seri)
    denet("bagSanalKayitBlogu() islevi", "bagSanalKayitBlogu" in seri)
    denet("bagListeCiz sanal kayitlari ayirir",
          bool(re.search(r'tur\s*===?\s*["\']sanal["\']', seri)))
    denet("ust grup toplam sayaci hesaplanir",
          'querySelectorAll(".dron-kart")' in seri
          or "querySelectorAll('.dron-kart')" in seri)
    css = oku("css/stil.css") or ""
    for sinif in (".bag-grup-sanal", ".bag-sanal-kayit", ".bag-sanal-govde"):
        denet("  css %s" % sinif, sinif in css)

    # ---------------------------------------------------------------
    print("\n--- 4. GCCDUAL (Yer Kontrol Istasyonu Dual) ---")
    idx = oku("index.html") or ""
    ist2js = oku("js/istasyon2.js") or ""
    ist2py = oku("goktungu/istasyon2.py") or ""
    prog = oku("js/program_ayar.js") or ""
    harita = oku("js/harita.js") or ""
    sunucu = oku("goktungu/sunucu.py") or ""

    denet("CIHAZ_KODU = GCCDUAL", 'CIHAZ_KODU = "GCCDUAL"' in ist2py)
    denet("mbIstasyon2 menu ogesi var", 'id="mbIstasyon2"' in idx)
    # Menu ogesi Dronlar'da DEGIL, Goktungu (uygulama) menusunde olmali
    dronlar_blok = ""
    mm = re.search(r'mbDronlarMenu.*?</div>', idx, re.S)
    if mm:
        dronlar_blok = mm.group(0)
    denet("menu ogesi Dronlar menusunde DEGIL",
          'id="mbIstasyon2"' not in dronlar_blok)
    denet("menu ogesi varsayilan gizli",
          bool(re.search(r'id="mbIstasyon2"[^>]*display\s*:\s*none', idx)))
    denet("istasyon2MenuGorunumGuncelle() var",
          "istasyon2MenuGorunumGuncelle" in ist2js)
    denet("istasyon2AyarSunucudan() var", "istasyon2AyarSunucudan" in ist2js)
    denet("istasyon2ArayuzAcikMi() var", "istasyon2ArayuzAcikMi" in ist2js)
    denet("harita.js ayarlariUygula GCCDUAL dagitimi",
          "istasyon2AyarSunucudan" in harita)
    denet("Program Ayarlari GCCDUAL anahtari", "progIst2Anahtar" in prog)
    denet("Program Ayarlari seri port girisi", "progIst2Port" in prog)
    denet("sunucu.py istasyon2_arayuz ayari", "istasyon2_arayuz" in sunucu)
    denet("kapatilinca istasyon2.kes() cagrilir",
          bool(re.search(r"istasyon2_arayuz.*?kes\(\)", sunucu, re.S)))
    denet("arayuz_acik() denetimi backend'de", "def arayuz_acik" in ist2py)
    denet("otomatik_baslat kapali cihazda baglanmaz",
          bool(re.search(r"def otomatik_baslat.*?arayuz_acik", ist2py, re.S)))

    # ---------------------------------------------------------------
    print("\n--- 5. AI bilgisayarlari SSH + konsol ---")
    aissh = oku("goktungu/ai_ssh.py")
    denet("goktungu/ai_ssh.py mevcut", aissh is not None)
    aissh = aissh or ""
    denet("ssh_yolu() Windows OpenSSH yolunu arar",
          "OpenSSH" in aissh and "def ssh_yolu" in aissh)
    denet("pip bagimliligi YOK (paramiko ithal edilmiyor)",
          not re.search(r"^\s*(import|from)\s+paramiko", aissh, re.M))
    denet("SSHOturum halka tamponu", "TAMPON_SATIR" in aissh)
    denet("duyurular toplanir (WS bogulmaz)", "_duyuru_dongusu" in aissh)
    denet("cikis kodu 255 kimlik ipucu", "255" in aissh)
    denet("AISSHYonetici sinifi", "class AISSHYonetici" in aissh)
    aiy = oku("goktungu/ai_yonetici.py") or ""
    denet("listele() ssh_sifre gondermez",
          "ssh_sifre_var" in aiy and 'kayit.pop("ssh_sifre"' in aiy
          or "ssh_sifre_var" in aiy)
    denet("kaydet(ssh=None) alanlari korur", "ssh=None" in aiy)
    vt = oku("goktungu/veritabani.py") or ""
    for kol in ("ssh_kullanici", "ssh_port", "ssh_anahtar", "ssh_komut",
                "ssh_sifre"):
        denet("  veritabani kolonu: %s" % kol, kol in vt)
    denet("ai_sunucular goc girdisi", '"ai_sunucular"' in vt)
    for k in ("ai_ssh_baslat", "ai_ssh_durdur", "ai_ssh_gecmis"):
        denet("  WS komutu: %s" % k, k in sunucu)
    denet("main.py AISSHYonetici kurulumu", "AISSHYonetici" in mainpy)
    aijs = oku("js/ai_sunucular.js") or ""
    denet("arayuz play/stop dugmesi", "ai-btn-ssh" in aijs)
    denet("arayuz konsol dugmesi", "ai-btn-konsol" in aijs)
    denet("konsol satirin ALTINA eklenir", "afterend" in aijs)
    denet("bos sifre alani sifre_koru gonderir", "sifre_koru" in aijs)
    denet("SSH form alanlari (index.html)",
          all(x in idx for x in ("aisSshKullanici", "aisSshPort",
                                 "aisSshAnahtar", "aisSshKomut")))
    ws = oku("js/ws.js") or ""
    for k in ("ai_ssh_durum", "ai_ssh_satir", "ai_ssh_gecmis"):
        denet("  ws.js yonlendirme: %s" % k, k in ws)
    for sinif in (".ai-konsol", ".ai-btn-ssh", ".ai-btn-konsol"):
        denet("  css %s" % sinif, sinif in css)

    # ---------------------------------------------------------------
    print("\n--- 6. Dron panelinde haberlesme konsolu ---")
    dronpy = oku("goktungu/dron.py") or ""
    denet("KONSOL_LIMIT sabiti", "KONSOL_LIMIT" in dronpy)
    denet("dkonsol() islevi", "def dkonsol" in dronpy)
    denet("konsol_gecmis() islevi", "def konsol_gecmis" in dronpy)
    denet("konsol_temizle() islevi", "def konsol_temizle" in dronpy)
    denet("konsol_kancasi alani", "konsol_kancasi" in dronpy)
    dk_sayi = len(re.findall(r"self\.dkonsol\(", dronpy))
    denet("dkonsol cagrisi >= 15", dk_sayi >= 15, "%d cagri" % dk_sayi)
    denet("STATUSTEXT dron konsoluna gider",
          bool(re.search(r'dkonsol\([^)]*"STATUS"', dronpy)))
    denet("hata/uyari genel konsolda KALIR (toast koprusu)",
          bool(re.search(r'self\.konsol\([^)]*"hata"', dronpy))
          or bool(re.search(r'self\.konsol\([^)]*"uyari"', dronpy)))
    for k in ("dron_konsol_gecmis", "dron_konsol_temizle"):
        denet("  WS komutu: %s" % k, k in sunucu)
    denet("main.py konsol kancasi enjeksiyonu",
          "konsol_kancasi" in mainpy and "dron_konsol_satir" in mainpy)
    djs = oku("js/dronlar.js") or ""
    denet("dkKonsolBolumuKur() islevi", "dkKonsolBolumuKur" in djs)
    denet("dkKonsolAcKapa() islevi", "dkKonsolAcKapa" in djs)
    denet("dronKonsolSatir() islevi", "dronKonsolSatir" in djs)
    denet("dronKonsolGecmis() islevi", "dronKonsolGecmis" in djs)
    denet("gecmis YALNIZ ilk acilista istenir",
          "dkKonsolAcKapa" in djs and "gecmisIstendi" in djs)
    denet("DOM satir siniri", "DK_KONSOL_DOM_LIMIT" in djs)
    denet("tekrar rozeti (xN)", "tekrar" in djs)
    for k in ("dron_konsol_satir", "dron_konsol_gecmis"):
        denet("  ws.js yonlendirme: %s" % k, k in ws)
    for sinif in (".dk-konsol", ".dk-kons-"):
        denet("  css %s" % sinif, sinif in css)

    # ---------------------------------------------------------------
    print("\n--- 7. Ucus duvarinda tam ekran ---")
    fh = oku("flight.html") or ""
    fjs = oku("js/flight.js") or ""
    fcss = oku("css/flight.css") or ""
    denet("sayfa tam ekran dugmesi (#fwTamEkran)", 'id="fwTamEkran"' in fh)
    denet("panel tam ekran dugmesi (.fw-p-tam)", "fw-p-tam" in fjs)
    denet("panelTamEkranCevir() islevi", "panelTamEkranCevir" in fjs)
    denet("sayfaTamEkranCevir() islevi", "sayfaTamEkranCevir" in fjs)
    denet("fullscreenchange dinleyicisi", "fullscreenchange" in fjs)
    denet("F tusu kisayolu", bool(re.search(r'["\']f["\']', fjs, re.I)))
    denet("1-6 panel kisayollari",
          bool(re.search(r'k\s*>=\s*"1"\s*&&\s*k\s*<=\s*"6"', fjs))
          or "Digit" in fjs)
    denet("INPUT/SELECT odakli iken kisayol yok",
          "SELECT" in fjs and "INPUT" in fjs)
    denet("API reddedilirse sahte tam ekran (yedek kip)",
          "fw-sayfa-tam" in fjs and "fw-sayfa-tam" in fcss)
    denet("yerlesimUygula tam ekran panelini korur",
          bool(re.search(r"yerlesimUygula.*?tam", fjs, re.S)))
    denet("ucusDilTazele tam ekran ipuclarini yeniler",
          "tamEkranTazele" in fjs)
    for sinif in (".fw-tam-btn", ".fw-p-tam", ".fw-panel-tam"):
        denet("  css %s" % sinif, sinif in fcss)

    # ---------------------------------------------------------------
    print("\n--- 8. i18n dengesi ---")
    i18 = oku("js/i18n.js") or ""
    bloklar = {}
    for dil in ("TR", "EN"):
        m = re.search(r"^\s{2}%s:\s*\{(.*?)^\s{2}\}," % dil, i18,
                      re.S | re.M)
        bloklar[dil] = m.group(1) if m else ""
    say = {}
    for dil, blok in bloklar.items():
        # Cok satirli dize devamlari (ornek: "Konum: " + lat + ...) anahtar
        # DEGILDIR; satir bir tirnakla basliyorsa atlanir.
        anahtarlar = set()
        for satir in blok.split("\n"):
            if re.match(r'^\s*["\']\s*[^"\']*["\']\s*\+', satir):
                continue
            mk = re.match(r'^\s*(["\']?)([A-Za-z_][A-Za-z0-9_]*)\1\s*:', satir)
            if mk:
                anahtarlar.add(mk.group(2))
        say[dil] = anahtarlar
    denet("TR/EN anahtar sayisi esit",
          len(say["TR"]) == len(say["EN"]) and len(say["TR"]) > 1300,
          "TR=%d EN=%d" % (len(say["TR"]), len(say["EN"])))
    eksik_en = sorted(say["TR"] - say["EN"])[:8]
    eksik_tr = sorted(say["EN"] - say["TR"])[:8]
    denet("EN'de eksik anahtar yok", not eksik_en,
          ", ".join(eksik_en) if eksik_en else "0")
    denet("TR'de eksik anahtar yok", not eksik_tr,
          ", ".join(eksik_tr) if eksik_tr else "0")
    # v2.4.45'te eklenen anahtarlar
    for k in ("bagSanalGrup", "mbIstasyon2", "progAyarIst2",
              "aiSshBaslat", "dkKonsolBaslik", "ucusTamEkran"):
        denet("  yeni anahtar TR+EN: %s" % k,
              any(x.startswith(k) for x in say["TR"])
              and any(x.startswith(k) for x in say["EN"]))

    # ---------------------------------------------------------------
    print("\n--- 9. Soz dizimi ---")
    import py_compile
    for py in ("goktungu/sitl.py", "goktungu/istasyon2.py", "goktungu/sunucu.py",
               "goktungu/dron.py", "goktungu/ai_ssh.py", "goktungu/ai_yonetici.py",
               "goktungu/veritabani.py", "main.py"):
        yol = os.path.join(KOK, py)
        ok = False
        hata = ""
        if os.path.exists(yol):
            try:
                with open(yol, "r", encoding="utf-8") as f:
                    compile(f.read(), yol, "exec")
                ok = True
            except SyntaxError as e:
                hata = "satir %s: %s" % (e.lineno, e.msg)
        else:
            hata = "dosya yok"
        denet("  %s derlenebilir" % py, ok, hata)

    # ---------------------------------------------------------------
    print("=" * 70)
    print("SONUC: %d GECTI / %d KALDI" % (_gecti, len(_kaldi)))
    if _kaldi:
        print("\nKALAN DENETIMLER:")
        for k in _kaldi:
            print("  - %s" % k)
    print("=" * 70)
    return 1 if _kaldi else 0


if __name__ == "__main__":
    sys.exit(main())
