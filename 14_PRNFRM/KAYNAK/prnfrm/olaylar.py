"""Olay merkezi: durum geçişlerini olaya çevirir, abonelere dağıtır.

Aktif uyarı sistemi (e-posta, Telegram, sesli uyarı vb.) buraya abone olarak
eklenir; çekirdek kod değişmez.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from . import k2_protokol as P

log = logging.getLogger("prnfrm.olaylar")

# Olay türleri
O_BAGLANDI = "baglandi"
O_KOPTU = "koptu"
O_BASKI_BASLADI = "baski_basladi"
O_BASKI_BITTI = "baski_bitti"
O_DURAKLATILDI = "duraklatildi"
O_SURDURULDU = "surduruldu"
O_HATA = "hata"
O_HATA_GECTI = "hata_gecti"
O_FILAMENT_YOK = "filament_yok"
O_YAZICI_EKLENDI = "yazici_eklendi"
O_YAZICI_SILINDI = "yazici_silindi"

SEVIYE = {
    O_KOPTU: "uyari", O_HATA: "kritik", O_FILAMENT_YOK: "uyari",
    O_BASKI_BITTI: "basari",
}

Abone = Callable[[dict], Awaitable[None] | None]


class OlayMerkezi:
    def __init__(self) -> None:
        self._aboneler: list[Abone] = []

    def abone_ol(self, geri: Abone) -> None:
        self._aboneler.append(geri)

    def abonelikten_cik(self, geri: Abone) -> None:
        if geri in self._aboneler:
            self._aboneler.remove(geri)

    async def yayinla(self, olay: dict) -> None:
        for a in list(self._aboneler):
            try:
                r = a(olay)
                if asyncio.iscoroutine(r):
                    await r
            except Exception:  # noqa: BLE001
                log.exception("olay abonesi hata verdi")


def gecis_olaylari(ad: str, eski: dict | None, yeni: dict) -> list[tuple[str, str, dict]]:
    """İki özet arasındaki farklardan (tur, mesaj, veri) üçlüleri üretir."""
    olaylar: list[tuple[str, str, dict]] = []
    e_bag = (eski or {}).get("baglanti")
    y_bag = yeni.get("baglanti")
    if e_bag != y_bag and y_bag in ("bagli", "kopuk"):
        if y_bag == "bagli":
            olaylar.append((O_BAGLANDI, f"{ad}: bağlantı kuruldu", {}))
        elif e_bag == "bagli":
            olaylar.append((O_KOPTU, f"{ad}: bağlantı koptu", {"hata": yeni.get("son_hata", "")}))
    e_d = (eski or {}).get("durum")
    y_d = yeni.get("durum")
    # Henüz telemetri gelmemişken ya da çevrimdışıyken görülen "durum" gerçek bir
    # geçiş değildir: yeniden bağlanınca süren baskı "başladı" sayılmaz. Yalnız
    # hata bu kuralın dışındadır; bağlanır bağlanmaz bilinmelidir.
    gecis_gecerli = (e_d is not None and (eski or {}).get("veri_var", True)
                     and e_d != P.D_CEVRIMDISI)
    if e_d != y_d and (gecis_gecerli or (y_d == P.D_HATA and e_d is not None)):
        dosya = yeni.get("dosya") or ""
        if y_d == P.D_BASIYOR and e_d != P.D_DURAKLATILDI:
            olaylar.append((O_BASKI_BASLADI, f"{ad}: baskı başladı {dosya}".strip(), {"dosya": dosya}))
        elif y_d == P.D_BASIYOR and e_d == P.D_DURAKLATILDI:
            olaylar.append((O_SURDURULDU, f"{ad}: baskı sürdürüldü", {"dosya": dosya}))
        elif y_d == P.D_TAMAMLANDI:
            olaylar.append((O_BASKI_BITTI, f"{ad}: baskı tamamlandı {dosya}".strip(), {"dosya": dosya}))
        elif y_d == P.D_DURAKLATILDI:
            olaylar.append((O_DURAKLATILDI, f"{ad}: baskı duraklatıldı", {"dosya": dosya}))
        elif y_d == P.D_HATA:
            olaylar.append((O_HATA, f"{ad}: hata {yeni.get('hata_kodu')} {yeni.get('hata_anahtari', '')}".strip(),
                            {"kod": yeni.get("hata_kodu"), "anahtar": yeni.get("hata_anahtari")}))
        elif e_d == P.D_HATA and y_d != P.D_CEVRIMDISI:
            olaylar.append((O_HATA_GECTI, f"{ad}: hata giderildi", {}))
    if yeni.get("filament_yok") and not (eski or {}).get("filament_yok"):
        olaylar.append((O_FILAMENT_YOK, f"{ad}: filament bitti", {}))
    return olaylar
