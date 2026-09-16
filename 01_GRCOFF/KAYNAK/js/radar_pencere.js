// =================================================================
// GOKTUNGU - RADAR YÖNETİM PENCERESİ (v2.4.227)
// Kullanıcı isteği: "Radara tıkladığımızda açılan ekran yerine SDK
// dokümanında yapılabilecek tüm işlemleri yapabildiğimiz bir panel
// açılsın; çoklu panel olmasın; listedeki radara tıklayınca o radara
// özel panel açılsın; M50 yönetim paneli gibi açılır kapanır
// bölümlerle yönetilsin; IP/port düzenle ekranında kalsın."
//
// T serisi tarama radarı protokolü (v3.0.0) yüzeyi:
//   LOGIN / HEARTBEAT ............ Bağlantı bölümü (Bağlan / Kes, sağlık)
//   SETREG WORKING_MODE .......... Çalışma bölümü (Başlat / Durdur, tarama hızı)
//   SETREG/GETREG USER_CFG0 ...... Tespit ayarları (frekans, hız, tespit, RCS)
//   REQUEST_RTK / UPLOAD_RTK ..... Konum & yön (RTK'dan konum, merkez yönü)
//   SETSELECT / GETSELECT ........ Seçili iz (radar yalnız seçili izi işaretler)
//   SETJSON / GETJSON ............ JSON yapılandırma (koordinat / sistem)
//   UPLOAD_TRACK_V3 / TARGET_V3 .. Hedefler bölümü (canlı iz listesi, nokta sayısı)
// Pencere yalnız SEÇİLİ radarı yönetir; her radar_id için ayrı pencere.
// Görsel iskelet m50_pencere.js ile aynı (.m50-pc sınıfları + .ra-pc).
// =================================================================
(function radarPencereModulu(){
  const pencereler = {};   // radar_id -> k
  const T = () => (typeof D === "function" ? D() : {}) || {};
  const yerel = {
    oku(a, v){ try { const s = localStorage.getItem(a); return s === null ? v : JSON.parse(s); } catch (e) { return v; } },
    yaz(a, v){ try { localStorage.setItem(a, JSON.stringify(v)); } catch (e) {} }
  };
  const KIMLIK_CARPANI = 1000000;
  const MODLAR = [["bekleme", "raModBekleme", "Bekleme"], ["tarama1", "raModTarama1", "Tarama 1 sn"],
                  ["tarama2", "raModTarama2", "Tarama 2 sn"], ["tarama4", "raModTarama4", "Tarama 4 sn"]];

  function raBul(rid){
    const l = (typeof radarListesi !== "undefined" && Array.isArray(radarListesi)) ? radarListesi : [];
    return l.find(r => Number(r.radar_id) === Number(rid)) || null;
  }
  function gonder(rid, paket){
    paket.radar_id = Number(rid);
    if (typeof radarGonder === "function") return radarGonder(paket);
    return false;
  }
  function radarIzleri(rid){
    const hepsi = (typeof sonRadarHedefler !== "undefined" && Array.isArray(sonRadarHedefler)) ? sonRadarHedefler : [];
    return hepsi.filter(h => {
      const id = Number(h.id);
      if (typeof h.radar_id === "number") return h.radar_id === Number(rid);
      if (id >= KIMLIK_CARPANI) return Math.floor(id / KIMLIK_CARPANI) === Number(rid);
      return true;   // ayrıştırılmamış eski kimlik: tek radar
    });
  }
  function radarIzKimligi(h){
    if (typeof h.radar_hedef_id === "number") return h.radar_hedef_id;
    const id = Number(h.id);
    return id >= KIMLIK_CARPANI ? id % KIMLIK_CARPANI : id;
  }
  function sure(sn){
    sn = Math.max(0, Math.floor(sn)); const s = sn % 60, d = Math.floor(sn / 60) % 60, h = Math.floor(sn / 3600);
    const pp = n => String(n).padStart(2, "0"); return (h > 0 ? h + ":" : "") + pp(d) + ":" + pp(s);
  }
  function sonucMetni(t, s){
    if (!s) return "";
    if (s === "gonderiliyor") return t.raSonucGonderiliyor || "Gönderiliyor…";
    if (s === "okunuyor") return t.rpOkunuyor || "Okunuyor…";
    if (s === "ok") return t.rpSonucOk || "Radar kabul etti.";
    if (s === "okundu") return t.rpOkundu || "Radardan okundu.";
    if (String(s).startsWith("hata")) return (t.rpSonucHata || "Radar reddetti: ") + String(s).slice(5).trim();
    return String(s);
  }

  // ---- pencere kurulumu ----
  function pencereKur(rid){
    const t = T();
    const k = { rid: Number(rid), taslak: null, rtkBekliyor: false };
    const p = document.createElement("div"); p.className = "m50-pc ra-pc"; p.dataset.radarId = String(rid);
    const baslik = document.createElement("div"); baslik.className = "m50-pc-baslik";
    const ikon = document.createElement("i"); ikon.className = "fa-solid fa-satellite-dish m50-pc-ikon";
    const ad = document.createElement("span"); ad.className = "m50-pc-ad";
    const rozetSurum = document.createElement("span"); rozetSurum.className = "m50-pc-rozet surum";
    rozetSurum.textContent = "v" + ((typeof GCS_SURUM === "string" && GCS_SURUM) || "?");
    const rozetMod = document.createElement("span"); rozetMod.className = "m50-pc-rozet";
    const rozetBag = document.createElement("span"); rozetBag.className = "m50-pc-rozet";
    const kapat = document.createElement("button"); kapat.type = "button"; kapat.className = "m50-pc-kapat";
    kapat.title = t.ipKapat || "Kapat"; kapat.innerHTML = "<i class='fa-solid fa-xmark'></i>";
    kapat.addEventListener("click", ev => { ev.stopPropagation(); window.radarPencereKapat(rid); });
    baslik.append(ikon, ad, rozetSurum, rozetMod, rozetBag, kapat);
    const govde = document.createElement("div"); govde.className = "m50-pc-govde";
    const sol = document.createElement("div"); sol.className = "m50-pc-sol";
    govde.appendChild(sol);

    const bolum = (metin, ik, acik) => {
      const d = document.createElement("details"); d.className = "m50-pc-bolum"; d.open = acik !== false;
      const sm = document.createElement("summary"); sm.innerHTML = "<i class='fa-solid " + ik + "'></i> " + metin; d.appendChild(sm);
      const ic = document.createElement("div"); ic.className = "m50-pc-bolum-ic"; d.appendChild(ic);
      const anahtar = "rabolum_" + rid + "_" + ik;
      try { const v = localStorage.getItem(anahtar); if (v !== null) d.open = v === "1"; } catch (e) {}
      d.addEventListener("toggle", () => { try { localStorage.setItem(anahtar, d.open ? "1" : "0"); } catch (e) {} });
      sol.appendChild(d); return ic;
    };
    const dugme = (sinif, ik, metin) => { const b = document.createElement("button"); b.type = "button"; b.className = "m50-pc-sb " + sinif;
      b.innerHTML = "<i class='fa-solid " + ik + "'></i><span>" + (metin || "") + "</span>"; return b; };
    const satir = (...el) => { const s = document.createElement("div"); s.className = "m50-pc-satir"; s.append(...el); return s; };
    const etiketli = (metin, el) => { const kap = document.createElement("div"); kap.className = "m50-pc-hassas m50-pc-satir";
      const e = document.createElement("span"); e.textContent = metin; kap.append(e, el); return kap; };
    const not = (sinif) => { const pnot = document.createElement("p"); pnot.className = "m50-pc-ayar-not " + (sinif || ""); return pnot; };
    const secim = (secenekler) => { const s = document.createElement("select"); s.className = "m50-pc-sb";
      for (const [v, m] of secenekler){ const o = document.createElement("option"); o.value = String(v); o.textContent = m; s.appendChild(o); } return s; };

    // 1) BAĞLANTI
    const bBag = bolum(t.rpBolumBaglanti || "Bağlantı", "fa-plug");
    const adres = document.createElement("div"); adres.className = "ra-pc-adres";
    const btnDuzenle = dugme("ra-pc-sb-duzenle", "fa-pen", t.btnDuzenle || "Düzenle");
    btnDuzenle.title = t.rpAdresIpucu || "IP ve port kayıt formunda düzenlenir";
    btnDuzenle.addEventListener("click", ev => { ev.stopPropagation(); const r = raBul(rid); if (r && typeof window.radarFormuAc === "function") window.radarFormuAc(r); });
    const btnBaglan = dugme("ra-pc-sb-baglan", "fa-plug", t.btnRadarBaglan || "RADARA BAĞLAN");
    btnBaglan.addEventListener("click", ev => {
      ev.stopPropagation();
      const r = raBul(rid); if (!r) return;
      if (r.durum === "bagli" || r.durum === "baglaniyor"){ gonder(rid, { tip: "radar_kes" }); return; }
      if (!r.kayit_ip){ k.durumNot.textContent = t.rpAdresYok || "Önce Düzenle ile radar IP adresini girin."; return; }
      gonder(rid, { tip: "radar_baglan", ip: r.kayit_ip, port: Number(r.kayit_port) || 5001 });
    });
    const durumSatir = document.createElement("div"); durumSatir.className = "ra-pc-durum";
    const durumNot = not("ra-pc-hata");
    bBag.append(satir(adres, btnDuzenle), satir(btnBaglan), durumSatir, durumNot);

    // 2) ÇALIŞMA (WORKING_MODE)
    const bCal = bolum(t.rpBolumCalisma || "Çalışma", "fa-play");
    const sbMod = secim(MODLAR.filter(m => m[0] !== "bekleme").map(m => [m[0], t[m[1]] || m[2]]));
    sbMod.value = yerel.oku("ramod_" + rid, "tarama2");
    sbMod.addEventListener("change", () => yerel.yaz("ramod_" + rid, sbMod.value));
    const btnBaslat = dugme("ra-pc-sb-baslat", "fa-play", t.rpBaslat || "BAŞLAT");
    btnBaslat.addEventListener("click", ev => { ev.stopPropagation(); gonder(rid, { tip: "radar_ayar_yaz", calisma_modu: sbMod.value }); k.calNot.textContent = t.raSonucGonderiliyor || "Gönderiliyor…"; });
    const btnDurdur = dugme("ra-pc-sb-durdur", "fa-stop", t.rpDurdur || "DURDUR");
    btnDurdur.addEventListener("click", ev => { ev.stopPropagation(); gonder(rid, { tip: "radar_ayar_yaz", calisma_modu: "bekleme" }); k.calNot.textContent = t.raSonucGonderiliyor || "Gönderiliyor…"; });
    const calDurum = document.createElement("div"); calDurum.className = "ra-pc-satir-bilgi";
    const calNot = not();
    bCal.append(etiketli(t.rpTaramaHizi || "Tarama hızı", sbMod), satir(btnBaslat, btnDurdur), calDurum, calNot);

    // 3) TESPİT AYARLARI (USER_CFG0)
    const bTes = bolum(t.rpBolumTespit || "Tespit ayarları", "fa-sliders");
    const sbFrekans = secim([0,1,2,3,4,5,6,7].map(i => [i, String(i)]));
    const sbTespit = secim([[0, t.raEsikDusuk || "Düşük"], [1, t.raEsikNormal || "Normal"], [2, t.raEsikYuksek || "Yüksek"]]);
    const sbHiz = secim([[0, "0.25 m/s"], [1, "0.5 m/s"], [2, "0.75 m/s"], [3, "1.0 m/s"]]);
    const sbRcs = secim([[0, t.raKapali || "KAPALI"], [1, "0.01 m²"], [2, "0.05 m²"]]);
    const tesTaslak = () => { k.tesTaslak = true; btnTesUygula.disabled = false; btnTesUygula.classList.add("kai-uygula-bekliyor"); };
    for (const s of [sbFrekans, sbTespit, sbHiz, sbRcs]) s.addEventListener("change", tesTaslak);
    const btnTesUygula = document.createElement("button"); btnTesUygula.type = "button"; btnTesUygula.className = "kai-uygula-dgm"; btnTesUygula.disabled = true;
    btnTesUygula.innerHTML = "<i class='fa-solid fa-check'></i><span>" + (t.kaiUygula || "Uygula") + "</span>";
    btnTesUygula.addEventListener("click", ev => {
      ev.stopPropagation();
      gonder(rid, { tip: "radar_ayar_yaz", frekans: parseInt(sbFrekans.value, 10), tespit_esigi: parseInt(sbTespit.value, 10),
                    hiz_esigi: parseInt(sbHiz.value, 10), rcs_esigi: parseInt(sbRcs.value, 10) });
      k.tesTaslak = false; btnTesUygula.disabled = true; btnTesUygula.classList.remove("kai-uygula-bekliyor");
      k.tesNot.textContent = t.raSonucGonderiliyor || "Gönderiliyor…";
    });
    const btnTesOku = dugme("ra-pc-sb-oku", "fa-rotate", t.rpRadardanOku || "Radardan oku");
    btnTesOku.addEventListener("click", ev => { ev.stopPropagation(); k.tesTaslak = false; btnTesUygula.disabled = true; btnTesUygula.classList.remove("kai-uygula-bekliyor"); gonder(rid, { tip: "radar_ayar_oku" }); });
    const tesNot = not();
    const tesUygulaSatir = document.createElement("div"); tesUygulaSatir.className = "m50-pc-satir m50-pc-uygula"; tesUygulaSatir.append(btnTesUygula, btnTesOku);
    bTes.append(etiketli(t.lblRaFrekans || "Frekans", sbFrekans), etiketli(t.lblRaTespit || "Tespit eşiği", sbTespit),
                etiketli(t.lblRaHiz || "Hız eşiği", sbHiz), etiketli(t.lblRaRcs || "RCS eşiği", sbRcs), tesUygulaSatir, tesNot);

    // 4) KONUM & YÖN (RTK + merkez yönü)
    const bKon = bolum(t.rpBolumKonum || "Konum ve yön", "fa-location-dot");
    const konumBilgi = document.createElement("div"); konumBilgi.className = "ra-pc-satir-bilgi";
    const btnRtk = dugme("ra-pc-sb-rtk", "fa-satellite", t.btnRtkKonum || "RTK'DAN KONUM AL");
    btnRtk.addEventListener("click", ev => {
      ev.stopPropagation();
      const r = raBul(rid);
      if (!r || r.durum !== "bagli"){ k.rtkNot.textContent = t.rtkHata || "RTK konumu alınamadı (radar bağlı değil)"; return; }
      k.rtkBekliyor = true; btnRtk.disabled = true; k.rtkKutu.style.display = ""; k.rtkBar.style.width = "0%";
      k.rtkNot.textContent = t.rtkAliniyor || "RTK verisi alınıyor…";
      gonder(rid, { tip: "rtk_konum_al" });
    });
    const rtkKutu = document.createElement("div"); rtkKutu.className = "ra-pc-ilerleme"; rtkKutu.style.display = "none";
    const rtkBar = document.createElement("div"); rtkKutu.appendChild(rtkBar);
    const rtkNot = not();
    const inYon = document.createElement("input"); inYon.type = "number"; inYon.min = "0"; inYon.max = "359.99"; inYon.step = "0.01"; inYon.className = "m50-pc-sb ra-pc-in";
    inYon.title = t.rpMerkezYonuIpucu || "Azimut ofseti: radarın sıfır yönü ile kuzey arasındaki fark";
    const btnYon = dugme("ra-pc-sb-yon", "fa-compass", t.kaiUygula || "Uygula");
    btnYon.addEventListener("click", ev => { ev.stopPropagation(); const my = parseFloat(inYon.value); if (isNaN(my)) return;
      gonder(rid, { tip: "radar_ayar_yaz", merkez_yonu: ((my % 360) + 360) % 360 }); k.rtkNot.textContent = t.rpYonKaydedildi || "Merkez yönü kaydedildi."; inYon.blur(); });
    bKon.append(konumBilgi, satir(btnRtk), rtkKutu, etiketli(t.lblRaMerkezYonu || "Merkez yönü (°)", inYon), satir(btnYon), rtkNot);

    // 5) SEÇİLİ İZ (SETSELECT / GETSELECT)
    const bSec = bolum(t.rpBolumSecim || "Seçili iz", "fa-crosshairs");
    const secBilgi = document.createElement("div"); secBilgi.className = "ra-pc-satir-bilgi";
    const secListe = document.createElement("div"); secListe.className = "ra-pc-sec-liste";
    const btnSecOku = dugme("ra-pc-sb-oku", "fa-rotate", t.rpRadardanOku || "Radardan oku");
    btnSecOku.addEventListener("click", ev => { ev.stopPropagation(); gonder(rid, { tip: "radar_secim_oku" }); });
    const btnSecTemizle = dugme("ra-pc-sb-temizle", "fa-eraser", t.rpSecimTemizle || "Seçimi temizle");
    btnSecTemizle.addEventListener("click", ev => { ev.stopPropagation(); gonder(rid, { tip: "radar_secim_yaz", izler: [] }); k.secNot.textContent = t.raSonucGonderiliyor || "Gönderiliyor…"; });
    const secNot = not();
    const secAciklama = not(); secAciklama.textContent = t.rpSecimAciklama || "Seçilen iz radarda 'seçili' işaretlenir; hedef listesindeki Seç düğmesiyle atanır (tek iz).";
    bSec.append(secBilgi, secListe, satir(btnSecOku, btnSecTemizle), secNot, secAciklama);

    // 6) JSON YAPILANDIRMA (SETJSON / GETJSON)
    const bJson = bolum(t.rpBolumJson || "JSON yapılandırma", "fa-code", false);
    const sbJsonTip = secim([[0, t.rpJsonKoordinat || "Koordinat yapılandırması (0)"], [1, t.rpJsonSistem || "Sistem yapılandırması (1)"]]);
    const btnJsonOku = dugme("ra-pc-sb-oku", "fa-download", t.rpOku || "Oku");
    btnJsonOku.addEventListener("click", ev => { ev.stopPropagation(); k.jsonBekleyenTip = Number(sbJsonTip.value); gonder(rid, { tip: "radar_json_oku", json_tip: Number(sbJsonTip.value) }); k.jsonNot.textContent = t.rpOkunuyor || "Okunuyor…"; });
    const taJson = document.createElement("textarea"); taJson.className = "ra-pc-json"; taJson.spellcheck = false; taJson.placeholder = t.rpJsonBos || "Radardan okunan JSON burada görünür; düzenleyip Yaz ile gönderin.";
    taJson.addEventListener("input", () => { k.jsonElleDegisti = true; });
    const btnJsonYaz = dugme("ra-pc-sb-yaz", "fa-upload", t.rpYaz || "Yaz");
    btnJsonYaz.addEventListener("click", ev => {
      ev.stopPropagation();
      let metin = taJson.value.trim(); if (!metin) return;
      try { JSON.parse(metin); } catch (e) { k.jsonNot.textContent = (t.rpJsonGecersiz || "JSON geçersiz: ") + e.message; return; }
      const onay = t.rpJsonOnay || "JSON yapılandırması radara yazılacak ve kalıcı olacak. Devam edilsin mi?";
      const yap = () => { gonder(rid, { tip: "radar_json_yaz", json_tip: Number(sbJsonTip.value), metin }); k.jsonElleDegisti = false; k.jsonNot.textContent = t.raSonucGonderiliyor || "Gönderiliyor…"; };
      if (typeof onayIste === "function") onayIste(onay, yap); else if (confirm(onay)) yap();
    });
    const jsonNot = not();
    bJson.append(etiketli(t.rpJsonTip || "Dosya", sbJsonTip), satir(btnJsonOku, btnJsonYaz), taJson, jsonNot);

    // 7) HEDEFLER (UPLOAD_TRACK_V3 / TARGET_V3)
    const bHed = bolum(t.rpBolumHedefler || "Hedefler", "fa-cubes");
    const hedOzet = document.createElement("div"); hedOzet.className = "ra-pc-satir-bilgi";
    const tablo = document.createElement("table"); tablo.className = "ra-pc-tablo";
    tablo.innerHTML = "<thead><tr><th>İz</th><th>" + (t.rhTip || "Tip") + "</th><th>" + (t.rhMesafe || "Mesafe") + "</th><th>" + (t.rhAzimut || "Az") +
      "</th><th>" + (t.rhYukseklik || "Yük") + "</th><th>" + (t.rhHiz || "Hız") + "</th><th>SNR</th><th></th></tr></thead><tbody></tbody>";
    const hedBos = not(); hedBos.textContent = t.hedefYokBuyuk || "GÖSTERİLECEK HEDEF YOK";
    bHed.append(hedOzet, tablo, hedBos);

    // 8) SAĞLIK
    const bSag = bolum(t.lblRadarSaglik || "Radar sağlığı", "fa-heart-pulse", false);
    const sagAlan = document.createElement("div"); sagAlan.className = "ra-pc-saglik";
    const sagSatir = (etiket) => { const s = document.createElement("div"); s.className = "rs-satir";
      const e = document.createElement("span"); e.className = "rs-etiket"; e.textContent = etiket; const d = document.createElement("span"); d.className = "rs-deger"; d.textContent = "-"; s.append(e, d); sagAlan.appendChild(s); return d; };
    const sag = { calisma: sagSatir(t.rsCalismaSuresi || "Çalışma süresi"), veri: sagSatir(t.rsVeriHizi || "Veri hızı"), son: sagSatir(t.rsSonVeri || "Son veri"),
                  hb: sagSatir(t.rsHbGecikme || "Kalp atışı gecikmesi"), mesaj: sagSatir(t.rsToplamMesaj || "Toplam mesaj"), crc: sagSatir(t.rsCrcHata || "Bozuk çerçeve"),
                  nokta: sagSatir(t.rpNoktaIzi || "Nokta izi (son kare / kare)") };
    bSag.appendChild(sagAlan);

    p.append(baslik, govde);
    Object.assign(k, { pencere: p, baslik, ad, rozetMod, rozetBag, adres, btnBaglan, durumSatir, durumNot, sbMod, btnBaslat, btnDurdur, calDurum, calNot,
                       sbFrekans, sbTespit, sbHiz, sbRcs, btnTesUygula, tesNot, tesTaslak: false, konumBilgi, btnRtk, rtkKutu, rtkBar, rtkNot, inYon,
                       secBilgi, secListe, secNot, sbJsonTip, taJson, jsonNot, jsonElleDegisti: false, jsonSonTs: 0, hedOzet, tablo, hedBos, sag, sonAyarKaynak: "" });
    document.body.appendChild(p);
    const kayitVar = typeof window.pencereKonumUygula === "function" && window.pencereKonumUygula("rapc_" + rid, p, true);
    if (!kayitVar){
      const n = Object.keys(pencereler).length;
      p.style.left = Math.max(8, (window.innerWidth - 470) / 2 + n * 32) + "px";
      p.style.top = Math.max(8, 70 + n * 32) + "px";
    }
    surukleKur(k);
    if (typeof ResizeObserver !== "undefined"){
      let ilk = true;
      new ResizeObserver(() => { if (ilk){ ilk = false; return; } if (typeof window.pencereKonumKaydet === "function") window.pencereKonumKaydet("rapc_" + rid, p, true); }).observe(p);
    }
    p.addEventListener("mousedown", () => oneAl(k));
    k.zaman = setInterval(() => { if (!p.isConnected){ clearInterval(k.zaman); return; } tazele(k); }, 1000);
    tazele(k);
    gonder(rid, { tip: "radar_ayar_oku" });
    return k;
  }

  function oneAl(k){
    const ust = [...document.querySelectorAll(".m50-pc, .kam-pencere")].reduce((v, el) => Math.max(v, Number(el.style.zIndex || 2450)), 2450);
    k.pencere.style.zIndex = String(ust + 1);
  }
  function surukleKur(k){
    let s = null; const b = k.baslik, p = k.pencere;
    b.addEventListener("pointerdown", ev => { if (ev.target.closest("button")) return; const r = p.getBoundingClientRect(); s = { dx: ev.clientX - r.left, dy: ev.clientY - r.top }; b.setPointerCapture(ev.pointerId); ev.preventDefault(); });
    b.addEventListener("pointermove", ev => { if (!s) return; const minT = (typeof window.pencereMinTop === "function") ? window.pencereMinTop() : 48;
      p.style.left = Math.min(Math.max(ev.clientX - s.dx, 0), window.innerWidth - 120) + "px"; p.style.top = Math.min(Math.max(ev.clientY - s.dy, minT), window.innerHeight - 40) + "px"; });
    const bitir = () => { if (!s) return; s = null; if (typeof window.pencereKonumKaydet === "function") window.pencereKonumKaydet("rapc_" + k.rid, p, true); };
    b.addEventListener("pointerup", bitir); b.addEventListener("pointercancel", bitir);
  }

  // ---- telemetriyle tazeleme ----
  function tazele(k){
    const t = T();
    const r = raBul(k.rid);
    if (!r){ k.ad.textContent = "Radar " + k.rid; return; }
    const bagli = r.durum === "bagli";
    k.ad.textContent = r.isim || ("Radar " + k.rid);
    k.rozetBag.textContent = (t["raDurum_" + (r.durum || "kapali")] || r.durum || "kapalı").toUpperCase();
    k.rozetBag.className = "m50-pc-rozet" + (bagli ? " bagli" : "");
    const a = r.ayarlar || {};
    const modAd = a.calisma_modu ? (t["raMod" + a.calisma_modu.charAt(0).toUpperCase() + a.calisma_modu.slice(1)] || a.calisma_modu) : "";
    k.rozetMod.textContent = bagli && modAd ? modAd.toUpperCase() : "";
    k.rozetMod.style.display = k.rozetMod.textContent ? "" : "none";
    // bağlantı
    k.adres.textContent = r.kayit_ip ? (r.kayit_ip + ":" + (r.kayit_port || 5001)) : (t.clAdresYok || "adres yok");
    k.btnBaglan.querySelector("span").textContent = (bagli || r.durum === "baglaniyor") ? (t.btnRadarKes || "RADARI KES") : (t.btnRadarBaglan || "RADARA BAĞLAN");
    k.btnBaglan.classList.toggle("bagli", bagli);
    k.btnBaglan.disabled = (r.durum === "baglaniyor");
    k.durumSatir.textContent = (t.lblRadarDurum || "Durum") + ": " + (t["raDurum_" + (r.durum || "kapali")] || r.durum) + (r.ip && bagli ? " · " + r.ip + ":" + r.port : "");
    k.durumSatir.className = "ra-pc-durum d-" + (r.durum || "kapali");
    k.durumNot.textContent = (r.durum === "hata" && r.hata) ? r.hata : "";
    // çalışma
    k.calDurum.textContent = bagli ? ((t.lblRaMod || "Çalışma modu") + ": " + (modAd || "?")) : (t.raBagliDegil || "Radar bağlı değil.");
    k.btnBaslat.disabled = !bagli; k.btnDurdur.disabled = !bagli;
    k.btnBaslat.classList.toggle("aktif", bagli && a.calisma_modu && a.calisma_modu !== "bekleme");
    if (a.son_sonuc && a.son_sonuc !== k.sonSetregSonuc){ k.sonSetregSonuc = a.son_sonuc; k.calNot.textContent = sonucMetni(t, a.son_sonuc); k.tesNot.textContent = sonucMetni(t, a.son_sonuc); }
    // tespit ayarları (kullanıcı taslağı yokken radardan doldur)
    const odak = document.activeElement;
    if (!k.tesTaslak && a.kaynak === "radar" && ![k.sbFrekans, k.sbTespit, k.sbHiz, k.sbRcs].includes(odak)){
      if (a.frekans != null) k.sbFrekans.value = String(a.frekans);
      if (a.tespit_esigi != null) k.sbTespit.value = String(a.tespit_esigi);
      if (a.hiz_esigi != null) k.sbHiz.value = String(a.hiz_esigi);
      if (a.rcs_esigi != null) k.sbRcs.value = String(a.rcs_esigi);
      if (!k.tesNot.textContent) k.tesNot.textContent = t.raRadardanOkundu || "Değerler radardan okundu.";
    }
    for (const s of [k.sbFrekans, k.sbTespit, k.sbHiz, k.sbRcs]) s.disabled = !bagli;
    k.btnTesUygula.disabled = !bagli || !k.tesTaslak;
    // konum & yön
    const kaynak = (typeof r.lat === "number") ? (t.raKonumRtk || "Konum: RTK") : (r.kayit_lat != null ? (t.raKonumKayit || "Konum: kayıtlı") : (t.raKonumMerkez || "Konum: merkez"));
    const lat = (typeof r.konum_lat === "number") ? r.konum_lat : null, lon = (typeof r.konum_lon === "number") ? r.konum_lon : null;
    k.konumBilgi.textContent = kaynak + (lat != null ? "  " + lat.toFixed(6) + ", " + lon.toFixed(6) : "") + (typeof r.hdt === "number" ? "  · HDT " + r.hdt.toFixed(2) + "°" : "");
    k.btnRtk.disabled = !bagli || k.rtkBekliyor;
    if (k.rtkBekliyor){
      if (r.rtk_durum === "aliniyor"){ k.rtkBar.style.width = (r.rtk_ilerleme || 0) + "%"; k.rtkNot.textContent = (t.rtkAliniyor || "RTK verisi alınıyor…") + " %" + (r.rtk_ilerleme || 0); }
      else if (r.rtk_durum === "tamam"){ k.rtkBar.style.width = "100%"; k.rtkNot.textContent = (t.rtkTamam || "RTK konumu alındı") + (lat != null ? " (" + lat.toFixed(6) + ", " + lon.toFixed(6) + ")" : ""); k.rtkBekliyor = false; setTimeout(() => { k.rtkKutu.style.display = "none"; }, 4000); }
      else if (r.rtk_durum === "hata"){ k.rtkNot.textContent = t.rtkHata || "RTK konumu alınamadı"; k.rtkBekliyor = false; setTimeout(() => { k.rtkKutu.style.display = "none"; }, 4000); }
    }
    if (odak !== k.inYon && typeof a.merkez_yonu === "number") k.inYon.value = a.merkez_yonu.toFixed(2);
    // seçili iz
    const secili = Array.isArray(a.secili_izler) ? a.secili_izler : [];
    k.secBilgi.textContent = (t.rpSeciliIz || "Radarda seçili iz") + ": " + (secili.length ? secili.join(", ") : (t.rpSecimYok || "yok"));
    if (a.secim_sonuc && a.secim_sonuc !== k.sonSecimSonuc){ k.sonSecimSonuc = a.secim_sonuc; k.secNot.textContent = sonucMetni(t, a.secim_sonuc); }
    // JSON
    if (a.json_ts && a.json_ts !== k.jsonSonTs && (k.jsonBekleyenTip == null || Number(a.json_tip) === k.jsonBekleyenTip)){
      k.jsonSonTs = a.json_ts;
      if (!k.jsonElleDegisti || !k.taJson.value.trim()){
        let metin = a.json_metin || "";
        try { metin = JSON.stringify(JSON.parse(metin), null, 2); } catch (e) {}
        k.taJson.value = metin; k.jsonElleDegisti = false;
      }
      if (a.json_tip != null) k.sbJsonTip.value = String(a.json_tip);
    }
    if (a.json_sonuc && a.json_sonuc !== k.sonJsonSonuc){ k.sonJsonSonuc = a.json_sonuc; k.jsonNot.textContent = sonucMetni(t, a.json_sonuc); }
    // hedefler
    hedefleriCiz(k, r, secili, t);
    // sağlık
    const simdi = Date.now() / 1000;
    k.sag.calisma.textContent = r.baglanti_ani ? sure(simdi - r.baglanti_ani) : "-";
    k.sag.veri.textContent = (typeof r.veri_hizi === "number") ? r.veri_hizi.toFixed(1) + " Hz" : "-";
    if (r.son_veri_ani){ const f = Math.max(0, simdi - r.son_veri_ani); k.sag.son.textContent = f.toFixed(1) + " " + (t.rsSnOnce || "sn önce"); k.sag.son.style.color = f > 5 ? "var(--kotu, #e05555)" : ""; }
    else { k.sag.son.textContent = "-"; k.sag.son.style.color = ""; }
    k.sag.hb.textContent = (typeof r.hb_gecikme_ms === "number" && r.hb_gecikme_ms >= 0) ? Math.round(r.hb_gecikme_ms) + " ms" : "-";
    k.sag.mesaj.textContent = (typeof r.toplam_mesaj === "number") ? String(r.toplam_mesaj) : "-";
    k.sag.crc.textContent = (typeof r.crc_hata === "number") ? String(r.crc_hata) : "-";
    k.sag.crc.style.color = r.crc_hata > 0 ? "var(--uyari, #d9a406)" : "";
    k.sag.nokta.textContent = (typeof r.nokta_kare === "number" && r.nokta_kare > 0) ? (r.nokta_sayisi || 0) + " / " + r.nokta_kare : "-";
  }

  function hedefleriCiz(k, r, secili, t){
    const izler = radarIzleri(k.rid);
    const tb = k.tablo.querySelector("tbody");
    const bagli = r.durum === "bagli";
    k.hedOzet.textContent = (t.rpIzSayisi || "Canlı iz") + ": " + izler.length + (typeof r.nokta_sayisi === "number" && r.nokta_kare ? "  · " + (t.rpNokta || "nokta") + ": " + r.nokta_sayisi : "");
    k.hedBos.style.display = izler.length ? "none" : "";
    k.tablo.style.display = izler.length ? "" : "none";
    const gorulen = new Set();
    for (const h of izler){
      const rid = radarIzKimligi(h); gorulen.add(String(h.id));
      let tr = tb.querySelector("tr[data-id='" + h.id + "']");
      if (!tr){
        tr = document.createElement("tr"); tr.dataset.id = String(h.id);
        tr.innerHTML = "<td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>";
        const bSec = document.createElement("button"); bSec.type = "button"; bSec.className = "kucuk ra-pc-sec"; bSec.textContent = t.rpSec || "Seç";
        bSec.addEventListener("click", ev => { ev.stopPropagation(); gonder(k.rid, { tip: "radar_secim_yaz", izler: [rid] }); k.secNot.textContent = t.raSonucGonderiliyor || "Gönderiliyor…"; });
        tr.lastElementChild.appendChild(bSec);
        tr.addEventListener("click", () => { if (typeof hedefeFokuslan === "function") hedefeFokuslan(h.id); });
        tb.appendChild(tr);
      }
      const td = tr.children;
      td[0].textContent = "R" + rid; td[1].textContent = (t.radarTipleri && t.radarTipleri[h.tip]) || h.tip || "?";
      td[2].textContent = (h.mesafe != null) ? Math.round(h.mesafe) + " m" : "-"; td[3].textContent = (h.azimut != null) ? Math.round(h.azimut) + "°" : "-";
      td[4].textContent = (h.yukseklik != null) ? Math.round(h.yukseklik) + " m" : "-"; td[5].textContent = (h.hiz != null) ? Number(h.hiz).toFixed(1) + " m/s" : "-";
      td[6].textContent = (h.snr != null) ? Number(h.snr).toFixed(0) + " dB" : "-";
      tr.classList.toggle("secili", secili.includes(rid) || !!h.secili);
      tr.classList.toggle("kayip", h.durum === "SUZULEN" || h.durum === "ADAY");
      tr.querySelector("button").disabled = !bagli;
    }
    for (const tr of Array.from(tb.children)) if (!gorulen.has(tr.dataset.id)) tr.remove();
  }

  // ---- dışa açık yüz ----
  window.radarPencereAc = function(rid){
    rid = Number(rid); if (!rid) return false;
    let k = pencereler[rid];
    if (k && document.body.contains(k.pencere)){ oneAl(k); tazele(k); return true; }
    k = pencereKur(rid); pencereler[rid] = k; oneAl(k); return true;
  };
  window.radarPencereKapat = function(rid){
    const k = pencereler[Number(rid)]; if (!k) return;
    clearInterval(k.zaman); k.pencere.remove(); delete pencereler[Number(rid)];
  };
  window.radarPencereAcikMi = function(rid){ const k = pencereler[Number(rid)]; return !!(k && document.body.contains(k.pencere)); };
  // radar_panel.js radarListesiGuncelle her telemetride çağırır
  window.radarPencereleriTazele = function(){
    for (const id of Object.keys(pencereler)){
      const k = pencereler[id];
      if (!document.body.contains(k.pencere)){ delete pencereler[id]; continue; }
      try { tazele(k); } catch (e) {}
    }
  };
})();
