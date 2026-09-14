"""Merkez sunucudan kullanici esitlemesi (Merkez Uygulama kurulumu).

NEDEN BU MODUL VAR — OLCULEN KUSUR (2026-08-16)
================================================
Merkez Uygulama satin alan firma kurulumu tamamladiginda, yerel
`kullanicilar` tablosu BOS kaliyordu. Bu durumda
`kullanicilar.py::_ilk_yonetici_guvence()` kaynak koda GOMULU bir
hesap yaratiyordu:

    e-posta: mkaderoglu@gokkubbetech.com
    sifre  : gokkubbe2026        <-- kaynak kodda sabit

Sonuc iki yonlu kusurdu:

1. ISLEVSEL: Firmanin /company/ panelinde tanimladigi sifre Merkez
   Uygulama'da GECERSIZ kaliyordu. Kullanicinin bildirimi:
   "kullanici emaili dogru olmasina ragmen sifre benim merkezde
   verdigim sifre yerine gokkubbe2026 olmus".

2. GUVENLIK: Her Merkez Uygulama kurulumunda AYNI bilinen sifre
   gecerliydi. 5.000 USD'lik urun, kaynak kodu goren herkesin
   bildigi bir sifreyle aciliyordu.

COZUM
=====
Kurulum, merkezdeki gercek kullanici listesini BIR KEZ ceker ve yerel
tabloya yazar. Sifre OZETLERI oldugu gibi tasinir (`pbkdf2_sha256$...`);
`veritabani.sifre_dogrula()` bu bicimi tanir. Boylece merkezde
tanimlanan sifre Merkez Uygulama'da da gecerli olur.

Esitleme BIR KEZ yapilir; sonrasinda uygulama KAPALI DEVRE calisir
(kullanicinin sarti: "isterse kapali devre kullanabiliyor"). Surekli
merkez baglantisi GEREKMEZ.

NEDEN DUZ SIFRE DEGIL OZET TASINIYOR
====================================
Duz sifre merkezde de saklanmaz; yalniz ozeti vardir. Ozet tasimak
duz sifre tasimaktan guvenlidir. Alternatif (tum kullanicilarin
sifresini yeniden belirlemesi) kullanici istegine aykiridir:
"merkezde ne verdiysem 5.000 dolarlik merkez yazilimda da o sifre
gecerli olmali".

NEDEN LISANSTAN MERKEZ ADRESI OKUNMUYOR
=======================================
Lisans govdesi imzalidir ve alanlari OLCULDU: surum, firma_id,
firma_unvan, lisans_uid, yetkiler. Merkez adresi YOKTUR. Govdeye alan
eklemek imza sozlesmesini bozar ve DAGITILMIS TUM lisanslari
gecersiz kilar. Bu yuzden adres ayrica istenir; kullanici paketi
zaten merkezden indirdigi icin adresi bilir.
"""
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request

_ZAMAN_ASIMI = 20


# ----------------------------------------------------------------------
# Yardimcilar
# ----------------------------------------------------------------------
def _adres_duzelt(adres):
    """Kullanicinin girdigi adresi kullanilabilir tabana cevirir.

    Kabul edilen bicimler (hepsi olculdu, varsayilmadi):
      goktungu.com
      https://goktungu.com
      https://goktungu.com/
      https://goktungu.com/company/
    """
    a = str(adres or "").strip()
    if not a:
        return ""
    if not a.startswith("http://") and not a.startswith("https://"):
        a = "https://" + a
    # Sondaki yol parcalarini at: yalniz sema://konak[:port] kalir.
    p = urllib.parse.urlsplit(a)
    if not p.netloc:
        return ""
    return "%s://%s" % (p.scheme, p.netloc)


def _baglam(dogrula=True):
    """TLS baglami. Yerel adreslerde kendinden imzali sertifika olabilir."""
    if dogrula:
        return None          # urllib varsayilani: dogrular
    b = ssl.create_default_context()
    b.check_hostname = False
    b.verify_mode = ssl.CERT_NONE
    return b


def _yerel_mi(taban):
    """127.0.0.1 / localhost / ozel ag adresi mi?

    AGENTS.md'deki kural: TLS zinciri YALNIZ yerel adres icin gevsetilir,
    diger adreslerde ASLA.
    """
    try:
        konak = urllib.parse.urlsplit(taban).hostname or ""
    except Exception:
        return False
    konak = konak.lower()
    if konak in ("127.0.0.1", "localhost", "::1"):
        return True
    if konak.startswith("192.168.") or konak.startswith("10."):
        return True
    if konak.startswith("172."):
        try:
            ikinci = int(konak.split(".")[1])
            return 16 <= ikinci <= 31
        except (IndexError, ValueError):
            return False
    return False


# ----------------------------------------------------------------------
# Merkez oturumu
# ----------------------------------------------------------------------
def _istek(taban, yol, veri=None, cerez="", dogrula=True):
    """Merkeze HTTP istegi atar. Doner: (durum, govde_sozluk, cerez)."""
    url = taban.rstrip("/") + yol
    basliklar = {"Accept": "application/json"}
    govde_bayt = None
    if veri is not None:
        govde_bayt = json.dumps(veri).encode("utf-8")
        basliklar["Content-Type"] = "application/json"
    if cerez:
        basliklar["Cookie"] = cerez
    istek = urllib.request.Request(url, data=govde_bayt, headers=basliklar)
    baglam = _baglam(dogrula)
    try:
        if baglam is None:
            yanit = urllib.request.urlopen(istek, timeout=_ZAMAN_ASIMI)
        else:
            yanit = urllib.request.urlopen(istek, timeout=_ZAMAN_ASIMI,
                                           context=baglam)
        with yanit:
            ham = yanit.read().decode("utf-8", "replace")
            # Set-Cookie: oturum cerezi
            yeni_cerez = ""
            for anahtar, deger in yanit.getheaders():
                if anahtar.lower() == "set-cookie":
                    yeni_cerez = deger.split(";")[0]
                    break
            try:
                return yanit.status, json.loads(ham), yeni_cerez
            except ValueError:
                return yanit.status, {"ham": ham}, yeni_cerez
    except urllib.error.HTTPError as e:
        ham = ""
        try:
            ham = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        try:
            return e.code, json.loads(ham), ""
        except ValueError:
            return e.code, {"hata": ham or str(e)}, ""
    except urllib.error.URLError as e:
        return 0, {"hata": "Merkeze ulasilamadi: %s" % e.reason}, ""
    except Exception as e:
        return 0, {"hata": "Merkez istegi basarisiz: %s" % e}, ""


def kullanicilari_cek(adres, eposta, sifre):
    """Merkezden firma kullanici listesini ceker.

    Doner: (liste, hata). Liste None ise hata metni doludur.

    Hata metinleri KULLANICIYA GOSTERILIR; kapali devre musteri destek
    arayamayabilir, ekranda ne yapmasi gerektigini gormeli.
    """
    taban = _adres_duzelt(adres)
    if not taban:
        return None, "Merkez adresi gecersiz. Ornek: goktungu.com"

    dogrula = not _yerel_mi(taban)

    # 1) Giris
    durum, govde, cerez = _istek(
        taban, "/api/firma/giris",
        {"eposta": str(eposta or "").strip().lower(),
         "sifre": str(sifre or "")},
        dogrula=dogrula)
    if durum != 200:
        ileti = (govde or {}).get("hata") or "Giris basarisiz"
        if durum == 0:
            return None, ileti
        return None, "Merkez girisi basarisiz (%s): %s" % (durum, ileti)
    if not cerez:
        return None, ("Merkez oturum cerezi alinamadi. Adresin dogru "
                      "oldugundan emin olun.")

    # 2) Kullanici listesi
    durum, govde, _ = _istek(taban, "/api/firma/merkez_kullanicilar",
                             cerez=cerez, dogrula=dogrula)
    if durum == 403:
        return None, ((govde or {}).get("hata") or
                      "Bu firmanin Merkez Uygulama lisansi yok")
    if durum != 200:
        return None, ("Kullanici listesi alinamadi (%s): %s"
                      % (durum, (govde or {}).get("hata") or ""))

    liste = (govde or {}).get("kullanicilar")
    if not isinstance(liste, list) or not liste:
        return None, "Merkezde bu firmaya ait kullanici bulunamadi"
    return liste, ""


# ----------------------------------------------------------------------
# Yerel tabloya yazma
# ----------------------------------------------------------------------
def yerele_yaz(liste):
    """Cekilen kullanicilari yerel `kullanicilar` tablosuna yazar.

    Var olan e-posta GUNCELLENIR (sifre ozeti dahil), olmayan EKLENIR.
    Yerelde olup merkezde olmayan kullanici SILINMEZ; Merkez Uygulama
    kapali devre calisirken yerel olarak eklenmis bir hesabi silmek
    veri kaybi olur.

    Doner: (eklendi, guncellendi, hata)
    """
    # OLCULDU: `baglanti` ve tablo semasi `veritabani.py`'de tanimli.
    # `kullanicilar.py` onu yalniz ice aktarir (satir 11).
    from .veritabani import baglanti

    # ROL ESLEMESI — OLCULDU, VARSAYILMADI
    #   Merkez roller (mk semasi) : firma_yonetici, pilot, gozlemci
    #   GOKTUNGU roller (veritabani.py:330 + kullanicilar.py:181,238):
    #                               yonetici, kullanici
    #
    # GOKTUNGU'da `pilot` veya `gozlemci` diye rol YOKTUR; kod
    # `gecerli_roller = {"yonetici", "kullanici"}` ile dogrular.
    # Eslenmeyen rol yazmak, kullanicinin arayuzde rol
    # duzenlemesini bozardi.
    rol_esle = {
        "firma_yonetici": "yonetici",
        "pilot": "kullanici",
        "gozlemci": "kullanici",
    }

    eklendi = 0
    guncellendi = 0
    try:
        with baglanti() as con:
            for k in liste:
                eposta = str(k.get("eposta") or "").strip().lower()
                if not eposta:
                    continue
                ozet = str(k.get("sifre_ozet") or "")
                if not ozet:
                    continue
                rol = rol_esle.get(str(k.get("rol") or ""), "kullanici")
                ad_soyad = str(k.get("ad_soyad") or "") or eposta
                unvan = str(k.get("unvan") or "")
                aktif = 1 if k.get("aktif") else 0

                var = con.execute(
                    "SELECT 1 FROM kullanicilar WHERE eposta = ?",
                    (eposta,)).fetchone()
                if var:
                    con.execute(
                        "UPDATE kullanicilar SET ad_soyad=?, unvan=?, "
                        "rol=?, sifre=?, aktif=? WHERE eposta=?",
                        (ad_soyad, unvan, rol, ozet, aktif, eposta))
                    guncellendi += 1
                else:
                    con.execute(
                        "INSERT INTO kullanicilar "
                        "(eposta, ad_soyad, unvan, rol, sifre, avatar, aktif) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (eposta, ad_soyad, unvan, rol, ozet, "", aktif))
                    eklendi += 1
    except Exception as e:
        return eklendi, guncellendi, "Yerel tabloya yazilamadi: %s" % e
    return eklendi, guncellendi, ""


def esitle(adres, eposta, sifre):
    """Uctan uca esitleme: cek + yaz.

    Doner: (ozet_sozluk, hata)
    """
    liste, hata = kullanicilari_cek(adres, eposta, sifre)
    if hata:
        return None, hata
    eklendi, guncellendi, hata2 = yerele_yaz(liste)
    if hata2:
        return None, hata2
    return {"cekilen": len(liste), "eklendi": eklendi,
            "guncellendi": guncellendi}, ""


def lisans_cek(adres, eposta, sifre):
    """v2.4.201: Merkezden GUNCEL imzali lisans belgesini ceker.

    Kullanici bildirimi: yerel `merkez_lisans.json` eski kalinca (ornegin
    M50 yetkisi merkezde sonradan acildiginda) Elektro-Optik menusu
    gorunmuyordu ve tek yol belgeyi kurumsal panelden elle indirip
    dosyayi degistirmekti. Bu islev `kullanicilari_cek` ile AYNI giris
    yolunu kullanir (firma yoneticisi oturumu), belgeyi
    `/api/firma/merkez_lisans` ucundan alir ve imza dogrulamasi ile
    diske yazilmasi icin `lisans.lisans_yaz`e verilecek sozlugu doner.

    Doner: (belge, hata). Belge None ise hata metni doludur.
    """
    taban = _adres_duzelt(adres)
    if not taban:
        return None, "Merkez adresi gecersiz. Ornek: goktungu.com"
    dogrula = not _yerel_mi(taban)
    durum, govde, cerez = _istek(
        taban, "/api/firma/giris",
        {"eposta": str(eposta or "").strip().lower(),
         "sifre": str(sifre or "")},
        dogrula=dogrula)
    if durum != 200:
        ileti = (govde or {}).get("hata") or "Giris basarisiz"
        if durum == 0:
            return None, ileti
        return None, "Merkez girisi basarisiz (%s): %s" % (durum, ileti)
    if not cerez:
        return None, ("Merkez oturum cerezi alinamadi. Adresin dogru "
                      "oldugundan emin olun.")
    durum, govde, _ = _istek(taban, "/api/firma/merkez_lisans",
                             cerez=cerez, dogrula=dogrula)
    if durum == 403:
        return None, ((govde or {}).get("hata") or
                      "Bu firmanin Merkez Uygulama lisansi yok ya da "
                      "hesap firma yoneticisi degil")
    if durum != 200:
        return None, ("Lisans belgesi alinamadi (%s): %s"
                      % (durum, (govde or {}).get("hata") or ""))
    if not isinstance(govde, dict) or not govde.get("lisans") or not govde.get("imza"):
        return None, "Merkez gecerli bir lisans belgesi dondurmedi"
    return {"lisans": govde["lisans"], "imza": govde["imza"]}, ""
