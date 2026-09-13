// =================================================================
// KUSUR-RADAR-ON-DEGER — ARAYUZ SINAVI (v2.4.62)
//
// ## OLCULEN KUSUR
//
// Kullanici bildirdi: "neden radar koprusu 192.168.8.186'ya
// baglanmaya calisiyor... kopru kendisine baglan komutu gelmeden
// baglanmamali".
//
// Ayni varsayim DORT ayri yerde gomuluydu. Bu sinav ARAYUZ
// kopyasini olcer: `index.html` icindeki radar IP alani
// `value="192.168.8.168"` on degeriyle aciliyordu. Operator alana hic
// dokunmadan RADARA BAGLAN'a bastiginda, kendisinin girmedigi bir
// adrese baglanti denemesi basliyordu.
//
// ## NEDEN ON DEGER YANLIS
//
// Radarin adresi her sahada farklidir. Bir on deger yalnizca TEK bir
// kurulumda dogrudur; diger her kurulumda operatoru yanlis bir adrese
// yonlendirir ve cikan zaman asimi hatasi da kendi girdisi gibi
// gorunur. Ipucu (placeholder) bicimi gosterir ama DEGER olarak
// gonderilmez; dogru cozum budur.
//
// ## YONTEM
//
// GERCEK dosyalar okunur: index.html (alan tanimi) ve js/i18n.js
// (ipucu metninin iki dilde de bulunmasi). Kopyalanan metin uzerinde
// olcum yapilmaz.
// =================================================================
"use strict";
const fs = require("fs");
const path = require("path");
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

function oku(bagil) {
  try {
    return fs.readFileSync(path.join(KOK, bagil), "utf8");
  } catch (e) { return ""; }
}

const html = oku("index.html");
const i18n = oku("js/i18n.js");
const rp = oku("js/radar_panel.js");
const surum = oku("js/surum.js");

console.log("\n--- 1. Radar IP alani ON DEGERSIZ ---");
olc("index.html okunabildi", html.length > 1000, html.length);

// Alanin tam etiketini yakala.
const m = html.match(/<input[^>]*id="radarIp"[^>]*>/);
olc("radarIp alani bulundu", !!m);
const etiket = m ? m[0] : "";

// ASIL OLCUM: gomulu adres on deger OLARAK kalmamali.
olc("radarIp icinde 192.168.8.168 ON DEGERI YOK",
    !/value\s*=\s*"192\.168\.8\.168"/.test(etiket), etiket);
olc("radarIp icinde HICBIR dolu value yok",
    !/value\s*=\s*"(?!\s*")[^"]+"/.test(etiket), etiket);
olc("radarIp value bos dize olarak tanimli",
    /value\s*=\s*""/.test(etiket), etiket);

console.log("\n--- 2. Ipucu (placeholder) dogru kurulmus ---");
olc("placeholder ozniteligi var",
    /placeholder\s*=\s*"[^"]+"/.test(etiket), etiket);
olc("placeholder i18n anahtariyla bagli (data-i18n-ph)",
    /data-i18n-ph\s*=\s*"phRadarIp"/.test(etiket), etiket);
// data-i18n-placeholder DESTEKLENMIYOR; i18n.js yalniz -ph okur.
// Yanlis oznitelik yazilirsa ipucu Ingilizceye HIC cevrilmez.
olc("yanlis oznitelik (data-i18n-placeholder) kullanilmamis",
    !/data-i18n-placeholder/.test(etiket), etiket);
olc("i18n.js data-i18n-ph dongusu var",
    /querySelectorAll\("\[data-i18n-ph\]"\)/.test(i18n));

console.log("\n--- 3. i18n dengesi: TR = EN ---");
const anahtarSay = (i18n.match(/phRadarIp\s*:/g) || []).length;
olc("phRadarIp iki dilde tanimli (TR + EN)", anahtarSay === 2,
    anahtarSay);

// Sozlukleri kabaca ayirip her birinde anahtarin varligini olc.
// TR sozlugu once gelir (DILLER = { TR: {...}, EN: {...} }).
const enBas = i18n.search(/\n\s{2}EN\s*:\s*\{/);
olc("EN sozlugunun basi bulundu", enBas > 0, enBas);
if (enBas > 0) {
  const trBolum = i18n.slice(0, enBas);
  const enBolum = i18n.slice(enBas);
  olc("phRadarIp TR sozlugunde var", /phRadarIp\s*:/.test(trBolum));
  olc("phRadarIp EN sozlugunde var", /phRadarIp\s*:/.test(enBolum));
  // Ceviriler ayni olmamali; ayniysa ceviri unutulmus demektir.
  const trM = trBolum.match(/phRadarIp\s*:\s*"([^"]*)"/);
  const enM = enBolum.match(/phRadarIp\s*:\s*"([^"]*)"/);
  olc("iki dilde de metin bos degil",
      !!(trM && trM[1] && enM && enM[1]));
  olc("EN metni TR metninden farkli (ceviri yapilmis)",
      !!(trM && enM && trM[1] !== enM[1]),
      { tr: trM && trM[1], en: enM && enM[1] });
}

console.log("\n--- 4. Port alani korundu (gerileme) ---");
// Port 5001 C20 protokolunun sabit portudur; adres gibi sahaya gore
// degismez, bu yuzden on degeri KALMALI. Yanlislikla silinmedigini
// olcmek bu sinavin isidir.
const pm = html.match(/<input[^>]*id="radarPort"[^>]*>/);
olc("radarPort alani bulundu", !!pm);
olc("radarPort on degeri 5001 KORUNDU",
    !!pm && /value\s*=\s*"5001"/.test(pm[0]), pm && pm[0]);

console.log("\n--- 5. Baglan komutu adresi arayuzden okuyor ---");
olc("radar_panel.js okunabildi", rp.length > 500, rp.length);
olc("radarIp degeri okunuyor",
    /radarIp/.test(rp), "radarIp gecmiyor");
olc("radar_baglan komutu var", /radar_baglan/.test(rp));

console.log("\n--- 6. Surum etiketi hizali ---");
const sm = surum.match(/GCS_SURUM\s*=\s*"([0-9.]+)"/);
olc("GCS_SURUM okunabildi", !!sm, sm && sm[1]);
if (sm) {
  const beklenen = "?v=v" + sm[1].replace(/\./g, "");
  // Onbellek etiketi surumle hizali olmazsa tarayici ESKI i18n.js'i
  // kullanir ve yeni eklenen phRadarIp metni hic gorunmez. Bu, bu
  // sinavin olctugu kusurun sessizce geri gelmesi demektir.
  for (const sayfa of ["index.html", "flight.html", "video.html"]) {
    const metin = oku(sayfa);
    if (!metin) { continue; }
    const etiketler = Array.from(
      new Set(metin.match(/\?v=v[0-9]+/g) || []));
    olc(sayfa + " onbellek etiketi surumle hizali",
        etiketler.length > 0 && etiketler.every(e => e === beklenen),
        { bulunan: etiketler, beklenen: beklenen });
  }
  olc("surum 2.4.62 veya ustu",
      parseInt(sm[1].replace(/\./g, ""), 10) >= 2462, sm[1]);
}

console.log("\n" + "-".repeat(66));
console.log("SONUC: " + gecti + " gecti / " + kaldi + " kaldi");
if (notlar.length) {
  console.log("Kalanlar:");
  for (const n of notlar) console.log("  - " + n);
}
process.exit(kaldi ? 1 : 0);
