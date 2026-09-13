/* ===================================================================
   GOKTUNGU tanitim sayfasi -- ust serit menu gruplari
   -------------------------------------------------------------------
   NEDEN VAR:  Ust seritte yedi duz menu maddesi + tema dugmesi + dil
   secici + iki oturum dugmesi tek satira sigmiyordu.  Kullanici
   bildirimi (2026-08-16): "Saha Yazilimi" iki satira kiriliyor, sag
   uctaki dugmeler tasiyor.  Hamburger yalniz 760 px altinda devreye
   girdigi icin 760-1200 px arasi tum genisliklerde tasma yasaniyordu.

   COZUM:  Maddeler iki acilir gruba toplandi (Sistem / Yetenekler),
   Fiyatlandirma duz kaldi.  Hamburger esigi 900 px'e cikarildi
   (CSS tarafinda).

   SOZLESME:
     .mg          -> grup kabugu, `data-mg` nitelikli
     .mg-dg       -> tetikleyici <button>, `data-mg-dg` nitelikli
     .mg-kutu     -> acilir kutu, `hidden` ile gizlenir
     aria-expanded-> tetikleyicide, true/false
     .mg.acik     -> gorsel durum sinifi (ok donmesi vb.)

   MOBILDE:  <=900 px'de gruplar acilir kutu DEGIL; CSS kutulari
   dogrudan gorunur kilar ve bu betik `mobilMi()` dogruysa tiklama
   isleyicisini etkisiz kilar -- kucuk ekranda ust uste iki katmanli
   acilir menu kullanilamaz.
   =================================================================== */
(function () {
  "use strict";

  var ESIK = 900;            /* CSS'teki @media (max-width:900px) ile ayni */
  var gruplar = [];

  function mobilMi() {
    return window.matchMedia("(max-width: " + ESIK + "px)").matches;
  }

  function kapat(g) {
    var dg = g.querySelector("[data-mg-dg]");
    var k  = g.querySelector(".mg-kutu");
    if (!dg || !k) return;
    g.classList.remove("acik");
    dg.setAttribute("aria-expanded", "false");
    k.hidden = true;
  }

  function ac(g) {
    gruplar.forEach(function (o) { if (o !== g) kapat(o); });
    var dg = g.querySelector("[data-mg-dg]");
    var k  = g.querySelector(".mg-kutu");
    if (!dg || !k) return;
    g.classList.add("acik");
    dg.setAttribute("aria-expanded", "true");
    k.hidden = false;
  }

  function acikMi(g) { return g.classList.contains("acik"); }

  function hepsiniKapat() { gruplar.forEach(kapat); }

  function bagla() {
    gruplar = [].slice.call(document.querySelectorAll("[data-mg]"));
    if (!gruplar.length) return;

    gruplar.forEach(function (g) {
      var dg = g.querySelector("[data-mg-dg]");
      if (!dg) return;

      dg.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        /* Mobilde kutular CSS ile zaten acik; tiklama bir sey yapmaz. */
        if (mobilMi()) return;
        if (acikMi(g)) kapat(g); else ac(g);
      });

      /* Kutudaki bir baglantiya tiklaninca grup kapanir -- yoksa
         kullanici bolume kaydiktan sonra menu acik kaliyor. */
      var k = g.querySelector(".mg-kutu");
      if (k) {
        k.addEventListener("click", function (e) {
          if (e.target.tagName === "A") kapat(g);
        });
      }

      /* Odak gruptan cikinca kapat (klavye ile Tab).  setTimeout
         gerekiyor: focusout aninda yeni odak henuz atanmamis olur. */
      g.addEventListener("focusout", function () {
        window.setTimeout(function () {
          if (mobilMi()) return;
          if (!g.contains(document.activeElement)) kapat(g);
        }, 0);
      });
    });

    /* Dis tiklama */
    document.addEventListener("click", function (e) {
      if (mobilMi()) return;
      var ic = gruplar.some(function (g) { return g.contains(e.target); });
      if (!ic) hepsiniKapat();
    });

    /* Escape */
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") hepsiniKapat();
    });

    /* Genislik degisince durumu sifirla: masaustunden mobile gecerken
       acik kalan grup, mobil duzende cift gorunume yol acardi. */
    var mq = window.matchMedia("(max-width: " + ESIK + "px)");
    var kolla = function () { hepsiniKapat(); };
    if (mq.addEventListener) mq.addEventListener("change", kolla);
    else if (mq.addListener) mq.addListener(kolla);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bagla);
  } else {
    bagla();
  }

  /* Sinav/olcum icin dis dunyaya acilan yardimcilar */
  window.mgHepsiniKapat = hepsiniKapat;
  window.mgMobilMi = mobilMi;
})();
