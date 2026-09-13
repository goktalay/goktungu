// =================================================================
// GOKTUNGU - SÜRÜ UÇUŞ (v2.4.3)
// =================================================================
// Dronlar menüsü → Sürü Uçuş: master/slave seçimi, XYZ ofset girişi,
// 3B formasyon izleme popup'ı (canvas), gerçek zamanlı mesafe tablosu,
// sürüyü dağıt / tek çıkar.
// =================================================================

(function () {
  "use strict";

  // --- Çeviri yardımcısı ---
  function t(k) { return (typeof D === "function") ? (D()[k] || k) : k; }

  // --- WS gönder ---
  function wsGonder(m) {
    if (typeof ws !== "undefined" && ws && ws.readyState === 1)
      ws.send(JSON.stringify(m));
  }

  // --- Dron listesi (sonVeri global'inden) ---
  function bagliDronlar() {
    if (typeof sonVeri === "undefined") return [];
    return Object.values(sonVeri).filter(d => d.baglanti);
  }

  // ===================================================================
  // KURULUM POPUP'I
  // ===================================================================
  let kurulumEl = null;
  let masterSelect = null;
  let slaveListeEl = null;
  let slaveler = []; // [{sysid, x, y, z}]

  function kurulumAc() {
    if (kurulumEl) { kurulumEl.remove(); kurulumEl = null; }
    slaveler = [];

    kurulumEl = document.createElement("div");
    kurulumEl.className = "suru-popup suru-kurulum";
    kurulumEl.innerHTML = `
      <div class="suru-baslik popup-baslik">
        <i class="fa-solid fa-layer-group"></i> ${t("suruBaslik")}
        <button class="suru-kapat"><i class="fa-solid fa-xmark"></i></button>
      </div>
      <!-- FAZ18/IS7: SLAVE EKLE ve SURUYU BASLAT govdenin altindan
           ust bara tasindi (Baglanti Yoneticisi/Kameralar deseni). -->
      <div class="panel-toolbar" id="suruToolbar">
        <!-- FAZ18-PANEL-ISKELET: ust bar sozlesmesi - ikonsuz,
             pencere basligindan FARKLI metin. -->
        <span class="tb-etiket">${t("suruUstBar")}</span>
        <span class="tb-bosluk"></span>
        <button class="suru-btn suru-btn-ekle tb-btn tb-btn-metin" id="suruSlaveEkleBtn">
          <i class="fa-solid fa-plus"></i><span>${t("suruSlaveEkle")}
        </span></button>
        <button class="suru-btn suru-btn-baslat tb-btn tb-btn-metin" id="suruBaslatBtn">
          <i class="fa-solid fa-play"></i><span>${t("suruBaslat")}
        </span></button>
      </div>
      <div class="suru-icerik">
        <label class="suru-lbl">${t("suruMaster")}</label>
        <select class="suru-select" id="suruMasterSec"></select>
        <label class="suru-lbl">${t("suruSlaveler")}</label>
        <div class="suru-slave-liste" id="suruSlaveListesi"></div>
      </div>`;
    document.body.appendChild(kurulumEl);

    // Taşınabilir
    const baslik = kurulumEl.querySelector(".suru-baslik");
    if (typeof popupTasinabilirYap === "function")
      popupTasinabilirYap(kurulumEl, baslik, "suruKurulum");
    if (typeof window.popupBoyutlandirilabilirYap === "function")
      window.popupBoyutlandirilabilirYap(kurulumEl, "suruKurulum");

    // Kapat
    baslik.querySelector(".suru-kapat").addEventListener("click", () => {
      kurulumEl.remove(); kurulumEl = null;
    });

    // Master select doldur
    masterSelect = kurulumEl.querySelector("#suruMasterSec");
    slaveListeEl = kurulumEl.querySelector("#suruSlaveListesi");
    _masterDoldur();

    // Slave ekle
    kurulumEl.querySelector("#suruSlaveEkleBtn")
      .addEventListener("click", _slaveEklePopup);

    // Başlat
    kurulumEl.querySelector("#suruBaslatBtn")
      .addEventListener("click", _suruBaslat);
  }

  /* BULGU_10c GUVENLIK (2026-08-17): HTML kacirma yardimcisi.

   * `app/js` altinda kacirma yardimcisi YOKTU (merkez panellerinde

   * `kacir()` var). Bu yuzden kullanicinin yazdigi dron adi

   * (`kullanici_isim`) `innerHTML` uzerinden ham basiliyordu:

   *   <option value="1"><img src=x onerror=alert(1)></option>

   * calisirdi. Somuru firma ici ve kimlik dogrulamali (saldirgan once

   * dron adi yazmali, sonra kurban suru panelini acmali) ama pilot ->

   * yonetici ayricalik yukseltmesi saglar.

   */

  function _kacir(s) {

    return String(s == null ? "" : s)

      .replace(/&/g, "&amp;")

      .replace(/</g, "&lt;")

      .replace(/>/g, "&gt;")

      .replace(/"/g, "&quot;")

      .replace(/'/g, "&#39;");

  }


  function _masterDoldur() {
    const dronlar = bagliDronlar();
    masterSelect.innerHTML = dronlar.map(d =>
      `<option value="${d.sysid}">${_kacir(d.kullanici_isim || d.isim || "D" + d.sysid)}</option>`
    ).join("");
  }

  function _slaveListeCiz() {
    slaveListeEl.innerHTML = slaveler.map((s, i) => {
      const d = (typeof sonVeri !== "undefined") ? sonVeri[s.sysid] : null;
      const ad = d ? (d.kullanici_isim || d.isim || "D" + s.sysid) : "D" + s.sysid;
      return `<div class="suru-slave-satir">
        <span class="suru-slave-ad">${ad}</span>
        <span class="suru-slave-xyz">X:${s.x} Y:${s.y} Z:${s.z}</span>
        <button class="suru-slave-sil" data-idx="${i}"><i class="fa-solid fa-trash"></i></button>
      </div>`;
    }).join("");
    slaveListeEl.querySelectorAll(".suru-slave-sil").forEach(btn => {
      btn.addEventListener("click", () => {
        slaveler.splice(+btn.dataset.idx, 1);
        _slaveListeCiz();
      });
    });
  }

  // --- Slave Ekle Mini Popup ---
  function _slaveEklePopup() {
    const mevcut = document.querySelector(".suru-slave-ekle-popup");
    if (mevcut) mevcut.remove();

    const masterSysid = +(masterSelect.value || 0);
    const dronlar = bagliDronlar().filter(d =>
      d.sysid !== masterSysid && !slaveler.find(s => s.sysid === d.sysid));

    const pop = document.createElement("div");
    pop.className = "suru-popup suru-slave-ekle-popup";
    pop.innerHTML = `
      <div class="suru-baslik popup-baslik">
        <i class="fa-solid fa-user-plus"></i> ${t("suruSlaveEkle")}
        <button class="suru-kapat"><i class="fa-solid fa-xmark"></i></button>
      </div>
      <div class="suru-icerik">
        <label class="suru-lbl">${t("suruDronSec")}</label>
        <select class="suru-select" id="suruSlaveDronSec">
          ${dronlar.map(d => `<option value="${d.sysid}">${_kacir(d.kullanici_isim || d.isim || "D" + d.sysid)}</option>`).join("")}
        </select>
        <div class="suru-xyz-grup">
          <label>X (${t("suruIleri")})<input type="number" id="suruSlaveX" value="0" step="1"></label>
          <label>Y (${t("suruSag")})<input type="number" id="suruSlaveY" value="10" step="1"></label>
          <label>Z (${t("suruYukari")})<input type="number" id="suruSlaveZ" value="0" step="1"></label>
        </div>
        <button class="suru-btn suru-btn-onayla" id="suruSlaveOnaylaBtn">
          <i class="fa-solid fa-check"></i><span>${t("suruEkle")}
        </span></button>
      </div>`;
    document.body.appendChild(pop);

    const baslik = pop.querySelector(".suru-baslik");
    if (typeof popupTasinabilirYap === "function")
      popupTasinabilirYap(pop, baslik, "suruSlaveEkle");
    baslik.querySelector(".suru-kapat").addEventListener("click", () => pop.remove());

    pop.querySelector("#suruSlaveOnaylaBtn").addEventListener("click", () => {
      const sid = +(pop.querySelector("#suruSlaveDronSec").value || 0);
      if (!sid) return;
      slaveler.push({
        sysid: sid,
        x: +(pop.querySelector("#suruSlaveX").value || 0),
        y: +(pop.querySelector("#suruSlaveY").value || 0),
        z: +(pop.querySelector("#suruSlaveZ").value || 0),
      });
      pop.remove();
      _slaveListeCiz();
    });
  }

  // --- Sürüyü Başlat ---
  function _suruBaslat() {
    const masterSysid = +(masterSelect.value || 0);
    if (!masterSysid) return alert(t("suruMasterSec"));
    if (slaveler.length === 0) return alert(t("suruSlaveGerekli"));
    wsGonder({
      tip: "suru_kur",
      master_sysid: masterSysid,
      slaves: slaveler.map(s => ({
        sysid: s.sysid, x: s.x, y: s.y, z: s.z
      }))
    });
    // Kurulum popup'ını kapat, izleme popup'ını aç
    if (kurulumEl) { kurulumEl.remove(); kurulumEl = null; }
    izlemeAc();
  }

  // ===================================================================
  // İZLEME POPUP'I (3B formasyon + mesafe tablosu)
  // ===================================================================
  let izlemeEl = null;
  let canvasEl = null;
  let ctx = null;
  let suruVeri = null; // telemetriden gelen sürü durumu
  let kameraAci = { yaw: 45, pitch: 30, zoom: 1.0 };
  let surukBaslangic = null;

  function izlemeAc() {
    if (izlemeEl) { izlemeEl.remove(); izlemeEl = null; }

    izlemeEl = document.createElement("div");
    izlemeEl.className = "suru-popup suru-izleme";
    izlemeEl.innerHTML = `
      <div class="suru-baslik popup-baslik">
        <i class="fa-solid fa-cubes"></i> ${t("suruIzlemeBaslik")}
        <button class="suru-kapat"><i class="fa-solid fa-xmark"></i></button>
      </div>
      <div class="suru-izleme-govde">
        <canvas class="suru-canvas" id="suruCanvas" width="480" height="360"></canvas>
        <div class="suru-mesafe-tablo" id="suruMesafeTablo"></div>
        <div class="suru-izleme-kontrol">
          <button class="suru-btn suru-btn-dagit" id="suruDagitBtn">
            <i class="fa-solid fa-ban"></i><span>${t("suruDagit")}
          </span></button>
        </div>
      </div>`;
    document.body.appendChild(izlemeEl);

    const baslik = izlemeEl.querySelector(".suru-baslik");
    if (typeof popupTasinabilirYap === "function")
      popupTasinabilirYap(izlemeEl, baslik, "suruIzleme");
    if (typeof window.popupBoyutlandirilabilirYap === "function")
      window.popupBoyutlandirilabilirYap(izlemeEl, "suruIzleme");
    baslik.querySelector(".suru-kapat").addEventListener("click", () => {
      izlemeEl.remove(); izlemeEl = null;
    });

    canvasEl = izlemeEl.querySelector("#suruCanvas");
    ctx = canvasEl.getContext("2d");

    // Kamera döndürme (fare sürükleme)
    canvasEl.addEventListener("mousedown", e => {
      surukBaslangic = { x: e.clientX, y: e.clientY, yaw: kameraAci.yaw, pitch: kameraAci.pitch };
    });
    document.addEventListener("mousemove", e => {
      if (!surukBaslangic) return;
      kameraAci.yaw = surukBaslangic.yaw + (e.clientX - surukBaslangic.x) * 0.5;
      kameraAci.pitch = Math.max(5, Math.min(85,
        surukBaslangic.pitch + (surukBaslangic.y - e.clientY) * 0.5));
    });
    document.addEventListener("mouseup", () => { surukBaslangic = null; });

    // Zoom (wheel)
    canvasEl.addEventListener("wheel", e => {
      e.preventDefault();
      kameraAci.zoom = Math.max(0.3, Math.min(4.0,
        kameraAci.zoom + (e.deltaY > 0 ? -0.1 : 0.1)));
    });

    // Dağıt düğmesi
    izlemeEl.querySelector("#suruDagitBtn").addEventListener("click", () => {
      if (confirm(t("suruOnayDagit"))) {
        wsGonder({ tip: "suru_dagit" });
      }
    });
  }

  // --- 3B projeksiyon (basit izometrik) ---
  function _proje(x, y, z) {
    // x=ileri, y=sağ, z=yukarı → ekran (px, py)
    const rad = Math.PI / 180;
    const cy = Math.cos(kameraAci.yaw * rad);
    const sy = Math.sin(kameraAci.yaw * rad);
    const cp = Math.cos(kameraAci.pitch * rad);
    const sp = Math.sin(kameraAci.pitch * rad);
    // Döndür
    const rx = x * cy - y * sy;
    const ry = x * sy + y * cy;
    const rz = z;
    // Perspektif (basit)
    const px = rx * kameraAci.zoom;
    const py = -(rz * cp - ry * sp) * kameraAci.zoom;
    return { px, py };
  }

  // --- Canvas çiz ---
  function _canvasCiz() {
    if (!ctx || !canvasEl) return;
    const W = canvasEl.width;
    const H = canvasEl.height;
    const cx = W / 2;
    const cy = H / 2;
    ctx.clearRect(0, 0, W, H);

    // Arka plan
    ctx.fillStyle = getComputedStyle(document.documentElement)
      .getPropertyValue("--panel-bg").trim() || "#1a1a2e";
    ctx.fillRect(0, 0, W, H);

    // Izgara
    ctx.strokeStyle = "rgba(100,100,200,0.2)";
    ctx.lineWidth = 0.5;
    const adim = 10; // metre
    for (let i = -50; i <= 50; i += adim) {
      const a = _proje(i, -50, 0);
      const b = _proje(i, 50, 0);
      ctx.beginPath(); ctx.moveTo(cx + a.px, cy + a.py);
      ctx.lineTo(cx + b.px, cy + b.py); ctx.stroke();
      const c = _proje(-50, i, 0);
      const d = _proje(50, i, 0);
      ctx.beginPath(); ctx.moveTo(cx + c.px, cy + c.py);
      ctx.lineTo(cx + d.px, cy + d.py); ctx.stroke();
    }

    if (!suruVeri || !suruVeri.aktif) {
      ctx.fillStyle = "#888";
      ctx.font = "14px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(t("suruAktifYok"), cx, cy);
      return;
    }

    // Master (merkez = 0,0,0)
    const mp = _proje(0, 0, 0);
    ctx.beginPath();
    ctx.arc(cx + mp.px, cy + mp.py, 8, 0, Math.PI * 2);
    ctx.fillStyle = "#4fc3f7";
    ctx.fill();
    ctx.fillStyle = "#fff";
    ctx.font = "bold 10px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("M", cx + mp.px, cy + mp.py + 4);

    // Slave'ler
    const renkler = ["#66bb6a", "#ffa726", "#ef5350", "#ab47bc",
                     "#26c6da", "#ffee58", "#8d6e63", "#78909c"];
    (suruVeri.slaves || []).forEach((s, i) => {
      const renk = renkler[i % renkler.length];
      // Hedef pozisyon (hayalet)
      const hp = _proje(s.x, s.y, s.z);
      ctx.beginPath();
      ctx.arc(cx + hp.px, cy + hp.py, 6, 0, Math.PI * 2);
      ctx.strokeStyle = renk;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([3, 3]);
      ctx.stroke();
      ctx.setLineDash([]);

      // Gerçek pozisyon (master'a göre ENU hesapla)
      if (s.lat != null && suruVeri.master_lat != null) {
        const dlat = (s.lat - suruVeri.master_lat) * 111320;
        const dlon = (s.lon - suruVeri.master_lon) * 111320 *
          Math.cos(suruVeri.master_lat * Math.PI / 180);
        const dalt = (s.alt || 0) - (suruVeri.master_alt || 0);
        // ENU → gövde çerçevesi (heading'e göre döndür)
        const hdg = (suruVeri.master_hdg || 0) * Math.PI / 180;
        const bx = dlat * Math.cos(hdg) + dlon * Math.sin(hdg);
        const by = -dlat * Math.sin(hdg) + dlon * Math.cos(hdg);
        const rp = _proje(bx, by, dalt);
        ctx.beginPath();
        ctx.arc(cx + rp.px, cy + rp.py, 6, 0, Math.PI * 2);
        ctx.fillStyle = renk;
        ctx.fill();
        // Bağlantı çizgisi (hedef → gerçek)
        ctx.beginPath();
        ctx.moveTo(cx + hp.px, cy + hp.py);
        ctx.lineTo(cx + rp.px, cy + rp.py);
        ctx.strokeStyle = renk;
        ctx.lineWidth = 1;
        ctx.globalAlpha = 0.4;
        ctx.stroke();
        ctx.globalAlpha = 1.0;
      }

      // Etiket
      const d = (typeof sonVeri !== "undefined") ? sonVeri[s.sysid] : null;
      const ad = d ? (d.kullanici_isim || d.isim || "D" + s.sysid) : "D" + s.sysid;
      ctx.fillStyle = renk;
      ctx.font = "10px sans-serif";
      ctx.fillText(ad, cx + hp.px, cy + hp.py - 10);
    });

    // Eksen etiketleri
    ctx.font = "9px sans-serif";
    ctx.fillStyle = "#aaa";
    const xp = _proje(40, 0, 0);
    ctx.fillText("X+", cx + xp.px, cy + xp.py);
    const yp = _proje(0, 40, 0);
    ctx.fillText("Y+", cx + yp.px, cy + yp.py);
    const zp = _proje(0, 0, 30);
    ctx.fillText("Z+", cx + zp.px, cy + zp.py);
  }

  // --- Mesafe tablosu ---
  function _mesafeTabloCiz() {
    const el = izlemeEl ? izlemeEl.querySelector("#suruMesafeTablo") : null;
    if (!el) return;
    if (!suruVeri || !suruVeri.aktif) {
      el.innerHTML = "";
      return;
    }
    let html = `<table class="suru-tbl"><thead><tr>
      <th>${t("suruCift")}</th><th>${t("suruMesafe")}</th>
    </tr></thead><tbody>`;

    // Slave satırları (master'a mesafe + çıkar düğmesi)
    (suruVeri.slaves || []).forEach(s => {
      const d = (typeof sonVeri !== "undefined") ? sonVeri[s.sysid] : null;
      const ad = d ? (d.kullanici_isim || d.isim || "D" + s.sysid) : "D" + s.sysid;
      const mesafe = s.mesafe_gercek != null ? s.mesafe_gercek.toFixed(1) + "m" : "-";
      const hedef = s.hedef_mesafe != null ? s.hedef_mesafe.toFixed(1) + "m" : "-";
      html += `<tr>
        <td>M ↔ ${ad}</td>
        <td>${mesafe} / <small>${hedef}</small></td>
        <td><button class="suru-cikar-btn" data-sysid="${s.sysid}">
          <i class="fa-solid fa-user-minus"></i>
        </button></td>
      </tr>`;
    });

    // Slave-slave mesafeler
    (suruVeri.mesafeler || []).forEach(m => {
      if (m.a === suruVeri.master_sysid || m.b === suruVeri.master_sysid) return;
      const da = (typeof sonVeri !== "undefined") ? sonVeri[m.a] : null;
      const db = (typeof sonVeri !== "undefined") ? sonVeri[m.b] : null;
      const adA = da ? (da.kullanici_isim || da.isim || "D" + m.a) : "D" + m.a;
      const adB = db ? (db.kullanici_isim || db.isim || "D" + m.b) : "D" + m.b;
      html += `<tr><td>${adA} ↔ ${adB}</td><td>${m.m.toFixed(1)}m</td><td></td></tr>`;
    });

    html += "</tbody></table>";
    el.innerHTML = html;

    // Çıkar düğmeleri
    el.querySelectorAll(".suru-cikar-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const sid = +btn.dataset.sysid;
        if (confirm(t("suruOnayDagit"))) {
          wsGonder({ tip: "suru_cikar", sysid: sid });
        }
      });
    });
  }

  // --- Telemetri besleme (ws.js'ten çağrılır) ---
  let suruAktifGoruldu = false; // daha önce aktif sürü telemetrisi geldi mi
  function suruTelemetriIsle(veri) {
    suruVeri = veri;
    if (veri && veri.aktif) suruAktifGoruldu = true;
    if (izlemeEl) {
      _canvasCiz();
      _mesafeTabloCiz();
    }
    // Sürü dağıtıldıysa izleme popup'ını kapat (yalnızca daha önce
    // aktif sürü görüldüyse; manuel açılan popup boş beklemede kalır)
    if (!veri && izlemeEl && suruAktifGoruldu) {
      izlemeEl.remove();
      izlemeEl = null;
      suruAktifGoruldu = false;
    }
  }

  // --- suru_durum WS mesajı (anlık duyuru) ---
  function suruDurumIsle(m) {
    suruVeri = m.suru;
    if (suruVeri && suruVeri.aktif && !izlemeEl) {
      izlemeAc();
    }
    if (!suruVeri && izlemeEl) {
      izlemeEl.remove();
      izlemeEl = null;
    }
  }

  // --- Window export'ları ---
  window.suruKurulumAc = kurulumAc;
  window.suruIzlemeAc = izlemeAc;
  window.suruTelemetriIsle = suruTelemetriIsle;
  window.suruDurumIsle = suruDurumIsle;

})();

/* FAZ18-IS2B-IKON-METIN-SPAN */
