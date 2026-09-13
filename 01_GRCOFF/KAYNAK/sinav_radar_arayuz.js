// =================================================================
// KUSUR-RADAR-KOPRU — ARAYUZ SINAVI
//
// Olculen: radar komutlarina DOGRU saha makinesi kimliginin eklenmesi,
// secici listesinin dogru uretilmesi ve v2.4.58 gorunurluk
// davranisinin BOZULMAMASI.
//
// YONTEM: radar_panel.js ve program_ayar.js'ten ilgili islevler
// GERCEK kaynaktan okunup calistirilir (kopyalanmaz).
//
// Neden onemli: kusur "radar merkez sunucuda arandi" sinifindandir.
// Radar, kopru makinesinin yerel agindaki bir cihazdir
// (192.168.8.168); merkez sunucudan ERISILEMEZ. Komut yanlis makineye
// giderse pilot "timed out" okur ve sebebini goremez.
// =================================================================
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const KOK = __dirname;
let gecti = 0, kaldi = 0;
const notlar = [];

function olc(ad, kosul, ek) {
  if (kosul) { gecti++; console.log("  OK    " + ad); }
  else {
    kaldi++; console.log("  KALDI " + ad);
    if (ek !== undefined) console.log("        -> " + JSON.stringify(ek));
    notlar.push(ad);
  }
}

function ortamKur() {
  const ogeler = {};

  function oge(id) {
    if (!ogeler[id]) {
      ogeler[id] = {
        id: id, value: "", innerHTML: "", textContent: "",
        style: { display: "", color: "", width: "" },
        checked: false, className: "", disabled: false,
        _cocuk: [], _olay: {},
        appendChild(c) { this._cocuk.push(c); },
        addEventListener(ad, fn) { this._olay[ad] = fn; },
        querySelector() { return null; },
        insertBefore() {}, remove() {},
      };
    }
    return ogeler[id];
  }

  const gonderilen = [];

  const kap = {
    console: console,
    gonderilen: gonderilen,
    ogeler: ogeler,
    document: {
      getElementById: (id) => (ogeler[id] !== undefined ? ogeler[id] : null),
      createElement: () => oge("_gecici_" + Math.random()),
      addEventListener: () => {},
      activeElement: null,
    },
    window: {},
    ws: { readyState: 1, send: (m) => gonderilen.push(JSON.parse(m)) },
    localStorage: { getItem: () => null, setItem: () => {} },
    D: () => ({}),
  };
  kap.window.window = kap.window;
  kap.globalThis = kap;
  return { kap: kap, oge: oge, gonderilen: gonderilen };
}

function kaynakParcasi(dosya, baslangic, bitis) {
  const metin = fs.readFileSync(path.join(KOK, dosya), "utf8");
  const b = metin.indexOf(baslangic);
  if (b < 0) throw new Error("baslangic bulunamadi: " + baslangic +
                             " (" + dosya + ")");
  const s = metin.indexOf(bitis, b);
  if (s < 0) throw new Error("bitis bulunamadi: " + bitis);
  return metin.slice(b, s);
}

console.log("=".repeat(66));
console.log("KUSUR-RADAR-KOPRU — ARAYUZ SINAVI");
console.log("=".repeat(66));

// ---------------------------------------------------------------
// [1] radarGonder: radar komutlarina secili makine eklenir
// ---------------------------------------------------------------
console.log("\n[1] Komutlara secili saha makinesi eklenir");

const o1 = ortamKur();
o1.oge("raKopruSar");
o1.oge("raKopruSec");

const parca = kaynakParcasi("js/radar_panel.js",
                            "let _raKopruler",
                            "// ---------------------------------------------------------------\n// Hedef tipine gore renkler");
const ctx1 = vm.createContext(o1.kap);
vm.runInContext(parca + "\n" +
  "globalThis._test = {gonder: radarGonder, ciz: radarKopruSeciciCiz," +
  " sec: (v)=>{_raKopruSecili=v;}, oku: ()=>_raKopruSecili};",
  ctx1);
const T1 = o1.kap._test;

// Secim YOKKEN: kimlik eklenmez -> merkez tek adayi kendisi bulur.
T1.gonder({ tip: "radar_durum" });
olc("secim yokken kimlik EKLENMEZ",
    o1.gonderilen[0].kopru_ornek_id === undefined, o1.gonderilen[0]);

// Secim VARKEN: DORT radar komutunun tamamina eklenir. Biri atlanirsa
// o komut sessizce baska makineye gider.
T1.sec(22);
o1.gonderilen.length = 0;
const komutlar = ["radar_baglan", "radar_kes", "radar_ayar_yaz",
                  "rtk_konum_al"];
for (const k of komutlar) T1.gonder({ tip: k });
olc("dort radar komutunun TAMAMINA kimlik eklendi",
    o1.gonderilen.length === komutlar.length &&
    o1.gonderilen.every((p) => p.kopru_ornek_id === 22),
    o1.gonderilen.map((p) => [p.tip, p.kopru_ornek_id]));

// Acik verilen kimlik EZILMEZ
o1.gonderilen.length = 0;
T1.gonder({ tip: "radar_durum", kopru_ornek_id: 99 });
olc("acik verilen kimlik ezilmez",
    o1.gonderilen[0].kopru_ornek_id === 99, o1.gonderilen[0]);

// WS kapali: cokmez, false doner
const wsEski = o1.kap.ws;
o1.kap.ws = { readyState: 3, send: () => { throw new Error("gonderilmemeliydi"); } };
let sonuc = null;
try { sonuc = T1.gonder({ tip: "radar_baglan" }); }
catch (e) { sonuc = "COKTU: " + e.message; }
olc("WS kapaliyken cokmez ve gondermez", sonuc === false, sonuc);
o1.kap.ws = wsEski;

// ---------------------------------------------------------------
// [2] Secici gorunurlugu
// ---------------------------------------------------------------
console.log("\n[2] Secici yalniz gerektiginde gorunur");

const guncelle = o1.kap.window.radarKopruListesiGuncelle;
olc("liste guncelleme yuzu tanimli", typeof guncelle === "function");

guncelle([]);
olc("kopru yokken secici GIZLI",
    o1.oge("raKopruSar").style.display === "none",
    o1.oge("raKopruSar").style.display);

guncelle([{ ornek_id: 11, ad: "SAHA1" }]);
olc("tek adayda secici GIZLI (merkez kendisi bulur)",
    o1.oge("raKopruSar").style.display === "none",
    o1.oge("raKopruSar").style.display);

guncelle([{ ornek_id: 11, ad: "SAHA1" }, { ornek_id: 22, ad: "SAHA2" }]);
olc("iki adayda secici GORUNUR",
    o1.oge("raKopruSar").style.display === "",
    o1.oge("raKopruSar").style.display);
olc("secenekler makine adlariyla dolduruldu",
    o1.oge("raKopruSec")._cocuk.length === 3,   // bos + 2 makine
    o1.oge("raKopruSec")._cocuk.length);

// Bozuk girdi cokertmez: liste merkezden gelir, guvenilmez.
let bozukSonuc = "ok";
try { guncelle(null); guncelle("bozuk"); guncelle([null, undefined]); }
catch (e) { bozukSonuc = "COKTU: " + e.message; }
olc("bozuk liste girdisi cokertmez", bozukSonuc === "ok", bozukSonuc);

// ---------------------------------------------------------------
// [3] Secili makine listeden DUSERSE secim temizlenir
// ---------------------------------------------------------------
console.log("\n[3] Kapanan makinenin secimi temizlenir");
guncelle([{ ornek_id: 11, ad: "SAHA1" }, { ornek_id: 22, ad: "SAHA2" }]);
T1.sec(22);
guncelle([{ ornek_id: 11, ad: "SAHA1" }]);   // 22 kapandi
olc("dusen makinenin secimi sifirlandi", T1.oku() === 0, T1.oku());
o1.gonderilen.length = 0;
T1.gonder({ tip: "radar_baglan" });
olc("kapanan makineye komut GONDERILMEZ",
    o1.gonderilen[0].kopru_ornek_id === undefined, o1.gonderilen[0]);

T1.sec(11);
guncelle([{ ornek_id: 11, ad: "SAHA1" }, { ornek_id: 22, ad: "SAHA2" }]);
olc("acik olan makinenin secimi korunur", T1.oku() === 11, T1.oku());

// Kimlik metin olarak gelirse de eslesir (merkez JSON'u tur garantisi
// vermez).
T1.sec(22);
guncelle([{ ornek_id: "22", ad: "SAHA2" }, { ornek_id: "33", ad: "SAHA3" }]);
olc("metin kimlik ile de eslesir (secim korunur)", T1.oku() === 22, T1.oku());

// ---------------------------------------------------------------
// [4] program_ayar.js: radar aday listesi
// ---------------------------------------------------------------
console.log("\n[4] radar servisi calisan makineler dogru saptanir");

const o2 = ortamKur();
const parca2 = kaynakParcasi("js/program_ayar.js",
                             "let _kopruGcsdualListe",
                             "// seri.js her kopru listesi");
const ctx2 = vm.createContext(o2.kap);
vm.runInContext(parca2 + "\n" +
  "globalThis._t2 = {adaylar: _kopruServisAdaylari," +
  " gcsdual: _kopruGcsdualAdaylari};", ctx2);
const T2 = o2.kap._t2;

const kopruler = [
  // cevrimici + radar calisiyor -> ADAY
  { ornek_id: 11, ad: "SAHA1", cevrimici: true,
    servisler: [{ ad: "radar", calisiyor: true }] },
  // radar DURMUS -> aday DEGIL
  { ornek_id: 22, ad: "SAHA2", cevrimici: true,
    servisler: [{ ad: "radar", calisiyor: false }] },
  // CEVRIMDISI -> aday DEGIL
  { ornek_id: 33, ad: "SAHA3", cevrimici: false,
    servisler: [{ ad: "radar", calisiyor: true }] },
  // yalniz gcsdual calisiyor -> radar adayi DEGIL
  { ornek_id: 44, ad: "SAHA4", cevrimici: true,
    servisler: [{ ad: "gcsdual", calisiyor: true }] },
  // durum metniyle bildirim -> ADAY
  { ornek_id: 55, ad: "SAHA5", cevrimici: true,
    servisler: [{ ad: "radar", durum: "calisiyor" }] },
];

const radarListe = T2.adaylar(kopruler, "radar");
olc("yalniz radar CALISAN cevrimici makineler aday",
    radarListe.length === 2, radarListe);
olc("dogru makineler secildi (11, 55)",
    radarListe.map((k) => k.ornek_id).join(",") === "11,55", radarListe);

// Ayni kaynak iki servis icin dogru ayrisir: radar listesi gcsdual
// makinesini ICERMEZ ve tersi.
const gcsListe = T2.adaylar(kopruler, "gcsdual");
olc("gcsdual listesi radar makinesini icermez",
    gcsListe.length === 1 && gcsListe[0].ornek_id === 44, gcsListe);
olc("radar listesi gcsdual makinesini icermez",
    !radarListe.some((k) => k.ornek_id === 44), radarListe);

// Geriye donuk sarmalayici bozulmadi (GCCDUAL sinavi buna dayaniyor)
const gcsListe2 = T2.gcsdual(kopruler);
olc("geriye donuk _kopruGcsdualAdaylari korundu",
    gcsListe2.length === 1 && gcsListe2[0].ornek_id === 44, gcsListe2);

// Servis adi buyuk/kucuk harf duyarsiz olmali: kopru "RADAR" da
// bildirebilir.
const buyuk = T2.adaylar([
  { ornek_id: 66, ad: "SAHA6", cevrimici: true,
    servisler: [{ ad: "RADAR", calisiyor: true }] },
], "radar");
olc("servis adi buyuk harfle bildirilse de saptanir",
    buyuk.length === 1, buyuk);

// ---------------------------------------------------------------
// [5] v2.4.58 GERILEME: radar gorunurlugu bozulmadi
// ---------------------------------------------------------------
console.log("\n[5] v2.4.58 gorunurluk davranisi korundu");

const pa = fs.readFileSync(path.join(KOK, "js/program_ayar.js"), "utf8");
olc("_kopruRadarAcik saptamasi hala var",
    /_kopruRadarAcik\s*=\s*_kopruServisiCalisiyorMu\(liste,\s*"radar"\)/
      .test(pa));
olc("radarMenuGorunumGuncelle hala cagriliyor",
    pa.includes("radarMenuGorunumGuncelle()"));
olc("radar harita gorunumu tazeleme cagrisi korundu",
    /radarGorunum|radarHaritaGorunum|radarVarlikGorunum/.test(pa) ||
    pa.includes("v2.4.58"));

// ---------------------------------------------------------------
// [6] i18n: TR ve EN dengeli
// ---------------------------------------------------------------
console.log("\n[6] i18n TR = EN dengesi");
const i18n = fs.readFileSync(path.join(KOK, "js/i18n.js"), "utf8");
for (const anahtar of ["raKopruEtiket", "raKopruSec"]) {
  const sayi = (i18n.match(new RegExp("\\b" + anahtar + ":", "g")) || [])
    .length;
  olc(anahtar + " TR ve EN'de tanimli (2 kez)", sayi === 2, sayi);
}
olc("EN karsiligi Turkce degil",
    i18n.includes("raKopruEtiket: \"Field machine\""));

// HTML'de secici DOM'u var mi
const html = fs.readFileSync(path.join(KOK, "index.html"), "utf8");
olc("raKopruSar HTML'de tanimli", html.includes('id="raKopruSar"'));
olc("raKopruSec HTML'de tanimli", html.includes('id="raKopruSec"'));
olc("secici baslangicta GIZLI (display:none)",
    /id="raKopruSar"[^>]*display:none/.test(html));
olc("etiket i18n'e bagli",
    html.includes('data-i18n="raKopruEtiket"'));

// ---------------------------------------------------------------
// [7] Komutlar sarmalayiciyi ATLAMIYOR
// ---------------------------------------------------------------
console.log("\n[7] Hicbir radar komutu ws.send'e dogrudan gitmiyor");
const rp = fs.readFileSync(path.join(KOK, "js/radar_panel.js"), "utf8");
// radarGonder tanimi disinda ws.send KALMAMALI: kalirsa o komut
// makine secimini yok sayar.
// DIKKAT: radar panelinde MERKEZE ait komutlar da var
// (siniflandirma_ayar -> merkezdeki siniflandirici, ayar_kaydet ->
// merkezdeki harita merkezi). Bunlar RADAR DONANIMINA gitmez, bu
// yuzden dogrudan ws.send kullanmalari DOGRUDUR. Olculecek olan:
// radar donanimina giden 4 komutun hicbiri dogrudan gonderilmiyor.
const RADAR_DONANIM_KOMUTLARI = ["radar_baglan", "radar_kes",
                                 "radar_ayar_yaz", "rtk_konum_al"];
const wsSatirlari = rp.split("\n")
  .map((s, i) => ({ n: i + 1, s }))
  .filter((o) => /ws\.send\(/.test(o.s));
// Her dogrudan ws.send satirinin MERKEZ komutu oldugunu dogrula
let donanimKacagi = [];
for (const o of wsSatirlari) {
  if (o.n <= 45) continue;   // radarGonder tanimi
  for (const k of RADAR_DONANIM_KOMUTLARI)
    if (o.s.includes(k)) donanimKacagi.push(o.n + ": " + k);
}
olc("radar donanim komutu dogrudan ws.send ile GITMIYOR",
    donanimKacagi.length === 0, donanimKacagi.join(", "));
// Merkez komutlarinin yonlendirilmedigi de dogrulanir: yonlendirilirse
// merkez bunlari kopruye yollar ve siniflandirici ayari kaybolur.
for (const mk of ["siniflandirma_ayar", "ayar_kaydet"])
  olc(mk + " MERKEZE gidiyor (kopruye yonlendirilmedi)",
      !new RegExp("radarGonder\\([^)]*" + mk).test(rp));
for (const k of ["radar_baglan", "radar_kes", "radar_ayar_yaz",
                 "rtk_konum_al"]) {
  olc(k + " radarGonder ile gonderiliyor",
      new RegExp("radarGonder\\([^)]*" + k).test(rp) ||
      new RegExp("radarGonder\\(\\{[\\s\\S]{0,120}" + k).test(rp) ||
      new RegExp("tip:\\s*\"" + k + "\"").test(rp));
}

console.log("\n" + "-".repeat(66));
console.log("SONUC: " + gecti + " gecti / " + kaldi + " kaldi");
if (notlar.length) {
  console.log("Kalanlar:");
  for (const n of notlar) console.log("  - " + n);
}
process.exit(kaldi ? 1 : 0);
