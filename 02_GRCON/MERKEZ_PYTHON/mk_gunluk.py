#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""GOKTUNGU — gunluk okuma modulu (Faz 18, Is 10).

KAYNAKLAR (olculdu, dordu de dogrulandi):

  1. `uygulama`  /var/log/goktungu-merkez.log (+ dondurulenler)
  2. `app`       /var/log/goktungu-app.log    (+ dondurulenler)
  3. `sistem`    `journalctl` (journald)  -> goktungu, systemd-journal grubunda
  4. `ag`        /var/log/fail2ban.log        (+ dondurulenler, ACL ile)

VERITABANI GUNLUGU KAPSAM DISI: `/var/lib/pgsql/16/data/log/*.log`
kipi `0600`, sahibi `postgres`. Okumak icin ya dizin ACL'i ya da
`log_file_mode` degisikligi + PG yeniden baslatma gerekir. Bu bir
goruntuleme isi oldugu icin canli veritabanini kesintiye ugratmak
tercih edilmedi. Arayuz bu sinirlamayi ACIKCA bildirir.

ZAMAN DAMGASI ASIMETRISI (olculdu — kritik):

  merkez.log.1   12074 satir, tarih damgali     4  (%0)
  app.log.1       7687 satir, tarih damgali     0  (%0)

Uygulama `print()` ile yaziyor, damga eklemiyor; birim
`StandardOutput=append:` kullandigi icin journald da damga
eklemiyor. Bu yuzden UYGULAMA gunluklerinde ZAMAN ARALIGI
SUZMESI YAPILAMAZ. `zaman_suzulebilir` alani her kaynak icin
bunu bildirir; arayuz zaman suzgecini yalniz destekleyen
kaynaklarda gosterir.

Damgasiz satir ATILMAZ (Is 9 dersi): zamani bilinmeyen satir
"tarih bilinmiyor" olarak islenir ve listede kalir.

YENIDEN KULLANIM: dosya okuma parcalari `mk_guvenlik`ten ICE
ALINIR, KOPYALANMAZ. Kopyalama iki kopyanin ayrisma riskini
dogurur (Is 6'da AiVekili kusuru boyle olustu: mantik iki yerde
durunca biri geride kaldi).

MALIYET: `journalctl -n 200 -o json` olculdu -> 75 ms. Onbellek
GEREKMIYOR; ek karmasiklik eklenmedi.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time as _zaman

# Dosya okuma parcalari — KOPYALANMAZ, ice alinir.
try:
    from mk_guvenlik import (_gun_al, _kuyruk_zincir_oku, _zincir_yollar,
                             _SATIR_SINIR)
    _GUV_VAR = True
except BaseException:
    _GUV_VAR = False
    _SATIR_SINIR = 20000

    def _zincir_yollar(yol):
        return [yol] if os.path.exists(yol) else []

    def _kuyruk_zincir_oku(yol, en_cok_bayt=4 * 1024 * 1024):
        try:
            with open(yol, encoding="utf-8", errors="replace") as f:
                return f.read().splitlines()[-_SATIR_SINIR:]
        except BaseException:
            return []

    def _gun_al(satir):
        return None, None


MERKEZ_GUNLUK = "/var/log/goktungu-merkez.log"
APP_GUNLUK = "/var/log/goktungu-app.log"
AG_GUNLUK = "/var/log/fail2ban.log"
PG_GUNLUK_DIZIN = "/var/lib/pgsql/16/data/log"

# Panelin bir istekte donebilecegi en cok satir.
_EN_COK = 500
_VARSAYILAN = 200

# --- duzey cikarimi (SEZGISEL — arayuz boyle bildirir) ----------------
_D_HATA = re.compile(
    r"(?i)(\bhata\b|\bkusur\b|traceback|exception|\berror\b|\bfail(ed)?\b"
    r"|critical|\bcrash)")
_D_UYARI = re.compile(r"(?i)(\buyari\b|\buyarı\b|\bwarn(ing)?\b|\bdikkat\b)")
_D_GUVENLIK = re.compile(r"(GOKTUNGU-KK-BLOK|fail2ban|\bBan\b|\bUnban\b)")

DUZEYLER = ("hata", "uyari", "guvenlik", "bilgi")

# --- hassas veri maskeleme -------------------------------------------
# Tarama SIMDI temiz cikti (jeton/e-posta bulunmadi); bu onlem
# GELECEGE karsi. Bir jeton gunluge duserse panel onu ekranda
# gostermez.
_MASKE = [
    (re.compile(r"(?i)(authorization\s*:\s*bearer\s+)(\S{6,})"), r"\1***"),
    (re.compile(r"(?i)\b(jeton|token|api[_-]?key|secret|apikey)"
                r"(\s*[=:]\s*)(\S{6,})"), r"\1\2***"),
    # `pwd` anahtari KASITLI OLARAK YOK: sudo kayitlarindaki
    # `PWD=/root` (calisma dizini) yakalanip maskeleniyordu ve
    # yoneticinin komutun hangi dizinde kosuldugunu gormesi
    # engelleniyordu. Olculdu: `root : PWD=*** ; USER=goktungu`.
    # Bu, "alt dizgi aramasi sinir gormez" tuzaginin maskeleme
    # katmanindaki bicimi.
    (re.compile(r"(?i)\b(sifre|şifre|password|passwd)"
                r"(\s*[=:]\s*)(\S{3,})"), r"\1\2***"),
]


def _maskele(s: str) -> str:
    """Jeton/anahtar desenlerini `***` ile degistirir.

    sshd basarisiz giris satirlari MASKELENMEZ: `invalid user admin`
    gibi kayitlar bir guvenlik verisidir ve yonetici gormeli.
    Yalniz gizli anahtar/jeton/sifre DEGERLERI maskelenir.
    """
    try:
        for d, y in _MASKE:
            s = d.sub(y, s)
    except BaseException:
        pass
    return s


def _duzey(s: str) -> str:
    try:
        if _D_GUVENLIK.search(s):
            return "guvenlik"
        if _D_HATA.search(s):
            return "hata"
        if _D_UYARI.search(s):
            return "uyari"
    except BaseException:
        pass
    return "bilgi"


# --- dosya tabanli kaynaklar -----------------------------------------
def _dosya_kaynak(yol: str, en_cok: int, ara: str = "",
                  duzey: str = "") -> dict:
    """Dosya tabanli gunluk: satir sirasi kronolojiktir.

    ZAMAN SUZGECI YOK: bu dosyalarda satirlarin %0'i tarih damgasi
    tasiyor (olculdu). Zaman araligi sunmak yanlis sonuc uretirdi.
    """
    satirlar = _kuyruk_zincir_oku(yol)
    okunabilir = bool(satirlar) or os.path.exists(yol)
    kayitlar = []
    damgali = 0
    # En yeniden geriye: kullanici son olaylari gormek ister.
    for i in range(len(satirlar) - 1, -1, -1):
        ham = satirlar[i]
        if not ham.strip():
            continue
        d = _duzey(ham)
        if duzey and d != duzey:
            continue
        if ara and ara.lower() not in ham.lower():
            continue
        gun, ts = _gun_al(ham)
        if ts:
            damgali += 1
        kayitlar.append({
            "ts": ts, "gun": gun, "duzey": d,
            "metin": _maskele(ham)[:2000],
            "birim": "", "pid": None,
        })
        if len(kayitlar) >= en_cok:
            break
    return {
        "kayitlar": kayitlar,
        "okunabilir": okunabilir,
        "kaynak": yol,
        "dosya_sayisi": len(_zincir_yollar(yol)),
        "taranan_satir": len(satirlar),
        "damgali": damgali,
        "zaman_suzulebilir": False,
        "not": ("Bu gunlukte satirlar tarih damgasi tasimiyor; "
                "zaman suzgeci uygulanamaz. Sira kronolojiktir "
                "(en yeni ustte)."),
    }


# --- journald ---------------------------------------------------------
def _journald(en_cok: int, ara: str = "", duzey: str = "",
              birim: str = "", saat: int = 0) -> dict:
    """`journalctl -o json` cikti okur.

    ZAMAN SUZGECI CALISIR: journald damgayi kendisi tutuyor.
    `saat` verilirse `--since` ile SUREC TARAFINDA suzulur; bu,
    tum ciktiyi okuyup Python'da atmaktan hizlidir.
    """
    komut = ["journalctl", "-o", "json", "--no-pager",
             "-n", str(max(1, min(en_cok * 4, 4000)))]
    if birim:
        # Birim adi disardan geliyor: yalniz guvenli karakterler.
        if re.fullmatch(r"[A-Za-z0-9@._-]{1,64}", birim):
            komut += ["-u", birim]
    if duzey == "hata":
        komut += ["-p", "3"]
    elif duzey == "uyari":
        komut += ["-p", "4"]
    if saat and saat > 0:
        komut += ["--since", "-%dh" % int(saat)]
    try:
        p = subprocess.run(komut, capture_output=True, text=True,
                           timeout=20)
        ham = p.stdout or ""
        hata = (p.stderr or "").strip()
    except BaseException as e:
        return {"kayitlar": [], "okunabilir": False, "kaynak": "journald",
                "hata": repr(e), "zaman_suzulebilir": True,
                "birimler": [], "taranan_satir": 0, "damgali": 0}

    kayitlar = []
    birimler = {}
    satirlar = ham.splitlines()
    for s in reversed(satirlar):
        if not s.strip():
            continue
        try:
            d = json.loads(s)
        except BaseException:
            continue
        m = d.get("MESSAGE")
        # MESSAGE ikili icerikte BAYT DIZISI olarak gelir.
        if isinstance(m, list):
            try:
                m = bytes(m).decode("utf-8", "replace")
            except BaseException:
                m = ""
        m = (m or "").strip()
        if not m:
            continue
        u = (d.get("_SYSTEMD_UNIT") or d.get("SYSLOG_IDENTIFIER") or "")
        birimler[u] = birimler.get(u, 0) + 1
        # journald oncelikleri: 0-3 hata, 4 uyari, digerleri bilgi.
        try:
            p_ = int(d.get("PRIORITY", 6))
        except BaseException:
            p_ = 6
        if _D_GUVENLIK.search(m):
            dz = "guvenlik"
        elif p_ <= 3:
            dz = "hata"
        elif p_ == 4:
            dz = "uyari"
        else:
            dz = "bilgi"
        if duzey and dz != duzey:
            continue
        if ara and ara.lower() not in m.lower():
            continue
        try:
            ts = int(d.get("__REALTIME_TIMESTAMP", 0)) / 1e6
        except BaseException:
            ts = None
        kayitlar.append({
            "ts": ts or None,
            "gun": (_zaman.strftime("%Y-%m-%d", _zaman.localtime(ts))
                    if ts else None),
            "duzey": dz, "metin": _maskele(m)[:2000],
            "birim": u, "pid": d.get("_PID"),
        })
        if len(kayitlar) >= en_cok:
            break

    return {
        "kayitlar": kayitlar,
        "okunabilir": bool(satirlar) or not hata,
        "kaynak": "journald",
        "hata": hata[:200] if hata and not satirlar else "",
        "taranan_satir": len(satirlar),
        "damgali": sum(1 for k in kayitlar if k["ts"]),
        "zaman_suzulebilir": True,
        "birimler": sorted(
            [{"birim": k, "sayi": v} for k, v in birimler.items()],
            key=lambda x: -x["sayi"])[:25],
        "not": ("Isletim sistemi gunlugu journald tarafindan tutulur; "
                "zaman damgasi ve oncelik alanlari guvenilirdir."),
    }


# --- veritabani gunlugu (kapsam disi, ama SESSIZ degil) --------------
def _pg_durum() -> dict:
    """PostgreSQL gunlugunun neden gosterilmedigini bildirir.

    Sessizce eksik BIRAKILMAZ: yonetici veritabani gunlugunun
    olmadigini degil, KAPSAM DISI oldugunu gormeli.
    """
    # `os.path.isdir()` IZIN YOKSA DA False doner. Ust dizin
    # `/var/lib/pgsql` kipi 0700 oldugu icin `goktungu` kullanicisi
    # dizini goremez ve `isdir` False dondurur — dizin VAR (root ile
    # olculdu: 6 dosya). "Yok" demek YANLIS OLUMSUZ bildirim olurdu.
    # Bu yuzden ucu durum ayrimi yapiliyor: gorunur / gorunmez /
    # gercekten yok. Gorunmezlik BELIRSIZLIK olarak bildirilir.
    gorunur = os.path.isdir(PG_GUNLUK_DIZIN)
    ust = os.path.dirname(os.path.dirname(os.path.dirname(
        PG_GUNLUK_DIZIN)))  # /var/lib/pgsql
    ust_gorunur = os.access(ust, os.R_OK | os.X_OK)
    okunabilir = False
    ornek = ""
    if gorunur:
        try:
            a = sorted(os.listdir(PG_GUNLUK_DIZIN))
            ornek = a[-1] if a else ""
            if ornek:
                with open(os.path.join(PG_GUNLUK_DIZIN, ornek), "rb") as f:
                    f.read(1)
                okunabilir = True
        except BaseException:
            okunabilir = False
    if gorunur:
        durum = "okunabilir" if okunabilir else "izin_yok"
    elif not ust_gorunur:
        durum = "dogrulanamiyor"
    else:
        durum = "yok"
    return {
        "dizin": PG_GUNLUK_DIZIN,
        "durum": durum,
        "ust_gorunur": ust_gorunur,
        "okunabilir": okunabilir,
        "ornek": ornek,
        "kapsam_disi": True,
        "gerekce": ("PostgreSQL gunluk dosyalarinin kipi 0600 ve sahibi "
                    "postgres kullanicisidir. Okumak icin dizin ACL'i "
                    "veya log_file_mode degisikligi ve veritabani "
                    "yeniden baslatmasi gerekir; canli veritabanini "
                    "kesintiye ugratmamak icin bu surumde kapsam "
                    "disinda birakildi."),
        "durum_aciklama": {
            "okunabilir": "Dizin okunabilir durumda.",
            "izin_yok": "Dizin gorunuyor ancak dosyalar okunamiyor.",
            "dogrulanamiyor": ("Ust dizin (/var/lib/pgsql) merkez "
                               "servis kullanicisina kapali oldugu icin "
                               "gunluk dizininin varligi bu katmandan "
                               "dogrulanamiyor. Bu bir kusur degildir: "
                               "veritabani gunlugu zaten kapsam "
                               "disindadir."),
            "yok": "Gunluk dizini bulunamadi.",
        }.get(durum, ""),
    }


# --- dis arayuz -------------------------------------------------------
KAYNAKLAR = ("uygulama", "app", "sistem", "ag")


def kaynaklar() -> dict:
    """Kaynak listesi ve her birinin yetenekleri."""
    return {
        "kaynaklar": [
            {"kod": "uygulama", "ad": "Merkez sunucu",
             "zaman_suzulebilir": False,
             "dosya_sayisi": len(_zincir_yollar(MERKEZ_GUNLUK))},
            {"kod": "app", "ad": "Yer kontrol istasyonu",
             "zaman_suzulebilir": False,
             "dosya_sayisi": len(_zincir_yollar(APP_GUNLUK))},
            {"kod": "sistem", "ad": "Isletim sistemi (journald)",
             "zaman_suzulebilir": True, "dosya_sayisi": None},
            {"kod": "ag", "ad": "Ag katmani (fail2ban)",
             "zaman_suzulebilir": False,
             "dosya_sayisi": len(_zincir_yollar(AG_GUNLUK))},
        ],
        "duzeyler": list(DUZEYLER),
        "veritabani": _pg_durum(),
        "en_cok": _EN_COK,
        "guvenlik_notu": ("Jeton, anahtar ve sifre degerleri ekranda "
                          "maskelenir. Basarisiz giris kayitlarindaki "
                          "kullanici adlari maskelenmez: bunlar "
                          "guvenlik incelemesi icin gereklidir."),
        "uretim_ts": _zaman.time(),
    }


def oku(kaynak: str = "uygulama", en_cok: int = _VARSAYILAN,
        ara: str = "", duzey: str = "", birim: str = "",
        saat: int = 0) -> dict:
    """Istenen kaynaktan gunluk kayitlarini doner (en yeni once)."""
    try:
        en_cok = max(1, min(int(en_cok or _VARSAYILAN), _EN_COK))
    except BaseException:
        en_cok = _VARSAYILAN
    ara = (ara or "")[:120]
    duzey = duzey if duzey in DUZEYLER else ""
    try:
        saat = max(0, min(int(saat or 0), 24 * 30))
    except BaseException:
        saat = 0

    if kaynak == "sistem":
        s = _journald(en_cok, ara, duzey, birim, saat)
    elif kaynak == "app":
        s = _dosya_kaynak(APP_GUNLUK, en_cok, ara, duzey)
    elif kaynak == "ag":
        s = _dosya_kaynak(AG_GUNLUK, en_cok, ara, duzey)
    else:
        kaynak = "uygulama"
        s = _dosya_kaynak(MERKEZ_GUNLUK, en_cok, ara, duzey)

    s["kaynak_kod"] = kaynak
    s["istek"] = {"en_cok": en_cok, "ara": ara, "duzey": duzey,
                  "birim": birim, "saat": saat}

    # KAPSAM DEGISIMI (olculdu — arayuz bunu yazar):
    # `sistem` kaynaginda duzey suzgeci `journalctl -p` ile SUREC
    # TARAFINDA uygulanir. Bu yuzden "son N kayit icindeki hatalar"
    # degil, "sistemdeki son N HATA kaydi" doner. Suzgecsiz cagride
    # dagilim `hata 0` gosterirken `duzey=hata` istegi 50 kayit
    # dondurebilir; ikisi FARKLI kume okur ve ikisi de dogrudur.
    # Yonetici hata ararken bu ISTENEN davranistir, ancak celiskili
    # gorunmemesi icin acikca bildirilir.
    s["kapsam_degisti"] = bool(
        kaynak == "sistem" and (duzey in ("hata", "uyari") or saat))
    if s["kapsam_degisti"]:
        s["kapsam_notu"] = (
            "Duzey ve zaman suzgeci sistem gunlugunde kaynak "
            "tarafinda uygulanir: son kayitlar arasindan secim degil, "
            "dogrudan bu olcute uyan en yeni kayitlar getirilir.")
    # Duzey dagilimi: suzgec uygulanmisken dagilim yaniltici olur.
    if not duzey:
        d = {}
        for k in s.get("kayitlar", []):
            d[k["duzey"]] = d.get(k["duzey"], 0) + 1
        s["duzey_dagilim"] = [{"duzey": a, "sayi": d.get(a, 0)}
                              for a in DUZEYLER]
        # Dagilim DONEN kayitlar uzerinden hesaplanir, tum gunluk
        # uzerinden DEGIL. Arayuz bunu "son N kayit icinde" diye
        # yazar; aksi halde rozetler tum sistemin ozeti sanilir.
        s["dagilim_kapsam"] = len(s.get("kayitlar", []))
    else:
        s["duzey_dagilim"] = None
        s["dagilim_kapsam"] = None
    s["uretim_ts"] = _zaman.time()
    s["guvenlik_moduluyle"] = _GUV_VAR
    return s


if __name__ == "__main__":
    import sys
    k = sys.argv[1] if len(sys.argv) > 1 else "uygulama"
    r = oku(k, 5)
    print("kaynak:", r["kaynak_kod"], "| okunabilir:", r["okunabilir"])
    print("taranan:", r.get("taranan_satir"), "| donen:",
          len(r["kayitlar"]), "| zaman suzulebilir:",
          r["zaman_suzulebilir"])
    for x in r["kayitlar"][:5]:
        print("  [%s] %s" % (x["duzey"], x["metin"][:90]))
