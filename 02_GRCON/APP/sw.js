// GOKTUNGU GCS service worker - v2.4.14
// Amac: PWA kurulabilirligi + temel cevrimdisi iskelet.
// Strateji: AG ONCELIKLI (network-first). GCS canli bir komuta arayuzu
// oldugundan bayat icerik gostermek tehlikelidir; onbellek yalnizca
// sunucuya ULASILAMADIGINDA devreye girer.
// Canli/dinamik yollar (WS, MJPEG proxy, tile, AI) HICBIR ZAMAN
// onbelleklenmez.

// v2.4.24: Onbellek adi KAYIT URL'indeki ?s= parametresinden okunur.
//
// Onceki halde bu sabit elle yazilmisti ve "goktungu-v2422a" degerinde
// kalmisti: yani surum 2.4.24 iken onbellek adi hala 2.4.22'yi
// gosteriyordu. `activate` olayi eski onbellekleri YALNIZCA bu ad
// degistiginde siler; ad sabit kalinca 2.4.22 doneminden kalan
// dosyalar suresiz saklanir. Olculen vaka: sunucu 2.4.24 verirken
// tarayici DOM'u v2423a etiketli eski dosyalari gosteriyordu.
//
// NOT: importScripts("js/surum.js") YOLU KULLANILMAZ. surum.js
// surumu `const GCS_SURUM` ile tanimlar; const global nesneye
// eklenmedigi icin SW baglaminda guvenilir sekilde okunamaz.
// Ayrica o dosya 41 surum kaydi tasir, SW'ye yuklemek gereksiz.
// Bunun yerine pwa.js kayit sirasinda `sw.js?s=<surum>` cagirir;
// URL degisince tarayici SW'yi yeni bayt dizisi sayar ve
// install/activate yeniden calisir, eski onbellekler silinir.
const _sp = new URL(self.location.href).searchParams;
const SURUM = "goktungu-" + (_sp.get("s") || "bilinmeyen");
const IskeletDosyalar = [
  "/",
  "/index.html",
  "/manifest.json",
  "/logo.png",
  "/pwa/ikon-192.png",
  "/pwa/ikon-512.png",
];

// Asla onbelleklenmeyecek yollar (canli veri / akis / API)
const CANLI_ONEK = [
  "/tile/",       // harita karolari (kendi cache mekanizmasi var)
  "/ai/",         // AI isci bildirimleri
  "/video",       // video duvari sayfasi haric degil ama akislar 8801'de
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(SURUM)
      .then((c) => c.addAll(IskeletDosyalar))
      .catch(() => null)   // ilk kurulumda eksik dosya olsa da kurul
  );
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((adlar) =>
      Promise.all(adlar.filter((a) => a !== SURUM)
                       .map((a) => caches.delete(a)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const istek = e.request;
  if (istek.method !== "GET") return;   // POST vb. daima aga
  const url = new URL(istek.url);
  // Farkli origin (baska port: MJPEG 8801, WS 8765) -> dokunma
  if (url.origin !== self.location.origin) return;
  // Canli yollara dokunma
  if (CANLI_ONEK.some((o) => url.pathname.startsWith(o))) return;

  // HTML gezinmeleri: onbellege YAZILMAZ.
  // index.html icinde alt kaynaklarin `?v=SURUM` etiketleri bulunur.
  // Bayat bir HTML onbellege yazilirsa, sunucu guncellense bile
  // tarayici ESKI etiketleri okur ve guncelleme hic gorunmez.
  // Cevrimdisi iskelet yine calisir: install sirasinda yazilan
  // /index.html kopyasi fetch basarisiz oldugunda kullanilir.
  const gezinme = (istek.mode === "navigate") ||
                  url.pathname === "/" ||
                  url.pathname.endsWith(".html");
  if (gezinme) {
    e.respondWith(
      fetch(istek).catch(() =>
        caches.match("/index.html").then((onb) => onb || Response.error())
      )
    );
    return;
  }

  // Ag oncelikli: once sunucu; olumlu yanit onbellege kopyalanir,
  // sunucuya ulasilamazsa onbellekten sunulur.
  e.respondWith(
    fetch(istek)
      .then((yanit) => {
        if (yanit && yanit.ok && (yanit.type === "basic")) {
          const kopya = yanit.clone();
          caches.open(SURUM).then((c) => c.put(istek, kopya))
                            .catch(() => null);
        }
        return yanit;
      })
      .catch(() =>
        caches.match(istek).then((onb) => {
          if (onb) return onb;
          // Sayfa gezinmesiyse iskelet index'e dus
          if (istek.mode === "navigate") {
            return caches.match("/index.html");
          }
          return Response.error();
        })
      )
  );
});
