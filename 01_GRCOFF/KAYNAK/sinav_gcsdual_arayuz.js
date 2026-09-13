// =================================================================
// KUSUR-GCSDUAL-PORT — ARAYUZ SINAVI
//
// Olculen: panel komutlarina DOGRU saha makinesi kimliginin eklenmesi
// ve secici listesinin dogru uretilmesi.
//
// YONTEM: istasyon2.js ve program_ayar.js'ten ilgili islevler GERCEK
// kaynaktan okunup calistirilir (kopyalanmaz). Kaynak kopyalamak, kod
// degisince sinavin sessizce eskimesi demektir.
//
// Neden onemli: kusur "komut yanlis makineye gitti" sinifindandir.
// `kopru_ornek_id` eklenmezse merkez tek adayi bulur ve HER SEY
// calisir gorunur — ta ki pilot ikinci bir kopru baslatana kadar. O
// noktada komutlar sessizce baska cantaya gider.
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

// ---------------------------------------------------------------
// Sahte tarayici ortami
// ---------------------------------------------------------------
function ortamKur() {
  const ogeler = {};

  function oge(id) {
    if (!ogeler[id]) {
      ogeler[id] = {
        id: id, value: "", innerHTML: "", textContent: "",
        style: { display: "" }, checked: false, className: "",
        _cocuk: [], _olay: {},
        appendChild(c) { this._cocuk.push(c); },
        addEventListener(ad, fn) { this._olay[ad] = fn; },
        querySelector() { return null; },
        insertBefore() {},
        remove() {},
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

// Kaynaktan belirli islevleri cikarip calistirir. Tum dosyayi
// yuklemek DOM'un tamamini taklit etmeyi gerektirir; sinavin konusu
// yalnizca kopru secimi mantigi.
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
console.log("KUSUR-GCSDUAL-PORT — ARAYUZ SINAVI");
console.log("=".repeat(66));

// ---------------------------------------------------------------
// [1] i2Gonder: istasyon2 komutlarina secili makine eklenir
// ---------------------------------------------------------------
console.log("\n[1] Komutlara secili saha makinesi eklenir");

const o1 = ortamKur();
o1.oge("i2KopruSar");
o1.oge("i2KopruSec");

const parca = kaynakParcasi("js/istasyon2.js",
                            "let _i2Kopruler",
                            "function i2Toast");
const ctx1 = vm.createContext(o1.kap);
// `i2D()` istasyon2.js'in i18n sozluk yardimcisi; parcanin disinda
// tanimli oldugu icin ortama eklenir. Bos sozluk dondurmek yeterli:
// islevler varsayilan metinlere duser ve sinav metin degil DAVRANIS
// olcer.
vm.runInContext("function i2D(){ return {}; }\n" + parca + "\n" +
  "globalThis._test = {i2Gonder: i2Gonder, ciz: i2KopruSeciciCiz," +
  " sec: (v)=>{_i2KopruSecili=v;}, oku: ()=>_i2KopruSecili};",
  ctx1);
const T1 = o1.kap._test;

// Secim YOKKEN: kimlik eklenmez (merkez tek adayi kendisi bulur)
T1.i2Gonder({ tip: "istasyon2_durum" });
olc("secim yokken kimlik EKLENMEZ",
    o1.gonderilen[0].kopru_ornek_id === undefined, o1.gonderilen[0]);

// Secim VARKEN: her istasyon2 komutuna eklenir
T1.sec(22);
o1.gonderilen.length = 0;
const komutlar = ["istasyon2_durum", "istasyon2_portlar",
                  "istasyon2_baglan", "istasyon2_kes",
                  "istasyon2_led", "istasyon2_kalibre",
                  "istasyon2_ayar"];
for (const k of komutlar) T1.i2Gonder({ tip: k });
olc("yedi komutun TAMAMINA kimlik eklendi",
    o1.gonderilen.length === komutlar.length &&
    o1.gonderilen.every((p) => p.kopru_ornek_id === 22),
    o1.gonderilen.map((p) => [p.tip, p.kopru_ornek_id]));

// ALAKASIZ komutlara EKLENMEZ: telemetri/dron komutlari kirlenmemeli
o1.gonderilen.length = 0;
T1.i2Gonder({ tip: "dron_arm", sysid: 1 });
olc("istasyon2 disi komut KIRLENMEZ",
    o1.gonderilen[0].kopru_ornek_id === undefined, o1.gonderilen[0]);

// Cagiran acikca kimlik verdiyse EZILMEZ
o1.gonderilen.length = 0;
T1.i2Gonder({ tip: "istasyon2_durum", kopru_ornek_id: 99 });
olc("acik verilen kimlik ezilmez",
    o1.gonderilen[0].kopru_ornek_id === 99, o1.gonderilen[0]);

// ---------------------------------------------------------------
// [2] Secici gorunurlugu: tek adayda GIZLI, iki adayda GORUNUR
// ---------------------------------------------------------------
console.log("\n[2] Secici yalniz gerektiginde gorunur");

const guncelle = o1.kap.window.istasyon2KopruListesiGuncelle;
olc("liste guncelleme yuzu tanimli", typeof guncelle === "function");

guncelle([]);
olc("kopru yokken secici GIZLI",
    o1.oge("i2KopruSar").style.display === "none",
    o1.oge("i2KopruSar").style.display);

guncelle([{ ornek_id: 11, ad: "IST2" }]);
olc("tek adayda secici GIZLI (merkez kendisi bulur)",
    o1.oge("i2KopruSar").style.display === "none",
    o1.oge("i2KopruSar").style.display);

guncelle([{ ornek_id: 11, ad: "IST2" }, { ornek_id: 22, ad: "ANK1" }]);
olc("iki adayda secici GORUNUR",
    o1.oge("i2KopruSar").style.display === "",
    o1.oge("i2KopruSar").style.display);
olc("secenekler makine adlariyla dolduruldu",
    o1.oge("i2KopruSec")._cocuk.length === 3,   // bos + 2 makine
    o1.oge("i2KopruSec")._cocuk.length);

// ---------------------------------------------------------------
// [3] Secili makine listeden DUSERSE secim temizlenir
// ---------------------------------------------------------------
console.log("\n[3] Kapanan makinenin secimi temizlenir");
T1.sec(22);
guncelle([{ ornek_id: 11, ad: "IST2" }]);   // 22 kapandi
olc("dusen makinenin secimi sifirlandi", T1.oku() === 0, T1.oku());
o1.gonderilen.length = 0;
T1.i2Gonder({ tip: "istasyon2_durum" });
olc("kapanan makineye komut GONDERILMEZ",
    o1.gonderilen[0].kopru_ornek_id === undefined, o1.gonderilen[0]);

// Secili makine listede KALIRSA secim korunur
T1.sec(11);
guncelle([{ ornek_id: 11, ad: "IST2" }, { ornek_id: 22, ad: "ANK1" }]);
olc("acik olan makinenin secimi korunur", T1.oku() === 11, T1.oku());

// ---------------------------------------------------------------
// [4] program_ayar.js: aday listesi dogru uretilir
// ---------------------------------------------------------------
console.log("\n[4] gcsdual calisan makineler dogru saptanir");

const o2 = ortamKur();
const parca2 = kaynakParcasi("js/program_ayar.js",
                             "let _kopruGcsdualListe",
                             "// seri.js her kopru listesi");
const ctx2 = vm.createContext(o2.kap);
vm.runInContext(parca2 + "\n" +
  "globalThis._t2 = {adaylar: _kopruGcsdualAdaylari};", ctx2);
const T2 = o2.kap._t2;

const liste = T2.adaylar([
  // cevrimici + gcsdual calisiyor -> ADAY
  { ornek_id: 11, ad: "IST2", cevrimici: true,
    servisler: [{ ad: "gcsdual", calisiyor: true }] },
  // cevrimici ama gcsdual DURMUS -> aday DEGIL
  { ornek_id: 22, ad: "ANK1", cevrimici: true,
    servisler: [{ ad: "gcsdual", calisiyor: false }] },
  // CEVRIMDISI: servis durumu bilinmez -> aday DEGIL
  { ornek_id: 33, ad: "IZM1", cevrimici: false,
    servisler: [{ ad: "gcsdual", calisiyor: true }] },
  // baska servis calisiyor -> aday DEGIL
  { ornek_id: 44, ad: "BUR1", cevrimici: true,
    servisler: [{ ad: "radar", calisiyor: true }] },
  // durum metniyle bildirim -> ADAY
  { ornek_id: 55, ad: "ADA1", cevrimici: true,
    servisler: [{ ad: "gcsdual", durum: "calisiyor" }] },
]);
olc("yalniz gcsdual CALISAN cevrimici makineler aday",
    liste.length === 2, liste);
olc("dogru makineler secildi (11, 55)",
    liste.map((k) => k.ornek_id).join(",") === "11,55", liste);
olc("makine adi tasindi",
    liste[0].ad === "IST2" && liste[1].ad === "ADA1", liste);

// Ad yoksa kurulum kimligi, o da yoksa numara kullanilir: pilotun
// listede bos satir gormesi kabul edilemez.
const liste2 = T2.adaylar([
  { ornek_id: 66, kurulum_uid: "UID-66", cevrimici: true,
    servisler: [{ ad: "gcsdual", calisiyor: true }] },
  { ornek_id: 77, cevrimici: true,
    servisler: [{ ad: "gcsdual", calisiyor: true }] },
]);
olc("ad yoksa kurulum kimligi kullanilir",
    liste2[0].ad === "UID-66", liste2);
olc("hicbir ad yoksa numara gosterilir",
    liste2[1].ad === "#77", liste2);

// Bozuk kayit COKERTMEZ: liste merkezden gelir, guvenilmez.
const liste3 = T2.adaylar([
  null,
  { cevrimici: true, servisler: [{ ad: "gcsdual", calisiyor: true }] },
  { ornek_id: 0, cevrimici: true,
    servisler: [{ ad: "gcsdual", calisiyor: true }] },
  { ornek_id: 88, cevrimici: true, servisler: null },
]);
olc("bozuk kayitlar sessizce atlanir", liste3.length === 0, liste3);

// ---------------------------------------------------------------
// [5] i18n: TR ve EN dengeli
// ---------------------------------------------------------------
console.log("\n[5] i18n TR = EN dengesi");
const i18n = fs.readFileSync(path.join(KOK, "js/i18n.js"), "utf8");
for (const anahtar of ["i2Kopru", "i2KopruSec"]) {
  const sayi = (i18n.match(new RegExp("\\b" + anahtar + ":", "g")) || [])
    .length;
  olc(anahtar + " TR ve EN'de tanimli (2 kez)", sayi === 2, sayi);
}
olc("EN karsiligi Turkce degil",
    i18n.includes("i2Kopru: \"Field machine\""));

console.log("\n" + "-".repeat(66));
console.log("SONUC: " + gecti + " gecti / " + kaldi + " kaldi");
if (notlar.length) {
  console.log("Kalanlar:");
  for (const n of notlar) console.log("  - " + n);
}
process.exit(kaldi ? 1 : 0);
