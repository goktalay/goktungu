// =====================================================================
// UCUS_RAPOR.JS - ANTETLI UCUS RAPORU (v2.4.41)
// ---------------------------------------------------------------------
// Dron History panelindeki "RAPOR OLARAK INDIR" dugmesi buraya baglanir.
//
// Neden tarayici yazdirma motoru (window.print) kullaniliyor:
//   - Turkce karakterler (s, g, I, o, u, c) hicbir font gomme islemi
//     gerektirmeden dogru cikar. Sunucuda saf Python PDF uretmek icin
//     TTF gomme + Identity-H sart olurdu; kullanicinin Windows
//     kurulumunda gomulebilir font garantisi yok.
//   - Yeni Python bagimliligi eklenmez (requirements.txt'de PDF
//     kutuphanesi YOK; kullanici pip install yapmak zorunda kalmaz).
//   - Sirket logosu ayarlarda zaten data: URI; ek kodlama gerekmez.
//   - Cikti imzalanacagi icin kullanici zaten yazdirma diyalogundan
//     geciyor; ayni diyalogda "PDF olarak kaydet" hazir.
//   - Sunucuda dosya birikmez, tahmin edilebilir indirme URL'i olusmaz.
//
// Rapor icerigi:
//   1. Antet: sirket logosu + unvan + adres/telefon/eposta/web/vergi no
//   2. Ucus kimlik tablosu (dron, UID, sysid, otopilot, pilot)
//   3. Ucus ozeti (tarih, takeoff/land saati, sure, mesafe, irtifa, hiz)
//   4. Saat saat zaman cizelgesi (her saat dilimi icin ozet satir)
//   5. AI tespitleri (varsa)
//   6. Imza bloklari: PILOT + SAHA SORUMLUSU (ad / tarih / imza)
// =====================================================================
"use strict";

// ---------------------------------------------------------------
// Yardimcilar
// ---------------------------------------------------------------
function urKacis(s) {
  return String(s === null || s === undefined ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function urSure(sn) {
  sn = Math.round(sn || 0);
  const s = sn % 60, dk = Math.floor(sn / 60) % 60, sa = Math.floor(sn / 3600);
  if (sa > 0) {
    return sa + ":" + String(dk).padStart(2, "0") +
           ":" + String(s).padStart(2, "0");
  }
  return dk + ":" + String(s).padStart(2, "0");
}

function urSaat(d) {
  if (!d) return "--";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit",
                                    second: "2-digit" });
}

// Iki nokta arasi yatay mesafe (haversine, metre)
function urMesafe(a, b) {
  const R = 6371000, RAD = Math.PI / 180;
  const dLat = (b[1] - a[1]) * RAD, dLon = (b[2] - a[2]) * RAD;
  const h = Math.sin(dLat / 2) ** 2 +
            Math.cos(a[1] * RAD) * Math.cos(b[1] * RAD) *
            Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

// ---------------------------------------------------------------
// Ucus istatistikleri
// Nokta formati (v2.4.41):
//   [t_rel(sn), lat, lon, alt_rel(m), hiz(m/s), yaw, bat_y(%), bat_v(V)]
// Indeks 6-7 v2.4.41'de eklendi; eski kayitlarda undefined olabilir.
// Batarya alanlari null/undefined olabilir (telemetride yoksa) —
// bu durumda rapora batarya satiri BASILMAZ, uydurulmaz.
// ---------------------------------------------------------------
function urIstatistik(ucus) {
  const n = ucus.noktalar || [];
  let mesafe = 0, maxIrtifa = 0, maxHiz = 0, hizToplam = 0;
  let batBas = null, batSon = null, batMin = null;
  let batVBas = null, batVSon = null, batVMin = null;
  for (let i = 0; i < n.length; i++) {
    if (i > 0) mesafe += urMesafe(n[i - 1], n[i]);
    if (n[i][3] > maxIrtifa) maxIrtifa = n[i][3];
    const h = n[i][4] || 0;
    if (h > maxHiz) maxHiz = h;
    hizToplam += h;

    // Batarya yuzdesi (indeks 6)
    const by = n[i][6];
    if (by !== null && by !== undefined && isFinite(by)) {
      if (batBas === null) batBas = by;
      batSon = by;
      if (batMin === null || by < batMin) batMin = by;
    }
    // Batarya voltaji (indeks 7)
    const bv = n[i][7];
    if (bv !== null && bv !== undefined && isFinite(bv) && bv > 0) {
      if (batVBas === null) batVBas = bv;
      batVSon = bv;
      if (batVMin === null || bv < batVMin) batVMin = bv;
    }
  }
  const sureSn = n.length ? n[n.length - 1][0] : (ucus.sure || 0);
  // Ortalama hiz: yol/zaman tercih edilir; zaman yoksa ornek ortalamasi.
  // Gerekce: telemetri ornekleme araligi duzensiz oldugunda ornek
  // ortalamasi duraklamalari yok sayar ve gercek disi yuksek cikar.
  const ortHiz = sureSn > 0 ? mesafe / sureSn
                            : (n.length ? hizToplam / n.length : 0);
  return { mesafe, maxIrtifa, maxHiz, ortHiz, sureSn, adet: n.length,
           batBas, batSon, batMin, batVBas, batVSon, batVMin };
}

// ---------------------------------------------------------------
// v2.4.42: Arac turu (MAV_TYPE -> insan okunur sinif)
//
// Neden burada: `dronlar.arac_sinifi` kolonu bir BAGLANTI ETIKETIDIR
// ("KAMIKAZE", "DJI", "BILINMEYEN"); MAV_TYPE'tan turetilmez. Rapor
// onu arac turu sanip basiyordu ve cogu dronda "BILINMEYEN" ciktisi
// veriyordu. Gercek sinif `arac_tipi` (MAV_TYPE) sayisindadir.
//
// Esleme js/dronlar.js -> dkAracTipiBilgi() ile BIREBIR AYNI tutulur;
// aksi halde kalkis kontrol listesi "multirotor" diye sorup rapor
// "sabit kanat" yazabilir ve imzali belge kendi denetim iziyle celisir.
// ---------------------------------------------------------------
function urAracTuru(ucus, dron, t) {
  let mt = null;
  if (dron && dron.arac_tipi !== null && dron.arac_tipi !== undefined)
    mt = Number(dron.arac_tipi);
  else if (ucus && ucus.arac_tipi !== null && ucus.arac_tipi !== undefined)
    mt = Number(ucus.arac_tipi);
  if (mt === null || isNaN(mt)) return "";
  if (mt === 1) return t.fsPlane || "Sabit Kanat";
  if (mt === 4) return t.fsHeli || "Helikopter";
  if ([19, 20, 21, 22, 23, 24, 25].includes(mt)) return "VTOL";
  // MAV_TYPE 0 (GENERIC) tek basina multikopter kaniti degildir:
  // kayit henuz HEARTBEAT'ten tip almamis olabilir. Uydurmak yerine
  // satiri hic yazmayiz.
  if (mt === 0) return "";
  return t.fsKopter || "Multikopter";
}

// ---------------------------------------------------------------
// Saat saat zaman cizelgesi
// Ucus baslangicindan itibaren SAAT DILIMLERINE bolunur (00:00-00:59,
// 01:00-01:59 ...). Her dilim icin o dilimde ucusan mesafe, maks irtifa,
// maks hiz ve ornek sayisi hesaplanir.
//
// Not: Cogu ucus 1 saatten kisadir; o durumda tek satir cikar ve
// cizelge yine anlamlidir (dilim = tum ucus). Kullanicinin "saat saat
// rapor olussun" istegi uzun/coklu batarya operasyonlari icin;
// dilimleme gercek saat sinirlarina (duvar saati) gore yapilir ki
// pilot kendi kaydiyla eslestirebilsin.
// ---------------------------------------------------------------
function urZamanCizelge(ucus) {
  const n = ucus.noktalar || [];
  if (n.length < 2 || !ucus.baslangic) return [];
  const bas = ucus.baslangic;
  const dilimler = new Map();

  for (let i = 0; i < n.length; i++) {
    const mutlak = new Date((bas + n[i][0]) * 1000);
    // Duvar saati dilim anahtari: YYYY-MM-DD HH
    const anahtar = mutlak.getFullYear() + "-" +
      String(mutlak.getMonth() + 1).padStart(2, "0") + "-" +
      String(mutlak.getDate()).padStart(2, "0") + " " +
      String(mutlak.getHours()).padStart(2, "0");
    let d = dilimler.get(anahtar);
    if (!d) {
      d = { anahtar, ilk: mutlak, son: mutlak, mesafe: 0,
            maxIrtifa: 0, maxHiz: 0, adet: 0, batSon: null };
      dilimler.set(anahtar, d);
    }
    d.son = mutlak;
    d.adet++;
    if (n[i][3] > d.maxIrtifa) d.maxIrtifa = n[i][3];
    const h = n[i][4] || 0;
    if (h > d.maxHiz) d.maxHiz = h;
    // Dilim sonundaki batarya yuzdesi (o saat biterken kalan sarj)
    const by = n[i][6];
    if (by !== null && by !== undefined && isFinite(by)) d.batSon = by;
    // Mesafe: onceki nokta AYNI dilimdeyse eklenir; dilim sinirini
    // asan parca bir sonraki dilime yazilmaz (cifte sayimi onler).
    if (i > 0) {
      const oncekiMutlak = new Date((bas + n[i - 1][0]) * 1000);
      const oncekiAnahtar = oncekiMutlak.getFullYear() + "-" +
        String(oncekiMutlak.getMonth() + 1).padStart(2, "0") + "-" +
        String(oncekiMutlak.getDate()).padStart(2, "0") + " " +
        String(oncekiMutlak.getHours()).padStart(2, "0");
      if (oncekiAnahtar === anahtar) d.mesafe += urMesafe(n[i - 1], n[i]);
    }
  }
  return Array.from(dilimler.values());
}

// ---------------------------------------------------------------
// HTML uretimi
// ---------------------------------------------------------------
function urMesafeYaz(m) {
  return m >= 1000 ? (m / 1000).toFixed(2) + " km" : Math.round(m) + " m";
}

function urAntet(sirket, t) {
  const logo = (sirket && sirket.logo_var && sirket.logo_url)
    ? "<img class='ur-logo' src='" + urKacis(sirket.logo_url) + "' alt=''>"
    : "";
  const satirlar = [];
  if (sirket && sirket.adres) satirlar.push(urKacis(sirket.adres));
  const iletisim = [];
  if (sirket && sirket.telefon) {
    iletisim.push((t.urTel || "Tel") + ": " + urKacis(sirket.telefon));
  }
  if (sirket && sirket.eposta) iletisim.push(urKacis(sirket.eposta));
  if (sirket && sirket.web) iletisim.push(urKacis(sirket.web));
  if (iletisim.length) satirlar.push(iletisim.join(" \u00b7 "));
  if (sirket && sirket.vergi_no) {
    satirlar.push((t.urVergiNo || "Vergi/Sicil No") + ": " +
                  urKacis(sirket.vergi_no));
  }
  return "<div class='ur-antet'>" + logo +
    "<div class='ur-antet-metin'>" +
      "<div class='ur-unvan'>" +
        urKacis((sirket && sirket.unvan) || "") + "</div>" +
      satirlar.map(s => "<div class='ur-antet-satir'>" + s + "</div>").join("") +
    "</div></div>";
}

function urTabloSatir(etiket, deger) {
  return "<tr><th>" + urKacis(etiket) + "</th><td>" +
         urKacis(deger) + "</td></tr>";
}

// ---------------------------------------------------------------
// v2.4.42: UCUS KODU + QR blogu (antetin sag ucu)
//
// Kullanici istegi: "tum history icin benzersiz bir UID gelistir ama
// kisa olsun, bu sayede o id ile raporlari birlestirebilelim" ve
// "tum raporlara bu kodu qr ile koy".
//
// Kod METNI QR'in yaninda ZORUNLU olarak basilir. Gerekce: imzali
// belge fotokopilenir/fakslanir/taranir; QR bozulursa belge yine
// eslestirilebilir kalmalidir. Ayrica pilot kodu telefonda okutmadan
// gozle de karsilastirabilir.
//
// QR icerigi DUZ KOD metnidir (URL degil). Saha kurulumu internetsiz
// oldugu icin bir URL'e gomulen kod okutuldugunda bos sayfa acardi;
// duz kod ise GOKTUNGU arama alanina dogrudan yapistirilabilir.
// ---------------------------------------------------------------
function urKodBlok(ucus, t) {
  const kod = (typeof window.ucusKodu === "function")
    ? window.ucusKodu(ucus) : "";
  if (!kod) return "";
  let qr = "";
  if (typeof window.qrSvg === "function") {
    try {
      qr = window.qrSvg(kod, 74, 2);
    } catch (e) {
      // QR uretilemezse belge kod metniyle basilmaya devam eder;
      // rapor uretimi QR yuzunden IPTAL EDILMEZ.
      qr = "";
    }
  }
  return "<div class='ur-kod-blok'>" +
    (qr ? "<div class='ur-qr'>" + qr + "</div>" : "") +
    "<div class='ur-kod-metin'>" +
      "<div class='ur-kod-bas'>" +
        urKacis(t.ugKod || "U\u00c7U\u015e KODU") + "</div>" +
      "<div class='ur-kod-deger'>" + urKacis(kod) + "</div>" +
    "</div></div>";
}

// Batarya satirlari: YALNIZCA telemetride gercek veri varsa basilir.
// Veri yoksa hic satir dondurmez (bos/uydurma deger yazilmaz).
// Coklu batarya (batarya degisimli) operasyonlarda kalkis/inis yuzdesi
// ile en dusuk yuzde, imzali raporun operasyonel cekirdegidir.
function urBataryaSatirlari(ist, t) {
  let cikti = "";
  if (ist.batBas !== null && ist.batBas !== undefined) {
    cikti += urTabloSatir(t.urBatKalkis || "Batarya (kalk\u0131\u015f)",
                          ist.batBas + " %");
    cikti += urTabloSatir(t.urBatInis || "Batarya (ini\u015f)",
                          ist.batSon + " %");
    if (ist.batMin !== null && ist.batMin !== ist.batSon) {
      cikti += urTabloSatir(t.urBatMin || "Batarya (en d\u00fc\u015f\u00fck)",
                            ist.batMin + " %");
    }
  }
  if (ist.batVBas !== null && ist.batVBas !== undefined) {
    cikti += urTabloSatir(t.urBatVolt || "Batarya voltaj\u0131",
                          ist.batVBas.toFixed(2) + " V \u2192 " +
                          ist.batVSon.toFixed(2) + " V" +
                          (ist.batVMin !== null &&
                           ist.batVMin < ist.batVSon
                            ? " (min " + ist.batVMin.toFixed(2) + " V)"
                            : ""));
  }
  return cikti;
}

// ---------------------------------------------------------------
// Kalkis kontrol listesi bolumu (denetim izi)
// Pilotun kalkis oncesi hangi soruya ne cevap verdigini, kim ve ne
// zaman onayladigini basar. Imzali raporun hukuki cekirdegi budur.
// Bir ucusta birden fazla kalkis kaydi olabilir (batarya degisimi,
// tekrar kalkis) -> her biri ayri tablo olarak basilir.
// ---------------------------------------------------------------
function urKalkisBolum(kayitlar, t) {
  if (!kayitlar || !kayitlar.length) return "";
  let cikti = "<h2>" +
    urKacis(t.urKalkisBaslik || "KALKI\u015e \u00d6NCES\u0130 KONTROL L\u0130STES\u0130") +
    "</h2>";

  for (const kk of kayitlar) {
    const zaman = kk.ts ? new Date(kk.ts * 1000) : null;
    const onayli = String(kk.sonuc || "") === "onay";
    // Ust bilgi: kim, ne zaman, sonuc
    cikti += "<table class='ur-tablo ur-kk-ust'><tr>" +
      "<th>" + urKacis(t.urKalkisPilot || "Onaylayan pilot") + "</th>" +
      "<td>" + urKacis(kk.pilot_ad || kk.pilot_eposta || "--") + "</td>" +
      "<th>" + urKacis(t.urKalkisZaman || "Onay zaman\u0131") + "</th>" +
      "<td>" + urKacis(zaman ? zaman.toLocaleString() : "--") + "</td>" +
      "<th>" + urKacis(t.urKalkisSonuc || "Sonu\u00e7") + "</th>" +
      "<td>" + urKacis(onayli
        ? (t.urKalkisOnay || "ONAYLANDI")
        : (t.urKalkisIptal || "TAMAMLANMADI")) + "</td>" +
    "</tr></table>";

    const maddeler = kk.maddeler || [];
    if (!maddeler.length) continue;
    cikti += "<table class='ur-tablo ur-genis ur-kk'><thead><tr>" +
      "<th>#</th>" +
      "<th>" + urKacis(t.urKalkisSoru || "Kontrol maddesi") + "</th>" +
      "<th>" + urKacis(t.urKalkisGrup || "Grup") + "</th>" +
      "<th>" + urKacis(t.urKalkisCevap || "Cevap") + "</th>" +
    "</tr></thead><tbody>";
    for (const m of maddeler) {
      // Cevap sutunu: EVET / HAYIR. Cevaplanmamis madde "--" basilir.
      let cevapYazi = "--", sinif = "";
      if (m.cevap === 1 || m.cevap === true || m.cevap === "1") {
        cevapYazi = t.urEvet || "EVET"; sinif = " class='ur-evet'";
      } else if (m.cevap === 0 || m.cevap === false || m.cevap === "0") {
        cevapYazi = t.urHayir || "HAYIR"; sinif = " class='ur-hayir'";
      }
      cikti += "<tr>" +
        "<td>" + urKacis(m.sira !== undefined ? m.sira : "") + "</td>" +
        "<td class='ur-sol'>" + urKacis(m.soru || m.anahtar || "") + "</td>" +
        "<td>" + urKacis(m.grup || "--") + "</td>" +
        "<td" + sinif + ">" + urKacis(cevapYazi) + "</td>" +
      "</tr>";
    }
    cikti += "</tbody></table>";
  }
  return cikti;
}

function urRaporHtml(ucus, dron, tespitler, sirket, t, kalkisKayitlari) {
  const ist = urIstatistik(ucus);
  const bas = ucus.baslangic ? new Date(ucus.baslangic * 1000) : null;
  const bit = ucus.bitis ? new Date(ucus.bitis * 1000)
    : (bas ? new Date((ucus.baslangic + ist.sureSn) * 1000) : null);

  // Pilot: sunucudan gelen telemetri kaydindan (istemci uydurmaz)
  // v2.4.42: Once ad soyad (pilotlar_ad), yoksa e-posta. Resmi/imzali
  // belgede pilot satirina e-posta yazmak kabul edilemez; sunucu ad
  // soyadi telemetri.pilot_isim -> kullanicilar.ad_soyad sirasiyla
  // cozumler, hicbiri yoksa son care olarak e-posta doner.
  const pilotlar = (ucus.pilotlar || []).filter(Boolean);
  const pilotAdlar = (ucus.pilotlar_ad || []).filter(Boolean);
  const pilotKaynak = pilotAdlar.length ? pilotAdlar : pilotlar;
  const pilotAd = pilotKaynak.length ? pilotKaynak.join(", ")
                                     : (t.urPilotBilinmiyor || "--");

  const dronAd = (dron && dron.isim) || ucus.isim ||
                 ("DRON " + (ucus.sysid !== null && ucus.sysid !== undefined
                             ? ucus.sysid : "?"));

  // 1) Ucus kimlik tablosu
  let kimlik = "<table class='ur-tablo'>" +
    urTabloSatir(t.urDron || "Hava arac\u0131", dronAd) +
    urTabloSatir("UID", (dron && dron.uid) || ucus.anahtar || "--") +
    urTabloSatir("SYSID", (ucus.sysid === null || ucus.sysid === undefined)
                 ? "--" : ucus.sysid);
  // v2.4.42: Arac turu MAV_TYPE'tan turetilir. `arac_sinifi` bir
  // BAGLANTI ETIKETIDIR (KAMIKAZE / DJI / BILINMEYEN) ve arac turu
  // yerine kullanilamaz — "BILINMEYEN" yazmasinin nedeni buydu.
  // Ayni eslemeyi kalkis kontrol listesi de kullanir; boylece rapor
  // ile kontrol listesi arasinda celiski olusmaz.
  const aracTuru = urAracTuru(ucus, dron, t);
  if (aracTuru) {
    kimlik += urTabloSatir(t.urAracSinifi || "Araç türü", aracTuru);
  }
  // Baglanti etiketi anlamli ise ayri satirda ek bilgi olarak kalir.
  const etiket = String((dron && dron.arac_sinifi) ||
                        ucus.arac_sinifi || "").trim();
  if (etiket && etiket.toUpperCase() !== "BILINMEYEN") {
    kimlik += urTabloSatir(t.urAracEtiket || "Platform etiketi", etiket);
  }
  if (dron && dron.otopilot) {
    kimlik += urTabloSatir(t.urOtopilot || "Otopilot", dron.otopilot);
  }
  if (dron && dron.firmware) {
    kimlik += urTabloSatir(t.urFirmware || "Yaz\u0131l\u0131m", dron.firmware);
  }
  kimlik += urTabloSatir(t.urPilot || "Pilot", pilotAd);
  // v2.4.42: Kisa ucus kodu kimlik tablosunda da yer alir. Antetteki
  // QR blogu gorsel; tablo satiri ise metin secilebilir/kopyalanabilir
  // kilar (PDF'ten kod kopyalayarak arama yapilabilsin).
  {
    const ucusKod = (typeof window.ucusKodu === "function")
      ? window.ucusKodu(ucus) : "";
    if (ucusKod) {
      kimlik += urTabloSatir(t.ugKod || "U\u00c7U\u015e KODU", ucusKod);
    }
  }
  kimlik += "</table>";

  // 2) Ucus ozeti
  const ozet = "<table class='ur-tablo'>" +
    urTabloSatir(t.urTarih || "U\u00e7u\u015f tarihi",
                 bas ? bas.toLocaleDateString() : "--") +
    urTabloSatir(t.urTakeoff || "Kalk\u0131\u015f saati", urSaat(bas)) +
    urTabloSatir(t.urLand || "\u0130ni\u015f saati", urSaat(bit)) +
    urTabloSatir(t.urSure || "U\u00e7u\u015f s\u00fcresi", urSure(ist.sureSn)) +
    urTabloSatir(t.urMesafe || "Kat edilen mesafe", urMesafeYaz(ist.mesafe)) +
    urTabloSatir(t.urMaxIrtifa || "Maksimum irtifa",
                 Math.round(ist.maxIrtifa) + " m") +
    urTabloSatir(t.urOrtHiz || "Ortalama h\u0131z",
                 ist.ortHiz.toFixed(1) + " m/s (" +
                 (ist.ortHiz * 3.6).toFixed(1) + " km/h)") +
    urTabloSatir(t.urMaxHiz || "Maksimum h\u0131z",
                 ist.maxHiz.toFixed(1) + " m/s (" +
                 (ist.maxHiz * 3.6).toFixed(1) + " km/h)") +
    urTabloSatir(t.urOrnek || "Telemetri \u00f6rne\u011fi", ist.adet) +
    urBataryaSatirlari(ist, t) +
    "</table>";

  // 3) Saat saat zaman cizelgesi
  const dilimler = urZamanCizelge(ucus);
  // Batarya kolonu yalnizca GERCEK veri varsa basilir (uydurma yok).
  const bataryaVar = dilimler.some(d => d.batSon !== null);
  let cizelge = "";
  if (dilimler.length) {
    cizelge =
      "<h2>" + urKacis(t.urCizelge || "SAAT SAAT U\u00c7U\u015e \u00d6ZET\u0130") + "</h2>" +
      "<table class='ur-tablo ur-genis'><thead><tr>" +
        "<th>" + urKacis(t.urDilim || "Saat aral\u0131\u011f\u0131") + "</th>" +
        "<th>" + urKacis(t.urDilimSure || "S\u00fcre") + "</th>" +
        "<th>" + urKacis(t.urMesafe || "Mesafe") + "</th>" +
        "<th>" + urKacis(t.urMaxIrtifa || "Maks irtifa") + "</th>" +
        "<th>" + urKacis(t.urMaxHiz || "Maks h\u0131z") + "</th>" +
        (bataryaVar ? "<th>" + urKacis(t.urBatSonu || "Batarya") +
                      "</th>" : "") +
        "<th>" + urKacis(t.urOrnek || "\u00d6rnek") + "</th>" +
      "</tr></thead><tbody>";
    for (const d of dilimler) {
      const sureSn = Math.max(0, (d.son - d.ilk) / 1000);
      cizelge += "<tr>" +
        "<td>" + urKacis(urSaat(d.ilk) + " \u2013 " + urSaat(d.son)) + "</td>" +
        "<td>" + urKacis(urSure(sureSn)) + "</td>" +
        "<td>" + urKacis(urMesafeYaz(d.mesafe)) + "</td>" +
        "<td>" + Math.round(d.maxIrtifa) + " m</td>" +
        "<td>" + d.maxHiz.toFixed(1) + " m/s</td>" +
        (bataryaVar
          ? "<td>" + (d.batSon === null ? "--" : d.batSon + " %") + "</td>"
          : "") +
        "<td>" + d.adet + "</td>" +
      "</tr>";
    }
    cizelge += "</tbody></table>";
  }

  // 4) AI tespitleri (varsa)
  let tespitBolum = "";
  const tl = (tespitler || []).filter(Boolean);
  if (tl.length) {
    tespitBolum =
      "<h2>" + urKacis(t.urTespitler || "AI TESP\u0130TLER\u0130") +
      " (" + tl.length + ")</h2>" +
      "<table class='ur-tablo ur-genis'><thead><tr>" +
        "<th>" + urKacis(t.urTespitSaat || "Saat") + "</th>" +
        "<th>" + urKacis(t.urTespitTur || "T\u00fcr") + "</th>" +
        "<th>" + urKacis(t.urTespitAd || "Tan\u0131m") + "</th>" +
        "<th>" + urKacis(t.urTespitSeviye || "Seviye") + "</th>" +
      "</tr></thead><tbody>";
    for (const tp of tl) {
      const zaman = tp.ts ? new Date(tp.ts * 1000) : null;
      const ad = tp.kisi_ad || tp.arac_plaka || tp.etiket || "--";
      const tur = (typeof window.aiTurAdi === "function")
        ? window.aiTurAdi(tp.tur) : (tp.tur || "--");
      tespitBolum += "<tr>" +
        "<td>" + urKacis(urSaat(zaman)) + "</td>" +
        "<td>" + urKacis(tur) + "</td>" +
        "<td>" + urKacis(ad) + "</td>" +
        "<td>" + urKacis(tp.seviye || "--") + "</td>" +
      "</tr>";
    }
    tespitBolum += "</tbody></table>";
  }

  // 5) Imza bloklari
  const imzaKutu = (rolAd, adDeger) =>
    "<div class='ur-imza'>" +
      "<div class='ur-imza-rol'>" + urKacis(rolAd) + "</div>" +
      "<div class='ur-imza-alan'><span>" +
        urKacis(t.urAdSoyad || "Ad Soyad") + "</span><b>" +
        urKacis(adDeger || "") + "</b></div>" +
      "<div class='ur-imza-alan'><span>" +
        urKacis(t.urTarihAlan || "Tarih") + "</span><b></b></div>" +
      "<div class='ur-imza-alan ur-imza-cizgi'><span>" +
        urKacis(t.urImza || "\u0130mza") + "</span><b></b></div>" +
    "</div>";

  const imzalar = "<div class='ur-imza-satir'>" +
    imzaKutu(t.urPilotRol || "PILOT", pilotlar.length ? pilotAd : "") +
    imzaKutu(t.urSahaRol || "SAHA SORUMLUSU", "") +
  "</div>";

  const uretim = new Date();
  const altbilgi = "<div class='ur-altbilgi'>" +
    urKacis((t.urUretim || "Rapor olu\u015fturma") + ": " +
            uretim.toLocaleString()) +
    " \u00b7 " + urKacis((t.ugKod || "U\u00c7U\u015e KODU") + ": " +
      ((typeof window.ucusKodu === "function")
        ? (window.ucusKodu(ucus) || "--") : "--")) +
    " \u00b7 " + urKacis((t.urKayitNo || "Kay\u0131t no") + ": " +
                        (ucus.id || "--")) +
    " \u00b7 G\u00d6KTUNGU GCS v" +
    urKacis(typeof GCS_SURUM !== "undefined" ? GCS_SURUM : "") +
  "</div>";

  // v2.4.42: Antet ile QR blogu AYNI SATIRDA; antet sola, kod saga
  // yerlesir. Boylece kod belgenin ilk bakista gorulen kismindadir
  // (dosyalama sirasinda ust kenardan okunabilir).
  return "<div class='ur-ust-satir'>" + urAntet(sirket, t) +
      urKodBlok(ucus, t) + "</div>" +
    "<h1>" + urKacis(t.urBaslik || "U\u00c7U\u015e RAPORU") + "</h1>" +
    "<div class='ur-iki'>" +
      "<div><h2>" + urKacis(t.urKimlik || "HAVA ARACI VE PERSONEL") +
        "</h2>" + kimlik + "</div>" +
      "<div><h2>" + urKacis(t.urOzet || "U\u00c7U\u015e \u00d6ZET\u0130") +
        "</h2>" + ozet + "</div>" +
    "</div>" +
    cizelge + tespitBolum +
    urKalkisBolum(kalkisKayitlari, t) +
    "<h2 class='ur-onay-bas'>" +
      urKacis(t.urOnay || "ONAY") + "</h2>" +
    "<div class='ur-beyan'>" +
      urKacis(t.urBeyan ||
        "Yukar\u0131da bilgileri verilen u\u00e7u\u015f, kay\u0131t alt\u0131na " +
        "al\u0131nan telemetri verilerine uygun olarak " +
        "ger\u00e7ekle\u015ftirilmi\u015ftir.") +
    "</div>" +
    imzalar + altbilgi;
}

// ---------------------------------------------------------------
// Yazdirma penceresi
// ---------------------------------------------------------------
function urStil() {
  return "" +
  "@page { size: A4; margin: 14mm 14mm 12mm 14mm; }" +
  "* { box-sizing: border-box; }" +
  "body { font-family: 'Segoe UI', Arial, Helvetica, sans-serif;" +
  "       color: #111; font-size: 10.5pt; margin: 0; }" +
  // v2.4.42: antet (sol) + ucus kodu/QR (sag) ayni satirda.
  // Alt cizgi artik ANTET'te degil bu kapsayicida; aksi halde QR
  // blogu cizginin altinda kalirdi.
  ".ur-ust-satir { display: flex; align-items: flex-start; gap: 14px;" +
  "       border-bottom: 2px solid #111; padding-bottom: 8px; }" +
  ".ur-antet { display: flex; align-items: center; gap: 12px;" +
  "            flex: 1 1 auto; min-width: 0; }" +
  ".ur-kod-blok { display: flex; align-items: center; gap: 8px;" +
  "       flex: 0 0 auto; border: 1px solid #999; padding: 5px 8px; }" +
  ".ur-qr svg { display: block; }" +
  ".ur-kod-bas { font-size: 7pt; color: #555; letter-spacing: .8px; }" +
  ".ur-kod-deger { font-family: Consolas, 'Courier New', monospace;" +
  "       font-size: 13pt; font-weight: 700; letter-spacing: 1px; }" +
  ".ur-logo { height: 62px; width: auto; max-width: 150px;" +
  "           object-fit: contain; }" +
  ".ur-unvan { font-size: 15pt; font-weight: 700; letter-spacing: .2px; }" +
  ".ur-antet-satir { font-size: 8.8pt; color: #333; margin-top: 1px; }" +
  "h1 { font-size: 13pt; text-align: center; margin: 14px 0 12px;" +
  "     letter-spacing: 1.5px; }" +
  "h2 { font-size: 9.5pt; margin: 12px 0 5px; letter-spacing: .8px;" +
  "     border-bottom: 1px solid #999; padding-bottom: 2px; }" +
  ".ur-iki { display: flex; gap: 14px; align-items: flex-start; }" +
  ".ur-iki > div { flex: 1 1 0; min-width: 0; }" +
  ".ur-tablo { width: 100%; border-collapse: collapse; }" +
  ".ur-tablo th, .ur-tablo td { border: 1px solid #bbb; padding: 3px 6px;" +
  "     text-align: left; vertical-align: top; font-size: 9pt; }" +
  ".ur-tablo th { background: #f0f0f0; font-weight: 600; width: 42%; }" +
  ".ur-genis thead th { width: auto; text-align: center; }" +
  ".ur-genis td { text-align: center; }" +
  ".ur-genis td:first-child { text-align: left; white-space: nowrap; }" +
  ".ur-sol { text-align: left !important; }" +
  ".ur-kk-ust th { width: auto; white-space: nowrap; }" +
  ".ur-kk td:first-child { text-align: center; width: 26px; }" +
  ".ur-kk td:last-child { font-weight: 700; white-space: nowrap;" +
  "     width: 62px; }" +
  ".ur-evet { color: #14663a; }" +
  ".ur-hayir { color: #a11414; }" +
  ".ur-beyan { font-size: 9pt; margin: 6px 0 14px; }" +
  ".ur-onay-bas { margin-top: 16px; }" +
  ".ur-imza-satir { display: flex; gap: 18px; }" +
  ".ur-imza { flex: 1 1 0; border: 1px solid #999; padding: 8px 10px 10px; }" +
  ".ur-imza-rol { font-size: 9pt; font-weight: 700; letter-spacing: .6px;" +
  "     border-bottom: 1px solid #ccc; padding-bottom: 4px;" +
  "     margin-bottom: 8px; }" +
  ".ur-imza-alan { display: flex; gap: 6px; font-size: 9pt;" +
  "     margin-top: 10px; align-items: flex-end; }" +
  ".ur-imza-alan span { color: #555; min-width: 58px; }" +
  ".ur-imza-alan b { flex: 1 1 auto; border-bottom: 1px dotted #777;" +
  "     min-height: 15px; font-weight: 500; }" +
  ".ur-imza-cizgi b { min-height: 34px; border-bottom: 1px solid #333; }" +
  ".ur-altbilgi { margin-top: 14px; padding-top: 5px;" +
  "     border-top: 1px solid #ccc; font-size: 7.8pt; color: #555;" +
  "     text-align: center; }" +
  "table { page-break-inside: auto; }" +
  "tr { page-break-inside: avoid; page-break-after: auto; }" +
  ".ur-imza-satir { page-break-inside: avoid; }";
}

// Disa acik: History panelinden cagrilir
window.ucusRaporAc = function (ucus, dron, tespitler, kalkisKayitlari) {
  const t = (typeof D === "function") ? D() : {};
  if (!ucus || !ucus.noktalar || ucus.noktalar.length < 2) return;

  // Sirket bilgisi ZORUNLU: antet olmadan resmi belge uretilmez.
  const sirket = (typeof window.sirketBilgi === "function")
    ? window.sirketBilgi() : null;
  // v2.4.64 DUZELTME: uyariToastGoster TEK nesne alir
  // ({seviye, kategori, mesaj}) - uyari_merkezi.js:65. Uc ayri dize
  // gonderildiginde `uyari.mesaj` undefined kalir ve BOS bildirim cikar;
  // kullanici raporun neden uretilmedigini ogrenemez.
  if (!sirket || !sirket.unvan) {
    if (typeof window.uyariToastGoster === "function") {
      window.uyariToastGoster({
        seviye: "hata",
        kategori: t.gcRaporHataBaslik || "RAPOR OLU\u015eTURULAMADI",
        mesaj: t.gcRaporSirketYok ||
               "\u015eirket bilgileri tan\u0131ml\u0131 de\u011fil.",
      });
    }
    return;
  }

  const govde = urRaporHtml(ucus, dron, tespitler, sirket, t,
                            kalkisKayitlari || []);
  const baslik = (t.urBaslik || "U\u00c7U\u015e RAPORU") + " - " +
                 ((dron && dron.isim) || ucus.isim || "");

  // Gizli iframe: ayni sekmede kalir, pop-up engelleyiciye takilmaz.
  // Yeni pencere (window.open) tarayici ayarlarina gore bloklanabilir;
  // iframe her durumda calisir.
  const eski = document.getElementById("ucusRaporCerceve");
  if (eski) eski.remove();
  const cerceve = document.createElement("iframe");
  cerceve.id = "ucusRaporCerceve";
  cerceve.style.cssText =
    "position:fixed;left:-10000px;top:0;width:794px;height:1123px;" +
    "border:0;visibility:hidden;";
  document.body.appendChild(cerceve);

  const belge = cerceve.contentDocument || cerceve.contentWindow.document;
  belge.open();
  belge.write(
    "<!DOCTYPE html><html lang='" +
    String(typeof aktifDil !== "undefined" ? aktifDil : "TR")
      .toLowerCase() + "'><head><meta charset='utf-8'>" +
    "<title>" + urKacis(baslik) + "</title>" +
    "<style>" + urStil() + "</style></head><body>" + govde +
    "</body></html>");
  belge.close();

  // Logo gorseli yuklenmeden yazdirmak antetsiz cikti verir; onu bekle.
  const yazdir = () => {
    try {
      cerceve.contentWindow.focus();
      cerceve.contentWindow.print();
    } catch (e) {
      // v2.4.64: dogru imza (nesne)
      if (typeof window.uyariToastGoster === "function") {
        window.uyariToastGoster({
          seviye: "hata",
          kategori: t.gcRaporHataBaslik || "RAPOR OLU\u015eTURULAMADI",
          mesaj: String(e && e.message ? e.message : e),
        });
      }
    }
    // Yazdirma diyalogu kapandiktan sonra temizle. Diyalog acikken
    // iframe silinirse Chrome'da bos sayfa yazdirilir; bu yuzden
    // gecikmeli kaldiriyoruz.
    setTimeout(() => { try { cerceve.remove(); } catch (e) {} }, 60000);
  };

  const gorseller = Array.from(belge.images || []);
  const bekleyen = gorseller.filter(g => !g.complete);
  if (!bekleyen.length) { setTimeout(yazdir, 80); return; }
  let kalan = bekleyen.length;
  let bitti = false;
  const azalt = () => {
    if (bitti) return;
    kalan--;
    if (kalan <= 0) { bitti = true; setTimeout(yazdir, 60); }
  };
  for (const g of bekleyen) {
    g.addEventListener("load", azalt);
    g.addEventListener("error", azalt);
  }
  // Guvenlik agi: gorsel hic yuklenmezse yazdirma yine tetiklenir
  setTimeout(() => { if (!bitti) { bitti = true; yazdir(); } }, 3000);

  // v2.4.64: dogru imza (nesne). Onceki halde BASARI bildirimi de
  // bos cikiyordu; kullanici raporun hazir oldugunu goremiyordu.
  if (typeof window.uyariToastGoster === "function") {
    window.uyariToastGoster({
      seviye: "basari",
      kategori: t.gcRaporTamamBaslik || "RAPOR HAZIR",
      mesaj: t.gcRaporTamam ||
             "Yazd\u0131rma penceresinden PDF olarak kaydedebilirsiniz.",
    });
  }
};

// ---------------------------------------------------------------
// SINAV KANCALARI (sinav_2441.html tarafindan kullanilir)
// Uretim akisini etkilemez; yalnizca cekirdek hesap fonksiyonlarini
// tarayici sinavina acar ki "kod var mi" degil "dogru hesapliyor mu"
// olculebilsin. Sinav, alan adlarini kisa takma adlarla bekler.
// ---------------------------------------------------------------
window.urIstatistikTest = function (ucus) {
  const i = urIstatistik(ucus);
  return {
    maxIrt: i.maxIrtifa, maxHiz: i.maxHiz, sureSn: i.sureSn,
    mesafeM: i.mesafe, ortHiz: i.ortHiz, adet: i.adet,
    batBas: i.batBas, batSon: i.batSon, batMin: i.batMin,
    voltBas: i.batVBas, voltSon: i.batVSon, voltMin: i.batVMin,
  };
};
window.urZamanCizelgeTest = function (ucus) {
  return urZamanCizelge(ucus).map(d => ({
    anahtar: d.anahtar, maxIrt: d.maxIrtifa, maxHiz: d.maxHiz,
    mesafeM: d.mesafe, adet: d.adet, batSon: d.batSon,
  }));
};
window.urKalkisBolumTest = function (kayitlar, t) {
  return urKalkisBolum(kayitlar, t || {});
};
