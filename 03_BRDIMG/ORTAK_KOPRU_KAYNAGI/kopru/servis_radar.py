# -*- coding: utf-8 -*-
"""KOPRU YAZILIMI — RADAR SERVISI (C20).

## KULLANICI ISTEGI (birebir)

    "radar ve ground control dual dedigimiz yer kontrol istasyonu, bu
     ikiside sunucu yazilimi icinde olmali, kopru olarak cikmali,
     arayuzde Goktungu menusunun altinda eger online ise gorunmeli, ayni
     zamanda radar menusude radar online ise gorunmeli"

ve KUSUR bildirimi:

    "radarda da ayni sorun var, radarin kopru yazilimi calisiyor ama
     sistem radari sunucuda ariyor"

## GOREVI

Saha makinesine bagli C20 tarama radarina TCP ile baglanir, iz verisini
cozer ve merkeze aktarir. Radar ayarlari (frekans / esikler / calisma
modu) ve RTK konum istegi de BURADA uygulanir.

## NEDEN MERKEZDE DEGIL KOPRUDE

Radar donanimi sahadaki YEREL agda durur (ornegin 192.168.8.186).
Merkez sunucu bu ozel ag adresine ULASAMAZ; merkezde kosan bir istemci
sonsuza kadar "timed out" verir — kullanicinin gordugu ekran tam olarak
buydu. Bu yuzden C20 oturumu SAHADA kurulur; merkeze yalniz cozumlenmis
durum ve iz verisi cikar.

## ONCEKI SURUMUN UC EKSIGI (v1.4.3 ve oncesi)

Bu servis onceden yalniz bir "canlilik" gostergesiydi:

1. **Protokol yoktu.** Sokete baglanip SATIR BAZLI JSON okumaya
   calisiyordu. C20 ise ikili cerceve konusur (0x55AA55AA + CRC16).
   LOGIN gonderilmedigi icin radar zaten iz yayinlamiyordu; okunan
   "iz sayisi" her zaman 0 kaliyordu.
2. **Izler merkeze hic cikmiyordu.** Bulunan sayi yalniz kendi
   konsoluna yaziliyordu; merkezdeki harita bu servisten tek bir hedef
   almiyordu.
3. **Adres sabitti.** Hedef IP yalniz ortam degiskeninden okunuyordu;
   panelden girilen IP/port servise ULASAMIYORDU.

Bu surum ucunu birlikte giderir: gercek C20 istemcisi (`radar_c20`)
sahada kosar, durum+izler `durum_yaz` ile merkeze cikar, panel
komutlari `ServisKanali` uzerinden gelir.

## MERKEZE NE GONDERILIR

`durum_yaz` her dongude su alanlari yazar:

  * `radar_durum`  : C20 istemcisinin tam durum sozlugu (baglanti,
                     saglik, RTK ilerlemesi, hata metni)
  * `radar_ayarlar`: radardan OKUNAN calisma ayarlari
  * `izler`        : cografi konuma cevrilmis hedef listesi
  * `radar_bagli`  : menu gorunurlugu icin tek bayrak

## IZ YAZIM SIKLIGI

Izler saniyede birkac kez yenilenir; her TRACK cercevesinde dosya
yazmak diski gereksiz yorar. Bu yuzden yazim `IZ_YAZIM_SN` ile
sinirlandirilmistir (varsayilan 0.5 sn = 2 Hz). Radar izleri 3 sn
zaman asimina sahip oldugu icin 2 Hz gorsel surekliligi korur.

## DURUM BILDIRIMI: "CALISIYOR" ILE "BAGLI" AYRI SEYLERDIR

Servis surecinin ayakta olmasi radarin bagli oldugunu GOSTERMEZ (kablo
cikmis olabilir). Menu gorunurlugu `radar_bagli` uzerinden karara
baglanir; aksi halde kablosu cikmis bir radar yuzunden operatore bos
bir radar ekrani gosterilir ve bu, olmayan bir hedefi aramaya yol acar.

## SERVIS KENDI BASINA BAGLANMAZ (v1.5.4 — KULLANICI ISTEGI)

    "neden radar koprusu 192.168.8.186'ya baglanmaya calisiyor, radar
     ben merkez yazilimdan hangi ipye baglan dersem o ipye baglanmali,
     kopru kendisine baglan komutu gelmeden baglanmamali"

Onceki surumlerde `hazirla()` sonunda kod gomulu `192.168.8.186`
adresine baglanmayi DENIYORDU. Bu davranis yanlisti:

1. **Operatorun niyeti degil, kodun varsayimi uygulaniyordu.** Radar
   baska bir adreste (ornek 192.168.1.50) ise servis her acilista
   yanlis adresi yokluyor, panelde sebepsiz "timed out / hata" cikiyor
   ve operator kendi girmedigi bir IP'yi gormenin sasirticiligini
   yasiyordu.
2. **Sahada baskasinin cihazina istek gidebilir.** Gomulu adres o agda
   bambaska bir cihaza ait olabilir; radar olmayan bir uca TCP oturumu
   acmak kabul edilemez.
3. **Hata sayaci kirlenir.** Baglanti kurulamadigi surece istemci
   yeniden deneme dongusune girer, gunluk dolar ve gercek hatalar
   gorunmez olur.

Artik servis acildiginda **kapali** durumda bekler. Baglanti YALNIZCA
iki kaynaktan baslar:

  * merkezden gelen `baglan` komutu (operatorun girdigi IP/port), veya
  * daha once ayni komutla baglanilmis bir adresin kalici kaydi
    (asagiya bakin).

## SON ADRES NEDEN HATIRLANIR

Otomatik baglanmayi tumuyle kaldirmak, saha makinesi yeniden
baslatildiginda radari sessizce kapali birakirdi; operatorun panele
girip her seferinde ayni IP'yi yeniden yazmasi beklenemez.

Bu yuzden `baglan` komutu geldiginde adres `radar_son_ip` /
`radar_son_port` olarak kalici ayara yazilir ve servis bir sonraki
acilista YALNIZCA bu adresi kullanir. Aradaki ayrim onemlidir: bu, kod
icine gomulu bir varsayim degil, **operatorun daha once verdigi komutun
kendisidir**. Hic komut verilmemisse hicbir adres denenmez.

`kes` komutu bu kaydi siler; operator baglantiyi bilerek kestiyse
yeniden baslatma onu geri getirmemelidir.

Ortam degiskeni (`GOKTUNGU_RADAR_IP`) yalnizca sinav ve ozel kurulum icin
kalir; ayarlanmissa kalici kayit gibi davranir. Varsayilan olarak
TANIMSIZDIR.
"""
import json
import os
import tempfile
import threading
import time

from .radar_c20 import (
    RADAR_IZ_ZAMANASIMI, RADAR_VARSAYILAN_PORT,
    RadarIstemcisi,
)
from .servis_kanal import ServisKanali
from .servis_temel import Servis, calistir

# Yalnizca PORT icin varsayilan vardir: operator merkezde IP yazar,
# port alanini cogu zaman bos birakir ve C20 hep 5001 konusur.
# IP icin VARSAYILAN YOKTUR: adres bilinmiyorsa hicbir yere baglanilmaz
# (bkz. modul basligi "SERVIS KENDI BASINA BAGLANMAZ").
VARSAYILAN_PORT = RADAR_VARSAYILAN_PORT

IZ_YAZIM_SN = 0.5          # merkeze iz yazim araligi (2 Hz)
KONSOL_BILDIRIM_SN = 30.0  # konsola ozet yazim araligi
DONGU_SN = 0.2             # komut yoklama araligi


class RadarServisi(Servis):
    ad = "radar"
    baslik = "Radar Servisi"

    # -----------------------------------------------------------------
    def hazirla(self):
        self.kanal = ServisKanali()
        self._ayar_kilidi = threading.Lock()
        self._ayarlar = {}
        self._ayar_yolu = self._ayar_yolu_bul()
        self._ayar_yukle()

        self.istemci = RadarIstemcisi(
            yaz=self.yaz,
            ayar_oku=self._ayar_oku,
            ayar_yaz=self._ayar_yaz,
        )
        self.istemci.ayar_yukle()

        self._son_iz_yazim = 0.0
        self._son_konsol = 0.0

        # Baslangic adresi UC kaynaktan gelebilir; hicbiri yoksa
        # baglanti KURULMAZ. Sira onemlidir: ortam degiskeni ozel
        # kurulum/sinav icindir ve en yuksek onceliktedir.
        a = self._ayar_oku()
        self._istek_ip = str(os.environ.get("GOKTUNGU_RADAR_IP")
                             or a.get("radar_son_ip") or "").strip()
        try:
            self._istek_port = int(os.environ.get("GOKTUNGU_RADAR_PORT")
                                   or a.get("radar_son_port")
                                   or VARSAYILAN_PORT)
        except (TypeError, ValueError):
            self._istek_port = VARSAYILAN_PORT

        self.yaz("C20 radar istemcisi hazir")
        if self.kanal.etkin():
            self.yaz("Panel komut kanali etkin (baglan / ayar / RTK)")
        else:
            self.yaz("Panel komut kanali yok; merkezden baglan komutu "
                     "alinamayacak", "uyari")

        if self._istek_ip:
            # Bu adres kodun varsayimi DEGIL; operatorun daha once
            # merkezden verdigi baglan komutunun kalici kaydidir.
            kaynak = ("ortam degiskeni"
                      if os.environ.get("GOKTUNGU_RADAR_IP")
                      else "son kullanilan adres")
            self.yaz("Baglaniliyor (%s): %s:%d"
                     % (kaynak, self._istek_ip, self._istek_port))
            self._baglan(self._istek_ip, self._istek_port)
        else:
            # KASITLI: hicbir adrese baglanilmaz. Radarin adresi
            # merkezden bildirilmeden TCP oturumu acmak, sahada baska
            # bir cihazi yoklamak anlamina gelir.
            self.yaz("Radar adresi henuz bildirilmedi; merkezden "
                     "'Radara baglan' komutu bekleniyor")

    # -----------------------------------------------------------------
    # Kalici ayar deposu
    #
    # C20 istemcisi merkez surumunde `AyarYoneticisi` kullanir. Koprude
    # o sinif yoktur; radar konumu (RTK ile ogrenilen merkez_lat/lon) ve
    # merkez yonu ofseti bu kucuk JSON dosyasinda tutulur. Dosya veri
    # dizinindedir: Windows'ta C:\ProgramData\Goktungu\Kopru, Ubuntu'da
    # ~/.local/share/goktungu-kopru — ikisi de yukseltmede korunur.
    # -----------------------------------------------------------------
    def _ayar_yolu_bul(self):
        dizin = (os.environ.get("GOKTUNGU_KOPRU_VERI_DIZIN")
                 or os.environ.get("GOKTUNGU_KOPRU_KANAL_DIZIN") or "")
        if not dizin:
            durum = os.environ.get("GOKTUNGU_KOPRU_DURUM_DOSYASI") or ""
            dizin = os.path.dirname(durum) if durum else ""
        if not dizin:
            dizin = os.path.join(os.path.expanduser("~"), ".goktungu_kopru")
        try:
            os.makedirs(dizin, exist_ok=True)
        except Exception:
            pass
        return os.path.join(dizin, "radar_ayar.json")

    def _ayar_yukle(self):
        try:
            with open(self._ayar_yolu, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                with self._ayar_kilidi:
                    self._ayarlar = d
        except Exception:
            pass

    def _ayar_oku(self):
        with self._ayar_kilidi:
            return dict(self._ayarlar)

    def _ayar_yaz(self, yeni):
        """Ayarlari birlestirip ATOMIK yazar.

        Atomik yazim gereklidir: RTK konumu yazilirken servis
        durdurulursa yarim dosya kalir ve sonraki acilista radar konumu
        okunamaz — izler haritada yanlis yere dusuor.
        """
        if not isinstance(yeni, dict):
            return
        with self._ayar_kilidi:
            self._ayarlar.update(yeni)
            veri = dict(self._ayarlar)
        self._diske_yaz(veri)

    def _ayar_sil(self, anahtarlar):
        """Verilen anahtarlari kalici ayardan siler (atomik).

        `radar_son_ip` icin gereklidir: bos dize YAZMAK ile anahtari
        SILMEK ayni sey degildir. Bos dize kalirsa acilista
        `a.get("radar_son_ip")` bos doner ve dogru davranilir, ancak
        dosyada olu bir alan birakmak sonraki okuyucuyu yanlis yonlendirir
        ("adres verilmis ama bos mu?"). Anahtari tumuyle kaldirmak niyeti
        acik tutar: adres HIC bildirilmemis.
        """
        if isinstance(anahtarlar, str):
            anahtarlar = (anahtarlar,)
        with self._ayar_kilidi:
            degisti = False
            for k in anahtarlar or ():
                if k in self._ayarlar:
                    self._ayarlar.pop(k, None)
                    degisti = True
            veri = dict(self._ayarlar)
        if degisti:
            self._diske_yaz(veri)

    def _diske_yaz(self, veri):
        gecici = None
        try:
            dizin = os.path.dirname(self._ayar_yolu) or "."
            os.makedirs(dizin, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                    "w", encoding="utf-8", dir=dizin, delete=False,
                    prefix=".radar_ayar_", suffix=".tmp") as f:
                gecici = f.name
                json.dump(veri, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(gecici, self._ayar_yolu)
        except Exception as e:
            try:
                if gecici and os.path.exists(gecici):
                    os.remove(gecici)
            except Exception:
                pass
            self.yaz("Ayar yazilamadi: %s" % e, "uyari")

    # -----------------------------------------------------------------
    # Baglanti
    # -----------------------------------------------------------------
    def _baglan(self, ip, port, hatirla=False):
        """Verilen adrese baglanir. Adres BOSSA hicbir sey yapmaz.

        `hatirla=True` yalnizca merkezden gelen `baglan` komutu icin
        verilir: adres kalici ayara yazilir, boylece saha makinesi
        yeniden baslatildiginda operator ayni IP'yi tekrar yazmak
        zorunda kalmaz. Acilistaki kendi cagrimiz `hatirla=False`
        kullanir; okudugu degeri yeniden yazmasi gereksizdir.
        """
        ip = str(ip or "").strip()
        if not ip:
            # Bos adresle VARSAYILANA DUSMEK, kullanicinin kaldirilmasini
            # istedigi davranisin ta kendisidir. Bunun yerine reddet.
            raise ValueError("radar adresi bos: baglanmak icin merkezden "
                             "IP bildirilmelidir")
        try:
            port = int(port or VARSAYILAN_PORT)
        except (TypeError, ValueError):
            port = VARSAYILAN_PORT
        if not (0 < port < 65536):
            raise ValueError("gecersiz radar portu: %s" % port)
        self._istek_ip, self._istek_port = ip, port
        if hatirla:
            self._ayar_yaz({"radar_son_ip": ip, "radar_son_port": port})
        self.istemci.baglan(ip, port)
        return ip, port

    # -----------------------------------------------------------------
    # Ana dongu
    # -----------------------------------------------------------------
    def dongu(self):
        while not self.durdur_istendi():
            self._komutlari_isle()
            self._merkeze_yaz()
            self._konsol_ozet()
            self.bekle(DONGU_SN)

    def _komutlari_isle(self):
        if not self.kanal.etkin():
            return
        for k in self.kanal.oku():
            kid = k.get("id")
            eylem = str(k.get("eylem") or "")
            veri = k.get("veri") if isinstance(k.get("veri"), dict) else {}
            try:
                sonuc = self._komut_uygula(eylem, veri)
                self.kanal.yanit(kid, True, "", sonuc)
            except Exception as e:
                self.yaz("Komut hatasi (%s): %s" % (eylem, e), "hata")
                self.kanal.yanit(kid, False, str(e))

    def _komut_uygula(self, eylem, veri):
        if eylem == "baglan":
            # Operatorun niyeti: bu adres hatirlanir.
            ip, port = self._baglan(veri.get("ip"), veri.get("port"),
                                    hatirla=True)
            self.yaz("Merkez istegi: baglan %s:%d" % (ip, port))
            return {"ip": ip, "port": port}

        if eylem == "kes":
            self.istemci.kes()
            # Kayit silinir: operator baglantiyi bilerek kestiyse servis
            # yeniden baslatildiginda onu geri getirmemelidir.
            self._ayar_sil(("radar_son_ip", "radar_son_port"))
            self._istek_ip = ""
            self.yaz("Merkez istegi: baglanti kesildi "
                     "(adres kaydi da silindi)")
            return {}

        if eylem == "durum":
            return self._durum_paketi()

        if eylem == "ayar_oku":
            # Radardan GUNCEL degerleri ister; yanit GETREG ile gelir ve
            # bir sonraki durum yaziminda panele ulasir.
            with self.istemci.kilit:
                self.istemci.ayar_kuyruk.append(("oku",))
            return {}

        if eylem == "ayar_yaz":
            a = dict(veri or {})
            # Merkez yonu ofseti RADARA yazilmaz; yerel kalibrasyondur ve
            # iz konumlandirmasinda kullanilir. Kalici olarak saklanir,
            # yoksa servis her yeniden baslatmada sifirlanir ve izler
            # haritada donmus gorunur.
            if a.get("merkez_yonu") is not None:
                try:
                    my = float(a["merkez_yonu"]) % 360.0
                except (TypeError, ValueError):
                    my = 0.0
                with self.istemci.kilit:
                    self.istemci.radar_ayarlar["merkez_yonu"] = my
                self._ayar_yaz({"radar_merkez_yonu": my})
            with self.istemci.kilit:
                self.istemci.ayar_kuyruk.append(("yaz", a))
            self.yaz("Panel istegi: ayarlar yazilacak")
            return {}

        if eylem == "rtk":
            with self.istemci.kilit:
                self.istemci.ayar_kuyruk.append(("rtk",))
            self.yaz("Panel istegi: RTK konumu alinacak")
            return {}

        raise ValueError("bilinmeyen eylem: %s" % eylem)

    # -----------------------------------------------------------------
    # Merkeze bildirim
    # -----------------------------------------------------------------
    def _durum_paketi(self):
        """Merkeze gidecek durum + iz paketi.

        ## IZ YASI NEDEN GORELI GONDERILIR

        Her iz kaydinda `son` alani BU MAKINENIN saatidir. Merkez ise
        izin tazeligini KENDI saatine gore olcer:
        `simdi - h["son"] <= RADAR_IZ_ZAMANASIMI`.

        Iki makinenin saati ayni degildir: saha bilgisayarinda NTP
        olmayabilir, sanal makinede saat kayabilir. Fark ileri ise
        merkez butun izleri ANINDA eskimis sayip suzer (radar calisirken
        harita bos kalir). Fark geri ise izler HIC eskimez ve dusen bir
        hedef haritada sonsuza kadar kalir. Ikisi de sahada kabul
        edilemez.

        Bu yuzden mutlak damga yerine `yas_sn` gonderilir: izin kac
        saniye once gorulduugu, TEK bir makinenin kendi saatiyle
        olculmus goreli degeri. Iki ayri saat hic karsilastirilmaz.

        ## RADAR SUSUNCA IZLER NEDEN BURADA SILINIR

        C20 istemcisi eski izleri YALNIZ yeni bir TRACK cercevesi
        isledigi anda temizler (`radar_c20.py`, UPLOAD_TRACK dali). Radar
        susarsa -- kablo cikar, radar kapanir, ag kopar -- yeni cerceve
        HIC gelmez, dolayisiyla temizlik kodu hic kosmaz ve son gorulen
        hedefler haritada SONSUZA KADAR kalir.

        Sahada bu, operatorun artik var olmayan bir hedefe gore karar
        vermesi demektir; angajman motoru da ayni listeyi okudugu icin
        hayalet bir ize kilitlenebilir. Bu yuzden eskitme, veri akisina
        DEGIL zamana baglanir: paket her uretildiginde yasi gecmis izler
        suzulur. Yalnizca suzmekle kalmayip kaynak sozlukten de silinir,
        aksi halde bellek sinirsiz buyur.
        """
        simdi = time.time()
        with self.istemci.kilit:
            durum = dict(self.istemci.durum)
            ayarlar = dict(self.istemci.radar_ayarlar)
            eskiler = []
            izler = []
            for tid, v in self.istemci.hedefler.items():
                k = dict(v)
                try:
                    yas = max(0.0, simdi - float(k["son"]))
                except (TypeError, ValueError, KeyError):
                    yas = 0.0
                if yas > RADAR_IZ_ZAMANASIMI:
                    eskiler.append(tid)
                    continue
                k["yas_sn"] = round(yas, 3)
                izler.append(k)
            for tid in eskiler:
                self.istemci.hedefler.pop(tid, None)
        # v2.1.0: "baglanti yok" iki cok farkli durumu ayni gosteriyordu:
        # (a) adres henuz bildirilmedi, (b) adres verildi ama cihaza
        # ulasilamiyor. Ilki normal bir bekleme halidir, ikincisi bir
        # arizadir. Merkez ikisini ayirt edemezse operatore "radar
        # cevrimdisi" gibi gorunur ve gercekte yapmasi gereken sey -
        # IP adresi girmek - hic akla gelmez.
        return {"radar_durum": durum, "radar_ayarlar": ayarlar,
                "izler": izler,
                "radar_bagli": durum.get("durum") == "bagli",
                "radar_adres_bekleniyor": not bool(self._istek_ip),
                "iz_sayisi": len(izler)}

    def _merkeze_yaz(self):
        simdi = time.time()
        if simdi - self._son_iz_yazim < IZ_YAZIM_SN:
            return
        self._son_iz_yazim = simdi
        p = self._durum_paketi()
        self.durum_yaz(**p)

    def _konsol_ozet(self):
        simdi = time.time()
        if simdi - self._son_konsol < KONSOL_BILDIRIM_SN:
            return
        self._son_konsol = simdi
        with self.istemci.kilit:
            d = self.istemci.durum.get("durum")
            hata = self.istemci.durum.get("hata")
            hiz = self.istemci.durum.get("veri_hizi")
            n = len(self.istemci.hedefler)
        satir = "Durum: %s, %d iz, %.1f mesaj/sn" % (d, n, hiz or 0.0)
        if d == "hata" and hata:
            satir += " (%s)" % hata
        self.yaz(satir, "uyari" if d != "bagli" else "bilgi")

    # -----------------------------------------------------------------
    def kapat(self):
        try:
            self.istemci.kes()
        except Exception:
            pass
        # Servis durdugunda merkez "bagli" gormeye devam etmemeli:
        # menu acik kalir ve operator olmayan bir radara guvenir.
        try:
            self.durum_yaz(radar_bagli=False, iz_sayisi=0, izler=[],
                           radar_durum={"durum": "kapali", "ip": "",
                                        "port": 0, "hata": ""},
                           radar_ayarlar={})
        except Exception:
            pass
        self.yaz("Radar oturumu kapatildi")


if __name__ == "__main__":
    calistir(RadarServisi)
