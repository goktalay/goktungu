/* ============================================================
   GÖRÜNTÜ KÖPRÜSÜ — AI menüsü girişi          [FAZ20-IS1-JS-v1]
   ============================================================

   Kullanıcı talebi: "Merkez yazılımın içinde AI menüsünün altında
   görünecek." ve "Görüntü merkeze hiç gitmeyecek."

   ------------------------------------------------------------
   NEDEN GÖMÜLÜ GÖSTERİM YOK — ÖLÇÜLDÜ
   ------------------------------------------------------------
   Görüntü Köprüsü kendi yerel panelini http://127.0.0.1:8802
   üzerinde sunar. GÖKTUNGU merkezi HTTPS'tir ve tarayıcının karma
   içerik politikası HTTPS sayfasından http://127.0.0.1 yüklemesini
   ENGELLER. Belirleyici deney (2026-08-21):

       açık port   127.0.0.1:8801  -> hata,    1 ms
       kapalı port 127.0.0.1:9     -> hata,    1 ms
       gerçek ağ isteği (HTTPS)    -> hata, 4051 ms

   Açık ve kapalı port birebir aynı 1 ms'de düştü; gerçekten ağa çıkan
   istek 4051 ms sürdü. Yani istek ağa HİÇ ÇIKMADI — tarayıcı daha
   başlamadan iptal etti. no-cors kipinde de aynı sonuç alındı,
   dolayısıyla engel CORS değil karma içeriktir. curl aynı adresi
   sorunsuz okuyor, yani sunucu çalışıyor.

   SONUÇ 1: iframe/img/fetch ile gömme DENENMEZ. Denenirse panel
   sessizce boş kalır ve kullanıcı sebebini anlayamaz.

   SONUÇ 2: "köprü kurulu mu" yoklaması da YAPILAMAZ — aynı engel
   yoklama isteğini de durdurur. Bu yüzden kurulu olup olmadığı TAHMİN
   EDİLMEZ; kullanıcıya her iki yol da (paneli aç / indir) açıkça
   sunulur. Yanlış bir "kurulu değil" mesajı göstermektense hiç
   göstermemek doğrudur.

   ------------------------------------------------------------
   SÖZLEŞMELER — hepsi sunucudan ÖLÇÜLDÜ, varsayılmadı
   ------------------------------------------------------------
   - Popup kalıbı: `lokasyonPopup` (index.html) birebir izlenir
     -> kök `class="popup-gizli"`, başlık `.popup-baslik`
   - Kayıt: window.popupBoyutlandirilabilirYap / popupTasinabilirYap
     (popup_tasima.js:310,315), anahtar kalıbı "pp_" + id
   - Menü kapatma: window.menubarKapat (menubar.js:18)
   - Çeviri: i18n.js hiçbir şeyi window'a AÇMIYOR; dil JS'ten
     sorulmaz. Metinler `data-i18n` ile sözlükten gelir.
   - Düğme: `dugme` diye bir sınıf YOK. dugme_birlik.css sözleşmeyi
     doğrudan `button` etiketine uygular. Bu yüzden indirme
     bağlantıları <a> değil <button> olarak yazılır — <a> sözleşmeyi
     almaz ve öteki düğmelerden farklı görünürdü.
   ============================================================ */
(function () {
  "use strict";

  var PORT = 8802;
  var YEREL = "http://127.0.0.1:" + PORT + "/";
  /* ---- Indirme baglantilari — DINAMIK  (IS93-INDIRME-DINAMIK)
     Surum SABIT YAZILMAZ. Olculen kusur: 1.0.0 sabitken 1.1.0
     yayinlandiginda kullanici sessizce ESKI paketi indiriyordu.
     Kurumsal panel bu kusuru yasamiyor cunku surumu depodan okuyor
     (mk_sunucu.py:5331 `depo.liste("video", ...)`). App de ayni
     ilkeye cekildi.

     Uc: GET /api/genel/guncelleme?urun=video&platform=<p>
     yetki="acik" (mk_sunucu.py:1807) — oturum gerekmez.
     Yanit `url` alanini HAZIR verir; istemcide yol kurulmaz.

     Yedek degerler ag kesintisi icindir; uc yanit verince UZERINE
     YAZILIR. Dugmeleri tiklanamaz birakmaktansa son bilinen surumu
     sunmak dogru. */
  /* Yedek degerler de OTURUM DENETIMLI uca gider; statik depo yolu
     403 dondurur (bkz. IS93-INDIRME-OTURUM). */
  var PAKET_LINUX = "/api/firma/goruntu_indir?surum=1.3.0&dosya=" +
                    "goktungu-goruntu_1.3.0_all.deb";
  var PAKET_WIN = "/api/firma/goruntu_indir?surum=1.3.0&dosya=" +
                  "GOKTUNGU-Goruntu-Setup-1.3.0.exe";
  var SURUM_BILGI = { linux: null, windows: null };

  /* Oturum denetimli indirme ucu. Kurumsal panelin kullandigi
     sozlesme (company/uygulama.js:126): surum ve dosya adi ayri ayri
     kacisli parametre olarak gecer. */
  function ucYolu(surum, dosya) {
    return "/api/firma/goruntu_indir?surum=" +
           encodeURIComponent(surum) + "&dosya=" +
           encodeURIComponent(dosya);
  }

  function boyutMB(b) {
    var n = Number(b);
    return (isFinite(n) && n > 0) ? (n / 1048576).toFixed(1) + " MB" : "";
  }

  /* Uctan surum cek. BASARISIZLIK SESSIZDIR: yedek baglantilar
     zaten kurulu, panel calismaya devam eder. */
  function surumCek() {
    ["linux", "windows"].forEach(function (p) {
      var istek = new XMLHttpRequest();
      istek.open("GET", "/api/genel/guncelleme?urun=video&platform=" + p,
                 true);
      istek.timeout = 6000;
      istek.onload = function () {
        if (istek.status !== 200) { return; }
        var v;
        try { v = JSON.parse(istek.responseText); }
        catch (e) { return; }
        if (!v || !v.url || !v.surum) { return; }
        SURUM_BILGI[p] = v;
        /* ---- IS93-INDIRME-OTURUM
           Yanittaki `v.url` STATIK depo yoludur (/indir/video/...)
           ve OTURUM KAPISININ arkasindadir: olculdu, oturumsuz istek
           403 "Bu paket kurumsal panelinizden indirilir" doner.
           Kapi Is 83'te konuldu (`video` OTURUM_GEREKEN_URUNLER
           uyesi, mk_sunucu.py:1448) — kimin indirdigi kayitlansin
           diye. Bu yuzden `v.url` KULLANILMAZ; kurumsal panelin
           kullandigi oturum denetimli uc kurulur
           (company/uygulama.js:126 ile ayni sozlesme). */
        var u = ucYolu(v.surum, v.dosya_ad);
        if (p === "linux") { PAKET_LINUX = u; }
        else { PAKET_WIN = u; }
        surumYaz(p);
      };
      istek.send();
    });
  }

  /* Acik paneldeki dugmeyi ve surum etiketini tazele. */
  function surumYaz(p) {
    var v = SURUM_BILGI[p];
    if (!v) { return; }
    var dugme = document.getElementById(
      p === "linux" ? "gkIndirLinux" : "gkIndirWin");
    /* IS93-INDIRME-TEKNOKTA
       `v.url` STATIK depo yoludur ve 403 doner (bkz.
       IS93-INDIRME-OTURUM). Dugmeye OTURUM DENETIMLI uc yazilir.
       Adres TEK NOKTADA kurulur (ucYolu); onceki halde hem
       surumCek hem surumYaz adres kuruyordu ve surumYaz dogru
       degerin uzerine yaziyordu. */
    if (dugme) {
      dugme.setAttribute("data-gk-url", ucYolu(v.surum, v.dosya_ad));
    }
    var et = document.getElementById(
      p === "linux" ? "gkSurumLinux" : "gkSurumWin");
    if (et) {
      var b = boyutMB(v.dosya_boyut);
      et.textContent = "s\u00fcr\u00fcm " + v.surum + (b ? " \u00b7 " + b : "");
    }
  }

  var ID = "goruntuKoprusuPopup";

  /* Windows mi — YALNIZ indirme düğmelerinin SIRASI için.
     Her iki paket de her zaman gösterilir; yanlış tahmin işlevi
     bozmaz, yalnız sıralama değişir. */
  function windowsMi() {
    try {
      var p = (navigator.userAgentData &&
               navigator.userAgentData.platform) ||
              navigator.platform || "";
      return /win/i.test(p);
    } catch (e) { return false; }
  }

  function kur() {
    var mevcut = document.getElementById(ID);
    if (mevcut) return mevcut;
    surumCek();  /* IS93-INDIRME-DINAMIK */

    var win = windowsMi();
    var d = document.createElement("div");
    d.id = ID;
    d.className = "popup-gizli";

    /* İndirme düğmeleri: yerel platform önce.
       data-i18n KULLANILMAZ çünkü metin dile göre değişmiyor
       ("Linux (.deb)" her dilde aynı). */
    var btnLinux =
      '<button type="button" id="gkIndirLinux" data-gk-url="' +
      PAKET_LINUX + '"><i class="fa-brands fa-linux"></i>' +
      '<span>Linux (.deb)</span></button>' +
      '<small id="gkSurumLinux" class="gk-surum"></small>';
    var btnWin =
      '<button type="button" id="gkIndirWin" data-gk-url="' +
      PAKET_WIN + '"><i class="fa-brands fa-windows"></i>' +
      '<span>Windows (.exe)</span></button>' +
      '<small id="gkSurumWin" class="gk-surum"></small>';

    d.innerHTML =
      '<div class="popup-baslik">' +
        '<span><i class="fa-solid fa-video"></i> ' +
          '<span data-i18n="panelGoruntuKoprusu">GÖRÜNTÜ KÖPRÜSÜ</span>' +
        '</span>' +
        '<button id="btnGkKapat" data-i18n-title="ipKapat" title="Kapat">' +
          '<i class="fa-solid fa-xmark"></i></button>' +
      '</div>' +

      '<div class="gk-icerik">' +

        '<p class="gk-aciklama" data-i18n="gkAciklama">' +
          'Görüntü Köprüsü kameraları ve yapay zekâ çıkarımını ' +
          'tamamen kendi bilgisayarınızda çalıştırır. Görüntü merkeze ' +
          'hiçbir zaman gönderilmez.' +
        '</p>' +

        '<div class="gk-bolum-baslik" data-i18n="gkPanelBaslik">' +
          'YEREL PANEL</div>' +

        '<div class="gk-satir">' +
          '<button type="button" id="gkPanelAc">' +
            '<i class="fa-solid fa-up-right-from-square"></i>' +
            '<span data-i18n="gkPanelAcDugme">PANELİ AÇ</span>' +
          '</button>' +
          '<code class="gk-adres">' + YEREL + '</code>' +
        '</div>' +

        '<p class="gk-not" data-i18n="gkPanelNot">' +
          'Panel yeni sekmede açılır. Sekme boş kalıyorsa köprü bu ' +
          'bilgisayarda kurulu ve çalışıyor değildir.' +
        '</p>' +

        '<div class="gk-bolum-baslik" data-i18n="gkKurulumBaslik">' +
          'KURULUM</div>' +

        '<div class="gk-satir">' +
          (win ? btnWin + btnLinux : btnLinux + btnWin) +
        '</div>' +

        '<p class="gk-not" data-i18n="gkKurulumNot">' +
          'Kurulumdan sonra köprü kendiliğinden başlar ve bilgisayar ' +
          'her açıldığında çalışır. Kamera görüntüsü ve tespit kayıtları ' +
          'yalnızca o bilgisayarda saklanır.' +
        '</p>' +

      '</div>';

    document.body.appendChild(d);

    d.querySelector("#btnGkKapat").addEventListener("click", function () {
      d.classList.add("popup-gizli");
    });

    /* Yeni sekme: karma içerik kuralı sekmenin KENDİ adresine
       uygulanmaz, çünkü sekme HTTPS bir sayfanın alt kaynağı değil.
       noopener güvenlik gereğidir. */
    d.querySelector("#gkPanelAc").addEventListener("click", function () {
      try { window.open(YEREL, "_blank", "noopener"); } catch (e) {}
    });

    Array.prototype.forEach.call(
      d.querySelectorAll("[data-gk-url]"), function (b) {
        b.addEventListener("click", function () {
          try { window.location.href = b.getAttribute("data-gk-url"); }
          catch (e) {}
        });
      });

    /* Merkezî pencere altyapısına kaydet. Anahtar kalıbı statik
       popup'larla aynı: "pp_" + id. Modül yoksa sessizce geçilir —
       popup yine çalışır, yalnız taşınamaz. */
    try {
      if (typeof window.popupBoyutlandirilabilirYap === "function")
        window.popupBoyutlandirilabilirYap(d, "pp_" + ID);
    } catch (e) {}
    try {
      if (typeof window.popupTasinabilirYap === "function")
        window.popupTasinabilirYap(d, null, "pp_" + ID);
    } catch (e) {}

    /* ÇEVİRİ — ölçülen gerçek:
       i18n.js klasik script olarak yükleniyor ("ortak scope", dosya
       başındaki not) ve `applyLanguage` ile `aktifDil` üst kapsamda
       tanımlı. Yani window.applyLanguage değil, DOĞRUDAN
       applyLanguage erişilebilir. Ancak dili DEĞİŞTİRMEDEN çağırmak
       için mevcut dili bilmek gerekiyor; `aktifDil` de aynı kapsamda.
       Yanlış bir dil geçirirsek applyLanguage sessizce return eder
       (ilk satırı: dil TR/EN değilse çık) — bu yüzden localStorage'dan
       okunur, i18n.js:8 ile aynı anahtar.
       kaydet=false: kullanıcının dil tercihi DEĞİŞTİRİLMEZ. */
    try {
      var dil = "TR";
      try {
        var s = localStorage.getItem("gcs_dil");
        if (s === "EN" || s === "TR") dil = s;
      } catch (e2) {}
      if (typeof applyLanguage === "function") applyLanguage(dil, false);
    } catch (e) {}

    return d;
  }

  function ac() {
    var d = kur();
    d.classList.remove("popup-gizli");
    try {
      if (typeof window.pencereKonumUygula === "function")
        window.pencereKonumUygula("pp_" + ID, d, true);
    } catch (e) {}
    try {
      if (typeof window.pencereEnUsteGetir === "function")
        window.pencereEnUsteGetir(d);
    } catch (e) {}
  }

  function bagla() {
    var oge = document.getElementById("mbGoruntuKoprusu");
    if (!oge) return false;
    oge.addEventListener("click", function () {
      ac();
      try {
        if (typeof window.menubarKapat === "function")
          window.menubarKapat();
      } catch (e) {}
    });
    return true;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bagla);
  } else {
    bagla();
  }

  window.goruntuKoprusuAc = ac;
})();
