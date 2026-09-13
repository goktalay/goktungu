#!/usr/bin/env python3
"""i18n.js TR/EN anahtar dengesini olcer."""
import io, os, re, sys

# Betik iki yerden de kostrulur:
#   a) gelistirme kokunden -> goktungu/js/i18n.js
#   b) KURULUM kokunden    -> js/i18n.js
# Yol sabit yazilirsa kullanicinin kendi kurulumunda dosya bulunamaz ve
# olcum hic yapilamaz. Bu yuzden aday yollar sirayla denenir.
if len(sys.argv) > 1:
    adaylar = [sys.argv[1]]
else:
    kok = os.path.dirname(os.path.abspath(__file__))
    adaylar = [
        os.path.join(kok, "js", "i18n.js"),           # kurulum koku
        os.path.join(kok, "goktungu", "js", "i18n.js"),  # gelistirme koku
        "js/i18n.js",
        "goktungu/js/i18n.js",
    ]
yol = None
for _a in adaylar:
    if os.path.exists(_a):
        yol = _a
        break
if yol is None:
    print("HATA: i18n.js bulunamadi. Denenen yollar:")
    for _a in adaylar:
        print("  " + _a)
    sys.exit(2)
print("olculen dosya: %s" % yol)
m = io.open(yol, encoding="utf-8").read()
i_tr = m.index("\n  TR: {")
i_en = m.index("\n  EN: {")
tr = m[i_tr:i_en]
en = m[i_en:]
# Anahtarlar hem "tirnakli" hem tirnaksiz yazilmis olabilir
pat = re.compile(r'^\s{4}"?([A-Za-z0-9_]+)"?\s*:', re.M)
a = set(pat.findall(tr))
b = set(pat.findall(en))
print("TR: %d  EN: %d" % (len(a), len(b)))
e1 = sorted(a - b); e2 = sorted(b - a)
print("TR'de olup EN'de olmayan (%d): %s" % (len(e1), e1[:15]))
print("EN'de olup TR'de olmayan (%d): %s" % (len(e2), e2[:15]))
print("DENGE: %s" % ("TAMAM" if a == b else "BOZUK"))
sys.exit(0 if a == b else 1)
