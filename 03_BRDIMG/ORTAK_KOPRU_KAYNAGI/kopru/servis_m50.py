"""GÖKTUNGU KÖPRÜ — M50 ELEKTRO-OPTİK SERVİSİ.

M50, C20 radardan bağımsız bir saha cihazıdır. Cihaz oturumu yalnız yerel
Köprüde, yalnız operatörün açık `baglan` komutuyla ve HVS Windows x64 SDK
3.0.10.869 üzerinden açılır. Varsayılan IP, gömülü parola, otomatik hedef
seçimi, silah/atış ve angajman komutu kesinlikle yoktur.

Üretici SDK'sının ham görüntü olayı bir Windows pencere tutamacına bağlıdır;
bu servis ham SDK baytını web ya da Merkez katmanına iletmez. Operatörün
ayrıca tanımladığı görünür/termal RTSP(S) kaynağı mevcut yerel video hattında
gösterilir. Bu hizmet yalnız cihaz durumu ve açık kullanıcı kontrolünü taşır.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from typing import Any, Dict
from urllib.parse import urlparse

from .m50_hvs import M50Hata, M50Istemcisi, M50_VARSAYILAN_PORT
from .servis_kanal import ServisKanali
from .servis_temel import Servis, calistir

DONGU_SN = 0.25
DURUM_YAZIM_SN = 0.5


class M50Servisi(Servis):
    """M50'nin Köprüdeki kuyruklu, kapalı-varsayılan hizmet yüzü."""

    ad = "m50"
    baslik = "M50 Elektro-Optik Servisi"

    def hazirla(self):
        self.kanal = ServisKanali()
        self._ayar_kilidi = threading.RLock()
        self._ayarlar: Dict[str, Any] = {}
        self._ayar_yolu = self._ayar_yolu_bul()
        self._ayar_yukle()
        self.istemci = M50Istemcisi(
            yaz=self.yaz, ayar_oku=self._ayar_oku, ayar_yaz=self._ayar_yaz
        )
        self._son_durum_yazim = 0.0
        self.yaz("M50 elektro-optik hizmeti hazır; açık bağlantı komutu bekleniyor")
        if not self.kanal.etkin():
            self.yaz("Panel komut kanalı etkin değil; M50 yerel olarak kapalı bekleyecek", "uyari")

    # Yerel, yükseltmede korunmuş ayarlar. Parola ve oturum bilgisi hiçbir
    # zaman bu dosyaya yazılmaz; cihaz yeniden başlatılırsa kullanıcı tekrar
    # oturum açar. Bu, yetkisiz otomatik cihaz erişimini önler.
    def _ayar_yolu_bul(self) -> str:
        dizin = (os.environ.get("GOKTUNGU_KOPRU_VERI_DIZIN") or
                 os.environ.get("GOKTUNGU_KOPRU_KANAL_DIZIN") or "")
        if not dizin:
            durum = os.environ.get("GOKTUNGU_KOPRU_DURUM_DOSYASI") or ""
            dizin = os.path.dirname(durum) if durum else ""
        if not dizin:
            dizin = os.path.join(os.path.expanduser("~"), ".goktungu_kopru")
        os.makedirs(dizin, exist_ok=True)
        return os.path.join(dizin, "m50_ayar.json")

    def _ayar_yukle(self) -> None:
        try:
            with open(self._ayar_yolu, "r", encoding="utf-8") as f:
                veri = json.load(f)
            if isinstance(veri, dict):
                self._ayarlar = self._ayar_filtrele(veri)
        except (OSError, ValueError, TypeError):
            self._ayarlar = {}

    @staticmethod
    def _metin(deger: Any, ad: str, en_cok: int = 512) -> str:
        sonuc = str(deger or "").strip()
        if "\x00" in sonuc or len(sonuc) > en_cok:
            raise ValueError("%s geçersiz" % ad)
        return sonuc

    @classmethod
    def _rtsp_uri(cls, deger: Any, ad: str) -> str:
        """Yalnız kimlik bilgisi taşımayan, açıkça belirtilmiş RTSP(S) URI'si."""
        uri = cls._metin(deger, ad)
        if not uri:
            return ""
        ayrik = urlparse(uri)
        if ayrik.scheme.lower() not in ("rtsp", "rtsps") or not ayrik.hostname:
            raise ValueError("%s yalnız geçerli rtsp:// veya rtsps:// URI'si olmalıdır" % ad)
        # URL kullanici/parola, query veya fragment ile saklanan gizler
        # durum paketine aktarilamaz. Kimlik dogrulama gerekiyorsa cihaz
        # tarafinda güvenli profil kullanılmalıdır; bu servis saklamaz.
        if ayrik.username is not None or ayrik.password is not None or ayrik.query or ayrik.fragment:
            raise ValueError("%s gömülü kimlik bilgisi veya oturum parametresi içeremez" % ad)
        return uri

    @classmethod
    def _ayar_filtrele(cls, veri: Dict[str, Any]) -> Dict[str, Any]:
        """Kalıcı ayarı izin listesiyle daraltır; parola/oturum saklamaz."""
        sonuc: Dict[str, Any] = {}
        if "m50_sdk_dizin" in veri:
            sonuc["m50_sdk_dizin"] = cls._metin(veri.get("m50_sdk_dizin"), "m50_sdk_dizin")
        for anahtar in ("rtsp_gorunur", "rtsp_termal"):
            if anahtar in veri:
                sonuc[anahtar] = cls._rtsp_uri(veri.get(anahtar), anahtar)
        return sonuc

    def _ayar_oku(self) -> Dict[str, Any]:
        with self._ayar_kilidi:
            return dict(self._ayarlar)

    def _ayar_yaz(self, veri: Dict[str, Any]) -> None:
        if not isinstance(veri, dict):
            return
        yeni = self._ayar_filtrele(veri)
        with self._ayar_kilidi:
            # Bos deger, operatörün ilgili yerel kaynağı özellikle
            # kaldırmak istediğini belirtir; eski akış URL'si kalmaz.
            for anahtar, deger in yeni.items():
                if deger:
                    self._ayarlar[anahtar] = deger
                else:
                    self._ayarlar.pop(anahtar, None)
            kayit = dict(self._ayarlar)
        gecici = None
        try:
            dizin = os.path.dirname(self._ayar_yolu) or "."
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=dizin,
                                             delete=False, prefix=".m50_",
                                             suffix=".tmp") as f:
                gecici = f.name
                json.dump(kayit, f, ensure_ascii=False, separators=(",", ":"))
                f.flush()
                os.fsync(f.fileno())
            os.replace(gecici, self._ayar_yolu)
        except OSError as exc:
            if gecici:
                try:
                    os.unlink(gecici)
                except OSError:
                    pass
            self.yaz("M50 ayarları yazılamadı: %s" % exc, "uyari")

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
            except (M50Hata, ValueError, TypeError) as exc:
                self.yaz("M50 komut hatası (%s): %s" % (eylem, exc), "hata")
                self.kanal.yanit(kimlik, False, str(exc))
            except Exception as exc:  # cihaz/SDK hatası hiçbir zaman hizmeti düşürmez
                self.yaz("M50 beklenmeyen komut hatası (%s): %s" % (eylem, exc), "hata")
                self.kanal.yanit(kimlik, False, "M50 komutu uygulanamadı")

    def _komut_uygula(self, eylem: str, veri: Dict[str, Any]) -> Dict[str, Any]:
        if eylem == "durum":
            return self._durum_paketi()
        if eylem == "ayar_oku":
            return {"ayarlar": self._ayar_oku()}
        if eylem == "ayar_yaz":
            self._ayar_yaz(veri)
            return {"ayarlar": self._ayar_oku()}
        if eylem == "baglan":
            # `baglan` sürücüde IP/port/doğrulama girdilerini sınırlar. Kimlik
            # bilgileri yalnız bu çağrı sırasında RAM'dedir.
            return {"m50_durum": self.istemci.baglan(veri)}
        if eylem == "kes":
            return {"m50_durum": self.istemci.kes()}
        if eylem == "ptz":
            return {"m50_durum": self.istemci.ptz(
                veri.get("yon"), veri.get("hiz"), veri.get("basili", True))}
        if eylem == "lens":
            return {"m50_durum": self.istemci.lens(
                veri.get("eylem"), veri.get("kanal"), veri.get("basili", True))}
        if eylem == "aci_konumla":
            return {"m50_durum": self.istemci.aci_konumla(
                veri.get("azimut"), veri.get("egim"), veri.get("hiz"))}
        if eylem == "takip_sec":
            return {"m50_durum": self.istemci.takip_sec(
                                veri.get("kanal"), veri.get("video_dikdortgen"), veri.get("secim"))
}
        if eylem == "takip_baslat":
            return {"m50_durum": self.istemci.takip_baslat(
                veri.get("kanal"), veri.get("mod"))}
        if eylem == "takip_durdur":
            return {"m50_durum": self.istemci.takip_durdur(veri.get("kanal"))}
        raise ValueError("bilinmeyen M50 eylemi: %s" % eylem)

    def _durum_paketi(self) -> Dict[str, Any]:
        durum = self.istemci.durum()
        ayarlar = self._ayar_oku()
        video = dict(durum.get("video") or {})
        # RTSP kaynağı yalnız operatör açıkça tanımladıysa gösterilir. Ham SDK
        # olayı web aktarımı olarak varsayılmaz.
        video["rtsp_gorunur"] = ayarlar.get("rtsp_gorunur", "")
        video["rtsp_termal"] = ayarlar.get("rtsp_termal", "")
        return {
            "m50_durum": durum,
            "m50_ayarlar": ayarlar,
            "m50_video": video,
            "m50_takip": dict(durum.get("takip") or {}),
            "m50_bagli": bool(durum.get("bagli")),
        }

    def kapat(self):
        try:
            self.istemci.kes()
        except Exception:
            pass
        try:
            self.durum_yaz(m50_bagli=False,
                            m50_durum={"tur": "m50", "durum": "kapali", "bagli": False})
        except Exception:
            pass


if __name__ == "__main__":
    calistir(M50Servisi)
