/* =================================================================
   GOKTUNGU -- Yardim Merkezi betigi (M21)
   Gokkubbe Teknoloji Anonim Sirketi
   -----------------------------------------------------------------
   Sorumluluklar:
     1. Sol agac: dal ac/kapa, durum saklama (localStorage)
     2. Cipa tabanli bolum yonlendirme (#anahtar)
     3. Istemci tarafi arama (baslik + govde metni)
     4. Sonraki/onceki gezinme
     5. Mobil agac perdesi
     6. TR/EN gecisi (window.YARDIM_EN sozlugu)
   Icerik HTML icinde tasinir -- JS kapali olsa da okunabilir olmali.
   Tema `/js/tema.js` tarafindan yonetilir, burada TEKRARLANMAZ.
   ================================================================= */
(function () {
  "use strict";

  var AGAC_ANAHTAR = "goktungu_yardim_agac";
  var DIL_ANAHTAR = "goktungu_landing_dil";   /* yasal.js ile AYNI */

  var yan, perde, agac, arama, aramaKutu, aramaSonuc, icerik;
  var bolumler = [];      /* [{anahtar, oge, baslik, metin, yol}] */
  var ozgun = null;       /* TR kaynak metinler */
  var suanki = "tr";

  /* ---------------------------------------------------------------
     Yardimcilar
     --------------------------------------------------------------- */
  function q(s, k) { return (k || document).querySelector(s); }
  function qa(s, k) { return Array.prototype.slice.call((k || document).querySelectorAll(s)); }

  function sakla(a, d) {
    try { localStorage.setItem(a, d); } catch (e) { /* gizli kip */ }
  }
  function oku(a) {
    try { return localStorage.getItem(a); } catch (e) { return null; }
  }

  /* ---------------------------------------------------------------
     1. Bolum dizini
     --------------------------------------------------------------- */
  function dizinKur() {
    bolumler = qa(".yrd-bolum").map(function (o) {
      var b = q("h1", o);
      var yolOge = q(".yrd-yol", o);
      return {
        anahtar: o.id.replace(/^b-/, ""),
        oge: o,
        baslik: b ? b.textContent.trim() : o.id,
        yol: yolOge ? yolOge.textContent.replace(/\s+/g, " ").trim() : "",
        metin: (o.textContent || "").toLowerCase()
      };
    });
  }

  /* ---------------------------------------------------------------
     2. Bolum gosterme
     --------------------------------------------------------------- */
  function bolumGoster(anahtar, kaydir) {
    var bulundu = null;
    bolumler.forEach(function (b) {
      var e = (b.anahtar === anahtar);
      b.oge.classList.toggle("etkin", e);
      if (e) bulundu = b;
    });
    if (!bulundu && bolumler.length) {
      bolumler[0].oge.classList.add("etkin");
      bulundu = bolumler[0];
    }
    /* agac isaretleme */
    qa(".yrd-agac a").forEach(function (a) {
      var e = (a.getAttribute("href") === "#" + anahtar);
      a.classList.toggle("etkin", e);
      if (e) {
        /* ust dallari ac */
        var p = a.parentNode;
        while (p && p !== agac) {
          if (p.classList && p.classList.contains("yrd-dal")) {
            p.classList.add("acik");
          }
          p = p.parentNode;
        }
        durumSakla();
      }
    });
    if (bulundu) {
      gezGuncelle(bulundu);
      document.title = bulundu.baslik + " | GÖKTUNGU Yardım";
    }
    if (kaydir !== false) {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
    yanKapa();
  }

  /* ---------------------------------------------------------------
     3. Sonraki / onceki gezinme
     --------------------------------------------------------------- */
  function gezGuncelle(b) {
    var kap = q(".yrd-gez", b.oge);
    if (!kap) return;
    var i = bolumler.indexOf(b);
    var onc = i > 0 ? bolumler[i - 1] : null;
    var son = i < bolumler.length - 1 ? bolumler[i + 1] : null;
    var h = "";
    if (onc) {
      h += '<a href="#' + onc.anahtar + '"><span class="yrd-ge">'
        + (suanki === "en" ? "Previous" : "Önceki") + '</span>'
        + '<span class="yrd-gb">' + onc.baslik + "</span></a>";
    }
    if (son) {
      h += '<a class="sag" href="#' + son.anahtar + '"><span class="yrd-ge">'
        + (suanki === "en" ? "Next" : "Sonraki") + '</span>'
        + '<span class="yrd-gb">' + son.baslik + "</span></a>";
    }
    kap.innerHTML = h;
  }

  /* ---------------------------------------------------------------
     4. Agac durumu
     --------------------------------------------------------------- */
  function durumSakla() {
    var acik = qa(".yrd-dal.acik", agac).map(function (d) {
      return d.getAttribute("data-dal");
    }).filter(Boolean);
    sakla(AGAC_ANAHTAR, JSON.stringify(acik));
  }
  function durumYukle() {
    var d = oku(AGAC_ANAHTAR);
    if (!d) return;
    var liste;
    try { liste = JSON.parse(d); } catch (e) { return; }
    if (!Array.isArray(liste)) return;
    liste.forEach(function (ad) {
      var o = q('.yrd-dal[data-dal="' + ad + '"]', agac);
      if (o) o.classList.add("acik");
    });
  }

  /* ===================================================================
     FAZ18-AGAC  —  aria-expanded esitleme
     -------------------------------------------------------------------
     Agac ac/kapa durumu artik (+/-) gostergesi ile anlatiliyor. Ekran
     okuyucu ve klavye kullanicisi icin durumun `aria-expanded` uzerinde
     de yazili olmasi gerekiyor; dal her acilip kapandiginda ve sayfa
     yuklenirken (kayitli durum geri okunduktan sonra) esitlenir.
     =================================================================== */
  function ariaEsitle() {
    qa(".yrd-dal", agac).forEach(function (d) {
      var b = q(".yrd-bas", d);
      if (b) b.setAttribute("aria-expanded",
                            d.classList.contains("acik") ? "true" : "false");
    });
  }

  /* ---------------------------------------------------------------
     5. Arama
     --------------------------------------------------------------- */
  function aramaUygula(s) {
    s = (s || "").trim().toLowerCase();
    arama.classList.toggle("dolu", !!s);
    if (!s) {
      qa(".yrd-agac li").forEach(function (o) { o.classList.remove("yrd-gizli"); });
      qa(".yrd-agac a").forEach(function (a) {
        if (a.dataset.ozgun) { a.textContent = a.dataset.ozgun; }
      });
      aramaSonuc.textContent = "";
      durumYukle();
      ariaEsitle();   /* FAZ18-AGAC */
      return;
    }
    var esles = 0;
    /* once tum baglantilari gizle */
    qa(".yrd-agac a").forEach(function (a) {
      var li = a.parentNode;
      if (!a.dataset.ozgun) a.dataset.ozgun = a.textContent;
      var ad = a.dataset.ozgun;
      var anahtar = (a.getAttribute("href") || "").replace("#", "");
      var b = null;
      for (var i = 0; i < bolumler.length; i++) {
        if (bolumler[i].anahtar === anahtar) { b = bolumler[i]; break; }
      }
      var basEs = ad.toLowerCase().indexOf(s) >= 0;
      var govEs = b && b.metin.indexOf(s) >= 0;
      if (basEs || govEs) {
        li.classList.remove("yrd-gizli");
        esles++;
        if (basEs) {
          var k = ad.toLowerCase().indexOf(s);
          a.innerHTML = kacir(ad.slice(0, k)) + "<mark>"
            + kacir(ad.slice(k, k + s.length)) + "</mark>"
            + kacir(ad.slice(k + s.length));
        } else {
          a.textContent = ad;
        }
        /* ust dallari gorunur kil ve ac */
        var p = li.parentNode;
        while (p && p !== agac) {
          if (p.tagName === "LI") p.classList.remove("yrd-gizli");
          if (p.classList && p.classList.contains("yrd-dal")) p.classList.add("acik");
          p = p.parentNode;
        }
      } else {
        li.classList.add("yrd-gizli");
        a.textContent = ad;
      }
    });
    /* icinde gorunur baglanti kalmayan dallari gizle */
    qa(".yrd-dal", agac).forEach(function (d) {
      var gor = qa("a", d).filter(function (a) {
        return !a.parentNode.classList.contains("yrd-gizli");
      });
      d.classList.toggle("yrd-gizli", gor.length === 0);
    });
    aramaSonuc.textContent = esles
      ? (suanki === "en" ? esles + " topic found" : esles + " başlık bulundu")
      : (suanki === "en" ? "No results" : "Sonuç yok");
  }

  function kacir(m) {
    return String(m).replace(/[&<>"']/g, function (k) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[k];
    });
  }

  /* ---------------------------------------------------------------
     6. Mobil yan panel
     --------------------------------------------------------------- */
  /* FAZ16-DESTEK-MENU  aria durumu duğmeye yazilir; ekran okuyucu
     panelin acik mi kapali mi oldugunu bilmeli. */
  function ariaYaz(acikMi) {
    var d = document.getElementById("icindekilerDg");
    if (d) d.setAttribute("aria-expanded", acikMi ? "true" : "false");
  }
  function yanAc() {
    yan.classList.add("acik");
    if (perde) perde.classList.add("acik");
    ariaYaz(true);
  }
  function yanKapa() {
    yan.classList.remove("acik");
    if (perde) perde.classList.remove("acik");
    ariaYaz(false);
  }

  /* ---------------------------------------------------------------
     7. TR/EN gecisi (yasal.js ile AYNI sozlesme)
     --------------------------------------------------------------- */
  function ogeler() { return document.querySelectorAll("[data-i18n]"); }

  function ozgunSakla() {
    if (ozgun) return;
    ozgun = {};
    Array.prototype.forEach.call(ogeler(), function (o) {
      var a = o.getAttribute("data-i18n");
      ozgun[a] = o.hasAttribute("data-i18n-html") ? o.innerHTML : o.textContent;
    });
    qa("[data-i18n-attr]").forEach(function (o) {
      var p = (o.getAttribute("data-i18n-attr") || "").split(":");
      if (p.length !== 2) return;
      ozgun["@" + p[1]] = o.getAttribute(p[0]);
    });
  }

  function dilUygula(d) {
    ozgunSakla();
    var s = (d === "en") ? (window.YARDIM_EN || null) : null;
    suanki = d;
    Array.prototype.forEach.call(ogeler(), function (o) {
      var a = o.getAttribute("data-i18n");
      var v = s ? s[a] : ozgun[a];
      if (v === undefined || v === null) v = ozgun[a];
      if (v === undefined) return;
      if (o.hasAttribute("data-i18n-html")) { o.innerHTML = v; }
      else { o.textContent = v; }
    });
    qa("[data-i18n-attr]").forEach(function (o) {
      var p = (o.getAttribute("data-i18n-attr") || "").split(":");
      if (p.length !== 2) return;
      var v = s ? s["@" + p[1]] : ozgun["@" + p[1]];
      if (v === undefined || v === null) v = ozgun["@" + p[1]];
      if (v !== undefined) o.setAttribute(p[0], v);
    });
    document.documentElement.setAttribute("lang", d);
    qa("[data-dil]").forEach(function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-dil") === d ? "true" : "false");
    });
    sakla(DIL_ANAHTAR, d);
    /* dizin metinleri dil degisince yenilenmeli */
    dizinKur();
    var mev = (location.hash || "").replace("#", "");
    bolumGoster(mev || (bolumler[0] && bolumler[0].anahtar), false);
    if (aramaKutu.value) aramaUygula(aramaKutu.value);
  }

  /* ---------------------------------------------------------------
     Kurulum
     --------------------------------------------------------------- */
  function kur() {
    yan = q(".yrd-yan");
    perde = q(".yrd-perde");
    agac = q(".yrd-agac");
    arama = q(".yrd-arama");
    aramaKutu = q(".yrd-arama input");
    aramaSonuc = q(".yrd-arama-sonuc");
    icerik = q(".yrd-icerik");
    if (!yan || !agac || !icerik) return;

    dizinKur();

    /* dal ac/kapa */
    qa(".yrd-dal > .yrd-bas", agac).forEach(function (b) {
      b.addEventListener("click", function () {
        b.parentNode.classList.toggle("acik");
        durumSakla();
        ariaEsitle();   /* FAZ18-AGAC */
      });
    });

    /* cipa yonlendirme */
    window.addEventListener("hashchange", function () {
      bolumGoster((location.hash || "").replace("#", ""));
    });

    /* arama */
    if (aramaKutu) {
      var zaman = null;
      aramaKutu.addEventListener("input", function () {
        clearTimeout(zaman);
        zaman = setTimeout(function () { aramaUygula(aramaKutu.value); }, 130);
      });
      aramaKutu.addEventListener("keydown", function (e) {
        if (e.key === "Escape") { aramaKutu.value = ""; aramaUygula(""); }
      });
    }
    var tmz = q(".yrd-temizle", arama);
    if (tmz) {
      tmz.addEventListener("click", function () {
        aramaKutu.value = ""; aramaUygula(""); aramaKutu.focus();
      });
    }

    /* FAZ16-DESTEK-MENU
       Icindekiler duğmesi ust cubukta ve AC/KAPA yapiyor.  Onceki
       surumde sol alttaki kirmizi yuvarlak duğme YALNIZ ACIYORDU
       (`click -> yanAc`); kapatmak icin perdeye tiklamak gerekiyordu ve
       `aria-expanded` hic yaziliyordu.  Davranis artik `#anaMenu`
       sozlesmesiyle ayni: toggle, aria durumu, Escape, secince kapanma. */
    var dg = document.getElementById("icindekilerDg");
    if (dg) {
      dg.addEventListener("click", function () {
        if (yan.classList.contains("acik")) yanKapa();
        else yanAc();
      });
    }
    if (perde) perde.addEventListener("click", yanKapa);
    /* Escape: acik panel klavyeyle kapanmali (WCAG 2.1.2 tuzak yok). */
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && yan.classList.contains("acik")) yanKapa();
    });
    /* Agactan baslik secilince panel kapanir -- yalniz duğme gorunurken,
       yani mobil duzende.  Masaustunde panel sabit durur, kapatilmaz. */
    agac.addEventListener("click", function (e) {
      var t = e.target;
      while (t && t !== agac && t.tagName !== "A") t = t.parentNode;
      if (t && t.tagName === "A" && yan.classList.contains("acik")) yanKapa();
    });

    /* dil dugmeleri */
    qa("[data-dil]").forEach(function (b) {
      b.addEventListener("click", function () {
        dilUygula(b.getAttribute("data-dil"));
      });
    });

    /* yil */
    var y = q("#yil");
    if (y) y.textContent = String(new Date().getFullYear());

    /* agac durumu + ilk bolum */
    durumYukle();
    ariaEsitle();   /* FAZ18-AGAC */
    var d = oku(DIL_ANAHTAR);
    if (d === "en" && window.YARDIM_EN) {
      dilUygula("en");
    } else {
      bolumGoster((location.hash || "").replace("#", ""), false);
    }

    /* klavye: / arama odagi */
    document.addEventListener("keydown", function (e) {
      if (e.key === "/" && document.activeElement !== aramaKutu) {
        e.preventDefault();
        if (aramaKutu) aramaKutu.focus();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", kur);
  } else {
    kur();
  }
})();

/* ===================================================================
   FAZ17-DESTEK-BAGIMSIZ -- olu hamburger korumasi
   ===================================================================
   Destek sitesinden `#menuAc` + `#anaMenu` kaldirildi.  Onbellekten
   eski HTML gelen istemcilerde dugme hala DOM'da olabilir ve dinleyicisi
   (`js/sayfa.js`) Destek'te yuklenmedigi icin OLU kalir -- kullanici
   basar, hicbir sey olmaz.

   Bu koruma, eski isaretleme kalintisi bulursa dugmeyi gizler ve
   islevini `#icindekilerDg`'ye baglar.  Yeni HTML'de dugme hic
   olmadigindan kod sessizce atlanir.
   ------------------------------------------------------------------- */
(function () {
  function olusuTemizle() {
    var olu = document.getElementById("menuAc");
    var nav = document.getElementById("anaMenu");
    if (olu) olu.style.display = "none";
    if (nav) nav.style.display = "none";
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", olusuTemizle);
  } else {
    olusuTemizle();
  }
})();
