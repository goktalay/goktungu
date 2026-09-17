// js/diyagram.js — v2.4.239 BAGLANTI DIYAGRAMI
//
// Kullanici istegi: "Tum cihazlar icin ortak bir diagram dugmesi olsun,
// kayitlarin gosterildigi listelerin sonunda kucuk bir dugme; bastigimizda
// baglanti diagramini gostersin ... kutular arasindaki cizgiler baglanti
// durumuna gore renk gostersin; kutular 2 tane de olabilir 5 tane de."
//
// Zincir sunucuda kurulur (`diyagram_bilgi` WS komutu -> kutular + baglar);
// burada yalniz cizilir. Panel acikken 3 sn'de bir tazelenir, panel
// kapaninca zamanlayici durur. Hicbir sifre/kimlik bilgisi gelmez.
(function () {
  const TAZELEME_MS = 3000;
  let _tur = null, _id = 0, _ekFn = null, _zaman = null, _acik = false;

  const panel = () => document.getElementById("yzDiyagram");
  const govde = () => document.getElementById("dygGovde");
  const T = () => (typeof D === "function") ? (D() || {}) : {};

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }

  function gonder() {
    if (!_acik || !_tur) return;
    if (typeof ws === "undefined" || !ws || ws.readyState !== 1) return;
    let ek = null;
    try { ek = (typeof _ekFn === "function") ? _ekFn() : null; } catch (e) { ek = null; }
    try {
      ws.send(JSON.stringify({ tip: "diyagram_bilgi", tur: _tur, id: _id, ek: ek || {} }));
    } catch (e) { /* baglanti kopuk; bir sonraki tazelemede tekrar */ }
  }

  function kapat() {
    _acik = false;
    if (_zaman) { clearInterval(_zaman); _zaman = null; }
  }

  /** Diyagrami acar. tur: baglanti|kamera|ai|radar|eo; ekFn: isteğe ek alan ureten islev. */
  window.diyagramAc = function (tur, id, ekFn) {
    _tur = String(tur || ""); _id = Number(id) || 0; _ekFn = ekFn || null; _acik = true;
    const p = panel();
    if (!p) return;
    const g = govde();
    if (g) g.innerHTML = '<div class="dyg-bos">' + esc(T().dygYukleniyor || "Yükleniyor…") + "</div>";
    if (typeof window.yuzenPanelAc === "function") window.yuzenPanelAc("yzDiyagram");
    else p.classList.remove("yuzen-gizli");
    gonder();
    if (_zaman) clearInterval(_zaman);
    _zaman = setInterval(() => {
      const pp = panel();
      if (!pp || pp.classList.contains("yuzen-gizli")) { kapat(); return; }
      gonder();
    }, TAZELEME_MS);
  };
  window.diyagramKapat = kapat;

  /** ws.js: tip === "diyagram_bilgi" */
  window.diyagramIsle = function (m) {
    if (!_acik || !m) return;
    if (String(m.tur) !== _tur || Number(m.id) !== Number(_id)) return;
    ciz(m);
  };

  function durumMetin(d) {
    const t = T();
    return ({ bagli: t.dygBagli, bekliyor: t.dygBekliyor, kopuk: t.dygKopuk, kapali: t.dygKapali })[d]
      || t.dygKapali || String(d || "");
  }

  // Sunucudan gelen ham durum sozcukleri (bagli/kapali/hata/cevrimici ...)
  // sozluge cevrilir; diger degerler oldugu gibi kalir.
  const DEGER_ESLEM = {
    bagli: "bagli", acik: "bagli", cevrimici: "bagli", calisiyor: "bagli", etkin: "bagli",
    baglaniyor: "bekliyor", bekliyor: "bekliyor",
    hata: "kopuk", kopuk: "kopuk", cevrimdisi: "kopuk",
    kapali: "kapali", durdu: "kapali", yok: "kapali"
  };
  function degerMetin(v) {
    const k = DEGER_ESLEM[String(v || "").toLowerCase()];
    if (!k) return String(v == null ? "" : v);
    return durumMetin(k);
  }

  const AD_ESLEM = {
    "IP": "dygIp", "Platform": "dygPlatform", "Surum": "dygSurum", "Kip": "dygKip",
    "Durum": "dygDurum", "Hata": "dygHata", "Adres": "dygAdres", "Tur": "dygTur",
    "Port": "dygPort", "Host": "dygHost", "Baud": "dygBaud", "Ucus yazilimi": "dygUcusYazilimi",
    "Son gorulme": "dygSonGorulme", "Dron": "dygDron", "Yol": "dygYol", "Yayin": "dygYayin",
    "Servis hatasi": "dygServisHata", "Kopru tarafi": "dygKopruTarafi", "GCS tarafi": "dygGcsTarafi",
    "Veri hizi": "dygVeriHizi", "Nokta": "dygNokta", "SDK hazir": "dygSdkHazir", "Yuk": "dygYuk",
    "Akis": "dygAkis", "SSH": "SSH", "URL": "URL", "FPS": "FPS", "Genislik": "dygGenislik",
    "AI": "AI", "SDK": "SDK", "Azimut/Egim": "dygAzimutEgim", "RTK": "RTK", "Yerel SDK": "dygYerelSdk"
  };
  function adMetin(ad) {
    const t = T(); const k = AD_ESLEM[ad];
    return (k && t[k]) || ad;
  }

  function ikon(tur) {
    return ({
      yazilim: "fa-desktop", kopru: "fa-diagram-project", kanal: "fa-right-left", servis: "fa-gears",
      dron: "fa-plane-up", radar: "fa-satellite-dish", eo: "fa-video", ai: "fa-microchip", kamera: "fa-camera"
    })[tur] || "fa-square";
  }

  function kutuOlustur(k) {
    const t = T();
    const e = document.createElement("div");
    e.className = "dyg-kutu dyg-kutu-" + (k.tur || "") + " dyg-d-" + (k.durum || "kapali");
    const ust = document.createElement("div");
    ust.className = "dyg-ust";
    ust.innerHTML = '<i class="fa-solid ' + ikon(k.tur) + '"></i><span class="dyg-baslik">' + esc(k.baslik) +
      '</span><span class="dyg-nokta dyg-' + esc(k.durum || "kapali") + '" title="' + esc(durumMetin(k.durum)) + '"></span>';
    e.appendChild(ust);
    if (k.alt) { const a = document.createElement("div"); a.className = "dyg-alt"; a.textContent = k.alt; e.appendChild(a); }
    const tbl = document.createElement("div");
    tbl.className = "dyg-satirlar";
    (k.satirlar || []).forEach((s) => {
      const r = document.createElement("div");
      r.className = "dyg-satir";
      r.innerHTML = '<span class="dyg-ad">' + esc(adMetin(s.ad)) + '</span><span class="dyg-deger">' + esc(degerMetin(s.deger)) + "</span>";
      tbl.appendChild(r);
    });
    e.appendChild(tbl);
    if (k.liste && k.liste.length) {
      const lb = document.createElement("div"); lb.className = "dyg-liste-baslik";
      lb.textContent = t.dygDinleyiciler || k.liste_baslik || ""; e.appendChild(lb);
      const ul = document.createElement("div"); ul.className = "dyg-liste";
      k.liste.forEach((x) => {
        const li = document.createElement("div"); li.className = "dyg-liste-satir";
        li.innerHTML = '<span class="dyg-nokta dyg-' + esc(x.durum || "kapali") + '"></span><span class="dyg-ad">' +
          esc(x.ad) + '</span><span class="dyg-deger">' + esc(degerMetin(x.deger)) + "</span>";
        ul.appendChild(li);
      });
      e.appendChild(ul);
    } else if (k.tur === "kopru") {
      const lb = document.createElement("div"); lb.className = "dyg-liste-baslik dyg-soluk";
      lb.textContent = t.dygDinleyiciYok || ""; e.appendChild(lb);
    }
    return e;
  }

  function ciz(m) {
    const g = govde();
    if (!g) return;
    g.innerHTML = "";
    if (m.hata) { g.innerHTML = '<div class="dyg-bos dyg-hata">' + esc(m.hata) + "</div>"; return; }
    const kutular = m.kutular || [], baglar = m.baglar || [];
    const zincir = document.createElement("div");
    zincir.className = "dyg-zincir";
    kutular.forEach((k, i) => {
      if (i > 0) {
        const b = baglar.find((x) => x.hedef === k.id) || baglar[i - 1] || {};
        const c = document.createElement("div");
        c.className = "dyg-bag dyg-" + esc(b.durum || "kapali");
        c.title = durumMetin(b.durum);
        c.innerHTML = '<span class="dyg-cizgi"></span><i class="fa-solid fa-caret-right"></i>';
        zincir.appendChild(c);
      }
      zincir.appendChild(kutuOlustur(k));
    });
    g.appendChild(zincir);
    const acik = document.createElement("div");
    acik.className = "dyg-aciklama";
    acik.innerHTML = ["bagli", "bekliyor", "kopuk", "kapali"].map((d) =>
      '<span class="dyg-nokta dyg-' + d + '"></span>' + esc(durumMetin(d))).join(" &nbsp; ");
    g.appendChild(acik);
  }

  /** Liste satirlarina eklenen ortak kucuk dugme. */
  window.diyagramDugmesi = function (tur, id, ekFn) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "dyg-btn";
    b.title = T().dygDugme || "Bağlantı diyagramı";
    b.setAttribute("data-i18n-title", "dygDugme");
    b.innerHTML = '<i class="fa-solid fa-diagram-project"></i>';
    b.addEventListener("click", (ev) => {
      ev.stopPropagation(); ev.preventDefault();
      window.diyagramAc(tur, id, ekFn);
    });
    return b;
  };
})();
