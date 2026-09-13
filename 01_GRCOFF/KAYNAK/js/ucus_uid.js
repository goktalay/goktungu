// =====================================================================
// GOKTUNGU GCS — Kisa ucus UID (belge esleme kodu)               [v2.4.42]
// =====================================================================
// Ucuslar bu dalda kalici satir DEGILDIR: sunucu tarafinda v_ucuslar
// GORUNUMU ile telemetriden turetilir. Bu yuzden rastgele veya artan
// bir numara KULLANILAMAZ; ucus yeniden hesaplandiginda deger degisir
// ve imzali iki belge (ucus raporu / yatay grafik ciktisi) celisir.
//
// UID mevcut ucus id'sinden DETERMINISTIK turetilir:
//   id bicimi: YYYYMMDD_HHMMSS_D{sysid}  (dron + kalkis saniyesi)
// Ayni ucus her zaman ayni kodu verir.
//
// !!! BU ALGORITMA goktungu/ucus_gecmisi.py::ucus_uid() ILE BIREBIR
// AYNI OLMAK ZORUNDADIR. Arayuzde gorunen kod ile rapordaki/sunucudan
// gelen kod ayrisirsa belge eslemesi bozulur. sinav_2442.html
// icindeki karsilastirma testi bu esitligi dogrular.
// =====================================================================

// CROCKFORD BASE32 alfabesi (fiili standart). TAM 32 karakter
// olmak ZORUNDA: her karakter 5 bit tasir.
//
// Havuz 36 karakter (10 rakam + 26 harf) oldugundan en fazla 4
// karakter cikarilabilir. Cikarilanlar: I, L, O, U
//   - I ve L cikarildi -> geriye '1' kaldi
//   - O cikarildi      -> geriye '0' kaldi
//   - U cikarildi      -> istenmeyen kelime uretimini azaltir
//
// Boylece benzer gorunen her grupta TEK gecerli karakter kalir ve
// belirsizlik TEK YONLU olur: pilot ciktidaki karakteri 'O' okusa
// bile tek gecerli karsilik '0'dir. Kod aranirken ucusKoduNormalize()
// bu cevrimi yapar, yani yanlis okuma kaybedilmis kayda yol acmaz.
// (0/1 yerine harfleri tutan varyantlar I/L cakismasini birakiyordu;
//  o cakisma IKI YONLU oldugu icin normalize edilemez.)
var UID_ALFABE = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';

/**
 * Ucus id'sinden kisa, okunabilir, deterministik kod uretir.
 * Bicim: XXXX-XXXX (8 karakter + tire)
 * FNV-1a 64-bit hash'in dusuk 40 biti Base32 ile yazilir.
 *
 * JS'te 64-bit tamsayi yok; BigInt kullanilir. Python tarafiyla
 * bit-bire ayni sonuc icin maskeleme de BigInt uzerinde yapilir.
 */
function ucusUid(ucusId) {
  var s = String(ucusId == null ? '' : ucusId);
  if (!s) return '';
  var MASK64 = (1n << 64n) - 1n;
  var h = 0xCBF29CE484222325n;          // FNV offset basis (64-bit)
  var PRIME = 0x100000001B3n;           // FNV prime (64-bit)
  // Python tarafi s.encode('utf-8') uzerinde donuyor; burada da
  // UTF-8 bayt dizisi uretilmeli ki cok baytli karakterlerde
  // (Turkce harf iceren bir id gelirse) sonuc ayni olsun.
  var bayt = uidUtf8Bayt(s);
  for (var i = 0; i < bayt.length; i++) {
    h = h ^ BigInt(bayt[i]);
    h = (h * PRIME) & MASK64;
  }
  h = h & 0xFFFFFFFFFFn;                // dusuk 40 bit
  var ch = [];
  for (var k = 0; k < 8; k++) {         // 8 * 5 bit = 40 bit
    ch.push(UID_ALFABE[Number(h & 0x1Fn)]);
    h = h >> 5n;
  }
  var kod = ch.reverse().join('');
  return kod.slice(0, 4) + '-' + kod.slice(4);
}

/** String -> UTF-8 bayt dizisi (TextEncoder yoksa elle). */
function uidUtf8Bayt(s) {
  if (typeof TextEncoder !== 'undefined') {
    return Array.from(new TextEncoder().encode(s));
  }
  var out = [];
  for (var i = 0; i < s.length; i++) {
    var c = s.charCodeAt(i);
    if (c < 0x80) {
      out.push(c);
    } else if (c < 0x800) {
      out.push(0xC0 | (c >> 6), 0x80 | (c & 0x3F));
    } else {
      out.push(0xE0 | (c >> 12), 0x80 | ((c >> 6) & 0x3F),
               0x80 | (c & 0x3F));
    }
  }
  return out;
}

/**
 * Bir ucus nesnesinin gosterilecek kodunu dondurur.
 * Sunucu `kod` alanini gonderiyorsa ONA guvenilir (tek dogruluk
 * kaynagi sunucudur); gelmiyorsa yerel olarak turetilir. Bu sayede
 * eski sunucuyla calisan arayuz de kod gosterebilir.
 */
function ucusKodu(ucus) {
  if (!ucus) return '';
  if (ucus.kod) return String(ucus.kod);
  return ucusUid(ucus.id || '');
}

/**
 * Elle girilen / sesli okunan kodu arama icin normalize eder.
 * Crockford cevrimi: O->0, I->1, L->1; kucuk harf ve tire/bosluk
 * temizlenir. Boylece imzali ciktidan okunan kod yanlis harfle
 * girilse bile dogru kayda ulasir.
 */
function ucusKoduNormalize(giris) {
  var s = String(giris == null ? '' : giris).toUpperCase();
  s = s.replace(/[^0-9A-Z]/g, '');   // tire, bosluk, noktalama
  s = s.replace(/O/g, '0');
  s = s.replace(/[IL]/g, '1');
  s = s.replace(/U/g, 'V');          // U uretilmez; en yakin karsilik
  if (s.length === 8) s = s.slice(0, 4) + '-' + s.slice(4);
  return s;
}

window.ucusUid = ucusUid;
window.ucusKodu = ucusKodu;
window.ucusKoduNormalize = ucusKoduNormalize;
