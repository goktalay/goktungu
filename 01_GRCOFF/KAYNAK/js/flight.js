// =================================================================
// GOKTUNGU - UCUS DUVARI (/flight)   v2.4.32
//
// Ikinci ekranda coklu dron izleme. 6 panel, video wall tarzi
// yerlesim dugmeleri, panel basina cevrimici dron secimi ve her
// panelde PFD gostergesi.
//
// NEDEN KENDI WS BAGLANTISI:
//   index.html'in ws.js dosyasi wsDurum, btnRadarBaglan gibi GCS DOM
//   ogelerini dogrudan kullanir; bu sayfada o ogeler yoktur ve dosya
//   yuklendigi anda patlar. Bu nedenle burada ayni protokol bagimsiz
//   olarak kurulur. Bagimlilik yoktur, yalnizca protokol paylasilir.
//
// SECIM KALICILIGI:
//   Panel-dron eslemesi ve yerlesim localStorage'da tutulur. Ikinci
//   ekran genelde ayni dronlari izler; sayfa yenilenince kullanicinin
//   6 paneli yeniden secmesi kabul edilemez.
// =================================================================
(function(){
  "use strict";

  // ws.js:11 ile ayni sirada olmali
  const WS_PORTLAR = [8765, 8766, 8777, 9765];
  const WSS_PORT = 9443;

  const YER_KEY = "gcs_flight_yerlesim";
  const SEC_KEY = "gcs_flight_secimler";

  let ws = null;
  let wsPortIdx = 0;
  let hicBaglanmadi = true;

  // sysid -> dron sozlugu (son telemetri)
  let dronlar = new Map();
  // panel indeksi (0-5) -> sysid (metin) veya ""
  let secimler = ["", "", "", "", "", ""];
  let yerlesim = 6;

  const izgara = document.getElementById("fwIzgara");
  const elWsDurum = document.getElementById("fwWsDurum");
  const elDronSayi = document.getElementById("fwDronSayi");

  // -----------------------------------------------------------------
  // v2.4.34: CEVIRI ERISIMI
  // -----------------------------------------------------------------
  // Bu sayfa v2.4.33'e kadar i18n.js'i HIC yuklemiyordu ve tum
  // metinleri Turkce gomuluydu. Artik ortak sozluk yuklu; ancak bu
  // modul i18n.js'ten ONCE de yuklenebilecegi icin (yukleme sirasi
  // degisirse) her erisim korumali yapilir: sozluk yoksa Turkce
  // yedek metin kullanilir, sayfa asla patlamaz.
  function S(anahtar, yedek){
    try {
      const t = D();
      if (t && t[anahtar] !== undefined) return t[anahtar];
    } catch(e){}
    return yedek;
  }

  // Panel nesneleri: { kok, canvas, secim, baslikAd, sonSysid }
  const paneller = [];

  // -----------------------------------------------------------------
  // Kalicilik
  // -----------------------------------------------------------------
  function ayarYukle(){
    try {
      const y = parseInt(localStorage.getItem(YER_KEY), 10);
      if (y >= 1 && y <= 6) yerlesim = y;
    } catch(e){}
    try {
      const s = JSON.parse(localStorage.getItem(SEC_KEY) || "null");
      if (Array.isArray(s)){
        for (let i = 0; i < 6; i++) secimler[i] = String(s[i] || "");
      }
    } catch(e){}
  }

  function ayarKaydet(){
    try {
      localStorage.setItem(YER_KEY, String(yerlesim));
      localStorage.setItem(SEC_KEY, JSON.stringify(secimler));
    } catch(e){}
  }

  // -----------------------------------------------------------------
  // Panel kurulumu
  // -----------------------------------------------------------------
  function panelleriKur(){
    izgara.innerHTML = "";
    paneller.length = 0;

    for (let i = 0; i < 6; i++){
      const kok = document.createElement("div");
      kok.className = "fw-panel";
      kok.dataset.idx = String(i);

      const baslik = document.createElement("div");
      baslik.className = "fw-p-baslik";

      const no = document.createElement("span");
      no.className = "fw-p-no";
      no.textContent = String(i + 1);

      const secim = document.createElement("select");
      secim.className = "fw-p-secim";
      secim.title = S("ucusPanelIpucu", "Bu panelde g\u00f6sterilecek dron");

      const ad = document.createElement("span");
      ad.className = "fw-p-ad";

      // v2.4.45: panel basina tam ekran. Ikinci ekranda tek dronu
      // buyutmek en sik istenen istek; sayfa tam ekraniyla ayni
      // Fullscreen API kullanilir ama hedef eleman PANELdir.
      const tam = document.createElement("button");
      tam.className = "fw-p-tam";
      tam.type = "button";
      tam.title = S("ucusPanelTamEkran", "Bu paneli tam ekran yap");
      tam.innerHTML =
        '<svg viewBox="0 0 24 24" class="fw-tam-ac">' +
        '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></svg>' +
        '<svg viewBox="0 0 24 24" class="fw-tam-kapa">' +
        '<path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5"/></svg>';

      baslik.appendChild(no);
      baslik.appendChild(secim);
      baslik.appendChild(ad);
      baslik.appendChild(tam);

      const govde = document.createElement("div");
      govde.className = "fw-p-govde";
      const cv = document.createElement("canvas");
      cv.className = "fw-p-canvas";
      govde.appendChild(cv);

      kok.appendChild(baslik);
      kok.appendChild(govde);
      izgara.appendChild(kok);

      const p = { kok: kok, canvas: cv, secim: secim, ad: ad, tam: tam };
      paneller.push(p);

      secim.addEventListener("change", () => {
        secimler[i] = secim.value;
        ayarKaydet();
        cizKare();
      });

      tam.addEventListener("click", (ev) => {
        ev.stopPropagation();
        panelTamEkranCevir(i);
      });
    }
  }

  // =================================================================
  // v2.4.45: TAM EKRAN (sayfa ve panel bazinda)
  // =================================================================
  // Kullanici istegi: ucus duvarinda mutlaka tam ekran gosterme
  // dugmesi olsun. Iki ayri ihtiyac vardir ve ikisi de karsilaniyor:
  //   1) SAYFA tam ekran  -> ust seritteki #fwTamEkran
  //   2) PANEL tam ekran  -> her panel basligindaki .fw-p-tam
  //
  // Tasarim notlari:
  //  - Fullscreen API izin gerektirir ve YALNIZ kullanici hareketiyle
  //    calisir; bu yuzden dugme/klavye olayindan dogrudan cagrilir.
  //  - Tarayici tam ekrani REDDEDERSE (izin yok, kiosk, iframe) sayfa
  //    islevsiz kalmasin diye CSS tabanli "sahte tam ekran" devreye
  //    girer: panel `position:fixed` ile tum goruntu alanini kaplar.
  //    Ikinci ekranda F11 ile zaten tam ekran olan tarayicida bu kip
  //    tek panele odaklanmak icin de dogru davranistir.
  //  - Canvas boyutu her karede cizKare() icinde yeniden olculdugu
  //    icin tam ekrana gecisde ek yeniden boyutlandirma gerekmez.
  //  - Esc tarayici tarafindan tam ekrani kapatir; `fullscreenchange`
  //    dinleyicisi ile sahte kip ve ikonlar da senkron tutulur.
  let tamPanelIdx = -1;   // -1: panel tam ekran yok
  let sahteTam = false;   // Fullscreen API reddedildiginde true

  function tamEkranAktif(){
    return !!(document.fullscreenElement ||
              document.webkitFullscreenElement);
  }

  function tamIste(el){
    // Soz dondurur; reddedilirse sahte kipe dusulur.
    try {
      if (el.requestFullscreen) return el.requestFullscreen();
      if (el.webkitRequestFullscreen)
        return Promise.resolve(el.webkitRequestFullscreen());
    } catch(e){}
    return Promise.reject(new Error("fullscreen yok"));
  }

  function tamCik(){
    try {
      if (document.exitFullscreen) return document.exitFullscreen();
      if (document.webkitExitFullscreen)
        return Promise.resolve(document.webkitExitFullscreen());
    } catch(e){}
    return Promise.resolve();
  }

  // Panel tam ekranini ac/kapa
  function panelTamEkranCevir(i){
    if (tamPanelIdx === i){ panelTamEkranKapat(); return; }
    // Baska bir panel tam ekransa once onu birak
    if (tamPanelIdx >= 0) panelTamEkranKapat(true);
    const p = paneller[i];
    if (!p) return;
    tamPanelIdx = i;
    p.kok.classList.add("fw-panel-tam");
    document.body.classList.add("fw-panel-tam-acik");
    tamIste(p.kok).catch(() => {
      // API reddetti: CSS tabanli sahte tam ekran yeterli.
      sahteTam = true;
    });
    tamEkranTazele();
  }

  function panelTamEkranKapat(sessiz){
    if (tamPanelIdx < 0) return;
    const p = paneller[tamPanelIdx];
    if (p) p.kok.classList.remove("fw-panel-tam");
    tamPanelIdx = -1;
    document.body.classList.remove("fw-panel-tam-acik");
    if (!sessiz && tamEkranAktif()) tamCik();
    sahteTam = false;
    tamEkranTazele();
  }

  // Sayfa tam ekranini ac/kapa
  function sayfaTamEkranCevir(){
    if (tamPanelIdx >= 0){ panelTamEkranKapat(); return; }
    if (tamEkranAktif() || sahteTam){
      sahteTam = false;
      document.body.classList.remove("fw-sayfa-tam");
      tamCik();
      tamEkranTazele();
      return;
    }
    tamIste(document.documentElement).catch(() => {
      // Tarayici reddetti: en azindan ust serit gizlenip izgara
      // tum alani kaplasin (kiosk/iframe durumlari).
      sahteTam = true;
      document.body.classList.add("fw-sayfa-tam");
      tamEkranTazele();
    });
    tamEkranTazele();
  }

  // Dugme ikonlarini ve ipuclarini duruma gore tazeler
  function tamEkranTazele(){
    const acik = tamEkranAktif() || sahteTam;
    const btn = document.getElementById("fwTamEkran");
    if (btn){
      const sayfaAcik = acik && tamPanelIdx < 0;
      btn.classList.toggle("fw-tam-aktif", sayfaAcik);
      btn.title = sayfaAcik
        ? S("ucusTamEkranCik", "Tam ekrandan \u00e7\u0131k (Esc)")
        : S("ucusTamEkran", "Tam ekran (F)");
    }
    paneller.forEach((p, i) => {
      if (!p.tam) return;
      const bu = (tamPanelIdx === i);
      p.tam.classList.toggle("fw-tam-aktif", bu);
      p.tam.title = bu
        ? S("ucusPanelTamCik", "Panel tam ekran\u0131ndan \u00e7\u0131k")
        : S("ucusPanelTamEkran", "Bu paneli tam ekran yap");
    });
  }

  const btnTam = document.getElementById("fwTamEkran");
  if (btnTam) btnTam.addEventListener("click", sayfaTamEkranCevir);

  // Tarayici Esc ile ciktiginda (ya da baska sekilde durum degistiginde)
  // sinifiar ve ikonlar senkron kalmali.
  ["fullscreenchange", "webkitfullscreenchange"].forEach(ad => {
    document.addEventListener(ad, () => {
      if (!tamEkranAktif() && !sahteTam){
        if (tamPanelIdx >= 0) panelTamEkranKapat(true);
        document.body.classList.remove("fw-sayfa-tam");
      }
      tamEkranTazele();
    });
  });

  // Klavye kisayollari: F sayfa, 1-6 o paneli tam ekran, Esc cikis.
  // Combobox'ta yazarken kisayol tetiklenmemeli.
  document.addEventListener("keydown", (ev) => {
    const hedef = ev.target;
    if (hedef && (hedef.tagName === "SELECT" ||
                  hedef.tagName === "INPUT" ||
                  hedef.tagName === "TEXTAREA")) return;
    if (ev.ctrlKey || ev.altKey || ev.metaKey) return;
    const k = ev.key;
    if (k === "f" || k === "F"){
      ev.preventDefault();
      sayfaTamEkranCevir();
    } else if (k === "Escape"){
      if (tamPanelIdx >= 0) panelTamEkranKapat();
      else if (sahteTam){
        sahteTam = false;
        document.body.classList.remove("fw-sayfa-tam");
        tamEkranTazele();
      }
    } else if (k >= "1" && k <= "6"){
      const i = parseInt(k, 10) - 1;
      // Yalniz o an GORUNEN panel tam ekran yapilabilir; gizli panelin
      // tam ekrana gelmesi kullaniciya bos kutu gosterirdi.
      if (i < yerlesim){
        ev.preventDefault();
        panelTamEkranCevir(i);
      }
    }
  });

  // -----------------------------------------------------------------
  // Yerlesim
  // -----------------------------------------------------------------
  function yerlesimUygula(n){
    // v2.4.45: yerlesim degisiminde panel tam ekrani birakilir; aksi
    // halde gizlenen bir panel tam ekranda kalabilir.
    if (tamPanelIdx >= 0 && tamPanelIdx >= n) panelTamEkranKapat();
    yerlesim = n;
    izgara.className = "fw-yer-" + n;
    // Fazla paneller CSS ile gizlenir (display:none), ancak secimleri
    // korunur; kullanici yerlesimi buyutunce eski secim geri gelir.
    document.querySelectorAll(".fw-yb").forEach(b => {
      b.classList.toggle("fw-yb-aktif",
                         b.dataset.yer === String(n));
    });
    ayarKaydet();
  }

  document.getElementById("fwYerlesimler")
    .addEventListener("click", (ev) => {
      const b = ev.target.closest(".fw-yb");
      if (!b) return;
      yerlesimUygula(parseInt(b.dataset.yer, 10));
    });

  // -----------------------------------------------------------------
  // Dron listesi (combobox)
  // -----------------------------------------------------------------
  function dronAdi(d){
    return (d.kullanici_isim || d.isim
            || ("DRON-" + d.sysid)).toString();
  }

  // Listeyi yalnizca degistiginde yeniden kur.
  // Her telemetride kurulursa kullanici combobox'i acik tutamaz:
  // liste yenilenince acilir menu kapanir.
  let sonListeImza = "";

  function listeleriTazele(){
    const dizi = Array.from(dronlar.values());
    dizi.sort((a, b) => sayi(a.sysid) - sayi(b.sysid));

    const imza = dizi.map(d => d.sysid + ":" + dronAdi(d)
                          + ":" + (d.baglanti ? 1 : 0)).join("|");
    if (imza === sonListeImza) return;
    sonListeImza = imza;

    elDronSayi.textContent = dizi.filter(d => d.baglanti).length
                             + " " + S("ucusDronSayi", "DRON");

    paneller.forEach((p, i) => {
      const mevcut = secimler[i];
      p.secim.innerHTML = "";

      const bos = document.createElement("option");
      bos.value = "";
      bos.textContent = S("ucusDronSec", "— dron seç —");
      p.secim.appendChild(bos);

      dizi.forEach(d => {
        const o = document.createElement("option");
        o.value = String(d.sysid);
        o.textContent = (d.baglanti ? "" : "\u25CB ") + dronAdi(d);
        p.secim.appendChild(o);
      });

      // Secim listede yoksa (dron dustu) secimi koru ama gosterme:
      // dron geri gelince kendiliginden eslesir.
      p.secim.value = dizi.some(d => String(d.sysid) === mevcut)
                      ? mevcut : "";
    });
  }

  function sayi(v){
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  }

  // -----------------------------------------------------------------
  // Cizim dongusu
  // -----------------------------------------------------------------
  // Yalnizca gorunur panelleri cizer. Yerlesim 1 ise 1 panel cizilir;
  // gizli panelleri cizmek bosa GPU/CPU yukudur.
  function cizKare(){
    for (let i = 0; i < 6; i++){
      if (i >= yerlesim) continue;
      const p = paneller[i];
      const sid = secimler[i];
      const d = sid ? dronlar.get(String(sid)) : null;
      p.ad.textContent = d ? dronAdi(d) : "";
      p.kok.classList.toggle("fw-p-kopuk", !!d && !d.baglanti);
      try {
        window.PFD.ciz(p.canvas, d || null);
      } catch(e){
        // Tek panelin cizim hatasi diger panelleri durdurmasin
      }
    }
  }

  function dongu(){
    cizKare();
    requestAnimationFrame(dongu);
  }

  // -----------------------------------------------------------------
  // WebSocket
  // -----------------------------------------------------------------
  // v2.4.34: son durum saklanir; dil degisince ayni durum yeni dilde
  // yeniden yazilabilsin (aksi halde WS olayi beklemek gerekirdi).
  let sonDurumKod = "baglaniyor";
  let sonDurumPort = 0;

  function wsDurumYaz(kod, sinif, port){
    sonDurumKod = kod;
    if (port) sonDurumPort = port;
    let metin;
    if (kod === "bagli"){
      metin = S("ucusBagli", "BA\u011eLI") + " :" + sonDurumPort;
    } else if (kod === "kopuk"){
      metin = S("ucusKopuk", "KOPUK");
    } else {
      metin = S("ucusBaglaniyor", "BA\u011eLANIYOR");
    }
    elWsDurum.textContent = metin;
    elWsDurum.className = "fw-ws " + sinif;
  }

  let sonDurumSinif = "fw-ws-kopuk";

  function wsBaglan(){
    const port = WS_PORTLAR[wsPortIdx];
    const host = location.hostname || "localhost";
    try {
      if (/\.manus\.computer$/.test(host)){
        ws = new WebSocket("wss://" + host.replace(/^\d+-/, "8765-"));
      } else if (location.pathname.indexOf("/app/") === 0
                 || /^app\./i.test(host)){
        // IS-WSTUNEL: bkz. js/ws.js ayni dal.  Konak temelli
        // secim, alt alan adi uzerinden gelen sayfayi da dogru
        // tunele baglar.
        // MERKEZ KIPI (v2.4.57): sayfa /app/ altindan geldi. Ucus
        // duvari, ana arayuzle AYNI yolu kullanir: 443 uzerindeki
        // /app/ws tuneli. Bu dal olmadan sayfa 9443'e baglanmaya
        // calisiyordu; merkez o portu kopru protokolu icin ayirdigi
        // icin arayuz vekili yaniti gelmiyor ve ucus duvari surekli
        // "KOPUK" kaliyordu (olculen vaka). Bkz. js/ws.js ayni dal.
        const sema = location.protocol === "https:" ? "wss://" : "ws://";
        ws = new WebSocket(sema + location.host + "/app/ws");
      } else if (location.protocol === "https:"){
        // IS-WSTUNEL: arayuz vekili yolu zorunlu (bkz. ws.js).
        ws = new WebSocket("wss://" + host + ":" + WSS_PORT
                           + "/app/ws");
      } else {
        ws = new WebSocket("ws://" + host + ":" + port);
      }
    } catch(err){
      sonDurumSinif = "fw-ws-kopuk";
      wsDurumYaz("kopuk", sonDurumSinif);
      setTimeout(wsBaglan, 3000);
      return;
    }

    ws.onopen = () => {
      hicBaglanmadi = false;
      sonDurumSinif = "fw-ws-bagli";
      wsDurumYaz("bagli", sonDurumSinif, port);
    };

    ws.onclose = () => {
      sonDurumSinif = "fw-ws-kopuk";
      wsDurumYaz("kopuk", sonDurumSinif);
      if (hicBaglanmadi)
        wsPortIdx = (wsPortIdx + 1) % WS_PORTLAR.length;
      setTimeout(wsBaglan, hicBaglanmadi ? 500 : 2000);
    };

    ws.onerror = () => { try { ws.close(); } catch(e){} };
    // FAZ18-IS25: tema dugmesi IIFE disinda tanimli oldugu icin
    // etkin baglantiya erisebilmeli. Yalniz OKUMA amacli acilir.
    window.fwWs = ws;

    // -----------------------------------------------------------
    // FAZ18-IS25: TEMA (gece / gunduz)
    // Desen video_duvar.js:14-19 ile AYNI. Tema `data-tema` niteligi
    // uzerinden uygulanir; CSS degiskenleri flight.css'te tanimli.
    // PFD canvas'i (flight_pfd.js) kendi renk paletini tasir ve
    // TEMADAN ETKILENMEZ - mavi gok / kahve yer / beyaz ufuk ucus
    // gostergesi standardidir, acik zeminde okunamaz.
    // -----------------------------------------------------------
    function fwTemaUygula(tema) {
      const acik = (tema === "acik");
      if (acik) document.documentElement.setAttribute("data-tema", "acik");
      else      document.documentElement.removeAttribute("data-tema");
      const b = document.getElementById("fwTema");
      if (b) b.classList.toggle("fw-tema-acik", acik);
    }
    window.fwTemaUygula = fwTemaUygula;

    ws.onmessage = (ev) => {
      let m;
      try { m = JSON.parse(ev.data); } catch(e){ return; }
      // FAZ18-IS25: telemetri EN SIK gelen mesaj; sicak yol
      // bozulmasin diye once o islenir, sonra digerleri.
      if (m.tip === "ayarlar") {
        // Tema sunucu tarafi kullanici ayarindan gelir (ana sistemle
        // AYNI kaynak). Onceki surumde bu mesaj erken donusle
        // atiliyordu; Ucus Duvari bu yuzden temayi hic okumuyordu.
        if (m.ayarlar && m.ayarlar.tema) fwTemaUygula(m.ayarlar.tema);
        return;
      }
      if (m.tip !== "telemetri") return;
      const liste = m.dronlar || [];
      const yeni = new Map();
      liste.forEach(d => {
        if (d && d.sysid !== undefined)
          yeni.set(String(d.sysid), d);
      });
      dronlar = yeni;
      listeleriTazele();
    };
  }

  // -----------------------------------------------------------------
  // Baslat
  // -----------------------------------------------------------------
  // -----------------------------------------------------------------
  // v2.4.34: DIL TAZELEME KANCASI
  // -----------------------------------------------------------------
  // applyLanguage() bu fonksiyonu cagirir. JS ile uretilen metinler
  // (panel secim listeleri, dron sayaci, WS durumu) `data-i18n`
  // dongusunun ulasmadigi yerlerdir; burada elle tazelenirler.
  window.ucusDilTazele = function(){
    try {
      paneller.forEach(p => {
        p.secim.title = S("ucusPanelIpucu", "Bu panelde g\u00f6sterilecek dron");
      });
      // Liste imzasini sifirla: aksi halde listeleriTazele() "degismedi"
      // diyip cikar ve "\u2014 dron se\u00e7 \u2014" eski dilde kalir.
      sonListeImza = "";
      listeleriTazele();
      wsDurumYaz(sonDurumKod, sonDurumSinif);
      // v2.4.45: tam ekran dugmelerinin ipuclari da JS ile yazilir.
      tamEkranTazele();
    } catch(e){}
  };

  ayarYukle();
  panelleriKur();
  tamEkranTazele();
  yerlesimUygula(yerlesim);
  listeleriTazele();
  wsBaglan();
  requestAnimationFrame(dongu);
})();

// FAZ18-IS25: tema dugmesi. Tercih sunucuya gonderilir
// ({tip:"tema"}) - tema.js:47-49 ile AYNI mesaj bicimi. Boylece
// tercih oturuma yazilir ve kullanici hangi panele girerse girsin
// ayni temayi gorur. Ucus Duvari bu surume kadar YALNIZ DINLEYICI
// idi (ws.send hic kullanilmiyordu); readyState denetimi zorunlu.
(function () {
  const btn = document.getElementById("fwTema");
  if (!btn) return;
  btn.addEventListener("click", () => {
    const suAn = document.documentElement.getAttribute("data-tema");
    const yeni = (suAn === "acik") ? "koyu" : "acik";
    // Once yerel uygula (aninda geri bildirim), sonra sunucuya bildir.
    if (typeof window.fwTemaUygula === "function") window.fwTemaUygula(yeni);
    try {
      const s = window.fwWs;
      if (s && s.readyState === 1)
        s.send(JSON.stringify({ tip: "tema", tema: yeni }));
    } catch (e) {
      // Baglanti yoksa tercih yalniz bu sekmede gecerli olur;
      // sonraki baglantida sunucudaki kayitli tema geri gelir.
      console.warn("[UCUS] tema gonderilemedi:", e);
    }
  });
})();
