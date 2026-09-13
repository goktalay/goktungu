/* =================================================================
   GOKTUNGU v2.10.0 -- Tanitim sitesi oturum katmani
   -----------------------------------------------------------------
   NEDEN BU DOSYA VAR
   Ziyaretci daha once giris ve kayit icin /company/ adresine
   gonderiliyordu.  Kullanici karari (2026-08-16): giris ve kayit
   DOGRUDAN tanitim sayfasindan yapilacak, kurumsal panel ise
   kullanici menusunden AYRI SEKMEDE acilacak.

   OTURUM NASIL PAYLASILIR
   Sunucu `goktungu_firma` cerezini `Path=/` ile yazar.  Bu sayede
   tanitim sayfasi (/) ile kurumsal panel (/company/) AYNI oturumu
   gorur; yeni sekme acilirken kimlik yeniden sorulmaz.  Cerez
   HttpOnly oldugundan JavaScript jetonu okuyamaz -- oturum durumu
   yalnizca `GET /api/firma/ben` yanitindan ogrenilir.  Bu kasitlidir:
   jeton XSS ile sizdirilamaz.

   SURE
   Cerezin `Max-Age` degeri ile jetonun veritabanindaki omru artik tek
   kaynaktan (`oturum_saat` ayari) uretilir.  Sunucu `kalan_sn`
   dondurur; bu dosya sure dolmadan kisa bir pay birakip oturumu
   kendiliginden kapatir, boylece kullanici olu oturumla islem
   denemez.

   ROL KAPISI
   "Musteri Paneli" ogesi YALNIZ `oturum.panel_yetkisi` true iken
   gorunur (rol = firma_yonetici).  Bu bir GORUNUM kararidir; asil
   engel sunucudadir (`_dosya_sun` icindeki /company/ kapisi pilot
   oturumuna 403 doner).  Arayuzdeki gizleme tek basina guvenlik
   dayanagi SAYILMAZ.
   (c) VEILOX Savunma Anonim Sirketi
   ================================================================= */
(function () {
  "use strict";

  /* Oturum sonuna ne kadar kala kendiliginden kapatilir (saniye).
     Pay birakilmazsa kullanici, cerez olmus ama arayuz hala acik
     gorunurken islem baslatir ve 401 alir. */
  var PAY_SN = 30;
  /* Kalan sure sayaci bu sikligla denetlenir (ms).  Zamanlayici
     dogrudan `kalan_sn` kadar beklemek yerine periyodik denetler:
     bilgisayar uykuya alinip geri donduğunde tek uzun bekleme
     gecikir, periyodik denetim ise dogru sonucu verir. */
  var DENETIM_MS = 15000;

  var durum = null;      /* {kullanici, oturum} veya null */
  var sayacId = null;
  var bitisMs = 0;

  /* --------------------------------------------------------------
     Yardimcilar
     -------------------------------------------------------------- */
  function el(id) { return document.getElementById(id); }

  function ceviri(anahtar, varsayilan) {
    /* EN sozlugu yalniz Ingilizce degerleri tutar; TR icin HTML'deki
       ozgun metin kaynaktir.  Betikle uretilen metinlerde HTML kaynagi
       olmadigi icin varsayilan (TR) burada verilir. */
    if (ingilizceMi() && window.goktunguSozluk &&
        window.goktunguSozluk[anahtar]) {
      return window.goktunguSozluk[anahtar];
    }
    return varsayilan;
  }

  /* Dil okumasi TEK yerden yapilir.  `window.goktunguDil` dil.js
     tarafindan yazilir; bu betik dil.js'ten ONCE yuklenirse
     tanimsiz olur.  O durumda `<html lang>` yedegi okunur --
     dil.js onu her zaman ayarlar.  Ikisi de yoksa Turkce
     varsayilir: sayfanin kaynak dili Turkce'dir. */
  function ingilizceMi() {
    if (window.goktunguDil === "en") return true;
    if (window.goktunguDil === "tr") return false;
    var l = (document.documentElement.getAttribute("lang") || "")
      .toLowerCase();
    return l.indexOf("en") === 0;
  }

  function json(yol, secenek) {
    secenek = secenek || {};
    secenek.credentials = "same-origin";   /* cerez gonderilsin */
    secenek.headers = Object.assign(
      { "Content-Type": "application/json" }, secenek.headers || {});
    return fetch(yol, secenek).then(function (y) {
      return y.json().catch(function () { return {}; }).then(function (g) {
        return { kod: y.status, tamam: y.ok, govde: g };
      });
    });
  }

  function hataYaz(kutu, metin) {
    if (!kutu) return;
    kutu.textContent = metin || "";
    kutu.style.display = metin ? "block" : "none";
  }

  /* --------------------------------------------------------------
     Katman gorunurlugu
     -------------------------------------------------------------- */
  var oncekiOdak = null;

  function katmanAc(kip) {
    var k = el("gkKatman");
    if (!k) return;
    oncekiOdak = document.activeElement;
    k.classList.add("acik");
    k.setAttribute("aria-hidden", "false");
    document.body.classList.add("gk-kilit");
    kipDegistir(kip || "giris");
    /* FAZ18-IS24-BAKIM-KIPI: katman her acilista durum sorulur.
       Sayfa yuklenirken DEGIL: kullanicinin cogu kayit katmanini
       hic acmaz ve gereksiz istek atmak dogru olmaz. */
    bakimDurumSor();
    /* Odak ilk alana tasinir: klavye kullanicisi katman acilinca
       arka plandaki baglantilarda dolasmasin. */
    var ilk = k.querySelector(
      ".gk-form:not([hidden]) input:not([type=hidden])");
    if (ilk) { try { ilk.focus(); } catch (e) { /* yok say */ } }
  }

  function katmanKapat() {
    var k = el("gkKatman");
    if (!k) return;
    k.classList.remove("acik");
    k.setAttribute("aria-hidden", "true");
    document.body.classList.remove("gk-kilit");
    if (oncekiOdak) { try { oncekiOdak.focus(); } catch (e) { /* yok say */ } }
  }

  function kipDegistir(kip) {
    /* UC FORM: giris | kurumsal kayit | bireysel kayit.
       `hidden` ozniteligi kullanilir: gizli formdaki `required`
       alanlar tarayici dogrulamasina KATILMAZ.  display:none ile
       gizlemek de ayni sonucu verir ama AYRI FORM kullanmanin
       nedeni budur -- tek formda alan gizlemek dogrulamayi bozar.
       Bireysel formu kurumsal formdan ayirmanin nedeni de ayni:
       kurum unvani `required` oldugu icin gizli kalsa bile bireysel
       gonderimi engellerdi. */
    var g = el("gkGirisForm"), y = el("gkKayitForm"),
        b = el("gkBireyselForm");
    if (!g || !y) return;
    var kayit = kip === "kayit", bir = kip === "bireysel";
    g.hidden = kayit || bir;
    y.hidden = !kayit;
    if (b) b.hidden = !bir;
    hataYaz(el("gkGirisHata"), "");
    hataYaz(el("gkKayitHata"), "");
    hataYaz(el("gkBireyselHata"), "");
    var hedef = bir ? (b || g) : (kayit ? y : g);
    var ilk = hedef.querySelector("input:not([type=hidden])");
    if (ilk) { try { ilk.focus(); } catch (e) { /* yok say */ } }
  }

  /* --------------------------------------------------------------
     Ust serit: oturum acik / kapali gorunumu
     -------------------------------------------------------------- */
  function baslikHarf(k) {
    var a = (k.ad || "").trim(), s = (k.soyad || "").trim();
    if (a || s) return ((a[0] || "") + (s[0] || "")).toUpperCase();
    return ((k.eposta || "?")[0] || "?").toUpperCase();
  }

  var ROL_ADI = {
    firma_yonetici: ["Kurum Yöneticisi", "Organization Admin"],
    pilot: ["Pilot", "Pilot"],
    gozlemci: ["Gözlemci", "Observer"]
  };

  function rolYaz(rol) {
    var c = ROL_ADI[rol];
    if (!c) return rol || "";
    return ingilizceMi() ? c[1] : c[0];
  }

  function serityaz() {
    var kapali = el("gkKapali"), acik = el("gkAcik");
    if (!kapali || !acik) return;
    if (!durum) {
      kapali.hidden = false;
      acik.hidden = true;
      return;
    }
    kapali.hidden = true;
    acik.hidden = false;
    var k = durum.kullanici || {};
    var o = durum.oturum || {};
    var ad = ((k.ad || "") + " " + (k.soyad || "")).trim() || k.eposta || "";
    var b;
    if ((b = el("gkAvatar"))) b.textContent = baslikHarf(k);
    if ((b = el("gkAd"))) b.textContent = ad;
    if ((b = el("gkMenuAd"))) b.textContent = ad;
    if ((b = el("gkMenuEposta"))) b.textContent = k.eposta || "";
    if ((b = el("gkMenuRol"))) b.textContent = rolYaz(k.rol);
    if ((b = el("gkMenuKurum"))) b.textContent = k.firma_unvan || "";
    /* ROL KAPISI (gorunum): panel ogesi yalniz yetkiliye gosterilir.
       Yetkisiz kullaniciya bunun yerine gerekce yazilir; oge sessizce
       kaybolursa kullanici eksiklik oldugunu sanir. */
    var p = el("gkMenuPanel"), pn = el("gkMenuPanelNot");
    if (p) p.hidden = !o.panel_yetkisi;
    if (pn) pn.hidden = !!o.panel_yetkisi;
  }

  /* v2.12.2: ust seritte artik IKI acilir menu var:
       gkMenuDg  -> gkMenu       (oturum ACIK: kullanici menusu)
       gkKonukDg -> gkKonukMenu  (oturum KAPALI: giris/kayit menusu)
     Iki menu ayni davranisi paylasir; islevler kimlik ciftini parametre
     alir.  Kopyalanmis ikinci bir islev yazilirsa dis tiklama / Escape
     islemleri iki yerde ayri ayri guncellenmek zorunda kalir. */
  var MENULER = [
    { m: "gkMenu", d: "gkMenuDg" },
    { m: "gkKonukMenu", d: "gkKonukDg" }
  ];

  function menuKapat() {
    MENULER.forEach(function (c) {
      var m = el(c.m), d = el(c.d);
      if (m) m.classList.remove("acik");
      if (d) d.setAttribute("aria-expanded", "false");
    });
  }

  function menuAcKapa(mId, dId) {
    var m = el(mId), d = el(dId);
    if (!m || !d) return;
    var acilacak = !m.classList.contains("acik");
    /* Once TUMU kapatilir: iki menu ayni anda acik kalmamali. */
    menuKapat();
    if (!acilacak) return;
    m.classList.add("acik");
    d.setAttribute("aria-expanded", "true");
  }

  /* --------------------------------------------------------------
     Oturum sayaci
     -------------------------------------------------------------- */
  function sayacDurdur() {
    if (sayacId) { clearInterval(sayacId); sayacId = null; }
  }

  function sayacKur(kalanSn) {
    sayacDurdur();
    if (!kalanSn || kalanSn <= 0) return;
    bitisMs = Date.now() + (kalanSn * 1000);
    sayacId = setInterval(function () {
      var kalan = Math.floor((bitisMs - Date.now()) / 1000);
      var g = el("gkMenuSure");
      if (g) g.textContent = sureMetni(kalan);
      if (kalan <= PAY_SN) {
        sayacDurdur();
        /* Sunucuya cikis bildirilir: cerez zaten olmus olsa da
           istegin basarisiz olmasi onemsizdir, arayuz her durumda
           kapali duruma gecer. */
        json("/api/firma/cikis", { method: "POST" })
          .catch(function () { /* yok say */ })
          .then(function () { oturumBitti(true); });
      }
    }, DENETIM_MS);
    var g = el("gkMenuSure");
    if (g) g.textContent = sureMetni(kalanSn);
  }

  function sureMetni(sn) {
    if (sn == null || sn < 0) return "";
    var s = Math.floor(sn / 3600), d = Math.floor((sn % 3600) / 60);
    if (ingilizceMi()) {
      return s > 0 ? (s + " h " + d + " min left")
                   : (d + " min left");
    }
    return s > 0 ? (s + " sa " + d + " dk kaldı") : (d + " dk kaldı");
  }

  function oturumBitti(uyar) {
    durum = null;
    sayacDurdur();
    menuKapat();
    serityaz();
    if (uyar) {
      katmanAc("giris");
      hataYaz(el("gkGirisHata"), ceviri(
        "gk.sureBitti",
        "Oturum süresi doldu. Lütfen yeniden giriş yapın."));
    }
  }

  /* --------------------------------------------------------------
     Oturum sorgusu
     -------------------------------------------------------------- */
  function benSor() {
    return json("/api/firma/ben").then(function (y) {
      if (!y.tamam || !y.govde || !y.govde.kullanici) {
        durum = null;
        sayacDurdur();
        serityaz();
        return null;
      }
      durum = {
        kullanici: y.govde.kullanici,
        oturum: y.govde.oturum || {}
      };
      serityaz();
      sayacKur(durum.oturum.kalan_sn);
      return durum;
    }).catch(function () {
      /* Ag hatasi oturumu DUSURMEZ: gecici kesintide kullaniciyi
         atmak, yeniden giris zorunlulugu dogurur. */
      return durum;
    });
  }

  /* --------------------------------------------------------------
     Giris
     -------------------------------------------------------------- */
  function girisGonder(ev) {
    if (ev) ev.preventDefault();
    var e = el("gkEposta"), s = el("gkSifre"), d = el("gkGirisDg");
    if (!e || !s) return;
    hataYaz(el("gkGirisHata"), "");
    if (d) { d.disabled = true; d.classList.add("mesgul"); }
    json("/api/firma/giris", {
      method: "POST",
      body: JSON.stringify({ eposta: e.value.trim(), sifre: s.value })
    }).then(function (y) {
      if (!y.tamam) {
        /* 403 + `dogrulama_gerekli`: sifre DOGRU ama e-posta
           dogrulanmamis.  Bu ayrim onemli -- yoksa kullanici
           bosuna sifre sifirlamaya yonelir. */
        if (y.kod === 403 && (y.govde || {}).dogrulama_gerekli) {
          var adres = (el("gkEposta") || {}).value || "";
          json("/api/dogrulama/gonder", {
            method: "POST",
            body: JSON.stringify({ eposta: adres })
          }).catch(function () { return null; }).then(function () {
            dogrulamaBilgisi(adres);
          });
          return;
        }
        hataYaz(el("gkGirisHata"), y.govde.hata || ceviri(
          "gk.girisHata", "E-posta veya şifre hatalı."));
        return;
      }
      s.value = "";
      return benSor().then(function () { katmanKapat(); });
    }).catch(function () {
      hataYaz(el("gkGirisHata"), ceviri(
        "gk.agHata", "Sunucuya ulaşılamadı. Lütfen yeniden deneyin."));
    }).then(function () {
      if (d) { d.disabled = false; d.classList.remove("mesgul"); }
    });
  }

  /* --------------------------------------------------------------
     Kayit
     -------------------------------------------------------------- */
  /* ------------------------------------------------------------
     FAZ18-IS24-BAKIM-KIPI: SISTEM BAKIM BANDI

     `GET /api/genel/bakim` durumu dondurur. Kip acikken kayit
     uclari 503 doner; kullaniciyi formu DOLDURMADAN once
     uyarmak gerekir.

     Uc erisilemezse band GIZLI kalir: bakim kipi hakkinda bilgi
     alinamamasi, kayit akisini engellemek icin gerekce degildir.
     ------------------------------------------------------------ */
  var _bakimDurum = null;

  function bakimBandiYaz(kutu, d) {
    if (!kutu) return;
    if (!d || !d.acik) { kutu.hidden = true; kutu.textContent = ""; return; }
    var m = d.mesaj || ceviri(
      "gk.bakimMesaj",
      "Sistem şu anda bakım aşamasındadır. Yeni kayıtlar geçici " +
      "olarak alınamıyor.");
    if (d.bitis) {
      m += " " + ceviri("gk.bakimBitis", "Tahmini bitiş:") +
           " " + d.bitis;
    }
    kutu.textContent = m;
    kutu.hidden = false;
  }

  function bakimDurumSor() {
    return json("/api/genel/bakim", { method: "GET" })
      .then(function (y) {
        _bakimDurum = (y && y.govde) || null;
        bakimBandiYaz(el("gkBakimKayit"), _bakimDurum);
        bakimBandiYaz(el("gkBakimBireysel"), _bakimDurum);
        return _bakimDurum;
      })
      .catch(function () { return null; });
  }

  /* Kayit ucundan donen 503'u bakim olarak tanir.
     Sunucu govdede `bakim: true` bayragi gonderir; kod yerine
     bayraga bakmak dogrudur cunku 503 baska nedenlerle de
     donebilir (ornegin vekil katmani). */
  function bakimYanitiMi(y) {
    return !!(y && y.govde && y.govde.bakim);
  }
  function kayitGonder(ev) {
    if (ev) ev.preventDefault();
    var d = el("gkKayitDg");
    var al = function (id) {
      var x = el(id);
      return x ? x.value.trim() : "";
    };
    var sifre = (el("gkKSifre") || {}).value || "";
    var sifre2 = (el("gkKSifre2") || {}).value || "";
    hataYaz(el("gkKayitHata"), "");
    /* Istemci tarafi on denetim: sunucu yine dogrular, ancak sifre
       uyusmazligini ag turuna cikmadan bildirmek daha hizlidir. */
    if (sifre !== sifre2) {
      hataYaz(el("gkKayitHata"), ceviri(
        "gk.sifreUyusmaz", "Şifreler eşleşmiyor."));
      return;
    }
    if (d) { d.disabled = true; d.classList.add("mesgul"); }
    json("/api/firma/kayit", {
      method: "POST",
      body: JSON.stringify({
        unvan: al("gkKUnvan"),
        vergi_no: al("gkKVergi"),
        telefon: al("gkKTelefon"),
        adres: al("gkKAdres"),
        ad: al("gkKAd"),
        soyad: al("gkKSoyad"),
        eposta: al("gkKEposta"),
        sifre: sifre,
        sifre2: sifre2
      })
    }).then(function (y) {
      if (!y.tamam) {
        /* FAZ18-IS24-BAKIM-KIPI: bakim yaniti ayri ele alinir --
           bandi da gosterir, boylece kullanici sayfayi
           yenilemeden durumu anlar. */
        if (bakimYanitiMi(y)) {
          _bakimDurum = { acik: true, mesaj: y.govde.hata,
                          bitis: y.govde.bitis || null };
          bakimBandiYaz(el("gkBakimKayit"), _bakimDurum);
          hataYaz(el("gkKayitHata"), "");
          return;
        }
        hataYaz(el("gkKayitHata"), y.govde.hata || ceviri(
          "gk.kayitHata", "Kayıt tamamlanamadı."));
        return;
      }
      if (el("gkKSifre")) el("gkKSifre").value = "";
      if (el("gkKSifre2")) el("gkKSifre2").value = "";
      /* Sunucu kayittan sonra oturumu kendisi acar (`giris:true`).
         Acmadiysa kullanici giris kipine alinir; sessizce kapatmak
         "kayit oldu ama hicbir sey olmadi" izlenimi verir. */
      return benSor().then(function (o) {
        if (o) { katmanKapat(); return; }
        kipDegistir("giris");
        hataYaz(el("gkGirisHata"), ceviri(
          "gk.kayitTamamGiris",
          "Kurumunuz kaydedildi. Lütfen giriş yapın."));
      });
    }).catch(function () {
      hataYaz(el("gkKayitHata"), ceviri(
        "gk.agHata", "Sunucuya ulaşılamadı. Lütfen yeniden deneyin."));
    }).then(function () {
      if (d) { d.disabled = false; d.classList.remove("mesgul"); }
    });
  }

  /* --------------------------------------------------------------
     Bireysel kayit
     --------------------------------------------------------------
     Kurumsal kayittan iki noktada AYRILIR:
       1. Kurum alanlari gonderilmez (unvan/vergi/adres yok).
       2. Sunucu OTURUM ACMAZ (`giris:false`, `dogrulama_gerekli:true`).
          Bu yuzden `benSor()` cagrilmaz; kullanici dogrulama
          bilgilendirmesine yonlendirilir.  `benSor()` cagirmak
          "kayit oldu ama giris yapamadi" gorunumu yaratirdi.
     -------------------------------------------------------------- */
  function bireyselGonder(ev) {
    if (ev) ev.preventDefault();
    var d = el("gkBireyselDg");
    var al = function (id) {
      var x = el(id);
      return x ? x.value.trim() : "";
    };
    var sifre = (el("gkBSifre") || {}).value || "";
    var sifre2 = (el("gkBSifre2") || {}).value || "";
    hataYaz(el("gkBireyselHata"), "");
    if (sifre !== sifre2) {
      hataYaz(el("gkBireyselHata"), ceviri(
        "gk.sifreUyusmaz", "Şifreler eşleşmiyor."));
      return;
    }
    if (d) { d.disabled = true; d.classList.add("mesgul"); }
    json("/api/bireysel/kayit", {
      method: "POST",
      body: JSON.stringify({
        ad: al("gkBAd"),
        soyad: al("gkBSoyad"),
        eposta: al("gkBEposta"),
        telefon: al("gkBTelefon"),
        sifre: sifre,
        sifre2: sifre2
      })
    }).then(function (y) {
      if (!y.tamam) {
        /* FAZ18-IS24-BAKIM-KIPI */
        if (bakimYanitiMi(y)) {
          _bakimDurum = { acik: true, mesaj: y.govde.hata,
                          bitis: y.govde.bitis || null };
          bakimBandiYaz(el("gkBakimBireysel"), _bakimDurum);
          hataYaz(el("gkBireyselHata"), "");
          return;
        }
        hataYaz(el("gkBireyselHata"), y.govde.hata || ceviri(
          "gk.kayitHata", "Kayıt tamamlanamadı."));
        return;
      }
      if (el("gkBSifre")) el("gkBSifre").value = "";
      if (el("gkBSifre2")) el("gkBSifre2").value = "";
      var e = (y.govde || {}).eposta || al("gkBEposta");
      /* Dogrulama bagi kayit aninda GONDERILMEZ: ayri uc cagrilir.
         Boylece SMTP arizasi kaydi geri almaz -- hesap olusmus olur
         ve kullanici bagi yeniden isteyebilir. */
      return json("/api/dogrulama/gonder", {
        method: "POST",
        body: JSON.stringify({ eposta: e })
      }).catch(function () { return null; }).then(function () {
        dogrulamaBilgisi(e);
      });
    }).catch(function () {
      hataYaz(el("gkBireyselHata"), ceviri(
        "gk.agHata", "Sunucuya ulaşılamadı. Lütfen yeniden deneyin."));
    }).then(function () {
      if (d) { d.disabled = false; d.classList.remove("mesgul"); }
    });
  }

  /* Kayit sonrasi bilgilendirme: form yerine dogrulama mesaji
     gosterilir.  Ayri sayfaya yonlendirmek yerine katman icinde
     kalinir -- kullanici adresini yanlis yazdiysa geri donup
     yeniden deneyebilir. */
  function dogrulamaBilgisi(eposta) {
    var b = el("gkBireyselForm");
    if (!b) return;
    var k = el("gkDogrulamaKart");
    if (!k) return;
    b.hidden = true;
    var a = el("gkDogAdres");
    if (a) a.textContent = eposta || "";
    k.hidden = false;
  }

  /* Dogrulama bagini yeniden gonderir.  Hiz siniri sunucuda
     (`kod_uret` -> YENIDEN_GONDER_SN); 429 kullaniciya oldugu gibi
     bildirilir cunku kalan sure metni sunucudan gelir. */
  function dogrulamaYinele(ev) {
    if (ev) ev.preventDefault();
    var d = el("gkDogYinele"), n = el("gkDogNot");
    var e = (el("gkDogAdres") || {}).textContent || "";
    if (!e) return;
    if (d) { d.disabled = true; d.classList.add("mesgul"); }
    if (n) { n.textContent = ""; }
    json("/api/dogrulama/gonder", {
      method: "POST",
      body: JSON.stringify({ eposta: e })
    }).then(function (y) {
      if (n) {
        n.textContent = y.tamam
          ? ((y.govde || {}).mesaj || ceviri(
              "gk.dogGonderildi",
              "Doğrulama bağı e-posta adresinize gönderildi."))
          : ((y.govde || {}).hata || ceviri(
              "gk.dogHata", "Gönderim başarısız."));
        n.className = y.tamam ? "gk-ipucu" : "gk-hata acik";
      }
    }).catch(function () {
      if (n) {
        n.textContent = ceviri(
          "gk.agHata", "Sunucuya ulaşılamadı. Lütfen yeniden deneyin.");
        n.className = "gk-hata acik";
      }
    }).then(function () {
      if (d) { d.disabled = false; d.classList.remove("mesgul"); }
    });
  }

  /* --------------------------------------------------------------
     Cikis
     -------------------------------------------------------------- */
  function cikisYap(ev) {
    if (ev) ev.preventDefault();
    json("/api/firma/cikis", { method: "POST" })
      .catch(function () { /* yok say */ })
      .then(function () { oturumBitti(false); });
  }

  /* --------------------------------------------------------------
     Baglama
     -------------------------------------------------------------- */
  function baglan() {
    /* Katmani acan tetikleyiciler: `data-gk-ac="giris|kayit"` */
    document.querySelectorAll("[data-gk-ac]").forEach(function (t) {
      t.addEventListener("click", function (ev) {
        ev.preventDefault();
        /* v2.12.2: tetikleyici artik konuk menusunun ICINDE olabilir.
           Katman acilirken menu kapatilmazsa menu katmanin arkasinda
           acik kalir ve katman kapandiginda ekranda asili gorunur. */
        menuKapat();
        katmanAc(t.getAttribute("data-gk-ac") || "giris");
      });
    });
    var b;
    /* Her iki formda kapat dugmesi vardir; kimlik yerine nitelik
       kullanilir ki yeni form eklendiginde baglama unutulmasin. */
    document.querySelectorAll("#gkKatman .gk-kapat").forEach(function (x) {
      x.addEventListener("click", katmanKapat);
    });
    if ((b = el("gkKayitAc"))) {
      b.addEventListener("click", function (ev) {
        ev.preventDefault(); kipDegistir("kayit");
      });
    }
    if ((b = el("gkGirisAc"))) {
      b.addEventListener("click", function (ev) {
        ev.preventDefault(); kipDegistir("giris");
      });
    }
    if ((b = el("gkBireyselAc"))) {
      b.addEventListener("click", function (ev) {
        ev.preventDefault(); kipDegistir("bireysel");
      });
    }
    if ((b = el("gkBireyselAc2"))) {
      b.addEventListener("click", function (ev) {
        ev.preventDefault(); kipDegistir("bireysel");
      });
    }
    if ((b = el("gkKurumsalAc"))) {
      b.addEventListener("click", function (ev) {
        ev.preventDefault(); kipDegistir("kayit");
      });
    }
    if ((b = el("gkDogYinele"))) {
      b.addEventListener("click", dogrulamaYinele);
    }
    if ((b = el("gkDogKapat"))) {
      b.addEventListener("click", function (ev) {
        ev.preventDefault();
        var k = el("gkDogrulamaKart");
        if (k) k.hidden = true;
        katmanKapat();
      });
    }
    if ((b = el("gkGirisForm"))) b.addEventListener("submit", girisGonder);
    if ((b = el("gkKayitForm"))) b.addEventListener("submit", kayitGonder);
    if ((b = el("gkBireyselForm"))) {
      b.addEventListener("submit", bireyselGonder);
    }
    if ((b = el("gkCikis"))) b.addEventListener("click", cikisYap);
    MENULER.forEach(function (c) {
      var t = el(c.d);
      if (!t) return;
      t.addEventListener("click", function (ev) {
        ev.stopPropagation(); menuAcKapa(c.m, c.d);
      });
    });
    /* Ortu tiklamasi katmani kapatir; kart icindeki tiklama kapatmaz */
    if ((b = el("gkKatman"))) {
      b.addEventListener("click", function (ev) {
        if (ev.target === b) katmanKapat();
      });
    }
    document.addEventListener("click", function (ev) {
      var acikVar = false, icinde = false;
      MENULER.forEach(function (c) {
        var m = el(c.m), d = el(c.d);
        if (!m || !m.classList.contains("acik")) return;
        acikVar = true;
        if (m.contains(ev.target) || (d && d.contains(ev.target))) {
          icinde = true;
        }
      });
      if (!acikVar || icinde) return;
      menuKapat();
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key !== "Escape") return;
      menuKapat();
      var k = el("gkKatman");
      if (k && k.classList.contains("acik")) katmanKapat();
    });
    /* Dil degisince betikle uretilen metinler (rol adi, kalan sure)
       yeniden yazilir; dil.js bu olayi yayar. */
    document.addEventListener("dilDegisti", function () {
      serityaz();
      var g = el("gkMenuSure");
      if (g && bitisMs) {
        g.textContent = sureMetni(Math.floor((bitisMs - Date.now()) / 1000));
      }
    });
    /* Sekme one geldiginde oturum yeniden dogrulanir: baska sekmede
       cikis yapilmis olabilir. */
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) benSor();
    });
    benSor();
  }

  window.goktunguOturum = {
    ac: katmanAc,
    kapat: katmanKapat,
    durum: function () { return durum; },
    tazele: benSor
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", baglan);
  } else {
    baglan();
  }
})();
