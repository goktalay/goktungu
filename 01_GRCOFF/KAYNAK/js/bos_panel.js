/* GOKTUNGU GCS — bos_panel.js
 * FAZ 18 / IS 7 (v2.4.81)
 *
 * NEDEN: Panellerde veri yokken uc ayri dosyada AYNI kod tekrarlaniyordu:
 *   const bos = document.createElement("div");
 *   bos.className = "ai-satir";
 *   bos.style.justifyContent = "center";
 *   bos.style.color = "var(--soluk)";
 *   bos.textContent = "...";
 * Sonuc: kucuk gri bir metin satiri. Kullanici bunun yerine Kameralar
 * panelindeki gibi BUYUK IKON + kisa aciklama istedi.
 *
 * Kameralar/Rotalar panelleri zaten dogru desende:
 *   <div class="bos-panel"><i class="fa-solid fa-video"></i>
 *     <span>KAYITLI KAMERA YOK</span></div>
 * `.bos-panel` CSS'i stil.css:493'te tanimli (64px ikon + 11px yazi).
 * Bu modul o desenli ogeyi tek yerden uretir; uc dosya buraya baglanir.
 *
 * NOT: `bosPanelYap` ASLA innerHTML kullanmaz. Tespit/kisi/arac
 * metinleri kullanici verisi tasiyabilir; textContent ile basilir.
 */
(function () {
  "use strict";

  /* Buyuk ikonlu bos durum ogesi uretir.
   * @param {string} metin  Gosterilecek kisa aciklama (zorunlu)
   * @param {string} ikon   Font Awesome sinifi, orn "fa-solid fa-user-tag"
   * @returns {HTMLElement} .bos-panel ogesi
   */
  function bosPanelYap(metin, ikon) {
    const kutu = document.createElement("div");
    kutu.className = "bos-panel";
    if (ikon) {
      const i = document.createElement("i");
      // Sinif dizesi bosluklu gelebilir: "fa-solid fa-user-tag"
      String(ikon).trim().split(/\s+/).forEach((c) => {
        if (c) i.classList.add(c);
      });
      kutu.appendChild(i);
    }
    const s = document.createElement("span");
    s.textContent = metin == null ? "" : String(metin);
    kutu.appendChild(s);
    return kutu;
  }

  window.bosPanelYap = bosPanelYap;
})();
