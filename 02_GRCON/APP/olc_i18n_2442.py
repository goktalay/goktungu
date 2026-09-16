#!/usr/bin/env python3
"""v2.4.42 i18n TR/EN esitligini ve KULLANILAN anahtarlarin varligini olcer.

Iki ayri sessiz kusur vardir:
  1. Bir anahtarin EN karsiligi yoksa arayuz Ingilizceye alindiginda
     etiket Turkce kalir ya da bos gorunur.
  2. Kodda `t.birSey` cagrilir ama sozlukte HIC tanimli degilse etiket
     bos gorunur veya yedek metne duser.

Bu yuzden anahtar listesi ELLE yazilmaz: v2.4.42 dosyalarindan
`t.xxx` kullanimlari cikarilip sozlukle karsilastirilir.
"""
import re
import sys

I18N = "js/i18n.js"

# v2.4.42 ile gelen veya degisen on yuz dosyalari.
DOSYALAR = [
    "js/ucus_grafik.js",
    "js/kayitli_dronlar.js",
    "js/home_ikon.js",
    "js/harita_menu.js",
    "js/ucus_rapor.js",
    "js/gecmis.js",
]

# Bu oneklerle baslayan anahtarlar v2.4.42 kapsamindadir.
ONEKLER = ("ug", "kd", "gc", "ur", "hm", "dkHome", "home")


def blok(metin: str, dil: str) -> str:
    """DILLER icindeki tek bir dil blogunu suslu parantez sayarak ayirir."""
    im = re.search(r"^\s{2}" + dil + r":\s*\{", metin, re.M)
    if not im:
        raise SystemExit("dil blogu bulunamadi: " + dil)
    bas = metin.index("{", im.start())
    derinlik = 0
    for i in range(bas, len(metin)):
        if metin[i] == "{":
            derinlik += 1
        elif metin[i] == "}":
            derinlik -= 1
            if derinlik == 0:
                return metin[bas + 1:i]
    raise SystemExit("dil blogu kapanmadi: " + dil)


def anahtarlar(govde: str) -> set:
    """Yalniz ilk seviye anahtarlari alir (girinti 4 bosluk)."""
    return set(re.findall(r"^    (\w+)\s*:", govde, re.M))


def kullanilanlar() -> set:
    """Kaynak dosyalardan t.xxx / _t.xxx kullanimlarini cikarir."""
    bulunan = set()
    for yol in DOSYALAR:
        try:
            metin = open(yol, encoding="utf-8").read()
        except OSError:
            continue
        for ad in re.findall(r"\b_?t\.(\w+)", metin):
            if ad.startswith(ONEKLER):
                bulunan.add(ad)
    return bulunan


def main() -> int:
    metin = open(I18N, encoding="utf-8").read()
    tr = anahtarlar(blok(metin, "TR"))
    en = anahtarlar(blok(metin, "EN"))
    print("TR anahtar : %d" % len(tr))
    print("EN anahtar : %d" % len(en))

    yalniz_tr = sorted(tr - en)
    yalniz_en = sorted(en - tr)
    print("yalniz TR  : %d" % len(yalniz_tr))
    print("yalniz EN  : %d" % len(yalniz_en))
    if yalniz_tr:
        print("  EN karsiligi EKSIK: " + ", ".join(yalniz_tr[:40]))
    if yalniz_en:
        print("  TR karsiligi EKSIK: " + ", ".join(yalniz_en[:40]))

    kul = kullanilanlar()
    eksik_tr = sorted(a for a in kul if a not in tr)
    eksik_en = sorted(a for a in kul if a not in en)
    print("kullanilan v2.4.42 anahtari : %d" % len(kul))
    if eksik_tr:
        print("  TR'de TANIMSIZ: " + ", ".join(eksik_tr))
    if eksik_en:
        print("  EN'de TANIMSIZ: " + ", ".join(eksik_en))
    if not eksik_tr and not eksik_en:
        print("  hepsi TR ve EN'de tanimli")

    tamam = not yalniz_tr and not yalniz_en and not eksik_tr and not eksik_en
    print("SONUC: " + ("TAMAM" if tamam else "EKSIK VAR"))
    return 0 if tamam else 1


if __name__ == "__main__":
    sys.exit(main())
