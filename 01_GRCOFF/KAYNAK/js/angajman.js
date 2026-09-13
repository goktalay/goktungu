// FAZ18-IS27-28-30: ikon+metin dugmelerinde metin <span> icine
// sarildi. Sebep: dugme_birlik.css yalniz-ikon kurali
// `:has(> i):not(:has(> span))` bu dugmeleri 26px kareye
// zorluyordu ve metin tasiyordu. CSS EZILMEDI; sozlesmeye
// uyuldu. Yalniz-ikon dugmelere DOKUNULMADI.
// =================================================================
// GOKTUNGU - ANGAJMAN POPUP AKISI (HEDEF-BAZLI + DRON-BAZLI)
// =================================================================
// Popup: ust bolum = angajman parametreleri
//        alt bolum = acik dron listesi (radio secim)
//        alt dugmeler = ANGAJE OL + IPTAL
// =================================================================

// Aktif angajmanlar: saldiran_sysid -> {hedef_tip, hedef_id, durum}
var aktifAngajmanlar = {};

// ---------------------------------------------------------------
// POPUP AC
// mod: "hedef" | "dron" | "goruntu"
// kaynakId: radar hedefi, dron sysid veya `kopru:kamera:iz` kimligi
// kaynakBaglam: goruntu hedefinde kaynak kopru/kamera/iz ve bagli dron ozeti
// ---------------------------------------------------------------
function angajmanPopupAc(mod, kaynakId, kaynakBaglam) {
  angajmanPopupKapat(); // Onceki popup varsa kapat
  const t = D();
  const goruntuMu = mod === "goruntu";
  const angajmanKipi = goruntuMu ? "goruntu" : "telemetri";
  const kaynak = (kaynakBaglam && typeof kaynakBaglam === "object") ? kaynakBaglam : {};

  function kaliciDronUid(d) {
    if (!d) return "";
    return String(d.dron_uid || d.kalici_uid || d.kayit_uid || d.uid || "");
  }

  const kaynakDronUid = String(kaynak.kaynak_dron_uid || kaynak.dron_uid || "");

  // Acik (bagli) dronlari listele
  const dronlar = [];
  for (const [sid, d] of Object.entries(sonVeri)) {
    if (!d.baglanti) continue;
    if (mod === "dron" && parseInt(sid) === kaynakId) continue; // kendisi haric
    dronlar.push(d);
  }

  const perde = document.createElement("div");
  perde.id = "angajmanPerde";
  perde.className = "ang-perde";
  // v2.4.164: yerel AI takibinden gelen angajman YÜZEN panelde açılır
  // (arka plan kararmaz, video izlenmeye devam eder, panel sürüklenir).
  const yuzen = !!kaynak.yuzen;
  if (yuzen) perde.classList.add("ang-yuzen");

  const kutu = document.createElement("div");
  kutu.className = "ang-kutu";

  // Baslik
  const baslik = document.createElement("div");
  baslik.className = "ang-baslik";
  const baslikIkon = goruntuMu ? "fa-camera" : (mod === "hedef" ? "fa-crosshairs" : "fa-plane-up");
  const baslikMetin = goruntuMu
    ? (t.angGoruntuAngajman || "GÖRÜNTÜ İŞLEME ANGAJMANI")
    : (mod === "hedef"
      ? (t.angHedefAngajman || "HEDEFE ANGAJMAN")
      : (t.angDronAngajman || "DRONA ANGAJMAN"));
  baslik.innerHTML = "<i class='fa-solid " + baslikIkon + "'></i> " + baslikMetin;
  kutu.appendChild(baslik);

  // İş 108: telemetri ve görüntü angajmanı aynı motoru kullansa da
  // operatöre iki ayrı kaynak kipi olarak gösterilir. Görüntü seçimi
  // telemetri hedefinin yerine geçmez.
  const kipBandı = document.createElement("div");
  kipBandı.className = "ang-kip-bandi " + (goruntuMu ? "goruntu" : "telemetri");
  const kipIkon = document.createElement("i");
  kipIkon.className = "fa-solid " + (goruntuMu ? "fa-camera" : "fa-tower-broadcast");
  const kipYazi = document.createElement("span");
  kipYazi.textContent = goruntuMu
    ? (t.angKipGoruntu || "KİP: GÖRÜNTÜ İLE ANGAJMAN")
    : (t.angKipTelemetri || "KİP: TELEMETRİ İLE ANGAJMAN");
  kipBandı.appendChild(kipIkon);
  kipBandı.appendChild(kipYazi);
  kutu.appendChild(kipBandı);

  // Hedef bilgisi
  const hedefBilgi = document.createElement("div");
  hedefBilgi.className = "ang-hedef-bilgi";
  if (mod === "hedef") {
    const hv = takipSonVeri[kaynakId] || sonRadarHedefler.find(h => h.id === kaynakId);
    const tipAd = hv ? ((t.radarTipleri && t.radarTipleri[hv.tip]) || hv.tip) : "?";
    hedefBilgi.innerHTML = "<i class='fa-solid fa-bullseye'></i> " +
      (t.angHedef || "Hedef") + ": <strong>R" + kaynakId + " · " + tipAd + "</strong>";
  } else if (goruntuMu) {
    const ikon = document.createElement("i");
    ikon.className = "fa-solid fa-camera";
    hedefBilgi.appendChild(ikon);
    hedefBilgi.appendChild(document.createTextNode(" " + (t.angGoruntuHedef || "Seçili Görüntü İzi") + ": "));
    const guclu = document.createElement("strong");
    guclu.textContent = String(kaynak.ad || ("İz #" + (kaynak.iz_id || String(kaynakId).split(":").pop())));
    hedefBilgi.appendChild(guclu);
  } else {
    const dd = sonVeri[kaynakId];
    const ad = dd ? (dd.tip || dd.isim || "D" + kaynakId) : "D" + kaynakId;
    hedefBilgi.innerHTML = "<i class='fa-solid fa-plane-up'></i> " +
      (t.angHedefDron || "Hedef Dron") + ": <strong>D" + kaynakId + " · " + ad + "</strong>";
  }
  kutu.appendChild(hedefBilgi);

  if (goruntuMu) {
    const kaynakBilgi = document.createElement("div");
    kaynakBilgi.className = "ang-hedef-bilgi ang-goruntu-kaynak";
    const satirlar = [
      [(kaynak.yerel ? "Kaynak" : (t.angKaynakKopru || "Görüntü Köprüsü")),
       kaynak.yerel ? "Yerel AI takibi" : (kaynak.kopru_ad || kaynak.ornek_id || "—")],
      [(t.angKaynakKamera || "Kamera"), kaynak.kamera_ad || kaynak.kamera_id || "—"],
      [(t.angKaynakIz || "Yerel İz"), kaynak.iz_id != null ? ("#" + kaynak.iz_id) : "—"],
      [(t.angKaynakDron || "Kamera Dronu"), kaynakDronUid || (t.angKaynakDronYok || "BAĞLI DEĞİL — icra dronu seçilmelidir")]
    ];
    satirlar.forEach(function (veri) {
      const satir = document.createElement("div");
      satir.className = "ang-goruntu-kaynak-satir";
      const etiket = document.createElement("span");
      etiket.textContent = veri[0];
      const deger = document.createElement("strong");
      deger.textContent = String(veri[1]);
      satir.appendChild(etiket);
      satir.appendChild(deger);
      kaynakBilgi.appendChild(satir);
    });
    kutu.appendChild(kaynakBilgi);
    if (kaynak.yerel) {
      // Canlı hedef konumu / güvenilirlik (takip modülünden)
      const canli = document.createElement("div");
      canli.className = "ang-hedef-bilgi ang-yerel-canli";
      kutu.appendChild(canli);
      let baglandi = false;
      const tazele = function () {
        // Panel henüz sayfaya eklenmemiş olabilir; eklendikten sonra
        // kaldırılırsa (panel kapandı) zamanlayıcı durur.
        if (!canli.isConnected) { if (baglandi) clearInterval(zam); return; }
        baglandi = true;
        const tk = (typeof window.kameraTakipDurumu === "function")
          ? window.kameraTakipDurumu(kaynak.kamera_id) : null;
        if (!tk || !tk.aktif) {
          canli.innerHTML = "<i class='fa-solid fa-triangle-exclamation'></i> Takip yok veya hedef kayboldu";
          canli.dataset.durum = "hata";
        } else if (tk.hedef_id) {
          const yontem = tk.kamera_tipi === "dron"
            ? "dron telemetrisiyle tahmin" : "sabit kamera kalibrasyonu";
          canli.innerHTML = "<i class='fa-solid fa-location-crosshairs'></i> Hedef konumu: <strong>" +
            Number(tk.hedef_lat).toFixed(6) + ", " + Number(tk.hedef_lon).toFixed(6) +
            "</strong>" + (tk.mesafe_m ? " · ~" + Math.round(tk.mesafe_m) + " m" : "") +
            " · " + yontem;
          canli.dataset.durum = "iyi";
        } else {
          canli.innerHTML = "<i class='fa-solid fa-circle-exclamation'></i> Konum çözülemiyor: " +
            String(tk.konum_gerekce || "bekleniyor").replace(/[<>&]/g, "");
          canli.dataset.durum = "uyari";
        }
      };
      const zam = setInterval(tazele, 500);
      tazele();
    }
  }

  // v2.4.161: KAMERA KALIBRASYONU angajman panelinde (kamera formundan
  // tasindi). Yalniz goruntu angajmaninda ve kaynak kamera biliniyorsa.
  const kalib = goruntuMu ? angajmanKalibBolumu(kutu, kaynak, t) : null;

  // Parametreler
  const paramDiv = document.createElement("div");
  paramDiv.className = "ang-param";
  paramDiv.innerHTML =
    "<div class='ang-param-baslik'>" + (t.angParamBaslik || "ANGAJMAN PARAMETRELERİ") + "</div>" +
    "<div class='ang-param-satir'><span>" + (t.angGudumHz || "Güdüm Frekansı (Hz)") +
      "</span><input type='text' id='angParamGudumHz' value='10' spellcheck='false'></div>" +
    "<div class='ang-param-satir'><span>" + (t.angYakalama || "Yakalama Mesafesi (m)") +
      "</span><input type='text' id='angParamYakalama' value='2.0' spellcheck='false'></div>" +
    "<div class='ang-param-satir ang-tamhiz'><span>" +
      (t.angHucum || "Hücum Hızı") + "</span>" +
      "<b id='angHucumSabit'>" + (t.angTamHiz || "MAKSİMUM (TAM HIZ)") +
      "</b><span class='ang-kmh'>" +
      ((typeof HIZ_MAKS_MS !== "undefined" ? HIZ_MAKS_MS : 83.3) * 3.6)
        .toFixed(0) + " km/h</span></div>" +
    // ----------------------------------------------------------------
    // v2.4.43: ONGORU (KESISME) SECENEKLERI
    // Kullanici istegi: "angajman asamasinda gorevi dikkate alip
    // almayacagini angajman ayarlarinda sorsun".
    // Iki ayri anahtar: (1) kesisme ongorusu, (2) hedefin gorev rotasi.
    // Gorev anahtarinin ongoruye bagimliligi vardir: ongoru kapaliysa
    // gorev de kullanilamaz, bu yuzden alt secenek olarak girintili.
    // ----------------------------------------------------------------
    "<div class='ang-param-baslik ang-param-baslik2'>" +
      (t.angOngoruBaslik || "KESİŞME ÖNGÖRÜSÜ") + "</div>" +
    "<div class='ang-param-satir ang-anahtar-satir'>" +
      "<span>" + (t.angOngoru || "Kesişme noktasına yönel") + "</span>" +
      "<label class='ang-anahtar'><input type='checkbox' id='angParamOngoru' checked>" +
      "<span class='ang-anahtar-kaydir'></span></label></div>" +
    "<div class='ang-param-satir ang-anahtar-satir ang-alt-secenek' id='angGorevSatir'>" +
      "<span>" + (t.angGorevDikkate || "Hedefin görev rotasını dikkate al") + "</span>" +
      "<label class='ang-anahtar'><input type='checkbox' id='angParamGorev' checked>" +
      "<span class='ang-anahtar-kaydir'></span></label></div>" +
    "<div class='ang-param-not' id='angOngoruNot'>" +
      (t.angOngoruNot || "Kapalı: hedefin anlık konumu izlenir (saf takip).") +
    "</div>";
  kutu.appendChild(paramDiv);

  // v2.4.43: kayitli ayarlari uygula (varsa) ve bagimliligi kur
  const ongoruKutu = paramDiv.querySelector("#angParamOngoru");
  const gorevKutu = paramDiv.querySelector("#angParamGorev");
  const gorevSatir = paramDiv.querySelector("#angGorevSatir");
  const notEl = paramDiv.querySelector("#angOngoruNot");
  const kayitli = (typeof window.angajmanAyar === "object" && window.angajmanAyar)
    ? window.angajmanAyar : {};
  if (kayitli.ongoru === false) ongoruKutu.checked = false;
  if (kayitli.gorev_dikkate === false) gorevKutu.checked = false;
  if (typeof kayitli.gudum_hz === "number")
    paramDiv.querySelector("#angParamGudumHz").value = String(kayitli.gudum_hz);
  if (typeof kayitli.yakalama_mesafe === "number")
    paramDiv.querySelector("#angParamYakalama").value = String(kayitli.yakalama_mesafe);

  function ongoruDurumTazele() {
    const acik = ongoruKutu.checked;
    gorevSatir.classList.toggle("ang-devre-disi", !acik);
    gorevKutu.disabled = !acik;
    notEl.textContent = acik
      ? (gorevKutu.checked
          ? (t.angOngoruNotGorev || "Hedef görevdeyse rota bacağı, değilse hız vektörü kullanılır.")
          : (t.angOngoruNotHiz || "Yalnız hedefin hız vektörü kullanılır; görev rotası yok sayılır."))
      : (t.angOngoruNot || "Kapalı: hedefin anlık konumu izlenir (saf takip).");
  }
  ongoruKutu.addEventListener("change", ongoruDurumTazele);
  gorevKutu.addEventListener("change", ongoruDurumTazele);
  ongoruDurumTazele();
  // v2.4.18: Hucum hizi ARTIK SORULMUYOR - daima maksimum hiz kullanilir.
  // Sunucu, saldiran dronun parametrelerinden okunan ust siniri (yoksa
  // 300 km/h) uygular; yaklasma yavaslamasi devre disidir.

  // Dron listesi
  const listeDiv = document.createElement("div");
  listeDiv.className = "ang-liste";
  const listeBaslik = document.createElement("div");
  listeBaslik.className = "ang-liste-baslik";
  listeBaslik.textContent = t.angDronSec || "SALDIRAN DRON SEÇ";
  listeDiv.appendChild(listeBaslik);

  let seciliSysid = null;
  if (dronlar.length === 0) {
    const bos = document.createElement("div");
    bos.className = "ang-liste-bos";
    bos.textContent = t.angDronYok || "Bağlı dron bulunamadı";
    listeDiv.appendChild(bos);
  } else {
    for (const d of dronlar) {
      const satir = document.createElement("div");
      satir.className = "ang-dron-satir";
      satir.dataset.sysid = d.sysid;
      const tipAd = d.tip || d.isim || "D" + d.sysid;
      const renk = tipRengi(d.tip);
      satir.innerHTML =
        "<span class='ang-dron-nokta' style='background:" + renk + "'></span>" +
        "<span class='ang-dron-ad'>D" + d.sysid + " · " + tipAd + "</span>" +
        "<span class='ang-dron-detay'>" +
          (typeof d.alt_rel === "number" ? Math.round(d.alt_rel) + "m" : "-") + " · " +
          (typeof d.groundspeed === "number" ? d.groundspeed.toFixed(1) + "m/s (" + (d.groundspeed * 3.6).toFixed(1) + "km/h)" : "-") +
        "</span>";
      const aktif = aktifAngajmanlar[d.sysid] || aktifAngajmanlar[String(d.sysid)];
      const kaynakDronMu = goruntuMu && kaynakDronUid && kaliciDronUid(d) === kaynakDronUid;
      if (aktif) {
        satir.classList.add("devre-disi");
        satir.title = t.angDronAktif || "Bu dronda zaten etkin bir angajman var; önce iptal edin.";
        const aktifRozet = document.createElement("span");
        aktifRozet.className = "ang-dron-aktif-rozet";
        aktifRozet.textContent = (aktif.hedef_tip === "goruntu")
          ? (t.angKipGoruntuKisa || "GÖRÜNTÜ AKTİF")
          : (t.angKipTelemetriKisa || "TELEMETRİ AKTİF");
        satir.appendChild(aktifRozet);
      } else if (kaynakDronMu) {
        satir.classList.add("secili", "kaynak-dron");
        satir.title = t.angKaynakDronOnSecili || "Kameraya bağlı dron ön seçildi";
        seciliSysid = parseInt(d.sysid);
      }
      satir.addEventListener("click", () => {
        if (aktifAngajmanlar[d.sysid] || aktifAngajmanlar[String(d.sysid)]) return;
        listeDiv.querySelectorAll(".ang-dron-satir").forEach(s => s.classList.remove("secili"));
        satir.classList.add("secili");
        seciliSysid = parseInt(d.sysid);
        btnAngaje.disabled = false;
      });
      listeDiv.appendChild(satir);
    }
  }
  kutu.appendChild(listeDiv);

  // Alt düğmeler
  const altDiv = document.createElement("div");
  altDiv.className = "ang-alt";
  const btnAngaje = document.createElement("button");
  btnAngaje.className = "ang-btn angaje";
  btnAngaje.disabled = seciliSysid === null;
  const baslatMetni = goruntuMu
    ? (t.angGoruntuBaslat || "GÖRÜNTÜ İLE ANGAJMANI BAŞLAT")
    : (t.angTelemetriBaslat || "TELEMETRİ İLE ANGAJMANI BAŞLAT");
  btnAngaje.innerHTML = "<i class='fa-solid fa-crosshairs'></i> " +
    "<span>" + baslatMetni + "</span>";
  btnAngaje.addEventListener("click", () => {
    if (seciliSysid === null) return;
    if (aktifAngajmanlar[seciliSysid] || aktifAngajmanlar[String(seciliSysid)]) {
      btnAngaje.disabled = true;
      return;
    }
    const ghz = parseFloat((document.getElementById("angParamGudumHz").value || "10").replace(",", "."));
    const ym = parseFloat((document.getElementById("angParamYakalama").value || "2").replace(",", "."));
    if (isNaN(ghz) || isNaN(ym)) return;
    // v2.4.161: kalibrasyon degistiyse angajmandan ONCE kaydet
    if (kalib && kalib.degisti()) kalib.kaydet();
    // v2.4.43: ongoru secenekleri
    const ongoruAcik = !!(ongoruKutu && ongoruKutu.checked);
    const gorevAcik = ongoruAcik && !!(gorevKutu && gorevKutu.checked);
    // Secim sonraki angajmanlar icin de hatirlanir
    window.angajmanAyar = Object.assign({}, window.angajmanAyar || {}, {
      ongoru: ongoruAcik, gorev_dikkate: gorevAcik,
      gudum_hz: ghz, yakalama_mesafe: ym
    });
    // v2.4.18: hucum hizi gonderilmez; sunucu daima maksimum hizi uygular
    const hh = (typeof HIZ_MAKS_MS !== "undefined") ? HIZ_MAKS_MS : 83.3;

    const hedefTip = mod === "hedef" ? "radar" : (goruntuMu ? "goruntu" : "dron");
    const hedefId = kaynakId;

    const hedefAd = goruntuMu
      ? String(kaynak.ad || ("Görüntü İzi #" + (kaynak.iz_id || String(kaynakId).split(":").pop())))
      : ((mod === "hedef") ? ("R" + kaynakId) : (function(){
          const dd = (typeof sonVeri !== "undefined") ? sonVeri[kaynakId] : null;
          return dd ? (dd.kullanici_isim || dd.isim || dd.tip || ("D" + kaynakId)) : ("D" + kaynakId);
        })());
    // v2.4.164: YEREL AI takibi -> yerel_angajman_baslat (secili dron ile)
    if (goruntuMu && kaynak.yerel) {
      const tk = (typeof window.kameraTakipDurumu === "function")
        ? window.kameraTakipDurumu(kaynak.kamera_id) : null;
      const uyar = function (m) {
        let e = kutu.querySelector(".ang-yerel-hata");
        if (!e) { e = document.createElement("div"); e.className = "ang-yerel-hata"; altDiv.before(e); }
        e.textContent = m;
      };
      if (!tk || !tk.aktif) { uyar("Takip aktif değil; önce videoda hedefe çift tıklayın."); return; }
      if (!tk.hedef_id) { uyar("Hedef konumu çözülemedi: " + (tk.konum_gerekce || "bekleniyor")); return; }
      angajmanPopupKapat();
      onayIste(
        onayMetni("onayGoruntuAngajman", {dron: seciliSysid, hedef: hedefAd, hiz: hh}),
        () => {
          ws.send(JSON.stringify({
            tip: "yerel_angajman_baslat",
            hedef_id: tk.hedef_id,
            saldiran_sysid: seciliSysid,
            operator_onayi: true,
            gudum_hz: ghz, yakalama_mesafe: ym,
            ongoru: ongoruAcik, gorev_dikkate: gorevAcik
          }));
          ws.send(JSON.stringify({
            tip: "angajman_ayar", gudum_hz: ghz, yakalama_mesafe: ym,
            ongoru: ongoruAcik, gorev_dikkate: gorevAcik
          }));
          if (typeof window.angajmanIzleAc === "function") window.angajmanIzleAc();
        });
      return;
    }
    // Onay diyalogu gosterilmeden once ang-perde'yi kapat (arkada kalmasin)
    angajmanPopupKapat();
    const onayAnahtari = goruntuMu ? "onayGoruntuAngajman" : "onayTelemetriAngajman";
    onayIste(
      onayMetni(onayAnahtari, {dron: seciliSysid, hedef: hedefAd, hiz: hh}),
      () => {
        ws.send(JSON.stringify({
          tip: "angajman_baslat",
          saldiran_sysid: seciliSysid,
          hedef_tip: hedefTip,
          angajman_kipi: angajmanKipi,
          operator_onayi: true,
          hedef_id: hedefId,
          gudum_hz: ghz,
          yakalama_mesafe: ym,
          // v2.4.43
          ongoru: ongoruAcik,
          gorev_dikkate: gorevAcik,
          // Görüntü bağlamı yalnız sunucunun güncel hedefi yeniden doğrulaması
          // ve operatör günlüğünde kaynağın açıkça görünmesi içindir.
          kaynak_kopru_id: goruntuMu ? String(kaynak.ornek_id || "") : undefined,
          kaynak_kamera_id: goruntuMu ? String(kaynak.kamera_id || "") : undefined,
          kaynak_iz_id: goruntuMu ? String(kaynak.iz_id || "") : undefined,
          kaynak_secim_ts: goruntuMu ? Number(kaynak.secim_ts || 0) : undefined
        }));
        // Secimi sunucuda kalici kaydet (bir daha sormaya gerek kalmasin)
        ws.send(JSON.stringify({
          tip: "angajman_ayar",
          gudum_hz: ghz, yakalama_mesafe: ym,
          ongoru: ongoruAcik, gorev_dikkate: gorevAcik
        }));
        // Angajman baslatilinca izleme popup'ini otomatik ac
        if (typeof window.angajmanIzleAc === "function") window.angajmanIzleAc();
      }
    );
  });

  const btnIptal = document.createElement("button");
  btnIptal.className = "ang-btn iptal";
  btnIptal.innerHTML = "<i class='fa-solid fa-xmark'></i> " + "<span>" + ( (t.angIptal || "İPTAL")) + "</span>";
  btnIptal.addEventListener("click", angajmanPopupKapat);

  altDiv.appendChild(btnAngaje);
  altDiv.appendChild(btnIptal);
  kutu.appendChild(altDiv);

  perde.appendChild(kutu);
  document.body.appendChild(perde);

  if (yuzen) {
    // Kapat düğmesi + sürükleme (başlıktan)
    const x = document.createElement("button");
    x.type = "button"; x.className = "ang-yuzen-kapat"; x.title = "Kapat";
    x.innerHTML = "<i class='fa-solid fa-xmark'></i>";
    x.addEventListener("click", angajmanPopupKapat);
    baslik.appendChild(x);
    // Sürükleme (başlıktan); son konum bu oturumda hatırlanır
    try {
      const k = JSON.parse(sessionStorage.getItem("ang_yuzen_konum") || "null");
      if (k && isFinite(k.x) && isFinite(k.y)) {
        kutu.style.left = Math.max(0, Math.min(window.innerWidth - 120, k.x)) + "px";
        kutu.style.top = Math.max(0, Math.min(window.innerHeight - 60, k.y)) + "px";
        kutu.style.right = "auto";
      }
    } catch (_) {}
    let surukle = null;
    baslik.addEventListener("pointerdown", (ev) => {
      if (ev.target.closest("button")) return;
      const r = kutu.getBoundingClientRect();
      surukle = {dx: ev.clientX - r.left, dy: ev.clientY - r.top};
      baslik.setPointerCapture(ev.pointerId);
      ev.preventDefault();
    });
    baslik.addEventListener("pointermove", (ev) => {
      if (!surukle) return;
      kutu.style.left = Math.max(0, ev.clientX - surukle.dx) + "px";
      kutu.style.top = Math.max(0, ev.clientY - surukle.dy) + "px";
      kutu.style.right = "auto";
    });
    baslik.addEventListener("pointerup", () => {
      if (!surukle) return;
      surukle = null;
      try {
        const r = kutu.getBoundingClientRect();
        sessionStorage.setItem("ang_yuzen_konum", JSON.stringify({x: r.left, y: r.top}));
      } catch (_) {}
    });
  } else {
    // Perde tiklaninca kapat
    perde.addEventListener("click", (ev) => {
      if (ev.target === perde) angajmanPopupKapat();
    });
  }
}

// ---------------------------------------------------------------
// v2.4.161: Angajman panelindeki KAMERA KALIBRASYONU bolumu.
// Alanlar kamera kaydindan doldurulur; "Kaydet" ya da angajman baslatma
// kamera_kaydet ile (kameranin diger alanlari korunarak) yazar.
// ---------------------------------------------------------------
function angajmanKalibBolumu(kutu, kaynak, t) {
  const kamId = Number(kaynak.kamera_id);
  const kam = (window._kameralarSon || []).find(k => Number(k.id) === kamId);
  if (!kam) return null;
  const ALANLAR = [
    ["lat", "Enlem (lat)", "sabit"], ["lon", "Boylam (lon)", "sabit"],
    ["kam_yukseklik", "Yer üstü yükseklik (m)", "sabit"],
    ["yon", "Bakış yönü (°, 0=kuzey)", "sabit"],
    ["tilt", "Aşağı eğim (°, +aşağı)", "sabit"],
    ["fov_yatay", "Yatay görüş açısı (°)", "ortak"],
    ["fov_dikey", "Dikey görüş açısı (°)", "ortak"],
    ["montaj_pan", "Montaj pan (°)", "dron"],
    ["montaj_tilt", "Montaj tilt (°)", "dron"],
    ["montaj_roll", "Montaj roll (°)", "dron"],
  ];
  const bolum = document.createElement("details");
  bolum.className = "ang-param ang-kalib";
  bolum.open = !kam.kalibre;   // kalibre degilse acik gelsin
  const ozet = document.createElement("summary");
  ozet.className = "ang-param-baslik";
  const durum = document.createElement("span");
  durum.className = "ang-kalib-durum";
  ozet.append(document.createTextNode(t.angKalibBaslik || "KAMERA KALİBRASYONU"), durum);
  bolum.appendChild(ozet);

  const tipSatir = document.createElement("div");
  tipSatir.className = "ang-param-satir";
  tipSatir.innerHTML = "<span>" + (t.angKalibTip || "Kamera tipi") + "</span>";
  const tipSec = document.createElement("select");
  tipSec.innerHTML = "<option value='sabit'>Sabit kamera</option>" +
                     "<option value='dron'>Drona takılı</option>";
  tipSec.value = kam.kamera_tipi || "sabit";
  tipSatir.appendChild(tipSec);
  bolum.appendChild(tipSatir);

  const girdiler = {};
  const satirlar = [];
  ALANLAR.forEach(([ad, etiket, grup]) => {
    const s = document.createElement("div");
    s.className = "ang-param-satir";
    s.dataset.grup = grup;
    const e = document.createElement("span");
    e.textContent = etiket;
    const g = document.createElement("input");
    g.type = "text"; g.spellcheck = false;
    const v = kam[ad];
    g.value = (v === null || v === undefined) ? "" : String(v);
    s.append(e, g);
    bolum.appendChild(s);
    girdiler[ad] = g;
    satirlar.push(s);
  });
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "ang-btn ang-kalib-kaydet";
  btn.innerHTML = "<i class='fa-solid fa-floppy-disk'></i> <span>" +
    (t.angKalibKaydet || "KALİBRASYONU KAYDET") + "</span>";
  bolum.appendChild(btn);

  function ilk() { return JSON.stringify(topla()); }
  function topla() {
    const o = { kamera_tipi: tipSec.value };
    for (const ad in girdiler) {
      const ham = String(girdiler[ad].value || "").trim().replace(",", ".");
      o[ad] = ham === "" ? null : parseFloat(ham);
    }
    return o;
  }
  function gorunum() {
    satirlar.forEach(s => {
      const gr = s.dataset.grup;
      s.style.display = (gr === "ortak" || gr === tipSec.value) ? "" : "none";
    });
    durum.textContent = kam.kalibre ? " ✓ kalibre" : " ⚠ eksik — angajman reddedilebilir";
    durum.style.color = kam.kalibre ? "#4ade80" : "#fbbf24";
  }
  let baslangic = ilk();
  function kaydet() {
    const c = topla();
    const msg = Object.assign({
      tip: "kamera_kaydet", id: kam.id, isim: kam.isim,
      protokol: kam.protokol, url: kam.url,
      lokasyon_id: kam.lokasyon_id || null,
      kopru_ornek_id: kam.kopru_ornek_id || null,
      dron_uid: kam.dron_uid || "",
      ai_gorevler: kam.ai_gorevler || ""
    }, c);
    try { ws.send(JSON.stringify(msg)); } catch (_) {}
    Object.assign(kam, c);
    baslangic = ilk();
    btn.querySelector("span").textContent = t.angKalibKaydedildi || "KAYDEDİLDİ ✓";
    setTimeout(() => { btn.querySelector("span").textContent = t.angKalibKaydet || "KALİBRASYONU KAYDET"; }, 1500);
  }
  tipSec.addEventListener("change", gorunum);
  btn.addEventListener("click", (ev) => { ev.preventDefault(); kaydet(); });
  gorunum();
  kutu.appendChild(bolum);
  return { degisti: () => ilk() !== baslangic, kaydet };
}

function angajmanPopupKapat() {
  const p = document.getElementById("angajmanPerde");
  if (p) p.remove();
}

// ---------------------------------------------------------------
// SUNUCUDAN ANGAJMAN DURUM GUNCELLEME
// ---------------------------------------------------------------
function angajmanDurumGuncelle(durum) {
  // durum: {saldiran_sysid, hedef_tip, hedef_id, aktif, mesafe}
  if (durum.aktif) {
    aktifAngajmanlar[durum.saldiran_sysid] = durum;
  } else {
    delete aktifAngajmanlar[durum.saldiran_sysid];
  }
  // Dron kartlarinda angajman durumunu goster (ileride genisletilebilir)
}

// Angajman iptal komutu gonder
function angajmanIptalGonder(sysid) {
  if (!ws || ws.readyState !== 1) return;
  ws.send(JSON.stringify({ tip: "angajman_iptal", saldiran_sysid: sysid }));
  delete aktifAngajmanlar[sysid];
}

// ---------------------------------------------------------------
