# -*- coding: utf-8 -*-
"""GOKTUNGU — Harita tile onbellegi (offline harita destegi).

Tek merkezde: tile indirme, disk onbellegi, boyut/temizlik ve
bolge toplu indirme (on-yukleme). HTTP handler ve WS komutlari
bu modulu kullanir.
"""
import math
import os
import shutil
import threading
import urllib.request

from .sabitler import HARITA_CACHE, TILE_KAYNAKLARI

_UA = "GoktunguGCS/2.1 (+offline-cache)"
_kilit = threading.Lock()
# Toplu indirme durumu (tek is; UI tek indirme baslatir)
indirme_durumu = {"aktif": False, "toplam": 0, "inen": 0,
                  "hata": 0, "iptal": False}

# ---------------------------------------------------------------
# v2.4.33: CALISAN ONBELLEK TOPLAMI (durum cubugu gostergesi icin)
# ---------------------------------------------------------------
# Kullanici istegi: "Durum cubuguna harita cache'inin boyutunu yaz,
# harita degistikce yuklendikce son boyutu yaz."
#
# NEDEN AYRI SAYAC?
# `cache_bilgi()` her cagrisinda TUM onbellek agacini `os.walk` ile
# tarar ve her dosya icin `os.stat` cagirir. Kullanicinin onbellegi
# GB seviyesine ve on binlerce karoya cikabilir; bu tarama saniyeler
# surer. Cagri WS isleyicisinin ICINDE senkron calistigi icin olay
# dongusunu bloklar ve TELEMETRI AKISI DONAR. Kullanici bu yazilimla
# gercek dron uctugu icin bu kabul edilemez.
#
# Cozum: toplam bir kez (arka planda) olculur, sonra her yeni karo
# diske yazildiginda YALNIZCA o karonun bayti eklenir -> O(1).
_toplam = {"boyut": 0, "adet": 0, "hazir": False}
# Ozet degisince cagrilacak dinleyiciler (sunucu.py WS yayini baglar).
_ozet_dinleyiciler = []


def ozet():
    """Durum cubugu icin hafif ozet: {boyut, adet, hazir}.

    `cache_bilgi()` aksine disk taramasi YAPMAZ; bellekteki calisan
    toplami dondurur. `hazir` False ise ilk tam olcum henuz
    bitmemistir (istemci "hesaplaniyor" gosterir).
    """
    return {"boyut": _toplam["boyut"], "adet": _toplam["adet"],
            "hazir": _toplam["hazir"]}


def ozet_dinleyici_ekle(cb):
    """Ozet degisince `cb(ozet_sozlugu)` cagrilir."""
    if callable(cb) and cb not in _ozet_dinleyiciler:
        _ozet_dinleyiciler.append(cb)


def _ozet_bildir():
    """Dinleyicileri uyarir. Dinleyici hatasi cagirani ETKILEMEZ:
    karo yazma yolu asla bir UI kancasi yuzunden bozulmamalidir."""
    o = ozet()
    for cb in list(_ozet_dinleyiciler):
        try:
            cb(o)
        except Exception:
            pass


def _toplama_ekle(bayt):
    """Yeni yazilan karoyu calisan toplama ekler (O(1))."""
    with _kilit:
        _toplam["boyut"] += int(bayt or 0)
        _toplam["adet"] += 1
    _ozet_bildir()


def toplam_olc(arka_planda=True):
    """Ilk tam olcum. `arka_planda=True` ise ayri is parcaciginda
    calisir ve cagirani BLOKLAMAZ (sunucu acilisinda kullanilir)."""
    def _isle():
        boyut, adet = 0, 0
        if os.path.isdir(HARITA_CACHE):
            for kok, _dz, dosyalar in os.walk(HARITA_CACHE):
                for ad in dosyalar:
                    if ad.endswith(".tmp"):
                        continue
                    try:
                        boyut += os.stat(os.path.join(kok, ad)).st_size
                        adet += 1
                    except OSError:
                        continue
        with _kilit:
            # Olcum suresince yeni karo inmis olabilir. Olculen deger
            # o karolari da KAPSAR (dosya zaten diskteydi), bu yuzden
            # ustune ekleme YAPILMAZ; dogrudan atanir.
            _toplam["boyut"] = boyut
            _toplam["adet"] = adet
            _toplam["hazir"] = True
        _ozet_bildir()

    if arka_planda:
        t = threading.Thread(target=_isle, name="tile-cache-olc",
                             daemon=True)
        t.start()
        return t
    _isle()
    return None


def _quadkey(x, y, z):
    """Bing quadkey: z/x/y -> quadkey dizesi."""
    q = ""
    for i in range(z, 0, -1):
        d = 0
        mask = 1 << (i - 1)
        if x & mask:
            d += 1
        if y & mask:
            d += 2
        q += str(d)
    return q


def tile_yolu(kaynak, z, x, y):
    k = TILE_KAYNAKLARI.get(kaynak)
    if not k:
        return None
    return os.path.join(HARITA_CACHE, kaynak, str(z), str(x),
                        str(y) + k.get("uzanti", ".png"))


def tile_url(kaynak, z, x, y):
    k = TILE_KAYNAKLARI.get(kaynak)
    if not k:
        return None
    url = k["url"]
    if k.get("quadkey"):
        url = url.replace("{q}", _quadkey(x, y, z))
    subs = k.get("s")
    if subs:
        url = url.replace("{s}", subs[(x + y) % len(subs)])
    return (url.replace("{z}", str(z))
               .replace("{x}", str(x))
               .replace("{y}", str(y)))


# ==================================================================
# v2.4.51: IKI KATMANLI KARO DEPOSU (PostgreSQL + yerel disk)
# ==================================================================
# Kullanici istegi: "mumkunse harita tamponlarini da postgresql'e
# cevir".
#
# OLCUM (dene_karo.py, gercek PG 16):
#   300 karo okuma  : disk 6 ms | PG 60 ms (10.6x)
#   karo basina PG  : 0.20 ms -> 60 karoluk harita hareketi = 12 ms
#   ikili butunluk  : bayt-bire-bir DOGRU
#
# Oransal olarak PG 10 kat yavas, ANCAK mutlak deger 12 ms ve fark
# edilme siniri ~100 ms. Bu yuzden PG ana depo yapildi.
#
# DISK NEDEN KORUNUYOR?
# Karo okuma yolu tarayicinin her harita hareketinde onlarca kez
# cagirdigi SICAK yoldur. Veritabani gecici olarak erisilemezse
# (yeniden baslatma, ag) tek depo PG olsaydi HARITA KARARIRDI. Yerel
# disk ikinci katman olarak kalir: once disk (en hizli), sonra PG
# (merkezi), sonra internet.
#
# Bu, telemetri tamponunda ve gorev durumunda verilen kararin ayni
# mantigi: veritabani ana depo, yerel dosya dayaniklilik agi.
_pg_karo_kapali = False        # PG karo yolu hata verirse bir daha denenmez


def _pg_hazir() -> bool:
    """PG karo deposu kullanilabilir mi."""
    if _pg_karo_kapali:
        return False
    try:
        from . import veritabani as vt
        if not vt.pg_kipinde():
            return False           # SQLite kipi: karo tablosu kullanilmaz
        from . import pg
        return pg.yapilandirma_var()
    except Exception:
        return False


def _pg_karo_oku(kaynak, z, x, y):
    """Karoyu PG'den okur; yoksa None."""
    global _pg_karo_kapali
    if not _pg_hazir():
        return None
    try:
        from . import veritabani as vt
        with vt.baglanti() as con:
            s = con.execute(
                "SELECT veri FROM harita_karo WHERE kaynak=? AND z=? AND"
                " x=? AND y=?", (kaynak, z, x, y)).fetchone()
        if s and s[0] is not None:
            return bytes(s[0])
    except Exception:
        # Karo okuma HARITAYI BLOKLAMAMALI. Hata durumunda PG yolu
        # kapatilir ve disk/internet ile devam edilir.
        _pg_karo_kapali = True
    return None


def _pg_karo_yaz(kaynak, z, x, y, veri):
    """Karoyu PG'ye yazar (hata harita cizimini engellemez)."""
    global _pg_karo_kapali
    if not _pg_hazir():
        return
    try:
        import time as _t
        from . import veritabani as vt
        from . import pg
        with vt.baglanti() as con:
            con.execute(
                "INSERT OR REPLACE INTO harita_karo"
                " (kaynak, z, x, y, veri, bayt, ts) VALUES (?,?,?,?,?,?,?)",
                (kaynak, z, x, y, pg.ikili(veri), len(veri), _t.time()))
    except Exception:
        _pg_karo_kapali = True


def tile_getir(kaynak, z, x, y):
    """Karoyu dondurur: once yerel disk, sonra PG, sonra internet.

    Donus: (bayt_icerigi | None, mime)
    """
    yol = tile_yolu(kaynak, z, x, y)
    if yol is None:
        return None, None
    mime = "image/png" if yol.endswith(".png") else "image/jpeg"

    # 1) Yerel disk (en hizli; olculen 0.02 ms/karo)
    if os.path.isfile(yol) and os.path.getsize(yol) > 0:
        with open(yol, "rb") as f:
            return f.read(), mime

    # 2) PostgreSQL (merkezi depo; baska istasyon indirmis olabilir)
    veri = _pg_karo_oku(kaynak, z, x, y)
    if veri:
        # Yerel diske de yaz: ayni karo bir daha PG'den istenmesin.
        try:
            os.makedirs(os.path.dirname(yol), exist_ok=True)
            gecici = yol + ".tmp"
            with open(gecici, "wb") as f:
                f.write(veri)
            os.replace(gecici, yol)
            _toplama_ekle(len(veri))
        except Exception:
            pass          # disk yazilamasa da karo donmeli
        return veri, mime

    # 3) Internet
    url = tile_url(kaynak, z, x, y)
    try:
        istek = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(istek, timeout=10) as yanit:
            veri = yanit.read()
        if veri:
            os.makedirs(os.path.dirname(yol), exist_ok=True)
            gecici = yol + ".tmp"
            with open(gecici, "wb") as f:
                f.write(veri)
            os.replace(gecici, yol)
            # v2.4.33: calisan toplami guncelle (durum cubugu gostergesi).
            # Sadece YENI yazilan karo icin cagrilir; onbellekten
            # donen karo (yukaridaki erken donus) toplami degistirmez.
            _toplama_ekle(len(veri))
            # v2.4.51: merkezi depoya da yaz
            _pg_karo_yaz(kaynak, z, x, y, veri)
            return veri, mime
    except Exception:
        pass  # cevrimdisi veya kaynak hatasi: None doner, istemci bos gri cizer
    return None, None


def cache_bilgi():
    """Onbellek istatistikleri.

    Donus: {boyut, adet, kaynaklar: {ad: {adet, boyut, zoom_min,
            zoom_max, son_indirme}}}
    v2.3.0: kaynak bazinda dagilim + zoom araligi + son indirme zamani.
    """
    boyut, adet = 0, 0
    kaynaklar = {}
    if os.path.isdir(HARITA_CACHE):
        for kaynak in sorted(os.listdir(HARITA_CACHE)):
            k_yol = os.path.join(HARITA_CACHE, kaynak)
            if not os.path.isdir(k_yol):
                continue
            kb, ka = 0, 0
            zmin, zmax, son = None, None, 0.0
            for kok, _dizinler, dosyalar in os.walk(k_yol):
                for ad in dosyalar:
                    if ad.endswith(".tmp"):
                        continue
                    try:
                        tam = os.path.join(kok, ad)
                        st = os.stat(tam)
                        kb += st.st_size
                        ka += 1
                        if st.st_mtime > son:
                            son = st.st_mtime
                    except OSError:
                        continue
                # zoom klasorleri: HARITA_CACHE/kaynak/{z}/{x}/{y}.png
            try:
                zoomlar = [int(d) for d in os.listdir(k_yol)
                           if d.isdigit()]
                if zoomlar:
                    zmin, zmax = min(zoomlar), max(zoomlar)
            except OSError:
                pass
            if ka:
                etiket = (TILE_KAYNAKLARI.get(kaynak) or {}).get(
                    "ad", kaynak)
                kaynaklar[kaynak] = {
                    "etiket": etiket, "adet": ka, "boyut": kb,
                    "zoom_min": zmin, "zoom_max": zmax,
                    "son_indirme": son}
                boyut += kb
                adet += ka
    return {"boyut": boyut, "adet": adet, "kaynaklar": kaynaklar}


def cache_temizle():
    with _kilit:
        if os.path.isdir(HARITA_CACHE):
            shutil.rmtree(HARITA_CACHE, ignore_errors=True)
        # v2.4.33: calisan toplami da sifirla. Aksi halde durum
        # cubugu onbellek silinmis olmasina ragmen eski boyutu
        # gostermeye devam eder.
        _toplam["boyut"] = 0
        _toplam["adet"] = 0
        _toplam["hazir"] = True
    _ozet_bildir()
    return cache_bilgi()


def _lonlat_tile(lon, lat, z):
    """WGS84 -> XYZ tile indeksi."""
    lat = max(-85.05112878, min(85.05112878, lat))
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    yr = math.radians(lat)
    y = int((1.0 - math.log(math.tan(yr) + 1.0 / math.cos(yr)) / math.pi)
            / 2.0 * n)
    return (max(0, min(n - 1, x)), max(0, min(n - 1, y)))


def bolge_tile_sayisi(lat1, lon1, lat2, lon2, z1, z2):
    """Verilen cografi kutu + zoom araligi icin toplam tile adedi."""
    toplam = 0
    for z in range(z1, z2 + 1):
        x1, ya = _lonlat_tile(min(lon1, lon2), max(lat1, lat2), z)
        x2, yb = _lonlat_tile(max(lon1, lon2), min(lat1, lat2), z)
        toplam += (x2 - x1 + 1) * (yb - ya + 1)
    return toplam


# ---------------------------------------------------------------
# FAZ18-IS31-ESZAMANLI: toplu indirme yeniden yazildi
# ---------------------------------------------------------------
# OLCUM: eski surum ardisik HTTP istegi yapiyordu -> 4.9 karo/sn.
# Ankara sehri z10-16 = 20.563 karo = 69 DAKIKA. Kullanici acisindan
# "calismiyor" demekle ayni sey. Upstream gecikmesi (~200 ms) I/O
# beklemesi oldugundan is parcacigi havuzu dogrusal hizlanma verir.
#
# ES ZAMANLILIK NEDEN 8?
# ESRI/Google karo uclari tek istemciden makul es zamanliligi kabul
# eder; 8 istek hem 8x hizlanma saglar hem de upstream'i taciz
# etmez (kendi sunucumuzu da 8 baglantiyla sinirlar).
#
# UST SINIR NEDEN VAR?
# z10-19 araligi Ankara icin 1.29 MILYON karo / 15 GB eder. Boyle
# bir istek diski doldurur ve gunlerce surer. Sinir asilinca islem
# baslamaz; kullaniciya zoom araligini daraltmasi soylenir.
INDIRME_UST_SINIR = 250000
INDIRME_ES_ZAMAN = 8
# Olculen deger (bkz. yama basligi): tek is parcacigi 4.9 karo/sn.
# Havuzla ~8x. Tahmini sure hesabinda kullanilir.
_KARO_HIZ_TAHMIN = 4.9 * INDIRME_ES_ZAMAN
_KARO_BOYUT_TAHMIN = 12288          # olculen ortalama: ~12 KB/karo


def bolge_karolari(lat1, lon1, lat2, lon2, z1, z2):
    """Bolgedeki tum (z, x, y) uclulerini uretir."""
    for z in range(z1, z2 + 1):
        x1, ya = _lonlat_tile(min(lon1, lon2), max(lat1, lat2), z)
        x2, yb = _lonlat_tile(max(lon1, lon2), min(lat1, lat2), z)
        for x in range(x1, x2 + 1):
            for y in range(ya, yb + 1):
                yield (z, x, y)


def bolge_on_olcum(kaynak, lat1, lon1, lat2, lon2, z1, z2):
    """Indirme ONCESI kullaniciya gosterilecek tahmin.

    Kullanici "Gorunen Bolgeyi Indir" dedigi anda ne kadar isin
    icine girdigini bilmiyordu; ilerleme cubugu saatlerce donmus
    gorunuyordu. Bu islev karo sayisi, sure ve disk boyutunu
    ONCEDEN verir.
    """
    toplam = bolge_tile_sayisi(lat1, lon1, lat2, lon2, z1, z2)
    return {
        "toplam": toplam,
        "sinir": INDIRME_UST_SINIR,
        "asildi": toplam > INDIRME_UST_SINIR,
        "saniye": int(toplam / _KARO_HIZ_TAHMIN) if toplam else 0,
        "bayt": toplam * _KARO_BOYUT_TAHMIN,
        "es_zaman": INDIRME_ES_ZAMAN,
    }


def bolge_indir(kaynak, lat1, lon1, lat2, lon2, z1, z2, ilerleme_cb=None):
    """Bolgeyi zoom araliginda ES ZAMANLI indirir.

    ilerleme_cb(inen, toplam, hata) her 5 karoda VE en az saniyede
    bir cagrilir (eski surum 20 karoda birdi -> cubuk donmus
    gorunuyordu).
    """
    global indirme_durumu
    import concurrent.futures as _cf
    import time as _t

    toplam = bolge_tile_sayisi(lat1, lon1, lat2, lon2, z1, z2)

    # UST SINIR KAPISI: islem hic baslamaz, durum hatayi tasir.
    if toplam > INDIRME_UST_SINIR:
        indirme_durumu = {"aktif": False, "toplam": toplam, "inen": 0,
                          "hata": 0, "iptal": False,
                          "reddedildi": True,
                          "sinir": INDIRME_UST_SINIR}
        if ilerleme_cb:
            ilerleme_cb(0, toplam, 0)
        return indirme_durumu

    indirme_durumu = {"aktif": True, "toplam": toplam, "inen": 0,
                      "hata": 0, "iptal": False, "reddedildi": False}

    kilit = threading.Lock()
    son = {"an": 0.0, "sayac": 0}

    def _bildir(zorla=False):
        """Ilerlemeyi kullaniciya iletir; kilit ALTINDA cagrilmaz."""
        if not ilerleme_cb:
            return
        simdi = _t.time()
        if (zorla or son["sayac"] % 5 == 0
                or simdi - son["an"] >= 1.0):
            son["an"] = simdi
            ilerleme_cb(indirme_durumu["inen"], toplam,
                        indirme_durumu["hata"])

    def _tek(uclu):
        z, x, y = uclu
        if indirme_durumu["iptal"]:
            return
        veri, _mime = tile_getir(kaynak, z, x, y)
        with kilit:
            if veri is None:
                indirme_durumu["hata"] += 1
            indirme_durumu["inen"] += 1
            son["sayac"] += 1
        _bildir()

    try:
        with _cf.ThreadPoolExecutor(
                max_workers=INDIRME_ES_ZAMAN) as havuz:
            # Uretici tembel: milyonluk listeyi bellege almaz.
            isler = []
            for uclu in bolge_karolari(lat1, lon1, lat2, lon2, z1, z2):
                if indirme_durumu["iptal"]:
                    break
                isler.append(havuz.submit(_tek, uclu))
                # Kuyrugu sinirli tut: bellek sismesin.
                if len(isler) >= INDIRME_ES_ZAMAN * 64:
                    for i in isler:
                        i.result()
                    isler = []
            for i in isler:
                i.result()
    except BaseException:
        # Havuz cokerse bile durum tutarli kalmali.
        pass

    indirme_durumu["aktif"] = False
    _bildir(zorla=True)
    return indirme_durumu


def indirme_iptal():
    indirme_durumu["iptal"] = True
