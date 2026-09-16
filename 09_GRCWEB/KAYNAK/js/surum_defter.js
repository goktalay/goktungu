/* =====================================================================
   SURUM_DEFTER.JS — panel bagimsiz surum defteri + Hakkinda bilesenÄ±
   ---------------------------------------------------------------------
   Her panel (tanitim / kurumsal / admin / kopru) KENDI surum defterini
   yurutur. Bu dosya yalnizca ORTAK arayuz davranisini tasir; veriyi
   panel kendi `surum_verisi.js` dosyasinda tanimlar:

     window.PANEL_SURUM = {
       ad:     "GOKTUNGU Kurumsal Panel",
       surum:  "1.0.0",
       tarih:  "2026-08-16",
       gecmis: [ { s: "1.0.0", t: "2026-08-16", d: ["..."] } ]
     };

   Davranis GCS'teki `js/surum_gecmisi.js` sozlesmesinden olculdu:
   akordiyon satirlar, ilk kayit acik gelir ve GUNCEL rozeti tasir,
   baslikta kapatma dugmesi, basliktan tasinabilir, dis tiklama kapatir.

   KULLANIM
     <script src="/js/surum_verisi.js"></script>   (panele ozel veri)
     <script src="/js/surum_defter.js"></script>   (bu dosya)
     ... ve bir tetikleyici:
     <button data-surum-defter>Hakkinda</button>
       veya  window.surumDefteriAc(fareOlayi)

   Bilesen kendi CSS'ini enjekte eder (panel tema degiskenlerine
   yaslanir), boylece dort panelde ayrica CSS bakimi gerekmez.
   ===================================================================== */
'use strict';

(function () {
  /* --------------------------------------------------------------- CSS */
  // Panel tema degiskenleri (kurumsal/admin): --zemin2/--cerceve/--yazi/
  // --yazi2/--vurgu/--yesil/--kirmizi/--golge/--r
  // Tanitim sayfasi ayni adlari tasimiyorsa yedek degerler devreye girer.
  const CSS = `
.sd-katman{position:fixed;inset:0;z-index:9998;background:rgba(0,0,0,.5)}
.sd-pencere{position:fixed;z-index:9999;width:460px;max-width:94vw;
  background:var(--zemin2,#111825);border:1px solid var(--cerceve,#223046);
  border-radius:var(--r,8px);box-shadow:var(--golge,0 10px 34px rgba(0,0,0,.5));
  display:flex;flex-direction:column;overflow:hidden;
  color:var(--yazi,#e6edf7);font-size:13px}
.sd-baslik{display:flex;align-items:center;justify-content:space-between;
  gap:10px;padding:10px 12px;background:var(--zemin3,#172033);
  border-bottom:1px solid var(--cerceve,#223046);
  font-size:12px;letter-spacing:.08em;font-weight:600;
  cursor:move;user-select:none;touch-action:none}
.sd-kapat{background:transparent;border:none;color:var(--yazi2,#93a3bb);
  cursor:pointer;font-size:18px;line-height:1;padding:0 4px}
.sd-kapat:hover{color:var(--kirmizi,#f85149)}
.sd-kimlik{padding:14px 14px 10px;text-align:center;
  border-bottom:1px solid var(--cerceve,#223046)}
.sd-logo{max-width:120px;max-height:46px;margin:0 auto 8px;display:block}
.sd-ad{font-size:15px;font-weight:700;letter-spacing:.04em}
.sd-surum{margin-top:4px;font-size:12px;color:var(--yazi2,#93a3bb)}
.sd-surum b{color:var(--vurgu,#1f9e8f);font-variant-numeric:tabular-nums}
.sd-telif{margin-top:8px;font-size:11px;color:var(--yazi2,#93a3bb)}
.sd-govde{max-height:min(52vh,420px);overflow-y:auto;padding:8px}
.sd-satir{margin-bottom:5px;border:1px solid var(--cerceve,#223046);
  border-radius:5px;overflow:hidden}
.sd-satir:last-child{margin-bottom:0}
.sd-ust{display:flex;align-items:center;gap:8px;padding:8px 10px;
  cursor:pointer;user-select:none;background:rgba(255,255,255,.045);
  border-left:3px solid var(--cerceve,#223046);
  transition:background .16s,border-left-color .16s}
.sd-ust:hover{background:rgba(255,255,255,.085);
  border-left-color:var(--yazi2,#93a3bb)}
.sd-satir.acik>.sd-ust{background:rgba(31,158,143,.14);
  border-left-color:var(--vurgu,#1f9e8f)}
.sd-satir.acik{border-color:var(--vurgu,#1f9e8f)}
.sd-ok{font-size:10px;color:var(--yazi2,#93a3bb);transition:transform .18s;
  flex:0 0 auto}
.sd-satir.acik .sd-ok{transform:rotate(90deg);color:var(--vurgu,#1f9e8f)}
.sd-no{font-weight:700;font-size:13px;font-variant-numeric:tabular-nums}
.sd-satir.acik .sd-no{color:var(--vurgu,#1f9e8f)}
.sd-guncel{font-size:9px;font-weight:700;letter-spacing:.08em;
  color:var(--yesil,#2ea043);border:1px solid var(--yesil,#2ea043);
  border-radius:3px;padding:1px 5px;flex:0 0 auto}
.sd-tarih{margin-left:auto;font-size:11px;color:var(--yazi2,#93a3bb);
  flex:0 0 auto;font-variant-numeric:tabular-nums}
.sd-detay{display:none;margin:0;padding:8px 12px 10px 22px;
  border-top:1px solid var(--cerceve,#223046);
  font-size:12px;line-height:1.55}
.sd-detay li{margin-bottom:4px}
.sd-detay li:last-child{margin-bottom:0}
.sd-satir.acik .sd-detay{display:block}
.sd-bos{padding:18px;text-align:center;color:var(--yazi2,#93a3bb)}
`;

  function cssKur() {
    if (document.getElementById('sd-stil')) return;
    const s = document.createElement('style');
    s.id = 'sd-stil';
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  /* ----------------------------------------------------------- yardimci */
  function kacir(m) {
    return String(m == null ? '' : m)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  let _pencere = null;
  let _katman = null;

  function kapat() {
    if (_pencere) { _pencere.remove(); _pencere = null; }
    if (_katman) { _katman.remove(); _katman = null; }
    document.removeEventListener('keydown', escDinle, true);
  }

  function escDinle(ev) {
    if (ev.key === 'Escape') { ev.preventDefault(); kapat(); }
  }

  /* --------------------------------------------------------------- ac */
  function ac(fare) {
    const v = window.PANEL_SURUM;
    if (!v) {
      console.warn('[surum_defter] window.PANEL_SURUM tanimli degil');
      return;
    }
    if (_pencere) { kapat(); return; }
    cssKur();

    _katman = document.createElement('div');
    _katman.className = 'sd-katman';
    _katman.addEventListener('pointerdown', kapat);
    document.body.appendChild(_katman);

    const p = document.createElement('div');
    p.className = 'sd-pencere';
    p.setAttribute('role', 'dialog');
    p.setAttribute('aria-label', 'Sürüm defteri');

    /* baslik */
    const bas = document.createElement('div');
    bas.className = 'sd-baslik';
    bas.innerHTML =
      '<span>SÜRÜM DEFTERİ</span>' +
      '<button class="sd-kapat" type="button" title="Kapat"' +
      ' aria-label="Kapat">&times;</button>';
    p.appendChild(bas);

    /* kimlik */
    const kim = document.createElement('div');
    kim.className = 'sd-kimlik';
    const logo = v.logo
      ? `<img class="sd-logo" src="${kacir(v.logo)}" alt="">` : '';
    kim.innerHTML = logo +
      `<div class="sd-ad">${kacir(v.ad || 'GÖKTUNGU')}</div>` +
      `<div class="sd-surum">Sürüm <b>${kacir(v.surum || '-')}</b>` +
      (v.tarih ? ` &middot; ${kacir(v.tarih)}` : '') + '</div>' +
      `<div class="sd-telif">${kacir(v.telif ||
        '© 2026 Türkbey Teknoloji A.Ş.')}</div>`;
    p.appendChild(kim);

    /* govde: akordiyon */
    const g = document.createElement('div');
    g.className = 'sd-govde';
    const gecmis = Array.isArray(v.gecmis) ? v.gecmis : [];
    if (!gecmis.length) {
      g.innerHTML = '<div class="sd-bos">Sürüm kaydı yok.</div>';
    } else {
      gecmis.forEach((k, i) => {
        const sat = document.createElement('div');
        sat.className = 'sd-satir';
        const rozet = (i === 0)
          ? '<span class="sd-guncel">GÜNCEL</span>' : '';
        const maddeler = Array.isArray(k.d) ? k.d : [];
        sat.innerHTML =
          '<div class="sd-ust">' +
            '<span class="sd-ok">&#9654;</span>' +
            `<span class="sd-no">v${kacir(k.s)}</span>` + rozet +
            `<span class="sd-tarih">${kacir(k.t || '')}</span>` +
          '</div>' +
          '<ul class="sd-detay">' +
            maddeler.map((m) => `<li>${kacir(m)}</li>`).join('') +
          '</ul>';
        sat.querySelector('.sd-ust').addEventListener('click', () => {
          sat.classList.toggle('acik');
        });
        if (i === 0) sat.classList.add('acik');
        g.appendChild(sat);
      });
    }
    p.appendChild(g);
    document.body.appendChild(p);
    _pencere = p;

    /* konum: fare yakininda, ekrandan tasmadan */
    const w = p.offsetWidth, h = p.offsetHeight;
    let x = (fare && fare.clientX) ? fare.clientX - w / 2
      : (window.innerWidth - w) / 2;
    let y = (fare && fare.clientY) ? Math.min(fare.clientY, 90)
      : (window.innerHeight - h) / 2;
    x = Math.max(8, Math.min(x, window.innerWidth - w - 8));
    y = Math.max(8, Math.min(y, window.innerHeight - h - 8));
    p.style.left = x + 'px';
    p.style.top = y + 'px';

    /* kapatma */
    bas.querySelector('.sd-kapat')
      .addEventListener('click', (ev) => { ev.stopPropagation(); kapat(); });
    document.addEventListener('keydown', escDinle, true);

    /* basliktan tasima */
    let tut = null;
    bas.addEventListener('pointerdown', (ev) => {
      if (ev.target.closest('.sd-kapat')) return;
      const r = p.getBoundingClientRect();
      tut = { dx: ev.clientX - r.left, dy: ev.clientY - r.top };
      bas.setPointerCapture(ev.pointerId);
    });
    bas.addEventListener('pointermove', (ev) => {
      if (!tut) return;
      const nx = Math.max(0, Math.min(ev.clientX - tut.dx,
        window.innerWidth - p.offsetWidth));
      const ny = Math.max(0, Math.min(ev.clientY - tut.dy,
        window.innerHeight - p.offsetHeight));
      p.style.left = nx + 'px';
      p.style.top = ny + 'px';
    });
    bas.addEventListener('pointerup', () => { tut = null; });
  }

  /* ------------------------------------------------------- tetikleyici */
  // `data-surum-defter` tasiyan her ogeyi delegasyonla baglar; oge
  // sonradan uretilse (SAYFALAR yonlendirmesi) de calisir.
  document.addEventListener('click', (ev) => {
    const t = ev.target && ev.target.closest
      ? ev.target.closest('[data-surum-defter]') : null;
    if (!t) return;
    ev.preventDefault();
    ac(ev);
  });

  window.surumDefteriAc = ac;
  window.surumDefteriKapat = kapat;

  /* Alt bilgi rozeti: `[data-surum-rozet]` ogesine surum yazar. */
  function rozetYaz() {
    const v = window.PANEL_SURUM;
    if (!v) return;
    document.querySelectorAll('[data-surum-rozet]').forEach((o) => {
      o.textContent = 'v' + (v.surum || '-');
      if (!o.hasAttribute('data-surum-defter')) {
        o.setAttribute('data-surum-defter', '');
        o.style.cursor = 'pointer';
        if (!o.title) o.title = 'Sürüm defterini aç';
      }
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', rozetYaz);
  } else {
    rozetYaz();
  }
  window.surumRozetYaz = rozetYaz;
})();
