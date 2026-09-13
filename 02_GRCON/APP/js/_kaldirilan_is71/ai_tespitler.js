// FAZ18-IS27-28-30: ikon+metin dugmelerinde metin <span> icine
// sarildi. Sebep: dugme_birlik.css yalniz-ikon kurali
// `:has(> i):not(:has(> span))` bu dugmeleri 26px kareye
// zorluyordu ve metin tasiyordu. CSS EZILMEDI; sozlesmeye
// uyuldu. Yalniz-ikon dugmelere DOKUNULMADI.
/* =====================================================================
   AI TESPITLER (v2.4.0)
   - Kayitsiz Tespitler popup'i: sisteme kayitli olmayan yuz/plaka
     tespitleri; "yeni kisiye ekle / mevcut kisiye ekle / yeni arac
     tanimla / yok say" islemleri.
   - Tespit Gecmisi popup'i: tur/kamera/tarih filtreli detayli gecmis.
   - Tespit Detay modali: buyuk fotograf + 3 sn video klip oynatma.
   Sunucu tarafi: goktungu/ai_yonetici.py (WS: ai_tespit_*)
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
  function kameraAd(kid) {
    const k = (window._kameralarSon || []).find((x) => x.id === kid);
    return k ? (k.isim || k.ad) : ("Kamera #" + kid);
  }
  function tarihYaz(ts) {
    if (!ts) return "";
    const d = new Date(ts * 1000);
    return d.toLocaleDateString() + " " +
           d.toLocaleTimeString([], {hour: "2-digit", minute: "2-digit",
                                     second: "2-digit"});
  }
  function svSinif(seviye) {
    const s = (seviye || "").toUpperCase();
    return s === "ARANILAN" ? "sv-aranilan" :
           s === "GUVENSIZ" ? "sv-guvensiz" : "sv-guvenli";
  }

  // Son gelen listeler (baska modullerin de erisimi icin)
  let kayitsizlar = [];
  let gecmis = [];

  // ==================================================================
  // TESPIT DETAY MODALI (foto + 3sn klip)
  // ==================================================================
  const dPerde  = document.getElementById("aiDetayPerde");
  const dIcerik = document.getElementById("aiDetayIcerik");
  const btnDKapat = document.getElementById("btnAiDetayKapat");

  function detayAc(tsp) {
    if (!dPerde || !dIcerik) return;
    dIcerik.innerHTML = "";
    if (tsp.foto) {
      const im = document.createElement("img");
      im.src = (window.goktunguYol ? goktunguYol(tsp.foto) : "/" + tsp.foto);
      im.onerror = () => im.remove();
      dIcerik.appendChild(im);
    }
    if (tsp.klip) {
      const vd = document.createElement("video");
      vd.src = (window.goktunguYol ? goktunguYol(tsp.klip) : "/" + tsp.klip);
      vd.controls = true;
      vd.loop = true;
      vd.muted = true;
      vd.autoplay = true;
      dIcerik.appendChild(vd);
    }
    const meta = document.createElement("div");
    meta.className = "detay-meta";
    const kimlik = tsp.kisi_ad ||
      (tsp.kisi && tsp.kisi.ad) ||
      tsp.arac_plaka || (tsp.arac && tsp.arac.plaka) ||
      tsp.etiket || tsp.plaka_metin ||
      t("aiBilinmiyor", "Bilinmiyor");
    meta.innerHTML =
      "<b>" + t("aigKimlik", "Kimlik") + ":</b> " + kimlik + "<br>" +
      "<b>" + t("aigTur2", "Tür") + ":</b> " + turAdi(tsp.tur) +
      "<br>" +
      "<b>" + t("aigKamera", "Kamera") + ":</b> " +
      kameraAd(tsp.kamera_id) + "<br>" +
      "<b>" + t("aigZaman", "Zaman") + ":</b> " + tarihYaz(tsp.ts) +
      (tsp.benzerlik ? "<br><b>" + t("aigBenzerlik", "Benzerlik") +
        ":</b> " + Math.round(tsp.benzerlik * 100) + "%" : "") +
      (tsp.guven ? "<br><b>" + t("aigGuven", "Güven") + ":</b> " +
        Math.round(tsp.guven * 100) + "%" : "");
    dIcerik.appendChild(meta);
    dPerde.style.display = "flex";
  }
  function detayKapat() {
    if (dPerde) dPerde.style.display = "none";
    if (dIcerik) dIcerik.innerHTML = ""; // videoyu durdur
  }
  if (btnDKapat) btnDKapat.addEventListener("click", detayKapat);
  if (dPerde) dPerde.addEventListener("click", (e) => {
    if (e.target === dPerde) detayKapat();
  });
  window.aiTespitDetayAc = detayAc;

  // ==================================================================
  // ORTAK: tespit satiri
  // ==================================================================
  // v2.4.2: tespit turu -> ikon ve etiket (yeni turler dahil)
  const TUR_IKONLARI = {
    yuz: "fa-user", insan: "fa-person-walking",
    plaka: "fa-car", kara_araci: "fa-truck",
    hava_araci: "fa-helicopter"
  };
  function turIkon(tur) {
    return '<i class="fa-solid ' + (TUR_IKONLARI[tur] || "fa-eye") +
           '"></i>';
  }
  function turAdi(tur) {
    if (tur === "yuz") return t("aigYuz", "Y\u00dcZ");
    if (tur === "plaka") return t("aigPlaka", "PLAKA");
    if (tur === "hava_araci") return t("aiTurHava", "HAVA ARACI");
    if (tur === "insan") return t("aiTurInsan", "\u0130NSAN");
    if (tur === "kara_araci") return t("aiTurKara", "KARA ARACI");
    return (tur || "").toUpperCase();
  }

  function tespitFoto(tsp) {
    const kaynak = tsp.foto ? "/" + tsp.foto :
      (tsp.onizleme_b64 ? "data:image/jpeg;base64," + tsp.onizleme_b64 : "");
    if (kaynak) {
      const im = document.createElement("img");
      im.className = "ai-tespit-foto";
      im.src = kaynak;
      im.onerror = () => {
        const yer = document.createElement("div");
        yer.className = "ai-tespit-foto yok";
        yer.innerHTML = turIkon(tsp.tur);
        im.replaceWith(yer);
      };
      return im;
    }
    const yer = document.createElement("div");
    yer.className = "ai-tespit-foto yok";
    yer.innerHTML = turIkon(tsp.tur);
    return yer;
  }

  function tespitBilgi(tsp) {
    const bilgi = document.createElement("div");
    bilgi.className = "ai-satir-bilgi";
    const ad = document.createElement("div");
    ad.className = "ad";
    const kimlik = tsp.kisi_ad || tsp.arac_plaka ||
      tsp.etiket || tsp.plaka_metin || "";
    ad.textContent = kimlik || t("aiBilinmiyor", "Bilinmiyor");
    if (!kimlik) ad.style.color = "var(--soluk)";
    const alt = document.createElement("div");
    alt.className = "alt";
    alt.textContent = turAdi(tsp.tur) +
      "  ·  " + kameraAd(tsp.kamera_id) + "  ·  " + tarihYaz(tsp.ts);
    bilgi.appendChild(ad); bilgi.appendChild(alt);
    return bilgi;
  }

  // ==================================================================
  // KAYITSIZ TESPITLER POPUP
  // ==================================================================
  const kzPop   = document.getElementById("aiKayitsizPopup");
  const kzListe = document.getElementById("aiKayitsizListe");
  let kayitsizAcik = false;

  function kayitsizAc() {
    const acikti = !kzPop.classList.contains("popup-gizli");
    if (acikti) { kayitsizKapat(); return; }
    kzPop.classList.remove("popup-gizli");
    kayitsizAcik = true;
    kayitsizYenile();
    if (typeof window.popupTikleriGuncelle === "function")
      window.popupTikleriGuncelle();
  }
  function kayitsizKapat() {
    kzPop.classList.add("popup-gizli");
    kayitsizAcik = false;
    if (typeof window.popupTikleriGuncelle === "function")
      window.popupTikleriGuncelle();
  }
  function kayitsizYenile() {
    gonder({tip: "ai_tespit_gecmis", sadece_kayitsiz: true, limit: 200});
  }
  const mbKz = document.getElementById("mbAIKayitsiz");
  if (mbKz) mbKz.addEventListener("click", (e) => {
    e.stopPropagation(); kayitsizAc();
  });
  const btnKzKapat = document.getElementById("btnAiKayitsizKapat");
  if (btnKzKapat) btnKzKapat.addEventListener("click", kayitsizKapat);
  const btnKzYenile = document.getElementById("btnAiKayitsizYenile");
  if (btnKzYenile) btnKzYenile.addEventListener("click", kayitsizYenile);

  function kayitsizSatir(tsp) {
    const sat = document.createElement("div");
    sat.className = "ai-tespit-satir";
    sat.style.cursor = "default";
    const foto = tespitFoto(tsp);
    foto.style.cursor = "pointer";
    foto.addEventListener("click", () => detayAc(tsp));
    sat.appendChild(foto);

    const bilgi = tespitBilgi(tsp);

    // Islem dugmeleri
    const islemler = document.createElement("div");
    islemler.className = "ai-kayitsiz-islem";
    if (tsp.tur === "yuz") {
      const bYeniK = document.createElement("button");
      bYeniK.innerHTML = '<i class="fa-solid fa-user-plus"></i> ' + "<span>" + (
        t("aiYeniKisiyeEkle", "Yeni kişiye ekle")) + "</span>";
      bYeniK.addEventListener("click", () => yeniKisiyeEkle(tsp));
      const bMevcut = document.createElement("button");
      bMevcut.innerHTML = '<i class="fa-solid fa-user-check"></i> ' + "<span>" + (
        t("aiMevcutKisiyeEkle", "Mevcut kişiye ekle")) + "</span>";
      bMevcut.addEventListener("click", () => mevcutKisiyeEkle(tsp, bMevcut));
      islemler.appendChild(bYeniK);
      islemler.appendChild(bMevcut);
    } else {
      const bYeniA = document.createElement("button");
      bYeniA.innerHTML = '<i class="fa-solid fa-car"></i> ' + "<span>" + (
        t("aiYeniAracTanimla", "Yeni araç tanımla")) + "</span>";
      bYeniA.addEventListener("click", () => yeniAracTanimla(tsp));
      islemler.appendChild(bYeniA);
    }
    const bYok = document.createElement("button");
    bYok.innerHTML = '<i class="fa-solid fa-eye-slash"></i> ' + "<span>" + (
      t("aiYoksay", "Yok say")) + "</span>";
    bYok.addEventListener("click", () => {
      gonder({tip: "ai_tespit_islem", islem: "yoksay",
              tespit_id: tsp.id});
    });
    islemler.appendChild(bYok);
    bilgi.appendChild(islemler);
    sat.appendChild(bilgi);
    return sat;
  }

  // Yeni kisiye ekle: ad sor, kisi olusturulunca tespit fotografini
  // yuz kaydi olarak ekle ve tespiti kisiyle iliskilendir.
  let bekleyenYuzTespit = null;
  function yeniKisiyeEkle(tsp) {
    const ad = prompt(t("aiYeniKisiAdSor", "Yeni kişinin adı soyadı:"));
    if (!ad || !ad.trim()) return;
    bekleyenYuzTespit = tsp;
    gonder({tip: "kisi_kaydet", ad: ad.trim(), seviye: "GUVENSIZ",
            notlar: t("aiOtoNot", "Kayıtsız tespitten eklendi")});
    // kisi_listesi duyurusu gelince en yeni kisiye foto eklenir
    // (asagida aiKisiListesiIsle zincirine kanca)
  }
  const oncekiKisiIsle = window.aiKisiListesiIsle;
  window.aiKisiListesiIsle = function (m) {
    if (typeof oncekiKisiIsle === "function") oncekiKisiIsle(m);
    if (!bekleyenYuzTespit) return;
    const tsp = bekleyenYuzTespit;
    bekleyenYuzTespit = null;
    const kisiler = m.kisiler || [];
    if (!kisiler.length) return;
    // En son eklenen kisi (en buyuk id)
    const yeni = kisiler.reduce((a, b) => (a.id > b.id ? a : b));
    tespitFotoyuKisiyeEkle(tsp, yeni.id);
  };
  function tespitFotoyuKisiyeEkle(tsp, kisiId) {
    // Tespiti kisiye ata
    gonder({tip: "ai_tespit_islem", islem: "kisi_ata",
            tespit_id: tsp.id, kisi_id: kisiId});
    // Tespit fotografini yuz kaydi olarak ekle (sunucudan indirilip
    // b64'e cevrilir)
    if (!tsp.foto) return;
    fetch(window.goktunguYol ? goktunguYol(tsp.foto) : "/" + tsp.foto)
      .then((c) => c.blob())
      .then((blob) => new Promise((coz) => {
        const fr = new FileReader();
        fr.onload = () => coz(fr.result);
        fr.readAsDataURL(blob);
      }))
      .then((dataUrl) => {
        const b64 = String(dataUrl).split(",")[1] || "";
        if (b64) gonder({tip: "kisi_yuz_ekle", kisi_id: kisiId,
                         foto_b64: b64});
        setTimeout(kayitsizYenile, 600);
      })
      .catch(() => setTimeout(kayitsizYenile, 600));
  }
  // Mevcut kisiye ekle: satir ici kisi secim listesi
  function mevcutKisiyeEkle(tsp, dugme) {
    const kisiler = window._aiKisilerSon || [];
    if (!kisiler.length) {
      gonder({tip: "kisi_listele"});
      alert(t("aiKisiYok", "Kayıtlı kişi yok"));
      return;
    }
    // Basit secim: prompt ile numarali liste
    const secenekler = kisiler.map((k, i) =>
      (i + 1) + ") " + k.ad).join("\n");
    const cevap = prompt(
      t("aiKisiSec", "Kişi seçin (numara girin):") + "\n" + secenekler);
    const idx = parseInt(cevap) - 1;
    if (isNaN(idx) || idx < 0 || idx >= kisiler.length) return;
    tespitFotoyuKisiyeEkle(tsp, kisiler[idx].id);
  }
  // Yeni arac tanimla: plaka onerili form
  function yeniAracTanimla(tsp) {
    const plaka = prompt(t("aiPlakaSor", "Araç plakası:"),
                         tsp.etiket || tsp.plaka_metin || "");
    if (!plaka || !plaka.trim()) return;
    bekleyenAracTespit = tsp;
    gonder({tip: "arac_kaydet", plaka: plaka.trim().toUpperCase(),
            seviye: "GUVENSIZ",
            notlar: t("aiOtoNot", "Kayıtsız tespitten eklendi")});
  }
  let bekleyenAracTespit = null;
  const oncekiAracIsle = window.aiAracListesiIsle;
  window.aiAracListesiIsle = function (m) {
    if (typeof oncekiAracIsle === "function") oncekiAracIsle(m);
    if (!bekleyenAracTespit) return;
    const tsp = bekleyenAracTespit;
    bekleyenAracTespit = null;
    const araclar = m.araclar || [];
    if (!araclar.length) return;
    const yeni = araclar.reduce((a, b) => (a.id > b.id ? a : b));
    gonder({tip: "ai_tespit_islem", islem: "arac_ata",
            tespit_id: tsp.id, arac_id: yeni.id});
    setTimeout(kayitsizYenile, 600);
  };

  // ==================================================================
  // TESPIT GECMISI POPUP
  // ==================================================================
  const gcPop    = document.getElementById("aiGecmisPopup");
  const gcListe  = document.getElementById("aiGecmisListe");
  const gcTur    = document.getElementById("aigTur");
  const gcKamera = document.getElementById("aigKamera");
  const gcTarih  = document.getElementById("aigTarih");
  let gecmisAcik = false;

  function gecmisAc() {
    const acikti = !gcPop.classList.contains("popup-gizli");
    if (acikti) { gecmisKapat(); return; }
    gcPop.classList.remove("popup-gizli");
    gecmisAcik = true;
    kameraCombosuDoldur();
    gecmisAra();
    if (typeof window.popupTikleriGuncelle === "function")
      window.popupTikleriGuncelle();
  }
  function gecmisKapat() {
    gcPop.classList.add("popup-gizli");
    gecmisAcik = false;
    if (typeof window.popupTikleriGuncelle === "function")
      window.popupTikleriGuncelle();
  }
  function kameraCombosuDoldur() {
    if (!gcKamera) return;
    const secili = gcKamera.value;
    gcKamera.innerHTML = "";
    const hepsi = document.createElement("option");
    hepsi.value = "";
    hepsi.textContent = t("aigTumKameralar", "TÜM KAMERALAR");
    gcKamera.appendChild(hepsi);
    (window._kameralarSon || []).forEach((k) => {
      const o = document.createElement("option");
      o.value = k.id;
      o.textContent = k.isim || k.ad || ("Kamera #" + k.id);
      gcKamera.appendChild(o);
    });
    gcKamera.value = secili || "";
  }
  function gecmisAra() {
    const istek = {tip: "ai_tespit_gecmis", limit: 300};
    if (gcTur && gcTur.value) istek.tur = gcTur.value;
    if (gcKamera && gcKamera.value)
      istek.kamera_id = parseInt(gcKamera.value);
    if (gcTarih && gcTarih.value) {
      const bas = new Date(gcTarih.value + "T00:00:00");
      istek.baslangic = bas.getTime() / 1000;
      istek.bitis = istek.baslangic + 86400;
    }
    gonder(istek);
  }
  const mbGc = document.getElementById("mbAIGecmis");
  if (mbGc) mbGc.addEventListener("click", (e) => {
    e.stopPropagation(); gecmisAc();
  });
  const btnGcKapat = document.getElementById("btnAiGecmisKapat");
  if (btnGcKapat) btnGcKapat.addEventListener("click", gecmisKapat);
  const btnGcAra = document.getElementById("btnAiGecmisAra");
  if (btnGcAra) btnGcAra.addEventListener("click", gecmisAra);

  function gecmisSatir(tsp) {
    const sat = document.createElement("div");
    sat.className = "ai-tespit-satir";
    sat.appendChild(tespitFoto(tsp));
    sat.appendChild(tespitBilgi(tsp));
    const seviye = tsp.seviye || tsp.kisi_seviye || tsp.arac_seviye;
    if (seviye) {
      const sv = document.createElement("span");
      sv.className = "sv-rozet " + svSinif(seviye);
      sv.textContent = seviye;
      sat.appendChild(sv);
    }
    if (tsp.klip) {
      const kl = document.createElement("i");
      kl.className = "fa-solid fa-film";
      kl.title = t("aiKlipVar", "3 sn video klip mevcut");
      kl.style.color = "var(--vurgu)";
      sat.appendChild(kl);
    }
    sat.addEventListener("click", () => detayAc(tsp));
    return sat;
  }

  // ==================================================================
  // WS cevap isleme: ayni mesaj tipi iki popup'i da besler.
  // sadece_kayitsiz isteklerini ayirt etmek icin istek aninda bayrak
  // kullanilamaz (tek yayin); tespitin kisi/arac atamasi bos ve
  // incelendi=0 ise kayitsiz listesine, aksi halde gecmise gider.
  // Basit yontem: acik olan popup'lara gore ciz.
  // ==================================================================
  window.aiTespitGecmisiIsle = function (m) {
    const tespitler = m.tespitler || [];
    const kayitsizGelen = tespitler.every((x) =>
      !x.kisi_id && !x.arac_id && !x.incelendi) && kayitsizAcik;
    // Kayitsiz penceresi acik ve liste tamamen kayitsizsa oraya ciz
    if (kayitsizGelen && kzListe) {
      kayitsizlar = tespitler;
      kzListe.innerHTML = "";
      if (!tespitler.length) {
        /* FAZ18/IS7: duz gri metin yerine buyuk ikonlu bos durum. */
        kzListe.appendChild(window.bosPanelYap
          ? window.bosPanelYap(t("aiKayitsizYok", "Kayıtsız tespit yok"),
                               "fa-solid fa-user-secret")
          : (function () {
              const b = document.createElement("div");
              b.className = "ai-satir";
              b.style.justifyContent = "center";
              b.style.color = "var(--soluk)";
              b.textContent = t("aiKayitsizYok", "Kayıtsız tespit yok");
              return b;
            })());
      } else {
        tespitler.forEach((tsp) =>
          kzListe.appendChild(kayitsizSatir(tsp)));
      }
      // Gecmis de acik olabilir: ayri sorgu atmasi icin bir sey yapma
      if (!gecmisAcik) return;
      return;
    }
    if (gcListe) {
      gecmis = tespitler;
      gcListe.innerHTML = "";
      if (!tespitler.length) {
        /* FAZ18/IS7: duz gri metin yerine buyuk ikonlu bos durum. */
        gcListe.appendChild(window.bosPanelYap
          ? window.bosPanelYap(t("aiGecmisYok", "Kayıt bulunamadı"),
                               "fa-solid fa-clock-rotate-left")
          : (function () {
              const b = document.createElement("div");
              b.className = "ai-satir";
              b.style.justifyContent = "center";
              b.style.color = "var(--soluk)";
              b.textContent = t("aiGecmisYok", "Kayıt bulunamadı");
              return b;
            })());
        return;
      }
      tespitler.forEach((tsp) => gcListe.appendChild(gecmisSatir(tsp)));
    }
  };

  window.aiIslemSonucIsle = function (m) {
    if (m.tamam && kayitsizAcik) kayitsizYenile();
  };

  // Canli tespit geldiginde acik listeleri tazele (alt panel akisi
  // ai_panel.js'te ayrica islenir)
  const oncekiCanli = window.aiCanliTespitIsle;
  window.aiCanliTespitIsle = function (m) {
    if (typeof oncekiCanli === "function") oncekiCanli(m);
    const tsp = (m && m.tespit) || {};
    const kayitli = (tsp.kisi || tsp.arac);
    if (kayitsizAcik && !kayitli) kayitsizYenile();
    if (gecmisAcik) gecmisAra();
  };
})();
