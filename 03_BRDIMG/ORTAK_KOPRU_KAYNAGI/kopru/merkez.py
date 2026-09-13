# -*- coding: utf-8 -*-
"""KOPRU YAZILIMI — merkez ile HTTP haberlesmesi.

Kopru yazilimi merkeze IKI ayri kanaldan baglanir:

  * HTTP (bu modul)  — kimlik dogrulama, kurulum kaydi, katalog sorgusu.
    Istege bagli, kisa omurlu.
  * WSS (ajan.py)    — kalici ters baglanti; merkez bu kanal uzerinden
    kopruye sorar.

Ayrimin nedeni: kimlik dogrulama BASIT ve SENKRON olmalidir (kullanici
panelde "Giris" dugmesine basar ve yanit bekler). Kalici WS baglantisi
ise arka planda, yeniden baglanma mantigiyla calisir. Ikisini tek
kanalda birlestirmek, giris ekranini WS oturumunun durumuna baglardi:
merkez bakimda oldugunda kullanici PANELE BILE giremezdi.
"""
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request

from . import ayar as ayar_mod

ZAMAN_ASIMI = 20.0
YEREL_ADLAR = ("127.0.0.1", "localhost", "::1", "0.0.0.0")


# Bulut merkezinde kopru WSS dinleyicisinin portu. HTTP ucu 443'tedir,
# bu yuzden WS adresinden HTTP tabani turetilirken YALNIZ bu port
# dusurulur.
BULUT_KOPRU_WS_PORTLARI = (9443, 9080)


def _http_taban(a=None):
    """HTTP ucunun taban adresini dondurur.

    ## OLCULEN KUSUR (v1.5.8'de duzeltildi)

    Kullanici bildirimi: "kopru yaziliminda lokal sunucuya baglanmaya
    calistigimda hata aliyorum".

    Onceki hali portu KOSULSUZ dusuruyordu (`parc.hostname`). Bulut icin
    dogruydu (9443 -> 443), ancak YEREL Merkez Uygulama HTTP'yi 8000'de
    dinler:

        ws://127.0.0.1:8765/kopru  ->  http://127.0.0.1     (port 80!)
        beklenen                   ->  http://127.0.0.1:8000

    Sonuc: yerel kurulumda her HTTP cagrisi baglanti reddi aliyordu ve
    kullanici giris yapamiyordu.

    Duzeltme: port yalnizca BILINEN bulut kopru WS portlarindan biriyse
    dusurulur; diger tum portlar KORUNUR. Yerel HTTP portu WS portundan
    farkli oldugu icin ayrica `merkez_http` ayari onerilir (arayuzde
    ipucu gosterilir).
    """
    a = a or ayar_mod.ayar_oku()
    taban = str(a.get("merkez_http") or "").strip()
    if taban:
        return taban.rstrip("/")
    # WS adresinden HTTP tabani turet: kullanici yalniz WS adresini
    # degistirmisse HTTP ucu da ayni sunucuya gitmelidir.
    ws = str(a.get("merkez_adres") or ayar_mod.VARSAYILAN_MERKEZ)
    ws = ws.replace("wss://", "https://").replace("ws://", "http://")
    kok = ws.split("/", 3)
    taban = "/".join(kok[:3])
    parc = urllib.parse.urlsplit(taban)
    konak = parc.hostname or ""
    if not konak:
        return taban.rstrip("/")
    # IPv6 adresleri kose parantez ISTER; `hostname` onlari soyar ve
    # "http://::1:8000" gibi cozulemez bir URL uretilirdi.
    if ":" in konak:
        konak = "[%s]" % konak
    try:
        port = parc.port
    except ValueError:
        port = None
    if port and port not in BULUT_KOPRU_WS_PORTLARI:
        return "%s://%s:%d" % (parc.scheme, konak, port)
    return "%s://%s" % (parc.scheme, konak)


def _yerel_mi(adres):
    try:
        ad = urllib.parse.urlsplit(adres).hostname or ""
    except Exception:
        ad = ""
    return str(ad).lower() in YEREL_ADLAR


def _ssl_baglami(url, a=None):
    if not str(url).startswith("https://"):
        return None
    baglam = ssl.create_default_context()
    a = a or ayar_mod.ayar_oku()
    # Yerel merkez kurulumunda kendinden imzali sertifika kacinilmazdir.
    # UZAK adreste dogrulama ASLA gevsetilmez; aksi halde her kurulum
    # ortadaki adam saldirisina acik olur ve merkez sifresi calinabilir.
    if _yerel_mi(url) or a.get("sertifika_dogrulama") is False:
        baglam.check_hostname = False
        baglam.verify_mode = ssl.CERT_NONE
    return baglam


def cagir(yol, govde=None, yontem=None, a=None):
    """Merkez HTTP ucunu cagirir. `(veri, hata)` dondurur.

    Istisna FIRLATMAZ: panelin her hatayi kullaniciya OKUNABILIR bir
    metinle gostermesi gerekir. Yigin izi kullaniciya bir sey anlatmaz.
    """
    a = a or ayar_mod.ayar_oku()
    url = _http_taban(a) + yol
    veri = None
    if govde is not None:
        veri = json.dumps(govde, ensure_ascii=False).encode("utf-8")
    istek = urllib.request.Request(
        url, data=veri, method=(yontem or ("POST" if veri else "GET")))
    istek.add_header("Content-Type", "application/json")
    istek.add_header("User-Agent", "GOKTUNGU-Kopru/%s" % ayar_mod.SURUM)
    try:
        with urllib.request.urlopen(istek, timeout=ZAMAN_ASIMI,
                                    context=_ssl_baglami(url, a)) as y:
            ham = y.read().decode("utf-8", "replace")
        return (json.loads(ham) if ham else {}), None
    except urllib.error.HTTPError as e:
        try:
            g = json.loads(e.read().decode("utf-8", "replace"))
        except Exception:
            g = {}
        mesaj = g.get("hata") or ("Merkez %d yanitladi" % e.code)
        g.setdefault("hata", mesaj)
        g["http_kod"] = e.code
        return g, mesaj
    except urllib.error.URLError as e:
        return None, "Merkeze ulasilamadi: %s" % (
            getattr(e, "reason", None) or e)
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)


def logo_getir(yol):
    """Kurum logosunu merkezden IKILI olarak ceker.

    `cagir()` JSON bekler; logo bir PNG/JPEG/SVG'dir. Ayri islev
    gerekir. Donus: `(baytlar, icerik_turu, hata)`.

    BOYUT SINIRI: merkez logoyu 2 MB ile sinirlar, ama koprunun buna
    GUVENMEMESI gerekir — yanlis yapilandirilmis bir vekil ya da farkli
    surumde bir merkez cok buyuk yanit dondurebilir ve panel surecinin
    bellegini tuketebilir.
    """
    a = ayar_mod.ayar_oku()
    if not str(yol or "").startswith("/"):
        return None, None, "Gecersiz logo yolu"
    url = _http_taban(a) + yol
    istek = urllib.request.Request(url, method="GET")
    istek.add_header("User-Agent", "GOKTUNGU-Kopru/%s" % ayar_mod.SURUM)
    try:
        with urllib.request.urlopen(istek, timeout=ZAMAN_ASIMI,
                                    context=_ssl_baglami(url, a)) as y:
            tur = y.headers.get("Content-Type") or "image/png"
            ham = y.read(2 * 1024 * 1024 + 1)
        if len(ham) > 2 * 1024 * 1024:
            return None, None, "Logo cok buyuk (>2 MB)"
        if not str(tur).lower().startswith("image/"):
            # Merkez oturum duserse HTML giris sayfasi donebilir; onu
            # logo sanip gostermek kirik gorsel uretir.
            return None, None, "Logo yerine %s dondu" % tur
        return ham, tur, None
    except urllib.error.HTTPError as e:
        return None, None, "Merkez %d yanitladi" % e.code
    except Exception as e:
        return None, None, "%s: %s" % (type(e).__name__, e)


# ---------------------------------------------------------------------
# Kimlik dogrulama
# ---------------------------------------------------------------------
def giris_dogrula(eposta, sifre):
    """Merkez kullanicisini dogrular. `(kullanici, hata)`.

    Kopru YEREL bir kullanici veritabani TUTMAZ. Tek dogruluk kaynagi
    merkezdir; boylece merkezde askiya alinan bir personel sahadaki
    kopruye de giremez. Yerel kopya tutulsaydi, isten ayrilan bir
    pilotun erisimi sahada aylarca acik kalabilirdi.
    """
    veri, hata = cagir("/api/istemci/giris",
                       {"eposta": eposta, "sifre": sifre})
    if hata:
        return None, hata
    k = (veri or {}).get("kullanici") or {}
    if not k.get("firma_id"):
        return None, "Merkez yaniti eksik: firma bilgisi yok"
    return k, None


def kurulum_kaydet(eposta, sifre, ad=None, yenile=False, aciklama=None):
    """Bu bilgisayari merkeze **sunucu ornegi** olarak kaydeder.

    Yanitta donen `gizli` merkez tarafindan BIR DAHA GOSTERILMEZ; bu
    yuzden hemen `kimlik.json` icine yazilir. `yenile=True` var olan
    kaydin gizlisini tazeler (kurulum tasima veya gizli kaybi).
    """
    a = ayar_mod.ayar_oku()
    mevcut = ayar_mod.kimlik_oku()
    govde = {
        "eposta": eposta, "sifre": sifre,
        "ad": (ad or "").strip() or ayar_mod.makine_adi(),
        "makine_adi": ayar_mod.makine_adi(),
        "platform": ayar_mod.platform_adi(),
        "surum": ayar_mod.SURUM,
        "aciklama": aciklama or "GOKTUNGU Kopru Yazilimi",
    }
    if yenile:
        govde["yenile"] = True
        if mevcut.get("kurulum_uid"):
            govde["kurulum_uid"] = mevcut["kurulum_uid"]
    veri, hata = cagir("/api/istemci/sunucu_kayit", govde, a=a)
    if hata:
        # 409: bu makine zaten kayitli. Kullaniciya ne yapacagini
        # SOYLEMEK gerekir; ciplak "409" hicbir sey anlatmaz.
        if (veri or {}).get("kayitli"):
            return None, ("Bu makine merkezde zaten kayitli (ornek %s). "
                          "Kimligi yenilemek icin 'Kimligi Yenile' "
                          "dugmesini kullanin."
                          % (veri.get("ornek_id")))
        return None, hata
    if not (veri or {}).get("gizli"):
        return None, "Merkez gizli anahtar dondurmedi"
    kimlik = {
        "kurulum_uid": veri.get("kurulum_uid") or "",
        "gizli": veri.get("gizli") or "",
        "ornek_id": veri.get("ornek_id"),
        "ad": veri.get("ad") or govde["ad"],
        "firma_id": veri.get("firma_id"),
        "firma_kisa_ad": veri.get("firma_kisa_ad") or "",
        "eposta": eposta,
    }
    ayar_mod.kimlik_yaz(kimlik)
    # Merkez kendi kopru adresini bildirirse onu kullan: merkez tasinirsa
    # kurulumlar elle duzeltilmek zorunda kalmasin.
    if veri.get("merkez_adres"):
        ayar_mod.ayar_guncelle(merkez_adres=veri["merkez_adres"])
    return ayar_mod.kimlik_maskeli(), None
