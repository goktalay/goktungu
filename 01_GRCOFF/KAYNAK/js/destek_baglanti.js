/* ============================================================
   GÖKTUNGU — Destek bağlantısı çözücü            FAZ15-DESTEK
   ------------------------------------------------------------
   Destek Merkezi iki farklı dağıtımda çalışır:

     Bulut (goktungu.com)  -> https://support.goktungu.com/
     Merkez Uygulama       -> /yardim/   (kapalı devre, localhost, IP)

   Merkez Uygulama satın alan firmalar sistemi kendi ağlarında veya
   `localhost` üzerinde çalıştırıyor; orada `support.goktungu.com`
   çözümlenmez ve sabit yazılmış bir bağlantı ölü olurdu.  Bu yüzden
   adres çalışma anında ana makineye bakılarak seçilir.

   Kullanım: `<a>` öğesine `data-destek-bag` niteliği eklenir; bu betik
   `href` değerini yükleme anında yazar.  Betiksiz durumda HTML'deki
   `/yardim/` değeri geçerli kalır — yani bozulma değil, geri düşüş.
   ============================================================ */
(function () {
  "use strict";

  var KOK = "goktungu.com";
  var ALT = "support";

  /* Bulut dağıtımı mı?  Yalnız kök alan adı VEYA onun alt alan adları.
     `localhost`, IPv4/IPv6 ve firmanın kendi alan adı bulut sayılmaz. */
  function bulutMu() {
    var k = (location.hostname || "").toLowerCase();
    if (!k) return false;
    return k === KOK || k.endsWith("." + KOK);
  }

  /* Destek Merkezi adresi. */
  function destekAdresi(capa) {
    var c = capa || "";
    if (c && c.charAt(0) !== "#") c = "#" + c;
    if (bulutMu()) return "https://" + ALT + "." + KOK + "/" + c;
    return "/yardim/" + c;
  }

  /* Dışa açılır: app menü çubuğu gibi betikten açılan yerler kullanır. */
  window.destekAdresi = destekAdresi;

  function uygula() {
    var liste = document.querySelectorAll("[data-destek-bag]");
    for (var i = 0; i < liste.length; i++) {
      var e = liste[i];
      /* Çapa niteliği varsa korunur: `data-destek-bag="kopru-kurulum"`
         -> `.../#kopru-kurulum`.  Derin bağlantılar kırılmamalı. */
      var capa = e.getAttribute("data-destek-bag") || "";
      e.setAttribute("href", destekAdresi(capa));
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", uygula);
  } else {
    uygula();
  }
})();
