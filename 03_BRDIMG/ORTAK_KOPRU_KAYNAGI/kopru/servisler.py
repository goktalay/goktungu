# -*- coding: utf-8 -*-
"""KOPRU YAZILIMI — servis yoneticisi (Dron / AI / Video).

## KULLANICI ISTEGI (birebir)

    "Kullanicilarin indirdigi sey locale bir sayfa acacak ama o sayfada
     dron, video ve ai sunucularini baslatma durdurma ve konsollarini
     gorme islevi olacak."

## TASARIM KARARLARI VE NEDENLERI

1) ALT SUREC, IS PARCACIGI DEGIL
   Uc servis BAGIMSIZ surecler olarak calisir. Is parcacigi olsalardi
   biri cokerse (ornegin AI iscisi bellek tuketirse) kopru panelini de
   goturur ve kullanici uzaktan hicbir seyi goremez hale gelirdi.
   Ayri surecte cokme YALITILIR: panel ayakta kalir, konsolda cokme
   izi durur, kullanici yeniden baslatir.

2) KONSOL DAIRESEL TAMPONDA
   Cikti `collections.deque(maxlen=...)` icinde tutulur. Sinirsiz liste
   kullanilsaydi gunlerce calisan bir servisin ciktisi belligi tuketirdi.
   Panel yalniz son N satiri gosterir; tam gunluk diske yazilir.

3) SATIR OKUMA AYRI IS PARCACIGINDA
   `subprocess.PIPE` dolarsa alt surec YAZARKEN BLOKE OLUR ve donar.
   Bu, "servis calisiyor ama yanit vermiyor" seklinde teshis edilmesi
   zor bir kusurdur. Her servis icin bir okuyucu is parcacigi ciktiyi
   surekli bosaltir.

4) SIGTERM SONRA SIGKILL
   Durdurmada once nazik sonlandirma (SIGTERM / Windows'ta terminate)
   denenir, 8 sn icinde olmezse zorla oldurulur. Yalniz `kill`
   kullanmak, servisin acik dosyalarini ve veritabani baglantisini
   duzgun kapatmasina izin vermez.

5) SUREC GRUBU
   POSIX'te `start_new_session=True` ile yeni oturum acilir; boylece
   servisin baslattigi ALT surecler de birlikte sonlandirilabilir.
   Aksi halde `arducopter` gibi torun surecler yetim kalir ve portu
   tutmaya devam eder ("Address already in use").
"""
import collections
import json
import os
import signal
import subprocess
import sys
import threading
import time

KONSOL_SATIR_SINIR = 2000
NAZIK_BEKLE_SN = 8.0

# Alt surecleri baslatan yorumlayicinin yolu icin onbellek. Cozumleme
# dosya sistemine bakar; her servis baslatmada yeniden yapmak gereksiz.
_YORUMLAYICI_ONBELLEK = None


def _pythonservice_mi(yol):
    """Verilen yol pywin32'nin servis barindiricisi mi?

    `pythonservice.exe` bir Python yorumlayicisi DEGILDIR; `-m modul`
    argumanini anlamaz, kendi kullanim metnini basip cikar.
    """
    if not yol:
        return False
    return os.path.basename(yol).lower().startswith("pythonservice")


def yorumlayici_yolu(yenile=False):
    """Alt servisleri baslatacak Python yorumlayicisinin tam yolu.

    ## KUSUR-ALTSERVIS-140 (bu islevin varlik nedeni)

    v1.4.0'da alt servisler `sys.executable` ile baslatiliyordu. Konsol
    kipinde bu dogrudur (`python.exe`), ancak kopru artik bir Windows
    SCM servisi olarak da calisir ve o baglamda sureci pywin32'nin
    `pythonservice.exe` barindiricisi baslatir. O surecte
    `sys.executable` -> `...\\python\\pythonservice.exe` doner.

    Sonuc: bes alt servis (dron/ai/video/gcsdual/radar)
    `pythonservice.exe -m kopru.dron_servis` olarak calistirildi;
    barindirici kullanim metnini basip **cikis kodu 2** ile sonlandi.
    Sahada gorulen belirti: "BASLAT" basiliyor, konsola pywin32'nin
    Ingilizce kullanim metni dusuyor, servis hic ayaga kalkmiyor.

    Bu yuzden yorumlayici asagidaki sirayla cozulur; ilk gecerli
    aday kullanilir:

    1. `GOKTUNGU_KOPRU_PYTHON` ortam degiskeni — servis kurulumunun acik
       niyeti. Elle mudahale ve olagandisi kurulumlar icin kacis kapisi.
    2. `sys.executable` — YALNIZ gercek bir yorumlayiciysa.
    3. `sys.executable` ile ayni dizinde `python.exe` / `pythonw.exe`
       (gomulu dagitimda barindirici ile yan yana durur).
    4. `sys.prefix` altinda ayni adaylar (venv/kurulum duzenleri).
    5. `sys.base_prefix` altinda ayni adaylar.

    Hicbiri bulunamazsa `RuntimeError` yukseltilir: sessizce yanlis bir
    ikiliyi calistirip anlasilmaz "cikis kodu 2" uretmek yerine, panele
    ne oldugunu soyleyen bir hata dusmesi yeglenir.
    """
    global _YORUMLAYICI_ONBELLEK
    if _YORUMLAYICI_ONBELLEK and not yenile:
        return _YORUMLAYICI_ONBELLEK

    # Aday adlari PLATFORMA GORE SECILMEZ, cunku barindirici tuzagi
    # Windows'a ozguyken bu islevin sinavlari Linux'ta kosar. `os.name`
    # ile dallanmak, sinavin Windows duzenini taklit etmesini olanaksiz
    # kilar (ilk yazimda bu yuzden yanlis kod yolu dogrulanmisti).
    # Bunun yerine tum bilinen adlar denenir; var olmayan ad zararsizca
    # atlanir. Windows'ta "python3" dosyasi bulunmaz, Linux'ta
    # "python.exe" bulunmaz.
    adlar = ("python.exe", "pythonw.exe", "python3", "python")

    def _dizinde_ara(dizin):
        if not dizin:
            return None
        for ad in adlar:
            for alt in ("", "bin", "Scripts"):
                aday = os.path.join(dizin, alt, ad) if alt else \
                    os.path.join(dizin, ad)
                if os.path.isfile(aday) and not _pythonservice_mi(aday):
                    return aday
        return None

    # 1) Acik niyet
    cevre = os.environ.get("GOKTUNGU_KOPRU_PYTHON")
    if cevre and os.path.isfile(cevre) and not _pythonservice_mi(cevre):
        _YORUMLAYICI_ONBELLEK = cevre
        return cevre

    # 2) sys.executable, yalniz gercek yorumlayiciysa
    if sys.executable and not _pythonservice_mi(sys.executable) \
            and os.path.isfile(sys.executable):
        _YORUMLAYICI_ONBELLEK = sys.executable
        return sys.executable

    # 3-5) Barindiricinin yani, sys.prefix, sys.base_prefix
    for dizin in (os.path.dirname(sys.executable or ""),
                  getattr(sys, "prefix", None),
                  getattr(sys, "base_prefix", None)):
        bulunan = _dizinde_ara(dizin)
        if bulunan:
            _YORUMLAYICI_ONBELLEK = bulunan
            return bulunan

    raise RuntimeError(
        "Python yorumlayicisi bulunamadi. sys.executable=%r bir servis "
        "barindiricisi ve yanindaki dizinlerde python bulunamadi. "
        "GOKTUNGU_KOPRU_PYTHON ortam degiskeniyle tam yolu belirtin."
        % (sys.executable,))

def paket_koku():
    """`kopru` paketinin bulundugu dizin (kurulum koku).

    Windows: `C:\\Program Files\\Goktungu\\Kopru`
    Ubuntu : `/opt/goktungu/kopru`

    Bu dosya `<kok>/kopru/servisler.py` oldugu icin iki ust dizin
    alinir. Mutlak yol calisma aninda cozulur; kurulum dizini nereye
    acilirsa acilsin dogrudur.
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Servis tanimlari. `komut` bir SABLON degildir; calistirilabilir dosya
# ve argumanlar listesi olarak verilir (kabuk enjeksiyonu riski yok:
# shell=False kullanilir).
SERVIS_TANIM = {
    "dron": {
        "baslik": "Dron Sunucusu",
        "aciklama": "Ucus baglantilarini (seri/UDP/TCP) merkeze koprular.",
        "modul": "kopru.servis_dron",
    },
    "ai": {
        "baslik": "AI Sunucusu",
        "aciklama": "Yerel goruntu isleme iscisi; tespitleri merkeze yollar.",
        "modul": "kopru.servis_ai",
    },
    "video": {
        "baslik": "Video Sunucusu",
        "aciklama": "Kamera akislarini yakalar ve merkeze aktarir.",
        "modul": "kopru.servis_video",
    },
    # 2026-08-13 — kullanici istegi: "radar ve ground control dual
    # dedigimiz yer kontrol istasyonu, bu ikiside sunucu yazilimi icinde
    # olmali, kopru olarak cikmali". Donanim SAHA MAKINESINDE takilidir,
    # bu yuzden merkezde degil kopruda servis olarak calisirlar.
    "radar": {
        "baslik": "Radar Sunucusu",
        "aciklama": "Yerel radar donanimini okur; hedef izlerini merkeze "
                     "yollar.",
        "modul": "kopru.servis_radar",
    },
    "gcsdual": {
        "baslik": "GroundGCC Sunucusu",
        "aciklama": "GCCDUAL cantasini (ESP32) okur; dugme ve joystick "
                     "verisini merkeze yollar.",
        "modul": "kopru.servis_gcsdual",
    },
    "m50": {
        "baslik": "M50 Elektro-Optik",
        "aciklama": "M50 HVS aygitini yerel Windows SDK ile, acik operator "
                     "komutuyla yonetir; ham video merkeze tasinmaz.",
        "modul": "kopru.servis_m50",
    },
}

# Panelde ve merkez bildiriminde kullanilan SABIT sira. Sozluk sirasina
# guvenilmez: servis eklendiginde panel duzeni kaymamalidir.
# Kullanicinin belirttigi menu sirasi (13.08.2026): Dron, AI, Video,
# GroundGCC, Radar.
SERVIS_SIRA = ("dron", "ai", "video", "gcsdual", "radar", "m50")

# Diger moduller (uygulama, panel, kurulum) servis adlarini ELLE
# yazmasin: yeni bir servis eklendiginde tek noktadan yayilir.
SERVIS_ADLARI = SERVIS_SIRA


# ---------------------------------------------------------------------
# v1.5.6 — Servis <-> firma yetkisi eslemesi
# ---------------------------------------------------------------------
# Kullanici istegi: "kullanicilar kopruyu indirip login olduktan sonra
# sirketlerine tanimli Radar ve GCCDual varsa solda menude gorunecek,
# yoksa gorunmeyecek".
#
# DIKKAT — ISIM AYRISIKLIGI: servis adi `gcsdual`, merkezdeki yetki
# anahtari `gccdual`'dir (biri GCS, oteki GCC). Iki yazim da sahada
# kullanimda oldugu icin BIRLESTIRILMEZ; esleme burada tek noktada
# tutulur. Elle yazilsa bir tarafta harf farki yetkiyi sessizce hep
# kapali gosterirdi.
#
# `None` = cekirdek yetenek, ucretlendirilmez, daima gorunur.
SERVIS_YETKI = {
    "dron": None,
    "ai": "ai",
    "video": None,
    "gcsdual": "gccdual",
    "radar": "radar",
    # M50, fiziksel cihaz denetimi içerdiğinden firma yetkisi yoksa
    # görünmez ve başlatılamaz. Eski merkezlerin eksik yetki özetinde
    # kapalı kalması bilinçli güvenli varsayımdır.
    "m50": "m50",
}


def servis_gorunur_mu(ad, yetkiler):
    """`ad` servisi bu firmanin yetkileriyle gorunur/kullanilabilir mi?

    `yetkiler` merkezin giris yanitindaki ozettir
    (`{dron,video,ai,radar,gccdual}`). Sozluk YOKSA (merkeze hic
    baglanilamadi, eski surum merkez, ozet alani bos) cekirdek
    servisler acik, ucretli/kisitli servisler KAPALI sayilir.

    Neden bu yon: yetki ozeti okunamadiginda "her seyi ac" demek,
    merkez erisilemezken radar/gccdual/ai'yi bedelsiz kullanima
    acardi. Kapali tarafa dusmek yalnizca menuyu eksik gosterir;
    kullanici merkeze baglaninca duzelir.
    """
    anahtar = SERVIS_YETKI.get(str(ad), None)
    if anahtar is None:
        # Tanimsiz (ozel tanimla eklenmis) servis de cekirdek sayilir:
        # yetki tablosunda yeri olmayan bir servisi gizlemek, panelde
        # "neden gorunmuyor" sorusuna yol acar.
        return True
    if not isinstance(yetkiler, dict):
        return False
    return bool(yetkiler.get(anahtar))


class Servis:
    """Tek bir alt surecin yasam dongusu ve konsol tamponu."""

    def __init__(self, ad, tanim, gunluk_dizin=None):
        self.ad = ad
        self.tanim = dict(tanim)
        self.surec = None
        self.baslama_ts = None
        self.bitis_ts = None
        self.cikis_kodu = None
        self.son_hata = None
        self.konsol = collections.deque(maxlen=KONSOL_SATIR_SINIR)
        self._kilit = threading.Lock()
        self._okuyucu = None
        self._gunluk_dosya = None
        self._gunluk_dizin = gunluk_dizin
        self._satir_no = 0

    # -----------------------------------------------------------------
    def calisiyor(self):
        s = self.surec
        return bool(s and s.poll() is None)

    def durum(self):
        d = {
            "ad": self.ad,
            "baslik": self.tanim.get("baslik") or self.ad,
            "aciklama": self.tanim.get("aciklama") or "",
            "calisiyor": self.calisiyor(),
            "pid": (self.surec.pid if self.calisiyor() else None),
            "baslama_ts": self.baslama_ts,
            "bitis_ts": self.bitis_ts,
            "cikis_kodu": self.cikis_kodu,
            "son_hata": self.son_hata or "",
            "konsol_satir": self._satir_no,
            # Canli olcumler (etkin dron sayisi, kuyruk boyu, seri port
            # vb.). Panel bunlari olcum seridinde gosterir; alan HER
            # ZAMAN vardir (bos sozluk olabilir) ki arayuz kosullu
            # kontrol yapmak zorunda kalmasin.
            "olcumler": self.olcumler(),
        }
        # Her sunucu tipi KENDI surumuyle isletilir (kullanici istegi).
        # Ice aktarma burada yapilir: modul duzeyinde yapilsa
        # `surumler` <-> `servisler` dairesel bagimliligi olusur.
        try:
            from . import surumler as _s
            d["surum"] = _s.SERVIS_SURUMLERI.get(self.ad, "")
        except Exception:
            d["surum"] = ""
        return d

    def olcumler(self):
        """Servisin durum dosyasina yazdigi canli olcumleri okur.

        Alt surecin bellegine erisim mumkun olmadigi icin dosya
        araciligi ZORUNLUDUR. Servis durmussa veya dosya bayatsa bos
        sozluk doner: durmus bir servisin son olcumunu CANLI gibi
        gostermek yanlis karar dogurur ("3 dron bagli" yazarken
        aslinda hicbiri bagli degildir).
        """
        if not self.calisiyor():
            return {}
        yol = self.tanim.get("durum_dosyasi")
        if not yol:
            return {}
        try:
            with open(yol, "r", encoding="utf-8") as f:
                d = json.load(f)
            if not isinstance(d, dict):
                return {}
            # 30 sn: servis dongusu 5 sn'de bir yazar; 30 sn sessizlik
            # cokme veya kilitlenme demektir.
            if time.time() - float(d.get("ts") or 0) > 30:
                return {}
            d.pop("ts", None)
            return d
        except Exception:
            return {}

    def dron_sayisi(self):
        """KULLANMAYIN: her zaman 0 doner.

        Etkin ucus baglantilari alt surecte degil panel/ajan surecinde
        tutulur, bu yuzden alt surecin durum dosyasinda boyle bir olcum
        YOKTUR. Gercek sayim `Uygulama.servis_durumu_zengin()` icindedir.

        Islev geriye uyumluluk icin duruyor; yeni cagri eklenmemeli.
        """
        try:
            return int(self.olcumler().get("dron_sayisi") or 0)
        except Exception:
            return 0

    def konsol_oku(self, sonrasi=0, sinir=400):
        """`sonrasi` satir numarasindan SONRAKI satirlari dondurur.

        Panel her sorguda tum tamponu indirmek zorunda kalmasin diye
        artimli okuma yapilir: 2000 satiri saniyede bir cekmek hem ag
        hem CPU israfidir.
        """
        with self._kilit:
            satirlar = [s for s in self.konsol if s["no"] > int(sonrasi or 0)]
        return satirlar[-int(sinir):]

    # -----------------------------------------------------------------
    def _yaz(self, metin, kaynak="sistem"):
        with self._kilit:
            self._satir_no += 1
            self.konsol.append({"no": self._satir_no, "ts": time.time(),
                                "kaynak": kaynak, "metin": metin})
        if self._gunluk_dosya:
            try:
                self._gunluk_dosya.write(
                    time.strftime("%H:%M:%S ") + metin + "\n")
                self._gunluk_dosya.flush()
            except Exception:
                pass

    def _gunluk_ac(self):
        if not self._gunluk_dizin:
            return
        try:
            os.makedirs(self._gunluk_dizin, exist_ok=True)
            yol = os.path.join(self._gunluk_dizin, "%s.log" % self.ad)
            # Ekleme kipi: onceki calismanin izi silinmez (kusur avinda
            # "bir onceki cokmede ne yazdi" sorusu kritiktir).
            self._gunluk_dosya = open(yol, "a", encoding="utf-8",
                                      errors="replace")
        except Exception as e:
            self.son_hata = "Gunluk acilamadi: %s" % e

    def _komut(self):
        """Alt surec komutu.

        Yorumlayici `yorumlayici_yolu()` ile cozulur; `sys.executable`
        DOGRUDAN kullanilmaz (KUSUR-ALTSERVIS-140).

        ## KUSUR-ALTSERVIS-141 (paket koku neden komuta gomulur)

        v1.4.1'de komut `<yorumlayici> -m kopru.servis_X` idi ve paket
        koku `PYTHONPATH` ile veriliyordu. Windows'ta gomulu Python
        kullanildigi icin bu ISLEMEDI: yanindaki `python311._pth`
        dosyasi bulununca CPython "isolated" kipe gecer, `PYTHONPATH`
        ve calisma dizini (cwd) YOK SAYILIR, `sys.path` yalnizca
        `._pth` iceriginden kurulur. Belirti:

            ModuleNotFoundError: No module named 'kopru'

        Asil duzeltme `gomulu_hazirla.py` icindedir (`._pth` dosyasina
        kurulum koku yazilir). Buradaki kalkan ikinci savunmadir: elle
        kurulmus, elden gecirilmis ya da `._pth`'i eksik bir dagitimda
        da servisler ayaga kalksin diye paket koku dogrudan komuta
        gomulur.

        `-c` ile kok `sys.path` basina eklenip modul `runpy` uzerinden
        `__main__` olarak kosturulur; boylece modulun `if __name__ ==
        "__main__"` blogu `-m` ile ozdes davranir.

        Kok yolu kaynak koda `repr()` ile gomulur: Windows yollarindaki
        ters bolu (`C:\\...`) ve bosluklar boylece kacislanir, elle
        tirnak/kacis kurma hatasi olanaksiz olur.
        """
        kok = paket_koku()
        onyukleyici = (
            "import sys, runpy; "
            "sys.path.insert(0, %r); "
            "runpy.run_module(%r, run_name='__main__', alter_sys=True)"
            % (kok, self.tanim["modul"])
        )
        return [yorumlayici_yolu(), "-c", onyukleyici]

    def baslat(self, ortam_ek=None):
        if self.calisiyor():
            return True, None
        self.son_hata = None
        self.cikis_kodu = None
        self.bitis_ts = None
        self._gunluk_ac()
        try:
            komut = self._komut()
        except RuntimeError as e:
            # Yorumlayici cozulemedi. Panelde "cikis kodu 2" gibi
            # anlamsiz bir iz yerine gercek nedeni goster.
            self.son_hata = str(e)
            self._yaz("BASLATILAMADI: %s" % self.son_hata)
            return False, self.son_hata
        ortam = dict(os.environ)
        # Alt surec `kopru` paketini bulabilmeli. PYTHONPATH, sistem
        # Python'unda (Linux/.deb kurulumu, gelistirme makinesi) calisan
        # yoldur; gomulu Windows Python'unda ISLEMEZ (isolated kip -
        # bkz. _komut icindeki KUSUR-ALTSERVIS-141). Bu yuzden burada
        # KALDIRILMAZ: iki ortam da desteklenmeli.
        kok = paket_koku()
        ortam["PYTHONPATH"] = kok + os.pathsep + ortam.get("PYTHONPATH", "")
        ortam["PYTHONUNBUFFERED"] = "1"     # cikti aninda gorunsun
        # Servis, olcumlerini (ornegin etkin dron sayisi) bu dosyaya
        # yazar. Alt surecin bellegi okunamayacagi icin dosya araciligi
        # zorunludur; panel ve merkez ayni kaynaktan okur.
        dd = self.tanim.get("durum_dosyasi")
        if dd:
            try:
                os.makedirs(os.path.dirname(dd), exist_ok=True)
                # Onceki calismadan kalan dosya BAYAT veridir; silinmezse
                # servis henuz olcum yazmadan once eski sayi okunur.
                if os.path.exists(dd):
                    os.remove(dd)
            except Exception:
                pass
            ortam["GOKTUNGU_KOPRU_DURUM_DOSYASI"] = dd
        # KUSUR-GCSDUAL-PORT (2026-08-14): panel -> alt servis komut
        # kanali. Aygit SAHA makinesinde takilidir; merkez portu acamaz.
        # Merkezden gelen "cantaya baglan / LED yak / kalibre et"
        # komutlari bu kanal uzerinden alt surece iner.
        #
        # Kanal her BASLATMADA temizlenir: onceki oturumda basilmis
        # dugmeler servis acilir acilmaz uygulanmamali ve gecen
        # oturumun "basarili" yaniti guncel sanilmamali.
        kanal_dizin = self.tanim.get("kanal_dizin") or (
            os.path.dirname(dd) if dd else "")
        if kanal_dizin:
            try:
                from . import servis_kanal as _sk
                os.makedirs(kanal_dizin, exist_ok=True)
                _sk.kanal_temizle(kanal_dizin, self.ad)
            except Exception:
                pass
            ortam["GOKTUNGU_KOPRU_KANAL_DIZIN"] = kanal_dizin
            ortam["GOKTUNGU_KOPRU_SERVIS_ADI"] = self.ad
        if ortam_ek:
            ortam.update({k: str(v) for k, v in ortam_ek.items()})
        try:
            ek = {}
            if os.name == "posix":
                ek["start_new_session"] = True
            else:
                ek["creationflags"] = getattr(
                    subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            self.surec = subprocess.Popen(
                komut, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                errors="replace", bufsize=1, env=ortam, cwd=kok, **ek)
        except Exception as e:
            self.son_hata = "%s: %s" % (type(e).__name__, e)
            self._yaz("BASLATILAMADI: %s" % self.son_hata)
            return False, self.son_hata
        self.baslama_ts = time.time()
        self._yaz("Servis baslatildi (pid %d)" % self.surec.pid)
        self._okuyucu = threading.Thread(target=self._oku_dongusu,
                                         name="servis-%s-oku" % self.ad,
                                         daemon=True)
        self._okuyucu.start()
        return True, None

    def _oku_dongusu(self):
        s = self.surec
        try:
            for satir in iter(s.stdout.readline, ""):
                self._yaz(satir.rstrip("\r\n"), "surec")
        except Exception as e:
            self._yaz("Cikti okunamadi: %s" % e)
        finally:
            with_kod = s.poll()
            if with_kod is None:
                try:
                    with_kod = s.wait(timeout=5)
                except Exception:
                    with_kod = None
            self.cikis_kodu = with_kod
            self.bitis_ts = time.time()
            self._yaz("Servis sonlandi (cikis kodu %s)" % with_kod)

    def durdur(self):
        s = self.surec
        if not (s and s.poll() is None):
            return True, None
        self._yaz("Durdurma istegi gonderildi")
        try:
            if os.name == "posix":
                # Surec GRUBUNA sinyal: torun surecler de sonlanir
                try:
                    os.killpg(os.getpgid(s.pid), signal.SIGTERM)
                except Exception:
                    s.terminate()
            else:
                s.terminate()
        except Exception as e:
            self.son_hata = str(e)
        try:
            s.wait(timeout=NAZIK_BEKLE_SN)
            return True, None
        except Exception:
            pass
        self._yaz("Nazik sonlandirma basarisiz; zorla kapatiliyor")
        try:
            if os.name == "posix":
                try:
                    os.killpg(os.getpgid(s.pid), signal.SIGKILL)
                except Exception:
                    s.kill()
            else:
                s.kill()
            s.wait(timeout=5)
        except Exception as e:
            self.son_hata = str(e)
            return False, self.son_hata
        return True, None


class ServisYoneticisi:
    """Uc servisi tek noktadan yonetir."""

    def __init__(self, gunluk_dizin=None, tanimlar=None):
        self.servisler = {}
        self.kanal_dizin = gunluk_dizin or "."
        for ad, tanim in (tanimlar or SERVIS_TANIM).items():
            tanim = dict(tanim)
            tanim.setdefault("durum_dosyasi", os.path.join(
                gunluk_dizin or ".", "durum_%s.json" % ad))
            tanim.setdefault("kanal_dizin", self.kanal_dizin)
            self.servisler[ad] = Servis(ad, tanim, gunluk_dizin)

    def al(self, ad):
        return self.servisler.get(str(ad))

    def durum(self, yetkiler=None):
        # SERVIS_SIRA'da olmayan (ozel tanimla eklenmis) servisler de
        # DUSURULMEZ: sonda alfabetik sirayla eklenir. Sessizce kaybolan
        # bir servis, panelde "neden gorunmuyor" sorusuna yol acar.
        sirali = [a for a in SERVIS_SIRA if a in self.servisler]
        ekstra = sorted(a for a in self.servisler if a not in SERVIS_SIRA)
        adlar = sirali + ekstra
        # v1.5.6 — yetki suzgeci. `yetkiler=None` verildiginde suzme
        # YAPILMAZ: ic cagirilar (tumunu_durdur, olcum, sinav) tam
        # listeyi gormeye devam etmeli.
        if yetkiler is not None:
            adlar = [a for a in adlar if servis_gorunur_mu(a, yetkiler)]
        return [self.servisler[a].durum() for a in adlar]

    def baslat(self, ad, ortam_ek=None, yetkiler=None):
        s = self.al(ad)
        if not s:
            return False, "Bilinmeyen servis: %s" % ad
        # Yetki denetimi SUNUCUDA yapilir. Menuyu JS'te saklamak
        # yeterli DEGILDIR: yetkisiz bir firma dogrudan
        # `POST /api/servis/baslat {"servis":"radar"}` diyerek servisi
        # yine ayaga kaldirabilirdi. Arayuzu saklamak denetim degildir.
        if yetkiler is not None and not servis_gorunur_mu(ad, yetkiler):
            return False, ("Bu servis firmanizin uyeliginde tanimli degil "
                           "(%s). Kurumsal panelden yetki talep edin." % ad)
        return s.baslat(ortam_ek)

    def durdur(self, ad, yetkiler=None):
        s = self.al(ad)
        if not s:
            return False, "Bilinmeyen servis: %s" % ad
        # Durdurma yetkisiz de olsa ENGELLENMEZ: yetki geri alinmis bir
        # firmada calisan servisin kapatilamamasi daha kotudur.
        return s.durdur()

    def tumunu_durdur(self):
        for s in self.servisler.values():
            if s.calisiyor():
                s.durdur()

    def calisan_sayisi(self):
        return sum(1 for s in self.servisler.values() if s.calisiyor())

    # -----------------------------------------------------------------
    # KUSUR-GCSDUAL-PORT: alt servise komut gonderme
    # -----------------------------------------------------------------
    def komut_gonder(self, ad, eylem, veri=None, zaman_asimi=8.0):
        """Alt servise komut yollar ve yanitini bekler.

        Donus: `(tamam, hata, veri)`.

        Servis CALISMIYORSA komut kuyruklanmaz ve ACIK hata dondurulur.
        Kuyruklamak burada YANLIS olur: kullanici "Baglan"a basip
        "tamam" gorur, oysa canta okunmuyordur ve dugmeler olusuz kalir.
        Servisin kapali oldugunu soylemek, pilotun panelde GroundGCC
        Sunucusu'nu baslatmasini saglar.
        """
        s = self.al(ad)
        if not s:
            return False, "Bilinmeyen servis: %s" % ad, {}
        if not s.calisiyor():
            baslik = s.tanim.get("baslik") or ad
            return (False,
                    "%s calismiyor. Kopru panelinde bu servisi baslatin."
                    % baslik, {})
        try:
            from . import servis_kanal as _sk
        except Exception as e:
            return False, "Komut kanali yuklenemedi: %s" % e, {}
        dizin = s.tanim.get("kanal_dizin") or self.kanal_dizin
        try:
            kid = _sk.komut_yaz(dizin, ad, eylem, veri or {})
            yanit = _sk.yanit_bekle(dizin, ad, kid,
                                    zaman_asimi=zaman_asimi)
        except Exception as e:
            return False, "Komut gonderilemedi: %s" % e, {}
        if yanit is None:
            # Sessizce basarili SAYILMAZ: servis kilitlenmis olabilir.
            return (False,
                    "Servis %.0f saniye icinde yanit vermedi."
                    % float(zaman_asimi or 0), {})
        return (bool(yanit.get("tamam")), str(yanit.get("hata") or ""),
                yanit.get("veri") or {})
