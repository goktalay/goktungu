/* ================================================================
   FAZ18-IS5-PILOT-KONUM — Pilot bazli harita konumu + Gokkubbe isareti
   ----------------------------------------------------------------
   NEDEN BU DOSYA VAR
   Olcumde bulunan kok neden: haritanin acilis konumu sunucu tarafinda
   TEK BIR GENEL ayarda tutuluyordu (`sunucu.py` -> `ayar_kaydet` ->
   `merkez_lat`/`merkez_lon`) ve kayit hemen ardindan `_duyur` ile
   BAGLI TUM ISTEMCILERE gonderiliyordu. Sonuc: bir pilot konumu
   degistirince baska pilotun haritasi da oraya uçuyordu.

   O genel ayara DOKUNULMAZ: ayni alanlar radar tarama merkezi olarak
   da kullaniliyor (`radar.py`, `radar_vekil.py`). Radar merkezi
   kurulum/firma duzeyinde ortak olmalidir; pilot basina alinirsa
   radar taramasi bozulur.

   COZUM: haritanin ACILIS konumu icin AYRI, pilot bazli bir kayit
   katmani. Anahtar `gcs_harita_konum_<eposta>`; boylece ayni
   tarayicida farkli pilotlar birbirinin gorunumunu ezmez.

   ILK GIRIS: kayit yoksa Gokkubbe adresine gidilir ve o adreste
   kurumsal isaret gosterilir.
   ================================================================ */
(function () {
  "use strict";

  /* Gokkubbe Teknoloji A.S. — Ahi Evren OSB Mah. Buyuk Selcuklu Cad.
     No:2/B Sincan/Ankara

     v2.4.120 (IS62): KOORDINAT DUZELTILDI. Onceki deger
     39.9334 / 32.5785 idi ve gercek adresten 5205 m sapiyordu;
     isaret Sincan'da bambaska bir noktayi gosteriyordu.
     Bu sabit dort yerde okunur (isaret konumu, ilk giris acilisi,
     `haritaGokkubbeyeGit`, `haritaGokkubbeKoordinat`) — tek
     noktadan duzeltmek dordunu birden duzeltir. */
  var GOKKUBBE = { lat: 39.973112, lon: 32.546172, yuk: 2600 };

  var ONEK = "gcs_harita_konum_";
  var pilot = null;          // aktif pilotun eposta anahtari
  var kameraIzleyiciKurulu = false;
  var yazmaZaman = null;
  var isaretEnt = null;
  var isaretKurulu = false;
  var acilisYapildi = false;

  function C() { return window.Cesium; }

  function vw() {
    // viewer harita.js modul kapsamindadir; window'a acilmaz. Bu modul
    // harita.js'in ICINE enjekte edilen kanca uzerinden viewer alir.
    return window.__haritaViewerAl ? window.__haritaViewerAl() : null;
  }

  function anahtar() {
    return pilot ? (ONEK + pilot) : null;
  }

  function kayitOku() {
    var a = anahtar();
    if (!a) return null;
    try {
      var ham = localStorage.getItem(a);
      if (!ham) return null;
      var d = JSON.parse(ham);
      if (!d || typeof d.lat !== "number" || typeof d.lon !== "number")
        return null;
      if (!(d.lat >= -90 && d.lat <= 90)) return null;
      if (!(d.lon >= -180 && d.lon <= 180)) return null;
      return d;
    } catch (e) { return null; }
  }

  function kayitYaz(lat, lon, yuk) {
    var a = anahtar();
    if (!a) return;
    try {
      localStorage.setItem(a, JSON.stringify({
        lat: lat, lon: lon, yuk: yuk, t: Date.now(),
      }));
    } catch (e) {}
  }

  // Kameranin baktigi yer + yukseklik. widget_hava.js'in kullandigi
  // window.haritaMerkezi() yalniz lat/lon verir; yukseklik de gerekli
  // oldugu icin burada kendi okumamizi yapariz.
  function kameraKonumu() {
    var v = vw(), Cs = C();
    if (!v || !Cs) return null;
    try {
      var k = v.camera.positionCartographic;
      if (!k) return null;
      var lat = Cs.Math.toDegrees(k.latitude);
      var lon = Cs.Math.toDegrees(k.longitude);
      if (!isFinite(lat) || !isFinite(lon)) return null;
      return { lat: lat, lon: lon, yuk: k.height };
    } catch (e) { return null; }
  }

  // Kamera her durdugunda yazmak diske gereksiz yuk bindirir; kisilir.
  function kameraIzleyiciKur() {
    if (kameraIzleyiciKurulu) return;
    var v = vw();
    if (!v || !v.camera || !v.camera.moveEnd) return;
    try {
      v.camera.moveEnd.addEventListener(function () {
        if (!pilot) return;               // oturum yoksa yazma
        if (yazmaZaman) clearTimeout(yazmaZaman);
        yazmaZaman = setTimeout(function () {
          var k = kameraKonumu();
          if (k) kayitYaz(k.lat, k.lon, k.yuk);
        }, 1200);
      });
      kameraIzleyiciKurulu = true;
    } catch (e) {}
  }

  /* -------------------- GOKKUBBE ISARETI --------------------------
     Kurumsal adres isareti. Logo dokulu billboard + zemin halkasi +
     etiket. `disableDepthTestDistance` mevcut tum varliklarda
     kullanilan desendir: arazi kabarttiginda isaret dagin arkasinda
     kaybolmaz.
     --------------------------------------------------------------- */
  function isaretKur() {
    if (isaretKurulu) return;
    var v = vw(), Cs = C();
    if (!v || !Cs || !v.entities) return;
    try {
      isaretEnt = v.entities.add({
        id: "gokkubbe_merkez",
        position: Cs.Cartesian3.fromDegrees(GOKKUBBE.lon, GOKKUBBE.lat, 0),
        billboard: {
          image: "logo.png",
          width: 46, height: 46,
          verticalOrigin: Cs.VerticalOrigin.BOTTOM,
          heightReference: Cs.HeightReference.CLAMP_TO_GROUND,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
          // Cok uzaktan bakildiginda kucuk, yakinda tam boy
          scaleByDistance: new Cs.NearFarScalar(2000, 1.0, 900000, 0.45),
        },
        ellipse: {
          semiMinorAxis: 90, semiMajorAxis: 90,
          material: Cs.Color.fromCssColorString("#5cc8ff").withAlpha(0.16),
          outline: true,
          outlineColor: Cs.Color.fromCssColorString("#5cc8ff").withAlpha(0.65),
          outlineWidth: 2,
          heightReference: Cs.HeightReference.CLAMP_TO_GROUND,
        },
        label: {
          text: "GOKKUBBE TEKNOLOJI",
          font: "bold 11px 'Chakra Petch', sans-serif",
          fillColor: Cs.Color.fromCssColorString("#5cc8ff"),
          showBackground: true,
          backgroundColor: Cs.Color.BLACK.withAlpha(0.62),
          verticalOrigin: Cs.VerticalOrigin.TOP,
          pixelOffset: new Cs.Cartesian2(0, 8),
          heightReference: Cs.HeightReference.CLAMP_TO_GROUND,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
          // Dunya olceginde bakarken etiket yigilmasin
          distanceDisplayCondition:
            new Cs.DistanceDisplayCondition(0, 400000),
        },
      });
      isaretKurulu = true;
    } catch (e) {}
  }

  /* -------------------- ACILIS AKISI ----------------------------- */
  function acilisUygula() {
    if (acilisYapildi) return;
    var v = vw();
    if (!v) return;
    acilisYapildi = true;
    isaretKur();
    kameraIzleyiciKur();
    var k = kayitOku();
    if (k) {
      // Pilotun kendi son gorunumu
      if (typeof window.__haritaMerkezeGit === "function")
        window.__haritaMerkezeGit(k.lat, k.lon, k.yuk);
    } else {
      // Ilk giris: kurumsal adres
      if (typeof window.__haritaMerkezeGit === "function")
        window.__haritaMerkezeGit(GOKKUBBE.lat, GOKKUBBE.lon, GOKKUBBE.yuk);
    }
  }

  /* -------------------- DIS YUZEY -------------------------------- */
  // kullanici.js girisi basarili olunca cagirir.
  window.haritaPilotDegisti = function (eposta) {
    var yeni = (eposta ? String(eposta).trim().toLowerCase() : null) || null;
    if (yeni === pilot) { acilisUygula(); return; }
    pilot = yeni;
    acilisYapildi = false;      // yeni pilot icin acilis yeniden yapilir
    if (yazmaZaman) { clearTimeout(yazmaZaman); yazmaZaman = null; }
    acilisUygula();
  };

  // Oturum kapaninca yazmayi durdur; sonraki pilot bosluga yazmasin.
  window.haritaPilotCikti = function () {
    pilot = null;
    acilisYapildi = false;
    if (yazmaZaman) { clearTimeout(yazmaZaman); yazmaZaman = null; }
  };

  // Kurumsal adrese don (menu/kisayol eklenmek istenirse)
  window.haritaGokkubbeyeGit = function () {
    isaretKur();
    if (typeof window.__haritaMerkezeGit === "function")
      window.__haritaMerkezeGit(GOKKUBBE.lat, GOKKUBBE.lon, GOKKUBBE.yuk);
  };

  // Pilotun kayitli gorunumunu sifirla (bir sonraki girise kurumsal
  // adres gelir)
  window.haritaKonumSifirla = function () {
    var a = anahtar();
    if (!a) return false;
    try { localStorage.removeItem(a); return true; } catch (e) { return false; }
  };

  // harita.js genel ayar duyurusunda bunu sorar: pilotun kendi
  // kayitli gorunumu varsa duyuru kamerayi ZORLA oynatmaz.
  window.haritaPilotKaydiVar = function () {
    return kayitOku() !== null;
  };

  window.haritaGokkubbeKoordinat = function () {
    return { lat: GOKKUBBE.lat, lon: GOKKUBBE.lon };
  };

  /* -------------------- KISAYOL DUGMESI -------------------------
     v2.4.120 (IS62): harita arac grubundaki Gokkubbe dugmesi.

     BAGLAMA NEDEN BURADA: `haritaGokkubbeyeGit` bu dosyada
     tanimlidir ve bu dosya harita.js'ten SONRA yuklenir. Baglama
     harita.js icinde yapilsaydi islev o an henuz tanimsiz olurdu.
     Tanim ve baglamayi yan yana tutmak, ileride biri degistiginde
     digerinin gozden kacmasini da onler.

     `if (btn)` korumasi kardes dugmelerdeki desenin aynisidir:
     oge bulunamazsa sessizce gecilir, arayuz cokmez. -------- */
  (function kisayolDugmesiKur() {
    function kur() {
      var btn = document.getElementById("btnGokkubbeyeGit");
      if (!btn || btn.__gkBagli) return;
      btn.__gkBagli = true;
      btn.addEventListener("click", function () {
        window.haritaGokkubbeyeGit();
      });
    }
    if (document.readyState === "loading")
      document.addEventListener("DOMContentLoaded", kur);
    else kur();
  })();
})();
