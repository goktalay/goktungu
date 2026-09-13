# -*- coding: utf-8 -*-
"""KullaniciYoneticisi: kullanicilari SQLite uzerinde yonetir.

Sifreler SHA-256 + tuz ile saklanir; eski duz metin sifreler ilk
basarili girisde otomatik olarak hashli bicime donusturulur.
"""
import json
import threading

from .sabitler import KULLANICI_DOSYASI
from .veritabani import (baglanti, tablolari_olustur,
                          ozet_zayif_mi,
                         sifre_hashle, sifre_dogrula)


def aktif_mi(deger):
    """'aktif' alanini tek bir dogruluk kuralina indirger (v2.4.64).

    Bu alan tarih icinde uc ayri bicimde tasindi: veritabani INTEGER
    0/1 tutar, arayuz JSON uzerinden true/false gonderir, eski JSON
    gocu ise "0"/"1" dizeleri uretebiliyordu. Her cagri yerinde ayri
    tip tahmini yapmak iki somut kusura yol acti:

      * JavaScript'te 0 === false DAIMA false verir; ham tamsayi
        arayuze gonderildiginde pasif kullanici ETKIN gorunur.
      * Python'da bool("0") True'dur; "0" dizesi 1 olarak yazilir ve
        pasiflestirme sessizce basarisiz olur.

    Bu yuzden donusum tek noktada toplanmistir. Dize degerlerde sayisal
    icerik once cozulur, boylece "0" dogru sekilde pasif sayilir.
    """
    if isinstance(deger, bool):
        return deger
    if deger is None:
        return True          # alan yoksa varsayilan etkin (DB DEFAULT 1)
    if isinstance(deger, (int, float)):
        return deger != 0
    metin = str(deger).strip().lower()
    if metin == "":
        return True          # bos deger "degistirme" anlamindadir
    if metin in ("0", "false", "hayir", "no", "pasif"):
        return False
    if metin in ("1", "true", "evet", "yes", "etkin", "aktif"):
        return True
    return True


class KullaniciYoneticisi:

    def __init__(self):
        tablolari_olustur()
        self._kilit = threading.Lock()
        self._json_goc()
        self._ilk_yonetici_guvence()

    def _ilk_yonetici_guvence(self):
        """DB'de hic kullanici yoksa KURULUM hesabi olusturur.

        OLCULEN KUSUR (2026-08-16) VE DUZELTMESI
        ========================================
        Bu yordam eskiden kaynak koda GOMULU sabit bir hesap
        yaratiyordu:

            eposta: mkaderoglu@gokkubbetech.com
            sifre : gokkubbe2026          <-- kaynakta SABIT

        Iki kusur birlikte olusuyordu:

        1. ISLEVSEL: Merkez Uygulama satin alan firma, kurumsal
           panelde tanimladigi sifre ile GIREMIYORDU; yerine bu
           gomulu sifre geciyordu. Kullanicinin bildirimi:
           "kullanici emaili dogru olmasina ragmen sifre benim
           merkezde verdigim sifre yerine gokkubbe2026 olmus".

        2. GUVENLIK: Her kurulumda AYNI bilinen sifre gecerliydi.
           5.000 USD'lik urun, kaynagi goren herkesin bildigi bir
           sifreyle aciliyordu. Internete acik bir kurulumda bu
           dogrudan yetkisiz erisim demekti.

        YENI DAVRANIS
        =============
        Hesap yine olusturulur (aksi halde temiz kurulumda sisteme
        hic girilemez), ancak sifre RASTGELE uretilir ve yalnizca
        kurulum konsoluna + `ilk_giris.txt` dosyasina yazilir.
        Boylece:
          - Sabit/bilinen sifre kalmaz.
          - Kurulumu yapan kisi sifreyi gorur.
          - Merkez lisansi varsa `merkez_esitle` bu hesabi gercek
            kurumsal hesaplarla degistirir (ayni e-posta ise
            UPDATE eder, sifre ozeti merkezden gelir).
        """
        import os
        import secrets

        with baglanti() as con:
            n = con.execute(
                "SELECT COUNT(*) FROM kullanicilar").fetchone()[0]
            if n > 0:
                return

        # 12 karakterlik, okunabilir rastgele sifre (kripto guvenli).
        # secrets.choice: rastgeleligin ongorulemez olmasi sart;
        # random modulu bu is icin UYGUN DEGILDIR.
        abece = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
        gecici = "".join(secrets.choice(abece) for _ in range(12))
        eposta = "kurulum@yerel"

        with baglanti() as con:
            con.execute(
                "INSERT INTO kullanicilar "
                "(eposta, ad_soyad, unvan, rol, sifre, avatar, aktif) "
                "VALUES (?,?,?,?,?,?,1)",
                (eposta, "Kurulum Yoneticisi", "Sistem Yoneticisi",
                 "yonetici", sifre_hashle(gecici), ""),
            )

        print("[AUTH] Hic kullanici yoktu; KURULUM hesabi olusturuldu.")
        print("[AUTH]   e-posta: %s" % eposta)
        print("[AUTH]   sifre  : %s" % gecici)
        print("[AUTH] Bu sifre RASTGELE uretildi ve bir daha "
              "gosterilmeyecek.")
        print("[AUTH] Merkez Uygulama lisansiniz varsa, kurumsal "
              "hesaplarinizi almak icin")
        print("[AUTH] arayuzde 'Merkez Kullanicilarini Esitle' "
              "adimini calistirin.")

        # Konsol kaydirilip kaybolabilir; sifreyi dosyaya da yaz.
        try:
            # OLCULDU: sabitler.py'de `VERI_DIZIN` YOKTUR;
            # gercek ad `VERI_KOKU` (satir 72/74, GOKTUNGU_VERI_KOKU
            # ortam degiskeniyle tasinabilir).
            from .sabitler import VERI_KOKU
            yol = os.path.join(VERI_KOKU, "ilk_giris.txt")
            with open(yol, "w", encoding="utf-8") as f:
                f.write("GOKTUNGU ilk giris bilgileri\n")
                f.write("e-posta: %s\n" % eposta)
                f.write("sifre  : %s\n" % gecici)
                f.write("\nBu dosyayi giris yaptiktan sonra SILIN.\n")
            try:
                os.chmod(yol, 0o600)   # yalniz sahibi okuyabilsin
            except OSError:
                pass                   # Windows'ta chmod etkisizdir
            print("[AUTH] Bilgiler ayrica yazildi: %s" % yol)
        except Exception as e:
            print("[AUTH] ilk_giris.txt yazilamadi: %s" % e)

    # ------------------------------------------------------------------
    # JSON → SQLite gocu (tek seferlik, tablo bossa calisir)
    # ------------------------------------------------------------------
    def _json_goc(self):
        """Mevcut kullanicilar.json varsa ve DB bossa icerisini aktarir."""
        import os
        with baglanti() as con:
            if con.execute(
                    "SELECT COUNT(*) FROM kullanicilar").fetchone()[0] > 0:
                return   # Zaten veri var
        if not os.path.isfile(KULLANICI_DOSYASI):
            return
        try:
            with open(KULLANICI_DOSYASI, "r", encoding="utf-8") as f:
                liste = json.load(f).get("kullanicilar", [])
        except Exception:
            return
        with baglanti() as con:
            for k in liste:
                eposta = (k.get("eposta") or "").strip().lower()
                if not eposta:
                    continue
                sifre = k.get("sifre", "")
                # Duz metin sifreleri hashle
                if sifre and not sifre.startswith("sha256:"):
                    sifre = sifre_hashle(sifre)
                con.execute(
                    "INSERT OR IGNORE INTO kullanicilar "
                    "(eposta, ad_soyad, unvan, rol, sifre, avatar, aktif) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (
                        eposta,
                        k.get("ad_soyad", ""),
                        k.get("unvan", ""),
                        k.get("rol", "kullanici"),
                        sifre,
                        k.get("avatar", ""),
                        1 if k.get("aktif", True) else 0,
                    ),
                )
        print(f"[AUTH] kullanicilar.json -> gcs.db aktarildi "
              f"({len(liste)} kayit, sifreler hashli).")

    # ------------------------------------------------------------------
    # Sorgular
    # ------------------------------------------------------------------
    def bul(self, eposta):
        """Kullaniciyi e-posta ile bulur; dict veya None dondurur."""
        eposta = (eposta or "").strip().lower()
        with baglanti() as con:
            row = con.execute(
                "SELECT * FROM kullanicilar WHERE eposta = ?",
                (eposta,)
            ).fetchone()
        return dict(row) if row else None

    def dogrula(self, eposta, sifre):
        """Basarili ise sifresiz kullanici bilgisini, degilse None dondurur.

        v2.4.64: pasiflik denetimi ortak aktif_mi() kuralindan gecer.
        Ham dogruluk sinamasi (not k.get("aktif")) "0" dizesini ETKIN
        sayardi; bu, guvenlik yonu yanlis olan bir sessiz basarisizliktir
        (pasiflestirilmis hesap giris yapabilir).
        """
        k = self.bul(eposta)
        if not k or not aktif_mi(k.get("aktif")):
            return None
        if not sifre_dogrula(sifre, k.get("sifre", "")):
            return None
        # ---- SIFRE YUKSELTME (v2.4.67'de DARALTILDI) ----
        #
        # OLCULEN KUSUR (2026-08-16):
        # Kosul eskiden `not startswith("sha256:")` idi. Merkezden
        # esitlenen ozetler `pbkdf2_sha256$...` bicimindedir ve bu
        # kosula TAKILIYORDU: ilk basarili girliste merkez ozeti
        # yerel `sha256:` bicimine EZILIYORDU.
        #
        # Sonuc (kullanicinin acik sarti ihlal ediliyordu):
        #   "merkezde ne verdiysem 5.000 dolarlik merkez yaziliminda
        #    da o sifre gecerli olmali"
        # Merkezde sifre degistiginde yerel kayit ESKI sifrede kalir;
        # `merkez_esitle` tekrar kosturulmadikca iki taraf ayrisir.
        #
        # KURAL (BULGU_08, 2026-08-17'de GENISLETILDI):
        # ------------------------------------------------------------------
        # Eski kosul `not startswith(("sha256:", "pbkdf2_sha256$"))` idi,
        # yani yalniz ONEKSIZ (duz metin) kayitlari yukseltiyordu. Duz
        # metin dali BULGU_08 ile `sifre_dogrula`dan KALDIRILDI — o
        # kayitlar artik giris yapamaz, dolayisiyla o kosul olu koddu.
        #
        # Gercek ihtiyac karsilanmiyordu: `sha256:` bicimi tek tur
        # SHA-256 kullanir, anahtar esnetmesi YOKTUR. Bu kayitlar
        # basarili girliste sessizce PBKDF2'ye yukseltilir.
        #
        # `pbkdf2_sha256$` ozetlerine DOKUNULMAZ (v2.4.67 dersi):
        # merkezden esitlenen ozet yerel bicime ezilirse kullanicinin
        # acik sarti ihlal edilir — "merkezde ne verdiysem 5.000
        # dolarlik merkez yaziliminda da o sifre gecerli olmali".
        # `ozet_zayif_mi` yalniz `sha256:` icin True doner.
        _ozet = k.get("sifre") or ""
        if ozet_zayif_mi(_ozet):
            self._sifre_yukselt(eposta, sifre)
        g = dict(k)
        g.pop("sifre", None)
        return g

    def _sifre_yukselt(self, eposta, sifre):
        """Duz metin sifre kaydi hashli bicime donusturur (gecis)."""
        yeni = sifre_hashle(sifre)
        with baglanti() as con:
            con.execute(
                "UPDATE kullanicilar SET sifre = ? WHERE eposta = ?",
                (yeni, eposta),
            )

    def ekle(self, eposta, ad_soyad="", unvan="", rol="kullanici",
             sifre="", avatar=""):
        """Yeni kullanici olusturur; (True, None) veya (False, hata)."""
        eposta = (eposta or "").strip().lower()
        if not eposta or "@" not in eposta:
            return False, "Gecerli bir e-posta girin."
        if not sifre:
            return False, "Sifre bos olamaz."
        with self._kilit:
            with baglanti() as con:
                var = con.execute(
                    "SELECT 1 FROM kullanicilar WHERE eposta = ?",
                    (eposta,)).fetchone()
                if var:
                    return False, "Bu e-posta zaten kayitli."
                gecerli_roller = {"yonetici", "kullanici"}
                try:
                    gecerli_roller |= {r["ad"].lower() for r in con.execute(
                        "SELECT ad FROM roller").fetchall()}
                except Exception:
                    pass
                if str(rol).lower() not in gecerli_roller:
                    rol = "kullanici"
                con.execute(
                    "INSERT INTO kullanicilar "
                    "(eposta, ad_soyad, unvan, rol, sifre, avatar, aktif) "
                    "VALUES (?,?,?,?,?,?,1)",
                    (eposta, ad_soyad or "", unvan or "", rol,
                     sifre_hashle(str(sifre)), avatar or ""),
                )
        return True, None

    def listesi_guvenli(self):
        """Sifreler haric tam liste (yonetici paneli icin).

        v2.4.64: 'aktif' alani BOOLEAN olarak dondurulur. Ham INTEGER
        gonderildiginde arayuzdeki 0 === false karsilastirmasi daima
        false verdigi icin pasif kullanici etkin gorunuyor ve
        etkinlestirme dugmesi ters calisiyordu. Tip donusumu burada,
        tek noktada yapilir.
        """
        with baglanti() as con:
            rows = con.execute(
                "SELECT eposta, ad_soyad, unvan, rol, avatar, aktif "
                "FROM kullanicilar ORDER BY ad_soyad"
            ).fetchall()
        liste = []
        for r in rows:
            k = dict(r)
            k["aktif"] = aktif_mi(k.get("aktif"))
            liste.append(k)
        return liste

    # ------------------------------------------------------------------
    # Guncelleme (yonetici paneli)
    # ------------------------------------------------------------------
    def guncelle(self, eposta, alanlar):
        """Verilen kullanicinin izinli alanlarini gunceller.
        Kullanici bulunduysa True, degilse False dondurur.
        """
        hedef = (eposta or "").strip().lower()
        izinli = {"rol", "aktif", "sifre", "ad_soyad", "unvan", "avatar"}
        with self._kilit:
            with baglanti() as con:
                mevcut = con.execute(
                    "SELECT eposta FROM kullanicilar WHERE eposta = ?",
                    (hedef,)
                ).fetchone()
                if not mevcut:
                    return False
                # v2.1.7b: gecerli roller dinamik (roller tablosu);
                # tablo bos/eksikse yerlesik ikili gecerli sayilir
                gecerli_roller = {"yonetici", "kullanici"}
                try:
                    gecerli_roller |= {r["ad"].lower() for r in con.execute(
                        "SELECT ad FROM roller").fetchall()}
                except Exception:
                    pass
                for alan, deger in (alanlar or {}).items():
                    if alan not in izinli or deger is None:
                        continue
                    # v2.3.3: avatar bos string ile silinebilir; diger
                    # alanlarda bos deger "degistirme" anlamina gelir
                    if deger == "" and alan != "avatar":
                        continue
                    if alan == "rol" and str(deger).lower() not in gecerli_roller:
                        continue
                    if alan == "aktif":
                        # v2.4.64: "0" dizesi bool("0") == True oldugu
                        # icin eskiden 1 yaziliyordu; ortak kural kullan
                        deger = 1 if aktif_mi(deger) else 0
                    elif alan == "sifre":
                        # Yeni sifre her zaman hashli kaydedilir
                        deger = sifre_hashle(str(deger))
                    con.execute(
                        f"UPDATE kullanicilar SET {alan} = ? WHERE eposta = ?",
                        (deger, hedef),
                    )
                return True
