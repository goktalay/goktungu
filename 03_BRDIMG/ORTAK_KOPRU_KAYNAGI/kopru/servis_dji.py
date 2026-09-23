# -*- coding: utf-8 -*-
"""GÖKTUNGU KÖPRÜ — DJI DRON SERVİSİ (Faz 5 DJI kısmı).

DJI dronları, ArduPilot/Betaflight (bkz. `servis_dron.py`) yolundan
BAĞIMSIZ, kapalı kaynak native SDK'larla konuşur:

  * DJI Onboard SDK (OSDK) — dron üzerindeki yardımcı bilgisayarda çalışan
    C++ kütüphanesi. GÖKTUNGU tarafında native `goktungu_osdk_kopru`
    yardımcısı OSDK Telemetry/FlightController API'lerini GDP (NDJSON)
    mesajlarına çevirir.
  * DJI Windows SDK (MSDK/Windows) — yalnız Windows x64 ikilisi olarak
    dağıtılır. Bu servis ileride M50'nin Wine köprüsü (`m50_wine.py`)
    emsali gibi bir yardımcıyla bağlanacaktır; ŞİMDİ yalnız placeholder
    (aşağıya bakın).

## KAPALI VARSAYILAN (M50 gibi)

Servis, açık bir `dji_baslat` komutu gelmeden HİÇBİR kanala bağlanmaz;
kör başlatma yoktur. Uygulama kimliği (app id/key/lisans) köprü veri
kökündeki `dji_ayar.json` dosyasından okunur (env
`GOKTUNGU_KOPRU_VERI_DIZIN`, `m50_ayar.json` deseniyle aynı). Anahtar
İÇERİĞİ bu serviste OKUNMAZ/GÜNLÜĞE YAZILMAZ; yalnız native OSDK
yardımcısına ortam değişkeniyle aktarılır (bkz. `dji_osdk.OsdkYardimci`).

## DONANIMSIZ / YARDIMCI YOK DAVRANIŞI (çökme YOK)

`dji_baslat` sırasında:
  1. Native `goktungu_osdk_kopru` yardımcısı config'te/PATH'te varsa alt
     süreç olarak başlatılır ve `OsdkKanal` ona bağlanır (kip="osdk").
  2. Yardımcı yok ama benzetim istendiyse (`sim`) `SimKanal` ile
     donanımsız uçtan uca akış kurulur (kip="sim").
  3. İkisi de yoksa servis "OSDK yardımcısı bekleniyor" durumuna düşer
     (kip="bekliyor"); çökmez, sonraki komutta yeniden denenir.

Kanal ne olursa olsun `OsdkAdaptor` GDP'yi yerel Merkez / role kanalına
(gcs_adres:gcs_port, varsayılan 127.0.0.1:8790) iletir; Android DJI
köprüsüyle aynı protokol. Native yardımcı geldiğinde kod yolu aynıdır.

## WINDOWS SDK — PLACEHOLDER (henüz yok)

DJI Windows SDK ikilisi bu ortamda YOKTUR ve yazılamaz. İleride
`m50_wine.py` emsali bir "dji_windows" yardımcısı (Wine altında Windows
Python veya native Windows süreci) eklenip protokol soyutlamasına
`dji_windows` kipi olarak bağlanacaktır. Şimdilik `dji_baslat`
`kip="windows"` istemi "Windows SDK bekleniyor" ile reddedilir.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from typing import Any, Dict

from . import dji_osdk
from .servis_kanal import ServisKanali
from .servis_temel import Servis, calistir

DONGU_SN = 0.25
DURUM_YAZIM_SN = 0.5

# Kalıcı ayarda izin verilen anahtarlar. `app_key`/`lisans` GİZLİDİR:
# duruma/yanıta HİÇBİR ZAMAN düz aktarılmaz (yalnız var/yok bildirilir).
GIZLI_ANAHTARLAR = ("app_key", "lisans")
METIN_ANAHTARLAR = ("app_id", "osdk_yardimci", "osdk_soket",
                    "gcs_adres", "video_url")


class DjiServisi(Servis):
    """DJI OSDK/Windows SDK'nın Köprüdeki kapalı-varsayılan hizmet yüzü."""

    ad = "dji"
    baslik = "DJI Dron Servisi"

    # Güvenli varsayılanlar (servis doğrudan sınav/teşhis için de
    # AttributeError vermeden kullanılabilmeli).
    kanal = None

    def hazirla(self):
        self.kanal = ServisKanali()
        self._kilit = threading.RLock()
        self._ayar_yolu = self._ayar_yolu_bul()
        self._ayarlar: Dict[str, Any] = {}
        self._ayar_yukle()
        # Etkin bağlantı bileşenleri (yalnız dji_baslat sonrası dolar).
        self._adaptor = None            # dji_osdk.OsdkAdaptor
        self._yardimci = None           # dji_osdk.OsdkYardimci
        self._kip = "kapali"            # kapali/osdk/sim/bekliyor
        self._son_hata = ""
        self._son_durum_yazim = 0.0
        self.yaz("DJI dron hizmeti hazır (kapalı varsayılan); açık "
                 "başlatma komutu bekleniyor")
        if not self.kanal.etkin():
            self.yaz("Panel komut kanalı etkin değil; DJI yerel olarak "
                     "kapalı bekleyecek", "uyari")
        if not os.path.exists(self._ayar_yolu):
            self.yaz("DJI anahtar dosyası yok (%s); app id/key/lisans "
                     "yapılandırılınca OSDK yardımcısı kullanılabilir."
                     % os.path.basename(self._ayar_yolu), "uyari")

    # ------------------------------------------------------------------
    # Config / anahtar okuma — M50'nin m50_ayar.json deseni
    # ------------------------------------------------------------------
    def _ayar_yolu_bul(self) -> str:
        dizin = (os.environ.get("GOKTUNGU_KOPRU_VERI_DIZIN") or
                 os.environ.get("GOKTUNGU_KOPRU_KANAL_DIZIN") or "")
        if not dizin:
            durum = os.environ.get("GOKTUNGU_KOPRU_DURUM_DOSYASI") or ""
            dizin = os.path.dirname(durum) if durum else ""
        if not dizin:
            dizin = os.path.join(os.path.expanduser("~"), ".goktungu_kopru")
        os.makedirs(dizin, exist_ok=True)
        return os.path.join(dizin, "dji_ayar.json")

    def _ayar_yukle(self) -> None:
        try:
            with open(self._ayar_yolu, "r", encoding="utf-8") as f:
                veri = json.load(f)
            if isinstance(veri, dict):
                self._ayarlar = self._ayar_filtrele(veri)
        except (OSError, ValueError, TypeError):
            self._ayarlar = {}

    @staticmethod
    def _metin(deger: Any, ad: str, en_cok: int = 1024) -> str:
        sonuc = str(deger or "").strip()
        if "\x00" in sonuc or len(sonuc) > en_cok:
            raise ValueError("%s geçersiz" % ad)
        return sonuc

    @classmethod
    def _ayar_filtrele(cls, veri: Dict[str, Any]) -> Dict[str, Any]:
        """Kalıcı ayarı izin listesiyle daraltır.

        Gizli anahtarlar (`app_key`, `lisans`) İÇERİĞİ İNCELENMEDEN
        (yalnız düz metin doğrulamasıyla) korunur; servis bunları
        kullanmaz, yalnız native yardımcıya aktarır.
        """
        sonuc: Dict[str, Any] = {}
        for anahtar in METIN_ANAHTARLAR + GIZLI_ANAHTARLAR:
            if anahtar in veri:
                sonuc[anahtar] = cls._metin(veri.get(anahtar), anahtar)
        if "gcs_port" in veri:
            try:
                sonuc["gcs_port"] = int(veri.get("gcs_port"))
            except (TypeError, ValueError):
                pass
        if "sim" in veri:
            sonuc["sim"] = bool(veri.get("sim"))
        if isinstance(veri.get("osdk_ek_arg"), list):
            sonuc["osdk_ek_arg"] = [str(x) for x in veri["osdk_ek_arg"]]
        return sonuc

    def _ayar_oku_ic(self) -> Dict[str, Any]:
        """Tam config (gizli dahil) — YALNIZ native yardımcıya geçmek için."""
        with self._kilit:
            return dict(self._ayarlar)

    def _ayar_oku_disa(self) -> Dict[str, Any]:
        """Panele/merkeze gösterilebilir config — gizli anahtarlar MASKELİ."""
        with self._kilit:
            a = dict(self._ayarlar)
        for anahtar in GIZLI_ANAHTARLAR:
            var = bool(a.pop(anahtar, ""))
            a[anahtar + "_var"] = var
        a.setdefault("gcs_adres", dji_osdk.VARSAYILAN_GDP_ADRES)
        a.setdefault("gcs_port", dji_osdk.VARSAYILAN_GDP_PORT)
        return a

    def _ayar_yaz(self, veri: Dict[str, Any]) -> None:
        yeni = self._ayar_filtrele(veri)
        with self._kilit:
            for anahtar, deger in yeni.items():
                # Boş metin = ilgili anahtarı KALDIR (operatör kaldırmak
                # istiyor). sim/gcs_port gibi metin olmayanlar aynen yazılır.
                if isinstance(deger, str) and not deger:
                    self._ayarlar.pop(anahtar, None)
                else:
                    self._ayarlar[anahtar] = deger
            kayit = dict(self._ayarlar)
        self._diske_yaz(kayit)

    def _diske_yaz(self, kayit: Dict[str, Any]) -> None:
        gecici = None
        try:
            dizin = os.path.dirname(self._ayar_yolu) or "."
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=dizin,
                                             delete=False, prefix=".dji_",
                                             suffix=".tmp") as f:
                gecici = f.name
                json.dump(kayit, f, ensure_ascii=False, separators=(",", ":"))
                f.flush()
                os.fsync(f.fileno())
            os.replace(gecici, self._ayar_yolu)
            try:
                os.chmod(self._ayar_yolu, 0o600)   # gizli anahtar tutar
            except OSError:
                pass
        except OSError as exc:
            if gecici:
                try:
                    os.unlink(gecici)
                except OSError:
                    pass
            self.yaz("DJI ayarları yazılamadı: %s" % exc, "uyari")

    # ------------------------------------------------------------------
    # Servis döngüsü
    # ------------------------------------------------------------------
    def dongu(self):
        while not self.durdur_istendi():
            self._komutlari_isle()
            simdi = time.time()
            if simdi - self._son_durum_yazim >= DURUM_YAZIM_SN:
                self._son_durum_yazim = simdi
                self.durum_yaz(**self._durum_paketi())
            self.bekle(DONGU_SN)

    def _komutlari_isle(self) -> None:
        if not self.kanal.etkin():
            return
        for komut in self.kanal.oku():
            kimlik = komut.get("id")
            eylem = str(komut.get("eylem") or "").strip().lower()
            veri = komut.get("veri") if isinstance(komut.get("veri"), dict) else {}
            try:
                sonuc = self._komut_uygula(eylem, veri)
                self.kanal.yanit(kimlik, True, "", sonuc)
            except (ValueError, TypeError) as exc:
                self.yaz("DJI komut hatası (%s): %s" % (eylem, exc), "hata")
                self.kanal.yanit(kimlik, False, str(exc))
            except Exception as exc:  # SDK/soket hatası hizmeti düşürmez
                self.yaz("DJI beklenmeyen komut hatası (%s): %s"
                         % (eylem, exc), "hata")
                self.kanal.yanit(kimlik, False, "DJI komutu uygulanamadı")

    def _komut_uygula(self, eylem: str, veri: Dict[str, Any]) -> Dict[str, Any]:
        if eylem in ("durum", "dji_durum"):
            return self._durum_paketi()
        if eylem == "ayar_oku":
            return {"ayarlar": self._ayar_oku_disa()}
        if eylem == "ayar_yaz":
            self._ayar_yaz(veri)
            return {"ayarlar": self._ayar_oku_disa()}
        if eylem == "dji_baslat":
            return self._baglanti_baslat(veri)
        if eylem == "dji_durdur":
            return self._baglanti_durdur()
        raise ValueError("bilinmeyen DJI eylemi: %s" % eylem)

    # ------------------------------------------------------------------
    # Bağlantı yaşam döngüsü
    # ------------------------------------------------------------------
    def _baglanti_baslat(self, veri: Dict[str, Any]) -> Dict[str, Any]:
        with self._kilit:
            if self._adaptor is not None:
                # Zaten çalışıyor: yeniden başlatmadan durum döndür.
                return self._durum_paketi()
            cfg = dict(self._ayarlar)

        # Bağlantı parametreleri config'ten gelir; komut (veri) geçersiz
        # kılabilir. Role kanalı durumunda ajan, GDP UDP portunu komutla
        # bildirir (native yardımcı GDP ucunu bilmez, servis köprüler).
        for anahtar in ("gcs_adres", "gcs_port", "video_url"):
            if veri.get(anahtar) not in (None, ""):
                cfg[anahtar] = veri[anahtar]

        istek_kip = str(veri.get("kip") or "").strip().lower()
        sim_iste = bool(veri.get("sim")) or bool(cfg.get("sim")) \
            or istek_kip == "sim"

        # Windows SDK henüz yok — placeholder.
        if istek_kip in ("windows", "dji_windows"):
            self._son_hata = "Windows SDK bekleniyor (henüz eklenmedi)"
            self._kip = "bekliyor"
            self.yaz(self._son_hata, "uyari")
            return self._durum_paketi()

        gcs_adres = str(cfg.get("gcs_adres") or dji_osdk.VARSAYILAN_GDP_ADRES)
        gcs_port = int(cfg.get("gcs_port") or dji_osdk.VARSAYILAN_GDP_PORT)
        video_url = str(cfg.get("video_url") or "")
        _yaz = lambda m, s="bilgi": self.yaz("[DJI] %s" % m, s)  # noqa: E731

        kanal = None
        yardimci = None
        # 1) Native OSDK yardımcısı (config/PATH). İstek açıkça sim değilse.
        if not sim_iste and dji_osdk.OsdkYardimci.kullanilabilir(cfg):
            yardimci = dji_osdk.OsdkYardimci(cfg, yaz=_yaz)
            hata = yardimci.baslat()
            if hata:
                self._son_hata = hata
                self.yaz("OSDK yardımcısı başlatılamadı: %s" % hata, "uyari")
                yardimci = None
            else:
                kanal = dji_osdk.OsdkKanal(yardimci.soket_yolu, yaz=_yaz)
                self._kip = "osdk"
        # 2) Benzetim (donanımsız uçtan uca).
        if kanal is None and sim_iste:
            kanal = dji_osdk.SimKanal()
            self._kip = "sim"
            self.yaz("OSDK donanımı yok; benzetim (SimKanal) kipinde "
                     "çalışılıyor", "uyari")
        # 3) Hiçbiri yok — bekleme durumu (çökme yok).
        if kanal is None:
            self._kip = "bekliyor"
            self._son_hata = dji_osdk.OsdkYardimci.eksik_gerekce(cfg) \
                or "OSDK yardımcısı bekleniyor"
            self.yaz("Bağlanılamadı: %s. Benzetim için sim=true veya "
                     "OSDK yardımcısını yapılandırın." % self._son_hata,
                     "uyari")
            return self._durum_paketi()

        adaptor = dji_osdk.OsdkAdaptor(gcs_adres, gcs_port, kanal,
                                       video_url=video_url, yaz=_yaz)
        adaptor.baslat()
        with self._kilit:
            self._adaptor = adaptor
            self._yardimci = yardimci
            self._son_hata = ""
        self.yaz("DJI bağlantısı başlatıldı (kip=%s; GDP %s:%d)"
                 % (self._kip, gcs_adres, gcs_port), "basari")
        return self._durum_paketi()

    def _baglanti_durdur(self) -> Dict[str, Any]:
        with self._kilit:
            adaptor, yardimci = self._adaptor, self._yardimci
            self._adaptor = self._yardimci = None
            self._kip = "kapali"
        if adaptor is not None:
            try:
                adaptor.durdur()
            except Exception:
                pass
        if yardimci is not None:
            try:
                yardimci.kapat()
            except Exception:
                pass
        self.yaz("DJI bağlantısı durduruldu", "bilgi")
        return self._durum_paketi()

    def _durum_paketi(self) -> Dict[str, Any]:
        with self._kilit:
            adaptor = self._adaptor
            kip = self._kip
            son_hata = self._son_hata
        ad = adaptor.durum() if adaptor is not None else {}
        bagli = bool(ad.get("gdp_bagli") and ad.get("kanal_bagli"))
        return {
            "dji_kip": kip,
            "dji_bagli": bagli,
            "dji_gdp_bagli": bool(ad.get("gdp_bagli")),
            "dji_kanal_bagli": bool(ad.get("kanal_bagli")),
            "dji_telem": int(ad.get("telem_gonderilen") or 0),
            "dji_anahtar_var": bool(self._ayarlar.get("app_key")),
            "dji_yardimci_var": dji_osdk.OsdkYardimci.kullanilabilir(
                self._ayar_oku_ic()),
            "dji_son_hata": son_hata,
            "gcs_adres": ad.get("gcs_adres") or self._ayarlar.get(
                "gcs_adres") or dji_osdk.VARSAYILAN_GDP_ADRES,
            "gcs_port": ad.get("gcs_port") or self._ayarlar.get(
                "gcs_port") or dji_osdk.VARSAYILAN_GDP_PORT,
        }

    def kapat(self):
        try:
            self._baglanti_durdur()
        except Exception:
            pass
        try:
            self.durum_yaz(dji_bagli=False, dji_kip="kapali", dji_telem=0)
        except Exception:
            pass


if __name__ == "__main__":
    calistir(DjiServisi)
