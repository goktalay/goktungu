// =====================================================================
// GECMIS.JS - DRON HISTORY PANELI
// ---------------------------------------------------------------------
// - DRONLAR panel basligindaki saat ikonu veya dron menusundeki History
//   ogesiyle acilir.
// - Tasinabilir (basliktan surukle) + resize edilebilir (sag-alt kose).
// - Sol: kayitli dronlar -> secilince ucus listesi.
// - Sag: kucuk Cesium haritasi; ucus secilince iz cizilir, PLAY ile
//   hareketli nokta animasyonu izlenir.
// =====================================================================
"use strict";

let _gecmisPopup = null;      // acik popup DOM'u
let _gecmisViewer = null;     // ikinci (mini) Cesium viewer
let _gecmisDronlar = [];      // backend'den gelen dron listesi
let _gecmisSecDron = null;    // secili dron anahtari
let _gecmisUcus = null;       // yuklu ucus verisi
let _gecmisOynatici = null;   // {timer, idx, hiz, oynuyor}
let _gecmisFiltreSysid = null; // menuden acilirsa bu dron one secilir
let _gecmisTespitler = [];    // v2.4.2: ucusa bagli AI tespitleri
let _gecmisKalkis = [];       // v2.4.41: ucusa bagli kalkis kontrol kaydi

// ---------------------------------------------------------------
// Acilis / kapanis
// ---------------------------------------------------------------
function dronGecmisAc(sysid) {
  _gecmisFiltreSysid = (typeof sysid === "number") ? sysid : null;
  if (_gecmisPopup) {
    // Zaten acik: yalniz listeyi tazele ve one getir
    if (ws && ws.readyState === 1) ws.send(JSON.stringify({ tip: "dron_gecmis_liste" }));
    
    return;
  }
  const t = D();
  const pop = document.createElement("div");
  pop.className = "gecmis-popup";
  _gecmisPopup = pop;

  // Baslik (tasinabilir + x) - dronlar.js'deki ortak yardimci
  dkMiniPopupBaslikKur(pop, t.gcBaslik || "DRON HISTORY",
    null, "fa-clock-rotate-left");
  // Kapanista kaynaklari temizle
  const kapatBtn = pop.querySelector(".dk-mp-kapat");
  if (kapatBtn) kapatBtn.addEventListener("click", dronGecmisKapat);

  // v2.4.64: TAM EKRAN dugmesi (kapatma dugmesinin soluna).
  // Kullanici istegi: "bu log panelini tam ekran yapabilsin".
  // Tarayici fullscreen API'si yerine CSS ile tam pencere kaplama
  // kullanilir; boylece Cesium viewer yeniden olusturulmaz ve
  // oynatici durumu (secili ucus, konum, hiz) korunur.
  const basSatir = pop.querySelector(".dk-mp-baslik");
  if (basSatir && kapatBtn) {
    const tamBtn = document.createElement("button");
    tamBtn.className = "dk-mp-kapat gc-tam-ekran";
    tamBtn.id = "gcTamEkran";
    tamBtn.title = t.gcTamEkran || "Tam ekran";
    tamBtn.innerHTML = "<i class='fa-solid fa-expand'></i>";
    tamBtn.addEventListener("click", (ev) => {
      ev.stopPropagation();
      gcTamEkranDegistir();
    });
    basSatir.insertBefore(tamBtn, kapatBtn);
  }

  // Govde: sol liste + sag harita
  const govde = document.createElement("div");
  govde.className = "gc-govde";

  const sol = document.createElement("div");
  sol.className = "gc-sol";
  // v2.1.8: yonetici icin TUMUNU SIL dugmesi (sunucu ayrica denetler)
  const yoneticiMi = (typeof oturum !== "undefined" && oturum &&
                      oturum.rol === "yonetici");
  sol.innerHTML =
    (yoneticiMi
      ? "<button class='gc-tumunu-sil' id='gcTumunuSil'>" +
        "<i class='fa-solid fa-trash-can'></i><span>" +
        (t.gcTumunuSil || "T\u00fcm\u00fcn\u00fc Sil") + "</span></button>"
      : "") +
    "<div class='gc-liste' id='gcDronListe'></div>";

  const sag = document.createElement("div");
  sag.className = "gc-sag";
  sag.innerHTML =
    "<div id='gcHarita'></div>" +
    // v2.4.64: ucusun belge esleme kodunun QR'i harita sag ust kosede.
    // Pilot ekrandaki QR'i telefonla okutup ayni ucusun raporuna
    // ulasabilir; rapor/grafik ciktilariyla ayni kodu tasir.
    // Ucus secilmeden gorunmez; gcUcusCiz() doldurup gosterir.
    "<div class='gc-qr' id='gcQr' style='display:none;'></div>" +
    "<div class='gc-oynatici' id='gcOynatici' style='display:none;'>" +
      "<button id='gcPlay' title='Play'><i class='fa-solid fa-play'></i></button>" +
      "<select id='gcHiz'>" +
        "<option value='1'>1x</option><option value='2'>2x</option>" +
        "<option value='5'>5x</option><option value='10'>10x</option>" +
      "</select>" +
      "<span class='gc-bar-sar' id='gcBarSar'>" +
        "<input type='range' id='gcBar' min='0' max='100' value='0' step='1'>" +
        "<span class='gc-tl-isaretler' id='gcTlIsaretler'></span>" +
      "</span>" +
      "<span id='gcZaman'>0:00 / 0:00</span>" +
    "</div>" +
    "<div class='gc-tespit-serit' id='gcTespitSerit' style='display:none;'></div>" +
    "<div class='gc-bilgi' id='gcBilgi'>" +
      (t.gcUcusSec || "Soldan bir u\u00e7u\u015f se\u00e7in") + "</div>" +
    // v2.4.41: antetli ucus raporu (yazdir / PDF olarak kaydet).
    // Ucus secilmeden gorunmez; gcUcusCiz() gosterir.
    "<div class='gc-rapor-satir' id='gcRaporSatir' style='display:none;'>" +
      // v2.4.42: EN SOLDA grafikler dugmesi (hiz/irtifa/batarya...).
      "<button class='gc-grafik-btn' id='gcGrafikBtn'>" +
        "<i class='fa-solid fa-chart-line'></i><span>" +
        (t.gcGrafikBtn || "GRAF\u0130KLER") + "</span></button>" +
      "<button class='gc-rapor-btn' id='gcRaporBtn'>" +
        "<i class='fa-solid fa-file-pdf'></i><span>" +
        (t.gcRaporBtn || "RAPOR OLARAK \u0130ND\u0130R") + "</span></button>" +
    "</div>";

  // FAZ18-IS22-GECMIS-FILTRE: FILTRE ust bari.
  // Kullanici istegi: "bu filitreleri de uste bir header ekle basligi
  // FILITRE olsun ve baslik solda olsun sag tarafa ise filitreleri koy".
  // Desen UYDURULMADI: Tespit Gecmisi paneli (index.html:1738) ayni
  // duzeni tasiyor -> `.tb-etiket` solda, `.tb-bosluk` (flex:1)
  // filtreleri SAGA yasliyor. CSS zaten hazir (panel_ustbar.css).
  const ustBar = document.createElement("div");
  ustBar.className = "panel-toolbar tb-filtre";
  ustBar.id = "gcFiltreBar";
  ustBar.innerHTML =
    "<span class='tb-etiket'>" + (t.gcFiltreEtiket || "F\u0130LTRE") + "</span>" +
    "<span class='tb-bosluk'></span>" +
    "<select id='gcFPilot'><option value=''>" +
      (t.gcPilotTumu || "T\u00dcM P\u0130LOTLAR") + "</option></select>" +
    "<select id='gcFTur'><option value=''>" +
      (t.gcTurTumu || "T\u00dcM T\u00dcRLER") + "</option></select>" +
    "<input type='date' id='gcFTarih'>" +
    "<button id='gcFTemizle' class='tb-btn tb-btn-metin' title='" +
      (t.gcTemizle || "Filtreyi temizle") + "'>" +
      "<i class='fa-solid fa-filter-circle-xmark'></i><span>" +
      (t.gcTemizle || "TEM\u0130ZLE") + "</span></button>";
  pop.appendChild(ustBar);
  govde.appendChild(sol);
  govde.appendChild(sag);
  pop.appendChild(govde);
  // Filtre olaylari: her degisiklikte YALNIZ liste yeniden cizilir.
  // Sunucuya yeni istek GONDERILMEZ -- veri istemcide zaten var
  // (dron_gecmis_liste tum ucuslari getiriyor).
  ["gcFPilot", "gcFTur"].forEach((id) => {
    const el = ustBar.querySelector("#" + id);
    if (el) el.addEventListener("change", () => { gcListeCiz(); });
  });
  const tarihEl = ustBar.querySelector("#gcFTarih");
  if (tarihEl) tarihEl.addEventListener("change", () => { gcListeCiz(); });
  const temizleEl = ustBar.querySelector("#gcFTemizle");
  if (temizleEl) temizleEl.addEventListener("click", () => {
    const p = document.getElementById("gcFPilot");
    const u = document.getElementById("gcFTur");
    const d = document.getElementById("gcFTarih");
    if (p) p.value = "";
    if (u) u.value = "";
    if (d) d.value = "";
    gcListeCiz();
  });

  // Resize tutamaci (sag-alt kose)
  const tutamac = document.createElement("div");
  tutamac.className = "gc-resize";
  tutamac.innerHTML = "<i class='fa-solid fa-grip-lines' style='transform:rotate(-45deg);'></i>";
  pop.appendChild(tutamac);
  let boyut = null;
  tutamac.addEventListener("pointerdown", (ev) => {
    const r = pop.getBoundingClientRect();
    boyut = { w: r.width, h: r.height, x: ev.clientX, y: ev.clientY };
    tutamac.setPointerCapture(ev.pointerId);
    ev.preventDefault(); ev.stopPropagation();
  });
  tutamac.addEventListener("pointermove", (ev) => {
    if (!boyut) return;
    const w = Math.max(560, Math.min(boyut.w + ev.clientX - boyut.x, window.innerWidth - 20));
    const h = Math.max(360, Math.min(boyut.h + ev.clientY - boyut.y, window.innerHeight - 20));
    pop.style.width = w + "px";
    pop.style.height = h + "px";
  });
  const birak = (ev) => {
    if (!boyut) return;
    boyut = null;
    try { tutamac.releasePointerCapture(ev.pointerId); } catch (e) {}
  };
  tutamac.addEventListener("pointerup", birak);
  tutamac.addEventListener("pointercancel", birak);

  document.body.appendChild(pop);
  // Ortala
  pop.style.left = Math.max(10, (window.innerWidth - pop.offsetWidth) / 2) + "px";
  pop.style.top = Math.max(10, (window.innerHeight - pop.offsetHeight) / 2) + "px";

  // Mini Cesium viewer (agir widget'lar kapali) - ana haritayla ayni altlik
  _gecmisViewer = new Cesium.Viewer("gcHarita", {
    baseLayer: haritaKatmani(),
    baseLayerPicker: false, geocoder: false, homeButton: false,
    sceneModePicker: false, navigationHelpButton: false,
    animation: false, timeline: false, fullscreenButton: false,
    infoBox: false, selectionIndicator: false,
  });
  _gecmisViewer.scene.globe.depthTestAgainstTerrain = false;
  _gecmisViewer.scene.globe.baseColor = Cesium.Color.fromCssColorString("#0b0e11");

  // Oynatici olaylari
  document.getElementById("gcPlay").addEventListener("click", gcPlayToggle);
  document.getElementById("gcHiz").addEventListener("change", () => {
    if (_gecmisOynatici) _gecmisOynatici.hiz = parseFloat(document.getElementById("gcHiz").value);
  });
  document.getElementById("gcBar").addEventListener("input", () => {
    if (!_gecmisUcus) return;
    const oran = parseFloat(document.getElementById("gcBar").value) / 100;
    gcOynaticiKonum(Math.floor(oran * (_gecmisUcus.noktalar.length - 1)));
  });

  // v2.1.8: TUMUNU SIL (yalniz yonetici; sunucu ayrica denetler)
  const btnTumSil = document.getElementById("gcTumunuSil");
  if (btnTumSil) btnTumSil.addEventListener("click", () => {
    onayIste((t.gcTumunuSilOnay ||
      "T\u00dcM u\u00e7u\u015f ge\u00e7mi\u015fi silinsin mi? Bu i\u015flem geri al\u0131namaz."), () => {
      gcOynaticiDurdur(); gcHaritaTemizle(); _gecmisUcus = null;
      if (ws && ws.readyState === 1)
        ws.send(JSON.stringify({ tip: "gecmis_tumunu_sil" }));
    });
  });

  // v2.4.41: antetli ucus raporu
  const btnRapor = document.getElementById("gcRaporBtn");
  if (btnRapor) btnRapor.addEventListener("click", gcRaporAl);

  // v2.4.42: ucus grafikleri (zaman eksenli cok serili)
  const btnGrafik = document.getElementById("gcGrafikBtn");
  if (btnGrafik) btnGrafik.addEventListener("click", gcGrafikAc);

  // Listeyi iste
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({ tip: "dron_gecmis_liste" }));
}

// v2.4.64: TAM EKRAN gecisi.
// CSS sinifi ile pencere tum gorunume yayilir; Cesium viewer ayni
// kaldigi icin secili ucus ve oynatici durumu korunur. Cesium'un
// kendi tuvali kapsayici boyutunu otomatik izler, ancak gecis
// aninda bir kez zorlamak gerekir (resize olayi tetiklenmez).
function gcTamEkranDegistir() {
  if (!_gecmisPopup) return;
  const acik = _gecmisPopup.classList.toggle("gc-tam");
  const btn = document.getElementById("gcTamEkran");
  if (btn) {
    btn.innerHTML = acik
      ? "<i class='fa-solid fa-compress'></i>"
      : "<i class='fa-solid fa-expand'></i>";
    const t = D();
    btn.title = acik ? (t.gcTamEkranCik || "Tam ekrandan \u00e7\u0131k")
                     : (t.gcTamEkran || "Tam ekran");
  }
  // Tam ekrandan cikarken satir ici konum/boyut yeniden gecerli olur.
  // Pencere ekran disinda kalmasin diye sinirlara cekilir.
  if (!acik) {
    const r = _gecmisPopup.getBoundingClientRect();
    const x = Math.max(0, Math.min(parseFloat(_gecmisPopup.style.left) || 0,
                                   window.innerWidth - r.width));
    const y = Math.max(0, Math.min(parseFloat(_gecmisPopup.style.top) || 0,
                                   window.innerHeight - 32));
    _gecmisPopup.style.left = x + "px";
    _gecmisPopup.style.top = y + "px";
  }
  // Cesium tuvalini yeni boyuta zorla
  if (_gecmisViewer) {
    try { _gecmisViewer.resize(); } catch (e) {}
    // Bir sonraki cizim karesinde tekrar dene (gecis animasyonu bitince)
    setTimeout(() => {
      if (_gecmisViewer) { try { _gecmisViewer.resize(); } catch (e) {} }
    }, 260);
  }
}

function dronGecmisKapat() {
  gcOynaticiDurdur();
  if (_gecmisViewer) { try { _gecmisViewer.destroy(); } catch (e) {} _gecmisViewer = null; }
  if (_gecmisPopup) { _gecmisPopup.remove(); _gecmisPopup = null; }
  _gecmisUcus = null; _gecmisSecDron = null;
}

// ---------------------------------------------------------------
// WS cevaplari (ws.js yonlendirir)
// ---------------------------------------------------------------
window.dronGecmisListeIsle = function (dronlar) {
  _gecmisDronlar = dronlar || [];
  if (!_gecmisPopup) return;
  // Menuden acildiysa ilgili dronu otomatik sec
  if (_gecmisFiltreSysid !== null && !_gecmisSecDron) {
    const es = _gecmisDronlar.find(x => x.sysid === _gecmisFiltreSysid);
    if (es) _gecmisSecDron = es.anahtar;
    _gecmisFiltreSysid = null;
  }
  gcListeCiz();
};

// v2.4.42: Kayitli Dronlar panelinden cagrilir.
// History panelini acar ve verilen dronu secili hale getirir, boylece
// o dronun ucus kayitlari filtrelenmis olarak gorunur.
// Not: secim `anahtar` uzerinden yapilir (sysid degil), cunku ayni sysid
// farkli dronlarda tekrar edebilir; anahtar kalici kimlige baglidir.
window.gecmisDronaFiltrele = function (anahtar) {
  if (!anahtar) return;
  _gecmisSecDron = anahtar;
  if (!_gecmisPopup) {
    // Panel kapali: ac. Liste geldiginde secim korunur (asagidaki
    // dronGecmisListeIsle _gecmisSecDron'u ezmez).
    dronGecmisAc();
    return;
  }
  // Panel acik: listeyi tazele + secimi uygula
  if (typeof ws !== "undefined" && ws && ws.readyState === 1) {
    ws.send(JSON.stringify({ tip: "dron_gecmis_liste" }));
  }
  gcListeCiz();
  // Secili satiri gorunur alana getir
  setTimeout(() => {
    const sec = document.querySelector("#gcDronListe .gc-dron.secili");
    if (sec && sec.scrollIntoView) {
      sec.scrollIntoView({ block: "nearest" });
    }
  }, 0);
};

// v2.4.42: grafikler dugmesi -> ucus_grafik.js
function gcGrafikAc() {
  if (!_gecmisUcus) return;
  if (typeof window.ucusGrafikAc !== "function") return;
  const dr = _gecmisDronlar.find(x => x.anahtar === _gecmisUcus.anahtar) || null;
  window.ucusGrafikAc(_gecmisUcus, dr);
}

// v2.4.41: antetli rapor dugmesi -> ucus_rapor.js
function gcRaporAl() {
  const t = D();
  if (!_gecmisUcus) return;
  if (typeof window.ucusRaporAc !== "function") return;
  // Secili dronun kimlik bilgileri (isim/uid/otopilot) rapor antetinde
  // kullanilir; sol listedeki kayittan alinir.
  const dr = _gecmisDronlar.find(x => x.anahtar === _gecmisUcus.anahtar) || null;
  window.ucusRaporAc(_gecmisUcus, dr, _gecmisTespitler || [],
                     _gecmisKalkis || []);
}

window.ucusVeriIsle = function (ucus, tespitler, kalkisKontrolleri) {
  if (!_gecmisPopup) return;
  const bilgi = document.getElementById("gcBilgi");
  if (!ucus || !ucus.noktalar || ucus.noktalar.length < 2) {
    if (bilgi) bilgi.textContent = (D().gcUcusYok || "U\u00e7u\u015f verisi okunamad\u0131");
    return;
  }
  _gecmisUcus = ucus;
  _gecmisTespitler = tespitler || [];
  // v2.4.41: imzali raporun denetim izi bolumu icin saklanir
  _gecmisKalkis = kalkisKontrolleri || [];
  gcUcusCiz(ucus);
  gcTespitleriCiz();
};

// ---------------------------------------------------------------
// Sol liste cizimi
// ---------------------------------------------------------------
// FAZ18-IS22-GECMIS-FILTRE: filtre yardimcilari.
//
// Neden istemci tarafinda: `dron_gecmis_liste` yaniti TUM ucuslari
// tasiyor (sunucu sahiplik suzgecini zaten uygulamis). Filtre yalnizca
// gorunurluk daraltir; sunucuya yeni istek gerekmez.
//
// PILOT ALANI SECIMI (onemli): `sahip_eposta` kullanilir, `pilotlar`
// DEGIL. Kullanicinin baglayici kurali "takeoff'u kim verdiyse o
// ucusun sahibi odur"; `pilotlar` telemetride adi gecen herkesi
// (vardiya, gozlemci) icerir ve sahiplik kaniti degildir.
function gcFiltreDegerleri() {
  const p = document.getElementById("gcFPilot");
  const u = document.getElementById("gcFTur");
  const d = document.getElementById("gcFTarih");
  return {
    pilot: (p && p.value) || "",
    tur: (u && u.value) || "",
    tarih: (d && d.value) || "",
  };
}
// Bir ucus filtreye uyuyor mu. `dr` ucusun ait oldugu dron kaydi
// (tur filtresi dron duzeyinde cozulur; ucus kaydinda arac_tipi yok).
function gcUcusFiltredeMi(u, dr, f) {
  if (f.pilot) {
    const sahip = String((u && u.sahip_eposta) || "").toLowerCase();
    if (sahip !== f.pilot.toLowerCase()) return false;
  }
  if (f.tur) {
    // Tur adi UCUNCU bir esleme yazilmadan cozulur: dronlar.js'teki
    // dkAracTipiBilgi() kanonik kaynaktir (ucus_rapor.js:116 yorumu
    // "BIREBIR AYNI tutulur" diye uyariyor).
    const ad = (typeof dkAracTipiBilgi === "function")
      ? (dkAracTipiBilgi(dr) || {}).ad : "";
    if (String(ad) !== f.tur) return false;
  }
  if (f.tarih) {
    // <input type="date"> "YYYY-MM-DD" verir. Ucus baslangici unix
    // saniye. Yerel gun sinirlari kullanilir (kullanici yerel takvim
    // gunu bekler; UTC kaydirmasi bir onceki gunu gosterebilir).
    const p = f.tarih.split("-");
    if (p.length === 3) {
      const y = Number(p[0]), ay = Number(p[1]) - 1, g = Number(p[2]);
      const bas = new Date(y, ay, g, 0, 0, 0, 0).getTime() / 1000;
      const bit = new Date(y, ay, g, 23, 59, 59, 999).getTime() / 1000;
      const ts = Number(u && u.baslangic) || 0;
      if (ts < bas || ts > bit) return false;
    }
  }
  return true;
}
// Filtre secenekleri VERIDEN uretilir. Secenek listesi her cizimde
// yenilenir ama SECILI DEGER korunur; aksi halde kullanici bir filtre
// secer, liste tazelenir ve secim sessizce kaybolurdu.
function gcFiltreSecenekleriDoldur() {
  const pEl = document.getElementById("gcFPilot");
  const uEl = document.getElementById("gcFTur");
  if (!pEl && !uEl) return;
  const t = D();
  if (pEl) {
    const onceki = pEl.value;
    const gorulen = new Map(); // eposta -> gorunen ad
    for (const dr of _gecmisDronlar) {
      for (const u of (dr.ucuslar || [])) {
        const ep = String(u.sahip_eposta || "").trim();
        if (!ep) continue;
        if (!gorulen.has(ep.toLowerCase()))
          gorulen.set(ep.toLowerCase(), String(u.sahip_ad || ep));
      }
    }
    pEl.innerHTML = "<option value=''>" +
      (t.gcPilotTumu || "T\u00dcM P\u0130LOTLAR") + "</option>";
    for (const [ep, ad] of gorulen) {
      const o = document.createElement("option");
      o.value = ep;
      o.textContent = ad;
      pEl.appendChild(o);
    }
    pEl.value = onceki;
    // Secili pilot artik listede yoksa (kayit silinmis olabilir)
    // filtre sessizce her seyi gizlemesin: secim sifirlanir.
    if (pEl.value !== onceki) pEl.value = "";
  }
  if (uEl) {
    const onceki = uEl.value;
    const turler = new Set();
    for (const dr of _gecmisDronlar) {
      if (!(dr.ucuslar || []).length) continue;
      const ad = (typeof dkAracTipiBilgi === "function")
        ? (dkAracTipiBilgi(dr) || {}).ad : "";
      if (ad) turler.add(String(ad));
    }
    uEl.innerHTML = "<option value=''>" +
      (t.gcTurTumu || "T\u00dcM T\u00dcRLER") + "</option>";
    for (const ad of turler) {
      const o = document.createElement("option");
      o.value = ad;
      o.textContent = ad;
      uEl.appendChild(o);
    }
    uEl.value = onceki;
    if (uEl.value !== onceki) uEl.value = "";
  }
}
function gcListeCiz() {
  const kutu = document.getElementById("gcDronListe");
  if (!kutu) return;
  const t = D();
  kutu.innerHTML = "";
  // FAZ18-IS22-GECMIS-FILTRE: filtre secenekleri veriden uretilir ve
  // aktif filtre degerleri okunur.
  gcFiltreSecenekleriDoldur();
  const _f = gcFiltreDegerleri();
  const _filtreAktif = !!(_f.pilot || _f.tur || _f.tarih);
  if (_gecmisDronlar.length === 0) {
    kutu.innerHTML = "<div class='gc-bos'>" + (t.gcDronYok || "Kay\u0131tl\u0131 dron yok") + "</div>";
    return;
  }
  for (const dr of _gecmisDronlar) {
    const el = document.createElement("div");
    el.className = "gc-dron" + (dr.anahtar === _gecmisSecDron ? " secili" : "");
    el.innerHTML =
      "<span class='gc-renk' style='background:" + (dr.renk || "#888") + "'></span>" +
      "<span class='gc-dron-ad'>" + (dr.isim || ("DRON " + dr.sysid)) + "</span>" +
      "<span class='gc-dron-sayi'>" + (dr.ucuslar || []).length + "</span>";
    el.addEventListener("click", () => {
      _gecmisSecDron = (dr.anahtar === _gecmisSecDron) ? null : dr.anahtar;
      gcListeCiz();
    });
    kutu.appendChild(el);
    // Secili dronun ucus listesi
    if (dr.anahtar === _gecmisSecDron) {
      // v2.4.21: kalici dron kimlik karti (UID, kayit tarihi, kaydeden)
      kutu.appendChild(gcKimlikKarti(dr, t));
      // FAZ18-IS22-GECMIS-FILTRE: filtreye uymayan ucuslar listelenmez.
      const _hepsi = (dr.ucuslar || []).slice().reverse(); // en yeni ustte
      const ucuslar = _filtreAktif
        ? _hepsi.filter((u) => gcUcusFiltredeMi(u, dr, _f))
        : _hepsi;
      if (ucuslar.length === 0) {
        const bos = document.createElement("div");
        bos.className = "gc-bos";
        // Filtre yuzunden mi bos, gercekten kayit yok mu -- kullanici
        // ayirt edebilmeli. Aksi halde filtre acikken "kayit yok"
        // mesaji yanlis izlenim verir.
        bos.textContent = _filtreAktif
          ? (t.gcFiltreBos || "Filtreye uyan u\u00e7u\u015f yok")
          : (t.gcUcusBos || "Kay\u0131tl\u0131 u\u00e7u\u015f yok");
        kutu.appendChild(bos);
      }
      for (const u of ucuslar) {
        const ue = document.createElement("div");
        ue.className = "gc-ucus" + (_gecmisUcus && _gecmisUcus.id === u.id ? " secili" : "");
        const trh = new Date(u.baslangic * 1000);
        const gg = trh.toLocaleDateString() + " " +
          trh.toTimeString().slice(0, 5);
        // v2.4.42: pilot satirinda e-posta yerine ad soyad (varsa).
        // pilotlar_ad eski sunucuda yok -> pilotlar'a geri duser.
        const pAd = (u.pilotlar_ad && u.pilotlar_ad.length)
          ? u.pilotlar_ad : (u.pilotlar || []);
        const pilotTxt = pAd.length ? " \u00b7 " + pAd.join(", ") : "";
        // v2.4.42: kisa belge esleme kodu. Elindeki imzali ciktiyi
        // sistemde bulabilmek icin listede de gorunur.
        const kod = (typeof window.ucusKodu === "function")
          ? window.ucusKodu(u) : (u.kod || "");
        const kodTxt = kod
          ? "<span class='gc-ucus-kod' title='" +
            (t.gcKodIpucu || "Belge esleme kodu") + "'>" + kod + "</span>"
          : "";
        ue.innerHTML =
          "<i class='fa-solid fa-plane-up' style='color:" + (dr.renk || "#888") + "'></i>" +
          "<div class='gc-ucus-bilgi'>" +
            "<div class='gc-ucus-tarih'>" + gg + kodTxt + "</div>" +
            "<div class='gc-ucus-alt'>" + gcSure(u.sure) + " \u00b7 " +
              (t.gcMaxIrtifa || "maks") + " " + Math.round(u.max_irtifa || 0) + "m" +
              pilotTxt + "</div>" +
          "</div>" +
          "<button class='gc-ucus-sil' title='" + (t.gcSil || "Sil") + "'><i class='fa-solid fa-trash'></i></button>";
        ue.addEventListener("click", (ev) => {
          if (ev.target.closest(".gc-ucus-sil")) return;
          if (ws && ws.readyState === 1) ws.send(JSON.stringify({ tip: "ucus_oku", id: u.id }));
        });
        ue.querySelector(".gc-ucus-sil").addEventListener("click", (ev) => {
          ev.stopPropagation();
          onayIste((t.gcSilOnay || "Bu u\u00e7u\u015f kayd\u0131 silinsin mi?"), () => {
            if (_gecmisUcus && _gecmisUcus.id === u.id) { gcOynaticiDurdur(); gcHaritaTemizle(); _gecmisUcus = null; }
            if (ws && ws.readyState === 1) ws.send(JSON.stringify({ tip: "ucus_sil", id: u.id }));
          });
        });
        kutu.appendChild(ue);
      }
    }
  }
}

// v2.4.21: secili dronun kalici kimlik karti
//  - UID + UID kaynagi (donanim serisi mi turetilmis mi)
//  - ilk kayit tarihi ve kaydeden pilot
//  - otopilot / firmware / arac sinifi
function gcKimlikKarti(dr, t) {
  const kart = document.createElement("div");
  kart.className = "gc-kimlik";
  const kaynakAd = {
    autopilot_uid: t.gcUidDonanim || "donan\u0131m serisi",
    uid2: t.gcUidDonanim || "donan\u0131m serisi",
    dji_sn: t.gcUidDji || "DJI seri no",
    turetilmis: t.gcUidTuretilmis || "t\u00fcretilmi\u015f",
  }[dr.uid_kaynak || "turetilmis"] || (dr.uid_kaynak || "");
  const kayitTxt = dr.kayit_ts
    ? new Date(dr.kayit_ts * 1000).toLocaleString()
    : "--";
  const satir = (etiket, deger, baslik) =>
    "<div class='gc-kimlik-satir'" +
    (baslik ? " title='" + String(baslik).replace(/'/g, "") + "'" : "") +
    "><span>" + etiket + "</span><b>" + deger + "</b></div>";
  kart.innerHTML =
    satir(t.gcUid || "UID", (dr.uid || "--") +
          (kaynakAd ? " <i>(" + kaynakAd + ")</i>" : ""), dr.uid) +
    satir(t.gcKayitTarihi || "Kay\u0131t tarihi", kayitTxt) +
    satir(t.gcKaydeden || "Kaydeden pilot", dr.kaydeden || "--") +
    satir("SYSID", (dr.sysid === null || dr.sysid === undefined)
          ? "--" : dr.sysid) +
    (dr.arac_sinifi
      ? satir(t.gcAracSinifi || "Ara\u00e7 t\u00fcr\u00fc", dr.arac_sinifi) : "") +
    (dr.otopilot
      ? satir(t.gcOtopilot || "Otopilot", dr.otopilot) : "") +
    (dr.firmware
      ? satir(t.gcFirmware || "Yaz\u0131l\u0131m", dr.firmware) : "");
  return kart;
}

function gcSure(sn) {
  sn = Math.round(sn || 0);
  const dk = Math.floor(sn / 60), s = sn % 60;
  return dk + ":" + String(s).padStart(2, "0");
}

// ---------------------------------------------------------------
// Harita: ucus izi cizimi + oynatici
// ---------------------------------------------------------------
function gcHaritaTemizle() {
  if (_gecmisViewer) _gecmisViewer.entities.removeAll();
  const oy = document.getElementById("gcOynatici");
  if (oy) oy.style.display = "none";
  const ts = document.getElementById("gcTespitSerit");
  if (ts) { ts.style.display = "none"; ts.innerHTML = ""; }
  const ti = document.getElementById("gcTlIsaretler");
  if (ti) ti.innerHTML = "";
  const bilgi = document.getElementById("gcBilgi");
  if (bilgi) {
    bilgi.classList.remove("gc-bilgi-istatistik");
    bilgi.innerHTML = (D().gcUcusSec || "Soldan bir u\u00e7u\u015f se\u00e7in");
    bilgi.style.display = "";
  }
  // v2.4.41: ucus secimi kalkinca rapor dugmesi de gizlenir
  const rs = document.getElementById("gcRaporSatir");
  if (rs) rs.style.display = "none";
  // v2.4.64: ucus secimi kalkinca QR de gizlenir
  const qr = document.getElementById("gcQr");
  if (qr) { qr.style.display = "none"; qr.innerHTML = ""; }
}

// v2.4.64: Secili ucusun belge esleme kodunu QR olarak harita sag ust
// kosede gosterir. Kod ucus_uid.js ile uretilir; ayni kod antetli
// ucus raporunda ve grafik raporunda da basilir, boylece ekrandaki
// ucus ile kagit belgeler eslestirilebilir.
function gcQrCiz(ucus) {
  const kutu = document.getElementById("gcQr");
  if (!kutu) return;
  const kod = (typeof window.ucusKodu === "function")
    ? window.ucusKodu(ucus) : (ucus && ucus.kod) || "";
  if (!kod || typeof window.qrSvg !== "function") {
    kutu.style.display = "none"; kutu.innerHTML = "";
    return;
  }
  let svg = "";
  try { svg = window.qrSvg(kod, 72, 2); } catch (e) { svg = ""; }
  if (!svg) { kutu.style.display = "none"; kutu.innerHTML = ""; return; }
  const t = D();
  kutu.innerHTML = svg + "<div class='gc-qr-kod'>" + kod + "</div>";
  kutu.title = (t.gcQrIpucu || t.gcKodIpucu || "Belge eşleme kodu") +
    ": " + kod;
  kutu.style.display = "block";
}

function gcUcusCiz(ucus) {
  if (!_gecmisViewer) return;
  gcOynaticiDurdur();
  gcHaritaTemizle();
  gcListeCiz(); // secili ucusu isaretle
  gcBilgiSeritDoldur(ucus);
  // v2.4.41: ucus yuklendi -> antetli rapor alinabilir
  const rs = document.getElementById("gcRaporSatir");
  if (rs) rs.style.display = "flex";
  // v2.4.64: ucusun belge esleme kodunun QR'i harita sag ust kosede
  gcQrCiz(ucus);

  // Dronun rengini bul
  const dr = _gecmisDronlar.find(x => x.anahtar === ucus.anahtar);
  const renk = (dr && dr.renk) || "#00E5FF";
  const cRenk = Cesium.Color.fromCssColorString(renk);

  // Iz cizgisi (tum ucus)
  const pozlar = ucus.noktalar.map(n =>
    Cesium.Cartesian3.fromDegrees(n[2], n[1], Math.max(0, n[3])));
  _gecmisViewer.entities.add({
    polyline: { positions: pozlar, width: 3, material: cRenk.withAlpha(0.9) },
  });
  // Baslangic/bitis isaretleri
  const ilk = ucus.noktalar[0], son = ucus.noktalar[ucus.noktalar.length - 1];
  _gecmisViewer.entities.add({
    position: Cesium.Cartesian3.fromDegrees(ilk[2], ilk[1], Math.max(0, ilk[3])),
    point: { pixelSize: 9, color: Cesium.Color.LIME,
             disableDepthTestDistance: Number.POSITIVE_INFINITY },
    label: { text: "T/O", font: "bold 11px Consolas", fillColor: Cesium.Color.LIME,
             pixelOffset: new Cesium.Cartesian2(0, -16),
             disableDepthTestDistance: Number.POSITIVE_INFINITY },
  });
  _gecmisViewer.entities.add({
    position: Cesium.Cartesian3.fromDegrees(son[2], son[1], Math.max(0, son[3])),
    point: { pixelSize: 9, color: Cesium.Color.RED,
             disableDepthTestDistance: Number.POSITIVE_INFINITY },
    label: { text: "LAND", font: "bold 11px Consolas", fillColor: Cesium.Color.RED,
             pixelOffset: new Cesium.Cartesian2(0, -16),
             disableDepthTestDistance: Number.POSITIVE_INFINITY },
  });
  // Hareketli dron noktasi
  const oynarNokta = _gecmisViewer.entities.add({
    id: "gc_oynar",
    position: Cesium.Cartesian3.fromDegrees(ilk[2], ilk[1], Math.max(0, ilk[3])),
    billboard: {
      image: elmasIkon(renk), width: 26, height: 26,
      verticalOrigin: Cesium.VerticalOrigin.CENTER,
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    },
    label: {
      text: "", font: "bold 11px Consolas, monospace",
      fillColor: cRenk, showBackground: true,
      backgroundColor: Cesium.Color.BLACK.withAlpha(0.7),
      verticalOrigin: Cesium.VerticalOrigin.TOP,
      pixelOffset: new Cesium.Cartesian2(0, 14),
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    },
  });

  // Kameraya izi sigdir
  _gecmisViewer.flyTo(_gecmisViewer.entities, { duration: 1.2 });

  // Oynatici durumu
  _gecmisOynatici = {
    timer: null, idx: 0, oynuyor: false,
    hiz: parseFloat((document.getElementById("gcHiz") || {}).value || "1"),
    nokta: oynarNokta,
  };
  const oy = document.getElementById("gcOynatici");
  if (oy) oy.style.display = "flex";
  gcOynaticiKonum(0);
}

// Ucus ozet istatistikleri: harita altindaki bilgi seridini doldurur.
// Nokta formati: [t(sn), lat, lon, alt_rel(m), hiz(m/s), yon]
function gcBilgiSeritDoldur(ucus) {
  const bilgi = document.getElementById("gcBilgi");
  if (!bilgi) return;
  const t = D();
  const n = ucus.noktalar;

  // Toplam mesafe (haversine, ardisik noktalar)
  let mesafe = 0;
  const R = 6371000, RAD = Math.PI / 180;
  for (let i = 1; i < n.length; i++) {
    const dLat = (n[i][1] - n[i-1][1]) * RAD;
    const dLon = (n[i][2] - n[i-1][2]) * RAD;
    const a = Math.sin(dLat/2)**2 +
              Math.cos(n[i-1][1]*RAD) * Math.cos(n[i][1]*RAD) * Math.sin(dLon/2)**2;
    mesafe += 2 * R * Math.asin(Math.sqrt(a));
  }

  let maxIrtifa = 0, maxHiz = 0, hizToplam = 0;
  for (const p of n) {
    if (p[3] > maxIrtifa) maxIrtifa = p[3];
    if ((p[4] || 0) > maxHiz) maxHiz = p[4] || 0;
    hizToplam += p[4] || 0;
  }
  const sureSn = n[n.length-1][0];
  const ortHiz = sureSn > 0 ? mesafe / sureSn : (hizToplam / n.length);

  const bas = ucus.baslangic ? new Date(ucus.baslangic * 1000) : null;
  const bit = ucus.bitis ? new Date(ucus.bitis * 1000) :
              (bas ? new Date((ucus.baslangic + sureSn) * 1000) : null);
  const saat = (d) => d ? d.toLocaleTimeString([], {hour:"2-digit", minute:"2-digit", second:"2-digit"}) : "--";
  const mesafeTxt = mesafe >= 1000 ? (mesafe/1000).toFixed(2) + " km" : Math.round(mesafe) + " m";

  const hucre = (ikon, etiket, deger) =>
    "<div class='gc-bilgi-hucre'><i class='fa-solid " + ikon + "'></i>" +
    "<span class='gc-bilgi-deger'>" + deger + "</span>" +
    "<span class='gc-bilgi-etiket'>" + etiket + "</span></div>";

  bilgi.innerHTML =
    hucre("fa-calendar-days", t.gcTarih || "U\u00e7u\u015f Tarihi", bas ? bas.toLocaleDateString() : "--") +
    hucre("fa-plane-departure", t.gcTakeoffSaat || "Takeoff", saat(bas)) +
    hucre("fa-plane-arrival", t.gcLandSaat || "Land", saat(bit)) +
    hucre("fa-stopwatch", t.gcSureEtiket || "S\u00fcre", gcSure(sureSn)) +
    hucre("fa-route", t.gcMesafe || "Mesafe", mesafeTxt) +
    hucre("fa-arrow-up", t.gcMaksIrtifa || "Maks \u0130rtifa", Math.round(maxIrtifa) + " m") +
    hucre("fa-gauge-high", t.gcOrtHiz || "Ort. H\u0131z", ortHiz.toFixed(1) + " m/s (" + (ortHiz * 3.6).toFixed(1) + " km/h)") +
    hucre("fa-gauge-max", t.gcMaxHiz || "Maks H\u0131z", maxHiz.toFixed(1) + " m/s (" + (maxHiz * 3.6).toFixed(1) + " km/h)");
  bilgi.classList.add("gc-bilgi-istatistik");
  bilgi.style.display = "flex";
}

function gcOynaticiKonum(idx) {
  if (!_gecmisUcus || !_gecmisOynatici) return;
  const n = _gecmisUcus.noktalar;
  idx = Math.max(0, Math.min(idx, n.length - 1));
  _gecmisOynatici.idx = idx;
  const p = n[idx];
  _gecmisOynatici.nokta.position = Cesium.Cartesian3.fromDegrees(p[2], p[1], Math.max(0, p[3]));
  _gecmisOynatici.nokta.label.text =
    Math.round(p[3]) + "m " + (p[4] || 0).toFixed(1) + "m/s (" + ((p[4] || 0) * 3.6).toFixed(1) + "km/h)";
  const bar = document.getElementById("gcBar");
  if (bar) bar.value = Math.round(100 * idx / Math.max(1, n.length - 1));
  const zam = document.getElementById("gcZaman");
  if (zam) zam.textContent = gcSure(p[0]) + " / " + gcSure(n[n.length - 1][0]);
}

function gcPlayToggle() {
  if (!_gecmisOynatici || !_gecmisUcus) return;
  const btn = document.getElementById("gcPlay");
  if (_gecmisOynatici.oynuyor) { gcOynaticiDurdur(); return; }
  _gecmisOynatici.oynuyor = true;
  if (btn) btn.innerHTML = "<i class='fa-solid fa-pause'></i>";
  // Sondaysa basa sar
  if (_gecmisOynatici.idx >= _gecmisUcus.noktalar.length - 1) gcOynaticiKonum(0);
  const adimla = () => {
    if (!_gecmisOynatici || !_gecmisOynatici.oynuyor) return;
    const n = _gecmisUcus.noktalar;
    const i = _gecmisOynatici.idx;
    if (i >= n.length - 1) { gcOynaticiDurdur(); return; }
    gcOynaticiKonum(i + 1);
    // Gercek zaman farki / hiz kadar bekle (min 30ms)
    const dt = Math.max(0.03, (n[i + 1][0] - n[i][0]) / _gecmisOynatici.hiz);
    _gecmisOynatici.timer = setTimeout(adimla, dt * 1000);
  };
  adimla();
}

function gcOynaticiDurdur() {
  if (!_gecmisOynatici) return;
  _gecmisOynatici.oynuyor = false;
  if (_gecmisOynatici.timer) { clearTimeout(_gecmisOynatici.timer); _gecmisOynatici.timer = null; }
  const btn = document.getElementById("gcPlay");
  if (btn) btn.innerHTML = "<i class='fa-solid fa-play'></i>";
}

// ---------------------------------------------------------------
// v2.4.2: Timeline AI tespit isaretleri + tespit seridi
// ---------------------------------------------------------------
// Tespit turu -> ikon/etiket (ai_tespitler.js yardimcilari yoksa yedek)
function gcTespitTurAd(tur) {
  if (typeof window.aiTurAdi === "function") return window.aiTurAdi(tur);
  const t = D();
  const m = { yuz: t.aiTurYuz || "Y\u00fcz", plaka: t.aiTurPlaka || "Plaka",
              hava_araci: t.aiTurHava || "Hava Arac\u0131",
              insan: t.aiTurInsan || "\u0130nsan",
              kara_araci: t.aiTurKara || "Kara Arac\u0131" };
  return m[tur] || tur;
}

function gcTespitIkon(tur) {
  const m = { yuz: "fa-user", plaka: "fa-car-rear",
              hava_araci: "fa-plane-up", insan: "fa-person",
              kara_araci: "fa-truck" };
  return m[tur] || "fa-eye";
}

// Tespit ts (epoch) -> ucus ici saniye (nokta[0] goreli zamani)
function gcTespitUcusSn(ts) {
  if (!_gecmisUcus || !_gecmisUcus.baslangic) return null;
  const sn = ts - _gecmisUcus.baslangic;
  const son = _gecmisUcus.noktalar[_gecmisUcus.noktalar.length - 1][0];
  if (sn < -2 || sn > son + 2) return null; // ucus disi
  return Math.max(0, Math.min(sn, son));
}

function gcTespitleriCiz() {
  const serit = document.getElementById("gcTespitSerit");
  const isaretler = document.getElementById("gcTlIsaretler");
  if (!serit || !isaretler) return;
  serit.innerHTML = ""; isaretler.innerHTML = "";
  const t = D();
  if (!_gecmisTespitler.length) { serit.style.display = "none"; return; }
  const sonSn = _gecmisUcus.noktalar[_gecmisUcus.noktalar.length - 1][0];

  // Baslik
  const baslik = document.createElement("div");
  baslik.className = "gc-tespit-baslik";
  baslik.innerHTML = "<i class='fa-solid fa-wand-magic-sparkles'></i> " +
    (t.gcAiTespitler || "AI TESP\u0130TLER\u0130") +
    " <span class='gc-tespit-sayi'>" + _gecmisTespitler.length + "</span>";
  serit.appendChild(baslik);

  // Yatay kaydirilabilir kart seridi
  const akis = document.createElement("div");
  akis.className = "gc-tespit-akis";
  akis.addEventListener("wheel", (ev) => {
    if (ev.deltaY) { akis.scrollLeft += ev.deltaY; ev.preventDefault(); }
  }, { passive: false });

  for (const tp of _gecmisTespitler) {
    const sn = gcTespitUcusSn(tp.ts);
    const ad = tp.kisi_ad || tp.arac_plaka || tp.etiket ||
               (t.aiBilinmiyor || "Bilinmiyor");
    // Timeline isaret cizgisi
    if (sn !== null && sonSn > 0) {
      const im = document.createElement("span");
      im.className = "gc-tl-isaret" +
        (tp.seviye === "araniyor" ? " araniyor" : "");
      im.style.left = (100 * sn / sonSn) + "%";
      im.title = gcTespitTurAd(tp.tur) + ": " + ad + " (" + gcSure(sn) + ")";
      im.addEventListener("click", (ev) => {
        ev.stopPropagation();
        gcTespitGit(tp, sn);
      });
      isaretler.appendChild(im);
    }
    // Serit karti
    const kart = document.createElement("div");
    kart.className = "gc-tespit-kart" +
      (tp.seviye === "araniyor" ? " araniyor" : "");
    const foto = tp.foto ? "<img src='/" + tp.foto + "' alt=''>" :
      "<span class='gc-tespit-ikon'><i class='fa-solid " +
      gcTespitIkon(tp.tur) + "'></i></span>";
    kart.innerHTML =
      foto +
      "<div class='gc-tespit-ad'>" + ad + "</div>" +
      "<div class='gc-tespit-alt'>" + gcTespitTurAd(tp.tur) +
        (sn !== null ? " \u00b7 " + gcSure(sn) : "") + "</div>";
    kart.title = (t.gcTespitGit || "Zaman \u00e7izelgesinde g\u00f6ster") +
      (tp.klip ? " \u00b7 " + (t.gcKlipVar || "klip mevcut") : "");
    kart.addEventListener("click", () => gcTespitGit(tp, sn));
    akis.appendChild(kart);
  }
  serit.appendChild(akis);
  serit.style.display = "block";
}

// Tespite git: oynaticiyi tespit anina sar + detay penceresi ac
function gcTespitGit(tp, sn) {
  // 1) Oynaticiyi tespit anina konumla
  if (sn !== null && _gecmisUcus && _gecmisOynatici) {
    const n = _gecmisUcus.noktalar;
    let idx = 0;
    for (let i = 0; i < n.length; i++) {
      if (n[i][0] >= sn) { idx = i; break; }
      idx = i;
    }
    gcOynaticiDurdur();
    gcOynaticiKonum(idx);
  }
  // 2) Detay penceresi: ai_tespitler.js detay modali varsa onu kullan
  if (typeof window.aiTespitDetayAc === "function") {
    window.aiTespitDetayAc(tp);
    return;
  }
  // Yedek: klip varsa yeni pencerede ac
  if (tp.klip) window.open("/" + tp.klip, "_blank");
  else if (tp.foto) window.open("/" + tp.foto, "_blank");
}

// ---------------------------------------------------------------
// Baglama
// ---------------------------------------------------------------
window.dronGecmisAc = dronGecmisAc;
document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("tbDronGecmis");
  if (btn) btn.addEventListener("click", () => dronGecmisAc());
});

/* FAZ18-IS2B-IKON-METIN-SPAN */
