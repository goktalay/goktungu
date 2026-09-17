// ================================================================
// KAMERALAR: sag panel KAMERALAR bolumu
//  - Kamera listesi (liste / onizleme gorunumu)
//  - Play / Stop / Duzenle / Sil
//  - RTSP/RTP -> sunucu MJPEG proxy'si uzerinden izleme
//  - MJPEG dogrudan <img>, HLS hls.js + <video>, HTTP <video>
//  - Tasinabilir ayrik video penceresi
// ================================================================
(function () {
  "use strict";

  let kameralar = [];            // sunucudan gelen kayitlar
  const oynayanlar = new Set();  // oynatilan kamera id'leri
  const ayrikler = {};           // id -> ayrik pencere DOM kaydi
  const hlsNesneleri = {};       // id -> Hls instance (temizlik icin)
  // v2.4.219 (kullanici istegi): Kameralar panelinde TEK gorunum (liste);
  // onizleme/izgara kipi ve gorunum secici kaldirildi.
  let gorunum = "liste";
  let duzenlenenId = null;       // modal duzenleme modundaki kamera id

  const listeKok = () => document.getElementById("kameraListesi");
  const T = () => (typeof D === "function" ? D() : {});

  // Offline Merkez canlı akışı, uygulamanın aynı origin'i üzerinden gelir.
  // Ayrı port veya cihaz Köprüsü gerekmez.
  function proxyUrl(id) {
    return window.location.origin + window.appYolu("/kamera/" + id) + "?t=" + Date.now();
  }
  // Dron harita önizlemesi yalnız bu same-origin vekil yolunu kullanır.
  // Uzak kaynak URL'si veya erişim bilgisi istemci modülleri arasında taşınmaz.
  window.kameraOnizlemeUrl = function (id) { return proxyUrl(Number(id)); };
  // Paylasimli AI paneli kamera kaydini bu kanaldan yollar.
  window.kameraWsGonder = function (obj) { wsGonder(obj); };
  // v2.4.222 (kullanici istegi): goruntu konumu SECENEGI KALDIRILDI —
  // oynayan kamera hem haritada (dron kucuk onizlemesi) hem yuzen pencerede.
  function hedef(id) { return "yuzen"; }

  function wsGonder(obj) {
    if (typeof ws !== "undefined" && ws && ws.readyState === 1)
      ws.send(JSON.stringify(obj));
  }

  // ----------------------------------------------------------------
  // MODAL: yeni kamera / duzenleme
  // ----------------------------------------------------------------
  const perde = document.getElementById("kamModalPerde");
  const inAd = document.getElementById("kamAd");
  const inLok = document.getElementById("kamLokasyon");
  const inDron = document.getElementById("kamDron");
  // Bu seçici mevcut dron UID alanını kullanır; yeni bir dron kimliği üretmez.
  function dronSecDoldur(secili) {
    if (!inDron) return;
    const tercih = String(secili !== undefined ? secili : inDron.value || "");
    const liste = Array.isArray(window._kayitliDronlarSon)
      ? window._kayitliDronlarSon : [];
    inDron.textContent = "";
    const bos = document.createElement("option");
    bos.value = ""; bos.textContent = "— Bağlı değil —";
    inDron.appendChild(bos);
    const gorulen = new Set();
    liste.forEach((dr) => {
      const uid = String((dr && dr.uid) || "").trim();
      if (!uid || gorulen.has(uid)) return;
      gorulen.add(uid);
      const opt = document.createElement("option");
      opt.value = uid;
      opt.textContent = String(dr.isim || ("DRON " + (dr.sysid || ""))) +
        " — " + uid.slice(0, 24);
      inDron.appendChild(opt);
    });
    // Önceden bağlı fakat geçmiş listesinde görünmeyen UID de korunur;
    // kullanıcı bilinçli olarak bağı çözene kadar veri kaybı oluşmaz.
    if (tercih && !gorulen.has(tercih)) {
      const opt = document.createElement("option");
      opt.value = tercih; opt.textContent = "Mevcut dron — " + tercih.slice(0, 24);
      inDron.appendChild(opt);
    }
    inDron.value = tercih;
  }
  window.kameraDronSeciciTazele = function () {
    if (inDron && !perde.classList.contains("popup-gizli")) dronSecDoldur();
  };
  // v2.4.0: bina/lokasyon secim listesi (lokasyonlar.js window'a yazar)
  function lokSecDoldur(secili){
    if (!inLok) return;
    const liste = window._lokasyonlarSon || [];
    inLok.innerHTML = "";
    const bos = document.createElement("option");
    bos.value = "";
    bos.textContent = ((typeof D === "function") ? (D().kamSecilmedi) : "") || "\u2014 Se\u00e7ilmedi \u2014";
    inLok.appendChild(bos);
    for (const l of liste){
      const opt = document.createElement("option");
      opt.value = String(l.id);
      opt.textContent = l.ad + (l.adres ? " \u2014 " + l.adres : "");
      inLok.appendChild(opt);
    }
    inLok.value = (secili != null) ? String(secili) : "";
  }
  const inProt = document.getElementById("kamProtokol");
  const inFps = document.getElementById("kamFps");   // v2.4.193: FPS tavani
  const inUrl = document.getElementById("kamUrl");
  const hataEl = document.getElementById("kamHata");
  const baslikEl = document.getElementById("kamModalBaslik");

  const cihazSatir = document.getElementById("kamCihazSatir");
  const cihazSec = document.getElementById("kamCihazSec");
  const lblUrlSatir = document.getElementById("lblKamUrlSatir");

  const djiSatir = document.getElementById("kamDjiSatir");
  const djiSec = document.getElementById("kamDjiSec");
  // v2.4.56: kameranin hangi KOPRU makinesine bagli oldugu secimi.
  const kopruAlan = document.getElementById("kamKopruAlan");
  const kopruSec  = document.getElementById("kamKopruSec");

  const dosyaSatir = document.getElementById("kamDosyaSatir");
  const dosyaSec = document.getElementById("kamDosyaSec");
  const dosyaBilgi = document.getElementById("kamDosyaBilgi");
  // v2.4.181: M50 kamerası — ağ/kimlik bilgisi M50 alt yapısına devredilir.
  const m50Satir = document.getElementById("kamM50Satir");
  const m50KanalSec = document.getElementById("kamM50Kanal");
  const m50IpEl = document.getElementById("kamM50Ip");
  const m50PortEl = document.getElementById("kamM50Port");
  const m50KullaniciEl = document.getElementById("kamM50Kullanici");
  const m50ParolaEl = document.getElementById("kamM50Parola");

  function protokolDegisti() {
    const prot = inProt.value;
    if (dosyaSatir) dosyaSatir.classList.toggle("gizli", prot !== "dosya");
    if (m50Satir) m50Satir.classList.toggle("gizli", prot !== "m50");
    if (prot === "donanim") {
      cihazSatir.classList.remove("gizli");
      if (djiSatir) djiSatir.classList.add("gizli");
      lblUrlSatir.classList.add("gizli");
      inUrl.classList.add("gizli");
      cihazlariListele();
    } else if (prot === "dji") {
      cihazSatir.classList.add("gizli");
      if (djiSatir) djiSatir.classList.remove("gizli");
      lblUrlSatir.classList.add("gizli");
      inUrl.classList.add("gizli");
      djiCihazlariListele();
    } else if (prot === "dosya" || prot === "m50") {
      cihazSatir.classList.add("gizli");
      if (djiSatir) djiSatir.classList.add("gizli");
      lblUrlSatir.classList.add("gizli");
      inUrl.classList.add("gizli");
    } else {
      cihazSatir.classList.add("gizli");
      if (djiSatir) djiSatir.classList.add("gizli");
      lblUrlSatir.classList.remove("gizli");
      inUrl.classList.remove("gizli");
    }
  }
  inProt.addEventListener("change", protokolDegisti);

  // v2.4.166: "dosya" protokolu — mp4 sunucuya yuklenir, url = dosya adi.
  async function videoDosyaYukle(dosya) {
    const yanit = await fetch(window.appYolu("/api/kamera/video_yukle"), {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
      headers: {
        "Content-Type": "application/octet-stream",
        "X-Dosya-Ad": encodeURIComponent(dosya.name || "video.mp4")
      },
      body: dosya
    });
    if (!yanit.ok) {
      let m = "";
      try { m = (await yanit.text()).slice(0, 200); } catch (e) {}
      throw new Error("HTTP " + yanit.status + (m ? " — " + m : ""));
    }
    const veri = await yanit.json();
    if (!veri || !veri.tamam || !veri.dosya) throw new Error("yükleme reddedildi");
    return veri.dosya;
  }

  // v2.4.7: cihazlar artik SUNUCU makinesinden listelenir (indeks
  // tabanli) — goruntu Python'da yakalanip AI boru hattina girer ve
  // anotasyonlu MJPEG olarak servis edilir. ws.js 'kamera_cihazlari'
  // mesajini window.kameraCihazlarIsle ile buraya yollar.
  function cihazlariListele() {
    const t = T();
    cihazSec.innerHTML = "<option value=''>" +
      (t.kamCihazYukleniyor || "Cihazlar sorgulan\u0131yor...") +
      "</option>";
    wsGonder({ tip: "kamera_cihazlari" });
  }

  window.kameraCihazlarIsle = function(m) {
    if (!cihazSec) return;
    const t = T();
    const cihazlar = m.cihazlar || [];
    cihazSec.innerHTML = "";
    if (!cihazlar.length) {
      cihazSec.innerHTML = "<option value=''>" +
        (t.kamCihazYok || "Sunucuda kamera bulunamad\u0131") + "</option>";
      return;
    }
    for (const c of cihazlar) {
      const opt = document.createElement("option");
      opt.value = String(c.indeks);
      opt.textContent = c.ad || ("Kamera " + c.indeks);
      cihazSec.appendChild(opt);
    }
    // duzenleme modunda kayitli indeksi sec
    if (cihazSec.dataset.secili) {
      cihazSec.value = cihazSec.dataset.secili;
      delete cihazSec.dataset.secili;
    }
  };

  // Bagli DJI dronlarini sunucudan iste; ws.js 'dji_cihazlar' mesajini
  // window.djiCihazlarIsle uzerinden buraya yollar.
  function djiCihazlariListele() {
    if (!djiSec) return;
    const t = T();
    djiSec.innerHTML = "<option value=''>" +
      (t.kamDjiYukleniyor || "DJI dronlar\u0131 sorgulan\u0131yor...") +
      "</option>";
    wsGonder({ tip: "dji_cihazlar" });
  }

  window.djiCihazlarIsle = function(m) {
    if (!djiSec) return;
    const t = T();
    const cihazlar = m.cihazlar || [];
    djiSec.innerHTML = "";
    if (!cihazlar.length) {
      djiSec.innerHTML = "<option value=''>" +
        (t.kamDjiYok || "Ba\u011fl\u0131 DJI dron yok") + "</option>";
      return;
    }
    for (const c of cihazlar) {
      const opt = document.createElement("option");
      opt.value = "dji:" + c.sysid;
      opt.textContent = c.model + " (SN:" + (c.sn || "?") + ")" +
        (c.video_url ? "" : " \u2014 " +
          (((typeof D === "function") ? (D().kamVideoYok) : "") || "video yok"));
      djiSec.appendChild(opt);
    }
  };

  // C-UAS modu: hava araci ana anahtari + alt siniflar (YOLO modeliyle).
  const AI_GOREV_KUTULARI = ["kamAiHava", "kamAiDrone", "kamAiUcak",
                             "kamAiHeli", "kamAiKus"];

  function aiGorevleriDoldur(csv) {
    const secili = String(csv || "").split(",").map(s => s.trim());
    for (const id of AI_GOREV_KUTULARI) {
      const kutu = document.getElementById(id);
      if (kutu) kutu.checked = secili.includes(kutu.value);
    }
  }

  function aiGorevleriOku() {
    const secili = [];
    for (const id of AI_GOREV_KUTULARI) {
      const kutu = document.getElementById(id);
      if (kutu && kutu.checked) secili.push(kutu.value);
    }
    return secili.join(",");
  }

  // v2.5.21: yerel AI angajman kalibrasyonu alanlari + tip gecisi.
  const KALIB_ALAN = {
    kamTipi: "kamera_tipi", kamLat: "lat", kamLon: "lon",
    kamYukseklik: "kam_yukseklik", kamYon: "yon", kamTilt: "tilt",
    kamFovY: "fov_yatay", kamFovD: "fov_dikey",
    kamMontajPan: "montaj_pan", kamMontajTilt: "montaj_tilt",
    kamMontajRoll: "montaj_roll",
  };

  function _el(id) { return document.getElementById(id); }

  function kamTipiGecisi() {
    const tip = (_el("kamTipi") || {}).value || "sabit";
    const sabit = _el("kamSabitKalib");
    const dron = _el("kamDronKalib");
    if (sabit) sabit.style.display = (tip === "sabit") ? "" : "none";
    if (dron) dron.style.display = (tip === "dron") ? "" : "none";
  }

  function kalibDoldur(kamera) {
    // Sayisal alanlari doldur (yoksa bos birak).
    const say = (v) => (v === null || v === undefined || v === "") ? "" : v;
    const eslesme = {
      kamLat: "lat", kamLon: "lon", kamYukseklik: "kam_yukseklik",
      kamYon: "yon", kamTilt: "tilt", kamFovY: "fov_yatay",
      kamFovD: "fov_dikey", kamMontajPan: "montaj_pan",
      kamMontajTilt: "montaj_tilt", kamMontajRoll: "montaj_roll",
    };
    for (const id in eslesme) {
      const el = _el(id);
      if (el) el.value = kamera ? say(kamera[eslesme[id]]) : "";
    }
    const tipEl = _el("kamTipi");
    if (tipEl) tipEl.value = (kamera && kamera.kamera_tipi) || "sabit";
    const durum = _el("kamKalibDurum");
    if (durum) {
      durum.textContent = (kamera && kamera.kalibre)
        ? "✓ Kalibre — bu kameranın AI hedefi angajmana alınabilir."
        : "Kalibrasyon eksik/yeni — tamamlanana kadar AI hedefi angajmana ALINAMAZ.";
    }
    kamTipiGecisi();
  }

  function kalibOku(k) {
    // Tip her zaman gonderilir; sayisal alanlar yalniz doluysa.
    k.kamera_tipi = (_el("kamTipi") || {}).value || "sabit";
    const eslesme = {
      kamLat: "lat", kamLon: "lon", kamYukseklik: "kam_yukseklik",
      kamYon: "yon", kamTilt: "tilt", kamFovY: "fov_yatay",
      kamFovD: "fov_dikey", kamMontajPan: "montaj_pan",
      kamMontajTilt: "montaj_tilt", kamMontajRoll: "montaj_roll",
    };
    for (const id in eslesme) {
      const el = _el(id);
      if (!el) continue;
      const ham = String(el.value || "").trim();
      k[eslesme[id]] = (ham === "") ? null : parseFloat(ham);
    }
  }

  function modalAc(kamera) {
    const t = T();
    duzenlenenId = kamera ? kamera.id : null;
    inAd.value = kamera ? kamera.isim : "";
    inProt.value = kamera ? kamera.protokol : "rtsp";
    inUrl.value = kamera ? kamera.url : "";
    if (inFps) inFps.value = String((kamera && kamera.fps) || 15);
    // v2.4.7: duzenlemede kayitli cihaz indeksi, liste gelince secilir
    if (kamera && kamera.protokol === "donanim" && cihazSec) {
      cihazSec.dataset.secili = kamera.url;
    }
    // v2.4.181: M50 kamerasi — kanal "m50:<kanal>" url'sinden okunur;
    // kimlik bilgisi ASLA geri doldurulmaz (guvenlik: sunucuda saklanmaz).
    if (m50KanalSec) {
      const kanal = (kamera && kamera.protokol === "m50" && kamera.url)
        ? String(kamera.url).split(":")[1] : "gorunur";
      m50KanalSec.value = (kanal === "termal") ? "termal" : "gorunur";
    }
    if (m50IpEl) m50IpEl.value = "";
    if (m50PortEl) m50PortEl.value = "";
    if (m50KullaniciEl) m50KullaniciEl.value = "";
    if (m50ParolaEl) m50ParolaEl.value = "";
    // v2.4.166: duzenlemede kayitli video dosyasi adi korunur/gosterilir
    if (dosyaSec) {
      dosyaSec.value = "";
      if (kamera && kamera.protokol === "dosya" && kamera.url) {
        dosyaSec.dataset.mevcut = kamera.url;
        if (dosyaBilgi) dosyaBilgi.textContent = "Kayıtlı dosya: " + kamera.url +
          " — değiştirmek için yeni dosya seçin.";
      } else {
        delete dosyaSec.dataset.mevcut;
        if (dosyaBilgi) dosyaBilgi.textContent =
          "Dosya sunucuya yüklenir ve döngüde canlı kamera gibi yayınlanır;" +
          " AI tespiti ve angajman testi için kullanılabilir.";
      }
    }
    aiGorevleriDoldur(kamera ? kamera.ai_gorevler : "");
    // v2.4.0: lokasyon listesi yoksa sunucudan iste, combobox'i doldur
    if (!window._lokasyonlarSon) wsGonder({tip: "lokasyon_liste"});
    lokSecDoldur(kamera ? kamera.lokasyon_id : null);
    // Bağ seçimi yalnız mevcut kayıtlı dron UID listesinden yapılır.
    if (!window._kayitliDronlarSon) wsGonder({tip: "dron_gecmis_liste"});
    dronSecDoldur(kamera ? kamera.dron_uid : "");
    // v2.4.56: kopru secimi. Kamera akisi (RTSP/donanim/DJI) saha
    // makinesinde vardir; merkez sunucusu o adrese erisemez. Bu yuzden
    // merkezde hangi kopru uzerinden okunacagi secilmelidir.
    if (typeof window.kopruSeciciDoldur === "function")
      window.kopruSeciciDoldur(kopruAlan, kopruSec,
                               kamera ? kamera.kopru_ornek_id : null);
    // v2.5.21: angajman kalibrasyon alanlari
    kalibDoldur(kamera);
    // v2.4.152: acilir bolumler. Genel hep acik; AI Gorevleri gorev
    // seciliyse, kalibrasyon ise kamera zaten bir tipe/kalibrasyona
    // sahipse acik gelir. Yeni kamerada yalniz Genel acik.
    bolumAc("kamBolumGenel", true);
    bolumAc("kamBolumAi", !!aiGorevleriOku());
    bolumAc("kamBolumKalib", !!(kamera && (kamera.kalibre ||
      kamera.lat !== null && kamera.lat !== undefined && kamera.lat !== "")));
    bolumRozetleri(kamera);
    hataEl.textContent = "";
    baslikEl.textContent = kamera
      ? (t.kamModalBaslikDuzenle || "KAMERAYI DÜZENLE")
      : (t.kamModalBaslikYeni || "YENİ KAMERA");
    protokolDegisti();
    perde.classList.remove("popup-gizli");
    setTimeout(() => inAd.focus(), 50);
  }

  // v2.4.152: acilir-kapanir kamera formu bolumleri
  function bolumAc(id, acik) {
    const b = _el(id);
    if (b) b.open = !!acik;
  }

  function bolumRozetleri(kamera) {
    const t = T();
    const ai = _el("kamRozetAi");
    if (ai) {
      const n = aiGorevleriOku().split(",").filter(Boolean).length;
      ai.textContent = n
        ? String(n) + " " + (t.kamRozetSecili || "seçili")
        : (t.kamRozetGorevYok || "görev yok");
      ai.className = "kam-bolum-rozet " + (n ? "iyi" : "");
    }
    const kl = _el("kamRozetKalib");
    if (kl) {
      const kalibre = !!(kamera && kamera.kalibre);
      kl.textContent = kalibre
        ? (t.kamRozetKalibre || "kalibre")
        : (t.kamRozetEksik || "eksik");
      kl.className = "kam-bolum-rozet " + (kalibre ? "iyi" : "uyari");
    }
    const gn = _el("kamRozetGenel");
    if (gn) gn.textContent = inAd.value.trim();
  }

  function modalKapat() {
    perde.classList.add("popup-gizli");
    duzenlenenId = null;
  }

  async function modalKaydet() {
    const t = T();
    const isim = inAd.value.trim();
    const prot = inProt.value;
    let url = inUrl.value.trim();
    bolumAc("kamBolumGenel", true);
    if (!isim) { hataEl.textContent = t.kamHataAd || "Kamera ad\u0131 bo\u015f olamaz."; return; }
    if (prot === "donanim") {
      url = cihazSec.value || "";
      if (!url) { hataEl.textContent = t.kamHataCihaz || "Kamera cihaz\u0131 se\u00e7in."; return; }
    } else if (prot === "dji") {
      url = djiSec ? (djiSec.value || "") : "";
      if (!url) { hataEl.textContent = t.kamHataDji || "DJI dron se\u00e7in."; return; }
    } else if (prot === "dosya") {
      // v2.4.166: yeni dosya secildiyse once yukle; secilmediyse mevcut
      // kayitli dosya adi (duzenleme) korunur.
      const dosya = dosyaSec && dosyaSec.files && dosyaSec.files[0];
      if (dosya) {
        hataEl.textContent = "";
        if (dosyaBilgi) dosyaBilgi.textContent =
          "Y\u00fckleniyor: " + dosya.name + " (" +
          (dosya.size / 1048576).toFixed(1) + " MB)\u2026";
        try {
          url = await videoDosyaYukle(dosya);
          if (dosyaBilgi) dosyaBilgi.textContent = "Y\u00fcklendi: " + url;
        } catch (e) {
          if (dosyaBilgi) dosyaBilgi.textContent = "";
          hataEl.textContent = (t.kamHataYukleme || "Video y\u00fcklenemedi: ") + e.message;
          return;
        }
      } else {
        url = (dosyaSec && dosyaSec.dataset.mevcut) || url;
      }
      if (!url) { hataEl.textContent = t.kamHataDosya || "Video dosyas\u0131 se\u00e7in."; return; }
    } else if (prot === "m50") {
      // v2.4.181: url sunucuda "m50:<kanal>" olarak kesin uretilir; burada
      // yalniz UI tutarliligi icin ayni degeri kuruyoruz.
      const kanal = (m50KanalSec && m50KanalSec.value === "termal") ? "termal" : "gorunur";
      url = "m50:" + kanal;
    } else {
      if (!url) { hataEl.textContent = t.kamHataUrl || "Yay\u0131n adresi bo\u015f olamaz."; return; }
    }
    // v2.4.56: merkezde kopru secimi zorunludur.
    // v2.4.166: "dosya" kaynagi MERKEZ sunucusunda durur — kopru gerekmez.
    const merkezde = (typeof window.kopruMerkezKipiMi === "function")
      && window.kopruMerkezKipiMi() && prot !== "dosya";
    const kopruId = kopruSec ? String(kopruSec.value || "") : "";
    if (merkezde && !kopruId) {
      hataEl.textContent = t.kamKopruUyari ||
        "Kameran\u0131n ba\u011fl\u0131 oldu\u011fu k\u00f6pr\u00fc makinesini se\u00e7in.";
      return;
    }
    const k = { tip: "kamera_kaydet", isim: isim,
                protokol: prot, url: url,
                kopru_ornek_id: kopruId ? parseInt(kopruId, 10) : null,
                ai_gorevler: aiGorevleriOku() };
    if (inLok) k.lokasyon_id = inLok.value ? parseInt(inLok.value, 10) : null;
    if (inDron) k.dron_uid = String(inDron.value || "").trim();
    if (inFps) {
      const f = parseInt(inFps.value, 10);
      k.fps = (Number.isFinite(f) && f > 0) ? Math.min(30, f) : 15;
    }
    // v2.5.21: yerel AI angajman kalibrasyonu (kamera tipi + alanlar)
    kalibOku(k);
    if (prot === "m50") {
      k.m50_kanal = (m50KanalSec && m50KanalSec.value === "termal") ? "termal" : "gorunur";
      const ip = m50IpEl ? m50IpEl.value.trim() : "";
      const port = m50PortEl ? m50PortEl.value.trim() : "";
      const kullanici = m50KullaniciEl ? m50KullaniciEl.value.trim() : "";
      const parola = m50ParolaEl ? m50ParolaEl.value : "";
      if (ip || port || kullanici || parola) {
        if (!ip || !port || !kullanici || !parola) {
          hataEl.textContent = t.kamHataM50Baglanti ||
            "M50 bağlantısı için IP, port, kullanıcı adı ve parola birlikte girilmeli (ya da dördü de boş bırakılmalı).";
          return;
        }
        k.m50_ip = ip; k.m50_port = parseInt(port, 10) || 0;
        k.m50_kullanici = kullanici; k.m50_parola = parola;
      }
    }
    if (duzenlenenId !== null) k.id = duzenlenenId;
    wsGonder(k);
    // Parola gönderimden hemen sonra ekrandan da silinir; yerel depoya yazılmaz.
    if (m50ParolaEl) m50ParolaEl.value = "";
    modalKapat();
  }

  // v2.4.152: gorev kutusu / ad degisince bolum rozetlerini tazele
  for (const id of AI_GOREV_KUTULARI) {
    const kutu = document.getElementById(id);
    if (kutu) kutu.addEventListener("change", () => bolumRozetleri(null));
  }
  inAd.addEventListener("input", () => {
    const gn = _el("kamRozetGenel");
    if (gn) gn.textContent = inAd.value.trim();
  });

  // v2.5.21: kamera tipi degisince sabit/dron kalibrasyon panelini degistir
  {
    const _tip = document.getElementById("kamTipi");
    if (_tip) _tip.addEventListener("change", kamTipiGecisi);
  }
  document.getElementById("btnKamKaydet").addEventListener("click", modalKaydet);
  document.getElementById("btnKamIptal").addEventListener("click", modalKapat);
  document.getElementById("btnKamModalKapat").addEventListener("click", modalKapat);
  perde.addEventListener("click", (e) => { if (e.target === perde) modalKapat(); });
  inUrl.addEventListener("keydown", (e) => { if (e.key === "Enter") modalKaydet(); });

  document.getElementById("tbYeniKamera").addEventListener("click", () => modalAc(null));

  // Video duvarini ayri pencerede ac
  const btnVideoDuvar = document.getElementById("tbVideoDuvar");
  if (btnVideoDuvar) {
    btnVideoDuvar.addEventListener("click", () => {
      window.open("video.html", "goktunguVideoDuvar",
        "width=1280,height=800,menubar=no,toolbar=no,location=no,status=no");
    });
  }

  // ----------------------------------------------------------------
  // GORUNUM TOGGLE (liste <-> onizleme)
  // ----------------------------------------------------------------
  const btnGorunum = document.getElementById("tbKamGorunum");
  function gorunumIkonTazele() { if (btnGorunum) btnGorunum.style.display = "none"; }
  try { localStorage.removeItem("kamGorunum"); } catch (e) {}

  // ----------------------------------------------------------------
  // VIDEO ELEMANI OLUSTURMA / TEMIZLEME
  // ----------------------------------------------------------------
  // Donanim kamera stream'leri: deviceId -> MediaStream
  const donanimStreamler = {};

  // v2.4.188: M50 Elektro-Optik paneli (m50_panel.js) kamera kaydini,
  // kanal degisimini ve MJPEG <img> uretimini buradan kullanir — tek
  // sistem: panel ayri bir akis acmaz, mevcut M50 kamera kaydini surer.
  // v2.4.191: coklu EO — url 'm50:<eo_id>:<kanal>'; eski 'm50:<kanal>' = cihaz 1.
  function m50EoIdOku(kamera) {
    const p = String(kamera.url || "").split(":");
    return p.length >= 3 ? (parseInt(p[1], 10) || 1) : 1;
  }
  window.m50KameraBul = function (eoId) {
    const hedef = Number(eoId) > 0 ? Number(eoId) : 0;
    return kameralar.find(k => String(k.protokol || "").toLowerCase() === "m50" &&
                               (!hedef || m50EoIdOku(k) === hedef)) || null;
  };
  // v2.4.210: kanal bazli kayit (gunduz/gece ayni anda: ana + kucuk goruntu)
  window.m50KameraBulKanal = function (eoId, kanal) {
    const hedef = Number(eoId) > 0 ? Number(eoId) : 0;
    const kn = kanal === "termal" ? "termal" : "gorunur";
    return kameralar.find(k => String(k.protokol || "").toLowerCase() === "m50" &&
                               (!hedef || m50EoIdOku(k) === hedef) &&
                               String(k.url || "").split(":").pop() === kn) || null;
  };
  // v2.4.207: M50 kamera kaydinin TEK alanini degistiren ortak yardimci
  // (kanal, genislik...). fps/genislik korunur; kamera_tipi/kalibrasyon
  // KASITLI atlanir: sunucu "kamera_tipi" yoksa kalibrasyonu SILMEZ.
  window.m50KameraAlanGuncelle = function (kamera, ekstra) {
    const eoId = m50EoIdOku(kamera);
    const kanal = (ekstra && ekstra.m50_kanal) || (String(kamera.url || "").split(":").pop() === "termal" ? "termal" : "gorunur");
    const paket = {
      tip: "kamera_kaydet", id: kamera.id, isim: kamera.isim,
      protokol: "m50", url: "m50:" + eoId + ":" + kanal, m50_kanal: kanal, eo_id: eoId,
      kopru_ornek_id: kamera.kopru_ornek_id || null,
      ai_gorevler: kamera.ai_gorevler || "",
      ai_hassasiyet: kamera.ai_hassasiyet || "",
      lokasyon_id: kamera.lokasyon_id || null,
      dron_uid: kamera.dron_uid || "",
      fps: kamera.fps || 15,
      genislik: kamera.genislik || 960
    };
    if (ekstra) for (const k of Object.keys(ekstra)) if (k !== "m50_kanal") paket[k] = ekstra[k];
    wsGonder(paket);
  };
  window.m50KanalDegistir = function (kamera, yeniKanal) {
    window.m50KameraAlanGuncelle(kamera, { m50_kanal: yeniKanal });
  };
  window.m50KameraOlustur = function (eoId, isim, kanal) {
    const eid = Number(eoId) > 0 ? Number(eoId) : 1;
    const kn = kanal === "termal" ? "termal" : "gorunur";
    // v2.4.209: hava araci tanima gorevi kayitla birlikte gelir (AI izlemesi
    // gorevsiz baslatilamaz — ai_yonetici.izleme_baslat).
    wsGonder({ tip: "kamera_kaydet", isim: isim || ("M50 " + eid + (kn === "termal" ? " Termal" : "")), protokol: "m50",
               url: "m50:" + eid + ":" + kn, m50_kanal: kn, eo_id: eid,
               ai_gorevler: "hava_araci" });
  };
  window.kamVideoOlustur = function (kamera) { return videoOlustur(kamera); };

  function videoOlustur(kamera) {
    const prot = kamera.protokol;

    // v2.4.7: DONANIM da dahil tum MJPEG kaynaklari SUNUCU proxy'sinden
    // gelir — goruntu Python'da yakalanir, AI izleme aktifse tespit
    // cerceveleri + kisi/nesne adlari kare uzerine cizilmis olarak doner.
    // v2.4.10: HTTP video (MP4/WebM) da proxy'den gecer — AI anotasyonu
    // MP4 kaynaklarinda da gorunur (ffmpeg -re -stream_loop ile dongulu).
    if (prot === "rtsp" || prot === "rtp" || prot === "mjpeg" ||
        prot === "dji" || prot === "donanim" || prot === "http" ||
        prot === "dosya" || prot === "m50") {
      const img = document.createElement("img");
      img.className = "kam-video" + (prot === "m50" ? " kam-video-m50" : "");
      img.draggable = false;
      // v2.4.164: cift tikla takip modulu hangi kamerada oldugunu bilsin
      img.dataset.kameraId = String(kamera.id);
      // v2.4.33: tek seferlik `error` yerine artan gecikmeli yeniden
      // deneme. Uzak MJPEG kaynaklarinda ffmpeg'in ilk kare gecikmesi
      // (olculen: 4-14 sn) tarayicinin <img> zaman asimini asabiliyor;
      // onceki halde kutu kalici olarak "YAYIN ALINAMIYOR" durumunda
      // kaliyordu. Ayrintili kok neden: BULGU_MJPEG.md
      if (typeof window.mjpegBagla === "function") {
        window.mjpegBagla(img, () => proxyUrl(kamera.id), ".kam-video-kutu");
      } else {
        // Yardimci yuklenmediyse eski davranisa dus (guvenli geri cekilme)
        img.src = proxyUrl(kamera.id);
        img.addEventListener("error", () => {
          var kutu = img.closest(".kam-video-kutu");
          if (kutu) kutu.classList.add("kam-hata");
        });
        img.addEventListener("load", () => {
          var kutu = img.closest(".kam-video-kutu");
          if (kutu) kutu.classList.remove("kam-hata");
        });
      }
      return img;
    }
    // HLS / HTTP: <video>
    const video = document.createElement("video");
    video.className = "kam-video";
    video.autoplay = true;
    video.muted = true;
    video.playsInline = true;
    video.controls = false;
    if (prot === "hls") {
      if (window.Hls && Hls.isSupported()) {
        const h = new Hls({ lowLatencyMode: true });
        h.loadSource(kamera.url);
        h.attachMedia(video);
        hlsNesneleri[kamera.id] = h;
      } else {
        video.src = kamera.url;   // Safari native HLS
      }
    } else {
      video.src = kamera.url;
      video.loop = true;
    }
    video.addEventListener("error", () => {
      var kutu = video.closest(".kam-video-kutu");
      if (kutu) kutu.classList.add("kam-hata");
    });
    video.addEventListener("canplay", () => {
      if (video.paused) video.play().catch(() => {});
    });
    // DOM'a eklendikten sonra autoplay tetiklenmezse zorla baslat
    setTimeout(() => { if (video.paused) video.play().catch(() => {}); }, 300);
    return video;
  }

  function videoTemizle(id) {
    if (hlsNesneleri[id]) {
      try { hlsNesneleri[id].destroy(); } catch (e) {}
      delete hlsNesneleri[id];
    }
    // Donanim stream'ini durdur (eski getUserMedia kayitlari icin)
    if (donanimStreamler[id]) {
      try { donanimStreamler[id].getTracks().forEach(t => t.stop()); } catch (e) {}
      delete donanimStreamler[id];
    }
    const kam = kameralar.find((k) => k.id === id);
    if (kam && (kam.protokol === "rtsp" || kam.protokol === "rtp" ||
                kam.protokol === "dji" || kam.protokol === "mjpeg" ||
                kam.protokol === "donanim" || kam.protokol === "http" ||
                kam.protokol === "dosya")) {
      // Sunucudaki FFmpeg/yakalama surecini serbest birak
      wsGonder({ tip: "kamera_proxy_durdur", id: id });
    }
  }

  // ----------------------------------------------------------------
  // PLAY / STOP
  // ----------------------------------------------------------------
  function _kameraAiGorevliMi(id) {
    const kam = kameralar.find((k) => Number(k.id) === Number(id));
    return !!(kam && String(kam.ai_gorevler || "").trim());
  }
  function oynat(id) {
    oynayanlar.add(id);
    // v2.4.158: Kamera KULLANICI tarafından başlatılınca, görevi varsa AI
    // izlemesi de başlar (otomatik başlatma kaldırıldı; manuel kontrol).
    if (_kameraAiGorevliMi(id) && typeof window.aiIzlemeBaslat === "function") {
      try { window.aiIzlemeBaslat(id); } catch (e) {}
    }
    listeCiz();
    // Bağlı dronların harita önizlemesi Play sonrasında anında görünür.
    if (typeof window.dronKameraHaritaOnizlemeTazele === "function")
      window.dronKameraHaritaOnizlemeTazele();
    // Ayrik penceredeyse onu da tazele
    if (ayrikler[id]) ayrikVideoTazele(id);
    if (typeof window.dronKartKameraTazeleTum === "function") window.dronKartKameraTazeleTum();
  }
  function durdur(id) {
    oynayanlar.delete(id);
    // v2.4.158: Durdur -> AI izlemesini de durdur.
    if (typeof window.aiIzlemeDurdur === "function") {
      try { window.aiIzlemeDurdur(id); } catch (e) {}
    }
    videoTemizle(id);
    if (typeof tamEkranId !== "undefined" && tamEkranId === id) tamEkranKapat();
    listeCiz();
    // Stop sonrası bağlı dronun küçük önizlemesini kaldır.
    if (typeof window.dronKameraHaritaOnizlemeTazele === "function")
      window.dronKameraHaritaOnizlemeTazele();
    if (ayrikler[id]) ayrikVideoTazele(id);
    if (typeof window.dronKartKameraTazeleTum === "function") window.dronKartKameraTazeleTum();
  }

  // Menubar: TUM KAMERALARA BAGLAN (hepsi oynuyorsa tumunu durdur - toggle)
  window.tumKameralaraBaglan = function () {
    if (!kameralar.length) return;
    const hepsiOynuyor = kameralar.every((k) => oynayanlar.has(k.id));
    if (hepsiOynuyor) {
      kameralar.forEach((k) => { oynayanlar.delete(k.id); videoTemizle(k.id); });
    } else {
      kameralar.forEach((k) => oynayanlar.add(k.id));
    }
    listeCiz();
    kameralar.forEach((k) => { if (ayrikler[k.id]) ayrikVideoTazele(k.id); });
  };

  // ----------------------------------------------------------------
  // KAMERA SATIRI / KARTI OLUSTURMA
  // ----------------------------------------------------------------
  function protokolRozet(prot) {
    const b = document.createElement("span");
    b.className = "kam-prot-rozet kam-prot-" + prot;
    b.textContent = prot.toUpperCase();
    return b;
  }

  function araclarOlustur(kamera) {
    const t = T();
    const kutu = document.createElement("div");
    kutu.className = "kam-araclar";
    const oynuyor = oynayanlar.has(kamera.id);

    const bPlay = document.createElement("button");
    bPlay.className = "kam-btn " + (oynuyor ? "kam-btn-stop" : "kam-btn-play");
    bPlay.title = oynuyor ? (t.kamStop || "Durdur") : (t.kamPlay || "Oynat");
    bPlay.innerHTML = oynuyor
      ? "<i class='fa-solid fa-stop'></i>" : "<i class='fa-solid fa-play'></i>";
    bPlay.addEventListener("click", (e) => {
      e.stopPropagation();
      if (oynayanlar.has(kamera.id)) {
        durdur(kamera.id);
      } else {
        // GRCOFF: Play, harita önizlemesinin de kullandığı ortak pencereyi açar.
        window.kameraIzlemeAc(kamera.id);
      }
    });

    // v2.4.222: "Panele yerlestir" ve goruntu-konumu secici kaldirildi.

    // v2.4.189: Kullanici istegi — "cok fazla dugme oldu": duzenle / AI /
    // (M50: Elektro-Optik paneli, kanal) / sil TEK "..." menusune; goruntu
    // konumu (4 dugme) TEK acilir dugmeye indi (kamera_ai_panel.js).
    kutu.append(bPlay);

    const bMenu = document.createElement("button");
    bMenu.className = "kam-btn kam-menu-btn";
    bMenu.title = t.kamMenu || "Diğer işlemler";
    bMenu.innerHTML = "<i class='fa-solid fa-ellipsis-vertical'></i>";
    const dd = document.createElement("div");
    dd.className = "dk-menu-dropdown kam-menu";
    const oge = (ikon, metin, tik, sinif) => {
      const it = document.createElement("div");
      it.className = "dk-menu-item" + (sinif ? " " + sinif : "");
      it.innerHTML = "<i class='fa-solid " + ikon + "'></i><span>" + metin + "</span>";
      it.addEventListener("click", (e) => { e.stopPropagation(); dd.classList.remove("acik"); tik(); });
      dd.appendChild(it);
    };
    oge("fa-pen", t.kamDuzenle || "Düzenle", () => modalAc(kamera));
    if (typeof window.kameraAiAyarPanelAc === "function")
      oge("fa-robot", t.kaiBaslik || "Yapay Zeka Ayarları", () => window.kameraAiAyarPanelAc(kamera.id));
    if (kamera.protokol === "m50") {
      const kanalSu = String(kamera.url || "").split(":")[1] === "termal" ? "termal" : "gorunur";
      oge("fa-binoculars", t.kamM50Panel || "Elektro-Optik paneli", () => {
        if (typeof window.yuzenPanelAc === "function") window.yuzenPanelAc("yzM50");
      });
      oge(kanalSu === "termal" ? "fa-sun" : "fa-fire",
          (t.kamM50KanalGecis || "Kanal değiştir") + " → " +
          (kanalSu === "termal" ? (t.m50Gorunur || "Görünür") : (t.m50Termal || "Termal")),
          () => window.m50KanalDegistir(kamera, kanalSu === "termal" ? "gorunur" : "termal"));
    }
    const ayrac = document.createElement("div"); ayrac.className = "dk-menu-ayrac"; dd.appendChild(ayrac);
    oge("fa-trash", t.kamSil || "Sil", () => {
      onayIste(onayMetni("onayKameraSil", {ad: kamera.isim || kamera.id}), () => {
        durdur(kamera.id);
        ayrikKapat(kamera.id);
        wsGonder({ tip: "kamera_sil", id: kamera.id });
      });
    }, "tehlikeli");
    bMenu.addEventListener("click", (e) => { e.stopPropagation(); window.kamMenuAcKapa(bMenu, dd); });
    kutu.append(bMenu, dd);
    return kutu;
  }

  // v2.4.189: ortak acilir menu ac/kapa (sabit konumlu .dk-menu-dropdown;
  // arayuz.js'teki hedef menusuyle ayni yerlesim kurali). Disari tiklama ve
  // Escape kapatir; ayni anda yalniz bir menu acik kalir.
  window.kamMenuAcKapa = function (btn, dd) {
    const acilacak = !dd.classList.contains("acik");
    document.querySelectorAll(".dk-menu-dropdown.acik").forEach(m => m.classList.remove("acik"));
    if (!acilacak) return;
    dd.classList.add("acik");
    const r = btn.getBoundingClientRect();
    let top = r.bottom + 4, left = r.left;
    dd.style.top = top + "px"; dd.style.left = left + "px";
    const mr = dd.getBoundingClientRect();
    if (mr.right > window.innerWidth) left = Math.max(4, window.innerWidth - mr.width - 8);
    if (mr.bottom > window.innerHeight) top = Math.max(4, r.top - mr.height - 4);
    dd.style.top = top + "px"; dd.style.left = left + "px";
  };
  document.addEventListener("click", (ev) => {
    if (!ev.target.closest(".kam-menu, .kam-hedef-menu"))
      document.querySelectorAll(".kam-menu.acik, .kam-hedef-menu.acik").forEach(m => m.classList.remove("acik"));
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape")
      document.querySelectorAll(".kam-menu.acik, .kam-hedef-menu.acik").forEach(m => m.classList.remove("acik"));
  });

  // =================================================================
  // v2.4.189: KAMERA BASINA HABERLESME KONSOLU — dronlar.js'teki
  // dk-konsol deseninin esi. Satir yeniden cizilse de konsol DOM'u ve
  // acik/kapali durumu `kamKonsollar[id]` icinde korunur.
  // =================================================================
  const KAM_KONSOL_DOM_LIMIT = 400;
  const KAM_KONSOL_SEV = { bilgi: "dk-kons-bilgi", basari: "dk-kons-basari",
                           uyari: "dk-kons-uyari", hata: "dk-kons-hata" };
  const kamKonsollar = {};
  function kamKonsolSaat(ts) {
    const n = Number(ts);
    if (!isFinite(n) || n <= 0) return "";
    const d = new Date(n * 1000);
    const iki = (x) => String(x).padStart(2, "0");
    return iki(d.getHours()) + ":" + iki(d.getMinutes()) + ":" + iki(d.getSeconds());
  }
  function kamKonsolSatirBas(k, s) {
    if (s && s.yeni === false && k.sonSatirEl && k.sonMetin === (s.etiket + " " + s.metin)) {
      let roz = k.sonSatirEl.querySelector(".dk-kons-tekrar");
      if (!roz) { roz = document.createElement("span"); roz.className = "dk-kons-tekrar"; k.sonSatirEl.appendChild(roz); }
      roz.textContent = "×" + (s.tekrar || 2);
      return;
    }
    const el = document.createElement("div");
    el.className = "dk-kons-satir " + (KAM_KONSOL_SEV[s.sev] || KAM_KONSOL_SEV.bilgi);
    const zs = document.createElement("span"); zs.className = "dk-kons-ts"; zs.textContent = kamKonsolSaat(s.ts);
    const es = document.createElement("span"); es.className = "dk-kons-etiket"; es.textContent = s.etiket || "";
    const ms = document.createElement("span"); ms.className = "dk-kons-metin"; ms.textContent = s.metin || "";
    el.append(zs, es, ms);
    if (s.tekrar && s.tekrar > 1) { const roz = document.createElement("span"); roz.className = "dk-kons-tekrar"; roz.textContent = "\u00d7" + s.tekrar; el.appendChild(roz); }
    // v2.4.219: etiketi AI olan satirlar AI sekmesine
    const aiMi = String(s.etiket || "").toUpperCase() === "AI";
    const hedefGovde = (aiMi && k.govdeAi) ? k.govdeAi : k.govde;
    hedefGovde.appendChild(el);
    k.sonSatirEl = el; k.sonMetin = (s.etiket || "") + " " + (s.metin || "");
    if (aiMi) { k.adetAi = (k.adetAi || 0) + 1; if (k.skAi) k.skAi.querySelector(".kam-konsol-sekme-sayac").textContent = String(Math.min(k.adetAi, 9999)); }
    else k.adet++;
    while (hedefGovde.childElementCount > KAM_KONSOL_DOM_LIMIT) hedefGovde.removeChild(hedefGovde.firstElementChild);
  }
  function kamKonsolBolumu(id) {
    if (kamKonsollar[id]) return kamKonsollar[id];
    const t = T();
    const kok = document.createElement("div"); kok.className = "dk-konsol kam-konsol";
    const bas = document.createElement("div"); bas.className = "dk-konsol-bas kapali";
    const ok = document.createElement("i"); ok.className = "fa-solid fa-chevron-down dk-konsol-ok";
    const ikon = document.createElement("i"); ikon.className = "fa-solid fa-terminal dk-konsol-ikon";
    const ad = document.createElement("span"); ad.className = "dk-konsol-ad";
    ad.textContent = t.kamKonsolBaslik || "Kamera konsolu";
    const sayac = document.createElement("span"); sayac.className = "dk-konsol-sayac"; sayac.textContent = "0";
    const araclar = document.createElement("span"); araclar.className = "dk-konsol-araclar";
    const btnDur = document.createElement("button"); btnDur.type = "button"; btnDur.className = "dk-konsol-btn";
    btnDur.innerHTML = '<i class="fa-solid fa-pause"></i>'; btnDur.title = t.dkKonsolDurdur || "Akışı duraklat";
    const btnTemiz = document.createElement("button"); btnTemiz.type = "button"; btnTemiz.className = "dk-konsol-btn";
    btnTemiz.innerHTML = '<i class="fa-solid fa-trash-can"></i>'; btnTemiz.title = t.dkKonsolTemizle || "Konsolu temizle";
    araclar.append(btnDur, btnTemiz);
    bas.append(ok, ikon, ad, sayac, araclar);
    const govde = document.createElement("div"); govde.className = "dk-konsol-govde gizli";
    // v2.4.219 (kullanici istegi): AI cikti satirlari ayri sekmede
    const sekmeler = document.createElement("div"); sekmeler.className = "kam-konsol-sekmeler gizli";
    const govdeAi = document.createElement("div"); govdeAi.className = "dk-konsol-govde gizli";
    const skKam = document.createElement("button"); skKam.type = "button"; skKam.className = "kam-konsol-sekme aktif";
    skKam.innerHTML = "<i class='fa-solid fa-video'></i><span>" + (t.kamKonsolSekmeKamera || "Kamera") + "</span>";
    const skAi = document.createElement("button"); skAi.type = "button"; skAi.className = "kam-konsol-sekme";
    skAi.innerHTML = "<i class='fa-solid fa-robot'></i><span>" + (t.kamKonsolSekmeAi || "AI") + "</span><b class='kam-konsol-sekme-sayac'></b>";
    sekmeler.append(skKam, skAi);
    kok.append(bas, sekmeler, govde, govdeAi);
    const k = { kok, bas, govde, govdeAi, sekmeler, skKam, skAi, sayac, ok, btnDur, acik: false, duraklat: false,
                gecmisIstendi: false, adet: 0, adetAi: 0, sonMetin: null, sonSatirEl: null, sekme: "kam" };
    const sekmeSec = (ad) => {
      k.sekme = ad;
      skKam.classList.toggle("aktif", ad === "kam"); skAi.classList.toggle("aktif", ad === "ai");
      govde.classList.toggle("gizli", !(k.acik && ad === "kam"));
      govdeAi.classList.toggle("gizli", !(k.acik && ad === "ai"));
      const g = ad === "ai" ? govdeAi : govde; g.scrollTop = g.scrollHeight;
    };
    skKam.addEventListener("click", (e) => { e.stopPropagation(); sekmeSec("kam"); });
    skAi.addEventListener("click", (e) => { e.stopPropagation(); sekmeSec("ai"); });
    k.sekmeSec = sekmeSec;
    bas.addEventListener("click", (e) => {
      if (e.target.closest(".dk-konsol-araclar")) return;
      e.stopPropagation();
      k.acik = !k.acik;
      bas.classList.toggle("kapali", !k.acik);
      sekmeler.classList.toggle("gizli", !k.acik);
      sekmeSec(k.sekme);
      // v2.4.222 (kullanici bildirimi: konsol gorunmuyordu): yuzen pencere
      // sabit yukseklikli; konsol acilinca pencere KONSOL_YUK kadar uzar.
      const pw = kok.closest(".kam-pencere");
      if (pw && !pw.classList.contains("kam-pencere-tam")) {
        const KONSOL_YUK = 340;   // v2.4.223: 300px govde + sekmeler (goruntu kuculmesin)
        const h = parseFloat(getComputedStyle(pw).height) || 400;
        pw.style.height = Math.max(260, h + (k.acik ? KONSOL_YUK : -KONSOL_YUK)) + "px";
      }
      if (k.acik) {
        if (!k.gecmisIstendi) { k.gecmisIstendi = true; wsGonder({ tip: "kamera_konsol_gecmis", id }); }
      }
    });
    btnDur.addEventListener("click", (e) => {
      e.stopPropagation();
      k.duraklat = !k.duraklat;
      btnDur.innerHTML = k.duraklat ? '<i class="fa-solid fa-play"></i>' : '<i class="fa-solid fa-pause"></i>';
      btnDur.classList.toggle("etkin", k.duraklat);
    });
    btnTemiz.addEventListener("click", (e) => {
      e.stopPropagation();
      wsGonder({ tip: "kamera_konsol_temizle", id });
      govde.innerHTML = ""; govdeAi.innerHTML = ""; k.adet = 0; k.adetAi = 0; k.sonMetin = null; k.sonSatirEl = null; sayac.textContent = "0";
      k.skAi.querySelector(".kam-konsol-sekme-sayac").textContent = "";
    });
    kamKonsollar[id] = k;
    return k;
  }
  window.kameraKonsolSatir = function (m) {
    const k = kamKonsollar[m.id];
    if (!k) return;
    k.sayac.textContent = String(Math.min(k.adet + 1, 9999));
    if (k.duraklat || !k.gecmisIstendi) return;
    const dipte = (k.govde.scrollHeight - k.govde.scrollTop - k.govde.clientHeight) < 24;
    kamKonsolSatirBas(k, m.satir || {});
    if (dipte) k.govde.scrollTop = k.govde.scrollHeight;
  };
  window.kameraKonsolGecmis = function (m) {
    const k = kamKonsollar[m.id];
    if (!k) return;
    k.govde.innerHTML = ""; if (k.govdeAi) k.govdeAi.innerHTML = ""; k.adet = 0; k.adetAi = 0; k.sonMetin = null; k.sonSatirEl = null;
    (m.satirlar || []).forEach((s) => kamKonsolSatirBas(k, s));
    k.sayac.textContent = String(k.adet);
    k.govde.scrollTop = k.govde.scrollHeight; if (k.govdeAi) k.govdeAi.scrollTop = k.govdeAi.scrollHeight;
  };

  function satirOlustur(kamera) {
    // LISTE gorunumu: tek satir (ad + protokol + araclar)
    const satir = document.createElement("div");
    satir.className = "kam-satir";
    satir.dataset.id = kamera.id;

    const sol = document.createElement("div");
    sol.className = "kam-satir-sol";
    const ikon = document.createElement("i");
    ikon.className = "fa-solid fa-video kam-ikon" +
      (oynayanlar.has(kamera.id) ? " kam-ikon-aktif" : "");
    const ad = document.createElement("span");
    ad.className = "kam-ad";
    ad.textContent = kamera.isim;
    ad.title = kamera.url;
    sol.append(ikon, ad, protokolRozet(kamera.protokol));
    // v2.4.8: AI izleme aktifse yesil AI rozeti
    const aiRozetS = aiRozetOlustur(kamera.id);
    if (aiRozetS) sol.appendChild(aiRozetS);
    // v2.4.219 (kullanici istegi): panel satirinda YALNIZ Duzenle + Sil;
    // oynat/ayir/goruntu-hedefi/menu yok. Satira tiklamak yuzen pencereyi
    // acar (canli goruntu, konsol ve diger araclar orada).
    const t = T();
    const araclar = document.createElement("div");
    araclar.className = "kam-araclar kam-satir-araclar";
    const bDuzenle = document.createElement("button");
    bDuzenle.className = "kam-btn"; bDuzenle.title = t.kamDuzenle || "Düzenle";
    bDuzenle.innerHTML = "<i class='fa-solid fa-pen'></i>";
    bDuzenle.addEventListener("click", (e) => { e.stopPropagation(); modalAc(kamera); });
    const bSil = document.createElement("button");
    bSil.className = "kam-btn kam-btn-sil"; bSil.title = t.kamSil || "Sil";
    bSil.innerHTML = "<i class='fa-solid fa-trash'></i>";
    bSil.addEventListener("click", (e) => {
      e.stopPropagation();
      onayIste(onayMetni("onayKameraSil", {ad: kamera.isim || kamera.id}), () => {
        durdur(kamera.id);
        ayrikKapat(kamera.id);
        wsGonder({ tip: "kamera_sil", id: kamera.id });
      });
    });
    araclar.append(bDuzenle, bSil);
    satir.append(sol, araclar);
    satir.classList.add("kam-satir-tikla");
    satir.title = t.kamSatirAc || "Yüzen pencerede aç";
    if (ayrikler[kamera.id]) satir.classList.add("kam-satir-acik");
    satir.addEventListener("click", () => {
      // v2.4.224: pencere zaten aciksa yalniz ONE AL (odakla); yeni akis yok.
      if (ayrikler[kamera.id]) { ayrikAc(kamera.id); return; }
      if (typeof window.kameraGoruntuHedefiAyarla === "function") window.kameraGoruntuHedefiAyarla(kamera.id, "yuzen");
      else window.kameraIzlemeAc(kamera.id);
    });
    const dis = document.createElement("div");
    dis.className = "kam-blok";
    dis.appendChild(satir);
    return dis;
  }

  function kartOlustur(kamera) {
    // ONIZLEME gorunumu: kucuk onizleme karti
    const kart = document.createElement("div");
    kart.className = "kam-kart";
    kart.dataset.id = kamera.id;

    const baslik = document.createElement("div");
    baslik.className = "kam-kart-baslik";
    const ad = document.createElement("span");
    ad.className = "kam-ad";
    ad.textContent = kamera.isim;
    ad.title = kamera.url;
    baslik.append(ad, protokolRozet(kamera.protokol));
    // v2.4.8: AI izleme aktifse yesil AI rozeti
    const aiRozet = aiRozetOlustur(kamera.id);
    if (aiRozet) baslik.appendChild(aiRozet);

    // v2.4.6: kamera ayri penceredeyse panelde bos kutu BIRAKILMAZ;
    // kart kompakt hale duser (baslik + araclar), pencere kapaninca
    // listeCiz() ile onizleme kutusu geri gelir.
    if (ayrikler[kamera.id]) {
      kart.classList.add("kam-kart-ayrik");
      kart.append(baslik, araclarOlustur(kamera));
      return kart;
    }

    const kutu = document.createElement("div");
    kutu.className = "kam-video-kutu kam-onizleme";
    if (oynayanlar.has(kamera.id) && hedef(kamera.id) === "panel") {
      kutu.appendChild(videoOlustur(kamera));
    } else if (oynayanlar.has(kamera.id)) {
      // Baska bir hedefte gosteriliyor: panelde nerede oldugunu bildir
      const bilgi = document.createElement("div");
      bilgi.className = "kam-bos-onizleme kam-baska-hedef";
      const nerede = { harita: "haritada", yuzen: "yüzen pencerede", tam: "tam ekranda" };
      bilgi.innerHTML = "<i class='fa-solid fa-up-right-from-square'></i>" +
        "<span>" + (nerede[hedef(kamera.id)] || "başka yerde") + "</span>";
      kutu.appendChild(bilgi);
    } else {
      const bos = document.createElement("div");
      bos.className = "kam-bos-onizleme";
      bos.innerHTML = "<i class='fa-solid fa-video-slash'></i>";
      kutu.appendChild(bos);
    }

    kart.append(baslik, kutu, araclarOlustur(kamera));
    return kart;
  }

  // v2.4.8: kamera icin aktif AI izleme rozeti (yoksa null)
  function aiRozetOlustur(kameraId) {
    const izler = window._aiIzlemelerSon || [];
    if (!izler.some((iz) => iz.kamera_id === kameraId)) return null;
    const r = document.createElement("span");
    r.className = "kam-ai-rozet";
    r.textContent = "AI";
    r.title = T().aiIzlemeAktif || "AI izleme aktif";
    return r;
  }

  // v2.4.8: izleme listesi degisince rozetler tazelensin
  window.aiIzlemeDegisti = function () { listeCiz(); };

  // ----------------------------------------------------------------
  // v2.4.56: KOPRU GRUPLARI
  // Baglanti Yoneticisi ve AI Sunuculari ile ayni gorunum kalibi.
  // Onizleme kipinde kartlar izgaraya yerlesir; bu yuzden her grup
  // kendi izgara kabinda cizilir, yoksa grup basliklari izgara
  // hucresi olur ve duzen bozulur.
  // ----------------------------------------------------------------
  function kamKopruBaslik(k, ornekId) {
    const t = T();
    const bas = document.createElement("div");
    bas.className = "kam-kopru-baslik";
    const led = document.createElement("span");
    led.className = "kam-kopru-led " +
      ((k && k.cevrimici) ? "cevrimici" : "cevrimdisi");
    bas.appendChild(led);
    const ad = document.createElement("span");
    ad.className = "ad";
    ad.textContent = (k && k.ad) ? k.ad : ("#" + ornekId);
    bas.appendChild(ad);
    const rozet = document.createElement("span");
    rozet.className = "kam-kopru-rozet";
    rozet.textContent = t.bagKopruEtiket || "K\u00d6PR\u00dc";
    bas.appendChild(rozet);
    if (k && k.ip) {
      const yer = document.createElement("span");
      yer.className = "alt";
      yer.textContent = k.ip;
      bas.appendChild(yer);
    }
    if (k && !k.cevrimici) {
      const cd = document.createElement("span");
      cd.className = "alt";
      cd.textContent = t.bagKopruCevrimdisi || "\u00e7evrimd\u0131\u015f\u0131";
      bas.appendChild(cd);
    }
    return bas;
  }

  function kamBosNot(metin) {
    const not = document.createElement("div");
    not.className = "kam-kopru-bos";
    not.textContent = metin;
    return not;
  }

  function kamGrupKabi() {
    const kab = document.createElement("div");
    kab.className = (gorunum === "onizleme")
      ? "kam-izgara kam-kopru-govde" : "kam-kopru-govde";
    return kab;
  }

  function kameraGrupluCiz(kok, kameraListesi) {
    const t = T();
    // Izgara sinifi grup kablarina tasinir; kok duz akis olur.
    kok.className = "kam-kopru-liste";
    const kopruler = (typeof window.kopruListesiAl === "function")
      ? window.kopruListesiAl() : [];
    const kullanilan = new Set();
    for (const kp of kopruler) {
      const oid = String(kp.ornek_id);
      kullanilan.add(oid);
      kok.appendChild(kamKopruBaslik(kp, oid));
      const altindakiler = kameraListesi.filter(
        (k) => String(k.kopru_ornek_id || "") === oid);
      if (!altindakiler.length) {
        kok.appendChild(kamBosNot(t.kopruGrupKameraYok ||
          "Bu k\u00f6pr\u00fcde kay\u0131tl\u0131 kamera yok"));
        continue;
      }
      const kab = kamGrupKabi();
      altindakiler.forEach((k) => {
        kab.appendChild(gorunum === "onizleme"
          ? kartOlustur(k) : satirOlustur(k));
      });
      kok.appendChild(kab);
    }
    // Koprusu bilinmeyen kayitlar ASLA gizlenmez.
    const artakalan = kameraListesi.filter((k) => {
      const oid = String(k.kopru_ornek_id || "");
      return !oid || !kullanilan.has(oid);
    });
    if (artakalan.length) {
      const bas = document.createElement("div");
      bas.className = "kam-kopru-baslik grupsuz";
      const ad = document.createElement("span");
      ad.className = "ad";
      ad.textContent = t.kopruGrupsuzKamera || "K\u00d6PR\u00dcYE BA\u011eLI OLMAYAN";
      bas.appendChild(ad);
      kok.appendChild(bas);
      const kab = kamGrupKabi();
      artakalan.forEach((k) => {
        kab.appendChild(gorunum === "onizleme"
          ? kartOlustur(k) : satirOlustur(k));
      });
      kok.appendChild(kab);
    }
  }

  // ----------------------------------------------------------------
  // LISTE CIZIMI
  // ----------------------------------------------------------------
  function listeCiz() {
    const kok = listeKok();
    if (!kok) return;
    kok.innerHTML = "";
    kok.className = (gorunum === "onizleme") ? "kam-izgara" : "";
    // v2.4.33: AYRIK PENCEREDEKI KAMERA LISTEDE GORUNMEZ
    // ----------------------------------------------------------------
    // Kullanici istegi: "kamera dronda oldugu gibi ayri pencere icinde
    // acilinca kameralar panelinden kalkacak". Onceki surumde kamera
    // ayrik pencerede acikken panelde de kompakt bir kart/satir olarak
    // duruyordu (kam-kart-ayrik); bu, ayni kameranin iki yerde
    // gorunmesine ve panelde olu bir satir kalmasina yol aciyordu.
    // Pencere kapatilinca ayrikKapat() -> listeCiz() cagrildigi icin
    // satir kendiliginden geri doner.
    // v2.4.207 (kullanici: "M50 neden kameralar modulunde de gorunuyor,
    // M50 ayri bir sistem"): M50 gorunutu kayitlari (m50:<eo>:<kanal>)
    // yalniz vekil akisi icin tutulur; Kameralar panelinde LISTELENMEZ.
    // Elektro-optik cihazlar kendi listesinde ve kendi penceresindedir.
    const modulKameralari = kameralar.filter((k) => String(k.protokol || "").toLowerCase() !== "m50");
    // v2.4.224 (kullanici istegi): yuzen penceresi acik kamera LISTEDEN
    // CIKMAZ; satira tekrar tiklaninca acik pencere one alinir (ayrikAc).
    const panelKameralari = modulKameralari;
    // v2.4.56: KOPRU BAZLI GRUPLAMA
    // Merkezde kameralar saha makinelerine baglidir. Duz liste hangi
    // kameranin hangi sahada oldugunu gizler. Yerel kurulumda gruplama
    // yapilmaz (tek makine); eski gorunum birebir korunur.
    const merkezde = (typeof window.kopruMerkezKipiMi === "function")
      && window.kopruMerkezKipiMi();
    if (merkezde) {
      kameraGrupluCiz(kok, panelKameralari);
    } else {
      panelKameralari.forEach((k) => {
        kok.appendChild(gorunum === "onizleme" ? kartOlustur(k) : satirOlustur(k));
      });
    }
    // v2.4.33: ayrik pencere sayisini gosteren bilgi satiri. Panel bos
    // gorunurken kullanicinin "kameralarim nereye gitti" sorusunu
    // onlemek icin gerekli.
    const ayrikSayi = modulKameralari.length - panelKameralari.length;
    if (ayrikSayi > 0) {
      const not = document.createElement("div");
      not.className = "kam-ayrik-not";
      const t = T();
      const kalip = t.kamAyrikNot || "%s kamera ayrı pencerede";
      not.innerHTML = "<i class='fa-solid fa-window-restore'></i> " +
        kalip.replace("%s", String(ayrikSayi));
      kok.appendChild(not);
    }
    const bosKutu = document.getElementById("kameraYokKutu");
    // Bos durum yalnizca HIC kamera kaydi yoksa gosterilir; tum
    // kameralar ayrik penceredeyse yukaridaki bilgi satiri devrede.
    if (bosKutu) bosKutu.classList.toggle("gizli", modulKameralari.length > 0);
  }

  // ----------------------------------------------------------------
  // AYRIK (TASINABILIR) VIDEO PENCERESI
  // ----------------------------------------------------------------
  function ayrikAc(id) {
    const mevcut = ayrikler[id];
    if (mevcut) {
      // Aynı kamera için ikinci video/akış yaratma; yalnız mevcut pencereyi öne al.
      const ust = [...document.querySelectorAll(".kam-pencere")]
        .reduce((deger, el) => Math.max(deger, Number(el.style.zIndex || 1000)), 1000);
      mevcut.pencere.style.zIndex = String(ust + 1);
      ayrikVideoTazele(id);
      return true;
    }
    const kamera = kameralar.find((k) => k.id === id);
    if (!kamera) return false;
    // v2.4.208: M50 ayri sistemdir; hangi yoldan gelirse gelsin (harita
    // onizlemesi, goruntu hedefi "yuzen", eski cagrilar) kamera modulunun
    // penceresi DEGIL, M50 penceresi acilir.
    if (String(kamera.protokol || "").toLowerCase() === "m50" &&
        typeof window.m50PencereAc === "function") {
      window.m50PencereAc(m50EoIdOku(kamera), kamera.id);
      return true;
    }
    const t = T();
    const pencere = document.createElement("div");
    pencere.className = "kam-pencere";
    const baslik = document.createElement("div");
    baslik.className = "kam-pencere-baslik";
    const ad = document.createElement("span");
    ad.innerHTML = "<i class='fa-solid fa-video'></i> " + kamera.isim;
    // v2.4.222 (kullanici istegi): standart pencere yonetimi — kapatma
    // carpisinin yaninda TAM EKRAN dugmesi (pencere ekrani kaplar).
    const btnTam = document.createElement("button");
    btnTam.className = "kam-btn kam-btn-tam";
    btnTam.title = t.kamTamEkran || "Tam ekran";
    btnTam.innerHTML = "<i class='fa-solid fa-expand'></i>";
    btnTam.addEventListener("click", (e) => {
      e.stopPropagation();
      const tam = !pencere.classList.contains("kam-pencere-tam");
      if (tam) {
        pencere._eskiStil = pencere.getAttribute("style") || "";
        pencere.classList.add("kam-pencere-tam");
        // v2.4.224 (kullanici istegi): tam ekran ekrani KAPLAMAZ; %80 x %80, ortali
        pencere.style.left = "10vw"; pencere.style.top = "10vh"; pencere.style.width = "80vw"; pencere.style.height = "80vh";
        btnTam.innerHTML = "<i class='fa-solid fa-compress'></i>"; btnTam.title = t.kamTamEkranKapat || "Tam ekrandan çık";
      } else {
        pencere.classList.remove("kam-pencere-tam");
        pencere.setAttribute("style", pencere._eskiStil || "");
        btnTam.innerHTML = "<i class='fa-solid fa-expand'></i>"; btnTam.title = t.kamTamEkran || "Tam ekran";
      }
    });
    const btnKapat = document.createElement("button");
    btnKapat.className = "kam-btn";
    btnKapat.title = "Görüntüyü kapat";
    btnKapat.innerHTML = "<i class='fa-solid fa-xmark'></i>";
    btnKapat.addEventListener("click", () => {
      // X yalnız bu kamera için pencereyi ve yerel akışı kapatır.
      durdur(id);
      ayrikKapat(id);
      listeCiz();
    });
    const baslikDgm = document.createElement("span"); baslikDgm.className = "kam-pencere-baslik-dgm";
    baslikDgm.append(btnTam, btnKapat);
    baslik.append(ad, baslikDgm);
    const kutu = document.createElement("div");
    kutu.className = "kam-video-kutu kam-pencere-video";
    const altBar = document.createElement("div");
    altBar.className = "kam-pencere-alt";
// v2.5.24: Yüzen pencere alt çubuğu — AI Ayarları (paylaşımlı açılır
    // panel) + görüntü hedefi seçici + düzenle. Eski satır içi AI kümesi
    // (tek global hassasiyet, radar sınıflandırıcıya gidiyordu) kaldırıldı;
    // yerini sınıf başına hassasiyet/aç-kapa taşıyan ortak panel aldı.
    const araclar = document.createElement("div");
    araclar.className = "kam-araclar kam-pencere-araclar";
    if (typeof window.kameraAiAyarButonu === "function")
      araclar.appendChild(window.kameraAiAyarButonu(kamera.id));
    const bDuzenleP = document.createElement("button");
    bDuzenleP.className = "kam-btn"; bDuzenleP.title = (t.kamDuzenle || "Düzenle");
    bDuzenleP.innerHTML = "<i class='fa-solid fa-pen'></i>";
    bDuzenleP.addEventListener("click", (e) => { e.stopPropagation(); modalAc(kamera); });
    araclar.appendChild(bDuzenleP);
    // v2.4.222: goruntu-konumu secici kaldirildi
    altBar.appendChild(araclar);
    pencere.append(baslik, kutu, altBar);
    // v2.4.206 (kullanici istegi): en altta DURUM CUBUGU — kameranin
    // temel bilgileri (ad, protokol, cozunurluk, FPS tavani, akis durumu).
    const durumBar = document.createElement("div");
    durumBar.className = "kam-pencere-durum";
    pencere.append(durumBar);
    // v2.4.219: kamera konsolu (Kamera / AI sekmeleri) yuzen pencerenin altinda
    pencere.appendChild(kamKonsolBolumu(id).kok);
    document.body.appendChild(pencere);
    // v2.4.206 (kullanici istegi): yeniden boyutlandirma PENCERENIN
    // BUTUNUNE uygulanir (CSS .kam-pencere resize:both); goruntu kutusu
    // kalan alani doldurur. Konum + boyut tek anahtarla saklanir.
    const kayitVar = typeof window.pencereKonumUygula === "function" &&
                     window.pencereKonumUygula("kam_" + id, pencere, true);
    if (!kayitVar) {
      pencere.style.left = Math.max(8, (window.innerWidth - 500) / 2 +
        (Object.keys(ayrikler).length * 30)) + "px";
      pencere.style.top = Math.max(8, 90 +
        (Object.keys(ayrikler).length * 30)) + "px";
    }
    ayrikler[id] = { pencere: pencere, kutu: kutu, altBar: altBar, durumBar: durumBar };
    pencereSurukleKur(pencere, baslik, id);
    if (typeof ResizeObserver !== "undefined" &&
        typeof window.pencereKonumKaydet === "function") {
      let ilk = true;
      const ro = new ResizeObserver(() => {
        if (ilk) { ilk = false; return; }
        if (pencere.classList.contains("kam-pencere-tam")) return;
        window.pencereKonumKaydet("kam_" + id, pencere, true);
      });
      ro.observe(pencere);
    }
    if (!oynayanlar.has(id)) oynayanlar.add(id);
    ayrikVideoTazele(id);
    listeCiz();
    return true;
  }
  function ayrikToggle(id) {
    if (ayrikler[id]) { ayrikKapat(id); listeCiz(); return; }
    ayrikAc(id);
  }
  // Harita/dron önizlemesi ve kamera paneli için tek güvenli giriş noktası.
  // Yalnız yerel kamera kimliği kullanır; kaynak URL veya kimlik bilgisi taşımaz.
  window.kameraIzlemeAc = function (kameraId) {
    const id = Number(kameraId);
    if (!Number.isFinite(id) || !kameralar.some((k) => Number(k.id) === id)) {
      return false;
    }
    oynat(id);
    hedefeGore(id);
    return true;
  };

  // v2.5.24: Canlı görüntüyü SEÇİLİ hedefte (yalnız orada) gösterir.
  function hedefeGore(id) {
    const h = hedef(id);
    // yüzen değilse açık pencereyi kapat
    if (!oynayanlar.has(id)) { listeCiz(); return; }
    ayrikAc(id);
    // 'panel' ve 'harita' listeCiz()/harita tazeleme ile çizilir
    listeCiz();
    if (typeof window.dronKameraHaritaOnizlemeTazele === "function")
      window.dronKameraHaritaOnizlemeTazele();
  }
  // Hedef değişince (seçiciden) uygula: oynatılmıyorsa başlat.
  window.kameraGoruntuHedefiUygula = function (id) {
    id = Number(id);
    if (!oynayanlar.has(id)) oynat(id);
    hedefeGore(id);
  };

  // --- Tam ekran hedefi ---
  let tamEkranId = null;
  function tamEkranKapat() {
    const el = document.getElementById("kamTamEkran");
    if (el) el.remove();
    tamEkranId = null;
  }
  function tamEkranAc(id) {
    const kamera = kameralar.find((k) => k.id === id);
    if (!kamera) return;
    if (tamEkranId === id && document.getElementById("kamTamEkran")) return;
    tamEkranKapat();
    tamEkranId = id;
    const t = T();
    const kap = document.createElement("div");
    kap.id = "kamTamEkran"; kap.className = "kam-tam-ekran";
    const bar = document.createElement("div");
    bar.className = "kam-tam-bar";
    const ad = document.createElement("span");
    ad.className = "kam-tam-ad";
    ad.innerHTML = "<i class='fa-solid fa-video'></i> " +
      String(kamera.isim || ("#" + id)).replace(/[<>&]/g, "");
    const sag = document.createElement("div");
    sag.className = "kam-tam-arac";
    if (typeof window.kameraAiAyarButonu === "function")
      sag.appendChild(window.kameraAiAyarButonu(id));
    if (kamera.protokol === "m50") {
      const bM50PanelTE = document.createElement("button");
      bM50PanelTE.className = "kam-btn";
      bM50PanelTE.title = t.kamM50Panel || "M50 PTZ / Lens Kontrolü";
      bM50PanelTE.innerHTML = "<i class='fa-solid fa-binoculars'></i>";
      bM50PanelTE.addEventListener("click", () => {
        if (typeof window.yuzenPanelAc === "function") window.yuzenPanelAc("yzM50");
      });
      sag.appendChild(bM50PanelTE);
    }
    if (typeof window.kameraGoruntuHedefSecici === "function")
      sag.appendChild(window.kameraGoruntuHedefSecici(id));
    const kapat = document.createElement("button");
    kapat.className = "kam-btn"; kapat.title = (t.kamStop || "Durdur");
    kapat.innerHTML = "<i class='fa-solid fa-xmark'></i>";
    kapat.addEventListener("click", () => { durdur(id); tamEkranKapat(); listeCiz(); });
    sag.appendChild(kapat);
    if (typeof window.kameraTakipAracAlani === "function")
      sag.prepend(window.kameraTakipAracAlani(id));
    bar.append(ad, sag);
    const kutu = document.createElement("div");
    kutu.className = "kam-video-kutu kam-tam-video";
    kutu.appendChild(videoOlustur(kamera));
    kap.append(bar, kutu);
    // v2.4.173: tam ekranda durum çubuğu altta yüzer
    if (typeof window.kameraTakipDurumCubugu === "function") {
      const dc = window.kameraTakipDurumCubugu(id);
      dc.style.position = "absolute";
      dc.style.bottom = "10px";
      dc.style.left = "50%";
      dc.style.transform = "translateX(-50%)";
      dc.style.width = "auto";
      dc.style.maxWidth = "92%";
      dc.style.zIndex = "6";
      kap.appendChild(dc);
    }
    document.body.appendChild(kap);
  }
  window.kameraTamEkranId = function () { return tamEkranId; };
  window.kameraIzlemeAktifMi = function (kameraId) {
    return oynayanlar.has(Number(kameraId));
  };
  window.kameraIzlemeDurdur = function (kameraId) {
    const id = Number(kameraId);
    if (ayrikler[id]) ayrikKapat(id);
    durdur(id);
  };
  function ayrikVideoTazele(id) {
    const kayit = ayrikler[id];
    if (!kayit) return;
    const kamera = kameralar.find((k) => k.id === id);
    if (!kamera) { ayrikKapat(id); return; }
    const t = T();
    kayit.kutu.innerHTML = "";
    kayit.altBar.innerHTML = "";
    if (oynayanlar.has(id)) {
      kayit.kutu.appendChild(videoOlustur(kamera));
    } else {
      const bos = document.createElement("div");
      bos.className = "kam-bos-onizleme";
      bos.innerHTML = "<i class='fa-solid fa-video-slash'></i>";
      kayit.kutu.appendChild(bos);
    }
    // Alt bar: play/stop + duzenle + sil
    kayit.altBar.appendChild(araclarOlustur(kamera));
    // v2.4.164: takip dugmeleri ("Hedef Seç" / "Görüntüye Angaje Ol")
    if (typeof window.kameraTakipAracAlani === "function")
      kayit.altBar.prepend(window.kameraTakipAracAlani(id));
    // v2.4.206: en alttaki durum cubugu = temel kamera bilgileri + takip
    // ipucu/teknik bilgi (v2.4.173 cubugu buraya tasindi).
    if (kayit.durumBar) {
      kayit.durumBar.innerHTML = "";
      kayit.durumBar.appendChild(temelBilgiSatiri(kamera, kayit.kutu));
      if (typeof window.kameraTakipDurumCubugu === "function")
        kayit.durumBar.appendChild(window.kameraTakipDurumCubugu(id));
    }
  }

  // v2.4.206: durum cubugu ust satiri — ad · protokol · cozunurluk · FPS
  // tavani · akis durumu. Cozunurluk ilk kare gelince (img load) yazilir.
  function temelBilgiSatiri(kamera, kutu) {
    const t = T();
    const el = document.createElement("div");
    el.className = "kam-temel-bilgi";
    const yaz = () => {
      const img = kutu.querySelector("img.kam-video, video.kam-video");
      const w = img ? (img.naturalWidth || img.videoWidth || 0) : 0;
      const h = img ? (img.naturalHeight || img.videoHeight || 0) : 0;
      const hata = kutu.classList.contains("kam-hata");
      const bagl = kutu.classList.contains("kam-baglaniyor");
      const durum = !oynayanlar.has(kamera.id) ? (t.kamDurumDurdu || "durduruldu") :
                    hata ? (t.kamDurumHata || "yayın alınamıyor") :
                    (bagl || !w) ? (t.kamDurumBaglaniyor || "bağlanıyor") : (t.kamDurumCanli || "canlı");
      const p = [kamera.isim || ("#" + kamera.id), String(kamera.protokol || "").toUpperCase()];
      if (w && h) p.push(w + "×" + h);
      p.push((t.kamFpsKisa || "FPS") + " ≤ " + (kamera.fps || 15));
      p.push(durum);
      el.textContent = p.join("  ·  ");
    };
    yaz();
    const img = kutu.querySelector("img.kam-video, video.kam-video");
    if (img) { img.addEventListener("load", yaz); img.addEventListener("loadedmetadata", yaz); }
    if (typeof MutationObserver !== "undefined")
      new MutationObserver(yaz).observe(kutu, { attributes: true, attributeFilter: ["class"] });
    return el;
  }

  function ayrikKapat(id) {
    const kayit = ayrikler[id];
    if (!kayit) return;
    kayit.pencere.remove();
    delete ayrikler[id];
  }

  function pencereSurukleKur(pencere, baslik, kamId) {
    let surukle = null;
    baslik.addEventListener("pointerdown", (ev) => {
      if (ev.target.closest("button")) return;
      const rect = pencere.getBoundingClientRect();
      surukle = { dx: ev.clientX - rect.left, dy: ev.clientY - rect.top };
      baslik.setPointerCapture(ev.pointerId);
      ev.preventDefault();
    });
    baslik.addEventListener("pointermove", (ev) => {
      if (!surukle) return;
      let x = ev.clientX - surukle.dx;
      let y = ev.clientY - surukle.dy;
      x = Math.max(0, Math.min(x, window.innerWidth - pencere.offsetWidth));
      y = Math.max(0, Math.min(y, window.innerHeight - 40));
      pencere.style.left = x + "px";
      pencere.style.top = y + "px";
    });
    const birak = (ev) => {
      if (!surukle) return;
      surukle = null;
      try { baslik.releasePointerCapture(ev.pointerId); } catch (e) {}
      // Konumu kalici kaydet
      if (kamId !== undefined && typeof window.pencereKonumKaydet === "function") {
        window.pencereKonumKaydet("kam_" + kamId, pencere);
      }
    };
    baslik.addEventListener("pointerup", birak);
    baslik.addEventListener("pointercancel", birak);
  }

  // ----------------------------------------------------------------
  // WS MESAJI: kamera listesi geldi
  // ----------------------------------------------------------------
  window.kameraListesiIsle = function (m) {
    kameralar = m.kameralar || [];
    window._kameralarSon = kameralar;
    // v2.4.206: M50 canli goruntu penceresi (ayri sistem) kayit/kanal degisimini izler
    if (typeof window.m50PencereKameraDegisti === "function") { try { window.m50PencereKameraDegisti(); } catch (e) {} }
    // v2.4.0: haritadaki kamera ikonlarini tazele
    if (typeof window.kameraHaritaTazele === "function")
      window.kameraHaritaTazele(kameralar);
    // v2.4.1: lokasyon listesindeki kamera sayisi rozetlerini tazele
    if (typeof window.lokasyonListeCiz === "function" && window._lokasyonlarSon)
      window.lokasyonListeCiz(window._lokasyonlarSon);
    // v2.4.2: dron paneli kamera bolumlerini tazele (dron_uid baglari)
    if (typeof window.dronKameraListesiTazele === "function")
      window.dronKameraListesiTazele();
    if (typeof window.dronKameraHaritaOnizlemeTazele === "function")
      window.dronKameraHaritaOnizlemeTazele();
    // Silinen kameralarin ayrik pencerelerini ve oynatmalarini temizle
    const idler = new Set(kameralar.map((k) => k.id));
    Object.keys(ayrikler).forEach((id) => {
      if (!idler.has(Number(id))) ayrikKapat(Number(id));
    });
    if (typeof tamEkranId !== "undefined" && tamEkranId !== null &&
        !idler.has(Number(tamEkranId))) tamEkranKapat();
    [...oynayanlar].forEach((id) => { if (!idler.has(id)) oynayanlar.delete(id); });
    listeCiz();
    // Acik ayrik pencerelerin basliklarini/videolarini tazele
    Object.keys(ayrikler).forEach((id) => ayrikVideoTazele(Number(id)));
  };

  // Dil degisiminde tooltipleri tazele
  window.kameraDilTazele = function () {
    gorunumIkonTazele();
    listeCiz();
    Object.keys(ayrikler).forEach((id) => ayrikVideoTazele(Number(id)));
    const t = T();
    const btnYeni = document.getElementById("tbYeniKamera");
    if (btnYeni) btnYeni.title = t.kamYeni || "Yeni Kamera";
    const btnVd = document.getElementById("tbVideoDuvar");
    if (btnVd) btnVd.title = t.kamVideoDuvar || "Video Duvarı (Ayrı Pencere)";
  };

  // v2.4.56: kopru listesi degisince (kopru cevrimdisi oldu, yenisi
  // katildi) gruplama ve form secicisi tazelenir.
  if (typeof window.kopruListesiDinle === "function") {
    window.kopruListesiDinle(function () {
      listeCiz();
      if (perde && !perde.classList.contains("popup-gizli") &&
          typeof window.kopruSeciciDoldur === "function") {
        const secili = kopruSec ? (kopruSec.value || null) : null;
        window.kopruSeciciDoldur(kopruAlan, kopruSec, secili);
      }
    });
  }

  gorunumIkonTazele();
})();
