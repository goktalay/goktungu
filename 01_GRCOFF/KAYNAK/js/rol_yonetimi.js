// =====================================================================
// ROL_YONETIMI.JS - ROL / IZIN YONETIMI POPUP'I (v2.1.7)
// ---------------------------------------------------------------------
// - Yalniz yonetici rolundeki kullanicilar icin profil menusunde
//   "Rol Yönetimi" ogesi gorunur.
// - Popup: solda rol listesi, sagda secili rolun izin gruplari
//   (Radar / Dron / Kamera / Rotalar) onay kutulariyla.
// - Kaydet -> rol_kaydet WS komutu; sunucu semaya gore dogrular.
// - Izinler backend'de denetlenir: izinsiz islem calismaz ve merkezi
//   uyari sistemine kayit duser (uyari_merkezi.js).
// =====================================================================
"use strict";

let _ryPopup = null;      // acik popup
let _rySema = null;       // {grup: [izin,...]} backend'den
let _ryRoller = {};       // {rol: {grup:{izin:bool}}}
let _rySecili = null;     // secili rol adi
let _ryDegisti = false;   // kaydedilmemis degisiklik var mi

// Izin/grup etiketleri (i18n anahtarlarina esler)
const RY_GRUP_I18N = { radar: "ryGrupRadar", dron: "ryGrupDron",
                       kamera: "ryGrupKamera", rota: "ryGrupRota",
                       ai: "ryGrupAI" };
const RY_IZIN_I18N = {
  izleme: "ryIzinIzleme", hedef_yonetimi: "ryIzinHedef",
  parametre: "ryIzinParametre", kayit_yonetimi: "ryIzinKayit",
  pilotluk: "ryIzinPilotluk", angajman: "ryIzinAngajman",
  kutuphane_yonetimi: "ryIzinKutuphane", sunucu_yonetimi: "ryIzinSunucu",
  tespit_yonetimi: "ryIzinTespit" };

// ---------------------------------------------------------------
// Acilis / kapanis
// ---------------------------------------------------------------
function rolYonetimiAc() {
  if (!(oturum && oturum.rol === "yonetici")) return;
  if (_ryPopup) { _ryPopup.style.zIndex = "3000"; return; }
  const t = D();
  const pop = document.createElement("div");
  pop.className = "ry-popup";
  _ryPopup = pop;
  const bas = document.createElement("div");
  bas.className = "popup-baslik";
  bas.innerHTML =
    "<span><i class='fa-solid fa-user-shield'></i> " +
    (t.ryBaslik || "ROL YÖNETİMİ") + "</span>" +
    "<button class='popup-kapat' id='ryKapat'><i class='fa-solid fa-xmark'></i></button>";
  pop.appendChild(bas);
  const govde = document.createElement("div");
  govde.className = "ry-govde";
  govde.innerHTML =
    "<div class='ry-sol' id='ryRolListe'></div>" +
    "<div class='ry-sag' id='ryDetay'><div class='ph-liste-bos'>" +
      (t.phYukleniyor || "Yükleniyor...") + "</div></div>";
  pop.appendChild(govde);
  document.body.appendChild(pop);
  pop.style.left = Math.max(10, (window.innerWidth - pop.offsetWidth) / 2) + "px";
  pop.style.top = Math.max(10, (window.innerHeight - pop.offsetHeight) / 2) + "px";
  if (window.popupTasinabilirYap) popupTasinabilirYap(pop, bas, "pp_rolYonetimi");
  if (window.popupBoyutlandirilabilirYap)
    popupBoyutlandirilabilirYap(pop, "pp_rolYonetimi", { minW: 520, minH: 380 });
  document.getElementById("ryKapat").addEventListener("click", rolYonetimiKapat);

  if (ws && ws.readyState === 1)
    ws.send(JSON.stringify({ tip: "rol_listesi" }));
}

function rolYonetimiKapat() {
  if (_ryPopup) { _ryPopup.remove(); _ryPopup = null; }
  _rySecili = null; _ryDegisti = false;
}

// ---------------------------------------------------------------
// WS cevaplari (ws.js yonlendirir): rol_listesi / rol_islem
// ---------------------------------------------------------------
window.rolListesiIsle = function (m) {
  _rySema = m.sema || _rySema;
  _ryRoller = m.roller || {};
  // Pilot Hakkinda rol combobox'i icin guncel rol adlari
  window._ryRolAdlari = Object.keys(_ryRoller);
  if (!_rySecili || !_ryRoller[_rySecili]) {
    // Varsayilan secim: kullanici rolu (duzenlenmesi en olasi olan)
    _rySecili = _ryRoller["kullanici"] ? "kullanici"
      : Object.keys(_ryRoller)[0] || null;
  }
  _ryDegisti = false;
  ryRolListeCiz();
  ryDetayCiz();
};

window.rolIslemIsle = function (m) {
  const t = D();
  if (m.roller) window.rolListesiIsle(m);
  const mes = document.getElementById("ryMesaj");
  if (mes) {
    const hataMetin = {
      rol_var: t.ryHataRolVar || "Bu adla bir rol zaten var.",
      rol_korumali: t.ryHataKorumali || "Bu rol korumalıdır; silinemez/değiştirilemez.",
      rol_kullanimda: t.ryHataKullanimda || "Bu role atanmış kullanıcılar var; önce rollerini değiştirin.",
      gecersiz_ad: t.ryHataGecersizAd || "Geçersiz rol adı.",
      rol_yok: t.ryHataRolYok || "Rol bulunamadı.",
    }[m.hata] || m.hata || "Hata";
    mes.textContent = m.basarili
      ? (t.ryKaydedildi || "Kaydedildi") : hataMetin;
    mes.className = m.basarili ? "basari" : "hata";
    setTimeout(() => { if (mes) mes.textContent = ""; }, 4000);
  }
};

// ---------------------------------------------------------------
// Sol: rol listesi
// ---------------------------------------------------------------
function ryRolListeCiz() {
  const kutu = document.getElementById("ryRolListe");
  if (!kutu) return;
  const t = D();
  kutu.innerHTML = "";
  // Yerlesik roller once, digerleri alfabetik
  const adlar = Object.keys(_ryRoller).sort((a, b) => {
    const s = (x) => x === "yonetici" ? 0 : x === "kullanici" ? 1 : 2;
    return s(a) - s(b) || a.localeCompare(b, "tr");
  });
  for (const ad of adlar) {
    const el = document.createElement("div");
    el.className = "ry-rol" + (ad === _rySecili ? " secili" : "");
    const etiket = ad === "yonetici" ? (t.rolYonetici || "Yönetici")
      : ad === "kullanici" ? (t.rolKullanici || "Kullanıcı") : ad;
    el.innerHTML = "<i class='fa-solid " +
      (ad === "yonetici" ? "fa-user-shield" : "fa-user") + "'></i><span>" +
      etiket + "</span>";
    // Korumasiz roller (yerlesik olmayanlar) silinebilir
    if (ad !== "yonetici" && ad !== "kullanici") {
      const sil = document.createElement("button");
      sil.className = "ry-rol-sil";
      sil.title = t.ryRolSil || "Rolü Sil";
      sil.innerHTML = "<i class='fa-solid fa-trash-can'></i>";
      sil.addEventListener("click", (e) => {
        e.stopPropagation();
        const soru = (t.ryRolSilOnay ||
          "'{rol}' rolü silinsin mi?").replace("{rol}", etiket);
        if (!window.confirm(soru)) return;
        if (ws && ws.readyState === 1)
          ws.send(JSON.stringify({ tip: "rol_sil", rol: ad }));
      });
      el.appendChild(sil);
    }
    el.addEventListener("click", () => {
      _rySecili = ad; _ryDegisti = false;
      ryRolListeCiz(); ryDetayCiz();
    });
    kutu.appendChild(el);
  }
  // Yeni rol ekleme satiri
  const ekle = document.createElement("div");
  ekle.className = "ry-rol-ekle";
  ekle.innerHTML =
    "<input type='text' id='ryYeniRolAd' maxlength='32' placeholder='" +
    (t.ryYeniRolPh || "Yeni rol adı...") + "'>" +
    "<button id='ryRolEkleBtn' title='" + (t.ryRolEkle || "Rol Ekle") +
    "'><i class='fa-solid fa-plus'></i></button>";
  kutu.appendChild(ekle);
  const giris = ekle.querySelector("#ryYeniRolAd");
  const gonder = () => {
    const ad = (giris.value || "").trim().toLowerCase();
    if (!ad) return;
    if (ws && ws.readyState === 1) {
      _rySecili = ad; // eklenen rol otomatik secilsin
      ws.send(JSON.stringify({ tip: "rol_ekle", rol: ad }));
    }
    giris.value = "";
  };
  ekle.querySelector("#ryRolEkleBtn").addEventListener("click", gonder);
  giris.addEventListener("keydown", (e) => {
    if (e.key === "Enter") gonder();
  });
}

// ---------------------------------------------------------------
// Sag: izin gruplari (onay kutulari)
// ---------------------------------------------------------------
function ryDetayCiz() {
  const detay = document.getElementById("ryDetay");
  if (!detay) return;
  const t = D();
  detay.innerHTML = "";
  if (!_rySecili || !_rySema) return;
  const izinler = _ryRoller[_rySecili] || {};
  const yoneticiRolu = _rySecili === "yonetici";

  if (yoneticiRolu) {
    const not = document.createElement("div");
    not.className = "ph-not";
    not.textContent = t.ryYoneticiNot ||
      "Yönetici rolü her zaman tam yetkilidir; kısıtlanamaz.";
    detay.appendChild(not);
  }

  for (const [grup, liste] of Object.entries(_rySema)) {
    const kart = document.createElement("div");
    kart.className = "ry-grup";
    const baslik = document.createElement("div");
    baslik.className = "ry-grup-baslik";
    baslik.textContent = t[RY_GRUP_I18N[grup]] || grup.toUpperCase();
    kart.appendChild(baslik);
    for (const izin of liste) {
      const satir = document.createElement("label");
      satir.className = "ry-izin";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = !!(izinler[grup] || {})[izin];
      cb.disabled = yoneticiRolu;
      cb.addEventListener("change", () => {
        if (!_ryRoller[_rySecili][grup]) _ryRoller[_rySecili][grup] = {};
        _ryRoller[_rySecili][grup][izin] = cb.checked;
        _ryDegisti = true;
      });
      const yazi = document.createElement("span");
      yazi.textContent = t[RY_IZIN_I18N[izin]] || izin;
      satir.appendChild(cb);
      satir.appendChild(yazi);
      kart.appendChild(satir);
    }
    detay.appendChild(kart);
  }

  if (!yoneticiRolu) {
    const alt = document.createElement("div");
    alt.className = "ry-alt";
    alt.innerHTML =
      "<button id='ryKaydet' class='onay-btn'><i class='fa-solid fa-check'></i><span>" +
      (t.btnKaydet || "Kaydet") + "</span></button><span id='ryMesaj'></span>";
    detay.appendChild(alt);
    document.getElementById("ryKaydet").addEventListener("click", () => {
      if (ws && ws.readyState === 1) {
        ws.send(JSON.stringify({
          tip: "rol_kaydet", rol: _rySecili,
          izinler: _ryRoller[_rySecili] || {} }));
      }
    });
  }
}

// ---------------------------------------------------------------
// v2.4.65 TEK KAPI: Menu baglantisi KALDIRILDI
// ---------------------------------------------------------------
// Rol/izin duzenleme kurumsal panelden (/company/) yapilir. Sunucu
// tarafinda da rol_kaydet / rol_ekle / rol_sil komutlari reddedilir;
// bu yuzden menuyu birakmak kullaniciyi calismayan bir ekrana
// goturur. rolYonetimiAc() islevi silinmedi (baska modul cagirabilir)
// ancak hicbir menu ogesine bagli degildir.
//
// OKUMA TARAFI KORUNUR: window.rolAdlariTazele ve rolListesiIsle
// calismaya devam eder; Pilot Hakkinda penceresindeki rol combobox'i
// bu listeyi kullanir ve rol_listesi komutu hala aciktir.

// Yonetici giris yaptiginda rol adlari cache'ini doldur
// (Pilot Hakkinda rol combobox'inin dinamik listesi icin)
window.rolAdlariTazele = function () {
  if (oturum && oturum.rol === "yonetici" && ws && ws.readyState === 1)
    ws.send(JSON.stringify({ tip: "rol_listesi" }));
};

/* FAZ18-IS2B-IKON-METIN-SPAN */
