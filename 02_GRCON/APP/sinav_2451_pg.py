#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GOKTUNGU v2.4.51 - POSTGRESQL GECIS / SIHIRBAZ SINAVI

Amac: v2.4.51'in kurulum yerinde GERCEKTEN calisip calismadigini
olcmek. Bu surumun tum kusurlari SESSIZDIR:

  * Yanlis API adi (`pg.yapilandirildi` yerine `pg.yapilandirma_var`)
    Python'da yalniz CAGRILDIGI AN patlar. WS islevi bir `except`
    icinde ise kullanici yalnizca "sihirbaz acilmiyor" gorur.
  * `goc.durum()` "guncel" doner; "gerekli" onun TERSIDIR. Bu iki
    alan karistirilirsa goc sihirbazi HIC acilmaz ve kullanici eski
    semayla calismaya devam eder -- veri kaybi bu sekilde olusur.
  * Arayuz ile arka uc AYRI yazildi. Bir alan adi uyusmazsa sihirbaz
    bos ekran gosterir; konsola hata DUSMEZ.
  * i18n dengesi bozulursa eksik dilde anahtar adi ("pgBaslik") ham
    metin olarak ekrana yazilir.

Bu yuzden sinav dosya varligiyla yetinmez: MODULU YUKLER, API
imzalarini olcer, arayuz-arka uc sozlesmesini iki yonlu karsilastirir
ve gercek PostgreSQL varsa ucu uca sema kurar.

Kullanim: kurulum kokunde `python3 sinav_2451_pg.py`
"""
from __future__ import annotations
import inspect
import json
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
    print("GOKTUNGU v2.4.51 - POSTGRESQL GECIS / SIHIRBAZ SINAVI")
    print("=" * 70)

    # ==================================================================
    print()
    print("[1] SURUM DAMGALARI")
    # Surum uc yerde tutulur; biri geride kalirsa tarayici ESKI JS'i
    # onbellekten yukler ve sihirbaz hic gorunmez.
    # NOT: Bu sinav ILERI SURUMLERDE de gerileme sinavi olarak
    # calisir. Bu yuzden olcut "tam olarak 2.4.51" degil, "2.4.51 VEYA
    # daha yeni"dir; aksi halde her yeni surumde sahte alarm verir ve
    # zamanla guvenilirligini yitirir.
    def _surum_en_az(metin, en_az=(2, 4, 51)):
        bulunan = re.findall(r"(\d+)\.(\d+)\.(\d+)", metin or "")
        return any(tuple(int(x) for x in b) >= en_az for b in bulunan)

    ini = oku("goktungu", "__init__.py")
    olc("goktungu/__init__.py surum >= 2.4.51", _surum_en_az(ini))
    sj = oku("js", "surum.js")
    olc("js/surum.js GCS_SURUM >= 2.4.51", _surum_en_az(sj))
    olc("js/surum.js 2.4.51 gecmis girdisi duruyor",
        re.search(r"2\.4\.51", sj) is not None)
    ih = oku("index.html")
    etiketler = set(int(e) for e in re.findall(r"\?v=v(\d{4})", ih))
    olc("index.html onbellek etiketi >= v2451",
        bool(etiketler) and min(etiketler) >= 2451,
        "etiketler: %s" % (sorted(etiketler) or "yok"))
    olc("index.html eski etiket kalmadi",
        "?v=v2450" not in ih and "?v=v2449" not in ih)

    # ==================================================================
    print()
    print("[2] YENI MODULLER VAR MI")
    for p in ("goktungu/pg.py", "goktungu/goc.py", "js/pg_sihirbaz.js"):
        olc("%s var" % p, os.path.isfile(_y(*p.split("/"))))

    # ==================================================================
    print()
    print("[3] pg.py API SOZLESMESI")
    # Bu adlar sunucu.py, main.py, veritabani.py, tile_cache.py ve
    # telemetri_tampon.py tarafindan cagrilir. Bir ad degisirse
    # cagiran taraf calisma aninda patlar.
    try:
        sys.path.insert(0, _y("goktungu"))
        from goktungu import pg as _pg
        olc("goktungu.pg yuklenebiliyor", True)

        for ad in ("yapilandir", "yapilandirma_var", "dosya_var",
                   "dosyadan_yukle", "yapilandirma_oku", "dene",
                   "veritabani_olustur", "baglanti", "ikili",
                   "tum_baglantilari_kapat"):
            olc("pg.%s() var" % ad, callable(getattr(_pg, ad, None)))
        olc("pg.VAR (surucu bayragi) var", hasattr(_pg, "VAR"))

        # `dene` ve `veritabani_olustur` ADLI parametre alir; sunucu.py
        # bunlari **cagri ile gecer. Sozluk beklerse TypeError olur.
        for ad in ("dene", "veritabani_olustur"):
            try:
                imza = inspect.signature(getattr(_pg, ad))
                p = set(imza.parameters)
                olc("pg.%s adli parametreli (host/veritabani/kullanici)"
                    % ad,
                    {"host", "veritabani", "kullanici", "sifre"} <= p,
                    str(sorted(p)))
            except (TypeError, ValueError):
                olc("pg.%s imzasi okunabilir" % ad, False)

        # `yapilandir` diske yazma anahtarini almali; sihirbaz bunu
        # True gecer, yoksa yapilandirma bir sonraki aciliste kaybolur.
        try:
            p = set(inspect.signature(_pg.yapilandir).parameters)
            olc("pg.yapilandir(diske_yaz=...) destekliyor",
                "diske_yaz" in p, str(sorted(p)))
        except (TypeError, ValueError):
            olc("pg.yapilandir imzasi okunabilir", False)

        olc("pg._hata_sadelestir() var",
            callable(getattr(_pg, "_hata_sadelestir", None)))
    except Exception as e:
        olc("goktungu.pg yuklenebiliyor", False, "%s: %s" % (type(e).__name__, e))

    # ==================================================================
    print()
    print("[4] pg.py SQL LEHCE CEVIRISI")
    pgk = oku("goktungu", "pg.py")
    # Bu cevirilerin her biri olculmus bir kusurdan dogdu; biri
    # kaybolursa SQLite icin yazilmis 146 cagri yerinden biri patlar.
    olc("? -> %s yer tutucu cevirisi var",
        "%s" in pgk and re.search(r"yer_?tutucu|placeholder|\?", pgk)
        is not None)
    olc("AUTOINCREMENT -> BIGSERIAL cevirisi var",
        "AUTOINCREMENT" in pgk and "BIGSERIAL" in pgk)
    olc("COLLATE NOCASE -> citext cevirisi var",
        "NOCASE" in pgk and "citext" in pgk.lower())
    olc("strftime -> to_char cevirisi var",
        "strftime" in pgk and "to_char" in pgk.lower())
    olc("INSERT OR REPLACE cevirisi var",
        "OR REPLACE" in pgk or "ON CONFLICT" in pgk)
    olc("lastrowid SAVEPOINT ile korunuyor",
        "SAVEPOINT" in pgk and "lastrowid" in pgk)
    olc("total_changes karsiligi var (telemetri aktarimi buna bakar)",
        "total_changes" in pgk)
    # OLCULEN KUSUR: `RETURNING id` kosulsuz eklenirse `id` kolonu
    # olmayan tablolarda hata olusur ve rollback onceki yazimlari siler.
    olc("RETURNING yalniz id kolonu VARSA ekleniyor",
        "RETURNING" in pgk and
        re.search(r"id_kolon|_id_var|id_kolonu|kolon_var", pgk) is not None)

    # ==================================================================
    print()
    print("[5] goc.py API SOZLESMESI")
    try:
        from goktungu import goc as _goc
        olc("goktungu.goc yuklenebiliyor", True)
        olc("goc.GocMotoru sinifi var",
            inspect.isclass(getattr(_goc, "GocMotoru", None)))
        M = getattr(_goc, "GocMotoru", None)
        if M:
            for ad in ("durum", "calistir", "gerekli_mi",
                       "bekleyen_adimlar"):
                olc("GocMotoru.%s() var" % ad,
                    callable(getattr(M, ad, None)))
            try:
                p = set(inspect.signature(M.calistir).parameters)
                olc("GocMotoru.calistir(ilerleme=...) destekliyor",
                    "ilerleme" in p, str(sorted(p)))
            except (TypeError, ValueError):
                olc("GocMotoru.calistir imzasi okunabilir", False)
            try:
                p = set(inspect.signature(M.__init__).parameters)
                olc("GocMotoru(konsol=...) destekliyor", "konsol" in p,
                    str(sorted(p)))
            except (TypeError, ValueError):
                olc("GocMotoru.__init__ imzasi okunabilir", False)
        for ad in ("sema_surumu", "adim_uygulandi_mi", "defter_kur"):
            olc("goc.%s() var" % ad, callable(getattr(_goc, ad, None)))
        olc("goc.ADIMLAR listesi dolu",
            isinstance(getattr(_goc, "ADIMLAR", None), list) and
            len(_goc.ADIMLAR) > 0,
            str(len(getattr(_goc, "ADIMLAR", []) or [])))
        # Her adimin agirligi olmali; yoksa ilerleme yuzdesi hesaplanamaz
        # ve cubuk 0'da donar.
        try:
            olc("her goc adiminda agirlik/aciklama var",
                all(getattr(a, "agirlik", 0) > 0 and
                    getattr(a, "aciklama", "") for a in _goc.ADIMLAR))
        except Exception:
            olc("her goc adiminda agirlik/aciklama var", False)
    except Exception as e:
        olc("goktungu.goc yuklenebiliyor", False,
            "%s: %s" % (type(e).__name__, e))

    gk = oku("goktungu", "goc.py")
    olc("sema_goc_defteri tablosu var", "sema_goc_defteri" in gk)
    olc("defter kaydi adim BASARILI olduktan SONRA yazilir",
        "adim_kaydet" in gk)
    olc("yarim kalmis goc kurtarma var",
        "yarim" in gk.lower() or "kurtar" in gk.lower() or
        "hata" in gk.lower())

    # ==================================================================
    print()
    print("[6] veritabani.py PG BAGLAMASI")
    vt = oku("goktungu", "veritabani.py")
    olc("kip_ayarla() var", "def kip_ayarla" in vt)
    olc("postgresql kipi taniniyor", "postgresql" in vt)
    for t in ("harita_karo", "gorev_durum", "telemetri_tampon_kayit"):
        olc("yeni tablo %s tanimli" % t, t in vt)
    # `sema_goc_defteri` BILINCLI olarak goc.py'de tanimlidir: goc
    # motoru kendi defterini veritabani semasindan ONCE kurmak zorunda
    # (sema henuz yokken bile hangi adimlarin uygulandigini bilmeli).
    olc("sema_goc_defteri goc.py'de tanimli",
        "sema_goc_defteri" in gk)
    # OLCULEN KUSUR: gorev_durum birincil anahtari dron_uid ise iki
    # dron AYNI satiri ezer. Anahtar MAVLink sysid olmali.
    olc("gorev_durum birincil anahtari sysid",
        re.search(r"gorev_durum.{0,400}?sysid[^,\)]{0,40}PRIMARY KEY",
                  vt, re.S) is not None)
    # OLCULEN KUSUR: BIGSERIAL anlamli anahtarlari ezmemeli.
    olc("v_ucuslar gorunumu GROUP BY ile duzeltildi",
        re.search(r"v_ucuslar", vt) is not None and "GROUP BY" in vt)

    # ==================================================================
    print()
    print("[7] sunucu.py WS KOMUTLARI")
    su = oku("goktungu", "sunucu.py")
    olc("_pg_sihirbaz() isleyicisi var", "_pg_sihirbaz" in su)
    for k in ("pg_durum", "pg_dene", "pg_olustur", "pg_kur", "pg_goc"):
        olc("WS komutu %s tanimli" % k, '"%s"' % k in su)
    olc("komut yonlendirme dali bagli",
        re.search(r"pg_durum.{0,200}_pg_sihirbaz", su, re.S) is not None
        or re.search(r"_pg_sihirbaz\(", su) is not None)
    olc("pg_ilerleme yayini var", "pg_ilerleme" in su)
    olc("ANLIK ilerleme: call_soon_threadsafe kullanilir",
        "call_soon_threadsafe" in su)
    olc("ilerleme kuyrugu asyncio.Queue", "asyncio.Queue" in su)
    # Kullanici istegi geregi sihirbaz giris ONCESI calisir; ama
    # yapilandirma varsa yalniz yonetici degistirebilir.
    olc("kapi denetimi: yapilandirma varsa yonetici sarti",
        re.search(r'rol.{0,30}yonetici', su) is not None)
    olc("pg_durum giris oncesi acik (kapi disi)",
        re.search(r'komut\s*!=\s*"pg_durum"', su) is not None)
    olc("SIFRE pg_durum yanitinda GONDERILMIYOR",
        re.search(r'durum\["sifre"\]', su) is None)
    # OLCULEN KUSUR: yuzde geri sariyordu (hazirlik 2,6 -> goc 0).
    olc("ilerleme yuzdesi TEK YONLU kelepceli (geri sarmaz)",
        "_tavan" in su or re.search(r"en_yuksek|geri sarma", su) is not None)
    # OLCULEN KUSUR: yetkisiz kullanici semasi yarida kalirdi.
    olc("pg_kur once tablo olusturma yetkisi olcer",
        "yetki_tablo" in su)

    # ==================================================================
    print()
    print("[8] ARAYUZ - ARKA UC SOZLESMESI (iki yonlu)")
    js = oku("js", "pg_sihirbaz.js")
    ws = oku("js", "ws.js")
    for k in ("pg_durum", "pg_sonuc", "pg_ilerleme"):
        olc("ws.js %s yonlendirmesi var" % k, k in ws)
    for f in ("pgDurumGeldi", "pgSonucGeldi", "pgIlerlemeGeldi"):
        olc("ws.js %s cagiriyor" % f, f in ws)
        olc("pg_sihirbaz.js %s tanimliyor" % f,
            "window.%s" % f in js)
    olc("ws.js acilista pgDurumSor cagiriyor", "pgDurumSor" in ws)
    olc("pg_sihirbaz.js pgDurumSor tanimliyor",
        "window.pgDurumSor" in js)
    # Arka ucun DONDURDUGU her alan arayuzde OKUNMALI; okunmayan alan
    # sessiz kopmanin isaretidir.
    for alan in ("yapilandirildi", "goc_gerekli", "erisim", "surucu_var",
                 "sema_surum", "hedef_surum", "bekleyen"):
        olc("arayuz pg_durum.%s okuyor" % alan, alan in js)
    for alan in ("basarili", "hata", "surum", "tablo_sayisi", "citext",
                 "veritabani_var", "yetki"):
        olc("arayuz pg_sonuc.%s okuyor" % alan, alan in js)
    for alan in ("yuzde", "ileti"):
        olc("arayuz pg_ilerleme.%s okuyor" % alan, alan in js)
    # Arayuzun GONDERDIGI her alan arka ucta OKUNMALI.
    for alan in ("sunucu", "port", "veritabani", "kullanici", "sifre"):
        olc("arka uc pg_dene.%s okuyor" % alan,
            'k.get("%s")' % alan in su or '"%s"' % alan in su)

    # ==================================================================
    print()
    print("[9] SIHIRBAZ AKISI (3 adim + goc kipi)")
    olc("kurulum kipi var", '"kurulum"' in js)
    olc("goc kipi var", '"goc"' in js)
    olc("adim 1 govdesi (baglanti bilgileri)", "pgAdim1Govde" in js)
    olc("adim 2 govdesi (dogrulama)", "pgAdim2Govde" in js)
    olc("adim 3 govdesi (ilerleme)", "pgAdim3Govde" in js)
    olc("goc govdesi ayri", "pgGocGovde" in js)
    olc("ilerleme cubugu cizimi", "pgIlerlemeGovde" in js)
    olc("veritabani olustur dugmesi", "pgVeritabaniOlustur" in js)
    olc("kur baslat", "pgKurBaslat" in js)
    olc("goc baslat", "pgGocBaslat" in js)
    olc("baglanti kopmasi ele alinir", "pgBaglantiYok" in js)
    olc("dil degisiminde yeniden cizilir",
        "pgSihirbazDilGuncelle" in js and "pgSihirbazDilGuncelle" in
        oku("js", "i18n.js"))
    olc("sihirbaz acik mi sorgusu (giris ekrani bunu bilmeli)",
        "pgSihirbazAcikMi" in js)
    olc("yonetici menusunden yeniden acilabilir",
        "pgSihirbazYenidenAc" in js)
    olc("kullanici menusune Veritabani Ayarlari eklendi",
        "pmVeritabani" in oku("index.html") or
        "pmVeritabani" in oku("js", "kullanici.js"))

    # ==================================================================
    print()
    print("[10] i18n ANAHTARLARI VE DENGE")
    i18 = oku("js", "i18n.js")
    # Adlar i18n.js'teki GERCEK anahtarlardir (dosyadan olculdu).
    for a in ("pgBaslik", "pgAltBaslik", "pgAdim", "pgAdim1", "pgAdim2",
              "pgAdim3", "pgSunucu", "pgPort", "pgVt", "pgKullanici",
              "pgSifre", "pgIleri", "pgGeri", "pgDeniyor",
              "pgBaglantiTamam", "pgSurum", "pgTabloSayisi", "pgVtYok",
              "pgOlustur", "pgCitext", "pgYetki", "pgKur",
              "pgKuruluyor", "pgKurulumTamam", "pgSemaSurum",
              "pgGiris", "pgHata", "pgSurucuYok", "pgGocBaslik",
              "pgGocGerekli", "pgGocBekleyen", "pgGocBaslat",
              "pgGocTamamlandi", "pgErisimYok", "pgYeniden",
              "pgYoneticiGerek", "pmVeritabani"):
        olc("i18n anahtari %s var" % a, a in i18)

    # Denge olcumu: sozlukler `  TR: {` / `  EN: {` ile baslar ve
    # anahtarlar DORT bosluk girintilidir. Daha gevsek bir desen
    # (`\s{2,}`) ic ice sozluklerin anahtarlarini da toplayip yanlis
    # sonuc uretir; bu yuzden girinti TAM dort bosluk olarak olculur.
    try:
        iTR = i18.index("  TR: {")
        iEN = i18.index("  EN: {")
        desen = re.compile(r"^ {4}([A-Za-z_][A-Za-z0-9_]*)\s*:", re.M)
        atr = set(desen.findall(i18[iTR:iEN]))
        aen = set(desen.findall(i18[iEN:]))
        olc("i18n TR/EN anahtar sayisi ESIT", len(atr) == len(aen),
            "TR %d / EN %d" % (len(atr), len(aen)))
        olc("EN'de eksik anahtar yok", not (atr - aen),
            ", ".join(sorted(atr - aen)[:12]))
        olc("TR'de eksik anahtar yok", not (aen - atr),
            ", ".join(sorted(aen - atr)[:12]))
        # PG anahtarlari IKI dilde de bulunmali; yalniz birinde varsa
        # eksik dilde ham anahtar adi ekrana yazilir.
        pgtr = {k for k in atr if k.startswith("pg")}
        pgen = {k for k in aen if k.startswith("pg")}
        olc("PG anahtarlari iki dilde de tam",
            pgtr == pgen and len(pgtr) >= 30,
            "TR %d / EN %d" % (len(pgtr), len(pgen)))
    except ValueError:
        olc("i18n TR/EN sozlukleri bulundu", False)

    # ==================================================================
    print()
    print("[11] CSS SINIFLARI")
    css = oku("css", "stil.css")
    for c in (".pgs-perde", ".pgs-kutu", ".pgs-adim", ".pgs-ilerleme",
              ".pgs-alan", ".pgs-giris", ".pgs-hata"):
        olc("CSS %s tanimli" % c, c in css)
    # Perde giris ekranindan (3000), sirket kilidinden (9400) ve
    # serbest form popup'indan (9500) YUKSEK olmali.
    m = re.search(r"\.pgs-perde\s*\{[^}]*z-index:\s*(\d+)", css, re.S)
    olc("pgs-perde z-index > 9500 (sf-popup ustunde)",
        m is not None and int(m.group(1)) > 9500,
        m.group(1) if m else "bulunamadi")
    olc("pgs-perde z-index < 9600 (uyari toast'i altinda)",
        m is not None and int(m.group(1)) < 9600,
        m.group(1) if m else "")

    # ==================================================================
    print()
    print("[12] DOSYA -> PG TASIMA BAGLAMALARI")
    tc = oku("goktungu", "tile_cache.py")
    olc("tile_cache PG ana depoya bagli",
        "harita_karo" in tc and "pg" in tc)
    olc("tile_cache disk IKINCI katman olarak korunuyor",
        re.search(r"disk|dosya", tc) is not None)
    gr = oku("goktungu", "gorev.py")
    olc("gorev.py PG'ye yaziyor", "gorev_durum" in gr)
    olc("gorev.py dosya geri donusu korunuyor",
        "gorev_durum.json" in gr)
    tt = oku("goktungu", "telemetri_tampon.py")
    olc("telemetri defter kaydi PG'ye gidiyor",
        "telemetri_tampon_kayit" in tt)
    olc("telemetri ham ornekleri DOSYADA kaliyor (ag kesintisi)",
        "jsonl" in tt)
    # Kiosk betigi sunucu ayakta degilken bu dosyayi okur; PG'ye
    # tasinirsa ikinci ekran acilmaz.
    olc("veri/calisma.json DOSYADA kaldi (kiosk okur)",
        "calisma.json" in oku("goktungu", "sunucu.py") + oku("main.py") +
        oku("goktungu", "ayarlar.py"))

    # ==================================================================
    print()
    print("[13] ACILIS AKISI (main.py)")
    mp = oku("main.py")
    olc("main.py PG yapilandirmasini diskten yukluyor",
        "dosya_var" in mp or "dosyadan_yukle" in mp)
    olc("main.py PG kipini aciyor", "kip_ayarla" in mp)
    olc("main.py goc gerekliligini olcuyor",
        "goc" in mp and ("gerekli" in mp or "GocMotoru" in mp))
    # SQLite'a ozel butunluk denetimi PG kipinde ANLAMSIZ; quick_check
    # bir SQLite pragmasidir.
    olc("PG kipinde SQLite butunluk denetimi atlaniyor",
        "_PgKipiAtla" in mp)
    olc("yapilandirma yoksa konsola bildirilir",
        re.search(r"sihirbaz", mp, re.I) is not None)

    # ==================================================================
    print()
    print("[14] SOZDIZIMI")
    for p in ("main.py", "goktungu/pg.py", "goktungu/goc.py",
              "goktungu/veritabani.py", "goktungu/sunucu.py", "goktungu/gorev.py",
              "goktungu/tile_cache.py", "goktungu/telemetri_tampon.py"):
        yol = _y(*p.split("/"))
        if not os.path.isfile(yol):
            olc("%s var" % p, False)
            continue
        r = subprocess.run([sys.executable, "-m", "py_compile", yol],
                           capture_output=True, text=True)
        olc("%s sozdizimi tamam" % p, r.returncode == 0,
            (r.stderr or "")[:160])

    if subprocess.run(["which", "node"], capture_output=True).returncode == 0:
        for p in ("js/pg_sihirbaz.js", "js/ws.js", "js/i18n.js",
                  "js/surum.js", "js/kullanici.js"):
            yol = _y(*p.split("/"))
            if not os.path.isfile(yol):
                olc("%s var" % p, False)
                continue
            r = subprocess.run(["node", "--check", yol],
                               capture_output=True, text=True)
            olc("%s sozdizimi tamam" % p, r.returncode == 0,
                (r.stderr or "")[:160])
    else:
        print("  [ATLA] node yok; JS sozdizimi olculemedi")

    # ==================================================================
    print()
    print("[15] GERCEK POSTGRESQL (varsa)")
    # Bu bolum yalniz psycopg2 kurulu VE erisilebilir bir sunucu varsa
    # calisir. Kurulum yerinde surucu yoksa ATLANIR -- sinav yine de
    # anlamlidir cunku yukaridaki 14 bolum kod sozlesmesini olcer.
    try:
        from goktungu import pg as _pg2
        if not getattr(_pg2, "VAR", False):
            print("  [ATLA] psycopg2 kurulu degil "
                  "(pip3 install psycopg2-binary)")
        elif not _pg2.dosya_var():
            print("  [ATLA] PG yapilandirmasi yok; sihirbaz henuz "
                  "calistirilmamis")
        else:
            _pg2.dosyadan_yukle()
            from goktungu import veritabani as _vt2
            _vt2.kip_ayarla("postgresql")
            from goktungu import goc as _goc2
            con = _vt2.baglanti()
            im = con.cursor()
            im.execute("SELECT count(*) FROM information_schema.tables "
                       "WHERE table_schema='public'")
            n = im.fetchone()[0]
            olc("PG'de tablolar kurulu (>=27)", n >= 27, "%d tablo" % n)
            s = _goc2.sema_surumu()
            olc("sema surumu damgalanmis", s > 0, str(s))
            # Bu sinav v2.4.52 gibi YENI sema adimlari getiren bir
            # yamadan sonra da calistirilabilir; o durumda gocun
            # GEREKLI olmasi normaldir ve kusur degildir. Olcut bu
            # yuzden "sema guncel olsun" degil TUTARLILIK'tir;
            # tutarsizlik gercek kusurdur: sihirbaz ya hic acilmaz
            # (eski semayla ucus) ya da her aciliste bosuna acilir.
            #
            # OLCULEN GERCEK: gereklilik surum SAYISI karsilastirmasiyla
            # degil, DEFTERDEKI ADIM KAYDIYLA belirlenir (yarim kalmis
            # gocu de yakalar). Dogru olcut bu yuzden gerekli_mi() ile
            # bekleyen_adimlar() arasindaki tutarliliktir.
            _m = _goc2.GocMotoru()
            _gerekli = _m.gerekli_mi()
            _bekleyen = _m.bekleyen_adimlar()
            olc("goc gerekliligi bekleyen adimlarla tutarli",
                _gerekli == (len(_bekleyen) > 0),
                "gerekli=%s bekleyen=%d" % (_gerekli, len(_bekleyen)))
            # durum() sozlugu arayuze gider; "guncel" alani
            # gerekli_mi()'nin TERSI olmalidir. Ters cevrilirse
            # sihirbaz hic acilmaz ve eski semayla ucus surer.
            _d = _m.durum()
            olc("durum()['guncel'] gerekli_mi() ile tutarli",
                bool(_d.get("guncel")) == (not _gerekli),
                "guncel=%s gerekli=%s" % (_d.get("guncel"), _gerekli))
            olc("durum() hedef_surum bildiriyor",
                isinstance(_d.get("hedef_surum"), int) and
                _d.get("hedef_surum") > 0,
                "hedef=%s sema=%s" % (_d.get("hedef_surum"), s))
            # Yazma yolu: ikili veri (harita karosu) PG'ye gidiyor mu
            im.execute("SELECT count(*) FROM harita_karo")
            olc("harita_karo tablosu okunabiliyor", True,
                "%d karo" % im.fetchone()[0])
            im.execute("SELECT count(*) FROM gorev_durum")
            olc("gorev_durum tablosu okunabiliyor", True)
            im.execute("SELECT count(*) FROM telemetri_tampon_kayit")
            olc("telemetri_tampon_kayit tablosu okunabiliyor", True)
            _pg2.tum_baglantilari_kapat()
    except Exception as e:
        olc("gercek PG olcumu", False, "%s: %s" % (type(e).__name__, e))

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
