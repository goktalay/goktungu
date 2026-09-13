// =================================================================
// GOKTUNGU v2.4.53 - PROGRAM AYARLARI -> MERKEZ SUNUCU BOLUMU
//
// Kullanici istegi: baglanti yoneticisinde "acik olan sunucular"
// listelenecek. Bu liste merkezden gelir; merkeze erisim icin bu
// kurulumun bir merkez HESABI olmalidir. Hesap bilgileri BURADA
// girilir (radar/GCCDUAL/servis bolumleriyle ayni kalip).
//
// Tasarim kararlari:
//   - Sifre SUNUCUDA saklanir, arayuze ASLA geri gonderilmez. Alan bos
//     gelir; bos birakilirsa sunucu mevcut sifreyi korur (sunucu.py
//     program_ayar_yaz icinde uygulanmistir).
//   - Merkeze cagriyi GCS sunucusu yapar (WS: merkez_dogrula). Boylece
//     sifre tarayiciya inmez ve CORS sorunu dogmaz.
//   - Yonetici olmayan kullanici alanlari degistiremez (sunucu ayrica
//     denetler).
// =================================================================
"use strict";

// Sunucudan gelen mevcut degerler (ayarlar duyurusu ile guncellenir).
// Sifre burada TUTULMAZ; sunucu yalnizca "sifre var mi" bilgisini verir.
window.merkezAyarDegerleri = window.merkezAyarDegerleri || {
  acik: false, adres: "", eposta: "", sifre_var: false
};

// harita.js/ayarlariUygula -> buraya dagitir.
window.merkezAyarSunucudan = function(a){
  if (!a) return;
  const d = window.merkezAyarDegerleri;
  // Sunucudaki gercek ayar anahtari `merkez_etkin` (bkz. sunucu.py
  // program_ayar_yaz ve goktungu/merkez.py ayar_coz).
  if (typeof a.merkez_etkin === "boolean") d.acik = a.merkez_etkin;
  if (typeof a.merkez_adres === "string") d.adres = a.merkez_adres;
  if (typeof a.merkez_eposta === "string") d.eposta = a.merkez_eposta;
  if (typeof a.merkez_sifre_var === "boolean") d.sifre_var = a.merkez_sifre_var;
  // Popup acikken durum degistiyse alanlari tazele
  const cb = document.getElementById("progMerkezAnahtar");
  if (cb) cb.checked = d.acik;
  const ad = document.getElementById("progMerkezAdres");
  if (ad && document.activeElement !== ad) ad.value = d.adres;
  const ep = document.getElementById("progMerkezEposta");
  if (ep && document.activeElement !== ep) ep.value = d.eposta;
  const sf = document.getElementById("progMerkezSifre");
  if (sf) sf.placeholder = d.sifre_var
    ? ((typeof D === "function" && D().progAyarMerkezSifreVar) ||
       "\u2022\u2022\u2022\u2022\u2022\u2022 (kay\u0131tl\u0131)")
    : ((typeof D === "function" && D().progAyarMerkezSifrePlaceholder) ||
       "Merkez hesab\u0131 \u015fifresi");
};

// MERKEZ bagalanti turu dugmesinin gorunurlugu: hesap kapali ise
// kullaniciya calismayacak bir dugme gostermek yanlis olur.
window.merkezTurDugmeTazele = function(){
  const b = document.getElementById("btnYeniMerkez");
  if (!b) return;
  b.style.display = window.merkezAyarDegerleri.acik ? "" : "none";
};

// ---------------------------------------------------------------
// Program Ayarlari govdesine bolumu ekler (svBolumEkle ile ayni kalip)
// ---------------------------------------------------------------
window.merkezBolumEkle = function(govde){
  const t = (typeof D === "function") ? D() : {};
  const yonetici = (typeof oturumYoneticiMi === "function")
    ? oturumYoneticiMi() : false;
  const d = window.merkezAyarDegerleri;

  govde.appendChild(document.createElement("hr"));

  // --- Ac/kapat satiri ---
  const s = document.createElement("div");
  s.className = "prog-ayar-satir";
  const e = document.createElement("span");
  e.className = "prog-ayar-etiket";
  e.innerHTML = "<i class='fa-solid fa-tower-broadcast'></i> " +
    (t.progAyarMerkez || "Merkez Sunucu");
  const an = document.createElement("label");
  an.className = "prog-anahtar";
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.id = "progMerkezAnahtar";
  cb.checked = d.acik;
  cb.disabled = !yonetici;
  const kay = document.createElement("span");
  kay.className = "prog-anahtar-top";
  an.appendChild(cb); an.appendChild(kay);
  if (!yonetici) an.classList.add("prog-anahtar-kilitli");
  s.appendChild(e); s.appendChild(an);
  govde.appendChild(s);

  const acik = document.createElement("div");
  acik.className = "prog-ayar-aciklama";
  const acikYaz = (v) => {
    acik.textContent = v
      ? (t.progAyarMerkezAcik ||
         "Merkez etkin: ba\u011flant\u0131 y\u00f6neticisinde a\u00e7\u0131k sunucular listelenir")
      : (t.progAyarMerkezKapali ||
         "Merkez kapal\u0131 (MERKEZ ba\u011flant\u0131 t\u00fcr\u00fc g\u00f6r\u00fcnmez)");
  };
  acikYaz(d.acik);
  govde.appendChild(acik);

  // --- Alanlar (yalniz acikken gorunur) ---
  const alanlar = [];
  const alanEkle = (id, etiketMetin, ikon, tur, yerTutucu, deger) => {
    const sat = document.createElement("div");
    sat.className = "prog-ayar-satir prog-ayar-port";
    const et = document.createElement("span");
    et.className = "prog-ayar-etiket";
    et.innerHTML = "<i class='fa-solid " + ikon + "'></i> " + etiketMetin;
    const gi = document.createElement("input");
    gi.type = tur;
    gi.id = id;
    gi.className = "prog-ayar-giris";
    gi.placeholder = yerTutucu;
    gi.value = deger || "";
    gi.disabled = !yonetici;
    if (tur === "password") gi.autocomplete = "new-password";
    sat.appendChild(et); sat.appendChild(gi);
    govde.appendChild(sat);
    alanlar.push(sat);
    return gi;
  };

  const gAdres = alanEkle("progMerkezAdres",
    t.progAyarMerkezAdres || "Merkez adresi", "fa-globe", "text",
    "https://goktungu.com", d.adres);
  const gEposta = alanEkle("progMerkezEposta",
    t.progAyarMerkezEposta || "Merkez e-posta", "fa-envelope", "text",
    "ad@firma.com", d.eposta);
  const gSifre = alanEkle("progMerkezSifre",
    t.progAyarMerkezSifre || "Merkez \u015fifresi", "fa-key", "password",
    d.sifre_var
      ? (t.progAyarMerkezSifreVar || "\u2022\u2022\u2022\u2022\u2022\u2022 (kay\u0131tl\u0131)")
      : (t.progAyarMerkezSifrePlaceholder || "Merkez hesab\u0131 \u015fifresi"),
    "");

  // --- Dogrula dugmesi + durum satiri ---
  const dSat = document.createElement("div");
  dSat.className = "prog-ayar-satir";
  const dBos = document.createElement("span");
  dBos.className = "prog-ayar-etiket";
  dBos.innerHTML = "<i class='fa-solid fa-circle-check'></i> " +
    (t.progAyarMerkezSina || "Hesab\u0131 s\u0131na");
  const dBtn = document.createElement("button");
  dBtn.type = "button";
  dBtn.className = "prog-ayar-dugme";
  dBtn.id = "btnMerkezDogrula";
  dBtn.textContent = t.progAyarMerkezDogrula || "Do\u011frula";
  dBtn.disabled = !yonetici;
  dSat.appendChild(dBos); dSat.appendChild(dBtn);
  govde.appendChild(dSat);
  alanlar.push(dSat);

  const durum = document.createElement("div");
  durum.className = "pa-merkez-durum";
  durum.id = "paMerkezDurum";
  durum.style.display = "none";
  govde.appendChild(durum);
  alanlar.push(durum);

  const bilgi = document.createElement("div");
  bilgi.className = "prog-ayar-aciklama";
  bilgi.textContent = t.progAyarMerkezAciklama ||
    "\u0130leti\u015fim tek y\u00f6nl\u00fcd\u00fcr: bu bilgisayar merkeze " +
    "ba\u011flan\u0131r, merkez bu bilgisayara ba\u011flanmaz. Sabit IP gerekmez.";
  govde.appendChild(bilgi);
  alanlar.push(bilgi);

  // =============================================================
  // KOPRU KAYDI (v2.4.53 Faz 12-14)
  //
  // Neden ayri bir bolum: `Dogrula` yalniz hesabi sinar, hicbir sey
  // yazmaz. `Merkeze kaydet` ise merkezde KALICI bir sunucu satiri ve
  // TEK SEFERLIK bir sir uretir; bu yuzden ayri dugme ve (yenileme
  // durumunda) onay ister.
  //
  // Sir arayüzde HIC gorunmez: sunucu yalniz `kimlik_ozet()` maskesini
  // gonderir (kayitli mi, ornek_id, ad, son 4 karakter).
  // =============================================================
  const kBaslik = document.createElement("div");
  kBaslik.className = "prog-ayar-altbaslik";
  kBaslik.innerHTML = "<i class='fa-solid fa-id-badge'></i> " +
    (t.progAyarKopruBaslik || "Bu kurulumun merkez kayd\u0131");
  govde.appendChild(kBaslik);
  alanlar.push(kBaslik);

  const gKurulumAd = alanEkle("progKopruAd",
    t.progAyarKopruAd || "Kurulum ad\u0131", "fa-signature", "text",
    t.progAyarKopruAdPlaceholder ||
      "Bo\u015f b\u0131rak\u0131l\u0131rsa bilgisayar ad\u0131 kullan\u0131l\u0131r", "");

  const kSat = document.createElement("div");
  kSat.className = "prog-ayar-satir";
  const kEt = document.createElement("span");
  kEt.className = "prog-ayar-etiket";
  // Satir etiketi dugme metniyle AYNI olmamali: ayni ifade iki kez
  // okunur ("Merkeze kaydet  [Merkeze kaydet]") ve ekran okuyucularda
  // gurultu uretir. Etiket eylemi degil KONUYU adlandirir.
  kEt.innerHTML = "<i class='fa-solid fa-tower-cell'></i> " +
    (t.progAyarKopruKayitEtiket || "Kay\u0131t i\u015flemi");
  const kBtnKutu = document.createElement("span");
  kBtnKutu.className = "pa-kopru-dugmeler";
  const kBtn = document.createElement("button");
  kBtn.type = "button";
  kBtn.className = "prog-ayar-dugme";
  kBtn.id = "btnKopruKayit";
  kBtn.textContent = t.progAyarKopruKayit || "Merkeze kaydet";
  kBtn.disabled = !yonetici;
  const kYenBtn = document.createElement("button");
  kYenBtn.type = "button";
  kYenBtn.className = "prog-ayar-dugme prog-ayar-dugme-ikincil";
  kYenBtn.id = "btnKopruYenile";
  kYenBtn.textContent = t.progAyarKopruYenile || "Kimli\u011fi yenile";
  kYenBtn.disabled = !yonetici;
  kYenBtn.style.display = "none";
  kBtnKutu.appendChild(kBtn); kBtnKutu.appendChild(kYenBtn);
  kSat.appendChild(kEt); kSat.appendChild(kBtnKutu);
  govde.appendChild(kSat);
  alanlar.push(kSat);

  const kDurum = document.createElement("div");
  kDurum.className = "pa-kopru-durum";
  kDurum.id = "paKopruDurum";
  govde.appendChild(kDurum);
  alanlar.push(kDurum);

  const kBilgi = document.createElement("div");
  kBilgi.className = "prog-ayar-aciklama";
  kBilgi.textContent = t.progAyarKopruAciklama ||
    "Bu kurulum merkeze kaydedilirse ba\u015fka pilotlar ba\u011flant\u0131 " +
    "y\u00f6neticisindeki MERKEZ listesinde bu bilgisayar\u0131 g\u00f6r\u00fcp " +
    "ba\u011flanabilir.";
  govde.appendChild(kBilgi);
  alanlar.push(kBilgi);

  const gorunumTazele = (v) => {
    alanlar.forEach(el => { el.style.display = v ? "" : "none"; });
    // Durum satiri yalniz sonuc geldiginde gorunur.
    if (!v) durum.style.display = "none";
    else if (!durum.textContent) durum.style.display = "none";
  };
  gorunumTazele(d.acik);

  // --- Olaylar ---
  const yaz = (alan, deger) => {
    if (!yonetici) return;
    if (typeof ws === "undefined" || !ws || ws.readyState !== 1) return false;
    const m = {tip: "program_ayar_yaz"};
    m[alan] = deger;
    ws.send(JSON.stringify(m));
    return true;
  };

  cb.addEventListener("change", () => {
    if (!yonetici){ cb.checked = d.acik; return; }
    if (yaz("merkez_etkin", cb.checked) === false){
      cb.checked = d.acik; return;
    }
    d.acik = cb.checked;
    acikYaz(d.acik);
    gorunumTazele(d.acik);
    window.merkezTurDugmeTazele();
  });

  const metinBagla = (gi, alan) => {
    gi.addEventListener("change", () => {
      const v = gi.value.trim();
      // Sifre alani BOS ise hic gonderilmez: bos gondermek sunucudaki
      // kayitli sifreyi silmek anlamina gelirdi (sunucu bos degeri
      // "degistirme" olarak yorumluyor, yine de gereksiz yazma yapmayiz).
      if (alan === "merkez_sifre" && !v) return;
      yaz(alan, v);
      if (alan === "merkez_adres") d.adres = v;
      if (alan === "merkez_eposta") d.eposta = v;
      if (alan === "merkez_sifre"){
        d.sifre_var = true;
        gi.value = "";
        gi.placeholder = t.progAyarMerkezSifreVar ||
          "\u2022\u2022\u2022\u2022\u2022\u2022 (kay\u0131tl\u0131)";
      }
    });
    gi.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter"){ ev.preventDefault(); gi.blur(); }
    });
  };
  metinBagla(gAdres, "merkez_adres");
  metinBagla(gEposta, "merkez_eposta");
  metinBagla(gSifre, "merkez_sifre");

  dBtn.addEventListener("click", () => {
    if (!yonetici) return;
    if (typeof ws === "undefined" || !ws || ws.readyState !== 1){
      durum.textContent = t.merkezSunucuBaglantiYok ||
        "Sunucu ba\u011flant\u0131s\u0131 yok.";
      durum.className = "pa-merkez-durum bag-merkez-kotu";
      durum.style.display = "block";
      return;
    }
    // Alanlar henuz kaydedilmemis olabilir: once yaz, sonra dogrula.
    const ad = gAdres.value.trim();
    const ep = gEposta.value.trim();
    const sf = gSifre.value;
    if (ad && ad !== d.adres){ yaz("merkez_adres", ad); d.adres = ad; }
    if (ep && ep !== d.eposta){ yaz("merkez_eposta", ep); d.eposta = ep; }
    if (sf){
      yaz("merkez_sifre", sf);
      d.sifre_var = true;
      gSifre.value = "";
      gSifre.placeholder = t.progAyarMerkezSifreVar ||
        "\u2022\u2022\u2022\u2022\u2022\u2022 (kay\u0131tl\u0131)";
    }
    durum.textContent = t.progAyarMerkezSiniyor ||
      "Do\u011frulan\u0131yor\u2026";
    durum.className = "pa-merkez-durum";
    durum.style.display = "block";
    ws.send(JSON.stringify({tip: "merkez_dogrula"}));
  });

  // --- Kopru kaydi olaylari ---
  const kayitGonder = (yenile) => {
    if (!yonetici) return;
    if (typeof ws === "undefined" || !ws || ws.readyState !== 1){
      window.kopruDurumCiz({basarili: false,
        hata: t.merkezSunucuBaglantiYok ||
          "Sunucu ba\u011flant\u0131s\u0131 yok."});
      return;
    }
    // Kayit merkeze HTTP cagrisi yapar; alanlar henuz kaydedilmemis
    // olabilir, once ayarlari yaz.
    const ad = gAdres.value.trim();
    const ep = gEposta.value.trim();
    const sf = gSifre.value;
    if (ad && ad !== d.adres){ yaz("merkez_adres", ad); d.adres = ad; }
    if (ep && ep !== d.eposta){ yaz("merkez_eposta", ep); d.eposta = ep; }
    if (sf){
      yaz("merkez_sifre", sf);
      d.sifre_var = true;
      gSifre.value = "";
      gSifre.placeholder = t.progAyarMerkezSifreVar ||
        "\u2022\u2022\u2022\u2022\u2022\u2022 (kay\u0131tl\u0131)";
    }
    kDurum.textContent = t.progAyarKopruKayitYapiliyor ||
      "Merkeze kaydediliyor\u2026";
    kDurum.className = "pa-kopru-durum";
    const paket = {tip: "merkez_kayit"};
    const kad = gKurulumAd.value.trim();
    if (kad) paket.ad = kad;
    if (yenile) paket.yenile = true;
    ws.send(JSON.stringify(paket));
  };

  kBtn.addEventListener("click", () => kayitGonder(false));
  kYenBtn.addEventListener("click", () => {
    // Yenileme merkezdeki eski sirri gecersiz kilar: onay sarti.
    const soru = t.progAyarKopruYenileOnay ||
      "Kurulum kimli\u011fi yenilenecek. S\u00fcrd\u00fcr\u00fcls\u00fcn m\u00fc?";
    // Projedeki ortak onay kalibi (bkz. servis_panel.js:128)
    if (typeof window.onayIste === "function"){
      window.onayIste(soru, () => kayitGonder(true));
    } else if (window.confirm(soru)){
      kayitGonder(true);
    }
  });

  // Popup her acildiginda taze durum istenir (kayit/kopru degismis
  // olabilir; ornegin baska bir oturumda kaydedilmis olabilir).
  if (typeof ws !== "undefined" && ws && ws.readyState === 1 && yonetici)
    ws.send(JSON.stringify({tip: "merkez_kopru_durum"}));
  else
    window.kopruDurumCiz(window.kopruDurumSon);
};

// ---------------------------------------------------------------
// Kopru durumu / kayit sonucu cizimi
//
// Sunucu iki mesaj gonderir: `merkez_kayit_sonuc` (dugme yaniti) ve
// `merkez_kopru_durum` (durum sorgusu + ayar degisiminde duyuru).
// Ikisi de ayni govdeyi tasir: {kimlik, kopru}.
// ---------------------------------------------------------------
window.kopruDurumSon = null;

window.kopruDurumCiz = function(m){
  if (m) window.kopruDurumSon = m;
  const t = (typeof D === "function") ? D() : {};
  const el = document.getElementById("paKopruDurum");
  const kBtn = document.getElementById("btnKopruKayit");
  const kYen = document.getElementById("btnKopruYenile");
  if (!el) return;
  m = m || {};
  if (m.basarili === false && m.hata){
    el.textContent = (t.progAyarKopruKayitHata ||
      "Merkez kayd\u0131 yap\u0131lamad\u0131") + ": " + m.hata;
    el.className = "pa-kopru-durum bag-merkez-kotu";
    return;
  }
  const k = m.kimlik || {};
  const kp = m.kopru || {};
  if (!k.kayitli){
    el.textContent = t.progAyarKopruKayitsiz || "Kay\u0131tl\u0131 de\u011fil";
    el.className = "pa-kopru-durum";
    if (kBtn) kBtn.textContent = t.progAyarKopruKayit || "Merkeze kaydet";
    if (kYen) kYen.style.display = "none";
    return;
  }
  // Kayitli: ad + ornek numarasi + kopru baglanti durumu
  const satirlar = [];
  const adPar = [k.ad || "", k.ornek_id ? ("#" + k.ornek_id) : ""]
    .filter(Boolean).join(" ");
  satirlar.push((t.progAyarKopruKayitli || "Kay\u0131tl\u0131") +
    (adPar ? (": " + adPar) : ""));
  if (k.firma_kisa_ad) satirlar.push(k.firma_kisa_ad);
  let sinif = "pa-kopru-durum bag-merkez-iyi";
  if (kp.bagli){
    satirlar.push(t.progAyarKopruBagli || "Merkeze ba\u011fl\u0131");
  } else if (kp.calisiyor){
    satirlar.push(t.progAyarKopruBagliDegil ||
      "Merkeze ba\u011fl\u0131 de\u011fil");
    sinif = "pa-kopru-durum bag-merkez-bekle";
  } else {
    satirlar.push(t.progAyarKopruKapali || "K\u00f6pr\u00fc kapal\u0131");
    sinif = "pa-kopru-durum";
  }
  if (kp.bekleyen_kayit)
    satirlar.push(kp.bekleyen_kayit + " " +
      (t.progAyarKopruBekleyen || "bekleyen kay\u0131t"));
  if (kp.son_hata && !kp.bagli){
    satirlar.push(kp.son_hata);
    sinif = "pa-kopru-durum bag-merkez-kotu";
  }
  el.textContent = satirlar.join(" \u00b7 ");
  el.className = sinif;
  // Kayitliyken ana dugme yine "kaydet" olarak kalir: kullanici baska
  // bir ad vermek isteyebilir; merkez ayni kurulum icin 409 doner ve
  // "Kimligi yenile" secenegi zaten ayrica sunulur.
  if (kBtn) kBtn.textContent = t.progAyarKopruKayit || "Merkeze kaydet";
  if (kYen) kYen.style.display = "";
};

// WS yonlendiricisinin cagirdigi adlar
window.merkezKayitSonuc = function(m){ window.kopruDurumCiz(m); };
window.merkezKopruDurum = function(m){ window.kopruDurumCiz(m); };
