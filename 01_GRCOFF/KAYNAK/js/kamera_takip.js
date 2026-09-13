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

  var KUTU_GECERLI_MS = 1500;
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
    kutular[id] = { ts: Date.now(), liste: Array.isArray(m.kutular) ? m.kutular : [] };
  };

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

  function doldur(kap) {
    var id = Number(kap.dataset.kameraId);
    var t = window.kameraTakipDurumu(id);
    kap.textContent = "";
    if (t && t.aktif) {
      var rozet = document.createElement("span");
      rozet.className = "kam-takip-rozet";
      rozet.textContent = "● TAKİPTE: " + (TUR_AD[t.sinif] || "HEDEF");
      rozet.title = t.hedef_id ? "Hedef konumu çözüldü" : ("Konum: " + (t.konum_gerekce || "bekleniyor"));
      var b = document.createElement("button");
      b.type = "button";
      b.className = "kam-takip-angaje";
      b.innerHTML = "<i class='fa-solid fa-crosshairs'></i><span>Görüntüye Angaje Ol</span>";
      b.addEventListener("click", function (ev) { ev.stopPropagation(); angajeAc(id); });
      kap.append(rozet, b);
    } else {
      var ip = document.createElement("span");
      ip.className = "kam-takip-ipucu";
      ip.textContent = "Takip için tespit kutusuna çift tıklayın";
      kap.appendChild(ip);
    }
  }

  function araclariTazele(id) {
    document.querySelectorAll(".kam-takip-arac" + (id != null ? "[data-kamera-id='" + Number(id) + "']" : ""))
      .forEach(doldur);
  }
  // Bayat takipler ve durum rozeti için periyodik tazeleme
  setInterval(function () {
    Object.keys(takip).forEach(function (k) {
      if (Date.now() - takip[k]._ts > TAKIP_BAYAT_MS * 3) { delete takip[k]; }
    });
    araclariTazele(null);
  }, 1000);

  function angajeAc(id) {
    var t = window.kameraTakipDurumu(id);
    if (!t || !t.aktif) { bildir(id, "Takip aktif değil"); return; }
    if (typeof window.angajmanPopupAc !== "function" && typeof angajmanPopupAc !== "function") return;
    var kam = kamBul(id) || {};
    var ac = window.angajmanPopupAc || angajmanPopupAc;
    ac("goruntu", t.hedef_id || ("yerel:" + id), {
      yerel: true, yuzen: true,
      kamera_id: id, kamera_ad: kam.isim || ("#" + id),
      kaynak_dron_uid: String(kam.dron_uid || ""),
      ad: "Takip: " + (TUR_AD[t.sinif] || "HEDEF") + " (" + (kam.isim || ("kamera #" + id)) + ")",
      iz_id: t.track_id || null
    });
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

  document.addEventListener("dblclick", function (ev) {
    var img = ev.target && ev.target.closest && ev.target.closest("img.kam-video[data-kamera-id]");
    if (!img) return;
    // Yalnız yüzen panel veya tam ekran (kullanıcı isteği)
    if (!img.closest(".kam-pencere") && !img.closest("#kamTamEkran")) return;
    ev.preventDefault();
    ev.stopPropagation();
    var id = Number(img.dataset.kameraId);

    // 1) Takip çerçevesine çift tık -> takibi bırak
    var t = window.kameraTakipDurumu(id);
    if (t && t.aktif && Array.isArray(t.kutu) && t.kutu.length === 4) {
      var kb = t.kare_boyutu || [];
      var nT = kaynakNoktasi(img, ev, kb[0], kb[1]);
      if (nT && icinde(nT, t.kutu[0], t.kutu[1], t.kutu[2], t.kutu[3])) {
        wsGonder({ tip: "ai_track_durdur", kamera_id: id });
        bildir(id, "Takip bırakılıyor…");
        return;
      }
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
               kutu: [Math.round(b.x), Math.round(b.y), Math.round(b.w), Math.round(b.h)] });
    bildir(id, "Takip başlatılıyor: " + TUR_AD[b.tur]);
  }, true);
})();
