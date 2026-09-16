// v2.4.64: yeni eklenen i18n anahtarlarinin TR=EN dengesini olcer.
// Kabuk icinde ters bolu kacisi bozuldugu icin ayri dosya olarak calisir.
const fs = require("fs");
const kaynak = fs.readFileSync("js/i18n.js", "utf8");

const anahtarlar = [
  "gcTamEkran", "gcTamEkranCik", "gcQrIpucu",
  "ugYazdirBtn", "phRadarIp", "gcKodIpucu",
];

let hata = 0;
for (const a of anahtarlar) {
  // Anahtar tanimi: satir basi bosluk + ad + iki nokta
  const kalip = new RegExp("^\\s+" + a + ":", "gm");
  const n = (kaynak.match(kalip) || []).length;
  const durum = n === 2 ? "OK" : "DENGESIZ";
  if (n !== 2) hata++;
  console.log(durum.padEnd(10), a, "->", n, "tanim");
}

console.log("");
console.log(hata === 0 ? "TR=EN dengesi TAM" : "DENGE BOZUK: " + hata + " anahtar");
process.exit(hata === 0 ? 0 : 1);
