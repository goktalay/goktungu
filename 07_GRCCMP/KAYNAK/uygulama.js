/* ==========================================================================
   GÖKTUNGU MÜŞTERİ PANELİ — /company/
   --------------------------------------------------------------------------
   Kurum kullanıcısının KENDİ firmasına ait uçuş, video, dron ve istasyon
   kayıtlarını gösterir. Yönetim panelinden (/admin/) tamamen ayrıdır:

   - Kimlik alanı ayrı: `goktungu_firma` kurabiyesi (admin `goktungu_admin`)
   - Veri alanı ayrı: her uç `firma_id`'yi OTURUMDAN okur, istekten ASLA
   - Yetki daraltma: rol `pilot` ise yalnız kendi uçuş/videosunu görür

   Bu dosya admin panelinin doğrulanmış yardımcılarını (biçimleyiciler,
   pencere yönetimi, SVG çizimler) aynı davranışla yeniden kullanır;
   kopyalamak yerine ortak dosyaya taşımak iki panelin sürüm bağımlılığını
   birbirine kilitlerdi, bu yüzden bilinçli olarak ayrı tutuldu.
   ======================================================================== */
'use strict';

const D = document;
const el = (s, k) => (k || D).querySelector(s);
const els = (s, k) => Array.from((k || D).querySelectorAll(s));

let BEN = null;               // oturum açan kurum kullanıcısı
let KURUM = null;             // firma özeti (gösterge yanıtından)
const DURUM = {};             // sayfa başına geçici durum

/* ---------------------------------------------------------------- yardımcı */
function kacir(m) {
  return String(m === null || m === undefined ? '' : m)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function bildir(mesaj, tur) {
  const d = D.createElement('div');
  d.className = 'bildirim ' + (tur || 'bilgi');
  d.textContent = mesaj;
  el('#bildirimler').appendChild(d);
  setTimeout(() => d.remove(), 5000);
}

async function cagir(yol, secenek) {
  const s = Object.assign({ credentials: 'same-origin', headers: {} },
    secenek || {});
  if (s.body && typeof s.body !== 'string') {
    s.headers['Content-Type'] = 'application/json';
    s.body = JSON.stringify(s.body);
  }
  const y = await fetch(yol, s);
  let veri = {};
  try { veri = await y.json(); } catch (e) { /* gövdesiz yanıt */ }
  if (y.status === 401 && BEN) { oturumBitti(); throw new Error('Oturum sona erdi'); }
  if (!y.ok) throw new Error(veri.hata || ('HTTP ' + y.status));
  return veri;
}

function tarih(x, saatli) {
  if (!x) return '—';
  const t = new Date(x);
  if (isNaN(t)) return '—';
  const p = (n) => String(n).padStart(2, '0');
  const g = `${p(t.getDate())}.${p(t.getMonth() + 1)}.${t.getFullYear()}`;
  return saatli === false ? g : `${g} ${p(t.getHours())}:${p(t.getMinutes())}`;
}

function sure(sn) {
  if (sn === null || sn === undefined) return '—';
  sn = Math.round(Number(sn) || 0);
  const s = Math.floor(sn / 3600), d = Math.floor((sn % 3600) / 60), k = sn % 60;
  return s > 0 ? `${s} sa ${d} dk` : (d > 0 ? `${d} dk ${k} sn` : `${k} sn`);
}

function sayi(x, basamak) {
  if (x === null || x === undefined || x === '') return '—';
  return Number(x).toLocaleString('tr-TR', {
    minimumFractionDigits: basamak || 0, maximumFractionDigits: basamak || 0
  });
}

function bayt(x) {
  x = Number(x || 0);
  const b = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  while (x >= 1024 && i < b.length - 1) { x /= 1024; i++; }
  return `${x.toFixed(i ? 1 : 0)} ${b[i]}`;
}

function rozet(metin, renk) {
  return `<span class="im-rozet r-${renk}">${kacir(metin)}</span>`;
}

/* ------------------------------------------------------ paket listeleme */

/* OLCULEN KUSUR (2026-08-16): depo 27 kopru + 4 merkez surumu tasiyor ve
 * panel HEPSINI duz liste olarak basiyordu (1.1.1'e kadar).  Kullanici en
 * guncel paketi onlarca satir arasinda ariyor, yanlislikla eski surumu
 * sahaya kurabiliyordu.  Cozum: en guncel surum one cikar, eskiler
 * katlanmis <details> icinde kalir.
 *
 * NEDEN KENDI KARSILASTIRICIMIZ: `localeCompare(numeric:true)` "1.4.10" ile
 * "1.4.9"u dogru siralamaz cunku parcalari ayri ayri degil butun metin
 * olarak tartar.  Depo `surum` alanini metin tuttugu icin siralamayi
 * burada bilesen bazinda yapmak zorundayiz. */
function surumKarsilastir(a, b) {
  const p = (s) => String(s || '').split('.').map((x) => parseInt(x, 10) || 0);
  const x = p(a);
  const y = p(b);
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    const f = (y[i] || 0) - (x[i] || 0);
    if (f) return f;                 /* buyuk surum ONCE gelir */
  }
  return 0;
}

/* Paket satiri; `ucYol` indirme ucunun yolu ('kopru_indir'/'merkez_indir'). */
function paketSatiri(k, ucYol, oneCikan) {
  return `
    <div class="paket-satir${oneCikan ? ' paket-guncel' : ''}">
      <div class="paket-bilgi">
        <strong>v${kacir(k.surum)}${
          oneCikan ? ' <span class="paket-etiket">en güncel</span>' : ''
        }</strong>
        <span>${kacir(k.dosya_ad)} · ${bayt(k.dosya_boyut)}</span>
        <span class="paket-ts">${tarih(k.yayin_ts)}</span>
      </div>
      <a class="dugme${oneCikan ? '' : ' ikincil'}" href="/api/firma/${
        ucYol}?surum=${encodeURIComponent(k.surum)}&dosya=${
        encodeURIComponent(k.dosya_ad)}">İndir</a>
    </div>`;
}

/* ---------------------------------------------- guncellik uyarisi
 * [IS52-APP-SURUM-V1]
 * NEDEN VAR: Merkez Uygulamasi paketleri artik her iste otomatik
 * uretilmiyor; yalniz kullanici acikca istediginde yeni surum
 * yayinlaniyor. Bu yuzden depodaki paket, canli App surumunun
 * gerisinde kalabilir. Kullanici bunu indirmeden ONCE bilmeli.
 *
 * `app_guncel` sunucudan gelir (merkez, App surumunu dosyadan okur).
 * `k.app_surum` paketin tasidigi App surumudur; depoda ACIKCA yazilir,
 * serbest metinden tahmin edilmez.
 *
 * UC DURUM VAR ve ucu de AYRI ele alinir:
 *   1. Ikisi de bilinir ve paket geride  -> uyari
 *   2. Ikisi de bilinir ve paket guncel  -> uyari yok
 *   3. Biri bilinmiyor                   -> "bilinmiyor" uyarisi
 * Ucuncu durumda sessiz kalmak, kullaniciya yanlis guven verirdi. */
function guncellikDurumu(k, appGuncel) {
  const pk = String((k && k.app_surum) || '').trim();
  const cn = String(appGuncel || '').trim();
  if (!pk || !cn) return { hal: 'bilinmiyor', paket: pk, canli: cn };
  /* surumKarsilastir BUYUK surumu ONE alir: sonuc < 0 ise a > b. */
  const f = surumKarsilastir(pk, cn);
  if (f > 0) return { hal: 'eski', paket: pk, canli: cn };
  return { hal: 'guncel', paket: pk, canli: cn };
}
/* Kart ustunde gosterilen uyari seridi. */
function guncellikSeridi(d) {
  if (!d || d.hal === 'guncel') return '';
  if (d.hal === 'bilinmiyor') {
    return `<div class="paket-uyari paket-uyari-bilinmiyor">
      <strong>Paket sürümü doğrulanamadı.</strong>
      Bu paketin hangi GÖKTUNGU sürümünü taşıdığı depoda kayıtlı değil.
      Kurulumdan sonra arayüz sürümünü <em>Hakkında</em> penceresinden
      doğrulayın.</div>`;
  }
  return `<div class="paket-uyari">
    <strong>Bu paket güncel değil.</strong>
    Paket <code class="kod">${kacir(d.paket)}</code> sürümünü taşıyor;
    çevrimiçi GÖKTUNGU arayüzü <code class="kod">${kacir(d.canli)}</code>
    sürümünde. Merkez Uygulama paketleri istek üzerine yayımlanır;
    yeni sürüm gerekiyorsa destek üzerinden talep edebilirsiniz.</div>`;
}
/* Bir platformun paket karti: en guncel one cikar, eskiler katlanir. */
function paketKarti(baslik, liste, ipucu, ucYol, appGuncel) {
  if (!liste.length) {
    return `<div class="pano">
      <div class="pano-baslik">${baslik}</div>
      <p class="bos">Bu platform için paket yayınlanmadı.</p>
      <p class="aciklama">${ipucu}</p>
    </div>`;
  }
  const sirali = liste.slice().sort((a, b) => surumKarsilastir(a.surum, b.surum));
  const guncel = sirali[0];
  const eski = sirali.slice(1);
  /* `appGuncel` GECILMEZSE serit hic uretilmez; kopru sayfasinin
   * davranisi birebir korunur (uyari yalniz Merkez Uygulamasi
   * kartinda istendi). */
  const gd = appGuncel === undefined
    ? null : guncellikDurumu(guncel, appGuncel);
  return `<div class="pano">
    <div class="pano-baslik">${baslik}</div>
    ${guncellikSeridi(gd)}
    ${paketSatiri(guncel, ucYol, true)}
    ${eski.length ? `<details class="paket-eski">
      <summary>Önceki sürümler (${eski.length})</summary>
      ${eski.map((k) => paketSatiri(k, ucYol, false)).join('')}
      <p class="aciklama">Önceki sürümler yalnızca geri dönüş (rollback)
        gerektiğinde kullanılmalıdır. Yeni kurulumlarda en güncel sürümü
        tercih edin.</p>
    </details>` : ''}
    <p class="aciklama">${ipucu}</p>
  </div>`;
}

const DURUM_RENK = { etkin: 'yesil', askida: 'sari', kapali: 'gri', pasif: 'gri' };
const GOREV_RENK = {
  tamamlandi: 'yesil', iptal: 'kirmizi', devam: 'mavi', hazir: 'gri',
  duraklatildi: 'sari'
};
const ROL_ADI = {
  firma_yonetici: 'Kurum Yöneticisi', pilot: 'Pilot', gozlemci: 'Gözlemci'
};

/* ---------------------------------------------------------------- pencere */
function pencereAc(baslik, govde, dugmeler, genis) {
  el('#pencere-baslik').textContent = baslik;
  el('#pencere-govde').innerHTML = govde;
  el('#pencere').className = 'pencere' + (genis ? ' genis' : '');
  const alt = el('#pencere-alt');
  alt.innerHTML = '';
  (dugmeler || []).forEach((d) => {
    const b = D.createElement('button');
    b.textContent = d.metin;
    if (d.sinif) b.className = d.sinif;
    b.onclick = d.tik;
    alt.appendChild(b);
  });
  el('#perde').classList.remove('gizli');
}

function pencereKapat() {
  el('#perde').classList.add('gizli');
  el('#pencere-govde').innerHTML = '';
}
window.pencereKapat = pencereKapat;

el('#pencere-kapat').onclick = pencereKapat;
el('#perde').onclick = (o) => { if (o.target === el('#perde')) pencereKapat(); };
D.addEventListener('keydown', (o) => {
  if (o.key === 'Escape' && !el('#perde').classList.contains('gizli')) pencereKapat();
});

/* ---------------------------------------------------------------- oturum */
el('#giris-form').addEventListener('submit', async (o) => {
  o.preventDefault();
  el('#giris-hata').textContent = '';
  const dugme = el('#giris-form button');
  dugme.disabled = true;
  try {
    const y = await cagir('/api/firma/giris', {
      method: 'POST',
      body: { eposta: el('#g-eposta').value.trim(), sifre: el('#g-sifre').value }
    });
    BEN = y.kullanici;
    kabukAc();
  } catch (e) {
    el('#giris-hata').textContent = e.message;
  } finally {
    dugme.disabled = false;
  }
});

/* ---------------------------------------------------------------- kayıt
   Giriş ve kayıt aynı katmanda iki ayrı <form>; birbirini gizler.
   Kayıt başarılı olduğunda merkez zaten oturum kurabiyesi döndürür,
   bu yüzden ayrıca giriş yapılmaz — doğrudan kabuk açılır. */
function kayitGoster(ac) {
  el('#giris-form').style.display = ac ? 'none' : '';
  el('#kayit-form').style.display = ac ? '' : 'none';
  el('#giris-hata').textContent = '';
  el('#kayit-hata').textContent = '';
  el('#kayit-basari').textContent = '';
}

el('#kayit-ac').onclick = (o) => { o.preventDefault(); kayitGoster(true); };
el('#giris-ac').onclick = (o) => { o.preventDefault(); kayitGoster(false); };

/* ---------------------------------------------------------- kurum logosu
   Logo, kayıt sırasında merkeze gönderilir ve /app/ altındaki GÖKTUNGU
   arayüzü ile uçuş raporu antedinde kullanılır. Dosya `data:` URL'sine
   çevrilip kayıt gövdesine eklenir: kayıt tek istekte tamamlanır,
   böylece logo yüklenirken kayıt yarı yolda kalmaz.

   Sınır 2 MB'dır ve BURADA da denetlenir; sunucu denetimi tek başına
   yeterli olsa da 2 MB'lık gövdeyi boşuna göndermek yavaş bağlantıda
   kullanıcıyı bekletir. */
const LOGO_MAKS = 2 * 1024 * 1024;
const LOGO_TURLERI = ['image/png', 'image/jpeg', 'image/webp',
                      'image/svg+xml'];
let LOGO_VERI = '';   // data: URL veya ''

function logoSifirla() {
  LOGO_VERI = '';
  el('#k-logo').value = '';
  el('#logo-alan').classList.remove('dolu');
  el('#logo-sil').style.display = 'none';
  el('#logo-baslik').textContent = 'Logo seçin';
  el('#logo-ipucu').textContent =
    'PNG, JPEG, WEBP veya SVG — en fazla 2 MB';
  el('#logo-onizleme').innerHTML =
    '<svg viewBox="0 0 24 24" width="26" height="26" fill="none" ' +
    'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" ' +
    'stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" ' +
    'rx="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle>' +
    '<path d="M21 15l-5-5L5 21"></path></svg>';
}

function logoYukle(dosya) {
  const hata = el('#kayit-hata');
  if (!dosya) { return; }
  if (LOGO_TURLERI.indexOf(dosya.type) < 0) {
    hata.textContent = 'Logo biçimi desteklenmiyor: PNG, JPEG, WEBP ' +
                       'veya SVG kullanın.';
    logoSifirla();
    return;
  }
  if (dosya.size > LOGO_MAKS) {
    hata.textContent = 'Logo çok büyük (' +
      (dosya.size / 1048576).toFixed(1) + ' MB); en fazla 2 MB.';
    logoSifirla();
    return;
  }
  const okuyucu = new FileReader();
  okuyucu.onload = () => {
    LOGO_VERI = String(okuyucu.result || '');
    hata.textContent = '';
    el('#logo-alan').classList.add('dolu');
    el('#logo-sil').style.display = '';
    el('#logo-baslik').textContent = dosya.name;
    el('#logo-ipucu').textContent =
      (dosya.size / 1024).toFixed(0) + ' KB — değiştirmek için tıklayın';
    const g = document.createElement('img');
    g.alt = 'Kurum logosu';
    g.src = LOGO_VERI;
    el('#logo-onizleme').innerHTML = '';
    el('#logo-onizleme').appendChild(g);
  };
  okuyucu.onerror = () => {
    hata.textContent = 'Logo dosyası okunamadı.';
    logoSifirla();
  };
  okuyucu.readAsDataURL(dosya);
}

el('#logo-alan').onclick = (o) => {
  // Silme düğmesine tıklama dosya seçiciyi açmamalı.
  if (o.target.closest('#logo-sil')) { return; }
  el('#k-logo').click();
};
el('#logo-alan').onkeydown = (o) => {
  if (o.key === 'Enter' || o.key === ' ') {
    o.preventDefault();
    el('#k-logo').click();
  }
};
el('#logo-sil').onclick = (o) => {
  o.preventDefault();
  o.stopPropagation();
  logoSifirla();
};
el('#k-logo').onchange = (o) => {
  logoYukle((o.target.files || [])[0]);
};
['dragenter', 'dragover'].forEach((a) => {
  el('#logo-alan').addEventListener(a, (o) => {
    o.preventDefault();
    el('#logo-alan').classList.add('uzerinde');
  });
});
['dragleave', 'drop'].forEach((a) => {
  el('#logo-alan').addEventListener(a, (o) => {
    o.preventDefault();
    el('#logo-alan').classList.remove('uzerinde');
  });
});
el('#logo-alan').addEventListener('drop', (o) => {
  logoYukle(((o.dataTransfer || {}).files || [])[0]);
});

el('#kayit-form').addEventListener('submit', async (o) => {
  o.preventDefault();
  const hata = el('#kayit-hata');
  const basari = el('#kayit-basari');
  hata.textContent = '';
  basari.textContent = '';

  const d = (k) => el(k).value.trim();
  const sifre = el('#k-sifre').value;
  const sifre2 = el('#k-sifre2').value;

  // Sunucu da denetler; buradaki denetim yalnızca gidiş-dönüşü azaltır.
  if (sifre !== sifre2) { hata.textContent = 'Şifreler birbirinden farklı.'; return; }
  if (sifre.length < 8) { hata.textContent = 'Şifre en az 8 karakter olmalı.'; return; }

  const dugme = el('#kayit-dugme');
  dugme.disabled = true;
  const eskiMetin = dugme.textContent;
  dugme.textContent = 'Kaydediliyor…';
  try {
    const y = await cagir('/api/firma/kayit', {
      method: 'POST',
      body: {
        unvan: d('#k-unvan'),
        vergi_no: d('#k-vergi'),
        telefon: d('#k-telefon'),
        adres: d('#k-adres'),
        ad: d('#k-ad'),
        soyad: d('#k-soyad'),
        eposta: d('#k-eposta'),
        sifre: sifre,
        sifre2: sifre2,
        logo: LOGO_VERI
      }
    });
    // Logo kaydedilemediyse kayıt GEÇERLİDİR; kullanıcı Kurum
    // Bilgileri ekranından sonradan yükleyebilir. Sessiz kalmak,
    // kullanıcının logosunun neden görünmediğini anlamamasına yol açar.
    const logoNotu = y.logo_uyari
      ? ' Not: logo kaydedilemedi (' + y.logo_uyari +
        '); Kurum ekranından yeniden yükleyebilirsiniz.'
      : '';
    // Merkez kayıtla birlikte oturum açar (giris:true). Aksi hâlde
    // kullanıcıyı giriş formuna düşür.
    if (y.giris && y.kullanici) {
      BEN = y.kullanici;
      basari.textContent = 'Kurum kaydı oluşturuldu, panel açılıyor…' +
                           logoNotu;
      el('#k-sifre').value = '';
      el('#k-sifre2').value = '';
      kabukAc();
    } else {
      basari.textContent = 'Kurum kaydı oluşturuldu. Şimdi giriş ' +
                           'yapabilirsiniz.' + logoNotu;
      el('#g-eposta').value = d('#k-eposta');
      setTimeout(() => kayitGoster(false), 1200);
    }
  } catch (e) {
    hata.textContent = e.message;
  } finally {
    dugme.disabled = false;
    dugme.textContent = eskiMetin;
  }
});

el('#cikis-dugme').onclick = async () => {
  try { await cagir('/api/firma/cikis', { method: 'POST', body: {} }); } catch (e) {}
  oturumBitti();
};

function oturumBitti() {
  BEN = null;
  KURUM = null;
  el('#kabuk').classList.remove('acik');
  el('#giris-katman').style.display = 'flex';
  el('#g-sifre').value = '';
  // Çıkışta her zaman giriş formuna dön; kayıt formu açık kalmasın.
  kayitGoster(false);
}

function kabukAc() {
  el('#giris-katman').style.display = 'none';
  el('#kabuk').classList.add('acik');
  const ad = (BEN.ad || BEN.soyad)
    ? `${BEN.ad || ''} ${BEN.soyad || ''}`.trim() : BEN.eposta;
  el('#kim-bilgi').textContent = `${ad} · ${ROL_ADI[BEN.rol] || BEN.rol}`;
  el('#firma-etiket').textContent = BEN.firma_kisa_ad || BEN.firma_unvan || '';
  basligiLogoyaBagla(false);
  // Pilot rolü kurum bilgisi ve ekip listesini görmez; menüyü daralt.
  // Yonetici olmayan roller uyelik/abonelik/lisans sayfalarini gormez.
  // NEDEN SADECE 'pilot' DEGIL: gozlemci rolu de yazma yetkisine sahip
  // olmadigi icin bu sayfalari gormesi yanlis beklenti yaratir; uclar
  // 403 dondurur ve kullanici bozuk sanir.
  if (!yoneticiMiKontrol()) {
    els('nav a.oge').forEach((a) => {
      const h = a.getAttribute('href');
      if (h === '#ekip' || h === '#kurum' ||
          h === '#abonelik' || h === '#merkez') a.style.display = 'none';
    });
  }
  yonlendir();
}

/* ---------------------------------------------------------------- oturum tazeleme */
// Sayfa yenilendiğinde kurabiye hâlâ geçerliyse giriş ekranını atla.
(async function ilkAcilis() {
  try {
    const y = await cagir('/api/firma/ben');
    BEN = y.kullanici;
    kabukAc();
  } catch (e) {
    el('#giris-katman').style.display = 'flex';
  }
})();

/* ---------------------------------------------------------------- yönlendirme */
const SAYFALAR = {
  gosterge: sayfaGosterge,
  ucuslar: sayfaUcuslar,
  videolar: sayfaVideolar,
  dronlar: sayfaDronlar,
  istasyonlar: sayfaKopruler,     /* eski baglantilar icin */
  kopruler: sayfaKopruler,
  merkezler: sayfaMerkezler,
  ekip: sayfaEkip,
  abonelik: sayfaAbonelik,
  merkez: sayfaMerkez,
  kopru: sayfaKopru,
  goruntu: sayfaGoruntu,
  kurum: sayfaKurum,
  destek: sayfaDestek
};

function cipa() {
  const h = (location.hash || '#gosterge').slice(1);
  const [ad, sorgu] = h.split('?');
  const par = {};
  new URLSearchParams(sorgu || '').forEach((d, a) => { par[a] = d; });
  return { ad: SAYFALAR[ad] ? ad : 'gosterge', par };
}

async function yonlendir() {
  if (!BEN) return;
  const { ad, par } = cipa();
  els('nav a.oge').forEach((a) =>
    a.classList.toggle('etkin', a.getAttribute('href') === '#' + ad));
  el('#icerik').innerHTML = '<div class="yukleniyor">Yükleniyor…</div>';
  try {
    await SAYFALAR[ad](par);
  } catch (e) {
    el('#icerik').innerHTML = `<div class="hata">${kacir(e.message)}</div>`;
  }
}
window.addEventListener('hashchange', yonlendir);

/* ================================================================ GÖSTERGE */
async function sayfaGosterge() {
  const g = await cagir('/api/firma/gosterge');
  KURUM = g.firma || null;
  const k = (etiket, deger, ek, vurgu) => `
    <div class="kart${vurgu ? ' vurgulu' : ''}">
      <div class="etiket">${etiket}</div>
      <div class="deger">${deger}</div>
      ${ek ? `<div class="ek">${ek}</div>` : ''}
    </div>`;

  const hicVeri = !Number(g.ucus) && !Number(g.dron) && !Number(g.sunucu);

  el('#icerik').innerHTML = `
    <h2>Gösterge Paneli</h2>
    <p class="aciklama">
      ${kacir(KURUM ? (KURUM.unvan || KURUM.kisa_ad) : 'Kurumunuz')} adına
      merkeze eşitlenen uçuş, video ve istasyon verisinin özeti.
      ${BEN.rol === 'pilot'
        ? 'Pilot rolüyle giriş yaptığınız için yalnızca kendi uçuşlarınız gösterilir.'
        : ''}
    </p>
    ${hicVeri ? `
      <div class="bos-durum">
        <h3>Henüz veri eşitlenmemiş</h3>
        <p>Yer kontrol istasyonunuz merkeze bağlandığında uçuş kayıtları,
          video kayıtları ve dron envanteri bu panelde otomatik görünür.
          İstasyonunuzda <strong>Program Ayarları → Merkez Sunucu</strong>
          bölümünden merkez bağlantısını etkinleştirin ve
          <strong>Merkeze kaydet</strong> düğmesine basın.</p>
        <a class="yerel-baglanti" href="/#istemciler">Yazılımı indir</a>
      </div>` : `
    <div class="kart-izgara">
      ${k('Uçuş Kaydı', sayi(g.ucus), `son 7 gün: ${sayi(g.ucus_7gun)}`)}
      ${k('Toplam Uçuş Süresi', sure(g.toplam_sure_sn))}
      ${k('Dron', sayi(g.dron))}
      ${k('Video Kaydı', sayi(g.video), bayt(g.video_bayt))}
      ${k('İstasyon', `${sayi(g.sunucu_cevrimici)} / ${sayi(g.sunucu)}`,
         'çevrimiçi / kayıtlı', Number(g.sunucu_cevrimici) > 0)}
      ${k('Ekip', sayi(g.kullanici), `${sayi(g.kullanici_etkin)} etkin`)}
      ${k('Telemetri Örneği', sayi(g.telemetri))}
      ${k('Toplam Mesafe', g.toplam_mesafe_m
         ? sayi(g.toplam_mesafe_m / 1000, 1) + ' km' : '—')}
    </div>
    <div class="pano">
      <h3>Son 14 günün uçuş dağılımı</h3>
      <div id="cizim-kap"></div>
    </div>
    <div class="pano">
      <h3>En çok uçan dronlar</h3>
      <table>
        <thead><tr><th>Dron</th><th>Tür</th><th class="sag">Uçuş</th>
          <th class="sag">Süre</th></tr></thead>
        <tbody>
          ${(g.dron_ucus || []).map((d) => `<tr>
            <td>${kacir(d.ad || d.yerel_uid || '—')}</td>
            <td>${kacir(d.arac_turu || '—')}</td>
            <td class="sag">${sayi(d.adet)}</td>
            <td class="sag">${sure(d.sure)}</td></tr>`).join('') ||
            '<tr><td colspan="4" class="bos">Henüz uçuş kaydı yok</td></tr>'}
        </tbody>
      </table>
    </div>`}`;

  if (!hicVeri) cizimCiz('#cizim-kap', g.gunluk_ucus || []);
}

function cizimCiz(kapSecici, veri) {
  const kap = el(kapSecici);
  if (!kap) return;
  if (!veri.length) {
    kap.innerHTML = '<div class="bos">Gösterilecek veri yok</div>';
    return;
  }
  const G = 760, Y = 190, bosluk = { s: 34, u: 12, a: 24, sa: 10 };
  const enb = Math.max(1, ...veri.map((v) => Number(v.adet)));
  const gen = (G - bosluk.s - bosluk.sa) / veri.length;
  const cubuklar = veri.map((v, i) => {
    const h = (Number(v.adet) / enb) * (Y - bosluk.u - bosluk.a);
    const x = bosluk.s + i * gen + gen * 0.15;
    const y = Y - bosluk.a - h;
    const g = gen * 0.7;
    const etiket = tarih(v.gun, false).slice(0, 5);
    return `<g>
      <rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${g.toFixed(1)}"
            height="${Math.max(h, 1).toFixed(1)}" fill="#1f9e8f" rx="2">
        <title>${etiket}: ${v.adet} uçuş</title></rect>
      <text x="${(x + g / 2).toFixed(1)}" y="${Y - 8}" fill="#93a3bb"
            font-size="9" text-anchor="middle">${etiket}</text>
    </g>`;
  }).join('');
  const yatay = [0, 0.5, 1].map((o) => {
    const y = Y - bosluk.a - o * (Y - bosluk.u - bosluk.a);
    return `<line x1="${bosluk.s}" y1="${y}" x2="${G - bosluk.sa}" y2="${y}"
                  stroke="#223046" stroke-width="1"/>
            <text x="4" y="${y + 3}" fill="#5d6b83" font-size="9">
              ${Math.round(o * enb)}</text>`;
  }).join('');
  kap.innerHTML = `<svg class="cizim" viewBox="0 0 ${G} ${Y}"
      preserveAspectRatio="none">${yatay}${cubuklar}</svg>`;
}

/* ================================================================ SAYFALAMA */
function sayfalamaHTML(toplam, sayfa, boyut, islev) {
  const son = Math.max(1, Math.ceil(toplam / boyut));
  return `<div class="sayfalama">
    <span>${sayi(toplam)} kayıt · sayfa ${sayfa}/${son}</span>
    <button class="ikincil kucuk" ${sayfa <= 1 ? 'disabled' : ''}
            onclick="${islev}(${sayfa - 1})">‹ Önceki</button>
    <button class="ikincil kucuk" ${sayfa >= son ? 'disabled' : ''}
            onclick="${islev}(${sayfa + 1})">Sonraki ›</button>
  </div>`;
}

/* ================================================================ UÇUŞLAR */
async function sayfaUcuslar(par) {
  DURUM.ucus = Object.assign({ sayfa: 1, boyut: 50, kullanici_id: '',
    baslangic: '', bitis: '' }, DURUM.ucus, par);
  await ucusTabloYenile();
}

async function ucusTabloYenile() {
  const d = DURUM.ucus;
  const s = new URLSearchParams({ sayfa: d.sayfa, boyut: d.boyut });
  if (d.kullanici_id) s.set('kullanici_id', d.kullanici_id);
  if (d.baslangic) s.set('baslangic', d.baslangic);
  if (d.bitis) s.set('bitis', d.bitis);

  // Pilot filtresi yalnızca kurum yöneticisi/gözlemci için anlamlı; pilot
  // rolünde merkez zaten kendi kayıtlarına daraltır.
  const ekipVar = BEN.rol !== 'pilot';
  const [y, ek] = await Promise.all([
    cagir('/api/firma/ucuslar?' + s.toString()),
    ekipVar ? cagir('/api/firma/ekip').catch(() => ({ kullanicilar: [] }))
            : Promise.resolve({ kullanicilar: [] })
  ]);

  el('#icerik').innerHTML = `
    <h2>Uçuş Kayıtları</h2>
    <p class="aciklama">İstasyonlarınızın merkeze eşitlediği uçuşlar.
      Kayda tıklayarak telemetri grafiğini, rotayı ve videoları izleyin.</p>
    <div class="arac-cubugu">
      ${ekipVar ? `<label>Pilot
        <select id="u-pilot">
          <option value="">tümü</option>
          ${(ek.kullanicilar || []).map((u) => `<option value="${u.kullanici_id}"
            ${String(d.kullanici_id) === String(u.kullanici_id) ? 'selected' : ''}>${
            kacir(`${u.ad || ''} ${u.soyad || ''}`.trim() || u.eposta)}</option>`).join('')}
        </select></label>` : ''}
      <label>Başlangıç <input type="date" id="u-bas" value="${kacir(d.baslangic)}"></label>
      <label>Bitiş <input type="date" id="u-bit" value="${kacir(d.bitis)}"></label>
      <button class="ikincil kucuk" id="u-ara">Filtrele</button>
      <button class="ikincil kucuk" id="u-sifirla">Sıfırla</button>
    </div>
    <div class="pano" style="margin-top:0">
      <table>
        <thead><tr>
          <th>Tarih</th><th>Pilot</th><th>Dron</th><th>Tür</th>
          <th>Görev</th><th class="sag">Süre</th><th class="sag">Mesafe</th>
          <th class="sag">Maks. İrtifa</th><th class="sag">Video</th><th></th>
        </tr></thead>
        <tbody>${(y.kayitlar || []).map((u) => `<tr>
          <td class="tek-satir">${tarih(u.baslangic_ts)}</td>
          <td>${kacir(u.pilot || '—')}</td>
          <td>${kacir(u.dron || '—')}</td>
          <td>${kacir(u.arac_turu || '—')}</td>
          <td>${rozet(u.gorev_durumu || '—', GOREV_RENK[u.gorev_durumu] || 'gri')}</td>
          <td class="sag">${sure(u.sure_sn)}</td>
          <td class="sag">${u.mesafe_m ? sayi(u.mesafe_m / 1000, 2) + ' km' : '—'}</td>
          <td class="sag">${u.maks_irtifa_m ? sayi(u.maks_irtifa_m, 1) + ' m' : '—'}</td>
          <td class="sag">${Number(u.video_sayisi) > 0
            ? rozet(u.video_sayisi, 'mor') : '—'}</td>
          <td class="sag"><button class="ikincil kucuk"
              onclick="ucusDetay(${u.ucus_id})">İzle</button></td>
        </tr>`).join('') ||
          '<tr><td colspan="10" class="bos">Uçuş kaydı bulunamadı</td></tr>'}</tbody>
      </table>
      ${sayfalamaHTML(y.toplam, y.sayfa, y.boyut, 'ucusSayfa')}
    </div>`;

  el('#u-ara').onclick = () => {
    if (el('#u-pilot')) DURUM.ucus.kullanici_id = el('#u-pilot').value;
    DURUM.ucus.baslangic = el('#u-bas').value;
    DURUM.ucus.bitis = el('#u-bit').value;
    DURUM.ucus.sayfa = 1;
    ucusTabloYenile();
  };
  el('#u-sifirla').onclick = () => {
    DURUM.ucus = { sayfa: 1, boyut: 50, kullanici_id: '', baslangic: '', bitis: '' };
    ucusTabloYenile();
  };
}
window.ucusSayfa = (n) => { DURUM.ucus.sayfa = n; ucusTabloYenile(); };

window.ucusDetay = async (uid) => {
  const u = await cagir('/api/firma/ucuslar/' + uid);
  pencereAc(`Uçuş ${u.ucus_uid}`, `
    <dl class="ozet">
      <dt>Pilot</dt><dd>${kacir(u.pilot || '—')}
        ${u.pilot_eposta ? ' · ' + kacir(u.pilot_eposta) : ''}</dd>
      <dt>Dron</dt><dd>${kacir(u.dron || '—')} ${u.arac_turu
        ? '· ' + kacir(u.arac_turu) : ''} ${u.sysid ? '· SYSID ' + u.sysid : ''}</dd>
      <dt>Başlangıç</dt><dd>${tarih(u.baslangic_ts)}</dd>
      <dt>Bitiş</dt><dd>${tarih(u.bitis_ts)}</dd>
      <dt>Süre</dt><dd>${sure(u.sure_sn)}</dd>
      <dt>Mesafe</dt><dd>${u.mesafe_m ? sayi(u.mesafe_m / 1000, 2) + ' km' : '—'}</dd>
      <dt>Maks. irtifa</dt><dd>${u.maks_irtifa_m ? sayi(u.maks_irtifa_m, 1) + ' m' : '—'}</dd>
      <dt>Maks. hız</dt><dd>${u.maks_hiz_ms ? sayi(u.maks_hiz_ms, 1) + ' m/s' : '—'}</dd>
      <dt>Görev</dt><dd>${kacir(u.gorev_turu || '—')} ·
        ${rozet(u.gorev_durumu || '—', GOREV_RENK[u.gorev_durumu] || 'gri')}</dd>
      <dt>İstasyon</dt><dd>${kacir(u.sunucu_ad || '—')}</dd>
      <dt>Telemetri</dt><dd>${sayi(u.telemetri_sayisi)} örnek</dd>
    </dl>
    <div class="pano">
      <h3>İrtifa ve hız</h3>
      <div id="tel-cizim"><div class="yukleniyor">Telemetri yükleniyor…</div></div>
    </div>
    <div class="pano">
      <h3>Rota</h3>
      <div id="rota-cizim"><div class="yukleniyor">Yükleniyor…</div></div>
    </div>
    <div class="pano">
      <h3>Video kayıtları (${(u.videolar || []).length})</h3>
      <table><thead><tr><th>Başlık</th><th>Kaynak</th><th>Süre</th>
        <th>Boyut</th><th>Depo</th><th></th></tr></thead>
      <tbody>${(u.videolar || []).map((v) => `<tr>
        <td>${kacir(v.baslik || v.video_uid)}</td>
        <td>${kacir(v.kaynak || '—')}</td>
        <td>${sure(v.sure_sn)}</td>
        <td>${bayt(v.boyut_bayt)}</td>
        <td>${rozet(v.depo_yeri, v.depo_yeri === 'merkez' ? 'yesil' : 'sari')}</td>
        <td class="sag"><button class="ikincil kucuk"
            onclick="videoIzle(${v.video_id})">Oynat</button></td></tr>`).join('') ||
        '<tr><td colspan="6" class="bos">Bu uçuşa ait video kaydı yok</td></tr>'}</tbody>
      </table>
    </div>`,
    [{ metin: 'Kapat', sinif: 'ikincil', tik: pencereKapat }], true);
  telemetriCiz(uid);
};

async function telemetriCiz(uid) {
  try {
    const y = await cagir(`/api/firma/ucuslar/${uid}/telemetri?seyreltme=6`);
    const k = y.kayitlar || [];
    if (!k.length) {
      const b = '<div class="bos">Telemetri örneği yok</div>';
      if (el('#tel-cizim')) el('#tel-cizim').innerHTML = b;
      if (el('#rota-cizim')) el('#rota-cizim').innerHTML = b;
      return;
    }
    cokCizgiCiz('#tel-cizim', k);
    rotaCiz('#rota-cizim', k);
  } catch (e) {
    if (el('#tel-cizim')) el('#tel-cizim').innerHTML =
      `<div class="hata">${kacir(e.message)}</div>`;
  }
}

function cokCizgiCiz(secici, k) {
  const kap = el(secici);
  if (!kap) return;
  const G = 900, Y = 220, b = { s: 34, u: 12, a: 26, sa: 34 };
  const irt = k.map((x) => Number(x.irtifa_m) || 0);
  const hiz = k.map((x) => Number(x.hiz_ms) || 0);
  const irtEnb = Math.max(1, ...irt);
  const hizEnb = Math.max(1, ...hiz);
  const gx = (i) => b.s + (i / Math.max(1, k.length - 1)) * (G - b.s - b.sa);
  const yol = (dizi, enb) => dizi.map((v, i) => {
    const y = Y - b.a - (v / enb) * (Y - b.u - b.a);
    return `${i ? 'L' : 'M'}${gx(i).toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  const izgara = [0, 0.5, 1].map((o) => {
    const y = Y - b.a - o * (Y - b.u - b.a);
    return `<line x1="${b.s}" y1="${y}" x2="${G - b.sa}" y2="${y}"
                  stroke="#223046" stroke-width="1"/>
            <text x="4" y="${y + 3}" fill="#5d6b83" font-size="9">
              ${Math.round(o * irtEnb)}</text>
            <text x="${G - b.sa + 4}" y="${y + 3}" fill="#5d6b83" font-size="9">
              ${Math.round(o * hizEnb)}</text>`;
  }).join('');
  const ilk = tarih(k[0].ts);
  const son = tarih(k[k.length - 1].ts);
  kap.innerHTML = `<svg viewBox="0 0 ${G} ${Y}" class="cizim">
      ${izgara}
      <path d="${yol(irt, irtEnb)}" fill="none" stroke="#1f9e8f" stroke-width="1.6"/>
      <path d="${yol(hiz, hizEnb)}" fill="none" stroke="#d29922" stroke-width="1.4"
            stroke-dasharray="4 3"/>
      <text x="${b.s}" y="${Y - 8}" fill="#5d6b83" font-size="9">${ilk}</text>
      <text x="${G - b.sa}" y="${Y - 8}" fill="#5d6b83" font-size="9"
            text-anchor="end">${son}</text>
    </svg>
    <div style="margin-top:6px;font-size:11px;color:#93a3bb">
      <span style="color:#1f9e8f">▬</span> irtifa (m, sol)
      &nbsp;&nbsp;<span style="color:#d29922">▬</span> hız (m/s, sağ)
      &nbsp;&nbsp;${k.length} örnek gösteriliyor
    </div>`;
}

function rotaCiz(secici, k) {
  const kap = el(secici);
  if (!kap) return;
  const n = k.filter((x) => Number(x.lat) && Number(x.lon));
  if (n.length < 2) {
    kap.innerHTML = '<div class="bos">Konum verisi yok</div>';
    return;
  }
  const lat = n.map((x) => Number(x.lat)), lon = n.map((x) => Number(x.lon));
  const laEn = Math.min(...lat), laEnb = Math.max(...lat);
  const loEn = Math.min(...lon), loEnb = Math.max(...lon);
  const G = 900, Y = 300, p = 18;
  const dl = Math.max(laEnb - laEn, 1e-6), dn = Math.max(loEnb - loEn, 1e-6);
  const olcek = Math.min((G - 2 * p) / dn, (Y - 2 * p) / dl);
  const gx = (o) => p + (o - loEn) * olcek + ((G - 2 * p) - dn * olcek) / 2;
  const gy = (a) => Y - p - (a - laEn) * olcek - ((Y - 2 * p) - dl * olcek) / 2;
  const yol = n.map((x, i) =>
    `${i ? 'L' : 'M'}${gx(Number(x.lon)).toFixed(1)},${gy(Number(x.lat)).toFixed(1)}`
  ).join(' ');
  const bas = n[0], son = n[n.length - 1];
  const mesafe = (dn * 111320 * Math.cos(laEn * Math.PI / 180));
  kap.innerHTML = `<svg viewBox="0 0 ${G} ${Y}" style="width:100%;height:300px;
      background:#0d1420;border-radius:8px">
      <path d="${yol}" fill="none" stroke="#2ea043" stroke-width="2"
            stroke-linejoin="round"/>
      <circle cx="${gx(Number(bas.lon))}" cy="${gy(Number(bas.lat))}" r="5"
              fill="#1f9e8f"><title>Kalkış</title></circle>
      <circle cx="${gx(Number(son.lon))}" cy="${gy(Number(son.lat))}" r="5"
              fill="#f85149"><title>İniş</title></circle>
    </svg>
    <div style="margin-top:6px;font-size:11px;color:#93a3bb">
      <span style="color:#1f9e8f">●</span> kalkış
      &nbsp;<span style="color:#f85149">●</span> iniş
      &nbsp;· enlem ${laEn.toFixed(5)}–${laEnb.toFixed(5)}
      &nbsp;· boylam ${loEn.toFixed(5)}–${loEnb.toFixed(5)}
      &nbsp;· yatay kapsam ≈ ${sayi(mesafe, 0)} m
    </div>`;
}

/* ================================================================ VİDEOLAR */
async function sayfaVideolar(par) {
  DURUM.video = Object.assign({ sayfa: 1, boyut: 50 }, DURUM.video, par);
  await videoTabloYenile();
}

async function videoTabloYenile() {
  const d = DURUM.video;
  const y = await cagir('/api/firma/videolar?' +
    new URLSearchParams({ sayfa: d.sayfa, boyut: d.boyut }).toString());
  el('#icerik').innerHTML = `
    <h2>Video Kayıtları</h2>
    <p class="aciklama">Uçuşlarınıza ait kamera kayıtları. Merkeze yüklenmiş
      kayıtlar doğrudan oynatılır; yalnız istasyonda saklanan kayıtlar
      istasyon çevrimiçiyse ters bağlantı üzerinden aktarılır.</p>
    <div class="pano" style="margin-top:0">
      <table>
        <thead><tr><th>Başlangıç</th><th>Başlık</th><th>Pilot</th><th>Dron</th>
          <th>Kaynak</th><th class="sag">Süre</th><th class="sag">Boyut</th>
          <th>Depo</th><th></th></tr></thead>
        <tbody>${(y.kayitlar || []).map((v) => `<tr>
          <td class="tek-satir">${tarih(v.baslangic_ts)}</td>
          <td>${kacir(v.baslik || v.video_uid)}</td>
          <td>${kacir(v.pilot || '—')}</td>
          <td>${kacir(v.dron || '—')}</td>
          <td>${kacir(v.kaynak || '—')}</td>
          <td class="sag">${sure(v.sure_sn)}</td>
          <td class="sag">${bayt(v.boyut_bayt)}</td>
          <td>${rozet(v.depo_yeri, v.depo_yeri === 'merkez' ? 'yesil' : 'sari')}</td>
          <td class="sag"><button class="ikincil kucuk"
              onclick="videoIzle(${v.video_id})">Oynat</button></td>
        </tr>`).join('') ||
          '<tr><td colspan="9" class="bos">Video kaydı bulunamadı</td></tr>'}</tbody>
      </table>
      ${sayfalamaHTML(y.toplam, y.sayfa, y.boyut, 'videoSayfa')}
    </div>`;
}
window.videoSayfa = (n) => { DURUM.video.sayfa = n; videoTabloYenile(); };

window.videoIzle = async (vid) => {
  const v = await cagir('/api/firma/videolar/' + vid);
  const merkezde = v.depo_yeri === 'merkez';
  const uyari = merkezde ? '' : (v.sunucu_cevrimici
    ? `<div class="uyari-kutu">Bu kayıt istasyonunuzda
        (<strong>${kacir(v.sunucu_ad || '—')}</strong>) saklanıyor. İstasyon
        çevrimiçi olduğu için ters bağlantı üzerinden aktarılacak; başlaması
        biraz sürebilir.</div>`
    : `<div class="uyari-kutu">Bu kayıt istasyonunuzda
        (<strong>${kacir(v.sunucu_ad || '—')}</strong>) saklanıyor ve istasyon
        şu anda <strong>çevrimdışı</strong>. Oynatma için istasyonun merkeze
        bağlanması gerekir.</div>`);
  pencereAc(v.baslik || v.video_uid, `
    ${uyari}
    <video id="oynatici" controls preload="metadata"
           src="/api/firma/videolar/${vid}/akis"></video>
    <dl class="ozet" style="margin-top:14px">
      <dt>Pilot</dt><dd>${kacir(v.pilot || '—')}</dd>
      <dt>Uçuş</dt><dd>${v.ucus_uid ? `<a href="#" onclick="pencereKapat();
        ucusDetay(${v.ucus_id});return false">${kacir(v.ucus_uid)}</a>` : '—'}</dd>
      <dt>Kaynak</dt><dd>${kacir(v.kaynak || '—')}</dd>
      <dt>Başlangıç</dt><dd>${tarih(v.baslangic_ts)}</dd>
      <dt>Süre</dt><dd>${sure(v.sure_sn)}</dd>
      <dt>Boyut</dt><dd>${bayt(v.boyut_bayt)}</dd>
      <dt>Çözünürlük</dt><dd>${kacir(v.cozunurluk || '—')} ${v.kodek
        ? '· ' + kacir(v.kodek) : ''}</dd>
      <dt>Depo</dt><dd>${rozet(v.depo_yeri, merkezde ? 'yesil' : 'sari')}</dd>
    </dl>`,
    [{ metin: 'Kapat', sinif: 'ikincil', tik: () => {
      const o = el('#oynatici');
      if (o) { o.pause(); o.removeAttribute('src'); o.load(); }
      pencereKapat();
    } }], true);
};

/* ================================================================ DRONLAR */
async function sayfaDronlar() {
  const y = await cagir('/api/firma/dronlar');
  const kayitlar = y.kayitlar || [];
  el('#icerik').innerHTML = `
    <h2>Dronlar</h2>
    <p class="aciklama">İstasyonlarınızın merkeze bildirdiği hava aracı
      envanteri. Kayıtlar uçuş verisinden otomatik üretilir.</p>
    <div class="pano" style="margin-top:0">
      <table>
        <thead><tr><th>Ad</th><th>Yerel kimlik</th><th>Tür</th>
          <th class="sag">SYSID</th><th class="sag">Uçuş</th>
          <th class="sag">Toplam süre</th><th>Son görülme</th></tr></thead>
        <tbody>${kayitlar.map((d) => `<tr>
          <td><strong>${kacir(d.ad || '—')}</strong></td>
          <td><code class="kod">${kacir(d.yerel_uid || '—')}</code></td>
          <td>${kacir(d.arac_turu || '—')}</td>
          <td class="sag">${d.sysid || '—'}</td>
          <td class="sag">${sayi(d.ucus_sayisi)}</td>
          <td class="sag">${sure(d.toplam_sure_sn)}</td>
          <td class="tek-satir">${tarih(d.son_ucus_ts)}</td>
        </tr>`).join('') ||
          '<tr><td colspan="7" class="bos">Dron kaydı yok</td></tr>'}</tbody>
      </table>
    </div>`;
}

/* ================================================================ İSTASYONLAR */
/* ================================================================ KÖPRÜLER /
   MERKEZİ YAZILIMLAR (2026-09-17, kullanıcı isteği)
   Eski "İstasyonlar" sayfası iki ürün tipine ayrıldı. Her ikisi de
   `sunucu_ornekleri` satırıdır (`urun` = kopru | gcs). Kayıt yalnız AD
   ister; sunucu API kodu üretir (GTK1.…). Kod ilk başarılı bağlantıya
   kadar listede görünür ve kopyalanır; sonra güvenlik için silinir,
   "Kodu yenile" yeni sır üretir. Köprülerde çevrimiçi modüller çip olarak
   gösterilir. */
const ORNEK_TANIM = {
  kopru: {
    baslik: 'Köprüler', tekil: 'Köprü', yeni: 'Yeni Köprü',
    aciklama: 'Sahadaki köprü yazılımları (Windows, Ubuntu, Android MAVLink) ' +
      'merkeze API koduyla eşleşir ve ters WebSocket ile bağlanır; sabit IP gerekmez. ' +
      'Kayıt yalnız bir ad ister. Üretilen kodu köprünün ilk kurulum ekranına ' +
      '(GRCON seçili) yapıştırın; dron, radar ve kamera bağlantılarını Merkez ' +
      'Uygulama’daki Bağlantı Yöneticisi bu köprü üzerinden açar.',
    bos: 'Kayıtlı köprü yok. "Yeni Köprü" ile bir kayıt oluşturun; kodu köprü ' +
      'yazılımının ilk kurulumunda girin.'
  },
  gcs: {
    baslik: 'Merkezi Yazılımlar', tekil: 'Merkezi Yazılım', yeni: 'Yeni Merkezi Yazılım',
    aciklama: 'Kapalı devre çalışan Merkez Uygulama (GRCOFF) kurulumları. Her kurulum ' +
      'bir kayıt alır; kurulum sihirbazı veritabanı bilgilerinden sonra merkez ' +
      'adresini ve bu API kodunu sorar, kurum bilgilerinizi ve logonuzu bir kez ' +
      'merkezden çeker. Kullanıcı adı / şifre girilmez.',
    bos: 'Kayıtlı Merkezi Yazılım yok. "Yeni Merkezi Yazılım" ile bir kayıt oluşturun; ' +
      'kodu GRCOFF kurulum sihirbazına girin.'
  }
};
const MODUL_AD = { dron: 'Dron', ai: 'AI', video: 'Video', gcsdual: 'GroundGCC',
                   radar: 'Radar', m50: 'M50' };

function modulCipleri(s) {
  if (!s.cevrimici) return '<span class="ek">çevrimdışı</span>';
  const liste = Array.isArray(s.servisler) ? s.servisler : null;
  if (!liste) return `<span class="ek">${kacir(s.servis_hata || 'servis bilgisi yok')}</span>`;
  if (!liste.length) return '<span class="ek">servis bildirilmedi</span>';
  return liste.map((m) => {
    const ad = String((m && (m.ad || m.servis)) || '').toLowerCase();
    const acik = !!(m && (m.calisiyor === true ||
      String(m.durum || '').toLowerCase() === 'calisiyor'));
    return `<span class="modul-cip ${acik ? 'acik' : 'kapali'}"
      title="${kacir(ad)}: ${acik ? 'çalışıyor' : 'durdu'}">${kacir(MODUL_AD[ad] || ad)}</span>`;
  }).join('');
}

async function sayfaOrnekler(urun) {
  const T = ORNEK_TANIM[urun];
  const y = await cagir(`/api/firma/ornekler/${urun}?servisler=1`);
  const kayitlar = y.kayitlar || [];
  const cevrimici = kayitlar.filter((s) => s.cevrimici).length;
  const yon = yoneticiMiKontrol();
  el('#icerik').innerHTML = `
    <h2>${T.baslik}</h2>
    <p class="aciklama">${T.aciklama} ${cevrimici} kayıt şu anda çevrimiçi.</p>
    ${yon ? `<div class="arac-cubugu" style="margin-bottom:12px">
      <button onclick="ornekEkle('${urun}')">+ ${T.yeni}</button></div>` : ''}
    ${kayitlar.length ? `<div class="istasyon-izgara">
      ${kayitlar.map((s) => `
        <div class="istasyon-kart${s.cevrimici ? ' cevrimici' : ''}">
          <h4><span class="nokta${s.cevrimici ? ' acik' : ''}"></span>
            ${kacir(s.ad)}</h4>
          <dl class="ozet">
            <dt>Durum</dt><dd>${s.cevrimici
              ? rozet('çevrimiçi', 'yesil') : rozet('çevrimdışı', 'gri')}</dd>
            ${urun === 'kopru' ? `<dt>Modüller</dt><dd class="modul-satir">${modulCipleri(s)}</dd>` : ''}
            <dt>Sürüm</dt><dd>${kacir(s.surum || '—')}</dd>
            <dt>Platform</dt><dd>${kacir(s.platform || '—')}</dd>
            <dt>Makine</dt><dd>${kacir(s.makine_adi || '—')}</dd>
            ${urun === 'kopru' ? `<dt>Dron</dt><dd>${sayi(s.dron_sayisi)}</dd>` : ''}
            <dt>Son IP</dt><dd>${kacir(s.son_ip || '—')}</dd>
            <dt>Son görülme</dt><dd>${tarih(s.son_gorulme_ts)}</dd>
          </dl>
          ${yon ? (s.api_kodu ? `
            <div class="kod-kutu">
              <div class="kod-baslik">API kodu <span class="ek">kurulumda girilir; ilk bağlantıda silinir</span></div>
              <textarea id="kod-${s.ornek_id}" readonly rows="3" spellcheck="false">${kacir(s.api_kodu)}</textarea>
              <div class="arac-cubugu">
                <button class="ikincil kucuk" onclick="ornekKodKopyala(${s.ornek_id})">Kopyala</button>
              </div>
            </div>` : `
            <div class="kod-kutu tuketildi">
              <div class="kod-baslik">API kodu <span class="ek">tüketildi (kurulum bağlandı)</span></div>
              <div class="arac-cubugu">
                <button class="ikincil kucuk" onclick="ornekKodYenile('${urun}', ${s.ornek_id}, '${kacir(s.ad)}', ${s.cevrimici ? 'true' : 'false'})">Kodu yenile</button>
              </div>
            </div>`) : ''}
          <div class="arac-cubugu">
            ${s.cevrimici ? `<button class="ikincil kucuk"
                onclick="istasyonSor(${s.ornek_id}, '${kacir(s.ad)}')">Canlı durum</button>` : ''}
            ${yon ? `<button class="ikincil kucuk tehlike"
                onclick="ornekSil('${urun}', ${s.ornek_id}, '${kacir(s.ad)}', ${s.cevrimici ? 'true' : 'false'})">Kaldır</button>` : ''}
          </div>
        </div>`).join('')}
    </div>` : `
      <div class="bos-durum">
        <h3>${kacir(T.bos)}</h3>
        ${urun === 'kopru'
          ? '<a class="yerel-baglanti" href="#kopru">Köprü yazılımını indir</a>'
          : '<a class="yerel-baglanti" href="#merkez">Merkez Uygulama paketini indir</a>'}
      </div>`}`;
}
async function sayfaKopruler() { return sayfaOrnekler('kopru'); }
async function sayfaMerkezler() { return sayfaOrnekler('gcs'); }

window.ornekEkle = (urun) => {
  const T = ORNEK_TANIM[urun];
  pencereAc(T.yeni, `
    <p class="aciklama">Yalnızca bir ad verin. Kayıt oluşunca API kodu üretilir;
      kodu listeden kopyalayıp kurulumda girin.</p>
    <label>Ad<input id="ornek-ad" type="text" maxlength="64"
      placeholder="${urun === 'kopru' ? 'Örn: Saha Aracı 1' : 'Örn: Ankara Merkez Odası'}"></label>
    <div id="ornek-hata" class="hata"></div>`,
    [{ metin: 'Vazgeç', sinif: 'ikincil', tik: pencereKapat },
     { metin: 'Oluştur', tik: async () => {
        const ad = (el('#ornek-ad').value || '').trim();
        if (!ad) { el('#ornek-hata').textContent = 'Ad zorunlu.'; return; }
        try {
          const y = await cagir(`/api/firma/ornekler/${urun}`, { method: 'POST', body: { ad } });
          pencereKapat();
          bildir(`${T.tekil} oluşturuldu: ${y.kayit && y.kayit.ad}`, 'basari');
          await sayfaOrnekler(urun);
          const ta = el(`#kod-${y.kayit && y.kayit.ornek_id}`);
          if (ta) { ta.focus(); ta.select(); }
        } catch (e) {
          el('#ornek-hata').textContent = e.message || 'Oluşturulamadı';
        }
      } }]);
  setTimeout(() => { const g = el('#ornek-ad'); if (g) g.focus(); }, 50);
};

window.ornekKodKopyala = async (oid) => {
  const ta = el(`#kod-${oid}`);
  if (!ta) return;
  const kod = ta.value;
  let ok = false;
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(kod); ok = true;
    }
  } catch (e) { ok = false; }
  if (!ok) {
    try { ta.focus(); ta.select(); ok = document.execCommand('copy'); } catch (e) { ok = false; }
  }
  bildir(ok ? 'API kodu panoya kopyalandı.' : 'Kopyalanamadı; kodu kutudan seçip kopyalayın.',
    ok ? 'basari' : 'hata');
};

window.ornekKodYenile = async (urun, oid, ad, cevrimici) => {
  const soru = `"${ad}" için yeni API kodu üretilecek` +
    (cevrimici ? '; bağlıysa bağlantısı kesilir ve yeni kodla yeniden kurulmalıdır' : '') +
    '. Devam edilsin mi?';
  if (!window.confirm(soru)) return;
  try {
    await cagir(`/api/firma/ornekler/${urun}/${oid}/kod_yenile`, { method: 'POST', body: {} });
    bildir('API kodu yenilendi.', 'basari');
    await sayfaOrnekler(urun);
    const ta = el(`#kod-${oid}`);
    if (ta) { ta.focus(); ta.select(); }
  } catch (e) {
    bildir(e.message || 'Yenilenemedi', 'hata');
  }
};

window.ornekSil = async (urun, oid, ad, cevrimici) => {
  const soru = (cevrimici
    ? `"${ad}" şu anda ÇEVRİMİÇİ. Kayıt silinirse bağlantısı kesilir ve aynı kimlikle yeniden bağlanamaz. `
    : `"${ad}" kaydı listeden kaldırılacak; aynı kimlikle yeniden bağlanamaz. `) + 'Devam edilsin mi?';
  if (!window.confirm(soru)) return;
  try {
    await cagir(`/api/firma/ornekler/${urun}/${oid}`, { method: 'DELETE' });
    bildir(`"${ad}" kaldırıldı.`, 'basari');
    sayfaOrnekler(urun);
  } catch (e) {
    bildir(e.message || 'Kaldırılamadı', 'hata');
  }
};

window.istasyonSor = async (oid, ad) => {
  pencereAc(`${ad} — canlı durum`, `
    <p class="aciklama">Merkez, açık ters bağlantı üzerinden istasyona sorgu
      gönderir. İstasyonun yanıtı aşağıda gösterilir.</p>
    <div class="arac-cubugu">
      <button class="ikincil kucuk"
        onclick="istasyonEylem(${oid},'dron_liste')">Dron listesi</button>
      <button class="ikincil kucuk"
        onclick="istasyonEylem(${oid},'port_liste')">Port listesi</button>
      <button class="ikincil kucuk"
        onclick="istasyonEylem(${oid},'servis_durum')">Servis durumu</button>
      <button class="ikincil kucuk"
        onclick="istasyonEylem(${oid},'sistem_bilgi')">Sistem bilgisi</button>
    </div>
    <div id="sorgu-sonuc" class="pano" style="margin-top:0">
      <div class="bos">Bir sorgu seçin</div></div>`,
    [{ metin: 'Kapat', sinif: 'ikincil', tik: pencereKapat }], true);
};

/* 2026-09-17 (kullanici istegi): kaldirilan/eski kopru kayitlari listeden
   silinebilir. Cevrimiciyse baglantisi da dusurulur; ayni kimlikle yeniden
   baglanamaz (yeni kimlik uretilmesi gerekir). */
window.istasyonSil = async (oid, ad, cevrimici) => {
  const soru = (cevrimici
    ? `"${ad}" şu anda ÇEVRİMİÇİ. Kayıt silinirse bağlantısı kesilir ve aynı kimlikle yeniden bağlanamaz. `
    : `"${ad}" kaydı listeden kaldırılacak; bu köprü aynı kimlikle yeniden bağlanamaz. `) + 'Devam edilsin mi?';
  if (!window.confirm(soru)) return;
  try {
    await cagir(`/api/firma/sunucular/${oid}`, { method: 'DELETE' });
    bildir(`"${ad}" kaldırıldı.`, 'basari');
    sayfaIstasyonlar();
  } catch (e) {
    bildir(e.message || 'Kaldırılamadı', 'hata');
  }
};

window.istasyonEylem = async (oid, eylem) => {
  const k = el('#sorgu-sonuc');
  k.innerHTML = '<div class="yukleniyor">İstasyondan yanıt bekleniyor…</div>';
  try {
    const y = await cagir(`/api/firma/sunucular/${oid}/sor/${eylem}`);
    k.innerHTML = `<pre style="margin:0;white-space:pre-wrap;font-size:12px;
      font-family:ui-monospace,Menlo,Consolas,monospace;color:#7ee787">${
      kacir(JSON.stringify(y, null, 2))}</pre>`;
  } catch (e) {
    k.innerHTML = `<div class="hata">${kacir(e.message)}</div>`;
  }
};

/* ================================================================ EKİP */
async function sayfaEkip() {
  const [y, ab] = await Promise.all([
    cagir('/api/firma/ekip'),
    cagir('/api/firma/abonelik').catch(() => null)
  ]);
  const kayitlar = y.kullanicilar || [];
  const yetki = (ab && ab.yetkiler) || {};
  const yon = yoneticiMiKontrol();
  const sinirsiz = !!yetki.sinirsiz;
  const koltuk = Number(yetki.pilot_koltuk || 0);
  const kullanilan = Number(yetki.pilot_kullanilan || 0);
  // `pilot_bos` sinirsiz durumda null doner — sayi DEGIL. Dogrudan
  // karsilastirma yapilmaz, aksi halde null < 1 dogru sanilir.
  const bos = sinirsiz ? null : Math.max(0, koltuk - kullanilan);
  el('#icerik').innerHTML = `
    <h2>Ekip</h2>
    <p class="aciklama">Kurumunuzun merkez hesapları. Kullanıcı tanımlama,
      rol ve durum değişikliği bu sayfadan yapılır.</p>
    ${yon ? `<div class="pano" style="margin-top:0">
      <div class="pano-baslik">Pilot koltuğu</div>
      <div class="koltuk-satir">
        <div class="koltuk-sayac">
          <strong>${sinirsiz ? '∞' : sayi(kullanilan) + ' / ' + sayi(koltuk)}</strong>
          <span>${sinirsiz ? 'Sınırsız lisans' : 'etkin pilot / koltuk'}</span>
        </div>
        ${sinirsiz ? '' : `<div class="koltuk-bar">
          <div class="koltuk-dolu" style="width:${
            koltuk > 0 ? Math.min(100, Math.round(kullanilan * 100 / koltuk)) : 0
          }%"></div></div>`}
        <div class="koltuk-islem">
          <button type="button" id="ekip-ekle">Kullanıcı ekle</button>
          ${sinirsiz ? '' :
            '<a class="dugme ikincil" href="#abonelik">Koltuk ekle</a>'}
        </div>
      </div>
      ${(!sinirsiz && bos === 0)
        ? `<p class="uyari-satir">Boş pilot koltuğunuz yok. Yeni pilot
             eklemek için koltuk satın alın veya gözlemci rolünde hesap
             açın (gözlemci koltuk tüketmez).</p>` : ''}
    </div>` : ''}
    <div class="pano"${yon ? '' : ' style="margin-top:0"'}>
      <table>
        <thead><tr><th>Ad Soyad</th><th>E-posta</th><th>Rol</th><th>Durum</th>
          <th class="sag">Uçuş</th><th class="sag">Süre</th>
          <th>Son giriş</th>${yon ? '<th></th>' : ''}</tr></thead>
        <tbody>${kayitlar.map((u) => `<tr>
          <td><strong>${kacir(`${u.ad || ''} ${u.soyad || ''}`.trim() || '—')}</strong>
            ${String(u.kullanici_id) === String(BEN.kullanici_id)
              ? ' ' + rozet('siz', 'mavi') : ''}</td>
          <td>${kacir(u.eposta)}</td>
          <td>${kacir(ROL_ADI[u.rol] || u.rol)}</td>
          <td>${rozet(u.durum, DURUM_RENK[u.durum] || 'gri')}</td>
          <td class="sag">${sayi(u.ucus_sayisi)}</td>
          <td class="sag">${sure(u.toplam_sure_sn)}</td>
          <td class="tek-satir">${tarih(u.son_giris_ts)}</td>
          ${yon ? `<td class="sag tek-satir">
            <button type="button" class="mini ekip-duzen"
              data-id="${u.kullanici_id}">Düzenle</button>
            ${String(u.kullanici_id) === String(BEN.kullanici_id) ? '' :
              `<button type="button" class="mini tehlike ekip-sil"
                data-id="${u.kullanici_id}"
                data-ad="${kacir(u.eposta)}">Sil</button>`}
          </td>` : ''}
        </tr>`).join('') ||
          `<tr><td colspan="${yon ? 8 : 7}" class="bos">Kullanıcı yok</td></tr>`}</tbody>
      </table>
    </div>`;
  if (!yon) { return; }
  const ekleDugme = el('#ekip-ekle');
  if (ekleDugme) {
    ekleDugme.addEventListener('click', () => ekipEklePencere(bos, sinirsiz));
  }
  els('.ekip-duzen').forEach((d) => d.addEventListener('click', () => {
    const k = kayitlar.filter(
      (x) => String(x.kullanici_id) === String(d.dataset.id))[0];
    if (k) { ekipDuzenPencere(k, bos, sinirsiz); }
  }));
  els('.ekip-sil').forEach((d) => d.addEventListener('click', () => {
    ekipSilPencere(d.dataset.id, d.dataset.ad);
  }));
}

/* ------------------------------------------------------------ ekip yazma */
// Rol secenekleri tek yerde tanimlanir; uc `KULLANICI_ROLLERI` ile
// dogrular ve gecersiz rolde 400 doner.
const EKIP_ROLLERI = [
  ['pilot', 'Pilot (koltuk tüketir)'],
  ['gozlemci', 'Gözlemci (koltuk tüketmez)'],
  ['firma_yonetici', 'Kurum Yöneticisi (koltuk tüketmez)']
];

function rolSecenek(secili) {
  return EKIP_ROLLERI.map(([d, a]) =>
    `<option value="${d}"${String(secili) === d ? ' selected' : ''}>${a}</option>`
  ).join('');
}

function ekipEklePencere(bos, sinirsiz) {
  const koltukYok = !sinirsiz && bos === 0;
  pencereAc('Kullanıcı ekle', `
    <form id="ekip-form" class="form-izgara">
      <label>E-posta<input type="email" name="eposta" required
        autocomplete="off"></label>
      <label>Geçici şifre<input type="text" name="sifre" required
        minlength="8" autocomplete="off"
        value="${'Goktungu' + Math.floor(Math.random() * 9000 + 1000) + '!'}"></label>
      <label>Ad<input type="text" name="ad"></label>
      <label>Soyad<input type="text" name="soyad"></label>
      <label>Telefon<input type="text" name="telefon"></label>
      <label>Pilot lisans no<input type="text" name="pilot_lisans"></label>
      <label class="tam">Rol<select name="rol">${
        rolSecenek(koltukYok ? 'gozlemci' : 'pilot')}</select></label>
      ${koltukYok ? `<p class="uyari-satir tam">Boş pilot koltuğunuz yok.
        Pilot rolü seçilirse kayıt reddedilir; koltuk satın alın veya
        gözlemci rolünü kullanın.</p>` : ''}
      <p class="aciklama tam">Kullanıcı geçici şifreyle giriş yapar ve
        şifresini kendisi değiştirir. Şifreyi güvenli bir kanaldan
        iletin.</p>
    </form>`, [
    { metin: 'Vazgeç', sinif: 'ikincil', tik: pencereKapat },
    { metin: 'Ekle', tik: async () => {
      const f = el('#ekip-form');
      if (!f.reportValidity()) { return; }
      const veri = {};
      new FormData(f).forEach((d, a) => {
        if (String(d).trim()) { veri[a] = String(d).trim(); }
      });
      try {
        await cagir('/api/firma/ekip', { method: 'POST', body: veri });
        pencereKapat();
        bildir('Kullanıcı eklendi', 'iyi');
        sayfaEkip();
      } catch (e) {
        // 409 = koltuk dolu. Kullaniciya cikis yolu gosterilir.
        const m = String(e.message || e);
        if (m.indexOf('koltuk') >= 0 || m.indexOf('409') >= 0) {
          bildir(m + ' — Abonelik sayfasından koltuk ekleyebilirsiniz.',
                 'kotu');
        } else { bildir(m, 'kotu'); }
      }
    } }
  ]);
}

function ekipDuzenPencere(k, bos, sinirsiz) {
  const kendisi = String(k.kullanici_id) === String(BEN.kullanici_id);
  pencereAc('Kullanıcı düzenle', `
    <form id="ekip-duzen-form" class="form-izgara">
      <p class="aciklama tam"><strong>${kacir(k.eposta)}</strong></p>
      <label>Ad<input type="text" name="ad" value="${kacir(k.ad || '')}"></label>
      <label>Soyad<input type="text" name="soyad"
        value="${kacir(k.soyad || '')}"></label>
      <label>Rol<select name="rol"${kendisi ? ' disabled' : ''}>${
        rolSecenek(k.rol)}</select></label>
      <label>Durum<select name="durum"${kendisi ? ' disabled' : ''}>
        <option value="etkin"${k.durum === 'etkin' ? ' selected' : ''}>Etkin</option>
        <option value="askida"${k.durum === 'askida' ? ' selected' : ''}>Askıda</option>
        <option value="iptal"${k.durum === 'iptal' ? ' selected' : ''}>İptal</option>
      </select></label>
      <label class="tam">Yeni şifre (boş bırakılırsa değişmez)
        <input type="text" name="sifre" minlength="8" autocomplete="off"></label>
      ${kendisi ? `<p class="aciklama tam">Kendi rolünüzü ve durumunuzu
        değiştiremezsiniz — kurumun yöneticisiz kalmasını önler.</p>` : ''}
      ${(!sinirsiz && bos === 0 && k.rol !== 'pilot')
        ? `<p class="uyari-satir tam">Boş pilot koltuğunuz yok; bu
             kullanıcıyı pilot yapmak reddedilir.</p>` : ''}
    </form>`, [
    { metin: 'Vazgeç', sinif: 'ikincil', tik: pencereKapat },
    { metin: 'Kaydet', tik: async () => {
      const f = el('#ekip-duzen-form');
      if (!f.reportValidity()) { return; }
      const veri = {};
      new FormData(f).forEach((d, a) => {
        if (String(d).trim()) { veri[a] = String(d).trim(); }
      });
      try {
        await cagir('/api/firma/ekip/' + encodeURIComponent(k.kullanici_id),
                    { method: 'PUT', body: veri });
        pencereKapat();
        bildir('Kullanıcı güncellendi', 'iyi');
        sayfaEkip();
      } catch (e) { bildir(String(e.message || e), 'kotu'); }
    } }
  ]);
}

function ekipSilPencere(kid, ad) {
  pencereAc('Kullanıcıyı sil', `
    <p><strong>${kacir(ad)}</strong> hesabını silmek üzeresiniz.</p>
    <p class="aciklama">Uçuş kayıtları korunur; hesap erişimi kalkar.
      Bu işlem geri alınamaz.</p>`, [
    { metin: 'Vazgeç', sinif: 'ikincil', tik: pencereKapat },
    { metin: 'Sil', sinif: 'tehlike', tik: async () => {
      try {
        await cagir('/api/firma/ekip/' + encodeURIComponent(kid),
                    { method: 'DELETE' });
        pencereKapat();
        bildir('Kullanıcı silindi', 'iyi');
        sayfaEkip();
      } catch (e) { bildir(String(e.message || e), 'kotu'); }
    } }
  ]);
}

/* ================================================================ KURUM */
async function sayfaKurum() {
  const y = await cagir('/api/firma/kurum');
  const f = y.firma || {};
  const o = y.ozet || {};
  // Logo URL'sine zaman damgası eklenir: logo değiştirildikten sonra
  // tarayıcı eski görseli önbellekten göstermesin (uç 1 gün önbellek
  // başlığı gönderir).
  const logoAdres = f.firma_id
    ? '/api/genel/firma_logo?firma_id=' + encodeURIComponent(f.firma_id) +
      '&t=' + Date.now()
    : '';
  const yoneticiMi = BEN && ['firma_yonetici', 'yonetici', 'admin']
    .indexOf(String(BEN.rol)) >= 0;
  el('#icerik').innerHTML = `
    <h2>Kurum Bilgileri</h2>
    <p class="aciklama">Merkez sistemdeki kurum kaydınız ve abonelik özeti.
      Bilgi değişikliği talepleriniz için sistem yöneticisine başvurun.</p>
    <div class="pano" style="margin-top:0">
      <div class="pano-baslik">Kurum kimliği</div>
      <div class="kurum-logo-satir">
        <div class="kurum-logo-kutu" id="kurum-logo-kutu">${
          f.logo_var
            ? `<img src="${kacir(logoAdres)}" alt="Kurum logosu">`
            : '<span class="kurum-logo-yok">Logo yok</span>'}</div>
        <div class="kurum-logo-metin">
          <strong>${kacir(f.unvan || '—')}</strong>
          <span>Bu logo GÖKTUNGU arayüzünün başlığında ve uçuş
            raporu antedinde kullanılır.</span>
          ${yoneticiMi
            ? `<div class="kurum-logo-islem">
                 <button type="button" class="ikincil"
                         id="kurum-logo-dugme">${
                   f.logo_var ? 'Logoyu değiştir' : 'Logo yükle'}</button>
                 <input type="file" id="kurum-logo-dosya"
                        accept="image/png,image/jpeg,image/webp,image/svg+xml"
                        style="display:none">
                 <span class="kurum-logo-durum" id="kurum-logo-durum"></span>
               </div>`
            : '<span class="kurum-logo-durum">Logoyu yalnızca kurum ' +
              'yöneticisi değiştirebilir.</span>'}
        </div>
      </div>
    </div>
    <div class="pano">
      <div class="pano-baslik">Kurum</div>
      <dl class="ozet">
        <dt>Ünvan</dt><dd>${kacir(f.unvan || '—')}</dd>
        <dt>Kısa ad</dt><dd><code class="kod">${kacir(f.kisa_ad || '—')}</code></dd>
        <dt>Vergi no</dt><dd>${kacir(f.vergi_no || '—')}</dd>
        <dt>Adres</dt><dd>${kacir(f.adres || '—')}</dd>
        <dt>Telefon</dt><dd>${kacir(f.telefon || '—')}</dd>
        <dt>E-posta</dt><dd>${kacir(f.eposta || '—')}</dd>
        <dt>Durum</dt><dd>${rozet(f.durum || '—', DURUM_RENK[f.durum] || 'gri')}</dd>
        <dt>Abonelik</dt><dd>${kacir(f.abonelik || '—')}</dd>
        <dt>Kayıt tarihi</dt><dd>${tarih(f.olusma_ts)}</dd>
      </dl>
    </div>
    <div class="pano">
      <div class="pano-baslik">Kullanım</div>
      <dl class="ozet">
        <dt>Kullanıcı</dt><dd>${sayi(o.kullanici)}</dd>
        <dt>Pilot koltuğu</dt><dd>${f.sinirsiz
          ? '∞ Sınırsız'
          : `${sayi(f.pilot_sayisi)} / ${sayi(f.pilot_koltuk)}`}
          ${yoneticiMi ? '<a class="ince-bag" href="#abonelik">yönet</a>' : ''}</dd>
        <dt>İstasyon</dt><dd>${sayi(o.sunucu)}${f.maks_sunucu
          ? ` / ${sayi(f.maks_sunucu)}` : ''}</dd>
        <dt>Dron</dt><dd>${sayi(o.dron)}</dd>
        <dt>Uçuş kaydı</dt><dd>${sayi(o.ucus)}</dd>
        <dt>Toplam uçuş süresi</dt><dd>${sure(o.toplam_sure_sn)}</dd>
        <dt>Video kaydı</dt><dd>${sayi(o.video)} · ${bayt(o.video_bayt)}</dd>
      </dl>
    </div>`;

  // Logo değiştirme: yalnızca yönetici için çizildiği için öğe
  // bulunamayabilir; kontrolü atlamak sayfayı pilot rolünde kırıyordu.
  const lgDugme = el('#kurum-logo-dugme');
  if (lgDugme) {
    const lgDosya = el('#kurum-logo-dosya');
    const lgDurum = el('#kurum-logo-durum');
    lgDugme.onclick = () => lgDosya.click();
    lgDosya.onchange = async (o2) => {
      const dosya = (o2.target.files || [])[0];
      if (!dosya) { return; }
      if (LOGO_TURLERI.indexOf(dosya.type) < 0) {
        lgDurum.textContent = 'Biçim desteklenmiyor (PNG, JPEG, WEBP, SVG).';
        return;
      }
      if (dosya.size > LOGO_MAKS) {
        lgDurum.textContent = 'Dosya 2 MB sınırını aşıyor.';
        return;
      }
      lgDurum.textContent = 'Yükleniyor…';
      lgDugme.disabled = true;
      try {
        const veri = await new Promise((coz, at) => {
          const r = new FileReader();
          r.onload = () => coz(String(r.result || ''));
          r.onerror = () => at(new Error('Dosya okunamadı'));
          r.readAsDataURL(dosya);
        });
        await cagir('/api/firma/logo', {
          method: 'POST', body: { logo: veri }
        });
        lgDurum.textContent = 'Logo güncellendi.';
        // Başlık logosu da anında yenilenir.
        basligiLogoyaBagla(true);
        setTimeout(() => sayfaKurum(), 600);
      } catch (e) {
        lgDurum.textContent = e.message;
      } finally {
        lgDugme.disabled = false;
      }
    };
  }
}

/* Müşteri panelinin başlığında kurum logosu.
   Kullanıcının kendi kurumsal kimliğini görmesi, hangi kurumla oturum
   açtığını doğrulamasını sağlar (birden fazla kurumda hesabı olan
   kullanıcılar için önemlidir). */
function basligiLogoyaBagla(zorla) {
  const fid = BEN && BEN.firma_id;
  const yer = el('#basli-logo');
  if (!yer) { return; }
  if (!fid) { yer.innerHTML = ''; return; }
  const adres = '/api/genel/firma_logo?firma_id=' +
                encodeURIComponent(fid) + (zorla ? '&t=' + Date.now() : '');
  const g = document.createElement('img');
  g.alt = '';
  // Logo yoksa uç 404 döner; boş kırık görsel yerine öğe kaldırılır.
  g.onerror = () => { yer.innerHTML = ''; };
  g.src = adres;
  yer.innerHTML = '';
  yer.appendChild(g);
}


/* ============================================================== YARDIMCI */
// Yonetici mi? Uc taraf `firma_yonetici` bekler; panel eski kurulumlarda
// `yonetici`/`admin` degerleri de gorebilir.
function yoneticiMiKontrol() {
  return !!(BEN && ['firma_yonetici', 'yonetici', 'admin']
    .indexOf(String(BEN.rol)) >= 0);
}

/* IS-2521-LISANS: Merkez Uygulama lisans belgesini indirir.
 * Belge `/api/firma/merkez_lisans` yanitinin kendisidir ({lisans, imza,
 * acik_anahtar}); kurulum imzayi kanonik govde uzerinden dogruladigi icin
 * JSON bicimlendirmesi imzayi bozmaz. Uc yalniz firma yoneticisine acik. */
const LISANS_YOLLARI = {
  windows: 'C:\\ProgramData\\Goktungu\\Merkez\\merkez_lisans.json',
  linux: '/var/lib/goktungu-merkez/merkez_lisans.json'
};

async function lisansBelgesiIndir(dugme) {
  if (dugme) dugme.disabled = true;
  try {
    const belge = await cagir('/api/firma/merkez_lisans', { cache: 'no-store' });
    const blob = new Blob([JSON.stringify(belge, null, 2) + '\n'],
                          { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'merkez_lisans.json';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    bildir('Lisans belgesi indirildi. Dosyayı kurulumunuzdaki lisans ' +
           'konumuna kopyalayıp Merkez servisini yeniden başlatın.', 'basari');
  } catch (e) {
    bildir(String(e.message || e), 'hata');
  } finally {
    if (dugme) dugme.disabled = false;
  }
}

function lisansDugmeleriBagla() {
  els('.lisans-indir').forEach((d) => d.addEventListener('click', () => {
    lisansBelgesiIndir(d);
  }));
}

function usd(x) {
  if (x === null || x === undefined) { return '—'; }
  return '$' + Number(x).toLocaleString('en-US',
    { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}
/* GELIR MODELI v2: TRY/USD cift para birimi.
   iyzico kurali -- "yabanci para biriminde SADECE yabanci kart
   kullanilabilir". TRY gosterilmezse yurt ici musteri Turk kartiyla
   odeme yapamaz. Bu yuzden panel iki para birimini de gosterir ve
   secim `goktungu_para` yerel anahtarinda korunur. */
var PARA = (function () {
  try {
    var v = localStorage.getItem('goktungu_para');
    return (v === 'USD' || v === 'TRY') ? v : 'TRY';
  } catch (e) { return 'TRY'; }
})();
function paraAyarla(p) {
  PARA = (p === 'USD') ? 'USD' : 'TRY';
  try { localStorage.setItem('goktungu_para', PARA); } catch (e) {}
}
function para(x, pb) {
  if (x === null || x === undefined) { return '—'; }
  var b = pb || PARA;
  var n = Number(x).toLocaleString(b === 'TRY' ? 'tr-TR' : 'en-US',
    { minimumFractionDigits: 0, maximumFractionDigits: 2 });
  return (b === 'TRY' ? '₺' : '$') + n;
}
/* Kalemden secili para birimine gore fiyat cikarir.
   Alan adlari uctan OLCULDU: aylik_try/aylik_usd/yillik_try/yillik_usd/
   tek_try/tek_usd; iskontolu karsiliklari `net_` onekli. */
function kalemFiyat(f, alan) {
  var ek = (PARA === 'TRY') ? '_try' : '_usd';
  var ham = f[alan + ek];
  if (ham === undefined || ham === null) { ham = f[alan + '_usd']; }
  var net = f['net_' + alan + ek];
  if (net === undefined || net === null) { net = f['net_' + alan]; }
  var iskontolu = (net !== undefined && net !== null
                   && Number(net) < Number(ham));
  return { ham: ham, net: iskontolu ? net : null };
}

/* ============================================================= ABONELIK */
async function sayfaAbonelik() {
  if (!yoneticiMiKontrol()) {
    el('#icerik').innerHTML =
      '<h2>Abonelik</h2><p class="aciklama">Bu sayfayı yalnızca kurum ' +
      'yöneticisi görebilir.</p>';
    return;
  }
  const [ab, od] = await Promise.all([
    cagir('/api/firma/abonelik'),
    cagir('/api/firma/odeme_durum').catch(() => null)
  ]);
  const y = ab.yetkiler || {};
  const kalemler = ab.kalemler || [];
  const talepler = ab.talepler || [];
  const fiyatlar = ab.fiyatlar || ab.kalemler || ab.paketler || [];
  /* Talep penceresi sabit liste yerine bunu okur. */
  window.SON_FIYATLAR = fiyatlar;
  const indirim = Number(ab.yillik_indirim || 0);
  const odemeAcik = !!(od && od.acik);
  const testModu = !!(od && od.test_modu);
  const sinirsiz = !!y.sinirsiz;
  const koltuk = Number(y.pilot_koltuk || 0);
  const kullanilan = Number(y.pilot_kullanilan || 0);

  const ozet = `
    <div class="pano" style="margin-top:0">
      <div class="pano-baslik">Mevcut haklarınız</div>
      <div class="yetki-izgara">
        <div class="yetki-kart${sinirsiz ? ' acik' : ''}">
          <span class="yetki-ad">Pilot koltuğu</span>
          <strong>${sinirsiz ? '∞ Sınırsız'
            : sayi(kullanilan) + ' / ' + sayi(koltuk)}</strong>
          <span class="yetki-not">${sinirsiz
            ? 'Merkez Uygulama lisansı'
            : 'ücretsiz taban 1 koltuk dahil'}</span>
        </div>
        <div class="yetki-kart${y.ai ? ' acik' : ''}">
          <span class="yetki-ad">AI sistemi</span>
          <strong>${y.ai ? 'Açık' : 'Kapalı'}</strong>
          <span class="yetki-not">${y.ai ? '' : 'aylık $10'}</span>
        </div>
        <div class="yetki-kart${y.radar ? ' acik' : ''}">
          <span class="yetki-ad">Radar modülü</span>
          <strong>${y.radar ? 'Açık' : 'Kapalı'}</strong>
          <span class="yetki-not">Üst yönetici tarafından tanımlanır</span>
        </div>
        <div class="yetki-kart${y.gccdual ? ' acik' : ''}">
          <span class="yetki-ad">GCCDUAL modülü</span>
          <strong>${y.gccdual ? 'Açık' : 'Kapalı'}</strong>
          <span class="yetki-not">Üst yönetici tarafından tanımlanır</span>
        </div>
        <div class="yetki-kart${y.merkez_lisans ? ' acik' : ''}">
          <span class="yetki-ad">Merkez Uygulama</span>
          <strong>${y.merkez_lisans ? 'Lisanslı' : 'Yok'}</strong>
          <span class="yetki-not">${y.merkez_lisans
            ? 'kendi sunucunuzda sınırsız'
            : 'tek seferlik $5.000'}</span>
          ${y.merkez_lisans ? `<button type="button" class="ikincil lisans-indir"
            style="margin-top:8px"
            title="Kurulum ve otomatik güncelleme için gerekli">Lisans belgesini indir</button>` : ''}
        </div>
      </div>
      <dl class="ozet" style="margin-top:14px">
        <dt>Abonelik</dt><dd>${kacir(y.abonelik || '—')}</dd>
        <dt>Fatura dönemi</dt><dd>${kacir(y.fatura_donemi || '—')}</dd>
        <dt>Bitiş</dt><dd>${y.abonelik_bitis ? tarih(y.abonelik_bitis) : '—'}</dd>
        <dt>Toplam hesap</dt><dd>${sayi(y.hesap_kullanilan)}</dd>
      </dl>
    </div>`;

  const fiyatKartlari = fiyatlar.map((f) => {
    const tek = f.tek_usd !== null && f.tek_usd !== undefined;
    const varOlan = (f.kalem === 'ai' && y.ai) ||
                    (f.kalem === 'merkez' && y.merkez_lisans);
    return `<div class="fiyat-kart${varOlan ? ' sahip' : ''}">
      <div class="fiyat-ad">${kacir(f.ad)}</div>
      ${(() => {
        const fa = kalemFiyat(f, tek ? 'tek' : 'aylik');
        const fy = tek ? null : kalemFiyat(f, 'yillik');
        /* Iskonto varsa ham fiyat USTU CIZILI gosterilir; musteri
           indirimi GORUR. Aksi halde odeme ekranindaki tutar farkli
           cikar ve guven kaybi olur. */
        const tutar = fa.net !== null
          ? `<s class="fiyat-ham">${para(fa.ham)}</s> ${para(fa.net)}`
          : para(fa.ham);
        return tek
          ? `<div class="fiyat-tutar">${tutar}
               <span>tek seferlik</span></div>`
          : `<div class="fiyat-tutar">${tutar}
               <span>/ ay</span></div>
             ${fy && fy.ham !== undefined && fy.ham !== null
               ? `<div class="fiyat-yillik">${
                   fy.net !== null ? para(fy.net) : para(fy.ham)} / yıl
                   <em>%${Math.round(indirim * 100)} indirimli</em></div>`
               : ''}`;
      })()}
      ${(f.iskonto_notu || (kalemFiyat(f, tek ? 'tek' : 'aylik').net !== null
         ? 'kuruma özel iskonto uygulandı' : ''))
        ? `<div class="fiyat-iskonto">${kacir(f.iskonto_notu
            || 'kuruma özel iskonto uygulandı')}</div>` : ''}
      ${f.koltuk ? `<div class="fiyat-not">+${f.koltuk} pilot koltuğu</div>`
                 : '<div class="fiyat-not">koltuk eklemez</div>'}
      ${varOlan
        ? '<div class="fiyat-sahip">Zaten sahipsiniz</div>'
        : `<div class="fiyat-islem">
             ${odemeAcik ? `<button type="button" class="satin-al"
               data-kalem="${f.kalem}" data-tek="${tek ? 1 : 0}"
               data-ad="${kacir(f.ad)}">Satın al</button>` : ''}
             <button type="button" class="ikincil talep-et"
               data-kalem="${f.kalem}" data-ad="${kacir(f.ad)}"
               data-tek="${tek ? 1 : 0}">Talep oluştur</button>
           </div>`}
    </div>`;
  }).join('');

  const kalemTablo = kalemler.length ? `
    <div class="pano">
      <div class="pano-baslik">Etkin kalemleriniz</div>
      <table>
        <thead><tr><th>Kalem</th><th class="sag">Adet</th><th>Dönem</th>
          <th>Kaynak</th><th>Başlangıç</th><th>Bitiş</th>
          <th>Durum</th></tr></thead>
        <tbody>${kalemler.map((k) => `<tr>
          <td>${kacir(k.ad || k.kalem)}</td>
          <td class="sag">${sayi(k.adet)}</td>
          <td>${kacir(k.donem || '—')}</td>
          <td>${kacir(k.kaynak || '—')}</td>
          <td class="tek-satir">${tarih(k.baslangic_ts)}</td>
          <td class="tek-satir">${k.bitis_ts ? tarih(k.bitis_ts) : '—'}</td>
          <td>${rozet(k.durum || '—', DURUM_RENK[k.durum] || 'gri')}</td>
        </tr>`).join('')}</tbody>
      </table>
    </div>` : '';

  const talepTablo = talepler.length ? `
    <div class="pano">
      <div class="pano-baslik">Üyelik talepleriniz</div>
      <table>
        <thead><tr><th>Kalem</th><th class="sag">Adet</th><th>Dönem</th>
          <th>Tarih</th><th>Durum</th><th>Not</th></tr></thead>
        <tbody>${talepler.map((t) => `<tr>
          <td>${kacir(t.ad || t.kalem)}</td>
          <td class="sag">${sayi(t.adet)}</td>
          <td>${kacir(t.donem || '—')}</td>
          <td class="tek-satir">${tarih(t.olusma_ts)}</td>
          <td>${rozet(t.durum || '—', DURUM_RENK[t.durum] ||
            (t.durum === 'onayli' ? 'yesil'
              : t.durum === 'reddedildi' ? 'kirmizi' : 'sari'))}</td>
          <td>${kacir(t.karar_notu || t.mesaj || '—')}</td>
        </tr>`).join('')}</tbody>
      </table>
    </div>` : '';

  el('#icerik').innerHTML = `
    <h2>Abonelik</h2>
    <p class="aciklama">Üyelik ücretsizdir; ilk pilot ve yönetici hesabı
      dahildir. Ek pilot koltuğu ve AI özelliği aylık veya yıllık
      abonelikle alınır. Yıllık ödemede %${Math.round(indirim * 100)}
      indirim uygulanır.</p>
    ${testModu ? `<p class="uyari-satir">Ödeme altyapısı <strong>test
      modunda</strong>. Gerçek tahsilat yapılmaz.</p>` : ''}
    ${!odemeAcik ? `<p class="uyari-satir">Çevrimiçi ödeme henüz
      etkinleştirilmedi. Talep oluşturabilirsiniz; Türkbey ekibi ön
      değerlendirme sonrası üyeliğinizi tanımlar.</p>` : ''}
    ${ozet}
    <div class="pano">
      <div class="pano-baslik">Fiyatlar
        <span class="para-secici">
          <button type="button" class="para-btn${PARA === 'TRY' ? ' etkin' : ''}"
            data-para="TRY">₺ TRY</button>
          <button type="button" class="para-btn${PARA === 'USD' ? ' etkin' : ''}"
            data-para="USD">$ USD</button>
        </span>
      </div>
      ${PARA === 'USD' ? `<p class="uyari-satir">Yabancı para biriminde
        <strong>yalnızca yabancı kart</strong> kullanılabilir. Türk
        kartıyla ödeme için ₺ TRY seçin.</p>` : ''}
      <div class="fiyat-izgara">${fiyatKartlari}</div>
      <p class="aciklama">Radar ve GCCDUAL modülleri satışa açık değildir;
        yalnızca üst yönetici tanımlar. Talep oluşturarak
        başvurabilirsiniz.</p>
    </div>
    ${kalemTablo}
    ${talepTablo}
    ${odemeAcik && kalemler.length ? `<div class="pano">
      <div class="pano-baslik">Ödeme yönetimi</div>
      <p class="aciklama">Aboneliğinizi buradan iptal edebilirsiniz.
        İptal sonrası dönem sonuna kadar haklarınız açık kalır;
        <strong>çalışan kurulumunuz kapatılmaz</strong>. Fatura
        talepleriniz için destek talebi oluşturun.</p>
      <button type="button" id="abonelik-iptal">Aboneliği iptal et</button>
    </div>` : ''}
    <div class="pano">
      <div class="pano-baslik">Özel talep</div>
      <p class="aciklama">Radar, GCCDUAL, Merkez Uygulama veya listede
        olmayan bir yapılandırma için ön talep oluşturun. Talepler
        değerlendirilerek üyelik tanımlanır.</p>
      <button type="button" class="ikincil talep-et" data-kalem=""
        data-ad="Özel talep" data-tek="0">Talep oluştur</button>
    </div>`;

  lisansDugmeleriBagla();
  els('.para-btn').forEach((d) => d.addEventListener('click', () => {
    paraAyarla(d.dataset.para);
    sayfaAbonelik();
  }));
  els('.satin-al').forEach((d) => d.addEventListener('click', () => {
    satinAlPencere(d.dataset.kalem, d.dataset.ad, d.dataset.tek === '1',
                   indirim);
  }));
  els('.talep-et').forEach((d) => d.addEventListener('click', () => {
    talepPencere(d.dataset.kalem, d.dataset.ad, d.dataset.tek === '1');
  }));
  /* iyzico'da Stripe benzeri musteri portali YOKTUR. Dugme
     abonelik iptaline baglanir. Eski `#odeme-portal` bagi kaldirildi;
     birakilirsa hicbir seye baglanmayan OLU kod olurdu ve iptal
     dugmesi tiklanmazdi. */
  const iptalDugme = el('#abonelik-iptal');
  if (iptalDugme) {
    iptalDugme.addEventListener('click', () => {
      pencereAc('Aboneliği iptal et', `
        <p class="aciklama">Abonelik yenilemesi durdurulur.
          <strong>Dönem sonuna kadar</strong> tüm haklarınız açık kalır.</p>
        <p class="aciklama">Kurulu sisteminiz <strong>kapatılmaz</strong>;
          yalnızca yeni dönem tahsilatı yapılmaz ve güncelleme hakkı
          dönem sonunda durur.</p>`, [
        { metin: 'Vazgeç', sinif: 'ikincil', tik: pencereKapat },
        { metin: 'İptal et', tik: async () => {
          try {
            await cagir('/api/firma/abonelik_iptal', { method: 'POST', body: {} });
            pencereKapat();
            bildir('Abonelik yenilemesi durduruldu', 'iyi');
            sayfaAbonelik();
          } catch (e) { bildir(String(e.message || e), 'kotu'); }
        } }
      ]);
    });
  }
}

function satinAlPencere(kalem, ad, tek, indirim) {
  pencereAc('Satın al — ' + ad, `
    <form id="satin-form" class="form-izgara">
      ${tek ? '' : `<label>Dönem<select name="donem">
        <option value="aylik">Aylık</option>
        <option value="yillik">Yıllık (%${Math.round(indirim * 100)} indirimli)</option>
      </select></label>`}
      ${tek ? '' : `<label>Adet<input type="number" name="adet" value="1"
        min="1" max="100" required></label>`}
      <p class="aciklama tam">Ödeme sayfasına yönlendirileceksiniz. Ödeme
        onaylandığında haklarınız otomatik olarak açılır.</p>
    </form>`, [
    { metin: 'Vazgeç', sinif: 'ikincil', tik: pencereKapat },
    { metin: 'Ödemeye geç', tik: async () => {
      const f = el('#satin-form');
      if (f && !f.reportValidity()) { return; }
      /* Para birimi ZORUNLU gonderilir. Sunucu tarafi hangi
         para biriminde tahsilat yapacagini tarayici secimine gore
         belirler; varsayilan sessizce USD olursa Turk musteri Turk
         kartiyla odeme yapamaz. */
      const veri = { kalem: kalem, para_birimi: PARA };
      if (!tek) {
        const fd = new FormData(f);
        veri.donem = fd.get('donem') || 'aylik';
        veri.adet = Number(fd.get('adet') || 1);
      } else {
        veri.donem = 'tek';
        veri.adet = 1;
      }
      try {
        const r = await cagir('/api/firma/checkout',
                              { method: 'POST', body: veri });
        if (r && r.url) { location.href = r.url; return; }
        bildir('Ödeme bağlantısı alınamadı', 'kotu');
      } catch (e) { bildir(String(e.message || e), 'kotu'); }
    } }
  ]);
}

function talepPencere(kalem, ad, tek) {
  /* Kalem listesi UCTAN turetilir. Sabit liste yazilirsa yeni
     paketler talep penceresinde GORUNMEZ ve musteri satin
     alamaz. `SON_FIYATLAR` sayfaAbonelik() tarafindan doldurulur. */
  const vitrin = (window.SON_FIYATLAR || [])
    .map((f) => [f.kalem || f.anahtar, f.ad])
    .filter((x) => x[0] && x[1]);
  const secenek = vitrin.length ? vitrin : [
    ['profesyonel', 'Profesyonel (pilot koltuğu)'],
    ['kurumsal_bulut', 'Kurumsal Bulut'],
    ['yz_analitik', 'Yapay Zekâ Analitiği'],
    ['GTU-MERKEZ', 'GTU-MERKEZ lisansı'],
    ['GTU-RADAR', 'GTU-RADAR modülü'],
    ['GTU-TAM', 'GTU-TAM (tam kapsam)']
  ];
  pencereAc('Üyelik talebi — ' + ad, `
    <form id="talep-form" class="form-izgara">
      <label class="tam">Kalem<select name="kalem" required>
        ${secenek.map(([d, a]) =>
          `<option value="${d}"${d === kalem ? ' selected' : ''}>${a}</option>`
        ).join('')}
      </select></label>
      <label>Adet<input type="number" name="adet" value="1" min="1"
        max="100"></label>
      <label>Dönem<select name="donem">
        <option value="aylik">Aylık</option>
        <option value="yillik">Yıllık</option>
        <option value="tek"${tek ? ' selected' : ''}>Tek seferlik</option>
      </select></label>
      <label>İletişim kişisi<input type="text" name="iletisim_ad"
        value="${kacir(((BEN.ad || '') + ' ' + (BEN.soyad || '')).trim())}"></label>
      <label>E-posta<input type="email" name="iletisim_eposta"
        value="${kacir(BEN.eposta || '')}" required></label>
      <label>Telefon<input type="text" name="iletisim_tel"></label>
      <label class="tam">Mesaj<textarea name="mesaj" rows="3"
        placeholder="Kullanım amacı, beklenen kullanıcı sayısı, özel istekler"></textarea></label>
      <p class="aciklama tam">Talebiniz Türkbey ekibi tarafından
        değerlendirilir. Onaylandığında üyeliğiniz tanımlanır ve bu
        sayfada görünür.</p>
    </form>`, [
    { metin: 'Vazgeç', sinif: 'ikincil', tik: pencereKapat },
    { metin: 'Talebi gönder', tik: async () => {
      const f = el('#talep-form');
      if (!f.reportValidity()) { return; }
      const veri = {};
      new FormData(f).forEach((d, a) => {
        if (String(d).trim()) { veri[a] = String(d).trim(); }
      });
      if (veri.adet) { veri.adet = Number(veri.adet); }
      try {
        await cagir('/api/firma/uyelik_talebi',
                    { method: 'POST', body: veri });
        pencereKapat();
        bildir('Talebiniz alındı. Değerlendirme sonrası bilgilendirileceksiniz.',
               'iyi');
        if (location.hash.slice(1).split('?')[0] === 'abonelik') {
          sayfaAbonelik();
        }
      } catch (e) { bildir(String(e.message || e), 'kotu'); }
    } }
  ]);
}

/* ====================================================== MERKEZ UYGULAMA */
async function sayfaMerkez() {
  if (!yoneticiMiKontrol()) {
    el('#icerik').innerHTML =
      '<h2>Merkez Uygulama</h2><p class="aciklama">Bu sayfayı yalnızca ' +
      'kurum yöneticisi görebilir.</p>';
    return;
  }
  const ab = await cagir('/api/firma/abonelik');
  const y = ab.yetkiler || {};
  if (!y.merkez_lisans) {
    const fiyat = (ab.fiyatlar || []).filter((f) => f.kalem === 'merkez')[0];
    el('#icerik').innerHTML = `
      <h2>Merkez Uygulama</h2>
      <p class="aciklama">Merkez Uygulama, GÖKTUNGU komuta kontrol yazılımını
        kendi sunucunuzda çalıştırmanızı sağlar.</p>
      <div class="pano" style="margin-top:0">
        <div class="pano-baslik">Lisansınız bulunmuyor</div>
        <p>Merkez Uygulama lisansı ile:</p>
        <ul class="madde">
          <li><strong>Sınırsız pilot koltuğu</strong> — koltuk ücreti
            uygulanmaz</li>
          <li><strong>AI sistemi dahil</strong> — ayrı ücret yok</li>
          <li><strong>Kapalı devre çalışma</strong> — internet bağlantısı
            gerekmez, veriler kurumunuzdan çıkmaz</li>
          <li>Windows ve Ubuntu kurulum paketleri</li>
          <li>Radar ve GCCDUAL yetkileriniz varsa kurulumunuzda da açık
            gelir</li>
        </ul>
        <p class="fiyat-tutar" style="margin:16px 0">${
          fiyat ? usd(fiyat.tek_usd) : '$5.000'}
          <span>tek seferlik</span></p>
        <button type="button" class="ikincil talep-et" data-kalem="merkez"
          data-ad="Merkez Uygulama kurulumu" data-tek="1">Talep oluştur</button>
        <a class="dugme" href="#abonelik">Abonelik sayfası</a>
      </div>`;
    els('.talep-et').forEach((d) => d.addEventListener('click', () => {
      talepPencere(d.dataset.kalem, d.dataset.ad, true);
    }));
    return;
  }
  let paket = null;
  try {
    paket = await cagir('/api/firma/merkez_paketler', { cache: 'no-store' });
  } catch (e) {
    el('#icerik').innerHTML = `<h2>Merkez Uygulama</h2>
      <p class="uyari-satir">${kacir(String(e.message || e))}</p>`;
    return;
  }
  const kayitlar = paket.kayitlar || [];
  const win = kayitlar.filter((k) => k.platform === 'windows');
  const lin = kayitlar.filter((k) => k.platform === 'linux' ||
                                     k.platform === 'ubuntu');
  /* Ortak `paketKarti` kullanilir: en guncel surum one cikar, eskiler
   * katlanir (bkz. dosya basindaki OLCULEN KUSUR notu). */
  const kart = (baslik, liste, ipucu) =>
    paketKarti(baslik, liste, ipucu, 'merkez_indir',
               paket.app_guncel || '');
  el('#icerik').innerHTML = `
    <h2>Merkez Uygulama</h2>
    <p class="aciklama">Lisansınız etkin. Kurulum paketlerini indirip kendi
      sunucunuzda çalıştırabilirsiniz.</p>
    <div class="pano" style="margin-top:0">
      <div class="pano-baslik">Lisans</div>
      <dl class="ozet">
        <dt>Durum</dt><dd>${rozet('lisanslı', 'yesil')}</dd>
        <dt>Lisans kodu</dt><dd><code class="kod">${
          kacir(paket.lisans_uid || '—')}</code></dd>
        <dt>Tanımlanma</dt><dd>${tarih(y.merkez_lisans_ts)}</dd>
        <dt>Pilot koltuğu</dt><dd>Sınırsız</dd>
        <dt>AI sistemi</dt><dd>${y.ai ? 'Dahil' : 'Kapalı'}</dd>
        <dt>Radar</dt><dd>${y.radar ? 'Açık' : 'Kapalı'}</dd>
        <dt>GCCDUAL</dt><dd>${y.gccdual ? 'Açık' : 'Kapalı'}</dd>
      </dl>
      <p class="aciklama">Kurulum paketi lisans belgesini İÇERMEZ. Belgeyi
        indirip aşağıdaki konuma kopyalayın ve Merkez servisini yeniden
        başlatın. Yazılım belgenin imzasını internet bağlantısı olmadan
        doğrular; otomatik güncelleme de bu belgeyle yetkilendirilir.</p>
      <p><button type="button" class="lisans-indir">Lisans belgesini indir
        (merkez_lisans.json)</button></p>
      <dl class="ozet">
        <dt>Windows</dt><dd><code class="kod">${kacir(LISANS_YOLLARI.windows)}</code></dd>
        <dt>Ubuntu / Linux</dt><dd><code class="kod">${kacir(LISANS_YOLLARI.linux)}</code></dd>
      </dl>
    </div>
    ${kart('Windows', win,
      'Kurulumu yönetici olarak çalıştırın. Yazılım Windows servisi ' +
      'olarak kaydolur ve ilk açılışta PostgreSQL bağlantı sihirbazı ' +
      'gelir.')}
    ${kart('Ubuntu / Linux', lin,
      'Kurulum: <code class="kod">sudo dpkg -i &lt;dosya&gt;.deb</code> · ' +
      'Servis: <code class="kod">goktungu-merkez</code> · İlk açılışta ' +
      'yerel web arayüzünde PostgreSQL sihirbazı gelir.')}
    <div class="pano">
      <div class="pano-baslik">Kurulum sonrası</div>
      <ol class="madde">
        <li>Yerel web arayüzünü açın (varsayılan
          <code class="kod">http://127.0.0.1:8080</code>)</li>
        <li>PostgreSQL sihirbazında sunucu, veritabanı, kullanıcı ve şifre
          bilgilerini girin; tablolar otomatik oluşturulur</li>
        <li><strong>Merkez Kullanıcıları</strong> adımında merkez adresini
          ve kurum yöneticisi girişinizi verin; ekip hesaplarınız
          şifreleriyle birlikte kurulumunuza aktarılır. Bu adımdan sonra
          kurulum kapalı devre çalışabilir.</li>
        <li>Köprü yazılımını aynı makineye kurabilirsiniz; köprü panelinde
          merkez adresi olarak <code class="kod">127.0.0.1</code>
          girilir</li>
      </ol>
    </div>`;
  lisansDugmeleriBagla();
}


// --------------------------------------------------------- kopru indirmeleri
// KULLANICI KARARI (2026-08-16): "bence herkes uye panelinden indirsin,
// ayni merkez yazilim gibi. siteye direkt koymayalim"
//
// OLCULEN KUSUR: tanitim sayfasindaki kopru baglantisi 1.4.2 surumune
// isaret ediyordu (guncel 1.5.6); kurumsal panelde kopru indirmesi HIC
// yoktu. Kullanici: "bende pilotlari ve kopru yazilimini indirme linkini
// goremiyorum".
//
// NEDEN LISANS SORULMUYOR: kopru UCRETSIZDIR (kullanici: "kullanicilarin
// bu yazilimi indirip kurmasina gerek yok sadece kopru yazilimini
// indirseler yeter"). Tek sart oturumdur.
/* ------------------------------------------------ goruntu koprusu indirmeleri
 * [IS83-PANEL-GORUNTU]
 *
 * Goruntu Koprusu, sokulen video/AI katmaninin (Is 71-74) yerine gecen
 * AYRI urundur. Kamera yakalama ve AI cikarimi TEK SURECTE, tek dongude
 * birlesiktir; goruntu merkeze HIC gonderilmez.
 *
 * NEDEN AYRI SAYFA (Kopru sayfasina kart eklenmedi): farkli urun, farkli
 * depo anahtari (`video`), farkli port (8802) ve farkli kurulum
 * yordami. Ayni sayfada gostermek iki urunu tek paket sanmaya yol
 * acardi.
 *
 * NEDEN `appGuncel` GECILMIYOR: guncellik seridi paketin tasidigi App
 * surumunu cevrimici App surumuyle karsilastirir. Goruntu Koprusu
 * App'ten BAGIMSIZ bir urundur; boyle bir karsilik yoktur. Parametre
 * gecilmezse `paketKarti` seridi hic uretmez (olculdu).
 */
async function sayfaGoruntu() {
  let paket;
  try {
    paket = await cagir('/api/firma/goruntu_paketler');
  } catch (e) {
    el('#icerik').innerHTML = `<h2>Görüntü Köprüsü</h2>
      <p class="uyari-satir">${kacir(String(e.message || e))}</p>`;
    return;
  }
  const kayitlar = paket.kayitlar || [];
  const win = kayitlar.filter((k) => k.platform === 'windows');
  const lin = kayitlar.filter((k) => k.platform === 'linux' ||
                                     k.platform === 'ubuntu');
  /* ANDROID GORUNTU KOPRUSU (BRDIAN) — com.turkbey.goktungu.image
   * Ayni `video` urunu ve `android` platformu altinda dagitilir; boylece
   * sunucudaki statik `/indir/video/` oturum kapisi bu APK'yi da korur.
   * Windows/Ubuntu ile ayni `goruntu_indir` ucundan iner. */
  const android = kayitlar.filter((k) => k.platform === 'android');
  const kart = (baslik, liste, ipucu) =>
    paketKarti(baslik, liste, ipucu, 'goruntu_indir');
  el('#icerik').innerHTML = `
    <h2>Görüntü Köprüsü</h2>
    <p class="aciklama">Görüntü Köprüsü, kameralarınızı <strong>kendi
      bilgisayarınızda</strong> işler. Kamera yakalama ve yapay zekâ
      çıkarımı yerel süreçte birleşiktir; <strong>ham görüntü bulut merkeze
      aktarılmaz</strong>. Ücretsizdir ve her kurumsal hesap indirebilir.</p>
    <div class="pano">
      <div class="pano-baslik">Yerel Merkez ile canlı görüntü</div>
      <p class="aciklama">Merkez Uygulaması <strong>2.5.19</strong>,
        internetten bağımsız kurulumda yerel USB ve açıkça tanımlanmış
        RTSP(S) kameraları Köprü gerektirmeden yönetebilir. Canlı görüntü,
        aynı yerel sunucunun oturum korumalı yolu üzerinden gösterilir;
        kamera adresi ve kaynak kimlik bilgileri URL’ye ya da merkez durum
        paketlerine yazılmaz. Görüntü Köprüsü ise yerel görüntü işleme için
        ayrı ve isteğe bağlı üründür.</p>
    </div>
    ${kart('Windows', win,
      'Kurulumu yönetici olarak çalıştırın. Köprü Windows servisi olarak ' +
      'kaydolur ve makine açılışında kendiliğinden başlar. Windows 10/11 ' +
      '64 bit. Gömülü Python içerir; ayrıca kurulum gerekmez.')}
    ${kart('Ubuntu / Linux', lin,
      'Kurulum: <code class="kod">sudo dpkg -i &lt;dosya&gt;.deb</code> · ' +
      'Servis: <code class="kod">goktungu-goruntu</code> · Panel: ' +
      '<code class="kod">http://127.0.0.1:8802</code> · Ubuntu 22.04 ve ' +
      'üzeri. Kurulum sırasında bağımlılıklar indirilir; internet ' +
      'bağlantısı gerekir.')}
    ${kart('Android — Görüntü Köprüsü', android,
      'GOKTUNGU Görüntü Köprüsü (Android): telefon veya tabletinizin ' +
      'kamerasını yerel Merkez Uygulamanıza (GRCON) ya da çevrimdışı ' +
      'merkeze (GRCOFF) köprüler; görüntü işleme ve tespit cihazda ' +
      'yereldir, ham görüntü buluta aktarılmaz. APK doğrudan iner: ' +
      'kurulum için cihazınızda <strong>bilinmeyen kaynaklardan ' +
      'kuruluma</strong> izin vermeniz gerekir (Ayarlar → Güvenlik). ' +
      'Android 8.0 ve üzeri. Sürüm 1.0.0.')}
    <div class="pano">
      <div class="pano-baslik">Kurulum sonrası</div>
      <ol class="madde">
        <li>Panel tarayıcıda açılır:
          <code class="kod">http://127.0.0.1:8802</code></li>
        <li><em>Kameralar</em> sayfasından tarama yapın ve kameranızı
          ekleyin</li>
        <li><em>AI Ayarları</em> sayfasından hassasiyeti ve tespit
          türlerini seçin</li>
        <li>Tespitler yerel veritabanına yazılır; merkeze aktarılmaz</li>
      </ol>
      <p class="aciklama">GPU varsa kendiliğinden kullanılır, yoksa CPU
        ile çalışır; ayar gerekmez. Merkez arayüzündeki
        <em>AI → Görüntü Köprüsü</em> menüsü bu paneli açar.</p>
    </div>
    <div class="pano">
      <div class="pano-baslik">Bu sürümde tespit edilenler</div>
      <p class="aciklama"><strong>İnsan</strong> ve <strong>araç</strong>
        (otomobil, kamyon, otobüs, motosiklet, bisiklet) tespiti
        çalışır. <strong>Dron ve plaka tanıma bu sürümde yoktur</strong>
        ve arayüzde devre dışı görünür; kullanılan açık modelin sınıf
        listesinde bu iki tür bulunmuyor. Özel model çalışması
        sürüyor.</p>
    </div>
    <div class="pano">
      <div class="pano-baslik">M50 görünür ve termal kaynakları</div>
      <p class="aciklama">Görüntü Köprüsü <strong>1.3.8</strong>, operatörün
        açıkça tanımladığı M50 görünür ve termal RTSP(S) kaynak türlerini
        yerel işleme için destekler. M50’nin üretici SDK video çağrıları bu
        katmana taşınmaz; RTSP(S) kaynağı ile SDK kontrolü birbirinden
        ayrıdır.</p>
    </div>
    <div class="pano">
      <div class="pano-baslik">Merkez Uygulama ve Köprü ile birlikte</div>
      <p class="aciklama">Üç yazılım aynı makinede çalışabilir; portlar
        çakışmayacak biçimde ayrılmıştır. Köprü
        <code class="kod">8790</code>, Görüntü Köprüsü
        <code class="kod">8802</code> portunu kullanır.</p>
    </div>`;
}
async function sayfaKopru() {
  let paket = null;
  try {
    paket = await cagir('/api/firma/kopru_paketler');
  } catch (e) {
    el('#icerik').innerHTML = `<h2>Köprü Yazılımı</h2>
      <p class="uyari-satir">${kacir(String(e.message || e))}</p>`;
    return;
  }
  const kayitlar = paket.kayitlar || [];
  const win = kayitlar.filter((k) => k.platform === 'windows');
  const lin = kayitlar.filter((k) => k.platform === 'linux' ||
                                     k.platform === 'ubuntu');
  /* ANDROID KOPRULERI — FAZ19-IS39-ANDROID-KOPRU
   * Android kopru uygulamasi ayni urun (`kopru`) ve ayni platform
   * (`android`) altinda durur; APK dosya adiyla suzulur. Ayri urun
   * kimligi kullanilmadi cunku sunucudaki statik `/indir/<urun>/`
   * oturum kapisi urun adina bakiyor ve yeni urun adlari oraya
   * eklenmezse APK'lar oturumsuz inebilirdi.
   * Suzgec tire ile SARILI arar: `-MAVLINK-` bir sozcugun icinde
   * gecen `MAVLINK` ile eslesmez. Buyuk/kucuk harf duyarsiz. */
  const apkTur = (anahtar) => kayitlar.filter(
    (k) => k.platform === 'android' &&
           String(k.dosya_ad || '').toUpperCase()
             .indexOf('-' + anahtar + '-') !== -1);
  const androidMav = apkTur('MAVLINK');
  /* Ortak `paketKarti` kullanilir: en guncel surum one cikar, eskiler
   * katlanir (bkz. dosya basindaki OLCULEN KUSUR notu). */
  const kart = (baslik, liste, ipucu) =>
    paketKarti(baslik, liste, ipucu, 'kopru_indir');
  el('#icerik').innerHTML = `
    <h2>Köprü Yazılımı</h2>
    <p class="aciklama">Köprü, sahadaki bilgisayarınızdaki dron, radar ve
      GCCDUAL donanımlarını merkez sistemine bağlar. M50 kontrol katmanı
      yalnızca yetkilendirilmiş <strong>Windows x64</strong> saha Köprüsünde
      bulunur; görüntü ve yerel yapay zekâ işleme bu paketten ayrıdır.
      <strong>Ücretsizdir</strong> ve her kurumsal hesap indirebilir.</p>
    ${kart('Windows', win,
      'Kurulumu yönetici olarak çalıştırın. Köprü Windows servisi olarak ' +
      'kaydolur; masaüstü ve başlat menüsü kısayolları oluşur. Güncelleme ' +
      'kurulumu servisi durdurup yerinde günceller.')}
    ${kart('Ubuntu / Linux', lin,
      'Kurulum: <code class="kod">sudo dpkg -i &lt;dosya&gt;.deb</code> · ' +
      'Servis: <code class="kod">goktungu-kopru</code> · Panel: ' +
      '<code class="kod">http://127.0.0.1:8790</code>')}
    ${kart('Android — Pixhawk / MAVLink', androidMav,
      'Telefon veya tabletinizi Pixhawk uçuş denetleyicisine USB OTG ya ' +
      'da telemetri bağlantısıyla bağlar; ArduPilot ve PX4 desteklenir. ' +
      'APK doğrudan iner: kurulum için cihazınızda ' +
      '<strong>bilinmeyen kaynaklardan kuruluma</strong> izin vermeniz ' +
      'gerekir (Ayarlar → Güvenlik). Android 8.0 ve üzeri.')}
    <div class="pano">
      <div class="pano-baslik">Kurulum sonrası</div>
      <ol class="madde">
        <li>Köprü panelini açın
          (<code class="kod">http://127.0.0.1:8790</code>)</li>
        <li>Kurumsal hesabınızla giriş yapın; kurum logonuz ve yetkileriniz
          panele yansır</li>
        <li>Dron, radar ve GCCDUAL bağlantılarını panelden yapılandırın;
          durum ve konsol çıktıları aynı ekranda görünür</li>
        <li>M50 için resmi SDK dizinini operatör seçer; cihaz bağlantısı
          yalnız açık IP, port, kullanıcı ve parola girişiyle başlar</li>
        <li>Radar, GCCDUAL ve M50 menüleri yalnızca kurumunuzda ilgili
          yetkiler açıksa listelenir</li>
      </ol>
      <p class="aciklama">M50 yetkisi yeni ve eski lisanslarda kapalı
        varsayılır. Etkin olduğunda yalnız sınırlı PTZ, lens, açı ve
        operatörün açık seçimine dayalı takip denetimleri sunulur; otomatik
        hedef edinimi veya otonom hareket işlevi yoktur. Merkez Uygulama
        satın aldıysanız Köprüyü aynı makinede çalıştırabilirsiniz; portlar
        çakışmayacak biçimde ayrılmıştır.</p>
    </div>`;
}

/* ================================================================ DESTEK */
/* Kullanıcı tarafı ticket arayüzü.
 *
 * Ek gönderiminde `data:` öneki KIRPILIR: sunucu ucu
 * `b64decode(..., validate=True)` kullanır ve `data:image/png;base64,`
 * öneki bu doğrulamadan geçmez ("Ek base64 cozulemedi" hatası verirdi).
 *
 * Biçem: mevcut sınıflar kullanılır (`arac-cubugu`, `pano`, `ozet`,
 * `kod`, `aciklama`, `bos`); yalnız destek bileşenleri yeni sınıf
 * tanımlar (`yazisma`, `mesaj`, `ek-*`).
 */
const DESTEK_DURUM_AD = {
  yeni: 'Yeni', islemde: 'İşlemde', yanit_bekliyor: 'Yanıt bekliyor',
  cozuldu: 'Çözüldü', kapandi: 'Kapandı'
};
const DESTEK_DURUM_RENK = {
  yeni: 'mavi', islemde: 'sari', yanit_bekliyor: 'sari',
  cozuldu: 'yesil', kapandi: 'gri'
};
const DESTEK_ONCELIK_AD = {
  dusuk: 'Düşük', normal: 'Normal', yuksek: 'Yüksek', kritik: 'Kritik'
};
const DESTEK_ONCELIK_RENK = {
  dusuk: 'gri', normal: 'mavi', yuksek: 'sari', kritik: 'kirmizi'
};
/* Modül adları sunucuda ASCII saklanır (ölçüldü); arayüzde Türkçe
   karşılıkları gösterilir. Anahtarlar sunucudan gelenle aynı. */
const DESTEK_MODUL_AD = {
  app: 'GCS Uygulaması', kopru: 'Köprü Yazılımı',
  merkez: 'Merkez Uygulama', radar: 'Radar Modülü',
  gccdual: 'Yer Kontrol İstasyonu Dual',
  ai: 'AI Sunucusu', video: 'Video Sunucusu',
  kurumsal_panel: 'Kurumsal Panel', yonetim_paneli: 'Yönetim Paneli',
  odeme: 'Ödeme / Abonelik', kurulum: 'Kurulum / Sihirbaz',
  diger: 'Diğer'
};
const DESTEK_EK_MAKS = 8 * 1024 * 1024;
const DESTEK_EK_ADET = 5;
const DESTEK_EK_KABUL = 'image/png,image/jpeg,image/webp,image/gif,' +
  'application/pdf,text/plain,application/json,application/zip,text/csv';
const DESTEK_EK_TURLER = DESTEK_EK_KABUL.split(',');
let DESTEK_EKLER = [];        // seçili ekler: {ad, mime, veri, boyut}

function destekModulAd(a) {
  return DESTEK_MODUL_AD[a] || a || '—';
}

/* Dosyayı çıplak base64'e çevirir. `data:` öneki kırpılır. */
function destekDosyaOku(dosya) {
  return new Promise((coz, at) => {
    const r = new FileReader();
    r.onload = () => {
      const tam = String(r.result || '');
      const v = tam.slice(tam.indexOf(',') + 1);
      if (!v) { at(new Error('Dosya boş okundu: ' + dosya.name)); return; }
      coz(v);
    };
    r.onerror = () => at(new Error('Dosya okunamadı: ' + dosya.name));
    r.readAsDataURL(dosya);
  });
}

function destekEkListeYaz() {
  const kap = el('#destek-ek-liste');
  if (!kap) return;
  if (!DESTEK_EKLER.length) {
    kap.innerHTML = '<span class="aciklama">Ek seçilmedi.</span>';
    return;
  }
  kap.innerHTML = DESTEK_EKLER.map((e, i) => `
    <span class="ek-fisi">
      ${kacir(e.ad)} <span class="ek-boyut">${(e.boyut / 1024).toFixed(0)} KB</span>
      <button type="button" class="ek-sil" onclick="destekEkSil(${i})"
              title="Ekten çıkar">×</button>
    </span>`).join('');
}
window.destekEkSil = (i) => { DESTEK_EKLER.splice(i, 1); destekEkListeYaz(); };

async function destekEkSec(dosyalar) {
  const durum = el('#destek-ek-durum');
  const liste = Array.from(dosyalar || []);
  if (!liste.length) return;
  if (DESTEK_EKLER.length + liste.length > DESTEK_EK_ADET) {
    durum.textContent = `En fazla ${DESTEK_EK_ADET} dosya eklenebilir.`;
    return;
  }
  durum.textContent = '';
  for (const d of liste) {
    if (DESTEK_EK_TURLER.indexOf(d.type) < 0) {
      durum.textContent = `Desteklenmeyen dosya türü: ${d.name} (${d.type || '?'})`;
      continue;
    }
    if (d.size > DESTEK_EK_MAKS) {
      durum.textContent = `${d.name} çok büyük ` +
        `(${(d.size / 1048576).toFixed(1)} MB); en fazla 8 MB.`;
      continue;
    }
    try {
      const veri = await destekDosyaOku(d);
      DESTEK_EKLER.push({ ad: d.name, mime: d.type, veri, boyut: d.size });
    } catch (e) {
      durum.textContent = e.message;
    }
  }
  destekEkListeYaz();
}

/* Ek seçme alanı — iki yerde kullanılır (yeni talep, yanıt). */
function destekEkAlanHTML(id) {
  return `
    <div class="ek-alan">
      <input id="${id}" type="file" multiple accept="${DESTEK_EK_KABUL}"
             style="display:none">
      <button type="button" class="ikincil kucuk"
              onclick="document.getElementById('${id}').click()">
        Dosya ekle</button>
      <span class="aciklama">en fazla ${DESTEK_EK_ADET} dosya, her biri 8 MB
        — görsel, PDF, metin, ZIP</span>
      <div id="destek-ek-liste" class="ek-liste">
        <span class="aciklama">Ek seçilmedi.</span></div>
      <div id="destek-ek-durum" class="hata"></div>
    </div>`;
}
function destekEkAlanBagla(id) {
  DESTEK_EKLER = [];
  const g = el('#' + id);
  if (!g) return;
  g.onchange = (o) => {
    destekEkSec(o.target.files);
    o.target.value = '';        // aynı dosya yeniden seçilebilsin
  };
}

async function sayfaDestek(par) {
  DURUM.destek = Object.assign({ durum: '' }, DURUM.destek, par);
  const s = DURUM.destek;
  const [y, m] = await Promise.all([
    cagir('/api/destek/talepler' + (s.durum ? '?durum=' + s.durum : '')),
    cagir('/api/destek/moduller')
  ]);
  const talepler = y.talepler || [];
  const moduller = m.moduller || [];

  el('#icerik').innerHTML = `
    <h2>Destek Talepleri</h2>
    <p class="aciklama">Yaşadığınız sorunu ilgili modülü seçerek bildirin.
      Ekran görüntüsü veya günlük dosyası ekleyebilirsiniz. Türkbey
      destek ekibi taleplerinizi bu ekrandan yanıtlar.</p>
    <div class="arac-cubugu">
      <select id="destek-durum-suzgec">
        <option value="">Tüm durumlar</option>
        ${Object.keys(DESTEK_DURUM_AD).map((d) =>
          `<option value="${d}"${s.durum === d ? ' selected' : ''}>${
            DESTEK_DURUM_AD[d]}</option>`).join('')}
      </select>
      <div class="bosluk"></div>
      <button id="destek-yeni">+ Yeni Talep</button>
    </div>
    <div class="pano" style="margin-top:0">
      <table>
        <thead><tr><th>Talep No</th><th>Modül</th><th>Konu</th>
          <th>Öncelik</th><th>Durum</th><th class="sag">Mesaj</th>
          <th>Güncelleme</th><th></th></tr></thead>
        <tbody>${talepler.map((t) => `<tr>
          <td class="tek-satir"><code class="kod">${kacir(t.ticket_no)}</code></td>
          <td>${kacir(destekModulAd(t.modul))}</td>
          <td>${kacir(t.konu)}</td>
          <td>${rozet(DESTEK_ONCELIK_AD[t.oncelik] || t.oncelik,
                      DESTEK_ONCELIK_RENK[t.oncelik] || 'gri')}</td>
          <td>${rozet(DESTEK_DURUM_AD[t.durum] || t.durum,
                      DESTEK_DURUM_RENK[t.durum] || 'gri')}</td>
          <td class="sag">${sayi(t.mesaj || 0)}${t.ek ?
            ` <span class="aciklama">+${sayi(t.ek)} ek</span>` : ''}</td>
          <td class="tek-satir">${tarih(t.guncel_ts)}</td>
          <td class="sag"><button class="ikincil kucuk"
                onclick="destekAc(${t.ticket_id})">Aç</button></td>
        </tr>`).join('') ||
          '<tr><td colspan="8" class="bos">Henüz destek talebi açmadınız</td></tr>'}
        </tbody>
      </table>
    </div>`;

  el('#destek-durum-suzgec').onchange = (o) => {
    DURUM.destek.durum = o.target.value;
    sayfaDestek();
  };
  el('#destek-yeni').onclick = () => destekYeniPencere(moduller);
}

function destekYeniPencere(moduller) {
  pencereAc('Yeni Destek Talebi', `
    <div class="ikili">
      <div>
        <label for="d-modul">Sorun yaşadığınız modül</label>
        <select id="d-modul">
          ${moduller.map((m) => `<option value="${kacir(m.anahtar)}">${
            kacir(destekModulAd(m.anahtar))}</option>`).join('')}
        </select>
      </div>
      <div>
        <label for="d-oncelik">Öncelik</label>
        <select id="d-oncelik">
          ${Object.keys(DESTEK_ONCELIK_AD).map((o) =>
            `<option value="${o}"${o === 'normal' ? ' selected' : ''}>${
              DESTEK_ONCELIK_AD[o]}</option>`).join('')}
        </select>
      </div>
    </div>
    <label for="d-konu">Konu</label>
    <input id="d-konu" type="text" maxlength="200"
           placeholder="Sorunu tek cümleyle özetleyin">
    <label for="d-aciklama">Ayrıntılı açıklama</label>
    <textarea id="d-aciklama" rows="7"
      placeholder="Ne yaptığınızda oluştuğunu, beklediğiniz ve gördüğünüz davranışı yazın."></textarea>
    <label>Ekler</label>
    ${destekEkAlanHTML('d-ek-girdi')}
    <div class="hata" id="d-hata"></div>`, [
    { metin: 'Vazgeç', sinif: 'ikincil', tik: pencereKapat },
    { metin: 'Talebi Gönder', tik: destekGonder }
  ], true);
  destekEkAlanBagla('d-ek-girdi');
}

async function destekGonder() {
  const hata = el('#d-hata');
  const konu = el('#d-konu').value.trim();
  const aciklama = el('#d-aciklama').value.trim();
  if (konu.length < 3) {
    hata.textContent = 'Konu en az 3 karakter olmalı.'; return;
  }
  if (aciklama.length < 10) {
    hata.textContent = 'Açıklama en az 10 karakter olmalı.'; return;
  }
  const dugme = els('#pencere-alt button').pop();
  dugme.disabled = true;
  hata.textContent = '';
  try {
    const y = await cagir('/api/destek/talepler', {
      method: 'POST',
      body: {
        modul: el('#d-modul').value,
        oncelik: el('#d-oncelik').value,
        konu, aciklama,
        ekler: DESTEK_EKLER.map((e) => ({ ad: e.ad, mime: e.mime, veri: e.veri }))
      }
    });
    pencereKapat();
    bildir(`Talep oluşturuldu: ${y.ticket_no}`, 'basari');
    if (y.ek_uyari) bildir(y.ek_uyari, 'uyari');
    DESTEK_EKLER = [];
    await sayfaDestek();
  } catch (e) {
    hata.textContent = e.message;
  } finally {
    dugme.disabled = false;
  }
}

window.destekAc = async (tid) => {
  const y = await cagir('/api/destek/talep/' + tid);
  const t = y.talep || {};
  const mesajlar = y.mesajlar || [];
  const ekler = y.ekler || [];
  const kapali = t.durum === 'kapandi';
  const ekleriMesaja = (mid) => ekler.filter((e) => e.mesaj_id === mid);

  pencereAc(`${t.ticket_no} — ${t.konu}`, `
    <dl class="ozet">
      <dt>Modül</dt><dd>${kacir(destekModulAd(t.modul))}</dd>
      <dt>Öncelik</dt><dd>${rozet(DESTEK_ONCELIK_AD[t.oncelik] || t.oncelik,
        DESTEK_ONCELIK_RENK[t.oncelik] || 'gri')}</dd>
      <dt>Durum</dt><dd>${rozet(DESTEK_DURUM_AD[t.durum] || t.durum,
        DESTEK_DURUM_RENK[t.durum] || 'gri')}</dd>
      <dt>Açılış</dt><dd>${tarih(t.olusma_ts)}</dd>
    </dl>
    <div class="yazisma">
      ${mesajlar.map((m) => {
        const me = ekleriMesaja(m.mesaj_id);
        return `<div class="mesaj ${m.yazan_tur === 'kullanici' ?
            'benim' : 'destek'}">
          <div class="mesaj-bas">
            <strong>${kacir(m.yazan_ad || (m.yazan_tur === 'kullanici' ?
              'Siz' : 'Türkbey Destek'))}</strong>
            <span class="aciklama">${tarih(m.olusma_ts)}</span>
          </div>
          <div class="mesaj-govde">${kacir(m.govde).replace(/\n/g, '<br>')}</div>
          ${me.length ? `<div class="mesaj-ekler">${me.map((e) =>
            `<a class="ek-bag" href="/api/destek/ek/${e.ek_id}" target="_blank"
                rel="noopener">⇩ ${kacir(e.dosya_ad)}
              <span class="ek-boyut">${(e.boyut / 1024).toFixed(0)} KB</span></a>`
          ).join('')}</div>` : ''}
        </div>`;
      }).join('')}
    </div>
    ${kapali ? `<p class="aciklama" style="margin-top:14px">Bu talep
      kapatıldı; yeni mesaj eklenemez. Sorun yeniden oluştuysa yeni bir
      talep açın.</p>` : `
    <label for="d-yanit">Yanıtınız</label>
    <textarea id="d-yanit" rows="4"
              placeholder="Eklemek istediğinizi yazın"></textarea>
    ${destekEkAlanHTML('d-yanit-ek')}
    <div class="hata" id="d-yanit-hata"></div>`}`, kapali ? [
    { metin: 'Kapat', sinif: 'ikincil', tik: pencereKapat }
  ] : [
    { metin: 'Kapat', sinif: 'ikincil', tik: pencereKapat },
    { metin: 'Çözüldü, Kapat', sinif: 'ikincil',
      tik: () => destekTalepKapat(tid) },
    { metin: 'Yanıt Gönder', tik: () => destekYanitGonder(tid) }
  ], true);

  if (!kapali) destekEkAlanBagla('d-yanit-ek');
  // Yazışma en alta kaydırılır: en yeni mesaj görünür olmalı.
  const yz = el('.yazisma');
  if (yz) yz.scrollTop = yz.scrollHeight;
};

async function destekYanitGonder(tid) {
  const hata = el('#d-yanit-hata');
  const govde = el('#d-yanit').value.trim();
  if (!govde) { hata.textContent = 'Mesaj boş olamaz.'; return; }
  const dugme = els('#pencere-alt button').pop();
  dugme.disabled = true;
  hata.textContent = '';
  try {
    const y = await cagir(`/api/destek/talep/${tid}/mesaj`, {
      method: 'POST',
      body: {
        govde,
        ekler: DESTEK_EKLER.map((e) => ({ ad: e.ad, mime: e.mime, veri: e.veri }))
      }
    });
    if (y.ek_uyari) bildir(y.ek_uyari, 'uyari');
    DESTEK_EKLER = [];
    bildir('Yanıtınız gönderildi.', 'basari');
    await window.destekAc(tid);          // yazışmayı yenile
    await sayfaDestek();
  } catch (e) {
    hata.textContent = e.message;
  } finally {
    dugme.disabled = false;
  }
}

async function destekTalepKapat(tid) {
  try {
    await cagir(`/api/destek/talep/${tid}/kapat`, { method: 'POST' });
    pencereKapat();
    bildir('Talep kapatıldı.', 'basari');
    await sayfaDestek();
  } catch (e) {
    bildir(e.message, 'hata');
  }
}
