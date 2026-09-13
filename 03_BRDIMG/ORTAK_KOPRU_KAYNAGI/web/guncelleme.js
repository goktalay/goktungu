/* GÖKTUNGU KÖPRÜ — imzalı uygulama içi güncelleme arayüzü.
   Paket URL'si istemciye verilmez. Yerel API, indirilen paketi ve
   özetini doğrular; bu arayüz yalnız durum gösterir ve açık kullanıcı
   eylemini iletir. */
'use strict';
(function(){
  var sonIstek = 0, durum = null, pencereKuruldu = false;
  function e(id){ return document.getElementById(id); }
  function html(s){ return String(s == null ? '' : s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
  function istek(yol, ayar){
    ayar = ayar || {};
    var baslik = {'Content-Type':'application/json'};
    if(ayar.method === 'POST') baslik['X-Kopru-Jeton'] = (window.G && G.jeton) || '1';
    return fetch(yol, {method:ayar.method || 'GET', headers:baslik,
      credentials:'same-origin', body:ayar.govde ? JSON.stringify(ayar.govde) : undefined})
      .then(function(r){ return r.json().catch(function(){ return {}; }).then(function(v){
        if(!r.ok){ var x = new Error(v.hata || ('Sunucu '+r.status)); x.kod=r.status; throw x; }
        return v;
      }); });
  }
  function kur(){
    if(pencereKuruldu) return;
    pencereKuruldu = true;
    var stil = document.createElement('style');
    stil.textContent = ''+
      '#guncellemeSerit{display:none;position:fixed;z-index:10050;top:0;left:0;right:0;min-height:42px;padding:9px 20px;background:#a30f16;color:#fff;border-bottom:1px solid #ff8990;font:600 13px/1.35 Arial,sans-serif;text-align:center;box-shadow:0 3px 13px #0008;cursor:pointer}'+
      '#guncellemeSerit.goster{display:block} #guncellemeSerit strong{margin-right:8px} #guncellemePencere{display:none;position:fixed;z-index:10060;inset:0;background:#0009;align-items:center;justify-content:center;padding:18px} #guncellemePencere.goster{display:flex} #guncellemeKutu{width:min(540px,100%);min-height:250px;background:var(--zemin,#101924);border:1px solid #cc3940;border-radius:8px;color:var(--yazi,#edf4ff);box-shadow:0 16px 48px #000;display:flex;flex-direction:column} #guncellemeBaslik{padding:18px 20px 12px;border-bottom:1px solid #cc394055;font-size:18px;font-weight:600;color:#ffabb0} #guncellemeIcerik{padding:20px;flex:1;line-height:1.6} #guncellemeDurum{min-height:48px;color:var(--soluk,#afbdd0)} #guncellemeIlerleme{height:7px;background:#ffffff19;border-radius:8px;overflow:hidden;margin:14px 0} #guncellemeIlerleme i{display:block;height:100%;width:0;background:#ef5660;transition:width .25s} #guncellemeEylem{display:flex;justify-content:flex-end;gap:10px;padding:14px 20px;border-top:1px solid #ffffff18} #guncellemeEylem button{min-width:118px;padding:9px 12px;border-radius:4px;border:1px solid #78899f;background:#1a2838;color:#fff;cursor:pointer} #guncellemeEylem button.birincil{background:#bd2029;border-color:#f66b72} #guncellemeEylem button:disabled{opacity:.5;cursor:wait} #guncellemeNot{font-size:12px;color:#aebdce;margin-top:10px}';
    document.head.appendChild(stil);
    var serit = document.createElement('div'); serit.id='guncellemeSerit'; serit.setAttribute('role','button'); serit.tabIndex=0;
    serit.addEventListener('click', ac); serit.addEventListener('keydown', function(x){ if(x.key==='Enter'||x.key===' '){x.preventDefault();ac();} });
    document.body.appendChild(serit);
    var modal = document.createElement('div'); modal.id='guncellemePencere'; modal.innerHTML = '<section id="guncellemeKutu" role="dialog" aria-modal="true" aria-labelledby="guncellemeBaslik"><div id="guncellemeBaslik">Yazılım Güncellemesi</div><div id="guncellemeIcerik"><div id="guncellemeDurum"></div><div id="guncellemeIlerleme"><i></i></div><div id="guncellemeNot"></div></div><div id="guncellemeEylem"><button type="button" id="guncellemeKapat">Kapat</button><button type="button" class="birincil" id="guncellemeDugme">İndir</button></div></section>';
    modal.addEventListener('click', function(x){ if(x.target===modal) kapat(); });
    document.body.appendChild(modal);
    e('guncellemeKapat').addEventListener('click', kapat);
    e('guncellemeDugme').addEventListener('click', eylem);
  }
  function bayt(n){ n=Number(n)||0; if(n<1024*1024) return Math.round(n/1024)+' KB'; return (n/(1024*1024)).toFixed(1)+' MB'; }
  function ciz(){
    kur();
    var s = durum || {};
    var yeni = !!s.guncelleme_var;
    var serit = e('guncellemeSerit');
    if(yeni){ serit.innerHTML='<strong>GÜNCELLEME GEREKLİ</strong> '+html(s.mevcut_surum)+' → '+html(s.hedef_surum)+' · Güncellemek için tıklayın'; serit.classList.add('goster'); }
    else serit.classList.remove('goster');
    if(!e('guncellemePencere').classList.contains('goster')) return;
    var asama=s.asama || 'bekliyor', ind=Number(s.indirilen)||0, top=Number(s.toplam)||0;
    var yuzde=top ? Math.max(0,Math.min(100,Math.floor(ind*100/top))) : 0;
    e('guncellemeIlerleme').firstChild.style.width=yuzde+'%';
    var baslik='Güncelleme bekliyor';
    if(asama==='indiriliyor') baslik='Doğrulanmış paket indiriliyor: '+bayt(ind)+' / '+bayt(top)+' ('+yuzde+'%)';
    else if(asama==='indirildi') baslik='Paket indirildi ve SHA-256 özeti doğrulandı.';
    else if(asama==='kurulum_baslatildi') baslik='Kurulum başlatıldı. Tamamlandığında uygulamayı yeniden açın.';
    else if(asama==='hata') baslik='Güncelleme işlemi tamamlanamadı: '+(s.hata||'bilinmeyen hata');
    else if(asama==='denetleniyor') baslik='İmzalı sürüm bildirimi denetleniyor…';
    e('guncellemeDurum').textContent=baslik;
    e('guncellemeNot').textContent=s.notlar || 'Paket yalnız imza ve SHA-256 doğrulamasından sonra kurulabilir.';
    var b=e('guncellemeDugme'); b.disabled=false;
    if(asama==='indiriliyor'||asama==='denetleniyor'){ b.textContent='Bekleyin'; b.disabled=true; }
    else if(asama==='indirildi'){ b.textContent='Güncellemeyi Uygula'; }
    else if(asama==='kurulum_baslatildi'){ b.textContent='Başlatıldı'; b.disabled=true; }
    else { b.textContent='Güncellemeyi İndir'; }
  }
  function ac(){ kur(); e('guncellemePencere').classList.add('goster'); ciz(); if(!durum || !durum.kontrol_edildi) denetle(); }
  function kapat(){ var m=e('guncellemePencere'); if(m) m.classList.remove('goster'); }
  function denetle(){ return istek('/api/guncelleme/denetle',{method:'POST'}).then(function(v){ durum=v.durum||v; ciz(); }).catch(function(x){ durum={asama:'hata',hata:x.message}; ciz(); }); }
  function eylem(){
    var s=durum||{};
    if(s.asama==='indirildi'){
      if(!window.confirm('Doğrulanmış güncelleme kurulumu başlatılsın mı? Uygulama yeniden başlatılabilir.')) return;
      istek('/api/guncelleme/kur',{method:'POST'}).then(function(v){durum=v.durum||v;ciz();}).catch(function(x){durum={asama:'hata',hata:x.message};ciz();});
    } else {
      istek('/api/guncelleme/indir',{method:'POST'}).then(function(v){durum=v.durum||v;ciz();}).catch(function(x){durum={asama:'hata',hata:x.message};ciz();});
    }
  }
  window.guncellemeCek=function(zorla){
    var simdi=Date.now(); if(!zorla && simdi-sonIstek<1800) return;
    sonIstek=simdi; istek('/api/guncelleme').then(function(v){durum=v||{};ciz();}).catch(function(){});
  };
  document.addEventListener('DOMContentLoaded', function(){ kur(); window.guncellemeCek(true); });
})();
