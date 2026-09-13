// ============================================================
// GOKTUNGU GCS — SAYAC (KRONOMETRE) WIDGET
// v2.4.33
//
// Kullanici istegi:
//   "Yeni bir widget ekle, sayac ismin, play dugmesine basinca mili
//    saniyelerle birlikte zaman sayaci baslasin, pause dugmesine
//    basinca dursun play dugmesi yansin, stop dugmesine basinca
//    sifirlasin."
//
// TASARIM KARARLARI
// -----------------
// 1) ZAMAN KAYNAGI: `performance.now()` kullanilir, `Date.now()`
//    DEGIL. Sistem saati NTP ile duzeltilebilir veya kullanici elle
//    degistirebilir; bu durumda `Date.now()` tabanli bir kronometre
//    geriye siçrar. `performance.now()` monotondur.
//
// 2) SAYIM YONTEMI: Gecen sure her karede BASLANGIC DAMGASINDAN
//    FARK olarak hesaplanir (`simdi - baslangic`), zamanlayicida
//    birikimli toplama YAPILMAZ. setInterval gecikmeleri birikimli
//    toplamda kayma yaratir; fark yontemi sekmeler arka plana
//    alinsa bile dogru kalir.
//
// 3) CIZIM DONGUSU: `requestAnimationFrame` kullanilir. Milisaniye
//    gosterildigi icin ~60 Hz tazeleme gerekir; `setInterval(…, 10)`
//    tarayici tarafindan kisilir ve gorsel takilma olusur.
//    Sekme arka plandayken rAF durur — sorun degil, cunku deger
//    fark yontemiyle hesaplandigi icin sekmeye donuldugunde dogru
//    degeri gosterir.
//
// 4) DURAKLATMADA GECEN SURE: `birikmis` degiskeninde saklanir.
//    Yeniden basladiginda `baslangic = performance.now() - birikmis`
//    yapilir; boylece tek bir kod yolu hem ilk baslatmayi hem
//    devam ettirmeyi karsilar.
//
// 5) KALICILIK: Kronometre durumu KASITLI olarak kalici DEGIL.
//    Sayfa yenilendiginde sifirlanir; arka planda calismaya devam
//    eden bir kronometre yanlis olcum izlenimi verir.
// ============================================================

(function(){
  "use strict";

  const ID = "sayac";

  let ogeler = null;      // { ss, ms, tur, turListe, btnPlay, ... }
  let cerceve = null;     // requestAnimationFrame kimligi
  let calisiyor = false;
  let baslangic = 0;      // performance.now() damgasi
  let birikmis = 0;       // duraklatmalarda gecen toplam ms
  let turlar = [];        // [{ no, toplam, fark }]

  function ingilizceMi(){
    try {
      if (typeof aktifDil !== "undefined") return String(aktifDil).toLowerCase().startsWith("en");
      const d = localStorage.getItem("gcs_dil");
      return !!(d && d.toLowerCase().startsWith("en"));
    } catch (e) { return false; }
  }

  function ikiHane(n){ return (n < 10 ? "0" : "") + n; }

  // ----------------------------------------------------------
  // BICIMLEME
  // Sure iki parcaya ayrilir: buyuk okuma (SS:DD:SS) ve milisaniye.
  // Milisaniye ayri bir oge oldugu icin daha kucuk puntoda ve soluk
  // renkte cizilebilir; boylece asil okuma goz yormaz.
  // ----------------------------------------------------------
  function bicimle(ms){
    if (ms < 0) ms = 0;
    const tumSaniye = Math.floor(ms / 1000);
    const saat = Math.floor(tumSaniye / 3600);
    const dakika = Math.floor((tumSaniye % 3600) / 60);
    const saniye = tumSaniye % 60;
    // Milisaniye 2 hane (yuzde-saniye): 3 hane 60 Hz'de okunamayacak
    // kadar hizli degisir ve gorsel gurultu yaratir.
    const yuzde = Math.floor((ms % 1000) / 10);
    const buyuk = (saat > 0)
      ? (saat + ":" + ikiHane(dakika) + ":" + ikiHane(saniye))
      : (ikiHane(dakika) + ":" + ikiHane(saniye));
    return { buyuk: buyuk, ms: "." + ikiHane(yuzde) };
  }

  function gecenSure(){
    return calisiyor ? (performance.now() - baslangic) : birikmis;
  }

  // ----------------------------------------------------------
  // GOVDE
  // ----------------------------------------------------------
  function govdeKur(govde, api){
    govde.classList.add("sayac-govde");

    const sarmal = document.createElement("div");
    sarmal.className = "sayac-sarmal";

    // --- Okuma ---
    const okuma = document.createElement("div");
    okuma.className = "sayac-okuma";
    const ss = document.createElement("span");
    ss.className = "sayac-buyuk";
    ss.textContent = "00:00";
    const msO = document.createElement("span");
    msO.className = "sayac-ms";
    msO.textContent = ".00";
    okuma.appendChild(ss);
    okuma.appendChild(msO);
    sarmal.appendChild(okuma);

    // --- Durum satiri ---
    const durum = document.createElement("div");
    durum.className = "sayac-durum";
    durum.textContent = "";
    sarmal.appendChild(durum);

    // --- Dugmeler ---
    const dugmeler = document.createElement("div");
    dugmeler.className = "sayac-dugmeler";

    function dugme(sinif, ikon, baslik){
      const b = document.createElement("button");
      b.type = "button";
      b.className = "sayac-btn " + sinif;
      b.innerHTML = '<i class="' + ikon + '"></i>';
      b.title = baslik;
      // pointerdown DEGIL click: widget tasima surukleyicisi
      // pointerdown'i yakalar; click guvenli olan olaydir.
      dugmeler.appendChild(b);
      return b;
    }

    const en = ingilizceMi();
    const btnPlay = dugme("sayac-btn-play", "fa-solid fa-play",
                          en ? "Start" : "Ba\u015flat");
    const btnPause = dugme("sayac-btn-pause", "fa-solid fa-pause",
                           en ? "Pause" : "Duraklat");
    const btnStop = dugme("sayac-btn-stop", "fa-solid fa-stop",
                          en ? "Reset" : "S\u0131f\u0131rla");
    const btnTur = dugme("sayac-btn-tur", "fa-solid fa-flag",
                         en ? "Lap" : "Tur");
    sarmal.appendChild(dugmeler);

    // --- Tur listesi ---
    const turListe = document.createElement("div");
    turListe.className = "sayac-tur-liste";
    sarmal.appendChild(turListe);

    govde.appendChild(sarmal);

    ogeler = { ss, ms: msO, durum, turListe,
               btnPlay, btnPause, btnStop, btnTur };

    btnPlay.addEventListener("click", (ev) => { ev.stopPropagation(); baslat(); });
    btnPause.addEventListener("click", (ev) => { ev.stopPropagation(); duraklat(); });
    btnStop.addEventListener("click", (ev) => { ev.stopPropagation(); sifirla(); });
    btnTur.addEventListener("click", (ev) => { ev.stopPropagation(); turEkle(); });

    dugmeDurumu();
    ciz();
  }

  // ----------------------------------------------------------
  // DENETIM
  // ----------------------------------------------------------
  function baslat(){
    if (calisiyor) return;
    // birikmis cikarilarak devam ettirilir; ilk baslatmada 0'dir
    baslangic = performance.now() - birikmis;
    calisiyor = true;
    dongubaslat();
    dugmeDurumu();
  }

  function duraklat(){
    if (!calisiyor) return;
    birikmis = performance.now() - baslangic;
    calisiyor = false;
    donguDurdur();
    ciz();            // duraklatilan tam degeri yaz
    dugmeDurumu();
  }

  function sifirla(){
    calisiyor = false;
    donguDurdur();
    birikmis = 0;
    baslangic = 0;
    turlar = [];
    turListesiCiz();
    ciz();
    dugmeDurumu();
  }

  function turEkle(){
    // Tur yalnizca sayim surerken anlamlidir
    if (!calisiyor) return;
    const toplam = gecenSure();
    const oncekiToplam = turlar.length ? turlar[turlar.length - 1].toplam : 0;
    turlar.push({ no: turlar.length + 1, toplam: toplam,
                  fark: toplam - oncekiToplam });
    turListesiCiz();
  }

  // ----------------------------------------------------------
  // CIZIM
  // ----------------------------------------------------------
  function ciz(){
    if (!ogeler) return;
    const b = bicimle(gecenSure());
    ogeler.ss.textContent = b.buyuk;
    ogeler.ms.textContent = b.ms;
  }

  function dongubaslat(){
    if (cerceve !== null) return;
    const adim = function(){
      ciz();
      // calisiyor bayragi dongu icinde denetlenir: duraklatma
      // aninda ek bir iptal cagrisina gerek kalmaz
      cerceve = calisiyor ? requestAnimationFrame(adim) : null;
    };
    cerceve = requestAnimationFrame(adim);
  }

  function donguDurdur(){
    if (cerceve !== null){ cancelAnimationFrame(cerceve); cerceve = null; }
  }

  // Dugme gorunurlugu: kullanici istegi geregi
  //   - sayim sureken PAUSE gorunur, PLAY gizli
  //   - duraklatildiginda PLAY "yanar" (vurgulu) ve PAUSE gizlenir
  function dugmeDurumu(){
    if (!ogeler) return;
    const en = ingilizceMi();
    ogeler.btnPlay.style.display = calisiyor ? "none" : "";
    ogeler.btnPause.style.display = calisiyor ? "" : "none";
    // Duraklatilmis ve sifirdan buyukse PLAY vurgulu yanar
    const duraklatilmis = (!calisiyor && birikmis > 0);
    ogeler.btnPlay.classList.toggle("sayac-yanan", duraklatilmis);
    ogeler.btnPlay.title = duraklatilmis
      ? (en ? "Resume" : "Devam et")
      : (en ? "Start" : "Ba\u015flat");
    // STOP yalnizca sifirlanacak bir sey varken etkin
    const sifirlanabilir = (calisiyor || birikmis > 0);
    ogeler.btnStop.disabled = !sifirlanabilir;
    ogeler.btnTur.disabled = !calisiyor;

    ogeler.durum.textContent = calisiyor
      ? (en ? "RUNNING" : "\u00c7ALI\u015eIYOR")
      : (duraklatilmis ? (en ? "PAUSED" : "DURAKLATILDI")
                       : (en ? "READY" : "HAZIR"));
    ogeler.durum.classList.toggle("sayac-durum-calisiyor", calisiyor);
    ogeler.durum.classList.toggle("sayac-durum-duraklatildi", duraklatilmis);
  }

  function turListesiCiz(){
    if (!ogeler) return;
    ogeler.turListe.textContent = "";
    if (!turlar.length){
      ogeler.turListe.classList.remove("sayac-tur-dolu");
      return;
    }
    ogeler.turListe.classList.add("sayac-tur-dolu");
    // En yeni tur en ustte
    for (let i = turlar.length - 1; i >= 0; i--){
      const t = turlar[i];
      const s = document.createElement("div");
      s.className = "sayac-tur-satir";
      const no = document.createElement("span");
      no.className = "sayac-tur-no";
      no.textContent = "#" + t.no;
      const fark = document.createElement("span");
      fark.className = "sayac-tur-fark";
      const bf = bicimle(t.fark);
      fark.textContent = bf.buyuk + bf.ms;
      const toplam = document.createElement("span");
      toplam.className = "sayac-tur-toplam";
      const bt = bicimle(t.toplam);
      toplam.textContent = bt.buyuk + bt.ms;
      s.appendChild(no);
      s.appendChild(fark);
      s.appendChild(toplam);
      ogeler.turListe.appendChild(s);
    }
  }

  // ----------------------------------------------------------
  // YASAM DONGUSU
  // Widget kapatilirsa SAYIM DEVAM EDER, yalnizca cizim durur:
  // operator widget'i kapatip yeniden actiginda olcumunu kaybetmez.
  // ----------------------------------------------------------
  function ac(){
    dugmeDurumu();
    turListesiCiz();
    if (calisiyor) dongubaslat();
    else ciz();
  }

  function kapa(){
    donguDurdur();
  }

  function dilTazele(){
    if (!ogeler) return;
    const en = ingilizceMi();
    ogeler.btnPause.title = en ? "Pause" : "Duraklat";
    ogeler.btnStop.title = en ? "Reset" : "S\u0131f\u0131rla";
    ogeler.btnTur.title = en ? "Lap" : "Tur";
    dugmeDurumu();
  }

  // ----------------------------------------------------------
  // KAYIT
  // Boyut: diger widget'larla ayni genislik (226). Yukseklik tur
  // listesine yer acmak icin 224 -> 208; okuma + dugmeler + 3-4 tur
  // satiri bu yuksekliğe sigar.
  // ----------------------------------------------------------
  function kaydol(){
    if (!window.Widget) return;
    window.Widget.kaydet({
      id: ID,
      // v2.4.34: `baslik` yalniz ilk cizimde kullanilan yedektir;
      // gorunen metin `baslikAnahtar` ile data-i18n uzerinden cevrilir.
      baslik: (typeof D === "function" && D().wgSayac) || "SAYA\u00c7",
      baslikAnahtar: "wgSayac",
      genislik: 226,
      yukseklik: 224,
      govdeKur: govdeKur,
      ac: ac,
      kapa: kapa,
      dilTazele: dilTazele,
    });
  }

  window.WidgetSayac = { kaydol: kaydol, ID: ID };
})();
