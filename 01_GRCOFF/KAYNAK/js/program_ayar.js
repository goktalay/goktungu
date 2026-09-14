// =================================================================
// GOKTUNGU - PROGRAM AYARLARI
// Ust bardaki "Program Ayarlari" ogesiyle acilan popup.
// Su an tek ayar: C20 RADAR ac/kapat.
//
// v2.1.8 degisiklikleri:
//   - Ayar SUNUCUDA saklanir (gcs_ayarlar.json: radar_arayuz) ve tum
//     istemcilere "ayarlar" mesajiyla dagitilir; localStorage yalnizca
//     ilk boyamada titremeyi onlemek icin onbellek olarak kullanilir.
//   - Program ayarlarini YALNIZCA yonetici degistirebilir (sunucu da
//     ayrica denetler); yonetici olmayanlara anahtar kilitli gorunur.
//   - RADAR KAPALI veya kullanicinin radar.izleme izni YOKSA ust
//     bardaki "Radar" menusu TAMAMEN gizlenir.
//
// RADAR KAPALI iken:
//   - body'ye "radar-kapali" sinifi eklenir (CSS: sol panel, sol tutamac,
//     grafik yarisi gizlenir; logo harita ustune tasinir)
//   - Haritadaki tum radar varliklari gizlenir (kapsama izgarasi, tarama
//     cizgisi + iz yelpazesi, irtifa kubbesi, GCS ikonu, hedef/iz varliklari)
// =================================================================
"use strict";

const PROG_AYAR_KEY = "gcs_radar_acik";   // yalniz ilk boyama onbellegi
let radarModuAcik = true;                 // etkin durum (sunucu + izin)
let radarAyarSunucu = true;               // sunucudaki radar_arayuz degeri

function radarModuOku(){
  try {
    const v = localStorage.getItem(PROG_AYAR_KEY);
    return v === null ? true : v === "1";
  } catch(e){ return true; }
}

function radarModuKaydet(acik){
  try { localStorage.setItem(PROG_AYAR_KEY, acik ? "1" : "0"); } catch(e){}
}

// ---------------------------------------------------------------
// IZIN + ROL YARDIMCILARI
// oturum: kullanici.js'de tanimli global (giris yapan kullanici)
// oturum.izinler: rol izinleri {radar:{izleme:true,...},...}
// ---------------------------------------------------------------
function oturumYoneticiMi(){
  return !!(typeof oturum !== "undefined" && oturum &&
            oturum.rol === "yonetici");
}

function radarIzlemeIzniVar(){
  if (typeof oturum === "undefined" || !oturum) return true; // giris oncesi
  if (oturum.rol === "yonetici") return true;
  const iz = oturum.izinler;
  if (!iz || !iz.radar) return true;           // izin tanimsiz -> serbest
  return iz.radar.izleme !== false;
}

// ---------------------------------------------------------------
// v2.4.53 Faz 8 — KOPRU SERVISLERINE BAGLI MENU GORUNURLUGU
// Kullanici istegi: "radar ve ground control dual ... arayuzde Goktungu
// menusunun altinda EGER ONLINE ISE gorunmeli, ayni zamanda radar
// menusu de radar online ise gorunmeli."
//
// Merkezde calisan ornekte bu iki yetenek artik KOPRU SERVISIDIR:
// saha makinesindeki `radar` ve `gcsdual` servisleri. Bu yuzden menu
// gorunurlugu program ayarinin YANINDA kopru servis durumuna da
// baglanir.
//
// LOKAL KURULUM DAVRANISI KORUNUR: kopru listesi bos oldugunda
// (`_kopruServisBilgiVar = false`) karar YALNIZCA program ayarina
// bakar — v2.4.24 davranisi birebir surer. Aksi halde koprusu olmayan
// yerel kurulumda Radar menusu kaybolurdu.
// ---------------------------------------------------------------
let _kopruServisBilgiVar = false;   // kopru listesi hic geldi mi
let _kopruRadarAcik = false;        // herhangi bir koprude radar calisiyor
let _kopruGcsdualAcik = false;      // herhangi bir koprude gcsdual calisiyor
let _kopruM50Acik = false;          // herhangi bir Köprüde M50 HVS hizmeti çalışıyor
let _m50YerelAcik = false;          // v2.4.199: Merkez'in kendi gömülü SDK'sı kullanılabilir (köprüsüz)
// v2.4.56: merkezde mi calisiyoruz. Sunucu `kopru_liste` yanitinda
// bildirir (bkz. sunucu.py). Menu kurali merkezde ve lokalde FARKLIDIR:
// merkezde yetenegin kaynagi kopru servisidir, lokalde program ayari.
let _kopruMerkezKipi = false;

// Bir servisin herhangi bir CEVRIMICI koprude calisip calismadigi.
// Cevrimdisi koprunun servis durumu bilinmez (`servisler: null`);
// bilinmeyen durum "calisiyor" sayilmaz.
function _kopruServisiCalisiyorMu(kopruler, ad){
  for (const k of (kopruler || [])){
    if (!k || !k.cevrimici) continue;
    for (const s of (k.servisler || [])){
      const sad = String((s && (s.ad || s.servis)) || "").toLowerCase();
      if (sad !== ad) continue;
      const d = String((s && s.durum) || "").toLowerCase();
      if (s.calisiyor === true || d === "calisiyor" || d === "acik")
        return true;
    }
  }
  return false;
}

// v2.4.59: GCCDUAL cantasi TAKILI olabilecek saha makineleri.
// Panelin makine secicisini besler.
//
// Neden gerekli: bir firma birden fazla kopru isletebilir (arac basi
// bir canta). Merkez, hangi makinede `gcsdual` calistigini tarayip tek
// aday varsa onu kendisi secer; IKI ve daha fazla adayda secim
// zorunludur ve karar PILOTUN olmalidir. Liste burada tutulmazsa panel
// secici cizemez ve pilot "Panelden makine secin" hatasini okur ama
// secebilecegi bir yer bulamaz.
let _kopruGcsdualListe = [];        // [{ornek_id, ad}]
// v2.4.60: RADAR da ayni sebeple makine bazlidir. Radar, kopru
// makinesinin yerel agindaki bir cihazdir (orn. 192.168.8.168);
// merkez sunucudan erisilemez.
let _kopruRadarListe = [];          // [{ornek_id, ad}]
let _kopruM50Liste = [];            // [{ornek_id, ad}] — fiziksel HVS yalnız saha Köprüsündedir

// Servis adi parametreli: gcsdual ve radar ayni mantigi paylasir.
// Iki ayri kopya tutulursa biri guncellenip diger unutulur.
function _kopruServisAdaylari(kopruler, servis_adi){
  const hedef = String(servis_adi || "").toLowerCase();
  const cikti = [];
  for (const k of (kopruler || [])){
    if (!k || !k.cevrimici) continue;
    let calisiyor = false;
    for (const s of (k.servisler || [])){
      const sad = String((s && (s.ad || s.servis)) || "").toLowerCase();
      if (sad !== hedef) continue;
      const d = String((s && s.durum) || "").toLowerCase();
      if (s.calisiyor === true || d === "calisiyor" || d === "acik"){
        calisiyor = true;
        break;
      }
    }
    if (!calisiyor) continue;
    const oid = parseInt(k.ornek_id, 10);
    if (!(oid > 0)) continue;
    cikti.push({
      ornek_id: oid,
      ad: String(k.ad || k.kurulum_uid || ("#" + oid))
    });
  }
  return cikti;
}

// Geriye donuk ad: mevcut cagiranlar bozulmasin.
function _kopruGcsdualAdaylari(kopruler){
  return _kopruServisAdaylari(kopruler, "gcsdual");
}

// istasyon2.js secici cizerken bunu sorar.
window.kopruGcsdualAdaylari = function(){
  return _kopruGcsdualListe.slice();
};

// radar_panel.js secici cizerken bunu sorar.
window.kopruRadarAdaylari = function(){
  return _kopruRadarListe.slice();
};

// m50_panel.js saha Köprüsü seçicisini bu doğrulanmış servis listesinden besler.
window.kopruM50Adaylari = function(){
  return _kopruM50Liste.slice();
};

// seri.js her kopru listesi yanitinda cagirir.
window.kopruServisMenuleriGuncelle = function(kopruler, merkezKipi){
  const liste = Array.isArray(kopruler) ? kopruler : [];
  if (typeof merkezKipi === "boolean") _kopruMerkezKipi = merkezKipi;
  _kopruServisBilgiVar = liste.length > 0;
  _kopruRadarAcik = _kopruServisiCalisiyorMu(liste, "radar");
  _kopruGcsdualAcik = _kopruServisiCalisiyorMu(liste, "gcsdual");
  _kopruM50Acik = _kopruServisiCalisiyorMu(liste, "m50");
  _kopruGcsdualListe = _kopruServisAdaylari(liste, "gcsdual");
  _kopruRadarListe = _kopruServisAdaylari(liste, "radar");
  _kopruM50Liste = _kopruServisAdaylari(liste, "m50");
  if (typeof window.istasyon2KopruListesiGuncelle === "function")
    window.istasyon2KopruListesiGuncelle(_kopruGcsdualListe);
  if (typeof window.radarKopruListesiGuncelle === "function")
    window.radarKopruListesiGuncelle(_kopruRadarListe);
  if (typeof window.m50KopruListesiGuncelle === "function")
    window.m50KopruListesiGuncelle(_kopruM50Liste);
  radarMenuGorunumGuncelle();
  m50MenuGorunumGuncelle();
  progAyarMenuGorunumGuncelle();
  if (typeof window.istasyon2MenuGorunumGuncelle === "function")
    window.istasyon2MenuGorunumGuncelle();
  // v2.4.58 — kullanici istegi: "radar menude gorunmuyorsa radar
  // halkalari ve radar ikonlari gorunmesin". Onceden BURADA yalniz
  // menu tazeleniyordu; harita gorunumu `radarAyarSunucu`ya bagli
  // kaldigi icin kopruda radar KAPALIYKEN menu gizlenirken kapsama
  // halkalari, izgara ve radar ikonu haritada cizilmeye devam
  // ediyordu. Artik ayni yetenek karari haritaya da uygulanir.
  radarModuUygula(radarYetenekVar());
};

// ---------------------------------------------------------------
// v2.4.58 — RADAR YETENEGININ TEK KARAR KAYNAGI
//
// Menu gorunurlugu ile harita gorunurlugu onceden IKI AYRI kaynaktan
// besleniyordu: menu kopru servis durumuna (v2.4.56), harita ise
// sunucudaki `radar_arayuz` ayarina. Iki kaynak ayrildigi anda
// "menude yok ama haritada var" celiskisi kacinilmaz hale gelir.
// Karar tek yerde uretilir ve her iki katman bunu okur.
//
// MERKEZ KIPI: radar donanimi sahadadir, yetenegin tek kaniti koprude
//   `radar` servisinin calismasidir.
// LOKAL KURULUM: kopru kavrami yoktur; karar program ayarina kalir
//   (v2.4.24 davranisi birebir korunur).
// ---------------------------------------------------------------
// v2.4.65 — UCUNCU KIP: MERKEZ UYGULAMA LISANSI
//
// Kullanici istegi (birebir): "radar yada gccdual acik olan sirketlerin
// indirdigi merkezi yazilimda bu modullerde acik olsun."
//
// Lisans, yetenegin UST SINIRIDIR; donanimin KANITI degildir. Ikisi
// AYRI sorulardir ve birlikte aranmalidir:
//
//   lisans.radar        -> "bu sirket radar satin aldi mi?"
//   kopru servisi/ayar  -> "radar donanimi gercekten bagli mi?"
//
// YALNIZ lisansa bakmak, v2.4.56'da giderilen kusuru geri getirirdi:
// radar yetkisi olan ama donanimi bagli olmayan kurulumda menu gorunur
// kalir, tiklayinca islevsiz panel acilir.
//
// YALNIZ servise/ayara bakmak ise yetkisiz kullanima kapi acardi:
// radar satin almamis sirket program ayarini elle acabilir.
//
// LISANS DOSYASI YOKSA ust sinir UYGULANMAZ (`lisansli === false`).
// Olagan kurulum ve merkez ornegi boylece birebir eski
// davranisini surdurur; lisans yalnizca Merkez Uygulama kipinde soz
// sahibidir.
let _lisansOzet = null;         // sunucudan gelen `ayarlar.lisans`

function lisansUstSinir(alan){
  // Donus: true  -> sinir yok ya da yetki var
  //        false -> lisansli kurulum ama bu yetki KAPALI
  if (!_lisansOzet || !_lisansOzet.lisansli) return true;
  return !!_lisansOzet[alan];
}
window.lisansUstSinir = lisansUstSinir;
window.lisansOzetiAl = function(){ return _lisansOzet; };

// harita.js/ayarlariUygula her ayar duyurusunda cagirir.
window.lisansOzetiSunucudan = function(o){
  _lisansOzet = (o && typeof o === "object") ? o : null;
  radarMenuGorunumGuncelle();
  m50MenuGorunumGuncelle();
  radarModuUygula(radarYetenekVar());
  if (typeof window.istasyon2MenuGorunumGuncelle === "function")
    window.istasyon2MenuGorunumGuncelle();
};

function radarYetenekVar(){
  const donanim = _kopruMerkezKipi ? _kopruRadarAcik : radarAyarSunucu;
  return donanim && lisansUstSinir("radar");
}
window.radarYetenekVar = radarYetenekVar;

// M50 HVS SDK yalnız Windows x64 saha Köprüsünde çalışır. Merkez veya
// bağımsız GCS'de fiziksel cihaz hizmeti yoksa menü kapalı kalır; lisans
// özeti bu donanım kanıtının yerine geçmez.
function m50YetenekVar(){
  // v2.4.199: koprusuz (dogrudan SDK) kurulumda da menu acilir.
  return (!!_kopruM50Acik || !!_m50YerelAcik) && lisansUstSinir("m50");
}
window.m50YerelDurum = function(v){
  const yeni = !!v;
  if (yeni === _m50YerelAcik) return;
  _m50YerelAcik = yeni;
  m50MenuGorunumGuncelle();
};
window.m50YetenekVar = m50YetenekVar;

function m50MenuGorunumGuncelle(){
  const mb = document.getElementById("mbM50");
  if (!mb) return;
  const goster = m50YetenekVar() && radarIzlemeIzniVar();
  mb.style.display = goster ? "" : "none";
  if (!goster){
    const pop = document.getElementById("yzM50");
    if (pop) pop.classList.add("yuzen-gizli");
  }
}
window.m50MenuGorunumGuncelle = m50MenuGorunumGuncelle;

// ---------------------------------------------------------------
// v2.4.57 — PROGRAM AYARLARI MENUSU MERKEZDE TAMAMEN KALDIRILIR
//
// Kullanici istegi (birebir): "artik bir servis yonetimine gerek yok
// onu sen merkez sunucuda yonetiyorsun, bilgisayarda otomatik baslat
// gibi ayarlarda gereksiz, bence program ayarlari menusunu tamamen
// kaldir".
//
// Menudeki her bolum merkezde ANLAMSIZ ve dahasi YANILTICI:
//   C20 RADAR / GCCDUAL anahtarlari  -> yetenek artik kopru servisinde
//     (v2.4.56); merkezdeki anahtarin menu uzerinde soz hakki yok.
//   GCCDUAL seri port (/dev/ttyACM0) -> aygit kopru makinesinde;
//     merkez sunucusunda boyle bir seri port yok.
//   Servis durumu / otomatik baslat  -> merkezin systemd birimi
//     (`goktungu-app`) operator tarafindan yonetilir. Arayuz "KURULU
//     DEGIL / bash kur_2449.sh --servis" yaziyordu, oysa surec PID
//     449992 ile CALISIYORDU: olculen, dogrudan yaniltici bir gosterge.
//   MERKEZ SUNUCU anahtari           -> merkezin kendisi merkez.
//
// AYRICA KRITIK: ayarlar merkezde TEK deposunda tutulur. Bir firmanin
// yoneticisi radar anahtarini kapatsa TUM firmalari etkiler. Menuyu
// gizlemek bu ortak-durum kazasini da kapatir.
//
// LOKAL KURULUM DEGISMEZ: `_kopruMerkezKipi` yalnizca merkezde calisan
// ornekte true olur (sunucu `kopru_liste` yanitinda bildirir). Kullanici
// sahada v2.4.24 ile ucuyor; o kurulumda menu ve tum bolumleri aynen
// kalir.
// ---------------------------------------------------------------
function progAyarMenuGorunumGuncelle(){
  const oge = document.getElementById("mbProgramAyar");
  if (oge) oge.style.display = _kopruMerkezKipi ? "none" : "";
  // Menu gizlenirken ACIK popup varsa kapatilir: kullanici menuyu
  // gizlemeden once acmis olabilir ve panel ekranda asili kalir.
  if (_kopruMerkezKipi){
    const pop = document.getElementById("programAyarPopup");
    if (pop) pop.remove();
  }
}
window.progAyarMenuGorunumGuncelle = progAyarMenuGorunumGuncelle;

// Merkezde mi. programAyarAc() ve harici cagiranlar icin.
window.progAyarMerkezKipiMi = function(){ return !!_kopruMerkezKipi; };

// istasyon2.js menu gorunurlugunu hesaplarken bunu sorar.
// Donen deger: null -> kopru bilgisi yok (program ayarina bak),
//              true/false -> koprude gcsdual servisi calisiyor mu.
window.kopruGcsdualDurumu = function(){
  // v2.4.56: merkez kipinde kopru servisi TEK yetkilidir. Kopru
  // listesi bos olsa bile (hic kopru kaydolmamis) yanit `false`
  // olmalidir: "koprusu olmayan merkez kullanicisinda GroundGCC
  // menusu gorunmez". Lokal kurulumda karar program ayarina kalir.
  if (_kopruMerkezKipi) return _kopruGcsdualAcik;
  return _kopruServisBilgiVar ? _kopruGcsdualAcik : null;
};

// ---------------------------------------------------------------
// RADAR MENUSU GORUNURLUGU
// Kosul: (program ayari ACIK **veya** koprude radar servisi calisiyor)
// **ve** kullanicinin radar.izleme izni var. Degilse ust bardaki
// "Radar" menusu tamamen gizlenir.
// ---------------------------------------------------------------
function radarMenuGorunumGuncelle(){
  const mb = document.getElementById("mbRadar");
  if (!mb) return;
  // v2.4.56 — kullanici istegi: "radarin koprusunu baslatmadiysam eger
  // radar menusu gorunmemeli."
  //
  // MERKEZ KIPI: yetenegin kaynagi YALNIZ kopru servisidir. Onceki
  // surumde program ayari ile VEYA'lanmisti; bu, koprude radar
  // kapaliyken menuyu gorunur birakiyordu. Merkezde radar donanimi
  // sahadadir — merkezin kendi program ayarinin radar yetenegi
  // uzerinde soz hakki yoktur.
  //
  // LOKAL KURULUM: kopru kavrami yok, karar program ayarina kalir
  // (v2.4.24 davranisi birebir korunur).
  // v2.4.58: kosul artik burada tekrarlanmiyor; tek karar kaynagi
  // radarYetenekVar(). Kosulun iki yerde kopyalanmasi zaten haritanin
  // menuden ayri dusmesine yol acmisti.
  const goster = radarYetenekVar() && radarIzlemeIzniVar();
  mb.style.display = goster ? "" : "none";
}
window.radarMenuGorunumGuncelle = radarMenuGorunumGuncelle;

// ---------------------------------------------------------------
// HARITA VARLIKLARINI GIZLE/GOSTER
// radar_gorsel.js ve hedefler.js'deki global varliklar uzerinden.
// Varliklar CallbackProperty ile canli calistigindan show=false yeterli.
// ---------------------------------------------------------------
function radarHaritaGorunum(acik){
  if (typeof viewer === "undefined" || !viewer) return;
  const goster = (e, g) => { if (e) e.show = g; };
  try {
    // Kapsama izgarasi (halkalar, mesafe etiketleri, azimut cizgileri)
    if (typeof kapsamaVarliklar !== "undefined")
      kapsamaVarliklar.forEach(e => goster(e, acik));
    // Tarama cizgisi + iz yelpazesi (radarBagli da dikkate alinir)
    const tarAcik = acik && (typeof radarBagli !== "undefined" ? radarBagli : false);
    if (typeof radarCizgi !== "undefined") goster(radarCizgi, tarAcik);
    if (typeof radarIzDilimleri !== "undefined")
      radarIzDilimleri.forEach(d => goster(d.varlik || d, tarAcik));
    // Irtifa kubbesi
    if (typeof irtifaKubbe !== "undefined") goster(irtifaKubbe, acik);
    // GCS (radar) ikonu
    if (typeof gcsVarlik !== "undefined") goster(gcsVarlik, acik);
    // Radar hedefleri + izleri
    if (typeof radarHedefVarliklar !== "undefined")
      Object.values(radarHedefVarliklar).forEach(e => goster(e, acik));
    if (typeof hedefIzVarliklar !== "undefined")
      Object.values(hedefIzVarliklar).forEach(e => goster(e, acik));
    if (typeof yetimIzVarliklar !== "undefined")
      Object.values(yetimIzVarliklar).forEach(e => goster(e, acik));
  } catch(e){ /* varliklar henuz kurulmamis olabilir */ }
}

// Radar acildiginda yeni gelen varliklar zaten show=true olusur.
// Kapaliyken hedefler.js yeni varlik ekleyebilir; periyodik supurme ile
// kapali moddayken sizan varliklar da gizlenir.
setInterval(() => { if (!radarModuAcik) radarHaritaGorunum(false); }, 2000);

// ---------------------------------------------------------------
// LOGOYU TASI
// Radar kapaliyken sol panel display:none oldugundan logo kutusu
// DOM'da haritaAlan'a tasinir (CSS orada yuzen kutu olarak konumlar);
// radar acilinca sol panelin en ustune geri konur.
// ---------------------------------------------------------------
function logoyuTasi(acik){
  const kutu = document.getElementById("sirketLogoKutu");
  if (!kutu) return;
  if (!acik){
    const harita = document.getElementById("haritaAlan");
    if (harita && kutu.parentElement !== harita)
      harita.appendChild(kutu);
  } else {
    const panel = document.getElementById("solPanel");
    if (panel && kutu.parentElement !== panel)
      panel.insertBefore(kutu, panel.firstElementChild);
  }
}

// ---------------------------------------------------------------
// MODU UYGULA
// Etkin gorunum = sunucu ayari VE kullanici izni. localStorage yalnizca
// ilk boyama onbellegi olarak guncellenir.
// ---------------------------------------------------------------
function radarModuUygula(acik){
  radarModuAcik = acik && radarIzlemeIzniVar();
  document.body.classList.toggle("radar-kapali", !radarModuAcik);
  logoyuTasi(radarModuAcik);
  radarHaritaGorunum(radarModuAcik);
  radarModuKaydet(radarModuAcik);
  radarMenuGorunumGuncelle();
  // Harita yerlesimi degisti - Cesium canvas boyutunu tazele
  try { if (typeof viewer !== "undefined" && viewer) viewer.resize(); } catch(e){}
}

// ---------------------------------------------------------------
// SUNUCU AYARI SENKRONU
// harita.js/ayarlariUygula -> window.radarAyarSunucudan(ayarlar)
// Sunucudan gelen radar_arayuz her istemcide aynen uygulanir.
// ---------------------------------------------------------------
window.radarAyarSunucudan = function(a){
  if (typeof a.radar_arayuz === "boolean"){
    radarAyarSunucu = a.radar_arayuz;
  } else {
    radarAyarSunucu = true;   // ayar hic yazilmamis -> varsayilan acik
  }
  radarModuUygula(radarYetenekVar());
  // Popup acikken durum degistiyse anahtari tazele
  const cb = document.getElementById("progRadarAnahtar");
  if (cb) cb.checked = radarAyarSunucu;
};

// Giris/rol degisiminde kullanici.js cagirir (izin degismis olabilir)
window.programAyarOturumTazele = function(){
  radarModuUygula(radarYetenekVar());
};

// ---------------------------------------------------------------
// PROGRAM AYARLARI POPUP'I
// dkMiniPopupBaslikKur (dronlar.js) ile tasinabilir + X ile kapanir.
// Yonetici olmayanlarda anahtar devre disi (sunucu ayrica denetler).
// ---------------------------------------------------------------
// v2.4.192 (kullanici bildirimi: "Program ayarlari ekrana sigmiyor"):
// her bolum acilir-kapanir <details> icine alinir; acik/kapali durumu
// tarayicida hatirlanir. Yalniz ilk bolum (radar) varsayilan aciktir.
function progBolum(govde, baslik, ikon, acik){
  const d = document.createElement("details");
  d.className = "kam-bolum prog-bolum";
  const anahtar = "progBolum_" + String(baslik).replace(/\W+/g, "_");
  let ac = !!acik;
  try {
    const k = localStorage.getItem(anahtar);
    if (k !== null) ac = (k === "1");
  } catch (e) {}
  d.open = ac;
  d.addEventListener("toggle", () => {
    try { localStorage.setItem(anahtar, d.open ? "1" : "0"); } catch (e) {}
  });
  const s = document.createElement("summary");
  s.innerHTML = "<i class='fa-solid " + ikon + "'></i> " + baslik;
  d.appendChild(s);
  const ic = document.createElement("div");
  ic.className = "prog-bolum-ic";
  d.appendChild(ic);
  govde.appendChild(d);
  return ic;
}

function programAyarAc(fare){
  // v2.4.57 KALKAN: merkezde panel HIC acilmaz. Menu ogesi gizlidir
  // ama tek savunma degildir — menubar.js hizli tus (`p`) atamasi ve
  // dis cagrilar (window.programAyarAc) ayni islevi cagirabilir. Karar
  // gorunurluge degil YETENEGE baglanir; boylece gizleme atlanirsa
  // panel yine acilmaz.
  if (_kopruMerkezKipi) return;
  // Acik popup varsa kapat (toggle davranisi)
  const eski = document.getElementById("programAyarPopup");
  if (eski) { eski.remove(); return; }
  const t = D();
  const yonetici = oturumYoneticiMi();
  const pop = document.createElement("div");
  pop.className = "dk-mini-popup prog-ayar-popup";
  pop.id = "programAyarPopup";
  // v2.4.53: konum/boyut anahtari VERILDI. Once null geciliyordu; ortak
  // yardimcidaki boyutlandirma kancasi anahtar kosuluna bagli oldugu icin
  // bu panelde resize tutamaci HIC olusmuyordu (tarayici olcumu: panel
  // 252 px'te sikisik, .popup-boyut-tutamac yok). Anahtar verilince hem
  // tasima konumu hem kullanicinin verdigi boyut kalici saklanir.
  dkMiniPopupBaslikKur(pop, t.progAyarBaslik || "PROGRAM AYARLARI",
    "pp_programAyarPopup", "fa-gears");

  const govde = document.createElement("div");
  govde.className = "prog-ayar-govde";

  // --- C20 RADAR ac/kapat satiri ---
  const bRadar = progBolum(govde, t.progAyarRadar || "C20 RADAR", "fa-satellite", true);
  const satir = document.createElement("div");
  satir.className = "prog-ayar-satir";
  const etiket = document.createElement("span");
  etiket.className = "prog-ayar-etiket";
  etiket.innerHTML = "<i class='fa-solid fa-satellite'></i> " +
    (t.progAyarRadar || "C20 RADAR");
  // Kaydirmali anahtar (toggle switch)
  const anahtar = document.createElement("label");
  anahtar.className = "prog-anahtar";
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.id = "progRadarAnahtar";
  cb.checked = radarAyarSunucu;
  cb.disabled = !yonetici;
  const kayar = document.createElement("span");
  kayar.className = "prog-anahtar-top";
  anahtar.appendChild(cb);
  anahtar.appendChild(kayar);
  if (!yonetici) anahtar.classList.add("prog-anahtar-kilitli");
  cb.addEventListener("change", () => {
    if (!yonetici){ cb.checked = radarAyarSunucu; return; }
    // Sunucuya yaz; onay "ayarlar" duyurusuyla gelir ve tum
    // istemcilerde radarAyarSunucudan uygulanir.
    if (typeof ws !== "undefined" && ws && ws.readyState === 1){
      ws.send(JSON.stringify({tip: "program_ayar_yaz",
                              radar_arayuz: cb.checked}));
      aciklama.textContent = cb.checked
        ? (t.progAyarRadarAcik || "Radar arayuzu aktif")
        : (t.progAyarRadarKapali || "Radar arayuzu gizlendi");
    } else {
      cb.checked = radarAyarSunucu;   // sunucu yoksa degistirme
    }
  });
  satir.appendChild(etiket);
  satir.appendChild(anahtar);
  bRadar.appendChild(satir);

  const aciklama = document.createElement("div");
  aciklama.className = "prog-ayar-aciklama";
  aciklama.textContent = radarAyarSunucu
    ? (t.progAyarRadarAcik || "Radar arayuzu aktif")
    : (t.progAyarRadarKapali || "Radar arayuzu gizlendi");
  bRadar.appendChild(aciklama);

  // ---------------------------------------------------------------
  // v2.4.45: GCCDUAL - Yer Kontrol Istasyonu Dual ac/kapat + port
  // Kullanici istegi: "aynen radar gibi program ayarlarindan acilip
  // kapatilabilmeli; kapali ise menude gorunmemeli. Acilistada program
  // ayarlarinda varsa baglanmaya calismali."
  // ---------------------------------------------------------------
  const bIst2 = progBolum(govde, t.progAyarIst2 || "Yer Kontrol \u0130stasyonu Dual",
                          "fa-gamepad", false);

  const ist2Acik = (typeof window.istasyon2ArayuzAcikMi === "function")
    ? window.istasyon2ArayuzAcikMi() : false;

  const s2 = document.createElement("div");
  s2.className = "prog-ayar-satir";
  const e2 = document.createElement("span");
  e2.className = "prog-ayar-etiket";
  e2.innerHTML = "<i class='fa-solid fa-gamepad'></i> " +
    (t.progAyarIst2 || "Yer Kontrol \u0130stasyonu Dual");
  const an2 = document.createElement("label");
  an2.className = "prog-anahtar";
  const cb2 = document.createElement("input");
  cb2.type = "checkbox";
  cb2.id = "progIst2Anahtar";
  cb2.checked = ist2Acik;
  cb2.disabled = !yonetici;
  const k2 = document.createElement("span");
  k2.className = "prog-anahtar-top";
  an2.appendChild(cb2); an2.appendChild(k2);
  if (!yonetici) an2.classList.add("prog-anahtar-kilitli");
  s2.appendChild(e2); s2.appendChild(an2);
  bIst2.appendChild(s2);

  const a2 = document.createElement("div");
  a2.className = "prog-ayar-aciklama";
  const a2Yaz = (v) => {
    a2.textContent = v
      ? (t.progAyarIst2Acik || "GCCDUAL etkin (G\u00f6ktungu men\u00fcs\u00fcnde)")
      : (t.progAyarIst2Kapali || "GCCDUAL kapal\u0131 (men\u00fcde g\u00f6r\u00fcnmez)");
  };
  a2Yaz(ist2Acik);
  bIst2.appendChild(a2);

  // Seri port satiri (yalniz cihaz acikken anlamli)
  const sp = document.createElement("div");
  sp.className = "prog-ayar-satir prog-ayar-port";
  const spE = document.createElement("span");
  spE.className = "prog-ayar-etiket";
  spE.innerHTML = "<i class='fa-solid fa-plug'></i> " +
    (t.progAyarIst2Port || "GCCDUAL seri port");
  const spG = document.createElement("input");
  spG.type = "text";
  spG.id = "progIst2Port";
  spG.className = "prog-ayar-giris";
  spG.placeholder = "/dev/ttyACM0";
  spG.disabled = !yonetici;
  sp.appendChild(spE); sp.appendChild(spG);
  bIst2.appendChild(sp);

  const spA = document.createElement("div");
  spA.className = "prog-ayar-aciklama";
  spA.textContent = t.progAyarIst2PortAcik ||
    "Windows'ta COM7 gibi; a\u00e7\u0131l\u0131\u015fta bu porta ba\u011flan\u0131l\u0131r.";
  bIst2.appendChild(spA);

  // Mevcut degeri sunucudan doldur (ayarlar duyurusu ile gelir)
  if (typeof window.progIst2PortDegeri === "string")
    spG.value = window.progIst2PortDegeri;

  const ist2GorunumTazele = (v) => {
    sp.style.display = v ? "" : "none";
    spA.style.display = v ? "" : "none";
  };
  ist2GorunumTazele(ist2Acik);

  cb2.addEventListener("change", () => {
    if (!yonetici){ cb2.checked = ist2Acik; return; }
    if (typeof ws !== "undefined" && ws && ws.readyState === 1){
      ws.send(JSON.stringify({tip: "program_ayar_yaz",
                              istasyon2_arayuz: cb2.checked}));
      a2Yaz(cb2.checked);
      ist2GorunumTazele(cb2.checked);
    } else {
      cb2.checked = ist2Acik;
    }
  });

  const portGonder = () => {
    if (!yonetici) return;
    if (typeof ws !== "undefined" && ws && ws.readyState === 1){
      ws.send(JSON.stringify({tip: "program_ayar_yaz",
                              istasyon2_port: spG.value.trim()}));
    }
  };
  spG.addEventListener("change", portGonder);
  spG.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter"){ ev.preventDefault(); spG.blur(); }
  });

  // v2.4.49: SERVIS bolumu (systemd). Kullanici istegi: "arayuzde
  // servisi durdurup baslatabilecegim program ayarlarinda bir bolum
  // olsun, bilgisayar acildiginda otomatik acilsin".
  // Durum SUNUCUDAN gelir (servis_durum); bolum kendini yeniden cizer.
  if (typeof window.svBolumEkle === "function")
    window.svBolumEkle(progBolum(govde, t.progAyarServisBaslik || "Servis durumu", "fa-gears", false));

  // v2.4.53: MERKEZ SUNUCU bolumu. Baglanti yoneticisindeki "acik
  // sunucular" listesi merkezden gelir; merkez hesabi burada girilir.
  if (typeof window.merkezBolumEkle === "function")
    window.merkezBolumEkle(progBolum(govde, t.progAyarMerkezBaslik || "Merkez Sunucu",
                                     "fa-tower-broadcast", false));

  // v2.4.67: KOPRU KIMLIKLERI bolumu. Merkez Uygulama'yi satin alan
  // sirket kapali devre calisabilir; saha bilgisayarlarindaki kopru
  // yazilimi buluta degil BU kuruluma baglanir. Kimlikler burada
  // uretilir. Merkez kipinde bolum kendini gizler (kimlikler kurumsal
  // panelden yonetilir).
  // BULGU_07: DJI KOPRU BELIRTECI bolumu. GDP protokolu (8790)
  // `merhaba` mesajinda belirtec ister; belirtec olmadan uzak DJI
  // baglantilari reddedilir. Kullanici belirteci buradan uretip
  // Android kopru uygulamasina girer.
  if (typeof window.djiBelirtecBolumEkle === "function")
    window.djiBelirtecBolumEkle(progBolum(govde, t.progAyarDjiBaslik || "DJI K\u00f6pr\u00fc Belirteci",
                                          "fa-key", false));
  if (typeof window.kopruKimlikBolumEkle === "function")
    window.kopruKimlikBolumEkle(progBolum(govde, t.progAyarKimlikBaslik || "K\u00f6pr\u00fc Kimlikleri",
                                          "fa-id-badge", false));

  // Yonetici olmayan icin bilgilendirme
  if (!yonetici){
    const uyari = document.createElement("div");
    uyari.className = "prog-ayar-aciklama prog-ayar-kilit-uyari";
    uyari.innerHTML = "<i class='fa-solid fa-lock'></i> " +
      (t.progAyarYalnizYonetici ||
       "Program ayarlar\u0131n\u0131 yaln\u0131zca y\u00f6netici de\u011fi\u015ftirebilir.");
    govde.appendChild(uyari);
  }

  pop.appendChild(govde);
  pop.style.position = "fixed";
  pop.style.zIndex = "3000";
  document.body.appendChild(pop);
  dkMiniPopupKonumla(pop, fare);
}

// ---------------------------------------------------------------
// KURULUM
// ---------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("btnProgramAyar");
  if (btn) btn.addEventListener("click", (ev) => {
    ev.stopPropagation();
    programAyarAc({x: ev.clientX, y: ev.clientY});
  });
  // Ilk boyama: localStorage onbellegi (titremeyi onler); sunucudan
  // "ayarlar" mesaji gelince radarAyarSunucudan gercek degeri uygular.
  radarAyarSunucu = radarModuOku();
  // v2.4.58 — ILK BOYAMADA MERKEZ KIPI HENUZ BILINMIYOR.
  // `_kopruMerkezKipi` baslangicta false oldugu icin radarYetenekVar()
  // bu anda onbellekteki program ayarini dondurur. Merkezde radar
  // koprusu kapali olsa bile onbellek "acik" ise halkalar bir an
  // cizilir ve `kopru_liste` yaniti gelene kadar ekranda kalir. Bu,
  // kullanicinin bildirdigi "menude yok ama haritada var" durumunun
  // gecici bicimidir. Merkez kipi tespiti icin merkez_kimlik'e degil
  // adres yoluna bakilir: merkezde arayuz /app/ altindan sunulur.
  const merkezYolu = /^\/app(\/|$)/.test(location.pathname);
  radarModuUygula(merkezYolu ? false : radarYetenekVar());
  // v2.4.57: menu gorunurlugu ilk boyamada da degerlendirilir. Merkez
  // kipi henuz bilinmiyorsa (`kopru_liste` yaniti gelmedi) oge gorunur
  // kalir ve ilk yanitla gizlenir; yanlis tarafta hata yapmak yerine
  // lokal davranis varsayilir.
  progAyarMenuGorunumGuncelle();
});
