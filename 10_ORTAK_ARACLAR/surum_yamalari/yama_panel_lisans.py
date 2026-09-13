"""IS-2521-LISANS: Musteri panelinde Merkez lisans belgesi indirme dugmesi.

OLCULEN KUSUR: panelde `merkez_lisans.json` indirme yolu HIC yoktu.
Merkez Uygulama sayfasi "lisans belgesi kurulum paketine gomuludur"
yaziyordu; oysa kurulum ve otomatik guncelleme belgeyi AYRICA bekliyor
(C:\\ProgramData\\Goktungu\\Merkez\\merkez_lisans.json). Sunucu ucu
(`/api/firma/merkez_lisans`) zaten vardi; yalniz arayuz eksikti.

Kullanim: python3.11 yama_panel_lisans.py <uygulama.js> <index.html>
"""
import sys

js_yol, html_yol = sys.argv[1], sys.argv[2]


def degistir(metin, eski, yeni, ad):
    n = metin.count(eski)
    if n != 1:
        sys.exit(f"HATA [{ad}]: capa {n} kez bulundu (1 bekleniyordu)")
    return metin.replace(eski, yeni)


s = open(js_yol, encoding="utf-8").read()
if "lisansBelgesiIndir" in s:
    sys.exit("HATA: yama zaten uygulanmis")

# 1) Ortak indirme islevi (yoneticiMiKontrol'un hemen ardina)
s = degistir(s, '''function yoneticiMiKontrol() {
  return !!(BEN && ['firma_yonetici', 'yonetici', 'admin']
    .indexOf(String(BEN.rol)) >= 0);
}
''', '''function yoneticiMiKontrol() {
  return !!(BEN && ['firma_yonetici', 'yonetici', 'admin']
    .indexOf(String(BEN.rol)) >= 0);
}

/* IS-2521-LISANS: Merkez Uygulama lisans belgesini indirir.
 * Belge `/api/firma/merkez_lisans` yanitinin kendisidir ({lisans, imza,
 * acik_anahtar}); kurulum imzayi kanonik govde uzerinden dogruladigi icin
 * JSON bicimlendirmesi imzayi bozmaz. Uc yalniz firma yoneticisine acik. */
const LISANS_YOLLARI = {
  windows: 'C:\\\\ProgramData\\\\Goktungu\\\\Merkez\\\\merkez_lisans.json',
  linux: '/var/lib/goktungu-merkez/merkez_lisans.json'
};

async function lisansBelgesiIndir(dugme) {
  if (dugme) dugme.disabled = true;
  try {
    const belge = await cagir('/api/firma/merkez_lisans', { cache: 'no-store' });
    const blob = new Blob([JSON.stringify(belge, null, 2) + '\\n'],
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
''', "ortak-islev")

# 2) Abonelik sayfasi: Merkez Uygulama hak karti
s = degistir(s, '''          <span class="yetki-not">${y.merkez_lisans
            ? 'kendi sunucunuzda sınırsız'
            : 'tek seferlik $5.000'}</span>
        </div>''', '''          <span class="yetki-not">${y.merkez_lisans
            ? 'kendi sunucunuzda sınırsız'
            : 'tek seferlik $5.000'}</span>
          ${y.merkez_lisans ? `<button type="button" class="ikincil lisans-indir"
            style="margin-top:8px"
            title="Kurulum ve otomatik güncelleme için gerekli">Lisans belgesini indir</button>` : ''}
        </div>''', "abonelik-kart")

s = degistir(s, '''  els('.para-btn').forEach((d) => d.addEventListener('click', () => {''', '''  lisansDugmeleriBagla();
  els('.para-btn').forEach((d) => d.addEventListener('click', () => {''', "abonelik-bagla")

# 3) Merkez Uygulama sayfasi: yanlis metni duzelt + dugme
s = degistir(s, '''      <p class="aciklama">Lisans belgesi kurulum paketine gömülüdür;
        kurulum internet bağlantısı olmadan da çalışır.</p>
    </div>''', '''      <p class="aciklama">Kurulum paketi lisans belgesini İÇERMEZ. Belgeyi
        indirip aşağıdaki konuma kopyalayın ve Merkez servisini yeniden
        başlatın. Yazılım belgenin imzasını internet bağlantısı olmadan
        doğrular; otomatik güncelleme de bu belgeyle yetkilendirilir.</p>
      <p><button type="button" class="lisans-indir">Lisans belgesini indir
        (merkez_lisans.json)</button></p>
      <dl class="ozet">
        <dt>Windows</dt><dd><code class="kod">${kacir(LISANS_YOLLARI.windows)}</code></dd>
        <dt>Ubuntu / Linux</dt><dd><code class="kod">${kacir(LISANS_YOLLARI.linux)}</code></dd>
      </dl>
    </div>''', "merkez-metin")

s = degistir(s, '''          girilir</li>
      </ol>
    </div>`;
}''', '''          girilir</li>
      </ol>
    </div>`;
  lisansDugmeleriBagla();
}''', "merkez-bagla")

open(js_yol, "w", encoding="utf-8").write(s)

h = open(html_yol, encoding="utf-8").read()
h = degistir(h, 'uygulama.js?v=138', 'uygulama.js?v=139', "onbellek")
open(html_yol, "w", encoding="utf-8").write(h)
print("panel lisans yamasi uygulandi")
