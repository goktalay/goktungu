// =================================================================
// GOKTUNGU v2.4.53 - MERKEZ SUNUCU SECIMI (baglanti yoneticisi)
//
// Kullanici istegi (birebir):
//   "kullanici sisteme baglanti yoneticisi bolumunde bir baglanti
//    ekleyeceginde sistem acik olan sunuculari gostersin ve kullanici
//    secsin, iletisim tek tarafli olacak ... kullanicilarin kurdugu
//    sunucularin sabit ip'si yok"
//
// Bu yuzden kullaniciya IP/port SORULMAZ. Sahadaki GCS sunuculari
// (kopruler) merkeze kendileri baglanir (client-to-server, WSS 9443);
// merkez ayni soket uzerinden haberlesir. Burada yalnizca "O AN acik"
// olan sunucular listelenir.
//
// Merkeze cagriyi TARAYICI DEGIL GCS SUNUCUSU yapar (WS komutu
// `merkez_sunucular`). Boylece merkez hesabinin sifresi tarayiciya
// hic inmez ve CORS sorunu dogmaz.
// =================================================================

// Secilen sunucunun ham kaydi (kaydetme aninda host alanina cevrilir).
let merkezSeciliSunucu = null;
// Liste bir kez yuklendi mi (diyalog her acilista tazelenir).
let merkezListeYukleniyor = false;

// ---------------------------------------------------------------
// Yardimcilar
// ---------------------------------------------------------------
function merkezDurumYaz(mesaj, tur){
  const el = document.getElementById("bagMerkezDurum");
  if (!el) return;
  el.textContent = mesaj || "";
  el.className = "bag-merkez-durum" + (tur ? (" bag-merkez-" + tur) : "");
  el.style.display = mesaj ? "block" : "none";
}

// Nabiz yasini insan okur bicime cevirir. Merkez `nabiz_yas_sn`
// dondurur; kullanicinin "acik mi" sorusuna cevap veren tek olcut bu.
function merkezNabizMetni(sn){
  const t = (typeof D === "function") ? D() : {};
  const n = Number(sn);
  if (!isFinite(n) || n < 0) return "";
  if (n < 10) return t.merkezNabizSimdi || "\u015fimdi";
  if (n < 90) return Math.round(n) + " " + (t.merkezNabizSn || "sn \u00f6nce");
  return Math.round(n / 60) + " " + (t.merkezNabizDk || "dk \u00f6nce");
}

// Listedeki bir sunucunun gorunen etiketi.
function merkezSunucuEtiket(s){
  const t = (typeof D === "function") ? D() : {};
  const ad = s.sunucu_ad || s.ad || s.ornek_uid || "?";
  const par = [];
  if (s.surum) par.push("v" + s.surum);
  if (s.platform) par.push(s.platform);
  const dron = Number(s.dron_sayisi);
  if (isFinite(dron) && dron > 0)
    par.push(dron + " " + (t.merkezDron || "dron"));
  const nb = merkezNabizMetni(s.nabiz_yas_sn);
  if (nb) par.push(nb);
  return par.length ? (ad + "  \u2014  " + par.join(" \u00b7 ")) : ad;
}

// ---------------------------------------------------------------
// Liste yenileme
// ---------------------------------------------------------------
function merkezSunucuListesiYenile(){
  const t = (typeof D === "function") ? D() : {};
  const sel = document.getElementById("bagMerkezSunucu");
  if (!sel) return;
  if (!ws || ws.readyState !== 1){
    merkezDurumYaz(t.merkezSunucuBaglantiYok ||
      "Sunucu ba\u011flant\u0131s\u0131 yok.", "kotu");
    return;
  }
  merkezListeYukleniyor = true;
  merkezSeciliSunucu = null;
  sel.innerHTML = "";
  const o = document.createElement("option");
  o.value = "";
  o.textContent = t.merkezSunucuYukleniyor || "Y\u00fckleniyor\u2026";
  sel.appendChild(o);
  sel.disabled = true;
  merkezDurumYaz("");
  ws.send(JSON.stringify({tip: "merkez_sunucular"}));
}

// ws.js -> `merkez_sunucular` yanitini karsilar.
window.merkezSunucularGeldi = function(m){
  merkezListeYukleniyor = false;
  const t = (typeof D === "function") ? D() : {};
  const sel = document.getElementById("bagMerkezSunucu");
  if (!sel) return;
  sel.innerHTML = "";
  sel.disabled = false;

  if (!m || m.basarili === false){
    const hata = (m && m.hata) || (t.merkezSunucuHata ||
      "Merkeze ula\u015f\u0131lam\u0131yor.");
    const o = document.createElement("option");
    o.value = "";
    o.textContent = t.merkezSunucuYok || "Sunucu yok";
    sel.appendChild(o);
    sel.disabled = true;
    merkezDurumYaz(hata, "kotu");
    return;
  }

  const liste = Array.isArray(m.sunucular) ? m.sunucular : [];
  if (!liste.length){
    const o = document.createElement("option");
    o.value = "";
    // Bos liste bir HATA DEGIL: hicbir sunucu o an acik olmayabilir.
    // Kullaniciya ne yapacagini soyleyen bir metin gerekir, yoksa
    // "neden bos?" sorusu cevapsiz kalir.
    o.textContent = t.merkezSunucuYok || "A\u00e7\u0131k sunucu yok";
    sel.appendChild(o);
    sel.disabled = true;
    merkezDurumYaz(t.merkezSunucuBosAciklama ||
      "\u015eu anda merkeze ba\u011fl\u0131 sunucu yok. Saha sunucusunu " +
      "\u00e7al\u0131\u015ft\u0131r\u0131p yeniden deneyin.", "uyari");
    return;
  }

  for (const s of liste){
    const o = document.createElement("option");
    o.value = String(s.ornek_uid || s.uid || "");
    o.textContent = merkezSunucuEtiket(s);
    o.dataset.ham = JSON.stringify(s);
    sel.appendChild(o);
  }
  sel.selectedIndex = 0;
  merkezSecimiOku();
  const adres = m.adres ? (" \u2014 " + m.adres) : "";
  merkezDurumYaz(liste.length + " " +
    (t.merkezSunucuAdet || "a\u00e7\u0131k sunucu") + adres, "iyi");
};

// Secimi ham kayda cevirir.
function merkezSecimiOku(){
  const sel = document.getElementById("bagMerkezSunucu");
  merkezSeciliSunucu = null;
  if (!sel || sel.disabled) return;
  const o = sel.options[sel.selectedIndex];
  if (!o || !o.value) return;
  try { merkezSeciliSunucu = JSON.parse(o.dataset.ham || "null"); }
  catch (e) { merkezSeciliSunucu = null; }
  // Baglanti adi bos ise sunucu adiyla onerilir; kullanici degistirebilir.
  const adEl = document.getElementById("bagAd");
  if (adEl && !adEl.value.trim() && merkezSeciliSunucu)
    adEl.value = merkezSeciliSunucu.sunucu_ad ||
                 merkezSeciliSunucu.ad || "";
}

// ---------------------------------------------------------------
// Kaydetme icin host derleme (sunucu tarafi ile AYNI bicim)
//   host = "ornek_uid|sunucu_ad|firma_unvan"
// Bicim baglantilar.py ve sunucu.py _merkez_host_derle ile eslesir.
// ---------------------------------------------------------------
function merkezKayitAlanlari(){
  const t = (typeof D === "function") ? D() : {};
  if (!merkezSeciliSunucu){
    return {hata: t.merkezSunucuSecUyari ||
      "Listeden bir sunucu se\u00e7in."};
  }
  const uid = String(merkezSeciliSunucu.ornek_uid ||
                     merkezSeciliSunucu.uid || "").trim();
  if (!uid){
    return {hata: t.merkezSunucuSecUyari ||
      "Listeden bir sunucu se\u00e7in."};
  }
  return {
    merkez_uid: uid,
    merkez_ad: String(merkezSeciliSunucu.sunucu_ad ||
                      merkezSeciliSunucu.ad || ""),
    merkez_firma: String(merkezSeciliSunucu.firma_unvan ||
                         merkezSeciliSunucu.firma || "")
  };
}

// "uid|ad|firma" dizesini ayristirir (kayit listesi ve duzenleme icin).
function bagMerkezCoz(b){
  const h = String((b && b.host) || "");
  if (!h) return null;
  const par = h.split("|");
  return {uid: par[0] || "", ad: par[1] || "", firma: par[2] || ""};
}

// Kayit karti alt metni.
function bagMerkezOzet(b){
  const t = (typeof D === "function") ? D() : {};
  const p = bagMerkezCoz(b);
  if (!p || !p.uid) return t.merkezSunucuBilinmiyor || "Merkez sunucu";
  const par = [p.ad || p.uid];
  if (p.firma) par.push(p.firma);
  return par.join(" \u00b7 ");
}

// ---------------------------------------------------------------
// Merkez hesabi dogrulama (Program Ayarlari -> Merkez Sunucu)
// ---------------------------------------------------------------
window.merkezDogrulaSonuc = function(m){
  const t = (typeof D === "function") ? D() : {};
  const el = document.getElementById("paMerkezDurum");
  if (!el) return;
  if (!m || m.basarili === false){
    el.textContent = (m && m.hata) ||
      (t.merkezDogrulaHata || "Do\u011frulanamad\u0131.");
    el.className = "pa-merkez-durum bag-merkez-kotu";
    el.style.display = "block";
    return;
  }
  const k = m.kullanici || {};
  const isim = [k.ad, k.soyad].filter(Boolean).join(" ") || k.eposta || "";
  const firma = k.firma_unvan || k.firma_kisa_ad || "";
  el.textContent = (t.merkezDogrulaTamam || "Do\u011fruland\u0131") +
    (isim ? (": " + isim) : "") + (firma ? (" \u2014 " + firma) : "");
  el.className = "pa-merkez-durum bag-merkez-iyi";
  el.style.display = "block";
};

// ---------------------------------------------------------------
// Olay baglama
// ---------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("btnYeniMerkez");
  if (btn) btn.addEventListener("click", () => {
    if (typeof bagDialogAc === "function") bagDialogAc("merkez", null);
  });
  const yen = document.getElementById("btnBagMerkezYenile");
  if (yen) yen.addEventListener("click", merkezSunucuListesiYenile);
  const sel = document.getElementById("bagMerkezSunucu");
  if (sel) sel.addEventListener("change", merkezSecimiOku);
});
