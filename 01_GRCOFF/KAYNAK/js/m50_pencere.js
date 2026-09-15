// =================================================================
// GÖKTUNGU — M50 CANLI GÖRÜNTÜ PENCERESİ (v2.4.206)
// -----------------------------------------------------------------
// Kullanıcı isteği (birebir): "M50 ayrı bir sistem … sen tamamen
// kameranın ayrılabilir panelini kopyalayıp gelmişsin lütfen ayrı bir
// sistem tasarla".
//
// Bu modül kamera modülünün (kameralar.js) yüzen penceresini KULLANMAZ.
// Kendi penceresini kurar: başlık (cihaz adı, kanal/bağlantı rozetleri,
// kapat) · görüntü alanı · araç çubuğu (Görünür/Termal, HEDEF / TAKİBİ
// DURDUR) · en altta DURUM ÇUBUĞU (cihaz, IP, kanal, çözünürlük,
// azimut/eğim, bağlantı, takip, konum kaynağı). Kamera düzenleme, AI
// ayarı, görüntü konumu ve dron piksel takibi düğmeleri burada YOKTUR.
//
// Pencerenin BÜTÜNÜ yeniden boyutlanır (CSS .m50-pc resize:both);
// görüntü kalan alanı doldurur. Konum + boyut tarayıcıda saklanır
// (bolum_resize.js: pencereKonumUygula/Kaydet, anahtar m50pc_<eo>).
//
// Görüntü: sunucu vekili /kamera/<id> (kayıt m50:<eo>:<kanal>). Kanal
// geçişi kayıttaki kanalı değiştirir (kameralar.js m50KanalDegistir);
// akış yeni kanaldan yeniden bağlanır.
//
// Hedef: HEDEF → görüntü üzerine dikdörtgen çizimi → görüntü kutusu
// (object-fit: contain) → doğal piksel koordinatı → m50_takip_sec +
// m50_takip_baslat. Takip sürerken HEDEF gizli, TAKİBİ DURDUR görünür;
// durdurunca çerçeve silinir. Düğmeler telemetriden (takip.etkin)
// eşitlenir; her cihaz için AYRI pencere açılır (eo_id anahtarı).
// =================================================================
"use strict";
(function m50PencereModulu(){
  const pencereler = {};   // eoId -> kayıt
  const T = () => (typeof D === "function" ? D() : {}) || {};

  function eoKaydi(eoId){
    const liste = (typeof window.eoListesiOku === "function") ? window.eoListesiOku() : [];
    return liste.find(x => Number(x.eo_id) === Number(eoId)) || null;
  }
  function kameraBul(eoId){
    return (typeof window.m50KameraBul === "function") ? window.m50KameraBul(eoId) : null;
  }
  function kanalOku(kamera){
    return String((kamera && kamera.url) || "").split(":").pop() === "termal" ? "termal" : "gorunur";
  }
  function gonder(paket){
    if (typeof window.m50Gonder === "function") return window.m50Gonder(paket);
    return false;
  }

  // ---- görüntü alanı: object-fit contain -> gerçek kare kutusu ----
  function goruntuKutusu(img){
    const r = img.getBoundingClientRect();
    const nw = img.naturalWidth || r.width, nh = img.naturalHeight || r.height;
    if (!nw || !nh || !r.width || !r.height)
      return { x: r.left, y: r.top, w: r.width, h: r.height, nw: nw || 1, nh: nh || 1 };
    const olcek = Math.min(r.width / nw, r.height / nh);
    const w = nw * olcek, h = nh * olcek;
    return { x: r.left + (r.width - w) / 2, y: r.top + (r.height - h) / 2, w, h, nw, nh };
  }
  function cerceveCiz(k){
    if (!k.cerceve){ if (k.kutuEl){ k.kutuEl.remove(); k.kutuEl = null; } return; }
    const img = k.video.querySelector("img.kam-video");
    if (!img) return;
    const g = goruntuKutusu(img), kr = k.video.getBoundingClientRect();
    if (!k.kutuEl){ k.kutuEl = document.createElement("div"); k.kutuEl.className = "m50-hedef-kutu"; k.video.appendChild(k.kutuEl); }
    const sx = g.w / g.nw, sy = g.h / g.nh;
    k.kutuEl.style.left = (g.x - kr.left + k.cerceve.sol * sx) + "px";
    k.kutuEl.style.top = (g.y - kr.top + k.cerceve.ust * sy) + "px";
    k.kutuEl.style.width = ((k.cerceve.sag - k.cerceve.sol) * sx) + "px";
    k.kutuEl.style.height = ((k.cerceve.alt - k.cerceve.ust) * sy) + "px";
  }

  // ---- HEDEF: dikdörtgen çizimi ----
  function hedefSec(k){
    const img = k.video.querySelector("img.kam-video");
    if (!img || k.ortu) return;
    const t = T();
    const ortu = document.createElement("div");
    ortu.className = "m50-hedef-ortu";
    ortu.title = t.m50HedefIpucu || "Hedefin üzerine bir dikdörtgen çizin (Esc: vazgeç)";
    const secim = document.createElement("div"); secim.className = "m50-hedef-secim"; ortu.appendChild(secim);
    k.video.appendChild(ortu); k.ortu = ortu;
    k.durumMetni = t.m50HedefIpucu || "Hedefin üzerine bir dikdörtgen çizin (Esc: vazgeç)";
    durumYaz(k);
    let bas = null;
    const bitir = () => { ortu.remove(); k.ortu = null; k.durumMetni = ""; durumYaz(k); document.removeEventListener("keydown", esc); };
    function esc(ev){ if (ev.key === "Escape") bitir(); }
    document.addEventListener("keydown", esc);
    const sinirla = (v, a, b) => Math.min(Math.max(v, a), b);
    ortu.addEventListener("mousedown", ev => {
      if (ev.button !== 0) return; ev.preventDefault(); ev.stopPropagation();
      const g = goruntuKutusu(img);
      bas = { x: sinirla(ev.clientX, g.x, g.x + g.w), y: sinirla(ev.clientY, g.y, g.y + g.h), g };
      secim.style.display = "block";
    });
    ortu.addEventListener("mousemove", ev => {
      if (!bas) return;
      const g = bas.g, kr = k.video.getBoundingClientRect();
      const x2 = sinirla(ev.clientX, g.x, g.x + g.w), y2 = sinirla(ev.clientY, g.y, g.y + g.h);
      secim.style.left = (Math.min(bas.x, x2) - kr.left) + "px"; secim.style.top = (Math.min(bas.y, y2) - kr.top) + "px";
      secim.style.width = Math.abs(x2 - bas.x) + "px"; secim.style.height = Math.abs(y2 - bas.y) + "px";
    });
    ortu.addEventListener("mouseup", ev => {
      if (!bas) return; ev.preventDefault(); ev.stopPropagation();
      const g = bas.g;
      const x2 = sinirla(ev.clientX, g.x, g.x + g.w), y2 = sinirla(ev.clientY, g.y, g.y + g.h);
      const sx = g.nw / g.w, sy = g.nh / g.h;
      const cer = { sol: Math.round((Math.min(bas.x, x2) - g.x) * sx), ust: Math.round((Math.min(bas.y, y2) - g.y) * sy),
                    sag: Math.round((Math.max(bas.x, x2) - g.x) * sx), alt: Math.round((Math.max(bas.y, y2) - g.y) * sy) };
      bas = null; bitir();
      if (cer.sag - cer.sol < 4 || cer.alt - cer.ust < 4) return;   // tık = vazgeç
      k.cerceve = cer; cerceveCiz(k);
      const kanal = kanalOku(kameraBul(k.eoId) || k.kamera);
      const modEl = document.getElementById("m50TakipMod");
      const mod = String((modEl && modEl.value) || "hava_yari_otomatik");
      gonder({ tip: "m50_takip_sec", eo_id: k.eoId, kanal,
               video_dikdortgen: { sol: 0, ust: 0, sag: Math.round(g.nw), alt: Math.round(g.nh) }, secim: cer });
      // Sunucu komutları bağlantı başına sırayla işler; seçim kabul
      // edildikten sonra başlat.
      setTimeout(() => gonder({ tip: "m50_takip_baslat", eo_id: k.eoId, kanal, mod }), 400);
      k.bekleniyor = Date.now();
      k.btnHedef.style.display = "none"; k.btnDurdur.style.display = "";
    });
  }

  function takipDurdur(k){
    gonder({ tip: "m50_takip_durdur", eo_id: k.eoId, kanal: kanalOku(kameraBul(k.eoId) || k.kamera) });
    k.cerceve = null; k.bekleniyor = 0; cerceveCiz(k);
    k.btnDurdur.style.display = "none"; k.btnHedef.style.display = "";
  }

  // ---- görüntü bağlama ----
  function videoBagla(k){
    k.video.querySelectorAll("img.kam-video").forEach(e => e.remove());
    const kam = kameraBul(k.eoId);
    k.kamera = kam || k.kamera;
    if (!kam){
      k.video.classList.remove("kam-hata", "kam-baglaniyor");
      if (!k.video.querySelector(".m50-pc-yok")){
        const yok = document.createElement("div"); yok.className = "m50-pc-yok kam-bos-onizleme";
        yok.textContent = T().m50PcKameraYok || "Bu cihaz için görüntü kaydı yok.";
        k.video.appendChild(yok);
      }
      return;
    }
    const y = k.video.querySelector(".m50-pc-yok"); if (y) y.remove();
    const img = document.createElement("img");
    img.className = "kam-video kam-video-m50";   // sürükle-PTZ katmanı bu sınıfı tanır
    img.draggable = false;
    img.dataset.kameraId = String(kam.id);
    img.addEventListener("load", () => { durumYaz(k); cerceveCiz(k); });
    if (typeof window.mjpegBagla === "function")
      window.mjpegBagla(img, () => window.kameraOnizlemeUrl(kam.id), ".m50-pc-video");
    else
      img.src = window.kameraOnizlemeUrl(kam.id);
    k.video.appendChild(img);
    if (k.kutuEl) k.video.appendChild(k.kutuEl);   // çerçeve en üstte kalsın
  }

  // ---- durum çubuğu ----
  function durumYaz(k){
    const t = T();
    const c = eoKaydi(k.eoId);
    const d = (c && c.m50_durum) || {};
    const a = (c && c.m50_ayarlar) || {};
    const takip = (c && (c.m50_takip || d.takip)) || {};
    const kam = kameraBul(k.eoId) || k.kamera;
    const kanal = kanalOku(kam);
    const img = k.video.querySelector("img.kam-video");
    const w = img ? img.naturalWidth : 0, h = img ? img.naturalHeight : 0;
    const isim = (c && c.isim) || (kam && kam.isim) || ("M50 " + k.eoId);
    const ip = (c && (c.kayit_ip || a.ip)) || "";
    const akis = !kam ? "—" : k.video.classList.contains("kam-hata") ? (t.m50PcAkisHata || "yayın alınamıyor") :
                 (k.video.classList.contains("kam-baglaniyor") || !w) ? (t.m50PcAkisBagl || "bağlanıyor") : (t.m50PcAkisCanli || "canlı");
    const aci = (Number.isFinite(Number(d.azimut)) && Number.isFinite(Number(d.egim)))
      ? Number(d.azimut).toFixed(1) + "° / " + Number(d.egim).toFixed(1) + "°" : "—";
    const konum = c && c.konum && typeof c.konum === "object" ? c.konum : null;
    const konumM = konum ? ((konum.kaynak === "rtk" ? "RTK " : "") + Number(konum.lat).toFixed(5) + ", " + Number(konum.lon).toFixed(5)) : "—";
    const parca = [];
    const ekle = (etiket, deger, sinif) => { const s = document.createElement("span"); if (sinif) s.className = sinif;
      s.innerHTML = etiket + ": <b></b>"; s.querySelector("b").textContent = deger; parca.push(s); };
    ekle(t.m50PcDurum || "Durum", d.bagli ? (t.m50Bagli || "Bağlı") : (t.m50Kapali || "Bağlı değil") + (d.hata ? " · " + d.hata : ""), d.bagli ? "" : "m50-pc-uyari");
    ekle("IP", ip || "—");
    ekle(t.m50PcKanal || "Kanal", kanal === "termal" ? (t.m50Termal || "Termal") : (t.m50Gorunur || "Görünür"));
    ekle(t.m50PcCozunurluk || "Çözünürlük", (w && h) ? (w + "×" + h) : "—");
    ekle(t.kamFpsKisa || "FPS", "≤ " + ((kam && kam.fps) || 15));
    ekle(t.m50PcAci || "Az/Eğ", aci);
    ekle(t.m50PcTakip || "Takip", takip.etkin ? (t.m50PcTakipVar || "etkin") : (t.m50PcTakipYok || "yok"));
    ekle(t.m50PcKonum || "Konum", konumM);
    ekle("Akış", akis, akis === (t.m50PcAkisHata || "yayın alınamıyor") ? "m50-pc-uyari" : "");
    k.durum.innerHTML = "";
    if (k.durumMetni){ const s = document.createElement("span"); s.className = "m50-pc-uyari"; s.textContent = k.durumMetni; k.durum.appendChild(s); }
    for (const p of parca) k.durum.appendChild(p);
    // başlık rozetleri
    k.ad.textContent = isim;
    k.rozetKanal.textContent = kanal === "termal" ? "TERMAL" : "GÖRÜNÜR";
    k.rozetBag.textContent = d.bagli ? "BAĞLI" : "KAPALI";
    k.rozetBag.classList.toggle("bagli", !!d.bagli);
    k.rozetTakip.style.display = takip.etkin ? "" : "none";
    // düğmeler
    for (const b of k.kanalDgm) b.classList.toggle("aktif", b.dataset.kanal === kanal);
    const etkin = !!takip.etkin;
    if (etkin) k.bekleniyor = 0;
    const bekliyor = k.bekleniyor && Date.now() - k.bekleniyor < 6000;
    if (!etkin && !bekliyor && k.cerceve && k.bekleniyor){ k.cerceve = null; k.bekleniyor = 0; cerceveCiz(k); }
    k.btnHedef.style.display = (etkin || bekliyor) ? "none" : "";
    k.btnDurdur.style.display = (etkin || bekliyor) ? "" : "none";
    k.btnHedef.disabled = !d.bagli || !kam;
    for (const b of k.kanalDgm) b.disabled = !kam;
  }

  // ---- pencere ----
  function pencereKur(eoId, kamId){
    const t = T();
    const k = { eoId: Number(eoId), kamera: null, cerceve: null, kutuEl: null, ortu: null, bekleniyor: 0, durumMetni: "" };
    const p = document.createElement("div"); p.className = "m50-pc"; p.dataset.eoId = String(eoId);
    // başlık
    const baslik = document.createElement("div"); baslik.className = "m50-pc-baslik";
    const ikon = document.createElement("i"); ikon.className = "fa-solid fa-binoculars m50-pc-ikon";
    const ad = document.createElement("span"); ad.className = "m50-pc-ad";
    const rozetKanal = document.createElement("span"); rozetKanal.className = "m50-pc-rozet";
    const rozetBag = document.createElement("span"); rozetBag.className = "m50-pc-rozet";
    const rozetTakip = document.createElement("span"); rozetTakip.className = "m50-pc-rozet takip"; rozetTakip.textContent = "TAKİP";
    const kapat = document.createElement("button"); kapat.type = "button"; kapat.className = "m50-pc-kapat";
    kapat.title = t.m50PcKapat || "Pencereyi kapat"; kapat.innerHTML = "<i class='fa-solid fa-xmark'></i>";
    kapat.addEventListener("click", ev => { ev.stopPropagation(); window.m50PencereKapat(eoId); });
    baslik.append(ikon, ad, rozetKanal, rozetBag, rozetTakip, kapat);
    // görüntü
    const video = document.createElement("div"); video.className = "m50-pc-video";
    // araç çubuğu
    const alt = document.createElement("div"); alt.className = "m50-pc-alt";
    const solGrup = document.createElement("div"); solGrup.className = "m50-pc-grup";
    const kanalDgm = [];
    for (const [kanal, ik, etiket] of [["gorunur", "fa-sun", t.m50Gorunur || "Görünür"], ["termal", "fa-fire", t.m50Termal || "Termal"]]){
      const b = document.createElement("button"); b.type = "button"; b.className = "m50-pc-btn m50-pc-kanal"; b.dataset.kanal = kanal;
      b.innerHTML = "<i class='fa-solid " + ik + "'></i>" + etiket;
      b.addEventListener("click", ev => {
        ev.stopPropagation();
        const kam = kameraBul(k.eoId);
        if (!kam || kanalOku(kam) === kanal || typeof window.m50KanalDegistir !== "function") return;
        window.m50KanalDegistir(kam, kanal);
        k.cerceve = null; cerceveCiz(k);
        setTimeout(() => videoBagla(k), 600);   // kayıt yenilendikten sonra yeni kanaldan bağlan
      });
      solGrup.appendChild(b); kanalDgm.push(b);
    }
    const sagGrup = document.createElement("div"); sagGrup.className = "m50-pc-grup";
    const btnHedef = document.createElement("button"); btnHedef.type = "button"; btnHedef.className = "m50-pc-btn m50-pc-hedef";
    btnHedef.innerHTML = "<i class='fa-solid fa-crosshairs'></i>" + (t.m50PencereHedef || "HEDEF");
    btnHedef.addEventListener("click", ev => { ev.stopPropagation(); hedefSec(k); });
    const btnDurdur = document.createElement("button"); btnDurdur.type = "button"; btnDurdur.className = "m50-pc-btn m50-pc-durdur";
    btnDurdur.innerHTML = "<i class='fa-solid fa-ban'></i>" + (t.m50PencereDurdur || "TAKİBİ DURDUR"); btnDurdur.style.display = "none";
    btnDurdur.addEventListener("click", ev => { ev.stopPropagation(); takipDurdur(k); });
    sagGrup.append(btnHedef, btnDurdur);
    alt.append(solGrup, sagGrup);
    // durum çubuğu
    const durum = document.createElement("div"); durum.className = "m50-pc-durum";
    p.append(baslik, video, alt, durum);
    Object.assign(k, { pencere: p, baslik, video, alt, durum, ad, rozetKanal, rozetBag, rozetTakip, kanalDgm, btnHedef, btnDurdur });
    document.body.appendChild(p);
    // konum/boyut
    const kayitVar = typeof window.pencereKonumUygula === "function" && window.pencereKonumUygula("m50pc_" + eoId, p, true);
    if (!kayitVar){
      const n = Object.keys(pencereler).length;
      p.style.left = Math.max(8, (window.innerWidth - 580) / 2 + n * 32) + "px";
      p.style.top = Math.max(8, 80 + n * 32) + "px";
    }
    surukleKur(k);
    if (typeof ResizeObserver !== "undefined"){
      let ilk = true;
      new ResizeObserver(() => {
        cerceveCiz(k);
        if (ilk){ ilk = false; return; }
        if (typeof window.pencereKonumKaydet === "function") window.pencereKonumKaydet("m50pc_" + eoId, p, true);
      }).observe(p);
    }
    if (typeof MutationObserver !== "undefined")
      new MutationObserver(() => durumYaz(k)).observe(video, { attributes: true, attributeFilter: ["class"] });
    p.addEventListener("mousedown", () => oneAl(k));
    videoBagla(k);
    durumYaz(k);
    return k;
  }

  function oneAl(k){
    const ust = [...document.querySelectorAll(".m50-pc, .kam-pencere")]
      .reduce((v, el) => Math.max(v, Number(el.style.zIndex || 2450)), 2450);
    k.pencere.style.zIndex = String(ust + 1);
  }

  function surukleKur(k){
    let s = null;
    const b = k.baslik, p = k.pencere;
    b.addEventListener("pointerdown", ev => {
      if (ev.target.closest("button")) return;
      const r = p.getBoundingClientRect();
      s = { dx: ev.clientX - r.left, dy: ev.clientY - r.top };
      b.setPointerCapture(ev.pointerId); ev.preventDefault();
    });
    b.addEventListener("pointermove", ev => {
      if (!s) return;
      const minT = (typeof window.pencereMinTop === "function") ? window.pencereMinTop() : 48;
      p.style.left = Math.min(Math.max(ev.clientX - s.dx, 0), window.innerWidth - 120) + "px";
      p.style.top = Math.min(Math.max(ev.clientY - s.dy, minT), window.innerHeight - 40) + "px";
    });
    const bitir = () => { if (!s) return; s = null;
      if (typeof window.pencereKonumKaydet === "function") window.pencereKonumKaydet("m50pc_" + k.eoId, p, true); };
    b.addEventListener("pointerup", bitir); b.addEventListener("pointercancel", bitir);
  }

  // ---- dışa açık yüz ----
  window.m50PencereAc = function(eoId, kamId){
    eoId = Number(eoId);
    if (!eoId) return false;
    let k = pencereler[eoId];
    if (k && document.body.contains(k.pencere)){ oneAl(k); videoBagla(k); durumYaz(k); return true; }
    k = pencereKur(eoId, kamId);
    pencereler[eoId] = k;
    oneAl(k);
    return true;
  };
  window.m50PencereKapat = function(eoId){
    const k = pencereler[Number(eoId)];
    if (!k) return;
    const img = k.video.querySelector("img.kam-video"); if (img) img.src = "";
    k.pencere.remove();
    delete pencereler[Number(eoId)];
  };
  // Telemetri her geldiğinde (m50_panel.js m50PaneliGuncelle) çağrılır.
  window.m50PencereleriTazele = function(){
    for (const id of Object.keys(pencereler)){
      const k = pencereler[id];
      if (!document.body.contains(k.pencere)){ delete pencereler[id]; continue; }
      try { durumYaz(k); } catch (e) {}
    }
  };
  // Kamera listesi değişince (kanal değişimi, kayıt oluşturma) akışı tazele.
  window.m50PencereKameraDegisti = function(){
    for (const id of Object.keys(pencereler)){
      const k = pencereler[id];
      const kam = kameraBul(k.eoId);
      const img = k.video.querySelector("img.kam-video");
      const eski = img ? Number(img.dataset.kameraId) : 0;
      if ((kam && kam.id !== eski) || (!kam && eski) || (kam && kam.url !== (k.kamera && k.kamera.url))) videoBagla(k);
      k.kamera = kam || k.kamera;
    }
  };
})();
