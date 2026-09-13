// =================================================================
// GOKTUNGU - PFD (Primary Flight Display) cizim motoru   v2.4.32
//
// Boeing tarzi birincil ucus gostergesi. Tek canvas uzerine cizer:
//   - orta: yapay ufuk (gok/yer), yatis olcegi, ucak sembolu
//   - sol : kayan hiz seridi
//   - sag : kayan irtifa seridi + dikey hiz cubugu
//   - alt : donen pusula gulu
//   - ust : ucus kipi satiri
//
// NEDEN CANVAS, SVG DEGIL:
//   Alti panel es zamanli animasyon yapiyor. Kayan seritlerde SVG
//   kullanilirsa her karede onlarca dugum yeniden olusur/tasinir ve
//   tarayici her biri icin yeniden duzen (reflow) hesaplar. Canvas'ta
//   ise tum panel tek cizim gecisidir. Ikinci ekranda 6 panel surekli
//   aktif oldugu icin bu fark belirleyicidir.
//
// OLCEKLEME:
//   Cizimler 1000x1000 mantiksal birim uzerinde tanimlidir; gercek
//   canvas boyutuna setTransform ile olceklenir. Boylece panel boyu
//   degisince oranlar bozulmaz ve devicePixelRatio ile keskin kalir.
// =================================================================
(function(){
  "use strict";

  // Mantiksal tuval (tum koordinatlar bu sistemde)
  const T = 1000;

  // Renk paleti (Boeing PFD gelenegi)
  const R = {
    gok:      "#1f6ec9",
    gokUst:   "#1558a6",
    yer:      "#8a5a25",
    yerAlt:   "#6d451a",
    ufuk:     "#ffffff",
    serit:    "rgba(12,16,22,0.78)",
    seritKen: "rgba(255,255,255,0.32)",
    metin:    "#ffffff",
    yesil:    "#25e07a",
    mor:      "#ff4fd8",
    sari:     "#ffd23f",
    kirmizi:  "#ff4d4d",
    camgobek: "#39d7ff",
    ucak:     "#111111",
    ucakKen:  "#ffd23f"
  };

  function sayi(v, y){
    const n = Number(v);
    return Number.isFinite(n) ? n : (y === undefined ? 0 : y);
  }

  // -----------------------------------------------------------------
  // Yapay ufuk
  // -----------------------------------------------------------------
  // Yatis (roll) ve kafa acisi (pitch) ufuk duzlemini dondurur/kaydirir.
  // Pitch olcegi: 1 derece = PITCH_BIRIM mantiksal birim.
  const PITCH_BIRIM = 7.2;

  function ufukCiz(c, roll, pitch, mx, my, mw, mh){
    c.save();
    // Kirpma: ufuk yalnizca orta pencerede gorunur
    c.beginPath();
    c.rect(mx, my, mw, mh);
    c.clip();

    const cx = mx + mw / 2;
    const cy = my + mh / 2;

    c.translate(cx, cy);
    c.rotate(-roll * Math.PI / 180);
    // pitch pozitifse (kafa yukari) ufuk asagi kayar
    c.translate(0, pitch * PITCH_BIRIM);

    // Ufuk duzlemini pencereden tasacak kadar buyuk ciz; dondurulunce
    // kose bosluklari olusmasin
    const B = Math.max(mw, mh) * 1.9;

    // Gok
    const gg = c.createLinearGradient(0, -B, 0, 0);
    gg.addColorStop(0, R.gokUst);
    gg.addColorStop(1, R.gok);
    c.fillStyle = gg;
    c.fillRect(-B, -B, B * 2, B);

    // Yer
    const yg = c.createLinearGradient(0, 0, 0, B);
    yg.addColorStop(0, R.yer);
    yg.addColorStop(1, R.yerAlt);
    c.fillStyle = yg;
    c.fillRect(-B, 0, B * 2, B);

    // Ufuk cizgisi
    c.strokeStyle = R.ufuk;
    c.lineWidth = 3.0;
    c.beginPath();
    c.moveTo(-B, 0);
    c.lineTo(B, 0);
    c.stroke();

    // Pitch merdiveni: 10 derecede uzun + rakam, 5 derecede kisa
    c.lineWidth = 2.4;
    c.font = "600 26px system-ui, sans-serif";
    c.textBaseline = "middle";
    for (let d = -90; d <= 90; d += 5){
      if (d === 0) continue;
      const y = -d * PITCH_BIRIM;
      if (Math.abs(y) > mh) continue;
      const uzun = (d % 10 === 0);
      const w = uzun ? 92 : 46;
      c.beginPath();
      c.moveTo(-w, y);
      c.lineTo(w, y);
      c.stroke();
      if (uzun){
        const et = String(Math.abs(d));
        c.textAlign = "right";
        c.fillStyle = R.metin;
        c.fillText(et, -w - 12, y);
        c.textAlign = "left";
        c.fillText(et, w + 12, y);
      }
    }
    c.restore();
  }

  // Yatis olcegi (sabit yay + hareketli isaretci)
  function yatisOlcegiCiz(c, roll, cx, cy, rad){
    c.save();
    c.strokeStyle = R.metin;
    c.fillStyle = R.metin;
    c.lineWidth = 2.6;

    // Sabit derece cizgileri
    const acilar = [-60, -45, -30, -20, -10, 0, 10, 20, 30, 45, 60];
    acilar.forEach(a => {
      const r1 = rad;
      const r2 = rad - ((a % 30 === 0) ? 26 : 15);
      const t = (a - 90) * Math.PI / 180;
      c.beginPath();
      c.moveTo(cx + Math.cos(t) * r1, cy + Math.sin(t) * r1);
      c.lineTo(cx + Math.cos(t) * r2, cy + Math.sin(t) * r2);
      c.stroke();
    });

    // Hareketli ucgen isaretci (mevcut yatis)
    const t = (-roll - 90) * Math.PI / 180;
    const px = cx + Math.cos(t) * (rad - 30);
    const py = cy + Math.sin(t) * (rad - 30);
    c.save();
    c.translate(px, py);
    c.rotate(t + Math.PI / 2);
    c.beginPath();
    c.moveTo(0, -18);
    c.lineTo(-15, 12);
    c.lineTo(15, 12);
    c.closePath();
    c.fillStyle = R.sari;
    c.fill();
    c.restore();
    c.restore();
  }

  // Sabit ucak sembolu
  function ucakSemboluCiz(c, cx, cy){
    c.save();
    c.lineWidth = 7;
    c.strokeStyle = R.ucakKen;
    c.fillStyle = R.ucak;

    // Sol kanat
    c.beginPath();
    c.moveTo(cx - 150, cy);
    c.lineTo(cx - 62, cy);
    c.lineTo(cx - 62, cy + 26);
    c.stroke();
    // Sag kanat
    c.beginPath();
    c.moveTo(cx + 150, cy);
    c.lineTo(cx + 62, cy);
    c.lineTo(cx + 62, cy + 26);
    c.stroke();
    // Merkez nokta
    c.beginPath();
    c.arc(cx, cy, 7, 0, Math.PI * 2);
    c.fillStyle = R.ucakKen;
    c.fill();
    c.restore();
  }

  // -----------------------------------------------------------------
  // Kayan serit (hiz ve irtifa icin ortak)
  // -----------------------------------------------------------------
  // deger    : gosterilecek anlik deger
  // adim     : kucuk cizgi araligi (birim)
  // etiketAdim: rakam yazilacak aralik
  // birimPx  : 1 birim kac mantiksal piksel
  // sag      : true ise olcek cizgileri sagda (irtifa seridi)
  function seritCiz(c, x, y, w, h, deger, adim, etiketAdim, birimPx, sag){
    c.save();
    c.beginPath();
    c.rect(x, y, w, h);
    c.clip();

    c.fillStyle = R.serit;
    c.fillRect(x, y, w, h);

    const cy = y + h / 2;
    // Gorunur aralik
    const yariBirim = (h / 2) / birimPx;
    const alt = deger - yariBirim - adim;
    const ust = deger + yariBirim + adim;
    const ilk = Math.ceil(alt / adim) * adim;

    c.strokeStyle = R.metin;
    c.fillStyle = R.metin;
    c.lineWidth = 2.2;
    c.font = "600 30px system-ui, sans-serif";
    c.textBaseline = "middle";

    for (let v = ilk; v <= ust; v += adim){
      const py = cy - (v - deger) * birimPx;
      if (py < y - 20 || py > y + h + 20) continue;
      const buyuk = (Math.round(v / etiketAdim) * etiketAdim === Math.round(v));
      const uzunluk = buyuk ? 22 : 12;
      c.beginPath();
      if (sag){
        c.moveTo(x, py);
        c.lineTo(x + uzunluk, py);
      } else {
        c.moveTo(x + w, py);
        c.lineTo(x + w - uzunluk, py);
      }
      c.stroke();
      if (buyuk){
        c.textAlign = sag ? "left" : "right";
        const tx = sag ? (x + uzunluk + 10) : (x + w - uzunluk - 10);
        c.fillText(String(Math.round(v)), tx, py);
      }
    }
    c.restore();

    // Kenar cizgisi
    c.save();
    c.strokeStyle = R.seritKen;
    c.lineWidth = 2;
    c.beginPath();
    if (sag) { c.moveTo(x, y); c.lineTo(x, y + h); }
    else     { c.moveTo(x + w, y); c.lineTo(x + w, y + h); }
    c.stroke();
    c.restore();
  }

  // Anlik deger kutusu (serit ortasinda)
  function degerKutusuCiz(c, x, y, w, h, metin, sag, renk){
    c.save();
    const ok = 16;
    c.beginPath();
    if (sag){
      c.moveTo(x - ok, y + h / 2);
      c.lineTo(x, y);
      c.lineTo(x + w, y);
      c.lineTo(x + w, y + h);
      c.lineTo(x, y + h);
    } else {
      c.moveTo(x + w + ok, y + h / 2);
      c.lineTo(x + w, y);
      c.lineTo(x, y);
      c.lineTo(x, y + h);
      c.lineTo(x + w, y + h);
    }
    c.closePath();
    c.fillStyle = "rgba(8,10,14,0.94)";
    c.fill();
    c.strokeStyle = renk || R.metin;
    c.lineWidth = 3;
    c.stroke();

    c.fillStyle = renk || R.metin;
    c.font = "700 42px system-ui, sans-serif";
    c.textAlign = "center";
    c.textBaseline = "middle";
    c.fillText(metin, x + w / 2, y + h / 2 + 1);
    c.restore();
  }

  // Dikey hiz cubugu
  function dikeyHizCiz(c, x, y, w, h, vz){
    c.save();
    c.fillStyle = R.serit;
    c.fillRect(x, y, w, h);

    const cy = y + h / 2;
    // +-10 m/s araligi, dogrusal
    const enb = 10;
    const v = Math.max(-enb, Math.min(enb, vz));

    c.strokeStyle = "rgba(255,255,255,0.45)";
    c.lineWidth = 2;
    [-10, -5, -2, 0, 2, 5, 10].forEach(t => {
      const py = cy - (t / enb) * (h / 2 - 10);
      c.beginPath();
      c.moveTo(x + 2, py);
      c.lineTo(x + (t % 5 === 0 ? 16 : 9), py);
      c.stroke();
    });

    // Hareketli gosterge
    const py = cy - (v / enb) * (h / 2 - 10);
    c.strokeStyle = (Math.abs(vz) < 0.3) ? R.metin
                  : (vz > 0 ? R.yesil : R.sari);
    c.lineWidth = 5;
    c.beginPath();
    c.moveTo(x + 2, cy);
    c.lineTo(x + w - 4, py);
    c.stroke();

    c.fillStyle = R.metin;
    c.font = "600 24px system-ui, sans-serif";
    c.textAlign = "right";
    c.textBaseline = "middle";
    c.fillText(vz.toFixed(1), x + w - 4, y + h - 16);
    c.restore();
  }

  // -----------------------------------------------------------------
  // Pusula gulu (alt)
  // -----------------------------------------------------------------
  function pusulaCiz(c, cx, cy, rad, heading){
    c.save();
    c.beginPath();
    c.arc(cx, cy, rad + 8, 0, Math.PI * 2);
    c.fillStyle = "rgba(12,16,22,0.80)";
    c.fill();

    c.save();
    c.translate(cx, cy);
    c.rotate(-heading * Math.PI / 180);

    c.strokeStyle = R.metin;
    c.fillStyle = R.metin;
    c.font = "700 34px system-ui, sans-serif";
    c.textAlign = "center";
    c.textBaseline = "middle";

    for (let d = 0; d < 360; d += 5){
      const buyuk = (d % 10 === 0);
      const t = (d - 90) * Math.PI / 180;
      const r2 = rad - (buyuk ? 26 : 14);
      c.lineWidth = buyuk ? 2.8 : 1.8;
      c.beginPath();
      c.moveTo(Math.cos(t) * rad, Math.sin(t) * rad);
      c.lineTo(Math.cos(t) * r2, Math.sin(t) * r2);
      c.stroke();

      if (d % 30 === 0){
        const et = (d === 0) ? "N" : (d === 90) ? "E"
                 : (d === 180) ? "S" : (d === 270) ? "W"
                 : String(d / 10);
        const rt = rad - 54;
        c.save();
        c.translate(Math.cos(t) * rt, Math.sin(t) * rt);
        c.rotate(heading * Math.PI / 180);
        c.fillText(et, 0, 0);
        c.restore();
      }
    }
    c.restore();

    // Sabit ust isaretci
    c.beginPath();
    c.moveTo(cx, cy - rad - 4);
    c.lineTo(cx - 16, cy - rad - 30);
    c.lineTo(cx + 16, cy - rad - 30);
    c.closePath();
    c.fillStyle = R.mor;
    c.fill();

    // Merkez basik degeri
    c.fillStyle = R.metin;
    c.font = "700 44px system-ui, sans-serif";
    c.textAlign = "center";
    c.textBaseline = "middle";
    c.fillText(String(Math.round(heading)).padStart(3, "0") + "\u00B0",
               cx, cy);
    c.font = "600 22px system-ui, sans-serif";
    c.fillStyle = R.mor;
    c.fillText("MAG", cx, cy + 38);
    c.restore();
  }

  // -----------------------------------------------------------------
  // Tam kare cizimi
  // -----------------------------------------------------------------
  // d: dron sozlugu (null ise "veri yok" ekrani)
  function ciz(cv, d){
    const c = cv.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const gw = cv.clientWidth || 400;
    const gh = cv.clientHeight || 300;

    // Tuval cozunurlugunu yalnizca degistiginde ayarla (pahali islem)
    const iw = Math.round(gw * dpr);
    const ih = Math.round(gh * dpr);
    if (cv.width !== iw || cv.height !== ih){
      cv.width = iw;
      cv.height = ih;
    }

    c.setTransform(1, 0, 0, 1, 0, 0);
    c.clearRect(0, 0, iw, ih);

    // 1000x1000 mantiksal alani panele sigdir (en-boy koruyarak)
    const olcek = Math.min(iw / T, ih / T);
    const ox = (iw - T * olcek) / 2;
    const oy = (ih - T * olcek) / 2;
    c.setTransform(olcek, 0, 0, olcek, ox, oy);

    // Arka plan
    c.fillStyle = "#05070a";
    c.fillRect(0, 0, T, T);

    if (!d){
      c.fillStyle = "rgba(255,255,255,0.28)";
      c.font = "600 44px system-ui, sans-serif";
      c.textAlign = "center";
      c.textBaseline = "middle";
      c.fillText(((typeof D === "function") ? (D().fpdDronSecilmedi) : "")
             || "DRON SE\u00c7\u0130LMED\u0130", T / 2, T / 2);
      return;
    }

    const roll  = sayi(d.roll);
    const pitch = sayi(d.pitch);
    const hdg   = (sayi(d.heading) + 360) % 360;
    const hiz   = sayi(d.groundspeed);
    const alt   = sayi(d.alt_rel);
    const vz    = sayi(d.vz);
    const canli = !!d.baglanti;

    // Yerlesim
    const seritW = 150;
    const mx = seritW + 24, my = 92;
    const mw = T - 2 * (seritW + 24), mh = 560;

    // Orta: yapay ufuk
    ufukCiz(c, roll, pitch, mx, my, mw, mh);
    yatisOlcegiCiz(c, roll, mx + mw / 2, my + mh / 2, mh / 2 - 14);
    ucakSemboluCiz(c, mx + mw / 2, my + mh / 2);

    // Orta pencere kenari
    c.strokeStyle = "rgba(255,255,255,0.30)";
    c.lineWidth = 2;
    c.strokeRect(mx, my, mw, mh);

    // Sol: hiz seridi (m/s, 1 birim = 9 px, 5'te bir etiket)
    seritCiz(c, 16, my, seritW, mh, hiz, 1, 5, 9, false);
    degerKutusuCiz(c, 16, my + mh / 2 - 34, seritW, 68,
                   hiz.toFixed(0), false, R.metin);
    c.save();
    c.fillStyle = R.yesil;
    c.font = "600 24px system-ui, sans-serif";
    c.textAlign = "center";
    c.fillText("m/s", 16 + seritW / 2, my - 18);
    c.restore();

    // Sag: irtifa seridi (m, 1 birim = 3.4 px, 10'da bir etiket)
    const sagX = T - 16 - seritW;
    seritCiz(c, sagX, my, seritW, mh, alt, 5, 10, 3.4, true);
    degerKutusuCiz(c, sagX, my + mh / 2 - 34, seritW, 68,
                   alt.toFixed(0), true, R.metin);
    c.save();
    c.fillStyle = R.camgobek;
    c.font = "600 24px system-ui, sans-serif";
    c.textAlign = "center";
    c.fillText("m AGL", sagX + seritW / 2, my - 18);
    c.restore();

    // Dikey hiz cubugu (irtifa seridinin sagi)
    dikeyHizCiz(c, sagX + seritW + 6, my + mh / 2 - 150, 44, 300, vz);

    // Ust: kip satiri
    c.save();
    c.fillStyle = "rgba(12,16,22,0.80)";
    c.fillRect(16, 14, T - 32, 62);
    c.font = "700 34px system-ui, sans-serif";
    c.textBaseline = "middle";
    c.textAlign = "left";
    c.fillStyle = R.yesil;
    c.fillText(String(d.mod || "?").toUpperCase(), 34, 45);
    c.textAlign = "center";
    c.fillStyle = d.armed ? R.kirmizi : "rgba(255,255,255,0.55)";
    c.fillText(d.armed ? "ARMED" : "DISARMED", T / 2, 45);
    c.textAlign = "right";
    c.fillStyle = canli ? R.yesil : R.kirmizi;
    c.fillText(canli ? "CANLI" : "KOPUK", T - 34, 45);
    c.restore();

    // Alt: pusula gulu
    pusulaCiz(c, T / 2, my + mh + 148, 130, hdg);

    // Alt bilgi satiri: batarya, uydu, MSL
    c.save();
    c.font = "600 28px system-ui, sans-serif";
    c.textBaseline = "middle";
    const by = T - 34;

    const bpct = sayi(d.batarya_pct, -1);
    // batarya_pct -1 = bilinmiyor; dogrudan yazilirsa "-1%" gorunur
    const bMetin = (bpct < 0) ? "--" : (Math.round(bpct) + "%");
    c.textAlign = "left";
    c.fillStyle = (bpct >= 0 && bpct < 20) ? R.kirmizi
                : (bpct >= 0 && bpct < 40) ? R.sari : R.yesil;
    c.fillText("BAT " + bMetin + "  ·  "
               + sayi(d.batarya_v).toFixed(1) + "V", 26, by);

    const uydu = sayi(d.uydu);
    c.textAlign = "center";
    c.fillStyle = (uydu >= 8) ? R.yesil : (uydu >= 5 ? R.sari : R.kirmizi);
    c.fillText("GPS " + uydu, T / 2, by);

    c.textAlign = "right";
    c.fillStyle = R.camgobek;
    c.fillText("MSL " + sayi(d.alt_msl).toFixed(0) + " m", T - 26, by);
    c.restore();
  }

  window.PFD = { ciz: ciz };
})();
