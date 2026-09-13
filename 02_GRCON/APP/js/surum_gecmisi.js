// =====================================================================
// SURUM_GECMISI.JS - v2.1.8
// ---------------------------------------------------------------------
// Program Hakkinda popup'indaki surum numarasina (#hkSurum) tiklaninca
// acilan "SURUM GECMISI" popup'i. GCS_SURUM_GECMISI (js/surum.js)
// verisini akordiyon listesi olarak gosterir: satira tiklaninca o
// surumun degisiklik listesi acilir/kapanir. Popup tasinabilir ve
// basliginda kapatma dugmesi vardir; fare konumunda acilir.
// =====================================================================
"use strict";

(function () {
  let _sgPopup = null;

  function sgKapat() {
    if (_sgPopup) { _sgPopup.remove(); _sgPopup = null; }
    document.removeEventListener("pointerdown", sgDisTik, true);
  }

  function sgDisTik(ev) {
    if (_sgPopup && !_sgPopup.contains(ev.target)) sgKapat();
  }

  // KAPATMA - DELEGASYON (v2.3.1): carpi tiklamasi document seviyesinde
  // capture fazinda yakalanir; popup ornegine bagli dinleyicilerin
  // (tasima / pointer-capture / yeniden olusturma) hicbir kosulda
  // yutamayacagi garantili kapatma yoludur.
  document.addEventListener("pointerdown", (ev) => {
    const dugme = ev.target && ev.target.closest
      ? ev.target.closest(".sg-kapat") : null;
    if (!dugme) return;
    ev.stopPropagation();
    ev.preventDefault();
    const pop = dugme.closest(".sg-popup");
    if (pop) pop.remove();
    if (_sgPopup && !_sgPopup.isConnected) _sgPopup = null;
    sgKapat();
  }, true);

  function sgAc(fare) {
    if (_sgPopup) { sgKapat(); return; }
    if (typeof GCS_SURUM_GECMISI === "undefined") return;
    const t = (typeof I18N !== "undefined" && typeof dil !== "undefined")
      ? (I18N[dil] || {}) : {};

    const pop = document.createElement("div");
    pop.id = "surumGecmisPopup";
    pop.className = "sg-popup";

    // Baslik (tasima + kapat)
    const baslik = document.createElement("div");
    baslik.className = "sg-baslik";
    baslik.innerHTML =
      "<span><i class='fa-solid fa-clock-rotate-left'></i> " +
      (t.sgBaslik || "S\u00dcR\u00dcM GE\u00c7M\u0130\u015e\u0130") +
      "</span>" +
      "<button class='sg-kapat' title='Kapat'>" +
      "<i class='fa-solid fa-xmark'></i></button>";
    pop.appendChild(baslik);

    // Govde: surum satirlari (akordiyon)
    const govde = document.createElement("div");
    govde.className = "sg-govde";
    /* FAZ18-IS17-SURUM-ALAN: KAYIT ALAN ADI UYUMU
     * ----------------------------------------------------------------
     * OLCUM: 109 kayit tarandi. 98 kayit `d` alani, 10 kayit `m` alani
     * tasiyor; 1 gecis kaydi (v2.4.85) her ikisini de tasiyor.
     * v2.4.86'da kayit deseni degistirilmis (`d` -> `m`, ayrica `b`
     * ozeti eklenmis) ancak BU OKUYUCU guncellenmemisti.
     *
     * Eski kod dogrudan `v.d.map(...)` cagiriyordu. En yeni kayitta
     * `d` bulunmadigi icin dongu ILK turda patliyor, `pop` ogesi
     * govdeye hic eklenmiyor ve pencere ACILMIYOR.
     *
     * Alan adi tercihi: yeni desen (`m`) once denenir, sonra eski
     * (`d`). 98 eski kayit silinmeyecegi icin geriye donuk uyum
     * zorunludur.
     */
    function alanAl(v, kisa, uzun, varsayilan) {
      if (!v) return varsayilan;
      if (v[kisa] != null) return v[kisa];
      if (v[uzun] != null) return v[uzun];
      return varsayilan;
    }

    function maddeleriAl(v) {
      var ham = alanAl(v, "m", "maddeler",
        (v && v.d != null) ? v.d : null);
      if (ham == null) return [];
      // Dizi olmayan deger de karsilanir: tek dize gelirse tek madde.
      if (!Array.isArray(ham)) return [String(ham)];
      return ham;
    }

    function kacir(x) {
      // Kayit metinleri surum.js'ten gelir (kendi kaynagimiz), ancak
      // innerHTML'e yazildigi icin yine de kacisla yaziyoruz: ileride
      // kayit metni baska bir yerden beslenirse yapiyi bozmasin.
      return String(x)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    }

    GCS_SURUM_GECMISI.forEach((v, i) => {
      const sat = document.createElement("div");
      sat.className = "sg-satir";
      /* Satir bazli dayaniklilik: tek bozuk kayit TUM listeyi
         goturmemeli. Eski kodda tek bir eksik alan pencerenin
         tamamini engelliyordu; ayni tuzaga bir daha dusulmesin. */
      try {
        const rozet = (i === 0)
          ? "<span class='sg-guncel'>" + (t.sgGuncel || "G\u00dcNCEL") + "</span>"
          : "";
        const surum = alanAl(v, "s", "surum", "?");
        const tarih = alanAl(v, "t", "tarih", "");
        const baslikMetni = alanAl(v, "b", "baslik", "");
        const maddeler = maddeleriAl(v);
        /* `b` alani (kisa ozet) yeni kayitlarda var ve hic
           kullanilmiyordu. Kapali durumda gorunmesi listeyi
           taranabilir kilar; kullanici her kaydi acmak zorunda
           kalmaz. */
        const ozet = baslikMetni
          ? "<div class='sg-ozet'>" + kacir(baslikMetni) + "</div>"
          : "";
        sat.innerHTML =
          "<div class='sg-ust'>" +
            "<i class='fa-solid fa-chevron-right sg-ok'></i>" +
            "<span class='sg-no'>v" + kacir(surum) + "</span>" + rozet +
            "<span class='sg-tarih'>" + kacir(tarih) + "</span>" +
          "</div>" +
          ozet +
          "<ul class='sg-detay'>" +
            maddeler.map((m) => "<li>" + kacir(m) + "</li>").join("") +
          "</ul>";
        sat.querySelector(".sg-ust").addEventListener("click", () => {
          sat.classList.toggle("acik");
        });
      } catch (hata) {
        /* Bozuk kayit sessizce YUTULMAZ: kullaniciya gorunur bir
           uyari birakilir ve konsola kaydedilir. Sessiz basarisizlik
           bu kusurun on gun fark edilmemesinin sebebiydi. */
        sat.innerHTML =
          "<div class='sg-ust'><span class='sg-no'>v" +
          kacir(alanAl(v, "s", "surum", "?")) + "</span>" +
          "<span class='sg-tarih'>" +
          (t.sgKayitBozuk || "kayit okunamadi") + "</span></div>";
        try { console.warn("[SURUM] kayit okunamadi:", v, hata); }
        catch (e) {}
      }
      govde.appendChild(sat);
      if (i === 0) sat.classList.add("acik"); // guncel surum acik gelir
    });
    pop.appendChild(govde);
    document.body.appendChild(pop);

    // Fare konumunda ac (ekrandan tasmasin)
    const w = pop.offsetWidth, h = pop.offsetHeight;
    let x = (fare && fare.clientX) ? fare.clientX : (window.innerWidth - w) / 2;
    let y = (fare && fare.clientY) ? fare.clientY : (window.innerHeight - h) / 2;
    x = Math.max(8, Math.min(x, window.innerWidth - w - 8));
    y = Math.max(8, Math.min(y, window.innerHeight - h - 8));
    pop.style.left = x + "px";
    pop.style.top = y + "px";

    // Kapatma: pointerdown asamasinda yakala (tasima/pointer-capture
    // click olayini yutabildigi icin click'e guvenilmez)
    const kapatBtn = baslik.querySelector(".sg-kapat");
    kapatBtn.addEventListener("pointerdown", (ev) => {
      ev.stopPropagation();
      ev.preventDefault();
      sgKapat();
    });
    kapatBtn.addEventListener("click", sgKapat);
    setTimeout(() =>
      document.addEventListener("pointerdown", sgDisTik, true), 0);

    // Ortak pencere yonetimine bagla (z-order / aktiflesme)
    if (typeof window.pencereEnUsteKur === "function") {
      window.pencereEnUsteKur(pop);
      window.pencereEnUsteGetir(pop);
    }

    // Basliktan tasima
    let tut = null;
    baslik.addEventListener("pointerdown", (ev) => {
      if (ev.target.closest(".sg-kapat")) return;
      const r = pop.getBoundingClientRect();
      tut = { dx: ev.clientX - r.left, dy: ev.clientY - r.top };
      baslik.setPointerCapture(ev.pointerId);
    });
    baslik.addEventListener("pointermove", (ev) => {
      if (!tut) return;
      pop.style.left = Math.max(0, Math.min(ev.clientX - tut.dx,
        window.innerWidth - pop.offsetWidth)) + "px";
      pop.style.top = Math.max(0, Math.min(ev.clientY - tut.dy,
        window.innerHeight - pop.offsetHeight)) + "px";
    });
    const birak = () => { tut = null; };
    baslik.addEventListener("pointerup", birak);
    baslik.addEventListener("pointercancel", birak);
  }

  // #hkSurum tiklamasi (Program Hakkinda icindeki surum numarasi)
  function kur() {
    const srm = document.getElementById("hkSurum");
    if (!srm) return;
    srm.classList.add("sg-tiklanabilir");
    srm.title = ((typeof D === "function") ? (D().ipSurumGecmisiGoster) : "") || "S\u00fcr\u00fcm ge\u00e7mi\u015fini g\u00f6ster";
    srm.addEventListener("click", (ev) => {
      ev.stopPropagation();
      sgAc(ev);
    });
  }
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", kur);
  else kur();
})();
