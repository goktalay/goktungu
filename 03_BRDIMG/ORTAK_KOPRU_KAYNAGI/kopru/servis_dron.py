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
"""
import glob
import json
import os
import time

from . import ayar as ayar_mod
from .servis_temel import Servis, calistir

DONGU_ARALIK_SN = 5.0
TAMPON_DAKIKA_SN = 60.0


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


class DronServisi(Servis):
    ad = "dron"
    baslik = "Dron Servisi"

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
                self.yaz("Durum: %d yerel seri port, %d bekleyen telemetri "
                         "ornegi" % (p, bekleyen))
            self.bekle(DONGU_ARALIK_SN)

    def _olcum_yaz(self):
        """Panel ve merkezin okudugu canli olcumleri yazar.

        `dron_sayisi` BURADA YAZILMAZ. Neden: ucus kanallari bu alt
        surecte degil, panel/ajan surecinde tutulur (ham byte'in merkeze
        gidecegi WSS baglantisi orada oldugu icin). Bu surec kanallari
        goremez; buradan 0 yazmak paneldeki gercek sayimi EZER ve
        "Dron: 0" gosterirken ucus surer.

        Sayim `Uygulama.servis_durumu_zengin()` icinde, kanallarin
        gercekten yasadigi yerde yapilir.
        """
        try:
            self.durum_yaz(seri_port=len(seri_portlar()),
                           bekleyen_telemetri=self._bekleyen_ornek())
        except Exception:
            pass

    def kapat(self):
        self.yaz("Ucus baglantilari kapatiliyor")


if __name__ == "__main__":
    calistir(DronServisi)
