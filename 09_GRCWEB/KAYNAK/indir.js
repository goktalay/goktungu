/* =================================================================
   GOKTUNGU v2.4.53 - Indirme merkezi
   VEILOX Savunma Anonim Sirketi

   Merkez sunucunun genel katalog ucundan (/api/genel/katalog) urun
   listesini okur, indirme kartlarini ve SHA-256 tablosunu olusturur.

   ------------------------------------------------------------------
   NEDEN YENIDEN YAZILDI
   ------------------------------------------------------------------
   Onceki surum statik bir /indir/surumler.json dosyasi okuyordu ve
   katalog semasi "uc ayri saha istemcisi" (dron/radar/ai) varsayimi
   uzerine kuruluydu.  Iki sey degisti:

     1) Statik dosya artik YOK (HTTP 404 ile olculdu).  Surum deposu
        veritabani tablidir; kayitlar `surumler` tablosunda tutulur ve
        paketler Ed25519 ile imzalanir.  Tek dogruluk kaynagi
        veritabanidir, elle guncellenen bir JSON dosyasi degil.

     2) Dagitim modeli degisti: kullanicinin indirdigi ANA urun artik
        `kopru` (Python kopru yazilimi, yerel web paneli + bes servis).
        Komuta kontrol arayuzu merkezde /app/ altinda sunulur; `gcs`
        paketi yalnizca kendi sunucusunu isleten kurumlar icindir.

   Yeni sema (bkz. mk_sunucu.py:_u_genel_katalog):

     { "urunler": ["gcs", ...],
       "kayitlar": [ { urun, surum, platform, kanal, paket_tur,
                       dosya_ad, dosya_boyut, sha256, asgari_surum,
                       notlar, yayin_ts, indir_yol, dosya_var } ] }

   Onemli fark: indirme yolu artik kayitla birlikte gelir
   (`indir_yol` = /indir/gcs/2.4.53/dosya.tar.gz).  Onceki surumde yol
   istemci tarafinda "/indir/" + dosya_ad olarak KURULUYORDU; bu uc
   duzeyli depo yerlesiminde 404 uretirdi.

   ------------------------------------------------------------------
   TAM PAKET / GUNCELLEME PAKETI AYRIMI
   ------------------------------------------------------------------
   Depo her surum icin iki paket tasir:

     tam        -> sifirdan kurulum (harita onbellegi, SITL ikilileri,
                   modeller dahil; on MB duzeyinde)
     guncelleme -> yalnizca degisen dosyalar (yuz KB duzeyinde);
                   mevcut kurulumun uzerine uygulanir, kullanici
                   verisi (veritabani, ayarlar, harita onbellegi)
                   korunur

   Ayrim gorunur kilinmali: kullanici yanlis paketi indirirse ya
   gereksiz 10 MB indirir ya da calisan kurulumunu bozar.  Bu yuzden
   `asgari_surum` alani da yazilir -- guncelleme paketi yalnizca o
   surum ve ustune uygulanabilir.
   ================================================================= */
(function () {
  "use strict";

  /* Urun kimliginden gorsel simge.  Depo yedi urun tanir
     (gcs, sunucu, dron, video, radar, ai, kopru); su an yalnizca gcs
     yayinda, digerleri katalogda gorunurse dogru simgeyi alir. */
  var SIMGE = {
    gcs: "\u25C9",      /* ◉ komuta kontrol arayuzu */
    sunucu: "\u25A6",   /* ▦ */
    kopru: "\u21C4",    /* ⇄ ters baglanti */
    dron: "\u25B2",     /* ▲ */
    radar: "\u25CE",    /* ◎ */
    video: "\u25B6",    /* ▶ */
    ai: "\u2699"        /* ⚙ */
  };

  /* Paket turu gosterim sirasi: tam paket once (yeni kurulum yapan
     ziyaretci cogunluktur), guncelleme ikincil satir olarak. */
  var TUR_SIRA = { tam: 0, guncelleme: 1 };

  var katalog = null;   /* son yuklenen katalog (yeniden cizim icin) */

  /* ---------------- Dil yardimcilari ---------------- */
  function dil() { return window.goktunguDil === "en" ? "en" : "tr"; }
  function en() { return dil() === "en"; }

  /* Sozlukten anahtar okur; yoksa yedek metni dondurur. */
  function ce(anahtar, yedek) {
    if (!en()) return yedek;
    var s = window.goktunguSozluk;
    return (s && s[anahtar] != null) ? s[anahtar] : yedek;
  }

  function kacir(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  /* Surum karsilastirmasi: "2.4.53" > "2.4.9" dogru sonuclanmali.
     Dizgi karsilastirmasi kullanilamaz cunku karakter duzeyinde
     "9" > "5" oldugu icin 2.4.9'u 2.4.53'ten yeni sanardi. */
  function surumKiyas(a, b) {
    var pa = String(a || "").split(".");
    var pb = String(b || "").split(".");
    var n = Math.max(pa.length, pb.length);
    for (var i = 0; i < n; i++) {
      var x = parseInt(pa[i], 10) || 0;
      var y = parseInt(pb[i], 10) || 0;
      if (x !== y) return x - y;
    }
    return 0;
  }

  /* Bayt -> okunabilir metin.  Katalog ham bayt dondurur; sunucuda
     bicimlendirmek yerine burada yapilir cunku ondalik isareti dile
     baglidir (TR "9,4 MB" / EN "9.4 MB"). */
  function boyutMetni(bayt) {
    var b = Number(bayt);
    if (!isFinite(b) || b <= 0) return "\u2014";
    var birim = ["B", "KB", "MB", "GB"];
    var i = 0;
    while (b >= 1024 && i < birim.length - 1) { b /= 1024; i++; }
    var s = b < 10 ? b.toFixed(1) : String(Math.round(b));
    if (!en()) s = s.replace(".", ",");
    return s + " " + birim[i];
  }

  /* ISO zaman damgasindan tarih (2026-08-13T15:18:04+03:00 -> 2026-08-13) */
  function tarihMetni(ts) {
    var m = String(ts == null ? "" : ts).match(/^(\d{4})-(\d{2})-(\d{2})/);
    return m ? m[0] : "";
  }

  /* Urun adi.  Katalogun `notlar` alani o SURUME ozgu degisiklik
     notudur, urun tanimi degildir; bu yuzden adlar burada tutulur. */
  var URUN_AD = {
    kopru: "G\u00d6KTUNGU K\u00f6pr\u00fc Yaz\u0131l\u0131m\u0131",
    gcs: "Komuta Kontrol Yaz\u0131l\u0131m\u0131",
    sunucu: "Merkez Sunucu",
    dron: "Dron \u0130stemcisi",
    video: "Video \u0130stemcisi",
    radar: "Radar \u0130stemcisi",
    ai: "Yapay Zek\u00e2 \u0130stemcisi"
  };

  var URUN_ACIKLAMA = {
    kopru: "Saha bilgisayar\u0131nda \u00e7al\u0131\u015fan k\u00f6pr\u00fc " +
           "yaz\u0131l\u0131m\u0131. Yerel bir web paneli a\u00e7ar; be\u015f " +
           "servisi (Dron, Yapay Zek\u00e2, Video, GroundGCC, Radar) " +
           "ba\u015flat\u0131r, durdurur ve konsollar\u0131n\u0131 " +
           "g\u00f6sterir. Dron, kamera ve radar ba\u011flant\u0131lar\u0131n\u0131 " +
           "merkeze giden tek \u015fifreli kanaldan ta\u015f\u0131r. " +
           "Python 3.11 gerekir.",
    gcs: "Harita, telemetri, g\u00f6rev y\u00f6netimi, kamera " +
         "ak\u0131\u015flar\u0131 ve u\u00e7u\u015f raporlamas\u0131n\u0131 " +
         "ta\u015f\u0131yan komuta kontrol yaz\u0131l\u0131m\u0131. " +
         "Normalde merkezden sunulur; bu paket kendi sunucusunu " +
         "i\u015fleten kurumlar i\u00e7indir.",
    sunucu: "\u00c7ok kirac\u0131l\u0131 merkez sunucu yaz\u0131l\u0131m\u0131."
  };

  function urunAd(urun) {
    return ce("indir." + urun, URUN_AD[urun] || urun.toUpperCase());
  }

  function urunAciklama(urun) {
    return ce("indir." + urun + "alt", URUN_ACIKLAMA[urun] || "");
  }

  /* Paket turu etiketi */
  function turEtiket(t) {
    if (t === "tam") return en() ? "Full installation" : "Tam kurulum";
    if (t === "guncelleme") {
      return en() ? "Update package" : "G\u00fcncelleme paketi";
    }
    return t;
  }

  /* Platform etiketi.  Depo "ortak" degerini tek arsivin her iki
     isletim sisteminde calistigi urunler icin kullanir. */
  function platformEtiket(p) {
    if (p === "ortak") {
      return en() ? "Windows \u00b7 Ubuntu \u00b7 portable archive"
                  : "Windows \u00b7 Ubuntu \u00b7 ta\u015f\u0131nabilir ar\u015fiv";
    }
    if (p === "windows") return en() ? "Windows (64-bit)" : "Windows (64 bit)";
    if (p === "linux") {
      return en() ? "Ubuntu / Linux (64-bit)" : "Ubuntu / Linux (64 bit)";
    }
    if (p === "linux-arm64") return "Ubuntu / Linux (ARM64)";
    return p;
  }

  /* Isletim sistemi simgesi.  Metin etiketinin yaninda gorsel bir
     ayirt edici olmadan iki indirme satiri birbirine cok benziyor;
     kullanici yanlis paketi indirdiginde bunu ancak kurulum
     basarisiz olunca anliyor. */
  function platformSimge(p) {
    if (p === "windows") return "\u229E";      /* pencere */
    if (p === "linux" || p === "linux-arm64") return "\u25B2";  /* ucgen */
    return "\u25A0";
  }

  /* Ziyaretcinin isletim sistemini tahmin eder.  Yalnizca ONERI
     amaclidir: yanlis tahmin kullanicinin dogru paketi indirmesini
     engellemez, iki satir da her zaman gorunur kalir. */
  function ziyaretciPlatformu() {
    var u = "";
    try {
      u = (navigator.userAgent || "") + " " + (navigator.platform || "");
    } catch (e) { return null; }
    u = u.toLowerCase();
    /* Android da "linux" tasir; koprü mobil cihaza kurulmadigi icin
       tahmin edilmez. */
    if (u.indexOf("android") !== -1) return null;
    if (u.indexOf("win") !== -1) return "windows";
    if (u.indexOf("linux") !== -1 || u.indexOf("ubuntu") !== -1) return "linux";
    return null;
  }

  /* ----------------------------------------------------------------
     TEK INDIRME SATIRI

     Yerlesim iki katmanlidir.  Tek satirda tur etiketi + onerilen
     etiketi + boyut + buton yan yana dizildiginde uzun metin 321px'lik
     karti tasiriyor, buton diger ogelerin uzerine biniyordu.  Bu
     yuzden:
       ust satir : paket turu + onerilen etiketi
       alt satir : boyut + indirme butonu
     ---------------------------------------------------------------- */
  function satir(k, onerilen) {
    var indirMetni = en() ? "\u2193 Download" : "\u2193 \u0130ndir";
    var onerilenMetni = en() ? "recommended" : "\u00f6nerilen";

    var h = '<div class="indir-satir' +
            (onerilen ? " onerilen" : " ikincil") + '">';

    /* Platform etiketi SATIR BAZINDA yazilir.  1.2.x'e kadar tek
       `ortak` arsiv dagitildigi icin platform kart basliginda bir kez
       yazmak yeterliydi.  1.3.0'dan itibaren Windows ve Ubuntu
       paketleri AYRI: kurulum betikleri, servis yontemi ve ikon
       bicimi farkli.  Platformu satirda yazmazsak iki ayni gorunumlu
       "Indir" dugmesi kalir ve kullanici hangisinin kendi isletim
       sistemine ait oldugunu goremez. */
    h += '<div class="ust-sat">';
    h += '<span class="plat">' + kacir(platformSimge(k.platform)) + " " +
         kacir(platformEtiket(k.platform)) + "</span>";
    if (onerilen) {
      h += '<span class="onerilen-et">' + onerilenMetni + "</span>";
    }
    h += "</div>";

    /* Guncelleme paketinin asgari surum kosulu belirtilmezse kullanici
       2.4.24 kurulumuna 2.4.53 yamasini uygulamaya kalkip calisan
       sistemini bozabilir. */
    if (k.paket_tur === "guncelleme" && k.asgari_surum) {
      var asg = en()
        ? "Requires version " + k.asgari_surum + " or later"
        : "S\u00fcr\u00fcm " + k.asgari_surum + " ve \u00fczeri gerekir";
      h += '<div class="asgari-not">' + kacir(asg) + "</div>";
    }

    h += '<div class="alt-sat">';
    h += '<span class="boyut">' + kacir(boyutMetni(k.dosya_boyut)) + "</span>";
    h += '<a class="dgi' + (onerilen ? "" : " dgi-ikincil") +
         '" href="' + kacir(k.indir_yol) + '" ' +
         'download title="SHA-256: ' + kacir(k.sha256) + '">' +
         indirMetni + "</a>";
    h += "</div>";

    h += "</div>";
    return h;
  }

  /* Bir urunun kartini olusturur */
  function kartOlustur(urun, kayitlar) {
    var d = document.createElement("div");
    d.className = "ist-kart " + urun;

    var surum = kayitlar.length ? kayitlar[0].surum : "";
    var surumMetni = en() ? "version " : "s\u00fcr\u00fcm ";

    var h = "";
    h += '<div class="ust">';
    h += '<div class="simge">' + (SIMGE[urun] || "\u25A0") + "</div>";
    h += "<div>";
    h += "<h3>" + kacir(urunAd(urun)) + "</h3>";
    h += '<div class="surum">goktungu-' + kacir(urun) + " &middot; " +
         surumMetni + kacir(surum) + "</div>";
    h += "</div></div>";
    h += "<p>" + kacir(urunAciklama(urun)) + "</p>";

    /* Siralama: once paket turu (tam kurulum en uste), sonra
       ZIYARETCININ isletim sistemi.  Windows kullanicisina Windows
       paketini ilk sirada gostermek, listeyi tarayip dogru satiri
       aramaktan daha az hata uretir. */
    var benim = ziyaretciPlatformu();
    var sirali = kayitlar.slice().sort(function (a, b) {
      var pa = TUR_SIRA[a.paket_tur];
      var pb = TUR_SIRA[b.paket_tur];
      pa = (pa == null ? 9 : pa);
      pb = (pb == null ? 9 : pb);
      if (pa !== pb) return pa - pb;
      if (benim) {
        var ba = (a.platform === benim) ? 0 : 1;
        var bb = (b.platform === benim) ? 0 : 1;
        if (ba !== bb) return ba - bb;
      }
      return String(a.platform).localeCompare(String(b.platform));
    });

    /* Kart basligindaki toplu platform satiri KALDIRILDI.  Paketler
       platforma gore ayrildiktan sonra bu satir "Windows (64 bit) ·
       Ubuntu / Linux (64 bit)" yaziyordu; asagida iki ayri indirme
       satiri varken bu, tek paketin her ikisinde de calistigi
       izlenimini veriyordu.  Platform artik her satirin kendisinde. */

    /* "onerilen" yalnizca ziyaretcinin sistemine ait tam kuruluma
       verilir.  Her iki tam kuruluma birlikte verilseydi "onerilen"
       sozcugu ayirt etme gucunu kaybederdi. */
    sirali.forEach(function (k) {
      var tam = (k.paket_tur === "tam");
      var oner = tam && (!benim || k.platform === benim ||
                         k.platform === "ortak");
      h += satir(k, oner);
    });

    d.innerHTML = h;
    return d;
  }

  /* SHA-256 tablosu: katalogdaki TUM paketler */
  function shaTablo(k) {
    var tb = document.querySelector("#shaTablo tbody");
    if (!tb) return;
    var h = "";
    (k.kayitlar || []).forEach(function (kayit) {
      h += "<tr><td>" + kacir(kayit.dosya_ad) + "</td><td>" +
           kacir(kayit.sha256) + "</td></tr>";
    });
    tb.innerHTML = h || '<tr><td colspan="2">\u2014</td></tr>';
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
    iz.innerHTML = "";

    /* Urun bazinda grupla; her urun icin YALNIZCA en yeni surumun
       paketleri gosterilir.  Eski surumleri listelemek indirme
       ekranini kalabaliklastirir ve kullanicinin yanlislikla geri
       surum indirmesine yol acar. */
    var gruplar = {};
    (katalog.kayitlar || []).forEach(function (k) {
      if (!gruplar[k.urun]) gruplar[k.urun] = [];
      gruplar[k.urun].push(k);
    });

    /* Ana urun sirasi.  Sahaya kurulan tek paket kopru oldugu icin o
       ilk sirada gelir; katalog ileride baska urun tasirsa alfabetik
       sirayla arkaya dizilir.  (Onceki surumde `gcs` ilk siraya
       zorlaniyordu; artik GCS tanitim vitrininde hic gorunmez -- bkz.
       mk_depo.GENEL_GIZLI_URUNLER.) */
    var urunler = Object.keys(gruplar).sort(function (a, b) {
      if (a === "kopru") return -1;
      if (b === "kopru") return 1;
      return a.localeCompare(b);
    });

    urunler.forEach(function (urun) {
      var kayitlar = gruplar[urun];
      var enYeni = kayitlar[0].surum;
      kayitlar.forEach(function (k) {
        if (surumKiyas(k.surum, enYeni) > 0) enYeni = k.surum;
      });
      var secili = kayitlar.filter(function (k) { return k.surum === enYeni; });
      if (secili.length) iz.appendChild(kartOlustur(urun, secili));
    });

    shaTablo(katalog);

    /* Yayin tarihi satiri */
    var eski = document.getElementById("indirTarih");
    if (eski) eski.remove();
    var not = document.querySelector("#istemciler .ist-not");
    var ilk = (katalog.kayitlar || [])[0];
    if (not && ilk) {
      var t = tarihMetni(ilk.yayin_ts);
      if (t) {
        var e = document.createElement("div");
        e.id = "indirTarih";
        e.className = "indir-tarih";
        e.textContent = (en() ? "Version " : "S\u00fcr\u00fcm ") + ilk.surum +
          (en() ? " \u00b7 released " : " \u00b7 yay\u0131n tarihi ") + t;
        not.appendChild(e);
      }
    }
  }

  /* ----------------------------------------------------------------
     SAYFA GENELI SURUM YAZIMI

     Surum numarasi HTML'e birden fazla yere ELLE yazilmisti (hero
     rozeti, yenilikler basligi, kurulum ornegi, alt bilgi...).  Yeni
     surum yayinlandiginda hepsini elle degistirmek gerekiyordu; biri
     atlandiginda sayfa eski surumu yazip yeni paketi indiren bir hale
     geliyordu.  Savunma musterisine giden bir sayfada indirilen
     dosyanin adiyla sayfadaki surumun ayrilmasi guven kiricidir.

     Cozum: HTML'deki degerler yalnizca JS yuklenmezse gorunecek YEDEK
     deger olarak kalir; gercek deger katalogdan (yani imzalanmis
     paketlerin kendisinden) gelir ve `data-surum-yaz` isaretli her
     ogeye yazilir.
     ---------------------------------------------------------------- */
  /* Bir urunun (surum hattinin) en yeni surumunu dondurur.  Katalog
     henuz yuklenmediyse veya urun katalogda yoksa bos dize doner ve
     cagiran taraf varsayilana duser. */
  function surumIcin(urun) {
    if (!urun) return "";
    var h = window.__GOKTUNGU_SURUMLER;
    return (h && h[urun]) ? h[urun] : "";
  }

  function surumYaz(surum) {
    if (!surum) return;
    var ogeler = document.querySelectorAll("[data-surum-yaz]");
    for (var i = 0; i < ogeler.length; i++) {
      var o = ogeler[i];
      var kalip = o.getAttribute("data-surum-yaz");
      /* Oge belirli bir surum hattini isteyebilir (ornek: kurulum
         komutu kopru paketini anlatir, GCS surumunu degil).  Hat
         belirtilmemisse varsayilan surum kullanilir. */
      var s = surumIcin(o.getAttribute("data-surum-urun")) || surum;
      /* Kalip bossa dogrudan surum yazilir; doluysa {s} yerine surum
         konur (ornek: "goktungu-guncelleme-{s}.tar.gz"). */
      o.textContent = (kalip && kalip.indexOf("{s}") >= 0)
        ? kalip.replace(/\{s\}/g, s)
        : s;
    }
    var rozet = document.getElementById("heroRozetMetin");
    if (rozet) rozet.setAttribute("data-surum", surum);

    /* dil.js sozlugundeki `{s}` yer tutuculari yalnizca `uygula`
       icinde cozulur.  Katalog fetch'i dil uygulamasindan SONRA
       tamamlandigi icin bir kez daha uygulanmasi gerekir; aksi halde
       "Version {s}" ham haliyle kalirdi. */
    if (typeof window.goktunguDilUygula === "function") {
      window.goktunguDilUygula(window.goktunguDil || "tr");
    }
  }

  function yukle() {
    var iz = document.getElementById("istIzgara");
    /* Surum yazimi indirme izgarasi OLMAYAN sayfalarda da calismali
       (yasal sayfalarin alt bilgisi gibi).  Bu yuzden erken cikis
       yalnizca kart cizimini atlar. */
    var yalnizSurum = !iz;

    fetch("/api/genel/katalog", { cache: "no-cache" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (k) {
        if (!k || !Array.isArray(k.kayitlar)) {
          throw new Error(en() ? "Invalid catalogue."
                              : "Ge\u00e7ersiz katalog.");
        }

        /* IKI HATLI SURUM YONETIMI
           Katalogda birden fazla urun var (gcs = merkezdeki komuta
           kontrol arayuzu, kopru = sahaya kurulan kopru yazilimi) ve
           surum hatlari BAGIMSIZ ilerler.  Tek bir global surum
           yazmak, kopruye ait metinlere GCS numarasini basiyordu;
           kurulum komutu bu yuzden var olmayan bir dosya adi
           uretiyordu (goktungu-kopru-2.4.52.tar.gz).
           Bu nedenle her urunun en yeni surumu ayri tutulur; oge
           hangi hatti istedigini `data-surum-urun` ile bildirir. */
        var surumler = {};
        k.kayitlar.forEach(function (x) {
          if (!x || !x.urun || !x.surum) return;
          var v = surumler[x.urun];
          if (!v || surumKiyas(x.surum, v) > 0) surumler[x.urun] = x.surum;
        });
        window.__GOKTUNGU_SURUMLER = surumler;

        /* Varsayilan (urun belirtmeyen ogeler icin): ana urun KOPRU,
           cunku sahaya inen tek paket odur.  Kopru katalogda yoksa en
           yeni surum ne ise o kullanilir. */
        var surum = surumler.kopru || "";
        if (!surum) {
          k.kayitlar.forEach(function (x) {
            if (!surum || surumKiyas(x.surum, surum) > 0) surum = x.surum;
          });
        }

        window.__GOKTUNGU_SURUM = surum || "";
        surumYaz(surum);

        if (yalnizSurum) return;

        if (!k.kayitlar.length) {
          throw new Error(en() ? "Catalogue is empty." : "Katalog bo\u015f.");
        }
        katalog = k;
        ciz();
      })
      .catch(function (e) {
        if (yalnizSurum) return;   /* surum yazimi kritik degil */
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
