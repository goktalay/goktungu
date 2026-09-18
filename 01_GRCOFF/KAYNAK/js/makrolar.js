// js/makrolar.js — v2.4.243 PYTHON MAKROLARI (Rotalar > Makrolar, IS137)
//
// Kullanici istegi: "dronlar icin python makrolari ... Rotalar menusu altinda
// Makrolar menusu, standart kayit paneli, yeni makro -> isim sor, kaydet ->
// listeye gelsin, satirda script ikonu -> python duzenleme paneli; altta
// kullanilabilecek degiskenleri listele; mavutil'e erisim."
//
// WS: makro_liste/makro_kaydet/makro_sil -> {tip:"makrolar", liste, durumlar}
//     makro_kod_oku -> {tip:"makro_kod", makro_id, kod, durum, cikti}
//     makro_kod_yaz -> {tip:"makro_kod_yazildi"}
//     makro_calistir/makro_durdur -> {tip:"makro_durum"}; cikti akisi {tip:"makro_cikti"}
(function () {
  const T = () => (typeof D === "function") ? (D() || {}) : {};
  let liste = [], durumlar = {}, seciliId = 0, kodDegisti = false, duzenlenenId = 0;
  const EN_FAZLA_KONSOL = 600;

  const el = (id) => document.getElementById(id);
  const panelGorunur = (id) => { const p = el(id); return !!(p && !p.classList.contains("yuzen-gizli")); };
  const ac = (id) => { if (typeof window.yuzenPanelAc === "function") window.yuzenPanelAc(id); else { const p = el(id); if (p) p.classList.remove("yuzen-gizli"); } };
  const kapat = (id) => { const p = el(id); if (p) p.classList.add("yuzen-gizli"); };

  function gonder(paket) {
    if (typeof ws === "undefined" || !ws || ws.readyState !== 1) return false;
    try { ws.send(JSON.stringify(paket)); return true; } catch (e) { return false; }
  }
  function iste() { gonder({ tip: "makro_liste" }); }

  function toast(mesaj, seviye, baslik) {
    if (typeof window.uyariToastGoster === "function")
      window.uyariToastGoster({ baslik: baslik || "MAKRO", mesaj: mesaj, seviye: seviye || "bilgi", sure: 5000, kategori: "makro" });
  }

  // -----------------------------------------------------------------
  // Kullanilabilir degiskenler (panelin altinda; tiklaninca koda eklenir)
  // -----------------------------------------------------------------
  const DEGISKENLER = [
    { ad: "mav", ek: "mav", tr: "Seçili dronun pymavlink bağlantısı (mavutil.mavlink_connection). Örn: mav.mav.command_long_send(...), mav.recv_match(type='HEARTBEAT', blocking=True)", en: "pymavlink connection of the selected drone (mavutil.mavlink_connection)." },
    { ad: "mavutil", ek: "mavutil", tr: "pymavlink.mavutil modülü (mavutil.mavlink_connection, mavutil.mavlink.MAV_CMD_*)", en: "pymavlink.mavutil module." },
    { ad: "mavlink", ek: "mavlink", tr: "MAVLink lehçesi (ardupilotmega): MAV_CMD_NAV_TAKEOFF, MAV_FRAME_* sabitleri", en: "MAVLink dialect (ardupilotmega) constants." },
    { ad: "dron", ek: "dron", tr: "Seçili dronun kolay arayüzü. Alanlar: lat, lon, konum, irtifa, irtifa_msl, hiz, yon, batarya, batarya_v, mod, armed, ucusta, bagli, gps_fix, uydu, roll, pitch, sysid, mav", en: "Easy facade of the selected drone (lat, lon, konum, irtifa, hiz, yon, batarya, mod, armed, ucusta, bagli...)." },
    { ad: "dron.arm()", ek: "dron.arm()", tr: "Arm eder; arm(zorla=True) zorlar. Başarı için True döner", en: "Arms the vehicle; arm(zorla=True) forces." },
    { ad: "dron.disarm()", ek: "dron.disarm()", tr: "Disarm eder", en: "Disarms." },
    { ad: "dron.mod_ayarla('GUIDED')", ek: "dron.mod_ayarla('GUIDED')", tr: "Uçuş modunu değiştirir (GUIDED, AUTO, LOITER, RTL, LAND ...)", en: "Sets the flight mode." },
    { ad: "dron.kalk(irtifa)", ek: "dron.kalk(20)", tr: "GUIDED + arm + kalkış; verilen göreli irtifaya ulaşınca döner", en: "GUIDED + arm + takeoff to the given relative altitude." },
    { ad: "dron.git(lat, lon, irtifa)", ek: "dron.git(39.9, 32.8, 30, bekle=True)", tr: "GUIDED hedefe uçar (göreli irtifa); bekle=True ile varışı bekler", en: "Flies to a GUIDED target; bekle=True waits for arrival." },
    { ad: "dron.eve_don()", ek: "dron.eve_don()", tr: "RTL modu", en: "RTL mode." },
    { ad: "dron.inis()", ek: "dron.inis()", tr: "LAND modu", en: "LAND mode." },
    { ad: "dron.hiz_ayarla(m_s)", ek: "dron.hiz_ayarla(5)", tr: "Yer hızı hedefi (m/s)", en: "Ground speed target (m/s)." },
    { ad: "dron.mesafe(lat, lon)", ek: "dron.mesafe(39.9, 32.8)", tr: "Drondan noktaya uzaklık (m)", en: "Distance from drone to a point (m)." },
    { ad: "dron.bekle_varis(lat, lon, tol_m)", ek: "dron.bekle_varis(39.9, 32.8, 3)", tr: "Noktaya varana kadar bekler", en: "Waits until the drone reaches the point." },
    { ad: "dron.bekle_irtifa(irtifa)", ek: "dron.bekle_irtifa(20)", tr: "İrtifaya ulaşana kadar bekler", en: "Waits until the altitude is reached." },
    { ad: "dron.komut(cmd, p1..p7)", ek: "dron.komut(mavlink.MAV_CMD_DO_SET_SERVO, 9, 1500)", tr: "Ham COMMAND_LONG gönderir, ACK sonucunu döner", en: "Sends raw COMMAND_LONG, returns ACK result." },
    { ad: "dron.durum()", ek: "dron.durum()", tr: "Tüm telemetri alanları sözlük olarak", en: "All telemetry fields as a dict." },
    { ad: "dronlar", ek: "dronlar", tr: "Bağlı tüm dronlar: dronlar[sysid] (tembel açılır), dronlar.sysidler()", en: "All connected drones: dronlar[sysid], dronlar.sysidler()." },
    { ad: "dron_bul(sysid)", ek: "dron_bul(2)", tr: "sysid ile dron arayüzü", en: "Drone facade by sysid." },
    { ad: "sysid", ek: "sysid", tr: "Seçili dronun sysid'i", en: "Selected drone's sysid." },
    { ad: "bekle(sn)", ek: "bekle(1)", tr: "Saniye bekler (time.sleep)", en: "Sleeps for seconds." },
    { ad: "yaz(...)", ek: "yaz('merhaba', dron.irtifa)", tr: "Çıktı penceresine yazar (print de aynı)", en: "Writes to the output console (print works too)." },
    { ad: "bildir(metin)", ek: "bildir('Görev tamam')", tr: "Arayüzde uyarı balonu gösterir", en: "Shows a toast notification in the UI." },
    { ad: "durdur()", ek: "durdur()", tr: "Makroyu bitirir", en: "Ends the macro." },
    { ad: "time, math, json", ek: "time.time()", tr: "Standart modüller hazır", en: "Standard modules available." },
  ];

  const ORNEK_KOD = [
    "# Örnek: 20 m'ye kalk, 30 m kuzeye git, geri dön",
    "yaz('Dron:', dron.sysid, 'mod:', dron.mod, 'batarya:', dron.batarya)",
    "if not dron.bagli:",
    "    yaz('Dron bağlı değil'); durdur()",
    "dron.kalk(20)",
    "lat, lon = dron.konum",
    "dron.git(lat + 30 / 111320.0, lon, 20, bekle=True)",
    "bildir('Hedefe varıldı')",
    "dron.eve_don()",
    "",
  ].join("\n");

  // -----------------------------------------------------------------
  // LISTE PANELI
  // -----------------------------------------------------------------
  function listeCiz() {
    const kok = el("makrolarListe");
    if (!kok) return;
    const t = T();
    kok.innerHTML = "";
    if (!liste.length) {
      if (typeof bosPanelYap === "function") kok.appendChild(bosPanelYap(t.bosMakro || "KAYITLI MAKRO YOK", "fa-solid fa-code"));
      return;
    }
    for (const r of liste) {
      const d = (durumlar[String(r.id)] || {}).durum || "hazir";
      const sat = document.createElement("div");
      sat.className = "cl-satir" + (Number(r.id) === seciliId ? " secili" : "");
      sat.innerHTML =
        "<span class='ra-nokta mk-d-" + d + "'></span>" +
        "<div class='cl-govde'><div class='cl-ad'></div><div class='cl-alt'></div></div>" +
        "<div class='cl-dgm'>" +
          "<button type='button' class='kucuk ikincil mk-kod-btn' title='" + (t.mkKodIpucu || "Python kodunu düzenle / çalıştır") + "'><i class='fa-solid fa-file-code'></i></button>" +
          "<button type='button' class='kucuk ikincil cl-duzenle' title='" + (t.btnDuzenle || "Düzenle") + "'><i class='fa-solid fa-pen'></i></button>" +
          "<button type='button' class='kucuk tehlike ikincil cl-sil' title='" + (t.btnSil || "Sil") + "'><i class='fa-solid fa-trash'></i></button>" +
        "</div>";
      sat.querySelector(".cl-ad").textContent = r.ad || ("Makro " + r.id);
      sat.querySelector(".cl-alt").textContent = (r.aciklama ? r.aciklama + "  ·  " : "") + (t["mkDurum_" + d] || d);
      sat.title = t.mkSatirIpucu || "Python düzenleme panelini aç";
      sat.addEventListener("click", () => editorAc(r.id));
      sat.querySelector(".mk-kod-btn").addEventListener("click", (ev) => { ev.stopPropagation(); editorAc(r.id); });
      sat.querySelector(".cl-duzenle").addEventListener("click", (ev) => { ev.stopPropagation(); formAc(r); });
      sat.querySelector(".cl-sil").addEventListener("click", (ev) => {
        ev.stopPropagation();
        const metin = (t.onayMakroSil || "{ad} makrosu silinsin mi?").replace("{ad}", r.ad || ("Makro " + r.id));
        const sil = () => gonder({ tip: "makro_sil", makro_id: Number(r.id) });
        if (typeof onayIste === "function") onayIste(metin, sil); else if (confirm(metin)) sil();
      });
      kok.appendChild(sat);
    }
  }

  // -----------------------------------------------------------------
  // FORM (ad / aciklama / sure)
  // -----------------------------------------------------------------
  function formAc(r) {
    const t = T();
    duzenlenenId = r ? Number(r.id) : 0;
    const ad = el("mfAd"), ac_ = el("mfAciklama"), sure = el("mfSure"), baslik = el("makroFormBaslik");
    if (!ad) return;
    ad.value = r ? (r.ad || "") : ((t.mkYeniAd || "Makro") + " " + (liste.length + 1));
    if (ac_) ac_.value = r ? (r.aciklama || "") : "";
    if (sure) sure.value = r ? String(r.sure_sn == null ? 3600 : r.sure_sn) : "3600";
    if (baslik) baslik.textContent = r ? (t.panelMakroFormDuzenle || "MAKROYU DÜZENLE") : (t.panelMakroFormYeni || "YENİ MAKRO");
    ac("yzMakroForm");
    setTimeout(() => { ad.focus(); ad.select(); }, 50);
  }
  function formKaydet() {
    const ad = (el("mfAd") || {}).value || "";
    if (!ad.trim()) { if (el("mfAd")) el("mfAd").focus(); return; }
    const paket = { tip: "makro_kaydet", makro_id: duzenlenenId || 0, ad: ad.trim(),
                    aciklama: ((el("mfAciklama") || {}).value || "").trim(),
                    sure_sn: parseInt((el("mfSure") || {}).value || "3600", 10) };
    if (isNaN(paket.sure_sn) || paket.sure_sn < 0) paket.sure_sn = 3600;
    if (gonder(paket)) kapat("yzMakroForm");
  }

  // -----------------------------------------------------------------
  // EDITOR PANELI
  // -----------------------------------------------------------------
  function sysidSeciciDoldur() {
    const s = el("mkSysid");
    if (!s) return;
    const t = T();
    const onceki = s.value;
    s.innerHTML = "";
    const dronlar = Array.isArray(window.dronlarSon) ? window.dronlarSon : [];
    if (!dronlar.length) {
      const o = document.createElement("option"); o.value = ""; o.textContent = t.mkDronYok || "Bağlı dron yok"; s.appendChild(o);
      return;
    }
    for (const d of dronlar) {
      const o = document.createElement("option");
      o.value = String(d.sysid);
      o.textContent = (d.isim || d.kullanici_isim || ("Dron " + d.sysid)) + " (sysid " + d.sysid + ")";
      s.appendChild(o);
    }
    if (onceki && [...s.options].some((o) => o.value === onceki)) s.value = onceki;
  }

  function durumYaz(durum) {
    const t = T();
    const d = (durum && durum.durum) || "hazir";
    const e = el("mkDurum");
    if (!e) return;
    let metin = t["mkDurum_" + d] || d;
    if (durum && durum.gecen_sn != null && d !== "hazir") metin += " · " + durum.gecen_sn + " sn";
    if (durum && durum.son_hata) metin += " · " + durum.son_hata;
    e.textContent = metin;
    e.className = "mk-durum mk-d-" + d;
    const cal = d === "calisiyor";
    if (el("btnMkCalistir")) el("btnMkCalistir").disabled = cal;
    if (el("btnMkDurdur")) el("btnMkDurdur").disabled = !cal;
  }

  function konsolTemizle() { const k = el("mkKonsol"); if (k) k.innerHTML = ""; }
  function konsolEkle(satirlar) {
    const k = el("mkKonsol");
    if (!k || !satirlar || !satirlar.length) return;
    for (const s of satirlar) {
      const sat = document.createElement("div");
      const sev = s.sev === "bildir" ? "basari" : (s.sev || "bilgi");
      sat.className = "dk-kons-satir dk-kons-" + sev;
      const ts = document.createElement("span"); ts.className = "dk-kons-ts";
      const dt = new Date((s.ts || Date.now() / 1000) * 1000);
      ts.textContent = dt.toTimeString().slice(0, 8);
      const m = document.createElement("span"); m.className = "dk-kons-metin"; m.textContent = s.metin || "";
      sat.appendChild(ts); sat.appendChild(m); k.appendChild(sat);
    }
    while (k.childNodes.length > EN_FAZLA_KONSOL) k.removeChild(k.firstChild);
    k.scrollTop = k.scrollHeight;
  }

  function degiskenleriCiz() {
    const kok = el("mkDegiskenler");
    if (!kok || kok.dataset.hazir) return;
    kok.dataset.hazir = "1";
    const dil = (localStorage.getItem("gcs_dil") || "TR").toUpperCase();
    for (const v of DEGISKENLER) {
      const sat = document.createElement("div");
      sat.className = "mk-degisken";
      const ad = document.createElement("code"); ad.textContent = v.ad;
      const ac_ = document.createElement("span"); ac_.textContent = dil === "EN" ? v.en : v.tr;
      sat.appendChild(ad); sat.appendChild(ac_);
      sat.title = T().mkDegiskenIpucu || "Tıklayınca koda eklenir";
      sat.addEventListener("click", () => kodaEkle(v.ek));
      kok.appendChild(sat);
    }
  }

  function kodaEkle(metin) {
    const ta = el("mkKod");
    if (!ta) return;
    const bas = ta.selectionStart || 0, son = ta.selectionEnd || 0;
    ta.value = ta.value.slice(0, bas) + metin + ta.value.slice(son);
    ta.selectionStart = ta.selectionEnd = bas + metin.length;
    ta.focus();
    kodDegisti = true; kaydetDurumu();
  }

  function kaydetDurumu() {
    const b = el("btnMkKaydet");
    if (b) b.classList.toggle("mk-kirli", !!kodDegisti);
    const n = el("mkKaydetNot");
    if (n) n.textContent = kodDegisti ? (T().mkDegismis || "Kaydedilmemiş değişiklik") : "";
  }

  function editorAc(id) {
    seciliId = Number(id) || 0;
    kodDegisti = false;
    kaydetDurumu();
    konsolTemizle();
    degiskenleriCiz();
    sysidSeciciDoldur();
    const r = liste.find((x) => Number(x.id) === seciliId);
    if (el("mkEditorBaslik")) el("mkEditorBaslik").textContent = ((r && r.ad) || ("Makro " + seciliId)).toUpperCase();
    if (el("mkKod")) el("mkKod").value = "";
    durumYaz(durumlar[String(seciliId)] || { durum: "hazir" });
    ac("yzMakroEditor");
    gonder({ tip: "makro_kod_oku", makro_id: seciliId });
    listeCiz();
  }

  function kodKaydet(sonra) {
    if (!seciliId) return;
    const kod = (el("mkKod") || {}).value || "";
    if (gonder({ tip: "makro_kod_yaz", makro_id: seciliId, kod: kod })) {
      kodDegisti = false; kaydetDurumu();
      if (typeof sonra === "function") sonra();
    }
  }
  function calistir() {
    if (!seciliId) return;
    const s = el("mkSysid");
    const sysid = s && s.value ? parseInt(s.value, 10) : 0;
    const t = T();
    if (!sysid) { toast(t.mkDronSec || "Önce çalıştırılacak dronu seçin.", "uyari"); return; }
    const kod = (el("mkKod") || {}).value || "";
    if (!kod.trim()) { toast(t.mkKodBos || "Makro kodu boş.", "uyari"); return; }
    const basla = () => { konsolTemizle(); gonder({ tip: "makro_calistir", makro_id: seciliId, sysid: sysid }); };
    if (kodDegisti) kodKaydet(basla); else basla();
  }

  // -----------------------------------------------------------------
  // WS isleyiciler
  // -----------------------------------------------------------------
  window.makroListesiIsle = function (m) {
    if (!m) return;
    liste = Array.isArray(m.liste) ? m.liste : [];
    durumlar = m.durumlar || {};
    listeCiz();
    if (m.komut === "kaydet" && m.yeni_id && !duzenlenenId) editorAc(m.yeni_id);
    if (seciliId && !liste.some((x) => Number(x.id) === seciliId)) { seciliId = 0; kapat("yzMakroEditor"); }
  };
  window.makroKodIsle = function (m) {
    if (!m || Number(m.makro_id) !== seciliId) return;
    const ta = el("mkKod");
    if (ta && !kodDegisti) ta.value = (m.kod && m.kod.length) ? m.kod : ORNEK_KOD;
    if (ta && !(m.kod && m.kod.length)) { kodDegisti = true; kaydetDurumu(); }
    if (el("mkEditorBaslik") && m.ad) el("mkEditorBaslik").textContent = String(m.ad).toUpperCase();
    durumYaz(m.durum || {});
    konsolTemizle(); konsolEkle(m.cikti || []);
  };
  window.makroKodYazildiIsle = function (m) {
    if (!m || Number(m.makro_id) !== seciliId) return;
    const n = el("mkKaydetNot");
    if (n) { n.textContent = T().mkKaydedildi || "Kaydedildi"; setTimeout(() => { if (!kodDegisti) n.textContent = ""; }, 2500); }
  };
  window.makroCiktiIsle = function (m) {
    if (!m) return;
    if (m.durum) durumlar[String(m.makro_id)] = m.durum;
    if (Number(m.makro_id) === seciliId) {
      if (m.temizle) konsolTemizle();
      konsolEkle(m.satirlar || []);
      if (m.durum) durumYaz(m.durum);
    }
    if (m.durum && m.durum.durum !== "calisiyor") listeCiz();
  };
  window.makroDurumIsle = function (m) {
    if (!m) return;
    if (m.durum) durumlar[String(m.makro_id)] = m.durum;
    if (Number(m.makro_id) === seciliId && m.durum) durumYaz(m.durum);
    listeCiz();
  };

  // -----------------------------------------------------------------
  function bagla() {
    const yeni = el("btnMakroYeni"); if (yeni) yeni.addEventListener("click", () => formAc(null));
    const kaydet = el("btnMakroFormKaydet"); if (kaydet) kaydet.addEventListener("click", formKaydet);
    const iptal = el("btnMakroFormIptal"); if (iptal) iptal.addEventListener("click", () => kapat("yzMakroForm"));
    const ad = el("mfAd"); if (ad) ad.addEventListener("keydown", (e) => { if (e.key === "Enter") formKaydet(); });
    const ta = el("mkKod");
    if (ta) {
      ta.addEventListener("input", () => { kodDegisti = true; kaydetDurumu(); });
      ta.addEventListener("keydown", (e) => {
        if (e.key === "Tab") {
          e.preventDefault();
          const b = ta.selectionStart, s = ta.selectionEnd;
          ta.value = ta.value.slice(0, b) + "    " + ta.value.slice(s);
          ta.selectionStart = ta.selectionEnd = b + 4;
          kodDegisti = true; kaydetDurumu();
        } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
          e.preventDefault(); kodKaydet();
        }
      });
    }
    const k = el("btnMkKaydet"); if (k) k.addEventListener("click", () => kodKaydet());
    const c = el("btnMkCalistir"); if (c) c.addEventListener("click", calistir);
    const d = el("btnMkDurdur"); if (d) d.addEventListener("click", () => { if (seciliId) gonder({ tip: "makro_durdur", makro_id: seciliId }); });
    const tz = el("btnMkTemizle"); if (tz) tz.addEventListener("click", () => { if (seciliId) gonder({ tip: "makro_cikti_temizle", makro_id: seciliId }); konsolTemizle(); });
    const sy = el("mkSysidYenile"); if (sy) sy.addEventListener("click", sysidSeciciDoldur);
    // Panel gorunur olunca liste istenir (kopruler_panel ile ayni kural).
    const p = el("yzMakrolar");
    if (p && typeof MutationObserver === "function") {
      let onceki = panelGorunur("yzMakrolar");
      new MutationObserver(() => { const g = panelGorunur("yzMakrolar"); if (g && !onceki) iste(); onceki = g; }).observe(p, { attributes: true, attributeFilter: ["class"] });
      if (onceki) iste();
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bagla); else bagla();
  window.makroPanelBagla = bagla;
  window.makroEditorAc = editorAc;
  window.makroListesiIste = iste;
})();
