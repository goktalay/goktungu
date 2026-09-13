#!/usr/bin/env python3.11
"""mk_sunucu.py'ye abonelik / yetki / lisanslı indirme uçlarını ekler.

Bu betik yeniden çalıştırılmaya karşı güvenlidir: eklenecek blok zaten
varsa dokunmaz.

NEDEN YAMA BETİĞİ: `mk_sunucu.py` 2200 satır ve uç noktalar dosyanın
sonuna doğru `@yol(...)` dekoratörüyle sıralanmış. Dosyayı elle
yeniden yazmak mevcut 60+ ucu riske atardı. Depodaki mevcut kalıp da
budur (`ek_firma_uclari.py`, `ek_kayit_ucu.py`).
"""
from __future__ import annotations

import os
import re
import sys

BURASI = os.path.dirname(os.path.abspath(__file__))
HEDEF = os.path.join(BURASI, "mk_sunucu.py")
IMZA = "# === ABONELIK VE LISANS UCLARI (v2.4.65) ==="

EK = '''

# ==========================================================================
''' + IMZA + '''
# ==========================================================================
# Bu bolumun tamami 2026-08-15'te abonelik/faturalandirma katmani icin
# eklendi. Yetki kararlari YALNIZ `mk_yetki` modulunden sorulur; burada
# kopya mantik YOKTUR.


# -------------------------------------------------------------- genel: fiyat
@yol("GET", r"/api/genel/fiyatlar", yetki="acik")
def _u_genel_fiyatlar(h, istek, oturum):
    """Tanitim sayfasinin ve kurumsal panelin okudugu fiyat listesi.

    Fiyatlar `mk_yetki.KALEMLER` tek kaynagindan TURETILIR; arayuze
    elle yazilmaz. Aksi halde aylik fiyat degistiginde tanitim sayfasi
    sessizce eskir.
    """
    h.json_yaz({
        "kalemler": yetki.fiyat_listesi(),
        "yillik_indirim": yetki.YILLIK_INDIRIM,
        "taban_pilot": yetki.TABAN_PILOT_KOLTUK,
        "para": "USD",
    })


# ------------------------------------------------------ genel: uyelik talebi
@yol("POST", r"/api/genel/uyelik_talebi", yetki="acik")
def _u_genel_uyelik_talebi(h, istek, oturum):
    """Tanitim sayfasindan gelen on talep. Kimlik ISTEMEZ.

    Sirket henuz kayitli olmayabilir; bu yuzden `firma_id` bos
    gecilebilir ve iletisim bilgisi zorunludur.
    """
    g = istek.govde or {}
    eposta = (g.get("iletisim_eposta") or "").strip()
    if "@" not in eposta:
        h.hata_yaz(400, "Gecerli bir e-posta gerekli")
        return
    kalem = (g.get("kalem") or "").strip()
    tid, hata = yetki.talep_olustur(
        None, kalem, int(g.get("adet") or 1),
        (g.get("donem") or "aylik").strip(),
        (g.get("iletisim_ad") or "").strip(), eposta,
        (g.get("iletisim_tel") or "").strip(),
        (g.get("mesaj") or "").strip())
    if hata:
        h.hata_yaz(400, hata)
        return
    h.json_yaz({"talep_id": tid, "durum": "bekliyor"}, 201)


# ------------------------------------------------------------- firma: ozet
@yol("GET", r"/api/firma/abonelik", yetki="firma")
def _u_firma_abonelik(h, istek, oturum):
    """Sirketin abonelik durumu: koltuk kullanimi, ozellikler, kalemler."""
    fid = _firma_id(oturum)
    y = yetki.firma_yetkileri(fid)
    if not y:
        h.hata_yaz(404, "Firma bulunamadi")
        return
    h.json_yaz({
        "yetkiler": y,
        "kalemler": yetki.kalem_listesi(fid),
        "talepler": yetki.talep_listesi(firma_id=fid),
        "fiyatlar": yetki.fiyat_listesi(),
        "yillik_indirim": yetki.YILLIK_INDIRIM,
    })


@yol("POST", r"/api/firma/uyelik_talebi", yetki="firma")
def _u_firma_uyelik_talebi(h, istek, oturum):
    """Sirket yoneticisinin panelden olusturdugu abonelik talebi."""
    if oturum.get("rol") != "firma_yonetici":
        h.hata_yaz(403, "Bu islem icin firma yoneticisi olmalisiniz")
        return
    g = istek.govde or {}
    tid, hata = yetki.talep_olustur(
        _firma_id(oturum), (g.get("kalem") or "").strip(),
        int(g.get("adet") or 1), (g.get("donem") or "aylik").strip(),
        (g.get("iletisim_ad") or oturum.get("ad") or "").strip(),
        (g.get("iletisim_eposta") or oturum.get("eposta") or "").strip(),
        (g.get("iletisim_tel") or "").strip(),
        (g.get("mesaj") or "").strip())
    if hata:
        h.hata_yaz(400, hata)
        return
    h.json_yaz({"talep_id": tid, "durum": "bekliyor"}, 201)


# --------------------------------------------- firma: uyelik (ekip) yonetimi
# GCS'ten KALDIRILAN yetenegin yeni ve TEK adresi. Kullanici acikca
# "tum uyelik surecleri kurumsal panelden sirket yoneticisi tarafindan
# yapilsin" dedi.
@yol("POST", r"/api/firma/ekip", yetki="firma")
def _u_firma_ekip_ekle(h, istek, oturum):
    if oturum.get("rol") != "firma_yonetici":
        h.hata_yaz(403, "Bu islem icin firma yoneticisi olmalisiniz")
        return
    g = dict(istek.govde or {})
    # Firma KENDI firmasina ekler; govdeden gelen firma_id yok sayilir,
    # aksi halde bir sirket baska sirkete kullanici ekleyebilirdi.
    g["firma_id"] = _firma_id(oturum)
    rol = (g.get("rol") or "pilot").strip()
    if rol not in ("pilot", "gozlemci", "firma_yonetici"):
        h.hata_yaz(400, "Gecersiz rol: %s" % rol)
        return
    g["rol"] = rol
    kid, hata = api.kullanici_ekle(g)
    if hata:
        # Koltuk dolulugu 409 ile bildirilir; arayuz bunu "talep olustur"
        # yonlendirmesine cevirir.
        h.hata_yaz(409 if "koltu" in hata.lower() else 400, hata)
        return
    h.json_yaz({"kullanici_id": kid}, 201)


@yol("PUT", r"/api/firma/ekip/(\\d+)", yetki="firma")
def _u_firma_ekip_guncelle(h, istek, oturum, kid):
    if oturum.get("rol") != "firma_yonetici":
        h.hata_yaz(403, "Bu islem icin firma yoneticisi olmalisiniz")
        return
    fid = _firma_id(oturum)
    k = db.tek("SELECT firma_id, rol FROM kullanicilar "
               "WHERE kullanici_id = %s", (int(kid),))
    if not k or int(k["firma_id"]) != fid:
        h.hata_yaz(404, "Kullanici bulunamadi")
        return
    g = dict(istek.govde or {})
    for yasak in ("firma_id", "kullanici_id"):
        g.pop(yasak, None)
    if g.get("rol") and g["rol"] not in ("pilot", "gozlemci",
                                         "firma_yonetici"):
        h.hata_yaz(400, "Gecersiz rol: %s" % g["rol"])
        return
    # Son firma yoneticisinin rolu dusurulemez / pasife alinamaz:
    # aksi halde sirket kendi panelinden tamamen kilitlenir.
    if k["rol"] == "firma_yonetici" and (
            (g.get("rol") and g["rol"] != "firma_yonetici")
            or (g.get("durum") and g["durum"] != "etkin")):
        kalan = db.deger(
            "SELECT count(*) FROM kullanicilar WHERE firma_id = %s "
            "AND rol = 'firma_yonetici' AND durum = 'etkin' "
            "AND kullanici_id <> %s", (fid, int(kid)))
        if not int(kalan or 0):
            h.hata_yaz(409, "Son firma yoneticisi devre disi birakilamaz")
            return
    tamam, hata = api.kullanici_guncelle(int(kid), g)
    if not tamam:
        h.hata_yaz(409 if "koltu" in (hata or "").lower() else 400,
                   hata or "Guncellenemedi")
        return
    h.json_yaz({"tamam": True})


@yol("DELETE", r"/api/firma/ekip/(\\d+)", yetki="firma")
def _u_firma_ekip_sil(h, istek, oturum, kid):
    if oturum.get("rol") != "firma_yonetici":
        h.hata_yaz(403, "Bu islem icin firma yoneticisi olmalisiniz")
        return
    fid = _firma_id(oturum)
    k = db.tek("SELECT firma_id, rol FROM kullanicilar "
               "WHERE kullanici_id = %s", (int(kid),))
    if not k or int(k["firma_id"]) != fid:
        h.hata_yaz(404, "Kullanici bulunamadi")
        return
    if int(kid) == int(oturum["kullanici_id"]):
        h.hata_yaz(409, "Kendi hesabinizi silemezsiniz")
        return
    if k["rol"] == "firma_yonetici":
        kalan = db.deger(
            "SELECT count(*) FROM kullanicilar WHERE firma_id = %s "
            "AND rol = 'firma_yonetici' AND durum = 'etkin' "
            "AND kullanici_id <> %s", (fid, int(kid)))
        if not int(kalan or 0):
            h.hata_yaz(409, "Son firma yoneticisi silinemez")
            return
    tamam, hata = api.kullanici_sil(int(kid))
    if not tamam:
        h.hata_yaz(400, hata or "Silinemedi")
        return
    h.json_yaz({"tamam": True})


# ------------------------------------------- firma: Merkez Uygulama indirme
@yol("GET", r"/api/firma/merkez_paketler", yetki="firma")
def _u_firma_merkez_paketler(h, istek, oturum):
    """Lisansli sirketin indirebilecegi Merkez Uygulama paketleri.

    Lisans yoksa 403 doner ve paket listesi HIC uretilmez.
    """
    fid = _firma_id(oturum)
    y = yetki.firma_yetkileri(fid)
    if not y.get("merkez_lisans"):
        h.hata_yaz(403, "Merkez Uygulama lisansiniz bulunmuyor")
        return
    kayitlar = [k for k in depo.liste("gcs", "kararli", etkin_yalniz=True)
                if k.get("dosya_var")]
    for k in kayitlar:
        k.pop("imza", None)
    h.json_yaz({"kayitlar": kayitlar,
                "lisans_uid": (db.deger(
                    "SELECT lisans_uid FROM merkez_lisanslari "
                    "WHERE firma_id = %s AND iptal_ts IS NULL "
                    "ORDER BY olusma_ts DESC LIMIT 1", (fid,)) or "")})


@yol("GET", r"/api/firma/merkez_lisans", yetki="firma")
def _u_firma_merkez_lisans(h, istek, oturum):
    """Sirkete ozel imzali lisans belgesini uretir ve dondurur.

    Bu belge Merkez Uygulama kurulumuna yerlestirilir. Uygulama KAPALI
    DEVRE calisabildigi icin lisansi cevrimici dogrulayamaz; imzayi
    gomulu acik anahtarla dogrular.
    """
    if oturum.get("rol") != "firma_yonetici":
        h.hata_yaz(403, "Bu islem icin firma yoneticisi olmalisiniz")
        return
    lisans, hata = yetki.lisans_uret(_firma_id(oturum))
    if hata:
        h.hata_yaz(403, hata)
        return
    h.json_yaz({"lisans": lisans["govde"], "imza": lisans["imza"],
                "acik_anahtar": depo.acik_anahtar_b64()})


@yol("GET", r"/api/firma/merkez_indir", yetki="firma")
def _u_firma_merkez_indir(h, istek, oturum):
    """Lisans denetimli Merkez Uygulama indirmesi.

    NEDEN AYRI UC: `/indir/` yolu statik dosya sunucusudur ve KIMLIK
    ISTEMEZ. `gcs` urununun yalnizca tanitim katalogundan gizlenmesi
    gercek bir kilit degildir; dosya adini bilen herkes 5.000 USD'lik
    urunu indirebilirdi. Bu uc oturumu ve lisansi dogrular, indirmeyi
    sayar, sonra dosyayi akitir.
    """
    fid = _firma_id(oturum)
    y = yetki.firma_yetkileri(fid)
    if not y.get("merkez_lisans"):
        h.hata_yaz(403, "Merkez Uygulama lisansiniz bulunmuyor")
        return
    surum = (istek.sorgu.get("surum") or "").strip()
    dosya = (istek.sorgu.get("dosya") or "").strip()
    if not surum or not dosya:
        h.hata_yaz(400, "surum ve dosya zorunlu")
        return
    # Dizin gezinme korumasi: dosya adinda ayirici olamaz.
    if "/" in dosya or "\\\\" in dosya or ".." in dosya:
        h.hata_yaz(400, "Gecersiz dosya adi")
        return
    hedef = depo.indirme_coz("gcs", surum, dosya)
    if not hedef or not os.path.isfile(hedef):
        h.hata_yaz(404, "Paket bulunamadi")
        return
    db.calistir(
        "UPDATE merkez_lisanslari SET indirme_sayisi = indirme_sayisi + 1, "
        "  son_indirme_ts = now() WHERE firma_id = %s AND iptal_ts IS NULL",
        (fid,))
    h.dosya_akit(hedef, dosya)


# ------------------------------------------------------- admin: yetki/abone
@yol("GET", r"/api/admin/firma/(\\d+)/abonelik")
def _u_admin_firma_abonelik(h, istek, oturum, fid):
    y = yetki.firma_yetkileri(int(fid))
    if not y:
        h.hata_yaz(404, "Firma bulunamadi")
        return
    h.json_yaz({"yetkiler": y,
                "kalemler": yetki.kalem_listesi(int(fid)),
                "talepler": yetki.talep_listesi(firma_id=int(fid)),
                "fiyatlar": yetki.fiyat_listesi()})


@yol("POST", r"/api/admin/firma/(\\d+)/yetki")
def _u_admin_firma_yetki(h, istek, oturum, fid):
    """VEILOX sistem yoneticisinin anahtar acma/kapama islemi.

    Radar ve GCCDUAL SATILMAZ; yalniz bu uctan acilir. Kullanici:
    "Radar ve GCCDual ozelligi en tepedeki sirketleri yoneten veilox
    kullanicisi acip kapatabilecek."
    """
    g = istek.govde or {}
    alan = (g.get("alan") or "").strip()
    if "deger" not in g:
        h.hata_yaz(400, "deger zorunlu")
        return
    deger = bool(g.get("deger"))
    tamam, hata = yetki.yetki_ayarla(int(fid), alan, deger,
                                     oturum.get("yonetici_id"))
    if not tamam:
        h.hata_yaz(400, hata)
        return
    kimlik.denetim(oturum.get("yonetici_id"), "firma_yetki", "firma",
                   str(fid), {"alan": alan, "deger": deger}, istek.ip)
    h.json_yaz({"tamam": True, "yetkiler": yetki.firma_yetkileri(int(fid))})


@yol("POST", r"/api/admin/firma/(\\d+)/kalem")
def _u_admin_firma_kalem(h, istek, oturum, fid):
    """VEILOX'un elle uyelik tanimlamasi (odeme akisini atlayarak).

    Kullanici: "veilox sistem yoneticisi isterse sirketlere her turlu
    uyeligi ekleyebilecek."
    """
    g = istek.govde or {}
    tamam, hata = yetki.kalem_uygula(
        int(fid), (g.get("kalem") or "").strip(),
        int(g.get("adet") or 1), (g.get("donem") or "aylik").strip(),
        kaynak=(g.get("kaynak") or "veilox").strip(),
        yonetici_id=oturum.get("yonetici_id"),
        notlar=(g.get("notlar") or "").strip() or None,
        bitis=(g.get("bitis") or "").strip() or None)
    if not tamam:
        h.hata_yaz(400, hata)
        return
    kimlik.denetim(oturum.get("yonetici_id"), "abonelik_kalem", "firma",
                   str(fid), g, istek.ip)
    h.json_yaz({"tamam": True, "yetkiler": yetki.firma_yetkileri(int(fid))})


@yol("GET", r"/api/admin/talepler")
def _u_admin_talepler(h, istek, oturum):
    h.json_yaz({"kayitlar": yetki.talep_listesi(
        (istek.sorgu.get("durum") or "").strip() or None)})


@yol("POST", r"/api/admin/talep/(\\d+)/karar")
def _u_admin_talep_karar(h, istek, oturum, tid):
    g = istek.govde or {}
    onay = bool(g.get("onay"))
    tamam, hata = yetki.talep_karar(int(tid), onay,
                                    oturum.get("yonetici_id"),
                                    (g.get("notu") or "").strip())
    if not tamam:
        h.hata_yaz(400, hata)
        return
    kimlik.denetim(oturum.get("yonetici_id"), "uyelik_talep_karar", "talep",
                   str(tid), {"onay": onay}, istek.ip)
    h.json_yaz({"tamam": True})


@yol("POST", r"/api/admin/firma/(\\d+)/merkez_lisans")
def _u_admin_merkez_lisans(h, istek, oturum, fid):
    """Merkez Uygulama lisansini elle aktiflestirir.

    Kullanici: "ben veilox olarak istedigim sirkete merkezi yazilim
    lisansi aktiflestirebilirim."
    """
    g = istek.govde or {}
    ac = bool(g.get("etkin", True))
    tamam, hata = yetki.yetki_ayarla(int(fid), "merkez_lisans", ac,
                                     oturum.get("yonetici_id"))
    if not tamam:
        h.hata_yaz(400, hata)
        return
    if ac:
        # Kalem defterine de yazilir; boylece "kim ne zaman verdi"
        # denetim izi kalir ve gelir raporlamasi eksik cikmaz.
        yetki.kalem_uygula(int(fid), "merkez", 1, "tek", kaynak="veilox",
                           yonetici_id=oturum.get("yonetici_id"),
                           notlar="Admin panelinden elle aktiflestirildi")
    kimlik.denetim(oturum.get("yonetici_id"), "merkez_lisans", "firma",
                   str(fid), {"etkin": ac}, istek.ip)
    h.json_yaz({"tamam": True, "yetkiler": yetki.firma_yetkileri(int(fid))})
'''

# `dosya_akit` yardimcisi MerkezIsleyici sinifina eklenir.
AKIT_IMZA = "def dosya_akit(self"
AKIT = '''
    def dosya_akit(self, hedef: str, indirme_ad: str) -> None:
        """Diskteki bir dosyayi indirme olarak akitir.

        v2.4.65 — lisans denetimli Merkez Uygulama indirmesi icin
        eklendi. `_dosya_sun()` kullanilamaz: o islev istegin YOLUNDAN
        dosya cozer ve kimlik denetimi yapmaz; burada dosya zaten
        yetkilendirilmis olarak verilir.
        """
        try:
            boyut = os.path.getsize(hedef)
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(boyut))
            self.send_header("Content-Disposition",
                             'attachment; filename="%s"' % indirme_ad)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if self.command == "HEAD":
                return
            with open(hedef, "rb") as f:
                while True:
                    parca = f.read(256 * 1024)
                    if not parca:
                        break
                    self.wfile.write(parca)
        except BrokenPipeError:
            pass
'''


def main() -> int:
    with open(HEDEF, "r", encoding="utf-8") as f:
        src = f.read()

    degisti = False

    # 1) `yetki` modulu ice alinir
    if "import mk_yetki as yetki" not in src:
        m = re.search(r"^import mk_depo as depo.*$", src, re.M)
        if not m:
            print("HATA: 'import mk_depo as depo' satiri bulunamadi")
            return 2
        src = src[:m.end()] + "\nimport mk_yetki as yetki" + src[m.end():]
        degisti = True
        print(" - ice alim eklendi: mk_yetki as yetki")

    # 2) `acik` yetkisi taninir mi? (mevcut kodda `acik` yetkili uclar
    #    zaten var; dogrulayalim)
    if 'yetki="acik"' not in src:
        print("UYARI: 'acik' yetkili uc yok; yonlendirme kontrol edilmeli")

    # 3) dosya_akit yardimcisi
    if AKIT_IMZA not in src:
        m = re.search(r"^    def hata_yaz\(self, kod: int, mesaj: str\) -> None:\n"
                      r"        self\.json_yaz\(\{\"hata\": mesaj\}, kod\)\n",
                      src, re.M)
        if not m:
            print("HATA: hata_yaz cengeli bulunamadi")
            return 3
        src = src[:m.end()] + AKIT + src[m.end():]
        degisti = True
        print(" - yardimci eklendi: MerkezIsleyici.dosya_akit()")

    # 4) DELETE ve PUT yontemleri destekleniyor mu?
    for y in ("do_PUT", "do_DELETE"):
        if y not in src:
            print("UYARI: %s yok; ilgili uclar calismaz" % y)

    # 5) Uc blogu
    if IMZA not in src:
        src = src.rstrip("\n") + "\n" + EK
        degisti = True
        print(" - uc blogu eklendi (14 yeni uc)")
    else:
        print(" - uc blogu zaten var, atlandi")

    if not degisti:
        print("Degisiklik yok.")
        return 0

    with open(HEDEF, "w", encoding="utf-8") as f:
        f.write(src)

    import ast
    try:
        ast.parse(src)
    except SyntaxError as e:
        print("HATA: yazilan dosya sozdizimi bozuk: %s" % e)
        return 4
    print("mk_sunucu.py guncellendi ve sozdizimi dogrulandi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
