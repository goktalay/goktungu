# -*- coding: utf-8 -*-
"""mk_sunucu.py dosyasina /api/firma/* uc noktalarini ekler.

Bu betik idempotenttir: ikinci calistirmada kendi imzasini tanir ve
hicbir sey yapmaz.
"""
import io
import sys

P = "mk_sunucu.py"
IMZA = "# FİRMA PANELİ (/company/) UÇ NOKTALARI"

BLOK = r'''
# ==========================================================================
# FİRMA PANELİ (/company/) UÇ NOKTALARI
# ==========================================================================
# Bu bolumdeki her uc `yetki="firma"` ile korunur ve YALNIZ oturum
# sahibinin firmasina ait veriyi dondurur. Firma kimligi ISTEK GOVDESINDEN
# DEGIL, oturumdan okunur; aksi halde bir musteri baska bir musterinin
# firma_id degerini gonderip verisini gorebilirdi. Bu ayrim panelin
# guvenlik temelidir ve degistirilmemelidir.


def _firma_id(oturum) -> int:
    return int(oturum["firma_id"])


def _pilot_kisitla(oturum, kid):
    """Pilot rolu YALNIZ kendi kayitlarini gorur; firma yoneticisi ve
    gozlemci firmanin tumunu gorur."""
    if oturum.get("rol") == "pilot":
        return int(oturum["kullanici_id"])
    return int(kid) if kid else None


@yol("POST", r"/api/firma/giris", yetki="acik")
def _u_firma_giris(h, istek, oturum):
    veri, hata = kimlik.kullanici_giris(
        (istek.govde.get("eposta") or "").strip(),
        istek.govde.get("sifre") or "",
        istek.ip, istek.h.headers.get("User-Agent"))
    if hata:
        h.json_yaz({"hata": hata}, 401)
        return
    # IS9B-CEREZ-ALANI: `Host` gecirilir; cerez kok alan adina baglanir.
    kurabiye = kimlik.kurabiye_yaz("goktungu_firma", veri["jeton"],
                                   istek.h.headers.get("Host"))
    h.json_yaz({"tamam": True, "kullanici": veri}, 200,
               {"Set-Cookie": kurabiye})


@yol("POST", r"/api/firma/cikis", yetki="firma")
def _u_firma_cikis(h, istek, oturum):
    kimlik.kullanici_cikis(oturum["jeton"])
    # IS9B-CEREZ-ALANI: silme dizesi yazma ile AYNI Domain'i tasir.
    h.json_yaz({"tamam": True}, 200,
               {"Set-Cookie": kimlik.kurabiye_sil(
                   "goktungu_firma", istek.h.headers.get("Host"))})


@yol("GET", r"/api/firma/ben", yetki="firma")
def _u_firma_ben(h, istek, oturum):
    # Oturum bitisi ve kalan sure YANITA KATILIR: tanitim sayfasi
    # kullanici menusunu bu bilgiyle yonetir ve sure dolunca kendini
    # kapatir.  Bunlar dondurulmezse arayuz oturumun ne zaman
    # dusecegini bilemez, kullanici da bos ekranla karsilasir.
    b = oturum.get("bitis_ts")
    try:
        bitis_iso = b.isoformat() if hasattr(b, "isoformat") else (
            str(b) if b else None)
    except Exception:
        bitis_iso = None
    kalan = None
    if hasattr(b, "timestamp"):
        try:
            simdi = dt.datetime.now(b.tzinfo) if b.tzinfo else \
                dt.datetime.now()
            kalan = max(0, int((b - simdi).total_seconds()))
        except Exception:
            kalan = None
    h.json_yaz({
        "kullanici": {a: oturum.get(a) for a in (
            "kullanici_id", "firma_id", "eposta", "ad", "soyad", "rol",
            "firma_unvan", "firma_kisa_ad")},
        "oturum": {
            "bitis_ts": bitis_iso,
            "kalan_sn": kalan,
            "omur_sn": kimlik.oturum_saniye(),
            # Kurumsal panel rol kapisi arayuzde de bilinmelidir: menu
            # ogesi yalniz yetkili kullaniciya gosterilir.  Sunucu kapisi
            # (_dosya_sun /company/) yine baskindir; bu alan gorunum
            # kararidir, guvenlik dayanagi degildir.
            "panel_yetkisi": str(oturum.get("rol")) == "firma_yonetici",
        },
    })


@yol("GET", r"/api/firma/gosterge", yetki="firma")
def _u_firma_gosterge(h, istek, oturum):
    """Firma ozeti. `api.gosterge()` TUM sistemi kapsadigi icin burada
    KULLANILAMAZ; firma sinirli sorgular ayrica yazilir."""
    fid = _firma_id(oturum)
    t = db.tek(
        "SELECT (SELECT count(*) FROM kullanicilar "
        "        WHERE firma_id = %s AND durum = 'etkin') AS kullanici, "
        "(SELECT count(*) FROM dronlar WHERE firma_id = %s) AS dron, "
        "(SELECT count(*) FROM ucus_kayitlari WHERE firma_id = %s) AS ucus, "
        "(SELECT coalesce(sum(sure_sn), 0) FROM ucus_kayitlari "
        "        WHERE firma_id = %s) AS toplam_sure_sn, "
        "(SELECT count(*) FROM ucus_kayitlari WHERE firma_id = %s "
        "        AND baslangic_ts > now() - interval '7 days') AS ucus_7gun, "
        "(SELECT count(*) FROM video_kayitlari WHERE firma_id = %s "
        "        AND durum = 'hazir') AS video, "
        "(SELECT coalesce(sum(boyut_bayt), 0) FROM video_kayitlari "
        "        WHERE firma_id = %s AND durum = 'hazir') AS video_bayt, "
        "(SELECT count(*) FROM sunucu_ornekleri WHERE firma_id = %s "
        "        AND durum = 'etkin') AS sunucu",
        (fid,) * 8) or {}
    sunucular = api.sunucu_liste(fid)
    t["sunucu_cevrimici"] = sum(1 for s in sunucular if s.get("cevrimici"))
    t["son_ucuslar"] = api.ucus_liste(firma_id=fid, boyut=10)["kayitlar"]
    t["gunluk_ucus"] = db.sorgu(
        "SELECT g::date AS gun, count(u.ucus_id) AS adet, "
        "       coalesce(sum(u.sure_sn), 0) AS sure_sn "
        "FROM generate_series(current_date - interval '13 days', "
        "                     current_date, interval '1 day') g "
        "LEFT JOIN ucus_kayitlari u ON u.baslangic_ts::date = g::date "
        "                          AND u.firma_id = %s "
        "GROUP BY g ORDER BY g", (fid,))
    t["firma"] = db.tek(
        "SELECT unvan, kisa_ad, maks_kullanici, maks_sunucu, paket, "
        "       durum, olusma_ts FROM firmalar WHERE firma_id = %s",
        (fid,)) or {}
    h.json_yaz(t)


@yol("GET", r"/api/firma/kullanicilar", yetki="firma")
def _u_firma_kullanicilar(h, istek, oturum):
    s = istek.sorgu
    h.json_yaz(api.kullanici_liste(
        _firma_id(oturum), s.get("arama") or None, s.get("rol") or None,
        int(s.get("sayfa", 1)), int(s.get("boyut", 50))))


@yol("GET", r"/api/firma/ucuslar", yetki="firma")
def _u_firma_ucuslar(h, istek, oturum):
    s = istek.sorgu
    h.json_yaz(api.ucus_liste(
        _firma_id(oturum), _pilot_kisitla(oturum, s.get("kullanici_id")),
        int(s["dron_id"]) if s.get("dron_id") else None,
        s.get("baslangic") or None, s.get("bitis") or None,
        int(s.get("sayfa", 1)), int(s.get("boyut", 50))))


def _firma_ucus_al(h, oturum, uid):
    """Ucus kaydini firma ve pilot sinirlarini DOGRULAYARAK dondurur.
    Yetkisizse yanit yazilir ve None doner."""
    u = api.ucus_getir(int(uid))
    if not u or int(u.get("firma_id") or 0) != _firma_id(oturum):
        h.hata_yaz(404, "Uçuş kaydı bulunamadı")
        return None
    if oturum.get("rol") == "pilot" and \
            int(u.get("kullanici_id") or 0) != int(oturum["kullanici_id"]):
        h.hata_yaz(403, "Bu uçuş kaydına erişim yetkiniz yok")
        return None
    return u


@yol("GET", r"/api/firma/ucuslar/(\d+)", yetki="firma")
def _u_firma_ucus_getir(h, istek, oturum, uid):
    u = _firma_ucus_al(h, oturum, uid)
    if u:
        h.json_yaz(u)


@yol("GET", r"/api/firma/ucuslar/(\d+)/telemetri", yetki="firma")
def _u_firma_ucus_telemetri(h, istek, oturum, uid):
    if _firma_ucus_al(h, oturum, uid):
        h.json_yaz({"kayitlar": api.ucus_telemetri(
            int(uid), int(istek.sorgu.get("seyreltme", 1)))})


@yol("GET", r"/api/firma/videolar", yetki="firma")
def _u_firma_videolar(h, istek, oturum):
    s = istek.sorgu
    h.json_yaz(api.video_liste(
        _firma_id(oturum), _pilot_kisitla(oturum, s.get("kullanici_id")),
        int(s["ucus_id"]) if s.get("ucus_id") else None,
        int(s.get("sayfa", 1)), int(s.get("boyut", 50))))


@yol("GET", r"/api/firma/videolar/(\d+)", yetki="firma")
def _u_firma_video_getir(h, istek, oturum, vid):
    v = api.video_getir(int(vid))
    if not v or int(v.get("firma_id") or 0) != _firma_id(oturum):
        h.hata_yaz(404, "Video kaydı bulunamadı")
        return
    h.json_yaz(v)


@yol("GET", r"/api/firma/videolar/(\d+)/akis", yetki="firma")
def _u_firma_video_akis(h, istek, oturum, vid):
    """Video oynatma. Yonetici ucuyla ayni mantik, firma sinirli."""
    v = api.video_getir(int(vid))
    if not v or int(v.get("firma_id") or 0) != _firma_id(oturum):
        h.hata_yaz(404, "Video kaydı bulunamadı")
        return
    if v["depo_yeri"] == "merkez" and v.get("dosya_yol"):
        hedef = os.path.normpath(os.path.join(VERI_KOKU, "video",
                                              v["dosya_yol"].lstrip("/")))
        if not os.path.isfile(hedef):
            h.hata_yaz(404, "Video dosyası merkezde bulunamadı")
            return
        istek.yol = "/video/" + v["dosya_yol"].lstrip("/")
        h._dosya_sun(istek)
        return
    if not v.get("ornek_id"):
        h.hata_yaz(409, "Video yerel sunucuda ve sunucu bilinmiyor")
        return
    veri, hata = kopruye_sor(int(v["ornek_id"]), "video_parca",
                             {"yerel_yol": v.get("yerel_yol"),
                              "video_uid": v.get("video_uid")}, 30.0)
    if hata:
        h.hata_yaz(503, f"Yerel sunucudan alınamadı: {hata}")
        return
    import base64
    govde = base64.b64decode((veri or {}).get("b64") or "")
    h._yaz(200, govde, (veri or {}).get("tur") or "video/mp4")


@yol("GET", r"/api/firma/sunucular", yetki="firma")
def _u_firma_sunucular(h, istek, oturum):
    """Firmanin kayitli GCS istasyonlari ve canli cevrimici durumu.
    `/app/` erisim kapisi bu ucu kullanir."""
    h.json_yaz({"kayitlar": api.sunucu_liste(_firma_id(oturum))})


@yol("GET", r"/api/firma/sunucular/(\d+)/sor/([a-z_]+)", yetki="firma")
def _u_firma_sunucu_sor(h, istek, oturum, oid, eylem):
    """Firmanin kendi istasyonuna canli koprü sorgusu (dron/port/servis).
    Ornegin SAHIBI dogrulanir; baska firmanin ornegi sorgulanamaz."""
    o = db.tek("SELECT firma_id FROM sunucu_ornekleri WHERE ornek_id = %s",
               (int(oid),))
    if not o or int(o["firma_id"]) != _firma_id(oturum):
        h.hata_yaz(404, "Sunucu bulunamadı")
        return
    veri, hata = kopruye_sor(int(oid), eylem, dict(istek.sorgu))
    if hata:
        h.hata_yaz(503, hata)
        return
    h.json_yaz(veri or {})


@yol("GET", r"/api/firma/dronlar", yetki="firma")
def _u_firma_dronlar(h, istek, oturum):
    h.json_yaz({"kayitlar": db.sorgu(
        "SELECT d.dron_id, d.dron_uid, d.ad, d.tur, d.sysid, d.otopilot, "
        "       d.seri_no, d.olusma_ts, "
        "       (SELECT count(*) FROM ucus_kayitlari u "
        "          WHERE u.dron_id = d.dron_id) AS ucus_sayisi, "
        "       (SELECT max(u.baslangic_ts) FROM ucus_kayitlari u "
        "          WHERE u.dron_id = d.dron_id) AS son_ucus_ts "
        "FROM dronlar d WHERE d.firma_id = %s ORDER BY d.ad",
        (_firma_id(oturum),))})

'''

IMZA_YER = ("# =========================================================="
            "================\n# WEBSOCKET — köprü ters bağlantıları\n")


def main() -> int:
    s = io.open(P, encoding="utf-8").read()
    if IMZA in s:
        print("ZATEN EKLENMIS — degisiklik yapilmadi")
        return 0
    if IMZA_YER not in s:
        print("HATA: WEBSOCKET bolum basligi bulunamadi")
        return 1
    n0 = len(s)
    s = s.replace(IMZA_YER, BLOK.lstrip("\n") + "\n" + IMZA_YER, 1)
    io.open(P, "w", encoding="utf-8").write(s)
    print("eklendi: %d -> %d bayt" % (n0, len(s)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
