// ================================================================
// GOKTUNGU VIDEO DUVARI (video.html)
//  - 1 / 2 / 4 / 6 kamera izgara yerlesimi
//  - Panel basina kamera secici + Play / Stop / Duzenle
//  - Ana sistemle ayni WS backend'i ve kamera kayitlarini kullanir
//  - Oturum paylasimi: localStorage goktungu_oturum (ayni origin)
//    kayitliysa otomatik giris; degilse giris perdesi gosterilir
// ================================================================
(function () {
  "use strict";

  // --------------------------------------------------------------
  // TEMA: sunucu "ayarlar" mesajindan gelir (ana sistemle ayni kaynak)
  // --------------------------------------------------------------
  function temaUygulaVd(tema) {
    if (tema === "acik")
      document.documentElement.setAttribute("data-tema", "acik");
    else
      document.documentElement.removeAttribute("data-tema");
  }

  // --------------------------------------------------------------
  // DURUM
  // --------------------------------------------------------------
  const OTURUM_KEY = "goktungu_oturum";
  let ws = null;
  let oturum = null;
  let otomatikGirisDenendi = false;
  let kameralar = [];                 // sunucudan gelen kamera kayitlari
  let yerlesim = parseInt(localStorage.getItem("vdYerlesim") || "4", 10);
  if (![1, 2, 4, 6].includes(yerlesim)) yerlesim = 4;
  // Panel -> kamera id atamasi (indeks = panel sirasi, deger = kamera id|null)
  let atamalar = [];
  try { atamalar = JSON.parse(localStorage.getItem("vdAtamalar") || "[]"); }
  catch (e) { atamalar = []; }
  const oynayanlar = new Set();       // oynatilan panel indeksleri
  const hlsNesneleri = {};            // panelIdx -> Hls instance
  const donanimStreamler = {};        // panelIdx -> MediaStream
  let duzenlenenId = null;            // modalda duzenlenen kamera id

  const izgara = document.getElementById("vdIzgara");
  const wsDurum = document.getElementById("vdWsDurum");
  const oturumBilgi = document.getElementById("vdOturumBilgi");

  // --------------------------------------------------------------
  // v2.4.34: CEVIRI ERISIMI
  // --------------------------------------------------------------
  // v2.4.33'e kadar /video sayfasi i18n.js'i hic yuklemiyordu; bu
  // dosyadaki tum metinler Turkce gomuluydu ve dil EN'e alinsa bile
  // sayfa Turkce kaliyordu. Artik ortak sozluk yuklu. Erisim
  // korumalidir: sozluk bir sekilde yoksa Turkce yedek kullanilir.
  function S(anahtar, yedek){
    try {
      const t = D();
      if (t && t[anahtar] !== undefined) return t[anahtar];
    } catch(e){}
    return yedek;
  }

  // WS durum metni dil degisiminde yeniden yazilabilsin diye son
  // durum kodu saklanir; aksi halde yeni bir WS olayi beklemek
  // gerekirdi ve durum cubugu eski dilde takili kalirdi.
  let sonWsKod = "baglaniyor";
  let sonWsPort = 0;

  function wsDurumTazele(){
    if (!wsDurum) return;
    if (sonWsKod === "bagli"){
      wsDurum.textContent = S("vpSunucuBagli", "Sunucu ba\u011fl\u0131")
                            + " (:" + sonWsPort + ")";
      wsDurum.className = "f-iyi";
    } else if (sonWsKod === "koptu"){
      wsDurum.textContent = S("vpSunucuKoptu", "Sunucu ba\u011flant\u0131s\u0131 koptu");
      wsDurum.className = "f-kotu";
    } else {
      wsDurum.textContent = S("vpSunucuyaBaglaniliyor", "Sunucuya ba\u011flan\u0131l\u0131yor...");
      wsDurum.className = "f-kotu";
    }
  }

  function atamalariKaydet() {
    try { localStorage.setItem("vdAtamalar", JSON.stringify(atamalar)); }
    catch (e) {}
  }

  // --------------------------------------------------------------
  // WEBSOCKET (bagimsiz, ws.js'deki port listesiyle ayni)
  // --------------------------------------------------------------
  const WS_PORTLAR = [8765, 8766, 8777, 9765];
  /* FAZ18-IS20-VD-OTURUM: WSS_PORT bu dosyada TANIMLI DEGILDI.
     flight.js:24 ve ws.js ayni sabiti tasiyor; Video Duvari HTTPS
     dalini hic uygulamadigi icin sabite ihtiyac duymamisti. */
  const WSS_PORT = 9443;
  let wsPortIdx = 0;
  let hicBaglanmadi = true;

  function wsGonder(obj) {
    if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj));
  }

  function wsBaglan() {
    const port = WS_PORTLAR[wsPortIdx];
    const host = location.hostname || "localhost";
    try {
      /* FAZ18-IS20-VD-OTURUM: WS ADRES SECIMI
       * --------------------------------------------------------------
       * OLCULEN KUSUR: bu dosya TEK ve KOSULSUZ bir dal tasiyordu:
       *     new WebSocket("ws://" + host + ":" + port)
       * Sayfa https://app.goktungu.com/video.html adresinden gelse
       * bile duz `ws://` deneniyordu. Tarayici bunu KARISIK ICERIK
       * olarak engeller: baglanti hic kurulmaz, `onopen` cagrilmaz,
       * `girisDurumunuIsle()` hic kosmaz. Kullanici giris perdesini
       * gorur, elle giris de `readyState !== 1` yuzunden "Sunucu
       * baglantisi yok" der. Video Duvari HTTPS'te tamamen islevsizdi.
       *
       * Dogru dallanma sistemde IKI yerde zaten vardi: js/flight.js ve
       * js/ws.js (IS-WSTUNEL). Bu dosya ucuncu yer olarak geride
       * kalmisti. Yeni desen uydurulmadi; mevcut kanonik dallanma
       * birebir uygulandi.
       */
      if (/\.manus\.computer$/.test(host)) {
        ws = new WebSocket("wss://" + host.replace(/^\d+-/, "8765-"));
      } else if (location.pathname.indexOf("/app/") === 0
                 || /^app\./i.test(host)) {
        /* MERKEZ KIPI: sayfa /app/ altindan ya da app. alt alan
           adindan geldi. Ana arayuzle AYNI yolu kullanir: 443
           uzerindeki /app/ws tuneli. */
        const sema = location.protocol === "https:" ? "wss://" : "ws://";
        ws = new WebSocket(sema + location.host + "/app/ws");
      } else if (location.protocol === "https:") {
        /* Arayuz vekili yolu zorunlu (bkz. js/ws.js ayni dal). */
        ws = new WebSocket("wss://" + host + ":" + WSS_PORT + "/app/ws");
      } else {
        ws = new WebSocket("ws://" + host + ":" + port);
      }
    } catch (err) {
      setTimeout(wsBaglan, 3000);
      return;
    }
    ws.onopen = () => {
      hicBaglanmadi = false;
      sonWsKod = "bagli"; sonWsPort = port;
      wsDurumTazele();
      otomatikGirisDenendi = false;
      girisDurumunuIsle();
    };
    ws.onclose = () => {
      sonWsKod = "koptu";
      wsDurumTazele();
      if (hicBaglanmadi) wsPortIdx = (wsPortIdx + 1) % WS_PORTLAR.length;
      setTimeout(wsBaglan, hicBaglanmadi ? 500 : 2000);
    };
    ws.onerror = () => { try { ws.close(); } catch (e) {} };
    ws.onmessage = (ev) => {
      let m;
      try { m = JSON.parse(ev.data); } catch (e) { return; }
      if (m.tip === "kamera_listesi") {
        kameralar = m.kameralar || [];
        izgaraCiz();
      } else if (m.tip === "kamera_cihazlari") {
        // v2.4.7: sunucu makinesindeki yerel kamera cihazlari
        cihazlarGeldi(m.cihazlar || []);
      } else if (m.tip === "giris_sonucu") {
        girisSonucIsle(m);
      } else if (m.tip === "ayarlar") {
        if (m.ayarlar && m.ayarlar.tema) temaUygulaVd(m.ayarlar.tema);
      }
    };
  }

  // --------------------------------------------------------------
  // GIRIS / OTURUM
  // --------------------------------------------------------------
  const girisPerde = document.getElementById("girisPerde");
  const girisEposta = document.getElementById("girisEposta");
  const girisSifre = document.getElementById("girisSifre");
  const girisHatirla = document.getElementById("girisHatirla");
  const btnGiris = document.getElementById("btnGiris");
  const girisHata = document.getElementById("girisHata");

  function sakliOturum() {
    try { return JSON.parse(localStorage.getItem(OTURUM_KEY) || "null"); }
    catch (e) { return null; }
  }

  /* FAZ18-IS20-VD-OTURUM: OTURUM DEVRI IKINCI YOL
   * ----------------------------------------------------------------
   * OLCULEN KUSUR: bu pencere oturum devri icin YALNIZCA
   * localStorage'a bakiyordu. Ana uygulamada jeton oraya sadece
   * kullanici "Bilgileri sakla" kutusunu isaretlerse yaziliyor
   * (kullanici.js:121); isaretlemezse VARSA SILINIYOR. Yani normal
   * kullanimda anahtar bos oluyor ve Video Duvari giris istiyordu.
   *
   * Ana uygulamanin IKINCI yolu vardi ve burada kullanilmiyordu:
   * `api/oturum/devir` ucu HttpOnly cerezden jeton uretiyor ve onay
   * kutusundan BAGIMSIZ calisiyor (kullanici.js:194). Uc canlida
   * dogrulandi. Ayni desen buraya tasindi.
   */
  let _devirDenendi = false;
  async function cerezdenJetonAl() {
    /* Tek deneme: basarisiz olursa BIR DAHA denenmez. Sonsuz yeniden
       deneme dongusu, WS her koptugunda yeni istek uretir ve sunucuyu
       gereksiz yukler. kullanici.js:194 ayni korumayi tasiyor. */
    if (_devirDenendi) return null;
    _devirDenendi = true;
    try {
      /* `credentials: "same-origin"` ZORUNLU: cerez HttpOnly ve
         gonderilmezse uc her zaman "Kurumsal oturum yok" doner. */
      const y = await fetch("api/oturum/devir", {
        credentials: "same-origin", cache: "no-store" });
      /* Kapali devre kurulumda (Merkez Uygulama) uc bulunmayabilir.
         Sessiz gecilir; giris perdesi zaten yedek yoldur. */
      if (!y.ok) return null;
      const d = await y.json();
      if (!d || !d.tamam || !d.jeton) return null;
      try {
        localStorage.setItem(OTURUM_KEY, JSON.stringify({
          eposta: d.eposta, jeton: d.jeton }));
      } catch (e) { /* depolama kapali: devir kalici olmaz */ }
      return d.jeton;
    } catch (e) {
      /* Ag hatasi: elle girise dusulur, cokme olmaz. */
      return null;
    }
  }

  function girisPerdesiniGoster() {
    girisPerde.classList.remove("popup-gizli");
    setTimeout(() => girisEposta.focus(), 50);
  }

  async function girisDurumunuIsle() {
    // WS acildiginda cagrilir: kayitli oturum varsa otomatik giris dene,
    // yoksa cerezden devir dene, o da olmazsa giris perdesini goster
    if (oturum) return;
    const s = sakliOturum();
    if (s && s.eposta && s.jeton && !otomatikGirisDenendi) {   // BULGU_10a
      otomatikGirisDenendi = true;
      wsGonder({ tip: "jeton_giris", jeton: s.jeton });   // BULGU_10a
      return;
    }
    if (!s || !s.eposta || !s.jeton) {   // BULGU_10a
      /* IKINCI YOL: localStorage bos. Ana uygulama oturumu cerezde
         olabilir; oradan jeton istenir. */
      const jeton = await cerezdenJetonAl();
      if (jeton && !otomatikGirisDenendi) {
        otomatikGirisDenendi = true;
        wsGonder({ tip: "jeton_giris", jeton: jeton });
        return;
      }
      girisPerdesiniGoster();
    }
  }

  function girisGonder() {
    const e = girisEposta.value.trim().toLowerCase();
    const s = girisSifre.value;
    if (!e || !s) {
      girisHata.textContent = S("vpHataGirisBos", "E-posta ve \u015fifre bo\u015f olamaz") + ".";
      return;
    }
    if (!ws || ws.readyState !== 1) {
      girisHata.textContent = S("girisHataSunucu", "Sunucu ba\u011flant\u0131s\u0131 yok. L\u00fctfen bekleyin...");
      return;
    }
    girisHata.textContent = "";
    btnGiris.disabled = true;
    wsGonder({ tip: "giris", eposta: e, sifre: s });
  }

  function girisSonucIsle(m) {
    btnGiris.disabled = false;
    if (m.basarili && m.kullanici) {
      oturum = m.kullanici;
      // Perdeden elle giris yapildiysa ve "sakla" isaretliyse kaydet
      if (!girisPerde.classList.contains("popup-gizli") && girisHatirla.checked &&
          girisEposta.value.trim()) {
        // BULGU_10a: PAROLA DEGIL, oturum jetonu saklanir.
        // `kullanici.js` ile AYNI OTURUM_KEY anahtarini paylasir; biri
        // duzeltilip digeri birakilsaydi parola yine diske yazilmaya
        // devam ederdi.
        //
        // Jeton YOKSA kayit SILINIR: bos jetonlu kayit ise yaramaz ama
        // dolu gorundugu icin otomatik giris denenir ve sessizce
        // basarisiz olur.
        try {
          if (m.jeton) {
            localStorage.setItem(OTURUM_KEY, JSON.stringify({
              eposta: girisEposta.value.trim().toLowerCase(),
              jeton: m.jeton }));
          } else {
            localStorage.removeItem(OTURUM_KEY);
          }
        } catch (e) {}
      }
      girisPerde.classList.add("popup-gizli");
      oturumBilgi.textContent = (oturum.ad_soyad || oturum.eposta || "");
      oturumBilgi.className = "f-iyi";
    } else {
      // Otomatik giris basarisizsa da perdeyi goster
      girisPerde.classList.remove("popup-gizli");
      girisHata.textContent = m.hata
        || (S("vpHataGirisHatali", "E-posta veya \u015fifre hatal\u0131") + ".");
      girisSifre.value = "";
      setTimeout(() => girisSifre.focus(), 50);
    }
  }

  btnGiris.addEventListener("click", girisGonder);
  girisSifre.addEventListener("keydown", (e) => {
    if (e.key === "Enter") girisGonder();
  });
  girisEposta.addEventListener("keydown", (e) => {
    if (e.key === "Enter") girisSifre.focus();
  });

  // --------------------------------------------------------------
  // VIDEO ELEMANI (kameralar.js ile ayni akis mantigi)
  // --------------------------------------------------------------
  function proxyUrl(id) {
    // FAZ19-IS60B: AYNI ORIGIN. Eskiden 8801 portlu mutlak adres
    // kullaniliyordu; merkez kipinde o port DINLENMIYOR ve sayfa
    // https iken adres http oldugundan tarayici karisik icerigi
    // engelliyordu (ERR_CONNECTION_TIMED_OUT). `/tile/` karo
    // vekili ayni sorunu coktan cozmus; video ayni yolu izler.
    //
    // `goktunguYol` DOGRUDAN cagrilmaz: video.html harita.js'i
    // yuklemiyor, orada tanimsiz olur ve ReferenceError video
    // duvarini tamamen kirardi. Varsa kullanilir, yoksa AYNI
    // formul yerinde hesaplanir.
    var tb = window.GOKTUNGU_TABAN ||
      ((location.pathname || "/").replace(/[^/]*$/, "") || "/");
    return tb + "kamera/" + id + "?t=" + Date.now();
  }

  function videoOlustur(kamera, panelIdx) {
    const prot = kamera.protokol;
    // v2.4.7: donanim + dji + mjpeg dahil tum MJPEG kaynaklari sunucu
    // proxy'sinden gelir (AI aktifse tespit cerceveli anotasyonlu kare)
    if (prot === "rtsp" || prot === "rtp" || prot === "mjpeg" ||
        prot === "dji" || prot === "donanim" || prot === "http") {
      // v2.4.10: http (MP4/WebM) da proxy'den - AI anotasyonlu
      const img = document.createElement("img");
      img.className = "vd-video";
      img.draggable = false;
      // v2.4.33: dayanikli yukleme. NOT: video duvarinda hata sinifi
      // `vd-hata` (kam-hata degil); mjpegBagla kam-* siniflari uygular,
      // bu yuzden burada ek olarak vd-hata koprusu kurulur.
      if (typeof window.mjpegBagla === "function") {
        window.mjpegBagla(img, () => proxyUrl(kamera.id), ".vd-govde");
        img.addEventListener("load", () => {
          img.closest(".vd-govde")?.classList.remove("vd-hata");
        });
        // Tum denemeler tukendiginde mjpegBagla kam-hata uygular;
        // MutationObserver yerine basit bir gozlem: kam-hata gorunurse
        // vd-hata da eklenir (CSS iki sinifi da destekler).
        const govde = () => img.closest(".vd-govde");
        const gozle = new MutationObserver(() => {
          const g = govde();
          if (!g) { gozle.disconnect(); return; }
          if (g.classList.contains("kam-hata")) g.classList.add("vd-hata");
          else g.classList.remove("vd-hata");
        });
        // govde henuz DOM'a eklenmemis olabilir; bir tur bekle
        setTimeout(() => {
          const g = govde();
          if (g) gozle.observe(g, { attributes: true,
                                    attributeFilter: ["class"] });
        }, 0);
      } else {
        img.src = proxyUrl(kamera.id);
        img.addEventListener("error", () => {
          img.closest(".vd-govde")?.classList.add("vd-hata");
        });
        img.addEventListener("load", () => {
          img.closest(".vd-govde")?.classList.remove("vd-hata");
        });
      }
      return img;
    }
    const video = document.createElement("video");
    video.className = "vd-video";
    video.autoplay = true; video.muted = true;
    video.playsInline = true; video.controls = false;
    if (prot === "hls") {
      if (window.Hls && Hls.isSupported()) {
        const h = new Hls({ lowLatencyMode: true });
        h.loadSource(kamera.url);
        h.attachMedia(video);
        hlsNesneleri[panelIdx] = h;
      } else {
        video.src = kamera.url;
      }
    } else {
      video.src = kamera.url;
      video.loop = true;
    }
    video.addEventListener("error", () => {
      video.closest(".vd-govde")?.classList.add("vd-hata");
    });
    video.addEventListener("canplay", () => {
      if (video.paused) video.play().catch(() => {});
    });
    setTimeout(() => { if (video.paused) video.play().catch(() => {}); }, 300);
    return video;
  }

  function videoTemizle(panelIdx) {
    if (hlsNesneleri[panelIdx]) {
      try { hlsNesneleri[panelIdx].destroy(); } catch (e) {}
      delete hlsNesneleri[panelIdx];
    }
    if (donanimStreamler[panelIdx]) {
      try {
        donanimStreamler[panelIdx].getTracks().forEach((t) => t.stop());
      } catch (e) {}
      delete donanimStreamler[panelIdx];
    }
    // RTSP/RTP proxy'sini yalnizca ayni kamerayi oynatan baska panel
    // yoksa serbest birak
    const kamId = atamalar[panelIdx];
    const kam = kameralar.find((k) => k.id === kamId);
    if (kam && (kam.protokol === "rtsp" || kam.protokol === "rtp")) {
      const baskaOynayan = [...oynayanlar].some(
        (i) => i !== panelIdx && atamalar[i] === kamId);
      if (!baskaOynayan) wsGonder({ tip: "kamera_proxy_durdur", id: kamId });
    }
  }

  // --------------------------------------------------------------
  // IZGARA CIZIMI
  // --------------------------------------------------------------
  const YERLESIM_SINIF = { 1: "vd-1", 2: "vd-2", 4: "vd-4", 6: "vd-6" };

  function panelOlustur(panelIdx) {
    const panel = document.createElement("div");
    panel.className = "vd-panel";

    // --- BASLIK ---
    const baslik = document.createElement("div");
    baslik.className = "vd-baslik";

    const ikon = document.createElement("i");
    ikon.className = "fa-solid fa-video vd-baslik-ikon" +
      (oynayanlar.has(panelIdx) ? " aktif" : "");

    const sec = document.createElement("select");
    sec.className = "vd-kam-sec";
    const bosOpt = document.createElement("option");
    bosOpt.value = "";
    bosOpt.textContent = S("vpKameraSec", "— Kamera seç —");
    sec.appendChild(bosOpt);
    kameralar.forEach((k) => {
      const opt = document.createElement("option");
      opt.value = String(k.id);
      opt.textContent = k.isim + " [" + k.protokol.toUpperCase() + "]";
      sec.appendChild(opt);
    });
    if (atamalar[panelIdx] !== null && atamalar[panelIdx] !== undefined &&
        kameralar.some((k) => k.id === atamalar[panelIdx])) {
      sec.value = String(atamalar[panelIdx]);
    }
    sec.addEventListener("change", () => {
      // Kamera degisince eski akisi durdur
      if (oynayanlar.has(panelIdx)) {
        videoTemizle(panelIdx);
        oynayanlar.delete(panelIdx);
      }
      atamalar[panelIdx] = sec.value ? Number(sec.value) : null;
      atamalariKaydet();
      // Yeni kamera secildiyse otomatik oynat
      if (atamalar[panelIdx] !== null) oynayanlar.add(panelIdx);
      izgaraCiz();
    });

    const araclar = document.createElement("div");
    araclar.className = "vd-araclar";
    const kamId = atamalar[panelIdx];
    const kam = kameralar.find((k) => k.id === kamId);
    const oynuyor = oynayanlar.has(panelIdx);

    const bPlay = document.createElement("button");
    bPlay.className = "vd-btn " + (oynuyor ? "vd-btn-stop" : "vd-btn-play");
    bPlay.title = oynuyor ? S("vpDurdur", "Durdur") : S("vpOynat", "Oynat");
    bPlay.innerHTML = oynuyor
      ? "<i class='fa-solid fa-stop'></i>"
      : "<i class='fa-solid fa-play'></i>";
    bPlay.disabled = !kam;
    bPlay.addEventListener("click", () => {
      if (!kam) return;
      if (oynayanlar.has(panelIdx)) {
        videoTemizle(panelIdx);
        oynayanlar.delete(panelIdx);
      } else {
        oynayanlar.add(panelIdx);
      }
      izgaraCiz();
    });

    const bDuzenle = document.createElement("button");
    bDuzenle.className = "vd-btn";
    bDuzenle.title = S("vpDuzenle", "Düzenle");
    bDuzenle.innerHTML = "<i class='fa-solid fa-pen'></i>";
    bDuzenle.disabled = !kam;
    bDuzenle.addEventListener("click", () => { if (kam) modalAc(kam); });

    araclar.append(bPlay, bDuzenle);
    baslik.append(ikon, sec, araclar);

    // --- GOVDE (video alani) ---
    const govde = document.createElement("div");
    govde.className = "vd-govde";
    if (kam && oynuyor) {
      govde.appendChild(videoOlustur(kam, panelIdx));
    } else {
      const bos = document.createElement("div");
      bos.className = "vd-bos";
      // Metinler textContent ile yazilir: sozlukten gelen deger HTML
      // olarak yorumlanmamalidir (kullanici verisi olmasa da kural).
      const bIkon = document.createElement("i");
      bIkon.className = kam ? "fa-solid fa-video-slash" : "fa-solid fa-video";
      const bMetin = document.createElement("span");
      bMetin.textContent = kam
        ? S("vpDurduruldu", "DURDURULDU")
        : S("vpKameraSecin", "KAMERA SEÇİN");
      bos.append(bIkon, bMetin);
      govde.appendChild(bos);
    }

    panel.append(baslik, govde);
    return panel;
  }

  function izgaraCiz() {
    // Once tum eski akislari temizlemeden yalnizca DOM'u tazeleyecegiz;
    // HLS/donanim nesneleri panel indeksine bagli oldugundan, cizim
    // oncesi gecersiz kalan (yerlesim disinda kalan) akislari kapat
    Object.keys(hlsNesneleri).forEach((i) => {
      if (Number(i) >= yerlesim || !oynayanlar.has(Number(i))) {
        try { hlsNesneleri[i].destroy(); } catch (e) {}
        delete hlsNesneleri[i];
      }
    });
    Object.keys(donanimStreamler).forEach((i) => {
      if (Number(i) >= yerlesim || !oynayanlar.has(Number(i))) {
        try { donanimStreamler[i].getTracks().forEach((t) => t.stop()); }
        catch (e) {}
        delete donanimStreamler[i];
      }
    });
    // HLS nesneleri her cizimde yeniden kurulacagi icin kalanlari da yok et
    Object.keys(hlsNesneleri).forEach((i) => {
      try { hlsNesneleri[i].destroy(); } catch (e) {}
      delete hlsNesneleri[i];
    });

    izgara.innerHTML = "";
    izgara.className = YERLESIM_SINIF[yerlesim] || "vd-4";
    for (let i = 0; i < yerlesim; i++) {
      izgara.appendChild(panelOlustur(i));
    }
    yerlesimDugmeTazele();
  }

  // --------------------------------------------------------------
  // YERLESIM DUGMELERI + TAM EKRAN
  // --------------------------------------------------------------
  const yerlesimBtnler =
    document.querySelectorAll("#vdYerlesimGrup button[data-yerlesim]");

  function yerlesimDugmeTazele() {
    yerlesimBtnler.forEach((b) =>
      b.classList.toggle("secili", Number(b.dataset.yerlesim) === yerlesim));
  }

  yerlesimBtnler.forEach((b) => b.addEventListener("click", () => {
    const yeni = Number(b.dataset.yerlesim);
    if (yeni === yerlesim) return;
    // Yerlesim kuculurken disarida kalan panellerin akislarini durdur
    for (let i = yeni; i < yerlesim; i++) {
      if (oynayanlar.has(i)) { videoTemizle(i); oynayanlar.delete(i); }
    }
    yerlesim = yeni;
    localStorage.setItem("vdYerlesim", String(yerlesim));
    izgaraCiz();
  }));

  document.getElementById("vdTamEkran").addEventListener("click", () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen().catch(() => {});
  });

  // --------------------------------------------------------------
  // DUZENLEME MODALI (kamera_kaydet ana sistemle paylasilir)
  // --------------------------------------------------------------
  const perde = document.getElementById("vdModalPerde");
  const inAd = document.getElementById("vdKamAd");
  const inProt = document.getElementById("vdKamProt");
  const inUrl = document.getElementById("vdKamUrl");
  const urlSatir = document.getElementById("vdUrlSatir");
  const cihazSatir = document.getElementById("vdCihazSatir");
  const cihazSec = document.getElementById("vdCihazSec");
  const hataEl = document.getElementById("vdKamHata");

  // v2.4.7: cihazlar SUNUCU makinesinden listelenir (indeks tabanli)
  function cihazlariListele() {
    cihazSec.innerHTML = "";
    const o = document.createElement("option");
    o.value = "";
    o.textContent = S("vpCihazlarSorgulaniyor", "Cihazlar sorgulan\u0131yor...");
    cihazSec.appendChild(o);
    wsGonder({ tip: "kamera_cihazlari" });
  }
  function cihazlarGeldi(cihazlar) {
    if (!cihazSec) return;
    cihazSec.innerHTML = "";
    if (!cihazlar.length) {
      const o = document.createElement("option");
      o.value = "";
      o.textContent = S("vpKameraBulunamadi", "Sunucuda kamera bulunamad\u0131");
      cihazSec.appendChild(o);
      return;
    }
    for (const c of cihazlar) {
      const opt = document.createElement("option");
      opt.value = String(c.indeks);
      opt.textContent = c.ad || (S("vpKameraNo", "Kamera") + " " + c.indeks);
      cihazSec.appendChild(opt);
    }
    if (cihazSec.dataset.secili) {
      cihazSec.value = cihazSec.dataset.secili;
      delete cihazSec.dataset.secili;
    }
  }

  function protokolDegisti() {
    if (inProt.value === "donanim") {
      cihazSatir.classList.remove("gizli");
      urlSatir.classList.add("gizli");
      cihazlariListele();
    } else {
      cihazSatir.classList.add("gizli");
      urlSatir.classList.remove("gizli");
    }
  }
  inProt.addEventListener("change", protokolDegisti);

  function modalAc(kamera) {
    duzenlenenId = kamera.id;
    inAd.value = kamera.isim || "";
    inProt.value = kamera.protokol || "rtsp";
    inUrl.value = (kamera.protokol === "donanim") ? "" : (kamera.url || "");
    hataEl.textContent = "";
    protokolDegisti();
    if (kamera.protokol === "donanim") {
      // Mevcut cihazi secili getirmeye calis
      setTimeout(() => { cihazSec.value = kamera.url || ""; }, 400);
    }
    perde.classList.remove("popup-gizli");
    setTimeout(() => inAd.focus(), 50);
  }

  function modalKapat() {
    perde.classList.add("popup-gizli");
    duzenlenenId = null;
  }

  function modalKaydet() {
    const isim = inAd.value.trim();
    const prot = inProt.value;
    let url = inUrl.value.trim();
    if (!isim) {
      hataEl.textContent = S("vpHataKamAd", "Kamera ad\u0131 bo\u015f olamaz") + ".";
      return;
    }
    if (prot === "donanim") {
      url = cihazSec.value || "";
      if (!url) {
        hataEl.textContent = S("vpHataKamCihaz", "Kamera cihaz\u0131 se\u00e7in") + ".";
        return;
      }
    } else if (!url) {
      hataEl.textContent = S("vpHataKamUrl", "Yay\u0131n adresi bo\u015f olamaz") + ".";
      return;
    }
    const k = { tip: "kamera_kaydet", isim: isim, protokol: prot, url: url };
    if (duzenlenenId !== null) k.id = duzenlenenId;
    wsGonder(k);
    modalKapat();
    // kamera_listesi yaniti gelince izgara otomatik tazelenir
  }

  document.getElementById("vdKamKaydet").addEventListener("click", modalKaydet);
  document.getElementById("vdKamIptal").addEventListener("click", modalKapat);
  document.getElementById("vdModalKapat").addEventListener("click", modalKapat);
  perde.addEventListener("click", (e) => { if (e.target === perde) modalKapat(); });
  inUrl.addEventListener("keydown", (e) => { if (e.key === "Enter") modalKaydet(); });

  // --------------------------------------------------------------
  // BASLAT
  // --------------------------------------------------------------
  // Sakli oturum yoksa giris perdesini hemen goster (WS beklenmez);
  // sakli oturum varsa WS acilinca otomatik giris denenir
  (function () {
    const s = sakliOturum();
    if (!s || !s.eposta || !s.jeton) {   // BULGU_10a
      girisPerde.classList.remove("popup-gizli");
      setTimeout(() => girisEposta.focus(), 50);
    }
  })();
  // --------------------------------------------------------------
  // v2.4.34: DIL TAZELEME KANCASI
  // --------------------------------------------------------------
  // applyLanguage() bu fonksiyonu cagirir. Panel basliklari, kamera
  // secim listeleri, dugme ipuclari ve durum cubugu JS ile uretildigi
  // icin `data-i18n` dongusu onlara ulasmaz; izgara yeniden cizilir.
  // NOT: izgaraCiz() oynatilan akislari korur (oynayanlar kumesi
  // degismez), dolayisiyle dil degisimi canli yayini kesmez.
  window.videoDuvarDilTazele = function(){
    try {
      wsDurumTazele();
      izgaraCiz();
    } catch(e){}
  };

  izgaraCiz();
  wsBaglan();
})();
