// FAZ19-IS71-K3-DRONKAMERA-SOKUM: lokasyon kamera baglari kaldirildi (video katmani soküldü)
// =================================================================
// GOKTUNGU - FARE KOORDINATI + ALT+SOL TIK KONUM KAYDET + KAYITLI LOKASYONLAR
// Bu dosya index.html'den mekanik olarak ayrilmistir; yukleme sirasi
// index.html'deki <script> sirasina baglidir (klasik script, ortak scope).
// =================================================================
// FARE KOORDINAT GOSTERGESI (alt bar) + ALT+SOL TIK KONUM KAYDET
// + KAYITLI LOKASYONLAR PANELI
// ---------------------------------------------------------------
(function(){
  const fareKoord = document.getElementById("fareKoordinat");
  const lokPopup  = document.getElementById("lokasyonPopup");
  const lokListe  = document.getElementById("lokasyonListe");
  const lokBosMsg = document.getElementById("lokasyonBos");
  const btnLok    = document.getElementById("btnLokasyonlar");
  const perde     = document.getElementById("lokKaydetPerde");
  const inpAd     = document.getElementById("lokAd");
  const inpAdres  = document.getElementById("lokAdres");
  const inpLat    = document.getElementById("lokEnlem");
  const inpLon    = document.getElementById("lokBoylam");
  const lokHata   = document.getElementById("lokHata");

  let lokasyonlar = [];   // {id, ad, lat, lon} - sunucudan gelir
  let duzenlenenId = null; // satir ici ad duzenleme modu

  // ===== FAZ18-IS23-LOK-IKON: HARITA IKONU =====
  // Olcum: bu modulde `entities.add` HIC cagrilmiyordu; panel satiri
  // ve kamera ucusu vardi, harita ikonu YOKTU. Desen home_ikon.js'ten
  // alindi: ikon canvas'ta uretilir, harici gorsel dosyasi YOK
  // (saha kurulumlari internetsiz calisir).
  const lokVarliklar = {};        // lokasyon id -> Cesium entity
  let lokIkonOnbellek = null;     // dataURL (renk temaya bagli degil)

  // Konum ignesi: taban ignenin ALT UCUNA oturur; billboard
  // `verticalOrigin: BOTTOM` ile ignenin ucu tam koordinata gelir.
  function lokIkonu(){
    if (lokIkonOnbellek) return lokIkonOnbellek;
    const b = 40;
    const c = document.createElement("canvas");
    c.width = b; c.height = b;
    const x = c.getContext("2d");
    x.lineJoin = "round";
    x.lineWidth = 3;
    x.strokeStyle = "rgba(0,0,0,.85)";   // her altlikta okunurluk
    x.fillStyle = "#f59e0b";             // kehribar: dron/hedef renkleriyle cakismaz
    // Damla govdesi
    x.beginPath();
    x.arc(b * 0.50, b * 0.36, b * 0.26, Math.PI * 0.85, Math.PI * 0.15);
    x.lineTo(b * 0.50, b * 0.96);        // ignenin ucu
    x.closePath();
    x.stroke(); x.fill();
    // Ic delik: kucuk olcekte de "konum ignesi" oldugu anlasilir
    x.beginPath();
    x.arc(b * 0.50, b * 0.34, b * 0.10, 0, Math.PI * 2);
    x.fillStyle = "rgba(0,0,0,.6)";
    x.fill();
    lokIkonOnbellek = c.toDataURL();
    return lokIkonOnbellek;
  }

  function lokIkonSil(id){
    const e = lokVarliklar[id];
    if (!e) return;
    try { viewer.entities.remove(e); } catch(_){ /* viewer kapanmis */ }
    delete lokVarliklar[id];
  }

  // Listeyi harita ikonlariyla eslestir. Listeden dusen lokasyonun
  // ikonu SILINIR: eski konumda ignesi birakmak, kullaniciya silinmis
  // bir lokasyonun hala kayitli oldugu izlenimi verirdi.
  function lokIkonSenkron(liste){
    if (typeof viewer === "undefined" || !viewer) return;
    const gorulen = {};
    (liste || []).forEach((l) => {
      if (!l || l.id === undefined || l.id === null) return;
      // IS 29C sozlesmesi: (0,0) ve gecersiz koordinat REDDEDILIR.
      // Kapinin govdesi DEGISTIRILMEDI - dort dosya ona bagli.
      if (typeof window.gecerliKonumMu === "function" &&
          !window.gecerliKonumMu(l.lat, l.lon)){
        lokIkonSil(l.id);
        return;
      }
      gorulen[l.id] = true;
      const ad = (l.ad || "").toString().slice(0, 40);
      let e = lokVarliklar[l.id];
      if (!e){
        e = viewer.entities.add({
          id: "lokasyon_" + l.id,
          position: Cesium.Cartesian3.fromDegrees(l.lon, l.lat, 0),
          billboard: {
            image: lokIkonu(),
            width: 24, height: 24,
            verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
            heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
            disableDepthTestDistance: Number.POSITIVE_INFINITY
          },
          label: {
            text: ad,
            font: "bold 10px Consolas, monospace",
            fillColor: Cesium.Color.fromCssColorString("#f59e0b"),
            style: Cesium.LabelStyle.FILL,
            showBackground: true,
            backgroundColor: Cesium.Color.BLACK.withAlpha(0.7),
            backgroundPadding: new Cesium.Cartesian2(5, 3),
            verticalOrigin: Cesium.VerticalOrigin.TOP,
            pixelOffset: new Cesium.Cartesian2(0, 4),
            heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
            // Uzaklasinca etiket kalabaligi yapmasin; ikon gorunur kalir
            distanceDisplayCondition:
              new Cesium.DistanceDisplayCondition(0, 40000)
          }
        });
        e._lLat = l.lat; e._lLon = l.lon; e._lAd = ad;
        lokVarliklar[l.id] = e;
        return;
      }
      // Konum yalniz GERCEKTEN degistiyse yazilir: liste her kamera
      // isleminde tazeleniyor, her seferinde Cartesian3 uretmek bosa
      // nesne ayirmadir.
      if (e._lLat !== l.lat || e._lLon !== l.lon){
        e.position = Cesium.Cartesian3.fromDegrees(l.lon, l.lat, 0);
        e._lLat = l.lat; e._lLon = l.lon;
      }
      if (e._lAd !== ad){ e.label.text = ad; e._lAd = ad; }
    });
    Object.keys(lokVarliklar).forEach((id) => {
      if (!gorulen[id]) lokIkonSil(id);
    });
  }

  // Tema degisiminde canvas gorseli yeniden uretilir (tema.js kancasi).
  window.lokasyonIkonTazele = function(){
    lokIkonOnbellek = null;
    Object.keys(lokVarliklar).forEach((id) => {
      const e = lokVarliklar[id];
      if (e && e.billboard) e.billboard.image = lokIkonu();
    });
  };
  // ===== FAZ18-IS23-LOK-IKON SONU =====

  // --- Fare koordinat gostergesi ---
  function fareKur(){
    const kap = document.getElementById("cesiumContainer");
    if (!kap || typeof viewer === "undefined" || !viewer){
      setTimeout(fareKur, 500); return;
    }
    kap.addEventListener("mousemove", (e) => {
      const r = kap.getBoundingClientRect();
      const k = window.__ekrandanKoordinat
        ? window.__ekrandanKoordinat(e.clientX - r.left, e.clientY - r.top) : null;
      fareKoord.textContent = k
        ? k.lat.toFixed(6) + "\u00b0, " + k.lon.toFixed(6) + "\u00b0" : "";
    });
    kap.addEventListener("mouseleave", () => { fareKoord.textContent = ""; });

    // --- ALT + SOL TIK: konum kaydet modali ---
    kap.addEventListener("click", (e) => {
      if (!e.altKey || e.ctrlKey) return;
      e.preventDefault(); e.stopPropagation();
      const r = kap.getBoundingClientRect();
      const k = window.__ekrandanKoordinat
        ? window.__ekrandanKoordinat(e.clientX - r.left, e.clientY - r.top) : null;
      if (!k) return;
      inpAd.value = "";
      if (inpAdres) inpAdres.value = "";
      inpLat.value = k.lat.toFixed(6);
      inpLon.value = k.lon.toFixed(6);
      lokHata.textContent = "";
      perde.classList.remove("popup-gizli");
      setTimeout(() => inpAd.focus(), 50);
    }, true);
  }
  fareKur();

  // FAZ18-IS23-LOK-IKON: Acilista bir kez liste iste.
  // Olcum: `lokasyon_liste` yalniz panel acilirsa gidiyordu
  // (bu dosya:92 / kameralar.js:193). Acilista istek olmadigi icin
  // harita ikonlari panel acilmadikca hic gorunmezdi.
  (function lokIlkIstek(){
    if (typeof ws === "undefined" || !ws || ws.readyState !== 1){
      setTimeout(lokIlkIstek, 700); return;
    }
    if (window._lokasyonlarSon) return;   // baska modul zaten istemis
    try { ws.send(JSON.stringify({tip: "lokasyon_liste"})); } catch(_){}
  })();

  function modalKapat(){ perde.classList.add("popup-gizli"); }
  document.getElementById("btnLokIptal").addEventListener("click", modalKapat);
  document.getElementById("btnLokKaydetKapat").addEventListener("click", modalKapat);
  perde.addEventListener("click", (e) => { if (e.target === perde) modalKapat(); });

  document.getElementById("btnLokKaydet").addEventListener("click", () => {
    const t = D();
    const ad = inpAd.value.trim();
    const lat = parseFloat(inpLat.value);
    const lon = parseFloat(inpLon.value);
    if (!ad){ lokHata.textContent = t.lokHataAd; inpAd.focus(); return; }
    if (!isFinite(lat) || !isFinite(lon) ||
        lat < -90 || lat > 90 || lon < -180 || lon > 180){
      lokHata.textContent = t.lokHataKoord; return;
    }
    if (ws && ws.readyState === 1){
      ws.send(JSON.stringify({tip: "lokasyon_ekle", ad: ad, lat: lat, lon: lon,
        adres: (inpAdres ? inpAdres.value.trim() : "")}));
      modalKapat();
    } else {
      lokHata.textContent = t.girisHataSunucu;
    }
  });
  inpAd.addEventListener("keydown", (e) => {
    if (e.key === "Enter") document.getElementById("btnLokKaydet").click();
  });

  // --- KAYITLI LOKASYONLAR PANELI ---
  btnLok.addEventListener("click", (e) => {
    e.stopPropagation();
    const acikti = !lokPopup.classList.contains("popup-gizli");
    lokPopup.classList.toggle("popup-gizli");
    if (!acikti && ws && ws.readyState === 1){
      ws.send(JSON.stringify({tip: "lokasyon_liste"}));
    }
  });
  document.getElementById("btnLokPopupKapat").addEventListener("click",
    () => lokPopup.classList.add("popup-gizli"));
  document.addEventListener("click", (e) => {
    if (!lokPopup.classList.contains("popup-gizli") &&
        !lokPopup.contains(e.target) && e.target !== btnLok && !btnLok.contains(e.target)){
      lokPopup.classList.add("popup-gizli");
    }
  });

  function lokasyonaGit(l){
    if (typeof viewer === "undefined" || !viewer) return;
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(l.lon, l.lat, 3000),
      duration: 1.6
    });
  }

  window.lokasyonListeCiz = function(liste){
    lokasyonlar = liste || [];
    window._lokasyonlarSon = lokasyonlar;  // v2.4.0: kamera bina combobox'i icin
    lokIkonSenkron(lokasyonlar);   /* FAZ18-IS23-LOK-IKON */
    if (typeof window.kameraHaritaLokTazele === "function")
      window.kameraHaritaLokTazele();
    duzenlenenId = null;
    lokListe.innerHTML = "";
    lokBosMsg.style.display = lokasyonlar.length ? "none" : "block";
    lokasyonlar.forEach(l => {
      const satir = document.createElement("div");
      satir.className = "lok-satir";

      const ikon = document.createElement("i");
      ikon.className = "fa-solid fa-location-dot";
      satir.appendChild(ikon);

      const bilgi = document.createElement("div");
      bilgi.className = "lok-bilgi";
      const adDiv = document.createElement("div");
      adDiv.className = "lb-ad"; adDiv.textContent = l.ad;
      const koordDiv = document.createElement("div");
      koordDiv.className = "lb-koord";
      koordDiv.textContent = l.lat.toFixed(6) + ", " + l.lon.toFixed(6);
      bilgi.appendChild(adDiv);
      if (l.adres){
        const adresDiv = document.createElement("div");
        adresDiv.className = "lb-adres";
        adresDiv.textContent = l.adres;
        bilgi.appendChild(adresDiv);
      }
      bilgi.appendChild(koordDiv);
      satir.appendChild(bilgi);

      // Satira tiklaninca haritayi konuma ucur + kameralar popup'ini ac
      satir.addEventListener("click", (e) => {
        if (duzenlenenId === l.id) return;   // duzenleme modunda ucma
        lokasyonaGit(l);
      });

      const islem = document.createElement("div");
      islem.className = "lok-islem";

      // Duzenle: yalniz ad degisir
      const bDuz = document.createElement("button");
      bDuz.title = ((typeof D === "function") ? (D().ipDuzenle) : "") || "D\u00fczenle";
      bDuz.innerHTML = '<i class="fa-solid fa-pen"></i>';
      bDuz.addEventListener("click", (e) => {
        e.stopPropagation();
        if (duzenlenenId === l.id) return;
        duzenlenenId = l.id;
        const inp = document.createElement("input");
        inp.type = "text"; inp.className = "lok-ad-duzenle";
        inp.value = l.ad; inp.maxLength = 60;
        inp.addEventListener("click", (ev) => ev.stopPropagation());
        function kaydet(){
          const yeniAd = inp.value.trim();
          if (yeniAd && yeniAd !== l.ad && ws && ws.readyState === 1){
            ws.send(JSON.stringify({tip: "lokasyon_duzenle", id: l.id, ad: yeniAd}));
          } else {
            window.lokasyonListeCiz(lokasyonlar);  // vazgec / degisiklik yok
          }
        }
        inp.addEventListener("keydown", (ev) => {
          if (ev.key === "Enter") kaydet();
          if (ev.key === "Escape") window.lokasyonListeCiz(lokasyonlar);
        });
        inp.addEventListener("blur", kaydet);
        bilgi.replaceWith(inp);
        inp.focus(); inp.select();
      });
      islem.appendChild(bDuz);

      // Sil
      const bSil = document.createElement("button");
      bSil.title = "Sil";
      bSil.innerHTML = '<i class="fa-solid fa-trash"></i>';
      bSil.addEventListener("click", (e) => {
        e.stopPropagation();
        onayIste(onayMetni("onayLokasyonSil", {ad: l.ad || l.id}), () => {
          if (ws && ws.readyState === 1){
            ws.send(JSON.stringify({tip: "lokasyon_sil", id: l.id}));
          }
        });
      });
      islem.appendChild(bSil);

      satir.appendChild(islem);
      lokListe.appendChild(satir);
    });
  };
})();

// ---------------------------------------------------------------
