// js/widget_baslatici.js — v2.4.247 WIDGET BASLATICI
//
// Kullanici: "Widget'lari Yardim menusunden cikart, Google'da uygulamalari
// sagda bir ikonla gosterir, onun gibi yap: ikonlar ustte altlarinda yazi,
// aktif olanlar secili olsun."
// Tiklama isleyicisi widget.js'tedir (`.mb-widget-toggle[data-widget]`);
// burada yalniz acma/kapama ve aktif isaretleme yapilir.
(function () {
  const btn = () => document.getElementById("btnWidgetler");
  const kutu = () => document.getElementById("wgBaslatici");
  function aktifTazele() {
    const k = kutu(); if (!k) return;
    k.querySelectorAll(".wg-tile[data-popup-hedef]").forEach((t) => {
      const w = document.getElementById(t.dataset.popupHedef);
      const acik = !!(w && !w.classList.contains("popup-gizli") && getComputedStyle(w).display !== "none");
      t.classList.toggle("aktif", acik);
    });
  }
  function ac() { const k = kutu(), b = btn(); if (!k) return; aktifTazele(); k.classList.add("acik"); if (b) b.classList.add("acik");
    if (typeof window.menubarKapat === "function") window.menubarKapat(); }
  function kapat() { const k = kutu(), b = btn(); if (k) k.classList.remove("acik"); if (b) b.classList.remove("acik"); }
  function acikMi() { const k = kutu(); return !!(k && k.classList.contains("acik")); }
  function bagla() {
    if (bagla._bagli) return;   // cift baglama (DOMContentLoaded + dogrudan) -> cift toggle
    const b = btn(), k = kutu(); if (!b || !k) return;
    bagla._bagli = true;
    b.addEventListener("click", (ev) => { ev.stopPropagation(); acikMi() ? kapat() : ac(); });
    // Yakalama asamasi: widget.js'in kutucuk isleyicisi stopPropagation
    // yapar; kabarcik asamasinda buraya hic ulasmazdi.
    k.addEventListener("click", () => { setTimeout(aktifTazele, 80); }, true);
    k.addEventListener("click", (ev) => { ev.stopPropagation(); });
    document.addEventListener("click", (ev) => { if (acikMi() && !k.contains(ev.target) && ev.target !== b) kapat(); });
    document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && acikMi()) kapat(); });
    // Menubar acilinca baslatici kapanir
    document.querySelectorAll(".mb-item").forEach((m) => m.addEventListener("click", () => kapat()));
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bagla); else bagla();
  window.widgetBaslaticiAc = ac; window.widgetBaslaticiKapat = kapat; window.widgetBaslaticiTazele = aktifTazele;
})();
