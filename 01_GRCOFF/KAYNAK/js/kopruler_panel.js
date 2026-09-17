// =================================================================
// GOKTUNGU - KOPRULER PANELI (Destek > Kopruler)  v2.4.232
// -----------------------------------------------------------------
// Kullanici istegi (2026-09-17, birebir):
//   "Yardim menusune Kopruler diye bir dugme koyalim, bu dugmeye
//    basinca bizim standart veri listeleme panelimizde kopruler
//    listelensin, yeni kopru kaydi olusturulsun kopruye bir isim
//    verebilelim, yeni koprude sadece kopru ismini sorsun, olusturulunca
//    bir API kodu olustursun, bu kodu listedeyken kopyalayabilsin ...
//    Kopruler modulunu actigimizda hangi moduller online ise listede
//    onlari sik bir sekilde gostersin, diger tum modullerden kopru
//    gruplamasi kalksin, en saginda hangi kopruye bagli onu gostersin"
//
// Kip BAGIMSIZDIR: merkezde (GRCON) kayit merkez veritabanindadir,
// yerel kipte (GRCOFF) `yerel_kopruler` tablosundadir. Sunucu
// `kopruler_liste / kopru_olustur / kopru_sil / kopru_kod_yenile`
// komutlarina tek bicimde `{tip:"kopruler", liste:[..]}` yanitlar.
//
// API kodu SIRRI tasir; sunucu onu yalniz kopru ilk kez baglanana
// kadar saklar ve yalniz yoneticiye gonderir. Kod tuketildiyse
// "Kodu yenile" yeni sir uretir.
// =================================================================
(function () {
  "use strict";

  const T = () => (typeof D === "function" ? D() : {});
  const ARALIK_MS = 10000;
  const SERVIS_SIRA = ["dron", "ai", "video", "gcsdual", "radar", "m50"];
  const SERVIS_IKON = { dron: "fa-plane-up", ai: "fa-brain", video: "fa-video",
                        gcsdual: "fa-gamepad", radar: "fa-satellite-dish",
                        m50: "fa-binoculars" };

  let liste = [];
  let merkezKipi = false;
  let acikKodlar = new Set();      // ornek_id -> kod kutusu acik
  let sonYeniId = null;            // az once olusturulan kayit (kod kutusu acilir)
  let zaman = null;

  const panel = () => document.getElementById("yzKopruler");
  const kok = () => document.getElementById("koprulerListe");
  const gorunur = () => { const p = panel(); return !!(p && !p.classList.contains("yuzen-gizli")); };
  const yonetici = () => (typeof oturumYoneticiMi === "function") ? !!oturumYoneticiMi() : false;

  function gonder(paket) {
    if (typeof ws === "undefined" || !ws || ws.readyState !== 1) return false;
    ws.send(JSON.stringify(paket));
    return true;
  }
  function toast(seviye, mesaj) {
    if (typeof window.uyariToastGoster === "function")
      window.uyariToastGoster({ kategori: "KÖPRÜ", seviye: seviye, mesaj: mesaj });
  }
  function servisEtiket(ad) {
    const t = T();
    const k = "kpServis" + ad.charAt(0).toUpperCase() + ad.slice(1);
    return t[k] || ({ dron: "Dron", ai: "AI", video: "Video", gcsdual: "GroundGCC",
                      radar: "Radar", m50: "M50" }[ad] || ad);
  }
  function zamanMetni(ts) {
    if (!ts) return "";
    const d = new Date(ts);
    if (isNaN(d.getTime())) return String(ts);
    const fark = Math.max(0, Math.round((Date.now() - d.getTime()) / 1000));
    if (fark < 60) return fark + " sn";
    if (fark < 3600) return Math.round(fark / 60) + " dk";
    if (fark < 86400) return Math.round(fark / 3600) + " sa";
    return d.toLocaleDateString();
  }

  // -----------------------------------------------------------------
  // Panoya kopyalama: guvenli baglam (https/localhost) disinda
  // navigator.clipboard YOKTUR (LAN IP uzerinden http). Yedek yol
  // gizli textarea + execCommand; o da olmazsa kod kutusu acilir ve
  // kullanici elle secer.
  // -----------------------------------------------------------------
  function panoyaKopyala(metin) {
    return new Promise((coz) => {
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(metin).then(() => coz(true), () => coz(yedekKopyala(metin)));
        return;
      }
      coz(yedekKopyala(metin));
    });
  }
  function yedekKopyala(metin) {
    try {
      const ta = document.createElement("textarea");
      ta.value = metin; ta.setAttribute("readonly", "");
      ta.style.position = "fixed"; ta.style.left = "-9999px";
      document.body.appendChild(ta); ta.select();
      const ok = document.execCommand && document.execCommand("copy");
      document.body.removeChild(ta);
      return !!ok;
    } catch (e) { return false; }
  }

  // -----------------------------------------------------------------
  // Servis (modul) cipleri — "hangi moduller online" sik gosterim
  // -----------------------------------------------------------------
  function servisCipleri(k) {
    const t = T();
    const kap = document.createElement("div");
    kap.className = "kp-servisler";
    if (!k.cevrimici) {
      const n = document.createElement("span");
      n.className = "kp-servis-yok";
      n.textContent = t.kpCevrimdisi || "Çevrimdışı";
      kap.appendChild(n);
      return kap;
    }
    const gelen = new Map();
    for (const s of (k.servisler || [])) {
      const ad = String((s && (s.ad || s.servis)) || "").toLowerCase();
      if (ad) gelen.set(ad, s);
    }
    if (!gelen.size) {
      const n = document.createElement("span");
      n.className = "kp-servis-yok";
      n.textContent = t.kpServisYok || "Servis bilgisi yok";
      if (k.servis_hata) n.title = k.servis_hata;
      kap.appendChild(n);
      return kap;
    }
    const sira = SERVIS_SIRA.filter((a) => gelen.has(a))
      .concat([...gelen.keys()].filter((a) => SERVIS_SIRA.indexOf(a) < 0));
    for (const ad of sira) {
      const s = gelen.get(ad);
      const durum = String((s && s.durum) || "").toLowerCase();
      const calisiyor = !!(s && (s.calisiyor === true || durum === "calisiyor" || durum === "acik"));
      const cip = document.createElement("span");
      cip.className = "kp-servis " + (calisiyor ? "acik" : "kapali");
      cip.innerHTML = "<i class='fa-solid " + (SERVIS_IKON[ad] || "fa-circle") + "'></i>";
      const e = document.createElement("span"); e.textContent = servisEtiket(ad);
      cip.appendChild(e);
      cip.title = servisEtiket(ad) + ": " + (calisiyor ? (t.bagServisCalisiyor || "Çalışıyor") : (t.bagServisDurdu || "Durdu"));
      kap.appendChild(cip);
    }
    return kap;
  }

  // -----------------------------------------------------------------
  // Liste cizimi (standart .cl-liste / .cl-satir deseni)
  // -----------------------------------------------------------------
  function listeCiz() {
    const el = kok();
    if (!el) return;
    const t = T();
    const yon = yonetici();
    el.innerHTML = "";
    if (!liste.length) {
      const bos = document.createElement("div");
      bos.className = "cl-bos";
      bos.textContent = t.kpBos || "Kayıtlı köprü yok. \"Yeni Köprü\" ile bir kayıt oluşturun; üretilen API kodunu köprü yazılımının kurulumunda girin.";
      el.appendChild(bos);
      return;
    }
    for (const k of liste) {
      const oid = String(k.ornek_id);
      const sat = document.createElement("div");
      sat.className = "cl-satir kp-satir " + (k.cevrimici ? "kp-cevrimici" : "kp-cevrimdisi");
      sat.dataset.ornekId = oid;

      const benek = document.createElement("span");
      benek.className = "kp-benek" + (k.cevrimici ? " acik" : "");
      benek.title = k.cevrimici ? (t.kpCevrimici || "Çevrimiçi") : (t.kpCevrimdisi || "Çevrimdışı");
      sat.appendChild(benek);

      const govde = document.createElement("div");
      govde.className = "cl-govde";
      const ad = document.createElement("div");
      ad.className = "cl-ad";
      ad.textContent = k.ad || ("#" + oid);
      const rozet = document.createElement("span");
      rozet.className = "kp-rozet " + (k.cevrimici ? "acik" : "kapali");
      rozet.textContent = k.cevrimici ? (t.kpCevrimici || "Çevrimiçi") : (t.kpCevrimdisi || "Çevrimdışı");
      ad.appendChild(rozet);
      const alt = document.createElement("div");
      alt.className = "cl-alt";
      const parcalar = [];
      if (k.ip) parcalar.push("IP " + k.ip);
      if (k.makine_adi) parcalar.push(k.makine_adi);
      if (k.surum) parcalar.push("v" + k.surum);
      if (k.platform) parcalar.push(k.platform);
      if (!k.cevrimici && k.son_gorulme_ts) parcalar.push((t.kpSonGorulme || "son görülme") + " " + zamanMetni(k.son_gorulme_ts));
      alt.textContent = parcalar.length ? parcalar.join("  ·  ") : (t.kpHenuzBaglanmadi || "Henüz hiç bağlanmadı");
      govde.appendChild(ad); govde.appendChild(alt);
      govde.appendChild(servisCipleri(k));
      sat.appendChild(govde);

      const dgm = document.createElement("div");
      dgm.className = "cl-dgm";
      const kodVar = !!(k.api_kodu);
      if (yon) {
        if (kodVar) {
          const bKopya = document.createElement("button");
          bKopya.type = "button"; bKopya.className = "kucuk ikincil kp-kopyala";
          bKopya.title = t.kpKodKopyala || "API kodunu kopyala";
          bKopya.innerHTML = "<i class='fa-solid fa-copy'></i>";
          bKopya.addEventListener("click", (ev) => {
            ev.stopPropagation();
            panoyaKopyala(k.api_kodu).then((ok) => {
              if (ok) { toast("bilgi", t.kpKodKopyalandi || "API kodu panoya kopyalandı"); }
              else { acikKodlar.add(oid); listeCiz(); toast("uyari", t.kpKodKopyalanamadi || "Panoya kopyalanamadı; kodu kutudan seçip kopyalayın"); }
            });
          });
          const bGoster = document.createElement("button");
          bGoster.type = "button"; bGoster.className = "kucuk ikincil kp-goster";
          bGoster.title = t.kpKodGoster || "API kodunu göster/gizle";
          bGoster.innerHTML = "<i class='fa-solid fa-eye'></i>";
          bGoster.addEventListener("click", (ev) => {
            ev.stopPropagation();
            if (acikKodlar.has(oid)) acikKodlar.delete(oid); else acikKodlar.add(oid);
            listeCiz();
          });
          dgm.appendChild(bKopya); dgm.appendChild(bGoster);
        } else {
          const bYenile = document.createElement("button");
          bYenile.type = "button"; bYenile.className = "kucuk ikincil kp-yenile";
          bYenile.title = t.kpKodYenile || "API kodunu yenile (yeni sır üretir; bağlı köprü düşer)";
          bYenile.innerHTML = "<i class='fa-solid fa-rotate'></i>";
          bYenile.addEventListener("click", (ev) => {
            ev.stopPropagation();
            const soru = (t.kpYenileOnay || "{ad} için yeni API kodu üretilecek; bağlıysa bağlantısı kesilir ve köprü yeni kodla yeniden kurulmalıdır. Devam edilsin mi?").replace("{ad}", k.ad || ("#" + oid));
            const yap = () => { sonYeniId = oid; gonder({ tip: "kopru_kod_yenile", ornek_id: k.ornek_id }); };
            if (typeof window.onayIste === "function") window.onayIste(soru, yap); else if (window.confirm(soru)) yap();
          });
          dgm.appendChild(bYenile);
        }
        const bSil = document.createElement("button");
        bSil.type = "button"; bSil.className = "kucuk tehlike ikincil kp-sil";
        bSil.title = t.kpSil || "Köprüyü sil";
        bSil.innerHTML = "<i class='fa-solid fa-trash'></i>";
        bSil.addEventListener("click", (ev) => {
          ev.stopPropagation();
          const soru = (k.cevrimici ? (t.bagKopruSilOnayCanli || "{ad} şu anda ÇEVRİMİÇİ. Kayıt silinirse bağlantısı kesilir ve aynı kimlikle yeniden bağlanamaz. Devam edilsin mi?")
                                    : (t.kpSilOnay || "{ad} silinecek; bu köprü aynı kimlikle yeniden bağlanamaz. Devam edilsin mi?")).replace("{ad}", k.ad || ("#" + oid));
          const yap = () => gonder({ tip: "kopru_sil", ornek_id: k.ornek_id });
          if (typeof window.onayIste === "function") window.onayIste(soru, yap); else if (window.confirm(soru)) yap();
        });
        dgm.appendChild(bSil);
      }
      sat.appendChild(dgm);
      el.appendChild(sat);

      // Kod kutusu (satirin altinda, yalniz yoneticiye ve kod varsa)
      if (yon && kodVar && acikKodlar.has(oid)) {
        const kutu = document.createElement("div");
        kutu.className = "kp-kod-kutu";
        const not = document.createElement("div");
        not.className = "kp-kod-not";
        not.textContent = t.kpKodNot || "Bu kodu köprü yazılımının ilk kurulum ekranına yapıştırın. Köprü ilk kez bağlanınca kod güvenlik için silinir.";
        const ta = document.createElement("textarea");
        ta.className = "kp-kod"; ta.readOnly = true; ta.spellcheck = false;
        ta.value = k.api_kodu; ta.rows = 3;
        ta.addEventListener("click", () => ta.select());
        kutu.appendChild(not); kutu.appendChild(ta);
        el.appendChild(kutu);
      }
    }
  }

  // -----------------------------------------------------------------
  // Sunucu yaniti
  // -----------------------------------------------------------------
  window.koprulerPanelIsle = function (m) {
    const t = T();
    if (typeof m.merkez_kipi === "boolean") merkezKipi = m.merkez_kipi;
    if (!m.basarili) {
      toast("hata", (t.kpHata || "Köprü işlemi başarısız: ") + (m.hata || "?"));
      if (Array.isArray(m.liste)) { liste = m.liste; listeCiz(); }
      return;
    }
    liste = Array.isArray(m.liste) ? m.liste : [];
    if (m.komut === "kopru_olustur" && m.yeni && m.yeni.ornek_id != null) {
      acikKodlar.add(String(m.yeni.ornek_id));
      toast("bilgi", (t.kpOlusturuldu || "Köprü oluşturuldu: ") + (m.yeni.ad || ""));
    } else if (m.komut === "kopru_kod_yenile" && m.yeni && m.yeni.ornek_id != null) {
      acikKodlar.add(String(m.yeni.ornek_id));
      toast("bilgi", (t.kpKodYenilendi || "API kodu yenilendi: ") + (m.yeni.ad || ("#" + m.yeni.ornek_id)));
    } else if (m.komut === "kopru_sil") {
      toast("bilgi", t.kpSilindi || "Köprü silindi.");
    }
    if (m.komut && m.komut !== "kopruler_liste" && typeof window.bagKopruListesiIste === "function")
      window.bagKopruListesiIste();   // diger panellerin kopru rozetleri tazelensin
    listeCiz();
  };

  function iste() { if (gorunur()) gonder({ tip: "kopruler_liste" }); }

  // -----------------------------------------------------------------
  // Diger panellerin satir sonunda gosterdigi "bagli oldugu kopru"
  // rozeti (Baglanti Yoneticisi / Kameralar / AI Sunuculari).
  // Kopru adi ve durumu seri.js'deki ortak kopru deposundan cozulur.
  // -----------------------------------------------------------------
  window.kopruRozetOlustur = function (ornekId) {
    if (ornekId == null || ornekId === "" || Number(ornekId) <= 0) return null;
    const t = T();
    const k = (typeof window.kopruAdCoz === "function") ? window.kopruAdCoz(ornekId) : null;
    const el = document.createElement("span");
    el.className = "kopru-rozet " + (k ? (k.cevrimici ? "cevrimici" : "cevrimdisi") : "bilinmiyor");
    el.innerHTML = "<i class='fa-solid fa-diagram-project'></i>";
    const ad = document.createElement("span");
    ad.textContent = (k && k.ad) ? k.ad : ("#" + ornekId);
    el.appendChild(ad);
    el.title = (t.kopruRozetBaslik || "Bağlı olduğu köprü") + ": " + ad.textContent +
      (k ? ("  ·  " + (k.cevrimici ? (t.kpCevrimici || "Çevrimiçi") : (t.kpCevrimdisi || "Çevrimdışı"))) : "");
    return el;
  };

  // -----------------------------------------------------------------
  // Form: yalniz AD
  // -----------------------------------------------------------------
  const ac = (id) => { if (typeof window.yuzenPanelAc === "function") window.yuzenPanelAc(id); else { const p = document.getElementById(id); if (p) p.classList.remove("yuzen-gizli"); } };
  const kapat = (id) => { const p = document.getElementById(id); if (p) p.classList.add("yuzen-gizli"); };

  window.kopruFormuAc = function () {
    const t = T();
    const gi = document.getElementById("kfAd");
    if (!gi) return;
    gi.value = (t.kpYeniAd || "Köprü") + " " + (liste.length + 1);
    if (t.kpAdYer) gi.placeholder = t.kpAdYer;
    ac("yzKopruForm");
    setTimeout(() => { gi.focus(); gi.select(); }, 50);
  };

  function bagla() {
    const yeni = document.getElementById("btnKopruYeni");
    if (yeni) yeni.addEventListener("click", () => window.kopruFormuAc());
    const kaydet = document.getElementById("btnKopruFormKaydet");
    if (kaydet) kaydet.addEventListener("click", () => {
      const gi = document.getElementById("kfAd");
      const ad = gi ? gi.value.trim() : "";
      if (!ad) { if (gi) gi.focus(); return; }
      if (gonder({ tip: "kopru_olustur", ad: ad })) kapat("yzKopruForm");
    });
    const gi = document.getElementById("kfAd");
    if (gi) gi.addEventListener("keydown", (ev) => { if (ev.key === "Enter") { ev.preventDefault(); if (kaydet) kaydet.click(); } });
    const iptal = document.getElementById("btnKopruFormIptal");
    if (iptal) iptal.addEventListener("click", () => kapat("yzKopruForm"));

    // Panel acilinca taze liste; acikken periyodik tazeleme.
    const p = panel();
    if (p && typeof MutationObserver === "function") {
      let onceki = gorunur();
      new MutationObserver(() => {
        const simdi = gorunur();
        if (simdi && !onceki) iste();
        onceki = simdi;
      }).observe(p, { attributes: true, attributeFilter: ["class"] });
    }
    if (zaman === null) zaman = setInterval(iste, ARALIK_MS);
    listeCiz();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bagla);
  else bagla();
})();
