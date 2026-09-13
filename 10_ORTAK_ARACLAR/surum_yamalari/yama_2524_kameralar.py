"""2.5.24 — kameralar.js: görüntü hedefi (tek konum) + AI ayar düğmesi."""
import sys
p = "/root/grcoff_2524_build/src/js/kameralar.js"
s = open(p, encoding="utf-8").read()

def r(a, b, ad):
    global s
    if s.count(a) != 1:
        sys.exit(f"HATA [{ad}]: {s.count(a)} eşleşme")
    s = s.replace(a, b)

# 1) wsGonder'i disari ac (paylasimli modul kullanir)
r('''  window.kameraOnizlemeUrl = function (id) { return proxyUrl(Number(id)); };''',
  '''  window.kameraOnizlemeUrl = function (id) { return proxyUrl(Number(id)); };
  // Paylasimli AI paneli kamera kaydini bu kanaldan yollar.
  window.kameraWsGonder = function (obj) { wsGonder(obj); };
  function hedef(id) {
    return (typeof window.kameraGoruntuHedefi === "function")
      ? window.kameraGoruntuHedefi(id) : "yuzen";
  }''', "ws-ac")

# 2) araclarOlustur: AI ayar dugmesi + goruntu hedefi secici ekle
r('''    kutu.append(bPlay, bAyir, bDuzenle, bSil);
    return kutu;''',
  '''    // v2.5.24: Yapay Zeka Ayarlari dugmesi (paylasimli panel)
    if (typeof window.kameraAiAyarButonu === "function") {
      kutu.appendChild(window.kameraAiAyarButonu(kamera.id));
    }
    kutu.append(bPlay, bAyir, bDuzenle, bSil);
    // v2.5.24: Goruntu hedefi secici (harita/yuzen/panel/tam) — tek konum
    if (typeof window.kameraGoruntuHedefSecici === "function") {
      kutu.appendChild(window.kameraGoruntuHedefSecici(kamera.id));
    }
    return kutu;''', "araclar-ai")

# 3) satirOlustur: satir ici video yalniz hedef 'panel' iken
r('''    // Liste gorunumunde oynayan kameranin videosu satirin altinda gosterilir
    if (oynayanlar.has(kamera.id) && !ayrikler[kamera.id]) {''',
  '''    // Liste gorunumunde oynayan kameranin videosu satirin altinda gosterilir
    // (v2.5.24: yalniz goruntu hedefi 'panel' iken; tek konumda gosterim)
    if (oynayanlar.has(kamera.id) && !ayrikler[kamera.id] && hedef(kamera.id) === "panel") {''', "satir-panel")

# 4) kartOlustur: onizleme videosu yalniz hedef 'panel' iken
r('''    const kutu = document.createElement("div");
    kutu.className = "kam-video-kutu kam-onizleme";
    if (oynayanlar.has(kamera.id)) {
      kutu.appendChild(videoOlustur(kamera));
    } else {
      const bos = document.createElement("div");
      bos.className = "kam-bos-onizleme";
      bos.innerHTML = "<i class='fa-solid fa-video-slash'></i>";
      kutu.appendChild(bos);
    }

    kart.append(baslik, kutu, araclarOlustur(kamera));
    return kart;''',
  '''    const kutu = document.createElement("div");
    kutu.className = "kam-video-kutu kam-onizleme";
    if (oynayanlar.has(kamera.id) && hedef(kamera.id) === "panel") {
      kutu.appendChild(videoOlustur(kamera));
    } else if (oynayanlar.has(kamera.id)) {
      // Baska bir hedefte gosteriliyor: panelde nerede oldugunu bildir
      const bilgi = document.createElement("div");
      bilgi.className = "kam-bos-onizleme kam-baska-hedef";
      const nerede = { harita: "haritada", yuzen: "yüzen pencerede", tam: "tam ekranda" };
      bilgi.innerHTML = "<i class='fa-solid fa-up-right-from-square'></i>" +
        "<span>" + (nerede[hedef(kamera.id)] || "başka yerde") + "</span>";
      kutu.appendChild(bilgi);
    } else {
      const bos = document.createElement("div");
      bos.className = "kam-bos-onizleme";
      bos.innerHTML = "<i class='fa-solid fa-video-slash'></i>";
      kutu.appendChild(bos);
    }

    kart.append(baslik, kutu, araclarOlustur(kamera));
    return kart;''', "kart-panel")

open(p, "w", encoding="utf-8").write(s)
print("kameralar.js 1. tur tamam")
