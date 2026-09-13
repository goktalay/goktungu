"""GRCOFF paket 2.5.22 / uygulama 2.4.152 kaynak yamasi.

1. Kamera formunda kaybolan AI GOREVLERI bolumu geri gelir.
2. Kamera formu acilir-kapanir bolumlere ayrilir (Genel / AI Gorevleri /
   AI Angajman Kalibrasyonu).
3. Paket surumu tek kaynaktan (goktungu/paket_surum.py) okunur; main.py
   icindeki sabit "2.5.19" kaldirilir.
4. Surum 2.4.152 + surum gecmisi.

Kullanim: python3.11 yama_2522.py <KAYNAK_KOKU>
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


# ---------------------------------------------------------------- index.html
h = oku("index.html")
h = degistir(h, '''    <div class="lok-kaydet-icerik">
      <label for="kamAd" data-i18n="lblKamAd">KAMERA ADI</label>''', '''    <div class="lok-kaydet-icerik">
      <!-- v2.4.152: Form acilir-kapanir bolumlere ayrildi (kullanici:
           "kamera ayarlari cok uzun bir form olarak aciliyor"). Kaydet /
           Iptal bolumlerin DISINDADIR; her zaman gorunur. -->
      <details class="kam-bolum" id="kamBolumGenel" open>
        <summary><span data-i18n="kamBolumGenel">GENEL</span><span class="kam-bolum-rozet" id="kamRozetGenel"></span></summary>
        <div class="kam-bolum-icerik">
      <label for="kamAd" data-i18n="lblKamAd">KAMERA ADI</label>''', "form-genel-bas")

h = degistir(h, '''      <input type="text" id="kamUrl" placeholder="rtsp://kamera-yerel-adres/akış" spellcheck="false" maxlength="500">

      <!-- v2.5.21: YEREL AI ANGAJMAN KALIBRASYONU -->''', '''      <input type="text" id="kamUrl" placeholder="rtsp://kamera-yerel-adres/akış" spellcheck="false" maxlength="500">
        </div>
      </details>

      <!-- v2.4.152: AI GOREVLERI geri geldi. OLCULEN KUSUR: bu blok bir
           onceki kesimde formdan dusmustu; kameralar.js kutulari
           (AI_GOREV_KUTULARI) arayip bulamiyor, `ai_gorevler` hep bos
           kaydediliyordu. Arka uc (_ai_izleme_esitle) yerel AI izlemesini
           YALNIZ gorevi secili kamerada baslattigi icin hicbir kamerada AI
           calismiyordu. -->
      <details class="kam-bolum" id="kamBolumAi">
        <summary><span data-i18n="lblKamAiGorevler">AI GÖREVLERİ</span><span class="kam-bolum-rozet" id="kamRozetAi"></span></summary>
        <div class="kam-bolum-icerik">
          <div class="kam-ai-grid">
            <label class="kam-ai-satir"><span data-i18n="kamAiYuz">Kişi Tanıma</span><span class="tgl"><input type="checkbox" id="kamAiYuz" value="yuz"><span class="tgl-iz"></span></span></label>
            <label class="kam-ai-satir"><span data-i18n="kamAiPlaka">Araç Tanıma</span><span class="tgl"><input type="checkbox" id="kamAiPlaka" value="plaka"><span class="tgl-iz"></span></span></label>
            <label class="kam-ai-satir"><span data-i18n="kamAiHava">Hava Aracı Tespit</span><span class="tgl"><input type="checkbox" id="kamAiHava" value="hava_araci"><span class="tgl-iz"></span></span></label>
            <label class="kam-ai-satir"><span data-i18n="kamAiInsan">İnsan Tespit</span><span class="tgl"><input type="checkbox" id="kamAiInsan" value="insan"><span class="tgl-iz"></span></span></label>
            <label class="kam-ai-satir"><span data-i18n="kamAiKara">Kara Aracı Tespit</span><span class="tgl"><input type="checkbox" id="kamAiKara" value="kara_araci"><span class="tgl-iz"></span></span></label>
          </div>
          <div class="form-not" data-i18n="kamAiNot">Görev seçilen kamerada yerel AI izlemesi kayıt anında otomatik başlar. Düşman dron tespiti için "Hava Aracı Tespit" seçilmelidir.</div>
        </div>
      </details>

      <!-- v2.5.21: YEREL AI ANGAJMAN KALIBRASYONU -->''', "form-ai")

h = degistir(h, '''      <div id="kamAngajmanBolum" style="margin-top:10px;border-top:1px solid rgba(255,255,255,.12);padding-top:8px;">''', '''      <details class="kam-bolum" id="kamBolumKalib">
        <summary><span data-i18n="kamBolumKalib">AI ANGAJMAN KALİBRASYONU</span><span class="kam-bolum-rozet" id="kamRozetKalib"></span></summary>
      <div id="kamAngajmanBolum" class="kam-bolum-icerik">''', "form-kalib-bas")

h = degistir(h, '''        <div class="form-not" id="kamKalibDurum"></div>
      </div>

      <div id="kamHata"></div>''', '''        <div class="form-not" id="kamKalibDurum"></div>
      </div>
      </details>

      <div id="kamHata"></div>''', "form-kalib-son")

h = degistir(h, 'css/stil.css?v=v24145', 'css/stil.css?v=v24152', "css-surum")
h = degistir(h, 'js/i18n.js?v=v24148', 'js/i18n.js?v=v24152', "i18n-surum")
h = degistir(h, 'js/kameralar.js?v=v2519', 'js/kameralar.js?v=v24152', "kam-surum")
yaz("index.html", h)

# ------------------------------------------------------------- css/stil.css
c = oku("css/stil.css")
if ".kam-bolum" in c:
    sys.exit("HATA: .kam-bolum stili zaten var")
c = c.rstrip("\n") + '''

/* v2.4.152: Kamera formu acilir-kapanir bolumler */
#kamModalKutu .lok-kaydet-icerik { max-height: calc(100vh - 140px); overflow-y: auto; }
.kam-bolum {
  border: 1px solid var(--cizgi);
  border-radius: 6px;
  margin-top: 8px;
}
.kam-bolum > summary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  cursor: pointer;
  user-select: none;
  list-style: none;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .1em;
  color: var(--soluk);
}
.kam-bolum > summary::-webkit-details-marker { display: none; }
.kam-bolum > summary::before {
  content: "\\25B8";
  display: inline-block;
  transition: transform .15s ease;
}
.kam-bolum[open] > summary::before { transform: rotate(90deg); }
.kam-bolum > summary:hover { color: var(--metin); }
.kam-bolum[open] > summary { border-bottom: 1px solid var(--cizgi); }
.kam-bolum-rozet {
  margin-left: auto;
  font-weight: 600;
  letter-spacing: .02em;
  text-transform: none;
}
.kam-bolum-rozet.iyi { color: #7fd6a0; }
.kam-bolum-rozet.uyari { color: #ffcf7a; }
.kam-bolum-icerik { padding: 4px 10px 10px; }
/* `#kamModalKutu label { display:block; margin:10px 0 5px }` (ID
   ozgullugu) gorev satirlarina da uyguluyordu; metin ve anahtar dikeyde
   kayiyordu. Bu yuzden kurallar ayni ID kapsaminda yazilir. */
#kamModalKutu .kam-bolum .kam-ai-grid { gap: 6px 16px; margin-top: 6px; }
#kamModalKutu .kam-bolum .kam-ai-satir .tgl input { margin: 0; width: 0; }
#kamModalKutu .kam-bolum .kam-ai-satir .tgl { flex: 0 0 34px; width: 34px; max-width: 34px; }
#kamModalKutu .kam-bolum .kam-ai-satir {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 0;
  padding: 4px 0;
  letter-spacing: normal;
  font-size: 12px;
  color: var(--metin);
}
.kam-bolum-icerik > label:first-child { margin-top: 4px; }
'''
yaz("css/stil.css", c)

# ---------------------------------------------------------- js/kameralar.js
k = oku("js/kameralar.js")
k = degistir(k, '''    // v2.5.21: angajman kalibrasyon alanlari
    kalibDoldur(kamera);
    hataEl.textContent = "";''', '''    // v2.5.21: angajman kalibrasyon alanlari
    kalibDoldur(kamera);
    // v2.4.152: acilir bolumler. Genel hep acik; AI Gorevleri gorev
    // seciliyse, kalibrasyon ise kamera zaten bir tipe/kalibrasyona
    // sahipse acik gelir. Yeni kamerada yalniz Genel acik.
    bolumAc("kamBolumGenel", true);
    bolumAc("kamBolumAi", !!aiGorevleriOku());
    bolumAc("kamBolumKalib", !!(kamera && (kamera.kalibre ||
      kamera.lat !== null && kamera.lat !== undefined && kamera.lat !== "")));
    bolumRozetleri(kamera);
    hataEl.textContent = "";''', "js-modal-ac")

k = degistir(k, '''  function modalKapat() {''', '''  // v2.4.152: acilir-kapanir kamera formu bolumleri
  function bolumAc(id, acik) {
    const b = _el(id);
    if (b) b.open = !!acik;
  }

  function bolumRozetleri(kamera) {
    const t = T();
    const ai = _el("kamRozetAi");
    if (ai) {
      const n = aiGorevleriOku().split(",").filter(Boolean).length;
      ai.textContent = n
        ? String(n) + " " + (t.kamRozetSecili || "seçili")
        : (t.kamRozetGorevYok || "görev yok");
      ai.className = "kam-bolum-rozet " + (n ? "iyi" : "");
    }
    const kl = _el("kamRozetKalib");
    if (kl) {
      const kalibre = !!(kamera && kamera.kalibre);
      kl.textContent = kalibre
        ? (t.kamRozetKalibre || "kalibre")
        : (t.kamRozetEksik || "eksik");
      kl.className = "kam-bolum-rozet " + (kalibre ? "iyi" : "uyari");
    }
    const gn = _el("kamRozetGenel");
    if (gn) gn.textContent = inAd.value.trim();
  }

  function modalKapat() {''', "js-bolum-fonk")

# Dogrulama hatasi Genel bolumundeki alanlardadir; bolum kapaliysa ac.
for eski in ('''    if (!isim) { hataEl.textContent = t.kamHataAd''',):
    # Basarili kayitta modal zaten kapanir; acmak yalniz hatada gorunur.
    k = degistir(k, eski, '''    bolumAc("kamBolumGenel", true);
''' + eski, "js-hata-ac")

k = degistir(k, '''  // v2.5.21: kamera tipi degisince sabit/dron kalibrasyon panelini degistir
  {''', '''  // v2.4.152: gorev kutusu / ad degisince bolum rozetlerini tazele
  for (const id of AI_GOREV_KUTULARI) {
    const kutu = document.getElementById(id);
    if (kutu) kutu.addEventListener("change", () => bolumRozetleri(null));
  }
  inAd.addEventListener("input", () => {
    const gn = _el("kamRozetGenel");
    if (gn) gn.textContent = inAd.value.trim();
  });

  // v2.5.21: kamera tipi degisince sabit/dron kalibrasyon panelini degistir
  {''', "js-dinleyici")
yaz("js/kameralar.js", k)

# ------------------------------------------------------------- js/i18n.js
i = oku("js/i18n.js")
i = degistir(i, '''    kamAiKara: "Kara Arac\\u0131 Tespit",''', '''    kamAiKara: "Kara Arac\\u0131 Tespit",
    kamBolumGenel: "GENEL",
    kamBolumKalib: "AI ANGAJMAN KAL\\u0130BRASYONU",
    kamAiNot: "G\\u00f6rev se\\u00e7ilen kamerada yerel AI izlemesi kay\\u0131t an\\u0131nda otomatik ba\\u015flar. D\\u00fc\\u015fman dron tespiti i\\u00e7in \\"Hava Arac\\u0131 Tespit\\" se\\u00e7ilmelidir.",
    kamRozetSecili: "se\\u00e7ili",
    kamRozetGorevYok: "g\\u00f6rev yok",
    kamRozetKalibre: "kalibre",
    kamRozetEksik: "eksik",''', "i18n-tr")
i = degistir(i, '''    kamAiKara: "Ground Vehicle Detection",''', '''    kamAiKara: "Ground Vehicle Detection",
    kamBolumGenel: "GENERAL",
    kamBolumKalib: "AI ENGAGEMENT CALIBRATION",
    kamAiNot: "Local AI monitoring starts automatically when the camera is saved with a task selected. Select \\"Aerial Vehicle Detection\\" to detect hostile drones.",
    kamRozetSecili: "selected",
    kamRozetGorevYok: "no tasks",
    kamRozetKalibre: "calibrated",
    kamRozetEksik: "incomplete",''', "i18n-en")
yaz("js/i18n.js", i)

# ------------------------------------------------- paket surumu tek kaynak
if os.path.exists(os.path.join(KOK, "goktungu/paket_surum.py")):
    sys.exit("HATA: goktungu/paket_surum.py zaten var")
yaz("goktungu/paket_surum.py", '''"""GRCOFF kurulum paketi (katalog) surumu - TEK KAYNAK.

Uygulama surumu (GCS_SURUM, js/surum.js) ile AYNI DEGILDIR: katalogdaki
paket 2.5.x, uygulama 2.4.x ilerler. Bu deger:
  * main.py'de GuncellemeYoneticisi'ne "mevcut surum" olarak verilir,
  * deb_merkez_uret.py ve setup_merkez_uret.py tarafindan paket adi/NSIS
    SURUM olarak okunur.

OLCULEN KUSUR (2.5.19-2.5.21): main.py surumu "2.5.19" diye SABIT
yaziyordu; 2.5.20 ve 2.5.21 kurulumlari kendini 2.5.19 sanip "YENI SURUM
HAZIR" uyarisini kalici gosteriyordu. Build betikleri de kendi sabitlerini
tasiyordu. Uc kopya tek kaynaga indirildi.
"""
PAKET_SURUM = "2.5.22"

# Bu paketin tasidigi uygulama surumu (js/surum.js GCS_SURUM ile ESLESMELI).
# Build betikleri eslesmezse durur (bayat agac / yanlis eslesme kapisi).
UYGULAMA_SURUM = "2.4.152"
''')

m = oku("main.py")
m = degistir(m, '''    from goktungu.sabitler import VERI_KOKU
    ws_sunucu.guncelleme = GuncellemeYoneticisi(
        "gcs", "2.5.19", VERI_KOKU, gunluk=konsol)''', '''    from goktungu.sabitler import VERI_KOKU
    # v2.4.152: paket surumu tek kaynaktan (bkz. goktungu/paket_surum.py).
    from goktungu.paket_surum import PAKET_SURUM
    ws_sunucu.guncelleme = GuncellemeYoneticisi(
        "gcs", PAKET_SURUM, VERI_KOKU, gunluk=konsol)''', "main-surum")
yaz("main.py", m)

OKUYUCU = '''def _paket_surum_oku(ad: str) -> str:
    """Surum alanini goktungu/paket_surum.py'den okur (TEK KAYNAK).

    Paket ice ALINMAZ (goktungu/__init__ calisma zamani yan etkileri);
    satir duzenli ifadeyle okunur.
    """
    yol = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "goktungu", "paket_surum.py")
    with open(yol, encoding="utf-8") as f:
        m = re.search(r'^' + ad + r'\\s*=\\s*"([0-9]+\\.[0-9]+\\.[0-9]+)"',
                      f.read(), re.M)
    if not m:
        raise SystemExit("HATA: goktungu/paket_surum.py icinde %s yok" % ad)
    return m.group(1)


PAKET_SURUM = _paket_surum_oku("PAKET_SURUM")'''

for betik in ("deb_merkez_uret.py", "setup_merkez_uret.py"):
    b = oku(betik)
    b = degistir(b, 'PAKET_SURUM = "2.5.21"', OKUYUCU, betik + "-surum")
    b = degistir(b, 'UYGULAMA_SURUM = "2.4.151"',
                 'UYGULAMA_SURUM = _paket_surum_oku("UYGULAMA_SURUM")',
                 betik + "-uygulama-surum")
    for gerek in ("import os", "import re"):
        if not re.search(r"^" + gerek + r"\b", b, re.M):
            b = degistir(b, "import subprocess\n", "import subprocess\n" + gerek + "\n",
                         betik + "-" + gerek)
    yaz(betik, b)

# --------------------------------------------------------- surum + gecmis
s = oku("js/surum.js")
s = degistir(s, 'const GCS_SURUM = "2.4.151";', 'const GCS_SURUM = "2.4.152";', "surum")
s = degistir(s, '''const GCS_SURUM_GECMISI = [
  {''', '''const GCS_SURUM_GECMISI = [
  {
    surum: "2.4.152",
    tarih: "2026-09-12",
    baslik: "Kamera formunda AI görevleri geri geldi, form bölümlere ayrıldı (paket 2.5.22)",
    maddeler: [
      "Kamera ekle/düzenle formunda kaybolan 'AI Görevleri' bölümü geri geldi: Kişi Tanıma, Araç Tanıma, Hava Aracı Tespit, İnsan Tespit, Kara Aracı Tespit. Bölüm eksik olduğu için görevler hep boş kaydediliyor ve yerel AI izlemesi hiçbir kamerada başlamıyordu; görev seçilen kamerada izleme kayıt anında otomatik başlar.",
      "Kamera formu açılır-kapanır bölümlere ayrıldı: Genel, AI Görevleri ve AI Angajman Kalibrasyonu. Bölüm başlıkları seçili görev sayısını ve kalibrasyon durumunu gösterir; Kaydet/İptal düğmeleri her zaman görünür kalır.",
      "Otomatik güncelleme artık kurulu paketin gerçek sürümünü bildirir. 2.5.20 ve 2.5.21 kendini 2.5.19 olarak tanıttığı için 'Yeni sürüm hazır' uyarısı güncelleme yapıldıktan sonra da kaybolmuyordu."
    ]
  },
  {''', "gecmis")
yaz("js/surum.js", s)

ini = oku("goktungu/__init__.py")
ini = degistir(ini, '_SON_BILINEN = "2.4.151"', '_SON_BILINEN = "2.4.152"', "son-bilinen")
yaz("goktungu/__init__.py", ini)

print("2.5.22 yamasi uygulandi")
