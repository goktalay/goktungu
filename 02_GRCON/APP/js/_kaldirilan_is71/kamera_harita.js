// =================================================================
// GOKTUNGU v2.4.1 - HARITADA LOKASYON + KAMERA IKONLARI
// - Kayitli lokasyonlar haritada bina ikonu olarak gosterilir;
//   ikonun sag ustunde bagli kamera SAYISI rozeti bulunur.
// - Lokasyon ikonuna tiklaninca o lokasyona bagli kameralarin
//   listelendigi tasinabilir bir popup (lokasyon kameralari) acilir.
// - Kamera ikonlari lokasyon cevresine dizilir; tiklaninca kucuk
//   MJPEG onizleme penceresi acilir (v2.4.0 davranisi korunur).
// =================================================================
(function(){
  "use strict";

  let varliklar = [];          // Cesium entity listesi
  let sonKameralar = [];       // son kamera listesi
  let onizlemePencere = null;  // acik onizleme popup kaydi {kok, img, kamId}
  let lokKamPencere = null;    // acik lokasyon kameralari popup'i {kok, lokId}

  function T(){ return (typeof D === "function") ? D() : {}; }

  function proxyUrl(id){
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

  function wsGonder(obj){
    if (typeof ws !== "undefined" && ws && ws.readyState === 1)
      ws.send(JSON.stringify(obj));
  }

  // Kamera ikonu (SVG data-uri billboard) — tema bagimsiz koyu rozet
  const KAM_IKON =
    "data:image/svg+xml;base64," + btoa(
      '<svg xmlns="http://www.w3.org/2000/svg" width="36" height="36">' +
      '<circle cx="18" cy="18" r="15" fill="#101820" stroke="#35d0ff"' +
      ' stroke-width="2"/>' +
      '<path fill="#35d0ff" d="M9 13.5h12a1.5 1.5 0 0 1 1.5 1.5v6a1.5 1.5' +
      ' 0 0 1-1.5 1.5H9A1.5 1.5 0 0 1 7.5 21v-6A1.5 1.5 0 0 1 9 13.5zm18' +
      ' 2.2v4.6l-4-1.6v-1.4z"/></svg>');

  // Lokasyon (bina) ikonu — kamera sayisi rozetiyle dinamik SVG.
  // Sayiya gore onbellege alinir (ayni sayi ayni data-uri).
  const lokIkonOnbellek = {};
  function lokIkon(kamSayi){
    const k = String(kamSayi || 0);
    if (lokIkonOnbellek[k]) return lokIkonOnbellek[k];
    const rozet = kamSayi > 0
      ? '<circle cx="34" cy="10" r="9" fill="#e03131" stroke="#fff"' +
        ' stroke-width="1.5"/>' +
        '<text x="34" y="13.5" font-family="Consolas,monospace"' +
        ' font-size="11" font-weight="bold" fill="#fff"' +
        ' text-anchor="middle">' + k + '</text>'
      : "";
    const svg =
      '<svg xmlns="http://www.w3.org/2000/svg" width="46" height="46">' +
      '<circle cx="21" cy="24" r="16" fill="#101820" stroke="#ffb020"' +
      ' stroke-width="2"/>' +
      // bina simgesi
      '<path fill="#ffb020" d="M14 31v-11l7-4.5 7 4.5v11h-4.6v-5.4h-4.8V31z"/>' +
      rozet + '</svg>';
    const uri = "data:image/svg+xml;base64," +
      btoa(unescape(encodeURIComponent(svg)));
    lokIkonOnbellek[k] = uri;
    return uri;
  }

  function temizle(){
    if (typeof viewer === "undefined" || !viewer) return;
    varliklar.forEach(e => { try { viewer.entities.remove(e); } catch(_){} });
    varliklar = [];
  }

  // Ayni lokasyondaki kameralari lokasyon cevresine dagit
  function ofset(lat, lon, sira, toplam){
    const r = 0.00022;                       // ~24 m
    const a = (2 * Math.PI * sira) / Math.max(toplam, 1);
    return [lat + r * Math.cos(a), lon + r * Math.sin(a)];
  }

  function ciz(){
    if (typeof viewer === "undefined" || !viewer){
      setTimeout(ciz, 800); return;
    }
    temizle();
    const lokListe = window._lokasyonlarSon || [];
    const lokIndex = {};
    lokListe.forEach(l => { lokIndex[l.id] = l; });
    // lokasyona bagli kameralari grupla
    const gruplar = {};
    sonKameralar.forEach(k => {
      if (!k.lokasyon_id || !lokIndex[k.lokasyon_id]) return;
      (gruplar[k.lokasyon_id] = gruplar[k.lokasyon_id] || []).push(k);
    });

    // --- LOKASYON IKONLARI (kamera sayisi rozetli) ---
    lokListe.forEach(l => {
      const kamSayi = (gruplar[l.id] || []).length;
      const ent = viewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(l.lon, l.lat),
        billboard: {
          image: lokIkon(kamSayi),
          width: 40, height: 40,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
          verticalOrigin: Cesium.VerticalOrigin.CENTER,
        },
        label: {
          text: l.ad || ("Lokasyon " + l.id),
          font: "11px Consolas, monospace",
          fillColor: Cesium.Color.fromCssColorString("#ffb020"),
          showBackground: true,
          backgroundColor:
            Cesium.Color.fromCssColorString("#101820").withAlpha(0.85),
          pixelOffset: new Cesium.Cartesian2(0, -30),
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      });
      ent._goktunguLokasyonId = l.id;
      varliklar.push(ent);
    });

    // v2.4.5: Haritada ayrik KAMERA ikonlari cizilmez — yalnizca
    // lokasyon (bina) ikonu gosterilir; kameralara lokasyon ikonuna
    // tiklaninca acilan popup'tan erisilir.

    // Acik lokasyon kameralari popup'i varsa listeyi tazele
    if (lokKamPencere) lokKamListeDoldur(lokKamPencere.lokId);
  }

  // ---------------------------------------------------------------
  // ONIZLEME POPUP'I
  // ---------------------------------------------------------------
  function onizlemeKapat(){
    if (!onizlemePencere) return;
    const kamera = sonKameralar.find(k => k.id === onizlemePencere.kamId);
    // proxy gerektiren protokollerde sunucu surecini serbest birak
    if (kamera && (kamera.protokol === "rtsp" || kamera.protokol === "rtp" ||
                   kamera.protokol === "dji")){
      wsGonder({ tip: "kamera_proxy_durdur", id: kamera.id });
    }
    try { onizlemePencere.kok.remove(); } catch(_){}
    onizlemePencere = null;
  }
  window.kameraOnizlemeKapat = onizlemeKapat;

  function onizlemeAc(kamera, ekranX, ekranY){
    const t = T();
    // ayni kameraya tekrar tiklanirsa kapat (toggle)
    if (onizlemePencere && onizlemePencere.kamId === kamera.id){
      onizlemeKapat(); return;
    }
    onizlemeKapat();

    const kok = document.createElement("div");
    kok.className = "kam-oniz-popup";

    const baslik = document.createElement("div");
    baslik.className = "kam-oniz-baslik";
    const ad = document.createElement("span");
    ad.innerHTML = "<i class='fa-solid fa-video'></i> " +
      (kamera.isim || ("Kamera " + kamera.id));
    const btnKapat = document.createElement("button");
    btnKapat.title = t.btnKapat || "Kapat";
    btnKapat.innerHTML = "<i class='fa-solid fa-xmark'></i>";
    btnKapat.addEventListener("click", (e) => {
      e.stopPropagation(); onizlemeKapat();
    });
    baslik.append(ad, btnKapat);

    const kutu = document.createElement("div");
    kutu.className = "kam-oniz-video";

    let medya;
    const prot = kamera.protokol;
    if (prot === "rtsp" || prot === "rtp" || prot === "mjpeg" ||
        prot === "dji" || prot === "donanim" || prot === "http"){
      // v2.4.7: hepsi sunucu proxy'sinden (anotasyonlu MJPEG)
      // v2.4.10: http (MP4/WebM) da proxy'den - AI anotasyonlu
      medya = document.createElement("img");
      medya.draggable = false;
      // v2.4.33: dayanikli yukleme (artan gecikmeli yeniden deneme).
      // Kaynak atamasi mjpegBagla icinde yapilir. Onceki halde tek bir
      // basarisiz istek kutuyu kalici hata durumuna dusuruyordu.
      if (typeof window.mjpegBagla === "function") {
        window.mjpegBagla(medya, () => proxyUrl(kamera.id), ".kam-oniz-video");
      } else {
        medya.src = proxyUrl(kamera.id);
      }
    } else {
      medya = document.createElement("video");
      medya.autoplay = true; medya.muted = true; medya.playsInline = true;
      if (prot === "hls" && window.Hls && Hls.isSupported()){
        const h = new Hls({ lowLatencyMode: true });
        h.loadSource(kamera.url); h.attachMedia(medya);
      } else {
        medya.src = kamera.url;
      }
    }
    medya.className = "kam-oniz-medya";
    medya.addEventListener("error", () => kutu.classList.add("kam-hata"));
    kutu.appendChild(medya);

    kok.append(baslik, kutu);
    document.body.appendChild(kok);

    // Konum: tiklanan noktaya yakin, ekran disina tasma
    const W = 280, H = 210;
    let x = ekranX + 14, y = ekranY - H - 10;
    if (x + W > window.innerWidth - 8) x = ekranX - W - 14;
    if (y < 50) y = ekranY + 14;
    if (y + H > window.innerHeight - 8) y = window.innerHeight - H - 8;
    kok.style.left = Math.max(8, x) + "px";
    kok.style.top = Math.max(50, y) + "px";

    onizlemePencere = { kok: kok, img: medya, kamId: kamera.id };
  }

  // ---------------------------------------------------------------
  // LOKASYON KAMERALARI POPUP'I
  // ---------------------------------------------------------------
  function lokKamKapat(){
    if (!lokKamPencere) return;
    lokKamTumMedyaTemizle();
    try { lokKamPencere.kok.remove(); } catch(_){}
    lokKamPencere = null;
  }
  window.lokasyonKameraKapat = lokKamKapat;

  // v2.4.5: popup icinde gomulu oynatma durumu (kamId -> true)
  let lokKamOynayan = {};
  const lokKamDonanimStream = {};
  const lokKamHls = {};

  function lokKamMedyaOlustur(k){
    // kameralar.js panelindeki kanitlanmis oynatma kalibi
    const prot = k.protokol;
    // v2.4.7: donanim + mjpeg dahil tum MJPEG kaynaklari sunucu
    // proxy'sinden gelir (AI aktifse tespit cerceveli anotasyonlu kare)
    if (prot === "rtsp" || prot === "rtp" || prot === "mjpeg" ||
        prot === "dji" || prot === "donanim" || prot === "http"){
      const img = document.createElement("img");
      img.className = "lok-kam-medya";
      img.draggable = false;
      // v2.4.33: dayanikli yukleme (bkz. BULGU_MJPEG.md)
      if (typeof window.mjpegBagla === "function") {
        window.mjpegBagla(img, () => proxyUrl(k.id), ".lok-kam-video-kutu");
      } else {
        img.src = proxyUrl(k.id);
        img.addEventListener("error", () => {
          img.closest(".lok-kam-video-kutu")?.classList.add("kam-hata");
        });
        img.addEventListener("load", () => {
          img.closest(".lok-kam-video-kutu")?.classList.remove("kam-hata");
        });
      }
      return img;
    }
    const video = document.createElement("video");
    video.className = "lok-kam-medya";
    video.autoplay = true; video.muted = true; video.playsInline = true;
    if (prot === "hls"){
      if (window.Hls && Hls.isSupported()){
        const h = new Hls({ lowLatencyMode: true });
        h.loadSource(k.url); h.attachMedia(video);
        lokKamHls[k.id] = h;
      } else video.src = k.url;
    } else { video.src = k.url; video.loop = true; }
    video.addEventListener("error", () => {
      video.closest(".lok-kam-video-kutu")?.classList.add("kam-hata");
    });
    setTimeout(() => { if (video.paused) video.play().catch(() => {}); }, 300);
    return video;
  }

  function lokKamMedyaTemizle(kamId){
    if (lokKamHls[kamId]){
      try { lokKamHls[kamId].destroy(); } catch(_){}
      delete lokKamHls[kamId];
    }
    if (lokKamDonanimStream[kamId]){
      try { lokKamDonanimStream[kamId].getTracks().forEach(t => t.stop()); }
      catch(_){}
      delete lokKamDonanimStream[kamId];
    }
    const k = sonKameralar.find(x => x.id === kamId);
    if (k && (k.protokol === "rtsp" || k.protokol === "rtp" ||
              k.protokol === "dji" || k.protokol === "mjpeg" ||
              k.protokol === "donanim")){
      // ayni kamera baska yerde oynamiyorsa sunucu surecini birak
      const baskaOynayan =
        (onizlemePencere && onizlemePencere.kamId === kamId);
      if (!baskaOynayan) wsGonder({ tip: "kamera_proxy_durdur", id: kamId });
    }
  }

  function lokKamTumMedyaTemizle(){
    Object.keys(lokKamOynayan).forEach(id => lokKamMedyaTemizle(+id));
    lokKamOynayan = {};
  }

  function lokKamListeDoldur(lokId){
    if (!lokKamPencere || lokKamPencere.lokId !== lokId) return;
    const t = T();
    const govde = lokKamPencere.govde;
    govde.innerHTML = "";
    const kamlar = sonKameralar.filter(k => k.lokasyon_id === lokId);
    if (!kamlar.length){
      const bos = document.createElement("div");
      bos.className = "lok-kam-bos";
      bos.innerHTML = "<i class='fa-solid fa-video-slash'></i><span>" +
        (t.lokKamYok || "Bu lokasyona bağlı kamera yok") + "</span>";
      govde.appendChild(bos);
      return;
    }
    kamlar.forEach(k => {
      const sar = document.createElement("div");
      sar.className = "lok-kam-oge";
      const satir = document.createElement("div");
      satir.className = "lok-kam-satir";
      const ikon = document.createElement("i");
      ikon.className = "fa-solid fa-video";
      const bilgi = document.createElement("div");
      bilgi.className = "lok-kam-bilgi";
      const ad = document.createElement("div");
      ad.className = "lok-kam-ad";
      ad.textContent = k.isim || ("Kamera " + k.id);
      const alt = document.createElement("div");
      alt.className = "lok-kam-alt";
      alt.textContent = (k.protokol || "").toUpperCase();
      bilgi.append(ad, alt);
      // Gomulu izleme dugmesi (satira tiklama da ayni islev)
      const btn = document.createElement("button");
      btn.className = "lok-kam-izle";
      btn.title = t.lokKamOnizle || "İzle";
      btn.innerHTML = lokKamOynayan[k.id]
        ? "<i class='fa-solid fa-stop'></i>"
        : "<i class='fa-solid fa-play'></i>";
      // v2.4.5: istege bagli AYRI POPUP dugmesi
      const btnAyri = document.createElement("button");
      btnAyri.className = "lok-kam-izle lok-kam-ayri";
      btnAyri.title = t.lokKamAyriAc || "Ayrı pencerede aç";
      btnAyri.innerHTML = "<i class='fa-solid fa-up-right-from-square'></i>";
      btnAyri.addEventListener("click", (e) => {
        e.stopPropagation();
        const r = satir.getBoundingClientRect();
        onizlemeAc(k, r.right, r.top);
      });
      // v2.4.5: satira/izle dugmesine tiklayinca GOMULU oynat/durdur
      const gomuluToggle = (e) => {
        e.stopPropagation();
        if (lokKamOynayan[k.id]){
          delete lokKamOynayan[k.id];
          lokKamMedyaTemizle(k.id);
        } else {
          lokKamOynayan[k.id] = true;
        }
        lokKamListeDoldur(lokId);
      };
      btn.addEventListener("click", gomuluToggle);
      satir.addEventListener("click", gomuluToggle);
      satir.append(ikon, bilgi, btn, btnAyri);
      sar.appendChild(satir);
      // Oynuyorsa satirin altina gomulu video kutusu ekle
      if (lokKamOynayan[k.id]){
        const kutu = document.createElement("div");
        kutu.className = "lok-kam-video-kutu";
        kutu.appendChild(lokKamMedyaOlustur(k));
        sar.appendChild(kutu);
      }
      govde.appendChild(sar);
    });
  }

  function lokKamAc(lok, ekranX, ekranY){
    const t = T();
    // ayni lokasyona tekrar tiklanirsa kapat (toggle)
    if (lokKamPencere && lokKamPencere.lokId === lok.id){
      lokKamKapat(); return;
    }
    lokKamKapat();

    const kok = document.createElement("div");
    kok.className = "lok-kam-popup";

    const baslik = document.createElement("div");
    baslik.className = "popup-baslik";
    const ad = document.createElement("span");
    ad.innerHTML = "<i class='fa-solid fa-building'></i> " +
      (lok.ad || ("Lokasyon " + lok.id)) +
      " — " + (t.lokKamBaslik || "KAMERALAR");
    const btnKapat = document.createElement("button");
    btnKapat.className = "popup-kapat";
    btnKapat.title = t.btnKapat || "Kapat";
    btnKapat.innerHTML = "<i class='fa-solid fa-xmark'></i>";
    btnKapat.addEventListener("click", (e) => {
      e.stopPropagation(); lokKamKapat();
    });
    baslik.append(ad, btnKapat);

    const govde = document.createElement("div");
    govde.className = "lok-kam-govde";

    kok.append(baslik, govde);
    document.body.appendChild(kok);

    // Konum: tiklanan noktaya yakin, ekran disina tasmadan
    const W = 300, H = 240;
    let x = (ekranX || window.innerWidth / 2) + 14;
    let y = (ekranY || window.innerHeight / 2) - 20;
    if (x + W > window.innerWidth - 8) x = (ekranX || 0) - W - 14;
    if (y + H > window.innerHeight - 8) y = window.innerHeight - H - 8;
    kok.style.left = Math.max(8, x) + "px";
    kok.style.top = Math.max(50, y) + "px";

    if (window.popupTasinabilirYap)
      popupTasinabilirYap(kok, baslik, "pp_lokKam");

    lokKamPencere = { kok: kok, govde: govde, lokId: lok.id };
    lokKamListeDoldur(lok.id);
  }

  // lokasyonlar.js listesinden cagrilir (liste satirindaki kamera butonu)
  window.lokasyonKameralariAc = function(lokId, ekranX, ekranY){
    const lok = (window._lokasyonlarSon || []).find(l => l.id === lokId);
    if (lok) lokKamAc(lok, ekranX, ekranY);
  };

  // ---------------------------------------------------------------
  // HARITA TIKLAMASI (projenin kanitlanmis DOM click deseni)
  // ---------------------------------------------------------------
  function tikKur(){
    const kap = document.getElementById("cesiumContainer");
    if (!kap || typeof viewer === "undefined" || !viewer || !viewer.scene){
      setTimeout(tikKur, 600); return;
    }
    kap.addEventListener("click", (e) => {
      if (e.ctrlKey || e.altKey || e.shiftKey) return;
      if (typeof window.__cetvelAktif === "function" &&
          window.__cetvelAktif()) return;
      const r = kap.getBoundingClientRect();
      let secilen = null;
      try {
        secilen = viewer.scene.pick(
          new Cesium.Cartesian2(e.clientX - r.left, e.clientY - r.top));
      } catch(_){ return; }
      if (!secilen || !secilen.id) return;
      // Lokasyon ikonu -> lokasyon kameralari popup'i
      if (secilen.id._goktunguLokasyonId){
        const lok = (window._lokasyonlarSon || []).find(
          l => l.id === secilen.id._goktunguLokasyonId);
        if (lok) lokKamAc(lok, e.clientX, e.clientY);
        return;
      }
      // Kamera ikonu -> onizleme
      if (secilen.id._goktunguKameraId){
        const kamera = sonKameralar.find(
          k => k.id === secilen.id._goktunguKameraId);
        if (kamera) onizlemeAc(kamera, e.clientX, e.clientY);
      }
    });
  }
  tikKur();

  // ---------------------------------------------------------------
  // DIS API
  // ---------------------------------------------------------------
  // kameralar.js kameraListesiIsle'den cagirir
  window.kameraHaritaTazele = function(kameralar){
    sonKameralar = kameralar || [];
    ciz();
  };

  // lokasyon listesi degisince de tazele (lokasyonlar.js cagirir)
  window.kameraHaritaLokTazele = function(){
    ciz();
  };
})();
