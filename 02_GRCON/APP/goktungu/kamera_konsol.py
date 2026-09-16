# -*- coding: utf-8 -*-
"""GÖKTUNGU — KAMERA BAŞINA HABERLEŞME KONSOLU (v2.4.189).

Dron panelindeki `dron.py` haberleşme konsolunun kamera eşleniği:
kamera yönetiminde her kameranın satırının altında açılır-kapanır bir
konsol vardır; o kameraya ait VIDEO/KAMERA/AI/M50 satırları YALNIZ
oraya düşer (genel konsolda da kalır — bu bir kopyadır, süzgeç değil).

Satırlar genel `KonsolLog.log()` üzerinden gelir: her genel konsol
satırı `konsoldan()` ile buraya uğrar, metinden kamera numarası
çıkarılabiliyorsa (`(kamera 3)`, `Kamera #3`, `kam=3`, `kamera 3`)
o kameranın tamponuna yazılır. M50 satırları numara taşımaz; `M50`
kaynağı için kayıtlı M50 kamerası bulunur.

Tampon dron.py ile aynı kurallara sahiptir: kamera başına 200 satır,
ardışık aynı metin yeni satır yerine `tekrar` sayacı, arayüze
`kanca(kamera_id, kayit)` ile anlık iletim.
"""
from __future__ import annotations

import re
import threading
import time

KONSOL_LIMIT = 200

_DESENLER = (
    re.compile(r"\(kamera\s+(\d+)\)", re.IGNORECASE),
    re.compile(r"\bkamera\s*#\s*(\d+)", re.IGNORECASE),
    re.compile(r"\bkam\s*=\s*(\d+)", re.IGNORECASE),
    re.compile(r"\bkamera\s+(\d+)\b", re.IGNORECASE),
    re.compile(r"\bkamera\s*:\s*(\d+)\b", re.IGNORECASE),
)
_KAYNAKLAR = frozenset(("KAMERA", "VIDEO", "AI", "M50", "TAKIP", "ANGAJMAN"))


def kamera_id_bul(mesaj):
    """Metinden kamera numarasını çıkarır; yoksa None."""
    m = str(mesaj or "")
    for d in _DESENLER:
        e = d.search(m)
        if e:
            try:
                return int(e.group(1))
            except (TypeError, ValueError):
                continue
    return None


class KameraKonsol:
    def __init__(self, m50_kamera_id_bul=None):
        self._tampon = {}
        self._kilit = threading.Lock()
        self.kanca = None
        self._m50_bul = m50_kamera_id_bul

    def konsoldan(self, kaynak, mesaj, seviye="bilgi"):
        """Genel konsol satırından kamera satırı türetir (KonsolLog kancası)."""
        k = str(kaynak or "").strip().upper()
        if k not in _KAYNAKLAR:
            return
        kid = kamera_id_bul(mesaj)
        if kid is None and k == "M50" and callable(self._m50_bul):
            try:
                kid = self._m50_bul()
            except Exception:
                kid = None
        if kid is None:
            return
        # Genel konsolda "[VIDEO] ..." önekiyle yazılan satırların
        # kaynağı KAMERA'dır; etiket olarak köşeli önek alınır.
        m = str(mesaj or "")
        etiket = k
        e = re.match(r"^\[([A-Z0-9_]+)\]\s*", m)
        if e:
            etiket = e.group(1)
            m = m[e.end():]
        self.ekle(kid, etiket, m, seviye)

    def ekle(self, kamera_id, etiket, metin, sev="bilgi"):
        try:
            kid = int(kamera_id)
        except (TypeError, ValueError):
            return
        kayit = {"ts": time.time(), "etiket": str(etiket),
                 "metin": str(metin), "sev": str(sev)}
        yeni = True
        with self._kilit:
            liste = self._tampon.setdefault(kid, [])
            if (liste and liste[-1]["metin"] == kayit["metin"]
                    and liste[-1]["etiket"] == kayit["etiket"]):
                liste[-1]["ts"] = kayit["ts"]
                liste[-1]["tekrar"] = liste[-1].get("tekrar", 1) + 1
                kayit = dict(liste[-1])
                yeni = False
            else:
                liste.append(kayit)
                if len(liste) > KONSOL_LIMIT:
                    del liste[:len(liste) - KONSOL_LIMIT]
            kayit = dict(kayit)
        kayit["yeni"] = yeni
        kanca = self.kanca
        if callable(kanca):
            try:
                kanca(kid, kayit)
            except Exception:
                pass

    def gecmis(self, kamera_id, adet=None):
        try:
            kid = int(kamera_id)
        except (TypeError, ValueError):
            return []
        with self._kilit:
            liste = list(self._tampon.get(kid, []))
        if adet:
            liste = liste[-int(adet):]
        return liste

    def temizle(self, kamera_id):
        try:
            kid = int(kamera_id)
        except (TypeError, ValueError):
            return
        with self._kilit:
            self._tampon.pop(kid, None)
