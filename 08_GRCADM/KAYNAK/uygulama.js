/* GÖKTUNGU MERKEZ — yönetim paneli uygulaması
 *
 * Tek sayfalık arayüz. Kimlik doğrulama HttpOnly kurabiyesi ile taşınır;
 * jeton JavaScript'te tutulmaz. Yönlendirme adres çıpasıyla (#) yapılır.
 */
'use strict';

const D = document;
const el = (s, k) => (k || D).querySelector(s);
const els = (s, k) => Array.from((k || D).querySelectorAll(s));

let BEN = null;              // oturum açan yönetici
const DURUM = {};            // sayfa başına geçici durum

/* ---------------------------------------------------------------- yardımcı */
function kacir(m) {
  return String(m ?? '').replace(/[&<>"']/g, (k) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[k]);
}

function bildir(mesaj, tur) {
  const d = D.createElement('div');
  d.className = 'bildirim ' + (tur || '');
  d.textContent = mesaj;
  el('#bildirimler').appendChild(d);
  setTimeout(() => d.remove(), 5000);
}

async function cagir(yol, secenek) {
  const s = Object.assign({ credentials: 'same-origin', headers: {} }, secenek || {});
  if (s.body && typeof s.body !== 'string') {
    s.headers['Content-Type'] = 'application/json';
    s.body = JSON.stringify(s.body);
  }
  const y = await fetch(yol, s);
  let veri = {};
  try { veri = await y.json(); } catch (e) { /* gövdesiz yanıt */ }
  if (y.status === 401 && BEN) { oturumBitti(); throw new Error('Oturum sona erdi'); }
  if (!y.ok) {
    // FAZ18-IS12-ACILIS-TESHIS: hata nesnesine HTTP durum kodu eklenir.
    // Metin BOZULMAZ (mevcut `e.message` kullanan tum catch bloklari
    // aynen calisir); yalnizca makine okunur bir alan eklenir ki
    // yetki hatasi ile teknik hata AYRISTIRILABILSIN.
    const h = new Error(veri.hata || ('HTTP ' + y.status));
    h.durum = y.status;
    throw h;
  }
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

const DURUM_RENK = { etkin: 'yesil', askida: 'sari', kapali: 'gri', pasif: 'gri' };
const GOREV_RENK = {
  tamamlandi: 'yesil', iptal: 'kirmizi', devam: 'mavi', hazir: 'gri',
  duraklatildi: 'sari'
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

el('#pencere-kapat').onclick = pencereKapat;
el('#perde').onclick = (o) => { if (o.target === el('#perde')) pencereKapat(); };
D.addEventListener('keydown', (o) => {
  if (o.key === 'Escape' && !el('#perde').classList.contains('gizli')) pencereKapat();
});

/* ---------------------------------------------------------------- oturum */
// HTML'de onsubmit="return false" var; bu nedenle dinleyici olarak
// baglanir (onsubmit atamasi HTML nitelini ezerdi ama betik yuklenene
// kadarki bosluk korumasiz kalirdi).
el('#giris-form').addEventListener('submit', async (o) => {
  o.preventDefault();
  el('#giris-hata').textContent = '';
  const dugme = el('#giris-form button');
  dugme.disabled = true;
  try {
    const y = await cagir('/api/admin/giris', {
      method: 'POST',
      body: { eposta: el('#g-eposta').value.trim(), sifre: el('#g-sifre').value }
    });
    BEN = y.yonetici;
    kabukAc();
  } catch (e) {
    el('#giris-hata').textContent = e.message;
  } finally {
    dugme.disabled = false;
  }
});

el('#cikis-dugme').onclick = async () => {
  try { await cagir('/api/admin/cikis', { method: 'POST', body: {} }); } catch (e) {}
  oturumBitti();
};

function oturumBitti() {
  BEN = null;
  el('#kabuk').classList.remove('acik');
  el('#giris-katman').style.display = 'flex';
  el('#g-sifre').value = '';
}

function kabukAc() {
  el('#giris-katman').style.display = 'none';
  el('#kabuk').classList.add('acik');
  el('#kim-bilgi').textContent =
    `${BEN.ad_soyad || BEN.eposta} · ${BEN.rol === 'sistem_yonetici' ? 'Sistem Yöneticisi' : 'Gözlemci'}`;
  yonlendir();
}

/* ---------------------------------------------------------------- yönlendirme */
const SAYFALAR = {
  gosterge: sayfaGosterge,
  firmalar: sayfaFirmalar,
  kullanicilar: sayfaKullanicilar,
  ucuslar: sayfaUcuslar,
  videolar: sayfaVideolar,
  sunucular: sayfaSunucular,
  surumler: sayfaSurumler,
  denetim: sayfaDenetim,
  guvenlik: sayfaGuvenlik,  // FAZ18-IS9-GUVENLIK-IZLEME
  gunluk: sayfaGunluk,  // FAZ18-IS10-GUNLUK-PANEL
  abonelikler: sayfaAbonelikler,
  destek: sayfaDestek,
  personel: sayfaPersonel
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
  const g = await cagir('/api/admin/gosterge');
  const k = (etiket, deger, ek, vurgu) => `
    <div class="kart${vurgu ? ' vurgulu' : ''}">
      <div class="etiket">${etiket}</div>
      <div class="deger">${deger}</div>
      ${ek ? `<div class="ek">${ek}</div>` : ''}
    </div>`;

  el('#icerik').innerHTML = `
    <h2>Gösterge Paneli</h2>
    <p class="aciklama">Merkez sisteme kayıtlı müşteriler, kullanıcılar ve uçuş verisinin özeti.</p>
    <div class="kart-izgara">
      ${k('Müşteri', sayi(g.firma), `${sayi(g.firma_etkin)} etkin`)}
      ${k('Kullanıcı', sayi(g.kullanici), `${sayi(g.kullanici_etkin)} etkin`)}
      ${k('Dron', sayi(g.dron))}
      ${k('Uçuş Kaydı', sayi(g.ucus), `son 7 gün: ${sayi(g.ucus_7gun)}`)}
      ${k('Toplam Uçuş Süresi', sure(g.toplam_sure_sn))}
      ${k('Video Kaydı', sayi(g.video), bayt(g.video_bayt))}
      ${k('Çevrimiçi Sunucu', `${sayi(g.sunucu_cevrimici)} / ${sayi(g.sunucu)}`,
         'ters WebSocket', Number(g.sunucu_cevrimici) > 0)}
      ${k('Telemetri Örneği', sayi(g.telemetri))}
    </div>

    <div class="pano">
      <h3>Son 14 günün uçuş dağılımı</h3>
      <div id="cizim-kap"></div>
    </div>

    <div class="pano">
      <h3>Uçuşa göre ilk 10 müşteri</h3>
      <table>
        <thead><tr><th>Müşteri</th><th class="sag">Uçuş</th><th class="sag">Süre</th></tr></thead>
        <tbody>
          ${(g.firma_ucus || []).map((f) => `<tr>
            <td>${kacir(f.kisa_ad)}</td>
            <td class="sag">${sayi(f.adet)}</td>
            <td class="sag">${sure(f.sure)}</td></tr>`).join('') ||
            '<tr><td colspan="3" class="bos">Henüz uçuş kaydı yok</td></tr>'}
        </tbody>
      </table>
    </div>`;
  cizimCiz('#cizim-kap', g.gunluk_ucus || []);
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
  // FAZ18-IS14-CIZIM-OLCEK: cubuk genisligi UST SINIRA baglanir.
  // ONCEKI KUSUR: `gen = alan / veri.length` idi; tek gunluk veride
  // gen=716 px olup cubuk 501 px genisliginde dev bir bloga donuyordu.
  // Cubuklar SOLA yaslanir (ortalamak tek cubugu ortada yuzdururdu ve
  // zaman ekseninin soldan basladigi izlenimini bozardi).
  const gen = Math.min((G - bosluk.s - bosluk.sa) / veri.length, 48);
  const cubuklar = veri.map((v, i) => {
    const h = (Number(v.adet) / enb) * (Y - bosluk.u - bosluk.a);
    const x = bosluk.s + i * gen + gen * 0.15;
    const y = Y - bosluk.a - h;
    const g = gen * 0.7;
    const etiket = tarih(v.gun, false).slice(0, 5);
    // Renkler CSS DEGISKENINDEN gelir (sabit renk sozlesme ihlalidir ve
    // acik temada okunamaz hale gelirdi). SVG'de `fill="var(--x)"`
    // OZNITELIK olarak calismadigi icin `style` kullanilir.
    return `<g>
      <rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${g.toFixed(1)}"
            height="${Math.max(h, 1).toFixed(1)}"
            style="fill:var(--vurgu)" rx="2">
        <title>${etiket}: ${v.adet} uçuş</title></rect>
      <text x="${(x + g / 2).toFixed(1)}" y="${Y - 8}"
            style="fill:var(--yazi2)"
            font-size="9" text-anchor="middle">${etiket}</text>
    </g>`;
  }).join('');
  const yatay = [0, 0.5, 1].map((o) => {
    const y = Y - bosluk.a - o * (Y - bosluk.u - bosluk.a);
    return `<line x1="${bosluk.s}" y1="${y}" x2="${G - bosluk.sa}" y2="${y}"
                  style="stroke:var(--cerceve)" stroke-width="1"/>
            <text x="4" y="${y + 3}" style="fill:var(--yazi2)"
                  font-size="9">${Math.round(o * enb)}</text>`;
  }).join('');
  // `xMidYMid meet` oran KORUR: dar kapta cubuklar ve etiket yazilari
  // artik yatay ezilmez (onceki `none` degeri deformasyon uretiyordu).
  kap.innerHTML = `<svg class="cizim" viewBox="0 0 ${G} ${Y}"
      preserveAspectRatio="xMidYMid meet">${yatay}${cubuklar}</svg>`;
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

/* ================================================================ MÜŞTERİLER */
async function sayfaFirmalar(par) {
  DURUM.firma = Object.assign({ sayfa: 1, boyut: 50, arama: '', durum: '' },
    DURUM.firma, par);
  await firmaTabloYenile();
}

async function firmaTabloYenile() {
  const s = DURUM.firma;
  const sorgu = new URLSearchParams({
    sayfa: s.sayfa, boyut: s.boyut, arama: s.arama || '', durum: s.durum || ''
  });
  const y = await cagir('/api/admin/firmalar?' + sorgu);
  el('#icerik').innerHTML = `
    <h2>Müşteriler</h2>
    <p class="aciklama">Sisteme kayıtlı firmalar, kullanıcı ve uçuş sayıları.</p>
    <div class="arac-cubugu">
      <input id="f-arama" placeholder="Unvan, kısa ad veya vergi no" value="${kacir(s.arama)}">
      <select id="f-durum">
        <option value="">Tüm durumlar</option>
        <option value="etkin"${s.durum === 'etkin' ? ' selected' : ''}>Etkin</option>
        <option value="askida"${s.durum === 'askida' ? ' selected' : ''}>Askıda</option>
        <option value="kapali"${s.durum === 'kapali' ? ' selected' : ''}>Kapalı</option>
      </select>
      <button class="ikincil kucuk" id="f-ara">Ara</button>
      <div class="bosluk"></div>
      ${BEN.rol === 'sistem_yonetici' ?
        '<button class="kucuk" id="f-yeni">+ Yeni Müşteri</button>' : ''}
    </div>
    <div class="pano" style="margin-top:0">
      <table>
        <thead><tr>
          <th>Unvan</th><th>Kısa Ad</th><th>Abonelik</th><th>Durum</th>
          <th class="sag">Pilot</th><th class="sag">Kullanıcı</th><th class="sag">Sunucu</th>
          <th class="sag">Uçuş</th><th class="sag">Video</th><th>Son Uçuş</th><th></th>
        </tr></thead>
        <tbody>${y.kayitlar.map(firmaSatir).join('') ||
          '<tr><td colspan="11" class="bos">Kayıt bulunamadı</td></tr>'}</tbody>
      </table>
      ${sayfalamaHTML(y.toplam, y.sayfa, y.boyut, 'firmaSayfa')}
    </div>`;
  el('#f-ara').onclick = () => {
    DURUM.firma.arama = el('#f-arama').value.trim();
    DURUM.firma.durum = el('#f-durum').value;
    DURUM.firma.sayfa = 1;
    firmaTabloYenile();
  };
  el('#f-arama').onkeydown = (o) => { if (o.key === 'Enter') el('#f-ara').click(); };
  if (el('#f-yeni')) el('#f-yeni').onclick = () => firmaPencere(null);
}

function firmaSatir(f) {
  return `<tr>
    <td>${kacir(f.unvan)}</td>
    <td><code class="kod">${kacir(f.kisa_ad)}</code></td>
    <td>${rozet(f.abonelik || 'deneme', f.abonelik === 'kurumsal' ? 'mor' : 'mavi')}</td>
    <td>${rozet(f.durum, DURUM_RENK[f.durum] || 'gri')}</td>
    <td class="sag">${f.sinirsiz ? '∞' :
      sayi(f.pilot_sayisi) + ' / ' + sayi(f.pilot_koltuk)}</td>
    <td class="sag">${sayi(f.kullanici_sayisi)} / ${sayi(f.maks_kullanici)}</td>
    <td class="sag">${sayi(f.cevrimici_sunucu)} / ${sayi(f.sunucu_sayisi)}</td>
    <td class="sag">${sayi(f.ucus_sayisi)}</td>
    <td class="sag">${sayi(f.video_sayisi)}</td>
    <td class="tek-satir">${tarih(f.son_ucus_ts)}</td>
    <td class="sag tek-satir">
      <button class="ikincil kucuk" onclick="firmaDetay(${f.firma_id})">Detay</button>
    </td></tr>`;
}

window.firmaSayfa = (n) => { DURUM.firma.sayfa = n; firmaTabloYenile(); };

window.firmaDetay = async (fid) => {
  const f = await cagir('/api/admin/firmalar/' + fid);
  const o = f.ozet || {};
  pencereAc(f.unvan, `
    <dl class="ozet">
      <dt>Kısa ad</dt><dd><code class="kod">${kacir(f.kisa_ad)}</code></dd>
      <dt>Vergi no</dt><dd>${kacir(f.vergi_no || '—')}</dd>
      <dt>Adres</dt><dd>${kacir(f.adres || '—')}</dd>
      <dt>Telefon</dt><dd>${kacir(f.telefon || '—')}</dd>
      <dt>E-posta</dt><dd>${kacir(f.eposta || '—')}</dd>
      <dt>Abonelik</dt><dd>${rozet(f.abonelik || 'deneme', 'mavi')}
        ${f.abonelik_bitis ? ' · bitiş ' + tarih(f.abonelik_bitis, false) : ''}</dd>
      <dt>Durum</dt><dd>${rozet(f.durum, DURUM_RENK[f.durum] || 'gri')}</dd>
      <dt>Sınırlar</dt><dd>${f.sinirsiz ? '<b>sınırsız</b>' :
        sayi(f.pilot_koltuk) + ' pilot koltuğu'} ·
        ${sayi(f.maks_kullanici)} hesap ·
        ${sayi(f.maks_sunucu)} sunucu</dd>
      <dt>Kayıt</dt><dd>${tarih(f.olusma_ts)}</dd>
    </dl>
    <div class="kart-izgara" style="margin-top:16px">
      <div class="kart"><div class="etiket">Kullanıcı</div>
        <div class="deger">${sayi(o.kullanici_sayisi)}</div></div>
      <div class="kart"><div class="etiket">Uçuş</div>
        <div class="deger">${sayi(o.ucus_sayisi)}</div>
        <div class="ek">${sure(o.toplam_sure_sn)}</div></div>
      <div class="kart"><div class="etiket">Video</div>
        <div class="deger">${sayi(o.video_sayisi)}</div>
        <div class="ek">${bayt(o.video_bayt)}</div></div>
      <div class="kart"><div class="etiket">Dron</div>
        <div class="deger">${sayi(o.dron_sayisi)}</div></div>
    </div>
    <div class="pano" style="margin-top:16px">
      <h3>Sunucular (${(f.sunucular || []).length})</h3>
      <table><thead><tr><th>Ad</th><th>Durum</th><th>Sürüm</th><th>Son Görülme</th></tr></thead>
      <tbody>${(f.sunucular || []).map((s) => `<tr>
        <td>${kacir(s.ad)}</td>
        <td><span class="nokta ${s.cevrimici ? 'acik' : 'kapali'}"></span>
            ${s.cevrimici ? 'Çevrimiçi' : 'Çevrimdışı'}</td>
        <td>${kacir(s.surum || '—')}</td>
        <td class="tek-satir">${tarih(s.son_gorulme_ts)}</td></tr>`).join('') ||
        '<tr><td colspan="4" class="bos">Kayıtlı sunucu yok</td></tr>'}</tbody></table>
    </div>`,
    [
      { metin: 'Abonelik', sinif: 'ikincil',
        tik: () => { pencereKapat(); firmaAbonelik(fid); } },
      { metin: 'Kullanıcıları', sinif: 'ikincil',
        tik: () => { pencereKapat(); location.hash = `#kullanicilar?firma_id=${fid}`; } },
      { metin: 'Uçuşları', sinif: 'ikincil',
        tik: () => { pencereKapat(); location.hash = `#ucuslar?firma_id=${fid}`; } },
      ...(BEN.rol === 'sistem_yonetici' ? [
        { metin: 'Düzenle', sinif: 'ikincil', tik: () => firmaPencere(f) },
        { metin: 'Sil', sinif: 'tehlike', tik: () => firmaSil(fid, f.unvan) }
      ] : []),
      { metin: 'Kapat', sinif: 'ikincil', tik: pencereKapat }
    ], true);
};

function firmaPencere(f) {
  const d = f || {};
  pencereAc(f ? 'Müşteriyi Düzenle' : 'Yeni Müşteri', `
    <label>Unvan *</label><input id="m-unvan" value="${kacir(d.unvan || '')}">
    <div class="ikili">
      <div><label>Kısa ad</label><input id="m-kisa" value="${kacir(d.kisa_ad || '')}"></div>
      <div><label>Vergi no</label><input id="m-vergi" value="${kacir(d.vergi_no || '')}"></div>
    </div>
    <label>Adres</label><input id="m-adres" value="${kacir(d.adres || '')}">
    <div class="ikili">
      <div><label>Telefon</label><input id="m-tel" value="${kacir(d.telefon || '')}"></div>
      <div><label>E-posta</label><input id="m-eposta" value="${kacir(d.eposta || '')}"></div>
    </div>
    <div class="ucul">
      <div><label>Abonelik</label>
        <select id="m-abonelik">
          ${['deneme', 'standart', 'kurumsal'].map((a) =>
            `<option value="${a}"${d.abonelik === a ? ' selected' : ''}>${a}</option>`).join('')}
        </select></div>
      <div><label>Maks. kullanıcı</label>
        <input id="m-maksk" type="number" min="1" value="${d.maks_kullanici || 10}"></div>
      <div><label>Maks. sunucu</label>
        <input id="m-makss" type="number" min="1" value="${d.maks_sunucu || 3}"></div>
    </div>
    ${f ? `<label>Durum</label><select id="m-durum">
      ${['etkin', 'askida', 'kapali'].map((a) =>
        `<option value="${a}"${d.durum === a ? ' selected' : ''}>${a}</option>`).join('')}
    </select>` : ''}
    <div class="hata" id="m-hata"></div>`,
    [
      { metin: 'Vazgeç', sinif: 'ikincil', tik: pencereKapat },
      { metin: f ? 'Kaydet' : 'Oluştur', tik: () => firmaKaydet(f && f.firma_id) }
    ]);
}

async function firmaKaydet(fid) {
  const govde = {
    unvan: el('#m-unvan').value.trim(),
    kisa_ad: el('#m-kisa').value.trim(),
    vergi_no: el('#m-vergi').value.trim(),
    adres: el('#m-adres').value.trim(),
    telefon: el('#m-tel').value.trim(),
    eposta: el('#m-eposta').value.trim(),
    abonelik: el('#m-abonelik').value,
    maks_kullanici: Number(el('#m-maksk').value),
    maks_sunucu: Number(el('#m-makss').value)
  };
  if (el('#m-durum')) govde.durum = el('#m-durum').value;
  try {
    if (fid) await cagir('/api/admin/firmalar/' + fid, { method: 'PUT', body: govde });
    else await cagir('/api/admin/firmalar', { method: 'POST', body: govde });
    pencereKapat();
    bildir(fid ? 'Müşteri güncellendi' : 'Müşteri oluşturuldu', 'iyi');
    firmaTabloYenile();
  } catch (e) {
    el('#m-hata').textContent = e.message;
  }
}

function firmaSil(fid, unvan) {
  pencereAc('Müşteriyi Sil', `
    <div class="uyari-kutu">
      <strong>${kacir(unvan)}</strong> silinecek. Bu firmaya ait tüm kullanıcılar,
      dronlar, uçuş kayıtları, telemetri ve video kayıtları da kalıcı olarak silinir.
      Bu işlem geri alınamaz.
    </div>
    <label style="margin-top:14px">Onaylamak için firmanın kısa adını yazın</label>
    <input id="s-onay" placeholder="kısa ad">
    <div class="hata" id="s-hata"></div>`,
    [
      { metin: 'Vazgeç', sinif: 'ikincil', tik: pencereKapat },
      { metin: 'Kalıcı olarak sil', sinif: 'tehlike', tik: async () => {
        try {
          await cagir('/api/admin/firmalar/' + fid, { method: 'DELETE' });
          pencereKapat();
          bildir('Müşteri silindi', 'iyi');
          firmaTabloYenile();
        } catch (e) { el('#s-hata').textContent = e.message; }
      } }
    ]);
}

/* ================================================================ ABONELIKLER
 * Ust yonetici: sirket bazli koltuk, ozellik ve lisans yonetimi.
 *
 * Model notu: ucretlendirilen birim PILOT koltugudur. Yonetici ve gozlemci
 * koltuk tuketmez; boylece ucretsiz taban ("1 pilot + 1 yonetici") tutarli
 * kalir. `sinirsiz` bayragi (Merkez Uygulama lisansi) tum koltuk ve ozellik
 * sinirlarini kaldirir.
 */
const KALEM_ETIKET = {
  pilot_1: '1 Pilot Koltugu', pilot_5: '5 Pilotluk Paket',
  pilot_10: '10 Pilotluk Paket', ai: 'AI Sistemi',
  merkez: 'Merkez Uygulama (tek seferlik)',
  radar: 'Radar Modulu', gccdual: 'GCCDUAL Modulu'
};

const YETKI_ETIKET = {
  ai: 'AI Sistemi', radar: 'Radar Modulu', gccdual: 'GCCDUAL Modulu',
  sinirsiz: 'Sinirsiz Kullanim', merkez_lisans: 'Merkez Uygulama Lisansi'
};

async function sayfaAbonelikler(par) {
  DURUM.abn = Object.assign({ durum: 'bekliyor' }, DURUM.abn, par);
  await abonelikYenile();
}

/* =====================================================================
   MUSTERI ISKONTOLARI
   ---------------------------------------------------------------------
   Sirket bazli indirim yonetimi. Iki bicim:

     yuzde -> paket fiyatinin yuzdesi   (para biriminden BAGIMSIZ)
     sabit -> mutlak tutar indirimi     (para birimi ZORUNLU)

   Sabit iskontoda para birimi zorunludur cunku "200 indirim" ifadesi
   tek basina anlamsizdir: 200 TL ile 200 USD arasinda ~34 kat fark var.
   Para birimi verilmezse iskonto yanlis para biriminde uygulanabilir ve
   urun bedelsize yakin satilir.

   Iskontolar KUMULATIF DEGILDIR. Bir paket icin birden fazla gecerli
   iskonto varsa musteriye EN YUKSEK olan uygulanir. Carpim uygulanirsa
   iki ayri kampanya ust uste binip beklenmeyen fiyat uretir.

   Sunucu tarafi (mk_paket.net_fiyat) ayni kurallari YENIDEN dogrular;
   buradaki denetim yalnizca kullaniciya hizli geri bildirim icindir.
   ===================================================================== */
function iskontoPanosu(isk, frm, fl) {
  const bugun = new Date().toISOString().slice(0, 10);
  const etkinMi = (i) => {
    /* Sunucu alan adlari: gecerli_bas / gecerli_bit (OLCULDU). */
    if (i.durum === 'iptal') return 'iptal';
    if (i.gecerli_bas && i.gecerli_bas > bugun) return 'bekliyor';
    if (i.gecerli_bit && i.gecerli_bit < bugun) return 'süresi doldu';
    return 'etkin';
  };
  const renk = { 'etkin': 'yesil', 'bekliyor': 'sari',
                 'süresi doldu': 'gri', 'iptal': 'kirmizi' };
  const firmaAd = (fid) => {
    /* OLCULDU: uc `firma_id` dondurur, `id` DEGIL. Alan adlari:
       firma_id, unvan, kisa_ad, vergi_no, abonelik, pilot_koltuk...
       `id` diye bir alan YOKTUR. */
    const f = (frm || []).find(
      (x) => String(x.firma_id) === String(fid));
    return f ? (f.unvan || f.kisa_ad || ('#' + fid)) : ('#' + fid);
  };
  const paketAd = (a) => {
    if (!a) return '<i>tüm paketler</i>';
    const p = (fl || []).find((x) => x.paket === a);
    return kacir(p ? (p.ad_tr || p.ad || a) : a);
  };
  return `
    <div class="pano" style="margin-top:16px">
      <h3>Müşteri İskontoları (${sayi((isk || []).length)})</h3>
      <p class="aciklama">Şirket bazlı indirim tanımları. İskontolar
        <b>kümülatif değildir</b>; bir paket için birden fazla geçerli
        iskonto varsa <b>en yükseği</b> uygulanır. Yıllık ödeme indirimi
        (%20) ayrıca ve <b>önce</b> uygulanır.</p>
      ${BEN.rol === 'sistem_yonetici' ? `<div class="arac-cubugu">
        <button class="birincil kucuk" id="a-iskekle">İskonto Tanımla</button>
      </div>` : `<div class="uyari-kutu">İskonto tanımlamak için sistem
        yöneticisi yetkisi gerekir.</div>`}
      ${(isk || []).length === 0 ? `<p class="aciklama"
        style="margin-top:10px"><i>Tanımlı iskonto yok.</i></p>` : `
      <table style="margin-top:10px">
        <thead><tr><th>Şirket</th><th>Paket</th><th class="sag">İndirim</th>
          <th>Geçerlilik</th><th>Gerekçe</th><th>Durum</th>
          ${BEN.rol === 'sistem_yonetici' ? '<th></th>' : ''}</tr></thead>
        <tbody>${isk.map((i) => {
          const d = etkinMi(i);
          return `<tr>
          <td>${kacir(firmaAd(i.firma_id))}</td>
          <td>${paketAd(i.paket_anahtar)}</td>
          <td class="sag"><b>${i.tur === 'yuzde'
            ? '%' + sayi(i.deger)
            : (i.para_birimi === 'USD' ? '$' : '₺') + sayi(i.deger)}</b></td>
          <td>${tarih(i.gecerli_bas, false)} → ${i.gecerli_bit
            ? tarih(i.gecerli_bit, false) : '<i>süresiz</i>'}</td>
          <td>${kacir(i.gerekce || '—')}</td>
          <td>${rozet(d, renk[d])}</td>
          ${BEN.rol === 'sistem_yonetici' && i.durum !== 'iptal'
            ? `<td><button class="tehlike kucuk"
                 data-isk-sil="${i.iskonto_id}">Kaldır</button></td>`
            : BEN.rol === 'sistem_yonetici' ? '<td></td>'
            : ''}
          </tr>`; }).join('')}
        </tbody>
      </table>`}
    </div>`;
}

function iskontoEkleAc(frm, fl) {
  const bugun = new Date().toISOString().slice(0, 10);
  /* Yalniz VITRIN paketleri secilebilir; gizli miras planlara yeni
     iskonto tanimlamak anlamsizdir (o planlar satista degil). */
  const secilebilir = (fl || []);
  pencereAc('İskonto Tanımla', `
    <label>Şirket
      <select id="i-firma">
        ${(frm || []).map((f) => `<option value="${f.firma_id}">${
          kacir(f.unvan || f.kisa_ad
                || ('#' + f.firma_id))}</option>`).join('')}
      </select></label>
    <label>Paket
      <select id="i-paket">
        <option value="">— tüm paketler —</option>
        ${secilebilir.map((p) => `<option value="${kacir(p.paket)}">${
          kacir(p.ad_tr || p.ad || p.paket)}</option>`).join('')}
      </select></label>
    <label>İskonto biçimi
      <select id="i-tur">
        <option value="yuzde">Yüzde (%)</option>
        <option value="tutar">Sabit tutar</option>
      </select></label>
    <label>Değer <input id="i-deger" type="number" step="0.01" min="0"
      placeholder="örn. 15"></label>
    <label id="i-para-sar" style="display:none">Para birimi
      <select id="i-para">
        <option value="TRY">₺ Türk lirası</option>
        <option value="USD">$ ABD doları</option>
      </select>
      <span class="ipucu">Sabit tutar iskontosunda zorunludur.</span></label>
    <label>Başlangıç <input id="i-bas" type="date" value="${bugun}"></label>
    <label>Bitiş <input id="i-bit" type="date">
      <span class="ipucu">Boş bırakılırsa süresiz.</span></label>
    <label>Gerekçe <input id="i-ger" maxlength="200"
      placeholder="örn. çok yıllı sözleşme"></label>
    <div class="uyari-kutu" style="margin-top:10px">İskontolar kümülatif
      değildir. Aynı paket için birden fazla geçerli iskonto varsa
      <b>en yükseği</b> uygulanır.</div>`,
    [{ metin: 'Tanımla', sinif: 'birincil', tik: async () => {
        const tur = el('#i-tur').value;
        const deger = parseFloat(el('#i-deger').value);
        const para = el('#i-para').value;
        const bas = el('#i-bas').value;
        const bit = el('#i-bit').value;
        const ger = el('#i-ger').value.trim();
        if (!(deger > 0)) { bildir('Değer sıfırdan büyük olmalı', 'hata'); return; }
        if (tur === 'yuzde' && deger > 100) {
          bildir('Yüzde iskonto 100\u0027ü aşamaz', 'hata'); return; }
        if (!ger) { bildir('Gerekçe zorunlu (denetim izi)', 'hata'); return; }
        if (bit && bas && bit < bas) {
          bildir('Bitiş tarihi başlangıçtan önce olamaz', 'hata'); return; }
        try {
          /* Sunucu sozlesmesi (OLCULDU): uc `iskonto_tanimla`,
             alanlar `para_birimi` / `gecerli_bas` / `gecerli_bit`. */
          await cagir('/api/admin/iskonto_tanimla', { method: 'POST', body: {
            firma_id: parseInt(el('#i-firma').value, 10),
            paket: el('#i-paket').value || null,
            tur: tur,
            deger: deger,
            para_birimi: tur === 'tutar' ? para : null,
            gecerli_bas: bas || null,
            gecerli_bit: bit || null,
            gerekce: ger,
          }});
          pencereKapat();
          bildir('İskonto tanımlandı', 'basari');
          abonelikYenile();
        } catch (e) { bildir(e.message, 'hata'); }
      }},
     { metin: 'Vazgeç', sinif: 'ikincil', tik: pencereKapat }]);
  /* Sabit tutar secilince para birimi alani ZORUNLU hale gelir. */
  const turSec = el('#i-tur');
  const paraSar = el('#i-para-sar');
  if (turSec && paraSar) {
    turSec.addEventListener('change', () => {
      paraSar.style.display = turSec.value === 'tutar' ? '' : 'none';
    });
  }
}

async function iskontoKaldir(id) {
  if (!confirm('İskonto kaldırılsın mı? Bu işlem denetim izine yazılır.')) return;
  try {
    /* Sunucu POST bekler ve id'yi GOVDEDE alir (OLCULDU). Kayit
       SILINMEZ, `durum='iptal'` olur -- denetim izi korunur. */
    await cagir('/api/admin/iskonto_iptal',
                { method: 'POST', body: { iskonto_id: parseInt(id, 10) } });
    bildir('İskonto kaldırıldı', 'basari');
    abonelikYenile();
  } catch (e) { bildir(e.message, 'hata'); }
}

function iskontoOlaylari(frm, fl) {
  const b = el('#a-iskekle');
  if (b) b.onclick = () => iskontoEkleAc(frm, fl);
  document.querySelectorAll('[data-isk-sil]').forEach((x) => {
    x.onclick = () => iskontoKaldir(x.getAttribute('data-isk-sil'));
  });
}

async function abonelikYenile() {
  const s = DURUM.abn;
  let sd = {};
  /* Uc `{tamam, durum:{...}}` sarmalayicisi dondurur; alanlar `durum`
     icindedir. Dogrudan `sd.acik` okunursa DAIMA undefined olur ve
     pano her zaman 'kapali' gosterir. */
  try { sd = (await cagir('/api/admin/iyzico_durum')).durum || {}; }
  catch (e) { sd = { hata: e.message }; }
  /* Iskonto listesi ayri uctan gelir; odeme kapaliyken de yonetilir. */
  let isk = [];
  try { isk = (await cagir('/api/admin/iskontolar')).iskontolar || []; }
  catch (e) { isk = []; }
  let frm = [];
  /* TEK cagri: `||` sag tarafinda yeniden `await cagir(...)` yazmak
     ayni ucu IKI KEZ vurur. Yanit bir kez alinir, alan adi sonra
     secilir. */
  try { const fy = await cagir('/api/admin/firmalar');
        frm = fy.firmalar || fy.kayitlar || []; }
  catch (e) { frm = []; }
  const t = await cagir('/api/admin/talepler?durum=' + encodeURIComponent(s.durum || ''));
  const tl = t.kayitlar || t.talepler || [];
  /* Fiyat listesi ayrı uçtan gelir; ödeme kapalıyken de gösterilmeli. */
  let fl = [];
  try { fl = (await cagir('/api/genel/fiyatlar')).kalemler || []; } catch (e) { fl = []; }

  el('#icerik').innerHTML = `
    <h2>Abonelikler</h2>
    <p class="aciklama">Uyelik talepleri, odeme yapilandirmasi ve fiyat listesi.
      Sirket bazli koltuk ve ozellik yonetimi icin <b>Musteriler</b> sayfasindaki
      <b>Abonelik</b> dugmesini kullanin.</p>

    <div class="pano">
      <h3>Ödeme Yapılandırması (iyzico)</h3>
      ${sd.hata ? `<div class="uyari-kutu">Durum okunamadı: ${kacir(sd.hata)}</div>` : `
      <dl class="ozet">
        <dt>Durum</dt><dd>${sd.acik
          ? rozet(sd.test_modu ? 'test modu' : 'canlı', sd.test_modu ? 'sari' : 'yesil')
          : rozet('kapalı', 'gri')}</dd>
        <dt>API anahtarı</dt><dd>${sd.acik ? 'tanımlı' : '<b>tanımlı değil</b>'}</dd>
        <dt>Abonelik eklentisi</dt><dd>${sd.abonelik_acik
          ? rozet('etkin', 'yesil')
          : rozet('iyzico panelinden etkinleştirilmeli', 'sari')}</dd>
        <dt>Bildirim (webhook)</dt><dd>${sd.webhook_hazir ? 'tanımlı' : '<b>tanımlı değil</b>'}</dd>
        <dt>Webhook yolu</dt><dd><code class="kod">${kacir(sd.webhook_yolu || '—')}</code></dd>
        <dt>Tahsilat</dt><dd>${kacir(sd.tahsilat || '—')}${
          sd.vkn ? ' · VKN ' + kacir(sd.vkn) : ''}</dd>
        <dt>Para birimleri</dt><dd>${(sd.para_birimleri || ['TRY', 'USD']).join(' · ')}
          <span class="ipucu">yabancı para için yabancı kart gerekir</span></dd>
        <dt>Vitrin kalemi</dt><dd>${sayi((sd.kalemler || []).length)} paket</dd>
      </dl>
      ${!sd.acik ? `<div class="uyari-kutu" style="margin-top:12px">
        iyzico API anahtarı tanımlı değil; <b>online ödeme kapalı</b>.
        Bu durumda üyelikler yalnızca bu panelden elle tanımlanabilir.
        Anahtarlar sunucuda <code class="kod">/opt/goktungu/merkez/veri/
        iyzico.json</code> dosyasına ya da <code class="kod">IYZICO_API_KEY
        </code> / <code class="kod">IYZICO_SECRET_KEY</code> ortam
        değişkenlerine yazılır.</div>` : ''}
      ${!sd.webhook_hazir && sd.acik ? `<div class="uyari-kutu" style="margin-top:12px">
        Bildirim sırrı tanımlı değil. Ödeme alınsa bile <b>yetki otomatik
        açılmaz</b>; iyzico panelinden bildirim adresi tanımlayıp
        <code class="kod">iyzico.json</code> içindeki
        <code class="kod">bildirim_sirri</code> değerini girin.</div>` : ''}
      ${BEN.rol === 'sistem_yonetici' && sd.acik ? `
        <div class="arac-cubugu" style="margin-top:12px">
          <button class="ikincil kucuk" id="a-fiyatkur">iyzico Ürün ve Planlarını Oluştur / Eşitle</button>
        </div>` : ''}`}
    </div>

    <div class="pano" style="margin-top:16px">
      <h3>Fiyat Listesi</h3>
      <table>
        <thead><tr><th>Kalem</th><th>Kod</th>
          <th class="sag">Aylık ₺</th><th class="sag">Yıllık ₺</th>
          <th class="sag">Aylık $</th><th class="sag">Tek $</th>
          <th class="sag">Koltuk</th><th>Durum</th></tr></thead>
        <tbody>${(fl || []).map((f) => `<tr>
          <td>${kacir(f.ad_tr || f.ad || f.paket)}</td>
          <td><code class="kod">${kacir(f.paket)}</code></td>
          <td class="sag">${f.aylik_try == null ? '—' : '₺' + sayi(f.aylik_try)}</td>
          <td class="sag">${f.yillik_try == null ? '—' : '₺' + sayi(f.yillik_try)}</td>
          <td class="sag">${f.aylik_usd == null ? '—' : '$' + sayi(f.aylik_usd)}</td>
          <td class="sag">${f.tek_usd == null ? '—' : '<b>$' + sayi(f.tek_usd) + '</b>'}</td>
          <td class="sag">${f.koltuk_sinirsiz ? '∞'
            : (f.koltuk ? sayi(f.koltuk) : '—')}${
            f.koltuk_basina ? ' <span class="ipucu">/pilot</span>' : ''}</td>
          <td>${f.satilabilir ? rozet('kartla satılır', 'yesil')
            : rozet('talep üzerine', 'mor')}</td>
          </tr>`).join('')}
          ${['radar', 'gccdual'].map((k) => `<tr>
            <td>${kacir(YETKI_ETIKET[k])}</td><td class="sag">—</td>
            <td class="sag">—</td><td class="sag">—</td>
            <td>${rozet('yalnız üst yönetici açar', 'mor')}</td></tr>`).join('')}
        </tbody>
      </table>
      <p class="aciklama" style="margin-top:10px">Şirket içi (on-premise)
        lisanslar <b>GTU-MERKEZ</b>, <b>GTU-MERKEZ-YZ</b>, <b>GTU-RADAR</b>
        ve <b>GTU-TAM</b> basamaklarından oluşur; tek seferlik bedel ile
        <b>süresiz kullanım hakkı</b> verir. İlk yıl bakım dahildir,
        sonraki yıllarda lisans bedelinin <b>%18</b>'i bakım ücreti olarak
        işletilir. <b>Bakım süresi bittiğinde sistem çalışmaya devam eder</b>;
        yalnız yeni sürüm ve destek hakkı düşer. Radar ve GCCDUAL abonelik
        katmanında satılmaz; SKU içinde ya da üst yönetici tanımıyla açılır.</p>
    </div>

    ${iskontoPanosu(isk, frm, fl)}
    <div class="pano" style="margin-top:16px">
      <h3>Uyelik Talepleri</h3>
      <div class="arac-cubugu">
        <select id="a-durum">
          ${['bekliyor', 'onaylandi', 'reddedildi', ''].map((d) =>
            `<option value="${d}"${s.durum === d ? ' selected' : ''}>${
              d === '' ? 'Tum talepler' : d}</option>`).join('')}
        </select>
      </div>
      <table>
        <thead><tr><th>Firma</th><th>Kalem</th><th class="sag">Adet</th>
          <th>Donem</th><th>Durum</th><th>Tarih</th><th></th></tr></thead>
        <tbody>${tl.map((t2) => `<tr>
          <td>${kacir(t2.firma_unvan || t2.firma_kisa_ad || '—')}</td>
          <td>${kacir(KALEM_ETIKET[t2.kalem] || t2.kalem)}</td>
          <td class="sag">${sayi(t2.adet)}</td>
          <td>${kacir(t2.donem || '—')}</td>
          <td>${rozet(t2.durum, t2.durum === 'onaylandi' ? 'yesil' :
            (t2.durum === 'reddedildi' ? 'kirmizi' : 'sari'))}</td>
          <td class="tek-satir">${tarih(t2.olusma_ts)}</td>
          <td class="sag tek-satir">${BEN.rol === 'sistem_yonetici' && t2.durum === 'bekliyor' ?
            `<button class="kucuk" onclick="talepKarar(${t2.talep_id}, true)">Onayla</button>
             <button class="tehlike kucuk" onclick="talepKarar(${t2.talep_id}, false)">Reddet</button>` :
            (t2.karar_notu ? kacir(t2.karar_notu) : '—')}</td>
          </tr>`).join('') || '<tr><td colspan="7" class="bos">Talep yok</td></tr>'}
        </tbody>
      </table>
    </div>`;

  /* Iskonto dugmeleri: pano her yenilemede YENIDEN uretildigi icin
     olay baglari da her seferinde kurulmalidir. Bir kez baglamak
     yetmez -- innerHTML atamasi eski ogeleri yok eder. */
  iskontoOlaylari(frm, fl);
  el('#a-durum').onchange = () => {
    DURUM.abn.durum = el('#a-durum').value;
    abonelikYenile();
  };
  if (el('#a-fiyatkur')) el('#a-fiyatkur').onclick = async () => {
    try {
      const y = await cagir('/api/admin/iyzico_plan_kur', { method: 'POST' });
      const isl = y.islem || [];
      bildir(isl.length ? `${sayi(isl.length)} işlem yapıldı`
        : 'Fiyat kayıtları zaten güncel', 'iyi');
      if (isl.length) {
        pencereAc('Fiyat Eşitleme Sonucu',
          '<ul class="liste">' + isl.map((s) => `<li>${kacir(s)}</li>`).join('') + '</ul>',
          [{ metin: 'Kapat', sinif: 'ikincil', tik: () => { pencereKapat(); abonelikYenile(); } }]);
      } else { abonelikYenile(); }
    } catch (e) { bildir(e.message, 'kotu'); }
  };
}

window.talepKarar = (tid, onay) => {
  pencereAc(onay ? 'Talebi Onayla' : 'Talebi Reddet', `
    <p>${onay ? 'Talep onaylanacak ve yetki hemen acilacak.' :
      'Talep reddedilecek; hicbir yetki acilmaz.'}</p>
    <label>Karar notu (istege bagli)</label>
    <input id="k-not" placeholder="on talep degerlendirmesi sonucu">
    <div class="hata" id="k-hata"></div>`,
    [
      { metin: 'Vazgec', sinif: 'ikincil', tik: pencereKapat },
      { metin: onay ? 'Onayla' : 'Reddet', sinif: onay ? '' : 'tehlike',
        tik: async () => {
          try {
            await cagir('/api/admin/talep/' + tid + '/karar',
              { method: 'POST', body: { onay, notu: el('#k-not').value.trim() } });
            pencereKapat();
            bildir(onay ? 'Talep onaylandi' : 'Talep reddedildi', 'iyi');
            abonelikYenile();
          } catch (e) { el('#k-hata').textContent = e.message; }
        } }
    ]);
};

/* Sirket bazli abonelik penceresi -- Musteriler sayfasindan acilir */
window.firmaAbonelik = async (fid) => {
  let d;
  try { d = await cagir('/api/admin/firma/' + fid + '/abonelik'); }
  catch (e) { bildir(e.message, 'kotu'); return; }
  const y = d.yetkiler || {};
  const yaz = BEN.rol === 'sistem_yonetici';

  const anahtar = (alan) => {
    const acik = !!y[alan];
    return `<tr>
      <td>${kacir(YETKI_ETIKET[alan] || alan)}</td>
      <td>${acik ? rozet('acik', 'yesil') : rozet('kapali', 'gri')}</td>
      <td class="sag">${yaz ?
        `<button class="${acik ? 'tehlike' : ''} kucuk"
           onclick="yetkiDegistir(${fid}, '${alan}', ${!acik})">${
           acik ? 'Kapat' : 'Ac'}</button>` : '—'}</td></tr>`;
  };

  pencereAc('Abonelik — ' + (y.unvan || y.kisa_ad || '#' + fid), `
    <div class="kart-izgara">
      <div class="kart"><div class="etiket">Pilot Koltugu</div>
        <div class="deger">${y.sinirsiz ? '∞' :
          sayi(y.pilot_kullanilan) + ' / ' + sayi(y.pilot_koltuk)}</div>
        <div class="ek">${y.sinirsiz ? 'sinirsiz lisans' :
          (y.pilot_bos != null ? sayi(y.pilot_bos) + ' bos' : '')}</div></div>
      <div class="kart"><div class="etiket">Abonelik</div>
        <div class="deger" style="font-size:20px">${kacir(y.abonelik || 'deneme')}</div>
        <div class="ek">${y.fatura_donemi ? kacir(y.fatura_donemi) : '—'}${
          y.abonelik_bitis ? ' · ' + tarih(y.abonelik_bitis, false) : ''}</div></div>
      <div class="kart"><div class="etiket">Toplam Hesap</div>
        <div class="deger">${sayi(y.hesap_kullanilan)} / ${sayi(y.maks_kullanici)}</div>
        <div class="ek">tum roller</div></div>
      <div class="kart"><div class="etiket">Merkez Lisansi</div>
        <div class="deger" style="font-size:20px">${y.merkez_lisans ? 'VAR' : 'yok'}</div>
        <div class="ek">${y.merkez_lisans_ts ? tarih(y.merkez_lisans_ts, false) : '—'}</div></div>
    </div>

    ${y.sinirsiz ? `<div class="uyari-kutu" style="margin-top:14px">
      Bu sirket <b>sinirsiz kullanim</b> hakkina sahiptir (Merkez Uygulama
      lisansi). Koltuk ve ozellik sinirlari uygulanmaz; kapali devre
      calisabilir.</div>` : ''}

    <div class="pano" style="margin-top:16px">
      <h3>Ozellik Anahtarlari</h3>
      <p class="aciklama">Radar ve GCCDUAL satilmaz; yalnizca ust yonetici acar.
        Kopru yazilimi giris yaptiginda bu yetkilere gore menu gosterir.</p>
      <table><thead><tr><th>Ozellik</th><th>Durum</th><th></th></tr></thead>
      <tbody>
        ${anahtar('ai')}${anahtar('radar')}${anahtar('gccdual')}
        ${anahtar('merkez_lisans')}${anahtar('sinirsiz')}
      </tbody></table>
    </div>

    ${yaz ? `<div class="pano" style="margin-top:16px">
      <h3>Elle Uyelik Tanimla</h3>
      <p class="aciklama">Odeme akisini atlayarak dogrudan hak tanimlar.
        Islem denetim izine kaydedilir.</p>
      <div class="ucul">
        <div><label>Kalem</label><select id="ek-kalem">
          ${(d.fiyatlar || []).map((f) =>
            `<option value="${f.kalem}">${kacir(KALEM_ETIKET[f.kalem] || f.kalem)}</option>`
          ).join('')}
        </select></div>
        <div><label>Adet</label><input id="ek-adet" type="number" min="1" value="1"></div>
        <div><label>Donem</label><select id="ek-donem">
          <option value="aylik">aylik</option>
          <option value="yillik">yillik</option>
          <option value="tek">tek seferlik</option>
        </select></div>
      </div>
      <label>Not</label><input id="ek-not" placeholder="on talep degerlendirmesi, sozlesme no vb.">
      <div class="hata" id="ek-hata"></div>
      <div class="arac-cubugu" style="margin-top:10px">
        <button class="kucuk" id="ek-uygula">Tanimla</button>
      </div>
    </div>` : ''}

    <div class="pano" style="margin-top:16px">
      <h3>Abonelik Kalemleri (${(d.kalemler || []).length})</h3>
      <table><thead><tr><th>Kalem</th><th class="sag">Adet</th><th>Donem</th>
        <th class="sag">Tutar</th><th>Kaynak</th><th>Durum</th><th>Tarih</th></tr></thead>
      <tbody>${(d.kalemler || []).map((k) => `<tr>
        <td>${kacir(KALEM_ETIKET[k.kalem] || k.kalem)}</td>
        <td class="sag">${sayi(k.adet)}</td>
        <td>${kacir(k.donem || '—')}</td>
        <td class="sag">${k.toplam_usd == null ? '—' : '$' + sayi(k.toplam_usd)}</td>
        <td>${rozet(k.kaynak || '—', k.kaynak === 'veilox' ? 'mor' :
          (k.kaynak === 'stripe' ? 'mavi' : 'gri'))}</td>
        <td>${rozet(k.durum, k.durum === 'etkin' ? 'yesil' : 'gri')}</td>
        <td class="tek-satir">${tarih(k.olusma_ts, false)}</td></tr>`).join('') ||
        '<tr><td colspan="7" class="bos">Kalem yok</td></tr>'}</tbody></table>
    </div>`,
    [{ metin: 'Kapat', sinif: 'ikincil', tik: pencereKapat }], true);

  if (el('#ek-uygula')) el('#ek-uygula').onclick = async () => {
    try {
      await cagir('/api/admin/firma/' + fid + '/kalem', {
        method: 'POST',
        body: {
          kalem: el('#ek-kalem').value,
          adet: Number(el('#ek-adet').value) || 1,
          donem: el('#ek-donem').value,
          notlar: el('#ek-not').value.trim()
        }
      });
      pencereKapat();
      bildir('Uyelik tanimlandi', 'iyi');
      firmaAbonelik(fid);
    } catch (e) { el('#ek-hata').textContent = e.message; }
  };
};

window.yetkiDegistir = async (fid, alan, deger) => {
  const ad = YETKI_ETIKET[alan] || alan;
  const uyari = (alan === 'sinirsiz' || alan === 'merkez_lisans') && deger
    ? `<div class="uyari-kutu" style="margin-top:12px">Bu yetki tum koltuk ve
       ozellik sinirlarini kaldirir. Merkez Uygulama satin alan sirketler icin
       kullanilir.</div>` : '';
  pencereAc(ad + (deger ? ' — Ac' : ' — Kapat'), `
    <p><b>${kacir(ad)}</b> ${deger ? 'acilacak' : 'kapatilacak'}.</p>${uyari}
    <div class="hata" id="yd-hata"></div>`,
    [
      { metin: 'Vazgec', sinif: 'ikincil', tik: () => { pencereKapat(); firmaAbonelik(fid); } },
      { metin: deger ? 'Ac' : 'Kapat', sinif: deger ? '' : 'tehlike',
        tik: async () => {
          try {
            await cagir('/api/admin/firma/' + fid + '/yetki',
              { method: 'POST', body: { alan, deger } });
            pencereKapat();
            bildir(ad + (deger ? ' acildi' : ' kapatildi'), 'iyi');
            firmaAbonelik(fid);
          } catch (e) { el('#yd-hata').textContent = e.message; }
        } }
    ]);
};

/* ================================================================ KULLANICILAR */
async function sayfaKullanicilar(par) {
  DURUM.kul = Object.assign({ sayfa: 1, boyut: 50, arama: '', rol: '', firma_id: '' },
    DURUM.kul, par);
  await kullaniciTabloYenile();
}

async function kullaniciTabloYenile() {
  const s = DURUM.kul;
  const [y, fl] = await Promise.all([
    cagir('/api/admin/kullanicilar?' + new URLSearchParams({
      sayfa: s.sayfa, boyut: s.boyut, arama: s.arama || '', rol: s.rol || '',
      firma_id: s.firma_id || ''
    })),
    cagir('/api/admin/firmalar?boyut=500')
  ]);
  DURUM.firmaListesi = fl.kayitlar;
  el('#icerik').innerHTML = `
    <h2>Kullanıcılar</h2>
    <p class="aciklama">Müşteri firmalarının kullanıcıları, rolleri ve uçuş sayıları.</p>
    <div class="arac-cubugu">
      <input id="k-arama" placeholder="Ad, soyad veya e-posta" value="${kacir(s.arama)}">
      <select id="k-firma"><option value="">Tüm müşteriler</option>
        ${fl.kayitlar.map((f) => `<option value="${f.firma_id}"${
          String(s.firma_id) === String(f.firma_id) ? ' selected' : ''
        }>${kacir(f.kisa_ad)}</option>`).join('')}</select>
      <select id="k-rol"><option value="">Tüm roller</option>
        ${['firma_yonetici', 'pilot', 'gozlemci'].map((r) =>
          `<option value="${r}"${s.rol === r ? ' selected' : ''}>${r}</option>`).join('')}
      </select>
      <button class="ikincil kucuk" id="k-ara">Ara</button>
      <div class="bosluk"></div>
      ${BEN.rol === 'sistem_yonetici' ?
        '<button class="kucuk" id="k-yeni">+ Yeni Kullanıcı</button>' : ''}
    </div>
    <div class="pano" style="margin-top:0">
      <table>
        <thead><tr>
          <th>Ad Soyad</th><th>E-posta</th><th>Müşteri</th><th>Rol</th><th>Durum</th>
          <th class="sag">Uçuş</th><th class="sag">Süre</th><th class="sag">Video</th>
          <th>Son Giriş</th><th></th>
        </tr></thead>
        <tbody>${y.kayitlar.map((k) => `<tr>
          <td>${kacir(k.ad_soyad || '—')}</td>
          <td>${kacir(k.eposta)}</td>
          <td><code class="kod">${kacir(k.firma_kisa_ad)}</code></td>
          <td>${rozet(k.rol, k.rol === 'firma_yonetici' ? 'mor' : 'mavi')}</td>
          <td>${rozet(k.durum, DURUM_RENK[k.durum] || 'gri')}</td>
          <td class="sag">${sayi(k.ucus_sayisi)}</td>
          <td class="sag">${sure(k.toplam_sure_sn)}</td>
          <td class="sag">${sayi(k.video_sayisi)}</td>
          <td class="tek-satir">${tarih(k.son_giris_ts)}</td>
          <td class="sag tek-satir">
            <button class="ikincil kucuk" onclick="kullaniciDetay(${k.kullanici_id})">Detay</button>
          </td></tr>`).join('') ||
          '<tr><td colspan="10" class="bos">Kayıt bulunamadı</td></tr>'}</tbody>
      </table>
      ${sayfalamaHTML(y.toplam, y.sayfa, y.boyut, 'kullaniciSayfa')}
    </div>`;
  el('#k-ara').onclick = () => {
    DURUM.kul.arama = el('#k-arama').value.trim();
    DURUM.kul.rol = el('#k-rol').value;
    DURUM.kul.firma_id = el('#k-firma').value;
    DURUM.kul.sayfa = 1;
    kullaniciTabloYenile();
  };
  el('#k-arama').onkeydown = (o) => { if (o.key === 'Enter') el('#k-ara').click(); };
  if (el('#k-yeni')) el('#k-yeni').onclick = () => kullaniciPencere(null);
}

window.kullaniciSayfa = (n) => { DURUM.kul.sayfa = n; kullaniciTabloYenile(); };

window.kullaniciDetay = async (kid) => {
  const k = await cagir('/api/admin/kullanicilar/' + kid);
  pencereAc(k.ad_soyad || k.eposta, `
    <dl class="ozet">
      <dt>E-posta</dt><dd>${kacir(k.eposta)}</dd>
      <dt>Müşteri</dt><dd>${kacir(k.firma_kisa_ad)}</dd>
      <dt>Rol</dt><dd>${rozet(k.rol, 'mavi')}</dd>
      <dt>Durum</dt><dd>${rozet(k.durum, DURUM_RENK[k.durum] || 'gri')}</dd>
      <dt>Telefon</dt><dd>${kacir(k.telefon || '—')}</dd>
      <dt>Lisans no</dt><dd>${kacir(k.pilot_lisans || k.lisans_no || '—')}</dd>
      <dt>Uçuş</dt><dd>${sayi(k.ucus_sayisi)} · ${sure(k.toplam_sure_sn)}</dd>
      <dt>Video</dt><dd>${sayi(k.video_sayisi)}</dd>
      <dt>Son giriş</dt><dd>${tarih(k.son_giris_ts)}</dd>
      <dt>Kayıt</dt><dd>${tarih(k.olusma_ts)}</dd>
    </dl>
    <div class="pano" style="margin-top:16px">
      <h3>Son uçuşlar</h3>
      <table><thead><tr><th>Tarih</th><th>Dron</th><th>Görev</th>
        <th class="sag">Süre</th><th></th></tr></thead>
      <tbody>${(k.son_ucuslar || []).map((u) => `<tr>
        <td class="tek-satir">${tarih(u.baslangic_ts)}</td>
        <td>${kacir(u.dron || '—')}</td>
        <td>${rozet(u.gorev_durumu || '—', GOREV_RENK[u.gorev_durumu] || 'gri')}</td>
        <td class="sag">${sure(u.sure_sn)}</td>
        <td class="sag"><button class="ikincil kucuk"
            onclick="ucusDetay(${u.ucus_id})">İzle</button></td></tr>`).join('') ||
        '<tr><td colspan="5" class="bos">Uçuş kaydı yok</td></tr>'}</tbody></table>
    </div>`,
    [
      { metin: 'Tüm uçuşları', sinif: 'ikincil',
        tik: () => { pencereKapat(); location.hash = `#ucuslar?kullanici_id=${kid}`; } },
      ...(BEN.rol === 'sistem_yonetici' ? [
        { metin: 'Düzenle', sinif: 'ikincil', tik: () => kullaniciPencere(k) }
      ] : []),
      { metin: 'Kapat', sinif: 'ikincil', tik: pencereKapat }
    ], true);
};

function kullaniciPencere(k) {
  const d = k || {};
  const fl = DURUM.firmaListesi || [];
  pencereAc(k ? 'Kullanıcıyı Düzenle' : 'Yeni Kullanıcı', `
    ${k ? '' : `<label>Müşteri *</label><select id="u-firma">
      ${fl.map((f) => `<option value="${f.firma_id}">${kacir(f.kisa_ad)} — ${kacir(f.unvan)}</option>`).join('')}
    </select>`}
    <label>E-posta *</label>
    <input id="u-eposta" type="email" value="${kacir(d.eposta || '')}" ${k ? 'disabled' : ''}>
    <div class="ikili">
      <div><label>Ad</label><input id="u-ad" value="${kacir(d.ad || '')}"></div>
      <div><label>Soyad</label><input id="u-soyad" value="${kacir(d.soyad || '')}"></div>
    </div>
    <div class="ikili">
      <div><label>Rol</label><select id="u-rol">
        ${['pilot', 'firma_yonetici', 'gozlemci'].map((r) =>
          `<option value="${r}"${d.rol === r ? ' selected' : ''}>${r}</option>`).join('')}
      </select></div>
      <div><label>Durum</label><select id="u-durum">
        ${['etkin', 'askida', 'pasif'].map((r) =>
          `<option value="${r}"${d.durum === r ? ' selected' : ''}>${r}</option>`).join('')}
      </select></div>
    </div>
    <div class="ikili">
      <div><label>Telefon</label><input id="u-tel" value="${kacir(d.telefon || '')}"></div>
      <div><label>Lisans no</label><input id="u-lisans" value="${kacir(d.lisans_no || '')}"></div>
    </div>
    <label>${k ? 'Yeni şifre (boş bırakılırsa değişmez)' : 'Şifre *'}</label>
    <input id="u-sifre" type="password" placeholder="en az 8 karakter, harf ve rakam">
    <div class="hata" id="u-hata"></div>`,
    [
      { metin: 'Vazgeç', sinif: 'ikincil', tik: pencereKapat },
      { metin: k ? 'Kaydet' : 'Oluştur', tik: () => kullaniciKaydet(k && k.kullanici_id) }
    ]);
}

async function kullaniciKaydet(kid) {
  const govde = {
    ad: el('#u-ad').value.trim(), soyad: el('#u-soyad').value.trim(),
    rol: el('#u-rol').value, durum: el('#u-durum').value,
    telefon: el('#u-tel').value.trim(), lisans_no: el('#u-lisans').value.trim()
  };
  const sifre = el('#u-sifre').value;
  if (sifre) govde.sifre = sifre;
  if (!kid) {
    govde.firma_id = Number(el('#u-firma').value);
    govde.eposta = el('#u-eposta').value.trim();
  }
  try {
    if (kid) await cagir('/api/admin/kullanicilar/' + kid, { method: 'PUT', body: govde });
    else await cagir('/api/admin/kullanicilar', { method: 'POST', body: govde });
    pencereKapat();
    bildir(kid ? 'Kullanıcı güncellendi' : 'Kullanıcı oluşturuldu', 'iyi');
    kullaniciTabloYenile();
  } catch (e) {
    el('#u-hata').textContent = e.message;
  }
}

/* ================================================================ UÇUŞLAR */
async function sayfaUcuslar(par) {
  DURUM.ucus = Object.assign(
    { sayfa: 1, boyut: 50, firma_id: '', kullanici_id: '', baslangic: '', bitis: '' },
    DURUM.ucus, par);
  await ucusTabloYenile();
}

async function ucusTabloYenile() {
  const s = DURUM.ucus;
  const [y, fl] = await Promise.all([
    cagir('/api/admin/ucuslar?' + new URLSearchParams({
      sayfa: s.sayfa, boyut: s.boyut, firma_id: s.firma_id || '',
      kullanici_id: s.kullanici_id || '', baslangic: s.baslangic || '',
      bitis: s.bitis || ''
    })),
    cagir('/api/admin/firmalar?boyut=500')
  ]);
  el('#icerik').innerHTML = `
    <h2>Uçuş Kayıtları</h2>
    <p class="aciklama">Sahadan merkeze aktarılan uçuşlar. Satırdaki İzle düğmesi
      uçuş rotasını, telemetri grafiğini ve varsa video kayıtlarını açar.</p>
    <div class="arac-cubugu">
      <select id="u-firma"><option value="">Tüm müşteriler</option>
        ${fl.kayitlar.map((f) => `<option value="${f.firma_id}"${
          String(s.firma_id) === String(f.firma_id) ? ' selected' : ''
        }>${kacir(f.kisa_ad)}</option>`).join('')}</select>
      <input id="u-bas" type="date" value="${kacir(s.baslangic)}">
      <input id="u-bit" type="date" value="${kacir(s.bitis)}">
      <button class="ikincil kucuk" id="u-ara">Filtrele</button>
      <button class="ikincil kucuk" id="u-sifirla">Sıfırla</button>
    </div>
    <div class="pano" style="margin-top:0">
      <table>
        <thead><tr>
          <th>Tarih</th><th>Müşteri</th><th>Pilot</th><th>Dron</th><th>Tür</th>
          <th>Görev</th><th class="sag">Süre</th><th class="sag">Mesafe</th>
          <th class="sag">Maks. İrtifa</th><th class="sag">Video</th><th></th>
        </tr></thead>
        <tbody>${y.kayitlar.map((u) => `<tr>
          <td class="tek-satir">${tarih(u.baslangic_ts)}</td>
          <td><code class="kod">${kacir(u.firma_kisa_ad)}</code></td>
          <td>${kacir(u.pilot || '—')}</td>
          <td>${kacir(u.dron || '—')}</td>
          <td>${kacir(u.arac_turu || '—')}</td>
          <td>${rozet(u.gorev_durumu || '—', GOREV_RENK[u.gorev_durumu] || 'gri')}</td>
          <td class="sag">${sure(u.sure_sn)}</td>
          <td class="sag">${u.mesafe_m ? sayi(u.mesafe_m / 1000, 2) + ' km' : '—'}</td>
          <td class="sag">${u.maks_irtifa_m ? sayi(u.maks_irtifa_m, 1) + ' m' : '—'}</td>
          <td class="sag">${Number(u.video_sayisi) > 0 ?
            rozet(u.video_sayisi, 'mor') : '—'}</td>
          <td class="sag"><button class="ikincil kucuk"
              onclick="ucusDetay(${u.ucus_id})">İzle</button></td>
        </tr>`).join('') ||
          '<tr><td colspan="11" class="bos">Uçuş kaydı bulunamadı</td></tr>'}</tbody>
      </table>
      ${sayfalamaHTML(y.toplam, y.sayfa, y.boyut, 'ucusSayfa')}
    </div>`;
  el('#u-ara').onclick = () => {
    DURUM.ucus.firma_id = el('#u-firma').value;
    DURUM.ucus.baslangic = el('#u-bas').value;
    DURUM.ucus.bitis = el('#u-bit').value;
    DURUM.ucus.sayfa = 1;
    ucusTabloYenile();
  };
  el('#u-sifirla').onclick = () => {
    DURUM.ucus = { sayfa: 1, boyut: 50, firma_id: '', kullanici_id: '',
                   baslangic: '', bitis: '' };
    ucusTabloYenile();
  };
}

window.ucusSayfa = (n) => { DURUM.ucus.sayfa = n; ucusTabloYenile(); };

window.ucusDetay = async (uid) => {
  const u = await cagir('/api/admin/ucuslar/' + uid);
  pencereAc(`Uçuş ${u.ucus_uid}`, `
    <dl class="ozet">
      <dt>Müşteri</dt><dd>${kacir(u.firma_kisa_ad || '')} — ${kacir(u.firma_unvan || '')}</dd>
      <dt>Pilot</dt><dd>${kacir(u.pilot || '—')}
        ${u.pilot_eposta ? ' · ' + kacir(u.pilot_eposta) : ''}</dd>
      <dt>Dron</dt><dd>${kacir(u.dron || '—')} ${u.arac_turu ?
        '· ' + kacir(u.arac_turu) : ''} ${u.sysid ? '· SYSID ' + u.sysid : ''}</dd>
      <dt>Başlangıç</dt><dd>${tarih(u.baslangic_ts)}</dd>
      <dt>Bitiş</dt><dd>${tarih(u.bitis_ts)}</dd>
      <dt>Süre</dt><dd>${sure(u.sure_sn)}</dd>
      <dt>Mesafe</dt><dd>${u.mesafe_m ? sayi(u.mesafe_m / 1000, 2) + ' km' : '—'}</dd>
      <dt>Maks. irtifa</dt><dd>${u.maks_irtifa_m ? sayi(u.maks_irtifa_m, 1) + ' m' : '—'}</dd>
      <dt>Maks. hız</dt><dd>${u.maks_hiz_ms ? sayi(u.maks_hiz_ms, 1) + ' m/s' : '—'}</dd>
      <dt>Görev</dt><dd>${kacir(u.gorev_turu || '—')} ·
        ${rozet(u.gorev_durumu || '—', GOREV_RENK[u.gorev_durumu] || 'gri')}</dd>
      <dt>Kaynak sunucu</dt><dd>${kacir(u.sunucu_ad || '—')}</dd>
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
    const y = await cagir(`/api/admin/ucuslar/${uid}/telemetri?seyreltme=6`);
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
  const G = 900, Y = 200, b = { s: 44, u: 14, a: 26, sa: 44 };
  const irt = k.map((x) => Number(x.irtifa_m) || 0);
  const hiz = k.map((x) => Number(x.hiz_ms) || 0);
  const irtEnb = Math.max(1, ...irt), hizEnb = Math.max(1, ...hiz);
  const gx = (i) => b.s + (i / Math.max(1, k.length - 1)) * (G - b.s - b.sa);
  const gy = (d, enb) => Y - b.a - (d / enb) * (Y - b.u - b.a);
  const yol = (dizi, enb) => dizi.map((d, i) =>
    `${i ? 'L' : 'M'}${gx(i).toFixed(1)},${gy(d, enb).toFixed(1)}`).join(' ');
  // FAZ18-IS14-CIZIM-OLCEK: renkler CSS degiskenine baglanir.
  // Sol eksen (irtifa) --vurgu, sag eksen (hiz) --sari olarak AYRI
  // kalir; ikisini de --yazi2 yapmak iki veri serisinin ayrimini yok
  // ederdi. Olcek ust siniri bu isleve UYGULANMAZ: cizgi grafiktir,
  // cubuk genisligi kavrami yoktur.
  const izgara = [0, 0.25, 0.5, 0.75, 1].map((o) => {
    const y = Y - b.a - o * (Y - b.u - b.a);
    return `<line x1="${b.s}" y1="${y}" x2="${G - b.sa}" y2="${y}"
                  style="stroke:var(--cerceve)"/>
      <text x="6" y="${y + 3}" style="fill:var(--vurgu)" font-size="9">
        ${Math.round(o * irtEnb)}</text>
      <text x="${G - b.sa + 6}" y="${y + 3}" style="fill:var(--sari)"
            font-size="9">${(o * hizEnb).toFixed(1)}</text>`;
  }).join('');
  const ilk = tarih(k[0].ts), son = tarih(k[k.length - 1].ts);
  kap.innerHTML = `<svg class="cizim" viewBox="0 0 ${G} ${Y}"
      preserveAspectRatio="xMidYMid meet">
      ${izgara}
      <path d="${yol(irt, irtEnb)}" fill="none"
            style="stroke:var(--vurgu)" stroke-width="1.6"/>
      <path d="${yol(hiz, hizEnb)}" fill="none"
            style="stroke:var(--sari)" stroke-width="1.4"
            stroke-dasharray="4 3"/>
      <text x="${b.s}" y="${Y - 8}" style="fill:var(--yazi2)"
            font-size="9">${ilk}</text>
      <text x="${G - b.sa}" y="${Y - 8}" style="fill:var(--yazi2)"
            font-size="9" text-anchor="end">${son}</text>
    </svg>
    <div style="margin-top:6px;font-size:11px;color:var(--yazi2)">
      <span style="color:var(--vurgu)">▬</span> irtifa (m, sol)
      &nbsp;&nbsp;<span style="color:var(--sari)">▬</span> hız (m/s, sağ)
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
  // FAZ18-IS14-CIZIM-OLCEK: en agir tema kusuru BURADAYDI — grafigin
  // KENDI ZEMINI sabit koyu (#0d1420) idi. Acik temada panel beyaza
  // donerken bu grafik koyu bir kare olarak kalip tema gecisini gorsel
  // olarak kiriyordu. --zemin2 tema duyarlidir (koyu #111825 / acik
  // #ffffff). Efsane isaretleri cizgi/nokta renkleriyle AYNI degiskene
  // baglanir; farkli baglanirsa efsane yanlis seriyi gosterirdi.
  kap.innerHTML = `<svg viewBox="0 0 ${G} ${Y}" style="width:100%;height:300px;
      background:var(--zemin2);border-radius:8px">
      <path d="${yol}" fill="none" style="stroke:var(--yesil)" stroke-width="2"
            stroke-linejoin="round"/>
      <circle cx="${gx(Number(bas.lon))}" cy="${gy(Number(bas.lat))}" r="5"
              style="fill:var(--vurgu)"><title>Kalkış</title></circle>
      <circle cx="${gx(Number(son.lon))}" cy="${gy(Number(son.lat))}" r="5"
              style="fill:var(--kirmizi)"><title>İniş</title></circle>
    </svg>
    <div style="margin-top:6px;font-size:11px;color:var(--yazi2)">
      <span style="color:var(--vurgu)">●</span> kalkış
      &nbsp;<span style="color:var(--kirmizi)">●</span> iniş
      &nbsp;· enlem ${laEn.toFixed(5)}–${laEnb.toFixed(5)}
      &nbsp;· boylam ${loEn.toFixed(5)}–${loEnb.toFixed(5)}
      &nbsp;· yatay kapsam ≈ ${sayi(mesafe, 0)} m
    </div>`;
}

/* ================================================================ VİDEOLAR */
async function sayfaVideolar(par) {
  DURUM.video = Object.assign({ sayfa: 1, boyut: 50, firma_id: '' },
    DURUM.video, par);
  await videoTabloYenile();
}

async function videoTabloYenile() {
  const s = DURUM.video;
  const [y, fl] = await Promise.all([
    cagir('/api/admin/videolar?' + new URLSearchParams({
      sayfa: s.sayfa, boyut: s.boyut, firma_id: s.firma_id || ''
    })),
    cagir('/api/admin/firmalar?boyut=500')
  ]);
  el('#icerik').innerHTML = `
    <h2>Video Kayıtları</h2>
    <p class="aciklama">Merkezde saklanan videolar doğrudan oynatılır. Yerel
      sunucuda kalan videolar, sunucu çevrimiçi olduğunda ters bağlantı
      üzerinden aktarılarak oynatılır.</p>
    <div class="arac-cubugu">
      <select id="v-firma"><option value="">Tüm müşteriler</option>
        ${fl.kayitlar.map((f) => `<option value="${f.firma_id}"${
          String(s.firma_id) === String(f.firma_id) ? ' selected' : ''
        }>${kacir(f.kisa_ad)}</option>`).join('')}</select>
      <button class="ikincil kucuk" id="v-ara">Filtrele</button>
    </div>
    <div class="pano" style="margin-top:0">
      <table>
        <thead><tr><th>Tarih</th><th>Müşteri</th><th>Başlık</th><th>Pilot</th>
          <th>Kaynak</th><th class="sag">Süre</th><th class="sag">Boyut</th>
          <th>Çözünürlük</th><th>Depo</th><th></th></tr></thead>
        <tbody>${y.kayitlar.map((v) => `<tr>
          <td class="tek-satir">${tarih(v.baslangic_ts)}</td>
          <td><code class="kod">${kacir(v.firma_kisa_ad)}</code></td>
          <td>${kacir(v.baslik || v.video_uid)}</td>
          <td>${kacir(v.pilot || '—')}</td>
          <td>${kacir(v.kaynak || '—')}</td>
          <td class="sag">${sure(v.sure_sn)}</td>
          <td class="sag">${bayt(v.boyut_bayt)}</td>
          <td>${kacir(v.cozunurluk || '—')}</td>
          <td>${rozet(v.depo_yeri, v.depo_yeri === 'merkez' ? 'yesil' : 'sari')}
              ${v.sunucu_cevrimici ? '<span class="nokta acik"></span>' : ''}</td>
          <td class="sag"><button class="ikincil kucuk"
              onclick="videoIzle(${v.video_id})">Oynat</button></td>
        </tr>`).join('') ||
          '<tr><td colspan="10" class="bos">Video kaydı bulunamadı</td></tr>'}</tbody>
      </table>
      ${sayfalamaHTML(y.toplam, y.sayfa, y.boyut, 'videoSayfa')}
    </div>`;
  el('#v-ara').onclick = () => {
    DURUM.video.firma_id = el('#v-firma').value;
    DURUM.video.sayfa = 1;
    videoTabloYenile();
  };
}

window.videoSayfa = (n) => { DURUM.video.sayfa = n; videoTabloYenile(); };

window.videoIzle = async (vid) => {
  const v = await cagir('/api/admin/videolar/' + vid);
  const merkezde = v.depo_yeri === 'merkez';
  const uyari = merkezde ? '' : (v.sunucu_cevrimici
    ? `<div class="uyari-kutu">Bu video yerel sunucuda
        (<strong>${kacir(v.sunucu_ad || '—')}</strong>) saklanıyor. Sunucu
        çevrimiçi olduğu için ters bağlantı üzerinden aktarılacak; başlaması
        biraz sürebilir.</div>`
    : `<div class="uyari-kutu">Bu video yerel sunucuda
        (<strong>${kacir(v.sunucu_ad || '—')}</strong>) saklanıyor ve sunucu
        şu anda <strong>çevrimdışı</strong>. Oynatma için sunucunun merkeze
        bağlanması gerekir.</div>`);
  pencereAc(v.baslik || v.video_uid, `
    ${uyari}
    <video id="oynatici" controls preload="metadata"
           src="/api/admin/videolar/${vid}/akis"></video>
    <dl class="ozet" style="margin-top:14px">
      <dt>Müşteri</dt><dd>${kacir(v.firma_kisa_ad || '')}</dd>
      <dt>Pilot</dt><dd>${kacir(v.pilot || '—')}</dd>
      <dt>Uçuş</dt><dd>${v.ucus_uid ? `<a href="#" onclick="pencereKapat();
        ucusDetay(${v.ucus_id});return false">${kacir(v.ucus_uid)}</a>` : '—'}</dd>
      <dt>Kaynak</dt><dd>${kacir(v.kaynak || '—')}</dd>
      <dt>Başlangıç</dt><dd>${tarih(v.baslangic_ts)}</dd>
      <dt>Süre</dt><dd>${sure(v.sure_sn)}</dd>
      <dt>Boyut</dt><dd>${bayt(v.boyut_bayt)}</dd>
      <dt>Çözünürlük</dt><dd>${kacir(v.cozunurluk || '—')} ${v.kodek ?
        '· ' + kacir(v.kodek) : ''}</dd>
      <dt>Depo</dt><dd>${rozet(v.depo_yeri, merkezde ? 'yesil' : 'sari')}</dd>
    </dl>`,
    [{ metin: 'Kapat', sinif: 'ikincil', tik: () => {
      const o = el('#oynatici');
      if (o) { o.pause(); o.removeAttribute('src'); o.load(); }
      pencereKapat();
    } }], true);
};

/* ================================================================ SUNUCULAR */
async function sayfaSunucular() {
  const [y, fl] = await Promise.all([
    cagir('/api/admin/sunucular'),
    cagir('/api/admin/firmalar?boyut=500')
  ]);
  DURUM.firmaListesi = fl.kayitlar;
  el('#icerik').innerHTML = `
    <h2>Sunucular</h2>
    <p class="aciklama">Müşterilerin kendi ortamlarına kurduğu köprü sunucuları.
      Bağlantıyı her zaman sunucu başlatır (client→server), bu nedenle sabit IP
      veya port yönlendirmesi gerekmez. Çevrimiçi sunucular, saha
      kullanıcılarının bağlantı yöneticisinde seçilebilir olarak görünür.</p>
    <div class="arac-cubugu">
      <div class="bosluk"></div>
      ${BEN.rol === 'sistem_yonetici' ?
        '<button class="kucuk" id="s-yeni">+ Sunucu Kaydı Oluştur</button>' : ''}
    </div>
    <div class="pano" style="margin-top:0">
      <table>
        <thead><tr><th>Durum</th><th>Ad</th><th>Müşteri</th><th>Sürüm</th>
          <th>Platform</th><th>Makine</th><th class="sag">Dron</th>
          <th>Son Görülme</th><th>Kurulum UID</th><th></th></tr></thead>
        <tbody>${y.kayitlar.map((s) => `<tr>
          <td class="tek-satir"><span class="nokta ${s.cevrimici ? 'acik' : 'kapali'}"></span>
              ${s.cevrimici ? 'Çevrimiçi' : 'Çevrimdışı'}</td>
          <td>${kacir(s.ad)}</td>
          <td><code class="kod">${kacir(s.firma_kisa_ad)}</code></td>
          <td>${kacir(s.surum || '—')}</td>
          <td>${kacir(s.platform || '—')}</td>
          <td>${kacir(s.makine_adi || '—')}</td>
          <td class="sag">${sayi(s.dron_sayisi)}</td>
          <td class="tek-satir">${tarih(s.son_gorulme_ts)}</td>
          <td><code class="kod">${kacir((s.kurulum_uid || '').slice(0, 12))}…</code></td>
          <td class="sag tek-satir">
            ${s.cevrimici ? `<button class="ikincil kucuk"
              onclick="sunucuSorgula(${s.ornek_id},'${kacir(s.ad)}')">Sorgula</button>` : ''}
            ${BEN.rol === 'sistem_yonetici' ? `<button class="tehlike kucuk"
              onclick="sunucuSil(${s.ornek_id},'${kacir(s.ad)}')">Sil</button>` : ''}
          </td></tr>`).join('') ||
          '<tr><td colspan="10" class="bos">Kayıtlı sunucu yok</td></tr>'}</tbody>
      </table>
    </div>`;
  if (el('#s-yeni')) el('#s-yeni').onclick = sunucuEklePencere;
}

function sunucuEklePencere() {
  const fl = DURUM.firmaListesi || [];
  pencereAc('Sunucu Kaydı Oluştur', `
    <p class="aciklama">Kayıt oluşturulduğunda bir <strong>kurulum kimliği</strong>
      ve <strong>gizli anahtar</strong> üretilir. Bu ikili, müşterinin sunucu
      kurulum sihirbazına girilir; sunucu bu bilgiyle merkeze bağlanır.
      Gizli anahtar yalnızca bir kez gösterilir.</p>
    <label>Müşteri *</label>
    <select id="sn-firma">${fl.map((f) =>
      `<option value="${f.firma_id}">${kacir(f.kisa_ad)} — ${kacir(f.unvan)}</option>`
    ).join('')}</select>
    <label>Sunucu adı *</label>
    <input id="sn-ad" placeholder="Örn. Ankara Saha Köprüsü">
    <label>Açıklama</label>
    <input id="sn-aciklama" placeholder="Konum, sorumlusu vb.">
    <div class="hata" id="sn-hata"></div>`,
    [
      { metin: 'Vazgeç', sinif: 'ikincil', tik: pencereKapat },
      { metin: 'Oluştur', tik: async () => {
        try {
          const y = await cagir('/api/admin/sunucular', {
            method: 'POST',
            body: { firma_id: Number(el('#sn-firma').value),
                    ad: el('#sn-ad').value.trim(),
                    aciklama: el('#sn-aciklama').value.trim() }
          });
          sunucuKimlikGoster(y.sunucu);
        } catch (e) { el('#sn-hata').textContent = e.message; }
      } }
    ]);
}

function sunucuKimlikGoster(s) {
  pencereAc('Sunucu Kimliği Oluşturuldu', `
    <div class="uyari-kutu">Gizli anahtar bir daha gösterilmeyecek.
      Şimdi kopyalayıp müşterinin kurulum sihirbazına giriniz.</div>
    <label style="margin-top:14px">Merkez adresi</label>
    <div class="gizli-kutu">${kacir(s.merkez_adres || 'wss://goktungu.com')}</div>
    <label>Kurulum kimliği (kurulum_uid)</label>
    <div class="gizli-kutu">${kacir(s.kurulum_uid)}</div>
    <label>Gizli anahtar</label>
    <div class="gizli-kutu">${kacir(s.gizli)}</div>`,
    [{ metin: 'Kopyaladım, kapat', tik: () => {
      pencereKapat();
      sayfaSunucular();
    } }]);
}

window.sunucuSil = (oid, ad) => {
  pencereAc('Sunucu Kaydını Sil', `
    <div class="uyari-kutu"><strong>${kacir(ad)}</strong> kaydı silinecek.
      Sunucu bir daha merkeze bağlanamaz; uçuş ve video kayıtları korunur
      ancak kaynak sunucu bağı boşalır.</div>`,
    [
      { metin: 'Vazgeç', sinif: 'ikincil', tik: pencereKapat },
      { metin: 'Sil', sinif: 'tehlike', tik: async () => {
        try {
          await cagir('/api/admin/sunucular/' + oid, { method: 'DELETE' });
          pencereKapat();
          bildir('Sunucu kaydı silindi', 'iyi');
          sayfaSunucular();
        } catch (e) { bildir(e.message, 'kotu'); }
      } }
    ]);
};

window.sunucuSorgula = async (oid, ad) => {
  pencereAc(`${ad} — canlı sorgu`, `
    <p class="aciklama">Merkez, açık ters bağlantı üzerinden sunucuya sorgu
      gönderir. Sunucu yanıtı burada gösterilir.</p>
    <div class="arac-cubugu">
      <button class="ikincil kucuk" onclick="sunucuEylem(${oid},'dron_liste')">Dron listesi</button>
      <button class="ikincil kucuk" onclick="sunucuEylem(${oid},'port_liste')">Port listesi</button>
      <button class="ikincil kucuk" onclick="sunucuEylem(${oid},'servis_durum')">Servis durumu</button>
      <button class="ikincil kucuk" onclick="sunucuEylem(${oid},'sistem_bilgi')">Sistem bilgisi</button>
    </div>
    <div id="sorgu-sonuc" class="pano" style="margin-top:0">
      <div class="bos">Bir sorgu seçin</div></div>`,
    [{ metin: 'Kapat', sinif: 'ikincil', tik: pencereKapat }], true);
};

window.sunucuEylem = async (oid, eylem) => {
  const k = el('#sorgu-sonuc');
  k.innerHTML = '<div class="yukleniyor">Sunucudan yanıt bekleniyor…</div>';
  try {
    const y = await cagir(`/api/admin/sunucular/${oid}/sor/${eylem}`);
    k.innerHTML = `<pre style="margin:0;white-space:pre-wrap;font-size:12px;
      font-family:ui-monospace,Menlo,Consolas,monospace;color:#7ee787">${
      kacir(JSON.stringify(y.veri, null, 2))}</pre>`;
  } catch (e) {
    k.innerHTML = `<div class="hata">${kacir(e.message)}</div>`;
  }
};

/* ================================================================ SÜRÜMLER */
async function sayfaSurumler() {
  const y = await cagir('/api/admin/surumler');
  const kayitlar = y.surumler || [];
  el('#icerik').innerHTML = `
    <h2>Sürümler</h2>
    <p class="aciklama">Otomatik güncelleme deposu. Saha kurulumları açılışta
      bu listeyi kontrol eder, <strong>Ed25519 imzasını doğruladıktan sonra</strong>
      paketi indirip uygular. İmzası doğrulanamayan paket asla uygulanmaz.</p>
    <div class="pano" style="margin-top:0">
      <div class="pano-baslik">Depo</div>
      <table>
        <thead><tr><th>Sürüm</th><th>Ürün</th><th>Platform</th><th>Kanal</th>
          <th>Tür</th><th class="sag">Boyut</th><th>Asgari</th><th>Yayın</th>
          <th>Durum</th><th>İmza</th><th class="sag">İşlem</th></tr></thead>
        <tbody>${kayitlar.map((s) => `<tr>
          <td><strong>${kacir(s.surum)}</strong></td>
          <td>${kacir(s.urun)}</td>
          <td>${kacir(s.platform === 'ortak' ? 'tümü' : s.platform)}</td>
          <td>${rozet(s.kanal, s.kanal === 'kararli' ? 'yesil' :
            (s.kanal === 'beta' ? 'sari' : 'gri'))}</td>
          <td>${rozet(s.paket_tur, s.paket_tur === 'tam' ? 'mor' : 'mavi')}</td>
          <td class="sag">${bayt(s.dosya_boyut)}</td>
          <td>${kacir(s.asgari_surum || '—')}</td>
          <td class="tek-satir">${tarih(s.yayin_ts)}</td>
          <td>${s.etkin ? rozet('yayında', 'yesil') : rozet('kapalı', 'gri')}${
            s.dosya_var ? '' : ' ' + rozet('dosya yok', 'kirmizi')}</td>
          <td>${s.imza ? rozet('imzalı', 'yesil') : rozet('imzasız', 'kirmizi')}</td>
          <td class="sag tek-satir">
            <a href="${kacir(s.indir_yol)}">indir</a>
            <button class="kucuk"
              data-surum="${s.surum_id}" data-eylem="${
                s.etkin ? 'devre_disi' : 'etkinlestir'}">${
                s.etkin ? 'yayından çek' : 'yayımla'}</button>
          </td>
        </tr>`).join('') ||
          '<tr><td colspan="11" class="bos">Depoya yüklenmiş sürüm yok</td></tr>'}</tbody>
      </table>
    </div>
    <div class="pano">
      <div class="pano-baslik">İmza anahtarı</div>
      <table>
        <tr><th>Algoritma</th><td>Ed25519</td></tr>
        <tr><th>Açık anahtar</th><td><code class="kod">${
          kacir(y.acik_anahtar || '—')}</code></td></tr>
        <tr><th>Özel anahtar</th><td>Yalnızca merkez sunucuda
          (<code class="kod">veri/imza/</code>, 0600). Panelden okunamaz.</td></tr>
      </table>
      <p class="aciklama">Paket yayımlama, dosya boyutları nedeniyle sunucu
        üzerinden yapılır:
        <code class="kod">python3.11 yayimla.py --urun gcs --surum 2.4.53
        --dosya /root/paket.tar.gz --paket-tur guncelleme</code></p>
    </div>`;

  el('#icerik').querySelectorAll('button[data-surum]').forEach((d) => {
    d.onclick = async () => {
      d.disabled = true;
      try {
        await cagir(`/api/admin/surumler/${d.dataset.surum}/${d.dataset.eylem}`,
                    { method: 'POST', body: {} });
        bildir(d.dataset.eylem === 'devre_disi'
               ? 'Sürüm yayından çekildi' : 'Sürüm yayımlandı', 'iyi');
        await sayfaSurumler();
      } catch (e) {
        d.disabled = false;
        bildir(e.message, 'kotu');
      }
    };
  });
}

/* ============================================================== GÜVENLİK */
/* FAZ18-IS9-GUVENLIK-IZLEME — Saldırı İzleme.
 *
 * ÜÇ veri kaynağı birleştirilir (sunucuda `mk_guvenlik` yapar):
 *   1. `mk_kaba_kuvvet` belleği -> etkin bloklar, canlı sayaçlar
 *   2. merkez günlüğü           -> KALICI blok geçmişi (günlük özet)
 *   3. fail2ban günlüğü         -> ağ katmanı yasakları (SSH + HTTP)
 *
 * KALICILIK UYARISI arayüzde GÖSTERİLİR: bellek kaynağı servis
 * yeniden başlayınca boşalır. Bu bildirilmezse yönetici yeniden
 * başlatma sonrası "saldırı yok" sanır ve gerçek durumu kaçırır.
 *
 * Günlük satırları dışarıdan gelen IP ve uç adlarını taşır; tüm
 * değerler `kacir()` ile kaçırılır.
 */
const GUV_TUR_AD = {
  basarisiz: 'Başarısız deneme', hesap_kilit: 'Hesap kilidi',
  ip_blok_kisa: 'IP bloğu (kısa)', ip_blok_uzun: 'IP bloğu (uzun)',
  basarili: 'Başarılı giriş'
};
const GUV_TUR_RENK = {
  basarisiz: 'sari', hesap_kilit: 'kirmizi', ip_blok_kisa: 'kirmizi',
  ip_blok_uzun: 'kirmizi', basarili: 'yesil'
};

function guvTur(t) {
  return rozet(GUV_TUR_AD[t] || t, GUV_TUR_RENK[t] || 'gri');
}

/* Blok geçmişi çubuk grafiği.
 *
 * Mevcut `cizimCiz` YENİDEN KULLANILMADI: ipucu metni "uçuş" olarak
 * sabit ve gösterge panelinde kullanılıyor; değiştirmek orayı bozardı.
 * Ölçek/boşluk sözleşmesi aynı tutuldu ki iki grafik görsel olarak
 * tutarlı görünsün.
 */
function guvCizim(kapSecici, gunler) {
  const kap = el(kapSecici);
  if (!kap) return;
  if (!gunler || !gunler.length) {
    kap.innerHTML = '<div class="bos">Bu aralıkta blok kaydı yok</div>';
    return;
  }
  const G = 760, Y = 190, bosluk = { s: 34, u: 12, a: 24, sa: 10 };
  const enb = Math.max(1, ...gunler.map((v) => Number(v.sayi)));
  // FAZ18-IS14-CIZIM-OLCEK: cubuk genisligi UST SINIRA baglanir.
  // Guvenlik baglaminda kusur DAHA SIK gorulur: saglikli bir sunucuda
  // gunlerin cogu SIFIR blok tasir, yani veri dizisi genellikle 1-2
  // ogeden olusur ve grafik tum genisligi kaplayan dev bir bloga
  // donusup "sistem saldiri altinda" izlenimi verirdi.
  const gen = Math.min((G - bosluk.s - bosluk.sa) / gunler.length, 48);
  const cubuklar = gunler.map((v, i) => {
    const h = (Number(v.sayi) / enb) * (Y - bosluk.u - bosluk.a);
    const x = bosluk.s + i * gen + gen * 0.15;
    const y = Y - bosluk.a - h;
    const g = gen * 0.7;
    const etiket = tarih(v.gun, false).slice(0, 5);
    // Renkler CSS DEGISKENINDEN gelir; `--kirmizi` tema duyarlidir
    // (koyu #f85149 / acik #cf222e). Sabit `#d13438` acik temada
    // zeminle kontrasti dusuruyordu.
    return `<g>
      <rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${g.toFixed(1)}"
            height="${Math.max(h, 1).toFixed(1)}"
            style="fill:var(--kirmizi)" rx="2">
        <title>${kacir(etiket)}: ${kacir(v.sayi)} blok</title></rect>
      <text x="${(x + g / 2).toFixed(1)}" y="${Y - 8}"
            style="fill:var(--yazi2)"
            font-size="9" text-anchor="middle">${kacir(etiket)}</text>
    </g>`;
  }).join('');
  const yatay = [0, 0.5, 1].map((o) => {
    const y = Y - bosluk.a - o * (Y - bosluk.u - bosluk.a);
    return `<line x1="${bosluk.s}" y1="${y}" x2="${G - bosluk.sa}" y2="${y}"
                  style="stroke:var(--cerceve)" stroke-width="1"/>
            <text x="4" y="${y + 3}" style="fill:var(--yazi2)"
                  font-size="9">${Math.round(o * enb)}</text>`;
  }).join('');
  kap.innerHTML = `<svg class="cizim" viewBox="0 0 ${G} ${Y}"
      preserveAspectRatio="xMidYMid meet">${yatay}${cubuklar}</svg>`;
}

async function sayfaGuvenlik(par) {
  DURUM.guvenlik = Object.assign({ gun: 7, tur: '', ip: '' },
                                 DURUM.guvenlik, par);
  const s = DURUM.guvenlik;

  let o = {};
  let ol = {};
  try {
    o = await cagir('/api/admin/guvenlik/ozet?' +
                    new URLSearchParams({ gun: s.gun }));
    ol = await cagir('/api/admin/guvenlik/olaylar?' +
                     new URLSearchParams({ sinir: 200, tur: s.tur, ip: s.ip }));
  } catch (e) {
    el('#icerik').innerHTML = `
      <h2>Saldırı İzleme</h2>
      <div class="pano"><div class="bos">Güvenlik verisi okunamadı:
        ${kacir(e.message || e)}</div></div>`;
    return;
  }

  const gec = o.gecmis || {};
  const f2b = o.fail2ban || {};
  const canli = o.canli || {};
  const esik = canli.esik || {};

  const k = (etiket, deger, ek, vurgu) => `
    <div class="kart${vurgu ? ' vurgulu' : ''}">
      <div class="etiket">${etiket}</div>
      <div class="deger">${deger}</div>
      ${ek ? `<div class="ek">${ek}</div>` : ''}
    </div>`;

  const esikMetni = (a) => {
    const d = esik[a];
    return (d && d.length >= 2) ? `${d[0]} deneme / ${sure(d[1])}` : '—';
  };

  /* Etkin bloklar — canlı bellekten. Liste biçimi modülün kendi
   * dönüşüne bağlı; hem düz metin hem nesne gelebileceği için
   * ikisi de karşılanır. */
  const blokSatir = (d, tur) => {
    const ad = (typeof d === 'string') ? d
      : String(d.ip || d.hesap || d.anahtar || '—');
    const kalan = (typeof d === 'object' && d.kalan) ? sure(d.kalan) : '—';
    return `<tr>
      <td>${guvTur(tur)}</td>
      <td class="tek-satir"><code class="kod">${kacir(ad)}</code></td>
      <td>${kacir(kalan)}</td>
      <td><button class="ikincil" onclick="guvCoz('${
        kacir(ad)}','${tur === 'hesap_kilit' ? 'hesap' : 'ip'}')"
        >Bloğu çöz</button></td>
    </tr>`;
  };
  const bloklar = []
    .concat((canli.ip_blok || []).map((d) => blokSatir(d, 'ip_blok_kisa')))
    .concat((canli.hesap_blok || []).map((d) => blokSatir(d, 'hesap_kilit')))
    .join('');

  el('#icerik').innerHTML = `
    <h2>Saldırı İzleme</h2>
    <p class="aciklama">Uygulama katmanı kaba kuvvet koruması ve ağ
      katmanı (fail2ban) yasaklarının birleşik görünümü.</p>

    <div class="kart-izgara">
      ${k('Etkin IP bloğu', sayi(o.etkin_ip_blok),
          'uygulama katmanı', Number(o.etkin_ip_blok) > 0)}
      ${k('Etkin hesap kilidi', sayi(o.etkin_hesap_blok),
          'uygulama katmanı', Number(o.etkin_hesap_blok) > 0)}
      ${k('Ağ yasağı (fail2ban)', sayi(o.ag_etkin_yasak),
          'firewalld kuralı', Number(o.ag_etkin_yasak) > 0)}
      ${k('Bugün blok', sayi(o.bugun_blok), 'kalıcı günlükten')}
      ${k('İzlenen IP', sayi(o.izlenen_ip), 'sayaç tutulan')}
      ${k('İzlenen hesap', sayi(o.izlenen_hesap), 'sayaç tutulan')}
      ${k('Başarısız deneme (24s)', sayi(o.basarisiz_24s), 'bellekten')}
      ${k('Toplam blok', sayi(gec.toplam), `son ${sayi(o.gun_sayisi)} gün`)}
    </div>

    <div class="pano">
      <h3>Blok geçmişi (kalıcı günlük)</h3>
      <div id="guv-cizim"></div>
      ${Number(gec.tarihsiz) > 0 ? `<p class="aciklama">
        ${sayi(gec.tarihsiz)} kayıt tarih damgası taşımıyor (koruma
        günlüğüne damga eklenmeden önce yazılmış). Bu kayıtlar toplam
        ve IP gruplamasına dahil, gün dağılımına değil.</p>` : ''}
    </div>

    <div class="pano">
      <h3>IP'ye göre gruplama</h3>
      <table>
        <thead><tr><th>IP</th><th class="sag">Blok</th><th>Türler</th>
          <th>Uçlar</th><th>Son olay</th><th></th></tr></thead>
        <tbody>${(gec.ip_grup || []).map((d) => `<tr>
          <td class="tek-satir"><code class="kod">${kacir(d.ip)}</code></td>
          <td class="sag">${sayi(d.sayi)}</td>
          <td>${Object.keys(d.turler || {}).map((t) =>
            `${guvTur(t)} <small>${sayi(d.turler[t])}</small>`).join(' ')}</td>
          <td><small>${(d.uclar || []).map((u) =>
            kacir(u)).join('<br>')}</small></td>
          <td class="tek-satir">${d.son_ts ?
            tarih(d.son_ts * 1000) : '<span class="bos">bilinmiyor</span>'}</td>
          <td><button class="ikincil" onclick="guvSuz('${kacir(d.ip)}')"
            >Olayları gör</button></td>
        </tr>`).join('') ||
          '<tr><td colspan="6" class="bos">Blok kaydı yok</td></tr>'}</tbody>
      </table>
    </div>

    <div class="pano">
      <h3>Şu an etkin bloklar</h3>
      <p class="aciklama">Uygulama katmanı sayaçları bellekte tutulur;
        merkez servisi yeniden başlatıldığında bu liste boşalır. Kalıcı
        kayıt için yukarıdaki blok geçmişine bakınız.</p>
      <table>
        <thead><tr><th>Tür</th><th>Hedef</th><th>Kalan</th><th></th></tr></thead>
        <tbody>${bloklar ||
          '<tr><td colspan="4" class="bos">Etkin blok yok</td></tr>'}</tbody>
      </table>
    </div>

    <div class="pano">
      <h3>Ağ katmanı yasakları (fail2ban)</h3>
      <!-- FAZ18-IS9-F2BNOT: gecmis kaliciligi asimetrisi bildirilir. -->
      <p class="aciklama">Etkin yasaklar güvenlik duvarından canlı
        okunur. Geçmiş kayıtları fail2ban günlüğünden gelir ve günlük
        döndürüldüğünde <em>fail2ban tarafından boşaltılır</em>
        (dondurulmuş kopya bırakmaz); bu nedenle ağ katmanı geçmişi
        uygulama katmanı geçmişi kadar uzun saklanmaz. Boş liste
        &quot;hiç yasak olmadı&quot; anlamına gelmez.</p>
      ${f2b.okunabilir === false ? `<div class="bos">
        fail2ban günlüğü okunamadı (${kacir(f2b.kaynak || '—')}).
        Erişim izni (ACL) günlük döndürmeden sonra düşmüş olabilir.
      </div>` : `
      <table>
        <thead><tr><th>IP</th><th>Hapis</th><th>Durum</th><th>Zaman</th></tr></thead>
        <tbody>${[].concat(
          (f2b.etkin || []).map((d) => `<tr>
            <td class="tek-satir"><code class="kod">${kacir(d.ip)}</code></td>
            <td>${kacir(d.hapis)}</td>
            <td>${rozet('Yasaklı', 'kirmizi')}</td>
            <td class="tek-satir">${d.ts ? tarih(d.ts * 1000) : '—'}</td></tr>`),
          (f2b.cozulmus || []).slice(0, 20).map((d) => `<tr>
            <td class="tek-satir"><code class="kod">${kacir(d.ip)}</code></td>
            <td>${kacir(d.hapis)}</td>
            <td>${rozet('Çözüldü', 'gri')}</td>
            <td class="tek-satir">${d.ts ? tarih(d.ts * 1000) : '—'}</td></tr>`)
        ).join('') ||
          '<tr><td colspan="4" class="bos">Ağ yasağı kaydı yok</td></tr>'}</tbody>
      </table>`}
    </div>

    <div class="pano">
      <h3>Canlı olay akışı</h3>
      <p class="aciklama">Son ${sayi((ol.olaylar || []).length)} olay
        (bellekten, en yeni önce). ${s.ip ?
        `Süzgeç: <code class="kod">${kacir(s.ip)}</code>
         <button class="ikincil" onclick="guvSuz('')">Süzgeci kaldır</button>`
        : ''}</p>
      <table>
        <thead><tr><th>Zaman</th><th>Tür</th><th>IP</th><th>Hesap</th>
          <th>Uç</th><th>Ek</th></tr></thead>
        <tbody>${(ol.olaylar || []).map((d) => `<tr>
          <td class="tek-satir">${d.ts ? tarih(d.ts * 1000) : '—'}</td>
          <td>${guvTur(d.tur)}</td>
          <td class="tek-satir"><code class="kod">${kacir(d.ip || '—')}</code></td>
          <td>${kacir(d.hesap || '—')}</td>
          <td><small>${kacir(d.uc || '—')}</small></td>
          <td><small>${kacir(d.ek || '')}</small></td>
        </tr>`).join('') ||
          '<tr><td colspan="6" class="bos">Olay kaydı yok</td></tr>'}</tbody>
      </table>
    </div>

    <div class="pano">
      <h3>Eşik sözleşmesi</h3>
      <table>
        <thead><tr><th>Sayaç</th><th>Eşik</th><th>Ceza</th></tr></thead>
        <tbody>
          <tr><td>IP (kısa pencere)</td><td>${kacir(esikMetni('ip_kisa'))}</td>
            <td>${(esik.ip_kisa || [])[2] ? sure(esik.ip_kisa[2]) : '—'}</td></tr>
          <tr><td>IP (uzun pencere)</td><td>${kacir(esikMetni('ip_uzun'))}</td>
            <td>${(esik.ip_uzun || [])[2] ? sure(esik.ip_uzun[2]) : '—'}</td></tr>
          <tr><td>Hesap</td><td>${kacir(esikMetni('hesap'))}</td>
            <td>${(esik.hesap || [])[2] ? sure(esik.hesap[2]) : '—'}</td></tr>
        </tbody>
      </table>
      <p class="aciklama">Yerel adresler (127.0.0.1 ve özel ağ
        aralıkları) kilitlenmez; kapalı devre kurulumda köprü ve GCS
        vekili kendi sunucusundan kilitlenemez.</p>
    </div>

    <div class="pano">
      <h3>Aralık</h3>
      ${[1, 7, 30, 90].map((g) => `<button class="${
        Number(s.gun) === g ? '' : 'ikincil'}"
        onclick="guvGun(${g})">${g} gün</button>`).join(' ')}
    </div>`;

  guvCizim('#guv-cizim', gec.gunler || []);
}

window.guvGun = (g) => { DURUM.guvenlik.gun = g; sayfaGuvenlik(); };

/* ================================================================ *
 * GUNLUKLER                                 FAZ18-IS10-GUNLUK-PANEL *
 *                                                                  *
 * Dort kaynak: uygulama (merkez), app (GCS), sistem (journald),     *
 * ag (fail2ban). Veritabani gunlugu kapsam disi ve bunu YAZAR.      *
 *                                                                  *
 * ZAMAN SUZGECI ASIMETRISI: uygulama gunluklerinde satirlar tarih   *
 * damgasi tasimiyor (olculdu: 12074 satirda 4). Zaman secicisi bu   *
 * kaynaklarda GIZLENIR; calismayan denetim gostermek yanlis guven   *
 * verir. Kaynak yetenegini `zaman_suzulebilir` ile kendisi bildirir.*
 * ================================================================ */
const GUN_DUZEY_RENK = {
  hata: 'kirmizi', uyari: 'sari', guvenlik: 'mor', bilgi: 'gri'
};
const GUN_DUZEY_AD = {
  hata: 'Hata', uyari: 'Uyarı', guvenlik: 'Güvenlik', bilgi: 'Bilgi'
};

async function sayfaGunluk(par) {
  DURUM.gunluk = Object.assign(
    { kaynak: 'uygulama', duzey: '', ara: '', birim: '', saat: 0,
      en_cok: 200 }, DURUM.gunluk, par);
  const s = DURUM.gunluk;

  let kay = {};
  let r = {};
  try {
    kay = await cagir('/api/admin/gunluk/kaynaklar');
    r = await cagir('/api/admin/gunluk?' + new URLSearchParams({
      kaynak: s.kaynak, duzey: s.duzey, ara: s.ara,
      birim: s.birim, saat: s.saat, en_cok: s.en_cok
    }));
  } catch (e) {
    el('#icerik').innerHTML = `
      <h2>Günlükler</h2>
      <div class="pano"><div class="bos">Günlük verisi okunamadı:
        ${kacir(e.message || e)}</div></div>`;
    return;
  }

  const kaynaklar = kay.kaynaklar || [];
  const vt = kay.veritabani || {};
  const aktif = kaynaklar.find((x) => x.kod === s.kaynak) || {};
  const zamanVar = !!r.zaman_suzulebilir;
  const kayitlar = r.kayitlar || [];
  const dag = r.duzey_dagilim || [];

  /* Kaynak secici: her kaynak kendi dosya sayisini gosterir; boylece
   * yonetici dondurulen dosyalarin da tarandigini gorur. */
  const kaynakDugme = kaynaklar.map((x) => `
    <button class="${x.kod === s.kaynak ? '' : 'ikincil'}"
      onclick="gunKaynak('${x.kod}')">
      ${kacir(x.ad)}${x.dosya_sayisi ?
        ` <span class="ek">(${x.dosya_sayisi})</span>` : ''}
    </button>`).join(' ');

  const duzeyDugme = ['', 'hata', 'uyari', 'guvenlik', 'bilgi'].map((d) => `
    <button class="${d === s.duzey ? '' : 'ikincil'}"
      onclick="gunDuzey('${d}')">${d ? GUN_DUZEY_AD[d] : 'Tümü'}</button>`
  ).join(' ');

  const saatDugme = [0, 1, 6, 24, 168].map((h) => `
    <button class="${Number(s.saat) === h ? '' : 'ikincil'}"
      onclick="gunSaat(${h})">${h === 0 ? 'Sınırsız' :
        (h < 24 ? h + ' saat' : (h / 24) + ' gün')}</button>`).join(' ');

  /* FAZ18-IS10-SINIF — suzgec satiri `arac-cubugu` sinifini
   * kullanir: panelin MEVCUT ve TANIMLI suzgec kalibi budur.
   * Ilk yazimda `satir-esnek` ve `alan` kullanilmisti; ikisi de
   * stil.css'te TANIMSIZ oldugu icin alanlar alt alta duserdi
   * (tanimsiz sinif hata vermez, sessizce etkisizdir). Yeni CSS
   * kurali EKLENMEDI: mevcut kalip tum panelde tutarli. */
  const birimSecici = (r.birimler && r.birimler.length) ? `
    <select onchange="gunBirim(this.value)" title="Servis birimi">
      <option value="">Tüm birimler</option>
      ${r.birimler.map((b) => `<option value="${kacir(b.birim)}"
        ${b.birim === s.birim ? 'selected' : ''}>${kacir(
          b.birim.replace(/\.service$/, ''))} (${sayi(b.sayi)})</option>`
      ).join('')}
    </select>` : '';

  el('#icerik').innerHTML = `
    <h2>Günlükler</h2>

    <div class="pano">
      <h3>Kaynak</h3>
      ${kaynakDugme}
      <p class="aciklama">Parantez içindeki sayı, döndürülmüş
        (arşivlenmiş) dosyalar dahil taranan dosya sayısıdır.
        ${vt.kapsam_disi ? `Veritabanı günlüğü bu sürümde kapsam
        dışıdır: ${kacir(vt.durum_aciklama || '')}` : ''}</p>
    </div>

    <div class="pano">
      <h3>Süzgeçler</h3>
      <div class="arac-cubugu">
        <input id="gun-ara" value="${kacir(s.ara)}"
          placeholder="Metin ara: ROLE, Traceback, 85.100"
          onkeydown="if(event.key==='Enter')gunAra(this.value)">
        ${birimSecici}
        <select onchange="gunEnCok(this.value)"
          title="Getirilecek kayıt sayısı">
          ${[100, 200, 500].map((n) => `<option value="${n}"
            ${Number(s.en_cok) === n ? 'selected' : ''}
            >${n} satır</option>`).join('')}
        </select>
      </div>
      <div style="margin-top:10px">${duzeyDugme}</div>
      ${zamanVar ? `<div style="margin-top:10px">${saatDugme}</div>` : `
      <p class="aciklama">Bu günlükte satırlar tarih damgası
        taşımadığı için zaman aralığı süzgeci uygulanamaz; kayıtlar
        kronolojik sırada (en yeni üstte) listelenir. Zaman süzgeci
        yalnızca işletim sistemi günlüğünde etkindir.</p>`}
      ${r.kapsam_degisti ? `<p class="aciklama">
        ${kacir(r.kapsam_notu || '')}</p>` : ''}
    </div>

    ${dag.length ? `<div class="pano">
      <h3>Düzey dağılımı</h3>
      <p class="aciklama">Aşağıdaki sayılar getirilen son
        ${sayi(r.dagilim_kapsam || 0)} kayıt içindir; günlüğün
        tamamının özeti değildir.</p>
      <div>${dag.map((d) => `${rozet(
        GUN_DUZEY_AD[d.duzey] + ': ' + sayi(d.sayi),
        GUN_DUZEY_RENK[d.duzey])}`).join(' ')}</div>
    </div>` : ''}

    <div class="pano">
      <h3>Kayıtlar</h3>
      <p class="aciklama">Kaynak: <code class="kod">${
        kacir(r.kaynak || '—')}</code> ·
        taranan ${sayi(r.taranan_satir || 0)} satır ·
        listelenen ${sayi(kayitlar.length)} kayıt${
        r.okunabilir === false ? ' · <strong>okunamadı</strong>' : ''}.
        ${kay.guvenlik_notu ? kacir(kay.guvenlik_notu) : ''}</p>
      <table>
        <thead><tr><th>Zaman</th><th>Düzey</th>${
          aktif.kod === 'sistem' ? '<th>Birim</th>' : ''}
          <th>Kayıt</th></tr></thead>
        <tbody>${kayitlar.map((x) => `<tr>
          <td class="tek-satir">${x.ts ? tarih(x.ts * 1000, true) :
            '<span class="ek">—</span>'}</td>
          <td>${rozet(GUN_DUZEY_AD[x.duzey] || x.duzey,
                      GUN_DUZEY_RENK[x.duzey] || 'gri')}</td>
          ${aktif.kod === 'sistem' ? `<td class="tek-satir">${
            kacir((x.birim || '—').replace(/\.service$/, ''))}</td>` : ''}
          <td><code class="kod">${kacir(x.metin)}</code></td>
        </tr>`).join('') || `<tr><td colspan="${
          aktif.kod === 'sistem' ? 4 : 3}" class="bos">
          Kayıt bulunamadı${s.ara || s.duzey ?
            ' (süzgeçleri gevşetmeyi deneyin)' : ''}</td></tr>`}</tbody>
      </table>
    </div>`;
}

window.gunKaynak = (k) => {
  /* Kaynak degisince BIRIM suzgeci sifirlanir: birim adlari yalniz
   * journald kaynaginda anlamlidir, tasinirsa hicbir kayit
   * eslesmez ve kullanici bos liste sebebini anlamaz. */
  DURUM.gunluk.kaynak = k;
  DURUM.gunluk.birim = '';
  sayfaGunluk();
};
window.gunDuzey = (d) => { DURUM.gunluk.duzey = d || ''; sayfaGunluk(); };
window.gunAra = (v) => { DURUM.gunluk.ara = v || ''; sayfaGunluk(); };
window.gunBirim = (v) => { DURUM.gunluk.birim = v || ''; sayfaGunluk(); };
window.gunSaat = (h) => { DURUM.gunluk.saat = Number(h) || 0; sayfaGunluk(); };
window.gunEnCok = (n) => {
  DURUM.gunluk.en_cok = Number(n) || 200; sayfaGunluk();
};
window.guvSuz = (ip) => { DURUM.guvenlik.ip = ip || ''; sayfaGuvenlik(); };
window.guvCoz = async (hedef, tur) => {
  const govde = (tur === 'hesap') ? { hesap: hedef } : { ip: hedef };
  try {
    await cagir('/api/admin/guvenlik/coz', { method: 'POST', body: govde });
    bildir('Blok çözüldü: ' + hedef, 'iyi');
    sayfaGuvenlik();
  } catch (e) {
    bildir('Çözülemedi: ' + (e.message || e), 'hata');
  }
};

/* ================================================================ DENETİM */
async function sayfaDenetim(par) {
  DURUM.denetim = Object.assign({ sayfa: 1, boyut: 100 }, DURUM.denetim, par);
  const s = DURUM.denetim;
  const y = await cagir('/api/admin/denetim?' + new URLSearchParams({
    sayfa: s.sayfa, boyut: s.boyut
  }));
  el('#icerik').innerHTML = `
    <h2>Denetim İzi</h2>
    <p class="aciklama">Sistem yöneticisi işlemlerinin değiştirilemez kaydı.</p>
    <div class="pano" style="margin-top:0">
      <table>
        <thead><tr><th>Zaman</th><th>Yönetici</th><th>Eylem</th><th>Hedef</th>
          <th>IP</th><th>Ayrıntı</th></tr></thead>
        <tbody>${(y.kayitlar || []).map((d) => `<tr>
          <td class="tek-satir">${tarih(d.ts)}</td>
          <td>${kacir(d.yonetici_eposta || '—')}</td>
          <td>${rozet(d.eylem, d.eylem.includes('sil') ? 'kirmizi' :
            (d.eylem.includes('ekle') ? 'yesil' : 'mavi'))}</td>
          <td>${kacir(d.hedef_tur || '—')}${d.hedef_id ?
            ' #' + kacir(d.hedef_id) : ''}</td>
          <td>${kacir(d.ip || '—')}</td>
          <td><code class="kod">${kacir(JSON.stringify(d.ayrinti || {}))}</code></td>
        </tr>`).join('') ||
          '<tr><td colspan="6" class="bos">Denetim kaydı yok</td></tr>'}</tbody>
      </table>
      ${sayfalamaHTML(y.toplam, y.sayfa, y.boyut, 'denetimSayfa')}
    </div>`;
}

window.denetimSayfa = (n) => { DURUM.denetim.sayfa = n; sayfaDenetim(); };

/* ================================================================ DESTEK */
/* Türkbey destek personeli görünümü.
 *
 * `yetki="destek"` uçlarını kullanır: sistem yöneticisi VE destek
 * personeli erişir; rol denetimi taşıma katmanındadır.
 *
 * DAHİLİ NOT: `ic_not=true` mesajlar YALNIZ bu panelde görünür;
 * kullanıcı ucu bunları süzer (sınavla kanıtlandı).
 *
 * Ek gönderiminde `data:` öneki KIRPILIR — uç çıplak base64 bekler.
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
const DESTEK_MODUL_AD = {
  app: 'GCS Uygulaması', kopru: 'Köprü Yazılımı',
  merkez: 'Merkez Uygulama', radar: 'Radar Modülü',
  gccdual: 'Yer Kontrol İstasyonu Dual', dji: 'DJI Köprüsü (Android)',
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
let DESTEK_EKLER = [];

function destekModulAd(a) {
  return DESTEK_MODUL_AD[a] || a || '—';
}

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

function destekEkAlanHTML(id) {
  return `
    <div class="ek-alan">
      <input id="${id}" type="file" multiple accept="${DESTEK_EK_KABUL}"
             style="display:none">
      <button type="button" class="ikincil kucuk"
              onclick="document.getElementById('${id}').click()">
        Dosya ekle</button>
      <span class="aciklama">en fazla ${DESTEK_EK_ADET} dosya, her biri 8 MB</span>
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
    o.target.value = '';
  };
}

async function sayfaDestek(par) {
  DURUM.destek = Object.assign(
    { durum: '', modul: '', oncelik: '', atanan: '' }, DURUM.destek, par);
  const s = DURUM.destek;
  const sorgu = {};
  ['durum', 'modul', 'oncelik', 'atanan'].forEach((a) => {
    if (s[a]) sorgu[a] = s[a];
  });
  const [y, p] = await Promise.all([
    cagir('/api/destek/personel/talepler?' + new URLSearchParams(sorgu)),
    cagir('/api/destek/personel/liste')
  ]);
  const talepler = y.talepler || [];
  const sayim = y.sayim || {};
  const personel = p.personel || [];
  DURUM.destekPersonel = personel;

  const sayac = (d) => `
    <button class="destek-sayac${s.durum === d ? ' etkin' : ''}"
            onclick="destekDurumSuz('${d}')">
      <span class="destek-sayac-deger">${sayi(sayim[d] || 0)}</span>
      <span class="destek-sayac-etiket">${DESTEK_DURUM_AD[d]}</span>
    </button>`;

  el('#icerik').innerHTML = `
    <h2>Destek Talepleri</h2>
    <p class="aciklama">Müşterilerden ve bireysel kullanıcılardan gelen
      destek talepleri. Dahili notlar yalnızca bu panelde görünür,
      talebi açan kullanıcıya gösterilmez.</p>
    <div class="destek-sayaclar">
      <button class="destek-sayac${!s.durum ? ' etkin' : ''}"
              onclick="destekDurumSuz('')">
        <span class="destek-sayac-deger">${sayi(
          Object.values(sayim).reduce((a, b) => a + b, 0))}</span>
        <span class="destek-sayac-etiket">Tümü</span>
      </button>
      ${Object.keys(DESTEK_DURUM_AD).map(sayac).join('')}
    </div>
    <div class="arac-cubugu">
      <select id="destek-modul-suzgec">
        <option value="">Tüm modüller</option>
        ${Object.keys(DESTEK_MODUL_AD).map((m) =>
          `<option value="${m}"${s.modul === m ? ' selected' : ''}>${
            DESTEK_MODUL_AD[m]}</option>`).join('')}
      </select>
      <select id="destek-oncelik-suzgec">
        <option value="">Tüm öncelikler</option>
        ${Object.keys(DESTEK_ONCELIK_AD).map((o) =>
          `<option value="${o}"${s.oncelik === o ? ' selected' : ''}>${
            DESTEK_ONCELIK_AD[o]}</option>`).join('')}
      </select>
      <select id="destek-atanan-suzgec">
        <option value="">Tüm atamalar</option>
        <option value="bos"${s.atanan === 'bos' ? ' selected' : ''}>Atanmamış</option>
        ${personel.map((k) => `<option value="${k.yonetici_id}"${
          String(s.atanan) === String(k.yonetici_id) ? ' selected' : ''}>${
          kacir(k.ad_soyad || k.eposta)}</option>`).join('')}
      </select>
    </div>
    <div class="pano" style="margin-top:0">
      <table>
        <thead><tr><th>Talep No</th><th>Müşteri</th><th>Modül</th>
          <th>Konu</th><th>Öncelik</th><th>Durum</th><th>Atanan</th>
          <th>Güncelleme</th><th></th></tr></thead>
        <tbody>${talepler.map((t) => `<tr>
          <td class="tek-satir"><code class="kod">${kacir(t.ticket_no)}</code></td>
          <td>${kacir(t.firma_unvan || '—')}${t.firma_tur === 'bireysel' ?
            ' ' + rozet('bireysel', 'mor') : ''}
            <div class="aciklama">${kacir(t.acan_eposta || '')}</div></td>
          <td>${kacir(destekModulAd(t.modul))}</td>
          <td>${kacir(t.konu)}</td>
          <td>${rozet(DESTEK_ONCELIK_AD[t.oncelik] || t.oncelik,
                      DESTEK_ONCELIK_RENK[t.oncelik] || 'gri')}</td>
          <td>${rozet(DESTEK_DURUM_AD[t.durum] || t.durum,
                      DESTEK_DURUM_RENK[t.durum] || 'gri')}</td>
          <td>${kacir(t.atanan_ad || '—')}</td>
          <td class="tek-satir">${tarih(t.guncel_ts)}</td>
          <td class="sag"><button class="ikincil kucuk"
                onclick="destekAc(${t.ticket_id})">Aç</button></td>
        </tr>`).join('') ||
          '<tr><td colspan="9" class="bos">Bu süzgeçle talep bulunamadı</td></tr>'}
        </tbody>
      </table>
    </div>`;

  el('#destek-modul-suzgec').onchange = (o) => {
    DURUM.destek.modul = o.target.value; sayfaDestek();
  };
  el('#destek-oncelik-suzgec').onchange = (o) => {
    DURUM.destek.oncelik = o.target.value; sayfaDestek();
  };
  el('#destek-atanan-suzgec').onchange = (o) => {
    DURUM.destek.atanan = o.target.value; sayfaDestek();
  };
}
window.destekDurumSuz = (d) => { DURUM.destek.durum = d; sayfaDestek(); };

window.destekAc = async (tid) => {
  const y = await cagir('/api/destek/personel/talep/' + tid);
  const t = y.talep || {};
  const mesajlar = y.mesajlar || [];
  const ekler = y.ekler || [];
  const personel = DURUM.destekPersonel || [];
  const ekleriMesaja = (mid) => ekler.filter((e) => e.mesaj_id === mid);

  pencereAc(`${t.ticket_no} — ${t.konu}`, `
    <dl class="ozet">
      <dt>Müşteri</dt><dd>${kacir(t.firma_unvan || '—')}${
        t.firma_tur === 'bireysel' ? ' ' + rozet('bireysel', 'mor') : ''}</dd>
      <dt>Açan</dt><dd>${kacir(t.acan_ad || '')}
        <span class="aciklama">${kacir(t.acan_eposta || '')}</span></dd>
      <dt>Modül</dt><dd>${kacir(destekModulAd(t.modul))}</dd>
      <dt>Öncelik</dt><dd>${rozet(DESTEK_ONCELIK_AD[t.oncelik] || t.oncelik,
        DESTEK_ONCELIK_RENK[t.oncelik] || 'gri')}</dd>
      <dt>Açılış</dt><dd>${tarih(t.olusma_ts)}</dd>
    </dl>
    <div class="destek-denetim">
      <div>
        <label for="d-durum">Durum</label>
        <select id="d-durum">
          ${Object.keys(DESTEK_DURUM_AD).map((d) =>
            `<option value="${d}"${t.durum === d ? ' selected' : ''}>${
              DESTEK_DURUM_AD[d]}</option>`).join('')}
        </select>
      </div>
      <div>
        <label for="d-atanan">Atanan personel</label>
        <select id="d-atanan">
          <option value="">— atanmamış —</option>
          ${personel.map((k) => `<option value="${k.yonetici_id}"${
            String(t.atanan_yonetici_id) === String(k.yonetici_id) ?
            ' selected' : ''}>${kacir(k.ad_soyad || k.eposta)}</option>`).join('')}
        </select>
      </div>
    </div>
    <div class="yazisma">
      ${mesajlar.map((m) => {
        const me = ekleriMesaja(m.mesaj_id);
        const sinif = m.ic_not ? 'ic-not' :
          (m.yazan_tur === 'kullanici' ? 'musteri' : 'benim');
        return `<div class="mesaj ${sinif}">
          <div class="mesaj-bas">
            <strong>${kacir(m.yazan_ad || '—')}</strong>
            ${m.ic_not ? rozet('dahili not', 'sari') : ''}
            <span class="aciklama">${tarih(m.olusma_ts)}</span>
          </div>
          <div class="mesaj-govde">${kacir(m.govde).replace(/\n/g, '<br>')}</div>
          ${me.length ? `<div class="mesaj-ekler">${me.map((e) =>
            `<a class="ek-bag" href="/api/destek/personel/ek/${e.ek_id}"
                target="_blank" rel="noopener">⇩ ${kacir(e.dosya_ad)}
              <span class="ek-boyut">${(e.boyut / 1024).toFixed(0)} KB</span></a>`
          ).join('')}</div>` : ''}
        </div>`;
      }).join('')}
    </div>
    <label for="d-yanit">Yanıt / not</label>
    <textarea id="d-yanit" rows="4"
              placeholder="Müşteriye gönderilecek yanıtı yazın"></textarea>
    <label class="onay-satir">
      <input type="checkbox" id="d-ic-not">
      <span>Dahili not — <strong>müşteriye gösterilmez</strong>,
        yalnızca destek ekibi görür</span>
    </label>
    ${destekEkAlanHTML('d-yanit-ek')}
    <div class="hata" id="d-yanit-hata"></div>`, [
    { metin: 'Kapat', sinif: 'ikincil', tik: pencereKapat },
    { metin: 'Durum/Atama Kaydet', sinif: 'ikincil',
      tik: () => destekDenetimKaydet(tid) },
    { metin: 'Gönder', tik: () => destekPersonelYanit(tid) }
  ], true);

  destekEkAlanBagla('d-yanit-ek');
  const yz = el('.yazisma');
  if (yz) yz.scrollTop = yz.scrollHeight;
};

async function destekPersonelYanit(tid) {
  const hata = el('#d-yanit-hata');
  const govde = el('#d-yanit').value.trim();
  if (!govde) { hata.textContent = 'Mesaj boş olamaz.'; return; }
  const icNot = el('#d-ic-not').checked;
  const dugme = els('#pencere-alt button').pop();
  dugme.disabled = true;
  hata.textContent = '';
  try {
    const y = await cagir(`/api/destek/personel/talep/${tid}/mesaj`, {
      method: 'POST',
      body: {
        govde, ic_not: icNot,
        ekler: DESTEK_EKLER.map((e) => ({ ad: e.ad, mime: e.mime, veri: e.veri }))
      }
    });
    if (y.ek_uyari) bildir(y.ek_uyari, 'uyari');
    DESTEK_EKLER = [];
    bildir(icNot ? 'Dahili not eklendi.' : 'Yanıt gönderildi.', 'basari');
    await window.destekAc(tid);
    await sayfaDestek();
  } catch (e) {
    hata.textContent = e.message;
  } finally {
    dugme.disabled = false;
  }
}

async function destekDenetimKaydet(tid) {
  const durum = el('#d-durum').value;
  const atanan = el('#d-atanan').value;
  try {
    await cagir(`/api/destek/personel/talep/${tid}/durum`, {
      method: 'POST', body: { durum }
    });
    await cagir(`/api/destek/personel/talep/${tid}/ata`, {
      method: 'POST',
      body: { yonetici_id: atanan ? Number(atanan) : null }
    });
    bildir('Talep güncellendi.', 'basari');
    await window.destekAc(tid);
    await sayfaDestek();
  } catch (e) {
    bildir(e.message, 'hata');
  }
}

/* ============================================================ PERSONEL
 * Turkbey ic personeli yonetimi (`sistem_yoneticileri` tablosu).
 *
 * FIRMA KULLANICILARI ILE KARISTIRILMAMALI: `#kullanicilar` bolumu
 * musteri tarafi kullanicilarini (`kullanicilar` tablosu) yonetir.
 * Bu bolum Turkbey personelini yonetir ve YALNIZ `sistem_yonetici`
 * rolune aciktir -- `destek_personel` ve `gozlemci` uctan 403 alir.
 *
 * Roller:
 *   sistem_yonetici  -- tam yetki, personel yonetebilir
 *   destek_personel  -- YALNIZ destek talepleri
 *   gozlemci         -- salt okuma
 */
const ROL_AD = {
  sistem_yonetici: 'Sistem Yöneticisi',
  destek_personel: 'Destek Personeli',
  gozlemci: 'Gözlemci'
};
const ROL_RENK = {
  sistem_yonetici: 'mor',
  destek_personel: 'mavi',
  gozlemci: 'gri'
};

async function sayfaPersonel() {
  /* Rol kapisi arayuzde ONCE gosterilir: kullanici 403 gormeden
     neden erisemedigini anlar.  Uc de ayrica denetliyor. */
  if (BEN.rol !== 'sistem_yonetici') {
    el('#icerik').innerHTML = `
      <h2>Personel</h2>
      <p class="aciklama">Bu bölüm yalnızca <strong>sistem
      yöneticisi</strong> yetkisiyle görüntülenebilir. Rolünüz:
      <strong>${kacir(ROL_AD[BEN.rol] || BEN.rol)}</strong>.</p>`;
    return;
  }

  const y = await cagir('/api/admin/yoneticiler');
  const p = y.personel || [];
  const s = y.sayim || {};
  const ben = y.ben;
  DURUM.personel = p;
  DURUM.personelBen = ben;

  const k = (etiket, deger, ek) => `
    <div class="kart">
      <div class="etiket">${etiket}</div>
      <div class="deger">${deger}</div>
      ${ek ? `<div class="ek">${ek}</div>` : ''}
    </div>`;

  el('#icerik').innerHTML = `
    <h2>Personel</h2>
    <p class="aciklama">Türkbey iç personeli. <strong>Destek
    Personeli</strong> rolü yalnızca destek taleplerini yönetir;
    müşteri, abonelik ve altyapı bölümlerine erişemez. Müşteri tarafı
    kullanıcıları için <a href="#kullanicilar">Kullanıcılar</a>
    bölümünü kullanın.</p>

    <div class="kart-izgara">
      ${k('Toplam Personel', sayi(s.toplam || 0))}
      ${k('Sistem Yöneticisi', sayi(s.sistem_yonetici || 0))}
      ${k('Destek Personeli', sayi(s.destek_personel || 0))}
      ${k('Askıda', sayi(s.askida || 0))}
    </div>

    <div class="arac-cubugu">
      <div class="bosluk"></div>
      <button class="kucuk" id="p-yeni">+ Personel Ekle</button>
    </div>

    <div class="pano" style="margin-top:0">
      <table>
        <thead><tr>
          <th>Ad Soyad</th><th>E-posta</th><th>Unvan</th>
          <th>Rol</th><th>Durum</th><th>E-posta</th>
          <th>Son Giriş</th><th class="sag">İşlem</th>
        </tr></thead>
        <tbody>${p.length ? p.map((x) => {
          const benim = x.yonetici_id === ben;
          return `<tr>
            <td>${kacir(x.ad_soyad)}${benim
              ? ' ' + rozet('siz', 'gri') : ''}</td>
            <td>${kacir(x.eposta)}</td>
            <td>${kacir(x.unvan || '—')}</td>
            <td>${rozet(ROL_AD[x.rol] || x.rol,
                        ROL_RENK[x.rol] || 'gri')}</td>
            <td>${rozet(x.durum === 'etkin' ? 'etkin' : 'askıda',
                        DURUM_RENK[x.durum] || 'gri')}</td>
            <td class="tek-satir">${x.eposta_dogrulandi
              ? rozet('doğrulandı', 'yesil')
              : rozet('bekliyor', 'sari') +
                ` <button class="ikincil kucuk"
                   onclick="personelDogrula(${x.yonetici_id})"
                   title="Doğrulama damgasını elle at">Doğrula</button>`}</td>
            <td class="tek-satir">${x.son_giris_ts
              ? tarih(x.son_giris_ts, true) : '—'}</td>
            <td class="sag tek-satir">
              <button class="ikincil kucuk"
                onclick="personelDuzenle(${x.yonetici_id})">Düzenle</button>
              <button class="ikincil kucuk"
                onclick="personelSifre(${x.yonetici_id})">Şifre</button>
              ${benim ? '' : `<button class="tehlike kucuk"
                onclick="personelSil(${x.yonetici_id})">Sil</button>`}
            </td></tr>`;
        }).join('')
          : '<tr><td colspan="8" class="bos">Personel yok</td></tr>'}
        </tbody>
      </table>
    </div>`;

  el('#p-yeni').onclick = () => personelPencere();
}

function personelPencere() {
  pencereAc('Personel Ekle', `
    <label>Ad Soyad *</label>
    <input id="pAd" maxlength="120" placeholder="Ahmet Yılmaz">
    <label>E-posta *</label>
    <input id="pEposta" type="email" maxlength="200"
           placeholder="ad.soyad@gokkubbetech.com">
    <label>Unvan</label>
    <input id="pUnvan" maxlength="120" placeholder="Destek Uzmanı">
    <label>Rol *</label>
    <select id="pRol">
      <option value="destek_personel">Destek Personeli — yalnız destek
        talepleri</option>
      <option value="gozlemci">Gözlemci — salt okuma</option>
      <option value="sistem_yonetici">Sistem Yöneticisi — tam
        yetki</option>
    </select>
    <label>Şifre *</label>
    <input id="pSifre" type="password" maxlength="200"
           placeholder="En az 8 karakter">
    <p class="aciklama">Personel ilk girişinde e-posta doğrulaması
    yapmak zorundadır. E-posta gönderimi hazır değilse listeden
    <strong>Doğrula</strong> düğmesiyle damgayı elle atabilirsiniz.</p>`,
    [{ metin: 'Ekle', tik: async () => {
      const g = {
        ad_soyad: el('#pAd').value.trim(),
        eposta: el('#pEposta').value.trim().toLowerCase(),
        unvan: el('#pUnvan').value.trim(),
        rol: el('#pRol').value,
        sifre: el('#pSifre').value
      };
      if (!g.ad_soyad) { bildir('Ad soyad zorunlu', 'hata'); return; }
      if (!g.eposta) { bildir('E-posta zorunlu', 'hata'); return; }
      if (!g.sifre) { bildir('Şifre zorunlu', 'hata'); return; }
      try {
        await cagir('/api/admin/yoneticiler',
                    { method: 'POST', body: g });
        pencereKapat();
        bildir('Personel eklendi', 'iyi');
        await sayfaPersonel();
      } catch (e) { bildir(e.message || 'Eklenemedi', 'hata'); }
    } }]);
}

window.personelDuzenle = (yid) => {
  const x = (DURUM.personel || []).find((z) => z.yonetici_id === yid);
  if (!x) return;
  const benim = yid === DURUM.personelBen;
  pencereAc('Personel Düzenle', `
    <label>Ad Soyad</label>
    <input id="pAd" maxlength="120" value="${kacir(x.ad_soyad)}">
    <label>Unvan</label>
    <input id="pUnvan" maxlength="120" value="${kacir(x.unvan || '')}">
    <label>Rol</label>
    <select id="pRol"${benim ? ' disabled' : ''}>
      ${['destek_personel', 'gozlemci', 'sistem_yonetici'].map((r) =>
        `<option value="${r}"${x.rol === r ? ' selected' : ''}>${
          ROL_AD[r]}</option>`).join('')}
    </select>
    <label>Durum</label>
    <select id="pDurum"${benim ? ' disabled' : ''}>
      <option value="etkin"${x.durum === 'etkin' ? ' selected' : ''}>
        Etkin</option>
      <option value="askida"${x.durum === 'askida' ? ' selected' : ''}>
        Askıda</option>
    </select>
    <p class="aciklama">E-posta adresi değiştirilemez.${benim
      ? ' <strong>Kendi rolünüzü ve durumunuzu değiştiremezsiniz</strong>' +
        ' — kendinizi yetkisiz bırakma riski engellenmiştir.' : ''}</p>`,
    [{ metin: 'Kaydet', tik: async () => {
      const g = {
        ad_soyad: el('#pAd').value.trim(),
        unvan: el('#pUnvan').value.trim()
      };
      /* Kendi kaydinda rol/durum GONDERILMEZ: uc 403 doner ve
         ad/unvan degisikligi de bosa gider. */
      if (!benim) {
        g.rol = el('#pRol').value;
        g.durum = el('#pDurum').value;
      }
      try {
        await cagir('/api/admin/yoneticiler/' + yid,
                    { method: 'PUT', body: g });
        pencereKapat();
        bildir('Güncellendi', 'iyi');
        await sayfaPersonel();
      } catch (e) { bildir(e.message || 'Güncellenemedi', 'hata'); }
    } }]);
};

window.personelSifre = (yid) => {
  const x = (DURUM.personel || []).find((z) => z.yonetici_id === yid);
  if (!x) return;
  pencereAc('Şifre Sıfırla', `
    <p class="aciklama"><strong>${kacir(x.ad_soyad)}</strong>
    (${kacir(x.eposta)}) için yeni şifre belirleyin. Mevcut şifre
    sorulmaz.</p>
    <label>Yeni Şifre *</label>
    <input id="pSifre" type="password" maxlength="200"
           placeholder="En az 8 karakter">`,
    [{ metin: 'Sıfırla', tik: async () => {
      const sifre = el('#pSifre').value;
      if (!sifre) { bildir('Şifre zorunlu', 'hata'); return; }
      try {
        await cagir('/api/admin/yoneticiler/' + yid + '/sifre',
                    { method: 'POST', body: { sifre } });
        pencereKapat();
        bildir('Şifre sıfırlandı', 'iyi');
      } catch (e) { bildir(e.message || 'Sıfırlanamadı', 'hata'); }
    } }]);
};

window.personelDogrula = async (yid) => {
  try {
    await cagir('/api/admin/yoneticiler/' + yid + '/dogrula',
                { method: 'POST', body: {} });
    bildir('E-posta doğrulama damgası atıldı', 'iyi');
    await sayfaPersonel();
  } catch (e) { bildir(e.message || 'Damga atılamadı', 'hata'); }
};

window.personelSil = (yid) => {
  const x = (DURUM.personel || []).find((z) => z.yonetici_id === yid);
  if (!x) return;
  pencereAc('Personel Sil', `
    <p><strong>${kacir(x.ad_soyad)}</strong> (${kacir(x.eposta)})
    kalıcı olarak silinecek.</p>
    <p class="aciklama">Bu personele atanmış destek talepleri
    <strong>silinmez</strong>; yalnızca ataması boşa çıkar ve başka
    personele atanabilir. Son etkin sistem yöneticisi silinemez.</p>`,
    [{ metin: 'Sil', sinif: 'tehlike', tik: async () => {
      try {
        await cagir('/api/admin/yoneticiler/' + yid,
                    { method: 'DELETE' });
        pencereKapat();
        bildir('Personel silindi', 'iyi');
        await sayfaPersonel();
      } catch (e) { bildir(e.message || 'Silinemedi', 'hata'); }
    } }]);
};

/* ================================================================ AÇILIŞ */
(async function acilis() {
  // FAZ18-IS12-ACILIS-TESHIS
  // ONCEKI KUSUR: tek `catch` iki AYRI durumu ayni sonuca goturuyordu:
  //   (a) oturum yok/dolmus  -> giris ekrani  (DOGRU davranis)
  //   (b) `kabukAc()` icinde calisma zamani hatasi -> giris ekrani
  // (b) durumunda yonetici gecerli oturumla gelir, panelde teknik hata
  // olur ve kullanici "oturumum dustu" sanip tekrar giris yapar; ayni
  // hata tekrarlanir (sonsuz dongu) ve gercek neden HIC bildirilmez.
  // Artik yetki hatasi (401/403) sessiz kalir, DIGER hatalar konsola
  // tam yigin iziyle yazilir ve kullaniciya "teknik hata" olarak
  // gorunur bildirilir.
  let asama = 'oturum';
  try {
    const y = await cagir('/api/admin/ben');
    BEN = y.yonetici;
    asama = 'kabuk';
    kabukAc();
  } catch (e) {
    const yetkiHatasi = (e && (e.durum === 401 || e.durum === 403));
    el('#giris-katman').style.display = 'flex';
    if (!yetkiHatasi) {
      // Teknik hata: yigin izi KAYBEDILMEZ.
      console.error('[ACILIS] asama=' + asama + ' teknik hata:', e);
      try {
        const k = el('#giris-hata');
        if (k) {
          k.textContent = 'Teknik hata (' + asama + '): ' +
            ((e && e.message) || 'bilinmeyen') +
            ' — oturum sorunu DEGIL, ayrinti icin tarayici konsolu.';
          k.style.display = 'block';
        } else {
          bildir('Teknik hata: ' + ((e && e.message) || 'bilinmeyen'),
                 'kotu');
        }
      } catch (i) { /* bildirim katmani da yoksa konsol yeterli */ }
    }
  }
})();
