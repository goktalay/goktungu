# -*- coding: utf-8 -*-
"""GÖKTUNGU MERKEZ — HTTP API iş mantığı.

Bu modül yalnız **veri** üretir; HTTP ayrıntıları `mk_sunucu.py`
içindedir. Böylece aynı işlevler sınav betiklerinden doğrudan
çağrılabilir.

Uç nokta grupları:

  `/api/admin/*`    sistem yöneticisi (tüm müşteriler)
  `/api/istemci/*`  firma kullanıcısı (yalnız kendi firması)
  `/api/genel/*`    kimliksiz (sunucu kimliği, sürüm bilgisi)
"""

from __future__ import annotations

import datetime as dt
import json
import secrets
from typing import Any

import mk_db as db
import mk_kimlik as kimlik
import mk_role as role
from mk_ayar import ayar_oku

SURUM = "1.0.0"


# ==========================================================================
# GENEL
# ==========================================================================
def sunucu_kimligi() -> dict[str, Any]:
    a = ayar_oku()
    return {
        "urun": "GOKTUNGU MERKEZ",
        "surum": SURUM,
        "kurum": a.get("kurum"),
        "alan_adi": a.get("alan_adi"),
        "ws_port": a.get("ws_port"),
        "sema_surum": db.deger("SELECT surum FROM sema_surum WHERE id = 1"),
    }


def saglik() -> dict[str, Any]:
    return {
        "durum": "ayakta",
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
        "havuz": db.havuz_durum(),
        "cevrimici_sunucu": role.ROLE.sayi(),
    }


# ==========================================================================
# ADMIN — MÜŞTERİLER (firmalar)
# ==========================================================================
def firma_liste(arama: str | None = None, durum: str | None = None,
                sayfa: int = 1, boyut: int = 50) -> dict[str, Any]:
    kosul: list[str] = []
    par: list[Any] = []
    if arama:
        kosul.append("(unvan ILIKE %s OR kisa_ad ILIKE %s OR "
                     "COALESCE(vergi_no,'') ILIKE %s)")
        par += [f"%{arama}%"] * 3
    if durum:
        kosul.append("durum = %s")
        par.append(durum)
    nerede = ("WHERE " + " AND ".join(kosul)) if kosul else ""
    toplam = db.deger(f"SELECT count(*) FROM v_firma_ozet {nerede}", tuple(par)) or 0
    boyut = max(1, min(int(boyut), 200))
    sayfa = max(1, int(sayfa))
    satirlar = db.sorgu(
        f"SELECT * FROM v_firma_ozet {nerede} ORDER BY kisa_ad "
        f"LIMIT %s OFFSET %s",
        tuple(par) + (boyut, (sayfa - 1) * boyut),
    )
    return {"toplam": int(toplam), "sayfa": sayfa, "boyut": boyut,
            "kayitlar": satirlar}


def firma_getir(firma_id: int) -> dict | None:
    f = db.tek("SELECT * FROM firmalar WHERE firma_id = %s", (firma_id,))
    if not f:
        return None
    f["ozet"] = db.tek("SELECT * FROM v_firma_ozet WHERE firma_id = %s",
                       (firma_id,))
    f["sunucular"] = db.sorgu(
        "SELECT ornek_id, kurulum_uid, ad, surum, platform, makine_adi, "
        "cevrimici, son_gorulme_ts, dron_sayisi, durum "
        "FROM sunucu_ornekleri WHERE firma_id = %s ORDER BY ad", (firma_id,))
    # Canlı röle durumu veritabanı işaretini geçersiz kılar
    canli = {s["kurulum_uid"] for s in role.ROLE.firma_sunuculari(firma_id)}
    for s in f["sunucular"]:
        s["cevrimici"] = s["kurulum_uid"] in canli
    return f


# Şemadaki CHECK kısıtlarının aynası (bkz. firmalar_abonelik_check)
ABONELIK_TURLERI = frozenset({"deneme", "standart", "kurumsal",
                              "sinirsiz", "bireysel"})
FIRMA_DURUMLARI = frozenset({"etkin", "askida", "iptal"})
# Firma turu: kurumsal = sirket kaydi (/company/ paneli kullanir),
# bireysel = sirkete bagli olmayan tek kullanici (panel kullanmaz,
# radar ve gccdual sema kisitiyla ZORUNLU kapali).
FIRMA_TURLERI = frozenset({"kurumsal", "bireysel"})
KULLANICI_ROLLERI = frozenset({"firma_yonetici", "pilot", "gozlemci"})

ALAN_FIRMA = ("unvan", "kisa_ad", "vergi_no", "vergi_dairesi", "adres",
              "telefon", "eposta", "web", "logo_yol", "ulke", "durum",
              "abonelik", "abonelik_bitis", "maks_kullanici", "maks_sunucu",
              "notlar", "tur", "pilot_koltuk", "ai_etkin",
              "radar_etkin", "gccdual_etkin")


def firma_ekle(veri: dict) -> tuple[int | None, str | None]:
    unvan = (veri.get("unvan") or "").strip()
    kisa = (veri.get("kisa_ad") or "").strip()
    if not unvan:
        return None, "Ünvan zorunlu"
    if not kisa:
        kisa = unvan[:40]
    vn = (veri.get("vergi_no") or "").strip()
    if vn and db.tek("SELECT 1 FROM firmalar WHERE vergi_no = %s", (vn,)):
        return None, "Bu vergi numarası zaten kayıtlı"
    # Şema kısıtları önceden doğrulanır; aksi halde çağıran
    # anlamsız bir CheckViolation izi alır.
    ab = (veri.get("abonelik") or "").strip()
    if ab and ab not in ABONELIK_TURLERI:
        return None, ("Geçersiz abonelik: " + ab + " (geçerli: "
                      + ", ".join(sorted(ABONELIK_TURLERI)) + ")")
    dr = (veri.get("durum") or "").strip()
    if dr and dr not in FIRMA_DURUMLARI:
        return None, ("Geçersiz durum: " + dr + " (geçerli: "
                      + ", ".join(sorted(FIRMA_DURUMLARI)) + ")")
    tr = (veri.get("tur") or "").strip()
    if tr and tr not in FIRMA_TURLERI:
        return None, ("Geçersiz firma türü: " + tr + " (geçerli: "
                      + ", ".join(sorted(FIRMA_TURLERI)) + ")")
    alanlar = ["unvan", "kisa_ad"]
    degerler: list[Any] = [unvan, kisa]
    for a in ALAN_FIRMA:
        if a in ("unvan", "kisa_ad"):
            continue
        if a in veri and veri[a] not in (None, ""):
            alanlar.append(a)
            degerler.append(veri[a])
    yer = ", ".join(["%s"] * len(alanlar))
    fid = db.deger(
        f"INSERT INTO firmalar ({', '.join(alanlar)}) VALUES ({yer}) "
        f"RETURNING firma_id", tuple(degerler))
    return int(fid), None


def firma_guncelle(firma_id: int, veri: dict) -> tuple[bool, str | None]:
    if not db.tek("SELECT 1 FROM firmalar WHERE firma_id = %s", (firma_id,)):
        return False, "Firma bulunamadı"
    atama: list[str] = []
    par: list[Any] = []
    for a in ALAN_FIRMA:
        if a in veri:
            atama.append(f"{a} = %s")
            par.append(veri[a] if veri[a] != "" else None)
    if not atama:
        return False, "Güncellenecek alan yok"
    atama.append("guncel_ts = now()")
    par.append(firma_id)
    db.calistir(f"UPDATE firmalar SET {', '.join(atama)} WHERE firma_id = %s",
                tuple(par))
    return True, None


def firma_sil(firma_id: int) -> tuple[bool, str | None]:
    """Müşteriyi ve tüm bağlı verisini siler (ON DELETE CASCADE)."""
    if not db.tek("SELECT 1 FROM firmalar WHERE firma_id = %s", (firma_id,)):
        return False, "Firma bulunamadı"
    db.calistir("DELETE FROM firmalar WHERE firma_id = %s", (firma_id,))
    return True, None


# ==========================================================================
# ADMIN — KULLANICILAR
# ==========================================================================
def kullanici_liste(firma_id: int | None = None, arama: str | None = None,
                    rol: str | None = None, sayfa: int = 1,
                    boyut: int = 50) -> dict[str, Any]:
    kosul: list[str] = []
    par: list[Any] = []
    if firma_id:
        kosul.append("firma_id = %s")
        par.append(firma_id)
    if arama:
        kosul.append("(eposta::text ILIKE %s OR ad_soyad ILIKE %s)")
        par += [f"%{arama}%"] * 2
    if rol:
        kosul.append("rol = %s")
        par.append(rol)
    nerede = ("WHERE " + " AND ".join(kosul)) if kosul else ""
    toplam = db.deger(f"SELECT count(*) FROM v_kullanici_ozet {nerede}",
                      tuple(par)) or 0
    boyut = max(1, min(int(boyut), 200))
    sayfa = max(1, int(sayfa))
    satirlar = db.sorgu(
        f"SELECT * FROM v_kullanici_ozet {nerede} "
        f"ORDER BY firma_kisa_ad, ad_soyad, eposta LIMIT %s OFFSET %s",
        tuple(par) + (boyut, (sayfa - 1) * boyut))
    for s in satirlar:
        s["eposta"] = str(s["eposta"])
    return {"toplam": int(toplam), "sayfa": sayfa, "boyut": boyut,
            "kayitlar": satirlar}


def kullanici_getir(kullanici_id: int) -> dict | None:
    k = db.tek("SELECT * FROM v_kullanici_ozet WHERE kullanici_id = %s",
               (kullanici_id,))
    if not k:
        return None
    k["eposta"] = str(k["eposta"])
    k["son_ucuslar"] = ucus_liste(kullanici_id=kullanici_id, boyut=10)["kayitlar"]
    return k


def kullanici_ekle(veri: dict) -> tuple[int | None, str | None]:
    try:
        firma_id = int(veri.get("firma_id") or 0)
    except (TypeError, ValueError):
        return None, "Geçersiz firma"
    if not firma_id:
        return None, "Firma zorunlu"
    eposta = (veri.get("eposta") or "").strip()
    if "@" not in eposta:
        return None, "Geçerli bir e-posta gerekli"
    sifre = veri.get("sifre") or ""
    rol = (veri.get("rol") or "pilot").strip()
    if rol not in KULLANICI_ROLLERI:
        return None, ("Geçersiz rol: " + rol + " (geçerli: "
                      + ", ".join(sorted(KULLANICI_ROLLERI)) + ")")
    kid, hata = kimlik.kullanici_olustur(
        firma_id, eposta, sifre, veri.get("ad") or "", veri.get("soyad") or "",
        rol, veri.get("telefon"))
    if kid and (veri.get("pilot_lisans") or veri.get("lisans_no")):
        db.calistir("UPDATE kullanicilar SET pilot_lisans = %s "
                    "WHERE kullanici_id = %s",
                    (veri.get("pilot_lisans") or veri.get("lisans_no"), kid))
    return kid, hata


def kullanici_guncelle(kullanici_id: int, veri: dict) -> tuple[bool, str | None]:
    mevcut = db.tek(
        "SELECT firma_id, rol, durum FROM kullanicilar WHERE kullanici_id = %s",
        (kullanici_id,))
    if not mevcut:
        return False, "Kullanıcı bulunamadı"
    if veri.get("rol") and veri["rol"] not in KULLANICI_ROLLERI:
        return False, ("Geçersiz rol: " + str(veri["rol"]) + " (geçerli: "
                       + ", ".join(sorted(KULLANICI_ROLLERI)) + ")")
    if veri.get("durum") and veri["durum"] not in FIRMA_DURUMLARI:
        return False, ("Geçersiz durum: " + str(veri["durum"]) + " (geçerli: "
                       + ", ".join(sorted(FIRMA_DURUMLARI)) + ")")

    # v2.4.65 — KOLTUK DENETİMİ GÜNCELLEMEDE DE UYGULANIR.
    #
    # NEDEN: yalnız oluşturma denetlenirse şirket 20 pilotu `pasif`
    # oluşturup sonra hepsini `etkin` yaparak koltuk sınırını atlar.
    # Aynı boşluk `gozlemci` olarak açıp sonra `pilot` rolüne
    # çevirmekle de kullanılabilir. Bu yüzden iki geçiş de denetlenir:
    #   (a) pasif -> etkin  ve hedef rol pilot
    #   (b) pilot olmayan -> pilot  ve kayıt etkin kalıyor
    yeni_rol = veri.get("rol") or mevcut["rol"]
    yeni_durum = veri.get("durum") or mevcut["durum"]
    etkinlesiyor = (mevcut["durum"] != "etkin" and yeni_durum == "etkin")
    pilota_geciyor = (mevcut["rol"] != "pilot" and yeni_rol == "pilot"
                      and yeni_durum == "etkin")
    if etkinlesiyor or pilota_geciyor:
        import mk_yetki as yetki
        uygun, hata = yetki.koltuk_uygun_mu(int(mevcut["firma_id"]), yeni_rol)
        if not uygun:
            return False, hata

    atama: list[str] = []
    par: list[Any] = []
    for a in ("ad", "soyad", "telefon", "rol", "durum", "pilot_lisans",
              "avatar_yol"):
        if a in veri:
            atama.append(f"{a} = %s")
            par.append(veri[a] if veri[a] != "" else None)
    # Arabirimde "lisans_no" adı kullanılıyorsa şemadaki kolona eşlenir
    if "lisans_no" in veri and "pilot_lisans" not in veri:
        atama.append("pilot_lisans = %s")
        par.append(veri["lisans_no"] or None)
    if veri.get("sifre"):
        hata = kimlik.sifre_gucu(veri["sifre"])
        if hata:
            return False, hata
        atama.append("sifre_ozet = %s")
        par.append(kimlik.sifre_ozetle(veri["sifre"]))
    if not atama:
        return False, "Güncellenecek alan yok"
    atama.append("guncel_ts = now()")
    par.append(kullanici_id)
    db.calistir(
        f"UPDATE kullanicilar SET {', '.join(atama)} WHERE kullanici_id = %s",
        tuple(par))
    return True, None


def kullanici_sil(kullanici_id: int) -> tuple[bool, str | None]:
    if not db.tek("SELECT 1 FROM kullanicilar WHERE kullanici_id = %s",
                  (kullanici_id,)):
        return False, "Kullanıcı bulunamadı"
    db.calistir("DELETE FROM kullanicilar WHERE kullanici_id = %s",
                (kullanici_id,))
    return True, None


# ==========================================================================
# UÇUŞ KAYITLARI
# ==========================================================================
def ucus_liste(firma_id: int | None = None, kullanici_id: int | None = None,
               dron_id: int | None = None, baslangic: str | None = None,
               bitis: str | None = None, sayfa: int = 1,
               boyut: int = 50) -> dict[str, Any]:
    kosul: list[str] = []
    par: list[Any] = []
    if firma_id:
        kosul.append("firma_id = %s")
        par.append(firma_id)
    if kullanici_id:
        kosul.append("kullanici_id = %s")
        par.append(kullanici_id)
    if dron_id:
        kosul.append("dron_id = %s")
        par.append(dron_id)
    if baslangic:
        kosul.append("baslangic_ts >= %s")
        par.append(baslangic)
    if bitis:
        kosul.append("baslangic_ts <= %s")
        par.append(bitis)
    nerede = ("WHERE " + " AND ".join(kosul)) if kosul else ""
    toplam = db.deger(f"SELECT count(*) FROM v_ucus_liste {nerede}",
                      tuple(par)) or 0
    boyut = max(1, min(int(boyut), 200))
    sayfa = max(1, int(sayfa))
    satirlar = db.sorgu(
        f"SELECT * FROM v_ucus_liste {nerede} ORDER BY baslangic_ts DESC "
        f"LIMIT %s OFFSET %s",
        tuple(par) + (boyut, (sayfa - 1) * boyut))
    return {"toplam": int(toplam), "sayfa": sayfa, "boyut": boyut,
            "kayitlar": satirlar}


def ucus_getir(ucus_id: int) -> dict | None:
    u = db.tek("SELECT * FROM v_ucus_liste WHERE ucus_id = %s", (ucus_id,))
    if not u:
        return None
    ham = db.tek("SELECT kalkis_kontrol, ozet, kalkis_lat, kalkis_lon, "
                 "inis_lat, inis_lon, ornek_sayisi, maks_hiz_ms "
                 "FROM ucus_kayitlari WHERE ucus_id = %s", (ucus_id,))
    u.update(ham or {})
    # Panel ayrıntı penceresi için ek alanlar
    ek = db.tek(
        "SELECT f.unvan AS firma_unvan, k.eposta AS pilot_eposta, "
        "       d.sysid, d.otopilot, d.seri_no "
        "FROM ucus_kayitlari u "
        "JOIN firmalar f ON f.firma_id = u.firma_id "
        "LEFT JOIN kullanicilar k ON k.kullanici_id = u.kullanici_id "
        "LEFT JOIN dronlar d ON d.dron_id = u.dron_id "
        "WHERE u.ucus_id = %s", (ucus_id,))
    u.update(ek or {})
    u["telemetri_sayisi"] = int(db.deger(
        "SELECT count(*) FROM ucus_telemetri WHERE ucus_id = %s",
        (ucus_id,)) or 0)
    u["videolar"] = db.sorgu(
        "SELECT video_id, video_uid, baslik, kaynak, baslangic_ts, sure_sn, "
        "boyut_bayt, cozunurluk, depo_yeri, durum, onizleme_yol "
        "FROM video_kayitlari WHERE ucus_id = %s ORDER BY baslangic_ts",
        (ucus_id,))
    return u


def ucus_telemetri(ucus_id: int, seyreltme: int = 1) -> list[dict]:
    """Grafik için telemetri örnekleri. `seyreltme` her N'inci örneği alır."""
    seyreltme = max(1, min(int(seyreltme), 100))
    return db.sorgu(
        "SELECT ts, lat, lon, irtifa_m, hiz_ms, yon_derece, batarya_v, "
        "       batarya_yuzde, uydu_sayisi, mod "
        "FROM (SELECT *, row_number() OVER (ORDER BY ts) AS sira "
        "        FROM ucus_telemetri WHERE ucus_id = %s) t "
        "WHERE (sira - 1) %% %s = 0 ORDER BY ts",
        (ucus_id, seyreltme))


def ucus_yaz(firma_id: int, veri: dict,
             ornek_id: int | None = None) -> tuple[int | None, str | None]:
    """Köprüden gelen uçuş kaydını merkeze işler (upsert)."""
    uid = (veri.get("ucus_uid") or "").strip() or secrets.token_hex(5).upper()
    bas = veri.get("baslangic_ts")
    if not bas:
        return None, "baslangic_ts zorunlu"

    kullanici_id = None
    if veri.get("pilot_eposta"):
        kullanici_id = db.deger(
            "SELECT kullanici_id FROM kullanicilar WHERE eposta = %s "
            "AND firma_id = %s", (veri["pilot_eposta"], firma_id))

    dron_id = None
    if veri.get("dron_uid"):
        dron_id = _dron_kaydet(firma_id, ornek_id, veri)

    mevcut = db.tek("SELECT ucus_id FROM ucus_kayitlari WHERE ucus_uid = %s",
                    (uid,))
    alanlar = {
        "firma_id": firma_id,
        "kullanici_id": kullanici_id,
        "dron_id": dron_id,
        "ornek_id": ornek_id,
        "pilot_ad": veri.get("pilot_ad"),
        "dron_ad": veri.get("dron_ad"),
        "arac_turu": veri.get("arac_turu"),
        "baslangic_ts": bas,
        "bitis_ts": veri.get("bitis_ts"),
        "sure_sn": veri.get("sure_sn"),
        "mesafe_m": veri.get("mesafe_m"),
        "maks_irtifa_m": veri.get("maks_irtifa_m"),
        "maks_hiz_ms": veri.get("maks_hiz_ms"),
        "kalkis_lat": veri.get("kalkis_lat"),
        "kalkis_lon": veri.get("kalkis_lon"),
        "inis_lat": veri.get("inis_lat"),
        "inis_lon": veri.get("inis_lon"),
        "gorev_turu": veri.get("gorev_turu"),
        "gorev_durumu": veri.get("gorev_durumu"),
        "ornek_sayisi": veri.get("ornek_sayisi") or 0,
        "kalkis_kontrol": json.dumps(veri.get("kalkis_kontrol") or None,
                                     ensure_ascii=False)
        if veri.get("kalkis_kontrol") is not None else None,
        "ozet": json.dumps(veri.get("ozet") or {}, ensure_ascii=False),
    }
    if mevcut:
        # Kısmi güncelleme: köprü yalnızca değişen alanları gönderebilir.
        # Gönderilmeyen alan NULL'a ezilmemeli, mevcut değer korunmalı.
        # (firma_id ve baslangic_ts her zaman doludur, doğrudan yazılır.)
        dogrudan = {"firma_id", "baslangic_ts"}
        atamalar: list[str] = []
        par: list[Any] = []
        for a, d in alanlar.items():
            if a in dogrudan:
                atamalar.append(f"{a} = %s")
                par.append(d)
            elif a == "ornek_sayisi":
                # 0 anlamlı bir değer değil; yalnız artışta güncellenir
                atamalar.append(f"{a} = GREATEST({a}, %s)")
                par.append(d)
            else:
                atamalar.append(f"{a} = COALESCE(%s, {a})")
                par.append(d)
        par.append(mevcut["ucus_id"])
        db.calistir(
            f"UPDATE ucus_kayitlari SET {', '.join(atamalar)}, "
            f"senk_ts = now() WHERE ucus_id = %s", tuple(par))
        return int(mevcut["ucus_id"]), None

    adlar = ["ucus_uid"] + list(alanlar)
    degerler = [uid] + list(alanlar.values())
    yer = ", ".join(["%s"] * len(adlar))
    ucus_id = db.deger(
        f"INSERT INTO ucus_kayitlari ({', '.join(adlar)}) VALUES ({yer}) "
        f"RETURNING ucus_id", tuple(degerler))
    return int(ucus_id), None


def _dron_kaydet(firma_id: int, ornek_id: int | None, veri: dict) -> int:
    uid = str(veri["dron_uid"])
    d = db.tek("SELECT dron_id FROM dronlar WHERE firma_id = %s AND "
               "yerel_uid = %s", (firma_id, uid))
    if d:
        db.calistir(
            "UPDATE dronlar SET son_gorulme_ts = now(), "
            "ad = COALESCE(%s, ad), arac_turu = COALESCE(%s, arac_turu), "
            "ornek_id = COALESCE(%s, ornek_id) WHERE dron_id = %s",
            (veri.get("dron_ad"), veri.get("arac_turu"), ornek_id,
             d["dron_id"]))
        return int(d["dron_id"])
    return int(db.deger(
        "INSERT INTO dronlar (firma_id, ornek_id, yerel_uid, sysid, ad, "
        "arac_turu, otopilot, seri_no, son_gorulme_ts) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now()) RETURNING dron_id",
        (firma_id, ornek_id, uid, veri.get("sysid"), veri.get("dron_ad"),
         veri.get("arac_turu"), veri.get("otopilot"), veri.get("seri_no"))))


def telemetri_yaz(ucus_id: int, ornekler: list[dict]) -> int:
    """Telemetri örneklerini toplu yazar; mükerrer zaman damgası atlanır."""
    if not ornekler:
        return 0
    satirlar = []
    for o in ornekler:
        if not o.get("ts"):
            continue
        satirlar.append((
            ucus_id, o["ts"], o.get("lat"), o.get("lon"), o.get("irtifa_m"),
            o.get("hiz_ms"), o.get("yon_derece"), o.get("batarya_v"),
            o.get("batarya_yuzde"), o.get("uydu_sayisi"), o.get("mod"),
            json.dumps(o.get("ek") or {}, ensure_ascii=False),
        ))
    if not satirlar:
        return 0
    import psycopg2.extras as _ex
    with db.imlec(sozluk=False) as cur:
        _ex.execute_values(
            cur,
            "INSERT INTO ucus_telemetri (ucus_id, ts, lat, lon, irtifa_m, "
            "hiz_ms, yon_derece, batarya_v, batarya_yuzde, uydu_sayisi, mod, ek) "
            "VALUES %s ON CONFLICT (ucus_id, ts) DO NOTHING",
            satirlar, page_size=500)
    db.calistir(
        "UPDATE ucus_kayitlari SET ornek_sayisi = "
        "(SELECT count(*) FROM ucus_telemetri WHERE ucus_id = %s) "
        "WHERE ucus_id = %s", (ucus_id, ucus_id))
    return len(satirlar)


# ==========================================================================
# VİDEO KAYITLARI
# ==========================================================================
def video_liste(firma_id: int | None = None, kullanici_id: int | None = None,
                ucus_id: int | None = None, sayfa: int = 1,
                boyut: int = 50) -> dict[str, Any]:
    kosul = ["v.durum <> 'silindi'"]
    par: list[Any] = []
    if firma_id:
        kosul.append("v.firma_id = %s")
        par.append(firma_id)
    if kullanici_id:
        kosul.append("v.kullanici_id = %s")
        par.append(kullanici_id)
    if ucus_id:
        kosul.append("v.ucus_id = %s")
        par.append(ucus_id)
    nerede = "WHERE " + " AND ".join(kosul)
    toplam = db.deger(
        f"SELECT count(*) FROM video_kayitlari v {nerede}", tuple(par)) or 0
    boyut = max(1, min(int(boyut), 200))
    sayfa = max(1, int(sayfa))
    satirlar = db.sorgu(
        "SELECT v.video_id, v.video_uid, v.firma_id, f.kisa_ad AS firma_kisa_ad, "
        "       v.ucus_id, u.ucus_uid, v.kullanici_id, "
        "       trim(COALESCE(k.ad,'') || ' ' || COALESCE(k.soyad,'')) AS pilot, "
        "       v.dron_id, d.ad AS dron, v.kaynak, v.baslik, v.baslangic_ts, "
        "       v.sure_sn, v.boyut_bayt, v.cozunurluk, v.kodek, v.depo_yeri, "
        "       v.durum, v.onizleme_yol, v.ornek_id, s.ad AS sunucu_ad, "
        "       s.cevrimici AS sunucu_cevrimici "
        "FROM video_kayitlari v "
        "JOIN firmalar f ON f.firma_id = v.firma_id "
        "LEFT JOIN ucus_kayitlari u ON u.ucus_id = v.ucus_id "
        "LEFT JOIN kullanicilar k ON k.kullanici_id = v.kullanici_id "
        "LEFT JOIN dronlar d ON d.dron_id = v.dron_id "
        "LEFT JOIN sunucu_ornekleri s ON s.ornek_id = v.ornek_id "
        f"{nerede} ORDER BY v.baslangic_ts DESC LIMIT %s OFFSET %s",
        tuple(par) + (boyut, (sayfa - 1) * boyut))
    return {"toplam": int(toplam), "sayfa": sayfa, "boyut": boyut,
            "kayitlar": satirlar}


def video_getir(video_id: int) -> dict | None:
    """Video ayrıntısı.

    Panel; videoyu barındıran sunucunun **canlı** durumunu gösterir:
    `depo_yeri='yerel'` olan kayıtlar yalnız kaynak köprü çevrimiçiyken
    izlenebilir, bu nedenle veritabanındaki `cevrimici` işareti röle
    durumuyla geçersiz kılınır.
    """
    v = db.tek(
        "SELECT v.*, f.kisa_ad AS firma_kisa_ad, f.unvan AS firma_unvan, "
        "       s.kurulum_uid, s.ad AS sunucu_ad, "
        "       s.cevrimici AS sunucu_cevrimici, "
        "       u.ucus_uid, "
        "       trim(COALESCE(k.ad,'') || ' ' || COALESCE(k.soyad,'')) AS pilot, "
        "       k.eposta AS pilot_eposta, d.ad AS dron "
        "FROM video_kayitlari v "
        "JOIN firmalar f ON f.firma_id = v.firma_id "
        "LEFT JOIN sunucu_ornekleri s ON s.ornek_id = v.ornek_id "
        "LEFT JOIN ucus_kayitlari u ON u.ucus_id = v.ucus_id "
        "LEFT JOIN kullanicilar k ON k.kullanici_id = v.kullanici_id "
        "LEFT JOIN dronlar d ON d.dron_id = v.dron_id "
        "WHERE v.video_id = %s", (video_id,))
    if not v:
        return None
    if v.get("pilot_eposta") is not None:
        v["pilot_eposta"] = str(v["pilot_eposta"])
    if v.get("kurulum_uid"):
        v["sunucu_cevrimici"] = role.ROLE.uid_ile(v["kurulum_uid"]) is not None
    return v


def video_yaz(firma_id: int, veri: dict,
              ornek_id: int | None = None) -> tuple[int | None, str | None]:
    uid = (veri.get("video_uid") or "").strip() or secrets.token_hex(6).upper()
    if not veri.get("baslangic_ts"):
        return None, "baslangic_ts zorunlu"
    ucus_id = None
    if veri.get("ucus_uid"):
        ucus_id = db.deger("SELECT ucus_id FROM ucus_kayitlari WHERE ucus_uid = %s",
                           (veri["ucus_uid"],))
    kullanici_id = None
    if veri.get("pilot_eposta"):
        kullanici_id = db.deger(
            "SELECT kullanici_id FROM kullanicilar WHERE eposta = %s AND "
            "firma_id = %s", (veri["pilot_eposta"], firma_id))
    alanlar = {
        "firma_id": firma_id, "ucus_id": ucus_id, "kullanici_id": kullanici_id,
        "ornek_id": ornek_id, "kaynak": veri.get("kaynak"),
        "baslik": veri.get("baslik"), "baslangic_ts": veri["baslangic_ts"],
        "bitis_ts": veri.get("bitis_ts"), "sure_sn": veri.get("sure_sn"),
        "boyut_bayt": veri.get("boyut_bayt"),
        "cozunurluk": veri.get("cozunurluk"), "kodek": veri.get("kodek"),
        "depo_yeri": veri.get("depo_yeri") or "yerel",
        "dosya_yol": veri.get("dosya_yol"), "yerel_yol": veri.get("yerel_yol"),
        "onizleme_yol": veri.get("onizleme_yol"),
        "ozet_sha256": veri.get("ozet_sha256"),
        "durum": veri.get("durum") or "hazir",
    }
    mevcut = db.tek("SELECT video_id FROM video_kayitlari WHERE video_uid = %s",
                    (uid,))
    if mevcut:
        # Kısmi güncelleme: gönderilmeyen alan NULL'a ezilmez
        # (ucus_yaz ile aynı gerekçe; bkz. sınav bölüm 4).
        dogrudan = {"firma_id", "baslangic_ts", "depo_yeri", "durum"}
        atamalar: list[str] = []
        par2: list[Any] = []
        for a, d in alanlar.items():
            if a in dogrudan:
                atamalar.append(f"{a} = %s")
                par2.append(d)
            else:
                atamalar.append(f"{a} = COALESCE(%s, {a})")
                par2.append(d)
        par2.append(mevcut["video_id"])
        db.calistir(
            f"UPDATE video_kayitlari SET {', '.join(atamalar)}, "
            f"senk_ts = now() WHERE video_id = %s", tuple(par2))
        return int(mevcut["video_id"]), None
    adlar = ["video_uid"] + list(alanlar)
    yer = ", ".join(["%s"] * len(adlar))
    vid = db.deger(
        f"INSERT INTO video_kayitlari ({', '.join(adlar)}) VALUES ({yer}) "
        f"RETURNING video_id", tuple([uid] + list(alanlar.values())))
    return int(vid), None


# ==========================================================================
# SUNUCU ÖRNEKLERİ
# ==========================================================================
def sunucu_liste(firma_id: int | None = None) -> list[dict]:
    kosul = "WHERE s.firma_id = %s" if firma_id else ""
    par = (firma_id,) if firma_id else ()
    satirlar = db.sorgu(
        "SELECT s.ornek_id, s.kurulum_uid, s.firma_id, f.kisa_ad AS firma_kisa_ad, "
        "       s.ad, s.aciklama, s.surum, s.platform, s.makine_adi, "
        "       s.cevrimici, s.son_gorulme_ts, s.son_ip, s.dron_sayisi, "
        "       s.yetenekler, s.durum, s.olusma_ts, s.urun, s.api_kodu "
        f"FROM sunucu_ornekleri s JOIN firmalar f ON f.firma_id = s.firma_id "
        f"{kosul} ORDER BY f.kisa_ad, s.ad", par)
    canli = {o["kurulum_uid"]: o for o in role.ROLE.tumu()}
    for s in satirlar:
        c = canli.get(s["kurulum_uid"])
        s["cevrimici"] = c is not None
        if c:
            s["son_nabiz_sn"] = c.get("son_nabiz_sn")
            s["kanal"] = c.get("kanal")
            s["dron_sayisi"] = c.get("dron_sayisi", s["dron_sayisi"])
    return satirlar


def sunucu_ekle(firma_id: int, ad: str, aciklama: str | None = None,
                urun: str = "kopru") -> tuple[dict | None, str | None]:
    if not (ad or "").strip():
        return None, "Sunucu adı zorunlu"
    return role.ornek_kaydet(firma_id, ad.strip(), aciklama, urun=urun)


def sunucu_sil(ornek_id: int) -> tuple[bool, str | None]:
    if not db.tek("SELECT 1 FROM sunucu_ornekleri WHERE ornek_id = %s",
                  (ornek_id,)):
        return False, "Sunucu bulunamadı"
    db.calistir("DELETE FROM sunucu_ornekleri WHERE ornek_id = %s", (ornek_id,))
    return True, None


def acik_sunucular(firma_id: int) -> list[dict]:
    """Bağlantı yöneticisi için: **şu an açık** olan sunucular.

    Kullanıcı yeni bağlantı eklerken bu listeden seçer. Liste canlı
    röle kayıtlarından üretilir; veritabanındaki `cevrimici` işareti
    yalnız yedek bilgidir.
    """
    canli = role.ROLE.firma_sunuculari(firma_id)
    if not canli:
        return []
    uidler = [c["kurulum_uid"] for c in canli]
    kayitlar = {
        r["kurulum_uid"]: r for r in db.sorgu(
            "SELECT ornek_id, kurulum_uid, ad, aciklama, surum, platform, "
            "makine_adi FROM sunucu_ornekleri WHERE kurulum_uid = ANY(%s) "
            "AND durum = 'etkin'", (uidler,))
    }
    sonuc = []
    for c in canli:
        k = kayitlar.get(c["kurulum_uid"])
        if not k:
            continue
        sonuc.append({
            "ornek_id": k["ornek_id"],
            "kurulum_uid": k["kurulum_uid"],
            "ad": k["ad"],
            "aciklama": k["aciklama"],
            "surum": c.get("surum") or k["surum"],
            "platform": c.get("platform") or k["platform"],
            "makine_adi": c.get("makine_adi") or k["makine_adi"],
            "dron_sayisi": c.get("dron_sayisi", 0),
            "yetenekler": c.get("yetenekler") or {},
            "son_nabiz_sn": c.get("son_nabiz_sn"),
        })
    sonuc.sort(key=lambda x: (x["ad"] or "").lower())
    return sonuc


# ==========================================================================
# GÖSTERGE PANELİ
# ==========================================================================
def gosterge() -> dict[str, Any]:
    t = db.tek(
        "SELECT (SELECT count(*) FROM firmalar) AS firma, "
        "(SELECT count(*) FROM firmalar WHERE durum='etkin') AS firma_etkin, "
        "(SELECT count(*) FROM kullanicilar) AS kullanici, "
        "(SELECT count(*) FROM kullanicilar WHERE durum='etkin') "
        "    AS kullanici_etkin, "
        "(SELECT count(*) FROM dronlar) AS dron, "
        "(SELECT count(*) FROM ucus_kayitlari) AS ucus, "
        "(SELECT count(*) FROM video_kayitlari WHERE durum='hazir') AS video, "
        "(SELECT coalesce(sum(boyut_bayt),0) FROM video_kayitlari "
        " WHERE durum='hazir') AS video_bayt, "
        "(SELECT count(*) FROM sunucu_ornekleri WHERE durum='etkin') AS sunucu, "
        "(SELECT coalesce(sum(sure_sn),0) FROM ucus_kayitlari) "
        "    AS toplam_sure_sn, "
        "(SELECT count(*) FROM ucus_telemetri) AS telemetri, "
        "(SELECT count(*) FROM ucus_kayitlari "
        " WHERE baslangic_ts > now() - interval '7 days') AS ucus_7gun"
    ) or {}
    t["sunucu_cevrimici"] = role.ROLE.sayi()
    t["son_ucuslar"] = ucus_liste(boyut=10)["kayitlar"]
    # Son 14 gunun her gunu icin satir uretilir; ucus olmayan gun 0 gorunur
    t["gunluk_ucus"] = db.sorgu(
        "SELECT g::date AS gun, "
        "       count(u.ucus_id) AS adet, "
        "       coalesce(sum(u.sure_sn),0) AS sure_sn "
        "FROM generate_series(current_date - interval '13 days', "
        "                     current_date, interval '1 day') AS g "
        "LEFT JOIN ucus_kayitlari u "
        "       ON u.baslangic_ts >= g AND u.baslangic_ts < g + interval '1 day' "
        "GROUP BY 1 ORDER BY 1")
    t["firma_ucus"] = db.sorgu(
        "SELECT f.kisa_ad, count(u.ucus_id) AS adet, "
        "       coalesce(sum(u.sure_sn),0) AS sure "
        "FROM firmalar f LEFT JOIN ucus_kayitlari u ON u.firma_id = f.firma_id "
        "GROUP BY f.kisa_ad HAVING count(u.ucus_id) > 0 "
        "ORDER BY adet DESC LIMIT 10")
    return t


def denetim_liste(sayfa: int = 1, boyut: int = 100) -> dict[str, Any]:
    boyut = max(1, min(int(boyut), 500))
    sayfa = max(1, int(sayfa))
    toplam = db.deger("SELECT count(*) FROM sistem_denetim") or 0
    satirlar = db.sorgu(
        "SELECT d.denetim_id, d.eylem, d.hedef_tur, d.hedef_id, d.ayrinti, "
        "       d.ip, d.ts, y.eposta AS yonetici "
        "FROM sistem_denetim d "
        "LEFT JOIN sistem_yoneticileri y ON y.yonetici_id = d.yonetici_id "
        "ORDER BY d.ts DESC LIMIT %s OFFSET %s",
        (boyut, (sayfa - 1) * boyut))
    for s in satirlar:
        if s.get("yonetici"):
            s["yonetici"] = str(s["yonetici"])
        s["yonetici_eposta"] = s.get("yonetici")
    return {"toplam": int(toplam), "sayfa": sayfa, "boyut": boyut,
            "kayitlar": satirlar}


# ==========================================================================
# GÜNCELLEME DEPOSU (sürümler)
# ==========================================================================
def surum_liste(urun: str | None = None,
                sadece_yayinda: bool = False) -> dict[str, Any]:
    kosul: list[str] = []
    par: list[Any] = []
    if urun:
        kosul.append("urun = %s")
        par.append(urun)
    if sadece_yayinda:
        kosul.append("etkin = true")
    nerede = ("WHERE " + " AND ".join(kosul)) if kosul else ""
    satirlar = db.sorgu(
        f"SELECT surum_id, urun, surum, platform, kanal, paket_tur, "
        f"       dosya_ad, dosya_boyut, sha256, imza, asgari_surum, "
        f"       etkin, yayin_ts, notlar "
        f"FROM surumler {nerede} "
        f"ORDER BY yayin_ts DESC, surum_id DESC", tuple(par))
    # Panelin beklediği ortak adlar
    for s in satirlar:
        s["paket_turu"] = s.get("paket_tur")
        s["boyut_bayt"] = s.get("dosya_boyut")
        s["durum"] = "yayinda" if s.get("etkin") else "pasif"
    return {"toplam": len(satirlar), "kayitlar": satirlar}
