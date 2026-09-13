"""GRCOFF paket 2.5.23 / uygulama 2.4.153 kaynak yamasi (2.5.22 uzerine).

GRCOFF Merkez ayni zamanda AI sunucusudur: yerel AI iscisi Merkez ile
birlikte baslar, AI yoneticisine kendini tanitir ve kopru gerektirmeden
canli goruntuye AI uygular.

OLCULEN KUSURLAR (2.4.150 - 2.4.152):
  1. main()'deki _yerel_ai_isci_baslat cagrisi betigi <kok>/ai_sunucu.py'de
     ariyordu; pakette <kok>/assets/python/ai_sunucu.py altindadir, isci
     hic ayaga kalkmiyordu.
  2. Cagri port ortam degiskenini ve kaydi bilmiyordu; tek basina
     duzeltilse bile iki yol (eski cagri + bekci) iki surec acardi.
  3. Isci ai_sunucular tablosuna kaydedilmiyordu; AI yoneticisi yalniz
     kayitli iscilere gorev verdigi icin "Uygun (cevrimici/bos) AI sunucusu
     yok" hatasi donuyordu.
  4. AI portu sabitti (8900); kurulum GOKTUNGU_AI_PORT=8910 verir.
     Isci goruntuyu kaldirilmis 8801 MJPEG dinleyicisinden okumaya
     calisiyordu (Connection refused); canli yayin yalniz Merkez HTTP
     `/kamera/<id>` yolunda ve oturum ister -> yerel isci anahtari.
  5. Isci kayitlari program dizinine yaziyordu; Linux servisinde
     (ReadWritePaths) yazma izni yok -> isci acilista coker.
  6. Kamera formunda GRCOFF iscisinde KAPALI olan Kisi/Arac Tanima
     anahtarlari gorunuyordu (2.4.152'de geri eklenmisti).

Kullanim: python3.11 yama_2523.py <KAYNAK_KOKU>
"""
import os
import re
import sys

KOK = sys.argv[1]


def oku(yol):
    with open(os.path.join(KOK, yol), encoding="utf-8") as f:
        return f.read()


def yaz(yol, metin):
    with open(os.path.join(KOK, yol), "w", encoding="utf-8") as f:
        f.write(metin)


def degistir(metin, eski, yeni, ad):
    n = metin.count(eski)
    if n != 1:
        sys.exit(f"HATA [{ad}]: capa {n} kez bulundu (1 bekleniyordu)")
    return metin.replace(eski, yeni)


# ------------------------------------------------------------ ai_sunucu.py
a = oku("ai_sunucu.py")
a = degistir(a, '''KAYIT_KLASORU = _ai_yolu("ai_kayitlar")
''', '''KAYIT_KLASORU = _ai_yolu("ai_kayitlar")

# v2.4.153: Kurulumda (Windows servisi / Linux systemd) program dizini
# YAZMAYA KAPALIDIR; veri koku GOKTUNGU_VERI_KOKU ile verilir. Kayitlar
# daima oraya yazilir. Modeller once veri kokunde aranir (kullanici
# guncel model koyabilsin), yoksa paketle gelen salt-okunur dizin kullanilir.
_KURULUM_VERI = (os.environ.get("GOKTUNGU_VERI_KOKU") or "").strip()
if _KURULUM_VERI:
    KAYIT_KLASORU = os.path.join(_KURULUM_VERI, "ai_kayitlar")
    if os.path.isdir(os.path.join(_KURULUM_VERI, "ai_modeller")):
        MODEL_KLASORU = os.path.join(_KURULUM_VERI, "ai_modeller")
''', "isci-veri-koku")

a = degistir(a, '''        if self.protokol == "gcs_proxy":
            taban = self.isci.ana_url  # http://ANA_IP:8000
            if "://" in taban:
                sema, kalan = taban.split("://", 1)
                host = kalan.split("/")[0].rsplit(":", 1)[0]
                return "%s://%s:8801%s" % (sema, host, self.url)
            return taban.rstrip("/") + self.url
        return self.url''', '''        if self.protokol == "gcs_proxy":
            # v2.4.153: Ayri MJPEG dinleyicisi (8801/8811) guvenlik
            # gerekcesiyle KALDIRILDI (video_proxy.calistir). Canli yayin
            # yalniz Merkez HTTP'nin `/kamera/<id>` yolundadir; isci oraya
            # yerel isci anahtariyla (X-Goktungu-AI-Isci) baglanir.
            # Yol YALNIZ `/kamera/<sayi>` olabilir: aksi halde
            # `@baska-sunucu/...` gibi bir yol, anahtar basligini
            # disaridaki bir sunucuya gonderirdi.
            if not re.fullmatch(r"/kamera/[0-9]{1,9}", str(self.url or "")):
                raise ValueError("gecersiz gcs_proxy yolu")
            return self.isci.ana_url.rstrip("/") + self.url
        return self.url''', "isci-url")

if not re.search(r"^import re$", a, re.M):
    a = degistir(a, "import json\n", "import json\nimport re\n", "isci-import-re")

a = degistir(a, '''def http_sunucu(isci, port):''', '''def http_sunucu(isci, port, dinle="0.0.0.0"):''', "isci-dinle-imza")
a = degistir(a, '''    srv = ThreadingHTTPServer(("0.0.0.0", port), Istek)
    print(f"[AI] HTTP API dinleniyor: 0.0.0.0:{port}")''', '''    srv = ThreadingHTTPServer((dinle, port), Istek)
    print(f"[AI] HTTP API dinleniyor: {dinle}:{port}")''', "isci-dinle")
a = degistir(a, '''    p.add_argument("--ana", default="http://127.0.0.1:8000",''', '''    # v2.4.153: GRCOFF yerel iscisi --dinle 127.0.0.1 ile baslar; ayri AI
    # bilgisayarinda calisan eski tip isci icin varsayilan degismedi.
    p.add_argument("--dinle", default="0.0.0.0",
                   help="dinlenecek adres (yerel isci: 127.0.0.1)")
    p.add_argument("--ana", default="http://127.0.0.1:8000",''', "isci-dinle-arg")
a = degistir(a, '''    http_sunucu(isci, args.port)''', '''    http_sunucu(isci, args.port, args.dinle)''', "isci-dinle-cagri")

a = degistir(a, '''    def _akisi_isle(self):
        url = self._url_coz()
        cap = cv2.VideoCapture(url)''', '''    def _akisi_isle(self):
        url = self._url_coz()
        if self.protokol == "gcs_proxy":
            # Merkez MJPEG verir; baslik (isci anahtari) gondermek ve
            # Windows'ta FFMPEG'siz OpenCV farklarindan kacinmak icin saf
            # Python MJPEG okuyucu kullanilir.
            self._akisi_isle_mjpeg(url)
            return
        cap = cv2.VideoCapture(url)''', "isci-mjpeg-yolu")

a = degistir(a, '''        istek = urllib.request.Request(
            url, headers={"User-Agent": "goktungu-ai"})''', '''        basliklar = {"User-Agent": "goktungu-ai"}
        _jeton = os.environ.get("GOKTUNGU_AI_ISCI_JETON") or ""
        if _jeton and self.protokol == "gcs_proxy":
            basliklar["X-Goktungu-AI-Isci"] = _jeton
        istek = urllib.request.Request(url, headers=basliklar)''', "isci-baslik")
yaz("ai_sunucu.py", a)

# ------------------------------------------------ sunucu.py: /kamera yetkisi
su = oku("goktungu/sunucu.py")
su = degistir(su, '''                        if not self.server.goktungu_http._kamera_oturum_gecerli(ham):
                            self.send_error(401, "Kamera oturumu gerekli")
                            return None
                        return self._kamera_mjpeg_sun()''', '''                        if not (self.server.goktungu_http._kamera_oturum_gecerli(ham)
                                or self._yerel_ai_isci_mi()):
                            self.send_error(401, "Kamera oturumu gerekli")
                            return None
                        return self._kamera_mjpeg_sun()''', "kamera-yetki")
su = degistir(su, '''            def _kamera_mjpeg_sun(self):''', '''            def _yerel_ai_isci_mi(self):
                """v2.4.153: GRCOFF yerel AI iscisi canli yayini okuyabilir.

                Kosullarin HEPSI gerekir: istek geri donus (loopback)
                adresinden gelir; `X-Goktungu-AI-Isci` basligi, Merkez'in
                veri dizininde urettigi en az 32 karakterlik isci anahtariyla
                sabit-zamanli eslesir. Anahtar yalniz GRCOFF'ta (main.py
                _yerel_ai_bekci) ortama konur; GRCON'da tanimsizdir, bu yol
                orada her zaman kapalidir.
                """
                beklenen = os.environ.get("GOKTUNGU_AI_ISCI_JETON") or ""
                gelen = self.headers.get("X-Goktungu-AI-Isci") or ""
                if len(beklenen) < 32 or not gelen:
                    return False
                if str(self.client_address[0]) not in (
                        "127.0.0.1", "::1", "::ffff:127.0.0.1"):
                    return False
                return hmac.compare_digest(gelen.encode("utf-8"),
                                           beklenen.encode("utf-8"))

            def _kamera_mjpeg_sun(self):''', "kamera-isci-fonk")
yaz("goktungu/sunucu.py", su)

# ------------------------------------------------------------------ main.py
m = oku("main.py")
m = degistir(m, '''def _yerel_ai_dinliyor(port=8900):''', '''AI_ISCI_ADI = "GRCOFF Yerel AI"


def _yerel_ai_portu():
    """v2.4.153: Kurulum AI portunu kaydirir (GOKTUNGU_AI_PORT=8910)."""
    try:
        return int(os.environ.get("GOKTUNGU_AI_PORT") or 8900)
    except ValueError:
        return 8900


def _yerel_ai_betigi():
    """Isci betiginin yolu. Pakette assets/python altinda, kaynakta kokte."""
    kok = os.path.dirname(os.path.abspath(__file__))
    for yol in (os.path.join(kok, "assets", "python", "ai_sunucu.py"),
                os.path.join(kok, "ai_sunucu.py")):
        if os.path.isfile(yol):
            return yol
    return None


def _yerel_ai_dinliyor(port=8900):''', "main-yardimcilar")

m = degistir(m, '''def _yerel_ai_isci_baslat(http_sunucu):
    global _yerel_ai_isci, _yerel_ai_gunluk''', '''def _yerel_ai_isci_baslat(http_sunucu, ai_port=8900):
    global _yerel_ai_isci, _yerel_ai_gunluk''', "main-baslat-imza")

m = degistir(m, '''    if _yerel_ai_dinliyor():
        print("[AI] GRCOFF yerel AI işçisi zaten çalışıyor (127.0.0.1:8900).")
        return''', '''    if _yerel_ai_dinliyor(ai_port):
        print(f"[AI] GRCOFF yerel AI işçisi zaten çalışıyor (127.0.0.1:{ai_port}).")
        return''', "main-baslat-dinliyor")

m = degistir(m, '''        betik = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_sunucu.py")
        tip = "nvidia" if shutil.which("nvidia-smi") else "cpu"
        komut = [sys.executable, betik, "--port", "8900", "--ad", "GRCOFF Yerel AI",''', '''        betik = _yerel_ai_betigi()
        if not betik:
            print("[AI] GRCOFF yerel AI işçisi başlatılamadı: ai_sunucu.py bulunamadı.")
            return
        tip = "nvidia" if shutil.which("nvidia-smi") else "cpu"
        komut = [sys.executable, betik, "--port", str(int(ai_port)), "--dinle", "127.0.0.1", "--ad", AI_ISCI_ADI,''', "main-baslat-betik")

m = degistir(m, '''def _yerel_ai_isci_durdur():''', '''def _yerel_ai_jetonu():
    """Yerel isci anahtarini hazirlar ve ortama koyar (isci miras alir).

    Anahtar veri dizininde KALICIDIR (0600): Merkez beklenmedik kapanip
    yeniden acildiginda hala calisan eski isci ayni anahtarla yayini
    okumaya devam eder. Yalniz loopback'ten gelen isteklerde gecerlidir
    (sunucu.py::_yerel_ai_isci_mi).
    """
    import secrets
    from goktungu.sabitler import _veri_alt_yolu
    yol = _veri_alt_yolu("ai_isci_anahtari")
    jeton = ""
    try:
        with open(yol, "r", encoding="utf-8") as f:
            jeton = f.read().strip()
    except OSError:
        pass
    if len(jeton) < 32:
        jeton = secrets.token_urlsafe(32)
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        gecici = yol + ".yeni"
        with open(gecici, "w", encoding="utf-8") as f:
            f.write(jeton)
        try:
            os.chmod(gecici, 0o600)
        except OSError:
            pass
        os.replace(gecici, yol)
    os.environ["GOKTUNGU_AI_ISCI_JETON"] = jeton
    return jeton


def _yerel_ai_kaydet(ai_yonetici, ai_port):
    """Yerel isciyi AI yoneticisine tanitir (tekillik: host+port).

    Port degismisse (or. 8900 -> 8910) eski yerel kayit silinir; aksi
    halde arayuzde surekli "yanit vermiyor" gorunen hayalet bir sunucu kalir.
    """
    tip = "nvidia" if shutil.which("nvidia-smi") else "cpu"
    for k in ai_yonetici.listele():
        if (k.get("ad") == AI_ISCI_ADI
                and str(k.get("host")) in ("127.0.0.1", "localhost")
                and int(k.get("port") or 0) != int(ai_port)):
            ai_yonetici.sil(k["id"])
    ai_yonetici.kaydet(None, AI_ISCI_ADI, tip, "127.0.0.1", int(ai_port), 4,
                       notlar="GRCOFF Merkez ile birlikte otomatik başlar")


def _yerel_ai_gorevleri_esitle(ai_yonetici, son_deneme):
    """AI gorevi secili ama iscide akisi olmayan kameralari izlemeye alir.

    Kamera, isci henuz ayaga kalkmadan kaydedildiyse veya isci yeniden
    basladiysa gorev kaybolur; kullanici kamerayi yeniden kaydetmek
    zorunda kalmamali. Ayni kamera 30 sn'de bir kereden sik denenmez.
    """
    if ai_yonetici.kameralar is None or ai_yonetici._en_az_yuklu() is None:
        return
    iscide = set()
    for s in list(ai_yonetici.saglik.values()):
        for ak in ((s.get("son_durum") or {}).get("akislar") or []):
            try:
                iscide.add(int(ak.get("kamera_id")))
            except (TypeError, ValueError):
                pass
    simdi = time.time()
    for kam in ai_yonetici.kameralar.listele():
        gorevler = (kam.get("ai_gorevler") or "").strip()
        kid = int(kam["id"])
        if not gorevler or kid in iscide:
            continue
        if simdi - son_deneme.get(kid, 0) < 30:
            continue
        son_deneme[kid] = simdi
        sonuc = ai_yonetici.izleme_baslat(kid, "/kamera/%s" % kid,
                                          "gcs_proxy", gorevler)
        if not sonuc.get("tamam"):
            print(f"[AI] Kamera #{kid} izlemesi başlatılamadı: "
                  f"{sonuc.get('hata', '')}", flush=True)


def _yerel_ai_bekci(ai_yonetici, http_sunucu):
    """v2.4.153: GRCOFF'ta Merkez ayni zamanda AI sunucusudur.

    Isciyi baslatir, AI yoneticisine kaydeder, dusen isciyi artan
    beklemeyle yeniden baslatir ve gorevli kameralari izlemeye alir.
    """
    ai_port = _yerel_ai_portu()
    try:
        _yerel_ai_jetonu()
    except Exception as e:
        print(f"[AI] Yerel AI işçi anahtarı hazırlanamadı: {e}", flush=True)
    try:
        _yerel_ai_kaydet(ai_yonetici, ai_port)
    except Exception as e:
        print(f"[AI] Yerel AI işçisi kaydedilemedi: {e}", flush=True)
    deneme, son_baslatma, son_deneme = 0, 0.0, {}
    while True:
        try:
            if _yerel_ai_dinliyor(ai_port):
                deneme = 0
                _yerel_ai_gorevleri_esitle(ai_yonetici, son_deneme)
            else:
                surec_var = (_yerel_ai_isci is not None
                             and _yerel_ai_isci.poll() is None)
                bekle = min(300, 15 * (2 ** deneme))
                if not surec_var and time.time() - son_baslatma >= bekle:
                    if deneme:
                        print("[AI] Yerel AI işçisi yanıt vermiyor; yeniden "
                              f"başlatılıyor (deneme {deneme + 1}).", flush=True)
                    _yerel_ai_isci_baslat(http_sunucu, ai_port)
                    son_baslatma = time.time()
                    deneme += 1
        except Exception as e:
            print(f"[AI] Yerel AI bekçisi: {e}", flush=True)
        time.sleep(10)


def _yerel_ai_isci_durdur():''', "main-bekci")

m = degistir(m, '''    # --- v2.4.0: AI islem katmani ---
    ai_yonetici.baslat()   # saglik yoklama + kalici gorevleri geri yukle''', '''    # --- v2.4.0: AI islem katmani ---
    ai_yonetici.baslat()   # saglik yoklama + kalici gorevleri geri yukle
    # v2.4.153: GRCOFF (offline Merkez) ayni zamanda AI sunucusudur. Yerel
    # isci baslatilir ve kaydedilir. GRCON (merkez kipi) AI'yi Goruntu
    # Koprusunde yapar; orada yerel isci ASLA calistirilmaz.
    if not _merkez_kipi:
        threading.Thread(target=_yerel_ai_bekci,
                         args=(ai_yonetici, http_sunucu),
                         name="yerel-ai-bekci", daemon=True).start()''', "main-cagri")
m = degistir(m, '''    # Köprüsüz GRCOFF AI: HTTP gerçek portu aldıktan sonra aynı makinede başlar.
    threading.Thread(target=_yerel_ai_isci_baslat, args=(http_sunucu,),
                     daemon=True, name="grcoff-yerel-ai").start()
''', '''    # v2.4.153: Yerel AI isci baslatma buradan KALDIRILDI; uygulama_kur()
    # icindeki `_yerel_ai_bekci` yapar. Iki yol birlikte kalinca ayni anda
    # iki isci sureci aciliyordu (olculdu: art arda iki pid).
''', "main-eski-cagri")

# Kurulumdan kalan hayalet AI kayitlari: yalniz DOKUNULMAMIS yer tutucular.
m = degistir(m, '''    tip = "nvidia" if shutil.which("nvidia-smi") else "cpu"
    for k in ai_yonetici.listele():''', '''    tip = "nvidia" if shutil.which("nvidia-smi") else "cpu"
    for k in ai_yonetici.listele():
        if (k.get("ad"), str(k.get("host")), int(k.get("port") or 0)) in _AI_TOHUM_YER_TUTUCULARI \\
                and str(k.get("notlar") or "").startswith(_AI_TOHUM_NOT_ONEKLERI):
            ai_yonetici.sil(k["id"])
            print(f"[AI] Kullanılmayan örnek AI kaydı kaldırıldı: {k.get('ad')}", flush=True)
            continue''', "main-tohum-temizlik")

m = degistir(m, '''AI_ISCI_ADI = "GRCOFF Yerel AI"
''', '''AI_ISCI_ADI = "GRCOFF Yerel AI"

# veritabani._varsayilan_ai_sunuculari() v2.4.0-2.4.152 arasi her yerel
# kurulumda bu iki ORNEK kaydi tohumluyordu. GRCOFF'ta ikisi de hayalettir
# (192.168.1.100 ornek adres; 127.0.0.1:8900 artik kullanilmayan port) ve
# arayuzde surekli "yanit vermiyor" gorunur. Kullanici adres/notu
# degistirdiyse kayit KORUNUR.
_AI_TOHUM_YER_TUTUCULARI = {
    ("ASUS Ascent GX10", "192.168.1.100", 8900),
    ("CPU AI Sunucusu (Yerel)", "127.0.0.1", 8900),
}
_AI_TOHUM_NOT_ONEKLERI = ("NVIDIA GB10 Grace Blackwell tabanli AI islem sunucusu.",
                          "Ana sunucu ile ayni makinede calisan CPU tabanli isci")
''', "main-tohum-sabit")
yaz("main.py", m)

# ------------------------------------------- veritabani: ornek tohumlari kaldir
v = oku("goktungu/veritabani.py")
v = degistir(v, '''    kayitlar = [
        ("ASUS Ascent GX10", "nvidia", "192.168.1.100", 8900, 8,
         "NVIDIA GB10 Grace Blackwell tabanli AI islem sunucusu. "
         "Host adresini agdaki gercek IP ile guncelleyin."),
        ("CPU AI Sunucusu (Yerel)", "cpu", "127.0.0.1", 8900, 4,
         "Ana sunucu ile ayni makinede calisan CPU tabanli isci "
         "(Windows/Linux). GCS acilisinda otomatik baslatilir."),
    ]''', '''    # v2.4.153: ORNEK KAYITLAR ARTIK TOHUMLANMAZ. GRCOFF yerel isciyi
    # main.py::_yerel_ai_kaydet gercek portuyla kendisi kaydeder; ornek
    # adresli (192.168.1.100) ve eski portlu (127.0.0.1:8900) kayitlar
    # arayuzde hayalet "yanit vermiyor" sunucular olarak kaliyordu.
    kayitlar = []''', "vt-tohum")
yaz("goktungu/veritabani.py", v)

# ------------------------------------------------ index.html: kapali siniflar
h = oku("index.html")
h = degistir(h, '''            <label class="kam-ai-satir"><span data-i18n="kamAiYuz">Kişi Tanıma</span><span class="tgl"><input type="checkbox" id="kamAiYuz" value="yuz"><span class="tgl-iz"></span></span></label>
            <label class="kam-ai-satir"><span data-i18n="kamAiPlaka">Araç Tanıma</span><span class="tgl"><input type="checkbox" id="kamAiPlaka" value="plaka"><span class="tgl-iz"></span></span></label>
''', '''            <!-- v2.4.153: Kisi/Arac Tanima GRCOFF yerel iscisinde KAPALIDIR
                 (ai_sunucu.py IZINLI_SINIFLAR); anahtar hicbir sey yapmadigi
                 icin gosterilmez. -->
''', "form-kapali-siniflar")
h = degistir(h, 'js/kameralar.js?v=v24152', 'js/kameralar.js?v=v24153', "kam-surum")
yaz("index.html", h)

# --------------------------------------------------------- surum + gecmis
p = oku("goktungu/paket_surum.py")
p = degistir(p, 'PAKET_SURUM = "2.5.22"', 'PAKET_SURUM = "2.5.23"', "paket")
p = degistir(p, 'UYGULAMA_SURUM = "2.4.152"', 'UYGULAMA_SURUM = "2.4.153"', "uygulama")
yaz("goktungu/paket_surum.py", p)

ini = oku("goktungu/__init__.py")
ini = degistir(ini, '_SON_BILINEN = "2.4.152"', '_SON_BILINEN = "2.4.153"', "son-bilinen")
yaz("goktungu/__init__.py", ini)

s = oku("js/surum.js")
s = degistir(s, 'const GCS_SURUM = "2.4.152";', 'const GCS_SURUM = "2.4.153";', "surum")
s = degistir(s, '''const GCS_SURUM_GECMISI = [
  {''', '''const GCS_SURUM_GECMISI = [
  {
    surum: "2.4.153",
    tarih: "2026-09-12",
    baslik: "GRCOFF Merkez aynı zamanda AI sunucusu: köprüsüz canlı görüntü AI (paket 2.5.23)",
    maddeler: [
      "GRCOFF (offline Merkez) yerel AI işçisini kendisi başlatır ve AI yöneticisine 'GRCOFF Yerel AI' olarak kaydeder; ayrı bir AI sunucusu veya köprü gerekmez. Görevi seçili kameraların canlı görüntüsüne AI doğrudan uygulanır. 'Uygun (çevrimiçi/boş) AI sunucusu yok' hatası giderildi.",
      "Yerel işçi Merkez ile birlikte açılır, düşerse artan beklemeyle yeniden başlatılır. Kamera işçi hazır olmadan kaydedildiyse veya işçi yeniden başladıysa, AI görevli kameralar kendiliğinden yeniden izlemeye alınır.",
      "Kurulumun kaydırılmış AI portu (8910) kullanılır. İşçi canlı görüntüyü Merkez'in kendi yayın yolundan, yalnız bu makineden geçerli yerel işçi anahtarıyla okur; yayın dışarıya açılmaz İşçi yalnız 127.0.0.1 üzerinde dinler; yerel ağdan erişilemez. İşçi kayıtlarını program dizini yerine veri dizinine yazar (Windows: C:\\\\ProgramData\\\\Goktungu\\\\Merkez, Linux: /var/lib/goktungu-merkez).",
      "Kamera formundan GRCOFF yerel işçisinde kapalı olan Kişi Tanıma ve Araç Tanıma anahtarları kaldırıldı; İnsan, Kara Aracı ve Hava Aracı tespiti etkin.",
      "Kurulumda örnek olarak eklenen ve hiç çalışmayan 'ASUS Ascent GX10' ile 'CPU AI Sunucusu (Yerel)' kayıtları artık eklenmez; değiştirilmemiş eski kayıtlar açılışta kaldırılır.",
      "GRCON (çevrimiçi Merkez) değişmedi: orada AI Görüntü Köprüsünde çalışır, yerel işçi başlatılmaz."
    ]
  },
  {''', "gecmis")
yaz("js/surum.js", s)

print("2.5.23 yamasi uygulandi")
