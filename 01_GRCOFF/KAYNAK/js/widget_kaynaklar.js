// ============================================================
// GOKTUNGU GCS — SISTEM KAYNAKLARI WIDGET
// v2.4.34
//
// Kullanici istegi:
//   "calisan browser'in cpu, ram ve network'unu gorsel gosteren bir
//    widget koy, canli olsun ki sisteme ne kadar yuklendigimizi
//    gorelim"
//
// NE OLCULUYOR
// ------------
//   CPU  : tarayicinin cizim isini yetistirme orani (FPS'ten turetilir)
//   RAM  : JS yigin kullanimi (yalniz Chromium/Edge)
//   AG   : WebSocket + MJPEG akislarinin bayt hizi
//   SUNUCU: GCS surecinin ve makinenin gercek CPU/RAM'i (WS ile gelir)
//
// TASARIM KARARLARI
// -----------------
// 1) TARAYICI "CPU"SU DOGRUDAN OLCULEMEZ. Web platformunda surece ait
//    CPU yuzdesi veren bir API YOKTUR. Bunun yerine ANA IS PARCACIGI
//    DOLULUGU olculur: rAF cerceveleri arasinda gecen sure hedef
//    cerceve suresinden (16.7 ms) ne kadar sapiyorsa, ana is parcacigi
//    o oranda mesguldur. Bu, "arayuz sistemi ne kadar zorluyor"
//    sorusunun tarayicida olculebilen en yakin karsiligidir ve
//    KULLANICININ AMACI tam olarak budur.
//
//    Etiket bu nedenle "CPU" degil "YUK" olarak yazilir; olcumun ne
//    oldugu ipucu metninde acikca belirtilir. Isletim sistemi CPU'su
//    ayrica SUNUCU satirinda gosterilir.
//
// 2) performance.memory YALNIZ CHROMIUM'DA VAR. Firefox/Safari'de
//    tanimsizdir. Yok ise RAM satiri "yok" yazar ve sparkline cizilmez;
//    sifir gostermek yanlis bilgi olur.
//
// 3) AG OLCUMU: WS icin `ws.onmessage` bayt sayaci gerektirir; ancak
//    ws.js'e dokunmadan olcmek icin `PerformanceObserver`/
//    `performance.getEntriesByType("resource")` kullanilir — MJPEG
//    akislari `transferSize` ile buradan gorulur. WS cercevelerini
//    Resource Timing gostermedigi icin WS baytlari `ws.js`'teki
//    global sayactan alinir (varsa); yoksa yalniz MJPEG sayilir ve
//    etiket bunu belirtir.
//
// 4) ORNEKLEME 1 Hz. Sparkline 60 ornek tutar (1 dakika gecmis).
//    Daha sik ornekleme, izleme aracinin kendisini yuk kaynagi yapar.
//
// 5) WIDGET KAPALIYKEN SIFIR MALIYET: `kapa()` hem rAF dongusunu hem
//    sunucu isteklerini durdurur. Bir izleme araci, izlemedigi zaman
//    kaynak tuketmemelidir.
//
// 6) SUNUCU OLCUMU ISTEGE BAGLI. `psutil` yoksa sunucu satiri
//    "olculemiyor" yazar; widget tarayici olcumleriyle calismaya devam
//    eder.
// ============================================================

(function(){
  "use strict";

  const ID = "kaynaklar";
  const ORNEK = 60;              // sparkline gecmis uzunlugu (1 dk)
  const SUNUCU_ARALIK_MS = 1000; // sunucu olcum istegi periyodu

  let ogeler = null;
  let cerceve = null;            // requestAnimationFrame kimligi
  let sunucuZamanlayici = null;
  let acikMi = false;

  // --- FPS / yuk olcum durumu ---
  let sonKare = 0;
  let kareSayisi = 0;
  let kareSuresiToplam = 0;
  let enUzunKare = 0;
  let sonOrnekT = 0;

  // --- Ag olcum durumu ---
  let sonAgBayt = 0;
  let sonAgT = 0;

  // --- Gecmis diziler (sparkline) ---
  const gecmis = {
    yuk: [], ram: [], ag: [], sunucuCpu: [], sunucuRam: [],
  };

  let sunucuSon = null;          // en son sunucu olcum paketi
  let sunucuHazir = null;        // null: bilinmiyor, false: olculemiyor

  function T(){ return (typeof D === "function") ? D() : {}; }

  function ingilizceMi(){
    try {
      if (typeof aktifDil !== "undefined")
        return String(aktifDil).toLowerCase().startsWith("en");
      const d = localStorage.getItem("gcs_dil");
      return !!(d && d.toLowerCase().startsWith("en"));
    } catch (e) { return false; }
  }

  function itele(dizi, deger){
    dizi.push(deger);
    while (dizi.length > ORNEK) dizi.shift();
  }

  // ----------------------------------------------------------
  // SPARKLINE
  // Canvas cizimi: dizinin son ORNEK degeri soldan saga cizilir.
  // `enUst` sabit oldugunda (yuzde olcumleri) olcek karsilastirilabilir
  // kalir; ag hizi gibi sinirsiz degerlerde dizinin kendi tavani
  // kullanilir ve tavan etikette yazilir.
  // ----------------------------------------------------------
  function sparkCiz(cv, dizi, renk, enUstSabit){
    if (!cv) return;
    const dpr = window.devicePixelRatio || 1;
    const g = cv.getBoundingClientRect();
    const w = Math.max(1, Math.round(g.width));
    const h = Math.max(1, Math.round(g.height));
    if (cv.width !== w * dpr || cv.height !== h * dpr){
      cv.width = w * dpr; cv.height = h * dpr;
    }
    const c = cv.getContext("2d");
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.clearRect(0, 0, w, h);

    // Zemin izgarasi (orta cizgi)
    c.strokeStyle = "rgba(255,255,255,0.08)";
    c.lineWidth = 1;
    c.beginPath();
    c.moveTo(0, Math.round(h / 2) + 0.5);
    c.lineTo(w, Math.round(h / 2) + 0.5);
    c.stroke();

    const gecerli = dizi.filter(v => typeof v === "number" && isFinite(v));
    if (gecerli.length < 2) return;

    let enUst = enUstSabit;
    if (!enUst){
      enUst = Math.max.apply(null, gecerli);
      if (!isFinite(enUst) || enUst <= 0) enUst = 1;
      enUst *= 1.15;             // tepe cizgiye yapismasin
    }

    // Dolgu + cizgi
    const adim = w / Math.max(1, ORNEK - 1);
    // Diziyi SAGA yasla: yeni ornekler sagda birikir, sol taraf
    // gecmis dolana kadar bos kalir (yaniltici duz cizgi cizilmez).
    const kaydir = (ORNEK - dizi.length) * adim;

    function y(v){
      const o = Math.max(0, Math.min(1, v / enUst));
      return h - 1 - o * (h - 2);
    }

    c.beginPath();
    let ilk = true;
    for (let i = 0; i < dizi.length; i++){
      const v = dizi[i];
      if (typeof v !== "number" || !isFinite(v)) continue;
      const x = kaydir + i * adim;
      if (ilk){ c.moveTo(x, y(v)); ilk = false; }
      else c.lineTo(x, y(v));
    }
    c.strokeStyle = renk;
    c.lineWidth = 1.6;
    c.lineJoin = "round";
    c.stroke();

    // Alan dolgusu
    c.lineTo(kaydir + (dizi.length - 1) * adim, h);
    c.lineTo(kaydir, h);
    c.closePath();
    const grad = c.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, renk.replace("rgb", "rgba").replace(")", ",0.28)"));
    grad.addColorStop(1, renk.replace("rgb", "rgba").replace(")", ",0.02)"));
    c.fillStyle = grad;
    c.fill();
  }

  // ----------------------------------------------------------
  // OLCUM: TARAYICI
  // ----------------------------------------------------------
  function agBaytOku(){
    // MJPEG ve diger kaynaklarin toplam transfer bayti.
    // `transferSize` yalniz ayni-kaynak veya Timing-Allow-Origin
    // veren yanitlarda doludur; kendi vekilimiz ayni kaynak oldugu
    // icin MJPEG akislari sayilir.
    let toplam = 0;
    try {
      const kayitlar = performance.getEntriesByType("resource");
      for (let i = 0; i < kayitlar.length; i++){
        const r = kayitlar[i];
        if (typeof r.transferSize === "number") toplam += r.transferSize;
      }
    } catch (e) {}
    // ws.js bayt sayaci tutuyorsa ekle (v2.4.34'te eklendi)
    try {
      if (typeof window.wsBaytSayaci === "number") toplam += window.wsBaytSayaci;
    } catch (e) {}
    return toplam;
  }

  function ornekAl(){
    const simdi = performance.now();

    // --- Yuk (ana is parcacigi dolulugu) ---
    // Ortalama cerceve suresi hedeften (16.7 ms) ne kadar uzunsa
    // ana is parcacigi o oranda mesguldur.
    let yuk = null, fps = null;
    if (kareSayisi > 0){
      const ortalama = kareSuresiToplam / kareSayisi;
      fps = 1000 / ortalama;
      // 16.7 ms -> %0 ek yuk; 33.3 ms (30 FPS) -> %50; 100 ms -> %83
      yuk = Math.max(0, Math.min(100, (1 - (16.7 / ortalama)) * 100));
    }

    // --- RAM (yalniz Chromium) ---
    let ram = null, ramSinir = null;
    try {
      if (performance.memory && performance.memory.usedJSHeapSize){
        ram = performance.memory.usedJSHeapSize / (1024 * 1024);
        ramSinir = performance.memory.jsHeapSizeLimit / (1024 * 1024);
      }
    } catch (e) {}

    // --- Ag (KB/s) ---
    let ag = null;
    const bayt = agBaytOku();
    if (sonAgT){
      const dt = (simdi - sonAgT) / 1000;
      if (dt > 0) ag = Math.max(0, (bayt - sonAgBayt) / dt / 1024);
    }
    sonAgBayt = bayt;
    sonAgT = simdi;

    if (yuk !== null) itele(gecmis.yuk, yuk);
    if (ram !== null) itele(gecmis.ram, ram);
    if (ag !== null) itele(gecmis.ag, ag);

    yaz({ yuk, fps, ram, ramSinir, ag, enUzunKare });

    kareSayisi = 0; kareSuresiToplam = 0; enUzunKare = 0;
  }

  // ----------------------------------------------------------
  // CIZIM DONGUSU
  // rAF her karede cagrilir; ORNEKLEME 1 Hz'dir. Boylece olcum
  // dogru (her kare sayilir) ama DOM yazma seyrek olur.
  // ----------------------------------------------------------
  function dongu(){
    const simdi = performance.now();
    if (sonKare){
      const dt = simdi - sonKare;
      kareSuresiToplam += dt;
      kareSayisi++;
      if (dt > enUzunKare) enUzunKare = dt;
    }
    sonKare = simdi;

    if (!sonOrnekT) sonOrnekT = simdi;
    if (simdi - sonOrnekT >= 1000){
      sonOrnekT = simdi;
      ornekAl();
    }
    cerceve = acikMi ? requestAnimationFrame(dongu) : null;
  }

  function donguBaslat(){
    if (cerceve !== null) return;
    sonKare = 0; kareSayisi = 0; kareSuresiToplam = 0;
    enUzunKare = 0; sonOrnekT = 0;
    cerceve = requestAnimationFrame(dongu);
  }

  function donguDurdur(){
    if (cerceve !== null){ cancelAnimationFrame(cerceve); cerceve = null; }
  }

  // ----------------------------------------------------------
  // SUNUCU OLCUMU
  // ----------------------------------------------------------
  function sunucuIste(){
    try {
      if (typeof ws !== "undefined" && ws && ws.readyState === 1){
        ws.send(JSON.stringify({ tip: "kaynak_olcum" }));
      }
    } catch (e) {}
  }

  window.kaynakOlcumGeldi = function(m){
    if (!m) return;
    sunucuHazir = !!m.hazir;
    sunucuSon = m;
    if (m.hazir){
      if (typeof m.sistem_cpu === "number") itele(gecmis.sunucuCpu, m.sistem_cpu);
      if (typeof m.sistem_ram === "number") itele(gecmis.sunucuRam, m.sistem_ram);
    }
    sunucuYaz();
  };

  function sunucuBaslat(){
    if (sunucuZamanlayici !== null) return;
    sunucuIste();
    sunucuZamanlayici = setInterval(sunucuIste, SUNUCU_ARALIK_MS);
  }

  function sunucuDurdur(){
    if (sunucuZamanlayici !== null){
      clearInterval(sunucuZamanlayici);
      sunucuZamanlayici = null;
    }
  }

  // ----------------------------------------------------------
  // GOVDE
  // ----------------------------------------------------------
  function satirKur(kap, sinif, etiketMetni){
    const s = document.createElement("div");
    s.className = "kyn-satir " + sinif;

    const ust = document.createElement("div");
    ust.className = "kyn-ust";
    const et = document.createElement("span");
    et.className = "kyn-etiket";
    et.textContent = etiketMetni;
    const dg = document.createElement("span");
    dg.className = "kyn-deger";
    dg.textContent = "—";
    ust.appendChild(et);
    ust.appendChild(dg);
    s.appendChild(ust);

    const cv = document.createElement("canvas");
    cv.className = "kyn-spark";
    s.appendChild(cv);

    kap.appendChild(s);
    return { kok: s, etiket: et, deger: dg, spark: cv };
  }

  function govdeKur(govde, api){
    govde.classList.add("kyn-govde");
    const t = T();
    const en = ingilizceMi();

    const sarmal = document.createElement("div");
    sarmal.className = "kyn-sarmal";

    const yuk = satirKur(sarmal, "kyn-yuk",
      t.kynYuk || (en ? "LOAD" : "Y\u00dcK"));
    const ram = satirKur(sarmal, "kyn-ram",
      t.kynRam || (en ? "JS HEAP" : "JS BELLEK"));
    const ag = satirKur(sarmal, "kyn-ag",
      t.kynAg || (en ? "NETWORK" : "A\u011e"));

    // --- Sunucu bolumu ---
    const ayrac = document.createElement("div");
    ayrac.className = "kyn-ayrac";
    ayrac.textContent = t.kynSunucu || (en ? "SERVER" : "SUNUCU");
    sarmal.appendChild(ayrac);

    const scpu = satirKur(sarmal, "kyn-scpu",
      t.kynSunucuCpu || (en ? "CPU" : "CPU"));
    const sram = satirKur(sarmal, "kyn-sram",
      t.kynSunucuRam || (en ? "RAM" : "RAM"));

    const dipnot = document.createElement("div");
    dipnot.className = "kyn-dipnot";
    sarmal.appendChild(dipnot);

    govde.appendChild(sarmal);

    ogeler = { yuk, ram, ag, scpu, sram, ayrac, dipnot };
    ipucuYaz();
  }

  // Etiketlerin ne olculdugunu anlatan ipucu: "CPU" sanilan degerin
  // aslinda ana is parcacigi dolulugu oldugu burada belirtilir.
  function ipucuYaz(){
    if (!ogeler) return;
    const t = T(), en = ingilizceMi();
    ogeler.yuk.kok.title = t.kynYukIpucu ||
      (en ? "Main-thread busyness derived from frame timing (not OS CPU)"
          : "Cizim cercevelerinden turetilen ana is parcacigi dolulugu "
            + "(isletim sistemi CPU'su degil)");
    ogeler.ram.kok.title = t.kynRamIpucu ||
      (en ? "JS heap usage; only available in Chromium-based browsers"
          : "JS yigin kullanimi; yalniz Chromium tabanli tarayicilarda "
            + "olculebilir");
    ogeler.ag.kok.title = t.kynAgIpucu ||
      (en ? "Transfer rate of page resources incl. MJPEG streams"
          : "MJPEG akislari dahil sayfa kaynaklarinin transfer hizi");
    ogeler.scpu.kok.title = t.kynSunucuIpucu ||
      (en ? "Real OS measurement from the GCS server"
          : "GCS sunucusundan gelen gercek isletim sistemi olcumu");
    ogeler.sram.kok.title = ogeler.scpu.kok.title;
  }

  // ----------------------------------------------------------
  // YAZMA
  // ----------------------------------------------------------
  function yaz(o){
    if (!ogeler) return;
    const en = ingilizceMi(), t = T();

    // --- Yuk ---
    if (o.yuk === null){
      ogeler.yuk.deger.textContent = "—";
    } else {
      const fps = o.fps ? Math.round(o.fps) : 0;
      ogeler.yuk.deger.textContent = Math.round(o.yuk) + "% \u00b7 " + fps + " FPS";
      ogeler.yuk.deger.classList.toggle("kyn-uyari", o.yuk >= 60);
      ogeler.yuk.deger.classList.toggle("kyn-kritik", o.yuk >= 85);
    }
    sparkCiz(ogeler.yuk.spark, gecmis.yuk, "rgb(90,200,255)", 100);

    // --- RAM ---
    if (o.ram === null){
      ogeler.ram.deger.textContent = en ? "not available" : "olc\u00fclemiyor";
      ogeler.ram.deger.classList.add("kyn-yok");
    } else {
      ogeler.ram.deger.classList.remove("kyn-yok");
      ogeler.ram.deger.textContent = o.ram.toFixed(0) + " MB"
        + (o.ramSinir ? " / " + Math.round(o.ramSinir) : "");
      sparkCiz(ogeler.ram.spark, gecmis.ram, "rgb(160,140,255)",
               o.ramSinir || null);
    }

    // --- Ag ---
    if (o.ag === null){
      ogeler.ag.deger.textContent = "—";
    } else {
      ogeler.ag.deger.textContent = (o.ag >= 1024)
        ? (o.ag / 1024).toFixed(1) + " MB/s"
        : o.ag.toFixed(0) + " KB/s";
    }
    sparkCiz(ogeler.ag.spark, gecmis.ag, "rgb(120,230,170)", null);

    // Takilma uyarisi: tek bir kare 200 ms'yi astiysa operator bunu
    // gorsel takilma olarak hisseder.
    if (o.enUzunKare >= 200){
      ogeler.dipnot.textContent = (t.kynTakilma
        ? t.kynTakilma(Math.round(o.enUzunKare))
        : (en ? ("longest frame " + Math.round(o.enUzunKare) + " ms")
              : ("en uzun kare " + Math.round(o.enUzunKare) + " ms")));
      ogeler.dipnot.classList.add("kyn-dipnot-uyari");
    } else {
      ogeler.dipnot.textContent = "";
      ogeler.dipnot.classList.remove("kyn-dipnot-uyari");
    }
  }

  function sunucuYaz(){
    if (!ogeler) return;
    const en = ingilizceMi(), t = T();
    const m = sunucuSon;

    if (sunucuHazir === false){
      const yok = t.kynSunucuYok ||
        (en ? "psutil not installed" : "psutil kurulu de\u011fil");
      ogeler.scpu.deger.textContent = yok;
      ogeler.scpu.deger.classList.add("kyn-yok");
      ogeler.sram.deger.textContent = "—";
      ogeler.sram.deger.classList.add("kyn-yok");
      return;
    }
    if (!m) return;

    ogeler.scpu.deger.classList.remove("kyn-yok");
    ogeler.sram.deger.classList.remove("kyn-yok");

    // Ilk olcumde CPU degeri None gelir (delta yok) — "—" yazilir,
    // sifir yazmak yanlis bilgi olur.
    if (typeof m.sistem_cpu === "number"){
      let metin = Math.round(m.sistem_cpu) + "%";
      if (typeof m.surec_cpu === "number")
        metin += " \u00b7 GCS " + m.surec_cpu.toFixed(1) + "%";
      ogeler.scpu.deger.textContent = metin;
      ogeler.scpu.deger.classList.toggle("kyn-uyari", m.sistem_cpu >= 70);
      ogeler.scpu.deger.classList.toggle("kyn-kritik", m.sistem_cpu >= 90);
    } else {
      ogeler.scpu.deger.textContent = "—";
    }
    sparkCiz(ogeler.scpu.spark, gecmis.sunucuCpu, "rgb(255,180,90)", 100);

    if (typeof m.sistem_ram === "number"){
      let metin = Math.round(m.sistem_ram) + "%";
      if (typeof m.surec_ram === "number")
        metin += " \u00b7 GCS " + Math.round(m.surec_ram) + " MB";
      ogeler.sram.deger.textContent = metin;
      ogeler.sram.deger.classList.toggle("kyn-uyari", m.sistem_ram >= 80);
      ogeler.sram.deger.classList.toggle("kyn-kritik", m.sistem_ram >= 92);
    } else {
      ogeler.sram.deger.textContent = "—";
    }
    sparkCiz(ogeler.sram.spark, gecmis.sunucuRam, "rgb(255,120,140)", 100);
  }

  // ----------------------------------------------------------
  // YASAM DONGUSU
  // ----------------------------------------------------------
  function ac(){
    acikMi = true;
    donguBaslat();
    sunucuBaslat();
  }

  function kapa(){
    acikMi = false;
    donguDurdur();
    sunucuDurdur();
  }

  function dilTazele(){
    if (!ogeler) return;
    const t = T(), en = ingilizceMi();
    ogeler.yuk.etiket.textContent = t.kynYuk || (en ? "LOAD" : "Y\u00dcK");
    ogeler.ram.etiket.textContent = t.kynRam || (en ? "JS HEAP" : "JS BELLEK");
    ogeler.ag.etiket.textContent = t.kynAg || (en ? "NETWORK" : "A\u011e");
    ogeler.ayrac.textContent = t.kynSunucu || (en ? "SERVER" : "SUNUCU");
    ogeler.scpu.etiket.textContent = t.kynSunucuCpu || "CPU";
    ogeler.sram.etiket.textContent = t.kynSunucuRam || "RAM";
    ipucuYaz();
    sunucuYaz();
  }

  // ----------------------------------------------------------
  // KAYIT
  // Yukseklik: 5 satir x (etiket + sparkline) + ayrac + dipnot.
  // Genislik diger widget'larla ayni (226).
  // ----------------------------------------------------------
  function kaydol(){
    if (!window.Widget) return;
    window.Widget.kaydet({
      id: ID,
      baslik: (typeof D === "function" && D().wgKaynaklar)
              || "KAYNAKLAR",
      baslikAnahtar: "wgKaynaklar",
      genislik: 226,
      yukseklik: 268,
      govdeKur: govdeKur,
      ac: ac,
      kapa: kapa,
      dilTazele: dilTazele,
    });
  }

  window.WidgetKaynaklar = { kaydol: kaydol, ID: ID };
})();
