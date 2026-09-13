/* =====================================================================
   IS56-DOK-TEMIZLIK-V1 — Dok artiklarinin depodan temizlenmesi
   ---------------------------------------------------------------------
   Is 56'da pencerelerin ic ice gecme (dok) davranisi kaldirildi:
   `js/pencere_dok.js` ve `css/pencere_dok.css` baglantidan cikarildi.

   NEDEN BU DOSYA VAR
   ------------------
   Kaldirilan dok modulu, kendi icinde bir depo temizligi tasiyordu
   (pencere_dok.js:334-347). Eski surumler pencere konumlarini
   `gcs_pencere_konum` altinda `dok_dokKap_*` anahtarlariyla
   kaydediyordu; bu artiklar temizlenmezse depoda kalicilasiyordu.

   Modul kaldirilinca temizlik de kalkacakti. Bu dosya o islevi
   kurtarir ve kapsamini genisletir: yalniz `dok_dokKap_*` degil,
   TUM `dok_` onekli kayitlar silinir.

   Artiklar dogrudan zarar vermez (karsilik gelen pencere artik hic
   uretilmez) ancak depoyu kirletir ve ileride ayni anahtar adi
   yeniden kullanilirsa yanlis boyut/konum uygulanmasina yol acar.

   TEK SEFERLIK DEGILDIR: her acilista kosar. Maliyeti ihmal
   edilebilir (tek JSON okuma) ve birden cok sekmede/eski onbellekte
   kalmis surumlerin yeniden artik uretmesine karsi korur.
   ===================================================================== */
(function () {
  "use strict";

  var DEPO_ANAHTAR = "gcs_pencere_konum";
  var ONEK = "dok_";

  try {
    var ham = localStorage.getItem(DEPO_ANAHTAR);
    if (!ham) return;

    var d = JSON.parse(ham);
    if (!d || typeof d !== "object") return;

    var silinen = 0;
    Object.keys(d).forEach(function (k) {
      if (k.indexOf(ONEK) === 0) {
        delete d[k];
        silinen++;
      }
    });

    if (silinen > 0) {
      localStorage.setItem(DEPO_ANAHTAR, JSON.stringify(d));
    }

    // Sinav ve teshis icin: kac artik temizlendigi disaridan okunabilir.
    window.DOK_TEMIZLIK = { silinen: silinen, isaret: "IS56-DOK-TEMIZLIK-V1" };
  } catch (e) {
    // Depo erisilemezse (gizli kip, kota dolu) sessiz gec — temizlik
    // bir iyilestirmedir, uygulamanin acilisini engellememeli.
    try {
      window.DOK_TEMIZLIK = { silinen: 0, isaret: "IS56-DOK-TEMIZLIK-V1" };
    } catch (e2) {}
  }
})();
