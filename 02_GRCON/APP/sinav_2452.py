#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GOKTUNGU v2.4.52 - BAGLANTI HAVUZU + KLASOR YAPISI SINAVI

Bu surumun iki degisikligi de SESSIZ kusur uretmeye elverisli:

1) BAGLANTI HAVUZU. Sizinti hicbir hata mesaji vermez. Program
   gunlerce sorunsuz calisir, yuvalar birikir ve sinir dolunca
   yalnizca GOKTUNGU degil ayni veritabanina baglanan HERKES disari
   itilir. Bu yuzden sinav "havuz kodu yazilmis mi" diye bakmaz;
   gercek PostgreSQL varsa is parcasi OLDURUR ve baglantinin
   gercekten geri dondugunu `pg_stat_activity` uzerinden olcer.

2) KLASOR YAPISI. Yol kusurlarinin cogu sessizdir: dosya bulunamaz,
   kod bir `except` icinde yedek degere duser ve kullanici yalnizca
   "bir sey calismiyor" gorur. Ornek: surum okumasi basarisiz olunca
   gomulu yedek surum gosterilir -- yanlis surum, sifir hata.

Sinav HER IKI YAPIDA da calisir (duz ve assets); yollar
`sinav_yol` modulu ile cozulur.

Kullanim: `python3 sinav_2452.py`  (kokten veya alt klasorden)
"""
from __future__ import annotations

import inspect
import os
import re
import sys
import threading
import time

_BU = os.path.dirname(os.path.abspath(__file__))
for _p in (_BU, os.path.dirname(_BU)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    import sinav_yol as SY
except ImportError:
    print("HATA: sinav_yol.py bulunamadi (sinav betigiyle ayni klasorde"
          " olmali).")
    raise SystemExit(2)

SY.ice_aktarma_yolu_kur()

_gecti = 0
_kaldi = 0
_kaldi_liste: list[str] = []
_atlandi = 0


def olc(ad, kosul, ayrinti=""):
    global _gecti, _kaldi
    if kosul:
        _gecti += 1
        print("  [OK]    %s" % ad)
    else:
        _kaldi += 1
        _kaldi_liste.append(ad + ((" - " + ayrinti) if ayrinti else ""))
        print("  [KALDI] %s%s" % (ad, (" - " + ayrinti) if ayrinti else ""))


def atla(ad, sebep):
    global _atlandi
    _atlandi += 1
    print("  [ATLA]  %s - %s" % (ad, sebep))


def main():
    print("=" * 72)
    print("GOKTUNGU v2.4.52 - BAGLANTI HAVUZU + KLASOR YAPISI SINAVI")
    print("=" * 72)
    print(SY.ozet())

    # ==================================================================
    print()
    print("[1] KLASOR YAPISI")
    # Kullanicinin istegi: kokte YALNIZ main.py + assets/ (+ uretilen
    # veri/). Yapi tasinmamissa bu bolum atlanir; sinav eski yapida da
    # anlamli kalmalidir.
    if not SY.YENI_YAPI:
        atla("Kok dizin sadelestirmesi", "duz yapi (henuz tasinmamis)")
        atla("assets/web ve assets/python ayrimi", "duz yapi")
    else:
        girdiler = set(os.listdir(SY.KOK))
        girdiler -= {"__pycache__", ".git", "veri", "assets", "main.py"}
        # Kurulum betikleri ve surum notlari ARSIV kokunde kalir; kullanici
        # onlari elle calistirip okur. Kurulu sistemde kalmazlar, bu yuzden
        # kok sadeligini bozmus saymiyoruz.
        #
        # `yedek_*` de MUAF: kurulum betigi her yamada guvenlik icin yedek
        # alir ve kurulumdan sonra SILMEZ (tek geri donus yolu). Onceki
        # halde sinav, yamayi kusursuz uygulamis bir kurulumda dahi bu
        # maddeden kaliyordu; kullanici bunu gercek bir kusur sanip
        # calisan kurulumu yedekten geri almaya yoneliyordu.
        # `*.log` / `*.md` kullanicinin kendi dosyalari olabilir; yapinin
        # dogrulugunu etkilemezler.
        kalanlar = {g for g in girdiler
                    if not re.match(r"^(kur_|paketle_|BENI_OKU|SURUM|GOKTUNGU_"
                                    r"|yedek_)", g)
                    and not g.endswith((".log", ".md"))}
        olc("Kok dizinde yalniz main.py + assets (+veri)",
            not kalanlar, "fazlalik: %s" % sorted(kalanlar)[:6])
        olc("assets/web/index.html var",
            os.path.isfile(SY.web("index.html")))
        olc("assets/python/goktungu paketi var",
            os.path.isdir(SY.py("goktungu")))
        olc("assets icinde yalniz web/python/belgeler",
            set(os.listdir(SY.kok("assets"))) <= {
                "web", "python", "belgeler", "__pycache__"},
            str(sorted(os.listdir(SY.kok("assets")))))
        # Kullanici verisi: pakete GIRMEMELI ama kaybolmamali da.
        olc("veri/ klasoru kokte",
            os.path.isdir(SY.kok("veri")))
        olc("Kullanici verisi assets altina KONMAMIS",
            not os.path.isdir(SY.kok("assets", "web", "harita_cache"))
            and not os.path.isdir(SY.kok("assets", "python", "veri")))

    # ==================================================================
    print()
    print("[2] SURUM DAMGALARI")
    # Surum uc yerde tutulur. Biri geride kalirsa tarayici ESKI JS'i
    # onbellekten yukler; duzeltme uygulanmis gorunur ama calismaz.
    ini = SY.py_oku("goktungu", "__init__.py")
    sj = SY.web_oku("js", "surum.js")
    ix = SY.web_oku("index.html")
    # NOT (Faz 11 duzeltmesi): bu sinav v2.4.52'de yazildi ve surum
    # numarasini sabit "2.4.52" olarak olcuyordu. Surum her yukseltmede
    # degistigi icin olcum kalici olarak kaliyordu ve GERCEK kusuru
    # (uc kaynagin BIRBIRIYLE tutarsiz olmasi) hic olculmuyordu.
    # Dogru olcum: uc kaynak ayni surumu bildirmeli, hangi surum
    # oldugu onemli degil.
    m_sj = re.search(r'GCS_SURUM\s*=\s*["\']([0-9.]+)["\']', sj)
    olc("js/surum.js GCS_SURUM okunabiliyor", m_sj is not None)
    _sur = m_sj.group(1) if m_sj else ""
    olc("goktungu/__init__.py yedek surum js ile ayni",
        bool(_sur) and ('"%s"' % _sur in ini or "'%s'" % _sur in ini),
        "js=%s" % _sur)
    olc("js/surum.js gecmis girdisi guncel surumu iceriyor",
        bool(_sur) and re.search(r's:\s*["\']%s["\']'
                                % re.escape(_sur), sj) is not None,
        "js=%s" % _sur)
    # Onbellek etiketi surumden uretilir: 2.4.64 -> v2464
    _et = "v" + _sur.replace(".", "") if _sur else ""
    olc("index.html onbellek etiketi guncel surumle uyusuyor",
        bool(_et) and ("?v=%s" % _et) in ix, "beklenen=?v=%s" % _et)
    # ESKI etiket kalmamis: guncel etiket disinda ?v=vNNNN olmamali
    _etler = set(re.findall(r'\?v=(v\d{4})', ix))
    olc("index.html'de ESKI onbellek etiketi kalmamis",
        _etler <= {_et}, "bulunan=%s beklenen=%s"
        % (sorted(_etler), _et))

    # ==================================================================
    print()
    print("[3] YOL COZUMLEME KATMANI (sabitler.py)")
    sab = SY.py_oku("goktungu", "sabitler.py")
    # NOT: WEB_KOKU/VERI_KOKU kosullu atanir (if/else icinde), bu
    # yuzden satir basi deseni ile aranmaz; adin gectigi olculur.
    olc("WEB_KOKU tanimli", re.search(r"\bWEB_KOKU\s*=", sab)
        is not None)
    olc("VERI_KOKU tanimli", re.search(r"\bVERI_KOKU\s*=", sab)
        is not None)
    olc("YAPI algilamasi var", "YAPI" in sab and "assets" in sab)
    # Iki ayri veri kurali: (a) kokteki dosyalar, (b) zaten veri/
    # altinda olanlar. Tek kural iki grubu birden karsilamaz.
    olc("_veri_yolu ve _veri_alt_yolu ayri tanimli",
        "_veri_yolu" in sab and "_veri_alt_yolu" in sab)
    olc("WEB_KOKU icin gecis guvenligi (index.html denetimi)",
        "index.html" in sab)

    try:
        from goktungu import sabitler as _sab
        olc("sabitler ice aktarilabiliyor", True)
        w_ok = os.path.isfile(os.path.join(_sab.WEB_KOKU, "index.html"))
        olc("WEB_KOKU gercekten index.html iceriyor", w_ok,
            _sab.WEB_KOKU)
        # Duz yapida VERI_KOKU == PROJE_KOKU olmali (geriye donuk uyum).
        if SY.YENI_YAPI:
            olc("VERI_KOKU = <kok>/veri",
                os.path.normpath(_sab.VERI_KOKU)
                == os.path.normpath(SY.kok("veri")), _sab.VERI_KOKU)
        else:
            olc("Duz yapida VERI_KOKU = PROJE_KOKU",
                os.path.normpath(_sab.VERI_KOKU)
                == os.path.normpath(_sab.PROJE_KOKU), _sab.VERI_KOKU)
    except Exception as e:
        olc("sabitler ice aktarilabiliyor", False, repr(e))

    # ------------------------------------------------------------------
    # Modul yollari: v2.4.51'de `veri/` altinda olan dosyalar ORADA
    # kalmali. Bu kural unutulursa mevcut kurulumda `pg.json`
    # bulunamaz, `yapilandirildi()` False doner ve SIHIRBAZ HER
    # ACILISTA yeniden cikar -- kullanici kurulumu bitirdigini sanir.
    try:
        from goktungu import pg as _pg
        from goktungu import veritabani as _vt
        from goktungu import sitl as _sitl
        from goktungu import gorev as _gorev
        beklenen_veri = (SY.kok("veri") if SY.YENI_YAPI else SY.KOK)
        pgy = _pg._pg_dosya_yolu()
        olc("pg.json 'veri/' altinda",
            os.path.normpath(os.path.dirname(pgy))
            == os.path.normpath(os.path.join(beklenen_veri, ""))
            or os.path.normpath(pgy).endswith(
                os.path.join("veri", "pg.json")), pgy)
        olc("gcs.db dogru kokte",
            os.path.normpath(os.path.dirname(_vt.DOSYA))
            == os.path.normpath(beklenen_veri), _vt.DOSYA)
        olc("SITL klasoru 'veri/sitl'",
            os.path.normpath(_sitl.SITL_KLASORU).endswith(
                os.path.join("veri", "sitl")), _sitl.SITL_KLASORU)
        olc("gorev_durum.json 'veri/' altinda",
            os.path.normpath(_gorev.GOREV_DURUM_DOSYA).endswith(
                os.path.join("veri", "gorev_durum.json")),
            _gorev.GOREV_DURUM_DOSYA)
    except Exception as e:
        olc("Modul yollari olculebiliyor", False, repr(e))

    # ==================================================================
    print()
    print("[4] TASIMA SONRASI YOL KUSURLARI (Faz 6'da yakalananlar)")
    mn = SY.kok_oku("main.py")
    olc("main.py ai_sunucu.py'yi assets/python altinda ariyor",
        "assets" in mn and "ai_sunucu.py" in mn
        and re.search(r'assets["\'],\s*["\']python["\'],\s*["\']'
                      r'ai_sunucu\.py', mn) is not None)
    ai = SY.py_oku("ai_sunucu.py")
    olc("ai_sunucu.py proje kokunu yukari dogru cozuyor",
        "_BU_DIZIN" in ai and "assets" in ai)
    olc("ai_sunucu.py modelleri veri/ altinda ariyor",
        "_ai_yolu" in ai)
    sk = SY.py_oku("betikler", "servis_kur.sh") or SY.kok_oku(
        "servis_kur.sh")
    kb = SY.py_oku("betikler", "kiosk_baslat.sh") or SY.kok_oku(
        "kiosk_baslat.sh")
    olc("servis_kur.sh main.py'yi yukari dogru ariyor",
        "v2.4.52: betik" in sk or 'for _i in 1 2 3 4' in sk)
    olc("kiosk_baslat.sh main.py'yi yukari dogru ariyor",
        "v2.4.52: betik" in kb or 'for _i in 1 2 3 4' in kb)
    # ai_isci.log dagitim dizinine yazilmamali (salt-okunur kurulum).
    olc("ai_isci.log veri/ altina yaziliyor",
        "VERI_KOKU" in mn and "ai_isci.log" in mn)

    # OLCULEN KUSUR: web koku assets/web'e inince, veri/ altindaki
    # kullanici dosyalari HTTP'den gorunmez olur. Arayuz bunlari
    # kok-goreli ister ve istenen yol VERITABANINDA kayitlidir.
    # Eksik esleme SESSIZCE 404 doner; konsola hicbir sey dusmez.
    su = SY.py_oku("goktungu", "sunucu.py")
    olc("sunucu.py translate_path esleme yapiyor",
        "translate_path" in su and "_VERI_ESLEME" in su)
    olc("esleme listesi /avatars/ iceriyor",
        '"/avatars/"' in su)
    olc("esleme listesi /ai_yuzler/ iceriyor",
        '"/ai_yuzler/"' in su,
        "ai_kutuphane.js yuz fotograflarini bu yoldan ister")
    olc("esleme dizin gezinmesini engelliyor",
        "basename" in su and '".."' in su)
    # Arayuzun gercekten istedigi kok-disi yollar eslemede var mi:
    # bu olcum, gelecekte yeni bir klasor eklenip eslemenin
    # unutulmasini yakalar.
    aik = SY.web_oku("js", "ai_kutuphane.js")
    if aik:
        # NOT (Faz 11 duzeltmesi): bu olcum duz `src = "/" + degisken`
        # desenini ariyordu. Kod o zamandan beri IYILESTI: artik
        # `goktunguYol(...)` yardimcisi kullaniliyor (yeni/duz yapi farkini
        # sogurur), duz birlestirme yalnizca yedek dal olarak kaldi.
        # Eski desen artik yok, bu yuzden olcum kalici olarak kaliyordu.
        # Dogru olcum: yuz dosyasi yolu HANGI yolla olsun kok-goreli
        # uretiliyor mu.
        istenen = set(re.findall(r'src\s*=\s*"/"\s*\+\s*(\w+)', aik))
        yardimci = "goktunguYol(" in aik
        yedek_dal = re.search(r'"/"\s*\+\s*kisi\.yuzler', aik) \
            is not None
        olc("ai_kutuphane.js yuz gorselini kok-goreli istiyor",
            bool(istenen) or (yardimci and yedek_dal),
            "goktunguYol=%s yedek_dal=%s duz=%s"
            % (yardimci, yedek_dal, sorted(istenen) or "yok"))

    # ==================================================================
    print()
    print("[5] BAGLANTI HAVUZU - KOD SOZLESMESI")
    pgs = SY.py_oku("goktungu", "pg.py")
    olc("pg.py okunabildi", bool(pgs))
    olc("Havuz sinir sabiti tanimli (HAVUZ_MAKS)",
        re.search(r"^HAVUZ_MAKS\s*=\s*\d+", pgs, re.M) is not None)
    olc("Is parcasi olumunde iade (weakref/finalize)",
        "weakref" in pgs)
    olc("Iade sirasinda rollback var",
        re.search(r"rollback", pgs) is not None)
    olc("Havuz dolunca ACIK hata (sessiz bekleme degil)",
        re.search(r"havuz dolu|Havuz dolu|HAVUZ_BEKLEME", pgs)
        is not None)
    olc("Baglanti kurulamazsa yuva geri veriliyor",
        re.search(r"yuva|_yuva", pgs) is not None)

    try:
        from goktungu import pg as _pg2
        # Gercek API adlari (v2.4.51'de olculdu; tahminle yazilmaz):
        #   yapilandirma_var()  -- 'yapilandirildi' DEGIL
        #   pg.VAR              -- 'surucu_var()' DEGIL (bayrak)
        for ad in ("baglanti", "yapilandir", "yapilandirma_var",
                   "yapilandirma_oku", "dene", "veritabani_olustur",
                   "baglanti_kapat", "tum_baglantilari_kapat"):
            olc("pg.%s() var" % ad, callable(getattr(_pg2, ad, None)))
        olc("pg.VAR bayragi (psycopg2 kurulu mu)",
            isinstance(getattr(_pg2, "VAR", None), bool))
        hd = getattr(_pg2, "havuz_durumu", None)
        olc("pg.havuz_durumu() var (izleme icin)", callable(hd))
        olc("pg.havuz_sinirini_ayarla() var",
            callable(getattr(_pg2, "havuz_sinirini_ayarla", None)))
        olc("HAVUZ_MAKS makul bir deger (2..100)",
            isinstance(getattr(_pg2, "HAVUZ_MAKS", None), int)
            and 2 <= _pg2.HAVUZ_MAKS <= 100,
            str(getattr(_pg2, "HAVUZ_MAKS", None)))
    except Exception as e:
        olc("pg ice aktarilabiliyor", False, repr(e))

    # ==================================================================
    print()
    print("[6] BAGLANTI HAVUZU - GERCEK OLCUM")
    # Kod denetimi yetmez: sizinti ancak gercek sunucuda gorulur.
    try:
        from goktungu import pg as P
    except Exception as e:
        atla("Gercek havuz olcumu", "pg ice aktarilamadi: %r" % e)
        P = None

    if P is not None and not getattr(P, "VAR", False):
        atla("Gercek havuz olcumu", "psycopg2 kurulu degil")
    elif P is not None and not (P.yapilandirma_var() or P.dosya_var()):
        atla("Gercek havuz olcumu", "PostgreSQL yapilandirilmamis")
    elif P is not None:
        if not P.yapilandirma_var():
            try:
                P.dosyadan_yukle()
            except Exception:
                pass
        # KRITIK: `yapilandirma_oku()` sifreyi '***' ile MASKELER
        # (gunluge yazmak icin dogru bir tasarim). O ciktiyla
        # baglanilamaz; olcum "sunucuya erisilemedi" deyip SESSIZCE
        # atlanir ve sinav yesil gorunur. Bu yuzden gercek deger
        # dogrudan pg modulunun ic yapilandirmasindan alinir.
        bilgi = dict(getattr(P, "_yapilandirma", None) or {})
        sonuc = None
        try:
            # dene() ayri parametreler alir; anahtarlar psycopg2 adlari.
            sonuc = P.dene(
                bilgi.get("host"), bilgi.get("port"),
                bilgi.get("dbname") or bilgi.get("veritabani"),
                bilgi.get("user"), bilgi.get("password"),
                bilgi.get("sslmode", "")) if bilgi else None
        except Exception as e:
            sonuc = {"tamam": False, "hata": repr(e)}
        # Maskeli sifreyle olculmedigini dogrula: aksi halde asagidaki
        # sizinti olcumu anlamsizdir.
        olc("Olcum GERCEK sifreyle yapiliyor (maskeli degil)",
            bilgi.get("password") != "***")
        if not sonuc or not sonuc.get("tamam"):
            atla("Gercek havuz olcumu",
                 "sunucuya erisilemedi: %s"
                 % (sonuc or {}).get("hata", "?"))
        else:
            _gercek_havuz_olcumu(P, bilgi)

    # ==================================================================
    print()
    print("[7] v2.4.51 GERILEMESI (PG sihirbazi bozulmamis)")
    olc("goktungu/pg.py duruyor", os.path.isfile(SY.py("goktungu", "pg.py")))
    olc("goktungu/goc.py duruyor", os.path.isfile(SY.py("goktungu", "goc.py")))
    olc("js/pg_sihirbaz.js duruyor",
        os.path.isfile(SY.web("js", "pg_sihirbaz.js")))
    sun = SY.py_oku("goktungu", "sunucu.py")
    for k in ("pg_durum", "pg_dene", "pg_olustur", "pg_kur", "pg_goc"):
        olc("sunucu.py WS komutu: %s" % k, '"%s"' % k in sun)
    olc("index.html pg_sihirbaz.js betigi",
        "pg_sihirbaz.js" in ix)
    i18 = SY.web_oku("js", "i18n.js")
    olc("i18n pgBaslik anahtari", "pgBaslik" in i18)

    # i18n dengesi: eksik dilde ANAHTAR ADI ekrana yazilir.
    tr = set(re.findall(r"^\s{4}(\w+):", i18, re.M))
    olc("i18n okunabildi (anahtar bulundu)", len(tr) > 100,
        "%d anahtar" % len(tr))

    # ==================================================================
    print()
    print("[8] PANEL KONUM KUSURU (transform cakismasi)")
    # KUSUR: bazi paneller CSS'te `left:50%; top:50%;
    # transform:translate(-50%,-50%)` ile ortalanir. Kayitli konum
    # uygulanirken yalniz left/top yazilir ve transform YERINDE KALIRSA
    # panel (left - genislik/2) noktasina kayar. 720px genislikte bu
    # 360px sola kayma demektir: kullanici paneli ekran DISINDA gorur,
    # baslik cubugu solda kaldigi icin tutup geri cekemez, kapatma
    # dugmesine de ulasamaz. Tarayici olcumu: -261px (kullanici -300
    # bildirdi). Ayni kusur `.kd-popup` (Kayitli Dronlar) icin 471px.
    br = SY.web_oku("js", "bolum_resize.js")
    olc("pencereKonumUygula transform'u sifirliyor",
        re.search(r"getComputedStyle\(el\)[\s\S]{0,400}?"
                  r"style\.transform\s*=\s*[\"']none[\"']", br)
        is not None)
    # Sol sinir: eski kod -200'e kadar tasmaya izin veriyordu; suruklenecek
    # tek yer baslik cubugu oldugu icin kurtarma yolu kapaniyordu.
    olc("Sol sinir -200 sabiti kaldirildi",
        "-200), maxL" not in br)
    olc("Sol sinir panelin tutulabilir kismini iceride tutuyor",
        re.search(r"TUTULABILIR\s*-\s*\(?el\.offsetWidth", br) is not None)
    # Ekran disi kayit kurtarma: kullanicinin localStorage'indaki bozuk
    # kayit duzeltmeden SONRA da paneli disarida acardi.
    olc("pencereKonumGecerliMi tanimli (ekran disi kurtarma)",
        "window.pencereKonumGecerliMi" in br)
    olc("pencereKonumSil tanimli", "window.pencereKonumSil" in br)

    # Kurtarma, konum kaydi tutan TUM panel ailelerine baglanmali.
    # Ortak gecit: dronlar.js icindeki dkMiniPopupBaslikKur().
    dr = SY.web_oku("js", "dronlar.js")
    olc("Ortak baslik yardimcisina kurtarma baglandi (dron/kam/yz/...)",
        "pencereKonumGecerliMi" in dr)
    i2 = SY.web_oku("js", "istasyon2.js")
    olc("GCCDUAL paneli kurtarmayi kullaniyor",
        "pencereKonumGecerliMi" in i2)
    olc("GCCDUAL bozuk kayitta ORTADA aciliyor",
        re.search(r"translate\(-50%,\s*-50%\)", i2) is not None)
    kd = SY.web_oku("js", "kayitli_dronlar.js")
    olc("Kayitli Dronlar kurtarmayi kullaniyor",
        "pencereKonumGecerliMi" in kd)
    # Ortak katman transform'u kosulsuz sifirladigi icin panelin kendi
    # kosullu blogu gereksizdi; kalirsa ileride celisir.
    olc("Kayitli Dronlar'daki kosullu transform blogu temizlendi",
        not re.search(r"if\s*\([^)]*k\.w[^)]*\)\s*\{?\s*"
                      r"[^\n]*style\.transform", kd))

    # ==================================================================
    print()
    print("[9] PANEL BOYUTLANDIRMA (resize)")
    # KUSUR: popup_tasima.js icindeki statikKur() yalniz index.html'de
    # TANIMLI panellere ve `.yuzen-panel` sinifina resize tutamaci
    # kuruyordu. Calisma aninda JS ile uretilen dk-mini-popup panelleri
    # (Program Ayarlari, GCCDUAL, dron/kamera panelleri, Kayitli Dronlar)
    # o listenin disinda kaliyor, sabit CSS genisliginde sikisip
    # kaliyordu. Kullanici bildirimi: "panel size duzgun degil,
    # resizable yap".
    pt = SY.web_oku("js", "popup_tasima.js")
    olc("popupBoyutlandirilabilirYap disa aciliyor",
        "window.popupBoyutlandirilabilirYap" in pt)
    olc("Boyut kaydi konumla ayni anahtarda tutuluyor (_boyutluKayit)",
        "_boyutluKayit" in pt)
    # Kanca ORTAK gecitte olmali: tek tek 18 cagriya dokunmak yeni kusur
    # riski demekti.
    olc("Ortak baslik yardimcisina boyutlandirma baglandi",
        "popupBoyutlandirilabilirYap" in dr)
    olc("Ortak gecit boyutlu kaydi geri yukluyor",
        re.search(r"pencereKonumUygula\(konumAnahtar,\s*pop,"
                  r"\s*!!pop\._boyutluKayit\)", dr) is not None)
    st = SY.web_oku("css", "stil.css")
    olc("popup-boyut-tutamac CSS sinifi tanimli",
        ".popup-boyut-tutamac" in st)
    # Sabit `width` inline boyutla ayni ozellikte carpisir: panel yeniden
    # acilinca CSS'e geri doner ve boyut kaydi gorunmez olur.
    olc("Program Ayarlari panelinde sabit genislik kalmadi",
        not re.search(r"\.prog-ayar-popup\s*\{[^}]*[^-]width\s*:\s*250px",
                      st))
    olc("Program Ayarlari panelinde min-width kullaniliyor",
        re.search(r"\.prog-ayar-popup\s*\{[^}]*min-width\s*:", st)
        is not None)
    # .dk-mini-popup `overflow:hidden` oldugu icin panel buyudugunde
    # govde kaydirilabilir olmali; aksi halde alt satirlar erisilemez.
    olc("Program Ayarlari govdesi dikey kaydirilabilir",
        re.search(r"\.prog-ayar-popup\s+\.prog-ayar-govde\s*\{"
                  r"[^}]*overflow-y\s*:\s*auto", st) is not None)

    # ==================================================================
    print()
    print("=" * 72)
    print("SONUC: %d gecti / %d kaldi / %d atlandi"
          % (_gecti, _kaldi, _atlandi))
    if _kaldi_liste:
        print()
        print("KALANLAR:")
        for k in _kaldi_liste:
            print("  - %s" % k)
    print("=" * 72)
    return 1 if _kaldi else 0


def _gercek_havuz_olcumu(P, bilgi):
    """Gercek PostgreSQL uzerinde sizinti ve sinir olcumu.

    OLCUM KIRLILIGI UYARISI
    -----------------------
    Ilk yazimda baglantilar yalnizca `application_name='goktungu'` ile
    sayiliyordu. Ancak ayni anda CALISAN GOKTUNGU SUNUCUSU da ayni adla
    baglanir; olcum onun baglantilarini da kendi is parcalarinin
    baglantisi sanip topluyordu. Sonuc: sinir 10 iken 14 olculdu ve
    saglam kod HATALI raporlandi. Ters yonu daha tehlikelidir: gercek
    bir sizinti, arka plandaki dalgalanma icinde gorunmez olabilirdi.

    Cozum: sayim `client_port` uzerinden BU SURECIN actigi baglantilara
    sinirlanir. Boylece ayni veritabanini kullanan baska bir GOKTUNGU
    ornegi acikken de olcum dogru kalir.
    """
    vt_adi = bilgi.get("dbname") or bilgi.get("veritabani")

    def _kendi_portlarimiz():
        """Bu surecin actigi TCP kaynak portlarini toplar."""
        portlar = set()
        try:
            import psutil  # varsa en kesin yontem
            for c in psutil.Process().net_connections(kind="tcp"):
                if c.raddr and int(c.raddr.port) == int(
                        bilgi.get("port") or 5432):
                    portlar.add(int(c.laddr.port))
            return portlar
        except Exception:
            pass
        # psutil yoksa /proc uzerinden oku (Linux).
        try:
            import glob
            inode_set = set()
            for fd in glob.glob("/proc/self/fd/*"):
                try:
                    hedef = os.readlink(fd)
                except OSError:
                    continue
                if hedef.startswith("socket:["):
                    inode_set.add(hedef[8:-1])
            for yol in ("/proc/net/tcp", "/proc/net/tcp6"):
                try:
                    with open(yol) as f:
                        next(f, None)
                        for satir in f:
                            a = satir.split()
                            if len(a) < 10 or a[9] not in inode_set:
                                continue
                            portlar.add(int(a[1].split(":")[1], 16))
                except OSError:
                    continue
        except Exception:
            pass
        return portlar

    def _acik_baglanti_sayisi():
        """BU SURECIN GOKTUNGU havuzu uzerinden actigi baglantilari sayar."""
        import psycopg2
        c = psycopg2.connect(
            host=bilgi.get("host"), port=int(bilgi.get("port") or 5432),
            dbname=vt_adi, user=bilgi.get("user"),
            password=bilgi.get("password"), connect_timeout=8,
            application_name="sinav2452")
        try:
            benim = _kendi_portlarimiz()
            with c.cursor() as im:
                im.execute(
                    "SELECT client_port FROM pg_stat_activity"
                    " WHERE datname=%s AND application_name=%s",
                    (vt_adi, "goktungu"))
                satirlar = [r[0] for r in im.fetchall()]
            if benim:
                return sum(1 for p in satirlar if p in benim)
            # Kaynak portlar okunamadiysa toplam sayiya duser; bu
            # durumda olcum kirlenebilir, bu yuzden bildirilir.
            return len(satirlar)
        finally:
            c.close()

    # --- 6a: is parcasi sayisindan BAGIMSIZ sinir ---------------------
    hata = []

    def _is():
        try:
            with P.baglanti() as b:
                im = b.cursor()
                im.execute("SELECT 1")
                im.fetchone()
                time.sleep(0.35)
        except Exception as e:
            hata.append(repr(e))

    ipler = [threading.Thread(target=_is) for _ in range(40)]
    for t in ipler:
        t.start()
    time.sleep(0.20)
    try:
        zirve = _acik_baglanti_sayisi()
    except Exception as e:
        zirve = -1
        hata.append(repr(e))
    for t in ipler:
        t.join(timeout=25)

    olc("40 is parcasi: hatasiz tamamlandi", not hata,
        "; ".join(hata[:2]))
    sinir = getattr(P, "HAVUZ_MAKS", 10)
    olc("40 is parcasi: baglanti sayisi sinirli (<= %d)" % (sinir + 2),
        0 <= zirve <= sinir + 2, "olculen zirve: %s" % zirve)

    # --- 6b: SIZINTI (asil kusur) -------------------------------------
    # DOGRU OLCUT NEDIR?
    # Ilk yazimda ACIK BAGLANTI SAYISI olculuyordu. Bu YANLIS bir
    # olcuttur: havuz, is parcasi olunce baglantiyi kapatmaz, yeniden
    # kullanmak uzere BOSTA listesinde tutar -- havuzun varlik sebebi
    # tam olarak budur, cunku PostgreSQL'de her yeni baglanti sunucuda
    # yeni bir surec demektir ve pahalidir. O olcutle saglam bir havuz
    # bile "sizdiriyor" gorunur.
    #
    # Gercek sizinti, YUVANIN GERI DONMEMESIDIR: is parcasi olmus ama
    # havuz onun yuvasini hala 'odunc verilmis' sayiyorsa o yuva bir
    # daha kullanilamaz ve havuz zamanla sifira iner. Olcut bu yuzden
    # `odunc` alanidir; ayrica bosta baglantilarin gercekten yeniden
    # kullanildigi dogrulanir.
    try:
        P.tum_baglantilari_kapat()
    except Exception:
        pass
    time.sleep(0.6)
    d0 = P.havuz_durumu()

    def _kirli_is():
        try:
            with P.baglanti() as b:
                im = b.cursor()
                im.execute("SELECT 1")
                im.fetchone()
        except Exception:
            pass
        # BILEREK temizlemeden cikiliyor.

    gecici = [threading.Thread(target=_kirli_is) for _ in range(15)]
    for t in gecici:
        t.start()
    for t in gecici:
        t.join(timeout=25)
    time.sleep(1.5)  # olum kancalarina zaman tani
    d1 = P.havuz_durumu()

    olc("15 temizlenmemis is parcasi: YUVA SIZINTISI YOK",
        d1.get("odunc", -1) == 0,
        "odunc=%s (once=%s)" % (d1.get("odunc"), d0.get("odunc")))
    olc("Iade edilen baglantilar bosta listesinde (yeniden kullanim)",
        d1.get("bosta", 0) > 0,
        "bosta=%s acik=%s" % (d1.get("bosta"), d1.get("acik")))
    olc("Acik baglanti sayisi sinirin ustune cikmadi",
        0 <= d1.get("acik", -1) <= sinir,
        "acik=%s maks=%s" % (d1.get("acik"), d1.get("maks")))

    # Yuvalar gercekten yeniden kullanilabiliyor mu? Sizinti varsa
    # asagidaki tur ya bloklanir ya da yeni baglanti acmak zorunda
    # kalir; ikisi de `acik` sayisini artirirdi.
    hata2 = []

    def _tekrar():
        try:
            with P.baglanti() as b:
                im = b.cursor()
                im.execute("SELECT 1")
                im.fetchone()
        except Exception as e:
            hata2.append(repr(e))

    t2 = [threading.Thread(target=_tekrar) for _ in range(15)]
    for t in t2:
        t.start()
    for t in t2:
        t.join(timeout=25)
    d2 = P.havuz_durumu()
    olc("Olu is parcalarinin yuvalari YENIDEN KULLANILIYOR",
        not hata2 and d2.get("acik", 99) <= sinir,
        "acik=%s hata=%s" % (d2.get("acik"), (hata2 or ["yok"])[0]))

    # Sunucu tarafinda da toplam baglanti sinirin altinda kalmali.
    try:
        gercek = _acik_baglanti_sayisi()
        olc("Sunucu tarafinda da baglanti sayisi sinirli",
            0 <= gercek <= sinir + 2, "sunucuda: %s" % gercek)
    except Exception as e:
        atla("Sunucu tarafi baglanti sayimi", repr(e))

    # --- 6c: 'islem icinde bosta' birakilmiyor -------------------------
    try:
        import psycopg2
        with P.baglanti() as b:
            im = b.cursor()
            im.execute("SELECT 1")
            im.fetchone()
        time.sleep(0.5)
        c = psycopg2.connect(
            host=bilgi.get("host"), port=int(bilgi.get("port") or 5432),
            dbname=vt_adi, user=bilgi.get("user"),
            password=bilgi.get("password"), connect_timeout=8,
            application_name="sinav2452")
        try:
            # Burada da yalniz BU SURECIN baglantilari sayilir; arka
            # planda calisan bir GOKTUNGU sunucusu olcumu kirletmesin.
            benim = _kendi_portlarimiz()
            with c.cursor() as im2:
                im2.execute(
                    "SELECT client_port FROM pg_stat_activity"
                    " WHERE datname=%s AND application_name=%s"
                    " AND state='idle in transaction'",
                    (vt_adi, "goktungu"))
                pl = [r[0] for r in im2.fetchall()]
            iit = (sum(1 for p in pl if p in benim) if benim else len(pl))
        finally:
            c.close()
        olc("Iade edilen baglanti 'islem icinde bosta' DEGIL",
            iit == 0, "olculen: %d" % iit)
    except Exception as e:
        olc("'islem icinde bosta' olcumu", False, repr(e))

    # --- 6d: havuz dolunca acik hata ----------------------------------
    # Sessiz bekleme ucus sirasinda donan arayuz demektir.
    try:
        kaynak = inspect.getsource(P)
        olc("Havuz dolunca zaman asimi ile hata veriliyor",
            re.search(r"HAVUZ_BEKLEME|timeout|zaman asimi", kaynak)
            is not None)
    except Exception:
        atla("Havuz dolunca hata", "kaynak okunamadi")

    try:
        P.tum_baglantilari_kapat()
    except Exception:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
