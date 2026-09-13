# -*- coding: utf-8 -*-
"""Merkez sunucu API istemcisi (GCS -> merkez, TEK YONLU).

## NEDEN BU MODUL VAR

Kullanici istegi (birebir):

    "kullanici sisteme baglanti yoneticisi bolumunde bir baglanti
     ekleyeceginde sistem acik olan sunuculari gostersin ve kullanici
     secsin, iletisim tek tarafli olacak bunuda belirteyim. Yani client
     to server olacak server kendisine yapilan baglanti uzerinden
     haberlesecek, yani kullanicilarin kurdugu sunucularin sabit ip'si
     yok"

Saha GCS kurulumlari NAT arkasindadir; sabit IP'leri yoktur. Bu yuzden
merkez ASLA saha kurulumuna baglanamaz. Butun trafik saha -> merkez
yonunde acilir:

    Saha GCS  ---- HTTPS / WSS (client -> server) ---->  Merkez
              <--- komut ve yanit AYNI soket uzerinde ---

Bu modul HTTPS tarafini kapsar (sorgu/yanit). Kalici komut kanali
`kopru_ajan.py` icindeki WSS baglantisidir.

## TASARIM KARARLARI

1) BLOKE EDICI CAGRI, ASYNCIO'DA CALISTIRILMAZ
   Buradaki islevler `urllib` ile senkron calisir. `sunucu.py` bunlari
   MUTLAKA `run_in_executor` ile cagirir; aksi halde tek bir yavas
   merkez yaniti tum telemetri yayinini kilitler.

2) SERTIFIKA DOGRULAMASI GEVSETILMEZ
   Merkez adresi gercek bir alan adidir (goktungu.com) ve
   Let's Encrypt sertifikasi vardir. Kendinden imzali sertifika kabul
   etmek, sahadaki her kurulumu ortadaki adam saldirisina acik hale
   getirir. Yalniz `127.0.0.1`/`localhost` icin dogrulama kapatilir
   (ayni makineye kurulum senaryosu).

3) SIFRE DISARI SIZDIRILMAZ
   Cagriyi TARAYICI DEGIL GCS SUNUCUSU yapar. Boylece merkez hesabinin
   sifresi tarayiciya inmez ve CORS sorunu dogmaz.

4) HATA METNI KULLANICIYA GOSTERILIR
   Sessiz basarisizlik en pahali kusur tipidir (v2.4.45 dersi). Her
   islev `(veri, hata)` ikilisi dondurur; hata dizesi Turkce ve
   eyleme cevrilebilir olmak zorundadir.
"""
import json
import os
import platform as _pf
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request

# Merkez sunucunun varsayilan adresi. Kullanici kendi merkezini
# kurabilir; bu yuzden ayarlarda degistirilebilir.
VARSAYILAN_ADRES = "goktungu.com"

# Zaman asimi: saha baglantisi uydu/GSM olabilir. 10 sn'den kisa deger
# yanlis "sunucu yok" karari uretir; 30 sn'den uzugu arayuzu bekletir.
ZAMAN_ASIMI = 12.0

# Yerel adresler: ayni makineye hem merkez hem GCS kurulabilir. Bu
# durumda kendinden imzali sertifika kacinilmazdir.
YEREL_ADLAR = ("127.0.0.1", "localhost", "::1", "0.0.0.0")


def _yerel_mi(adres):
    ad = str(adres or "").strip().lower()
    # "127.0.0.1:8443" gibi port icerebilir
    if ":" in ad and not ad.startswith("["):
        ad = ad.split(":", 1)[0]
    return ad in YEREL_ADLAR


def _taban(adres):
    """Ayardaki adresi tam URL tabanina cevirir.

    Kullanici "goktungu.com", "https://goktungu.com" ya da
    "192.168.1.50:8443" yazabilir; hepsi kabul edilir.
    """
    ad = str(adres or "").strip()
    if not ad:
        ad = VARSAYILAN_ADRES
    if ad.startswith("http://") or ad.startswith("https://"):
        return ad.rstrip("/")
    sema = "http" if _yerel_mi(ad) else "https"
    return f"{sema}://{ad}".rstrip("/")


def _ssl_baglam(adres):
    """SSL baglami. Yalniz yerel adreslerde dogrulama kapatilir."""
    if _yerel_mi(adres):
        b = ssl.create_default_context()
        b.check_hostname = False
        b.verify_mode = ssl.CERT_NONE
        return b
    return ssl.create_default_context()


def _istek(adres, yol, govde=None, yontem="POST", sorgu=None):
    """Merkeze JSON istegi gonderir. `(veri, hata)` dondurur.

    POST cagrilari govdeyi JSON olarak, GET cagrilari `sorgu`yu URL
    parametresi olarak gonderir (merkez GET uclarinda `istek.sorgu`
    okur).
    """
    url = _taban(adres) + yol
    if sorgu:
        url += "?" + urllib.parse.urlencode(sorgu)
    ham = json.dumps(govde or {}, ensure_ascii=False).encode("utf-8")
    istek = urllib.request.Request(
        url, data=ham if yontem == "POST" else None, method=yontem,
        headers={"Content-Type": "application/json",
                 "Accept": "application/json",
                 "User-Agent": "GOKTUNGU-GCS"})
    try:
        with urllib.request.urlopen(
                istek, timeout=ZAMAN_ASIMI,
                context=_ssl_baglam(adres)) as yanit:
            gelen = yanit.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        # Merkez hata govdesinde anlamli aciklama dondurur; onu goster.
        try:
            g = json.loads(e.read().decode("utf-8", errors="replace"))
            mesaj = g.get("hata") or g.get("mesaj") or ""
        except Exception:
            mesaj = ""
        if e.code == 401:
            return None, (mesaj or "Merkez kimlik dogrulamasi basarisiz: "
                                   "e-posta veya sifre hatali.")
        if e.code == 403:
            return None, (mesaj or "Merkez bu islem icin yetki vermiyor.")
        if e.code == 404:
            return None, ("Merkez sunucuda bu servis yok "
                          f"({yol}). Merkez surumu eski olabilir.")
        return None, (mesaj or f"Merkez hatasi (HTTP {e.code}).")
    except urllib.error.URLError as e:
        neden = getattr(e, "reason", e)
        if isinstance(neden, ssl.SSLError):
            return None, ("Merkez sunucunun guvenlik sertifikasi "
                          f"dogrulanamadi: {neden}")
        if isinstance(neden, socket.timeout):
            return None, (f"Merkez sunucuya {int(ZAMAN_ASIMI)} saniyede "
                          "ulasilamadi (zaman asimi).")
        return None, f"Merkez sunucuya ulasilamadi: {neden}"
    except socket.timeout:
        return None, (f"Merkez sunucuya {int(ZAMAN_ASIMI)} saniyede "
                      "ulasilamadi (zaman asimi).")
    except Exception as e:                      # beklenmeyen
        return None, f"Merkez istegi basarisiz: {e}"
    try:
        veri = json.loads(gelen)
    except ValueError:
        return None, ("Merkez sunucudan gecersiz yanit geldi "
                      "(JSON degil). Adres dogru mu?")
    if isinstance(veri, dict) and veri.get("hata"):
        return None, str(veri["hata"])
    return veri, None


# ----------------------------------------------------------------------
# Ayar okuma yardimcisi
# ----------------------------------------------------------------------
def ayar_coz(ayarlar):
    """Program ayarlarindan merkez yapilandirmasini cikarir.

    Doner: {"etkin":bool,"adres":str,"eposta":str,"sifre":str}
    """
    a = ayarlar or {}
    return {
        "etkin": bool(a.get("merkez_etkin")),
        "adres": str(a.get("merkez_adres") or VARSAYILAN_ADRES).strip(),
        "eposta": str(a.get("merkez_eposta") or "").strip(),
        "sifre": str(a.get("merkez_sifre") or ""),
    }


def _kimlik_denetle(y):
    """Hesap eksikse eyleme cevrilebilir hata dondurur."""
    if not y.get("eposta") or not y.get("sifre"):
        return ("Merkez hesabi tanimli degil. Program Ayarlari -> "
                "Merkez Sunucu bolumunden e-posta ve sifre girin.")
    return None


# ----------------------------------------------------------------------
# API cagrilari
# ----------------------------------------------------------------------
def dogrula(yapilandirma):
    """Merkez hesabini sinar. `(bilgi, hata)` dondurur."""
    y = dict(yapilandirma or {})
    hata = _kimlik_denetle(y)
    if hata:
        return None, hata
    veri, hata = _istek(y["adres"], "/api/istemci/giris",
                        {"eposta": y["eposta"], "sifre": y["sifre"]})
    if hata:
        return None, hata
    return veri, None


def acik_sunucular(yapilandirma):
    """Firmaya ait ve O AN acik olan sunuculari dondurur.

    Merkez, canli role soketine gore liste uretir; kapali sunucular
    listede YER ALMAZ (kullanici istegi: "acik olan sunuculari
    gostersin").
    """
    y = dict(yapilandirma or {})
    hata = _kimlik_denetle(y)
    if hata:
        return None, hata
    veri, hata = _istek(y["adres"], "/api/istemci/acik_sunucular",
                        {"eposta": y["eposta"], "sifre": y["sifre"]})
    if hata:
        return None, hata
    liste = (veri or {}).get("sunucular")
    if not isinstance(liste, list):
        liste = []
    return liste, None


def guncelleme_kontrol(yapilandirma, urun="gcs", surum="0.0.0",
                      platform="ortak", kanal="kararli",
                      paket_tur="guncelleme"):
    """Merkez depoda daha yeni surum var mi.

    Kimlik GEREKTIRMEZ: guncelleme kontrolu acik uctur, boylece hesabi
    tanimlanmamis kurulumlar da yama alabilir. Merkez bu ucta GET ve
    sorgu parametresi bekler.

    Yanit alanlari (dogrulanmis):
      guncelleme_var, uygulanabilir, neden, urun, surum, platform,
      kanal, paket_tur, dosya_ad, dosya_boyut, sha256, imza,
      asgari_surum, notlar, url, acik_anahtar
    """
    y = dict(yapilandirma or {})
    veri, hata = _istek(
        y.get("adres") or VARSAYILAN_ADRES, "/api/genel/guncelleme",
        yontem="GET",
        sorgu={"urun": urun, "surum": surum, "platform": platform,
               "kanal": kanal, "paket_tur": paket_tur})
    if hata:
        return None, hata
    return veri or {}, None


def imza_anahtari(yapilandirma):
    """Merkezin Ed25519 acik anahtarini dondurur (dogrulama icin)."""
    y = dict(yapilandirma or {})
    veri, hata = _istek(y.get("adres") or VARSAYILAN_ADRES,
                        "/api/genel/imza_anahtari", yontem="GET")
    if hata:
        return None, hata
    return (veri or {}).get("acik_anahtar") or "", None


def kimlik(yapilandirma):
    """Merkez kimligi: urun, surum, alan_adi, ws_port, sema_surum.

    Adres dogrulamasi icin kullanilir: bu uc yanit veriyorsa adres bir
    GOKTUNGU merkezidir.
    """
    y = dict(yapilandirma or {})
    veri, hata = _istek(y.get("adres") or VARSAYILAN_ADRES,
                        "/api/genel/kimlik", yontem="GET")
    if hata:
        return None, hata
    return veri or {}, None


# ----------------------------------------------------------------------
# KOPRU KIMLIGI (veri/kopru.json)
# ----------------------------------------------------------------------
# Merkez, kurulum sirrini (`gizli`) YALNIZ BIR KEZ dondurur; bir daha
# okunamaz. Bu yuzden kayit yaniti hemen diske yazilir. Dosya kaybolursa
# kayit `yenile=True` ile tazelenmek zorundadir (yeni sir uretilir).
#
# Dosya arayuze ASLA oldugu gibi gonderilmez: `gizli` alani sifre
# degerindedir. `kimlik_ozet()` maskeli kopya uretir.
KOPRU_DOSYA_ADI = "kopru.json"


def _veri_koku():
    """`veri/` dizininin tam yolu (paket disindaki kurulum koku)."""
    try:
        from . import yol as _yol            # varsa merkezi yol modulu
        k = getattr(_yol, "VERI_KOKU", None)
        if k:
            return k
    except Exception:
        pass
    # goktungu/goktungu/merkez.py  ->  <kurulum>/veri
    burasi = os.path.dirname(os.path.abspath(__file__))
    kok = os.path.dirname(burasi)
    # assets/python/goktungu/ yapisinda iki ust dizin daha yukaridadir
    for aday in (os.path.join(kok, "veri"),
                 os.path.join(os.path.dirname(os.path.dirname(kok)), "veri")):
        if os.path.isdir(aday):
            return aday
    aday = os.path.join(kok, "veri")
    try:
        os.makedirs(aday, exist_ok=True)
    except OSError:
        pass
    return aday


def kopru_dosya():
    return os.path.join(_veri_koku(), KOPRU_DOSYA_ADI)


def kimlik_oku():
    """Diskteki kopru kimligini dondurur; yoksa `{}`."""
    try:
        with open(kopru_dosya(), "r", encoding="utf-8") as f:
            veri = json.load(f)
        return veri if isinstance(veri, dict) else {}
    except (OSError, ValueError):
        return {}


def kimlik_yaz(veri):
    """Kopru kimligini diske yazar. `(yol, hata)` dondurur.

    Atomik yazim: gecici dosyaya yazilip `os.replace` ile tasinir; boylece
    yazim ortasinda kesilen surec yarim dosya birakmaz (v2.4.47 dersi:
    yarim JSON, GCS'yi acilista kilitliyordu).
    """
    hedef = kopru_dosya()
    gecici = hedef + ".yeni"
    try:
        os.makedirs(os.path.dirname(hedef), exist_ok=True)
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump(veri or {}, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(gecici, hedef)
        try:
            os.chmod(hedef, 0o600)          # sir icerir
        except OSError:
            pass
        return hedef, None
    except OSError as e:
        return None, f"Kopru kimligi yazilamadi: {e}"


def kimlik_sil():
    try:
        os.remove(kopru_dosya())
    except OSError:
        pass


def kimlik_ozet():
    """Arayuze gonderilebilir MASKELI kopru kimligi.

    `gizli` alani hicbir kosulda arayuze inmez; yalniz var/yok bilgisi
    ve son 4 karakteri bildirilir.
    """
    k = kimlik_oku()
    if not k:
        return {"kayitli": False}
    gizli = str(k.get("gizli") or "")
    return {
        "kayitli": bool(k.get("kurulum_uid")),
        "ornek_id": k.get("ornek_id"),
        "ad": k.get("ad"),
        "kurulum_uid": k.get("kurulum_uid"),
        "merkez_adres": k.get("merkez_adres"),
        "firma_id": k.get("firma_id"),
        "firma_kisa_ad": k.get("firma_kisa_ad"),
        "platform": k.get("platform"),
        "makine_adi": k.get("makine_adi"),
        "surum": k.get("surum"),
        "kayit_ts": k.get("kayit_ts"),
        "gizli_var": bool(gizli),
        "gizli_kuyruk": gizli[-4:] if gizli else "",
    }


# ----------------------------------------------------------------------
# MAKINE KIMLIGI
# ----------------------------------------------------------------------
def platform_adi():
    """Merkez depo adlandirmasiyla uyumlu platform kodu.

    Depo paketleri `linux-x64`, `windows-x64`, `linux-aarch64` gibi
    adlar kullanir; ayni kodlama burada da uretilir ki admin panelinde
    surum/paket eslesmesi tek bakista okunabilsin.
    """
    s = (_pf.system() or "").lower()
    m = (_pf.machine() or "").lower()
    if m in ("x86_64", "amd64"):
        m = "x64"
    elif m in ("aarch64", "arm64"):
        m = "aarch64"
    elif m in ("i386", "i686", "x86"):
        m = "x86"
    if s.startswith("win"):
        s = "windows"
    elif s == "darwin":
        s = "macos"
    elif not s:
        s = "bilinmeyen"
    return f"{s}-{m}" if m else s


def makine_adi():
    try:
        ad = socket.gethostname()
    except Exception:
        ad = ""
    return (ad or "goktungu-gcs").strip()


# ----------------------------------------------------------------------
# SUNUCU KAYDI (kopru ajaninin ilk adimi)
# ----------------------------------------------------------------------
def sunucu_kayit(yapilandirma, ad=None, surum="", aciklama=None,
                 yenile=False, kaydet=True):
    """Bu GCS kurulumunu merkeze **sunucu ornegi** olarak kaydeder.

    Merkez `kurulum_uid` + `gizli` ikilisini dondurur; ikisi birlikte
    kopru ajaninin WSS kimlik bilgisidir. `gizli` bir daha alinamaz, bu
    yuzden yanit varsayilan olarak hemen `veri/kopru.json` icine yazilir.

    Ayni makine ikinci kez kayit isterse merkez 409 dondurur; bu durumda
    `yenile=True` ile cagrilirsa var olan kaydin sirri tazelenir. Boylece
    kurulum tasindiginda ya da `kopru.json` kaybedildiginde kullanici
    yeni bir sunucu lisansi harcamak zorunda kalmaz.

    Doner: `(kimlik_sozlugu, hata)`
    """
    y = dict(yapilandirma or {})
    hata = _kimlik_denetle(y)
    if hata:
        return None, hata
    mevcut = kimlik_oku()
    makine = makine_adi()
    govde = {
        "eposta": y["eposta"],
        "sifre": y["sifre"],
        "ad": str(ad or mevcut.get("ad") or makine).strip(),
        "platform": platform_adi(),
        "makine_adi": makine,
        "surum": str(surum or ""),
    }
    if aciklama:
        govde["aciklama"] = str(aciklama)
    if yenile:
        govde["yenile"] = True
        if mevcut.get("kurulum_uid"):
            govde["kurulum_uid"] = mevcut["kurulum_uid"]
    veri, hata = _istek(y["adres"], "/api/istemci/sunucu_kayit", govde)
    if hata:
        return None, hata
    veri = dict(veri or {})
    veri["platform"] = govde["platform"]
    veri["makine_adi"] = govde["makine_adi"]
    veri["surum"] = govde["surum"]
    veri["adres"] = y["adres"]
    try:
        import time
        veri["kayit_ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        pass
    if kaydet:
        _, yazma_hatasi = kimlik_yaz(veri)
        if yazma_hatasi:
            # Sir kaybedildi: kullaniciya sessiz kalmak en kotusudur.
            return veri, (yazma_hatasi + " Kayit merkezde olustu ancak "
                          "yerel kimlik dosyasi yazilamadi; 'Kaydi "
                          "tazele' ile yeniden deneyin.")
    return veri, None


def kayit_gerekli_mi():
    """Kopru ajani baslayabilir mi? `True` ise once kayit sarttir."""
    k = kimlik_oku()
    return not (k.get("kurulum_uid") and k.get("gizli"))
