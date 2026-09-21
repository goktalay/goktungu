#!/usr/bin/env python3.11
"""Turkbey kurt ikonundan (gece/gunduz) tum urun ikonlarini uretir (PIL).

Kaynak: 01_GRCOFF/KAYNAK/varliklar/marka/turkbey_ikon_{gece,gunduz}_1024.png
(896x967 tasarim dosyasindan golgesiz kirpilip 895x895 kare tuvale ortalanmis,
1024'e olceklenmis). Hedefler: GRCOFF/GRCON (logo.png=gece, logo_acik.png=gunduz,
pwa, varliklar/hicolor, goktungu.ico, favicon), kopru varliklar, Android
mipmap/round/adaptive (05_BRDAND, 06_BRDDJI), web img/favicon_*.

Kullanim: python3.11 ikon_uret_pil.py [--src /root/grcoff_2528_build/src]
"""
import os, re, sys, glob
from PIL import Image, ImageDraw

REPO = "/root/goktungu_github"
SRC = sys.argv[sys.argv.index("--src") + 1] if "--src" in sys.argv else REPO + "/01_GRCOFF/KAYNAK"
M = REPO + "/01_GRCOFF/KAYNAK/varliklar/marka/"
gece = Image.open(M + "turkbey_ikon_gece_1024.png").convert("RGBA")
gunduz = Image.open(M + "turkbey_ikon_gunduz_1024.png").convert("RGBA")
# 2026-09-21: Turkbey amblemi (kirmizi kalkan-kurt) SEFFAF zeminlidir; gece/gunduz
# ayrimi yoktur. logo.png/logo_acik.png seffaf amblem olur (her temada kirmizi
# gorunur). maskable/Android/favicon zemini BEYAZ (kurumsal): kirmizi amblem
# beyaz uzerinde okunur. Kose pikselinden zemin okumak amblem kirmizisini
# verecegi icin (amblem gorunmez olurdu) zemin sabit beyazdir.
px = (255, 255, 255, 255)
ZEMIN = "#FFFFFF"


def kare(im, n):
    return im.resize((n, n), Image.LANCZOS)


def yaz(im, n, yol):
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    kare(im, n).save(yol)


def yuvarlak(im, n):
    k = kare(im, n)
    m = Image.new("L", (n, n), 0)
    ImageDraw.Draw(m).ellipse((0, 0, n - 1, n - 1), fill=255)
    o = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    o.paste(k, (0, 0), m)
    return o


def maskeli(im, n, oran=0.78):
    o = Image.new("RGBA", (n, n), px)
    ic = int(n * oran)
    k = kare(im, ic)
    o.paste(k, ((n - ic) // 2, (n - ic) // 2), k)
    return o


def onplan(im, n=432, oran=0.62):
    o = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ic = int(n * oran)
    k = kare(im, ic)
    o.paste(k, ((n - ic) // 2, (n - ic) // 2), k)
    return o


def ico(im, yol, boylar):
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    kare(im, max(boylar)).save(yol, format="ICO", sizes=[(b, b) for b in boylar])


def varliklar(V):
    yaz(gece, 640, V + "goktungu_kare.png")
    ico(gece, V + "goktungu.ico", [256, 128, 64, 48, 32, 24, 16])
    yaz(gece, 32, V + "favicon.png")
    ico(gece, V + "favicon.ico", [32, 16])
    for n in (16, 22, 24, 32, 48, 64, 128, 256, 512):
        yaz(gece, n, V + "hicolor/%dx%d/apps/goktungu-kopru.png" % (n, n))


S = SRC.rstrip("/") + "/"
gece.save(S + "logo.png"); gunduz.save(S + "logo_acik.png")
yaz(gece, 180, S + "pwa/apple-touch-icon.png"); yaz(gece, 192, S + "pwa/ikon-192.png"); yaz(gece, 512, S + "pwa/ikon-512.png")
maskeli(gece, 192).save(S + "pwa/ikon-maskable-192.png"); maskeli(gece, 512).save(S + "pwa/ikon-maskable-512.png")
varliklar(S + "varliklar/")
varliklar(REPO + "/03_BRDIMG/ORTAK_KOPRU_KAYNAGI/varliklar/")
for app in ("05_BRDAND", "06_BRDDJI"):
    R = REPO + "/%s/KAYNAK/app/src/main/res/" % app
    for d, n in (("mdpi", 48), ("hdpi", 72), ("xhdpi", 96), ("xxhdpi", 144), ("xxxhdpi", 192)):
        yaz(gece, n, R + "mipmap-%s/ic_launcher.png" % d)
        yuvarlak(gece, n).save(R + "mipmap-%s/ic_launcher_round.png" % d)
    onplan(gece).save(R + "drawable/ic_launcher_on.png")
    z = R + "drawable/ic_launcher_zemin.xml"
    if os.path.exists(z):
        s = open(z, encoding="utf-8").read()
        s2 = re.sub(r'android:color="#[0-9A-Fa-f]{6,8}"', 'android:color="%s"' % ZEMIN, s)
        open(z, "w", encoding="utf-8").write(s2)
for W in ("/opt/goktungu/merkez/web/img/", REPO + "/09_GRCWEB/KAYNAK/img/"):
    if os.path.isdir(W):
        yaz(gece, 32, W + "favicon_32.png"); yaz(gece, 180, W + "favicon_180.png"); yaz(gece, 512, W + "favicon_512.png")
print("ikonlar uretildi; zemin", ZEMIN)
