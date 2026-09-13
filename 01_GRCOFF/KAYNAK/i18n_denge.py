# -*- coding: utf-8 -*-
"""i18n.js icindeki TR ve EN sozluklerinin anahtar dengesini olcer.

Anahtarlar iki bicimde yazilmis: `"anahtar": "deger"` ve `anahtar: "deger"`.
Ikisi de sayilmalidir; yoksa denge olcumu yanlis olur.
"""
import io
import re
import sys

YOL = "js/i18n.js"
DESEN = re.compile(r'^\s*(?:"([A-Za-z0-9_]+)"|([A-Za-z0-9_]+))\s*:')


def bloklar(satirlar):
    """TR ve EN bloklarinin (baslangic, bitis) satir indekslerini bulur."""
    tr_bas = en_bas = son = None
    for i, l in enumerate(satirlar):
        if re.match(r'^\s{2}TR:\s*\{', l):
            tr_bas = i
        elif re.match(r'^\s{2}EN:\s*\{', l):
            en_bas = i
        elif re.match(r'^\};', l):
            son = i
    if tr_bas is None or en_bas is None or son is None:
        raise SystemExit("i18n.js yapisi taninamadi")
    return (tr_bas + 1, en_bas), (en_bas + 1, son)


def anahtarlar(satirlar, aralik):
    bas, bit = aralik
    cikti = []
    for l in satirlar[bas:bit]:
        m = DESEN.match(l)
        if m:
            cikti.append(m.group(1) or m.group(2))
    return cikti


def main():
    satirlar = io.open(YOL, encoding="utf-8").read().splitlines()
    tr_a, en_a = bloklar(satirlar)
    tr = anahtarlar(satirlar, tr_a)
    en = anahtarlar(satirlar, en_a)
    print(f"TR blok: satir {tr_a[0]+1}-{tr_a[1]}  anahtar: {len(tr)}")
    print(f"EN blok: satir {en_a[0]+1}-{en_a[1]}  anahtar: {len(en)}")
    trs, ens = set(tr), set(en)
    eksik_en = sorted(trs - ens)
    eksik_tr = sorted(ens - trs)
    print(f"TR'de olup EN'de OLMAYAN: {len(eksik_en)}")
    for a in eksik_en[:40]:
        print("  -", a)
    print(f"EN'de olup TR'de OLMAYAN: {len(eksik_tr)}")
    for a in eksik_tr[:40]:
        print("  -", a)
    yinelenen_tr = [a for a in trs if tr.count(a) > 1]
    yinelenen_en = [a for a in ens if en.count(a) > 1]
    if yinelenen_tr:
        print("TR yinelenen:", sorted(yinelenen_tr)[:20])
    if yinelenen_en:
        print("EN yinelenen:", sorted(yinelenen_en)[:20])
    dengeli = not eksik_en and not eksik_tr
    print("DENGE:", "TAMAM" if dengeli else "BOZUK")
    return 0 if dengeli else 1


if __name__ == "__main__":
    sys.exit(main())
