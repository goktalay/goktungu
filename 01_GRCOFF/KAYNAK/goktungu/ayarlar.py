# -*- coding: utf-8 -*-
"""AyarYoneticisi: program ayarlarini SQLite (gcs.db / ayarlar tablosu)
uzerinde tutar ve SYSID tipi cozumleme yapar.

v2.3.0: JSON dosyasi (gcs_ayarlar.json) yerine SQLite. Mevcut JSON
dosyasi varsa ilk calistirmada otomatik aktarilir ve yeniden
adlandirilir (gcs_ayarlar.json.eski) — artik hicbir veri JSON'da
tutulmaz.
"""
import base64
import binascii
import hashlib
import json
import os

from .sabitler import AYAR_DOSYASI, SYSID_TABLOSU
from . import veritabani


class AyarYoneticisi:
    """Program ayarlari (gcs.db 'ayarlar' tablosu) okuma/yazma."""

    def __init__(self, konsol, dosya=AYAR_DOSYASI):
        self.konsol = konsol
        self.dosya = dosya
        veritabani.tablolari_olustur()
        self._json_goc()

    # ------------------------------------------------------------------
    # JSON -> SQLite tek seferlik goc
    # ------------------------------------------------------------------
    def _json_goc(self):
        if not os.path.isfile(self.dosya):
            return
        try:
            with open(self.dosya, "r", encoding="utf-8") as f:
                eski = json.load(f)
        except (OSError, json.JSONDecodeError):
            eski = {}
        if eski:
            with veritabani.baglanti() as con:
                mevcut = con.execute(
                    "SELECT COUNT(*) AS n FROM ayarlar").fetchone()["n"]
                if mevcut == 0:
                    for k, v in eski.items():
                        con.execute(
                            "INSERT OR REPLACE INTO ayarlar (anahtar, deger)"
                            " VALUES (?,?)",
                            (str(k), json.dumps(v, ensure_ascii=False)))
                    self.konsol("AYAR",
                                f"gcs_ayarlar.json -> gcs.db aktarildi "
                                f"({len(eski)} anahtar).")
        # JSON dosyasini devre disi birak (veri kaybi olmasin diye sil-me)
        try:
            os.replace(self.dosya, self.dosya + ".eski")
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Okuma / yazma (API ayni kaldi)
    # ------------------------------------------------------------------
    @staticmethod
    def _metin(deger):
        """BLOB olarak saklanmis metni `str`e cevirir.

        ## v2.4.26 SAVUNMA KATMANI

        v2.4.25 onarimi tum metin kolonlarini BLOB'a cevirmisti; kok
        neden `db_onarim` icinde hedef baglantiya da
        `text_factory = bytes` uygulanmasiydi. Bunun sonucunda `yukle()`
        sozluk anahtarlarini `bytes` olarak donduruyor ve `sunucu.py`
        her arayuz baglantisinda cokuyordu:

            TypeError: keys must be str, int, float, bool or None,
                       not bytes

        Asil duzeltme `db_onarim` icindedir ve acilistaki goc adimi
        mevcut veritabanini onarir. Buradaki donusum IKINCI KATMANDIR:
        goc herhangi bir nedenle calismazsa (salt okunur dosya, izin
        hatasi, elle kopyalanmis eski dosya) uygulama en azindan
        calismaya devam eder.
        """
        if isinstance(deger, bytes):
            try:
                return deger.decode("utf-8")
            except UnicodeDecodeError:
                return deger.decode("utf-8", errors="replace")
        return deger

    # ------------------------------------------------------------------
    # v2.4.53 GUVENLIK: arayuze yayinlanacak surum
    # ------------------------------------------------------------------
    # `yukle()` merkez hesabinin SIFRESINI de dondurur, cunku merkeze
    # her cagrida kimlik gonderilir (merkez tek yonlu modelde oturum
    # tutmaz). Ancak bu sozluk WebSocket ile TUM arayuz istemcilerine
    # duyurulur; ham sifrenin tarayiciya inmesi kabul edilemez.
    # `yayin()` sifreyi cikarir ve yerine yalnizca "kayitli mi"
    # bilgisini koyar (`merkez_sifre_var`). Arayuz bu bayrakla alanin
    # yer tutucusunu yazar.
    # BULGU_07: `dji_belirtec` GDP istemci kimlik dogrulamasi
    # icin kullanilir. Bu sozluk WebSocket ile TUM arayuz
    # istemcilerine duyuruldugu icin belirtecin tarayiciya
    # inmesi onu ise yaramaz hale getirirdi.
    GIZLI_ANAHTARLAR = ("merkez_sifre", "dji_belirtec")

    # IS96: logo SQLite'da data URI olarak saklanmaya devam eder; ancak
    # WebSocket protokolunde ham `logo_veri` alani artik YOKTUR. HTTP ucu
    # yalniz kapali MIME kumesi ve sinirli boyuttaki veriyi sunabilir.
    LOGO_MIME = {
        "image/png": "image/png",
        "image/jpeg": "image/jpeg",
        "image/jpg": "image/jpeg",
        "image/webp": "image/webp",
    }
    LOGO_AZAMI = 512 * 1024

    @classmethod
    def _sirket_logo_coz(cls, logo_veri):
        """Dogrulanmis logo baytlari, MIME ve SHA-256 ozetini dondurur."""
        if not isinstance(logo_veri, str) or not logo_veri.startswith("data:"):
            return None
        try:
            baslik, kodlu = logo_veri.split(",", 1)
        except ValueError:
            return None
        if not baslik.endswith(";base64"):
            return None
        mime = cls.LOGO_MIME.get(baslik[5:-7].strip().lower())
        if mime is None or not kodlu:
            return None
        # Once kodlu metni sinirla; gereksiz buyuk bellek ayirimi olmasin.
        kodlu_azami = 4 * ((cls.LOGO_AZAMI + 2) // 3)
        if len(kodlu) > kodlu_azami:
            return None
        try:
            ham = base64.b64decode(kodlu, validate=True)
        except (ValueError, binascii.Error):
            return None
        if not ham or len(ham) > cls.LOGO_AZAMI:
            return None
        # Yalniz data URI basligina guvenilmez; ham dosya imzasi da MIME
        # ile uyusmalidir. Boylece image/* etiketi altinda HTML/SVG veya
        # baska icerik sunulamaz.
        imza_gecerli = (
            (mime == "image/png" and ham.startswith(b"\x89PNG\r\n\x1a\n"))
            or (mime == "image/jpeg" and ham.startswith(b"\xff\xd8\xff"))
            or (mime == "image/webp" and len(ham) >= 12
                and ham[:4] == b"RIFF" and ham[8:12] == b"WEBP")
        )
        if not imza_gecerli:
            return None
        return ham, mime, hashlib.sha256(ham).hexdigest()

    def sirket_logo(self, ayarlar=None):
        """HTTP ucunun sunabilecegi dogrulanmis firma logosunu dondurur."""
        a = ayarlar if ayarlar is not None else self.yukle()
        sirket = a.get("sirket") if isinstance(a, dict) else None
        if not isinstance(sirket, dict):
            return None
        return self._sirket_logo_coz(sirket.get("logo_veri"))

    def yayin(self, ayarlar=None):
        """Arayuze duyurulabilir ayar sozlugu (gizli alanlar maskeli)."""
        a = dict(ayarlar if ayarlar is not None else self.yukle())
        for anahtar in self.GIZLI_ANAHTARLAR:
            if anahtar in a:
                a.pop(anahtar, None)
                a[anahtar + "_var"] = True
            else:
                a.setdefault(anahtar + "_var", False)

        # IS96 yeni istemci sozlesmesi: data URI cikartilir. Yalniz logo
        # varligi ve icerik ozetli URL duyurulur; eski `logo_veri` alani
        # yanita geri eklenmez.
        sirket = a.get("sirket")
        if isinstance(sirket, dict):
            sirket_yayin = dict(sirket)
            logo = self._sirket_logo_coz(sirket_yayin.pop("logo_veri", None))
            # Sunucu audit alanları istemcide tüketilmiyor ve açılış
            # sözleşmesinin parçası değildir. Şirket kaydında tutulurlar;
            # yalnız WebSocket yayın kopyasından çıkarılırlar.
            for alan in ("kuran", "kurulum_ts", "guncelleyen",
                         "guncelleme_ts"):
                sirket_yayin.pop(alan, None)
            sirket_yayin["logo_var"] = logo is not None
            sirket_yayin["logo_url"] = (
                "/api/app/sirket_logo?v=" + logo[2][:16]
                if logo is not None else "")
            a["sirket"] = sirket_yayin

        a["lisans"] = self._lisans_ozeti()
        return a

    # ------------------------------------------------------------------
    # MERKEZ UYGULAMA LISANSI (v2.4.65)
    # ------------------------------------------------------------------
    # Lisans ozeti VAR OLAN `{"tip": "ayarlar"}` duyurusuna eklenir;
    # ayri bir kanal ACILMAZ. Gerekce: arayuzun radar/GCCDUAL yetenek
    # karari zaten bu duyuruyla tazeleniyor. Ikinci bir kanal, iki
    # kaynagin esitlenmesi gereken bir yaris durumu yaratir ve bu
    # proje bunun bedelini bir kez odedi: menu gorunurlugu ile harita
    # gorunurlugu ayri kaynaklardan beslendigi icin "menude yok ama
    # haritada radar halkalari var" celiskisi dogmustu (v2.4.58).
    #
    # GIZLILIK: lisans belgesinin IMZASI arayuze GONDERILMEZ. Arayuzun
    # imzaya isi yoktur; dogrulama sunucuda yapilir. Imzayi yayinlamak,
    # belgeyi baska kuruluma kopyalamayi kolaylastirmaktan baska bir
    # sey saglamazdi.
    def _lisans_ozeti(self):
        try:
            from goktungu import lisans as _lis
            o = _lis.yetki_ozeti()
        except Exception:
            # Lisans modulu ice aktarilamazsa GCS acilmaya devam eder.
            # Yetkiler "merkezden" sayilir; olagan kurulum davranisi
            # birebir korunur.
            return {"lisansli": False, "kaynak": "merkez",
                    "sinirsiz": False, "ai": False,
                    "radar": False, "gccdual": False, "m50": False,
                    "firma_unvan": "", "lisans_uid": "", "hata": ""}
        return {
            "lisansli": bool(o.get("lisansli")),
            "kaynak": str(o.get("kaynak") or "merkez"),
            "sinirsiz": bool(o.get("sinirsiz")),
            "ai": bool(o.get("ai")),
            "radar": bool(o.get("radar")),
            "gccdual": bool(o.get("gccdual")),
            # v2.4.203 OLCULEN KUSUR: bu ozet `m50` alanini TASIMIYORDU.
            # "Lisansi Yenile" yaniti tam ozeti gonderdigi icin menu
            # aciliyor, sayfa yenilenince (F5) buradaki eksik ozet gelip
            # `lisansUstSinir("m50")` tanimsiz -> false oldugundan
            # Elektro-Optik menusu yeniden gizleniyordu. Belge dogruydu;
            # eksik olan bu satirdi.
            "m50": bool(o.get("m50", False)),
            "firma_unvan": str(o.get("firma_unvan") or ""),
            "lisans_uid": str(o.get("lisans_uid") or ""),
            # Hata metni arayuze TASINIR: 5.000 $ odemis musteri
            # yetkilerinin neden acilmadigini ekrandan gormeli.
            # Sessizce yok saymak kabul edilemez.
            "hata": str(o.get("hata") or ""),
        }

    def yukle(self):
        ayarlar = {}
        try:
            with veritabani.baglanti() as con:
                for r in con.execute("SELECT anahtar, deger FROM ayarlar"):
                    anahtar = self._metin(r["anahtar"])
                    if not isinstance(anahtar, str):
                        # JSON nesne anahtari olarak yalnizca `str`
                        # guvenlidir; sayisal veya beklenmeyen tipler
                        # metne cevrilir.
                        anahtar = str(anahtar)
                    ham = self._metin(r["deger"])
                    try:
                        ayarlar[anahtar] = json.loads(ham)
                    except (ValueError, TypeError):
                        ayarlar[anahtar] = None
        except Exception:
            pass
        return ayarlar

    def kaydet(self, yeni):
        with veritabani.baglanti() as con:
            for k, v in (yeni or {}).items():
                con.execute(
                    "INSERT OR REPLACE INTO ayarlar (anahtar, deger)"
                    " VALUES (?,?)",
                    (str(k), json.dumps(v, ensure_ascii=False)))
        self.konsol("AYAR", f"Kaydedildi: {yeni}")
        return self.yukle()

    def sysid_tipi(self, sysid):
        """Tabloya (ve varsa ayarlardaki eklere) gore dron tipi."""
        ekler = self.yukle().get("sysid_tablosu", {}) or {}
        try:
            birlesik = dict(SYSID_TABLOSU)
            for k, v in ekler.items():
                birlesik[int(k)] = str(v)
        except (TypeError, ValueError):
            birlesik = SYSID_TABLOSU
        return birlesik.get(sysid)
