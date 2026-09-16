/* =================================================================
   GOKTUNGU v2.12.3 -- Yasal sayfalar ortak betigi (M20)
   Turkbey Teknoloji Anonim Sirketi
   -----------------------------------------------------------------
   Yasal metinler tek dosyada tutulmaz; her sayfa kendi TR icerigini
   HTML icinde tasir (JS kapali olsa da okunabilir olmasi gerekir --
   yasal metin icin zorunlu).  Bu betik yalnizca:
     1. ortak ust cubuk / alt bilgi davranisini,
     2. TR/EN gecisini (sayfa kendi EN sozlugunu window.YASAL_EN
        olarak tanimlar),
     3. son guncelleme tarihini
   yonetir.
   ================================================================= */
(function () {
  "use strict";

  var ANAHTAR = "goktungu_landing_dil";
  var ozgun = null;          /* TR kaynak metinler */
  var suanki = "tr";

  /* ---------------------------------------------------------------
     Ceviri altyapisi (dil.js ile ayni sozlesme)
     --------------------------------------------------------------- */
  function ogeler() {
    return document.querySelectorAll("[data-i18n]");
  }

  function ozgunSakla() {
    if (ozgun) return;
    ozgun = {};
    ogeler().forEach(function (o) {
      var a = o.getAttribute("data-i18n");
      ozgun[a] = o.hasAttribute("data-i18n-html")
        ? o.innerHTML : o.textContent;
    });
    /* Oznitelik cevirileri */
    document.querySelectorAll("[data-i18n-attr]").forEach(function (o) {
      var p = (o.getAttribute("data-i18n-attr") || "").split(":");
      if (p.length !== 2) return;
      ozgun["@" + p[1]] = o.getAttribute(p[0]);
    });
    ozgun["@baslik"] = document.title;
  }

  function uygula(dil) {
    ozgunSakla();
    var en = window.YASAL_EN || {};
    var sozluk = (dil === "en") ? en : ozgun;

    /* `{s}` = imzali katalogtan gelen surum. Katalog henuz
       gelmediyse ifade atlanir (yer tutucu ham gorunmesin);
       surumGetir() gelince surumYaz + yeniden uygula cagirir. */
    var s = window.__GOKTUNGU_SURUM || "";
    function surumUygula(v) {
      if (typeof v !== "string" || v.indexOf("{s}") < 0) return v;
      return s ? v.replace(/\{s\}/g, s) : undefined;
    }

    ogeler().forEach(function (o) {
      var a = o.getAttribute("data-i18n");
      var d = surumUygula(sozluk[a]);
      if (d === undefined) d = surumUygula(ozgun[a]);
      if (d === undefined) return;
      if (o.hasAttribute("data-i18n-html")) o.innerHTML = d;
      else o.textContent = d;
    });

    document.querySelectorAll("[data-i18n-attr]").forEach(function (o) {
      var p = (o.getAttribute("data-i18n-attr") || "").split(":");
      if (p.length !== 2) return;
      var d = sozluk[p[1]];
      if (d === undefined) d = ozgun["@" + p[1]];
      if (d !== undefined) o.setAttribute(p[0], d);
    });

    var b = sozluk["@baslik"] || sozluk["meta.baslik"];
    document.title = b || ozgun["@baslik"];
    document.documentElement.lang = dil;
    suanki = dil;

    document.querySelectorAll(".dil-sec button").forEach(function (d) {
      var e = d.getAttribute("data-dil") === dil;
      d.classList.toggle("etkin", e);
      d.setAttribute("aria-pressed", e ? "true" : "false");
    });

    try { localStorage.setItem(ANAHTAR, dil); } catch (e) {}
  }

  function ilkDil() {
    var s = null;
    try { s = localStorage.getItem(ANAHTAR); } catch (e) {}
    if (s === "tr" || s === "en") return s;
    var q = new URLSearchParams(location.search);
    var p = (q.get("dil") || q.get("lang") || "").toLowerCase();
    if (p === "tr" || p === "en") return p;
    var t = (navigator.language || "tr").toLowerCase();
    return t.indexOf("tr") === 0 ? "tr" : "en";
  }

  /* ---------------------------------------------------------------
     Ust cubuk kaydirma golgesi
     --------------------------------------------------------------- */
  function kaydirma() {
    var c = document.getElementById("ustCubuk");
    if (!c) return;
    var f = function () {
      c.classList.toggle("kaydi", window.scrollY > 10);
    };
    f();
    window.addEventListener("scroll", f, { passive: true });
  }

  /* ---------------------------------------------------------------
     Mobil menu
     --------------------------------------------------------------- */
  function menu() {
    var d = document.getElementById("menuAc");
    var m = document.getElementById("anaMenu");
    if (!d || !m) return;
    d.addEventListener("click", function () {
      var a = m.classList.toggle("acik");
      d.setAttribute("aria-expanded", a ? "true" : "false");
    });
  }

  /* ---------------------------------------------------------------
     Yil ve dil dugmeleri
     --------------------------------------------------------------- */
  function kurulum() {
    var y = document.getElementById("yil");
    if (y) y.textContent = String(new Date().getFullYear());

    document.querySelectorAll(".dil-sec button").forEach(function (d) {
      d.addEventListener("click", function () {
        uygula(d.getAttribute("data-dil") || "tr");
      });
    });
  }

  /* ---------------------------------------------------------------
     SURUM YAZIMI (imzali katalogtan)

     Yasal sayfalarda surum numarasi UC yere elle yazilmisti:
     ust bilgi "Sistem surumu", alt kunye satiri ve alt bilgi.
     2.6.1 yayinlandiginda dort yasal sayfanin tamami 2.6.0
     demeye devam etti; yani hukuki metinlerin ust verisi
     dagitilan yazilimla uyusmuyordu. Savunma musterisine giden
     bir sozlesme sayfasinda bu tur bir sapma kabul edilemez.

     Surum artik imzalanmis paketlerin katalogundan okunur.
     HTML'deki degerler JS kapali tarayicida gorunecek yedek olarak
     kalir.

     v2.12.3 -- KAYNAK DEGISTI (olculdu, gercek kusurdu):
     Bu dosya statik `/indir/surumler.json` okuyordu.  Surum deposu
     veritabanina tasindiginda o dosya KALDIRILDI ve uc 404 donmeye
     basladi.  `js/indir.js` bu gecisi yapip `/api/genel/katalog`
     ucuna baglanmisti -- hatta indirme izgarasi olmayan sayfalar
     icin ("yasal sayfalarin alt bilgisi gibi") ozel bir dal bile
     yazilmisti.  Ancak YASAL sayfalar bu betigi hic yuklemedigi
     icin geride kaldilar ve olu uca istek atmaya devam ettiler.
     Hata `catch` dalinda sessizce yutuldugundan fark edilmedi.

     SONUCU: yasal metinlerin ust bilgisindeki "Sistem surumu"
     HTML'deki yedek degerde (2.6.4) donuk kaldi ve alt kunye ile
     protokol basligindaki `{s}` yer tutuculari HAM METIN olarak
     ziyaretciye gorundu.  Bu dosyanin en basinda yazan gerekce
     tam da bunu yasakliyor: hukuki metnin ust verisi dagitilan
     yazilimla uyusmalidir.

     UC SOZLESMESI (dogrulandi, canli):
       GET /api/genel/katalog
       { "urunler": [...],
         "kayitlar": [ { urun, surum, platform, etkin,
                         dosya_var, ... } ] }
     Sayfada gosterilen surum KOPRU surumudur -- sahaya kurulan
     tek paket odur (js/indir.js ile ayni kural).
     --------------------------------------------------------------- */
  function surumYaz(surum) {
    if (!surum) return;
    document.querySelectorAll("[data-surum-yaz]").forEach(function (o) {
      var kalip = o.getAttribute("data-surum-yaz");
      o.textContent = (kalip && kalip.indexOf("{s}") >= 0)
        ? kalip.replace(/\{s\}/g, surum)
        : surum;
    });
  }

  function surumGetir() {
    if (!window.fetch) return;   /* eski tarayici: yedek deger kalir */
    fetch("/api/genel/katalog", { cache: "no-cache" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (y) {
        var kayitlar = (y && Array.isArray(y.kayitlar)) ? y.kayitlar : [];
        /* Yalniz ETKIN ve dosyasi diskte BULUNAN kayitlar sayilir;
           katalog devre disi birakilmis surumleri de dondurur. */
        var kopru = null, ilk = null;
        for (var i = 0; i < kayitlar.length; i++) {
          var k = kayitlar[i];
          if (k.etkin === false || k.dosya_var === false) continue;
          if (!ilk) ilk = k;
          if (k.urun === "kopru") { kopru = k; break; }
        }
        var gosterilen = kopru ? kopru.surum : (ilk ? ilk.surum : "");
        if (!gosterilen) return;
        window.__GOKTUNGU_SURUM = gosterilen;
        surumYaz(gosterilen);
        uygula(suanki);        /* sozlukteki {s} ifadelerini coz */
      })
      .catch(function (e) {
        /* Surum yazimi sayfayi bozmaz ama sebebi konsola dusmelidir:
           bu hatanin sessizce yutulmasi, olu uca yapilan istegin
           fark edilmemesine ve surumun donuk kalmasina yol acti. */
        if (window.console && console.warn) {
          console.warn("[yasal] katalog okunamadi:", e && e.message);
        }
      });
  }

  /* ---------------------------------------------------------------
     Baslat
     --------------------------------------------------------------- */
  function baslat() {
    kurulum();
    kaydirma();
    menu();
    uygula(ilkDil());
    surumGetir();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", baslat);
  } else {
    baslat();
  }

  window.goktunguYasalDil = uygula;
})();
