// ============================================================
// GOKTUNGU GCS — KONUM (ADRES) WIDGET
// v2.4.32
//
// Haritanin BAKTIGI noktanin adresini gosterir: ulke, il, ilce,
// mahalle/yol. Ayrica kapsam bilgisini (gorunur alanin yaklasik
// genisligi) ve tam koordinati verir.
//
// TASARIM KARARI — NEDEN OTOMATIK YENILEMIYOR
// Ters cografi kodlama (reverse geocoding) servisleri, hava
// servislerinin aksine SIKI kota uygular. Nominatim'in kullanim
// politikasi saniyede 1 istek ve degismeyen bir User-Agent bekler;
// haritayi surukleyen bir operator saniyede onlarca moveEnd uretir.
// Bu nedenle konum/zoom degisimi yalnizca ISARETLENIR (kirmizi
// yenile dugmesi belirir) ve istek operator basana kadar gitmez.
//
// VERI KAYNAGI: OpenStreetMap Nominatim (anahtar gerektirmez).
// Cevrimdisi saha kurulumunda istek basarisiz olur; widget bu
// durumda koordinati gostermeye devam eder — koordinat her zaman
// yereldir, ag gerektirmez. Adres satiri "adres alinamadi" der.
//
// ZOOM/KAPSAM: Cesium'da "zoom seviyesi" diye bir kavram yoktur;
// kamera yukseklige gore surekli degisir. Bu nedenle kapsam,
// gorunur alanin YER UZERINDEKI genisligi (km) olarak olculur;
// operator icin zoom seviyesinden daha anlamlidir.
// ============================================================

(function(){
  "use strict";

  const ID = "konum";
  // Bu esikler asilirsa adres artik gecerli sayilmaz:
  const KAYMA_ESIK_KM = 2;      // merkez bu kadar kayarsa
  const KAPSAM_ORAN = 1.6;      // kapsam bu kat degisirse (zoom)

  let ogeler = null;
  let sonKonum = null;      // { lat, lon }
  let sonKapsamKm = null;
  let sonAdres = null;
  let istekSurmekte = false;
  let bayat = false;
  let izleyiciKurulu = false;
  // v2.4.33: baslikta duran tekil yenileme dugmesine erisim
  let wApi = null;

  function ingilizceMi(){
    try {
      if (typeof aktifDil !== "undefined") return String(aktifDil).toLowerCase().startsWith("en");
      const d = localStorage.getItem("gcs_dil");
      return !!(d && d.toLowerCase().startsWith("en"));
    } catch (e) { return false; }
  }

  // ----------------------------------------------------------
  // GOVDE
  // ----------------------------------------------------------
  function govdeKur(govde, api){
    wApi = api;
    govde.classList.add("konum-govde");

    const sarmal = document.createElement("div");
    sarmal.className = "konum-sarmal";

    // ------------------------------------------------------------
    // v2.4.33: TABLO YERLESIMI (kullanici istegi)
    // ------------------------------------------------------------
    // "Konum widget'inda font bir tik kucuk olsun, aralarinda birer
    //  satir olsun, Adres / Lokasyon / Kapsam, widget icinde ikon
    //  olmasin tablo seklinde gosterelim."
    //
    // Onceki yerlesim: pin ikonu + iki satirlik serbest metin blogu +
    // altta ikonlu iki olcu kutucugu. Artik tek bir etiket/deger
    // izgarasi var; ikon YOK.
    //
    // Satirlar:
    //   ADRES     yol / mahalle ayrintisi (en ozgul bilgi)
    //   LOKASYON  ilce - il - ulke
    //   KAPSAM    gorunur alan genisligi
    //   MERKEZ    ekran ortasinin koordinati
    const tablo = document.createElement("div");
    tablo.className = "konum-tablo";

    // satirKur(etiketAnahtar) -> { satir, etiket, deger }
    function satirKur(){
      const s = document.createElement("div");
      s.className = "konum-satir";
      const e = document.createElement("div");
      e.className = "konum-etiket";
      const v = document.createElement("div");
      v.className = "konum-deger";
      v.textContent = "—";
      s.appendChild(e);
      s.appendChild(v);
      tablo.appendChild(s);
      return { satir: s, etiket: e, deger: v };
    }
    const sAdres   = satirKur();
    const sLokasyon= satirKur();
    const sKapsam  = satirKur();
    const sMerkez  = satirKur();

    // Adres satiri iki satira kadar sarabilir (yol adlari uzun olur);
    // digerleri tek satir + kirpma.
    sAdres.deger.classList.add("konum-deger-sar");
    sLokasyon.deger.classList.add("konum-deger-sar");

    // koordYaz/kapsamYaz eski `{ b, s }` bicimini kullanir; satir
    // nesnelerine bu bicimde koprulenir (fazla degisken tanimlanmaz).
    const kKoord = { b: sMerkez.deger, s: sMerkez.etiket };
    const kKapsam = { b: sKapsam.deger, s: sKapsam.etiket };

    // v2.4.33: Bayat isareti artik BASLIKTAKI tekil kirmizi dugmede.
    // Onceki surumde govdenin sag-alt kosesinde yuzen ayri bir daire
    // vardi (`konum-bayat-btn`); kullanici istegi uzerine tum
    // widget'larda yenileme basliga tasindi.
    if (wApi && typeof wApi.yenilemeKur === "function"){
      wApi.yenilemeKur(function(){ adresAl(true); });
    }

    const perde = document.createElement("div");
    perde.className = "konum-perde";
    perde.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';

    sarmal.appendChild(tablo);
    govde.appendChild(sarmal);
    govde.appendChild(perde);

    ogeler = { sarmal, perde, kKoord, kKapsam,
               sAdres, sLokasyon, sKapsam, sMerkez };
    etiketleriYaz();

    // Cift tiklama: elle yenileme (hava widget'i ile ayni alisknlik)
    govde.addEventListener("dblclick", (ev) => {
      ev.stopPropagation();
      adresAl(true);
    });
  }

  // ----------------------------------------------------------
  // HARITA OKUMA
  // Merkez: ekran ortasindan yere isin. Kapsam: sol ve sag kenar
  // orta noktalarinin yer uzerindeki uzakligi.
  // ----------------------------------------------------------
  function yereNokta(x, y){
    try {
      const C = window.Cesium;
      if (!C || typeof viewer === "undefined" || !viewer || !viewer.scene) return null;
      const sahne = viewer.scene;
      const isin = viewer.camera.getPickRay(new C.Cartesian2(x, y));
      if (!isin) return null;
      const n = sahne.globe.pick(isin, sahne);
      if (!n) return null;
      const k = C.Cartographic.fromCartesian(n);
      if (!k) return null;
      return { lat: C.Math.toDegrees(k.latitude),
               lon: C.Math.toDegrees(k.longitude) };
    } catch (e) { return null; }
  }

  function haritaDurumu(){
    try {
      const C = window.Cesium;
      if (!C || typeof viewer === "undefined" || !viewer || !viewer.scene) return null;
      const kanvas = viewer.scene.canvas;
      const g = kanvas.clientWidth, y = kanvas.clientHeight;
      const merkez = yereNokta(g / 2, y / 2);
      if (!merkez){
        // Kamera ufka bakiyorsa isin yere degmez; kameranin kendi
        // konumu kullanilir, kapsam olculemez.
        const kk = viewer.camera.positionCartographic;
        if (!kk) return null;
        return { lat: C.Math.toDegrees(kk.latitude),
                 lon: C.Math.toDegrees(kk.longitude),
                 kapsamKm: null };
      }
      // Kapsam: sol/sag kenar orta noktalari. Kenarlar ufka
      // dusuyorsa (egik kamera) yer noktasi bulunamaz; bu durumda
      // kapsam bilinmez olarak isaretlenir.
      const sol = yereNokta(2, y / 2);
      const sag = yereNokta(g - 2, y / 2);
      let kapsamKm = null;
      if (sol && sag) kapsamKm = kmUzaklik(sol, sag);
      return { lat: merkez.lat, lon: merkez.lon, kapsamKm: kapsamKm };
    } catch (e) { return null; }
  }

  function kmUzaklik(a, b){
    const R = 6371;
    const dLat = (b.lat - a.lat) * Math.PI / 180;
    const dLon = (b.lon - a.lon) * Math.PI / 180;
    const la1 = a.lat * Math.PI / 180, la2 = b.lat * Math.PI / 180;
    const h = Math.sin(dLat/2)**2 + Math.cos(la1) * Math.cos(la2) * Math.sin(dLon/2)**2;
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
  }

  // ----------------------------------------------------------
  // BAYAT TAKIBI
  // ----------------------------------------------------------
  function bayatIsaretle(b){
    bayat = b;
    // v2.4.33: dugme baslikta; gorunurlugu widget API'si yonetir
    if (wApi && typeof wApi.yenileGoster === "function"){
      const en = ingilizceMi();
      wApi.yenileGoster(b, b
        ? ((D().wgKonumBayat)
           || (en ? "Map view changed \u2014 refresh address"
                  : "Harita g\u00f6r\u00fcn\u00fcm\u00fc de\u011fi\u015fti \u2014 adresi yenile"))
        : "");
    }
    if (ogeler && ogeler.sarmal)
      ogeler.sarmal.classList.toggle("konum-solgun", b);
  }

  function degistiMi(d){
    if (!sonKonum) return true;
    if (kmUzaklik(sonKonum, d) >= KAYMA_ESIK_KM) return true;
    // Kapsam (zoom) degisimi
    if (sonKapsamKm && d.kapsamKm){
      const oran = d.kapsamKm / sonKapsamKm;
      if (oran >= KAPSAM_ORAN || oran <= 1 / KAPSAM_ORAN) return true;
    }
    return false;
  }

  function izleyiciKur(){
    if (izleyiciKurulu) return;
    try {
      if (typeof viewer === "undefined" || !viewer || !viewer.camera) return;
      viewer.camera.moveEnd.addEventListener(() => {
        if (!ogeler || !sonAdres) return;
        const d = haritaDurumu();
        if (!d) return;
        // Kapsam kutusu her zaman canli tutulur: bu yerel bir
        // hesap, ag istegi gerektirmez. Yalnizca ADRES bayatlar.
        kapsamYaz(d.kapsamKm);
        if (degistiMi(d)) bayatIsaretle(true);
        else if (bayat) bayatIsaretle(false);
      });
      izleyiciKurulu = true;
    } catch (e) {}
  }

  // ----------------------------------------------------------
  // ADRES ALMA
  // ----------------------------------------------------------
  function adresAl(zorla){
    if (!ogeler) return;
    if (istekSurmekte) return;
    const d = haritaDurumu();
    if (!d){
      perdeGoster(true, ingilizceMi() ? "Map position unknown"
                                      : "Harita konumu okunamad\u0131");
      return;
    }
    // Koordinat ve kapsam AG GEREKTIRMEZ: hemen yazilir.
    koordYaz(d.lat, d.lon);
    kapsamYaz(d.kapsamKm);

    if (!zorla && sonAdres && !degistiMi(d)) return;

    istekSurmekte = true;
    if (!sonAdres) perdeGoster(false);

    // zoom=14 mahalle/yol duzeyi verir; kapsam genisse daha kaba
    // duzey istenir, boylece "sehir goruntusunde sokak adi" gibi
    // yanlis ozgullukten kacinilir.
    let zoom = 16;
    if (d.kapsamKm !== null){
      if (d.kapsamKm > 400) zoom = 5;
      else if (d.kapsamKm > 120) zoom = 8;
      else if (d.kapsamKm > 40) zoom = 10;
      else if (d.kapsamKm > 12) zoom = 12;
      else if (d.kapsamKm > 4) zoom = 14;
    }

    const en = ingilizceMi();
    const url = "https://nominatim.openstreetmap.org/reverse?format=jsonv2" +
      "&lat=" + d.lat.toFixed(5) + "&lon=" + d.lon.toFixed(5) +
      "&zoom=" + zoom + "&addressdetails=1" +
      "&accept-language=" + (en ? "en" : "tr");

    const iptal = new AbortController();
    const zt = setTimeout(() => iptal.abort(), 12000);

    fetch(url, { signal: iptal.signal, cache: "no-store" })
      .then(y => { if (!y.ok) throw new Error("HTTP " + y.status); return y.json(); })
      .then(j => {
        clearTimeout(zt);
        istekSurmekte = false;
        sonKonum = { lat: d.lat, lon: d.lon };
        sonKapsamKm = d.kapsamKm;
        sonAdres = adresAyristir(j);
        bayatIsaretle(false);
        gorunumTazele();
      })
      .catch(err => {
        clearTimeout(zt);
        istekSurmekte = false;
        if (sonAdres){
          gorunumTazele();
        } else {
          // Adres yok ama koordinat var: koordinati gostermeye devam
          // et, yalnizca adres satirini bilgilendir.
          const ag = (err && err.name === "AbortError");
          perdeGoster(true, ag
            ? (en ? "Request timed out" : "\u0130stek zaman a\u015f\u0131m\u0131na u\u011frad\u0131")
            : (en ? "Address unavailable" : "Adres al\u0131namad\u0131"));
        }
      });
  }

  // Nominatim yaniti bolgeye gore cok farkli anahtarlar kullanir;
  // sirali yedekleme ile en anlamli alan secilir.
  function adresAyristir(j){
    const a = (j && j.address) || {};
    const ilk = (...adlar) => {
      for (const ad of adlar) if (a[ad]) return a[ad];
      return "";
    };
    const ulke = ilk("country");
    const il = ilk("province", "state", "region");
    const ilce = ilk("county", "city_district", "town", "city", "municipality");
    const yerlesim = ilk("suburb", "neighbourhood", "quarter", "village", "hamlet");
    const yol = ilk("road", "pedestrian", "footway");
    return {
      ulke: ulke, il: il, ilce: ilce, yerlesim: yerlesim, yol: yol,
      tam: (j && j.display_name) ? j.display_name : "",
    };
  }

  // ----------------------------------------------------------
  // GORUNUM
  // ----------------------------------------------------------
  function perdeGoster(hataMi, mesaj){
    if (!ogeler) return;
    const en = ingilizceMi();
    if (hataMi){
      // Hata durumunda sarmal GIZLENMEZ: koordinat ve kapsam
      // gecerli kalir; yalnizca adres satiri hatayi bildirir.
      ogeler.perde.style.display = "none";
      ogeler.sarmal.style.display = "";
      // v2.4.33: hata yalnizca ADRES satirina yazilir; Lokasyon,
      // Kapsam ve Merkez satirlari hesaplanabilir oldugu icin
      // gecerli kalir (koordinat ag istegi gerektirmez).
      ogeler.sAdres.deger.textContent = mesaj ||
        (en ? "Address unavailable" : "Adres al\u0131namad\u0131");
      ogeler.sAdres.deger.classList.add("konum-hata");
      ogeler.sLokasyon.deger.textContent = "—";
      bayatIsaretle(true);   // yeniden denemek icin dugme kalsin
    } else {
      ogeler.perde.style.display = "";
      ogeler.perde.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
      ogeler.sarmal.style.display = "none";
    }
  }

  // v2.4.33: satir etiketleri (tablonun sol sutunu). Dil degisiminde
  // yeniden cagrilir. Degerler ayri fonksiyonlarda yazilir.
  function etiketleriYaz(){
    if (!ogeler || !ogeler.sAdres) return;
    const en = ingilizceMi();
    ogeler.sAdres.etiket.textContent    = en ? "Address"  : "Adres";
    ogeler.sLokasyon.etiket.textContent = en ? "Location" : "Lokasyon";
    ogeler.sKapsam.etiket.textContent   = en ? "Span"     : "Kapsam";
    ogeler.sMerkez.etiket.textContent   = en ? "Center"   : "Merkez";
  }

  function koordYaz(lat, lon){
    if (!ogeler) return;
    ogeler.kKoord.b.textContent =
      Math.abs(lat).toFixed(3) + (lat >= 0 ? "N " : "S ") +
      Math.abs(lon).toFixed(3) + (lon >= 0 ? "E" : "W");
  }

  function kapsamYaz(kapsamKm){
    if (!ogeler) return;
    if (kapsamKm === null || !isFinite(kapsamKm)){
      ogeler.kKapsam.b.textContent = "—";
      return;
    }
    ogeler.kKapsam.b.textContent = (kapsamKm < 1)
      ? Math.round(kapsamKm * 1000) + " m"
      : (kapsamKm < 20 ? kapsamKm.toFixed(1) : Math.round(kapsamKm)) + " km";
  }

  function gorunumTazele(){
    if (!ogeler || !sonAdres) return;
    ogeler.perde.style.display = "none";
    ogeler.sarmal.style.display = "";
    ogeler.sAdres.deger.classList.remove("konum-hata");

    const a = sonAdres;
    const en = ingilizceMi();

    // v2.4.33 TABLO ANLAMLARI:
    //   ADRES    = en ozgul konum bilgisi (yol / mahalle)
    //   LOKASYON = yonetsel zincir (ilce - il - ulke)
    // Onceki surumde ilce basliga, yol ise alt ayrinti satirina
    // yaziliyordu; kullanici tablo istedigi icin anlamlar
    // "Adres" ve "Lokasyon" etiketleriyle netlestirildi.
    const ayr = [];
    if (a.yol) ayr.push(a.yol);
    if (a.yerlesim) ayr.push(a.yerlesim);
    let adresMetin = ayr.join(" \u00b7 ");
    if (!adresMetin && a.tam) adresMetin = a.tam.split(",").slice(0, 2).join(",").trim();
    if (!adresMetin) adresMetin = a.ilce || a.il ||
      (en ? "Unknown area" : "Bilinmeyen b\u00f6lge");
    ogeler.sAdres.deger.textContent = adresMetin;

    // Lokasyon: ilce - il - ulke, yinelenenler atlanir
    const lok = [];
    [a.ilce, a.il, a.ulke].forEach(p => {
      if (p && lok.indexOf(p) === -1) lok.push(p);
    });
    ogeler.sLokasyon.deger.textContent = lok.length
      ? lok.join(" \u00b7 ")
      : (en ? "Unknown" : "Bilinmiyor");

    if (sonKonum) koordYaz(sonKonum.lat, sonKonum.lon);
    kapsamYaz(sonKapsamKm);
  }

  // ----------------------------------------------------------
  // YASAM DONGUSU
  // ----------------------------------------------------------
  function ac(){
    if (sonAdres) gorunumTazele();
    adresAl(!sonAdres);
    izleyiciKur();
  }
  function kapa(){ /* zamanlayici yok */ }

  function dilTazele(){
    if (!ogeler) return;
    // Adres dile bagli geldi: yeniden istemek gerekir, ancak kota
    // nedeniyle kendiliginden istek atilmaz — bayat isaretlenir.
    if (sonAdres) bayatIsaretle(true);
    etiketleriYaz();
    if (sonKonum) koordYaz(sonKonum.lat, sonKonum.lon);
    kapsamYaz(sonKapsamKm);
  }

  function kaydol(){
    if (!window.Widget) return;
    window.Widget.kaydet({
      id: ID,
      baslik: "KONUM",
      baslikAnahtar: "wgKonum",
      genislik: 226,
      yukseklik: 224,
      govdeKur: govdeKur,
      ac: ac,
      kapa: kapa,
    });
  }

  window.WidgetKonum = {
    kaydol: kaydol,
    adresAl: adresAl,
    dilTazele: dilTazele,
  };
})();
