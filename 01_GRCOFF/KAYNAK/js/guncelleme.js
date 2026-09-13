// GOKTUNGU — UYGULAMA ICI DOSYA TABANLI GUNCELLEME ARAYUZU (v2.5.30)
//
// Yalniz yerel WebSocket uzerinden DosyaGuncellemeYoneticisi ile konusur.
// Bu ekran imza/SHA-256 dogrulamasini yapmaz; onlar sunucuda ve arka
// plandaki gozetmende yapilir. Akis TEK ADIMDIR: "Denetle" yeni surum var
// mi bakar; "Guncelle ve Yeniden Baslat" gozetmene bir tetik gonderir, o da
// yalniz DEGISEN dosyalari indirip atomik yerlestirir ve uygulamayi yeniden
// baslatir (imzasiz .exe indirilmez -> Defender yanlis-pozitifi olmaz).
(function(){
  'use strict';
  let sonDurum = null;
  let zamanlayici = null;

  function sozluk(){ return (typeof D === 'function') ? D() : {}; }
  function metin(anahtar, yedek){ return sozluk()[anahtar] || yedek || anahtar; }
  function degistir(m, alanlar){
    return String(m || '').replace(/\{(\w+)\}/g, function(_, ad){
      return Object.prototype.hasOwnProperty.call(alanlar || {}, ad) ? alanlar[ad] : _;
    });
  }
  function wsGonder(tip){
    try {
      if (typeof ws !== 'undefined' && ws && ws.readyState === WebSocket.OPEN){
        ws.send(JSON.stringify({tip: tip}));
        return true;
      }
    } catch (_) {}
    return false;
  }
  function asamaMetni(d){
    if (!d || !d.kontrol_edildi && !d.asama) return metin('guncellemeBaglanti', 'Güncelleme denetimi için bağlantı bekleniyor.');
    if (d.asama === 'denetleniyor') return metin('guncellemeDenetleniyor', 'Yeni sürüm denetleniyor…');
    if (d.asama === 'uygula_istendi') return metin('guncellemeUygulaniyor', 'Güncelleme başlatıldı. Değişen dosyalar indirilip yerleştiriliyor; uygulama birazdan kendiliğinden yeniden başlayacak.');
    if (d.hata) return metin('guncellemeHata', 'Güncelleme işlemi tamamlanamadı') + ': ' + d.hata;
    if (d.asama === 'guncel') return metin('guncellemeGuncel', 'Yazılımınız güncel.');
    if (d.guncelleme_var) return degistir(metin('guncellemeHazirDosya', 'Yeni sürüm {hedef} hazır — {sayi} dosya güncellenecek.'), {hedef: d.hedef_surum || '—', sayi: Number(d.dosya_sayisi) || 0});
    return metin('guncellemeBaglanti', 'Güncelleme denetimi için bağlantı bekleniyor.');
  }
  function stilEkle(){
    if (document.getElementById('gt-guncelleme-stil')) return;
    const s = document.createElement('style');
    s.id = 'gt-guncelleme-stil';
    s.textContent = [
      '#guncellemeSerit{flex:0 0 42px;min-height:42px;box-sizing:border-box;display:none;align-items:center;justify-content:center;gap:12px;padding:6px 16px;background:linear-gradient(90deg,#14532d,#166534,#14532d);color:#fff;border-bottom:1px solid #bbf7d0;box-shadow:0 2px 12px rgba(22,101,52,.45);font:700 12px/1.2 Segoe UI,system-ui,sans-serif;letter-spacing:.075em;z-index:2700;cursor:pointer;user-select:none}',
      '#guncellemeSerit.aktif{display:flex}#guncellemeSerit:hover{filter:brightness(1.12)}#guncellemeSerit i{font-size:15px}.gu-serit-metin{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gu-serit-ok{font-size:11px;opacity:.92}',
      '#gu-perde{display:none;position:fixed;inset:0;z-index:10050;background:rgba(0,0,0,.64);align-items:center;justify-content:center;padding:22px;box-sizing:border-box}#gu-perde.aktif{display:flex}#gu-pencere{width:min(570px,calc(100vw - 44px));max-height:calc(100vh - 44px);overflow:auto;box-sizing:border-box;background:var(--panel,#0b0e11);color:var(--metin,#cfd8e3);border:1px solid var(--cizgi,#1e2630);border-top:3px solid #16a34a;border-radius:8px;box-shadow:0 22px 65px rgba(0,0,0,.55);font:13px/1.45 Segoe UI,system-ui,sans-serif}',
      '.gu-baslik{display:flex;align-items:center;gap:10px;padding:15px 18px 12px;border-bottom:1px solid var(--cizgi,#1e2630);letter-spacing:.09em;font-size:13px;font-weight:700}.gu-baslik i{color:#4ade80;font-size:17px}.gu-kapat{margin-left:auto;border:0;background:transparent;color:var(--metin,#cfd8e3);font-size:20px;cursor:pointer}.gu-icerik{padding:17px 18px}.gu-surumler{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:0 0 15px}.gu-kutu{padding:10px 12px;border:1px solid var(--cizgi,#1e2630);border-radius:5px;background:var(--dugme-arka,#141a21)}.gu-etiket{display:block;color:var(--soluk,#5c6b7a);font-size:10px;letter-spacing:.08em;margin-bottom:3px}.gu-deger{font-weight:700;color:var(--metin,#cfd8e3)}.gu-not{margin:10px 0 14px;white-space:pre-wrap;color:var(--soluk,#5c6b7a);max-height:112px;overflow:auto}.gu-durum{min-height:42px;padding:10px 12px;margin:12px 0;border-left:3px solid #16a34a;background:rgba(22,101,52,.14)}.gu-guvenlik{font-size:11px;color:var(--soluk,#5c6b7a);margin:14px 0 0}.gu-dugmeler{display:flex;justify-content:flex-end;gap:8px;padding:12px 18px 16px;border-top:1px solid var(--cizgi,#1e2630)}.gu-dugme{min-width:126px;min-height:34px;padding:7px 12px;border:1px solid var(--cizgi,#1e2630);border-radius:4px;background:var(--dugme-arka,#141a21);color:var(--metin,#cfd8e3);cursor:pointer;font:700 11px Segoe UI,system-ui,sans-serif;letter-spacing:.055em}.gu-dugme:hover:not(:disabled){filter:brightness(1.16)}.gu-dugme.ana{background:#15803d;border-color:#22c55e;color:#fff}.gu-dugme:disabled{opacity:.48;cursor:not-allowed}@media(max-width:520px){#guncellemeSerit{min-height:52px;flex-basis:52px;font-size:10px}.gu-surumler{grid-template-columns:1fr}.gu-dugmeler{flex-wrap:wrap}.gu-dugme{flex:1}}'
    ].join('');
    document.head.appendChild(s);
  }
  function domKur(){
    stilEkle();
    if (!document.getElementById('guncellemeSerit')){
      const serit = document.createElement('div');
      serit.id = 'guncellemeSerit';
      serit.setAttribute('role', 'button');
      serit.setAttribute('tabindex', '0');
      serit.innerHTML = '<i class="fa-solid fa-cloud-arrow-down" aria-hidden="true"></i><span class="gu-serit-metin"></span><i class="fa-solid fa-chevron-right gu-serit-ok" aria-hidden="true"></i>';
      serit.addEventListener('click', pencereAc);
      serit.addEventListener('keydown', function(e){ if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pencereAc(); } });
      const ust = document.getElementById('ustBar');
      document.body.insertBefore(serit, ust || document.body.firstChild);
    }
    if (!document.getElementById('gu-perde')){
      const perde = document.createElement('div');
      perde.id = 'gu-perde';
      perde.setAttribute('aria-hidden', 'true');
      perde.innerHTML = '<section id="gu-pencere" role="dialog" aria-modal="true" aria-labelledby="gu-baslik"><header class="gu-baslik"><i class="fa-solid fa-shield-halved" aria-hidden="true"></i><span id="gu-baslik"></span><button class="gu-kapat" type="button" aria-label="Kapat">×</button></header><div class="gu-icerik"><div class="gu-surumler"><div class="gu-kutu"><span class="gu-etiket gu-mevcut-etiket"></span><span class="gu-deger" id="gu-mevcut"></span></div><div class="gu-kutu"><span class="gu-etiket gu-hedef-etiket"></span><span class="gu-deger" id="gu-hedef"></span></div></div><span class="gu-etiket gu-notlar-etiket"></span><div id="gu-notlar" class="gu-not">—</div><div id="gu-durum" class="gu-durum"></div><div class="gu-guvenlik"></div></div><footer class="gu-dugmeler"><button id="gu-denetle" class="gu-dugme" type="button"></button><button id="gu-kapat-alt" class="gu-dugme" type="button"></button><button id="gu-guncelle" class="gu-dugme ana" type="button"></button></footer></section>';
      document.body.appendChild(perde);
      const kapat = function(){ perde.classList.remove('aktif'); perde.setAttribute('aria-hidden','true'); };
      perde.addEventListener('click', function(e){ if (e.target === perde) kapat(); });
      perde.querySelector('.gu-kapat').addEventListener('click', kapat);
      perde.querySelector('#gu-kapat-alt').addEventListener('click', kapat);
      perde.querySelector('#gu-denetle').addEventListener('click', function(){ if (wsGonder('guncelleme_denete')) baslatmaTakibi(); });
      perde.querySelector('#gu-guncelle').addEventListener('click', function(){
        const onay = metin('guncellemeUygulaOnay', 'Değişen dosyalar indirilip kurulacak ve uygulama yeniden başlatılacak. Devam edilsin mi?');
        if (window.confirm(onay) && wsGonder('guncelleme_uygula')) baslatmaTakibi();
      });
    }
  }
  function seritCiz(){
    const serit = document.getElementById('guncellemeSerit');
    if (!serit) return;
    const d = sonDurum || {};
    const goster = !!d.guncelleme_var && d.asama !== 'uygula_istendi';
    serit.classList.toggle('aktif', goster);
    if (goster) serit.querySelector('.gu-serit-metin').textContent = degistir(metin('guncellemeSerit', 'YENİ SÜRÜM HAZIR: {hedef} — GÜNCELLE'), {hedef: d.hedef_surum || '—'});
  }
  function pencereCiz(){
    const perde = document.getElementById('gu-perde');
    if (!perde) return;
    const d = sonDurum || {};
    perde.querySelector('#gu-baslik').textContent = metin('guncellemeBaslik', 'YAZILIM GÜNCELLEMESİ');
    perde.querySelector('.gu-mevcut-etiket').textContent = metin('guncellemeMevcut', 'Mevcut sürüm');
    perde.querySelector('.gu-hedef-etiket').textContent = metin('guncellemeHedef', 'Yeni sürüm');
    perde.querySelector('.gu-notlar-etiket').textContent = metin('guncellemeNotlar', 'Sürüm notları');
    perde.querySelector('#gu-mevcut').textContent = d.mevcut_surum || '—';
    perde.querySelector('#gu-hedef').textContent = (d.guncelleme_var && d.hedef_surum) ? d.hedef_surum : (d.mevcut_surum || '—');
    perde.querySelector('#gu-notlar').textContent = d.notlar || '—';
    perde.querySelector('#gu-durum').textContent = asamaMetni(d);
    perde.querySelector('.gu-guvenlik').textContent = metin('guncellemeGuvenlik', 'Yalnız imzalı manifest ve SHA-256 doğrulaması geçen değişen dosyalar indirilir; çalıştırılabilir kurulum indirilmez.');
    const guncelle = perde.querySelector('#gu-guncelle');
    const denetle = perde.querySelector('#gu-denetle');
    guncelle.textContent = metin('guncellemeUygula', 'GÜNCELLE VE YENİDEN BAŞLAT');
    denetle.textContent = metin('guncellemeDenetle', 'TEKRAR DENETLE');
    perde.querySelector('#gu-kapat-alt').textContent = metin('guncellemeKapat', 'ŞİMDİLİK KAPAT');
    const denetleniyor = d.asama === 'denetleniyor';
    guncelle.disabled = !d.guncelleme_var || d.asama === 'uygula_istendi' || denetleniyor;
    denetle.disabled = denetleniyor;
  }
  function pencereAc(){
    domKur();
    pencereCiz();
    const perde = document.getElementById('gu-perde');
    perde.classList.add('aktif');
    perde.setAttribute('aria-hidden', 'false');
    const odak = perde.querySelector('#gu-guncelle:not([disabled])') || perde.querySelector('#gu-kapat-alt');
    if (odak) odak.focus();
  }
  function baslatmaTakibi(){
    if (zamanlayici) return;
    zamanlayici = window.setInterval(function(){
      if (!wsGonder('guncelleme_durum')) { window.clearInterval(zamanlayici); zamanlayici = null; }
    }, 850);
  }
  function takipBitir(d){
    if (!zamanlayici) return;
    if (!d || d.asama !== 'denetleniyor'){
      window.clearInterval(zamanlayici);
      zamanlayici = null;
    }
  }
  window.guncellemeDurumIsle = function(zarf){
    sonDurum = (zarf && zarf.durum) ? zarf.durum : (zarf || {});
    domKur(); seritCiz(); pencereCiz(); takipBitir(sonDurum);
  };
  window.guncellemeSonucIsle = function(zarf){
    // uygula sonucu: takibi tazele, durum penceresini guncelle
    baslatmaTakibi();
    window.setTimeout(function(){ wsGonder('guncelleme_durum'); }, 80);
  };
  window.guncellemeDurumSor = function(){ wsGonder('guncelleme_durum'); };
  window.guncellemeDilTazele = function(){ domKur(); seritCiz(); pencereCiz(); };
  // Yardim menusu -> "Guncellemeleri Denetle": pencereyi ac + taze denetim iste.
  window.guncellemePenceresiAc = function(){
    domKur();
    if (wsGonder('guncelleme_denete')) baslatmaTakibi();
    pencereAc();
  };
  document.addEventListener('keydown', function(e){
    if (e.key === 'Escape'){
      const perde = document.getElementById('gu-perde');
      if (perde && perde.classList.contains('aktif')) perde.classList.remove('aktif');
    }
  });
  document.addEventListener('DOMContentLoaded', function(){
    domKur();
    ['btnDilTR','btnDilEN'].forEach(function(id){
      const b = document.getElementById(id);
      if (b) b.addEventListener('click', function(){ window.setTimeout(window.guncellemeDilTazele, 0); });
    });
  });
})();
