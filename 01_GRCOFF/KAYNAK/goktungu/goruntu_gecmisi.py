"""İş 99: drona bağlı Görüntü Köprüsü kameralarının sınırlı geçmiş kareleri.

JPEG yalnız açık yönetici izni bulunan yerel kameradan gelir. App katmanı
ikinci savunma hattı olarak firma/köprü/dron sahipliği, 1 FPS, 96 KiB,
SHA-256, saklama ve disk kotası kapılarını tekrar uygular. Görüntü veritabanı
BLOB'u değildir; ``0600`` dosyada, yalnız metadata PostgreSQL/SQLite'tadır.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import urlencode

from . import veritabani as vt
from .sabitler import _veri_yolu

MAKS_JPEG = 96 * 1024
MAKS_GENISLIK = 640
MAKS_YUKSEKLIK = 640
VARSAYILAN_SAKLAMA_GUN = 7
VARSAYILAN_KOTA = 10 * 1024 * 1024 * 1024

_KOK = Path(_veri_yolu("goruntu_gecmisi"))
_SEMA_KILIT = threading.Lock()
_SEMA_HAZIR = False
_ORAN_KILIT = threading.Lock()
_SON_KARE = {}
_BAKIM_KILIT = threading.Lock()
_SON_BAKIM = 0.0
_KOTA_ONBELLEK = (0.0, 0)


def _tam_sayi(v, alt=0, ust=2_147_483_647):
    try:
        i = int(v)
    except (TypeError, ValueError):
        return None
    return i if alt <= i <= ust else None


def _sayi(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


def _jpeg_boyut(ham):
    """JPEG SOF başlığından gerçek genişlik/yüksekliği güvenli biçimde okur."""
    if not isinstance(ham, (bytes, bytearray)) or len(ham) < 16 or ham[:2] != b"\xff\xd8":
        return None
    i = 2
    sof = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
           0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    uzunluk = len(ham)
    while i + 3 < uzunluk:
        if ham[i] != 0xFF:
            i += 1
            continue
        while i < uzunluk and ham[i] == 0xFF:
            i += 1
        if i >= uzunluk:
            return None
        isaret = ham[i]
        i += 1
        if isaret in (0xD8, 0xD9) or 0xD0 <= isaret <= 0xD7:
            continue
        if i + 2 > uzunluk:
            return None
        parca = (ham[i] << 8) | ham[i + 1]
        if parca < 2 or i + parca > uzunluk:
            return None
        if isaret in sof:
            if parca < 7:
                return None
            yukseklik = (ham[i + 3] << 8) | ham[i + 4]
            genislik = (ham[i + 5] << 8) | ham[i + 6]
            return (genislik, yukseklik) if genislik > 0 and yukseklik > 0 else None
        i += parca
    return None


def _saklama_gun():
    try:
        return max(1, min(30, int(os.environ.get(
            "GOKTUNGU_GORUNTU_SAKLAMA_GUN", VARSAYILAN_SAKLAMA_GUN))))
    except (TypeError, ValueError):
        return VARSAYILAN_SAKLAMA_GUN


def _kota_bayt():
    try:
        return max(256 * 1024 * 1024, min(100 * 1024 * 1024 * 1024,
            int(os.environ.get("GOKTUNGU_GORUNTU_KOTA_BAYT", VARSAYILAN_KOTA))))
    except (TypeError, ValueError):
        return VARSAYILAN_KOTA


def sema_hazirla():
    global _SEMA_HAZIR
    if _SEMA_HAZIR:
        return
    with _SEMA_KILIT:
        if _SEMA_HAZIR:
            return
        with vt.baglanti() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS goruntu_gecmis_kareleri (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    firma_id    INTEGER NOT NULL,
                    ornek_id    INTEGER NOT NULL,
                    kurulum_uid TEXT NOT NULL DEFAULT '',
                    kamera_id   INTEGER NOT NULL,
                    dron_id     INTEGER NOT NULL,
                    dron_uid    TEXT NOT NULL,
                    ts          REAL NOT NULL,
                    alis_ts     REAL NOT NULL,
                    lat         REAL,
                    lon         REAL,
                    irtifa      REAL,
                    genislik    INTEGER NOT NULL DEFAULT 0,
                    yukseklik   INTEGER NOT NULL DEFAULT 0,
                    boyut       INTEGER NOT NULL DEFAULT 0,
                    sha256      TEXT NOT NULL,
                    dosya       TEXT NOT NULL UNIQUE
                );
                CREATE INDEX IF NOT EXISTS ix_goruntu_kare_firma_dron_ts
                    ON goruntu_gecmis_kareleri (firma_id, dron_id, ts DESC);
                CREATE INDEX IF NOT EXISTS ix_goruntu_kare_ornek_kamera_ts
                    ON goruntu_gecmis_kareleri (ornek_id, kamera_id, ts DESC);
                CREATE INDEX IF NOT EXISTS ix_goruntu_kare_alis
                    ON goruntu_gecmis_kareleri (alis_ts);
            """)
        _KOK.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(_KOK, 0o700)
        except OSError:
            pass
        _SEMA_HAZIR = True


def _dron_coz(firma_id, dron_uid):
    """Firma kapsamındaki kalıcı dron kimliğini ve son konumunu çözer."""
    uid = str(dron_uid or "").strip()[:120]
    if not uid:
        return None, "dron UID gerekli"
    firma_var = False
    try:
        firma_var = bool(vt.firma_kolonu_var("dronlar"))
    except Exception:
        firma_var = False
    with vt.baglanti() as con:
        if firma_var:
            d = con.execute(
                "SELECT id, uid, sysid FROM dronlar WHERE uid=? AND firma_id=?",
                (uid, int(firma_id))).fetchone()
        else:
            d = con.execute(
                "SELECT id, uid, sysid FROM dronlar WHERE uid=?", (uid,)).fetchone()
        if not d:
            return None, "dron firma kapsamında bulunamadı"
        son = con.execute(
            "SELECT lat, lon, irtifa FROM telemetri WHERE dron_id=?"
            " AND lat IS NOT NULL AND lon IS NOT NULL"
            " AND NOT (lat=0 AND lon=0) ORDER BY ts DESC LIMIT 1",
            (int(d["id"]),)).fetchone()
    try:
        sysid = int(d["sysid"] or 0)
    except (TypeError, ValueError, KeyError, IndexError):
        sysid = 0
    return {
        "id": int(d["id"]), "uid": str(d["uid"]),
        "sysid": sysid if 1 <= sysid <= 255 else None,
        "lat": (None if not son else son["lat"]),
        "lon": (None if not son else son["lon"]),
        "irtifa": (None if not son else son["irtifa"]),
    }, None


def _oran_kapisi(firma_id, ornek_id, kamera_id, kaynak_ts):
    """Aynı kamera için hem geliş hem kaynak zamanında en fazla 1 FPS."""
    simdi = time.time()
    anahtar = (int(firma_id), int(ornek_id), int(kamera_id))
    with _ORAN_KILIT:
        once = _SON_KARE.get(anahtar)
        if once:
            once_gelis, once_kaynak = once
            if simdi - once_gelis < 0.90:
                return False
            if kaynak_ts <= once_kaynak or kaynak_ts - once_kaynak < 0.90:
                return False
        _SON_KARE[anahtar] = (simdi, kaynak_ts)
        if len(_SON_KARE) > 4096:
            esik = simdi - 3600.0
            for k, v in list(_SON_KARE.items()):
                if v[0] < esik:
                    _SON_KARE.pop(k, None)
    return True


def _kota_doldu_mu():
    global _KOTA_ONBELLEK
    simdi = time.time()
    ts, toplam = _KOTA_ONBELLEK
    if simdi - ts > 30.0:
        sema_hazirla()
        try:
            with vt.baglanti() as con:
                toplam = int(con.execute(
                    "SELECT COALESCE(SUM(boyut),0) AS toplam"
                    " FROM goruntu_gecmis_kareleri").fetchone()["toplam"] or 0)
        except Exception:
            toplam = _kota_bayt()  # Ölçemiyorsak güvenli yönde reddet.
        _KOTA_ONBELLEK = (simdi, toplam)
    return int(toplam) >= _kota_bayt()


def _dosya_yaz(firma_id, ornek_id, dron_uid, kamera_id, ts, ham, ozet):
    tarih = time.strftime("%Y/%m/%d", time.gmtime(ts))
    dron_ozet = hashlib.sha256(str(dron_uid).encode("utf-8")).hexdigest()[:20]
    dizin = _KOK / str(int(firma_id)) / str(int(ornek_id)) / dron_ozet / tarih
    dizin.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(dizin, 0o700)
    except OSError:
        pass
    ad = "%d_%d_%s_%s.jpg" % (
        int(ts * 1000), int(kamera_id), ozet[:16], secrets.token_hex(5))
    hedef = dizin / ad
    gecici = dizin / ("." + ad + ".tmp")
    fd = os.open(str(gecici), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(ham)
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(gecici), str(hedef))
        try:
            os.chmod(hedef, 0o600)
        except OSError:
            pass
    except BaseException:
        try:
            gecici.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return str(hedef.relative_to(_KOK))


def kaydet(firma_id, ornek_id, kurulum_uid, paket):
    """Doğrulanmış merkez oturumundaki tek geçmiş karesini kaydeder."""
    sema_hazirla()
    if not isinstance(paket, dict) or paket.get("tur") != "dron_gecmis_kare":
        return None, "geçmiş kare paketi gerekli"
    firma_id = _tam_sayi(firma_id, 1)
    ornek_id = _tam_sayi(ornek_id, 1)
    kamera_id = _tam_sayi(paket.get("kamera_id"), 1)
    kaynak_ts = _sayi(paket.get("zaman"))
    genislik = _tam_sayi(paket.get("genislik"), 1, MAKS_GENISLIK)
    yukseklik = _tam_sayi(paket.get("yukseklik"), 1, MAKS_YUKSEKLIK)
    if None in (firma_id, ornek_id, kamera_id, kaynak_ts, genislik, yukseklik):
        return None, "kare metadata geçersiz"
    if abs(time.time() - kaynak_ts) > 300.0:
        return None, "kare zamanı bayat veya ileri"
    if not _oran_kapisi(firma_id, ornek_id, kamera_id, kaynak_ts):
        return None, "1 FPS sınırı"
    b64 = paket.get("jpeg_base64")
    if not isinstance(b64, str) or len(b64) > 132 * 1024:
        return None, "JPEG gövdesi geçersiz"
    try:
        ham = base64.b64decode(b64, validate=True)
    except Exception:
        return None, "JPEG base64 bozuk"
    if (not ham or len(ham) > MAKS_JPEG or len(ham) < 128 or
            not ham.startswith(b"\xff\xd8") or not ham.endswith(b"\xff\xd9")):
        return None, "JPEG biçim/boyut kapısı"
    gercek_boyut = _jpeg_boyut(ham)
    if (not gercek_boyut or gercek_boyut != (genislik, yukseklik) or
            gercek_boyut[0] > MAKS_GENISLIK or gercek_boyut[1] > MAKS_YUKSEKLIK):
        return None, "JPEG gerçek boyutu metadata ile uyuşmuyor"
    ozet = hashlib.sha256(ham).hexdigest()
    if not hmac.compare_digest(ozet, str(paket.get("sha256") or "")):
        return None, "JPEG özeti uyuşmuyor"
    dron, hata = _dron_coz(firma_id, paket.get("kaynak_dron_id"))
    if hata:
        return None, hata
    if _kota_doldu_mu():
        return None, "görüntü geçmişi disk kotası dolu"
    yol = _dosya_yaz(firma_id, ornek_id, dron["uid"], kamera_id,
                     kaynak_ts, ham, ozet)
    alis_ts = time.time()
    try:
        with vt.baglanti() as con:
            cur = con.execute(
                "INSERT INTO goruntu_gecmis_kareleri"
                " (firma_id,ornek_id,kurulum_uid,kamera_id,dron_id,dron_uid,"
                " ts,alis_ts,lat,lon,irtifa,genislik,yukseklik,boyut,sha256,dosya)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (firma_id, ornek_id, str(kurulum_uid or "")[:160], kamera_id,
                 dron["id"], dron["uid"], kaynak_ts, alis_ts,
                 dron["lat"], dron["lon"], dron["irtifa"], genislik,
                 yukseklik, len(ham), ozet, yol))
            kayit_id = int(cur.lastrowid)
    except BaseException:
        try:
            (_KOK / yol).unlink(missing_ok=True)
        except OSError:
            pass
        raise
    global _KOTA_ONBELLEK
    _KOTA_ONBELLEK = (time.time(), int(_KOTA_ONBELLEK[1]) + len(ham))
    bakim_yap()
    return {
        "id": kayit_id, "firma_id": firma_id, "ornek_id": ornek_id,
        "kamera_id": kamera_id, "dron_id": dron["id"],
        "dron_uid": dron["uid"], "sysid": dron.get("sysid"),
        "ts": kaynak_ts, "alis_ts": alis_ts,
        "lat": dron["lat"], "lon": dron["lon"], "irtifa": dron["irtifa"],
        "genislik": genislik, "yukseklik": yukseklik,
        "boyut": len(ham), "sha256": ozet,
    }, None


def _imza_anahtari():
    ham = (os.environ.get("GOKTUNGU_GORUNTU_URL_ANAHTAR") or
           os.environ.get("GOKTUNGU_IC_ANAHTAR") or "").encode("utf-8")
    return hashlib.sha256(b"goktungu-goruntu-url-v1\0" + ham).digest() if len(ham) >= 24 else None


def url_uret(kayit, ttl=90):
    anahtar = _imza_anahtari()
    if not anahtar or not kayit:
        return ""
    son = int(time.time()) + max(15, min(3600, int(ttl)))
    govde = "%d:%d:%d:%s" % (int(kayit["id"]), int(kayit["firma_id"]),
                              son, str(kayit["sha256"]))
    imza = hmac.new(anahtar, govde.encode("utf-8"), hashlib.sha256).hexdigest()
    return "/api/app/goruntu_kare?" + urlencode({
        "id": int(kayit["id"]), "firma": int(kayit["firma_id"]),
        "son": son, "imza": imza,
    })


def dosya_oku(kayit_id, firma_id, son, imza):
    sema_hazirla()
    kayit_id = _tam_sayi(kayit_id, 1)
    firma_id = _tam_sayi(firma_id, 1)
    son = _tam_sayi(son, 1, 9_999_999_999)
    if None in (kayit_id, firma_id, son) or son < int(time.time()):
        return None, "URL süresi dolmuş"
    with vt.baglanti() as con:
        r = con.execute(
            "SELECT id,firma_id,sha256,dosya,boyut FROM goruntu_gecmis_kareleri"
            " WHERE id=? AND firma_id=?", (kayit_id, firma_id)).fetchone()
    if not r:
        return None, "kare bulunamadı"
    anahtar = _imza_anahtari()
    govde = "%d:%d:%d:%s" % (kayit_id, firma_id, son, str(r["sha256"]))
    beklenen = (hmac.new(anahtar, govde.encode("utf-8"), hashlib.sha256).hexdigest()
                if anahtar else "")
    if not beklenen or not hmac.compare_digest(beklenen, str(imza or "")):
        return None, "imza geçersiz"
    hedef = (_KOK / str(r["dosya"])).resolve()
    kok = _KOK.resolve()
    if kok not in hedef.parents or not hedef.is_file():
        return None, "dosya bulunamadı"
    try:
        ham = hedef.read_bytes()
    except OSError:
        return None, "dosya okunamadı"
    if len(ham) != int(r["boyut"] or 0) or hashlib.sha256(ham).hexdigest() != str(r["sha256"]):
        return None, "dosya bütünlüğü bozuk"
    return ham, None


def son_kare(firma_id, dron_uid):
    sema_hazirla()
    with vt.baglanti() as con:
        r = con.execute(
            "SELECT id,firma_id,ornek_id,kamera_id,dron_id,dron_uid,ts,alis_ts,lat,lon,"
            " irtifa,genislik,yukseklik,boyut,sha256 FROM goruntu_gecmis_kareleri"
            " WHERE firma_id=? AND dron_uid=? ORDER BY ts DESC LIMIT 1",
            (int(firma_id), str(dron_uid or "")[:120])).fetchone()
    if not r:
        return None
    d = dict(r)
    d["url"] = url_uret(d, 90)
    return d


def son_kareler(firma_id, dron_uidleri, limit=100):
    """İzinli UID kümesindeki her dronun en yeni karesini döndürür.

    Çağıran katman firma dron sahipliğini kesin kaynak listesinden çözer.
    Bu katman ayrıca ``firma_id`` ve UID beyaz listesi uygular; böylece başka
    firmaya ait bir kare, yanlış istemci eşlemesi yapılsa bile dönemez.
    """
    sema_hazirla()
    try:
        fid = int(firma_id)
        sinir = max(1, min(500, int(limit or 100)))
    except (TypeError, ValueError):
        return []
    if fid <= 0:
        return []
    uidler = []
    gorulen = set()
    for ham in dron_uidleri or []:
        uid = str(ham or "").strip()[:120]
        if uid and uid not in gorulen:
            gorulen.add(uid)
            uidler.append(uid)
        if len(uidler) >= sinir:
            break
    if not uidler:
        return []
    imler = ",".join("?" for _ in uidler)
    arg = [fid] + uidler + [sinir]
    with vt.baglanti() as con:
        rows = con.execute(
            "SELECT g.id,g.firma_id,g.ornek_id,g.kamera_id,g.dron_id,"
            "g.dron_uid,g.ts,g.alis_ts,g.lat,g.lon,g.irtifa,g.genislik,g.yukseklik,"
            "g.boyut,g.sha256 FROM goruntu_gecmis_kareleri g "
            "WHERE g.firma_id=? AND g.dron_uid IN (" + imler + ") "
            "AND NOT EXISTS (SELECT 1 FROM goruntu_gecmis_kareleri n "
            "WHERE n.firma_id=g.firma_id AND n.dron_uid=g.dron_uid "
            "AND (n.ts>g.ts OR (n.ts=g.ts AND n.id>g.id))) "
            "ORDER BY g.ts DESC,g.id DESC LIMIT ?", arg).fetchall()
    sonuc = []
    for r in rows:
        d = dict(r)
        d["url"] = url_uret(d, 90)
        if d["url"]:
            sonuc.append(d)
    return sonuc


def listele(firma_id, dron_id, baslangic, bitis, limit=1000):
    sema_hazirla()
    limit = max(1, min(5000, int(limit or 1000)))
    with vt.baglanti() as con:
        rows = con.execute(
            "SELECT id,firma_id,ornek_id,kamera_id,dron_id,dron_uid,ts,alis_ts,lat,lon,"
            " irtifa,genislik,yukseklik,boyut,sha256"
            " FROM goruntu_gecmis_kareleri WHERE firma_id=? AND dron_id=?"
            " AND ts BETWEEN ? AND ? ORDER BY ts LIMIT ?",
            (int(firma_id), int(dron_id), float(baslangic), float(bitis), limit)
        ).fetchall()
    sonuc = []
    for r in rows:
        d = dict(r)
        d["url"] = url_uret(d, 900)
        sonuc.append(d)
    return sonuc


def bakim_yap(zorla=False):
    global _SON_BAKIM, _KOTA_ONBELLEK
    simdi = time.time()
    if not zorla and simdi - _SON_BAKIM < 3600.0:
        return 0
    if not _BAKIM_KILIT.acquire(blocking=False):
        return 0
    try:
        if not zorla and time.time() - _SON_BAKIM < 3600.0:
            return 0
        sema_hazirla()
        esik = time.time() - _saklama_gun() * 86400.0
        with vt.baglanti() as con:
            rows = con.execute(
                "SELECT id,dosya FROM goruntu_gecmis_kareleri WHERE alis_ts<?"
                " ORDER BY alis_ts LIMIT 10000", (esik,)).fetchall()
            ids = [int(r["id"]) for r in rows]
            if ids:
                imler = ",".join("?" for _ in ids)
                con.execute("DELETE FROM goruntu_gecmis_kareleri WHERE id IN (" +
                            imler + ")", ids)
        for r in rows:
            try:
                hedef = (_KOK / str(r["dosya"])).resolve()
                if _KOK.resolve() in hedef.parents:
                    hedef.unlink(missing_ok=True)
            except OSError:
                pass
        _SON_BAKIM = time.time()
        _KOTA_ONBELLEK = (0.0, 0)
        return len(rows)
    finally:
        _BAKIM_KILIT.release()
