// ===============================================================
// GOKTUNGU GCS - KAYITLI DRONLAR (v2.4.42)
// ---------------------------------------------------------------
// Dronlar menusu -> "Kayitli Dronlar"
//
// Sisteme bugune kadar girmis ve yazilim tarafindan kalici bir kimlik
// (UID) verilmis tum dronlari listeler.
//
// YETKI KURALI (sunucu tarafinda uygulanir; burada yalnizca gorunum):
//   - pilot   : yalnizca kendi ucurdugu dronlar
//   - yonetici: tum dronlar + her satirda PILOT ADI kolonu
// Istemci "hepsini ver" diyemez; `dron_gecmis_liste` cevabini sunucu
// oturumdaki role gore filtreler. Buradaki rol kontrolu SADECE pilot
// kolonunu cizmek icindir, veri gizleme amaci tasimaz.
//
// Her acilista liste yenilenir (kullanici istegi). Basliktaki yenile
// dugmesi ile de elle tazelenir.
//
// Panel deseni: dkMiniPopupBaslikKur (History/ARM check ile ayni)
// ===============================================================
"use strict";

let _kdPopup = null;       // acik popup DOM'u
let _kdVeri = [];          // sunucudan gelen dron agaci
let _kdYukleniyor = false;
let _kdSonHata = "";

function kdD() {
  return (typeof D === "function") ? D() : {};
}

// Yonetici mi? (pilot adi kolonu icin) - gecmis.js ile ayni desen
function kdYonetici() {
  return (typeof oturum !== "undefined" && oturum &&
          oturum.rol === "yonetici");
}

function kdKacis(s) {
  return String(s === null || s === undefined ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ---------------------------------------------------------------
// Acilis / kapanis
// ---------------------------------------------------------------
function kayitliDronlarAc() {
  if (_kdPopup) {
    // Zaten acik: listeyi tazele (kullanici istegi: her acilista yenile)
    kdListeIste();
    return;
  }
  const t = kdD();
  const pop = document.createElement("div");
  pop.className = "kd-popup";
  _kdPopup = pop;

  // Baslik: tasinabilir + kapat (dronlar.js ortak yardimcisi)
  const bas = dkMiniPopupBaslikKur(pop, t.kdBaslik || "KAYITLI DRONLAR",
    "kayitliDronlar", "fa-clipboard-list");
  const kapatBtn = pop.querySelector(".dk-mp-kapat");
  if (kapatBtn) kapatBtn.addEventListener("click", kayitliDronlarKapat);

  // Yenile dugmesi basliga, kapatmanin soluna
  const yenile = document.createElement("button");
  yenile.className = "kd-yenile";
  yenile.title = t.kdYenile || "Yenile";
  yenile.innerHTML = "<i class='fa-solid fa-rotate-right'></i>";
  yenile.addEventListener("click", (ev) => {
    ev.stopPropagation();
    kdListeIste();
  });
  if (kapatBtn) bas.insertBefore(yenile, kapatBtn);
  else bas.appendChild(yenile);

  const govde = document.createElement("div");
  govde.className = "kd-govde";
  govde.innerHTML =
    "<div class='kd-ust'>" +
      "<input type='text' id='kdAra' class='kd-ara' placeholder='" +
        kdKacis(t.kdAra || "Ara: isim, UID, sysid...") + "'>" +
      "<span class='kd-sayi' id='kdSayi'></span>" +
    "</div>" +
    "<div class='kd-liste' id='kdListe'></div>";
  pop.appendChild(govde);

  // Yeniden boyutlandirma tutamaci (sag-alt kose).
  //
  // Panel varsayilan olarak `left:50%; transform:translateX(-50%)` ile
  // ortalanir; olculeri `min(940px,94vw)` ve `max-height:76vh` ile
  // GORUNTU ALANINA baglidir. Elle boyutlandirmada bu iki kural sorun
  // cikarir:
  //   - transform ile ortalanmis bir ogenin genisligi buyudugunde panel
  //     iki yana birlikte acilir ve imlec tutamactan kayar;
  //   - vw/vh tabanli olcu, piksel atamasini pencere yeniden
  //     boyutlandirildiginda sessizce ezer.
  // Bu yuzden ilk suruklemede panel o anki gorunen dikdortgenine
  // PIKSEL olarak sabitlenir (left/top/width/height) ve transform
  // kaldirilir: panel yerinden ziplamaz, buyume yalniz sag/alt yone olur.
  const tutamac = document.createElement("div");
  tutamac.className = "kd-resize";
  tutamac.title = t.kdResize || "Boyutland\u0131r";
  tutamac.innerHTML =
    "<i class='fa-solid fa-grip-lines' style='transform:rotate(-45deg);'></i>";
  pop.appendChild(tutamac);

  let kdBoyut = null;
  tutamac.addEventListener("pointerdown", (ev) => {
    const r = pop.getBoundingClientRect();
    pop.style.transform = "none";
    pop.style.left = r.left + "px";
    pop.style.top = r.top + "px";
    pop.style.width = r.width + "px";
    pop.style.height = r.height + "px";
    pop.style.maxHeight = "none";
    kdBoyut = { w: r.width, h: r.height, x: ev.clientX, y: ev.clientY };
    try { tutamac.setPointerCapture(ev.pointerId); } catch (e) {}
    ev.preventDefault();
    ev.stopPropagation();
  });
  tutamac.addEventListener("pointermove", (ev) => {
    if (!kdBoyut) return;
    const r = pop.getBoundingClientRect();
    // Alt sinir: baslik + arama satiri + birkac liste satiri sigsin.
    // Ust sinir: panel gorunur alandan tasmasin (sol/ust kose sabit).
    const w = Math.max(420, Math.min(kdBoyut.w + ev.clientX - kdBoyut.x,
                                     window.innerWidth - r.left - 8));
    const h = Math.max(220, Math.min(kdBoyut.h + ev.clientY - kdBoyut.y,
                                     window.innerHeight - r.top - 8));
    pop.style.width = w + "px";
    pop.style.height = h + "px";
  });
  const kdBirak = (ev) => {
    if (!kdBoyut) return;
    kdBoyut = null;
    try { tutamac.releasePointerCapture(ev.pointerId); } catch (e) {}
    // Olcuyu KALICI kaydet (3. arguman = boyutlu). Ortak baslik
    // yardimcisi ayni anahtarla yalniz konumu kaydeder; burada boyutu da
    // ekliyoruz, boylece panel bir sonraki acilista ayni olcude gelir.
    if (typeof window.pencereKonumKaydet === "function") {
      window.pencereKonumKaydet("kayitliDronlar", pop, true);
    }
  };
  tutamac.addEventListener("pointerup", kdBirak);
  tutamac.addEventListener("pointercancel", kdBirak);

  document.body.appendChild(pop);

  // Kayitli OLCUYU geri yukle. Ortak baslik yardimcisi (dronlar.js)
  // `setTimeout(...,0)` icinde yalniz KONUMU uygular; boyut icin ucuncu
  // argumanla ikinci bir cagri gerekir.
  //
  // v2.4.52 - TRANSFORM KUSURU DUZELTILDI:
  // Onceki surumde transform YALNIZ "genislik degistiyse" kaldiriliyordu.
  // Kullanici paneli hic boyutlandirmamissa `translateX(-50%)` yerinde
  // kalip paneli genisligin yarisi kadar (940px'te 470px) SOLA kaydiriyordu.
  // Ekran icinde kaldigi icin fark edilmemisti; ayni kusur GCCDUAL
  // panelinde (.i2-popup, 720px + translate(-50%,-50%)) -300'e tasarak
  // gorunur hale geldi ve panel tutulamaz oldu.
  // Artik transform pencereKonumUygula() icinde KOSULSUZ sifirlaniyor.
  //
  // Ek olarak: kayitli konum gorunur alanin tamamen disindaysa (ekran
  // duzeni degismis ya da eski surum bozuk deger yazmis) kayit SILINIR
  // ve panel CSS varsayilaninda ortada acilir.
  setTimeout(() => {
    if (!_kdPopup) return;
    if (typeof window.pencereKonumUygula !== "function") return;
    const gecerli = (typeof window.pencereKonumGecerliMi === "function")
      ? window.pencereKonumGecerliMi("kayitliDronlar",
                                     pop.offsetWidth, pop.offsetHeight)
      : true;
    if (!gecerli) {
      if (typeof window.pencereKonumSil === "function")
        window.pencereKonumSil("kayitliDronlar");
      return;   // CSS varsayilani: ortada
    }
    if (window.pencereKonumUygula("kayitliDronlar", pop, true)
        && pop.style.width) {
      pop.style.maxHeight = "none";
    }
  }, 0);

  const ara = pop.querySelector("#kdAra");
  if (ara) ara.addEventListener("input", kdCiz);

  kdListeIste();
}

function kayitliDronlarKapat() {
  if (_kdPopup) { _kdPopup.remove(); _kdPopup = null; }
}

function kdListeIste() {
  _kdYukleniyor = true;
  _kdSonHata = "";
  kdCiz();
  if (typeof ws !== "undefined" && ws && ws.readyState === 1) {
    // WS komutu History paneli ile paylasiliyor; sunucu role gore filtreler
    ws.send(JSON.stringify({ tip: "dron_gecmis_liste" }));
  } else {
    _kdYukleniyor = false;
    _kdSonHata = kdD().kdBagliDegil || "Sunucu ba\u011flant\u0131s\u0131 yok";
    kdCiz();
  }
}

// ws.js -> dron_gecmis_liste cevabi buraya da dusuyor.
// History paneli ayni veriyi kullaniyor; iki tuketici de salt okuma
// yaptigi icin birbirini etkilemez.
window.kayitliDronlarVeri = function (liste) {
  _kdVeri = Array.isArray(liste) ? liste : [];
  // Kamera formu bu referansı yalnız seçim listesi için okur.
  window._kayitliDronlarSon = _kdVeri.slice();
  _kdYukleniyor = false;
  if (_kdPopup) kdCiz();
  if (typeof window.kameraDronSeciciTazele === "function")
    window.kameraDronSeciciTazele();
};

function kdSure(sn) {
  sn = Math.max(0, Math.round(sn || 0));
  const s = Math.floor(sn / 3600);
  const d = Math.floor((sn % 3600) / 60);
  if (s > 0) return s + "s " + d + "d";
  return d + "d";
}

// Bir dronun ucus adedi, toplam sure ve son ucus zamani
function kdOzet(dr) {
  const uc = dr.ucuslar || [];
  let toplam = 0;
  let son = 0;
  for (const u of uc) {
    toplam += (u.sure || 0);
    if ((u.baslangic || 0) > son) son = u.baslangic || 0;
  }
  return { adet: uc.length, toplam, son };
}

// Yonetici gorunumu: dronu ucuran pilotlarin adlari (tekrarsiz)
function kdPilotlar(dr) {
  const set = [];
  for (const u of (dr.ucuslar || [])) {
    const kaynak = (u.pilotlar_ad && u.pilotlar_ad.length)
      ? u.pilotlar_ad : (u.pilotlar || []);
    for (const p of kaynak) {
      if (p && set.indexOf(p) === -1) set.push(p);
    }
  }
  return set;
}

function kdCiz() {
  const kutu = document.getElementById("kdListe");
  if (!kutu) return;
  const t = kdD();
  const yonetici = kdYonetici();

  if (_kdYukleniyor) {
    kutu.innerHTML = "<div class='kd-bos'>" +
      kdKacis(t.kdYukleniyor || "Y\u00fckleniyor...") + "</div>";
    return;
  }
  if (_kdSonHata) {
    kutu.innerHTML = "<div class='kd-bos kd-hata'>" +
      kdKacis(_kdSonHata) + "</div>";
    return;
  }

  const aramaEl = document.getElementById("kdAra");
  const arama = (aramaEl ? aramaEl.value : "").trim().toLowerCase();

  let liste = _kdVeri.slice();
  if (arama) {
    liste = liste.filter(dr => {
      const alan = [
        dr.isim, dr.uid, dr.sysid, dr.otopilot, dr.arac_sinifi,
      ].join(" ").toLowerCase();
      const pilotAlan = yonetici
        ? kdPilotlar(dr).join(" ").toLowerCase() : "";
      return alan.indexOf(arama) >= 0 || pilotAlan.indexOf(arama) >= 0;
    });
  }

  // En son ucan en ustte
  liste.sort((a, b) => kdOzet(b).son - kdOzet(a).son);

  const sayi = document.getElementById("kdSayi");
  if (sayi) sayi.textContent = liste.length + " / " + _kdVeri.length;

  if (liste.length === 0) {
    kutu.innerHTML = "<div class='kd-bos'>" +
      kdKacis(_kdVeri.length
        ? (t.kdAramaBos || "Aramaya uyan dron yok")
        : (t.kdBos || "Kay\u0131tl\u0131 dron yok")) + "</div>";
    return;
  }

  let html = "<table class='kd-tablo'><thead><tr>" +
    "<th></th>" +
    "<th>" + kdKacis(t.kdDron || "DRON") + "</th>" +
    "<th>" + kdKacis(t.kdUid || "UID") + "</th>" +
    "<th>" + kdKacis(t.kdSinif || "T\u00dcR") + "</th>" +
    (yonetici ? "<th>" + kdKacis(t.kdPilot || "P\u0130LOT") + "</th>" : "") +
    "<th class='kd-sag'>" + kdKacis(t.kdUcus || "U\u00c7U\u015e") + "</th>" +
    "<th class='kd-sag'>" + kdKacis(t.kdSure || "S\u00dcRE") + "</th>" +
    "<th>" + kdKacis(t.kdSon || "SON U\u00c7U\u015e") + "</th>" +
    "</tr></thead><tbody>";

  for (const dr of liste) {
    const oz = kdOzet(dr);
    const sonTxt = oz.son ? new Date(oz.son * 1000).toLocaleString() : "--";
    // UID donanim serisi oldugunda 16+ hane olabilir -> kisalt,
    // tam degeri title'a koy.
    const uidTam = dr.uid || "";
    const uidKisa = uidTam.length > 14
      ? uidTam.slice(0, 6) + "\u2026" + uidTam.slice(-4)
      : (uidTam || "--");
    const sinif = dr.arac_sinifi || dr.otopilot || "--";
    const pilotHucre = yonetici
      ? "<td class='kd-pilot'>" +
        kdKacis(kdPilotlar(dr).join(", ") || "--") + "</td>"
      : "";

    html +=
      "<tr class='kd-satir' data-anahtar='" + kdKacis(dr.anahtar) + "'>" +
        "<td><span class='kd-renk' style='background:" +
          kdKacis(dr.renk || "#888") + "'></span></td>" +
        "<td class='kd-ad'>" +
          kdKacis(dr.isim || ("DRON " + dr.sysid)) + "</td>" +
        "<td class='kd-uid' title='" + kdKacis(uidTam) + "'>" +
          kdKacis(uidKisa) + "</td>" +
        "<td>" + kdKacis(sinif) + "</td>" +
        pilotHucre +
        "<td class='kd-sag'>" + oz.adet + "</td>" +
        "<td class='kd-sag'>" + kdKacis(kdSure(oz.toplam)) + "</td>" +
        "<td class='kd-son'>" + kdKacis(sonTxt) + "</td>" +
      "</tr>";
  }
  html += "</tbody></table>";
  kutu.innerHTML = html;

  // Satira tiklayinca: History panelini ac ve BU DRONA filtrele
  for (const tr of kutu.querySelectorAll(".kd-satir")) {
    tr.addEventListener("click", () => {
      kdDronaGit(tr.getAttribute("data-anahtar"));
    });
  }
}

// Secilen dronun ucus kayitlarina gec.
// History paneli ayni WS verisini kullaniyor; oradaki dron secimini
// programatik olarak ayarliyoruz (gecmis.js -> gecmisDronaFiltrele).
function kdDronaGit(anahtar) {
  if (!anahtar) return;
  if (typeof window.gecmisDronaFiltrele === "function") {
    window.gecmisDronaFiltrele(anahtar);
  }
}

window.kayitliDronlarAc = kayitliDronlarAc;
