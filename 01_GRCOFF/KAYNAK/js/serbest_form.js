// =================================================================
// GOKTUNGU - SERBEST FORM GOREV (v2.4.4)
// Ilaclama dronu icin cokgen alan uzerinde zigzag (boustrophedon)
// tarama rotasi ureten gorev tipi.
// Akis:
//   1) Rotalar > Serbest Form -> tasinabilir popup acilir
//      (gorev ismi, aralik mesafesi, ucus yonu/acisi, yukseklik, hiz)
//   2) OLUSTUR -> harita cizim moduna gecer; kullanici haritaya
//      tiklayarak cokgen kosesi ekler. 3. noktadan itibaren cokgen
//      olusur ve rota HER yeni noktada yeniden hesaplanir.
//   3) Popup KAPANMAZ; aralik/yon/yukseklik degisince rota canli
//      yeniden uretilir.
//   4) GOREVI SONLANDIR -> rota sunucuya kaydedilir, mod kapanir.
// Algoritma: cokgen, ucus yonune dik seritlerle dilimlenir; her
// seridin cokgenle kesisim parcalari sirayla (zigzag) gezilir.
// Bu dosya klasik script'tir; rotalar.js'ten SONRA yuklenmelidir.
// =================================================================
(function(){
  "use strict";
  function t(k){
    const d = (typeof D === "function") ? D() : {};
    return d[k] || k;
  }
  function konsol(m){
    if (typeof konsolYaz === "function") konsolYaz("SERBEST FORM", m);
    else console.log(m);
  }
  function wsGonder(m){
    if (typeof ws !== "undefined" && ws && ws.readyState === 1)
      ws.send(JSON.stringify(m));
  }

  // --- Durum ---
  let popupEl = null;        // parametre popup'i (surekli acik)
  let aktif = false;         // cizim modu aktif mi
  let koseler = [];          // cokgen koseleri [{lat, lon}]
  let rotaNoktalari = [];    // uretilen ilaclama rotasi
  let cizimler = [];         // Cesium entity'leri
  let duzenlenenId = null;   // v2.4.5: duzenlenen rota id (null=yeni)

  // ---------------------------------------------------------------
  // GEOMETRI: yerel duzlem (metre) donusumleri
  // ---------------------------------------------------------------
  const R_DUNYA = 6371000;
  const rad = Math.PI / 180;
  let ref = null;   // referans nokta {lat, lon}

  function xyYap(k){
    // ref etrafinda yerel ENU (dogu=x, kuzey=y) metre
    const x = (k.lon - ref.lon) * rad * R_DUNYA * Math.cos(ref.lat * rad);
    const y = (k.lat - ref.lat) * rad * R_DUNYA;
    return { x, y };
  }
  function koordYap(p){
    return {
      lat: ref.lat + (p.y / R_DUNYA) / rad,
      lon: ref.lon + (p.x / (R_DUNYA * Math.cos(ref.lat * rad))) / rad,
    };
  }

  // Cokgen ile yatay dogru kesisimi (donusturulmus uzayda)
  // Cokgen noktalar: [{x,y}], dogru: y = sabit
  // Donus: kesisen x degerleri (sirali)
  function yatayKesisim(poly, y){
    const xs = [];
    for (let i = 0; i < poly.length; i++){
      const a = poly[i], b = poly[(i + 1) % poly.length];
      if ((a.y <= y && b.y > y) || (b.y <= y && a.y > y)){
        const oran = (y - a.y) / (b.y - a.y);
        xs.push(a.x + oran * (b.x - a.x));
      }
    }
    xs.sort((p, q) => p - q);
    return xs;
  }

  // Zigzag rota uretimi:
  //  aralik: serit arasi mesafe (m), aci: ucus yonu (derece, 0=K, CW)
  //  Cokgen once -aci kadar dondurulur (seritler yatay olur),
  //  yatay seritler kesisimlerle dilimlenir, zigzag siralanir,
  //  sonra geri dondurulur.
  function zigzagUret(kseler, aralik, aciDeg){
    if (kseler.length < 3) return [];
    ref = kseler[0];
    const poly = kseler.map(xyYap);
    // Ucus yonu acisi: 0 = kuzey; seritler ucus yonunde uzanir.
    // Donusum: ucus yonu vektoru (sin a, cos a) -> +x eksenine dondur.
    const a = aciDeg * rad;
    // Ucus yonunu +x'e tasiyan donme acisi: atan2(cos a, sin a)... 
    // Basitce: nokta (x,y) -> (x', y') = R(-theta) uygulanir; theta,
    // ucus vektoru ile +x arasindaki aci.
    const theta = Math.atan2(Math.cos(a), Math.sin(a)); // ucus vektorunun +x'e acisi
    const ct = Math.cos(-theta), st = Math.sin(-theta);
    const don = poly.map(p => ({ x: p.x * ct - p.y * st,
                                 y: p.x * st + p.y * ct }));
    // Geri donusum
    const cg = Math.cos(theta), sg = Math.sin(theta);
    function geri(p){ return { x: p.x * cg - p.y * sg,
                               y: p.x * sg + p.y * cg }; }
    // y araligi
    let minY = Infinity, maxY = -Infinity;
    don.forEach(p => { minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y); });
    if (!isFinite(minY) || maxY - minY < 0.5) return [];
    const noktalar = [];
    let ters = false;
    // Ilk serit yarim aralik iceriden baslar (kenar bindirmesini dengeler)
    for (let y = minY + aralik / 2; y <= maxY; y += aralik){
      const xs = yatayKesisim(don, y);
      // Kesisim ciftleri: [x0,x1], [x2,x3], ...
      const parcalar = [];
      for (let i = 0; i + 1 < xs.length; i += 2)
        parcalar.push([xs[i], xs[i + 1]]);
      if (!parcalar.length) continue;
      if (ters) parcalar.reverse();
      parcalar.forEach(par => {
        let x0 = par[0], x1 = par[1];
        if (ters) { const tmp = x0; x0 = x1; x1 = tmp; }
        noktalar.push(geri({ x: x0, y }));
        noktalar.push(geri({ x: x1, y }));
      });
      ters = !ters;
    }
    return noktalar.map(koordYap);
  }

  // ---------------------------------------------------------------
  // HARITA CIZIMI
  // ---------------------------------------------------------------
  function cizimTemizle(){
    cizimler.forEach(e => { try { viewer.entities.remove(e); } catch(_){} });
    cizimler = [];
  }

  function ciz(){
    cizimTemizle();
    if (typeof viewer === "undefined" || !viewer) return;
    const yuk = popupEl ? parseFloat(popupEl.querySelector("#sfYukseklik").value) : 20;
    // Kose isaretcileri
    koseler.forEach((k, i) => {
      cizimler.push(viewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(k.lon, k.lat, 2),
        point: { pixelSize: 10,
                 color: Cesium.Color.fromCssColorString("#f59e0b"),
                 outlineColor: Cesium.Color.WHITE, outlineWidth: 2,
                 disableDepthTestDistance: Number.POSITIVE_INFINITY },
        // v2.4.64: rotalar.js F_NOKTA ile ayni boyut. Ayni haritada
        // iki farkli etiket boyutu dengesiz gorunur.
        label: { text: String(i + 1),
                 font: "700 13px Consolas, monospace",
                 fillColor: Cesium.Color.WHITE,
                 style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                 outlineColor: Cesium.Color.BLACK, outlineWidth: 4,
                 pixelOffset: new Cesium.Cartesian2(0, -18),
                 disableDepthTestDistance: Number.POSITIVE_INFINITY },
      }));
      const ent = cizimler[cizimler.length - 1];
      ent._sfKoseIdx = i;
    });
    // Cokgen dolgusu + kenar cizgisi
    if (koseler.length >= 3){
      const dizi = [];
      koseler.forEach(k => dizi.push(k.lon, k.lat));
      cizimler.push(viewer.entities.add({
        polygon: {
          hierarchy: Cesium.Cartesian3.fromDegreesArray(dizi),
          material: Cesium.Color.fromCssColorString("#22c55e").withAlpha(0.18),
          outline: false,
        }
      }));
      const kapali = dizi.concat([koseler[0].lon, koseler[0].lat]);
      cizimler.push(viewer.entities.add({
        polyline: {
          positions: Cesium.Cartesian3.fromDegreesArray(kapali),
          width: 2.5, clampToGround: true,
          material: Cesium.Color.fromCssColorString("#22c55e").withAlpha(0.9),
        }
      }));
    } else if (koseler.length === 2){
      cizimler.push(viewer.entities.add({
        polyline: {
          positions: Cesium.Cartesian3.fromDegreesArray(
            [koseler[0].lon, koseler[0].lat, koseler[1].lon, koseler[1].lat]),
          width: 2, clampToGround: true,
          material: Cesium.Color.fromCssColorString("#22c55e").withAlpha(0.7),
        }
      }));
    }
    // Ilaclama rotasi (zigzag)
    if (rotaNoktalari.length >= 2){
      const dizi3 = [];
      rotaNoktalari.forEach(n => dizi3.push(n.lon, n.lat, yuk));
      cizimler.push(viewer.entities.add({
        polyline: {
          positions: Cesium.Cartesian3.fromDegreesArrayHeights(dizi3),
          width: 3,
          material: new Cesium.PolylineDashMaterialProperty({
            color: Cesium.Color.fromCssColorString("#3b82f6"),
            dashLength: 12,
          }),
        }
      }));
      // Baslangic / bitis isaretcileri
      const b0 = rotaNoktalari[0], b1 = rotaNoktalari[rotaNoktalari.length - 1];
      cizimler.push(viewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(b0.lon, b0.lat, yuk),
        point: { pixelSize: 9, color: Cesium.Color.fromCssColorString("#16a34a"),
                 outlineColor: Cesium.Color.WHITE, outlineWidth: 2,
                 disableDepthTestDistance: Number.POSITIVE_INFINITY },
      }));
      cizimler.push(viewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(b1.lon, b1.lat, yuk),
        point: { pixelSize: 9, color: Cesium.Color.fromCssColorString("#dc2626"),
                 outlineColor: Cesium.Color.WHITE, outlineWidth: 2,
                 disableDepthTestDistance: Number.POSITIVE_INFINITY },
      }));
    }
  }

  // ---------------------------------------------------------------
  // ROTA HESABI + BILGI
  // ---------------------------------------------------------------
  function yenidenHesapla(){
    if (!popupEl) return;
    const aralik = parseFloat(popupEl.querySelector("#sfAralik").value);
    const aci = parseFloat(popupEl.querySelector("#sfYon").value);
    rotaNoktalari = (koseler.length >= 3)
      ? zigzagUret(koseler, Math.max(1, aralik), aci) : [];
    ciz();
    bilgiTazele();
  }

  function bilgiTazele(){
    if (!popupEl) return;
    const el = popupEl.querySelector("#sfBilgi");
    if (koseler.length < 3){
      el.textContent = t("sfBilgiBekliyor");
      return;
    }
    // Toplam rota uzunlugu
    let mesafe = 0;
    for (let i = 1; i < rotaNoktalari.length; i++){
      const a = rotaNoktalari[i - 1], b = rotaNoktalari[i];
      ref = koseler[0];
      const pa = xyYap(a), pb = xyYap(b);
      mesafe += Math.hypot(pb.x - pa.x, pb.y - pa.y);
    }
    // Alan (shoelace, yerel duzlem)
    ref = koseler[0];
    const poly = koseler.map(xyYap);
    let alan = 0;
    for (let i = 0; i < poly.length; i++){
      const a = poly[i], b = poly[(i + 1) % poly.length];
      alan += a.x * b.y - b.x * a.y;
    }
    alan = Math.abs(alan) / 2;
    const mMetin = (mesafe >= 1000)
      ? (mesafe / 1000).toFixed(2) + " km" : Math.round(mesafe) + " m";
    const aMetin = (alan >= 10000)
      ? (alan / 10000).toFixed(2) + " ha" : Math.round(alan) + " m²";
    el.textContent =
      t("sfBilgiKose") + ": " + koseler.length + "   " +
      t("sfBilgiNokta") + ": " + rotaNoktalari.length + "\n" +
      t("sfBilgiAlan") + ": " + aMetin + "   " +
      t("sfBilgiMesafe") + ": " + mMetin;
  }

  // ---------------------------------------------------------------
  // PARAMETRE POPUP'I (tasinabilir, cizim boyunca acik kalir)
  // ---------------------------------------------------------------
  function popupAc(){
    if (popupEl){ popupEl.remove(); popupEl = null; }
    popupEl = document.createElement("div");
    popupEl.className = "sf-popup";
    popupEl.innerHTML = `
      <div class="sf-baslik popup-baslik">
        <i class="fa-solid fa-draw-polygon"></i> <span>${t("sfBaslik")}</span>
        <button class="sf-kapat" title="${t("btnIptal")}"><i class="fa-solid fa-xmark"></i></button>
      </div>
      <div class="sf-icerik">
        <label class="sf-lbl" for="sfAd">${t("sfGorevAdi")}</label>
        <input type="text" id="sfAd" maxlength="60" spellcheck="false"
               placeholder="${t("sfGorevAdiIpucu")}">
        <div class="sf-slider-satir">
          <label><span>${t("sfAralik")}</span>
            <span class="sf-deger" id="sfAralikDeger">10 m</span></label>
          <input type="range" id="sfAralik" min="2" max="100" step="1" value="10">
        </div>
        <div class="sf-slider-satir">
          <label><span>${t("sfYon")}</span>
            <span class="sf-deger" id="sfYonDeger">0°</span></label>
          <input type="range" id="sfYon" min="0" max="359" step="1" value="0">
        </div>
        <div class="sf-slider-satir">
          <label><span>${t("sfYukseklik")}</span>
            <span class="sf-deger" id="sfYukseklikDeger">20 m</span></label>
          <input type="range" id="sfYukseklik" min="2" max="200" step="1" value="20">
        </div>
        <div class="sf-slider-satir">
          <label><span>${t("sfHiz")}</span>
            <span class="sf-deger" id="sfHizDeger">5.0 m/s</span></label>
          <input type="range" id="sfHiz" min="1" max="20" step="0.5" value="5">
        </div>
        <div class="sf-bilgi" id="sfBilgi"></div>
        <div class="sf-hata" id="sfHata"></div>
        <button class="sf-btn sf-btn-olustur" id="sfOlusturBtn">
          <i class="fa-solid fa-pen"></i><span>${t("sfOlustur")}
        </span></button>
        <div class="sf-cizim-butonlar" id="sfCizimButonlar" style="display:none">
          <button class="sf-btn sf-btn-geri" id="sfGeriAlBtn">
            <i class="fa-solid fa-rotate-left"></i><span>${t("sfGeriAl")}
          </span></button>
          <button class="sf-btn sf-btn-bitir" id="sfBitirBtn">
            <i class="fa-solid fa-flag-checkered"></i><span>${t("sfBitir")}
          </span></button>
        </div>
      </div>`;
    document.body.appendChild(popupEl);

    const baslik = popupEl.querySelector(".sf-baslik");
    if (typeof popupTasinabilirYap === "function")
      popupTasinabilirYap(popupEl, baslik, "serbestForm");

    // Kapat: cizimi iptal eder
    baslik.querySelector(".sf-kapat").addEventListener("click", iptalEt);

    // Slider etiketleri + canli yeniden hesap
    const inpAralik = popupEl.querySelector("#sfAralik");
    const inpYon = popupEl.querySelector("#sfYon");
    const inpYuk = popupEl.querySelector("#sfYukseklik");
    const inpHiz = popupEl.querySelector("#sfHiz");
    function etiketTazele(){
      popupEl.querySelector("#sfAralikDeger").textContent = inpAralik.value + " m";
      popupEl.querySelector("#sfYonDeger").textContent = inpYon.value + "°";
      popupEl.querySelector("#sfYukseklikDeger").textContent = inpYuk.value + " m";
      popupEl.querySelector("#sfHizDeger").textContent =
        parseFloat(inpHiz.value).toFixed(1) + " m/s";
    }
    [inpAralik, inpYon, inpYuk, inpHiz].forEach(el =>
      el.addEventListener("input", () => { etiketTazele(); if (aktif) yenidenHesapla(); }));
    etiketTazele();

    // OLUSTUR: cizim modunu baslat
    popupEl.querySelector("#sfOlusturBtn").addEventListener("click", () => {
      const isim = popupEl.querySelector("#sfAd").value.trim();
      if (!isim){
        popupEl.querySelector("#sfHata").textContent = t("rotaHataAd");
        return;
      }
      popupEl.querySelector("#sfHata").textContent = "";
      cizimBaslat();
    });

    duzenlenenId = null;

    // GERI AL: son koseyi kaldir
    popupEl.querySelector("#sfGeriAlBtn").addEventListener("click", () => {
      if (!koseler.length) return;
      koseler.pop();
      yenidenHesapla();
    });

    // GOREVI SONLANDIR: kaydet
    popupEl.querySelector("#sfBitirBtn").addEventListener("click", kaydet);

    popupEl.querySelector("#sfBilgi").textContent = t("sfBilgiIlk");
  }

  // ---------------------------------------------------------------
  // CIZIM MODU
  // ---------------------------------------------------------------
  function cizimBaslat(){
    aktif = true;
    koseler = [];
    rotaNoktalari = [];
    popupEl.querySelector("#sfOlusturBtn").style.display = "none";
    popupEl.querySelector("#sfCizimButonlar").style.display = "";
    popupEl.querySelector("#sfAd").disabled = true;
    popupEl.querySelector("#sfBilgi").textContent = t("sfBilgiBekliyor");
    const kap = document.getElementById("cesiumContainer");
    if (kap) kap.style.cursor = "crosshair";
    konsol(t("sfKonsolBaslat"));
  }

  function haritaTikla(e){
    if (!aktif) return false;
    const kap = document.getElementById("cesiumContainer");
    const r = kap.getBoundingClientRect();
    const k = (typeof window.__ekrandanKoordinat === "function")
      ? window.__ekrandanKoordinat(e.clientX - r.left, e.clientY - r.top)
      : null;
    if (!k) return true;
    koseler.push({ lat: k.lat, lon: k.lon });
    yenidenHesapla();
    return true;
  }

  // Harita tiklama: rotalar.js'in click handler'i "duzenleme" modunda
  // degilken calismaz; serbest form kendi capture dinleyicisini kurar.
  function tikKur(){
    const kap = document.getElementById("cesiumContainer");
    if (!kap){ setTimeout(tikKur, 500); return; }
    kap.addEventListener("click", (e) => {
      if (!aktif) return;
      if (e.altKey || e.ctrlKey) return;   // konum kaydet / dron menu
      // Rota duzenleme moduyla cakismayi onle
      if (typeof window.__rotaDuzenlemeAktif === "function" &&
          window.__rotaDuzenlemeAktif()) return;
      e.preventDefault(); e.stopPropagation();
      haritaTikla(e);
    }, true);
  }
  tikKur();

  // ---------------------------------------------------------------
  // KAYDET / IPTAL
  // ---------------------------------------------------------------
  function kaydet(){
    if (koseler.length < 3 || rotaNoktalari.length < 2){
      popupEl.querySelector("#sfHata").textContent = t("sfHataNokta");
      return;
    }
    const isim = popupEl.querySelector("#sfAd").value.trim();
    const aralik = parseFloat(popupEl.querySelector("#sfAralik").value);
    const yon = parseFloat(popupEl.querySelector("#sfYon").value);
    const yuk = parseFloat(popupEl.querySelector("#sfYukseklik").value);
    const hiz = parseFloat(popupEl.querySelector("#sfHiz").value);
    const noktalar = rotaNoktalari.map(n => ({
      lat: n.lat, lon: n.lon, irtifa: yuk, hiz: hiz,
    }));
    const mesaj = { tip: "rota_kaydet", isim: isim,
                    irtifa: yuk, hiz: hiz, noktalar: noktalar,
                    meta: { tur: "serbest_form",
                            koseler: koseler.map(k => ({
                              lat: k.lat, lon: k.lon })),
                            aralik: aralik, yon: yon } };
    if (duzenlenenId !== null) mesaj.id = duzenlenenId;
    wsGonder(mesaj);
    konsol("'" + isim + "' " + t("sfKonsolKaydet") +
           " (" + noktalar.length + " nokta)");
    kapat();
  }

  function iptalEt(){
    if (aktif && koseler.length){
      if (!confirm(t("sfOnayIptal"))) return;
    }
    kapat();
  }

  function kapat(){
    aktif = false;
    koseler = [];
    rotaNoktalari = [];
    duzenlenenId = null;
    cizimTemizle();
    const kap = document.getElementById("cesiumContainer");
    if (kap) kap.style.cursor = "";
    if (popupEl){ popupEl.remove(); popupEl = null; }
  }

  // ---------------------------------------------------------------
  // v2.4.5: DUZENLEME MODU — kayitli serbest form gorevini popup'ta ac
  // ---------------------------------------------------------------
  function duzenleAc(rota){
    if (!rota || !rota.meta || rota.meta.tur !== "serbest_form") return;
    popupAc();
    duzenlenenId = rota.id;
    // Parametreleri mevcut degerlerle doldur
    popupEl.querySelector("#sfAd").value = rota.isim || "";
    const m = rota.meta;
    if (isFinite(m.aralik))
      popupEl.querySelector("#sfAralik").value = m.aralik;
    if (isFinite(m.yon))
      popupEl.querySelector("#sfYon").value = m.yon;
    if (isFinite(rota.irtifa_varsayilan))
      popupEl.querySelector("#sfYukseklik").value = rota.irtifa_varsayilan;
    if (isFinite(rota.hiz_varsayilan))
      popupEl.querySelector("#sfHiz").value = rota.hiz_varsayilan;
    // Etiketleri tazele (input event'i tetikle)
    ["#sfAralik", "#sfYon", "#sfYukseklik", "#sfHiz"].forEach(s =>
      popupEl.querySelector(s).dispatchEvent(new Event("input")));
    // Cizim modunu koselerle baslat
    cizimBaslat();
    koseler = (m.koseler || []).map(k => ({ lat: k.lat, lon: k.lon }));
    // Bitir dugmesi etiketi guncelleme moduna isaret etsin
    const btn = popupEl.querySelector("#sfBitirBtn");
    if (btn) btn.innerHTML =
      '<i class="fa-solid fa-floppy-disk"></i> ' + t("sfGuncelle");
    yenidenHesapla();
    konsol("'" + (rota.isim || "#" + rota.id) + "' " +
           t("sfKonsolDuzenle"));
  }

  // Haritada rota entity'sine cift tiklama: serbest form ise duzenle
  (function ciftTikKur(){
    if (typeof viewer === "undefined" || !viewer || !viewer.scene){
      setTimeout(ciftTikKur, 500); return;
    }
    try {
      const h = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
      h.setInputAction((ev) => {
        if (aktif) return;   // cizim/duzenleme zaten acik
        let secilen = [];
        try { secilen = viewer.scene.drillPick(ev.position, 8); }
        catch(_){ return; }
        for (const p of secilen){
          const ent = p && p.id;
          if (!ent || typeof ent._rotaId === "undefined") continue;
          const rotalar = (typeof window.rotaVerileri === "function")
            ? window.rotaVerileri() : [];
          const rota = rotalar.find(r => r.id === ent._rotaId);
          if (rota && rota.meta && rota.meta.tur === "serbest_form"){
            duzenleAc(rota);
            return;
          }
          // v2.4.40: koridor gorevi kendi popup'inda acilir; aksi halde
          // merkez hat / genislik / tur alanlari duzenlenemez.
          if (rota && rota.meta && rota.meta.tur === "koridor" &&
              typeof window.koridorDuzenle === "function"){
            window.koridorDuzenle(rota);
            return;
          }
          // v2.4.23: diger rota tiplerinde cift tik parametre
          // duzenleme popup'ini acar (irtifa / hiz / aci)
          if (rota && typeof window.rotaParamAc === "function"){
            window.rotaParamAc(rota);
            return;
          }
        }
      }, Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);
    } catch(_){}
  })();

  // ---------------------------------------------------------------
  // MENU BAGLANTISI
  // ---------------------------------------------------------------
  const mb = document.getElementById("mbSerbestForm");
  if (mb){
    mb.addEventListener("click", (e) => {
      e.stopPropagation();
      const mi = mb.closest(".mb-item");
      if (mi) mi.classList.remove("acik");
      setTimeout(popupAc, 0);
    });
  }

  // --- Test / dis erisim ---
  window.serbestFormAc = popupAc;
  window.serbestFormDuzenle = duzenleAc;
  // v2.4.23: rota_param.js zigzag rotayi yeniden uretmek icin kullanir
  // (koseler, aralik_m, yon_derece) -> [{lat, lon}]
  window.serbestFormRotaUret = function(koseler, aralik, aciDeg){
    if (!koseler || koseler.length < 3) return [];
    const k = koseler.map(c => ({lat: Number(c.lat), lon: Number(c.lon)}));
    try {
      return zigzagUret(k, Math.max(1, Number(aralik) || 10),
                        Number(aciDeg) || 0);
    } catch(_){ return []; }
  };
  window.__serbestFormDuzenlenenId = function(){ return duzenlenenId; };
  window.__serbestFormDurum = function(){
    return { aktif, koseler: koseler.slice(), rota: rotaNoktalari.slice() };
  };
  window.__serbestFormTikla = function(lat, lon){
    if (!aktif) return false;
    koseler.push({ lat, lon });
    yenidenHesapla();
    return true;
  };
})();

/* FAZ18-IS2B-IKON-METIN-SPAN */
