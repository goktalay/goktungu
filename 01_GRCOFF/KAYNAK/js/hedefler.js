// =================================================================
// GOKTUNGU - HAVA IZI (TRAIL) + HEDEF GOSTERIMI + HEDEF KARTLARI + BIP SESI
// Bu dosya index.html'den mekanik olarak ayrilmistir; yukleme sirasi
// index.html'deki <script> sirasina baglidir (klasik script, ortak scope).
// =================================================================
// HAVA IZI (TRAIL): backend iz_gecmisi verisinden Cesium polyline cizer
// ---------------------------------------------------------------
let hedefIzGecmisi = {};   // id -> [Cartesian3, ...]
let hedefIzVarliklar = {}; // id -> Cesium polyline entity
let yetimIzVarliklar = {}; // id -> Cesium polyline entity (backend yetim)

// Her iz KENDI renginde cizilir: iz ID'sinden deterministik benzersiz renk
// (golden-angle dagilimi — ardisik ID'ler birbirinden uzak tonlar alir)
function izRengi(id){
  const ton = (Number(id) * 137.508) % 360;
  return "hsl(" + ton.toFixed(1) + ", 85%, 60%)";
}
function izGecmisiCiz(h){
  // h.iz_gecmisi: [[lat,lon,yuk], ...] backend'den gelir
  const gecmis = h.iz_gecmisi;
  if (!gecmis || gecmis.length < 2) return;
  const id = h.id;
  const pozlar = gecmis.map(n => Cesium.Cartesian3.fromDegrees(n[1], n[0], n[2]));
  hedefIzGecmisi[id] = pozlar;
  if (!hedefIzVarliklar[id]){
    hedefIzVarliklar[id] = viewer.entities.add({
      polyline: {
        positions: new Cesium.CallbackProperty(() => hedefIzGecmisi[id] || [], false),
        width: 2.5,
        material: new Cesium.PolylineGlowMaterialProperty({
          color: Cesium.Color.fromCssColorString(izRengi(id)).withAlpha(0.85),
          glowPower: 0.25, taperPower: 0.6,
        }),
      },
    });
  }
}

function izGecmisiSil(id){
  if (hedefIzVarliklar[id]){
    viewer.entities.remove(hedefIzVarliklar[id]);
    delete hedefIzVarliklar[id];
  }
  delete hedefIzGecmisi[id];
}

function yetimIzleriCiz(yetimler){
  // Backend'den gelen yetim izleri soluk cizgi olarak goster
  const canliIdler = new Set();
  for (const y of (yetimler || [])){
    canliIdler.add(y.id);
    if (yetimIzVarliklar[y.id]) continue; // zaten cizili
    if (!y.gecmis || y.gecmis.length < 2) continue;
    const pozlar = y.gecmis.map(n => Cesium.Cartesian3.fromDegrees(n[1], n[0], n[2]));
    yetimIzVarliklar[y.id] = viewer.entities.add({
      polyline: {
        positions: pozlar,
        width: 2.0,
        material: new Cesium.PolylineGlowMaterialProperty({
          color: Cesium.Color.fromCssColorString("#9fb4c7").withAlpha(0.4),
          glowPower: 0.2, taperPower: 0.6,
        }),
      },
    });
  }
  // Artik backend'de olmayan yetimleri kaldir
  for (const id of Object.keys(yetimIzVarliklar)){
    if (!canliIdler.has(Number(id))){
      viewer.entities.remove(yetimIzVarliklar[id]);
      delete yetimIzVarliklar[id];
    }
  }
}

function tumIzleriTemizle(){
  for (const id of Object.keys(hedefIzVarliklar)) viewer.entities.remove(hedefIzVarliklar[id]);
  for (const id of Object.keys(yetimIzVarliklar)) viewer.entities.remove(yetimIzVarliklar[id]);
  hedefIzVarliklar = {}; hedefIzGecmisi = {}; yetimIzVarliklar = {};
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({tip:"izleri_temizle"}));
}

// YENI HEDEF BIP SESI: klasik radar "dit" tonu (Web Audio, dosya gerektirmez)
// Tarayici otomatik oynatma kisiti: ilk kullanici etkilesiminde AudioContext acilir
// ---------------------------------------------------------------
let bipCtx = null;
const bilinenHedefIdler = new Set();
let sonBipZamani = 0;

function bipCal(){
  const simdi = Date.now();
  if (simdi - sonBipZamani < 250) return;   // ust uste bip'leri seyrelt
  sonBipZamani = simdi;
  try {
    if (!bipCtx) bipCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (bipCtx.state === "suspended") bipCtx.resume();
    const t0 = bipCtx.currentTime;
    const osc = bipCtx.createOscillator();
    const kazanc = bipCtx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(1100, t0);   // klasik radar ping tonu
    kazanc.gain.setValueAtTime(0.0001, t0);
    kazanc.gain.exponentialRampToValueAtTime(0.25, t0 + 0.01);  // hizli atak
    kazanc.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.18); // kisa sonum
    osc.connect(kazanc); kazanc.connect(bipCtx.destination);
    osc.start(t0); osc.stop(t0 + 0.2);
  } catch(e){}
}
// Otomatik oynatma kisitini asmak icin ilk tiklamada ses baglamini hazirla
document.addEventListener("click", function sesiAc(){
  try {
    if (!bipCtx) bipCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (bipCtx.state === "suspended") bipCtx.resume();
  } catch(e){}
  document.removeEventListener("click", sesiAc);
});

// Hedef hareket yonu: iz gecmisinin son iki noktasindan bearing (derece, kuzeyden CW)
// Not: h.azimut radar->hedef acisidir, hareket yonu DEGILDIR.
function hedefHareketYonu(h){
  const g = h.iz_gecmisi;
  if (g && g.length >= 2){
    // Son nokta ile yeterince geride bir nokta sec (gurultuyu azalt)
    const son = g[g.length - 1];
    let onceki = g[g.length - 2];
    for (let i = g.length - 2; i >= 0 && i >= g.length - 6; i--){
      onceki = g[i];
      const dlat = son[0] - onceki[0], dlon = son[1] - onceki[1];
      if (Math.abs(dlat) > 1e-6 || Math.abs(dlon) > 1e-6) break;
    }
    const lat1 = onceki[0] * Math.PI/180, lat2 = son[0] * Math.PI/180;
    const dLon = (son[1] - onceki[1]) * Math.PI/180;
    const y = Math.sin(dLon) * Math.cos(lat2);
    const x = Math.cos(lat1)*Math.sin(lat2) - Math.sin(lat1)*Math.cos(lat2)*Math.cos(dLon);
    if (Math.abs(y) > 1e-12 || Math.abs(x) > 1e-12){
      const b = Math.atan2(y, x) * 180/Math.PI;
      return ((b % 360) + 360) % 360;
    }
  }
  return null;   // yon bilinmiyor
}

function radarHedefleriGuncelle(hedefler){
  // hedefler: backend'den gelen islenmiş iz listesi (radar_izler)
  sonRadarHedefler = hedefler || [];
  const t = D();
  const canliIdler = new Set();

  // Bip: backend bip=true isaretlemişse cal
  for (const h of sonRadarHedefler){
    if (h.bip) bipCal();
  }

  for (const h of sonRadarHedefler){
    if (!window.gecerliKonumMu(h.lat, h.lon)) continue; /* FAZ18-IS29C */
    canliIdler.add(h.id);
    izGecmisiCiz(h);   // hava izi polyline
    const tipAd = (t.radarTipleri && t.radarTipleri[h.tip]) || h.tip;
    const renk = radarHedefRengi(h.tip);
    const durumEk = (h.durum === "ADAY") ? " [" + (t.rhAday || "ADAY") + "]"
                  : (h.durum === "SUZULEN") ? " [" + (t.rhKayip || "KAYIP") + "]" : "";
    const etiket = "R" + h.id + " " + tipAd + durumEk +
      "\n" + t.rhMesafe + ":" + Math.round(h.mesafe) + "m" +
      " " + t.rhYukseklik + ":" + Math.round(h.yukseklik) + "m" +
      "\n" + t.rhHiz + ":" + h.hiz.toFixed(1) + "m/s (" + (h.hiz * 3.6).toFixed(1) + "km/h)" +
      " " + t.rhSnr + ":" + h.snr.toFixed(0) + "dB";
    const yuk = Math.max(0, h.yukseklik);
    const poz = Cesium.Cartesian3.fromDegrees(h.lon, h.lat, yuk);
    const dikeyPoz = Cesium.Cartesian3.fromDegreesArrayHeights(
      [h.lon, h.lat, 0, h.lon, h.lat, yuk]);

    // Hareket yonu (iz gecmisinden) — yalniz yon cizgisi icin kullanilir
    const hYon = hedefHareketYonu(h);
    // Yon cizgisi uc noktasi (hizla orantili uzunluk)
    let hYonPoz = null;
    if (hYon !== null){
      const uz = yonCizgiUzunluk(h.hiz);
      const [hyLat, hyLon] = bearingOffset(h.lat, h.lon, hYon, uz);
      hYonPoz = Cesium.Cartesian3.fromDegreesArrayHeights(
        [h.lon, h.lat, yuk, hyLon, hyLat, yuk]);
    }

    // v2.4.29: prizma ikon + arazi yukseklik referansi.
    // `h.yukseklik` radar olcumu olup ZEMINE GORE yuksekliktir; bu nedenle
    // dogru referans RELATIVE_TO_GROUND'dur. Onceki surumlerde konum
    // elipsoid referansina veriliyordu ve terrain acikken hedefler
    // arazinin altinda kalip kamera dondukce kayiyordu.
    // v2.4.30: hedef ikonu artik CIFT PIRAMIT (bipiramit / plumbob elmas).
    // v2.4.31: BASARIM — elmas artik ayri bir primitive DEGIL, entity'nin
    // `ellipsoid` ozelligidir (`slicePartitions:4` + `stackPartitions:2`
    // kare tabanli cift piramit verir). Hedef sayisi radar taramasiyla
    // hizla artabildigi icin kazanc dron tarafindan daha buyuktur.
    // Renk hedef tipine gore atanan renktir ve KORUNUR.
    const hPrizmaMod = (typeof window.ikonPrizmaMi === "function")
      ? window.ikonPrizmaMi() : true;
    const hPrizmaSecenek = { lat: h.lat, lon: h.lon, yuk: yuk,
                             yon: (hYon !== null ? hYon : 0), renk: renk };

    let e = radarHedefVarliklar[h.id];
    if (!e){
      const hTanim = {
        position: poz,
        label: {
          show: false,   // v2.4.202: fareyle uzerine gelince gorunur (harita_hover.js)
          text: etiket,
          font: "bold 12px Consolas, monospace",
          fillColor: Cesium.Color.fromCssColorString(renk),
          style: Cesium.LabelStyle.FILL,
          showBackground: true,
          backgroundColor: Cesium.Color.BLACK.withAlpha(0.72),
          backgroundPadding: new Cesium.Cartesian2(7, 5),
          verticalOrigin: Cesium.VerticalOrigin.TOP,
          pixelOffset: new Cesium.Cartesian2(0, 18),
          heightReference: Cesium.HeightReference.RELATIVE_TO_GROUND,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
        polyline: {
          positions: dikeyPoz,
          width: 2,
          clampToGround: false,
          material: new Cesium.PolylineDashMaterialProperty({
            color: Cesium.Color.fromCssColorString(renk).withAlpha(0.9),
            dashLength: 12,
          }),
        },
      };
      if (!hPrizmaMod){
        hTanim.billboard = {
          image: elmasIkon(renk),
          width: 30, height: 30,
          verticalOrigin: Cesium.VerticalOrigin.CENTER,
          heightReference: Cesium.HeightReference.RELATIVE_TO_GROUND,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        };
      }
      if (hPrizmaMod && window.PrizmaIkon){
        // Elmas gosterimi entity TANIMINA girer (sonradan ozellik eklemek
        // Cesium'da gorsel bileseni yeniden kurdurur).
        hTanim.ellipsoid = window.PrizmaIkon.elmasTanimi(hPrizmaSecenek);
        // FAZ18-IS11-HEDEF-MESAFE: ELMAS YALNIZ YAKIN GORUSTE.
        // Elmas METRE tabanlidir (radii 15/15/20.5) ve kamera
        // uzaklastikca kuculur. Olculen degerler (fovy 60, 1080 px):
        //   1200 m -> 23.4 px | 2500 m -> 11.2 px | 3000 m -> 9.4 px
        // Radar azami menzili 20 km'dir (radar_gorsel.js IZGARA_MENZIL)
        // ve operator tarama alanini gormek icin kamerayi genellikle
        // 20-30 km'ye cikarir; o mesafede elmas ~1.4 px'e duser.
        // Dron ikonundan FARKLI olarak radar hedefleri TEK TEK degil
        // TOPLU izlenir, yani kusur burada daha agir goruluyordu.
        // Esik dron ile ayni (2500 m): elmas boyutu ayni oldugu icin
        // piksel egrisi ayni, ayrica ayni sahnede dron nokta olurken
        // hedef elmas kalirsa operator iki gosterimi farkli
        // anlamlandirirdi.
        hTanim.ellipsoid.distanceDisplayCondition =
          new Cesium.DistanceDisplayCondition(0, 2500);
        // Uzak gorus gosterimi: `pixelSize` PIKSEL cinsindendir ve
        // mesafeden BAGIMSIZDIR, bu yuzden 30 km'de de gorunur.
        // Gecis Cesium tarafinda yapilir -> her karede JS hesabi YOK,
        // v2.4.31 basarim kazanci korunur.
        hTanim.point = {
          pixelSize: 14,
          color: Cesium.Color.fromCssColorString(renk),
          // Koyu cerceve: acik zemin ve uydu goruntusu uzerinde de
          // ayirt edilir kalmasini saglar.
          outlineColor: Cesium.Color.BLACK.withAlpha(0.85),
          outlineWidth: 2,
          // Elmasla AYNI yukseklik sozlesmesi: `h.yukseklik` radar
          // olcumu olup ZEMINE goredir (bkz. v2.4.29 notu).
          heightReference: Cesium.HeightReference.RELATIVE_TO_GROUND,
          distanceDisplayCondition:
            new Cesium.DistanceDisplayCondition(2500, 1.0e9),
          // Etiketle ayni davranis: arazi arkasinda kalsa da gorunur.
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        };
        hTanim.position = window.PrizmaIkon.elmasKonumu(
          h.lat, h.lon, yuk, false, undefined);
        hTanim.orientation = window.PrizmaIkon.elmasYonu(
          h.lat, h.lon, yuk, (hYon !== null ? hYon : 0), false, undefined);
      }
      e = viewer.entities.add(hTanim);
      if (hPrizmaMod && window.PrizmaIkon){
        e._elmasRenk = renk;
        e._elmasAlfa = window.PrizmaIkon.ALFA;
        e._elmasZemine = false;
        e._bipiramit = e;      // geriye uyum: artik entity'nin kendisi
      }
      radarHedefVarliklar[h.id] = e;
    } else {
      e.position = poz;
      e.label.text = etiket;
      if (e.ellipsoid && window.PrizmaIkon){
        // Konum VE yon her radar guncellemesinde tazelenir. Soluk (SUZULEN)
        // durumundaki opaklik `hedefSolukYap` tarafindan yonetildigi icin
        // burada mevcut opaklik korunur.
        // DIKKAT: yukaridaki `e.position = poz` atamasi merkez kaydirmasini
        // icermez; `bpTazele` konumu dogru degerle UZERINE yazar.
        window.PrizmaIkon.bpTazele(e, Object.assign({}, hPrizmaSecenek,
          { alfa: window.PrizmaIkon.ALFA * (e._soluk ? 0.45 : 1.0) }));
      } else if (e.polygon){
        window.PrizmaIkon.tazele(e, hPrizmaSecenek);
      } else if (e.billboard){
        e.billboard.image = elmasIkon(renk);
      }
      e.label.fillColor = Cesium.Color.fromCssColorString(renk);
      e.polyline.positions = dikeyPoz;
      e.polyline.material = new Cesium.PolylineDashMaterialProperty({
        color: Cesium.Color.fromCssColorString(renk).withAlpha(0.9),
        dashLength: 12,
      });
    }
    // Hedef yon cizgisi (ayri entity; yon bilinmiyorsa gizle)
    if (hYonPoz){
      if (!e._yonCizgi){
        e._yonCizgi = viewer.entities.add({
          id: "hedef_yon_" + h.id,
          polyline: {
            positions: hYonPoz,
            width: 3,
            clampToGround: false,
            material: new Cesium.PolylineArrowMaterialProperty(
              Cesium.Color.fromCssColorString(renk).withAlpha(0.95)),
          },
        });
      } else {
        e._yonCizgi.show = true;
        e._yonCizgi.polyline.positions = hYonPoz;
        e._yonCizgi.polyline.material = new Cesium.PolylineArrowMaterialProperty(
          Cesium.Color.fromCssColorString(renk).withAlpha(e._soluk ? 0.3 : 0.95));
      }
    } else if (e._yonCizgi){
      e._yonCizgi.show = false;
    }
    // Durum bazli gorsellestirme: ADAY ve SUZULEN soluk, TEYITLI tam
    const solukOlmali = (h.durum === "ADAY" || h.durum === "SUZULEN");
    if (!!e._soluk !== solukOlmali) hedefSolukYap(e, solukOlmali);
  }

  // Backend'de olmayan izlerin entity ve kartlarini kaldir
  // ISTISNA: takipteki hedefler haritadan HICBIR SEKILDE kaldirilmaz;
  // yalnizca soluk gosterilir (son bilinen konumda kalir)
  for (const id of Object.keys(radarHedefVarliklar)){
    const nid = Number(id);
    if (!canliIdler.has(nid)){
      if (typeof takipIdler !== "undefined" && takipIdler.has(nid)){
        hedefSolukYap(radarHedefVarliklar[id], true);
        continue;
      }
      if (radarHedefVarliklar[id]._yonCizgi)
        viewer.entities.remove(radarHedefVarliklar[id]._yonCizgi);
      hedefBipiramitSil(radarHedefVarliklar[id]);
      viewer.entities.remove(radarHedefVarliklar[id]);
      delete radarHedefVarliklar[id];
      const kart = document.getElementById("rh-" + id);
      if (kart) kart.remove();
      izGecmisiSil(nid);
    }
  }

  // Panel ozeti
  if (radarHedefOzet) radarHedefOzet.textContent = radarBagli
    ? t.radarHedefSayi(sonRadarHedefler.length) : "";

  // Sol panel hedef kartlari
  radarHedefKartlariGuncelle();
}

// ---------------------------------------------------------------
// HEDEF KALICILIGI: SUZULEN (kayip) hedef izGorunmeSuresi boyunca soluk kalir
// (silme karari takipcide; asagidaki periyodik cagri radar guncellemesi
// gelmese bile suzulme suresinin islemesini saglar)
// ---------------------------------------------------------------
// v2.4.31: elmas artik entity OZELLIGIDIR; entity kaldirilinca
// kendiliginden gider. v2.4.30'da ayri primitive oldugu icin dort ayri
// silme noktasinda acik temizlik gerekiyordu. Yardimci ISLEVSIZ hale
// geldi ancak cagrilari kaldirmak yerine korunur: kip gecisinde
// (`prizmaKipiUygula`) gosterimin entity yasarken kaldirilmasi hala
// gerekebilir ve tek bir gecis noktasi tutmak ileride guvenlidir.
function hedefBipiramitSil(e){
  if (e && e.ellipsoid && window.PrizmaIkon)
    window.PrizmaIkon.bpSil(e);
}

function hedefSolukYap(e, soluk){
  if (!e) return;
  const alfa = soluk ? 0.35 : 1.0;
  if (e.billboard) e.billboard.color = Cesium.Color.WHITE.withAlpha(alfa);
  // v2.4.30: bipiramit kipinde dolgu opakligi taban %80 uzerinden carpanla
  // azaltilir (dogrudan 0.35 yazilirsa SUZULEN hedef normalden daha OPAK
  // gorunurdu).
  // v2.4.31: gosterim entity'nin `ellipsoid` ozelligi; renk `_elmasRenk`
  // alaninda tutulur (v2.4.30'daki `_gcsRenk` primitive alaniydi ve artik
  // yoktur — duzeltilmezse renk `undefined` gecip beyaza donerdi).
  if (e.ellipsoid && window.PrizmaIkon){
    window.PrizmaIkon.bpAlfaAyarla(e, e._elmasRenk, soluk ? 0.45 : 1.0);
  }
  // FAZ18-IS11-HEDEF-MESAFE: uzak gorus noktasi da soldurulur.
  // ZORUNLU: nokta gosterimi soldurulmazsa 2500 m uzerinde SUZULEN
  // hedef etkin hedefle AYNI parlaklikta gorunur ve operator suzulen
  // izi canli sanar. Elmasla ayni carpan (0.45) uygulanir.
  if (e.point && e._elmasRenk){
    const pA = soluk ? 0.45 : 1.0;
    e.point.color =
      Cesium.Color.fromCssColorString(e._elmasRenk).withAlpha(pA);
    e.point.outlineColor = Cesium.Color.BLACK.withAlpha(0.85 * pA);
  }
  // v2.4.29: prizma kipinde dolgu ve kenar opakligi birlikte azaltilir.
  // Prizmanin taban opakligi %80 oldugundan carpan uzerinden hesaplanir
  // (dogrudan 0.35 yazilirsa SUZULEN hedef normalden daha OPAK gorunur).
  if (e.polygon && e.polygon.material){
    try {
      const mevcut = e.polygon.material.color
        ? e.polygon.material.color.getValue()
        : e.polygon.material.getValue().color;
      const taban = window.PrizmaIkon ? window.PrizmaIkon.ALFA : 0.8;
      e.polygon.material = mevcut.withAlpha(taban * (soluk ? 0.45 : 1.0));
      if (e.polygon.outlineColor){
        e.polygon.outlineColor = e.polygon.outlineColor.getValue()
          .withAlpha(soluk ? 0.4 : 0.95);
      }
    } catch (err) { /* materyal bicimi beklenmedik: gorsel degisiklik atlanir */ }
  }
  if (e.label){
    e.label.fillColor = e.label.fillColor.getValue().withAlpha(alfa);
    e.label.backgroundColor = Cesium.Color.BLACK.withAlpha(soluk ? 0.35 : 0.72);
  }
  if (e.polyline && e.polyline.material && e.polyline.material.color){
    e.polyline.material.color =
      e.polyline.material.color.getValue().withAlpha(soluk ? 0.3 : 0.9);
  }
  if (e._yonCizgi && e._yonCizgi.polyline && e._yonCizgi.polyline.material &&
      e._yonCizgi.polyline.material.color){
    e._yonCizgi.polyline.material.color =
      e._yonCizgi.polyline.material.color.getValue().withAlpha(soluk ? 0.3 : 0.95);
  }
  e._soluk = soluk;
}

// (Suzulme/coasting suresi artik backend'de islenir; frontend'de zamanlayici gerekmez)

// ---------------------------------------------------------------
// HEDEF TAKIBI: takip edilen hedefler alt panelde listelenir ve
// haritadan HICBIR SEKILDE kaldirilmaz (takipci dususe bile).
// Takip kumesi localStorage'da saklanir (sayfa yenilemede korunur).
// ---------------------------------------------------------------
const TAKIP_KEY = "goktungu_takip_idler";
let takipIdler = new Set();
try {
  const sakli = JSON.parse(localStorage.getItem(TAKIP_KEY) || "[]");
  if (Array.isArray(sakli)) takipIdler = new Set(sakli.map(Number));
} catch(e){}
function takipKaydet(){
  try { localStorage.setItem(TAKIP_KEY, JSON.stringify([...takipIdler])); } catch(e){}
}
// Takipteki hedeflerin son bilinen verisi (takipci dusurse bile korunur)
let takipSonVeri = {};   // id -> h (son bilinen iz verisi)

function hedefeFokuslan(id){
  const h = sonRadarHedefler.find(x => x.id === id) || takipSonVeri[id];
  if (!h || !window.gecerliKonumMu(h.lat, h.lon)) return; /* FAZ18-IS29C */
  viewer.camera.flyTo({
    destination: Cesium.Cartesian3.fromDegrees(h.lon, h.lat, Math.max(0, h.yukseklik || 0) + 1200),
    orientation: { heading: 0, pitch: Cesium.Math.toRadians(-90), roll: 0 },
    duration: 1.2,
  });
}

function takibeAl(id){
  takipIdler.add(id);
  takipKaydet();
  const h = sonRadarHedefler.find(x => x.id === id);
  if (h) takipSonVeri[id] = h;
  radarHedefKartlariGuncelle();
}

// Menubar: TUM TAKIBI BIRAK - takipteki tum hedeflerin takibini birakir
window.tumTakibiBirak = function(){
  if (takipIdler.size === 0){
    if (typeof konsolYaz === "function")
      konsolYaz("RADAR", (D().mbTumTakipYok || "Takipte hedef yok."), "bilgi");
    return;
  }
  const say = takipIdler.size;
  const metin = (typeof onayMetni === "function")
    ? onayMetni("onayTumTakip", {say: say})
    : (say + " hedefin takibi birakilacak. Emin misiniz?");
  onayIste(metin, () => {
    [...takipIdler].forEach(id => takiptenCikar(id));
    if (typeof konsolYaz === "function")
      konsolYaz("RADAR", (D().mbTumTakipTamam || "Tum hedef takipleri birakildi.").replace("{say}", say), "basari");
  });
};

function takiptenCikar(id){
  takipIdler.delete(id);
  takipKaydet();
  const kart = document.getElementById("rh-" + id);
  if (kart) kart.remove();
  // Hedef artik canli degilse haritadan da kaldir
  const canli = sonRadarHedefler.some(x => x.id === id);
  if (!canli && radarHedefVarliklar[id]){
    hedefBipiramitSil(radarHedefVarliklar[id]);
    viewer.entities.remove(radarHedefVarliklar[id]);
    delete radarHedefVarliklar[id];
    izGecmisiSil(id);
  }
  delete takipSonVeri[id];
  radarHedefKartlariGuncelle();
}

// HEDEFI KALDIR: hedefi haritadan, sol panelden ve backend iz tablosundan
// tamamen cikarir (operator karari). Takipteyse takipten de cikar.
function hedefKaldir(id){
  const nid = Number(id);
  // Takipten cikar (varsa)
  takipIdler.delete(nid);
  takipKaydet();
  delete takipSonVeri[nid];
  // Haritadan entity ve izi kaldir
  if (radarHedefVarliklar[nid]){
    hedefBipiramitSil(radarHedefVarliklar[nid]);
    viewer.entities.remove(radarHedefVarliklar[nid]);
    delete radarHedefVarliklar[nid];
  }
  izGecmisiSil(nid);
  // Sol panel ve takip listesindeki karti kaldir
  const kart = document.getElementById("rh-" + nid);
  if (kart) kart.remove();
  // Yerel iz listesinden dusur (bir sonraki guncellemeye kadar geri gelmesin)
  sonRadarHedefler = sonRadarHedefler.filter(x => x.id !== nid);
  // Backend'e bildir: takipci iz tablosundan silinsin ki hedef geri gelmesin
  try {
    if (typeof ws !== "undefined" && ws && ws.readyState === 1)
      ws.send(JSON.stringify({tip: "iz_sil", id: nid}));
  } catch(e){}
  radarHedefKartlariGuncelle();
}

// Sol paneldeki radar hedef kartlarini (TESPIT + TAKIP) tazeler
const radarHedefListesi = document.getElementById("radarHedefListesi");
const takipHedefListesi = document.getElementById("takipHedefListesi");
// Menu item helper'lari
function _rhMenuItem(ikon, metin, cb) {
  const el = document.createElement("div");
  el.className = "dk-menu-item";
  el.innerHTML = "<i class='fa-solid " + ikon + "'></i><span>" + metin + "</span>";
  el.addEventListener("click", (ev) => {
    ev.stopPropagation();
    document.querySelectorAll(".dk-menu-dropdown.acik").forEach(m => m.classList.remove("acik"));
    cb();
  });
  return el;
}
function _rhMenuAyrac() {
  const el = document.createElement("div");
  el.className = "dk-menu-ayrac";
  return el;
}

function radarHedefKartlariGuncelle(){
  // v2.4.227: sol dock (Tespit/Takip listeleri) kaldirildi; kartlar cizilmez
  if (!radarHedefListesi || !takipHedefListesi) return;
  const t = D();
  const canli = new Set();
  // Kart listesi: canli izler + canli olmayan ama takipte olan izler
  const gosterilecek = [...sonRadarHedefler];
  const canliIdSet = new Set(sonRadarHedefler.map(h => h.id));
  for (const id of takipIdler){
    if (!canliIdSet.has(id) && takipSonVeri[id]) gosterilecek.push(takipSonVeri[id]);
  }
  for (const h of gosterilecek){
    const takipte = takipIdler.has(h.id);
    const hCanli = canliIdSet.has(h.id);
    if (hCanli && takipte) takipSonVeri[h.id] = h;   // son veriyi tazele
    canli.add("rh-" + h.id);
    let kart = document.getElementById("rh-" + h.id);
    const tipAd = (t.radarTipleri && t.radarTipleri[h.tip]) || h.tip;
    const renk = radarHedefRengi(h.tip);
    if (!kart){
      kart = document.createElement("div");
      kart.className = "dron-kart";
      kart.id = "rh-" + h.id;
      kart.innerHTML =
        '<div class="dron-kart-baslik kapali">' +
          '<span class="rh-kare"></span>' +
          '<span class="rh-baslik"></span>' +
          '<span class="rh-tb">' +
            '<button class="dk-menu-btn rh-menu-tetik" title=""><i class="fa-solid fa-ellipsis-vertical"></i></button>' +
            '<div class="dk-menu-dropdown rh-menu"></div>' +
          '</span></div>' +
        '<div class="dron-kart-icerik gizli">' +
          '<div><span class="etiket" data-rh="mesafe"></span><span class="rh-mesafe">-</span></div>' +
          '<div><span class="etiket" data-rh="yukseklik"></span><span class="rh-yukseklik">-</span></div>' +
          '<div><span class="etiket" data-rh="hiz"></span><span class="rh-hiz">-</span></div>' +
          '<div><span class="etiket" data-rh="azimut"></span><span class="rh-azimut">-</span></div>' +
          '<div><span class="etiket" data-rh="snr"></span><span class="rh-snr">-</span></div>' +
          '<div class="rh-etiket-satir gizli"></div>' +
        '</div>';
      const kb = kart.querySelector(".dron-kart-baslik");
      const ki = kart.querySelector(".dron-kart-icerik");
      kb.addEventListener("click", () => {
        kb.classList.toggle("kapali");
        ki.classList.toggle("gizli");
      });
      // Acilir menu: baslik ac/kapa tetiklenmesin diye stopPropagation
      const hid = h.id;
      const menuTetik = kart.querySelector(".rh-menu-tetik");
      const menuDiv   = kart.querySelector(".rh-menu");
      const menuAna   = menuTetik.parentNode; // .rh-tb — kapatirken geri tasimak icin

      function _menuKapat() {
        menuDiv.classList.remove("acik");
        // Overflow/klipleme sorununu onlemek icin element body'e tasindi;
        // kapatirken orijinal ebeveynine geri al ki kart.querySelector calissa.
        if (menuDiv.parentNode === document.body) menuAna.appendChild(menuDiv);
      }

      menuTetik.addEventListener("click", (ev) => {
        ev.stopPropagation();
        // Diger acik menuleri kapat
        document.querySelectorAll(".dk-menu-dropdown.acik").forEach(m => {
          if (m !== menuDiv) { m.classList.remove("acik"); }
        });
        if (menuDiv.classList.contains("acik")) {
          _menuKapat();
        } else {
          // Body'e tasi: overflow:hidden klipleme sorununu cozer
          document.body.appendChild(menuDiv);
          // Mouse pozisyonunun hemen altinda konumlandir
          const genislik = 170;
          let sol = ev.clientX;
          if (sol + genislik > window.innerWidth - 4) sol = window.innerWidth - genislik - 4;
          if (sol < 4) sol = 4;
          let ust = ev.clientY + 6;
          if (ust + 180 > window.innerHeight - 4) ust = ev.clientY - 180;
          menuDiv.style.left = sol + "px";
          menuDiv.style.top  = ust + "px";
          menuDiv.classList.add("acik");
        }
      });
      // Menu disina tiklaninca kapat
      document.addEventListener("click", (ev) => {
        if (menuDiv.classList.contains("acik") &&
            !menuDiv.contains(ev.target) &&
            ev.target !== menuTetik && !menuTetik.contains(ev.target))
          _menuKapat();
      });
      (takipte ? takipHedefListesi : radarHedefListesi).appendChild(kart);
    }
    // Kart dogru listede mi? (takip durumu degistiyse tasi)
    const hedefListe = takipte ? takipHedefListesi : radarHedefListesi;
    if (kart.parentElement !== hedefListe) hedefListe.appendChild(kart);
    kart.classList.toggle("takipte", takipte);
    // Acilir menu icerigini duruma gore guncelle
    const menuDiv2 = kart.querySelector(".rh-menu");
    if (menuDiv2) {
      const hid2 = h.id;
      menuDiv2.innerHTML = "";
      // Fokuslan (her zaman)
      menuDiv2.appendChild(_rhMenuItem("fa-location-crosshairs", t.rhFokus || "Hedefe Fokuslan", () => hedefeFokuslan(hid2)));
      if (!takipte) {
        menuDiv2.appendChild(_rhMenuItem("fa-bullseye", t.rhTakipEt || "Takip Et", () => takibeAl(hid2)));
      } else {
        menuDiv2.appendChild(_rhMenuItem("fa-xmark", t.rhTakiptenCik || "Takipten \u00c7\u0131k", () => takiptenCikar(hid2)));
        menuDiv2.appendChild(_rhMenuAyrac());
        menuDiv2.appendChild(_rhMenuItem("fa-tower-broadcast", t.angTelemetriSecenek || "Telemetri ile Angajman", () => angajmanPopupAc("hedef", hid2)));
        menuDiv2.appendChild(_rhMenuItem("fa-satellite-dish", t.angiBaslik || "Angajman \u0130zle", () => {
          if (typeof window.angajmanIzleAcKapat === "function") window.angajmanIzleAcKapat();
        }));
      }
    }
    const b = kart.querySelector(".rh-baslik");
    const durumEk = (!hCanli && takipte) ? " \u00b7 " + (t.rhTakipKayip || "S\u0130NYAL YOK")
                  : (h.durum === "ADAY") ? " \u00b7 " + (t.rhAday || "ADAY")
                  : (h.durum === "SUZULEN") ? " \u00b7 " + (t.rhKayip || "KAYIP") : "";
    b.textContent = "R" + h.id + " \u00b7 " + tipAd + durumEk;
    // Baslik metni sabit renkte kalir; tip rengi baslik basindaki kare noktada gosterilir
    const kare = kart.querySelector(".rh-kare");
    if (kare) kare.style.background = renk;
    // Siniflandirma kaynagi ve guveni tooltip'te (kural/ml kestirimiyse)
    const kb2 = kart.querySelector(".dron-kart-baslik");
    if (kb2){
      if (h.tip_kaynak && h.tip_kaynak !== "radar" && h.tip_guven > 0){
        kb2.title = tipAd + " · " + (t.rhGuven || "G\u00fcven") + ": %" +
                    Math.round(h.tip_guven * 100) +
                    " (" + h.tip_kaynak.toUpperCase() + ")";
      } else {
        kb2.title = "";
      }
    }
    kart.classList.toggle("kayip", h.durum === "SUZULEN" || h.durum === "ADAY" || (!hCanli && takipte));
    kart.querySelector('[data-rh="mesafe"]').textContent    = t.rhMesafe;
    kart.querySelector('[data-rh="yukseklik"]').textContent = t.rhYukseklik;
    kart.querySelector('[data-rh="hiz"]').textContent       = t.rhHiz;
    kart.querySelector('[data-rh="azimut"]').textContent    = t.rhAzimut || "AZ";
    kart.querySelector('[data-rh="snr"]').textContent       = t.rhSnr;
    kart.querySelector(".rh-mesafe").textContent =
      (h.mesafe !== undefined) ? Math.round(h.mesafe) + " m" : "-";
    kart.querySelector(".rh-yukseklik").textContent =
      (h.yukseklik !== undefined) ? Math.round(h.yukseklik) + " m" : "-";
    kart.querySelector(".rh-hiz").textContent =
      (h.hiz !== undefined) ? h.hiz.toFixed(1) + " m/s (" + (h.hiz * 3.6).toFixed(1) + " km/h)" : "-";
    kart.querySelector(".rh-azimut").textContent =
      (h.azimut !== undefined) ? h.azimut.toFixed(0) + "\u00b0" : "-";
    kart.querySelector(".rh-snr").textContent =
      (h.snr !== undefined) ? h.snr.toFixed(0) + " dB" : "-";
    etiketSatiriGuncelle(kart, h);
  }
  // Takipciden dusen (ve takipte olmayan) izlerin kartlarini kaldir
  for (const kart of Array.from(radarHedefListesi.children)){
    if (!canli.has(kart.id)) kart.remove();
  }
  for (const kart of Array.from(takipHedefListesi.children)){
    if (!canli.has(kart.id)) kart.remove();
  }
  // Bos panel gostergeleri
  const hedefBos = document.getElementById("hedefYokKutu");
  if (hedefBos) hedefBos.classList.toggle("gizli", radarHedefListesi.children.length > 0);
  const takipBos = document.getElementById("takipYokKutu");
  if (takipBos) takipBos.classList.toggle("gizli", takipHedefListesi.children.length > 0);
}

// ---------------------------------------------------------------------
// HARITADA HEDEF TIKLAMA MENUSU: hedef ikonuna sol tiklaninca
// "Hedefi Takip Et" / "Hedefi Kaldir" menusu acilir.
// dronlar.js'deki harita click dinleyicisinden delege edilir
// (once dron aranir, dron degilse buraya dusulur).
// ---------------------------------------------------------------------
let _hedefMenuEl = null;
function hedefMenuKapat(){
  if (_hedefMenuEl){ _hedefMenuEl.remove(); _hedefMenuEl = null; }
  document.removeEventListener("pointerdown", _hedefMenuDisTik, true);
}
function _hedefMenuDisTik(ev){
  if (_hedefMenuEl && !ev.target.closest(".dk-menu-dropdown")) hedefMenuKapat();
}

function hedefMenuAc(id, poz){
  hedefMenuKapat();
  // v2.4.23: dron dropdown menusu kaldirildi (ISLEMLER popup'i geldi);
  // guvenlik icin fonksiyon hala varsa cagirilir.
  if (typeof dronMenuKapat === "function") dronMenuKapat();
  const t = D();
  const nid = Number(id);
  const h = sonRadarHedefler.find(x => x.id === nid) || takipSonVeri[nid];
  const menu = document.createElement("div");
  menu.className = "dk-menu-dropdown acik";
  menu.style.position = "fixed";
  menu.style.zIndex = "2500";

  // Baslik: hedef kimligi
  const bas = document.createElement("div");
  bas.className = "dk-menu-item";
  bas.style.pointerEvents = "none";
  bas.style.opacity = ".65";
  const tipAd = h ? (((t.radarTipleri && t.radarTipleri[h.tip]) || h.tip)) : "";
  bas.innerHTML = "<i class='fa-solid fa-crosshairs'></i><span><strong>R" + nid + "</strong> " + tipAd + "</span>";
  menu.appendChild(bas);
  const ayrac = document.createElement("div");
  ayrac.className = "dk-menu-ayrac";
  menu.appendChild(ayrac);

  const takipte = takipIdler.has(nid);
  if (!takipte){
    menu.appendChild(_rhMenuItem("fa-bullseye", t.rhTakibeAl || "Hedefi Takip Et", () => {
      hedefMenuKapat(); takibeAl(nid);
    }));
  } else {
    menu.appendChild(_rhMenuItem("fa-ban", t.rhTakiptenCik || "Takipten \u00c7\u0131kar", () => {
      hedefMenuKapat(); takiptenCikar(nid);
    }));
  }
  const kaldirEl = _rhMenuItem("fa-trash-can", t.rhHedefKaldir || "Hedefi Kald\u0131r", () => {
    hedefMenuKapat(); hedefKaldir(nid);
  });
  kaldirEl.classList.add("tehlikeli");
  menu.appendChild(kaldirEl);

  document.body.appendChild(menu);
  // Konumlandir (ekran disina tasma korumasi)
  const mw = menu.offsetWidth || 180, mh = menu.offsetHeight || 120;
  menu.style.left = Math.min(poz.x, window.innerWidth - mw - 8) + "px";
  menu.style.top = Math.min(poz.y, window.innerHeight - mh - 8) + "px";
  _hedefMenuEl = menu;
  // Dis tiklamada kapat (capture: harita tiklamasindan once yakala)
  setTimeout(() => document.addEventListener("pointerdown", _hedefMenuDisTik, true), 0);
}

// dronlar.js harita click dinleyicisinden cagrilir: tiklanan noktada
// radar hedefi varsa menuyu acar, yoksa false doner.
window.hedefHaritaTikIsle = function(clientX, clientY){
  if (typeof viewer === "undefined" || !viewer || !viewer.scene) return false;
  const canvas = viewer.scene.canvas;
  const rect = canvas.getBoundingClientRect();
  const ekranPoz = new Cesium.Cartesian2(clientX - rect.left, clientY - rect.top);
  let secilen = [];
  try { secilen = viewer.scene.drillPick(ekranPoz, 8) || []; } catch(e){ return false; }
  for (const p of secilen){
    const ent = p && p.id;
    if (!ent) continue;
    for (const hid of Object.keys(radarHedefVarliklar)){
      if (radarHedefVarliklar[hid] === ent){
        hedefMenuAc(Number(hid), {x: clientX, y: clientY});
        return true;
      }
    }
  }
  return false;
};

// ---------------------------------------------------------------------
// HARITADA CIFT TIKLAMA: hedefe cift tiklaninca takibe al
// ---------------------------------------------------------------------
(function haritaCiftTikKur(){
  if (typeof viewer === "undefined" || !viewer) { setTimeout(haritaCiftTikKur, 500); return; }
  // Cesium'un varsayilan cift-tik davranisini (entity'yi kameraya kilitleme) kapat
  viewer.screenSpaceEventHandler.removeInputAction(
    Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);
  const h = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
  h.setInputAction((ev) => {
    const secilen = viewer.scene.drillPick(ev.position, 6);
    for (const p of secilen){
      const ent = p && p.id;
      if (!ent) continue;
      // Entity, radar hedef varliklarindan biri mi? (id esle)
      for (const hid of Object.keys(radarHedefVarliklar)){
        if (radarHedefVarliklar[hid] === ent){
          const idNum = isNaN(Number(hid)) ? hid : Number(hid);
          if (!takipIdler.has(idNum)) takibeAl(idNum);
          return;
        }
      }
    }
  }, Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);
})();

// ---------------------------------------------------------------------
// ETIKETLEME (Faz 2): replay sirasinda hedef kartindan iz etiketleme
// ---------------------------------------------------------------------
const ETIKET_SINIFLAR = ["DRON", "KUS", "INSAN", "ARAC", "KLUTTER"];

// Kart icindeki etiket satirini gunceller (yalniz replay modunda gorunur)
function etiketSatiriGuncelle(kart, h){
  const satir = kart.querySelector(".rh-etiket-satir");
  if (!satir) return;
  const aktif = (typeof replayAktif !== "undefined") && replayAktif &&
                (typeof replayDosya !== "undefined") && replayDosya;
  satir.classList.toggle("gizli", !aktif);
  if (!aktif) return;
  const t = D();
  const mevcut = (typeof etiketler !== "undefined" && etiketler[String(h.id)])
                 ? etiketler[String(h.id)].sinif : "";
  // Satiri yalniz gerektiginde yeniden kur (mevcut secim degistiyse)
  if (satir._mevcut === mevcut && satir._dil === aktifDil) return;
  satir._mevcut = mevcut;
  satir._dil = aktifDil;
  satir.innerHTML = "";
  const bas = document.createElement("span");
  bas.className = "rh-etiket-baslik";
  bas.textContent = t.etiketBaslik || "ET\u0130KET";
  satir.appendChild(bas);
  for (const s of ETIKET_SINIFLAR){
    const d = document.createElement("button");
    d.className = "rh-etiket-dgm" + (s === mevcut ? " secili" : "");
    d.textContent = (t.radarTipleri && t.radarTipleri[s]) || s;
    d.title = (s === mevcut) ? (t.etiketKaldir || "Etiketi kald\u0131r")
                             : (t.etiketAta || "Bu s\u0131n\u0131f\u0131 ata");
    d.addEventListener("click", (ev) => {
      ev.stopPropagation();
      if (s === mevcut){
        gonder({tip: "etiket_sil", dosya: replayDosya, iz_id: h.id});
      } else {
        gonder({tip: "etiket_ekle", dosya: replayDosya, iz_id: h.id,
                sinif: s, guven: "kesin", kaynak: "operator"});
      }
    });
    satir.appendChild(d);
  }
}

// WS'den etiket listesi gelince acik kartlardaki satirlari tazeler
function etiketRozetleriTazele(){
  for (const kart of Array.from(radarHedefListesi.children)){
    const id = kart.id.replace("rh-", "");
    const h = sonRadarHedefler.find(x => String(x.id) === id);
    if (h){
      const satir = kart.querySelector(".rh-etiket-satir");
      if (satir) satir._mevcut = undefined;   // yeniden cizimi zorla
      etiketSatiriGuncelle(kart, h);
    }
  }
}

function radarHedefleriTemizle(){
  // Yalnizca ekrani temizler; backend iz tablosuna dokunmaz
  // (radar kesilince izler backend'de yasamaya devam eder, yeniden baglaninca geri gelir)
  // ISTISNA: takipteki hedefler haritada ve takip listesinde korunur (soluk)
  for (const id of Object.keys(radarHedefVarliklar)){
    const nid = Number(id);
    if (takipIdler.has(nid)){
      hedefSolukYap(radarHedefVarliklar[id], true);
      continue;
    }
    hedefBipiramitSil(radarHedefVarliklar[id]);
    viewer.entities.remove(radarHedefVarliklar[id]);
    delete radarHedefVarliklar[id];
  }
  sonRadarHedefler = [];
  for (const id of Object.keys(hedefIzVarliklar)){
    if (takipIdler.has(Number(id))) continue;   // takipteki hedefin izi kalsin
    viewer.entities.remove(hedefIzVarliklar[id]);
    delete hedefIzVarliklar[id]; delete hedefIzGecmisi[id];
  }
  for (const id of Object.keys(yetimIzVarliklar)) viewer.entities.remove(yetimIzVarliklar[id]);
  yetimIzVarliklar = {};
  if (radarHedefOzet) radarHedefOzet.textContent = "";
  if (radarHedefListesi) radarHedefListesi.innerHTML = "";
  radarHedefKartlariGuncelle();   // takip kartlarini SINYAL YOK durumuna gecir
}

// ---------------------------------------------------------------
