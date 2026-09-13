/* =================================================================
   GOKTUNGU v2.9.0 - Tanitim sitesi sayfa etkilesimleri
   VEILOX Savunma Anonim Sirketi

   M19 degisiklikleri:
   - Satir ici stil atamalari CSS siniflarina tasindi (.gorunume-gir)
   - prefers-reduced-motion destegi: hareket azaltma tercihi varsa
     tum gecisler atlanir, icerik dogrudan gorunur
   - Istatistik sayaclari (3 / 4 / 47) gorunume girince sayarak artar
   - Surum rozeti: API daha ESKI surum bildirirse HTML'deki deger
     korunur (v2.5.0 donen API v2.5.1 metnini ezmesin)
   - Cerez bildirim bandi (yalniz zorunlu cerez kullanildigi icin
     bilgilendirme yeterlidir, onay sarti yoktur)
   ================================================================= */
(function () {
  "use strict";

  /* --- Hareket azaltma tercihi --- */
  var azalt = false;
  try {
    azalt = window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch (e) { /* yok say */ }

  /* --- Telif yili --- */
  var y = document.getElementById("yil");
  if (y) y.textContent = new Date().getFullYear();

  /* --- Ust cubuk kaydirma durumu --- */
  var cubuk = document.getElementById("ustCubuk");
  function kaydirmaDurum() {
    if (!cubuk) return;
    if (window.scrollY > 12) cubuk.classList.add("kaydi");
    else cubuk.classList.remove("kaydi");
  }
  window.addEventListener("scroll", kaydirmaDurum, { passive: true });
  kaydirmaDurum();

  /* --- Mobil menu --- */
  var dg = document.getElementById("menuAc");
  var menu = document.getElementById("anaMenu");
  if (dg && menu) {
    dg.addEventListener("click", function () {
      var acik = menu.classList.toggle("acik");
      dg.setAttribute("aria-expanded", acik ? "true" : "false");
      dg.innerHTML = acik ? "&times;" : "&#9776;";
    });
    menu.addEventListener("click", function (e) {
      if (e.target.tagName === "A" && menu.classList.contains("acik")) {
        menu.classList.remove("acik");
        dg.setAttribute("aria-expanded", "false");
        dg.innerHTML = "&#9776;";
      }
    });
  }

  /* --- Bolum ici baglantilarda ust cubuk yuksekligini telafi et --- */
  document.querySelectorAll('a[href^="#"]').forEach(function (a) {
    a.addEventListener("click", function (e) {
      var id = a.getAttribute("href");
      if (!id || id === "#") return;
      var h = document.querySelector(id);
      if (!h) return;
      e.preventDefault();
      var ust = h.getBoundingClientRect().top + window.scrollY - 78;
      window.scrollTo({ top: ust, behavior: azalt ? "auto" : "smooth" });
      if (history.replaceState) history.replaceState(null, "", id);
    });
  });

  /* ---------------------------------------------------------------
     Canlilik gostergesi: /api/genel/saglik
     ---------------------------------------------------------------
     v2.9.0'DA DUZELTILDI.  Bu blok `/company/api/durum` ucunu
     cagiriyordu; sunucuda BOYLE BIR UC YOK -- gercek uc ailesi
     `/api/genel/*`.  Cagri yazildigi gunden beri 404 donuyordu ve
     hata `.catch` icinde sessizce yutuldugu icin fark edilmemisti.
     Sonuc: hero rozetindeki "sistem cevrimici" gostergesi HIC
     yanmiyordu.  (Ayni desen daha once `indir.js`'te `/surumler.json`
     cagrisinda ve `/app/` altindaki eksik logo dosyalarinda yasandi:
     sessizce yutulan hata, kusuru aylarca gorunmez kilar.)

     SURUM YAZIMI BURADAN KALDIRILDI.  Rozetteki surum, sahaya kurulan
     KOPRU surumudur ve `js/indir.js` onu `/api/genel/katalog` ucundan
     okuyup `data-surum-yaz` ogelerine yazar.  Buradaki API ise
     (`/api/genel/kimlik`) MERKEZ MODULUNUN surumunu (1.0.0) bildirir;
     ikisini ayni yere yazmak donuk-surum kusurunu geri getirirdi.
     Bu yuzden bu blok artik YALNIZCA canlilik isaretler.
     --------------------------------------------------------------- */
  fetch("/api/genel/saglik", { cache: "no-cache" })
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(function (d) {
      if (!d || d.durum !== "ayakta") return;
      var nokta = document.getElementById("heroRozetNokta");
      if (nokta) nokta.classList.add("canli");
      var el = document.getElementById("heroRozetMetin");
      if (el) el.classList.add("cevrimici");
    })
    .catch(function (e) {
      /* Sessiz yutma YASAK: yukaridaki kusur tam bu yuzden aylarca
         gorunmedi.  Gosterge yanmasa da sebebi konsola dusmelidir. */
      if (window.console && console.warn) {
        console.warn("[sayfa] saglik ucu okunamadi:", e && e.message);
      }
    });

  /* ---------------------------------------------------------------
     Gorunume giren ogeleri belirt
     --------------------------------------------------------------- */
  var hedefler = document.querySelectorAll(
    ".kart, .ist-kart, .adim, .guv, .ss-kucuk, .plat-kart, .proto-kart");

  if (azalt || !("IntersectionObserver" in window)) {
    hedefler.forEach(function (el) { el.classList.add("gorundu"); });
  } else {
    hedefler.forEach(function (el) { el.classList.add("gorunume-gir"); });
    var izleyici = new IntersectionObserver(function (girisler) {
      girisler.forEach(function (gi) {
        if (!gi.isIntersecting) return;
        gi.target.classList.add("gorundu");
        izleyici.unobserve(gi.target);
      });
    }, { threshold: 0.08, rootMargin: "0px 0px -40px 0px" });
    hedefler.forEach(function (el) { izleyici.observe(el); });
  }

  /* ---------------------------------------------------------------
     Istatistik sayaclari
     ---------------------------------------------------------------
     data-sayi ozniteligindeki hedefe kadar sayar.  Hareket azaltma
     tercihi varsa dogrudan son deger yazilir.
     --------------------------------------------------------------- */
  function sayacBaslat(el) {
    var hedef = parseInt(el.getAttribute("data-sayi") || "0", 10) || 0;
    if (azalt) { el.textContent = String(hedef); return; }
    var sure = 900, bas = null;
    function adim(t) {
      if (bas === null) bas = t;
      var o = Math.min((t - bas) / sure, 1);
      // Yumusak yavaslama (easeOutCubic)
      var k = 1 - Math.pow(1 - o, 3);
      el.textContent = String(Math.round(hedef * k));
      if (o < 1) requestAnimationFrame(adim);
      else el.textContent = String(hedef);
    }
    requestAnimationFrame(adim);
  }

  var sayaclar = document.querySelectorAll("[data-sayi]");
  if (sayaclar.length) {
    if (azalt || !("IntersectionObserver" in window)) {
      sayaclar.forEach(sayacBaslat);
    } else {
      var si = new IntersectionObserver(function (g) {
        g.forEach(function (gi) {
          if (!gi.isIntersecting) return;
          sayacBaslat(gi.target);
          si.unobserve(gi.target);
        });
      }, { threshold: 0.5 });
      sayaclar.forEach(function (el) {
        el.textContent = "0";
        si.observe(el);
      });
    }
  }

  /* ---------------------------------------------------------------
     Cerez bildirim bandi
     ---------------------------------------------------------------
     Sitede yalniz zorunlu cerez/yerel depolama kullanilir (dil
     tercihi, oturum).  KVKK ve cerez mevzuati uyarinca zorunlu
     cerezler icin ONAY gerekmez, BILGILENDIRME yeterlidir.  Bu
     nedenle band "kabul et / reddet" degil "anladim" sunar.
     --------------------------------------------------------------- */
  var CEREZ_ANAHTAR = "goktungu_cerez_bildirim";

  /* KUSUR (v2.12.3 olcumuyle yakalandi): band `position:fixed` oldugu
     icin sayfa akisindan cikar ve alt bilgideki TELIF/SAHIPLIK satirini
     orter (olculen ortusme 20.954 px^2).  Marka gecisinden sonra firma
     kunyesi yalnizca o satirda yer aldigi icin bu, ilk ziyarette
     sahiplik bildiriminin hic okunamamasi demekti.

     Cozum: bandin GERCEK yuksekligi `--cerez-yuk` ozel ozelligine
     yazilir; CSS bu degeri alt bilgiye alt bosluk olarak uygular.
     Sabit deger yetmez -- band metni dile (TR/EN) ve ekran genisligine
     gore 1-3 satir arasi degisir, dolayisiyla yuksekligi de degisir. */
  function cerezYukseklikYaz(band) {
    var y = Math.ceil(band.getBoundingClientRect().height);
    if (y > 0) {
      document.documentElement.style.setProperty("--cerez-yuk", y + "px");
    }
  }

  function cerezBandi() {
    var band = document.getElementById("cerezBandi");
    if (!band) return;
    var goruldu = null;
    try { goruldu = localStorage.getItem(CEREZ_ANAHTAR); } catch (e) { /* yok */ }
    if (goruldu === "1") { band.remove(); return; }
    band.classList.add("acik");
    cerezYukseklikYaz(band);

    /* Dil degisimi ve pencere yeniden boyutlandirmasi bandin satir
       sayisini degistirebilir; yuksekligi izlemek gerekir.  Yoksa TR'de
       olculen bosluk EN'de yetersiz kalir ve kusur geri doner. */
    if (typeof ResizeObserver === "function") {
      new ResizeObserver(function () { cerezYukseklikYaz(band); })
        .observe(band);
    } else {
      window.addEventListener("resize", function () {
        cerezYukseklikYaz(band);
      });
    }

    var kapat = document.getElementById("cerezTamam");
    if (kapat) {
      kapat.addEventListener("click", function () {
        try { localStorage.setItem(CEREZ_ANAHTAR, "1"); } catch (e) { /* yok */ }
        band.classList.remove("acik");
        setTimeout(function () {
          band.remove();
          /* Band DOM'dan silindiginde `:has()` kurali kendiliginden
             dusr; yine de degisken temizlenir ki artik deger kalmasin. */
          document.documentElement.style.removeProperty("--cerez-yuk");
        }, 300);
      });
    }
  }
  cerezBandi();
})();

/* =================================================================
   Fiyatlandirma - aylik / yillik donem gecisi
   -----------------------------------------------------------------
   Sozlesme (index.html):
     .fiy-secici [data-donem="aylik|yillik"]  -> secici dugmeler
     [data-fiyat][data-aylik][data-yillik]    -> tutar ogesi
     [data-donem-etiket]                      -> /ay | /yil etiketi

   Dil bagi: dil.js satir 412'de `dilDegisti` olayi yayinlanir ve
   uygula() TUM data-i18n ogelerini sozlukten yeniden yazar.  Donem
   etiketi de data-i18n tasidigi icin dil degisiminde "/ay" kaynak
   metnine doner.  Bu nedenle olay dinlenip secili donem YENIDEN
   uygulanir; aksi halde yillik seciliyken dil degistirince etiket
   sessizce "/ay" olur (tutar 48 kalir -> tutarsiz gosterim).
   ================================================================= */
(function () {
  "use strict";

  var DONEM_ANAHTAR = "goktungu_fiyat_donem";
  var donem = "aylik";

  function sozlukten(anahtar, yedek) {
    // EN sozlugu yalniz Ingilizcede gecerlidir; TR'de HTML kaynagi kalir.
    var s = window.goktunguSozluk;
    if (window.goktunguDil === "en" && s && s[anahtar]) return s[anahtar];
    return yedek;
  }

  function uygula(yeni) {
    donem = yeni === "yillik" ? "yillik" : "aylik";

    // Tutarlar
    document.querySelectorAll("[data-fiyat]").forEach(function (el) {
      var v = el.getAttribute(donem === "yillik" ? "data-yillik" : "data-aylik");
      if (v != null) el.textContent = v;
    });

    // Donem etiketleri (/ay | /yil)
    var etiket = donem === "yillik"
      ? sozlukten("fiy.yilBasi", "/y\u0131l")
      : sozlukten("fiy.ayBasi", "/ay");
    document.querySelectorAll("[data-donem-etiket]").forEach(function (el) {
      el.textContent = etiket;
    });

    // Secici dugme durumu
    document.querySelectorAll(".fiy-secici [data-donem]").forEach(function (b) {
      var etkin = b.getAttribute("data-donem") === donem;
      b.classList.toggle("etkin", etkin);
      b.setAttribute("aria-selected", etkin ? "true" : "false");
    });

    // Yillik indirim bilgisi
    var ind = document.getElementById("fiyIndirim");
    if (ind) ind.classList.toggle("acik", donem === "yillik");

    try { localStorage.setItem(DONEM_ANAHTAR, donem); } catch (e) { /* yok */ }
  }


  /* === CANLI FIYAT + PARA BIRIMI (gelir modeli v2) === */

  var PARA_ANAHTAR = "goktungu_fiyat_para";
  var para = "TRY";
  var KATALOG = null;          // /api/genel/fiyatlar yaniti
  var SIMGE = { TRY: "\u20BA", USD: "$" };

  function biciml(sayi) {
    // 990 -> "990", 16900 -> "16.900", 9504 -> "9.504"
    var n = Number(sayi);
    if (!isFinite(n)) return String(sayi);
    if (Math.abs(n - Math.round(n)) < 0.005) n = Math.round(n);
    var p = String(n).split(".");
    p[0] = p[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return p.join(",");
  }

  function paraUygula(yeni) {
    para = yeni === "USD" ? "USD" : "TRY";
    document.querySelectorAll("[data-para-simge]").forEach(function (el) {
      el.textContent = SIMGE[para];
    });
    document.querySelectorAll(".fiy-para-secici [data-para]")
      .forEach(function (b) {
        var etkin = b.getAttribute("data-para") === para;
        b.classList.toggle("etkin", etkin);
        b.setAttribute("aria-selected", etkin ? "true" : "false");
      });
    // Yabanci kart uyarisi yalniz USD'de gorunur (iyzico kisiti)
    var not = document.getElementById("fiyParaNot");
    if (not) not.classList.toggle("acik", para === "USD");
    katalogUygula();
    try { localStorage.setItem(PARA_ANAHTAR, para); } catch (e) { /* yok */ }
  }

  function katalogUygula() {
    if (!KATALOG) { uygula(donem); return; }
    var eslem = {};
    (KATALOG.kalemler || KATALOG.paketler || []).forEach(function (k) {
      eslem[k.paket] = k;
    });
    var ek = para === "USD" ? "usd" : "try";
    document.querySelectorAll("[data-paket]").forEach(function (kart) {
      var k = eslem[kart.getAttribute("data-paket")];
      if (!k) return;
      var ay = k["aylik_" + ek];
      var yil = k["yillik_" + ek];
      kart.querySelectorAll("[data-fiyat]").forEach(function (el) {
        if (ay != null) el.setAttribute("data-aylik", biciml(ay));
        if (yil != null) el.setAttribute("data-yillik", biciml(yil));
      });
      /* YILLIK AYLIK KARSILIK
         Donem secicisinden BAGIMSIZ: yillik toplam / 12. Bu satir
         musteriye "%20 indirimle aylik ne odersin" bilgisini verir.
         `data-fiyat` KULLANILMAZ -- kullanilirsa donem secicisi bu
         satiri da degistirir ve indirim vaadi ekranda kaybolur. */
      if (yil != null) {
        kart.querySelectorAll("[data-yillik-ayl]").forEach(function (el) {
          el.textContent = biciml(yil / 12);
        });
      }
      kart.querySelectorAll("[data-fiyat-tek]").forEach(function (el) {
        var kk = eslem[el.getAttribute("data-fiyat-tek")];
        var t = kk ? kk["tek_" + ek] : null;
        if (t != null) el.textContent = biciml(t);
      });
    });
    document.querySelectorAll(".fiy-sku-satir[data-paket]")
      .forEach(function (satir) {
        var k = eslem[satir.getAttribute("data-paket")];
        if (!k) return;
        var t = k["tek_" + ek];
        var el = satir.querySelector(".fiy-sku-tutar");
        if (el && t != null) el.textContent = SIMGE[para] + biciml(t);
      });
    uygula(donem);   // tutarlari yeniden yaz
  }

  function katalogCek() {
    /* Uc erisilemezse HTML'deki deger YEDEK olarak kalir; sayfa bos
       gorunmez. Bu yuzden hata konsola yazilip yutulur. */
    if (!window.fetch) return;
    fetch("/api/genel/fiyatlar", { credentials: "same-origin" })
      .then(function (y) { return y.ok ? y.json() : null; })
      .then(function (d) {
        if (!d) return;
        KATALOG = d;
        if (d.yillik_indirim != null) {
          var ind = document.getElementById("fiyIndirim");
          if (ind) {
            var yuzde = Math.round(Number(d.yillik_indirim) * 100);
            if (yuzde > 0 && /%\s*\d+/.test(ind.textContent)) {
              ind.textContent = ind.textContent
                .replace(/%\s*\d+/, "%" + yuzde);
            }
          }
        }
        katalogUygula();
      })
      .catch(function (e) {
        if (window.console) console.warn("[fiyat] katalog okunamadi", e);
      });
  }

  function paraBagla() {
    /* Tuzak: donem secicinin querySelectorAll'i [data-para] dugmelerini
       KAPSAMAZ; ayri baglanmalidir. */
    var p = document.querySelector(".fiy-para-secici");
    if (!p) return;
    p.querySelectorAll("[data-para]").forEach(function (b) {
      b.addEventListener("click", function () {
        paraUygula(b.getAttribute("data-para"));
      });
    });
    var kayitli = null;
    try { kayitli = localStorage.getItem(PARA_ANAHTAR); } catch (e) { /* yok */ }
    paraUygula(kayitli === "USD" ? "USD" : "TRY");
  }

  function baglan() {
    /* KRITIK: ":not(.fiy-para-secici)" ZORUNLU. Para birimi secici
       de ".fiy-secici" sinifini tasir; ciplak querySelector ILK
       eslesen ogeyi dondurur ve kartlarin sirasi degisirse donem
       dugmeleri SESSIZCE olur. */
    var secici = document.querySelector(".fiy-secici:not(.fiy-para-secici)");
    if (!secici) return;   // fiyat bolumu olmayan sayfada sessiz cik

    secici.querySelectorAll("[data-donem]").forEach(function (b) {
      b.addEventListener("click", function () {
        uygula(b.getAttribute("data-donem"));
      });
    });

    var kayitli = null;
    try { kayitli = localStorage.getItem(DONEM_ANAHTAR); } catch (e) { /* yok */ }
    uygula(kayitli === "yillik" ? "yillik" : "aylik");

    // Dil degisiminde secili donemi yeniden uygula (yukaridaki gerekce)
    paraBagla();
    katalogCek();
    document.addEventListener("dilDegisti", function () {
      uygula(donem);
      var n = document.getElementById("fiyParaNot");
      if (n) n.classList.toggle("acik", para === "USD");
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", baglan);
  } else {
    baglan();
  }
})();
