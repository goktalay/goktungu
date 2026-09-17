# -*- coding: utf-8 -*-
"""merkez_kimlik: merkez kullanicilar tablosuna dayali kimlik dogrulama.

GOKTUNGU merkezde (/app/ altinda) calistirildiginda pilotlar kendi yerel
gcs veritabanina degil, MERKEZ veritabanina (goktungu_merkez.kullanicilar)
kayitli kurumsal hesaplariyla giris yapar. Boylece /company/ altindan
kayit olan firma, ayni kimlikle /app/ uzerinde ucus yapar.

Etkinlestirme (ortam degiskenleri):
    GOKTUNGU_MERKEZ_KIMLIK=1
    GOKTUNGU_MERKEZ_DSN=postgresql://kullanici:sifre@127.0.0.1:5432/goktungu_merkez

Etkin degilse GOKTUNGU eski davranisini korur (yerel kullanicilar tablosu).
Bu sayede kullanicinin lokal kurulumu bozulmaz; yalniz merkez ornegi
kurumsal kimlige baglanir.

Sifre bicimi merkezle aynidir:  pbkdf2_sha256$<yineleme>$<tuz_b64>$<ozet_b64>
"""
import base64
import hashlib
import hmac
import json
import os
import threading

_ETIKET = "pbkdf2_sha256"
_kilit = threading.Lock()
_havuz = None


# ----------------------------------------------------------------------
# Yapilandirma
# ----------------------------------------------------------------------
def etkin():
    """Merkez kimligi etkin mi? (ortam degiskeni ile acilir)"""
    return str(os.environ.get("GOKTUNGU_MERKEZ_KIMLIK", "")).strip() in (
        "1", "true", "True", "evet")


def merkez_kipinde():
    """Bu ornek MERKEZDE mi calisiyor? (/app/ altinda, cok kiracili)

    `etkin()` ile ayni bayragi okur ama SORUSU farklidir ve cagiran
    taraflar bu ayrimi bilmek zorundadir:

      etkin()          -> "kimlik dogrulamasi merkez tablosundan mi?"
      merkez_kipinde() -> "bu ornek operatorun islettigi merkez ornegi mi?"

    Ikisi bugun ayni ortam degiskenine bagli; ayri isim vermek, ileride
    merkez kipi baska bir bayrakla belirlenirse cagiran her yeri tek tek
    duzeltmek zorunda kalmamak icindir.

    OLCULEN KUSUR (bkz. HATA_GOC_SIHIRBAZI.md): merkezde calisan ornek
    kendini lokal kurulum sanip pilota sema goc sihirbazi gosteriyordu.
    Sihirbaz giris ekranindan ONCE aciliyor, oturum henuz bos oldugu icin
    yonetici denetimi kapaniyor ve pilot %0'da sikisiyordu. Merkezde
    sema yonetimi operatorun isidir; bu yardimci o ayrimi kurar.
    """
    return etkin()


def dsn():
    return str(os.environ.get("GOKTUNGU_MERKEZ_DSN", "")).strip()


# ----------------------------------------------------------------------
# Sifre dogrulama (merkez bicimi)
# ----------------------------------------------------------------------
def sifre_dogrula(sifre, ozet):
    """pbkdf2_sha256 ozetini sabit zamanli karsilastirir."""
    try:
        etiket, yineleme, tuz_b64, ozet_b64 = str(ozet).split("$")
        if etiket != _ETIKET:
            return False
        tuz = base64.b64decode(tuz_b64)
        beklenen = base64.b64decode(ozet_b64)
        hesap = hashlib.pbkdf2_hmac(
            "sha256", str(sifre).encode("utf-8"), tuz, int(yineleme))
        return hmac.compare_digest(hesap, beklenen)
    except Exception:
        return False


# ----------------------------------------------------------------------
# Baglanti havuzu (tembel kurulum)
# ----------------------------------------------------------------------
def _havuz_al():
    global _havuz
    with _kilit:
        if _havuz is not None:
            return _havuz
        b = dsn()
        if not b:
            raise RuntimeError("GOKTUNGU_MERKEZ_DSN tanimli degil")
        from psycopg2.pool import ThreadedConnectionPool
        _havuz = ThreadedConnectionPool(1, 6, b)
        return _havuz


def _tek(sorgu, parametre=()):
    """Tek satir dondurur (dict) veya None."""
    from psycopg2.extras import RealDictCursor
    havuz = _havuz_al()
    con = havuz.getconn()
    try:
        with con.cursor(cursor_factory=RealDictCursor) as im:
            im.execute(sorgu, parametre)
            s = im.fetchone()
        con.commit()
        return dict(s) if s else None
    except Exception:
        try:
            con.rollback()
        except Exception:
            pass
        raise
    finally:
        havuz.putconn(con)


def _sorgu(sorgu, parametre=()):
    """Cok satir dondurur (dict listesi)."""
    from psycopg2.extras import RealDictCursor
    havuz = _havuz_al()
    con = havuz.getconn()
    try:
        with con.cursor(cursor_factory=RealDictCursor) as im:
            im.execute(sorgu, parametre)
            satirlar = im.fetchall()
        con.commit()
        return [dict(s) for s in satirlar]
    except Exception:
        try:
            con.rollback()
        except Exception:
            pass
        raise
    finally:
        havuz.putconn(con)


def _calistir(sorgu, parametre=()):
    havuz = _havuz_al()
    con = havuz.getconn()
    try:
        with con.cursor() as im:
            im.execute(sorgu, parametre)
        con.commit()
    except Exception:
        try:
            con.rollback()
        except Exception:
            pass
        raise
    finally:
        havuz.putconn(con)


# ----------------------------------------------------------------------
# Kimlik dogrulama
# ----------------------------------------------------------------------
def dogrula(eposta, sifre):
    """Merkez kullanicilar tablosunda dogrular.

    Doner: (kullanici_dict | None, hata_metni | None)

    Donen sozluk GOKTUNGU'nun bekledigi alanlari icerir:
      eposta, ad_soyad, unvan, rol, avatar, aktif
    ve ek olarak firma izolasyonu icin:
      firma_id, firma_unvan, firma_kisa_ad, kullanici_id
    """
    eposta = str(eposta or "").strip().lower()
    if not eposta:
        return None, "E-posta bos olamaz"
    try:
        k = _tek(
            "SELECT k.kullanici_id, k.firma_id, k.eposta, k.sifre_ozet, "
            "       k.ad, k.soyad, k.rol, k.durum, "
            "       f.unvan AS firma_unvan, f.kisa_ad AS firma_kisa_ad, "
            "       f.durum AS firma_durum "
            "FROM kullanicilar k "
            "JOIN firmalar f ON f.firma_id = k.firma_id "
            "WHERE lower(k.eposta) = %s",
            (eposta,),
        )
    except Exception as e:
        return None, "Merkez veritabanina ulasilamadi: %s" % e
    if not k or not sifre_dogrula(sifre, k.get("sifre_ozet") or ""):
        return None, "E-posta veya sifre hatali."
    if k.get("durum") != "etkin":
        return None, "Kullanici askiya alinmis."
    if k.get("firma_durum") != "etkin":
        return None, "Firma hesabi etkin degil."
    ad_soyad = ("%s %s" % (k.get("ad") or "", k.get("soyad") or "")).strip()
    rol = str(k.get("rol") or "kullanici")
    # Merkez rolleri -> GOKTUNGU rolleri
    if rol in ("firma_yonetici", "yonetici", "admin"):
        gcs_rol = "yonetici"
    else:
        gcs_rol = "kullanici"
    return {
        "eposta": str(k["eposta"]),
        "ad_soyad": ad_soyad or str(k["eposta"]),
        "unvan": str(k.get("firma_unvan") or ""),
        "rol": gcs_rol,
        "merkez_rol": rol,
        "avatar": "",
        "aktif": 1,
        "kullanici_id": int(k["kullanici_id"]),
        "firma_id": int(k["firma_id"]),
        "firma_unvan": str(k.get("firma_unvan") or ""),
        "firma_kisa_ad": str(k.get("firma_kisa_ad") or ""),
    }, None


def _gcs_sozluk(k):
    """Merkez satirini GOKTUNGU kullanici sozlugune cevirir.

    IS9B-OTURUM-DEVRI: `dogrula()` bu donusumu kendi icinde yapiyordu.
    Devir ucu ve jeton cozumu AYNI bicimi uretmek zorunda: arayuz ve
    WS katmani `rol`, `ad_soyad`, `firma_id` alanlarini bu adlarla
    okur. Donusum tek yerde tutulmazsa iki yol zamanla ayrisir ve
    "sifreyle giren kullanici yonetici, jetonla giren kullanici degil"
    gibi izi zor surulen kusurlar dogar.
    """
    ad_soyad = ("%s %s" % (k.get("ad") or "", k.get("soyad") or "")).strip()
    rol = str(k.get("rol") or "kullanici")
    if rol in ("firma_yonetici", "yonetici", "admin"):
        gcs_rol = "yonetici"
    else:
        gcs_rol = "kullanici"
    return {
        "eposta": str(k["eposta"]),
        "ad_soyad": ad_soyad or str(k["eposta"]),
        "unvan": str(k.get("firma_unvan") or ""),
        "rol": gcs_rol,
        "merkez_rol": rol,
        "avatar": "",
        "aktif": 1,
        "kullanici_id": int(k["kullanici_id"]),
        "firma_id": int(k["firma_id"]),
        "firma_unvan": str(k.get("firma_unvan") or ""),
        "firma_kisa_ad": str(k.get("firma_kisa_ad") or ""),
    }


def oturum_coz(jeton):
    """Kurumsal panel oturum jetonundan kullaniciyi cozer.

    IS9B-OTURUM-DEVRI: kullanici kurumsal panelde (`company.`) giris
    yaptiginda merkez `kullanici_oturumlari` tablosuna bir satir yazilir
    ve jeton `goktungu_firma` kurabiyesiyle tarayiciya verilir. Ayni
    tarayici App'e (`app.`) gectiginde bu jetonu tasir; bu islev jetonu
    dogrulayarak kullaniciyi cozer ve App kendi oturumunu acabilir.

    SIFRE SORULMAZ ve sorulmamalidir: kullanici kimligini kurumsal
    panelde ZATEN kanitladi. Jeton o kanitin tasiyicisidir ve suresi,
    kullanici durumu ile firma durumu SQL icinde denetlenir.

    Doner: (kullanici_dict | None, hata_metni | None)
    """
    j = str(jeton or "").strip()
    if not j:
        return None, "Jeton bos"
    try:
        k = _tek(
            "SELECT o.kullanici_id, o.firma_id, "
            "       k.eposta, k.ad, k.soyad, k.rol, "
            "       f.unvan AS firma_unvan, f.kisa_ad AS firma_kisa_ad "
            "FROM kullanici_oturumlari o "
            "JOIN kullanicilar k ON k.kullanici_id = o.kullanici_id "
            "JOIN firmalar f     ON f.firma_id = o.firma_id "
            "WHERE o.jeton = %s AND o.bitis_ts > now() "
            "  AND k.durum = 'etkin' AND f.durum = 'etkin'",
            (j,),
        )
    except Exception as e:
        return None, "Merkez veritabanina ulasilamadi: %s" % e
    if not k:
        return None, "Oturum gecersiz veya suresi gecmis"
    return _gcs_sozluk(k), None


def eposta_ile_coz(eposta):
    """E-postadan merkez kullanicisini cozer (SIFRE DOGRULAMAZ).

    IS9B-OTURUM-DEVRI: App'in jeton dogrulamasi kullaniciyi YEREL
    tablodan cozuyordu. Merkez kipinde kullanicilar merkez
    veritabanindadir ve yerel tabloya otomatik yazilmaz; olculen
    durumda merkezdeki uc kullanicidan yalniz biri yerel tabloda
    vardi. Bu islev olmadan jetonla giris YALNIZ yerel tabloda kaydi
    olan hesaplarda calisir, diger firmalarda sessizce basarisiz olur.

    SIFRE DOGRULAMADIGI ICIN yalnizca jetonu ZATEN dogrulanmis
    cagrilardan kullanilmalidir. Jeton dogrulamasi kimligi kanitlar;
    bu islev yalnizca kanitlanmis kimligin ayrintilarini getirir.

    Doner: kullanici_dict | None
    """
    e = str(eposta or "").strip().lower()
    if not e:
        return None
    try:
        k = _tek(
            "SELECT k.kullanici_id, k.firma_id, k.eposta, "
            "       k.ad, k.soyad, k.rol, "
            "       f.unvan AS firma_unvan, f.kisa_ad AS firma_kisa_ad "
            "FROM kullanicilar k "
            "JOIN firmalar f ON f.firma_id = k.firma_id "
            "WHERE lower(k.eposta) = %s "
            "  AND k.durum = 'etkin' AND f.durum = 'etkin'",
            (e,),
        )
    except Exception:
        return None
    if not k:
        return None
    return _gcs_sozluk(k)


def firma_kullanicilari(firma_id):
    """Ayni firmanin kullanicilarini dondurur (pilot listesi widget'i icin)."""
    from psycopg2.extras import RealDictCursor
    havuz = _havuz_al()
    con = havuz.getconn()
    try:
        with con.cursor(cursor_factory=RealDictCursor) as im:
            im.execute(
                "SELECT eposta, ad, soyad, rol, durum "
                "FROM kullanicilar WHERE firma_id = %s "
                "ORDER BY ad, soyad", (int(firma_id),))
            satirlar = im.fetchall()
        con.commit()
    finally:
        havuz.putconn(con)
    cikti = []
    for s in satirlar:
        ad_soyad = ("%s %s" % (s.get("ad") or "",
                               s.get("soyad") or "")).strip()
        cikti.append({
            "eposta": str(s["eposta"]),
            "ad_soyad": ad_soyad or str(s["eposta"]),
            "unvan": "",
            "rol": ("yonetici" if str(s.get("rol")) in
                    ("firma_yonetici", "yonetici", "admin")
                    else "kullanici"),
            "avatar": "",
            "aktif": 1 if s.get("durum") == "etkin" else 0,
        })
    return cikti


def firma_bilgi(firma_id):
    """Kurum kimligini dondurur (unvan, kisa ad, logo, adres, telefon).

    v2.4.53 Faz 4: /app/ arayuzu ve ucus raporu antedi bu bilgileri
    kullanir. Logo ikili verisi BURADAN DONMEZ; yalnizca `logo_var`
    bayragi doner ve logo HTTP ucundan (onbelleklenebilir) cekilir.
    """
    s = _tek(
        "SELECT firma_id, unvan, kisa_ad, vergi_no, vergi_dairesi,"
        " adres, telefon, eposta, web, logo_yol, durum, abonelik"
        " FROM firmalar WHERE firma_id = %s", (int(firma_id),))
    if not s:
        return None
    logo = str(s.get("logo_yol") or "").strip()
    return {
        "firma_id": int(s["firma_id"]),
        "unvan": str(s.get("unvan") or ""),
        "kisa_ad": str(s.get("kisa_ad") or ""),
        "vergi_no": str(s.get("vergi_no") or ""),
        "vergi_dairesi": str(s.get("vergi_dairesi") or ""),
        "adres": str(s.get("adres") or ""),
        "telefon": str(s.get("telefon") or ""),
        "eposta": str(s.get("eposta") or ""),
        "web": str(s.get("web") or ""),
        "durum": str(s.get("durum") or ""),
        "abonelik": str(s.get("abonelik") or ""),
        "logo_var": bool(logo),
    }


def firma_kopruleri(firma_id):
    """Firmanin kayitli kopru (saha kurulumu) listesini dondurur.

    v2.4.53 Faz 7: merkezde calisan GCS'in Baglanti Yoneticisi, dron
    baglantilarini KOPRU basina gruplar. Bu islev grup basliklarinin
    kaynagidir: isim + IP + cevrimici durumu.

    Cevrimici alani BURADA veritabanindan okunur; canli soket durumu
    merkez surecinde (role.ROLE) tutulur ve ayni surecte olmadigimiz
    icin buradan gorulemez. Merkez, nabiz gormedigi kurulumu
    `cevrimici=false` olarak isaretledigi (mk_role.bayat_temizle) icin
    veritabani degeri en cok `kopru_zaman_asimi_sn` kadar gecikir.

    `gizli_ozet` ASLA donmez: panel tarafina sizmasi kayit sahtekarligi
    riski yaratir.
    """
    # v2.4.232: `api_kodu` (goc 12) — ilk baglantiya kadar dolu, sonra
    # bos. Goc henuz uygulanmamis bir merkezde sutun yoktur; liste o
    # zaman kodsuz doner, panel bosalmaz.
    try:
        satirlar = _sorgu(
            "SELECT ornek_id, kurulum_uid, ad, aciklama, surum, platform,"
            "       makine_adi, cevrimici, son_gorulme_ts, son_ip,"
            "       dron_sayisi, yetenekler, durum, api_kodu"
            "  FROM sunucu_ornekleri WHERE firma_id = %s"
            " ORDER BY cevrimici DESC, ad", (int(firma_id),))
    except Exception:
        satirlar = _sorgu(
            "SELECT ornek_id, kurulum_uid, ad, aciklama, surum, platform,"
            "       makine_adi, cevrimici, son_gorulme_ts, son_ip,"
            "       dron_sayisi, yetenekler, durum"
            "  FROM sunucu_ornekleri WHERE firma_id = %s"
            " ORDER BY cevrimici DESC, ad", (int(firma_id),))
    cikti = []
    for s in satirlar or []:
        yet = s.get("yetenekler")
        if isinstance(yet, str):
            try:
                yet = json.loads(yet)
            except Exception:
                yet = {}
        cikti.append({
            "ornek_id": int(s["ornek_id"]),
            "kurulum_uid": str(s.get("kurulum_uid") or ""),
            "ad": str(s.get("ad") or ""),
            "aciklama": str(s.get("aciklama") or ""),
            "surum": str(s.get("surum") or ""),
            "platform": str(s.get("platform") or ""),
            "makine_adi": str(s.get("makine_adi") or ""),
            "cevrimici": bool(s.get("cevrimici")),
            "son_gorulme_ts": (s.get("son_gorulme_ts").isoformat()
                               if hasattr(s.get("son_gorulme_ts"),
                                          "isoformat")
                               else s.get("son_gorulme_ts")),
            "ip": str(s.get("son_ip") or ""),
            "dron_sayisi": int(s.get("dron_sayisi") or 0),
            "yetenekler": yet if isinstance(yet, dict) else {},
            "durum": str(s.get("durum") or ""),
            "api_kodu": str(s.get("api_kodu") or ""),
        })
    return cikti


# ----------------------------------------------------------------------
# v2.4.232: Kopruler paneli — merkez ic uclari uzerinden yonetim
# ----------------------------------------------------------------------
# Merkezde calisan GCS'in firma oturum kurabiyesi yoktur; kopru kaydi
# olusturma/silme/kod yenileme merkezin ic uclarina (127.0.0.1 +
# X-Ic-Anahtar) gider. Firma izolasyonu merkezde YENIDEN denetlenir.
def kopru_olustur(firma_id, ad):
    """`(yeni_kayit, hata)`; kayit `api_kodu` icerir."""
    g, hata = _ic_post("/api/ic/kopru_olustur",
                       {"firma_id": int(firma_id), "ad": str(ad or "")})
    if hata:
        return None, hata
    if not (g or {}).get("basarili"):
        return None, str((g or {}).get("hata") or "Kopru olusturulamadi")
    return (g or {}).get("kopru") or {}, None


def kopru_sil(firma_id, ornek_id):
    g, hata = _ic_post("/api/ic/kopru_sil",
                       {"firma_id": int(firma_id),
                        "ornek_id": int(ornek_id)})
    if hata:
        return False, hata
    if not (g or {}).get("basarili"):
        return False, str((g or {}).get("hata") or "Kopru silinemedi")
    return True, None


def kopru_kod_yenile(firma_id, ornek_id):
    g, hata = _ic_post("/api/ic/kopru_kod_yenile",
                       {"firma_id": int(firma_id),
                        "ornek_id": int(ornek_id)})
    if hata:
        return None, hata
    if not (g or {}).get("basarili"):
        return None, str((g or {}).get("hata") or "Kod yenilenemedi")
    return (g or {}).get("kopru") or {}, None


def _ic_taban():
    """Merkezin dahili taban adresini dondurur."""
    return (os.environ.get("GOKTUNGU_MERKEZ_IC_TABAN")
            or "http://127.0.0.1:80").rstrip("/")


def _ic_baglam(url):
    """Yerel adresler icin sertifika dogrulamasini gevsetir.

    Merkez alan adina bagli sertifika sunar; `127.0.0.1` uzerinden
    baglanildiginda konak adi eslesmez. Muafiyet YALNIZ yerel adreslere
    verilir — uzak bir adrese asla.
    """
    import ssl as _ssl
    import urllib.parse as _up
    if not url.lower().startswith("https"):
        return None
    konak = (_up.urlsplit(url).hostname or "").lower()
    if konak not in ("127.0.0.1", "localhost", "::1"):
        return None
    b = _ssl.create_default_context()
    b.check_hostname = False
    b.verify_mode = _ssl.CERT_NONE
    return b


def _ic_post(yol, govde_sozluk, zaman_asimi=8.0):
    """Merkezin dahili ucuna POST atar; 308/301 yonlendirmesini izler.

    `(ham_yanit, hata)` ikilisi doner. `urllib`, POST isteginde 308'i
    HIC izlemez ve 301/302'yi GET'e cevirir; bu yuzden yonlendirme elle
    ve yontem KORUNARAK takip edilir. En cok 3 adim (donguye karsi).
    """
    import json as _json
    import urllib.error
    import urllib.parse as _up
    import urllib.request
    anahtar = (os.environ.get("GOKTUNGU_IC_ANAHTAR") or "").strip()
    if not anahtar:
        return None, "Ic anahtar tanimli degil"
    url = _ic_taban() + yol
    veri = _json.dumps(govde_sozluk).encode("utf-8")
    for _adim in range(3):
        istek = urllib.request.Request(
            url, data=veri, method="POST",
            headers={"Content-Type": "application/json",
                     "X-Ic-Anahtar": anahtar})
        try:
            with urllib.request.urlopen(
                    istek, timeout=float(zaman_asimi),
                    context=_ic_baglam(url)) as y:
                return _json.loads(y.read().decode("utf-8", "replace")), None
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 307, 308):
                hedef = e.headers.get("Location") or ""
                if hedef:
                    url = _up.urljoin(url, hedef)
                    continue
            try:
                g = _json.loads(e.read().decode("utf-8", "replace"))
                return None, str(g.get("hata") or ("HTTP %d" % e.code))
            except Exception:
                return None, "HTTP %d" % e.code
        except Exception as e:
            return None, "%s: %s" % (type(e).__name__, e)
    return None, "Cok fazla yonlendirme"


def kopruye_sor(ornek_id, firma_id, eylem, veri=None, zaman_asimi=8.0):
    """Merkezin IC ucundan canli kopruye sorgu yapar.

    v2.4.53 Faz 7: AI ve video servis durumlari kopru makinesinde
    yasar; merkez veritabaninda YOKTUR. GCS ayri bir surec oldugu icin
    role katmanina dogrudan erisemez ve firma oturum kurabiyesine de
    sahip degildir; bu yuzden merkezin yalniz yerelden erisilebilen
    `/api/ic/kopru_sor` ucu kullanilir.

    Merkez tarafinda iki koruma vardir (gercek TCP esi + paylasilan
    sir) ve `firma_id` ornegin sahibiyle karsilastirilir; yani buradan
    yanlis bir firma kimligi gonderilse dahi capraz veri gelmez.

    `(veri, hata)` ikilisi doner. Kopru cevrimici degilse veri None,
    hata aciklamalidir — bos sozluk DONMEZ, cunku bos sozluk arayuzde
    "servis kapali" gibi gorunur ve operatoru yanlis yonlendirir.
    """
    g, hata = _ic_post("/api/ic/kopru_sor", {
        "ornek_id": int(ornek_id),
        "firma_id": int(firma_id),
        "eylem": str(eylem),
        "veri": veri or {},
        "zaman_asimi": float(zaman_asimi),
    }, zaman_asimi=float(zaman_asimi) + 6.0)
    if hata:
        return None, hata
    if not (g or {}).get("basarili"):
        return None, str((g or {}).get("hata") or "Bilinmeyen hata")
    return (g.get("veri") or {}), None


def _ic_cagri(yol, govde_sozluk, zaman_asimi=14.0):
    """Merkezin ic ucuna JSON POST yapar.

    `kopruye_sor` ile ayni korumayi kullanir; ortak yardimci olarak
    ayrilmasinin nedeni akis uclarinin (`/api/ic/akis_ac` vb.) ayni
    basligi ve tabani gerektirmesidir.
    """
    return _ic_post(yol, govde_sozluk, zaman_asimi=float(zaman_asimi))


def akis_ac(ornek_id, firma_id, kanal_id, tanim, gcs_port=0):
    """Kopruden merkeze ham MAVLink akis kanali acar.

    Doner: `(port, hata)`. `port`, GCS'nin `udpin:127.0.0.1:<port>` ile
    DINLEYECEGI portudur.

    v2.4.56: `gcs_port` verilmesi ZORUNLU degildir ama verilmelidir.
    Cagirici o portu ONCE kendisi bind eder, sonra bu islevi cagirir;
    merkez kendi ayri portundan o adrese yazar.

    Neden: `udpin` bir bind cagrisidir. Eskiden merkez kendi portunu
    bildiriyor, GCS ayni portu bind etmeye calisiyor ve
    `[Errno 98] Address already in use` aliyordu — akis yolu hic
    calismiyordu (canli olarak olculdu, bkz. HATA_AKIS_PORT_CAKISMASI.md).

    HATA DURUMUNDA port None doner ve hata metni ACIKTIR. Bos deger
    donmesi, cagirici tarafta "baglandi" sanilmasina ve pilotun var
    olmayan bir baglantiya komut gondermesine yol acar.
    """
    govde = {
        "ornek_id": int(ornek_id),
        "firma_id": int(firma_id),
        "kanal_id": int(kanal_id),
        "tanim": dict(tanim or {}),
    }
    if int(gcs_port or 0) > 0:
        govde["gcs_port"] = int(gcs_port)
    g, hata = _ic_cagri("/api/ic/akis_ac", govde, zaman_asimi=20.0)
    if hata:
        return None, hata
    if not (g or {}).get("basarili"):
        return None, str((g or {}).get("hata") or "Akis kanali acilamadi")
    try:
        port = int(g.get("port") or 0)
    except Exception:
        port = 0
    if not port:
        return None, "Merkez port bildirmedi"
    # Merkez, bildirdigimiz porttan BASKA bir port dondurduyse eski
    # surumdur (gcs_port'u yok sayip kendi portunu bildirmis). Bu durumda
    # ayirdigimiz soketi kullanmak yanlis olur; acik hata donulur, cunku
    # sessiz geri donus pilotun var olmayan bir kanala komut gondermesine
    # yol acar.
    if int(gcs_port or 0) > 0 and port != int(gcs_port):
        return None, ("Merkez surumu akis portu devrini desteklemiyor "
                      "(istenen %d, donen %d). Merkezi guncelleyin."
                      % (int(gcs_port), port))
    return port, None


def video_ac(ornek_id, firma_id, kamera_id, app_port):
    """Canli kamera kanali acar. Doner: `(tamam, hata)`.

    `app_port` ZORUNLUDUR ve cagirici onu ONCE kendisi bind etmis
    olmalidir. Gerekce `akis_ac` ile birebir aynidir: merkez kendi
    portunu bildirseydi, App ayni portu bind etmeye calisip
    `[Errno 98] Address already in use` alirdi. O kusur bir kez
    olculdu; ayni tuzak burada tekrarlanmaz.
    """
    if int(app_port or 0) <= 0:
        return False, "app_port zorunlu"
    g, hata = _ic_cagri("/api/ic/video_ac", {
        "ornek_id": int(ornek_id),
        "firma_id": int(firma_id),
        "kamera_id": int(kamera_id),
        "app_port": int(app_port),
    }, zaman_asimi=20.0)
    if hata:
        return False, hata
    if not (g or {}).get("basarili"):
        return False, str((g or {}).get("hata")
                          or "Canli kamera kanali acilamadi")
    return True, None


def video_kapat(ornek_id, firma_id, kamera_id):
    """Canli kamera kanalini kapatir. Hata metnini dondurur (yoksa None)."""
    g, hata = _ic_cagri("/api/ic/video_kapat", {
        "ornek_id": int(ornek_id),
        "firma_id": int(firma_id),
        "kamera_id": int(kamera_id),
    }, zaman_asimi=12.0)
    if hata:
        return hata
    return str((g or {}).get("kopru_hata") or "") or None


def video_durum(ornek_id, firma_id, kopru=False):
    """Acik canli kamera kanallarinin olcumleri (tanilama)."""
    g, hata = _ic_cagri("/api/ic/video_durum", {
        "ornek_id": int(ornek_id),
        "firma_id": int(firma_id),
        "kopru": bool(kopru),
    }, zaman_asimi=12.0)
    if hata:
        return None, hata
    return (g or {}), None


def akis_kapat(ornek_id, firma_id, kanal_id):
    """Akis kanalini kapatir. Hata metnini dondurur (yoksa None)."""
    g, hata = _ic_cagri("/api/ic/akis_kapat", {
        "ornek_id": int(ornek_id),
        "firma_id": int(firma_id),
        "kanal_id": int(kanal_id),
    }, zaman_asimi=12.0)
    if hata:
        return hata
    return str((g or {}).get("kopru_hata") or "") or None


def akis_durum(ornek_id, firma_id, kopru=False):
    """Acik akis kanallarinin olcumlerini dondurur (tanilama)."""
    g, hata = _ic_cagri("/api/ic/akis_durum", {
        "ornek_id": int(ornek_id),
        "firma_id": int(firma_id),
        "kopru": bool(kopru),
    }, zaman_asimi=12.0)
    if hata:
        return None, hata
    return (g or {}), None


def sifre_degistir(eposta, yeni_sifre):
    """Merkez tablosunda sifre gunceller (pbkdf2 ozeti uretir)."""
    import secrets
    tuz = secrets.token_bytes(16)
    yineleme = 240000
    ozet = hashlib.pbkdf2_hmac(
        "sha256", str(yeni_sifre).encode("utf-8"), tuz, yineleme)
    kayit = "%s$%d$%s$%s" % (
        _ETIKET, yineleme,
        base64.b64encode(tuz).decode("ascii"),
        base64.b64encode(ozet).decode("ascii"))
    _calistir(
        "UPDATE kullanicilar SET sifre_ozet = %s WHERE lower(eposta) = %s",
        (kayit, str(eposta).strip().lower()))
    return True
