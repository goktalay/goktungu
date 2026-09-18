#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""v2.4.64 — Ucus kaydi sahipligi ve yetkilendirme sinavi.

KUSUR (kullanici bildirdi): "yeni olusturdugum pilotta ucus kayitlari
gorunuyor, gorunmemesi gerekiyor."

KULLANICI KURALI (BAGLAYICI): "takeoff'u kim verdiyse o ucusun sahibi
odur (COK ONEMLI)". Yalnizca Yonetici rolu tum ucuslari gorebilir.

MIMARI (olculerek dogrulandi, varsayim degil):
  - Sahiplik kaynagi : veritabani.ucus_sahibi_detay() -> kalkis_kontrolleri
  - Suzme            : veritabani.ucus_listesi(eposta, yonetici)
  - Erisim denetimi  : ucus_gecmisi.sahip_mi(ucus_id, eposta, yonetici)
  - Denetim NOKTASI  : sunucu.py komut isleyicileri (ucus_oku / ucus_sil)
                       cagriDAN ONCE denetler; ucus_oku()/ucus_sil()
                       fonksiyonlarinin KENDISI kimlik almaz.
                       Bu gecerli bir tasarim: denetim tek kapida
                       (WS komut sinirinda) toplanmistir.

Bu sinav bu mimariyi oldugu gibi olcer. Onceki surumu ucus_oku()
imzasinda kimlik ariyordu ve 6 yanlis pozitif uretti.
"""
import ast
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent
gecti = 0
kaldi = 0


def olc(ad, kosul, ayrinti=""):
    global gecti, kaldi
    if kosul:
        gecti += 1
        print(f"  GECTI  {ad}")
    else:
        kaldi += 1
        print(f"  KALDI  {ad}" + (f" -> {ayrinti}" if ayrinti else ""))


def kaynak(yol):
    p = KOK / yol
    if not p.exists():
        return "", None
    metin = p.read_text(encoding="utf-8")
    try:
        agac = ast.parse(metin)
    except SyntaxError as e:
        print(f"  SOZDIZIMI HATASI {yol}: {e}")
        return metin, None
    return metin, agac


def fonksiyon_bul(agac, ad):
    for d in ast.walk(agac):
        if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef)) and d.name == ad:
            return d
    return None


print("=" * 68)
print("v2.4.64 — UCUS SAHIPLIGI VE YETKILENDIRME SINAVI")
print("=" * 68)

# ---------------------------------------------------------------- 1
print("\n[1] veritabani.py — sahiplik kaynagi (takeoff kaydi)")
vt_metin, vt_agac = kaynak("goktungu/veritabani.py")
olc("veritabani.py okunabildi", bool(vt_agac))

if vt_agac:
    for ad in ("ucus_sahibi", "ucus_sahibi_detay"):
        olc(f"{ad}() tanimli", fonksiyon_bul(vt_agac, ad) is not None)

    detay = fonksiyon_bul(vt_agac, "ucus_sahibi_detay")
    if detay:
        govde = ast.unparse(detay)
        olc("sahiplik kalkis_kontrolleri'nden cozuluyor",
            "kalkis_kontrolleri" in govde,
            "KURAL IHLALI: sahip takeoff kaydindan cozulmuyor")
        olc("takeoff_gonderildi kosulu var",
            "takeoff_gonderildi" in govde,
            "takeoff VERMEYEN kalkis kaydi da sahip sayilir")
        olc("pilot_eposta okunuyor", "pilot_eposta" in govde)

    sarmal = fonksiyon_bul(vt_agac, "ucus_sahibi")
    if sarmal:
        olc("ucus_sahibi() detay fonksiyonuna delege ediyor",
            "ucus_sahibi_detay" in ast.unparse(sarmal),
            "ikinci bir sahiplik sorgusu olusmus")

# ---------------------------------------------------------------- 2
print("\n[2] veritabani.py — ucus_listesi() suzmesi")
if vt_agac:
    lst = fonksiyon_bul(vt_agac, "ucus_listesi")
    olc("ucus_listesi() tanimli", lst is not None)
    if lst:
        arglar = [a.arg for a in lst.args.args]
        olc("eposta ve yonetici parametreleri var",
            "eposta" in arglar and "yonetici" in arglar,
            f"yonetici ayrimi yok (arglar: {arglar})")

        kod_metni = "\n".join(ast.unparse(d) for d in lst.body
                              if not (isinstance(d, ast.Expr)
                                      and isinstance(d.value, ast.Constant)))
        olc("suzme ortak sahiplik kaynagina bagli",
            "ucus_sahibi_detay" in kod_metni or "ucus_sahibi" in kod_metni,
            "suzme kendi kuralini yaziyor")

# ---------------------------------------------------------------- 3
print("\n[3] ucus_gecmisi.py — sahip_mi() erisim denetimi")
ug_metin, ug_agac = kaynak("goktungu/ucus_gecmisi.py")
olc("ucus_gecmisi.py okunabildi", bool(ug_agac))

if ug_agac:
    sm = fonksiyon_bul(ug_agac, "sahip_mi")
    olc("sahip_mi() tanimli", sm is not None,
        "erisim denetimi yardimcisi yok")
    if sm:
        arglar = [a.arg for a in sm.args.args]
        olc("sahip_mi(ucus_id, eposta, yonetici) imzasi",
            "ucus_id" in arglar and "eposta" in arglar
            and "yonetici" in arglar,
            f"imza beklenenden farkli: {arglar}")
        govde = ast.unparse(sm)
        olc("sahip_mi ortak sahiplik kaynagini kullaniyor",
            "ucus_sahibi" in govde,
            "ikinci bir sahiplik kurali olusmus")
        olc("sahip_mi (izin, sebep) donduruyor",
            "return" in govde and "," in govde,
            "sebep bildirilmiyor -> reddedilme gerekcesi kayboluyor")

    olc("ucus_gecmisi.py kendi kalkis sorgusu yazmiyor",
        "kalkis_kontrolleri" not in (ug_metin or ""),
        "ikinci sahiplik sorgusu -> kurallar ayrisabilir")

# ---------------------------------------------------------------- 4
print("\n[4] sunucu.py — denetim komut sinirinda uygulaniyor")
sn_metin, sn_agac = kaynak("goktungu/sunucu.py")
olc("sunucu.py okunabildi", bool(sn_agac))

if sn_metin:
    for komut, cagri in (("ucus_oku", "ucus_oku"), ("ucus_sil", "ucus_sil")):
        idx = sn_metin.find(f'komut == "{komut}"')
        olc(f"{komut} komut isleyicisi var", idx > 0)
        if idx <= 0:
            continue
        pencere = sn_metin[idx:idx + 2000]

        olc(f"{komut}: sahip_mi denetimi var",
            "sahip_mi" in pencere,
            f"{komut} yetkilendirme yapmiyor -> baskasinin ucusuna erisim")
        olc(f"{komut}: pilot kimligi sunucudan aliniyor",
            "_pilot_bilgi" in pencere,
            f"{komut} kimligi istemciden aliyor -> taklit edilebilir")
        olc(f"{komut}: yonetici rolu geciriliyor",
            'rol") == "yonetici"' in pencere or "rol') == 'yonetici'" in pencere,
            f"{komut} yonetici ayrimi yapmiyor")

        # KRITIK: denetim, veri cagrisindan ONCE gelmeli
        i_denetim = pencere.find("sahip_mi")
        i_cagri = pencere.find(f".{cagri}(")
        olc(f"{komut}: denetim veri cagrisindan ONCE",
            i_denetim > 0 and i_cagri > 0 and i_denetim < i_cagri,
            f"{komut} once veriyi aliyor, sonra denetliyor")

        # Reddedilme sessiz olmamali
        olc(f"{komut}: reddedilme kullaniciya bildiriliyor",
            "_hata_bildir" in pencere,
            f"{komut} sessizce reddediyor -> kullanici sebebini bilmiyor")

# ---------------------------------------------------------------- 5
print("\n[5] Liste suzmesi cagri yerinde kimlik geciriyor")
# ucus_listesi() cagrilari ucus_gecmisi.py'de (sunucu.py'de degil).
# ucus_gecmisi.dron_listesi() disa donuk yoldur ve kimlik gecirmeli.
if ug_agac:
    dl = fonksiyon_bul(ug_agac, "dron_listesi")
    olc("dron_listesi() tanimli", dl is not None)
    if dl:
        arglar = [a.arg for a in dl.args.args]
        olc("dron_listesi kimlik parametresi aliyor",
            any(x in arglar for x in ("eposta", "yonetici")),
            f"disa donuk liste kimlik almiyor (arglar: {arglar})")
        govde = ast.unparse(dl)
        olc("dron_listesi suzmeyi ucus_listesi'ne geciriyor",
            "eposta" in govde and "yonetici" in govde,
            "suzme atlanmis -> tum dronlar herkese gorunur")
        olc("dron_listesi sabit yonetici=True kullanmiyor",
            "yonetici=True" not in govde,
            "disa donuk yol suzmeyi atliyor")

# ---------------------------------------------------------------- 6
# DAVRANIS OLCUMU (dize taramasi DEGIL)
#
# Neden gerekli: kontrol deneyi (olc_kontrol_deneyi.py) dize tabanli
# olcumlerin iki kritik kusuru KACIRDIGINI kanitladi:
#   A) 'if not yonetici:' -> 'if not yonetici and False:' yapilinca
#      dize hala mevcut oldugu icin sinav gecti diyordu.
#   C) takeoff siralamasi bozulunca yine gecti diyordu.
# Cozum: gercek fonksiyonlari sahte veritabaniyla CALISTIR ve donen
# kayitlari olc. Bu, davranis degistiginde kaciramaz.
print("\n[6] DAVRANIS: gercek fonksiyonlar sahte veriyle kosuluyor")

sys.path.insert(0, str(KOK))
try:
    from goktungu import veritabani as vt
except Exception as e:                                  # pragma: no cover
    olc("veritabani modulu ice aktarilabildi", False, f"{e}")
    vt = None
else:
    olc("veritabani modulu ice aktarilabildi", True)


class SahteSatir(dict):
    """sqlite3.Row gibi hem indeks hem anahtar ile okunabilen satir."""

    def __getitem__(self, k):
        if isinstance(k, int):
            return list(self.values())[k]
        return dict.__getitem__(self, k)


class SahteImlec:
    def __init__(self, satirlar):
        self._s = satirlar

    def fetchone(self):
        return self._s[0] if self._s else None

    def fetchall(self):
        return self._s


class SahteBaglanti:
    """Yalnizca kalkis_kontrolleri sorgusuna yanit veren sahte baglanti.

    Gercek SQL'i taklit etmez; siralama kuralini PYTHON'da uygular ve
    boylece 'ORDER BY takeoff_gonderildi DESC, ts DESC' ifadesinin
    kaynakta VAR OLDUGUNU degil, sonucu ETKILEDIGINI olcer.
    """

    def __init__(self, kayitlar):
        self.kayitlar = kayitlar
        self.son_sql = ""

    def execute(self, sql, arg=()):
        self.son_sql = " ".join(sql.split())
        if "kalkis_kontrolleri" not in sql:
            return SahteImlec([])
        dron_id, ust, alt = arg[0], arg[1], arg[2]
        uygun = [k for k in self.kayitlar
                 if k["dron_id"] == dron_id
                 and str(k["pilot_eposta"]).strip() != ""
                 and alt <= k["ts"] <= ust]

        # ORDER BY'i KAYNAKTAN ayristir (sabit dize aramaz).
        #
        # Neden boyle: onceki surum "ORDER BY takeoff_gonderildi DESC"
        # dizesini ariyordu. Kontrol deneyi bu dizeyi bozdugunda sahte
        # baglanti onu taniyamayip yedek dala dusuyor ve TESADUFEN dogru
        # sonuc veriyordu -> kusur kaciyordu. Artik ORDER BY'daki alan
        # adlari sirayla okunur; bilinmeyen alan adi sessizce yok
        # sayilmaz, siralama o alan uzerinden yapilamadigi icin sonuc
        # gercekten degisir.
        s = self.son_sql
        anahtarlar = []
        if "ORDER BY" in s:
            kisim = s.split("ORDER BY", 1)[1]
            for parca in kisim.split("LIMIT")[0].split(","):
                p = parca.strip().split()
                if not p:
                    continue
                alan = p[0]
                tersine = len(p) > 1 and p[1].upper() == "DESC"
                anahtarlar.append((alan, tersine))

        # Siralamayi sondan basa uygula (kararli siralama zinciri).
        for alan, tersine in reversed(anahtarlar):
            if not uygun or alan not in uygun[0]:
                # Kaynakta olmayan alan: siralanamaz. Sessizce atlamak
                # kusuru gizler, bu yuzden isaretle.
                self.bilinmeyen_alan = alan
                continue
            uygun.sort(key=lambda k: k[alan], reverse=tersine)

        return SahteImlec([SahteSatir(k) for k in uygun[:1]])


if vt is not None:
    # --- C) SAHIPLIK: takeoff VEREN pilot kazanmali -------------------
    # Iki kalkis kaydi: Ayse takeoff VERMEDI ama DAHA YENI (ts buyuk),
    # Veli takeoff VERDI ama daha eski. Kural: sahip VELI olmali.
    # ONEMLI: sahte veri anahtari SABIT yazilmaz. Kaynaktaki SQL hangi
    # alan adini kullaniyorsa sahte kayitlar O ADI tasir. Aksi halde
    # kaynakta alan adi degistiginde (or. takeoff_gonderildi ->
    # takeoff_ZZZ_yok) sahte veri eski adi tasidigi icin siralama
    # sessizce atlanir, LIMIT 1 tesadufen dogru kaydi getirir ve
    # kusur olcumden KACAR. Kontrol deneyi bu tuzagi ortaya cikardi.
    _sahip_sql = ""
    _sd = fonksiyon_bul(vt_agac, "ucus_sahibi_detay") if vt_agac else None
    if _sd:
        for _s in ast.walk(_sd):
            if isinstance(_s, ast.Constant) and isinstance(_s.value, str):
                if "kalkis_kontrolleri" in _s.value:
                    _sahip_sql = " ".join(_s.value.split())
                    break
    # ORDER BY'daki BIRINCI alan adini kaynaktan oku.
    _oncelik_alan = "takeoff_gonderildi"
    if "ORDER BY" in _sahip_sql:
        _ilk = _sahip_sql.split("ORDER BY", 1)[1].split(",")[0].strip()
        _p = _ilk.split()
        if _p:
            _oncelik_alan = _p[0]
    olc("sahiplik SQL'i kaynaktan okundu", bool(_sahip_sql),
        "ucus_sahibi_detay icinde kalkis_kontrolleri sorgusu bulunamadi")

    # Iki kalkis kaydi: Ayse oncelik alaninda 0 ama DAHA YENI (ts buyuk),
    # Veli oncelik alaninda 1 ama daha eski. Kural: sahip VELI olmali.
    # ts DESC tek basina Ayse'yi getirir -> oncelik alani gercekten
    # kullanilmazsa olcum DUSER.
    kayitlar = [
        {"dron_id": 7, "pilot_eposta": "ayse@x.com", "pilot_isim": "Ayse",
         "ts": 1000.0, _oncelik_alan: 0},
        {"dron_id": 7, "pilot_eposta": "veli@x.com", "pilot_isim": "Veli",
         "ts": 900.0, _oncelik_alan: 1},
    ]
    con = SahteBaglanti(kayitlar)
    try:
        ep, isim = vt.ucus_sahibi_detay(7, 950.0, 1100.0, con=con)
    except Exception as e:
        olc("ucus_sahibi_detay calistirilabildi", False, f"{e}")
        ep, isim = None, None
    else:
        olc("ucus_sahibi_detay calistirilabildi", True)
        olc("DAVRANIS: sahip = takeoff'u VEREN pilot",
            ep == "veli@x.com",
            f"KURAL IHLALI: sahip '{ep}' dondu, 'veli@x.com' olmaliydi "
            f"(takeoff vermeyen daha yeni kayit kazandi)")
        olc("DAVRANIS: pilot ismi de cozuluyor", isim == "Veli",
            f"isim '{isim}' dondu")

    # Sahipsiz durum: takeoff kaydi hic yoksa bos donmeli
    bos_con = SahteBaglanti([])
    try:
        ep2, _ = vt.ucus_sahibi_detay(7, 950.0, 1100.0, con=bos_con)
        olc("DAVRANIS: kalkis kaydi yoksa ucus SAHIPSIZ", ep2 == "",
            f"sahipsiz olmaliydi, '{ep2}' dondu")
    except Exception as e:
        olc("DAVRANIS: kalkis kaydi yoksa ucus SAHIPSIZ", False, f"{e}")

    # --- A) SUZME: sahipsiz ucus pilota GORUNMEMELI -------------------
    # ucus_listesi()'nin suzme blogunu izole olcmek icin fonksiyonun
    # kendisini cagirmak yerine ayni kurali uygulayan kod yolunu
    # dogrudan sinariz: satirlar listesi hazir verilir.
    lst_dugum = fonksiyon_bul(vt_agac, "ucus_listesi") if vt_agac else None
    if lst_dugum:
        # Suzme blogunu kaynaktan cikarip ayri bir fonksiyon olarak kos.
        # Boylece 'and False' gibi bir bozulma DAVRANISI degistirir ve
        # olcum kacirmaz.
        suzgec_kaynak = (
            "def _suz(satirlar, eposta, yonetici):\n"
            "    if not yonetici:\n"
            "        e = (eposta or '').strip().lower()\n"
            "        if not e:\n"
            "            return []\n"
            "        satirlar = [u for u in satirlar\n"
            "                    if str(u.get('sahip_eposta', '')).strip()"
            ".lower() == e]\n"
            "    return satirlar\n")
        # Kaynaktaki GERCEK blogu al (taklit degil): son 'if not yonetici'
        # blogunu ve return'u ayikla.
        govde_satirlari = ast.unparse(lst_dugum).splitlines()
        idx = next((i for i, s in enumerate(govde_satirlari)
                    if s.strip().startswith("if not yonetici")), -1)
        olc("suzme blogu kaynakta bulundu", idx >= 0,
            "yonetici ayrimi yapan blok yok")
        if idx >= 0:
            blok = govde_satirlari[idx:]
            govde = "\n".join("    " + s for s in blok)
            kod = ("def _suz_gercek(satirlar, eposta, yonetici):\n"
                   + govde + "\n")
            alan = {}
            try:
                exec(compile(kod, "<suzme>", "exec"), alan)
                _suz = alan["_suz_gercek"]
            except Exception as e:
                olc("suzme blogu calistirilabildi", False, f"{e}")
                _suz = None
            else:
                olc("suzme blogu calistirilabildi", True)

            if _suz:
                satirlar = [
                    {"id": 1, "sahip_eposta": "veli@x.com"},   # Veli'nin
                    {"id": 2, "sahip_eposta": ""},             # SAHIPSIZ
                    {"id": 3, "sahip_eposta": "ayse@x.com"},   # Ayse'nin
                ]
                try:
                    veli = _suz(list(satirlar), "veli@x.com", False)
                    yon = _suz(list(satirlar), "admin@x.com", True)
                    kimliksiz = _suz(list(satirlar), "", False)
                except Exception as e:
                    olc("DAVRANIS: suzme kosuldu", False, f"{e}")
                else:
                    olc("DAVRANIS: suzme kosuldu", True)
                    kimlikler = sorted(u["id"] for u in veli)
                    olc("DAVRANIS: pilot YALNIZ kendi ucusunu goruyor",
                        kimlikler == [1],
                        f"pilot {kimlikler} gordu, [1] olmaliydi")
                    olc("DAVRANIS: SAHIPSIZ ucus pilota GORUNMUYOR",
                        not any(u["id"] == 2 for u in veli),
                        "KRITIK: sahipsiz ucus pilota gorunuyor "
                        "(kullanicinin bildirdigi kusur)")
                    olc("DAVRANIS: baskasinin ucusu GORUNMUYOR",
                        not any(u["id"] == 3 for u in veli),
                        "KRITIK: baska pilotun ucusu gorunuyor")
                    olc("DAVRANIS: yonetici TUM ucuslari goruyor",
                        sorted(u["id"] for u in yon) == [1, 2, 3],
                        f"yonetici {[u['id'] for u in yon]} gordu")
                    olc("DAVRANIS: kimliksiz istek hicbir kayit almiyor",
                        kimliksiz == [],
                        "kimlik yoksa kayit donmemeli")

print("\n" + "=" * 68)
print(f"SONUC: {gecti} gecti, {kaldi} kaldi")
print("=" * 68)
sys.exit(1 if kaldi else 0)
sys.exit(0 if kaldi == 0 else 1)
