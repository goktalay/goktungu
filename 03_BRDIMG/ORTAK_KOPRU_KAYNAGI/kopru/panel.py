# -*- coding: utf-8 -*-
"""KOPRU YAZILIMI — yerel web paneli (HTTP).

## KULLANICI ISTEGI (birebir)

    "Kullanicilarin indirdigi sey locale bir sayfa acacak ama o sayfada
     dron, video ve ai sunucularini baslatma durdurma ve konsollarini
     gorme islevi olacak. bu sayfaya girerken kullanici adi ve sifre
     isteyecek."

## GUVENLIK TASARIMI VE NEDENLERI

1) TUM ARAYUZLERE BAGLANIR (varsayilan `0.0.0.0`)
   KULLANICI ISTEGI (2026-08-15, birebir): "yalniz kopru yazilimi sadece
   127.0.0.1'de calisiyor sanirim lutfen onu 0.0.0.0 yap".

   NEDENI: saha kurulumunda kopru makinesi genellikle ekransiz bir
   kutudur (GCS cantasi, rack sunucusu, kiosk). Panele yalniz o
   makinenin basinda oturarak erisilebilmesi, uzaktan servis baslatma
   ve merkeze kayit islemlerini imkansiz kiliyordu.

   BUNUN BEDELI VE KARSILIGI: panel servisleri baslatip durdurabilen bir
   YONETIM yuzeyidir. `0.0.0.0` demek, ayni aga erisen herkesin panel
   sayfasini GOREBILMESI demektir. Bu yuzden asagidaki korumalar
   varsayilan olarak acik tutulur ve `0.0.0.0` bunlarin YERINE gecmez:
     - Oturum zorunlulugu: sayfa gorulur, ama merkez kimligiyle giris
       yapilmadan hicbir servis baslatilamaz/durdurulamaz (madde 2)
     - CSRF basligi: cerez tek basina yetmez (madde 4)
     - Merkeze KAYIT ve ayar yazma islemleri yalniz YEREL istekten
       kabul edilir (madde 6) — agdaki biri kopruyu baska bir merkeze
       kaydedemez
     - Acilista panel, erisilebilir gercek adresi ve guvenlik duvari
       onerisini yazar (`main.py`)

   Yalniz yerel erisime donmek isteyen kullanici icin yol acik:
     panel_arayuz = 127.0.0.1   (panel ayarlari) veya
     python3 main.py --arayuz 127.0.0.1

   NOT: Dron servisinin MAVLink UDP cikisi bundan AYRIDIR ve zaten
   `0.0.0.0`'a baglanir (Mission Planner ayni agdaki baska
   bilgisayardan baglanabilsin). Yonetim yuzeyi ile veri yuzeyi farkli
   guvenlik siniflarindadir; artik ikisi de aga aciktir, ancak yonetim
   yuzeyi kimlik dogrulamasi ve yerel-istek kisitiyla korunur.

2) OTURUM CEREZI, TEMEL KIMLIK DOGRULAMA DEGIL
   HTTP Basic kullanilsaydi tarayici sifreyi HER istekte gonderirdi ve
   cikis yapmak imkansiz olurdu. Bunun yerine merkeze bir kez sorulur,
   rastgele bir oturum jetonu uretilir ve `HttpOnly` cerezde tutulur.

3) SIFRE DISKE YAZILMAZ
   Merkez sifresi yalniz dogrulama aninda bellekte durur. Diske
   yazilsaydi, dosyayi okuyan biri merkezin TAMAMINA erisirdi (kopru
   kimligi yalniz bu kuruluma ait, sifre ise kullanicinin tumune).

4) CSRF KORUMASI
   Durum degistiren tum istekler POST'tur ve `X-Kopru-Jeton` basligi
   ister. Yalniz cereze guvenilseydi, kullanici baska bir sitede
   gezerken o site `http://127.0.0.1:8790/api/servis/baslat` cagirip
   servisleri baslatabilirdi (cerez otomatik gider, ozel baslik gitmez).

5) KUCUK, BAGIMLILIKSIZ SUNUCU
   `http.server` kullanilir. Flask/FastAPI eklemek, kullanicinin
   makinesine pip bagimliliklari kurmayi zorunlu kilardi; kopru
   yaziliminin en onemli ozelligi SORUNSUZ KURULMASIDIR.

6) YIKICI ISLEMLER YALNIZ YEREL ISTEKTEN (0.0.0.0 ile birlikte eklendi)
   Panel aga acildiginda, oturum acmis bir kullanicinin yapabilecegi
   islerin tamami ayni risk sinifinda degildir. Servisi baslatip
   durdurmak geri alinabilir; kopruyu BASKA BIR MERKEZE kaydetmek ya
   da kimligi silmek geri alinamaz ve sahadaki tum cihazlari yanlis
   merkeze baglar. Bu yuzden asagidaki uc nokta, oturum acik olsa bile
   yalniz baglantinin KAYNAK ADRESI yerel oldugunda kabul edilir:
     - /api/merkez/kaydet (merkeze kayit / kimlik yenileme)
     - /api/ayar          (merkez adresi/arayuz/port yazma)
   Boylece agdan panele erisen biri servisleri yonetebilir ama kuruluma
   kalici zarar veremez. Yerel kabul edilen kaynaklar: 127.0.0.0/8,
   ::1 ve gecerli IPv4-mapped karsiliklari.
"""
import contextlib
import http.cookies
import ipaddress
import json
import mimetypes
import os
import re
import secrets
import socket
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import ayar as ayar_mod
from . import merkez as merkez_mod
from . import surumler as surum_mod
from .servisler import servis_gorunur_mu

WEB_DIZIN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
OTURUM_SURE_SN = 12 * 3600
CEREZ_AD = "goktungu_kopru"

# ---------------------------------------------------------------------
# ONBELLEK ETIKETI (v1.5.8)
#
# HTML icindeki `stil.css?v=157` / `uygulama.js?v=157` etiketleri
# teslim aninda GECERLI surume gore yeniden yazilir. Kaynak dosyada
# hangi sayi yazili oldugu onemsizdir; tek gercek kaynak KOPRU_SURUM.
#
# Neden gerekli: etiket elle guncellendigi surece bir surumde atlanmasi
# kacinilmazdir ve sonucu SESSIZ bir kusurdur -- tarayici eski betigi
# onbellekten sunar, kullanici duzeltmeleri gormez. 1.5.7'de ayni kusur
# bir kez giderilmisti; kalici cozum uretimi otomatiklestirmektir.
_ETIKET_DESEN = re.compile(r"(\?v=)[0-9]+")


def _onbellek_etiketi():
    """`1.5.8` -> `158`. Noktalar atilir, boylece adres kisa kalir."""
    return surum_mod.KOPRU_SURUM.replace(".", "")


class Oturumlar:
    """Bellek ici oturum deposu.

    Diske yazilmaz: kopru yeniden baslatildiginda oturumlarin
    dusmesi ISTENEN davranistir (servis yeniden kurulduysa kimlik
    yeniden dogrulanmalidir).
    """

    def __init__(self):
        self._veri = {}
        self._kilit = threading.Lock()

    def ac(self, kullanici):
        jeton = secrets.token_urlsafe(32)
        with self._kilit:
            self._veri[jeton] = {"kullanici": dict(kullanici),
                                 "ts": time.time()}
        return jeton

    def al(self, jeton):
        if not jeton:
            return None
        with self._kilit:
            k = self._veri.get(jeton)
            if not k:
                return None
            if time.time() - k["ts"] > OTURUM_SURE_SN:
                self._veri.pop(jeton, None)
                return None
            return k["kullanici"]

    def kapat(self, jeton):
        with self._kilit:
            self._veri.pop(jeton, None)

    def sayi(self):
        with self._kilit:
            return len(self._veri)


class PanelIsleyici(BaseHTTPRequestHandler):
    server_version = "GoktunguKopru/" + ayar_mod.SURUM
    protocol_version = "HTTP/1.1"

    # Sunucu ornegi tarafindan atanir
    uygulama = None

    # -----------------------------------------------------------------
    # Yardimcilar
    # -----------------------------------------------------------------
    def log_message(self, bicim, *arg):
        # Varsayilan gunluk stderr'e her istegi yazar; panel saniyede
        # bir durum sorgusu yaptigi icin bu konsolu bogar.
        pass

    def _cerez_oku(self):
        ham = self.headers.get("Cookie") or ""
        try:
            c = http.cookies.SimpleCookie()
            c.load(ham)
            if CEREZ_AD in c:
                return c[CEREZ_AD].value
        except Exception:
            pass
        return None

    def _govde_oku(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0:
            return {}
        if n > 4 * 1024 * 1024:
            return {}
        ham = self.rfile.read(n)
        try:
            v = json.loads(ham.decode("utf-8", "replace"))
            return v if isinstance(v, dict) else {}
        except Exception:
            return {}

    def _yaz(self, veri, kod=200, basliklar=None):
        ham = json.dumps(veri, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(ham)))
        self.send_header("Cache-Control", "no-store")
        # Panel tarayicida acilir; tiklama hirsizligina karsi
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        for a, d in (basliklar or {}).items():
            self.send_header(a, d)
        self.end_headers()
        self.wfile.write(ham)

    def _hata(self, mesaj, kod=400):
        self._yaz({"hata": str(mesaj)}, kod)

    def _oturum(self):
        return self.uygulama.oturumlar.al(self._cerez_oku())

    def _csrf_tamam(self):
        """Durum degistiren istekler icin ozel baslik zorunlu."""
        return bool(self.headers.get("X-Kopru-Jeton"))

    def _yerel_istek(self):
        """Istek bu makinenin kendisinden mi geliyor?

        Panel `0.0.0.0`'a baglandigi icin (kullanici istegi) geri
        alinamayan islemler agdan gelen isteklere KAPALIDIR. Karar
        yalniz TCP kaynak adresine dayanir; `X-Forwarded-For` gibi
        basliklar SAHTE olabilecegi icin dikkate ALINMAZ.
        """
        try:
            kaynak = self.client_address[0]
        except Exception:
            return False
        if not kaynak:
            return False
        # IPv6 icinde tasinan IPv4 (::ffff:127.0.0.1) ayiklanir.
        if kaynak.startswith("::ffff:"):
            kaynak = kaynak[7:]
        if kaynak in ("::1", "localhost"):
            return True
        try:
            return ipaddress.ip_address(kaynak).is_loopback
        except ValueError:
            return False

    def _yerel_zorunlu(self):
        """Yerel olmayan istegi reddeder; reddettiyse True doner."""
        if self._yerel_istek():
            return False
        self._hata(
            "Bu islem yalniz koprunun kurulu oldugu bilgisayardan "
            "yapilabilir. Panel aga acik oldugu icin merkeze kayit ve "
            "ayar yazma uzaktan engellenir.", 403)
        return True

    # -----------------------------------------------------------------
    # GET
    # -----------------------------------------------------------------
    def do_GET(self):
        yol = self.path.split("?", 1)[0]
        if yol.startswith("/api/"):
            self._api_get(yol)
            return
        self._statik(yol)

    def _statik(self, yol):
        if yol in ("/", ""):
            yol = "/index.html"
        # Dizin kacisi korumasi: `..` ile web dizininin disina cikilamaz
        hedef = os.path.normpath(os.path.join(WEB_DIZIN, yol.lstrip("/")))
        if not hedef.startswith(os.path.abspath(WEB_DIZIN)):
            self._hata("Gecersiz yol", 403)
            return
        if not os.path.isfile(hedef):
            self._hata("Bulunamadi", 404)
            return
        tur = mimetypes.guess_type(hedef)[0] or "application/octet-stream"
        try:
            with open(hedef, "rb") as f:
                ham = f.read()
        except Exception as e:
            self._hata(str(e), 500)
            return

        # ---- Onbellek etiketi surumden URETILIR (v1.5.8) ----
        #
        # Etiket onceden index.html icine ELLE yaziliyordu ('?v=157').
        # Surum yukseltildiginde etiketi guncellemek unutuldugunda kusur
        # SESSIZ olur: sunucu dogru dosyayi teslim eder ama tarayici
        # adresi ayni gordugu icin ESKI kopyayi kullanmaya devam eder.
        # Kullanici yeni surumu kurar, duzeltmeleri GORMEZ ve kusurun
        # giderilmedigini dusunur. Ayni kusur 1.5.7'de bir kez giderildi
        # ('?v=2' -> '?v=157'); elle yazildigi surece her surumde geri
        # gelmeye adaydi. Etiket artik teslim aninda surumden uretilir,
        # boylece guncellemeyi unutmak MUMKUN DEGIL.
        if hedef.endswith(".html"):
            with contextlib.suppress(Exception):
                ham = _ETIKET_DESEN.sub(
                    lambda m: m.group(1) + _onbellek_etiketi(),
                    ham.decode("utf-8")).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", tur + (
            "; charset=utf-8" if tur.startswith("text/") or
            tur in ("application/javascript", "image/svg+xml") else ""))
        self.send_header("Content-Length", str(len(ham)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(ham)

    def _api_get(self, yol):
        u = self.uygulama
        if yol == "/api/durum":
            # Giris yapilmadan da MINIMUM bilgi verilir: panel giris
            # ekraninda "merkez kaydi var mi" bilgisini gosterir.
            #
            # ANCAK panel artik `0.0.0.0`'a baglandigi icin bu yanit
            # agdaki HERKESE gider. `kimlik_maskeli()` gizli anahtari
            # ICERMEZ, ama kurulum UID'sini, firma kisa adini ve kayitli
            # kullanicinin E-POSTA adresini icerir. Bunlar kimlik avi
            # icin yeterli bilgidir ve giris ekraninin isine yaramaz.
            # Bu yuzden kimlik ozeti yalniz YEREL isteklere ve girisli
            # oturumlara verilir; agdan gelen anonim istek yalniz
            # "merkeze kayitli mi" bilgisini gorur.
            o = self._oturum()
            temel = {
                "surum": ayar_mod.SURUM,
                "girisli": bool(o),
            }
            # v1.6.0 — ILK ACILIS SIHIRBAZI icin durum bayraklari.
            #
            # Arayüz, sihirbazi GIRIS EKRANINDAN ONCE gosterip
            # gostermeyecegini bu iki alandan anlar. Alanlar oturum
            # GEREKTIRMEZ: sihirbazin tum varlik nedeni, kullanicinin
            # henuz giris YAPAMADIGI durumdur.
            #
            # Neden `yerel` de bildirilir: sihirbaz merkez adresini
            # yazar ve bu islem `_yerel_zorunlu()` ile korunur. Arayüz
            # bunu bilmezse, agdaki bir tarayicida formu gosterir,
            # kullanici doldurur ve 403 alir -- kullanicinin cozemeyecegi
            # bir hata. Bayrak sayesinde arayüz "bu islem koprunun
            # kurulu oldugu bilgisayardan yapilmalidir" diyebilir.
            with contextlib.suppress(Exception):
                _ay = ayar_mod.ayar_oku()
                temel["kurulum_gerekli"] = not bool(
                    _ay.get("merkez_secim_yapildi"))
                temel["merkez_adres_ozet"] = str(
                    _ay.get("merkez_adres") or "")
                temel["merkez_varsayilan"] = ayar_mod.VARSAYILAN_MERKEZ
                temel["merkez_varsayilan_http"] = (
                    ayar_mod.VARSAYILAN_MERKEZ_HTTP)
            temel["yerel"] = self._yerel_istek()
            if o or self._yerel_istek():
                temel["kimlik"] = ayar_mod.kimlik_maskeli()
            else:
                _k = ayar_mod.kimlik_maskeli()
                temel["kimlik"] = {"gizli_var": bool(_k.get("gizli_var"))}
            if o:
                # v1.5.6 — `yetkiler`: merkezin giris yanitindan gelen
                # firma yetki ozeti (`{dron,video,ai,radar,gccdual}`).
                # Bu alan olmadan panel hangi servisi gosterecegini
                # bilemez; onceki surumde alan demeti sabitti ve ozet
                # oturumda durdugu halde panele HIC ulasmiyordu.
                yetkiler = o.get("yetkiler")
                temel.update({
                    "kullanici": {a: o.get(a) for a in
                                  ("kullanici_id", "eposta", "ad", "soyad",
                                   "rol", "firma_id", "firma_unvan",
                                   "firma_kisa_ad", "yetkiler")},
                    "servisler": u.servis_durumu_zengin(yetkiler),
                    "ajan": u.ajan_durum(),
                    "ayar": u.ayar_maskeli(),
                    # Acik ucus kanallari: pilot hangi baglantinin
                    # gercekten veri tasidigini panelde gormeli. Yalniz
                    # "Dron: 3" yazmak yetmez; hangi porta baglandigini
                    # ve ne kadar byte gectigini gormeden ariza
                    # ayiklanamaz.
                    "kanallar": u.kanal_durumu(),
                })
            self._yaz(temel)
            return
        if yol == "/api/guncelleme":
            # Paket konumu veya kimlik verisi degil, yalniz imzali katalogdan
            # turetilmis guncelleme durumu verilir. Giris ekrani de eski
            # surumu kullaniciyi bekletmeden bildirebilir.
            self._yaz(u.guncelleme.durum())
            return
        if not self._oturum():
            self._hata("Oturum gerekli", 401)
            return
        if yol == "/api/surumler":
            # Surum defteri KODUN ICINDE tanimlidir; merkeze bagimli
            # degildir. Boylece merkez erisilemezken de kullanici hangi
            # surumu calistirdigini ve neyin degistigini gorebilir.
            self._yaz(surum_mod.defter())
            return
        if yol == "/api/logo":
            # NEDEN VEKIL: logo merkezde durur ve panel yerel adreste
            # calisir. Tarayicinin dogrudan merkeze gitmesi (a) merkez
            # adresini sayfaya gomer, (b) merkez erisilemezken kirik
            # gorsel gosterir, (c) karisik icerik uyarisi dogurur.
            # Vekil, logoyu bir kez cekip bellekte tutar.
            ham, tur = u.logo_al()
            if not ham:
                self._hata("Logo yok", 404)
                return
            self.send_response(200)
            self.send_header("Content-Type", tur or "image/png")
            self.send_header("Content-Length", str(len(ham)))
            self.send_header("Cache-Control", "private, max-age=600")
            self.end_headers()
            self.wfile.write(ham)
            return
        if yol == "/api/konsol":
            from urllib.parse import parse_qs, urlsplit
            s = parse_qs(urlsplit(self.path).query)
            ad = (s.get("servis") or [""])[0]
            sonrasi = (s.get("sonrasi") or ["0"])[0]
            srv = u.servisler.al(ad)
            if not srv:
                self._hata("Bilinmeyen servis", 404)
                return
            self._yaz({"servis": ad, "satirlar": srv.konsol_oku(sonrasi)})
            return
        self._hata("Bulunamadi", 404)

    # -----------------------------------------------------------------
    # POST
    # -----------------------------------------------------------------
    def do_POST(self):
        yol = self.path.split("?", 1)[0]
        if not yol.startswith("/api/"):
            self._hata("Bulunamadi", 404)
            return
        g = self._govde_oku()
        u = self.uygulama

        if yol == "/api/giris":
            # Giriste CSRF basligi ARANMAZ: henuz oturum yoktur ve
            # saldirgan cerezden yararlanamaz.
            eposta = str(g.get("eposta") or "").strip()
            sifre = str(g.get("sifre") or "")
            if not eposta or not sifre:
                self._hata("E-posta ve sifre zorunlu")
                return
            k, hata = merkez_mod.giris_dogrula(eposta, sifre)
            if hata:
                # Kaba kuvvet yavaslatmasi: yanlis her denemede 1 sn.
                time.sleep(1.0)
                self._hata(hata, 401)
                return
            jeton = u.oturumlar.ac(k)
            # Kurum logosu, GIREN kullanicinin firmasina gore belirlenir.
            # Baska firmadan bir personel girdiginde onbellek dusurulur,
            # aksi halde panelde ONCEKI kurumun logosu gorunurdu.
            u.logo_adres_ayarla(k.get("logo_adres") or "")
            cerez = ("%s=%s; Path=/; HttpOnly; SameSite=Strict; Max-Age=%d"
                     % (CEREZ_AD, jeton, OTURUM_SURE_SN))
            self._yaz({"tamam": True, "jeton": jeton,
                       "kullanici": k}, 200, {"Set-Cookie": cerez})
            return

        if not self._csrf_tamam():
            self._hata("Eksik istek basligi (X-Kopru-Jeton)", 403)
            return

        if yol == "/api/kurulum/kod":
            # 1.7.23 — API KODU ILE KURULUM (giris ONCESI; kullanici
            # istegi 2026-09-17). Kapi denetimi /api/kurulum/merkez ile
            # AYNI: yalniz yerel istek + secim henuz yapilmamis. Kod
            # kimligi ve adresi tasidigi icin e-posta/sifre sorulmaz.
            if self._yerel_zorunlu():
                return
            try:
                _a = ayar_mod.ayar_oku()
            except Exception:
                _a = {}
            if _a.get("merkez_secim_yapildi"):
                self._hata(
                    "Kurulum sihirbazi tamamlanmis: yeni API kodu yalniz "
                    "giris yaptiktan sonra Ayarlar > Merkez bolumunden "
                    "girilebilir.", 409)
                return
            sonuc = u.api_kodu_kur(g.get("kod"), g.get("secim"))
            if isinstance(sonuc, dict) and sonuc.get("hata"):
                self._hata(sonuc["hata"], 400)
                return
            self._yaz({"tamam": True, "sonuc": sonuc})
            return

        if yol == "/api/kurulum/merkez":
            # v1.6.0 — ILK ACILIS KURULUM SIHIRBAZI (giris ONCESI calisir)
            #
            # KULLANICI ISTEGI (birebir, 2026-08-16):
            #   "bu guncelleme sonrasinda kopru yazilimda da ilk
            #    girdigimizde sihirbaz gelmeli ve ip bilgilerini
            #    sormali, yoksa merkeze merkez kullanici ile baglanip
            #    sonra lokal kullaniciyla devam etmesi sacma olacaktir."
            #
            # NEDEN `/api/merkez/secim` YETMEZ (olculen kilitli dongu):
            # O uc OTURUM ve `yonetici` rolu ister; oturum ise
            # `merkez_mod.giris_dogrula()` uzerinden AYARDAKI merkez
            # adresine sorulur. Varsayilan adres GOKTUNGU bulutudur.
            # Kapali devre kurulumda kullanicinin hesabi KENDI Merkez
            # Uygulamasindadir, bulutta DEGIL. Yani:
            #   adresi duzeltmek icin -> giris gerekiyordu
            #   giris yapmak icin      -> adresin dogru olmasi gerekiyordu
            # Bu uc dongunun tek cikisidir ve bu yuzden oturum denetimi
            # yapilan satirlarin YUKARISINDA durur.
            #
            # KAPI DENETIMI (iki katman, oturumun yerine gecer):
            #  1. `_yerel_zorunlu()` — yalniz koprunun kurulu oldugu
            #     bilgisayardan. Panel `0.0.0.0`'a bagli oldugu icin
            #     bu sart olmadan agdaki herkes adresi yazabilirdi.
            #  2. Secim HENUZ yapilmamis olmali. Bir kez yapildiginda uc
            #     KAPANIR (409) ve degisiklik yalniz oturum acmis
            #     `yonetici` tarafindan `/api/merkez/secim` ile yapilir.
            #     Aksi halde calisan bir kurulumun merkez adresi, ayni
            #     makinede oturum acmadan sifirlanabilirdi.
            #
            # CSRF basligi YUKARIDA zorunlu kilinmistir: bu uc ondan
            # muaf DEGILDIR (kullanici baska bir sitede gezerken o site
            # kurulumun merkez adresini degistirebilirdi).
            if self._yerel_zorunlu():
                return
            try:
                _a = ayar_mod.ayar_oku()
            except Exception:
                _a = {}
            if _a.get("merkez_secim_yapildi"):
                self._hata(
                    "Kurulum sihirbazi tamamlanmis: merkez adresi "
                    "yalniz giris yaptiktan sonra Ayarlar bolumunden "
                    "degistirilebilir.", 409)
                return
            sonuc = u.merkez_secimi_kaydet(
                bool(g.get("kendi")),
                adres=g.get("merkez_adres"),
                http_adres=g.get("merkez_http"))
            if isinstance(sonuc, dict) and sonuc.get("hata"):
                self._hata(sonuc["hata"], 400)
                return
            self._yaz({"tamam": True, "ayar": sonuc})
            return

        if yol == "/api/cikis":
            u.oturumlar.kapat(self._cerez_oku())
            self._yaz({"tamam": True}, 200,
                      {"Set-Cookie": "%s=; Path=/; Max-Age=0" % CEREZ_AD})
            return

        o = self._oturum()
        if not o:
            self._hata("Oturum gerekli", 401)
            return

        if yol == "/api/guncelleme/denetle":
            # Denetim agdan cagrilabilir, ancak servis dongusunu bekletmez.
            basladi = u.guncelleme.denetle_arka_planda()
            self._yaz({"tamam": bool(basladi), "durum": u.guncelleme.durum()},
                      200 if basladi else 409)
            return
        if yol == "/api/guncelleme/indir":
            if self._yerel_zorunlu():
                return
            tamam, hata = u.guncelleme.indir_arka_planda()
            self._yaz({"tamam": bool(tamam), "hata": hata,
                       "durum": u.guncelleme.durum()}, 200 if tamam else 409)
            return
        if yol == "/api/guncelleme/kur":
            # Kod calistiran kurulum, yerel ve yonetici onayi olmadan asla
            # baslatilmaz; imzali paket/ozet denetimi yoneticide yeniden yapilir.
            if self._yerel_zorunlu():
                return
            if str(o.get("rol") or "") != "yonetici":
                self._hata("Guncelleme kurulumu icin yonetici rolu gerekir", 403)
                return
            tamam, hata = u.guncelleme.kurulum_baslat()
            self._yaz({"tamam": bool(tamam), "hata": hata,
                       "durum": u.guncelleme.durum()}, 200 if tamam else 409)
            return
        if yol == "/api/servis/baslat":
            # Yetki denetimi SUNUCUDA: menuyu gizlemek yeterli degildir,
            # yetkisiz firma bu ucu dogrudan cagirip radar/gccdual/ai
            # servisini ayaga kaldirabilirdi.
            tamam, hata = u.servisler.baslat(g.get("servis"),
                                             yetkiler=o.get("yetkiler"))
            self._yaz({"tamam": bool(tamam), "hata": hata or ""},
                      200 if tamam else 400)
            return
        if yol == "/api/servis/durdur":
            tamam, hata = u.servisler.durdur(g.get("servis"))
            self._yaz({"tamam": bool(tamam), "hata": hata or ""},
                      200 if tamam else 400)
            return
        if yol == "/api/m50/komut":
            # M50 fiziksel cihaz komutları yalnız yönetici tarafından ve
            # CSRF başlığıyla gönderilebilir. Menünün gizlenmesi tek başına
            # yetki değildir; doğrudan HTTP isteği de aynı kapıdan geçer.
            if str(o.get("rol") or "") != "yonetici":
                self._hata("M50 denetimi için yönetici rolü gerekir", 403)
                return
            if not servis_gorunur_mu("m50", o.get("yetkiler")):
                self._hata("Firmanız için M50 elektro-optik yetkisi yok", 403)
                return
            eylem = str(g.get("eylem") or "").strip().lower()
            izinli = {
                "durum", "ayar_oku", "ayar_yaz", "baglan", "kes", "ptz",
                "lens", "aci_konumla", "takip_sec", "takip_baslat", "takip_durdur",
                # 1.7.19: SDK geri kalani + coklu cihaz listesi
                "cihazlar", "aci_oku", "onayar_liste", "onayar_kaydet",
                "onayar_cagir", "onayar_sil", "onayar_hepsini_sil", "tarama",
                "takip_yetenek",
            }
            if eylem not in izinli:
                self._hata("İzin verilmeyen M50 eylemi", 400)
                return
            veri = g.get("veri") if isinstance(g.get("veri"), dict) else {}
            tamam, hata, cikti = u.servisler.komut_gonder(
                "m50", eylem, veri, zaman_asimi=35.0 if eylem == "baglan" else 8.0)
            sonuc = {"tamam": bool(tamam), "hata": hata or ""}
            if isinstance(cikti, dict):
                sonuc.update(cikti)
            # Savunma katmanı: alt süreç beklenmedik veri döndürse bile
            # bağlantı parolası veya oturum anahtarı HTTP yanıtına çıkmaz.
            for gizli in ("parola", "password", "pwd", "oturum", "token"):
                sonuc.pop(gizli, None)
            self._yaz(sonuc, 200 if tamam else 400)
            return
        if yol == "/api/ajan/baslat":
            tamam, hata = u.ajan_baslat()
            self._yaz({"tamam": bool(tamam), "hata": hata or ""},
                      200 if tamam else 400)
            return
        if yol == "/api/ajan/durdur":
            u.ajan_durdur()
            self._yaz({"tamam": True})
            return
        if yol == "/api/merkez/kod":
            # 1.7.23 — girisli yonetici yeni API kodu girer (panelde
            # "Kodu yenile" yapildiysa ya da kopru baska merkeze
            # tasiniyorsa). Yerel istek zorunlu: adres/kimlik yazimi
            # agdan yapilamaz.
            if self._yerel_zorunlu():
                return
            if str(o.get("rol") or "") != "yonetici":
                self._hata("Bu islem icin yonetici yetkisi gerekir", 403)
                return
            sonuc = u.api_kodu_kur(g.get("kod"), g.get("secim"))
            if isinstance(sonuc, dict) and sonuc.get("hata"):
                self._hata(sonuc["hata"], 400)
                return
            self._yaz({"tamam": True, "sonuc": sonuc})
            return
        if yol == "/api/merkez/kaydet":
            # Geri alinamaz: yanlis merkeze kayit tum sahayi kopartir.
            if self._yerel_zorunlu():
                return
            # Sifre YALNIZ bu cagride kullanilir ve diske yazilmaz.
            sonuc, hata = merkez_mod.kurulum_kaydet(
                str(g.get("eposta") or o.get("eposta") or ""),
                str(g.get("sifre") or ""),
                ad=g.get("ad"), yenile=bool(g.get("yenile")))
            if hata:
                self._hata(hata, 400)
                return
            u.kimlik_yenile()
            self._yaz({"tamam": True, "kimlik": sonuc})
            return
        if yol == "/api/ayar":
            # Merkez adresi/panel arayuzu/port yazimi kalicidir; agdan
            # degistirilmesi kopruyu erisilemez hale getirebilir.
            if self._yerel_zorunlu():
                return
            yeni = u.ayar_kaydet(g)
            self._yaz({"tamam": True, "ayar": yeni})
            return
        if yol == "/api/merkez/secim":
            # v1.5.6 — Merkez Uygulama satin alan sirkette, giris sonrasi
            # "telemetri nereye gitsin" sorusunun yaniti.
            #
            # Merkez adresi yazdigi icin `/api/ayar` ile AYNI kisitlar
            # gecerlidir: yalniz yerel istek ve yalniz `yonetici`. Rol
            # denetimi burada yapilir; arayuzde pencereyi gostermemek
            # yeterli degildir, pilot ucu dogrudan cagirip tum sahanin
            # merkez adresini degistirebilirdi.
            if self._yerel_zorunlu():
                return
            if str(o.get("rol") or "") != "yonetici":
                self._hata("Bu islem icin yonetici rolu gerekir", 403)
                return
            sonuc = u.merkez_secimi_kaydet(
                bool(g.get("kendi")),
                adres=g.get("merkez_adres"),
                http_adres=g.get("merkez_http"))
            if isinstance(sonuc, dict) and sonuc.get("hata"):
                self._hata(sonuc["hata"], 400)
                return
            self._yaz({"tamam": True, "ayar": sonuc})
            return
        self._hata("Bulunamadi", 404)


class Panel:
    """Yerel panel sunucusu (ayri is parcaciginda calisir)."""

    def __init__(self, uygulama, arayuz=None, port=None):
        self.uygulama = uygulama
        a = ayar_mod.ayar_oku()
        self.arayuz = (arayuz or a.get("panel_arayuz")
                       or ayar_mod.AYAR_VARSAYILAN["panel_arayuz"])
        self.port = int(port or a.get("panel_port")
                        or ayar_mod.VARSAYILAN_PANEL_PORT)
        self.httpd = None
        self._iplik = None

    def baslat(self):
        isleyici = type("Isleyici", (PanelIsleyici,),
                        {"uygulama": self.uygulama})
        # `ThreadingHTTPServer`: konsol akisi surerken durum sorgusu da
        # yanitlanabilsin. Tek is parcacikli sunucuda uzun bir istek tum
        # paneli kilitler.
        socketserver.TCPServer.allow_reuse_address = True
        self.httpd = ThreadingHTTPServer((self.arayuz, self.port), isleyici)
        self.httpd.daemon_threads = True
        self._iplik = threading.Thread(target=self.httpd.serve_forever,
                                       name="panel-http", daemon=True)
        self._iplik.start()
        return "http://%s:%d/" % (
            "127.0.0.1" if self.arayuz in ("0.0.0.0", "::") else self.arayuz,
            self.port)

    def erisim_adresleri(self):
        """Panelin GERCEKTEN erisilebilir oldugu adresleri dondurur.

        `0.0.0.0`'a baglandiginda kullaniciya "http://0.0.0.0:8790"
        yazmak ise yaramaz; o adres tarayiciya girilemez. Bu yuzden
        makinenin LAN adresleri bulunup dogrudan kullanilabilir
        baglantilar uretilir.
        """
        if self.arayuz not in ("0.0.0.0", "::", ""):
            return ["http://%s:%d/" % (self.arayuz, self.port)]
        adresler = ["http://127.0.0.1:%d/" % self.port]
        for ip in self._yerel_ipler():
            adres = "http://%s:%d/" % (ip, self.port)
            if adres not in adresler:
                adresler.append(adres)
        return adresler

    @staticmethod
    def _yerel_ipler():
        """Makinenin LAN IPv4 adresleri.

        `gethostbyname(gethostname())` KULLANILMAZ: birçok Ubuntu
        kurulumunda `/etc/hosts` makine adini 127.0.1.1'e esler ve bu
        yontem yalniz onu dondurur — yani agdan erisilemeyen bir adres.
        Yerine cekirdege "bu hedefe hangi arayuzden cikarim" sorulur;
        UDP yuvasi baglamak paket GONDERMEZ, yalniz yonlendirme
        tablosuna bakar.
        """
        bulunan = []
        for hedef in ("10.255.255.255", "192.168.1.1", "172.16.0.1"):
            s = None
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(0.2)
                s.connect((hedef, 9))
                ip = s.getsockname()[0]
                if ip and not ip.startswith("127.") and ip not in bulunan:
                    bulunan.append(ip)
            except Exception:
                pass
            finally:
                if s is not None:
                    with contextlib.suppress(Exception):
                        s.close()
        return bulunan

    def durdur(self):
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
