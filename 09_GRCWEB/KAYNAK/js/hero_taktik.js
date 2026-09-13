/* =====================================================================
   HERO TAKTIK ANIMASYONU
   ---------------------------------------------------------------------
   Tek <canvas> uzerinde:
     1) Ortografik izdusumle donen dunya (GERCEK kita sinirlari,
        js/kita_verisi.js -> window.GOKTUNGU_KITA)
     2) Meridyen / paralel izgarasi
     3) Turkiye uzerinde radar: donen tarama huzmesi + menzil halkalari
     4) Elmas bicimli dron ikonlari, yon gosteren burun cizgisi ve iz

   TASARIM KARARLARI
   - DOM'a yuzlerce oge eklemek yerine TEK canvas: 30+ hareketli oge
     DOM'da her karede yeniden duzen (layout) tetikler; canvas'ta
     tetiklemez.
   - Kure yaricapi CSS pikselinde olculur, devicePixelRatio ile
     olceklenir; retina ekranda bulanik cizgi olmaz.
   - Renkler CSS degiskenlerinden OKUNUR (--siyan/--kehribar/--vurgu).
     Sabit yazilsa tema degistiginde animasyon eski palette kalirdi.
   - `prefers-reduced-motion: reduce` -> hareket YOK, tek kare cizilir.
     Kullanicinin isletim sistemi tercihi kirilmaz.
   - Sekme arka plandayken (`visibilitychange`) dongu durur; bos sekme
     pil tuketmez.
   - IntersectionObserver: hero gorunmuyorsa cizim yapilmaz.
   ===================================================================== */
'use strict';

(function () {
  var TUVAL_ID = 'heroTuval';

  /* ---- Coğrafi sabitler -------------------------------------------- */
  // Radar mevzii: Turkiye'nin yaklasik cografi merkezi (Ankara guneyi).
  var RADAR_LAT = 39.0;
  var RADAR_LON = 35.0;

  /* ---- Ayarlar -----------------------------------------------------
     DONUS SOZLESMESI (v2.12.1 -- KRITIK):
     Kure SERBEST DONMEZ.  Once `donme` surekli 0->360 artiyordu; bunun
     sonucu olarak Turkiye zamanin ancak ~%40'inda on yuzde kaliyor,
     geri kalan surede radar mevzii ve TUM dronlar `gorunur:false`
     oldugu icin eliyor ve sahnede yalnizca bos bir kure kaliyordu.
     Ekran goruntusu Amerika onde iken alindiginda bu apacik goruldu.

     Cozum: kure, radar mevziini merkezde tutan bir taban aciya
     KILITLENIR ve bu tabanin etrafinda yavas SALINIM yapar.  Boylece
     "donen dunya" izlenimi korunur, harekat bolgesi HER ZAMAN gorunur.
     Salinim genligi, Turkiye'nin kure kenarina hic yaklasmayacagi
     sekilde secildi (+-16 derece). */
  // Mevziyi ekran merkezine getiren taban boylam ofseti.
  var TABAN_DONME = -35.0;     // = -RADAR_LON
  var SALINIM_GENLIK = 16;     // derece
  var SALINIM_SURE = 21000;    // ms -> tam salinim dongusu

  /* YAKINLASTIRMA (v2.12.3 -- KRITIK OLCEK KARARI)
     Kure tam olarak sahneye sigdirildiginda (yaricap = min(g,y)*0.42)
     Turkiye ekranda yalnizca ~35 px genisliginde kaliyor.  12 px'lik
     hedef cerceveleri bu alanda ZORUNLU olarak ust uste biner; dron
     yayilimini artirmak sorunu cozmedi (s4.png).  Ayrica radar menzili
     `yaricap*0.46` ~ 104 px, yani cografi olarak Turkiye'den kat kat
     buyuk -- olcek tutarsizdi.

     1.55 DENENDI VE GERI ALINDI: o olcekte kure hissi tamamen kayboldu,
     kita cizgileri taninmaz koseli parcalara dondu (s5.png) -- kullanici
     "izgara seklinde DUNYA" istemisti, bolgesel harita degil.

     Nihai denge: kure sahneyi neredeyse dolduracak kadar buyuk ama
     TAMAMI gorunur (0.60).  Mevzi merkeze tam oturtulmaz; yalnizca
     kismen (MEVZI_KAYMA) yukari tasinir, boylece Turkiye sahnenin ust
     ortasinda genis yer kaplar ve kurenin alt kavisi gorunur kalir. */
  var KURE_OLCEK = 0.60;
  var MEVZI_KAYMA = 0.55;      // mevzi merkezleme orani (0=yok, 1=tam)
  var RADAR_HIZI = 0.075;      // derece/ms -> ~4.8 s'de tam tur
  var HUZME_ACI = 46;          // tarama huzmesi acisi (derece)
  var IZ_UZUNLUK = 26;         // dron izinde tutulan nokta sayisi
  var DRON_SAYI = 5;

  /* ---- Durum ------------------------------------------------------- */
  var tuval, ctx, dpr = 1;
  var g = 0, y = 0;            // canvas CSS boyutu
  var merkezX = 0, merkezY = 0, yaricap = 0;
  /* OLCEK: ikon boyutlari SABIT PIKSEL yazilmamali.  Once dron govdesi
     5.4 px sabitti; 536 px'lik sahnede ikonlar noktaya donusuyor,
     kullanici "dronlar gorunmuyor" diyordu.  Artik tum ikon olculeri
     kure yaricapina oranlanir (`olcek`), boylece mobil (320 px) ve
     genis ekran (700 px) sahnede ayni gorsel agirlik korunur. */
  var olcek = 1;
  var donme = TABAN_DONME;     // dunya boylam ofseti (derece)
  var salinimT = 0;            // salinim fazi (ms)
  var radarAci = 0;            // radar huzmesi acisi (derece)
  var dronlar = [];
  var sonZaman = 0;
  var kare = null;
  var kosuyor = false;
  var azHareket = false;
  var renk = {};
  /* ---- Etkilesim (v2.12.1) ----------------------------------------
     Kullanici kureyi fare veya parmakla dondurebilir.

     `elleDonme`  : kullanicinin ekledigi boylam ofseti (derece)
     `elleEgim`   : kullanicinin ekledigi enlem egimi (derece, sinirli)
     `surukluyor` : etkin surukleme var mi
     `bosalma`    : birakildiktan sonra atalet hizi (derece/ms)

     Birakildiginda ofset SIFIRA geri yaslanir (`GERI_YASLANMA`), boylece
     radar mevzii her zaman gorunur kalir -- kullanicinin "radar
     Turkiye'nin ortasinda" istegi korunur. */
  var elleDonme = 0, elleEgim = 0;
  var surukluyor = false;
  var bosalmaX = 0, bosalmaY = 0;
  var sonPX = 0, sonPY = 0, sonPZaman = 0;
  var etkilesimVar = false;      // kullanici hic dokundu mu
  var ELLE_EGIM_SINIR = 30;      // derece: kutup otesine gecmeyi engeller
  /* YATAY SINIR (v2.12.1 -- kullanici istegiyle dengelendi)
     Serbest 360 derece dondurme denendi ve GERI ALINDI: 300 px'lik bir
     surukleme 96 derece cevirdiginde radar mevzii ve dronlar kurenin
     kenarina itiliyor, harekat bolgesi kayboluyordu (x_surukle.png).
     Kullanici "radar Turkiye'nin ortasinda etrafini algilasa" dedi;
     bu yuzden dondurme SINIRLI bir pencerede serbesttir. */
  var ELLE_DONME_SINIR = 45;     // derece
  var GERI_YASLANMA = 0.00055;   // 1/ms -> birakinca yavas merkeze doner
  var SURUKLE_DUYARLIK = 0.17;   // px -> derece
  // Hero gorus alaninda mi.  `visibilitychange` isleyicisi bunu okur;
  // isleyici icinde tanimlanirsa `var` yukari cekilse bile degeri
  // `undefined` olur ve sekmeye donuldugunde animasyon BASLAMAZ.
  var gorunurdeMi = true;

  /* ---- Yardimcilar ------------------------------------------------- */

  function cssRenk(ad, yedek) {
    try {
      var d = getComputedStyle(document.documentElement)
        .getPropertyValue(ad).trim();
      return d || yedek;
    } catch (e) { return yedek; }
  }

  // '#5cc8ff' | 'rgb(a,b,c)' -> {r,g,b}
  function ayir(s) {
    s = (s || '').trim();
    if (s.charAt(0) === '#') {
      if (s.length === 4) {
        return { r: parseInt(s[1] + s[1], 16),
                 g: parseInt(s[2] + s[2], 16),
                 b: parseInt(s[3] + s[3], 16) };
      }
      return { r: parseInt(s.substr(1, 2), 16),
               g: parseInt(s.substr(3, 2), 16),
               b: parseInt(s.substr(5, 2), 16) };
    }
    var m = s.match(/[\d.]+/g);
    if (m && m.length >= 3) {
      return { r: +m[0], g: +m[1], b: +m[2] };
    }
    return { r: 92, g: 200, b: 255 };
  }

  function rgba(c, a) {
    return 'rgba(' + c.r + ',' + c.g + ',' + c.b + ',' + a + ')';
  }

  function renkleriOku() {
    renk.siyan = ayir(cssRenk('--siyan', '#5cc8ff'));
    renk.kehribar = ayir(cssRenk('--kehribar', '#f2b24a'));
    renk.vurgu = ayir(cssRenk('--vurgu', '#b91c1c'));
    // Izgara ve kita cizgisi siyandan turetilir; ayri degisken yok.
    renk.izgara = renk.siyan;
  }

  /* ---- Ortografik izdusum -----------------------------------------
     lon/lat (derece) -> ekran kordinati.  Kurenin GORUNMEYEN yuzundeki
     noktalar icin `gorunur:false` doner; cagiran taraf cizgiyi keser.
     Egim (tilt) ile kuzey yarimkure one bakar: Turkiye ve Avrupa
     ziyaretcinin ilgi alani.                                          */
  var EGIM = 22 * Math.PI / 180;
  var sinEgim = Math.sin(EGIM), cosEgim = Math.cos(EGIM);
  /* Etkin egim = taban EGIM + kullanicinin dikey suruklemesi.
     `sinEgim`/`cosEgim` SABIT kalir (merkezY hesabi ve mevzi
     yerlesimi bunlara dayanir); izdusum ise her karede guncellenen
     `sinEtkin`/`cosEtkin` kullanir. */
  var sinEtkin = sinEgim, cosEtkin = cosEgim;

  function egimiTazele() {
    var e = EGIM + elleEgim * Math.PI / 180;
    sinEtkin = Math.sin(e);
    cosEtkin = Math.cos(e);
  }

  function izdusum(lon, lat) {
    var l = (lon + donme) * Math.PI / 180;
    var f = lat * Math.PI / 180;
    var cosF = Math.cos(f);
    // Kure uzerinde birim vektor
    var x = cosF * Math.sin(l);
    var yy = Math.sin(f);
    var z = cosF * Math.cos(l);
    // X ekseni etrafinda egim (kullanici suruklemesi dahil)
    var y2 = yy * cosEtkin - z * sinEtkin;
    var z2 = yy * sinEtkin + z * cosEtkin;
    return {
      x: merkezX + x * yaricap,
      y: merkezY - y2 * yaricap,
      gorunur: z2 > 0,
      z: z2
    };
  }

  /* ---- Dronlar ----------------------------------------------------
     Her dron kure uzerinde bir buyuk daire yayinda ilerler.  Basit
     "lon/lat'i sabit hizla artir" yaklasimi kutuplara yakin yerlerde
     gorsel olarak hizlanir; bunu onlemek icin hiz cos(lat) ile
     olceklenir.                                                       */
  function dronlariKur() {
    dronlar = [];
    // Mevziye gore dagilim: ikisi Turkiye cevresinde devriye, ucu
    // daha genis yayda.  Sabit tohum yok -- her yuklemede hafif farkli
    // olmasi canli izlenim verir, ama menzil bilincli sinirlandirildi.
    /* YAYILIM (v2.12.2): once bes dron 9.5 derece yaricapa hapsedilmisti;
       ikonlar ust uste biniyor, sahnede tek bir kume gibi gorunuyorlardi
       (acik tema ekran goruntusunde apacik).  Artik her dron kendi
       DEVRIYE MERKEZI ve yaricapi ile ayri bir sektorde ucar; boylece
       ikonlar birbirine girmez ve bazilari radar menzilinin DISINDA
       kalir -- huzme onlari taradikca temas parlamasi anlam kazanir. */
    var kur = [
      { lat: 40.4, lon: 30.0, yon: 74,  hiz: 0.0060, tip: 'vtol',
        mLat: 40.6, mLon: 29.4, mYar: 4.4 },
      { lat: 37.0, lon: 39.6, yon: 318, hiz: 0.0052, tip: 'multi',
        mLat: 37.2, mLon: 40.2, mYar: 4.0 },
      { lat: 42.4, lon: 41.0, yon: 128, hiz: 0.0068, tip: 'kanat',
        mLat: 42.0, mLon: 41.6, mYar: 4.8 },
      { lat: 35.4, lon: 30.2, yon: 22,  hiz: 0.0056, tip: 'vtol',
        mLat: 35.2, mLon: 30.0, mYar: 4.2 },
      { lat: 39.2, lon: 35.4, yon: 244, hiz: 0.0064, tip: 'kanat',
        mLat: 39.0, mLon: 35.0, mYar: 3.2 }
    ];
    for (var i = 0; i < DRON_SAYI && i < kur.length; i++) {
      var d = kur[i];
      dronlar.push({
        lat: d.lat, lon: d.lon, yon: d.yon, hiz: d.hiz, tip: d.tip,
        mLat: d.mLat, mLon: d.mLon, mYar: d.mYar,
        iz: [],
        // Devriye: yon yavasca degisir, dron kavis cizer.
        donus: (i % 2 === 0 ? 1 : -1) * (0.010 + i * 0.0024)
      });
    }
  }

  function dronlariIlerlet(dt) {
    for (var i = 0; i < dronlar.length; i++) {
      var d = dronlar[i];
      d.yon = (d.yon + d.donus * dt + 360) % 360;
      var r = d.yon * Math.PI / 180;
      var cosLat = Math.max(0.25, Math.cos(d.lat * Math.PI / 180));
      // Kuzey = +lat, dogu = +lon.  Boylam adimi cos(lat) ile bolunur:
      // yuksek enlemde ayni mesafe daha buyuk boylam farki demektir.
      d.lat += Math.cos(r) * d.hiz * dt;
      d.lon += Math.sin(r) * d.hiz * dt / cosLat;
      // KENDI devriye merkezi cevresinde tut (ortak mevzi degil):
      // ortak merkez kullanildiginda bes dron ayni kucuk alana
      // toplaniyor ve ikonlar ust uste biniyordu.
      var dLat = d.lat - d.mLat, dLon = (d.lon - d.mLon) * cosLat;
      if (Math.sqrt(dLat * dLat + dLon * dLon) > d.mYar) {
        var hedef = Math.atan2(-dLon, -dLat) * 180 / Math.PI;
        var fark = ((hedef - d.yon + 540) % 360) - 180;
        // 0.06 idi: donus cok yavas, dron sinirdan tasip geri gelirken
        // uzun bir dogru cizgi olusturuyordu.  0.10 daha sikca kavis.
        d.yon = (d.yon + fark * 0.10 + 360) % 360;
      }
      d.iz.push([d.lon, d.lat]);
      if (d.iz.length > IZ_UZUNLUK) d.iz.shift();
    }
  }

  /* ---- Cizim ------------------------------------------------------- */

  function tuvaliOlcekle() {
    var kap = tuval.parentNode;
    var g2 = kap.clientWidth;
    var y2 = kap.clientHeight;
    if (!g2 || !y2) return false;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    g = g2; y = y2;
    tuval.width = Math.round(g * dpr);
    tuval.height = Math.round(y * dpr);
    tuval.style.width = g + 'px';
    tuval.style.height = y + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    /* v2.12.1 -- TAM BOYUT KURE
       Serit artik genis-alcak (or. 1600x620).  `min(g,y)` kullanmak
       kureyi seridin YUKSEKLIGINE hapsediyor ve genis ekranda kure
       kucuk kaliyordu.  Kullanici "dunya tam boyut gorunmeli" dedi:
       yaricap YUKSEKLIGE gore hesaplanir ve kure seridi dikeyde
       doldurur; yatayda zaten fazlasiyla yer var.

       Yaricap yuksekligin yarisi kadardir; mevzi kaymasi asagida
       SINIRLANIR, boylece kurenin alt/ust kavisi seritten tasmaz. */
    yaricap = y * 0.47;
    // Mevzi, egim uygulandiktan sonra kure merkezinden `mevziY*yaricap`
    // kadar YUKARIDA cikar.  merkezY bu kadar asagi kaydirilirsa mevzi
    // tam ortaya oturur; MEVZI_KAYMA ile kismen uygulanir.
    merkezX = g * 0.5;
    var fRad = RADAR_LAT * Math.PI / 180;
    /* KUSUR (v2.12.0): bu degisken `y2` adiyla tanimlanmisti ve
       fonksiyonun basindaki `var y2 = kap.clientHeight` degerini
       EZIYORDU.  `var` fonksiyon kapsamli oldugu icin ikinci tanim
       ayni degiskeni yeniden atiyor; merkezY hesabi dogru calisiyor
       gorunse de kabin yuksekligi bu noktadan sonra kaybediliyordu.
       Ad `mevziY` olarak ayristirildi. */
    var mevziY = Math.sin(fRad) * cosEgim - Math.cos(fRad) * sinEgim;
    /* Kayma, kurenin serit icinde kalacagi tavanla sinirlanir:
       merkezY - yaricap >= 0  ve  merkezY + yaricap <= y.
       yaricap = y/2 oldugundan tavan pratikte 0'a yakindir; bu yuzden
       kayma yalnizca artakalan bosluk kadar uygulanir. */
    var istenen = mevziY * yaricap * MEVZI_KAYMA;
    var tavan = Math.max(0, y * 0.5 - yaricap);
    if (istenen > tavan) istenen = tavan;
    if (istenen < -tavan) istenen = -tavan;
    merkezY = y * 0.5 + istenen;
    // Ikon olcegi kure YARICAPINA oranlanir: serit genisledikce
    // ikonlar da buyumeli, yoksa 1600 px'lik sahnede noktaya doner.
    olcek = Math.max(0.82, Math.min(1.6, yaricap / 240));
    return true;
  }

  function kureCiz() {
    // Ic dolgu: mevzi cevresi hafif aydinlik, kenarlara dogru koyu.
    // Kure sahneden buyuk oldugu icin gradyan MEVZI merkezli kurulur.
    // Gradyan kurenin GERCEK merkezine ve yaricapina baglanir; onceki
    // `min(g,y)` temeli genis seritte kureden bagimsiz kaliyor ve
    // aydinlanma kurenin disina tasiyordu.
    var gr = ctx.createRadialGradient(
      merkezX, merkezY, yaricap * 0.08,
      merkezX, merkezY, yaricap * 1.02);
    gr.addColorStop(0, rgba(renk.siyan, 0.11));
    gr.addColorStop(0.6, rgba(renk.siyan, 0.045));
    gr.addColorStop(1, rgba(renk.siyan, 0.012));
    ctx.beginPath();
    ctx.arc(merkezX, merkezY, yaricap, 0, Math.PI * 2);
    ctx.fillStyle = gr;
    ctx.fill();

    // Kenar cizgisi (uzay ufku).  Kure sahneden buyuk oldugunda bu
    // cember ekran disinda kalir; ctx.arc zaten kirpilir.
    ctx.beginPath();
    ctx.arc(merkezX, merkezY, yaricap, 0, Math.PI * 2);
    ctx.strokeStyle = rgba(renk.siyan, 0.30);
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  function izgaraCiz() {
    ctx.lineWidth = 1;
    // 0.11 idi: izgara ekranda GORUNMUYORDU.  Kullanicinin istedigi
    // "arka planda izgara seklinde dunya" izlenimi icin meridyen ve
    // paraleller ayirt edilebilir olmali.  Karsitlik olcumu bu ogeyi
    // gormedigi icin kusur sessizce gecmisti.
    // FAZ15-IZGARA-HIYERARSI: .20 -> .26.  Arka plandaki kare
    // izgara zayiflatildigi icin kurenin kendi meridyen/paralel
    // agi one cikarilabilir; dunya artik sahnenin ana ogesi.
    ctx.strokeStyle = rgba(renk.izgara, 0.26);

    var i, lat, lon, ilk, p;

    // Paraleller (15 derece: 30 cok seyrek, 10 asiri yogundu)
    for (lat = -75; lat <= 75; lat += 15) {
      ctx.beginPath();
      ilk = true;
      for (lon = -180; lon <= 180; lon += 4) {
        p = izdusum(lon, lat);
        if (!p.gorunur) { ilk = true; continue; }
        if (ilk) { ctx.moveTo(p.x, p.y); ilk = false; }
        else ctx.lineTo(p.x, p.y);
      }
      ctx.stroke();
    }

    // Meridyenler (15 derece arayla)
    for (lon = -180; lon < 180; lon += 15) {
      ctx.beginPath();
      ilk = true;
      for (lat = -90; lat <= 90; lat += 4) {
        p = izdusum(lon, lat);
        if (!p.gorunur) { ilk = true; continue; }
        if (ilk) { ctx.moveTo(p.x, p.y); ilk = false; }
        else ctx.lineTo(p.x, p.y);
      }
      ctx.stroke();
    }
  }

  function kitalarCiz() {
    var veri = window.GOKTUNGU_KITA;
    if (!veri || !veri.length) return;
    ctx.lineWidth = 1;
    // FAZ15-IZGARA-HIYERARSI: .46 -> .56.  Kita sinirlari sahnenin en
    // belirgin ogesi olmali; "dunya" izlenimini tasiyan katman bu.
    ctx.strokeStyle = rgba(renk.siyan, 0.56);
    for (var h = 0; h < veri.length; h++) {
      var halka = veri[h];
      ctx.beginPath();
      var ilk = true;
      for (var i = 0; i < halka.length; i++) {
        var p = izdusum(halka[i][0], halka[i][1]);
        if (!p.gorunur) { ilk = true; continue; }
        if (ilk) { ctx.moveTo(p.x, p.y); ilk = false; }
        else ctx.lineTo(p.x, p.y);
      }
      ctx.stroke();
    }
  }

  /* Radar: mevzi gorunur yuzdeyse menzil halkalari + tarama huzmesi.
     Huzme kure yuzeyine YAPISTIRILMAZ (izdusumde bu cok pahali olur);
     mevzi noktasi merkezli ekran duzleminde cizilir ve kurenin
     kenarina yaklastikca soluklastirilir -- boylece perspektif
     tutarsizligi gorsel olarak fark edilmez.                          */
  function radarCiz(zaman) {
    var m = izdusum(RADAR_LON, RADAR_LAT);
    if (!m.gorunur) return;

    // Kenara yakinsa soluklastir (z: 0=kenar, 1=tam karsi)
    var solukluk = Math.max(0, Math.min(1, (m.z - 0.12) / 0.5));
    if (solukluk <= 0) return;

    /* Menzil SAHNE boyutuna oranlanir (kure yaricapina degil): kure
       olcegi degistiginde menzil sahneden tasmasin. */
    var menzil = Math.min(g, y) * 0.235;

    ctx.save();
    ctx.translate(m.x, m.y);

    // Menzil halkalari
    ctx.lineWidth = 1;
    for (var i = 1; i <= 3; i++) {
      ctx.beginPath();
      ctx.arc(0, 0, menzil * i / 3, 0, Math.PI * 2);
      ctx.strokeStyle = rgba(renk.kehribar, 0.26 * solukluk);
      ctx.stroke();
    }

    // Genisleyen darbe halkasi (2.6 s dongu)
    var darbe = (zaman % 2600) / 2600;
    ctx.beginPath();
    ctx.arc(0, 0, menzil * darbe, 0, Math.PI * 2);
    ctx.strokeStyle = rgba(renk.kehribar, (1 - darbe) * 0.42 * solukluk);
    ctx.lineWidth = 1.4;
    ctx.stroke();

    // Tarama huzmesi: acisal gradyan yerine yelpaze dilim + kenar cizgi
    var a0 = radarAci * Math.PI / 180;
    var a1 = (radarAci - HUZME_ACI) * Math.PI / 180;
    var hg = ctx.createRadialGradient(0, 0, 0, 0, 0, menzil);
    hg.addColorStop(0, rgba(renk.kehribar, 0.34 * solukluk));
    hg.addColorStop(1, rgba(renk.kehribar, 0));
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.arc(0, 0, menzil, a1, a0);
    ctx.closePath();
    ctx.fillStyle = hg;
    ctx.fill();

    // Huzmenin on kenari (parlak cizgi)
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(Math.cos(a0) * menzil, Math.sin(a0) * menzil);
    ctx.strokeStyle = rgba(renk.kehribar, 0.62 * solukluk);
    ctx.lineWidth = 1.2;
    ctx.stroke();

    // Mevzi isareti: ucgen (yon gosterebilen ikon sozlesmesi)
    var mb = 7 * olcek;
    ctx.beginPath();
    ctx.moveTo(0, -mb);
    ctx.lineTo(mb * 0.84, mb * 0.58);
    ctx.lineTo(-mb * 0.84, mb * 0.58);
    ctx.closePath();
    ctx.fillStyle = rgba(renk.kehribar, 0.95 * solukluk);
    ctx.fill();
    // Mevzi halesi: ikonun kure dokusu icinde kaybolmamasi icin
    ctx.beginPath();
    ctx.arc(0, 0, mb * 1.7, 0, Math.PI * 2);
    ctx.strokeStyle = rgba(renk.kehribar, 0.5 * solukluk);
    ctx.lineWidth = 1.1;
    ctx.stroke();

    ctx.restore();
  }

  /* Dron ikonu: ELMAS govde + yon gosteren burun cizgisi.
     (Kullanici sozlesmesi: dron ikonu elmas, yonu belirten on cizgi)  */
  function dronCiz(d, zaman) {
    var p = izdusum(d.lon, d.lat);

    // Iz: gorunur parcalari cizgi olarak
    if (d.iz.length > 1) {
      ctx.lineWidth = 1.4 * olcek;
      for (var i = 1; i < d.iz.length; i++) {
        var a = izdusum(d.iz[i - 1][0], d.iz[i - 1][1]);
        var b = izdusum(d.iz[i][0], d.iz[i][1]);
        if (!a.gorunur || !b.gorunur) continue;
        // Izin sonu daha belirgin.  0.38 idi -- iz ekranda
        // secilemiyordu.
        var op = (i / d.iz.length) * 0.6;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = rgba(renk.siyan, op);
        ctx.stroke();
      }
    }

    if (!p.gorunur) return;
    var solukluk = Math.max(0, Math.min(1, (p.z - 0.06) / 0.4));
    if (solukluk <= 0) return;

    // Ekran duzleminde yon: kuzey yonunun izdusumdeki egimi hesaplanir,
    // boylece ikon kurenin donusuyle birlikte dogru bakar.
    var ileri = izdusum(
      d.lon + Math.sin(d.yon * Math.PI / 180) * 0.6,
      d.lat + Math.cos(d.yon * Math.PI / 180) * 0.6);
    var ekranAci = Math.atan2(ileri.y - p.y, ileri.x - p.x);

    ctx.save();
    ctx.translate(p.x, p.y);
    ctx.rotate(ekranAci);

    // Hedef kilidi: koseli cerceve (hedef ikonu izlenimi)
    var k = 12 * olcek;
    var kc = k * 0.34;            // kose parcasi uzunlugu
    // 0.42 opaklik + 1.1 px cizgi, kure dokusu uzerinde kayboluyordu
    // (s6.png: yalniz elmas govdeler goruluyor, cerceve yok).
    ctx.strokeStyle = rgba(renk.siyan, 0.72 * solukluk);
    ctx.lineWidth = 1.6 * olcek;
    ctx.beginPath();
    // Kose parcalari -- tam kare degil, koseli hedef isareti
    ctx.moveTo(-k, -k + kc); ctx.lineTo(-k, -k); ctx.lineTo(-k + kc, -k);
    ctx.moveTo(k - kc, -k);  ctx.lineTo(k, -k);  ctx.lineTo(k, -k + kc);
    ctx.moveTo(k, k - kc);   ctx.lineTo(k, k);   ctx.lineTo(k - kc, k);
    ctx.moveTo(-k + kc, k);  ctx.lineTo(-k, k);  ctx.lineTo(-k, k - kc);
    ctx.stroke();

    // Elmas govde
    var gb = 7.6 * olcek;         // govde yarim uzunlugu
    ctx.beginPath();
    ctx.moveTo(gb, 0);
    ctx.lineTo(0, gb * 0.63);
    ctx.lineTo(-gb, 0);
    ctx.lineTo(0, -gb * 0.63);
    ctx.closePath();
    ctx.fillStyle = rgba(renk.siyan, 0.97 * solukluk);
    ctx.fill();

    // Burun cizgisi (yon)
    ctx.beginPath();
    ctx.moveTo(gb, 0);
    ctx.lineTo(gb * 2.3, 0);
    ctx.strokeStyle = rgba(renk.siyan, 0.85 * solukluk);
    ctx.lineWidth = 1.5 * olcek;
    ctx.stroke();

    ctx.restore();
  }

  /* Radar huzmesi dronun uzerinden gectiginde kisa parlama.
     Acisal fark hesaplanir; huzme dronu tarayinca isaret buyur.       */
  function temasCiz() {
    var m = izdusum(RADAR_LON, RADAR_LAT);
    if (!m.gorunur) return;
    for (var i = 0; i < dronlar.length; i++) {
      var d = dronlar[i];
      var p = izdusum(d.lon, d.lat);
      if (!p.gorunur) continue;
      var aci = Math.atan2(p.y - m.y, p.x - m.x) * 180 / Math.PI;
      var fark = ((radarAci - aci + 540) % 360) - 180;
      if (fark >= -HUZME_ACI && fark <= 4) {
        // Huzme dronu simdi tarıyor
        var kuv = 1 - Math.abs(fark + HUZME_ACI / 2) / (HUZME_ACI / 2 + 4);
        kuv = Math.max(0, Math.min(1, kuv));
        ctx.beginPath();
        ctx.arc(p.x, p.y, (16 + kuv * 9) * olcek, 0, Math.PI * 2);
        ctx.strokeStyle = rgba(renk.kehribar, 0.62 * kuv);
        ctx.lineWidth = 1.4 * olcek;
        ctx.stroke();
      }
    }
  }

  function ciz(zaman) {
    ctx.clearRect(0, 0, g, y);
    kureCiz();
    izgaraCiz();
    kitalarCiz();
    radarCiz(zaman);
    for (var i = 0; i < dronlar.length; i++) dronCiz(dronlar[i], zaman);
    temasCiz();
  }

  function dongu(zaman) {
    if (!kosuyor) return;
    if (!sonZaman) sonZaman = zaman;
    var dt = Math.min(zaman - sonZaman, 60);   // sekme donusunde ziplama olmasin
    sonZaman = zaman;

    // Salinim: taban aci etrafinda sinus.  `donme`ye dogrudan artis
    // EKLENMEZ -- yoksa mevzi yine kurenin arkasina gecer.
    // Kullanici sahneyle etkilesime girdiyse otomatik salinim DURUR:
    // aksi halde kendi cevirdigi kure elinden kayiyor gibi olur.
    if (!etkilesimVar) {
      salinimT = (salinimT + dt) % SALINIM_SURE;
    }
    // Surukleme birakildiktan sonra atalet + merkeze geri yaslanma.
    if (!surukluyor) {
      if (bosalmaX || bosalmaY) {
        elleDonme += bosalmaX * dt;
        elleEgim += bosalmaY * dt;
        var sonum = Math.pow(0.9975, dt);
        bosalmaX *= sonum;
        bosalmaY *= sonum;
        if (Math.abs(bosalmaX) < 0.00004) bosalmaX = 0;
        if (Math.abs(bosalmaY) < 0.00004) bosalmaY = 0;
      }
      // Merkeze geri yaslanma (mevzi gorunur kalsin).
      var k = Math.min(1, GERI_YASLANMA * dt);
      elleDonme += (0 - elleDonme) * k;
      elleEgim += (0 - elleEgim) * k;
      if (Math.abs(elleDonme) < 0.02 && Math.abs(elleEgim) < 0.02 &&
          !bosalmaX && !bosalmaY && etkilesimVar) {
        // Tam merkeze oturdu: otomatik salinima geri don.
        elleDonme = 0; elleEgim = 0;
        etkilesimVar = false;
      }
    }
    if (elleEgim > ELLE_EGIM_SINIR) elleEgim = ELLE_EGIM_SINIR;
    if (elleEgim < -ELLE_EGIM_SINIR) elleEgim = -ELLE_EGIM_SINIR;
    if (elleDonme > ELLE_DONME_SINIR) { elleDonme = ELLE_DONME_SINIR; bosalmaX = 0; }
    if (elleDonme < -ELLE_DONME_SINIR) { elleDonme = -ELLE_DONME_SINIR; bosalmaX = 0; }
    egimiTazele();
    donme = TABAN_DONME + elleDonme +
      Math.sin(salinimT / SALINIM_SURE * Math.PI * 2) * SALINIM_GENLIK;
    radarAci = (radarAci + RADAR_HIZI * dt) % 360;
    dronlariIlerlet(dt);
    ciz(zaman);

    kare = window.requestAnimationFrame(dongu);
  }

  function basla() {
    if (kosuyor || azHareket) return;
    kosuyor = true;
    sonZaman = 0;
    kare = window.requestAnimationFrame(dongu);
  }

  function dur() {
    kosuyor = false;
    if (kare) window.cancelAnimationFrame(kare);
    kare = null;
  }

  function kur() {
    tuval = document.getElementById(TUVAL_ID);
    if (!tuval || !tuval.getContext) return;
    ctx = tuval.getContext('2d');
    if (!ctx) return;

    renkleriOku();
    dronlariKur();
    if (!tuvaliOlcekle()) return;

    var mq = window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)');
    azHareket = !!(mq && mq.matches);

    if (azHareket) {
      // Hareket istenmiyor: tek kare ciz, dongu baslatma.
      dronlariIlerlet(0);
      ciz(0);
    } else {
      basla();
    }

    /* ---- Surukleme ile dondurme (v2.12.1) -------------------------
       Pointer Events kullanilir: fare, kalem ve dokunma ayni kod yolu.

       DOKUNMATIK KARARI: `touch-action:pan-y` CSS'te verilir, boylece
       DIKEY kaydirma parmakla calismaya devam eder ve yalniz YATAY
       hareket kureyi cevirir.  Aksi halde kullanici sahne uzerinde
       sayfayi kaydiramaz -- mobilde ciddi kullanilabilirlik kusuru.

       Az-hareket tercihinde surukleme yine calisir ama animasyon
       dongusu kosmadigi icin her olayda tek kare cizilir. */
    var etkinPointer = null;

    function pointerBasla(o) {
      // Yalniz birincil dugme (fare) ya da tek parmak
      if (o.pointerType === 'mouse' && o.button !== 0) return;
      if (etkinPointer !== null) return;
      etkinPointer = o.pointerId;
      surukluyor = true;
      etkilesimVar = true;
      bosalmaX = 0; bosalmaY = 0;
      sonPX = o.clientX; sonPY = o.clientY;
      sonPZaman = (o.timeStamp || Date.now());
      try { tuval.setPointerCapture(o.pointerId); } catch (e) {}
      tuval.style.cursor = 'grabbing';
    }

    function pointerHareket(o) {
      if (!surukluyor || o.pointerId !== etkinPointer) return;
      var dx = o.clientX - sonPX;
      var dy = o.clientY - sonPY;
      var dzaman = (o.timeStamp || Date.now()) - sonPZaman;
      sonPX = o.clientX; sonPY = o.clientY;
      sonPZaman = (o.timeStamp || Date.now());

      elleDonme += dx * SURUKLE_DUYARLIK;
      if (elleDonme > ELLE_DONME_SINIR) elleDonme = ELLE_DONME_SINIR;
      if (elleDonme < -ELLE_DONME_SINIR) elleDonme = -ELLE_DONME_SINIR;
      // Dikeyde ters isaret: yukari suruklemek kuzeyi one getirir.
      elleEgim += dy * SURUKLE_DUYARLIK * 0.55;
      if (elleEgim > ELLE_EGIM_SINIR) elleEgim = ELLE_EGIM_SINIR;
      if (elleEgim < -ELLE_EGIM_SINIR) elleEgim = -ELLE_EGIM_SINIR;

      // Atalet icin anlik hiz (derece/ms)
      if (dzaman > 0 && dzaman < 120) {
        bosalmaX = (dx * SURUKLE_DUYARLIK) / dzaman;
        bosalmaY = (dy * SURUKLE_DUYARLIK * 0.55) / dzaman;
      }
      if (azHareket) { egimiTazele(); ciz(0); }
    }

    function pointerBitir(o) {
      if (o.pointerId !== etkinPointer) return;
      surukluyor = false;
      etkinPointer = null;
      try { tuval.releasePointerCapture(o.pointerId); } catch (e) {}
      tuval.style.cursor = 'grab';
      // Atalet hizini makul bir tavana sinirla
      var tavan = 0.09;
      if (bosalmaX > tavan) bosalmaX = tavan;
      if (bosalmaX < -tavan) bosalmaX = -tavan;
      if (bosalmaY > tavan) bosalmaY = tavan;
      if (bosalmaY < -tavan) bosalmaY = -tavan;
    }

    if (window.PointerEvent) {
      tuval.style.cursor = 'grab';
      tuval.addEventListener('pointerdown', pointerBasla);
      tuval.addEventListener('pointermove', pointerHareket);
      tuval.addEventListener('pointerup', pointerBitir);
      tuval.addEventListener('pointercancel', pointerBitir);
      // Surukleme sirasinda metin secimi / goruntu surukleme olmasin
      tuval.addEventListener('dragstart', function (o) {
        o.preventDefault();
      });
    }

    // Boyut degisimi
    var zamanlayici = null;
    window.addEventListener('resize', function () {
      if (zamanlayici) clearTimeout(zamanlayici);
      zamanlayici = setTimeout(function () {
        if (tuvaliOlcekle() && azHareket) ciz(0);
      }, 160);
    });

    // Sekme arka plandayken cizim yapma
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) dur();
      else if (!azHareket && gorunurdeMi) basla();
    });

    // Hero gorunur degilse cizim yapma
    if (window.IntersectionObserver) {
      var io = new IntersectionObserver(function (girisler) {
        for (var i = 0; i < girisler.length; i++) {
          gorunurdeMi = girisler[i].isIntersecting;
        }
        if (!gorunurdeMi) dur();
        else if (!azHareket && !document.hidden) basla();
      }, { threshold: 0.02 });
      io.observe(tuval);
    }

    // Tema degisiminde renkleri yeniden oku.  Tema betigi
    // documentElement uzerindeki data-tema niteligini degistirir.
    if (window.MutationObserver) {
      new MutationObserver(function () {
        renkleriOku();
        if (azHareket) ciz(0);
      }).observe(document.documentElement,
        { attributes: true, attributeFilter: ['data-tema'] });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', kur);
  } else {
    kur();
  }
})();
