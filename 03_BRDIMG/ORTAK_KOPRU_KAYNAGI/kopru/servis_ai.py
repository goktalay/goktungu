# -*- coding: utf-8 -*-
"""KOPRU YAZILIMI - AI SERVISI.

## KULLANICI ISTEGI (birebir)

    "hem ai icin hem kameralar icin ayni kopru gruplamasi gerekiyor"

    "Birde AI bilgisayarlar bolumunde bilgisayarin ip'si gibi ayni
     zamanda SSH kullanici bilgilerini de isteyelim"

## GOREVI

Saha agindaki AI bilgisayarlarina (goruntu isleme iscilerine) HTTP ile
baglanir: sagliklarini yoklar, izleme gorevi atar, tespit kutularini
toplar ve merkeze YALNIZ ozet bildirir.

## NEDEN MERKEZDE DEGIL KOPRUDE

AI bilgisayarlari saha agindadir (ornegin 192.168.1.100). Merkez sunucu
bir veri merkezindedir ve bu ozel ag adresine ULASAMAZ.

Onceki surumde `ai_izleme_baslat` komutu MERKEZDE kosuyor ve merkezden
`http://{host}:{port}/izle` istegi atiliyordu. Bu istek saha adresine
gittigi icin her zaman zaman asimina dusuyordu. Ayni yol saglik
yoklamasi icin de kullanildigindan, calisan bir AI bilgisayari merkezde
SUREKLI "yanit vermiyor" gorunuyordu.

Ustelik iki nokta birden kopuyordu: iscye verilen akis adresi de
merkezin kendi video vekilini (`gcs_proxy`) gosteriyordu; isci o adrese
de erisemezdi. Artik hem istek hem akis adresi saha agi icinde kalir.

## ONCEKI SURUMUN IKI EKSIGI (v1.4.4 ve oncesi)

Bu servis onceden yalniz bir "canlilik" gostergesiydi:

1. **Isciye hic baglanmiyordu.** Yalnizca yerel GPU/CPU tespiti yapip
   30 saniyede bir "0 etkin izleme gorevi" yaziyordu.
2. **Komut kanalina bagli degildi.** Panelden gelen izleme istegi bu
   servise HIC ulasmiyordu.

## GPU ZORUNLU DEGILDIR

Bu servis kendisi cikarim YAPMAZ; cikarimi AI bilgisayarlari yapar. Yerel
hizlandirici bilgisi yalnizca RAPORLAMA icindir (operator hangi
makinenin ne yetenekte oldugunu gorur). Bu yuzden GPU yoklugu servisi
engellemez.

## MERKEZE NE GONDERILIR

`durum_yaz` her dongude su alanlari yazar:

  * `ai_sunucular` : yoklanan iscilerin cevrimici/yuk/kapasite durumu
  * `ai_gorevler`  : kamera -> isci atamalari
  * `ai_hazir`     : en az bir cevrimici isci var mi
  * `hizlandirici` : bu makinenin yerel hesaplama birimi

Tespit kutulari merkeze DEGIL, ayni makinedeki video servisine gider
(`anotasyon` eylemi): kutular karenin uzerine sahada cizilir, boylece
merkeze ek yuk binmez.

## YEREL AI ISCISI (v1.7.20 / servis 2.1.0)

Kullanici istegi (birebir): "her goruntu baglantisi kendi AI alt
yapisini calistirsin, su anki GRCOFF'daki gibi".

Onceki surumlerde bu servis YALNIZ saha agindaki AYRI bir AI
bilgisayarina baglanabiliyordu. Ayri AI donanimi OLMAYAN sahada AI
hic calismiyordu: operator izleme baslatinca "Tanimli AI sunucusu yok"
uyarisi aliyordu ve yapabilecegi hicbir sey yoktu.

Cozum EN AZ RISKLI yoldan kuruldu: GRCOFF'un isci sureci
(`ai_sunucu.py`) zaten `/izle`, `/durdur`, `/durum` sozlesmesini
konusur ve bu servis TAM O SOZLESMEYI konusur. Bu yuzden protokol
DEGISMEDI; yalnizca ayni isci, kopru kurulumunun ICINDEN `127.0.0.1`
uzerinde baslatilir ve isci listesine EK bir aday olarak yazilir.

Onemli ayrimlar:

  * Uzak AI bilgisayari kayitlari KALDIRILMADI. Operator isterse
    harici AI donanimini kullanmaya devam eder; yerel isci yalnizca
    `_en_az_yuklu` secimine giren fazladan bir adaydir.
  * Yerel isci baslatilamazsa (python/paket/model eksik) servis
    COKMEZ: uyari yazilir ve yalniz uzak iscilerle devam edilir.
  * Isci sureci `kapat()` icinde nazikce sonlandirilir; aksi halde
    kopru durdurulunca port tutulmaya devam eder ve bir sonraki
    baslatma "Address already in use" ile duser.
"""
import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

from .servis_kanal import ServisKanali, komut_yaz
from .servis_temel import Servis, calistir
from .video_vekil import VIDEO_PROXY_PORT

DONGU_SN = 0.2              # komut yoklama araligi
YOKLAMA_ARALIGI_SN = 5.0    # isci saglik yoklamasi araligi
DURUM_YAZIM_SN = 2.0        # merkeze durum yazim araligi
KONSOL_BILDIRIM_SN = 30.0   # konsola ozet yazim araligi
HTTP_ZAMANASIMI = 6.0
YOKLAMA_ZAMANASIMI = 4.0

# ---------------------------------------------------------------------
# YEREL AI ISCISI SABITLERI
# ---------------------------------------------------------------------
# Port SABIT KODLANMAZ: ayni bilgisayarda Merkez Uygulama da kurulu
# olabilir ve o da kendi portlarini acar. Olculen kurulum (bkz.
# surumler.py 1.5.6 kaydi): kopru 8790/8900, merkez 8000/8765/8811/8910.
# Bu yuzden 8811 (merkezin MJPEG vekili) ve 8900 (elle kurulmus tekil
# AI iscisinin varsayilani) BILEREK secilmedi; catisma halinde operator
# ortam degiskeniyle kaydirabilsin diye disaridan da okunur.
YEREL_AI_PORT_ORTAM = "GOKTUNGU_KOPRU_YEREL_AI_PORT"
YEREL_AI_PORT_VARSAYILAN = 8902

# Yerel iscinin kayit kimligi NEGATIFTIR: merkezin veritabani kimlikleri
# daima pozitif oldugu icin cakisma OLANAKSIZDIR. Pozitif bir sabit
# secilseydi (ornegin 9001) merkeze o kimlikle bir AI bilgisayari
# eklendiginde iki kayit birbirini sessizce ezerdi.
YEREL_AI_ID = -1
YEREL_AI_AD = "Yerel AI (Kopru)"
# Es zamanli islenebilecek akis sayisi. Yerel isci kopru ile AYNI
# cekirdekleri paylasir; yuksek deger panelin ve video vekilinin
# tepkisini oldurur. Iki akis, tek kameralik kurulumda bile yedek birak
# ve dort cekirdekli saha bilgisayarini bogmaz.
YEREL_AI_KAPASITE = 2
YEREL_AI_BETIK = "ai_sunucu.py"
# Surec ayaga kalkip portu dinlemeye baslayana kadar beklenecek sure.
# Beklenmezse ilk saglik yoklamasi "cevrimici degil" der ve operator
# yerel iscinin hic calismadigini sanir.
YEREL_AI_HAZIR_SN = 25.0

# ---------------------------------------------------------------------
# 1.7.20 — TESPIT KUTUSU ALICISI
# ---------------------------------------------------------------------
# OLCULEN KUSUR: `ai_sunucu.py` canli tespit kutularini `--ana` adresine
# `POST /ai/kutular` ile gonderir. Koprude `--ana` MERKEZI gosteriyordu;
# dolayisiyla kutular sahadaki video servisine HIC ulasmiyor ve saha
# goruntusune CIZILMIYORDU. `servis_video.py` icindeki `anotasyon`
# eylemi yalnizca izleme durdurulunca (kutulari TEMIZLEMEK icin)
# cagriliyordu -- yani cizim yolu vardi ama besleyeni yoktu.
#
# Cozum: bu servis 127.0.0.1 uzerinde kucuk bir alici acar ve isciye
# `--ana` olarak KENDINI verir. Gelen kutular:
#   1) ayni makinedeki video servisine `anotasyon` komutu olarak yazilir
#      (kare uzerine sahada cizilir -- GRCOFF'taki davranisin aynisi),
#   2) merkez adresi cozulebiliyorsa oraya AYNEN iletilir (eski davranis
#      korunur; merkez paneli kutulari ve tespitleri gormeye devam eder).
# Alici YALNIZ geri donus arayuzunu dinler: saha aginda kimliksiz bir uc
# acmaz.
YEREL_ALICI_PORT_ORTAM = "GOKTUNGU_KOPRU_AI_ALICI_PORT"
YEREL_ALICI_PORT_VARSAYILAN = 8903


class AiServisi(Servis):
    ad = "ai"
    baslik = "AI Servisi"

    # -----------------------------------------------------------------
    def hazirla(self):
        self.kanal = ServisKanali()
        self.kilit = threading.Lock()
        self.sunucular = {}     # sid -> kayit (merkezden gelir)
        self.saglik = {}        # sid -> {cevrimici, son_durum, ts}
        self.gorevler = {}      # kamera_id -> sid
        self.gorev_bilgi = {}   # kamera_id -> {url, protokol, gorevler}

        # Yerel AI iscisi (ai_sunucu.py) alt sureci. `hazirla` icinde
        # kurulur ama ATAMA ONCE yapilir: baslatma basarisiz olsa bile
        # `kapat()` bu alanlari her zaman bulmalidir.
        self.yerel_surec = None
        self.yerel_port = self._yerel_port_coz()
        # Kutu alicisi: isci baslamadan ONCE ayaga kalkar, cunku isciye
        # `--ana` olarak bu alicinin adresi verilir.
        self.alici = None
        self.alici_port = 0
        self.merkez_taban = ""
        self._alici_kur()

        self.hizlandirici = self._hizlandirici_bul()
        self.yaz("Yerel hesaplama birimi: %s" % self.hizlandirici,
                 "basari" if self.hizlandirici != "CPU" else "bilgi")

        # Yerel isci, uzak AI bilgisayarlarindan ONCE ayaga kaldirilir:
        # merkezden gelen ilk `izleme_baslat` komutu geldiginde aday
        # listesinde hazir bulunmali.
        self._yerel_isci_kur()

        self._son_yoklama = 0.0
        self._son_durum = 0.0
        self._son_konsol = 0.0

    # -----------------------------------------------------------------
    # YEREL AI ISCISI
    # -----------------------------------------------------------------
    @staticmethod
    def _yerel_port_coz():
        """Yerel iscinin dinleyecegi portu cozer (ortam > varsayilan)."""
        ham = (os.environ.get(YEREL_AI_PORT_ORTAM) or "").strip()
        if ham:
            try:
                port = int(ham)
                if 1 <= port <= 65535:
                    return port
            except (TypeError, ValueError):
                pass
            # Gecersiz deger SESSIZCE yutulmaz: operator degiskeni
            # yazdigini bilir, calismadigini bilmez.
            return YEREL_AI_PORT_VARSAYILAN
        return YEREL_AI_PORT_VARSAYILAN

    @staticmethod
    def _kopru_koku():
        """Kurulum koku: `<kok>/kopru/servis_ai.py` -> `<kok>`.

        `servisler.paket_koku()` ile ayni sonucu verir; o modul BURADA
        ice aktarilmaz cunku servis surecinde yalniz bu dosya icin
        surec yonetimi siniflarini yuklemek gereksiz yuktur.
        """
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _yerel_ana_adres(self):
        """Iscinin tespit/kutu bildirimi gonderecegi taban adres.

        1.7.20: bu adres artik MERKEZ DEGIL, ayni surecte kosan yerel
        KUTU ALICISIDIR. Kutular once sahadaki video servisine (kare
        uzerine cizim) gider, ardindan cozulebiliyorsa merkeze aynen
        iletilir. Merkezi dogrudan gostermek, sahadaki goruntude kutu
        hic cikmamasi demekti (bkz. YEREL_ALICI_PORT_VARSAYILAN notu).

        Alici kurulamamissa BOS donulur ve `--ana` hic verilmez;
        iscinin kendi varsayilani kullanilir, bildirimler sessizce
        duser ama tespit/izleme calismaya devam eder.
        """
        if self.alici_port:
            return "http://127.0.0.1:%d" % int(self.alici_port)
        return ""

    def _merkez_taban_coz(self):
        """Merkezin HTTP tabani (kutu/tespit iletimi icin).

        Ice aktarim try/except icindedir: `merkez` modulu ayar dosyasini
        okur ve bu servis ayar dosyasi olmadan da (elle calistirma)
        ayaga kalkabilmelidir.
        """
        try:
            from .merkez import _http_taban
            return str(_http_taban() or "").strip().rstrip("/")
        except Exception:                                   # noqa: BLE001
            return ""

    # -----------------------------------------------------------------
    # KUTU ALICISI
    # -----------------------------------------------------------------
    def _alici_kur(self):
        """Yerel kutu/tespit alicisini baslatir. ASLA YUKSELTMEZ."""
        try:
            port = int(os.environ.get(YEREL_ALICI_PORT_ORTAM)
                       or YEREL_ALICI_PORT_VARSAYILAN)
        except (TypeError, ValueError):
            port = YEREL_ALICI_PORT_VARSAYILAN
        self.merkez_taban = self._merkez_taban_coz()
        servis = self

        class _Istek(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_a):      # konsolu bosuna doldurmasin
                pass

            def do_POST(self):
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                except (TypeError, ValueError):
                    n = 0
                # Govde SINIRLANIR: bozuk/kotucul bir istek bellegi
                # tuketmemeli. 2 MB, en kalabalik kutu listesinden kat
                # kat buyuktur.
                if n < 0 or n > 2 * 1024 * 1024:
                    self.send_error(413)
                    return
                ham = self.rfile.read(n) if n else b""
                yol = self.path.split("?")[0]
                if yol == "/ai/kutular":
                    servis._kutulari_isle(ham)
                elif yol != "/ai/tespit":
                    self.send_error(404)
                    return
                servis._merkeze_ilet(yol, ham)
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"ok")

        class _Sunucu(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True
            allow_reuse_address = True

        try:
            # YALNIZ geri donus arayuzu: saha aginda kimliksiz bir uc
            # acmak, disaridan sahte tespit kutusu enjekte edilmesine
            # kapi aralardi.
            self.alici = _Sunucu(("127.0.0.1", port), _Istek)
        except OSError as e:
            self.alici = None
            self.alici_port = 0
            self.yaz("AI kutu alicisi acilamadi (127.0.0.1:%d): %s. "
                     "Tespit kutulari saha goruntusune cizilmeyecek."
                     % (port, e), "uyari")
            return
        self.alici_port = self.alici.server_address[1]
        threading.Thread(target=self.alici.serve_forever,
                         kwargs={"poll_interval": 0.4},
                         name="ai-kutu-alici", daemon=True).start()
        self.yaz("AI kutu alicisi hazir (127.0.0.1:%d)" % self.alici_port)

    def _kutulari_isle(self, ham):
        """Isciden gelen kutulari ayni makinedeki video servisine yazar."""
        try:
            veri = json.loads(ham.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return
        if not isinstance(veri, dict):
            return
        try:
            kamera_id = int(veri.get("kamera_id"))
        except (TypeError, ValueError):
            return
        kutular = veri.get("kutular")
        if not isinstance(kutular, list):
            kutular = []
        dizin = (self.kanal.dizin if self.kanal else "") or os.environ.get(
            "GOKTUNGU_KOPRU_KANAL_DIZIN") or ""
        if not dizin:
            return
        try:
            komut_yaz(dizin, "video", "anotasyon",
                      {"id": kamera_id, "kutular": kutular})
        except Exception:                                   # noqa: BLE001
            # Cizim kritik degildir: yazilamazsa izleme surer.
            pass

    def _merkeze_ilet(self, yol, ham):
        """Gelen bildirimi merkeze AYNEN iletir (eski davranis).

        Merkez adresi yoksa veya ulasilamazsa SESSIZ gecilir: saha
        goruntusundeki cizim bu iletime bagli degildir.
        """
        taban = self.merkez_taban
        if not taban or not ham:
            return
        def _gonder():
            try:
                istek = urllib.request.Request(
                    taban + yol, data=ham,
                    headers={"Content-Type": "application/json"})
                urllib.request.urlopen(istek, timeout=3).read()
            except Exception:                               # noqa: BLE001
                pass
        threading.Thread(target=_gonder, name="ai-kutu-ilet",
                         daemon=True).start()

    def _port_dolu_mu(self):
        """Yerel portu baska bir surec tutuyor mu?

        Dogrudan `Popen` edip beklemek YETERSIZDIR: isci portu alamayinca
        cikar, konsola yigin izi duser ve operator nedeni anlamaz.
        """
        import socket
        yuva = None
        try:
            yuva = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            yuva.settimeout(0.5)
            return yuva.connect_ex(("127.0.0.1", self.yerel_port)) == 0
        except Exception:                                   # noqa: BLE001
            return False
        finally:
            if yuva is not None:
                try:
                    yuva.close()
                except Exception:
                    pass

    def _yerel_kayit(self):
        """Yerel isciyi aday listesine yazar.

        Kayit `_kayit_normalize` SUZGECINDEN GECIRILIR: uzak kayitlarla
        birebir ayni bicimde tutulmasi sarttir, aksi halde
        `_en_az_yuklu` ve `_sunucu_ozet` yerel kayitta eksik alan bulur.
        """
        k = self._kayit_normalize({"id": YEREL_AI_ID, "ad": YEREL_AI_AD,
                                   "host": "127.0.0.1",
                                   "port": self.yerel_port,
                                   "kapasite": YEREL_AI_KAPASITE})
        if not k:
            return None
        with self.kilit:
            self.sunucular[k["id"]] = k
        return k

    def _yerel_isci_kur(self):
        """Yerel AI iscisini baslatir ve aday listesine ekler.

        BU ISLEV ASLA YUKSELTMEZ. Yerel isci bir EK yetenektir; eksik
        python paketi ya da dolu port yuzunden tum AI servisinin (ve
        onunla birlikte uzak AI bilgisayarlarinin) kaybedilmesi kabul
        edilemez.
        """
        try:
            self._yerel_isci_baslat()
        except Exception as e:                              # noqa: BLE001
            self.yaz("Yerel AI iscisi kurulamadi: %s: %s "
                     "(yalniz uzak AI bilgisayarlari kullanilacak)"
                     % (type(e).__name__, e), "uyari")

    def _yerel_isci_baslat(self):
        kok = self._kopru_koku()
        betik = os.path.join(kok, YEREL_AI_BETIK)
        if not os.path.isfile(betik):
            self.yaz("Yerel AI iscisi betigi bulunamadi: %s "
                     "(yalniz uzak AI bilgisayarlari kullanilacak)"
                     % betik, "uyari")
            return

        # Port zaten dinleniyorsa: elle baslatilmis ya da onceki
        # oturumdan kalmis bir isci olabilir. Ikinci bir surec
        # baslatmak anlamsizdir (port alamaz), ama var olani yok
        # saymak da yanlistir: yoklama zaten cevrimici/cevrimdisi
        # kararini verecek.
        if self._port_dolu_mu():
            k = self._yerel_kayit()
            self.yaz("Yerel AI portu %d zaten dinleniyor; yeni surec "
                     "baslatilmadi, var olan isci aday listesine "
                     "eklendi. Port cakismasi varsa %s ortam "
                     "degiskeniyle baska bir port verin."
                     % (self.yerel_port, YEREL_AI_PORT_ORTAM), "uyari")
            if k:
                self._yokla_tek(k)
            return

        yorumlayici = self._yorumlayici()
        if not yorumlayici:
            self.yaz("Yerel AI iscisi icin Python yorumlayicisi "
                     "bulunamadi (yalniz uzak AI bilgisayarlari "
                     "kullanilacak)", "uyari")
            return

        komut = [yorumlayici, betik,
                 "--port", str(self.yerel_port),
                 # YALNIZ geri donus arayuzu: isci disaridan
                 # cagrilmamalidir. Gorevi ayni makinedeki bu servis
                 # atar; 0.0.0.0 dinlemek saha aginda kimliksiz bir
                 # cikarim ucu acardi.
                 "--dinle", "127.0.0.1",
                 "--ad", YEREL_AI_AD,
                 "--tip", "cpu",
                 "--kapasite", str(YEREL_AI_KAPASITE)]
        ana = self._yerel_ana_adres()
        if ana:
            komut += ["--ana", ana]

        ortam = dict(os.environ)
        ortam["PYTHONUNBUFFERED"] = "1"   # cikti panelde aninda gorunsun
        # Kurulum dizini (Program Files / /opt/goktungu/kopru) YAZMAYA
        # KAPALIDIR. `ai_sunucu.py` kayitlarini (ai_kayitlar/) veri
        # kokune yazar; degisken verilmezse kendi dizinine yazmaya
        # calisir ve her tespitte izin hatasi alir.
        try:
            from . import ayar as ayar_mod
            ortam["GOKTUNGU_VERI_KOKU"] = ayar_mod.veri_dizini()
        except Exception:                                   # noqa: BLE001
            pass

        try:
            ek = {}
            if os.name == "posix":
                # Surec grubu: iscinin acacagi torun surecler de
                # birlikte sonlandirilabilsin.
                ek["start_new_session"] = True
            else:
                ek["creationflags"] = getattr(
                    subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            self.yerel_surec = subprocess.Popen(
                komut, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                errors="replace", bufsize=1, env=ortam, cwd=kok, **ek)
        except Exception as e:                              # noqa: BLE001
            self.yerel_surec = None
            self.yaz("Yerel AI iscisi baslatilamadi: %s: %s "
                     "(yalniz uzak AI bilgisayarlari kullanilacak)"
                     % (type(e).__name__, e), "uyari")
            return

        self.yaz("Yerel AI iscisi baslatildi (pid %d, 127.0.0.1:%d)"
                 % (self.yerel_surec.pid, self.yerel_port), "basari")

        # Cikti SUREKLI bosaltilmalidir: `subprocess.PIPE` dolarsa isci
        # YAZARKEN bloke olur ve "calisiyor ama kare islemiyor" gibi
        # teshisi zor bir donma ortaya cikar.
        threading.Thread(target=self._yerel_cikti_oku,
                         args=(self.yerel_surec,),
                         name="yerel-ai-oku", daemon=True).start()

        k = self._yerel_kayit()
        if k:
            self._yerel_hazir_bekle(k)

    def _yorumlayici(self):
        """Alt sureci calistiracak Python yorumlayicisinin yolu.

        `sys.executable` DOGRUDAN kullanilmaz: kopru Windows'ta bir SCM
        servisi olarak kosarken `sys.executable` pywin32'nin
        `pythonservice.exe` barindiricisini gosterir ve o ikili bir
        betigi calistiramaz (KUSUR-ALTSERVIS-140). Cozumleme mantigi
        `servisler.yorumlayici_yolu()` icinde zaten dogrulanmistir;
        tekrar yazmak iki yerde ayrisan kod uretirdi.
        """
        try:
            from .servisler import yorumlayici_yolu
            return yorumlayici_yolu()
        except Exception:                                   # noqa: BLE001
            # Son care: gercek bir yorumlayici gibi gorunuyorsa kullan.
            yol = sys.executable or ""
            if yol and not os.path.basename(yol).lower().startswith(
                    "pythonservice"):
                return yol
            return ""

    def _yerel_hazir_bekle(self, kayit):
        """Isci portu dinlemeye baslayana kadar bekler.

        Beklenmezse ilk `/durum` yoklamasi bos donerdi ve panel yerel
        isciyi "cevrimdisi" gosterirdi. Isci acilista ONNX/OpenCV
        modellerini yukler; bu yavas diskte saniyeler surer.
        """
        bitis = time.time() + YEREL_AI_HAZIR_SN
        while time.time() < bitis and not self.durdur_istendi():
            if self.yerel_surec is not None and \
                    self.yerel_surec.poll() is not None:
                self.yaz("Yerel AI iscisi acilista sonlandi "
                         "(cikis kodu %s); yalniz uzak AI bilgisayarlari "
                         "kullanilacak" % self.yerel_surec.poll(), "uyari")
                with self.kilit:
                    self.sunucular.pop(YEREL_AI_ID, None)
                    self.saglik.pop(YEREL_AI_ID, None)
                self.yerel_surec = None
                return
            if self._port_dolu_mu():
                self._yokla_tek(kayit)
                with self.kilit:
                    cevrimici = bool((self.saglik.get(YEREL_AI_ID) or {})
                                     .get("cevrimici"))
                if cevrimici:
                    self.yaz("Yerel AI iscisi hazir (127.0.0.1:%d)"
                             % self.yerel_port, "basari")
                    return
            self.bekle(0.5)
        # Zaman asimi COKME DEGILDIR: surec hala aciliyor olabilir.
        # Duzenli yoklama kaydi birkac saniye sonra cevrimici yapar.
        self.yaz("Yerel AI iscisi %.0f sn icinde hazir olmadi; yoklama "
                 "surdurulecek" % YEREL_AI_HAZIR_SN, "uyari")

    def _yerel_cikti_oku(self, surec):
        """Isci sureci ciktisini servis konsoluna aktarir."""
        try:
            for satir in iter(surec.stdout.readline, ""):
                satir = satir.rstrip("\r\n")
                if satir:
                    self.yaz("[yerel-ai] %s" % satir)
        except Exception as e:                              # noqa: BLE001
            self.yaz("Yerel AI iscisi ciktisi okunamadi: %s" % e, "uyari")
        finally:
            try:
                surec.stdout.close()
            except Exception:
                pass
            if self.durdur_istendi():
                return
            # Cikis kodu HENUZ YOKSA surec yasiyor, yalnizca borusu
            # kapanmistir. "Sonlandi (cikis kodu None)" yazmak yanlis
            # teshise goturur; bu yuzden iki durum ayri bildirilir.
            try:
                kod = surec.wait(timeout=2)
            except Exception:                               # noqa: BLE001
                kod = surec.poll()
            if kod is None:
                self.yaz("Yerel AI iscisinin cikti borusu kapandi; "
                         "surec calismaya devam ediyor", "uyari")
            else:
                # Beklenmedik sonlanma GORUNUR olmalidir: aksi halde
                # panelde yalniz "cevrimdisi" yazar ve nedeni bilinmez.
                self.yaz("Yerel AI iscisi sonlandi (cikis kodu %s)"
                         % kod, "uyari")

    def _yerel_isci_durdur(self):
        """Yerel isci surecini nazikce sonlandirir."""
        surec = self.yerel_surec
        self.yerel_surec = None
        if surec is None or surec.poll() is not None:
            return
        try:
            surec.terminate()
        except Exception:                                   # noqa: BLE001
            pass
        try:
            surec.wait(timeout=6)
        except Exception:                                   # noqa: BLE001
            # Nazik sonlandirma islemedi. Zorla oldurulmezse port
            # tutulmaya devam eder ve bir sonraki baslatmada yerel isci
            # "port dolu" diye hic ayaga kalkmaz.
            try:
                surec.kill()
            except Exception:
                pass
        self.yaz("Yerel AI iscisi durduruldu")

    def _hizlandirici_bul(self):
        """Kullanilabilir hizlandiriciyi tespit eder.

        Ice aktarim hatalari SESSIZCE yutulur: paketlerin bulunmamasi
        normal durumdur, hata degildir. Yigin izi basmak kullaniciyi
        gereksiz endiselendirir.
        """
        try:
            import torch
            if torch.cuda.is_available():
                return "CUDA (%s)" % torch.cuda.get_device_name(0)
        except Exception:
            pass
        try:
            import onnxruntime as ort
            saglayici = ort.get_available_providers()
            for p in ("CUDAExecutionProvider", "DmlExecutionProvider",
                      "OpenVINOExecutionProvider"):
                if p in saglayici:
                    return p.replace("ExecutionProvider", "")
        except Exception:
            pass
        return "CPU"

    # -----------------------------------------------------------------
    def _yerel_akis_adresi(self, kamera_id):
        """AI iscisinin cekecegi akis adresini bu makineye gore uretir.

        Isci ayni makinede degil, ayni YEREL AGDA olabilir; bu yuzden
        `127.0.0.1` yeterli DEGILDIR. Iscinin bu makineye ulasabilecegi
        adres kullanilir: `GOKTUNGU_KOPRU_YEREL_IP` verilmisse o, yoksa
        disa acilan arayuzun adresi, hicbiri bulunamazsa `127.0.0.1`.
        """
        adres = (os.environ.get("GOKTUNGU_KOPRU_YEREL_IP") or "").strip()
        if not adres:
            adres = self._dis_arayuz_ip()
        return "http://%s:%s/kamera/%s" % (adres, VIDEO_PROXY_PORT,
                                           int(kamera_id))

    @staticmethod
    def _dis_arayuz_ip():
        """Yerel agda gorunen arayuz adresini bulur.

        UDP yuvasi baglanir ama VERI GONDERILMEZ; cekirdek yalnizca
        yonlendirme tablosuna bakip hangi arayuzun kullanilacagini
        soyler. Ag erisimi olmasa da hata vermez, o durumda geri donus
        adresi kullanilir.
        """
        import socket
        yuva = None
        try:
            yuva = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            yuva.settimeout(0.4)
            yuva.connect(("192.0.2.1", 9))   # TEST-NET-1: yonlendirilmez
            return yuva.getsockname()[0] or "127.0.0.1"
        except Exception:
            return "127.0.0.1"
        finally:
            if yuva is not None:
                try:
                    yuva.close()
                except Exception:
                    pass

    # -----------------------------------------------------------------
    # Isci HTTP yardimcilari
    # -----------------------------------------------------------------
    def _http(self, kayit, yol, veri=None, zamanasimi=HTTP_ZAMANASIMI):
        """AI iscisine HTTP istegi (merkezden TASINDI).

        Merkezdeki `ai_yonetici._http` ile ayni sozlesmeyi konusur;
        degisen tek sey bu kodun KOSTUGU makinedir. Saha adresine ancak
        buradan erisilebilir.
        """
        url = "http://%s:%s%s" % (kayit.get("host"), kayit.get("port"),
                                  yol)
        if veri is None:
            istek = urllib.request.Request(url)
        else:
            istek = urllib.request.Request(
                url, data=json.dumps(veri).encode(),
                headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(istek, timeout=zamanasimi) as c:
            return json.loads(c.read() or b"{}")

    def _en_az_yuklu(self, haric=None):
        """Cevrimici, kapasitesi dolu olmayan en az yuklu isci kaydi."""
        aday, aday_yuk = None, 10 ** 9
        with self.kilit:
            kayitlar = list(self.sunucular.values())
            saglik = dict(self.saglik)
        for kayit in kayitlar:
            sid = kayit.get("id")
            if haric and sid == haric:
                continue
            s = saglik.get(sid) or {}
            if not s.get("cevrimici"):
                continue
            durum = s.get("son_durum") or {}
            yuk = durum.get("yuk", 0)
            kapasite = durum.get("kapasite", kayit.get("kapasite", 1))
            try:
                if float(yuk) >= float(kapasite):
                    continue
            except (TypeError, ValueError):
                pass
            if yuk < aday_yuk:
                aday, aday_yuk = kayit, yuk
        return aday

    # -----------------------------------------------------------------
    # Ana dongu
    # -----------------------------------------------------------------
    def dongu(self):
        self.yaz("AI servisi hazir. Isciler BU agdan yoklanir; uzak "
                 "sunucu tanimlari merkezden gelir, yerel isci kopru "
                 "kurulumundan gelir.", "basari")
        while not self.durdur_istendi():
            self._komutlari_isle()
            self._yoklama()
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
        # --- isci kayitlari -------------------------------------------
        if eylem == "sunucu_yaz":
            kayit = veri.get("sunucu") if isinstance(
                veri.get("sunucu"), dict) else veri
            k = self._kayit_normalize(kayit)
            if not k:
                raise ValueError("gecersiz AI sunucu kaydi")
            with self.kilit:
                self.sunucular[k["id"]] = k
            self.yaz("AI sunucu kaydi: #%s %s (%s:%s)"
                     % (k["id"], k["ad"] or "-", k["host"], k["port"]))
            # Yeni kayit hemen yoklanir; aksi halde panel 5 saniye
            # boyunca "bilinmiyor" gosterir ve kullanici kaydin
            # islenmedigini sanar.
            self._yokla_tek(k)
            return {"sunucu": k}

        if eylem == "sunucu_sil":
            sid = veri.get("id")
            try:
                sid = int(sid)
            except (TypeError, ValueError):
                raise ValueError("sunucu id gerekli")
            with self.kilit:
                var = self.sunucular.pop(sid, None) is not None
                self.saglik.pop(sid, None)
                tasinacak = [k for k, s in self.gorevler.items()
                             if s == sid]
            # Dusen iscinin gorevleri BASKA isciye tasinir; aksi halde
            # kamera sessizce izlemesiz kalir ve operator bunu bilmez.
            for kamera_id in tasinacak:
                self._gorev_yeniden_ata(kamera_id, dusen=sid)
            return {"silindi": bool(var)}

        if eylem == "sunucular":
            return {"ai_sunucular": self._sunucu_ozet()}

        # --- izleme gorevleri -----------------------------------------
        if eylem == "izleme_baslat":
            kamera_id = veri.get("kamera_id")
            if kamera_id is None:
                raise ValueError("kamera_id gerekli")
            kamera_id = int(kamera_id)
            gorevler = str(veri.get("gorevler") or "")
            # AKIS ADRESI BURADA URETILIR, merkezden GELMEZ.
            #
            # Merkez kipinde merkezin uretecegi adres kendi 8801
            # vekilini gosterir; saha iscisi o adrese erisemez. Bu
            # yuzden merkez yalniz kamera kimligini ve gorev listesini
            # gonderir. Adresi bu makine kendi yerel vekiline gore
            # uretir; boylece hem istek hem goruntu saha aginda kalir.
            #
            # Merkez yine de bir adres gonderirse (lokal kurulumda GCS
            # ile kopru ayni makinede olabilir) o adres kullanilir.
            url = str(veri.get("url") or "").strip()
            protokol = str(veri.get("protokol") or "")
            kamera = veri.get("kamera") or None
            if not url:
                url = self._yerel_akis_adresi(kamera_id)
                protokol = protokol or "gcs_proxy"
                # Isci bu makinenin vekilinden cekecek; vekilin kare
                # uretmesi icin akisin ACIK olmasi gerekir.
                self._akis_actir(kamera_id, kamera)
            return self._gorev_ata(kamera_id, url, protokol,
                                   gorevler=gorevler, kamera=kamera)

        if eylem == "izleme_durdur":
            kamera_id = veri.get("kamera_id")
            if kamera_id is None:
                raise ValueError("kamera_id gerekli")
            return self._izleme_durdur(int(kamera_id))

        if eylem == "izleme_listesi":
            return {"ai_gorevler": self._gorev_ozet()}

        if eylem == "durum":
            return self._durum_paketi()

        raise ValueError("bilinmeyen eylem: %s" % eylem)

    def _kayit_normalize(self, kayit):
        if not isinstance(kayit, dict):
            return None
        try:
            sid = int(kayit.get("id"))
        except (TypeError, ValueError):
            return None
        try:
            port = int(kayit.get("port") or 8900)
        except (TypeError, ValueError):
            port = 8900
        try:
            kapasite = int(kayit.get("kapasite") or 1)
        except (TypeError, ValueError):
            kapasite = 1
        return {"id": sid,
                "ad": str(kayit.get("ad") or ""),
                "host": str(kayit.get("host") or ""),
                "port": port,
                "kapasite": kapasite}

    # -----------------------------------------------------------------
    # Gorev atama
    # -----------------------------------------------------------------
    def _gorev_ata(self, kamera_id, url, protokol, haric=None,
                   gorevler="", kamera=None):
        kayit = self._en_az_yuklu(haric=haric)
        if not kayit:
            # Gerekce NET olmali: "cevrimici isci yok" ile "isci dolu"
            # farkli sorunlardir ve farkli mudahale gerektirir.
            with self.kilit:
                toplam = len(self.sunucular)
                cevrimici = sum(1 for s in self.saglik.values()
                                if s.get("cevrimici"))
            if toplam == 0:
                hata = "Tanimli AI sunucusu yok"
            elif cevrimici == 0:
                hata = ("Hicbir AI sunucusu cevrimici degil "
                        "(%d tanimli)" % toplam)
            else:
                hata = ("Cevrimici AI sunucularinin kapasitesi dolu "
                        "(%d/%d)" % (cevrimici, toplam))
            self.yaz("Kamera %d izlemesi atanamadi: %s"
                     % (kamera_id, hata), "uyari")
            return {"tamam": False, "hata": hata}
        try:
            sonuc = self._http(kayit, "/izle",
                               {"kamera_id": kamera_id, "url": url,
                                "protokol": protokol,
                                "gorevler": gorevler or ""})
        except Exception as e:
            self.yaz("Kamera %d izlemesi %s sunucusuna atanamadi: %s"
                     % (kamera_id, kayit.get("ad") or kayit.get("host"),
                        e), "hata")
            return {"tamam": False,
                    "hata": "%s: %s" % (kayit.get("ad") or
                                        kayit.get("host"), e)}
        if sonuc.get("tamam"):
            with self.kilit:
                self.gorevler[int(kamera_id)] = kayit["id"]
                self.gorev_bilgi[int(kamera_id)] = {
                    "url": url, "protokol": protokol,
                    "gorevler": gorevler or "",
                    "kamera": dict(kamera) if kamera else None}
            self.yaz("Kamera %d izlemesi %s sunucusuna atandi"
                     % (kamera_id, kayit.get("ad") or kayit.get("host")),
                     "basari")
        return sonuc

    def _gorev_yeniden_ata(self, kamera_id, dusen=None):
        with self.kilit:
            bilgi = dict(self.gorev_bilgi.get(int(kamera_id)) or {})
            self.gorevler.pop(int(kamera_id), None)
        if not bilgi.get("url"):
            return
        self._gorev_ata(int(kamera_id), bilgi["url"],
                        bilgi.get("protokol", ""), haric=dusen,
                        gorevler=bilgi.get("gorevler", ""),
                        kamera=bilgi.get("kamera"))

    def _akis_actir(self, kamera_id, kamera=None):
        """Video servisine kamerayi acmasini bildirir.

        ## NEDEN GEREKLI

        Isci goruntuyu bu makinenin `/kamera/<id>` adresinden ceker,
        ancak o adres YALNIZCA akis acikken kare uretir. Akis acilmazsa
        gorev basariyla atanmis gorunur, panelde 'atandi' yazar, ama
        isciye tek kare gitmez. Bu, en tehlikeli basarisizlik bicimidir:
        operator AI'nin izledigini sanir.

        Kamera kaydi da birlikte gonderilir; video servisi kamerayi
        kendi defterinde bulamazsa akisi acamaz.
        """
        dizin = self.kanal.dizin or os.environ.get(
            "GOKTUNGU_KOPRU_KANAL_DIZIN") or ""
        if not dizin:
            return
        try:
            if kamera:
                komut_yaz(dizin, "video", "kamera_yaz",
                          {"kamera": dict(kamera)})
            komut_yaz(dizin, "video", "akis_baslat",
                      {"id": int(kamera_id)})
        except Exception as e:                          # noqa: BLE001
            self.yaz("Kamera %s akisi video servisinde acilamadi: %s"
                     % (kamera_id, e), "uyari")

    def _izleme_durdur(self, kamera_id):
        with self.kilit:
            sid = self.gorevler.pop(int(kamera_id), None)
            self.gorev_bilgi.pop(int(kamera_id), None)
            kayit = dict(self.sunucular.get(sid) or {}) if sid else None
        if kayit:
            try:
                self._http(kayit, "/durdur", {"kamera_id": int(kamera_id)})
            except Exception as e:
                # Isci ulasilamiyorsa gorev YINE de birakilir: aksi halde
                # panelde silinemeyen bir izleme kaydi kalir.
                self.yaz("Kamera %s izlemesi durdurulurken isciye "
                         "ulasilamadi: %s" % (kamera_id, e), "uyari")
        # Kutular donuk kalmamali: video servisine bos kutu gonderilir.
        self._anotasyon_temizle(int(kamera_id))
        self.yaz("Kamera %s izlemesi durduruldu" % kamera_id)
        return {"tamam": True}

    def _anotasyon_temizle(self, kamera_id):
        """Video servisine bos kutu listesi gonderir.

        Tespit kutulari merkeze DEGIL ayni makinedeki video servisine
        gider. Izleme durdurulunca kutular temizlenmezse son kareye ait
        cerceveler ekranda donuk kalir ve operator olmayan bir hedefi
        gorur.

        ## KANAL DIZINI NEDEN ELLE COZULUR

        `komut_yaz(dizin, ...)` dizini ortam degiskeninden OKUMAZ; yolu
        dogrudan `os.path.join` ile kurar. `None` gecilirse TypeError
        atar. `ServisKanali` ise ayni degiskeni kendi icinde cozer; bu
        yuzden dizin oradan alinir. Kanal kurulu degilse (servis elle
        calistirilmis olabilir) sessizce vazgecilir.
        """
        dizin = self.kanal.dizin or os.environ.get(
            "GOKTUNGU_KOPRU_KANAL_DIZIN") or ""
        if not dizin:
            return
        try:
            komut_yaz(dizin, "video", "anotasyon",
                      {"id": int(kamera_id), "kutular": []})
        except Exception:
            pass

    # -----------------------------------------------------------------
    # Saglik yoklamasi
    # -----------------------------------------------------------------
    def _yoklama(self):
        simdi = time.time()
        if simdi - self._son_yoklama < YOKLAMA_ARALIGI_SN:
            return
        self._son_yoklama = simdi
        with self.kilit:
            kayitlar = list(self.sunucular.values())
        for kayit in kayitlar:
            self._yokla_tek(kayit)

    def _yokla_tek(self, kayit):
        sid = kayit.get("id")
        with self.kilit:
            onceki = (self.saglik.get(sid) or {}).get("cevrimici")
        try:
            durum = self._http(kayit, "/durum",
                               zamanasimi=YOKLAMA_ZAMANASIMI)
            with self.kilit:
                self.saglik[sid] = {"cevrimici": True,
                                    "son_durum": durum,
                                    "son_yoklama_ts": time.time(),
                                    "hata": ""}
            if onceki is False:
                self.yaz("AI sunucusu tekrar cevrimici: %s"
                         % (kayit.get("ad") or kayit.get("host")),
                         "basari")
        except Exception as e:
            with self.kilit:
                self.saglik[sid] = {"cevrimici": False,
                                    "son_durum": {},
                                    "son_yoklama_ts": time.time(),
                                    "hata": str(e)[:200]}
                dusen_gorevler = [k for k, s in self.gorevler.items()
                                  if s == sid]
            if onceki is True:
                self.yaz("AI sunucusu yanit vermiyor: %s (%s)"
                         % (kayit.get("ad") or kayit.get("host"), e),
                         "uyari")
                # Dusen iscinin gorevleri baska isciye tasinir.
                for kamera_id in dusen_gorevler:
                    self._gorev_yeniden_ata(kamera_id, dusen=sid)

    # -----------------------------------------------------------------
    # Merkeze bildirim
    # -----------------------------------------------------------------
    def _sunucu_ozet(self):
        with self.kilit:
            kayitlar = list(self.sunucular.values())
            saglik = dict(self.saglik)
            gorevler = dict(self.gorevler)
        ozet = []
        for k in kayitlar:
            sid = k.get("id")
            s = saglik.get(sid) or {}
            d = s.get("son_durum") or {}
            ozet.append({
                "id": sid,
                "ad": k.get("ad", ""),
                "host": k.get("host", ""),
                "port": k.get("port", 0),
                "cevrimici": bool(s.get("cevrimici")),
                "hata": s.get("hata", ""),
                "yuk": d.get("yuk", 0),
                "kapasite": d.get("kapasite", k.get("kapasite", 1)),
                "hizlandirici": d.get("hizlandirici", ""),
                "gorev_sayisi": sum(1 for v in gorevler.values()
                                    if v == sid),
                "son_yoklama_ts": s.get("son_yoklama_ts", 0),
            })
        return ozet

    def _gorev_ozet(self):
        with self.kilit:
            gorevler = dict(self.gorevler)
            bilgi = {k: dict(v) for k, v in self.gorev_bilgi.items()}
            saglik = dict(self.saglik)
        # Iscinin /durum yanitindaki akis canli/hata bilgisi izleme
        # kaydina islenir; arayuzde "atandi ama akis yok" durumu
        # gorunur olmalidir.
        akis_durum = {}
        for sid, s in saglik.items():
            for a in ((s.get("son_durum") or {}).get("akislar") or []):
                try:
                    akis_durum[int(a.get("kamera_id"))] = a
                except (TypeError, ValueError):
                    continue
        sonuc = []
        for kamera_id, sid in gorevler.items():
            b = bilgi.get(kamera_id) or {}
            sonuc.append({
                "kamera_id": int(kamera_id),
                "sunucu_id": sid,
                "protokol": b.get("protokol", ""),
                "gorevler": b.get("gorevler", ""),
                "akis": akis_durum.get(int(kamera_id)) or {},
            })
        return sonuc

    def _durum_paketi(self):
        ozet = self._sunucu_ozet()
        return {
            "ai_sunucular": ozet,
            "ai_gorevler": self._gorev_ozet(),
            "ai_hazir": any(s["cevrimici"] for s in ozet),
            "ai_sunucu_sayisi": len(ozet),
            "ai_cevrimici": sum(1 for s in ozet if s["cevrimici"]),
            "hizlandirici": self.hizlandirici,
        }

    def _merkeze_yaz(self):
        simdi = time.time()
        if simdi - self._son_durum < DURUM_YAZIM_SN:
            return
        self._son_durum = simdi
        self.durum_yaz(**self._durum_paketi())

    def _konsol_ozet(self):
        simdi = time.time()
        if simdi - self._son_konsol < KONSOL_BILDIRIM_SN:
            return
        self._son_konsol = simdi
        p = self._durum_paketi()
        self.yaz("Durum: %d/%d isci cevrimici, %d etkin izleme gorevi, "
                 "yerel birim %s"
                 % (p["ai_cevrimici"], p["ai_sunucu_sayisi"],
                    len(p["ai_gorevler"]), self.hizlandirici))

    # -----------------------------------------------------------------
    def kapat(self):
        with self.kilit:
            kameralar = list(self.gorevler.keys())
        for kamera_id in kameralar:
            try:
                self._izleme_durdur(kamera_id)
            except Exception:
                pass
        # Yerel isci gorevler BIRAKILDIKTAN SONRA durdurulur: once
        # oldurulseydi `/durdur` istekleri bos bir porta gider ve her
        # kamera icin gereksiz bir hata satiri dusuverirdi.
        try:
            self._yerel_isci_durdur()
        except Exception:                                   # noqa: BLE001
            pass
        try:
            if getattr(self, "alici", None) is not None:
                self.alici.shutdown()
                self.alici.server_close()
                self.alici = None
        except Exception:                                   # noqa: BLE001
            pass
        # Servis durdugunda merkez isciyi "cevrimici" gormeye devam
        # etmemeli; aksi halde operator var olmayan bir izlemeye guvenir.
        try:
            self.durum_yaz(ai_sunucular=[], ai_gorevler=[],
                           ai_hazir=False, ai_cevrimici=0,
                           ai_sunucu_sayisi=0)
        except Exception:
            pass
        self.yaz("Izleme gorevleri kapatildi")


if __name__ == "__main__":
    calistir(AiServisi)
