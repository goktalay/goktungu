/* =====================================================================
   GÖKTUNGU KÖPRÜ — yerel panel istemcisi

   Düzen: üst şerit + sol menü (kurum logosu + sunucu listesi) + ana alan
   (başlat/durdur üstte, konsol altta ve sürekli açık).

   Bağımlılık YOKTUR (React/Vue yok). Neden: köprü paketinin küçük ve
   çevrimdışı kurulabilir kalması gerekir; derleme adımı sahada elle
   yama uygulamayı imkânsız hale getirirdi.
   ===================================================================== */
'use strict';

var G = {
  jeton: null,            // CSRF başlığı için (oturum çerezde)
  durum: null,
  secili: null,           // seçili servis adı
  konsolSon: {},          // servis adı -> son okunan satır numarası
  konsolUcusta: {},       // servis adı -> yanıt bekleyen istek var mı
  konsolTur: {},          // servis adı -> tur sayacı (eski yanıtı atmak için)
  surumler: null,         // /api/surumler önbelleği
  logoDenendi: false,
  zamanlayici: null,
  konsolZaman: null,
  sureZaman: null,
  menuImza: ''
};

/* ------------------------------------------------------------------ ARAÇ */
function d(id){ return document.getElementById(id); }
function goster(e){ if(e) e.classList.remove('gizli'); }
function gizle(e){ if(e) e.classList.add('gizli'); }
function metin(e,v){ if(e) e.textContent = (v===null||v===undefined)?'':String(v); }

/** Kullanıcı verisini HTML'e gömerken kaçış: kurum ünvanında `<`
 *  bulunması yeterlidir; kaçış yapılmazsa arayüz bozulur (ve XSS
 *  yüzeyi açılır). */
function kacis(s){
  return String(s===null||s===undefined?'':s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}

function sureBicim(sn){
  sn = Math.max(0, Math.floor(sn||0));
  var s = sn%60, dk = Math.floor(sn/60)%60, st = Math.floor(sn/3600);
  var ik = function(n){ return String(n).padStart(2,'0'); };
  if(st>0) return st+':'+ik(dk)+':'+ik(s);
  return ik(dk)+':'+ik(s);
}

function zamanBicim(ts){
  if(!ts) return '—';
  try{ return new Date(ts*1000).toLocaleTimeString('tr-TR'); }
  catch(e){ return '—'; }
}

/* ------------------------------------------------------------------ AĞ */
function istek(yol, secenek){
  secenek = secenek || {};
  var b = { 'Content-Type':'application/json' };
  // CSRF: durum değiştiren isteklerde özel başlık zorunlu. Sunucu
  // yalnız başlığın VARLIĞINI arar; değeri gizli değildir.
  if(secenek.method === 'POST') b['X-Kopru-Jeton'] = G.jeton || '1';
  return fetch(yol, {
    method: secenek.method || 'GET',
    headers: b,
    credentials: 'same-origin',
    body: secenek.govde ? JSON.stringify(secenek.govde) : undefined
  }).then(function(y){
    return y.json().catch(function(){ return {}; }).then(function(v){
      if(!y.ok){
        var h = new Error(v.hata || ('Sunucu '+y.status));
        h.kod = y.status;
        throw h;
      }
      return v;
    });
  });
}

function hataGoster(e, mesaj){
  if(!e) return;
  metin(e, mesaj);
  goster(e);
}

/* ------------------------------------------------------------------ SAAT */
function saatYaz(){
  var t = new Date();
  var ik = function(n){ return String(n).padStart(2,'0'); };
  metin(d('saat'), ik(t.getHours())+':'+ik(t.getMinutes())+':'+ik(t.getSeconds()));
  var aylar = ['Ocak','Şubat','Mart','Nisan','Mayıs','Haziran','Temmuz',
               'Ağustos','Eylül','Ekim','Kasım','Aralık'];
  var gunler = ['Pazar','Pazartesi','Salı','Çarşamba','Perşembe','Cuma',
                'Cumartesi'];
  metin(d('tarih'), t.getDate()+' '+aylar[t.getMonth()]+' '+gunler[t.getDay()]);
}

/* ------------------------------------------------- KURULUM SİHİRBAZI */
/* v1.6.0 — Giriş ekranından ÖNCE çalışan ilk açılış sihirbazı.

   Köprü kimliği merkezde doğrulanır; varsayılan merkez GÖKTUNGU
   bulutudur. Kapalı devre kurulumda kullanıcının hesabı KENDİ Merkez
   Uygulamasındadır. Adres sorulmadan giriş denenirse şifre doğru olsa
   bile başarısız olur — kullanıcının çözemeyeceği bir kilit.        */

// Sihirbazın bir kez gösterildiğini izler: `durumCek()` 2 saniyede bir
// çalışır, bayrak olmazsa kullanıcı form doldururken ekran sürekli
// yeniden çizilir ve yazılan adres silinirdi.
var kurulumGosterildi = false;

function kurulumEkraniAc(v){
  if(kurulumGosterildi) return;
  kurulumGosterildi = true;
  gizle(d('girisEkran'));
  gizle(d('panelEkran'));
  goster(d('kurulumEkran'));
  metin(d('kurulumSurum'), (v && v.surum) || '—');
  // Uzak tarayicıda form doldurulup 403 alınmasın: sunucu bu işlemi
  // `_yerel_zorunlu()` ile korur, bunu kullanıcıya ÖNCEDEN söylüyoruz.
  if(v && v.yerel === false){
    goster(d('kurulumUzak'));
    d('kurulumDugme').disabled = true;
  }
}

function kurulumKur(){
  var kendi = d('kurKendi'), bulut = d('kurBulut');
  var alan = d('kurKendiAlan');
  var tazele = function(){
    if(kendi.checked) goster(alan); else gizle(alan);
  };
  kendi.addEventListener('change', tazele);
  bulut.addEventListener('change', tazele);

  d('kurulumForm').addEventListener('submit', function(ev){
    ev.preventDefault();
    var dg = d('kurulumDugme');
    gizle(d('kurulumHata'));

    var govde = { kendi: kendi.checked };
    if(kendi.checked){
      var ip = d('kurIp').value.trim();
      var ws = d('kurAdres').value.trim();
      var ht = d('kurHttp').value.trim();
      // Elle yazılan adres, IP alanından TÜRETİLENİN ÖNÜNE geçer:
      // gelişmiş bölümü açıp adres yazan kullanıcı bunu bilerek yapar.
      if(!ws || !ht){
        if(!ip){
          hataGoster(d('kurulumHata'),
            'Merkez sunucu adresini yazın (örnek: 127.0.0.1).');
          return;
        }
        // Yerel Merkez Uygulaması TLS kullanmaz: sertifika yoktur ve
        // kapalı devrede gerekmez. Bu yüzden ws:// + http:// ve
        // merkezin gerçek portları (8765 / 8000) türetilir.
        ws = ws || ('ws://' + ip + ':8765/kopru');
        ht = ht || ('http://' + ip + ':8000');
      }
      govde.merkez_adres = ws;
      govde.merkez_http = ht;
    }

    dg.disabled = true;
    metin(dg, 'Kaydediliyor...');
    istek('/api/kurulum/merkez', { method:'POST', govde:govde })
      .then(function(){
        gizle(d('kurulumEkran'));
        goster(d('girisEkran'));
        durumCek();
      }).catch(function(e){
        hataGoster(d('kurulumHata'), e.message);
      }).then(function(){
        dg.disabled = false;
        metin(dg, 'Kaydet ve Devam Et');
      });
  });
}

/* ------------------------------------------------------------------ GİRİŞ */
function girisKur(){
  d('girisForm').addEventListener('submit', function(ev){
    ev.preventDefault();
    var dg = d('girisDugme');
    gizle(d('girisHata'));
    dg.disabled = true;
    metin(dg, 'Doğrulanıyor...');
    istek('/api/giris', { method:'POST', govde:{
      eposta: d('gEposta').value.trim(), sifre: d('gSifre').value
    }}).then(function(v){
      G.jeton = v.jeton;
      d('gSifre').value = '';
      panelAc();
    }).catch(function(e){
      hataGoster(d('girisHata'), e.message);
    }).then(function(){
      dg.disabled = false;
      metin(dg, 'Giriş Yap');
    });
  });

  d('cikisDugme').addEventListener('click', function(){
    istek('/api/cikis', { method:'POST' }).then(function(){
      G.jeton = null; G.secili = null; G.surumler = null;
      G.logoDenendi = false; G.konsolSon = {}; G.menuImza = '';
      // Çıkışta sıfırlanır: aynı makinede BAŞKA bir firmanın yöneticisi
      // giriş yaparsa merkez seçimi ona da sorulmalıdır.
      merkezSecimGosterildi = false;
      gizle(d('merkezSecimPencere'));
      G.konsolUcusta = {}; G.konsolTur = {};
      if(G.zamanlayici) clearInterval(G.zamanlayici);
      if(G.konsolZaman) clearInterval(G.konsolZaman);
      if(G.sureZaman) clearInterval(G.sureZaman);
      var l = d('kurumLogo');
      if(l){ l.removeAttribute('src'); gizle(l); }
      goster(d('kurumLogoYok'));
      gizle(d('panelEkran'));
      goster(d('girisEkran'));
      durumCek();
    });
  });
}

function panelAc(){
  gizle(d('girisEkran'));
  goster(d('panelEkran'));
  surumleriCek();
  durumCek();
  if(G.zamanlayici) clearInterval(G.zamanlayici);
  // 2 sn: servis durumu için yeterince canlı, sunucuyu yormaz.
  G.zamanlayici = setInterval(durumCek, 2000);
  if(G.konsolZaman) clearInterval(G.konsolZaman);
  G.konsolZaman = setInterval(function(){ konsolCek(false); }, 1200);
  if(G.sureZaman) clearInterval(G.sureZaman);
  // Çalışma süresi sayacı: durum sorgusunu beklemeden saniyede bir akar.
  G.sureZaman = setInterval(function(){ if(G.durum) anaCiz(); }, 1000);
}

/* ------------------------------------------------------------------ DURUM */
function durumCek(){
  return istek('/api/durum').then(function(v){
    G.durum = v;
    metin(d('girisSurum'), v.surum);
    var k = v.kimlik || {};
    metin(d('girisKimlikDurum'),
      k.gizli_var ? ('Merkez kaydı: '+(k.ad||'var')) : 'Merkez kaydı yok');

    // v1.6.0 — EKRAN YÖNLENDİRMESİ (sıra önemlidir)
    //
    // 1) Oturum varsa panel: sihirbaz zaten tamamlanmış demektir.
    // 2) Oturum yok + kurulum gerekli -> sihirbaz.
    // 3) Oturum yok + kurulum tamam   -> giriş ekranı.
    //
    // 1. maddenin önce gelmesi şart: kurulum bayrağı herhangi bir
    // nedenle geri dönerse, çalışan bir oturumun üstüne sihirbaz
    // açılıp operatörü paneli kaybettirmesin.
    if(v.girisli){
      gizle(d('kurulumEkran'));
      if(d('panelEkran').classList.contains('gizli')) panelAc();
      panelCiz(v);
      return;
    }
    if(v.kurulum_gerekli){
      kurulumEkraniAc(v);
      return;
    }
    gizle(d('kurulumEkran'));
    gizle(d('panelEkran'));
    goster(d('girisEkran'));
  }).catch(function(e){
    if(e.kod === 401){
      gizle(d('panelEkran'));
      // Oturum düştüğünde sihirbaz AÇIKSA kapatılmaz: kullanıcı form
      // doldururken 401 gelirse yazılanlar silinirdi.
      if(d('kurulumEkran').classList.contains('gizli')){
        goster(d('girisEkran'));
      }
    }
  });
}

function panelCiz(v){
  // Surum denetimi ayri bir yerel API'den gelir; paket verisi bu durum
  // yanitina eklenmez. Bilesen kendi icinde istekleri sinirlar.
  if(window.guncellemeCek) window.guncellemeCek(false);
  ustCiz(v);
  kurumCiz(v);

  // v1.5.6 — `v.servisler` merkezden gelen firma yetkilerine göre
  // SUNUCUDA süzülmüş gelir (radar/gccdual/ai yetkisi yoksa listede
  // yoktur). Panel süzme yapmaz; süzgeci burada yinelemek iki ayrı
  // doğruluk kaynağı yaratırdı.
  var liste = v.servisler || [];
  // Seçili servis yetki geri alındığında listeden düşebilir; o hâlde
  // ana alan boş bir servise bakmaya devam eder ve panel donmuş
  // görünür. İlk geçerli servise düşülür.
  var seciliVar = false;
  for(var i=0;i<liste.length;i++){
    if(liste[i].ad === G.secili){ seciliVar = true; break; }
  }
  if(!seciliVar){
    G.secili = liste.length ? liste[0].ad : null;
    G.menuImza = '';
    G.konsolSon = {};
  }

  menuCiz(liste);
  anaCiz();
  ajanCiz(v.ajan || {}, v.kimlik || {});
  ayarCiz(v.ayar || {});
  merkezSecimDenetle(v);

  var a = (v.ayar||{}).merkez_http;
  if(a) d('merkezBag').href = a.replace(/\/$/,'') + '/app/';
}

function ustCiz(v){
  metin(d('kopruSurumDugme'), 'v' + (v.surum || '—'));
  var kul = v.kullanici || {}, kim = v.kimlik || {};
  var ad = ((kul.ad||'')+' '+(kul.soyad||'')).trim() || kul.eposta || '';
  metin(d('ustKullanici'), ad);
  var uk = d('ustKullanici');
  if(uk) uk.title = kul.eposta || '';
  metin(d('ustMakine'),
    kim.ad ? (kim.ad + (kim.makine ? ' · '+kim.makine : '')) : '');

  var a = v.ajan || {};
  var sinif = 'kotu', yazi = 'merkez: bağlı değil';
  if(a.bagli){ sinif = 'iyi'; yazi = 'merkez: bağlı'; }
  else if(a.calisiyor){ sinif = 'beklet'; yazi = 'merkez: bağlanıyor…'; }
  else if(!kim.gizli_var){ yazi = 'merkez: kayıt yok'; }
  var n = d('merkezNokta');
  if(n) n.className = 'nokta ' + sinif;
  metin(d('merkezMetin'), yazi);
}

function kurumCiz(v){
  var kul = v.kullanici || {};
  metin(d('kurumUnvan'), kul.firma_unvan || kul.firma_kisa_ad || '');
  // Logo merkezden vekil uçla gelir; yalnız bir kez denenir.
  if(G.logoDenendi) return;
  G.logoDenendi = true;
  var img = d('kurumLogo'), yok = d('kurumLogoYok');
  if(!img) return;
  img.onload = function(){ goster(img); gizle(yok); };
  img.onerror = function(){ gizle(img); goster(yok); };
  img.src = '/api/logo?z=' + Date.now();
}

function servisBul(ad){
  var l = (G.durum && G.durum.servisler) || [];
  for(var i=0;i<l.length;i++){ if(l[i].ad === ad) return l[i]; }
  return null;
}

/* -------------------------------------------------------------- SOL MENÜ */
function menuCiz(liste){
  var kap = d('menuListe');
  if(!kap) return;
  var html = liste.map(function(s){
    var nsinif = 'm-nokta';
    if(s.calisiyor) nsinif += ' iyi';
    else if(s.son_hata || s.cikis_kodu) nsinif += ' kotu';
    return '<li><button type="button" data-servis="'+kacis(s.ad)+'"'
      + (s.ad === G.secili ? ' class="etkin"' : '') + '>'
      + '<span class="'+nsinif+'"></span>'
      + '<span class="m-ad">'+kacis(s.baslik || s.ad)+'</span>'
      + '<span class="m-surum">v'+kacis(s.surum || '—')+'</span>'
      + '</button></li>';
  }).join('');
  // Aynı HTML'i yeniden yazmak, 2 sn'de bir odak/kaydırma kaybına yol
  // açar; bu yüzden yalnız değiştiğinde çizilir.
  if(G.menuImza === html) return;
  G.menuImza = html;
  kap.innerHTML = html;
  var dugmeler = kap.querySelectorAll('button[data-servis]');
  for(var i=0;i<dugmeler.length;i++){
    dugmeler[i].addEventListener('click', function(){
      servisSec(this.getAttribute('data-servis'));
    });
  }
}

function servisSec(ad){
  if(G.secili === ad) return;
  G.secili = ad;
  G.menuImza = '';
  var k = d('konsol');
  if(k) k.innerHTML = '<span class="bos">Konsol yükleniyor…</span>';
  menuCiz((G.durum && G.durum.servisler) || []);
  anaCiz();
  konsolCek(true);
}

/* -------------------------------------------------------------- ANA ALAN */
function anaCiz(){
  var s = servisBul(G.secili);
  var bd = d('baslatDugme'), dd = d('durdurDugme');
  if(!s){
    metin(d('servisBaslik'), '—');
    metin(d('servisAciklama'), '');
    if(bd) bd.disabled = true;
    if(dd) dd.disabled = true;
    return;
  }
  metin(d('servisBaslik'), s.baslik || s.ad);
  metin(d('servisAciklama'), s.aciklama || '');
  metin(d('servisSurumDugme'), 'v' + (s.surum || '—'));
  if(bd) bd.disabled = !!s.calisiyor;
  if(dd) dd.disabled = !s.calisiyor;

  if(!s.calisiyor && s.son_hata) hataGoster(d('servisHata'), s.son_hata);
  else gizle(d('servisHata'));

  var o = [];
  o.push(['Durum', s.calisiyor ? 'ÇALIŞIYOR' : 'DURDU',
          s.calisiyor ? 'iyi' : '']);
  o.push(['PID', s.pid ? String(s.pid) : '—', '']);
  o.push(['Çalışma süresi',
          s.calisiyor ? sureBicim((Date.now()/1000)-(s.baslama_ts||0)) : '—', '']);
  if(!s.calisiyor && s.cikis_kodu !== null && s.cikis_kodu !== undefined){
    o.push(['Çıkış kodu', String(s.cikis_kodu), s.cikis_kodu === 0 ? '' : 'kotu']);
  }
  o.push(['Konsol satırı', String(s.konsol_satir || 0), '']);
  var olc = s.olcumler || {};
  if(olc.dron_sayisi !== undefined)
    o.push(['Dron', String(olc.dron_sayisi), '']);
  if(olc.seri_port) o.push(['Seri port', String(olc.seri_port), '']);
  if(olc.bekleyen_telemetri !== undefined)
    o.push(['Kuyruk', String(olc.bekleyen_telemetri), '']);
  // 1.7.19: çoklu radar / M50 özetleri
  if(olc.radar_sayisi !== undefined)
    o.push(['Radar', (olc.bagli_radar_sayisi||0)+' / '+olc.radar_sayisi+' bağlı',
            (olc.bagli_radar_sayisi||0) ? 'iyi' : '']);
  if(olc.iz_sayisi !== undefined && olc.radar_sayisi !== undefined)
    o.push(['İz', String(olc.iz_sayisi), '']);
  if(olc.eo_sayisi !== undefined)
    o.push(['M50', (olc.bagli_eo_sayisi||0)+' / '+olc.eo_sayisi+' bağlı',
            (olc.bagli_eo_sayisi||0) ? 'iyi' : '']);

  var serit = d('olcumSerit');
  if(serit){
    serit.innerHTML = o.map(function(x){
      return '<div class="olcum"><div class="o-ad">'+kacis(x[0])+'</div>'
        + '<div class="o-deger '+x[2]+'">'+kacis(x[1])+'</div></div>';
    }).join('');
  }

  kanalCiz(s);
  m50YonetGorunurluk(s);
}

/* ---------------------------------------------------------- M50 YÖNETİMİ */
/* M50 SDK'sı tarayıcıya veya Merkez'e taşınmaz. Bu istemci yalnız yerel
 * Köprüdeki yetki/CSRF denetimli izinli komut ucunu kullanır. */
var M50 = { aktifBasili: null, sonDurum: null };

function m50YonetGorunurluk(s){
  var dugme = d('m50Yonet');
  if(!dugme) return;
  if(s && s.ad === 'm50') goster(dugme); else gizle(dugme);
}

function m50Hata(ileti){
  if(ileti) hataGoster(d('m50Hata'), ileti); else gizle(d('m50Hata'));
}

/* 1.7.19: çoklu M50 — her komut seçili cihaz kimliğini (eo_id) taşır. */
function m50CihazNo(){
  var e = d('m50CihazNo');
  var n = Number(e && e.value) || 1;
  return n > 0 ? Math.floor(n) : 1;
}

function m50Komut(eylem, veri){
  veri = veri || {};
  if(veri.eo_id === undefined) veri.eo_id = m50CihazNo();
  var eid = String(veri.eo_id);
  return istek('/api/m50/komut', {method:'POST', govde:{
    eylem: eylem, veri: veri
  }}).then(function(sonuc){
    sonuc = sonuc || {};
    // Durum paketinin üst düzeyi BİRİNCİL cihazındır; seçili cihazın
    // paketi eo_cihazlar[eo_id] altındadır (yoksa eski tek cihaz yolu).
    var c = (sonuc.eo_cihazlar && sonuc.eo_cihazlar[eid]) ? sonuc.eo_cihazlar[eid] : sonuc;
    if(c && c.m50_durum) m50DurumCiz(c.m50_durum, c.m50_video);
    return sonuc;
  });
}

function m50DurumCiz(durum, video){
  if(!durum) return;
  M50.sonDurum = durum;
  var olcum = [
    ['Cihaz', '#' + m50CihazNo(), ''],
    ['Bağlantı', durum.bagli ? 'BAĞLI' : (durum.durum || 'KAPALI').toUpperCase(), durum.bagli ? 'iyi' : ''],
    ['SDK', durum.sdk_hazir ? 'HAZIR' : 'YÜKLENMEDİ', durum.sdk_hazir ? 'iyi' : ''],
    ['Takip', (durum.takip && durum.takip.etkin) ? ('ETKİN — '+(durum.takip.kanal || '').toUpperCase()) : 'KAPALI', ''],
    ['Son işlem', durum.son_islem || '—', '']
  ];
  var serit = d('m50OlcumSerit');
  if(serit) serit.innerHTML = olcum.map(function(x){
    return '<div class="olcum"><div class="o-ad">'+kacis(x[0])+'</div><div class="o-deger '+x[2]+'">'+kacis(x[1])+'</div></div>';
  }).join('');
  var kontroller = d('m50KontrolKap');
  if(kontroller){ if(durum.bagli) goster(kontroller); else gizle(kontroller); }
  var baglan = d('m50Baglan'), kes = d('m50Kes');
  if(baglan) baglan.disabled = !!durum.bagli;
  if(kes) kes.disabled = !durum.bagli;
  if(durum.hata) m50Hata(durum.hata);
  // RTSP URI yalnız operatörün açık ayarından gelir; burada oynatılmaz veya merkeze yollanmaz.
  if(video && video.rtsp_gorunur !== undefined) {
    if(!d('m50RtspGorunur').value) d('m50RtspGorunur').value = video.rtsp_gorunur || '';
    if(!d('m50RtspTermal').value) d('m50RtspTermal').value = video.rtsp_termal || '';
  }
}

function m50AyarYukle(ayarlar){
  ayarlar = ayarlar || {};
  d('m50SdkDizin').value = ayarlar.m50_sdk_dizin || '';
  d('m50RtspGorunur').value = ayarlar.rtsp_gorunur || '';
  d('m50RtspTermal').value = ayarlar.rtsp_termal || '';
  // Parola ve oturum hiçbir zaman ayardan okunmaz; alan her açılışta boştur.
  d('m50Parola').value = '';
}

function m50DikdortgenOku(id, baslik){
  var parca = String(d(id).value || '').split(',').map(function(v){ return v.trim(); });
  if(parca.length !== 4 || parca.some(function(v){ return !/^-?\d+$/.test(v); })) {
    throw new Error(baslik + ' dört tam piksel değeriyle girilmelidir.');
  }
  return {sol:Number(parca[0]), ust:Number(parca[1]), sag:Number(parca[2]), alt:Number(parca[3])};
}

function m50BasiliGonder(tur, eylem, basili){
  var veri = tur === 'ptz'
    ? {yon:eylem, hiz:Number(d('m50PtzHiz').value), basili:!!basili}
    : {eylem:eylem, kanal:d('m50LensKanal').value, basili:!!basili};
  return m50Komut(tur, veri);
}

function m50BasiliBirak(){
  var etkin = M50.aktifBasili;
  M50.aktifBasili = null;
  if(!etkin) return;
  m50BasiliGonder(etkin.tur, etkin.eylem, false).catch(function(e){ m50Hata(e.message); });
}

function m50BasiliDugmeleriniKur(secici, tur){
  var dugmeler = document.querySelectorAll(secici);
  for(var i=0; i<dugmeler.length; i++) (function(dugme){
    var eylem = dugme.getAttribute(tur === 'ptz' ? 'data-m50-ptz' : 'data-m50-lens');
    dugme.addEventListener('pointerdown', function(ev){
      ev.preventDefault(); m50Hata('');
      if(tur === 'ptz' && eylem === 'dur') {
        m50BasiliBirak();
        m50BasiliGonder(tur, eylem, true).catch(function(e){ m50Hata(e.message); });
        return;
      }
      m50BasiliBirak();
      M50.aktifBasili = {tur:tur, eylem:eylem};
      m50BasiliGonder(tur, eylem, true).catch(function(e){ m50Hata(e.message); });
    });
  })(dugmeler[i]);
}

function m50Kur(){
  var pencere = d('m50Pencere');
  if(!pencere) return;
  function ac(){
    m50Hata(''); metin(d('m50AyarBilgi'), ''); d('m50Parola').value = '';
    goster(pencere);
    m50Komut('ayar_oku').then(function(v){
      m50AyarYukle(v.ayarlar); return m50Komut('durum');
    }).catch(function(e){ m50Hata(e.message); });
  }
  function kapat(){ m50BasiliBirak(); d('m50Parola').value = ''; gizle(pencere); }
  d('m50Yonet').addEventListener('click', ac);
  d('m50Kapat').addEventListener('click', kapat);
  // Cihaz no değişince o cihazın ayar ve durumu yüklenir.
  d('m50CihazNo').addEventListener('change', function(){
    m50BasiliBirak(); m50Hata('');
    m50Komut('ayar_oku').then(function(v){
      m50AyarYukle(v.ayarlar); return m50Komut('durum');
    }).catch(function(e){ m50Hata(e.message); });
  });
  pencere.addEventListener('click', function(ev){ if(ev.target === pencere) kapat(); });
  d('m50Form').addEventListener('submit', function(ev){ ev.preventDefault(); });
  d('m50AyarKaydet').addEventListener('click', function(){
    m50Hata(''); var dugme = d('m50AyarKaydet'); dugme.disabled = true;
    m50Komut('ayar_yaz', {m50_sdk_dizin:d('m50SdkDizin').value.trim(), rtsp_gorunur:d('m50RtspGorunur').value.trim(), rtsp_termal:d('m50RtspTermal').value.trim()})
      .then(function(v){ m50AyarYukle(v.ayarlar); metin(d('m50AyarBilgi'), 'Yerel ayarlar kaydedildi; parola kaydedilmedi.'); })
      .catch(function(e){ m50Hata(e.message); }).then(function(){ dugme.disabled = false; });
  });
  d('m50Baglan').addEventListener('click', function(){
    m50Hata(''); var dugme = d('m50Baglan'); dugme.disabled = true;
    m50Komut('baglan', {ip:d('m50Ip').value.trim(), port:Number(d('m50Port').value), kullanici:d('m50Kullanici').value.trim(), parola:d('m50Parola').value})
      .then(function(){ d('m50Parola').value = ''; }).catch(function(e){ m50Hata(e.message); })
      .then(function(){ if(!(M50.sonDurum && M50.sonDurum.bagli)) dugme.disabled = false; });
  });
  d('m50Kes').addEventListener('click', function(){ m50BasiliBirak(); m50Hata(''); m50Komut('kes').catch(function(e){ m50Hata(e.message); }); });
  d('m50AciGit').addEventListener('click', function(){
    m50Hata(''); m50Komut('aci_konumla', {azimut:Number(d('m50Azimut').value), egim:Number(d('m50Egim').value), hiz:Number(d('m50AciHiz').value)}).catch(function(e){ m50Hata(e.message); });
  });
  d('m50TakipSec').addEventListener('click', function(){
    try {
      m50Hata('');
      m50Komut('takip_sec', {kanal:d('m50TakipKanal').value, video_dikdortgen:m50DikdortgenOku('m50VideoDikdortgen', 'Video alanı'), secim:m50DikdortgenOku('m50SecimDikdortgen', 'Operatör seçimi')})
        .then(function(){ metin(d('m50AyarBilgi'), 'Manuel seçim onaylandı; takip için ayrıca başlatma onayı gerekir.'); })
        .catch(function(e){ m50Hata(e.message); });
    } catch(e) { m50Hata(e.message); }
  });
  d('m50TakipBaslat').addEventListener('click', function(){ m50Hata(''); m50Komut('takip_baslat', {kanal:d('m50TakipKanal').value, mod:d('m50TakipMod').value}).catch(function(e){ m50Hata(e.message); }); });
  d('m50TakipDurdur').addEventListener('click', function(){ m50Hata(''); m50Komut('takip_durdur', {kanal:d('m50TakipKanal').value}).catch(function(e){ m50Hata(e.message); }); });
  m50BasiliDugmeleriniKur('[data-m50-ptz]', 'ptz');
  m50BasiliDugmeleriniKur('[data-m50-lens]', 'lens');
  document.addEventListener('pointerup', m50BasiliBirak);
  document.addEventListener('pointercancel', m50BasiliBirak);
  document.addEventListener('keydown', function(ev){ if(ev.key === 'Escape') kapat(); });
}

/** Açık uçuş kanalları tablosu.
 *
 *  Yalnız Dron Sunucusu seçiliyken ve en az bir kanal varken görünür:
 *  boş bir tablo ekranda yer kaplayıp konsolu küçültürdü.
 */
function kanalCiz(s){
  var kap = d('kanalKap'), gov = d('kanalGovde');
  var liste = (G.durum && G.durum.kanallar) || [];
  if(!kap || !gov) return;
  if(!s || s.ad !== 'dron' || !liste.length){
    gizle(kap);
    gov.innerHTML = '';
    return;
  }
  goster(kap);
  metin(d('kanalSayi'), String(liste.length));
  gov.innerHTML = liste.map(function(k){
    var iyi = !!k.calisiyor;
    // Merkez kopukken durum "AKIYOR" göstermek yanıltıcı olur: veri
    // donanımdan akıyor ama merkeze ULAŞMIYOR. Pilot bunu ayırt
    // edebilmeli, yoksa merkezde uçuş kaydı olduğunu sanır.
    var dRozet = iyi ? (k.merkez_kesik ? 'YEREL KAYIT' : 'AKIYOR')
                     : 'KAPALI';
    var dSinif = iyi ? (k.merkez_kesik ? 'bekliyor' : 'iyi') : 'kotu';
    var kb = Number(k.kesinti_byte || 0);
    var dusen = Number(k.kesinti_dusen_byte || 0);
    var kMetin = kb ? bayt(kb) : '—';
    if(dusen) kMetin += ' (' + bayt(dusen) + ' kayıp)';
    return '<tr'+(k.merkez_kesik ? ' class="kanal-kesik"' : '')+'>'
      + '<td class="tek-satir">#'+kacis(k.kanal_id)+'</td>'
      + '<td class="tek-satir">'+kacis(k.etiket || k.tur || '—')+'</td>'
      + '<td><span class="kanal-durum '+dSinif+'">'
      +   kacis(dRozet) + '</span></td>'
      + '<td>'+kacis(bayt(k.giden_byte))+'</td>'
      + '<td>'+kacis(bayt(k.gelen_byte))+'</td>'
      + '<td'+(dusen ? ' class="kanal-kayip"' : '')+'>'
      +   kacis(kMetin) + '</td>'
      + '<td class="tek-satir">'+kacis(zamanBicim(k.son_veri_ts))+'</td>'
      + '</tr>'
      + (k.son_hata ? '<tr class="kanal-hata-satir"><td colspan="7">'
          + kacis(k.son_hata) + '</td></tr>' : '');
  }).join('');
}

/** Bayt sayısını okunur biçime çevirir: 1536 -> "1,5 KB". */
function bayt(n){
  n = Number(n||0);
  if(n < 1024) return String(n)+' B';
  if(n < 1024*1024) return (n/1024).toFixed(1).replace('.',',')+' KB';
  return (n/1048576).toFixed(1).replace('.',',')+' MB';
}

function servisEylem(eylem){
  var s = servisBul(G.secili);
  if(!s) return;
  var bd = d('baslatDugme'), dd = d('durdurDugme');
  if(bd) bd.disabled = true;
  if(dd) dd.disabled = true;
  gizle(d('servisHata'));
  istek('/api/servis/'+eylem, { method:'POST', govde:{ servis: s.ad } })
    .catch(function(hata){
      // Kullanıcı NEDEN başlamadığını görmeli.
      hataGoster(d('servisHata'), hata.message);
    }).then(function(){
      durumCek();
      konsolCek(false);
    });
}

/* --------------------------------------------------------------- KONSOL */
function konsolCek(zorla){
  if(!G.secili) return;
  var ad = G.secili;
  // YARIS KORUMASI: aynı servis için uçuşta bir istek varken yoklama
  // turu ikinci bir istek açmamalı. Açarsa iki yanıt da aynı satırları
  // döndürür (`sonrasi` henüz güncellenmemiştir) ve konsolda her satır
  // İKİ KEZ görünür. Zorla çağrısı (servis seçimi) bu kuralı aşar ve
  // uçuştaki yanıtı geçersiz kılar.
  if(!zorla && G.konsolUcusta[ad]) return;
  if(zorla) G.konsolSon[ad] = 0;
  var tur = (G.konsolTur[ad] = (G.konsolTur[ad] || 0) + 1);
  G.konsolUcusta[ad] = true;
  var son = G.konsolSon[ad] || 0;
  istek('/api/konsol?servis='+encodeURIComponent(ad)+'&sonrasi='+son)
    .then(function(v){
      if(G.secili !== ad) return;             // kullanıcı arada değiştirdi
      // Daha yeni bir tur başlamışsa bu yanıt BAYATTIR: eklenmesi
      // yinelenen satır üretir.
      if(G.konsolTur[ad] !== tur) return;
      var k = d('konsol');
      if(!k) return;
      var satirlar = v.satirlar || [];
      if(zorla){
        k.innerHTML = '';
        if(!satirlar.length){
          k.innerHTML = '<span class="bos">Konsol boş — sunucu henüz çıktı '
            + 'üretmedi.</span>';
          return;
        }
      }
      if(!satirlar.length) return;
      var bos = k.querySelector('.bos');
      if(bos) bos.remove();
      // Otomatik kaydırma YALNIZ kullanıcı en alttaysa yapılır; aksi
      // halde geçmişi okuyan kullanıcı her yeni satırda aşağı fırlatılır.
      var oto = d('otoKaydir');
      var altta = (k.scrollHeight - k.scrollTop - k.clientHeight) < 40;
      satirlar.forEach(function(s){
        // Sunucu `sonrasi` filtresini uygular; buradaki denetim ağ
        // yeniden denemesi gibi olağandışı durumlarda ikinci kalkandır.
        var no = s.no || 0;
        if(no && no <= (G.konsolSon[ad] || 0)) return;
        G.konsolSon[ad] = Math.max(G.konsolSon[ad]||0, no);
        var e = document.createElement('div');
        e.className = 'satir ' + sinifBul(s);
        e.textContent = s.metin;
        k.appendChild(e);
      });
      // Tarayıcı tarafında sınır: 1500 satır üstü DOM'u yavaşlatır.
      while(k.children.length > 1500) k.removeChild(k.firstChild);
      if(altta && (!oto || oto.checked)) k.scrollTop = k.scrollHeight;
    }).catch(function(){ /* geçici hata: sonraki turda yeniden */ })
    .then(function(){ G.konsolUcusta[ad] = false; });
}

function sinifBul(s){
  if(s.kaynak === 'sistem') return 'sistem';
  var m = String(s.metin||'');
  if(m.indexOf('[HATA]') >= 0) return 'hata';
  if(m.indexOf('[UYARI]') >= 0) return 'uyari';
  if(m.indexOf('[OK]') >= 0) return 'basari';
  return '';
}

/* ---------------------------------------------------------------- AJAN */
function ajanCiz(a, kim){
  var r = d('ajanEtiket');
  if(r){
    r.className = 'etiket';
    if(a.bagli){ r.classList.add('bagli'); metin(r, 'BAĞLI'); }
    else if(a.calisiyor){ r.classList.add('bekle'); metin(r, 'BAĞLANIYOR'); }
    else if(!kim.gizli_var){ metin(r, 'KAYIT YOK'); }
    else { r.classList.add('kopuk'); metin(r, 'KAPALI'); }
  }
  var bd = d('ajanBaslat'), dd = d('ajanDurdur');
  if(bd) bd.disabled = !kim.gizli_var || !!a.calisiyor;
  if(dd) dd.disabled = !a.calisiyor;
  metin(d('kayitAc'), kim.gizli_var ? 'KAYDI YENİLE' : 'MERKEZE KAYDET');
  var md = d('merkezDurum');
  if(md){
    md.title = 'Merkez: ' + (a.adres || '—')
      + '\nSon nabız: ' + zamanBicim(a.son_nabiz_ts)
      + '\nBekleyen kayıt: ' + (a.bekleyen_kayit || 0)
      + (a.son_hata ? ('\nSon hata: ' + a.son_hata) : '');
  }
}

function ajanKur(){
  d('ajanBaslat').addEventListener('click', function(){
    d('ajanBaslat').disabled = true;
    istek('/api/ajan/baslat', { method:'POST', govde:{} })
      .catch(function(e){ alert(e.message); }).then(durumCek);
  });
  d('ajanDurdur').addEventListener('click', function(){
    d('ajanDurdur').disabled = true;
    istek('/api/ajan/durdur', { method:'POST', govde:{} }).then(durumCek);
  });
}

/* --------------------------------------------------------- SÜRÜM DEFTERİ */
function surumleriCek(){
  return istek('/api/surumler').then(function(v){ G.surumler = v; })
    .catch(function(){ G.surumler = null; });
}

function gecmisHtml(kayitlar){
  if(!kayitlar || !kayitlar.length){
    return '<p class="kucuk sonuk">Bu bileşen için kayıtlı geçmiş yok.</p>';
  }
  return kayitlar.map(function(k){
    /* ALAN ADI UYUSMAZLIGI (v1.5.7'de giderildi): defterdeki kayitlar
       maddeleri "notlar" adiyla tasir (kopru/surumler.py, 35 kayit),
       burada ise yalniz "maddeler" okunuyordu. Sonuc: surum gecmisi
       penceresi acildiginda her kayit BOS gorunuyordu - yalniz surum
       ve tarih basligi cikiyor, degisiklik metni hic gelmiyordu.
       Kusur sessizdir: istek basarili, pencere aciliyor, hata yok.
       Iki ad da kabul edilir ki ileride hangisi kullanilirsa calissin. */
    var md = k.maddeler || k.notlar || [];
    return '<div class="gecmis-kayit"><div class="gecmis-ust">'
      + '<span class="gecmis-surum">v'+kacis(k.surum)+'</span>'
      + '<span class="gecmis-tarih">'+kacis(k.tarih||'')+'</span></div><ul>'
      + md.map(function(m){ return '<li>'+kacis(m)+'</li>'; }).join('')
      + '</ul></div>';
  }).join('');
}

/* Hakkinda kimlik basligi: surum defterinin USTUNDE bilesenin kimligini
   gosterir (ad, surum, tarih, firma, telif). Kullanici dort panelde de
   ayni "Hakkinda + surum defteri" yapisini gormek istedi; kopruda
   defter zaten vardi, eksik olan kimlik bolumuydu.

   OLCULEN SOZLESMELER (varsayim yok):
   - `defter()` yalniz {surum, gecmis} dondurur; TARIH ALANI YOKTUR.
     Bu yuzden tarih, gecmisin ILK kaydindan (en yeni) okunur.
   - Kurum logosu merkezde durur ve panele `/api/logo` VEKILI uzerinden
     gelir; kimlik nesnesinde logo adresi tasinmaz.
   - Firma unvani oturum kimliginde `firma_unvan` adiyla bulunur
     (panel.py:313 ile olculdu). */
function hakkindaHtml(ad, surum, gecmis){
  var kim = (G.durum || {}).kimlik || {};
  var tarih = (gecmis && gecmis.length) ? (gecmis[0].tarih || '') : '';
  var firma = kim.firma_unvan || '';
  // Logo yalniz oturum acikken vekilden gelir; yuklenemezse gizlenir
  // (kirik gorsel gostermek yerine).
  var logo = '<img class="hk-logo" src="/api/logo" alt=""'
    + ' onerror="this.style.display=&quot;none&quot;">';
  return '<div class="hakkinda">'
    + logo
    + '<div class="hk-ad">' + kacis(ad) + '</div>'
    + '<div class="hk-surum">Sürüm <b>' + kacis(surum || '—') + '</b>'
    + (tarih ? ' &middot; ' + kacis(tarih) : '') + '</div>'
    + (firma ? '<div class="hk-firma">' + kacis(firma) + '</div>' : '')
    + '<div class="hk-telif">© 2026 Gökkubbe Teknoloji Anonim Şirketi</div>'
    + '</div>';
}

function surumAc(tur){
  var yaz = function(){
    if(!G.surumler){
      metin(d('surumBaslik'), 'Hakkında');
      d('surumIcerik').innerHTML =
        '<p class="kucuk sonuk">Sürüm defteri okunamadı.</p>';
    }else if(tur === 'kopru'){
      var k = G.surumler.kopru || {};
      metin(d('surumBaslik'), 'Hakkında — Köprü Yazılımı');
      d('surumIcerik').innerHTML =
        hakkindaHtml('GÖKTUNGU Köprü Yazılımı', k.surum, k.gecmis)
        + gecmisHtml(k.gecmis);
    }else{
      var s = servisBul(G.secili);
      var sv = (G.surumler.servisler || {})[G.secili] || {};
      var ad = s ? (s.baslik || s.ad) : 'Sunucu';
      metin(d('surumBaslik'), 'Hakkında — ' + ad);
      d('surumIcerik').innerHTML =
        hakkindaHtml(ad, sv.surum, sv.gecmis) + gecmisHtml(sv.gecmis);
    }
    goster(d('surumPencere'));
  };
  if(G.surumler) yaz(); else surumleriCek().then(yaz);
}

/* ---------------------------------------------------------------- KAYIT */
function kayitKur(){
  function ac(){
    var kim = (G.durum||{}).kimlik || {};
    d('kAd').value = kim.ad || '';
    d('kYenile').checked = !!kim.gizli_var;
    d('kSifre').value = '';
    gizle(d('kayitHata'));
    goster(d('kayitPencere'));
    d('kSifre').focus();
  }
  function kapat(){ gizle(d('kayitPencere')); }
  d('kayitAc').addEventListener('click', ac);
  d('kayitKapat').addEventListener('click', kapat);
  d('kayitVazgec').addEventListener('click', kapat);
  d('kayitForm').addEventListener('submit', function(ev){
    ev.preventDefault();
    var dg = d('kayitOnay');
    dg.disabled = true;
    metin(dg, 'Kaydediliyor...');
    gizle(d('kayitHata'));
    istek('/api/merkez/kaydet', { method:'POST', govde:{
      sifre: d('kSifre').value,
      ad: d('kAd').value.trim(),
      yenile: d('kYenile').checked
    }}).then(function(){
      d('kSifre').value = '';
      kapat();
      durumCek();
    }).catch(function(e){
      hataGoster(d('kayitHata'), e.message);
    }).then(function(){
      dg.disabled = false;
      metin(dg, 'Kaydet');
    });
  });
}

/* ---------------------------------------------------------------- AYAR */
var ayarDokunuldu = false;

function ayarCiz(a){
  // Kullanıcı yazarken alanı EZMEMEK kritik: durum sorgusu 2 sn'de bir
  // çalışır, ezilirse kullanıcı adresi hiç yazamaz.
  if(ayarDokunuldu) return;
  d('ayMerkezAdres').value = a.merkez_adres || '';
  d('ayMerkezHttp').value = a.merkez_http || '';
  d('ayPanelPort').value = a.panel_port || '';
  d('ayPanelArayuz').value = a.panel_arayuz || '';
  d('aySertifika').checked = a.sertifika_dogrulama !== false;
  metin(d('ayVeriDizin'), a.veri_dizini || '—');
  metin(d('ayGunlukDizin'), a.gunluk_dizin || '—');

  // Açılışta otomatik başlat onayları servis listesinden üretilir;
  // servis eklendiğinde arayüzü elle güncellemek gerekmez.
  var kap = d('acilisOnaylar');
  if(!kap) return;
  var liste = (G.durum && G.durum.servisler) || [];
  var oto = a.acilista_baslat || {};
  var html = liste.map(function(s){
    return '<label class="onay"><input type="checkbox" data-acilis="'
      + kacis(s.ad) + '"' + (oto[s.ad] ? ' checked' : '') + '>'
      + '<span>'+kacis(s.baslik || s.ad)+'</span></label>';
  }).join('');
  if(kap.getAttribute('data-imza') === html) return;
  kap.setAttribute('data-imza', html);
  kap.innerHTML = html;
  var kutular = kap.querySelectorAll('[data-acilis]');
  for(var i=0;i<kutular.length;i++){
    kutular[i].addEventListener('change', function(){ ayarDokunuldu = true; });
  }
}

function ayarKur(){
  d('ayarDugme').addEventListener('click', function(){
    gizle(d('ayarHata'));
    metin(d('ayarBilgi'), '');
    goster(d('ayarPencere'));
  });
  d('ayarKapat').addEventListener('click', function(){
    gizle(d('ayarPencere'));
  });
  ['ayMerkezAdres','ayMerkezHttp','ayPanelPort','ayPanelArayuz',
   'aySertifika'].forEach(function(id){
    var o = d(id);
    if(o) o.addEventListener('input', function(){ ayarDokunuldu = true; });
  });
  d('ayarForm').addEventListener('submit', function(ev){
    ev.preventDefault();
    gizle(d('ayarHata'));
    var dg = d('ayarKaydet');
    dg.disabled = true;
    var acilis = {};
    var kutular = document.querySelectorAll('[data-acilis]');
    for(var i=0;i<kutular.length;i++){
      acilis[kutular[i].getAttribute('data-acilis')] = !!kutular[i].checked;
    }
    var port = parseInt(d('ayPanelPort').value, 10);
    istek('/api/ayar', { method:'POST', govde:{
      merkez_adres: d('ayMerkezAdres').value.trim(),
      merkez_http: d('ayMerkezHttp').value.trim(),
      panel_port: isNaN(port) ? undefined : port,
      panel_arayuz: d('ayPanelArayuz').value.trim(),
      sertifika_dogrulama: d('aySertifika').checked,
      acilista_baslat: acilis
    }}).then(function(v){
      if(v.ayar && v.ayar.hata){ hataGoster(d('ayarHata'), v.ayar.hata); return; }
      ayarDokunuldu = false;
      metin(d('ayarBilgi'),
        'Kaydedildi. Port ve arayüz değişikliği yeniden başlatmada etkin olur.');
      setTimeout(function(){ metin(d('ayarBilgi'), ''); }, 6000);
      durumCek();
    }).catch(function(e){
      hataGoster(d('ayarHata'), e.message);
    }).then(function(){ dg.disabled = false; });
  });
}

/* ------------------------------------------------------------- PENCERE */
function pencereKur(){
  d('surumKapat').addEventListener('click', function(){
    gizle(d('surumPencere'));
  });
  d('kopruSurumDugme').addEventListener('click', function(){ surumAc('kopru'); });
  d('servisSurumDugme').addEventListener('click', function(){ surumAc('servis'); });

  // Örtü boşluğuna tıklayınca pencere kapanır.
  ['surumPencere','kayitPencere','ayarPencere','m50Pencere'].forEach(function(id){
    var o = d(id);
    if(o) o.addEventListener('click', function(ev){
      if(ev.target === o) gizle(o);
    });
  });
  document.addEventListener('keydown', function(ev){
    if(ev.key === 'Escape'){
      ['surumPencere','kayitPencere','ayarPencere','m50Pencere'].forEach(function(id){
        gizle(d(id));
      });
    }
  });
}

/* ------------------------------------------------- MERKEZ SUNUCU SEÇİMİ */
/* Merkez Uygulama lisansı olan firmanın yöneticisine, giriş sonrası
 * bir kez sorulur. Koşullar SUNUCUDAN gelen veriye dayanır; arayuzde
 * uydurulmaz:
 *   1) kullanici.merkez_lisans === true  (merkez giriş yanıtı)
 *   2) kullanici.rol === 'yonetici'      (pilot altyapı seçemez)
 *   3) ayar.merkez_secim_yapildi === false (bir kez)
 * Aynı kurallar `/api/merkez/secim` ucunda YENİDEN denetlenir; buradaki
 * denetim yalnız görünürlük içindir.
 */
var merkezSecimGosterildi = false;

function merkezSecimGerekli(v){
  var kul = v.kullanici || {}, ayar = v.ayar || {};
  if(!kul.merkez_lisans) return false;
  if(String(kul.rol||'') !== 'yonetici') return false;
  if(ayar.merkez_secim_yapildi) return false;
  return true;
}

function merkezSecimDenetle(v){
  if(merkezSecimGosterildi) return;
  if(!merkezSecimGerekli(v)) return;
  merkezSecimGosterildi = true;
  var ayar = v.ayar || {};
  // Alanlar mevcut ayarla dolar: kullanıcı zaten kendi adresini
  // yazmışsa boş bir kutu görmesi "ayarım silindi mi" sorusuna yol açar.
  if(ayar.merkez_kendi){
    d('msKendi').checked = true;
    goster(d('msKendiAlan'));
    d('msAdres').value = ayar.merkez_adres || '';
    d('msHttp').value = ayar.merkez_http || '';
  }
  goster(d('merkezSecimPencere'));
}

function merkezSecimKur(){
  var kendi = d('msKendi'), bulut = d('msBulut');
  function alanGuncelle(){
    if(kendi && kendi.checked) goster(d('msKendiAlan'));
    else gizle(d('msKendiAlan'));
  }
  if(kendi) kendi.addEventListener('change', alanGuncelle);
  if(bulut) bulut.addEventListener('change', alanGuncelle);

  d('merkezSecimForm').addEventListener('submit', function(ev){
    ev.preventDefault();
    gizle(d('merkezSecimHata'));
    var dg = d('merkezSecimOnay');
    dg.disabled = true;
    metin(dg, 'Kaydediliyor...');
    var kendiMi = !!(kendi && kendi.checked);
    istek('/api/merkez/secim', { method:'POST', govde:{
      kendi: kendiMi,
      merkez_adres: kendiMi ? d('msAdres').value.trim() : '',
      merkez_http: kendiMi ? d('msHttp').value.trim() : ''
    }}).then(function(){
      gizle(d('merkezSecimPencere'));
      // Ayar değişti: `ayarCiz` bir sonraki durum sorgusunda alanları
      // tazeleyecek. `ayarDokunuldu` bayrağı sıfırlanmazsa Ayarlar
      // penceresi eski adresi göstermeye devam eder.
      ayarDokunuldu = false;
      durumCek();
    }).catch(function(e){
      // Başarısız kayıtta pencere KAPANMAZ: seçim yapılmadan devam
      // etmek telemetrinin yanlış merkeze akması demektir.
      hataGoster(d('merkezSecimHata'), e.message);
      merkezSecimGosterildi = true;
    }).then(function(){
      dg.disabled = false;
      metin(dg, 'Kaydet ve Devam Et');
    });
  });
}

/* ---------------------------------------------------------------- KONSOL */
function konsolKur(){
  d('baslatDugme').addEventListener('click', function(){ servisEylem('baslat'); });
  d('durdurDugme').addEventListener('click', function(){ servisEylem('durdur'); });
  d('konsolTemizle').addEventListener('click', function(){
    var k = d('konsol');
    if(k) k.innerHTML = '<span class="bos">Ekran temizlendi — yeni satırlar '
      + 'burada görünecek.</span>';
  });
}

/* ---------------------------------------------------------------- AÇILIŞ */
document.addEventListener('DOMContentLoaded', function(){
  // Kurulum sihirbazi ILK kurulur: `durumCek()` asagida cagrilir ve
  // kurulum gerekiyorsa sihirbaz ekranini acar. Dinleyicileri o andan
  // once baglamazsak formun gonderimi calismaz.
  kurulumKur();
  girisKur();
  ajanKur();
  kayitKur();
  ayarKur();
  m50Kur();
  merkezSecimKur();
  pencereKur();
  konsolKur();
  saatYaz();
  setInterval(saatYaz, 1000);
  durumCek();
});
