// =================================================================
// GOKTUNGU - HEDEF FILTRESI + TAKIPCI PANEL KONTROLLERI
// Bu dosya index.html'den mekanik olarak ayrilmistir; yukleme sirasi
// index.html'deki <script> sirasina baglidir (klasik script, ortak scope).
// =================================================================
// Takipci panel kontrolleri: ayar degisiklikleri WS uzerinden backend'e gider
// Backend her telemetri paketinde guncel takipci_ayarlar gonderir; panel onlarla senkron kalir
(function(){
  const ss = document.getElementById("izSureSlider");
  const sd = document.getElementById("fdIzSure");
  const b = document.getElementById("btnIzTemizle");
  function sureMetni(sn){ return sn >= 60 ? (sn/60).toFixed(sn%60?1:0) + " dk" : sn + " sn"; }
  if (ss){
    ss.addEventListener("input", () => {
      const v = Number(ss.value);
      if (sd) sd.textContent = sureMetni(v);
      if (ws && ws.readyState === 1)
        ws.send(JSON.stringify({tip:"takipci_ayar",alan:"iz_gorunme_suresi",deger:v}));
    });
  }
  if (b) b.addEventListener("click", () => tumIzleriTemizle());
  // Teyit kurali (M-of-N)
  const ms = document.getElementById("mofnSec");
  const md = document.getElementById("fdMofN");
  if (ms){
    ms.addEventListener("change", () => {
      const [m, n] = ms.value.split(",").map(Number);
      if (md) md.textContent = m + "/" + n;
      if (ws && ws.readyState === 1){
        ws.send(JSON.stringify({tip:"takipci_ayar",alan:"M",deger:m}));
        ws.send(JSON.stringify({tip:"takipci_ayar",alan:"N",deger:n}));
      }
    });
  }
  // GNN iz devralma anahtari
  const gk = document.getElementById("gnnKutu");
  if (gk){
    gk.addEventListener("change", () => {
      if (ws && ws.readyState === 1)
        ws.send(JSON.stringify({tip:"takipci_ayar",alan:"gnn_acik",deger:gk.checked}));
    });
  }
})();

// ---------------------------------------------------------------
// Backend'den gelen takipci_ayarlar ile paneli senkronize et
function takipciAyarSenkron(a){
  if (!a) return;
  const ss = document.getElementById("izSureSlider");
  const sd = document.getElementById("fdIzSure");
  const ms = document.getElementById("mofnSec");
  const md = document.getElementById("fdMofN");
  const gk = document.getElementById("gnnKutu");
  function sureMetni(sn){ return sn >= 60 ? (sn/60).toFixed(sn%60?1:0) + " dk" : sn + " sn"; }
  if (ss && a.iz_gorunme_suresi !== undefined){ ss.value = a.iz_gorunme_suresi; if(sd) sd.textContent = sureMetni(a.iz_gorunme_suresi); }
  if (ms && a.M !== undefined && a.N !== undefined){
    const k = a.M + "," + a.N;
    if (["1,1","2,3","3,5","4,6"].includes(k)) ms.value = k;
    if (md) md.textContent = a.M + "/" + a.N;
  }
  if (gk && a.gnn_acik !== undefined) gk.checked = a.gnn_acik;
}

// HEDEF FILTRESI: Slider/checkbox degisiklikleri WS ile backend'e gider
// Backend filtreler uygulanmis iz listesi dondurur
// ---------------------------------------------------------------

// --- Cift uclu slider kurulumu (gorsel UI + backend'e WS komutu gonderir) ---
function ciftSliderKur(kok){
  const ad = kok.dataset.filtre;
  const sMin = kok.querySelector(".s-min");
  const sMaks = kok.querySelector(".s-maks");
  const dolgu = kok.querySelector(".ray-dolgu");
  const satir = kok.closest(".filtre-satir");
  const degerEl = satir.querySelector(".f-deger");
  const tabanMin = parseFloat(kok.dataset.min);
  const tabanMaks = parseFloat(kok.dataset.max);

  function ciz(){
    let a = parseFloat(sMin.value), b = parseFloat(sMaks.value);
    const mn = Math.min(a, b), mx = Math.max(a, b);
    const oran = (v) => ((v - tabanMin) / (tabanMaks - tabanMin)) * 100;
    dolgu.style.left = oran(mn) + "%";
    dolgu.style.width = Math.max(0, oran(mx) - oran(mn)) + "%";
    const t = D();
    let kapali = false;
    if (ad === "rcs" || ad === "hiz") kapali = (mn === -1 && mx === -1);
    if (ad === "azimut") kapali = (mn === mx);
    satir.classList.toggle("devre-disi", kapali);
    degerEl.textContent = kapali ? (t.fKapali || "KAPALI") : mn + " ~ " + mx;
  }
  function degisti(){
    ciz();
    const mn = Math.min(parseFloat(sMin.value), parseFloat(sMaks.value));
    const mx = Math.max(parseFloat(sMin.value), parseFloat(sMaks.value));
    if (ws && ws.readyState === 1){
      ws.send(JSON.stringify({tip:"filtre_ayar",alan:ad+"_min",deger:mn}));
      ws.send(JSON.stringify({tip:"filtre_ayar",alan:ad+"_maks",deger:mx}));
    }
  }
  sMin.addEventListener("input", degisti);
  sMaks.addEventListener("input", degisti);
  kok._ciz = ciz;
  ciz();
}

// --- Tip onay kutulari ---
const tfTumu = document.getElementById("tfTumu");
const tfTipler = Array.from(document.querySelectorAll(".tf-tip"));
function tipFiltreGonder(){
  let secili = [];
  if (!tfTumu.checked) secili = tfTipler.filter(c => c.checked).map(c => c.value);
  if (ws && ws.readyState === 1)
    ws.send(JSON.stringify({tip:"filtre_ayar",alan:"tip_filtre",deger:secili}));
}
tfTumu.addEventListener("change", () => {
  if (tfTumu.checked) tfTipler.forEach(c => { c.checked = false; });
  tipFiltreGonder();
});
tfTipler.forEach(c => c.addEventListener("change", () => {
  if (c.checked) tfTumu.checked = false;
  tipFiltreGonder();
}));

// --- Iz durumu onay kutulari ---
const dfDurumlar = Array.from(document.querySelectorAll(".df-durum"));
function durumFiltreGonder(){
  const secili = dfDurumlar.filter(c => c.checked).map(c => c.value);
  if (!secili.length) dfDurumlar.forEach(c => { c.checked = true; });
  const s2 = dfDurumlar.filter(c => c.checked).map(c => c.value);
  if (ws && ws.readyState === 1)
    ws.send(JSON.stringify({tip:"filtre_ayar",alan:"durum_filtre",deger:s2}));
}
dfDurumlar.forEach(c => c.addEventListener("change", durumFiltreGonder));

// Slider'lari kur (gorsel baslangic)
(function filtreBaslat(){
  document.querySelectorAll(".cift-slider").forEach(kok => ciftSliderKur(kok));
})();

// (Takipci motoru tamamen Python backend'ine tasindi - takipci.py)


// ---------------------------------------------------------------
