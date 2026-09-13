/* ====================================================================
 * GRCOFF 2.5.24 — Paylaşımlı kamera AI ayarları + görüntü hedefi modülü
 *
 * Bu modül üç yüzeyin ORTAK kullandığı iki şeyi sağlar:
 *   1) "Yapay Zeka Ayarları" düğmesi + açılır-kapanır (collapsible) panel:
 *      sınıf başına (İnsan / Kara Aracı / Hava Aracı) tanımayı aç-kapat ve
 *      hassasiyet ayarı. Ayarlar mevcut `kamera_kaydet` sözleşmesiyle
 *      (ai_gorevler + ai_hassasiyet) kaydedilir. Hiçbir uçuş/joystick/
 *      angajman/aktüatör komutu üretmez.
 *   2) Görüntü hedefi (display target): canlı görüntü AYNI ANDA tek yerde
 *      gösterilir — harita küçük önizleme / yüzen panel / kameralar paneli
 *      içi / tam ekran. Seçici bu dört kip arasında geçiş yapar.
 *
 * kameralar.js render işini yapar; bu modül yalnız durum + arayüz sağlar.
 * ================================================================== */
(function () {
  "use strict";

  // v2.4.161: "yuz" (yakın çekim yüz tespiti) ayrı aç/kapat + hassasiyet.
  // Tam beden "insan" (yaya) ile bağımsızdır; tespit yine "insan" bildirilir.
  var SINIFLAR = [
    ["insan", "İnsan (tam beden / yaya)"],
    ["yuz", "Yüz (yakın çekim)"],
    ["kara_araci", "Kara Aracı"],
    ["hava_araci", "Hava Aracı"]
  ];
  var HEDEFLER = [
    ["harita", "Harita", "fa-map-location-dot"],
    ["yuzen", "Yüzen", "fa-window-restore"],
    ["panel", "Panel", "fa-table-cells-large"],
    ["tam", "Tam Ekran", "fa-expand"]
  ];
  var VARSAYILAN_HASSASIYET = 50;   // worker'da s=50 mevcut davranışa EŞİT

  function T() {
    try { return (typeof window.D === "function" && window.D()) ||
      (typeof DILLER !== "undefined" && DILLER[typeof aktifDil !== "undefined" ? aktifDil : "tr"]) || {}; }
    catch (e) { return {}; }
  }
  function kamBul(id) {
    id = Number(id);
    return (window._kameralarSon || []).find(function (k) { return Number(k.id) === id; }) || null;
  }
  function gorevSeti(kam) {
    var s = new Set();
    String((kam && kam.ai_gorevler) || "").split(",").forEach(function (x) {
      x = x.trim();
      if (SINIFLAR.some(function (c) { return c[0] === x; })) s.add(x);
    });
    return s;
  }
  function hassasiyetOku(kam) {
    var h = {};
    var ham = kam && kam.ai_hassasiyet;
    if (typeof ham === "string" && ham) { try { ham = JSON.parse(ham); } catch (e) { ham = null; } }
    if (ham && typeof ham === "object") {
      SINIFLAR.forEach(function (c) {
        var v = Number(ham[c[0]]);
        h[c[0]] = (isFinite(v) && v >= 10 && v <= 90) ? v : VARSAYILAN_HASSASIYET;
      });
    } else {
      SINIFLAR.forEach(function (c) { h[c[0]] = VARSAYILAN_HASSASIYET; });
    }
    return h;
  }

  // Kamera kaydını AI alanlarıyla günceller (diğer alanları korur).
  function aiKaydet(kam, gorevSet, hassasiyet) {
    var gorevler = SINIFLAR.filter(function (c) { return gorevSet.has(c[0]); })
      .map(function (c) { return c[0]; }).join(",");
    var msg = {
      tip: "kamera_kaydet", id: kam.id, isim: kam.isim,
      protokol: kam.protokol, url: kam.url,
      lokasyon_id: kam.lokasyon_id || null,
      kopru_ornek_id: kam.kopru_ornek_id || null,
      dron_uid: kam.dron_uid || "",
      ai_gorevler: gorevler,
      ai_hassasiyet: JSON.stringify(hassasiyet)
    };
    if (typeof window.kameraWsGonder === "function") window.kameraWsGonder(msg);
    kam.ai_gorevler = gorevler;
    kam.ai_hassasiyet = JSON.stringify(hassasiyet);
  }

  // ---- AI ayar paneli (yüzen, açılır-kapanır) --------------------
  var acikPanel = null;  // {el, kameraId}

  function panelKapat() {
    if (acikPanel) { acikPanel.el.remove(); acikPanel = null; }
  }

  window.kameraAiAyarPanelAc = function (kameraId) {
    var kam = kamBul(kameraId);
    if (!kam) return;
    if (acikPanel && acikPanel.kameraId === Number(kameraId)) { panelKapat(); return; }
    panelKapat();
    var t = T();
    var gorevler = gorevSeti(kam);
    var hassasiyet = hassasiyetOku(kam);

    var el = document.createElement("div");
    el.className = "kai-panel";
    var bas = document.createElement("div");
    bas.className = "kai-panel-baslik";
    bas.innerHTML = "<span><i class='fa-solid fa-robot'></i> " +
      (t.kaiBaslik || "Yapay Zeka Ayarları") + " — " +
      (kam.isim ? String(kam.isim).replace(/[<>&]/g, "") : ("#" + kam.id)) + "</span>";
    var kapat = document.createElement("button");
    kapat.type = "button"; kapat.className = "kam-btn";
    kapat.innerHTML = "<i class='fa-solid fa-xmark'></i>";
    kapat.addEventListener("click", panelKapat);
    bas.appendChild(kapat);
    el.appendChild(bas);

    var govde = document.createElement("div");
    govde.className = "kai-panel-govde";

    SINIFLAR.forEach(function (c) {
      var deger = c[0], etiket = c[1];
      var det = document.createElement("details");
      det.className = "kai-sinif";
      if (gorevler.has(deger)) det.open = true;

      var ozet = document.createElement("summary");
      var acikCb = document.createElement("input");
      acikCb.type = "checkbox"; acikCb.checked = gorevler.has(deger);
      acikCb.className = "kai-acik";
      acikCb.title = t.kaiTani || "Tanımayı aç/kapat";
      // summary içindeki checkbox tıklaması detaili açıp kapatmasın
      acikCb.addEventListener("click", function (ev) { ev.stopPropagation(); });
      acikCb.addEventListener("change", function () {
        if (acikCb.checked) { gorevler.add(deger); det.open = true; }
        else gorevler.delete(deger);
        rozetTazele();
        aiKaydet(kam, gorevler, hassasiyet);
      });
      var ad = document.createElement("span");
      ad.className = "kai-sinif-ad";
      ad.textContent = t["kaiSinif_" + deger] || etiket;
      var durum = document.createElement("span");
      durum.className = "kai-sinif-durum";
      ozet.append(acikCb, ad, durum);
      det.appendChild(ozet);

      var ic = document.createElement("div");
      ic.className = "kai-sinif-ic";
      var satir = document.createElement("label");
      satir.className = "kai-hassas-satir";
      satir.textContent = t.kaiHassasiyet || "Hassasiyet";
      var slider = document.createElement("input");
      slider.type = "range"; slider.min = "10"; slider.max = "90"; slider.step = "5";
      slider.value = String(hassasiyet[deger]);
      slider.className = "kai-hassas";
      var deg = document.createElement("span");
      deg.className = "kai-hassas-deger";
      deg.textContent = String(hassasiyet[deger]);
      slider.addEventListener("input", function () { deg.textContent = slider.value; });
      slider.addEventListener("change", function () {
        hassasiyet[deger] = Number(slider.value);
        aiKaydet(kam, gorevler, hassasiyet);
      });
      var yardim = document.createElement("div");
      yardim.className = "kai-hassas-yardim";
      yardim.textContent = t.kaiHassasYardim ||
        "Yüksek değer daha çok tespit (ve daha çok yanlış alarm) demektir.";
      satir.appendChild(slider); satir.appendChild(deg);
      ic.append(satir, yardim);
      det.appendChild(ic);
      govde.appendChild(det);

      function rozetTazele() {
        durum.textContent = acikCb.checked ? (t.kaiAcik || "açık") : (t.kaiKapali || "kapalı");
        durum.className = "kai-sinif-durum " + (acikCb.checked ? "iyi" : "");
      }
      rozetTazele();
    });

    var not = document.createElement("div");
    not.className = "kai-panel-not";
    not.textContent = t.kaiNot ||
      "Yerel AI köprüsüz çalışır; görüntü ve tespit bu bilgisayardan çıkmaz. " +
      "Angajman için kamera kalibrasyonu Angajman Başlat panelinden yapılır.";
    govde.appendChild(not);

    el.appendChild(govde);
    document.body.appendChild(el);
    // Konumlandırma: ekran ortası-üstü, kalıcı sürükleme
    if (!(typeof window.pencereKonumUygula === "function" &&
          window.pencereKonumUygula("kai_" + kam.id, el))) {
      el.style.left = Math.max(8, (window.innerWidth - 340) / 2) + "px";
      el.style.top = "80px";
    }
    if (typeof window.popupTasinabilirYap === "function")
      window.popupTasinabilirYap(el, bas, "kai_" + kam.id);
    acikPanel = { el: el, kameraId: Number(kam.id) };
  };

  // Ortak "AI Ayarları" düğmesi (istenen yüzeye eklenir)
  window.kameraAiAyarButonu = function (kameraId, ekstraSinif) {
    var t = T();
    var b = document.createElement("button");
    b.type = "button";
    b.className = "kam-btn kai-ac-btn" + (ekstraSinif ? " " + ekstraSinif : "");
    b.title = t.kaiBaslik || "Yapay Zeka Ayarları";
    b.innerHTML = "<i class='fa-solid fa-robot'></i>";
    b.addEventListener("click", function (ev) {
      ev.stopPropagation();
      window.kameraAiAyarPanelAc(kameraId);
    });
    return b;
  };

  // ---- Görüntü hedefi (tek konumda gösterim) ---------------------
  var HEDEF_KEY = "gcs_kamera_goruntu_hedefi";
  var hedefler = {};
  try { hedefler = JSON.parse(localStorage.getItem(HEDEF_KEY) || "{}") || {}; } catch (e) { hedefler = {}; }

  window.kameraGoruntuHedefi = function (id) {
    var h = hedefler[String(id)];
    return (h === "harita" || h === "yuzen" || h === "panel" || h === "tam") ? h : "yuzen";
  };
  window.kameraGoruntuHedefiAyarla = function (id, hedef) {
    id = Number(id);
    if (!["harita", "yuzen", "panel", "tam"].includes(hedef)) return;
    hedefler[String(id)] = hedef;
    try { localStorage.setItem(HEDEF_KEY, JSON.stringify(hedefler)); } catch (e) {}
    if (typeof window.kameraGoruntuHedefiUygula === "function")
      window.kameraGoruntuHedefiUygula(id);
  };

  // Segment seçici (harita | yüzen | panel | tam)
  window.kameraGoruntuHedefSecici = function (kameraId) {
    var t = T();
    var kap = document.createElement("div");
    kap.className = "kam-hedef-secici";
    var aktif = window.kameraGoruntuHedefi(kameraId);
    HEDEFLER.forEach(function (h) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "kam-hedef-btn" + (h[0] === aktif ? " secili" : "");
      b.dataset.hedef = h[0];
      b.title = t["kaiHedef_" + h[0]] || h[1];
      b.innerHTML = "<i class='fa-solid " + h[2] + "'></i>";
      b.addEventListener("click", function (ev) {
        ev.stopPropagation();
        window.kameraGoruntuHedefiAyarla(kameraId, h[0]);
        kap.querySelectorAll(".kam-hedef-btn").forEach(function (x) {
          x.classList.toggle("secili", x.dataset.hedef === h[0]);
        });
      });
      kap.appendChild(b);
    });
    return kap;
  };

  window.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && acikPanel) panelKapat();
  });
})();
