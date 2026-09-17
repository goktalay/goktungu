#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""GÖKTUNGU MERKEZ — giriş noktası.

Kullanım:

    python3.11 main.py                 # servisi başlat
    python3.11 main.py --kurulum       # şema + ilk yönetici (etkileşimsiz)
    python3.11 main.py --sema          # yalnız şemayı uygula/güncelle
    python3.11 main.py --durum         # veritabanı ve röle durumu

Açılış sırası:
  1. Yapılandırma okunur (yoksa üretilir).
  2. PostgreSQL erişimi denenir; şema sürümü kontrol edilir, gerekiyorsa
     göç uygulanır (kullanıcı isteği: "güncelleme varsa ilk açılışta yap").
  3. Ters WebSocket röle dinleyicisi ayrı iş parçacığında başlatılır.
  4. HTTP (ve sertifika varsa HTTPS) dinleyicileri açılır.
"""

from __future__ import annotations

import os
import re
import signal
import sys
import time

BURASI = os.path.dirname(os.path.abspath(__file__))
if BURASI not in sys.path:
    sys.path.insert(0, BURASI)

import mk_db as db          # noqa: E402
import mk_kimlik as kimlik  # noqa: E402
import mk_role as role      # noqa: E402
import mk_sunucu as sunucu  # noqa: E402
from mk_ayar import PROJE_KOKU, ayar_oku  # noqa: E402

SEMA_DOSYA = os.path.join(BURASI, "merkez_sema.sql")
BEKLENEN_SEMA = 13  # 2026-09-17: sunucu_ornekleri.urun (goc_sema13)


def _pg_dene() -> tuple[bool, str]:
    try:
        db.deger("SELECT 1")
        return True, ""
    except Exception as e:
        return False, str(e)


def sema_surumu() -> int:
    try:
        return int(db.deger("SELECT surum FROM sema_surum WHERE id = 1") or 0)
    except Exception:
        return 0


def goc_dosyalari() -> list[tuple[int, str]]:
    """`goc_sema{N}.sql` dosyalarını (hedef sürüm, yol) olarak döndürür.

    Dosya adındaki sayı **hedef** şema sürümüdür: `goc_sema6.sql`
    5'ten 6'ya yükseltir. Sıralama SAYISALDIR; alfabetik sıralama
    `goc_sema10` öğesini `goc_sema6`'dan önce koyardı.
    """
    bulunan: list[tuple[int, str]] = []
    for ad in os.listdir(BURASI):
        e = re.match(r"^goc_sema(\d+)\.sql$", ad)
        if e:
            bulunan.append((int(e.group(1)), os.path.join(BURASI, ad)))
    bulunan.sort(key=lambda x: x[0])
    return bulunan


def goc_uygula(mevcut: int) -> tuple[bool, str, int]:
    """`mevcut` sürümünden sonraki tüm göçleri sırayla uygular.

    TASARIM: Her göç KENDİ işleminde çalışır. Hepsi tek işleme
    alınsaydı sondaki bir hata, başarıyla uygulanmış öncekileri de
    geri alacak ve sistem hangi sürümde olduğunu bilemeyecekti. Göç
    dosyalarının kendisi `sema_surum` satırını günceller; böylece
    başarılı bir göç kalıcı olarak işaretlenmiş olur.
    """
    son = mevcut
    for hedef, yol in goc_dosyalari():
        if hedef <= mevcut:
            continue
        with open(yol, "r", encoding="utf-8") as f:
            sql = f.read()
        print(f"[MERKEZ] Goc uygulaniyor: {os.path.basename(yol)} "
              f"({son} -> {hedef})")
        try:
            with db.baglanti() as con:
                cur = con.cursor()
                cur.execute(sql)
                con.commit()
                cur.close()
        except Exception as e:
            return False, f"{os.path.basename(yol)}: {e}", son
        son = sema_surumu() or hedef
    return True, "", son


def sema_uygula() -> tuple[bool, str]:
    """Şemayı ve ardından bekleyen göçleri uygular.

    Taban betik baştan sona `IF NOT EXISTS` ile yazıldığı için birden
    çok kez çalıştırılması güvenlidir. Göçler taban betikten SONRA
    çalışır; çünkü `ALTER TABLE ... ADD COLUMN` için tablonun önce var
    olması gerekir.
    """
    if not os.path.isfile(SEMA_DOSYA):
        return False, f"Şema dosyası yok: {SEMA_DOSYA}"
    with open(SEMA_DOSYA, "r", encoding="utf-8") as f:
        sql = f.read()
    try:
        with db.baglanti() as con:
            cur = con.cursor()
            cur.execute(sql)
            con.commit()
            cur.close()
    except Exception as e:
        return False, str(e)
    tamam, hata, _ = goc_uygula(sema_surumu())
    if not tamam:
        return False, hata
    return True, ""


def kurulum(eposta: str | None = None, sifre: str | None = None,
            ad_soyad: str = "", unvan: str | None = None) -> int:
    tamam, hata = _pg_dene()
    if not tamam:
        print(f"[KURULUM] PostgreSQL erisilemedi: {hata}")
        return 2
    print("[KURULUM] Sema uygulaniyor...")
    tamam, hata = sema_uygula()
    if not tamam:
        print(f"[KURULUM] Sema hatasi: {hata}")
        return 3
    print(f"[KURULUM] Sema surumu: {sema_surumu()}")
    if kimlik.yonetici_var_mi():
        print("[KURULUM] Sistem yoneticisi zaten var; atlandi")
        return 0
    eposta = eposta or os.environ.get("MERKEZ_YONETICI_EPOSTA") or \
        "mkaderoglu@veilox.com.tr"
    sifre = sifre or os.environ.get("MERKEZ_YONETICI_SIFRE") or ""
    if not sifre:
        print("[KURULUM] Yonetici sifresi verilmedi "
              "(MERKEZ_YONETICI_SIFRE veya --sifre)")
        return 4
    yid, hata = kimlik.yonetici_olustur(
        eposta, sifre, ad_soyad or "Muhammed Kaderoğlu",
        unvan or "Kurucu Ortağı ve Genel Müdürü")
    if hata:
        print(f"[KURULUM] Yonetici olusturulamadi: {hata}")
        return 5
    print(f"[KURULUM] Sistem yoneticisi olusturuldu: {eposta} (id {yid})")
    return 0


def durum() -> int:
    tamam, hata = _pg_dene()
    if not tamam:
        print(f"PostgreSQL: ERISILEMEDI ({hata})")
        return 2
    print(f"PostgreSQL      : tamam")
    print(f"Sema surumu     : {sema_surumu()} (beklenen {BEKLENEN_SEMA})")
    print(f"Havuz           : {db.havuz_durum()}")
    for ad, sql in (
        ("Firma", "SELECT count(*) FROM firmalar"),
        ("Kullanici", "SELECT count(*) FROM kullanicilar"),
        ("Sistem yonetici", "SELECT count(*) FROM sistem_yoneticileri"),
        ("Sunucu ornegi", "SELECT count(*) FROM sunucu_ornekleri"),
        ("Ucus kaydi", "SELECT count(*) FROM ucus_kayitlari"),
        ("Video kaydi", "SELECT count(*) FROM video_kayitlari"),
        ("Surum paketi", "SELECT count(*) FROM surumler"),
    ):
        print(f"{ad:<16}: {db.deger(sql)}")
    return 0


def servis(gecersiz: dict[str, int] | None = None) -> int:
    a = ayar_oku()
    # Test kurulumları için port geçersiz kılma (canlı servisi etkilemez)
    for anahtar, deger in (gecersiz or {}).items():
        a[anahtar] = deger
        print(f"[MERKEZ] {anahtar} gecersiz kilindi: {deger}")
    print(f"[MERKEZ] Proje koku: {PROJE_KOKU}")
    tamam, hata = _pg_dene()
    if not tamam:
        print(f"[MERKEZ] PostgreSQL erisilemedi: {hata}")
        return 2
    mevcut = sema_surumu()
    if mevcut < BEKLENEN_SEMA:
        print(f"[MERKEZ] Sema {mevcut} -> {BEKLENEN_SEMA} guncelleniyor...")
        tamam, hata = sema_uygula()
        if not tamam:
            print(f"[MERKEZ] Sema guncellenemedi: {hata}")
            return 3
        print(f"[MERKEZ] Sema surumu: {sema_surumu()}")
    else:
        print(f"[MERKEZ] Sema surumu guncel: {mevcut}")

    silinen = kimlik.oturum_temizle()
    if silinen:
        print(f"[MERKEZ] Suresi gecmis {silinen} yonetici oturumu silindi")

    sunucu.ws_iplikte_baslat()
    time.sleep(0.6)  # röle döngüsü kurulsun

    http = sunucu.http_baslat(int(a["http_port"]), tls=False)
    https = sunucu.http_baslat(int(a["https_port"]), tls=True)
    if http is None and https is None:
        print("[MERKEZ] Hicbir HTTP dinleyicisi acilamadi")
        return 4

    kapan = {"istendi": False}

    def _kapat(imza, kare):  # noqa: ANN001
        kapan["istendi"] = True

    signal.signal(signal.SIGTERM, _kapat)
    signal.signal(signal.SIGINT, _kapat)
    print("[MERKEZ] Hazir.")
    try:
        while not kapan["istendi"]:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    print("[MERKEZ] Kapatiliyor...")
    for s in (http, https):
        if s:
            try:
                s.shutdown()
                s.server_close()
            except Exception:
                pass
    db.havuz_kapat()
    return 0


def main() -> int:
    arg = sys.argv[1:]
    if "--durum" in arg:
        return durum()
    if "--sema" in arg:
        tamam, hata = sema_uygula()
        print("Sema uygulandi" if tamam else f"Sema hatasi: {hata}")
        return 0 if tamam else 3
    if "--kurulum" in arg:
        def al(ad: str) -> str | None:
            if ad in arg:
                i = arg.index(ad)
                if i + 1 < len(arg):
                    return arg[i + 1]
            return None
        return kurulum(al("--eposta"), al("--sifre"), al("--ad") or "",
                       al("--unvan"))

    def sayi_al(ad: str) -> int | None:
        if ad in arg:
            i = arg.index(ad)
            if i + 1 < len(arg):
                try:
                    return int(arg[i + 1])
                except ValueError:
                    print(f"[MERKEZ] {ad} sayisal olmali")
        return None

    gecersiz: dict[str, int] = {}
    for secenek, anahtar in (("--http-port", "http_port"),
                             ("--https-port", "https_port"),
                             ("--ws-port", "ws_port")):
        d = sayi_al(secenek)
        if d is not None:
            gecersiz[anahtar] = d
    return servis(gecersiz)


if __name__ == "__main__":
    sys.exit(main())
