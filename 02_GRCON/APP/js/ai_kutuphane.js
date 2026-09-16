/* =====================================================================
   AI KUTUPHANE (v2.4.0)
   Kisiler: kisi CRUD + arama seviyesi + yuz kaydi (webcam / dosya).
   Araclar: arac CRUD (plaka, marka, model, renk) + arama seviyesi.
   Sunucu tarafi: gozcu/kutuphane.py (WS: kisi_*, arac_*)
   ===================================================================== */
(function () {
  "use strict";

  function t(anahtar, varsayilan) {
    try {
      const d = (typeof D === "function") ? D() : null;
      return (d && d[anahtar]) || varsayilan;
    } catch (e) { return varsayilan; }
  }
  function gonder(obj) {
    try {
      if (typeof ws !== "undefined" && ws && ws.readyState === 1) {
        ws.send(JSON.stringify(obj));
        return true;
      }
    } catch (e) {}
    return false;
  }
  function svRozet(seviye) {
    const sp = document.createElement("span");
    const s = (seviye || "GUVENLI").toUpperCase();
    sp.className = "sv-rozet " +
      (s === "ARANILAN" ? "sv-aranilan" :
       s === "GUVENSIZ" ? "sv-guvensiz" : "sv-guvenli");
    sp.textContent =
      s === "ARANILAN" ? t("svAranilan", "ARANILAN") :
      s === "GUVENSIZ" ? t("svGuvensiz", "GÜVENSİZ") :
                         t("svGuvenli", "GÜVENLİ");
    return sp;
  }
  function onayla(soru, evet) {
    if (typeof window.onayIste === "function") window.onayIste(soru, evet);
    else if (confirm(soru)) evet();
  }

  // ==================================================================
  // KISILER
  // ==================================================================
  const kPop      = document.getElementById("aiKisiPopup");
  const kListe    = document.getElementById("aiKisiListe");
  const kForm     = document.getElementById("aiKisiForm");
  const kAd       = document.getElementById("aikAd");
  const kSeviye   = document.getElementById("aikSeviye");
  const kNotlar   = document.getElementById("aikNotlar");
  const kMesaj    = document.getElementById("aikMesaj");
  const kAra      = document.getElementById("aiKisiAra");
  let kisiDuzenId = null;
  let sonKisiler  = [];

  function kisiPopupAc() {
    const acikti = !kPop.classList.contains("popup-gizli");
    if (acikti) { kisiPopupKapat(); return; }
    kPop.classList.remove("popup-gizli");
    kForm.style.display = "none";
    gonder({tip: "kisi_listele"});
    if (typeof window.popupTikleriGuncelle === "function")
      window.popupTikleriGuncelle();
  }
  function kisiPopupKapat() {
    kPop.classList.add("popup-gizli");
    if (typeof window.popupTikleriGuncelle === "function")
      window.popupTikleriGuncelle();
  }
  const mbK = document.getElementById("mbAIKisiler");
  if (mbK) mbK.addEventListener("click", (e) => {
    e.stopPropagation(); kisiPopupAc();
  });
  const btnKKapat = document.getElementById("btnAiKisiKapat");
  if (btnKKapat) btnKKapat.addEventListener("click", kisiPopupKapat);

  function kisiFormGoster(kisi) {
    kisiDuzenId = kisi ? kisi.id : null;
    kAd.value = kisi ? (kisi.ad || "") : "";
    kSeviye.value = kisi ? (kisi.seviye || "GUVENLI") : "GUVENLI";
    kNotlar.value = kisi ? (kisi.notlar || "") : "";
    kMesaj.textContent = "";
    kForm.style.display = "";
    kAd.focus();
  }
  const btnKYeni = document.getElementById("btnAiKisiYeni");
  if (btnKYeni) btnKYeni.addEventListener("click", () => {
    (kForm.style.display === "none") ? kisiFormGoster(null)
                                     : (kForm.style.display = "none");
  });
  const btnKVazgec = document.getElementById("btnAiKisiVazgec");
  if (btnKVazgec) btnKVazgec.addEventListener("click", () => {
    kForm.style.display = "none";
  });
  const btnKKaydet = document.getElementById("btnAiKisiKaydet");
  if (btnKKaydet) btnKKaydet.addEventListener("click", () => {
    const ad = kAd.value.trim();
    if (!ad) {
      kMesaj.textContent = t("aiKisiAdGerekli", "Ad Soyad zorunludur");
      kMesaj.style.color = "var(--kotu)";
      return;
    }
    gonder({tip: "kisi_kaydet", id: kisiDuzenId, ad: ad,
            seviye: kSeviye.value, notlar: kNotlar.value.trim()});
    kForm.style.display = "none";
  });
  if (kAra) kAra.addEventListener("input", () => kisiListeCiz());

  function kisiSatir(kisi) {
    const sat = document.createElement("div");
    sat.className = "ai-satir";
    sat.style.alignItems = "flex-start";

    // Ilk yuz fotografi veya ikon
    const foto = document.createElement("div");
    foto.style.cssText =
      "width:44px;height:44px;border-radius:50%;overflow:hidden;" +
      "flex-shrink:0;border:1px solid var(--cizgi);display:flex;" +
      "align-items:center;justify-content:center;color:var(--soluk);";
    if (kisi.yuzler && kisi.yuzler.length) {
      const im = document.createElement("img");
      im.src = (window.gozcuYol ? gozcuYol(kisi.yuzler[0].dosya)
                                 : "/" + kisi.yuzler[0].dosya);
      im.style.cssText = "width:100%;height:100%;object-fit:cover;";
      im.onerror = () => {
        foto.innerHTML = '<i class="fa-solid fa-user"></i>';
      };
      foto.appendChild(im);
    } else {
      foto.innerHTML = '<i class="fa-solid fa-user"></i>';
    }
    sat.appendChild(foto);

    const bilgi = document.createElement("div");
    bilgi.className = "ai-satir-bilgi";
    const ad = document.createElement("div");
    ad.className = "ad";
    ad.textContent = kisi.ad;
    const alt = document.createElement("div");
    alt.className = "alt";
    const yuzSayi = (kisi.yuzler || []).length;
    alt.textContent = yuzSayi + " " + t("aiYuzKaydi", "yüz kaydı") +
                      (kisi.notlar ? "  ·  " + kisi.notlar : "");
    bilgi.appendChild(ad); bilgi.appendChild(alt);

    // Yuz mini galerisi
    if (yuzSayi) {
      const mini = document.createElement("div");
      mini.className = "ai-yuz-mini";
      kisi.yuzler.forEach((y) => {
        const kut = document.createElement("div");
        kut.className = "yuz-kut";
        const im = document.createElement("img");
        im.src = (window.gozcuYol ? gozcuYol(y.dosya) : "/" + y.dosya);
        kut.appendChild(im);
        const sil = document.createElement("button");
        sil.className = "yuz-sil";
        sil.innerHTML = "&times;";
        sil.title = t("btnSil", "Sil");
        sil.addEventListener("click", (e) => {
          e.stopPropagation();
          onayla(t("aiYuzSilOnay", "Yüz kaydı silinsin mi?"),
                 () => gonder({tip: "kisi_yuz_sil", yuz_id: y.id}));
        });
        kut.appendChild(sil);
        mini.appendChild(kut);
      });
      bilgi.appendChild(mini);
    }
    sat.appendChild(bilgi);
    sat.appendChild(svRozet(kisi.seviye));

    const btnlar = document.createElement("div");
    btnlar.className = "ai-satir-btnlar";
    const bY = document.createElement("button");
    bY.innerHTML = '<i class="fa-solid fa-id-badge"></i>';
    bY.title = t("aiYuzBaslik", "Yüz Kaydı");
    bY.addEventListener("click", () => yuzModalAc(kisi));
    const bD = document.createElement("button");
    bD.innerHTML = '<i class="fa-solid fa-pen"></i>';
    bD.title = t("btnDuzenle", "Düzenle");
    bD.addEventListener("click", () => kisiFormGoster(kisi));
    const bS = document.createElement("button");
    bS.className = "tehlike";
    bS.innerHTML = '<i class="fa-solid fa-trash"></i>';
    bS.title = t("btnSil", "Sil");
    bS.addEventListener("click", () => {
      onayla(t("aiKisiSilOnay", "Kişi silinsin mi?") + " (" + kisi.ad + ")",
             () => gonder({tip: "kisi_sil", id: kisi.id}));
    });
    btnlar.appendChild(bY); btnlar.appendChild(bD); btnlar.appendChild(bS);
    sat.appendChild(btnlar);
    return sat;
  }

  function kisiListeCiz() {
    if (!kListe) return;
    const f = (kAra && kAra.value || "").toLocaleLowerCase("tr");
    kListe.innerHTML = "";
    const suzgec = sonKisiler.filter((kisi) =>
      !f || (kisi.ad || "").toLocaleLowerCase("tr").includes(f) ||
      (kisi.notlar || "").toLocaleLowerCase("tr").includes(f));
    if (!suzgec.length) {
      const bos = document.createElement("div");
      bos.className = "ai-satir";
      bos.style.justifyContent = "center";
      bos.style.color = "var(--soluk)";
      bos.textContent = t("aiKisiYok", "Kayıtlı kişi yok");
      kListe.appendChild(bos);
      return;
    }
    suzgec.forEach((kisi) => kListe.appendChild(kisiSatir(kisi)));
  }

  window.aiKisiListesiIsle = function (m) {
    sonKisiler = m.kisiler || [];
    window._aiKisilerSon = sonKisiler;
    kisiListeCiz();
    // Yuz modali acik olan kisi guncellenirse galerisini tazele
    if (yuzKisi) {
      const g = sonKisiler.find((x) => x.id === yuzKisi.id);
      if (g) { yuzKisi = g; yuzGaleriCiz(); }
    }
  };

  // ==================================================================
  // YUZ KAYDI MODALI (webcam / dosya)
  // ==================================================================
  const yzPerde  = document.getElementById("aiYuzPerde");
  const yzKisiAd = document.getElementById("aiYuzKisiAd");
  const yzVideo  = document.getElementById("aiYuzVideo");
  const yzKamAlan = document.getElementById("aiYuzKameraAlan");
  const yzGaleri = document.getElementById("aiYuzGaleri");
  const yzDurum  = document.getElementById("aiYuzDurum");
  const yzDosyaIn = document.getElementById("aiYuzDosyaInput");
  let yuzKisi = null;
  let yzAkis = null;

  function yuzModalAc(kisi) {
    yuzKisi = kisi;
    if (yzKisiAd) yzKisiAd.textContent = kisi.ad;
    yzDurum.textContent = "";
    yzDurum.className = "";
    yzKamAlan.style.display = "none";
    yzPerde.style.display = "flex";
    yuzGaleriCiz();
  }
  function yuzModalKapat() {
    yzPerde.style.display = "none";
    yuzKisi = null;
    kameraDurdur();
  }
  function kameraDurdur() {
    if (yzAkis) {
      yzAkis.getTracks().forEach((tr) => tr.stop());
      yzAkis = null;
    }
    if (yzVideo) yzVideo.srcObject = null;
    yzKamAlan.style.display = "none";
  }
  function yuzGaleriCiz() {
    if (!yzGaleri || !yuzKisi) return;
    yzGaleri.innerHTML = "";
    (yuzKisi.yuzler || []).forEach((y) => {
      const im = document.createElement("img");
      im.src = (window.gozcuYol ? gozcuYol(y.dosya) : "/" + y.dosya) +
               "?t=" + Date.now();
      yzGaleri.appendChild(im);
    });
  }
  function durum(metin, sinif) {
    yzDurum.textContent = metin;
    yzDurum.className = sinif || "";
  }
  function fotoGonder(dataUrl) {
    if (!yuzKisi) return;
    const b64 = dataUrl.split(",")[1] || "";
    durum(t("aiYuzIsleniyor", "Yüz işleniyor..."), "");
    gonder({tip: "kisi_yuz_ekle", kisi_id: yuzKisi.id, foto_b64: b64});
  }
  // Canvas ile 640px'e olcekleyip JPEG dataURL uret
  function olcekle(kaynak, w, h, cb) {
    const MAKS = 640;
    let nw = w, nh = h;
    if (Math.max(w, h) > MAKS) {
      const oran = MAKS / Math.max(w, h);
      nw = Math.round(w * oran); nh = Math.round(h * oran);
    }
    const cv = document.createElement("canvas");
    cv.width = nw; cv.height = nh;
    cv.getContext("2d").drawImage(kaynak, 0, 0, nw, nh);
    cb(cv.toDataURL("image/jpeg", 0.85));
  }

  const btnYzKam = document.getElementById("btnAiYuzKamera");
  if (btnYzKam) btnYzKam.addEventListener("click", async () => {
    if (yzAkis) { kameraDurdur(); return; }
    try {
      yzAkis = await navigator.mediaDevices.getUserMedia(
        {video: {width: 640, height: 480}});
      yzVideo.srcObject = yzAkis;
      yzKamAlan.style.display = "";
      durum("", "");
    } catch (e) {
      durum(t("aiKameraHata", "Web kamerasına erişilemedi: ") +
            (e.message || e.name), "hata");
    }
  });
  const btnYzCek = document.getElementById("btnAiYuzCek");
  if (btnYzCek) btnYzCek.addEventListener("click", () => {
    if (!yzAkis || !yzVideo.videoWidth) return;
    olcekle(yzVideo, yzVideo.videoWidth, yzVideo.videoHeight, fotoGonder);
  });
  const btnYzDosya = document.getElementById("btnAiYuzDosya");
  if (btnYzDosya) btnYzDosya.addEventListener("click", () => {
    if (yzDosyaIn) yzDosyaIn.click();
  });
  if (yzDosyaIn) yzDosyaIn.addEventListener("change", () => {
    Array.from(yzDosyaIn.files || []).forEach((dosya) => {
      const im = new Image();
      im.onload = () => olcekle(im, im.width, im.height, fotoGonder);
      im.src = URL.createObjectURL(dosya);
    });
    yzDosyaIn.value = "";
  });
  const btnYzKapat = document.getElementById("btnAiYuzKapat");
  if (btnYzKapat) btnYzKapat.addEventListener("click", yuzModalKapat);
  if (yzPerde) yzPerde.addEventListener("click", (e) => {
    if (e.target === yzPerde) yuzModalKapat();
  });

  window.aiKisiYuzSonucIsle = function (m) {
    if (m.tamam) {
      durum(t("aiYuzEklendi", "Yüz kaydı eklendi"), "iyi");
    } else {
      durum(t("aiYuzHata", "Yüz kaydedilemedi: ") + (m.hata || ""), "hata");
    }
  };

  // ==================================================================
  // ARACLAR
  // ==================================================================
  const aPop    = document.getElementById("aiAracPopup");
  const aListe  = document.getElementById("aiAracListe");
  const aForm   = document.getElementById("aiAracForm");
  const aPlaka  = document.getElementById("aiaPlaka");
  const aMarka  = document.getElementById("aiaMarka");
  const aModel  = document.getElementById("aiaModel");
  const aRenk   = document.getElementById("aiaRenk");
  const aSeviye = document.getElementById("aiaSeviye");
  const aNotlar = document.getElementById("aiaNotlar");
  const aMesaj  = document.getElementById("aiaMesaj");
  const aAra    = document.getElementById("aiAracAra");
  let aracDuzenId = null;
  let sonAraclar  = [];

  function aracPopupAc() {
    const acikti = !aPop.classList.contains("popup-gizli");
    if (acikti) { aracPopupKapat(); return; }
    aPop.classList.remove("popup-gizli");
    aForm.style.display = "none";
    gonder({tip: "arac_listele"});
    if (typeof window.popupTikleriGuncelle === "function")
      window.popupTikleriGuncelle();
  }
  function aracPopupKapat() {
    aPop.classList.add("popup-gizli");
    if (typeof window.popupTikleriGuncelle === "function")
      window.popupTikleriGuncelle();
  }
  const mbA = document.getElementById("mbAIAraclar");
  if (mbA) mbA.addEventListener("click", (e) => {
    e.stopPropagation(); aracPopupAc();
  });
  const btnAKapat = document.getElementById("btnAiAracKapat");
  if (btnAKapat) btnAKapat.addEventListener("click", aracPopupKapat);

  function aracFormGoster(arac) {
    aracDuzenId = arac ? arac.id : null;
    aPlaka.value  = arac ? (arac.plaka || "") : "";
    aMarka.value  = arac ? (arac.marka || "") : "";
    aModel.value  = arac ? (arac.model || "") : "";
    aRenk.value   = arac ? (arac.renk || "") : "";
    aSeviye.value = arac ? (arac.seviye || "GUVENLI") : "GUVENLI";
    aNotlar.value = arac ? (arac.notlar || "") : "";
    aMesaj.textContent = "";
    aForm.style.display = "";
    aPlaka.focus();
  }
  const btnAYeni = document.getElementById("btnAiAracYeni");
  if (btnAYeni) btnAYeni.addEventListener("click", () => {
    (aForm.style.display === "none") ? aracFormGoster(null)
                                     : (aForm.style.display = "none");
  });
  const btnAVazgec = document.getElementById("btnAiAracVazgec");
  if (btnAVazgec) btnAVazgec.addEventListener("click", () => {
    aForm.style.display = "none";
  });
  const btnAKaydet = document.getElementById("btnAiAracKaydet");
  if (btnAKaydet) btnAKaydet.addEventListener("click", () => {
    const plaka = aPlaka.value.trim().toUpperCase();
    if (!plaka) {
      aMesaj.textContent = t("aiPlakaGerekli", "Plaka zorunludur");
      aMesaj.style.color = "var(--kotu)";
      return;
    }
    gonder({tip: "arac_kaydet", id: aracDuzenId, plaka: plaka,
            marka: aMarka.value.trim(), model: aModel.value.trim(),
            renk: aRenk.value.trim(), seviye: aSeviye.value,
            notlar: aNotlar.value.trim()});
    aForm.style.display = "none";
  });
  if (aAra) aAra.addEventListener("input", () => aracListeCiz());

  function aracSatir(arac) {
    const sat = document.createElement("div");
    sat.className = "ai-satir";

    const ikon = document.createElement("div");
    ikon.style.cssText =
      "width:38px;height:38px;border-radius:8px;flex-shrink:0;" +
      "border:1px solid var(--cizgi);display:flex;align-items:center;" +
      "justify-content:center;color:var(--soluk);font-size:15px;";
    ikon.innerHTML = '<i class="fa-solid fa-car"></i>';
    sat.appendChild(ikon);

    const bilgi = document.createElement("div");
    bilgi.className = "ai-satir-bilgi";
    const ad = document.createElement("div");
    ad.className = "ad";
    ad.textContent = arac.plaka;
    const alt = document.createElement("div");
    alt.className = "alt";
    alt.textContent = [arac.marka, arac.model, arac.renk]
      .filter(Boolean).join(" · ") +
      (arac.notlar ? "  ·  " + arac.notlar : "");
    bilgi.appendChild(ad); bilgi.appendChild(alt);
    sat.appendChild(bilgi);
    sat.appendChild(svRozet(arac.seviye));

    const btnlar = document.createElement("div");
    btnlar.className = "ai-satir-btnlar";
    const bD = document.createElement("button");
    bD.innerHTML = '<i class="fa-solid fa-pen"></i>';
    bD.title = t("btnDuzenle", "Düzenle");
    bD.addEventListener("click", () => aracFormGoster(arac));
    const bS = document.createElement("button");
    bS.className = "tehlike";
    bS.innerHTML = '<i class="fa-solid fa-trash"></i>';
    bS.title = t("btnSil", "Sil");
    bS.addEventListener("click", () => {
      onayla(t("aiAracSilOnay", "Araç silinsin mi?") +
             " (" + arac.plaka + ")",
             () => gonder({tip: "arac_sil", id: arac.id}));
    });
    btnlar.appendChild(bD); btnlar.appendChild(bS);
    sat.appendChild(btnlar);
    return sat;
  }

  function aracListeCiz() {
    if (!aListe) return;
    const f = (aAra && aAra.value || "").toLocaleUpperCase("tr");
    aListe.innerHTML = "";
    const suzgec = sonAraclar.filter((arac) =>
      !f || (arac.plaka || "").toLocaleUpperCase("tr").includes(f) ||
      (arac.marka || "").toLocaleUpperCase("tr").includes(f) ||
      (arac.model || "").toLocaleUpperCase("tr").includes(f));
    if (!suzgec.length) {
      const bos = document.createElement("div");
      bos.className = "ai-satir";
      bos.style.justifyContent = "center";
      bos.style.color = "var(--soluk)";
      bos.textContent = t("aiAracYok", "Kayıtlı araç yok");
      aListe.appendChild(bos);
      return;
    }
    suzgec.forEach((arac) => aListe.appendChild(aracSatir(arac)));
  }

  window.aiAracListesiIsle = function (m) {
    sonAraclar = m.araclar || [];
    window._aiAraclarSon = sonAraclar;
    aracListeCiz();
  };
})();
