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

  // v2.4.165: C-UAS modu — yalnız hava aracı tespiti etkin.
  // v2.4.169: Alt sınıflar (3. eleman=1): çok sınıflı YOLO modeliyle
  // sınıf bazlı aç/kapat + hassasiyet. Hiç alt sınıf seçilmemişse tümü
  // açık sayılır (tek sınıflı model / MOG2 ile geriye uyumlu).
  var SINIFLAR = [
    ["hava_araci", "Hava Aracı (ana anahtar)"],
    ["drone", "Drone / İHA", 1],
    ["ucak", "Uçak (sabit kanat)", 1],
    ["helikopter", "Helikopter", 1],
    ["kus", "Kuş (ayırt etme)", 1]
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
      // v2.4.173: takip ayarlarini koru (ayni JSON'da tasinir)
      if (ham.takip_yontem) h.takip_yontem = String(ham.takip_yontem);
      var tt = Number(ham.takip_tolerans);
      if (isFinite(tt) && tt >= 1 && tt <= 30) h.takip_tolerans = tt;
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
    // v2.4.173: tam ekran görünümün (#kamTamEkran) ÜZERİNDE kalmalı —
    // eskiden arkada kalıyor, tam ekrandayken ayar yapılamıyordu.
    el.style.zIndex = "100050";
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
      if (c[2]) det.style.marginLeft = "18px";   // alt sınıf girintisi
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

    // v2.4.173: piksel takip ayarlari (CSRT/KCF/MIL yontemi + kayip
    // toleransi). Cift tikla/dikdortgen ciz ile baslayan pasif piksel
    // takibini etkiler; ucus-seviyesi angajman/takip ile ilgisizdir.
    var takipBolum = document.createElement("details");
    takipBolum.className = "kai-sinif";
    var takipOzet = document.createElement("summary");
    var takipBaslikSpan = document.createElement("span");
    takipBaslikSpan.className = "kai-sinif-ad";
    takipBaslikSpan.textContent = t.kaiTakipAyarBaslik || "Piksel Takip Ayarları";
    takipOzet.appendChild(takipBaslikSpan);
    takipBolum.appendChild(takipOzet);
    var takipIc = document.createElement("div");
    takipIc.className = "kai-sinif-ic";

    var yontemSatir = document.createElement("label");
    yontemSatir.className = "kai-hassas-satir";
    yontemSatir.textContent = t.kaiTakipYontem || "İzleme Yöntemi";
    var yontemSec = document.createElement("select");
    yontemSec.className = "kai-hassas";
    [["", t.kaiTakipYontemVarsayilan || "Otomatik (CSRT — hassas)"],
     ["kcf", t.kaiTakipYontemKcf || "Hızlı (KCF)"],
     ["mil", t.kaiTakipYontemMil || "Basit (MIL)"]].forEach(function (o) {
      var opt = document.createElement("option");
      opt.value = o[0]; opt.textContent = o[1];
      if ((hassasiyet.takip_yontem || "") === o[0]) opt.selected = true;
      yontemSec.appendChild(opt);
    });
    yontemSec.addEventListener("change", function () {
      hassasiyet.takip_yontem = yontemSec.value;
      aiKaydet(kam, gorevler, hassasiyet);
    });
    yontemSatir.appendChild(yontemSec);

    var tolSatir = document.createElement("label");
    tolSatir.className = "kai-hassas-satir";
    tolSatir.textContent = t.kaiTakipTolerans || "Kayıp Toleransı (sn)";
    var tolSlider = document.createElement("input");
    tolSlider.type = "range"; tolSlider.min = "1"; tolSlider.max = "30"; tolSlider.step = "1";
    tolSlider.value = String(hassasiyet.takip_tolerans || 5);
    tolSlider.className = "kai-hassas";
    var tolDeg = document.createElement("span");
    tolDeg.className = "kai-hassas-deger";
    tolDeg.textContent = String(hassasiyet.takip_tolerans || 5);
    tolSlider.addEventListener("input", function () { tolDeg.textContent = tolSlider.value; });
    tolSlider.addEventListener("change", function () {
      hassasiyet.takip_tolerans = Number(tolSlider.value);
      aiKaydet(kam, gorevler, hassasiyet);
    });
    tolSatir.appendChild(tolSlider); tolSatir.appendChild(tolDeg);

    var takipYardim = document.createElement("div");
    takipYardim.className = "kai-hassas-yardim";
    takipYardim.textContent = t.kaiTakipYardim ||
      "CSRT en hassas ama en yavaştır (önerilir); KCF hızlı CPU'larda daha " +
      "akıcıdır. Kayıp toleransı: hedef bu süre görünmezse takip bırakılır.";
    takipIc.append(yontemSatir, tolSatir, takipYardim);
    takipBolum.appendChild(takipIc);
    govde.appendChild(takipBolum);

    var not = document.createElement("div");
    not.className = "kai-panel-not";
    not.textContent = t.kaiNot ||
      "Alt sınıflar (Drone/Uçak/Helikopter/Kuş) yalnız YOLO modeli kuruluysa " +
      "ayırt edilir; hiç alt sınıf seçilmemişse tümü açık sayılır. " +
      "Yerel AI köprüsüz çalışır; görüntü ve tespit bu bilgisayardan çıkmaz.";
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

  // v2.4.189: Görüntü konumu TEK düğme + açılır menü (kullanıcı: "dört
  // düğme yerine bir düğme olsun, menü altında gösterelim"). Düğmenin
  // ikonu seçili konumu gösterir; menü .dk-menu-dropdown desenini kullanır.
  window.kameraGoruntuHedefSecici = function (kameraId) {
    var t = T();
    var kap = document.createElement("div");
    kap.className = "kam-hedef-secici";
    var aktif = window.kameraGoruntuHedefi(kameraId);
    var b = document.createElement("button");
    b.type = "button";
    b.className = "kam-btn kam-hedef-btn secili";
    var dd = document.createElement("div");
    dd.className = "dk-menu-dropdown kam-hedef-menu";
    function ciz() {
      var h = HEDEFLER.find(function (x) { return x[0] === aktif; }) || HEDEFLER[1];
      b.title = (t.kaiHedefBaslik || "Görüntü konumu") + ": " + (t["kaiHedef_" + h[0]] || h[1]);
      b.innerHTML = "<i class='fa-solid " + h[2] + "'></i><i class='fa-solid fa-caret-down kam-hedef-ok'></i>";
      dd.querySelectorAll(".dk-menu-item").forEach(function (it) {
        it.classList.toggle("secili", it.dataset.hedef === aktif);
      });
    }
    HEDEFLER.forEach(function (h) {
      var it = document.createElement("div");
      it.className = "dk-menu-item";
      it.dataset.hedef = h[0];
      it.innerHTML = "<i class='fa-solid " + h[2] + "'></i><span>" + (t["kaiHedef_" + h[0]] || h[1]) + "</span>";
      it.addEventListener("click", function (ev) {
        ev.stopPropagation();
        aktif = h[0];
        window.kameraGoruntuHedefiAyarla(kameraId, h[0]);
        dd.classList.remove("acik");
        ciz();
      });
      dd.appendChild(it);
    });
    b.addEventListener("click", function (ev) {
      ev.stopPropagation();
      if (typeof window.kamMenuAcKapa === "function") window.kamMenuAcKapa(b, dd);
    });
    kap.appendChild(b); kap.appendChild(dd);
    ciz();
    return kap;
  };

  window.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && acikPanel) panelKapat();
  });
})();
