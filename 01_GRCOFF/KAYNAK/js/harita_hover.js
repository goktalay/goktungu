// =================================================================
// GÖKTUNGU — HARİTA İKON ETİKETİ: FAREYLE ÜZERİNE GELİNCE (v2.4.202)
// -----------------------------------------------------------------
// Kullanici istegi: "dronu ve radar hedefini haritada gosteren ikonun
// altinda cikan bilgilendirme normalde gizli olsun, mouse ile uzerine
// gelince ciksin". Dron (dronlar.js) ve radar hedefi (hedefler.js)
// etiketleri `show:false` ile olusur; bu modul fare hareketinde
// drillPick ile altindaki varligi bulur ve YALNIZ onun etiketini acar.
// Radar hedef kaydi `radarHedefVarliklar` radar_panel.js'te ust duzey
// `let` olarak tanimlidir (betikler arasi sozcuksel global).
// Projenin kanitlanmis deseni: ScreenSpaceEventHandler yerine container
// uzerinde DOM olayi (bkz. dronlar.js kurHaritaDronTik).
// =================================================================
"use strict";
(function haritaHover(){
  let acik = null;
  let sonIslem = 0;
  // v2.4.205: EO (kamera) ikonu uzerine gelince kucuk canli onizleme
  let onizleme = null;
  function eoOnizlemeAc(ent, ev){
    const eid = parseInt(String(ent.id).slice(3), 10);
    const kam = typeof window.m50KameraBul === "function" ? window.m50KameraBul(eid) : null;
    const kutu = document.createElement("div");
    kutu.className = "eo-onizleme";
    const ad = document.createElement("div"); ad.className = "eo-onizleme-ad";
    ad.textContent = (ent.label && ent.label.text && ent.label.text.getValue) ? ent.label.text.getValue() : ("EO " + eid);
    kutu.appendChild(ad);
    if (kam && typeof window.kameraOnizlemeUrl === "function"){
      const img = document.createElement("img");
      img.src = window.kameraOnizlemeUrl(kam.id) + (window.kameraOnizlemeUrl(kam.id).includes("?") ? "&" : "?") + "hover=" + Date.now();
      img.alt = "";
      kutu.appendChild(img);
    } else {
      const yok = document.createElement("div"); yok.className = "eo-onizleme-yok";
      yok.textContent = (typeof D === "function" && D().eoOnizlemeYok) || "Canlı görüntü kaydı yok";
      kutu.appendChild(yok);
    }
    document.body.appendChild(kutu);
    onizleme = kutu;
    eoOnizlemeTasi(ev);
  }
  function eoOnizlemeTasi(ev){
    if (!onizleme) return;
    const w = onizleme.offsetWidth || 200, h = onizleme.offsetHeight || 130;
    let x = ev.clientX + 16, y = ev.clientY + 16;
    if (x + w > window.innerWidth - 8) x = ev.clientX - w - 16;
    if (y + h > window.innerHeight - 8) y = ev.clientY - h - 16;
    onizleme.style.left = x + "px"; onizleme.style.top = y + "px";
  }
  function eoOnizlemeKapat(){
    if (onizleme){ const im = onizleme.querySelector("img"); if (im) im.src = ""; onizleme.remove(); onizleme = null; }
  }
  function eoMu(ent){ return !!(ent && typeof ent.id === "string" && ent.id.startsWith("eo_") && !ent.id.startsWith("eo_gorus_")); }
  function hedefMi(ent){
    if (!ent) return false;
    if (eoMu(ent)) return true;
    if (typeof ent.id === "string" && ent.id.startsWith("dron_") && !ent.id.startsWith("dron_yon_")) return true;
    let rh = null;
    try { rh = (typeof radarHedefVarliklar !== "undefined") ? radarHedefVarliklar : window.radarHedefVarliklar; } catch (e) {}
    if (rh) for (const k of Object.keys(rh)) if (rh[k] === ent) return true;
    return false;
  }
  function kapat(){
    if (acik && acik.label && !eoMu(acik)) { try { acik.label.show = false; } catch (e) {} }
    eoOnizlemeKapat();
    acik = null;
  }
  function isle(ev){
    const simdi = Date.now();
    if (simdi - sonIslem < 60) return;
    sonIslem = simdi;
    if (typeof viewer === "undefined" || !viewer || !viewer.scene) return;
    const r = viewer.scene.canvas.getBoundingClientRect();
    const p = new Cesium.Cartesian2(ev.clientX - r.left, ev.clientY - r.top);
    let secilen = [];
    try { secilen = viewer.scene.drillPick(p, 6) || []; } catch (e) { return; }
    let bulunan = null;
    for (const s of secilen){ const ent = s && s.id; if (hedefMi(ent)) { bulunan = ent; break; } }
    if (bulunan === acik){ if (onizleme) eoOnizlemeTasi(ev); return; }
    kapat();
    if (bulunan && eoMu(bulunan)){ eoOnizlemeAc(bulunan, ev); acik = bulunan; return; }
    if (bulunan && bulunan.label){ try { bulunan.label.show = true; } catch (e) {} acik = bulunan; }
  }
  function kur(){
    const kap = document.getElementById("cesiumContainer");
    if (!kap || typeof viewer === "undefined" || !viewer || !viewer.scene){ setTimeout(kur, 500); return; }
    kap.addEventListener("mousemove", isle, {passive: true});
    kap.addEventListener("mouseleave", kapat, {passive: true});
  }
  kur();
})();
