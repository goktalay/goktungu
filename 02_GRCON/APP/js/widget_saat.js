// ============================================================
// GOKTUNGU GCS — SAAT WIDGET
// v2.4.29
//
// Guncel saati gosterir; DIJITAL ve ANALOG kipler arasinda gecilir.
// Kip secimi widget altyapisinin `ayarYaz`/`ayarOku` API'si ile
// kalici olarak saklanir.
//
// ZAMANLAYICI DISIPLINI
// ---------------------
// Zamanlayici YALNIZCA widget gorunurken calisir; `kapa` geri
// cagrisinda durdurulur. Boylece kapali widget islemci harcamaz.
//
// Analog kipte ibreler SVG `transform` ile dondurulur. Saniye ibresi
// icin CSS gecisi KULLANILMAZ: 59 -> 0 gecisinde ibre geri saracagi
// icin gorsel bozulma olusur.
// ============================================================

(function(){
  "use strict";

  const ID = "saat";
  let zamanlayici = null;
  let ogeler = null;      // { kip, dijital:{...}, analog:{...} }

  const GUN_TR = ["Pazar","Pazartesi","Salı","Çarşamba","Perşembe","Cuma","Cumartesi"];
  const AY_TR = ["Ocak","Şubat","Mart","Nisan","Mayıs","Haziran",
                 "Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"];
  const GUN_EN = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];
  const AY_EN = ["January","February","March","April","May","June",
                 "July","August","September","October","November","December"];

  function ingilizceMi(){
    try {
      if (typeof aktifDil !== "undefined") return String(aktifDil).toLowerCase().startsWith("en");
      const d = localStorage.getItem("gcs_dil");
      return !!(d && d.toLowerCase().startsWith("en"));
    } catch (e) { return false; }
  }

  function ikiHane(n){ return (n < 10 ? "0" : "") + n; }

  // ----------------------------------------------------------
  // ANALOG KADRAN (SVG)
  // ----------------------------------------------------------
  const SVG_NS = "http://www.w3.org/2000/svg";
  function svgOge(ad, ozellikler){
    const e = document.createElementNS(SVG_NS, ad);
    for (const k in ozellikler) e.setAttribute(k, ozellikler[k]);
    return e;
  }

  // v2.4.31: kadran 116 -> 176 px. Widget hava durumu ile esitlendigi
  // (226x224) icin eski 116 px kadran ortada kucuk kaliyor ve cevresinde
  // genis bos alan olusuyordu. viewBox degismedi; yalnizca cizim olcegi
  // buyudu, boylece tum ic koordinatlar gecerliligini korur.
  const KADRAN_PX = 176;

  function analogKur(){
    const R = 52;                 // kadran yaricapi (viewBox birimi)
    const svg = svgOge("svg", {
      class: "saat-analog", viewBox: "0 0 120 120",
      width: String(KADRAN_PX), height: String(KADRAN_PX),
    });

    // Kadran zemini
    // v2.4.31: renkler CSS sinifi uzerinden temadan gelir; SVG'de sabit
    // renk YAZILMAZ (koyu temada okunamiyordu).
    svg.appendChild(svgOge("circle", {
      class: "saat-kadran-zemin",
      cx: 60, cy: 60, r: R, "stroke-width": 2,
    }));
    // Ic halka
    svg.appendChild(svgOge("circle", {
      class: "saat-kadran-ic",
      cx: 60, cy: 60, r: R - 5, fill: "none", "stroke-width": 1,
    }));

    // Dakika ve saat cizgileri
    for (let i = 0; i < 60; i++){
      const buyuk = (i % 5 === 0);
      const a = (i / 60) * Math.PI * 2 - Math.PI / 2;
      const r1 = buyuk ? R - 11 : R - 6;
      const r2 = R - 3;
      svg.appendChild(svgOge("line", {
        class: buyuk ? "saat-cizgi-buyuk" : "saat-cizgi-kucuk",
        x1: (60 + Math.cos(a) * r1).toFixed(2),
        y1: (60 + Math.sin(a) * r1).toFixed(2),
        x2: (60 + Math.cos(a) * r2).toFixed(2),
        y2: (60 + Math.sin(a) * r2).toFixed(2),
        "stroke-width": buyuk ? 2.1 : 1,
        "stroke-linecap": "round",
      }));
    }

    // 12/3/6/9 sayilari
    [[12, 0], [3, 90], [6, 180], [9, 270]].forEach(([s, der]) => {
      const a = (der / 180) * Math.PI - Math.PI / 2;
      const rr = R - 18;
      const t = svgOge("text", {
        class: "saat-sayi",
        x: (60 + Math.cos(a) * rr).toFixed(2),
        y: (60 + Math.sin(a) * rr + 3.6).toFixed(2),
        "text-anchor": "middle",
        "font-size": "10.5", "font-weight": "700",
        "font-family": "inherit",
      });
      t.textContent = String(s);
      svg.appendChild(t);
    });

    // Ibreler (transform ile dondurulur)
    const saatIbre = svgOge("line", {
      class: "saat-ibre-saat",
      x1: 60, y1: 64, x2: 60, y2: 34,
      "stroke-width": 4.2, "stroke-linecap": "round",
    });
    const dakIbre = svgOge("line", {
      class: "saat-ibre-dak",
      x1: 60, y1: 66, x2: 60, y2: 22,
      "stroke-width": 2.9, "stroke-linecap": "round",
    });
    const sanIbre = svgOge("line", {
      class: "saat-ibre-san",
      x1: 60, y1: 70, x2: 60, y2: 18,
      "stroke-width": 1.35, "stroke-linecap": "round",
    });
    svg.appendChild(saatIbre);
    svg.appendChild(dakIbre);
    svg.appendChild(sanIbre);

    // Merkez gobek
    svg.appendChild(svgOge("circle", { class: "saat-gobek", cx: 60, cy: 60, r: 3.1 }));
    svg.appendChild(svgOge("circle", { class: "saat-gobek-ic", cx: 60, cy: 60, r: 1.25 }));

    return { svg, saatIbre, dakIbre, sanIbre };
  }

  // ----------------------------------------------------------
  // GOVDE
  // ----------------------------------------------------------
  function govdeKur(govde, api){
    const sarmal = document.createElement("div");
    sarmal.className = "saat-sarmal";

    // Dijital
    const dij = document.createElement("div");
    dij.className = "saat-dijital";
    const zaman = document.createElement("div");
    zaman.className = "saat-dij-zaman";
    zaman.innerHTML = '<span class="saat-dij-ss">--:--</span><span class="saat-dij-saniye">:--</span>';
    const tarih = document.createElement("div");
    tarih.className = "saat-dij-tarih";
    tarih.textContent = "";
    dij.appendChild(zaman);
    dij.appendChild(tarih);

    // Analog
    const ana = analogKur();

    sarmal.appendChild(dij);
    sarmal.appendChild(ana.svg);

    // Kip degistirme dugmesi
    const kipBtn = document.createElement("button");
    kipBtn.className = "saat-kip-btn";
    kipBtn.type = "button";
    govde.appendChild(sarmal);
    govde.appendChild(kipBtn);

    ogeler = {
      kip: api.ayarOku("kip", "dijital"),
      dij: dij,
      dijSS: zaman.querySelector(".saat-dij-ss"),
      dijSaniye: zaman.querySelector(".saat-dij-saniye"),
      dijTarih: tarih,
      ana: ana,
      kipBtn: kipBtn,
    };

    function kipUygula(){
      const analogMu = (ogeler.kip === "analog");
      ogeler.dij.style.display = analogMu ? "none" : "";
      ogeler.ana.svg.style.display = analogMu ? "" : "none";
      kipBtn.innerHTML = analogMu
        ? '<i class="fa-solid fa-stopwatch-20"></i>'
        : '<i class="fa-regular fa-clock"></i>';
      kipBtn.title = analogMu
        ? (((typeof D === "function") ? (D().wgSaatDijitalGec) : "") || "Dijital saate ge\u00e7")
        : (((typeof D === "function") ? (D().wgSaatAnalogGec) : "") || "Analog saate ge\u00e7");
      tazele();
    }

    kipBtn.addEventListener("click", (ev) => {
      ev.stopPropagation();
      ogeler.kip = (ogeler.kip === "analog") ? "dijital" : "analog";
      api.ayarYaz("kip", ogeler.kip);
      kipUygula();
    });

    kipUygula();
  }

  // ----------------------------------------------------------
  // TAZELEME
  // ----------------------------------------------------------
  function tazele(){
    if (!ogeler) return;
    const d = new Date();
    if (ogeler.kip === "analog"){
      const sn = d.getSeconds();
      const dk = d.getMinutes();
      const st = d.getHours() % 12;
      // Saat ve dakika ibreleri kesirli ilerler (gercekci hareket)
      const sanDer = sn * 6;
      const dakDer = dk * 6 + sn * 0.1;
      const satDer = st * 30 + dk * 0.5;
      ogeler.ana.sanIbre.setAttribute("transform", "rotate(" + sanDer + " 60 60)");
      ogeler.ana.dakIbre.setAttribute("transform", "rotate(" + dakDer.toFixed(2) + " 60 60)");
      ogeler.ana.saatIbre.setAttribute("transform", "rotate(" + satDer.toFixed(2) + " 60 60)");
    } else {
      ogeler.dijSS.textContent = ikiHane(d.getHours()) + ":" + ikiHane(d.getMinutes());
      ogeler.dijSaniye.textContent = ":" + ikiHane(d.getSeconds());
      const en = ingilizceMi();
      const gun = en ? GUN_EN[d.getDay()] : GUN_TR[d.getDay()];
      const ay = en ? AY_EN[d.getMonth()] : AY_TR[d.getMonth()];
      ogeler.dijTarih.textContent = en
        ? (gun + ", " + ay + " " + d.getDate())
        : (d.getDate() + " " + ay + " " + gun);
    }
  }

  function baslatZamanlayici(){
    if (zamanlayici) return;
    tazele();
    zamanlayici = setInterval(tazele, 1000);
  }
  function durdurZamanlayici(){
    if (zamanlayici){ clearInterval(zamanlayici); zamanlayici = null; }
  }

  // ----------------------------------------------------------
  // KAYIT
  // ----------------------------------------------------------
  function kaydol(){
    if (!window.Widget) return;
    window.Widget.kaydet({
      id: ID,
      baslik: "SAAT",
      baslikAnahtar: "wgSaat",
      // v2.4.31: kullanici istegi — saat boyutu HAVA DURUMU ile ayni.
      // Hava durumu widget'i 226x224 (widget_hava.js) oldugu icin bu iki
      // deger oradan alinmistir; degistirilecekse ikisi birlikte
      // degistirilmelidir.
      genislik: 226,
      yukseklik: 224,
      govdeKur: govdeKur,
      ac: baslatZamanlayici,
      kapa: durdurZamanlayici,
    });
  }

  window.WidgetSaat = { kaydol: kaydol, tazele: tazele, ID: ID };
})();
