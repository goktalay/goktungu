# -*- coding: utf-8 -*-
"""Kurum logosu uclari (v2.4.53 Faz 4).

Kullanici talebi:
> "register sayfasinda logo yok. app uygulamasi bu kayitta ekledigi
>  logo ile acilacak"

Bu betik `mk_sunucu.py` dosyasina uc ekler:

  POST /api/firma/kayit          -> `logo` alanini (data URL) kabul eder
  GET  /api/genel/firma_logo     -> logoyu sunar (kimliksiz, onbellekli)
  POST /api/firma/logo           -> oturum acmis yonetici logoyu degistirir

TASARIM KARARI — logo neden veritabaninda DEGIL diskte:
`firmalar.logo_yol` kolonu semada ZATEN var (TEXT). Ikili veriyi
PostgreSQL'e bytea olarak koymak her giriste DB trafigi yaratir ve
HTTP onbellegi kullanilamaz. Dosya olarak `VERI_KOKU/varlik/logo/`
altina yazilir; `/varlik/` yolu statik sunucu tarafindan ZATEN
sunulmaktadir (mk_sunucu.py:366). Ancak dogrudan `/varlik/logo/...`
yolu firma_id'yi tahmin ederek baska kurumun logosunu cekmeye izin
verir; bu yuzden `/api/genel/firma_logo?firma_id=N` ucu kullanilir ve
dosya adina rastgele bir belirtec eklenir.
"""
import io
import os
import re
import sys

YOL = os.path.expanduser("~/merkez_calisma/mk_sunucu.py")

with io.open(YOL, "r", encoding="utf-8") as f:
    m = f.read()

ilk = m

# ======================================================================
# 1) Logo yardimcilari — dosyanin sonuna eklenir (uc tanimlarindan once
#    degil; @yol dekoratoru import sirasinda calisir, sira onemsizdir)
# ======================================================================
YARDIMCI = '''

# ======================================================================
# v2.4.53 Faz 4 — KURUM LOGOSU
# ======================================================================
# Logo, kurum /company/ altinda kayit olurken yuklenir ve merkezde
# saklanir. /app/ altindaki GOKTUNGU arayuzu giris yaptiginda kendi
# kurumunun logosuyla acilir; ucus raporu antedi de ayni logoyu
# kullanir. Boylece kullanici hangi bilgisayardan girerse girsin
# kurumsal kimlik korunur.
LOGO_DIZIN = os.path.join(VERI_KOKU, "varlik", "logo")
LOGO_MAKS_BAYT = 2 * 1024 * 1024          # 2 MB
LOGO_TURLERI = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}


def logo_coz(veri_url):
    """`data:` URL'sini (tur, baytlar) ikilisine cozer.

    Donus: (uzanti, baytlar, hata). Hata varsa ilk iki deger None.

    NEDEN data URL: kayit formu tek JSON istegi gonderir; multipart
    kullanmak icin hem istemci hem sunucu tarafinda ayri bir ayristirici
    gerekirdi. Logo boyutu 2 MB ile sinirli oldugu icin base64
    genislemesi (%33) kabul edilebilir.
    """
    s = str(veri_url or "").strip()
    if not s:
        return None, None, None                # logo istege bagli
    if not s.startswith("data:"):
        return None, None, "Logo bicimi taninmadi"
    basl, _, govde64 = s.partition(",")
    if not govde64:
        return None, None, "Logo verisi bos"
    tur = basl[5:].split(";")[0].strip().lower()
    uzanti = LOGO_TURLERI.get(tur)
    if not uzanti:
        return None, None, ("Desteklenmeyen logo turu: %s "
                            "(PNG, JPEG, WEBP veya SVG kullanin)" % tur)
    if "base64" not in basl:
        return None, None, "Logo base64 kodlanmis olmali"
    import base64 as _b64
    try:
        baytlar = _b64.b64decode(govde64, validate=False)
    except Exception:
        return None, None, "Logo verisi cozulemedi"
    if not baytlar:
        return None, None, "Logo verisi bos"
    if len(baytlar) > LOGO_MAKS_BAYT:
        return None, None, ("Logo cok buyuk (%.1f MB); en fazla 2 MB"
                            % (len(baytlar) / 1048576.0))
    # Ikili imza denetimi: uzanti ile gercek icerik uyusmuyorsa dosya
    # sunucuda yanlis Content-Type ile sunulur.
    if uzanti == ".png" and not baytlar.startswith(b"\\x89PNG"):
        return None, None, "Dosya gercek bir PNG degil"
    if uzanti == ".jpg" and not baytlar.startswith(b"\\xff\\xd8"):
        return None, None, "Dosya gercek bir JPEG degil"
    if uzanti == ".webp" and baytlar[8:12] != b"WEBP":
        return None, None, "Dosya gercek bir WEBP degil"
    if uzanti == ".svg":
        try:
            bas = baytlar[:400].decode("utf-8", "ignore").lower()
        except Exception:
            bas = ""
        if "<svg" not in bas:
            return None, None, "Dosya gercek bir SVG degil"
        # SVG icinde betik calistirilabilir; kurum logosunda buna
        # gerek yoktur ve saklanan dosya baska kullanicilara sunulur.
        if "<script" in baytlar.decode("utf-8", "ignore").lower():
            return None, None, "SVG icinde betik bulundu; kabul edilmez"
    return uzanti, baytlar, None


def logo_yaz(firma_id, veri_url):
    """Logoyu diske yazar ve `firmalar.logo_yol` degerini gunceller.

    Donus: (logo_yol|None, hata|None). Logo bos ise (None, None).
    """
    uzanti, baytlar, hata = logo_coz(veri_url)
    if hata:
        return None, hata
    if not baytlar:
        return None, None
    import secrets as _sec
    os.makedirs(LOGO_DIZIN, exist_ok=True)
    # Rastgele belirtec: firma_id tahmin edilerek baska kurumun logosu
    # dogrudan /varlik/ yolundan cekilemesin.
    ad = "firma_%d_%s%s" % (int(firma_id), _sec.token_hex(8), uzanti)
    tam = os.path.join(LOGO_DIZIN, ad)
    try:
        with open(tam, "wb") as f:
            f.write(baytlar)
    except OSError as e:
        return None, "Logo kaydedilemedi: %s" % e
    goreli = "logo/" + ad
    # Eski logo dosyasi varsa silinir; aksi halde her guncellemede
    # disk sisirilir.
    try:
        eski = db.deger(
            "SELECT logo_yol FROM firmalar WHERE firma_id = %s",
            (int(firma_id),))
        if eski and str(eski) != goreli:
            e_tam = os.path.join(VERI_KOKU, "varlik", str(eski))
            if os.path.isfile(e_tam) and os.path.realpath(
                    e_tam).startswith(os.path.realpath(LOGO_DIZIN)):
                os.remove(e_tam)
    except Exception:
        pass
    try:
        db.calistir(
            "UPDATE firmalar SET logo_yol = %s, guncel_ts = now()"
            " WHERE firma_id = %s", (goreli, int(firma_id)))
    except Exception as e:
        return None, "Logo yolu yazilamadi: %s" % e
    return goreli, None


@yol("GET", r"/api/genel/firma_logo", yetki="acik")
def _u_firma_logo(h, istek, oturum):
    """Kurum logosunu sunar (kimlik gerekmez).

    NEDEN KIMLIKSIZ: logo, giris ekraninda ve ucus raporu antedinde
    gorunur; her ikisi de oturum acilmadan once cizilebilir. Logo
    hassas veri DEGILDIR (kurumun web sitesinde de yayindadir).
    """
    try:
        fid = int(istek.sorgu.get("firma_id", [""])[0] or 0)
    except (TypeError, ValueError):
        fid = 0
    if not fid:
        h.hata_yaz(400, "firma_id zorunlu")
        return
    goreli = db.deger(
        "SELECT logo_yol FROM firmalar WHERE firma_id = %s", (fid,))
    if not goreli:
        h.hata_yaz(404, "Logo yok")
        return
    tam = os.path.normpath(os.path.join(VERI_KOKU, "varlik", str(goreli)))
    if not os.path.realpath(tam).startswith(
            os.path.realpath(os.path.join(VERI_KOKU, "varlik"))):
        h.hata_yaz(403, "Erisim engellendi")
        return
    if not os.path.isfile(tam):
        h.hata_yaz(404, "Logo dosyasi bulunamadi")
        return
    tur = mimetypes.guess_type(tam)[0] or "application/octet-stream"
    with open(tam, "rb") as f:
        icerik = f.read()
    h.send_response(200)
    h.send_header("Content-Type", tur)
    h.send_header("Content-Length", str(len(icerik)))
    # Dosya adi rastgele belirtec icerdigi icin degisince URL de degisir;
    # bu yuzden uzun onbellek guvenlidir.
    h.send_header("Cache-Control", "public, max-age=86400")
    h.end_headers()
    try:
        h.wfile.write(icerik)
    except BrokenPipeError:
        pass


@yol("POST", r"/api/firma/logo", yetki="firma")
def _u_firma_logo_yaz(h, istek, oturum):
    """Oturum acmis kurum yoneticisi logoyu degistirir."""
    if str(oturum.get("rol")) not in ("firma_yonetici", "yonetici",
                                      "admin"):
        h.json_yaz({"hata": "Bu islem icin yonetici yetkisi gerekir"}, 403)
        return
    fid = int(oturum.get("firma_id") or 0)
    if not fid:
        h.json_yaz({"hata": "Kurum bulunamadi"}, 400)
        return
    g = istek.govde or {}
    goreli, hata = logo_yaz(fid, g.get("logo"))
    if hata:
        h.json_yaz({"hata": hata}, 400)
        return
    if not goreli:
        h.json_yaz({"hata": "Logo verisi gonderilmedi"}, 400)
        return
    kimlik.denetim(None, "firma_logo", "firma", str(fid),
                   {"logo_yol": goreli}, istek.ip)
    h.json_yaz({"tamam": True,
                "logo_url": "/api/genel/firma_logo?firma_id=%d" % fid})
'''

if "v2.4.53 Faz 4 — KURUM LOGOSU" not in m:
    m = m.rstrip("\n") + "\n" + YARDIMCI
    print("[1] logo yardimcilari + 2 uc eklendi")
else:
    print("[1] zaten var (atlandi)")

# ======================================================================
# 2) Kayit ucu logo kabul etmeli
# ======================================================================
eski = '''    kimlik.denetim(None, "firma_kayit", "firma", str(fid),
                   {"unvan": unvan, "eposta": eposta}, istek.ip)'''
yeni = '''    # v2.4.53 Faz 4: kurum logosu. Logo BASARISIZ olsa bile kayit
    # geri alinmaz — kurum olusmustur ve logo sonradan Kurum Bilgileri
    # ekranindan yuklenebilir. Kullanici uyarilir.
    logo_uyari = ""
    try:
        _lg, _lh = logo_yaz(int(fid), g.get("logo"))
        if _lh:
            logo_uyari = _lh
    except Exception as _le:
        logo_uyari = "Logo kaydedilemedi: %s" % _le

    kimlik.denetim(None, "firma_kayit", "firma", str(fid),
                   {"unvan": unvan, "eposta": eposta}, istek.ip)'''
if eski in m:
    m = m.replace(eski, yeni, 1)
    print("[2] kayit ucu logo kabul ediyor")
elif "logo_uyari" in m:
    print("[2] zaten var (atlandi)")
else:
    print("[2] HATA: denetim cagrisi kalibi eslesmedi")
    sys.exit(1)

# Yanitlara logo bilgisi eklenir
eski = '''        h.json_yaz({"tamam": True, "firma_id": int(fid),
                    "kullanici_id": int(kid), "giris": False})
        return'''
yeni = '''        h.json_yaz({"tamam": True, "firma_id": int(fid),
                    "kullanici_id": int(kid), "giris": False,
                    "logo_uyari": logo_uyari})
        return'''
if eski in m:
    m = m.replace(eski, yeni, 1)
    print("[3] giris=False yanitina logo_uyari eklendi")

eski = '''    h.json_yaz({"tamam": True, "firma_id": int(fid),
                "kullanici_id": int(kid), "giris": True,
                "kullanici": veri}, 200, {"Set-Cookie": kurabiye})'''
yeni = '''    h.json_yaz({"tamam": True, "firma_id": int(fid),
                "kullanici_id": int(kid), "giris": True,
                "kullanici": veri, "logo_uyari": logo_uyari},
               200, {"Set-Cookie": kurabiye})'''
if eski in m:
    m = m.replace(eski, yeni, 1)
    print("[4] giris=True yanitina logo_uyari eklendi")

if m == ilk:
    print("DEGISIKLIK YOK")
    sys.exit(0)

import ast
ast.parse(m)
with io.open(YOL, "w", encoding="utf-8") as f:
    f.write(m)
print("YAZILDI:", YOL, "(%d bayt)" % len(m))
