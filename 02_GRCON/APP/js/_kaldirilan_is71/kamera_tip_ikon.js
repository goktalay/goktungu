/* GOKTUNGU GCS — kamera_tip_ikon.js
 * FAZ 18 / IS 7 (v2.4.81)
 *
 * NEDEN: Kamera ekleme formunda protokol tek bir <select> icindeydi:
 *   rtsp / rtp / mjpeg / hls / http / donanim / dji
 * Kullanici "kamera tipleri ikon olarak gelsin" dedi.
 *
 * TASARIM KARARI: <select id="kamProtokol"> KALDIRILMADI, GIZLENMEDI.
 * Gerekce: kameralar.js icinde bes ayri yerde okunuyor/yaziliyor
 * (satir 56 tanim, 72 okuma, 92 change dinleyicisi, 185 duzenlemede
 * deger yazma, 218 kaydetmede okuma). Select kaldirilirsa bu bes
 * nokta da degismek zorunda kalir ve duzenleme akisi kirilir.
 * Bunun yerine select'in USTUNE ikonlu dugme kumesi eklendi;
 * dugme tiklaninca select.value yazilir ve `change` olayi elle
 * tetiklenir. Boylece mevcut mantik hic degismeden calisir.
 *
 * Select ayrica GORUNUR kalir: klavye ile gezinen ve ekran okuyucu
 * kullanan pilot icin erisilebilir yol korunur.
 */
(function () {
  "use strict";

  /* Protokol -> ikon + kisa etiket.
   * Etiketler i18n anahtarlarina baglanir; anahtar yoksa yedek
   * metin kullanilir (t() ikinci parametresi). */
  const TIPLER = [
    { deger: "rtsp",    ikon: "fa-solid fa-video",
      anahtar: "kamTipRtsp",    yedek: "RTSP" },
    { deger: "rtp",     ikon: "fa-solid fa-tower-broadcast",
      anahtar: "kamTipRtp",     yedek: "RTP / UDP" },
    { deger: "mjpeg",   ikon: "fa-solid fa-images",
      anahtar: "kamTipMjpeg",   yedek: "MJPEG" },
    { deger: "hls",     ikon: "fa-solid fa-file-video",
      anahtar: "kamTipHls",     yedek: "HLS" },
    { deger: "http",    ikon: "fa-solid fa-globe",
      anahtar: "kamTipHttp",    yedek: "HTTP VİDEO" },
    { deger: "donanim", ikon: "fa-solid fa-camera",
      anahtar: "kamTipDonanim", yedek: "DONANIM" },
    { deger: "dji",     ikon: "fa-solid fa-helicopter",
      anahtar: "kamTipDji",     yedek: "DJI DRON" }
  ];

  let izgara = null;

  function cevir(anahtar, yedek) {
    if (typeof window.t === "function") {
      try { return window.t(anahtar, yedek); } catch (e) { /* yut */ }
    }
    return yedek;
  }

  /* Secili dugmeyi select degerine gore isaretler. */
  function isaretle() {
    const sec = document.getElementById("kamProtokol");
    if (!sec || !izgara) return;
    const deger = sec.value;
    izgara.querySelectorAll(".kam-tip-btn").forEach((b) => {
      if (b.dataset.tip === deger) b.classList.add("secili");
      else b.classList.remove("secili");
    });
  }

  function izgaraKur() {
    const sec = document.getElementById("kamProtokol");
    if (!sec) return false;
    if (document.getElementById("kamTipIzgara")) return true;

    izgara = document.createElement("div");
    izgara.id = "kamTipIzgara";
    izgara.className = "kam-tip-izgara";

    TIPLER.forEach((tp) => {
      const b = document.createElement("button");
      b.type = "button";           // form gondermesin
      b.className = "kam-tip-btn";
      b.dataset.tip = tp.deger;
      b.setAttribute("data-i18n-title", tp.anahtar);
      b.title = cevir(tp.anahtar, tp.yedek);

      const i = document.createElement("i");
      tp.ikon.split(/\s+/).forEach((c) => { if (c) i.classList.add(c); });
      b.appendChild(i);

      const s = document.createElement("span");
      s.setAttribute("data-i18n", tp.anahtar);
      s.textContent = cevir(tp.anahtar, tp.yedek);
      b.appendChild(s);

      b.addEventListener("click", () => {
        const hedef = document.getElementById("kamProtokol");
        if (!hedef) return;
        hedef.value = tp.deger;
        // kameralar.js:92 bu olayi dinliyor; elle tetiklenmeli.
        hedef.dispatchEvent(new Event("change", { bubbles: true }));
        isaretle();
      });

      izgara.appendChild(b);
    });

    // Select'in ONUNE yerlestir: once ikonlar, altta klasik liste.
    sec.parentNode.insertBefore(izgara, sec);

    // Select disaridan degisirse (duzenleme akisi: kameralar.js:185)
    // isaretleme guncellenmeli.
    sec.addEventListener("change", isaretle);
    isaretle();
    return true;
  }

  /* Kamera penceresi acilinca kur. Pencere DOM'da statik oldugu icin
   * DOMContentLoaded yeterli; ancak i18n sonradan yuklenirse
   * etiketler tazelenir. */
  function baslat() {
    if (!izgaraKur()) return;
  }

  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", baslat);
  else baslat();

  // Dil degisiminde etiketleri tazele (i18n data-i18n'i kendi ceviriyor,
  // ama title icin yedek yol).
  window.kamTipIkonTazele = function () {
    if (!izgara) return;
    izgara.querySelectorAll(".kam-tip-btn").forEach((b) => {
      const tp = TIPLER.find((x) => x.deger === b.dataset.tip);
      if (tp) b.title = cevir(tp.anahtar, tp.yedek);
    });
    isaretle();
  };
})();
