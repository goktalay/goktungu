// =================================================================
// GOKTUNGU - JOYSTICK AYARLARI (PILOT BAZLI)  [v2.4.50]
// -----------------------------------------------------------------
// Kullanici istegi:
//   "sanirim dronu kontrol eden joystikler ters, bazi pilotlar farkli
//    kullanabiliyor, bunu lutfen pilot ayarlarina koyalim, birde su an
//    durduk yere joystick ortadayken bile dron kendi etrafinda donuyor"
//
// TASARIM KARARLARI (neden boyle):
//
// 1) PILOT MENUSUNDE, PROGRAM AYARLARINDA DEGIL
//    Bu ayar KISISELDIR. Ayni yer istasyonunu birden fazla pilot
//    kullanir; biri "Mode 1", digeri "Mode 2" yerlesimine alisiktir.
//    Program Ayarlari makine geneli ayarlar icindir ve yalniz
//    yonetici yazabilir — oysa her pilot kendi cubugunun ters olup
//    olmadigina kendisi karar vermelidir. Bu yuzden rol sarti YOK.
//
// 2) OLU BOLGE ARAYUZDE DEGIL SUNUCUDA UYGULANIR
//    v2.4.49'a kadar tarayici kendi sabit olu bolgesini (0.12)
//    uyguluyor ve sunucuya ISLENMIS deger gonderiyordu. Bu iki sorun
//    dogurur: (a) pilot tercihi arayuz ile sunucu arasinda ayrisir,
//    (b) merkez kalibrasyonu IMKANSIZ hale gelir cunku kayma zaten
//    maskelenmis gelir. Artik arayuz HAM deger yollar.
//
// 3) CANLI CUBUK GOSTERGESI ZORUNLU
//    Pilot "ters mi degil mi" sorusunu ancak cubugu oynatip sonucu
//    GORUREK yanitlar. Bu yuzden panel canli bir cubuk gostergesi
//    icerir ve ters cevirme aninda uygulanir. Yalniz onay kutusu
//    gostermek, pilotu deneme-yanilma icin ucusa zorlamak olurdu.
//
// 4) KALIBRASYON, OLU BOLGENIN YERINE DEGIL YANINDA
//    Olculdu: 0.13 kaymis bir cubukta olu bolge (0.12) sonrasi hala
//    0.011 kalir ve dron YAVAS DA OLSA doner. Merkez kalibrasyonu
//    kaymayi kaynagindan giderir (tam 0.000). Ikisi birlikte gerekir:
//    kalibrasyon sonrasi sicaklik/yaslanma kaynakli yeni kayma da
//    olu bolge tarafindan yutulur.
// =================================================================
let jaTercih = null;        // sunucudan gelen son tercih
let jaVarsayilan = null;    // sunucunun bildirdigi varsayilan
let jaPanel = null;         // panel DOM (perde)
let jaHamZaman = null;      // canli ham okuma zamanlayicisi
let jaSonHam = { gamepad: {}, pygame: {} };
let jaKaynak = "gamepad";   // panelde secili kaynak

const JA_EKSEN = ["vx", "vy", "vz", "yaw"];

function jaT() { return (typeof D === "function") ? D() : {}; }

function jaGonder(nesne) {
  if (typeof ws !== "undefined" && ws && ws.readyState === 1) {
    ws.send(JSON.stringify(nesne));
    return true;
  }
  return false;
}

function jaToast(mesaj, seviye, baslik) {
  if (typeof window.uyariToastGoster === "function") {
    window.uyariToastGoster({
      baslik: baslik || "", mesaj: mesaj,
      seviye: seviye || "bilgi", sure: 5000, kategori: "joystick",
    });
  }
}

function jaKacis(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Eksen etiketleri: teknik ad yerine PILOTUN gordugu hareket yazilir.
// "vx" pilota hicbir sey anlatmaz; "Ileri / Geri" anlatir.
function jaEksenEtiket(e) {
  const t = jaT();
  switch (e) {
    case "vx": return t.jaEksenIleri || "İleri / Geri";
    case "vy": return t.jaEksenYanal || "Sağa / Sola (yanal)";
    case "vz": return t.jaEksenIrtifa || "Yukarı / Aşağı (irtifa)";
    case "yaw": return t.jaEksenYaw || "Dönüş (yaw)";
    default: return e;
  }
}

// -----------------------------------------------------------------
// Sunucu mesajlari
// -----------------------------------------------------------------
window.jaTercihGeldi = function (m) {
  if (!m || m.basarili === false) {
    if (m && m.hata) jaToast(m.hata, "uyari");
    return;
  }
  jaTercih = m.tercih || null;
  if (m.varsayilan) jaVarsayilan = m.varsayilan;
  if (jaPanel) jaPanelTazele(m);
};

window.jaTercihSonuc = function (m) {
  if (!m) return;
  if (m.basarili === false) {
    jaToast(m.hata || (jaT().jaKaydedilemedi || "Ayar kaydedilemedi."),
            "hata");
    return;
  }
  jaTercih = m.tercih || jaTercih;
  jaToast(jaT().jaKaydedildi || "Joystick ayarları kaydedildi.",
          "basari");
};

window.jaKalibreSonuc = function (m) {
  if (!m) return;
  if (m.basarili === false) {
    jaToast(m.hata || (jaT().jaKalibreHata || "Kalibrasyon yapılamadı."),
            "uyari");
    return;
  }
  jaTercih = m.tercih || jaTercih;
  jaToast(m.silindi
    ? (jaT().jaKalibreSilindi || "Kalibrasyon sıfırlandı.")
    : (jaT().jaKalibreTamam || "Çubuk merkezi kaydedildi."),
    "basari");
  if (jaPanel) jaPanelTazele();
};

window.jaHamGeldi = function (m) {
  if (!m) return;
  jaSonHam = { gamepad: m.gamepad || {}, pygame: m.pygame || {} };
  jaCubukTazele();
};

// -----------------------------------------------------------------
// Canli cubuk gostergesi
// -----------------------------------------------------------------
function jaCubukTazele() {
  if (!jaPanel) return;
  // Tarayici joystick'i varsa DOGRUDAN oku (WS gecikmesi olmadan);
  // yoksa sunucudan gelen degeri kullan (pygame/canta yolu).
  let ham = null;
  if (jaKaynak === "gamepad") {
    ham = jaTarayiciHamOku();
    if (!ham) ham = jaSonHam.gamepad || {};
  } else {
    ham = jaSonHam.pygame || {};
  }
  JA_EKSEN.forEach((e) => {
    const cizgi = jaPanel.querySelector('[data-ja-bar="' + e + '"]');
    const deger = jaPanel.querySelector('[data-ja-deger="' + e + '"]');
    const islenmis = jaPanel.querySelector('[data-ja-islenmis="' + e + '"]');
    const h = Number(ham[e] || 0);
    if (cizgi) {
      // -1..1 -> %0..100 (merkez %50)
      const yuzde = Math.max(0, Math.min(100, (h + 1) * 50));
      cizgi.style.left = yuzde + "%";
    }
    if (deger) deger.textContent = h.toFixed(3);
    if (islenmis) {
      const s = jaIsleYerel(e, h);
      islenmis.textContent = s.toFixed(3);
      // Notr degilken vurgula: pilot kaymayi GORSUN
      islenmis.classList.toggle("ja-uyari", Math.abs(s) > 0.001);
    }
  });
}

// Tarayici joystick'inin HAM eksenlerini okur (panel gostergesi icin).
// dronlar.js ayni okumayi yapar; burada bagimsiz okumak paneli
// manuel kontrol anahtarina BAGIMLI olmaktan kurtarir (pilot ayari
// dron ucurmadan da sinayabilmeli).
function jaTarayiciHamOku() {
  if (!navigator.getGamepads) return null;
  const gps = navigator.getGamepads() || [];
  let gp = null;
  for (let i = 0; i < gps.length; i++) {
    if (gps[i] && gps[i].connected) { gp = gps[i]; break; }
  }
  if (!gp) return null;
  const n = gp.axes.length;
  return {
    vy: n > 0 ? gp.axes[0] : 0,
    vx: n > 1 ? -gp.axes[1] : 0,
    yaw: n > 2 ? gp.axes[2] : 0,
    vz: n > 3 ? -gp.axes[3] : 0,
  };
}

// Panelde gosterilen "islenmis" deger: sunucudaki `joystick_ayar.isle`
// ile AYNI matematigi uygular. Iki yerde ayni mantik olmasi tercih
// edilmedi ama kacinilamaz: pilot ayari degistirirken sonucu ANINDA
// gormeli, WS tur suresi beklemek geri bildirimi kullanissiz kilar.
// Sunucu tek DOGRULUK kaynagi olarak kalir; bu yalniz gostergedir.
function jaIsleYerel(eksen, ham) {
  const t = jaFormOku();
  const kaynakOnek = jaKaynak + "_" + eksen;
  const merkez = (t.merkez && (kaynakOnek in t.merkez))
    ? Number(t.merkez[kaynakOnek]) : 0;
  let v = Number(ham || 0) - merkez;
  const bolen = (v >= 0) ? Math.max(1e-6, 1 - merkez)
                         : Math.max(1e-6, 1 + merkez);
  v = Math.max(-1, Math.min(1, v / bolen));
  const olu = Math.max(0, Math.min(0.9, Number(t.olu[eksen] || 0)));
  const a = Math.abs(v);
  let n = 0;
  if (a > olu) {
    const kalan = 1 - olu;
    n = kalan <= 1e-9 ? 0 : (a - olu) / kalan;
    const egri = Number(t.egri || 1);
    if (egri > 1) n = Math.pow(n, egri);
    n = Math.max(0, Math.min(1, n));
  }
  let s = v > 0 ? n : -n;
  if (t.ters[eksen]) s = -s;
  s *= Number(t.olcek[eksen] || 1);
  return Math.max(-1, Math.min(1, s));
}

// -----------------------------------------------------------------
// Panel
// -----------------------------------------------------------------
function jaFormOku() {
  // Formdaki guncel degerleri tercih bicimine cevirir
  const t = {
    ters: {}, olu: {}, olcek: {}, egri: 1,
    merkez: (jaTercih && jaTercih.merkez) ? jaTercih.merkez : {},
  };
  JA_EKSEN.forEach((e) => {
    const kutu = jaPanel
      ? jaPanel.querySelector('[data-ja-ters="' + e + '"]') : null;
    const olu = jaPanel
      ? jaPanel.querySelector('[data-ja-olu="' + e + '"]') : null;
    const olcek = jaPanel
      ? jaPanel.querySelector('[data-ja-olcek="' + e + '"]') : null;
    t.ters[e] = kutu ? !!kutu.checked
      : !!(jaTercih && jaTercih.ters && jaTercih.ters[e]);
    t.olu[e] = olu ? Number(olu.value) / 100
      : ((jaTercih && jaTercih.olu && jaTercih.olu[e]) || 0.08);
    t.olcek[e] = olcek ? Number(olcek.value) / 100
      : ((jaTercih && jaTercih.olcek && jaTercih.olcek[e]) || 1);
  });
  const egri = jaPanel ? jaPanel.querySelector("[data-ja-egri]") : null;
  t.egri = egri ? Number(egri.value) / 100
    : ((jaTercih && jaTercih.egri) || 1);
  return t;
}

function jaSatir(e, tercih) {
  const ters = !!(tercih.ters && tercih.ters[e]);
  const olu = Math.round(((tercih.olu && tercih.olu[e]) || 0.08) * 100);
  const olcek = Math.round(((tercih.olcek && tercih.olcek[e]) || 1) * 100);
  const t = jaT();
  return '' +
    '<div class="ja-satir">' +
      '<div class="ja-satir-bas">' +
        '<strong>' + jaKacis(jaEksenEtiket(e)) + '</strong>' +
        '<label class="ja-ters">' +
          '<input type="checkbox" data-ja-ters="' + e + '"' +
            (ters ? " checked" : "") + '>' +
          '<span>' + jaKacis(t.jaTers || "Ters çevir") + '</span>' +
        '</label>' +
      '</div>' +
      '<div class="ja-cubuk">' +
        '<div class="ja-cubuk-orta"></div>' +
        '<div class="ja-cubuk-nokta" data-ja-bar="' + e + '"></div>' +
      '</div>' +
      '<div class="ja-olcum">' +
        '<span>' + jaKacis(t.jaHam || "Ham") + ': ' +
          '<b data-ja-deger="' + e + '">0.000</b></span>' +
        '<span>' + jaKacis(t.jaIslenmis || "İşlenmiş") + ': ' +
          '<b data-ja-islenmis="' + e + '">0.000</b></span>' +
      '</div>' +
      '<div class="ja-kaydir">' +
        '<label>' + jaKacis(t.jaOlu || "Ölü bölge") + '</label>' +
        '<input type="range" min="0" max="40" value="' + olu +
          '" data-ja-olu="' + e + '">' +
        '<span data-ja-olu-yaz="' + e + '">' + olu + '%</span>' +
      '</div>' +
      '<div class="ja-kaydir">' +
        '<label>' + jaKacis(t.jaOlcek || "Hassasiyet") + '</label>' +
        '<input type="range" min="10" max="100" value="' + olcek +
          '" data-ja-olcek="' + e + '">' +
        '<span data-ja-olcek-yaz="' + e + '">' + olcek + '%</span>' +
      '</div>' +
    '</div>';
}

window.joystickPanelAc = function () {
  if (jaPanel) return;
  const t = jaT();
  const tercih = jaTercih || {
    ters: {}, olu: { vx: .08, vy: .08, vz: .08, yaw: .12 },
    olcek: { vx: 1, vy: 1, vz: 1, yaw: 1 }, egri: 1, merkez: {},
  };
  const egri = Math.round((tercih.egri || 1) * 100);
  const perde = document.createElement("div");
  perde.className = "sk-perde";
  perde.id = "joystickPanelPerde";
  const kutu = document.createElement("div");
  kutu.className = "sk-kutu ja-kutu";
  kutu.innerHTML = '' +
    '<div class="sk-bas">' +
      '<i class="fa-solid fa-gamepad"></i>' +
      '<div>' +
        '<strong>' + jaKacis(t.jaBaslik || "JOYSTICK AYARLARI") +
          '</strong>' +
        '<span>' + jaKacis(t.jaAciklama ||
          "Bu ayarlar yalnızca sizin hesabınız için geçerlidir. " +
          "Çubuğu oynatarak yönü doğrulayın.") + '</span>' +
      '</div>' +
    '</div>' +
    '<div class="ja-kaynak">' +
      '<label>' + jaKacis(t.jaKaynak || "Kaynak") + '</label>' +
      '<select data-ja-kaynak>' +
        '<option value="gamepad">' +
          jaKacis(t.jaKaynakTarayici || "Tarayıcıya takılı joystick") +
        '</option>' +
        '<option value="pygame">' +
          jaKacis(t.jaKaynakSunucu || "Sunucuya takılı joystick") +
        '</option>' +
      '</select>' +
      '<span class="ja-durum" data-ja-durum></span>' +
    '</div>' +
    '<div class="ja-uyari-kutu" data-ja-kayma style="display:none;">' +
      '<i class="fa-solid fa-triangle-exclamation"></i>' +
      '<span>' + jaKacis(t.jaKaymaUyari ||
        "Çubuk ortadayken sıfır olmayan değer okunuyor. " +
        "Çubuğu bırakıp \"Merkezi kaydet\" düğmesine basın.") +
      '</span>' +
    '</div>' +
    '<div class="ja-satirlar">' +
      JA_EKSEN.map((e) => jaSatir(e, tercih)).join("") +
    '</div>' +
    '<div class="ja-kaydir ja-egri">' +
      '<label>' + jaKacis(t.jaEgri || "Merkez yumuşatma") + '</label>' +
      '<input type="range" min="100" max="300" value="' + egri +
        '" data-ja-egri>' +
      '<span data-ja-egri-yaz>' + egri + '%</span>' +
    '</div>' +
    '<div class="ja-dugmeler">' +
      '<button class="sk-btn sk-btn-kucuk ja-kalibre" data-ja-kalibre>' +
        '<i class="fa-solid fa-crosshairs"></i><span>' +
        jaKacis(t.jaMerkeziKaydet || "Merkezi kaydet") +
      '</span></button>' +
      '<button class="sk-btn sk-btn-ikincil sk-btn-kucuk ja-sil" data-ja-kalibre-sil>' +
        '<i class="fa-solid fa-eraser"></i><span>' +
        jaKacis(t.jaKalibreSil || "Kalibrasyonu sıfırla") +
      '</span></button>' +
      '<button class="sk-btn sk-btn-ikincil sk-btn-kucuk ja-varsayilan" data-ja-varsayilan>' +
        '<i class="fa-solid fa-rotate-left"></i><span>' +
        jaKacis(t.jaVarsayilan || "Varsayılana dön") +
      '</span></button>' +
      '<div class="ja-bosluk"></div>' +
      '<button class="sk-btn sk-btn-ikincil ja-iptal" data-ja-kapat>' +
        jaKacis(t.jaKapat || "Kapat") +
      '</button>' +
      '<button class="sk-btn" data-ja-kaydet>' +
        '<i class="fa-solid fa-floppy-disk"></i><span>' +
        jaKacis(t.jaKaydet || "Kaydet") +
      '</span></button>' +
    '</div>';
  perde.appendChild(kutu);
  perde.addEventListener("click", (ev) => {
    if (ev.target === perde) window.joystickPanelKapat();
  });
  document.body.appendChild(perde);
  jaPanel = perde;
  jaOlaylariBagla();
  // Sunucudan guncel tercihi ve canli ham degeri iste
  jaGonder({ tip: "joystick_tercih" });
  jaHamZaman = setInterval(() => {
    // Sunucu tarafli joystick icin periyodik ham okuma; tarayici
    // joystick'i yerel okunur (gecikmesiz).
    if (jaKaynak === "pygame") jaGonder({ tip: "joystick_ham" });
    jaCubukTazele();
    jaKaymaDenetle();
  }, 100);
};

window.joystickPanelKapat = function () {
  if (jaHamZaman) { clearInterval(jaHamZaman); jaHamZaman = null; }
  if (jaPanel && jaPanel.parentNode)
    jaPanel.parentNode.removeChild(jaPanel);
  jaPanel = null;
};

// Cubuk ortadayken islenmis deger sifir degilse pilotu UYAR.
// Bu, kullanicinin bildirdigi "durduk yere donuyor" belirtisinin
// arayuzdeki karsiligidir: kayma gorunur hale getirilir.
function jaKaymaDenetle() {
  if (!jaPanel) return;
  const kutu = jaPanel.querySelector("[data-ja-kayma]");
  if (!kutu) return;
  let kayma = false;
  JA_EKSEN.forEach((e) => {
    const oge = jaPanel.querySelector('[data-ja-islenmis="' + e + '"]');
    if (oge && Math.abs(Number(oge.textContent || 0)) > 0.001)
      kayma = true;
  });
  kutu.style.display = kayma ? "flex" : "none";
}

function jaPanelTazele(m) {
  if (!jaPanel || !jaTercih) return;
  JA_EKSEN.forEach((e) => {
    const kutu = jaPanel.querySelector('[data-ja-ters="' + e + '"]');
    if (kutu) kutu.checked = !!(jaTercih.ters && jaTercih.ters[e]);
    const olu = jaPanel.querySelector('[data-ja-olu="' + e + '"]');
    if (olu) {
      olu.value = Math.round(((jaTercih.olu && jaTercih.olu[e]) || 0.08) * 100);
      const yaz = jaPanel.querySelector('[data-ja-olu-yaz="' + e + '"]');
      if (yaz) yaz.textContent = olu.value + "%";
    }
    const olcek = jaPanel.querySelector('[data-ja-olcek="' + e + '"]');
    if (olcek) {
      olcek.value = Math.round(
        ((jaTercih.olcek && jaTercih.olcek[e]) || 1) * 100);
      const yaz = jaPanel.querySelector('[data-ja-olcek-yaz="' + e + '"]');
      if (yaz) yaz.textContent = olcek.value + "%";
    }
  });
  const egri = jaPanel.querySelector("[data-ja-egri]");
  if (egri) {
    egri.value = Math.round((jaTercih.egri || 1) * 100);
    const yaz = jaPanel.querySelector("[data-ja-egri-yaz]");
    if (yaz) yaz.textContent = egri.value + "%";
  }
  if (m) {
    const durum = jaPanel.querySelector("[data-ja-durum]");
    if (durum) {
      const t = jaT();
      if (jaKaynak === "pygame") {
        durum.textContent = m.joystick
          ? (m.joystick_adi || (t.jaBagli || "bağlı"))
          : (t.jaBagliDegil || "bağlı değil");
        durum.classList.toggle("ja-yok", !m.joystick);
      }
    }
  }
}

function jaOlaylariBagla() {
  if (!jaPanel) return;
  const sec = jaPanel.querySelector("[data-ja-kaynak]");
  if (sec) {
    sec.value = jaKaynak;
    sec.addEventListener("change", () => {
      jaKaynak = sec.value === "pygame" ? "pygame" : "gamepad";
      jaGonder({ tip: "joystick_tercih" });
    });
  }
  // Kaydiriciler: deger etiketini canli guncelle
  JA_EKSEN.forEach((e) => {
    const olu = jaPanel.querySelector('[data-ja-olu="' + e + '"]');
    if (olu) olu.addEventListener("input", () => {
      const yaz = jaPanel.querySelector('[data-ja-olu-yaz="' + e + '"]');
      if (yaz) yaz.textContent = olu.value + "%";
    });
    const olcek = jaPanel.querySelector('[data-ja-olcek="' + e + '"]');
    if (olcek) olcek.addEventListener("input", () => {
      const yaz = jaPanel.querySelector('[data-ja-olcek-yaz="' + e + '"]');
      if (yaz) yaz.textContent = olcek.value + "%";
    });
  });
  const egri = jaPanel.querySelector("[data-ja-egri]");
  if (egri) egri.addEventListener("input", () => {
    const yaz = jaPanel.querySelector("[data-ja-egri-yaz]");
    if (yaz) yaz.textContent = egri.value + "%";
  });
  const kapat = jaPanel.querySelector("[data-ja-kapat]");
  if (kapat) kapat.addEventListener("click", window.joystickPanelKapat);
  const kaydet = jaPanel.querySelector("[data-ja-kaydet]");
  if (kaydet) kaydet.addEventListener("click", () => {
    const t = jaFormOku();
    jaGonder({ tip: "joystick_tercih_yaz", tercih: t });
  });
  const kalibre = jaPanel.querySelector("[data-ja-kalibre]");
  if (kalibre) kalibre.addEventListener("click", () => {
    // Tarayici joystick'i icin ham deger BURADAN gonderilir; sunucu
    // yalniz manuel kontrol anahtari acikken ham deger gorur, oysa
    // pilot ayari ucus yapmadan da kalibre edebilmelidir.
    const ham = (jaKaynak === "gamepad") ? jaTarayiciHamOku() : null;
    jaGonder({ tip: "joystick_kalibre", kaynak: jaKaynak,
               ham: ham || undefined });
  });
  const sil = jaPanel.querySelector("[data-ja-kalibre-sil]");
  if (sil) sil.addEventListener("click", () => {
    jaGonder({ tip: "joystick_kalibre", kaynak: jaKaynak, sil: true });
  });
  const vars = jaPanel.querySelector("[data-ja-varsayilan]");
  if (vars) vars.addEventListener("click", () => {
    const v = jaVarsayilan || {
      ters: { vx: false, vy: false, vz: false, yaw: false },
      olu: { vx: .08, vy: .08, vz: .08, yaw: .12 },
      olcek: { vx: 1, vy: 1, vz: 1, yaw: 1 }, egri: 1,
    };
    // Merkez kalibrasyonu KORUNUR: varsayilana donmek, olculmus
    // donanim merkezini atmak anlamina gelmemeli.
    const yeni = JSON.parse(JSON.stringify(v));
    yeni.merkez = (jaTercih && jaTercih.merkez) ? jaTercih.merkez : {};
    jaTercih = yeni;
    jaPanelTazele();
  });
}

// Kullanici menusu ogesi
(function () {
  const oge = document.getElementById("pmJoystick");
  if (!oge) return;
  oge.addEventListener("click", () => {
    const menu = document.getElementById("profilMenu");
    if (menu) menu.classList.add("popup-gizli");
    window.joystickPanelAc();
  });
})();

/* FAZ18-IS2B-IKON-METIN-SPAN */
