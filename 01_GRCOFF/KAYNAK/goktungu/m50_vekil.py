# -*- coding: utf-8 -*-
"""GÖKTUNGU — MERKEZ KIPI M50 ELEKTRO-OPTİK VEKİLİ.

M50 HVS SDK yalnız Windows x64 saha Köprüsünde çalışır. Bu sınıf cihaz SDK'sını,
DLL'lerini ya da ham video verisini yüklemez; yalnız seçilmiş, yetkili Köprüden
gelen arındırılmış M50 durumunu alır. Cihaz komutları `sunucu.py` tarafından
açıkça seçilen Köprüye yönlendirilir.

Güvenlik sınırları:
* Parola, kullanıcı adı, oturum anahtarı ve SDK hata ayrıntıları Merkezde
  saklanmaz veya yayımlanmaz.
* Ham SDK görüntü olayı taşınmaz. Operatörün açıkça tanımladığı, gömülü kimlik
  bilgisi taşımayan RTSP(S) kaynakları yalnız durum metaverisi olarak kalır.
* Vekil kendi başına bağlantı kuramaz; merkezden sahadaki M50 IP adresine ağ
  erişimi denemez.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict
from urllib.parse import urlparse


CEKME_ARALIK_SN = 0.5
KOPMA_TOLERANS_SN = 6.0
_GIZLI_ANAHTARLAR = {
    "parola", "password", "sifre", "secret", "token", "oturum",
    "session", "credential", "kimlik", "kullanici", "username",
}


def _arindir(deger: Any, derinlik: int = 0) -> Any:
    """Merkeze taşınacak M50 paketinden sır olabilecek alanları çıkarır."""
    if derinlik > 8:
        return None
    if isinstance(deger, dict):
        sonuc: Dict[str, Any] = {}
        for anahtar, deger_ in deger.items():
            ad = str(anahtar).strip().lower()
            if any(gizli in ad for gizli in _GIZLI_ANAHTARLAR):
                continue
            sonuc[str(anahtar)] = _arindir(deger_, derinlik + 1)
        return sonuc
    if isinstance(deger, list):
        return [_arindir(x, derinlik + 1) for x in deger[:64]]
    if isinstance(deger, str):
        # Köprü doğrulaması bu biçimi zaten reddeder; vekil de eski/hatalı
        # bir Köprüden dönebilecek kullanıcı bilgili RTSP(S) URI'sini
        # telemetriye taşımamak için ikinci savunma hattıdır.
        try:
            ayrik = urlparse(deger)
            if ayrik.scheme.lower() in ("rtsp", "rtsps") and (
                    ayrik.username is not None or ayrik.password is not None or
                    ayrik.query or ayrik.fragment):
                return ""
        except Exception:
            return ""
        return deger
    if isinstance(deger, (int, float, bool)) or deger is None:
        return deger
    return str(deger)[:256]


class M50Vekili:
    """M50 Köprü hizmetinin kapalı-varsayılan, salt-vekil Merkez yüzü."""

    def __init__(self, konsol, kilit, cek=None):
        self.konsol = konsol
        self.kilit = kilit
        self._cek = cek
        self._son_cekme = 0.0
        self._son_basarili = 0.0
        self._cekme_kilit = threading.Lock()
        self.durum = {
            "tur": "m50", "durum": "kapali", "bagli": False,
            "sdk_surumu": "", "sdk_hazir": False, "ip": "", "port": 0,
            "hata": "", "azimut": None, "egim": None,
            "takip": {"etkin": False, "kanal": "", "secim_hazir": False},
            "video": {"gorunur": False, "termal": False,
                      "kaynak": "yerel_kopru"},
            "son_islem": "", "guncelleme": 0.0,
        }
        # M50 ayarları saha makinesinde kalır. Merkez yalnız yerel görüntü
        # hattına eklenebilecek açık RTSP(S) kaynaklarını görür.
        self.ayarlar = {"rtsp_gorunur": "", "rtsp_termal": ""}
        self.video = {"gorunur": False, "termal": False,
                      "kaynak": "yerel_kopru",
                      "rtsp_gorunur": "", "rtsp_termal": ""}
        self.takip = {"etkin": False, "kanal": "", "secim_hazir": False}
        self.osd = {}      # v2.4.215: kanal -> cihaz OSD ayarlari

    def cek_gerekirse(self):
        """Telemetri döngüsünden çağrılır; gerektiğinde Köprüden durum çeker."""
        simdi = time.time()
        if simdi - self._son_cekme < CEKME_ARALIK_SN:
            return
        if not self._cekme_kilit.acquire(blocking=False):
            return
        try:
            self._son_cekme = simdi
            if self._cek is None:
                self._kopru_yok("M50 saha Köprüsü yapılandırılmadı")
                return
            paket, hata = self._cek()
            if hata or not isinstance(paket, dict):
                self._kopru_hatasi(hata or "M50 saha Köprüsü yanıt vermedi")
                return
            self._uygula(paket)
            self._son_basarili = simdi
        except Exception as exc:
            self._kopru_hatasi("%s: %s" % (type(exc).__name__, exc))
        finally:
            self._cekme_kilit.release()

    def _uygula(self, paket):
        ham_durum = paket.get("m50_durum")
        ham_ayarlar = paket.get("m50_ayarlar")
        ham_video = paket.get("m50_video")
        ham_takip = paket.get("m50_takip")
        ham_osd = paket.get("m50_osd")          # v2.4.215
        with self.kilit:
            if isinstance(ham_durum, dict):
                self.durum.update(_arindir(ham_durum))
            # SDK dizini Merkezde işe yaramaz; yalnız saha makinesinde kalır.
            if isinstance(ham_ayarlar, dict):
                temiz_ayarlar = _arindir(ham_ayarlar)
                for alan in ("rtsp_gorunur", "rtsp_termal"):
                    if alan in temiz_ayarlar:
                        self.ayarlar[alan] = str(temiz_ayarlar.get(alan) or "")
                # v2.4.187: sır olmayan kimlik özeti — arayüz "IP/port
                # kayıtlı, tekrar girmene gerek yok" gösterebilsin.
                for alan in ("ip", "port", "kimlik_kayitli"):
                    if alan in temiz_ayarlar:
                        self.ayarlar[alan] = temiz_ayarlar.get(alan)
                # v2.4.207 (kullanici: "duzenlemede kullanici adi bos
                # geliyor"): `_arindir` "kullanici" anahtarini sir sayip
                # atar; kullanici ADI sir degildir (parola hic gelmez),
                # duzenleme formunun on-dolumu icin ayrica tasinir.
                ku = ham_ayarlar.get("kullanici")
                self.ayarlar["kullanici"] = str(ku)[:64] if isinstance(ku, str) else ""
            if isinstance(ham_video, dict):
                self.video.update(_arindir(ham_video))
            if isinstance(ham_takip, dict):
                self.takip.update(_arindir(ham_takip))
            if isinstance(ham_osd, dict):
                self.osd = _arindir(ham_osd)
            # Tek durum kaynağı korunur: UI eski Köprü sürümlerinde dahi
            # `m50_durum.takip/video` üzerinden geriye düşebilir.
            self.durum["takip"] = dict(self.takip)
            self.durum["video"] = dict(self.video)
            self.durum["bagli"] = bool(self.durum.get("bagli"))

    def rtsp_url(self, kanal: str):
        """v2.4.181: kamera modülü için kanal->RTSP çözümü ('gorunur'/'termal').

        Bu URL'ler kimlik bilgisi TAŞIMAZ (Köprü zaten `_arindir` ile
        kullanıcı bilgili RTSP(S) URI'sini reddeder) — yerel Görüntü
        Köprüsünün açık yeniden yayınıdır. Kamera kaydı bu değeri
        DOĞRUDAN saklamaz; her akış açılışında burada TAZE okunur, böylece
        Köprü ayarı sonradan değişse (SDK yeniden bağlanırsa port/URL
        değişebilir) kamera kaydı güncellenmeden yeni adres kullanılır.
        """
        kanal = str(kanal or "").strip().lower()
        if kanal not in ("gorunur", "termal"):
            return None
        with self.kilit:
            return str(self.ayarlar.get("rtsp_" + kanal) or "").strip() or None

    def paket(self) -> Dict[str, Any]:
        """Telemetri için derin kopya niteliğinde, sırdan arındırılmış paket."""
        with self.kilit:
            return {
                "m50_durum": _arindir(dict(self.durum)),
                "m50_ayarlar": dict(_arindir(dict(self.ayarlar)),
                                    kullanici=str(self.ayarlar.get("kullanici") or "")),
                "m50_video": _arindir(dict(self.video)),
                "m50_takip": _arindir(dict(self.takip)),
                "m50_osd": _arindir(dict(self.osd)),
            }

    def _kopru_yok(self, mesaj):
        with self.kilit:
            self.durum.update({"durum": "kapali", "bagli": False,
                               "hata": mesaj, "ip": "", "port": 0})
            self.takip = {"etkin": False, "kanal": "", "secim_hazir": False}

    def _kopru_hatasi(self, mesaj):
        simdi = time.time()
        if self._son_basarili and simdi - self._son_basarili < KOPMA_TOLERANS_SN:
            return
        with self.kilit:
            self.durum.update({"durum": "hata", "bagli": False,
                               "hata": str(mesaj)[:256], "ip": "", "port": 0})
            self.takip = {"etkin": False, "kanal": "", "secim_hazir": False}

    # Yerel SDK çağrısına karşı açık savunma. Bir gerileme ile bu yöntemler
    # çağrılsa dahi Merkez fiziksel M50'ye doğrudan ağ erişimi denemez.
    def baglan(self, *_args, **_kwargs):
        self.konsol("M50", "Merkez kipinde M50 bağlantısı yalnız saha Köprüsü üzerinden kurulur.", "uyari")
        return False

    def kes(self):
        self.konsol("M50", "Merkez kipinde M50 oturumu yalnız saha Köprüsü üzerinden kesilir.", "uyari")
        return False
