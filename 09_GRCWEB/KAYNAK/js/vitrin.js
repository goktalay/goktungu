/* ============================================================
   ARAYUZ VITRINI  --  sekmeli ekran goruntusu gostericisi
   ------------------------------------------------------------
   Onceki durum: bir buyuk gorsel + bes esit agirlikli kucuk gorsel
   yan yana diziliydi.  Hiyerarsi yoktu, bes gorsel birden yukleniyordu.

   Yeni yapi: solda ikon+baslik+aciklama tasiyan sekme listesi,
   sagda tek buyuk gorsel.  Bir defada tek kare gorunur.

   ILERLEYICI ZENGINLESTIRME:
   Bu betik yuklenmezse veya JS kapaliysa hicbir kare `hidden`
   kaldirilmaz -- bu yuzden HTML'de ilk kare `hidden` DEGILDIR ve
   digerleri `hidden`dir.  Betik yoksa kullanici en azindan ana
   ekrani gorur; CSS'te `.vitrin-secim` JS yoksa da okunur kalir.

   ERISILEBILIRLIK:
   - role="tablist" / role="tab" / role="tabpanel" HTML'de tanimli
   - aria-selected ve hidden birlikte guncellenir
   - ok tuslari, Home/End ile gezinme (WAI-ARIA sekme kalibi)
   - secili sekme tek odak durak noktasi olur (tabindex yonetimi)

   SOZLESME:
   - Sekme dugmesi: `.vs`, `data-kare="{kare_id}"`
   - Kare: `.vk`, id sekmenin `data-kare` degeriyle ayni
   - `hidden` niteligi kullanilir; CSS'te [hidden]{display:none!important}
     genel kurali oldugu icin display kurallari bunu EZMEZ
   ============================================================ */
(function () {
  'use strict';

  var kok = document.getElementById('vitrin');
  if (!kok) return;

  var sekmeler = [].slice.call(kok.querySelectorAll('.vs'));
  if (!sekmeler.length) return;

  function kareBul(s) {
    var id = s.getAttribute('data-kare');
    return id ? document.getElementById(id) : null;
  }

  function sec(hedef, odakla) {
    for (var i = 0; i < sekmeler.length; i++) {
      var s = sekmeler[i];
      var acik = (s === hedef);
      s.setAttribute('aria-selected', acik ? 'true' : 'false');
      // Sekme listesinde tek odak durak noktasi: WAI-ARIA kalibi
      s.setAttribute('tabindex', acik ? '0' : '-1');
      var k = kareBul(s);
      if (k) {
        if (acik) k.removeAttribute('hidden');
        else k.setAttribute('hidden', '');
      }
    }
    if (odakla && hedef) hedef.focus();
  }

  for (var i = 0; i < sekmeler.length; i++) {
    (function (s) {
      s.addEventListener('click', function () { sec(s, false); });
    })(sekmeler[i]);
  }

  // Ok tuslari ile gezinme
  kok.addEventListener('keydown', function (e) {
    var etkin = document.activeElement;
    var n = sekmeler.indexOf(etkin);
    if (n < 0) return;
    var y = -1;
    if (e.key === 'ArrowDown' || e.key === 'ArrowRight') y = (n + 1) % sekmeler.length;
    else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') y = (n - 1 + sekmeler.length) % sekmeler.length;
    else if (e.key === 'Home') y = 0;
    else if (e.key === 'End') y = sekmeler.length - 1;
    if (y < 0) return;
    e.preventDefault();
    sec(sekmeler[y], true);
  });

  // Baslangic durumu: HTML'de aria-selected="true" olan sekme,
  // yoksa ilki.  Boylece HTML ile betik arasinda tutarsizlik olmaz.
  var ilk = null;
  for (var j = 0; j < sekmeler.length; j++) {
    if (sekmeler[j].getAttribute('aria-selected') === 'true') { ilk = sekmeler[j]; break; }
  }
  sec(ilk || sekmeler[0], false);
})();
