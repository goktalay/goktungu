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
  function hedefMi(ent){
    if (!ent) return false;
    if (typeof ent.id === "string" && ent.id.startsWith("dron_") && !ent.id.startsWith("dron_yon_")) return true;
    let rh = null;
    try { rh = (typeof radarHedefVarliklar !== "undefined") ? radarHedefVarliklar : window.radarHedefVarliklar; } catch (e) {}
    if (rh) for (const k of Object.keys(rh)) if (rh[k] === ent) return true;
    return false;
  }
  function kapat(){
    if (acik && acik.label) { try { acik.label.show = false; } catch (e) {} }
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
    if (bulunan === acik) return;
    kapat();
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
