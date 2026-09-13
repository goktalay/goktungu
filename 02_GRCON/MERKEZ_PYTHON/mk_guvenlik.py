# -*- coding: utf-8 -*-
"""FAZ18-IS9-GUVENLIK-IZLEME — guvenlik gorunurlugu modulu.

Yonetim panelinin "Guvenlik / Saldiri Izleme" bolumunu besler. UC
kaynagi birlestirir:

  1. `mk_kaba_kuvvet` bellek durumu  -> ETKIN bloklar, canli sayaclar
  2. `/var/log/goktungu-merkez.log`  -> KALICI blok gecmisi (gunluk ozet)
  3. `/var/log/fail2ban.log`         -> AG katmani yasaklari (SSH + HTTP)

NEDEN YENI TABLO YOK:
  Veri zaten iki yerde kalici. Ucuncu bir kopya (`guvenlik_olaylari`
  tablosu) her giris denemesinde veritabani yazimi demek olurdu —
  saldiri aninda veritabanini tam yuk altinda birakir. Sema gocu
  riski de getirir. Gunluk dosyasi + bellek yeterli olculdu.

KAYNAK 1 — BELLEK (mk_kaba_kuvvet):
  `durum()`      -> {ip_blok, hesap_blok, izlenen_ip, izlenen_hesap, esik}
  `son_olaylar()`-> son 500 olay (basarisiz denemeler DAHIL)
  Servis yeniden baslayinca SILINIR. Bu yuzden "gunluk ozet" bu
  kaynaktan uretilemez.

KAYNAK 2 — MERKEZ GUNLUGU:
  `mk_kaba_kuvvet._olay_ekle` yalniz BLOK turlerini basar:
    2026-08-18 22:49:09 GOKTUNGU-KK-BLOK ip=1.2.3.4 uc=/api/firma/giris tur=ip_blok_kisa n=10
  Kodun kendi gerekcesi: her basarisiz deneme basilsa gunluk
  saldirinin kendisiyle sisirdi (20 bin satir/48 saat olculdu).
  Bu gerekce saglam, DEGISTIRILMEDI.

  TARIHSIZ SATIR TUZAGI: `KK_GUNLUK_TARIH_v1` yamasindan ONCE yazilan
  satirlarda tarih damgasi YOK (canlida uc adet olculdu). Bu satirlar
  ATILMAZ — "tarih bilinmiyor" olarak isaretlenip toplama dahil edilir.
  Atilsa gecmis veri sessizce kaybolurdu.

KAYNAK 3 — FAIL2BAN:
  `2026-08-18 22:49:13,083 fail2ban.actions [869745]: NOTICE  [goktungu-http] Ban 198.51.100.222`
  Soket (`/var/run/fail2ban/fail2ban.sock`) `srwx------ root root` —
  merkez `goktungu` olarak kostugu icin OKUNAMAZ (olculdu). Bu yuzden
  CLI/soket yerine gunluk dosyasi okunur; dosyada `goktungu` icin ACL
  var (`user:goktungu:r--`, olculdu).

  Ban/Unban eslestirmesi: bir adres icin son olay `Ban` ise ETKIN,
  `Unban` ise cozulmus sayilir.

OKUMA MALIYETI:
  Gunluk dosyalari sinirsiz buyuyor (logrotate yoktu — bu yamada
  kuruldu). Yine de dosya bastan okunmaz: `_kuyruk_oku` sondan
  bloklar halinde geri okur ve yalniz gereken satir sayisini alir.
"""
from __future__ import annotations

import gzip
import io
import os
import re
import time as _zaman
from collections import OrderedDict

MERKEZ_GUNLUK = "/var/log/goktungu-merkez.log"
APP_GUNLUK = "/var/log/goktungu-app.log"
FAIL2BAN_GUNLUK = "/var/log/fail2ban.log"

# Okuma ust siniri: cok buyuk dosyada tum satirlari belleğe almayiz.
_OKUMA_BAYT = 4 * 1024 * 1024      # sondan en cok 4 MB
_SATIR_SINIR = 20000

_KK_DESEN = re.compile(
    r"GOKTUNGU-KK-BLOK\s+ip=(\S+)\s+uc=(\S+)\s+tur=(\S+)(?:\s+n=(\d+))?")
_TARIH_ONEK = re.compile(r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})")
_F2B_DESEN = re.compile(
    r"^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})[,.]?\d*\s+"
    r"fail2ban\.actions\s+\[\d+\]:\s+\w+\s+\[([^\]]+)\]\s+"
    r"(Ban|Unban)\s+(\S+)")


def _kuyruk_oku(yol: str, en_cok_bayt: int = _OKUMA_BAYT) -> list[str]:
    """Dosyanin SONUNDAN en cok `en_cok_bayt` okur, satir listesi doner.

    Dosya bastan okunmaz: gunluk dosyalari sinirsiz buyuyebilir ve
    panel her istekte tum dosyayi tarasa yanit suresi dosya boyutuyla
    dogru oranli buyurdu.
    """
    try:
        boyut = os.path.getsize(yol)
    except BaseException:
        return []
    try:
        with io.open(yol, "rb") as f:
            if boyut > en_cok_bayt:
                f.seek(boyut - en_cok_bayt)
                f.readline()  # yarim satiri at
            ham = f.read()
    except BaseException:
        # Izin yok / dosya silinmis: panel KIRILMAZ, bos doner.
        return []
    try:
        metin = ham.decode("utf-8", "replace")
    except BaseException:
        return []
    satirlar = metin.splitlines()
    if len(satirlar) > _SATIR_SINIR:
        satirlar = satirlar[-_SATIR_SINIR:]
    return satirlar


def _zincir_yollar(yol: str) -> list:
    """Canli dosya + dondurulmus kardesleri, EN YENIDEN eskiye.

    logrotate `delaycompress` kullaniyor: `.1` duz metin, `.2+` gzip.
    IKI bicim de dondurulur; yalniz birini desteklemek ilk gunden
    sonra sessiz veri kaybi olurdu.
    """
    a = []
    if os.path.exists(yol):
        a.append(yol)
    for i in range(1, 16):
        for k in ("%s.%d" % (yol, i), "%s.%d.gz" % (yol, i)):
            if os.path.exists(k):
                a.append(k)
    return a


def _tek_oku(yol: str, en_cok_bayt: int) -> list:
    """Tek dosyayi sondan okur. `.gz` ise tamami acilir.

    Sikistirilmis dosyada rasgele erisim yok: `seek` ile sondan
    okumak gzip akisini bozar. Bu yuzden gzip dosyasi bastan acilir
    ama YALNIZ satir siniri kadari tutulur.
    """
    if yol.endswith(".gz"):
        try:
            with gzip.open(yol, "rt", encoding="utf-8", errors="replace") as f:
                s = f.read().splitlines()
        except BaseException:
            return []
        return s[-_SATIR_SINIR:] if len(s) > _SATIR_SINIR else s
    return _kuyruk_oku(yol, en_cok_bayt)


def _kuyruk_zincir_oku(yol: str, en_cok_bayt: int = _OKUMA_BAYT) -> list:
    """Gunluk zincirini okur; sonuc KRONOLOJIK (en eski once).

    Zincir en yeniden eskiye taranir ve toplam satir sinirina
    ulasilinca DURULUR: 14 gunluk arsiv diskte dursa da panel
    yaniti dosya boyutuyla dogru oranli buyumez.
    """
    parcalar = []
    toplam = 0
    for k in _zincir_yollar(yol):
        s = _tek_oku(k, en_cok_bayt)
        if not s:
            continue
        parcalar.append(s)
        toplam += len(s)
        if toplam >= _SATIR_SINIR:
            break
    # `parcalar` yeniden eskiye; kronolojik sira icin ters cevrilir.
    cikti = []
    for s in reversed(parcalar):
        cikti.extend(s)
    return cikti[-_SATIR_SINIR:] if len(cikti) > _SATIR_SINIR else cikti


def _gun_al(satir: str):
    """Satirin tarih damgasini (varsa) `(gun, ts)` olarak doner.

    TARIHSIZ SATIR TUZAGI: eski kayitlarda damga yok. `(None, None)`
    doner ve cagiran taraf bunu "tarih bilinmiyor" olarak isler —
    satiri ATMAZ.
    """
    m = _TARIH_ONEK.match(satir)
    if not m:
        return None, None
    gun = m.group(1)
    try:
        ts = _zaman.mktime(_zaman.strptime(
            gun + " " + m.group(2), "%Y-%m-%d %H:%M:%S"))
    except BaseException:
        ts = None
    return gun, ts


def blok_gecmisi(gun_sayisi: int = 7) -> dict:
    """Merkez gunlugunden kalici blok gecmisini ozetler.

    Doner:
      {
        "gunler":   [{"gun": "2026-08-18", "sayi": 4}, ...]  (eskiden yeniye)
        "ip_grup":  [{"ip": "1.2.3.4", "sayi": 3, "son_ts": ..., "turler": {...}, "uclar": [...]}]
        "tur_grup": {"hesap_kilit": 2, "ip_blok_kisa": 3}
        "toplam":   7,
        "tarihsiz": 3,        # damgasiz eski kayitlar
        "kaynak":   "/var/log/goktungu-merkez.log",
        "okunabilir": True
      }
    """
    # FAZ18-IS9-DONDURULEN — dondurulen dosyalar da okunur; rotasyondan
    # sonra kalici gecmis kaybolmaz.
    satirlar = _kuyruk_zincir_oku(MERKEZ_GUNLUK)
    okunabilir = bool(satirlar) or os.path.exists(MERKEZ_GUNLUK)

    simdi = _zaman.time()
    en_eski = simdi - (max(1, int(gun_sayisi)) * 86400)

    gun_sayaci = OrderedDict()
    ip_bilgi = {}
    tur_sayaci = {}
    toplam = 0
    tarihsiz = 0

    for s in satirlar:
        if "GOKTUNGU-KK-BLOK" not in s:
            continue
        m = _KK_DESEN.search(s)
        if not m:
            continue
        ip, uc, tur, n = m.group(1), m.group(2), m.group(3), m.group(4)
        gun, ts = _gun_al(s)

        if gun is None:
            # Damgasiz eski kayit: ozete DAHIL edilir ama gun
            # dagilimina konulamaz.
            tarihsiz += 1
        elif ts is not None and ts < en_eski:
            # Pencere disi: sayilmaz.
            continue

        toplam += 1
        tur_sayaci[tur] = tur_sayaci.get(tur, 0) + 1
        if gun:
            gun_sayaci[gun] = gun_sayaci.get(gun, 0) + 1

        b = ip_bilgi.setdefault(ip, {"ip": ip, "sayi": 0, "son_ts": None,
                                     "turler": {}, "uclar": []})
        b["sayi"] += 1
        b["turler"][tur] = b["turler"].get(tur, 0) + 1
        if uc and uc not in b["uclar"]:
            b["uclar"].append(uc)
        if ts and (b["son_ts"] is None or ts > b["son_ts"]):
            b["son_ts"] = ts

    gunler = [{"gun": g, "sayi": c} for g, c in sorted(gun_sayaci.items())]
    ip_grup = sorted(ip_bilgi.values(),
                     key=lambda x: (-x["sayi"], x["ip"]))

    return {"gunler": gunler, "ip_grup": ip_grup, "tur_grup": tur_sayaci,
            "toplam": toplam, "tarihsiz": tarihsiz,
            "kaynak": MERKEZ_GUNLUK, "okunabilir": okunabilir}


def fail2ban_durum() -> dict:
    """fail2ban gunlugunden ag katmani yasaklarini cikarir.

    Soket root'a kapali oldugu icin CLI KULLANILMAZ (olculdu:
    `srwx------ root root`). Gunluk dosyasinda `goktungu` icin ACL var.

    Bir adres icin SON olay `Ban` ise etkin, `Unban` ise cozulmus.
    """
    # FAZ18-IS9-DONDURULEN — fail2ban gunlugu de dondurulur (logrotate
    # yapilandirmasi sistemle geliyor); zincir okunur.
    satirlar = _kuyruk_zincir_oku(FAIL2BAN_GUNLUK)
    var_mi = os.path.exists(FAIL2BAN_GUNLUK)
    okunabilir = bool(satirlar)

    son = OrderedDict()   # ip -> kayit
    hapis_sayac = {}
    toplam_ban = 0

    for s in satirlar:
        m = _F2B_DESEN.match(s)
        if not m:
            continue
        gun, saat, hapis, eylem, ip = m.groups()
        try:
            ts = _zaman.mktime(_zaman.strptime(
                gun + " " + saat, "%Y-%m-%d %H:%M:%S"))
        except BaseException:
            ts = None
        if eylem == "Ban":
            toplam_ban += 1
            hapis_sayac[hapis] = hapis_sayac.get(hapis, 0) + 1
        son[ip] = {"ip": ip, "hapis": hapis, "eylem": eylem, "ts": ts,
                   "gun": gun}

    etkin = [k for k in son.values() if k["eylem"] == "Ban"]
    etkin.sort(key=lambda x: -(x["ts"] or 0))
    gecmis = [k for k in son.values() if k["eylem"] != "Ban"]
    gecmis.sort(key=lambda x: -(x["ts"] or 0))

    return {"etkin": etkin, "cozulmus": gecmis[:50],
            "hapis_sayac": hapis_sayac, "toplam_ban": toplam_ban,
            "kaynak": FAIL2BAN_GUNLUK, "var_mi": var_mi,
            "okunabilir": okunabilir}


def ozet(gun_sayisi: int = 7) -> dict:
    """Yonetim panelinin ust kart izgarasini besleyen birlesik ozet."""
    try:
        import mk_kaba_kuvvet as kk
        canli = kk.durum()
        olaylar = kk.son_olaylar(200)
        kk_var = True
    except BaseException as e:
        canli = {"ip_blok": [], "hesap_blok": [], "izlenen_ip": 0,
                 "izlenen_hesap": 0, "esik": {}}
        olaylar = []
        kk_var = False
        canli["hata"] = str(e)

    gecmis = blok_gecmisi(gun_sayisi)
    f2b = fail2ban_durum()

    # Bugunun blok sayisi: gunluk gruplarindan alinir (kalici kaynak).
    bugun = _zaman.strftime("%Y-%m-%d")
    bugun_blok = 0
    for g in gecmis["gunler"]:
        if g["gun"] == bugun:
            bugun_blok = g["sayi"]
            break

    # Son 24 saatteki basarisiz deneme: BELLEK kaynagi (kalici degil).
    # Servis yeniden baslamissa bu sayi dusuk gorunur; arayuz bunu
    # `bellek_kalici = False` alaniyla bildirir.
    esik_ts = _zaman.time() - 86400
    basarisiz_24 = sum(1 for o in olaylar
                       if o.get("tur") == "basarisiz"
                       and (o.get("ts") or 0) >= esik_ts)

    return {
        "canli": canli,
        "kk_var": kk_var,
        "bellek_kalici": False,
        "etkin_ip_blok": len(canli.get("ip_blok") or []),
        "etkin_hesap_blok": len(canli.get("hesap_blok") or []),
        "izlenen_ip": canli.get("izlenen_ip", 0),
        "izlenen_hesap": canli.get("izlenen_hesap", 0),
        "basarisiz_24s": basarisiz_24,
        "bugun_blok": bugun_blok,
        "gecmis": gecmis,
        "fail2ban": f2b,
        "ag_etkin_yasak": len(f2b.get("etkin") or []),
        "gun_sayisi": int(gun_sayisi),
        "uretim_ts": _zaman.time(),
    }


def olaylar(sinir: int = 200, tur: str = "", ip: str = "") -> dict:
    """Bellekteki canli olay akisi (suzulebilir).

    UYARI: bu kaynak KALICI DEGIL. Servis yeniden baslayinca bosalir.
    Arayuz `kalici: False` alanini gorup kullaniciyi bilgilendirir.
    """
    try:
        import mk_kaba_kuvvet as kk
        ham = kk.son_olaylar(max(1, min(int(sinir or 200), 500)))
    except BaseException as e:
        return {"olaylar": [], "kalici": False, "hata": str(e)}

    t = (tur or "").strip()
    i = (ip or "").strip()
    suz = []
    for o in ham:
        if t and o.get("tur") != t:
            continue
        if i and o.get("ip") != i:
            continue
        suz.append(o)
    return {"olaylar": suz, "kalici": False, "toplam": len(suz),
            "sinir": int(sinir or 200)}


def blok_coz(ip: str = "", hesap: str = "") -> dict:
    """Yoneticinin bir bloku elle cozmesini saglar.

    `mk_kaba_kuvvet` tek tek cozme islevi SUNMUYOR (olculdu: yalniz
    `sifirla_hepsi()` var ve o SINAV icindir). Bu yuzden cozme,
    modulun ic sozlukleri uzerinde DEGIL, `basarili()` cagrisi ile
    yapilir — `basarili` sayaclari sifirlar ve modulun kendi sozlesmesi
    icindedir. Boylece ic yapiya bagimlilik olusmaz.
    """
    ip = (ip or "").strip()
    hesap = (hesap or "").strip()
    if not ip and not hesap:
        return {"tamam": False, "hata": "ip veya hesap gerekli"}
    try:
        import mk_kaba_kuvvet as kk
    except BaseException as e:
        return {"tamam": False, "hata": "modul yok: %s" % e}

    # `basarili(ip, uc, hesap)` uc bazli sayaclari sifirlar. Uc
    # bilinmedigi icin KORUNAN_UCLAR kumesinin tamami dolasilir.
    uclar = list(getattr(kk, "KORUNAN_UCLAR", ()) or ())
    sayi = 0
    for uc in uclar:
        try:
            kk.basarili(ip or "0.0.0.0", uc, hesap)
            sayi += 1
        except BaseException:
            pass
    return {"tamam": True, "ip": ip, "hesap": hesap, "uc_sayisi": sayi}
