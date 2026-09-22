# -*- coding: utf-8 -*-
"""KOPRU YAZILIMI — DRON SERVISI.

## GOREVI

Ucus donanimini (Pixhawk/RFD900X seri baglantisi, SITL TCP, telemetri
UDP) merkezdeki GOKTUNGU'ye baglar. Merkez sahaya baglanamadigi icin
(NAT) akis SAHADAN merkeze dogru kurulur.

    Ucus kontrolcusu <--seri/UDP/TCP--> DRON SERVISI --WSS--> Merkez

## PORT LISTESI YEREL OKUNUR — VE BU KRITIKTIR

Merkezdeki GOKTUNGU, kullanicinin bilgisayarindaki COM/ttyUSB portlarini
GOREMEZ. Kullanici Baglanti Yoneticisi'nde port secebilsin diye port
listesi BURADA toplanir ve merkeze bildirilir. Bu, mimarinin
kacinilmaz sonucudur: seri port fiziksel olarak kullanicinin
makinesindedir.

## TELEMETRI TAMPONU

Kullanici istegi (birebir):

    "bence dron calismaya basladiginda 1 er dakikalik fiziksel dosyalar
     tutalim sonra her bir dakikada bir veritabanina yazalim"

Telemetri once yerel JSONL dosyasina yazilir, dakikalik dosyalar
kapandikca merkeze aktarilir. Dogrudan her ornegi merkeze gondermek
10 Hz x dron sayisi kadar WSS mesaji uretir ve baglanti koptugunda
veri KAYBOLUR. Tampon, kopmayi dayanikli hale getirir.

## PROTOKOL SOYUTLAMASI (Faz 5)

Bir seri ucus kumandasi iki farkli protokol konusabilir:

  * ArduPilot / PX4  -> MAVLink  (mevcut, DEGISMEZ yol)
  * Betaflight       -> MSP v1   (Faz 5'te EKLENDI, SALT-OKUNUR)

MAVLink yolu bugune kadarki gibi merkezdeki Baglanti Yoneticisi
uzerinden yurur; bu servis onu OLDUGU GIBI korur. Faz 5, buna iki sey
ekler:

1. `protokol_algila(kayit)`: bir seri portun MAVLink mi (ardupilot) yoksa
   MSP mi (betaflight) konustugunu, hicbir kumanda cercevesi yazmadan,
   guvenli sekilde ayirt eder (bkz. `protokol_algilama`).
2. Salt-okunur Betaflight MSP oturumlari: `betaflight_msp` surucusuyle
   MSP tanilama/telemetri sorgulari yapilir. MSP_SET_*, ARM, motor, RC,
   reboot, CLI gibi YAZMA komutlari surucude ne tanimli ne de
   uretilebilir; Betaflight yolu tamamen pasiftir.

Bu islevler panel/merkez tarafindan `servis_kanal` komut kanaliyla
(GCSDUAL ile ayni desen) surulur; boylece seri port yalniz SAHA
makinesinde acilir.

## HENUZ EKLENMEDI — DJI Onboard SDK / DJI Windows SDK

BRDTLM'in kapsaminda DJI dron protokolleri de var; ancak masaustu DJI
uygulama anahtarlari (app key/secret) HENUZ YOK ve bu SDK'lar native
(C++/kapali kaynak) baglama gerektirir. Bu yuzden DJI yolu bilerek
ATLANMISTIR: anahtar + SDK saglaninca protokol soyutlamasina ucuncu bir
yol (`dji_onboard` / `dji_windows`) olarak eklenecektir. Su an yalnizca
MAVLink (ardupilot) ve MSP (betaflight) yollari vardir.
"""
import glob
import json
import os
import time

from . import ayar as ayar_mod
from . import servis_kanal as _sk
from .servis_temel import Servis, calistir

DONGU_ARALIK_SN = 5.0
TAMPON_DAKIKA_SN = 60.0

# Servisin tanidigi ucus protokolleri. `bilinmiyor`, algilama sonucsuz
# kaldiginda dondurulur; cagiran taraf kullaniciya baud/hat kontrolu
# onerir.
PROTOKOLLER = ("ardupilot", "betaflight", "bilinmiyor")


def _ilgili_mi(port, aciklama, donanim):
    """Bu port bir ucus donanimi ADAYI mi?

    ## NEDEN SUZME ZORUNLU

    Linux cekirdegi, HICBIRI fiziksel olmayan 32 adet `/dev/ttyS0..31`
    girdisi olusturur. Ham `pyserial` listesi bunlarin tumunu dondurur.
    Baglanti Yoneticisi'nde 32 anlamsiz port arasindan dogru olani
    bulmak, sahada pilot icin gercek bir hatadir: yanlis port secilir,
    baglanti kurulmaz ve suclu "yazilim" sanilir.

    Olcut: gercek USB seri donusturuculer (`ttyUSB*`, `ttyACM*`,
    Windows'ta `COM*`) ve donanim kimligi olan platform portlari
    kalir; `ttyS*` girdileri YALNIZ gercek bir donanim kimligi
    tasiyorsa listede kalir (bazi endustriyel anakartlarda gercek
    RS-232 portu boyle gorunur).
    """
    p = str(port or "")
    alt = p.lower()
    hw = str(donanim or "").strip().lower()
    if os.name == "nt":
        return alt.startswith("com")
    if "ttyusb" in alt or "ttyacm" in alt or "/serial/by-id/" in alt:
        return True
    if "ttyama" in alt or "ttyths" in alt:      # Raspberry Pi / Jetson
        return True
    if "ttys" in alt:
        # pyserial fiziksel olmayan portlar icin hwid degerini "n/a"
        # dondurur; gercek portta USB/PCI kimligi bulunur.
        return bool(hw) and hw not in ("n/a", "none", "")
    return True


def seri_portlar(tumu=False):
    """Yerel seri portlari listeler.

    `pyserial` varsa onu kullanir (en dogru sonuc: aciklama ve donanim
    kimligi verir). Yoksa dosya sistemine bakar; kopru yaziliminin
    pyserial OLMADAN da calismasi gerekir cunku tek zorunlu bagimliligi
    `websockets`'tir.

    `tumu=True` suzmeyi atlar. Bu bilerek birakildi: nadir bir
    anakartta gercek port suzgece takilirsa kullanicinin onu gorebilmesi
    gerekir. Suzgeci tamamen kaldirmak yerine ASILABILIR yapmak, hem
    varsayilanin temiz kalmasini hem de kose durumlarin cozulebilmesini
    saglar.
    """
    bulunan = []
    ham = []
    try:
        from serial.tools import list_ports
        for p in list_ports.comports():
            ham.append({
                "port": p.device,
                "aciklama": (p.description or "").strip(),
                "donanim": (p.hwid or "").strip(),
                "kaynak": "pyserial",
            })
    except Exception:
        if os.name == "nt":
            # pyserial yoksa Windows'ta kayit defterine bakmak gerekir;
            # bunu yapmak yerine kullaniciya durumu bildiriyoruz.
            return []
        for kalip in ("/dev/serial/by-id/*", "/dev/ttyUSB*",
                      "/dev/ttyACM*", "/dev/ttyAMA*"):
            for y in sorted(glob.glob(kalip)):
                ham.append({"port": y, "aciklama": "", "donanim": "",
                            "kaynak": "dosya"})
    for p in ham:
        if tumu or _ilgili_mi(p["port"], p["aciklama"], p["donanim"]):
            bulunan.append(p)
    return bulunan


def protokol_algila(kayit):
    """Bir seri baglantinin ucus protokolunu guvenli biçimde belirler.

    Protokol soyutlamasinin oto-algilama yuzu. Once (hicbir sey
    gondermeden) gecerli CRC'li MAVLink HEARTBEAT dinlenir; kanit yoksa
    YALNIZ Betaflight'in salt-okunur `MSP_API_VERSION` sorgusu denenir.
    ARM/motor/RC/ayar/reboot/CLI gibi hicbir kumanda uretilmez.

    Donus sozlugu `protokol` alaninda `ardupilot`, `betaflight` ya da
    `bilinmiyor` tasir (bkz. `protokol_algilama.seri_protokol_algila`).
    """
    try:
        from . import protokol_algilama as _pa
    except Exception as e:
        return {"tamam": False, "protokol": "bilinmiyor",
                "hata": "Protokol algilayici yuklenemedi: %s" % e}
    return _pa.seri_protokol_algila(kayit)


class DronServisi(Servis):
    ad = "dron"
    baslik = "Dron Servisi"

    # Guvenli varsayilanlar: `hazirla()` bunlari yeniden atar, ancak
    # servis dogrudan (sinav/teshis) kullanildiginda da komut yonlendirme
    # ve olcum kodu AttributeError vermeden calismalidir.
    kanal = None
    _msp = None

    def hazirla(self):
        self.tampon_dizin = os.path.join(ayar_mod.veri_dizini(),
                                         "telemetri_tampon")
        os.makedirs(self.tampon_dizin, exist_ok=True)
        self.yaz("Telemetri tamponu: %s" % self.tampon_dizin)
        p = seri_portlar()
        if p:
            self.yaz("Yerel seri portlar: %s"
                     % ", ".join(x["port"] for x in p), "basari")
        else:
            try:
                import serial          # noqa: F401
                self.yaz("Yerel seri port bulunamadi (takili cihaz yok)",
                         "uyari")
            except Exception:
                self.yaz("pyserial kurulu degil; seri port listesi "
                         "sinirli. Kurmak icin: pip install pyserial",
                         "uyari")
        self._son_bildirim = 0.0

        # --- Protokol soyutlamasi (Faz 5) -----------------------------
        # Panel/merkez komutlari bu surece `servis_kanal` uzerinden iner
        # (GCSDUAL ile ayni desen). Kanal yoksa (elle calistirma) servis
        # yine calisir; komut yalnizca islenmez.
        try:
            self.kanal = _sk.ServisKanali()
        except Exception as e:
            self.kanal = None
            self.yaz("Komut kanali kurulamadi: %s" % e, "uyari")
        if self.kanal is not None and self.kanal.etkin():
            self.yaz("Protokol komut kanali etkin (algilama + Betaflight "
                     "MSP komutlari bu surece iner).", "basari")

        # Salt-okunur Betaflight MSP oturum yoneticisi. MAVLink yolu bundan
        # BAGIMSIZDIR ve degismeden merkezdeki Baglanti Yoneticisi
        # uzerinden yurur; bu yonetici yalnizca MSP (betaflight) yolunu
        # ekler. Surucu YAZMA komutu uretemez.
        self._msp = None

    def _msp_yonetici(self):
        """MSP yoneticisini gec yaratir (yalniz gerekince).

        Betaflight surucusu yalniz bir baglanti betaflight olarak
        algilandiginda/kullanildiginda gerekir; her dron servisinin onu
        pesinen kurmasi gereksizdir.
        """
        if self._msp is None:
            from .betaflight_msp import BetaflightMspYonetici
            self._msp = BetaflightMspYonetici(
                konsol=lambda etiket, metin, seviye="bilgi":
                    self.yaz("%s: %s" % (etiket, metin), seviye))
        return self._msp

    def _tampon_dosyalari(self):
        return sorted(glob.glob(os.path.join(self.tampon_dizin, "*.jsonl")))

    def _bekleyen_ornek(self):
        n = 0
        for y in self._tampon_dosyalari():
            try:
                with open(y, "r", encoding="utf-8", errors="replace") as f:
                    n += sum(1 for _ in f)
            except Exception:
                pass
        return n

    def dongu(self):
        self.yaz("Dron servisi hazir. Baglanti tanimlari merkezdeki "
                 "Baglanti Yoneticisi'nden yonetilir.", "basari")
        self._olcum_yaz()
        son_olcum = time.time()
        while not self.durdur_istendi():
            simdi = time.time()
            # Protokol/MSP komutlarini yokla. Beklemeden ONCE yapilir ki
            # panelden gelen "protokolu algila" komutu 5 sn'ye kadar
            # gecikmesin.
            self._komutlari_isle()
            # Olcum dosyasi KONSOL bildiriminden daha sik guncellenir:
            # panel ve merkez bunu canli gosterge olarak okur, 30 sn
            # gecikme kullaniciya "donmus" izlenimi verir.
            if simdi - son_olcum >= 5.0:
                son_olcum = simdi
                self._olcum_yaz()
            if simdi - self._son_bildirim >= 30.0:
                self._son_bildirim = simdi
                bekleyen = self._bekleyen_ornek()
                p = len(seri_portlar())
                msp = self._msp_oturum_sayisi()
                self.yaz("Durum: %d yerel seri port, %d bekleyen telemetri "
                         "ornegi, %d Betaflight MSP oturumu"
                         % (p, bekleyen, msp))
            self._bekle_komutlu(DONGU_ARALIK_SN)

    def _bekle_komutlu(self, sn):
        """Beklerken komut yoklar. Kanal yoksa duz bekleme yapar.

        Beklerken de komut yoklanir; aksi halde "protokolu algila" veya
        "MSP baslat" komutu bir sonraki donguye (5 sn) kadar gecikir.
        """
        if not (self.kanal is not None and self.kanal.etkin()):
            return self.bekle(sn)
        bitis = time.time() + float(sn)
        while not self.durdur_istendi():
            kalan = bitis - time.time()
            if kalan <= 0:
                return self.durdur_istendi()
            if self.bekle(min(0.25, kalan)):
                return True
            self._komutlari_isle()
        return self.durdur_istendi()

    # -----------------------------------------------------------------
    # Komut kanali (panel/merkez -> bu surec)
    # -----------------------------------------------------------------
    def _komutlari_isle(self):
        k = self.kanal
        if not (k is not None and k.etkin()):
            return
        for komut in k.oku():
            kid = komut.get("id")
            eylem = str(komut.get("eylem") or "")
            veri = komut.get("veri") or {}
            try:
                tamam, hata, cikti = self._komut_uygula(eylem, veri)
            except Exception as e:
                tamam, hata, cikti = False, "%s: %s" % (
                    type(e).__name__, e), {}
            k.yanit(kid, tamam, hata, cikti)

    def _komut_uygula(self, eylem, veri):
        """Tek protokol komutunu uygular. Donus: `(tamam, hata, veri)`.

        Desteklenen eylemler (hepsi SALT-OKUNUR):

          * `protokol_algila` : {port, baud, tur} -> ardupilot/betaflight
          * `msp_baslat`      : {id, port, baud, ucus_yazilimi, tur}
          * `msp_durdur`      : {id}
          * `msp_durum`       : (arguman yok) -> tum MSP oturum durumlari

        MAVLink/ArduPilot baglantilari BU KANALDAN yonetilmez: onlar
        merkezdeki Baglanti Yoneticisi'nde bugune kadarki gibi yurur.
        """
        eylem = str(eylem or "").lower()

        if eylem == "protokol_algila":
            kayit = dict(veri or {})
            kayit.setdefault("tur", "seri")
            sonuc = protokol_algila(kayit)
            return (bool(sonuc.get("tamam")), str(sonuc.get("hata") or ""),
                    sonuc)

        if eylem == "msp_baslat":
            kayit = dict(veri or {})
            kayit.setdefault("tur", "seri")
            kayit.setdefault("ucus_yazilimi", "betaflight")
            tamam, hata = self._msp_yonetici().baslat(kayit)
            return bool(tamam), str(hata or ""), {
                "baglanti_id": kayit.get("id")}

        if eylem == "msp_durdur":
            if self._msp is None:
                return True, "", {}
            self._msp.durdur(veri.get("id"))
            return True, "", {"baglanti_id": veri.get("id")}

        if eylem == "msp_durum":
            durumlar = self._msp.durumlar() if self._msp is not None else {}
            return True, "", {"oturumlar": durumlar}

        return False, "Bilinmeyen dron komutu: %s" % eylem, {}

    def _msp_oturum_sayisi(self):
        if self._msp is None:
            return 0
        try:
            return len(self._msp.durumlar())
        except Exception:
            return 0

    def _olcum_yaz(self):
        """Panel ve merkezin okudugu canli olcumleri yazar.

        `dron_sayisi` BURADA YAZILMAZ. Neden: ucus kanallari bu alt
        surecte degil, panel/ajan surecinde tutulur (ham byte'in merkeze
        gidecegi WSS baglantisi orada oldugu icin). Bu surec kanallari
        goremez; buradan 0 yazmak paneldeki gercek sayimi EZER ve
        "Dron: 0" gosterirken ucus surer.

        Sayim `Uygulama.servis_durumu_zengin()` icinde, kanallarin
        gercekten yasadigi yerde yapilir.

        `betaflight_msp` olcumu ise BU surece aittir (MSP oturumlari
        burada yasar), bu yuzden burada yazilir.
        """
        try:
            self.durum_yaz(seri_port=len(seri_portlar()),
                           bekleyen_telemetri=self._bekleyen_ornek(),
                           betaflight_msp=self._msp_oturum_sayisi())
        except Exception:
            pass

    def kapat(self):
        self.yaz("Ucus baglantilari kapatiliyor")
        # Salt-okunur MSP oturumlari acikta kalmasin: seri portlar
        # birakilmali ki servis yeniden baslatilinca "port mesgul"
        # hatasi cikmasin.
        if self._msp is not None:
            try:
                self._msp.kapat()
            except Exception:
                pass


if __name__ == "__main__":
    calistir(DronServisi)
