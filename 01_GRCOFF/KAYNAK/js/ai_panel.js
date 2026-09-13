/* =====================================================================
   AI PANEL (v2.4.0)
   Alt-orta panelin sag yarisi: RADAR (hedef sayisi grafigi) ve
   AI TESPIT sekmeleri. AI TESPIT sekmesinde canli tespit akisi:
   tespit edilen yuzler / plakalar kart olarak akar, altinda isim
   (kayitli degilse "Bilinmiyor") yazar. Karta tiklaninca detay
   modali (foto + 3 sn klip) acilir.

   NOT: Bu dosya ai_tespitler.js'ten ONCE yuklenmelidir; temel
   window.aiCanliTespitIsle tanimini burasi yapar, ai_tespitler.js
   kendi islevini zincirler.
   ===================================================================== */
(function () {
  "use strict";

  const sekmeRadar = document.getElementById("sekmeRadar");
  const sekmeAI    = document.getElementById("sekmeAI");
  const sayac      = document.getElementById("aiSekmeSayac");
  const canvas     = document.getElementById("hedefGrafik");
  const akis       = document.getElementById("aiTespitAkis");
  if (!sekmeRadar || !sekmeAI || !akis) return;

  const MAKS_KART = 40;      // akista tutulan azami kart
  let aktifSekme = "radar";
  let okunmamis = 0;

  function t(anahtar, varsayilan) {
    try {
      const d = (typeof D === "function") ? D() : null;
      return (d && d[anahtar]) || varsayilan;
    } catch (e) { return varsayilan; }
  }

  function sekmeSec(ad) {
    aktifSekme = ad;
    const radarMi = (ad === "radar");
    sekmeRadar.classList.toggle("aktif", radarMi);
    sekmeAI.classList.toggle("aktif", !radarMi);
    if (canvas) canvas.style.display = radarMi ? "" : "none";
    akis.style.display = radarMi ? "none" : "";
    if (!radarMi) {
      okunmamis = 0;
      sayacGuncelle();
    }
  }
  function sayacGuncelle() {
    if (!sayac) return;
    if (okunmamis > 0 && aktifSekme !== "ai") {
      sayac.textContent = okunmamis > 99 ? "99+" : String(okunmamis);
      sayac.style.display = "";
    } else {
      sayac.style.display = "none";
    }
  }
  sekmeRadar.addEventListener("click", () => sekmeSec("radar"));
  sekmeAI.addEventListener("click", () => sekmeSec("ai"));

  // (v2.4.0c) Radar arayuzu kapali kurulumlarda RADAR sekmesi CSS ile
  // gizlenir; AI TESPIT otomatik aktif olmali. Radar modu calisma
  // aninda degisebildigi icin body class'i izlenir.
  function radarKapaliUyum() {
    if (document.body.classList.contains("radar-kapali") &&
        aktifSekme === "radar") {
      sekmeSec("ai");
    }
  }
  try {
    new MutationObserver(radarKapaliUyum).observe(document.body,
      { attributes: true, attributeFilter: ["class"] });
    setTimeout(radarKapaliUyum, 1500);
  } catch (e) {}

  function kameraAd(kid) {
    const k = (window._kameralarSon || []).find((x) => x.id === kid);
    return k ? k.ad : ("Kamera #" + kid);
  }

  // v2.4.2: tespit turu -> ikon + varsayilan etiket
  const TUR_IKON = {
    yuz: "fa-user", insan: "fa-person-walking",
    plaka: "fa-car", kara_araci: "fa-truck",
    hava_araci: "fa-helicopter"
  };
  function turIkonHtml(tur) {
    return '<i class="fa-solid ' + (TUR_IKON[tur] || "fa-eye") + '"></i>';
  }
  function turEtiket(tur) {
    if (tur === "hava_araci") return t("aiTurHava", "HAVA ARACI");
    if (tur === "insan") return t("aiTurInsan", "\u0130NSAN");
    if (tur === "kara_araci") return t("aiTurKara", "KARA ARACI");
    return "";
  }

  function kartOlustur(tsp) {
    const kart = document.createElement("div");
    kart.className = "ai-akis-kart";
    const seviye = (tsp.kisi && tsp.kisi.seviye) ||
                   (tsp.arac && tsp.arac.seviye) || "";
    if (seviye === "ARANILAN") kart.classList.add("aranilan");
    else if (seviye === "GUVENSIZ") kart.classList.add("guvensiz");

    // Gorsel: onizleme b64 > foto dosyasi > ikon
    const gorselKaynak = tsp.onizleme_b64
      ? "data:image/jpeg;base64," + tsp.onizleme_b64
      : (tsp.foto ? "/" + tsp.foto : "");
    if (gorselKaynak) {
      const im = document.createElement("img");
      im.src = gorselKaynak;
      im.onerror = () => {
        const yer = document.createElement("div");
        yer.className = "gorsel-yok";
        yer.innerHTML = turIkonHtml(tsp.tur);
        im.replaceWith(yer);
      };
      kart.appendChild(im);
    } else {
      const yer = document.createElement("div");
      yer.className = "gorsel-yok";
      yer.innerHTML = turIkonHtml(tsp.tur);
      kart.appendChild(yer);
    }

    const isim = document.createElement("div");
    isim.className = "isim";
    const kimlik = (tsp.kisi && tsp.kisi.ad) ||
                   (tsp.arac && tsp.arac.plaka) ||
                   tsp.plaka_metin || turEtiket(tsp.tur) || "";
    isim.textContent = kimlik || t("aiBilinmiyor", "Bilinmiyor");
    if (!kimlik) isim.classList.add("bilinmiyor");
    kart.appendChild(isim);

    const alt = document.createElement("div");
    alt.className = "kam";
    const dd = new Date((tsp.ts || Date.now() / 1000) * 1000);
    alt.textContent = dd.toLocaleTimeString([], {hour: "2-digit",
      minute: "2-digit", second: "2-digit"});
    alt.title = kameraAd(tsp.kamera_id);
    kart.appendChild(alt);

    kart.addEventListener("click", () => {
      if (typeof window.aiTespitDetayAc === "function")
        window.aiTespitDetayAc(tsp);
    });
    return kart;
  }

  // Temel canli tespit isleyici (ai_tespitler.js bunu zincirler)
  window.aiCanliTespitIsle = function (m) {
    const tsp = (m && m.tespit) || null;
    if (!tsp) return;
    akis.insertBefore(kartOlustur(tsp), akis.firstChild);
    while (akis.children.length > MAKS_KART)
      akis.removeChild(akis.lastChild);
    if (aktifSekme !== "ai") {
      okunmamis += 1;
      sayacGuncelle();
    }
  };
})();
