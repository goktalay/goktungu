# -*- coding: utf-8 -*-
"""KOPRU YAZILIMI — AKIS KANALLARI (ham MAVLink byte tasima).

## NEDEN BU MODUL VAR

Ucus donanimi kullanicinin bilgisayarinda, GOKTUNGU ise merkezde calisir.
Merkez sahaya baglanamaz (NAT). Dolayisiyla MAVLink trafigi SAHADAN
merkeze dogru tasinmalidir.

Iki yol vardi:

  A) Kopru MAVLink'i cozer, telemetriyi JSON olarak merkeze yollar.
  B) Kopru YALNIZ BYTE tasir; cozumleme merkezde kalir.

(B) secildi. Nedeni tek bir cumlede: `goktungu/goktungu/dron.py` icindeki
`_dongu` islevi HEARTBEAT/PARAM_VALUE/LOG_DATA/MISSION_REQUEST
protokollerini, sysid esleme tablosunu, UDP yayin koprusunu ve dron
modelini yonetir. (A) secilseydi bu mantigin BIR KOPYASI koprude de
yasardi; birinde duzeltilen kusur digerinde yasamaya devam eder ve
kusur yalniz sahada gorunurdu. Ayrica komut yonu (arm, takeoff, gorev
yukleme) MAVLink'in kendi paketleriyle akar; JSON'a cevirmek her komut
turu icin ayri bir cevirici yazmak demektir.

## KANAL

Bir kanal = bir ucus baglantisi. Kanal acildiginda `pymavlink` DEGIL,
dogrudan isletim sistemi soketi/seri portu kullanilir:

    seri  -> pyserial
    tcp   -> socket.create_connection
    udp   -> UDP dinleyici (udpin)

`pymavlink` kullanilmaz cunku burada paket COZULMEZ. Ham byte okunur ve
oldugu gibi merkeze aktarilir. Bu, koprunun `pymavlink` bagimliligini
tasimamasini da saglar (tek zorunlu bagimlilik `websockets`).

## TAMPONLAMA VE PARTILEME

MAVLink 10 Hz telemetride ~50-100 kucuk paket/sn uretir. Her byte
dizisini ayri WSS mesaji olarak gondermek, mesaj basina JSON+base64
yukunu (~80 byte) faydali yuke (~40 byte) baskin hale getirir. Bu
yuzden okunan byte'lar KISA bir pencerede (varsayilan 20 ms)
biriktirilip tek pakette gonderilir. 20 ms, MAVLink komut gecikmesi
icin fark edilmezdir (ArduPilot HEARTBEAT araligi 1000 ms) ama mesaj
sayisini 5-10 kat dusurur.
"""
import base64
import os
import socket
import threading
import time

# Okuma penceresi: bu sure boyunca biriken byte'lar tek pakette gider.
PARTI_PENCERE_SN = 0.02
# Tek pakette gonderilecek en fazla byte. MAVLink v2 azami cerceve 280
# byte; 8 KB ~ 29 cerceve. Daha buyugu gecikmeyi artirir, faydasi yok.
PARTI_ENUST_BYTE = 8192
# Okuma tamponu. 4 KB, seri portta bir okuma cagrisinda gelebilecek
# azami veriden fazlasidir; daha buyuk tampon bellek israfidir.
OKUMA_TAMPON = 4096
SERI_ZAMAN_ASIMI_SN = 0.05

# --- Kesinti tamponu -----------------------------------------------
# Merkez erisilemezken ham byte diske yazilir. Tek dosyanin azami
# boyutu: bir dosya bozulursa kaybedilen bolum sinirli kalsin.
KESINTI_DOSYA_ENUST_BYTE = 8 * 1024 * 1024        # 8 MB/dosya
# Kanal basina azami toplam. 10 Hz MAVLink ~4 KB/sn uretir; 128 MB
# yaklasik 9 saatlik kesintiye karsilik gelir. Sinirsiz birakmak,
# gunler suren bir merkez arizasinda kullanicinin diskini doldurur.
KESINTI_KANAL_ENUST_BYTE = 128 * 1024 * 1024      # 128 MB/kanal


class AkisHatasi(Exception):
    """Kanal acilamadi/yazilamadi; mesaj kullaniciya gosterilir."""


class Kanal:
    """Tek bir ucus baglantisinin iki yonlu byte kanali.

    Kanal, iki bagimsiz yonu ayri ele alir:

      OKUMA  : arka plan is parcacigi, donanimdan okur, `gonder`
               cagrilabilirini cagirir (merkeze gider)
      YAZMA  : `yaz()` cagrisi, merkezden gelen byte'i donanima basar

    Yazma icin ayri is parcacigi YOKTUR: merkezden gelen komutlar
    seyrektir (arm, mod degistir, gorev yukle) ve dogrudan yazmak
    gecikmeyi en aza indirir. Okuma ise sureklidir, bu yuzden kendi
    is parcacigina ihtiyac duyar.
    """

    def __init__(self, kanal_id, tanim, gonder, gunluk=None):
        """
        kanal_id: merkezin bu kanali tanimladigi sayi
        tanim   : {"tur": "seri"|"tcp"|"udp", "port": ..., "host": ...,
                   "baud": ...}
        gonder  : gonder(kanal_id, bytes) -> merkeze aktarir
        gunluk  : gunluk(metin, seviye) -> servis konsoluna yazar
        """
        self.kanal_id = int(kanal_id)
        self.tanim = dict(tanim or {})
        self._gonder = gonder
        self._gunluk = gunluk
        self._dur = threading.Event()
        self._iplik = None
        self._kaynak = None          # seri: Serial, tcp/udp: socket
        self._udp_es = None          # UDP'de karsi tarafin adresi
        self._yazma_kilit = threading.Lock()
        self.acilma_ts = None
        self.son_veri_ts = None
        self.giden_byte = 0          # donanimdan okunup merkeze giden
        self.gelen_byte = 0          # merkezden gelip donanima yazilan
        self.son_hata = ""
        # v1.1.0 kesinti tamponu
        self._kesinti_dosya = None       # acik dosya tutamagi
        self._kesinti_yol = ""           # acik dosyanin yolu
        self._kesinti_dosya_byte = 0     # acik dosyaya yazilan
        self.kesinti_byte = 0            # bu kanal icin diskteki toplam
        self.kesinti_dosya_sayi = 0
        self.kesinti_dusen_byte = 0      # sinir asildigi icin atilan
        self.merkez_kesik = False        # son gonderme basarisiz miydi

    # ------------------------------------------------------------------
    def gunluk(self, metin, seviye="bilgi"):
        if self._gunluk:
            try:
                self._gunluk(metin, seviye)
                return
            except Exception:
                pass
        print("[AKIS] %s" % metin, flush=True)

    def tur(self):
        return str(self.tanim.get("tur") or "").lower()

    def etiket(self):
        t = self.tur()
        if t == "seri":
            return "%s @ %s" % (self.tanim.get("port") or "?",
                                self.tanim.get("baud") or 57600)
        if t == "tcp":
            return "tcp %s:%s" % (self.tanim.get("host") or "127.0.0.1",
                                  self.tanim.get("port") or "?")
        if t == "udp":
            return "udp :%s" % (self.tanim.get("port") or "?")
        return t or "?"

    # ------------------------------------------------------------------
    def ac(self):
        """Donanim kaynagini acar ve okuma is parcacigini baslatir.

        Basarisizlikta `AkisHatasi` YUKSELTIR (sessizce gecmez): merkez
        bu hatayi kullaniciya Baglanti Yoneticisi'nde gosterir. Sessiz
        basarisizlik, pilotun "baglandi" sanip ucmaya calismasina yol
        acar — sahada gercek bir tehlikedir.
        """
        t = self.tur()
        if t == "seri":
            self._seri_ac()
        elif t == "tcp":
            self._tcp_ac()
        elif t == "udp":
            self._udp_ac()
        else:
            raise AkisHatasi("Desteklenmeyen baglanti turu: %s" % (t or "(bos)"))
        self.acilma_ts = time.time()
        self._dur.clear()
        self._iplik = threading.Thread(target=self._okuma_dongusu,
                                       name="akis-%d" % self.kanal_id,
                                       daemon=True)
        self._iplik.start()
        self.gunluk("Kanal %d acildi: %s" % (self.kanal_id, self.etiket()),
                    "basari")

    def _seri_ac(self):
        try:
            import serial
        except ImportError:
            raise AkisHatasi(
                "pyserial kurulu degil; seri baglanti acilamaz. "
                "Kurmak icin: pip install pyserial")
        port = str(self.tanim.get("port") or "").strip()
        if not port:
            raise AkisHatasi("Seri port belirtilmedi.")
        try:
            baud = int(self.tanim.get("baud") or 57600)
        except (TypeError, ValueError):
            baud = 57600
        try:
            self._kaynak = serial.Serial(port, baud,
                                         timeout=SERI_ZAMAN_ASIMI_SN)
        except Exception as e:
            # Sahada en sik iki neden: port baska programda acik
            # (Mission Planner) veya kullanici dialout grubunda degil.
            # Ham hatayi tasimak, cozumu tahmin etmekten iyidir.
            raise AkisHatasi("Seri port acilamadi (%s): %s" % (port, e))

    def _tcp_ac(self):
        host = str(self.tanim.get("host") or "127.0.0.1").strip()
        try:
            port = int(self.tanim.get("port") or 0)
        except (TypeError, ValueError):
            port = 0
        if not port:
            raise AkisHatasi("TCP portu belirtilmedi.")
        try:
            s = socket.create_connection((host, port), timeout=8.0)
        except Exception as e:
            raise AkisHatasi("TCP baglanti kurulamadi (%s:%d): %s"
                             % (host, port, e))
        # Nagle KAPATILIR: MAVLink kucuk paketler gonderir, Nagle bunlari
        # birlestirmek icin bekletir ve komut gecikmesi olusur.
        with_no_delay = getattr(socket, "TCP_NODELAY", None)
        if with_no_delay is not None:
            try:
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass
        s.settimeout(0.2)
        self._kaynak = s

    def _udp_ac(self):
        try:
            port = int(self.tanim.get("port") or 0)
        except (TypeError, ValueError):
            port = 0
        if not port:
            raise AkisHatasi("UDP portu belirtilmedi.")
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception:
            pass
        # 0.0.0.0 dinlenir: telemetri radyosu ya da SITL ayni agdaki
        # baska bir makinede olabilir. Yalniz 127.0.0.1 dinlemek, sahada
        # "baglanti yok" hatasinin en sik sebebidir.
        try:
            s.bind(("0.0.0.0", port))
        except Exception as e:
            raise AkisHatasi("UDP port dinlenemedi (%d): %s" % (port, e))
        s.settimeout(0.2)
        self._kaynak = s

    # ------------------------------------------------------------------
    def _okuma_dongusu(self):
        """Donanimdan okur, kisa pencerede biriktirir, merkeze yollar."""
        t = self.tur()
        parti = bytearray()
        pencere_baslangic = time.time()
        while not self._dur.is_set():
            veri = b""
            try:
                if t == "seri":
                    veri = self._seri_oku()
                elif t == "tcp":
                    veri = self._tcp_oku()
                else:
                    veri = self._udp_oku()
            except _Kapandi as e:
                self.son_hata = str(e)
                self.gunluk("Kanal %d kaynagi kapandi: %s"
                            % (self.kanal_id, e), "uyari")
                break
            except Exception as e:
                self.son_hata = "%s: %s" % (type(e).__name__, e)
                self.gunluk("Kanal %d okuma hatasi: %s"
                            % (self.kanal_id, self.son_hata), "uyari")
                time.sleep(0.2)
                continue
            if veri:
                parti.extend(veri)
                self.son_veri_ts = time.time()
            simdi = time.time()
            dolu = len(parti) >= PARTI_ENUST_BYTE
            sure_gecti = (simdi - pencere_baslangic) >= PARTI_PENCERE_SN
            if parti and (dolu or sure_gecti):
                gonderilecek = bytes(parti)
                parti = bytearray()
                pencere_baslangic = simdi
                self.giden_byte += len(gonderilecek)
                try:
                    self._gonder(self.kanal_id, gonderilecek)
                    if self.merkez_kesik:
                        # Baglanti donmus: acik kesinti dosyasini kapat
                        # ki dosya bir kesinti aralligini temsil etsin.
                        self.merkez_kesik = False
                        self._kesinti_dosya_kapat()
                        self.gunluk(
                            "Kanal %d: merkez baglantisi dondu"
                            % self.kanal_id, "basari")
                except Exception as e:
                    # Merkez erisilemez. Byte MERKEZE gonderilemez ama
                    # ATILMAZ: ucus kaydinin tam kalmasi kaza
                    # incelemesi icin kritiktir; kesintinin oldugu
                    # saniyeler genellikle en onemli bolumdur.
                    #
                    # Bu byte'lar SONRADAN canli kanaldan merkeze
                    # AKITILMAZ. Akitilirsa merkezdeki `dron.py` onlari
                    # canli telemetri sanir: dron yerde dururken
                    # "uculuyor" gorunur, harita ikonu gecmis konumlar
                    # arasinda ziplar. Bu yuzden diske yazilip ayri bir
                    # gecmis yukleme yolundan tasinir.
                    self.son_hata = "%s: %s" % (type(e).__name__, e)
                    if not self.merkez_kesik:
                        self.merkez_kesik = True
                        self.gunluk(
                            "Kanal %d: merkez erisilemez, ham veri diske"
                            " yaziliyor (%s)" % (self.kanal_id,
                                                 self.son_hata), "uyari")
                    self._kesintiye_yaz(gonderilecek)
            elif not veri:
                # Bosta CPU yakmayi onler; seri/soket zaman asimlari
                # zaten 50-200 ms bekliyor ama UDP'de veri yoksa
                # dongu hizli doner.
                time.sleep(0.005)
        self._kapat_kaynak()

    def _seri_oku(self):
        s = self._kaynak
        if s is None:
            raise _Kapandi("kaynak yok")
        try:
            bekleyen = s.in_waiting
        except Exception:
            bekleyen = 0
        n = max(1, min(bekleyen or 1, OKUMA_TAMPON))
        veri = s.read(n)
        return veri or b""

    def _tcp_oku(self):
        s = self._kaynak
        if s is None:
            raise _Kapandi("kaynak yok")
        try:
            veri = s.recv(OKUMA_TAMPON)
        except socket.timeout:
            return b""
        if veri == b"":
            raise _Kapandi("karsi taraf baglantiyi kapatti")
        return veri

    def _udp_oku(self):
        s = self._kaynak
        if s is None:
            raise _Kapandi("kaynak yok")
        try:
            veri, es = s.recvfrom(OKUMA_TAMPON)
        except socket.timeout:
            return b""
        # UDP'de yazma yonu icin karsi adres GEREKLIDIR ve ancak ilk
        # paket geldiginde bilinir (udpin semantigi). Es adresi her
        # pakette guncellenir: telemetri radyosu yeniden baglanirsa
        # kaynak portu degisir.
        self._udp_es = es
        return veri or b""

    # ------------------------------------------------------------------
    def yaz(self, veri):
        """Merkezden gelen byte'i donanima basar."""
        if not veri:
            return 0
        s = self._kaynak
        if s is None:
            raise AkisHatasi("Kanal kapali")
        t = self.tur()
        with self._yazma_kilit:
            try:
                if t == "seri":
                    n = s.write(veri)
                    try:
                        s.flush()
                    except Exception:
                        pass
                    n = int(n or len(veri))
                elif t == "tcp":
                    s.sendall(veri)
                    n = len(veri)
                else:
                    if self._udp_es is None:
                        # Henuz karsi taraftan paket gelmediyse hedef
                        # bilinmiyor. Sessizce atmak yerine sayilir:
                        # kullanici "komut gitmiyor" derse neden gorunur.
                        return 0
                    s.sendto(veri, self._udp_es)
                    n = len(veri)
            except Exception as e:
                self.son_hata = "%s: %s" % (type(e).__name__, e)
                raise AkisHatasi("Yazma basarisiz: %s" % e)
        self.gelen_byte += n
        return n

    # ------------------------------------------------------------------
    def _kesinti_dizini(self):
        """Bu kanalin kesinti dosyalarinin dizini."""
        from . import ayar as ayar_mod
        y = os.path.join(ayar_mod.veri_dizini(), "akis_kesinti",
                         "kanal_%d" % self.kanal_id)
        os.makedirs(y, exist_ok=True)
        return y

    def _kesintiye_yaz(self, veri):
        """Merkeze gonderilemeyen ham byte'i diske yazar.

        Bicim: ham ikili (base64 DEGIL). Base64 dosya boyutunu %33
        buyutur ve buradaki tek tuketici kendi kodumuzdur; metin
        guvenligi gerekmez. Zaman damgasi ayri bir `.idx` satirinda
        tutulur ki gecmis yukleme dogru zamani bilsin.
        """
        if not veri:
            return
        if self.kesinti_byte >= KESINTI_KANAL_ENUST_BYTE:
            # Sinir asildi: EN YENI veri korunur mu, en eski mi?
            # En yeniyi atiyoruz. Nedeni: kesinti uzunsa kullanici
            # zaten kesintiyi fark etmistir; kesintinin BASLANGICI
            # (ariza aninin hemen oncesi) tanilama icin en degerli
            # bolumdur. Halka tampon yapip basi ezmek, kaza aninin
            # kaydini silmek olurdu.
            self.kesinti_dusen_byte += len(veri)
            return
        try:
            if (self._kesinti_dosya is None
                    or self._kesinti_dosya_byte >= KESINTI_DOSYA_ENUST_BYTE):
                self._kesinti_dosya_kapat()
                ad = "kesinti_%s_%d" % (
                    time.strftime("%Y%m%d_%H%M%S"), self.kanal_id)
                self._kesinti_yol = os.path.join(self._kesinti_dizini(),
                                                 ad + ".bin")
                self._kesinti_dosya = open(self._kesinti_yol, "ab")
                self._kesinti_dosya_byte = 0
                self.kesinti_dosya_sayi += 1
                with open(self._kesinti_yol[:-4] + ".idx", "a",
                          encoding="utf-8") as f:
                    f.write("basladi\t%.3f\t%s\n"
                            % (time.time(), self.etiket()))
            self._kesinti_dosya.write(veri)
            self._kesinti_dosya.flush()
            self._kesinti_dosya_byte += len(veri)
            self.kesinti_byte += len(veri)
        except Exception as e:
            # Diske yazamiyorsak (disk dolu, izin) byte kaybedilir ama
            # UCUS DEVAM ETMELIDIR. Kanali dusurmek, kayit tutmak icin
            # ucusu kesmek olurdu.
            self.kesinti_dusen_byte += len(veri)
            self.son_hata = "kesinti yazilamadi: %s" % e

    def _kesinti_dosya_kapat(self):
        f, self._kesinti_dosya = self._kesinti_dosya, None
        if f is None:
            return
        try:
            f.close()
        except Exception:
            pass
        try:
            if self._kesinti_yol:
                with open(self._kesinti_yol[:-4] + ".idx", "a",
                          encoding="utf-8") as g:
                    g.write("bitti\t%.3f\t%d\n"
                            % (time.time(), self._kesinti_dosya_byte))
        except Exception:
            pass
        self._kesinti_dosya_byte = 0

    # ------------------------------------------------------------------
    def kapat(self):
        self._dur.set()
        i = self._iplik
        if i and i.is_alive():
            i.join(timeout=2.0)
        self._kapat_kaynak()
        self._kesinti_dosya_kapat()
        self.gunluk("Kanal %d kapatildi (%s)" % (self.kanal_id, self.etiket()))

    def _kapat_kaynak(self):
        s, self._kaynak = self._kaynak, None
        if s is None:
            return
        try:
            s.close()
        except Exception:
            pass

    def calisiyor(self):
        return bool(self._iplik and self._iplik.is_alive()
                    and not self._dur.is_set())

    def durum(self):
        return {
            "kanal_id": self.kanal_id,
            "tur": self.tur(),
            "etiket": self.etiket(),
            "calisiyor": self.calisiyor(),
            "acilma_ts": self.acilma_ts,
            "son_veri_ts": self.son_veri_ts,
            "giden_byte": self.giden_byte,
            "gelen_byte": self.gelen_byte,
            "son_hata": self.son_hata,
            # v1.1.0: kesinti tamponu panelde gorunur olmali. Sessiz
            # bir tampon, kullanicinin veri kaybini fark etmemesine yol
            # acar; sayilar gosterilirse "merkez kopuk ama kayit
            # tutuluyor" bilgisi pilota ulasir.
            "merkez_kesik": self.merkez_kesik,
            "kesinti_byte": self.kesinti_byte,
            "kesinti_dosya_sayi": self.kesinti_dosya_sayi,
            "kesinti_dusen_byte": self.kesinti_dusen_byte,
        }


class _Kapandi(Exception):
    """Kaynak normal biçimde kapandı (hata değil, sonlanma)."""


class KanalYoneticisi:
    """Acik kanallari tutar; merkez isteklerini karsilar."""

    def __init__(self, gonder, gunluk=None, enust_kanal=16):
        """
        enust_kanal: es zamanli kanal siniri. Sinirsiz birakilmasi,
        hatali bir merkez dongusunun kullanicinin makinesinde yuzlerce
        soket acmasina yol acar.
        """
        self._gonder = gonder
        self._gunluk = gunluk
        self._enust = int(enust_kanal)
        self._kanallar = {}
        self._kilit = threading.Lock()

    def ac(self, kanal_id, tanim):
        kanal_id = int(kanal_id)
        with self._kilit:
            eski = self._kanallar.get(kanal_id)
            if eski is not None:
                # Ayni kanal yeniden aciliyorsa (kullanici stop/play
                # yaptiysa) eskisi temiz kapatilir. Iki kanal ayni seri
                # portu acamaz; sessiz birakmak "port mesgul" hatasi verir.
                try:
                    eski.kapat()
                except Exception:
                    pass
                self._kanallar.pop(kanal_id, None)
            if len(self._kanallar) >= self._enust:
                raise AkisHatasi("Es zamanli kanal siniri asildi (%d)"
                                 % self._enust)
        k = Kanal(kanal_id, tanim, self._gonder, self._gunluk)
        k.ac()
        with self._kilit:
            self._kanallar[kanal_id] = k
        return k.durum()

    def kapat(self, kanal_id):
        kanal_id = int(kanal_id)
        with self._kilit:
            k = self._kanallar.pop(kanal_id, None)
        if k is None:
            return False
        try:
            k.kapat()
        except Exception:
            pass
        return True

    def tumunu_kapat(self):
        with self._kilit:
            hepsi = list(self._kanallar.values())
            self._kanallar.clear()
        for k in hepsi:
            try:
                k.kapat()
            except Exception:
                pass

    def yaz(self, kanal_id, veri):
        with self._kilit:
            k = self._kanallar.get(int(kanal_id))
        if k is None:
            raise AkisHatasi("Kanal %s acik degil" % kanal_id)
        return k.yaz(veri)

    def temizle_olu(self):
        """Kaynagi kapanmis kanallari listeden duser.

        Okuma is parcacigi kaynak kapandiginda sonlanir ama kanal
        listede kalir. Temizlenmezse `dron_sayisi` olcumu gercek
        durumdan sapar ve merkezde var olmayan dronlar gorunur.
        """
        dusen = []
        with self._kilit:
            for kid, k in list(self._kanallar.items()):
                if not k.calisiyor():
                    self._kanallar.pop(kid, None)
                    dusen.append(kid)
        return dusen

    def durum(self):
        with self._kilit:
            return [k.durum() for k in self._kanallar.values()]

    def etkin_sayi(self):
        with self._kilit:
            return sum(1 for k in self._kanallar.values() if k.calisiyor())


def b64_coz(metin):
    """Merkezden gelen base64 metnini byte'a cevirir.

    Gecersiz veri sessizce b"" dondurur: bozuk tek bir paket yuzunden
    kanalin komple dusmesi, ucus sirasinda kabul edilemez.
    """
    try:
        return base64.b64decode(metin or "", validate=False)
    except Exception:
        return b""


def b64_kur(veri):
    return base64.b64encode(veri or b"").decode("ascii")


def veri_dizini_gecici():
    """Kanal gunlukleri icin dizin (yalniz tanilama amacli)."""
    from . import ayar as ayar_mod
    y = os.path.join(ayar_mod.veri_dizini(), "akis")
    os.makedirs(y, exist_ok=True)
    return y
