/* =================================================================
   GOKTUNGU v2.6.0 - Indirme merkezi
   VEILOX Savunma Anonim Sirketi
   surumler.json dosyasindan istemci katalogunu okur, indirme
   kartlarini ve SHA-256 tablosunu olusturur.

   M19: TR/EN dil destegi.  Katalog yalniz Turkce metin icerdigi icin
   istemci adi ve aciklamasi EN'de js/dil.js sozlugunden alinir; kart
   yapisi dilDegisti olayinda yeniden cizilir.

   v2.6.0 DEGISIKLIKLERI
   ---------------------
   1) Android kaldirildi.  Yalnizca Windows ve Ubuntu/Linux desteklenir;
      platform tahmini ve etiket eslemesinden Android/APK cikarildi.

   2) Katalog artik IKI paket alani tasir:
        paketler[]   -> tasinabilir arsiv (.zip / .tar.gz)
        kurulumlar[] -> kurulum paketi   (.exe sihirbaz / .deb)
      Ayrim guncelleme akisi icin zorunluydu: sunucudaki guncelleme
      modulu (guncelleme.py) platform koduna gore eslesen ILK paketi
      secer ve `kurulum` bayragini tanimaz.  Iki paket ayni dizide
      dursaydi guncelleme .deb indirmeye kalkabilirdi.
      Bu dosya IKI alani da gosterir; aksi halde site kurulum
      dosyalarini hic sunmazdi.

   3) Her platform icin kurulum paketi ONERILEN olarak one cikarilir,
      tasinabilir arsiv ikincil satir olarak sunulur.
   ================================================================= */
(function () {
  "use strict";

  var SIMGE = { dron: "\u25B2", radar: "\u25CE", ai: "\u25A6" };
  var katalog = null;      // son yuklenen katalog (yeniden cizim icin)

  /* ---------------- Dil yardimcilari ---------------- */
  function dil() { return window.goktunguDil === "en" ? "en" : "tr"; }
  function en() { return dil() === "en"; }

  /* Sozlukten anahtar okur; yoksa yedek metni dondurur. */
  function ce(anahtar, yedek) {
    if (!en()) return yedek;
    var s = window.goktunguSozluk;
    return (s && s[anahtar] != null) ? s[anahtar] : yedek;
  }

  /* Istemci turune gore EN ad ve aciklama */
  function istemciAd(ist) {
    return ce("indir." + ist.tur, ist.ad);
  }
  function istemciAciklama(ist) {
    return ce("indir." + ist.tur + "alt", ist.aciklama);
  }

  /* Platform etiketini yerelleştir: katalog Turkce yaziyor */
  function platformEtiket(etiket) {
    var s = String(etiket == null ? "" : etiket);
    if (!en()) return s;
    return s
      .replace(/kurulum sihirbaz\u0131/i, "installer")
      .replace(/Debian \/ Ubuntu paketi/i, "Debian / Ubuntu package")
      .replace(/ta\u015f\u0131nabilir/i, "portable")
      .replace(/\(64 bit\)/i, "(64-bit)")
      .replace(/ikili/i, "binary");
  }

  /* Kullanicinin isletim sistemini tahmin et -> ilgili paketi one cikar.
     v2.6.0: Android kaldirildi. */
  function platformTahmin() {
    var u = (navigator.userAgent || "") + " " + (navigator.platform || "");
    if (/Win/i.test(u)) return "windows-x64";
    if (/Linux|X11|Ubuntu/i.test(u)) return "linux-x64";
    return "";
  }

  /* Paket kaydindan platform kodunu al.
     platform_kod alani v2.6.0 katalogunda her zaman dolu; eski
     kataloglarla uyum icin etiketten tahmine dusulur. */
  function platformKod(p) {
    if (p && p.platform_kod) return String(p.platform_kod);
    var e = String((p && p.platform) || "");
    if (/Windows/i.test(e)) return "windows-x64";
    if (/Ubuntu|Debian|Linux/i.test(e)) return "linux-x64";
    return "diger";
  }

  function kacir(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  /* Tek indirme satiri uretir.
     onerilen=true  -> vurgulu buton + "onerilen" etiketi
     onerilen=false -> ikincil (soluk) buton

     YERLESIM (v2.6.0 duzeltmesi)
     ----------------------------
     Ilk tasarimda platform adi + "onerilen" etiketi + boyut + buton
     TEK satirda yan yanaydi.  Tarayicida olculdugunde icerik 321px'lik
     karti 432px'e tasiriyordu: etiket ve boyut kartin disina cikiyor,
     buton uzerlerine biniyordu.  Sebep uzun platform adlari
     ("Debian / Ubuntu paketi (.deb)" = 203px).

     Cozum: iki katmanli yerlesim.
       ust satir : platform adi + onerilen etiketi
       alt satir : boyut + indirme butonu
     Boylece uzun adlar tasmaz, etiket ve boyut bilgisi korunur. */
  function satir(p, bu, onerilen) {
    var indirMetni = en() ? "\u2193 Download" : "\u2193 \u0130ndir";
    var onerilenMetni = en() ? "recommended" : "\u00f6nerilen";

    /* Yesil nokta = "bu satir kullandiginiz isletim sistemi icin".
       Isaret onceden ACIKLAMASIZDI: kullanici yesil bir nokta gorup
       anlamini bilemiyordu.  Yanlis dosya indirme riski, savunma
       musterisi icin kabul edilemez.  Artik title ipucu ve ekran
       okuyucu metni tasir; ayrica kartlarin altinda gorunur bir
       aciklama satiri bulunur (bkz. platformNotu). */
    var buIpucu = en()
      ? "Matches the operating system you are using"
      : "Kulland\u0131\u011f\u0131n\u0131z i\u015fletim sistemiyle uyumlu";
    var buOkuyucu = en() ? "your platform" : "sizin platformunuz";

    var h = '<div class="indir-satir' +
            (onerilen ? " onerilen" : " ikincil") + '">';

    /* ust katman: platform adi + onerilen etiketi */
    h += '<div class="ust-sat">';
    h += '<span class="plat">' + kacir(platformEtiket(p.platform)) +
         (bu
           ? ' <span class="bu-plat" role="img" title="' +
             kacir(buIpucu) + '" aria-label="' + kacir(buOkuyucu) +
             '">\u25CF</span>'
           : "") +
         "</span>";
    if (onerilen) {
      h += '<span class="onerilen-et">' + onerilenMetni + "</span>";
    }
    h += "</div>";

    /* alt katman: boyut + indirme butonu */
    h += '<div class="alt-sat">';
    h += '<span class="boyut">' + kacir(p.boyut_metni) + "</span>";
    h += '<a class="dgi' + (onerilen ? "" : " dgi-ikincil") +
         '" href="/indir/' + encodeURIComponent(p.dosya) + '" ' +
         'download title="SHA-256: ' + kacir(p.sha256) + '">' +
         indirMetni + "</a>";
    h += "</div>";

    h += "</div>";
    return h;
  }

  function kartOlustur(ist, tercih) {
    var d = document.createElement("div");
    d.className = "ist-kart " + ist.tur;

    var surumMetni = en() ? "version " : "s\u00fcr\u00fcm ";

    var h = "";
    h += '<div class="ust">';
    h += '<div class="simge">' + (SIMGE[ist.tur] || "\u25A0") + "</div>";
    h += "<div>";
    h += "<h3>" + kacir(istemciAd(ist)) + "</h3>";
    h += '<div class="surum">goktungu-' + kacir(ist.tur) + " &middot; " +
         surumMetni + kacir(window.__GOKTUNGU_SURUM || "") + "</div>";
    h += "</div></div>";
    h += "<p>" + kacir(istemciAciklama(ist)) + "</p>";

    /* Platform koduna gore grupla: her platform icin
       once kurulum paketi (onerilen), sonra tasinabilir arsiv. */
    var kurulumlar = ist.kurulumlar || [];
    var arsivler = ist.paketler || [];

    var kodlar = [];
    function kodEkle(liste) {
      liste.forEach(function (p) {
        var k = platformKod(p);
        if (kodlar.indexOf(k) === -1) kodlar.push(k);
      });
    }
    kodEkle(kurulumlar);
    kodEkle(arsivler);

    /* Kullanicinin platformu once gelsin */
    kodlar.sort(function (a, b) {
      if (a === tercih && b !== tercih) return -1;
      if (b === tercih && a !== tercih) return 1;
      return 0;
    });

    var isaretVar = false;
    kodlar.forEach(function (kod) {
      var bu = kod === tercih;
      if (bu) isaretVar = true;
      kurulumlar.forEach(function (p) {
        if (platformKod(p) === kod) h += satir(p, bu, true);
      });
      arsivler.forEach(function (p) {
        if (platformKod(p) === kod) h += satir(p, bu, false);
      });
    });

    /* Yesil nokta isareti kullanildiysa anlamini yaz.
       Isaretin kendini aciklamasi gerekir; aksi halde kullanici
       neye baktigini bilmez. */
    if (isaretVar) {
      var aciklama = en()
        ? "\u25CF marks the build for the operating system you are using."
        : "\u25CF i\u015faretli sat\u0131r kulland\u0131\u011f\u0131n\u0131z i\u015fletim sistemi i\u00e7indir.";
      h += '<div class="plat-notu">' + kacir(aciklama) + "</div>";
    }

    d.innerHTML = h;
    return d;
  }

  /* SHA-256 tablosu: arsiv + kurulum paketlerinin TAMAMI listelenir */
  function shaTablo(k) {
    var tb = document.querySelector("#shaTablo tbody");
    if (!tb) return;
    var h = "";
    k.istemciler.forEach(function (ist) {
      (ist.kurulumlar || []).forEach(function (p) {
        h += "<tr><td>" + kacir(p.dosya) + "</td><td>" +
             kacir(p.sha256) + "</td></tr>";
      });
      (ist.paketler || []).forEach(function (p) {
        h += "<tr><td>" + kacir(p.dosya) + "</td><td>" +
             kacir(p.sha256) + "</td></tr>";
      });
    });
    var tam = en() ? "Full list: " : "Tam liste: ";
    h += '<tr><td colspan="2" class="sha-son">' + tam +
         '<a href="/indir/SHA256SUMS.txt">SHA256SUMS.txt</a></td></tr>';
    tb.innerHTML = h;
  }

  function hataGoster(mesaj) {
    var iz = document.getElementById("istIzgara");
    if (!iz) return;
    var bas = en() ? "Download catalogue could not be loaded."
                   : "\u0130ndirme katalo\u011fu y\u00fcklenemedi.";
    var son = en() ? " Please refresh the page or try again later."
                   : " L\u00fctfen sayfay\u0131 yenileyin veya daha sonra tekrar deneyin.";
    iz.innerHTML = '<div class="ist-not ist-hata"><strong>' + bas +
      "</strong> " + kacir(mesaj) + son + "</div>";
  }

  /* Katalogu ekrana ciz (dil degisiminde yeniden cagrilir) */
  function ciz() {
    if (!katalog) return;
    var iz = document.getElementById("istIzgara");
    if (!iz) return;

    var tercih = platformTahmin();
    iz.innerHTML = "";
    katalog.istemciler.forEach(function (ist) {
      var varMi = (ist.paketler && ist.paketler.length) ||
                  (ist.kurulumlar && ist.kurulumlar.length);
      if (varMi) iz.appendChild(kartOlustur(ist, tercih));
    });
    shaTablo(katalog);

    /* Yayin tarihi satiri */
    var eski = document.getElementById("indirTarih");
    if (eski) eski.remove();
    var not = document.querySelector("#istemciler .ist-not");
    if (not && katalog.tarih) {
      var e = document.createElement("div");
      e.id = "indirTarih";
      e.className = "indir-tarih";
      e.textContent = (en() ? "Version " : "S\u00fcr\u00fcm ") + katalog.surum +
        (en() ? " \u00b7 released " : " \u00b7 yay\u0131n tarihi ") + katalog.tarih;
      not.appendChild(e);
    }
  }

  /* ----------------------------------------------------------------
     SAYFA GENELI SURUM YAZIMI

     Surum numarasi HTML'e yedi ayri yere ELLE yazilmisti (hero
     rozeti, protokol basligi, yenilikler basligi, dpkg ornegi,
     alt bilgi...). 2.6.1 yayinlandiginda paketler 2.6.1 iken
     sitenin her yeri 2.6.0 demeye devam etti. Savunma musterisine
     giden bir sayfada indirilen dosyanin adiyla sayfadaki surumun
     ayrilmasi guven kiricidir.

     Cozum: HTML'deki degerler yalnizca JS yuklenmezse gorunecek
     YEDEK deger olarak kalir; gercek deger katalogdan (yani
     imzalanmis paketlerin kendisinden) gelir ve `data-surum-yaz`
     isaretli her ogeye yazilir. Boylece tek dogruluk kaynagi
     surumler.json olur.
  ---------------------------------------------------------------- */
  function surumYaz(surum) {
    if (!surum) return;
    var ogeler = document.querySelectorAll("[data-surum-yaz]");
    for (var i = 0; i < ogeler.length; i++) {
      var o = ogeler[i];
      var kalip = o.getAttribute("data-surum-yaz");
      /* Kalip bossa dogrudan surum yazilir; doluysa {s} yerine
         surum konur (ornek: "goktungu-dron_{s}_amd64.deb"). */
      o.textContent = (kalip && kalip.indexOf("{s}") >= 0)
        ? kalip.replace(/\{s\}/g, surum)
        : surum;
    }
    var rozet = document.getElementById("heroRozetMetin");
    if (rozet) rozet.setAttribute("data-surum", surum);

    /* dil.js sozlugundeki `{s}` yer tutuculari yalnizca `uygula`
       icinde cozulur. Katalog fetch'i dil uygulamasindan SONRA
       tamamlandigi icin bir kez daha uygulanmasi gerekir; aksi
       halde "Version {s}" ham haliyle kalirdi. */
    if (typeof window.goktunguDilUygula === "function") {
      window.goktunguDilUygula(window.goktunguDil || "tr");
    }
  }

  /* ----------------------------------------------------------------
     KATALOG KAYNAGI: /api/genel/katalog

     NEDEN DEGISTI: Bu dosya eskiden statik `/indir/surumler.json`
     dosyasini okuyordu. Surum deposu veritabanina tasindiginda o
     dosya kaldirildi; uc artik 404 donuyor. Hata `catch` dalinda
     sessizce yutuldugu icin kimse fark etmedi ve SONUC OLARAK:
       - hero rozeti HTML'deki YEDEK degerde (1.1.1) donuk kaldi,
         gercek kopru surumu 1.5.7 iken,
       - alt bilgi ve protokol basligindaki `{s}` yer tutuculari
         ham metin olarak ziyaretciye gorundu.
     Savunma musterisine giden bir sayfada yanlis surum guven kirici
     oldugu icin kaynak canli depo ucuna baglandi.

     UC SOZLESMESI (mk_sunucu.py `_u_genel_katalog`):
       { "urunler": ["kopru", ...],
         "kayitlar": [ { urun, surum, platform, dosya_ad,
                         dosya_boyut, sha256, indir_yol, ... } ] }
     Yalnizca ETKIN ve dosyasi diskte bulunan kayitlar doner.
  ---------------------------------------------------------------- */

  /* Surum dizelerini sayisal olarak tartar: "1.4.10" > "1.4.9".
     Ham metin siralamasi bu ikisini ters cevirirdi. */
  function surumTart(a, b) {
    var pa = String(a || "0").split(".");
    var pb = String(b || "0").split(".");
    var n = Math.max(pa.length, pb.length);
    for (var i = 0; i < n; i++) {
      var xa = parseInt(pa[i] || "0", 10) || 0;
      var xb = parseInt(pb[i] || "0", 10) || 0;
      if (xa !== xb) return xa - xb;
    }
    return 0;
  }

  /* Depo kayitlarini tanitim sayfasinin bekledigi istemci
     bicimine cevirir: ayni urunun en guncel surumu tek kart. */
  function kayitlariCevir(kayitlar) {
    var enYeni = {};      /* urun -> surum */
    var i, k;
    for (i = 0; i < kayitlar.length; i++) {
      k = kayitlar[i];
      if (!k || !k.urun || !k.surum) continue;
      if (!enYeni[k.urun] || surumTart(k.surum, enYeni[k.urun]) > 0) {
        enYeni[k.urun] = k.surum;
      }
    }
    var gruplar = {};
    for (i = 0; i < kayitlar.length; i++) {
      k = kayitlar[i];
      if (!k || !k.urun || !k.surum) continue;
      if (k.surum !== enYeni[k.urun]) continue;   /* eski surumler vitrinde yok */
      if (!gruplar[k.urun]) {
        gruplar[k.urun] = { tur: k.urun, surum: k.surum, kurulumlar: [] };
      }
      var win = String(k.platform || "").indexOf("win") === 0;
      gruplar[k.urun].kurulumlar.push({
        platform: win ? "Windows 10/11 kurulum sihirbazı (.exe)"
                      : "Debian / Ubuntu paketi (.deb)",
        platform_kod: win ? "windows-x64" : "linux-x64",
        dosya: k.dosya_ad,
        boyut: k.dosya_boyut,
        boyut_metni: boyutMetni(k.dosya_boyut),
        sha256: k.sha256,
        indir_yol: k.indir_yol
      });
    }
    var cikti = [];
    for (var u in gruplar) {
      if (Object.prototype.hasOwnProperty.call(gruplar, u)) {
        gruplar[u].kurulumlar.sort(function (x, y) {
          return x.platform_kod < y.platform_kod ? -1 : 1;
        });
        cikti.push(gruplar[u]);
      }
    }
    return cikti;
  }

  function boyutMetni(b) {
    var n = Number(b) || 0;
    if (n >= 1048576) return (n / 1048576).toFixed(1) + " MB";
    if (n >= 1024) return (n / 1024).toFixed(0) + " KB";
    return n + " B";
  }

  function yukle() {
    var iz = document.getElementById("istIzgara");
    /* Surum yazimi indirme izgarasi OLMAYAN sayfalarda da
       calismali (yasal sayfalarin alt bilgisi gibi). Bu yuzden
       erken cikis yalnizca kart cizimini atlar. */
    var yalnizSurum = !iz;

    fetch("/api/genel/katalog", { cache: "no-cache" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (y) {
        var kayitlar = (y && Array.isArray(y.kayitlar)) ? y.kayitlar : [];
        var istemciler = kayitlariCevir(kayitlar);

        /* Sayfadaki `{s}` yer tutuculari ve hero rozeti KOPRU
           surumunu gosterir (sahaya kurulan tek paket odur). */
        var kopru = null;
        for (var i = 0; i < istemciler.length; i++) {
          if (istemciler[i].tur === "kopru") { kopru = istemciler[i]; break; }
        }
        var gosterilen = kopru ? kopru.surum
                              : (istemciler[0] ? istemciler[0].surum : "");

        if (yalnizSurum) {
          if (gosterilen) {
            window.__GOKTUNGU_SURUM = gosterilen;
            surumYaz(gosterilen);
          }
          return;
        }
        if (!istemciler.length) {
          throw new Error(en() ? "Catalogue is empty." : "Katalog bo\u015f.");
        }
        katalog = { surum: gosterilen, istemciler: istemciler };
        window.__GOKTUNGU_SURUM = gosterilen;
        surumYaz(gosterilen);
        ciz();
      })
      .catch(function (e) {
        /* Surum yazimi sessizce atlanabilir ama sebebi konsola
           dusmelidir; bu hatanin sessizce yutulmasi yukaridaki
           donuk-surum kusurunun aylarca fark edilmemesine yol acti. */
        if (window.console && console.warn) {
          console.warn("[indir] katalog okunamadi:", e && e.message);
        }
        if (yalnizSurum) return;
        hataGoster(e && e.message ? e.message : "Bilinmeyen hata.");
      });
  }

  /* Dil degistiginde kartlari yeniden ciz */
  document.addEventListener("dilDegisti", function () {
    if (katalog) ciz();
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", yukle);
  } else {
    yukle();
  }
})();
