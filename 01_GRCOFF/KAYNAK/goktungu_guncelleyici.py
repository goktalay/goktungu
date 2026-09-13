#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GRCOFF arka plan güncelleme servisi (dosya tabanlı).

NEDEN (2.5.26): Önceki model her güncellemede imzasız bir NSIS `.exe`
indirip çalıştırıyordu; Windows Defender bunu sezgisel olarak
`Trojan:Win32/Sabsik.FL.A!ml` diye karantinaya alıp güncellemeyi
`[Errno 22]` ile bozuyordu. Bu servis bunun yerine yalnız DEĞİŞEN düz
veri dosyalarını (.py/.js/.html/...) indirir — çalıştırılabilir kurulum
indirmez, dolayısıyla AV sezgiselini tetiklemez. Ayrıca yalnız değişen
dosyalar indiği için güncelleme küçük ve hızlıdır (artımlı).

ROL:
  1. Uygulamayı (main.py) alt süreç olarak başlatır ve ayakta tutar
     (uygulama çökse bile bu servis yaşar; yeniden başlatır).
  2. Belirli aralıklarla katalogtan İMZALI dosya manifesti çeker.
  3. Yerel dosyalarla karşılaştırır, yalnız sha256'sı farklı olanları
     indirir, her dosyayı doğrular.
  4. Uygulamayı durdurur, dosyaları ATOMİK yerleştirir, silinecekleri
     kaldırır, PostgreSQL göçü uygulamanın açılışında koşar, uygulamayı
     yeniden başlatır. Herhangi bir adım başarısızsa GERİ ALIR.

GÜVENLİK (savunma sistemi): manifest Ed25519 imzalı (gömülü açık
anahtar), yalnız goktungu.com HTTPS, her dosya sha256 doğrulanır,
lisans kimliği zorunlu, dizin-gezinme koruması, atomik uygulama + geri
alma. Bu modül cv2/psycopg2 gibi ağır/yerel bağımlılık İÇE ALMAZ.
"""
from __future__ import annotations

import hashlib
import json
import os
import ssl
import sys
import time
import urllib.request

KATALOG = "https://goktungu.com"
MANIFEST_YOLU = "/api/istemci/dosya_manifesti"
DOSYA_YOLU = "/api/istemci/dosya"
# Güncellemeyle YÖNETİLEN kökler (yalnız bunların altındaki dosyalar
# yazılır/silinir). Kullanıcı verisi (veri/, ai_kayitlar/, *.log,
# merkez_lisans.json, pg.json) ASLA dokunulmaz.
YONETILEN_KOKLER = ("assets/", "ai_modeller/")
YONETILEN_DOSYALAR = ("main.py", "requirements.txt", "goktungu_guncelleyici.py")
KORUNAN = ("veri/", "ai_kayitlar/", "gunluk/", "telemetri_tampon/")
_BLOK = 256 * 1024
_AZAMI_DOSYA = 80 * 1024 * 1024


def _sha256_dosya(yol: str) -> str:
    h = hashlib.sha256()
    try:
        with open(yol, "rb") as f:
            for blok in iter(lambda: f.read(_BLOK), b""):
                h.update(blok)
    except OSError:
        return ""
    return h.hexdigest()


def _guvenli_bilesenler(bagil: str):
    """Manifest yolunu güvenli göreli parçalara çevirir; kötüyse None."""
    bagil = str(bagil or "").replace("\\", "/")
    if not bagil or bagil.startswith("/") or ".." in bagil.split("/"):
        return None
    # Sürücü harfi / iki nokta / geri gidiş yok
    if ":" in bagil:
        return None
    parcalar = [p for p in bagil.split("/") if p not in ("", ".")]
    return parcalar or None


def _yonetilen_mi(bagil: str) -> bool:
    b = bagil.replace("\\", "/")
    if any(b == d or b.startswith(k) for k in KORUNAN for d in ()):
        return False
    if any(b.startswith(k) for k in KORUNAN):
        return False
    return b in YONETILEN_DOSYALAR or any(b.startswith(k) for k in YONETILEN_KOKLER)


class GuncellemeMotoru:
    """Manifest çek → farkı bul → indir → uygula. Ağ enjekte edilebilir
    (sınav için `_getir` ve `_dosya_getir` override edilir)."""

    def __init__(self, kok: str, urun: str, mevcut_surum: str,
                 lisans_belgesi=None, gunluk=print):
        self.kok = os.path.abspath(kok)
        self.urun = urun
        self.mevcut_surum = mevcut_surum
        self.lisans_belgesi = lisans_belgesi or {}
        self.gunluk = gunluk
        # 2.5.33: ayrıntılı ilerleme (IlerlemeYazici.bildir imzalı çağrı)
        self.ilerleme = None

    def _il(self, asama, mesaj, yuzde=None, adim=True, durum="calisiyor", **alt):
        if self.ilerleme is None:
            return
        try:
            self.ilerleme(asama=asama, mesaj=mesaj, yuzde=yuzde, adim=adim,
                          durum=durum, **alt)
        except Exception:
            pass

    # -- ağ (gerçek) --------------------------------------------------
    def _istek(self, yol, govde):
        veri = json.dumps(govde, ensure_ascii=False).encode("utf-8")
        return urllib.request.Request(
            KATALOG + yol, data=veri, method="POST",
            headers={"Content-Type": "application/json",
                     "User-Agent": "GOKTUNGU-Guncelleyici/" + self.mevcut_surum})

    def _getir_manifest(self) -> dict:
        istek = self._istek(MANIFEST_YOLU,
                            {"urun": self.urun, "surum": self.mevcut_surum,
                             "lisans": self.lisans_belgesi})
        with urllib.request.urlopen(istek, timeout=20,
                                    context=ssl.create_default_context()) as y:
            return json.loads(y.read() or b"{}")

    def _dosya_getir(self, surum: str, bagil: str, bayt_cb=None) -> bytes:
        istek = self._istek(DOSYA_YOLU,
                            {"urun": self.urun, "surum": surum, "yol": bagil,
                             "lisans": self.lisans_belgesi})
        with urllib.request.urlopen(istek, timeout=45,
                                    context=ssl.create_default_context()) as y:
            veri = b""
            while True:
                blok = y.read(_BLOK)
                if not blok:
                    break
                veri += blok
                if bayt_cb:
                    try:
                        bayt_cb(len(blok))
                    except Exception:
                        pass
                if len(veri) > _AZAMI_DOSYA:
                    raise ValueError("dosya beklenenden büyük")
            return veri

    # -- doğrulama ----------------------------------------------------
    def _manifest_dogrula(self, m: dict) -> dict | None:
        try:
            from goktungu import lisans
        except Exception:
            import lisans  # düz yapı yedeği
        imza = str(m.get("imza") or "")
        govde = m.get("manifest")
        if not isinstance(govde, dict) or not imza:
            self.gunluk("[GUNC] Manifest eksik (imza/govde yok)")
            return None
        if str(govde.get("acik_anahtar") or "") != lisans.ACIK_ANAHTAR_B64:
            self.gunluk("[GUNC] Manifest imza anahtarı tanınmıyor")
            return None
        if not lisans.imza_dogrula(lisans.govde_bayt(govde), imza):
            self.gunluk("[GUNC] Manifest imzası geçersiz")
            return None
        if str(govde.get("urun")) != self.urun:
            return None
        dosyalar = govde.get("dosyalar")
        if not isinstance(dosyalar, list):
            return None
        return govde

    # -- fark ---------------------------------------------------------
    def fark_bul(self, manifest: dict):
        """(indirilecek [(yol,sha256,boyut)], silinecek [yol]) döndürür."""
        indir, gecersiz = [], []
        _liste = manifest.get("dosyalar", [])
        _n = len(_liste)
        for _i, d in enumerate(_liste, 1):
            if _i == 1 or _i % 25 == 0 or _i == _n:
                self._il("karsilastirma",
                         "Yerel dosyalar karşılaştırılıyor (%d/%d)" % (_i, _n),
                         yuzde=5 + 10.0 * _i / max(1, _n), adim=False,
                         no=_i, toplam=_n)
            bagil = d.get("yol"); sha = str(d.get("sha256") or "").lower()
            parc = _guvenli_bilesenler(bagil)
            if not parc or len(sha) != 64 or not _yonetilen_mi(bagil):
                gecersiz.append(bagil)
                continue
            yerel = os.path.join(self.kok, *parc)
            if _sha256_dosya(yerel) != sha:
                indir.append((bagil, sha, int(d.get("boyut", 0))))
        if gecersiz:
            self.gunluk("[GUNC] Manifestte %d geçersiz/yönetilmeyen yol atlandı"
                        % len(gecersiz))
        silinecek = []
        for bagil in manifest.get("silinecekler", []):
            parc = _guvenli_bilesenler(bagil)
            if parc and _yonetilen_mi(bagil) and \
                    os.path.isfile(os.path.join(self.kok, *parc)):
                silinecek.append(bagil)
        return indir, silinecek

    # -- indir + uygula ----------------------------------------------
    def uygula(self, dur_geri_cagir=None, baslat_geri_cagir=None) -> dict:
        """Tam döngü: manifest → fark → indir(stage) → uygula(atomik).

        `dur_geri_cagir`/`baslat_geri_cagir`: uygulamayı durdur/başlat.
        Döner: {"guncellendi": bool, "surum": ..., "neden": ...}
        2.5.33: her adım `self.ilerleme` ile ayrıntılı bildirilir.
        """
        t0 = time.time()
        MB = 1024.0 * 1024.0
        self._il("manifest", "İmzalı sürüm listesi (manifest) alınıyor", yuzde=1)
        try:
            ham = self._getir_manifest()
        except Exception as e:
            self._il("hata", "Manifest alınamadı: %s" % e, yuzde=100, durum="hata")
            return {"guncellendi": False, "neden": "manifest alınamadı: %s" % e}
        self._il("imza", "Manifest Ed25519 imzası doğrulanıyor", yuzde=3)
        manifest = self._manifest_dogrula(ham)
        if not manifest:
            self._il("hata", "Manifest imzası doğrulanamadı", yuzde=100, durum="hata")
            return {"guncellendi": False, "neden": "manifest doğrulanamadı"}
        hedef = str(manifest.get("surum") or "")
        self._il("imza", "İmza geçerli; yayınlanan sürüm %s (kurulu %s)"
                 % (hedef, self.mevcut_surum), yuzde=4, durum="tamam",
                 hedef_surum=hedef)
        if not _surum_yeni_mi(self.mevcut_surum, hedef):
            self._il("guncel", "Yazılım güncel (%s)" % self.mevcut_surum,
                     yuzde=100, durum="tamam")
            return {"guncellendi": False, "surum": hedef, "neden": "guncel"}

        indir, silinecek = self.fark_bul(manifest)
        if not indir and not silinecek:
            self._il("guncel", "Dosyalar zaten güncel", yuzde=100, durum="tamam")
            return {"guncellendi": False, "surum": hedef,
                    "neden": "fark yok (sürüm damgası tazelenecek)"}
        toplam_bayt = sum(max(0, int(b)) for _, _, b in indir)
        self._il("karsilastirma", "%d dosya indirilecek (%.2f MB), %d dosya silinecek"
                 % (len(indir), toplam_bayt / MB, len(silinecek)), yuzde=15,
                 durum="tamam", toplam=len(indir), bayt_toplam=toplam_bayt)
        self.gunluk("[GUNC] %s -> %s: %d dosya indirilecek, %d silinecek"
                    % (self.mevcut_surum, hedef, len(indir), len(silinecek)))

        # 1) Stage: değişen dosyaları geçici dizine indir + doğrula
        sahne = os.path.join(self.kok, ".guncelleme_sahne")
        _rmtree(sahne)
        os.makedirs(sahne, exist_ok=True)
        inen = [0]
        n = len(indir)
        try:
            for no, (bagil, sha, boyut) in enumerate(indir, 1):
                son = [0.0]

                def _cb(k, _no=no, _bagil=bagil, _son=son):
                    inen[0] += k
                    if time.time() - _son[0] >= 0.25:
                        _son[0] = time.time()
                        self._il("indirme", "İndiriliyor (%d/%d): %s" % (_no, n, _bagil),
                                 yuzde=15 + 60.0 * inen[0] / max(1, toplam_bayt),
                                 adim=False, no=_no, toplam=n, dosya=_bagil,
                                 bayt=inen[0], bayt_toplam=toplam_bayt)
                veri = self._dosya_getir(hedef, bagil, bayt_cb=_cb)
                if hashlib.sha256(veri).hexdigest().lower() != sha:
                    raise ValueError("sha256 uyuşmadı: %s" % bagil)
                parc = _guvenli_bilesenler(bagil)
                hedef_yol = os.path.join(sahne, *parc)
                os.makedirs(os.path.dirname(hedef_yol), exist_ok=True)
                with open(hedef_yol, "wb") as f:
                    f.write(veri)
                self._il("indirme", "İndirildi ve SHA-256 doğrulandı (%d/%d): %s — %.1f KB"
                         % (no, n, bagil, len(veri) / 1024.0),
                         yuzde=15 + 60.0 * inen[0] / max(1, toplam_bayt),
                         durum="tamam", no=no, toplam=n, dosya=bagil,
                         bayt=inen[0], bayt_toplam=toplam_bayt)
        except Exception as e:
            _rmtree(sahne)
            self._il("hata", "İndirme/doğrulama hatası: %s — kurulu sürüm değiştirilmedi" % e,
                     yuzde=100, durum="hata")
            return {"guncellendi": False, "neden": "indirme/doğrulama: %s" % e}

        # 2) Uygula: uygulamayı durdur, yedekle, taşı, sil, yeniden başlat
        self._il("durdurma", "Uygulama durduruluyor (dosyalar değiştirilecek)", yuzde=77)
        if dur_geri_cagir:
            try:
                dur_geri_cagir()
            except Exception as e:
                self.gunluk("[GUNC] Uygulama durdurma uyarısı: %s" % e)
        self._il("durdurma", "Uygulama durduruldu", yuzde=80, durum="tamam")
        yedek = os.path.join(self.kok, ".guncelleme_yedek")
        _rmtree(yedek)
        os.makedirs(yedek, exist_ok=True)
        uygulanan = []
        try:
            for no, (bagil, sha, boyut) in enumerate(indir, 1):
                parc = _guvenli_bilesenler(bagil)
                canli = os.path.join(self.kok, *parc)
                yeni = os.path.join(sahne, *parc)
                if os.path.isfile(canli):
                    yb = os.path.join(yedek, *parc)
                    os.makedirs(os.path.dirname(yb), exist_ok=True)
                    _kopyala(canli, yb)
                os.makedirs(os.path.dirname(canli), exist_ok=True)
                _kopyala(yeni, canli)
                uygulanan.append(bagil)
                self._il("yerlestirme", "Yedeklendi ve yerleştirildi (%d/%d): %s" % (no, n, bagil),
                         yuzde=80 + 12.0 * no / max(1, n), durum="tamam",
                         no=no, toplam=n, dosya=bagil)
            for bagil in silinecek:
                parc = _guvenli_bilesenler(bagil)
                canli = os.path.join(self.kok, *parc)
                if os.path.isfile(canli):
                    yb = os.path.join(yedek, *parc)
                    os.makedirs(os.path.dirname(yb), exist_ok=True)
                    _kopyala(canli, yb)
                    os.remove(canli)
                    uygulanan.append("-" + bagil)
                    self._il("silme", "Kaldırıldı: %s" % bagil, yuzde=93, durum="tamam")
        except Exception as e:
            self.gunluk("[GUNC] Uygulama hatası, GERİ ALINIYOR: %s" % e)
            self._il("geri_alma", "Yerleştirme hatası (%s); değişiklikler geri alınıyor" % e,
                     yuzde=94, durum="hata")
            self._geri_al(yedek, uygulanan, silinecek)
            _rmtree(sahne)
            self._il("baslatma", "Önceki sürümle uygulama başlatılıyor", yuzde=97)
            if baslat_geri_cagir:
                try: baslat_geri_cagir()
                except Exception: pass
            self._il("hata", "Güncelleme geri alındı; kurulu sürüm korunuyor (%s)"
                     % self.mevcut_surum, yuzde=100, durum="hata")
            return {"guncellendi": False, "neden": "uygulama hatası: %s" % e}

        _rmtree(sahne)
        _rmtree(yedek)
        self._il("temizlik", "Geçici dosyalar ve yedek temizlendi", yuzde=94, durum="tamam")
        # 3) Sürüm damgası (isteğe bağlı; asıl sürüm js/surum.js'ten okunur)
        try:
            with open(os.path.join(self.kok, ".surum"), "w") as f:
                f.write(hedef + "\n")
        except OSError:
            pass
        self._il("baslatma", "Uygulama yeni sürümle (%s) başlatılıyor" % hedef, yuzde=96)
        if baslat_geri_cagir:
            try:
                baslat_geri_cagir()
            except Exception as e:
                self.gunluk("[GUNC] Uygulama başlatma uyarısı: %s" % e)
        self._il("baslatma", "Uygulama başlatıldı; arayüz bağlantısı bekleniyor",
                 yuzde=98, durum="tamam")
        self.gunluk("[GUNC] Güncelleme tamam: %s" % hedef)
        self._il("tamam", "Güncelleme tamamlandı: %s → %s (%d dosya, %.1f MB, %.0f sn)"
                 % (self.mevcut_surum, hedef, len(uygulanan), inen[0] / MB,
                    time.time() - t0), yuzde=100, durum="tamam")
        return {"guncellendi": True, "surum": hedef, "sayi": len(uygulanan)}

    def _geri_al(self, yedek, uygulanan, silinecek):
        for bagil in uygulanan:
            try:
                if bagil.startswith("-"):
                    b = bagil[1:]; parc = _guvenli_bilesenler(b)
                    yb = os.path.join(yedek, *parc)
                    if os.path.isfile(yb):
                        _kopyala(yb, os.path.join(self.kok, *parc))
                else:
                    parc = _guvenli_bilesenler(bagil)
                    yb = os.path.join(yedek, *parc)
                    if os.path.isfile(yb):
                        _kopyala(yb, os.path.join(self.kok, *parc))
            except Exception:
                pass


def _surum_yeni_mi(mevcut: str, aday: str) -> bool:
    def p(s):
        try:
            return tuple(int(x) for x in str(s).split("."))
        except (TypeError, ValueError):
            return ()
    a, b = p(mevcut), p(aday)
    return bool(b) and (not a or b > a)


def _kopyala(kaynak, hedef):
    with open(kaynak, "rb") as g:
        veri = g.read()
    gecici = hedef + ".yeni"
    with open(gecici, "wb") as f:
        f.write(veri)
        f.flush()
        os.fsync(f.fileno())
    os.replace(gecici, hedef)


def _rmtree(yol):
    import shutil
    try:
        shutil.rmtree(yol)
    except FileNotFoundError:
        pass
    except OSError:
        pass


# ======================================================================
# Arka plan servisi (gözetmen): main.py'yi çalıştırır + günceller
# ======================================================================
import subprocess
import threading

URUN = "gcs"
KONTROL_ARALIGI = 15 * 60      # 15 dk'da bir güncelleme kontrolü
ILK_KONTROL_GECIKME = 60       # açılıştan 60 sn sonra ilk kontrol
# 2.5.30: Uygulama içi "Şimdi Güncelle" düğmesi VERİ köküne bu dosyayı
# yazar; gözetmen görünce 15 dk'yı beklemeden hemen güncelleme uygular.
# (goktungu/guncelleme_dosya.TETIK_ADI ile birebir aynı olmalı.)
TETIK_ADI = ".guncelleme_istek"


def _kurulum_koku() -> str:
    """Kurulum kökü = bu dosyanın bulunduğu dizin (main.py ile aynı)."""
    return os.path.dirname(os.path.abspath(__file__))


def _yol_kur(kok: str):
    """goktungu paketini içe alabilmek için sys.path'i hazırlar.

    Paket yapısında kod <kok>/assets/python altında; düz geliştirme
    yapısında <kok> altındadır. İkisi de eklenir."""
    for p in (os.path.join(kok, "assets", "python"), kok):
        if p not in sys.path and os.path.isdir(p):
            sys.path.insert(0, p)


def _surum_oku(kok: str) -> str:
    """Kurulu uygulama sürümünü js/surum.js -> GCS_SURUM'dan okur."""
    import re
    for aday in (os.path.join(kok, "assets", "web", "js", "surum.js"),
                 os.path.join(kok, "js", "surum.js")):
        try:
            with open(aday, encoding="utf-8") as f:
                bas = f.read(2048)
            m = re.search(r'GCS_SURUM\s*=\s*["\']([0-9][0-9.]*)["\']', bas)
            if m:
                return m.group(1)
        except OSError:
            continue
    return "0.0.0"


def _veri_koku() -> str:
    v = (os.environ.get("GOKTUNGU_VERI_KOKU") or "").strip()
    if v:
        return v
    kok = _kurulum_koku()
    return os.path.join(kok, "veri")


def _lisans_belgesi(veri: str):
    """merkez_lisans.json içeriğini ({lisans, imza, acik_anahtar}) okur."""
    yol = os.path.join(veri, "merkez_lisans.json")
    try:
        with open(yol, encoding="utf-8") as f:
            belge = json.load(f)
        if isinstance(belge, dict) and isinstance(belge.get("lisans"), dict):
            return belge
    except (OSError, ValueError):
        pass
    return None


ILERLEME_ADI = "guncelleme_ilerleme.json"
GOZETMEN_ISARET_ADI = "gozetmen_kod.json"


class IlerlemeYazici:
    """2.5.33: Güncelleme ilerlemesini VERİ kökünde JSON olarak yazar.

    Uygulama (main.py) bu dosyayı okuyup arayüze iletir. Dosya atomik
    yazılır; ara bildirimler 0,2 sn'de bir, adım/aşama değişimleri anında.
    `adimlar` her ayrıntıyı zaman damgasıyla tutar (son 400)."""

    def __init__(self, veri_koku, tetik="otomatik", mevcut_surum=""):
        self.yol = os.path.join(veri_koku, ILERLEME_ADI)
        self._son_yazim = 0.0
        self.d = {
            "kimlik": "%d" % int(time.time() * 1000),
            "tetik": tetik, "etkin": True, "asama": "basladi",
            "durum": "calisiyor", "mesaj": "Güncelleme denetimi başladı",
            "yuzde": 0.0, "mevcut_surum": mevcut_surum, "hedef_surum": "",
            "no": 0, "toplam": 0, "dosya": "", "bayt": 0, "bayt_toplam": 0,
            "basla_ts": time.time(), "guncel_ts": time.time(), "bitis_ts": None,
            "adimlar": [],
        }

    def bildir(self, asama, mesaj, yuzde=None, adim=True, durum="calisiyor", **alt):
        d = self.d
        onceki = d.get("asama")
        d["asama"], d["mesaj"], d["durum"] = asama, mesaj, durum
        if yuzde is not None:
            d["yuzde"] = round(max(d.get("yuzde") or 0.0, min(100.0, float(yuzde))), 1)
        for k in ("no", "toplam", "dosya", "bayt", "bayt_toplam", "hedef_surum"):
            if k in alt:
                d[k] = alt[k]
        d["guncel_ts"] = time.time()
        son = asama in ("tamam", "guncel", "hata")
        if son:
            d["etkin"] = False
            d["bitis_ts"] = time.time()
        if adim or son:
            d["adimlar"].append({"ts": time.time(), "asama": asama,
                                 "mesaj": mesaj, "durum": durum})
            d["adimlar"] = d["adimlar"][-400:]
        if adim or son or asama != onceki or time.time() - self._son_yazim >= 0.2:
            self.yaz()

    def yaz(self):
        self._son_yazim = time.time()
        try:
            gecici = self.yol + ".yeni"
            with open(gecici, "w", encoding="utf-8") as f:
                json.dump(self.d, f, ensure_ascii=False)
            os.replace(gecici, self.yol)
        except OSError:
            pass


ANA_PID_ADI = "merkez_ana_pid.json"


def _win_is_nesnesi():
    """2.5.33: Bu süreci 'kapanınca çocukları öldür' Windows iş nesnesine
    alır. Servis durdurulurken gözetmen zorla kapatıldığında (CTRL_BREAK
    servis bağlamında gönderilemiyor) main.py ve AI işçisi ÖKSÜZ kalıp
    portları tutuyor, yeni Merkez 'kod 0' ile çıkıp döngüye giriyordu."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)

        class BASIC(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                        ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t),
                        ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class IO(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in (
                "a", "b", "c", "d", "e", "f")]

        class EXT(ctypes.Structure):
            _fields_ = [("Basic", BASIC), ("Io", IO),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        k32.CreateJobObjectW.restype = wintypes.HANDLE
        is_h = k32.CreateJobObjectW(None, None)
        if not is_h:
            return None
        bilgi = EXT()
        # KILL_ON_JOB_CLOSE | BREAKAWAY_OK (servis yeniden baslatma komutu kacabilsin)
        bilgi.Basic.LimitFlags = 0x2000 | 0x800
        if not k32.SetInformationJobObject(is_h, 9, ctypes.byref(bilgi),
                                           ctypes.sizeof(bilgi)):
            return None
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        if not k32.AssignProcessToJobObject(is_h, k32.GetCurrentProcess()):
            return None
        return is_h
    except Exception:
        return None


def _surec_yolu(pid):
    """PID'in çalıştırılabilir yolu (yalnız Windows; bulunamazsa '')."""
    try:
        cikti = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-Process -Id %d -ErrorAction SilentlyContinue).Path" % int(pid)],
            capture_output=True, text=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        return cikti.strip()
    except Exception:
        return ""


def _port_sahipleri(portlar):
    pidler = set()
    try:
        cikti = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True,
            timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        for satir in cikti.splitlines():
            p = satir.split()
            if (len(p) >= 5 and p[0].upper() == "TCP"
                    and p[2] in ("0.0.0.0:0", "[::]:0")
                    and any(p[1].endswith(":%d" % po) for po in portlar)):
                pidler.add(int(p[4]))
    except Exception:
        pass
    return pidler


class Gozetmen:
    """main.py'yi alt süreç olarak çalıştırır, ayakta tutar; ayrı bir
    iş parçacığında periyodik güncelleme uygular."""

    def __init__(self, gunluk=print):
        self.kok = _kurulum_koku()
        self.gunluk = gunluk
        self.surec = None
        self._calis = True
        self._guncelleniyor = threading.Event()
        self._kilit = threading.Lock()
        _yol_kur(self.kok)

    # -- uygulama süreci --
    def _ana_baslat(self):
        with self._kilit:
            if self.surec and self.surec.poll() is None:
                return
            py = sys.executable
            ana = os.path.join(self.kok, "main.py")
            bayrak = 0
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                bayrak |= subprocess.CREATE_NO_WINDOW
            ortam = dict(os.environ)
            ortam.setdefault("PYTHONUNBUFFERED", "1")
            ortam["PYTHONIOENCODING"] = "utf-8"
            cikti = None
            try:
                # 2.5.33: main.py çıktısı ayrı ve okunur (UTF-8) günlükte.
                veri = _veri_koku()
                os.makedirs(veri, exist_ok=True)
                yol = os.path.join(veri, "merkez_uygulama.log")
                if os.path.isfile(yol) and os.path.getsize(yol) > 20 * 1024 * 1024:
                    os.replace(yol, yol + ".1")
                cikti = open(yol, "a", encoding="utf-8")
                cikti.write("\n=== %s main.py başlatılıyor ===\n"
                            % time.strftime("%Y-%m-%d %H:%M:%S"))
                cikti.flush()
            except OSError:
                cikti = None
            self.surec = subprocess.Popen(
                [py, ana, "--tarayici-yok"], cwd=self.kok,
                env=ortam, creationflags=bayrak,
                stdout=cikti, stderr=subprocess.STDOUT if cikti else None)
            self.gunluk("[GOZETMEN] Uygulama başlatıldı (PID %d)" % self.surec.pid)
            try:
                with open(os.path.join(_veri_koku(), ANA_PID_ADI), "w") as f:
                    json.dump({"pid": self.surec.pid, "ts": time.time()}, f)
            except OSError:
                pass

    def _ana_durdur(self, sure=25):
        with self._kilit:
            s = self.surec
            self.surec = None
        if not s or s.poll() is not None:
            return
        try:
            if os.name == "nt" and hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
                import signal
                s.send_signal(getattr(signal, "CTRL_BREAK_EVENT", signal.SIGTERM))
            else:
                s.terminate()
        except Exception:
            try: s.terminate()
            except Exception: pass
        try:
            s.wait(timeout=sure)
        except Exception:
            try: s.kill()
            except Exception: pass
        self.gunluk("[GOZETMEN] Uygulama durduruldu")

    # -- güncelleme --
    def _guncelle_dene(self):
        veri = _veri_koku()
        belge = _lisans_belgesi(veri)
        if belge is None:
            self.gunluk("[GUNC] Lisans belgesi yok; güncelleme atlandı "
                        "(merkez_lisans.json gerekli)")
            return
        surum = _surum_oku(self.kok)
        # 2.5.33: Motor kodu HER turda diskten taze yüklenir; güncelleyicinin
        # kendisindeki iyileştirmeler servis yeniden başlamadan devreye girer.
        mod = self._taze_modul()
        tetik = "kullanici" if getattr(self, "_kullanici_istedi", False) else "otomatik"
        self._kullanici_istedi = False
        motor = mod.GuncellemeMotoru(self.kok, URUN, surum,
                                     lisans_belgesi=belge, gunluk=self.gunluk)
        il = None
        if hasattr(mod, "IlerlemeYazici"):
            il = mod.IlerlemeYazici(veri, tetik=tetik, mevcut_surum=surum)
            il.yaz()
            motor.ilerleme = il.bildir
        self._guncelleniyor.set()
        try:
            sonuc = motor.uygula(dur_geri_cagir=lambda: self._ana_durdur(),
                                 baslat_geri_cagir=lambda: self._ana_baslat())
        except Exception as e:
            self.gunluk("[GUNC] Güncelleme hatası: %s" % e)
            if il is not None:
                il.bildir("hata", "Güncelleme hatası: %s" % e, yuzde=100, durum="hata")
            self._ana_baslat()
            return
        finally:
            self._guncelleniyor.clear()
        if sonuc.get("guncellendi"):
            self.gunluk("[GUNC] %s sürümüne güncellendi (%d dosya)"
                        % (sonuc.get("surum"), sonuc.get("sayi", 0)))

    def _taze_modul(self):
        """goktungu_guncelleyici.py'yi diskten yeni bir modül olarak yükler;
        olmazsa çalışan kopyayı kullanır."""
        try:
            import importlib.util
            yol = os.path.join(self.kok, "goktungu_guncelleyici.py")
            spec = importlib.util.spec_from_file_location(
                "goktungu_guncelleyici_taze_%d" % int(time.time() * 1000), yol)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            return m
        except Exception as e:
            self.gunluk("[GUNC] Taze motor yüklenemedi (%s); mevcut kullanılıyor" % e)
            return sys.modules[__name__]

    def _isaret_yaz(self):
        """Çalışan gözetmenin kod özeti (arayüz eski gözetmeni tanır)."""
        try:
            with open(os.path.abspath(__file__), "rb") as f:
                ozet = hashlib.sha256(f.read()).hexdigest()
            veri = _veri_koku()
            os.makedirs(veri, exist_ok=True)
            with open(os.path.join(veri, GOZETMEN_ISARET_ADI), "w", encoding="utf-8") as f:
                json.dump({"ozet": ozet, "pid": os.getpid(), "ts": time.time(),
                           "taze_motor": True}, f)
        except Exception:
            pass

    def _tetik_tuket(self):
        """Uygulama içi 'Şimdi Güncelle' isteği (tetik dosyası) var mı?
        Varsa siler ve True döner (tek seferlik tüketim)."""
        try:
            yol = os.path.join(_veri_koku(), TETIK_ADI)
            if os.path.isfile(yol):
                try:
                    os.remove(yol)
                except OSError:
                    pass
                return True
        except OSError:
            pass
        return False

    def _guncelle_dongu(self):
        # İlk kontrol gecikmesi de tetiğe duyarlı (kullanıcı hemen isteyebilir).
        for _ in range(ILK_KONTROL_GECIKME):
            if not self._calis:
                break
            if self._tetik_tuket():
                self._kullanici_istedi = True
                break
            time.sleep(1)
        while self._calis:
            try:
                self._guncelle_dene()
            except Exception as e:
                self.gunluk("[GUNC] Döngü hatası: %s" % e)
            for _ in range(KONTROL_ARALIGI):
                if not self._calis:
                    break
                if self._tetik_tuket():
                    self.gunluk("[GUNC] Uygulama içi güncelleme isteği alındı")
                    self._kullanici_istedi = True
                    break
                time.sleep(1)

    def _oksuzleri_temizle(self):
        """Önceki (öldürülmüş) gözetmenden kalan main.py/işçi süreçlerini
        kapatır. YALNIZ bu kurulumun python.exe'si ile çalışanlar."""
        if os.name != "nt":
            return
        adaylar = set()
        try:
            with open(os.path.join(_veri_koku(), ANA_PID_ADI)) as f:
                adaylar.add(int(json.load(f).get("pid")))
        except Exception:
            pass
        try:
            http = int(os.environ.get("GOKTUNGU_HTTP_PORT") or 8000)
        except ValueError:
            http = 8000
        adaylar |= _port_sahipleri((http, 8765, int(os.environ.get(
            "GOKTUNGU_AI_PORT") or 8910)))
        benim = os.path.normcase(os.path.abspath(sys.executable))
        for pid in sorted(adaylar):
            if pid in (os.getpid(), 0, 4):
                continue
            yol = _surec_yolu(pid)
            if not yol or os.path.normcase(os.path.abspath(yol)) != benim:
                continue
            self.gunluk("[GOZETMEN] Öksüz kalmış süreç kapatılıyor (PID %d)" % pid)
            try:
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                               capture_output=True, timeout=15,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except Exception:
                pass
        time.sleep(1.5)

    def calis(self):
        self._is_nesnesi = _win_is_nesnesi()
        if os.name == "nt":
            self.gunluk("[GOZETMEN] İş nesnesi (çocuklar birlikte kapanır): %s"
                        % ("etkin" if self._is_nesnesi else "kurulamadı"))
        self._oksuzleri_temizle()
        self._isaret_yaz()
        self.gunluk("[GOZETMEN] Başladı; kök=%s sürüm=%s"
                    % (self.kok, _surum_oku(self.kok)))
        self._ana_baslat()
        threading.Thread(target=self._guncelle_dongu, daemon=True,
                         name="guncelleme").start()
        # Ana süreç gözetimi: güncelleme sırasında DEĞİLKEN çökerse yeniden başlat
        while self._calis:
            time.sleep(3)
            if self._guncelleniyor.is_set():
                continue
            s = self.surec
            if s is not None and s.poll() is not None:
                self.gunluk("[GOZETMEN] Uygulama beklenmedik durdu "
                            "(kod %s); yeniden başlatılıyor" % s.returncode)
                time.sleep(2)
                self._ana_baslat()

    def durdur(self):
        self._calis = False
        self._ana_durdur()


def _zamanli_gunluk(metin):
    print("%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), metin), flush=True)


def main():
    g = Gozetmen(gunluk=_zamanli_gunluk)
    try:
        g.calis()
    except KeyboardInterrupt:
        g.durdur()


if __name__ == "__main__":
    main()
