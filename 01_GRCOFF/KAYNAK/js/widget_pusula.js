// ============================================================
// GOKTUNGU GCS — PUSULA WIDGET
// v2.4.32
//
// Haritanin 3B yonelimini gosterir: kamera basligi (heading),
// egimi (pitch) ve yatirmasi (roll). Ustte kuzeye gore donen
// kadran, altta sayisal okuma.
//
// TASARIM KARARLARI
//
// 1) NE DONER? Kadran doner, ibre sabit kalir. Bu, ucak/gemi
//    pusulalarinin (HSI) yerlesik davranisidir: operator "benim
//    onum" sabit referansini korur, dunya doner. Kuzey oku
//    kadranla birlikte doner, boylece kuzeyin nerede oldugu
//    dogrudan gorulur.
//
// 2) NEDEN requestAnimationFrame DEGIL? Sahne surekli cizilirken
//    her karede DOM yazmak gereksiz yuktur. Cesium'un
//    `camera.changed` olayi yalnizca kamera GERCEKTEN degisince
//    tetiklenir. Ancak bu olayin varsayilan duyarliligi
//    (`percentageChanged`) buyuk aci degisimleri bekler; pusula
//    icin kucuk donuslerin de yakalanmasi gerekir, bu nedenle
//    duyarlilik dusurulur.
//
// 3) EGIM GOSTERGESI: Cesium'da pitch, asagi bakiste NEGATIF
//    olur (-90 tepeden bakis, 0 ufka bakis). Operator icin
//    "tepeden bakis 90" daha anlasilirdir, bu nedenle isaret
//    ters cevrilerek "bakis acisi" olarak sunulur.
//
// 4) SVG kullanilir, kanvas degil: kadran cizgileri ve yazilar
//    olcekten bagimsiz keskin kalir, tema renkleri CSS
//    degiskenleriyle dogrudan uygulanabilir (kanvasta her tema
//    degisiminde yeniden cizim gerekirdi).
// ============================================================

(function(){
  "use strict";

  const ID = "pusula";
  const M = 100;          // SVG koordinat merkezi (200x200 gorunum)
  const R_DIS = 92;       // dis cember
  const R_KADRAN = 78;    // kadran halkasi

  // v2.4.35: 3B kip sabitleri
  // Kadran duzlemi CSS 3D transform ile uzayda egilir. Egim acisi
  // sinirlandirilir: kadran tam dikleserse yazilar okunmaz hale
  // gelir. Cesium pitch 0..-90 araligi 0..EGIM_MAKS'a eslenir
  // (tepeden bakista duz, ufka bakista egik).
  const EGIM_MAKS = 55;   // derece
  const PERSPEKTIF = 420; // px — kucuk deger asiri bozar
  const YAT_MAKS = 25;    // roll siniri (harita gorunumunde ~0'dir)
  const AYAR_3B = "gcs_pusula_3b";

  let ogeler = null;
  let izleyici = null;    // camera.changed aboneligi
  let onIzleyici = null;  // preRender yedegi
  let sonBaslik = null;
  let sonEgim = null;     // v2.4.35: 3B kipte egim degisimi de tazeleme gerektirir
  let kip3B = true;

  // 3B kip tercihi kalicidir: dusuk donanimda kapatan kullanici
  // her acilista tekrar kapatmak zorunda kalmamali.
  function kip3BOku(){
    try {
      const v = localStorage.getItem(AYAR_3B);
      return v === null ? true : v === "1";
    } catch (e) { return true; }
  }
  function kip3BYaz(a){
    try { localStorage.setItem(AYAR_3B, a ? "1" : "0"); } catch (e) {}
  }

  function ingilizceMi(){
    try {
      if (typeof aktifDil !== "undefined") return String(aktifDil).toLowerCase().startsWith("en");
      const d = localStorage.getItem("gcs_dil");
      return !!(d && d.toLowerCase().startsWith("en"));
    } catch (e) { return false; }
  }

  function svgOge(ad, ozellikler){
    const e = document.createElementNS("http://www.w3.org/2000/svg", ad);
    for (const k in ozellikler) e.setAttribute(k, ozellikler[k]);
    return e;
  }

  // ----------------------------------------------------------
  // GOVDE
  // ----------------------------------------------------------
  function govdeKur(govde, api){
    govde.classList.add("pusula-govde");
    kip3B = kip3BOku();

    // ------------------------------------------------------------
    // v2.4.35: GERCEK 3B YERLESIM
    // ------------------------------------------------------------
    // Kadran duzlemi uzayda egilir. Bunun icin SVG IKIYE bolunur:
    //
    //   sahne (perspective)
    //     +-- duzlem  <div>  rotateX(egim) rotateZ(yat)  -> EGILIR
    //     |     +-- svgAlt : dis cember, ic zemin, kadran
    //     +-- svgUst <svg>  konumu sabit               -> EGILMEZ
    //           +-- ibre, gobek, lubber, egim olcegi, yon adi
    //
    // Neden iki SVG? Tek SVG icinde bir <g>'ye CSS 3D transform
    // vermek ise yaramaz: SVG icindeki gruplar tarayicilarda 3B
    // kompozit katman olarak islenmez (perspective, SVG cocuk
    // ogelerinde guvenilir bicimde uygulanmaz). Egilen katmanin
    // ayri bir HTML <div> olmasi gerekir.
    //
    // Neden ust katman egilmez? HSI mantigi: operatorun referansi
    // (ibre, lubber) sabit kalmalidir. Yalniz "dunya" egilir.
    const sahne = document.createElement("div");
    sahne.className = "pusula-sahne";

    const duzlem = document.createElement("div");
    duzlem.className = "pusula-duzlem";

    const svg = svgOge("svg", {
      viewBox: "0 0 200 200",
      class: "pusula-svg pusula-svg-alt",
    });

    // --- Sabit katman: dis cember + govde ---
    svg.appendChild(svgOge("circle", {
      cx: M, cy: M, r: R_DIS, class: "pusula-dis",
    }));
    svg.appendChild(svgOge("circle", {
      cx: M, cy: M, r: R_KADRAN + 6, class: "pusula-ic-zemin",
    }));

    // --- DONEN KATMAN: kadran ---
    // Tek bir <g> dondurulur; icindeki her sey birlikte doner.
    const kadran = svgOge("g", { class: "pusula-kadran" });

    // Derece cizgileri: her 15 derecede kucuk, her 45'te buyuk
    for (let a = 0; a < 360; a += 15){
      const buyuk = (a % 45 === 0);
      const r1 = R_KADRAN;
      const r2 = R_KADRAN - (buyuk ? 13 : 7);
      const rad = (a - 90) * Math.PI / 180;
      kadran.appendChild(svgOge("line", {
        x1: (M + r1 * Math.cos(rad)).toFixed(2),
        y1: (M + r1 * Math.sin(rad)).toFixed(2),
        x2: (M + r2 * Math.cos(rad)).toFixed(2),
        y2: (M + r2 * Math.sin(rad)).toFixed(2),
        class: buyuk ? "pusula-cizgi-buyuk" : "pusula-cizgi",
      }));
    }

    // Yon harfleri. Ingilizce/Turkce ayrimi: K/D/G/B vs N/E/S/W
    const en = ingilizceMi();
    const yonlar = en
      ? [["N", 0], ["E", 90], ["S", 180], ["W", 270]]
      : [["K", 0], ["D", 90], ["G", 180], ["B", 270]];
    const harfDugumleri = [];
    yonlar.forEach(([harf, aci]) => {
      const rad = (aci - 90) * Math.PI / 180;
      const r = R_KADRAN - 28;
      const t = svgOge("text", {
        x: (M + r * Math.cos(rad)).toFixed(2),
        y: (M + r * Math.sin(rad)).toFixed(2),
        class: "pusula-yon" + (aci === 0 ? " pusula-yon-k" : ""),
        "text-anchor": "middle",
        "dominant-baseline": "central",
      });
      t.textContent = harf;
      kadran.appendChild(t);
      harfDugumleri.push(t);
    });

    // Kuzey ucgeni (kadranla doner, kuzeyin nerede oldugunu gosterir)
    kadran.appendChild(svgOge("path", {
      d: "M " + M + " " + (M - R_KADRAN + 2) +
         " l 7 13 l -14 0 z",
      class: "pusula-kuzey-ucgen",
    }));

    svg.appendChild(kadran);

    // Egilen duzlem tamamlandi: alt SVG duzleme, duzlem sahneye.
    duzlem.appendChild(svg);
    sahne.appendChild(duzlem);

    // ------------------------------------------------------------
    // UST KATMAN (EGILMEZ) — operatorun sabit referanslari
    // ------------------------------------------------------------
    const svgUst = svgOge("svg", {
      viewBox: "0 0 200 200",
      class: "pusula-svg pusula-svg-ust",
    });

    // --- SABIT IBRE (ucagin/operatorun onu) ---
    // Yukari bakan ok: her zaman ekranin yukarisini gosterir.
    svgUst.appendChild(svgOge("path", {
      d: "M " + M + " " + (M - 44) +
         " l 11 30 l -11 -7 l -11 7 z",
      class: "pusula-ibre",
    }));
    svgUst.appendChild(svgOge("circle", {
      cx: M, cy: M, r: 4.5, class: "pusula-gobek",
    }));

    // Ust isaret (lubber line) — ibrenin okundugu sabit nokta
    svgUst.appendChild(svgOge("path", {
      d: "M " + M + " " + (M - R_DIS - 1) + " l 6 11 l -12 0 z",
      class: "pusula-lubber",
    }));

    // --- EGIM GOSTERGESI (yan cubuk) ---
    // Kadranin icinde yatay bir cizgi olarak degil, sagda dikey
    // bir olcek olarak sunulur; boylece kadran okunakli kalir.
    const egimG = svgOge("g", { class: "pusula-egim-g" });
    egimG.appendChild(svgOge("line", {
      x1: 186, y1: 58, x2: 186, y2: 142, class: "pusula-egim-eksen",
    }));
    const egimIsaret = svgOge("path", {
      d: "M 186 100 l -7 -5 l 0 10 z", class: "pusula-egim-isaret",
    });
    egimG.appendChild(egimIsaret);
    svgUst.appendChild(egimG);

    // --- MERKEZ OKUMA (yon adi) ---
    // v2.4.33: Derece sayisi kadran ICINDEN alt satira tasindi
    // (asagiya bkz.). Kadranin ortasinda yalnizca yon kisaltmasi
    // kalir; boylece kadran okunakli olur ve alt satirda
    // "Derece solda / Bakis sagda" duzeni kurulabilir.
    const yonAd = svgOge("text", {
      x: M, y: M + 34, class: "pusula-yon-ad",
      "text-anchor": "middle", "dominant-baseline": "central",
    });
    yonAd.textContent = "";
    svgUst.appendChild(yonAd);

    sahne.appendChild(svgUst);
    govde.appendChild(sahne);

    // ------------------------------------------------------------
    // v2.4.35: 2B / 3B ANAHTARI
    // ------------------------------------------------------------
    // Dusuk donanimda veya duz gorunum tercih edildiginde
    // kapatilabilir. Kucuk bir kose dugmesi; kadranin okunmasini
    // engellememesi icin sag ustte ve yariseffaf.
    const btn3B = document.createElement("button");
    btn3B.type = "button";
    btn3B.className = "pusula-3b-btn";
    btn3B.textContent = kip3B ? "3D" : "2D";
    btn3B.addEventListener("click", (ev) => {
      ev.stopPropagation();
      kip3B = !kip3B;
      kip3BYaz(kip3B);
      btn3B.textContent = kip3B ? "3D" : "2D";
      btn3BIpucuTazele();
      tazele();
    });
    // Tasima ile catismamasi icin surukleme baslangicini engelle
    btn3B.addEventListener("pointerdown", (ev) => ev.stopPropagation());
    sahne.appendChild(btn3B);

    // ------------------------------------------------------------
    // v2.4.33: ALT SATIR — DERECE SOLDA, BAKIS SAGDA (AYNI SATIR)
    // ------------------------------------------------------------
    // Kullanici istegi: "Pusula Widget'inda Derece solda bakis sagda
    // olsun alt alta olmasin ayni satirda olsun."
    //
    // Onceki yerlesim: kadran ortasinda buyuk derece yazisi, altta
    // yan yana iki KUTU (bakis / yatirma) — her kutunun icinde deger
    // ve etiket ALT ALTA dizilmisti. Artik tek bir satir var:
    //   [DERECE 137°]            [BAKIŞ 45°]
    // Etiket ve deger yatay; sol blok sola, sag blok saga yasli.
    //
    // "Yatirma" (roll) degeri kaldirildi: harita gorunumunde roll
    // neredeyse daima 0'dir ve kullanici iki alan istedi.
    const alt = document.createElement("div");
    alt.className = "pusula-alt";

    function altAlan(etiketMetin, hizaSinif){
      const d = document.createElement("div");
      d.className = "pusula-alan " + hizaSinif;
      const e = document.createElement("span");
      e.className = "pusula-alan-etiket";
      e.textContent = etiketMetin;
      const v = document.createElement("b");
      v.className = "pusula-alan-deger";
      v.textContent = "—";
      d.appendChild(e);
      d.appendChild(v);
      alt.appendChild(d);
      return { b: v, s: e };
    }
    const kDerece = altAlan(en ? "HDG" : "DERECE", "pusula-alan-sol");
    const kEgim   = altAlan(en ? "VIEW" : "BAKI\u015e", "pusula-alan-sag");
    govde.appendChild(alt);

    // Kuzeye don: kadrana cift tiklama
    // pointerdown yerine dblclick: tek tiklama tasima ile catisir.
    // v2.4.35: cift tik artik SAHNEYE baglanir. Onceden alt SVG'ye
    // bagliydi; 3B kipte ustteki sabit SVG olaylari yakaladigi icin
    // (ust katman alt katmani ortuyor) cift tik calismaz hale
    // gelirdi. Sahne her iki katmani kapsar.
    sahne.addEventListener("dblclick", (ev) => {
      ev.stopPropagation();
      kuzeyeDon();
    });
    sahne.style.cursor = "pointer";

    ogeler = { svg, svgUst, sahne, duzlem, btn3B, kadran, yonAd, egimIsaret,
               kDerece, kEgim, harfDugumleri };

    ipucuTazele();
    btn3BIpucuTazele();
  }

  // Kuzeye don ipucusu sahnede durur (her iki katmani kapsar).
  function ipucuTazele(){
    if (!ogeler) return;
    const en = ingilizceMi();
    ogeler.sahne.setAttribute("title", (D().wgPusulaKuzeyIpucu)
      || (en ? "Double-click: face north"
             : "\u00c7ift t\u0131k: kuzeye d\u00f6n"));
  }

  function btn3BIpucuTazele(){
    if (!ogeler || !ogeler.btn3B) return;
    const t = D();
    const en = ingilizceMi();
    const yedek = kip3B
      ? (en ? "Switch to flat (2D) view" : "D\u00fcz (2B) g\u00f6r\u00fcn\u00fcme ge\u00e7")
      : (en ? "Switch to tilted (3D) view" : "E\u011fik (3B) g\u00f6r\u00fcn\u00fcme ge\u00e7");
    ogeler.btn3B.title =
      (kip3B ? t.wgPusula2BGec : t.wgPusula3BGec) || yedek;
  }

  // ----------------------------------------------------------
  // KAMERA OKUMA
  // ----------------------------------------------------------
  function kameraAcilari(){
    try {
      const C = window.Cesium;
      if (!C || typeof viewer === "undefined" || !viewer || !viewer.camera) return null;
      const k = viewer.camera;
      let baslik = C.Math.toDegrees(k.heading);
      let egim = C.Math.toDegrees(k.pitch);
      let yat = C.Math.toDegrees(k.roll);
      // heading 0..360'a normalize
      baslik = ((baslik % 360) + 360) % 360;
      // roll, tam ters durusta 180'e yakin doner; -180..180 araligina al
      if (yat > 180) yat -= 360;
      if (yat < -180) yat += 360;
      return { baslik: baslik, egim: egim, yat: yat };
    } catch (e) { return null; }
  }

  function yonAdi(derece){
    const en = ingilizceMi();
    const adlar = en
      ? ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
      : ["K","KKD","KD","DKD","D","DGD","GD","GGD","G","GGB","GB","BGB","B","BKB","KB","KKB"];
    const i = Math.round(derece / 22.5) % 16;
    return adlar[i];
  }

  function tazele(){
    if (!ogeler) return;
    const a = kameraAcilari();
    if (!a) return;

    // Kadran, basligin TERSINE doner: kamera saga donerse dunya
    // sola kayar. Ibre sabit oldugu icin dogru okuma budur.
    ogeler.kadran.setAttribute("transform",
      "rotate(" + (-a.baslik).toFixed(2) + " " + M + " " + M + ")");

    // ----------------------------------------------------------
    // v2.4.35: 3B EGIM
    // ----------------------------------------------------------
    // Cesium pitch: -90 tepeden bakis, 0 ufka bakis.
    // Kadran egimi: tepeden bakista 0 (duz), ufka bakista EGIM_MAKS.
    // Boylece pusula haritanin gercek yonelimini taklit eder.
    if (kip3B){
      const bakisAcisi = Math.max(0, Math.min(90, -a.egim)); // 0..90
      const egim = (1 - bakisAcisi / 90) * EGIM_MAKS;        // 90->0, 0->MAKS
      const yat = Math.max(-YAT_MAKS, Math.min(YAT_MAKS, a.yat));
      ogeler.duzlem.style.transform =
        "rotateX(" + egim.toFixed(2) + "deg) rotateZ(" + yat.toFixed(2) + "deg)";
      ogeler.sahne.classList.add("pusula-3b");
    } else {
      ogeler.duzlem.style.transform = "";
      ogeler.sahne.classList.remove("pusula-3b");
    }

    // v2.4.33: derece artik alt satirin SOL alaninda
    ogeler.kDerece.b.textContent =
      Math.round(a.baslik).toString().padStart(3, "0") + "\u00b0";
    ogeler.yonAd.textContent = yonAdi(a.baslik);

    // Bakis acisi: Cesium pitch asagi bakista negatif; isaret ters
    // cevrilir (90 = tam tepeden bakis, 0 = ufka bakis)
    const bakis = Math.max(0, Math.min(90, -a.egim));
    ogeler.kEgim.b.textContent = Math.round(bakis) + "\u00b0";

    // Egim isareti: 0..90 -> y 142..58
    const y = 142 - (bakis / 90) * 84;
    ogeler.egimIsaret.setAttribute("d",
      "M 186 " + y.toFixed(1) + " l -7 -5 l 0 10 z");

    sonBaslik = a.baslik;
    sonEgim = a.egim;
  }

  // ----------------------------------------------------------
  // KUZEYE DON
  // Mevcut bakilan noktayi ve yuksekligi KORUYARAK yalnizca
  // basligi sifirlar. `flyTo` degil `camera.flyTo` + orientation
  // kullanilir; boylece konum sicramaz.
  // ----------------------------------------------------------
  function kuzeyeDon(){
    try {
      const C = window.Cesium;
      if (!C || typeof viewer === "undefined" || !viewer || !viewer.camera) return;
      const k = viewer.camera;
      k.flyTo({
        destination: k.position.clone(),
        orientation: { heading: 0, pitch: k.pitch, roll: 0 },
        duration: 0.6,
      });
    } catch (e) {}
  }

  // ----------------------------------------------------------
  // IZLEME
  // camera.changed duyarliligi dusurulur (varsayilan 0.5 cok
  // kaba); ayrica ilk kare icin dogrudan tazele cagrilir.
  // ----------------------------------------------------------
  function izleyiciKur(){
    if (izleyici) return;
    try {
      if (typeof viewer === "undefined" || !viewer || !viewer.camera) return;
      // 0.5 -> yalnizca buyuk degisimlerde tetiklenir. Pusula icin
      // kucuk donuslerin de yakalanmasi gerektiginden dusurulur.
      viewer.camera.percentageChanged = 0.001;
      const geri = () => { tazele(); };
      viewer.camera.changed.addEventListener(geri);
      izleyici = geri;

      // `changed` bazi surumlerde yalnizca hareket BITINCE
      // tetiklenir; surukleme sirasinda pusula donmus gorunur.
      // Bu nedenle sahne cizim oncesine hafif bir yedek baglanir:
      // yalnizca baslik gercekten degistiyse DOM'a yazar.
      // v2.4.35: 3B kipte YALNIZ baslik izlemek yetmez. Kullanici
      // haritayi egdiginde (orta tus / Ctrl+surukleme) baslik hic
      // degismeden pitch degisir; kadran duzlemi donmus kalirdi.
      // Bu nedenle egim degisimi de esige dahil edilir.
      const onGeri = () => {
        const a = kameraAcilari();
        if (!a) return;
        const basDegisti =
          sonBaslik === null || Math.abs(a.baslik - sonBaslik) > 0.15;
        const egimDegisti =
          sonEgim === null || Math.abs(a.egim - sonEgim) > 0.15;
        if (basDegisti || egimDegisti) tazele();
      };
      viewer.scene.preRender.addEventListener(onGeri);
      onIzleyici = onGeri;
    } catch (e) {}
  }

  function izleyiciKaldir(){
    try {
      if (izleyici && typeof viewer !== "undefined" && viewer && viewer.camera){
        viewer.camera.changed.removeEventListener(izleyici);
      }
      if (onIzleyici && typeof viewer !== "undefined" && viewer && viewer.scene){
        viewer.scene.preRender.removeEventListener(onIzleyici);
      }
    } catch (e) {}
    izleyici = null;
    onIzleyici = null;
  }

  // ----------------------------------------------------------
  // YASAM DONGUSU
  // Widget gizliyken izleyici KALDIRILIR: gizli bir widget icin
  // her karede aci okumak bosa yuktur.
  // ----------------------------------------------------------
  function ac(){
    izleyiciKur();
    tazele();
  }
  function kapa(){
    izleyiciKaldir();
  }

  function dilTazele(){
    if (!ogeler) return;
    const en = ingilizceMi();
    const yonlar = en ? ["N","E","S","W"] : ["K","D","G","B"];
    ogeler.harfDugumleri.forEach((t, i) => { t.textContent = yonlar[i]; });
    // v2.4.33: iki alan, etiketler buyuk harf
    ogeler.kDerece.s.textContent = en ? "HDG" : "DERECE";
    ogeler.kEgim.s.textContent   = en ? "VIEW" : "BAKI\u015e";
    // v2.4.35: ipucu artik sahnede (iki katmani kapsar)
    ipucuTazele();
    btn3BIpucuTazele();
    tazele();
  }

  function kaydol(){
    if (!window.Widget) return;
    window.Widget.kaydet({
      id: ID,
      baslik: "PUSULA",
      baslikAnahtar: "wgPusula",
      genislik: 226,
      yukseklik: 224,
      govdeKur: govdeKur,
      ac: ac,
      kapa: kapa,
    });
  }

  window.WidgetPusula = {
    kaydol: kaydol,
    tazele: tazele,
    kuzeyeDon: kuzeyeDon,
    dilTazele: dilTazele,
  };
})();
