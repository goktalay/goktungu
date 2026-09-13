# -*- coding: utf-8 -*-
"""MERKEZ VIDEO KOPRULEYICI — BOS OMURGA (IS71)

Isaret dizesi: FAZ19-IS71-OMURGA-MK-VIDEO

NEDEN BOS OMURGA
----------------
`mk_sunucu.py:44` -> `import mk_video as video`
Kullanim noktalari (olculdu):
  3802: video.VIDEO.kanal_ac(oid, kid, app_port)   -> (ozet, hata)
  3809: video.VIDEO.kanal_kapat(oid, kid)
  3837: vardi = video.VIDEO.kanal_kapat(oid, kid)  -> bool
  3854: video.VIDEO.durum(oid)                     -> dict
  4359: video.VIDEO.kopruden_geldi(...)
  4393: nv = video.VIDEO.ornek_kapat(o.ornek_id)   -> sayi

Modul silinseydi mk_sunucu.py ImportError verir ve MERKEZ HIC
ACILMAZDI (443/80 portlari dusürdü).

Omurgada:
  - hicbir UDP soketi acilmaz
  - hicbir kanal tahsis edilmez
  - kopruden gelen video kareleri sessizce atilir
  - donus sozlesmesi cagri yerlerine gore korunur

Gercek surum arsivde: /opt/goktungu/arsiv/
"""

FAZ19_IS71_OMURGA_MK_VIDEO = True

# Gercek surumdeki sabitler korunur (baska yerler okuyabilir)
YEREL_ADRES = "127.0.0.1"
GENEL_ENUST_KANAL = 0          # 0 = kanal tahsisi yok
ORNEK_BASINA_ENUST_KANAL = 0
TERK_ZAMAN_ASIMI_SN = 60.0
KARE_ENUST_BYTE = 63 * 1024

KALDIRILDI_MESAJ = (
    "Video katmani bu surumde kaldirildi (IS71). "
    "Ayri altyapida yeniden kurgulanacak."
)


class VideoKanali:
    """Gercek surumdeki kanal nesnesinin bos karsiligi."""

    def __init__(self, *a, **k):
        self.kaldirildi = True
        self.acik = False

    def kapat(self, *a, **k):
        return None


class VideoKopruleyici:
    """Is yapmayan video kopruleyici omurgasi."""

    def __init__(self, *a, **k):
        self.kaldirildi = True
        self.kanallar = {}

    def kanal_ac(self, ornek_id=None, kamera_id=None, app_port=None,
                 *a, **k):
        """mk_sunucu.py:3802 -> `ozet, hata = ...`

        Iki degerli demet DONMELI, yoksa acma hatasi olur.
        Omurga: (None, mesaj) doner -> cagiran taraf duzgun hata verir.
        """
        return None, KALDIRILDI_MESAJ

    def kanal_kapat(self, ornek_id=None, kamera_id=None, *a, **k):
        """mk_sunucu.py:3837 -> `vardi = ...` (bool beklenir)"""
        return False

    def durum(self, ornek_id=None, *a, **k):
        """mk_sunucu.py:3854 -> yanit sozlugune konur (dict beklenir)"""
        return {}

    def kopruden_geldi(self, *a, **k):
        """mk_sunucu.py:4359 — kopruden gelen video karesi.
        Omurga: sessizce atilir."""
        return None

    def ornek_kapat(self, ornek_id=None, *a, **k):
        """mk_sunucu.py:4393 -> `nv = ...` (kapatilan kanal sayisi)"""
        return 0

    def temizle(self, *a, **k):
        return None

    def __getattr__(self, ad):
        if ad.startswith("__"):
            raise AttributeError(ad)

        def _bos(*a, **k):
            return None
        return _bos


VIDEO = VideoKopruleyici()
