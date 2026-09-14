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
        # 1.7.19 (Faz C): COKLU M50. Her elektro-optik kimligi (eo_id)
        # icin ayri bir SDK istemcisi; komutlar `eo_id` tasir (yoksa 1).
        # Kimlik bilgisi (kullanici/parola) burada da SAKLANMAZ: Merkez
        # kayitli kimligi her baglan komutunda yeniden gonderir.
        self.istemciler: Dict[int, M50Istemcisi] = {}
        self._son_durum_yazim = 0.0
        self.yaz("M50 elektro-optik hizmeti hazır (çoklu cihaz); açık bağlantı komutu bekleniyor")
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
                self._ayarlar = self._ayar_filtrele(veri, ic=True)
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
    def _ayar_filtrele(cls, veri: Dict[str, Any], ic: bool = False) -> Dict[str, Any]:
        """Kalıcı ayarı izin listesiyle daraltır; parola/oturum saklamaz.

        `cihazlar` alt sözlüğü (1.7.19, eo_id>1 için cihaz başına RTSP
        adresleri) yalnız dosyadan okuma/yazma sırasında (`ic=True`)
        geçer; komuttan gelen veri bu anahtarı doğrudan yazamaz.
        """
        sonuc: Dict[str, Any] = {}
        if "m50_sdk_dizin" in veri:
            sonuc["m50_sdk_dizin"] = cls._metin(veri.get("m50_sdk_dizin"), "m50_sdk_dizin")
        for anahtar in ("rtsp_gorunur", "rtsp_termal"):
            if anahtar in veri:
                sonuc[anahtar] = cls._rtsp_uri(veri.get(anahtar), anahtar)
        if ic and isinstance(veri.get("cihazlar"), dict):
            cihazlar: Dict[str, Any] = {}
            for k, v in veri["cihazlar"].items():
                try:
                    eid = int(k)
                except (TypeError, ValueError):
                    continue
                if eid > 1 and isinstance(v, dict):
                    alt = {}
                    for anahtar in ("rtsp_gorunur", "rtsp_termal"):
                        if v.get(anahtar):
                            try:
                                alt[anahtar] = cls._rtsp_uri(v.get(anahtar), anahtar)
                            except ValueError:
                                continue
                    if alt:
                        cihazlar[str(eid)] = alt
            if cihazlar:
                sonuc["cihazlar"] = cihazlar
        return sonuc

    def _ayar_oku(self) -> Dict[str, Any]:
        with self._ayar_kilidi:
            return dict(self._ayarlar)

    # ---- 1.7.19: cihaz basina ayar gorunumu ----
    @staticmethod
    def _eid(veri: Any) -> int:
        try:
            eid = int((veri or {}).get("eo_id") or 1)
        except (TypeError, ValueError):
            eid = 1
        return eid if eid > 0 else 1

    def _ayar_oku_cihaz(self, eid: int) -> Dict[str, Any]:
        """SDK dizini ortaktır; RTSP adresleri cihaz başınadır (eo_id>1
        için `cihazlar` alt sözlüğünden, 1 için eski düz anahtarlardan)."""
        a = self._ayar_oku()
        sonuc = {k: v for k, v in a.items() if k != "cihazlar"}
        if int(eid) != 1:
            sonuc.pop("rtsp_gorunur", None)
            sonuc.pop("rtsp_termal", None)
            alt = (a.get("cihazlar") or {}).get(str(int(eid))) or {}
            sonuc.update({k: v for k, v in alt.items() if v})
        return sonuc

    def _ayar_yaz_cihaz(self, eid: int, veri: Dict[str, Any]) -> None:
        if not isinstance(veri, dict):
            return
        if int(eid) == 1:
            self._ayar_yaz(veri)
            return
        yeni = self._ayar_filtrele(veri)
        with self._ayar_kilidi:
            if "m50_sdk_dizin" in yeni:
                if yeni["m50_sdk_dizin"]:
                    self._ayarlar["m50_sdk_dizin"] = yeni["m50_sdk_dizin"]
                else:
                    self._ayarlar.pop("m50_sdk_dizin", None)
            cihazlar = dict(self._ayarlar.get("cihazlar") or {})
            alt = dict(cihazlar.get(str(int(eid))) or {})
            for anahtar in ("rtsp_gorunur", "rtsp_termal"):
                if anahtar in yeni:
                    if yeni[anahtar]:
                        alt[anahtar] = yeni[anahtar]
                    else:
                        alt.pop(anahtar, None)
            if alt:
                cihazlar[str(int(eid))] = alt
            else:
                cihazlar.pop(str(int(eid)), None)
            if cihazlar:
                self._ayarlar["cihazlar"] = cihazlar
            else:
                self._ayarlar.pop("cihazlar", None)
            kayit = dict(self._ayarlar)
        self._diske_yaz(kayit)

    def _istemci(self, eid: int, olustur: bool = True):
        eid = int(eid)
        ist = self.istemciler.get(eid)
        if ist is None and olustur:
            ist = M50Istemcisi(
                yaz=(lambda m, s="bilgi", _e=eid: self.yaz("[EO%d] %s" % (_e, m), s)),
                ayar_oku=(lambda _e=eid: self._ayar_oku_cihaz(_e)),
                ayar_yaz=(lambda d, _e=eid: self._ayar_yaz_cihaz(_e, d)),
            )
            self.istemciler[eid] = ist
        return ist

    def _birincil_id(self) -> int:
        return min(self.istemciler) if self.istemciler else 1

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
        self._diske_yaz(kayit)

    def _diske_yaz(self, kayit: Dict[str, Any]) -> None:
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
        eid = self._eid(veri)
        if eylem == "durum":
            return self._durum_paketi()
        if eylem == "cihazlar":
            return {"eo_cihazlar": self._cihaz_listesi()}
        if eylem == "ayar_oku":
            return {"ayarlar": self._ayar_oku_cihaz(eid), "eo_id": eid}
        if eylem == "ayar_yaz":
            self._ayar_yaz_cihaz(eid, veri)
            return {"ayarlar": self._ayar_oku_cihaz(eid), "eo_id": eid}
        ist = self._istemci(eid)
        if eylem == "baglan":
            # `baglan` sürücüde IP/port/doğrulama girdilerini sınırlar. Kimlik
            # bilgileri yalnız bu çağrı sırasında RAM'dedir.
            return {"m50_durum": ist.baglan(veri), "eo_id": eid}
        if eylem == "kes":
            return {"m50_durum": ist.kes(), "eo_id": eid}
        if eylem == "ptz":
            return {"m50_durum": ist.ptz(
                veri.get("yon"), veri.get("hiz"), veri.get("basili", True)), "eo_id": eid}
        if eylem == "lens":
            return {"m50_durum": ist.lens(
                veri.get("eylem"), veri.get("kanal"), veri.get("basili", True)), "eo_id": eid}
        if eylem == "aci_konumla":
            return {"m50_durum": ist.aci_konumla(
                veri.get("azimut"), veri.get("egim"), veri.get("hiz")), "eo_id": eid}
        if eylem == "takip_sec":
            return {"m50_durum": ist.takip_sec(
                veri.get("kanal"), veri.get("video_dikdortgen"), veri.get("secim")),
                "eo_id": eid}
        if eylem == "takip_baslat":
            return {"m50_durum": ist.takip_baslat(
                veri.get("kanal"), veri.get("mod")), "eo_id": eid}
        if eylem == "takip_durdur":
            return {"m50_durum": ist.takip_durdur(veri.get("kanal")), "eo_id": eid}
        # --- 1.7.18: SDK'nın geri kalanı (Merkez m50_yerel.py ile aynı sözleşme) ---
        if eylem == "aci_oku":
            return {"m50_durum": ist.aci_oku(), "eo_id": eid}
        if eylem == "onayar_liste":
            return {"m50_durum": dict(ist.durum(), onayarlar=ist.onayarlar()),
                    "eo_id": eid}
        if eylem == "onayar_kaydet":
            ist.onayar_kaydet(veri.get("no"), veri.get("ad"), veri.get("hiz", 5))
            return {"m50_durum": dict(ist.durum(), onayarlar=ist.onayarlar()),
                    "eo_id": eid}
        if eylem == "onayar_cagir":
            return {"m50_durum": ist.onayar_cagir(veri.get("no")), "eo_id": eid}
        if eylem == "onayar_sil":
            ist.onayar_sil(veri.get("no"))
            return {"m50_durum": dict(ist.durum(), onayarlar=ist.onayarlar()),
                    "eo_id": eid}
        if eylem == "onayar_hepsini_sil":
            ist.onayar_hepsini_sil()
            return {"m50_durum": dict(ist.durum(), onayarlar=[]), "eo_id": eid}
        if eylem == "tarama":
            return {"m50_durum": ist.tarama(
                veri.get("tur"), veri.get("kontrol"), veri.get("yol", 0)), "eo_id": eid}
        if eylem == "takip_yetenek":
            return {"m50_durum": ist.takip_yetenek(
                veri.get("kanal"), veri.get("etkin", True)), "eo_id": eid}
        raise ValueError("bilinmeyen M50 eylemi: %s" % eylem)

    def _cihaz_listesi(self):
        cikti = []
        for eid in sorted(self.istemciler):
            d = self.istemciler[eid].durum()
            cikti.append({"eo_id": eid, "bagli": bool(d.get("bagli")),
                          "ip": d.get("ip") or "", "port": d.get("port") or 0,
                          "durum": d.get("durum") or ""})
        return cikti

    def _cihaz_paketi(self, eid: int, ist: M50Istemcisi) -> Dict[str, Any]:
        durum = ist.durum()
        kayitli = self._ayar_oku_cihaz(eid)
        # Öncelik CİHAZIN KENDİ bildirdiği adrestedir (HVS_GetRtspUrl):
        # operatörün elle girmesine gerek kalmaz. Bağlı değilse veya SDK
        # adres vermiyorsa (None), operatörün elle kaydettiği adrese
        # düşülür — eski davranış korunur. `m50_ayarlar` alanına yazılır
        # (Merkez'deki `M50Vekili.rtsp_url()` BURADAN okur) — yalnız
        # `m50_video` özetine değil; aksi halde kamera akışı hâlâ boş
        # adrese düşerdi. Ham SDK video olayı yine web aktarımı olarak
        # varsayılmaz; yalnız RTSP URI'si taşınır.
        etkin = dict(kayitli)
        for kanal in ("gorunur", "termal"):
            otomatik = None
            if bool(durum.get("bagli")):
                try:
                    otomatik = ist.rtsp_url(kanal)
                except Exception:
                    otomatik = None
            if otomatik:
                etkin["rtsp_" + kanal] = otomatik
        video = dict(durum.get("video") or {})
        video["rtsp_gorunur"] = etkin.get("rtsp_gorunur", "")
        video["rtsp_termal"] = etkin.get("rtsp_termal", "")
        return {
            "eo_id": eid,
            "m50_durum": durum,
            "m50_ayarlar": etkin,
            "m50_video": video,
            "m50_takip": dict(durum.get("takip") or {}),
            "m50_bagli": bool(durum.get("bagli")),
        }

    def _durum_paketi(self) -> Dict[str, Any]:
        """Merkeze giden paket.

        1.7.19 (Faz C): üst düzey alanlar BİRİNCİL (en küçük kimlikli)
        cihazındır — eski Merkez sürümleri yalnız bunları okur. Yeni
        Merkez `eo_cihazlar` sözlüğünden cihaz başına okur. Henüz hiç
        cihaz istemcisi yoksa 1 numaralı cihazın boş (kapalı) paketi
        üretilir ki kamera/menü mantığı alan yokluğuna düşmesin.
        """
        if not self.istemciler:
            self._istemci(1)
        cihazlar = {str(eid): self._cihaz_paketi(eid, ist)
                    for eid, ist in sorted(self.istemciler.items())}
        birincil = cihazlar[str(self._birincil_id())]
        paket = dict(birincil)
        paket.pop("eo_id", None)
        paket["eo_cihazlar"] = cihazlar
        paket["eo_sayisi"] = len(cihazlar)
        paket["bagli_eo_sayisi"] = sum(1 for p in cihazlar.values() if p["m50_bagli"])
        # Menü görünürlüğü: herhangi bir cihaz bağlıysa açık kalsın.
        paket["m50_bagli"] = paket["bagli_eo_sayisi"] > 0
        return paket

    def kapat(self):
        for ist in list(self.istemciler.values()):
            try:
                ist.kes()
            except Exception:
                pass
        try:
            self.durum_yaz(m50_bagli=False, eo_cihazlar={}, eo_sayisi=0,
                            bagli_eo_sayisi=0,
                            m50_durum={"tur": "m50", "durum": "kapali", "bagli": False})
        except Exception:
            pass


if __name__ == "__main__":
    calistir(M50Servisi)
