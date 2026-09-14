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

        # v2.2.0 (Faz C): COKLU RADAR. Her radar kimligi (radar_id) icin
        # ayri bir C20 istemcisi tutulur; merkez komutlari `radar_id`
        # tasir (verilmezse 1). Kalici kayit `radar_cihazlar` sozlugudur:
        # {"1": {"ip":..., "port":..., "isim":...}, "2": {...}}.
        # Eski tek kayit (`radar_son_ip/port`) 1 numaraya tasinir.
        self.istemciler = {}
        self._istekler = {}      # radar_id -> (ip, port)
        self._son_iz_yazim = 0.0
        self._son_konsol = 0.0

        cihazlar = self._cihaz_kayitlari()
        # Ortam degiskeni ozel kurulum/sinav icindir ve 1 numarali radar
        # icin en yuksek onceliktedir.
        ort_ip = str(os.environ.get("GOKTUNGU_RADAR_IP") or "").strip()
        if ort_ip:
            try:
                ort_port = int(os.environ.get("GOKTUNGU_RADAR_PORT")
                               or VARSAYILAN_PORT)
            except (TypeError, ValueError):
                ort_port = VARSAYILAN_PORT
            cihazlar[1] = dict(cihazlar.get(1) or {}, ip=ort_ip, port=ort_port)

        self.yaz("C20 radar istemcisi hazir (coklu radar; %d kayit)"
                 % len(cihazlar))
        if self.kanal.etkin():
            self.yaz("Panel komut kanali etkin (baglan / ayar / RTK)")
        else:
            self.yaz("Panel komut kanali yok; merkezden baglan komutu "
                     "alinamayacak", "uyari")

        bagli_sayisi = 0
        for rid in sorted(cihazlar):
            k = cihazlar[rid]
            ip = str(k.get("ip") or "").strip()
            if not ip:
                continue
            # Bu adres kodun varsayimi DEGIL; operatorun daha once
            # merkezden verdigi baglan komutunun kalici kaydidir.
            kaynak = ("ortam degiskeni" if (rid == 1 and ort_ip)
                      else "son kullanilan adres")
            try:
                self.yaz("Radar %d baglaniliyor (%s): %s:%s"
                         % (rid, kaynak, ip, k.get("port") or VARSAYILAN_PORT))
                self._baglan(ip, k.get("port"), radar_id=rid)
                bagli_sayisi += 1
            except Exception as e:
                self.yaz("Radar %d baglanamadi: %s" % (rid, e), "uyari")
        if not bagli_sayisi:
            # KASITLI: hicbir adrese baglanilmaz. Radarin adresi
            # merkezden bildirilmeden TCP oturumu acmak, sahada baska
            # bir cihazi yoklamak anlamina gelir.
            self.yaz("Radar adresi henuz bildirilmedi; merkezden "
                     "'Radara baglan' komutu bekleniyor")

    # -----------------------------------------------------------------
    # Coklu radar: kimlik, istemci ve kayit yardimcilari
    # -----------------------------------------------------------------
    @staticmethod
    def _rid(veri):
        """Komut verisindeki radar kimligi; yoksa/gecersizse 1."""
        try:
            rid = int((veri or {}).get("radar_id") or 1)
        except (TypeError, ValueError):
            rid = 1
        return rid if rid > 0 else 1

    def _cihaz_kayitlari(self):
        """Kalici `radar_cihazlar` sozlugu (int anahtarli kopya).

        Eski tek kayit (`radar_son_ip/port`, surum <2.2.0) varsa ve
        1 numara kayitli degilse oraya tasinir; boylece yukseltme
        sonrasi operator IP'yi yeniden girmek zorunda kalmaz.
        """
        a = self._ayar_oku()
        ham = a.get("radar_cihazlar")
        cihazlar = {}
        if isinstance(ham, dict):
            for k, v in ham.items():
                try:
                    rid = int(k)
                except (TypeError, ValueError):
                    continue
                if rid > 0 and isinstance(v, dict):
                    cihazlar[rid] = dict(v)
        eski_ip = str(a.get("radar_son_ip") or "").strip()
        if eski_ip and 1 not in cihazlar:
            try:
                eski_port = int(a.get("radar_son_port") or VARSAYILAN_PORT)
            except (TypeError, ValueError):
                eski_port = VARSAYILAN_PORT
            cihazlar[1] = {"ip": eski_ip, "port": eski_port, "isim": ""}
        return cihazlar

    def _cihaz_kaydet(self, rid, ip=None, port=None, isim=None, sil=False):
        cihazlar = {str(k): v for k, v in self._cihaz_kayitlari().items()}
        anahtar = str(int(rid))
        if sil:
            cihazlar.pop(anahtar, None)
        else:
            k = dict(cihazlar.get(anahtar) or {})
            if ip is not None:
                k["ip"] = str(ip)
            if port is not None:
                k["port"] = int(port)
            if isim is not None:
                k["isim"] = str(isim)[:64]
            cihazlar[anahtar] = k
        self._ayar_yaz({"radar_cihazlar": cihazlar})
        # Eski tek kayit artik yalniz goc icin okunur; yeni yazimdan
        # sonra silinir ki iki kaynak birbirinden kopmasin.
        self._ayar_sil(("radar_son_ip", "radar_son_port"))

    def _ayar_oku_cihaz(self, rid):
        """Radar basina ayar gorunumu.

        1 numarali radar eski duz anahtarlari (merkez_lat/merkez_lon/
        radar_merkez_yonu) kullanir — yukseltmede RTK kalibrasyonu
        korunur. Diger radarlar `radar_<id>_<anahtar>` on ekiyle ayrisir.
        """
        a = self._ayar_oku()
        if int(rid) == 1:
            return a
        on_ek = "radar_%d_" % int(rid)
        sonuc = {k: v for k, v in a.items() if not k.startswith("radar_")}
        for k, v in a.items():
            if k.startswith(on_ek):
                sonuc[k[len(on_ek):]] = v
        # Ortak/duz anahtarlar diger radara SIZMAMALI: 2 numarali radar
        # kendi RTK'sini almadan 1 numaranin konumunu kullanirsa izler
        # yanlis yere duser.
        for k in ("merkez_lat", "merkez_lon", "radar_merkez_yonu"):
            if k not in {kk[len(on_ek):] for kk in a if kk.startswith(on_ek)}:
                sonuc.pop(k, None)
        return sonuc

    def _ayar_yaz_cihaz(self, rid, yeni):
        if not isinstance(yeni, dict):
            return
        if int(rid) == 1:
            self._ayar_yaz(yeni)
            return
        on_ek = "radar_%d_" % int(rid)
        self._ayar_yaz({on_ek + str(k): v for k, v in yeni.items()})

    def _istemci(self, rid, olustur=True):
        rid = int(rid)
        ist = self.istemciler.get(rid)
        if ist is None and olustur:
            ist = RadarIstemcisi(
                yaz=(lambda m, t="bilgi", _r=rid: self.yaz(
                    ("[R%d] " % _r) + str(m), t)),
                ayar_oku=lambda _r=rid: self._ayar_oku_cihaz(_r),
                ayar_yaz=lambda d, _r=rid: self._ayar_yaz_cihaz(_r, d),
            )
            ist.ayar_yukle()
            self.istemciler[rid] = ist
        return ist

    def _birincil_id(self):
        return min(self.istemciler) if self.istemciler else 1

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
    def _baglan(self, ip, port, hatirla=False, radar_id=1, isim=None):
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
        rid = int(radar_id or 1)
        self._istekler[rid] = (ip, port)
        if hatirla:
            self._cihaz_kaydet(rid, ip=ip, port=port, isim=isim)
        self._istemci(rid).baglan(ip, port)
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
        rid = self._rid(veri)

        if eylem == "baglan":
            # Operatorun niyeti: bu adres hatirlanir.
            ip, port = self._baglan(veri.get("ip"), veri.get("port"),
                                    hatirla=True, radar_id=rid,
                                    isim=veri.get("isim"))
            self.yaz("Merkez istegi: radar %d baglan %s:%d" % (rid, ip, port))
            return {"ip": ip, "port": port, "radar_id": rid}

        if eylem == "kes":
            ist = self._istemci(rid, olustur=False)
            if ist is not None:
                ist.kes()
            # Kayit silinir: operator baglantiyi bilerek kestiyse servis
            # yeniden baslatildiginda onu geri getirmemelidir.
            self._cihaz_kaydet(rid, sil=True)
            self._istekler.pop(rid, None)
            self.yaz("Merkez istegi: radar %d baglantisi kesildi "
                     "(adres kaydi da silindi)" % rid)
            return {"radar_id": rid}

        if eylem == "durum":
            return self._durum_paketi()

        if eylem == "cihazlar":
            return {"radarlar": self._cihaz_listesi()}

        if eylem == "ayar_oku":
            # Radardan GUNCEL degerleri ister; yanit GETREG ile gelir ve
            # bir sonraki durum yaziminda panele ulasir.
            ist = self._istemci(rid)
            with ist.kilit:
                ist.ayar_kuyruk.append(("oku",))
            return {"radar_id": rid}

        if eylem == "ayar_yaz":
            a = dict(veri or {})
            a.pop("radar_id", None)
            ist = self._istemci(rid)
            # Merkez yonu ofseti RADARA yazilmaz; yerel kalibrasyondur ve
            # iz konumlandirmasinda kullanilir. Kalici olarak saklanir,
            # yoksa servis her yeniden baslatmada sifirlanir ve izler
            # haritada donmus gorunur.
            if a.get("merkez_yonu") is not None:
                try:
                    my = float(a["merkez_yonu"]) % 360.0
                except (TypeError, ValueError):
                    my = 0.0
                with ist.kilit:
                    ist.radar_ayarlar["merkez_yonu"] = my
                self._ayar_yaz_cihaz(rid, {"radar_merkez_yonu": my})
            with ist.kilit:
                ist.ayar_kuyruk.append(("yaz", a))
            self.yaz("Panel istegi: radar %d ayarlari yazilacak" % rid)
            return {"radar_id": rid}

        if eylem == "rtk":
            ist = self._istemci(rid)
            with ist.kilit:
                ist.ayar_kuyruk.append(("rtk",))
            self.yaz("Panel istegi: radar %d RTK konumu alinacak" % rid)
            return {"radar_id": rid}

        raise ValueError("bilinmeyen eylem: %s" % eylem)

    def _cihaz_listesi(self):
        kayit = self._cihaz_kayitlari()
        cikti = []
        for rid in sorted(set(kayit) | set(self.istemciler)):
            k = kayit.get(rid) or {}
            ist = self.istemciler.get(rid)
            bagli = False
            if ist is not None:
                with ist.kilit:
                    bagli = ist.durum.get("durum") == "bagli"
            cikti.append({"radar_id": rid, "isim": k.get("isim") or "",
                          "ip": k.get("ip") or "", "port": k.get("port") or 0,
                          "bagli": bagli})
        return cikti

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
        kayit = self._cihaz_kayitlari()
        radarlar = {}
        for rid in sorted(set(kayit) | set(self.istemciler)):
            ist = self.istemciler.get(rid)
            k = kayit.get(rid) or {}
            if ist is None:
                radarlar[str(rid)] = {
                    "radar_id": rid, "isim": k.get("isim") or "",
                    "radar_durum": {"durum": "kapali", "ip": k.get("ip") or "",
                                    "port": k.get("port") or 0, "hata": ""},
                    "radar_ayarlar": {}, "izler": [], "radar_bagli": False,
                    "radar_adres_bekleniyor": not bool(k.get("ip")),
                    "iz_sayisi": 0}
                continue
            radarlar[str(rid)] = self._radar_paketi(rid, ist, k, simdi)
        # v2.1.0: "baglanti yok" iki cok farkli durumu ayni gosteriyordu:
        # (a) adres henuz bildirilmedi, (b) adres verildi ama cihaza
        # ulasilamiyor. Ilki normal bir bekleme halidir, ikincisi bir
        # arizadir. Merkez ikisini ayirt edemezse operatore "radar
        # cevrimdisi" gibi gorunur ve gercekte yapmasi gereken sey -
        # IP adresi girmek - hic akla gelmez.
        #
        # v2.2.0 (Faz C): ust duzey alanlar BIRINCIL (en kucuk kimlikli)
        # radarindir — eski Merkez surumleri (2.4.191 ve oncesi) yalniz
        # bunlari okur. Yeni Merkez `radarlar` sozlugunden radar basina
        # okur. `radar_bagli` menu gorunurlugu icindir: herhangi bir
        # radar bagliysa radar menusu acik kalmalidir.
        birincil = radarlar.get(str(self._birincil_id())) or (
            next(iter(radarlar.values())) if radarlar else None)
        if birincil is None:
            birincil = {"radar_durum": {"durum": "kapali", "ip": "", "port": 0,
                                        "hata": ""},
                        "radar_ayarlar": {}, "izler": [], "radar_bagli": False,
                        "radar_adres_bekleniyor": True, "iz_sayisi": 0}
        toplam_iz = sum(int(p.get("iz_sayisi") or 0) for p in radarlar.values())
        return {"radar_durum": birincil["radar_durum"],
                "radar_ayarlar": birincil["radar_ayarlar"],
                "izler": birincil["izler"],
                "radar_bagli": any(p.get("radar_bagli") for p in radarlar.values()),
                "radar_adres_bekleniyor": all(
                    p.get("radar_adres_bekleniyor") for p in radarlar.values()
                ) if radarlar else True,
                "iz_sayisi": toplam_iz,
                "radar_sayisi": len(radarlar),
                "bagli_radar_sayisi": sum(
                    1 for p in radarlar.values() if p.get("radar_bagli")),
                "radarlar": radarlar}

    def _radar_paketi(self, rid, ist, kayit, simdi):
        with ist.kilit:
            durum = dict(ist.durum)
            ayarlar = dict(ist.radar_ayarlar)
            eskiler = []
            izler = []
            for tid, v in ist.hedefler.items():
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
                ist.hedefler.pop(tid, None)
        return {"radar_id": rid, "isim": (kayit or {}).get("isim") or "",
                "radar_durum": durum, "radar_ayarlar": ayarlar,
                "izler": izler,
                "radar_bagli": durum.get("durum") == "bagli",
                "radar_adres_bekleniyor": rid not in self._istekler,
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
        if not self.istemciler:
            return
        for rid in sorted(self.istemciler):
            ist = self.istemciler[rid]
            with ist.kilit:
                d = ist.durum.get("durum")
                hata = ist.durum.get("hata")
                hiz = ist.durum.get("veri_hizi")
                n = len(ist.hedefler)
            satir = "Radar %d durum: %s, %d iz, %.1f mesaj/sn" % (
                rid, d, n, hiz or 0.0)
            if d == "hata" and hata:
                satir += " (%s)" % hata
            self.yaz(satir, "uyari" if d != "bagli" else "bilgi")

    # -----------------------------------------------------------------
    def kapat(self):
        for ist in list(self.istemciler.values()):
            try:
                ist.kes()
            except Exception:
                pass
        # Servis durdugunda merkez "bagli" gormeye devam etmemeli:
        # menu acik kalir ve operator olmayan bir radara guvenir.
        try:
            self.durum_yaz(radar_bagli=False, iz_sayisi=0, izler=[],
                           radar_durum={"durum": "kapali", "ip": "",
                                        "port": 0, "hata": ""},
                           radar_ayarlar={}, radarlar={}, radar_sayisi=0,
                           bagli_radar_sayisi=0)
        except Exception:
            pass
        self.yaz("Radar oturumlari kapatildi")


if __name__ == "__main__":
    calistir(RadarServisi)
