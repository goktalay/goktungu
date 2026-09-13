// =================================================================
// GOKTUNGU - KULLANICI GIRISI + OTURUM + KULLANICI YONETIM PANELI
// Bu dosya index.html'den mekanik olarak ayrilmistir; yukleme sirasi
// index.html'deki <script> sirasina baglidir (klasik script, ortak scope).
// =================================================================
// KULLANICI GIRISI VE OTURUM YONETIMI
// ---------------------------------------------------------------
const OTURUM_KEY = "goktungu_oturum";      // {eposta, jeton} - "bilgileri sakla"
// BULGU_10a (2026-08-17): burada ARTIK PAROLA TUTULMUYOR.
// Eskiden {eposta, sifre} saklaniyordu ve 800 ms'lik
// zamanlayici parolayi otomatik giris icin yeniden
// kullaniyordu; XSS ile calinan parola KALICI erisim
// veriyordu. Artik 30 gun gecerli, iptal edilebilir oturum
// jetonu saklanir.
let oturum = null;                       // giris yapan kullanici (sifresiz)
let girisBekleniyor = false;             // WS yaniti bekleniyor mu
let otomatikGirisDenendi = false;

const girisPerde  = document.getElementById("girisPerde");
const girisEposta = document.getElementById("girisEposta");
const girisSifre  = document.getElementById("girisSifre");
const girisHatirla= document.getElementById("girisHatirla");
const btnGiris    = document.getElementById("btnGiris");
const girisHata   = document.getElementById("girisHata");

function sakliOturum(){
  // BULGU_10a: kayit DOGRULANIR. `eposta` veya `jeton` eksikse kayit
  // SILINIR ve null donulur.
  //
  // NEDEN: `otomatikGirisDene` kosulu `s.eposta && s.jeton` arar.
  // Eksik alanli kayit varsa jeton_giris HIC gonderilmez, sunucu
  // reddetme firsati bulamaz, `jeton_gecersiz` gelmez ve kayit
  // SONSUZA KADAR kalir. `girisHatirla` isaretli gorunur, kullanici
  // otomatik giris bekler, hicbir hata cikmaz -> SESSIZ KUSUR.
  // Eski surumden kalan {eposta, sifre} kayitlari da burada temizlenir.
  let s = null;
  try { s = JSON.parse(localStorage.getItem(OTURUM_KEY) || "null"); }
  catch(e){
    try { localStorage.removeItem(OTURUM_KEY); } catch(e2){}
    return null;
  }
  if (!s || typeof s !== "object") return null;
  if (!s.eposta || !s.jeton){
    try { localStorage.removeItem(OTURUM_KEY); } catch(e){}
    return null;
  }
  return s;
}

// Kayitli bilgiler varsa formu doldur
(function(){
  const s = sakliOturum();
  if (s && s.eposta){
    girisEposta.value = s.eposta;
    // BULGU_10a: parola alani ARTIK DOLDURULMAZ (parola saklanmiyor).
    // Eski surumden kalan duz metin parola varsa kayit TEMIZLENIR.
    //
    // NEDEN kaydi bos jetonla GUNCELLEMEK yerine SILIYORUZ: bos
    // jetonlu kayit ise yaramaz, ama `girisHatirla` isaretli gorunur
    // ve kullanici otomatik giris bekler. Hicbir hata cikmadigi icin
    // bu SESSIZ bir kusur olurdu. Kayit silinince kullanici bir kez
    // elle giris yapar ve yerine gecerli jeton yazilir.
    if (s.sifre && !s.jeton){
      try { localStorage.removeItem(OTURUM_KEY); } catch(e){}
      girisHatirla.checked = false;
    } else {
      girisHatirla.checked = true;
    }
  }
})();

function girisGonder(){
  const e = girisEposta.value.trim().toLowerCase();
  const s = girisSifre.value;
  const t = D();
  if (!e || !s){ girisHata.textContent = t.girisHataBos; return; }
  if (!ws || ws.readyState !== 1){
    girisHata.textContent = t.girisHataSunucu;
    return;
  }
  girisHata.textContent = "";
  girisBekleniyor = true;
  btnGiris.disabled = true;
  ws.send(JSON.stringify({tip: "giris", eposta: e, sifre: s}));
}

btnGiris.addEventListener("click", girisGonder);
girisSifre.addEventListener("keydown", (e) => { if (e.key === "Enter") girisGonder(); });
girisEposta.addEventListener("keydown", (e) => { if (e.key === "Enter") girisSifre.focus(); });

function girisSonucIsle(m){
  girisBekleniyor = false;
  btnGiris.disabled = false;
  if (m.basarili && m.kullanici){
    oturum = m.kullanici;
    // FAZ18-IS5-PILOT-KONUM: harita acilis konumu PILOT BAZINDA saklanir. Kanca burada
    // cagrilir cunku `oturum` yalniz bu dosyanin kapsamindadir ve
    // eposta pilotu ayiran fiili anahtardir (tum moduller onu
    // kullaniyor). harita.js index.html'de ONCE yuklendigi icin islev
    // bu noktada hazirdir; yine de varlik denetimi yapilir.
    try {
      if (typeof window.haritaPilotDegisti === "function")
        window.haritaPilotDegisti(oturum.eposta || null);
    } catch (e) {}
    oturum.izinler = m.izinler || null;   // v2.1.7: rol izinleri
    // v2.4.53 Faz 4: merkezde calisan ornek giris yanitinda kurum
    // kimligini (unvan + logo + adres) gonderir. sirket.js bunu yerel
    // `sirket` ayarinin ONUNE koyar; boylece cok kiracili /app/ her
    // oturumda dogru kurumun logosunu gosterir. Lokal kurulumda bu
    // alan gelmez ve cagri hic yapilmaz (eski davranis korunur).
    if (m.firma && typeof window.sirketMerkezKimlik === "function")
      window.sirketMerkezKimlik(m.firma);
    if (typeof window.uyariMerkeziOturum === "function")
      window.uyariMerkeziOturum(m.okunmamis || 0);
    // v2.4.32: mesaj merkezi. Sunucu giris yanitinda okunmamis mesaj
    // sayisini `mesaj_okunmamis` alaninda gonderir (uyari sayaci olan
    // `okunmamis` alanindan AYRIDIR; ikisi karistirilmamalidir).
    if (typeof window.mesajMerkeziOturum === "function")
      window.mesajMerkeziOturum(m.mesaj_okunmamis || 0);
    // Bilgileri sakla secenegi
    if (girisHatirla.checked){
      // BULGU_10a: PAROLA DEGIL, sunucudan gelen oturum jetonu
      // saklanir. Sunucu jeton uretemezse (veritabani sorunu) `m.jeton`
      // gelmez; o durumda HICBIR SEY saklanmaz ve kullanici bir sonraki
      // acilista elle giris yapar. Islev kaybi olur ama parola diske
      // YAZILMAZ.
      try {
        if (m.jeton){
          localStorage.setItem(OTURUM_KEY, JSON.stringify(
            {eposta: girisEposta.value.trim().toLowerCase(),
             jeton: m.jeton}));
        } else {
          localStorage.removeItem(OTURUM_KEY);
        }
      } catch(e){}
    } else {
      try { localStorage.removeItem(OTURUM_KEY); } catch(e){}
    }
    girisPerde.classList.add("popup-gizli");
    oturumArayuzuKur();
  } else {
    // v2.4.34: `m.hata` sunucudan gelen ozel mesaj; yoksa sozlukten
    // cevrilmis genel metin kullanilir. Eskiden Turkce dize gomuluydu
    // ve EN arayuzde Turkce goruntuluyordu.
    const _t = D();
    // BULGU_10a: sunucu `jeton_gecersiz` bildirdiyse sakli
    // kayit SILINIR; aksi halde 800 ms'lik zamanlayici
    // suresiz olarak gecersiz jetonla dener.
    if (m.jeton_gecersiz){
      try { localStorage.removeItem(OTURUM_KEY); } catch(e){}
      otomatikGirisDenendi = false;
      // FAZ18-IS8-GIRIS-PENCERESI: tazeleme bayragi da indirilir ve perde
      // acilir. Bayrak kalsa gecersiz jetonla her yeniden baglanma
      // bir BASARISIZ deneme sayilir ve kaba kuvvet sayaci
      // (kaba_kuvvet.py `ws:jeton_giris`) kullanicinin kendi
      // hesabini kilitleyebilirdi. Sakli kayit yukarida silindigi
      // icin ikinci turda gonderim olmaz; zincir kendini kapatir.
      window.kimlikTazeleGerekli = false;
      if (typeof girisGerekliGoster === "function") girisGerekliGoster();
    }
    girisHata.textContent = m.hata
      || ((_t.vpHataGirisHatali || "E-posta veya \u015fifre hatal\u0131") + ".");
    girisSifre.value = "";
    girisSifre.focus();
  }
}

// WS acildiginda kayitli bilgilerle otomatik giris dene (bir kez)
// IS9B-OTURUM-DEVRI: kurumsal panelden gelen oturumu devral.
//
// SORUN: kullanici `company.goktungu.com` uzerinde giris yapip App'e
// gectiginde yeniden parola soruluyordu. Iki panel AYRI KAYNAKLARDIR
// (`company.` vs `app.`), bu yuzden `localStorage` PAYLASILMAZ; App
// kendi oturumunu gormedigi icin giris perdesini aciyordu.
//
// COZUM: sakli oturum YOKSA once `/api/oturum/devir` ucuna sorulur.
// Uc, tarayicinin tasidigi `goktungu_firma` cerezini merkez oturum
// tablosunda dogrular ve bir App jetonu uretir. Jeton normal sakli
// oturum kaydi olarak yazilir; sonrasinda AKIS DEGISMEZ, mevcut
// `jeton_giris` yolu isler.
//
// TEK DENEME: `_devirDenendi` bayragi 800 ms'lik zamanlayicinin ucu
// tekrar tekrar cagirmasini engeller. Bayrak olmasa cerezi olmayan
// her kullanici icin saniyede birden fazla bosa istek gider.
let _devirDenendi = false;
let _devirSuruyor = false;

async function oturumDevralDene(){
  if (_devirDenendi || _devirSuruyor) return false;
  _devirSuruyor = true;
  try {
    // `credentials: "same-origin"` ZORUNLU: cerez `HttpOnly` ve
    // gonderilmezse uc her zaman "Kurumsal oturum yok" doner.
    const y = await fetch("api/oturum/devir", {
      credentials: "same-origin",
      cache: "no-store",
    });
    // 404: kapali devre kurulum (Merkez Uygulama) — uc yok, sessiz gec.
    if (!y.ok) { _devirDenendi = true; return false; }
    const d = await y.json();
    if (!d || !d.tamam || !d.eposta || !d.jeton){
      _devirDenendi = true;
      return false;
    }
    try {
      localStorage.setItem(OTURUM_KEY, JSON.stringify({
        eposta: d.eposta, jeton: d.jeton,
      }));
    } catch(e){ /* depolama kapali: devir kalici olmaz, giris yine gecer */ }
    _devirDenendi = true;
    return true;
  } catch(e){
    // Ag hatasi: bir daha denenmez. Kullanici elle giris yapabilir;
    // sonsuz yeniden deneme dongusu OLUSMAZ.
    _devirDenendi = true;
    return false;
  } finally {
    _devirSuruyor = false;
  }
}

function otomatikGirisDene(){
  // FAZ18-IS8-GIRIS-PENCERESI: WS YENIDEN BAGLANDIYSA KIMLIK TEKRAR GONDERILIR.
  //
  // Sunucuda oturumun firma baglami WS baglanti nesnesinin kimligine
  // baglidir (sunucu.py `_ws_firma[id(websocket)]`). Baglanti kopunca
  // o baglam sunucuda YOK OLUR. `ws.onclose` yeniden baglanir ama
  // istemcideki `oturum` dolu kaldigi icin eski kapi burada donuyor
  // ve jeton TEKRAR GONDERILMIYORDU. Sonuc: istemci "girisli"
  // gorunurken sunucu "kimliksiz" biliyor ve her panel istegi
  // "Oturum gerekli" hatasi aliyordu; kullanici sayfayi yenilemeden
  // duzeltemiyordu.
  //
  // `kimlikTazeleGerekli` bayragi `ws.js` onclose tarafindan kaldirilir.
  // Bayrak varken `oturum` dolu olsa DA jeton gonderilir; sunucu
  // tarafinda atama islemi oldugu icin (ekleme degil) tekrar giris
  // guvenlidir ve yan etkisi yoktur.
  const _tazele = !!window.kimlikTazeleGerekli;
  if (!_tazele && (oturum || otomatikGirisDenendi)) return;
  if (_tazele && !sakliOturum()){
    // Tazeleme isteniyor ama sakli jeton yok: gonderilecek kimlik
    // yoktur. Bayrak indirilir, aksi halde her 800 ms'de bu dal
    // yeniden degerlendirilir. Giris perdesi asagidaki normal
    // akista acilir.
    window.kimlikTazeleGerekli = false;
  }
  let s = sakliOturum();
  // IS9B-OTURUM-DEVRI: sakli oturum yoksa kurumsal oturumu devral.
  // `ws` HAZIR OLMASI BEKLENIR: devir jetonu uretilip WS kapali
  // kalirsa jeton kullanilmadan durur ve kullanici gereksiz bir
  // "sunucu yok" perdesi gorur.
  // FAZ18-IS8-GIRIS-PENCERESI: devir denendi ve sakli oturum yoksa
  // kullanicinin giris yapmasi GEREKIR -> perde acilir. Perde artik
  // baslangicta gizli oldugu icin bu cagri olmadan kullanici bos
  // arayuz gorurdu.
  if (!s && _devirDenendi && ws && ws.readyState === 1){
    girisGerekliGoster();
  }
  if (!s && ws && ws.readyState === 1 && !_devirDenendi){
    oturumDevralDene().then((oldu) => {
      if (oldu) otomatikGirisDene();
    });
    return;
  }
  if (s && s.eposta && s.jeton && ws && ws.readyState === 1){
    otomatikGirisDenendi = true;
    girisBekleniyor = true;
    // BULGU_10a: otomatik giris JETONLA yapilir. Parolayi
    // tekrar aga gondermek, saklamayi bitirmenin amacini
    // bosa cikarirdi.
    // FAZ18-IS8-GIRIS-PENCERESI: bayrak burada indirilir. Gonderim
    // yapildigi icin tekrar tazelemeye gerek yoktur; yanit
    // `giris_sonuc` olarak gelir ve normal akis isler.
    window.kimlikTazeleGerekli = false;
    ws.send(JSON.stringify({tip: "jeton_giris", jeton: s.jeton}));
  }
}
// FAZ18-IS8-GIRIS-PENCERESI: GIRIS PENCERESINI ACAN TEK KAPI.
//
// Perde `index.html` icinde `popup-gizli` ile baslar; boylece oturumu
// olan kullanici giris formunu HIC gormez. Giris gercekten
// gerektiginde bu islev perdeyi acar. Tek kapi olmasi, perdenin
// hangi kosulda acildigini izlenebilir kilar.
function girisGerekliGoster(){
  if (!girisPerde) return;
  if (!girisPerde.classList.contains("popup-gizli")) return;  // zaten acik
  girisPerde.classList.remove("popup-gizli");
  // Odak dogrudan bos alana verilir: e-posta bossa oraya, doluysa
  // (hatirlanan kullanici) parolaya.
  try {
    if (girisEposta && !girisEposta.value) girisEposta.focus();
    else if (girisSifre) girisSifre.focus();
  } catch(e){}
}
window.girisGerekliGoster = girisGerekliGoster;
setInterval(otomatikGirisDene, 800);

// ---------------------------------------------------------------
// OTURUM ARAYUZU: profil rozeti, profil menusu, yonetici dugmesi
// ---------------------------------------------------------------
const profilKutu = document.getElementById("profilKutu");
const profilFoto = document.getElementById("profilFoto");
const profilAd   = document.getElementById("profilAd");
const profilMenu = document.getElementById("profilMenu");
const btnKullanicilar = document.getElementById("btnKullanicilar");
const kullaniciPopup  = document.getElementById("kullaniciPopup");
const kullaniciListe  = document.getElementById("kullaniciListe");

// v2.3.3: AVATAR YARDIMCISI — resim yoksa/yuklenemezse yuvarlak
// fa-user ikonu gosterir. img'nin hemen yanina .avatar-ikon span'i
// yerlestirir; resim basariyla yuklenirse ikon gizlenir.
function avatarUygula(img, url){
  if (!img) return;
  let ikon = img._avatarIkon;
  if (!ikon){
    ikon = document.createElement("span");
    ikon.className = "avatar-ikon";
    ikon.innerHTML = "<i class='fa-solid fa-user'></i>";
    img.parentNode.insertBefore(ikon, img);
    img._avatarIkon = ikon;
    img.addEventListener("error", () => {
      img.style.display = "none"; ikon.style.display = "inline-flex";
    });
    img.addEventListener("load", () => {
      img.style.display = ""; ikon.style.display = "none";
    });
  }
  if (url){
    // Ayni URL yeniden atanirsa load/error tetiklenmeyebilir:
    // ikon acik kalsin, load gelince kapanir.
    if (img.getAttribute("src") !== url){
      img.style.display = "none"; ikon.style.display = "inline-flex";
      img.src = url;
    } else if (img.complete && img.naturalWidth > 0){
      img.style.display = ""; ikon.style.display = "none";
    }
  } else {
    img.removeAttribute("src");
    img.style.display = "none"; ikon.style.display = "inline-flex";
  }
}
window.avatarUygula = avatarUygula;

function oturumArayuzuKur(){
  if (!oturum) return;
  avatarUygula(profilFoto, oturum.avatar || "");
  profilFoto.title = oturum.ad_soyad || oturum.eposta || "";
  if (profilAd) profilAd.textContent = oturum.ad_soyad || oturum.eposta;
  profilKutu.style.display = "flex";
  avatarUygula(document.getElementById("pmFoto"), oturum.avatar || "");
  document.getElementById("pmAd").textContent = oturum.ad_soyad || "";
  document.getElementById("pmUnvan").textContent = oturum.unvan || "";
  // Yonetici ise profil menusunde KULLANICI YONETIMI + YENI KULLANICI
  // + ROL YONETIMI
  // v2.4.65 TEK KAPI: Uyelik ve rol yonetimi ARTIK bu arayuzde yok.
  // Kurumsal panelden (/company/) yapilir. Ogeler yoneticiye bile
  // gosterilmez; yerine "Kurumsal Panel" baglantisi cikar.
  // NEDEN: bu arayuzun yazdigi yerel tablo ile girisin dogrulandigi
  // merkez tablosu AYRI. Yerel tabloya yazilan kullanici giris
  // yapamaz. Ayrica koltuk/faturalandirma denetimi merkezde.
  const pmKul = document.getElementById("pmKullanicilar");
  if (pmKul) pmKul.style.display = "none";
  const pmYeniKul = document.getElementById("pmYeniKullanici");
  if (pmYeniKul) pmYeniKul.style.display = "none";
  const pmRol = document.getElementById("pmRolYonetimi");
  if (pmRol) pmRol.style.display = "none";
  // Yonetici rolundeki kullaniciya kurumsal panel baglantisi gosterilir
  const pmKurumsal = document.getElementById("pmKurumsalPanel");
  if (pmKurumsal) pmKurumsal.style.display =
    (oturum.rol === "yonetici") ? "flex" : "none";
  // v2.4.41: Sirket Bilgileri - YALNIZ yonetici gorur
  const pmSirket = document.getElementById("pmSirketBilgi");
  if (pmSirket) pmSirket.style.display =
    (oturum.rol === "yonetici") ? "flex" : "none";
  // v2.4.51: Veritabani Ayarlari - YALNIZ yonetici gorur.
  // Gorunurluk kolaylik saglar; sunucu her PG komutunda rolu AYRICA
  // denetler (istemciye guvenilmez).
  // VT_MENU_KIP_2486: oge artik ROLE DEGIL, kuruluma bakar. Yalniz kendi
  // merkez sunucusunu kuran musteri (kapali devre) gorur. Bulut
  // ornegindeki yonetici GORMEZ -- orada sema operatorun isidir ve
  // sunucu komutu zaten reddeder, yani oge islevsizdi.
  if (typeof window.vtMenuGorunumTazele === "function")
    window.vtMenuGorunumTazele();
  // v2.4.49: Makine kapat / yeniden baslat - YALNIZ yonetici gorur.
  // Gorunurluk yalnizca kolaylik saglar; sunucu her komutta rolu
  // AYRICA denetler (istemciye guvenilmez). Ayrica guc_hazir=false
  // ise (polkit/sudo yetkisi yok) dugmeler gizlenir; aksi halde
  // basildiginda hicbir sey olmaz ve sessiz basarisizlik olur.
  if (typeof window.makineGucGorunumTazele === "function")
    window.makineGucGorunumTazele();
  // v2.4.41: sirket bilgileri tanimli degilse ZORUNLU sihirbaz.
  // Giristen SONRA cagrilir: rol bilinmeden yonetici olup olmadigi
  // anlasilamaz, dolayisiyla giris ekraninda gosterilemez.
  if (typeof window.sirketSihirbazDenetle === "function")
    window.sirketSihirbazDenetle(oturum);
  // v2.4.0: AI menusu giris yapinca gorunur
  const mbAIOge = document.getElementById("mbAI");
  if (mbAIOge) mbAIOge.style.display = "";
  // v2.1.7: Pilot Hakkinda rol combobox'i icin dinamik rol listesi
  if (typeof window.rolAdlariTazele === "function") window.rolAdlariTazele();
  // v2.1.8: Radar menusu gorunurlugu (radar.izleme izni) + program
  // ayari kilidi giris yapan kullaniciya gore tazelenir
  if (typeof window.programAyarOturumTazele === "function")
    window.programAyarOturumTazele();
  // v2.4.53 Faz 7: KOPRU listesi periyodik tazelenir. GIRISTEN SONRA
  // baslar: sunucu listeyi oturumun firmasina gore suzer, oturum
  // yoksa "Oturum gerekli." doner. Ayrica bu liste Faz 8'de Radar ve
  // Yer Kontrol Istasyonu Dual menulerinin gorunurlugunu belirler.
  if (typeof window.bagKopruZamanlayiciKur === "function")
    window.bagKopruZamanlayiciKur();
}

profilKutu.addEventListener("click", (e) => {
  e.stopPropagation();
  profilMenu.classList.toggle("popup-gizli");
});
document.addEventListener("click", (e) => {
  if (!profilMenu.classList.contains("popup-gizli") &&
      !profilMenu.contains(e.target)){
    profilMenu.classList.add("popup-gizli");
  }
});

// Cikis yap
document.getElementById("btnCikis").addEventListener("click", () => {
  oturum = null;
  otomatikGirisDenendi = true;  // cikis sonrasi otomatik giris tekrar denenmesin
  profilMenu.classList.add("popup-gizli");
  profilKutu.style.display = "none";
  const pmKulX = document.getElementById("pmKullanicilar");
  if (pmKulX) pmKulX.style.display = "none";
  const pmYeniKulX = document.getElementById("pmYeniKullanici");
  if (pmYeniKulX) pmYeniKulX.style.display = "none";
  const pmRolX = document.getElementById("pmRolYonetimi");
  if (pmRolX) pmRolX.style.display = "none";
  // v2.4.65: cikista kurumsal panel baglantisi da gizlenir
  const pmKurumsalX = document.getElementById("pmKurumsalPanel");
  if (pmKurumsalX) pmKurumsalX.style.display = "none";
  const pmSirketX = document.getElementById("pmSirketBilgi");
  if (pmSirketX) pmSirketX.style.display = "none";
  // v2.4.51: cikista veritabani ayarlari ogesi gizlenir
  const pmVtX = document.getElementById("pmVeritabani");
  if (pmVtX) pmVtX.style.display = "none";
  // v2.4.49: cikista makine guc dugmeleri gizlenir
  ["pmMakineKapat", "pmMakineYeniden"].forEach((mid) => {
    const el = document.getElementById(mid);
    if (el) el.style.display = "none";
  });
  // v2.4.41: cikista sirket kilidi/sihirbazi ve duzenleme paneli
  // kapatilir; oturum bilgisi de sifirlanir ki bir sonraki girise
  // kadar sihirbaz yeniden degerlendirilsin.
  if (typeof window.sirketOturumBitti === "function")
    window.sirketOturumBitti();
  const ykPopupX = document.getElementById("yeniKulPopup");
  if (ykPopupX) ykPopupX.classList.add("popup-gizli");
  // v2.4.0: AI menusu cikista gizlenir
  const mbAIX = document.getElementById("mbAI");
  if (mbAIX) mbAIX.style.display = "none";
  if (typeof window.uyariMerkeziCikis === "function") window.uyariMerkeziCikis();
  if (typeof window.mesajMerkeziCikis === "function") window.mesajMerkeziCikis();
  if (typeof pilotHakkindaKapat === "function") pilotHakkindaKapat();
  if (typeof rolYonetimiKapat === "function") rolYonetimiKapat();
  // v2.4.53 Faz 7: KOPRU listesi oturuma baglidir. Cikista zamanlayici
  // durdurulur ve liste bosaltilir; aksi halde bir sonraki kullanici
  // onceki firmanin saha makinelerini gorurdu (cok kiracili /app/).
  if (typeof window.bagKopruOturumBitti === "function")
    window.bagKopruOturumBitti();
  kullaniciPopup.classList.add("popup-gizli");
  // "Bilgileri sakla" isaretli degilse alanlari temizle
  if (!girisHatirla.checked){
    girisEposta.value = ""; girisSifre.value = "";
    try { localStorage.removeItem(OTURUM_KEY); } catch(e){}
  } else {
    // BULGU_10a: cikis sonrasi parola forma GERI YAZILMAZ.
    // Eskiden saklanan duz metin parola buraya doldurulurdu;
    // parola artik saklanmadigi icin bu satir kaldirildi.
    girisSifre.value = "";
  }
  girisHata.textContent = "";
  girisPerde.classList.remove("popup-gizli");
});

// ---------------------------------------------------------------
// KULLANICI YONETIM PANELI (YONETICI)
// ---------------------------------------------------------------
btnKullanicilar.addEventListener("click", (e) => {
  e.stopPropagation();
  const acikti = !kullaniciPopup.classList.contains("popup-gizli");
  kullaniciPopup.classList.toggle("popup-gizli");
  if (!acikti && ws && ws.readyState === 1){
    ws.send(JSON.stringify({tip: "kullanici_liste"}));
  }
});
document.getElementById("btnKulPopupKapat").addEventListener("click",
  () => kullaniciPopup.classList.add("popup-gizli"));
document.addEventListener("click", (e) => {
  if (!kullaniciPopup.classList.contains("popup-gizli") &&
      !kullaniciPopup.contains(e.target) && e.target !== btnKullanicilar){
    kullaniciPopup.classList.add("popup-gizli");
  }
});

// v2.4.64: 'aktif' alani sunucudan boolean gelir, ancak eski surumlerle
// veya dogrudan veritabani duzenlemesiyle 0/1 tamsayisi ya da "0"/"1"
// dizesi de gelebilir. JavaScript'te 0 === false DAIMA false verdigi
// icin ham karsilastirma pasif kullaniciyi ETKIN gosteriyordu; daha
// kotusu, etkinlestirme dugmesi {aktif:false} gonderip kullaniciyi
// pasif tutuyordu. Tum okumalar bu yardimcidan gecer.
function kulAktifMi(deger){
  if (deger === undefined || deger === null) return true;
  if (typeof deger === "boolean") return deger;
  if (typeof deger === "number") return deger !== 0;
  const m = String(deger).trim().toLowerCase();
  if (m === "") return true;
  if (m === "0" || m === "false" || m === "hayir" || m === "pasif") return false;
  return true;
}

// v2.4.65 TEK KAPI: Bu islev ARTIK sunucuya yazma komutu gondermez.
// Rol degistirme, etkinlestirme/pasiflestirme ve silme kurumsal
// panelden yapilir. Sunucu tarafi da bu alanlari reddeder; istek
// gondermek kullaniciya sessiz basarisizlik olarak gorunurdu.
function kullaniciGuncelleGonder(eposta, alanlar){
  const t = (typeof D === "function") ? D() : {};
  if (typeof window.uyariToastGoster === "function"){
    window.uyariToastGoster({
      baslik: t.uyelikTekKapiBaslik || "Üyelik Yönetimi",
      mesaj: t.uyelikTekKapiMesaj ||
             "Üyelik işlemleri kurumsal panelden yapılır.",
      seviye: "bilgi", sure: 6000});
  }
}

function kullaniciListeCiz(liste){
  const t = D();
  kullaniciListe.innerHTML = "";
  liste.forEach(k => {
    const satir = document.createElement("div");
    const kAktif = kulAktifMi(k.aktif);
    satir.className = "kul-satir" + (kAktif ? "" : " pasif");
    // v2.1.7: satira tiklayinca kullanicinin Pilot Hakkında popup'i acilir
    satir.style.cursor = "pointer";
    satir.addEventListener("click", (ev) => {
      if (ev.target.closest(".kul-islem")) return;  // islem dugmeleri haric
      if (typeof pilotHakkindaAc === "function") pilotHakkindaAc(k.eposta);
    });

    const img = document.createElement("img");
    img.alt = "";
    satir.appendChild(img);
    avatarUygula(img, k.avatar || "");

    const bilgi = document.createElement("div");
    bilgi.className = "kul-bilgi";
    const ad = document.createElement("div");
    ad.className = "kb-ad"; ad.textContent = k.ad_soyad || "";
    const ep = document.createElement("div");
    ep.className = "kb-eposta"; ep.textContent = k.eposta || "";
    const un = document.createElement("div");
    un.className = "kb-unvan"; un.textContent = k.unvan || "";
    bilgi.appendChild(ad); bilgi.appendChild(ep); bilgi.appendChild(un);
    satir.appendChild(bilgi);

    const rol = document.createElement("span");
    rol.className = "kul-rol " + (k.rol === "yonetici" ? "yonetici" : "kullanici");
    rol.textContent = k.rol === "yonetici" ? t.rolYonetici : t.rolKullanici;
    satir.appendChild(rol);

    // Islem dugmeleri (kendi hesabinda rol dusurme/pasifleme engellenir)
    const islem = document.createElement("div");
    islem.className = "kul-islem";
    if (oturum && k.eposta !== oturum.eposta){
      const bRol = document.createElement("button");
      bRol.title = t.btnRolYap;
      bRol.innerHTML = '<i class="fa-solid fa-user-shield"></i>';
      bRol.addEventListener("click", () => {
        kullaniciGuncelleGonder(k.eposta,
          {rol: k.rol === "yonetici" ? "kullanici" : "yonetici"});
      });
      islem.appendChild(bRol);

      const bAktif = document.createElement("button");
      bAktif.title = t.btnAktifPasif;
      bAktif.innerHTML = kAktif
        ? '<i class="fa-solid fa-user-slash"></i>'
        : '<i class="fa-solid fa-user-check"></i>';
      bAktif.addEventListener("click", () => {
        // Mevcut durumun TERSI gonderilir
        kullaniciGuncelleGonder(k.eposta, {aktif: !kAktif});
      });
      islem.appendChild(bAktif);

      // v2.3.2: Sifre sifirlama (yonetici, baska kullanici icin)
      const bSifre = document.createElement("button");
      bSifre.title = t.btnSifreSifirla || "Şifre Sıfırla";
      bSifre.innerHTML = '<i class="fa-solid fa-key"></i>';
      bSifre.addEventListener("click", () => {
        const yeni = prompt(
          (t.sifreSifirlaSoru || "Yeni şifre") + " — " + k.eposta);
        if (yeni && yeni.trim()){
          kullaniciGuncelleGonder(k.eposta, {sifre: yeni.trim()});
        }
      });
      islem.appendChild(bSifre);
    }
    satir.appendChild(islem);
    kullaniciListe.appendChild(satir);
  });
}

// ---------------------------------------------------------------
// v2.3.3: YENI KULLANICI POPUP'I (yonetici, profil menusunden acilir)
// ---------------------------------------------------------------
const yeniKulPopup = document.getElementById("yeniKulPopup");
const pmYeniKullaniciOge = document.getElementById("pmYeniKullanici");
function yeniKulPopupAc(){
  // v2.4.65 TEK KAPI: bu popup ARTIK acilmaz. Uyelik ekleme kurumsal
  // panelden yapilir. Islev korunur (baska yerlerden cagriliyor
  // olabilir) ancak daima kurumsal panele yonlendirir.
  const t = (typeof D === "function") ? D() : {};
  if (typeof window.uyariToastGoster === "function"){
    window.uyariToastGoster({
      baslik: t.uyelikTekKapiBaslik || "Üyelik Yönetimi",
      mesaj: t.uyelikTekKapiMesaj ||
             "Üyelik ekleme kurumsal panelden yapılır.",
      seviye: "bilgi", sure: 6000});
  }
  return;
}
function yeniKulPopupAcEski(){
  if (!(oturum && oturum.rol === "yonetici") || !yeniKulPopup) return;
  yeniKulPopup.classList.remove("popup-gizli");
  ykRolDoldur();
  const mes = document.getElementById("ykMesaj");
  if (mes){ mes.textContent = ""; mes.className = ""; }
  const ep = document.getElementById("ykEposta");
  if (ep) ep.focus();
}
function yeniKulPopupKapat(){
  if (yeniKulPopup) yeniKulPopup.classList.add("popup-gizli");
}
if (pmYeniKullaniciOge){
  pmYeniKullaniciOge.addEventListener("click", (e) => {
    e.stopPropagation();
    profilMenu.classList.add("popup-gizli");
    yeniKulPopupAc();
  });
}
const btnYeniKulKapat = document.getElementById("btnYeniKulKapat");
if (btnYeniKulKapat)
  btnYeniKulKapat.addEventListener("click", yeniKulPopupKapat);
// Not: surukleme/boyutlandirma popup_tasima.js statik kurulumunda
// ("yeniKulPopup") otomatik yapilir.
const yeniKulForm = document.getElementById("yeniKulForm");
if (yeniKulForm){
  document.getElementById("ykEkleBtn").addEventListener("click", () => {
    const t = D();
    const mes = document.getElementById("ykMesaj");
    const eposta = document.getElementById("ykEposta").value.trim();
    const sifre = document.getElementById("ykSifre").value;
    if (!eposta || !sifre){
      if (mes){ mes.textContent = t.ykEksikAlan ||
        "E-posta ve şifre zorunludur"; mes.className = "hata"; }
      return;
    }
    // v2.4.65 TEK KAPI: kullanici_ekle komutu ARTIK gonderilmez.
    // Sunucu da bu komutu reddeder. Uyelik ekleme kurumsal panelde
    // yapilir; boylece kayit merkez tablosuna gider (girisin
    // dogrulandigi yer) ve pilot koltuk siniri denetlenir.
    if (mes){
      mes.textContent = t.uyelikTekKapiMesaj ||
        "Üyelik ekleme kurumsal panelden yapılır.";
      mes.className = "hata";
    }
  });
}

function ykRolDoldur(){
  const t = D();
  const sec = document.getElementById("ykRol");
  if (!sec) return;
  let adlar = (window._ryRolAdlari && window._ryRolAdlari.length)
    ? window._ryRolAdlari.slice() : ["kullanici", "yonetici"];
  if (!adlar.includes("kullanici")) adlar.push("kullanici");
  if (!adlar.includes("yonetici")) adlar.push("yonetici");
  adlar.sort((a, b) => {
    const s = (x) => x === "yonetici" ? 0 : x === "kullanici" ? 1 : 2;
    return s(a) - s(b) || a.localeCompare(b, "tr");
  });
  sec.innerHTML = adlar.map((ad) => {
    const etiket = ad === "yonetici" ? (t.rolYonetici || "Yönetici")
      : ad === "kullanici" ? (t.rolKullanici || "Kullanıcı")
      : ad.toUpperCase();
    return "<option value='" + ad + "'" +
      (ad === "kullanici" ? " selected" : "") + ">" + etiket + "</option>";
  }).join("");
}

// kullanici_islem (islem: ekle) cevabi — ws.js cagirir
window.yeniKullaniciSonuc = function (m) {
  if (m.islem !== "ekle") return;
  const t = D();
  const mes = document.getElementById("ykMesaj");
  if (mes){
    mes.textContent = m.basarili
      ? (t.ykEklendi || "Kullanıcı eklendi") : (m.hata || "Hata");
    mes.className = m.basarili ? "basari" : "hata";
    setTimeout(() => { if (mes) mes.textContent = ""; }, 4000);
  }
  if (m.basarili && yeniKulForm){
    ["ykEposta", "ykAd", "ykUnvan", "ykSifre"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.value = "";
    });
    setTimeout(yeniKulPopupKapat, 1200);
  }
};

// ---------------------------------------------------------------
// v2.3.2: SIFREMI UNUTTUM (giris ekrani bilgilendirme)
// ---------------------------------------------------------------
const girisSifremiUnuttum = document.getElementById("girisSifremiUnuttum");
const girisUnuttumBilgi = document.getElementById("girisUnuttumBilgi");
if (girisSifremiUnuttum && girisUnuttumBilgi){
  girisSifremiUnuttum.addEventListener("click", () => {
    const t = D();
    girisUnuttumBilgi.textContent = t.sifremiUnuttumBilgi ||
      "Şifrenizi sıfırlamak için sistem yöneticinize başvurun. " +
      "Yönetici, Profil > Kullanıcı Yönetimi ekranından hesabınız " +
      "için yeni bir şifre belirleyebilir.";
    girisUnuttumBilgi.classList.toggle("popup-gizli");
  });
}
