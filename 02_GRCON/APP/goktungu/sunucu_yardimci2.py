# -*- coding: utf-8 -*-
"""Sunucu koprusu yardimcilari: SSL baglami, DB is-parcasi sarmalayicilari,
veri esleme, merkez panel adresi ve kamera listesi cozucusu.

Bu modul `sunucu.py`den DAVRANIS-KORUYUCU olarak ayrilmistir (Risk 6,
kademeli modulerlestirme). Icerik BIREBIR tasinmistir; mantik, sabit,
string, sira ve global durum DEGISTIRILMEMISTIR.

Geriye tam uyumluluk: `sunucu.py` bu moduldeki isimleri
`from .sunucu_yardimci2 import *` (+ altcizgili adlar icin acik liste)
ile yeniden disa acar; boylece `goktungu.sunucu.ssl_baglami`,
`goktungu.sunucu._db_is_parcasi`, `goktungu.sunucu._VERI_ESLEME`,
`goktungu.sunucu.IS94_SESSIZLIK_TAVANI` gibi mevcut erisimler AYNEN
calisir.

Bagimliliklar ve import dongusu:
  - Ust duzeyde yalniz stdlib (asyncio, json, os) ve `.sabitler`e
    baglidir. `sabitler` HICBIR `from . import` yapmaz -> dongu YOK.
  - `_db_iade_ederek` ve `_merkez_panel_adresi` icindeki
    `from . import veritabani/merkez` importlari GOVDE ICINDEDIR
    (fonksiyon calisirken cozulur); modul yukleme aninda cozulmez, bu
    yuzden `sunucu` <-> bu modul arasinda import dongusu OLUSMAZ.
"""
import asyncio
import json
import os

from .sabitler import SERTIFIKA_KLASORU, AVATAR_KLASORU, _veri_yolu

__all__ = [
    "IS94_SESSIZLIK_TAVANI",
    "_VERI_ESLEME",
    "_db_iade_ederek",
    "_db_is_parcasi",
    "_merkez_panel_adresi",
    "ssl_baglami",
    "_goruntu_kamera_listesi_coz",
]

# IS94_TELEMETRI_KISMA: veri degismese bile en gec bu kadar saniyede
# bir paket gonderilir. Gerekce: NAT/LTE ara kutulari uzun sessizlikte
# baglantiyi dusurur. Sunucu ping araligi 20 sn oldugu icin 10 sn
# guvenli tarafta kalir.
IS94_SESSIZLIK_TAVANI = 10.0


# v2.4.163: asyncio.to_thread varsayilan havuz is parcaciklari HIC olmez;
# PostgreSQL havuzundan odunc aldiklari baglanti is parcacigi olumunde geri
# alinir -> hic geri verilmiyordu. Birkac AI ayar degisikliginden sonra
# havuz (10) doluyor, sonraki islemler 20 sn bekleyip arayuzu kilitliyordu.
# Her cagri sonunda baglanti havuza iade edilir.
def _db_iade_ederek(fn, *a, **k):
    try:
        return fn(*a, **k)
    finally:
        try:
            from . import veritabani as _vt
            _vt.baglanti_kapat()
        except Exception:
            pass


async def _db_is_parcasi(fn, *a, **k):
    return await asyncio.to_thread(_db_iade_ederek, fn, *a, **k)


# v2.4.52: HTTP koku `assets/web`, kullanici verisi `veri/` altinda.
# Arayuz bu dosyalari KOK-GORELI ister ve istenen yollar veritabaninda
# kayitlidir (`avatars/x.png`, `ai_yuzler/kisiN_....jpg`); yol bicimi
# degistirilemez, cunku mevcut kayitlar bozulur. Bu yuzden istek yolu
# korunur, dosya sistemi tarafinda gercek konuma cevrilir.
#
# Yeni bir kullanici-verisi klasoru arayuze acilacaksa BURAYA eklenir;
# tek tek `translate_path` icine yazilirsa biri unutulur ve eksik olan
# SESSIZCE 404 doner (olculen vaka: `ai_yuzler`).
_VERI_ESLEME = (
    ("/avatars/", AVATAR_KLASORU),
    ("/ai_yuzler/", _veri_yolu("ai_yuzler")),
)


def _merkez_panel_adresi():
    """Kurumsal panelin (merkez sunucudaki) tam adresini dondurur.

    Merkez Uygulama kurulumunda `/company/` yereldeki dosyalardan
    servis EDILEMEZ: panel 23 ayri `/api/firma/...` ucu cagirir ve
    bu uclar yalniz merkez sunucuda vardir (olculdu). Bu yuzden
    istek merkeze yonlendirilir.

    Adres program ayarindan (`merkez_adres`) okunur; lisans
    dosyasindan DEGIL. Lisans govdesine alan eklemek imza
    sozlesmesini degistirir ve dagitilmis tum lisanslari gecersiz
    kilar.

    Merkez kullanilmayan (kapali devre) kurulumda bos dizi doner;
    cagiran taraf kullaniciyi bilgilendirir.
    """
    # `AyarYoneticisi` KULLANILMAZ: kurucusu `konsol` parametresi ister
    # ve icinde `tablolari_olustur()` + JSON gocu calistirir. Her HTTP
    # isteginde ornek yaratmak hem hatali (konsol yok) hem pahalidir.
    # Yalniz gereken anahtar dogrudan okunur.
    try:
        from . import merkez as _merkez
        from . import veritabani as _vt
    except Exception:
        return ""
    try:
        with _vt.baglanti() as con:
            r = con.execute(
                "SELECT deger FROM ayarlar WHERE anahtar = ?",
                ("merkez_adres",)).fetchone()
        ham = r["deger"] if r else None
        try:
            deger = json.loads(ham) if ham is not None else None
        except (ValueError, TypeError):
            deger = None
        ayar = _merkez.ayar_coz({"merkez_adres": deger})
    except Exception:
        return ""
    # `etkin` degil `adres` olculur: merkez kimlik dogrulamasi kapali
    # olsa da (yerel kullanicilarla giris) kurumsal panel adresi
    # gecerli olabilir. Ters durum da olur; bu yuzden adres bos ise
    # panel yok sayilir.
    adres = str(ayar.get("adres") or "").strip()
    if not adres:
        return ""
    try:
        taban = _merkez._taban(adres)
    except Exception:
        return ""
    return f"{taban}/company/" if taban else ""


def ssl_baglami():
    """Kendinden imzali sertifika ile SSL baglami dondurur.

    sertifika/gcs.crt + gcs.key yoksa openssl ile otomatik uretir.
    openssl bulunamazsa veya uretim basarisiz olursa None doner
    (HTTPS/WSS devre disi kalir, HTTP/WS calismaya devam eder).
    """
    import ssl
    import subprocess
    crt = os.path.join(SERTIFIKA_KLASORU, "gcs.crt")
    key = os.path.join(SERTIFIKA_KLASORU, "gcs.key")
    if not (os.path.exists(crt) and os.path.exists(key)):
        try:
            os.makedirs(SERTIFIKA_KLASORU, exist_ok=True)
            subprocess.run(
                ["openssl", "req", "-x509", "-newkey", "rsa:2048",
                 "-keyout", key, "-out", crt,
                 "-days", "3650", "-nodes",
                 "-subj", "/CN=goktungu-gcs"],
                check=True, capture_output=True, timeout=30)
            print(f"[SSL] Kendinden imzali sertifika uretildi: {crt}")
        except Exception as e:
            print(f"[SSL] Sertifika uretilemedi ({e}); "
                  f"HTTPS/WSS devre disi. openssl kurulu mu?")
            return None
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(crt, key)
        return ctx
    except Exception as e:
        print(f"[SSL] Sertifika yuklenemedi ({e}); HTTPS/WSS devre disi.")
        return None


def _goruntu_kamera_listesi_coz(veri):
    """Köprü kamera yanıtının doğrudan veya zarflı liste biçimini çözer."""
    if isinstance(veri, dict):
        veri = veri.get("sonuc", veri.get("kameralar"))
    return veri if isinstance(veri, list) else None
