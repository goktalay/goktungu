// =================================================================
// GOKTUNGU - SANAL DRON (SITL) SIHIRBAZI            FAZ18 / v2.4.74
// -----------------------------------------------------------------
// Kullanici istegi:
//   "Sanal dron baslatacagimda play dugmesine bastigimda stil dosyasi
//    indirilmesi gerekiyor diyor, bunun yerine sanal dron olusturma
//    sihirbazi yapsak, once bana resimli olarak hangi dron tipi icin
//    sanal baslatacagimi sorsa, secince bir sonraki ekranda progressli
//    olarak download etsin, sonra dronun ismini ve diger parametreleri
//    sorsun, kaydet deyince sanal dron olussun. otomatik olarak play
//    yapsin"
//
// Uc adim:
//   1) Resimli arac tipi kartlari (SVG; harici dosya YOK)
//   2) SITL hazirlik + ilerlemeli indirme
//   3) Ad / adet / kalkis konumu -> KAYDET -> otomatik baslat
//
// TASARIM KARARI (kirilganligi en aza indirmek icin):
//   Mevcut `.bag-tur-sanal` girdileri (bagSanalTip / bagSanalAdet /
//   bagSanalEnlem / bagSanalBoylam) KALDIRILMAZ. Sihirbaz onlari GIZLI
//   VERI TASIYICISI olarak kullanir: karta tiklaninca `bagSanalTip`
//   degeri yazilir, 3. adimin girdileri dogrudan o alanlardir. Boylece
//   `bagKaydet()` govdesi (seri.js:272-289) HIC DEGISMEZ ve kaydetme
//   sozlesmesi bozulmaz. Sihirbaz yalnizca gorunumu yonetir.
//
// SUNUCU SOZLESMESI (Faz 18 Adim 3'te uygulandi, olculdu):
//   -> {tip:"sitl_durum", sanal_tip}
//   <- {tip:"sitl_durum", sanal_tip, hazir, yol, model, hata}
//   -> {tip:"sitl_indir", sanal_tip}
//   <- {tip:"sitl_indirme", durum:"basladi"|"ilerleme"|"bitti"|"hata",
//       sanal_tip, inen, toplam, hata}
// =================================================================
(function () {
  "use strict";

  // ---------------------------------------------------------------
  // Arac tipi katalogu
  // ---------------------------------------------------------------
  // `tip` degerleri sunucudaki TIP_ESLEME anahtarlariyla BIREBIR
  // ayni olmak zorundadir (sitl.py:59). Uyusmazsa sunucu
  // "Bilinmeyen tip" doner. Olculdu 2026-08-18: alti tip.
  //
  // `ikili` alani hangi SITL ikilisinin gerektigini soyler. Ayni
  // ikiliyi paylasan tipler tek indirmeyle hazir olur; sihirbazin
  // 2. adimi bu yuzden coklu pervaneli secimlerde aninda gecer.
  var KATALOG = [
    {tip: "multirotor",  ikili: "arducopter", ik: "sw-multirotor"},
    {tip: "hexarotor",   ikili: "arducopter", ik: "sw-hexarotor"},
    {tip: "helikopter",  ikili: "arducopter", ik: "sw-helikopter"},
    {tip: "sabit_kanat", ikili: "arduplane",  ik: "sw-sabitkanat"},
    {tip: "vtol",        ikili: "arduplane",  ik: "sw-vtol"},
    {tip: "interceptor", ikili: "arducopter", ik: "sw-interceptor"}
  ];

  // Kart gorselleri SVG olarak GOMULU uretilir: harici dosya indirme
  // yok (cevrimdisi kurulumda da calisir), tema degiskenlerine uyar
  // (`currentColor`), her cozunurlukte keskin kalir.
  var SVG = {
    "sw-multirotor":
      '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" ' +
      'stroke-width="2.4" stroke-linecap="round">' +
      '<circle cx="16" cy="16" r="8"/><circle cx="48" cy="16" r="8"/>' +
      '<circle cx="16" cy="48" r="8"/><circle cx="48" cy="48" r="8"/>' +
      '<path d="M21 21 L43 43 M43 21 L21 43"/>' +
      '<rect x="27" y="27" width="10" height="10" rx="2"/></svg>',
    "sw-hexarotor":
      '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" ' +
      'stroke-width="2.2" stroke-linecap="round">' +
      '<circle cx="32" cy="10" r="6"/><circle cx="32" cy="54" r="6"/>' +
      '<circle cx="13" cy="21" r="6"/><circle cx="51" cy="21" r="6"/>' +
      '<circle cx="13" cy="43" r="6"/><circle cx="51" cy="43" r="6"/>' +
      '<path d="M32 16 V26 M32 38 V48 M18 24 L27 29 M46 24 L37 29 ' +
      'M18 40 L27 35 M46 40 L37 35"/>' +
      '<circle cx="32" cy="32" r="6"/></svg>',
    "sw-helikopter":
      '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" ' +
      'stroke-width="2.4" stroke-linecap="round">' +
      '<path d="M8 14 H56"/><path d="M32 14 V24"/>' +
      '<path d="M20 24 H40 a8 8 0 0 1 8 8 v4 H20 z"/>' +
      '<path d="M48 32 H58"/><path d="M54 27 V37"/>' +
      '<path d="M22 40 H40 M24 36 V40 M38 36 V40"/></svg>',
    "sw-sabitkanat":
      '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" ' +
      'stroke-width="2.4" stroke-linecap="round">' +
      '<path d="M32 6 L38 26 H56 L38 34 L34 56 L30 34 L8 26 H26 z"/>' +
      '<path d="M32 6 V56"/></svg>',
    "sw-vtol":
      '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" ' +
      'stroke-width="2.2" stroke-linecap="round">' +
      '<path d="M32 8 L36 26 H54 L36 32 L33 54 L30 32 L10 26 H28 z"/>' +
      '<circle cx="14" cy="20" r="5"/><circle cx="50" cy="20" r="5"/>' +
      '<circle cx="14" cy="40" r="5"/><circle cx="50" cy="40" r="5"/>' +
      '</svg>',
    "sw-interceptor":
      '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" ' +
      'stroke-width="2.2" stroke-linecap="round">' +
      '<circle cx="14" cy="14" r="6"/><circle cx="50" cy="14" r="6"/>' +
      '<circle cx="14" cy="50" r="6"/><circle cx="50" cy="50" r="6"/>' +
      '<path d="M18 18 L27 27 M46 18 L37 27 M18 46 L27 37 ' +
      'M46 46 L37 37"/>' +
      '<circle cx="32" cy="32" r="9"/><path d="M32 20 V26 M32 38 V44 ' +
      'M20 32 H26 M38 32 H44"/></svg>'
  };

  // ---------------------------------------------------------------
  // Durum
  // ---------------------------------------------------------------
  var etkin = false;          // sihirbaz acik mi (SANAL turu + yeni kayit)
  var adim = 1;               // 1..3
  var secilenTip = "multirotor";
  var indirmeSuruyor = false;
  var hazirTipler = {};       // tip -> true (bu oturumda "hazir" olculdu)
  // Otomatik baslatma niyeti: kaydetten sonra listede beliren YENI
  // sanal kaydin kimligi bulunup baslatilir.
  var otoBaslat = null;       // null | {oncekiIdler: Set}

  function D_() {
    try { return (typeof D === "function") ? D() : {}; }
    catch (e) { return {}; }
  }
  function s(anahtar, yedek) {
    var t = D_();
    var d = t[anahtar];
    return (typeof d === "string" && d) ? d : yedek;
  }
  function el(id) { return document.getElementById(id); }
  // FAZ18-IS34-KAPSAM: `.bag-tur-sanal` sinifi DOM'da IKI yerde geciyor:
  // (a) panel listesindeki SANAL rozeti (seri.js, DOM'da ONCE gelir)
  // (b) modaldeki sanal form blogu (index.html)
  // `document.querySelector` ILK eslesmeyi dondurdugu icin sihirbaz
  // panel listesine kuruluyordu ve modal dugmesiz kaliyordu.
  // Arama MODAL KAPSAMINA daraltilir; panel rozetine dokunulmaz.
  function sanalFormBlok() {
    var kutu = document.getElementById("bagEkleKutu");
    if (!kutu) return null;
    return kutu.querySelector(".bag-tur-sanal");
  }

  function tipAd(tip) {
    return s("swTip_" + tip, tip);
  }
  function tipAciklama(tip) {
    return s("swTipAck_" + tip, "");
  }

  // ---------------------------------------------------------------
  // Iskelet kurulumu (bir kez)
  // ---------------------------------------------------------------
  // Sihirbaz isaretlemesi `.bag-tur-sanal` bloguna KOMSU olarak
  // eklenir; mevcut girdiler blogun icinde kalir ve gizlenir.
  var kuruldu = false;
  // FAZ18-IS34-KAPSAM: onceki surumde panel listesine kurulmus artik
  // sarmal DOM'da kalmis olabilir (liste yeniden cizildiginde
  // silinir, ama ilk yuklemede durabilir). Kurulumdan once
  // MODAL DISINDAKI her #swSarmal kaldirilir.
  function artikTemizle() {
    var kutu = document.getElementById("bagEkleKutu");
    var hepsi = document.querySelectorAll("#swSarmal, [id='swSarmal']");
    for (var i = 0; i < hepsi.length; i++) {
      if (kutu && kutu.contains(hepsi[i])) continue;
      if (hepsi[i].parentNode) hepsi[i].parentNode.removeChild(hepsi[i]);
    }
  }

  function kur() {
    if (kuruldu) return true;
    artikTemizle();
    var sanalBlok = sanalFormBlok();
    if (!sanalBlok) {
      // FAZ18-IS34-KAPSAM: modal blogu bulunamadi. Sessizce donmek yerine
      // iz birakilir; aksi halde sihirbaz hic acilmadigi halde
      // hicbir teshis verisi kalmaz (bu kusur boyle gizlenmisti).
      try { console.warn("[SITL-SIHIRBAZ] modal sanal blogu yok; sihirbaz devre disi, modal duz kipte kullanilabilir"); } catch (e) {}
      return false;
    }

    var sar = document.createElement("div");
    sar.id = "swSarmal";
    sar.style.display = "none";

    // --- Adim gostergesi ---
    var ad = document.createElement("div");
    ad.className = "sw-adimlar";
    ad.innerHTML =
      '<div class="sw-adim" data-adim="1"><span class="sw-adim-no">1</span>' +
      '<span class="sw-adim-ad" id="swAdimAd1"></span></div>' +
      '<div class="sw-adim-cizgi"></div>' +
      '<div class="sw-adim" data-adim="2"><span class="sw-adim-no">2</span>' +
      '<span class="sw-adim-ad" id="swAdimAd2"></span></div>' +
      '<div class="sw-adim-cizgi"></div>' +
      '<div class="sw-adim" data-adim="3"><span class="sw-adim-no">3</span>' +
      '<span class="sw-adim-ad" id="swAdimAd3"></span></div>';
    sar.appendChild(ad);

    // --- Adim 1: tip kartlari ---
    var a1 = document.createElement("div");
    a1.id = "swAdim1";
    a1.className = "sw-adim-govde";
    var ipucu1 = document.createElement("div");
    ipucu1.className = "sw-ipucu";
    ipucu1.id = "swIpucu1";
    a1.appendChild(ipucu1);
    var izgara = document.createElement("div");
    izgara.className = "sw-kartlar";
    izgara.id = "swKartlar";
    for (var i = 0; i < KATALOG.length; i++) {
      var k = KATALOG[i];
      var kart = document.createElement("button");
      kart.type = "button";
      kart.className = "sw-kart";
      kart.dataset.tip = k.tip;
      kart.innerHTML =
        '<span class="sw-kart-gorsel">' + (SVG[k.ik] || "") + '</span>' +
        '<span class="sw-kart-ad"></span>' +
        '<span class="sw-kart-ack"></span>';
      izgara.appendChild(kart);
    }
    a1.appendChild(izgara);
    sar.appendChild(a1);

    // --- Adim 2: hazirlik / indirme ---
    var a2 = document.createElement("div");
    a2.id = "swAdim2";
    a2.className = "sw-adim-govde";
    a2.style.display = "none";
    a2.innerHTML =
      '<div class="sw-durum-satir">' +
      '<i class="fa-solid fa-microchip sw-durum-ikon" id="swDurumIkon"></i>' +
      '<div class="sw-durum-metin">' +
      '<div class="sw-durum-baslik" id="swDurumBaslik"></div>' +
      '<div class="sw-durum-alt" id="swDurumAlt"></div>' +
      '</div></div>' +
      '<div class="sw-cubuk-cerceve" id="swCubukCerceve">' +
      '<div class="sw-cubuk" id="swCubuk"></div></div>' +
      '<div class="sw-cubuk-bilgi" id="swCubukBilgi"></div>' +
      '<button type="button" class="sw-yeniden" id="swYeniden"></button>';
    sar.appendChild(a2);

    // --- Adim 3: parametreler ---
    // Mevcut girdiler (bagAd, bagSanalAdet, bagSanalEnlem/Boylam)
    // BURAYA TASINMAZ: DOM'dan sokup takmak dinleyicileri ve
    // `seri.js`teki dogrudan referanslari kirma riski tasir. Bunun
    // yerine `.bag-tur-sanal` blogu 3. adimda GORUNUR kalir, 1-2.
    // adimlarda gizlenir. Ozet satiri buraya eklenir.
    var a3 = document.createElement("div");
    a3.id = "swAdim3";
    a3.className = "sw-adim-govde";
    a3.style.display = "none";
    a3.innerHTML =
      '<div class="sw-ozet" id="swOzet"></div>';
    sar.appendChild(a3);

    // --- Gezinme dugmeleri ---
    var gez = document.createElement("div");
    gez.className = "sw-gezinme";
    gez.innerHTML =
      '<button type="button" class="sw-geri" id="swGeri"></button>' +
      '<button type="button" class="sw-ileri" id="swIleri"></button>';
    sar.appendChild(gez);

    // Sihirbaz, sanal alan blogunun ONUNE eklenir: sirasiyla
    // adimlar -> (3. adimda) mevcut girdiler goruntulenir.
    sanalBlok.parentNode.insertBefore(sar, sanalBlok);

    // Dinleyiciler
    izgara.addEventListener("click", function (ev) {
      var b = ev.target.closest(".sw-kart");
      if (!b) return;
      tipSec(b.dataset.tip);
      // Kart secimi tek tiklamayla 2. adima gecirir: kullanici
      // "secince bir sonraki ekranda" dedi.
      adimaGit(2);
    });
    el("swGeri").addEventListener("click", function () {
      if (adim > 1) adimaGit(adim - 1);
    });
    el("swIleri").addEventListener("click", function () {
      if (adim < 3) adimaGit(adim + 1);
    });
    el("swYeniden").addEventListener("click", function () {
      indirmeBaslat();
    });

    kuruldu = true;
    return true;
  }

  // ---------------------------------------------------------------
  // Metinleri diller degistiginde de tazele
  // ---------------------------------------------------------------
  function metinleriYaz() {
    if (!kuruldu) return;
    el("swAdimAd1").textContent = s("swAdim1Ad", "Ara\u00e7 Tipi");
    el("swAdimAd2").textContent = s("swAdim2Ad", "Haz\u0131rl\u0131k");
    el("swAdimAd3").textContent = s("swAdim3Ad", "Parametreler");
    el("swIpucu1").textContent =
      s("swIpucu1", "Benzetilecek ara\u00e7 tipini se\u00e7in.");
    el("swGeri").textContent = s("swGeri", "GER\u0130");
    el("swIleri").textContent = s("swIleri", "\u0130LER\u0130");
    el("swYeniden").textContent =
      s("swYeniden", "YEN\u0130DEN DENE");
    var kartlar = el("swKartlar").querySelectorAll(".sw-kart");
    for (var i = 0; i < kartlar.length; i++) {
      var tip = kartlar[i].dataset.tip;
      kartlar[i].querySelector(".sw-kart-ad").textContent = tipAd(tip);
      kartlar[i].querySelector(".sw-kart-ack").textContent =
        tipAciklama(tip);
    }
    ozetYaz();
  }

  function tipSec(tip) {
    if (!tip) return;
    secilenTip = tip;
    // Gizli tasiyiciya yaz: bagKaydet() bu alani okur.
    var sec = el("bagSanalTip");
    if (sec) {
      // Katalog genisledi ama <select> uc secenekle geldi: eksik
      // secenekler eklenir, yoksa `.value` atamasi SESSIZCE bosa
      // duser ve kullanici multirotor secmis sayilir (v2.4.37'de
      // baud alaninda ayni sinif kusur olculmustu).
      var varMi = false;
      for (var i = 0; i < sec.options.length; i++)
        if (sec.options[i].value === tip) { varMi = true; break; }
      if (!varMi) {
        var o = document.createElement("option");
        o.value = tip;
        o.textContent = tipAd(tip);
        sec.appendChild(o);
      }
      sec.value = tip;
    }
    var kartlar = el("swKartlar").querySelectorAll(".sw-kart");
    for (var j = 0; j < kartlar.length; j++)
      kartlar[j].classList.toggle("secili",
                                  kartlar[j].dataset.tip === tip);
    ozetYaz();
  }

  function ozetYaz() {
    var o = el("swOzet");
    if (!o) return;
    o.innerHTML =
      '<span class="sw-ozet-etiket">' +
      s("swOzetTip", "Se\u00e7ilen tip") + '</span>' +
      '<span class="sw-ozet-deger">' + tipAd(secilenTip) + '</span>';
  }

  // ---------------------------------------------------------------
  // Adim gecisleri
  // ---------------------------------------------------------------
  function adimaGit(no) {
    if (!kuruldu) return;
    adim = no;
    el("swAdim1").style.display = (no === 1) ? "" : "none";
    el("swAdim2").style.display = (no === 2) ? "" : "none";
    el("swAdim3").style.display = (no === 3) ? "" : "none";
    // Mevcut sanal girdiler yalniz 3. adimda gorunur.
    var sanalBlok = sanalFormBlok();
    if (sanalBlok) sanalBlok.style.display = (no === 3) ? "" : "none";
    // Ad alani da 3. adima ait: 1-2. adimda gorunmesi kullaniciyi
    // henuz sirasi gelmemis bir alani doldurmaya cagirir.
    // `#bagAdAlan` yamayla verilen ACIK kimliktir; `parentNode`
    // uzerinden erismek isaretleme degisirse sessizce yanlis ogeyi
    // gizlerdi.
    var adAlan = el("bagAdAlan");
    if (adAlan) adAlan.style.display = (no === 3) ? "" : "none";
    // KAYDET yalniz son adimda anlamlidir.
    var kaydet = el("btnBagKaydet");
    if (kaydet) kaydet.style.display = (no === 3) ? "" : "none";

    var adimlar = document.querySelectorAll("#swSarmal .sw-adim");
    for (var i = 0; i < adimlar.length; i++) {
      var n = parseInt(adimlar[i].dataset.adim, 10);
      adimlar[i].classList.toggle("etkin", n === no);
      adimlar[i].classList.toggle("bitti", n < no);
    }
    // FAZ18-IS1-SIHIRBAZ-DUZELT: GERI solda / ILERI sagda. Gizleme yerine
    // `visibility` kullanilir; `display:none` olsaydi tek dugme
    // kalan adimlarda dugme yatay olarak KAYARDI.
    el("swGeri").style.visibility = (no === 1) ? "hidden" : "visible";
    el("swIleri").style.visibility = (no === 3) ? "hidden" : "visible";
    // 2. adimda ileri, hazirlik bitene kadar kapali kalir.
    if (no === 2) hazirlikBaslat();
    if (no === 3) ozetYaz();
  }

  // ---------------------------------------------------------------
  // Adim 2: hazirlik olcumu + indirme
  // ---------------------------------------------------------------
  function ileriKilit(kilitli) {
    var b = el("swIleri");
    if (!b) return;
    b.disabled = !!kilitli;
    b.classList.toggle("kilitli", !!kilitli);
  }
  // FAZ18-IS1-SIHIRBAZ-DUZELT: gorunurluk `hidden` NITELIGI ile yonetilir.
  // Olculen kusur: `.sw-yeniden` sinifinda `display:none` vardi;
  // `style.display = ""` satir ici bildirimi KALDIRIR ve sinif
  // kurali yeniden gecerli olur -> dugme hic gorunmezdi.
  function yenidenGoster(gorunur) {
    var b = el("swYeniden");
    if (!b) return;
    if (gorunur) b.removeAttribute("hidden");
    else b.setAttribute("hidden", "hidden");
    b.style.display = "";
  }
  function cubukGoster(gorunur) {
    var c = el("swCubukCerceve");
    if (c) c.style.display = gorunur ? "" : "none";
  }
  function durumYaz(baslik, alt, sinif, ikon) {
    var b = el("swDurumBaslik"), a = el("swDurumAlt"),
        i = el("swDurumIkon");
    if (b) b.textContent = baslik || "";
    if (a) a.textContent = alt || "";
    if (i) {
      i.className = "sw-durum-ikon fa-solid " +
        (ikon || "fa-microchip");
      i.classList.remove("iyi", "kotu", "bekle");
      if (sinif) i.classList.add(sinif);
    }
  }

  function hazirlikBaslat() {
    yenidenGoster(false);
    cubukGoster(false);
    el("swCubukBilgi").textContent = "";
    // Bu oturumda hazir oldugu olculen tip icin agi yeniden
    // yormayiz: ikili silinmedikce durum degismez.
    if (hazirTipler[secilenTip]) {
      hazirBildir();
      return;
    }
    // FAZ18-IS1-SIHIRBAZ-DUZELT: `window.ws` yerine canli cozucu.
    // Olculen kusur: `window.ws` yalniz `bagKaydet()` icinde
    // atanyordu; bu adimda TANIMSIZ oldugu icin baglanti acikken
    // "Sunucu baglantisi yok" yaziyordu.
    if (!window.wsAcikMi || !window.wsAcikMi()) {
      durumYaz(s("swSunucuYok", "Sunucu ba\u011flant\u0131s\u0131 yok"),
               s("swSunucuYokAlt",
                 "Ba\u011flant\u0131 kurulunca YENILE'ye bas\u0131n."),
               "kotu", "fa-plug-circle-xmark");
      ileriKilit(true);
      yenidenGoster(true);
      return;
    }
    durumYaz(s("swOlculuyor", "SITL kurulumu denetleniyor\u2026"),
             tipAd(secilenTip), "bekle", "fa-spinner");
    ileriKilit(true);
    try {
      // FAZ18-IS1B-GONDER-ZAMANASIMI: yanit gelmezse sonsuza bekleme.
      // Sunucu yaniti herhangi bir nedenle gelmezse (uc kusuru,
      // yetki reddi, agin kopmasi) kullanici donen carki izlemek
      // zorunda kalmamali. 12 saniye sonunda hata durumuna gecer
      // ve YENIDEN DENE dugmesi belirir.
      zamanAsimiKur();
      window.wsCanli().send(JSON.stringify({tip: "sitl_durum",
                                     sanal_tip: secilenTip}));
    } catch (e) {
      durumYaz(s("swOlcumHata", "Denetim yap\u0131lamad\u0131"),
               String(e), "kotu", "fa-triangle-exclamation");
      yenidenGoster(true);
    }
  }

  function hazirBildir() {
    hazirTipler[secilenTip] = true;
    durumYaz(s("swHazir", "SITL haz\u0131r"),
             s("swHazirAlt",
               "Benzetim dosyas\u0131 sistemde mevcut."),
             "iyi", "fa-circle-check");
    cubukGoster(false);
    yenidenGoster(false);
    ileriKilit(false);
    // Kullanici "secince bir sonraki ekranda" dedi: hazirsa bu adim
    // bir engel degil, bir onaydir. Kisa bir gecikmeyle 3. adima
    // gecilir; gecikme kullanicinin onayi gormesini saglar.
    setTimeout(function () {
      if (etkin && adim === 2 && hazirTipler[secilenTip])
        adimaGit(3);
    }, 900);
  }

  function indirmeBaslat() {
    if (indirmeSuruyor) return;
    if (!window.wsAcikMi || !window.wsAcikMi()) {
      durumYaz(s("swSunucuYok", "Sunucu ba\u011flant\u0131s\u0131 yok"),
               "", "kotu", "fa-plug-circle-xmark");
      yenidenGoster(true);
      return;
    }
    indirmeSuruyor = true;
    yenidenGoster(false);
    cubukGoster(true);
    cubukYaz(0, 0);
    durumYaz(s("swIniyor", "Benzetim dosyas\u0131 indiriliyor"),
             tipAd(secilenTip), "bekle", "fa-cloud-arrow-down");
    ileriKilit(true);
    try {
      // FAZ18-IS1B-GONDER-ZAMANASIMI: indirme istegi de yanitsiz kalabilir.
      zamanAsimiKur();
      window.wsCanli().send(JSON.stringify({tip: "sitl_indir",
                                     sanal_tip: secilenTip}));
    } catch (e) {
      indirmeSuruyor = false;
      durumYaz(s("swIndirHata", "\u0130ndirme ba\u015flat\u0131lamad\u0131"),
               String(e), "kotu", "fa-triangle-exclamation");
      yenidenGoster(true);
    }
  }

  function mbYaz(bayt) {
    return (bayt / 1048576).toFixed(1) + " MB";
  }

  function cubukYaz(inen, toplam) {
    var c = el("swCubuk"), b = el("swCubukBilgi");
    if (!c) return;
    if (toplam > 0) {
      var yuzde = Math.max(0, Math.min(100, (inen / toplam) * 100));
      c.classList.remove("belirsiz");
      c.style.width = yuzde.toFixed(1) + "%";
      if (b) b.textContent = yuzde.toFixed(0) + "%  \u00b7  " +
        mbYaz(inen) + " / " + mbYaz(toplam);
    } else {
      // Content-Length yoksa yuzde hesaplanamaz: belirsiz cubuk
      // cizilir ve inen bayt gosterilir. (Olculdu: ArduPilot
      // sunucusu basligi veriyor, bu dal yalniz guvenlik agi.)
      c.classList.add("belirsiz");
      c.style.width = "100%";
      if (b) b.textContent = mbYaz(inen);
    }
  }

  // =================================================================
  // FAZ18-IS1B-GONDER-ZAMANASIMI - YANIT ZAMAN ASIMI
  // -----------------------------------------------------------------
  // Sunucu `sitl_durum` yanitini gondermezse sihirbaz bekleme
  // durumunda kilitlenirdi. Olculen ornek: `_sitl_durum` icinde var
  // olmayan `self._gonder` cagriliyordu; sunucu hata firlatip yaniti
  // hic gondermiyordu. Kok neden giderildi, ancak arayuz bir daha
  // sunucunun yanit verecegine KOSULSUZ guvenmiyor.
  // =================================================================
  var _zamanAsimi = null;

  function zamanAsimiTemizle() {
    if (_zamanAsimi) { clearTimeout(_zamanAsimi); _zamanAsimi = null; }
  }

  function zamanAsimiKur() {
    zamanAsimiTemizle();
    _zamanAsimi = setTimeout(function () {
      _zamanAsimi = null;
      durumYaz(s("swYanitYok", "Sunucu yan\u0131t vermedi"),
               s("swYanitYokAlt",
                 "Sunucu iste\u011fi i\u015fledi ancak yan\u0131t "
                 + "d\u00f6nmedi. Yeniden deneyin."),
               "kotu", "fa-triangle-exclamation");
      ileriKilit(true);
      yenidenGoster(true);
    }, 12000);
  }

  // ---------------------------------------------------------------
  // Sunucu mesajlari
  // ---------------------------------------------------------------
  // ws.js -> window.sitlDurumGeldi
  window.sitlDurumGeldi = function (m) {
    // FAZ18-IS1B-GONDER-ZAMANASIMI: yanit geldi, bekleme sayaci durur.
    zamanAsimiTemizle();
    if (!etkin || !m) return;
    if (String(m.sanal_tip || "") !== secilenTip) return;
    if (m.hazir) { hazirBildir(); return; }
    // Hazir degil: indirme gerekiyor. Kullaniciya karar sorulmaz —
    // sihirbazin bu adimi tam olarak bunun icin var.
    durumYaz(s("swGerekli", "Benzetim dosyas\u0131 gerekli"),
             m.hata || s("swGerekliAlt",
               "Dosya sistemde yok, indirilecek."),
             "bekle", "fa-cloud-arrow-down");
    indirmeBaslat();
  };

  // ws.js -> mevcut `sitl_indirme` duyurusu buraya da dallanir.
  window.sitlSihirbazIndirme = function (m) {
    // FAZ18-IS1B-GONDER-ZAMANASIMI: indirme duyurusu geldi, bekleme sayaci
    // durur. Indirme dakikalar surebilir; ilerleme bildirimleri
    // zaten canlilik kanitidir, sabit bir sure sinirina
    // baglanmak buyuk dosyalarda yanlis hata uretirdi.
    zamanAsimiTemizle();
    if (!etkin || !m) return;
    if (m.durum === "basladi") {
      indirmeSuruyor = true;
      cubukGoster(true);
      cubukYaz(0, 0);
      return;
    }
    if (m.durum === "ilerleme") {
      cubukYaz(Number(m.inen) || 0, Number(m.toplam) || 0);
      return;
    }
    if (m.durum === "bitti") {
      indirmeSuruyor = false;
      cubukYaz(1, 1);
      hazirBildir();
      return;
    }
    if (m.durum === "hata") {
      indirmeSuruyor = false;
      durumYaz(s("swIndirHata", "\u0130ndirme ba\u015far\u0131s\u0131z"),
               m.hata || "", "kotu", "fa-triangle-exclamation");
      cubukGoster(false);
      yenidenGoster(true);
      ileriKilit(true);
    }
  };

  // ---------------------------------------------------------------
  // Diyalog kancalari
  // ---------------------------------------------------------------
  // `bagDialogAc` cagrildiktan SONRA cagrilir (seri.js yamasi).
  window.sitlSihirbazAc = function (tur, kayit) {
    var sanal = (tur === "sanal");
    // Duzenleme modunda sihirbaz ACILMAZ: kullanici var olan bir
    // kaydin adini degistirmek isterken uc adimli akisa sokulmak
    // istemez ve indirme adimi zaten gereksizdir.
    etkin = sanal && !kayit;
    if (!kuruldu && etkin && !kur()) {
      // FAZ18-IS34-KAPSAM: sihirbaz kurulamadi. `etkin=false` yapmak
      // yeterli DEGIL: asagidaki geri alma blogu yalniz `!etkin`
      // dalinda kosar, o yuzden burada da modalin duz kipte
      // kullanilabilir kalmasi garanti edilir.
      etkin = false;
    }
    var sar = el("swSarmal");
    if (sar) sar.style.display = etkin ? "" : "none";
    // FAZ18-IS1-SIHIRBAZ-DUZELT: sihirbaz kipinde kutu genisler ve IPTAL
    // dugmesi gizlenir. Kullanici: "iptal icinse bir dugme
    // gerekmez paneli kapatinca iptal olur". Baslikta
    // `#btnBagKapat` (X) zaten var.
    var kutu = el("bagEkleKutu");
    if (kutu) kutu.classList.toggle("sw-genis", !!etkin);
    var iptal = el("btnBagIptal");
    if (iptal) iptal.style.display = etkin ? "none" : "";
    // Sihirbaz kapaliysa tum gizlemeler geri alinir; aksi halde
    // SERI/TCP formlari 3. adimdan kalan gizli alanlarla acilirdi.
    if (!etkin) {
      var sanalBlok = sanalFormBlok();
      if (sanalBlok) sanalBlok.style.display = sanal ? "" : "none";
      var adAlan = el("bagAdAlan");
      if (adAlan) adAlan.style.display = "";
      var kaydet = el("btnBagKaydet");
      if (kaydet) kaydet.style.display = "";
      var iptal2 = el("btnBagIptal");
      if (iptal2) iptal2.style.display = "";
      var kutu2 = el("bagEkleKutu");
      if (kutu2) kutu2.classList.remove("sw-genis");
      return;
    }
    metinleriYaz();
    indirmeSuruyor = false;
    tipSec(el("bagSanalTip") ? (el("bagSanalTip").value || "multirotor")
                             : "multirotor");
    adimaGit(1);
  };

  // Kaydet'e basildiginda cagrilir (seri.js yamasi).
  // Kullanici istegi: "kaydet deyince sanal dron olussun. otomatik
  // olarak play yapsin".
  window.sitlSihirbazKaydediliyor = function () {
    if (!etkin) return;
    // Kimlik TAHMIN EDILMEZ: kaydetmeden ONCEKI kimlik kumesi
    // saklanir, listede beliren yeni kayit fark alinarak bulunur.
    var onceki = {};
    try {
      var kl = window.bagKayitlar || [];
      for (var i = 0; i < kl.length; i++) onceki[String(kl[i].id)] = true;
    } catch (e) { onceki = {}; }
    otoBaslat = {onceki: onceki, ts: Date.now()};
  };

  // `baglantiListesiIsle` sonunda cagrilir (seri.js yamasi).
  window.sitlSihirbazListeGeldi = function () {
    if (!otoBaslat) return;
    // 20 saniyeden eski niyet dusurulur: aradaki baska bir liste
    // duyurusu niyeti tasiyor olabilir ve yanlis kaydi baslatmak
    // gorunmez bir yan etki uretir.
    if (Date.now() - otoBaslat.ts > 20000) { otoBaslat = null; return; }
    var kl = window.bagKayitlar || [];
    var yeni = null;
    for (var i = 0; i < kl.length; i++) {
      if (kl[i].tur !== "sanal") continue;
      if (!otoBaslat.onceki[String(kl[i].id)]) { yeni = kl[i]; break; }
    }
    if (!yeni) return;
    otoBaslat = null;
    if (!window.wsAcikMi || !window.wsAcikMi()) return;
    try {
      window.wsCanli().send(JSON.stringify({tip: "baglanti_baslat",
                                     id: yeni.id}));
    } catch (e) { /* baslatma bosa duserse kullanici elle basar */ }
  };

  // Dil degisince metinler tazelenir.
  window.sitlSihirbazDilDegisti = function () {
    if (kuruldu) metinleriYaz();
  };
})();
