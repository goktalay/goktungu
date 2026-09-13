// =====================================================================
// UCUS_GRAFIK.JS - UCUS GRAFIKLERI (v2.4.42)
// ---------------------------------------------------------------------
// History panelindeki "GRAFIKLER" dugmesi buraya baglanir
// (gecmis.js -> gcGrafikAc -> window.ucusGrafikAc).
//
// Kullanici istegi: "hiz zaman, irtifa zaman vb... bu sistemde farkli
// parametrelerle line'lar ekleyebilelim" + "o grafigi de ayni sekilde
// YATAY antetli kagida yazdirabilelim".
//
// TASARIM KARARLARI
// -----------------
// 1) Harici grafik kutuphanesi YOK. Saha kurulumlari internetsiz
//    calisiyor; Chart.js/plotly gibi bir CDN bagimliligi eklenemez.
//    Cizim js/grafik.js ile ayni desende saf Canvas 2D ile yapilir.
//
// 2) Ek WS komutu YOK. Seriler `ucus.noktalar[]` dizisinden turetilir;
//    veri History paneli ucusu yuklerken zaten gelmis durumdadir:
//      [t_rel(sn), lat, lon, alt_rel(m), hiz(m/s), yaw(derece),
//       bat_y(%), bat_v(V)]
//    Indeks 6-7 v2.4.41'de eklendi; eski kayitlarda undefined olabilir.
//
// 3) COKLU EKSEN yerine SERI BASINA NORMALIZASYON kullanilmaz; bunun
//    yerine her seri KENDI Y EKSENINDE olceklenir ve ekseni kendi
//    renginde yazilir. Gerekce: irtifa (0-120 m), hiz (0-20 m/s) ve
//    batarya (%0-100) tek eksende cizilirse hiz egrisi tabana yapisir
//    ve okunamaz. Normalize edip "0-1" gostermek ise imzali ciktida
//    SAYISAL DEGER kaybina yol acardi; teknik belgede kabul edilemez.
//    Cozum: her seri icin sol/sag kenarda ayri etiketli eksen; en fazla
//    2 eksen basilir, digerleri icin degerler tepe/ortalama olarak
//    lejantta yazilir.
//
// 4) TURETILMIS SERILER: kat edilen mesafe (kumulatif) ve tirmanma hizi
//    (dAlt/dt) telemetride yoktur, burada hesaplanir. Tirmanma hizi
//    gurultulu oldugu icin 5 ornekli kayan ortalama ile yumusatilir;
//    yumusatma lejantta belirtilir (belge seffafligi).
//
// 5) YAZDIRMA: ucus_rapor.js ile AYNI desen (gizli iframe + tarayici
//    yazdirma motoru). Fark: `@page size: A4 landscape`. Antet
//    ur* yardimcilariyla degil, burada YENIDEN uretilir - gerekce:
//    ucus_rapor.js'teki urAntet() dosya-yerel (window'a acik degil) ve
//    o dosyanin ic sozlesmesini disa acmak iki modulu birbirine
//    kilitlerdi. Ayni gorsel dil, bagimsiz uretim.
//
// 6) QR: uçuş kodu hem okunabilir metin hem QR olarak basilir
//    (window.qrSvg, js/qr.js). Kod ucus_uid.js ile uretilir ve sunucu
//    `kod` alani varsa ONA guvenilir.
// =====================================================================
"use strict";

// ---------------------------------------------------------------
// Durum
// ---------------------------------------------------------------
let _ugPopup = null;      // acik popup DOM'u
let _ugUcus = null;       // gosterilen ucus
let _ugDron = null;       // ucusun dron kaydi (isim/uid/renk)
let _ugSeciliSeri = [];   // acik seri anahtarlari (sirali)

function ugD() {
  return (typeof D === "function") ? D() : {};
}

function ugKacis(s) {
  return String(s === null || s === undefined ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ---------------------------------------------------------------
// Yardimci hesaplar
// ---------------------------------------------------------------
// Iki nokta arasi yatay mesafe (haversine, metre).
// ucus_rapor.js'teki urMesafe ile ayni formul; o fonksiyon dosya-yerel
// oldugu icin burada bagimsiz tutulur (modul kilitlenmesini onler).
function ugMesafe(a, b) {
  const R = 6371000, RAD = Math.PI / 180;
  const dLat = (b[1] - a[1]) * RAD, dLon = (b[2] - a[2]) * RAD;
  const h = Math.sin(dLat / 2) ** 2 +
            Math.cos(a[1] * RAD) * Math.cos(b[1] * RAD) *
            Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

function ugSure(sn) {
  sn = Math.round(sn || 0);
  const s = sn % 60, dk = Math.floor(sn / 60) % 60, sa = Math.floor(sn / 3600);
  if (sa > 0) {
    return sa + ":" + String(dk).padStart(2, "0") +
           ":" + String(s).padStart(2, "0");
  }
  return dk + ":" + String(s).padStart(2, "0");
}

// Zaman ekseni etiketi: mm:ss (uzun ucusta h:mm)
function ugZamanEtiket(sn) {
  sn = Math.max(0, Math.round(sn));
  if (sn >= 3600) {
    return Math.floor(sn / 3600) + ":" +
           String(Math.floor(sn / 60) % 60).padStart(2, "0");
  }
  return Math.floor(sn / 60) + ":" + String(sn % 60).padStart(2, "0");
}

// ---------------------------------------------------------------
// SERI TANIMLARI
// ---------------------------------------------------------------
// `al(n, i, yardim)` -> deger veya null (veri yoksa null; UYDURULMAZ)
//   n      : noktalar dizisi
//   i      : nokta indeksi
//   yardim : { kumMesafe: [...] } gibi on-hesaplanmis diziler
//
// `birim`  : eksen/lejant birimi
// `renk`   : cizgi rengi (temadan bagimsiz sabit; yazdirma ciktisinda
//            da ayni renk kullanildigi icin ekran-baski tutarliligi
//            saglanir)
// `sifirTaban`: Y ekseni 0'dan baslasin mi (irtifa/hiz icin evet,
//            voltaj icin hayir - 22-25 V araligini 0'dan cizmek
//            egriyi duz cizgiye cevirirdi)
const UG_SERILER = [
  {
    anahtar: "irtifa", renk: "#4da3ff", birim: "m", sifirTaban: true,
    ad: (t) => t.ugSeriIrtifa || "\u0130rtifa",
    al: (n, i) => {
      const v = n[i][3];
      return (v === null || v === undefined || !isFinite(v)) ? null : v;
    },
  },
  {
    anahtar: "hiz", renk: "#ffb74d", birim: "m/s", sifirTaban: true,
    ad: (t) => t.ugSeriHiz || "H\u0131z",
    al: (n, i) => {
      const v = n[i][4];
      return (v === null || v === undefined || !isFinite(v)) ? null : v;
    },
  },
  {
    anahtar: "hizKmh", renk: "#ff8a65", birim: "km/h", sifirTaban: true,
    ad: (t) => t.ugSeriHizKmh || "H\u0131z (km/h)",
    al: (n, i) => {
      const v = n[i][4];
      return (v === null || v === undefined || !isFinite(v)) ? null : v * 3.6;
    },
  },
  {
    anahtar: "batY", renk: "#66bb6a", birim: "%", sifirTaban: true,
    ad: (t) => t.ugSeriBatY || "Batarya",
    al: (n, i) => {
      const v = n[i][6];
      return (v === null || v === undefined || !isFinite(v)) ? null : v;
    },
  },
  {
    anahtar: "batV", renk: "#ba68c8", birim: "V", sifirTaban: false,
    ad: (t) => t.ugSeriBatV || "Batarya voltaj\u0131",
    al: (n, i) => {
      const v = n[i][7];
      return (v === null || v === undefined || !isFinite(v) || v <= 0)
        ? null : v;
    },
  },
  {
    anahtar: "yaw", renk: "#4db6ac", birim: "\u00b0", sifirTaban: true,
    ad: (t) => t.ugSeriYaw || "Y\u00f6n (yaw)",
    al: (n, i) => {
      const v = n[i][5];
      if (v === null || v === undefined || !isFinite(v)) return null;
      // 0-360 araligina normalize (bazi kayitlarda -180..180 gelir)
      let d = v % 360;
      if (d < 0) d += 360;
      return d;
    },
  },
  {
    anahtar: "mesafe", renk: "#f06292", birim: "m", sifirTaban: true,
    ad: (t) => t.ugSeriMesafe || "Kat edilen mesafe",
    al: (n, i, y) => y.kumMesafe[i],
  },
  {
    anahtar: "tirmanma", renk: "#9575cd", birim: "m/s", sifirTaban: false,
    ad: (t) => t.ugSeriTirmanma || "T\u0131rmanma h\u0131z\u0131",
    al: (n, i, y) => y.tirmanma[i],
  },
];

function ugSeriBul(anahtar) {
  return UG_SERILER.find(s => s.anahtar === anahtar) || null;
}

// ---------------------------------------------------------------
// Turetilmis dizileri bir kez hesapla (her cizimde tekrar etmemek icin)
// ---------------------------------------------------------------
function ugYardimHesapla(n) {
  const kumMesafe = new Array(n.length);
  const hamTirmanma = new Array(n.length);
  let toplam = 0;
  kumMesafe[0] = 0;
  hamTirmanma[0] = null;
  for (let i = 1; i < n.length; i++) {
    toplam += ugMesafe(n[i - 1], n[i]);
    kumMesafe[i] = toplam;
    const dt = n[i][0] - n[i - 1][0];
    const dAlt = (n[i][3] || 0) - (n[i - 1][3] || 0);
    // dt <= 0: ayni saniyede iki ornek (veya bozuk zaman damgasi).
    // Bolme yapmak sonsuz/gurultulu deger uretir -> nokta atlanir.
    hamTirmanma[i] = (dt > 0) ? (dAlt / dt) : null;
  }
  // Tirmanma hizi tek ornekten cok gurultulu; 5 ornekli KAYAN ORTALAMA
  // uygulanir. Pencere ortalanir; kenarlarda mevcut ornekler kullanilir.
  const tirmanma = new Array(n.length);
  const P = 2;   // her iki yana 2 ornek -> pencere 5
  for (let i = 0; i < n.length; i++) {
    let top = 0, adet = 0;
    for (let k = i - P; k <= i + P; k++) {
      if (k < 0 || k >= n.length) continue;
      const v = hamTirmanma[k];
      if (v === null || v === undefined || !isFinite(v)) continue;
      top += v; adet++;
    }
    tirmanma[i] = adet ? (top / adet) : null;
  }
  return { kumMesafe, tirmanma };
}

// Bir serinin ucus boyunca degerlerini ve istatistiklerini uret.
// Donen `veri` dizisi noktalarla AYNI uzunluktadir; eksik yerler null.
function ugSeriVeri(seri, n, yardim) {
  const veri = new Array(n.length);
  let min = null, maks = null, top = 0, adet = 0;
  for (let i = 0; i < n.length; i++) {
    const v = seri.al(n, i, yardim);
    veri[i] = (v === null || v === undefined || !isFinite(v)) ? null : v;
    if (veri[i] === null) continue;
    if (min === null || veri[i] < min) min = veri[i];
    if (maks === null || veri[i] > maks) maks = veri[i];
    top += veri[i]; adet++;
  }
  return { veri, min, maks, ort: adet ? top / adet : null, adet };
}

// Seride hic gercek veri var mi? (yoksa secim listesinde pasif gosterilir)
function ugSeriVarMi(seri, n, yardim) {
  for (let i = 0; i < n.length; i++) {
    const v = seri.al(n, i, yardim);
    if (v !== null && v !== undefined && isFinite(v)) return true;
  }
  return false;
}

// Y ekseni araligi: "guzel" adimlara yuvarla
function ugEksenAralik(min, maks, sifirTaban) {
  if (min === null || maks === null) return { alt: 0, ust: 1, adim: 0.2 };
  let alt = sifirTaban ? Math.min(0, min) : min;
  let ust = maks;
  if (ust - alt < 1e-9) { ust = alt + 1; }        // sabit seri
  const kaba = (ust - alt) / 5;
  const buyukluk = Math.pow(10, Math.floor(Math.log10(kaba)));
  const oran = kaba / buyukluk;
  let adim;
  if (oran <= 1) adim = buyukluk;
  else if (oran <= 2) adim = 2 * buyukluk;
  else if (oran <= 5) adim = 5 * buyukluk;
  else adim = 10 * buyukluk;
  alt = Math.floor(alt / adim) * adim;
  ust = Math.ceil(ust / adim) * adim;
  return { alt, ust, adim };
}

function ugSayiYaz(v, adim) {
  if (v === null || v === undefined) return "--";
  const basamak = adim >= 10 ? 0 : (adim >= 1 ? 0 : (adim >= 0.1 ? 1 : 2));
  return v.toFixed(basamak);
}

// ---------------------------------------------------------------
// CIZIM
// ---------------------------------------------------------------
// `hedef` bir <canvas>. `secenek`:
//   { baski: bool }  -> baski modunda arka plan BEYAZ, yazilar siyah
//                       (ekranda koyu tema; kagitta mürekkep tasarrufu
//                        ve okunurluk icin ters cevrilir)
function ugCiz(hedef, ucus, seriAnahtarlar, secenek) {
  secenek = secenek || {};
  const baski = !!secenek.baski;
  const t = ugD();
  const n = (ucus && ucus.noktalar) || [];
  if (!hedef || n.length < 2) return;

  // Cozunurluk: ekranda devicePixelRatio ile keskinlestir; baskida
  // sabit 2x kullanilir (yazdirma DPI'i canvas'a yansimaz, bu yuzden
  // PNG'yi buyuk uretip kucuk yerlestirmek gerekir).
  const dpr = baski ? 2 : (window.devicePixelRatio || 1);
  const W = secenek.genislik || hedef.clientWidth || 900;
  const H = secenek.yukseklik || hedef.clientHeight || 380;
  hedef.width = Math.round(W * dpr);
  hedef.height = Math.round(H * dpr);
  const ctx = hedef.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  const arka = baski ? "#ffffff" : "#0d1218";
  const izgara = baski ? "rgba(0,0,0,.13)" : "rgba(154,163,171,.18)";
  const yaziR = baski ? "#333333" : "#9aa3ab";
  ctx.fillStyle = arka;
  ctx.fillRect(0, 0, W, H);

  const yardim = ugYardimHesapla(n);
  const seciliTanim = (seriAnahtarlar || [])
    .map(ugSeriBul).filter(Boolean);
  const seriler = seciliTanim.map(s => ({
    tanim: s, ...ugSeriVeri(s, n, yardim),
  })).filter(s => s.adet > 0);

  const sureSn = n[n.length - 1][0] || 1;

  // Eksen paylari: solda 1., sagda 2. seri ekseni. Lejant grafigin
  // ALTINDA ayri seritte cizilir (ustte cizmek grafik alanini kirpiyordu).
  const solPay = 46;
  const sagPay = seriler.length > 1 ? 46 : 12;
  const ustPay = 10;
  const lejantY = H - 22;
  const altPay = 40;                  // zaman etiketi + lejant
  const x0 = solPay, x1 = W - sagPay;
  const y0 = ustPay, y1 = H - altPay;
  const gw = x1 - x0, gh = y1 - y0;

  if (gw <= 10 || gh <= 10) return;

  // Cerceve
  ctx.strokeStyle = izgara;
  ctx.lineWidth = 1;
  ctx.strokeRect(x0, y0, gw, gh);

  ctx.font = "9px Consolas, monospace";
  ctx.fillStyle = yaziR;

  // --- Zaman ekseni (X) ---
  // Etiket adimi: yaklasik 6 bolum, "guzel" saniye adimlarina yuvarlanir
  const xAdimAdaylar = [5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600];
  let xAdim = xAdimAdaylar[xAdimAdaylar.length - 1];
  for (const a of xAdimAdaylar) {
    if (sureSn / a <= 8) { xAdim = a; break; }
  }
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  for (let s = 0; s <= sureSn + 1e-6; s += xAdim) {
    const x = x0 + (s / sureSn) * gw;
    if (x > x1 + 0.5) break;
    ctx.strokeStyle = izgara;
    ctx.beginPath();
    ctx.moveTo(x, y0); ctx.lineTo(x, y1); ctx.stroke();
    ctx.fillStyle = yaziR;
    ctx.fillText(ugZamanEtiket(s), x, y1 + 4);
  }
  // X ekseni basligi
  ctx.textAlign = "right";
  ctx.fillStyle = yaziR;
  ctx.fillText(t.ugZamanEksen || "s\u00fcre (dk:sn)", x1, y1 + 16);

  if (!seriler.length) {
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = "11px 'Segoe UI', Arial, sans-serif";
    ctx.fillStyle = yaziR;
    ctx.fillText(t.ugSeriYok || "Seri se\u00e7ilmedi",
                 x0 + gw / 2, y0 + gh / 2);
    return;
  }

  // --- Her seri icin kendi olcegi ---
  const olcekler = seriler.map(s =>
    ugEksenAralik(s.min, s.maks, s.tanim.sifirTaban));

  // Y eksenleri: en fazla 2 (sol = 1. seri, sag = 2. seri).
  // Yatay izgara SADECE sol eksene gore cizilir; iki farkli izgara
  // ust uste binince grafik okunamaz hale geliyordu.
  const solOlcek = olcekler[0];
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (let v = solOlcek.alt; v <= solOlcek.ust + 1e-9; v += solOlcek.adim) {
    const y = y1 - ((v - solOlcek.alt) / (solOlcek.ust - solOlcek.alt)) * gh;
    ctx.strokeStyle = izgara;
    ctx.beginPath();
    ctx.moveTo(x0, y); ctx.lineTo(x1, y); ctx.stroke();
    ctx.fillStyle = seriler[0].tanim.renk;
    ctx.fillText(ugSayiYaz(v, solOlcek.adim), x0 - 4, y);
  }
  // Sol eksen birimi
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  ctx.fillStyle = seriler[0].tanim.renk;
  ctx.fillText(seriler[0].tanim.birim, 3, y0);

  if (seriler.length > 1) {
    const sagOlcek = olcekler[1];
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    for (let v = sagOlcek.alt; v <= sagOlcek.ust + 1e-9; v += sagOlcek.adim) {
      const y = y1 - ((v - sagOlcek.alt) /
                      (sagOlcek.ust - sagOlcek.alt)) * gh;
      ctx.fillStyle = seriler[1].tanim.renk;
      ctx.fillText(ugSayiYaz(v, sagOlcek.adim), x1 + 4, y);
    }
    ctx.textAlign = "right";
    ctx.textBaseline = "top";
    ctx.fillStyle = seriler[1].tanim.renk;
    ctx.fillText(seriler[1].tanim.birim, W - 3, y0);
  }

  // --- Egriler ---
  for (let si = 0; si < seriler.length; si++) {
    const s = seriler[si];
    const o = olcekler[si];
    const yayilim = (o.ust - o.alt) || 1;
    ctx.strokeStyle = s.tanim.renk;
    ctx.lineWidth = baski ? 1.4 : 1.6;
    ctx.lineJoin = "round";
    ctx.beginPath();
    let kalemDe = false;
    for (let i = 0; i < n.length; i++) {
      const v = s.veri[i];
      if (v === null) { kalemDe = false; continue; }   // bosluk: kesik ciz
      const x = x0 + ((n[i][0] || 0) / sureSn) * gw;
      const y = y1 - ((v - o.alt) / yayilim) * gh;
      if (!kalemDe) { ctx.moveTo(x, y); kalemDe = true; }
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  // --- Lejant (grafigin altinda) ---
  ctx.font = "9px 'Segoe UI', Arial, sans-serif";
  ctx.textBaseline = "middle";
  ctx.textAlign = "left";
  let lx = x0;
  for (let si = 0; si < seriler.length; si++) {
    const s = seriler[si];
    const o = olcekler[si];
    const eksenNot = si === 0 ? " \u25c0" : (si === 1 ? " \u25b6" : "");
    const metin = s.tanim.ad(t) + eksenNot + "  " +
      "max " + ugSayiYaz(s.maks, o.adim) + " " + s.tanim.birim +
      " \u00b7 " + (t.ugOrt || "ort") + " " +
      ugSayiYaz(s.ort, o.adim) + " " + s.tanim.birim;
    const gen = ctx.measureText(metin).width + 22;
    if (lx + gen > x1 && lx > x0) break;   // sigmayan seri lejanti atlanir
    ctx.fillStyle = s.tanim.renk;
    ctx.fillRect(lx, lejantY - 3, 12, 3);
    ctx.fillStyle = baski ? "#222" : "#c8cfd6";
    ctx.fillText(metin, lx + 16, lejantY - 1);
    lx += gen;
  }
}

// ---------------------------------------------------------------
// EKRAN PENCERESI
// ---------------------------------------------------------------
function ucusGrafikAc(ucus, dron) {
  if (!ucus || !ucus.noktalar || ucus.noktalar.length < 2) return;
  _ugUcus = ucus;
  _ugDron = dron || null;

  const t = ugD();
  const n = ucus.noktalar;
  const yardim = ugYardimHesapla(n);

  // Varsayilan secim: irtifa + hiz (kullanicinin ornek verdigi ikili).
  // Yalnizca GERCEK veri iceren seriler secilir.
  if (!_ugSeciliSeri.length) {
    for (const a of ["irtifa", "hiz"]) {
      const s = ugSeriBul(a);
      if (s && ugSeriVarMi(s, n, yardim)) _ugSeciliSeri.push(a);
    }
    if (!_ugSeciliSeri.length) {
      const ilk = UG_SERILER.find(s => ugSeriVarMi(s, n, yardim));
      if (ilk) _ugSeciliSeri.push(ilk.anahtar);
    }
  }
  // Bu ucusta verisi olmayan seriler secimden dusurulur (onceki
  // ucustan tasinmis secim bos grafik gostermesin)
  _ugSeciliSeri = _ugSeciliSeri.filter(a => {
    const s = ugSeriBul(a);
    return s && ugSeriVarMi(s, n, yardim);
  });

  if (_ugPopup) { _ugPopup.remove(); _ugPopup = null; }

  const pop = document.createElement("div");
  pop.className = "ug-popup";
  _ugPopup = pop;

  const dronAd = (dron && dron.isim) || ucus.isim ||
    ("DRON " + (ucus.sysid !== null && ucus.sysid !== undefined
                ? ucus.sysid : "?"));
  const kod = (typeof window.ucusKodu === "function")
    ? window.ucusKodu(ucus) : "";

  // Baslik: History/ARM check ile ayni tasinabilir mini popup deseni
  const bas = dkMiniPopupBaslikKur(
    pop, (t.ugBaslik || "U\u00c7U\u015e GRAF\u0130KLER\u0130") + " \u2013 " + dronAd,
    "ucusGrafik", "fa-chart-line");
  const kapatBtn = pop.querySelector(".dk-mp-kapat");
  if (kapatBtn) {
    kapatBtn.addEventListener("click", () => {
      _ugPopup = null;
    });
  }
  // v2.4.64 (kullanici istegi): yazdirma dugmesi ARTIK BASLIKTA DEGIL.
  // Baslikta yalniz ikon olarak duruyordu; kullanici "en uste print
  // seklinde koymussun, alta normal dugme olarak koy" dedi. Dugme alt
  // seride (.ug-alt) YAZILI dugme olarak tasindi -> asagida govde
  // HTML'inde uretiliyor.

  const govde = document.createElement("div");
  govde.className = "ug-govde";

  // Ust serit: uçuş kodu + seri secim dugmeleri
  let secHtml = "";
  for (const s of UG_SERILER) {
    const var_ = ugSeriVarMi(s, n, yardim);
    const acik = _ugSeciliSeri.indexOf(s.anahtar) >= 0;
    secHtml +=
      "<button class='ug-seri" + (acik ? " acik" : "") +
        (var_ ? "" : " yok") + "'" +
        " data-seri='" + ugKacis(s.anahtar) + "'" +
        (var_ ? "" : " disabled title='" +
          ugKacis(t.ugVeriYok || "Bu u\u00e7u\u015fta veri yok") + "'") +
        ">" +
        "<span class='ug-seri-renk' style='background:" + s.renk + "'></span>" +
        ugKacis(s.ad(t)) +
      "</button>";
  }

  govde.innerHTML =
    "<div class='ug-ust'>" +
      "<div class='ug-seriler'>" + secHtml + "</div>" +
    "</div>" +
    "<div class='ug-tuval-kutu'>" +
      "<canvas id='ugTuval' class='ug-tuval'></canvas>" +
    "</div>" +
    "<div class='ug-alt'>" +
      "<span class='ug-kod-etiket'>" +
        ugKacis(t.ugKod || "U\u00c7U\u015e KODU") + "</span>" +
      "<span class='ug-kod'>" + ugKacis(kod || "--") + "</span>" +
      "<span class='ug-bosluk'></span>" +
      "<span class='ug-ozet' id='ugOzet'></span>" +
      // v2.4.64: yazili yazdirma dugmesi (ucus_gecmisi'ndeki "Rapor
      // olarak indir" dugmesiyle ayni gorsel dil)
      "<button class='ug-yazdir-btn' id='ugYazdirBtn' title='" +
        ugKacis(t.ugYazdirIpucu ||
          "Yatay antetli k\u00e2\u011f\u0131da yazd\u0131r") + "'>" +
        "<i class='fa-solid fa-file-lines'></i> " +
        ugKacis(t.ugYazdirBtn || "Rapor olarak \u00e7\u0131kt\u0131 al") +
      "</button>" +
    "</div>";
  pop.appendChild(govde);
  document.body.appendChild(pop);

  // Seri dugmeleri
  for (const b of pop.querySelectorAll(".ug-seri")) {
    b.addEventListener("click", () => {
      const a = b.getAttribute("data-seri");
      const i = _ugSeciliSeri.indexOf(a);
      if (i >= 0) _ugSeciliSeri.splice(i, 1);
      else _ugSeciliSeri.push(a);
      b.classList.toggle("acik", _ugSeciliSeri.indexOf(a) >= 0);
      ugEkranCiz();
    });
  }

  // v2.4.64: alt seritteki yazili yazdirma dugmesi. Onceki surumde
  // olay basliktaki ikona bagliydi; ikon kaldirildigi icin baglama
  // buraya tasindi.
  const yazBtn = pop.querySelector("#ugYazdirBtn");
  if (yazBtn) {
    yazBtn.addEventListener("click", (ev) => {
      ev.stopPropagation();
      ucusGrafikYazdir();
    });
  }

  // Ozet satiri
  const ozet = pop.querySelector("#ugOzet");
  if (ozet) {
    const sureSn = n[n.length - 1][0] || 0;
    ozet.textContent =
      (t.ugOzetSure || "S\u00fcre") + ": " + ugSure(sureSn) + "  \u00b7  " +
      (t.ugOzetOrnek || "\u00d6rnek") + ": " + n.length;
  }

  ugEkranCiz();

  // Pencere yeniden boyutlanirsa canvas'i tazele. Popup kapandiginda
  // dinleyici birakmamak icin varliga bagli kontrol yapilir.
  if (!window._ugResizeBagli) {
    window.addEventListener("resize", () => {
      if (_ugPopup && _ugPopup.isConnected) ugEkranCiz();
    });
    window._ugResizeBagli = true;
  }
}

function ugEkranCiz() {
  if (!_ugPopup || !_ugUcus) return;
  const cv = _ugPopup.querySelector("#ugTuval");
  if (!cv) return;
  ugCiz(cv, _ugUcus, _ugSeciliSeri, { baski: false });
}

// ---------------------------------------------------------------
// YATAY ANTETLI YAZDIRMA
// ---------------------------------------------------------------
// Antet ucus_rapor.js ile ayni gorsel dilde, bagimsiz uretilir.
function ugAntet(sirket, t) {
  const logo = (sirket && sirket.logo_var && sirket.logo_url)
    ? "<img class='ug-logo' src='" + ugKacis(sirket.logo_url) + "' alt=''>"
    : "";
  const satirlar = [];
  if (sirket && sirket.adres) satirlar.push(ugKacis(sirket.adres));
  const iletisim = [];
  if (sirket && sirket.telefon) {
    iletisim.push((t.urTel || "Tel") + ": " + ugKacis(sirket.telefon));
  }
  if (sirket && sirket.eposta) iletisim.push(ugKacis(sirket.eposta));
  if (sirket && sirket.web) iletisim.push(ugKacis(sirket.web));
  if (iletisim.length) satirlar.push(iletisim.join(" \u00b7 "));
  if (sirket && sirket.vergi_no) {
    satirlar.push((t.urVergiNo || "Vergi/Sicil No") + ": " +
                  ugKacis(sirket.vergi_no));
  }
  return "<div class='ug-antet'>" + logo +
    "<div class='ug-antet-metin'>" +
      "<div class='ug-unvan'>" +
        ugKacis((sirket && sirket.unvan) || "") + "</div>" +
      satirlar.map(s => "<div class='ug-antet-satir'>" + s + "</div>")
        .join("") +
    "</div></div>";
}

// Ucus kodu blogu: QR + okunabilir kod.
// QR'in yaninda kodun METIN olarak da basilmasi ZORUNLU: QR okunamayan
// bir fotokopi/faks ciktisinda belge yine eslestirilebilir olmali.
function ugKodBlok(ucus, t) {
  const kod = (typeof window.ucusKodu === "function")
    ? window.ucusKodu(ucus) : "";
  if (!kod) return "";
  let qr = "";
  if (typeof window.qrSvg === "function") {
    try {
      qr = window.qrSvg(kod, 78, 2);
    } catch (e) {
      qr = "";   // QR uretilemezse belge kod metniyle basilmaya devam eder
    }
  }
  return "<div class='ug-kod-blok'>" +
    (qr ? "<div class='ug-qr'>" + qr + "</div>" : "") +
    "<div class='ug-kod-metin'>" +
      "<div class='ug-kod-bas'>" +
        ugKacis(t.ugKod || "U\u00c7U\u015e KODU") + "</div>" +
      "<div class='ug-kod-deger'>" + ugKacis(kod) + "</div>" +
    "</div></div>";
}

function ugYazdirStil() {
  return "" +
  // Kullanici istegi: YATAY antetli kagit
  "@page { size: A4 landscape; margin: 12mm 12mm 10mm 12mm; }" +
  "* { box-sizing: border-box; }" +
  "body { font-family: 'Segoe UI', Arial, Helvetica, sans-serif;" +
  "       color: #111; font-size: 10pt; margin: 0; }" +
  ".ug-ust-satir { display: flex; align-items: flex-start;" +
  "       gap: 14px; border-bottom: 2px solid #111; padding-bottom: 7px; }" +
  ".ug-antet { display: flex; align-items: center; gap: 12px;" +
  "       flex: 1 1 auto; min-width: 0; }" +
  ".ug-logo { height: 54px; width: auto; max-width: 140px;" +
  "       object-fit: contain; }" +
  ".ug-unvan { font-size: 14pt; font-weight: 700; letter-spacing: .2px; }" +
  ".ug-antet-satir { font-size: 8.4pt; color: #333; margin-top: 1px; }" +
  ".ug-kod-blok { display: flex; align-items: center; gap: 8px;" +
  "       flex: 0 0 auto; border: 1px solid #999; padding: 5px 8px; }" +
  ".ug-qr svg { display: block; }" +
  ".ug-kod-bas { font-size: 7pt; color: #555; letter-spacing: .8px; }" +
  ".ug-kod-deger { font-family: Consolas, 'Courier New', monospace;" +
  "       font-size: 13pt; font-weight: 700; letter-spacing: 1px; }" +
  "h1 { font-size: 12pt; text-align: center; margin: 10px 0 8px;" +
  "     letter-spacing: 1.4px; }" +
  ".ug-kimlik { width: 100%; border-collapse: collapse;" +
  "     margin-bottom: 8px; }" +
  ".ug-kimlik th, .ug-kimlik td { border: 1px solid #bbb;" +
  "     padding: 3px 6px; font-size: 8.6pt; text-align: left; }" +
  ".ug-kimlik th { background: #f0f0f0; font-weight: 600;" +
  "     white-space: nowrap; }" +
  ".ug-grafik-img { display: block; width: 100%; height: auto;" +
  "     border: 1px solid #bbb; }" +
  ".ug-seri-tablo { width: 100%; border-collapse: collapse;" +
  "     margin-top: 8px; }" +
  ".ug-seri-tablo th, .ug-seri-tablo td { border: 1px solid #bbb;" +
  "     padding: 3px 6px; font-size: 8.6pt; text-align: center; }" +
  ".ug-seri-tablo th { background: #f0f0f0; font-weight: 600; }" +
  ".ug-seri-tablo td:first-child { text-align: left; }" +
  ".ug-seri-nokta { display: inline-block; width: 9px; height: 9px;" +
  "     margin-right: 5px; vertical-align: -1px; }" +
  ".ug-imza-satir { display: flex; gap: 18px; margin-top: 12px;" +
  "     page-break-inside: avoid; }" +
  ".ug-imza { flex: 1 1 0; border: 1px solid #999;" +
  "     padding: 7px 10px 9px; }" +
  ".ug-imza-rol { font-size: 8.6pt; font-weight: 700; letter-spacing: .6px;" +
  "     border-bottom: 1px solid #ccc; padding-bottom: 3px;" +
  "     margin-bottom: 6px; }" +
  ".ug-imza-alan { display: flex; gap: 6px; font-size: 8.6pt;" +
  "     margin-top: 8px; align-items: flex-end; }" +
  ".ug-imza-alan span { color: #555; min-width: 54px; }" +
  ".ug-imza-alan b { flex: 1 1 auto; border-bottom: 1px dotted #777;" +
  "     min-height: 14px; font-weight: 500; }" +
  ".ug-imza-cizgi b { min-height: 30px; border-bottom: 1px solid #333; }" +
  ".ug-altbilgi { margin-top: 10px; padding-top: 4px;" +
  "     border-top: 1px solid #ccc; font-size: 7.6pt; color: #555;" +
  "     text-align: center; }";
}

function ucusGrafikYazdir() {
  const t = ugD();
  const ucus = _ugUcus;
  if (!ucus || !ucus.noktalar || ucus.noktalar.length < 2) return;

  // Sirket bilgisi ZORUNLU: antetsiz resmi cikti uretilmez
  // (ucus_rapor.js ile ayni kural).
  const sirket = (typeof window.sirketBilgi === "function")
    ? window.sirketBilgi() : null;
  // v2.4.64 DUZELTME: uyariToastGoster TEK nesne alir
  // ({seviye, kategori, mesaj}) - uyari_merkezi.js:65. Onceki kod uc
  // ayri dize gonderiyordu; ilk arguman dize oldugu icin `uyari.mesaj`
  // undefined kaliyor ve BOS bildirim cikiyordu. Kullanicinin gordugu
  // belirti: "dugmeye basiyorum, hicbir sey olmuyor".
  if (!sirket || !sirket.unvan) {
    if (typeof window.uyariToastGoster === "function") {
      window.uyariToastGoster({
        seviye: "hata",
        kategori: t.ugYazdirHataBaslik || "\u00c7IKTI ALINAMADI",
        mesaj: t.gcRaporSirketYok ||
               "\u015eirket bilgileri tan\u0131ml\u0131 de\u011fil.",
      });
    }
    return;
  }
  if (!_ugSeciliSeri.length) {
    if (typeof window.uyariToastGoster === "function") {
      window.uyariToastGoster({
        seviye: "uyari",
        kategori: t.ugYazdirHataBaslik || "\u00c7IKTI ALINAMADI",
        mesaj: t.ugSeriSecin || "En az bir seri se\u00e7in.",
      });
    }
    return;
  }

  const n = ucus.noktalar;
  const yardim = ugYardimHesapla(n);

  // Baski icin AYRI canvas: ekran canvas'i CSS boyutunda; kagit orani
  // farkli oldugu icin yeniden cizilir (A4 yatay yazi alani ~273 mm).
  const gecici = document.createElement("canvas");
  ugCiz(gecici, ucus, _ugSeciliSeri,
        { baski: true, genislik: 1040, yukseklik: 380 });
  const png = gecici.toDataURL("image/png");

  // Kimlik tablosu
  const dronAd = (_ugDron && _ugDron.isim) || ucus.isim ||
    ("DRON " + (ucus.sysid !== null && ucus.sysid !== undefined
                ? ucus.sysid : "?"));
  const bas = ucus.baslangic ? new Date(ucus.baslangic * 1000) : null;
  const sureSn = n[n.length - 1][0] || 0;
  const pilotAdlar = (ucus.pilotlar_ad || []).filter(Boolean);
  const pilotlar = (ucus.pilotlar || []).filter(Boolean);
  const pilotKaynak = pilotAdlar.length ? pilotAdlar : pilotlar;
  const pilotAd = pilotKaynak.length ? pilotKaynak.join(", ") : "--";

  const kimlik = "<table class='ug-kimlik'><tr>" +
    "<th>" + ugKacis(t.urDron || "Hava arac\u0131") + "</th>" +
    "<td>" + ugKacis(dronAd) + "</td>" +
    "<th>" + ugKacis(t.urPilot || "Pilot") + "</th>" +
    "<td>" + ugKacis(pilotAd) + "</td>" +
    "<th>" + ugKacis(t.urTarih || "U\u00e7u\u015f tarihi") + "</th>" +
    "<td>" + ugKacis(bas ? bas.toLocaleString() : "--") + "</td>" +
    "<th>" + ugKacis(t.urSure || "U\u00e7u\u015f s\u00fcresi") + "</th>" +
    "<td>" + ugKacis(ugSure(sureSn)) + "</td>" +
    "<th>" + ugKacis(t.urOrnek || "Telemetri \u00f6rne\u011fi") + "</th>" +
    "<td>" + n.length + "</td>" +
  "</tr></table>";

  // Seri ozet tablosu: grafikteki her egrinin sayisal karsiligi.
  // Gerekce: grafik gorseldir; imzali belgede olculen degerler
  // sayisal olarak da yer almalidir.
  let seriTablo = "<table class='ug-seri-tablo'><thead><tr>" +
    "<th>" + ugKacis(t.ugSeri || "Seri") + "</th>" +
    "<th>" + ugKacis(t.ugMin || "En k\u00fc\u00e7\u00fck") + "</th>" +
    "<th>" + ugKacis(t.ugMaks || "En b\u00fcy\u00fck") + "</th>" +
    "<th>" + ugKacis(t.ugOrtalama || "Ortalama") + "</th>" +
    "<th>" + ugKacis(t.ugBirim || "Birim") + "</th>" +
    "<th>" + ugKacis(t.ugOrnekAdet || "\u00d6rnek") + "</th>" +
  "</tr></thead><tbody>";
  for (const a of _ugSeciliSeri) {
    const s = ugSeriBul(a);
    if (!s) continue;
    const d = ugSeriVeri(s, n, yardim);
    if (!d.adet) continue;
    const o = ugEksenAralik(d.min, d.maks, s.sifirTaban);
    seriTablo += "<tr>" +
      "<td><span class='ug-seri-nokta' style='background:" + s.renk +
        "'></span>" + ugKacis(s.ad(t)) +
        (a === "tirmanma"
          ? " <small>(" + ugKacis(t.ugYumusatma ||
              "5 \u00f6rnekli kayan ortalama") + ")</small>"
          : "") +
      "</td>" +
      "<td>" + ugSayiYaz(d.min, o.adim) + "</td>" +
      "<td>" + ugSayiYaz(d.maks, o.adim) + "</td>" +
      "<td>" + ugSayiYaz(d.ort, o.adim) + "</td>" +
      "<td>" + ugKacis(s.birim) + "</td>" +
      "<td>" + d.adet + "</td>" +
    "</tr>";
  }
  seriTablo += "</tbody></table>";

  // Imza bloklari (ucus raporuyla ayni yapi)
  const imzaKutu = (rolAd, adDeger) =>
    "<div class='ug-imza'>" +
      "<div class='ug-imza-rol'>" + ugKacis(rolAd) + "</div>" +
      "<div class='ug-imza-alan'><span>" +
        ugKacis(t.urAdSoyad || "Ad Soyad") + "</span><b>" +
        ugKacis(adDeger || "") + "</b></div>" +
      "<div class='ug-imza-alan'><span>" +
        ugKacis(t.urTarihAlan || "Tarih") + "</span><b></b></div>" +
      "<div class='ug-imza-alan ug-imza-cizgi'><span>" +
        ugKacis(t.urImza || "\u0130mza") + "</span><b></b></div>" +
    "</div>";

  const uretim = new Date();
  const kod = (typeof window.ucusKodu === "function")
    ? window.ucusKodu(ucus) : "";
  const altbilgi = "<div class='ug-altbilgi'>" +
    ugKacis((t.urUretim || "Rapor olu\u015fturma") + ": " +
            uretim.toLocaleString()) +
    " \u00b7 " + ugKacis((t.ugKod || "U\u00c7U\u015e KODU") + ": " +
                        (kod || "--")) +
    " \u00b7 " + ugKacis((t.urKayitNo || "Kay\u0131t no") + ": " +
                        (ucus.id || "--")) +
    " \u00b7 G\u00d6KTUNGU GCS v" +
    ugKacis(typeof GCS_SURUM !== "undefined" ? GCS_SURUM : "") +
  "</div>";

  const govde =
    "<div class='ug-ust-satir'>" + ugAntet(sirket, t) +
      ugKodBlok(ucus, t) + "</div>" +
    "<h1>" + ugKacis(t.ugYazdirBaslik ||
      "U\u00c7U\u015e GRAF\u0130K RAPORU") + "</h1>" +
    kimlik +
    "<img class='ug-grafik-img' src='" + png + "' alt=''>" +
    seriTablo +
    "<div class='ug-imza-satir'>" +
      imzaKutu(t.urPilotRol || "PILOT", pilotKaynak.length ? pilotAd : "") +
      imzaKutu(t.urSahaRol || "SAHA SORUMLUSU", "") +
    "</div>" +
    altbilgi;

  // Gizli iframe ile yazdirma (ucus_rapor.js ile ayni gerekce:
  // pop-up engelleyiciye takilmaz, ayni sekmede kalir)
  const eski = document.getElementById("ucusGrafikCerceve");
  if (eski) eski.remove();
  const cerceve = document.createElement("iframe");
  cerceve.id = "ucusGrafikCerceve";
  cerceve.style.cssText =
    "position:fixed;left:-10000px;top:0;width:1123px;height:794px;" +
    "border:0;visibility:hidden;";
  document.body.appendChild(cerceve);

  const belge = cerceve.contentDocument || cerceve.contentWindow.document;
  belge.open();
  belge.write(
    "<!DOCTYPE html><html lang='" +
    String(typeof aktifDil !== "undefined" ? aktifDil : "TR")
      .toLowerCase() + "'><head><meta charset='utf-8'>" +
    "<title>" + ugKacis((t.ugYazdirBaslik || "UCUS GRAFIK RAPORU") +
      " - " + dronAd) + "</title>" +
    "<style>" + ugYazdirStil() + "</style></head><body>" + govde +
    "</body></html>");
  belge.close();

  const yazdir = () => {
    try {
      cerceve.contentWindow.focus();
      cerceve.contentWindow.print();
    } catch (e) {
      // v2.4.64: dogru imza (nesne)
      if (typeof window.uyariToastGoster === "function") {
        window.uyariToastGoster({
          seviye: "hata",
          kategori: t.ugYazdirHataBaslik || "\u00c7IKTI ALINAMADI",
          mesaj: String(e && e.message ? e.message : e),
        });
      }
    }
    // Diyalog acikken iframe silinirse Chrome bos sayfa yazdirir
    setTimeout(() => { try { cerceve.remove(); } catch (e) {} }, 60000);
  };

  // Logo ve grafik PNG'si yuklenmeden yazdirmak eksik cikti verir
  const gorseller = Array.from(belge.images || []);
  const bekleyen = gorseller.filter(g => !g.complete);
  if (!bekleyen.length) { setTimeout(yazdir, 80); return; }
  let kalan = bekleyen.length, bitti = false;
  const azalt = () => {
    if (bitti) return;
    kalan--;
    if (kalan <= 0) { bitti = true; setTimeout(yazdir, 60); }
  };
  for (const g of bekleyen) {
    g.addEventListener("load", azalt);
    g.addEventListener("error", azalt);
  }
  setTimeout(() => { if (!bitti) { bitti = true; yazdir(); } }, 3000);
}

window.ucusGrafikAc = ucusGrafikAc;
window.ucusGrafikYazdir = ucusGrafikYazdir;

// ---------------------------------------------------------------
// SINAV KANCALARI (sinav_2442.html tarafindan kullanilir)
// Uretim akisini etkilemez; cekirdek hesaplari olculebilir kilar.
// ---------------------------------------------------------------
window.ugSeriVeriTest = function (anahtar, ucus) {
  const s = ugSeriBul(anahtar);
  if (!s || !ucus || !ucus.noktalar) return null;
  const y = ugYardimHesapla(ucus.noktalar);
  const d = ugSeriVeri(s, ucus.noktalar, y);
  return { min: d.min, maks: d.maks, ort: d.ort, adet: d.adet,
           birim: s.birim };
};
window.ugEksenAralikTest = function (min, maks, sifirTaban) {
  return ugEksenAralik(min, maks, sifirTaban);
};
window.ugSeriListeTest = function () {
  return UG_SERILER.map(s => s.anahtar);
};
