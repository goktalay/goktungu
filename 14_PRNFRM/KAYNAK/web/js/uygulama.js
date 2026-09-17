/* PRNFRM arayüzü — bağımlılıksız, tek dosya. */
(function () {
  "use strict";

  const DURUM_AD = {
    basiyor: "Basıyor", bosta: "Boşta", duraklatildi: "Duraklatıldı", tamamlandi: "Tamamlandı",
    hata: "Hata", hazirlaniyor: "Hazırlanıyor", cevrimdisi: "Çevrimdışı",
  };
  const DURUM_SIRA = ["basiyor", "duraklatildi", "hata", "hazirlaniyor", "tamamlandi", "bosta", "cevrimdisi"];

  const $ = (s, k) => (k || document).querySelector(s);
  const $$ = (s, k) => Array.from((k || document).querySelectorAll(s));

  const st = { yazicilar: new Map(), olaylar: [], tarama: null, acikYazici: null, ws: null };

  // ---------- yardımcılar ----------
  function kacis(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function sure(sn) {
    if (sn == null || isNaN(sn)) return "–";
    sn = Math.max(0, Math.round(sn));
    const s = Math.floor(sn / 3600), d = Math.floor((sn % 3600) / 60);
    return s ? `${s} sa ${d} dk` : `${d} dk`;
  }
  function saat(ts) {
    const t = new Date(ts * 1000);
    return t.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }
  function derece(v, hedef) {
    if (v == null) return "–";
    const a = Number(v).toFixed(0) + "°";
    return hedef ? `${a}/${Number(hedef).toFixed(0)}°` : a;
  }
  function bildir(m, sure_ms) {
    const b = $("#bildirim"); b.textContent = m; b.hidden = false;
    clearTimeout(bildir._t); bildir._t = setTimeout(() => { b.hidden = true; }, sure_ms || 3000);
  }
  async function api(yol, secenek) {
    const r = await fetch(yol, Object.assign({ headers: { "Content-Type": "application/json" } }, secenek || {}));
    let veri = {};
    try { veri = await r.json(); } catch (e) { /* boş gövde */ }
    if (!r.ok) throw new Error(veri.hata || (r.status + " " + r.statusText));
    return veri;
  }
  const post = (yol, govde) => api(yol, { method: "POST", body: JSON.stringify(govde || {}) });
  const put = (yol, govde) => api(yol, { method: "PUT", body: JSON.stringify(govde || {}) });
  const del = (yol) => api(yol, { method: "DELETE" });

  // ---------- WebSocket ----------
  function wsBaglan() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws`);
    st.ws = ws;
    ws.onopen = () => rozet(true);
    ws.onclose = () => { rozet(false); setTimeout(wsBaglan, 2000); };
    ws.onerror = () => ws.close();
    ws.onmessage = (e) => {
      let m; try { m = JSON.parse(e.data); } catch (err) { return; }
      if (m.tur === "anlik") {
        st.yazicilar = new Map(m.yazicilar.map(y => [y.id, y]));
        st.olaylar = m.olaylar || [];
        st.tarama = m.tarama;
        cizHepsi(); cizOlaylar(); taramaGuncelle();
      } else if (m.tur === "yazici") {
        st.yazicilar.set(m.yazici.id, m.yazici);
        cizKart(m.yazici); cizSayaclar(); cizGruplar();
        if (st.acikYazici === m.yazici.id) ayrintiDoldur(m.yazici);
      } else if (m.tur === "yazici_silindi") {
        st.yazicilar.delete(m.id); cizHepsi();
        if (st.acikYazici === m.id) kapat("ortu-ayrinti");
      } else if (m.tur === "olay") {
        st.olaylar.unshift(m.olay); st.olaylar = st.olaylar.slice(0, 200); cizOlaylar();
        if (m.olay.seviye === "kritik" || m.olay.seviye === "uyari") bildir(m.olay.mesaj, 5000);
      } else if (m.tur === "tarama") {
        st.tarama = m.tarama; taramaGuncelle();
      }
    };
  }
  function rozet(bagli) {
    const r = $("#baglanti-rozeti");
    r.textContent = bagli ? "Sunucuya bağlı" : "Sunucu bağlantısı yok";
    r.className = "rozet " + (bagli ? "rozet-bagli" : "rozet-kopuk");
  }

  // ---------- liste / kartlar ----------
  function filtreli() {
    const q = $("#arama").value.trim().toLowerCase();
    const d = $("#filtre-durum").value, g = $("#filtre-grup").value;
    return Array.from(st.yazicilar.values()).filter(y => {
      const c = y.canli || {};
      if (d && c.durum !== d) return false;
      if (g && (y.grup || "") !== g) return false;
      if (q && !(`${y.ad} ${y.ip} ${y.hostname || ""} ${c.dosya || ""} ${y.grup || ""}`.toLowerCase().includes(q))) return false;
      return true;
    }).sort((a, b) => {
      const da = DURUM_SIRA.indexOf((a.canli || {}).durum), db = DURUM_SIRA.indexOf((b.canli || {}).durum);
      return da - db || a.ad.localeCompare(b.ad, "tr");
    });
  }
  function kartHtml(y) {
    const c = y.canli || {}, d = c.durum || "cevrimdisi";
    const ilerleme = c.ilerleme != null ? Math.round(c.ilerleme) : null;
    return `
      <div class="baslik"><span class="ad" title="${kacis(y.ad)}">${kacis(y.ad)}</span><span class="durum">${DURUM_AD[d] || d}</span></div>
      <div class="ip">${kacis(y.ip)}${y.grup ? " · " + kacis(y.grup) : ""}${c.model ? " · " + kacis(c.model) : ""}</div>
      <div class="dosya" title="${kacis(c.dosya)}">${c.dosya ? kacis(c.dosya) : (d === "cevrimdisi" ? kacis(c.son_hata || "bağlantı bekleniyor") : "")}</div>
      <progress max="100" value="${ilerleme == null ? 0 : ilerleme}"></progress>
      <div class="satir-bilgi"><span>${ilerleme == null ? "" : "%" + ilerleme}</span><span>${c.katman != null && c.toplam_katman ? `katman ${c.katman}/${c.toplam_katman}` : ""}</span><span>${c.kalan_sn != null && d === "basiyor" ? "kalan " + sure(c.kalan_sn) : ""}</span></div>
      <div class="sicaklik"><span>Nozul <b>${derece(c.nozul, c.nozul_hedef)}</b></span><span>Tabla <b>${derece(c.tabla, c.tabla_hedef)}</b></span><span>Kabin <b>${derece(c.kabin, c.kabin_hedef)}</b></span>${c.filament_yok ? '<span class="olay-kritik">Filament yok</span>' : ""}</div>`;
  }
  function cizKart(y) {
    const gorunur = filtreli().some(f => f.id === y.id);
    let k = $(`.kart[data-id="${y.id}"]`);
    if (!gorunur) { if (k) k.remove(); sonucSayisi(); bosMu(); return; }
    if (!k) { cizHepsi(); return; }
    const d = (y.canli || {}).durum || "cevrimdisi";
    k.className = "kart " + d; k.style.setProperty("--renk", `var(--d-${d})`);
    k.innerHTML = kartHtml(y);
  }
  function cizHepsi() {
    const kap = $("#kartlar");
    kap.innerHTML = filtreli().map(y => {
      const d = (y.canli || {}).durum || "cevrimdisi";
      return `<div class="kart ${d}" data-id="${y.id}" style="--renk: var(--d-${d})">${kartHtml(y)}</div>`;
    }).join("");
    cizSayaclar(); cizGruplar(); sonucSayisi(); bosMu();
  }
  function bosMu() { $("#bos").hidden = st.yazicilar.size > 0; }
  function sonucSayisi() { $("#sonuc-sayisi").textContent = `${filtreli().length} / ${st.yazicilar.size} yazıcı`; }
  function cizSayaclar() {
    const s = {}; DURUM_SIRA.forEach(d => s[d] = 0);
    st.yazicilar.forEach(y => { const d = (y.canli || {}).durum || "cevrimdisi"; s[d] = (s[d] || 0) + 1; });
    const aktif = $("#filtre-durum").value;
    $("#sayaclar").innerHTML = `<span class="sayac" data-d="">Toplam<b>${st.yazicilar.size}</b></span>` +
      DURUM_SIRA.map(d => `<span class="sayac${aktif === d ? " aktif" : ""}" data-d="${d}" style="--renk: var(--d-${d})">${DURUM_AD[d]}<b>${s[d]}</b></span>`).join("");
  }
  function cizGruplar() {
    const sel = $("#filtre-grup"), mevcut = sel.value;
    const gruplar = Array.from(new Set(Array.from(st.yazicilar.values()).map(y => y.grup).filter(Boolean))).sort();
    sel.innerHTML = '<option value="">Tüm gruplar</option>' + gruplar.map(g => `<option value="${kacis(g)}">${kacis(g)}</option>`).join("");
    sel.value = gruplar.includes(mevcut) ? mevcut : "";
  }
  function cizOlaylar() {
    $("#olay-listesi").innerHTML = st.olaylar.slice(0, 100).map(o =>
      `<li class="olay-${o.seviye}"><time>${saat(o.zaman)}</time>${kacis(o.mesaj)}</li>`).join("") || '<li class="ipucu">Henüz olay yok.</li>';
  }

  // ---------- ayrıntı ----------
  async function ayrintiAc(id) {
    st.acikYazici = id;
    const y = st.yazicilar.get(id); if (!y) return;
    ayrintiDoldur(y);
    ac("ortu-ayrinti");
    try {
      const v = await api(`/api/yazicilar/${id}`);
      $("#ay-ham").textContent = JSON.stringify(v.ham, null, 1);
      $("#ay-olaylar").innerHTML = v.olaylar.map(o => `<li class="olay-${o.seviye}"><time>${saat(o.zaman)}</time>${kacis(o.mesaj)}</li>`).join("") || "<li class='ipucu'>Olay yok.</li>";
    } catch (e) { bildir(e.message); }
  }
  function ayrintiDoldur(y) {
    const c = y.canli || {};
    $("#ay-baslik").textContent = `${y.ad} — ${y.ip}`;
    const alan = (k, v) => `<div><span>${k}</span>${v == null || v === "" ? "–" : kacis(v)}</div>`;
    $("#ay-alanlar").innerHTML = [
      alan("Durum", DURUM_AD[c.durum] || c.durum), alan("Bağlantı", c.baglanti),
      alan("Model", c.model || y.model), alan("Hostname", c.hostname || y.hostname),
      alan("Dosya", c.dosya), alan("İlerleme", c.ilerleme != null ? "%" + Math.round(c.ilerleme) : null),
      alan("Katman", c.katman != null ? `${c.katman} / ${c.toplam_katman || "?"}` : null), alan("Kalan süre", c.kalan_sn != null ? sure(c.kalan_sn) : null),
      alan("Geçen süre", c.gecen_sn != null ? sure(c.gecen_sn) : null), alan("Hız", c.hiz_yuzde != null ? "%" + c.hiz_yuzde : null),
      alan("Nozul", derece(c.nozul, c.nozul_hedef)), alan("Tabla", derece(c.tabla, c.tabla_hedef)),
      alan("Kabin", derece(c.kabin, c.kabin_hedef)), alan("Fan", c.fan != null ? "%" + c.fan : null),
      alan("Işık", c.isik == null ? null : (c.isik ? "Açık" : "Kapalı")), alan("CFS", c.cfs_bagli ? "Bağlı" : "Yok"),
      alan("Ham state", c.state_kodu), alan("Hata", c.hata_kodu ? `${c.hata_kodu} ${c.hata_anahtari || ""}` : "Yok"),
      alan("Son veri", c.son_veri ? saat(c.son_veri) : null), alan("Son hata", c.son_hata),
    ].join("");
    const f = $("#ay-form");
    if (!f.dataset.id || Number(f.dataset.id) !== y.id) {
      f.dataset.id = y.id; f.ad.value = y.ad; f.ip.value = y.ip; f.port.value = y.port;
      f.grup.value = y.grup || ""; f.notlar.value = y.notlar || ""; f.etkin.checked = !!y.etkin;
    }
  }
  $("#ay-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target, id = Number(f.dataset.id);
    try {
      await put(`/api/yazicilar/${id}`, { ad: f.ad.value, ip: f.ip.value, port: Number(f.port.value) || 9999, grup: f.grup.value, notlar: f.notlar.value, etkin: f.etkin.checked });
      bildir("Kaydedildi");
    } catch (err) { bildir(err.message); }
  });
  $("#ay-sil").addEventListener("click", async () => {
    const id = Number($("#ay-form").dataset.id), y = st.yazicilar.get(id);
    if (!y || !confirm(`${y.ad} (${y.ip}) silinsin mi?`)) return;
    try { await del(`/api/yazicilar/${id}`); kapat("ortu-ayrinti"); } catch (err) { bildir(err.message); }
  });
  $$("#ortu-ayrinti [data-komut]").forEach(b => b.addEventListener("click", async () => {
    const id = st.acikYazici, komut = b.dataset.komut;
    if (komut === "durdur" && !confirm("Baskı durdurulsun mu? Bu işlem geri alınamaz.")) return;
    try {
      const v = await post(`/api/yazicilar/${id}/komut`, { komut, deger: b.dataset.deger != null ? Number(b.dataset.deger) : null });
      bildir(v.gonderildi ? "Komut gönderildi" : "Gönderilemedi: yazıcı bağlı değil");
    } catch (err) { bildir(err.message); }
  }));

  // ---------- sihirbaz ----------
  function adim(n) {
    $$("#ortu-sihirbaz .adim").forEach(s => s.hidden = Number(s.dataset.adim) !== n);
    $$("#ortu-sihirbaz .adimlar li").forEach(l => l.classList.toggle("aktif", Number(l.dataset.adim) === n));
  }
  async function sihirbazAc() {
    ac("ortu-sihirbaz");
    if (st.tarama && ["hazir", "port", "kimlik"].includes(st.tarama.asama)) { adim(2); taramaGuncelle(); return; }
    adim(1);
    try {
      const v = await api("/api/aglar");
      $("#ag-listesi").innerHTML = v.aglar.map((a, i) =>
        `<label><input type="radio" name="ag" value="${kacis(a.cidr)}" ${i === 0 ? "checked" : ""}> ${kacis(a.cidr)} <small>${kacis(a.arayuz || "")} · bu makine ${kacis(a.ip)} · ${a.host_sayisi} adres</small></label>`).join("") ||
        '<p class="ipucu">Arayüz bulunamadı; CIDR girin.</p>';
      if (v.aglar[0] && !$("#cidr").value) $("#cidr").value = v.aglar[0].cidr;
      $$("input[name=ag]").forEach(r => r.addEventListener("change", () => { $("#cidr").value = r.value; }));
    } catch (e) { bildir(e.message); }
  }
  $("#btn-tara").addEventListener("click", async () => {
    const cidr = $("#cidr").value.trim(), port = Number($("#tarama-port").value) || 9999;
    if (!cidr) { bildir("CIDR girin"); return; }
    try { await post("/api/tarama", { cidr, port }); adim(2); $("#btn-tarama-ileri").disabled = true; }
    catch (e) { bildir(e.message); }
  });
  $("#btn-tarama-iptal").addEventListener("click", () => post("/api/tarama/iptal").catch(() => {}));
  $("#btn-tarama-ileri").addEventListener("click", () => { adim(3); sonucCiz(); });
  $("#btn-yeniden-tara").addEventListener("click", () => adim(1));
  $("#btn-elle-ekle").addEventListener("click", async () => {
    const ip = $("#elle-ip").value.trim(), ad = $("#elle-ad").value.trim();
    if (!ip) { bildir("IP girin"); return; }
    try { await post("/api/yazicilar", { ip, ad, port: Number($("#tarama-port").value) || 9999 }); bildir("Eklendi"); $("#elle-ip").value = ""; $("#elle-ad").value = ""; }
    catch (e) { bildir(e.message); }
  });
  function taramaGuncelle() {
    const t = st.tarama; if (!t) return;
    const yuzde = t.toplam ? Math.round(100 * t.taranan / t.toplam) : 0;
    $("#tarama-cubuk").value = t.asama === "port" ? yuzde : (t.asama === "hazir" ? 0 : 100);
    const metin = {
      hazir: "Hazırlanıyor…", port: `${t.cidr} taranıyor: ${t.taranan} / ${t.toplam} adres, ${t.bulunan.length} açık port`,
      kimlik: "Yanıt veren cihazlara kimlik soruluyor…", bitti: `Tarama bitti: ${t.bulunan.length} yazıcı bulundu`,
      iptal: "Tarama iptal edildi", hata: "Hata: " + t.hata,
    }[t.asama] || t.asama;
    $("#tarama-metin").textContent = metin;
    $("#tarama-ipucu").textContent = t.asama === "port" ? "Tipik bir /24 ağ 5–10 saniyede taranır." : "";
    const bitti = ["bitti", "iptal", "hata"].includes(t.asama);
    $("#btn-tarama-ileri").disabled = !bitti;
    $("#btn-tarama-iptal").disabled = bitti;
    if (bitti && !$("#ortu-sihirbaz").hidden && !$('#ortu-sihirbaz .adim[data-adim="2"]').hidden && t.asama === "bitti") { adim(3); sonucCiz(); }
  }
  function sonucCiz() {
    const t = st.tarama, tb = $("#sonuc-tablo tbody");
    if (!t) return;
    $("#sonuc-metin").textContent = t.bulunan.length ? `${t.cidr} içinde ${t.bulunan.length} yazıcı bulundu. Eklemek istediklerinizi seçin, ad verin.` : "Bu ağda yanıt veren yazıcı bulunamadı. Yazıcıların açık ve aynı ağda olduğundan emin olun.";
    tb.innerHTML = t.bulunan.map(b => `
      <tr class="${b.kayitli ? "kayitli" : ""}" data-ip="${kacis(b.ip)}">
        <td><input type="checkbox" class="sec" ${b.kayitli ? "disabled" : "checked"}></td>
        <td>${kacis(b.ip)}</td><td>${kacis(b.hostname || "–")}</td><td>${kacis(b.model || "–")}</td>
        <td><input type="text" class="ad" value="${kacis(b.hostname || b.ip)}" ${b.kayitli ? "disabled" : ""}></td>
        <td><input type="text" class="grup" placeholder="isteğe bağlı" ${b.kayitli ? "disabled" : ""}></td>
        <td>${b.kayitli ? "Zaten kayıtlı" : (b.hata ? "Kimlik alınamadı" : "Yeni")}</td>
      </tr>`).join("");
  }
  $("#tumu-sec").addEventListener("change", (e) => $$("#sonuc-tablo .sec:not(:disabled)").forEach(c => c.checked = e.target.checked));
  $("#btn-ekle").addEventListener("click", async () => {
    const secilen = $$("#sonuc-tablo tbody tr").filter(tr => $(".sec", tr).checked && !$(".sec", tr).disabled).map(tr => {
      const b = st.tarama.bulunan.find(x => x.ip === tr.dataset.ip) || {};
      return { ip: tr.dataset.ip, ad: $(".ad", tr).value, grup: $(".grup", tr).value, port: b.port, model: b.model, hostname: b.hostname };
    });
    if (!secilen.length) { bildir("Seçim yapın"); return; }
    try {
      const v = await post("/api/yazicilar/toplu", { yazicilar: secilen });
      bildir(`${v.eklenen.length} yazıcı eklendi${v.atlanan.length ? ", " + v.atlanan.length + " atlandı" : ""}`);
      kapat("ortu-sihirbaz");
    } catch (e) { bildir(e.message); }
  });

  // ---------- genel ----------
  function ac(id) { $("#" + id).hidden = false; }
  function kapat(id) { $("#" + id).hidden = true; if (id === "ortu-ayrinti") { st.acikYazici = null; $("#ay-form").dataset.id = ""; } }
  $$("[data-kapat]").forEach(b => b.addEventListener("click", () => kapat(b.dataset.kapat)));
  $$(".ortu").forEach(o => o.addEventListener("click", (e) => { if (e.target === o) kapat(o.id); }));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") $$(".ortu").forEach(o => { if (!o.hidden) kapat(o.id); }); });
  $("#kartlar").addEventListener("click", (e) => { const k = e.target.closest(".kart"); if (k) ayrintiAc(Number(k.dataset.id)); });
  $("#sayaclar").addEventListener("click", (e) => { const s = e.target.closest(".sayac"); if (!s) return; $("#filtre-durum").value = s.dataset.d || ""; cizHepsi(); });
  ["#arama", "#filtre-durum", "#filtre-grup"].forEach(s => $(s).addEventListener("input", cizHepsi));
  $("#btn-sihirbaz").addEventListener("click", sihirbazAc);
  $("#btn-sihirbaz-2").addEventListener("click", sihirbazAc);

  api("/api/surum").then(v => { $("#surum").textContent = `${v.urun} ${v.surum}`; }).catch(() => {});
  wsBaglan();
})();
