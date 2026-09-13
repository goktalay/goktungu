// GOKTUNGU — UYGULAMA ICI DOSYA TABANLI GUNCELLEME ARAYUZU (v2.5.33)
//
// Yalniz yerel WebSocket uzerinden DosyaGuncellemeYoneticisi ile konusur.
// v2.5.33: Kullanici istegi "guncellemede progress goster, her detay
// progress ile gorunsun". Gozetmen her adimi (imzali liste, imza, dosya
// karsilastirma, her dosyanin indirilip SHA-256 dogrulanmasi, durdurma,
// her dosyanin yerlestirilmesi, baslatma, sure) guncelleme_ilerleme.json'a
// yazar; bu ekran genel yuzde + asama + alt ilerleme + zaman damgali adim
// listesiyle gosterir. Uygulama yeniden baslarken baglanti beklenir; bitince
// ozet gosterilip sayfa yeni surumle yenilenir. Otomatik guncellemeler de
// ayni pencerede kendiliginden acilir.
(function(){
  'use strict';
  let sonDurum = null;
  let hizliZaman = null;
  let kopusBasi = 0;           // guncelleme sirasinda baglanti koptugu an
  let izlenenKimlik = null;    // ekranda izlenen guncelleme kimligi
  let yenilemeZamani = null;
  const ONAY_ANAHTAR = 'gt_guncelleme_goruldu';

  const ASAMA_AD = {
    istek: 'İstek iletildi', basladi: 'Başladı', manifest: 'İmzalı sürüm listesi',
    imza: 'İmza doğrulama', karsilastirma: 'Dosya karşılaştırma', indirme: 'İndirme',
    durdurma: 'Uygulamayı durdurma', yerlestirme: 'Dosyaları yerleştirme',
    silme: 'Eski dosyaları kaldırma', temizlik: 'Temizlik', baslatma: 'Uygulamayı başlatma',
    tamam: 'Tamamlandı', guncel: 'Güncel', hata: 'Hata', geri_alma: 'Geri alma',
    baglanti: 'Yeniden bağlanma'
  };
  const AKTIF_UYGULAMA = ['istek', 'indirme', 'durdurma', 'yerlestirme', 'silme',
                          'temizlik', 'baslatma', 'geri_alma'];

  function sozluk(){ return (typeof D === 'function') ? D() : {}; }
  function metin(a, y){ return sozluk()[a] || y || a; }
  function wsAcik(){ try { return typeof ws !== 'undefined' && ws && ws.readyState === WebSocket.OPEN; } catch (_) { return false; } }
  function wsGonder(tip){
    try { if (wsAcik()){ ws.send(JSON.stringify({tip: tip})); return true; } } catch (_) {}
    return false;
  }
  function saat(ts){
    const d = new Date((ts || Date.now() / 1000) * 1000);
    return d.toLocaleTimeString('tr-TR', {hour12: false});
  }
  function mb(b){ return (Number(b || 0) / 1048576).toFixed(2); }
  function el(etiket, sinif, icerik){
    const e = document.createElement(etiket);
    if (sinif) e.className = sinif;
    if (icerik != null) e.textContent = icerik;
    return e;
  }
  function onaylandiMi(k){ try { return localStorage.getItem(ONAY_ANAHTAR) === String(k); } catch (_) { return false; } }
  function onayla(k){ try { localStorage.setItem(ONAY_ANAHTAR, String(k)); } catch (_) {} }

  function stilEkle(){
    if (document.getElementById('gt-guncelleme-stil')) return;
    const s = document.createElement('style');
    s.id = 'gt-guncelleme-stil';
    s.textContent = [
      '#guncellemeSerit{flex:0 0 42px;min-height:42px;box-sizing:border-box;display:none;align-items:center;justify-content:center;gap:12px;padding:6px 16px;background:linear-gradient(90deg,#14532d,#166534,#14532d);color:#fff;border-bottom:1px solid #bbf7d0;font:700 12px/1.2 Segoe UI,system-ui,sans-serif;letter-spacing:.075em;z-index:2700;cursor:pointer;user-select:none;position:relative;overflow:hidden}',
      '#guncellemeSerit.aktif{display:flex}#guncellemeSerit:hover{filter:brightness(1.12)}#guncellemeSerit .gu-serit-dolgu{position:absolute;left:0;top:0;bottom:0;background:rgba(255,255,255,.14);transition:width .3s}#guncellemeSerit>*:not(.gu-serit-dolgu){position:relative}',
      '#gu-perde{display:none;position:fixed;inset:0;z-index:10050;background:rgba(0,0,0,.64);align-items:center;justify-content:center;padding:22px;box-sizing:border-box}#gu-perde.aktif{display:flex}',
      '#gu-pencere{width:min(640px,calc(100vw - 44px));max-height:calc(100vh - 44px);display:flex;flex-direction:column;box-sizing:border-box;background:var(--panel,#0b0e11);color:var(--metin,#cfd8e3);border:1px solid var(--cizgi,#1e2630);border-top:3px solid #16a34a;border-radius:8px;box-shadow:0 22px 65px rgba(0,0,0,.55);font:13px/1.45 Segoe UI,system-ui,sans-serif}',
      '#gu-pencere.hata{border-top-color:#dc2626}.gu-baslik{display:flex;align-items:center;gap:10px;padding:14px 18px 11px;border-bottom:1px solid var(--cizgi,#1e2630);letter-spacing:.09em;font-size:13px;font-weight:700}.gu-baslik i{color:#4ade80;font-size:17px}.gu-kapat{margin-left:auto;border:0;background:transparent;color:var(--metin,#cfd8e3);font-size:20px;cursor:pointer}',
      '.gu-icerik{padding:14px 18px;overflow:auto;flex:1 1 auto}.gu-surumler{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:0 0 12px}.gu-kutu{padding:8px 12px;border:1px solid var(--cizgi,#1e2630);border-radius:5px;background:var(--dugme-arka,#141a21)}.gu-etiket{display:block;color:var(--soluk,#6b7b8c);font-size:10px;letter-spacing:.08em;margin-bottom:3px}.gu-deger{font-weight:700}',
      '.gu-asama{display:flex;justify-content:space-between;align-items:baseline;gap:10px;margin:4px 0 6px}.gu-asama-ad{font-weight:700;font-size:13px}.gu-yuzde{font:700 20px/1 Segoe UI,system-ui,sans-serif;color:#4ade80;font-variant-numeric:tabular-nums}',
      '.gu-cubuk{height:12px;border-radius:99px;overflow:hidden;background:var(--cizgi,#1e2630)}.gu-cubuk>span{display:block;height:100%;width:0;background:linear-gradient(90deg,#15803d,#4ade80);transition:width .3s}.gu-cubuk.belirsiz>span{width:35%!important;animation:gu-kay 1.2s linear infinite}.gu-cubuk.hata>span{background:linear-gradient(90deg,#b91c1c,#f87171)}@keyframes gu-kay{0%{margin-left:-35%}100%{margin-left:100%}}',
      '.gu-mesaj{margin:8px 0 2px;min-height:18px}.gu-alt{display:flex;justify-content:space-between;gap:10px;color:var(--soluk,#6b7b8c);font-size:11px;font-variant-numeric:tabular-nums;min-height:15px}.gu-alt-dosya{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
      '.gu-uyari{margin:10px 0 0;padding:9px 11px;border-left:3px solid #f59e0b;background:rgba(245,158,11,.1);font-size:12px}.gu-uyari button{margin-top:7px}',
      '.gu-adimlar{margin-top:12px;border:1px solid var(--cizgi,#1e2630);border-radius:5px;max-height:220px;overflow:auto;background:rgba(0,0,0,.18);font-size:12px}.gu-adim{display:grid;grid-template-columns:62px 16px 1fr;gap:6px;padding:4px 9px;border-bottom:1px solid rgba(255,255,255,.04)}.gu-adim:last-child{border-bottom:0}.gu-adim-saat{color:var(--soluk,#6b7b8c);font-variant-numeric:tabular-nums}.gu-adim-ikon.tamam{color:#4ade80}.gu-adim-ikon.hata{color:#f87171}.gu-adim-ikon.calisiyor{color:#fbbf24}.gu-adim-bos{padding:9px;color:var(--soluk,#6b7b8c)}',
      '.gu-not{margin:10px 0 0;white-space:pre-wrap;color:var(--soluk,#6b7b8c);max-height:80px;overflow:auto}.gu-guvenlik{font-size:11px;color:var(--soluk,#6b7b8c);margin:10px 0 0}',
      '.gu-dugmeler{display:flex;justify-content:flex-end;flex-wrap:wrap;gap:8px;padding:11px 18px 14px;border-top:1px solid var(--cizgi,#1e2630)}.gu-dugme{min-width:120px;min-height:34px;padding:7px 12px;border:1px solid var(--cizgi,#1e2630);border-radius:4px;background:var(--dugme-arka,#141a21);color:var(--metin,#cfd8e3);cursor:pointer;font:700 11px Segoe UI,system-ui,sans-serif;letter-spacing:.055em}.gu-dugme:hover:not(:disabled){filter:brightness(1.16)}.gu-dugme.ana{background:#15803d;border-color:#22c55e;color:#fff}.gu-dugme:disabled{opacity:.45;cursor:not-allowed}',
      '@media(max-width:520px){.gu-surumler{grid-template-columns:1fr}.gu-dugme{flex:1}}'
    ].join('');
    document.head.appendChild(s);
  }

  function domKur(){
    stilEkle();
    if (!document.getElementById('guncellemeSerit')){
      const serit = el('div');
      serit.id = 'guncellemeSerit';
      serit.setAttribute('role', 'button');
      serit.setAttribute('tabindex', '0');
      serit.innerHTML = '<span class="gu-serit-dolgu"></span><i class="fa-solid fa-cloud-arrow-down" aria-hidden="true"></i><span class="gu-serit-metin"></span><i class="fa-solid fa-chevron-right" aria-hidden="true"></i>';
      serit.addEventListener('click', pencereAc);
      serit.addEventListener('keydown', function(e){ if (e.key === 'Enter' || e.key === ' '){ e.preventDefault(); pencereAc(); } });
      const ust = document.getElementById('ustBar');
      document.body.insertBefore(serit, ust || document.body.firstChild);
    }
    if (document.getElementById('gu-perde')) return;
    const perde = el('div');
    perde.id = 'gu-perde';
    perde.setAttribute('aria-hidden', 'true');
    perde.innerHTML =
      '<section id="gu-pencere" role="dialog" aria-modal="true" aria-labelledby="gu-baslik">' +
        '<header class="gu-baslik"><i class="fa-solid fa-shield-halved" aria-hidden="true"></i><span id="gu-baslik">YAZILIM GÜNCELLEMESİ</span><button class="gu-kapat" type="button" aria-label="Kapat">×</button></header>' +
        '<div class="gu-icerik">' +
          '<div class="gu-surumler"><div class="gu-kutu"><span class="gu-etiket">KURULU SÜRÜM</span><span class="gu-deger" id="gu-mevcut">—</span></div><div class="gu-kutu"><span class="gu-etiket">HEDEF SÜRÜM</span><span class="gu-deger" id="gu-hedef">—</span></div></div>' +
          '<div class="gu-asama"><span class="gu-asama-ad" id="gu-asama">—</span><span class="gu-yuzde" id="gu-yuzde">0%</span></div>' +
          '<div class="gu-cubuk" id="gu-cubuk"><span></span></div>' +
          '<div class="gu-mesaj" id="gu-mesaj"></div>' +
          '<div class="gu-alt"><span class="gu-alt-dosya" id="gu-alt-sol"></span><span id="gu-alt-sag"></span></div>' +
          '<div class="gu-uyari" id="gu-uyari" hidden></div>' +
          '<div class="gu-adimlar" id="gu-adimlar"><div class="gu-adim-bos">Henüz adım yok.</div></div>' +
          '<div class="gu-not" id="gu-notlar" hidden></div>' +
          '<div class="gu-guvenlik">Yalnız imzalı manifest ve SHA-256 doğrulaması geçen değişen dosyalar indirilir; çalıştırılabilir kurulum indirilmez. Hata olursa değişiklikler geri alınır.</div>' +
        '</div>' +
        '<footer class="gu-dugmeler"><button id="gu-denetle" class="gu-dugme" type="button">TEKRAR DENETLE</button><button id="gu-kapat-alt" class="gu-dugme" type="button">KAPAT</button><button id="gu-guncelle" class="gu-dugme ana" type="button">GÜNCELLE VE YENİDEN BAŞLAT</button></footer>' +
      '</section>';
    document.body.appendChild(perde);
    const kapat = function(){ perde.classList.remove('aktif'); perde.setAttribute('aria-hidden', 'true'); };
    perde.addEventListener('click', function(e){ if (e.target === perde) kapat(); });
    perde.querySelector('.gu-kapat').addEventListener('click', kapat);
    perde.querySelector('#gu-kapat-alt').addEventListener('click', kapat);
    perde.querySelector('#gu-denetle').addEventListener('click', function(){ if (wsGonder('guncelleme_denete')) hizliBaslat(); });
    perde.querySelector('#gu-guncelle').addEventListener('click', function(){
      const onay = metin('guncellemeUygulaOnay', 'Değişen dosyalar indirilip kurulacak ve uygulama yeniden başlatılacak. Devam edilsin mi?');
      if (window.confirm(onay) && wsGonder('guncelleme_uygula')){ izlenenKimlik = null; hizliBaslat(); }
    });
  }

  function ilerlemeGecerli(d){
    const il = d && d.ilerleme;
    if (!il || typeof il !== 'object') return null;
    return il;
  }

  // Uygulama sureci (indirme/yerlestirme vb.) yuruyor mu?
  function uygulamaYuruyor(d){
    const il = ilerlemeGecerli(d);
    if (d && d.asama === 'uygula_istendi') return true;
    if (!il || !il.etkin) return false;
    // bayat kayit (ör. gozetmen oldu) 10 dk'dan eskiyse sayma
    if (il.guncel_ts && Date.now() / 1000 - il.guncel_ts > 600) return false;
    return AKTIF_UYGULAMA.indexOf(il.asama) >= 0 || il.tetik === 'kullanici';
  }

  function adimlariCiz(liste, ekler){
    const kap = document.getElementById('gu-adimlar');
    if (!kap) return;
    const tum = (liste || []).concat(ekler || []);
    const altta = kap.scrollTop + kap.clientHeight >= kap.scrollHeight - 8;
    kap.textContent = '';
    if (!tum.length){ kap.appendChild(el('div', 'gu-adim-bos', 'Henüz adım yok.')); return; }
    tum.forEach(function(a, i){
      const satir = el('div', 'gu-adim');
      satir.appendChild(el('span', 'gu-adim-saat', saat(a.ts)));
      let durum = a.durum || 'tamam';
      // Ardindan baska adim gelmisse "suruyor" adimi tamamlanmistir.
      if (durum === 'calisiyor' && i < tum.length - 1) durum = 'tamam';
      satir.appendChild(el('span', 'gu-adim-ikon ' + durum, durum === 'hata' ? '✗' : (durum === 'calisiyor' ? '⟳' : '✓')));
      satir.appendChild(el('span', 'gu-adim-mesaj', a.mesaj || ''));
      kap.appendChild(satir);
    });
    if (altta || uygulamaYuruyor(sonDurum)) kap.scrollTop = kap.scrollHeight;
  }

  function ciz(){
    domKur();
    const d = sonDurum || {};
    const il = ilerlemeGecerli(d);
    const pencere = document.getElementById('gu-pencere');
    const cubuk = document.getElementById('gu-cubuk');
    const $ = function(id){ return document.getElementById(id); };
    let yuzde = 0, asamaAd = '—', mesaj = '', altSol = '', altSag = '', belirsiz = false, hata = false;
    const ekAdimlar = [];
    const kopuk = !wsAcik();

    const izliyor = il && (uygulamaYuruyor(d) || (izlenenKimlik && il.kimlik === izlenenKimlik) ||
                    (il.asama === 'tamam' && !onaylandiMi(il.kimlik) && il.bitis_ts && Date.now() / 1000 - il.bitis_ts < 300));

    if (izliyor){
      izlenenKimlik = il.kimlik;
      yuzde = Number(il.yuzde) || 0;
      asamaAd = ASAMA_AD[il.asama] || il.asama;
      mesaj = il.mesaj || '';
      hata = il.durum === 'hata' || il.asama === 'hata';
      if (il.toplam && il.asama !== 'tamam' && il.asama !== 'hata') altSol = (il.dosya ? il.dosya + '  ' : '') + '(' + (il.no || 0) + '/' + il.toplam + ')';
      if (il.bayt_toplam) altSag = mb(il.bayt) + ' / ' + mb(il.bayt_toplam) + ' MB';
      if (il.basla_ts) altSag += (altSag ? '  •  ' : '') + Math.max(0, Math.round((il.bitis_ts || Date.now() / 1000) - il.basla_ts)) + ' sn';
      // Uygulama yeniden baslarken baglanti kopar: bekleme sayaci
      if (kopuk && il.asama !== 'tamam' && il.asama !== 'hata'){
        if (!kopusBasi) kopusBasi = Date.now();
        belirsiz = true;
        asamaAd = 'Uygulama yeniden başlatılıyor';
        mesaj = 'Dosyalar yerleştiriliyor ve Merkez yeniden başlatılıyor; bağlantı bekleniyor (' + Math.round((Date.now() - kopusBasi) / 1000) + ' sn)…';
        ekAdimlar.push({ts: kopusBasi / 1000, durum: 'calisiyor', mesaj: 'Merkez bağlantısı kesildi (beklenen): yeniden bağlanılıyor… ' + Math.round((Date.now() - kopusBasi) / 1000) + ' sn'});
      } else if (kopusBasi){
        ekAdimlar.push({ts: kopusBasi / 1000, durum: 'tamam', mesaj: 'Merkez yeniden bağlandı (' + Math.round((Date.now() - kopusBasi) / 1000) + ' sn sonra)'});
      }
      if (il.asama === 'tamam'){
        if (d.mevcut_surum && il.hedef_surum && d.mevcut_surum === il.hedef_surum){
          if (!yenilemeZamani){
            yenilemeZamani = Date.now() + 4000;
          }
          const kalan = Math.max(0, Math.ceil((yenilemeZamani - Date.now()) / 1000));
          mesaj = (il.mesaj || 'Güncelleme tamamlandı') + ' — arayüz yeni sürümle ' + kalan + ' sn içinde yenilenecek.';
          ekAdimlar.push({ts: Date.now() / 1000, durum: 'calisiyor', mesaj: 'Arayüz yeni sürümle yenileniyor (' + kalan + ' sn)'});
          if (Date.now() >= yenilemeZamani){ onayla(il.kimlik); location.reload(); return; }
        } else if (!kopuk){
          mesaj = (il.mesaj || '') + ' — Merkez yeni sürümle açılıyor…';
          belirsiz = true;
        }
      }
    } else if (d.asama === 'denetleniyor'){
      const dn = d.denetim || {};
      asamaAd = 'Güncelleme denetleniyor';
      yuzde = Number(dn.yuzde) || 5;
      mesaj = dn.mesaj || 'Sunucuya bağlanılıyor…';
    } else if (d.asama === 'uygula_istendi'){
      asamaAd = 'İstek iletildi'; yuzde = 1; belirsiz = true;
      mesaj = 'Güncelleme servisine istek iletildi; servis yanıtı bekleniyor…';
    } else if (d.hata){
      asamaAd = 'Hata'; hata = true; yuzde = 100; mesaj = d.hata;
    } else if (d.guncelleme_var){
      asamaAd = 'Yeni sürüm hazır'; yuzde = 0;
      mesaj = 'Sürüm ' + (d.hedef_surum || '—') + ' hazır — ' + (Number(d.dosya_sayisi) || 0) + ' dosya güncellenecek (' + mb(d.toplam) + ' MB).';
    } else if (d.asama === 'guncel'){
      asamaAd = 'Güncel'; yuzde = 100; mesaj = 'Yazılımınız güncel (' + (d.mevcut_surum || '—') + ').';
    } else if (!d.kontrol_edildi){
      asamaAd = kopuk ? 'Bağlantı bekleniyor' : 'Hazır'; belirsiz = kopuk;
      mesaj = kopuk ? 'Merkez bağlantısı bekleniyor…' : 'Denetim için "Tekrar Denetle"ye basın.';
    }
    if (!kopuk) kopusBasi = kopusBasi && izliyor && il && il.asama !== 'tamam' ? kopusBasi : 0;

    $('gu-mevcut').textContent = d.mevcut_surum || (il && il.mevcut_surum) || '—';
    $('gu-hedef').textContent = (il && izliyor && il.hedef_surum) || d.hedef_surum || d.mevcut_surum || '—';
    $('gu-asama').textContent = asamaAd;
    $('gu-yuzde').textContent = belirsiz ? '…' : (Math.round(yuzde) + '%');
    cubuk.classList.toggle('belirsiz', belirsiz);
    cubuk.classList.toggle('hata', hata);
    cubuk.firstElementChild.style.width = Math.max(0, Math.min(100, yuzde)) + '%';
    pencere.classList.toggle('hata', hata);
    $('gu-mesaj').textContent = mesaj;
    $('gu-alt-sol').textContent = altSol;
    $('gu-alt-sag').textContent = altSag;
    const notEl = $('gu-notlar');
    notEl.hidden = !d.notlar; notEl.textContent = d.notlar || '';
    adimlariCiz(izliyor ? il.adimlar : [], ekAdimlar);

    // Eski gozetmen uyarisi (ilerleme gostermez)
    const uyari = $('gu-uyari');
    if (!kopuk && d.kontrol_edildi !== undefined && d.gozetmen_guncel === false && !izliyor){
      uyari.hidden = false;
      uyari.textContent = '';
      uyari.appendChild(el('div', '', 'Arka plandaki güncelleme servisi eski sürümde çalışıyor; ayrıntılı ilerleme ancak servis bir kez yeniden başlatıldıktan sonra görünür.'));
      if (d.servis_yenilenebilir){
        const b = el('button', 'gu-dugme', 'GÜNCELLEME SERVİSİNİ YENİDEN BAŞLAT');
        b.type = 'button';
        b.addEventListener('click', function(){
          if (window.confirm('Merkez servisi yeniden başlatılacak (15-30 sn bağlantı kesilir). Devam edilsin mi?') && wsGonder('guncelleme_servis_yenile')){
            b.disabled = true; b.textContent = 'YENİDEN BAŞLATILIYOR…';
          }
        });
        uyari.appendChild(b);
      }
    } else {
      uyari.hidden = true;
    }

    const calisiyor = izliyor && il && il.asama !== 'tamam' && il.asama !== 'hata' && il.asama !== 'guncel';
    $('gu-guncelle').disabled = !d.guncelleme_var || calisiyor || d.asama === 'uygula_istendi' || d.asama === 'denetleniyor' || kopuk;
    $('gu-denetle').disabled = calisiyor || d.asama === 'denetleniyor' || kopuk;

    // Serit: yeni surum veya suren guncelleme
    const serit = document.getElementById('guncellemeSerit');
    const seritMetin = serit.querySelector('.gu-serit-metin');
    const dolgu = serit.querySelector('.gu-serit-dolgu');
    if (calisiyor){
      serit.classList.add('aktif');
      seritMetin.textContent = 'GÜNCELLENİYOR: ' + asamaAd.toLocaleUpperCase('tr-TR') + (belirsiz ? '' : ' — %' + Math.round(yuzde));
      dolgu.style.width = (belirsiz ? 100 : yuzde) + '%';
    } else if (d.guncelleme_var){
      serit.classList.add('aktif');
      seritMetin.textContent = 'YENİ SÜRÜM HAZIR: ' + (d.hedef_surum || '—') + ' — GÜNCELLE';
      dolgu.style.width = '0%';
    } else {
      serit.classList.remove('aktif');
    }
  }

  function pencereAc(){
    domKur(); ciz();
    const perde = document.getElementById('gu-perde');
    perde.classList.add('aktif');
    perde.setAttribute('aria-hidden', 'false');
  }
  function pencereAcikMi(){
    const p = document.getElementById('gu-perde');
    return !!(p && p.classList.contains('aktif'));
  }

  // Hizli yoklama: denetim/guncelleme surerken 600 ms; baglanti koptuysa
  // yine de ekrani (sayaci) tazeler, geri gelince durumu ister.
  function hizliBaslat(){
    if (hizliZaman) return;
    hizliZaman = window.setInterval(function(){
      if (!wsGonder('guncelleme_durum')) ciz();
      const d = sonDurum || {};
      const il = ilerlemeGecerli(d);
      const surer = d.asama === 'denetleniyor' || uygulamaYuruyor(d) ||
        (il && il.asama === 'tamam' && izlenenKimlik === il.kimlik && !onaylandiMi(il.kimlik)) || kopusBasi;
      if (!surer){ window.clearInterval(hizliZaman); hizliZaman = null; }
    }, 600);
  }

  window.guncellemeDurumIsle = function(zarf){
    sonDurum = (zarf && zarf.durum) ? zarf.durum : (zarf || {});
    const il = ilerlemeGecerli(sonDurum);
    // Otomatik ya da baska ekrandan baslatilan guncelleme: pencereyi kendiliginden ac
    if ((uygulamaYuruyor(sonDurum) && il && AKTIF_UYGULAMA.indexOf(il.asama) >= 0) ||
        (il && il.asama === 'tamam' && il.bitis_ts && Date.now() / 1000 - il.bitis_ts < 300 && !onaylandiMi(il.kimlik) &&
         sonDurum.mevcut_surum === il.hedef_surum)){
      if (!pencereAcikMi()) pencereAc();
      hizliBaslat();
    }
    if (sonDurum.asama === 'denetleniyor') hizliBaslat();
    ciz();
  };
  window.guncellemeSonucIsle = function(zarf){
    if (zarf && zarf.islem === 'servis' && zarf.bilgi){
      const m = document.getElementById('gu-mesaj');
      if (m) m.textContent = zarf.bilgi;
    }
    hizliBaslat();
    window.setTimeout(function(){ wsGonder('guncelleme_durum'); }, 80);
  };
  window.guncellemeDurumSor = function(){ wsGonder('guncelleme_durum'); };
  window.guncellemeDilTazele = function(){ ciz(); };
  window.guncellemePenceresiAc = function(){
    domKur();
    if (wsGonder('guncelleme_denete')) hizliBaslat();
    pencereAc();
  };
  document.addEventListener('keydown', function(e){
    if (e.key === 'Escape' && pencereAcikMi()) document.getElementById('gu-perde').classList.remove('aktif');
  });
  document.addEventListener('DOMContentLoaded', function(){
    domKur();
    // Yavas arka plan yoklamasi: otomatik guncellemeler de gorunsun
    window.setInterval(function(){ if (!hizliZaman) wsGonder('guncelleme_durum'); }, 4000);
    window.setTimeout(function(){ wsGonder('guncelleme_durum'); }, 1500);
  });
})();
