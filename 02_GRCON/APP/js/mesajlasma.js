// ============================================================
// GOKTUNGU GCS — MESAJLASMA (v2.4.32)
//
// AMAC
// ----
// Sirket ici pilotlar arasi canli mesajlasma arayuzu:
//   1) Header'da mesaj ikonu + okunmamis rozeti (kirmizi)
//   2) Ikona tik -> okunmamis mesaj listesi (kucuk acilir panel)
//   3) Bir kisiyle sohbet penceresi (tasinabilir, boyutlandirilabilir)
//
// TASARIM KARARLARI
// -----------------
// 1) SAYAC KAYNAGI: okunmamis sayisi ISTEMCIDE HESAPLANMAZ. Sunucu
//    `mesaj_okunmamis_sayi` olayiyla bildirir. Istemcide sayma
//    denemesi, ayni pilotun ikinci sekmesi mesaji okudugunda bu
//    sekmenin sayacini bayat birakirdi.
//
// 2) OKUNDU ANI: header listesi acildiginda sunucuya `mesaj_okundu`
//    (tumu) gonderilir — kullanicinin istegi boyleydi: "ikona
//    tiklayinca ... artik mesaj okunmus olsun". Sohbet penceresi
//    acildiginda ise YALNIZ o kisinin mesajlari okundu isaretlenir.
//
// 3) SOHBET PENCERESI SAYISI: her kisi icin ayri pencere acilir ve
//    `_pencereler` haritasinda tutulur. Ayni kisi icin ikinci pencere
//    acilmaz, var olan one getirilir (v2.4.27 "cift pencere" dersi).
//
// 4) GECMIS ISTEGI: pencere acilinca `mesaj_gecmis` istenir. Gelen
//    yanit `karsi` alanini tasir; bu alan pencereyi bulmak icin
//    kullanilir. Aksi halde hizli acilip kapanan iki pencerede yanit
//    yanlis pencereye yazilabilirdi.
//
// 5) XSS: mesaj metni DAIMA `textContent` ile yazilir, asla innerHTML
//    ile birlestirilmez. Mesaj metni kullanici girdisidir.
// ============================================================
"use strict";

(function(){

  // karsi_eposta -> { pop, liste, girdi, ad }
  const _pencereler = new Map();
  let _mesajPanel = null;        // header acilir paneli
  let _okunmamisSayi = 0;
  let _benEposta = "";

  const _btn = document.getElementById("btnMesajlar");
  const _rozet = document.getElementById("mesajRozet");

  function _t(){
    try { return (typeof D === "function") ? D() : {}; } catch(e){ return {}; }
  }
  function _en(){
    try {
      if (typeof aktifDil !== "undefined") return String(aktifDil).toLowerCase().startsWith("en");
    } catch(e){}
    return false;
  }
  function _wsGonder(obj){
    try {
      if (typeof ws !== "undefined" && ws && ws.readyState === 1){
        ws.send(JSON.stringify(obj));
        return true;
      }
    } catch(e){}
    return false;
  }

  // ----------------------------------------------------------
  // SAAT BICIMI
  // ----------------------------------------------------------
  function _saat(ts){
    try {
      const d = new Date((ts || 0) * 1000);
      return d.toLocaleTimeString(_en() ? "en-GB" : "tr-TR",
        { hour: "2-digit", minute: "2-digit" });
    } catch(e){ return ""; }
  }
  function _tarihSaat(ts){
    try {
      const d = new Date((ts || 0) * 1000);
      const bugun = new Date();
      const ayniGun = d.toDateString() === bugun.toDateString();
      if (ayniGun) return _saat(ts);
      return d.toLocaleDateString(_en() ? "en-GB" : "tr-TR",
        { day: "2-digit", month: "2-digit" }) + " " + _saat(ts);
    } catch(e){ return ""; }
  }

  // ----------------------------------------------------------
  // ROZET
  // ----------------------------------------------------------
  function rozetGuncelle(sayi){
    _okunmamisSayi = Math.max(0, sayi | 0);
    if (!_rozet) return;
    _rozet.textContent = _okunmamisSayi > 99 ? "99+" : String(_okunmamisSayi);
    _rozet.style.display = _okunmamisSayi > 0 ? "inline-flex" : "none";
    // Kullanici istegi: okunmamis varsa ikon KIRMIZI olsun
    if (_btn) _btn.classList.toggle("mesaj-var", _okunmamisSayi > 0);
  }

  window.mesajMerkeziOturum = function(okunmamis){
    if (_btn) _btn.style.display = "";
    rozetGuncelle(okunmamis || 0);
    // Pilot listesi widget'i acikken oturum degisirse liste tazelenir
    _wsGonder({ tip: "pilot_liste" });
  };
  window.mesajMerkeziCikis = function(){
    if (_btn) _btn.style.display = "none";
    rozetGuncelle(0);
    panelKapat();
    for (const eposta of Array.from(_pencereler.keys())) sohbetKapat(eposta);
    _benEposta = "";
  };

  // ----------------------------------------------------------
  // HEADER ACILIR PANELI
  // ----------------------------------------------------------
  function panelKapat(){
    if (_mesajPanel){ _mesajPanel.remove(); _mesajPanel = null; }
  }

  function panelAc(){
    if (_mesajPanel){ panelKapat(); return; }
    const t = _t();
    const pop = document.createElement("div");
    pop.className = "msj-panel";
    _mesajPanel = pop;

    const bas = document.createElement("div");
    bas.className = "msj-panel-bas";
    const bsp = document.createElement("span");
    bsp.innerHTML = "<i class='fa-solid fa-comment-dots'></i> ";
    const bad = document.createElement("span");
    bad.textContent = t.msjOkunmamis || (_en() ? "UNREAD MESSAGES" : "OKUNMAMI\u015E MESAJLAR");
    bsp.appendChild(bad);
    bas.appendChild(bsp);
    const kapat = document.createElement("button");
    kapat.className = "msj-panel-kapat";
    kapat.innerHTML = "<i class='fa-solid fa-xmark'></i>";
    kapat.addEventListener("click", panelKapat);
    bas.appendChild(kapat);
    pop.appendChild(bas);

    const liste = document.createElement("div");
    liste.className = "msj-panel-liste";
    liste.textContent = t.phYukleniyor || (_en() ? "Loading..." : "Y\u00fckleniyor...");
    pop.appendChild(liste);
    pop._liste = liste;

    document.body.appendChild(pop);

    // Ikonun altina hizala (uyari merkeziyle ayni yerlesim kurali)
    const r = (_btn || document.getElementById("profilKutu")).getBoundingClientRect();
    pop.style.top = (r.bottom + 6) + "px";
    pop.style.left = Math.max(10, Math.min(r.right - pop.offsetWidth,
      window.innerWidth - pop.offsetWidth - 10)) + "px";

    // Listeyi iste; okundu isareti YANIT GELDIKTEN SONRA yapilir,
    // aksi halde sunucu listeyi zaten bosaltmis olur ve panel bos acilir.
    _wsGonder({ tip: "mesaj_okunmamis" });
  }

  function panelListeCiz(liste, sayi){
    if (!_mesajPanel || !_mesajPanel._liste) return;
    const kap = _mesajPanel._liste;
    kap.textContent = "";
    const t = _t();
    if (!liste || !liste.length){
      const bos = document.createElement("div");
      bos.className = "msj-panel-bos";
      bos.textContent = t.msjYokOkunmamis || (_en() ? "No unread messages" : "Okunmam\u0131\u015F mesaj yok");
      kap.appendChild(bos);
    } else {
      for (const oge of liste){
        const satir = document.createElement("div");
        satir.className = "msj-panel-satir";

        const sol = document.createElement("div");
        sol.className = "msj-panel-sol";
        const ad = document.createElement("div");
        ad.className = "msj-panel-ad";
        ad.textContent = oge.ad_soyad || oge.gonderen || "";
        sol.appendChild(ad);
        const metin = document.createElement("div");
        metin.className = "msj-panel-metin";
        metin.textContent = oge.metin || "";
        sol.appendChild(metin);
        satir.appendChild(sol);

        const sag = document.createElement("div");
        sag.className = "msj-panel-sag";
        const zaman = document.createElement("div");
        zaman.className = "msj-panel-zaman";
        zaman.textContent = _tarihSaat(oge.ts);
        sag.appendChild(zaman);
        if ((oge.sayi | 0) > 1){
          const rz = document.createElement("span");
          rz.className = "uyari-rozet";
          rz.textContent = String(oge.sayi);
          sag.appendChild(rz);
        }
        satir.appendChild(sag);

        // Mesaja tiklarsa gonderenle sohbet acilir (kullanici istegi)
        satir.addEventListener("click", () => {
          panelKapat();
          sohbetAc(oge.gonderen, oge.ad_soyad || oge.gonderen);
        });
        kap.appendChild(satir);
      }
      // Kullanici istegi: ikona tiklayinca mesajlar okunmus sayilir.
      // Liste CIZILDIKTEN sonra isaretlenir, boylece panel dolu acilir.
      _wsGonder({ tip: "mesaj_okundu", tumu: true });
    }
    rozetGuncelle(0);
  }

  // Dis tiklamada paneli kapat
  document.addEventListener("click", (e) => {
    if (_mesajPanel && !_mesajPanel.contains(e.target) &&
        !(_btn && _btn.contains(e.target))){
      panelKapat();
    }
  });
  if (_btn) _btn.addEventListener("click", (e) => {
    e.stopPropagation();
    panelAc();
  });

  // ----------------------------------------------------------
  // SOHBET PENCERESI
  // ----------------------------------------------------------
  function sohbetKapat(eposta){
    const p = _pencereler.get(eposta);
    if (!p) return;
    if (p.pop) p.pop.remove();
    _pencereler.delete(eposta);
  }

  function sohbetAc(eposta, ad){
    eposta = String(eposta || "").trim().toLowerCase();
    if (!eposta) return;
    // Var olan pencereyi one getir (cift pencere acilmaz)
    const mevcut = _pencereler.get(eposta);
    if (mevcut){
      mevcut.pop.classList.remove("popup-gizli");
      if (typeof window.enUsteGetir === "function") window.enUsteGetir(mevcut.pop);
      if (mevcut.girdi) mevcut.girdi.focus();
      _wsGonder({ tip: "mesaj_okundu", karsi: eposta });
      return;
    }
    const t = _t();
    const pop = document.createElement("div");
    // `.bolum-popup` sinifi: pencere yonetimi ve tema ile uyumlu olur
    pop.className = "bolum-popup msj-sohbet";
    pop.id = "msjSohbet_" + eposta.replace(/[^a-z0-9]/g, "_");

    const bas = document.createElement("div");
    bas.className = "popup-baslik";
    const bsol = document.createElement("span");
    bsol.innerHTML = "<i class='fa-solid fa-comments'></i> ";
    const bad = document.createElement("span");
    bad.className = "msj-sohbet-ad";
    bad.textContent = ad || eposta;
    bsol.appendChild(bad);
    const dur = document.createElement("span");
    dur.className = "msj-sohbet-durum";
    bsol.appendChild(dur);
    bas.appendChild(bsol);
    const kapatBtn = document.createElement("button");
    kapatBtn.className = "popup-kapat";
    kapatBtn.innerHTML = "<i class='fa-solid fa-xmark'></i>";
    kapatBtn.addEventListener("click", () => sohbetKapat(eposta));
    bas.appendChild(kapatBtn);
    pop.appendChild(bas);

    const govde = document.createElement("div");
    govde.className = "msj-sohbet-govde";
    pop.appendChild(govde);

    const liste = document.createElement("div");
    liste.className = "msj-sohbet-liste";
    liste.textContent = t.phYukleniyor || (_en() ? "Loading..." : "Y\u00fckleniyor...");
    govde.appendChild(liste);

    const altKap = document.createElement("div");
    altKap.className = "msj-sohbet-alt";
    const girdi = document.createElement("textarea");
    girdi.className = "msj-sohbet-girdi";
    girdi.rows = 2;
    girdi.placeholder = _en() ? "Type a message..." : "Mesaj yaz\u0131n...";
    girdi.maxLength = 4000;
    altKap.appendChild(girdi);
    const gonderBtn = document.createElement("button");
    gonderBtn.className = "msj-sohbet-gonder";
    gonderBtn.innerHTML = "<i class='fa-solid fa-paper-plane'></i>";
    gonderBtn.title = _en() ? "Send" : "G\u00f6nder";
    altKap.appendChild(gonderBtn);
    govde.appendChild(altKap);

    document.body.appendChild(pop);

    // Yerlesim: ekranin sag altina, acik pencere sayisina gore kaydir
    const n = _pencereler.size;
    const g = 340, y = 420;
    pop.style.width = g + "px";
    pop.style.height = y + "px";
    pop.style.left = Math.max(10, window.innerWidth - g - 24 - n * 28) + "px";
    pop.style.top = Math.max(60, window.innerHeight - y - 60) + "px";

    if (typeof window.popupTasinabilirYap === "function")
      window.popupTasinabilirYap(pop, bas, "pp_msj_" + eposta);
    if (typeof window.popupBoyutlandirilabilirYap === "function")
      window.popupBoyutlandirilabilirYap(pop, "pp_msj_" + eposta,
        { minW: 280, minH: 300 });

    const kayit = { pop, liste, girdi, ad: ad || eposta, durum: dur };
    _pencereler.set(eposta, kayit);

    function gonder(){
      const metin = girdi.value.trim();
      if (!metin) return;
      if (!_wsGonder({ tip: "mesaj_gonder", alici: eposta, metin: metin })){
        return;
      }
      girdi.value = "";
      girdi.focus();
    }
    gonderBtn.addEventListener("click", gonder);
    girdi.addEventListener("keydown", (e) => {
      // Enter gonderir, Shift+Enter satir atlar
      if (e.key === "Enter" && !e.shiftKey){
        e.preventDefault();
        gonder();
      }
    });

    // Gecmisi iste ve o kisiden gelenleri okundu isaretle
    _wsGonder({ tip: "mesaj_gecmis", karsi: eposta, limit: 200 });
    _wsGonder({ tip: "mesaj_okundu", karsi: eposta });
    girdi.focus();
    durumTazele(eposta);
  }

  function _balonEkle(kap, mesaj){
    const benim = String(mesaj.gonderen || "").toLowerCase() === _benEposta;
    const sar = document.createElement("div");
    sar.className = "msj-balon-sar " + (benim ? "msj-ben" : "msj-karsi");
    const balon = document.createElement("div");
    balon.className = "msj-balon";
    const mt = document.createElement("div");
    mt.className = "msj-balon-metin";
    mt.textContent = mesaj.metin || "";      // XSS: daima textContent
    balon.appendChild(mt);
    const zm = document.createElement("div");
    zm.className = "msj-balon-zaman";
    zm.textContent = _saat(mesaj.ts);
    balon.appendChild(zm);
    sar.appendChild(balon);
    kap.appendChild(sar);
  }

  function gecmisCiz(karsi, mesajlar){
    const p = _pencereler.get(String(karsi || "").toLowerCase());
    if (!p) return;
    p.liste.textContent = "";
    if (!mesajlar || !mesajlar.length){
      const bos = document.createElement("div");
      bos.className = "msj-panel-bos";
      bos.textContent = _en() ? "No messages yet" : "Hen\u00fcz mesaj yok";
      p.liste.appendChild(bos);
    } else {
      for (const m of mesajlar) _balonEkle(p.liste, m);
    }
    p.liste.scrollTop = p.liste.scrollHeight;
  }

  // ----------------------------------------------------------
  // WS OLAYLARI (ws.js yonlendirir)
  // ----------------------------------------------------------
  window.mesajOlayIsle = function(m){
    if (!m || !m.tip) return;
    if (m.tip === "mesaj_okunmamis"){
      panelListeCiz(m.liste || [], m.sayi || 0);
    } else if (m.tip === "mesaj_okunmamis_sayi"){
      rozetGuncelle(m.sayi || 0);
      if (typeof window.pilotOkunmamisSifirla === "function" && m.okundu_karsi)
        window.pilotOkunmamisSifirla(m.okundu_karsi);
    } else if (m.tip === "mesaj_gecmis"){
      gecmisCiz(m.karsi, m.mesajlar);
    } else if (m.tip === "mesaj_yeni"){
      const mes = m.mesaj || {};
      const g = String(mes.gonderen || "").toLowerCase();
      const a = String(mes.alici || "").toLowerCase();
      // Sohbet penceresi hangi karsi tarafa ait? Gonderen ben isem
      // alici, degilse gonderen.
      const karsi = (g === _benEposta) ? a : g;
      const p = _pencereler.get(karsi);
      if (p){
        // Ilk mesajda "henuz mesaj yok" yazisi temizlenir
        const bos = p.liste.querySelector(".msj-panel-bos");
        if (bos) bos.remove();
        _balonEkle(p.liste, mes);
        p.liste.scrollTop = p.liste.scrollHeight;
        // Pencere acikken gelen mesaj aninda okundu sayilir
        if (karsi === g) _wsGonder({ tip: "mesaj_okundu", karsi: g });
      }
      if (typeof window.pilotYeniMesaj === "function" && karsi === g)
        window.pilotYeniMesaj(g);
    } else if (m.tip === "mesaj_sonuc"){
      if (!m.basarili && m.hata && typeof window.bildir === "function")
        window.bildir(m.hata, "hata");
    } else if (m.tip === "pilot_liste"){
      if (m.ben) _benEposta = String(m.ben).toLowerCase();
      if (typeof window.pilotListeCiz === "function")
        window.pilotListeCiz(m.pilotlar || [], _benEposta);
    } else if (m.tip === "pilot_durum"){
      if (typeof window.pilotDurumGuncelle === "function")
        window.pilotDurumGuncelle(m.eposta, !!m.cevrimici);
      durumTazele(String(m.eposta || "").toLowerCase(), !!m.cevrimici);
    }
  };

  // Sohbet basligindaki cevrimici noktasi
  function durumTazele(eposta, cevrimici){
    const p = _pencereler.get(eposta);
    if (!p || !p.durum) return;
    if (typeof cevrimici === "undefined"){
      // Pilot listesi widget'inda biliniyorsa oradan al
      if (typeof window.pilotCevrimiciMi === "function")
        cevrimici = !!window.pilotCevrimiciMi(eposta);
      else return;
    }
    p.durum.className = "msj-sohbet-durum " + (cevrimici ? "msj-online" : "msj-offline");
    p.durum.title = cevrimici ? (_en() ? "Online" : "\u00c7evrimi\u00e7i")
                              : (_en() ? "Offline" : "\u00c7evrimd\u0131\u015f\u0131");
  }

  // Pilot listesi widget'i bu fonksiyonla sohbet acar
  window.mesajSohbetAc = sohbetAc;
  window.mesajBenEposta = function(){ return _benEposta; };
  window.mesajBenAta = function(e){ _benEposta = String(e || "").toLowerCase(); };
})();
