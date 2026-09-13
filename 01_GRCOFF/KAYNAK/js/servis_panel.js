// FAZ18-IS27-28-30: ikon+metin dugmelerinde metin <span> icine
// sarildi. Sebep: dugme_birlik.css yalniz-ikon kurali
// `:has(> i):not(:has(> span))` bu dugmeleri 26px kareye
// zorluyordu ve metin tasiyordu. CSS EZILMEDI; sozlesmeye
// uyuldu. Yalniz-ikon dugmelere DOKUNULMADI.
/* ===================================================================
   GOKTUNGU GCS — v2.4.49  SERVIS PANELI + MAKINE GUC YONETIMI
   ===================================================================
   Kullanici istegi (iki ekranli GCCDUAL cantasi):
     "arayuzde servisi durdurup baslatabilecegim program ayarlarinda
      bir bolum olsun, bilgisayar acildiginda otomatik acilsin"
     "kullanici menusu altinda bilgisayari kapat dugmesi olsun, basinca
      eminmisiniz desin evet derse bilgisayari kapatsin, bu sayede
      kullanici bilgisayara erismek zorunda kalmasin"

   TASARIM KARARLARI (neden boyle):

   1) SERVISI DURDURMAK = KENDINI DURDURMAK
      Servisi durdurma komutu, sunucunun kendi surecini oldurmesi
      demektir. Sunucu yaniti gondermeden once dururse WS baglantisi
      kopar ve arayuz "ne oldu" bilemez. Bu yuzden sunucu ONCE yaniti
      gonderir (`beklemede:true`), eylemi 1 sn sonra uygular. Arayuz
      bu isareti gorunce "baglanti kesilecek" der ve yeniden baglanma
      beklentisine gecer. Aksi halde operator, islem basarisiz sandi.

   2) YETKI OLCUMU SUNUCUDAN GELIR, TAHMIN EDILMEZ
      `guc_hazir=false` ise (polkit/sudo kurali yok) dugmeler HIC
      gosterilmez. Gosterilip basildiginda hicbir sey olmamasi en kotu
      davranistir: operator makineyi kapattigini sanip gider.

   3) UCUS EMNIYETI
      Havada dron varken makineyi kapatmak/servisi durdurmak baglantiyi
      kesip gorevi yarida birakir. Sunucu ucan dron sayisini dondurur;
      arayuz onay metnine bunu YAZAR. Karar operatore ait, ancak
      korlemede degil.

   4) YALNIZ YONETICI
      Gorunurluk kolayliktir; sunucu her komutta rolu AYRICA denetler
      (istemciye guvenilmez).
   =================================================================== */

// Sunucudan gelen son servis durumu (servis_durum yaniti)
let svDurum = null;
// Servis bolumunun DOM govdesi (popup her acilista yeniden kurulur)
let svGovde = null;
// Gunluk penceresi acik mi
let svGunlukAcik = false;

function svT(){ return (typeof D === "function") ? D() : {}; }

function svToast(mesaj, seviye, baslik){
  if (typeof window.uyariToastGoster === "function"){
    window.uyariToastGoster({
      baslik: baslik || "", mesaj: mesaj,
      seviye: seviye || "bilgi", sure: 5000, kategori: "servis",
    });
  }
}

function svGonder(nesne){
  if (typeof ws !== "undefined" && ws && ws.readyState === 1){
    ws.send(JSON.stringify(nesne));
    return true;
  }
  return false;
}

/* Sunucudan servis durumunu ister. Popup acilista ve eylem sonrasi. */
function svDurumIste(){ svGonder({tip: "servis_durum"}); }
window.svDurumIste = svDurumIste;

/* -------------------------------------------------------------------
   MAKINE GUC DUGMELERI (kullanici menusu)
   Gorunurluk: yonetici + guc_hazir. kullanici.js giriste cagirir,
   servis_durum yaniti gelince yeniden degerlendirilir.
   ------------------------------------------------------------------- */
window.makineGucGorunumTazele = function(){
  const yonetici = (typeof oturumYoneticiMi === "function")
    ? oturumYoneticiMi() : false;
  // guc_hazir henuz bilinmiyorsa (durum gelmedi) dugme gizli kalir ve
  // durum gelince acilir. Once gosterip sonra gizlemek titreme yapar.
  const hazir = !!(svDurum && svDurum.guc_hazir);
  const gorunur = (yonetici && hazir) ? "flex" : "none";
  ["pmMakineKapat", "pmMakineYeniden"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.style.display = gorunur;
  });
  // Yonetici ama yetki yoksa bir kez bilgilendir: sessizce gizlemek
  // "dugme neden yok" sorusunu dogurur.
  if (yonetici && svDurum && !hazir && !svDurum._gucUyarildi){
    svDurum._gucUyarildi = true;
    const t = svT();
    if (svDurum.destekli === false){
      // systemd yok (Windows/macOS) — beklenen durum, uyari gerekmez.
    } else {
      svToast(t.svGucYetkiYok ||
        "Makineyi kapatma yetkisi yok. Kurulum betigi calistirilmadiysa: " +
        "bash kur_2449.sh --servis", "bilgi",
        t.svGucBaslik || "GUC YONETIMI");
    }
  }
};

/* Ucan dron sayisini onay metnine ekler (emniyet). */
function svUcusUyarisi(){
  const t = svT();
  const n = (svDurum && typeof svDurum.ucan === "number")
    ? svDurum.ucan : 0;
  if (n <= 0) return "";
  return "\n\n\u26a0 " + (t.svUcanDron ||
    "DIKKAT: su anda havada {n} dron var; baglanti kesilecek.")
    .replace("{n}", String(n));
}

function svMakineOnay(ad){
  const t = svT();
  const kapat = (ad === "kapat");
  const soru = (kapat
    ? (t.svKapatSoru || "Bilgisayar KAPATILACAK. Emin misiniz?")
    : (t.svYenidenSoru ||
       "Bilgisayar YENIDEN BASLATILACAK. Emin misiniz?"))
    + svUcusUyarisi();
  const uygula = () => {
    if (!svGonder({tip: "makine_kapat", ad: ad})){
      svToast(t.svBaglantiYok || "Sunucu baglantisi yok.", "hata");
      return;
    }
    svToast(kapat
      ? (t.svKapatiliyor || "Kapatma komutu verildi...")
      : (t.svYenidenBasliyor || "Yeniden baslatma komutu verildi..."),
      "uyari", t.svGucBaslik || "GUC YONETIMI");
  };
  if (typeof window.onayIste === "function") window.onayIste(soru, uygula);
  else if (window.confirm(soru)) uygula();
}

/* -------------------------------------------------------------------
   WS YANIT ISLEYICILERI (ws.js cagirir)
   ------------------------------------------------------------------- */
window.svDurumGeldi = function(m){
  const oncekiHazir = !!(svDurum && svDurum.guc_hazir);
  const uyarildi = !!(svDurum && svDurum._gucUyarildi);
  svDurum = m || {};
  // Uyari bir kez verilir; durum her tazelemede yeniden gelmesin.
  if (uyarildi && !svDurum.guc_hazir) svDurum._gucUyarildi = true;
  window.makineGucGorunumTazele();
  if (svGovde) svBolumCiz(svGovde);
  if (oncekiHazir !== !!svDurum.guc_hazir){
    // yetki durumu degistiyse (kurulum betigi kosturuldu) sessiz kalma
  }
};

window.svSonucGeldi = function(m){
  const t = svT();
  if (m && m.beklemede){
    // Sunucu kendini durduracak/yeniden baslatacak: baglanti kopacak.
    svToast(m.ileti || (t.svBaglantiKesilecek ||
      "Servis durduruluyor; baglanti kesilecek."), "uyari",
      t.svBaslik || "SERVIS");
    return;
  }
  if (m && m.basarili){
    svToast(m.ileti || (t.svIslemTamam || "Islem tamamlandi."),
      "basari", t.svBaslik || "SERVIS");
  } else {
    svToast((m && (m.hata || m.ileti)) ||
      (t.svIslemBasarisiz || "Islem basarisiz."), "hata",
      t.svBaslik || "SERVIS");
  }
  // Durum degismis olabilir; tazele.
  setTimeout(svDurumIste, 900);
};

window.svGunlukGeldi = function(m){
  const kutu = document.getElementById("svGunlukKutu");
  if (!kutu) return;
  const t = svT();
  if (m && m.basarili && Array.isArray(m.satirlar)){
    kutu.textContent = m.satirlar.length
      ? m.satirlar.join("\n")
      : (t.svGunlukBos || "Gunluk bos.");
  } else {
    kutu.textContent = (m && m.hata) ||
      (t.svGunlukAlinamadi || "Gunluk alinamadi.");
  }
  kutu.scrollTop = kutu.scrollHeight;
};

window.svMakineSonucGeldi = function(m){
  const t = svT();
  if (m && m.basarili){
    svToast(m.ileti || (t.svGucVerildi ||
      "Komut verildi; makine kapaniyor."), "uyari",
      t.svGucBaslik || "GUC YONETIMI");
  } else {
    svToast((m && m.hata) || (t.svGucBasarisiz ||
      "Makine komutu basarisiz."), "hata",
      t.svGucBaslik || "GUC YONETIMI");
  }
};

/* -------------------------------------------------------------------
   PROGRAM AYARLARI — SERVIS BOLUMU
   program_ayar.js cagirir: svBolumEkle(govde, yonetici)
   ------------------------------------------------------------------- */
function svSatir(etiketHtml){
  const s = document.createElement("div");
  s.className = "prog-ayar-satir";
  const e = document.createElement("span");
  e.className = "prog-ayar-etiket";
  e.innerHTML = etiketHtml;
  s.appendChild(e);
  return {satir: s, etiket: e};
}

function svAciklama(metin, sinif){
  const a = document.createElement("div");
  a.className = "prog-ayar-aciklama" + (sinif ? " " + sinif : "");
  a.textContent = metin;
  return a;
}

/* Servis bolumunu (yeniden) cizer. Durum degisince cagrilir. */
function svBolumCiz(govde){
  const t = svT();
  const yonetici = (typeof oturumYoneticiMi === "function")
    ? oturumYoneticiMi() : false;
  govde.innerHTML = "";

  // --- Durum ozeti ---
  const d = svDurum || {};
  const destekli = d.destekli !== false;
  const kurulu = !!d.kurulu;
  const aktif = d.aktif === true;

  const bas = document.createElement("div");
  bas.className = "prog-ayar-satir svc-durum-satir";
  const basE = document.createElement("span");
  basE.className = "prog-ayar-etiket";
  basE.innerHTML = "<i class='fa-solid fa-gears'></i> " +
    (t.svDurumEtiket || "Servis durumu");
  const rozet = document.createElement("span");
  rozet.className = "svc-rozet " + (
    !destekli ? "svc-rozet-yok"
    : !kurulu ? "svc-rozet-kurulmadi"
    : aktif ? "svc-rozet-aktif" : "svc-rozet-durdu");
  rozet.textContent = !destekli
    ? (t.svYok || "DESTEKLENMIYOR")
    : !kurulu ? (t.svKurulmadi || "KURULU DEGIL")
    : aktif ? (t.svAktif || "CALISIYOR") : (t.svDurdu || "DURDU");
  bas.appendChild(basE); bas.appendChild(rozet);
  govde.appendChild(bas);

  if (d.ozet) govde.appendChild(svAciklama(d.ozet));

  if (!destekli){
    govde.appendChild(svAciklama(t.svYokAciklama ||
      "Bu isletim sisteminde systemd yok; servis yonetimi yalniz " +
      "Linux'ta kullanilabilir."));
    return;
  }

  // Kurulu degilse: ne yapilacagini SOYLE (sessiz kalma)
  if (!kurulu){
    govde.appendChild(svAciklama(t.svKurulumGerek ||
      "Servis kurulmamis. Kurmak icin: bash kur_2449.sh --servis",
      "prog-ayar-kilit-uyari"));
  }

  // --- Acilista otomatik baslat anahtari ---
  const {satir: sA, etiket: eA} = svSatir(
    "<i class='fa-solid fa-power-off'></i> " +
    (t.svAcilista || "Bilgisayar acilinca otomatik baslat"));
  const an = document.createElement("label");
  an.className = "prog-anahtar";
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.id = "svAcilistaAnahtar";
  cb.checked = !!d.acilista;
  cb.disabled = !yonetici || !kurulu;
  const top = document.createElement("span");
  top.className = "prog-anahtar-top";
  an.appendChild(cb); an.appendChild(top);
  if (cb.disabled) an.classList.add("prog-anahtar-kilitli");
  sA.appendChild(an);
  govde.appendChild(sA);
  cb.addEventListener("change", () => {
    if (cb.disabled){ cb.checked = !!d.acilista; return; }
    const ad = cb.checked ? "etkinlestir" : "devredisi";
    if (!svGonder({tip: "servis_eylem", ad: ad})){
      cb.checked = !!d.acilista;
      svToast(t.svBaglantiYok || "Sunucu baglantisi yok.", "hata");
    }
  });

  // --- Eylem dugmeleri ---
  const dugKap = document.createElement("div");
  dugKap.className = "svc-dugme-kap";

  const dugmeEkle = (ad, metin, ikon, sinif, tehlikeli) => {
    const b = document.createElement("button");
    b.className = "svc-dugme " + (sinif || "");
    b.innerHTML = "<i class='fa-solid " + ikon + "'></i> " + "<span>" + ( metin) + "</span>";
    b.disabled = !yonetici || !kurulu;
    b.addEventListener("click", () => {
      if (b.disabled) return;
      const uygula = () => {
        if (!svGonder({tip: "servis_eylem", ad: ad}))
          svToast(t.svBaglantiYok || "Sunucu baglantisi yok.", "hata");
      };
      if (tehlikeli){
        const soru = (ad === "durdur"
          ? (t.svDurdurSoru ||
             "Servis durdurulacak; arayuz baglantisi kesilecek. Emin misiniz?")
          : (t.svYenidenServisSoru ||
             "Servis yeniden baslatilacak; baglanti kisa sure kesilecek. Emin misiniz?"))
          + svUcusUyarisi();
        if (typeof window.onayIste === "function")
          window.onayIste(soru, uygula);
        else if (window.confirm(soru)) uygula();
      } else uygula();
    });
    dugKap.appendChild(b);
  };

  if (!aktif) dugmeEkle("baslat", t.svBaslat || "Baslat",
                        "fa-play", "svc-dugme-basari", false);
  if (aktif) dugmeEkle("durdur", t.svDurdur || "Durdur",
                       "fa-stop", "svc-dugme-tehlike", true);
  dugmeEkle("yeniden", t.svYeniden || "Yeniden baslat",
            "fa-rotate-right", "svc-dugme-uyari", true);

  const gBtn = document.createElement("button");
  gBtn.className = "svc-dugme";
  gBtn.innerHTML = "<i class='fa-solid fa-file-lines'></i> " + "<span>" + (
    (t.svGunluk || "Gunluk")) + "</span>";
  gBtn.disabled = !kurulu;
  gBtn.addEventListener("click", () => {
    svGunlukAcik = !svGunlukAcik;
    const k = document.getElementById("svGunlukSar");
    if (k) k.style.display = svGunlukAcik ? "" : "none";
    if (svGunlukAcik) svGonder({tip: "servis_gunluk", satir: 120});
  });
  dugKap.appendChild(gBtn);
  govde.appendChild(dugKap);

  // --- Gunluk kutusu (acilir kapanir) ---
  const gSar = document.createElement("div");
  gSar.id = "svGunlukSar";
  gSar.className = "svc-gunluk-sar";
  gSar.style.display = svGunlukAcik ? "" : "none";
  const gKutu = document.createElement("pre");
  gKutu.id = "svGunlukKutu";
  gKutu.className = "svc-gunluk-kutu";
  gKutu.textContent = t.svGunlukYukleniyor || "Yukleniyor...";
  gSar.appendChild(gKutu);
  const gTaze = document.createElement("button");
  gTaze.className = "svc-dugme svc-dugme-mini";
  gTaze.innerHTML = "<i class='fa-solid fa-rotate'></i> " + "<span>" + (
    (t.svTazele || "Tazele")) + "</span>";
  gTaze.addEventListener("click",
    () => svGonder({tip: "servis_gunluk", satir: 120}));
  gSar.appendChild(gTaze);
  govde.appendChild(gSar);

  // --- Calisma bilgisi ---
  const bilgiler = [];
  if (d.pid) bilgiler.push((t.svPid || "PID") + ": " + d.pid);
  if (d.kip && d.kip !== "yok")
    bilgiler.push((t.svKip || "Kip") + ": " + d.kip);
  if (d.servis_olarak_calisiyor === false && kurulu && aktif)
    bilgiler.push(t.svElleCalisiyor ||
      "DIKKAT: bu arayuz servis DISINDA elle baslatilmis bir surecten " +
      "geliyor.");
  if (bilgiler.length)
    govde.appendChild(svAciklama(bilgiler.join("  \u00b7  ")));

  if (!yonetici)
    govde.appendChild(svAciklama(t.progAyarYalnizYonetici ||
      "Program ayarlarini yalniz yonetici degistirebilir.",
      "prog-ayar-kilit-uyari"));
}

/* program_ayar.js bu islevi cagirir. */
window.svBolumEkle = function(govde){
  govde.appendChild(document.createElement("hr"));
  const sar = document.createElement("div");
  sar.className = "svc-bolum";
  govde.appendChild(sar);
  svGovde = sar;
  svBolumCiz(sar);
  svDurumIste();          // gercek durumu sunucudan al
};

/* Popup kapaninca govde referansi birakilir (DOM'dan silindi). */
window.svBolumKapandi = function(){ svGovde = null; svGunlukAcik = false; };

// ---------------------------------------------------------------
// KURULUM
// ---------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  const k = document.getElementById("pmMakineKapat");
  if (k) k.addEventListener("click", (ev) => {
    ev.stopPropagation();
    const pm = document.getElementById("profilMenu");
    if (pm) pm.classList.add("popup-gizli");
    svMakineOnay("kapat");
  });
  const y = document.getElementById("pmMakineYeniden");
  if (y) y.addEventListener("click", (ev) => {
    ev.stopPropagation();
    const pm = document.getElementById("profilMenu");
    if (pm) pm.classList.add("popup-gizli");
    svMakineOnay("yeniden");
  });
});
