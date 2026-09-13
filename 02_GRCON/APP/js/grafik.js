// =================================================================
// GOKTUNGU - HEDEF SAYISI GRAFIGI
// Bu dosya index.html'den mekanik olarak ayrilmistir; yukleme sirasi
// index.html'deki <script> sirasina baglidir (klasik script, ortak scope).
// =================================================================
// HEDEF SAYISI GRAFIGI: zamana gore kayan (sonsuz) cizgi grafik
// Her telemetri paketinde aktif iz sayisi (SUZULEN haric degil; tum
// gorunen izler) 1 sn araliklarla orneklenir; canvas'ta son 5 dk
// penceresi cizilir, grafik sola dogru surekli akar.
// ---------------------------------------------------------------
const GRAFIK_PENCERE_SN = 300;   // gosterilen pencere (5 dk)
const GRAFIK_ORNEK_SN   = 1;     // ornekleme araligi
const grafikVeri = [];           // {t, n} cifti (en fazla pencere+pay)
let grafikSonOrnek = 0;

function grafikOrnekle(hedefSayisi){
  const simdi = Date.now() / 1000;
  if (simdi - grafikSonOrnek < GRAFIK_ORNEK_SN) return;
  grafikSonOrnek = simdi;
  grafikVeri.push({ t: simdi, n: hedefSayisi });
  // pencere disindaki eski ornekleri at (kucuk pay birak)
  const esik = simdi - GRAFIK_PENCERE_SN - 10;
  while (grafikVeri.length && grafikVeri[0].t < esik) grafikVeri.shift();
  grafikCiz();
}

function grafikCiz(){
  const cv = document.getElementById("hedefGrafik");
  if (!cv) return;
  // panel kapaliysa cizme (gorunmez canvas)
  if (cv.offsetParent === null) return;
  // gercek CSS boyutuna gore cozunurluk ayarla (bulanikligi onler)
  const W = cv.clientWidth || 268, H = cv.clientHeight || 120;
  if (cv.width !== W) cv.width = W;
  if (cv.height !== H) cv.height = H;
  const ctx = cv.getContext("2d");
  const koyu = !document.body.classList.contains("acik-tema");
  const arka = "#0d1218", izgara = "rgba(154,163,171,.18)",
        yazi = "#9aa3ab", cizgiR = "#6bd8b9", dolgu = "rgba(107,216,185,.15)";
  ctx.fillStyle = arka;
  ctx.fillRect(0, 0, W, H);

  const simdi = Date.now() / 1000;
  const t0 = simdi - GRAFIK_PENCERE_SN;
  const sol = 24, alt = H - 14, ust = 6;         // eksen paylari
  const gw = W - sol - 4, gh = alt - ust;

  // Y ekseni ustsiniri: en az 5, veride ustune yuvarla
  let maksN = 5;
  for (const v of grafikVeri) if (v.n > maksN) maksN = v.n;
  maksN = Math.ceil(maksN / 5) * 5;

  // yatay izgara + Y etiketleri
  ctx.font = "9px Consolas, monospace";
  ctx.textAlign = "right"; ctx.textBaseline = "middle";
  ctx.strokeStyle = izgara; ctx.fillStyle = yazi; ctx.lineWidth = 1;
  const yAdim = maksN / 5;
  for (let i = 0; i <= 5; i++){
    const yv = i * yAdim;
    const y = alt - (yv / maksN) * gh;
    ctx.beginPath(); ctx.moveTo(sol, y); ctx.lineTo(W - 4, y); ctx.stroke();
    ctx.fillText(String(yv), sol - 3, y);
  }
  // dikey izgara + zaman etiketleri (her 60 sn)
  ctx.textAlign = "center"; ctx.textBaseline = "top";
  for (let s = 60; s < GRAFIK_PENCERE_SN; s += 60){
    const x = sol + ((GRAFIK_PENCERE_SN - s) / GRAFIK_PENCERE_SN) * gw;
    ctx.beginPath(); ctx.moveTo(x, ust); ctx.lineTo(x, alt); ctx.stroke();
    ctx.fillText("-" + (s / 60) + "dk", x, alt + 2);
  }

  if (grafikVeri.length < 2) return;

  // cizgi + dolgu (basamakli: hedef sayisi ayrik deger)
  ctx.beginPath();
  let ilkX = null, sonX = null, sonY = null;
  for (const v of grafikVeri){
    if (v.t < t0) continue;
    const x = sol + ((v.t - t0) / GRAFIK_PENCERE_SN) * gw;
    const y = alt - (Math.min(v.n, maksN) / maksN) * gh;
    if (ilkX === null){ ctx.moveTo(x, y); ilkX = x; }
    else { ctx.lineTo(x, sonY); ctx.lineTo(x, y); }  // basamak
    sonX = x; sonY = y;
  }
  if (ilkX === null) return;
  ctx.strokeStyle = cizgiR; ctx.lineWidth = 1.5; ctx.stroke();
  // dolgu
  ctx.lineTo(sonX, alt); ctx.lineTo(ilkX, alt); ctx.closePath();
  ctx.fillStyle = dolgu; ctx.fill();
  // son deger noktasi + etiketi
  ctx.beginPath(); ctx.arc(sonX, sonY, 2.5, 0, Math.PI * 2);
  ctx.fillStyle = cizgiR; ctx.fill();
  ctx.textAlign = "right"; ctx.textBaseline = "bottom";
  ctx.font = "bold 10px Consolas, monospace";
  ctx.fillText(String(grafikVeri[grafikVeri.length - 1].n), sonX - 4, sonY - 2);
}

// ---------------------------------------------------------------
