# -*- coding: utf-8 -*-
"""GRCOFFANDR — gömülü GRCOFF arka ucu (Android / Chaquopy giriş noktası).

Kotlin tarafındaki `ArkaUcServisi` bu modülün `baslat(veri_koku, port)`
fonksiyonunu bir arka plan iş parçacığında çağırır.

TASARIM: KOD YENİDEN KULLANIMI
------------------------------
Bu modül GRCOFF arka ucunu YENİDEN YAZMAZ. Masaüstü GRCOFF'un
kompozisyon kökü `main.uygulama_kur()`'u OLDUĞU GİBİ çağırır ve yalnız
Android'e özgü farkları ayarlar. Böylece sunucu, WebSocket, telemetri,
görev, radar, angajman mantığı masaüstü ile BİREBİR paylaşılır.

ANDROID FARKLARI
----------------
  * Veri deposu: PostgreSQL yerine cihaz-içi SQLite. GRCOFF zaten PG
    yapılandırması yoksa otomatik SQLite'a düşer; ayrıca
    `GOKTUNGU_ANDROID` bayrağı PG kurulum sihirbazını bastırır.
  * Veri kökü: uygulamanın özel `filesDir` klasörü (harici erişime kapalı).
  * HTTP portu: WebView'in yüklediği sabit port (`GOKTUNGU_HTTP_PORT`).
  * `main.main()` DEĞİL çağrılır: o `signal.signal` ile SIGTERM kancası
    kurar; bu yalnız ANA iş parçacığında çalışır. Arka uç bir arka plan
    iş parçacığında koştuğu için kurulum + döngü burada elle yapılır.
  * SITL (sanal dron) ve video (cv2) Android'de yoktur; ilgili çağrılar
    kendiliğinden ve zararsızca başarısız olur (tembel importlar).
"""
import os
import sys
import time
import socket
import traceback

_CALISIYOR = False
_GUNLUK = None
_GUNLUK_YOL = None


def _ikon_img():
    """Açılış ekranı için uygulama ikonunu (base64 PNG) <img> olarak döndürür."""
    try:
        from ikon_veri import IKON_B64
        return '<img alt="GÖKTUNGU" src="data:image/png;base64,%s">' % IKON_B64
    except Exception:
        return ""


def _gunlukle(mesaj):
    """Cihazda tanılama için veri kökündeki bir dosyaya yazar."""
    try:
        satir = "%s  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), mesaj)
        if _GUNLUK:
            _GUNLUK.write(satir)
            _GUNLUK.flush()
        _asil_stdout().write("[GRCOFFANDR] " + mesaj + "\n")
        _asil_stdout().flush()
    except Exception:
        pass


class _Tee:
    """stdout/stderr'i hem asıl akışa (logcat) hem log dosyasına yazar."""
    def __init__(self, asil):
        self._asil = asil

    def write(self, s):
        try:
            self._asil.write(s)
        except Exception:
            pass
        try:
            if _GUNLUK:
                _GUNLUK.write(s)
                _GUNLUK.flush()
        except Exception:
            pass

    def flush(self):
        try:
            self._asil.flush()
        except Exception:
            pass


_ASIL_STDOUT = None


def _asil_stdout():
    return _ASIL_STDOUT or sys.stdout


def _stdio_yakala():
    """uygulama_kur çıktısını (tanı için) log dosyasına da yönlendirir."""
    global _ASIL_STDOUT
    if _ASIL_STDOUT is None:
        _ASIL_STDOUT = sys.stdout
        sys.stdout = _Tee(sys.stdout)
        sys.stderr = _Tee(sys.stderr)


def _port_hazir_bekle(port, zaman_asimi=25.0):
    """127.0.0.1:port bağlanabilir olana kadar bekler (HTTP ayakta mı)."""
    bitis = time.time() + zaman_asimi
    while time.time() < bitis:
        try:
            with socket.create_connection(("127.0.0.1", int(port)), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def _yigin_string():
    """Tüm iş parçacıklarının yığınını string döndürür (fd gerektirmez)."""
    try:
        import sys as _sys
        import traceback as _tb
        try:
            _adlar = {t.ident: t.name for t in __import__("threading").enumerate()}
        except Exception:
            _adlar = {}
        parcalar = []
        for _tid, _frame in _sys._current_frames().items():
            parcalar.append("--- İş parçacığı %s (%s) ---\n"
                            % (_adlar.get(_tid, "?"), _tid))
            parcalar.append("".join(_tb.format_stack(_frame)))
            parcalar.append("\n")
        return "".join(parcalar) or "(çalışan iş parçacığı yok)"
    except Exception:
        return "(yığın dökümü alınamadı: %s)" % traceback.format_exc()


def _log_kuyrugu(n=200):
    try:
        if _GUNLUK_YOL and os.path.isfile(_GUNLUK_YOL):
            with open(_GUNLUK_YOL, encoding="utf-8", errors="replace") as f:
                return "".join(f.readlines()[-n:])
    except Exception:
        pass
    return "(günlük okunamadı)"


class _AcilisSunucusu:
    """Arka uç kurulurken WebView'e 'başlatılıyor' sayfası; hata olursa
    aynı sunucu gerçek hatayı (traceback + günlük) gösterir.

    Neden: tablette uygulama_kur (numpy + kurulum) 30-60 sn sürebilir; bu
    sürede boş 'bağlantı reddedildi' yerine ilerleme gösterilir. Gerçek
    sunucu hazır olunca bu sunucu KAPATILIR ve port ona devredilir.
    """
    def __init__(self, port):
        self.port = int(port)
        self._t0 = time.time()
        self.hata = None
        self._srv = None

    def _sayfa(self):
        import html as _html
        if self.hata:
            return (
                "<!doctype html><html lang=tr><head><meta charset=utf-8>"
                "<meta name=viewport content='width=device-width,initial-scale=1'>"
                "<title>GÖKTUNGU — Arka uç başlatılamadı</title>"
                "<style>body{margin:0;background:#12161c;color:#e7eef6;"
                "font-family:system-ui,sans-serif;padding:16px}h1{color:#ff6b6b;"
                "font-size:20px}pre{white-space:pre-wrap;word-break:break-word;"
                "background:#0b0e12;border:1px solid #2a323c;border-radius:8px;"
                "padding:12px;font-size:12px}h2{font-size:14px;color:#9fb2c8}"
                "</style></head><body><h1>GÖKTUNGU arka ucu başlatılamadı</h1>"
                "<p>Aşağıdaki bilgiyi geliştiriciye iletin.</p>"
                "<h2>Hata</h2><pre>%s</pre>"
                "<h2>Günlük (son satırlar)</h2><pre>%s</pre></body></html>"
            ) % (_html.escape(self.hata), _html.escape(_log_kuyrugu()))
        return (
            "<!doctype html><html lang=tr><head><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<meta http-equiv=refresh content=2>"
            "<title>GÖKTUNGU</title>"
            "<style>html,body{margin:0;height:100%;background:#0b1622;"
            "color:#e7eef6;font-family:system-ui,sans-serif;display:flex;"
            "align-items:center;justify-content:center;flex-direction:column}"
            "h1{letter-spacing:2px;margin:0 0 6px}p{opacity:.7}"
            ".n{margin-top:16px;width:180px;height:3px;background:#1b2a3c;"
            "overflow:hidden;border-radius:3px}.n b{display:block;height:100%;"
            # NOT: bu HTML'de literal % işaretleri var (CSS yüzdeleri,
            # @keyframes). Bu yüzden `%` BİÇİMLENDİRME KULLANILMAZ; ikon
            # birleştirmeyle eklenir (aksi halde ValueError → boş yanıt).
            "width:40%;background:#1f6feb;animation:s 1.1s infinite}"
            "@keyframes s{0%{margin-left:-40%}100%{margin-left:100%}}"
            "img{width:96px;height:96px;margin-bottom:14px;border-radius:22px}"
            "p .sn{opacity:.55;font-size:13px}"
            "</style></head><body>" + _ikon_img()
            + "<h1>GÖKTUNGU</h1><p>Başlatılıyor… "
            + ("<span class=sn>%d sn</span>" % int(time.time() - self._t0))
            + "</p><div class=n><b></b></div></body></html>")

    def _yap_handler(self):
        from http.server import BaseHTTPRequestHandler
        disari = self

        class _H(BaseHTTPRequestHandler):
            def do_GET(self):
                govde = disari._sayfa().encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(govde)))
                self.end_headers()
                self.wfile.write(govde)

            def log_message(self, *a):
                pass
        return _H

    def baslat(self):
        from http.server import ThreadingHTTPServer
        import threading
        try:
            self._srv = ThreadingHTTPServer(("127.0.0.1", self.port),
                                            self._yap_handler())
            threading.Thread(target=self._srv.serve_forever, daemon=True,
                             name="acilis-sunucu").start()
            _gunlukle("Açılış sunucusu 127.0.0.1:%s'te açıldı." % self.port)
        except Exception:
            _gunlukle("Açılış sunucusu açılamadı:\n" + traceback.format_exc())

    def kapat(self):
        try:
            if self._srv:
                self._srv.shutdown()
                self._srv.server_close()
                self._srv = None
        except Exception:
            pass

    def hatada_bekle(self, hata):
        """Hata sayfasını gösterir ve süresiz bloklar (WebView okusun)."""
        self.hata = hata
        while True:
            time.sleep(3600)


def _ortam_hazirla(veri_koku, web_koku, port):
    """Android'e özgü ortam değişkenlerini ve dizinleri hazırlar."""
    global _GUNLUK, _GUNLUK_YOL
    os.makedirs(veri_koku, exist_ok=True)
    for alt in ("veri", "harita_cache", "kayitlar", "gunluk"):
        os.makedirs(os.path.join(veri_koku, alt), exist_ok=True)
    _GUNLUK_YOL = os.path.join(veri_koku, "gunluk", "android_arka_uc.log")
    # Önceki çalıştırmadan kalan bayrak/döküm dosyalarını temizle (taze tanı).
    for _ad in ("hazir.flag", "yigin_dokumu.log"):
        try:
            os.remove(os.path.join(veri_koku, "gunluk", _ad))
        except OSError:
            pass

    # Veri kökü: sabitler.py ve veritabani.py bunu okur (gcs.db burada).
    os.environ["GOKTUNGU_VERI_KOKU"] = veri_koku
    # Web kökü: Kotlin'in APK'den filesDir/web'e ayıkladığı arayüz dizini.
    # sabitler.py bu değişkeni okuyup HTTP kökünü buradan gösterir.
    if web_koku and os.path.isfile(os.path.join(web_koku, "index.html")):
        os.environ["GOKTUNGU_WEB_KOKU"] = web_koku
    # Gömülü Android işareti: PG sihirbazını bastırır (sunucu.py + JS).
    os.environ["GOKTUNGU_ANDROID"] = "1"
    # WebView bu porttan yükler; HTTP sunucusu bu portu bağlar.
    os.environ["GOKTUNGU_HTTP_PORT"] = str(port)
    # PG yapılandırması BİLEREK ayarlanmaz → veritabani otomatik SQLite.

    try:
        # "w": her çalıştırmada TAZE log (ekleme kipinde eski sürümlerin
        # gürültüsü tanıyı karıştırıyordu).
        _GUNLUK = open(_GUNLUK_YOL, "w", encoding="utf-8")
    except Exception:
        _GUNLUK = None


_USB_TCP_PORT = "5760"
_USB_HOST = "127.0.0.1"

# DJI native köprüsü (Faz 4): Kotlin MSDK katmanı 127.0.0.1:8790'daki
# GDP (NDJSON) sunucusuna bağlanır. "dji" türü bir bağlantı kaydı
# olmadan dji_kopru.py o portu DİNLEMEZ; bu yüzden (yoksa) kaydedilir.
# Kullanıcı arayüzden "Bağlan"a dokununca sunucu 8790'ı dinlemeye başlar
# ve native istemci (üstel geri çekilmeyle bekleyen) bağlanır.
_DJI_PORT = "8790"


def _dji_baglantisini_kaydet(baglantilar):
    """DJI native köprüsü için 'dji' türü bağlantıyı (yoksa) ekler."""
    for k in (baglantilar.listele() or []):
        if k.get("tur") == "dji" and str(k.get("port")) == _DJI_PORT:
            return  # zaten kayıtlı
    kid, hata = baglantilar.ekle(
        "DJI Aracı (yerel)", "dji", _DJI_PORT, ucus_yazilimi="dji")
    if hata:
        _gunlukle("DJI bağlantısı eklenemedi: %s" % hata)
    else:
        _gunlukle("DJI bağlantısı kaydedildi (dji:0.0.0.0:%s)" % _DJI_PORT)


def _usb_baglantisini_kaydet(baglantilar):
    """USB köprüsü için tcp:127.0.0.1:5760 bağlantısını (yoksa) ekler."""
    for k in (baglantilar.listele() or []):
        if (k.get("tur") == "tcp" and str(k.get("port")) == _USB_TCP_PORT
                and str(k.get("host") or "") in (_USB_HOST, "localhost")):
            return  # zaten kayıtlı
    kid, hata = baglantilar.ekle(
        "USB Uçuş Kontrolcüsü", "tcp", _USB_TCP_PORT,
        host=_USB_HOST, ucus_yazilimi="ardupilot")
    if hata:
        _gunlukle("USB bağlantısı eklenemedi: %s" % hata)
    else:
        _gunlukle("USB bağlantısı kaydedildi (tcp:%s:%s)" % (_USB_HOST, _USB_TCP_PORT))


def baslat(veri_koku, web_koku, port):
    """Kotlin tarafından çağrılır. Arka ucu kurar ve döngüye girer (bloklar)."""
    global _CALISIYOR
    if _CALISIYOR:
        return
    _CALISIYOR = True

    _ortam_hazirla(veri_koku, web_koku, port)
    _stdio_yakala()
    _gunlukle("Arka uç başlıyor. veri_koku=%s web_koku=%s http_port=%s python=%s"
              % (veri_koku, web_koku, port, sys.version.split()[0]))

    import asyncio
    import threading

    # Açılış sunucusu: WebView'e hemen "başlatılıyor" göster (kurulum
    # tablette 30-60 sn sürebilir). Hazır olunca port gerçek sunucuya
    # devredilir; çökerse bu sunucu hatayı gösterir.
    acilis = _AcilisSunucusu(port)
    acilis.baslat()

    # uygulama_kur'u WORKER THREAD'de çalıştır ve ASILMAYA karşı izle.
    # Neden: Android'de bir başlangıç çağrısı (DNS/soket/subprocess) sonsuza
    # kadar bloklarsa "Başlatılıyor" ekranı sonsuza döner. Watchdog belirli
    # süre sonra TÜM iş parçacığı yığınlarını hata ekranına döker; böylece
    # asılmanın TAM YERİ görülür.
    #
    # Ayrıca uygulama_kur boyunca soket varsayılan zaman aşımı 30 sn: ağ/DNS
    # kaynaklı asılma zaman aşımına uğrar (çoğu çağrı try/except ile sarılı,
    # böylece kurulum devam eder). Sunum başlamadan önce sıfırlanır.
    try:
        _watchdog_sn = int(os.environ.get("GRCOFFANDR_WATCHDOG_SN") or 40)
    except ValueError:
        _watchdog_sn = 40

    # GIL'i TUTAN bir asılmada Python thread'leri (watchdog + açılış
    # sunucusu) donar; C-seviyesi faulthandler zamanlayıcısı yine de
    # gerçek dosyaya yazar. Kotlin bu dosyayı okuyup gösterir.
    global _GUNLUK_YOL
    _yigin_dosya = None
    try:
        import faulthandler as _fh
        _yol = os.path.join(os.path.dirname(_GUNLUK_YOL or "."), "yigin_dokumu.log")
        _yigin_dosya = open(_yol, "w", encoding="utf-8")
        _fh.dump_traceback_later(_watchdog_sn + 3, repeat=True, file=_yigin_dosya)
    except Exception:
        pass

    _sonuc = {}

    def _kur():
        try:
            import socket as _sk
            _sk.setdefaulttimeout(30)
            # goktungu paketini main.py'den ÖNCE doğrula: Chaquopy sanal
            # importer ile yükler (dosya sisteminde dizin yoktur). Böylece
            # sys.modules'a girer ve main.py'nin paket kontrolü geçer.
            import goktungu  # noqa: F401
            import main as _main  # assets/python/main.py
            ws, http = _main.uygulama_kur()
            try:
                _usb_baglantisini_kaydet(ws.baglantilar)
            except Exception as e:
                _gunlukle("USB bağlantısı kaydedilemedi: %r" % e)
            try:
                _dji_baglantisini_kaydet(ws.baglantilar)
            except Exception as e:
                _gunlukle("DJI bağlantısı kaydedilemedi: %r" % e)
            _sonuc["ws"], _sonuc["http"] = ws, http
        except BaseException:
            # BaseException: `import main` SystemExit fırlatabilir (paket
            # bulunamazsa); Exception onu YAKALAMAZ. Hata ekranda görünsün.
            _sonuc["hata"] = traceback.format_exc()
        finally:
            try:
                import socket as _sk
                _sk.setdefaulttimeout(None)
            except Exception:
                pass

    _kt = threading.Thread(target=_kur, daemon=True, name="uygulama-kur")
    _kt.start()
    _kt.join(_watchdog_sn)

    # Kurulum bitti/çöktü: C-seviyesi zamanlayıcıyı durdur.
    try:
        import faulthandler as _fh
        _fh.cancel_dump_traceback_later()
        if _yigin_dosya:
            _yigin_dosya.close()
    except Exception:
        pass

    if _kt.is_alive():
        # ASILDI: yığın dökümünü sys._current_frames ile string olarak al
        # (faulthandler.dump_traceback bir StringIO'ya yazamaz — fd ister).
        ozet = ("Arka uç %d sn içinde başlamadı (ASILDI). Bir başlangıç "
                "çağrısı bloklanıyor. İş parçacığı yığın dökümü:\n\n"
                % _watchdog_sn + _yigin_string())
        _gunlukle(ozet)
        _CALISIYOR = False
        acilis.hatada_bekle(ozet)
        return

    if _sonuc.get("hata"):
        _gunlukle("ARKA UÇ ÇÖKTÜ (uygulama_kur):\n" + _sonuc["hata"])
        _CALISIYOR = False
        acilis.hatada_bekle(_sonuc["hata"])
        return

    ws_sunucu, http_sunucu = _sonuc["ws"], _sonuc["http"]
    _gunlukle("uygulama_kur() tamam.")

    # Kurulum tamam: portu açılış sunucusundan gerçek HTTP sunucusuna devret.
    acilis.kapat()

    _http_hata = []

    def _http_calistir():
        try:
            http_sunucu.calistir()   # allow_reuse_address açık; TIME_WAIT sorun değil
        except Exception:
            _http_hata.append(traceback.format_exc())
            _gunlukle("HTTP SUNUCUSU ÇÖKTÜ:\n" + _http_hata[-1])

    threading.Thread(target=_http_calistir, daemon=True,
                     name="grcoff-http").start()

    if not _port_hazir_bekle(port):
        ozet = ("HTTP sunucusu %s portuna zamanında bağlanmadı.\n\n" % port
                + ("".join(_http_hata)
                   or "(HTTP thread hata vermedi; günlüğe bakın)"))
        _gunlukle(ozet)
        _CALISIYOR = False
        hata_sun = _AcilisSunucusu(port)
        hata_sun.baslat()
        hata_sun.hatada_bekle(ozet)   # bloklar
        return

    # HAZIR bayrağı: Kotlin bunu görürse arka ucun ayakta olduğunu bilir
    # ve tanı fallback'ini göstermez (GIL-tutan asılmada bu dosya oluşmaz).
    try:
        with open(os.path.join(os.path.dirname(_GUNLUK_YOL), "hazir.flag"),
                  "w", encoding="utf-8") as _hf:
            _hf.write(str(int(time.time())))
    except Exception:
        pass

    _gunlukle("HTTP 127.0.0.1:%s hazır. WS döngüsü başlıyor." % port)
    try:
        # WebSocket + telemetri asyncio döngüsünde. main.main()'deki
        # SIGTERM kancası ATLANIR (arka plan iş parçacığında signal yok).
        asyncio.run(ws_sunucu.calistir())
    except Exception:
        _gunlukle("WS DÖNGÜSÜ ÇÖKTÜ:\n" + traceback.format_exc())
        _CALISIYOR = False
