// ============================================================
// GOKTUNGU GCS — PILOTLAR WIDGET (v2.4.32)
//
// Ayni sirket icindeki pilotlarin listesi; her satirda cevrimici /
// cevrimdisi gostergesi ve okunmamis mesaj rozeti. Satira tiklayinca
// o pilotla sohbet penceresi acilir.
//
// TASARIM KARARLARI
// -----------------
// 1) YUKSEKLIK: diger widget'lar 226x224 sabittir; pilot listesi
//    dogal olarak daha uzundur, bu nedenle 226x300 kullanilir ve
//    liste kendi icinde kayar. Widget altyapisi sabit boyutlu
//    oldugu icin liste tasmasi `overflow-y:auto` ile cozulur.
//
// 2) DURUM KAYNAGI: cevrimici durumu SUNUCUDAN gelir (`pilot_durum`).
//    Istemcide tahmin edilmez. Ayni pilotun birden fazla sekmesi
//    olabilecegi icin sunucu kume uzerinden hesaplar.
//
// 3) YERINDE GUNCELLEME: `pilot_durum` olayinda tum liste yeniden
//    cizilmez, yalnizca ilgili satirin sinifi degisir. Yeniden cizim
//    kaydirma konumunu sifirlar ve kullanici listeyi incelerken
//    rahatsiz olur.
//
// 4) SIRALAMA: sunucu cevrimicileri one alir. Durum degisiminde
//    yeniden siralama YAPILMAZ (satir kullanicinin gozu onunde yer
//    degistirmemeli); siralama yalniz tam liste tazelemesinde uygulanir.
// ============================================================

(function(){
  "use strict";

  const ID = "pilotlar";

  let ogeler = null;
  // eposta -> { satir, nokta, rozet, cevrimici, okunmamis }
  const kayit = new Map();
  let benEposta = "";
  let tazeleZaman = null;
  // v2.4.33: baslikta duran tekil yenileme dugmesine erisim
  let wApi = null;

  function ingilizceMi(){
    try {
      if (typeof aktifDil !== "undefined") return String(aktifDil).toLowerCase().startsWith("en");
      const d = localStorage.getItem("gcs_dil");
      return !!(d && d.toLowerCase().startsWith("en"));
    } catch (e) { return false; }
  }

  function wsGonder(obj){
    try {
      if (typeof ws !== "undefined" && ws && ws.readyState === 1){
        ws.send(JSON.stringify(obj));
        return true;
      }
    } catch(e){}
    return false;
  }

  // ----------------------------------------------------------
  // GOVDE
  // ----------------------------------------------------------
  function govdeKur(govde, api){
    wApi = api;
    govde.classList.add("wg-pilot-govde");

    const ust = document.createElement("div");
    ust.className = "wg-pilot-ust";
    const sayac = document.createElement("span");
    sayac.className = "wg-pilot-sayac";
    ust.appendChild(sayac);
    // v2.4.33: yenileme dugmesi BASLIGA tasindi (tum widget'larda ayni).
    // Onceki surumde bu ust seritte kucuk gri bir dugmeydi
    // (`wg-pilot-yenile`) ve digerlerinden farkli gorunuyordu.
    //
    // Pilot listesi "bayatlik" kavramina sahip degil (WS ile canli
    // guncellenir), bu nedenle dugme DAIMA gorunur tutulur: operator
    // istedigi an listeyi elle tazeleyebilir.
    if (wApi && typeof wApi.yenilemeKur === "function"){
      const en = ingilizceMi();
      wApi.yenilemeKur(function(){
        wApi.yenileDonuyor(true);
        istekAt();
        // Yanit WS ile gelir; sabit bir sure sonra donusu durdur.
        setTimeout(function(){ wApi.yenileDonuyor(false); }, 900);
      }, en ? "Refresh pilot list" : "Pilot listesini yenile");
      wApi.yenileGoster(true);
    }
    govde.appendChild(ust);

    const liste = document.createElement("div");
    liste.className = "wg-pilot-liste";
    govde.appendChild(liste);

    ogeler = { govde, liste, sayac };

    bosYaz(ingilizceMi() ? "Loading..." : "Y\u00fckleniyor...");
  }

  function bosYaz(metin){
    if (!ogeler) return;
    ogeler.liste.textContent = "";
    const b = document.createElement("div");
    b.className = "wg-pilot-bos";
    b.textContent = metin;
    ogeler.liste.appendChild(b);
  }

  // ----------------------------------------------------------
  // LISTE CIZIMI
  // ----------------------------------------------------------
  function listeCiz(pilotlar, ben){
    if (!ogeler) return;
    benEposta = String(ben || benEposta || "").toLowerCase();
    kayit.clear();
    ogeler.liste.textContent = "";

    const digerleri = (pilotlar || []).filter(p => !p.kendisi);
    if (!digerleri.length){
      bosYaz(ingilizceMi() ? "No other pilots" : "Ba\u015Fka pilot yok");
      sayacYaz(0, 0);
      return;
    }

    let online = 0;
    for (const p of digerleri){
      if (p.cevrimici) online++;
      const eposta = String(p.eposta || "").toLowerCase();

      const satir = document.createElement("div");
      satir.className = "wg-pilot-satir" + (p.cevrimici ? " wg-online" : "");
      satir.title = (p.unvan ? p.unvan + " — " : "") + eposta;

      const nokta = document.createElement("span");
      nokta.className = "wg-pilot-nokta";
      satir.appendChild(nokta);

      const orta = document.createElement("div");
      orta.className = "wg-pilot-orta";
      const ad = document.createElement("div");
      ad.className = "wg-pilot-ad";
      ad.textContent = p.ad_soyad || eposta;
      orta.appendChild(ad);
      const alt = document.createElement("div");
      alt.className = "wg-pilot-alt";
      alt.textContent = p.unvan || p.rol || "";
      orta.appendChild(alt);
      satir.appendChild(orta);

      const rozet = document.createElement("span");
      rozet.className = "uyari-rozet wg-pilot-rozet";
      const n = p.okunmamis | 0;
      rozet.textContent = n > 99 ? "99+" : String(n);
      rozet.style.display = n > 0 ? "inline-flex" : "none";
      satir.appendChild(rozet);

      satir.addEventListener("click", () => {
        if (typeof window.mesajSohbetAc === "function")
          window.mesajSohbetAc(eposta, p.ad_soyad || eposta);
      });

      ogeler.liste.appendChild(satir);
      kayit.set(eposta, { satir, nokta, rozet,
                          cevrimici: !!p.cevrimici, okunmamis: n });
    }
    sayacYaz(online, digerleri.length);
  }

  function sayacYaz(online, toplam){
    if (!ogeler) return;
    const en = ingilizceMi();
    // v2.4.34: etiket sozlukten alinir (wgPilotCevrimici)
    const etiket = (D().wgPilotCevrimici)
      || (en ? "online" : "\u00e7evrimi\u00e7i");
    ogeler.sayac.textContent = online + " / " + toplam + " " + etiket;
  }

  function sayacTazele(){
    let online = 0;
    for (const k of kayit.values()) if (k.cevrimici) online++;
    sayacYaz(online, kayit.size);
  }

  // ----------------------------------------------------------
  // YERINDE GUNCELLEMELER
  // ----------------------------------------------------------
  function durumGuncelle(eposta, cevrimici){
    const e = String(eposta || "").toLowerCase();
    const k = kayit.get(e);
    if (!k) return;
    k.cevrimici = !!cevrimici;
    k.satir.classList.toggle("wg-online", k.cevrimici);
    sayacTazele();
  }

  function okunmamisArtir(eposta){
    const e = String(eposta || "").toLowerCase();
    const k = kayit.get(e);
    if (!k) return;
    k.okunmamis = (k.okunmamis | 0) + 1;
    k.rozet.textContent = k.okunmamis > 99 ? "99+" : String(k.okunmamis);
    k.rozet.style.display = "inline-flex";
  }

  function okunmamisSifirla(eposta){
    const e = String(eposta || "").toLowerCase();
    if (!e){
      for (const k of kayit.values()){
        k.okunmamis = 0;
        k.rozet.style.display = "none";
      }
      return;
    }
    const k = kayit.get(e);
    if (!k) return;
    k.okunmamis = 0;
    k.rozet.style.display = "none";
  }

  function cevrimiciMi(eposta){
    const k = kayit.get(String(eposta || "").toLowerCase());
    return !!(k && k.cevrimici);
  }

  // ----------------------------------------------------------
  // ISTEK
  // ----------------------------------------------------------
  function istekAt(){
    if (!wsGonder({ tip: "pilot_liste" })){
      bosYaz(ingilizceMi() ? "No connection" : "Ba\u011Flant\u0131 yok");
    }
  }

  function ac(){
    istekAt();
    // Periyodik hafif tazeleme: durum olaylari kacirilirsa (ornek:
    // WS yeniden baglandi) liste bayat kalmasin.
    if (tazeleZaman) clearInterval(tazeleZaman);
    tazeleZaman = setInterval(istekAt, 60000);
  }
  function kapa(){
    if (tazeleZaman){ clearInterval(tazeleZaman); tazeleZaman = null; }
  }

  function dilTazele(){
    if (!ogeler) return;
    sayacTazele();
  }

  function kaydol(){
    if (!window.Widget) return;
    window.Widget.kaydet({
      id: ID,
      baslik: "PILOTLAR",
      baslikAnahtar: "wgPilotlar",
      genislik: 226,
      yukseklik: 300,
      govdeKur: govdeKur,
      ac: ac,
      kapa: kapa,
    });
  }

  // mesajlasma.js bu adlarla cagirir
  window.pilotListeCiz = listeCiz;
  window.pilotDurumGuncelle = durumGuncelle;
  window.pilotYeniMesaj = okunmamisArtir;
  window.pilotOkunmamisSifirla = okunmamisSifirla;
  window.pilotCevrimiciMi = cevrimiciMi;

  window.WidgetPilotlar = {
    kaydol: kaydol,
    dilTazele: dilTazele,
    tazele: istekAt,
  };
})();
