// =================================================================
// GOKTUNGU v2.4.67 - PROGRAM AYARLARI -> KOPRU KIMLIKLERI BOLUMU
//
// Merkez Uygulama'yi satin alan sirket KAPALI DEVRE calisabilir. Bu
// durumda saha bilgisayarlarindaki kopru yazilimi buluta degil BU
// kuruluma baglanir. Baglanabilmesi icin her saha makinesine bir
// kurulum kimligi (kurulum_uid + gizli) verilmelidir; bu bolum o
// kimlikleri uretir, listeler ve iptal eder.
//
// SUNUCU SOZLESMESI (goktungu/sunucu.py::_kopru_kimlik_komut):
//   istek  {"tip":"kopru_kimlik_liste"}
//          {"tip":"kopru_kimlik_uret","ad":..,"aciklama":..}
//          {"tip":"kopru_kimlik_sil","ornek_id":..}
//   yanit  {"tip":"kopru_kimlik_sonuc","komut":..,"basarili":bool,
//           "hata":str,"liste":[...],"kimlik":{...},"port":int,
//           "uc":str,"canli":int}
//
// ## GIZLI YALNIZ BIR KEZ GORUNUR
//
// Sunucu sirri veritabaninda YALNIZ ozet olarak saklar. `uret`
// yanitindaki `gizli` bir daha okunamaz; bu yuzden uretim sonrasi
// kullaniciya kalici bir kutuda gosterilir ve kopyalatilir. Kutu
// kullanici kapatana kadar DURUR: otomatik kapanan bir bildirim
// kullanicinin sirri kaybetmesine yol acardi.
//
// ## MERKEZ KIPINDE GORUNMEZ
//
// Bulut merkezinde (/app/) kopru kimlikleri kurumsal panelden
// uretilir. Ayni kimligi iki ayri tabloda tutmamak icin sunucu bu
// komutlari merkez kipinde reddeder; arayuz de bolumu gizler.
// =================================================================
"use strict";

// Sunucudan gelen son durum. Popup her acildiginda tazelenir.
window.kopruKimlikDurum = window.kopruKimlikDurum || {
  liste: [], port: 8765, canli: 0, yuklendi: false, merkez_kipi: false
};

// -----------------------------------------------------------------
// Koprunun gireceegi adresi uretir.
//
// Kopru `wss://`/`ws://` bekler. Yerel kurulumda TLS zorunlu degildir
// (ayni makine / kapali ag) ve `ws://` daha az kurulum hatasi uretir.
// PORT MUTLAKA yazilir: kopru port yoksa 443 varsayar ve baglanti
// reddedilir (bkz. kopru/merkez.py::_http_taban aciklamasi).
// -----------------------------------------------------------------
window.kopruUcAdresi = function(konak){
  const p = window.kopruKimlikDurum.port || 8765;
  const k = String(konak || "").trim() ||
    (location.hostname || "127.0.0.1");
  return "ws://" + k + ":" + p + "/kopru";
};

// -----------------------------------------------------------------
// Program Ayarlari govdesine bolumu ekler
// -----------------------------------------------------------------
window.kopruKimlikBolumEkle = function(govde){
  const t = (typeof D === "function") ? D() : {};
  const yonetici = (typeof oturumYoneticiMi === "function")
    ? oturumYoneticiMi() : false;

  // Merkez kipinde bolum HIC cizilmez (sunucu da reddeder).
  if (window.kopruKimlikDurum.merkez_kipi) return;

  govde.appendChild(document.createElement("hr"));

  const baslik = document.createElement("div");
  baslik.className = "prog-ayar-altbaslik";
  baslik.innerHTML = "<i class='fa-solid fa-diagram-project'></i> " +
    (t.kokBaslik || "K\u00f6pr\u00fc Kimlikleri");
  govde.appendChild(baslik);

  const aciklama = document.createElement("div");
  aciklama.className = "prog-ayar-aciklama";
  aciklama.textContent = t.kokAciklama ||
    "Saha bilgisayarlar\u0131ndaki k\u00f6pr\u00fc yaz\u0131l\u0131m\u0131n\u0131n " +
    "bu kuruluma ba\u011flanabilmesi i\u00e7in her makineye bir kimlik " +
    "verilir. Kapal\u0131 devre kullan\u0131mda internet gerekmez.";
  govde.appendChild(aciklama);

  // --- Uc adresi (kopyalanabilir) ---
  const ucSat = document.createElement("div");
  ucSat.className = "prog-ayar-satir prog-ayar-port";
  const ucEt = document.createElement("span");
  ucEt.className = "prog-ayar-etiket";
  ucEt.innerHTML = "<i class='fa-solid fa-link'></i> " +
    (t.kokUcAdres || "K\u00f6pr\u00fc ba\u011flant\u0131 adresi");
  const ucGi = document.createElement("input");
  ucGi.type = "text";
  ucGi.id = "kokUcAdres";
  ucGi.className = "prog-ayar-giris";
  ucGi.readOnly = true;
  ucGi.value = window.kopruUcAdresi();
  ucGi.title = t.kokUcAdresIpucu ||
    "Bu adresi k\u00f6pr\u00fc yaz\u0131l\u0131m\u0131n\u0131n ayarlar\u0131ndaki " +
    "\u0022Merkez adresi\u0022 alan\u0131na yaz\u0131n.";
  ucSat.appendChild(ucEt); ucSat.appendChild(ucGi);
  govde.appendChild(ucSat);

  const ucNot = document.createElement("div");
  ucNot.className = "prog-ayar-aciklama";
  ucNot.id = "kokUcNot";
  ucNot.textContent = t.kokUcNot ||
    "Saha bilgisayar\u0131 ba\u015fka bir makinedeyse 127.0.0.1 yerine bu " +
    "bilgisayar\u0131n a\u011f adresini yaz\u0131n. Port numaras\u0131 " +
    "mutlaka kalmal\u0131d\u0131r.";
  govde.appendChild(ucNot);

  // --- Yeni kimlik uretme ---
  const adGi = document.createElement("input");
  const adSat = document.createElement("div");
  adSat.className = "prog-ayar-satir prog-ayar-port";
  const adEt = document.createElement("span");
  adEt.className = "prog-ayar-etiket";
  adEt.innerHTML = "<i class='fa-solid fa-signature'></i> " +
    (t.kokMakineAd || "Makine ad\u0131");
  adGi.type = "text";
  adGi.id = "kokMakineAd";
  adGi.className = "prog-ayar-giris";
  adGi.placeholder = t.kokMakineAdYer || "\u00d6rn: Saha Ara\u00e7 1";
  adGi.disabled = !yonetici;
  adSat.appendChild(adEt); adSat.appendChild(adGi);
  govde.appendChild(adSat);

  const uSat = document.createElement("div");
  uSat.className = "prog-ayar-satir";
  const uEt = document.createElement("span");
  uEt.className = "prog-ayar-etiket";
  uEt.innerHTML = "<i class='fa-solid fa-key'></i> " +
    (t.kokUretEtiket || "Yeni kimlik");
  const uBtn = document.createElement("button");
  uBtn.type = "button";
  uBtn.className = "prog-ayar-dugme";
  uBtn.id = "btnKkUret";
  uBtn.textContent = t.kokUret || "Kimlik \u00fcret";
  uBtn.disabled = !yonetici;
  uSat.appendChild(uEt); uSat.appendChild(uBtn);
  govde.appendChild(uSat);

  // --- Uretilen sir kutusu (kalici) ---
  const sirKutu = document.createElement("div");
  sirKutu.className = "kok-sir-kutu";
  sirKutu.id = "kokSirKutu";
  sirKutu.style.display = "none";
  govde.appendChild(sirKutu);

  // --- Kimlik listesi ---
  const liste = document.createElement("div");
  liste.className = "kok-liste";
  liste.id = "kokListe";
  govde.appendChild(liste);

  // --- Olaylar ---
  uBtn.addEventListener("click", () => {
    if (!yonetici) return;
    if (typeof ws === "undefined" || !ws || ws.readyState !== 1){
      window.kokDurumYaz(t.merkezSunucuBaglantiYok ||
        "Sunucu ba\u011flant\u0131s\u0131 yok.", true);
      return;
    }
    uBtn.disabled = true;
    ws.send(JSON.stringify({
      tip: "kopru_kimlik_uret",
      ad: adGi.value.trim(),
      aciklama: ""
    }));
  });

  window.kokListeCiz();

  // Popup her acildiginda taze liste istenir.
  if (typeof ws !== "undefined" && ws && ws.readyState === 1 && yonetici)
    ws.send(JSON.stringify({tip: "kopru_kimlik_liste"}));
};

// -----------------------------------------------------------------
// Hata/bilgi satiri
// -----------------------------------------------------------------
window.kokDurumYaz = function(metin, kotu){
  const el = document.getElementById("kokListe");
  if (!el) return;
  el.innerHTML = "";
  const d = document.createElement("div");
  d.className = "kok-durum" + (kotu ? " bag-merkez-kotu" : "");
  d.textContent = metin;
  el.appendChild(d);
};

// -----------------------------------------------------------------
// Kimlik listesini cizer
// -----------------------------------------------------------------
window.kokListeCiz = function(){
  const t = (typeof D === "function") ? D() : {};
  const el = document.getElementById("kokListe");
  if (!el) return;
  const yonetici = (typeof oturumYoneticiMi === "function")
    ? oturumYoneticiMi() : false;
  const dm = window.kopruKimlikDurum;
  el.innerHTML = "";

  if (!dm.yuklendi){
    const b = document.createElement("div");
    b.className = "kok-durum";
    b.textContent = t.kokYukleniyor || "Y\u00fckleniyor\u2026";
    el.appendChild(b);
    return;
  }
  if (!dm.liste.length){
    const b = document.createElement("div");
    b.className = "kok-durum";
    b.textContent = t.kokBosListe ||
      "Hen\u00fcz kimlik \u00fcretilmedi.";
    el.appendChild(b);
    return;
  }

  dm.liste.forEach(k => {
    const sat = document.createElement("div");
    sat.className = "kok-satir" + (k.cevrimici ? " kok-satir-canli" : "");

    const sol = document.createElement("div");
    sol.className = "kok-satir-sol";
    const ad = document.createElement("div");
    ad.className = "kok-ad";
    ad.textContent = (k.ad || "?") +
      (k.ornek_id ? (" #" + k.ornek_id) : "");
    sol.appendChild(ad);

    // Ikincil satir: durum + surum + makine. Sir ASLA yer almaz.
    const alt = document.createElement("div");
    alt.className = "kok-alt";
    const par = [];
    par.push(k.cevrimici
      ? (t.kokCevrimici || "\u00c7evrimi\u00e7i")
      : (t.kokCevrimdisi || "\u00c7evrimd\u0131\u015f\u0131"));
    if (k.surum) par.push("v" + k.surum);
    if (k.makine_adi) par.push(k.makine_adi);
    if (typeof k.dron_sayisi === "number" && k.dron_sayisi > 0)
      par.push(k.dron_sayisi + " " + (t.kokDron || "dron"));
    alt.textContent = par.join(" \u00b7 ");
    sol.appendChild(alt);
    sat.appendChild(sol);

    const silBtn = document.createElement("button");
    silBtn.type = "button";
    silBtn.className = "kok-sil";
    silBtn.title = t.kokSil || "Kimli\u011fi iptal et";
    silBtn.innerHTML = "<i class='fa-solid fa-trash'></i>";
    silBtn.disabled = !yonetici;
    silBtn.addEventListener("click", () => {
      const soru = (t.kokSilOnay ||
        "Bu kimlik iptal edilecek ve makine ba\u011flant\u0131s\u0131 " +
        "kesilecek. S\u00fcrd\u00fcr\u00fcls\u00fcn m\u00fc?");
      const gonder = () => {
        if (typeof ws === "undefined" || !ws || ws.readyState !== 1) return;
        ws.send(JSON.stringify({
          tip: "kopru_kimlik_sil", ornek_id: k.ornek_id}));
      };
      if (typeof window.onayIste === "function") window.onayIste(soru, gonder);
      else if (window.confirm(soru)) gonder();
    });
    sat.appendChild(silBtn);
    el.appendChild(sat);
  });
};

// -----------------------------------------------------------------
// Uretilen sirri gosterir (KALICI kutu)
// -----------------------------------------------------------------
window.kokSirGoster = function(kimlik){
  const t = (typeof D === "function") ? D() : {};
  const el = document.getElementById("kokSirKutu");
  if (!el || !kimlik) return;
  el.innerHTML = "";
  el.style.display = "";

  const uy = document.createElement("div");
  uy.className = "kok-sir-uyari";
  uy.innerHTML = "<i class='fa-solid fa-triangle-exclamation'></i> " +
    (t.kokSirUyari ||
     "Bu bilgiler bir daha g\u00f6sterilmez. K\u00f6pr\u00fc " +
     "yaz\u0131l\u0131m\u0131na girmeden \u00f6nce kaydedin.");
  el.appendChild(uy);

  const alanEkle = (etiket, deger) => {
    const s = document.createElement("div");
    s.className = "kok-sir-satir";
    const e = document.createElement("span");
    e.className = "kok-sir-etiket";
    e.textContent = etiket;
    const g = document.createElement("input");
    g.type = "text";
    g.className = "kok-sir-giris";
    g.readOnly = true;
    g.value = deger || "";
    g.addEventListener("focus", () => g.select());
    s.appendChild(e); s.appendChild(g);
    el.appendChild(s);
  };

  alanEkle(t.kokUcAdres || "Merkez adresi", window.kopruUcAdresi());
  alanEkle(t.kokKurulumUid || "Kurulum kimli\u011fi", kimlik.kurulum_uid);
  alanEkle(t.kokGizli || "Gizli anahtar", kimlik.gizli);

  const kapat = document.createElement("button");
  kapat.type = "button";
  kapat.className = "prog-ayar-dugme prog-ayar-dugme-ikincil";
  kapat.textContent = t.kokSirKapat || "Kaydettim, kapat";
  kapat.addEventListener("click", () => {
    el.style.display = "none";
    el.innerHTML = "";
  });
  el.appendChild(kapat);
};

// -----------------------------------------------------------------
// WS yanit isleyicisi (sunucu.py -> kopru_kimlik_sonuc)
// -----------------------------------------------------------------
window.kopruKimlikSonuc = function(m){
  const t = (typeof D === "function") ? D() : {};
  const dm = window.kopruKimlikDurum;
  const uBtn = document.getElementById("btnKkUret");
  if (uBtn) uBtn.disabled = (typeof oturumYoneticiMi === "function")
    ? !oturumYoneticiMi() : false;

  if (!m || m.basarili === false){
    const h = (m && m.hata) || "";
    // Merkez kipi reddi: bolumu tamamen gizle (tekrar sorulmaz).
    if (h.indexOf("Merkez kipinde") === 0){
      dm.merkez_kipi = true;
      const kok = document.getElementById("kokListe");
      if (kok && kok.parentNode) kok.parentNode.style.display = "none";
      return;
    }
    window.kokDurumYaz(h || (t.kokHata || "\u0130\u015flem ba\u015far\u0131s\u0131z."),
                      true);
    return;
  }

  if (typeof m.port === "number" && m.port > 0){
    dm.port = m.port;
    const u = document.getElementById("kokUcAdres");
    if (u) u.value = window.kopruUcAdresi();
  }
  if (typeof m.canli === "number") dm.canli = m.canli;
  if (Array.isArray(m.liste)){
    dm.liste = m.liste;
    dm.yuklendi = true;
  }
  // Sir YALNIZ uret yanitinda gelir.
  if (m.kimlik && m.kimlik.gizli) window.kokSirGoster(m.kimlik);
  const ad = document.getElementById("kokMakineAd");
  if (ad && m.komut === "kopru_kimlik_uret") ad.value = "";
  window.kokListeCiz();
};
