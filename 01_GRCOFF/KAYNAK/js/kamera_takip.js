/* ====================================================================
 * GRCOFF 2.5.34 — Videoda ÇİFT TIKLA TAKİP + GÖRÜNTÜYE ANGAJE OL
 *
 * Kullanıcı isteği:
 *   - Yüzen panel veya tam ekrandayken tespit edilen hedefe çift tıklayınca
 *     takip başlasın; takip çerçevesi kırmızı olsun (sunucu videoya çizer).
 *   - Takip çerçevesine tekrar çift tıklayınca takip bırakılsın.
 *   - Takipteyken panelde "Görüntüye Angaje Ol" düğmesi çıksın; basınca
 *     angajman ayarları + dron seçimi YÜZEN panelde açılsın, "Başlat" seçili
 *     dronla yerel görüntü angajmanını başlatsın.
 *
 * Veri: sunucu `ai_kutular` (canlı tespit kutuları, kaynak pikselde +
 * kaynak_w/kaynak_h) ve `ai_takip` (takip kutusu, kare_boyutu, çözülen
 * hedef kimliği/konumu) yayınlar. Hedef konumu SUNUCUDA çözülür: kamera
 * drona takılıysa o dronun telemetrisiyle, sabit kameraysa kalibrasyonla.
 * Bu modül uçuş komutu üretmez; angajmanı mevcut onaylı yola devreder.
 * ================================================================== */
(function () {
  "use strict";

  // v2.4.169: YOLO cikarimi yavas CPU'da saniyeler surebilir; cift tik
  // hedef secim penceresi son kutu yayinini o kadar sure gecerli sayar.
  var KUTU_GECERLI_MS = 6000;
  var TAKIP_BAYAT_MS = 3000;
  var kutular = {};   // kamera_id -> {ts, liste:[{x,y,w,h,tur,etiket,kaynak_w,kaynak_h}]}
  var takip = {};     // kamera_id -> son ai_takip mesajı (+ _ts)

  var TUR_AD = { hava_araci: "HAVA ARACI" };

  function wsGonder(o) {
    try {
      if (typeof ws !== "undefined" && ws && ws.readyState === 1) {
        ws.send(JSON.stringify(o)); return true;
      }
    } catch (_) {}
    return false;
  }
  function kamBul(id) {
    id = Number(id);
    return (window._kameralarSon || []).find(function (k) { return Number(k.id) === id; }) || null;
  }

  // ---- sunucu mesajları ----------------------------------------------
  window.kameraAiKutularIsle = function (m) {
    var id = Number(m && m.kamera_id);
    if (!isFinite(id)) return;
    kutular[id] = { ts: Date.now(), liste: Array.isArray(m.kutular) ? m.kutular : [],
                    durum: (m && m.durum) || null };
  };

  // v2.4.171: dedektor/GPU/fps durum rozeti metni
  var SAGLAYICI_AD = {
    DmlExecutionProvider: "DirectML GPU",
    CUDAExecutionProvider: "CUDA GPU",
    CPUExecutionProvider: "CPU"
  };
  function durumMetni(id) {
    var k = kutular[Number(id)];
    if (!k || !k.durum || Date.now() - k.ts > 8000) return "";
    var d = k.durum;
    var p = [];
    p.push(d.dedektor || "?");
    if (d.saglayici) p.push(SAGLAYICI_AD[d.saglayici] || d.saglayici);
    else if (d.dedektor === "MOG2" || d.dedektor === "YOLO") p.push("CPU");
    if (d.cikarim_ms > 0) p.push("çıkarım " + (d.cikarim_ms >= 1000
      ? (d.cikarim_ms / 1000).toFixed(1) + " sn" : d.cikarim_ms + " ms"));
    if (d.analiz_hz > 0) p.push("tespit " + d.analiz_hz + " Hz");
    if (d.video_fps > 0) p.push("video " + d.video_fps + " fps");
    return p.join(" · ");
  }

  window.kameraTakipIsle = function (m) {
    var id = Number(m && m.kamera_id);
    if (!isFinite(id)) return;
    if (m.tip === "ai_takip_sonuc") {
      if (!m.tamam) bildir(id, "Takip başlatılamadı: " + (m.hata || "bilinmeyen hata"));
      return;
    }
    var onceki = takip[id];
    if (m.aktif) {
      takip[id] = Object.assign({}, m, { _ts: Date.now() });
      if (!onceki || !onceki.aktif) bildir(id, "Takip başladı: " + (TUR_AD[m.sinif] || m.sinif || "hedef"));
    } else {
      if (onceki && onceki.aktif) bildir(id, m.kayip ? "Hedef kayboldu — takip sona erdi" : "Takip bırakıldı");
      delete takip[id];
    }
    araclariTazele(id);
  };

  window.kameraTakipDurumu = function (id) {
    var t = takip[Number(id)];
    if (!t) return null;
    return Object.assign({}, t, { aktif: !!t.aktif && Date.now() - t._ts < TAKIP_BAYAT_MS });
  };

  // ---- panel araç alanı ----------------------------------------------
  window.kameraTakipAracAlani = function (id) {
    var kap = document.createElement("span");
    kap.className = "kam-takip-arac";
    kap.dataset.kameraId = String(id);
    doldur(kap);
    return kap;
  };

  // v2.4.173: Arac alani YALNIZ dugme tasir (yerlesim bozulmasin);
  // ipucu, durum metni ve teknik bilgiler DURUM ÇUBUĞUNDA (aşağıda).
  function doldur(kap) {
    var id = Number(kap.dataset.kameraId);
    var t = window.kameraTakipDurumu(id);
    kap.textContent = "";
    kap.style.cssText = "display:inline-flex;align-items:center;gap:6px;flex-wrap:wrap;";
    if (t && t.aktif) {
      // v2.4.173: "Görüntüye Angaje Ol" (çarp) + "Takip Et" (mesafeyi
      // koru, çarpma) — ikisi de aynı pasif piksel takibini kullanır.
      var bAngaje = document.createElement("button");
      bAngaje.type = "button";
      bAngaje.className = "kam-takip-angaje";
      bAngaje.innerHTML = "<i class='fa-solid fa-crosshairs'></i><span>Angaje Ol</span>";
      bAngaje.addEventListener("click", function (ev) { ev.stopPropagation(); angajeAc(id, false); });
      var bTakip = document.createElement("button");
      bTakip.type = "button";
      bTakip.className = "kam-takip-angaje kam-takip-mesafe";
      bTakip.innerHTML = "<i class='fa-solid fa-satellite-dish'></i><span>Takip Et</span>";
      bTakip.addEventListener("click", function (ev) { ev.stopPropagation(); angajeAc(id, true); });
      // v2.4.173: acik "Takibi Birak" dugmesi (cift tik + ESC'ye ek)
      var birak = document.createElement("button");
      birak.type = "button";
      birak.className = "kam-takip-angaje kam-takip-birak";
      birak.title = "Piksel takibini bırak (ESC)";
      birak.innerHTML = "<i class='fa-solid fa-xmark'></i><span>Bırak</span>";
      birak.addEventListener("click", function (ev) {
        ev.stopPropagation(); takipBirak(id);
      });
      kap.append(bAngaje, bTakip, birak);
    } else {
      // v2.4.172: elle hedef secimi — videoya dikdortgen ciz, takip baslasin
      var sec = document.createElement("button");
      sec.type = "button";
      sec.className = "kam-takip-angaje kam-hedef-sec";
      sec.innerHTML = secim[id]
        ? "<i class='fa-solid fa-xmark'></i><span>Seçimi İptal</span>"
        : "<i class='fa-solid fa-vector-square'></i><span>Hedef Seç</span>";
      sec.addEventListener("click", function (ev) {
        ev.stopPropagation(); hedefSecBaslat(id);
      });
      kap.appendChild(sec);
    }
    // v2.4.173: ucus-seviyesinde (dron havada gerçekten yöneliyor) aktif
    // angajman/takip varsa, piksel-takip durumundan BAĞIMSIZ "Durdur"
    // düğmesi — kamera panelinden ayrı izleme popup'ı açmadan durdurulur.
    var ucus = (typeof window.angajmanKameraDurumu === "function")
      ? window.angajmanKameraDurumu(id) : null;
    if (ucus) {
      var bDurdur = document.createElement("button");
      bDurdur.type = "button";
      bDurdur.className = "kam-takip-angaje kam-ucus-durdur";
      bDurdur.title = "D" + ucus.sysid + " " +
        (ucus.mod === "takip" ? "takibini" : "angajmanını") + " durdur";
      bDurdur.innerHTML = "<i class='fa-solid fa-stop'></i><span>" +
        (ucus.mod === "takip" ? "Takibi Durdur" : "Angajmanı Durdur") + "</span>";
      bDurdur.addEventListener("click", function (ev) {
        ev.stopPropagation(); ucusDurdur(id);
      });
      kap.appendChild(bDurdur);
    }
  }

  // ---- v2.4.173: ALT DURUM ÇUBUĞU (ipucu + teknik bilgi) --------------
  window.kameraTakipDurumCubugu = function (id) {
    var el = document.createElement("div");
    el.className = "kam-takip-durumcubuk";
    el.dataset.kameraId = String(id);
    el.style.cssText = "display:flex;align-items:center;" +
      "justify-content:space-between;gap:12px;flex-wrap:wrap;" +
      "padding:3px 10px;font-size:11.5px;line-height:1.5;min-height:22px;" +
      "background:rgba(0,0,0,.40);color:#e8e8e8;border-radius:4px;" +
      "font-variant-numeric:tabular-nums;width:100%;box-sizing:border-box;";
    durumCubukDoldur(el);
    return el;
  };

  function durumCubukDoldur(el) {
    var id = Number(el.dataset.kameraId);
    var t = window.kameraTakipDurumu(id);
    var sol;
    if (secim[id]) {
      sol = "Hedefin üzerine dikdörtgen çizin — ESC iptal";
    } else if (t && t.aktif) {
      sol = "● TAKİPTE: " + (TUR_AD[t.sinif] || "HEDEF") +
        (t.hedef_id ? " · konum çözüldü"
                    : " · konum: " + (t.konum_gerekce || "bekleniyor"));
    } else {
      sol = "Takip: tespit kutusuna çift tıklayın veya Hedef Seç ile çizin";
    }
    // v2.4.173: ucus-seviyesi angajman/takip durumu (mesafe/ETA)
    var ucus = (typeof window.angajmanKameraDurumu === "function")
      ? window.angajmanKameraDurumu(id) : null;
    if (ucus) {
      sol += "  ▸  D" + ucus.sysid + " " +
        (ucus.mod === "takip" ? "TAKİP EDİYOR" : "ANGAJE") +
        (ucus.mesafe != null ? " · " + Math.round(ucus.mesafe) + " m" : "") +
        (ucus.mod === "takip" && ucus.takip_mesafe
          ? " (hedef " + Math.round(ucus.takip_mesafe) + " m)" : "") +
        (ucus.eta_sn != null && ucus.mod !== "takip"
          ? " · ETA " + Math.round(ucus.eta_sn) + " sn" : "");
    }
    el.textContent = "";
    var s1 = document.createElement("span");
    s1.textContent = sol;
    var s2 = document.createElement("span");
    s2.style.cssText = "opacity:.85;white-space:nowrap;";
    var dm = durumMetni(id);
    if (dm) {
      var gpuMu = /GPU/.test(dm);
      s2.innerHTML = "<i class='fa-solid fa-microchip' style='margin-right:5px;" +
        (gpuMu ? "color:#4caf50" : "color:#ff9800") + "'></i>";
      s2.appendChild(document.createTextNode(dm));
    }
    el.append(s1, s2);
  }

  function araclariTazele(id) {
    var sec = (id != null ? "[data-kamera-id='" + Number(id) + "']" : "");
    document.querySelectorAll(".kam-takip-arac" + sec).forEach(doldur);
    document.querySelectorAll(".kam-takip-durumcubuk" + sec)
      .forEach(durumCubukDoldur);
  }
  // v2.4.173: angajman_izle.js her telemetri karesinde bunu cagirir
  window.kameraTakipDurumTazele = function () { araclariTazele(null); };
  // Bayat takipler ve durum rozeti için periyodik tazeleme
  setInterval(function () {
    Object.keys(takip).forEach(function (k) {
      if (Date.now() - takip[k]._ts > TAKIP_BAYAT_MS * 3) { delete takip[k]; }
    });
    araclariTazele(null);
  }, 1000);

  // v2.4.173: `takipModu=true` -> "Takip Et" (mesafeyi koru, çarpma);
  // false -> "Görüntüye Angaje Ol" (hedefe tam hızda yönel).
  function angajeAc(id, takipModu) {
    var t = window.kameraTakipDurumu(id);
    if (!t || !t.aktif) { bildir(id, "Takip aktif değil"); return; }
    if (typeof window.angajmanPopupAc !== "function" && typeof angajmanPopupAc !== "function") return;
    var kam = kamBul(id) || {};
    var ac = window.angajmanPopupAc || angajmanPopupAc;
    ac("goruntu", t.hedef_id || ("yerel:" + id), {
      yerel: true, yuzen: true, takip_modu: !!takipModu,
      kamera_id: id, kamera_ad: kam.isim || ("#" + id),
      kaynak_dron_uid: String(kam.dron_uid || ""),
      ad: (takipModu ? "Takip: " : "Angaje: ") +
        (TUR_AD[t.sinif] || "HEDEF") + " (" + (kam.isim || ("kamera #" + id)) + ")",
      iz_id: t.track_id || null
    });
  }

  // v2.4.173: bu kameranin hedefine su an ucus-seviyesinde angaje/takipte
  // olan dronu bulup angajmani durdurur (ayri IZLEME popup'ini acmadan).
  function ucusDurdur(id) {
    if (typeof window.angajmanKameraDurumu !== "function") return;
    var d = window.angajmanKameraDurumu(id);
    if (!d) { bildir(id, "Bu hedefe yönelen aktif angajman/takip yok"); return; }
    var fn = window.angajmanIptalGonder ||
      (typeof angajmanIptalGonder === "function" ? angajmanIptalGonder : null);
    if (!fn) return;
    fn(d.sysid);
    bildir(id, "D" + d.sysid + " " + (d.mod === "takip" ? "takibi" : "angajmanı") + " durduruluyor…");
  }

  // ---- v2.4.172: elle hedef seçimi (dikdörtgen çiz -> takip) ----------
  var secim = {};   // kamera_id -> {ort, img, bas:{x,y}|null, _esc}

  // İstemci (ekran) koordinatını kaynak (doğal) piksele çevirir.
  // Tarayıcı <img> ve AI işçisi AYNI proxy MJPEG akışını okur; doğal
  // boyut = işçinin kare boyutu, kutu doğrudan takibe verilebilir.
  function kaynakXY(img, cx, cy) {
    var r = img.getBoundingClientRect();
    var nw = img.naturalWidth, nh = img.naturalHeight;
    if (!nw || !nh || !r.width || !r.height) return null;
    var olcek = Math.min(r.width / nw, r.height / nh);
    var gw = nw * olcek, gh = nh * olcek;
    var ox = (r.width - gw) / 2, oy = (r.height - gh) / 2;
    var px = (cx - r.left - ox) / olcek;
    var py = (cy - r.top - oy) / olcek;
    return { x: Math.max(0, Math.min(nw, px)),
             y: Math.max(0, Math.min(nh, py)) };
  }

  function hedefSecBaslat(id) {
    id = Number(id);
    if (secim[id]) { secimIptal(id); return; }   // ikinci basış = iptal
    var img = document.querySelector(
      ".kam-pencere img.kam-video[data-kamera-id='" + id + "'], " +
      "#kamTamEkran img.kam-video[data-kamera-id='" + id + "']");
    if (!img) {
      bildir(id, "Hedef seçimi için videoyu yüzen panelde veya tam ekranda açın");
      return;
    }
    var kap = img.closest(".kam-video-kutu") || img.parentElement;
    if (getComputedStyle(kap).position === "static")
      kap.style.position = "relative";
    var ort = document.createElement("div");
    ort.className = "kam-hedef-sec-ortu";
    ort.style.cssText = "position:absolute;inset:0;cursor:crosshair;" +
      "z-index:40;background:rgba(0,0,0,.10);user-select:none;";
    var cerceve = document.createElement("div");
    cerceve.style.cssText = "position:absolute;border:2px dashed #ff5252;" +
      "background:rgba(255,82,82,.12);display:none;pointer-events:none;";
    var uyari = document.createElement("div");
    uyari.style.cssText = "position:absolute;top:6px;left:50%;" +
      "transform:translateX(-50%);background:rgba(0,0,0,.65);color:#fff;" +
      "padding:2px 10px;border-radius:4px;font-size:12px;pointer-events:none;" +
      "white-space:nowrap;";
    uyari.textContent = "Hedefin üzerine dikdörtgen çizin — ESC iptal";
    ort.append(cerceve, uyari);
    kap.appendChild(ort);
    var s = { ort: ort, img: img, bas: null };
    secim[id] = s;

    function yerel(ev) {
      var r = ort.getBoundingClientRect();
      return { x: ev.clientX - r.left, y: ev.clientY - r.top,
               cx: ev.clientX, cy: ev.clientY };
    }
    function ciz(a, b) {
      cerceve.style.display = "block";
      cerceve.style.left = Math.min(a.x, b.x) + "px";
      cerceve.style.top = Math.min(a.y, b.y) + "px";
      cerceve.style.width = Math.abs(a.x - b.x) + "px";
      cerceve.style.height = Math.abs(a.y - b.y) + "px";
    }
    ort.addEventListener("mousedown", function (ev) {
      ev.preventDefault(); ev.stopPropagation();
      s.bas = yerel(ev); ciz(s.bas, s.bas);
    });
    ort.addEventListener("mousemove", function (ev) {
      if (s.bas) ciz(s.bas, yerel(ev));
    });
    ort.addEventListener("mouseleave", function () {
      s.bas = null; cerceve.style.display = "none";
    });
    ort.addEventListener("mouseup", function (ev) {
      ev.preventDefault(); ev.stopPropagation();
      if (!s.bas) return;
      var bas = s.bas, son = yerel(ev);
      s.bas = null;
      secimIptal(id);
      var p1 = kaynakXY(img, bas.cx, bas.cy);
      var p2 = kaynakXY(img, son.cx, son.cy);
      if (!p1 || !p2) { bildir(id, "Video karesi hazır değil"); return; }
      var x = Math.round(Math.min(p1.x, p2.x));
      var y = Math.round(Math.min(p1.y, p2.y));
      var w = Math.round(Math.abs(p1.x - p2.x));
      var h = Math.round(Math.abs(p1.y - p2.y));
      if (w < 8 || h < 8) {
        bildir(id, "Seçim çok küçük — hedefi saracak bir dikdörtgen çizin");
        return;
      }
      if (!wsGonder({ tip: "ai_track_baslat", kamera_id: id,
                      tur: "hava_araci", kutu: [x, y, w, h],
                      ts: Date.now() / 1000 })) {
        bildir(id, "Sunucu bağlantısı yok");
        return;
      }
      bildir(id, "Takip başlatılıyor: seçilen bölge (" + w + "×" + h + " px)");
    });
    s._esc = function (ev) { if (ev.key === "Escape") secimIptal(id); };
    document.addEventListener("keydown", s._esc);
    araclariTazele(id);
  }

  function secimIptal(id) {
    var s = secim[Number(id)];
    if (!s) return;
    try { s.ort.remove(); } catch (e) {}
    if (s._esc) document.removeEventListener("keydown", s._esc);
    delete secim[Number(id)];
    araclariTazele(id);
  }

  // ---- kısa bildirim video üzerinde ------------------------------------
  function bildir(id, metin) {
    document.querySelectorAll("img.kam-video[data-kamera-id='" + Number(id) + "']").forEach(function (img) {
      var kutu = img.closest(".kam-video-kutu");
      if (!kutu) return;
      if (getComputedStyle(kutu).position === "static") kutu.style.position = "relative";
      var e = kutu.querySelector(".kam-takip-bildirim");
      if (!e) { e = document.createElement("div"); e.className = "kam-takip-bildirim"; kutu.appendChild(e); }
      e.textContent = metin;
      clearTimeout(e._z);
      e._z = setTimeout(function () { e.remove(); }, 2500);
    });
  }

  // ---- çift tık: koordinat çevirimi + isabet ---------------------------
  // <img> object-fit: contain -> görünen içerik dikdörtgeni
  function kaynakNoktasi(img, ev, kaynakW, kaynakH) {
    var r = img.getBoundingClientRect();
    var nw = img.naturalWidth, nh = img.naturalHeight;
    if (!nw || !nh || !r.width || !r.height) return null;
    var olcek = Math.min(r.width / nw, r.height / nh);
    var gw = nw * olcek, gh = nh * olcek;
    var ox = (r.width - gw) / 2, oy = (r.height - gh) / 2;
    var px = (ev.clientX - r.left - ox) / olcek;   // doğal piksel
    var py = (ev.clientY - r.top - oy) / olcek;
    if (px < 0 || py < 0 || px > nw || py > nh) return null;
    var kw = kaynakW || nw, kh = kaynakH || nh;
    return { x: px * kw / nw, y: py * kh / nh, tol: 14 / olcek * (kw / nw) };
  }

  function icinde(n, x, y, w, h) {
    return n.x >= x - n.tol && n.x <= x + w + n.tol && n.y >= y - n.tol && n.y <= y + h + n.tol;
  }

  function takipBirak(id) {
    wsGonder({ tip: "ai_track_durdur", kamera_id: Number(id) });
    bildir(id, "Takip bırakılıyor…");
  }

  // v2.4.173: ESC — önce seçim modunu, yoksa görünür kameradaki takibi bırakır
  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "Escape") return;
    var ids = Object.keys(secim);
    if (ids.length) { ids.forEach(secimIptal); return; }
    document.querySelectorAll(
      ".kam-pencere img.kam-video[data-kamera-id]," +
      "#kamTamEkran img.kam-video[data-kamera-id]").forEach(function (img) {
      var id = Number(img.dataset.kameraId);
      var t = window.kameraTakipDurumu(id);
      if (t && t.aktif) takipBirak(id);
    });
  });

  document.addEventListener("dblclick", function (ev) {
    var img = ev.target && ev.target.closest && ev.target.closest("img.kam-video[data-kamera-id]");
    if (!img) return;
    // Yalnız yüzen panel veya tam ekran (kullanıcı isteği)
    if (!img.closest(".kam-pencere") && !img.closest("#kamTamEkran")) return;
    ev.preventDefault();
    ev.stopPropagation();
    var id = Number(img.dataset.kameraId);

    // 1) Takipteyken videoya çift tık (HER YERDE) -> takibi bırak.
    //    v2.4.173: eskiden yalnız çerçevenin içi bırakıyordu; hızlı hedefte
    //    çerçeve tıklanana kadar kayıyor ve bırakma tutmuyordu.
    var t = window.kameraTakipDurumu(id);
    if (t && t.aktif) {
      takipBirak(id);
      return;
    }

    // 2) Tespit kutusuna çift tık -> takibi başlat (en küçük isabet)
    var k = kutular[id];
    if (!k || Date.now() - k.ts > KUTU_GECERLI_MS || !k.liste.length) {
      bildir(id, "Tespit edilmiş hedef yok — AI izlemesi açık mı?");
      return;
    }
    var aday = null;
    k.liste.forEach(function (b) {
      if (!TUR_AD[b.tur]) return;           // yalnız takip edilebilir sınıflar
      var n = kaynakNoktasi(img, ev, b.kaynak_w, b.kaynak_h);
      if (!n || !icinde(n, +b.x, +b.y, +b.w, +b.h)) return;
      var alan = b.w * b.h;
      if (!aday || alan < aday.alan) aday = { b: b, alan: alan };
    });
    if (!aday) { bildir(id, "Tıklanan yerde hedef yok — kutunun üzerine çift tıklayın"); return; }
    var b = aday.b;
    wsGonder({ tip: "ai_track_baslat", kamera_id: id, tur: b.tur,
               kutu: [Math.round(b.x), Math.round(b.y), Math.round(b.w), Math.round(b.h)],
               ts: Date.now() / 1000 });
    bildir(id, "Takip başlatılıyor: " + TUR_AD[b.tur]);
  }, true);
})();
