/* ============================================================
   GOKTUNGU IKON DIZGESI
   ------------------------------------------------------------
   NEDEN VAR:
   Yetenek kartlarinda ikon yerine Unicode geometrik karakterler
   kullaniliyordu:  &#9678; &#9650; &#9635; &#9707; &#9707; &#9200;
   Uc ciddi kusur vardi:
     1) k4 ve k5 BIREBIR AYNI karakteri kullaniyordu (&#9707;)
     2) bu karakterler yazi tipine gore farkli cizilir; bazi
        platformlarda (ozellikle Windows'ta Chakra Petch ile)
        hic cizilmez veya tofu (kutu) olarak gorunur
     3) hicbiri anlatilan yetenekle gorsel iliski kurmuyordu
   Cozum: cizgi tabanli, tek renkli (currentColor) SVG dizgesi.

   TASARIM SOZLESMESI:
   - viewBox 0 0 24 24, stroke tabanli, dolgu YOK (fill=none)
   - stroke="currentColor" -- renk CSS'ten gelir, tema uyumlu
   - stroke-width 1.6, linecap/linejoin "round"
   - piksel izgarasina oturmasi icin yarim piksel kacinilir

   KULLANIM:
     <span class="gz-ikon" data-ikon="radar"></span>
   Betik yuklendiginde tum [data-ikon] ogeleri doldurur.
   `window.goktunguIkon(ad)` ile de tek ikonun SVG metni alinir.
   ============================================================ */
(function () {
  'use strict';

  var IKON = {};

  /* --- Radar: tarama huzmeli menzil yaylari ---
     ONCEKI KUSUR: yaylar `a9 9 0 0 1` idi, merkez 12,12 -- yaricap 9
     ile cizim 24x24 kutunun disina tasip kirpiliyordu.  Sonuc: iki
     ucu kapanmis bir "damla" gorunuyor, radar supurmesi okunmuyordu.
     IKINCI DENEME de kusurluydu: iki menzil YAYI (r=7.4/3.8) 24px
     kutuda birbirine fazla yakindi, ust uste binip "tarali yarim
     daire" gibi gorunuyordu ve huzme yaylarin icinde kayboluyordu.
     SIMDI: iki es merkezli TAM DAIRE (r=8.6 ve r=4.2 -- aralik 4.4px,
     acikca ayrik) + merkezden cevreye uzanan iki kenarli tarama
     kamasi + dolu mevzi noktasi. */
  IKON.radar =
    /* tam menzil dairesi -- kutu icinde, r=8.6 */
    '<circle cx="12" cy="12" r="8.6"/>' +
    /* ic menzil halkasi -- yeterince ayrik (r=4.2) */
    '<circle cx="12" cy="12" r="4.2"/>' +
    /* tarama huzmesi: merkezden cevreye iki kenar (kama) */
    '<path d="M12 12 12 3.4"/>' +
    '<path d="M12 12 19.4 7.7"/>' +
    /* mevzi */
    '<circle cx="12" cy="12" r="1.15" fill="currentColor" stroke="none"/>';

  /* --- IHA: multikopter, dort kol ve pervane ---
     ONCEKI KUSUR: pervaneler YATAY CIZGI olarak cizilmisti; dort kol
     ile birlesince multikopter degil bir yildiz/asterisk izlenimi
     veriyordu.  Multikopterin ayirt edici isareti pervane
     DAIRELERIDIR. */
  IKON.iha =
    '<rect x="9.7" y="9.7" width="4.6" height="4.6" rx="1"/>' +
    '<path d="M9.7 9.7 7.3 7.3M14.3 9.7 16.7 7.3M9.7 14.3 7.3 16.7M14.3 14.3 16.7 16.7"/>' +
    '<circle cx="5.6" cy="5.6" r="2.2"/>' +
    '<circle cx="18.4" cy="5.6" r="2.2"/>' +
    '<circle cx="5.6" cy="18.4" r="2.2"/>' +
    '<circle cx="18.4" cy="18.4" r="2.2"/>';

  /* --- Yapay zeka: hedef cercevesi + isaret noktalari --- */
  IKON.yapayZeka =
    '<path d="M4 8.6V5.6A1.6 1.6 0 0 1 5.6 4h3"/>' +
    '<path d="M15.4 4h3A1.6 1.6 0 0 1 20 5.6v3"/>' +
    '<path d="M20 15.4v3a1.6 1.6 0 0 1-1.6 1.6h-3"/>' +
    '<path d="M8.6 20h-3A1.6 1.6 0 0 1 4 18.4v-3"/>' +
    '<circle cx="12" cy="12" r="2.4"/>' +
    '<path d="M12 7.2v2.4M12 14.4v2.4M7.2 12h2.4M14.4 12h2.4"/>';

  /* --- Cok kiracili yapi: katmanli kurum blogu --- */
  IKON.kurum =
    '<path d="M4 20h16"/>' +
    '<path d="M6 20V9.5l6-3.5 6 3.5V20"/>' +
    '<path d="M10 20v-4.2h4V20"/>' +
    '<path d="M9.2 11.8h1.4M13.4 11.8h1.4"/>';

  /* --- Pilot kaydi: kimlik karti --- */
  IKON.pilot =
    '<rect x="3.2" y="5.2" width="17.6" height="13.6" rx="1.8"/>' +
    '<circle cx="8.8" cy="10.6" r="1.9"/>' +
    '<path d="M5.7 15.6a3.2 3.2 0 0 1 6.2 0"/>' +
    '<path d="M14.4 9.8h3.8M14.4 12.6h3.8M14.4 15.2h2.4"/>';

  /* --- Gecmis: zaman cizgisi + oynatma --- */
  IKON.gecmis =
    '<circle cx="12" cy="12" r="8.2"/>' +
    '<path d="M12 7.4V12l3.4 2"/>' +
    '<path d="M3.9 9.4 6.4 8"/>';

  /* --- Ek ikonlar (ekran goruntusu vitrini icin) --- */
  IKON.baglanti =
    '<path d="M9.6 14.4 6.8 17.2a3.4 3.4 0 0 1-4.8-4.8l2.8-2.8"/>' +
    '<path d="M14.4 9.6l2.8-2.8a3.4 3.4 0 0 1 4.8 4.8l-2.8 2.8"/>' +
    '<path d="M9.2 14.8l5.6-5.6"/>';

  IKON.kamera =
    '<path d="M3.4 7.6h9.2a1.4 1.4 0 0 1 1.4 1.4v6a1.4 1.4 0 0 1-1.4 1.4H3.4A1.4 1.4 0 0 1 2 15V9a1.4 1.4 0 0 1 1.4-1.4z"/>' +
    '<path d="M14 11.2l5.4-2.8a.7.7 0 0 1 1 .62v5.96a.7.7 0 0 1-1 .62L14 12.8z"/>';

  IKON.hedef =
    '<circle cx="12" cy="12" r="7.6"/>' +
    '<circle cx="12" cy="12" r="3.6"/>' +
    '<path d="M12 1.6v3.2M12 19.2v3.2M1.6 12h3.2M19.2 12h3.2"/>';

  IKON.harita =
    '<path d="M9.2 4.4 3.6 6.6v13l5.6-2.2 5.6 2.2 5.6-2.2v-13l-5.6 2.2z"/>' +
    '<path d="M9.2 4.4v13M14.8 6.6v13"/>';

  IKON.kalkan =
    '<path d="M12 3.2l7 2.6v5.4c0 4.3-2.9 7.6-7 9.6-4.1-2-7-5.3-7-9.6V5.8z"/>' +
    '<path d="M9 12.2l2.2 2.2 4-4.2"/>';

  IKON.sunucu =
    '<rect x="3.4" y="4.2" width="17.2" height="6" rx="1.3"/>' +
    '<rect x="3.4" y="13.8" width="17.2" height="6" rx="1.3"/>' +
    '<path d="M7 7.2h.02M7 16.8h.02"/>' +
    '<path d="M11 7.2h6M11 16.8h6"/>';

  /* Ad esleri: HTML'de okunabilir adlar kullanilabilsin */
  var ES = {
    'ai': 'yapayZeka',
    'drone': 'iha',
    'dron': 'iha',
    'sirket': 'kurum',
    'tarih': 'gecmis',
    'guvenlik': 'kalkan'
  };

  function svg(ad) {
    var k = ES[ad] || ad;
    var g = IKON[k];
    if (!g) return '';
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" ' +
      'aria-hidden="true" focusable="false">' + g + '</svg>';
  }

  function doldur(kok) {
    var liste = (kok || document).querySelectorAll('[data-ikon]');
    for (var i = 0; i < liste.length; i++) {
      var o = liste[i];
      // Iki kez doldurmayi engelle (dil degisimi DOM'u yenilemez ama
      // ileride bir bilesen yenilerse ikon cogalmasin)
      if (o.getAttribute('data-ikon-hazir') === '1') continue;
      var m = svg(o.getAttribute('data-ikon'));
      if (!m) continue;
      o.innerHTML = m;
      o.setAttribute('data-ikon-hazir', '1');
      // Ikon dekoratif: ekran okuyucu atlamali, baslik metni zaten var
      if (!o.hasAttribute('aria-hidden')) {
        o.setAttribute('aria-hidden', 'true');
      }
    }
  }

  window.goktunguIkon = svg;
  window.goktunguIkonDoldur = doldur;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { doldur(); });
  } else {
    doldur();
  }
})();
