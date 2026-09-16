// ================================================================
// GOKTUNGU - MJPEG YENIDEN DENEME YARDIMCISI          (v2.4.33 - YENI)
// ================================================================
// SORUN
// -----
// Kullanici uzak bir MJPEG kamerasi ekledigi zaman goruntu hic
// gelmiyor, kutuda kalici olarak "YAYIN ALINAMIYOR" yaziyordu.
//
// Olculen kok neden (bkz. BULGU_MJPEG.md):
//   - Uzak 1920x1080 MJPEG kaynaginda ffmpeg'in ILK KAREYI uretmesi
//     13.6 sn suruyordu (v2.4.33'te ffmpeg secenekleri duzeltilerek
//     4.6 sn'ye indirildi, ama ag gecikmesine bagli oldugu icin tek
//     basina yeterli degil).
//   - Bu sure boyunca <img> bos govdeli bir multipart yaniti bekliyor,
//     Chromium `error` olayini atesliyordu.
//   - Istemci tarafinda `error` olayi TEK SEFERLIK idi: bir kez
//     tetiklendiginde kutu kalici olarak `.kam-hata` durumunda
//     kaliyordu. Kaynak 2 sn sonra saglikli akmaya baslasa bile
//     <img> artik o baglantiya bakmiyordu.
//
// COZUM
// -----
// `mjpegBagla(img, urlUret, kutuSec)` her <img> icin artan gecikmeli
// yeniden deneme yonetir:
//   deneme 1 -> 1.0 sn sonra
//   deneme 2 -> 2.0 sn sonra
//   deneme 3 -> 3.5 sn sonra
//   deneme 4 -> 5.0 sn sonra
//   deneme 5 -> 7.0 sn sonra
// Hepsi tukendiginde `.kam-hata` uygulanir. Ilk kare geldiginde
// (`load` olayi) sayac sifirlanir, boylece uzun izlemelerde gecici
// ag kesintileri de kendiliginden toparlanir.
//
// Ayrica ilk kare gelene kadar kutuya `.kam-baglaniyor` sinifi
// eklenir; CSS bunu "BAGLANIYOR" olarak gosterir. Onceki surumde
// kullanici bos siyah kutuya bakiyor, sistemin calisip calismadigini
// anlayamiyordu.
// ================================================================
// v2.4.34 EKI: GERCEK GEREKCEYI GOSTER
// -----------------------------------
// Kullanici kamerasini saatlerce "YAYIN ALINAMIYOR" olarak gordu;
// gerekce ffmpeg'in kurulu olmamasiydi ve sunucu bunu BILIYORDU
// (video_proxy `_Yayin.hata` alani). Artik vekil 503 yanitinda
// `X-Goktungu-Hata` basligi + JSON govdesi dondurur; buradaki kod bunu
// okuyup kutuya net metin yazar (or. "ffmpeg kurulu degil").
//
// <img> `error` olayi HTTP durum kodunu VERMEZ; bu yuzden gerekce
// ayrica kucuk bir fetch ile alinir. Fetch yalnizca tum denemeler
// tukendiginde bir kez yapilir — boylece normal calismada ek yuk yok.
(function () {
  "use strict";

  // Artan gecikme merdiveni (ms). Uzunlugu = en fazla deneme sayisi.
  const GECIKMELER = [1000, 2000, 3500, 5000, 7000];

  /**
   * Bir MJPEG <img> ogesine dayanikli yukleme davranisi baglar.
   *
   * @param {HTMLImageElement} img  Kaynak atanacak <img> ogesi
   * @param {function():string} urlUret  Her denemede TAZE url ureten
   *        fonksiyon. Onbellek kirici (?t=...) icermeli, aksi halde
   *        tarayici basarisiz istegi onbellekten tekrar dondurur.
   * @param {string} kutuSec  Durum siniflarinin uygulanacagi ust
   *        kapsayicinin CSS secicisi (or. ".kam-video-kutu").
   */
  function mjpegBagla(img, urlUret, kutuSec) {
    let deneme = 0;
    let zaman = null;
    let kapandi = false;

    const kutu = () => (kutuSec ? img.closest(kutuSec) : img.parentElement);

    function durumBaglaniyor() {
      const k = kutu();
      if (!k) return;
      k.classList.add("kam-baglaniyor");
      k.classList.remove("kam-hata");
    }

    function durumTamam() {
      const k = kutu();
      if (!k) return;
      k.classList.remove("kam-baglaniyor");
      k.classList.remove("kam-hata");
      k.removeAttribute("data-kam-hata");
    }

    function durumHata() {
      const k = kutu();
      if (!k) return;
      k.classList.remove("kam-baglaniyor");
      k.classList.add("kam-hata");
      // v2.4.219 (kullanici istegi): kirik resim simgesi yerine BUYUK, dile
      // gore "BAGLANTI YOK" metni; sunucu gerekcesi gelirse onunla degisir.
      if (!k.getAttribute("data-kam-hata"))
        k.setAttribute("data-kam-hata", (typeof D === "function" && D().kamBaglantiYok) || "BAĞLANTI YOK");
      gerekceSor(k);
    }

    // ---- v2.4.34: sunucudan gercek gerekceyi al ve goster ----------
    function gerekceSor(k) {
      let url;
      try { url = urlUret(); } catch (e) { return; }
      if (!url) return;
      fetch(url, { method: "GET", cache: "no-store" })
        .then((r) => {
          // Basarili olursa gerekce yok; sadece gec kalmis bir kare
          if (r.ok) return null;
          const bas = r.headers.get("X-Goktungu-Hata");
          if (bas) return bas;
          return r.json().then((j) => (j && j.hata) || null,
                              () => null);
        })
        .then((gerekce) => {
          if (!gerekce || !k.isConnected) return;
          k.setAttribute("data-kam-hata", gerekce);
          // Toast: kullanici pencereye bakmiyorsa da gorsun.
          // API: window.uyariToastGoster({seviye, kategori, mesaj})
          if (typeof window.uyariToastGoster === "function") {
            window.uyariToastGoster({
              seviye: "hata",
              kategori: "kamera",
              mesaj: "Yayin alinamadi: " + gerekce,
            });
          }
        })
        .catch(() => {});
    }

    function temizle() {
      kapandi = true;
      if (zaman) { clearTimeout(zaman); zaman = null; }
    }

    function yenidenDene() {
      if (kapandi) return;
      // Oge DOM'dan koparildiysa denemeyi birak (bellek sizmasini onler)
      if (!img.isConnected) { temizle(); return; }
      if (deneme >= GECIKMELER.length) {
        durumHata();
        return;
      }
      const bekle = GECIKMELER[deneme];
      deneme += 1;
      durumBaglaniyor();
      zaman = setTimeout(() => {
        zaman = null;
        if (kapandi || !img.isConnected) return;
        img.src = urlUret();
      }, bekle);
    }

    img.addEventListener("error", yenidenDene);
    img.addEventListener("load", () => {
      // Ilk kare geldi: sayaci sifirla, boylece uzun izlemelerde
      // gecici kesintiler yeniden tam bir deneme butcesi alir.
      deneme = 0;
      durumTamam();
    });

    // Baslangic durumu
    durumBaglaniyor();
    img.src = urlUret();

    // Cagiran taraf pencereyi kapatirken denemeleri iptal edebilsin
    return temizle;
  }

  window.mjpegBagla = mjpegBagla;
})();
