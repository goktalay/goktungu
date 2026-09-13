/* ============================================================
   GÖKTUNGU — Amblem ve yükleme perdesi          FAZ15-LOGOANIM
   ------------------------------------------------------------
   İki iş yapar:

   1. `.marka` içindeki raster logonun yanına SVG amblemi yerleştirir
      ve rasterdan amblem bölgesini kırpar (`clip-path`), böylece
      amblem iki kez görünmez.
   2. Sayfa yüklenirken kısa bir perde gösterir.

   PERDE EMNİYETİ — komuta arayüzünde asılı bir perde operasyonel
   risktir.  Bu yüzden perde HTML'de YOKTUR, bu betik oluşturur: betik
   yüklenmezse perde hiç görünmez.  Ayrıca en fazla `AZAMI_SURE`
   yaşar; `load` olayı hiç gelmese bile kendini kaldırır.
   ============================================================ */
(function () {
  "use strict";

  var AMBLEM_YOL = "/img/goktungu_amblem.svg";
  var AZAMI_SURE = 2500;   /* perde en fazla bu kadar yaşar (ms) */
  var ASGARI_SURE = 420;   /* göz kırpması gibi görünmemesi için */

  /* ---------- 1) amblemi markaya yerleştir ---------- */

  /* Rasterda amblem sol %24'te duruyor (ölçüldü: 125/522 opak genişlik).
     SVG amblem eklendiğinde rasterın o bölgesi kırpılır, yoksa amblem
     iki kez görünür. */
  /* FAZ15-AMBLEM-DUZELT  Ölçülen değer: amblem rasterda
     18..142 px, yazı ~152 px'de başlıyor; 152/550 = %27.6. */
  var KIRP_ORAN = 0.276;   /* FAZ15-AMBLEM-HIZA  kirpma orani */
  /* FAZ16-PANEL-AMBLEM  metin markasinda amblem/yazi orani.
     14px yazi -> 28px amblem (olculen: 48px ust seritte
     ustte/altta 10px bosluk kalir). */
  var METIN_ORAN = 2.0;
  var RASTER_KIRP = "inset(0 0 0 " + (KIRP_ORAN * 100).toFixed(1) + "%)";

  function amblemKur() {
    var markalar = document.querySelectorAll(".marka, .ft-marka");
    for (var i = 0; i < markalar.length; i++) {
      var m = markalar[i];

      /* FAZ15-AMBLEM-DUZELT
         Rasterlar amblem EKLENMEDEN önce toplanır.  Önceki sürümde
         amblem `insertBefore` ile eklendikten sonra `querySelectorAll`
         çalıştığı için amblem de `<img>` listesine giriyordu; ölçülen
         sonuç hiçbirine kırpma yazılmaması oldu. */
      var rasterlar = [];
      var hepsi = m.querySelectorAll("img");
      for (var j = 0; j < hepsi.length; j++) {
        var e = hepsi[j];
        /* Amblemin kendisi asla kırpılmaz. */
        if (e.parentNode && e.parentNode.classList &&
            e.parentNode.classList.contains("gt-amblem")) continue;
        rasterlar.push(e);
      }
      /* FAZ16-PANEL-AMBLEM
         Raster yoksa amblem TEK BASINA eklenir.  Onceki surumde burada
         `continue` vardi ve yonetim/kurumsal panellerin metin markasina
         ("GOKTUNGU MUSTERI") amblem HIC eklenmiyordu -- betik `.marka`
         icinde var olan bir <img> varsayiyordu.  Olculen sonuc: iki
         panelde gorsel marka yok.
         Raster yoksa kirpma ve negatif kenar boslugu da yazilmaz;
         kirpilacak sey yok. */
      var rastersiz = !rasterlar.length;

      /* Yükseklik rasterdan alınır; amblem yazıyla aynı boyda durur.
         Gizli tema varyantı 0 döner, o yüzden en büyüğü alınır. */
      var y = 0;
      if (rastersiz) {
        /* FAZ16-PANEL-AMBLEM
           Metin markasinda amblem yuksekligi YAZI BUYUKLUGUNDEN
           turetilir.  Sabit deger yazilmaz: panel yazi tipi buyurse
           amblem de buyumeli.  Olculen: panel `.marka` font-size 14px,
           ust serit 48px -> 28px amblem, ustte/altta 10px bosluk. */
        var yb = parseFloat(getComputedStyle(m).fontSize) || 14;
        y = Math.round(yb * METIN_ORAN);
        /* Ust serit yuksekligini asmasin: 48px seritte en cok 32px. */
        var kap_y = m.parentNode
          ? (m.parentNode.getBoundingClientRect().height || 0) : 0;
        if (kap_y > 0 && y > kap_y - 16) y = Math.round(kap_y - 16);
        if (y < 18) y = 18;
      } else {
        for (var k = 0; k < rasterlar.length; k++) {
          var h = rasterlar[k].getBoundingClientRect().height;
          if (h > y) y = h;
        }
        if (!y) y = parseFloat(getComputedStyle(rasterlar[0]).height) || 36;
      }

      /* Kırpma her çağrıda yazılır: tema değişiminde görünür varyant
         değişir ve yeni varyantın kırpması eksik kalabilir. */
      /* FAZ16-PANEL-AMBLEM  rastersizse kirpilacak sey yok */
      for (var n = 0; rastersiz ? false : n < rasterlar.length; n++) {
        rasterlar[n].style.clipPath = RASTER_KIRP;
        rasterlar[n].style.webkitClipPath = RASTER_KIRP;

        /* FAZ15-AMBLEM-HIZA
           `clip-path` yerleşimi etkilemez: rasterın kutusu kırpılmadan
           önceki tam genişliğini korur, kırpılan bölge ölü alan olarak
           kalır.  Negatif kenar boşluğuyla geri alınır.

           Değer YÜZDE OLARAK VERİLEMEZ: CSS `margin-left` yüzdesi
           kapsayıcı genişliğine göre hesaplanır, öğenin kendi
           genişliğine göre değil.  `.marka` genişliği menü diline göre
           değiştiği için yüzde değer kararsızdı (ölçüldü: yazı amblem
           üzerine 36 px bindi).  Bu yüzden rasterın kendi ölçülen
           genişliğinden piksel hesaplanır. */
        var g = rasterlar[n].offsetWidth;
        if (g > 0) {
          rasterlar[n].style.marginLeft = (-(g * KIRP_ORAN)).toFixed(2) + "px";
        }
      }

      var mevcut = m.querySelector(".gt-amblem");
      if (mevcut) {
        /* Yükseklik değiştiyse güncelle, ikinci amblem ekleme. */
        var im = mevcut.querySelector("img");
        if (im) im.style.height = y + "px";
        continue;
      }

      var kap = document.createElement("span");
      kap.className = "gt-amblem";
      kap.setAttribute("aria-hidden", "true");

      var nesne = document.createElement("img");
      nesne.src = AMBLEM_YOL;
      nesne.alt = "";
      nesne.style.height = y + "px";
      nesne.style.display = "block";
      nesne.style.width = "auto";

      /* SVG `<img>` içinde de 3B dönüşüm alır; ayrı istek, önbelleklenir.
         Satır içi gömme yapılmadı: aynı SVG beş panelde kullanılıyor,
         tek dosya olarak önbelleğe girmesi daha verimli. */
      kap.appendChild(nesne);
      m.insertBefore(kap, m.firstChild);

      /* Amblem eklendi: `gap` küçültülür, yoksa kırpılan rasterın iç
         boşluğuyla üst üste binip ~30 px'e çıkıyor (ölçüldü). */
      /* FAZ16-SINIF-AYRIK
         Iki sinif BIRBIRINI DISLAR.  Onceki surumde `gt-amblemli`
         kosulsuz ekleniyordu; metin markasinda ikisi birlikte olusuyor
         ve dogru bosluk yalniz CSS SIRASI sayesinde kazaniyordu
         (`.gt-amblem-metin` sonra tanimli).  Kurallarin yeri degisirse
         `gap:7px` kazanir ve amblem yaziya yapisir.
           raster VARSA -> gt-amblemli     (kirpilan serit, 7px)
           raster YOKSA -> gt-amblem-metin (yazi markasi, 10px) */
      if (rastersiz) {
        m.classList.add("gt-amblem-metin");
        m.classList.remove("gt-amblemli");
      } else {
        m.classList.add("gt-amblemli");
        m.classList.remove("gt-amblem-metin");
      }
    }
  }

  /* ---------- 2) yükleme perdesi ---------- */

  var perde = null;
  var basla = Date.now();
  var kapandi = false;

  function perdeAc() {
    /* Yalnız ilk yüklemede; sayfa içi gezinmede tekrar gösterilmez. */
    if (perde) return;
    perde = document.createElement("div");
    perde.id = "gtPerde";
    perde.setAttribute("role", "status");
    perde.setAttribute("aria-live", "polite");
    perde.setAttribute("aria-label", "Yükleniyor");
    perde.innerHTML =
      '<div class="gt-perde-ic">' +
        '<span class="gt-amblem" aria-hidden="true">' +
          '<img src="' + AMBLEM_YOL + '" alt="" style="height:64px">' +
        '</span>' +
        '<span class="gt-perde-cizgi" aria-hidden="true"></span>' +
      '</div>';
    (document.body || document.documentElement).appendChild(perde);
  }

  function perdeKapa() {
    if (kapandi || !perde) return;
    kapandi = true;
    var gecen = Date.now() - basla;
    var bekle = gecen < ASGARI_SURE ? ASGARI_SURE - gecen : 0;
    setTimeout(function () {
      perde.classList.add("gt-kapan");
      /* Geçiş bitince DOM'dan tamamen çıkar: görünmez bir katman
         kalmasın. */
      setTimeout(function () {
        if (perde && perde.parentNode) perde.parentNode.removeChild(perde);
        perde = null;
      }, 520);
    }, bekle);
  }

  /* EMNİYET: `load` hiç gelmese bile perde kalkar. */
  setTimeout(perdeKapa, AZAMI_SURE);

  if (document.readyState === "complete") {
    /* Betik geç yüklendiyse perdeyi hiç açma. */
  } else {
    perdeAc();
    window.addEventListener("load", perdeKapa);
  }

  /* Sekme arkaya atılıp geri gelirse `load` kaçabilir. */
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden && document.readyState === "complete") perdeKapa();
  });

  /* ---------- başlat ---------- */
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", amblemKur);
  } else {
    amblemKur();
  }
  /* Görseller sonradan yüklenince yükseklik değişebilir; bir kez daha. */
  window.addEventListener("load", function () { setTimeout(amblemKur, 60); });
})();
