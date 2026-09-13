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
  /* ================================================================
     FAZ15-TEMA-CEREZ — tema tercihi paneller arasi PAYLASILIR
     ----------------------------------------------------------------
     Olculen kusur: anahtar YOLDAN turetiliyordu, dolayisiyla her panel
     kendi tercihini ayri tutuyordu:
         /          -> goktungu_tema_genel
         /admin/    -> goktungu_tema_admin
         /company/  -> goktungu_tema_company
         /404.html  -> goktungu_tema_404.html   (dosya adi siziyordu)
     Tanitim sayfasinda gece temasina gecmek admin panelini
     etkilemiyordu.

     Ayrica `localStorage` ETKI ALANINA OZGUDUR: paneller
     `admin.goktungu.com` gibi alt alan adlarina tasindiginda hic
     paylasilmaz.  Bu yuzden tasiyici CEREZ oldu.
     ================================================================ */
  const CEREZ_AD = 'goktungu_tema';
  const CEREZ_OMUR = 31536000;          // 1 yil (saniye)

  // Eski, panel bazli anahtarlar -- yalnizca GOC icin okunur.
  function eskiAnahtar() {
    if (typeof window.TEMA_ANAHTAR === 'string' && window.TEMA_ANAHTAR) {
      return window.TEMA_ANAHTAR;
    }
    let yol = '';
    try {
      yol = (location.pathname || '/').split('/').filter(Boolean)[0] || 'genel';
    } catch (e) { yol = 'genel'; }
    return 'goktungu_tema_' + yol;
  }

  /* MERKEZ UYGULAMA KISITI
     Merkez Uygulama satin alan firmalar sistemi kapali devre veya
     `localhost` uzerinde calistiriyor; orada alt alan adi YOKTUR.
     `Domain` niteligi yalnizca gercek bir alan adinda yazilir.
     Tarayicilar IP adreslerine `Domain` niteligini REDDEDER -- kosulsuz
     yazilsa merkez kurulumlarinda cerez hic kurulmaz ve tema kaliciligi
     sessizce bozulurdu. */
  function cerezAlani() {
    let h = '';
    try { h = (location.hostname || '').toLowerCase(); } catch (e) { return ''; }
    if (!h) return '';
    // IPv4 / IPv6 / localhost -> Domain YAZILMAZ
    if (h === 'localhost' || h.indexOf(':') >= 0) return '';
    if (/^\d{1,3}(\.\d{1,3}){3}$/.test(h)) return '';
    // Tek etiketli ana makine adi (or. `merkez`) -> Domain yazilamaz
    const p = h.split('.');
    if (p.length < 2) return '';
    // Son iki etiket: alt alan adlari arasinda paylasim icin yeterli.
    // `app.goktungu.com` -> `.goktungu.com`
    return '.' + p.slice(-2).join('.');
  }

  function cerezOku() {
    try {
      const c = document.cookie || '';
      const parcalar = c.split(';');
      for (let i = 0; i < parcalar.length; i++) {
        const e = parcalar[i].trim();
        if (e.indexOf(CEREZ_AD + '=') === 0) {
          return decodeURIComponent(e.slice(CEREZ_AD.length + 1));
        }
      }
    } catch (e) {}
    return null;
  }

  function cerezYaz(t) {
    try {
      const alan = cerezAlani();
      let s = CEREZ_AD + '=' + encodeURIComponent(t) +
              '; Path=/; Max-Age=' + CEREZ_OMUR + '; SameSite=Lax';
      if (alan) s += '; Domain=' + alan;
      // `Secure` yalnizca HTTPS'te anlamlidir; merkez kurulumlari duz
      // metin HTTP uzerinde calisabilir ve `Secure` cerezi engellerdi.
      try {
        if (location.protocol === 'https:') s += '; Secure';
      } catch (e) {}
      document.cookie = s;
    } catch (e) {}
  }

  /* Okuma sirasi: cerez -> panele ozgu anahtar (goc) -> tanitim
     sayfasinin eski anahtari -> marka gecisi oncesi kalinti.
     Mevcut kullanicinin secimi kaybolmaz. */
  function oku() {
    const c = cerezOku();
    if (c === KOYU || c === ACIK) return c;
    const gocAnahtarlari = [
      eskiAnahtar(),          // bu panelin kendi eski anahtari
      'goktungu_tema_genel',  // tanitim sayfasi
      'gozcu_tema_genel'      // marka gecisi oncesi
    ];
    for (let i = 0; i < gocAnahtarlari.length; i++) {
      let v = null;
      try { v = localStorage.getItem(gocAnahtarlari[i]); } catch (e) {}
      if (v === KOYU || v === ACIK) {
        cerezYaz(v);          // bir kereye mahsus goc
        return v;
      }
    }
    return null;
  }

  /* Cerez BIRINCIL tasiyici; `localStorage` geriye donuk uyum icin
     yazilmaya devam eder (cerez silinirse tercih yine durur). */
  function yaz(t) {
    cerezYaz(t);
    try { localStorage.setItem(CEREZ_AD, t); } catch (e) {}
    try { localStorage.setItem(eskiAnahtar(), t); } catch (e) {}
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
