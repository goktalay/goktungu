#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""GÖKTUNGU MERKEZ — guncelleme deposu ve imzalama.

Bu modul, GCS ve istemci yazilimlarinin guncelleme paketlerini merkez
sunucuda saklar, imzalar ve istemcilere sunar.

Tasarim kararlari
-----------------
1. **Ed25519 imza.** Ozel anahtar YALNIZ merkez sunucuda (`veri/imza/`),
   acik anahtar istemci paketine gomulur. Istemci indirdigi paketi acmadan
   once imzayi dogrular; dogrulanamayan paket ASLA uygulanmaz.
2. **SHA-256 ozeti** imzadan bagimsiz olarak da tutulur; boylece indirme
   bozulmasi (imza gecerliyken bile) yakalanabilir.
3. **Kanal ayrimi** (`kararli` / `beta` / `deneysel`): saha kurulumlari
   varsayilan olarak yalniz `kararli` kanali gorur.
4. **`asgari_surum`**: bir paket yalnizca belirli bir surumden itibaren
   uygulanabiliyorsa (ornegin sema gocu zinciri) bu alan zorlanir.
5. Paket dosyalari `depo/` altinda `urun/surum/` duzeninde tutulur; ayni
   dosya adi iki kez yazilamaz (uzerine yazma kazasi engellenir).

Imza bicimi: ham Ed25519 imzasi, base64 (urlsafe degil) olarak `imza`
kolonunda saklanir. Imzalanan icerik paketin SHA-256 ozetinin **ikili**
hali degil, asagidaki kanonik dizedir:

    urun|surum|platform|paket_tur|sha256|dosya_boyut

Bu sekilde saldirgan gecerli imzali bir paketi baska bir urun/platform
kaydina tasiyamaz (imza baglami paketle birlikte kilitlenir).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
from typing import Any, Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.exceptions import InvalidSignature

import mk_ayar
import mk_db

# ---------------------------------------------------------------- sabitler

URUNLER = ("gcs", "sunucu", "dron", "video", "radar", "ai", "kopru")

# Genel (kimlik istemeyen) tanitim katalogunda GORUNMEYECEK urunler.
#
# Dagitim modeli: komuta kontrol yazilimi (`gcs`) MERKEZDE, /app/
# altinda calisir; kuruma ayri bir kurulum dusmez.  Sahadaki bilgisayara
# yalnizca `kopru` paketi kurulur.  GCS paketini tanitim sayfasinda
# indirilebilir gostermek iki somut zarar uretiyordu:
#
#   1) Kurum, merkezde hazir calisan arayuzun ayni kopyasini kendi
#      makinesine kuruyor; kendi PostgreSQL'ini, kendi sema gocunu ve
#      kendi surum takibini islemek zorunda kaliyor.  Merkezle iki ayri
#      dogruluk kaynagi olusuyor.
#   2) Kurulum sonrasi acilista sema gocu sihirbazi cikiyor ve pilotu
#      operatorun isiyle mesgul ediyor.
#
# Kayit depoda ETKIN kalir -- Merkez Uygulama lisansi satin alan kurum
# paketi kurumsal panelinden indirir ve guncelleme ucu
# (`/api/genel/guncelleme?urun=gcs`) calismaya devam eder.  Gizlenen
# tanitim sayfasindaki vitrindir.
GENEL_GIZLI_URUNLER = ("gcs",)

# Kimlik istemeyen statik `/indir/` yolundan SUNULMAYACAK urunler.
#
# NEDEN AYRI LISTE: `GENEL_GIZLI_URUNLER` yalnizca tanitim vitrinini
# suzer; vitrinden cikarmak dosyayi korumaz.  Merkez Uygulama (`gcs`)
# tek seferlik 5.000 USD karsiligi satildigi icin, dosya adini bilen
# birinin `/indir/gcs/<surum>/<dosya>` isteyip paketi almasi gercek bir
# gelir kaybidir.  Bu listedeki urunler statik sunucuda 403 alir ve
# yalnizca oturum + `merkez_lisans` dogrulayan
# `/api/firma/merkez_indir` ucundan inilir.
#
# Depodaki diger urunler (ozellikle `kopru`) ucretsiz dagitildigi icin
# listede DEGILDIR; koprunun kurulumu ve otomatik guncellemesi kimlik
# istemeyen yoldan surmelidir.
LISANSLI_URUNLER = ("gcs",)

# Statik `/indir/` yolundan SUNULMAYACAK, ancak lisans degil yalnizca
# OTURUM isteyen urunler.
#
# KULLANICI KARARI (2026-08-16): "bence herkes uye panelinden indirsin,
# ayni merkez yazilim gibi. siteye direkt koymayalim".
#
# NEDEN LISANSLI_URUNLER'E EKLENMEDI: kopru UCRETSIZDIR; lisans sarti
# konsa hicbir kurum indiremezdi.  Buradaki amac odeme degil, dagitimin
# tek kapidan (kurumsal panel) yurumesi ve kimin indirdiginin
# kayitlanmasidir.  `/api/firma/kopru_indir` oturum ister, lisans
# istemez.
#
# GUNCELLEME UCU ETKILENMEZ: `/api/genel/guncelleme?urun=kopru` surum
# bilgisini ve indirme adresini dondurmeye devam eder; kurulu koprunun
# kendini guncellemesi bu listeden bagimsizdir.
# `video` (Goruntu Koprusu) — IS83-GORUNTU-DAGITIM
# Olculdu (2026-08-21): `/indir/video/1.0.0/...` OTURUMSUZ 200
# donuyordu; `kopru` ve `gcs` ayni anda 403 veriyordu. Bu bir
# tutarsizlikti. Kullanicinin 2026-08-16 karari ("herkes uye
# panelinden indirsin") Goruntu Koprusu icin de gecerlidir.
#
# LISANSLI_URUNLER'e EKLENMEDI: Goruntu Koprusu ayri satilan bir
# urun degil; `kopru` ile ayni ucretsiz dagitim modelindedir.
#
# ISTEMCI KIRILMA RISKI YOK (olculdu): Goruntu Koprusu 1.0.0
# kaynaginda urlopen/requests/urlretrieve cagrisi yalniz sinav
# dosyalarinda var, urun kodunda yok — otomatik guncelleme
# yetenegi bulunmuyor.
OTURUM_GEREKEN_URUNLER = ("kopru", "video")

# `android`: Pixhawk/MAVLink kopru uygulamasi (APK).
# Ayri URUN olarak eklenmedi - mk_sunucu.py statik `/indir/<urun>/`
# oturum kapisi urun adina bakar; ayri urun oturumsuz indirmeye
# kapi acardi. `kopru` urunu altinda platform olarak durur.
# APK dosya adiyla suzulur: -MAVLink-
# FAZ19-IS39-ANDROID-KOPRU
PLATFORMLAR = ("ortak", "linux", "windows", "linux-arm64", "android")
KANALLAR = ("kararli", "beta", "deneysel")
PAKET_TURLERI = ("tam", "guncelleme")

_SURUM_KALIP = re.compile(r"^\d+(\.\d+){1,3}$")
_OZET_BLOK = 1024 * 1024


def _depo_koku() -> str:
    yol = mk_ayar.DEPO_KOKU
    os.makedirs(yol, exist_ok=True)
    return yol


def _imza_koku() -> str:
    yol = os.path.join(mk_ayar.VERI_KOKU, "imza")
    os.makedirs(yol, mode=0o700, exist_ok=True)
    return yol


# ---------------------------------------------------------------- anahtar


def anahtar_yollari() -> tuple[str, str]:
    kok = _imza_koku()
    return (
        os.path.join(kok, "goktungu_imza_gizli.pem"),
        os.path.join(kok, "goktungu_imza_acik.pem"),
    )


def anahtar_uret(zorla: bool = False) -> dict[str, Any]:
    """Ed25519 anahtar cifti uretir. Var olan anahtari EZMEZ."""
    gizli_yol, acik_yol = anahtar_yollari()
    if os.path.exists(gizli_yol) and not zorla:
        return {"olustu": False, "gizli": gizli_yol, "acik": acik_yol,
                "acik_b64": acik_anahtar_b64()}

    gizli = Ed25519PrivateKey.generate()
    pem_gizli = gizli.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pem_acik = gizli.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    # once gecici dosyaya yaz, sonra yerine koy (yarim dosya birakmamak icin)
    gec = gizli_yol + ".yeni"
    with open(gec, "wb") as f:
        f.write(pem_gizli)
    os.chmod(gec, 0o600)
    os.replace(gec, gizli_yol)
    with open(acik_yol, "wb") as f:
        f.write(pem_acik)
    os.chmod(acik_yol, 0o644)
    return {"olustu": True, "gizli": gizli_yol, "acik": acik_yol,
            "acik_b64": acik_anahtar_b64()}


def _gizli_anahtar() -> Ed25519PrivateKey:
    gizli_yol, _ = anahtar_yollari()
    if not os.path.exists(gizli_yol):
        anahtar_uret()
    with open(gizli_yol, "rb") as f:
        anahtar = serialization.load_pem_private_key(f.read(), password=None)
    if not isinstance(anahtar, Ed25519PrivateKey):
        raise ValueError("imza anahtari Ed25519 degil")
    return anahtar


def _acik_anahtar() -> Ed25519PublicKey:
    _, acik_yol = anahtar_yollari()
    if not os.path.exists(acik_yol):
        anahtar_uret()
    with open(acik_yol, "rb") as f:
        anahtar = serialization.load_pem_public_key(f.read())
    if not isinstance(anahtar, Ed25519PublicKey):
        raise ValueError("acik anahtar Ed25519 degil")
    return anahtar


def acik_anahtar_b64() -> str:
    """Istemciye gomulecek 32 baytlik ham acik anahtar (base64)."""
    try:
        ham = _acik_anahtar().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    except Exception:
        return ""
    return base64.b64encode(ham).decode("ascii")


# ---------------------------------------------------------------- ozet/imza


def dosya_ozeti(yol: str) -> tuple[str, int]:
    ozet = hashlib.sha256()
    boyut = 0
    with open(yol, "rb") as f:
        while True:
            blok = f.read(_OZET_BLOK)
            if not blok:
                break
            boyut += len(blok)
            ozet.update(blok)
    return ozet.hexdigest(), boyut


def imza_baglami(urun: str, surum: str, platform: str, paket_tur: str,
                 sha256: str, boyut: int) -> bytes:
    return "|".join((urun, surum, platform, paket_tur, sha256,
                     str(boyut))).encode("utf-8")


def imzala(urun: str, surum: str, platform: str, paket_tur: str,
           sha256: str, boyut: int) -> str:
    ham = _gizli_anahtar().sign(
        imza_baglami(urun, surum, platform, paket_tur, sha256, boyut))
    return base64.b64encode(ham).decode("ascii")


def imza_dogrula(urun: str, surum: str, platform: str, paket_tur: str,
                 sha256: str, boyut: int, imza_b64: str) -> bool:
    try:
        _acik_anahtar().verify(
            base64.b64decode(imza_b64),
            imza_baglami(urun, surum, platform, paket_tur, sha256, boyut))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


# ---------------------------------------------------------------- genel imza
# 2026-08-15 — Merkez Uygulama lisansi icin eklendi.
#
# NEDEN AYRI ISLEV: yukaridaki `imzala()` paket ustverisine ozeldir
# (urun|surum|platform|...). Lisans belgesi tamamen farkli bir govde
# tasir. Ayni anahtar cifti kullanilir, boylece yeni anahtar yonetimi
# ve yeni bagimlilik gerekmez; yalniz imzalanan bayt dizisi degisir.
#
# ONEMLI: cagiran taraf govdeyi KANONIK bicimde (sort_keys) uretmekle
# yukumludur. Sozluk sirasi degisirse imza dogrulamasi rastgele
# basarisiz olur.


def veri_imzala(ham: bytes) -> str:
    """Verilen ham bayt dizisini Ed25519 ile imzalar, base64 dondurur."""
    return base64.b64encode(_gizli_anahtar().sign(ham)).decode("ascii")


def veri_imza_dogrula(ham: bytes, imza_b64: str) -> bool:
    try:
        _acik_anahtar().verify(base64.b64decode(imza_b64), ham)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


# ---------------------------------------------------------------- surum karsilastirma


def surum_ayikla(s: str) -> tuple[int, ...]:
    parcalar = []
    for p in str(s or "").strip().split("."):
        sayi = re.sub(r"[^0-9]", "", p)
        parcalar.append(int(sayi) if sayi else 0)
    while len(parcalar) < 4:
        parcalar.append(0)
    return tuple(parcalar[:4])


def surum_kiyas(a: str, b: str) -> int:
    ta, tb = surum_ayikla(a), surum_ayikla(b)
    return (ta > tb) - (ta < tb)


# ---------------------------------------------------------------- depo islemleri


def paket_yolu(urun: str, surum: str, dosya_ad: str) -> str:
    return os.path.join(_depo_koku(), urun, surum, dosya_ad)


def paket_ekle(urun: str, surum: str, kaynak_yol: str, *,
               platform: str = "ortak", kanal: str = "kararli",
               paket_tur: str = "guncelleme",
               asgari_surum: Optional[str] = None,
               notlar: Optional[str] = None,
               yonetici_id: Optional[int] = None) -> dict[str, Any]:
    """Bir paket dosyasini depoya alir, imzalar ve kaydeder."""
    urun = (urun or "").strip().lower()
    surum = (surum or "").strip()
    platform = (platform or "ortak").strip().lower()
    kanal = (kanal or "kararli").strip().lower()
    paket_tur = (paket_tur or "guncelleme").strip().lower()

    if urun not in URUNLER:
        raise ValueError(f"gecersiz urun: {urun} (gecerli: {', '.join(URUNLER)})")
    if not _SURUM_KALIP.match(surum):
        raise ValueError(f"gecersiz surum bicimi: {surum} (ornek: 2.4.52)")
    if platform not in PLATFORMLAR:
        raise ValueError(f"gecersiz platform: {platform}")
    if kanal not in KANALLAR:
        raise ValueError(f"gecersiz kanal: {kanal}")
    if paket_tur not in PAKET_TURLERI:
        raise ValueError(f"gecersiz paket turu: {paket_tur}")
    if not os.path.isfile(kaynak_yol):
        raise FileNotFoundError(kaynak_yol)
    if asgari_surum and not _SURUM_KALIP.match(asgari_surum.strip()):
        raise ValueError(f"gecersiz asgari surum: {asgari_surum}")

    dosya_ad = os.path.basename(kaynak_yol)
    hedef = paket_yolu(urun, surum, dosya_ad)
    os.makedirs(os.path.dirname(hedef), exist_ok=True)

    sha256, boyut = dosya_ozeti(kaynak_yol)
    if boyut == 0:
        raise ValueError("paket dosyasi bos")

    # Ayni kayit var mi (urun+surum+platform+paket_tur benzersiz)
    #
    # `etkin=TRUE` KOSULU ZORUNLU (olculen kusur, 16 Agu 2026):
    # Hata metni "once devre disi birakin veya surum numarasini artirin"
    # diyor, ama denetim `etkin` bayragini gozetmedigi icin devre disi
    # birakmak ISE YARAMIYORDU: kayit tabloda kaldigi surece ayni surum
    # numarasi kalici olarak kilitleniyordu. Olculen olay: kopru 1.5.8
    # yanlislikla .zip/.tar.gz ile kaydedildi; dogru setup .exe / .deb
    # ile degistirmek istendiginde kayitlar devre disi birakilmasina
    # ragmen `paket_ekle` reddetti.
    #
    # Devre disi kayitlar zaten hicbir akista gorunmez (`liste`,
    # `son_surum`, `guncelleme_kontrol`, katalog hepsi `etkin` suzer);
    # bu yuzden onlari cakisma sayma dogru davranistir. Asagidaki
    # INSERT ... ON CONFLICT yine ayni benzersiz anahtari hedefler ve
    # kaydi `etkin=TRUE` yaparak tazeler, yani kayit cogaltilmaz.
    mevcut = mk_db.tek(
        "SELECT surum_id, sha256, dosya_ad FROM surumler "
        "WHERE urun=%s AND surum=%s AND platform=%s AND paket_tur=%s "
        "AND etkin=TRUE",
        (urun, surum, platform, paket_tur))
    if mevcut and mevcut["sha256"] != sha256:
        raise ValueError(
            f"bu surum zaten farkli bir dosyayla kayitli "
            f"(surum_id={mevcut['surum_id']}, dosya={mevcut['dosya_ad']}); "
            f"once devre disi birakin veya surum numarasini artirin")

    if os.path.exists(hedef):
        var_ozet, _ = dosya_ozeti(hedef)
        if var_ozet != sha256:
            raise ValueError(f"depoda ayni adli farkli dosya var: {hedef}")
    else:
        gec = hedef + ".yeni"
        shutil.copyfile(kaynak_yol, gec)
        os.replace(gec, hedef)
        os.chmod(hedef, 0o644)

    imza = imzala(urun, surum, platform, paket_tur, sha256, boyut)
    if not imza_dogrula(urun, surum, platform, paket_tur, sha256, boyut, imza):
        raise RuntimeError("uretilen imza dogrulanamadi")

    kayit = mk_db.tek(
        """
        INSERT INTO surumler
            (urun, surum, platform, kanal, paket_tur, dosya_ad, dosya_boyut,
             sha256, imza, asgari_surum, notlar, etkin)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, TRUE)
        ON CONFLICT (urun, surum, platform, paket_tur) DO UPDATE SET
            kanal        = EXCLUDED.kanal,
            dosya_ad     = EXCLUDED.dosya_ad,
            dosya_boyut  = EXCLUDED.dosya_boyut,
            sha256       = EXCLUDED.sha256,
            imza         = EXCLUDED.imza,
            asgari_surum = COALESCE(EXCLUDED.asgari_surum, surumler.asgari_surum),
            notlar       = COALESCE(EXCLUDED.notlar, surumler.notlar),
            etkin        = TRUE,
            yayin_ts     = now()
        RETURNING surum_id, urun, surum, platform, kanal, paket_tur,
                  dosya_ad, dosya_boyut, sha256, imza, asgari_surum,
                  notlar, yayin_ts, etkin
        """,
        (urun, surum, platform, kanal, paket_tur, dosya_ad, boyut, sha256,
         imza, (asgari_surum or None), (notlar or None)))

    if yonetici_id:
        try:
            mk_db.calistir(
                "INSERT INTO sistem_denetim (yonetici_id, eylem, hedef_tur, hedef_id, ayrinti) "
                "VALUES (%s,%s,%s,%s,%s)",
                (yonetici_id, "surum_yayinla", "surum",
                 str(kayit["surum_id"]) if kayit else None,
                 json.dumps({"urun": urun, "surum": surum,
                             "platform": platform, "kanal": kanal,
                             "paket_tur": paket_tur, "boyut": boyut},
                            ensure_ascii=False)))
        except Exception:
            pass

    return dict(kayit) if kayit else {}


def paket_devre_disi(surum_id: int, yonetici_id: Optional[int] = None) -> bool:
    kayit = mk_db.tek(
        "UPDATE surumler SET etkin=FALSE WHERE surum_id=%s "
        "RETURNING urun, surum, platform, paket_tur", (surum_id,))
    if not kayit:
        return False
    if yonetici_id:
        try:
            mk_db.calistir(
                "INSERT INTO sistem_denetim (yonetici_id, eylem, hedef_tur, hedef_id, ayrinti) "
                "VALUES (%s,%s,%s,%s,%s)",
                (yonetici_id, "surum_devre_disi", "surum", str(surum_id),
                 json.dumps(dict(kayit), ensure_ascii=False)))
        except Exception:
            pass
    return True


def paket_etkinlestir(surum_id: int) -> bool:
    return bool(mk_db.tek(
        "UPDATE surumler SET etkin=TRUE WHERE surum_id=%s RETURNING surum_id",
        (surum_id,)))


def liste(urun: Optional[str] = None, kanal: Optional[str] = None,
          etkin_yalniz: bool = False) -> list[dict[str, Any]]:
    kosul, par = ["1=1"], []
    if urun:
        kosul.append("urun=%s")
        par.append(urun.strip().lower())
    if kanal:
        kosul.append("kanal=%s")
        par.append(kanal.strip().lower())
    if etkin_yalniz:
        kosul.append("etkin")
    satirlar = mk_db.sorgu(
        f"""
        SELECT surum_id, urun, surum, platform, kanal, paket_tur, dosya_ad,
               dosya_boyut, sha256, imza, asgari_surum, notlar, yayin_ts, etkin,
               app_surum
          FROM surumler
         WHERE {' AND '.join(kosul)}
         ORDER BY urun, yayin_ts DESC
        """, tuple(par))
    cikti = []
    for s in satirlar:
        d = dict(s)
        d["indir_yol"] = f"/indir/{d['urun']}/{d['surum']}/{d['dosya_ad']}"
        d["dosya_var"] = os.path.isfile(
            paket_yolu(d["urun"], d["surum"], d["dosya_ad"]))
        cikti.append(d)
    return cikti


def son_surum(urun: str, *, platform: str = "ortak",
              kanal: str = "kararli",
              paket_tur: str = "guncelleme") -> Optional[dict[str, Any]]:
    """Verilen urun/platform/kanal icin en yuksek etkin surumu dondurur.

    `platform='ortak'` kayitlari her platform icin gecerlidir; bu yuzden
    somut bir platform istendiginde hem o platform hem `ortak` aranir.

    OLCULEN KUSUR (2026-08-16): suzgec her durumda
    ``platform IN (istenen, 'ortak')`` idi.  Istemci platformunu
    BILDIRMEZSE `platform` varsayilani `ortak` olur ve suzgec yalnizca
    `ortak` kayitlari gorur.  Kopru paketleri 1.3.0'dan beri `windows` /
    `linux` olarak yayinlandigi icin uc, en son `ortak` kayit olan
    1.2.1'i "guncel" ilan ediyordu: platformunu bildirmeyen HER kopru
    1.2.1'de takili kaliyor, 1.5.6 guncellemesini hic gormuyordu.
    Ayni nedenle `paket_tur='kurulum'` sorgusu "depoda etkin paket yok"
    donuyordu.

    DUZELTME: `ortak` istendiginde platform kisiti UYGULANMAZ -- soru
    "hangi platform" degil "bu urunun en yeni surumu ne" demektir.
    Somut platform istendiginde eski davranis birebir korunur, cunku o
    durumda yanlis platformun ikilisini vermek gercek bir kusur olur.
    """
    genel = platform.strip().lower() in ("", "ortak")
    kosul = "" if genel else " AND platform IN (%s, 'ortak')"
    degerler: list[Any] = [urun.strip().lower(), kanal.strip().lower(),
                           paket_tur.strip().lower()]
    if not genel:
        degerler.append(platform.strip().lower())
    satirlar = mk_db.sorgu(
        """
        SELECT surum_id, urun, surum, platform, kanal, paket_tur, dosya_ad,
               dosya_boyut, sha256, imza, asgari_surum, notlar, yayin_ts
          FROM surumler
         WHERE urun=%s AND kanal=%s AND paket_tur=%s AND etkin
        """ + kosul, tuple(degerler))
    if not satirlar:
        return None
    # En yuksek surum; esitlikte platforma ozel kayit 'ortak'a tercih
    # edilir.  `ortak` sorgusunda esit surumlu birden fazla platform
    # kaydi cikabilir (or. 1.5.6 windows + linux); bu durumda dosya adi
    # ile kararlilastirilir, aksi halde ayni sorgu farkli yanit verirdi.
    def anahtar(s):
        return (surum_ayikla(s["surum"]),
                1 if s["platform"] != "ortak" else 0,
                s["dosya_ad"])
    en = max(satirlar, key=anahtar)
    d = dict(en)
    d["indir_yol"] = f"/indir/{d['urun']}/{d['surum']}/{d['dosya_ad']}"
    return d


def guncelleme_kontrol(urun: str, mevcut_surum: str, *,
                       platform: str = "ortak", kanal: str = "kararli",
                       paket_tur: str = "guncelleme",
                       taban_url: str = "") -> dict[str, Any]:
    """Istemcinin acilista cagirdigi kontrol.

    Doner: {'guncelleme_var': bool, 'surum': ..., 'sha256': ..., 'imza': ...,
            'url': ..., 'uygulanabilir': bool, 'neden': ...}
    """
    en = son_surum(urun, platform=platform, kanal=kanal, paket_tur=paket_tur)

    # TAM PAKETE DUSME: istemci varsayilan olarak artimli `guncelleme`
    # paketi sorar, ama her surum icin artimli paket uretilmez -- dagitim
    # su an tumuyle `tam` paketlerden olusuyor.
    #
    # DUSME KOSULU "hic artimli paket yok" DEGILDIR.  Depoda eski bir
    # artimli kayit dururken (or. gcs 2.4.52 `guncelleme`) yeni surumler
    # yalnizca `tam` olarak yayinlanirsa, "yok ise dus" mantigi eski
    # kaydi bulur ve uc "guncel" diyerek 2.4.65'i gizler; Merkez
    # Uygulama sahibi kurum guncellemeyi hic gormez.  Bu yuzden DAHA
    # YENI bir tam paket varsa o tercih edilir.
    #
    # Yalnizca istenen tur `guncelleme` iken denenir; cagiran acikca
    # `tam` istediyse yorumlanacak bir belirsizlik yoktur.
    dusuldu = False
    if paket_tur == "guncelleme":
        tam = son_surum(urun, platform=platform, kanal=kanal, paket_tur="tam")
        if tam and (not en or surum_kiyas(tam["surum"], en["surum"]) > 0):
            en = tam
            dusuldu = True

    if not en:
        return {"guncelleme_var": False, "neden": "depoda etkin paket yok"}

    if surum_kiyas(en["surum"], mevcut_surum) <= 0:
        return {"guncelleme_var": False, "surum": en["surum"],
                "neden": "guncel"}

    uygulanabilir, neden = True, ""
    asgari = en.get("asgari_surum")
    if asgari and surum_kiyas(mevcut_surum, asgari) < 0:
        uygulanabilir = False
        neden = (f"bu guncelleme en az {asgari} surumunden uygulanabilir; "
                 f"once ara surumu kurun veya tam paketi indirin")

    if not os.path.isfile(paket_yolu(en["urun"], en["surum"], en["dosya_ad"])):
        return {"guncelleme_var": False, "surum": en["surum"],
                "neden": "paket dosyasi depoda bulunamadi"}

    if dusuldu and not neden:
        neden = ("bu surum icin artimli guncelleme paketi yok; "
                 "tam paket kurulacak")

    return {
        "guncelleme_var": True,
        "uygulanabilir": uygulanabilir,
        "neden": neden,
        "urun": en["urun"],
        "surum": en["surum"],
        "platform": en["platform"],
        "kanal": en["kanal"],
        "paket_tur": en["paket_tur"],
        "dosya_ad": en["dosya_ad"],
        "dosya_boyut": en["dosya_boyut"],
        "sha256": en["sha256"],
        "imza": en["imza"],
        "asgari_surum": asgari,
        "notlar": en.get("notlar") or "",
        "url": (taban_url.rstrip("/") + en["indir_yol"]) if taban_url
               else en["indir_yol"],
        "acik_anahtar": acik_anahtar_b64(),
    }


def indirme_coz(urun: str, surum: str, dosya_ad: str) -> Optional[str]:
    """`/indir/...` istegini guvenli sekilde dosya yoluna cevirir."""
    for parca in (urun, surum, dosya_ad):
        if not parca or "/" in parca or "\\" in parca or ".." in parca:
            return None
    yol = paket_yolu(urun, surum, dosya_ad)
    kok = os.path.realpath(_depo_koku())
    gercek = os.path.realpath(yol)
    if not gercek.startswith(kok + os.sep):
        return None
    return gercek if os.path.isfile(gercek) else None


def indirme_say(surum_id: int, ip: str = "") -> None:
    """Indirmeyi denetim izine yazar (surumler tablosunda sayac kolonu yok)."""
    try:
        mk_db.calistir(
            "INSERT INTO sistem_denetim (eylem, hedef_tur, hedef_id, ayrinti, ip) "
            "VALUES (%s,%s,%s,%s,%s)",
            ("paket_indirme", "surum", str(surum_id),
             json.dumps({"surum_id": surum_id}, ensure_ascii=False),
             (ip or None)))
    except Exception:
        pass
