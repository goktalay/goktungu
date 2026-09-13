# -*- coding: utf-8 -*-
"""AI-SSH — BOS OMURGA (IS71: video/AI katmani sokuldu)

Isaret dizesi: FAZ19-IS71-OMURGA-AI-SSH

main.py:625-632 bu modulu try/except icinde ice alir:
    from goktungu.ai_ssh import AISSHYonetici, ssh_yolu
    ws_sunucu.ai_ssh = AISSHYonetici(konsol, duyuru_cb=...)

try/except korumali oldugu icin modul SILINEBILIRDI. Ancak silinirse
her aciliste except dalina duser ve gunluge yaniltici bir hata yazar.
Bos omurga daha temiz: hicbir SSH istemcisi baslatilmaz, gunluk temiz
kalir.

Omurgada:
  - hicbir SSH baglantisi kurulmaz
  - hicbir alt surec calistirilmaz
  - ssh_yolu() bos doner -> main.py "SSH istemcisi yok" dalina girer

Gercek surum arsivde: /opt/goktungu/arsiv/
"""

FAZ19_IS71_OMURGA_AI_SSH = True

KALDIRILDI_MESAJ = (
    "AI-SSH katmani bu surumde kaldirildi (IS71)."
)


def ssh_yolu():
    """Gercek surumde SSH istemci ikilisinin yolunu bulur.

    Omurgada bos doner; main.py bunu "istemci yok" olarak yorumlar
    ve kullaniciya dogru bilgi verir.
    """
    return ""


class AISSHYonetici:
    """Is yapmayan AI-SSH yoneticisi omurgasi."""

    def __init__(self, konsol=None, duyuru_cb=None, *a, **k):
        self.konsol = konsol
        self.duyuru_cb = duyuru_cb
        self.kaldirildi = True

    def baglan(self, *a, **k):
        return None

    def kapat(self, *a, **k):
        return None

    def komut(self, *a, **k):
        return None

    def durum(self, *a, **k):
        return {}

    def gecmis(self, *a, **k):
        return []

    def __getattr__(self, ad):
        if ad.startswith("__"):
            raise AttributeError(ad)

        def _bos(*a, **k):
            return None
        return _bos
