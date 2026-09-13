/* =====================================================================
   PANEL ACILIS YERLESTIRME                       (FAZ 18 / IS 3)
   Isaret: FAZ18-IS3-PANEL-ACILIS
   =====================================================================
   ISTEK: "tum paneller ekranin ortasinda acilsin ve min 500px X 400px
   olculerinde acilsin sonra kendisi degistirmek isterse degistirsin"

   OLCULEN DURUM: Arayuzde ortalama diye bir sozlesme YOKTU. Her pencere
   kendi sabitini tasiyordu: `.dk-mini-popup` 200px, `.bolum-popup`
   320px + `left:120px top:90px`, `.angi-popup` `top:80px`,
   `.suru-popup` `translateX(-50%)`, `.gecmis-popup` 760px. Yalnizca
   `.dk-param-popup` gercekten ortaliydi. Yukseklik neredeyse hic
   bildirilmemis, icerik kadardi.

   YAKLASIM: 40'tan fazla CSS kuralini elle duzeltmek yerine ACILIS
   ANINA tek bir yerlestirme kurali baglanir. `popup_tasima.js` zaten
   `window.PENCERE_SECICI` ile 28 seciciyi tek kaynakta topluyor ve
   MutationObserver ile gizli->gorunur gecisini yakaliyor; ayni evren
   yeniden kullanilir, yeni bir pencere listesi TUTULMAZ.

   KULLANICI TERCIHI USTUNDUR: pencerenin `gcs_pencere_konum` altinda
   kayitli konumu varsa hicbir sey yapilmaz. Yani kullanici bir kez
   tasidiktan ya da boyutlandirdiktan sonra kendi duzenini korur --
   istegin "sonra kendisi degistirmek isterse degistirsin" kismi.
   ===================================================================== */
(function () {
  "use strict";

  const EN_AZ_GENISLIK = 500;
  const EN_AZ_YUKSEKLIK = 400;
  const KENAR_PAY = 16;        // gorunur alan kenarindan en az bosluk

  // ------------------------------------------------------------------
  // DISLAMA: fare imlecinin yaninda acilan BAGLAM pencereleri.
  // Bunlar 500x400'e buyutulurse ekrani kaplar ve islevleri bozulur;
  // kullanicinin kastettigi "panel" bunlar degil. Olculdu: telemetri
  // 250px, kip 232px, kamera secim 260px, mini kaydirici 200px.
  // ------------------------------------------------------------------
  const DISLANAN = [
    ".dk-mini-popup", ".dk-telemetri-popup", ".dk-mod-popup",
    ".dk-kamsec-popup", ".kam-oniz-popup", ".lok-kam-popup",
    ".dk-islem-popup", ".ang-menu", ".dron-kart",
    "#rotaNoktaPopup", "#haritaMenu", "#profilMenu", "#haritaAramaPopup",
    // Onay kutulari: kisa soru + iki dugme. Buyutulurse bos alan olur.
    "#onayKutu", "#onayPerde",
  ].join(", ");

  // ------------------------------------------------------------------
  // Ust bar alti sinir: popup_tasima.js'teki TEK KAYNAKtan okunur.
  // Kendi sabitini tutmak, header inceldiginde kopmaya yol acar.
  // ------------------------------------------------------------------
  function minUst() {
    if (typeof window.pencereMinTop === "function") {
      try { return window.pencereMinTop(); } catch (e) {}
    }
    return 48;
  }

  // ------------------------------------------------------------------
  // Konum anahtari: `popup_tasima.js` anahtari kapanista tutuyor,
  // pencere nesnesine YAZMIYOR (olculdu: `_konumAnahtar` alani yok).
  // Bu yuzden anahtar burada ayni onek sozlesmesiyle yeniden uretilir:
  //   pp_<id>  statik popup ve perde kutulari
  //   yz_<id>  yuzen paneller
  // Anahtar cozulemezse kayit ARANMAZ ve pencere yine ortalanir.
  // ------------------------------------------------------------------
  function anahtarCoz(el) {
    if (el.classList.contains("yuzen-panel") && el.id) return "yz_" + el.id;
    if (el.id) return "pp_" + el.id;
    // Perde icindeki kutu: anahtar perdenin kimligiyle kaydediliyor
    const perde = el.parentElement;
    if (perde && perde.id && /Perde$/.test(perde.id)) {
      return "pp_" + perde.id;
    }
    return null;
  }

  function kayitliKonumVarMi(anahtar) {
    if (!anahtar) return false;
    try {
      const ham = localStorage.getItem("gcs_pencere_konum");
      if (!ham) return false;
      const k = JSON.parse(ham)[anahtar];
      return !!(k && typeof k.l === "number" && typeof k.t === "number");
    } catch (e) { return false; }
  }

  // ------------------------------------------------------------------
  // ILK ACILIS YERLESTIRMESI
  // ------------------------------------------------------------------
  function yerlestir(el) {
    if (!el || el._acilisYerlesti) return;

    // IS56: dok kapsayicisi kontrolu kaldirildi — ic ice gecme
    // davranisi artik yok, `.dok-kapsayici` hic uretilmiyor.

    // Baglam pencereleri dislanir
    if (el.matches && el.matches(DISLANAN)) {
      el._acilisYerlesti = true;
      return;
    }
    if (el.closest && el.closest(DISLANAN)) {
      el._acilisYerlesti = true;
      return;
    }

    // Kullanici tercihi ustundur
    const anahtar = anahtarCoz(el);
    if (kayitliKonumVarMi(anahtar)) {
      el._acilisYerlesti = true;
      return;
    }

    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return;   // henuz gorunmedi

    const ust = minUst();
    const alanG = window.innerWidth;
    const alanY = window.innerHeight - ust;

    // ---------------------------------------------------------------
    // OLCU: en az 500x400, ancak gorunur alani ASMAZ. Kucuk ekranda
    // (or. dizustu 1366x768 degil, dar pencere) sigdirma yapilir;
    // yoksa pencere ekran disina tasar ve baslik cubugu erisilemez
    // olur -- bolum_resize.js v2.4.52'de ogrenilen ders.
    // ---------------------------------------------------------------
    const hedefG = Math.min(Math.max(r.width, EN_AZ_GENISLIK),
                            alanG - KENAR_PAY * 2);
    const hedefY = Math.min(Math.max(r.height, EN_AZ_YUKSEKLIK),
                            alanY - KENAR_PAY * 2);

    // ---------------------------------------------------------------
    // CSS ORTALAMASI ILE CAKISMAYI ONLE
    // Bazi pencereler `left:50%; transform:translate(-50%,-50%)` ile
    // ortalaniyor. Yalniz left/top yazilirsa transform YERINDE KALIR
    // ve pencere (left - genislik/2) noktasina kayar; 760px genislikte
    // bu 380px sola kayma demektir. Transform mutlaka sifirlanir.
    // ---------------------------------------------------------------
    const cs = getComputedStyle(el);
    if (cs.position !== "fixed" && cs.position !== "absolute") {
      el.style.position = "fixed";
    }
    if (cs.transform && cs.transform !== "none") el.style.transform = "none";
    el.style.right = "auto";
    el.style.bottom = "auto";
    el.style.margin = "0";

    // Olcu yaz. `max-height`/`max-width` kisitlari hedefi kirpabilir;
    // bu yuzden en az olcu ayrica bildirilir.
    if (hedefG > r.width) {
      el.style.width = Math.round(hedefG) + "px";
      el.style.minWidth = Math.round(hedefG) + "px";
      el.style.maxWidth = "none";
    }
    if (hedefY > r.height) {
      el.style.height = Math.round(hedefY) + "px";
      el.style.minHeight = Math.round(hedefY) + "px";
      el.style.maxHeight = "none";
    }

    // Ortala. Yukseklik olcusu yeni yazildiysa gercek olcu bir sonraki
    // cizim cerceve sinde belli olur; hesapta hedef olcu kullanilir.
    const sonG = Math.max(r.width, hedefG);
    const sonY = Math.max(r.height, hedefY);
    const sol = Math.max(KENAR_PAY, Math.round((alanG - sonG) / 2));
    const yuk = Math.max(ust + KENAR_PAY,
                         Math.round(ust + (alanY - sonY) / 2));
    el.style.left = sol + "px";
    el.style.top = yuk + "px";

    el._acilisYerlesti = true;
  }

  // ------------------------------------------------------------------
  // GOZLEMCI: `popup_tasima.js` ile AYNI pencere evrenini kullanir.
  // Kendi pencere listesini tutmaz; yeni bir pencere turu eklendiginde
  // tek kaynak guncellenince burasi da kendiliginden kapsar.
  // ------------------------------------------------------------------
  function secici() {
    return window.PENCERE_SECICI ||
      ".yuzen-panel, .bolum-popup, .gecmis-popup, .ph-popup, .um-popup, " +
      ".ry-popup, .angi-popup, .sg-popup";
  }

  function gorunurMu(el) {
    if (!el.isConnected) return false;
    const cs = getComputedStyle(el);
    return cs.display !== "none" && cs.visibility !== "hidden";
  }

  function tara(kok) {
    if (!kok || kok.nodeType !== 1) return;
    const s = secici();
    if (kok.matches && kok.matches(s) && gorunurMu(kok)) yerlestir(kok);
    if (kok.querySelectorAll) {
      kok.querySelectorAll(s).forEach((el) => {
        if (gorunurMu(el)) yerlestir(el);
      });
    }
  }

  function kur() {
    tara(document.body);
    const obs = new MutationObserver((kayitlar) => {
      for (const k of kayitlar) {
        if (k.type === "childList") {
          k.addedNodes.forEach((n) => tara(n));
        } else if (k.type === "attributes") {
          const el = k.target;
          if (el.nodeType === 1 && el.matches && el.matches(secici())) {
            // Yalniz GIZLI -> GORUNUR gecisinde calis. Gecis takibi
            // olmadan, yerlestirmenin yazdigi `style` yeni bir
            // attribute mutation tetikler ve sonsuz donguye girer --
            // popup_tasima.js'te ayni tuzak yasanmis.
            const g = gorunurMu(el);
            if (g && el._acilisSonGorunur !== true) yerlestir(el);
            el._acilisSonGorunur = g;
          }
        }
      }
    });
    obs.observe(document.body, {
      childList: true, subtree: true,
      attributes: true, attributeFilter: ["style", "class"],
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", kur);
  } else {
    kur();
  }

  // Dis yuzey: elle cagirmak isteyen moduller icin
  window.panelAcilisYerlestir = yerlestir;
})();
