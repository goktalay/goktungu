// FAZ18-IS27-28-30: ikon+metin dugmelerinde metin <span> icine
// sarildi. Sebep: dugme_birlik.css yalniz-ikon kurali
// `:has(> i):not(:has(> span))` bu dugmeleri 26px kareye
// zorluyordu ve metin tasiyordu. CSS EZILMEDI; sozlesmeye
// uyuldu. Yalniz-ikon dugmelere DOKUNULMADI.
// =================================================================
// GOKTUNGU - POSTGRESQL ILK KURULUM / GOC SIHIRBAZI  [v2.4.51]
// -----------------------------------------------------------------
// Kullanici istegi (birebir):
//   "sistemi ilk actigimda bana sunucu bilgilerini sorsun, ip adresi,
//    kullanici adi, sifresi, veritabani adi, sonra ilk kurulumu
//    yapsin, eger daha once kurulum yapildiysa ilk acilista veri
//    tabaninda tablolarda yada diger seylerde bir guncelleme varsa
//    sihirbaz acilsin ve guncellemeyi yapsin. tum bu sureclerde
//    mutlaka progressbar olsun ve neyin surdugunu bilgilendirsin."
//
// TASARIM KARARLARI
// -----------------
// 1) Sihirbaz GIRIS EKRANINDAN ONCE acilir.
//    Sebep: kullanicilar tablosu PostgreSQL'de. Veritabani
//    yapilandirilmamisken kimse dogrulanamaz; giris formu gostermek
//    kullaniciyi cikisi olmayan bir ekranda birakirdi. Bu, sirket
//    sihirbazinin (sirket.js) TERSIDIR — o giristen SONRA acilir,
//    cunku rol bilgisi gerekir.
//
// 2) Uc adim, tek perde. Adim gecisleri DOM'u yeniden uretir; ara
//    durum tek bir nesnede (_pgD) tutulur. Bu, "geri" dusmesinin
//    girilen bilgileri kaybetmemesini saglar.
//
// 3) Her "Ileri" dugmesi sunucuya GERCEK bir baglanti denemesi yapar
//    (pg_dene). Kullanici istegi: "her ilerle dediginde mutlaka
//    girilen bilgileri dogrulamali". Yanlis bilgiyle kurulum
//    baslatilmaz.
//
// 4) Ilerleme cubugu SUNUCUDAN gelen pg_ilerleme mesajlariyla
//    beslenir; tarayicida sahte animasyon YOKTUR. Cubuk gercekten
//    tamamlanan adimi gosterir. Adim gunlugu ayrica listelenir
//    (denetim izi: hangi adim tamamlandi).
//
// 5) Sihirbaz TAMAMLANMADAN kapatilamaz (ESC/dis tik yok, kapat
//    dugmesi yok). Veritabani olmadan sistemin hicbir islevi
//    calismaz; "gorsel uyari" degil GERCEK bir engeldir.
//
// 6) Sifre asla sunucudan geri OKUNMAZ (pg_durum sifre gondermez).
//    Yeniden yapilandirmada kullanici sifreyi tekrar girer.
// =================================================================

// Sihirbaz durum nesnesi. Adim gecisleri arasinda yasar.
var _pgD = {
  perde: null,        // DOM perdesi (null ise sihirbaz kapali)
  kip: "",            // "kurulum" | "goc"
  adim: 1,            // 1..4  (4: v2.4.66 merkez kullanici esitlemesi)
  bekliyor: false,    // sunucu yaniti bekleniyor mu
  gonderilen: "",     // bekledigimiz komutun adi
  bilgi: {            // form verisi
    sunucu: "127.0.0.1", port: 5432,
    veritabani: "goktungu", kullanici: "goktungu", sifre: ""
  },
  dogrulama: null,    // pg_dene yaniti
  durum: null,        // son pg_durum yaniti
  adimlar: [],        // ilerleme gunlugu satirlari
  yuzde: 0,
  ileti: "",
  hata: "",
  bitti: false,

  // ---- v2.4.66: MERKEZ KULLANICI ESITLEMESI (ADIM 4) ----
  // OLCULEN KUSUR: Kurulum bittiginde yerel `kullanicilar` tablosu bos
  // kaliyor, bu yuzden GOKTUNGU kaynak koda GOMULU bir hesap yaratiyordu
  // (`gokkubbe2026`). Musterinin /company/ panelinde tanimladigi sifre
  // GECERSIZ kaliyordu. Bu adim merkezdeki gercek kullanici listesini
  // bir kez ceker.
  //
  // ATLANABILIR: kullanicinin sarti "isterse kapali devre kullanabilir".
  // Merkeze hic baglanmadan da kurulum tamamlanabilmelidir.
  esitlemeBilgi: { adres: "", eposta: "", sifre: "" },
  esitlemeSonuc: null,   // {cekilen, eklendi, guncellendi, firma_unvan}
  esitlemeAtlandi: false,
  // ---- 2.4.233 (kullanici istegi): MERKEZ SUNUCU + API KODU (ADIM 4) ----
  // E-posta/sifre ve sirket bilgisi formu yerine kurumsal paneldeki
  // "Merkezi Yazilimlar" kaydinin API kodu girilir; kurum bilgileri ve
  // logo merkezden BIR KEZ cekilir (pg_merkez_kod).
  kodBilgi: { adres: "", kod: "" },
  kodSonuc: null,        // {firma_unvan, logo_var, ad, adres}
  // ---- v2.4.67: KURULUM KIMLIGI (ADIM 5) ----
  // `pg_sonuc` yanitindaki `kurulum_hesabi` buraya yazilir:
  // {eposta, sifre, dosya}. v2.4.68'de EKRANDA GOSTERILMIYOR (asagi bak)
  // ama alan korunuyor: `pg_sonuc` isleyicisi hala yaziyor.
  kurulumHesabi: null,

  // ---- v2.4.68: YONETICI HESABI (ADIM 5) ----
  // OLCULEN KUSUR: v2.4.67 adim 5'te RASTGELE uretilmis sifreyi
  // gosteriyordu. Servis olarak kurulunca konsol gorunmedigi icin
  // kullanici o sifreyi hic gormuyordu; merkez esitlemesi de
  // atlandiginda sisteme HIC giremiyordu.
  //
  // Kullanicinin bildirimi (birebir): "en azindan sihirbazda bana
  // sorsun kullanici adi sifreyi, merkezden bagimsiz olarak".
  //
  // AYRI NESNE ZORUNLU: `pgAlanKur` degerleri `_pgD.bilgi`ye yazar;
  // ayni nesne kullanilsaydi veritabani baglanti bilgilerinin UZERINE
  // yazardi (adim 4'te olculen ayni tuzak).
  yonBilgi: { eposta: "", ad_soyad: "", sifre: "", sifre2: "" },
  yonSonuc: null,        // {basarili, eposta, degistirildi}
  yonYurutuluyor: false, // sunucu yaniti bekleniyor mu
};

function pgKacis(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Dil sozlugu; i18n.js yuklenmemisse cokmemek icin korumali.
function pgT() {
  try { return (typeof D === "function" ? D() : {}) || {}; }
  catch (e) { return {}; }
}

function pgGonder(nesne) {
  try {
    if (typeof ws === "undefined" || !ws || ws.readyState !== 1) return false;
    ws.send(JSON.stringify(nesne));
    return true;
  } catch (e) { return false; }
}

// ---------------------------------------------------------------
// ACILIS: sunucuya durum sor (ws.js -> onopen)
// ---------------------------------------------------------------
window.pgDurumSor = function () {
  pgGonder({ tip: "pg_durum" });
};

// ---------------------------------------------------------------
// pg_durum yaniti: sihirbaz acilacak mi?
// ---------------------------------------------------------------
window.pgDurumGeldi = function (m) {
  _pgD.durum = m || {};
  // VT_MENU_KIP_2486: bayrak her tazelendiginde menu gorunumu yeniden
  // hesaplanir. Sira garantisi YOKTUR: pg_durum yaniti giristen once
  // de sonra da gelebilir, bu yuzden iki taraftan da cagrilir.
  try { window.vtMenuGorunumTazele(); } catch (e) {}

  // ---- MERKEZ KIPI: SIHIRBAZ HIC ACILMAZ (v2.4.54) ----
  // Kullanici istegi: "merkez guncellemesini sen yap neden kullaniciya
  // yaptiriyorsun". Merkezde sema yonetimi operatorun isidir; goc
  // acilista sunucu tarafinda uygulanir.
  //
  // Sunucu zaten `goc_gerekli:false` gonderir; bu denetim IKINCI
  // savunmadir. Sebebi olculdu: bayragi tek yerde bastirmak, ileride
  // pg_durum yolunda (erisim hatasi dali gibi) bir kosul degistiginde
  // sihirbazin sessizce geri gelmesine yol acar. Merkezde perde acilmasi
  // pilotu cikisi olmayan bir ekranda birakir -- sihirbaz kapatilamaz
  // (tasarim karari 5).
  if (m && m.merkez_kipi) {
    if (_pgD.perde) pgSihirbazKapat();
    return;
  }

  // Sihirbaz zaten acik ve bir islem suruyorsa durumu bozma.
  // v2.4.196 OLCULEN KUSUR: kurulum (pg_kur) surerken WS koptu ve yeniden
  // kuruldu; ws.onopen yeniden pg_durum sordu ama sihirbaz `bekliyor`
  // oldugu icin yaniti YOK SAYDI ve dugme sonsuza kadar dondu. Sunucu
  // kurulumu aslinda bitirmisti (F5 sonrasi sistem acildi). Beklerken
  // gelen durum "yapilandirilmis + erisim var + goc yok" diyorsa
  // kurulum TAMAMLANMIS sayilir ve sihirbaz sonuca gecer.
  if (_pgD.perde && _pgD.bekliyor) {
    const _tamam = !!m.yapilandirildi && m.erisim !== false && !m.goc_gerekli;
    if (_tamam && (_pgD.gonderilen === "pg_kur" || _pgD.gonderilen === "pg_goc")) {
      _pgD.bekliyor = false;
      _pgD.bitti = true;
      _pgD.hata = "";
      _pgD.yuzde = 100;
      if (_pgD.kip === "kurulum" && _pgD.adim < 4) _pgD.adim = 4;
      pgCiz();
    }
    return;
  }

  const yapilandirildi = !!m.yapilandirildi;
  const gocGerekli = !!m.goc_gerekli;
  const erisim = m.erisim !== false;

  if (!yapilandirildi) {
    // ILK KURULUM. Kayitli bilgi yok; varsayilanlarla form acilir.
    if (!_pgD.perde) pgSihirbazAc("kurulum");
    return;
  }

  if (!erisim) {
    // Yapilandirma var ama sunucuya erisilemiyor (sifre degismis,
    // sunucu tasinmis, servis kapali). Bilgileri onceden dolduralim;
    // sifre gelmez, kullanici yeniden girer.
    _pgD.bilgi.sunucu = m.sunucu || _pgD.bilgi.sunucu;
    _pgD.bilgi.port = m.port || 5432;
    _pgD.bilgi.veritabani = m.veritabani || _pgD.bilgi.veritabani;
    _pgD.bilgi.kullanici = m.kullanici || _pgD.bilgi.kullanici;
    _pgD.bilgi.sifre = "";
    _pgD.hata = m.hata || (pgT().pgErisimYok || "");
    if (!_pgD.perde) pgSihirbazAc("kurulum");
    else pgCiz();
    return;
  }

  if (gocGerekli) {
    // GOC SIHIRBAZI. Kullanici istegi: "tablolarda yada diger
    // seylerde bir guncelleme varsa sihirbaz acilsin".
    if (!_pgD.perde) pgSihirbazAc("goc");
    return;
  }

  // Her sey yolunda: sihirbaz acik kaldiysa kapat.
  //
  // v2.4.69 OLCULEN KUSUR ("postgresql kurulumu sonrasi direkt login
  // sayfasina atiyor, kullanici adi ve sifre gelmiyor"):
  // Kurulum bitince `pgSonucGeldi` `_pgD.bitti = true` yapar ve 300 ms
  // sonra `pg_durum` sorar.  Yanit "yapilandirildi + goc yok" olarak
  // gelir, yani bu dala duser ve perde SILINIR.  Kullanici adim 3'un
  // dugmelerine basacak zaman bulamaz; adim 4 (merkez aktarimi) ve
  // adim 5 (kendi yonetici hesabi) HIC gorunmez.  Yerel tabloda yalniz
  // `kurulum@yerel` + rastgele sifre kalir -- sifre servis kipinde
  // gorunmeyen konsola yazildigi icin kullanici sisteme HIC giremez.
  //
  // AYRIM ZORUNLU:
  //  - goc kipi: kimlik adimi YOKTUR, bitince kapanmasi dogrudur.
  //  - kurulum kipi: kullanici adim 4 veya 5 uzerinden CIKMALIDIR.
  //    Bu yuzden kurulum kipinde otomatik kapatma YAPILMAZ; bunun
  //    yerine kimlik adimina gecilir (kullanici dugmeye basmayi
  //    unutsa bile hesap ekranini gorur).
  if (_pgD.perde && _pgD.bitti) {
    if (_pgD.kip === "kurulum" && _pgD.adim < 4) {
      _pgD.adim = 4;
      _pgD.hata = "";
      pgCiz();
      return;
    }
    if (_pgD.kip !== "kurulum") pgSihirbazKapat();
  }
};

// ---------------------------------------------------------------
// SIHIRBAZI AC / KAPAT
// ---------------------------------------------------------------
function pgSihirbazAc(kip) {
  _pgD.kip = kip;
  _pgD.adim = (kip === "goc") ? 3 : 1;
  _pgD.bekliyor = false;
  _pgD.bitti = false;
  _pgD.adimlar = [];
  _pgD.yuzde = 0;
  _pgD.ileti = "";
  if (_pgD.perde) { pgCiz(); return; }
  const perde = document.createElement("div");
  perde.className = "pgs-perde";
  perde.id = "pgSihirbazPerde";
  const kutu = document.createElement("div");
  kutu.className = "pgs-kutu";
  kutu.id = "pgSihirbazKutu";
  perde.appendChild(kutu);
  document.body.appendChild(perde);
  _pgD.perde = perde;
  pgCiz();
}
window.pgSihirbazAc = pgSihirbazAc;

function pgSihirbazKapat() {
  if (_pgD.perde && _pgD.perde.parentNode)
    _pgD.perde.parentNode.removeChild(_pgD.perde);
  _pgD.perde = null;
  _pgD.bekliyor = false;
  _pgD.hata = "";
}
window.pgSihirbazKapat = pgSihirbazKapat;

// Kullanici menusunden yeniden yapilandirma (yalniz yonetici).
window.pgSihirbazYenidenAc = function () {
  const d = _pgD.durum || {};
  _pgD.bilgi.sunucu = d.sunucu || _pgD.bilgi.sunucu;
  _pgD.bilgi.port = d.port || 5432;
  _pgD.bilgi.veritabani = d.veritabani || _pgD.bilgi.veritabani;
  _pgD.bilgi.kullanici = d.kullanici || _pgD.bilgi.kullanici;
  _pgD.bilgi.sifre = "";
  _pgD.hata = "";
  pgSihirbazAc("kurulum");
};

// ---------------------------------------------------------------
// CIZIM
// ---------------------------------------------------------------
function pgCiz() {
  if (!_pgD.perde) return;
  const kutu = _pgD.perde.querySelector(".pgs-kutu");
  if (!kutu) return;
  kutu.innerHTML = "";
  kutu.appendChild(pgBaslikKur());
  if (_pgD.kip === "kurulum") kutu.appendChild(pgAdimlarKur());
  if (_pgD.kip === "goc") {
    kutu.appendChild(pgGocGovde());
  } else if (_pgD.adim === 1) {
    kutu.appendChild(pgAdim1Govde());
  } else if (_pgD.adim === 2) {
    kutu.appendChild(pgAdim2Govde());
  } else if (_pgD.adim === 4) {
    // v2.4.66: merkez kullanici esitlemesi. Ayri dal ZORUNLU; aksi
    // halde `else` dali adim 3'u cizer ve adim 4 hic gorunmez.
    kutu.appendChild(pgAdim4Govde());
  } else if (_pgD.adim === 5) {
    // v2.4.67: esitleme ATLANDIGINDA kurulum kimligini gosterir.
    // Ayri dal ZORUNLU (adim 4 ile ayni gerekce).
    kutu.appendChild(pgAdim5Govde());
  } else {
    kutu.appendChild(pgAdim3Govde());
  }
  kutu.appendChild(pgAltBarKur());
}

function pgBaslikKur() {
  const t = pgT();
  const goc = _pgD.kip === "goc";
  const bas = document.createElement("div");
  bas.className = "pgs-bas";

  // v2.4.66/67: adim 4 ve 5 veritabani kurulumu DEGIL; kimlik
  // adimlaridir. Baslik "VERITABANI KURULUMU" kalirsa kullanici
  // hangi asamada oldugunu anlamaz.
  let ikon = goc ? "fa-arrow-up-right-dots" : "fa-database";
  let ust = goc ? (t.pgGocBaslik || "VER\u0130TABANI G\u00dcNCELLEMES\u0130")
                : (t.pgBaslik || "VER\u0130TABANI KURULUMU");
  let altb = goc
    ? (t.pgGocAltBaslik ||
       "Yeni s\u00fcr\u00fcm veritaban\u0131nda de\u011fi\u015fiklik gerektiriyor.")
    : (t.pgAltBaslik ||
       "G\u00d6KTUNGU verilerini saklayacak PostgreSQL sunucusunu " +
       "tan\u0131mlay\u0131n.");

  if (!goc && _pgD.adim === 4) {
    // 2.4.235: adim 4 artik merkez sunucu + API kodu (kullanici esitlemesi degil).
    ikon = "fa-key";
    ust = t.pgKodBaslik || "MERKEZ SUNUCU";
    altb = t.pgKodAltBaslik ||
      "Bu kurulumu merkeze API koduyla e\u015fle\u015ftirin; kurum bilgileri " +
      "ve logo merkezden bir kez al\u0131n\u0131r.";
  } else if (!goc && _pgD.adim === 5) {
    ikon = "fa-user-shield";
    ust = t.pgYonBaslik || "YÖNETİCİ HESABI";
    altb = t.pgYonAltBaslik ||
      "Sisteme gireceğiniz kullanıcı adını ve şifreyi siz belirleyin.";
  }

  bas.innerHTML =
    "<i class='fa-solid " + ikon + "'></i>" +
    "<div><strong>" + pgKacis(ust) + "</strong><span>" +
    pgKacis(altb) + "</span></div>";
  return bas;
}

function pgAdimlarKur() {
  const t = pgT();
  // v2.4.66: dorduncu adim — merkez kullanici esitlemesi.
  const adlar = [
    t.pgAdim1 || "Sunucu Bilgileri",
    t.pgAdim2 || "Do\u011frulama",
    t.pgAdim3 || "Kurulum",
    t.pgAdim4Kod || "Merkez Sunucu",
  ];
  // v2.4.67: adim 5 (kurulum kimligi) YALNIZ esitleme atlandiginda
  // gorunur. Kosulsuz eklenirse esitleme yapan kullanici hic
  // ulasmayacagi bir adim gorur ve akis yarim kalmis izlenimi verir.
  if (_pgD.adim === 5) adlar.push(t.pgAdim5 || "Giri\u015f");
  const sar = document.createElement("div");
  sar.className = "pgs-adimlar";
  for (let i = 0; i < adlar.length; i++) {
    const no = i + 1;
    const d = document.createElement("div");
    d.className = "pgs-adim" +
      (no === _pgD.adim ? " aktif" : "") +
      (no < _pgD.adim ? " bitti" : "");
    d.innerHTML =
      "<span class='pgs-adim-no'>" +
      (no < _pgD.adim ? "<i class='fa-solid fa-check'></i>" : no) +
      "</span><span class='pgs-adim-ad'>" + pgKacis(adlar[i]) + "</span>";
    sar.appendChild(d);
  }
  return sar;
}

// ---- ADIM 1: baglanti bilgileri ----
function pgAdim1Govde() {
  const t = pgT();
  const sar = document.createElement("div");
  sar.style.display = "flex";
  sar.style.flexDirection = "column";
  sar.style.gap = "13px";

  // Surucu yoksa kurulum imkansiz; kullaniciya komutu ver.
  if (_pgD.durum && _pgD.durum.surucu_var === false) {
    const u = document.createElement("div");
    u.className = "pgs-bilgi uyari";
    u.innerHTML = "<i class='fa-solid fa-triangle-exclamation'></i><span>" +
      pgKacis(t.pgSurucuYok ||
        "PostgreSQL s\u00fcr\u00fcc\u00fcs\u00fc (psycopg2) kurulu de\u011fil.") +
      "</span>";
    sar.appendChild(u);
  }

  const iz = document.createElement("div");
  iz.className = "pgs-izgara";
  iz.appendChild(pgAlanKur({
    ad: "sunucu", etiket: t.pgSunucu || "Sunucu adresi (IP)",
    deger: _pgD.bilgi.sunucu, zorunlu: true, genis: false,
    ipucu: t.pgSunucuIpucu || "",
  }));
  iz.appendChild(pgAlanKur({
    ad: "port", etiket: t.pgPort || "Port", tip: "number",
    deger: _pgD.bilgi.port, zorunlu: true,
  }));
  iz.appendChild(pgAlanKur({
    ad: "veritabani", etiket: t.pgVt || "Veritaban\u0131 ad\u0131",
    deger: _pgD.bilgi.veritabani, zorunlu: true, genis: true,
    ipucu: t.pgVtIpucu || "",
  }));
  iz.appendChild(pgAlanKur({
    ad: "kullanici", etiket: t.pgKullanici || "Kullan\u0131c\u0131 ad\u0131",
    deger: _pgD.bilgi.kullanici, zorunlu: true,
  }));
  iz.appendChild(pgAlanKur({
    ad: "sifre", etiket: t.pgSifre || "\u015eifre", tip: "password",
    deger: _pgD.bilgi.sifre,
  }));
  sar.appendChild(iz);

  if (_pgD.hata) sar.appendChild(pgHataKur(_pgD.hata));
  return sar;
}

function pgAlanKur(o) {
  const d = document.createElement("div");
  d.className = "pgs-alan" + (o.genis ? " genis" : "");
  const et = document.createElement("label");
  et.className = "pgs-etiket";
  et.innerHTML = pgKacis(o.etiket) +
    (o.zorunlu ? " <span class='pgs-yildiz'>*</span>" : "");
  const gr = document.createElement("input");
  gr.className = "pgs-giris";
  gr.type = o.tip || "text";
  gr.value = o.deger == null ? "" : String(o.deger);
  gr.id = "pgGiris_" + o.ad;
  gr.autocomplete = "off";
  // Her tuslamada durum nesnesine yaz: adim gecisinde DOM yeniden
  // uretildigi icin degeri DOM'da tutmak veri kaybina yol acardi.
  gr.addEventListener("input", () => {
    _pgD.bilgi[o.ad] = (o.tip === "number")
      ? (parseInt(gr.value, 10) || 0) : gr.value;
  });
  // Enter tusu "Ileri" ile aynidir (klavye ile hizli tamamlama).
  gr.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") { ev.preventDefault(); pgIleriBas(); }
  });
  d.appendChild(et);
  d.appendChild(gr);
  if (o.ipucu) {
    const ip = document.createElement("div");
    ip.className = "pgs-ipucu";
    ip.textContent = o.ipucu;
    d.appendChild(ip);
  }
  return d;
}

function pgHataKur(metin) {
  const d = document.createElement("div");
  d.className = "pgs-hata";
  d.innerHTML = "<i class='fa-solid fa-circle-exclamation'></i><span>" +
    pgKacis(metin) + "</span>";
  return d;
}

// ---- ADIM 2: dogrulama ozeti ----
function pgAdim2Govde() {
  const t = pgT();
  const dg = _pgD.dogrulama || {};
  const sar = document.createElement("div");
  sar.style.display = "flex";
  sar.style.flexDirection = "column";
  sar.style.gap = "13px";

  const iyi = document.createElement("div");
  iyi.className = "pgs-bilgi iyi";
  iyi.innerHTML = "<i class='fa-solid fa-circle-check'></i><span>" +
    pgKacis(t.pgBaglantiTamam || "Ba\u011flant\u0131 do\u011fruland\u0131.") +
    "</span>";
  sar.appendChild(iyi);

  const oz = document.createElement("div");
  oz.className = "pgs-ozet";
  const satirlar = [
    [t.pgSunucu || "Sunucu",
     _pgD.bilgi.sunucu + ":" + _pgD.bilgi.port, ""],
    [t.pgVt || "Veritaban\u0131", _pgD.bilgi.veritabani, ""],
    [t.pgKullanici || "Kullan\u0131c\u0131", _pgD.bilgi.kullanici, ""],
  ];
  if (dg.surum) satirlar.push([t.pgSurum || "S\u00fcr\u00fcm", dg.surum, ""]);
  if (dg.veritabani_var !== undefined) {
    satirlar.push([t.pgVt || "Veritaban\u0131",
      dg.veritabani_var ? (t.pgVtVar || "mevcut") : (t.pgYok || "yok"),
      dg.veritabani_var ? "f-iyi" : "f-kotu"]);
  }
  if (dg.tablo_sayisi !== undefined && dg.tablo_sayisi !== null) {
    satirlar.push([t.pgTabloSayisi || "Tablo say\u0131s\u0131",
                   String(dg.tablo_sayisi), ""]);
  }
  if (dg.citext !== undefined) {
    satirlar.push([t.pgCitext || "citext",
      dg.citext ? (t.pgVar || "var") : (t.pgYok || "yok"),
      dg.citext ? "f-iyi" : ""]);
  }
  const yetki = dg.yetki || {};
  const yAnahtar = Object.keys(yetki);
  if (yAnahtar.length) {
    satirlar.push([t.pgYetki || "Yetkiler",
      yAnahtar.map(a => a + ": " +
        (yetki[a] ? (t.pgVar || "var") : (t.pgYok || "yok"))).join(", "), ""]);
  }
  for (const s of satirlar) {
    const sd = document.createElement("div");
    sd.className = "pgs-ozet-satir";
    sd.innerHTML = "<span>" + pgKacis(s[0]) + "</span><span" +
      (s[2] ? " class='" + s[2] + "'" : "") + ">" +
      pgKacis(s[1]) + "</span>";
    oz.appendChild(sd);
  }
  sar.appendChild(oz);

  // Veritabani yoksa kullanici onu bu ekranda olusturur. Kurulumu
  // otomatik yapmiyoruz: veritabani olusturmak sunucu tarafinda
  // kalici bir degisikliktir, kullanici bilinerek onaylamali.
  if (dg.veritabani_var === false) {
    const uy = document.createElement("div");
    uy.className = "pgs-bilgi uyari";
    uy.innerHTML = "<i class='fa-solid fa-triangle-exclamation'></i><span>" +
      pgKacis(t.pgVtYok ||
        "Veritaban\u0131 bulunamad\u0131. Olu\u015fturmak i\u00e7in " +
        "a\u015fa\u011f\u0131daki d\u00fc\u011fmeye bas\u0131n.") + "</span>";
    sar.appendChild(uy);
  }
  if (_pgD.hata) sar.appendChild(pgHataKur(_pgD.hata));
  return sar;
}

// ---- ADIM 3: kurulum ilerlemesi ----
function pgAdim3Govde() {
  return pgIlerlemeGovde(false);
}

// ---- ADIM 4: MERKEZ KULLANICI ESITLEMESI (v2.4.66) ----
//
// OLCULEN KUSUR: kurulum bitince yerel `kullanicilar` tablosu bos
// kaliyor; GOKTUNGU kaynak koda GOMULU bir hesap yaratiyordu
// (`gokkubbe2026`). Musterinin merkezde tanimladigi sifre gecersiz,
// buna karsilik her kurulumda AYNI bilinen sifre gecerli oluyordu.
//
// Bu ekran merkezdeki gercek kullanici listesini bir kez ceker.
// ATLANABILIR: kullanicinin sarti geregi kapali devre kurulum da
// desteklenir (merkeze hic baglanmadan sisteme girilebilir).
function pgAdim4Govde() {
  const t = pgT();
  const sar = document.createElement("div");
  sar.style.display = "flex";
  sar.style.flexDirection = "column";
  sar.style.gap = "13px";

  // Eslesme tamamlandi: kurum ozeti goster.
  if (_pgD.kodSonuc) {
    const s = _pgD.kodSonuc;
    const iyi = document.createElement("div");
    iyi.className = "pgs-bilgi iyi";
    iyi.innerHTML = "<i class='fa-solid fa-circle-check'></i><span>" +
      pgKacis(t.pgKodTamam ||
        "Merkeze eşleşildi; kurum bilgileri ve logo alındı.") + "</span>";
    sar.appendChild(iyi);
    const oz = document.createElement("div");
    oz.className = "pgs-ozet";
    const satirlar = [
      [t.pgKodFirma || "Kurum", s.firma_unvan || "—"],
      [t.pgKodAd || "Kayıt adı", s.ad || "—"],
      [t.pgKodAdres2 || "Merkez", s.adres || "—"],
      [t.pgKodLogo || "Logo", s.logo_var ? (t.pgKodLogoVar || "alındı")
                                          : (t.pgKodLogoYok || "merkezde tanımlı değil")],
    ];
    for (const [k, v] of satirlar) {
      const d = document.createElement("div");
      d.className = "pgs-ozet-satir";
      d.innerHTML = "<span>" + pgKacis(k) + "</span><span>" + pgKacis(v) + "</span>";
      oz.appendChild(d);
    }
    sar.appendChild(oz);
    const n = document.createElement("div");
    n.className = "pgs-bilgi";
    n.innerHTML = "<i class='fa-solid fa-circle-info'></i><span>" +
      pgKacis(t.pgKodNot ||
        "Şirket bilgileri bir daha sorulmaz. İleri deyip bu kuruluma ait " +
        "yönetici hesabınızı belirleyin.") + "</span>";
    sar.appendChild(n);
    return sar;
  }

  const b = document.createElement("div");
  b.className = "pgs-bilgi";
  b.innerHTML = "<i class='fa-solid fa-key'></i><span>" +
    pgKacis(t.pgKodAciklama ||
      "Kurumsal panelde (goktungu.com) Merkezi Yazılımlar bölümünde " +
      "bu kurulum için oluşturulan kaydın API kodunu yapıştırın. " +
      "Kurum bilgileriniz ve logonuz merkezden bir kez alınır; " +
      "kullanıcı adı ve şifre girilmez.") + "</span>";
  sar.appendChild(b);

  const iz = document.createElement("div");
  iz.className = "pgs-izgara";
  iz.appendChild(pgKodAlanKur({
    ad: "adres", etiket: t.pgKodAdres || "Merkez sunucu adresi",
    deger: _pgD.kodBilgi.adres, genis: true,
    ipucu: t.pgKodAdresIpucu ||
      "örn. goktungu.com — boş bırakılırsa API kodundaki adres kullanılır",
  }));
  iz.appendChild(pgKodAlanKur({
    ad: "kod", etiket: t.pgKod || "API kodu", coklu: true,
    deger: _pgD.kodBilgi.kod, zorunlu: true, genis: true,
    ipucu: t.pgKodIpucu || "GTK1. ile başlar; Merkezi Yazılımlar > kayıt > Kopyala",
  }));
  sar.appendChild(iz);

  if (_pgD.hata) sar.appendChild(pgHataKur(_pgD.hata));
  return sar;
}

// Adim 4 alanlari (adres + kod). `coklu` cok satirli metin kutusu.
function pgKodAlanKur(o) {
  const d = document.createElement("div");
  d.className = "pgs-alan" + (o.genis ? " genis" : "");
  const et = document.createElement("label");
  et.className = "pgs-etiket";
  et.innerHTML = pgKacis(o.etiket) +
    (o.zorunlu ? " <span class='pgs-yildiz'>*</span>" : "");
  const gr = document.createElement(o.coklu ? "textarea" : "input");
  gr.className = "pgs-giris";
  if (o.coklu) { gr.rows = 4; gr.spellcheck = false; gr.style.fontFamily = "Consolas, monospace"; gr.style.resize = "vertical"; }
  else gr.type = "text";
  gr.value = o.deger == null ? "" : String(o.deger);
  gr.id = "pgKod_" + o.ad;
  gr.autocomplete = "off";
  gr.addEventListener("input", () => { _pgD.kodBilgi[o.ad] = gr.value; });
  if (!o.coklu) {
    gr.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") { ev.preventDefault(); pgKodBaslat(); }
    });
  }
  d.appendChild(et);
  d.appendChild(gr);
  if (o.ipucu) {
    const ip = document.createElement("div");
    ip.className = "pgs-ipucu";
    ip.textContent = o.ipucu;
    d.appendChild(ip);
  }
  return d;
}

function pgKodBaslat() {
  if (_pgD.bekliyor) return;
  for (const ad of ["adres", "kod"]) {
    const g = document.getElementById("pgKod_" + ad);
    if (g) _pgD.kodBilgi[ad] = g.value;
  }
  const t = pgT();
  const kod = String(_pgD.kodBilgi.kod || "").replace(/\s+/g, "");
  if (!kod) {
    _pgD.hata = (t.pgHata || "Hata") + ": " + (t.pgKod || "API kodu");
    pgCiz();
    return;
  }
  _pgD.hata = "";
  _pgD.bekliyor = true;
  _pgD.gonderilen = "pg_merkez_kod";
  pgCiz();
  if (!pgGonder({ tip: "pg_merkez_kod", adres: String(_pgD.kodBilgi.adres || "").trim(),
                  kod: kod })) pgBaglantiYok();
  else pgKisaBekci("pg_merkez_kod");
}

// ---- ADIM 5: KURULUM KIMLIGI (v2.4.67) ----
//
// OLCULEN KUSUR (kullanici bildirimi: "merkez yazilimina hic bir sifre
// ile giremiyorum"): esitleme ATLANDIGINDA sihirbaz dogrudan kapaniyordu.
// `kullanicilar._ilk_yonetici_guvence()` yerel tablo bosken
// `kurulum@yerel` hesabini RASTGELE sifreyle acar ve sifreyi yalniz
// konsola + `<VERI_KOKU>/ilk_giris.txt`e yazar. Merkez Uygulama SERVIS
// olarak kuruldugu icin kullanici konsolu hic gormez -> sisteme giris
// imkansiz hale gelir.
//
// Bu adim kimligi EKRANDA gosterir. Sabit/gomulu sifreye DONMEZ
// (v2.4.66'da kaldirilan `gokkubbe2026` guvenlik kusuruydu).
function pgAdim5Govde() {
  const t = pgT();
  const sar = document.createElement("div");
  sar.style.display = "flex";
  sar.style.flexDirection = "column";
  sar.style.gap = "13px";

  // v2.4.68 — KULLANICI KENDİ HESABINI BELİRLER
  //
  // v2.4.67 bu adimda RASTGELE uretilmis bir sifre GOSTERIYORDU.
  // Sahada yetmedi; kullanicinin bildirimi (birebir):
  //   "hala merkez yazilima kendi sifremle giremiyorum, en azindan
  //    sihirbazda bana sorsun kullanici adi sifreyi, merkezden
  //    bagimsiz olarak"
  // Artik kullanici e-postasini ve sifresini KENDISI yaziyor. Merkeze
  // hic baglanmadan calisir — kapali devre kurulumun sarti budur.
  const b = document.createElement("div");
  b.className = "pgs-bilgi";
  b.innerHTML = "<i class='fa-solid fa-user-shield'></i><span>" +
    pgKacis(t.pgYonAciklama ||
      "Bu kuruluma ait yönetici hesabınızı belirleyin. " +
      "Bu hesap yereldir; merkeze bağlantı gerektirmez ve " +
      "kapalı devre kullanımda da geçerlidir.") + "</span>";
  sar.appendChild(b);

  const iz = document.createElement("div");
  iz.className = "pgs-izgara";
  iz.appendChild(pgYonAlanKur({
    ad: "eposta", etiket: t.pgYonEposta || "E-posta",
    tip: "email", zorunlu: true,
    deger: _pgD.yonBilgi.eposta,
    ipucu: t.pgYonEpostaIpucu || "Girişte kullanacağınız adres.",
  }));
  iz.appendChild(pgYonAlanKur({
    ad: "ad_soyad", etiket: t.pgYonAdSoyad || "Ad Soyad",
    deger: _pgD.yonBilgi.ad_soyad,
    ipucu: t.pgYonAdIpucu || "Raporlarda görünecek ad.",
  }));
  iz.appendChild(pgYonAlanKur({
    ad: "sifre", etiket: t.pgYonSifre || "Şifre",
    tip: "password", zorunlu: true,
    deger: _pgD.yonBilgi.sifre,
    ipucu: t.pgYonSifreIpucu || "En az 8 karakter.",
  }));
  iz.appendChild(pgYonAlanKur({
    ad: "sifre2", etiket: t.pgYonSifre2 || "Şifre (tekrar)",
    tip: "password", zorunlu: true,
    deger: _pgD.yonBilgi.sifre2,
    ipucu: t.pgYonSifre2Ipucu || "Aynı şifreyi tekrar yazın.",
  }));
  sar.appendChild(iz);

  if (_pgD.yonSonuc && _pgD.yonSonuc.basarili) {
    const o = document.createElement("div");
    o.className = "pgs-bilgi iyi";
    o.innerHTML = "<i class='fa-solid fa-circle-check'></i><span>" +
      pgKacis((_pgD.yonSonuc.degistirildi
        ? (t.pgYonGuncellendi || "Hesap güncellendi:")
        : (t.pgYonOlusturuldu || "Hesap oluşturuldu:")) + " " +
        _pgD.yonSonuc.eposta) + "</span>";
    sar.appendChild(o);
  }

  const g = document.createElement("div");
  g.className = "pgs-bilgi";
  g.innerHTML = "<i class='fa-solid fa-circle-info'></i><span>" +
    pgKacis(t.pgKimlikSonra ||
      "Merkez lisansınızı sonradan bağlamak isterseniz, " +
      "Kullanıcılar bölümünden merkez kullanıcılarını " +
      "aktarabilirsiniz.") + "</span>";
  sar.appendChild(g);

  return sar;
}

// Adim 5 alanlari AYRI nesneye yazar (`yonBilgi`).
// `pgAlanKur` degerleri `_pgD.bilgi`ye yazar ve Enter'da `pgIleriBas()`
// cagirir; ayni yardimci kullanilsa veritabani baglanti bilgilerinin
// uzerine yazardi (adim 4'te olculen ayni tuzak).
function pgYonAlanKur(o) {
  const d = document.createElement("div");
  d.className = "pgs-alan" + (o.genis ? " genis" : "");
  const et = document.createElement("label");
  et.className = "pgs-etiket";
  et.innerHTML = pgKacis(o.etiket) +
    (o.zorunlu ? " <span class='pgs-yildiz'>*</span>" : "");
  const gr = document.createElement("input");
  gr.className = "pgs-giris";
  gr.type = o.tip || "text";
  gr.value = o.deger == null ? "" : String(o.deger);
  gr.id = "pgYon_" + o.ad;
  // Tarayici kayitli sifreleri BU forma doldurmasin: kullanici farkinda
  // olmadan baska bir sifreyle hesap acar ve giremezdi.
  gr.autocomplete = "new-password";
  gr.addEventListener("input", () => {
    _pgD.yonBilgi[o.ad] = gr.value;
  });
  gr.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") { ev.preventDefault(); pgYoneticiKur(); }
  });
  d.appendChild(et);
  d.appendChild(gr);
  if (o.ipucu) {
    const ip = document.createElement("div");
    ip.className = "pgs-ipucu";
    ip.textContent = o.ipucu;
    d.appendChild(ip);
  }
  return d;
}

// Adim 5: yonetici hesabini kurar. Sunucu tarafi son savunma hatti;
// buradaki denetimler kullaniciya HIZLI geri bildirim icindir.
function pgYoneticiKur() {
  const t = pgT();
  const b = _pgD.yonBilgi;
  const eposta = String(b.eposta || "").trim();
  const sifre = String(b.sifre || "");
  const sifre2 = String(b.sifre2 || "");

  if (!eposta || eposta.indexOf("@") < 0) {
    _pgD.hata = t.pgYonHataEposta || "Geçerli bir e-posta adresi girin.";
    pgCiz();
    return;
  }
  if (sifre.length < 8) {
    _pgD.hata = t.pgYonHataKisa || "Şifre en az 8 karakter olmalıdır.";
    pgCiz();
    return;
  }
  if (sifre !== sifre2) {
    _pgD.hata = t.pgYonHataUyusmaz || "Şifreler birbiriyle uyuşmuyor.";
    pgCiz();
    return;
  }

  _pgD.hata = "";
  _pgD.yonYurutuluyor = true;
  pgCiz();

  // `pgGonder` baglanti kapaliysa false doner. KONTROL ZORUNLU:
  // aksi halde dugme sonsuza kadar "Olusturuluyor..." kalir ve
  // kullanici neden ilerlemedigini anlamaz.
  if (!pgGonder({
    tip: "yonetici_kur",
    eposta: eposta,
    sifre: sifre,
    ad_soyad: String(b.ad_soyad || "").trim(),
  })) {
    _pgD.yonYurutuluyor = false;
    _pgD.hata = t.pgYonHataBaglanti ||
      "Sunucu bağlantısı yok. Sayfayı yenileyip tekrar deneyin.";
    pgCiz();
  }
}

// Sunucu yaniti (`yonetici_kur_sonuc`).
function pgYoneticiKurSonuc(m) {
  _pgD.yonYurutuluyor = false;
  if (!m || !m.basarili) {
    _pgD.hata = (m && m.hata) ||
      (pgT().pgYonHataGenel || "Hesap oluşturulamadı.");
    pgCiz();
    return;
  }
  _pgD.hata = "";
  _pgD.yonSonuc = {
    basarili: true, eposta: m.eposta,
    degistirildi: !!m.degistirildi,
  };
  // Sifreleri bellekte TUTMUYORUZ: is bitti, ekranda da kalmasinlar.
  _pgD.yonBilgi.sifre = "";
  _pgD.yonBilgi.sifre2 = "";
  pgCiz();
  // Kullanici artik giris yapabilir; sihirbaz kapanip giris ekrani
  // gelsin. Kisa gecikme onay iletisinin okunmasi icindir.
  setTimeout(() => { pgSihirbazKapat(); }, 1400);
}
// ZORUNLU: `ws.js` yonlendiricisi `window.pgYoneticiKurSonuc` arar.
// Bu atama olmadan sunucu yaniti gelse bile arayuz TEPKI VERMEZ ve
// dugme sonsuza kadar "Olusturuluyor..." kalir (olculdu).
window.pgYoneticiKurSonuc = pgYoneticiKurSonuc;

// Atla dugmesi: kimligi goster (sihirbazi KAPATMAZ).
function pgKurulumKimligiGoster() {
  _pgD.esitlemeAtlandi = true;
  _pgD.hata = "";
  _pgD.adim = 5;
  pgCiz();
}

// Adim 4 alanlari AYRI nesneye yazar (`esitlemeBilgi`).
// NEDEN AYRI YARDIMCI: `pgAlanKur` degerleri `_pgD.bilgi`ye yazar ve
// Enter tusunda `pgIleriBas()` cagirir. Ayni yardimci kullanilsaydi
// veritabani baglanti bilgilerinin UZERINE yazardi.
function pgEsitlemeAlanKur(o) {
  const d = document.createElement("div");
  d.className = "pgs-alan" + (o.genis ? " genis" : "");
  const et = document.createElement("label");
  et.className = "pgs-etiket";
  et.innerHTML = pgKacis(o.etiket) +
    (o.zorunlu ? " <span class='pgs-yildiz'>*</span>" : "");
  const gr = document.createElement("input");
  gr.className = "pgs-giris";
  gr.type = o.tip || "text";
  gr.value = o.deger == null ? "" : String(o.deger);
  gr.id = "pgEsitleme_" + o.ad;
  gr.autocomplete = "off";
  gr.addEventListener("input", () => {
    _pgD.esitlemeBilgi[o.ad] = gr.value;
  });
  gr.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") { ev.preventDefault(); pgEsitlemeBaslat(); }
  });
  d.appendChild(et);
  d.appendChild(gr);
  if (o.ipucu) {
    const ip = document.createElement("div");
    ip.className = "pgs-ipucu";
    ip.textContent = o.ipucu;
    d.appendChild(ip);
  }
  return d;
}

// ---- GOC EKRANI (tek adim) ----
function pgGocGovde() {
  const t = pgT();
  const d = _pgD.durum || {};
  const sar = document.createElement("div");
  sar.style.display = "flex";
  sar.style.flexDirection = "column";
  sar.style.gap = "13px";

  if (!_pgD.adimlar.length && !_pgD.bekliyor && !_pgD.bitti) {
    // Henuz baslamadi: neyin degisecegini goster.
    const b = document.createElement("div");
    b.className = "pgs-bilgi";
    b.innerHTML = "<i class='fa-solid fa-circle-info'></i><span>" +
      pgKacis((t.pgGocGerekli || "\u015eema g\u00fcncellemesi gerekiyor") +
        " (v" + (d.sema_surum || 0) + " \u2192 v" +
        (d.hedef_surum || 0) + ")") + "</span>";
    sar.appendChild(b);
    const bekleyen = d.bekleyen || [];
    if (bekleyen.length) {
      const oz = document.createElement("div");
      oz.className = "pgs-ozet";
      const bas = document.createElement("div");
      bas.className = "pgs-ozet-satir";
      bas.innerHTML = "<span>" +
        pgKacis(t.pgGocBekleyen || "Bekleyen ad\u0131mlar") +
        "</span><span>" + bekleyen.length + "</span>";
      oz.appendChild(bas);
      for (const a of bekleyen) {
        const sd = document.createElement("div");
        sd.className = "pgs-ozet-satir";
        sd.innerHTML = "<span>v" + pgKacis(a.surum != null ? a.surum : "") +
          "</span><span>" + pgKacis(a.ad || a.aciklama || "") + "</span>";
        oz.appendChild(sd);
      }
      sar.appendChild(oz);
    }
    if (_pgD.hata) sar.appendChild(pgHataKur(_pgD.hata));
    return sar;
  }
  sar.appendChild(pgIlerlemeGovde(true));
  return sar;
}

// Ortak ilerleme govdesi: cubuk + ileti + adim gunlugu.
function pgIlerlemeGovde(goc) {
  const t = pgT();
  const sar = document.createElement("div");
  sar.className = "pgs-ilerleme";

  const ust = document.createElement("div");
  ust.className = "pgs-ilerleme-ust";
  const ileti = _pgD.ileti ||
    (_pgD.bekliyor
      ? (goc ? (t.pgGocSuruyor || "G\u00fcncelleme s\u00fcr\u00fcyor...")
             : (t.pgKuruluyor || "Kurulum s\u00fcr\u00fcyor..."))
      : (_pgD.bitti
          ? (goc ? (t.pgGocTamamlandi || "Tamamland\u0131.")
                 : (t.pgKurulumTamam || "Tamamland\u0131."))
          : ""));
  ust.innerHTML =
    "<span class='pgs-ilerleme-ileti'>" + pgKacis(ileti) + "</span>" +
    "<span class='pgs-ilerleme-yuzde'>" + (_pgD.yuzde | 0) + "%</span>";
  sar.appendChild(ust);

  const cub = document.createElement("div");
  cub.className = "pgs-ilerleme-cubuk";
  const dol = document.createElement("div");
  dol.className = "pgs-ilerleme-dolgu" +
    (_pgD.hata ? " hata" : (_pgD.bitti ? " bitti" : ""));
  dol.id = "pgIlerlemeDolgu";
  dol.style.width = (_pgD.yuzde | 0) + "%";
  cub.appendChild(dol);
  sar.appendChild(cub);

  // Adim gunlugu: hangi adimin tamamlandigi gorulur.
  if (_pgD.adimlar.length) {
    const g = document.createElement("div");
    g.className = "pgs-gunluk";
    g.id = "pgGunluk";
    for (const s of _pgD.adimlar) g.appendChild(pgGunlukSatir(s));
    sar.appendChild(g);
  }
  if (_pgD.hata) sar.appendChild(pgHataKur(_pgD.hata));
  if (_pgD.bitti && !_pgD.hata) {
    const iyi = document.createElement("div");
    iyi.className = "pgs-bilgi iyi";
    const sSurum = (_pgD.semaSurum != null)
      ? " (" + (t.pgSemaSurum || "\u015eema") + " v" + _pgD.semaSurum + ")"
      : "";
    iyi.innerHTML = "<i class='fa-solid fa-circle-check'></i><span>" +
      pgKacis((goc ? (t.pgGocTamamlandi ||
                      "Veritaban\u0131 g\u00fcncellemesi tamamland\u0131.")
                   : (t.pgKurulumTamam ||
                      "Veritaban\u0131 kurulumu tamamland\u0131.")) + sSurum) +
      "</span>";
    sar.appendChild(iyi);
  }
  return sar;
}

function pgGunlukSatir(s) {
  const d = document.createElement("div");
  d.className = "pgs-gunluk-satir" + (s.hata ? " hata" : " tamam");
  d.innerHTML = "<i class='fa-solid " +
    (s.hata ? "fa-circle-xmark" : "fa-circle-check") + "'></i><span>" +
    pgKacis(s.metin) + "</span>";
  return d;
}

// ---- ALT BAR ----
function pgAltBarKur() {
  const t = pgT();
  const alt = document.createElement("div");
  alt.className = "pgs-alt";
  const goc = _pgD.kip === "goc";

  function btn(metin, ikon, birincil, tiklama, kapali) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "pgs-btn" + (birincil ? "" : " pgs-btn-ikincil");
    b.innerHTML = "<i class='fa-solid " + ikon + "'></i> " + "<span>" + ( pgKacis(metin)) + "</span>";
    b.disabled = !!kapali;
    b.addEventListener("click", tiklama);
    return b;
  }

  if (goc) {
    if (_pgD.bitti && !_pgD.hata) {
      alt.appendChild(btn(t.pgGiris || "Sisteme Gir", "fa-right-to-bracket",
        true, () => pgSihirbazKapat()));
    } else {
      alt.appendChild(btn(
        _pgD.bekliyor ? (t.pgGocSuruyor || "S\u00fcr\u00fcyor...")
                      : (t.pgGocBaslat || "G\u00fcncellemeyi Ba\u015flat"),
        _pgD.bekliyor ? "fa-spinner" : "fa-play",
        true, () => pgGocBaslat(), _pgD.bekliyor));
    }
    return alt;
  }

  if (_pgD.adim === 1) {
    alt.appendChild(btn(
      _pgD.bekliyor ? (t.pgDeniyor || "Do\u011frulan\u0131yor...")
                    : (t.pgIleri || "\u0130leri"),
      _pgD.bekliyor ? "fa-spinner" : "fa-arrow-right",
      true, () => pgIleriBas(), _pgD.bekliyor));
    return alt;
  }

  if (_pgD.adim === 2) {
    alt.className = "pgs-alt ayrik";
    alt.appendChild(btn(t.pgGeri || "Geri", "fa-arrow-left", false,
      () => { _pgD.adim = 1; _pgD.hata = ""; pgCiz(); }, _pgD.bekliyor));
    const sag = document.createElement("div");
    sag.style.display = "flex";
    sag.style.gap = "9px";
    const dg = _pgD.dogrulama || {};
    if (dg.veritabani_var === false) {
      sag.appendChild(btn(
        _pgD.bekliyor ? (t.pgOlusturuluyor || "Olu\u015fturuluyor...")
                      : (t.pgOlustur || "Veritaban\u0131n\u0131 Olu\u015ftur"),
        _pgD.bekliyor ? "fa-spinner" : "fa-plus",
        true, () => pgVeritabaniOlustur(), _pgD.bekliyor));
    } else {
      sag.appendChild(btn(
        _pgD.bekliyor ? (t.pgKuruluyor || "S\u00fcr\u00fcyor...")
                      : (t.pgKur || "Kurulumu Ba\u015flat"),
        _pgD.bekliyor ? "fa-spinner" : "fa-play",
        true, () => pgKurBaslat(), _pgD.bekliyor));
    }
    alt.appendChild(sag);
    return alt;
  }

  // ---- ADIM 5: yonetici hesabi (v2.4.68) ----
  if (_pgD.adim === 5) {
    alt.className = "pgs-alt ayrik";
    // Geri: kullanici fikrini degistirip esitleme yapabilmeli.
    alt.appendChild(btn(t.pgKimlikGeriKod || "Merkez Sunucu",
      "fa-arrow-left", false, () => {
        _pgD.adim = 4; _pgD.hata = ""; _pgD.yonSonuc = null; pgCiz();
      }, _pgD.yonYurutuluyor));
    // Hesap KURULDUKTAN sonra dugme "Sisteme Gir"e doner: kullanici
    // ayni hesabi iki kez olusturmaya calismasin.
    if (_pgD.yonSonuc && _pgD.yonSonuc.basarili) {
      alt.appendChild(btn(t.pgGiris || "Sisteme Gir", "fa-right-to-bracket",
        true, () => pgSihirbazKapat()));
    } else {
      alt.appendChild(btn(
        _pgD.yonYurutuluyor ? (t.pgYonKuruluyor || "Oluşturuluyor...")
                            : (t.pgYonKur || "Hesabı Oluştur"),
        _pgD.yonYurutuluyor ? "fa-spinner" : "fa-user-plus",
        true, () => pgYoneticiKur(), _pgD.yonYurutuluyor));
    }
    return alt;
  }

  // ---- ADIM 4: merkez kullanici esitlemesi (v2.4.66) ----
  if (_pgD.adim === 4) {
    if (_pgD.kodSonuc) {
      // 2.4.233: eslesme tamam -> yonetici hesabi adimina gecilir.
      alt.appendChild(btn(t.pgIleri || "\u0130leri", "fa-arrow-right",
        true, () => { _pgD.adim = 5; _pgD.hata = ""; pgCiz(); }));
      return alt;
    }
    alt.className = "pgs-alt ayrik";
    // ATLA: kapali devre kurulum kullanicinin acik sartidir.
    //
    // v2.4.67 OLCULEN KUSUR: Atla dogrudan sihirbazi kapatiyordu.
    // Yerel tabloda yalnizca `kurulum@yerel` + RASTGELE sifre kalir;
    // sifre sadece konsola/`ilk_giris.txt`e yazilir. Servis olarak
    // kurulunca konsol gorunmez -> kullanici sisteme HIC giremez
    // ("hic bir sifre ile giremiyorum"). Artik Atla kimligi GOSTERIR.
    alt.appendChild(btn(t.pgEsitlemeAtla || "Atla", "fa-forward", false,
      () => pgKurulumKimligiGoster(), _pgD.bekliyor));
    alt.appendChild(btn(
      _pgD.bekliyor ? (t.pgKodBaglaniyor || "Merkeze ba\u011flan\u0131l\u0131yor...")
                    : (t.pgKodBaglan || "Merkeze Ba\u011flan"),
      _pgD.bekliyor ? "fa-spinner" : "fa-cloud-arrow-down",
      true, () => pgKodBaslat(), _pgD.bekliyor));
    return alt;
  }

  // Adim 3
  if (_pgD.bitti && !_pgD.hata) {
    // v2.4.66: kurulum bitti. DOGRUDAN "Sisteme Gir" YETMEZ; yerel
    // kullanici tablosu bostur ve eskiden gomulu `gokkubbe2026` hesabi
    // devreye giriyordu. Kullaniciyi adim 4'e yonlendiriyoruz.
    alt.className = "pgs-alt ayrik";
    alt.appendChild(btn(t.pgEsitlemeAtla || "Atla", "fa-forward", false,
      () => pgKurulumKimligiGoster()));
    alt.appendChild(btn(
      t.pgKodGec || "Merkez Sunucu ve API Kodu",
      "fa-arrow-right", true, () => {
        _pgD.adim = 4; _pgD.hata = ""; pgCiz();
      }));
  } else if (_pgD.hata) {
    alt.appendChild(btn(t.pgYeniden || "Bilgileri D\u00fczenle",
      "fa-pen", false, () => {
        _pgD.adim = 1; _pgD.hata = ""; _pgD.yuzde = 0;
        _pgD.adimlar = []; _pgD.ileti = ""; pgCiz();
      }));
    alt.appendChild(btn(t.pgKur || "Yeniden Dene", "fa-rotate-right",
      true, () => pgKurBaslat()));
  } else {
    alt.appendChild(btn(t.pgKuruluyor || "S\u00fcr\u00fcyor...", "fa-spinner",
      true, () => {}, true));
  }
  return alt;
}

// ---------------------------------------------------------------
// EYLEMLER
// ---------------------------------------------------------------
function pgFormOku() {
  // DOM'dan tazele (tarayici otomatik doldurma "input" olayi
  // uretmeyebilir; bu durumda durum nesnesi bos kalirdi).
  for (const ad of ["sunucu", "port", "veritabani", "kullanici", "sifre"]) {
    const g = document.getElementById("pgGiris_" + ad);
    if (!g) continue;
    _pgD.bilgi[ad] = (ad === "port")
      ? (parseInt(g.value, 10) || 0) : g.value;
  }
}

function pgIleriBas() {
  if (_pgD.bekliyor) return;
  if (_pgD.kip === "goc") { pgGocBaslat(); return; }
  if (_pgD.adim !== 1) return;
  pgFormOku();
  const t = pgT();
  const eksik = ["sunucu", "veritabani", "kullanici"]
    .filter(a => !String(_pgD.bilgi[a] || "").trim());
  if (eksik.length) {
    _pgD.hata = (t.pgHata || "Hata") + ": " +
      eksik.map(a => ({
        sunucu: t.pgSunucu, veritabani: t.pgVt, kullanici: t.pgKullanici
      })[a] || a).join(", ");
    pgCiz();
    return;
  }
  _pgD.hata = "";
  _pgD.bekliyor = true;
  _pgD.gonderilen = "pg_dene";
  pgCiz();
  if (!pgGonder(Object.assign({ tip: "pg_dene" }, _pgD.bilgi)))
    pgBaglantiYok();
  else pgKisaBekci("pg_dene");
}
// v2.4.197: dogrulama/olusturma 30 sn icinde yanitlanmazsa dugme sonsuza
// kadar donmez: bekleme kaldirilir, neden yazilir, kullanici yeniden
// deneyebilir. (Olculen kusur: "Baglanti dogrulaniyor..." asamasinda
// kilitlenme.)
function pgKisaBekci(komut) {
  if (_pgD._kisaBekci) clearTimeout(_pgD._kisaBekci);
  _pgD._kisaBekci = setTimeout(function () {
    _pgD._kisaBekci = null;
    if (!_pgD.bekliyor || _pgD.gonderilen !== komut) return;
    _pgD.bekliyor = false;
    _pgD.hata = (pgT().pgYanitYok ||
      "Sunucu 30 saniye i\u00e7inde yan\u0131t vermedi. Sunucu g\u00fcnl\u00fc\u011f\u00fcn\u00fc (servis.log) kontrol edin ve yeniden deneyin.");
    pgCiz();
  }, 30000);
}

function pgVeritabaniOlustur() {
  if (_pgD.bekliyor) return;
  _pgD.hata = "";
  _pgD.bekliyor = true;
  _pgD.gonderilen = "pg_olustur";
  pgCiz();
  if (!pgGonder(Object.assign({ tip: "pg_olustur" }, _pgD.bilgi)))
    pgBaglantiYok();
  else pgKisaBekci("pg_olustur");
}

// v2.4.196: BEKCI — kur/goc gonderildikten sonra ne ilerleme ne sonuc
// gelirse (baglanti kopmasi, yanit kaybi) 45 sn'de bir durum sorulur;
// pgDurumGeldi kurulumun bitip bitmedigine karar verir. Sonsuz donen
// dugme yerine en kotu durumda 45 sn gecikmeli sonuc gorulur.
function pgBekciKur() {
  if (_pgD._bekci) clearInterval(_pgD._bekci);
  _pgD._bekciSon = Date.now();
  _pgD._bekci = setInterval(function () {
    if (!_pgD.bekliyor || !_pgD.perde) { clearInterval(_pgD._bekci); _pgD._bekci = null; return; }
    if (Date.now() - _pgD._bekciSon < 45000) return;
    _pgD._bekciSon = Date.now();
    _pgD.ileti = (pgT().pgYanitBekleniyor || "Sunucudan yan\u0131t bekleniyor; durum yeniden sorgulan\u0131yor...");
    pgCiz();
    pgGonder({ tip: "pg_durum" });
  }, 5000);
}
function pgKurBaslat() {
  if (_pgD.bekliyor) return;
  _pgD.hata = "";
  _pgD.adim = 3;
  _pgD.adimlar = [];
  _pgD.yuzde = 0;
  _pgD.ileti = pgT().pgKuruluyor || "Kurulum s\u00fcr\u00fcyor...";
  _pgD.bitti = false;
  _pgD.bekliyor = true;
  _pgD.gonderilen = "pg_kur";
  pgCiz();
  if (!pgGonder(Object.assign({ tip: "pg_kur" }, _pgD.bilgi)))
    pgBaglantiYok();
  else pgBekciKur();
}

function pgGocBaslat() {
  if (_pgD.bekliyor) return;
  _pgD.hata = "";
  _pgD.adimlar = [];
  _pgD.yuzde = 0;
  _pgD.ileti = pgT().pgGocSuruyor || "G\u00fcncelleme s\u00fcr\u00fcyor...";
  _pgD.bitti = false;
  _pgD.bekliyor = true;
  _pgD.gonderilen = "pg_goc";
  pgCiz();
  if (!pgGonder({ tip: "pg_goc" })) pgBaglantiYok();
  else pgBekciKur();
}

// v2.4.66: merkez kullanici esitlemesini baslat.
function pgEsitlemeBaslat() {
  if (_pgD.bekliyor) return;
  // DOM'dan tazele (otomatik doldurma "input" olayi uretmeyebilir).
  for (const ad of ["adres", "eposta", "sifre"]) {
    const g = document.getElementById("pgEsitleme_" + ad);
    if (g) _pgD.esitlemeBilgi[ad] = g.value;
  }
  const t = pgT();
  const eksik = ["adres", "eposta", "sifre"]
    .filter(a => !String(_pgD.esitlemeBilgi[a] || "").trim());
  if (eksik.length) {
    _pgD.hata = (t.pgHata || "Hata") + ": " +
      eksik.map(a => ({
        adres: t.pgEsitlemeAdres || "Merkez sunucu adresi",
        eposta: t.pgEsitlemeEposta || "Y\u00f6netici e-postas\u0131",
        sifre: t.pgEsitlemeSifre || "\u015eifre",
      })[a] || a).join(", ");
    pgCiz();
    return;
  }
  _pgD.hata = "";
  _pgD.bekliyor = true;
  _pgD.gonderilen = "merkez_esitle";
  pgCiz();
  if (!pgGonder({
    tip: "merkez_esitle",
    adres: _pgD.esitlemeBilgi.adres,
    eposta: _pgD.esitlemeBilgi.eposta,
    sifre: _pgD.esitlemeBilgi.sifre,
  })) pgBaglantiYok();
}

function pgBaglantiYok() {
  _pgD.bekliyor = false;
  _pgD.hata = (pgT().girisHataSunucu ||
    "Sunucu ba\u011flant\u0131s\u0131 yok. L\u00fctfen bekleyin...");
  pgCiz();
}

// ---------------------------------------------------------------
// SUNUCU YANITLARI
// ---------------------------------------------------------------
window.pgIlerlemeGeldi = function (m) {
  _pgD._bekciSon = Date.now();
  if (!_pgD.perde) return;
  const y = Math.max(0, Math.min(100, parseInt(m.yuzde, 10) || 0));
  _pgD.yuzde = y;
  _pgD.ileti = m.ileti || "";
  if (m.ileti) {
    // Ayni ileti tekrar gelirse gunluge iki kez yazma.
    const son = _pgD.adimlar[_pgD.adimlar.length - 1];
    if (!son || son.metin !== m.ileti)
      _pgD.adimlar.push({ metin: m.ileti, hata: false });
  }
  // Tam yeniden cizim yerine noktasal guncelleme: gunlukteki kaydirma
  // konumu korunur ve cubuk gecisi kesintiye ugramaz.
  const dol = document.getElementById("pgIlerlemeDolgu");
  const kutu = _pgD.perde.querySelector(".pgs-ilerleme-ileti");
  const yz = _pgD.perde.querySelector(".pgs-ilerleme-yuzde");
  const gun = document.getElementById("pgGunluk");
  if (dol && kutu && yz) {
    dol.style.width = y + "%";
    kutu.textContent = _pgD.ileti;
    yz.textContent = y + "%";
    if (gun && _pgD.adimlar.length) {
      const son = _pgD.adimlar[_pgD.adimlar.length - 1];
      if (gun.childElementCount < _pgD.adimlar.length) {
        gun.appendChild(pgGunlukSatir(son));
        gun.scrollTop = gun.scrollHeight;
      }
    } else if (!gun) {
      pgCiz();
    }
  } else {
    pgCiz();
  }
};

window.pgSonucGeldi = function (m) {
  if (!_pgD.perde) return;
  const komut = m.komut || _pgD.gonderilen;
  _pgD.bekliyor = false;

  // 2.4.233: merkez sunucu + API kodu yaniti.
  if (m.tip === "pg_merkez_kod_sonuc" || komut === "pg_merkez_kod") {
    if (m.basarili) {
      _pgD.hata = "";
      _pgD.kodSonuc = {
        firma_unvan: m.firma_unvan || "", logo_var: !!m.logo_var,
        ad: m.ad || "", adres: m.adres || "",
      };
      _pgD.kodBilgi.kod = "";
    } else {
      _pgD.hata = m.hata || (pgT().pgHata || "Hata");
    }
    _pgD.adim = 4;
    pgCiz();
    return;
  }

  // v2.4.66: merkez kullanici esitlemesi yaniti.
  if (komut === "merkez_esitle" || m.tip === "merkez_esitle_sonuc") {
    if (m.basarili) {
      _pgD.hata = "";
      _pgD.esitlemeSonuc = {
        cekilen: m.cekilen || 0,
        eklendi: m.eklendi || 0,
        guncellendi: m.guncellendi || 0,
        firma_unvan: m.firma_unvan || "",
      };
    } else {
      _pgD.hata = m.hata || (pgT().pgHata || "Hata");
    }
    _pgD.adim = 4;
    pgCiz();
    return;
  }

  if (komut === "pg_dene") {
    _pgD.dogrulama = m;
    if (m.basarili) {
      _pgD.hata = "";
      _pgD.adim = 2;
    } else {
      _pgD.hata = m.hata || (pgT().pgHata || "Hata");
      _pgD.adim = 1;
    }
    pgCiz();
    return;
  }

  if (komut === "pg_olustur") {
    if (m.basarili) {
      _pgD.hata = "";
      // Veritabani olusturuldu: dogrulamayi tazele ki adim 2 "mevcut"
      // gostersin ve kurulum dugmesi ortaya cikssin.
      _pgD.bekliyor = true;
      _pgD.gonderilen = "pg_dene";
      pgCiz();
      pgGonder(Object.assign({ tip: "pg_dene" }, _pgD.bilgi));
    } else {
      _pgD.hata = m.hata || (pgT().pgHata || "Hata");
      pgCiz();
    }
    return;
  }

  // pg_kur / pg_goc
  _pgD.semaSurum = m.sema_surum;
  const adimlar = m.adimlar || [];
  for (const a of adimlar) {
    const metin = (typeof a === "string") ? a
      : (a.ad || a.aciklama || JSON.stringify(a));
    const son = _pgD.adimlar[_pgD.adimlar.length - 1];
    if (!son || son.metin !== metin)
      _pgD.adimlar.push({ metin: metin, hata: false });
  }
  if (m.basarili) {
    _pgD.bitti = true;
    _pgD.hata = "";
    _pgD.yuzde = 100;
    // v2.4.67: sunucu `kurulum_hesabi` dondurur (eposta/sifre/dosya).
    // Esitleme atlanirsa adim 5 bunu ekranda gosterir; aksi halde
    // kullanici sisteme hic giremez (bkz. pgAdim5Govde aciklamasi).
    if (m.kurulum_hesabi) _pgD.kurulumHesabi = m.kurulum_hesabi;
    // Kurulum bittikten sonra durumu tazele: goc gerekli kalmis
    // olabilir (kurulum sirasinda yeni adim eklenmis olabilir).
    setTimeout(() => pgGonder({ tip: "pg_durum" }), 300);
  } else {
    _pgD.bitti = false;
    _pgD.hata = m.hata || (pgT().pgHata || "Hata");
    _pgD.adimlar.push({ metin: _pgD.hata, hata: true });
  }
  pgCiz();
};

// ---------------------------------------------------------------
// Dil degisiminde yeniden ciz (i18n.js applyLanguage koprusu)
// ---------------------------------------------------------------
window.pgSihirbazDilGuncelle = function () {
  if (_pgD.perde) pgCiz();
};

// Sihirbaz acik mi? (kullanici.js giris ekranini bastirmak icin sorar)
window.pgSihirbazAcikMi = function () { return !!_pgD.perde; };
// ---------------------------------------------------------------
// VT_MENU_KIP_2486: "Veritabani Ayarlari" menu ogesi gorunurlugu
// ---------------------------------------------------------------
// KULLANICI ISTEGI: oge YALNIZ kendi merkez sunucusunu satin alip
// kuran musteride (kapali devre kurulum) gorunur. Bulut ornegindeki
// yoneticide GORUNMEZ.
//
// NEDEN BURADA: merkez kipi bayragi (`merkez_kipi`) yalnizca pg_durum
// yanitinda gelir ve bu modulun `_pgD.durum` nesnesinde yasar. Ogeyi
// yoneten betik, bayragi tutan modulde durmalidir.
//
// GUVENLI TARAF: bayrak henuz gelmediyse oge GIZLENIR. Yanlislikla
// gostermek islevsiz bir menu demektir (sunucu komutu reddeder);
// gecikmeli gostermek ise yalnizca kisa bir bekleme demektir.
//
// Gorunurluk kolaylik saglar; sunucu her PG komutunda hem rolu hem
// merkez kipini AYRICA denetler (istemciye guvenilmez).
window.vtMenuGorunumTazele = function () {
  const oge = document.getElementById("pmVeritabani");
  if (!oge) return;
  // OLCULDU: `oturum` kullanici.js icinde `let` ile tanimli GLOBAL
  // degiskendir (window.oturum DEGIL). Diger moduller de ona bu
  // yolla erisir: program_ayar.js:44 `typeof oturum !== "undefined"`.
  let rolTamam = false;
  try {
    rolTamam = !!(typeof oturum !== "undefined" && oturum &&
                  oturum.rol === "yonetici");
  } catch (e) { rolTamam = false; }
  const d = _pgD.durum || {};
  // Bayrak gelmemisse (durum bos) gizle; merkez kipiyse gizle.
  const kapaliDevre = (_pgD.durum !== null) && !d.merkez_kipi;
  oge.style.display = (rolTamam && kapaliDevre) ? "flex" : "none";
};

// ---------------------------------------------------------------
// Profil menusu: "Veritabani Ayarlari" (yalniz yonetici gorur)
// ---------------------------------------------------------------
document.addEventListener("DOMContentLoaded", function () {
  const oge = document.getElementById("pmVeritabani");
  if (!oge) return;
  oge.addEventListener("click", function () {
    const menu = document.getElementById("profilMenu");
    if (menu) menu.classList.add("popup-gizli");
    // Kayitli bilgileri tazele, sonra sihirbazi ac. Sifre sunucudan
    // GELMEZ; kullanici yeniden girer.
    pgGonder({ tip: "pg_durum" });
    setTimeout(function () { window.pgSihirbazYenidenAc(); }, 150);
  });
});
