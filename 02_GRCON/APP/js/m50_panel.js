// =================================================================
// GÖKTUNGU — M50 ELEKTRO-OPTİK MERKEZ PANELİ
// -----------------------------------------------------------------
// M50 HVS SDK Merkezde asla yüklenmez. Bu modül, yalnız yetkili saha
// Köprüsüne izinli komutlar yollar; ham görüntü veya parola taşımaz.
// =================================================================
"use strict";

const m50Ip = document.getElementById("m50Ip");
const m50Port = document.getElementById("m50Port");
const m50Kullanici = document.getElementById("m50Kullanici");
const m50Parola = document.getElementById("m50Parola");
const btnM50Baglan = document.getElementById("btnM50Baglan");
const btnM50AyarKaydet = document.getElementById("btnM50AyarKaydet");
const btnM50TakipSec = document.getElementById("btnM50TakipSec");
const btnM50TakipBaslat = document.getElementById("btnM50TakipBaslat");
const btnM50TakipDurdur = document.getElementById("btnM50TakipDurdur");
const m50DurumMetin = document.getElementById("m50DurumMetin");
const m50Hata = document.getElementById("m50Hata");
const m50Ozet = document.getElementById("m50Ozet");
const m50TakipDurum = document.getElementById("m50TakipDurum");
const m50PtzHiz = document.getElementById("m50PtzHiz");
const m50LensKanal = document.getElementById("m50LensKanal");
const m50TakipKanal = document.getElementById("m50TakipKanal");
const m50TakipMod = document.getElementById("m50TakipMod");
const m50VideoDikdortgen = document.getElementById("m50VideoDikdortgen");
const m50SecimDikdortgen = document.getElementById("m50SecimDikdortgen");
const m50KopruSec = document.getElementById("m50KopruSec");
const m50KopruSar = document.getElementById("m50KopruSar");

let sonM50 = { durum: "kapali", bagli: false, hata: "" };
let _m50Kopruler = [];
let _m50KopruSecili = 0;
let _m50AyarYuklendi = false;

function m50Gonder(paket){
  if (typeof ws === "undefined" || !ws || ws.readyState !== 1) return false;
  if (_m50KopruSecili > 0 && paket && paket.kopru_ornek_id === undefined)
    paket.kopru_ornek_id = _m50KopruSecili;
  ws.send(JSON.stringify(paket));
  return true;
}

function m50KopruSeciciCiz(){
  if (!m50KopruSar || !m50KopruSec) return;
  if (_m50Kopruler.length < 2){
    m50KopruSar.style.display = "none";
    return;
  }
  const onceki = _m50KopruSecili;
  m50KopruSec.innerHTML = "";
  const bos = document.createElement("option");
  bos.value = "";
  bos.textContent = (typeof D === "function" && D().m50KopruSec) || "Saha makinesi seç...";
  m50KopruSec.appendChild(bos);
  for (const k of _m50Kopruler){
    const o = document.createElement("option");
    o.value = String(k.ornek_id);
    o.textContent = String(k.ad || ("#" + k.ornek_id));
    m50KopruSec.appendChild(o);
  }
  m50KopruSec.value = onceki > 0 ? String(onceki) : "";
  m50KopruSar.style.display = "";
}

window.m50KopruListesiGuncelle = function(liste){
  _m50Kopruler = (Array.isArray(liste) ? liste : []).filter(
    k => k && parseInt(k.ornek_id, 10) > 0);
  if (_m50KopruSecili > 0 && !_m50Kopruler.some(
      k => parseInt(k.ornek_id, 10) === _m50KopruSecili))
    _m50KopruSecili = 0;
  m50KopruSeciciCiz();
};

function m50BagliMi(){ return !!(sonM50 && sonM50.durum === "bagli" && sonM50.bagli); }
function m50HataYaz(mesaj){
  if (!m50Hata) return;
  m50Hata.textContent = String(mesaj || "");
  m50Hata.style.display = mesaj ? "block" : "none";
}
function m50TakipBilgiGuncelle(){
  if (!m50TakipDurum) return;
  const t = typeof D === "function" ? D() : {};
  const takip = sonM50 && sonM50.takip && typeof sonM50.takip === "object" ? sonM50.takip : {};
  if (takip.etkin) {
    m50TakipDurum.textContent = t.m50TakipEtkin || "Manuel takip etkin";
  } else if (takip.secim_hazir) {
    m50TakipDurum.textContent = t.m50SecimOnayli || "Manuel seçim kabul edildi. Takibi başlatmak için ayrıca onay verin.";
  } else {
    m50TakipDurum.textContent = t.m50SecimBekleniyor || "Önce video alanını ve operatör seçimini girin.";
  }
}
function m50Metinler(){
  const t = typeof D === "function" ? D() : {};
  return {
    kapali: t.m50Kapali || "Bağlı değil",
    baglaniyor: t.m50Baglaniyor || "Bağlanıyor...",
    bagli: t.m50Bagli || "Bağlı",
    hata: t.m50Hata || "Hata",
  };
}

function m50AlanlariEtkinlestir(){
  const bagli = m50BagliMi();
  const agVar = typeof ws !== "undefined" && ws && ws.readyState === 1;
  if (btnM50Baglan){
    const t = typeof D === "function" ? D() : {};
    const yazi = bagli ? (t.btnM50Kes || "M50 BAĞLANTISINI KES") :
      (t.btnM50Baglan || "M50'YE BAĞLAN");
    const span = btnM50Baglan.querySelector("span");
    if (span) span.textContent = yazi;
    btnM50Baglan.disabled = !agVar || sonM50.durum === "baglaniyor";
    btnM50Baglan.classList.toggle("bagli", bagli);
  }
  for (const el of document.querySelectorAll(".m50-ptz,.m50-lens"))
    el.disabled = !agVar || !bagli;
  const takip = sonM50 && sonM50.takip && typeof sonM50.takip === "object" ? sonM50.takip : {};
  if (btnM50TakipSec) btnM50TakipSec.disabled = !agVar || !bagli || !!takip.etkin;
  if (btnM50TakipBaslat) btnM50TakipBaslat.disabled = !agVar || !bagli ||
    !!takip.etkin || !takip.secim_hazir;
  if (btnM50TakipDurdur) btnM50TakipDurdur.disabled = !agVar || !bagli || !takip.etkin;
  if (btnM50AyarKaydet) btnM50AyarKaydet.disabled = !agVar;
}

function m50AyarGuncelle(a){
  if (!a || typeof a !== "object") return;
  // Kullanıcı yazarken alanları ezmeyiz. Bu URI'ler Köprü tarafından
  // kullanıcı bilgisini gömülü taşıma bakımından zaten doğrulanmıştır.
  const alanlar = [["m50RtspGorunur", "rtsp_gorunur"],
                   ["m50RtspTermal", "rtsp_termal"],
                   ["m50SdkDizin", "m50_sdk_dizin"]];
  for (const [id, ad] of alanlar){
    const el = document.getElementById(id);
    if (el && document.activeElement !== el && !_m50AyarYuklendi)
      el.value = String(a[ad] || "");
  }
  _m50AyarYuklendi = true;
}

window.m50PaneliGuncelle = function(paket){
  const p = paket && paket.m50_durum ? paket : {m50_durum: paket || {}};
  const r = (p.m50_durum && typeof p.m50_durum === "object") ? p.m50_durum : {};
  sonM50 = r;
  const metinler = m50Metinler();
  if (m50DurumMetin){
    m50DurumMetin.textContent = metinler[r.durum] || String(r.durum || "kapali");
    m50DurumMetin.className = "d-" + String(r.durum || "kapali");
  }
  if (m50Hata){
    m50Hata.textContent = r.durum === "hata" && r.hata ? String(r.hata) : "";
    m50Hata.style.display = (r.durum === "hata" && r.hata) ? "block" : "none";
  }
  if (m50Ozet){
    const video = (p.m50_video && typeof p.m50_video === "object") ? p.m50_video : (r.video || {});
    const takip = (p.m50_takip && typeof p.m50_takip === "object") ? p.m50_takip : (r.takip || {});
    const kanallar = [];
    if (video.gorunur) kanallar.push((typeof D === "function" && D().m50Gorunur) || "Görünür");
    if (video.termal) kanallar.push((typeof D === "function" && D().m50Termal) || "Termal");
    const aci = (Number.isFinite(Number(r.azimut)) && Number.isFinite(Number(r.egim))) ?
      ` · ${Number(r.azimut).toFixed(1)}° / ${Number(r.egim).toFixed(1)}°` : "";
    const takipMetin = takip && takip.etkin ? " · " + ((typeof D === "function" && D().m50TakipEtkin) || "Manuel takip etkin") : "";
    m50Ozet.textContent = (kanallar.length ? kanallar.join(" + ") :
      ((typeof D === "function" && D().m50YerelAkisYok) || "Yerel akış yapılandırılmadı")) + aci + takipMetin;
  }
  m50AyarGuncelle(p.m50_ayarlar || {});
  m50TakipBilgiGuncelle();
  m50AlanlariEtkinlestir();
};

m50KopruSec.addEventListener("change", ev => {
  _m50KopruSecili = parseInt(ev.target.value, 10) || 0;
});

btnM50Baglan.addEventListener("click", () => {
  if (m50BagliMi()){
    m50Gonder({tip: "m50_kes"});
    return;
  }
  const ip = String(m50Ip.value || "").trim();
  const port = Number.parseInt(m50Port.value, 10);
  const kullanici = String(m50Kullanici.value || "").trim();
  const parola = String(m50Parola.value || "");
  if (!ip || !Number.isInteger(port) || port < 1 || port > 65535 || !kullanici || !parola){
    if (m50Hata){
      m50Hata.textContent = (typeof D === "function" && D().m50BaglantiEksik) ||
        "IP, port, kullanıcı adı ve parola girilmelidir.";
      m50Hata.style.display = "block";
    }
    return;
  }
  const gonderildi = m50Gonder({tip: "m50_baglan", ip, port, kullanici, parola});
  // Parola gönderimden hemen sonra ekrandan da silinir; yerel depoya yazılmaz.
  m50Parola.value = "";
  if (gonderildi) m50AlanlariEtkinlestir();
});

btnM50AyarKaydet.addEventListener("click", () => {
  const paket = {tip: "m50_ayar_yaz"};
  for (const [id, ad] of [["m50RtspGorunur", "rtsp_gorunur"],
                          ["m50RtspTermal", "rtsp_termal"],
                          ["m50SdkDizin", "m50_sdk_dizin"]]){
    const el = document.getElementById(id);
    if (el) paket[ad] = String(el.value || "").trim();
  }
  m50Gonder(paket);
  _m50AyarYuklendi = false;
});

let _m50BasiliKomut = null;
function m50KanalOku(el, alan){
  const kanal = String(el && el.value || "").trim().toLowerCase();
  if (kanal !== "gorunur" && kanal !== "termal")
    throw new Error((alan || "M50 video kanalı") + " görünür veya termal olmalıdır.");
  return kanal;
}
function m50PtzHizOku(){
  const hiz = Number(m50PtzHiz && m50PtzHiz.value);
  if (!Number.isInteger(hiz) || hiz < 1 || hiz > 10)
    throw new Error((typeof D === "function" && D().m50PtzHizGecersiz) || "PTZ hızı 1–10 arasında tam sayı olmalıdır.");
  return hiz;
}
function m50DikdortgenOku(el, baslik){
  const parcalar = String(el && el.value || "").split(",").map(x => x.trim());
  if (parcalar.length !== 4 || parcalar.some(x => !/^\d+$/.test(x)))
    throw new Error((baslik || "Dikdörtgen") + " sol, üst, sağ, alt biçiminde dört tam piksel değeriyle girilmelidir.");
  const [sol, ust, sag, alt] = parcalar.map(Number);
  if (!(0 <= sol && sol < sag && sag <= 8192 && 0 <= ust && ust < alt && alt <= 8192))
    throw new Error((baslik || "Dikdörtgen") + " 0–8192 sınırları içinde olmalıdır.");
  return {sol, ust, sag, alt};
}
function m50BasiliGonder(tur, eylem, basili, kanal){
  if (tur === "ptz") return m50Gonder({tip: "m50_ptz", yon: eylem,
    hiz: m50PtzHizOku(), basili: !!basili});
  return m50Gonder({tip: "m50_lens", eylem, kanal: kanal || m50KanalOku(m50LensKanal),
    basili: !!basili});
}
function m50BasiliBirak(){
  const komut = _m50BasiliKomut;
  _m50BasiliKomut = null;
  if (!komut) return;
  try { m50BasiliGonder(komut.tur, komut.eylem, false, komut.kanal); }
  catch (hata) { m50HataYaz(hata.message); }
}
for (const el of document.querySelectorAll(".m50-ptz,.m50-lens")){
  const tur = el.classList.contains("m50-ptz") ? "ptz" : "lens";
  const eylem = tur === "ptz" ? el.dataset.yon : el.dataset.eylem;
  el.addEventListener("pointerdown", ev => {
    ev.preventDefault();
    try {
      m50HataYaz("");
      m50BasiliBirak();
      if (tur === "ptz" && eylem === "dur") {
        m50BasiliGonder(tur, eylem, true);
      } else {
        const kanal = tur === "lens" ? m50KanalOku(m50LensKanal) : "";
        _m50BasiliKomut = {tur, eylem, kanal};
        m50BasiliGonder(tur, eylem, true, kanal);
      }
      try { el.setPointerCapture(ev.pointerId); } catch (_e) {}
    } catch (hata) { m50HataYaz(hata.message); }
  });
  const birak = ev => { ev.preventDefault(); m50BasiliBirak(); };
  el.addEventListener("pointerup", birak);
  el.addEventListener("pointercancel", birak);
  el.addEventListener("pointerleave", ev => { if (ev.buttons) birak(ev); });
}
document.addEventListener("pointerup", m50BasiliBirak);
document.addEventListener("pointercancel", m50BasiliBirak);

btnM50TakipSec.addEventListener("click", () => {
  try {
    m50HataYaz("");
    const kanal = m50KanalOku(m50TakipKanal);
    const video_dikdortgen = m50DikdortgenOku(m50VideoDikdortgen, "Video alanı");
    const secim = m50DikdortgenOku(m50SecimDikdortgen, "Operatör seçimi");
    if (!(video_dikdortgen.sol <= secim.sol && secim.sag <= video_dikdortgen.sag &&
          video_dikdortgen.ust <= secim.ust && secim.alt <= video_dikdortgen.alt))
      throw new Error((typeof D === "function" && D().m50SecimVideoDisi) || "Operatör seçimi video alanının dışında olamaz.");
    if (!m50Gonder({tip: "m50_takip_sec", kanal, video_dikdortgen, secim}))
      throw new Error((typeof D === "function" && D().m50BaglantiYok) || "Merkez bağlantısı yok; komut gönderilemedi.");
    if (m50TakipDurum) m50TakipDurum.textContent = (typeof D === "function" && D().m50SecimGonderildi) || "Manuel seçim saha Köprüsü onayı için gönderildi; takip başlatma kapalıdır.";
  } catch (hata) { m50HataYaz(hata.message); }
});
btnM50TakipBaslat.addEventListener("click", () => {
  try {
    m50HataYaz("");
    const takip = sonM50 && sonM50.takip && typeof sonM50.takip === "object" ? sonM50.takip : {};
    const kanal = m50KanalOku(m50TakipKanal);
    if (!takip.secim_hazir || takip.kanal !== kanal)
      throw new Error((typeof D === "function" && D().m50SecimOnayiGerekli) || "Takip için bu kanalın manuel seçimi önce saha Köprüsü tarafından kabul edilmelidir.");
    const mod = String(m50TakipMod && m50TakipMod.value || "hava_yari_otomatik");
    if (!m50Gonder({tip: "m50_takip_baslat", kanal, mod}))
      throw new Error((typeof D === "function" && D().m50BaglantiYok) || "Merkez bağlantısı yok; komut gönderilemedi.");
    if (m50TakipDurum) m50TakipDurum.textContent = (typeof D === "function" && D().m50TakipOnayiGonderildi) || "Takip başlatma onayı saha Köprüsüne gönderildi.";
  } catch (hata) { m50HataYaz(hata.message); }
});
btnM50TakipDurdur.addEventListener("click", () => {
  try {
    m50HataYaz("");
    const kanal = m50KanalOku(m50TakipKanal);
    if (!m50Gonder({tip: "m50_takip_durdur", kanal}))
      throw new Error((typeof D === "function" && D().m50BaglantiYok) || "Merkez bağlantısı yok; komut gönderilemedi.");
  } catch (hata) { m50HataYaz(hata.message); }
});

// Parola panel kapandığında da kesin olarak temizlenir.
const _m50Panel = document.getElementById("yzM50");
if (_m50Panel){
  const kapat = _m50Panel.querySelector(".yuzen-kapat");
  if (kapat) kapat.addEventListener("click", () => { m50BasiliBirak(); m50Parola.value = ""; });
}
m50KopruSeciciCiz();
m50AlanlariEtkinlestir();
