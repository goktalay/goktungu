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
      durumYaz(k);
    });
  }

  function takipDurdur(k){
    if (k.aiTakip){ aiTakipDurdur(k); return; }
    gonder({ tip: "m50_takip_durdur", eo_id: k.eoId, kanal: kanalOku(kameraBul(k.eoId) || k.kamera) });
    k.cerceve = null; k.bekleniyor = 0; cerceveCiz(k);
    durumYaz(k);
  }

  // =================================================================
  // v2.4.209 — HAVA ARACI TANIMA + GÖRÜNTÜ İŞLEME VERİSİYLE TAKİP
  // Kullanıcı isteği: "m50 için hava araçları tanıma modülünü entegre
  // edelim; objeye çift tıklarsak kamera track etmeye başlasın, track
  // için görüntü işleme verisini kullansın".
  //
  // TANIMA: durum çubuğundaki düğme AI izlemesini (hava_araci görevi)
  // bu kameranın vekil akışı üzerinde başlatır/durdurur; tespit kutuları
  // sunucuda kareye çizilir (anotasyon) ve `ai_kutular` ile istemciye
  // gelir (kamera_takip.js → kameraTespitKutulari).
  //
  // ÇİFT TIK: tıklanan noktadaki tespit kutusu hedef olur. Takip, SDK'nın
  // kendi izleyicisine DEĞİL görüntü işleme verisine dayanır: her 300 ms
  // en yakın tespit kutusu bulunur, kutunun merkezi ile kare merkezi
  // arasındaki sapma PTZ komutuna (yön + hız, ölü bölge %5) çevrilir.
  // Kutu 4 sn gelmezse hedef kayıp sayılır, PTZ durdurulur.
  // =================================================================
  const AI_ARALIK_MS = 300, AI_KAYIP_MS = 4000, AI_OLU_BOLGE = 0.05, AI_ESLEME_ORAN = 0.35;
  const AI_TUR_AD = { hava_araci: "HAVA ARACI" };
  function aiAktifMi(kam){ return !!(kam && typeof window.aiIzlemeAktifMi === "function" && window.aiIzlemeAktifMi(kam.id)); }
  function aiTanimaAcKapa(k){
    const kam = kameraBul(k.eoId);
    if (!kam) return;
    if (aiAktifMi(kam)){
      if (typeof window.aiIzlemeDurdur === "function") window.aiIzlemeDurdur(kam.id);
      if (k.aiTakip) aiTakipDurdur(k);
      return;
    }
    const gorevler = String(kam.ai_gorevler || "");
    if (!/\bhava_araci\b/.test(gorevler) && typeof window.m50KameraAlanGuncelle === "function"){
      // Görev kayıtta yoksa önce kayıt (sunucu komutları bağlantı başına sırayla işler).
      window.m50KameraAlanGuncelle(kam, { ai_gorevler: gorevler ? gorevler + ",hava_araci" : "hava_araci" });
    }
    if (typeof window.aiIzlemeBaslat === "function") setTimeout(() => window.aiIzlemeBaslat(kam.id), 300);
  }
  function kutuNoktasi(img, ev, kw, kh){
    const g = goruntuKutusu(img);
    const px = (ev.clientX - g.x) * g.nw / g.w, py = (ev.clientY - g.y) * g.nh / g.h;
    if (px < 0 || py < 0 || px > g.nw || py > g.nh) return null;
    return { x: px * (kw || g.nw) / g.nw, y: py * (kh || g.nh) / g.nh };
  }
  function aiHedefSec(k, ev){
    const kam = kameraBul(k.eoId);
    const img = k.video.querySelector("img.kam-video");
    if (!kam || !img) return false;
    const t = T();
    const kt = typeof window.kameraTespitKutulari === "function" ? window.kameraTespitKutulari(kam.id) : null;
    if (!kt || !kt.liste.length){
      k.durumMetni = aiAktifMi(kam) ? (t.m50AiHedefYok || "Tespit edilmiş hedef yok") : (t.m50AiKapali || "Tanıma kapalı — durum çubuğundan açın");
      durumYaz(k); setTimeout(() => { if (!k.ortu){ k.durumMetni = ""; durumYaz(k); } }, 2500);
      return false;
    }
    let aday = null;
    for (const b of kt.liste){
      if (!AI_TUR_AD[b.tur]) continue;
      const n = kutuNoktasi(img, ev, b.kaynak_w, b.kaynak_h);
      if (!n) continue;
      const tol = 12;
      if (n.x < b.x - tol || n.y < b.y - tol || n.x > b.x + b.w + tol || n.y > b.y + b.h + tol) continue;
      const alan = b.w * b.h;
      if (!aday || alan < aday.alan) aday = { b, alan };
    }
    if (!aday){
      k.durumMetni = t.m50AiKutuDisi || "Tıklanan yerde hedef yok — tespit kutusuna çift tıklayın";
      durumYaz(k); setTimeout(() => { if (!k.ortu){ k.durumMetni = ""; durumYaz(k); } }, 2500);
      return false;
    }
    aiTakipBaslat(k, kam, aday.b);
    return true;
  }
  function aiTakipBaslat(k, kam, b){
    if (k.aiTakip) aiTakipDurdur(k, true);
    if (k.bekleniyor || k.cerceve){ gonder({ tip: "m50_takip_durdur", eo_id: k.eoId, kanal: kanalOku(kam) }); k.bekleniyor = 0; }
    k.aiTakip = { tur: b.tur, cx: b.x + b.w / 2, cy: b.y + b.h / 2, kw: b.kaynak_w || 0, kh: b.kaynak_h || 0,
                  sonTs: Date.now(), yon: "", hiz: 0, kamId: kam.id, kutu: b };
    aiCerceve(k, b);
    k.aiZaman = setInterval(() => aiTakipAdim(k), AI_ARALIK_MS);
    durumYaz(k);
  }
  function aiCerceve(k, b){
    const img = k.video.querySelector("img.kam-video");
    if (!img || !img.naturalWidth) return;
    const kw = b.kaynak_w || img.naturalWidth, kh = b.kaynak_h || img.naturalHeight;
    const sx = img.naturalWidth / kw, sy = img.naturalHeight / kh;
    k.cerceve = { sol: Math.round(b.x * sx), ust: Math.round(b.y * sy), sag: Math.round((b.x + b.w) * sx), alt: Math.round((b.y + b.h) * sy) };
    cerceveCiz(k);
  }
  function aiPtz(k, yon, hiz){
    const a = k.aiTakip; if (!a) return;
    if (yon === a.yon && hiz === a.hiz) return;
    if (a.yon && yon !== a.yon) gonder({ tip: "m50_ptz", eo_id: k.eoId, yon: a.yon, hiz: a.hiz || 1, basili: false });
    if (yon) gonder({ tip: "m50_ptz", eo_id: k.eoId, yon, hiz, basili: true });
    a.yon = yon; a.hiz = hiz;
  }
  function aiTakipAdim(k){
    const a = k.aiTakip; if (!a) return;
    const kam = kameraBul(k.eoId);
    const kt = (kam && typeof window.kameraTespitKutulari === "function") ? window.kameraTespitKutulari(kam.id) : null;
    const simdi = Date.now();
    let enIyi = null;
    if (kt && kt.ts > (a.kutuTs || 0) && kt.liste.length){
      const kw = a.kw || (kt.liste[0].kaynak_w || 1), kh = a.kh || (kt.liste[0].kaynak_h || 1);
      const esik = AI_ESLEME_ORAN * Math.hypot(kw, kh);
      for (const b of kt.liste){
        if (b.tur !== a.tur) continue;
        const d = Math.hypot(b.x + b.w / 2 - a.cx, b.y + b.h / 2 - a.cy);
        if (d <= esik && (!enIyi || d < enIyi.d)) enIyi = { b, d };
      }
      a.kutuTs = kt.ts;
    }
    if (enIyi){
      const b = enIyi.b;
      a.cx = b.x + b.w / 2; a.cy = b.y + b.h / 2; a.kw = b.kaynak_w || a.kw; a.kh = b.kaynak_h || a.kh;
      a.sonTs = simdi; a.kutu = b;
      aiCerceve(k, b);
    } else if (simdi - a.sonTs > AI_KAYIP_MS){
      const t = T();
      aiTakipDurdur(k);
      k.durumMetni = t.m50AiKayip || "Hedef kaybedildi — takip durduruldu";
      durumYaz(k); setTimeout(() => { if (!k.ortu){ k.durumMetni = ""; durumYaz(k); } }, 3000);
      return;
    }
    // Sapma -> PTZ (kare merkezine göre, -0.5..0.5)
    const kw = a.kw || 1, kh = a.kh || 1;
    const dx = a.cx / kw - 0.5, dy = a.cy / kh - 0.5;
    const yx = Math.abs(dx) > AI_OLU_BOLGE ? (dx > 0 ? "sag" : "sol") : "";
    const yy = Math.abs(dy) > AI_OLU_BOLGE ? (dy > 0 ? "asagi" : "yukari") : "";
    const yon = yx && yy ? yx + "_" + yy : (yx || yy);
    const sapma = Math.max(Math.abs(dx), Math.abs(dy));
    // Hız: sapma 0.05 -> ~4, 0.5 -> 60 (doğrusal); küçük sapmada yavaş yaklaşır.
    const hiz = Math.max(2, Math.min(60, Math.round((sapma - AI_OLU_BOLGE) / (0.5 - AI_OLU_BOLGE) * 58 + 2)));
    aiPtz(k, yon, yon ? hiz : 0);
  }
  function aiTakipDurdur(k, sessiz){
    const a = k.aiTakip; if (!a) return;
    clearInterval(k.aiZaman); k.aiZaman = null;
    if (a.yon) gonder({ tip: "m50_ptz", eo_id: k.eoId, yon: a.yon, hiz: a.hiz || 1, basili: false });
    k.aiTakip = null; k.cerceve = null; cerceveCiz(k);
    if (!sessiz) durumYaz(k);
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

  // ---- durum çubuğu (v2.4.207: ETKİLEŞİMLİ, kullanıcı isteği) ----
  // Kanal: düğme (Görünür <-> Termal) · Çözünürlük: açılır seçim ·
  // FPS · Az/Eğ · Takip: düğme (yok -> hedef seç, etkin -> durdur).
  // IP / Durum / Konum / Akış gösterilmez. Düğmeler <span> taşır:
  // dugme_birlik.css yalnız-ikonlu düğmeleri 26 px kareye zorlar.
  const GENISLIKLER = [320, 480, 640, 800, 960, 1280, 1600, 1920];
  function durumYaz(k){
    const t = T();
    const c = eoKaydi(k.eoId);
    const d = (c && c.m50_durum) || {};
    const takip = (c && (c.m50_takip || d.takip)) || {};
    const kam = kameraBul(k.eoId) || k.kamera;
    const kanal = kanalOku(kam);
    const img = k.video.querySelector("img.kam-video");
    const w = img ? img.naturalWidth : 0, h = img ? img.naturalHeight : 0;
    const isim = (c && c.isim) || (kam && kam.isim) || ("M50 " + k.eoId);
    const aci = (Number.isFinite(Number(d.azimut)) && Number.isFinite(Number(d.egim)))
      ? Number(d.azimut).toFixed(1) + "° / " + Number(d.egim).toFixed(1) + "°" : "—";
    const etkin = !!takip.etkin;
    if (etkin) k.bekleniyor = 0;
    const bekliyor = k.bekleniyor && Date.now() - k.bekleniyor < 6000;
    if (!etkin && !bekliyor && k.cerceve && k.bekleniyor){ k.cerceve = null; k.bekleniyor = 0; cerceveCiz(k); }
    // --- kanal düğmesi ---
    k.sbKanal.querySelector("span").textContent = kanal === "termal" ? (t.m50Termal || "Termal") : (t.m50Gorunur || "Görünür");
    k.sbKanal.querySelector("i").className = "fa-solid " + (kanal === "termal" ? "fa-fire" : "fa-sun");
    k.sbKanal.title = kanal === "termal" ? (t.m50PcKanalGorunurGec || "Görünür kanala geç") : (t.m50PcKanalTermalGec || "Termal kanala geç");
    k.sbKanal.disabled = !kam;
    // --- çözünürlük seçimi ---
    const gen = Number((kam && kam.genislik) || 960);
    if (document.activeElement !== k.sbGen){
      k.sbGen.innerHTML = "";
      for (const g of GENISLIKLER){
        const o = document.createElement("option"); o.value = String(g);
        const yh = (w && h) ? Math.round(g * h / w) : Math.round(g * 9 / 16);
        o.textContent = g + "×" + yh + (g === gen && w && h ? "" : "");
        if (g === gen) o.selected = true;
        k.sbGen.appendChild(o);
      }
      k.sbGen.disabled = !kam;
    }
    k.sbGenOlcu.textContent = (w && h) ? "(" + w + "×" + h + ")" : "";
    // --- fps / açı ---
    k.sbFps.textContent = "≤ " + ((kam && kam.fps) || 15);
    k.sbAci.textContent = aci;
    // --- takip düğmesi ---
    const takipDurumu = etkin || bekliyor || !!k.aiTakip;
    k.sbTakip.querySelector("span").textContent = k.aiTakip
      ? (t.m50PcDurdur || "Durdur") + " · AI " + (AI_TUR_AD[k.aiTakip.tur] || "")
      : takipDurumu ? (t.m50PcDurdur || "Durdur") : (t.m50PcHedefSec || "Hedef seç");
    // --- tanıma düğmesi ---
    const aiAcik = aiAktifMi(kam);
    k.sbTanima.querySelector("span").textContent = aiAcik ? (t.m50AiAcik || "Açık") : (t.m50AiKapaliKisa || "Kapalı");
    k.sbTanima.classList.toggle("acik", aiAcik);
    k.sbTanima.disabled = !kam;
    k.sbTanima.title = aiAcik ? (t.m50AiKapatIpucu || "Hava aracı tanımayı kapat") : (t.m50AiAcIpucu || "Hava aracı tanımayı aç (tespit kutusuna çift tık: takip)");
    k.sbTakip.querySelector("i").className = "fa-solid " + (takipDurumu ? "fa-ban" : "fa-crosshairs");
    k.sbTakip.classList.toggle("takipte", takipDurumu);
    k.sbTakip.disabled = !kam || (!d.bagli && !takipDurumu);
    k.sbTakip.title = takipDurumu ? (t.m50PencereDurdur || "TAKİBİ DURDUR") : (t.m50HedefIpucu || "Hedefin üzerine bir dikdörtgen çizin");
    k.takipte = takipDurumu;
    // --- ipucu satırı (çizim sırasında) ---
    k.sbIpucu.textContent = k.durumMetni || "";
    k.sbIpucu.style.display = k.durumMetni ? "" : "none";
    // --- başlık rozetleri ---
    k.ad.textContent = isim;
    k.rozetKanal.textContent = kanal === "termal" ? "TERMAL" : "GÖRÜNÜR";
    k.rozetBag.textContent = d.bagli ? "BAĞLI" : "KAPALI";
    k.rozetBag.classList.toggle("bagli", !!d.bagli);
    k.rozetTakip.style.display = (etkin || k.aiTakip) ? "" : "none";
    k.rozetTakip.textContent = k.aiTakip ? "AI TAKİP" : "TAKİP";
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
    // durum çubuğu (etkileşimli)
    const durum = document.createElement("div"); durum.className = "m50-pc-durum";
    const alan = (etiket) => { const sp = document.createElement("span"); sp.className = "m50-pc-alan";
      const e = document.createElement("em"); e.textContent = etiket + ":"; sp.appendChild(e); durum.appendChild(sp); return sp; };
    const dugme = (sinif, ikon) => { const b = document.createElement("button"); b.type = "button"; b.className = "m50-pc-sb " + sinif;
      b.innerHTML = "<i class='fa-solid " + ikon + "'></i><span></span>"; return b; };
    const aKanal = alan(t.m50PcKanal || "Kanal");
    const sbKanal = dugme("m50-pc-sb-kanal", "fa-sun");
    sbKanal.addEventListener("click", ev => {
      ev.stopPropagation();
      const kam = kameraBul(k.eoId);
      if (!kam || typeof window.m50KanalDegistir !== "function") return;
      const yeni = kanalOku(kam) === "termal" ? "gorunur" : "termal";
      window.m50KanalDegistir(kam, yeni);
      k.cerceve = null; cerceveCiz(k);
      setTimeout(() => videoBagla(k), 600);
    });
    aKanal.appendChild(sbKanal);
    const aGen = alan(t.m50PcCozunurluk || "Çözünürlük");
    const sbGen = document.createElement("select"); sbGen.className = "m50-pc-sb m50-pc-sb-gen";
    sbGen.title = t.m50PcGenIpucu || "Vekil çıktı genişliği; değiştirince akış yeniden kurulur";
    sbGen.addEventListener("change", ev => {
      ev.stopPropagation();
      const kam = kameraBul(k.eoId);
      if (!kam || typeof window.m50KameraAlanGuncelle !== "function") return;
      window.m50KameraAlanGuncelle(kam, { genislik: parseInt(sbGen.value, 10) || 960 });
      setTimeout(() => videoBagla(k), 800);
    });
    sbGen.addEventListener("mousedown", ev => ev.stopPropagation());
    const sbGenOlcu = document.createElement("small"); sbGenOlcu.className = "m50-pc-olcu";
    aGen.append(sbGen, sbGenOlcu);
    const aFps = alan(t.kamFpsKisa || "FPS"); const sbFps = document.createElement("b"); aFps.appendChild(sbFps);
    const aAci = alan(t.m50PcAci || "Az/Eğ"); const sbAci = document.createElement("b"); aAci.appendChild(sbAci);
    const aTanima = alan(t.m50AiTanima || "Tanıma");
    const sbTanima = dugme("m50-pc-sb-tanima", "fa-plane");
    sbTanima.addEventListener("click", ev => { ev.stopPropagation(); aiTanimaAcKapa(k); });
    aTanima.appendChild(sbTanima);
    const aTakip = alan(t.m50PcTakip || "Takip");
    const sbTakip = dugme("m50-pc-sb-takip", "fa-crosshairs");
    sbTakip.addEventListener("click", ev => { ev.stopPropagation(); if (k.takipte) takipDurdur(k); else hedefSec(k); });
    aTakip.appendChild(sbTakip);
    const sbIpucu = document.createElement("span"); sbIpucu.className = "m50-pc-ipucu"; sbIpucu.style.display = "none";
    durum.appendChild(sbIpucu);
    p.append(baslik, video, durum);
    Object.assign(k, { pencere: p, baslik, video, durum, ad, rozetKanal, rozetBag, rozetTakip,
                       sbKanal, sbGen, sbGenOlcu, sbFps, sbAci, sbTanima, sbTakip, sbIpucu, takipte: false, aiTakip: null, aiZaman: null });
    // Çift tık: tespit kutusundaki hava aracını görüntü işleme verisiyle takip et
    video.addEventListener("dblclick", ev => {
      const img = ev.target && ev.target.closest && ev.target.closest("img.kam-video");
      if (!img) return;
      ev.preventDefault(); ev.stopPropagation();
      if (k.aiTakip){ aiTakipDurdur(k); return; }   // takipteyken çift tık: bırak
      aiHedefSec(k, ev);
    }, true);
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
    if (k.aiTakip) aiTakipDurdur(k, true);
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
