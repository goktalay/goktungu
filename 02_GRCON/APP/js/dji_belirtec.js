// =================================================================
// GOKTUNGU - PROGRAM AYARLARI -> DJI KOPRU BELIRTECI
//
// GDP protokolu (varsayilan port 8790) artik `merhaba` mesajinda
// belirtec ister (bkz. goktungu/dji_kopru.py). Belirtec olmadan
// GONDERILEN her uzak baglanti REDDEDILIR. Android kopru uygulamasi
// belirteci kendi ayar ekranindan alir; kullanici o degeri BURADAN
// kopyalar.
//
// Bu bolum olmasa kimlik dogrulama teknik olarak calisir ama
// KULLANILAMAZ: kullanici Android'e ne yazacagini bilemez.
//
// SUNUCU SOZLESMESI (goktungu/sunucu.py::_dji_belirtec_komut):
//   istek  {"tip":"dji_belirtec_durum"}
//          {"tip":"dji_belirtec_uret"}
//          {"tip":"dji_belirtec_sil"}
//   yanit  {"tip":"dji_belirtec_sonuc","komut":..,"basarili":bool,
//           "hata":str,"tanimli":bool,"kuyruk":str,"belirtec":str}
//
// ## BELIRTEC YALNIZ BIR KEZ GORUNUR
//
// `durum` yaniti belirteci ASLA tasimaz; yalnizca `tanimli` bayragi ve
// son 4 karakter (`kuyruk`) gelir. Tam deger SADECE `uret` yanitinda
// gelir ve kalici bir kutuda gosterilir. Kutu kullanici kapatana kadar
// DURUR: otomatik kapanan bir bildirim kullanicinin belirteci
// kaybetmesine yol acardi (kopru_kimlik.js ile ayni kural).
//
// ## KUYRUK (son 4 karakter) NEDEN GOSTERILIYOR
//
// Kullanici Android'e girdigi belirtecin guncel olani olup olmadigini
// ayirt edebilmeli. Tam belirteci tekrar gostermeden bunu saglamanin
// en ucuz yolu son 4 karakter. Tek basina ise yaramaz: 43 karakterlik
// bir sirrin 4 karakteri kalan 39'u vermez.
//
// ## YENI BELIRTEC ESKISINI GECERSIZ KILAR
//
// Sunucu tek bir belirtec tutar. Yeni uretim eskisini siler; eski
// belirtecle yapilandirilmis cihazlar baglanamaz. Bu davranis
// KULLANICIYA UYARI OLARAK yazilir, cunku sessizce kopan bir saha
// cihazi en pahali kusur turudur.
// =================================================================
"use strict";
// Sunucudan gelen son durum. Popup her acildiginda tazelenir.
window.djiBelirtecDurum = window.djiBelirtecDurum || {
  tanimli: false, kuyruk: "", yuklendi: false
};
// -----------------------------------------------------------------
// Program Ayarlari govdesine bolumu ekler
// -----------------------------------------------------------------
window.djiBelirtecBolumEkle = function(govde){
  const t = (typeof D === "function") ? D() : {};
  const yonetici = (typeof oturumYoneticiMi === "function")
    ? oturumYoneticiMi() : false;
  govde.appendChild(document.createElement("hr"));
  const baslik = document.createElement("div");
  baslik.className = "prog-ayar-altbaslik";
  baslik.innerHTML = "<i class='fa-solid fa-helicopter'></i> " +
    (t.djbBaslik || "DJI K\u00f6pr\u00fc Belirteci");
  govde.appendChild(baslik);
  const aciklama = document.createElement("div");
  aciklama.className = "prog-ayar-aciklama";
  aciklama.textContent = t.djbAciklama ||
    "DJI Android k\u00f6pr\u00fc uygulamas\u0131n\u0131n bu kuruluma " +
    "ba\u011flanabilmesi i\u00e7in bir belirte\u00e7 gerekir. " +
    "Belirte\u00e7 tan\u0131ml\u0131 de\u011filse uzak ba\u011flant\u0131lar " +
    "reddedilir; yaln\u0131zca ayn\u0131 makinedeki k\u00f6pr\u00fc " +
    "\u00e7al\u0131\u015f\u0131r.";
  govde.appendChild(aciklama);
  // --- Durum satiri ---
  const dSat = document.createElement("div");
  dSat.className = "prog-ayar-satir";
  const dEt = document.createElement("span");
  dEt.className = "prog-ayar-etiket";
  dEt.innerHTML = "<i class='fa-solid fa-circle-info'></i> " +
    (t.djbDurum || "Durum");
  const dDeg = document.createElement("span");
  dDeg.className = "prog-ayar-deger";
  dDeg.id = "djbDurumDeger";
  dDeg.textContent = t.djbYukleniyor || "\u2014";
  dSat.appendChild(dEt); dSat.appendChild(dDeg);
  govde.appendChild(dSat);
  // --- Dugmeler ---
  const uSat = document.createElement("div");
  uSat.className = "prog-ayar-satir";
  const uEt = document.createElement("span");
  uEt.className = "prog-ayar-etiket";
  uEt.innerHTML = "<i class='fa-solid fa-key'></i> " +
    (t.djbUretEtiket || "Belirte\u00e7");
  const uBtn = document.createElement("button");
  uBtn.type = "button";
  uBtn.className = "prog-ayar-dugme";
  uBtn.id = "btnDjbUret";
  uBtn.textContent = t.djbUret || "Yeni belirte\u00e7 \u00fcret";
  uBtn.disabled = !yonetici;
  const sBtn = document.createElement("button");
  sBtn.type = "button";
  sBtn.className = "prog-ayar-dugme prog-ayar-dugme-ikincil";
  sBtn.id = "btnDjbSil";
  sBtn.textContent = t.djbSil || "Sil";
  sBtn.disabled = !yonetici;
  uSat.appendChild(uEt);
  uSat.appendChild(uBtn);
  uSat.appendChild(sBtn);
  govde.appendChild(uSat);
  // --- Uretilen belirtec kutusu (kalici) ---
  const sirKutu = document.createElement("div");
  sirKutu.className = "kok-sir-kutu";
  sirKutu.id = "djbSirKutu";
  sirKutu.style.display = "none";
  govde.appendChild(sirKutu);
  // --- Durum/hata satiri ---
  const liste = document.createElement("div");
  liste.className = "kok-liste";
  liste.id = "djbListe";
  govde.appendChild(liste);
  // --- Olaylar ---
  const wsHazir = () =>
    (typeof ws !== "undefined") && ws && ws.readyState === 1;
  uBtn.addEventListener("click", () => {
    if (!yonetici) return;
    if (!wsHazir()){
      window.djbDurumYaz(t.merkezSunucuBaglantiYok ||
        "Sunucu ba\u011flant\u0131s\u0131 yok.", true);
      return;
    }
    // Mevcut belirtec varsa onay istenir: yeni uretim eskisini
    // gecersiz kilar ve sahadaki cihazlar sessizce kopar.
    if (window.djiBelirtecDurum.tanimli){
      const onay = confirm(t.djbUretOnay ||
        "Yeni belirte\u00e7 \u00fcretilirse mevcut belirte\u00e7 " +
        "ge\u00e7ersiz olur ve onu kullanan DJI cihazlar\u0131 " +
        "ba\u011flanamaz.\n\nDevam edilsin mi?");
      if (!onay) return;
    }
    uBtn.disabled = true;
    ws.send(JSON.stringify({tip: "dji_belirtec_uret"}));
  });
  sBtn.addEventListener("click", () => {
    if (!yonetici) return;
    if (!wsHazir()){
      window.djbDurumYaz(t.merkezSunucuBaglantiYok ||
        "Sunucu ba\u011flant\u0131s\u0131 yok.", true);
      return;
    }
    const onay = confirm(t.djbSilOnay ||
      "Belirte\u00e7 silinirse uzak DJI ba\u011flant\u0131lar\u0131 " +
      "reddedilir.\n\nDevam edilsin mi?");
    if (!onay) return;
    sBtn.disabled = true;
    ws.send(JSON.stringify({tip: "dji_belirtec_sil"}));
  });
  window.djbDurumCiz();
  // Popup her acildiginda taze durum istenir.
  if (wsHazir() && yonetici)
    ws.send(JSON.stringify({tip: "dji_belirtec_durum"}));
};
// -----------------------------------------------------------------
// Durum satirini cizer
// -----------------------------------------------------------------
window.djbDurumCiz = function(){
  const t = (typeof D === "function") ? D() : {};
  const el = document.getElementById("djbDurumDeger");
  if (!el) return;
  const d = window.djiBelirtecDurum;
  if (!d.yuklendi){
    el.textContent = t.djbYukleniyor || "\u2014";
    el.className = "prog-ayar-deger";
    return;
  }
  if (d.tanimli){
    el.textContent = (t.djbTanimli || "Tan\u0131ml\u0131") +
      (d.kuyruk ? " (\u2026" + d.kuyruk + ")" : "");
    el.className = "prog-ayar-deger prog-ayar-deger-iyi";
  } else {
    el.textContent = t.djbTanimsiz ||
      "Tan\u0131ms\u0131z \u2014 uzak ba\u011flant\u0131lar reddedilir";
    el.className = "prog-ayar-deger prog-ayar-deger-uyari";
  }
};
// -----------------------------------------------------------------
// Hata/bilgi satiri
// -----------------------------------------------------------------
window.djbDurumYaz = function(metin, kotu){
  const el = document.getElementById("djbListe");
  if (!el) return;
  el.innerHTML = "";
  const d = document.createElement("div");
  d.className = "kok-durum" + (kotu ? " bag-merkez-kotu" : "");
  d.textContent = metin;
  el.appendChild(d);
};
// -----------------------------------------------------------------
// Uretilen belirteci KALICI kutuda gosterir
// -----------------------------------------------------------------
window.djbSirGoster = function(belirtec){
  const t = (typeof D === "function") ? D() : {};
  const el = document.getElementById("djbSirKutu");
  if (!el || !belirtec) return;
  el.innerHTML = "";
  el.style.display = "";
  const uy = document.createElement("div");
  uy.className = "kok-sir-uyari";
  uy.innerHTML = "<i class='fa-solid fa-triangle-exclamation'></i> " +
    (t.djbSirUyari ||
     "Bu belirte\u00e7 bir daha g\u00f6sterilmez. DJI k\u00f6pr\u00fc " +
     "uygulamas\u0131na girmeden \u00f6nce kaydedin.");
  el.appendChild(uy);
  const s = document.createElement("div");
  s.className = "kok-sir-satir";
  const e = document.createElement("span");
  e.className = "kok-sir-etiket";
  e.textContent = t.djbBelirtec || "Belirte\u00e7";
  const g = document.createElement("input");
  g.type = "text";
  g.className = "kok-sir-giris";
  g.readOnly = true;
  g.value = belirtec;
  g.addEventListener("focus", () => g.select());
  s.appendChild(e); s.appendChild(g);
  el.appendChild(s);
  const nasil = document.createElement("div");
  nasil.className = "prog-ayar-aciklama";
  nasil.textContent = t.djbNasil ||
    "Android k\u00f6pr\u00fc uygulamas\u0131: Ayarlar \u2192 " +
    "\u201cK\u00f6pr\u00fc belirteci\u201d alan\u0131na yap\u0131\u015ft\u0131r\u0131n.";
  el.appendChild(nasil);
  const kapat = document.createElement("button");
  kapat.type = "button";
  kapat.className = "prog-ayar-dugme prog-ayar-dugme-ikincil";
  kapat.textContent = t.djbSirKapat || "Kaydettim, kapat";
  kapat.addEventListener("click", () => {
    el.style.display = "none";
    el.innerHTML = "";
  });
  el.appendChild(kapat);
};
// -----------------------------------------------------------------
// WS yanit isleyicisi (sunucu.py -> dji_belirtec_sonuc)
// -----------------------------------------------------------------
window.djiBelirtecSonuc = function(m){
  const t = (typeof D === "function") ? D() : {};
  const d = window.djiBelirtecDurum;
  const yonetici = (typeof oturumYoneticiMi === "function")
    ? oturumYoneticiMi() : false;
  const uBtn = document.getElementById("btnDjbUret");
  const sBtn = document.getElementById("btnDjbSil");
  if (uBtn) uBtn.disabled = !yonetici;
  if (sBtn) sBtn.disabled = !yonetici;
  if (!m || m.basarili === false){
    window.djbDurumYaz((m && m.hata) ||
      (t.djbHata || "\u0130\u015flem ba\u015far\u0131s\u0131z."), true);
    return;
  }
  d.tanimli = !!m.tanimli;
  d.kuyruk = String(m.kuyruk || "");
  d.yuklendi = true;
  window.djbDurumCiz();
  // Belirtec YALNIZ uret yanitinda gelir.
  if (m.belirtec) window.djbSirGoster(m.belirtec);
  if (m.komut === "dji_belirtec_sil")
    window.djbDurumYaz(t.djbSilindi ||
      "Belirte\u00e7 silindi. Uzak DJI ba\u011flant\u0131lar\u0131 " +
      "art\u0131k reddedilir.", false);
};
