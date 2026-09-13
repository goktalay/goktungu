// ===============================================================
// GOKTUNGU GCS - YER ISTASYONU 2 (ESP32-S3 kontrol paneli)  v2.4.44
// ---------------------------------------------------------------
// Dronlar menusu -> "Yer Istasyonu 2"
//
// Backend (`goktungu/istasyon2.py`) seri portu okur ve her tam durumu
// `istasyon2_durum` ile yayinlar. UCUS eylemleri sunucuda uygulanir;
// HARITA eylemleri BURADA uygulanir cunku harita durumu (Cesium
// kamerasi, katman sirasi, nesne listesi) yalniz tarayicida vardir.
//
// KANAL ESLEMESI (kullanici tanimi):
//   P1 ARM/DISARM   P2 TAKEOFF/LAND   P3 RTL
//   P4 GUIDED       P5 ALT_HOLD       P6 AUTO      -> sunucu
//   T1  -> P7 LED (backend surer) + "Patlatmak icin emin misiniz?"
//   J1  -> harita dondurme (heading) + egim (pitch)
//   J2  -> harita kaydirma (kuzey/guney, dogu/bati)
//   T2  -> UP zoom, DOWN ters zoom, CENTER dur
//   P8 harita kaynagi  P9 kullanici konumu
//   P10 tumunu kapsa   P11 noktalar arasinda gez
//
// HARITA KONTROLU NICIN requestAnimationFrame ILE?
//   Panel cubugu 20 Hz'de durum basar; kamerayi her mesajda bir kez
//   itmek takilmali bir hareket verir. Bunun yerine son eksen degeri
//   bir HIZ olarak saklanir ve her cizim karesinde gecen sureyle
//   carpilarak uygulanir. Boylece hareket kare hizindan bagimsiz ve
//   akici olur; mesaj gelmese de (cubuk sabit tutuluyorsa) kamera
//   dogru hizda gitmeye devam eder.
//
// ARKA PLAN SEKMESI: `document.hidden` iken kamera surulmez. Iki
// tarayici sekmesi acikken haritanin iki yerden cekilmesi engellenir.
// ===============================================================
"use strict";

let _i2Popup = null;         // acik panel DOM'u
let _i2Durum = null;         // son `istasyon2_durum` paketi
let _i2Portlar = [];         // son port taramasi
let _i2OnayAcik = null;      // acik patlatma onay penceresi
let _i2NoktaSira = 0;        // P11 gezme sirasi
let _i2Akis = [];            // ham olay akisi (son 20)

// Harita kontrol hizlari (eksen -1..+1 -> saniyedeki degisim)
const I2_DONME_HIZ = 60.0;   // derece/sn (J1_X)
const I2_EGIM_HIZ = 45.0;    // derece/sn (J1_Y)
const I2_KAYMA_ORAN = 0.60;  // kamera yuksekliginin %60'i / sn (J2)
const I2_ZOOM_ORAN = 0.80;   // yukseklik degisimi / sn (T2)
const I2_OLU = 0.06;         // normalize olu bolge (kalibrasyon ustu)

// Kamera surme durumu
const _i2Kamera = { dx: 0, dy: 0, kx: 0, ky: 0, zoom: 0 };
let _i2Kare = 0;             // requestAnimationFrame kimligi
let _i2SonKare = 0;

function i2D() {
  return (typeof D === "function") ? D() : {};
}

function i2Kacis(s) {
  return String(s === null || s === undefined ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// Eylem adi CEVIRIDEN gelir. Backend eylem ANAHTARINI gonderir
// (arm_disarm, harita_kaynak...); sozluklerdeki Turkce metin yalniz
// ceviri anahtari bulunamazsa devreye giren son caredir. Aksi halde
// arayuz Ingilizce iken buton aciklamalari Turkce kalirdi.
function i2EylemAd(eylem, ucus, harita) {
  if (!eylem) return "";
  const t = i2D();
  const anahtar = "i2Eylem_" + eylem;
  if (t[anahtar]) return t[anahtar];
  return (ucus && ucus[eylem]) || (harita && harita[eylem]) || eylem;
}

// ---------------------------------------------------------------
// v2.4.59: SAHA MAKINESI (KOPRU) SECIMI
//
// KUSUR-GCSDUAL-PORT: canta pilotun makinesine takilidir, merkez
// sunucusunun seri portu yoktur. Merkez kipinde tum port islemleri
// koprude yapilir. Firma birden fazla kopru isletiyorsa hangi makineye
// komut gidecegi PILOTUN karari olmalidir; rastgele secim, A cantasini
// kalibre ederken B cantasina komut gondermek demektir.
//
// Tek aday varsa secim BOS birakilir: merkez tek adayi kendisi bulur ve
// pilotun ek bir sey yapmasi gerekmez.
// ---------------------------------------------------------------
let _i2Kopruler = [];        // [{ornek_id, ad}] gcsdual calisan makineler
let _i2KopruSecili = 0;      // 0 -> merkez karar verir

function i2Gonder(paket) {
  if (typeof ws === "undefined" || !ws || ws.readyState !== 1) return false;
  // Secili makine TUM istasyon2 komutlarina eklenir. Tek yerde
  // yapilir: her cagri yerine elle eklenirse biri atlanir ve o komut
  // sessizce baska makineye gider.
  if (_i2KopruSecili > 0 && paket && typeof paket.tip === "string" &&
      paket.tip.indexOf("istasyon2_") === 0 &&
      paket.kopru_ornek_id === undefined)
    paket.kopru_ornek_id = _i2KopruSecili;
  ws.send(JSON.stringify(paket));
  return true;
}

// program_ayar.js kopru listesi her tazelendiginde cagirir.
window.istasyon2KopruListesiGuncelle = function (liste) {
  _i2Kopruler = Array.isArray(liste) ? liste.slice() : [];
  // Secili makine listeden DUSTUYSE secim temizlenir. Aksi halde
  // kapanmis bir makineye komut gonderilmeye devam edilir ve pilot
  // "bu firmaya ait degil" gibi ilgisiz bir hata okur.
  if (_i2KopruSecili > 0 &&
      !_i2Kopruler.some((k) => parseInt(k.ornek_id, 10) === _i2KopruSecili))
    _i2KopruSecili = 0;
  i2KopruSeciciCiz();
};

function i2KopruSeciciCiz() {
  const sar = document.getElementById("i2KopruSar");
  const sec = document.getElementById("i2KopruSec");
  if (!sar || !sec) return;
  // Tek aday varsa secici GEREKSIZDIR: merkez zaten onu bulur. Gorunur
  // birakmak paneli kalabaliklastirir ve pilota olmayan bir karar
  // sunar. Lokal kurulumda liste her zaman bostur.
  if (_i2Kopruler.length < 2) {
    sar.style.display = "none";
    return;
  }
  sar.style.display = "";
  const t = i2D();
  const onceki = _i2KopruSecili;
  sec.innerHTML = "";
  const bos = document.createElement("option");
  bos.value = "";
  bos.textContent = t.i2KopruSec || "Saha makinesi se\u00e7...";
  sec.appendChild(bos);
  for (const k of _i2Kopruler) {
    const o = document.createElement("option");
    o.value = String(k.ornek_id);
    o.textContent = k.ad;
    sec.appendChild(o);
  }
  sec.value = onceki > 0 ? String(onceki) : "";
}

function i2Toast(baslik, mesaj, seviye) {
  if (typeof window.uyariToastGoster === "function") {
    window.uyariToastGoster({
      baslik: baslik, mesaj: mesaj,
      seviye: seviye || "bilgi", kategori: "sistem",
    });
  }
}

// ---------------------------------------------------------------
// HARITA 3B KONTROLU (J1/J2 + T2)
// ---------------------------------------------------------------
// Olu bolge: kalibrasyon backend'de yapilir ama normalize deger yine
// de sifir civarinda gezinir (ADC gurultusu). Bu esik altinda kamera
// hic itilmez; aksi halde cubuk birakilmis olsa da harita surekli
// kayar ve pilot haritayi "kacmis" gorur.
function i2Olu(v) {
  const d = Number(v) || 0;
  if (Math.abs(d) < I2_OLU) return 0;
  // Olu bolgeyi cikardiktan sonra yeniden 0..1'e olcekle: cubuk esigi
  // gectigi anda kamera ziplamaz, yumusak baslar.
  const isaret = d < 0 ? -1 : 1;
  return isaret * ((Math.abs(d) - I2_OLU) / (1 - I2_OLU));
}

function i2KameraHizGuncelle(d) {
  const n = (d && d.normalize) || {};
  const olcek = (d && Number(d.harita_hiz)) || 1.0;
  _i2Kamera.dx = i2Olu(n.J1_X) * olcek;   // dondurme
  _i2Kamera.dy = i2Olu(n.J1_Y) * olcek;   // egim
  _i2Kamera.kx = i2Olu(n.J2_X) * olcek;   // dogu/bati
  _i2Kamera.ky = i2Olu(n.J2_Y) * olcek;   // kuzey/guney
  const t2 = (d && d.durum && d.durum.toggles && d.durum.toggles.T2) || "CENTER";
  _i2Kamera.zoom = (t2 === "UP") ? 1 : (t2 === "DOWN") ? -1 : 0;
  i2KareBaslat();
}

function i2KareGerek() {
  return (_i2Kamera.dx || _i2Kamera.dy || _i2Kamera.kx ||
          _i2Kamera.ky || _i2Kamera.zoom);
}

function i2KareBaslat() {
  if (_i2Kare || !i2KareGerek()) return;
  _i2SonKare = performance.now();
  _i2Kare = requestAnimationFrame(i2Kare);
}

function i2Kare(simdi) {
  _i2Kare = 0;
  const dt = Math.min(0.1, Math.max(0, (simdi - _i2SonKare) / 1000));
  _i2SonKare = simdi;
  if (typeof viewer === "undefined" || !viewer || viewer.isDestroyed()) return;
  // Arka plan sekmesi kamerayi cekmesin (iki sekme acikken cakisma)
  if (document.hidden) { i2KareBaslat(); return; }

  const kam = viewer.camera;
  try {
    // Yukseklik: kaydirma ve zoom adimlari yukseklikle olceklenir.
    // 1 km'de 30 m/s uygun bir hizken 100 km'de aynisi felce yakindir.
    const kart = kam.positionCartographic;
    const yuk = Math.max(50, kart ? kart.height : 1000);

    if (_i2Kamera.dx) {
      // Sag/sol: kamerayi kendi ekseninde dondur (heading)
      kam.rotateRight(Cesium.Math.toRadians(
        I2_DONME_HIZ * _i2Kamera.dx * dt));
    }
    if (_i2Kamera.dy) {
      // Ileri/geri: egim (pitch). Cubuk ileri -> yere bak.
      kam.lookUp(Cesium.Math.toRadians(
        I2_EGIM_HIZ * _i2Kamera.dy * dt));
    }
    if (_i2Kamera.kx || _i2Kamera.ky) {
      const adim = yuk * I2_KAYMA_ORAN * dt;
      if (_i2Kamera.kx) kam.moveRight(adim * _i2Kamera.kx);
      if (_i2Kamera.ky) kam.moveForward(adim * _i2Kamera.ky);
    }
    if (_i2Kamera.zoom) {
      // Zoom: yuksekligin orani kadar. Yere cakilmayi onlemek icin
      // 60 m'nin altina inilmez.
      const adim = yuk * I2_ZOOM_ORAN * dt;
      if (_i2Kamera.zoom > 0) {
        if (yuk - adim > 60) kam.moveForward(adim);
      } else {
        kam.moveBackward(adim);
      }
    }
  } catch (e) {
    // Kamera surmede hata olursa hareketi durdur; dron ucuran bir
    // arayuzde her karede istisna atan bir dongu kabul edilemez.
    console.warn("[IST2] kamera surme hatasi:", e);
    _i2Kamera.dx = _i2Kamera.dy = _i2Kamera.kx = _i2Kamera.ky = 0;
    _i2Kamera.zoom = 0;
    return;
  }
  i2KareBaslat();
}

// ---------------------------------------------------------------
// HARITA EYLEMLERI (P8-P11, T1)
// ---------------------------------------------------------------
// P11: haritadaki noktalar. Kaynaklar harita.js'teki "tumunu sigdir"
// ile ayni; her erisim `typeof` ile korunur cunku modul yuklenme
// sirasi degisirse global tanimsiz olabilir.
function i2Noktalar() {
  const nok = [];
  const ekle = (lat, lon, ad) => {
    if (typeof lat !== "number" || typeof lon !== "number") return;
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
    nok.push({ lat: lat, lon: lon, ad: ad || "" });
  };
  try {
    if (typeof sonDronlar !== "undefined" && sonDronlar) {
      for (const d of Object.values(sonDronlar)) {
        if (d && d.lat && d.lon) ekle(d.lat, d.lon, d.ad || ("D" + d.sysid));
      }
    }
  } catch (e) {}
  try {
    if (typeof sonRadarHedefler !== "undefined" && sonRadarHedefler) {
      for (const h of Object.values(sonRadarHedefler)) {
        if (h && h.lat && h.lon) ekle(h.lat, h.lon, h.ad || "HEDEF");
      }
    }
  } catch (e) {}
  try {
    if (window._lokasyonlarSon) {
      for (const l of window._lokasyonlarSon) {
        if (l) ekle(l.lat, l.lon, l.ad || "LOKASYON");
      }
    }
  } catch (e) {}
  try {
    if (window._kameralarSon) {
      for (const k of window._kameralarSon) {
        if (k) ekle(k.lat, k.lon, k.isim || k.ad || "KAMERA");
      }
    }
  } catch (e) {}
  try {
    if (typeof gcsKonum !== "undefined" && gcsKonum)
      ekle(gcsKonum.lat, gcsKonum.lon, "GCS");
  } catch (e) {}
  return nok;
}

function i2NoktayaGit() {
  const nok = i2Noktalar();
  const t = i2D();
  if (!nok.length) {
    i2Toast(t.i2Baslik || "Yer Istasyonu 2",
            t.i2NoktaYok || "Haritada gezilecek nokta yok.", "uyari");
    return;
  }
  if (_i2NoktaSira >= nok.length) _i2NoktaSira = 0;
  const n = nok[_i2NoktaSira];
  _i2NoktaSira = (_i2NoktaSira + 1) % nok.length;
  try {
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(n.lon, n.lat, 1200),
      duration: 1.0,
    });
  } catch (e) { return; }
  i2Toast(t.i2Baslik || "Yer Istasyonu 2",
          (t.i2NoktaGit || "Nokta") + ": " + n.ad +
          " (" + (_i2NoktaSira || nok.length) + "/" + nok.length + ")",
          "bilgi");
}

// T1 = patlatma kolu. Kol ACILDIGINDA onay penceresi acilir, kol
// KAPANDIGINDA pencere kendiliginden kapanir (fiziksel kol tek
// dogruluk kaynagidir: ekranda "emin misiniz" durup kol inmisse
// yaniltici olur).
function i2PatlatOnay(acik) {
  if (!acik) {
    if (_i2OnayAcik) { _i2OnayAcik.remove(); _i2OnayAcik = null; }
    return;
  }
  if (_i2OnayAcik) return;
  const t = i2D();
  const kap = document.createElement("div");
  kap.className = "i2-onay-kap";
  kap.innerHTML =
    "<div class='i2-onay'>" +
      "<div class='i2-onay-bas'><i class='fa-solid fa-triangle-exclamation'></i> " +
        i2Kacis(t.i2PatlatBaslik || "PATLATMA ONAYI") + "</div>" +
      "<div class='i2-onay-govde'>" +
        "<div class='i2-onay-soru'>" +
          i2Kacis(t.i2PatlatSoru || "Patlatmak icin emin misiniz?") + "</div>" +
        "<div class='i2-onay-not'>" +
          i2Kacis(t.i2PatlatNot ||
            "T1 kolu acik konumda. Kolu kapatmak bu pencereyi kapatir.") +
        "</div>" +
      "</div>" +
      "<div class='i2-onay-alt'>" +
        "<button class='i2-onay-iptal'>" +
          i2Kacis(t.i2Vazgec || t.iptal || "Vazge\u00e7") + "</button>" +
        "<button class='i2-onay-tamam'>" +
          i2Kacis(t.i2PatlatEvet || "EVET, PATLAT") + "</button>" +
      "</div>" +
    "</div>";
  document.body.appendChild(kap);
  _i2OnayAcik = kap;
  kap.querySelector(".i2-onay-iptal").addEventListener("click", () => {
    kap.remove(); _i2OnayAcik = null;
  });
  kap.querySelector(".i2-onay-tamam").addEventListener("click", () => {
    kap.remove(); _i2OnayAcik = null;
    // Imha komutu bu surumde BAGLANMADI: patlatma cikisinin hangi
    // servo/role kanalina bagli oldugu kullanici tarafindan
    // bildirilmedi. Onay akisi hazir; komut tek satirla eklenecek.
    i2Toast(t.i2PatlatBaslik || "PATLATMA ONAYI",
            t.i2PatlatBekliyor ||
            "Onay alindi. Imha cikisi (servo/role kanali) tanimlanmadigi " +
            "icin komut gonderilmedi.", "uyari");
  });
}

// Sunucudan gelen harita eylemi
function i2HaritaEylem(eylem, ayrinti) {
  const t = i2D();
  if (eylem === "harita_kaynak") {
    if (typeof window.haritaKaynakSirala === "function") {
      const yeni = window.haritaKaynakSirala(1);
      const ad = (typeof window.katmanAdi === "function")
        ? window.katmanAdi(yeni) : yeni;
      i2Toast(t.i2Baslik || "Yer Istasyonu 2",
              (t.i2HaritaKaynak || "Harita kaynagi") + ": " + ad, "bilgi");
    }
  } else if (eylem === "kullanici_konum") {
    if (typeof window.haritaKonumumaGit === "function")
      window.haritaKonumumaGit();
  } else if (eylem === "hepsini_kapsa") {
    if (typeof window.haritaTumunuSigdir === "function")
      window.haritaTumunuSigdir();
  } else if (eylem === "nokta_gez") {
    i2NoktayaGit();
  } else if (eylem === "patlat_onay") {
    i2PatlatOnay(!!(ayrinti && ayrinti.acik));
  } else if (eylem === "harita_zoom_in") {
    _i2Kamera.zoom = 1; i2KareBaslat();
  } else if (eylem === "harita_zoom_out") {
    _i2Kamera.zoom = -1; i2KareBaslat();
  } else if (eylem === "harita_zoom_dur") {
    _i2Kamera.zoom = 0;
  }
}

// ---------------------------------------------------------------
// WS mesaj girisleri (ws.js buradan cagirir)
// ---------------------------------------------------------------
window.istasyon2DurumIsle = function (m) {
  _i2Durum = m || null;
  i2KameraHizGuncelle(_i2Durum);
  if (_i2Popup) i2PanelCiz();
};

window.istasyon2EylemIsle = function (m) {
  const eylem = (m && m.eylem) || "";
  i2AkisEkle((m && m.ayrinti && m.ayrinti.kanal) || eylem,
             i2EylemAd(eylem) || eylem);
  i2HaritaEylem(eylem, (m && m.ayrinti) || {});
};

window.istasyon2EylemSonucIsle = function (m) {
  const t = i2D();
  const kanal = (m && m.kanal) || "";
  const eylem = (m && m.eylem) || "";
  i2AkisEkle(kanal || eylem, (i2EylemAd(eylem) || eylem) +
    (m && m.basari ? " \u2713" : " \u2717"));
  if (m && !m.basari) {
    // En sik sebep: panel dugmesine basildi ama hicbir dronda joystick
    // kontrolu acik degil. Pilot bunu gormeli, yoksa "dugme bozuk"
    // sanir.
    const sebep = (m.sebep === "joystick_kapali")
      ? (t.i2JoystickKapali ||
         "Joystick kontrolu acik bagli dron yok - komut gonderilmedi.")
      : (t.i2EylemBasarisiz || "Eylem uygulanamadi.");
    i2Toast((t.i2Baslik || "Yer Istasyonu 2") + " \u00b7 " + (kanal || eylem),
            sebep, "uyari");
  } else if (m && m.sysidler && m.sysidler.length) {
    const ak = (m.aksiyonlar || []).join(", ");
    i2Toast((t.i2Baslik || "Yer Istasyonu 2") + " \u00b7 " + (kanal || eylem),
            "D" + m.sysidler.join(", D") + " \u2192 " + ak, "basari");
  }
  if (_i2Popup) i2PanelCiz();
};

window.istasyon2PortlarIsle = function (m) {
  _i2Portlar = (m && m.portlar) || [];
  if (_i2Popup) i2PortlariCiz();
};

window.istasyon2SonucIsle = function (m) {
  const t = i2D();
  if (m && m.islem === "baglan" && !m.basari) {
    i2Toast(t.i2Baslik || "Yer Istasyonu 2",
            (t.i2BaglanamadiOn || "Baglanamadi: ") + (m.sebep || ""), "hata");
  }
};

function i2AkisEkle(kanal, aciklama) {
  const z = new Date();
  const saat = String(z.getHours()).padStart(2, "0") + ":" +
               String(z.getMinutes()).padStart(2, "0") + ":" +
               String(z.getSeconds()).padStart(2, "0");
  _i2Akis.unshift({ saat: saat, kanal: kanal, aciklama: aciklama });
  if (_i2Akis.length > 20) _i2Akis.length = 20;
}

// ---------------------------------------------------------------
// PANEL
// ---------------------------------------------------------------
function istasyon2Ac() {
  if (_i2Popup) { i2Durumsor(); return; }
  const t = i2D();
  const pop = document.createElement("div");
  pop.className = "i2-popup";
  _i2Popup = pop;

  const bas = (typeof dkMiniPopupBaslikKur === "function")
    ? dkMiniPopupBaslikKur(pop, t.i2Baslik || "YER \u0130STASYONU 2",
                           "istasyon2", "fa-gamepad")
    : null;
  const kapatBtn = pop.querySelector(".dk-mp-kapat");
  if (kapatBtn) kapatBtn.addEventListener("click", istasyon2Kapat);
  if (bas && kapatBtn) {
    const yenile = document.createElement("button");
    yenile.className = "i2-yenile";
    yenile.title = t.yenile || "Yenile";
    yenile.innerHTML = "<i class='fa-solid fa-rotate-right'></i>";
    yenile.addEventListener("click", (ev) => {
      ev.stopPropagation();
      i2Durumsor();
      i2Gonder({ tip: "istasyon2_portlar" });
    });
    bas.insertBefore(yenile, kapatBtn);
  }

  const govde = document.createElement("div");
  govde.className = "i2-govde";
  govde.innerHTML =
    "<div class='i2-bag'>" +
      "<div class='i2-bag-sol'>" +
        // v2.4.59: saha makinesi secici. Yalniz IKI ve daha fazla
        // aday varsa gorunur (bkz. i2KopruSeciciCiz).
        "<div class='i2-kopru-sar' id='i2KopruSar' style='display:none'>" +
          "<label class='i2-etiket'>" +
            i2Kacis(t.i2Kopru || "Saha makinesi") + "</label>" +
          "<select id='i2KopruSec' class='i2-sec i2-sec-genis'></select>" +
        "</div>" +
        "<label class='i2-etiket'>" + i2Kacis(t.i2Port || "Seri port") +
          "</label>" +
        "<div class='i2-port-satir'>" +
          "<input type='text' id='i2Port' class='i2-giris' " +
            "placeholder='/dev/ttyACM0'>" +
          "<select id='i2PortSec' class='i2-sec'></select>" +
        "</div>" +
        "<label class='i2-onay-kutu'>" +
          "<input type='checkbox' id='i2Otomatik'> " +
          i2Kacis(t.i2Otomatik || "A\u00e7\u0131l\u0131\u015fta otomatik ba\u011flan") +
        "</label>" +
      "</div>" +
      "<div class='i2-bag-sag'>" +
        "<div id='i2DurumRozet' class='i2-rozet'>-</div>" +
        "<div class='i2-dugmeler'>" +
          "<button id='i2Baglan' class='i2-btn i2-btn-ana'>" +
            i2Kacis(t.i2Baglan || t.baglan || "Ba\u011flan") + "</button>" +
          "<button id='i2Kes' class='i2-btn'>" +
            i2Kacis(t.i2Kes || t.kes || "Kes") + "</button>" +
          "<button id='i2Ping' class='i2-btn'>PING</button>" +
          "<button id='i2Kalibre' class='i2-btn'>" +
            i2Kacis(t.i2Kalibre || "Kalibre et") + "</button>" +
        "</div>" +
      "</div>" +
    "</div>" +
    "<div class='i2-olcu' id='i2Olcu'></div>" +
    "<div class='i2-bolum-bas'>" +
      i2Kacis(t.i2Butonlar || "BUTONLAR") + "</div>" +
    "<div class='i2-btn-izgara' id='i2Izgara'></div>" +
    "<div class='i2-alt-iki'>" +
      "<div class='i2-kol-blok'>" +
        "<div class='i2-bolum-bas'>" +
          i2Kacis(t.i2Toggle || "KOLLAR") + "</div>" +
        "<div id='i2Kollar' class='i2-kollar'></div>" +
        "<div class='i2-bolum-bas'>" +
          i2Kacis(t.i2Led || "LED DENET\u0130M\u0130") + "</div>" +
        "<div id='i2Ledler' class='i2-ledler'></div>" +
      "</div>" +
      "<div class='i2-joy-blok'>" +
        "<div class='i2-bolum-bas'>" +
          i2Kacis(t.i2Joystick || "JOYST\u0130CKLER") + "</div>" +
        "<div class='i2-joylar' id='i2Joylar'></div>" +
      "</div>" +
    "</div>" +
    "<div class='i2-bolum-bas'>" +
      i2Kacis(t.i2Akis || "OLAY AKI\u015eI") + "</div>" +
    "<div class='i2-akis' id='i2AkisKap'></div>";
  pop.appendChild(govde);

  // Yeniden boyutlandirma (Kayitli Dronlar paneliyle ayni desen:
  // ilk suruklemede panel piksele sabitlenir, transform kaldirilir)
  const tutamac = document.createElement("div");
  tutamac.className = "i2-resize";
  tutamac.innerHTML =
    "<i class='fa-solid fa-grip-lines' style='transform:rotate(-45deg);'></i>";
  pop.appendChild(tutamac);
  let boyut = null;
  tutamac.addEventListener("pointerdown", (ev) => {
    const r = pop.getBoundingClientRect();
    pop.style.transform = "none";
    pop.style.left = r.left + "px";
    pop.style.top = r.top + "px";
    pop.style.width = r.width + "px";
    pop.style.height = r.height + "px";
    pop.style.maxHeight = "none";
    boyut = { w: r.width, h: r.height, x: ev.clientX, y: ev.clientY };
    try { tutamac.setPointerCapture(ev.pointerId); } catch (e) {}
    ev.preventDefault();
    ev.stopPropagation();
  });
  tutamac.addEventListener("pointermove", (ev) => {
    if (!boyut) return;
    pop.style.width = Math.max(560, boyut.w + (ev.clientX - boyut.x)) + "px";
    pop.style.height = Math.max(420, boyut.h + (ev.clientY - boyut.y)) + "px";
  });
  tutamac.addEventListener("pointerup", () => { boyut = null; });

  document.body.appendChild(pop);

  // v2.4.52 - PANEL EKRAN DISINDA ACILMA KUSURU DUZELTILDI
  //
  // Onceki surumde kayitli konum kosulsuz uygulaniyordu. Iki sorun:
  //   1) .i2-popup CSS'te transform:translate(-50%,-50%) ile ortalanir.
  //      Yalniz left/top yazilinca transform yerinde kalir ve panel
  //      720px genislikte 360px sola kayar. Kullanici paneli ekranin
  //      solunda (-300 gibi) gorur; baslik cubugu disarida kaldigi
  //      icin ne tutup cekebilir ne de kapatabilir.
  //   2) Bozuk kayit bir kez yazildiginda her acilista tekrarlanir.
  //
  // Cozum: kayit GECERLI ise uygula, degilse yok say ve CSS
  //        varsayilaninda (ortada) birak. Bozuk kayit ayrica silinir
  //        ki bir daha ayni sorun yasanmasin.
  const kayitGecerli = (typeof window.pencereKonumGecerliMi === "function")
    ? window.pencereKonumGecerliMi("istasyon2", pop.offsetWidth, pop.offsetHeight)
    : true;
  if (kayitGecerli) {
    if (typeof window.pencereKonumUygula === "function")
      window.pencereKonumUygula("istasyon2", pop, true);
  } else {
    // Bozuk/ekran disi kayit: sil ve paneli ortada birak.
    if (typeof window.pencereKonumSil === "function")
      window.pencereKonumSil("istasyon2");
    pop.style.left = "50%";
    pop.style.top = "50%";
    pop.style.transform = "translate(-50%, -50%)";
  }

  // Olaylar
  document.getElementById("i2Baglan").addEventListener("click", () => {
    const p = (document.getElementById("i2Port").value || "").trim();
    i2Gonder({ tip: "istasyon2_baglan", port: p });
  });
  document.getElementById("i2Kes").addEventListener("click", () => {
    i2Gonder({ tip: "istasyon2_kes" });
  });
  document.getElementById("i2Ping").addEventListener("click", () => {
    i2Gonder({ tip: "istasyon2_led", kanal: "PING" });
  });
  document.getElementById("i2Kalibre").addEventListener("click", () => {
    i2Gonder({ tip: "istasyon2_kalibre" });
  });
  document.getElementById("i2Otomatik").addEventListener("change", (ev) => {
    i2Gonder({ tip: "istasyon2_ayar", otomatik: !!ev.target.checked });
  });
  document.getElementById("i2PortSec").addEventListener("change", (ev) => {
    if (ev.target.value)
      document.getElementById("i2Port").value = ev.target.value;
  });
  const kopruSec = document.getElementById("i2KopruSec");
  if (kopruSec) kopruSec.addEventListener("change", (ev) => {
    _i2KopruSecili = parseInt(ev.target.value, 10) || 0;
    // Makine degisti: eski makinenin portlari ve durumu ARTIK
    // gecersizdir. Temizlenmezse pilot A makinesinin port listesinden
    // secip B makinesine baglanmaya calisir.
    _i2Portlar = [];
    _i2Durum = null;
    i2PortlariCiz();
    i2Durumsor();
    i2Gonder({ tip: "istasyon2_portlar" });
  });

  // Panel her acildiginda secici listesi tazelenir: kopru listesi
  // panel kapaliyken degismis olabilir.
  if (typeof window.kopruGcsdualAdaylari === "function")
    _i2Kopruler = window.kopruGcsdualAdaylari() || [];
  i2KopruSeciciCiz();

  i2Durumsor();
  i2Gonder({ tip: "istasyon2_portlar" });
  i2PanelCiz();
}

function istasyon2Kapat() {
  if (typeof window.pencereKonumKaydet === "function" && _i2Popup)
    window.pencereKonumKaydet("istasyon2", _i2Popup, true);
  if (_i2Popup) _i2Popup.remove();
  _i2Popup = null;
}

function i2Durumsor() {
  i2Gonder({ tip: "istasyon2_durum" });
}

function i2PortlariCiz() {
  const sec = document.getElementById("i2PortSec");
  if (!sec) return;
  const t = i2D();
  sec.innerHTML = "<option value=''>" +
    i2Kacis(t.i2PortSec || "Portlar\u0131 tara...") + "</option>";
  for (const p of _i2Portlar) {
    const o = document.createElement("option");
    o.value = p.port || "";
    o.textContent = (p.port || "?") + " \u2014 " + (p.aciklama || "");
    sec.appendChild(o);
  }
}

function i2PanelCiz() {
  if (!_i2Popup || !_i2Durum) return;
  const t = i2D();
  const d = _i2Durum;
  const dr = d.durum || {};
  const btn = dr.buttons || {};
  const tg = dr.toggles || {};
  const led = dr.leds || {};
  const nrm = d.normalize || {};
  const esl = d.buton_esleme || {};
  const ledli = d.ledli || [];
  const ucus = d.ucus_eylemleri || {};
  const harita = d.harita_eylemleri || {};

  // Baglanti rozeti
  const rozet = document.getElementById("i2DurumRozet");
  if (rozet) {
    if (d.bagli) {
      rozet.className = "i2-rozet i2-rozet-ok";
      rozet.textContent = (t.i2Bagli || "BA\u011eLI") + " \u00b7 " +
        (d.port || "") + " @ " + (d.baud || 115200);
    } else {
      rozet.className = "i2-rozet i2-rozet-yok";
      rozet.textContent = (t.i2Kopuk || "BA\u011eLI DE\u011e\u0130L") +
        (d.hata ? (" \u00b7 " + d.hata) : "");
    }
  }
  const pg = document.getElementById("i2Port");
  if (pg && document.activeElement !== pg)
    pg.value = d.port_ayar || d.port || "";
  const oto = document.getElementById("i2Otomatik");
  if (oto) oto.checked = !!d.otomatik;

  // Olcum satiri
  const olcu = document.getElementById("i2Olcu");
  if (olcu) {
    const s = d.sayac || {};
    olcu.innerHTML =
      "<span>" + i2Kacis(t.i2Alinan || "Al\u0131nan") + ": <b>" +
        (s.rx || 0) + "</b></span>" +
      "<span>" + i2Kacis(t.i2Gonderilen || "G\u00f6nderilen") + ": <b>" +
        (s.tx || 0) + "</b></span>" +
      "<span>PONG: <b>" + (s.pong || 0) + "</b></span>" +
      "<span>" + i2Kacis(t.i2Bozuk || "Bozuk") + ": <b" +
        ((s.bozuk || 0) > 0 ? " class='i2-kotu'" : "") + ">" +
        (s.bozuk || 0) + "</b></span>" +
      "<span>" + i2Kacis(t.i2Gecikme || "Gecikme") + ": <b>" +
        (d.gecikme_ms || 0) + " ms</b></span>" +
      "<span>" + i2Kacis(t.i2KalibreDurum || "Kalibrasyon") + ": <b>" +
        (d.kalibre ? (t.i2Var || "var") : (t.i2Yok || "yok")) + "</b></span>";
  }

  // Buton izgarasi
  const izg = document.getElementById("i2Izgara");
  if (izg) {
    let h = "";
    for (let i = 1; i <= 11; i++) {
      const k = "P" + i;
      const basili = !!btn[k];
      const ledVar = ledli.indexOf(k) >= 0;
      const eylem = esl[k] || "";
      const ad = i2EylemAd(eylem, ucus, harita);
      const tur = ucus[eylem] ? "i2-ucus" : (harita[eylem] ? "i2-harita" : "");
      h += "<div class='i2-tus " + (basili ? "i2-tus-basili " : "") +
           (ledVar ? "i2-tus-ledli " : "") + tur + "'>" +
             "<div class='i2-tus-ust'>" +
               "<span class='i2-tus-ad'>" + k + "</span>" +
               (ledVar ? "<span class='i2-tus-led" +
                 (led[k] ? " i2-tus-led-acik" : "") + "'></span>" : "") +
             "</div>" +
             "<div class='i2-tus-eylem'>" + i2Kacis(ad || "\u2014") + "</div>" +
           "</div>";
    }
    izg.innerHTML = h;
  }

  // Kollar
  const kol = document.getElementById("i2Kollar");
  if (kol) {
    const t1 = !!tg.T1;
    const t2 = String(tg.T2 || "CENTER");
    kol.innerHTML =
      "<div class='i2-kol " + (t1 ? "i2-kol-acik" : "") + "'>" +
        "<div class='i2-kol-ad'>T1</div>" +
        "<div class='i2-kol-deger'>" + (t1 ? "1" : "0") + "</div>" +
        "<div class='i2-kol-not'>" +
          i2Kacis(t1 ? (t.i2PatlatAcik || "PATLATMA KOLU A\u00c7IK")
                     : (t.i2PatlatKapali || "kapal\u0131")) + "</div>" +
      "</div>" +
      "<div class='i2-kol i2-kol-t2'>" +
        "<div class='i2-kol-ad'>T2</div>" +
        "<div class='i2-kol-deger'>" + i2Kacis(t2) + "</div>" +
        "<div class='i2-kol-not'>" +
          i2Kacis(t2 === "UP" ? (t.i2ZoomIn || "zoom")
                : t2 === "DOWN" ? (t.i2ZoomOut || "ters zoom")
                : (t.i2ZoomDur || "dur")) + "</div>" +
      "</div>";
  }

  // LED denetimi
  const ledKap = document.getElementById("i2Ledler");
  if (ledKap) {
    let h = "";
    for (const p of ledli) {
      h += "<button class='i2-led-btn" + (led[p] ? " i2-led-acik" : "") +
           "' data-led='" + p + "'>" + p + "</button>";
    }
    h += "<button class='i2-led-btn i2-led-hepsi' data-led='ALL' " +
         "data-deger='1'>ALL ON</button>" +
         "<button class='i2-led-btn i2-led-hepsi' data-led='ALL' " +
         "data-deger='0'>ALL OFF</button>";
    ledKap.innerHTML = h;
    for (const b of ledKap.querySelectorAll(".i2-led-btn")) {
      b.addEventListener("click", () => {
        const k = b.getAttribute("data-led");
        let acik;
        if (b.hasAttribute("data-deger")) {
          acik = b.getAttribute("data-deger") === "1";
        } else {
          acik = !led[k];
        }
        i2Gonder({ tip: "istasyon2_led", kanal: k, acik: acik });
      });
    }
  }

  // Joystickler (canvas)
  const joyKap = document.getElementById("i2Joylar");
  if (joyKap) {
    const ekAdlar = d.ek_eksen_adlari || [];
    const cubuklar = [
      { ad: "J1", x: "J1_X", y: "J1_Y",
        not: t.i2J1Not || "harita d\u00f6nd\u00fcr / e\u011fim" },
      { ad: "J2", x: "J2_X", y: "J2_Y",
        not: t.i2J2Not || "harita kayd\u0131r" },
    ];
    if (ekAdlar.length === 4) {
      cubuklar.push({ ad: ekAdlar[0].split("_")[0], x: ekAdlar[0],
                      y: ekAdlar[1], dron: true,
                      not: t.i2DronNot || "DRON: yaw / irtifa" });
      cubuklar.push({ ad: ekAdlar[2].split("_")[0], x: ekAdlar[2],
                      y: ekAdlar[3], dron: true,
                      not: t.i2DronNot2 || "DRON: yanal / ileri-geri" });
    }
    if (joyKap.childElementCount !== cubuklar.length) {
      joyKap.innerHTML = "";
      for (const c of cubuklar) {
        const kutu = document.createElement("div");
        kutu.className = "i2-joy" + (c.dron ? " i2-joy-dron" : "");
        kutu.innerHTML =
          "<canvas width='118' height='118' data-joy='" + c.ad + "'></canvas>" +
          "<div class='i2-joy-ad'>" + i2Kacis(c.ad) + "</div>" +
          "<div class='i2-joy-not'>" + i2Kacis(c.not) + "</div>" +
          "<div class='i2-joy-deger' data-deger='" + c.ad + "'></div>";
        joyKap.appendChild(kutu);
      }
    }
    for (const c of cubuklar) {
      const cv = joyKap.querySelector("canvas[data-joy='" + c.ad + "']");
      const dv = joyKap.querySelector("[data-deger='" + c.ad + "']");
      const nx = Number(nrm[c.x]) || 0;
      const ny = Number(nrm[c.y]) || 0;
      if (cv) i2JoyCiz(cv, nx, ny, !!c.dron);
      if (dv) {
        const hx = (dr.joysticks || {})[c.x];
        const hy = (dr.joysticks || {})[c.y];
        const ex = (dr.ek_eksen || {})[c.x];
        const ey = (dr.ek_eksen || {})[c.y];
        dv.textContent =
          "X " + (hx !== undefined ? hx : (ex !== undefined ? ex : "-")) +
          " (" + nx.toFixed(2) + ")  \u00b7  Y " +
          (hy !== undefined ? hy : (ey !== undefined ? ey : "-")) +
          " (" + ny.toFixed(2) + ")";
      }
    }
  }

  // Olay akisi
  const akis = document.getElementById("i2AkisKap");
  if (akis) {
    let h = "";
    for (const a of _i2Akis) {
      h += "<div class='i2-akis-satir'><span class='i2-akis-saat'>" +
        i2Kacis(a.saat) + "</span><span class='i2-akis-kanal'>" +
        i2Kacis(a.kanal) + "</span><span class='i2-akis-ac'>" +
        i2Kacis(a.aciklama) + "</span></div>";
    }
    akis.innerHTML = h || "<div class='i2-akis-bos'>" +
      i2Kacis(t.i2AkisBos || "Hen\u00fcz olay yok.") + "</div>";
  }
}

// Joystick gorseli: merkez, olu bolge halkasi ve o anki konum
function i2JoyCiz(cv, nx, ny, dron) {
  const c = cv.getContext("2d");
  const w = cv.width, h = cv.height;
  const cx = w / 2, cy = h / 2, r = Math.min(w, h) / 2 - 6;
  c.clearRect(0, 0, w, h);
  // Cerceve
  c.strokeStyle = dron ? "#f0a020" : "#3a4a5a";
  c.lineWidth = 1.5;
  c.beginPath(); c.arc(cx, cy, r, 0, Math.PI * 2); c.stroke();
  // Olu bolge
  c.strokeStyle = "rgba(255,255,255,0.14)";
  c.setLineDash([3, 3]);
  c.beginPath(); c.arc(cx, cy, r * I2_OLU * 3, 0, Math.PI * 2); c.stroke();
  c.setLineDash([]);
  // Eksen cizgileri
  c.strokeStyle = "rgba(255,255,255,0.10)";
  c.beginPath();
  c.moveTo(cx - r, cy); c.lineTo(cx + r, cy);
  c.moveTo(cx, cy - r); c.lineTo(cx, cy + r);
  c.stroke();
  // Konum (ekranda Y yukari pozitif olsun -> isaret ters)
  const px = cx + Math.max(-1, Math.min(1, nx)) * r;
  const py = cy - Math.max(-1, Math.min(1, ny)) * r;
  c.strokeStyle = dron ? "#f0a020" : "#2ea8ff";
  c.lineWidth = 2;
  c.beginPath(); c.moveTo(cx, cy); c.lineTo(px, py); c.stroke();
  c.fillStyle = dron ? "#f0a020" : "#2ea8ff";
  c.beginPath(); c.arc(px, py, 5.5, 0, Math.PI * 2); c.fill();
}

// Dil degisiminde paneli yeniden ciz
window.istasyon2DilTazele = function () {
  if (_i2Popup) { istasyon2Kapat(); istasyon2Ac(); }
};

// -----------------------------------------------------------------
// v2.4.45 - GCCDUAL MENU GORUNUMU (radar deseniyle ayni)
// Program Ayarlari'nda "Yer Kontrol Istasyonu Dual" KAPALI ise Goktungu
// menusundeki oge TAMAMEN gizlenir ve acik panel kapatilir. Kullanici
// farkli istasyon cihazlari kullandigini bildirdi; cantasi olmayan
// kurulumda menude olu bir oge gorunmemelidir.
// -----------------------------------------------------------------
let i2ArayuzAcik = false;      // sunucudaki istasyon2_arayuz degeri
function istasyon2MenuGorunumGuncelle() {
  const oge = document.getElementById("mbIstasyon2");
  const ayr = document.getElementById("mbIstasyon2Ayrac");
  // v2.4.56: merkezde calisan ornekte GCCDUAL cantasi saha makinesinde
  // KOPRU SERVISI (`gcsdual`) olarak yasar; yetenegin TEK kaynagi odur.
  //
  // Onceki surumde program ayari ile VEYA'lanmisti. Bu yanlisti: merkezin
  // kendi program ayari acik oldugu icin, sahada canta hic baglanmamisken
  // menu gorunur kaliyor ve tiklayinca islevsiz panel aciliyordu. Merkez
  // sunucusuna fiziksel canta takilamaz; ayarin yetenek uzerinde soz
  // hakki yoktur.
  //
  // LOKAL KURULUM: kopru kavrami yok (`kopruGcsdualDurumu()` null doner),
  // karar program ayarina kalir — v2.4.45 davranisi birebir korunur.
  const kd = (typeof window.kopruGcsdualDurumu === "function")
    ? window.kopruGcsdualDurumu() : null;
  const donanim = (kd === null) ? i2ArayuzAcik : kd;
  // v2.4.65: MERKEZ UYGULAMA LISANSI ust sinir olarak uygulanir.
  // Radar ile AYNI desen (program_ayar.js:lisansUstSinir): lisans
  // "satin alindi mi", kopru servisi/ayar "donanim bagli mi" sorusunu
  // yanitlar; ikisi BIRLIKTE aranir. Lisans dosyasi yoksa ust sinir
  // uygulanmaz ve v2.4.45/v2.4.56 davranisi birebir korunur.
  const izin = (typeof window.lisansUstSinir === "function")
    ? window.lisansUstSinir("gccdual") : true;
  const acik = donanim && izin;
  const g = acik ? "" : "none";
  if (oge) oge.style.display = g;
  if (ayr) ayr.style.display = g;
  // Kapatildiysa acik panel de kapanir
  if (!acik && _i2Popup) istasyon2Kapat();
}
window.istasyon2MenuGorunumGuncelle = istasyon2MenuGorunumGuncelle;

// harita.js/ayarlariUygula -> sunucudan gelen ayarlar burada uygulanir
window.istasyon2AyarSunucudan = function (a) {
  i2ArayuzAcik = (typeof a.istasyon2_arayuz === "boolean")
    ? a.istasyon2_arayuz : false;   // yazilmamis -> KAPALI
  istasyon2MenuGorunumGuncelle();
  // Program Ayarlari popup'i acikken anahtari tazele
  const cb = document.getElementById("progIst2Anahtar");
  if (cb) cb.checked = i2ArayuzAcik;
  if (typeof a.istasyon2_port === "string")
    window.progIst2PortDegeri = a.istasyon2_port;
  const pr = document.getElementById("progIst2Port");
  if (pr && typeof a.istasyon2_port === "string" &&
      document.activeElement !== pr) pr.value = a.istasyon2_port;
};

// program_ayar.js anahtari degistirince cagirir (sunucu onayi beklemeden
// menuyu tazelemek icin degil, yalniz yerel durumu okumak icin)
window.istasyon2ArayuzAcikMi = function () { return i2ArayuzAcik; };

document.addEventListener("DOMContentLoaded", istasyon2MenuGorunumGuncelle);

window.istasyon2Ac = istasyon2Ac;
window.istasyon2Kapat = istasyon2Kapat;
