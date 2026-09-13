// v2.4.14: PWA - service worker kaydi ve "uygulama olarak kur" destegi.
// - SW yalnizca guvenli baglamda kaydolur (https:// veya localhost).
//   HTTP + IP adresiyle erisimde tarayici SW'ye izin vermez; bu durumda
//   sessizce atlanir (arayuz normal calisir, yalnizca kurulum onerisi
//   cikmaz).
// - beforeinstallprompt yakalanir; profil menusunden veya konsoldan
//   window.goktunguUygulamaKur() ile kurulum istemi tetiklenebilir.
(function () {
  "use strict";

  // --- Service worker kaydi ---
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      // v2.4.24: Kayit URL'ine surum eklenir -> "sw.js?s=2.4.24".
      // Bu iki isi birlikte yapar:
      //  1) SW icindeki onbellek adi bu parametreden turetilir; boylece
      //     her surumde ad degisir ve activate eski onbellekleri siler.
      //  2) URL degistigi icin tarayici SW'yi yeni dosya sayar ve
      //     guncellemeyi hemen alir (aksi halde bayat SW kalabilir).
      // Olculen vaka: onbellek adi "goktungu-v2422a"da donmustu; surum
      // 2.4.24 iken 2.4.22 doneminin dosyalari sunuluyordu.
      var s = (typeof window.GCS_SURUM === "string" && window.GCS_SURUM)
                ? window.GCS_SURUM
                : (typeof GCS_SURUM === "string" ? GCS_SURUM : "bilinmeyen");
      navigator.serviceWorker.register("sw.js?s=" + encodeURIComponent(s))
        .then(function (kayit) {
        // Yeni surum etkinlesince sayfa yenilemede devreye girer
        if (kayit && kayit.update) {
          // Her acilista guncelleme kontrolu
          try { kayit.update(); } catch (e) { /* yoksay */ }
        }
      }).catch(function (e) {
        // Guvenli baglam degilse (http + IP) sessizce atla
        console.log("[PWA] SW kaydedilemedi:", e && e.message);
      });
    });
  }

  // --- Kurulum istemi (Chrome/Edge) ---
  let bekleyenIstem = null;

  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    bekleyenIstem = e;
    console.log("[PWA] Uygulama kurulabilir. Kurmak icin: " +
                "adres cubugundaki kur simgesi veya goktunguUygulamaKur()");
    // Profil menusunde "Uygulamayi Kur" ogesi varsa goster
    const oge = document.getElementById("pmUygulamaKur");
    if (oge) oge.style.display = "";
  });

  window.addEventListener("appinstalled", function () {
    bekleyenIstem = null;
    console.log("[PWA] Uygulama kuruldu.");
    const oge = document.getElementById("pmUygulamaKur");
    if (oge) oge.style.display = "none";
  });

  window.goktunguUygulamaKur = function () {
    if (!bekleyenIstem) {
      console.log("[PWA] Kurulum istemi hazir degil " +
                  "(zaten kurulu olabilir veya tarayici desteklemiyor).");
      return;
    }
    bekleyenIstem.prompt();
    bekleyenIstem.userChoice.then(function (secim) {
      console.log("[PWA] Kullanici secimi:", secim && secim.outcome);
      bekleyenIstem = null;
    });
  };

  // Profil menusundeki "Uygulamayi Kur" ogesine tiklama bagla
  document.addEventListener("DOMContentLoaded", function () {
    const oge = document.getElementById("pmUygulamaKur");
    if (oge) {
      oge.addEventListener("click", function () {
        window.goktunguUygulamaKur();
      });
    }
  });
})();
