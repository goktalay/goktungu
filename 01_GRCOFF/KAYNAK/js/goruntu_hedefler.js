/* ============================================================
   GÖRÜNTÜ HEDEFLERİ — köprü hedef listesi + angajman girişi
                                          [FAZ20-IS93-JS-v1]
   ============================================================
   Kullanıcı hedefi: "benim sonunda tek amacım görüntü işleme ile
   angajman yapmak".

   ------------------------------------------------------------
   NEDEN AYRI DOSYA
   ------------------------------------------------------------
   `goruntu_koprusu.js` yalnız indirme/panel açma girişidir ve
   köprünün KURULU OLUP OLMADIĞINI bilemez (karma içerik engeli,
   İş 84). Bu dosya ise merkeze GELEN hedef verisini gösterir —
   veri WebSocket'ten gelir, tarayıcı köprüye hiç bağlanmaz.
   İki dosyanın bilgi kaynağı farklı olduğu için ayrı tutuldular.

   ------------------------------------------------------------
   ÖLÇÜLEN SÖZLEŞMELER (varsayılmadı, sunucudan okundu)
   ------------------------------------------------------------
   - `hedef_liste` komutu -> {"tip":"hedef_sonuc", "komut":"hedef_liste",
     "kopruler":[...], "sayim":{...}}  (sunucu.py:2244,2274)
   - `hedef_sonuc` tipi ws.js'te İŞLENMİYORDU; bu sürümde dal eklendi.
   - Yetki: `hedef_liste` okuma (pilot), `angajman_ekle`/`angajman_karar`
     YALNIZ yönetici (sunucu.py:2264). Bu panel yalnız OKUR ve
     angajmanı mevcut `angajman_baslat` yoluna devreder.
   - Popup kalıbı: kök `popup-gizli`, başlık `.popup-baslik`
   - Kayıt: popupBoyutlandirilabilirYap / popupTasinabilirYap,
     anahtar "pp_" + ID  (popup_tasima.js:310,315)
   - Düğme: `dugme` sınıfı YOK; dugme_birlik.css doğrudan `button`
     etiketine uygular -> her tıklanabilir öğe <button>
   - Boş veri: window.bosPanelYap(metin, ikon)  (bos_panel.js:47)
   - Menü kapatma: window.menubarKapat  (menubar.js:18)
   - Renkler: SABİT RENK YASAK, yalnız CSS değişkeni.
     `--iyi-zemin` DİYE BİR DEĞİŞKEN YOK (ölçüldü) — `--iyi` var.

   ------------------------------------------------------------
   KALİBRASYON KAPISI
   ------------------------------------------------------------
   Kamera kalibre değilse hedefin yeryüzü koordinatı ÇÖZÜLEMEZ.
   Merkez bu durumda `konum_guvenilir=false` işaretler. Panel
   hedefi yine gösterir (operatör görüntüde bir şey olduğunu
   bilmeli) ama angajman düğmesi KİLİTLİDİR ve gerekçe yazılıdır.
   Sunucu tarafında da ayrı bir kapı var (angajman.py baslat ön
   denetimi) — arayüz kilidi yalnız ilk savunma hattıdır.
   ============================================================ */
(function () {
  "use strict";

  var ID = "goruntuHedeflerPopup";
  var YENILE_MS = 2000;      // hedef verisi ~2 paket/sn geliyor
  var zamanlayici = null;
  var sonKopruler = [];
  var sonSayim = {};

  /* --- yardımcılar ------------------------------------------- */

  function S() { return (typeof D === "function") ? D() : {}; }

  function wsGonder(n) {
    if (typeof ws !== "undefined" && ws && ws.readyState === 1) {
      ws.send(JSON.stringify(n));
      return true;
    }
    return false;
  }

  function metin(anahtar, yedek) {
    var s = S();
    return (s && s[anahtar]) ? s[anahtar] : yedek;
  }

  function yoneticiMi() {
    return (typeof oturum !== "undefined" && oturum &&
            oturum.rol === "yonetici");
  }

  /* Tür adları: köprü `insan`/`arac`/`dron` gönderir. */
  function turAdi(tur) {
    var s = S();
    var harita = {
      insan: metin("ghTurInsan", "İnsan"),
      arac: metin("ghTurArac", "Araç"),
      dron: metin("ghTurDron", "Dron"),
      plaka: metin("ghTurPlaka", "Plaka")
    };
    return harita[tur] || tur || "?";
  }

  function turIkonu(tur) {
    var harita = {
      insan: "fa-person",
      arac: "fa-car",
      dron: "fa-helicopter",
      plaka: "fa-rectangle-list"
    };
    return "fa-solid " + (harita[tur] || "fa-crosshairs");
  }

  function kaynakTuruAdi(tur) {
    if (tur === "dron") return metin("ghKaynakDron", "Hareketli dron kamerası");
    if (tur === "lokasyon") return metin("ghKaynakLokasyon", "Kayıtlı sabit lokasyon");
    return metin("ghKaynakManuel", "Manuel sabit kamera");
  }

  /* Bileşik hedef kimliği — angajman motorunun beklediği biçim.
     İz numaraları kamera başına üretilir ve her köprüde baştan
     başlar; yalnız `iz` taşınsaydı iki köprünün 7 numaralı izleri
     ayırt edilemezdi. */
  function hedefKimligi(ornekId, kamera, iz) {
    return String(ornekId) + ":" + String(kamera) + ":" + String(iz);
  }

  /* --- panel kurulumu ---------------------------------------- */

  function geometriyiDuzelt(d) {
    if (!d) return;
    var kenar = 16;
    var minUst = (typeof window.pencereMinTop === "function")
      ? Number(window.pencereMinTop()) || 48 : 48;
    var azamiW = Math.max(240, Math.min(900, window.innerWidth - kenar * 2));
    var azamiH = Math.max(220, Math.min(680, window.innerHeight - minUst - kenar));
    var r = d.getBoundingClientRect();
    var w = Math.min(Math.max(r.width || 620, Math.min(400, azamiW)), azamiW);
    var h = Math.min(Math.max(r.height || 460, Math.min(300, azamiH)), azamiH);
    var bozukBoyut = Math.abs(w - r.width) > 1 || Math.abs(h - r.height) > 1;
    var ekranDisi = r.right < 120 || r.left > window.innerWidth - 120 ||
      r.bottom < minUst + 40 || r.top > window.innerHeight - 40;
    if (bozukBoyut) {
      d.style.width = Math.round(w) + "px";
      d.style.height = Math.round(h) + "px";
    }
    if (bozukBoyut || ekranDisi) {
      d.style.transform = "none";
      d.style.left = Math.round(Math.max(kenar, (window.innerWidth - w) / 2)) + "px";
      d.style.top = Math.round(Math.max(minUst, (window.innerHeight - h) / 2)) + "px";
      d.style.right = "auto";
      try {
        if (typeof window.pencereKonumKaydet === "function")
          window.pencereKonumKaydet("pp_" + ID, d, true);
      } catch (e) {}
    }
  }

  function kur() {
    var mevcut = document.getElementById(ID);
    if (mevcut) return mevcut;

    var d = document.createElement("div");
    d.id = ID;
    d.className = "popup-gizli gh-popup";
    d.innerHTML =
      '<div class="popup-baslik">' +
        '<span><i class="fa-solid fa-crosshairs"></i> ' +
          '<span data-i18n="panelGoruntuHedefler">GÖRÜNTÜ HEDEFLERİ</span>' +
        '</span>' +
        '<button id="btnGhKapat" data-i18n-title="ipKapat" title="Kapat">' +
          '<i class="fa-solid fa-xmark"></i></button>' +
      '</div>' +
      '<div class="gh-ustbar">' +
        '<span class="gh-ustbar-baslik" data-i18n="ghUstbarBaslik">' +
          'TESPİT EDİLEN HEDEFLER</span>' +
        '<span class="gh-ustbar-sag">' +
          '<button type="button" id="ghYenile">' +
            '<i class="fa-solid fa-rotate"></i>' +
            '<span data-i18n="ghYenile">YENİLE</span>' +
          '</button>' +
        '</span>' +
      '</div>' +
      '<div class="gh-govde" id="ghGovde"></div>';

    document.body.appendChild(d);

    var kapat = d.querySelector("#btnGhKapat");
    if (kapat) kapat.addEventListener("click", gizle);

    var yenile = d.querySelector("#ghYenile");
    if (yenile) yenile.addEventListener("click", iste);

    try {
      if (typeof window.popupBoyutlandirilabilirYap === "function")
        window.popupBoyutlandirilabilirYap(d, "pp_" + ID);
    } catch (e) {}
    try {
      if (typeof window.popupTasinabilirYap === "function")
        window.popupTasinabilirYap(d, null, "pp_" + ID);
    } catch (e) {}

    return d;
  }

  /* --- çizim -------------------------------------------------- */

  function govdeyiCiz() {
    var govde = document.getElementById("ghGovde");
    if (!govde) return;

    govde.textContent = "";

    var hicHedefVar = sonKopruler.some(function (k) {
      return (k.kameralar || []).some(function (kam) {
        return (kam.hedefler || []).length > 0;
      });
    });

    if (!hicHedefVar) {
      /* Boş panel sözleşmesi: düz metin değil, büyük ikon. */
      if (typeof window.bosPanelYap === "function") {
        govde.appendChild(window.bosPanelYap(
          metin("ghHedefYok", "Görüntü hedefi yok"),
          "fa-solid fa-crosshairs"));
      }
      return;
    }

    sonKopruler.forEach(function (kopru) {
      (kopru.kameralar || []).forEach(function (kam) {
        var hedefler = kam.hedefler || [];
        if (!hedefler.length) return;

        var kal = kam.kalibrasyon || {};
        var kaynakTuru = kam.poz_kaynak || kal.poz_kaynak || "manuel";
        var hareketliMi = kaynakTuru === "dron";
        var kalibreMi = !!kal.kalibre;

        /* Kamera başlığı */
        var bas = document.createElement("div");
        bas.className = "gh-kamera-baslik";

        var ad = document.createElement("span");
        ad.className = "gh-kamera-ad";
        ad.textContent = (kopru.kopru_ad || kopru.ad || "?") + " · " +
                         metin("ghKamera", "Kamera") + " " + kam.kamera +
                         " · " + kaynakTuruAdi(kaynakTuru);
        bas.appendChild(ad);

        var rozet = document.createElement("span");
        rozet.className = "gh-kalibre-rozet" + (kalibreMi ? " tamam" : "");
        rozet.textContent = kalibreMi
          ? (hareketliMi ? metin("ghKaynakHazir", "KAYNAK HAZIR")
                         : metin("ghKalibre", "KALİBRE"))
          : metin("ghKalibreDegil", "KALİBRE DEĞİL");
        bas.appendChild(rozet);

        govde.appendChild(bas);

        /* Kalibre değilse tek seferlik açıklama — her hedefin
           altında tekrarlamak gürültü olurdu. */
        if (!kalibreMi) {
          var uyari = document.createElement("div");
          uyari.className = "gh-kalibre-uyari";
          uyari.textContent = hareketliMi
            ? metin("ghDronKaynakUyari",
              "Kayıtlı kaynak dron veya görüş açısı eksik. Angajman kapalı. " +
              "Görüntü Köprüsü kamera ayarından firma kapsamındaki dronu seçin.")
            : metin("ghKalibreUyari",
              "Kamera konumu girilmediği için hedeflerin harita " +
              "koordinatı çözülemiyor. Angajman kapalı. Köprü " +
              "panelinden enlem, boylam ve görüş açısını girin.");
          govde.appendChild(uyari);
        }

        /* Hedefler — öncelik sırasına göre */
        hedefler.slice().sort(function (a, b) {
          return (b.oncelik || 0) - (a.oncelik || 0);
        }).forEach(function (h) {
          govde.appendChild(hedefSatiri(kopru, kam, h, kalibreMi));
        });
      });
    });
  }

  function hedefSatiri(kopru, kam, h, kalibreMi) {
    var satir = document.createElement("div");
    satir.className = "gh-hedef";

    /* Sol: ikon + kimlik */
    var sol = document.createElement("div");
    sol.className = "gh-hedef-sol";

    var ikon = document.createElement("i");
    ikon.className = turIkonu(h.tur) + " gh-hedef-ikon";
    sol.appendChild(ikon);

    var kimlik = document.createElement("span");
    kimlik.className = "gh-hedef-kimlik";
    kimlik.textContent = turAdi(h.tur) + " #" + h.iz;
    sol.appendChild(kimlik);

    satir.appendChild(sol);

    /* Orta: ölçümler */
    var orta = document.createElement("div");
    orta.className = "gh-hedef-olcum";

    orta.appendChild(olcum(
      metin("ghGuven", "Güven"),
      (h.puan != null) ? (h.puan * 100).toFixed(0) + "%" : "—"));

    orta.appendChild(olcum(
      metin("ghAzimut", "Azimut"),
      (h.azimut != null) ? h.azimut.toFixed(1) + "°" : "—"));

    /* Mesafe bir TAHMİN. Güveni düşük olduğu için sayının yanına
       her zaman güven yüzdesi yazılır — operatör bunu kesin bir
       ölçüm sanmamalı. */
    var mesafeMetin = "—";
    if (h.mesafe_m != null && h.mesafe_m > 0) {
      mesafeMetin = h.mesafe_m.toFixed(0) + " m";
      if (h.mesafe_guven != null)
        mesafeMetin += " (±" + ((1 - h.mesafe_guven) * 100).toFixed(0) + "%)";
    }
    orta.appendChild(olcum(metin("ghMesafe", "Mesafe"), mesafeMetin));
    orta.appendChild(olcum(metin("ghKaynak", "Kaynak"),
                           kaynakTuruAdi(h.poz_kaynak || kam.poz_kaynak)));
    if (!h.konum_guvenilir || kopru.bayat) {
      orta.appendChild(olcum(metin("ghKilit", "Kilit"), kopru.bayat
        ? metin("ghPaketBayat", "Hedef paketi bayat")
        : (h.konum_gerekce || metin("ghAngajmanKapali",
                                    "Hedef konumu çözülemedi"))));
    }

    satir.appendChild(orta);

    /* Sağ: eylemler */
    var sag = document.createElement("div");
    sag.className = "gh-hedef-eylem";

    var konumVar = !kopru.bayat && kalibreMi && h.konum_guvenilir
                   && h.lat != null && h.lon != null;

    var btnHarita = document.createElement("button");
    btnHarita.type = "button";
    btnHarita.className = "gh-btn-harita";
    btnHarita.innerHTML = '<i class="fa-solid fa-location-crosshairs"></i>';
    btnHarita.title = metin("ghHaritadaGoster", "Haritada göster");
    btnHarita.disabled = !konumVar;
    if (konumVar) {
      btnHarita.addEventListener("click", function () {
        haritayaUc(h.lat, h.lon, h.alt);
      });
    }
    sag.appendChild(btnHarita);

    var btnAng = document.createElement("button");
    btnAng.type = "button";
    btnAng.className = "gh-btn-angajman";
    btnAng.innerHTML = '<i class="fa-solid fa-crosshairs"></i>' +
                       '<span>' + metin("ghAngajman", "ANGAJMAN") + '</span>';
    var eylemYetkisi = yoneticiMi();
    btnAng.disabled = !konumVar || !eylemYetkisi;
    if (!eylemYetkisi) {
      btnAng.title = metin(
        "ghYoneticiGerek", "Angajmanı yalnızca yönetici başlatabilir");
    } else if (!konumVar) {
      /* Gerekçe merkezden geliyor; arayüz kendi metnini uydurmuyor. */
      btnAng.title = kopru.bayat
        ? metin("ghPaketBayat", "Hedef paketi bayat")
        : (h.konum_gerekce ||
           metin("ghAngajmanKapali", "Hedef konumu çözülemedi"));
    } else {
      btnAng.addEventListener("click", function () {
        angajmaniBaslat(kopru, kam, h);
      });
    }
    sag.appendChild(btnAng);

    satir.appendChild(sag);
    return satir;
  }

  function olcum(etiket, deger) {
    var d = document.createElement("span");
    d.className = "gh-olcum";
    var e = document.createElement("span");
    e.className = "gh-olcum-etiket";
    e.textContent = etiket;
    var v = document.createElement("span");
    v.className = "gh-olcum-deger";
    v.textContent = deger;
    d.appendChild(e);
    d.appendChild(v);
    return d;
  }

  /* --- eylemler ----------------------------------------------- */

  function haritayaUc(lat, lon, alt) {
    try {
      if (typeof viewer === "undefined" || !viewer) return;
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(
          lon, lat, (alt || 0) + 400),
        duration: 1.2
      });
    } catch (e) {}
  }

  /* Angajmanı MEVCUT motora devreder. Yeni bir angajman yolu
     AÇILMAZ — insan onayı, yetki kapısı ve güdüm döngüsü zaten
     `angajman.js` + `angajman_baslat` yolunda. */
  function angajmanBaglami(kopru, kam, h) {
    var kal = kam.kalibrasyon || {};
    return {
      ad: turAdi(h.tur) + " #" + h.iz,
      lat: h.lat, lon: h.lon, alt: h.alt,
      ornek_id: String(kopru.ornek_id || h.ornek_id || ""),
      kopru_ad: String(kopru.kopru_ad || kopru.ad || h.kopru_ad || ""),
      kamera_id: String(kam.kamera || h.kamera || ""),
      kamera_ad: String(kam.ad || h.kamera_ad || (metin("ghKamera", "Kamera") + " " + (kam.kamera || h.kamera || ""))),
      iz_id: h.iz,
      secim_ts: Number(h.secim_zamani || h.secim_ts || 0),
      kaynak_dron_uid: String(h.kaynak_dron_id || h.dron_uid || kam.kaynak_dron_id || kal.kaynak_dron_id || "")
    };
  }

  function angajmaniBaslat(kopru, kam, h) {
    var kimlik = hedefKimligi(kopru.ornek_id, kam.kamera, h.iz);
    if (typeof window.angajmanPopupAc === "function") {
      window.angajmanPopupAc("goruntu", kimlik, angajmanBaglami(kopru, kam, h));
    }
  }

  /* Yerel tam ekran görüntüde seçilen çerçeve, sunucudan aynı firma
     oturumlarına tek-seferlik aday olayı olarak gelir. Görüntü gelmez;
     yalnız bileşik iz kimliği ve kaynak metadata kullanılır. */
  function adayYanit(m) {
    if (!m || m.tip !== "goruntu_angajman_adayi" || !m.hedef_id) return;
    if (typeof window.angajmanPopupAc !== "function") return;
    window.angajmanPopupAc("goruntu", String(m.hedef_id), m.kaynak || {});
  }

  /* --- veri --------------------------------------------------- */

  function iste() {
    wsGonder({ tip: "hedef_liste" });
  }

  function yanit(m) {
    if (!m || m.komut !== "hedef_liste") return;
    if (!m.basarili) return;
    sonKopruler = m.kopruler || [];
    sonSayim = m.sayim || {};
    govdeyiCiz();
    try {
      if (typeof window.panelDurumTazele === "function")
        window.panelDurumTazele();
    } catch (e) {}
  }

  /* --- görünürlük --------------------------------------------- */

  function ac() {
    var d = kur();
    d.classList.remove("popup-gizli");
    try {
      if (typeof window.pencereKonumUygula === "function")
        window.pencereKonumUygula("pp_" + ID, d, true);
    } catch (e) {}
    geometriyiDuzelt(d);
    try {
      if (typeof window.pencereEnUsteGetir === "function")
        window.pencereEnUsteGetir(d);
    } catch (e) {}
    iste();
    /* Panel kapalıyken yoklama yapmak boşuna trafik üretir. */
    if (zamanlayici) clearInterval(zamanlayici);
    zamanlayici = setInterval(iste, YENILE_MS);
  }

  function gizle() {
    var d = document.getElementById(ID);
    if (d) d.classList.add("popup-gizli");
    if (zamanlayici) { clearInterval(zamanlayici); zamanlayici = null; }
  }

  /* --- menü bağlama ------------------------------------------- */

  function bagla() {
    var oge = document.getElementById("mbGoruntuHedefler");
    if (!oge) return false;
    oge.addEventListener("click", function () {
      var d = document.getElementById(ID);
      if (d && !d.classList.contains("popup-gizli")) gizle();
      else ac();
      try {
        if (typeof window.menubarKapat === "function")
          window.menubarKapat();
      } catch (e) {}
    });
    return true;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bagla);
  } else {
    bagla();
  }

  window.goruntuHedeflerAc = ac;
  window.goruntuHedefYanit = yanit;
  window.goruntuAngajmanAdayiIsle = adayYanit;
  /* Sınav ve tanı için */
  window.GoruntuHedefler = {
    kimlik: hedefKimligi,
    veri: function () { return sonKopruler; },
    sayim: function () { return sonSayim; },
    adayIsle: adayYanit,
    baglam: angajmanBaglami,
    isaret: "FAZ20-IS99-JS-v1"
  };
})();
