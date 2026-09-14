# -*- coding: utf-8 -*-
"""GÖKTUNGU MERKEZ — M50 elektro-optik DOĞRUDAN (köprüsüz) modu.

`m50_vekil.py`'nin aksine bu modül HVS SDK'yı Merkez sürecinin İÇİNDE,
`m50_hvs.M50Istemcisi` üzerinden çağırır. Yalnız Merkez'in KENDİSİ
Windows x64 üzerinde çalışıyorsa ve `m50_sdk/` gömülü SDK kopyası
mevcutsa kullanılabilir; aksi halde `kullanilabilir()` False döner ve
çağıran yer (sunucu.py) otomatik olarak saha Köprüsü akışına düşer.

Bu, `kopru/servis_m50.py`'nin (saha Köprüsündeki eşdeğer sarmalayıcı)
Merkez tarafındaki ikizidir — aynı komut sözleşmesini (`durum`,
`ayar_oku`, `ayar_yaz`, `baglan`, `kes`, `ptz`, `lens`, `aci_konumla`,
`takip_sec`, `takip_baslat`, `takip_durdur`) uygular.

GÜVENLİK: kullanıcı adı/parola hiçbir zaman `ayarlar`a (kalıcı depoya)
yazılmaz; yalnız `baglan` çağrısı süresince RAM'de tutulur — tıpkı
saha Köprüsündeki davranış gibi. Kalıcı ayar yalnız üç açık anahtarla
sınırlıdır: `m50_sdk_dizin`, `rtsp_gorunur`, `rtsp_termal`.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict
from urllib.parse import urlparse

from .m50_hvs import M50Hata, M50Istemcisi

_AYAR_ANAHTARI = "m50_yerel"


class M50YerelServisi:
    """Merkez içinde çalışan, köprüsüz M50 komut yüzü."""

    def __init__(self, konsol, ayarlar):
        self._konsol = konsol
        self._ayarlar = ayarlar
        self._ayar_kilidi = threading.RLock()
        self._kullanilabilir_onbellek = None
        self._kullanilabilir_ts = 0.0
        self.istemci = M50Istemcisi(
            yaz=self._yaz, ayar_oku=self._ayar_oku, ayar_yaz=self._ayar_yaz_ic)

    # -----------------------------------------------------------------
    def _yaz(self, mesaj: str, seviye: str = "bilgi") -> None:
        try:
            self._konsol("M50", str(mesaj), seviye)
        except Exception:
            pass

    def kullanilabilir(self) -> bool:
        """Bu Merkez süreci M50 SDK'sını doğrudan çalıştırabilir mi?

        10 sn önbelleklenir: her `_m50_kopruye` çağrısında dosya sistemi
        ve platform denetimi tekrar etmesin diye.
        """
        simdi = time.time()
        if (self._kullanilabilir_onbellek is not None and
                simdi - self._kullanilabilir_ts < 10.0):
            return self._kullanilabilir_onbellek
        try:
            M50Istemcisi._sdk_kok(self._ayar_oku())
            sonuc = True
        except Exception:
            sonuc = False
        self._kullanilabilir_onbellek = sonuc
        self._kullanilabilir_ts = simdi
        return sonuc

    # -----------------------------------------------------------------
    # Kalıcı ayar — YALNIZ m50_sdk_dizin / rtsp_gorunur / rtsp_termal.
    # Parola/kullanıcı adı BURADAN ASLA GEÇMEZ.
    # -----------------------------------------------------------------
    @staticmethod
    def _metin(deger: Any, ad: str, en_cok: int = 512) -> str:
        sonuc = str(deger or "").strip()
        if "\x00" in sonuc or len(sonuc) > en_cok:
            raise ValueError("%s geçersiz" % ad)
        return sonuc

    @classmethod
    def _rtsp_uri(cls, deger: Any, ad: str) -> str:
        uri = cls._metin(deger, ad)
        if not uri:
            return ""
        ayrik = urlparse(uri)
        if ayrik.scheme.lower() not in ("rtsp", "rtsps") or not ayrik.hostname:
            raise ValueError(
                "%s yalnız geçerli rtsp:// veya rtsps:// URI'si olmalıdır" % ad)
        if (ayrik.username is not None or ayrik.password is not None or
                ayrik.query or ayrik.fragment):
            raise ValueError(
                "%s gömülü kimlik bilgisi veya oturum parametresi içeremez" % ad)
        return uri

    @classmethod
    def _ayar_filtrele(cls, veri: Dict[str, Any]) -> Dict[str, Any]:
        sonuc: Dict[str, Any] = {}
        if "m50_sdk_dizin" in veri:
            sonuc["m50_sdk_dizin"] = cls._metin(veri.get("m50_sdk_dizin"),
                                                "m50_sdk_dizin")
        for anahtar in ("rtsp_gorunur", "rtsp_termal"):
            if anahtar in veri:
                sonuc[anahtar] = cls._rtsp_uri(veri.get(anahtar), anahtar)
        return sonuc

    def _ayar_oku(self) -> Dict[str, Any]:
        with self._ayar_kilidi:
            try:
                tumu = self._ayarlar.yukle()
            except Exception:
                return {}
            deger = tumu.get(_AYAR_ANAHTARI)
            return dict(deger) if isinstance(deger, dict) else {}

    def _ayar_yaz_ic(self, veri: Dict[str, Any]) -> None:
        if not isinstance(veri, dict):
            return
        yeni = self._ayar_filtrele(veri)
        with self._ayar_kilidi:
            mevcut = self._ayar_oku()
            for anahtar, deger in yeni.items():
                if deger:
                    mevcut[anahtar] = deger
                else:
                    mevcut.pop(anahtar, None)
            try:
                self._ayarlar.kaydet({_AYAR_ANAHTARI: mevcut})
            except Exception as exc:
                self._yaz("M50 ayarları yazılamadı: %s" % exc, "uyari")

    # -----------------------------------------------------------------
    # Komut sözleşmesi — kopru/servis_m50.py._komut_uygula ile aynı şekil.
    # -----------------------------------------------------------------
    def uygula(self, eylem: str, veri: Dict[str, Any]) -> Dict[str, Any]:
        veri = veri if isinstance(veri, dict) else {}
        if eylem == "durum":
            pass
        elif eylem == "ayar_oku":
            pass
        elif eylem == "ayar_yaz":
            self._ayar_yaz_ic(veri)
        elif eylem == "baglan":
            self.istemci.baglan(veri)
        elif eylem == "kes":
            self.istemci.kes()
        elif eylem == "ptz":
            self.istemci.ptz(veri.get("yon"), veri.get("hiz"),
                             veri.get("basili", True))
        elif eylem == "lens":
            self.istemci.lens(veri.get("eylem"), veri.get("kanal"),
                              veri.get("basili", True))
        elif eylem == "aci_konumla":
            self.istemci.aci_konumla(veri.get("azimut"), veri.get("egim"),
                                     veri.get("hiz"))
        elif eylem == "takip_sec":
            self.istemci.takip_sec(veri.get("kanal"),
                                   veri.get("video_dikdortgen"),
                                   veri.get("secim"))
        elif eylem == "takip_baslat":
            self.istemci.takip_baslat(veri.get("kanal"), veri.get("mod"))
        elif eylem == "takip_durdur":
            self.istemci.takip_durdur(veri.get("kanal"))
        else:
            raise M50Hata("bilinmeyen M50 eylemi: %s" % eylem)
        return self._durum_paketi()

    def _durum_paketi(self) -> Dict[str, Any]:
        durum = self.istemci.durum()
        ayarlar = self._ayar_oku()
        video = dict(durum.get("video") or {})
        video["rtsp_gorunur"] = ayarlar.get("rtsp_gorunur", "")
        video["rtsp_termal"] = ayarlar.get("rtsp_termal", "")
        return {
            "m50_durum": durum,
            "m50_ayarlar": ayarlar,
            "m50_video": video,
            "m50_takip": dict(durum.get("takip") or {}),
        }
