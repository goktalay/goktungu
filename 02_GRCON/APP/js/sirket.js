// FAZ18-IS27-28-30: ikon+metin dugmelerinde metin <span> icine
// sarildi. Sebep: dugme_birlik.css yalniz-ikon kurali
// `:has(> i):not(:has(> span))` bu dugmeleri 26px kareye
// zorluyordu ve metin tasiyordu. CSS EZILMEDI; sozlesmeye
// uyuldu. Yalniz-ikon dugmelere DOKUNULMADI.
// =================================================================
// GOKTUNGU - SIRKET BILGILERI  [v2.4.41]
// Iki islev:
//   1) ZORUNLU ILK KURULUM SIHIRBAZI — sirket bilgileri tanimli
//      degilse sistem kilitlenir. Yonetici doldurur; doldurmadan
//      sisteme girilemez.
//   2) YONETICI PANELI — kullanici menusundeki "Sirket Bilgileri"
//      ogesinden acilir, ayni alanlari duzenler.
//
// Tasarim kararlari:
//  * Sihirbaz GIRISTEN SONRA acilir. Sebep: rol bilinmeden yonetici
//    olup olmadigi anlasilamaz; giris ekraninda gostermek yonetici
//    olmayan kullaniciya doldurulamayan bir form gostermek olurdu.
//  * Yonetici olmayan kullanici sirket tanimsizken sisteme giremez;
//    bilgilendirilir ve yoneticiye yonlendirilir (kilit kalkmaz).
//    Gerekce: antetli ucus raporu sirket kimligine dayanir, eksik
//    kimlikle ucus kaydi acmak denetim izini gecersiz kilar.
//  * Logo tarayicida <canvas> ile 512x512'ye kucultulup yalniz
//    kaydetme komutunda data URI olarak sunucuya gider. Ayarlar WS
//    mesajinda logo_url tasinir; gorsel talep uzerine HTTP'den alinir.
//  * Depolama: ayarlar tablosunda tek "sirket" anahtari (sunucu
//    `sirket_kaydet` komutu, YALNIZ yonetici).
// =================================================================

var _sirketVeri = null;         // sunucudan gelen son sirket bilgisi
var _sirketAyarGeldiMi = false; // ayarlar paketi hic geldi mi
var _sirketOturum = null;       // giris yapan kullanici
var _sirketKilit = null;        // kilit perdesi DOM
var _sirketPanel = null;        // duzenleme paneli DOM
var _sirketLogoVeri = "";       // form onizleme URL'si veya yeni data URI
var _sirketLogoDegisti = false;   // yalniz yeni dosya secildiyse sunucuya gonder

// v2.4.53 Faz 4 — MERKEZ KURUM KIMLIGI
// Merkezde (/app/) calisan ornek COK KIRACILIDIR: ayni program birden
// fazla kurumun pilotlarina hizmet eder. Yerel `sirket` ayari TEK
// kayit oldugu icin merkezde kullanilamaz; bir kurumun logosunu
// digerine gosterirdi. Bu yuzden giris yanitindaki `firma` alani
// (merkez `firmalar` tablosundan) varsa YEREL AYARIN ONUNE GECER.
// Lokal kurulumda `firma` gelmez ve eski davranis aynen surer.
var _sirketMerkez = null;       // giris yanitindaki kurum kimligi

// Merkez kurum kimligini yeni ortak ayar bicimine cevirir. Hem merkez
// hem yerel kurulum logoyu `logo_url` ile talep uzerine HTTP'den alir.
function skMerkezSirket(f) {
  if (!f) return null;
  return {
    unvan: String(f.unvan || ""),
    kisa_ad: String(f.kisa_ad || ""),
    adres: String(f.adres || ""),
    telefon: String(f.telefon || ""),
    eposta: String(f.eposta || ""),
    web: String(f.web || ""),
    vergi_no: String(f.vergi_no || ""),
    vergi_dairesi: String(f.vergi_dairesi || ""),
    logo_var: !!f.logo_url,
    logo_url: String(f.logo_url || ""),
    _merkez: true,
    firma_id: f.firma_id || null
  };
}

// kullanici.js giris yanitini buraya aktarir.
window.sirketMerkezKimlik = function (f) {
  _sirketMerkez = skMerkezSirket(f);
  if (_sirketMerkez) {
    // Merkez kimligi geldiyse ayar paketi beklenmeden karar verilir;
    // aksi halde kurum kaydi eksiksizken bile kilit ekrani gorunurdu.
    _sirketAyarGeldiMi = true;
  }
  skArayuzeUygula();
  if (_sirketOturum) window.sirketSihirbazDenetle(_sirketOturum);
};

// ---------------------------------------------------------------
function skKacis(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Disa acik okuyucu: ucus_rapor.js antet icin bunu kullanir.
// Fonksiyon olarak veriliyor (degisken degil) ki cagiran taraf her
// zaman EN SON gelen sirket bilgisini gorsun.
window.sirketBilgi = function () {
  // Merkez kurum kimligi varsa o kullanilir (cok kiracili /app/).
  return _sirketMerkez || _sirketVeri;
};

// Sirket bilgisi gecerli mi? (zorunlu alanlar dolu mu)
function skGecerli(s) {
  return !!(s && String(s.unvan || "").trim() &&
            String(s.adres || "").trim() &&
            String(s.telefon || "").trim());
}

// ---------------------------------------------------------------
// Sunucudan ayarlar geldi (harita.js -> ayarlariUygula koprusu)
// ---------------------------------------------------------------
window.sirketAyarGeldi = function (s) {
  _sirketVeri = s || null;
  _sirketAyarGeldiMi = true;
  skArayuzeUygula();
  // Ayarlar giristen once de gelebilir; oturum varsa kilidi tazele
  if (_sirketOturum) window.sirketSihirbazDenetle(_sirketOturum);
};

// Arayuzdeki unvan ve logoyu sirket bilgisine gore guncelle
function skArayuzeUygula() {
  const s = _sirketMerkez || _sirketVeri;
  // Merkez kimliginde adres/telefon bos olabilir (kurum kaydinda
  // doldurulmamis olabilir); logo ve unvan yine de gosterilmelidir.
  // Bu yuzden merkez kipinde yalnizca unvan sarti aranir.
  if (_sirketMerkez ? !String(s.unvan || "").trim() : !skGecerli(s)) return;
  const telif = document.getElementById("hkTelif");
  if (telif) {
    const yil = new Date().getFullYear();
    telif.textContent = "\u00a9 " + yil + " " + s.unvan;
  }
  if (s.logo_var && s.logo_url) {
    // Logo HTTP'den talep uzerine gelir ve 404 donebilir. Bu durumda
    // GOKTUNGU'nun kendi logosu KORUNUR; aksi halde kirik gorsel olur.
    const hkLogo = document.getElementById("sirketLogo");
    const ustLogo = document.getElementById("logo");
    function logoAta(el, url, alt) {
      if (!el) return;
      if (!el.dataset.skVarsayilanLogo) {
        el.dataset.skVarsayilanLogo = el.src || "/logo.png";
      }
      const yedek = el.dataset.skVarsayilanLogo;
      el.onerror = function () {
        el.onerror = null;
        if (yedek && el.src !== yedek) el.src = yedek;
      };
      el.src = url;
      if (alt !== undefined) el.alt = alt;
    }
    // v2.4.229: GRCON'da /app/ oneki (bkz. app_yolu.js)
    const logoUrl = (typeof window.appYolu === "function") ? window.appYolu(s.logo_url) : s.logo_url;
    logoAta(hkLogo, logoUrl, s.unvan);
    logoAta(ustLogo, logoUrl);
  }
}

// ---------------------------------------------------------------
// ZORUNLU SIHIRBAZ DENETIMI (kullanici.js -> oturumArayuzuKur)
// ---------------------------------------------------------------
window.sirketSihirbazDenetle = function (oturum) {
  _sirketOturum = oturum || null;
  if (!_sirketOturum) return;
  // MERKEZ KIPI: kurum kimligi /company/ kaydindan gelir; ilk kurulum
  // sihirbazi ANLAMSIZDIR ve gosterilmemelidir. Kurum bilgilerini
  // burada duzenlemek de yanlis olur (merkez kaydi degismez), bu yuzden
  // kilit hic kurulmaz.
  if (_sirketMerkez && String(_sirketMerkez.unvan || "").trim()) {
    window.sirketKilitKaldir();
    return;
  }
  // Ayarlar paketi henuz gelmediyse karar verilemez; geldiginde
  // sirketAyarGeldi() bu fonksiyonu yeniden cagirir.
  if (!_sirketAyarGeldiMi) return;
  if (skGecerli(_sirketVeri)) {
    window.sirketKilitKaldir();
    return;
  }
  skKilitGoster(_sirketOturum.rol === "yonetici");
};

window.sirketKilitKaldir = function () {
  if (_sirketKilit && _sirketKilit.parentNode)
    _sirketKilit.parentNode.removeChild(_sirketKilit);
  _sirketKilit = null;
};

// Cikis: kilit + duzenleme paneli kapanir, oturum sifirlanir.
// _sirketVeri KORUNUR (sunucudan gelen bilgi kullaniciya bagli degil);
// boylece yeniden giriste ayarlar paketi beklenmeden karar verilebilir.
window.sirketOturumBitti = function () {
  _sirketOturum = null;
  // Merkez kimligi KULLANICIYA baglidir: cikista temizlenmezse ayni
  // tarayicidan baska kurumun pilotu girdiginde onceki kurumun logosu
  // ve antedi kullanilmaya devam ederdi (veri sizmasi).
  _sirketMerkez = null;
  window.sirketKilitKaldir();
  window.sirketPanelKapat();
};

// ---------------------------------------------------------------
// KILIT PERDESI + SIHIRBAZ FORMU
// yonetici=false ise yalnizca bilgilendirme gosterilir.
// ---------------------------------------------------------------
function skKilitGoster(yonetici) {
  if (_sirketKilit) return;
  const t = D();
  const perde = document.createElement("div");
  perde.className = "sk-perde";
  perde.id = "sirketKilitPerde";

  const kutu = document.createElement("div");
  kutu.className = "sk-kutu";

  if (!yonetici) {
    kutu.innerHTML =
      "<div class='sk-bas'><i class='fa-solid fa-building-lock'></i>" +
      "<div><strong>" +
      skKacis(t.skKilitBaslik || "S\u0130STEM HEN\u00dcZ YAPILANDIRILMADI") +
      "</strong><span>" +
      skKacis(t.skKilitAlt ||
        "\u015eirket bilgileri tan\u0131mlanmadan sistem kullan\u0131lamaz.") +
      "</span></div></div>" +
      "<div class='sk-uyari'><i class='fa-solid fa-circle-info'></i>" +
      "<span>" + skKacis(t.skYoneticiGerek ||
        "Bu ad\u0131m\u0131 yaln\u0131zca y\u00f6netici tamamlayabilir. " +
        "L\u00fctfen sistem y\u00f6neticinize ba\u015fvurun.") +
      "</span></div>";
    const alt = document.createElement("div");
    alt.className = "sk-alt";
    const cikisBtn = document.createElement("button");
    cikisBtn.type = "button";
    cikisBtn.className = "sk-btn sk-btn-ikincil";
    cikisBtn.innerHTML = "<i class='fa-solid fa-right-from-bracket'></i> " + "<span>" + (
      (t.btnCikis || "\u00c7\u0131k\u0131\u015f Yap")) + "</span>";
    cikisBtn.addEventListener("click", () => {
      const cb = document.getElementById("btnCikis");
      if (cb) cb.click();
    });
    alt.appendChild(cikisBtn);
    kutu.appendChild(alt);
    perde.appendChild(kutu);
    document.body.appendChild(perde);
    _sirketKilit = perde;
    return;
  }

  kutu.appendChild(skFormKur({
    baslik: t.skSihirbazBaslik || "\u0130LK KURULUM \u2014 \u015e\u0130RKET B\u0130LG\u0130LER\u0130",
    altBaslik: (t.skSihirbazAlt ||
      "Bu bilgiler u\u00e7u\u015f raporlar\u0131n\u0131n antetinde kullan\u0131l\u0131r ve " +
      "sistem genelinde \u015firket kimli\u011fi olarak g\u00f6r\u00fcn\u00fcr."),
    sihirbaz: true,
    mevcut: _sirketVeri || {},
  }));
  perde.appendChild(kutu);
  document.body.appendChild(perde);
  _sirketKilit = perde;
}

// ---------------------------------------------------------------
// ORTAK FORM (sihirbaz ve duzenleme paneli ayni alanlari kullanir)
// ---------------------------------------------------------------
function skFormKur(secenek) {
  const t = D();
  const s = secenek.mevcut || {};
  const sar = document.createElement("div");
  sar.className = "sk-form-sar";

  const bas = document.createElement("div");
  bas.className = "sk-bas";
  bas.innerHTML =
    "<i class='fa-solid " +
    (secenek.sihirbaz ? "fa-wand-magic-sparkles" : "fa-building") +
    "'></i><div><strong>" + skKacis(secenek.baslik) + "</strong>" +
    (secenek.altBaslik
      ? "<span>" + skKacis(secenek.altBaslik) + "</span>" : "") +
    "</div>";
  sar.appendChild(bas);

  // ---- Logo secimi ----
  _sirketLogoVeri = s.logo_url || "";
  _sirketLogoDegisti = false;
  const logoSatir = document.createElement("div");
  logoSatir.className = "sk-logo-satir";
  const logoOn = document.createElement("div");
  logoOn.className = "sk-logo-on";
  const logoImg = document.createElement("img");
  logoImg.alt = "";
  const logoBos = document.createElement("i");
  logoBos.className = "fa-solid fa-image";
  const logoTazele = () => {
    if (_sirketLogoVeri) {
      logoImg.src = _sirketLogoVeri;
      logoImg.style.display = "";
      logoBos.style.display = "none";
    } else {
      logoImg.removeAttribute("src");
      logoImg.style.display = "none";
      logoBos.style.display = "";
    }
  };
  logoOn.appendChild(logoImg);
  logoOn.appendChild(logoBos);
  const logoSag = document.createElement("div");
  logoSag.className = "sk-logo-sag";
  const logoGiris = document.createElement("input");
  logoGiris.type = "file";
  logoGiris.accept = "image/png,image/jpeg,image/webp";
  logoGiris.style.display = "none";
  const logoBtn = document.createElement("button");
  logoBtn.type = "button";
  logoBtn.className = "sk-btn sk-btn-ikincil sk-btn-kucuk";
  logoBtn.innerHTML = "<i class='fa-solid fa-upload'></i> " + "<span>" + (
    (t.skLogoSec || "Logo Se\u00e7")) + "</span>";
  logoBtn.addEventListener("click", () => logoGiris.click());
  const logoNot = document.createElement("div");
  logoNot.className = "sk-not";
  logoNot.textContent = t.skLogoNot ||
    "PNG / JPG. Otomatik olarak 512 px'e k\u00fc\u00e7\u00fclt\u00fcl\u00fcr.";
  logoGiris.addEventListener("change", () => {
    const dosya = logoGiris.files && logoGiris.files[0];
    if (!dosya) return;
    skLogoKucult(dosya, (dataUri, hata) => {
      if (hata) {
        logoNot.className = "sk-not hata";
        logoNot.textContent = hata;
        return;
      }
      _sirketLogoVeri = dataUri;
      _sirketLogoDegisti = true;
      logoNot.className = "sk-not";
      logoNot.textContent = t.skLogoTamam || "Logo hazır.";
      logoTazele();
    });
  });
  logoSag.appendChild(logoBtn);
  logoSag.appendChild(logoNot);
  logoSag.appendChild(logoGiris);
  logoSatir.appendChild(logoOn);
  logoSatir.appendChild(logoSag);
  sar.appendChild(logoSatir);
  logoTazele();

  // ---- Metin alanlari ----
  const alanlar = [
    {ad: "unvan", etiket: t.skUnvan || "\u015eirket \u00dcnvan\u0131",
     zorunlu: true, ipucu: "\u00d6rn. T\u00fcrkbey Teknoloji Anonim \u015eirketi"},
    {ad: "adres", etiket: t.skAdres || "Adres", zorunlu: true,
     coksatir: true},
    {ad: "telefon", etiket: t.skTelefon || "Telefon", zorunlu: true,
     ipucu: "+90 ..."},
    {ad: "eposta", etiket: t.skEposta || "E-posta", zorunlu: false},
    {ad: "web", etiket: t.skWeb || "Web Sitesi", zorunlu: false},
    {ad: "vergi_no", etiket: t.skVergiNo || "Vergi / Sicil No",
     zorunlu: false},
  ];
  const girisler = {};
  const izgara = document.createElement("div");
  izgara.className = "sk-izgara";
  alanlar.forEach(a => {
    const kutu = document.createElement("label");
    kutu.className = "sk-alan" + (a.coksatir ? " genis" : "");
    const et = document.createElement("span");
    et.className = "sk-etiket";
    et.innerHTML = skKacis(a.etiket) +
      (a.zorunlu ? " <b class='sk-yildiz'>*</b>" : "");
    const g = a.coksatir
      ? document.createElement("textarea")
      : document.createElement("input");
    if (!a.coksatir) g.type = "text";
    else g.rows = 2;
    g.className = "sk-giris";
    g.value = s[a.ad] || "";
    if (a.ipucu) g.placeholder = a.ipucu;
    girisler[a.ad] = g;
    kutu.appendChild(et);
    kutu.appendChild(g);
    izgara.appendChild(kutu);
  });
  sar.appendChild(izgara);

  // ---- Hata satiri + alt bar ----
  const hataSatir = document.createElement("div");
  hataSatir.className = "sk-hata";
  hataSatir.style.display = "none";
  sar.appendChild(hataSatir);

  const alt = document.createElement("div");
  alt.className = "sk-alt";
  if (!secenek.sihirbaz) {
    const iptal = document.createElement("button");
    iptal.type = "button";
    iptal.className = "sk-btn sk-btn-ikincil";
    iptal.innerHTML = "<i class='fa-solid fa-xmark'></i> " + "<span>" + (
      (t.kkIptal || "\u0130PTAL")) + "</span>";
    iptal.addEventListener("click", () => window.sirketPanelKapat());
    alt.appendChild(iptal);
  }
  const kaydet = document.createElement("button");
  kaydet.type = "button";
  kaydet.className = "sk-btn";
  const kaydetYazi = secenek.sihirbaz
    ? (t.skTamamla || "KURULUMU TAMAMLA")
    : (t.skKaydet || "KAYDET");
  kaydet.innerHTML = "<i class='fa-solid fa-floppy-disk'></i> " + "<span>" + ( kaydetYazi) + "</span>";
  alt.appendChild(kaydet);
  sar.appendChild(alt);

  // Zorunlu alanlar dolmadan kaydet pasif
  const tazele = () => {
    const tamam = ["unvan", "adres", "telefon"]
      .every(ad => girisler[ad].value.trim().length > 0);
    kaydet.disabled = !tamam;
  };
  ["unvan", "adres", "telefon"].forEach(ad => {
    girisler[ad].addEventListener("input", tazele);
  });
  tazele();

  kaydet.addEventListener("click", () => {
    if (!(ws && ws.readyState === 1)) {
      hataSatir.style.display = "";
      hataSatir.textContent = t.skWsYok ||
        "Sunucu ba\u011flant\u0131s\u0131 yok; kaydedilemedi.";
      return;
    }
    hataSatir.style.display = "none";
    kaydet.disabled = true;
    kaydet.innerHTML = "<i class='fa-solid fa-spinner fa-spin'></i> " + "<span>" + (
      (t.skKaydediliyor || "KAYDED\u0130L\u0130YOR...")) + "</span>";
    // Mevcut logo URL'si geri gonderilmez: sunucu data URI bekler.
    // Yeni dosya secilmediyse bos deger mevcut SQLite logosunu korur.
    const kayit = {logo_veri: _sirketLogoDegisti ? _sirketLogoVeri : ""};
    Object.keys(girisler).forEach(ad => {
      kayit[ad] = girisler[ad].value.trim();
    });
    _sirketKaydetBekleyen = {kaydet, kaydetYazi, hataSatir,
                             sihirbaz: !!secenek.sihirbaz};
    ws.send(JSON.stringify({tip: "sirket_kaydet", sirket: kayit}));
  });

  return sar;
}

var _sirketKaydetBekleyen = null;

// ---------------------------------------------------------------
// Sunucu cevabi (ws.js -> sirket_sonuc)
// ---------------------------------------------------------------
window.sirketSonucIsle = function (m) {
  const B = _sirketKaydetBekleyen;
  _sirketKaydetBekleyen = null;
  const t = D();
  if (m && m.basarili) {
    // Ayarlar duyurusu sirketAyarGeldi() ile gelecek; kilit orada
    // kalkar. Panel acikse kapatilir.
    if (B && !B.sihirbaz) window.sirketPanelKapat();
    if (typeof window.uyariToastGoster === "function") {
      window.uyariToastGoster({
        baslik: t.skKayitTamamBaslik || "\u015e\u0130RKET B\u0130LG\u0130LER\u0130 KAYDED\u0130LD\u0130",
        mesaj: t.skKayitTamam ||
          "Bilgiler t\u00fcm istemcilere uyguland\u0131.",
        seviye: "bilgi", sure: 5000,
      });
    }
    return;
  }
  if (B) {
    B.kaydet.disabled = false;
    B.kaydet.innerHTML = "<i class='fa-solid fa-floppy-disk'></i> " + "<span>" + (
      B.kaydetYazi) + "</span>";
    B.hataSatir.style.display = "";
    B.hataSatir.textContent = (m && m.hata) ||
      (t.skKayitHata || "Kaydedilemedi.");
  }
};

// ---------------------------------------------------------------
// LOGO KUCULTME (canvas ile 512 px'e sigdirma, PNG data URI)
// Sunucu 512 KB data URI siniri koyuyor; kucultme bu siniri
// pratikte her zaman saglar.
// ---------------------------------------------------------------
function skLogoKucult(dosya, geriCagir) {
  const t = D();
  if (dosya.size > 8 * 1024 * 1024) {
    geriCagir(null, t.skLogoBuyuk || "Dosya çok büyük (en çok 8 MB).");
    return;
  }
  const okuyucu = new FileReader();
  okuyucu.onerror = () => geriCagir(null,
    t.skLogoOkunamadi || "Dosya okunamadı.");
  okuyucu.onload = () => {
    const img = new Image();
    img.onerror = () => geriCagir(null,
      t.skLogoGecersiz || "Geçersiz görsel dosyası.");
    img.onload = () => {
      const enBuyuk = 512;
      let g = img.naturalWidth || img.width;
      let y = img.naturalHeight || img.height;
      if (!g || !y) {
        geriCagir(null, t.skLogoGecersiz || "Geçersiz görsel dosyası.");
        return;
      }
      const olcek = Math.min(1, enBuyuk / Math.max(g, y));
      const kg = Math.max(1, Math.round(g * olcek));
      const ky = Math.max(1, Math.round(y * olcek));
      const kanvas = document.createElement("canvas");
      kanvas.width = kg; kanvas.height = ky;
      const ctx = kanvas.getContext("2d");
      // Saydamlik korunur (PNG); JPG girdide arka plan saydam kalir
      ctx.drawImage(img, 0, 0, kg, ky);
      let uri = "";
      try {
        uri = kanvas.toDataURL("image/png");
      } catch (e) {
        geriCagir(null, t.skLogoGecersiz || "Görsel işlenemedi.");
        return;
      }
      if (uri.length > 512 * 1024) {
        // PNG hala buyukse JPEG'e dus (fotografik logolar icin)
        try {
          uri = kanvas.toDataURL("image/jpeg", 0.85);
        } catch (e) { /* PNG ile devam */ }
      }
      if (uri.length > 512 * 1024) {
        geriCagir(null, t.skLogoBuyuk ||
          "Logo çok büyük; daha küçük bir görsel seçin.");
        return;
      }
      geriCagir(uri, null);
    };
    img.src = okuyucu.result;
  };
  okuyucu.readAsDataURL(dosya);
}

// ---------------------------------------------------------------
// YONETICI DUZENLEME PANELI (kullanici menusu -> Sirket Bilgileri)
// ---------------------------------------------------------------
window.sirketPanelAc = function () {
  if (_sirketPanel) return;
  const t = D();
  // MERKEZ KIPI: kurum kimligi merkez `firmalar` tablosundadir; bu
  // panelden kaydetmek YEREL ayara yazar ve hicbir etkisi olmaz
  // (bir sonraki giriste merkez degeri yine one gecer). Kullaniciyi
  // dogru yere yonlendirmek, ise yaramayan bir form gostermekten
  // iyidir.
  if (_sirketMerkez) {
    if (typeof window.uyariToastGoster === "function") {
      window.uyariToastGoster({
        baslik: t.skMerkezBaslik || "KURUM BİLGİLERİ MERKEZDE",
        mesaj: t.skMerkezAciklama ||
          "Kurum ünvanı, adresi ve logosu Müşteri Paneli → " +
          "Kurum Bilgileri ekranından güncellenir.",
        seviye: "bilgi", sure: 8000,
      });
    }
    try {
      window.open("/company/#kurum", "_blank", "noopener");
    } catch (e) {}
    return;
  }
  if (!(_sirketOturum && _sirketOturum.rol === "yonetici")) {
    if (typeof window.uyariToastGoster === "function") {
      window.uyariToastGoster({
        baslik: t.skYetkiBaslik || "YETK\u0130 YOK",
        mesaj: t.skYoneticiGerek ||
          "Bu i\u015flemi yaln\u0131zca y\u00f6netici yapabilir.",
        seviye: "uyari", sure: 6000,
      });
    }
    return;
  }
  const perde = document.createElement("div");
  perde.className = "sk-perde";
  perde.id = "sirketPanelPerde";
  const kutu = document.createElement("div");
  kutu.className = "sk-kutu";
  kutu.appendChild(skFormKur({
    baslik: t.skPanelBaslik || "\u015e\u0130RKET B\u0130LG\u0130LER\u0130",
    altBaslik: t.skPanelAlt ||
      "U\u00e7u\u015f raporu antetinde ve sistem genelinde kullan\u0131l\u0131r.",
    sihirbaz: false,
    mevcut: _sirketVeri || {},
  }));
  perde.appendChild(kutu);
  // Perdeye tiklayinca kapat (kutunun icine tiklama sayilmaz)
  perde.addEventListener("click", (ev) => {
    if (ev.target === perde) window.sirketPanelKapat();
  });
  document.body.appendChild(perde);
  _sirketPanel = perde;
};

window.sirketPanelKapat = function () {
  if (_sirketPanel && _sirketPanel.parentNode)
    _sirketPanel.parentNode.removeChild(_sirketPanel);
  _sirketPanel = null;
};

// Kullanici menusu ogesi
(function () {
  const oge = document.getElementById("pmSirketBilgi");
  if (!oge) return;
  oge.addEventListener("click", () => {
    const menu = document.getElementById("profilMenu");
    if (menu) menu.classList.add("popup-gizli");
    window.sirketPanelAc();
  });
})();

// Disari acilan yardimcilar
window.sirketGecerliMi = function () { return skGecerli(_sirketVeri); };
