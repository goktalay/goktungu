// ============================================================
// GOKTUNGU GCS — HAVA DURUMU WIDGET
// v2.4.29
//
// Haritanin BULUNDUGU ALANIN havasini gosterir. Konum, Cesium
// kamerasinin baktigi noktadan (yer merkezi) alinir; kamera konumu
// degistiginde belirgin bir kayma varsa veri yenilenir.
//
// VERI KAYNAGI: Open-Meteo (api.open-meteo.com) — API anahtari
// gerektirmez. Ruzgar hizi KNOT olarak istenir (`wind_speed_unit=kn`),
// km/h degeri `x 1.852` ile hesaplanir. Boylece iki birim ayni
// olcumden turer ve birbirleriyle tutarli olur.
//
// CEVRIMDISI SAHA KURULUMU: istek basarisiz olursa widget "veri yok"
// durumunu gosterir ve elle yenileme dugmesi sunar. Arayuzun geri
// kalani etkilenmez.
//
// ANIMASYON: tum hareket CSS ile yapilir (bkz. css/widget.css). JS
// yalnizca ruzgar yonunu (ibre donusu) ve fan hizini (animasyon suresi)
// ayarlar. Boylece kare basi JS maliyeti sifirdir.
// ============================================================

(function(){
  "use strict";

  const ID = "havadurumu";
  const KN_KMH = 1.852;              // 1 knot = 1.852 km/h
  const TAZELEME_MS = 10 * 60 * 1000; // 10 dakika
  const KONUM_ESIK_KM = 25;           // bu kadar kayma olursa yeniden sorgula

  let ogeler = null;
  let zamanlayici = null;
  let sonKonum = null;    // { lat, lon }
  let sonVeri = null;
  let istekSurmekte = false;
  let bayat = false;                 // harita kaydi, veri baska bolgeye ait
  let kameraIzleyiciKurulu = false;
  // v2.4.33: baslikta duran tekil yenileme dugmesine erisim.
  // `govdeKur(govde, api)` ile gelir; bayatIsaretle() bunu kullanir.
  let wApi = null;

  const SVG_NS = "http://www.w3.org/2000/svg";
  function sv(ad, oz, icerik){
    const e = document.createElementNS(SVG_NS, ad);
    for (const k in oz) e.setAttribute(k, oz[k]);
    if (icerik !== undefined) e.textContent = icerik;
    return e;
  }

  function ingilizceMi(){
    try {
      if (typeof aktifDil !== "undefined") return String(aktifDil).toLowerCase().startsWith("en");
      const d = localStorage.getItem("gcs_dil");
      return !!(d && d.toLowerCase().startsWith("en"));
    } catch (e) { return false; }
  }

  // ----------------------------------------------------------
  // WMO HAVA KODU ESLEMESI
  // Kaynak: WMO 4677 / Open-Meteo dokumantasyonu
  // ----------------------------------------------------------
  const KOD = {
    0:  { tr:"Açık",                  en:"Clear",              tur:"gunes" },
    1:  { tr:"Genelde açık",          en:"Mainly clear",       tur:"gunes-bulut" },
    2:  { tr:"Parçalı bulutlu",       en:"Partly cloudy",      tur:"gunes-bulut" },
    3:  { tr:"Kapalı",                en:"Overcast",           tur:"bulut" },
    45: { tr:"Sisli",                 en:"Fog",                tur:"sis" },
    48: { tr:"Kırağılı sis",          en:"Rime fog",           tur:"sis" },
    51: { tr:"Hafif çisenti",         en:"Light drizzle",      tur:"yagmur" },
    53: { tr:"Çisenti",               en:"Drizzle",            tur:"yagmur" },
    55: { tr:"Yoğun çisenti",         en:"Dense drizzle",      tur:"yagmur" },
    56: { tr:"Donan çisenti",         en:"Freezing drizzle",   tur:"yagmur" },
    57: { tr:"Yoğun donan çisenti",   en:"Dense freez. drizzle", tur:"yagmur" },
    61: { tr:"Hafif yağmur",          en:"Light rain",         tur:"yagmur" },
    63: { tr:"Yağmur",                en:"Rain",               tur:"yagmur" },
    65: { tr:"Şiddetli yağmur",       en:"Heavy rain",         tur:"yagmur" },
    66: { tr:"Donan yağmur",          en:"Freezing rain",      tur:"yagmur" },
    67: { tr:"Şiddetli donan yağmur", en:"Heavy freezing rain", tur:"yagmur" },
    71: { tr:"Hafif kar",             en:"Light snow",         tur:"kar" },
    73: { tr:"Kar",                   en:"Snow",               tur:"kar" },
    75: { tr:"Yoğun kar",             en:"Heavy snow",         tur:"kar" },
    77: { tr:"Kar taneleri",          en:"Snow grains",        tur:"kar" },
    80: { tr:"Hafif sağanak",         en:"Light showers",      tur:"yagmur" },
    81: { tr:"Sağanak",               en:"Showers",            tur:"yagmur" },
    82: { tr:"Şiddetli sağanak",      en:"Violent showers",    tur:"yagmur" },
    85: { tr:"Hafif kar sağanağı",    en:"Light snow showers", tur:"kar" },
    86: { tr:"Kar sağanağı",          en:"Snow showers",       tur:"kar" },
    95: { tr:"Gök gürültülü fırtına", en:"Thunderstorm",       tur:"firtina" },
    96: { tr:"Dolulu fırtına",        en:"Thunderstorm, hail", tur:"firtina" },
    99: { tr:"Şiddetli dolulu fırtına", en:"Severe hail storm", tur:"firtina" },
  };
  function kodBilgi(k){
    const b = KOD[k];
    if (b) return b;
    return { tr:"Bilinmiyor", en:"Unknown", tur:"bulut" };
  }

  // ----------------------------------------------------------
  // BEAUFORT OLCEGI (knot esiklerine gore)
  // ----------------------------------------------------------
  const BEAUFORT = [
    [1,   0, "Sakin",          "Calm"],
    [4,   1, "Hafif esinti",   "Light air"],
    [7,   2, "Hafif rüzgar",   "Light breeze"],
    [11,  3, "Tatlı rüzgar",   "Gentle breeze"],
    [17,  4, "Orta rüzgar",    "Moderate breeze"],
    [22,  5, "Sert rüzgar",    "Fresh breeze"],
    [28,  6, "Kuvvetli rüzgar","Strong breeze"],
    [34,  7, "Fırtınamsı",     "Near gale"],
    [41,  8, "Fırtına",        "Gale"],
    [48,  9, "Kuvvetli fırtına","Strong gale"],
    [56, 10, "Tam fırtına",    "Storm"],
    [64, 11, "Çok şiddetli fırtına","Violent storm"],
    [999,12, "Kasırga",        "Hurricane"],
  ];
  function beaufort(kn){
    for (const [esik, kuvvet, tr, en] of BEAUFORT){
      if (kn < esik) return { kuvvet, tr, en };
    }
    return { kuvvet: 12, tr: "Kasırga", en: "Hurricane" };
  }

  // 16 yon kisaltmasi
  const YON16_TR = ["K","KKD","KD","DKD","D","DGD","GD","GGD",
                    "G","GGB","GB","BGB","B","BKB","KB","KKB"];
  const YON16_EN = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
                    "S","SSW","SW","WSW","W","WNW","NW","NNW"];
  function yonAdi(der){
    const i = Math.round((((der % 360) + 360) % 360) / 22.5) % 16;
    return ingilizceMi() ? YON16_EN[i] : YON16_TR[i];
  }

  // ----------------------------------------------------------
  // HAVA IKONU (animasyonlu SVG)
  // Her tur icin ayri SVG uretilir; animasyon CSS siniflari ile.
  //
  // RENK POLITIKASI (v2.4.31b) — bilincli istisna
  // Bu ikonlardaki renkler TEMADAN ALINMAZ ve sabit tutulur: gunes
  // sari, yagmur mavisi, bulut grisi, simsek sari. Bunlar arayuz
  // rengi degil, NESNENIN KENDI rengidir; temaya baglanirsa gunes ile
  // yagmur ayni renge duser ve ikon anlamini yitirir. Secilen tonlar
  // hem koyu hem acik zeminde okunacak sekilde orta parlaklikta
  // tutulmustur. Widget'in KABUK renkleri (govde, metin, kenar,
  // kadran) ise tamamen temadan gelir.
  // ----------------------------------------------------------
  function havaIkonu(tur, gunduzMu){
    const svg = sv("svg", { viewBox:"0 0 48 48", width:"42", height:"42" });

    function gunesEkle(cx, cy, r){
      // Isinlar (donen grup)
      const g = sv("g", { class:"hv-gunes-isin" });
      for (let i = 0; i < 8; i++){
        const a = (i / 8) * Math.PI * 2;
        g.appendChild(sv("line", {
          x1:(cx + Math.cos(a) * (r + 3.2)).toFixed(2),
          y1:(cy + Math.sin(a) * (r + 3.2)).toFixed(2),
          x2:(cx + Math.cos(a) * (r + 7.0)).toFixed(2),
          y2:(cy + Math.sin(a) * (r + 7.0)).toFixed(2),
          stroke:"#f59e0b", "stroke-width":2.1, "stroke-linecap":"round",
        }));
      }
      svg.appendChild(g);
      svg.appendChild(sv("circle", { cx, cy, r, fill:"#fbbf24",
        stroke:"#f59e0b", "stroke-width":1.2 }));
    }

    function ayEkle(cx, cy, r){
      // Hilal: iki dairenin farki (maske yerine path)
      svg.appendChild(sv("path", {
        d:"M " + (cx + r * 0.55) + " " + (cy - r) +
          " a " + r + " " + r + " 0 1 0 0 " + (2 * r) +
          " a " + (r * 0.82) + " " + (r * 0.82) + " 0 1 1 0 " + (-2 * r) + " z",
        fill:"#cbd5e1", stroke:"#94a3b8", "stroke-width":1,
      }));
    }

    function bulutEkle(x, y, olcek, renk, kenar){
      const g = sv("g", { class:"hv-bulut" });
      g.appendChild(sv("path", {
        d:"M 8 20 a 6.2 6.2 0 0 1 6.1 -6.1 a 8.4 8.4 0 0 1 15.9 -1.6 " +
          "a 6.6 6.6 0 0 1 5.4 7.7 a 5.6 5.6 0 0 1 -1.6 11 H 10.6 " +
          "a 5.8 5.8 0 0 1 -2.6 -11 z",
        fill: renk || "#e2e8f0", stroke: kenar || "#a8b3c2", "stroke-width":1.15,
        transform:"translate(" + x + " " + y + ") scale(" + olcek + ")",
      }));
      svg.appendChild(g);
    }

    if (tur === "gunes"){
      if (gunduzMu) gunesEkle(24, 24, 9.5); else ayEkle(24, 24, 10);
    } else if (tur === "gunes-bulut"){
      if (gunduzMu) gunesEkle(17, 16, 7.4); else ayEkle(17, 16, 7.8);
      bulutEkle(8, 12, 0.78, "#eef2f7", "#aab5c4");
    } else if (tur === "bulut"){
      bulutEkle(6, 12, 0.86, "#cfd8e3", "#93a0b1");
      bulutEkle(2, 4, 0.62, "#e7edf4", "#aab5c4");
    } else if (tur === "yagmur"){
      bulutEkle(5, 4, 0.82, "#cfd8e3", "#93a0b1");
      for (let i = 0; i < 3; i++){
        svg.appendChild(sv("line", {
          class:"hv-damla",
          x1: 15 + i * 8, y1: 33, x2: 13.6 + i * 8, y2: 39,
          stroke:"#3b82f6", "stroke-width":2.1, "stroke-linecap":"round",
        }));
      }
    } else if (tur === "kar"){
      bulutEkle(5, 4, 0.82, "#dde5ee", "#9aa6b6");
      for (let i = 0; i < 3; i++){
        const g = sv("g", { class:"hv-damla" });
        const cx = 15.5 + i * 8, cy = 36;
        [0, 60, 120].forEach(a => {
          const r = (a / 180) * Math.PI;
          g.appendChild(sv("line", {
            x1:(cx - Math.cos(r) * 2.5).toFixed(2), y1:(cy - Math.sin(r) * 2.5).toFixed(2),
            x2:(cx + Math.cos(r) * 2.5).toFixed(2), y2:(cy + Math.sin(r) * 2.5).toFixed(2),
            stroke:"#60a5fa", "stroke-width":1.5, "stroke-linecap":"round",
          }));
        });
        svg.appendChild(g);
      }
    } else if (tur === "firtina"){
      bulutEkle(5, 3, 0.82, "#9aa6b8", "#6b7789");
      svg.appendChild(sv("path", {
        class:"hv-simsek",
        d:"M 25 27 L 19.5 38 L 23.5 38 L 21 46 L 29.5 34.5 L 25 34.5 L 27.5 27 z",
        fill:"#fbbf24", stroke:"#f59e0b", "stroke-width":0.9,
      }));
    } else if (tur === "sis"){
      bulutEkle(5, 1, 0.74, "#dbe2ea", "#a4aebd");
      for (let i = 0; i < 3; i++){
        svg.appendChild(sv("line", {
          class:"hv-sis",
          x1: 9, y1: 32 + i * 5, x2: 39, y2: 32 + i * 5,
          stroke:"#94a3b8", "stroke-width":2.2, "stroke-linecap":"round",
        }));
      }
    }
    return svg;
  }

  // ----------------------------------------------------------
  // RUZGAR GULU (animasyonlu SVG)
  // - Sabit kadran: K/D/G/B harfleri ve derece cizgileri
  // - Donen ibre: ruzgarin ESTIGI yone bakar (meteorolojik yon +180)
  // - Fan: hiza gore donme suresi ayarlanir
  // - Akis cizgileri: ruzgar dogrultusunda kayan izler
  // ----------------------------------------------------------
  function ruzgarGulu(){
    const svg = sv("svg", { class:"ruzgar-gulu", viewBox:"0 0 76 76",
                            width:"70", height:"70" });
    // Kadran
    // v2.4.31: renkler CSS sinifi uzerinden temadan gelir; SVG'de sabit
    // renk YAZILMAZ (koyu temada kadran ve harfler okunamiyordu).
    svg.appendChild(sv("circle", { class:"rg-zemin", cx:38, cy:38, r:31,
      "stroke-width":1.4 }));
    svg.appendChild(sv("circle", { class:"rg-ic-halka", cx:38, cy:38, r:24,
      fill:"none", "stroke-width":1, "stroke-dasharray":"2 3" }));

    // Derece cizgileri (her 30 derece)
    for (let i = 0; i < 12; i++){
      const a = (i / 12) * Math.PI * 2 - Math.PI / 2;
      const buyuk = (i % 3 === 0);
      svg.appendChild(sv("line", {
        class: buyuk ? "rg-cizgi-buyuk" : "rg-cizgi-kucuk",
        x1:(38 + Math.cos(a) * (buyuk ? 25 : 27.5)).toFixed(2),
        y1:(38 + Math.sin(a) * (buyuk ? 25 : 27.5)).toFixed(2),
        x2:(38 + Math.cos(a) * 30).toFixed(2),
        y2:(38 + Math.sin(a) * 30).toFixed(2),
        "stroke-width": buyuk ? 1.7 : 1, "stroke-linecap":"round",
      }));
    }

    // Yon harfleri
    // Kuzey harfi bilerek kirmizi kalir (yon referansi); temaya gore
    // ton degistirmesi icin `--w-kirmizi` kullanilir.
    const harfKuzey = sv("text", { x:38, y:14.5, "text-anchor":"middle",
      "font-size":"8", "font-weight":"800", fill:"var(--w-kirmizi)",
      "font-family":"inherit" }, "K");
    const harfDogu  = sv("text", { class:"rg-harf", x:62.5, y:41, "text-anchor":"middle",
      "font-size":"7", "font-weight":"700", "font-family":"inherit" }, "D");
    const harfGuney = sv("text", { class:"rg-harf", x:38, y:66.5, "text-anchor":"middle",
      "font-size":"7", "font-weight":"700", "font-family":"inherit" }, "G");
    const harfBati  = sv("text", { class:"rg-harf", x:13.5, y:41, "text-anchor":"middle",
      "font-size":"7", "font-weight":"700", "font-family":"inherit" }, "B");
    [harfKuzey, harfDogu, harfGuney, harfBati].forEach(h => svg.appendChild(h));

    // Akis cizgileri (donen grupla birlikte yonlenir)
    const ibre = sv("g", { class:"ruzgar-ibre" });
    for (let i = -1; i <= 1; i++){
      ibre.appendChild(sv("line", {
        class:"ruzgar-akis-cizgi rg-akis",
        x1:(38 + i * 5.5), y1:52, x2:(38 + i * 5.5), y2:26,
        "stroke-width":1.5, "stroke-linecap":"round",
        opacity:"0",
      }));
    }
    // Ok (ruzgarin gittigi yon)
    ibre.appendChild(sv("path", {
      class:"rg-ibre-govde",
      d:"M 38 12.5 L 43.4 25.5 L 38 22.6 L 32.6 25.5 z",
      "stroke-width":0.9,
    }));
    ibre.appendChild(sv("line", {
      class:"rg-ibre-govde",
      x1:38, y1:22.6, x2:38, y2:53,
      "stroke-width":2.1, "stroke-linecap":"round",
    }));
    svg.appendChild(ibre);

    // Fan (hiz gostergesi) — merkezde kucuk pervane
    const fan = sv("g", { class:"ruzgar-fan" });
    for (let i = 0; i < 3; i++){
      const a = (i / 3) * 360;
      fan.appendChild(sv("path", {
        d:"M 38 38 q 5.5 -3 8.5 -0.6 q -3 3.4 -8.5 0.6 z",
        fill:"var(--w-soluk)", opacity:"0.85",
        transform:"rotate(" + a + " 38 38)",
      }));
    }
    svg.appendChild(fan);
    svg.appendChild(sv("circle", { cx:38, cy:38, r:2.4, fill:"var(--w-ibre)" }));

    return { svg, ibre, fan, harfKuzey, harfDogu, harfGuney, harfBati };
  }

  // ----------------------------------------------------------
  // GOVDE
  // ----------------------------------------------------------
  function govdeKur(govde, api){
    wApi = api;
    const sarmal = document.createElement("div");
    sarmal.className = "hava-sarmal";

    // Ust satir: ikon + sicaklik + durum
    const ust = document.createElement("div");
    ust.className = "hava-ust";
    const ikonKutu = document.createElement("div");
    ikonKutu.className = "hava-ikon-kutu";
    // v2.4.33: satir ici stil CSS sinifina tasindi
    // (`.hava-ust-metin`). Boylece hizalama CSS'ten yonetilir ve
    // "Sicaklik ortada dursun" istegi tek noktadan uygulanir.
    const ustSag = document.createElement("div");
    ustSag.className = "hava-ust-metin";
    const sic = document.createElement("div");
    sic.className = "hava-sicaklik";
    sic.textContent = "--°";
    const durumMetin = document.createElement("div");
    durumMetin.className = "hava-durum-metin";
    durumMetin.textContent = "";
    const hisMetin = document.createElement("div");
    hisMetin.className = "hava-hissedilen";
    hisMetin.textContent = "";
    ustSag.appendChild(sic);
    ustSag.appendChild(durumMetin);
    ustSag.appendChild(hisMetin);
    ust.appendChild(ikonKutu);
    ust.appendChild(ustSag);

    // Orta satir: ruzgar gulu + hiz
    const orta = document.createElement("div");
    orta.className = "hava-orta";
    const gulu = ruzgarGulu();
    const rBilgi = document.createElement("div");
    rBilgi.className = "ruzgar-bilgi";
    const rKnot = document.createElement("div");
    rKnot.className = "ruzgar-knot";
    rKnot.innerHTML = '--<span>kn</span>';
    const rKmh = document.createElement("div");
    rKmh.className = "ruzgar-kmh";
    rKmh.innerHTML = '--<span>km/h</span>';
    const rYon = document.createElement("div");
    rYon.className = "ruzgar-yon-metin";
    rYon.textContent = "";
    const rBeaufort = document.createElement("div");
    rBeaufort.className = "ruzgar-yon-metin";
    rBeaufort.textContent = "";
    rBilgi.appendChild(rKnot);
    rBilgi.appendChild(rKmh);
    rBilgi.appendChild(rYon);
    rBilgi.appendChild(rBeaufort);
    orta.appendChild(gulu.svg);
    orta.appendChild(rBilgi);

    // Alt satir: hamle, nem, yagis
    const alt = document.createElement("div");
    alt.className = "hava-alt";
    function kutucuk(ikon){
      const d = document.createElement("div");
      d.className = "hava-kutucuk";
      d.innerHTML = '<i class="' + ikon + '"></i><b>--</b><small></small>';
      alt.appendChild(d);
      return { b: d.querySelector("b"), s: d.querySelector("small") };
    }
    const kHamle = kutucuk("fa-solid fa-wind");
    const kNem = kutucuk("fa-solid fa-droplet");
    const kYagis = kutucuk("fa-solid fa-cloud-rain");

    const konum = document.createElement("div");
    konum.className = "hava-konum";
    konum.textContent = "";

    // v2.4.33: BAYAT VERI UYARISI artik BASLIKTAKI TEKIL DUGMEDE.
    //
    // Harita her kaydirmada hava servisine istek atmak agir olurdu
    // (Open-Meteo kotasi ve gereksiz ag yuku). Bunun yerine konum
    // esigi asildiginda baslikta kirmizi yenileme dugmesi belirir;
    // operator basmadikca istek gitmez. Widget'in mevcut verisi
    // ekranda kalir ama artik baska bir bolgeye ait oldugu gorunur
    // bicimde isaretlenir.
    //
    // v2.4.32'de bu dugme govdenin sag-alt kosesinde yuzen ayri bir
    // daireydi (`hava-bayat-btn`) ve alttaki konum yazisinin uzerine
    // biniyordu. Kullanici istegi uzerine tum widget'larda yenileme
    // basliga tasindi; DOM ogesi burada KALDIRILDI.
    if (wApi && typeof wApi.yenilemeKur === "function"){
      wApi.yenilemeKur(function(){
        bayatIsaretle(false);
        veriAl(true);
      });
    }

    // Yukleniyor / hata perdesi
    const perde = document.createElement("div");
    perde.className = "hava-yukleniyor";
    perde.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i><span>Hava verisi alınıyor…</span>';

    sarmal.appendChild(ust);
    sarmal.appendChild(orta);
    sarmal.appendChild(alt);
    sarmal.appendChild(konum);

    govde.appendChild(perde);
    govde.appendChild(sarmal);
    sarmal.style.display = "none";

    ogeler = {
      sarmal, perde, ikonKutu, sic, durumMetin, hisMetin,
      gulu, rKnot, rKmh, rYon, rBeaufort,
      kHamle, kNem, kYagis, konum,
    };

    // Elle yenileme: govdeye cift tiklama (baslik dugmesi yalnizca
    // veri bayatken gorunur; bu kisayol her zaman calisir)
    govde.addEventListener("dblclick", (ev) => { ev.stopPropagation(); veriAl(true); });
  }

  // ----------------------------------------------------------
  // GORUNUM TAZELEME
  // ----------------------------------------------------------
  function perdeGoster(hataMi, mesaj){
    if (!ogeler) return;
    ogeler.sarmal.style.display = "none";
    ogeler.perde.style.display = "";
    const en = ingilizceMi();
    if (hataMi){
      ogeler.perde.className = "hava-hata";
      ogeler.perde.innerHTML =
        '<i class="fa-solid fa-triangle-exclamation"></i>' +
        '<span>' + (mesaj || (en ? "Weather data unavailable" : "Hava verisi alınamadı")) + '</span>' +
        '<button class="hava-yenile-btn" type="button">' +
        (en ? "Retry" : "Yeniden dene") + '</button>';
      const b = ogeler.perde.querySelector(".hava-yenile-btn");
      if (b) b.addEventListener("click", (ev) => { ev.stopPropagation(); veriAl(true); });
    } else {
      ogeler.perde.className = "hava-yukleniyor";
      ogeler.perde.innerHTML =
        '<i class="fa-solid fa-spinner fa-spin"></i><span>' +
        (en ? "Fetching weather…" : "Hava verisi alınıyor…") + '</span>';
    }
  }

  function gorunumTazele(v){
    if (!ogeler || !v) return;
    const en = ingilizceMi();
    ogeler.perde.style.display = "none";
    ogeler.sarmal.style.display = "";

    // Hava ikonu
    const bilgi = kodBilgi(v.kod);
    const saat = new Date().getHours();
    const gunduz = (saat >= 6 && saat < 20);
    ogeler.ikonKutu.innerHTML = "";
    ogeler.ikonKutu.appendChild(havaIkonu(bilgi.tur, gunduz));

    // Sicaklik ve durum
    ogeler.sic.textContent = (v.sicaklik !== null ? Math.round(v.sicaklik) : "--") + "°";
    ogeler.durumMetin.textContent = en ? bilgi.en : bilgi.tr;
    ogeler.hisMetin.textContent = (v.hissedilen !== null)
      ? ((en ? "feels " : "hissedilen ") + Math.round(v.hissedilen) + "°")
      : "";

    // Ruzgar
    const kn = (v.ruzgarKn !== null) ? v.ruzgarKn : 0;
    const kmh = kn * KN_KMH;
    ogeler.rKnot.innerHTML = kn.toFixed(1) + '<span>kn</span>';
    ogeler.rKmh.innerHTML = kmh.toFixed(1) + '<span>km/h</span>';

    const yon = (v.ruzgarYon !== null) ? v.ruzgarYon : 0;
    // Meteorolojik yon = ruzgarin GELDIGI yon. Ok, ruzgarin GITTIGI
    // yone bakar; bu nedenle 180 derece eklenir.
    ogeler.gulu.ibre.setAttribute("transform",
      "rotate(" + ((yon + 180) % 360).toFixed(1) + " 38 38)");
    ogeler.rYon.textContent = (en ? "from " : "yön ") + Math.round(yon) + "° " + yonAdi(yon);

    const bf = beaufort(kn);
    ogeler.rBeaufort.textContent = "Bft " + bf.kuvvet + " · " + (en ? bf.en : bf.tr);

    // Fan hizi: 0 kn -> durur, 40+ kn -> 0.35 s tur
    const fanEl = ogeler.gulu.fan;
    if (kn < 0.6){
      fanEl.style.animation = "none";
    } else {
      const sure = Math.max(0.32, 4.2 / Math.max(0.6, kn));
      fanEl.style.animation = "ruzgar-fan " + sure.toFixed(2) + "s linear infinite";
    }
    // Akis cizgisi hizi da ruzgara baglanir
    const akisSure = Math.max(0.42, 2.6 / Math.max(0.6, kn) * 1.4);
    ogeler.gulu.svg.querySelectorAll(".ruzgar-akis-cizgi").forEach((c, i) => {
      c.style.animationDuration = akisSure.toFixed(2) + "s";
      c.style.animationDelay = (akisSure / 3 * i).toFixed(2) + "s";
    });

    // Alt kutucuklar
    ogeler.kHamle.b.textContent = (v.hamleKn !== null) ? v.hamleKn.toFixed(0) : "--";
    ogeler.kHamle.s.textContent = en ? "gust kn" : "hamle kn";
    ogeler.kNem.b.textContent = (v.nem !== null) ? v.nem : "--";
    ogeler.kNem.s.textContent = en ? "hum %" : "nem %";
    ogeler.kYagis.b.textContent = (v.yagis !== null) ? v.yagis.toFixed(1) : "--";
    ogeler.kYagis.s.textContent = en ? "prec mm" : "yağış mm";

    // Konum satiri
    const zamanMetin = v.zaman
      ? new Date().toLocaleTimeString(en ? "en-GB" : "tr-TR",
          { hour:"2-digit", minute:"2-digit" })
      : "";
    ogeler.konum.textContent =
      v.lat.toFixed(3) + "°, " + v.lon.toFixed(3) + "°" +
      (v.rakim !== null ? " · " + Math.round(v.rakim) + " m" : "") +
      (zamanMetin ? " · " + zamanMetin : "");
  }

  // ----------------------------------------------------------
  // v2.4.32: BAYAT VERI TAKIBI
  //
  // Cesium'un camera.moveEnd olayi kamera her durdugunda tetiklenir.
  // moveEnd yerine changed/moveStart kullanilmazdi: changed her karede
  // atesler, moveStart ise henuz yeni konum bilinmedigi anda gelir.
  // moveEnd hem seyrek hem de konum kesinlesmis haldedir.
  //
  // Dinleyici widget kapatilsa bile birakilmaz — kaldirilirsa
  // Cesium'un olay listesi sisirilmez ama widget yeniden acildiginda
  // yeniden baglamak gerekir; bunun yerine tek dinleyici tutulur ve
  // widget kapaliyken hicbir sey yapmaz.
  // ----------------------------------------------------------
  function bayatIsaretle(bayatMi){
    bayat = bayatMi;
    // v2.4.33: dugme artik BASLIKTA; gorunurluk widget API'sinden
    // yonetilir (bkz. widget.js `api.yenileGoster`).
    if (wApi && typeof wApi.yenileGoster === "function"){
      const en = ingilizceMi();
      wApi.yenileGoster(bayatMi, bayatMi
        ? ((D().wgHavaBayat)
           || (en ? "Map moved \u2014 refresh weather for this area"
                  : "Harita de\u011fi\u015fti \u2014 bu b\u00f6lgenin havas\u0131n\u0131 yenile"))
        : "");
    }
    if (ogeler && ogeler.konum)
      ogeler.konum.classList.toggle("hava-konum-bayat", bayatMi);
  }

  function kameraIzleyiciKur(){
    if (kameraIzleyiciKurulu) return;
    try {
      if (typeof viewer === "undefined" || !viewer || !viewer.camera) return;
      viewer.camera.moveEnd.addEventListener(() => {
        // Widget kapaliysa veya hic veri yoksa isaretlemenin anlami yok
        if (!ogeler || !sonVeri || !sonKonum) return;
        const merkez = haritaMerkezi();
        if (!merkez) return;
        if (kmUzaklik(sonKonum, merkez) >= KONUM_ESIK_KM) bayatIsaretle(true);
        else if (bayat) bayatIsaretle(false);  // geri donuldu
      });
      kameraIzleyiciKurulu = true;
    } catch (e) {}
  }

  // ----------------------------------------------------------
  // HARITA MERKEZI
  // Kameranin YERE baktigi noktayi dondurur; bulunamazsa kameranin
  // kendi coğrafi konumunu kullanir.
  // ----------------------------------------------------------
  function haritaMerkezi(){
    try {
      if (typeof viewer === "undefined" || !viewer || !viewer.scene) return null;
      const C = window.Cesium;
      if (!C) return null;
      const sahne = viewer.scene;
      // 1) Ekran ortasindan yere isin
      try {
        const kanvas = sahne.canvas;
        const orta = new C.Cartesian2(kanvas.clientWidth / 2, kanvas.clientHeight / 2);
        const isin = viewer.camera.getPickRay(orta);
        if (isin){
          const nokta = sahne.globe.pick(isin, sahne);
          if (nokta){
            const k = C.Cartographic.fromCartesian(nokta);
            if (k) return {
              lat: C.Math.toDegrees(k.latitude),
              lon: C.Math.toDegrees(k.longitude),
            };
          }
        }
      } catch (e) {}
      // 2) Yedek: kamera konumu
      const kk = viewer.camera.positionCartographic;
      if (kk) return {
        lat: C.Math.toDegrees(kk.latitude),
        lon: C.Math.toDegrees(kk.longitude),
      };
    } catch (e) {}
    return null;
  }

  function kmUzaklik(a, b){
    const R = 6371;
    const dLat = (b.lat - a.lat) * Math.PI / 180;
    const dLon = (b.lon - a.lon) * Math.PI / 180;
    const la1 = a.lat * Math.PI / 180, la2 = b.lat * Math.PI / 180;
    const h = Math.sin(dLat/2)**2 + Math.cos(la1) * Math.cos(la2) * Math.sin(dLon/2)**2;
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
  }

  // ----------------------------------------------------------
  // VERI ALMA
  // ----------------------------------------------------------
  function veriAl(zorla){
    if (!ogeler) return;
    if (istekSurmekte) return;
    const merkez = haritaMerkezi();
    if (!merkez){
      perdeGoster(true, ingilizceMi() ? "Map position unknown" : "Harita konumu okunamadı");
      return;
    }
    if (!zorla && sonKonum && sonVeri && kmUzaklik(sonKonum, merkez) < KONUM_ESIK_KM){
      // Konum yeterince yakin: yalnizca zaman satirini tazele
      return;
    }

    istekSurmekte = true;
    if (!sonVeri) perdeGoster(false);

    const url = "https://api.open-meteo.com/v1/forecast" +
      "?latitude=" + merkez.lat.toFixed(4) +
      "&longitude=" + merkez.lon.toFixed(4) +
      "&current=temperature_2m,relative_humidity_2m,apparent_temperature," +
      "precipitation,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m" +
      "&wind_speed_unit=kn";

    const zamanAsimi = new AbortController();
    const zt = setTimeout(() => zamanAsimi.abort(), 12000);

    fetch(url, { signal: zamanAsimi.signal, cache: "no-store" })
      .then(y => {
        if (!y.ok) throw new Error("HTTP " + y.status);
        return y.json();
      })
      .then(j => {
        clearTimeout(zt);
        istekSurmekte = false;
        const c = j && j.current;
        if (!c) throw new Error(
      ((typeof D === "function") ? (D().wgHavaBicimHata) : "") || "Yan\u0131t bi\u00e7imi beklenmedik");
        sonKonum = merkez;
        bayatIsaretle(false);   // veri artik bu bolgeye ait
        sonVeri = {
          lat: merkez.lat, lon: merkez.lon,
          rakim: (typeof j.elevation === "number") ? j.elevation : null,
          zaman: c.time || null,
          sicaklik: sayi(c.temperature_2m),
          hissedilen: sayi(c.apparent_temperature),
          nem: sayi(c.relative_humidity_2m),
          yagis: sayi(c.precipitation),
          kod: (typeof c.weather_code === "number") ? c.weather_code : -1,
          ruzgarKn: sayi(c.wind_speed_10m),
          ruzgarYon: sayi(c.wind_direction_10m),
          hamleKn: sayi(c.wind_gusts_10m),
        };
        gorunumTazele(sonVeri);
      })
      .catch(err => {
        clearTimeout(zt);
        istekSurmekte = false;
        if (sonVeri){
          // Elde eski veri var: onu koru, kullaniciyi bos ekranla bosa dusurme
          gorunumTazele(sonVeri);
        } else {
          const en = ingilizceMi();
          const ag = (err && err.name === "AbortError");
          perdeGoster(true, ag
            ? (en ? "Request timed out" : "İstek zaman aşımına uğradı")
            : (en ? "No internet connection" : "İnternet bağlantısı yok"));
        }
      });
  }

  function sayi(v){ return (typeof v === "number" && isFinite(v)) ? v : null; }

  // ----------------------------------------------------------
  // YASAM DONGUSU
  // ----------------------------------------------------------
  function ac(){
    if (sonVeri) gorunumTazele(sonVeri);
    // Widget acilirken bayat isareti temizlenir: veriAl() zaten
    // guncel merkeze gore karar verir.
    bayatIsaretle(false);
    veriAl(!sonVeri);
    if (!zamanlayici) zamanlayici = setInterval(() => veriAl(true), TAZELEME_MS);
    // Cesium viewer widget'tan sonra kurulmus olabilir; her acilista
    // denenir, kurulduysa bir daha baglanmaz.
    kameraIzleyiciKur();
  }
  function kapa(){
    if (zamanlayici){ clearInterval(zamanlayici); zamanlayici = null; }
  }

  function kaydol(){
    if (!window.Widget) return;
    window.Widget.kaydet({
      id: ID,
      baslik: "HAVA DURUMU",
      baslikAnahtar: "wgHava",
      genislik: 226,
      yukseklik: 224,
      govdeKur: govdeKur,
      ac: ac,
      kapa: kapa,
    });
  }

  window.WidgetHava = {
    kaydol: kaydol,
    veriAl: veriAl,
    ID: ID,
    _merkez: haritaMerkezi,
    _son: function(){ return sonVeri; },
  };
})();
