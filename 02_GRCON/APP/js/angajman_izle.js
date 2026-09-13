// =================================================================
// GOKTUNGU - ANGAJMAN IZLEME POPUP'I (CANLI GUNCELLENEN)
// =================================================================
// Aktif angajmanlar icin detayli bilgi gosteren tasinabilir popup.
// Sunucudan her telemetri karesinde gelen "angajmanlar" verisiyle beslenir.
// =================================================================

(function () {
  "use strict";

  // --- Popup DOM referanslari ---
  let popupEl = null;   // ana popup div
  let icerikEl = null;  // icerik alani (baslik haric)
  const POPUP_ID = "angIzlePopup";

  // --- Canli veri (ws.js'ten beslenir) ---
  let canliVeri = {}; // saldiran_sysid -> {...}

  // --- Yardimci: sure formatla ---
  function sureFmt(sn) {
    if (sn == null || sn < 0) return "-";
    if (sn < 60) return Math.round(sn) + "s";
    const dk = Math.floor(sn / 60);
    const kalan = Math.round(sn % 60);
    return dk + "dk " + kalan + "s";
  }

  // --- Yardimci: mesafe formatla ---
  function mesafeFmt(m) {
    if (m == null) return "-";
    if (m >= 1000) return (m / 1000).toFixed(2) + " km";
    return m.toFixed(1) + " m";
  }

  // --- Yardimci: yon formatla ---
  function yonFmt(derece) {
    if (derece == null) return "-";
    const yonler = ["K", "KD", "D", "GD", "G", "GB", "B", "KB"];
    const idx = Math.round(derece / 45) % 8;
    return Math.round(derece) + "° " + yonler[idx];
  }

  // --- Popup olustur ---
  function popupOlustur() {
    if (popupEl) return;
    const t = (typeof D === "function") ? D() : {};

    popupEl = document.createElement("div");
    popupEl.id = POPUP_ID;
    popupEl.className = "angi-popup";

    // Baslik
    const baslik = document.createElement("div");
    baslik.className = "angi-baslik popup-baslik";
    baslik.innerHTML =
      "<i class='fa-solid fa-satellite-dish'></i> " +
      (t.angiBaslik || "ANGAJMAN İZLEME") +
      "<button class='angi-kapat'><i class='fa-solid fa-xmark'></i></button>";
    popupEl.appendChild(baslik);

    // Kapat dugmesi
    baslik.querySelector(".angi-kapat").addEventListener("click", popupKapat);

    // Icerik alani
    icerikEl = document.createElement("div");
    icerikEl.className = "angi-icerik";
    popupEl.appendChild(icerikEl);

    document.body.appendChild(popupEl);

    // Tasinabilir yap (popup_tasima.js modulu varsa)
    if (typeof window.popupBoyutlandirilabilirYap === "function") {
      window.popupBoyutlandirilabilirYap(popupEl, "angIzlePopup");
    }
    if (typeof popupTasinabilirYap === "function") {
      popupTasinabilirYap(popupEl, baslik, "angIzlePopup");
    }
  }

  // --- Popup kapat ---
  function popupKapat() {
    if (popupEl) {
      popupEl.remove();
      popupEl = null;
      icerikEl = null;
    }
  }

  // --- Popup ac (disaridan cagrilir) ---
  function popupAcKapat() {
    if (popupEl) {
      popupKapat();
    } else {
      popupOlustur();
      icerikCiz();
    }
  }

  // --- Icerik ciz / guncelle ---
  function icerikCiz() {
    if (!icerikEl) return;
    const t = (typeof D === "function") ? D() : {};
    const anahtarlar = Object.keys(canliVeri);

    if (anahtarlar.length === 0) {
      icerikEl.innerHTML =
        "<div class='angi-bos'><i class='fa-solid fa-circle-info'></i> " +
        (t.angiAktifYok || "Aktif angajman yok") + "</div>";
      return;
    }

    let html = "";
    for (const sysid of anahtarlar) {
      const v = canliVeri[sysid];
      if (!v) continue;

      // Dron bilgisi
      const dronVeri = (typeof sonVeri !== "undefined") ? sonVeri[sysid] : null;
      const dronAd = dronVeri
        ? (dronVeri.kullanici_isim || dronVeri.isim || dronVeri.tip || "D" + sysid)
        : "D" + sysid;

      // Hedef bilgisi
      let hedefAd = "";
      if (v.hedef_tip === "radar") {
        hedefAd = "R" + v.hedef_id;
      } else {
        const hd = (typeof sonVeri !== "undefined") ? sonVeri[v.hedef_id] : null;
        hedefAd = hd ? (hd.kullanici_isim || hd.isim || hd.tip || "D" + v.hedef_id) : "D" + v.hedef_id;
      }

      const hedefIkon = v.hedef_tip === "radar" ? "fa-crosshairs" : "fa-plane-up";

      // Durum: hedef_bekleniyor ise ozel uyari goster
      const durum = v.durum || "aktif";

      // Ilerleme cubugu (mesafe / baslangic mesafesi tahmini)
      const mesafe = v.mesafe || 0;
      const etaPct = (durum === "aktif" && v.eta_sn != null && v.eta_sn > 0)
        ? Math.max(0, Math.min(100, 100 - (mesafe / Math.max(mesafe + (v.hiz || 1) * v.eta_sn, 1)) * 100))
        : 0;

      html += "<div class='angi-kart'>";
      // Ust satir: dron -> hedef
      html += "<div class='angi-kart-baslik'>";
      html += "<span class='angi-dron'><i class='fa-solid fa-jet-fighter'></i> " + dronAd + "</span>";
      html += "<span class='angi-ok'>→</span>";
      html += "<span class='angi-hedef'><i class='fa-solid " + hedefIkon + "'></i> " + hedefAd + "</span>";
      html += "</div>";

      // Durum uyarisi
      if (durum === "hedef_bekleniyor") {
        html += "<div class='angi-uyari'><i class='fa-solid fa-triangle-exclamation'></i> " +
          (t.angiHedefBekleniyor || "Hedef konumu bekleniyor...") + "</div>";
      }

      // Ilerleme cubugu
      html += "<div class='angi-progress'><div class='angi-progress-bar' style='width:" + etaPct.toFixed(0) + "%'></div></div>";

      // Detay tablosu
      html += "<div class='angi-detay'>";
      html += "<div class='angi-satir'><span class='angi-etiket'>" + (t.angiMesafe || "Mesafe") + "</span><span class='angi-deger angi-vurgu'>" + mesafeFmt(v.mesafe) + "</span></div>";
      html += "<div class='angi-satir'><span class='angi-etiket'>" + (t.angiYatayMesafe || "Yatay") + "</span><span class='angi-deger'>" + mesafeFmt(v.yatay_mesafe) + "</span></div>";
      html += "<div class='angi-satir'><span class='angi-etiket'>" + (t.angiDikeyFark || "Dikey Fark") + "</span><span class='angi-deger'>" + (v.dikey_fark != null ? (v.dikey_fark > 0 ? "+" : "") + v.dikey_fark.toFixed(1) + " m" : "-") + "</span></div>";
      html += "<div class='angi-satir'><span class='angi-etiket'>" + (t.angiYon || "Yön") + "</span><span class='angi-deger'>" + yonFmt(v.yon) + "</span></div>";
      html += "<div class='angi-satir'><span class='angi-etiket'>" + (t.angiHiz || "Hız") + "</span><span class='angi-deger'>" + (v.hiz != null ? v.hiz.toFixed(1) + " m/s (" + (v.hiz * 3.6).toFixed(1) + " km/h)" : "-") + "</span></div>";
      html += "<div class='angi-satir'><span class='angi-etiket'>" + (t.angiHucumHizi || "Hücum Hızı") + "</span><span class='angi-deger'>" + (v.hucum_hizi != null ? v.hucum_hizi + " m/s (" + (v.hucum_hizi * 3.6).toFixed(1) + " km/h)" : "-") + "</span></div>";
      html += "<div class='angi-satir'><span class='angi-etiket'>" + (t.angiETA || "Tahmini Varış") + "</span><span class='angi-deger angi-vurgu'>" + sureFmt(v.eta_sn) + "</span></div>";
      html += "<div class='angi-satir'><span class='angi-etiket'>" + (t.angiSaldiranIrt || "Saldıran İrt.") + "</span><span class='angi-deger'>" + (v.saldiran_alt != null ? v.saldiran_alt + " m" : "-") + "</span></div>";
      html += "<div class='angi-satir'><span class='angi-etiket'>" + (t.angiHedefIrt || "Hedef İrt.") + "</span><span class='angi-deger'>" + (v.hedef_alt != null ? v.hedef_alt + " m" : "-") + "</span></div>";
      html += "<div class='angi-satir'><span class='angi-etiket'>" + (t.angiYakalama || "Yakalama Mes.") + "</span><span class='angi-deger'>" + (v.yakalama_mesafe != null ? v.yakalama_mesafe + " m" : "-") + "</span></div>";
      html += "</div>";

      // ----------------------------------------------------------------
      // v2.4.43: ONGORU (KESISME) BLOGU
      // Operatorun "neden hedefin yanina dogru ucuyor?" sorusunu
      // cevaplar: cozum kaynagi, kesisme suresi, sapma acisi.
      // Cozum yoksa saf takipte oldugumuz ACIKCA yazilir - sessizce
      // eski davranisa dusmek operatoru yanlis bilgilendirirdi.
      // ----------------------------------------------------------------
      if (durum === "aktif" || durum === "temas") {
        const kaynak = v.ongoru_kaynak || "yok";
        const ongoruAcik = !!v.ongoru;
        const kaynakAd = ongoruAcik
          ? (kaynak === "gorev"
              ? (t.angiKaynakGorev || "Görev rodaşı")
              : (t.angiKaynakHiz || "Hız vektörü"))
          : (t.angiKaynakYok || "Saf takip");
        html += "<div class='angi-ongoru " +
          (ongoruAcik ? "angi-ongoru-acik" : "angi-ongoru-kapali") + "'>";
        html += "<div class='angi-ongoru-baslik'><i class='fa-solid " +
          (ongoruAcik ? "fa-bullseye" : "fa-arrow-right-long") + "'></i> " +
          (t.angiOngoruBaslik || "KESİŞME ÖNGÖRÜSÜ") +
          "<span class='angi-ongoru-kaynak'>" + kaynakAd + "</span></div>";
        html += "<div class='angi-detay'>";
        html += "<div class='angi-satir'><span class='angi-etiket'>" +
          (t.angiHedefHiz || "Hedef Hızı") + "</span><span class='angi-deger'>" +
          (v.hedef_hiz != null
            ? v.hedef_hiz.toFixed(1) + " m/s (" + (v.hedef_hiz * 3.6).toFixed(0) + " km/h)"
            : "-") + "</span></div>";
        html += "<div class='angi-satir'><span class='angi-etiket'>" +
          (t.angiKesismeSn || "Kesişmeye") + "</span><span class='angi-deger angi-vurgu'>" +
          sureFmt(v.kesisme_sn) + "</span></div>";
        html += "<div class='angi-satir'><span class='angi-etiket'>" +
          (t.angiSapma || "Kestirme Açısı") + "</span><span class='angi-deger'>" +
          (v.sapma != null ? v.sapma.toFixed(1) + "°" : "-") + "</span></div>";
        if (v.hedef_mod) {
          html += "<div class='angi-satir'><span class='angi-etiket'>" +
            (t.angiHedefMod || "Hedef Modu") + "</span><span class='angi-deger'>" +
            v.hedef_mod +
            (v.hedef_gorev_seq != null ? " · WP" + v.hedef_gorev_seq : "") +
            "</span></div>";
        }
        html += "</div>";
        if (!ongoruAcik) {
          html += "<div class='angi-ongoru-not'>" +
            (v.gorev_dikkate === false
              ? (t.angiOngoruNotKapali ||
                 "Görev rotası yok sayılıyor; hedefin anlık konumu izleniyor.")
              : (t.angiOngoruNotYok ||
                 "Kesişme çözülemedi; hedefin anlık konumu izleniyor.")) +
            "</div>";
        }
        html += "</div>";
      }

      // Iptal dugmesi
      html += "<div class='angi-kart-alt'><button class='angi-iptal-btn' data-sysid='" + sysid + "'><i class='fa-solid fa-stop'></i><span>" + (t.angiIptal || "İPTAL ET") + "</span></button></div>";
      html += "</div>";
    }
    icerikEl.innerHTML = html;

    // Iptal butonlari
    icerikEl.querySelectorAll(".angi-iptal-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const sid = parseInt(btn.dataset.sysid);
        if (typeof angajmanIptalGonder === "function") angajmanIptalGonder(sid);
      });
    });
  }

  // --- WS'ten gelen canli veri (window.angajmanCanliGuncelle) ---
  window.angajmanCanliGuncelle = function (veri) {
    canliVeri = veri || {};
    // aktifAngajmanlar global'ini de guncelle (uyumluluk)
    if (typeof aktifAngajmanlar !== "undefined") {
      for (const k of Object.keys(aktifAngajmanlar)) {
        if (!canliVeri[k]) delete aktifAngajmanlar[k];
      }
      for (const k of Object.keys(canliVeri)) {
        aktifAngajmanlar[k] = canliVeri[k];
      }
    }
    // Popup aciksa guncelle
    if (popupEl) icerikCiz();
  };

  // --- Global erisim ---
  window.angajmanIzleAcKapat = popupAcKapat;
  // Sadece ac (angajman baslatildiginda cagrilir; acik ise dokunmaz)
  window.angajmanIzleAc = function () {
    if (!popupEl) { popupOlustur(); icerikCiz(); }
  };

})();

/* FAZ18-IS2B-IKON-METIN-SPAN */
