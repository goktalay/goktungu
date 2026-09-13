#!/usr/bin/env python3
"""Merkez firma API'sini /company/ panelinin ihtiyaclarina gore tamamlar.

Uc ekleme (ekip, kurum) ve `gosterge` ucuna panelin bekledigi dort alanin
(`telemetri`, `kullanici_etkin`, `toplam_mesafe_m`, `dron_ucus`) eklenmesi.
Sozlesme yonu: SUNUCU dogru kabul edilir, panel ona uyarlanir; yalniz
gercekten EKSIK olan seyler burada eklenir.
"""
import io
import sys

P = "mk_sunucu.py"
s = io.open(P, encoding="utf-8").read()
ilk = s

# ---------------------------------------------------------------- gosterge
# Panel `kullanici_etkin` bekliyor; mevcut sorgu ayni degeri `kullanici`
# adiyla donduruyor. `kullanici` TUM kullanicilari, `kullanici_etkin`
# yalniz etkin olanlari saymali.
ESKI_G = (
    '    t = db.tek(\n'
    '        "SELECT (SELECT count(*) FROM kullanicilar "\n'
    '        "        WHERE firma_id = %s AND durum = \'etkin\') AS kullanici, "\n'
)
YENI_G = (
    '    t = db.tek(\n'
    '        "SELECT (SELECT count(*) FROM kullanicilar "\n'
    '        "        WHERE firma_id = %s) AS kullanici, "\n'
    '        "(SELECT count(*) FROM kullanicilar WHERE firma_id = %s "\n'
    '        "        AND durum = \'etkin\') AS kullanici_etkin, "\n'
    '        "(SELECT count(*) FROM telemetri_ornekleri t "\n'
    '        "   JOIN ucus_kayitlari u ON u.ucus_id = t.ucus_id "\n'
    '        "  WHERE u.firma_id = %s) AS telemetri, "\n'
    '        "(SELECT coalesce(sum(mesafe_m), 0) FROM ucus_kayitlari "\n'
    '        "        WHERE firma_id = %s) AS toplam_mesafe_m, "\n'
)
if ESKI_G not in s:
    sys.exit("HATA: gosterge sorgu basi bulunamadi")
s = s.replace(ESKI_G, YENI_G, 1)

# Parametre sayisi 8 -> 12 (dort yeni alt sorgu eklendi)
ESKI_P = '        (fid,) * 8) or {}'
YENI_P = '        (fid,) * 12) or {}'
if ESKI_P not in s:
    sys.exit("HATA: gosterge parametre demeti bulunamadi")
s = s.replace(ESKI_P, YENI_P, 1)

# `dron_ucus`: en cok ucan dronlar (panelin tablosu)
ESKI_D = '    t["firma"] = db.tek('
YENI_D = (
    '    t["dron_ucus"] = db.sorgu(\n'
    '        "SELECT d.ad, d.yerel_uid, d.arac_turu, count(u.ucus_id) AS adet, "\n'
    '        "       coalesce(sum(u.sure_sn), 0) AS sure "\n'
    '        "FROM dronlar d "\n'
    '        "JOIN ucus_kayitlari u ON u.dron_id = d.dron_id "\n'
    '        "WHERE d.firma_id = %s "\n'
    '        "GROUP BY d.dron_id, d.ad, d.yerel_uid, d.arac_turu "\n'
    '        "ORDER BY adet DESC, sure DESC LIMIT 10", (fid,))\n'
    '    t["firma"] = db.tek('
)
s = s.replace(ESKI_D, YENI_D, 1)

# ---------------------------------------------------------------- yeni uclar
ANKRA = '@yol("GET", r"/api/firma/dronlar", yetki="firma")'
if ANKRA not in s:
    sys.exit("HATA: dronlar ucu bulunamadi")

EK = '''@yol("GET", r"/api/firma/ekip", yetki="firma")
def _u_firma_ekip(h, istek, oturum):
    """Firmanin kullanici listesi + kisi basi ucus ozeti.

    `api.kullanici_liste()` sayfali ve arama odakli oldugu icin panelin
    ekip sayfasi burada AYRI sorgu kullanir: ucus sayisi ve toplam sure
    kullanici bazinda toplanir. Pilot rolu de kendi ekibini gorur, cunku
    bu sayfa kisisel veri degil kurum rehberi niteligindedir; ancak ucus
    sayilari zaten kisi bazlidir, capraz veri sizmaz."""
    h.json_yaz({"kullanicilar": db.sorgu(
        "SELECT k.kullanici_id, k.eposta, k.ad, k.soyad, k.rol, k.durum, "
        "       k.son_giris_ts, k.olusma_ts, "
        "       (SELECT count(*) FROM ucus_kayitlari u "
        "          WHERE u.kullanici_id = k.kullanici_id) AS ucus_sayisi, "
        "       (SELECT coalesce(sum(u.sure_sn), 0) FROM ucus_kayitlari u "
        "          WHERE u.kullanici_id = k.kullanici_id) AS toplam_sure_sn "
        "FROM kullanicilar k WHERE k.firma_id = %s "
        "ORDER BY k.ad, k.soyad, k.eposta",
        (_firma_id(oturum),))})


@yol("GET", r"/api/firma/kurum", yetki="firma")
def _u_firma_kurum(h, istek, oturum):
    """Kurum kunyesi + kullanim ozeti (kota karsilastirmasi icin)."""
    fid = _firma_id(oturum)
    f = db.tek(
        "SELECT firma_id, unvan, kisa_ad, vergi_no, adres, telefon, eposta, "
        "       web, ulke, maks_kullanici, maks_sunucu, abonelik, "
        "       abonelik_bitis, durum, olusma_ts "
        "FROM firmalar WHERE firma_id = %s", (fid,))
    if not f:
        h.hata_yaz(404, "Kurum kaydı bulunamadı")
        return
    o = db.tek(
        "SELECT (SELECT count(*) FROM kullanicilar WHERE firma_id = %s) "
        "         AS kullanici, "
        "(SELECT count(*) FROM sunucu_ornekleri WHERE firma_id = %s "
        "        AND durum = 'etkin') AS sunucu, "
        "(SELECT count(*) FROM dronlar WHERE firma_id = %s) AS dron, "
        "(SELECT count(*) FROM ucus_kayitlari WHERE firma_id = %s) AS ucus, "
        "(SELECT coalesce(sum(sure_sn), 0) FROM ucus_kayitlari "
        "        WHERE firma_id = %s) AS toplam_sure_sn, "
        "(SELECT count(*) FROM video_kayitlari WHERE firma_id = %s "
        "        AND durum = 'hazir') AS video, "
        "(SELECT coalesce(sum(boyut_bayt), 0) FROM video_kayitlari "
        "        WHERE firma_id = %s AND durum = 'hazir') AS video_bayt",
        (fid,) * 7) or {}
    h.json_yaz({"firma": f, "ozet": o})


'''
s = s.replace(ANKRA, EK + ANKRA, 1)

if s == ilk:
    sys.exit("HATA: hicbir degisiklik uygulanmadi")
io.open(P, "w", encoding="utf-8").write(s)
print("mk_sunucu.py guncellendi:")
print(" - gosterge: kullanici_etkin, telemetri, toplam_mesafe_m, dron_ucus")
print(" - yeni uc: GET /api/firma/ekip")
print(" - yeni uc: GET /api/firma/kurum")
