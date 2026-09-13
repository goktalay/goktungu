// =====================================================================
// PILOT_HAKKINDA.JS - PILOT HAKKINDA POPUP'I (v2.1.7)
// ---------------------------------------------------------------------
// - Profil menusundeki "Pilot Hakkında" ile acilir (kendi profili).
// - Yonetici, Kullanici Yonetimi listesinde bir kullaniciya tiklayarak
//   o kullanicinin profilini acabilir (+ rol degistirme yetkisi).
// - Sol: modul listesi | Sag: secili modulun detayi.
//   Moduller: Pilot Bilgileri, Program Gecmisi, Ucuslar, Uyarilar
//   (yeni moduller PH_MODULLER listesine eklenerek genisletilir).
// - Ucuslar listesinde CIFT TIK -> ucus onizleme (mini harita + oynatici,
//   gecmis.js'teki dron history oynaticisini kullanir: dronGecmisAc yerine
//   kendi mini onizleme popup'i acar).
// =====================================================================
"use strict";

let _phPopup = null;        // acik popup DOM'u
let _phHedef = null;        // goruntulenen kullanici {eposta, ad_soyad, ...}
let _phModul = "bilgiler";  // secili modul id'si
let _phLoglar = [];         // program gecmisi kayitlari
let _phUcusDronlar = [];    // dron gecmisi listesi (ucuslar modulu)
let _phUyarilar = [];       // uyari listesi
let _phOnizleme = null;     // {popup, viewer, oynatici, ucus}

// Modul tanimlari: yeni modul eklemek icin buraya kayit ekleyin.
const PH_MODULLER = [
  { id: "bilgiler", ikon: "fa-id-card",       i18n: "phModBilgiler" },
  { id: "gecmis",   ikon: "fa-clock-rotate-left", i18n: "phModGecmis" },
  { id: "ucuslar",  ikon: "fa-plane-up",      i18n: "phModUcuslar" },
  { id: "uyarilar", ikon: "fa-bell",          i18n: "phModUyarilar" },
];

// ---------------------------------------------------------------
// Acilis / kapanis
// ---------------------------------------------------------------
// eposta verilmezse oturum sahibinin profili acilir. Yonetici baska
// bir kullanicinin epostasi ile cagirabilir.
function pilotHakkindaAc(eposta) {
  if (!oturum) return;
  pilotHakkindaKapat();
  const kendi = !eposta || eposta === oturum.eposta;
  _phHedef = kendi ? Object.assign({}, oturum) : { eposta: eposta };
  _phModul = "bilgiler";
  _phLoglar = []; _phUcusDronlar = []; _phUyarilar = [];

  const t = D();
  const pop = document.createElement("div");
  pop.className = "ph-popup";
  _phPopup = pop;

  const bas = document.createElement("div");
  bas.className = "popup-baslik ph-baslik";
  bas.innerHTML =
    "<span><i class='fa-solid fa-id-card'></i> " +
    (t.phBaslik || "PİLOT HAKKINDA") +
    " <span class='ph-baslik-ad' id='phBaslikAd'></span></span>" +
    "<button class='popup-kapat' id='phKapat'><i class='fa-solid fa-xmark'></i></button>";
  pop.appendChild(bas);

  const govde = document.createElement("div");
  govde.className = "ph-govde";
  // Sol modul listesi
  const sol = document.createElement("div");
  sol.className = "ph-sol";
  sol.id = "phModulListe";
  // Sag detay
  const sag = document.createElement("div");
  sag.className = "ph-sag";
  sag.id = "phDetay";
  govde.appendChild(sol);
  govde.appendChild(sag);
  pop.appendChild(govde);

  document.body.appendChild(pop);
  // Ortala + tasima/resize (ortak modul)
  pop.style.left = Math.max(10, (window.innerWidth - pop.offsetWidth) / 2) + "px";
  pop.style.top = Math.max(10, (window.innerHeight - pop.offsetHeight) / 2) + "px";
  if (window.popupTasinabilirYap) popupTasinabilirYap(pop, bas, "pp_pilotHakkinda");
  if (window.popupBoyutlandirilabilirYap)
    popupBoyutlandirilabilirYap(pop, "pp_pilotHakkinda", { minW: 640, minH: 400 });

  document.getElementById("phKapat").addEventListener("click", pilotHakkindaKapat);

  phModulListeCiz();
  phModulAc("bilgiler");

  // Yonetici baska kullanici acti: guncel kullanici bilgisi liste
  // uzerinden gelir (kullanici_liste yenile)
  if (!kendi && ws && ws.readyState === 1) {
    ws.send(JSON.stringify({ tip: "kullanici_liste" }));
  }
}

function pilotHakkindaKapat() {
  phOnizlemeKapat();
  if (_phPopup) { _phPopup.remove(); _phPopup = null; }
  _phHedef = null;
}

// Kullanici listesi geldiginde hedefin bilgilerini tazele (yonetici akisi)
window.pilotHakkindaKullaniciTazele = function (liste) {
  if (!_phPopup || !_phHedef) return;
  const k = (liste || []).find(x => x.eposta === _phHedef.eposta);
  if (k) {
    Object.assign(_phHedef, k);
    phBaslikTazele();
    if (_phModul === "bilgiler") phBilgilerCiz();
  }
};

function phBaslikTazele() {
  const el = document.getElementById("phBaslikAd");
  if (el) el.textContent = "— " + (_phHedef.ad_soyad || _phHedef.eposta || "");
}

// ---------------------------------------------------------------
// Sol modul listesi
// ---------------------------------------------------------------
function phModulListeCiz() {
  const t = D();
  const kutu = document.getElementById("phModulListe");
  if (!kutu) return;
  kutu.innerHTML = "";
  for (const m of PH_MODULLER) {
    const el = document.createElement("div");
    el.className = "ph-modul" + (m.id === _phModul ? " secili" : "");
    el.dataset.modul = m.id;
    el.innerHTML = "<i class='fa-solid " + m.ikon + "'></i><span>" +
      (t[m.i18n] || m.id) + "</span>";
    el.addEventListener("click", () => phModulAc(m.id));
    kutu.appendChild(el);
  }
}

function phModulAc(id) {
  _phModul = id;
  phModulListeCiz();
  phBaslikTazele();
  const detay = document.getElementById("phDetay");
  if (!detay) return;
  detay.innerHTML = "";
  if (id === "bilgiler") phBilgilerCiz();
  else if (id === "gecmis") phGecmisAc();
  else if (id === "ucuslar") phUcuslarAc();
  else if (id === "uyarilar") phUyarilarAc();
}

// ---------------------------------------------------------------
// MODUL: Pilot Bilgileri (duzenlenebilir form)
// ---------------------------------------------------------------
function phBilgilerCiz() {
  const t = D();
  const detay = document.getElementById("phDetay");
  if (!detay) return;
  const k = _phHedef || {};
  const kendi = oturum && k.eposta === oturum.eposta;
  const yonetici = oturum && oturum.rol === "yonetici";
  // v2.4.65 TEK KAPI: Rol degistirme bu pencereden KALDIRILDI.
  // Rol atamasi kurumsal panelde (/company/) yapilir; sunucu da
  // kullanici_guncelle icindeki rol alanini reddeder. Combobox
  // mevcut rolu GOSTERIR ama daima salt okunurdur.
  const rolDegistirebilir = false;

  // Fotograf degistirme: kendi profili veya yonetici
  const fotoDegistirebilir = kendi || yonetici;
  detay.innerHTML =
    "<div class='ph-form'>" +
      "<div class='ph-avatar-satir'>" +
        "<img id='phAvatarImg' alt=''>" +
        "<div><div class='ph-form-ad'>" + (k.ad_soyad || "") + "</div>" +
        "<div class='ph-form-eposta'>" + (k.eposta || "") + "</div></div>" +
        (fotoDegistirebilir ?
          "<div class='ph-foto-btnler'>" +
            "<button id='phFotoYukle' title='" +
              phKacir(t.phFotoYukle || "Fotoğraf Yükle") + "'>" +
              "<i class='fa-solid fa-camera'></i><span>" +
              (t.phFotoYukle || "Fotoğraf Yükle") + "</span></button>" +
            (k.avatar ?
              "<button id='phFotoKaldir' title='" +
                phKacir(t.phFotoKaldir || "Fotoğrafı Kaldır") + "'>" +
                "<i class='fa-solid fa-trash'></i></button>" : "") +
            "<input type='file' id='phFotoInput' accept='image/*'" +
            " style='display:none'>" +
          "</div>" : "") +
      "</div>" +
      "<label>" + (t.phAdSoyad || "İsim Soyisim") + "</label>" +
      "<input type='text' id='phAd' value='" + phKacir(k.ad_soyad || "") + "'>" +
      "<label>" + (t.phUnvan || "Ünvan") + "</label>" +
      "<input type='text' id='phUnvan' value='" + phKacir(k.unvan || "") + "'>" +
      "<label>" + (t.phRol || "Rol") + "</label>" +
      "<select id='phRol'" + (rolDegistirebilir ? "" : " disabled") + ">" +
        phRolSecenekleri(k.rol, t) +
      "</select>" +
      "<div class='ph-not'>" +
        (t.phRolTekKapiNot ||
         "Rol ataması kurumsal panelden yapılır.") + "</div>" +
      "<label>" + (t.phYeniSifre || "Yeni Şifre (boş bırakılırsa değişmez)") + "</label>" +
      "<input type='password' id='phSifre' value='' autocomplete='new-password'>" +
      "<div class='ph-form-alt'>" +
        "<button id='phKaydet' class='onay-btn'><i class='fa-solid fa-check'></i><span>" +
          (t.btnKaydet || "Kaydet") + "</span></button>" +
        "<span id='phFormMesaj'></span>" +
      "</div>" +
    "</div>";

  // Avatar goster (resim yoksa ikon)
  if (typeof window.avatarUygula === "function")
    window.avatarUygula(document.getElementById("phAvatarImg"),
                        k.avatar || "");

  // Fotograf yukleme akisi: dosya sec -> canvas ile 256px'e kucult ->
  // data URL -> WS avatar_yukle komutu
  if (fotoDegistirebilir) {
    const fotoBtn = document.getElementById("phFotoYukle");
    const fotoInput = document.getElementById("phFotoInput");
    const fotoKaldir = document.getElementById("phFotoKaldir");
    if (fotoBtn && fotoInput) {
      fotoBtn.addEventListener("click", () => fotoInput.click());
      fotoInput.addEventListener("change", () => {
        const dosya = fotoInput.files && fotoInput.files[0];
        if (!dosya) return;
        phFotoOlcekleGonder(dosya, k.eposta);
        fotoInput.value = "";
      });
    }
    if (fotoKaldir) {
      fotoKaldir.addEventListener("click", () => {
        if (ws && ws.readyState === 1 && oturum) {
          ws.send(JSON.stringify({
            tip: "avatar_yukle", yetkili: oturum.eposta,
            eposta: k.eposta, veri: "" }));
          const mes = document.getElementById("phFormMesaj");
          if (mes) mes.textContent = "...";
        }
      });
    }
  }

  document.getElementById("phKaydet").addEventListener("click", () => {
    const alanlar = {
      ad_soyad: document.getElementById("phAd").value.trim(),
      unvan: document.getElementById("phUnvan").value.trim(),
    };
    const sifre = document.getElementById("phSifre").value;
    if (sifre) alanlar.sifre = sifre;
    // v2.4.65 TEK KAPI: ROL DEGISTIRME BU PENCEREDEN KALDIRILDI.
    // Rol atamasi kurumsal panelde yapilir; sunucu da rol alanini
    // reddeder. Onceki kod burada alanlar.rol gonderiyordu; bu,
    // kapatilan "Kullanici Yonetimi" kapisinin yaninda acik kalan
    // ikinci bir kapiydi. Ad/unvan/sifre duzenlemesi KALIR.
    if (ws && ws.readyState === 1) {
      ws.send(JSON.stringify({
        tip: "kullanici_guncelle", yetkili: oturum.eposta,
        eposta: k.eposta, alanlar: alanlar }));
      const mes = document.getElementById("phFormMesaj");
      if (mes) mes.textContent = "...";
    }
  });
}

// v2.3.3: Secilen resmi canvas ile 256x256'ya sigacak sekilde
// kucultup JPEG data URL'e cevirir ve avatar_yukle komutu gonderir
function phFotoOlcekleGonder(dosya, eposta) {
  const t = D();
  const mes = document.getElementById("phFormMesaj");
  if (!/^image\//.test(dosya.type)) {
    if (mes) {
      mes.textContent = t.phFotoHataTip || "Yaln\u0131zca resim dosyas\u0131 se\u00e7in.";
      mes.className = "hata";
    }
    return;
  }
  const okuyucu = new FileReader();
  okuyucu.onload = () => {
    const resim = new Image();
    resim.onload = () => {
      const MAKS = 256;
      let g = resim.width, y = resim.height;
      const oran = Math.min(1, MAKS / Math.max(g, y));
      g = Math.max(1, Math.round(g * oran));
      y = Math.max(1, Math.round(y * oran));
      const tuval = document.createElement("canvas");
      tuval.width = g; tuval.height = y;
      tuval.getContext("2d").drawImage(resim, 0, 0, g, y);
      const veri = tuval.toDataURL("image/jpeg", 0.85);
      if (ws && ws.readyState === 1 && oturum) {
        ws.send(JSON.stringify({
          tip: "avatar_yukle", yetkili: oturum.eposta,
          eposta: eposta, veri: veri }));
        if (mes) { mes.textContent = "..."; mes.className = ""; }
      }
    };
    resim.onerror = () => {
      if (mes) {
        mes.textContent = t.phFotoHata || "Resim okunamad\u0131.";
        mes.className = "hata";
      }
    };
    resim.src = okuyucu.result;
  };
  okuyucu.readAsDataURL(dosya);
}

// Dinamik rol secenekleri: rol_yonetimi'nden gelen liste varsa onu,
// yoksa yerlesik kullanici/yonetici ikilisini kullanir
function phRolSecenekleri(mevcutRol, t) {
  let adlar = (window._ryRolAdlari && window._ryRolAdlari.length)
    ? window._ryRolAdlari.slice() : ["kullanici", "yonetici"];
  if (mevcutRol && !adlar.includes(mevcutRol)) adlar.push(mevcutRol);
  adlar.sort((a, b) => {
    const s = (x) => x === "yonetici" ? 0 : x === "kullanici" ? 1 : 2;
    return s(a) - s(b) || a.localeCompare(b, "tr");
  });
  return adlar.map((ad) => {
    const etiket = ad === "yonetici" ? (t.rolYonetici || "Yönetici")
      : ad === "kullanici" ? (t.rolKullanici || "Kullanıcı")
      : ad.toUpperCase();
    return "<option value='" + phKacir(ad) + "'" +
      (mevcutRol === ad ? " selected" : "") + ">" + etiket + "</option>";
  }).join("");
}

function phKacir(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/'/g, "&#39;").replace(/"/g, "&quot;");
}

// kullanici_islem cevabi geldiginde form geri bildirimi (ws.js cagirir)
window.pilotHakkindaIslemSonuc = function (m) {
  if (!_phPopup) return;
  const mes = document.getElementById("phFormMesaj");
  const t = D();
  if (mes) {
    mes.textContent = m.basarili
      ? (t.phKaydedildi || "Kaydedildi") : (m.hata || "Hata");
    mes.className = m.basarili ? "basari" : "hata";
    setTimeout(() => { if (mes) mes.textContent = ""; }, 3000);
  }
  // Hedefin guncel bilgisi
  if (m.basarili && m.guncel && _phHedef &&
      m.eposta === _phHedef.eposta) {
    Object.assign(_phHedef, m.guncel);
    phBaslikTazele();
    // Kendi profilimizi guncelledik: oturum + ust bar tazele
    if (oturum && m.eposta === oturum.eposta) {
      Object.assign(oturum, m.guncel);
      if (typeof oturumArayuzuKur === "function") oturumArayuzuKur();
    }
    // v2.3.3: avatar degisti -> bilgiler modulunu yeniden ciz
    // (yeni fotograf + kaldir dugmesi guncellensin)
    if (m.islem === "avatar" && _phModul === "bilgiler") phBilgilerCiz();
  }
};

// ---------------------------------------------------------------
// MODUL: Program Gecmisi (pilotun parametrik degisiklikleri)
// ---------------------------------------------------------------
function phGecmisAc() {
  const t = D();
  const detay = document.getElementById("phDetay");
  if (!detay) return;
  detay.innerHTML = "<div class='ph-liste-bos'>" +
    (t.phYukleniyor || "Yükleniyor...") + "</div>";
  if (ws && ws.readyState === 1) {
    ws.send(JSON.stringify({ tip: "pilot_log_listesi",
                             eposta: _phHedef.eposta }));
  }
}

// ws.js yonlendirir
window.pilotLogListeIsle = function (m) {
  if (!_phPopup || _phModul !== "gecmis") return;
  if (_phHedef && m.eposta && m.eposta !== _phHedef.eposta) return;
  _phLoglar = m.kayitlar || [];
  const t = D();
  const detay = document.getElementById("phDetay");
  if (!detay) return;
  if (_phLoglar.length === 0) {
    detay.innerHTML = "<div class='ph-liste-bos'>" +
      (t.phGecmisBos || "Kayıtlı işlem yok") + "</div>";
    return;
  }
  const kutu = document.createElement("div");
  kutu.className = "ph-log-liste";
  for (const kayit of _phLoglar) {
    const el = document.createElement("div");
    el.className = "ph-log";
    const dt = new Date((kayit.ts || 0) * 1000);
    const detayTxt = phLogDetayOzet(kayit.detay);
    el.innerHTML =
      "<span class='ph-log-kat " + phKacir(kayit.kategori || "") + "'>" +
        phKacir(kayit.kategori || "-") + "</span>" +
      "<div class='ph-log-govde'>" +
        "<div class='ph-log-islem'>" + phKacir(kayit.islem || "") + "</div>" +
        (detayTxt ? "<div class='ph-log-detay'>" + detayTxt + "</div>" : "") +
      "</div>" +
      "<span class='ph-log-zaman'>" + dt.toLocaleDateString() + " " +
        dt.toTimeString().slice(0, 8) + "</span>";
    kutu.appendChild(el);
  }
  detay.innerHTML = "";
  detay.appendChild(kutu);
};

function phLogDetayOzet(d) {
  if (!d || typeof d !== "object") return "";
  const parcalar = [];
  for (const [a, v] of Object.entries(d)) {
    if (v === null || v === undefined || v === "") continue;
    parcalar.push(phKacir(a) + "=" + phKacir(
      typeof v === "object" ? JSON.stringify(v) : String(v)));
  }
  return parcalar.slice(0, 6).join(" · ");
}

// ---------------------------------------------------------------
// MODUL: Ucuslar (tum kayitli ucuslar; cift tik -> onizleme)
// ---------------------------------------------------------------
function phUcuslarAc() {
  const t = D();
  const detay = document.getElementById("phDetay");
  if (!detay) return;
  detay.innerHTML = "<div class='ph-liste-bos'>" +
    (t.phYukleniyor || "Yükleniyor...") + "</div>";
  if (ws && ws.readyState === 1) {
    ws.send(JSON.stringify({ tip: "dron_gecmis_liste" }));
  }
}

// ws.js: dron_gecmis_liste cevabi hem gecmis.js hem buraya yonlenir
window.pilotUcusListeIsle = function (dronlar) {
  if (!_phPopup || _phModul !== "ucuslar") return;
  _phUcusDronlar = dronlar || [];
  const t = D();
  const detay = document.getElementById("phDetay");
  if (!detay) return;
  // Tum dronlarin ucuslarini tek listede topla (en yeni ustte)
  const ucuslar = [];
  for (const dr of _phUcusDronlar) {
    for (const u of (dr.ucuslar || [])) {
      ucuslar.push({ u: u, dron: dr });
    }
  }
  ucuslar.sort((a, b) => (b.u.baslangic || 0) - (a.u.baslangic || 0));
  if (ucuslar.length === 0) {
    detay.innerHTML = "<div class='ph-liste-bos'>" +
      (t.phUcusBos || "Kayıtlı uçuş yok") + "</div>";
    return;
  }
  const kutu = document.createElement("div");
  kutu.className = "ph-ucus-liste";
  const ipucu = document.createElement("div");
  ipucu.className = "ph-not";
  ipucu.textContent = t.phUcusIpucu ||
    "Bir uçuşa çift tıklayarak önizlemeyi açın";
  kutu.appendChild(ipucu);
  for (const { u, dron } of ucuslar) {
    const el = document.createElement("div");
    el.className = "ph-ucus";
    const dt = new Date((u.baslangic || 0) * 1000);
    el.innerHTML =
      "<span class='gc-renk' style='background:" + (dron.renk || "#888") + "'></span>" +
      "<div class='ph-ucus-govde'>" +
        "<div class='ph-ucus-ad'>" + phKacir(dron.isim || ("DRON " + dron.sysid)) + "</div>" +
        "<div class='ph-ucus-alt'>" + dt.toLocaleDateString() + " " +
          dt.toTimeString().slice(0, 5) + " · " + phSure(u.sure) + " · maks " +
          Math.round(u.max_irtifa || 0) + "m</div>" +
      "</div>" +
      "<i class='fa-solid fa-play ph-ucus-oynat' title='" +
        (t.phUcusOnizle || "Önizle") + "'></i>";
    el.addEventListener("dblclick", () => phUcusOnizle(u.id, dron));
    el.querySelector(".ph-ucus-oynat").addEventListener("click",
      () => phUcusOnizle(u.id, dron));
    kutu.appendChild(el);
  }
  detay.innerHTML = "";
  detay.appendChild(kutu);
};

function phSure(sn) {
  sn = Math.round(sn || 0);
  return Math.floor(sn / 60) + ":" + String(sn % 60).padStart(2, "0");
}

// ---------------------------------------------------------------
// Ucus onizleme popup'i (mini harita + basit oynatici)
// ---------------------------------------------------------------
function phUcusOnizle(ucusId, dron) {
  phOnizlemeKapat();
  const t = D();
  const pop = document.createElement("div");
  pop.className = "ph-onizleme";
  const bas = document.createElement("div");
  bas.className = "popup-baslik";
  bas.innerHTML =
    "<span><i class='fa-solid fa-plane-up'></i> " +
    (t.phUcusOnizleme || "UÇUŞ ÖNİZLEME") + " — " +
    phKacir(dron.isim || ("DRON " + dron.sysid)) + "</span>" +
    "<button class='popup-kapat' id='phOnKapat'><i class='fa-solid fa-xmark'></i></button>";
  pop.appendChild(bas);
  const govde = document.createElement("div");
  govde.className = "ph-onizleme-govde";
  govde.innerHTML =
    "<div id='phOnHarita'></div>" +
    "<div class='gc-oynatici' id='phOnOynatici'>" +
      "<button id='phOnPlay' title='Play'><i class='fa-solid fa-play'></i></button>" +
      "<select id='phOnHiz'>" +
        "<option value='1'>1x</option><option value='2'>2x</option>" +
        "<option value='5'>5x</option><option value='10'>10x</option>" +
      "</select>" +
      "<input type='range' id='phOnBar' min='0' max='100' value='0' step='1'>" +
      "<span id='phOnZaman'>0:00 / 0:00</span>" +
    "</div>";
  pop.appendChild(govde);
  document.body.appendChild(pop);
  pop.style.left = Math.max(10, (window.innerWidth - pop.offsetWidth) / 2 + 40) + "px";
  pop.style.top = Math.max(10, (window.innerHeight - pop.offsetHeight) / 2 + 20) + "px";
  if (window.popupTasinabilirYap) popupTasinabilirYap(pop, bas, "pp_phOnizleme");
  if (window.popupBoyutlandirilabilirYap)
    popupBoyutlandirilabilirYap(pop, "pp_phOnizleme", { minW: 480, minH: 340 });

  const viewer = new Cesium.Viewer("phOnHarita", {
    baseLayer: haritaKatmani(),
    baseLayerPicker: false, geocoder: false, homeButton: false,
    sceneModePicker: false, navigationHelpButton: false,
    animation: false, timeline: false, fullscreenButton: false,
    infoBox: false, selectionIndicator: false,
  });
  viewer.scene.globe.depthTestAgainstTerrain = false;
  viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString("#0b0e11");

  _phOnizleme = { popup: pop, viewer: viewer, oynatici: null, ucus: null,
                  renk: dron.renk || "#00E5FF" };

  document.getElementById("phOnKapat").addEventListener("click", phOnizlemeKapat);
  document.getElementById("phOnPlay").addEventListener("click", phOnPlayToggle);
  document.getElementById("phOnHiz").addEventListener("change", () => {
    if (_phOnizleme && _phOnizleme.oynatici)
      _phOnizleme.oynatici.hiz = parseFloat(document.getElementById("phOnHiz").value);
  });
  document.getElementById("phOnBar").addEventListener("input", () => {
    if (!_phOnizleme || !_phOnizleme.ucus) return;
    const oran = parseFloat(document.getElementById("phOnBar").value) / 100;
    phOnKonum(Math.floor(oran * (_phOnizleme.ucus.noktalar.length - 1)));
  });

  if (ws && ws.readyState === 1)
    ws.send(JSON.stringify({ tip: "ucus_oku", id: ucusId }));
}

function phOnizlemeKapat() {
  if (!_phOnizleme) return;
  if (_phOnizleme.oynatici && _phOnizleme.oynatici.timer)
    clearInterval(_phOnizleme.oynatici.timer);
  try { _phOnizleme.viewer.destroy(); } catch (e) {}
  _phOnizleme.popup.remove();
  _phOnizleme = null;
}

// ws.js: ucus_veri cevabi — onizleme acik ise buraya da yonlenir
window.pilotUcusVeriIsle = function (ucus) {
  if (!_phOnizleme) return false;
  if (!ucus || !ucus.noktalar || ucus.noktalar.length < 2) return true;
  const o = _phOnizleme;
  o.ucus = ucus;
  const viewer = o.viewer;
  const cRenk = Cesium.Color.fromCssColorString(o.renk);
  viewer.entities.removeAll();
  const pozlar = ucus.noktalar.map(n =>
    Cesium.Cartesian3.fromDegrees(n[2], n[1], Math.max(0, n[3])));
  viewer.entities.add({
    polyline: { positions: pozlar, width: 3, material: cRenk.withAlpha(0.9) } });
  const ilk = ucus.noktalar[0];
  o.nokta = viewer.entities.add({
    position: Cesium.Cartesian3.fromDegrees(ilk[2], ilk[1], Math.max(0, ilk[3])),
    billboard: (typeof elmasIkon === "function") ? {
      image: elmasIkon(o.renk), width: 26, height: 26,
      verticalOrigin: Cesium.VerticalOrigin.CENTER,
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    } : undefined,
    point: (typeof elmasIkon === "function") ? undefined : {
      pixelSize: 10, color: cRenk,
      disableDepthTestDistance: Number.POSITIVE_INFINITY },
  });
  viewer.flyTo(viewer.entities, { duration: 1.0 });
  o.oynatici = { timer: null, idx: 0, oynuyor: false,
    hiz: parseFloat((document.getElementById("phOnHiz") || {}).value || "1") };
  phOnKonum(0);
  return true;
};

function phOnKonum(idx) {
  const o = _phOnizleme;
  if (!o || !o.ucus) return;
  const n = o.ucus.noktalar;
  idx = Math.max(0, Math.min(idx, n.length - 1));
  o.oynatici.idx = idx;
  const p = n[idx];
  if (o.nokta) o.nokta.position =
    Cesium.Cartesian3.fromDegrees(p[2], p[1], Math.max(0, p[3]));
  const bar = document.getElementById("phOnBar");
  if (bar) bar.value = String(Math.round(idx / (n.length - 1) * 100));
  const z = document.getElementById("phOnZaman");
  if (z) z.textContent = phSure(p[0]) + " / " + phSure(n[n.length - 1][0]);
}

function phOnPlayToggle() {
  const o = _phOnizleme;
  if (!o || !o.ucus) return;
  const btn = document.getElementById("phOnPlay");
  if (o.oynatici.oynuyor) {
    clearInterval(o.oynatici.timer);
    o.oynatici.oynuyor = false;
    if (btn) btn.innerHTML = "<i class='fa-solid fa-play'></i>";
    return;
  }
  o.oynatici.oynuyor = true;
  if (btn) btn.innerHTML = "<i class='fa-solid fa-pause'></i>";
  if (o.oynatici.idx >= o.ucus.noktalar.length - 1) o.oynatici.idx = 0;
  o.oynatici.timer = setInterval(() => {
    if (!_phOnizleme || !_phOnizleme.ucus) return;
    const adim = Math.max(1, Math.round(_phOnizleme.oynatici.hiz));
    let yeni = _phOnizleme.oynatici.idx + adim;
    if (yeni >= _phOnizleme.ucus.noktalar.length - 1) {
      yeni = _phOnizleme.ucus.noktalar.length - 1;
      phOnPlayToggle(); // durdur
    }
    phOnKonum(yeni);
  }, 500);
}

// ---------------------------------------------------------------
// MODUL: Uyarilar
// ---------------------------------------------------------------
function phUyarilarAc() {
  const t = D();
  const detay = document.getElementById("phDetay");
  if (!detay) return;
  detay.innerHTML = "<div class='ph-liste-bos'>" +
    (t.phYukleniyor || "Yükleniyor...") + "</div>";
  if (ws && ws.readyState === 1) {
    ws.send(JSON.stringify({ tip: "uyari_listesi",
                             eposta: _phHedef.eposta }));
  }
}

// ws.js: uyari_listesi cevabi — modul acik ise ciz
window.pilotUyariListeIsle = function (m) {
  if (!_phPopup || _phModul !== "uyarilar") return;
  _phUyarilar = m.uyarilar || [];
  const t = D();
  const detay = document.getElementById("phDetay");
  if (!detay) return;
  if (_phUyarilar.length === 0) {
    detay.innerHTML = "<div class='ph-liste-bos'>" +
      (t.phUyariBos || "Uyarı yok") + "</div>";
    return;
  }
  const kutu = document.createElement("div");
  kutu.className = "ph-log-liste";
  for (const u of _phUyarilar) {
    const el = document.createElement("div");
    el.className = "ph-log ph-uyari" + (u.okundu ? "" : " okunmamis");
    const dt = new Date((u.ts || 0) * 1000);
    el.innerHTML =
      "<i class='fa-solid fa-triangle-exclamation ph-uyari-ikon'></i>" +
      "<div class='ph-log-govde'>" +
        "<div class='ph-log-islem'>" + phKacir(u.mesaj || "") + "</div>" +
      "</div>" +
      "<span class='ph-log-zaman'>" + dt.toLocaleDateString() + " " +
        dt.toTimeString().slice(0, 8) + "</span>";
    kutu.appendChild(el);
  }
  detay.innerHTML = "";
  detay.appendChild(kutu);
};

// ---------------------------------------------------------------
// Menu baglantisi
// ---------------------------------------------------------------
(function () {
  const oge = document.getElementById("pmPilotHakkinda");
  if (oge) oge.addEventListener("click", () => {
    document.getElementById("profilMenu").classList.add("popup-gizli");
    pilotHakkindaAc();
  });
})();

/* FAZ18-IS2B-IKON-METIN-SPAN */
