// =================================================================
// GOKTUNGU - RADARLAR LİSTESİ + KAYIT FORMU + HARİTA BAĞI
// Bu dosya index.html'den mekanik olarak ayrilmistir; yukleme sirasi
// index.html'deki <script> sirasina baglidir (klasik script, ortak scope).
//
// v2.4.227 (kullanici istegi): eski "RADAR AYARLARI" yuzen paneli
// (yzRadar: radar sekmeleri + tek form), Hedef Filtresi, Iz Ayarlari,
// Hedef Siniflandirma, Kayit & Tekrar Oynatma ve sol dock panelleri
// KALDIRILDI. Listedeki bir radara tiklaninca o radara OZEL yonetim
// penceresi acilir (radar_pencere.js; protokolun tum yuzeyi). Burada
// yalniz liste, kayit formu ve haritayla bag (kapsama, ikon, RTK) kalir.
// =================================================================
let sonRadar = { durum: "kapali", ip: "", port: 0, hata: "" };
let radarHedefVarliklar = {};   // id -> Cesium entity (hedefler.js)
let sonRadarHedefler = [];      // son telemetri iz listesi (hedefler.js / radar_pencere.js)
const radarHedefOzet = null;    // eski panel elemani (hedefler.js null-guvenli)

// ---------------------------------------------------------------
// v2.4.60 - SAHA MAKINESI (KOPRU) SECIMI
// ---------------------------------------------------------------
let _raKopruler = [];        // [{ornek_id, ad}] radar servisi calisan makineler
let _raKopruSecili = 0;      // 0 -> merkez karar verir

// Butun radar komutlari BU islevden gecer (kopru_ornek_id ve radar_id
// tek yerde eklenir; bir komutun sessizce baska makineye gitmesi kusuru
// zaten bir kez yasandi).
function radarGonder(paket) {
  if (typeof ws === "undefined" || !ws || ws.readyState !== 1) return false;
  if (_raKopruSecili > 0 && paket && paket.kopru_ornek_id === undefined)
    paket.kopru_ornek_id = _raKopruSecili;
  if (_raSecili > 0 && paket && paket.radar_id === undefined)
    paket.radar_id = _raSecili;
  ws.send(JSON.stringify(paket));
  return true;
}

// =================================================================
// COKLU RADAR: telemetri `radarlar: [{radar_id, isim, durum, ...}]`
// =================================================================
let radarListesi = [];
let _raSecili = 0;            // son tiklanan radar (komutlarda varsayilan)

function raSeciliRadar(){
  return radarListesi.find(r => Number(r.radar_id) === _raSecili) || radarListesi[0] || null;
}

window.radarListesiGuncelle = function(liste, eski){
  radarListesi = Array.isArray(liste) ? liste : [];
  if (typeof window.radarlarListeCiz === "function") window.radarlarListeCiz();
  if (!radarListesi.length){ if (eski) radarPaneliGuncelle(eski); return; }
  if (!radarListesi.some(r => Number(r.radar_id) === _raSecili))
    _raSecili = Number(radarListesi[0].radar_id);
  // Harita bagi: bagli bir radar varsa onu, yoksa secili radari temel al
  const temel = radarListesi.find(r => r.durum === "bagli") || raSeciliRadar();
  radarPaneliGuncelle(temel);
  for (const r of radarListesi) radarRtkUygula(r);
  if (typeof window.radarIkonlariGuncelle === "function") window.radarIkonlariGuncelle(radarListesi);
  if (typeof window.radarPencereleriTazele === "function") window.radarPencereleriTazele();
};

// program_ayar.js kopru listesi her tazelendiginde cagirir.
window.radarKopruListesiGuncelle = function (liste) {
  _raKopruler = (Array.isArray(liste) ? liste : []).filter(
    (k) => k && parseInt(k.ornek_id, 10) > 0);
  if (_raKopruSecili > 0 &&
      !_raKopruler.some((k) => parseInt(k.ornek_id, 10) === _raKopruSecili))
    _raKopruSecili = 0;
  radarKopruSeciciCiz();
};

function radarKopruSeciciCiz() {
  const sar = document.getElementById("raKopruSar");
  const sec = document.getElementById("raKopruSec");
  if (!sar || !sec) return;
  if (_raKopruler.length < 2) { sar.style.display = "none"; return; }
  sar.style.display = "";
  const t = D();
  const onceki = _raKopruSecili;
  sec.innerHTML = "";
  const bos = document.createElement("option");
  bos.value = ""; bos.textContent = t.raKopruSec || "Saha makinesi seç...";
  sec.appendChild(bos);
  for (const k of _raKopruler) {
    const o = document.createElement("option");
    o.value = String(k.ornek_id); o.textContent = k.ad; sec.appendChild(o);
  }
  sec.value = onceki > 0 ? String(onceki) : "";
}
(function raKopruSeciciBagla(){
  const sec = document.getElementById("raKopruSec");
  if (!sec) return;
  sec.addEventListener("change", (ev) => { _raKopruSecili = parseInt(ev.target.value, 10) || 0; });
  radarKopruSeciciCiz();
})();

// ---------------------------------------------------------------
// Hedef tipine gore renkler (koyu/acik tema) — hedefler.js kullanir
const RADAR_HEDEF_RENKLERI = {
  koyu: { DRON:"#ff5d5d", INSAN:"#ffc94d", ARAC:"#35d0ff",
          KUS:"#b98cff", BELIRSIZ:"#ffffff", TANIMSIZ:"#ffffff" },
  acik: { DRON:"#c22626", INSAN:"#b8860b", ARAC:"#0077b6",
          KUS:"#7b3ff2", BELIRSIZ:"#5c6b7a", TANIMSIZ:"#5c6b7a" },
};

function radarHedefRengi(tip){
  const p = RADAR_HEDEF_RENKLERI[aktifTema] || RADAR_HEDEF_RENKLERI.koyu;
  return p[tip] || p.TANIMSIZ;
}

// Elmas (baklava) sekilli hedef ikonu - dron uclarindan ayirt edilir
function elmasIkon(renk){
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 36 36">
       <polygon points="18,3 33,18 18,33 3,18"
                fill="${renk}" fill-opacity="0.85" stroke="#000" stroke-width="2"
                stroke-linejoin="round"/>
     </svg>`;
  return "data:image/svg+xml;base64," + btoa(svg);
}

// Harita bagi: kapsama halkalari / supurme / radar ikonu radar
// baglantisina baglidir (radar_gorsel.js `radarBagli`, `sonRadar`).
// v2.4.227: panel DOM'u yok; yalniz harita durumu guncellenir.
function radarPaneliGuncelle(r){
  if (!r) return;
  sonRadar = r;
  radarBagli = radarListesi.length ? radarListesi.some(x => x.durum === "bagli") : (r.durum === "bagli");
  if (typeof radarKapsamaGorunurluk === "function") radarKapsamaGorunurluk(radarBagli);
  if (typeof radarIkonGuncelle === "function") radarIkonGuncelle();
}

// Radar RTK konumu: RTK enlem/boylam degistiginde kayda yazilir; harita
// ikonu (radar_gorsel.js) kayittan konumu okur. Radar basina onbellek.
const radarRtkSon = {};   // radar_id -> {lat, lon}
function radarRtkUygula(r){
  if (!r || r.durum !== "bagli" || typeof r.lat !== "number" || typeof r.lon !== "number") return;
  const rid = Number(r.radar_id) || 0;
  const son = radarRtkSon[rid];
  if (son && Math.abs(son.lat - r.lat) < 1e-7 && Math.abs(son.lon - r.lon) < 1e-7) return;
  radarRtkSon[rid] = { lat: r.lat, lon: r.lon };
  if (rid && (r.kayit_lat == null || Math.abs(Number(r.kayit_lat) - r.lat) > 1e-6 ||
              r.kayit_lon == null || Math.abs(Number(r.kayit_lon) - r.lon) > 1e-6))
    radarGonder({tip: "radar_kaydet", radar_id: rid, lat: r.lat, lon: r.lon});
  if (!radarListesi.length && typeof gcsGuncelle === "function"){
    // eski tek radar kurulumu: merkez ikonu radar konumuna
    gcsGuncelle(r.lat, r.lon);
  }
}

// =================================================================
// RADARLAR liste paneli + radar kayit formu
// (kullanici istegi #1: "Radarlar menusu -> listeleyen yuzen panel,
//  Yeni Radar dugmesi; satira tiklaninca radarin yonetim penceresi")
// =================================================================
(function radarlarPaneli(){
  const liste = document.getElementById("radarlarListe");
  const rfId = document.getElementById("rfId"), rfIsim = document.getElementById("rfIsim");
  const rfIp = document.getElementById("rfIp"), rfPort = document.getElementById("rfPort");
  const rfLat = document.getElementById("rfLat"), rfLon = document.getElementById("rfLon");
  const baslik = document.getElementById("radarFormBaslik");
  const rfKopruSar = document.getElementById("rfKopruSar"), rfKopru = document.getElementById("rfKopru");
  // v2.4.231: merkez kipinde saha koprusu secimi zorunlu (GRCON'da radar yalniz kopruden)
  function kopruSeciciDoldur(secili){
    if (!rfKopruSar || !rfKopru) return;
    const merkez = typeof window.kopruMerkezKipiMi === "function" && window.kopruMerkezKipiMi();
    // 2.4.238: yerel kipte de gorunur; varsayilan "Merkez baglantisi" (koprusuz).
    rfKopruSar.style.display = "";
    const liste = (typeof window.kopruListesiAl === "function") ? window.kopruListesiAl() : [];
    const t = D();
    rfKopru.innerHTML = "";
    const bos = document.createElement("option"); bos.value = "";
    bos.textContent = merkez ? (t.raKopruSec || "Saha makinesi seç...")
                             : (t.bagKopruYerel || "Merkez bağlantısı (bu bilgisayar, köprüsüz)"); rfKopru.appendChild(bos);
    for (const k of liste){
      // 2.4.240: merkez kipinde yalniz CEVRIMICI kopruler secilebilir; kaydin
      // mevcut koprusu cevrimdisi olsa da (duzenleme) listede kalir.
      if (merkez && !k.cevrimici && Number(k.ornek_id) !== Number(secili || 0)) continue;
      const o = document.createElement("option"); o.value = String(k.ornek_id);
      o.textContent = (k.ad || ("#" + k.ornek_id)) + (k.cevrimici ? "" : " (" + (t.bagKopruCevrimdisi || "çevrimdışı") + ")");
      rfKopru.appendChild(o);
    }
    rfKopru.value = secili ? String(secili) : "";
  }
  const ac = id => { if (typeof window.yuzenPanelAc === "function") window.yuzenPanelAc(id); };
  const kapat = id => { const p = document.getElementById(id); if (p) p.classList.add("yuzen-gizli"); };

  window.radarFormuAc = function(r){
    const t = D();
    if (!rfId) return;
    // 2.4.240: merkezde yeni radar yalniz cevrimici kopru varken.
    if (!r && typeof window.kopruYeniKayitIzni === "function" && !window.kopruYeniKayitIzni("radar")) return;
    rfId.value = r ? String(r.radar_id) : "";
    rfIsim.value = r ? (r.isim || "") : ((t.raYeniAd || "Radar") + " " + (radarListesi.length + 1));
    rfIp.value = r ? (r.kayit_ip || "") : "";
    rfPort.value = r && r.kayit_port ? String(r.kayit_port) : "5001";
    rfLat.value = r && r.kayit_lat != null ? Number(r.kayit_lat).toFixed(6) : "";
    rfLon.value = r && r.kayit_lon != null ? Number(r.kayit_lon).toFixed(6) : "";
    if (baslik) baslik.textContent = r ? (t.panelRadarFormDuzenle || "RADARI DÜZENLE") : (t.panelRadarFormYeni || "YENİ RADAR");
    kopruSeciciDoldur(r ? r.kopru_ornek_id : null);
    ac("yzRadarForm");
    setTimeout(() => rfIsim.focus(), 50);
  };

  window.radarlarListeCiz = function(){
    if (!liste) return;
    const t = D();
    liste.innerHTML = "";
    if (!radarListesi.length){
      if (typeof bosPanelYap === "function")
        liste.appendChild(bosPanelYap(t.bosRadar || "KAYITLI RADAR YOK", "fa-solid fa-satellite-dish"));
      return;
    }
    for (const r of radarListesi){
      const sat = document.createElement("div");
      const acik = typeof window.radarPencereAcikMi === "function" && window.radarPencereAcikMi(r.radar_id);
      sat.className = "cl-satir" + (acik ? " secili" : "");
      const d = r.durum || "kapali";
      sat.innerHTML =
        "<span class='ra-nokta d-" + d + "'></span>" +
        "<div class='cl-govde'><div class='cl-ad'></div><div class='cl-alt'></div></div>" +
        "<div class='cl-dgm'>" +
          "<button type='button' class='kucuk ikincil cl-duzenle' title='" + (t.btnDuzenle || "Düzenle") + "'><i class='fa-solid fa-pen'></i></button>" +
          "<button type='button' class='kucuk tehlike ikincil cl-sil' title='" + (t.btnSil || "Sil") + "'><i class='fa-solid fa-trash'></i></button>" +
        "</div>";
      sat.querySelector(".cl-ad").textContent = r.isim || ("Radar " + r.radar_id);
      // v2.4.239: baglanti diyagrami
      if (typeof window.diyagramDugmesi === "function") sat.querySelector(".cl-dgm").appendChild(window.diyagramDugmesi("radar", r.radar_id));
      const kopruAd = (() => { if (!r.kopru_ornek_id || typeof window.kopruListesiAl !== "function") return "";
        const kk = window.kopruListesiAl().find(x => Number(x.ornek_id) === Number(r.kopru_ornek_id)); return kk ? (kk.ad || ("#" + r.kopru_ornek_id)) : ("#" + r.kopru_ornek_id); })();
      sat.querySelector(".cl-alt").textContent =
        (r.kayit_ip ? r.kayit_ip + ":" + (r.kayit_port || 5001) : (t.clAdresYok || "adres yok")) +
        "  ·  " + (t["raDurum_" + d] || d) + (kopruAd ? "  ·  " + (t.bagKopruEtiket || "KÖPRÜ") + ": " + kopruAd : "");
      sat.title = t.rpSatirIpucu || "Radar yönetim penceresini aç";
      // v2.4.227: satira tik -> o radara OZEL yonetim penceresi
      sat.addEventListener("click", () => {
        _raSecili = Number(r.radar_id);
        if (typeof window.radarPencereAc === "function") window.radarPencereAc(r.radar_id);
        window.radarlarListeCiz();
      });
      sat.querySelector(".cl-duzenle").addEventListener("click", ev => { ev.stopPropagation(); window.radarFormuAc(r); });
      sat.querySelector(".cl-sil").addEventListener("click", ev => {
        ev.stopPropagation();
        const metin = (t.onayRadarSil || "{ad} radar kaydı silinsin mi?").replace("{ad}", r.isim || ("Radar " + r.radar_id));
        const sil = () => { if (typeof window.radarPencereKapat === "function") window.radarPencereKapat(r.radar_id); radarGonder({tip: "radar_sil", radar_id: Number(r.radar_id)}); };
        if (typeof onayIste === "function") onayIste(metin, sil); else if (confirm(metin)) sil();
      });
      liste.appendChild(sat);
    }
  };

  const yeni = document.getElementById("btnRadarYeni");
  if (yeni) yeni.addEventListener("click", () => window.radarFormuAc(null));
  const kaydet = document.getElementById("btnRadarFormKaydet");
  if (kaydet) kaydet.addEventListener("click", () => {
    const t = D();
    const paket = {tip: "radar_kaydet", radar_id: parseInt(rfId.value, 10) || 0,
                   isim: rfIsim.value.trim(), ip: rfIp.value.trim(),
                   port: parseInt(rfPort.value, 10) || 5001};
    const lat = parseFloat(rfLat.value), lon = parseFloat(rfLon.value);
    paket.lat = isNaN(lat) ? "" : lat; paket.lon = isNaN(lon) ? "" : lon;
    if (!paket.isim){ rfIsim.focus(); return; }
    {
      const merkez = typeof window.kopruMerkezKipiMi === "function" && window.kopruMerkezKipiMi();
      const kid = parseInt((rfKopru && rfKopru.value) || "0", 10);
      if (merkez && !kid){
        // 2.4.240: sessiz odaklama yerine acik uyari.
        if (typeof window.uyariToastGoster === "function")
          window.uyariToastGoster({baslik: t.panelRadarFormYeni || "RADAR", mesaj: t.raKopruUyari || "Köprü seçilmeden radar kaydedilemez.", seviye: "uyari", sure: 5000, kategori: "radar"});
        if (rfKopru) rfKopru.focus(); return;
      }
      // 2.4.238: yerel kipte kopru secilmediyse null -> koprusuz (dogrudan TCP).
      paket.kopru_ornek_id = kid || null;
    }
    if (radarGonder(paket)) kapat("yzRadarForm");
  });
  const iptal = document.getElementById("btnRadarFormIptal");
  if (iptal) iptal.addEventListener("click", () => kapat("yzRadarForm"));
  const mbYeni = document.getElementById("mbRadarYeni");
  if (mbYeni) mbYeni.addEventListener("click", () => window.radarFormuAc(null));
  window.radarlarListeCiz();
})();
