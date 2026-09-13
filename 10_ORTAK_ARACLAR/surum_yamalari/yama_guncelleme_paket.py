"""IS-2521-GUNCELLEME: /api/istemci/guncelleme_paket sunucu ucunu ekler.

Kullanim: python3.11 yama_guncelleme_paket.py <mk_sunucu.py> <mk_kaba_kuvvet.py>
Idempotent degil; yalniz orijinal dosyalara bir kez uygulanir.
"""
import sys

sunucu, kaba = sys.argv[1], sys.argv[2]
s = open(sunucu, encoding="utf-8").read()
capa = '''        (fid,))
    h.dosya_akit(hedef, dosya)


# --------------------------------------------------------- kopru indirmeleri'''
if s.count(capa) != 1:
    sys.exit("HATA: mk_sunucu.py capasi bulunamadi (%d)" % s.count(capa))
if "_u_istemci_guncelleme_paket" in s:
    sys.exit("HATA: uc zaten var")

yeni = '''        (fid,))
    h.dosya_akit(hedef, dosya)


# ----------------------------------------- istemci: otomatik guncelleme paketi
# IS-2521-GUNCELLEME (2026-09-12): Kurulu Merkez (`gcs`) ve Kopru
# (`kopru`/`video`) istemcilerindeki `guncelleme.py::_paket_indir` bu uca
# POST eder. OLCULEN KUSUR: uc sunucuda HIC YOKTU (404); istemcideki
# "Indir ve dogrula" her kosulda basarisiz oluyordu.
#
# Kimlik tarayici oturumu DEGILDIR (servis olarak calisan istemcinin
# oturumu yoktur):
#   * gcs         -> kurulumdaki imzali `merkez_lisans.json`. Imza bu
#                    sunucunun anahtariyla dogrulanir, lisans_uid bu
#                    firmaya verilmis olmali, firma BUGUN etkin ve
#                    `merkez_lisans` sahibi olmali, bakim kapsami surmeli.
#                    Yetki degisimiyle tazelenmis (iptal_ts dolu) eski UID
#                    KABUL edilir: kapali devre kurulum lisansini yeniden
#                    indirmemis olabilir; asil hak firmanin guncel yetkisidir.
#   * kopru/video -> merkezce verilen `kurulum_uid` + `gizli` (ucretsiz
#                    urunler; bakim kapisi uygulanmaz).
# Yalniz katalogda ETKIN ve urun/surum/platform/dosya ile birebir eslesen
# kayit akitilir. Kaba kuvvet korumasi: mk_kaba_kuvvet.KORUNAN_UCLAR.
_GUNCELLEME_PAKET_URUNLERI = ("gcs", "kopru", "video")


@yol("POST", r"/api/istemci/guncelleme_paket", yetki="acik")
def _u_istemci_guncelleme_paket(h, istek, oturum):
    g = istek.govde if isinstance(istek.govde, dict) else {}
    urun = str(g.get("urun") or "").strip().lower()
    surum = str(g.get("surum") or "").strip()
    platform = str(g.get("platform") or "").strip().lower()
    dosya = str(g.get("dosya") or "").strip()
    if (urun not in _GUNCELLEME_PAKET_URUNLERI or not surum
            or not platform or not dosya):
        h.hata_yaz(400, "urun, surum, platform ve dosya zorunlu")
        return
    if "/" in dosya or "\\\\" in dosya or ".." in dosya:
        h.hata_yaz(400, "Gecersiz dosya adi")
        return

    if urun == "gcs":
        belge = g.get("lisans")
        govde = belge.get("lisans") if isinstance(belge, dict) else None
        imza = str(belge.get("imza") or "") if isinstance(belge, dict) else ""
        if (not isinstance(govde, dict) or not imza
                or not depo.veri_imza_dogrula(yetki.govde_bayt(govde), imza)):
            h.hata_yaz(403, "Lisans belgesi dogrulanamadi")
            return
        try:
            fid = int(govde.get("firma_id"))
        except (TypeError, ValueError):
            h.hata_yaz(403, "Lisans belgesi dogrulanamadi")
            return
        if not db.deger(
                "SELECT 1 FROM merkez_lisanslari "
                "WHERE firma_id = %s AND lisans_uid = %s",
                (fid, str(govde.get("lisans_uid") or ""))):
            h.hata_yaz(403, "Lisans bu sunucuda kayitli degil")
            return
        y = yetki.firma_yetkileri(fid)
        if not y or y.get("durum") != "etkin" or not y.get("merkez_lisans"):
            h.hata_yaz(403, "Merkez Uygulama lisansi etkin degil")
            return
        hakli, neden = bakim.guncelleme_alabilir_mi(fid)
        if not hakli:
            h.hata_yaz(403, neden)
            return
    else:
        uid = str(g.get("kurulum_uid") or "").strip()
        gizli = str(g.get("gizli") or "")
        k = db.tek(
            "SELECT s.firma_id, s.gizli_ozet, s.durum, "
            "       f.durum AS firma_durum "
            "FROM sunucu_ornekleri s "
            "JOIN firmalar f ON f.firma_id = s.firma_id "
            "WHERE s.kurulum_uid = %s", (uid,)) if uid else None
        if not k or not role.gizli_dogrula(gizli, k["gizli_ozet"]):
            h.hata_yaz(403, "Kurulum kimligi gecersiz")
            return
        if k["durum"] != "etkin" or k["firma_durum"] != "etkin":
            h.hata_yaz(403, "Kurulum veya firma etkin degil")
            return
        fid = int(k["firma_id"])

    kayit = db.tek(
        "SELECT surum_id FROM surumler "
        "WHERE urun = %s AND surum = %s AND platform IN (%s, 'ortak') "
        "AND dosya_ad = %s AND etkin AND paket_tur IN ('tam', 'guncelleme') "
        "ORDER BY (platform = %s) DESC, surum_id DESC LIMIT 1",
        (urun, surum, platform, dosya, platform))
    hedef = depo.indirme_coz(urun, surum, dosya) if kayit else None
    if not hedef:
        h.hata_yaz(404, "Paket bulunamadi")
        return
    if urun == "gcs":
        db.calistir(
            "UPDATE merkez_lisanslari SET indirme_sayisi = indirme_sayisi + 1, "
            "  son_indirme_ts = now() WHERE firma_id = %s AND iptal_ts IS NULL",
            (fid,))
    depo.indirme_say(int(kayit["surum_id"]), h._kk_es())
    h.dosya_akit(hedef, dosya)


# --------------------------------------------------------- kopru indirmeleri'''
open(sunucu, "w", encoding="utf-8").write(s.replace(capa, yeni))

t = open(kaba, encoding="utf-8").read()
a = '    "/api/istemci/sunucu_kayit",\n'
if t.count(a) != 1:
    sys.exit("HATA: KORUNAN_UCLAR capasi bulunamadi")
if "/api/istemci/guncelleme_paket" not in t:
    open(kaba, "w", encoding="utf-8").write(t.replace(a, a + '    "/api/istemci/guncelleme_paket",\n'))
print("yama uygulandi")
