#!/usr/bin/env python3
"""v2.4.51 — Goc motorunu GERCEK PostgreSQL uzerinde olcer.

Olculen davranislar:
- Bos veritabaninda goc GEREKLI der ve adimlari uygular
- Ikinci kosumda goc GEREKMEZ der (idempotent)
- Ilerleme geri cagirmasi ARTAN yuzde ve BOS OLMAYAN ileti verir
- Defter kaydi tutulur (adim, sure, durum)
- Basarisiz adim goc'u DURDURUR ve sonraki adimlar CALISMAZ
- Sema surumu kaydedilir
"""
import os
import sys

KOK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(KOK, "goktungu"))

from goktungu import pg                                    # noqa: E402
from goktungu import veritabani as vt                      # noqa: E402
from goktungu import goc                                   # noqa: E402

G = K = 0
BASARISIZ = []


def olc(ad, kosul, detay=""):
    global G, K
    if kosul:
        G += 1
        print(f"  [GECTI] {ad}")
    else:
        K += 1
        BASARISIZ.append(ad)
        print(f"  [KALDI] {ad}" + (f" -> {detay}" if detay else ""))


def bolum(ad):
    print(f"\n=== {ad} ===")


pg.yapilandir(host="127.0.0.1", port=5432, veritabani="goktungu",
              kullanici="goktungu", sifre="goktungu2451")


def semayi_sifirla():
    con = pg.baglanti()
    with con as c:
        c.execute("DROP SCHEMA public CASCADE")
        c.execute("CREATE SCHEMA public")
    pg._CITEXT_VAR = None


bolum("bos veritabani: goc GEREKLI")
semayi_sifirla()
m = goc.GocMotoru()
olc("gerekli_mi() True (bos db)", m.gerekli_mi() is True)
olc("sema_surumu() 0 (bos db)", goc.sema_surumu() == 0,
    str(goc.sema_surumu()))
bekleyen = m.bekleyen_adimlar()
olc("bekleyen adim var", len(bekleyen) == len(goc.ADIMLAR),
    f"{len(bekleyen)}/{len(goc.ADIMLAR)}")

bolum("goc kosumu ve ilerleme bildirimi")
kayitlar = []


def ilerleme(yuzde, ileti, adim):
    kayitlar.append((yuzde, ileti, adim))


sonuc = m.calistir(ilerleme=ilerleme)
olc("calistir tamam=True", sonuc["tamam"] is True, str(sonuc.get("hata")))
olc("tum adimlar uygulandi",
    sonuc["uygulanan"] == len(goc.ADIMLAR),
    f"{sonuc['uygulanan']}/{len(goc.ADIMLAR)}")

olc("ilerleme cagrildi", len(kayitlar) >= len(goc.ADIMLAR),
    f"{len(kayitlar)} cagri")
yuzdeler = [k[0] for k in kayitlar]
olc("yuzde ARTAN (azalma yok)",
    all(yuzdeler[i] <= yuzdeler[i + 1] for i in range(len(yuzdeler) - 1)),
    str(yuzdeler))
olc("son yuzde 100", yuzdeler and abs(yuzdeler[-1] - 100) < 0.01,
    str(yuzdeler[-1] if yuzdeler else None))
olc("iletiler BOS DEGIL", all(str(k[1]).strip() for k in kayitlar),
    str([k[1] for k in kayitlar if not str(k[1]).strip()]))
# Kullanici "neyin surdugunu" gormeli: adim aciklamalari gorunmeli
iletiler = " | ".join(k[1] for k in kayitlar)
olc("ileti 'Tablolar' gecer", "Tablo" in iletiler, iletiler[:200])

bolum("idempotentlik: ikinci kosum")
olc("gerekli_mi() False (goc sonrasi)", m.gerekli_mi() is False)
olc("sema_surumu() = SEMA_SURUMU",
    goc.sema_surumu() == goc.SEMA_SURUMU,
    f"{goc.sema_surumu()} vs {goc.SEMA_SURUMU}")
k2 = []
s2 = m.calistir(ilerleme=lambda y, i, a: k2.append((y, i, a)))
olc("ikinci kosum tamam", s2["tamam"] is True)
olc("ikinci kosumda 0 adim", s2["uygulanan"] == 0, str(s2["uygulanan"]))

bolum("defter kaydi")
d = goc.defter_oku()
olc("defterde kayit var", len(d) == len(goc.ADIMLAR),
    f"{len(d)}/{len(goc.ADIMLAR)}")
if d:
    olc("tum kayitlar 'tamam'",
        all(r["durum"] == "tamam" for r in d),
        str([(r["adim"], r["durum"]) for r in d]))
    olc("sure_ms kaydedildi",
        all(isinstance(r["sure_ms"], int) for r in d))
    adlar = {r["adim"] for r in d}
    olc("beklenen adimlar defterde",
        adlar == {a.ad for a in goc.ADIMLAR},
        str(adlar))

bolum("durum() sihirbaz ozeti")
dur = m.durum()
olc("durum kip bildirir", dur["kip"] == "postgresql", str(dur["kip"]))
olc("durum guncel=True", dur["guncel"] is True)
olc("durum bekleyen bos", dur["bekleyen"] == [], str(dur["bekleyen"]))
olc("durum hedef_surum dogru", dur["hedef_surum"] == goc.SEMA_SURUMU)

bolum("basarisiz adim goc'u DURDURUR")
semayi_sifirla()


def _patlayan(con, bildir):
    raise RuntimeError("kasitli hata")


asil = list(goc.ADIMLAR)
try:
    goc.ADIMLAR = [
        goc.Adim("dene_ilk", 2451, "Ilk adim", asil[0].islev),
        goc.Adim("dene_patlar", 2451, "Patlayan adim", _patlayan),
        goc.Adim("dene_son", 2451, "Son adim",
                 lambda c, b: "calismamali"),
    ]
    m2 = goc.GocMotoru()
    s3 = m2.calistir()
    olc("basarisiz goc tamam=False", s3["tamam"] is False)
    olc("hata bildirilir", "kasitli hata" in s3["hata"], s3["hata"])
    olc("SONRAKI adim CALISMADI",
        not any(a["ad"] == "dene_son" for a in s3["adimlar"]),
        str([a["ad"] for a in s3["adimlar"]]))
    d2 = goc.defter_oku()
    hatali = [r for r in d2 if r["adim"] == "dene_patlar"]
    olc("hatali adim deftere 'hata' olarak yazildi",
        hatali and hatali[0]["durum"] == "hata",
        str([(r["adim"], r["durum"]) for r in d2]))
    olc("hatali adim UYGULANDI sayilmaz",
        not goc.adim_uygulandi_mi("dene_patlar"))
    # Sema surumu yazilmamali (goc tamamlanmadi)
    olc("basarisiz goc'ta sema surumu YAZILMAZ",
        goc.sema_surumu() != goc.SEMA_SURUMU,
        str(goc.sema_surumu()))
finally:
    goc.ADIMLAR = asil

print(f"\n{'=' * 52}")
print(f"SONUC: {G} gecti, {K} kaldi")
if BASARISIZ:
    print("\nBASARISIZ:")
    for b in BASARISIZ:
        print(f"  - {b}")
pg.tum_baglantilari_kapat()
sys.exit(1 if K else 0)
