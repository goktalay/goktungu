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
  function kameraBul(eoId, kanal){
    if (kanal && typeof window.m50KameraBulKanal === "function") return window.m50KameraBulKanal(eoId, kanal);
    return (typeof window.m50KameraBul === "function") ? window.m50KameraBul(eoId) : null;
  }
  // v2.4.210: ana görüntünün kaydı = seçili kanalın kaydı; yoksa herhangi bir M50 kaydı
  function anaKamera(k){ return kameraBul(k.eoId, k.anaKanal) || anaKamera(k); }
  function digerKanal(kanal){ return kanal === "termal" ? "gorunur" : "termal"; }
  const yerel = {
    oku(anahtar, varsayilan){ try { const v = localStorage.getItem(anahtar); return v === null ? varsayilan : JSON.parse(v); } catch (e) { return varsayilan; } },
    yaz(anahtar, deger){ try { localStorage.setItem(anahtar, JSON.stringify(deger)); } catch (e) {} }
  };
  // v2.4.210: video kaydı durumu (sunucu `video_kayit_durum`)
  let kayitlar = {};
  window.videoKayitDurumIsle = function(m){ kayitlar = (m && m.kayitlar) || {}; window.m50PencereleriTazele(); };
  function kayitBul(kam){ const r = kam && kayitlar[String(kam.id)]; return (r && r.calisiyor) ? r : null; }
  function wsGonder(o){ if (typeof window.kameraWsGonder === "function") window.kameraWsGonder(o); }
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
      const kanal = kanalOku(anaKamera(k) || k.kamera);
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
    gonder({ tip: "m50_takip_durdur", eo_id: k.eoId, kanal: kanalOku(anaKamera(k) || k.kamera) });
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
    const kam = anaKamera(k);
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
    const kam = anaKamera(k);
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
    const kam = anaKamera(k);
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
  function kanalKaydiGaranti(k, kanal){
    if (kameraBul(k.eoId, kanal)) return true;
    k.istenenKayit = k.istenenKayit || {};
    if (Date.now() - (k.istenenKayit[kanal] || 0) > 8000){
      k.istenenKayit[kanal] = Date.now();
      // Aynı EO'nun aynı kanalda İKİ kaydı varsa (eski kanal düğmesinin url
      // yeniden yazması) üçüncü kayıt açmak yerine sonuncusu bu kanala çevrilir.
      const hepsi = (window._kameralarSon || []).filter(x => String(x.protokol || "").toLowerCase() === "m50" &&
        Number(String(x.url || "").split(":")[1]) === Number(k.eoId));
      if (hepsi.length >= 2 && typeof window.m50KanalDegistir === "function"){ window.m50KanalDegistir(hepsi[hepsi.length - 1], kanal); return false; }
      if (typeof window.m50KameraOlustur === "function"){
        const c = eoKaydi(k.eoId);
        window.m50KameraOlustur(k.eoId, ((c && c.isim) || ("M50 " + k.eoId)) + (kanal === "termal" ? " Termal" : ""), kanal);
      }
    }
    return false;
  }
  function videoBagla(k){
    k.video.querySelectorAll("img.kam-video").forEach(e => e.remove());
    kanalKaydiGaranti(k, k.anaKanal);
    const kam = anaKamera(k);
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

  // =================================================================
  // v2.4.210 — KÜÇÜK GÖRÜNTÜ (PiP): ana görüntü gündüzse gece, geceyse
  // gündüz kanalı; pencere içinde sürüklenir/boyutlanır, kapatılıp açılır.
  // =================================================================
  function pipBagla(k){
    if (!k.pip) return;
    const kanal = digerKanal(k.anaKanal);
    kanalKaydiGaranti(k, kanal);
    const kam = kameraBul(k.eoId, kanal);
    const img = k.pip.querySelector("img");
    if (!kam){ img.removeAttribute("src"); img.dataset.kameraId = ""; k.pip.classList.add("bos"); k.pipEtiket.textContent = (kanal === "termal" ? "TERMAL" : "GÖRÜNÜR") + " · " + (T().m50PipKayitYok || "kayıt oluşturuluyor…"); return; }
    k.pip.classList.remove("bos");
    k.pipEtiket.textContent = kanal === "termal" ? "TERMAL" : "GÖRÜNÜR";
    if (Number(img.dataset.kameraId) !== kam.id){
      img.dataset.kameraId = String(kam.id);
      img.src = window.kameraOnizlemeUrl(kam.id);
    }
  }
  function pipAcKapa(k, ac){
    const t = T();
    k.pipAcik = (ac === undefined) ? !k.pipAcik : !!ac;
    yerel.yaz("m50pip_" + k.eoId, k.pipAcik);
    if (!k.pipAcik){
      if (k.pip){ const im = k.pip.querySelector("img"); if (im) im.removeAttribute("src"); k.pip.remove(); k.pip = null; }
      durumYaz(k); return;
    }
    if (k.pip) return;
    const pip = document.createElement("div"); pip.className = "m50-pc-pip";
    const bas = document.createElement("div"); bas.className = "m50-pc-pip-bas";
    const et = document.createElement("span"); const kp = document.createElement("button"); kp.type = "button"; kp.className = "m50-pc-pip-kapat";
    kp.innerHTML = "<i class='fa-solid fa-xmark'></i>"; kp.title = t.m50PipKapat || "Küçük görüntüyü kapat";
    kp.addEventListener("click", ev => { ev.stopPropagation(); pipAcKapa(k, false); });
    bas.append(et, kp);
    const img = document.createElement("img"); img.draggable = false; img.alt = "";
    pip.append(bas, img);
    const kon = yerel.oku("m50pipkon_" + k.eoId, null);
    if (kon){ pip.style.left = kon.l + "px"; pip.style.top = kon.t + "px"; if (kon.w) pip.style.width = kon.w + "px"; }
    else { pip.style.right = "10px"; pip.style.bottom = "10px"; }
    // sürükle (görüntü alanı içinde)
    let sr = null;
    bas.addEventListener("pointerdown", ev => {
      if (ev.target.closest("button")) return;
      const r = pip.getBoundingClientRect(); sr = { dx: ev.clientX - r.left, dy: ev.clientY - r.top };
      bas.setPointerCapture(ev.pointerId); ev.preventDefault(); ev.stopPropagation();
    });
    bas.addEventListener("pointermove", ev => {
      if (!sr) return;
      const vr = k.video.getBoundingClientRect(), pr = pip.getBoundingClientRect();
      const l = Math.min(Math.max(ev.clientX - sr.dx - vr.left, 0), vr.width - pr.width);
      const tt = Math.min(Math.max(ev.clientY - sr.dy - vr.top, 0), vr.height - pr.height);
      pip.style.left = l + "px"; pip.style.top = tt + "px"; pip.style.right = "auto"; pip.style.bottom = "auto";
    });
    const bitir = () => { if (!sr) return; sr = null; yerel.yaz("m50pipkon_" + k.eoId, { l: pip.offsetLeft, t: pip.offsetTop, w: pip.offsetWidth }); };
    bas.addEventListener("pointerup", bitir); bas.addEventListener("pointercancel", bitir);
    pip.addEventListener("dblclick", ev => { ev.stopPropagation(); ev.preventDefault(); kanalDegistir(k); });
    pip.addEventListener("mousedown", ev => ev.stopPropagation());
    pip.addEventListener("wheel", ev => ev.stopPropagation(), { passive: true });
    if (typeof ResizeObserver !== "undefined") new ResizeObserver(() => { if (pip.isConnected) yerel.yaz("m50pipkon_" + k.eoId, { l: pip.offsetLeft, t: pip.offsetTop, w: pip.offsetWidth }); }).observe(pip);
    k.pip = pip; k.pipEtiket = et;
    k.video.appendChild(pip);
    pipBagla(k);
    durumYaz(k);
  }
  function kanalDegistir(k){
    k.anaKanal = digerKanal(k.anaKanal);
    yerel.yaz("m50kanal_" + k.eoId, k.anaKanal);
    if (k.oc){ k.oc.sonImza = ""; k.oc.kirli = false; k.ocIstek = 0; }
    if (k.aiTakip) aiTakipDurdur(k, true);
    k.cerceve = null; cerceveCiz(k);
    videoBagla(k); pipBagla(k); durumYaz(k);
  }

  // =================================================================
  // v2.4.210 — EKRAN BİLGİLERİ (OSD) AYAR PANELİ
  // Görüntü üzerine tarayıcıda çizilen bilgi katmanı; hangi alanların
  // görüneceği, köşe ve yazı boyu pencere başına saklanır. (Cihazın
  // kendi kareye bastığı yazı SDK üzerinden değiştirilemez; bkz. sürüm notu.)
  // =================================================================
  const OSD_ALANLAR = [["cihaz", "Cihaz adı"], ["saat", "Tarih / saat"], ["aci", "Azimut / eğim"], ["kanal", "Kanal"],
                       ["cozunurluk", "Çözünürlük · FPS"], ["konum", "Konum"], ["takip", "Takip durumu"], ["kayit", "Kayıt durumu"]];
  const OSD_VARSAYILAN = { acik: true, kose: "sol_ust", boy: 12, alanlar: { cihaz: true, saat: true, aci: true, kanal: true, cozunurluk: false, konum: false, takip: true, kayit: true } };
  function osdOku(k){ const v = yerel.oku("m50osd_" + k.eoId, null); return Object.assign({}, OSD_VARSAYILAN, v || {}, { alanlar: Object.assign({}, OSD_VARSAYILAN.alanlar, (v && v.alanlar) || {}) }); }
  function osdCiz(k){
    // v2.4.214 (kullanici: "katman var, ayarlar etkilemiyor"): ayar her
    // cizimde DEPODAN okunur; bellekteki nesne kimligine bagli hicbir yol
    // kalmadi. (2.4.211 duzeltmesi yayinli kodda dogrulandi; yine de
    // sahada etkisiz raporlandigi icin en dayanikli bicime cevrildi.)
    const a = osdOku(k); k.osd = a;
    let el = k.video.querySelector(".m50-pc-osd");
    if (!a.acik){ if (el) el.remove(); return; }
    if (!el){ el = document.createElement("div"); el.className = "m50-pc-osd"; k.video.appendChild(el); }
    el.className = "m50-pc-osd kose-" + a.kose; el.style.fontSize = a.boy + "px";
    const t = T(), c = eoKaydi(k.eoId), d = (c && c.m50_durum) || {}, kam = anaKamera(k);
    const takip = (c && (c.m50_takip || d.takip)) || {};
    const img = k.video.querySelector("img.kam-video");
    const sat = [];
    if (a.alanlar.cihaz) sat.push((c && c.isim) || ("M50 " + k.eoId));
    if (a.alanlar.saat){ const n = new Date(); sat.push(n.toLocaleDateString("tr-TR") + " " + n.toLocaleTimeString("tr-TR")); }
    if (a.alanlar.aci) sat.push("AZ " + (Number.isFinite(Number(d.azimut)) ? Number(d.azimut).toFixed(1) + "°" : "—") + "  EĞ " + (Number.isFinite(Number(d.egim)) ? Number(d.egim).toFixed(1) + "°" : "—"));
    if (a.alanlar.kanal) sat.push(k.anaKanal === "termal" ? (t.m50Termal || "Termal") : (t.m50Gorunur || "Görünür"));
    if (a.alanlar.cozunurluk) sat.push((img && img.naturalWidth ? img.naturalWidth + "×" + img.naturalHeight : "—") + "  ≤" + ((kam && kam.fps) || 15) + " fps");
    if (a.alanlar.konum && c && c.konum) sat.push((c.konum.kaynak === "rtk" ? "RTK " : "") + Number(c.konum.lat).toFixed(5) + ", " + Number(c.konum.lon).toFixed(5));
    if (a.alanlar.takip && (takip.etkin || k.aiTakip)) sat.push(k.aiTakip ? "● AI TAKİP " + (AI_TUR_AD[k.aiTakip.tur] || "") : "● TAKİP");
    const ky = kayitBul(kam);
    if (a.alanlar.kayit && ky) sat.push("● REC " + sureMetni(ky.sure_sn));
    el.textContent = ""; for (const m of sat){ const sp = document.createElement("span"); sp.textContent = m; el.appendChild(sp); }
  }
  function sureMetni(sn){ sn = Math.max(0, Math.round(Number(sn) || 0)); const d = Math.floor(sn / 60), s = sn % 60; return (d < 10 ? "0" : "") + d + ":" + (s < 10 ? "0" : "") + s; }
  // =================================================================
  // v2.4.215 — CİHAZ OSD'Sİ (SDK HVS_GetOsdInfo / HVS_SetOsdInfo)
  // Kullanıcı: "m50 sdk'sı ile görüntünün üzerine basılan OSD". Yapı
  // üreticinin datdefs.h dosyasından (OsdInfo_t) aktarıldı. Form, seçili
  // ana kanal için cihazdan okunur (telemetri: eo_cihazlar[].m50_osd[kanal])
  // ve "Cihaza yaz" ile geri yazılır. Değerler cihazda kalıcıdır.
  // =================================================================
  const OSDC_KONUM = [[0, "Sol üst"], [1, "Sağ üst"], [2, "Sol alt"], [3, "Sağ alt"], [4, "Gizli"], [5, "Özel"]];
  function osdCihazBolumDoldur(k, kap){
    const t = T();
    const oc = { girdi: {}, kirli: false, sonImza: "" };
    const satir = (etiket, el) => { const l = document.createElement(el.type === "checkbox" ? "label" : "div"); l.className = "m50-pc-ayar-satir";
      const s2 = document.createElement("span"); s2.textContent = etiket; if (el.type === "checkbox"){ l.append(el, s2); } else { l.append(s2, el); } kap.appendChild(l); return l; };
    const kirlet = el => el.addEventListener("input", () => { oc.kirli = true; });
    const secim = (ad, etiket, secenekler) => { const s = document.createElement("select"); s.className = "m50-pc-sb";
      for (const [v, e] of secenekler){ const o = document.createElement("option"); o.value = String(v); o.textContent = e; s.appendChild(o); }
      s.addEventListener("change", () => { oc.kirli = true; }); oc.girdi[ad] = s; satir(etiket, s); return s; };
    const kutu = (ad, etiket) => { const c = document.createElement("input"); c.type = "checkbox"; c.addEventListener("change", () => { oc.kirli = true; }); oc.girdi[ad] = c; satir(etiket, c); return c; };
    const metin = (ad, etiket, uz) => { const i = document.createElement("input"); i.type = "text"; i.maxLength = uz || 64; i.className = "m50-pc-sb"; kirlet(i); oc.girdi[ad] = i; satir(etiket, i); return i; };
    const baslik = (m) => { const h = document.createElement("div"); h.className = "m50-pc-osdc-baslik"; h.textContent = m; kap.appendChild(h); };
    const konum = (ad, etiket) => secim(ad, etiket, OSDC_KONUM.map(([v, e]) => [v, t["m50OsdcKonum" + v] || e]));
    const durumSatiri = document.createElement("p"); durumSatiri.className = "m50-pc-ayar-not"; oc.durum = durumSatiri; kap.appendChild(durumSatiri);
    baslik(t.m50OsdcAd || "KANAL ADI");
    metin("channelName", t.m50OsdcAdMetin || "Metin", 120);
    konum("namePos", t.m50OsdcKonumEtiket || "Konum");
    secim("channelNameAlign", t.m50OsdcHiza || "Hizalama", [[0, t.m50OsdcSol || "Sol"], [1, t.m50OsdcSag || "Sağ"]]);
    baslik(t.m50OsdcSaat || "TARİH / SAAT");
    konum("timePos", t.m50OsdcKonumEtiket || "Konum");
    secim("timeFormat", t.m50OsdcBicim || "Biçim", [[0, "yyyy-MM-dd"], [1, "dd/MM/yyyy"], [2, "MM/dd/yyyy"]]);
    secim("timeMode", t.m50OsdcSaatKip || "Saat", [[0, "24"], [1, "12"]]);
    kutu("displayWeek", t.m50OsdcHafta || "Haftanın günü");
    kutu("showMilliSec", t.m50OsdcOndalikSn || "1/10 saniye");
    baslik(t.m50OsdcPtz || "PTZ BİLGİSİ");
    konum("osdPtzPos", t.m50OsdcKonumEtiket || "Konum");
    kutu("displayPtz", t.m50OsdcAzimut || "Azimut (P/T)");
    kutu("displayPtzAngDir", t.m50OsdcAciYon || "Açı ve yön");
    kutu("displayFocalPos", t.m50OsdcOdak || "Odak konumu");
    kutu("displayFov", t.m50OsdcFov || "Görüş açısı");
    kutu("displayZoomTimes", t.m50OsdcZoom || "Büyütme (zoom)");
    kutu("displayTrackState", t.m50OsdcTakip || "Takip durumu");
    kutu("displayPtzState", t.m50OsdcPtzDurum || "PTZ durumu");
    secim("ptzAngleDecCount", t.m50OsdcOndalik || "Açı ondalık basamağı", [[0, "0"], [1, "1"], [2, "2"]]);
    baslik(t.m50OsdcPusula || "PUSULA / GPS");
    konum("osdCompassPos", t.m50OsdcKonumEtiket || "Konum");
    kutu("showCompass", t.m50OsdcPusulaGoster || "Pusula");
    kutu("showGPS", "GPS");
    kutu("displaySelfDefine", t.m50OsdcOzelMetin || "Özel metin");
    metin("radarInfo", t.m50OsdcOzelMetinIcerik || "Özel metin içeriği", 120);
    baslik(t.m50OsdcGenel || "GENEL");
    const fs = document.createElement("input"); fs.type = "range"; fs.min = "16"; fs.max = "64"; fs.step = "8"; kirlet(fs); oc.girdi.fontSize = fs;
    const fsDeger = document.createElement("b"); fsDeger.textContent = "";
    fs.addEventListener("input", () => { fsDeger.textContent = fs.value; });
    const fsSatir = document.createElement("div"); fsSatir.className = "m50-pc-ayar-satir"; const fsEt = document.createElement("span"); fsEt.textContent = t.m50OsdBoy || "Yazı boyu"; fsSatir.append(fsEt, fs, fsDeger); kap.appendChild(fsSatir); oc.fsDeger = fsDeger;
    metin("fontColor", t.m50OsdcYaziRengi || "Yazı rengi", 15);
    kutu("multiLine", t.m50OsdcCokSatir || "Çok satırlı");
    kutu("colorInvert", t.m50OsdcRenkTers || "Otomatik renk tersleme");
    kutu("cross", t.m50OsdcArti || "Artı (cross)");
    kutu("showGrid", t.m50OsdcIzgara || "Izgara");
    kutu("dpyLaserRange", t.m50OsdcLazer || "Lazer mesafe");
    const dgm = document.createElement("div"); dgm.className = "m50-pc-satir";
    const bOku = document.createElement("button"); bOku.type = "button"; bOku.className = "m50-pc-sb"; bOku.innerHTML = "<i class='fa-solid fa-rotate'></i><span>" + (t.m50OsdcOku || "Cihazdan oku") + "</span>";
    bOku.addEventListener("click", ev => { ev.stopPropagation(); oc.kirli = false; oc.sonImza = ""; osdCihazIste(k); });
    const bYaz = document.createElement("button"); bYaz.type = "button"; bYaz.className = "m50-pc-sb m50-pc-sb-tanima acik"; bYaz.innerHTML = "<i class='fa-solid fa-upload'></i><span>" + (t.m50OsdcYaz || "Cihaza yaz") + "</span>";
    bYaz.addEventListener("click", ev => { ev.stopPropagation(); osdCihazYaz(k); });
    dgm.append(bOku, bYaz); kap.appendChild(dgm);
    oc.bOku = bOku; oc.bYaz = bYaz;
    k.oc = oc;
  }
  function osdCihazIste(k){
    const c = eoKaydi(k.eoId), d = (c && c.m50_durum) || {};
    if (!d.bagli){ if (k.oc) k.oc.durum.textContent = T().m50OsdcBagliDegil || "Cihaz bağlı değil; OSD okunamaz."; return; }
    gonder({ tip: "m50_osd_oku", eo_id: k.eoId, kanal: k.anaKanal });
    if (k.oc) k.oc.durum.textContent = T().m50OsdcOkunuyor || "Cihazdan okunuyor…";
    k.ocIstek = Date.now();
  }
  function osdCihazDoldur(k){
    const oc = k.oc; if (!oc) return;
    const c = eoKaydi(k.eoId);
    const hepsi = c && c.m50_osd && typeof c.m50_osd === "object" ? c.m50_osd : null;
    const v = hepsi && hepsi[k.anaKanal];
    const t = T();
    if (!v){
      if (!k.ocIstek && c && c.m50_durum && c.m50_durum.bagli) osdCihazIste(k);
      else if (k.ocIstek && Date.now() - k.ocIstek > 8000) oc.durum.textContent = t.m50OsdcOkunamadi || "Cihazdan OSD bilgisi gelmedi.";
      return;
    }
    const imza = JSON.stringify(v);
    if (imza === oc.sonImza) return;
    if (oc.kirli) { oc.durum.textContent = t.m50OsdcYeniVar || "Cihazda yeni değer var; 'Cihazdan oku' ile yenileyin."; return; }
    oc.sonImza = imza;
    for (const ad of Object.keys(oc.girdi)){
      const el = oc.girdi[ad];
      let deger = v[ad];
      if (ad === "channelName") deger = Array.isArray(v.channelName) ? (v.channelName[0] || "") : (v.channelName || "");
      if (el.type === "checkbox") el.checked = !!deger;
      else if (el.tagName === "SELECT") el.value = String(deger == null ? 0 : deger);
      else el.value = deger == null ? "" : String(deger);
    }
    if (oc.fsDeger) oc.fsDeger.textContent = String(v.fontSize || "");
    oc.durum.textContent = (t.m50OsdcOkundu || "Cihazdan okundu") + " · " + (k.anaKanal === "termal" ? (t.m50Termal || "Termal") : (t.m50Gorunur || "Görünür"));
  }
  function osdCihazYaz(k){
    const oc = k.oc; if (!oc) return;
    const alanlar = {};
    for (const ad of Object.keys(oc.girdi)){
      const el = oc.girdi[ad];
      if (el.type === "checkbox") alanlar[ad] = !!el.checked;
      else if (el.tagName === "SELECT" || el.type === "range") alanlar[ad] = parseInt(el.value, 10) || 0;
      else alanlar[ad] = String(el.value || "");
    }
    alanlar.channelName = [alanlar.channelName];
    if (!alanlar.fontColor) delete alanlar.fontColor;
    oc.kirli = false; oc.sonImza = "";
    gonder({ tip: "m50_osd_yaz", eo_id: k.eoId, kanal: k.anaKanal, alanlar });
    oc.durum.textContent = T().m50OsdcYaziliyor || "Cihaza yazılıyor…";
    k.ocIstek = Date.now();
  }

  // v2.4.211: ekran bilgileri ayarları SOL PANELDE satır içi bölüm (popover değil)
  function osdBolumDoldur(k, kap){
    const t = T();
    const a = osdOku(k); k.osd = a;
    // KOK NEDEN (OSD ayari calismiyor): pencere kurulumu sonradan k.osd'yi
    // sifirliyordu; panelin duzenledigi nesne ile cizimin okudugu nesne
    // ayrisiyordu. Her kayitta ayni nesne yeniden baglanir.
    const kaydet = () => { k.osd = a; yerel.yaz("m50osd_" + k.eoId, a); osdCiz(k); if (typeof window.uyariGoster === "function") window.uyariGoster("M50", (T().m50OsdKaydedildi || "Ekran bilgileri güncellendi"), "bilgi"); };
    const satir = (etiket, el) => { const l = document.createElement("label"); l.className = "m50-pc-ayar-satir"; const s2 = document.createElement("span"); s2.textContent = etiket; l.append(el, s2); kap.appendChild(l); return l; };
    const cAcik = document.createElement("input"); cAcik.type = "checkbox"; cAcik.checked = !!a.acik;
    cAcik.addEventListener("change", () => { a.acik = cAcik.checked; kaydet(); });
    satir(t.m50OsdGoster || "Bilgi katmanını göster", cAcik);
    for (const [ad, etiket] of OSD_ALANLAR){
      const c = document.createElement("input"); c.type = "checkbox"; c.checked = !!a.alanlar[ad];
      c.addEventListener("change", () => { a.alanlar[ad] = c.checked; kaydet(); });
      satir(t["m50Osd_" + ad] || etiket, c);
    }
    const kose = document.createElement("select"); kose.className = "m50-pc-sb";
    for (const [v, e] of [["sol_ust", t.m50OsdSolUst || "Sol üst"], ["sag_ust", t.m50OsdSagUst || "Sağ üst"], ["sol_alt", t.m50OsdSolAlt || "Sol alt"], ["sag_alt", t.m50OsdSagAlt || "Sağ alt"]]){
      const o = document.createElement("option"); o.value = v; o.textContent = e; if (v === a.kose) o.selected = true; kose.appendChild(o); }
    kose.addEventListener("change", () => { a.kose = kose.value; kaydet(); });
    const lk = document.createElement("div"); lk.className = "m50-pc-ayar-satir"; const ek = document.createElement("span"); ek.textContent = t.m50OsdKose || "Köşe"; lk.append(ek, kose); kap.appendChild(lk);
    const boy = document.createElement("input"); boy.type = "range"; boy.min = "9"; boy.max = "24"; boy.value = String(a.boy);
    boy.addEventListener("input", () => { a.boy = parseInt(boy.value, 10) || 12; kaydet(); });
    const lb = document.createElement("div"); lb.className = "m50-pc-ayar-satir"; const eb = document.createElement("span"); eb.textContent = t.m50OsdBoy || "Yazı boyu"; lb.append(eb, boy); kap.appendChild(lb);
    const not_ = document.createElement("p"); not_.className = "m50-pc-ayar-not"; not_.textContent = t.m50OsdNot || "Cihazın kendi kareye bastığı yazılar (P/T açı, saat, Channel) SDK üzerinden değiştirilemez; bu katman Merkez'in çizdiği bilgilerdir.";
    kap.appendChild(not_);
  }

  // =================================================================
  // v2.4.210 — VİDEO KAYDI ve TANIMA HASSASİYETİ
  // =================================================================
  function kayitAcKapa(k){
    const kam = anaKamera(k); if (!kam) return;
    const ky = kayitBul(kam);
    if (ky) wsGonder({ tip: "video_kayit_durdur", kamera_id: kam.id });
    else { const c = eoKaydi(k.eoId); wsGonder({ tip: "video_kayit_baslat", kamera_id: kam.id, etiket: ((c && c.isim) || ("M50_" + k.eoId)) + "_" + k.anaKanal }); }
  }
  function hassasiyetOku(kam){
    let h = {}; try { h = kam && kam.ai_hassasiyet ? JSON.parse(kam.ai_hassasiyet) : {}; } catch (e) { h = {}; }
    if (!h || typeof h !== "object") h = {};
    const v = Number(h.hava_araci); return { h, deger: (isFinite(v) && v >= 10 && v <= 90) ? v : 50 };
  }
  function hassasiyetYaz(k, deger){
    const kam = anaKamera(k); if (!kam || typeof window.m50KameraAlanGuncelle !== "function") return;
    const { h } = hassasiyetOku(kam); h.hava_araci = Math.max(10, Math.min(90, Math.round(deger)));
    const json = JSON.stringify(h);
    kam.ai_hassasiyet = json;
    window.m50KameraAlanGuncelle(kam, { ai_hassasiyet: json });
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
    const kam = anaKamera(k) || k.kamera;
    const kanal = k.anaKanal;
    const img = k.video.querySelector("img.kam-video");
    const w = img ? img.naturalWidth : 0, h = img ? img.naturalHeight : 0;
    const isim = (c && c.isim) || ("M50 " + k.eoId);
    const etkin = !!takip.etkin;
    if (etkin) k.bekleniyor = 0;
    const bekliyor = k.bekleniyor && Date.now() - k.bekleniyor < 6000;
    if (!etkin && !bekliyor && k.cerceve && k.bekleniyor){ k.cerceve = null; k.bekleniyor = 0; cerceveCiz(k); }
    // --- kanal düğmeleri ---
    for (const b of k.kanalDgm) b.classList.toggle("aktif", b.dataset.kanal === kanal);
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
    // --- kayıt ---
    const ky = kayitBul(kam);
    k.sbKayit.querySelector("span").textContent = ky ? (t.m50KayitDurdur || "Durdur") + " " + sureMetni(ky.sure_sn) : (t.m50KayitBaslat || "Kaydet");
    k.sbKayit.classList.toggle("kayitta", !!ky);
    k.sbKayit.disabled = !kam;
    k.sbKayit.title = ky ? (ky.dosya || "") : (t.m50KayitIpucu || "Vekil akışını dosyaya kaydet (kayitlar/video)");
    k.sbKayitBilgi.textContent = ky ? (ky.dosya || "") + (ky.boyut ? "  ·  " + (ky.boyut / 1048576).toFixed(1) + " MB" : "") : (t.m50KayitYer || "kayitlar/video/");
    // --- küçük görüntü ---
    k.sbPip.querySelector("span").textContent = k.pipAcik ? (t.m50AiAcik || "Açık") : (t.m50AiKapaliKisa || "Kapalı");
    k.sbPip.classList.toggle("acik", !!k.pipAcik);
    // --- hassasiyet ---
    if (document.activeElement !== k.sbHassas){ const hs = hassasiyetOku(kam); k.sbHassas.value = String(hs.deger); k.sbHassasDeger.textContent = String(hs.deger); }
    k.sbHassasKap.style.display = aiAktifMi(kam) ? "" : "none";
    osdCiz(k);
    if (k.pip) pipBagla(k);
    osdCihazDoldur(k);
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
    // v2.4.214: calisan arayuz surumu basligta — saha "eski kod mu?" sorusunu aninda yanitlar
    const rozetSurum = document.createElement("span"); rozetSurum.className = "m50-pc-rozet surum";
    rozetSurum.textContent = "v" + ((typeof GCS_SURUM === "string" && GCS_SURUM) || (window.GCS_SURUM || "?"));
    rozetSurum.title = "Arayüz sürümü (js/m50_pencere.js)";
    const kapat = document.createElement("button"); kapat.type = "button"; kapat.className = "m50-pc-kapat";
    kapat.title = t.m50PcKapat || "Pencereyi kapat"; kapat.innerHTML = "<i class='fa-solid fa-xmark'></i>";
    kapat.addEventListener("click", ev => { ev.stopPropagation(); window.m50PencereKapat(eoId); });
    baslik.append(ikon, ad, rozetSurum, rozetKanal, rozetBag, rozetTakip, kapat);
    // v2.4.211 (kullanıcı isteği): pencere İKİYE bölündü — SOL 300 px kontrol
    // paneli (tüm özellikler alt alta), SAĞ görüntü. Durum çubuğu kaldırıldı.
    const govde = document.createElement("div"); govde.className = "m50-pc-govde";
    const sol = document.createElement("div"); sol.className = "m50-pc-sol";
    const video = document.createElement("div"); video.className = "m50-pc-video";
    // v2.4.213 (kullanıcı isteği): sol panel genişliği AYRAÇ ile değiştirilir, hatırlanır
    const ayrac = document.createElement("div"); ayrac.className = "m50-pc-ayrac"; ayrac.title = t.m50AyracIpucu || "Sürükle: sol panel genişliği (çift tık: 300 px)";
    ayrac.innerHTML = "<i class='fa-solid fa-grip-lines-vertical'></i>";
    const solGen = Number(yerel.oku("m50sol_" + eoId, 300)) || 300;
    sol.style.flexBasis = sol.style.width = Math.max(220, Math.min(700, solGen)) + "px";
    let ayr = null;
    ayrac.addEventListener("pointerdown", ev => { ayr = { x: ev.clientX, w: sol.getBoundingClientRect().width }; ayrac.setPointerCapture(ev.pointerId); ev.preventDefault(); ev.stopPropagation(); });
    ayrac.addEventListener("pointermove", ev => {
      if (!ayr) return;
      const enCok = Math.max(220, p.getBoundingClientRect().width - 260);
      const w = Math.max(220, Math.min(enCok, ayr.w + (ev.clientX - ayr.x)));
      sol.style.flexBasis = sol.style.width = w + "px";
      cerceveCiz(k);
    });
    const ayrBitir = () => { if (!ayr) return; ayr = null; yerel.yaz("m50sol_" + eoId, Math.round(sol.getBoundingClientRect().width)); };
    ayrac.addEventListener("pointerup", ayrBitir); ayrac.addEventListener("pointercancel", ayrBitir);
    ayrac.addEventListener("dblclick", ev => { ev.stopPropagation(); sol.style.flexBasis = sol.style.width = "300px"; yerel.yaz("m50sol_" + eoId, 300); });
    govde.append(sol, ayrac, video);
    k.anaKanal = yerel.oku("m50kanal_" + eoId, "gorunur") === "termal" ? "termal" : "gorunur";
    k.pipAcik = !!yerel.oku("m50pip_" + eoId, false);
    const bolum = (baslikMetin, ikon, acik) => {
      const d = document.createElement("details"); d.className = "m50-pc-bolum"; d.open = acik !== false;
      const sm = document.createElement("summary"); sm.innerHTML = "<i class='fa-solid " + ikon + "'></i> " + baslikMetin; d.appendChild(sm);
      const ic = document.createElement("div"); ic.className = "m50-pc-bolum-ic"; d.appendChild(ic);
      const anahtar = "m50bolum_" + eoId + "_" + ikon; try { const v = localStorage.getItem(anahtar); if (v !== null) d.open = v === "1"; } catch (e) {}
      d.addEventListener("toggle", () => { try { localStorage.setItem(anahtar, d.open ? "1" : "0"); } catch (e) {} });
      sol.appendChild(d); return ic;
    };
    const dugme = (sinif, ikon, metin) => { const b = document.createElement("button"); b.type = "button"; b.className = "m50-pc-sb " + sinif;
      b.innerHTML = "<i class='fa-solid " + ikon + "'></i><span>" + (metin || "") + "</span>"; return b; };
    // KANAL
    const bKanal = bolum(t.m50PcKanal || "Kanal", "fa-sun");
    const kanalSatir = document.createElement("div"); kanalSatir.className = "m50-pc-satir";
    const kanalDgm = [];
    for (const [kn, ik, et] of [["gorunur", "fa-sun", t.m50Gorunur || "Görünür"], ["termal", "fa-fire", t.m50Termal || "Termal"]]){
      const b = dugme("m50-pc-sb-kanal", ik, et); b.dataset.kanal = kn;
      b.addEventListener("click", ev => { ev.stopPropagation(); if (k.anaKanal !== kn) kanalDegistir(k); });
      kanalSatir.appendChild(b); kanalDgm.push(b);
    }
    bKanal.appendChild(kanalSatir);
    // ÇÖZÜNÜRLÜK
    const bGen = bolum(t.m50PcCozunurluk || "Çözünürlük", "fa-expand");
    const sbGen = document.createElement("select"); sbGen.className = "m50-pc-sb m50-pc-sb-gen";
    sbGen.title = t.m50PcGenIpucu || "Vekil çıktı genişliği; değiştirince akış yeniden kurulur";
    sbGen.addEventListener("change", ev => {
      ev.stopPropagation();
      const kam = anaKamera(k);
      if (!kam || typeof window.m50KameraAlanGuncelle !== "function") return;
      window.m50KameraAlanGuncelle(kam, { genislik: parseInt(sbGen.value, 10) || 960 });
      setTimeout(() => videoBagla(k), 800);
    });
    const sbGenOlcu = document.createElement("small"); sbGenOlcu.className = "m50-pc-olcu";
    const genSatir = document.createElement("div"); genSatir.className = "m50-pc-satir"; genSatir.append(sbGen, sbGenOlcu); bGen.appendChild(genSatir);
    // TANIMA + HASSASİYET
    const bTanima = bolum(t.m50AiTanima || "Tanıma", "fa-plane");
    const sbTanima = dugme("m50-pc-sb-tanima", "fa-plane");
    sbTanima.addEventListener("click", ev => { ev.stopPropagation(); aiTanimaAcKapa(k); });
    const tanSatir = document.createElement("div"); tanSatir.className = "m50-pc-satir"; tanSatir.appendChild(sbTanima); bTanima.appendChild(tanSatir);
    const sbHassasKap = document.createElement("div"); sbHassasKap.className = "m50-pc-hassas m50-pc-satir";
    const hEt = document.createElement("span"); hEt.textContent = (t.m50Hassasiyet || "Hassasiyet");
    const sbHassas = document.createElement("input"); sbHassas.type = "range"; sbHassas.min = "10"; sbHassas.max = "90"; sbHassas.step = "5"; sbHassas.value = "50";
    sbHassas.title = t.m50HassasIpucu || "Tanıma hassasiyeti (10 düşük … 90 yüksek)";
    const sbHassasDeger = document.createElement("b"); sbHassasDeger.textContent = "50";
    let hzaman = null;
    sbHassas.addEventListener("input", () => { sbHassasDeger.textContent = sbHassas.value; clearTimeout(hzaman); hzaman = setTimeout(() => hassasiyetYaz(k, parseInt(sbHassas.value, 10)), 400); });
    sbHassasKap.append(hEt, sbHassas, sbHassasDeger); bTanima.appendChild(sbHassasKap);
    const tanNot = document.createElement("p"); tanNot.className = "m50-pc-ayar-not"; tanNot.textContent = t.m50AiAcIpucu || "Tespit kutusuna çift tık: takip"; bTanima.appendChild(tanNot);
    // TAKİP
    const bTakip = bolum(t.m50PcTakip || "Takip", "fa-crosshairs");
    const sbTakip = dugme("m50-pc-sb-takip", "fa-crosshairs");
    sbTakip.addEventListener("click", ev => { ev.stopPropagation(); if (k.takipte) takipDurdur(k); else hedefSec(k); });
    const takSatir = document.createElement("div"); takSatir.className = "m50-pc-satir"; takSatir.appendChild(sbTakip); bTakip.appendChild(takSatir);
    const sbIpucu = document.createElement("p"); sbIpucu.className = "m50-pc-ipucu"; sbIpucu.style.display = "none"; bTakip.appendChild(sbIpucu);
    // KAYIT
    const bKayit = bolum(t.m50Kayit || "Kayıt", "fa-circle");
    const sbKayit = dugme("m50-pc-sb-kayit", "fa-circle");
    sbKayit.addEventListener("click", ev => { ev.stopPropagation(); kayitAcKapa(k); });
    const kaySatir = document.createElement("div"); kaySatir.className = "m50-pc-satir"; kaySatir.appendChild(sbKayit); bKayit.appendChild(kaySatir);
    const sbKayitBilgi = document.createElement("p"); sbKayitBilgi.className = "m50-pc-ayar-not"; bKayit.appendChild(sbKayitBilgi);
    // KÜÇÜK GÖRÜNTÜ
    const bPip = bolum(t.m50Pip || "Küçük görüntü", "fa-clone");
    const sbPip = dugme("m50-pc-sb-pip", "fa-clone");
    sbPip.title = t.m50PipIpucu || "Diğer kanalı (gündüz ⇄ gece) küçük pencerede göster";
    sbPip.addEventListener("click", ev => { ev.stopPropagation(); pipAcKapa(k); });
    const pipSatir = document.createElement("div"); pipSatir.className = "m50-pc-satir"; pipSatir.appendChild(sbPip); bPip.appendChild(pipSatir);
    // CİHAZ OSD'Sİ (SDK)
    const bOsdc = bolum(t.m50OsdcBaslik || "Cihaz OSD'si", "fa-font", false);
    osdCihazBolumDoldur(k, bOsdc);
    // MERKEZ BİLGİ KATMANI
    const bOsd = bolum(t.m50OsdBaslik || "Merkez bilgi katmanı", "fa-sliders", false);
    osdBolumDoldur(k, bOsd);
    p.append(baslik, govde);
    Object.assign(k, { pencere: p, baslik, video, sol, ad, rozetKanal, rozetBag, rozetTakip,
                       kanalDgm, sbGen, sbGenOlcu, sbTanima, sbHassasKap, sbHassas, sbHassasDeger, sbKayit, sbKayitBilgi, sbPip, sbTakip, sbIpucu,
                       takipte: false, aiTakip: null, aiZaman: null, pip: null, pipEtiket: null });
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
    if (k.pipAcik){ k.pipAcik = false; pipAcKapa(k, true); }
    durumYaz(k);
    wsGonder({ tip: "video_kayit_durum" });
    k.osdSaat = setInterval(() => { if (!p.isConnected){ clearInterval(k.osdSaat); return; } const o = osdOku(k); if (o.acik && o.alanlar.saat) osdCiz(k); }, 1000);
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
    if (k.pip){ const im = k.pip.querySelector("img"); if (im) im.removeAttribute("src"); }
    clearInterval(k.osdSaat);
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
      const kam = anaKamera(k);
      const img = k.video.querySelector("img.kam-video");
      const eski = img ? Number(img.dataset.kameraId) : 0;
      if ((kam && kam.id !== eski) || (!kam && eski) || (kam && kam.url !== (k.kamera && k.kamera.url))) videoBagla(k);
      k.kamera = kam || k.kamera;
      if (k.pip) pipBagla(k);
    }
  };
})();
