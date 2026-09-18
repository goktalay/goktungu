#!/usr/bin/env python3
"""Lisans -> radar/GCCDUAL yetenek ust siniri olcumu.

NE OLCULUYOR
  Kullanici istegi: "radar yada gccdual acik olan sirketlerin indirdigi
  merkezi yazilimda bu modullerde acik olsun".

  Bunun iki yani var ve IKISI de olculmeli:
    1) ARAYUZ: menuler lisansa gore gorunur/gizlenir
    2) SUNUCU: menu gizlemek YETMEZ — istemci WS komutunu dogrudan
       gonderebilir, sunucu da reddetmeli

  Ayrica olagan (lisanssiz) kurulumun BOZULMADIGI olculuyor: lisans
  dosyasi yoksa ust sinir uygulanmamali, yoksa kopruden merkeze baglanan
  mevcut musterilerin radar/AI menuleri kapanirdi.

KOSUM  python3.11 sinav_lisans_yetenek.py
"""
import os
import re
import sys

KOK = os.path.dirname(os.path.abspath(__file__))

gecti = []
kaldi = []


def olc(ad, kosul, ek=""):
    (gecti if kosul else kaldi).append(ad)
    im = "GECTI" if kosul else "KALDI"
    print(f"  [{im}] {ad}" + (f"  -- {ek}" if not kosul and ek else ""))


def oku(*parcalar):
    with open(os.path.join(KOK, *parcalar), encoding="utf-8") as f:
        return f.read()


def yorumsuz_js(metin):
    """JS yorumlarini siler.

    NEDEN: bir onceki fazda ayni ad hem gercek kodda hem YORUMDA
    geciyordu; enjeksiyon gercek satiri bozdugunda sinav yorumdaki
    kalintiyi gorup geciyordu. Bu yuzden olcum yorumsuz metinde.
    """
    metin = re.sub(r"/\*.*?\*/", "", metin, flags=re.S)
    metin = re.sub(r"(?m)^\s*//.*$", "", metin)
    metin = re.sub(r"(?m)\s//[^\"'\n]*$", "", metin)
    return metin


def yorumsuz_py(metin):
    return re.sub(r"(?m)^\s*#.*$", "", metin)


def davranis_olc():
    """`_lisans_izni_var` ve `_komut_isle`'yi GERCEKTEN cagirir.

    Metin olcumu, denetimin etkisiz hale getirilmesini (`if False and
    ...`) yakalamaz. Burada sahte bir sunucu nesnesi kurulup davranis
    olculuyor.
    """
    import asyncio
    import types

    sys.path.insert(0, KOK)
    try:
        from goktungu import sunucu as sun_mod
    except Exception as e:
        olc("sunucu modulu ice alinabiliyor", False, repr(e)[:120])
        return
    olc("sunucu modulu ice alinabiliyor", True)

    # Sunucu sinifini bul
    sinif = None
    for ad in dir(sun_mod):
        n = getattr(sun_mod, ad)
        if isinstance(n, type) and hasattr(n, "_lisans_izni_var"):
            sinif = n
            break
    olc("_lisans_izni_var tasiyan sinif bulundu", sinif is not None)
    if sinif is None:
        return

    class SahteSunucu:
        """Yalnizca lisans denetimi icin gereken en kucuk yuzey."""

        LISANS_KOMUT_ALANI = sinif.LISANS_KOMUT_ALANI
        _lisans_izni_var = sinif._lisans_izni_var

        def __init__(self, ozet):
            self._ozet = ozet
            self.uyarilar = []
            self.konsollar = []

        def _lisans_ozeti_al(self):
            return self._ozet

        async def _uyari_gonder(self, ws, alan, mesaj, tur="bilgi"):
            self.uyarilar.append((alan, mesaj, tur))

        def konsol(self, *a, **k):
            self.konsollar.append(a)

    def cagir(ozet, komut):
        s = SahteSunucu(ozet)
        sonuc = asyncio.new_event_loop().run_until_complete(
            s._lisans_izni_var(None, komut))
        return sonuc, s

    # --- Durum 1: lisans YOK -> sinir uygulanmaz (olagan kurulum) ---
    for ozet in (None, {"lisansli": False, "radar": False}):
        sonuc, s = cagir(ozet, "radar_baglan")
        olc(f"lisanssiz ({'None' if ozet is None else 'lisansli=False'}) "
            f"radar_baglan GECIYOR", sonuc is True,
            "olagan kurulumda radar kilitlenir!")

    # --- Durum 2: lisansli, radar KAPALI -> reddedilir ---
    ozet_kapali = {"lisansli": True, "sinirsiz": True, "ai": True,
                   "radar": False, "gccdual": False}
    sonuc, s = cagir(ozet_kapali, "radar_baglan")
    olc("lisansli+radar kapali -> radar_baglan REDDEDILIYOR",
        sonuc is False, "yetkisiz radar komutu gecti!")
    olc("ret uyarisi gonderiliyor", len(s.uyarilar) == 1,
        f"{len(s.uyarilar)} uyari")
    if s.uyarilar:
        alan, mesaj, tur = s.uyarilar[0]
        olc("uyari alani radar", alan == "radar", f"alan={alan}")
        olc("uyari turu hata", tur == "hata", f"tur={tur}")
        olc("uyari kurumsal panele yonlendiriyor",
            "kurumsal panel" in mesaj.lower(), mesaj[:80])
    olc("ret konsola yaziliyor", len(s.konsollar) >= 1)

    sonuc, _ = cagir(ozet_kapali, "istasyon2_baglan")
    olc("lisansli+gccdual kapali -> istasyon2_baglan REDDEDILIYOR",
        sonuc is False)

    # --- Durum 3: lisansli, radar ACIK -> gecer ---
    ozet_acik = {"lisansli": True, "sinirsiz": True, "ai": True,
                 "radar": True, "gccdual": True}
    sonuc, s = cagir(ozet_acik, "radar_baglan")
    olc("lisansli+radar acik -> radar_baglan GECIYOR", sonuc is True,
        "lisansta acik olan modul reddedildi!")
    olc("gecen komutta uyari YOK", not s.uyarilar)

    sonuc, _ = cagir(ozet_acik, "istasyon2_baglan")
    olc("lisansli+gccdual acik -> istasyon2_baglan GECIYOR",
        sonuc is True)

    # --- Durum 4: tabloda olmayan komut hic denetlenmez ---
    sonuc, s = cagir(ozet_kapali, "drone_listesi")
    olc("ilgisiz komut denetimden etkilenmiyor", sonuc is True,
        "lisans denetimi ilgisiz komutu engelledi!")

    # --- Durum 5: _komut_isle GERCEKTEN denetimi cagiriyor mu ---
    # `if False and not await ...` enjeksiyonu ancak boyle yakalanir.
    kaynak = ""
    try:
        import inspect
        kaynak = inspect.getsource(sinif._komut_isle)
    except Exception:
        pass
    if kaynak:
        # Denetim, kosulsuz olarak (short-circuit edilmeden) cagrilmali
        satir = None
        for s_ in kaynak.splitlines():
            if "_lisans_izni_var" in s_:
                satir = s_.strip()
                break
        olc("_komut_isle denetimi cagiriyor", satir is not None)
        if satir:
            olc("denetim cagrisi kosulsuz (short-circuit YOK)",
                re.match(r"if\s+not\s+await\s+self\._lisans_izni_var\(",
                         satir) is not None,
                f"satir: {satir[:80]}")


def main():
    print("=" * 66)
    print(" LISANS -> YETENEK UST SINIRI OLCUMU")
    print("=" * 66)

    # ================================================================
    # 1) SUNUCU: lisans ozeti arayuze yayinlaniyor mu
    # ================================================================
    print("\n[1] goktungu/ayarlar.py — lisans ozeti yayini")
    ay = yorumsuz_py(oku("goktungu", "ayarlar.py"))

    olc("yayin() lisans alanini dolduruyor",
        re.search(r'a\["lisans"\]\s*=\s*self\._lisans_ozeti\(\)', ay)
        is not None)
    olc("_lisans_ozeti tanimli",
        re.search(r"def _lisans_ozeti\(self", ay) is not None)

    # Imza ASLA yayinlanmamali: istemciye giderse taklit riski dogar
    ozet_blok = ""
    m = re.search(r"def _lisans_ozeti\(self.*?(?=\n    def |\Z)", ay,
                  flags=re.S)
    if m:
        ozet_blok = m.group(0)
    olc("lisans ozetinde imza YAYINLANMIYOR",
        bool(ozet_blok) and "imza" not in ozet_blok,
        "imza alani ozete girmis")
    olc("ozet lisans modulunden geliyor",
        "yetki_ozeti" in ozet_blok, "yetki_ozeti cagrisi yok")

    # ================================================================
    # 2) ARAYUZ: ust sinir islevi
    # ================================================================
    print("\n[2] js/program_ayar.js — ust sinir islevi")
    pa = yorumsuz_js(oku("js", "program_ayar.js"))

    olc("lisansUstSinir tanimli",
        re.search(r"function lisansUstSinir\s*\(\s*alan\s*\)", pa)
        is not None)

    # En kritik davranis: LISANSSIZ kurulumda sinir UYGULANMAZ
    m = re.search(r"function lisansUstSinir\s*\([^)]*\)\s*\{(.*?)\n\}", pa,
                  flags=re.S)
    govde = m.group(1) if m else ""
    olc("lisanssiz kurulumda ust sinir UYGULANMIYOR",
        re.search(r"if\s*\(\s*!_lisansOzet\s*\|\|\s*!_lisansOzet\.lisansli\s*\)"
                  r"\s*return\s+true", govde) is not None,
        "lisanssiz kurulumda menuler kapanir!")
    olc("lisansli kurumda alan degeri donuyor",
        re.search(r"return\s+!!\s*_lisansOzet\[\s*alan\s*\]", govde)
        is not None)

    olc("radarYetenekVar ust sinira bagli",
        re.search(r"function radarYetenekVar\s*\(\s*\)\s*\{.*?"
                  r"lisansUstSinir\(\s*[\"']radar[\"']\s*\)", pa, flags=re.S)
        is not None)
    olc("radarYetenekVar donanim kosulunu KORUYOR",
        re.search(r"function radarYetenekVar\s*\(\s*\)\s*\{.*?donanim.*?"
                  r"&&.*?lisansUstSinir", pa, flags=re.S) is not None,
        "donanim/kopru kosulu dusmus")

    olc("lisansOzetiSunucudan tanimli",
        re.search(r"window\.lisansOzetiSunucudan\s*=\s*function", pa)
        is not None)
    m2 = re.search(r"window\.lisansOzetiSunucudan\s*=\s*function[^{]*\{"
                   r"(.*?)\n\};", pa, flags=re.S)
    g2 = m2.group(1) if m2 else ""
    olc("ozet gelince radar menusu yenileniyor",
        "radarMenuGorunumGuncelle" in g2)
    olc("ozet gelince radar kipi uygulaniyor",
        "radarModuUygula" in g2)
    olc("ozet gelince GCCDUAL menusu yenileniyor",
        "istasyon2MenuGorunumGuncelle" in g2)

    # ================================================================
    # 3) GCCDUAL menusu
    # ================================================================
    print("\n[3] js/istasyon2.js — GCCDUAL gorunurlugu")
    i2 = yorumsuz_js(oku("js", "istasyon2.js"))
    olc("GCCDUAL gorunurlugu ust sinira bagli",
        re.search(r"lisansUstSinir\(\s*[\"']gccdual[\"']\s*\)", i2)
        is not None)

    # ================================================================
    # 4) Cagri SIRASI — lisans ozeti radar/GCCDUAL kararindan ONCE
    # ================================================================
    print("\n[4] js/harita.js — cagri sirasi")
    ha = yorumsuz_js(oku("js", "harita.js"))
    m3 = re.search(r"function ayarlariUygula\s*\([^)]*\)\s*\{(.*?)\n\}",
                   ha, flags=re.S)
    g3 = m3.group(1) if m3 else ha

    i_lis = g3.find("lisansOzetiSunucudan")
    i_rad = g3.find("radarMenuGorunumGuncelle")
    olc("ayarlariUygula lisans ozetini besliyor", i_lis >= 0)
    if i_lis >= 0 and i_rad >= 0:
        olc("lisans ozeti radar kararindan ONCE besleniyor", i_lis < i_rad,
            f"lisans@{i_lis} radar@{i_rad} — sira ters, ilk acilista "
            f"menu yanlis cizilir")

    # ================================================================
    # 5) SUNUCU tarafi ust sinir — menu gizlemek YETMEZ
    # ================================================================
    print("\n[5] goktungu/sunucu.py — sunucu tarafi denetim")
    su = yorumsuz_py(oku("goktungu", "sunucu.py"))

    olc("LISANS_KOMUT_ALANI tablosu var",
        re.search(r"LISANS_KOMUT_ALANI\s*=\s*\{", su) is not None)
    olc("_lisans_izni_var tanimli",
        re.search(r"def _lisans_izni_var\(", su) is not None)

    # Radar ve GCCDUAL komutlari tabloda olmali
    # NOT: tablo SINIF ICINDE tanimli, yani girintili `    }` ile
    # kapaniyor. Once `\n\}` araniyordu; hicbir sey ayiklanamiyordu ve
    # 5 olcum sahte KALDI veriyordu.
    m4 = re.search(r"LISANS_KOMUT_ALANI\s*=\s*\{(.*?)^\s*\}", su,
                   flags=re.S | re.M)
    tablo = m4.group(1) if m4 else ""
    olc("tablo ayiklandi", bool(tablo.strip()))
    for komut in ("radar_baglan", "radar_kes", "radar_ayar_yaz",
                  "rtk_konum_al"):
        olc(f"tabloda {komut}", f'"{komut}"' in tablo)
    for komut in ("istasyon2_baglan", "istasyon2_kes", "istasyon2_led"):
        olc(f"tabloda {komut}", f'"{komut}"' in tablo)
    olc("tablo radar alanina bagliyor", '"radar"' in tablo)
    olc("tablo gccdual alanina bagliyor", '"gccdual"' in tablo)

    # Tabloda HAYALI komut olmamali: gercekte islenmeyen bir komut adi
    # yazilirsa o yetki hic uygulanmaz (sessiz bosluk).
    tablo_komutlari = re.findall(r'"([a-z0-9_]+)"\s*:\s*"(radar|gccdual)"',
                                 tablo)
    olc("tabloda 13 komut var", len(tablo_komutlari) == 13,
        f"{len(tablo_komutlari)} komut bulundu")
    hayali = [k for k, _ in tablo_komutlari
              if f'komut == "{k}"' not in su and f'"{k}"' not in su.replace(
                  tablo, "")]
    olc("tabloda hayali komut YOK", not hayali, f"islenmeyen: {hayali}")

    # Denetim IZIN_HARITASI KULLANIMINDAN once olmali; sonra olursa
    # yetkisiz komut once rol denetiminden gecip yan etki yapabilir.
    #
    # NOT: `IZIN_HARITASI` TANIMI dosyanin cok basinda (satir ~2960).
    # Onceki olcum tanim konumuyla karsilastiriyordu ve bu yuzden
    # dogru kodu KALDI diye isaretliyordu. Karsilastirma, komut
    # isleyicisindeki GERCEK KULLANIM (`self.IZIN_HARITASI.get`) ile
    # yapiliyor.
    m_cagri = re.search(r"await\s+self\._lisans_izni_var\(", su)
    m_kull = re.search(r"self\.IZIN_HARITASI\.get\(", su)
    olc("lisans denetimi komut isleyicisinde cagriliyor",
        m_cagri is not None)
    olc("IZIN_HARITASI komut isleyicisinde kullaniliyor",
        m_kull is not None)
    if m_cagri and m_kull:
        olc("lisans denetimi IZIN_HARITASI kullanimindan ONCE",
            m_cagri.start() < m_kull.start(),
            f"lisans@{m_cagri.start()} izin@{m_kull.start()} — yetkisiz "
            f"komut rol denetiminden gecip yan etki yapabilir")

    # Lisanssiz kurulumda sunucu da sinir uygulamamali
    m5 = re.search(r"def _lisans_izni_var\([^)]*\):(.*?)(?=\n    def |\ndef |\Z)",
                   su, flags=re.S)
    g5 = m5.group(1) if m5 else ""
    olc("lisanssiz kurulumda sunucu ust sinir UYGULAMIYOR",
        re.search(r"lisansli", g5) is not None
        and re.search(r"return\s+True", g5) is not None,
        "lisanssiz kurulumda komutlar reddedilir!")

    # Ret bildirimi dogru sozlesmeyle: duz {"tip":"uyari"} SESSIZCE duser
    olc("ret bildirimi _uyari_gonder ile yapiliyor",
        "_uyari_gonder" in g5 or re.search(
            r"_lisans_izni_var.*?_uyari_gonder", su, flags=re.S) is not None,
        "duz tip:uyari arayuzde sessizce dusurulur")

    # ================================================================
    # 5b) DAVRANIS OLCUMU — desen aramak YETMEZ
    # ================================================================
    # NEDEN: kontrol deneyi, `if False and not await self._lisans_izni_var(...)`
    # enjeksiyonunun KACTIGINI gosterdi. Desen hala kaynakta oldugu icin
    # metin olcumu geciyordu, oysa denetim etkisiz haldeydi.
    #
    # Bu yuzden `_lisans_izni_var` GERCEKTEN cagriliyor ve `_komut_isle`
    # yetkisiz komutu gercekten dusuruyor mu olculuyor.
    print("\n[5b] davranis olcumu — gercek cagri")
    davranis_olc()

    # ================================================================
    # 6) lisans.py sozlesmesi
    # ================================================================
    print("\n[6] goktungu/lisans.py — sozlesme")
    li = oku("goktungu", "lisans.py")
    olc("yetki_ozeti lisansli alanini donuyor",
        re.search(r'"lisansli"\s*:', li) is not None)
    olc("lisans yokken kaynak merkez",
        re.search(r'"kaynak"\s*:\s*"merkez"', li) is not None)
    olc("lisans varken kaynak yerel_lisans",
        re.search(r'"kaynak"\s*:\s*"yerel_lisans"', li) is not None)
    olc("kapali devre: ag cagrisi YOK",
        not re.search(r"\b(urllib|requests|http\.client|socket)\b", li))

    rapor()


def rapor():
    print("-" * 66)
    print(f" SONUC: {len(gecti)} gecti / {len(kaldi)} kaldi")
    for k in kaldi:
        print(f"   KALDI: {k}")
    print("=" * 66)
    sys.exit(1 if kaldi else 0)


if __name__ == "__main__":
    main()
