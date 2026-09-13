// ===============================================================
// GOKTUNGU GCS - QR kod ureticisi (v2.4.42)
// ---------------------------------------------------------------
// NEDEN kendi kodumuz: saha kurulumu internetsiz calisiyor ve
// harici paket kurulumu (npm/pip) istenmiyor. Bu yuzden QR
// kodlayici bagimliliksiz, tek dosya olarak yazildi.
//
// KAPSAM: QR Code Model 2, byte (8-bit) mode, ECC seviyesi M.
// Versiyon 1-10 destekli (max 213 byte @ M). Ucus kodu 9-13
// karakter oldugu icin Version 1-2 yeterli; genel yazildi ki
// ileride URL/seri no gibi daha uzun veri de basilabilsin.
//
// CIKTI: SVG (vektor). Baskida net olsun diye raster degil vektor;
// yazici cozunurlugu ne olursa olsun kenarlar keskin cikar.
//
// Dogrulama: sinav_2441.html icinde bilinen referans vektorlerle
// (ISO/IEC 18004 ornekleri) karsilastirilir.
// ===============================================================

(function () {
  "use strict";

  // ----- Galois alani GF(256), QR icin p(x)=0x11D -----
  const EXP = new Uint8Array(512);
  const LOG = new Uint8Array(256);
  (function gfHazirla() {
    let x = 1;
    for (let i = 0; i < 255; i++) {
      EXP[i] = x;
      LOG[x] = i;
      x <<= 1;
      if (x & 0x100) x ^= 0x11D;
    }
    for (let i = 255; i < 512; i++) EXP[i] = EXP[i - 255];
  })();

  function gfCarp(a, b) {
    if (a === 0 || b === 0) return 0;
    return EXP[LOG[a] + LOG[b]];
  }

  // Reed-Solomon uretici polinomu (derece = ecc byte sayisi)
  function rsUretici(derece) {
    let poly = [1];
    for (let i = 0; i < derece; i++) {
      const yeni = new Array(poly.length + 1).fill(0);
      for (let j = 0; j < poly.length; j++) {
        yeni[j] ^= poly[j];
        yeni[j + 1] ^= gfCarp(poly[j], EXP[i]);
      }
      poly = yeni;
    }
    return poly;
  }

  function rsEcc(veri, eccSayi) {
    const gen = rsUretici(eccSayi);
    const kalan = new Array(eccSayi).fill(0);
    for (const b of veri) {
      const fak = b ^ kalan[0];
      kalan.shift();
      kalan.push(0);
      if (fak !== 0) {
        for (let i = 0; i < eccSayi; i++) {
          kalan[i] ^= gfCarp(gen[i + 1], fak);
        }
      }
    }
    return kalan;
  }

  // ----- Versiyon tablolari (ECC seviyesi M) -----
  // [toplam kod sozcugu, ecc/blok, blok1 sayisi, blok1 veri,
  //  blok2 sayisi, blok2 veri]
  const VER_M = {
    1:  [26,   10, 1, 16,  0, 0],
    2:  [44,   16, 1, 28,  0, 0],
    3:  [70,   26, 1, 44,  0, 0],
    4:  [100,  18, 2, 32,  0, 0],
    5:  [134,  24, 2, 43,  0, 0],
    6:  [172,  16, 4, 27,  0, 0],
    7:  [196,  18, 4, 31,  0, 0],
    8:  [242,  22, 2, 38,  2, 39],
    9:  [292,  22, 3, 36,  2, 37],
    10: [346,  26, 4, 43,  1, 44],
  };

  // Hizalama deseni merkez koordinatlari (versiyon 2-10)
  const HIZALAMA = {
    1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30],
    6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46],
    10: [6, 28, 50],
  };

  // Versiyon bilgisi (>=7) BCH(18,6) tablosu
  const VER_BILGI = {
    7: 0x07C94, 8: 0x085BC, 9: 0x09A99, 10: 0x0A4D3,
  };

  function veriKapasitesi(ver) {
    const t = VER_M[ver];
    return t[2] * t[3] + t[4] * t[5];
  }

  // ----- Bit tamponu -----
  function BitTampon() {
    this.bitler = [];
  }
  BitTampon.prototype.ekle = function (deger, uzunluk) {
    for (let i = uzunluk - 1; i >= 0; i--) {
      this.bitler.push((deger >>> i) & 1);
    }
  };

  // ----- Veri kodlama (byte mode) -----
  function veriKodla(metin, ver) {
    // UTF-8 byte dizisi
    const bayt = [];
    for (const ch of metin) {
      const kp = ch.codePointAt(0);
      if (kp < 0x80) bayt.push(kp);
      else if (kp < 0x800) {
        bayt.push(0xC0 | (kp >> 6), 0x80 | (kp & 0x3F));
      } else if (kp < 0x10000) {
        bayt.push(0xE0 | (kp >> 12), 0x80 | ((kp >> 6) & 0x3F),
                  0x80 | (kp & 0x3F));
      } else {
        bayt.push(0xF0 | (kp >> 18), 0x80 | ((kp >> 12) & 0x3F),
                  0x80 | ((kp >> 6) & 0x3F), 0x80 | (kp & 0x3F));
      }
    }

    const kap = veriKapasitesi(ver);
    const uzBit = (ver <= 9) ? 8 : 16;   // byte mode karakter sayisi biti
    const bt = new BitTampon();
    bt.ekle(0b0100, 4);                  // mode: byte
    bt.ekle(bayt.length, uzBit);
    for (const b of bayt) bt.ekle(b, 8);

    // Bitis gostergesi
    const maxBit = kap * 8;
    if (bt.bitler.length + 4 <= maxBit) bt.ekle(0, 4);
    // 8'e tamamla
    while (bt.bitler.length % 8 !== 0) bt.bitler.push(0);

    // Kod sozcuklerine cevir
    const kod = [];
    for (let i = 0; i < bt.bitler.length; i += 8) {
      let v = 0;
      for (let j = 0; j < 8; j++) v = (v << 1) | bt.bitler[i + j];
      kod.push(v);
    }
    // Dolgu bayt deseni (ISO: 0xEC, 0x11 donusumlu)
    const dolgu = [0xEC, 0x11];
    let di = 0;
    while (kod.length < kap) kod.push(dolgu[di++ % 2]);
    return kod;
  }

  // Blok bolme + ECC + serpistirme
  function kodSozcukleriUret(metin, ver) {
    const t = VER_M[ver];
    const eccSayi = t[1];
    const veri = veriKodla(metin, ver);

    const bloklar = [];
    let p = 0;
    for (let i = 0; i < t[2]; i++) {
      bloklar.push(veri.slice(p, p + t[3]));
      p += t[3];
    }
    for (let i = 0; i < t[4]; i++) {
      bloklar.push(veri.slice(p, p + t[5]));
      p += t[5];
    }
    const eccler = bloklar.map(b => rsEcc(b, eccSayi));

    // Serpistirme: veri once, sonra ecc
    const sonuc = [];
    const maxVeri = Math.max(...bloklar.map(b => b.length));
    for (let i = 0; i < maxVeri; i++) {
      for (const b of bloklar) if (i < b.length) sonuc.push(b[i]);
    }
    for (let i = 0; i < eccSayi; i++) {
      for (const e of eccler) sonuc.push(e[i]);
    }
    return sonuc;
  }

  // ----- Matris kurulumu -----
  function matrisKur(ver) {
    const n = ver * 4 + 17;
    const m = [];
    const rez = [];   // rezerve (fonksiyon deseni) haritasi
    for (let i = 0; i < n; i++) {
      m.push(new Array(n).fill(0));
      rez.push(new Array(n).fill(false));
    }

    // Finder deseni (7x7) + separator (cevresindeki 1 modul beyaz serit).
    // -1 ve 7 indexleri separator'e denk gelir: oralara MUTLAKA 0 yazilir.
    // Aksi halde rezerve edilip 1 kalir ve kod okunamaz (olculdu: 12 modul).
    function finder(r, c) {
      for (let i = -1; i <= 7; i++) {
        for (let j = -1; j <= 7; j++) {
          const y = r + i, x = c + j;
          if (y < 0 || y >= n || x < 0 || x >= n) continue;
          let deger;
          if (i === -1 || i === 7 || j === -1 || j === 7) {
            deger = 0;                  // separator: her zaman beyaz
          } else {
            const kenar = (i === 0 || i === 6 || j === 0 || j === 6);
            const ic = (i >= 2 && i <= 4 && j >= 2 && j <= 4);
            deger = (kenar || ic) ? 1 : 0;
          }
          m[y][x] = deger;
          rez[y][x] = true;
        }
      }
    }
    finder(0, 0);
    finder(0, n - 7);
    finder(n - 7, 0);

    // Zamanlama desenleri
    for (let i = 8; i < n - 8; i++) {
      m[6][i] = (i % 2 === 0) ? 1 : 0; rez[6][i] = true;
      m[i][6] = (i % 2 === 0) ? 1 : 0; rez[i][6] = true;
    }

    // Hizalama desenleri
    const hz = HIZALAMA[ver] || [];
    for (const r of hz) {
      for (const c of hz) {
        // finder ile cakisanlari atla
        if ((r <= 8 && c <= 8) || (r <= 8 && c >= n - 9) ||
            (r >= n - 9 && c <= 8)) continue;
        for (let i = -2; i <= 2; i++) {
          for (let j = -2; j <= 2; j++) {
            const ap = (Math.max(Math.abs(i), Math.abs(j)) !== 1);
            m[r + i][c + j] = ap ? 1 : 0;
            rez[r + i][c + j] = true;
          }
        }
      }
    }

    // Karanlik modul + format alani rezervi
    m[n - 8][8] = 1; rez[n - 8][8] = true;
    for (let i = 0; i <= 8; i++) {
      if (!rez[8][i]) { rez[8][i] = true; }
      if (!rez[i][8]) { rez[i][8] = true; }
    }
    for (let i = 0; i < 8; i++) {
      rez[8][n - 1 - i] = true;
      rez[n - 1 - i][8] = true;
    }
    // Versiyon bilgisi alani (>=7)
    if (ver >= 7) {
      for (let i = 0; i < 6; i++) {
        for (let j = 0; j < 3; j++) {
          rez[n - 11 + j][i] = true;
          rez[i][n - 11 + j] = true;
        }
      }
    }
    return { m, rez, n };
  }

  // Veri bitlerini zigzag yerlestir
  function veriYerlestir(m, rez, n, kodlar) {
    const bitler = [];
    for (const k of kodlar) {
      for (let i = 7; i >= 0; i--) bitler.push((k >>> i) & 1);
    }
    let bi = 0, yukari = true;
    for (let sag = n - 1; sag > 0; sag -= 2) {
      if (sag === 6) sag = 5;    // zamanlama kolonunu atla
      for (let adim = 0; adim < n; adim++) {
        const y = yukari ? (n - 1 - adim) : adim;
        for (let dx = 0; dx < 2; dx++) {
          const x = sag - dx;
          if (rez[y][x]) continue;
          m[y][x] = (bi < bitler.length) ? bitler[bi] : 0;
          bi++;
        }
      }
      yukari = !yukari;
    }
  }

  // Maske fonksiyonlari
  const MASKE = [
    (y, x) => (y + x) % 2 === 0,
    (y, x) => y % 2 === 0,
    (y, x) => x % 3 === 0,
    (y, x) => (y + x) % 3 === 0,
    (y, x) => (Math.floor(y / 2) + Math.floor(x / 3)) % 2 === 0,
    (y, x) => ((y * x) % 2 + (y * x) % 3) === 0,
    (y, x) => (((y * x) % 2 + (y * x) % 3) % 2) === 0,
    (y, x) => (((y + x) % 2 + (y * x) % 3) % 2) === 0,
  ];

  // Format bilgisi BCH(15,5) + XOR 0x5412
  function formatBilgi(eccSeviye, maske) {
    // ECC M -> 0b00
    const veri = (eccSeviye << 3) | maske;
    let d = veri << 10;
    const g = 0x537;
    for (let i = 14; i >= 10; i--) {
      if ((d >>> i) & 1) d ^= g << (i - 10);
    }
    return ((veri << 10) | d) ^ 0x5412;
  }

  // Format bilgisi yerlesimi. ISO/IEC 18004 sekil 25.
  // Eslesme, 4 ECC x 8 maske = 32 referans
  // kodun format alani modul modul cozulerek dogrulandi; formul ile
  // turetmeye calismak hatali sonuc veriyor (olculdu).
  // Kopya 1: en anlamli bit (14) (8,0)'da, en anlamsiz bit (0) (0,8)'de.
  // Kopya 2: bit 14 (n-1,8)'de, bit 0 (8,n-1)'de.
  function formatYaz(m, n, fmt) {
    const bit = (i) => (fmt >>> i) & 1;

    // Kopya 1: sol-ust finder cevresi
    m[8][0] = bit(14);
    m[8][1] = bit(13);
    m[8][2] = bit(12);
    m[8][3] = bit(11);
    m[8][4] = bit(10);
    m[8][5] = bit(9);
    m[8][7] = bit(8);
    m[8][8] = bit(7);
    m[7][8] = bit(6);
    m[5][8] = bit(5);
    m[4][8] = bit(4);
    m[3][8] = bit(3);
    m[2][8] = bit(2);
    m[1][8] = bit(1);
    m[0][8] = bit(0);

    // Kopya 2: sol-alt (dikey) + sag-ust (yatay)
    m[n - 1][8] = bit(14);
    m[n - 2][8] = bit(13);
    m[n - 3][8] = bit(12);
    m[n - 4][8] = bit(11);
    m[n - 5][8] = bit(10);
    m[n - 6][8] = bit(9);
    m[n - 7][8] = bit(8);
    m[8][n - 8] = bit(7);
    m[8][n - 7] = bit(6);
    m[8][n - 6] = bit(5);
    m[8][n - 5] = bit(4);
    m[8][n - 4] = bit(3);
    m[8][n - 3] = bit(2);
    m[8][n - 2] = bit(1);
    m[8][n - 1] = bit(0);

    m[n - 8][8] = 1;   // dark module (her zaman koyu)
  }

  function versiyonYaz(m, n, ver) {
    if (ver < 7) return;
    const vb = VER_BILGI[ver];
    if (!vb) return;
    for (let i = 0; i < 18; i++) {
      const bit = (vb >>> i) & 1;
      const a = Math.floor(i / 3), b = i % 3;
      m[n - 11 + b][a] = bit;
      m[a][n - 11 + b] = bit;
    }
  }

  // Ceza puani (ISO 18004 4 kural) - en iyi maskeyi secmek icin
  function cezaPuani(m, n) {
    let ceza = 0;
    // Kural 1: ayni renk 5+ ardisik
    for (let y = 0; y < n; y++) {
      for (const yatay of [true, false]) {
        let say = 1;
        for (let i = 1; i < n; i++) {
          const a = yatay ? m[y][i - 1] : m[i - 1][y];
          const b = yatay ? m[y][i] : m[i][y];
          if (a === b) say++;
          else { if (say >= 5) ceza += 3 + (say - 5); say = 1; }
        }
        if (say >= 5) ceza += 3 + (say - 5);
      }
    }
    // Kural 2: 2x2 ayni renk
    for (let y = 0; y < n - 1; y++) {
      for (let x = 0; x < n - 1; x++) {
        const v = m[y][x];
        if (v === m[y][x + 1] && v === m[y + 1][x] && v === m[y + 1][x + 1]) {
          ceza += 3;
        }
      }
    }
    // Kural 3: 1:1:3:1:1 deseni
    const desen = [1, 0, 1, 1, 1, 0, 1];
    function desenAra(dizi) {
      let c = 0;
      for (let i = 0; i + 7 <= dizi.length; i++) {
        let eslesti = true;
        for (let j = 0; j < 7; j++) {
          if (dizi[i + j] !== desen[j]) { eslesti = false; break; }
        }
        if (!eslesti) continue;
        const oncesi = dizi.slice(Math.max(0, i - 4), i);
        const sonrasi = dizi.slice(i + 7, i + 11);
        if (oncesi.length === 4 && oncesi.every(v => v === 0)) c++;
        else if (sonrasi.length === 4 && sonrasi.every(v => v === 0)) c++;
      }
      return c;
    }
    for (let i = 0; i < n; i++) {
      ceza += 40 * desenAra(m[i]);
      ceza += 40 * desenAra(m.map(r => r[i]));
    }
    // Kural 4: koyu modul orani
    let koyu = 0;
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) koyu += m[y][x];
    const oran = (koyu * 100) / (n * n);
    ceza += Math.floor(Math.abs(oran - 50) / 5) * 10;
    return ceza;
  }

  // ----- Ana kodlayici -----
  // metin -> { n, modul(2B dizi 0/1) }
  function qrUret(metin) {
    metin = String(metin == null ? "" : metin);
    // Uygun en kucuk versiyonu sec
    let ver = 0;
    for (let v = 1; v <= 10; v++) {
      const uzBit = (v <= 9) ? 8 : 16;
      // UTF-8 byte sayisi
      let bn = 0;
      for (const ch of metin) {
        const kp = ch.codePointAt(0);
        bn += (kp < 0x80) ? 1 : (kp < 0x800) ? 2 : (kp < 0x10000) ? 3 : 4;
      }
      const gerekli = 4 + uzBit + bn * 8;
      if (gerekli <= veriKapasitesi(v) * 8) { ver = v; break; }
    }
    if (!ver) throw new Error("QR: veri cok uzun (max versiyon 10)");

    const kodlar = kodSozcukleriUret(metin, ver);

    // Tum maskeleri dene, en az cezalı olani sec
    let enIyi = null, enIyiCeza = Infinity;
    for (let mk = 0; mk < 8; mk++) {
      const { m, rez, n } = matrisKur(ver);
      veriYerlestir(m, rez, n, kodlar);
      // Maskeyi uygula (rezerve olmayanlara)
      for (let y = 0; y < n; y++) {
        for (let x = 0; x < n; x++) {
          if (!rez[y][x] && MASKE[mk](y, x)) m[y][x] ^= 1;
        }
      }
      formatYaz(m, n, formatBilgi(0b00, mk));   // ECC M
      versiyonYaz(m, n, ver);
      const c = cezaPuani(m, n);
      if (c < enIyiCeza) { enIyiCeza = c; enIyi = { m, n }; }
    }
    return { n: enIyi.n, modul: enIyi.m, versiyon: ver };
  }

  // ----- SVG cikti -----
  // Baskida net olsun diye vektor. `kenar` = sessiz bolge (modul cinsinden,
  // ISO minimum 4).
  function qrSvg(metin, piksel, kenar) {
    piksel = piksel || 96;
    kenar = (kenar == null) ? 4 : kenar;
    const q = qrUret(metin);
    const tam = q.n + kenar * 2;
    let yol = "";
    for (let y = 0; y < q.n; y++) {
      for (let x = 0; x < q.n; x++) {
        if (q.modul[y][x]) {
          yol += "M" + (x + kenar) + "," + (y + kenar) + "h1v1h-1z";
        }
      }
    }
    return '<svg xmlns="http://www.w3.org/2000/svg" width="' + piksel +
      '" height="' + piksel + '" viewBox="0 0 ' + tam + ' ' + tam +
      '" shape-rendering="crispEdges">' +
      '<rect width="' + tam + '" height="' + tam + '" fill="#fff"/>' +
      '<path d="' + yol + '" fill="#000"/></svg>';
  }

  window.qrUret = qrUret;
  window.qrSvg = qrSvg;
})();
