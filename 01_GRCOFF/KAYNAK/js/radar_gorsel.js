// =================================================================
// GOKTUNGU - RADAR IZGARASI + SUPURME + IRTIFA KUBBESI + RADAR IKONU
// Bu dosya index.html'den mekanik olarak ayrilmistir; yukleme sirasi
// index.html'deki <script> sirasina baglidir (klasik script, ortak scope).
// =================================================================
// ZOOM-DUYARLI RADAR IZGARASI (C20 orijinal yazilimi gibi)
// Kamera yuksekligine gore halka adimi/azimut adimi degisir.
// Menzil halkalari + azimut cizgileri + mesafe/aci etiketleri, teal renk.
// ---------------------------------------------------------------
const IZGARA_RENK   = "#6bd8b9";   // orijinal C20 teal/yesil tonu
const IZGARA_MENZIL = 20000;       // radar azami menzili (m)
let kapsamaVarliklar = [];
let radarBagli = false;   // C20 radar baglanti durumu (radar paneli asagida gunceller)
let izgaraSonAdim = 0;    // en son cizilen halka adimi (gereksiz yeniden cizimi onler)
let izgaraMerkez = null;  // en son cizim merkezi {lat, lon}
// v2.4.33: kubbe sinir cizgileri (taban cemberi + dusey kesit yaylari).
// TANIM BURADA: `kubbeRenkUygula()` bu diziyi satir ~257'de okuyor ve
// `let` bildirimleri hoist EDILMEZ (TDZ). Bildirim kullanimdan sonra
// kalirsa, kubbe olusturulmadan once cagrilan bir renk uygulamasi
// "Cannot access before initialization" ReferenceError atar.
let kubbeTelVarliklar = [];

function dairePoz(lat, lon, yaricapM, n){
  // Merkez etrafinda yaricapM metrelik daire noktalari
  n = n || 128;
  const dLat = yaricapM / 111320.0;
  const dLon = yaricapM / (111320.0 * Math.cos(lat * Math.PI / 180));
  const dizi = [];
  for (let i = 0; i < n; i++){
    const a = 2 * Math.PI * i / n;
    dizi.push(lon + dLon * Math.sin(a), lat + dLat * Math.cos(a));
  }
  return Cesium.Cartesian3.fromDegreesArray(dizi);
}

function izgaraAdimSec(){
  // Kamera yuksekligine gore halka adimi (m) ve azimut adimi (derece)
  let h = 20000;
  try { h = viewer.camera.positionCartographic.height; } catch(e){}
  if      (h <  3000) return { halka: 200,  azim: 20 };
  else if (h <  8000) return { halka: 500,  azim: 20 };
  else if (h < 20000) return { halka: 1000, azim: 45 };
  else if (h < 45000) return { halka: 2000, azim: 45 };
  else                return { halka: 5000, azim: 45 };
}

function mesafeMetni(m){
  return (m < 1000) ? m.toFixed(1) + "m" : (m / 1000).toFixed(2) + "Km";
}

function kapsamaGuncelle(lat, lon, zorla){
  // v2.4.58 — RADAR KAPALIYKEN YENIDEN CIZILEN IZGARA SIZINTISI.
  // Bu islev harita her hareket ettiginde cagrilir ve varliklari
  // `show: true` ile yeniden olusturur. program_ayar.js'deki gizleme
  // yalniz o ANDAKI varliklara uygulandigi icin, radar kapaliyken
  // haritayi kaydirmak halkalari geri getiriyordu; iki saniyelik
  // periyodik supurme de aradaki karelerde gorunmelerini engellemiyor.
  // Karar kaynagi tek: radarYetenekVar() (bkz. program_ayar.js).
  const _radarGoster = (typeof window.radarYetenekVar === "function")
    ? window.radarYetenekVar() : true;
  const adim = izgaraAdimSec();
  // Ayni merkez ve ayni adim ise yeniden cizme
  if (!zorla && izgaraMerkez && izgaraSonAdim === adim.halka &&
      Math.abs(izgaraMerkez.lat - lat) < 1e-9 && Math.abs(izgaraMerkez.lon - lon) < 1e-9) return;
  izgaraSonAdim = adim.halka;
  izgaraMerkez = { lat: lat, lon: lon };

  for (const e of kapsamaVarliklar) viewer.entities.remove(e);
  kapsamaVarliklar = [];

  const renk = Cesium.Color.fromCssColorString(IZGARA_RENK);
  const halkaSayisi = Math.min(Math.round(IZGARA_MENZIL / adim.halka), 100);
  const maksR = halkaSayisi * adim.halka;

  // --- Menzil halkalari + mesafe etiketleri ---
  for (let i = 1; i <= halkaSayisi; i++){
    const r = i * adim.halka;
    const halka = dairePoz(lat, lon, r, 180);
    const halkaE = viewer.entities.add({
      show: _radarGoster,
      polyline: {
        positions: halka.concat([halka[0]]),
        width: (r === maksR) ? 3.0 : 2.0,
        material: renk.withAlpha((r === maksR) ? 0.95 : 0.7),
        clampToGround: true,
      },
    });
    halkaE._alfaTaban = (r === maksR) ? 0.95 : 0.7;
    kapsamaVarliklar.push(halkaE);
    // Mesafe etiketi: halkanin kuzeydogu (~30 derece) yonunde, cizginin ustunde
    const eA = 30 * Math.PI / 180;
    const eP = noktada(lat, lon, r, eA);
    const mesafeE = viewer.entities.add({
      show: _radarGoster,
      position: Cesium.Cartesian3.fromDegrees(eP[0], eP[1], 0),
      label: {
        text: mesafeMetni(r),
        font: "12px Consolas, monospace",
        fillColor: renk.withAlpha(0.95),
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        outlineColor: Cesium.Color.BLACK.withAlpha(0.7),
        outlineWidth: 2,
        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
        pixelOffset: new Cesium.Cartesian2(0, -2),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      }
    });
    mesafeE._alfaTaban = 0.95;
    kapsamaVarliklar.push(mesafeE);
  }

  // --- Azimut cizgileri + aci etiketleri ---
  for (let aci = 0; aci < 360; aci += adim.azim){
    const aRad = aci * Math.PI / 180;
    const uc = noktada(lat, lon, maksR, aRad);
    const azimE = viewer.entities.add({
      show: _radarGoster,
      polyline: {
        positions: Cesium.Cartesian3.fromDegreesArray([lon, lat, uc[0], uc[1]]),
        width: 2.0,
        material: renk.withAlpha(0.6),
        clampToGround: true,
      },
    });
    azimE._alfaTaban = 0.6;
    kapsamaVarliklar.push(azimE);
    // Aci etiketi: cizginin dis ucuna yakin (%92 mesafede)
    const eP = noktada(lat, lon, maksR * 0.92, aRad);
    const aciE = viewer.entities.add({
      show: _radarGoster,
      position: Cesium.Cartesian3.fromDegrees(eP[0], eP[1], 0),
      label: {
        text: aci.toFixed(1) + "\u00b0",
        font: "12px Consolas, monospace",
        fillColor: renk.withAlpha(0.95),
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        outlineColor: Cesium.Color.BLACK.withAlpha(0.7),
        outlineWidth: 2,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      }
    });
    aciE._alfaTaban = 0.95;
    kapsamaVarliklar.push(aciE);
    // Ara aci etiketi: ic bolgede de bir etiket (orta halka civari) - yakin zoomda okunabilirlik
    if (halkaSayisi >= 4){
      const oP = noktada(lat, lon, maksR * 0.45, aRad);
      const araE = viewer.entities.add({
        show: _radarGoster,
        position: Cesium.Cartesian3.fromDegrees(oP[0], oP[1], 0),
        label: {
          text: aci.toFixed(1) + "\u00b0",
          font: "11px Consolas, monospace",
          fillColor: renk.withAlpha(0.8),
          style: Cesium.LabelStyle.FILL_AND_OUTLINE,
          outlineColor: Cesium.Color.BLACK.withAlpha(0.6),
          outlineWidth: 2,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        }
      });
      araE._alfaTaban = 0.8;
      kapsamaVarliklar.push(araE);
    }
  }

  // --- Merkez isareti (kucuk nokta) ---
  kapsamaVarliklar.push(viewer.entities.add({
    show: _radarGoster,
    position: Cesium.Cartesian3.fromDegrees(lon, lat, 0),
    point: {
      pixelSize: 5,
      color: Cesium.Color.fromCssColorString("#ff5d5d").withAlpha(0.95),
      outlineColor: renk.withAlpha(0.9),
      outlineWidth: 1,
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    },
  }));

  // Yeniden cizim sonrasi mevcut baglanti durumuna gore boya
  // (offline'da gri/silik; radarGorselCevrimici null ise offline say)
  izgaraRenkUygula(radarGorselCevrimici === true);
}

// Kamera zoom degisince izgarayi yeni adimla yeniden ciz (debounce)
let izgaraZamanlayici = null;
function izgaraKameraTakibi(){
  viewer.camera.changed.addEventListener(() => {
    if (!gcsKonum) return;
    if (izgaraZamanlayici) clearTimeout(izgaraZamanlayici);
    izgaraZamanlayici = setTimeout(() => {
      const adim = izgaraAdimSec();
      if (adim.halka !== izgaraSonAdim) kapsamaGuncelle(gcsKonum.lat, gcsKonum.lon, true);
    }, 150);
  });
  viewer.camera.percentageChanged = 0.05; // daha hassas zoom takibi
}

// ---------------------------------------------------------------
// RADAR SUPURME - GCS merkezli, 20 km'lik donen cizgi + iz yelpazesi
// ---------------------------------------------------------------
const RADAR_YARICAP     = 20000;   // metre
const RADAR_TUR_SANIYE  = 4.5;     // varsayilan tam tur suresi (mod bilinmiyorsa)
// Calisma modu -> tarama tur suresi (sn); bekleme = donus yok
const RADAR_MOD_TUR_SN  = { tarama1: 1, tarama2: 2, tarama4: 4, bekleme: 0 };
const RADAR_IZ_DERECE   = 25;      // cizginin arkasindaki solan iz genisligi
const RADAR_IZ_DILIM    = 18;      // iz kac dilimle solacak
// Tema bazli radar rengi: koyu modda askeri yesil, acik modda kirmizi
const RADAR_RENKLERI    = { koyu: "#6bd8b9", acik: "#6bd8b9" };  // izgara ile uyumlu teal
let radarCizgi = null;
let radarIzDilimleri = [];   // {varlik, alfa}

function radarRengi(){
  return Cesium.Color.fromCssColorString(RADAR_RENKLERI[aktifTema]);
}

function radarRenkUygula(){
  if (!radarCizgi) return;
  const renk = radarRengi();
  radarCizgi.polyline.material =
    new Cesium.ColorMaterialProperty(renk.withAlpha(0.85));
  for (const d of radarIzDilimleri){
    d.varlik.polygon.material = renk.withAlpha(d.alfa);
  }
}

// Radar gorselleri (izgara, supurme, kubbe) HER ZAMAN gorunur.
// Radar cevrimdisiyken gri ve silik, bagliyken normal teal renkte cizilir.
const IZGARA_OFFLINE_RENK = "#c2cad2";   // cevrimdisi gri ton (acik, uydu haritasinda secilebilir)
const OFFLINE_ALFA_CARPAN = 0.6;           // cevrimdisi soluklastirma katsayisi
let radarGorselCevrimici = null;           // son uygulanan durum (gereksiz tekrar boyamayi onler)

function radarKapsamaGorunurluk(bagli){
  // Isim geriye donuk korunur; artik gizlemek yerine renk/solukluk uygular
  if (radarGorselCevrimici === bagli) return;
  radarGorselCevrimici = bagli;
  // Supurme cizgisi + iz yelpazesi: offline'da tamamen gizli kalir (donen
  // tarama animasyonu yalnizca gercek veri akisi varken anlamlidir)
  // v2.4.58: baglanti durumu TEK BASINA yeterli degil; radar yetenegi
  // yoksa (koprudeki radar servisi kapali) hicbir kosulda gorunmez.
  const _rg = (typeof window.radarYetenekVar === "function")
    ? window.radarYetenekVar() : true;
  if (radarCizgi) radarCizgi.show = bagli && _rg;
  for (const d of radarIzDilimleri) d.varlik.show = bagli && _rg;
  // Izgara + kubbe: her zaman gorunur, offline'da gri/silik
  izgaraRenkUygula(bagli);
  kubbeRenkUygula(bagli);
}

function izgaraRenkUygula(bagli){
  // v2.4.58 — GIZLEMEYI GERI ACAN SATIR BURADAYDI.
  // Bu islev yalnizca RENK/ALFA tazelemek icin cagrilir (radar cevrimici
  // olunca yesil, cevrimdisi olunca gri). Ancak icindeki `e.show = true`
  // radarin gorunur olup olmadigina hic bakmadan tum izgara varliklarini
  // geri aciyordu. Radar yetenegi yoksa varliklar `show:false` ile dogsa
  // bile ilk renk tazelemesinde yeniden gorunur hale geliyorlardi.
  // Renk tazelemesi bir gorunurluk karari DEGILDIR; gorunurluk kararinin
  // tek sahibi radarYetenekVar()'dir.
  const _rg = (typeof window.radarYetenekVar === "function")
    ? window.radarYetenekVar() : true;
  const renk = Cesium.Color.fromCssColorString(bagli ? IZGARA_RENK : IZGARA_OFFLINE_RENK);
  const c = bagli ? 1.0 : OFFLINE_ALFA_CARPAN;
  for (const e of kapsamaVarliklar){
    e.show = _rg;
    if (e.polyline){
      const alfaTaban = e._alfaTaban !== undefined ? e._alfaTaban : 0.7;
      e.polyline.material = renk.withAlpha(alfaTaban * c);
    }
    if (e.label){
      const alfaTaban = e._alfaTaban !== undefined ? e._alfaTaban : 0.95;
      e.label.fillColor = renk.withAlpha(alfaTaban * c);
    }
    if (e.point){
      e.point.color = Cesium.Color.fromCssColorString("#ff5d5d").withAlpha(bagli ? 0.95 : 0.35);
      e.point.outlineColor = renk.withAlpha(0.9 * c);
    }
  }
}

function kubbeRenkUygula(bagli){
  if (!irtifaKubbe) return;
  // v2.4.58 — ayni kusur kubbede de vardi (bkz. izgaraRenkUygula).
  const _rg = (typeof window.radarYetenekVar === "function")
    ? window.radarYetenekVar() : true;
  irtifaKubbe.show = _rg;
  for (const e of kubbeTelVarliklar) e.show = _rg;
  const renk = Cesium.Color.fromCssColorString(bagli ? "#6bd8b9" : IZGARA_OFFLINE_RENK);
  const c = bagli ? 1.0 : OFFLINE_ALFA_CARPAN;
  irtifaKubbe.ellipsoid.material = renk.withAlpha(0.08 * c);
  // v2.4.33: outline kapatildi (gl.LINES kusuru) -> outlineColor yazmak
  // gereksiz. Kubbe siniri artik ayri polyline varliklarindan geliyor.
  for (const e of kubbeTelVarliklar){
    if (!e.polyline) continue;
    const alfaTaban = e._alfaTaban !== undefined ? e._alfaTaban : 0.35;
    e.polyline.material =
      new Cesium.ColorMaterialProperty(renk.withAlpha(alfaTaban * c));
  }
}

// ---------------------------------------------------------------
// IRTIFA KAPSAMA KUBBESI: radar merkezli, 40 km cap x 3000 m yukseklik
// Basik yarim elipsoit (merkez z=0) -> radar irtifa/menzil kapsamasini gosterir
// Yatay yaricap radar menziliyle (IZGARA_MENZIL = 20 km) uyumludur
// ---------------------------------------------------------------
const KUBBE_YATAY_YARICAP = 20000;  // metre (40 km cap / 2, radar menzili)
const KUBBE_YUKSEKLIK = 3000;       // metre (radar irtifa kapasitesi)
let irtifaKubbe = null;

// v2.4.33 KURE (KUBBE) BOZULMASI DUZELTMESI
// ------------------------------------------
// SEMPTOM: Bazi bilgisayarlarda kubbe, birbirini kesen dik/eksen hizali
// cizgilerden olusan dagilmis bir kafes olarak goruluyordu; menzil
// halkalari da kayboluyordu. Ayni surum baska bilgisayarda dogru
// gorunuyordu -> kod degil, GPU/surucu bagimli bir kusur.
//
// KOK NEDEN: `ellipsoid` grafiginde `outline: true` verildiginde Cesium
// tel kafesi `EllipsoidOutlineGeometry` ile, yani WebGL `gl.LINES`
// primitifiyle cizer (stackPartitions 24 x slicePartitions 36 = ~860
// cizgi parcasi). `gl.LINES` uygulamasi suruculer arasinda tutarsizdir:
// Intel tumlesik grafik, SwiftShader (yazilim rasterlestirme), uzak
// masaustu ve sanal makinelerde kirpma duzlemi disina tasan parcalar
// eksen hizali cizgilere cokerek tam olarak bu kafes goruntusunu uretir.
// Basik elipsoit (z=3 km, xy=20 km) oldugu icin cizgilerin cogu arazinin
// icinde kaliyor ve terrain ile z-fighting'e girip durumu agirlastiriyor.
//
// COZUM: Tel kafes tumden birakildi (`outline: false`). Kubbe hacmi
// yariseffaf dolgudan zaten anlasiliyor. Sinirini belirtmek icin taban
// cemberi + iki dusey kesit yayi `polyline` olarak cizilir. Polyline
// Cesium'da TRIANGLES tabanli `PolylineMaterialAppearance` ile cizilir;
// `gl.LINES`'a bagli DEGILDIR ve her GPU'da ayni gorunur.
const KUBBE_KESIT_ADIM = 48;      // yay cozunurlugu (nokta sayisi)
// NOT: `kubbeTelVarliklar` dosya basinda tanimli (TDZ gerekcesi orada).

// Kubbe yuzeyinde, verilen azimutta dusey kesit yayi (yatay yaricap r,
// dusey yaricap KUBBE_YUKSEKLIK olan yarim elips) noktalarini uretir.
function kubbeKesitNoktalari(lat, lon, azimutRad){
  const dizi = [];
  // Yay bir uctan (yatay, yukseklik 0) tepeye ve karsi uca gider:
  // theta 0 -> PI, yatay bilesen cos(theta), dusey bilesen sin(theta)
  for (let i = 0; i <= KUBBE_KESIT_ADIM; i++){
    const th = Math.PI * i / KUBBE_KESIT_ADIM;
    const yatay = KUBBE_YATAY_YARICAP * Math.cos(th);
    const yuk = KUBBE_YUKSEKLIK * Math.sin(th);
    // Negatif yatay bilesen = karsi azimut
    const p = noktada(lat, lon, Math.abs(yatay),
                      yatay >= 0 ? azimutRad : azimutRad + Math.PI);
    dizi.push(p[0], p[1], yuk);
  }
  return Cesium.Cartesian3.fromDegreesArrayHeights(dizi);
}

function irtifaKubbesiOlustur(){
  if (irtifaKubbe) return;   // bir kez kurulur; merkezi gcsKonum'dan canli okur
  // v2.4.58: radar yetenegi yoksa kubbe de olusmaz (bkz. kapsamaGuncelle)
  const _rg = (typeof window.radarYetenekVar === "function")
    ? window.radarYetenekVar() : true;
  irtifaKubbe = viewer.entities.add({
    show: _rg,   // yetenek varken gorunur; offline'da gri/silik boyanir
    position: new Cesium.CallbackProperty(() =>
      Cesium.Cartesian3.fromDegrees(gcsKonum.lon, gcsKonum.lat, 0), false),
    ellipsoid: {
      radii: new Cesium.Cartesian3(KUBBE_YATAY_YARICAP, KUBBE_YATAY_YARICAP, KUBBE_YUKSEKLIK),
      // Sadece ust yarim kure cizilir (0 -> 90 derece)
      minimumCone: 0.0,
      maximumCone: Cesium.Math.PI_OVER_TWO,
      material: Cesium.Color.fromCssColorString("#6bd8b9").withAlpha(0.08),
      // v2.4.33: gl.LINES tabanli tel kafes KAPATILDI (yukaridaki not).
      outline: false,
      // subdivisions dolgu yuzeyinin puruzsuzlugunu belirler; tel kafes
      // olmadigi icin stack/slicePartitions gorsel etkisi kalmadi ama
      // dusuk tutmak GPU yukunu azaltir.
      subdivisions: 48,
    },
  });

  // --- Kubbe siniri: taban cemberi (yerden bagimsiz, sabit yukseklik) ---
  // clampToGround KULLANILMAZ: o da GroundPolylinePrimitive'i, dolayisiyla
  // `EXT_frag_depth` eklentisini gerektirir ve ayni sinif kirilganliktir.
  const kubbeRenk = Cesium.Color.fromCssColorString("#6bd8b9");
  const tabanE = viewer.entities.add({
    show: _rg,
    polyline: {
      positions: new Cesium.CallbackProperty(() => {
        const halka = dairePoz(gcsKonum.lat, gcsKonum.lon, KUBBE_YATAY_YARICAP, 96);
        return halka.concat([halka[0]]);
      }, false),
      width: 1.6,
      material: new Cesium.ColorMaterialProperty(kubbeRenk.withAlpha(0.40)),
      arcType: Cesium.ArcType.NONE,
    },
  });
  tabanE._alfaTaban = 0.40;
  kubbeTelVarliklar.push(tabanE);

  // --- Iki dusey kesit yayi (kuzey-guney ve dogu-bati duzlemleri) ---
  [0, Math.PI / 2].forEach(az => {
    const yayE = viewer.entities.add({
      show: _rg,
      polyline: {
        positions: new Cesium.CallbackProperty(() =>
          kubbeKesitNoktalari(gcsKonum.lat, gcsKonum.lon, az), false),
        width: 1.4,
        material: new Cesium.ColorMaterialProperty(kubbeRenk.withAlpha(0.30)),
        arcType: Cesium.ArcType.NONE,
      },
    });
    yayE._alfaTaban = 0.30;
    kubbeTelVarliklar.push(yayE);
  });

  // Olusturma sonrasi mevcut baglanti durumuna gore boya (offline = gri/silik)
  kubbeRenkUygula(radarGorselCevrimici === true);
}

// Supurme acisi: calisma moduna senkron, mutlak zaman tabanli.
// aci = bazAci + gecenSure * acisalHiz  -> ayni frame'de kac kez cagrilirsa
// cagrilsin ayni sonucu verir (cift entegrasyon olmaz).
// Mod degistiginde baz aci guncel aciya sabitlenir; boylece sicrama olmaz.
let radarAciDurum = { bazAci: 0, t0: Date.now(), turSn: RADAR_TUR_SANIYE, aci: 0 };
function radarTurSuresi(){
  const mod = (sonRadar && sonRadar.ayarlar && sonRadar.ayarlar.calisma_modu) || null;
  if (mod && RADAR_MOD_TUR_SN.hasOwnProperty(mod)) return RADAR_MOD_TUR_SN[mod];
  return RADAR_TUR_SANIYE;
}
function radarAcisi(){
  const turSn = radarTurSuresi();
  const simdi = Date.now();
  if (turSn !== radarAciDurum.turSn){
    // Mod degisti: guncel aciyi baz al, zamani sifirla (sicramasiz gecis)
    radarAciDurum.bazAci = radarAciDurum.aci;
    radarAciDurum.t0 = simdi;
    radarAciDurum.turSn = turSn;
  }
  if (turSn > 0){
    const gecen = (simdi - radarAciDurum.t0) / 1000;
    radarAciDurum.aci =
      (radarAciDurum.bazAci + (2 * Math.PI / turSn) * gecen) % (2 * Math.PI);
  }
  // bekleme modunda (turSn=0) aci sabit kalir (donus durur)
  return radarAciDurum.aci;
}

function noktada(lat, lon, r, aci){
  // Merkezden r metre, aci radyan (0 = kuzey, saat yonu) yondeki nokta
  const dLat = r / 111320.0;
  const dLon = r / (111320.0 * Math.cos(lat * Math.PI / 180));
  return [lon + dLon * Math.sin(aci), lat + dLat * Math.cos(aci)];
}

function radarOlustur(){
  if (radarCizgi) return;   // bir kez kurulur; merkezi gcsKonum'dan canli okur
  // v2.4.58: tarama cizgisi hem radar baglantisina hem radar yetenegine bagli
  const _rg = (typeof window.radarYetenekVar === "function")
    ? window.radarYetenekVar() : true;
  const radarRenk = radarRengi();
  radarCizgi = viewer.entities.add({
    show: radarBagli && _rg,
    polyline: {
      positions: new Cesium.CallbackProperty(() => {
        const a = radarAcisi();
        const uc = noktada(gcsKonum.lat, gcsKonum.lon, RADAR_YARICAP, a);
        return Cesium.Cartesian3.fromDegreesArray(
          [gcsKonum.lon, gcsKonum.lat, uc[0], uc[1]]);
      }, false),
      width: 2,
      material: new Cesium.ColorMaterialProperty(radarRenk.withAlpha(0.85)),
    },
  });

  // Iz yelpazesi: acisal solma - cizgiye bitisik %50, kuyruk ucunda %0
  const izRad = RADAR_IZ_DERECE * Math.PI / 180;
  for (let i = 0; i < RADAR_IZ_DILIM; i++){
    // i = 0 kuyruk ucu, son dilim cizgiye bitisik
    const alfa = 0.50 * (i + 1) / RADAR_IZ_DILIM;
    const dilim = i;
    radarIzDilimleri.push({ alfa: alfa, varlik: viewer.entities.add({
      show: radarBagli && _rg,
      polygon: {
        hierarchy: new Cesium.CallbackProperty(() => {
          const a = radarAcisi();
          const bas = a - izRad + izRad *  dilim      / RADAR_IZ_DILIM;
          const son = a - izRad + izRad * (dilim + 1) / RADAR_IZ_DILIM;
          const dizi = [gcsKonum.lon, gcsKonum.lat];
          for (let j = 0; j <= 3; j++){
            const ac = bas + (son - bas) * j / 3;
            const p = noktada(gcsKonum.lat, gcsKonum.lon, RADAR_YARICAP, ac);
            dizi.push(p[0], p[1]);
          }
          return new Cesium.PolygonHierarchy(
            Cesium.Cartesian3.fromDegreesArray(dizi));
        }, false),
        material: radarRenk.withAlpha(alfa),
      },
    })});
  }
}

// ---------------------------------------------------------------
// RADAR IKONU - merkez konumda yon gosteren ucgen
// Renk = baglanti durumu, aci = aktif tarama yonu (supurme ile senkron)
// ---------------------------------------------------------------
const RADAR_IKON_RENKLERI = {
  bagli:  "#6bd8b9",   // bagli: teal (izgara/supurme ile uyumlu)
  hata:   "#e05555",   // hata: kirmizi
  kapali: "#8a97a5",   // bagli degil / baglaniyor: gri
};

// Radarin gercek bakis yonu (derece, 0-360): once telemetriden gelen
// merkez_yonu, yoksa paneldeki Merkez Yonu girisi, o da yoksa 0.
function radarBakisYonu(){
  if (typeof sonRadar !== "undefined" && sonRadar && sonRadar.ayarlar &&
      typeof sonRadar.ayarlar.merkez_yonu === "number")
    return sonRadar.ayarlar.merkez_yonu;
  const el = document.getElementById("raMerkezYonu");
  if (el){
    const v = parseFloat(el.value);
    if (!isNaN(v)) return ((v % 360) + 360) % 360;
  }
  return 0;
}

function radarIkonRengi(){
  if (typeof sonRadar === "undefined" || !sonRadar) return RADAR_IKON_RENKLERI.kapali;
  if (sonRadar.durum === "bagli") return RADAR_IKON_RENKLERI.bagli;
  if (sonRadar.durum === "hata")  return RADAR_IKON_RENKLERI.hata;
  return RADAR_IKON_RENKLERI.kapali;
}

function ucgenIkon(renk){
  // Kuzeye (yukari) bakan yon ucgeni; govde daire ile radar merkezi vurgusu
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="44" height="44" viewBox="0 0 44 44">
       <circle cx="22" cy="22" r="8" fill="${renk}" fill-opacity="0.25" stroke="${renk}" stroke-width="1.5"/>
       <path d="M 22 3 L 31 27 L 22 21.5 L 13 27 Z"
             fill="${renk}" stroke="#000" stroke-width="1.5" stroke-linejoin="round"/>
       <circle cx="22" cy="22" r="2.5" fill="${renk}" stroke="#000" stroke-width="1"/>
     </svg>`;
  return "data:image/svg+xml;base64," + btoa(svg);
}

// v2.4.30 DUZELTME (kritik gerileme)
// ------------------------------------
// v2.4.29'da GCS/radar varligi PRIZMA kipinde `polygon` olarak
// uretilmeye baslandi; bu fonksiyon ise guncellenmedigi icin hala
// `gcsVarlik.billboard.image` yazmaya calisiyordu. Prizma kipi
// varsayilan ACIK oldugundan `billboard` undefined donuyor ve her
// telemetri paketinde `TypeError: Cannot set properties of undefined`
// atiliyordu. Hata `ws.onmessage` govdesinde radar cagrisinda
// (satir 74) firladigi icin AYNI govdedeki dron dongusune (satir 100)
// hic ulasilamiyor, dolayisiyla DRONLAR paneli bos kaliyordu.
function radarIkonGuncelle(){
  if (!gcsVarlik) return;
  const renk = radarIkonRengi();
  if (gcsVarlik.polygon){
    // Prizma kipi: rengi malzeme ve kenar cizgisi uzerinden guncelle
    try {
      if (window.PrizmaIkon) window.PrizmaIkon.alfaAyarla(gcsVarlik, renk, 1);
    } catch (e){ /* renk guncellemesi kritik degil */ }
  } else if (gcsVarlik.billboard){
    gcsVarlik.billboard.image = ucgenIkon(renk);
  }
}

// =================================================================
// v2.4.190 — COKLU RADAR IKONLARI
// Her radar kendi konumunda (RTK > kayitli > merkez) yon ucgeni + ad
// etiketi + kucuk menzil halkasi olarak cizilir. Merkezdeki supurme/
// izgara (gcsKonum) izleme orijinini gosterir ve DEGISMEZ.
// =================================================================
const RADAR_IKON_HALKA_M = 1500;
let radarIkonVarliklar = {};   // radar_id -> {ikon, halka, sonKey}

window.radarIkonlariGuncelle = function(liste){
  if (typeof viewer === "undefined" || !viewer) return;
  const gorulen = {};
  const _rg = (typeof window.radarYetenekVar === "function") ? window.radarYetenekVar() : true;
  for (const r of (liste || [])){
    const rid = Number(r.radar_id);
    const lat = (typeof r.konum_lat === "number") ? r.konum_lat : null;
    const lon = (typeof r.konum_lon === "number") ? r.konum_lon : null;
    if (lat === null || lon === null) continue;
    if (typeof window.gecerliKonumMu === "function" && !window.gecerliKonumMu(lat, lon)) continue;
    gorulen[rid] = true;
    const renk = r.durum === "bagli" ? RADAR_IKON_RENKLERI.bagli :
                 r.durum === "hata" ? RADAR_IKON_RENKLERI.hata : RADAR_IKON_RENKLERI.kapali;
    const yon = (r.ayarlar && typeof r.ayarlar.merkez_yonu === "number") ? r.ayarlar.merkez_yonu : 0;
    const key = [lat.toFixed(6), lon.toFixed(6), renk, yon.toFixed(1), r.isim].join("|");
    let v = radarIkonVarliklar[rid];
    if (v && v.sonKey === key){ v.ikon.show = _rg; v.halka.show = _rg && r.durum === "bagli"; continue; }
    const pos = Cesium.Cartesian3.fromDegrees(lon, lat, 0);
    if (!v){
      v = { sonKey: "", ikon: null, halka: null };
      v.ikon = viewer.entities.add({
        id: "radar_" + rid, position: pos, show: _rg,
        billboard: {
          image: ucgenIkon(renk), width: 36, height: 36,
          verticalOrigin: Cesium.VerticalOrigin.CENTER,
          horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
          rotation: new Cesium.CallbackProperty(() => {
            const kam = viewer ? viewer.camera.heading : 0;
            const vv = radarIkonVarliklar[rid];
            return -Cesium.Math.toRadians(vv ? vv.yon || 0 : 0) + kam;
          }, false),
        },
        label: {
          text: r.isim || ("Radar " + rid),
          font: "bold 10px Consolas, monospace",
          fillColor: Cesium.Color.fromCssColorString(renk),
          style: Cesium.LabelStyle.FILL, showBackground: true,
          backgroundColor: Cesium.Color.BLACK.withAlpha(0.7),
          backgroundPadding: new Cesium.Cartesian2(5, 3),
          verticalOrigin: Cesium.VerticalOrigin.TOP,
          pixelOffset: new Cesium.Cartesian2(0, 20),
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 60000)
        }
      });
      v.halka = viewer.entities.add({
        id: "radar_halka_" + rid, show: _rg && r.durum === "bagli",
        polyline: { positions: dairePoz(lat, lon, RADAR_IKON_HALKA_M, 96), width: 1.5,
                    material: Cesium.Color.fromCssColorString(renk).withAlpha(0.5),
                    clampToGround: true }
      });
      radarIkonVarliklar[rid] = v;
    } else {
      v.ikon.position = pos;
      v.ikon.billboard.image = ucgenIkon(renk);
      v.ikon.label.text = r.isim || ("Radar " + rid);
      v.ikon.label.fillColor = Cesium.Color.fromCssColorString(renk);
      v.ikon.show = _rg;
      v.halka.polyline.positions = dairePoz(lat, lon, RADAR_IKON_HALKA_M, 96);
      v.halka.polyline.material = Cesium.Color.fromCssColorString(renk).withAlpha(0.5);
      v.halka.show = _rg && r.durum === "bagli";
    }
    v.yon = yon; v.sonKey = key;
  }
  for (const rid of Object.keys(radarIkonVarliklar)){
    if (!gorulen[rid]){
      const v = radarIkonVarliklar[rid];
      try { viewer.entities.remove(v.ikon); viewer.entities.remove(v.halka); } catch (e) {}
      delete radarIkonVarliklar[rid];
    }
  }
};

// =================================================================
// v2.4.191 — ELEKTRO-OPTIK (M50) IKONLARI
// Konum: cihazin RTK/GPS'i (SDK) > kayitli enlem/boylam. Ikon kamera
// simgesi; azimut (SDK) yonu gosterir; kisa gorus cizgisi eklenir.
// =================================================================
const EO_IKON_RENKLERI = { bagli: "#f0a830", hata: "#e05555", kapali: "#8a97a5" };
const EO_GORUS_M = 800;
let eoIkonVarliklar = {};

function eoIkon(renk){
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">
       <circle cx="20" cy="20" r="9" fill="${renk}" fill-opacity="0.25" stroke="${renk}" stroke-width="1.5"/>
       <rect x="11" y="15" width="14" height="10" rx="2" fill="${renk}" stroke="#000" stroke-width="1.5"/>
       <polygon points="25,17 33,13 33,27 25,23" fill="${renk}" stroke="#000" stroke-width="1.5" stroke-linejoin="round"/>
       <path d="M 20 3 L 24 10 L 16 10 Z" fill="${renk}" stroke="#000" stroke-width="1"/>
     </svg>`;
  return "data:image/svg+xml;base64," + btoa(svg);
}

window.eoIkonlariGuncelle = function(liste){
  if (typeof viewer === "undefined" || !viewer) return;
  const gorulen = {};
  for (const c of (liste || [])){
    const eid = Number(c.eo_id);
    const konum = c.konum && typeof c.konum === "object" ? c.konum : null;
    const lat = konum && typeof konum.lat === "number" ? konum.lat : null;
    const lon = konum && typeof konum.lon === "number" ? konum.lon : null;
    if (lat === null || lon === null) continue;
    if (typeof window.gecerliKonumMu === "function" && !window.gecerliKonumMu(lat, lon)) continue;
    gorulen[eid] = true;
    const d = c.m50_durum || {};
    const renk = d.durum === "bagli" ? EO_IKON_RENKLERI.bagli :
                 d.durum === "hata" ? EO_IKON_RENKLERI.hata : EO_IKON_RENKLERI.kapali;
    const az = (typeof d.azimut === "number") ? d.azimut :
               (d.pusula && typeof d.pusula.yon === "number") ? d.pusula.yon : 0;
    const key = [lat.toFixed(6), lon.toFixed(6), renk, az.toFixed(1), c.isim, konum.kaynak].join("|");
    let v = eoIkonVarliklar[eid];
    if (v && v.sonKey === key) continue;
    const pos = Cesium.Cartesian3.fromDegrees(lon, lat, 0);
    const uc = noktada(lat, lon, EO_GORUS_M, az * Math.PI / 180);
    const cizgi = Cesium.Cartesian3.fromDegreesArray([lon, lat, uc[0], uc[1]]);
    const etiket = (c.isim || ("M50 " + eid)) + (konum.kaynak === "rtk" ? " · RTK" : "");
    if (!v){
      v = { sonKey: "", ikon: null, gorus: null, az: 0 };
      v.ikon = viewer.entities.add({
        id: "eo_" + eid, position: pos,
        billboard: {
          image: eoIkon(renk), width: 36, height: 36,
          verticalOrigin: Cesium.VerticalOrigin.CENTER, horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
          rotation: new Cesium.CallbackProperty(() => {
            const kam = viewer ? viewer.camera.heading : 0;
            const vv = eoIkonVarliklar[eid];
            return -Cesium.Math.toRadians(vv ? vv.az || 0 : 0) + kam;
          }, false),
        },
        label: {
          text: etiket, font: "bold 10px Consolas, monospace",
          fillColor: Cesium.Color.fromCssColorString(renk), style: Cesium.LabelStyle.FILL,
          showBackground: true, backgroundColor: Cesium.Color.BLACK.withAlpha(0.7),
          backgroundPadding: new Cesium.Cartesian2(5, 3),
          verticalOrigin: Cesium.VerticalOrigin.TOP, pixelOffset: new Cesium.Cartesian2(0, 20),
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 60000)
        }
      });
      v.gorus = viewer.entities.add({
        id: "eo_gorus_" + eid, show: d.durum === "bagli",
        polyline: { positions: cizgi, width: 2, clampToGround: true,
                    material: Cesium.Color.fromCssColorString(renk).withAlpha(0.7) }
      });
      eoIkonVarliklar[eid] = v;
    } else {
      v.ikon.position = pos;
      v.ikon.billboard.image = eoIkon(renk);
      v.ikon.label.text = etiket;
      v.ikon.label.fillColor = Cesium.Color.fromCssColorString(renk);
      v.gorus.polyline.positions = cizgi;
      v.gorus.polyline.material = Cesium.Color.fromCssColorString(renk).withAlpha(0.7);
      v.gorus.show = d.durum === "bagli";
    }
    v.az = az; v.sonKey = key;
  }
  for (const eid of Object.keys(eoIkonVarliklar)){
    if (!gorulen[eid]){
      const v = eoIkonVarliklar[eid];
      try { viewer.entities.remove(v.ikon); viewer.entities.remove(v.gorus); } catch (e) {}
      delete eoIkonVarliklar[eid];
    }
  }
};

let gcsVarlik = null;
let gcsKonum = null;                 // {lat, lon}
let sonSeri = {durum:"kapali", port:"", baud:0};

function gcsKutuMetni(){
  const t = D();
  let portSatir;
  if (sonSeri.durum === "bagli")
    portSatir = sonSeri.port + " @ " + sonSeri.baud;
  else if (sonSeri.durum === "baglaniyor")
    portSatir = sonSeri.port + t.gcsBaglaniyorEk;
  else if (sonSeri.durum === "hata")
    portSatir = (sonSeri.port || "-") + " (" + t.seriHataM + ")";
  else
    portSatir = t.fSeriKapali.split(": ")[1] || "bagli degil";
  return "GCS \u00b7 " + t.gcsKartBaslik + "\n" +
         t.lblPort + ": " + portSatir + "\n" +
         t.lblEnl + " : " + gcsKonum.lat.toFixed(6) + "\n" +
         t.lblBoy + " : " + gcsKonum.lon.toFixed(6);
}

function gcsGuncelle(lat, lon){
  gcsKonum = {lat: lat, lon: lon};
  kapsamaGuncelle(lat, lon);
  radarOlustur();
  irtifaKubbesiOlustur();
  if (!gcsGuncelle._kameraTakip){ izgaraKameraTakibi(); gcsGuncelle._kameraTakip = true; }
  const pos = Cesium.Cartesian3.fromDegrees(lon, lat, 0);
  // v2.4.29: radar/GCS istasyonu ZEMINDE durur; yukseklik sabit 0 verildigi
  // icin terrain acikken ikon arazinin TAM ALTINDA kaliyordu (Ankara'da
  // olculen zemin: 787-962 m). Dogru referans CLAMP_TO_GROUND'dur.
  const gPrizmaMod = (typeof window.ikonPrizmaMi === "function")
    ? window.ikonPrizmaMi() : true;
  const gRenk = radarIkonRengi();
  // Prizma yonu = radarin gercek bakis yonu (Merkez Yonu ayari).
  // Prizma 3B geometri oldugu icin DUNYA uzayinda doner; billboard'da
  // gereken kamera heading telafisi burada GEREKMEZ.
  // v2.4.30: kullanici geri bildirimi — radar prizmasi COK UZUNDU.
  // Yatay olcek 48 m -> 30 m, dikey kalinlik 22 m -> 8 m (%64 kisalma).
  // Degerler prizma_ikon.js'teki varsayilanlardan alinir; boylece olcu
  // tek bir yerden yonetilir.
  const gSecenek = { lat: lat, lon: lon, yuk: 0, yon: radarBakisYonu(),
                     renk: gRenk, zemine: true,
                     olcek: window.PrizmaIkon.OLCEK_M,
                     kalinlik: window.PrizmaIkon.KALINLIK_M };
  if (!gcsVarlik){
    // v2.4.58: radar yetenegi yoksa ikon gizli olusur. `gcsGuncelle`
    // konum her guncellendiginde cagrildigi icin ikon, gizleme
    // uygulandiktan SONRA da yeniden dogabiliyordu.
    const _rg = (typeof window.radarYetenekVar === "function")
      ? window.radarYetenekVar() : true;
    const gTanim = { id: "gcs", position: pos, show: _rg };
    if (gPrizmaMod){
      gTanim.polygon = window.PrizmaIkon.tanim(gSecenek);
    } else {
      gTanim.billboard = {
        image: ucgenIkon(gRenk),
        width: 44, height: 44,
        verticalOrigin: Cesium.VerticalOrigin.CENTER,
        horizontalOrigin: Cesium.HorizontalOrigin.CENTER,
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
        // Ikon acisi = radarin gercek bakis yonu (Merkez Yonu ayari, derece).
        // Supurme animasyonuyla DONMEZ; sabit olarak radarin baktigi yonu gosterir.
        // Billboard rotation EKRANA gorelidir; kamera 3B dondurulunce ikon da
        // donmesin diye kamera heading'i telafi edilir: ekranUstu-kuzey farki
        // cikarilir. Cesium rotation CCW+, azimut CW+ -> isaret ters.
        rotation: new Cesium.CallbackProperty(() => {
          const kameraYonu = viewer ? viewer.camera.heading : 0; // radyan, CW+
          return -Cesium.Math.toRadians(radarBakisYonu()) + kameraYonu;
        }, false),
      };
    }
    gcsVarlik = viewer.entities.add(gTanim);
  } else {
    gcsVarlik.position = pos;
    if (gcsVarlik.polygon) window.PrizmaIkon.tazele(gcsVarlik, gSecenek);
  }
  // Sol paneldeki GCS kartini guncelle
  gcsKartGuncelle();
}

function gcsKartGuncelle(){
  const elDurum = document.getElementById("gcsKartDurum");
  const elPort = document.getElementById("gcsKartPort");
  const elLat = document.getElementById("gcsKartLat");
  const elLon = document.getElementById("gcsKartLon");
  if (!elDurum) return;

  const t = D();
  // Durum
  if (sonSeri.durum === "bagli") {
    elDurum.textContent = t.gcsBagli;
    elDurum.style.color = "#3ddc84";
  } else if (sonSeri.durum === "baglaniyor") {
    elDurum.textContent = t.gcsBaglaniyor;
    elDurum.style.color = "#ffc94d";
  } else {
    elDurum.textContent = t.gcsBagliDegil;
    elDurum.style.color = "#ff5252";
  }

  // Port
  if (sonSeri.durum === "bagli")
    elPort.textContent = sonSeri.port + " @ " + sonSeri.baud;
  else if (sonSeri.durum === "baglaniyor")
    elPort.textContent = sonSeri.port + t.gcsBaglaniyorEk;
  else
    elPort.textContent = "-";

  // Koordinatlar
  if (gcsKonum) {
    elLat.textContent = gcsKonum.lat.toFixed(6);
    elLon.textContent = gcsKonum.lon.toFixed(6);
  }
}

function gcsKutuTazele(){
  gcsKartGuncelle();
}

// ---------------------------------------------------------------
