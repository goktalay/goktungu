// =================================================================
// GOKTUNGU - C20 RADAR PANELI + SAGLIK + AYARLAR + RTK
// Bu dosya index.html'den mekanik olarak ayrilmistir; yukleme sirasi
// index.html'deki <script> sirasina baglidir (klasik script, ortak scope).
// =================================================================
// C20 RADAR PANELI + HARITA HEDEF GOSTERIMI
// ---------------------------------------------------------------
const radarIpGiris    = document.getElementById("radarIp");
const radarPortGiris  = document.getElementById("radarPort");
const btnRadarBaglan  = document.getElementById("btnRadarBaglan");
const radarDurumMetin = document.getElementById("radarDurumMetin");
const radarHataKutu   = document.getElementById("radarHata");
const radarHedefOzet  = document.getElementById("radarHedefOzet");

let sonRadar = { durum: "kapali", ip: "", port: 0, hata: "" };
let radarHedefVarliklar = {};   // id -> Cesium entity
let sonRadarHedefler = [];

// ---------------------------------------------------------------
// v2.4.60 - SAHA MAKINESI (KOPRU) SECIMI
// Radar, merkez sunucunun agina DEGIL kopru yaziliminin kuruldugu
// makinenin agina baglidir (orn. 192.168.8.168). Bu yuzden butun
// radar komutlari o makineye gitmelidir. Bir firmada birden fazla
// kopru varsa hangisinde radar oldugunu pilot secer; tek kopru
// varsa merkez kendisi bulur ve secici gizli kalir.
// ---------------------------------------------------------------
let _raKopruler = [];        // [{ornek_id, ad}] radar servisi calisan makineler
let _raKopruSecili = 0;      // 0 -> merkez karar verir

// Butun radar komutlari BU islevden gecer. Her cagri yerine elle
// kopru_ornek_id eklenirse biri atlanir ve o komut sessizce baska
// makineye (ya da merkeze) gider; bu kusur sinifi zaten bir kez
// yasandi.
function radarGonder(paket) {
  if (typeof ws === "undefined" || !ws || ws.readyState !== 1) return false;
  if (_raKopruSecili > 0 && paket && paket.kopru_ornek_id === undefined)
    paket.kopru_ornek_id = _raKopruSecili;
  // v2.4.190: her radar komutu SECILI radara gider.
  if (_raSecili > 0 && paket && paket.radar_id === undefined)
    paket.radar_id = _raSecili;
  ws.send(JSON.stringify(paket));
  return true;
}

// =================================================================
// v2.4.190 — COKLU RADAR: liste/sekmeler + kayit formu
// Telemetri `radarlar: [{radar_id, isim, durum, ..., konum_lat, ...}]`
// tasir; panel secili radari gosterir, komutlar radar_id ile gider.
// =================================================================
let radarListesi = [];
let _raSecili = 0;            // 0 = henuz secilmedi (ilk kayit secilir)
let _raKayitFormuDoldu = 0;   // formun hangi radar icin dolduruldugu
const raListeEl = document.getElementById("raListe");
const raIsimEl = document.getElementById("raIsim");
const raKayitLatEl = document.getElementById("raKayitLat");
const raKayitLonEl = document.getElementById("raKayitLon");
const raKonumKaynakEl = document.getElementById("raKonumKaynak");

function raSeciliRadar(){
  return radarListesi.find(r => Number(r.radar_id) === _raSecili) || radarListesi[0] || null;
}

function raListeCiz(){
  if (!raListeEl) return;
  const t = D();
  raListeEl.innerHTML = "";
  for (const r of radarListesi){
    const b = document.createElement("button");
    b.type = "button";
    b.className = "ra-sekme" + (Number(r.radar_id) === _raSecili ? " secili" : "");
    b.innerHTML = "<span class='ra-nokta d-" + (r.durum || "kapali") + "'></span>" +
      "<span>" + (r.isim || ("Radar " + r.radar_id)) + "</span>";
    b.title = (r.konum_lat != null ? Number(r.konum_lat).toFixed(5) + ", " + Number(r.konum_lon).toFixed(5) : "") ;
    b.addEventListener("click", () => { _raSecili = Number(r.radar_id); _raKayitFormuDoldu = 0; raListeCiz(); raPaneliTazele(); });
    raListeEl.appendChild(b);
  }
  const ekle = document.createElement("button");
  ekle.type = "button";
  ekle.className = "ra-sekme ra-ekle";
  ekle.innerHTML = "<i class='fa-solid fa-plus'></i>";
  ekle.title = t.btnRaEkle || "Yeni radar";
  ekle.addEventListener("click", () => {
    radarGonder({tip: "radar_kaydet", radar_id: 0,
                 isim: (t.raYeniAd || "Radar") + " " + (radarListesi.length + 1), port: 5001});
  });
  raListeEl.appendChild(ekle);
}

function raKayitFormuDoldur(r){
  if (!r) return;
  if (_raKayitFormuDoldu === Number(r.radar_id)) return;
  const odak = document.activeElement;
  if (odak && (odak === raIsimEl || odak === raKayitLatEl || odak === raKayitLonEl ||
               odak === radarIpGiris || odak === radarPortGiris)) return;
  _raKayitFormuDoldu = Number(r.radar_id);
  if (raIsimEl) raIsimEl.value = r.isim || "";
  if (raKayitLatEl) raKayitLatEl.value = (r.kayit_lat != null) ? Number(r.kayit_lat).toFixed(6) : "";
  if (raKayitLonEl) raKayitLonEl.value = (r.kayit_lon != null) ? Number(r.kayit_lon).toFixed(6) : "";
  if (radarIpGiris && !radarIpGiris.value) radarIpGiris.value = r.kayit_ip || "";
  if (radarPortGiris && r.kayit_port) radarPortGiris.value = String(r.kayit_port);
}

function raPaneliTazele(){
  const r = raSeciliRadar();
  if (!r) return;
  raKayitFormuDoldur(r);
  if (raKonumKaynakEl){
    const t = D();
    raKonumKaynakEl.textContent = (typeof r.lat === "number")
      ? (t.raKonumRtk || "Konum: RTK")
      : (r.kayit_lat != null ? (t.raKonumKayit || "Konum: kayıtlı") : (t.raKonumMerkez || "Konum: merkez"));
  }
  radarPaneliGuncelle(r);
}

window.radarListesiGuncelle = function(liste, eski){
  radarListesi = Array.isArray(liste) ? liste : [];
  if (!radarListesi.length){ if (eski) radarPaneliGuncelle(eski); return; }
  if (!radarListesi.some(r => Number(r.radar_id) === _raSecili))
    _raSecili = Number(radarListesi[0].radar_id);
  raListeCiz();
  raPaneliTazele();
  if (typeof window.radarIkonlariGuncelle === "function") window.radarIkonlariGuncelle(radarListesi);
};

(function raKayitDugmeleri(){
  const kaydet = document.getElementById("btnRaKayitKaydet");
  const sil = document.getElementById("btnRaKayitSil");
  if (kaydet) kaydet.addEventListener("click", () => {
    const r = raSeciliRadar();
    const paket = {tip: "radar_kaydet", radar_id: r ? Number(r.radar_id) : 0,
                   isim: raIsimEl ? raIsimEl.value.trim() : "",
                   ip: radarIpGiris ? radarIpGiris.value.trim() : "",
                   port: radarPortGiris ? (parseInt(radarPortGiris.value, 10) || 5001) : 5001};
    const lat = parseFloat(raKayitLatEl && raKayitLatEl.value), lon = parseFloat(raKayitLonEl && raKayitLonEl.value);
    paket.lat = isNaN(lat) ? "" : lat; paket.lon = isNaN(lon) ? "" : lon;
    _raKayitFormuDoldu = 0;
    radarGonder(paket);
  });
  if (sil) sil.addEventListener("click", () => {
    const r = raSeciliRadar();
    if (!r) return;
    const t = D();
    const metin = (t.onayRadarSil || "{ad} radar kaydı silinsin mi?").replace("{ad}", r.isim || ("Radar " + r.radar_id));
    if (typeof onayIste === "function") onayIste(metin, () => radarGonder({tip: "radar_sil", radar_id: Number(r.radar_id)}));
    else if (confirm(metin)) radarGonder({tip: "radar_sil", radar_id: Number(r.radar_id)});
  });
})();

// program_ayar.js kopru listesi her tazelendiginde cagirir.
window.radarKopruListesiGuncelle = function (liste) {
  // Liste MERKEZDEN gelir: bozuk/eksik kayit gelebilir ve radar
  // panelinin cokmesi kabul edilemez (panel cokerse pilot radari
  // hic yonetemez). Gecersiz kayitlar sessizce atilir.
  _raKopruler = (Array.isArray(liste) ? liste : []).filter(
    (k) => k && parseInt(k.ornek_id, 10) > 0);
  // Secili makine listeden DUSTUYSE secim temizlenir; aksi halde
  // kapanmis bir makineye komut gonderilmeye devam edilir ve pilot
  // ilgisiz bir hata okur.
  if (_raKopruSecili > 0 &&
      !_raKopruler.some((k) => parseInt(k.ornek_id, 10) === _raKopruSecili))
    _raKopruSecili = 0;
  radarKopruSeciciCiz();
};

function radarKopruSeciciCiz() {
  const sar = document.getElementById("raKopruSar");
  const sec = document.getElementById("raKopruSec");
  if (!sar || !sec) return;
  // Tek aday varsa secici GEREKSIZDIR: merkez zaten onu bulur.
  // Lokal kurulumda liste her zaman bostur.
  if (_raKopruler.length < 2) {
    sar.style.display = "none";
    return;
  }
  sar.style.display = "";
  const t = D();
  const onceki = _raKopruSecili;
  sec.innerHTML = "";
  const bos = document.createElement("option");
  bos.value = "";
  bos.textContent = t.raKopruSec || "Saha makinesi se\u00e7...";
  sec.appendChild(bos);
  for (const k of _raKopruler) {
    const o = document.createElement("option");
    o.value = String(k.ornek_id);
    o.textContent = k.ad;
    sec.appendChild(o);
  }
  sec.value = onceki > 0 ? String(onceki) : "";
}

// ---------------------------------------------------------------
// Hedef tipine gore renkler (koyu/acik tema)
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

function radarPaneliGuncelle(r){
  sonRadar = r;
  radarBagli = (r.durum === "bagli");
  // Radar animasyonu ve kapsama halkalari radar baglantisina bagli
  if (typeof radarKapsamaGorunurluk === "function") radarKapsamaGorunurluk(radarBagli);
  // Radar ikonunun rengi baglanti durumunu yansitir (bagli/hata/kapali)
  radarIkonGuncelle();
  // Radar RTK konumu geldiyse ikon/halka/supurme merkezini radara tasi
  radarRtkUygula(r);
  // RTK'DAN KONUM AL dugmesinin ilerleme/sonuc gostergesi
  rtkDurumGuncelle(r);
  const t = D();
  const metinler = {
    kapali:     t.radarKapali,
    baglaniyor: t.radarBaglaniyor(r.ip),
    bagli:      t.radarBagliM(r.ip, r.port),
    hata:       t.radarHataM,
  };
  radarDurumMetin.textContent = metinler[r.durum] || r.durum;
  radarDurumMetin.className = "d-" + r.durum;

  if (r.durum === "hata" && r.hata){
    radarHataKutu.textContent = r.hata;
    radarHataKutu.style.display = "block";
  } else {
    radarHataKutu.style.display = "none";
  }

  butonMetinAyarla(btnRadarBaglan, radarBagli ? t.btnRadarKes : t.btnRadarBaglan);
  btnRadarBaglan.classList.toggle("bagli", radarBagli);
  btnRadarBaglan.disabled = (r.durum === "baglaniyor") || !ws || ws.readyState !== 1;

  if (r.ayarlar) radarAyarPaneliGuncelle(r.ayarlar);

  radarSaglikGuncelle(r);
}

// --- RADAR SAGLIK TELEMETRISI ---
const radarSaglikAlan = document.getElementById("radarSaglikAlan");
function sureBicimle(sn){
  sn = Math.max(0, Math.floor(sn));
  const s = sn % 60, d = Math.floor(sn / 60) % 60, h = Math.floor(sn / 3600);
  const pp = (n) => String(n).padStart(2, "0");
  return (h > 0 ? h + ":" : "") + pp(d) + ":" + pp(s);
}
function radarSaglikGuncelle(r){
  const bagli = (r.durum === "bagli");
  radarSaglikAlan.style.display = bagli ? "" : "none";
  if (!bagli) return;
  const t = D();
  const simdi = Date.now() / 1000;
  document.getElementById("rsCalisma").textContent =
    r.baglanti_ani ? sureBicimle(simdi - r.baglanti_ani) : "-";
  document.getElementById("rsVeriHizi").textContent =
    (typeof r.veri_hizi === "number") ? r.veri_hizi.toFixed(1) + " Hz" : "-";
  const sonEl = document.getElementById("rsSonVeri");
  if (r.son_veri_ani){
    const fark = Math.max(0, simdi - r.son_veri_ani);
    sonEl.textContent = fark.toFixed(1) + " " + (t.rsSnOnce || "sn \u00f6nce");
    sonEl.style.color = fark > 5 ? "var(--kotu, #e05555)" : "";
  } else {
    sonEl.textContent = "-"; sonEl.style.color = "";
  }
  const hbEl = document.getElementById("rsHb");
  if (typeof r.hb_gecikme_ms === "number" && r.hb_gecikme_ms >= 0){
    hbEl.textContent = Math.round(r.hb_gecikme_ms) + " ms";
    hbEl.style.color = r.hb_gecikme_ms > 500 ? "var(--kotu, #e05555)" : "";
  } else {
    hbEl.textContent = "-"; hbEl.style.color = "";
  }
  document.getElementById("rsMesaj").textContent =
    (typeof r.toplam_mesaj === "number") ? String(r.toplam_mesaj) : "-";
  const crcEl = document.getElementById("rsCrc");
  crcEl.textContent = (typeof r.crc_hata === "number") ? String(r.crc_hata) : "-";
  crcEl.style.color = (r.crc_hata > 0) ? "var(--uyari, #d9a406)" : "";
}

// --- RADAR AYARLARI (USER_CFG0 + WORKING_MODE + merkez yonu) ---
const raFrekans = document.getElementById("raFrekans");
const raTespit = document.getElementById("raTespit");
const raHiz = document.getElementById("raHiz");
const raRcs = document.getElementById("raRcs");
const raMod = document.getElementById("raMod");
const raMerkezYonu = document.getElementById("raMerkezYonu");
const btnRadarAyarKaydet = document.getElementById("btnRadarAyarKaydet");
const raSonuc = document.getElementById("raSonuc");
let raKaydetBekleniyor = false;   // KAYDET sonrasi sonuc bekleme durumu
let raSonSonuc = "";              // son gosterilen sonuc (tekrar yazmayi onle)

function raOdakVar(){
  const a = document.activeElement;
  return a && (a === raFrekans || a === raTespit || a === raHiz ||
               a === raRcs || a === raMod || a === raMerkezYonu);
}

function radarAyarPaneliGuncelle(a){
  const t = D();
  // Kullanici alanlarla oynarken veya kaydetme beklerken degerleri ezme
  if (!raOdakVar() && !raKaydetBekleniyor && a.kaynak === "radar"){
    if (a.frekans !== null) raFrekans.value = String(a.frekans);
    if (a.tespit_esigi !== null) raTespit.value = String(a.tespit_esigi);
    if (a.hiz_esigi !== null) raHiz.value = String(a.hiz_esigi);
    if (a.rcs_esigi !== null) raRcs.value = String(a.rcs_esigi);
    if (a.calisma_modu) raMod.value = a.calisma_modu;
  }
  // Merkez yonu: sunucudaki kayitli deger (kullanici yazmiyorsa)
  if (document.activeElement !== raMerkezYonu && !raKaydetBekleniyor &&
      typeof a.merkez_yonu === "number"){
    raMerkezYonu.value = a.merkez_yonu.toFixed(2);
  }
  // Sonuc durumu
  let mesaj = "", renk = "var(--soluk)";
  if (a.son_sonuc === "gonderiliyor"){
    mesaj = t.raSonucGonderiliyor;
  } else if (a.son_sonuc === "ok"){
    mesaj = t.raSonucOk; renk = "#6bd8b9";
    raKaydetBekleniyor = false;
  } else if (a.son_sonuc && a.son_sonuc.startsWith("hata")){
    mesaj = t.raSonucHata(a.son_sonuc.slice(5).trim() || a.son_sonuc);
    renk = "#e05555";
    raKaydetBekleniyor = false;
  } else if (a.kaynak === "radar"){
    mesaj = t.raRadardanOkundu;
  }
  if (mesaj !== raSonSonuc){
    raSonuc.textContent = mesaj;
    raSonuc.style.color = renk;
    raSonSonuc = mesaj;
  }
}

btnRadarAyarKaydet.addEventListener("click", () => {
  if (!ws || ws.readyState !== 1) return;
  const paket = { tip: "radar_ayar_yaz" };
  const my = parseFloat(raMerkezYonu.value);
  if (!isNaN(my)) paket.merkez_yonu = ((my % 360) + 360) % 360;
  if (radarBagli){
    paket.frekans = parseInt(raFrekans.value, 10);
    paket.tespit_esigi = parseInt(raTespit.value, 10);
    paket.hiz_esigi = parseInt(raHiz.value, 10);
    paket.rcs_esigi = parseInt(raRcs.value, 10);
    paket.calisma_modu = raMod.value;
    raKaydetBekleniyor = true;
    raSonuc.textContent = D().raSonucGonderiliyor;
    raSonuc.style.color = "var(--soluk)";
    raSonSonuc = raSonuc.textContent;
  } else {
    raSonuc.textContent = D().raBagliDegil;
    raSonuc.style.color = "var(--soluk)";
    raSonSonuc = raSonuc.textContent;
  }
  radarGonder(paket);
  // Odagi birak ki telemetri guncellemeleri panelde gorunsun
  if (document.activeElement && document.activeElement.blur)
    document.activeElement.blur();
});

// --- RTK'DAN KONUM AL dugmesi ---
const btnRtkKonum = document.getElementById("btnRtkKonum");
const rtkIlerlemeKutu = document.getElementById("rtkIlerlemeKutu");
const rtkIlerlemeBar = document.getElementById("rtkIlerlemeBar");
const rtkIlerlemeYazi = document.getElementById("rtkIlerlemeYazi");
let rtkBekleniyor = false;   // dugmeye basildi, sonuc bekleniyor

btnRtkKonum.addEventListener("click", () => {
  if (!ws || ws.readyState !== 1) return;
  if (!radarBagli){
    raSonuc.textContent = D().rtkHata;
    raSonuc.style.color = "#ff6b6b";
    raSonSonuc = raSonuc.textContent;
    return;
  }
  rtkBekleniyor = true;
  btnRtkKonum.disabled = true;
  rtkIlerlemeKutu.style.display = "block";
  rtkIlerlemeBar.style.width = "0%";
  rtkIlerlemeYazi.textContent = D().rtkAliniyor;
  rtkIlerlemeYazi.style.color = "var(--soluk)";
  radarGonder({tip: "rtk_konum_al"});
  if (document.activeElement && document.activeElement.blur)
    document.activeElement.blur();
});

// Telemetri paketindeki rtk_durum / rtk_ilerleme alanlarini isler
function rtkDurumGuncelle(r){
  if (!rtkBekleniyor) return;
  if (r.rtk_durum === "aliniyor"){
    rtkIlerlemeBar.style.width = (r.rtk_ilerleme || 0) + "%";
    rtkIlerlemeYazi.textContent = D().rtkAliniyor + " %" + (r.rtk_ilerleme || 0);
  } else if (r.rtk_durum === "tamam"){
    rtkIlerlemeBar.style.width = "100%";
    rtkIlerlemeYazi.textContent = D().rtkTamam +
      (typeof r.lat === "number" ? " (" + r.lat.toFixed(6) + ", " + r.lon.toFixed(6) + ")" : "");
    rtkIlerlemeYazi.style.color = "#6bd8b9";
    rtkBekleniyor = false;
    btnRtkKonum.disabled = false;
    // RTK konumu merkez olarak uygulanir (radarRtkUygula zaten cagriliyor;
    // burada son konum degisimini zorlamak icin onbellegi sifirla)
    radarRtkSon = null;
    setTimeout(() => { rtkIlerlemeKutu.style.display = "none"; }, 4000);
  } else if (r.rtk_durum === "hata"){
    rtkIlerlemeYazi.textContent = D().rtkHata;
    rtkIlerlemeYazi.style.color = "#ff6b6b";
    rtkBekleniyor = false;
    btnRtkKonum.disabled = false;
    setTimeout(() => { rtkIlerlemeKutu.style.display = "none"; }, 4000);
  }
}

// Radar RTK konumu: radar ikonu gercek radar konumunu temsil eder.
// RTK enlem/boylam degistiginde merkez (ikon + halkalar + supurme) guncellenir.
let radarRtkSon = null;   // {lat, lon} en son uygulanan RTK konumu
function radarRtkUygula(r){
  if (!radarBagli || typeof r.lat !== "number" || typeof r.lon !== "number") return;
  if (radarRtkSon &&
      Math.abs(radarRtkSon.lat - r.lat) < 1e-7 &&
      Math.abs(radarRtkSon.lon - r.lon) < 1e-7) return;   // degisim yok
  const ilkRtk = (radarRtkSon === null);   // bu oturumda ilk RTK konumu
  radarRtkSon = { lat: r.lat, lon: r.lon };
  // v2.4.190: COKLU RADARDA RTK konumu MERKEZI TASIMAZ. Izleme orijini
  // merkez konumudur; RTK bu radarin kendi konumudur ve kayda yazilir,
  // haritada radarin kendi ikonu oraya gider (radar_gorsel.js).
  if (radarListesi.length){
    if (raKayitLatEl && document.activeElement !== raKayitLatEl) raKayitLatEl.value = r.lat.toFixed(6);
    if (raKayitLonEl && document.activeElement !== raKayitLonEl) raKayitLonEl.value = r.lon.toFixed(6);
    if (r.radar_id != null && (r.kayit_lat == null || Math.abs(Number(r.kayit_lat) - r.lat) > 1e-6 ||
        r.kayit_lon == null || Math.abs(Number(r.kayit_lon) - r.lon) > 1e-6))
      radarGonder({tip: "radar_kaydet", radar_id: Number(r.radar_id), lat: r.lat, lon: r.lon});
    return;
  }
  gcsGuncelle(r.lat, r.lon);   // (eski tek radar) ikon + kapsama halkalari + supurme merkezi
  latGiris.value = r.lat.toFixed(6);
  lonGiris.value = r.lon.toFixed(6);
  konumKaynak.textContent = D().konumKaynakRtk || "Kaynak: radar RTK";
  // Radar RTK konumu merkez icin en guvenilir kaynaktir:
  // sayfa yenilendiginde radar hala bagliysa merkez radar konumuna kilitlenir
  // (kayitli dosya konumu veya PC konumu olsa bile radar oncelik alir).
  if (ilkRtk || !merkezVar){
    merkezVar = true;
    merkezeGit(r.lat, r.lon);
    if (ws && ws.readyState === 1){
      ws.send(JSON.stringify({tip:"ayar_kaydet", lat:r.lat, lon:r.lon}));
    }
  }
}

// Saha makinesi secimi degistiginde: secim sonraki komutlara uygulanir.
// Radar zaten bagliysa DOKUNULMAZ; pilot once kesip yeni makinede
// baglar. Aksi halde iki makinede ayni radar iki kez aranabilir.
(function raKopruSeciciBagla(){
  const sec = document.getElementById("raKopruSec");
  if (!sec) return;
  sec.addEventListener("change", (ev) => {
    _raKopruSecili = parseInt(ev.target.value, 10) || 0;
  });
  radarKopruSeciciCiz();
})();

btnRadarBaglan.addEventListener("click", () => {
  if (!ws || ws.readyState !== 1) return;
  if (radarBagli || sonRadar.durum === "baglaniyor"){
    radarGonder({tip:"radar_kes"});
  } else {
    radarHataKutu.style.display = "none";
    radarGonder({
      tip: "radar_baglan",
      ip: radarIpGiris.value.trim(),
      port: parseInt(radarPortGiris.value, 10) || 5001,
    });
  }
});

// ---------------------------------------------------------------
// --- HEDEF SINIFLANDIRMA ayarlari -------------------------------
const sinifAcikKutu = document.getElementById("sinifAcik");
const sinifHassasiyetKaydirici = document.getElementById("sinifHassasiyet");
const sinifHassasiyetDeger = document.getElementById("sinifHassasiyetDeger");
let sinifAyarUygulaniyor = false;  // sunucudan gelen durumla dongusel gonderim engeli

function sinifAyarGonder(alan, deger){
  if (!ws || ws.readyState !== 1) return;
  ws.send(JSON.stringify({tip:"siniflandirma_ayar", alan, deger}));
}

sinifAcikKutu.addEventListener("change", () => {
  if (sinifAyarUygulaniyor) return;
  sinifAyarGonder("acik", sinifAcikKutu.checked);
});

// Kaydirici: surukleme sirasinda sadece gosterge, birakinca gonder
sinifHassasiyetKaydirici.addEventListener("input", () => {
  sinifHassasiyetDeger.textContent = sinifHassasiyetKaydirici.value;
});
sinifHassasiyetKaydirici.addEventListener("change", () => {
  if (sinifAyarUygulaniyor) return;
  sinifAyarGonder("hassasiyet", parseInt(sinifHassasiyetKaydirici.value, 10));
});

// Sunucudan gelen guncel durumu arayuze uygula (ws.js cagirir)
function siniflandirmaDurumUygula(ayar){
  if (!ayar) return;
  sinifAyarUygulaniyor = true;
  if (typeof ayar.acik === "boolean") sinifAcikKutu.checked = ayar.acik;
  if (typeof ayar.hassasiyet === "number"){
    sinifHassasiyetKaydirici.value = ayar.hassasiyet;
    sinifHassasiyetDeger.textContent = ayar.hassasiyet;
  }
  sinifAyarUygulaniyor = false;
}

// Baglanti kurulunca guncel ayari iste (alan gondermeden sorgula)
function siniflandirmaDurumSorgula(){
  if (!ws || ws.readyState !== 1) return;
  ws.send(JSON.stringify({tip:"siniflandirma_ayar"}));
}
