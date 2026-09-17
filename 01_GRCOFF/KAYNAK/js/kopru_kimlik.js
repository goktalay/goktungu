// =================================================================
// GOKTUNGU v2.4.67 - PROGRAM AYARLARI -> KOPRU KIMLIKLERI BOLUMU
//
// Merkez Uygulama'yi satin alan sirket KAPALI DEVRE calisabilir. Bu
// durumda saha bilgisayarlarindaki kopru yazilimi buluta degil BU
// kuruluma baglanir. Baglanabilmesi icin her saha makinesine bir
// kurulum kimligi (kurulum_uid + gizli) verilmelidir; bu bolum o
// kimlikleri uretir, listeler ve iptal eder.
//
// SUNUCU SOZLESMESI (goktungu/sunucu.py::_kopru_kimlik_komut):
//   istek  {"tip":"kopru_kimlik_liste"}
//          {"tip":"kopru_kimlik_uret","ad":..,"aciklama":..}
//          {"tip":"kopru_kimlik_sil","ornek_id":..}
//   yanit  {"tip":"kopru_kimlik_sonuc","komut":..,"basarili":bool,
//           "hata":str,"liste":[...],"kimlik":{...},"port":int,
//           "uc":str,"canli":int}
//
// ## GIZLI YALNIZ BIR KEZ GORUNUR
//
// Sunucu sirri veritabaninda YALNIZ ozet olarak saklar. `uret`
// yanitindaki `gizli` bir daha okunamaz; bu yuzden uretim sonrasi
// kullaniciya kalici bir kutuda gosterilir ve kopyalatilir. Kutu
// kullanici kapatana kadar DURUR: otomatik kapanan bir bildirim
// kullanicinin sirri kaybetmesine yol acardi.
//
// ## MERKEZ KIPINDE GORUNMEZ
//
// Bulut merkezinde (/app/) kopru kimlikleri kurumsal panelden
// uretilir. Ayni kimligi iki ayri tabloda tutmamak icin sunucu bu
// komutlari merkez kipinde reddeder; arayuz de bolumu gizler.
// =================================================================
"use strict";

// Sunucudan gelen son durum. Popup her acildiginda tazelenir.
window.kopruKimlikDurum = window.kopruKimlikDurum || {
  liste: [], port: 8765, canli: 0, yuklendi: false, merkez_kipi: false
};

// -----------------------------------------------------------------
// Koprunun gireceegi adresi uretir.
//
// Kopru `wss://`/`ws://` bekler. Yerel kurulumda TLS zorunlu degildir
// (ayni makine / kapali ag) ve `ws://` daha az kurulum hatasi uretir.
// PORT MUTLAKA yazilir: kopru port yoksa 443 varsayar ve baglanti
// reddedilir (bkz. kopru/merkez.py::_http_taban aciklamasi).
// -----------------------------------------------------------------
window.kopruUcAdresi = function(konak){
  const p = window.kopruKimlikDurum.port || 8765;
  const k = String(konak || "").trim() ||
    (location.hostname || "127.0.0.1");
  return "ws://" + k + ":" + p + "/kopru";
};

// -----------------------------------------------------------------
// Program Ayarlari govdesine bolumu ekler
// -----------------------------------------------------------------
window.kopruKimlikBolumEkle = function(govde){
  const t = (typeof D === "function") ? D() : {};
  const yonetici = (typeof oturumYoneticiMi === "function")
    ? oturumYoneticiMi() : false;

  // Merkez kipinde bolum HIC cizilmez (kopru kayitlari kurumsal panelde).
  if (window.kopruKimlikDurum.merkez_kipi) return;
  if (typeof window.kopruMerkezKipiMi === "function" && window.kopruMerkezKipiMi()) return;

  govde.appendChild(document.createElement("hr"));

  const baslik = document.createElement("div");
  baslik.className = "prog-ayar-altbaslik";
  baslik.innerHTML = "<i class='fa-solid fa-diagram-project'></i> " +
    (t.kokBaslik || "K\u00f6pr\u00fc Kimlikleri");
  govde.appendChild(baslik);

  const aciklama = document.createElement("div");
  aciklama.className = "prog-ayar-aciklama";
  aciklama.textContent = t.kokAciklama ||
    "Saha bilgisayarlar\u0131ndaki k\u00f6pr\u00fc yaz\u0131l\u0131m\u0131n\u0131n " +
    "bu kuruluma ba\u011flanabilmesi i\u00e7in her makineye bir kimlik " +
    "verilir. Kapal\u0131 devre kullan\u0131mda internet gerekmez.";
  govde.appendChild(aciklama);

  // --- Uc adresi (kopyalanabilir) ---
  const ucSat = document.createElement("div");
  ucSat.className = "prog-ayar-satir prog-ayar-port";
  const ucEt = document.createElement("span");
  ucEt.className = "prog-ayar-etiket";
  ucEt.innerHTML = "<i class='fa-solid fa-link'></i> " +
    (t.kokUcAdres || "K\u00f6pr\u00fc ba\u011flant\u0131 adresi");
  const ucGi = document.createElement("input");
  ucGi.type = "text";
  ucGi.id = "kokUcAdres";
  ucGi.className = "prog-ayar-giris";
  ucGi.readOnly = true;
  ucGi.value = window.kopruUcAdresi();
  ucGi.title = t.kokUcAdresIpucu ||
    "Bu adresi k\u00f6pr\u00fc yaz\u0131l\u0131m\u0131n\u0131n ayarlar\u0131ndaki " +
    "\u0022Merkez adresi\u0022 alan\u0131na yaz\u0131n.";
  ucSat.appendChild(ucEt); ucSat.appendChild(ucGi);
  govde.appendChild(ucSat);

  const ucNot = document.createElement("div");
  ucNot.className = "prog-ayar-aciklama";
  ucNot.id = "kokUcNot";
  ucNot.textContent = t.kokUcNot ||
    "Saha bilgisayar\u0131 ba\u015fka bir makinedeyse 127.0.0.1 yerine bu " +
    "bilgisayar\u0131n a\u011f adresini yaz\u0131n. Port numaras\u0131 " +
    "mutlaka kalmal\u0131d\u0131r.";
  govde.appendChild(ucNot);

  // v2.4.232: kimlik uretme/listeleme Destek > Kopruler paneline tasindi
  // (API kodu). Burada yalniz adres bilgisi ve panele gecis kalir.
  const yonNot = document.createElement("div");
  yonNot.className = "prog-ayar-aciklama";
  yonNot.textContent = t.kokYeniPanelNot ||
    "K\u00f6pr\u00fc kay\u0131tlar\u0131 ve API kodlar\u0131 Destek > K\u00f6pr\u00fcler panelinden y\u00f6netilir.";
  govde.appendChild(yonNot);
  const pSat = document.createElement("div");
  pSat.className = "prog-ayar-satir";
  const pEt = document.createElement("span");
  pEt.className = "prog-ayar-etiket";
  pEt.innerHTML = "<i class='fa-solid fa-diagram-project'></i> " +
    (t.mbKopruler || "K\u00f6pr\u00fcler");
  const pBtn = document.createElement("button");
  pBtn.type = "button";
  pBtn.className = "prog-ayar-dugme";
  pBtn.id = "btnKkPanel";
  pBtn.textContent = t.kokPaneliAc || "K\u00f6pr\u00fcler panelini a\u00e7";
  pBtn.addEventListener("click", () => {
    if (typeof window.yuzenPanelAc === "function") window.yuzenPanelAc("yzKopruler");
    else { const pn = document.getElementById("yzKopruler"); if (pn) pn.classList.remove("yuzen-gizli"); }
  });
  pSat.appendChild(pEt); pSat.appendChild(pBtn);
  govde.appendChild(pSat);
};

// -----------------------------------------------------------------
// v2.4.232: eski `kopru_kimlik_*` yanitlari yalniz port/kip bilgisini
// gunceller (adres satiri icin). Liste/sir gosterimi kaldirildi;
// kopru kayitlari Destek > Kopruler panelindedir (kopruler_panel.js).
// -----------------------------------------------------------------
window.kopruKimlikSonuc = function(m){
  const dm = window.kopruKimlikDurum;
  if (m && m.port) dm.port = m.port;
  if (m && typeof m.merkez_kipi === "boolean") dm.merkez_kipi = m.merkez_kipi;
  const uc = document.getElementById("kokUcAdres");
  if (uc) uc.value = window.kopruUcAdresi();
};
