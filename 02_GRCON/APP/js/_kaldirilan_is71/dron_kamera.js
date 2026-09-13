// ================================================================
// DRON KAMERA (v2.4.2): dron kartinin en altinda kamera secimi ve
// gomulu kamera izleme.
//  - "Kamera Sec" dugmesi: bosta (lokasyona veya baska drona bagli
//    olmayan) kameralari listeleyen kucuk popup acar.
//  - Kamera secilince dron kartinin altinda gomulu izleme alani
//    gosterilir ve kamera_dron_bagla WS komutu ile bag kaydedilir.
//  - Gomulu izleme alanina tiklaninca goruntu ayri popup'a alinir.
//  - Ayri popup kapatilinca goruntu baglantisina gore geri doner:
//      dron_uid dolu   -> dron panelindeki gomulu alana
//      lokasyon_id var -> lokasyon kameralari popup'ina
//      hicbiri yok     -> Kameralar paneline
// ================================================================
(function () {
  "use strict";

  const T = () => (typeof D === "function" ? D() : {});

  function wsGonder(obj) {
    if (typeof ws !== "undefined" && ws && ws.readyState === 1)
      ws.send(JSON.stringify(obj));
  }

  // Video proxy adresi (kameralar.js ile ayni kalip)
  function proxyUrl(id) {
    // FAZ19-IS60B: AYNI ORIGIN. Eskiden 8801 portlu mutlak adres
    // kullaniliyordu; merkez kipinde o port DINLENMIYOR ve sayfa
    // https iken adres http oldugundan tarayici karisik icerigi
    // engelliyordu (ERR_CONNECTION_TIMED_OUT). `/tile/` karo
    // vekili ayni sorunu coktan cozmus; video ayni yolu izler.
    //
    // `goktunguYol` DOGRUDAN cagrilmaz: video.html harita.js'i
    // yuklemiyor, orada tanimsiz olur ve ReferenceError video
    // duvarini tamamen kirardi. Varsa kullanilir, yoksa AYNI
    // formul yerinde hesaplanir.
    var tb = window.GOKTUNGU_TABAN ||
      ((location.pathname || "/").replace(/[^/]*$/, "") || "/");
    return tb + "kamera/" + id + "?t=" + Date.now();
  }

  // sysid -> {kutu, secBtn, izlemeKutu, video, kamId, popup}
  const kayitlar = {};
  let secimPopup = null;   // acik kamera secim popup'i {kok, sysid}

  function kameralar() { return window._kameralarSon || []; }

  // Dronun kalici kimligi: donanim UID varsa o, yoksa "sysid:N"
  function dronUid(d) {
    return (d && d.uid) ? String(d.uid) : ("sysid:" + (d ? d.sysid : "?"));
  }

  function dronaBagliKamera(uid) {
    return kameralar().find(k => (k.dron_uid || "") === uid) || null;
  }

  // Bosta kamera: lokasyona bagli degil VE hicbir drona bagli degil
  function bostaKameralar() {
    return kameralar().filter(k => !k.lokasyon_id && !(k.dron_uid || ""));
  }

  // ----------------------------------------------------------------
  // Video elementi (kameralar.js videoOlustur'un sade kopyasi)
  // ----------------------------------------------------------------
  function videoOlustur(kamera) {
    const prot = kamera.protokol;
    // v2.4.7: donanim + mjpeg dahil tum MJPEG kaynaklari sunucu
    // proxy'sinden gelir (AI aktifse tespit cerceveli anotasyonlu kare)
    if (prot === "rtsp" || prot === "rtp" || prot === "mjpeg" ||
        prot === "dji" || prot === "donanim" || prot === "http") {
      // v2.4.10: http (MP4/WebM) da proxy'den - AI anotasyonlu
      const img = document.createElement("img");
      img.className = "dk-kam-video";
      img.draggable = false;
      // v2.4.33: dayanikli yukleme (bkz. BULGU_MJPEG.md)
      if (typeof window.mjpegBagla === "function") {
        window.mjpegBagla(img, () => proxyUrl(kamera.id), ".dk-kam-izleme");
      } else {
        img.src = proxyUrl(kamera.id);
        img.addEventListener("error", () => {
          img.closest(".dk-kam-izleme")?.classList.add("kam-hata");
        });
      }
      return img;
    }
    // hls / http
    const video = document.createElement("video");
    video.className = "dk-kam-video";
    video.autoplay = true; video.muted = true; video.playsInline = true;
    if (prot === "hls" && window.Hls && Hls.isSupported()) {
      const h = new Hls({ lowLatencyMode: true });
      h.loadSource(kamera.url); h.attachMedia(video);
    } else {
      video.src = kamera.url;
    }
    video.addEventListener("error", () => {
      video.closest(".dk-kam-izleme")?.classList.add("kam-hata");
    });
    return video;
  }

  function videoDurdur(kutu, kamera) {
    // donanim stream'i kapat + rtsp/rtp proxy'yi durdur
    const video = kutu.querySelector("video");
    if (video && video.srcObject) {
      try { video.srcObject.getTracks().forEach(t => t.stop()); } catch (e) {}
      video.srcObject = null;
    }
    if (kamera && (kamera.protokol === "rtsp" || kamera.protokol === "rtp" ||
                   kamera.protokol === "dji" || kamera.protokol === "mjpeg" ||
                   kamera.protokol === "donanim")) {
      wsGonder({ tip: "kamera_proxy_durdur", id: kamera.id });
    }
    kutu.innerHTML = "";
  }

  // ----------------------------------------------------------------
  // KAMERA SECIM POPUP'I: bosta kameralar listesi
  // ----------------------------------------------------------------
  function secimPopupKapat() {
    if (!secimPopup) return;
    try { secimPopup.kok.remove(); } catch (e) {}
    secimPopup = null;
  }

  function secimPopupAc(sysid, dron, ekranX, ekranY) {
    const t = T();
    if (secimPopup && secimPopup.sysid === sysid) { secimPopupKapat(); return; }
    secimPopupKapat();
    const kok = document.createElement("div");
    kok.className = "dk-kamsec-popup";
    const baslik = document.createElement("div");
    baslik.className = "dk-kamsec-baslik";
    baslik.innerHTML = "<span><i class='fa-solid fa-video'></i> " +
      (t.dkKamSecBaslik || "Kamera Se\u00e7") + "</span>";
    const btnKapat = document.createElement("button");
    btnKapat.innerHTML = "<i class='fa-solid fa-xmark'></i>";
    btnKapat.addEventListener("click", (e) => {
      e.stopPropagation(); secimPopupKapat();
    });
    baslik.appendChild(btnKapat);
    const liste = document.createElement("div");
    liste.className = "dk-kamsec-liste";
    const bosta = bostaKameralar();
    if (!bosta.length) {
      const bos = document.createElement("div");
      bos.className = "dk-kamsec-bos";
      bos.textContent = t.dkKamSecBos ||
        "Bo\u015fta kamera yok (lokasyona veya drona ba\u011fl\u0131 olmayan)";
      liste.appendChild(bos);
    } else {
      for (const k of bosta) {
        const satir = document.createElement("div");
        satir.className = "dk-kamsec-satir";
        satir.innerHTML = "<i class='fa-solid fa-video'></i>" +
          "<span class='dk-kamsec-ad'>" + (k.isim || ("Kamera " + k.id)) +
          "</span><span class='dk-kamsec-prot'>" +
          (k.protokol || "").toUpperCase() + "</span>";
        satir.addEventListener("click", () => {
          secimPopupKapat();
          wsGonder({ tip: "kamera_dron_bagla", id: k.id,
                     dron_uid: dronUid(dron) });
        });
        liste.appendChild(satir);
      }
    }
    kok.append(baslik, liste);
    document.body.appendChild(kok);
    // Konum: dugmenin yakininda, ekran disina tasmadan
    const W = 260, H = Math.min(300, 60 + bosta.length * 34);
    let x = ekranX - W / 2, y = ekranY - H - 12;
    if (y < 52) y = ekranY + 12;
    x = Math.max(8, Math.min(x, window.innerWidth - W - 8));
    kok.style.left = x + "px";
    kok.style.top = y + "px";
    secimPopup = { kok, sysid };
  }

  // Dis tiklama: secim popup'ini kapat
  document.addEventListener("pointerdown", (e) => {
    if (secimPopup && !secimPopup.kok.contains(e.target) &&
        !e.target.closest(".dk-kam-sec-btn"))
      secimPopupKapat();
  });

  // ----------------------------------------------------------------
  // AYRI POPUP: gomulu izlemeden ayrilan kamera penceresi
  // ----------------------------------------------------------------
  const ayrikPencereler = {};  // kamId -> {pencere, kutu, kamera}

  function ayrikAc(kamera) {
    if (ayrikPencereler[kamera.id]) {
      if (typeof window.pencereEnUsteGetir === "function")
        window.pencereEnUsteGetir(ayrikPencereler[kamera.id].pencere);
      return;
    }
    const t = T();
    const pencere = document.createElement("div");
    pencere.className = "kam-pencere";
    const baslik = document.createElement("div");
    baslik.className = "kam-pencere-baslik";
    const ad = document.createElement("span");
    ad.innerHTML = "<i class='fa-solid fa-video'></i> " +
      (kamera.isim || ("Kamera " + kamera.id));
    const btnKapat = document.createElement("button");
    btnKapat.className = "kam-btn";
    btnKapat.title = t.btnKapat || "Kapat";
    btnKapat.innerHTML = "<i class='fa-solid fa-xmark'></i>";
    btnKapat.addEventListener("click", () => ayrikKapatYonlendir(kamera.id));
    baslik.append(ad, btnKapat);
    const kutu = document.createElement("div");
    kutu.className = "kam-video-kutu kam-pencere-video";
    kutu.appendChild(videoOlustur(kamera));
    pencere.append(baslik, kutu);
    document.body.appendChild(pencere);
    // Konum: kayitli varsa oradan, yoksa ortada
    const kayitVar = typeof window.pencereKonumUygula === "function" &&
                     window.pencereKonumUygula("dkam_" + kamera.id, pencere);
    if (!kayitVar) {
      pencere.style.left = Math.max(8, (window.innerWidth - 480) / 2) + "px";
      pencere.style.top = "100px";
    }
    // Surukleme (basit): baslik ile tasi
    let surukle = null;
    baslik.addEventListener("pointerdown", (ev) => {
      if (ev.target.closest("button")) return;
      const r = pencere.getBoundingClientRect();
      surukle = { dx: ev.clientX - r.left, dy: ev.clientY - r.top };
      baslik.setPointerCapture(ev.pointerId);
      ev.preventDefault();
      if (typeof window.pencereEnUsteGetir === "function")
        window.pencereEnUsteGetir(pencere);
    });
    baslik.addEventListener("pointermove", (ev) => {
      if (!surukle) return;
      const x = Math.max(0, Math.min(ev.clientX - surukle.dx,
        window.innerWidth - pencere.offsetWidth));
      const y = Math.max(48, Math.min(ev.clientY - surukle.dy,
        window.innerHeight - 40));
      pencere.style.left = x + "px"; pencere.style.top = y + "px";
    });
    baslik.addEventListener("pointerup", (ev) => {
      if (!surukle) return;
      surukle = null;
      try { baslik.releasePointerCapture(ev.pointerId); } catch (e) {}
      if (typeof window.pencereKonumKaydet === "function")
        window.pencereKonumKaydet("dkam_" + kamera.id, pencere);
    });
    ayrikPencereler[kamera.id] = { pencere, kutu, kamera };
  }

  // Ayri popup kapatildiginda: baglantiya gore geri yonlendir
  function ayrikKapatYonlendir(kamId) {
    const kayit = ayrikPencereler[kamId];
    if (!kayit) return;
    videoDurdur(kayit.kutu, kayit.kamera);
    kayit.pencere.remove();
    delete ayrikPencereler[kamId];
    // Guncel kamera kaydini al (bag degismis olabilir)
    const kamera = kameralar().find(k => k.id === kamId) || kayit.kamera;
    const uid = kamera.dron_uid || "";
    if (uid) {
      // 1) Drona bagli -> dron panelindeki gomulu alana geri don
      for (const sysid in kayitlar) {
        const r = kayitlar[sysid];
        if (r && r.uid === uid) { gomuluIzlemeTazele(sysid); return; }
      }
      tazeleHepsi();
    } else if (kamera.lokasyon_id) {
      // 2) Lokasyona bagli -> lokasyon kameralari popup'i
      if (typeof window.lokasyonKameralariAc === "function")
        window.lokasyonKameralariAc(kamera.lokasyon_id,
          window.innerWidth / 2, window.innerHeight / 3);
    } else {
      // 3) Bagsiz -> Kameralar panelini ac
      if (typeof window.bolumGorunumAyarla === "function")
        window.bolumGorunumAyarla("kameralar", true);
    }
  }

  // ----------------------------------------------------------------
  // DRON KARTI KAMERA BOLUMU
  // ----------------------------------------------------------------
  // dronlar.js kart olustururken cagirir: govde sonuna eklenir
  window.dronKameraBolumuKur = function (sysid, govde) {
    if (kayitlar[sysid]) return kayitlar[sysid].kutu;
    const t = T();
    const kutu = document.createElement("div");
    kutu.className = "dk-kam-bolum";
    // Kamera Sec dugmesi
    const secBtn = document.createElement("button");
    secBtn.type = "button";
    secBtn.className = "dk-kam-sec-btn";
    secBtn.innerHTML = "<i class='fa-solid fa-video'></i> <span>" +
      (t.dkKamSec || "Kamera Se\u00e7") + "</span>";
    secBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const d = (typeof sonVeri !== "undefined" ? sonVeri : {})[sysid];
      const r = secBtn.getBoundingClientRect();
      secimPopupAc(sysid, d, r.left + r.width / 2, r.top);
    });
    // Gomulu izleme alani (kamera baglaninca gorunur)
    const izlemeKutu = document.createElement("div");
    izlemeKutu.className = "dk-kam-izleme gizli";
    izlemeKutu.title = t.dkKamAyir || "Ayr\u0131 pencerede a\u00e7";
    izlemeKutu.addEventListener("click", () => {
      const r = kayitlar[sysid];
      if (!r || !r.kamera) return;
      // Gomulu izlemeyi durdur, ayri popup'a al
      videoDurdur(izlemeKutu, r.kamera);
      izlemeKutu.classList.add("gizli");
      r.izleniyor = false;
      ayrikAc(r.kamera);
    });
    // Tespit seridi: bagli kameradan gelen aktif AI tespitleri
    const tespitSerit = document.createElement("div");
    tespitSerit.className = "dk-tespit-serit gizli";
    const tespitBaslik = document.createElement("div");
    tespitBaslik.className = "dk-tespit-baslik";
    tespitBaslik.innerHTML =
      "<i class='fa-solid fa-crosshairs'></i> " +
      (t.dkTespitBaslik || "AKT\u0130F TESP\u0130TLER");
    const tespitAkis = document.createElement("div");
    tespitAkis.className = "dk-tespit-akis";
    // Mouse tekerlegi ile yatay kaydirma (touch zaten dogal calisir)
    tespitAkis.addEventListener("wheel", (ev) => {
      if (ev.deltaY) { tespitAkis.scrollLeft += ev.deltaY; ev.preventDefault(); }
    }, { passive: false });
    tespitSerit.append(tespitBaslik, tespitAkis);
    kutu.append(secBtn, izlemeKutu, tespitSerit);
    govde.appendChild(kutu);
    kayitlar[sysid] = { kutu, secBtn, izlemeKutu, kamera: null,
                        uid: null, izleniyor: false,
                        tespitSerit, tespitAkis, tespitler: [] };
    return kutu;
  };

  // Kart guncellenince dronlar.js cagirir (uid teslimi + tazeleme)
  window.dronKameraTazele = function (sysid, d) {
    const r = kayitlar[sysid];
    if (!r) return;
    const uid = dronUid(d);
    if (r.uid !== uid) { r.uid = uid; gomuluIzlemeTazele(sysid); }
  };

  // Dron karti silinince temizlik
  window.dronKameraKaldir = function (sysid) {
    const r = kayitlar[sysid];
    if (!r) return;
    if (r.kamera && r.izleniyor) videoDurdur(r.izlemeKutu, r.kamera);
    delete kayitlar[sysid];
  };

  function gomuluIzlemeTazele(sysid) {
    const r = kayitlar[sysid];
    if (!r || !r.uid) return;
    const t = T();
    const kamera = dronaBagliKamera(r.uid);
    // Ayri popup'ta aciksa gomulu alani bos tut
    if (kamera && ayrikPencereler[kamera.id]) {
      r.kamera = kamera;
      return;
    }
    if (!kamera) {
      // Bag cozulmus: izlemeyi kapat, dugmeyi sifirla
      if (r.kamera && r.izleniyor) videoDurdur(r.izlemeKutu, r.kamera);
      r.kamera = null; r.izleniyor = false;
      r.izlemeKutu.classList.add("gizli");
      r.secBtn.innerHTML = "<i class='fa-solid fa-video'></i> <span>" +
        (t.dkKamSec || "Kamera Se\u00e7") + "</span>";
      r.secBtn.classList.remove("bagli");
      return;
    }
    if (r.kamera && r.kamera.id === kamera.id && r.izleniyor) {
      r.kamera = kamera;  // kayit guncel kalsin
      return;             // zaten izleniyor
    }
    // Yeni kamera baglandi -> gomulu izlemeyi baslat
    if (r.kamera && r.izleniyor) videoDurdur(r.izlemeKutu, r.kamera);
    r.kamera = kamera;
    r.izleniyor = true;
    r.izlemeKutu.innerHTML = "";
    r.izlemeKutu.classList.remove("gizli", "kam-hata");
    // Ust bilgi cubugu: kamera adi + bagi coz dugmesi
    const bar = document.createElement("div");
    bar.className = "dk-kam-bar";
    const adEl = document.createElement("span");
    adEl.innerHTML = "<i class='fa-solid fa-video'></i> " +
      (kamera.isim || ("Kamera " + kamera.id));
    const btnCoz = document.createElement("button");
    btnCoz.title = t.dkKamCoz || "Kameray\u0131 ay\u0131r";
    btnCoz.innerHTML = "<i class='fa-solid fa-link-slash'></i>";
    btnCoz.addEventListener("click", (e) => {
      e.stopPropagation();
      wsGonder({ tip: "kamera_dron_bagla", id: kamera.id, dron_uid: "" });
    });
    bar.append(adEl, btnCoz);
    r.izlemeKutu.append(bar, videoOlustur(kamera));
    // Dugme etiketi: bagli kamera adi
    r.secBtn.innerHTML = "<i class='fa-solid fa-video'></i> <span>" +
      (kamera.isim || ("Kamera " + kamera.id)) + "</span>";
    r.secBtn.classList.add("bagli");
  }

  function tazeleHepsi() {
    for (const sysid in kayitlar) gomuluIzlemeTazele(sysid);
  }

  // Kamera listesi degisince (kamera_listesi duyurusu) tazele
  window.dronKameraListesiTazele = tazeleHepsi;

  // ----------------------------------------------------------------
  // TESPIT SERIDI: bagli kameradan gelen aktif AI tespitleri
  // ----------------------------------------------------------------
  const TESPIT_LIMIT = 20;      // dron basina tutulan son tespit sayisi
  const TESPIT_OMUR_SN = 120;   // bu sureden eski tespitler dusurulur

  function tespitTurAd(tur) {
    if (typeof window.aiTurAdi === "function") return window.aiTurAdi(tur);
    const t = T();
    const m = { yuz: t.aiTurYuz || "Y\u00fcz", plaka: t.aiTurPlaka || "Plaka",
                hava_araci: t.aiTurHava || "Hava Arac\u0131",
                insan: t.aiTurInsan || "\u0130nsan",
                kara_araci: t.aiTurKara || "Kara Arac\u0131" };
    return m[tur] || tur;
  }

  function tespitIkon(tur) {
    const m = { yuz: "fa-user", plaka: "fa-car-rear",
                hava_araci: "fa-plane-up", insan: "fa-person",
                kara_araci: "fa-truck" };
    return m[tur] || "fa-eye";
  }

  function tespitSeritCiz(sysid) {
    const r = kayitlar[sysid];
    if (!r || !r.tespitAkis) return;
    const t = T();
    const simdi = Date.now() / 1000;
    r.tespitler = r.tespitler.filter(tp =>
      (simdi - (tp.ts || simdi)) < TESPIT_OMUR_SN);
    r.tespitAkis.innerHTML = "";
    if (!r.tespitler.length) { r.tespitSerit.classList.add("gizli"); return; }
    r.tespitSerit.classList.remove("gizli");
    for (const tp of r.tespitler) {
      const ad = tp.kisi_ad || tp.arac_plaka || tp.etiket ||
                 (t.aiBilinmiyor || "Bilinmiyor");
      const kart = document.createElement("div");
      kart.className = "dk-tespit-kart" +
        (tp.seviye === "araniyor" ? " araniyor" : "");
      const foto = tp.foto ? "<img src='/" + tp.foto + "' alt=''>" :
        "<span class='dk-tespit-ikon'><i class='fa-solid " +
        tespitIkon(tp.tur) + "'></i></span>";
      kart.innerHTML = foto +
        "<div class='dk-tespit-ad'>" + ad + "</div>" +
        "<div class='dk-tespit-tur'>" + tespitTurAd(tp.tur) + "</div>";
      kart.title = t.dkAngajeIpucu || "Angaje olmak i\u00e7in t\u0131klay\u0131n";
      kart.addEventListener("click", () => angajeOnay(sysid, tp));
      r.tespitAkis.appendChild(kart);
    }
  }

  // Angaje onayi + tracking baslatma
  function angajeOnay(sysid, tp) {
    const t = T();
    const ad = tp.kisi_ad || tp.arac_plaka || tp.etiket ||
               (t.aiBilinmiyor || "Bilinmiyor");
    const mesaj = (t.dkAngajeOnay ||
      "Angaje olmak istedi\u011finize emin misiniz?") +
      "\n\n" + tespitTurAd(tp.tur) + ": " + ad;
    if (!window.confirm(mesaj)) return;
    wsGonder({
      tip: "ai_track_baslat",
      tespit_id: tp.id || 0,
      kamera_id: tp.kamera_id || 0,
      sysid: Number(sysid),
      tur: tp.tur || "",
      kutu: tp.kutu || null,
    });
  }

  // v2.4.2: takip baslatma sonucu + canli takip durumu (ws.js'ten)
  window.dronTakipIsle = function (m) {
    const t = T();
    if (m.tip === "ai_takip_sonuc") {
      if (m.tamam) {
        if (typeof konsolYaz === "function")
          konsolYaz("AI", (t.dkTakipBasladi ||
            "Hedef takibi ba\u015flad\u0131, dron angaje oluyor") +
            " (K" + m.kamera_id + ")", "basari");
      } else {
        alert((t.dkTakipHata || "Takip ba\u015flat\u0131lamad\u0131:") +
          " " + (m.hata || ""));
      }
      return;
    }
    // canli takip durumu (ai_takip): kayip bildirimi
    if (m.kayip && typeof konsolYaz === "function")
      konsolYaz("AI", (t.dkTakipKayip ||
        "Hedef takibi kaybedildi") + " (K" + m.kamera_id + ")", "uyari");
  };

  // Canli tespit duyurusu (ws.js ai_tespit -> ai_panel.js zincirinden):
  // bagli kameranin tespitlerini ilgili dron seridine ekle
  window.dronTespitIsle = function (m) {
    if (!m || !m.kamera_id) return;
    for (const sysid in kayitlar) {
      const r = kayitlar[sysid];
      if (!r || !r.kamera || r.kamera.id !== m.kamera_id) continue;
      r.tespitler.unshift({
        id: m.id, ts: m.ts || (Date.now() / 1000),
        kamera_id: m.kamera_id, tur: m.tur, etiket: m.etiket,
        seviye: m.seviye, foto: m.foto, klip: m.klip,
        kisi_ad: m.kisi_ad, arac_plaka: m.arac_plaka, kutu: m.kutu,
      });
      if (r.tespitler.length > TESPIT_LIMIT)
        r.tespitler.length = TESPIT_LIMIT;
      tespitSeritCiz(sysid);
      return;
    }
  };
})();
