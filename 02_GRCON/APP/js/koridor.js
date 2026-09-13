// =================================================================
// GOKTUNGU - KORIDOR GOREV (v2.4.40)
// Bir merkez hat (yol, sinir, boru hatti, kanal...) etrafinda
// belirtilen genislikte koridor tanimlar ve koridorun SAG ve SOL
// kenarlarindan gecen bir tarama rotasi uretir.
//
// Akis:
//   1) Rotalar > Koridor -> tasinabilir popup acilir
//      (gorev ismi, yukseklik, tur sayisi, koridor genisligi, seyir hizi)
//   2) ROTA EKLE -> harita cizim moduna gecer; kullanici haritaya
//      tiklayarak merkez hat noktasi ekler. 2. noktadan itibaren
//      koridor olusur ve rota HER yeni noktada yeniden hesaplanir.
//   3) Popup KAPANMAZ; genislik/yukseklik/tur degisince rota canli
//      yeniden uretilir.
//   4) GOREVI TAMAMLA -> rota sunucuya kaydedilir, mod kapanir.
//
// Geometri:
//   Merkez hat P0..Pn. Her nokta icin komsu segmentlerin birim
//   normallerinin ortalamasi alinir (yumusak kose gecisi). Sol kenar
//   = P + nSol*(W/2), sag kenar = P - nSol*(W/2).
//   Rota (tur basina): solKenar[0..n] -> sagKenar[n..0]
//   Bu, koridorun bir kenarindan gidip diger kenarindan donen kapali
//   bir tur uretir; T tur icin desen T kez tekrarlanir.
//
// Bu dosya klasik script'tir; rotalar.js'ten SONRA yuklenmelidir.
// =================================================================
(function(){
  "use strict";
  function t(k){
    const d = (typeof D === "function") ? D() : {};
    return d[k] || k;
  }
  function konsol(m){
    if (typeof konsolYaz === "function") konsolYaz("KORIDOR", m);
    else console.log(m);
  }
  function wsGonder(m){
    if (typeof ws !== "undefined" && ws && ws.readyState === 1)
      ws.send(JSON.stringify(m));
  }

  // --- Durum ---
  let popupEl = null;        // parametre popup'i (surekli acik)
  let aktif = false;         // cizim modu aktif mi
  let merkez = [];           // merkez hat noktalari [{lat, lon}]
  let rotaNoktalari = [];    // uretilen koridor rotasi
  let solKenar = [];         // hesaplanan sol kenar [{lat, lon}]
  let sagKenar = [];         // hesaplanan sag kenar [{lat, lon}]
  let cizimler = [];         // Cesium entity'leri
  let duzenlenenId = null;   // duzenlenen rota id (null = yeni)

  // ---------------------------------------------------------------
  // GEOMETRI: yerel duzlem (metre) donusumleri
  // ---------------------------------------------------------------
  const R_DUNYA = 6371000;
  const rad = Math.PI / 180;
  let ref = null;   // referans nokta {lat, lon}

  function xyYap(k){
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

  // Koridor kenarlarini uret.
  //   noktalar: merkez hat [{lat,lon}] (>=2)
  //   genislik: koridor toplam genisligi (m)
  // Donus: { sol: [{lat,lon}], sag: [{lat,lon}] }
  //
  // Her merkez noktasinda, o noktaya komsu segmentlerin SOL birim
  // normalleri toplanip normalize edilir. Kose noktalarinda ofset
  // mesafesi 1/cos(yarim kose acisi) kadar buyur; bu carpan
  // KOSE_SINIR ile sinirlanir (cok keskin koselerde ucus disari
  // firlamasin).
  const KOSE_SINIR = 2.5;

  function kenarlarUret(noktalar, genislik){
    if (!noktalar || noktalar.length < 2) return { sol: [], sag: [] };
    ref = noktalar[0];
    const p = noktalar.map(xyYap);
    const yari = Math.max(0.5, genislik / 2);

    // Segment birim vektorleri ve sol normalleri
    const seg = [];
    for (let i = 0; i + 1 < p.length; i++){
      const dx = p[i + 1].x - p[i].x, dy = p[i + 1].y - p[i].y;
      const uzunluk = Math.hypot(dx, dy);
      if (uzunluk < 1e-6){ seg.push(null); continue; }
      const ux = dx / uzunluk, uy = dy / uzunluk;
      // Sol normal: yon vektorunu +90 derece dondur -> (-uy, ux)
      seg.push({ ux, uy, nx: -uy, ny: ux });
    }
    // Bos (cakisan) segmentleri komsulariyla doldur
    for (let i = 0; i < seg.length; i++){
      if (seg[i]) continue;
      let j = i - 1; while (j >= 0 && !seg[j]) j--;
      let k = i + 1; while (k < seg.length && !seg[k]) k++;
      seg[i] = (j >= 0 ? seg[j] : (k < seg.length ? seg[k] : null));
    }
    if (!seg.length || !seg[0]) return { sol: [], sag: [] };

    const sol = [], sag = [];
    for (let i = 0; i < p.length; i++){
      const a = (i === 0) ? seg[0] : seg[i - 1];
      const b = (i === p.length - 1) ? seg[seg.length - 1] : seg[i];
      const sa = a || b, sb = b || a;
      let nx = sa.nx + sb.nx, ny = sa.ny + sb.ny;
      const uz = Math.hypot(nx, ny);
      let carpan = 1;
      if (uz < 1e-6){
        // Tam geri donus (180 derece); tek segmentin normalini kullan
        nx = sa.nx; ny = sa.ny;
      } else {
        nx /= uz; ny /= uz;
        // Mitre carpani: 1 / cos(yarim aci). Ic carpimla hesaplanir.
        const cosYari = nx * sa.nx + ny * sa.ny;
        carpan = (cosYari > 1e-3) ? Math.min(1 / cosYari, KOSE_SINIR) : KOSE_SINIR;
      }
      const d = yari * carpan;
      sol.push(koordYap({ x: p[i].x + nx * d, y: p[i].y + ny * d }));
      sag.push(koordYap({ x: p[i].x - nx * d, y: p[i].y - ny * d }));
    }
    return { sol, sag };
  }

  // Koridor rotasi: her tur sol kenar boyunca ileri, sag kenar
  // boyunca geri. turSayisi kadar tekrarlanir.
  function koridorRotaUret(noktalar, genislik, turSayisi){
    const k = kenarlarUret(noktalar, genislik);
    solKenar = k.sol; sagKenar = k.sag;
    if (!k.sol.length) return [];
    const tur = Math.max(1, Math.round(turSayisi) || 1);
    const cikti = [];
    for (let d = 0; d < tur; d++){
      k.sol.forEach(n => cikti.push({ lat: n.lat, lon: n.lon }));
      for (let i = k.sag.length - 1; i >= 0; i--)
        cikti.push({ lat: k.sag[i].lat, lon: k.sag[i].lon });
    }
    return cikti;
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
    const yuk = popupEl
      ? parseFloat(popupEl.querySelector("#korYukseklik").value) : 30;

    // Merkez hat noktalari
    merkez.forEach((k, i) => {
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
    });

    // Merkez hat cizgisi (kesikli, turuncu)
    if (merkez.length >= 2){
      const mDizi = [];
      merkez.forEach(k => mDizi.push(k.lon, k.lat));
      cizimler.push(viewer.entities.add({
        polyline: {
          positions: Cesium.Cartesian3.fromDegreesArray(mDizi),
          width: 2, clampToGround: true,
          material: new Cesium.PolylineDashMaterialProperty({
            color: Cesium.Color.fromCssColorString("#f59e0b").withAlpha(0.85),
            dashLength: 10,
          }),
        }
      }));
    }

    // KORIDOR GOVDESI: sol kenar + ters sag kenar = kapali cokgen.
    // Ortasi SEFFAF MAVI ile boyanir (kullanici istegi).
    if (solKenar.length >= 2 && sagKenar.length >= 2){
      const cev = [];
      solKenar.forEach(n => cev.push(n.lon, n.lat));
      for (let i = sagKenar.length - 1; i >= 0; i--)
        cev.push(sagKenar[i].lon, sagKenar[i].lat);
      cizimler.push(viewer.entities.add({
        polygon: {
          hierarchy: Cesium.Cartesian3.fromDegreesArray(cev),
          material: Cesium.Color.fromCssColorString("#3b82f6").withAlpha(0.22),
          outline: false,
          // Arazi yuksekligi acikken koridor zemine otursun
          classificationType: Cesium.ClassificationType.TERRAIN,
        }
      }));
      // Kenar cizgileri (dolgudan biraz daha belirgin mavi)
      [solKenar, sagKenar].forEach(kenar => {
        const d = [];
        kenar.forEach(n => d.push(n.lon, n.lat));
        cizimler.push(viewer.entities.add({
          polyline: {
            positions: Cesium.Cartesian3.fromDegreesArray(d),
            width: 2, clampToGround: true,
            material: Cesium.Color.fromCssColorString("#60a5fa").withAlpha(0.9),
          }
        }));
      });
    }

    // Ucus rotasi (yukseklikte, mavi kesikli)
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
      const b0 = rotaNoktalari[0];
      const b1 = rotaNoktalari[rotaNoktalari.length - 1];
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
    const gen = parseFloat(popupEl.querySelector("#korGenislik").value);
    const tur = parseInt(popupEl.querySelector("#korTur").value, 10);
    if (merkez.length >= 2){
      rotaNoktalari = koridorRotaUret(merkez, Math.max(1, gen), tur);
    } else {
      rotaNoktalari = []; solKenar = []; sagKenar = [];
    }
    ciz();
    bilgiTazele();
  }

  function bilgiTazele(){
    if (!popupEl) return;
    const el = popupEl.querySelector("#korBilgi");
    if (merkez.length < 2){
      el.textContent = t("korBilgiBekliyor");
      return;
    }
    // Merkez hat uzunlugu
    ref = merkez[0];
    let hatUzunluk = 0;
    for (let i = 1; i < merkez.length; i++){
      const a = xyYap(merkez[i - 1]), b = xyYap(merkez[i]);
      hatUzunluk += Math.hypot(b.x - a.x, b.y - a.y);
    }
    // Toplam ucus mesafesi
    let mesafe = 0;
    for (let i = 1; i < rotaNoktalari.length; i++){
      const a = xyYap(rotaNoktalari[i - 1]), b = xyYap(rotaNoktalari[i]);
      mesafe += Math.hypot(b.x - a.x, b.y - a.y);
    }
    const gen = parseFloat(popupEl.querySelector("#korGenislik").value);
    const alan = hatUzunluk * Math.max(1, gen);
    function mMetin(m){
      return (m >= 1000) ? (m / 1000).toFixed(2) + " km" : Math.round(m) + " m";
    }
    const aMetin = (alan >= 10000)
      ? (alan / 10000).toFixed(2) + " ha" : Math.round(alan) + " m²";
    el.textContent =
      t("korBilgiHat") + ": " + merkez.length + "   " +
      t("korBilgiNokta") + ": " + rotaNoktalari.length + "\n" +
      t("korBilgiUzunluk") + ": " + mMetin(hatUzunluk) + "   " +
      t("korBilgiAlan") + ": " + aMetin + "\n" +
      t("korBilgiMesafe") + ": " + mMetin(mesafe);
  }

  // ---------------------------------------------------------------
  // PARAMETRE POPUP'I (tasinabilir, cizim boyunca acik kalir)
  // ---------------------------------------------------------------
  function popupAc(){
    if (popupEl){ popupEl.remove(); popupEl = null; }
    popupEl = document.createElement("div");
    popupEl.className = "sf-popup kor-popup";
    popupEl.innerHTML = `
      <div class="sf-baslik kor-baslik popup-baslik">
        <i class="fa-solid fa-road"></i> <span>${t("korBaslik")}</span>
        <button class="sf-kapat" title="${t("btnIptal")}"><i class="fa-solid fa-xmark"></i></button>
      </div>
      <div class="sf-icerik">
        <label class="sf-lbl" for="korAd">${t("korGorevAdi")}</label>
        <input type="text" id="korAd" maxlength="60" spellcheck="false"
               placeholder="${t("korGorevAdiIpucu")}">
        <div class="sf-slider-satir">
          <label><span>${t("korYukseklik")}</span>
            <span class="sf-deger" id="korYukseklikDeger">30 m</span></label>
          <input type="range" id="korYukseklik" min="2" max="300" step="1" value="30">
        </div>
        <div class="sf-slider-satir">
          <label><span>${t("korTur")}</span>
            <span class="sf-deger" id="korTurDeger">1</span></label>
          <input type="range" id="korTur" min="1" max="20" step="1" value="1">
        </div>
        <div class="sf-slider-satir">
          <label><span>${t("korGenislik")}</span>
            <span class="sf-deger" id="korGenislikDeger">50 m</span></label>
          <input type="range" id="korGenislik" min="4" max="500" step="2" value="50">
        </div>
        <div class="sf-slider-satir">
          <label><span>${t("korHiz")}</span>
            <span class="sf-deger" id="korHizDeger">8.0 m/s</span></label>
          <input type="range" id="korHiz" min="1" max="40" step="0.5" value="8">
        </div>
        <div class="sf-bilgi" id="korBilgi"></div>
        <div class="sf-hata" id="korHata"></div>
        <button class="sf-btn sf-btn-olustur" id="korOlusturBtn">
          <i class="fa-solid fa-pen"></i><span>${t("korRotaEkle")}
        </span></button>
        <div class="sf-cizim-butonlar" id="korCizimButonlar" style="display:none">
          <button class="sf-btn sf-btn-geri" id="korGeriAlBtn">
            <i class="fa-solid fa-rotate-left"></i><span>${t("korGeriAl")}
          </span></button>
          <button class="sf-btn sf-btn-bitir" id="korBitirBtn">
            <i class="fa-solid fa-flag-checkered"></i><span>${t("korTamamla")}
          </span></button>
        </div>
      </div>`;
    document.body.appendChild(popupEl);

    const baslik = popupEl.querySelector(".kor-baslik");
    if (typeof popupTasinabilirYap === "function")
      popupTasinabilirYap(popupEl, baslik, "koridorRota");

    baslik.querySelector(".sf-kapat").addEventListener("click", iptalEt);

    const inpYuk = popupEl.querySelector("#korYukseklik");
    const inpTur = popupEl.querySelector("#korTur");
    const inpGen = popupEl.querySelector("#korGenislik");
    const inpHiz = popupEl.querySelector("#korHiz");
    function etiketTazele(){
      popupEl.querySelector("#korYukseklikDeger").textContent = inpYuk.value + " m";
      popupEl.querySelector("#korTurDeger").textContent = inpTur.value;
      popupEl.querySelector("#korGenislikDeger").textContent = inpGen.value + " m";
      popupEl.querySelector("#korHizDeger").textContent =
        parseFloat(inpHiz.value).toFixed(1) + " m/s";
    }
    [inpYuk, inpTur, inpGen, inpHiz].forEach(el =>
      el.addEventListener("input", () => {
        etiketTazele(); if (aktif) yenidenHesapla();
      }));
    etiketTazele();

    popupEl.querySelector("#korOlusturBtn").addEventListener("click", () => {
      const isim = popupEl.querySelector("#korAd").value.trim();
      if (!isim){
        popupEl.querySelector("#korHata").textContent = t("rotaHataAd");
        return;
      }
      popupEl.querySelector("#korHata").textContent = "";
      cizimBaslat();
    });

    duzenlenenId = null;

    popupEl.querySelector("#korGeriAlBtn").addEventListener("click", () => {
      if (!merkez.length) return;
      merkez.pop();
      yenidenHesapla();
    });

    popupEl.querySelector("#korBitirBtn").addEventListener("click", kaydet);

    popupEl.querySelector("#korBilgi").textContent = t("korBilgiIlk");
  }

  // ---------------------------------------------------------------
  // CIZIM MODU
  // ---------------------------------------------------------------
  function cizimBaslat(){
    aktif = true;
    merkez = [];
    rotaNoktalari = [];
    solKenar = []; sagKenar = [];
    popupEl.querySelector("#korOlusturBtn").style.display = "none";
    popupEl.querySelector("#korCizimButonlar").style.display = "";
    popupEl.querySelector("#korAd").disabled = true;
    popupEl.querySelector("#korBilgi").textContent = t("korBilgiBekliyor");
    const kap = document.getElementById("cesiumContainer");
    if (kap) kap.style.cursor = "crosshair";
    konsol(t("korKonsolBaslat"));
  }

  function haritaTikla(e){
    if (!aktif) return false;
    const kap = document.getElementById("cesiumContainer");
    const r = kap.getBoundingClientRect();
    const k = (typeof window.__ekrandanKoordinat === "function")
      ? window.__ekrandanKoordinat(e.clientX - r.left, e.clientY - r.top)
      : null;
    if (!k) return true;
    merkez.push({ lat: k.lat, lon: k.lon });
    yenidenHesapla();
    return true;
  }

  // Harita tiklama: rotalar.js'in click handler'i "duzenleme" modunda
  // degilken calismaz; koridor kendi capture dinleyicisini kurar.
  function tikKur(){
    const kap = document.getElementById("cesiumContainer");
    if (!kap){ setTimeout(tikKur, 500); return; }
    kap.addEventListener("click", (e) => {
      if (!aktif) return;
      if (e.altKey || e.ctrlKey) return;   // konum kaydet / dron menu
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
    if (merkez.length < 2 || rotaNoktalari.length < 2){
      popupEl.querySelector("#korHata").textContent = t("korHataNokta");
      return;
    }
    const isim = popupEl.querySelector("#korAd").value.trim();
    const yuk = parseFloat(popupEl.querySelector("#korYukseklik").value);
    const tur = parseInt(popupEl.querySelector("#korTur").value, 10);
    const gen = parseFloat(popupEl.querySelector("#korGenislik").value);
    const hiz = parseFloat(popupEl.querySelector("#korHiz").value);
    const noktalar = rotaNoktalari.map(n => ({
      lat: n.lat, lon: n.lon, irtifa: yuk, hiz: hiz,
    }));
    const mesaj = { tip: "rota_kaydet", isim: isim,
                    irtifa: yuk, hiz: hiz, noktalar: noktalar,
                    meta: { tur: "koridor",
                            merkez: merkez.map(k => ({
                              lat: k.lat, lon: k.lon })),
                            genislik: gen, tur_sayisi: tur } };
    if (duzenlenenId !== null) mesaj.id = duzenlenenId;
    wsGonder(mesaj);
    konsol("'" + isim + "' " + t("korKonsolKaydet") +
           " (" + noktalar.length + " nokta, " + tur + " tur)");
    kapat();
  }

  function iptalEt(){
    if (aktif && merkez.length){
      if (!confirm(t("korOnayIptal"))) return;
    }
    kapat();
  }

  function kapat(){
    aktif = false;
    merkez = [];
    rotaNoktalari = [];
    solKenar = []; sagKenar = [];
    duzenlenenId = null;
    cizimTemizle();
    const kap = document.getElementById("cesiumContainer");
    if (kap) kap.style.cursor = "";
    if (popupEl){ popupEl.remove(); popupEl = null; }
  }

  // ---------------------------------------------------------------
  // DUZENLEME MODU — kayitli koridor gorevini popup'ta ac
  // ---------------------------------------------------------------
  function duzenleAc(rota){
    if (!rota || !rota.meta || rota.meta.tur !== "koridor") return;
    popupAc();
    duzenlenenId = rota.id;
    popupEl.querySelector("#korAd").value = rota.isim || "";
    const m = rota.meta;
    if (isFinite(m.genislik))
      popupEl.querySelector("#korGenislik").value = m.genislik;
    if (isFinite(m.tur_sayisi))
      popupEl.querySelector("#korTur").value = m.tur_sayisi;
    if (isFinite(rota.irtifa_varsayilan))
      popupEl.querySelector("#korYukseklik").value = rota.irtifa_varsayilan;
    if (isFinite(rota.hiz_varsayilan))
      popupEl.querySelector("#korHiz").value = rota.hiz_varsayilan;
    ["#korGenislik", "#korTur", "#korYukseklik", "#korHiz"].forEach(s =>
      popupEl.querySelector(s).dispatchEvent(new Event("input")));
    cizimBaslat();
    merkez = (m.merkez || []).map(k => ({ lat: k.lat, lon: k.lon }));
    const btn = popupEl.querySelector("#korBitirBtn");
    if (btn) btn.innerHTML =
      '<i class="fa-solid fa-floppy-disk"></i> ' + t("korGuncelle");
    yenidenHesapla();
    konsol("'" + (rota.isim || "#" + rota.id) + "' " + t("korKonsolDuzenle"));
  }

  // ---------------------------------------------------------------
  // MENU BAGLANTISI
  // ---------------------------------------------------------------
  const mb = document.getElementById("mbKoridorRota");
  if (mb){
    mb.addEventListener("click", (e) => {
      e.stopPropagation();
      const mi = mb.closest(".mb-item");
      if (mi) mi.classList.remove("acik");
      setTimeout(popupAc, 0);
    });
  }

  // --- Test / dis erisim ---
  window.koridorAc = popupAc;
  window.koridorDuzenle = duzenleAc;
  // rota_param.js / serbest_form.js cift tik yonlendirmesi icin
  window.koridorRotaUret = function(merkezNoktalar, genislik, turSayisi){
    if (!merkezNoktalar || merkezNoktalar.length < 2) return [];
    const k = merkezNoktalar.map(c => ({
      lat: Number(c.lat), lon: Number(c.lon) }));
    try {
      return koridorRotaUret(k, Math.max(1, Number(genislik) || 50),
                             Number(turSayisi) || 1);
    } catch(_){ return []; }
  };
  window.koridorKenarUret = function(merkezNoktalar, genislik){
    if (!merkezNoktalar || merkezNoktalar.length < 2) return { sol: [], sag: [] };
    const k = merkezNoktalar.map(c => ({
      lat: Number(c.lat), lon: Number(c.lon) }));
    try { return kenarlarUret(k, Math.max(1, Number(genislik) || 50)); }
    catch(_){ return { sol: [], sag: [] }; }
  };
  window.__koridorDuzenlenenId = function(){ return duzenlenenId; };
  window.__koridorDurum = function(){
    return { aktif, merkez: merkez.slice(), rota: rotaNoktalari.slice(),
             sol: solKenar.slice(), sag: sagKenar.slice() };
  };
  window.__koridorTikla = function(lat, lon){
    if (!aktif) return false;
    merkez.push({ lat, lon });
    yenidenHesapla();
    return true;
  };
})();

/* FAZ18-IS2B-IKON-METIN-SPAN */
