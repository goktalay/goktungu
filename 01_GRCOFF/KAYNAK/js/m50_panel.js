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
// v2.4.187: sunucudan gelen son M50 ayar özeti (kimlik_kayitli, ip, port;
// parola ASLA gelmez). "Bağlan" boş formla basılınca kayıtlı kimlik kullanılır.
let sonM50Ayar = {};

function m50Gonder(paket){
  if (typeof ws === "undefined" || !ws || ws.readyState !== 1) return false;
  if (_m50KopruSecili > 0 && paket && paket.kopru_ornek_id === undefined)
    paket.kopru_ornek_id = _m50KopruSecili;
  // v2.4.191: her komut SECILI elektro-optik cihaza gider.
  if (_eoSecili > 0 && paket && paket.eo_id === undefined)
    paket.eo_id = _eoSecili;
  ws.send(JSON.stringify(paket));
  return true;
}

// =================================================================
// v2.4.191 — COKLU ELEKTRO-OPTIK: cihaz sekmeleri + kayit
// Telemetri `eo_cihazlar: [{eo_id, isim, m50_durum, konum, ...}]` tasir.
// =================================================================
let eoListesi = [];
let _eoSecili = 0;
let _eoFormuDoldu = 0;
const eoListeEl = document.getElementById("eoListe");
const eoIsimEl = document.getElementById("eoIsim");
window.eoSeciliId = function(){ return _eoSecili; };

function eoSecili(){
  return eoListesi.find(c => Number(c.eo_id) === _eoSecili) || eoListesi[0] || null;
}
function eoListeCiz(){
  if (!eoListeEl) return;
  const t = m50T();
  eoListeEl.innerHTML = "";
  for (const c of eoListesi){
    const d = (c.m50_durum && c.m50_durum.durum) || "kapali";
    const b = document.createElement("button");
    b.type = "button";
    b.className = "ra-sekme" + (Number(c.eo_id) === _eoSecili ? " secili" : "");
    b.innerHTML = "<span class='ra-nokta d-" + d + "'></span><span>" + (c.isim || ("M50 " + c.eo_id)) + "</span>";
    b.addEventListener("click", () => { _eoSecili = Number(c.eo_id); _eoFormuDoldu = 0; _m50VideoKamId = null; _m50AyarYuklendi = false; eoListeCiz(); eoPaneliTazele(); });
    eoListeEl.appendChild(b);
  }
  const ekle = document.createElement("button");
  ekle.type = "button"; ekle.className = "ra-sekme ra-ekle";
  ekle.innerHTML = "<i class='fa-solid fa-plus'></i>";
  ekle.title = t.btnEoEkle || "Yeni elektro-optik cihaz";
  ekle.addEventListener("click", () => {
    m50Gonder({tip: "eo_kaydet", eo_id: 0, isim: "M50 " + (eoListesi.length + 1), port: 39020});
  });
  eoListeEl.appendChild(ekle);
}
function eoPaneliTazele(){
  const c = eoSecili();
  if (!c) return;
  if (eoIsimEl && _eoFormuDoldu !== Number(c.eo_id) && document.activeElement !== eoIsimEl){
    eoIsimEl.value = c.isim || ""; _eoFormuDoldu = Number(c.eo_id);
  }
  window.m50PaneliGuncelle(c);
}
// v2.4.192: Elektro-Optik menusu kisayollari (kullanici istegi):
// Cihazlar (paneli acip cihaz sekmelerine gider), Yeni M50 (kayit
// ekler), Tum Cihazlara Baglan (her cihaz icin kayitli kimlikle baglan).
(function eoMenuKisayollari(){
  const panelAc = () => {
    if (typeof window.yuzenPanelAc === "function") window.yuzenPanelAc("yzM50");
    if (typeof menubarKapat === "function") menubarKapat();
  };
  const cihazlar = document.getElementById("mbEoCihazlar");
  const yeni = document.getElementById("mbEoYeni");
  const tum = document.getElementById("mbEoTumBaglan");
  if (cihazlar) cihazlar.addEventListener("click", () => {
    panelAc();
    const b = document.getElementById("m50BolumCihaz") || eoListeEl;
    if (b && b.tagName === "DETAILS") b.open = true;
    if (b && typeof b.scrollIntoView === "function") b.scrollIntoView({block: "start", behavior: "smooth"});
  });
  if (yeni) yeni.addEventListener("click", () => {
    panelAc();
    m50Gonder({tip: "eo_kaydet", eo_id: 0, isim: "M50 " + (eoListesi.length + 1), port: 39020});
  });
  if (tum) tum.addEventListener("click", () => {
    if (typeof menubarKapat === "function") menubarKapat();
    let n = 0;
    for (const c of eoListesi){
      const d = c.m50_durum || {};
      if (d.durum === "bagli" || d.durum === "baglaniyor") continue;
      // Alanlar bos: sunucu kayitli kimligi kullanir (yerel modda
      // baglan_kayitli, kopru modunda kayitli kimlik ile baglan).
      m50Gonder({tip: "m50_baglan", eo_id: Number(c.eo_id), ip: "", port: 0,
                 kullanici: "", parola: "", zaman_asimi: 5000});
      n++;
    }
    if (typeof window.uyariGoster === "function")
      window.uyariGoster("M50", n ? (n + " cihaza bağlantı isteği gönderildi") : "Bağlanacak cihaz yok", n ? "bilgi" : "uyari");
  });
})();

window.eoListesiGuncelle = function(liste, eski){
  eoListesi = Array.isArray(liste) ? liste : [];
  if (!eoListesi.length){ if (eski) window.m50PaneliGuncelle(eski); return; }
  if (!eoListesi.some(c => Number(c.eo_id) === _eoSecili))
    _eoSecili = Number(eoListesi[0].eo_id);
  eoListeCiz();
  eoPaneliTazele();
  if (typeof window.eoIkonlariGuncelle === "function") window.eoIkonlariGuncelle(eoListesi);
};
(function eoKayitDugmeleri(){
  const kaydet = document.getElementById("btnEoKaydet");
  const sil = document.getElementById("btnEoSil");
  if (kaydet) kaydet.addEventListener("click", () => {
    const c = eoSecili();
    _eoFormuDoldu = 0;
    m50Gonder({tip: "eo_kaydet", eo_id: c ? Number(c.eo_id) : 0,
               isim: eoIsimEl ? eoIsimEl.value.trim() : "",
               ip: m50Ip ? m50Ip.value.trim() : "", port: parseInt(m50Port && m50Port.value, 10) || 39020});
  });
  if (sil) sil.addEventListener("click", () => {
    const c = eoSecili();
    if (!c) return;
    const metin = (m50T().onayEoSil || "{ad} elektro-optik kaydı silinsin mi?").replace("{ad}", c.isim || ("M50 " + c.eo_id));
    if (typeof onayIste === "function") onayIste(metin, () => m50Gonder({tip: "eo_sil", eo_id: Number(c.eo_id)}));
    else if (confirm(metin)) m50Gonder({tip: "eo_sil", eo_id: Number(c.eo_id)});
  });
})();

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
  sonM50Ayar = a;
  // Kayıtlı kimlik varsa IP/port önceden doldurulur, parola alanı
  // "kayıtlı" ipucu gösterir; operatör hiçbir şey girmeden BAĞLAN'a basar.
  if (a.kimlik_kayitli){
    if (m50Ip && document.activeElement !== m50Ip && !m50Ip.value && a.ip)
      m50Ip.value = String(a.ip);
    if (m50Port && document.activeElement !== m50Port && !m50Port.value && a.port)
      m50Port.value = String(a.port);
    if (m50Parola) m50Parola.placeholder =
      (typeof D === "function" && D().m50ParolaKayitli) || "kayıtlı — boş bırakın";
    if (m50Kullanici) m50Kullanici.placeholder =
      (typeof D === "function" && D().m50KullaniciKayitli) || "kayıtlı — boş bırakın";
  }
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
  // v2.4.187: kimlik bir kez kaydedildiyse alanlar BOŞ bırakılabilir;
  // sunucu kayıtlı kimlikle bağlanır. Kısmen dolu form yine reddedilir.
  // IP/port kayıttan otomatik doldurulmuş olabilir; "boş" sayımı yalnız
  // kullanıcı adı + parolaya bakar.
  const hepsiBos = !kullanici && !parola;
  if (hepsiBos && sonM50Ayar && sonM50Ayar.kimlik_kayitli){
    const gonderildi = m50Gonder({tip: "m50_baglan"});
    if (gonderildi) m50AlanlariEtkinlestir();
    return;
  }
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

// =================================================================
// v2.4.188 — ELEKTRO-OPTİK PANELİ: SDK'nın geri kalanı
// (gömülü canlı görüntü + kanal geçişi, 8 yönlü PTZ, açı okuma/gitme,
// ön ayarlar, tarama/devriye, takip yeteneği). Her bölüm <details>.
// =================================================================
const m50VideoSar = document.getElementById("m50VideoSar");
const btnM50KameraOlustur = document.getElementById("btnM50KameraOlustur");
const m50Azimut = document.getElementById("m50Azimut");
const m50Egim = document.getElementById("m50Egim");
const m50AciHiz = document.getElementById("m50AciHiz");
const m50AciRozet = document.getElementById("m50AciRozet");
const btnM50AciGit = document.getElementById("btnM50AciGit");
const btnM50AciOku = document.getElementById("btnM50AciOku");
const m50OnayarSec = document.getElementById("m50OnayarSec");
const m50OnayarNo = document.getElementById("m50OnayarNo");
const m50OnayarAd = document.getElementById("m50OnayarAd");
const m50OnayarHiz = document.getElementById("m50OnayarHiz");
const m50OnayarRozet = document.getElementById("m50OnayarRozet");
const m50TaramaTur = document.getElementById("m50TaramaTur");
const m50TaramaYol = document.getElementById("m50TaramaYol");
const m50TaramaRozet = document.getElementById("m50TaramaRozet");
const m50TakipRozet = document.getElementById("m50TakipRozet");
const m50KimlikRozet = document.getElementById("m50KimlikRozet");
const m50VideoRozet = document.getElementById("m50VideoRozet");

let _m50VideoKamId = null;   // panelde su an cizili kamera kaydi
let _m50VideoKanal = "";     // ... ve kanali
let _m50OnayarImza = "";     // liste degismediyse <select> yeniden cizilmez

function m50T(){ return (typeof D === "function" ? D() : {}) || {}; }

// --- Canlı görüntü: mevcut M50 kamera kaydını panele gömer -----------
function m50VideoKur(){
  if (!m50VideoSar) return;
  const kam = typeof window.m50KameraBul === "function" ? window.m50KameraBul(_eoSecili) : null;
  const kanal = kam ? (String(kam.url || "").split(":").pop() === "termal" ? "termal" : "gorunur") : "";
  if (!kam){
    if (_m50VideoKamId !== null){
      m50VideoSar.querySelectorAll("img.kam-video").forEach(e => e.remove());
      _m50VideoKamId = null; _m50VideoKanal = "";
    }
    m50VideoSar.classList.remove("var");
    if (m50VideoRozet) m50VideoRozet.textContent = "";
    return;
  }
  m50VideoSar.classList.add("var");
  if (_m50VideoKamId !== kam.id || _m50VideoKanal !== kanal){
    m50VideoSar.querySelectorAll("img.kam-video").forEach(e => e.remove());
    if (typeof window.kamVideoOlustur === "function"){
      const img = window.kamVideoOlustur(kam);
      if (img) m50VideoSar.insertBefore(img, m50VideoSar.firstChild);
    }
    _m50VideoKamId = kam.id; _m50VideoKanal = kanal;
  }
  for (const b of m50VideoSar.querySelectorAll(".m50-kanal"))
    b.classList.toggle("aktif", b.dataset.kanal === kanal);
  if (m50VideoRozet) m50VideoRozet.textContent =
    kanal === "termal" ? (m50T().m50Termal || "Termal") : (m50T().m50Gorunur || "Görünür");
}
if (m50VideoSar){
  for (const b of m50VideoSar.querySelectorAll(".m50-kanal")){
    b.addEventListener("click", ev => {
      ev.stopPropagation();
      const kam = typeof window.m50KameraBul === "function" ? window.m50KameraBul(_eoSecili) : null;
      if (kam && typeof window.m50KanalDegistir === "function" && b.dataset.kanal !== _m50VideoKanal)
        window.m50KanalDegistir(kam, b.dataset.kanal);
    });
  }
}
if (btnM50KameraOlustur) btnM50KameraOlustur.addEventListener("click", () => {
  const c = eoSecili();
  if (typeof window.m50KameraOlustur === "function") window.m50KameraOlustur(_eoSecili, c ? c.isim : "");
});

// --- Açı ---------------------------------------------------------------
if (btnM50AciGit) btnM50AciGit.addEventListener("click", () => {
  try {
    m50HataYaz("");
    const azimut = Number(m50Azimut && m50Azimut.value);
    const egim = Number(m50Egim && m50Egim.value);
    const hiz = Number(m50AciHiz && m50AciHiz.value) || 5;
    if (!Number.isFinite(azimut) || !Number.isFinite(egim))
      throw new Error("Azimut ve eğim sayısal olmalıdır.");
    m50Gonder({tip: "m50_aci_konumla", azimut, egim, hiz});
  } catch (hata) { m50HataYaz(hata.message); }
});
if (btnM50AciOku) btnM50AciOku.addEventListener("click", () => m50Gonder({tip: "m50_aci_oku"}));

// --- Ön ayarlar ----------------------------------------------------------
function m50OnayarListeCiz(liste){
  if (!m50OnayarSec) return;
  const l = Array.isArray(liste) ? liste : [];
  const imza = JSON.stringify(l);
  if (imza === _m50OnayarImza) return;
  _m50OnayarImza = imza;
  const secili = m50OnayarSec.value;
  m50OnayarSec.innerHTML = "";
  if (!l.length){
    const o = document.createElement("option"); o.value = "";
    o.textContent = m50T().m50OnayarBos || "(kayıtlı ön ayar yok)";
    m50OnayarSec.appendChild(o);
  }
  for (const p of l){
    const o = document.createElement("option");
    o.value = String(p.no);
    o.textContent = p.no + (p.ad ? " — " + p.ad : "");
    m50OnayarSec.appendChild(o);
  }
  if (secili && l.some(p => String(p.no) === secili)) m50OnayarSec.value = secili;
  if (m50OnayarRozet) m50OnayarRozet.textContent = l.length ? String(l.length) : "";
}
if (m50OnayarSec) m50OnayarSec.addEventListener("change", () => {
  if (m50OnayarSec.value !== "" && m50OnayarNo) m50OnayarNo.value = m50OnayarSec.value;
  const secili = m50OnayarSec.selectedOptions[0];
  if (secili && m50OnayarAd) m50OnayarAd.value = (secili.textContent.split(" — ")[1] || "");
});
function m50OnayarNoOku(){
  const no = Number(m50OnayarNo && m50OnayarNo.value);
  if (!Number.isInteger(no) || no < 0 || no > 255) throw new Error("Ön ayar numarası 0–255 arasında olmalıdır.");
  return no;
}
const _btn = id => document.getElementById(id);
if (_btn("btnM50OnayarCagir")) _btn("btnM50OnayarCagir").addEventListener("click", () => {
  try { m50HataYaz(""); m50Gonder({tip: "m50_onayar_cagir", no: m50OnayarNoOku()}); }
  catch (hata) { m50HataYaz(hata.message); }
});
if (_btn("btnM50OnayarKaydet")) _btn("btnM50OnayarKaydet").addEventListener("click", () => {
  try {
    m50HataYaz("");
    m50Gonder({tip: "m50_onayar_kaydet", no: m50OnayarNoOku(),
               ad: String(m50OnayarAd && m50OnayarAd.value || "").trim(),
               hiz: Number(m50OnayarHiz && m50OnayarHiz.value) || 30});
  } catch (hata) { m50HataYaz(hata.message); }
});
if (_btn("btnM50OnayarSil")) _btn("btnM50OnayarSil").addEventListener("click", () => {
  try { m50HataYaz(""); m50Gonder({tip: "m50_onayar_sil", no: m50OnayarNoOku()}); }
  catch (hata) { m50HataYaz(hata.message); }
});
if (_btn("btnM50OnayarHepsiniSil")) _btn("btnM50OnayarHepsiniSil").addEventListener("click", () => {
  if (confirm(m50T().m50HepsiniSilOnay || "M50 üzerindeki TÜM ön ayarlar silinecek. Emin misiniz?"))
    m50Gonder({tip: "m50_onayar_hepsini_sil"});
});

// --- Tarama / devriye --------------------------------------------------
for (const b of document.querySelectorAll(".m50-tarama")){
  b.addEventListener("click", () => {
    try {
      m50HataYaz("");
      m50Gonder({tip: "m50_tarama", tur: String(m50TaramaTur && m50TaramaTur.value || "yatay"),
                 kontrol: b.dataset.kontrol, yol: Number(m50TaramaYol && m50TaramaYol.value) || 0});
    } catch (hata) { m50HataYaz(hata.message); }
  });
}

// --- Takip yeteneği ------------------------------------------------------
if (_btn("btnM50TakipYetenekAc")) _btn("btnM50TakipYetenekAc").addEventListener("click", () => {
  try { m50Gonder({tip: "m50_takip_yetenek", kanal: m50KanalOku(m50TakipKanal), etkin: true}); }
  catch (hata) { m50HataYaz(hata.message); }
});
if (_btn("btnM50TakipYetenekKapat")) _btn("btnM50TakipYetenekKapat").addEventListener("click", () => {
  try { m50Gonder({tip: "m50_takip_yetenek", kanal: m50KanalOku(m50TakipKanal), etkin: false}); }
  catch (hata) { m50HataYaz(hata.message); }
});

// --- Telemetri: mevcut m50PaneliGuncelle'yi sar, yeni bölümleri tazele ---
(function(){
  const asil = window.m50PaneliGuncelle;
  window.m50PaneliGuncelle = function(paket){
    if (typeof asil === "function") asil(paket);
    const p = paket && paket.m50_durum ? paket : {m50_durum: paket || {}};
    const r = (p.m50_durum && typeof p.m50_durum === "object") ? p.m50_durum : {};
    const bagli = m50BagliMi();
    const agVar = typeof ws !== "undefined" && ws && ws.readyState === 1;
    m50VideoKur();
    if (m50AciRozet){
      const az = Number(r.azimut), eg = Number(r.egim);
      m50AciRozet.textContent = (Number.isFinite(az) && Number.isFinite(eg))
        ? ("Az " + az.toFixed(1) + "° / Eğ " + eg.toFixed(1) + "°") : "—";
    }
    m50OnayarListeCiz(r.onayarlar);
    if (m50TaramaRozet){
      const tr = r.tarama && typeof r.tarama === "object" ? r.tarama : {};
      m50TaramaRozet.textContent = (tr.kontrol === "baslat" || tr.kontrol === "devam")
        ? (tr.tur || "") : "";
    }
    if (m50TakipRozet){
      const tk = r.takip && typeof r.takip === "object" ? r.takip : {};
      m50TakipRozet.textContent = tk.etkin ? ((m50T().m50TakipEtkin || "etkin") + (tk.kanal ? " · " + tk.kanal : "")) : "";
    }
    if (m50KimlikRozet){
      m50KimlikRozet.textContent = (sonM50Ayar && sonM50Ayar.kimlik_kayitli)
        ? (m50T().m50KimlikKayitli || "kimlik kayıtlı") : (m50T().m50KimlikYok || "kimlik girilmedi");
    }
    for (const el of document.querySelectorAll(
        "#btnM50AciGit,#btnM50AciOku,#btnM50OnayarCagir,#btnM50OnayarKaydet,#btnM50OnayarSil," +
        "#btnM50OnayarHepsiniSil,.m50-tarama,#btnM50TakipYetenekAc,#btnM50TakipYetenekKapat"))
      el.disabled = !agVar || !bagli;
  };
})();

// Parola panel kapandığında da kesin olarak temizlenir.
const _m50Panel = document.getElementById("yzM50");
if (_m50Panel){
  const kapat = _m50Panel.querySelector(".yuzen-kapat");
  if (kapat) kapat.addEventListener("click", () => { m50BasiliBirak(); m50Parola.value = ""; });
}
m50KopruSeciciCiz();
m50AlanlariEtkinlestir();

// =================================================================
// v2.4.181 — VİDEO ÖNİZLEMESİNDE SÜRÜKLE-BIRAK PTZ (JOYSTICK KİPİ)
// -----------------------------------------------------------------
// M50 kamerasının video görüntüsü üzerinde sol tuşa basılı tutup fareyi
// hareket ettirmek, o yöne doğru PTZ hareketini başlatır (basma noktasından
// uzaklaşma mesafesi hızı belirler); tuş bırakılınca PTZ durur. Mevcut
// panel düğmelerinin kullandığı AYNI süreklilik sözleşmesi (m50_ptz
// {yon, hiz, basili}) kullanılır — Köprü tarafında yeni bir komut
// gerekmez. Yalnız protokolü "m50" olan kameraların <img> öğesinde
// etkindir; "Hedef Seç" dikdörtgeni (kamera_takip.js) video üzerine
// kendi örtüsünü koyduğunda bu örtü olayları önce yakalar, çakışma olmaz.
// =================================================================
(function () {
  "use strict";
  var OLU_BOLGE_PX = 8;     // bu yaricapin altinda hareket "dur" sayilir
  var MAKS_SURUKLEME_PX = 140; // bu mesafede hiz=10'a ulasir
  var GONDER_ARALIK_MS = 120;  // WS'i bogmamak icin sinirli tekrar hizi

  function kamM50Mi(id) {
    var kam = (window._kameralarSon || []).find(
      function (k) { return Number(k.id) === Number(id); });
    return !!(kam && kam.protokol === "m50");
  }

  var surukleme = null; // {img, bx, by, sonYon, sonHiz, sonGonderMs}

  function yonHizHesapla(dx, dy) {
    var mesafe = Math.sqrt(dx * dx + dy * dy);
    if (mesafe < OLU_BOLGE_PX) return { yon: "dur", hiz: 1 };
    var yon = Math.abs(dx) >= Math.abs(dy)
      ? (dx > 0 ? "sag" : "sol")
      : (dy > 0 ? "asagi" : "yukari");
    var oran = Math.min(1, (mesafe - OLU_BOLGE_PX) / MAKS_SURUKLEME_PX);
    var hiz = Math.max(1, Math.min(10, Math.round(1 + oran * 9)));
    return { yon: yon, hiz: hiz };
  }

  // NOT: `m50BasiliGonder` PTZ hizini panelin #m50PtzHiz alanindan okur;
  // surukleme mesafesiyle ORANTILI ozel hiz gondermek icin dogrudan
  // `m50Gonder` kullanilir (panel alanina dokunulmaz).
  function komutGonder(yon, hiz, zorla) {
    var s = surukleme;
    if (!s) return;
    var simdi = Date.now();
    if (!zorla && yon === s.sonYon && hiz === s.sonHiz &&
        simdi - s.sonGonderMs < GONDER_ARALIK_MS) return;
    // Yon degistiyse ONCE eskisini birak (basili paneldeki desenle ayni).
    if (s.sonYon && s.sonYon !== yon && s.sonYon !== "dur") {
      m50Gonder({ tip: "m50_ptz", yon: s.sonYon, hiz: s.sonHiz || 1, basili: false });
    }
    if (yon !== "dur") {
      m50Gonder({ tip: "m50_ptz", yon: yon, hiz: hiz, basili: true });
    }
    s.sonYon = yon; s.sonHiz = hiz; s.sonGonderMs = simdi;
  }

  document.addEventListener("mousedown", function (ev) {
    if (ev.button !== 0) return;
    var img = ev.target && ev.target.closest &&
      ev.target.closest("img.kam-video[data-kamera-id]");
    if (!img) return;
    var id = Number(img.dataset.kameraId);
    if (!kamM50Mi(id)) return;
    if (!m50BagliMi()) return; // baglanti yoksa surukleme baslatilmaz
    ev.preventDefault();
    surukleme = { img: img, bx: ev.clientX, by: ev.clientY,
                 sonYon: "", sonHiz: 0, sonGonderMs: 0 };
    img.classList.add("m50-ptz-aktif");
    try { img.setPointerCapture && img.setPointerCapture(ev.pointerId); } catch (e) {}
  }, true);

  document.addEventListener("mousemove", function (ev) {
    if (!surukleme) return;
    var d = yonHizHesapla(ev.clientX - surukleme.bx, ev.clientY - surukleme.by);
    komutGonder(d.yon, d.hiz, false);
  });

  function suruklemeBitir() {
    if (!surukleme) return;
    var s = surukleme;
    surukleme = null;
    if (s.img) s.img.classList.remove("m50-ptz-aktif");
    if (s.sonYon && s.sonYon !== "dur") {
      m50Gonder({ tip: "m50_ptz", yon: s.sonYon, hiz: s.sonHiz || 1, basili: false });
    }
  }
  document.addEventListener("mouseup", suruklemeBitir);
  document.addEventListener("mouseleave", function (ev) {
    if (surukleme && ev.target === document.documentElement) suruklemeBitir();
  });
  window.addEventListener("blur", suruklemeBitir);
})();
