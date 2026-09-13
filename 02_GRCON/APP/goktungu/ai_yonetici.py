# -*- coding: utf-8 -*-
"""AI YONETICI — BOS OMURGA (IS71: video/AI katmani sokuldu)

Isaret dizesi: FAZ19-IS71-OMURGA-AI-YONETICI

NEDEN BOS OMURGA, NEDEN SILINMEDI
----------------------------------
Olculdu: `goktungu/sunucu.py` (9500+ satir) icinde `self.ai_yonetici.*`
65 cagri var; bunlarin 42'si KORUMASIZ (getattr/None denetimi yok).
Modul silinseydi bu 42 nokta AttributeError firlatirdi ve sunucu.py'nin
komut yonlendiricisi coker, TELEMETRI/HARITA/ANGAJMAN dahil her sey
kirilirdi.

Bu yuzden modul SILINMEDI; ayni arayuze sahip ama IS YAPMAYAN bir
omurga ile degistirildi:
  - sunucu.py'ye hic dokunulmadi
  - agir bagimliliklar (OpenCV / torch / ffmpeg) YUKLENMEZ
  - hicbir surec, is parcacigi veya soket acilmaz
  - tum yontemler guvenli bos deger doner

Gercek surum arsivde: /opt/goktungu/arsiv/ (REHBER.md okunmali)
Yeni video/AI altyapisi kurulunca bu dosya gercek modulle degistirilir.

DONUS SOZLESMESI (cagri yerlerinden olculdu)
--------------------------------------------
  listele(firma_id=)        -> list   (sunucu.py:1435, 7529)
  izleme_listesi()          -> list   (sunucu.py:1044 icinde donguye girer)
  gecmis(...)               -> list   (sunucu.py:7967)
  ucus_tespitleri(...)      -> list   (sunucu.py:6298)
  sahibi_mi(...)            -> bool   (sunucu.py:7567, "not" ile kullanilir)
  kaydet(...)               -> list   (sunucu.py:7572, "liste =" atamasi)
  sil(...)                  -> list   (sunucu.py:7590)
  _sunucu_kaydi(id)         -> None   (sunucu.py:7548, 7618)
  embed_hesapla(foto)       -> None   (sunucu.py:7888)
  digerleri                 -> None
"""

FAZ19_IS71_OMURGA_AI_YONETICI = True
KALDIRILDI_MESAJ = (
    "Video/AI katmani bu surumde kaldirildi (IS71). "
    "Ayri altyapida yeniden kurgulanacak."
)


class AIYonetici:
    """Is yapmayan AI yonetici omurgasi.

    Tum yontemler cagrilabilir, hicbiri yan etki uretmez.
    """

    def __init__(self, konsol=None, ayarlar=None, *a, **k):
        self.konsol = konsol
        self.ayarlar = ayarlar
        # main.py bu uyeleri disaridan atar; onceden tanimli olmalari
        # AttributeError'u degil, sessiz calismayi saglar.
        self.ucus_gecmisi = None
        self.video_proxy = None
        self.kameralar = None
        self.duyuru_cb = None
        self._cek = None
        self._komut = None
        self.kaldirildi = True

    # --- yasam dongusu ------------------------------------------------
    def baslat(self, *a, **k):
        """Gercek surumde saglik yoklama + kalici gorev geri yukleme.
        Omurgada: hicbir is parcacigi baslatilmaz."""
        if self.konsol:
            try:
                self.konsol(KALDIRILDI_MESAJ)
            except BaseException:
                pass
        return None

    def durdur(self, *a, **k):
        return None

    # --- liste donenler -----------------------------------------------
    def listele(self, *a, **k):
        return []

    def izleme_listesi(self, *a, **k):
        return []

    def gecmis(self, *a, **k):
        return []

    def ucus_tespitleri(self, *a, **k):
        return []

    def kaydet(self, *a, **k):
        return []

    def sil(self, *a, **k):
        return []

    # --- bool donenler ------------------------------------------------
    def sahibi_mi(self, *a, **k):
        return False

    # --- None donenler ------------------------------------------------
    def _sunucu_kaydi(self, *a, **k):
        return None

    def embed_hesapla(self, *a, **k):
        return None

    def izleme_baslat(self, *a, **k):
        return None

    def izleme_durdur(self, *a, **k):
        return None

    def track_baslat(self, *a, **k):
        return None

    def track_durdur(self, *a, **k):
        return None

    def yuz_onbellek_sifirla(self, *a, **k):
        return None

    def tespit_kisi_ata(self, *a, **k):
        return None

    def tespit_arac_ata(self, *a, **k):
        return None

    def tespit_islenmis(self, *a, **k):
        return None

    def gorev_ata(self, *a, **k):
        return None

    def gorev_birak(self, *a, **k):
        return None

    def saglik_yokla(self, *a, **k):
        return None

    def __getattr__(self, ad):
        """Olculmemis bir yontem cagrilirsa da cokme olmasin.

        DIKKAT: yalniz `_` ile baslamayan ve bilinmeyen adlar icin
        calisir. Guvenli bir bos islev doner.
        """
        if ad.startswith("__"):
            raise AttributeError(ad)

        def _bos(*a, **k):
            return None
        return _bos
