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
  let gorunum = localStorage.getItem("kamGorunum") || "liste"; // liste|onizleme
  let duzenlenenId = null;       // modal duzenleme modundaki kamera id

  const listeKok = () => document.getElementById("kameraListesi");
  const T = () => (typeof D === "function" ? D() : {});

  // Offline Merkez canlı akışı, uygulamanın aynı origin'i üzerinden gelir.
  // Ayrı port veya cihaz Köprüsü gerekmez.
  function proxyUrl(id) {
    return window.location.origin + "/kamera/" + id + "?t=" + Date.now();
  }

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

  function protokolDegisti() {
    const prot = inProt.value;
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
    } else {
      cihazSatir.classList.add("gizli");
      if (djiSatir) djiSatir.classList.add("gizli");
      lblUrlSatir.classList.remove("gizli");
      inUrl.classList.remove("gizli");
    }
  }
  inProt.addEventListener("change", protokolDegisti);

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

  // v2.4.2: kamera basina AI gorev checkbox'lari
  const AI_GOREV_KUTULARI = ["kamAiYuz", "kamAiPlaka", "kamAiHava",
                             "kamAiInsan", "kamAiKara"];

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

  function modalAc(kamera) {
    const t = T();
    duzenlenenId = kamera ? kamera.id : null;
    inAd.value = kamera ? kamera.isim : "";
    inProt.value = kamera ? kamera.protokol : "rtsp";
    inUrl.value = kamera ? kamera.url : "";
    // v2.4.7: duzenlemede kayitli cihaz indeksi, liste gelince secilir
    if (kamera && kamera.protokol === "donanim" && cihazSec) {
      cihazSec.dataset.secili = kamera.url;
    }
    aiGorevleriDoldur(kamera ? kamera.ai_gorevler : "");
    // v2.4.0: lokasyon listesi yoksa sunucudan iste, combobox'i doldur
    if (!window._lokasyonlarSon) wsGonder({tip: "lokasyon_liste"});
    lokSecDoldur(kamera ? kamera.lokasyon_id : null);
    // v2.4.56: kopru secimi. Kamera akisi (RTSP/donanim/DJI) saha
    // makinesinde vardir; merkez sunucusu o adrese erisemez. Bu yuzden
    // merkezde hangi kopru uzerinden okunacagi secilmelidir.
    if (typeof window.kopruSeciciDoldur === "function")
      window.kopruSeciciDoldur(kopruAlan, kopruSec,
                               kamera ? kamera.kopru_ornek_id : null);
    hataEl.textContent = "";
    baslikEl.textContent = kamera
      ? (t.kamModalBaslikDuzenle || "KAMERAYI DÜZENLE")
      : (t.kamModalBaslikYeni || "YENİ KAMERA");
    protokolDegisti();
    perde.classList.remove("popup-gizli");
    setTimeout(() => inAd.focus(), 50);
  }

  function modalKapat() {
    perde.classList.add("popup-gizli");
    duzenlenenId = null;
  }

  function modalKaydet() {
    const t = T();
    const isim = inAd.value.trim();
    const prot = inProt.value;
    let url = inUrl.value.trim();
    if (!isim) { hataEl.textContent = t.kamHataAd || "Kamera ad\u0131 bo\u015f olamaz."; return; }
    if (prot === "donanim") {
      url = cihazSec.value || "";
      if (!url) { hataEl.textContent = t.kamHataCihaz || "Kamera cihaz\u0131 se\u00e7in."; return; }
    } else if (prot === "dji") {
      url = djiSec ? (djiSec.value || "") : "";
      if (!url) { hataEl.textContent = t.kamHataDji || "DJI dron se\u00e7in."; return; }
    } else {
      if (!url) { hataEl.textContent = t.kamHataUrl || "Yay\u0131n adresi bo\u015f olamaz."; return; }
    }
    // v2.4.56: merkezde kopru secimi zorunludur.
    const merkezde = (typeof window.kopruMerkezKipiMi === "function")
      && window.kopruMerkezKipiMi();
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
    if (duzenlenenId !== null) k.id = duzenlenenId;
    wsGonder(k);
    modalKapat();
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
  function gorunumIkonTazele() {
    const t = T();
    if (gorunum === "liste") {
      btnGorunum.innerHTML = "<i class='fa-solid fa-table-cells-large'></i>";
      btnGorunum.title = t.kamGorunumOnizleme || "Önizleme Görünümü";
    } else {
      btnGorunum.innerHTML = "<i class='fa-solid fa-list'></i>";
      btnGorunum.title = t.kamGorunumListe || "Liste Görünümü";
    }
  }
  btnGorunum.addEventListener("click", () => {
    gorunum = (gorunum === "liste") ? "onizleme" : "liste";
    localStorage.setItem("kamGorunum", gorunum);
    gorunumIkonTazele();
    listeCiz();
  });

  // ----------------------------------------------------------------
  // VIDEO ELEMANI OLUSTURMA / TEMIZLEME
  // ----------------------------------------------------------------
  // Donanim kamera stream'leri: deviceId -> MediaStream
  const donanimStreamler = {};

  function videoOlustur(kamera) {
    const prot = kamera.protokol;

    // v2.4.7: DONANIM da dahil tum MJPEG kaynaklari SUNUCU proxy'sinden
    // gelir — goruntu Python'da yakalanir, AI izleme aktifse tespit
    // cerceveleri + kisi/nesne adlari kare uzerine cizilmis olarak doner.
    // v2.4.10: HTTP video (MP4/WebM) da proxy'den gecer — AI anotasyonu
    // MP4 kaynaklarinda da gorunur (ffmpeg -re -stream_loop ile dongulu).
    if (prot === "rtsp" || prot === "rtp" || prot === "mjpeg" ||
        prot === "dji" || prot === "donanim" || prot === "http") {
      const img = document.createElement("img");
      img.className = "kam-video";
      img.draggable = false;
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
                kam.protokol === "donanim" || kam.protokol === "http")) {
      // Sunucudaki FFmpeg/yakalama surecini serbest birak
      wsGonder({ tip: "kamera_proxy_durdur", id: id });
    }
  }

  // ----------------------------------------------------------------
  // PLAY / STOP
  // ----------------------------------------------------------------
  function oynat(id) {
    oynayanlar.add(id);
    listeCiz();
    // Ayrik penceredeyse onu da tazele
    if (ayrikler[id]) ayrikVideoTazele(id);
  }

  function durdur(id) {
    oynayanlar.delete(id);
    videoTemizle(id);
    listeCiz();
    if (ayrikler[id]) ayrikVideoTazele(id);
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
      oynuyor ? durdur(kamera.id) : oynat(kamera.id);
    });

    const bAyir = document.createElement("button");
    bAyir.className = "kam-btn";
    bAyir.title = ayrikler[kamera.id]
      ? (t.kamYerlestir || "Panele Yerleştir") : (t.kamAyir || "Ayrı Pencere");
    bAyir.innerHTML = ayrikler[kamera.id]
      ? "<i class='fa-solid fa-down-left-and-up-right-to-center'></i>"
      : "<i class='fa-solid fa-up-right-from-square'></i>";
    bAyir.addEventListener("click", (e) => {
      e.stopPropagation();
      ayrikToggle(kamera.id);
    });

    const bDuzenle = document.createElement("button");
    bDuzenle.className = "kam-btn";
    bDuzenle.title = t.kamDuzenle || "Düzenle";
    bDuzenle.innerHTML = "<i class='fa-solid fa-pen'></i>";
    bDuzenle.addEventListener("click", (e) => {
      e.stopPropagation();
      modalAc(kamera);
    });

    const bSil = document.createElement("button");
    bSil.className = "kam-btn kam-btn-sil";
    bSil.title = t.kamSil || "Sil";
    bSil.innerHTML = "<i class='fa-solid fa-trash'></i>";
    bSil.addEventListener("click", (e) => {
      e.stopPropagation();
      onayIste(onayMetni("onayKameraSil", {ad: kamera.isim || kamera.id}), () => {
        durdur(kamera.id);
        ayrikKapat(kamera.id);
        wsGonder({ tip: "kamera_sil", id: kamera.id });
      });
    });

    kutu.append(bPlay, bAyir, bDuzenle, bSil);
    return kutu;
  }

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
    satir.append(sol, araclarOlustur(kamera));

    // Liste gorunumunde oynayan kameranin videosu satirin altinda gosterilir
    if (oynayanlar.has(kamera.id) && !ayrikler[kamera.id]) {
      const kutu = document.createElement("div");
      kutu.className = "kam-video-kutu";
      kutu.appendChild(videoOlustur(kamera));
      const dis = document.createElement("div");
      dis.className = "kam-blok";
      dis.append(satir, kutu);
      return dis;
    }
    return satir;
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
    if (oynayanlar.has(kamera.id)) {
      kutu.appendChild(videoOlustur(kamera));
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
    const panelKameralari = kameralar.filter((k) => !ayrikler[k.id]);
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
    const ayrikSayi = kameralar.length - panelKameralari.length;
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
    if (bosKutu) bosKutu.classList.toggle("gizli", kameralar.length > 0);
  }

  // ----------------------------------------------------------------
  // AYRIK (TASINABILIR) VIDEO PENCERESI
  // ----------------------------------------------------------------
  function ayrikToggle(id) {
    if (ayrikler[id]) { ayrikKapat(id); listeCiz(); return; }
    const kamera = kameralar.find((k) => k.id === id);
    if (!kamera) return;
    const t = T();

    const pencere = document.createElement("div");
    pencere.className = "kam-pencere";

    const baslik = document.createElement("div");
    baslik.className = "kam-pencere-baslik";
    const ad = document.createElement("span");
    ad.innerHTML = "<i class='fa-solid fa-video'></i> " + kamera.isim;
    const btnKapat = document.createElement("button");
    btnKapat.className = "kam-btn";
    btnKapat.title = t.kamYerlestir || "Panele Yerleştir";
    btnKapat.innerHTML = "<i class='fa-solid fa-down-left-and-up-right-to-center'></i>";
    btnKapat.addEventListener("click", () => { ayrikKapat(id); listeCiz(); });
    baslik.append(ad, btnKapat);

    const kutu = document.createElement("div");
    kutu.className = "kam-video-kutu kam-pencere-video";

    const altBar = document.createElement("div");
    altBar.className = "kam-pencere-alt";

    pencere.append(baslik, kutu, altBar);
        document.body.appendChild(pencere);
    // Kayitli konum/boyut varsa oradan ac (boyut video kutusuna uygulanir)
    const kayitVar = typeof window.pencereKonumUygula === "function" &&
                     window.pencereKonumUygula("kam_" + id, pencere);
    if (!kayitVar) {
      pencere.style.left = Math.max(8, (window.innerWidth - 480) / 2 +
        (Object.keys(ayrikler).length * 30)) + "px";
      pencere.style.top = Math.max(8, 90 +
        (Object.keys(ayrikler).length * 30)) + "px";
    }
    if (typeof window.pencereKonumUygula === "function") {
      window.pencereKonumUygula("kam_" + id + "_video", kutu, true);
      kutu.style.left = ""; kutu.style.top = ""; kutu.style.right = "";
    }
    ayrikler[id] = { pencere: pencere, kutu: kutu, altBar: altBar };
    pencereSurukleKur(pencere, baslik, id);
    // Video kutusu elle boyutlandirilinca (CSS resize) boyutu kaydet
    if (typeof ResizeObserver !== "undefined" &&
        typeof window.pencereKonumKaydet === "function") {
      let ilk = true;
      const ro = new ResizeObserver(() => {
        if (ilk) { ilk = false; return; } // ilk tetikleme (acilis) atlanir
        window.pencereKonumKaydet("kam_" + id + "_video", kutu, true);
      });
      ro.observe(kutu);
    }
    if (!oynayanlar.has(id)) oynayanlar.add(id);
    ayrikVideoTazele(id);
    listeCiz();
  }

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
    // v2.4.0: haritadaki kamera ikonlarini tazele
    if (typeof window.kameraHaritaTazele === "function")
      window.kameraHaritaTazele(kameralar);
    // v2.4.1: lokasyon listesindeki kamera sayisi rozetlerini tazele
    if (typeof window.lokasyonListeCiz === "function" && window._lokasyonlarSon)
      window.lokasyonListeCiz(window._lokasyonlarSon);
    // v2.4.2: dron paneli kamera bolumlerini tazele (dron_uid baglari)
    if (typeof window.dronKameraListesiTazele === "function")
      window.dronKameraListesiTazele();
    // Silinen kameralarin ayrik pencerelerini ve oynatmalarini temizle
    const idler = new Set(kameralar.map((k) => k.id));
    Object.keys(ayrikler).forEach((id) => {
      if (!idler.has(Number(id))) ayrikKapat(Number(id));
    });
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
