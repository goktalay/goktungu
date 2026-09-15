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

KİMLİK KALICILIĞI (v2.4.187 — kullanıcı isteği: "bir kere gireyim,
veritabanına kaydet, sormasın"): saha Köprüsünün aksine bu modül TEK
MAKİNELİK, tek-operatörlü yerel kuruluş içindir; ip/port/kullanıcı
adı/parola başarılı bir `baglan` sonrası Merkez'in KENDİ yerel
ayarlar tablosuna (aynı veritabanı, aynı güven sınırı — ağ üzerinden
hiçbir yere gönderilmez) yazılır ve süreç yeniden başladığında
(main.py) otomatik olarak yeniden bağlanmak için kullanılır. Parola
API üzerinden asla GERİ okunmaz (`ayar_oku` yalnız ip/port/kullanıcı
döner) — yalnızca yazılır ve dahili bağlantı çağrısında kullanılır.
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

    def __init__(self, konsol, ayarlar, eo_id=1):
        self._konsol = konsol
        self._ayarlar = ayarlar
        # v2.4.191: cihaz basina ayri ayar anahtari; 1 numarali cihaz eski
        # tek-cihaz anahtarini ("m50_yerel") devralir.
        self.eo_id = int(eo_id or 1)
        self._ayar_anahtari = (_AYAR_ANAHTARI if self.eo_id == 1
                               else "%s_%d" % (_AYAR_ANAHTARI, self.eo_id))
        self._konum_ts = 0.0
        self._osd_son = {}   # v2.4.215: kanal -> cihaz OSD sozlugu
        self._ayar_kilidi = threading.RLock()
        self._kullanilabilir_onbellek = None
        self._kullanilabilir_ts = 0.0
        # Bağlantı başına SDK'dan bir kez okunur; telemetri döngüsü her
        # turda `_durum_paketi()` çağırdığı için SDK'ya saniyede iki
        # GetRtspUrl gitmesin. baglan/kes temizler.
        self._rtsp_onbellek: Dict[str, str] = {}
        self._onayar_onbellek = None
        self._aci_ts = 0.0
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
    # Kalıcı ayar: m50_sdk_dizin / rtsp_gorunur / rtsp_termal (RTSP
    # doğrulamalı, kimlik bilgisi taşıyamaz) + ip/port/kullanici/parola
    # (v2.4.187 — bkz. modül başlığı). `_KIMLIK_ALANLARI` API üzerinden
    # ASLA geri okunmaz; yalnız dahili `otomatik_baglan()` kullanır.
    # -----------------------------------------------------------------
    _KIMLIK_ALANLARI = ("ip", "port", "kullanici", "parola")

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
        if "ip" in veri:
            sonuc["ip"] = cls._metin(veri.get("ip"), "ip", 64)
        if "port" in veri:
            try:
                sonuc["port"] = int(veri.get("port"))
            except (TypeError, ValueError):
                raise ValueError("port geçersiz")
        if "kullanici" in veri:
            sonuc["kullanici"] = cls._metin(veri.get("kullanici"), "kullanici", 64)
        if "parola" in veri:
            # Uzunluk sınırı hariç biçim denetimi yok: SDK'nın kabul
            # ettiği her karakter kalıcı depoda da kabul edilir.
            sonuc["parola"] = str(veri.get("parola") or "")[:128]
        return sonuc

    def _ayar_oku(self) -> Dict[str, Any]:
        """SDK/RTSP çözümü için TÜM alanları (parola dahil) döner —
        yalnız içeride kullanılır, WS'e asla verilmez (bkz. `_ayar_oku_disa`)."""
        with self._ayar_kilidi:
            try:
                tumu = self._ayarlar.yukle()
            except Exception:
                return {}
            deger = tumu.get(self._ayar_anahtari)
            return dict(deger) if isinstance(deger, dict) else {}

    def _ayar_oku_disa(self) -> Dict[str, Any]:
        """`ayar_oku` WS yanıtı: parola KESİNLİKLE dışlanır; kullanıcı
        adı/IP/port operatöre "zaten kayıtlı, tekrar girmene gerek yok"
        göstermek için döner."""
        a = dict(self._ayar_oku())
        a.pop("parola", None)
        return a

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
                self._ayarlar.kaydet({self._ayar_anahtari: mevcut})
            except Exception as exc:
                self._yaz("M50 ayarları yazılamadı: %s" % exc, "uyari")

    def otomatik_baglan(self) -> None:
        """Süreç başlarken (main.py) önceden kaydedilmiş kimlik bilgisi
        varsa otomatik bağlanmayı dener. Hiçbir kayıt yoksa sessizce
        çıkar; SDK kullanılamıyorsa (Linux/DLL yok) da sessizce çıkar —
        çağıran yer zaten `kullanilabilir()` denetler."""
        if not self.kullanilabilir():
            return
        a = self._ayar_oku()
        if not (a.get("ip") and a.get("kullanici") and a.get("parola") and a.get("port")):
            return
        try:
            self._rtsp_onbellek = {}
            self.istemci.baglan({
                "ip": a["ip"], "port": a["port"],
                "kullanici": a["kullanici"], "parola": a["parola"],
            })
            self._yaz("Kayıtlı M50 kimliğiyle otomatik bağlanıldı: %s:%s"
                      % (a["ip"], a["port"]))
        except Exception as exc:
            self._yaz("Otomatik M50 bağlantısı başarısız: %s" % exc, "uyari")

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
            self._rtsp_onbellek = {}
            self.istemci.baglan(veri)
            # Başarılı bağlantıdan SONRA kimlik kalıcılaştırılır (bkz.
            # modül başlığı): bir dahaki sefere operatör tekrar girmez,
            # süreç yeniden başlayınca `otomatik_baglan()` kullanır.
            self._ayar_yaz_ic({a: veri.get(a) for a in self._KIMLIK_ALANLARI
                               if a in veri})
        elif eylem == "baglan_kayitli":
            # Operatör alanları boş bıraktı: kayıtlı kimlikle bağlan.
            a = self._ayar_oku()
            if not (a.get("ip") and a.get("kullanici") and a.get("parola")
                    and a.get("port")):
                raise M50Hata("Kayıtlı M50 kimliği yok; IP, port, kullanıcı "
                              "adı ve parolayı bir kez girin.")
            self._rtsp_onbellek = {}
            self.istemci.baglan({"ip": a["ip"], "port": a["port"],
                                 "kullanici": a["kullanici"],
                                 "parola": a["parola"],
                                 "zaman_asimi": veri.get("zaman_asimi", 5000)})
        elif eylem == "kes":
            self._rtsp_onbellek = {}
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
        # --- v2.4.188: SDK'nın geri kalanı ---
        elif eylem == "aci_oku":
            self.istemci.aci_oku()
        elif eylem == "onayar_liste":
            self._onayar_onbellek = None
        elif eylem == "onayar_kaydet":
            self.istemci.onayar_kaydet(veri.get("no"), veri.get("ad"),
                                       veri.get("hiz", 5))
            self._onayar_onbellek = None
        elif eylem == "onayar_cagir":
            self.istemci.onayar_cagir(veri.get("no"))
        elif eylem == "onayar_sil":
            self.istemci.onayar_sil(veri.get("no"))
            self._onayar_onbellek = None
        elif eylem == "onayar_hepsini_sil":
            self.istemci.onayar_hepsini_sil()
            self._onayar_onbellek = None
        elif eylem == "tarama":
            self.istemci.tarama(veri.get("tur"), veri.get("kontrol"),
                                veri.get("yol", 0))
        elif eylem == "takip_yetenek":
            self.istemci.takip_yetenek(veri.get("kanal"), veri.get("etkin", True))
        # --- v2.4.215: cihaz OSD'si (kareye basılan yazı) ---
        elif eylem == "osd_oku":
            kanal = str(veri.get("kanal") or "gorunur")
            self._osd_son[kanal] = self.istemci.osd_oku(kanal)
        elif eylem == "osd_yaz":
            kanal = str(veri.get("kanal") or "gorunur")
            self._osd_son[kanal] = self.istemci.osd_yaz(kanal, veri.get("alanlar") or {})
        else:
            raise M50Hata("bilinmeyen M50 eylemi: %s" % eylem)
        return self._durum_paketi()

    def _onayarlari_getir(self, bagli: bool) -> list:
        """Ön ayar listesi cihazdan yalnız değişince/ilk kez okunur."""
        if not bagli:
            self._onayar_onbellek = None
            return []
        if self._onayar_onbellek is None:
            try:
                self._onayar_onbellek = self.istemci.onayarlar()
            except Exception:
                self._onayar_onbellek = []
        return list(self._onayar_onbellek)

    def _aci_tazele(self, bagli: bool) -> None:
        """Telemetri her turda çağırır; SDK'ya en çok saniyede bir gidilir."""
        if not bagli:
            return
        simdi = time.time()
        if simdi - self._aci_ts < 1.0:
            return
        self._aci_ts = simdi
        try:
            self.istemci.aci_oku()
        except Exception:
            pass

    def _konum_tazele(self, bagli: bool) -> None:
        """RTK/GPS + pusula 5 sn'de bir istenir (geri çağrı ile gelir)."""
        if not bagli:
            return
        simdi = time.time()
        if simdi - self._konum_ts < 5.0:
            return
        self._konum_ts = simdi
        try:
            d = self.istemci.konum_oku()
            tani = d.get("konum_tani") if isinstance(d, dict) else None
            if tani and not getattr(self, "_konum_tani_yazildi", False):
                self._konum_tani_yazildi = True
                self._yaz("M50 %s" % tani, "bilgi")
            tani2 = d.get("konum_tani2") if isinstance(d, dict) else None
            if tani2 and not getattr(self, "_konum_tani2_yazildi", False):
                self._konum_tani2_yazildi = True
                self._yaz("M50 %s" % tani2, "bilgi")
        except Exception:
            pass

    def _durum_paketi(self) -> Dict[str, Any]:
        bagli = bool(self.istemci.durum().get("bagli"))
        self._aci_tazele(bagli)
        self._konum_tazele(bagli)
        durum = self.istemci.durum()
        durum["onayarlar"] = self._onayarlari_getir(bagli)
        # Parola bu paketten DIŞLANIR: paket `M50Vekili._uygula()` ve
        # telemetriye gider; savunma derinliği için hiç girmemeli.
        kayitli = self._ayar_oku_disa()
        # Öncelik CİHAZIN KENDİ bildirdiği adrestedir (HVS_GetRtspUrl):
        # operatörün elle girmesine gerek kalmaz. Bağlı değilse veya SDK
        # adres vermiyorsa (None), operatörün elle kaydettiği adrese
        # düşülür — eski davranış korunur. `ayarlar` alanına (video_proxy
        # `M50Vekili.rtsp_url()` ile BURADAN okur) yazılır — yalnız
        # `video` özetine değil; aksi halde kamera akışı hâlâ boş adrese
        # düşerdi.
        etkin = dict(kayitli)
        etkin["kimlik_kayitli"] = bool(self._ayar_oku().get("parola"))
        for kanal in ("gorunur", "termal"):
            otomatik = self._rtsp_onbellek.get(kanal)
            if not otomatik and bool(durum.get("bagli")):
                try:
                    otomatik = self.istemci.rtsp_url(kanal)
                except Exception:
                    otomatik = None
                if otomatik:
                    self._rtsp_onbellek[kanal] = otomatik
            if otomatik:
                etkin["rtsp_" + kanal] = otomatik
        video = dict(durum.get("video") or {})
        video["rtsp_gorunur"] = etkin.get("rtsp_gorunur", "")
        video["rtsp_termal"] = etkin.get("rtsp_termal", "")
        return {
            "m50_durum": durum,
            "m50_ayarlar": etkin,
            "m50_video": video,
            "m50_takip": dict(durum.get("takip") or {}),
            "m50_osd": dict(getattr(self, "_osd_son", {}) or {}),   # v2.4.215
        }
