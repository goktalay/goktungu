# -*- coding: utf-8 -*-
"""GÖKTUNGU KÖPRÜ AJANI — yerel sunucudan merkeze ters WebSocket bağlantısı.

Bu modül **saha tarafında** (kullanıcının kendi GCS/köprü sunucusunda)
çalışır ve merkeze (`goktungu.com`) bağlanır. Bağlantıyı hep
saha tarafı açar; merkez asla sahaya bağlanmaz. Böylece:

  * sahada açık port, sabit IP veya port yönlendirmesi gerekmez,
  * NAT/güvenlik duvarı arkasındaki kurulumlar da merkeze görünür,
  * merkez, açık soket üzerinden sahaya istek gönderebilir.

Ajan üç işi yürütür:

  1. **Kimlik**: `kurulum_uid` + `gizli` ile `merhaba` gönderir.
  2. **Nabız**: düzenli aralıkla `nabiz` yollar; merkez bu sunucuyu
     "açık" listesinde tutar (bağlantı yöneticisi bu listeyi gösterir).
  3. **İstek karşılama**: merkezin `istek` mesajlarını yerel işleyiciye
     verip `yanit` döner (dron listesi, port listesi, video parçası...).

Ayrıca uçuş ve video kayıtlarını merkeze senkronize eder.

Kullanım (GCS içinden):

    ajan = KopruAjani(yapilandirma, islevler)
    ajan.baslat()          # arka planda iş parçacığı

Tek başına deneme:

    python3 kopru_ajan.py --uid <kurulum_uid> --gizli <gizli> \
        --merkez wss://goktungu.com
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import platform
import socket
import ssl
import threading
import time
from typing import Any, Callable

VARSAYILAN_MERKEZ = "wss://goktungu.com"
NABIZ_ARALIK_SN = 25
YENIDEN_BAGLAN_TABAN = 3
YENIDEN_BAGLAN_ENUST = 60


class KopruAjani:
    """Merkeze kalıcı ters bağlantı tutan ajan."""

    def __init__(self, ayar: dict[str, Any],
                 islevler: dict[str, Callable[[dict], Any]] | None = None,
                 gunluk: Callable[[str], None] | None = None) -> None:
        self.ayar = ayar
        self.islevler = islevler or {}
        self.gunluk = gunluk or (lambda m: print(f"[KOPRU] {m}"))
        self._iplik: threading.Thread | None = None
        self._dur = threading.Event()
        self._dongu: asyncio.AbstractEventLoop | None = None
        self._soket: Any = None
        self.bagli = False
        self.kanal: str | None = None
        self.ornek_id: int | None = None
        self.son_hata: str | None = None
        self.baglanma_ts: float | None = None
        self._kuyruk: list[dict] = []      # bağlantı yokken bekleyen kayıtlar
        self._kuyruk_kilit = threading.Lock()

    # ------------------------------------------------------------------
    # Yaşam döngüsü
    # ------------------------------------------------------------------
    def yapilandirildi(self) -> bool:
        return bool(self.ayar.get("kurulum_uid") and self.ayar.get("gizli"))

    def baslat(self) -> bool:
        if not self.yapilandirildi():
            self.gunluk("Merkez kaydi yok; ajan baslatilmadi")
            return False
        if self._iplik and self._iplik.is_alive():
            return True
        self._dur.clear()
        self._iplik = threading.Thread(target=self._kos, name="kopru-ajan",
                                       daemon=True)
        self._iplik.start()
        return True

    def durdur(self) -> None:
        self._dur.set()
        if self._dongu and self._soket:
            with contextlib.suppress(Exception):
                asyncio.run_coroutine_threadsafe(self._soket.close(), self._dongu)

    def durum(self) -> dict[str, Any]:
        return {
            "yapilandirildi": self.yapilandirildi(),
            "bagli": self.bagli,
            "merkez": self.ayar.get("merkez") or VARSAYILAN_MERKEZ,
            "kurulum_uid": self.ayar.get("kurulum_uid"),
            "ornek_id": self.ornek_id,
            "kanal": self.kanal,
            "son_hata": self.son_hata,
            "bekleyen_kayit": len(self._kuyruk),
            "baglanma_ts": self.baglanma_ts,
        }

    def _kos(self) -> None:
        try:
            asyncio.run(self._dongu_kos())
        except Exception as e:
            self.son_hata = str(e)
            self.gunluk(f"Ajan durdu: {e}")

    async def _dongu_kos(self) -> None:
        self._dongu = asyncio.get_running_loop()
        gecikme = YENIDEN_BAGLAN_TABAN
        while not self._dur.is_set():
            try:
                await self._oturum()
                gecikme = YENIDEN_BAGLAN_TABAN
            except Exception as e:
                self.son_hata = f"{type(e).__name__}: {e}"
                self.gunluk(f"Baglanti kesildi ({self.son_hata}); "
                            f"{gecikme} sn sonra yeniden denenecek")
            finally:
                self.bagli = False
                self.kanal = None
            if self._dur.is_set():
                break
            await asyncio.sleep(gecikme)
            gecikme = min(gecikme * 2, YENIDEN_BAGLAN_ENUST)

    # ------------------------------------------------------------------
    # Tek oturum
    # ------------------------------------------------------------------
    def _ssl_baglami(self, adres: str) -> ssl.SSLContext | None:
        if not adres.startswith("wss://"):
            return None
        ctx = ssl.create_default_context()
        if self.ayar.get("sertifika_dogrulama") is False:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def _merhaba(self) -> dict[str, Any]:
        return {
            "tur": "merhaba",
            "kurulum_uid": self.ayar["kurulum_uid"],
            "gizli": self.ayar["gizli"],
            "surum": self.ayar.get("surum") or "",
            "platform": self.ayar.get("platform") or
                        f"{platform.system().lower()}-{platform.machine()}",
            "makine_adi": self.ayar.get("makine_adi") or socket.gethostname(),
            "yetenekler": self.ayar.get("yetenekler") or {},
            "dron_sayisi": self._dron_sayisi(),
        }

    def _dron_sayisi(self) -> int:
        f = self.islevler.get("dron_sayisi")
        if not f:
            return 0
        with contextlib.suppress(Exception):
            return int(f({}) or 0)
        return 0

    async def _oturum(self) -> None:
        import websockets

        adres = self.ayar.get("merkez") or VARSAYILAN_MERKEZ
        self.gunluk(f"Merkeze baglaniliyor: {adres}")
        async with websockets.connect(
            adres, ssl=self._ssl_baglami(adres), ping_interval=20,
            ping_timeout=20, max_size=32 * 1024 * 1024,
            open_timeout=20,
        ) as soket:
            self._soket = soket
            await soket.send(json.dumps(self._merhaba(), ensure_ascii=False))
            ilk = json.loads(await asyncio.wait_for(soket.recv(), timeout=20))
            if ilk.get("tur") != "merhaba_tamam":
                raise ConnectionError(ilk.get("mesaj") or "Merkez kabul etmedi")
            self.bagli = True
            self.son_hata = None
            self.kanal = ilk.get("kanal")
            self.ornek_id = ilk.get("ornek_id")
            self.baglanma_ts = time.time()
            self.gunluk(f"Merkeze baglandi: {ilk.get('ad')} "
                        f"(ornek {self.ornek_id}, kanal {self.kanal})")

            nabiz = asyncio.ensure_future(self._nabiz_dongusu(soket))
            kuyruk = asyncio.ensure_future(self._kuyruk_dongusu(soket))
            try:
                async for ham in soket:
                    with contextlib.suppress(Exception):
                        await self._mesaj_isle(soket, json.loads(ham))
            finally:
                for g in (nabiz, kuyruk):
                    g.cancel()
                    with contextlib.suppress(Exception, asyncio.CancelledError):
                        await g
                self._soket = None

    async def _nabiz_dongusu(self, soket) -> None:
        while True:
            await asyncio.sleep(NABIZ_ARALIK_SN)
            paket = {"tur": "nabiz", "dron_sayisi": self._dron_sayisi(),
                     "yetenekler": self.ayar.get("yetenekler") or {}}
            f = self.islevler.get("durum")
            if f:
                with contextlib.suppress(Exception):
                    ek = f({})
                    if isinstance(ek, dict):
                        paket.update(ek)
            await soket.send(json.dumps(paket, ensure_ascii=False))

    async def _kuyruk_dongusu(self, soket) -> None:
        """Bağlantı yokken biriken kayıtları merkeze aktarır."""
        while True:
            await asyncio.sleep(5)
            with self._kuyruk_kilit:
                if not self._kuyruk:
                    continue
                parti = self._kuyruk[:20]
            for paket in parti:
                await soket.send(json.dumps(paket, ensure_ascii=False))
            with self._kuyruk_kilit:
                self._kuyruk = self._kuyruk[len(parti):]

    async def _mesaj_isle(self, soket, m: dict) -> None:
        tur = m.get("tur")
        if tur == "istek":
            eylem = str(m.get("eylem") or "")
            islev = self.islevler.get(eylem)
            yanit: dict[str, Any] = {"tur": "yanit",
                                     "istek_id": m.get("istek_id")}
            if islev is None:
                yanit["hata"] = f"Bilinmeyen eylem: {eylem}"
            else:
                try:
                    sonuc = islev(m.get("veri") or {})
                    if asyncio.iscoroutine(sonuc):
                        sonuc = await sonuc
                    yanit["veri"] = sonuc if isinstance(sonuc, dict) \
                        else {"sonuc": sonuc}
                except Exception as e:
                    yanit["hata"] = f"{type(e).__name__}: {e}"
            await soket.send(json.dumps(yanit, ensure_ascii=False,
                                        default=str))
        elif tur == "kapat":
            self.gunluk("Merkez kapatma istedi")
            await soket.close()
        elif tur in ("nabiz_tamam", "ucus_tamam", "video_tamam",
                     "telemetri_tamam"):
            if m.get("hata"):
                self.gunluk(f"Merkez uyarisi ({tur}): {m['hata']}")

    # ------------------------------------------------------------------
    # Kayıt gönderimi (uçuş / video / telemetri)
    # ------------------------------------------------------------------
    def _gonder(self, paket: dict) -> bool:
        if self.bagli and self._soket and self._dongu:
            try:
                asyncio.run_coroutine_threadsafe(
                    self._soket.send(json.dumps(paket, ensure_ascii=False,
                                                default=str)),
                    self._dongu).result(timeout=10)
                return True
            except Exception as e:
                self.son_hata = str(e)
        with self._kuyruk_kilit:
            self._kuyruk.append(paket)
            if len(self._kuyruk) > 5000:      # bellek koruması
                self._kuyruk = self._kuyruk[-5000:]
        return False

    def ucus_gonder(self, veri: dict) -> bool:
        return self._gonder({"tur": "ucus", "veri": veri})

    def telemetri_gonder(self, ucus_uid: str, ornekler: list[dict]) -> bool:
        return self._gonder({"tur": "telemetri", "ucus_uid": ucus_uid,
                             "ornekler": ornekler})

    def video_gonder(self, veri: dict) -> bool:
        return self._gonder({"tur": "video", "veri": veri})


# ==========================================================================
# Tek başına deneme
# ==========================================================================
def _deneme() -> int:
    import argparse

    a = argparse.ArgumentParser(description="GÖKTUNGU köprü ajanı denemesi")
    a.add_argument("--uid", required=True)
    a.add_argument("--gizli", required=True)
    a.add_argument("--merkez", default=VARSAYILAN_MERKEZ)
    a.add_argument("--surum", default="2.4.52")
    a.add_argument("--dogrulamasiz", action="store_true",
                   help="TLS sertifikasını doğrulamaz (yalnız deneme)")
    a.add_argument("--sure", type=int, default=0,
                   help="kaç saniye sonra çıkılsın (0 = süresiz)")
    p = a.parse_args()

    ajan = KopruAjani(
        {"kurulum_uid": p.uid, "gizli": p.gizli, "merkez": p.merkez,
         "surum": p.surum, "sertifika_dogrulama": not p.dogrulamasiz,
         "yetenekler": {"dron": True, "video": True, "ai": False}},
        islevler={
            "dron_sayisi": lambda v: 2,
            "dron_liste": lambda v: {"dronlar": [
                {"uid": "SITL-1", "sysid": 1, "ad": "Sanal 1",
                 "arac_turu": "multirotor", "cevrimici": True},
                {"uid": "SITL-2", "sysid": 2, "ad": "Sanal 2",
                 "arac_turu": "sabit_kanat", "cevrimici": True},
            ]},
            "port_liste": lambda v: {"portlar": ["/dev/ttyACM0", "/dev/ttyUSB0"]},
            "servis_durum": lambda v: {"servis": "goktungu", "durum": "aktif"},
            "durum": lambda v: {"dron_sayisi": 2},
        })
    ajan.baslat()
    bas = time.time()
    try:
        while True:
            time.sleep(2)
            d = ajan.durum()
            print(f"bagli={d['bagli']} ornek={d['ornek_id']} "
                  f"kanal={d['kanal']} hata={d['son_hata']}")
            if p.sure and (time.time() - bas) > p.sure:
                break
    except KeyboardInterrupt:
        pass
    ajan.durdur()
    return 0


if __name__ == "__main__":
    raise SystemExit(_deneme())
