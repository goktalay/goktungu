# -*- coding: utf-8 -*-
"""GÖKTUNGU MERKEZ — kimlik doğrulama ve oturum yönetimi.

İki ayrı kimlik alanı vardır ve **birbirine karışmaz**:

  1. Sistem yöneticileri (`sistem_yoneticileri`) — VEILOX personeli,
     `/admin` panelini kullanır, tüm müşterileri görür.
  2. Firma kullanıcıları (`kullanicilar`) — müşteri pilotları ve firma
     yöneticileri, yalnız kendi firmasının verisini görür.

Şifreler PBKDF2-HMAC-SHA256 ile saklanır. Tuz her kayıt için ayrı
üretilir ve özet dizesinin içine gömülür:

    pbkdf2_sha256$<yineleme>$<tuz_b64>$<ozet_b64>
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import os
import secrets

from mk_ayar import ayar_oku
import mk_db as db

YINELEME = 240_000
_AYIRAC = "$"
_ETIKET = "pbkdf2_sha256"


# --------------------------------------------------------------------------
# Oturum ömrü
# --------------------------------------------------------------------------
# TEK KAYNAK: oturum süresi yalnız `ayar_oku()["oturum_saat"]` üzerinden
# belirlenir.  Bu yardımcılar eklenmeden önce jetonun veritabanı bitisi
# ayardan, kurabiyenin `Max-Age` degeri ise DORT AYRI YERDE sabit
# `12 * 3600` ifadesinden geliyordu (mk_sunucu.py 648/1270/1287,
# ek_firma_uclari.py 46, ek_kayit_ucu.py 125).  Ayar 12'den farklı
# yapıldığında ikisi ayrışıyordu: ayar 24 ise kurabiye 12 saatte silinip
# kullanıcı jetonu geçerliyken dışarı atılıyor, ayar 6 ise kurabiye 12 saat
# yaşayıp her istek 401 dönüyordu.  Kurabiye üreten her yer artik
# `kurabiye_yaz()` cagirmalidir.
def oturum_saniye() -> int:
    """Yapılandırılmış oturum ömrü (saniye). En az 1 saat."""
    try:
        saat = int(ayar_oku().get("oturum_saat", 12))
    except (TypeError, ValueError):
        saat = 12
    return max(1, saat) * 3600


def _cerez_alani(host: str | None) -> str | None:
    """Set-Cookie icin `Domain` degeri (nokta onekli) veya None.

    IS9B-CEREZ-ALANI: dort panel AYRI ALT ALAN ADLARINDA calisir
    (`app.`, `admin.`, `company.`, `support.`).  Domain yazilmazsa
    tarayici cerezi yalniz yazan tam ana bilgisayar adina baglar ve
    `company.` uzerinde acilan oturum `app.` tarafinda GORUNMEZ:
    kullanici ayni tarayicida ikinci kez giris yapmak zorunda kalir
    (olculdu 18 Agu 2026).

    MERKEZ UYGULAMA KISITI: Merkez Uygulama satin alan firma sistemi
    IP, `localhost` veya kendi alan adi uzerinde calistirir.  Boyle bir
    kurulumda alt alan adi yoktur ve `Domain` yazmak cerezi GECERSIZ
    kilar (tarayici kendi host'una uymayan Domain'i reddeder).  Bu
    yuzden Domain YALNIZCA host, yapilandirilmis `alan_adi` degerinin
    gercek bir alt alani ise uretilir.

    Ornekler (alan_adi = goktungu.com):
      company.goktungu.com -> ".goktungu.com"
      goktungu.com         -> ".goktungu.com"   (kokun kendisi de dahil)
      104.247.173.243      -> None
      localhost            -> None
      musteri.local        -> None
    """
    h = str(host or "").strip().lower()
    if not h:
        return None
    # Port ve IPv6 koseli parantezini ayikla.
    if h.startswith("["):
        kapanis = h.find("]")
        h = h[1:kapanis] if kapanis > 0 else h
    else:
        h = h.split(":", 1)[0]
    if not h:
        return None
    try:
        kok = (ayar_oku().get("alan_adi") or "").strip().lower()
    except Exception:
        return None
    # Alan adi tanimsiz veya tek etiketli ise (`localhost`) Domain
    # yazilamaz: kok alan adi olmayan bir ada nitelik baglanmaz.
    if not kok or "." not in kok:
        return None
    # Host ya kokun kendisi ya da onun alt alani olmalidir.  Salt
    # sonek denetimi YETMEZ: `sahtegoktungu.com` de `goktungu.com`
    # ile biter ama alt alani DEGILDIR (etki alani kacirma).
    if h != kok and not h.endswith("." + kok):
        return None
    return "." + kok


def kurabiye_sil(ad: str, host: str | None = None) -> str:
    """Oturum kurabiyesini silen Set-Cookie dizesi.

    IS9B-CEREZ-ALANI: silme dizesi, YAZMA dizesiyle AYNI `Domain` ve
    `Path` degerlerini tasimak ZORUNDADIR.  Tarayici cerezi
    (ad, domain, path) uclusuyle tanir; Domain'li yazilmis bir cerezi
    Domain'siz `Max-Age=0` dizesi SILMEZ, yeni ve bos bir cerez
    olusturur.  Sonuc sessiz bir kusurdur: kullanici "cikis yaptim"
    goruntusu alir, oturum kurabiyesi diskte durmaya devam eder.
    """
    alan = _cerez_alani(host)
    parcalar = ["%s=" % ad, "Path=/", "Max-Age=0"]
    if alan:
        parcalar.insert(1, "Domain=%s" % alan)
    return "; ".join(parcalar)


def kurabiye_yaz(ad: str, jeton: str, host: str | None = None) -> str:
    """Oturum kurabiyesi üretir. `Path=/` KASITLIDIR: tanıtım sayfası (`/`)
    ile kurumsal panel (`/company/`) aynı oturumu görmelidir; kullanıcı
    tanıtım sayfasından giriş yapıp Müşteri Paneli'ni yeni sekmede
    açtığında yeniden kimlik sorulmaz."""
    import urllib.parse as _up
    # BULGU_08: `Secure` niteligi. Olmadan tarayici kurabiyeyi
    # HTTP istegine de ekler; saldirgan kurbani
    # http://goktungu.com adresine yonlendirirse jeton
    # sifresiz gider — 301 yaniti donmeden ONCE istek
    # basligi jetonu tasir. `SameSite=Lax` bunu kismen
    # azaltir ama tumuyle engellemez.
    # IS9B-CEREZ-ALANI: `Domain` niteligi. Dort panel ayri alt alan
    # adlarinda calistigi icin cerez etki alani KOK ALAN ADINA
    # baglanmalidir; aksi halde `company.` uzerinde acilan oturum
    # `app.` tarafinda gorunmez. `host` gecilmezse (eski cagri bicimi)
    # davranis birebir eski surumle ayni kalir.
    alan = _cerez_alani(host)
    _alan_p = f"Domain={alan}; " if alan else ""
    return (f"{ad}={_up.quote(jeton)}; Path=/; {_alan_p}"
            f"HttpOnly; Secure; SameSite=Lax; Max-Age={oturum_saniye()}")


# --------------------------------------------------------------------------
# Şifre
# --------------------------------------------------------------------------
def sifre_ozetle(sifre: str, tuz: bytes | None = None) -> str:
    if tuz is None:
        tuz = os.urandom(16)
    ozet = hashlib.pbkdf2_hmac("sha256", sifre.encode("utf-8"), tuz, YINELEME)
    return _AYIRAC.join(
        [
            _ETIKET,
            str(YINELEME),
            base64.b64encode(tuz).decode("ascii"),
            base64.b64encode(ozet).decode("ascii"),
        ]
    )


def sifre_dogrula(sifre: str, saklanan: str) -> bool:
    try:
        etiket, yineleme, tuz_b64, ozet_b64 = saklanan.split(_AYIRAC)
        if etiket != _ETIKET:
            return False
        tuz = base64.b64decode(tuz_b64)
        beklenen = base64.b64decode(ozet_b64)
        hesap = hashlib.pbkdf2_hmac(
            "sha256", sifre.encode("utf-8"), tuz, int(yineleme)
        )
        return hmac.compare_digest(hesap, beklenen)
    except Exception:
        return False


def sifre_gucu(sifre: str) -> str | None:
    """Kabul edilebilir değilse hata metni, uygunsa None döner."""
    if len(sifre) < 8:
        return "Şifre en az 8 karakter olmalı"
    if sifre.isdigit() or sifre.isalpha():
        return "Şifre harf ve rakam içermeli"
    return None


# --------------------------------------------------------------------------
# Sistem yöneticisi oturumu
# --------------------------------------------------------------------------
def yonetici_giris(eposta: str, sifre: str, ip: str | None = None,
                   tarayici: str | None = None) -> tuple[dict | None, str | None]:
    y = db.tek(
        "SELECT yonetici_id, eposta, sifre_ozet, ad_soyad, unvan, rol, durum, "
        "       eposta_dogrulama_ts "
        "FROM sistem_yoneticileri WHERE eposta = %s",
        (eposta,),
    )
    if not y or not sifre_dogrula(sifre, y["sifre_ozet"]):
        return None, "E-posta veya şifre hatalı"
    if y["durum"] != "etkin":
        return None, "Hesap askıya alınmış"

    # v2.5.1 - E-POSTA DOGRULAMA KAPISI (sistem yoneticisi)
    #
    # Jeton uretiminden ONCE; bkz. kullanici_giris'teki ayni gerekce.
    # Sistem yoneticisi TUM firmalari yonetir, bu yuzden dogrulama
    # burada bireysel kullanicidan daha da onemlidir.
    if not y.get("eposta_dogrulama_ts"):
        return None, "E-POSTA_DOGRULANMADI"

    jeton = secrets.token_urlsafe(32)
    bitis = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
        hours=int(ayar_oku().get("oturum_saat", 12))
    )
    db.calistir(
        "INSERT INTO sistem_oturumlari (jeton, yonetici_id, ip, tarayici, bitis_ts) "
        "VALUES (%s, %s, %s, %s, %s)",
        (jeton, y["yonetici_id"], ip, (tarayici or "")[:400], bitis),
    )
    db.calistir(
        "UPDATE sistem_yoneticileri SET son_giris_ts = now(), son_ip = %s "
        "WHERE yonetici_id = %s",
        (ip, y["yonetici_id"]),
    )
    denetim(y["yonetici_id"], "giris", "yonetici", str(y["yonetici_id"]), ip=ip)
    return {
        "jeton": jeton,
        "yonetici_id": y["yonetici_id"],
        "eposta": str(y["eposta"]),
        "ad_soyad": y["ad_soyad"],
        "unvan": y["unvan"],
        "rol": y["rol"],
        "bitis_ts": bitis.isoformat(),
    }, None


def yonetici_oturum(jeton: str | None) -> dict | None:
    if not jeton:
        return None
    return db.tek(
        "SELECT o.jeton, o.yonetici_id, y.eposta, y.ad_soyad, y.unvan, y.rol "
        "FROM sistem_oturumlari o "
        "JOIN sistem_yoneticileri y ON y.yonetici_id = o.yonetici_id "
        "WHERE o.jeton = %s AND o.bitis_ts > now() AND y.durum = 'etkin'",
        (jeton,),
    )


def yonetici_cikis(jeton: str) -> None:
    db.calistir("DELETE FROM sistem_oturumlari WHERE jeton = %s", (jeton,))


def oturum_temizle() -> int:
    return db.calistir("DELETE FROM sistem_oturumlari WHERE bitis_ts <= now()")


def denetim(yonetici_id: int | None, eylem: str, hedef_tur: str | None = None,
            hedef_id: str | None = None, ayrinti: dict | None = None,
            ip: str | None = None) -> None:
    import json as _json

    db.calistir(
        "INSERT INTO sistem_denetim (yonetici_id, eylem, hedef_tur, hedef_id, "
        "ayrinti, ip) VALUES (%s, %s, %s, %s, %s, %s)",
        (yonetici_id, eylem, hedef_tur, hedef_id,
         _json.dumps(ayrinti or {}, ensure_ascii=False), ip),
    )


# --------------------------------------------------------------------------
# İlk yönetici (kurulum)
# --------------------------------------------------------------------------
def yonetici_var_mi() -> bool:
    return bool(db.deger("SELECT count(*) FROM sistem_yoneticileri"))


def yonetici_olustur(eposta: str, sifre: str, ad_soyad: str = "",
                     unvan: str | None = None,
                     rol: str = "sistem_yonetici") -> tuple[int | None, str | None]:
    hata = sifre_gucu(sifre)
    if hata:
        return None, hata
    if db.tek("SELECT 1 FROM sistem_yoneticileri WHERE eposta = %s", (eposta,)):
        return None, "Bu e-posta zaten kayıtlı"
    yid = db.deger(
        "INSERT INTO sistem_yoneticileri (eposta, sifre_ozet, ad_soyad, unvan, rol) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING yonetici_id",
        (eposta, sifre_ozetle(sifre), ad_soyad, unvan, rol),
    )
    return int(yid), None


# --------------------------------------------------------------------------
# Firma kullanıcısı (müşteri tarafı) — merkez API'si için
# --------------------------------------------------------------------------
def kullanici_dogrula(eposta: str, sifre: str) -> tuple[dict | None, str | None]:
    k = db.tek(
        "SELECT k.kullanici_id, k.firma_id, k.eposta, k.sifre_ozet, k.ad, k.soyad, "
        "       k.eposta_dogrulama_ts, "
        "       k.rol, k.durum, f.unvan AS firma_unvan, f.kisa_ad AS firma_kisa_ad, "
        "       f.durum AS firma_durum, f.logo_yol, f.tur AS firma_tur "
        "FROM kullanicilar k JOIN firmalar f ON f.firma_id = k.firma_id "
        "WHERE k.eposta = %s",
        (eposta,),
    )
    if not k or not sifre_dogrula(sifre, k["sifre_ozet"]):
        return None, "E-posta veya şifre hatalı"
    if k["durum"] != "etkin":
        return None, "Kullanıcı askıya alınmış"
    if k["firma_durum"] != "etkin":
        return None, "Firma hesabı etkin değil"
    k.pop("sifre_ozet", None)
    k["eposta"] = str(k["eposta"])
    # Logo DOSYA YOLU istemciye verilmez: sunucunun dizin yapısını
    # sızdırır ve istemcinin işine yaramaz. Yerine yalnızca varlık
    # bayrağı ve herkese açık erişim adresi döner.
    logo_yol = k.pop("logo_yol", None)
    k["logo_var"] = bool(logo_yol)
    k["logo_adres"] = (
        "/api/genel/firma_logo?firma_id=%d" % int(k["firma_id"])
        if logo_yol else "")
    # v2.4.65 — Firmaya tanımlı modül yetkileri giriş yanıtına eklenir.
    #
    # NEDEN BURADA: köprü paneli hangi servis menülerini göstereceğine
    # buna bakar (Radar/GCCDUAL/AI). Ayrı bir uçtan sorulsaydı köprü
    # giriş anında ikinci bir ağ gidiş-dönüşü yapmak zorunda kalır ve
    # çevrimdışı ilk açılışta menü boş gelirdi.
    try:
        import mk_yetki as _yetki
        k["yetkiler"] = _yetki.kopru_yetkileri(int(k["firma_id"]))
        # v1.5.6 — Merkez Uygulama lisansı da yanıta girer.
        #
        # Köprü, lisanslı firmanın YÖNETİCİSİNE giriş sonrası bir kez
        # "telemetri VEILOX buluta mı, kendi merkez sunucunuza mı
        # gitsin" sorusunu bu alana bakarak sorar. Lisansı olmayan
        # firmada soru HİÇ görünmez; aksi halde müşterilerin %99'una
        # anlamsız bir altyapı sorusu gösterilirdi.
        _y = _yetki.firma_yetkileri(int(k["firma_id"]))
        k["merkez_lisans"] = bool(_y.get("merkez_lisans"))
        k["sinirsiz"] = bool(_y.get("sinirsiz"))
    except Exception:
        # Yetki motoru okunamazsa çekirdek servisler açık, ücretli ve
        # VEILOX'a bağlı modüller KAPALI varsayılır. Hata durumunda
        # yetki açmak, kapatmaktan daha büyük bir kusurdur.
        k["yetkiler"] = {"dron": True, "video": True, "ai": False,
                         "radar": False, "gccdual": False}
        k["merkez_lisans"] = False
        k["sinirsiz"] = False
    return k, None


def kullanici_olustur(firma_id: int, eposta: str, sifre: str, ad: str = "",
                      soyad: str = "", rol: str = "pilot",
                      telefon: str | None = None) -> tuple[int | None, str | None]:
    hata = sifre_gucu(sifre)
    if hata:
        return None, hata
    if db.tek("SELECT 1 FROM kullanicilar WHERE eposta = %s", (eposta,)):
        return None, "Bu e-posta zaten kayıtlı"
    # v2.4.65 — Koltuk denetimi `mk_yetki` motoruna devredildi.
    #
    # ÖNCEKİ DAVRANIŞ: `maks_kullanici` karşılığında TÜM roller
    # sayılıyordu. Yeni abonelik modelinde ücretsiz taban "1 pilot +
    # 1 yönetici" olduğu için bu sayım yanlış olur: yönetici tek
    # koltuğu tüketir ve şirket ilk pilotunu hiç ekleyemez.
    #
    # Yeni kural: koltuk YALNIZ `rol='pilot'` kayıtlarını sayar;
    # `firma_yonetici` ve `gozlemci` koltuk tüketmez ama toplam hesap
    # üst sınırına (`maks_kullanici`) tabidir. Sınırsız lisanslı
    # firmalar (Merkez Uygulama sahipleri) tüm denetimlerden muaftır.
    import mk_yetki as yetki
    uygun, hata = yetki.koltuk_uygun_mu(firma_id, rol)
    if not uygun:
        return None, hata
    kid = db.deger(
        "INSERT INTO kullanicilar (firma_id, eposta, sifre_ozet, ad, soyad, rol, "
        "telefon) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING kullanici_id",
        (firma_id, eposta, sifre_ozetle(sifre), ad, soyad, rol, telefon),
    )
    return int(kid), None

# --------------------------------------------------------------------------
# Firma kullanıcısı oturumu (/company/ paneli)
# --------------------------------------------------------------------------
# NEDEN AYRI TABLO: `sistem_oturumlari` yalnızca VEILOX personelinin
# jetonlarını tutar ve `yonetici_id` ile `sistem_yoneticileri` tablosuna
# bağlıdır. Firma kullanıcılarını aynı tabloya yazmak, yetki denetimini
# tek bir rol kolonuna indirgeyeceği için müşteri verisinin yönetici
# uçlarına sızma riskini doğurur. Bu nedenle firma oturumları
# `kullanici_oturumlari` tablosunda, ayrı kurabiye adıyla (`goktungu_firma`)
# ve ayrı yetki adıyla (`firma`) taşınır.


def kullanici_giris(eposta: str, sifre: str, ip: str | None = None,
                    tarayici: str | None = None
                    ) -> tuple[dict | None, str | None]:
    """Firma kullanıcısını doğrular ve kalıcı oturum jetonu üretir."""
    k, hata = kullanici_dogrula(eposta, sifre)
    if hata:
        return None, hata

    # v2.5.1 - E-POSTA DOGRULAMA KAPISI
    #
    # NEDEN BURADA: jeton uretiminden ONCE. Jeton uretildikten sonra
    # koyulursa kullanici_oturumlari'na satir YAZILIR ve dogrulanmamis
    # hesap icin gecerli bir oturum kaydi diskte kalir.
    #
    # NEDEN YALNIZ BIREYSEL: kurumsal kullanicilari firma yoneticisi
    # elle ekler, e-posta sahipligi firmanin sorumlulugundadir. Bireysel
    # kullanici kendini kaydeder; e-posta sahipligi dogrulanmadan hesap
    # acilirsa baskasinin adresiyle hesap acilabilir.
    if str(k.get("firma_tur") or "") == "bireysel" and \
            not k.get("eposta_dogrulama_ts"):
        return None, "E-POSTA_DOGRULANMADI"

    jeton = secrets.token_urlsafe(32)
    bitis = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
        hours=int(ayar_oku().get("oturum_saat", 12))
    )
    db.calistir(
        "INSERT INTO kullanici_oturumlari "
        "(jeton, kullanici_id, firma_id, ip, tarayici, bitis_ts) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (jeton, k["kullanici_id"], k["firma_id"], ip,
         (tarayici or "")[:400], bitis),
    )
    db.calistir(
        "UPDATE kullanicilar SET son_giris_ts = now(), son_ip = %s "
        "WHERE kullanici_id = %s",
        (ip, k["kullanici_id"]),
    )
    return {
        "jeton": jeton,
        "kullanici_id": k["kullanici_id"],
        "firma_id": k["firma_id"],
        "eposta": k["eposta"],
        "ad": k["ad"],
        "soyad": k["soyad"],
        "rol": k["rol"],
        "firma_unvan": k["firma_unvan"],
        "firma_kisa_ad": k["firma_kisa_ad"],
        "bitis_ts": bitis.isoformat(),
    }, None


def kullanici_oturum(jeton: str | None) -> dict | None:
    """Jetondan firma kullanıcısı oturumunu çözer. Süresi geçmiş jeton,
    askıya alınmış kullanıcı veya etkin olmayan firma için None döner.

    `o.bitis_ts` ALANI ZORUNLUDUR: tarayıcı tarafı oturumun ne zaman
    düşeceğini bilmeden "belirli süre açık kalsın" davranışını
    uygulayamaz.  Alan yoksa arayuz her istekte 401 bekler ve kullanıcı
    oturumu bittiğinde sessizce boş ekranla karşılaşır."""
    if not jeton:
        return None
    return db.tek(
        "SELECT o.jeton, o.kullanici_id, o.firma_id, o.bitis_ts, "
        "       k.eposta, k.ad, k.soyad, "
        "       k.rol, f.unvan AS firma_unvan, f.kisa_ad AS firma_kisa_ad "
        "FROM kullanici_oturumlari o "
        "JOIN kullanicilar k ON k.kullanici_id = o.kullanici_id "
        "JOIN firmalar f     ON f.firma_id = o.firma_id "
        "WHERE o.jeton = %s AND o.bitis_ts > now() "
        "  AND k.durum = 'etkin' AND f.durum = 'etkin'",
        (jeton,),
    )


def kullanici_cikis(jeton: str) -> None:
    db.calistir("DELETE FROM kullanici_oturumlari WHERE jeton = %s", (jeton,))


def kullanici_oturum_temizle() -> int:
    return db.calistir(
        "DELETE FROM kullanici_oturumlari WHERE bitis_ts <= now()")
