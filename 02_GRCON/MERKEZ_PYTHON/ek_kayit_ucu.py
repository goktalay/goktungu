#!/usr/bin/env python3.11
"""mk_sunucu.py'ye kurumsal kayit ucunu ekler.

NEDEN GEREKLI: /company/ panelinde yalniz giris vardi; yeni musteri
yalnizca VEILOX personeli tarafindan /admin/ uzerinden elle
olusturulabiliyordu. Kullanici web'den kendi kurumunu kaydedebilmeli.

TASARIM KARARLARI:
  * Kayit TEK islemde firma + yonetici kullanici olusturur. Ikisi ayri
    istekte olsaydi, ikinci istek basarisiz oldugunda sahipsiz firma
    kaydi kalirdi.
  * Yeni firma `durum='etkin'`, `abonelik='deneme'` ile acilir; VEILOX
    onayi beklemez, aksi halde kullanici indirdigi yazilimi hic
    kullanamaz. Yukseltme /admin/ uzerinden yapilir.
  * Ilk kullanicinin rolu ZORUNLU olarak `firma_yonetici`; aksi halde
    kurumun hicbir yoneticisi olmaz ve ekip yonetimi kilitlenir.
  * Vergi no verilirse tekillik `firma_ekle` icinde denetlenir.
  * Kayit sonrasi OTURUM ACILIR (giris ucundaki ayni kurabiye); boylece
    kullanici tekrar sifre girmez.
"""
from __future__ import annotations
import io
import re

YOL = "mk_sunucu.py"

with io.open(YOL, encoding="utf-8") as f:
    s = f.read()

if "/api/firma/kayit" in s:
    print("ATLANDI: kayit ucu zaten var")
    raise SystemExit(0)

# Kayit ucu, giris ucunun HEMEN ONUNE eklenir; boylece acik uclar
# bir arada kalir ve okuyan kisi ikisini birlikte gorur.
capa = '@yol("POST", r"/api/firma/giris", yetki="acik")'
if capa not in s:
    raise SystemExit("HATA: giris ucu capasi bulunamadi")

yeni = '''@yol("POST", r"/api/firma/kayit", yetki="acik")
def _u_firma_kayit(h, istek, oturum):
    """Kurumsal kayit: firma + ilk yonetici kullanici, TEK islemde.

    NEDEN TEK ISLEM: firma ile yonetici ayri isteklerde olusturulsa,
    ikinci istek basarisiz oldugunda sahipsiz firma kaydi kalirdi ve
    ayni vergi no ile yeniden kayit engellenirdi.
    """
    g = istek.govde or {}
    unvan = (g.get("unvan") or "").strip()
    eposta = (g.get("eposta") or "").strip()
    sifre = g.get("sifre") or ""
    sifre2 = g.get("sifre2") or ""
    ad = (g.get("ad") or "").strip()
    soyad = (g.get("soyad") or "").strip()

    if not unvan:
        h.json_yaz({"hata": "Kurum unvani zorunlu"}, 400)
        return
    if len(unvan) < 3:
        h.json_yaz({"hata": "Kurum unvani en az 3 karakter olmali"}, 400)
        return
    if "@" not in eposta or "." not in eposta.split("@")[-1]:
        h.json_yaz({"hata": "Gecerli bir e-posta adresi girin"}, 400)
        return
    if not ad:
        h.json_yaz({"hata": "Yetkili adi zorunlu"}, 400)
        return
    if sifre2 and sifre != sifre2:
        h.json_yaz({"hata": "Sifreler eslesmiyor"}, 400)
        return
    # Sifre gucu kimlik katmaninda da denetlenir; burada ONCE denetlemek
    # firma kaydinin bosuna olusmasini onler.
    sg = kimlik.sifre_gucu(sifre)
    if sg:
        h.json_yaz({"hata": sg}, 400)
        return
    # E-posta tekilligi firma olusturmadan ONCE denetlenir; aksi halde
    # sahipsiz firma kaydi kalir.
    if db.tek("SELECT 1 FROM kullanicilar WHERE eposta = %s", (eposta,)):
        h.json_yaz({"hata": "Bu e-posta zaten kayitli"}, 409)
        return

    fid, hata = api.firma_ekle({
        "unvan": unvan,
        "kisa_ad": (g.get("kisa_ad") or "").strip() or unvan[:40],
        "vergi_no": (g.get("vergi_no") or "").strip(),
        "vergi_dairesi": (g.get("vergi_dairesi") or "").strip(),
        "adres": (g.get("adres") or "").strip(),
        "telefon": (g.get("telefon") or "").strip(),
        "eposta": eposta,
        "web": (g.get("web") or "").strip(),
        "ulke": (g.get("ulke") or "TR").strip(),
        "durum": "etkin",
        "abonelik": "deneme",
    })
    if hata or not fid:
        h.json_yaz({"hata": hata or "Kurum olusturulamadi"}, 400)
        return

    kid, hata = api.kullanici_ekle({
        "firma_id": fid, "eposta": eposta, "sifre": sifre,
        "ad": ad, "soyad": soyad, "rol": "firma_yonetici",
        "telefon": (g.get("telefon") or "").strip(),
    })
    if hata or not kid:
        # Yonetici olusmadiysa firma da GERI ALINIR; aksi halde
        # erisilemeyen bir kurum kaydi kalir ve vergi no bloke olur.
        api.firma_sil(int(fid))
        h.json_yaz({"hata": hata or "Yetkili hesabi olusturulamadi"}, 400)
        return

    kimlik.denetim_yaz(None, "firma_kayit", "firma", int(fid),
                       {"unvan": unvan, "eposta": eposta}, istek.ip)

    # Kayit sonrasi oturum acilir; kullanici tekrar sifre girmez.
    veri, hata = kimlik.kullanici_giris(
        eposta, sifre, istek.ip, istek.h.headers.get("User-Agent"))
    if hata or not veri:
        # Kayit BASARILI, yalniz otomatik giris olmadi; kullanici
        # giris ekranina yonlendirilir.
        h.json_yaz({"tamam": True, "firma_id": int(fid),
                    "kullanici_id": int(kid), "giris": False})
        return
    kurabiye = (f"goktungu_firma={urllib.parse.quote(veri['jeton'])}; Path=/; "
                f"HttpOnly; SameSite=Lax; Max-Age={12 * 3600}")
    h.json_yaz({"tamam": True, "firma_id": int(fid),
                "kullanici_id": int(kid), "giris": True,
                "kullanici": veri}, 200, {"Set-Cookie": kurabiye})


'''

s = s.replace(capa, yeni + capa, 1)

with io.open(YOL, "w", encoding="utf-8") as f:
    f.write(s)
print("EKLENDI: POST /api/firma/kayit")
