/* =====================================================================
   PENCERE DOK — SEKME BIRLESTIRME / AYIRMA / IKIYE BOLME  (v2.4.24)

   Chrome sekme davranisinin pencere yoneticisi karsiligi:

     1) Bir pencereyi baska pencerenin BASLIGINA surukle  -> sekme olur
        (iki pencere tek kapsayicida, ustte sekme cubugu)
     2) Sekmeyi basligindan disariya surukle              -> tekrar ayrilir
     3) Bir pencereyi digerinin ORTASINA surukle          -> ikiye boler
        (yatay/dikey bolunmus tek pencere, ortada tasinabilir ayirici)

   Tasarim kararlari
   -----------------
   * Mevcut surukleme akisina DOKUNULMAZ. popup_tasima.js surukleme
     sirasinda surukleHareket(), birakinca surukleBitti() cagirir.
     Bu modul yoksa eski davranis aynen surer (guvenli bozunum).
   * Pencerelerin DOM yeri degisir ama kendileri klonlanmaz; icerideki
     canli baglantilar (Cesium, video, WebSocket dinleyicileri, olay
     handler'lari) korunur. Klonlama yapilsaydi video akislari ve
     harita ornekleri kopardi.
   * Kapsayici kapandiginda/son sekme ayrildiginda pencere eski
     stiline (_dokEskiStil) donerek serbest kalir.
   ===================================================================== */
(function () {
  "use strict";

  // ------------------------------------------------------------------
  // AYARLAR
  // ------------------------------------------------------------------
  const BASLIK_BOLGE = 0.34;   // pencere ustunden bu oran = sekme bolgesi
  const KENAR_BOLGE  = 0.30;   // kenarlardan bu oran = bolme bolgesi
  const MIN_HEDEF_W  = 160;    // bundan kucuk pencere hedef sayilmaz
  const MIN_HEDEF_H  = 90;

  // Sekme/bolme hedefi OLMAYACAK pencereler: menuler ve anlik
  // bildirimler. Bunlar sekme haline gelirse kullanilamaz olur.
  const HARIC = new Set(["haritaMenu", "profilMenu", "rotaNoktaPopup",
                         "haritaAramaPopup"]);

  function haricMi(el) {
    if (!el) return true;
    if (el.id && HARIC.has(el.id)) return true;
    if (el.classList.contains("um-toast")) return true;
    return false;
  }

  function pencereSecici() {
    return window.PENCERE_SECICI ||
      ".yuzen-panel, .bolum-popup, .dk-pencere, .kam-pencere";
  }

  function gorunurMu(el) {
    if (!el || !el.isConnected) return false;
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") return false;
    const r = el.getBoundingClientRect();
    return r.width >= MIN_HEDEF_W && r.height >= MIN_HEDEF_H;
  }

  // ------------------------------------------------------------------
  // GOSTERGE (drop indicator) — nereye birakilacagini gosteren mavi alan
  // ------------------------------------------------------------------
  let gosterge = null;

  function gostergeAl() {
    if (gosterge && gosterge.isConnected) return gosterge;
    gosterge = document.createElement("div");
    gosterge.className = "dok-gosterge";
    document.body.appendChild(gosterge);
    return gosterge;
  }

  function gostergeGizle() {
    if (gosterge && gosterge.isConnected) gosterge.style.display = "none";
  }

  function gostergeGoster(r, tur) {
    const g = gostergeAl();
    g.style.display = "block";
    g.className = "dok-gosterge dok-" + tur;
    let x = r.left, y = r.top, w = r.width, h = r.height;
    if (tur === "sekme") { h = Math.max(30, r.height * BASLIK_BOLGE * 0.6); }
    else if (tur === "sol")  { w = r.width / 2; }
    else if (tur === "sag")  { w = r.width / 2; x = r.left + w; }
    else if (tur === "ust")  { h = r.height / 2; }
    else if (tur === "alt")  { h = r.height / 2; y = r.top + h; }
    g.style.left = x + "px";
    g.style.top = y + "px";
    g.style.width = w + "px";
    g.style.height = h + "px";
  }

  // ------------------------------------------------------------------
  // HEDEF BULMA
  // Surukledigimiz pencerenin ALTINDA kalan gecerli pencereyi bulur.
  // elementsFromPoint kullanir; surukledigimiz pencere ve gosterge
  // atlanir. En ustteki (z-index en yuksek) gecerli hedef secilir.
  // ------------------------------------------------------------------
  function hedefBul(suruklenen, x, y) {
    const yiginlar = document.elementsFromPoint(x, y) || [];
    const sec = pencereSecici();
    // Surukledigimiz pencere zaten bir kapsayicida ise O KAPSAYICI hedef
    // olamaz. Aksi halde pencere ayni kapsayiciya ikinci kez eklenir ve
    // "DRONLAR | DRONLAR" gibi cift sekme olusur (olculen v2.4.24 kusuru).
    const kendiKap = (suruklenen && suruklenen._dokKap) ||
                     (suruklenen && suruklenen.closest
                       ? suruklenen.closest(".dok-kapsayici") : null);
    for (const el of yiginlar) {
      if (!el || el === gosterge) continue;
      // Surukledigimiz pencerenin kendisi veya icindeki bir oge ise atla
      if (suruklenen && (el === suruklenen || suruklenen.contains(el))) continue;
      // Kapsayici govdesi ise: onu hedef kabul et (sekme eklenir)
      const kap = el.closest(".dok-kapsayici");
      if (kap && kap !== suruklenen && kap !== kendiKap &&
          !suruklenen.contains(kap)) {
        if (gorunurMu(kap)) return kap;
      }
      const aday = el.closest(sec);
      if (!aday) continue;
      if (aday === suruklenen || suruklenen.contains(aday)) continue;
      if (haricMi(aday)) continue;
      if (!gorunurMu(aday)) continue;
      // Baska bir kapsayicinin icindeki sekme govdesi ise kapsayiciyi al
      const ustKap = aday.closest(".dok-kapsayici");
      // v2.4.25 DUZELTME: eskiden `if (ustKap === kendiKap) continue;`
      // yaziliydi. Iki serbest pencere sürüklendiğinde ikisi de
      // kapsayici DISINDA oldugu icin `ustKap` ve `kendiKap` degerleri
      // null'dir; `null === null` dogru olur ve GECERLI hedef atlanir.
      // Olcum: hedefBul() daima null donuyordu, bu yuzden hicbir
      // pencere birbirine sekme olarak eklenemiyordu (kullanicinin
      // "bazi pencereler birbiri icine hic gecmiyor" sikayeti).
      // Dogru kural: yalnizca GERCEK bir kapsayici, sürüklenenin
      // kendi kapsayicisiyla ayni ise atlanir.
      if (ustKap && kendiKap && ustKap === kendiKap) continue;
      if (ustKap && ustKap !== suruklenen) return ustKap;
      return aday;
    }
    return null;
  }

  // Birakma noktasinin hedef icindeki bolgesini belirler
  function bolgeBul(hedef, x, y) {
    const r = hedef.getBoundingClientRect();
    const bx = (x - r.left) / r.width;   // 0..1
    const by = (y - r.top) / r.height;   // 0..1
    // Ust bant = sekme birlestirme
    if (by <= BASLIK_BOLGE) return "sekme";
    // Kenarlar = bolme
    if (bx <= KENAR_BOLGE) return "sol";
    if (bx >= 1 - KENAR_BOLGE) return "sag";
    if (by >= 1 - KENAR_BOLGE) return "alt";
    // Merkez = kullanicinin istedigi "ortaya birakinca ikiye bol"
    return "orta";
  }

  // ------------------------------------------------------------------
  // PENCERE BASLIGI / AD OKUMA
  //
  // v2.4.25: TEK KAYNAK. Onceden bu liste `pencere_dok.js` (10 sinif)
  // ve `popup_tasima.js` (4 sinif) icinde AYRI AYRI tutuluyordu.
  // Uyusmazligin sonucu: dok modulu `.yuzen-baslik`'i taniyor ama
  // surukleme modulu tanimadigi icin o pencereler dok sistemine hic
  // giremiyordu. Iki yerde liste tutmak ayni hatayi tekrar uretir;
  // bu yuzden `window.PENCERE_BASLIK_SECICI` tek dogruluk kaynagidir.
  //
  // NOT: CSS'te 43 farkli `*baslik*` sinifi var; buraya YALNIZCA
  // gercek pencere basligi olanlar girer. Panel ici bolum basliklari
  // (`.alt-baslik`, `.fs-grup-baslik`, `.rp-bolum-baslik`,
  // `.ang-liste-baslik` vb.) surukleme tutamagi DEGILDIR.
  // ------------------------------------------------------------------
  // Sinif secimi KAYNAK OLCUMUNE dayanir. Cogu pencere basligini
  // `"<ozel>-baslik popup-baslik"` seklinde IKI sinifla kurar
  // (angajman_izle.js:54, suru.js:42, serbest_form.js:273,
  // pilot_hakkinda.js:51, bolum_popup.js:55). Bunlar `.popup-baslik`
  // tarafindan zaten kapsanir; ayri giris GEREKSIZDIR.
  // Buraya yalnizca `.popup-baslik` KULLANMAYAN basliklar girer.
  const BASLIK_SECICI = [
    ".popup-baslik",           // ortak temel (v2.4.24 tek tasarim);
                               // angi/suru/sf/ph/bolum-popup dahil
    ".yuzen-baslik",           // arayuz.js:165 — BAGLANTI YONETICISI,
                               // RADAR, HAKKINDA (ayri tasima modulu)
    ".dk-pp-baslik",           // dron kart param popup
    ".dk-mp-baslik",           // dron kart mini popup;
                               // ARM CHECK (arm_check.js:90) ve
                               // DRON HISTORY (gecmis.js:37) bunu kullanir
    ".modal-baslik",           // perde (overlay) modallari
    ".kam-oniz-baslik",        // kamera_harita.js:158
    ".kam-pencere-baslik",     // kameralar.js:556, dron_kamera.js:184
    ".vd-baslik",              // video_duvar.js:266
    ".sg-baslik",              // surum_gecmisi.js:52
  ].join(", ");
  // DISLANANLAR (olcumle dogrulandi — pencere basligi DEGIL):
  //   .dron-kart-baslik  -> hedefler.js:445 acilir/kapanir kart basligi
  //   .ry-grup-baslik    -> rol_yonetimi.js:201 liste grup basligi
  //   .hk-baslik         -> index.html:298 "Gelistirici Ekip" metni
  //   .alt-baslik, .fs-grup-baslik, .rp-bolum-baslik, .ang-liste-baslik
  // Bunlar eklenirse panel ici basliga tiklayinca pencere suruklenir.
  window.PENCERE_BASLIK_SECICI = BASLIK_SECICI;

  function baslikElBul(pop) {
    return pop.querySelector(BASLIK_SECICI);
  }

  function adOku(pop) {
    const b = baslikElBul(pop);
    if (b) {
      const ad = b.querySelector(
        ".bolum-popup-ad, .tb-baslik, span");
      let t = (ad ? ad.textContent : b.textContent) || "";
      t = t.replace(/\s+/g, " ").trim();
      if (t) return t.slice(0, 40);
    }
    return pop.id || "PENCERE";
  }

  function ikonOku(pop) {
    const b = baslikElBul(pop);
    const i = b ? b.querySelector("i.fa-solid, i.fa-regular, i[class*='fa-']") : null;
    return i ? i.className : "";
  }

  // ------------------------------------------------------------------
  // STIL YEDEKLEME / GERI YUKLEME
  // Pencere kapsayiciya girerken konum stilleri sifirlanir; ayrilinca
  // eski haline doner. Boylece serbest pencere davranisi korunur.
  // ------------------------------------------------------------------
  const YEDEK_ALAN = ["position", "left", "top", "right", "bottom",
                      "width", "height", "maxWidth", "maxHeight",
                      "zIndex", "margin", "transform", "flex", "display",
                      "flexDirection", "overflow", "overflowY", "minWidth",
                      "minHeight", "borderRadius", "border", "boxShadow"];

  function stilYedekle(pop) {
    if (pop._dokEskiStil) return;
    const y = {};
    YEDEK_ALAN.forEach(a => { y[a] = pop.style[a] || ""; });
    pop._dokEskiStil = y;
  }

  function stilGeriYukle(pop) {
    const y = pop._dokEskiStil;
    if (!y) return;
    // v2.4.28 - important olarak yazilan z-index'i ONCE kaldir.
    // icerideStil() z-index'i setProperty(...,"important") ile
    // sabitler; duz atama (pop.style.zIndex = ...) important bir
    // bildirimi EZEMEZ. Temizlenmezse serbest kalan pencere bir daha
    // one getirilemez (enUsteGetir yazdigi deger etkisiz kalir).
    pop.style.removeProperty("z-index");
    YEDEK_ALAN.forEach(a => { pop.style[a] = y[a]; });
    delete pop._dokEskiStil;
  }

  // Kapsayici icinde pencere: konumdan bagimsiz, alani doldurur.
  //
  // flexDirection MUTLAKA "column" olmalidir. Aksi halde (tarayici
  // varsayilani "row") baslik ile govde YAN YANA dizilir ve baslik
  // satirin tum yuksekligine gerilir; olculen ornek: 380px baslik.
  // Ayrica pencerenin kendi cercevesi/golgesi gozenek icinde
  // gereksizdir - kapsayici zaten cerceve tasir.
  function icerideStil(pop) {
    pop.style.position = "relative";
    pop.style.left = "auto";
    pop.style.top = "auto";
    pop.style.right = "auto";
    pop.style.bottom = "auto";
    pop.style.width = "100%";
    pop.style.height = "100%";
    pop.style.maxWidth = "none";
    pop.style.maxHeight = "none";
    pop.style.minWidth = "0";
    pop.style.minHeight = "0";
    pop.style.margin = "0";
    pop.style.transform = "none";
    // v2.4.28 - z-index YARISI KAPATILIR (olculen kusur)
    //
    // popup_tasima.js:enUsteGetir her pointerdown'da panele artan bir
    // z-index yazar (enUsteKur capture asamasinda bagli). Panel bir
    // kapsayici icine alindiktan sonra da bu isleyici calismaya devam
    // ediyordu. Olcum (v2.4.27, tarayici):
    //
    //   panel   z-index = 1213   <- enUsteGetir yazdi
    //   tutamac z-index = 5      <- CSS sabiti
    //   elementFromPoint(tutamac merkezi) -> .sabit-icerik (panel icerigi)
    //   erisilebilir: false
    //
    // kap ve .dok-govde z-index:auto oldugu icin yigin baglami
    // olusturmuyor; panel ile tutamac AYNI baglamda karsilastiriliyor
    // ve 1213 > 5 oldugu icin panel tutamacin ustune biniyor. Sonuc:
    // birlesmis pencere fare ile boyutlandirilamiyor.
    //
    // Duz atama (pop.style.zIndex = "auto") yetmez; enUsteGetir bir
    // sonraki tiklamada yeniden sayisal deger yazar. Bu yuzden
    // important ile sabitlenir, ayrica enUsteGetir kapsayici icindeki
    // panelleri atlar (bkz. popup_tasima.js) ve .dok-govde kendi yigin
    // baglamini olusturur (bkz. pencere_dok.css).
    pop.style.setProperty("z-index", "auto", "important");
    pop.style.display = "flex";
    pop.style.flexDirection = "column";
    pop.style.overflow = "hidden";
    // Gozenek icinde cift cerceve/golge olmasin
    pop.style.border = "none";
    pop.style.borderRadius = "0";
    pop.style.boxShadow = "none";
  }

  // ------------------------------------------------------------------
  // KAPSAYICI OLUSTURMA
  // ------------------------------------------------------------------
  let kapSayac = 0;

  // v2.4.28 (D5): Kapsayici kimlikleri OTURUMA OZELDIR.
  //
  // `kapSayac` modul ici bir degiskendir ve sayfa her yenilendiginde
  // sifirdan baslar. Onceden kapsayici kimligi (`dokKap_1` gibi)
  // dogrudan kalici depo anahtari olarak kullaniliyordu:
  //
  //     popupBoyutlandirilabilirYap(kap, "dok_" + kap.id);
  //     popupTasinabilirYap(kap, cubuk, "dok_" + kap.id);
  //
  // `boyutlandirilabilirYap` kurulum sonunda kayitli boyutu geri
  // yukledigi icin, YENI oturumun ilk kapsayicisi ONCEKI oturumda
  // tamamen farkli panellerden olusmus `dokKap_1`'in boyutunu ve
  // konumunu miras aliyordu. Olculen sonuc: paneller 440x360 iken
  // olusan kapsayici 1280x1100@41,137 (depodan gelen deger) — yani
  // birlesmis pencere tam ekran aciliyordu.
  //
  // Cozum: kapsayicilar gecici nesnelerdir, kalici boyut/konum
  // hatirlamasi yapilmaz. Tasima ve boyutlandirma calisir, yalnizca
  // depoya yazilmaz (anahtar `null`).
  const KAP_ANAHTAR = null;

  // Onceki surumlerin depoda biraktigi `dok_dokKap_*` artiklarini
  // temizle; aksi halde mevcut kurulumlarda hatali boyut surmeye
  // devam eder (kullanici tarafinda gorulen belirti).
  (function dokArtiklariTemizle() {
    try {
      const ham = localStorage.getItem("gcs_pencere_konum");
      if (!ham) return;
      const d = JSON.parse(ham) || {};
      let degisti = false;
      Object.keys(d).forEach((k) => {
        if (k.indexOf("dok_dokKap_") === 0) { delete d[k]; degisti = true; }
      });
      if (degisti) {
        localStorage.setItem("gcs_pencere_konum", JSON.stringify(d));
      }
    } catch (e) { /* depo erisilemezse sessiz gec */ }
  })();

  function kapsayiciOlustur(r) {
    const kap = document.createElement("div");
    kap.className = "dok-kapsayici";
    kap.id = "dokKap_" + (++kapSayac);
    kap.style.position = "fixed";
    kap.style.left = Math.max(0, r.left) + "px";
    const minT = (typeof window.pencereMinTop === "function")
      ? window.pencereMinTop() : 48;
    kap.style.top = Math.max(minT, r.top) + "px";
    kap.style.width = Math.max(320, r.width) + "px";
    kap.style.height = Math.max(200, r.height) + "px";
    document.body.appendChild(kap);
    if (typeof window.pencereEnUsteKur === "function") {
      window.pencereEnUsteKur(kap);
    }
    if (typeof window.pencereEnUsteGetir === "function") {
      window.pencereEnUsteGetir(kap);
    }
    return kap;
  }

  // ==================================================================
  // SEKME KAPSAYICISI
  // ==================================================================
  function sekmeKapsayiciKur(kap) {
    if (kap._sekmeKuruldu) return;
    kap._sekmeKuruldu = true;
    kap.classList.add("dok-sekmeli");

    const cubuk = document.createElement("div");
    cubuk.className = "dok-sekme-cubuk";
    kap.appendChild(cubuk);

    const govde = document.createElement("div");
    govde.className = "dok-govde";
    kap.appendChild(govde);

    // Kapsayici basligindan (bos alanindan) tasinabilir olsun
    if (typeof window.popupTasinabilirYap === "function") {
      window.popupTasinabilirYap(kap, cubuk, KAP_ANAHTAR);
    }
    // Sag-alt tutamac ile boyutlandirilabilir
    if (typeof window.popupBoyutlandirilabilirYap === "function") {
      window.popupBoyutlandirilabilirYap(kap, KAP_ANAHTAR);
    }
    kap._cubuk = cubuk;
    kap._govde = govde;
    kap._sekmeler = [];
  }

  // ==================================================================
  // ONCEKI KAPSAYICIDAN AYIRMA (v2.4.27)
  //
  // ## Olculen kusur
  //
  // Bir panel bir kapsayicidan digerine tasindiginda ESKI kapsayicinin
  // uye listeleri temizlenmiyordu. Olcum (v2.4.26, tarayici):
  //
  //   bolmeOlustur(A,B) -> surukleBitti(B, C.baslik)
  //     dokKap_3._bolme.uyeler = [dronlar, ROTALAR]   <- hayalet uye
  //     rotalar._dokBolme      = dokKap_3             <- silinmemis
  //     rotalar.parentElement  = dok-govde (dokKap_4) <- DOM'da tasinmis
  //
  //   surukleBitti(B, A.baslik) -> surukleBitti(B, C.orta)
  //     dokKap_5._sekmeler     = [dronlar, ROTALAR]   <- hayalet uye
  //     dokKap_5 DOM sekmeleri = [DRONLAR, ROTALAR]   <- sahipsiz etiket
  //     rotalar._dokKap        = dokKap_5             <- silinmemis
  //
  // Sonuclari (kullanicinin videoda gosterdigi davranislar):
  //   * ayni sekme iki kez gorunuyor        (hayalet uye + sahipsiz etiket)
  //   * ayrilan pencerenin ici bos geliyor  (eski gozenek bos kaliyor)
  //   * panel tasinmiyor, klonlanmis gibi   (bolmeCoz hayalet uyeyi geri
  //                                          koymaya calisip paneli yeni
  //                                          kapsayicisindan koparıyor)
  //   * sekmeye tiklayinca icerik kayboluyor (eski kapsayicinin
  //                                           sekmeAktifEt cagrisi
  //                                           bolmedeki panele display:none)
  //
  // Bu fonksiyon TEK giris noktasidir: bir panel yeni bir kapsayiciya
  // alinmadan once HER ZAMAN buradan gecirilir. Iki ayri yerde
  // (sekmeEkle ve bolmeOlustur) ayri temizlik mantigi tutmak ayni
  // kusuru tekrar uretir.
  // ==================================================================
  function oncekindenAyir(pop, yeniKap) {
    if (!pop) return;

    // --- 1) Sekmeli kapsayici uyeligi ---
    const eskiKap = pop._dokKap;
    if (eskiKap && eskiKap !== yeniKap) {
      if (eskiKap._sekmeler) {
        const i = eskiKap._sekmeler.indexOf(pop);
        if (i >= 0) eskiKap._sekmeler.splice(i, 1);
      }
      // Sekme etiketini kaldir
      sekmeEtiketiTemizle(eskiKap, pop);
      delete pop._dokKap;
      // Geride kalanlari duzenle: tek sekme kaldiysa coz, hic kalmadiysa
      // kapsayiciyi kaldir. (Aksi halde bos govde ekranda kalir.)
      try { cikarmaSonrasiDenetim(eskiKap); } catch (e) {}
    } else if (eskiKap === yeniKap) {
      // Ayni kapsayici: yalnizca dizi/etiket tekrarini onle
      if (eskiKap._sekmeler) {
        const i = eskiKap._sekmeler.indexOf(pop);
        if (i >= 0) eskiKap._sekmeler.splice(i, 1);
      }
      sekmeEtiketiTemizle(eskiKap, pop);
      delete pop._dokKap;
    }

    // --- 2) Bolunmus kapsayici uyeligi ---
    const eskiBolme = pop._dokBolme;
    if (eskiBolme && eskiBolme !== yeniKap) {
      const b = eskiBolme._bolme;
      if (b && b.uyeler) {
        const i = b.uyeler.indexOf(pop);
        if (i >= 0) b.uyeler.splice(i, 1);
      }
      delete pop._dokBolme;
      // Bolmede tek uye kaldiysa bolmeyi coz: kalan panel serbest kalir.
      // Hic uye kalmadiysa kapsayiciyi kaldir.
      try { bolmeSonrasiDenetim(eskiBolme); } catch (e) {}
    } else if (eskiBolme === yeniKap) {
      const b = eskiBolme._bolme;
      if (b && b.uyeler) {
        const i = b.uyeler.indexOf(pop);
        if (i >= 0) b.uyeler.splice(i, 1);
      }
      delete pop._dokBolme;
    }

    // --- 3) Sahipsiz kalmis sekme etiketi (referanssiz) ---
    if (pop._dokSekme) {
      try { pop._dokSekme.remove(); } catch (e) {}
      delete pop._dokSekme;
    }
  }

  // Bir panele ait sekme etiketini kapsayici cubugunda TARAYARAK bulur ve
  // kaldirir. `pop._dokSekme` referansina guvenilmez: referans uzerine
  // yazildiginda DOM'daki eski etiket sahipsiz kalir ve cubukta gorunmeye
  // devam eder (olculen "cift sekme" kusuru).
  function sekmeEtiketiTemizle(kap, pop) {
    if (!kap) return;
    if (pop && pop._dokSekme) {
      try { pop._dokSekme.remove(); } catch (e) {}
      delete pop._dokSekme;
    }
    const cubuk = kap._cubuk || kap.querySelector(":scope > .dok-sekme-cubuk");
    if (!cubuk) return;
    cubuk.querySelectorAll(".dok-sekme").forEach(s => {
      // Sahibi bu panel olan VEYA sahibi artik bu kapsayicida olmayan
      // etiketleri kaldir.
      const sahip = s._dokPop;
      if (!sahip || sahip === pop ||
          !sahip.isConnected ||
          (kap._sekmeler && kap._sekmeler.indexOf(sahip) < 0)) {
        try { s.remove(); } catch (e) {}
      }
    });
  }

  // Bolunmus kapsayicida uye sayisi azaldiktan sonra cagrilir.
  function bolmeSonrasiDenetim(kap) {
    const b = kap && kap._bolme;
    if (!b) { if (kap) kap.remove(); return; }
    if (b.uyeler.length >= 2) return;
    if (b.uyeler.length === 1) {
      // Kalan tek paneli serbest birak, kapsayiciyi kaldir
      bolmeCoz(kap);
    } else {
      kap.remove();
    }
  }

  function sekmeEkle(kap, pop, aktifYap) {
    sekmeKapsayiciKur(kap);

    // ---- CIFTE EKLEME KORUMASI (v2.4.25 / v2.4.27) ----
    // Olculen kusur: ayni pencere iki kez sekme olarak eklenebiliyordu
    // ("DRONLAR | DRONLAR") ve eski sekme etiketi sahipsiz kalarak bos
    // kalinti uretiyordu (_dokSekme uzerine yazildigi icin).
    if (pop === kap) return null;              // kapsayici kendine eklenemez
    if (kap._sekmeler.indexOf(pop) >= 0) {     // zaten bu kapsayicida
      if (aktifYap !== false) sekmeAktifEt(kap, pop);
      return pop._dokSekme || null;
    }
    // v2.4.27: TEK temizlik yolu. Onceden yalnizca `_dokKap` (sekmeli)
    // yolu ele aliniyordu; `_dokBolme` (bolunmus) yolu hic temizlenmedigi
    // icin panel iki kapsayiciya ait sayiliyordu.
    oncekindenAyir(pop, kap);

    stilYedekle(pop);

    const sekme = document.createElement("div");
    sekme.className = "dok-sekme";
    const ik = ikonOku(pop);
    sekme.innerHTML =
      (ik ? "<i class='" + ik + "'></i>" : "") +
      "<span class='dok-sekme-ad'></span>" +
      "<button class='dok-sekme-kapat' title='Kapat'>" +
      "<i class='fa-solid fa-xmark'></i></button>";
    sekme.querySelector(".dok-sekme-ad").textContent = adOku(pop);

    kap._cubuk.appendChild(sekme);
    kap._govde.appendChild(pop);
    icerideStil(pop);

    pop._dokKap = kap;
    pop._dokSekme = sekme;
    sekme._dokPop = pop;
    kap._sekmeler.push(pop);

    // Pencerenin kendi baslik cubugu sekme icinde gereksiz: gizle.
    // (sekme cubugu artik baslik islevini goruyor)
    kendiBaslikGizle(pop);
    // v2.4.27: kendi boyut tutamaci da gizlenir; aksi halde govdenin
    // sag-alt kosesinde ikinci bir tutamac gorunur.
    kendiTutamacGizle(pop);

    // Sekmeye tiklayinca aktif et.
    // NOT: "click" olayina GUVENILMEZ. sekmeSuruklemeKur() ayni sekme
    // uzerinde setPointerCapture cagirdiginda tarayici "click" uretmeyi
    // birakir (pointerdown/pointerup ayni capture'siz hedefte olmali).
    // Bu yuzden aktif etme dogrudan pointerup ile yapilir; ayirma esigi
    // asilmamissa (bas.ayrildi === false) tiklama sayilir.
    sekme.addEventListener("pointerup", (ev) => {
      if (ev.target.closest(".dok-sekme-kapat")) return;
      if (sekme._dokAyrildi) return; // surukleyip ayirma yapildi
      sekmeAktifEt(kap, pop);
    });
    // Klavye erisilebilirligi ve yedek yol olarak click de baglanir
    sekme.addEventListener("click", (ev) => {
      if (ev.target.closest(".dok-sekme-kapat")) return;
      sekmeAktifEt(kap, pop);
    });

    // Sekme kapat
    // Kapat dugmesi: pointerup ile (click uretilmeyebilir)
    sekme.querySelector(".dok-sekme-kapat")
      .addEventListener("pointerup", (ev) => {
        ev.stopPropagation();
        ev.preventDefault();
        sekmeKapat(kap, pop);
      });

    // Sekmeyi surukleyip disariya cikarma (Chrome tarzi ayirma)
    sekmeSuruklemeKur(kap, sekme, pop);

    if (aktifYap !== false) sekmeAktifEt(kap, pop);
    // NOT: burada cikarmaSonrasiDenetim CAGRILMAZ. O fonksiyon "tek sekme
    // kaldiysa kapsayiciyi coz" mantigi tasir; ekleme sirasinda ilk
    // pencere eklendiginde sayi 1 olur ve kapsayici ikinci pencere
    // gelmeden kendini yok eder. Cozme denetimi yalnizca CIKARMA
    // yolunda (sekmeCikar) yapilir.
    return sekme;
  }

  function sekmeAktifEt(kap, pop) {
    kap._sekmeler.forEach(p => {
      const aktif = (p === pop);
      p.style.display = aktif ? "flex" : "none";
      if (p._dokSekme) p._dokSekme.classList.toggle("aktif", aktif);
    });
    kap._aktif = pop;
  }

  // Yalnizca sekme CIKARILDIKTAN sonra cagrilir: tek sekme kaldiysa
  // kapsayiciyi coz, hic kalmadiysa kapsayiciyi kaldir (Chrome davranisi).
  function cikarmaSonrasiDenetim(kap) {
    if (!kap._sekmeler) { kap.remove(); return; }
    if (kap._sekmeler.length === 1) {
      kapsayiciCoz(kap);
    } else if (kap._sekmeler.length === 0) {
      kap.remove();
    }
  }

  function sekmeCikar(kap, pop, konumla) {
    const i = kap._sekmeler.indexOf(pop);
    if (i < 0) return;
    kap._sekmeler.splice(i, 1);
    // v2.4.27: referansa ek olarak cubugu da tara (sahipsiz etiket kalmasin)
    sekmeEtiketiTemizle(kap, pop);
    delete pop._dokKap;

    // Kendi baslik cubugunu ve boyut tutamacini geri getir
    kendiBaslikGoster(pop);
    kendiTutamacGoster(pop);

    document.body.appendChild(pop);
    stilGeriYukle(pop);
    pop.style.display = "flex";
    if (konumla) {
      pop.style.position = "fixed";
      pop.style.left = konumla.x + "px";
      pop.style.top = konumla.y + "px";
      pop.style.right = "auto";
      pop.style.bottom = "auto";
      pop.style.margin = "0";
      pop.style.transform = "none";
      if (!pop.style.width || pop.style.width === "100%") {
        pop.style.width = Math.max(300, konumla.w || 340) + "px";
      }
      if (pop.style.height === "100%") pop.style.height = "";
    }
    if (typeof window.pencereEnUsteGetir === "function") {
      window.pencereEnUsteGetir(pop);
    }
    if (typeof window.pencereMinTopUygula === "function") {
      window.pencereMinTopUygula(pop);
    }

    // Kalan sekmelerden birini aktif et
    if (kap._sekmeler.length) {
      sekmeAktifEt(kap, kap._sekmeler[Math.max(0, i - 1)]);
    }
    cikarmaSonrasiDenetim(kap);
  }

  function sekmeKapat(kap, pop) {
    // Pencerenin kendi kapatma dugmesini bulup tetikle: modulun
    // kendi temizlik mantigi (WebSocket kapatma, timer temizleme)
    // calissin. Bulunamazsa pencere gizlenir.
    const kapatBtn = (function () {
      const bas = baslikElBul(pop);
      if (!bas) return null;
      return bas.querySelector("button[class*='kapat'], button");
    })();
    sekmeCikar(kap, pop, null);
    if (kapatBtn) {
      kapatBtn.click();
    } else {
      pop.style.display = "none";
    }
  }

  // Son sekme kaldiginda kapsayiciyi coz, pencereyi serbest birak
  function kapsayiciCoz(kap) {
    if (!kap) return;
    // v2.4.28 - BOLME KAPSAYICISINDA PANEL KAYBI ONLENIR
    //
    // Bu islev yalnizca SEKMELI kapsayici icin yazilmisti; uyeleri
    // `kap._sekmeler` uzerinden okur. Bolunmus bir kapsayicida bu alan
    // TANIMSIZDIR (uyeler `kap._bolme.uyeler` icinde tutulur), bu yuzden:
    //
    //   kalan = []            -> hicbir panel serbest birakilmaz
    //   kap.remove()          -> gozeneklerdeki TUM paneller DOM'dan kopar
    //   p._dokBolme silinmez  -> paneller kaldirilmis kapsayiciya bagli kalir
    //
    // Olcum (v2.4.28 gerileme testi, tarayici):
    //   kapsayiciCoz(dokKap_9)  ->  bolumPopup_rotalar.isConnected = false
    //                               rotalar._dokBolme = dokKap_9 (silinmemis)
    //
    // Bolme uyelerini serbest birakan dogru islev `bolmeCoz`'dur; is
    // ona devredilir.
    if (kap._bolme) { bolmeCoz(kap); return; }
    const kalan = kap._sekmeler ? kap._sekmeler.slice() : [];
    const r = kap.getBoundingClientRect();
    kalan.forEach(p => {
      sekmeEtiketiTemizle(kap, p);
      delete p._dokKap;
      kendiBaslikGoster(p);
      kendiTutamacGoster(p);
      document.body.appendChild(p);
      stilGeriYukle(p);
      p.style.display = "flex";
      p.style.position = "fixed";
      p.style.left = r.left + "px";
      p.style.top = r.top + "px";
      p.style.width = r.width + "px";
      p.style.height = r.height + "px";
      p.style.margin = "0";
      p.style.transform = "none";
      if (typeof window.pencereMinTopUygula === "function") {
        window.pencereMinTopUygula(p);
      }
    });
    kap._sekmeler = [];
    kap.remove();
  }

  // ------------------------------------------------------------------
  // SEKME SURUKLEME (Chrome tarzi ayirma)
  // Sekme etiketini asagi/yukari belirli mesafe surukleyince pencere
  // kapsayicidan ayrilir ve serbest pencere olarak imlece yapisir.
  // ------------------------------------------------------------------
  const AYIRMA_ESIGI = 26; // px

  function sekmeSuruklemeKur(kap, sekme, pop) {
    let bas = null;

    sekme.addEventListener("pointerdown", (ev) => {
      if (ev.target.closest(".dok-sekme-kapat")) return;
      bas = { x: ev.clientX, y: ev.clientY, ayrildi: false };
      sekme._dokAyrildi = false;
      // NOT: setPointerCapture BURADA CAGRILMAZ. Capture alinirsa tarayici
      // "click" olayi uretmeyi birakir ve sekmeye tiklayip sekme
      // degistirmek imkansiz hale gelir (olculdu: v2.4.24 kusuru).
      // Capture yalnizca ayirma esigi asildiginda alinir.
    });

    sekme.addEventListener("pointermove", (ev) => {
      if (!bas) return;
      const dx = ev.clientX - bas.x;
      const dy = ev.clientY - bas.y;
      if (!bas.ayrildi && Math.hypot(dx, dy) > AYIRMA_ESIGI) {
        bas.ayrildi = true;
        sekme._dokAyrildi = true; // pointerup'ta sekme aktif etmeyi engelle
        try { sekme.setPointerCapture(ev.pointerId); } catch (e) {}
        const r = kap.getBoundingClientRect();
        // Pencereyi ayir ve imlecin altina yerlestir
        sekmeCikar(kap, pop, {
          x: ev.clientX - 60,
          y: Math.max(0, ev.clientY - 14),
          w: r.width,
        });
        // Ayrildiktan sonra pencereyi imlece bagli tasimaya devam et
        serbestTasimaBaslat(pop, ev, 60, 14);
        bas = null;
      }
    });

    const birak = (ev) => {
      if (!bas) return;
      bas = null;
      try { sekme.releasePointerCapture(ev.pointerId); } catch (e) {}
    };
    sekme.addEventListener("pointerup", birak);
    sekme.addEventListener("pointercancel", birak);
  }

  // Ayrilan pencereyi imlec birakilana kadar tasimaya devam et
  function serbestTasimaBaslat(pop, ev0, ofsX, ofsY) {
    const minT = (typeof window.pencereMinTop === "function")
      ? window.pencereMinTop() : 48;

    function hareket(ev) {
      let x = ev.clientX - ofsX;
      let y = ev.clientY - ofsY;
      x = Math.max(0, Math.min(x, window.innerWidth - 120));
      y = Math.max(minT, Math.min(y, window.innerHeight - 36));
      pop.style.left = x + "px";
      pop.style.top = y + "px";
      surukleHareket(pop, ev.clientX, ev.clientY);
    }
    function bitti(ev) {
      document.removeEventListener("pointermove", hareket, true);
      document.removeEventListener("pointerup", bitti, true);
      document.removeEventListener("pointercancel", bitti, true);
      surukleBitti(pop, ev.clientX, ev.clientY);
    }
    document.addEventListener("pointermove", hareket, true);
    document.addEventListener("pointerup", bitti, true);
    document.addEventListener("pointercancel", bitti, true);
  }

  // ==================================================================
  // BOLME (SPLIT) KAPSAYICISI
  // ==================================================================
  function bolmeOlustur(hedef, yeni, yon) {
    // yon: "sol" | "sag" | "ust" | "alt" | "orta"
    // "orta" -> dikey bolme (yan yana), kullanicinin bekledigi davranis
    const yatay = (yon === "ust" || yon === "alt");
    const r = hedef.getBoundingClientRect();

    const kap = kapsayiciOlustur(r);
    kap.classList.add("dok-bolmeli");
    kap.classList.add(yatay ? "dok-yatay" : "dok-dikey");

    // Acik g1/g2 siniflari: CSS grid yerlesimi bunlara dayanir.
    // (nth-of-type kullanilmaz; baslik ilk cocuk oldugu icin sayim kayar)
    const g1 = document.createElement("div");
    g1.className = "dok-gozeneki dok-g1";
    const ayirici = document.createElement("div");
    ayirici.className = "dok-ayirici";
    const g2 = document.createElement("div");
    g2.className = "dok-gozeneki dok-g2";

    kap.appendChild(g1);
    kap.appendChild(ayirici);
    kap.appendChild(g2);

    // Sira: "sol"/"ust" -> yeni pencere basta
    const basta = (yon === "sol" || yon === "ust");
    stilYedekle(hedef);
    stilYedekle(yeni);

    // v2.4.27: Her iki uyeyi de ONCEKI kapsayicisindan duzgunce cikar.
    // Onceden bu yapilmiyordu; hedef zaten sekmeli/bolunmus bir
    // kapsayicidaysa eski kapsayicinin `_sekmeler` / `_bolme.uyeler`
    // listesi paneli icermeye devam ediyordu (hayalet uye).
    oncekindenAyir(hedef, kap);
    oncekindenAyir(yeni, kap);

    if (basta) { g1.appendChild(yeni); g2.appendChild(hedef); }
    else       { g1.appendChild(hedef); g2.appendChild(yeni); }

    [hedef, yeni].forEach(p => {
      icerideStil(p);
      p._dokBolme = kap;
      // v2.4.27: Panelin kendi basligi ve boyut tutamaci gozenek icinde
      // gereksizdir. Onceden yalnizca `sekmeEkle` yolunda gizleniyordu;
      // bolme yolunda gizlenmedigi icin kapsayici basligi + iki panel
      // basligi = UC baslik satiri olusuyordu (olculen kusur).
      kendiBaslikGizle(p);
      kendiTutamacGizle(p);
    });

    kap._bolme = { g1, g2, ayirici, yatay, uyeler: [hedef, yeni] };
    ayiriciKur(kap);

    // Bolunmus pencereye baslik cubugu ekle (tasima + kapatma)
    bolmeBaslikEkle(kap);

    if (typeof window.popupBoyutlandirilabilirYap === "function") {
      window.popupBoyutlandirilabilirYap(kap, KAP_ANAHTAR);
    }
    return kap;
  }

  // ------------------------------------------------------------------
  // KAPSAYICI ICINDEKI PANELIN KENDI BASLIGI / TUTAMACI (v2.4.27)
  //
  // Kapsayici kendi baslik cubugunu (sekme cubugu veya bolme basligi) ve
  // kendi sag-alt boyut tutamacini tasir. Icerideki panellerin kendi
  // baslik ve tutamaclari:
  //   * baslik  -> ayni metni iki kez gosterir ("cift baslik" kusuru)
  //   * tutamac -> `position:absolute; right:0; bottom:0` oldugu icin
  //                gozenegin sag-alt kosesinde, yani kapsayicinin
  //                ORTASINDA havada duran bir tutamac olarak gorunur
  //                (olcum: dokKap_6 icinde 3 tutamac)
  // Ikisi de gizlenir; panel ayrildiginda geri getirilir.
  // ------------------------------------------------------------------
  function kendiBaslikGizle(pop) {
    const bas = baslikElBul(pop);
    if (!bas) return;
    if (pop._dokBasEskiDisplay === undefined) {
      pop._dokBasEskiDisplay = bas.style.display || "";
    }
    bas.style.display = "none";
  }

  function kendiBaslikGoster(pop) {
    const bas = baslikElBul(pop);
    if (bas) bas.style.display = pop._dokBasEskiDisplay || "";
    delete pop._dokBasEskiDisplay;
  }

  function kendiTutamacGizle(pop) {
    const tutlar = pop.querySelectorAll(":scope > .popup-boyut-tutamac");
    if (!tutlar.length) return;
    pop._dokTutEski = [];
    tutlar.forEach(t => {
      pop._dokTutEski.push(t.style.display || "");
      t.style.display = "none";
    });
  }

  function kendiTutamacGoster(pop) {
    const tutlar = pop.querySelectorAll(":scope > .popup-boyut-tutamac");
    const eski = pop._dokTutEski || [];
    tutlar.forEach((t, i) => { t.style.display = eski[i] || ""; });
    delete pop._dokTutEski;
  }

  function bolmeBaslikEkle(kap) {
    const bas = document.createElement("div");
    bas.className = "dok-bolme-baslik popup-baslik";
    bas.innerHTML =
      "<span><i class='fa-solid fa-table-columns'></i>" +
      " <span class='dok-bolme-ad'></span></span>" +
      "<button class='dok-bolme-coz' title='Bolmeyi coz'>" +
      "<i class='fa-solid fa-object-ungroup'></i></button>";
    kap.insertBefore(bas, kap.firstChild);
    kap._baslik = bas;
    // v2.4.27: sabit "BOLUNMUS PENCERE" metni yerine panel adlari.
    // Panellerin kendi basliklari artik gizlendigi icin hangi paneller
    // bolunmus oldugu YALNIZCA buradan anlasilir.
    bolmeAdYenile(kap);

    bas.querySelector(".dok-bolme-coz")
      .addEventListener("click", () => bolmeCoz(kap));

    if (typeof window.popupTasinabilirYap === "function") {
      window.popupTasinabilirYap(kap, bas, KAP_ANAHTAR);
    }
  }

  // Bolme uyesi bir SEKMELI ALT KAPSAYICI olabilir; o durumda kendi
  // sekmelerinin adlari birlestirilerek gosterilir.
  function uyeAdOku(uye) {
    if (!uye) return "";
    if (uye.classList && uye.classList.contains("dok-kapsayici")) {
      const ad = (uye._sekmeler || []).map(adOku).filter(Boolean);
      return ad.length ? "[" + ad.join(" / ") + "]" : "";
    }
    return adOku(uye);
  }

  function bolmeAdYenile(kap) {
    const b = kap && kap._bolme;
    const el = kap && kap._baslik
      ? kap._baslik.querySelector(".dok-bolme-ad") : null;
    if (!el) return;
    const adlar = (b && b.uyeler ? b.uyeler : []).map(uyeAdOku).filter(Boolean);
    el.textContent = adlar.length ? adlar.join("  \u2502  ")
                                  : "BOLUNMUS PENCERE";
  }

  // ------------------------------------------------------------------
  // BOLUNMUS KAPSAYICI ICINDE HEDEF GOZENEK (v2.4.27)
  //
  // Bolunmus bir kapsayiciya birakma yapildiginda "hangi gozenege"
  // birakildigi bilinmeden islem yapilamaz. Onceden bu hesaplanmadigi
  // icin `surukleBitti` bolunmus kapsayici hedeflerini sessizce
  // reddediyordu (`return false`): kullanici mavi birakma gostergesini
  // goruyor, birakiyor ve HICBIR SEY olmuyordu.
  // ------------------------------------------------------------------
  function bolmeGozenekUyesi(kap, x, y) {
    const b = kap && kap._bolme;
    if (!b) return null;
    for (const goz of [b.g1, b.g2]) {
      if (!goz) continue;
      const r = goz.getBoundingClientRect();
      if (x >= r.left && x <= r.right && y >= r.top && y <= r.bottom) {
        // Gozenek icindeki panel (veya ic ice kapsayici)
        const ic = goz.firstElementChild;
        if (ic) return ic;
      }
    }
    // Birakma noktasi baslik/ayirici uzerindeyse ilk uyeyi kullan
    return (b.uyeler && b.uyeler.length) ? b.uyeler[0] : null;
  }

  // Bolunmus kapsayicinin bir gozenegindeki paneli, gelen pencereyle
  // birlikte SEKMELI bir alt kapsayiciya donusturur. Bolme yerlesimi
  // korunur; yalnizca o gozenegin icerigi sekmeli kapsayici olur.
  function gozenekIcindeSekmele(kap, uye, pop) {
    const b = kap._bolme;
    if (!b) return;
    const goz = (uye.parentElement && uye.parentElement.classList
                 .contains("dok-gozeneki")) ? uye.parentElement : null;
    if (!goz) { sekmeEkle(kap, pop, true); return; }

    // Uye zaten sekmeli bir alt kapsayici ise dogrudan ekle
    if (uye.classList.contains("dok-kapsayici") &&
        uye.classList.contains("dok-sekmeli")) {
      sekmeEkle(uye, pop, true);
      bolmeAdYenile(kap);
      return;
    }

    const r = goz.getBoundingClientRect();
    const altKap = kapsayiciOlustur(r);
    sekmeKapsayiciKur(altKap);

    // ---- SIRA KRITIK (v2.4.27) ----
    // Olculen kusur: `sekmeEkle(altKap, uye, ...)` once cagrildiginda
    // `oncekindenAyir(uye, altKap)` uyeyi bolme listesinden cikariyor,
    // bolmede tek uye kaldigi icin `bolmeCoz(kap)` tetikleniyor ve
    // kapsayici DOM'dan kaldiriliyordu. Geri donuldugunde `goz` kopmus
    // bir gozenek oldugu icin `altKap` (ve icindeki iki panel) DOM
    // agacindan tamamen kopuyordu:
    //   tespit.isConnected=false, rotalar.isConnected=false, kapAdet=0
    //
    // Cozum: bolme uyeligini `sekmeEkle` cagrilmadan ONCE devret.
    // Boylece `oncekindenAyir` cozulecek bir bolme bulamaz.
    const i = b.uyeler.indexOf(uye);
    if (i >= 0) b.uyeler[i] = altKap;
    delete uye._dokBolme;
    altKap._dokBolme = kap;
    goz.appendChild(altKap);
    icerideStil(altKap);
    // Alt kapsayicinin kendi boyut tutamaci gozenek icinde gereksizdir;
    // gozenegin sag-alt kosesinde ikinci bir tutamac olarak gorunur.
    kendiTutamacGizle(altKap);

    // Artik guvenli: uye'nin bolme uyeligi yok, altKap gozenekte.
    // Uye'nin bolmede gizlenen kendi basligi/tutamaci sekmeEkle icinde
    // tekrar gizlenecegi icin once geri getirilir (yedek deger tutarli
    // kalsin).
    kendiBaslikGoster(uye);
    kendiTutamacGoster(uye);
    sekmeEkle(altKap, uye, false);
    sekmeEkle(altKap, pop, true);
    bolmeAdYenile(kap);
  }

  function bolmeCoz(kap) {
    const b = kap._bolme;
    if (!b) { kap.remove(); return; }
    const r = kap.getBoundingClientRect();
    b.uyeler.slice().forEach((p, i) => {
      delete p._dokBolme;
      // v2.4.27: uye bir SEKMELI ALT KAPSAYICI ise (gozenek icinde
      // sekmeleme yapilmisti) onu serbest pencere olarak birak; kendi
      // sekme cubugunu korur.
      if (p.classList.contains("dok-kapsayici")) {
        // v2.4.27: gozenek icinde gizlenen kendi boyut tutamacini geri
        // getir; aksi halde serbest kalan sekmeli pencere
        // boyutlandirilamaz.
        kendiTutamacGoster(p);
        document.body.appendChild(p);
        stilGeriYukle(p);
        p.style.position = "fixed";
        p.style.left = (r.left + i * 28) + "px";
        p.style.top = (r.top + i * 28) + "px";
        p.style.width = Math.max(320, r.width / 2) + "px";
        p.style.height = Math.max(200, r.height) + "px";
        p.style.margin = "0";
        p.style.transform = "none";
        p.style.display = "flex";
        if (typeof window.pencereMinTopUygula === "function") {
          window.pencereMinTopUygula(p);
        }
        if (typeof window.pencereEnUsteGetir === "function") {
          window.pencereEnUsteGetir(p);
        }
        return;
      }
      // v2.4.27: bolmede gizlenen kendi baslik ve tutamacini geri getir
      kendiBaslikGoster(p);
      kendiTutamacGoster(p);
      document.body.appendChild(p);
      stilGeriYukle(p);
      p.style.display = "flex";
      p.style.position = "fixed";
      p.style.left = (r.left + i * 28) + "px";
      p.style.top = (r.top + i * 28) + "px";
      p.style.margin = "0";
      p.style.transform = "none";
      if (typeof window.pencereMinTopUygula === "function") {
        window.pencereMinTopUygula(p);
      }
      if (typeof window.pencereEnUsteGetir === "function") {
        window.pencereEnUsteGetir(p);
      }
    });
    // v2.4.27: uye listesi bosaltilir; aksi halde bu kapsayici kaldirilmis
    // olsa bile `oncekindenAyir` eski listeyi bulup ikinci kez islem yapar.
    b.uyeler.length = 0;
    kap._bolme = null;
    kap.remove();
  }

  // Ortadaki ayiriciyi surukleyerek oranlari degistir
  function ayiriciKur(kap) {
    const b = kap._bolme;
    if (!b) return;
    let s = null;

    b.ayirici.addEventListener("pointerdown", (ev) => {
      const r1 = b.g1.getBoundingClientRect();
      const r2 = b.g2.getBoundingClientRect();
      s = {
        p: b.yatay ? ev.clientY : ev.clientX,
        a: b.yatay ? r1.height : r1.width,
        t: (b.yatay ? r1.height + r2.height : r1.width + r2.width),
      };
      try { b.ayirici.setPointerCapture(ev.pointerId); } catch (e) {}
      ev.preventDefault();
      ev.stopPropagation();
    });

    b.ayirici.addEventListener("pointermove", (ev) => {
      if (!s) return;
      const simdi = b.yatay ? ev.clientY : ev.clientX;
      let yeni = s.a + (simdi - s.p);
      const enAz = 60;
      yeni = Math.max(enAz, Math.min(yeni, s.t - enAz));
      // Yerlesim GRID: oranlar grid-template ile ayarlanir
      // (flex degil; kapsayici display:grid)
      if (b.yatay) {
        kap.style.gridTemplateRows =
          "auto " + yeni + "px auto 1fr";
      } else {
        kap.style.gridTemplateColumns =
          yeni + "px auto 1fr";
      }
    });

    const birak = (ev) => {
      if (!s) return;
      s = null;
      try { b.ayirici.releasePointerCapture(ev.pointerId); } catch (e) {}
    };
    b.ayirici.addEventListener("pointerup", birak);
    b.ayirici.addEventListener("pointercancel", birak);
  }

  // ==================================================================
  // SURUKLEME KANCALARI (popup_tasima.js buradan cagirir)
  // ==================================================================
  let sonHedef = null, sonBolge = null;

  function surukleHareket(pop, x, y) {
    if (haricMi(pop)) { gostergeGizle(); return; }
    const hedef = hedefBul(pop, x, y);
    if (!hedef) {
      sonHedef = null; sonBolge = null;
      gostergeGizle();
      return;
    }
    const bolge = bolgeBul(hedef, x, y);
    sonHedef = hedef; sonBolge = bolge;
    const r = hedef.getBoundingClientRect();
    // "orta" gostergesi: dikey bolme onizlemesi (sag yari)
    gostergeGoster(r, bolge === "orta" ? "sag" : bolge);
  }

  function surukleBitti(pop, x, y) {
    gostergeGizle();
    if (haricMi(pop)) return false;
    // Birakma anini yeniden dogrula (imlec hizli hareket etmis olabilir)
    const hedef = hedefBul(pop, x, y);
    if (!hedef) { sonHedef = null; sonBolge = null; return false; }
    const bolge = bolgeBul(hedef, x, y);
    sonHedef = null; sonBolge = null;

    try {
      if (bolge === "sekme") {
        // Hedef zaten kapsayici ise sekme olarak ekle
        if (hedef.classList.contains("dok-kapsayici")) {
          if (hedef.classList.contains("dok-sekmeli")) {
            sekmeEkle(hedef, pop, true);
            return true;
          }
          // v2.4.27: Bolunmus kapsayiciya sekme birakildi.
          // Onceden `return false` yaziliydi ve islem SESSIZCE reddedilirdi;
          // kullanici birakma gostergesini gorup birakmasina ragmen hicbir
          // sey olmuyordu. Artik bolme icindeki HANGI gozenege birakildigi
          // hesaplanir ve o gozenekteki panel ile sekme yapilir.
          const uye = bolmeGozenekUyesi(hedef, x, y);
          if (uye && uye !== pop) {
            gozenekIcindeSekmele(hedef, uye, pop);
            return true;
          }
          return false;
        }
        // Iki serbest pencere -> yeni sekmeli kapsayici
        const r = hedef.getBoundingClientRect();
        const kap = kapsayiciOlustur(r);
        sekmeKapsayiciKur(kap);
        sekmeEkle(kap, hedef, false);
        sekmeEkle(kap, pop, true);
        return true;
      }
      // Bolme
      if (hedef.classList.contains("dok-kapsayici")) {
        // v2.4.27: Bolunmus kapsayicinin bir gozenegine kenar/orta
        // birakmasi: o gozenekteki paneli hedef alarak ic ice bolme yap.
        const uye = bolmeGozenekUyesi(hedef, x, y);
        if (uye && uye !== pop) {
          bolmeOlustur(uye, pop, bolge);
          return true;
        }
        return false;
      }
      bolmeOlustur(hedef, pop, bolge);
      return true;
    } catch (e) {
      try { console.warn("[DOK] islem basarisiz:", e); } catch (x) {}
      return false;
    }
  }

  // ------------------------------------------------------------------
  // DISA ACILAN API
  // ------------------------------------------------------------------
  window.pencereDok = {
    surukleHareket: surukleHareket,
    surukleBitti: surukleBitti,
    sekmeEkle: sekmeEkle,
    sekmeCikar: sekmeCikar,
    bolmeOlustur: bolmeOlustur,
    bolmeCoz: bolmeCoz,
    kapsayiciCoz: kapsayiciCoz,
    _hedefBul: hedefBul,
    _oncekindenAyir: oncekindenAyir,
    _bolmeGozenekUyesi: bolmeGozenekUyesi,
    _bolmeAdYenile: bolmeAdYenile,
    _bolgeBul: bolgeBul,
  };
})();
