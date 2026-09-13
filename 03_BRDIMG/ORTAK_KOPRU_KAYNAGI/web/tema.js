/* =====================================================================
   TEMA.JS — panel bagimsiz gunduz/gece dongusu
   ---------------------------------------------------------------------
   Dort arayuzun (tanitim / kurumsal / admin / kopru) ortak tema
   anahtari.  Merkez Uygulamadaki (GCS) `js/tema.js` SOZLESMESI birebir
   korunur, boylece kullanici hangi arayuzde olursa olsun ayni davranisi
   gorur:

       <html data-tema="acik">   -> gunduz (acik) tema
       <html>                    -> gece (koyu) tema, ontanimli

   GCS'te tema secimi sunucuya WS ile yazilir (`{tip:"tema"}`) cunku o
   arayuz oturumlu ve tek kullanicilik.  Buradaki dort panel icin ayni
   yolu kullanmak dogru degildi: kurumsal/admin panelleri cok
   kullanicili, tanitim sayfasi ise oturumsuz.  Bu yuzden secim
   `localStorage` icinde panel bazli anahtarla saklanir.

   ILK ACILIS: kullanici hic secim yapmadiysa isletim sisteminin
   tercihi (`prefers-color-scheme`) izlenir ve OS tercihi degistiginde
   canli olarak takip edilir.  Kullanici bir kez elle sectiginde artik
   OS'u izlemeyi birakir -- elle yapilan secim her zaman ustundur.

   KULLANIM
     <script src="/js/tema.js"></script>
     ... ve bir tetikleyici (herhangi biri):
       <button data-tema-dugme></button>     (otomatik ikon + baslik)
       window.temaDegistir()                 (dongu: koyu <-> acik)
       window.temaUygula("acik")             (dogrudan ata)

   Panel kendi anahtarini secebilir:
     <script>window.TEMA_ANAHTAR = "goktungu_tema_kurumsal";</script>

   OLAY: tema her degistiginde `document` uzerinde `tema-degisti`
   olayi tetiklenir; ayrinti `{tema:"koyu"|"acik", kaynak:"..."}`.
   Cizim yapan bilesenler (grafik, canvas) buna baglanabilir.
   ===================================================================== */
'use strict';

(function () {
  const KOYU = 'koyu';
  const ACIK = 'acik';

  // Panel kendi anahtarini tanimlayabilir; tanimlamazsa yol adindan
  // turetilir (or. /company/ -> goktungu_tema_company).  Boylece kurumsal
  // panelde secilen tema admin panelini etkilemez.
  function anahtar() {
    if (typeof window.TEMA_ANAHTAR === 'string' && window.TEMA_ANAHTAR) {
      return window.TEMA_ANAHTAR;
    }
    let yol = '';
    try {
      yol = (location.pathname || '/').split('/').filter(Boolean)[0] || 'genel';
    } catch (e) { yol = 'genel'; }
    return 'goktungu_tema_' + yol;
  }

  function oku() {
    try { return localStorage.getItem(anahtar()); } catch (e) { return null; }
  }
  function yaz(t) {
    try { localStorage.setItem(anahtar(), t); } catch (e) {}
  }

  /* --------------------------------------------------------------- CSS */
  // Yalnizca dugmenin kendi bicimi.  Panellerin renk degiskenleri
  // (--zemin/--yazi/...) her panelin kendi stil.css dosyasinda
  // `:root[data-tema="acik"]` blogu ile tanimlanir; bu dosya renk
  // KARARI vermez, yalnizca durumu tasir.
  const CSS = `
.tema-dugme{display:inline-flex;align-items:center;justify-content:center;
  width:32px;height:32px;padding:0;border-radius:8px;cursor:pointer;
  background:transparent;border:1px solid var(--cerceve,var(--cizgi,#223046));
  color:var(--yazi2,var(--sonuk,#93a3bb));line-height:1;
  transition:color .16s,border-color .16s,background .16s}
.tema-dugme:hover{color:var(--yazi,#e6edf7);
  border-color:var(--vurgu,#1f9e8f);background:rgba(255,255,255,.06)}
.tema-dugme svg{width:17px;height:17px;display:block}
:root[data-tema="acik"] .tema-dugme:hover{background:rgba(0,0,0,.05)}
`;

  let _cssKuruldu = false;
  function cssKur() {
    if (_cssKuruldu) return;
    _cssKuruldu = true;
    const s = document.createElement('style');
    s.setAttribute('data-tema-css', '');
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  /* ------------------------------------------------------------- ikonlar */
  // Gece kipindeyken GUNES gosterilir ("gunduze gec"), gunduz kipinde AY.
  const IKON_GUNES =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"' +
    ' stroke-width="2" stroke-linecap="round" aria-hidden="true">' +
    '<circle cx="12" cy="12" r="4.2"/>' +
    '<path d="M12 2v2.4M12 19.6V22M2 12h2.4M19.6 12H22' +
    'M4.9 4.9l1.7 1.7M17.4 17.4l1.7 1.7M19.1 4.9l-1.7 1.7' +
    'M6.6 17.4l-1.7 1.7"/></svg>';
  const IKON_AY =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"' +
    ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round"' +
    ' aria-hidden="true">' +
    '<path d="M20.5 14.6A8.6 8.6 0 1 1 9.4 3.5a6.9 6.9 0 0 0 11.1 11.1z"/>' +
    '</svg>';

  /* --------------------------------------------------------------- durum */
  // Kullanici elle sectiyse OS tercihini artik izlemeyiz.
  let _elleSecildi = !!oku();

  function aktif() {
    return document.documentElement.dataset.tema === ACIK ? ACIK : KOYU;
  }

  function dugmeleriTazele() {
    const t = aktif();
    // Gece kipinde "gunduze gec" daveti, gunduz kipinde tersi.
    const geceMi = (t === KOYU);
    const ikon = geceMi ? IKON_GUNES : IKON_AY;
    const baslik = geceMi ? 'Gündüz temasına geç' : 'Gece temasına geç';
    document.querySelectorAll('[data-tema-dugme]').forEach((o) => {
      if (!o.classList.contains('tema-dugme')) o.classList.add('tema-dugme');
      if (o.getAttribute('type') === null && o.tagName === 'BUTTON') {
        o.setAttribute('type', 'button');
      }
      o.innerHTML = ikon;
      o.title = baslik;
      o.setAttribute('aria-label', baslik);
      o.setAttribute('aria-pressed', String(!geceMi));
    });
  }

  /* -------------------------------------------------------------- uygula */
  function uygula(tema, kaydet, kaynak) {
    if (tema !== KOYU && tema !== ACIK) return;
    const onceki = aktif();

    // GCS sozlesmesi: koyu tema NITELIK TASIMAZ (varsayilan), acik tema
    // `data-tema="acik"` tasir.  Ayni desen korunuyor ki panellerin
    // CSS'i tek bir secici ile yazilabilsin.
    if (tema === ACIK) {
      document.documentElement.dataset.tema = ACIK;
    } else {
      delete document.documentElement.dataset.tema;
    }

    if (kaydet) {
      yaz(tema);
      _elleSecildi = true;
    }
    dugmeleriTazele();

    if (onceki !== tema) {
      try {
        document.dispatchEvent(new CustomEvent('tema-degisti', {
          detail: { tema: tema, kaynak: kaynak || 'elle' }
        }));
      } catch (e) {}
    }
  }

  function degistir() {
    uygula(aktif() === ACIK ? KOYU : ACIK, true, 'dugme');
  }

  /* ---------------------------------------------------------- ilk kurulum */
  function osTercihi() {
    try {
      if (window.matchMedia &&
          window.matchMedia('(prefers-color-scheme: light)').matches) {
        return ACIK;
      }
    } catch (e) {}
    return KOYU;
  }

  // Erken uygulama: CSS yuklendikten sonra ama boyamadan once niteligi
  // koymak "renk sicramasi"ni (flash) onler.  Bu dosya <head> icinde
  // cagrildiginda body henuz yoktur; nitelik `documentElement` uzerinde
  // oldugu icin sorun olmaz.
  (function ilk() {
    const kayit = oku();
    uygula(kayit || osTercihi(), false, kayit ? 'kayit' : 'os');
  })();

  // OS tercihi degisirse (kullanici elle secmediyse) canli takip et.
  try {
    if (window.matchMedia) {
      const mq = window.matchMedia('(prefers-color-scheme: light)');
      const dinle = (ev) => {
        if (_elleSecildi) return;
        uygula(ev.matches ? ACIK : KOYU, false, 'os');
      };
      if (mq.addEventListener) mq.addEventListener('change', dinle);
      else if (mq.addListener) mq.addListener(dinle);
    }
  } catch (e) {}

  /* ------------------------------------------------------- tetikleyici */
  // Delegasyon: dugme sonradan uretilse de (SAYFALAR yonlendirmesi,
  // kopru panelinin dinamik ust seridi) calisir.
  document.addEventListener('click', (ev) => {
    const t = ev.target && ev.target.closest
      ? ev.target.closest('[data-tema-dugme]') : null;
    if (!t) return;
    ev.preventDefault();
    degistir();
  });

  function kur() {
    cssKur();
    dugmeleriTazele();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', kur);
  } else {
    kur();
  }

  /* ------------------------------------------------------------- dis API */
  window.temaUygula = (t) => uygula(t, true, 'api');
  window.temaDegistir = degistir;
  window.temaAktif = aktif;
  window.temaDugmeTazele = dugmeleriTazele;
})();
