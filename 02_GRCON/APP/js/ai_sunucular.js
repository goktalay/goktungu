/* =====================================================================
   AI SUNUCULAR (v2.4.0)
   AI > Sunucular popup'i: NVIDIA/CPU islem sunuculari CRUD + durum
   (cevrimici LED, yuk cubugu) + aktif AI izlemeleri listesi.
   Sunucu tarafi: gozcu/ai_yonetici.py (WS: ai_sunucu_*, ai_izleme_*)

   v2.4.45: SSH ile uzaktan baslatma. Her AI bilgisayarinin yaninda
   PLAY dugmesi (SSH ile baglanip AI iscisini baslatir) ve KONSOL
   dugmesi (SSH ciktilarini canli gosteren acilir kapanir pencere).
   Sunucu tarafi: gozcu/ai_ssh.py (WS: ai_ssh_baslat/durdur/gecmis,
   yayin: ai_ssh_durum, ai_ssh_satir, ai_ssh_gecmis)
   ===================================================================== */
(function () {
  "use strict";

  const pop        = document.getElementById("aiSunucuPopup");
  const btnKapat   = document.getElementById("btnAiSunucuKapat");
  const btnYeni    = document.getElementById("btnAiSunucuYeni");
  const form       = document.getElementById("aiSunucuForm");
  const inAd       = document.getElementById("aisAd");
  const inTip      = document.getElementById("aisTip");
  const inHost     = document.getElementById("aisHost");
  const inPort     = document.getElementById("aisPort");
  const inKapasite = document.getElementById("aisKapasite");
  const inNotlar   = document.getElementById("aisNotlar");
  // v2.4.56: AI sunucusunun hangi KOPRU makinesinde oldugu secimi.
  const kopruAlan  = document.getElementById("aisKopruAlan");
  const kopruSec   = document.getElementById("aisKopruSec");
  // v2.4.45: SSH alanlari
  const inSshKul   = document.getElementById("aisSshKullanici");
  const inSshPort  = document.getElementById("aisSshPort");
  const inSshKey   = document.getElementById("aisSshAnahtar");
  const inSshSif   = document.getElementById("aisSshSifre");
  const inSshKomut = document.getElementById("aisSshKomut");
  const sifreVarNot = document.getElementById("aisSifreVar");
  const btnKaydet  = document.getElementById("btnAiSunucuKaydet");
  const btnVazgec  = document.getElementById("btnAiSunucuVazgec");
  const mesaj      = document.getElementById("aisMesaj");
  const liste      = document.getElementById("aiSunucuListe");
  const izlListe   = document.getElementById("aiIzlemeListe");
  if (!pop) return;

  let duzenlenenId = null;   // null: yeni kayit
  let sonSunucular = [];
  let sonIzlemeler = [];
  let tazeleyici = null;
  // v2.4.45: sunucu_id -> {calisiyor, cikis_kodu, komut, hata}
  const sshDurumlar = {};
  // v2.4.45: sunucu_id -> konsol penceresi acik mi
  const konsolAcik = {};

  function t(anahtar, varsayilan) {
    try {
      const d = (typeof D === "function") ? D() : null;
      return (d && d[anahtar]) || varsayilan;
    } catch (e) { return varsayilan; }
  }

  function gonder(obj) {
    try {
      if (typeof ws !== "undefined" && ws && ws.readyState === 1) {
        ws.send(JSON.stringify(obj));
        return true;
      }
    } catch (e) {}
    return false;
  }

  // ------------------------------------------------------------------
  // Popup ac / kapat
  // ------------------------------------------------------------------
  function ac() {
    const acikti = !pop.classList.contains("popup-gizli");
    if (acikti) { kapat(); return; }
    pop.classList.remove("popup-gizli");
    formGizle();
    tazele();
    // Acikken durumu periyodik yenile (saglik LED'leri, yuk)
    if (!tazeleyici) tazeleyici = setInterval(tazele, 5000);
    if (typeof window.popupTikleriGuncelle === "function")
      window.popupTikleriGuncelle();
  }
  function kapat() {
    pop.classList.add("popup-gizli");
    if (tazeleyici) { clearInterval(tazeleyici); tazeleyici = null; }
    if (typeof window.popupTikleriGuncelle === "function")
      window.popupTikleriGuncelle();
  }
  function tazele() {
    gonder({tip: "ai_sunucu_listele"});
    gonder({tip: "ai_izleme_listele"});
  }

  const mb = document.getElementById("mbAISunucular");
  if (mb) mb.addEventListener("click", (e) => { e.stopPropagation(); ac(); });
  if (btnKapat) btnKapat.addEventListener("click", kapat);

  // ------------------------------------------------------------------
  // Form
  // ------------------------------------------------------------------
  function formGoster(s) {
    duzenlenenId = s ? s.id : null;
    inAd.value       = s ? (s.ad || "") : "";
    inTip.value      = s ? (s.tip || "cpu") : "nvidia";
    inHost.value     = s ? (s.host || "") : "";
    inPort.value     = s ? (s.port || 8900) : 8900;
    inKapasite.value = s ? (s.kapasite || 4) : 4;
    inNotlar.value   = s ? (s.notlar || "") : "";
    // v2.4.45: SSH alanlari. Sifre ASLA geri doldurulmaz (sunucu
    // gondermiyor); bunun yerine "kayitli" notu gosterilir.
    if (inSshKul)   inSshKul.value   = s ? (s.ssh_kullanici || "") : "";
    if (inSshPort)  inSshPort.value  = s ? (s.ssh_port || 22) : 22;
    if (inSshKey)   inSshKey.value   = s ? (s.ssh_anahtar || "") : "";
    if (inSshKomut) inSshKomut.value = s ? (s.ssh_komut || "") : "";
    if (inSshSif)   inSshSif.value   = "";
    if (sifreVarNot)
      sifreVarNot.style.display = (s && s.ssh_sifre_var) ? "" : "none";
    // v2.4.56: kopru secimi. Duzenlemede kaydin koprusu onsecili gelir;
    // yeni kayitta secim bos baslar ve merkezde ZORUNLUDUR.
    if (typeof window.kopruSeciciDoldur === "function")
      window.kopruSeciciDoldur(kopruAlan, kopruSec,
                               s ? s.kopru_ornek_id : null);
    mesaj.textContent = "";
    form.style.display = "";
    inAd.focus();
  }
  function formGizle() {
    form.style.display = "none";
    duzenlenenId = null;
  }
  if (btnYeni) btnYeni.addEventListener("click", () => {
    (form.style.display === "none") ? formGoster(null) : formGizle();
  });
  if (btnVazgec) btnVazgec.addEventListener("click", formGizle);
  if (btnKaydet) btnKaydet.addEventListener("click", () => {
    const ad = inAd.value.trim(), host = inHost.value.trim();
    if (!ad || !host) {
      mesaj.textContent = t("aiFormEksik", "Ad ve host zorunludur");
      mesaj.style.color = "var(--kotu)";
      return;
    }
    // v2.4.56: merkezde kopru secimi zorunludur. Secilmezse kayit
    // merkez sunucusunun kendi makinesine baglanmaya calisir ve
    // "Connection refused" verir — pilot sebebini goremez.
    const merkezde = (typeof window.kopruMerkezKipiMi === "function")
      && window.kopruMerkezKipiMi();
    const kopruId = kopruSec ? String(kopruSec.value || "") : "";
    if (merkezde && !kopruId) {
      mesaj.textContent = t("aisKopruUyari",
        "AI sunucusunun çalıştığı köprü makinesini seçin.");
      mesaj.style.color = "var(--kotu)";
      return;
    }
    // v2.4.45: SSH sozlugu. Sifre alani BOS ise kayitli sifre KORUNUR
    // (sifre_koru), doldurulmussa degistirilir.
    const sifreMetin = inSshSif ? inSshSif.value : "";
    const ssh = {
      kullanici: inSshKul ? inSshKul.value.trim() : "",
      port: inSshPort ? (parseInt(inSshPort.value) || 22) : 22,
      anahtar: inSshKey ? inSshKey.value.trim() : "",
      komut: inSshKomut ? inSshKomut.value.trim() : "",
      sifre: sifreMetin
    };
    gonder({tip: "ai_sunucu_kaydet", id: duzenlenenId, ad: ad,
            sunucu_tip: inTip.value,
            host: host,
            port: parseInt(inPort.value) || 8900,
            kapasite: parseInt(inKapasite.value) || 4,
            notlar: inNotlar.value.trim(),
            ssh: ssh,
            kopru_ornek_id: kopruId ? parseInt(kopruId) : null,
            sifre_koru: (sifreMetin === "")});
    if (inSshSif) inSshSif.value = "";
    formGizle();
  });

  // ------------------------------------------------------------------
  // v2.4.45: SSH konsolu
  // ------------------------------------------------------------------
  function zamanMetni(ts) {
    try {
      const d = new Date((ts || 0) * 1000);
      const ik = (n) => (n < 10 ? "0" + n : "" + n);
      return ik(d.getHours()) + ":" + ik(d.getMinutes()) + ":" +
             ik(d.getSeconds());
    } catch (e) { return ""; }
  }

  function konsolKabi(sid) {
    return document.querySelector('.ai-konsol[data-ai-konsol="' + sid + '"]');
  }

  function konsolSatirEkle(sid, satirlar) {
    const kab = konsolKabi(sid);
    if (!kab) return;
    const govde = kab.querySelector(".ai-konsol-govde");
    if (!govde) return;
    // Kullanici yukari kaydirdiysa otomatik kaydirma yapilmaz
    const dipte = (govde.scrollHeight - govde.scrollTop -
                   govde.clientHeight) < 24;
    (satirlar || []).forEach((s) => {
      const sat = document.createElement("div");
      sat.className = "ai-konsol-satir akis-" + (s.akis || "cikti");
      const zm = document.createElement("span");
      zm.className = "zm";
      zm.textContent = zamanMetni(s.ts);
      const mt = document.createElement("span");
      mt.className = "mt";
      mt.textContent = s.metin || "";
      sat.appendChild(zm); sat.appendChild(mt);
      govde.appendChild(sat);
    });
    // Tarayici tarafinda da sinir: en fazla 1200 satir tutulur
    while (govde.childElementCount > 1200) govde.removeChild(govde.firstChild);
    if (dipte) govde.scrollTop = govde.scrollHeight;
  }

  function konsolBaslikGuncelle(sid) {
    const kab = konsolKabi(sid);
    if (!kab) return;
    const d = sshDurumlar[sid] || {};
    const et = kab.querySelector(".ai-konsol-durum");
    if (!et) return;
    if (d.calisiyor) {
      et.textContent = t("aiSshCalisiyor", "çalışıyor");
      et.className = "ai-konsol-durum calisiyor";
    } else if (d.cikis_kodu !== undefined && d.cikis_kodu !== null) {
      et.textContent = t("aiSshBitti", "bitti") + " (" + d.cikis_kodu + ")";
      et.className = "ai-konsol-durum bitti";
    } else {
      et.textContent = t("aiSshHazir", "bağlantı yok");
      et.className = "ai-konsol-durum";
    }
  }

  // KOPRU OTURUMLARI ICIN YOKLAMA
  //
  // Yerel (merkez surecindeki) SSH oturumlari satirlari kendiliginden
  // `ai_ssh_satir` ile iter. Kopru makinesindeki oturumlar ITMEZ:
  // kopru merkeze kendiliginden mesaj gondermez, merkez `ai_ssh_gecmis`
  // ile CEKER. Bu yuzden konsol penceresi acikken duzenli aralikla
  // sorulur; pencere kapaninca yoklama DURUR ki bant genisligi bosa
  // harcanmasin.
  const yoklamalar = {};

  function yoklamaBaslat(sid) {
    if (yoklamalar[sid]) return;
    const s = (sonSunucular || []).find((x) => String(x.id) === String(sid));
    if (!s || !s.kopru_ornek_id) return;   // yerel oturum: itme var
    yoklamalar[sid] = setInterval(() => {
      if (!konsolAcik[sid]) { yoklamaDurdur(sid); return; }
      gonder({tip: "ai_ssh_gecmis", id: sid});
    }, 2000);
  }

  function yoklamaDurdur(sid) {
    if (!yoklamalar[sid]) return;
    clearInterval(yoklamalar[sid]);
    delete yoklamalar[sid];
  }

  function konsolAcKapat(sid) {
    if (konsolAcik[sid]) {
      konsolAcik[sid] = false;
      yoklamaDurdur(sid);
      const kab = konsolKabi(sid);
      if (kab) kab.remove();
      dugmeleriTazele();
      return;
    }
    konsolAcik[sid] = true;
    // Satir DOM'unda konsol kabini olustur
    const sat = document.querySelector('.ai-satir[data-ai-sunucu="' + sid + '"]');
    if (!sat) return;
    const kab = document.createElement("div");
    kab.className = "ai-konsol";
    kab.setAttribute("data-ai-konsol", String(sid));
    const bas = document.createElement("div");
    bas.className = "ai-konsol-baslik";
    const bsl = document.createElement("span");
    bsl.innerHTML = '<i class="fa-solid fa-terminal"></i> ' +
                    t("aiSshKonsol", "SSH KONSOLU");
    const drm = document.createElement("span");
    drm.className = "ai-konsol-durum";
    const btnTemiz = document.createElement("button");
    btnTemiz.innerHTML = '<i class="fa-solid fa-eraser"></i>';
    btnTemiz.title = t("aiSshTemizle", "Ekranı temizle");
    btnTemiz.addEventListener("click", () => {
      const g = kab.querySelector(".ai-konsol-govde");
      if (g) g.innerHTML = "";
    });
    const btnKap = document.createElement("button");
    btnKap.innerHTML = '<i class="fa-solid fa-xmark"></i>';
    btnKap.title = t("ipKapat", "Kapat");
    btnKap.addEventListener("click", () => konsolAcKapat(sid));
    bas.appendChild(bsl); bas.appendChild(drm);
    bas.appendChild(btnTemiz); bas.appendChild(btnKap);
    const govde = document.createElement("div");
    govde.className = "ai-konsol-govde";
    kab.appendChild(bas); kab.appendChild(govde);
    sat.insertAdjacentElement("afterend", kab);
    konsolBaslikGuncelle(sid);
    dugmeleriTazele();
    // Gecmisi iste (pencere kapanip acilinca gecmis kaybolmasin)
    gonder({tip: "ai_ssh_gecmis", id: sid});
    yoklamaBaslat(sid);
  }

  function dugmeleriTazele() {
    (sonSunucular || []).forEach((s) => {
      const sat = document.querySelector(
        '.ai-satir[data-ai-sunucu="' + s.id + '"]');
      if (!sat) return;
      const d = sshDurumlar[s.id] || {};
      const bp = sat.querySelector(".ai-btn-ssh");
      if (bp) {
        bp.innerHTML = d.calisiyor
          ? '<i class="fa-solid fa-stop"></i>'
          : '<i class="fa-solid fa-play"></i>';
        bp.title = d.calisiyor
          ? t("aiSshDurdur", "SSH oturumunu durdur")
          : t("aiSshBaslat", "SSH ile bağlan ve başlat");
        bp.classList.toggle("tehlike", !!d.calisiyor);
      }
      const bk = sat.querySelector(".ai-btn-konsol");
      if (bk) bk.classList.toggle("etkin", !!konsolAcik[s.id]);
    });
  }

  function sshBaslatDurdur(s) {
    const d = sshDurumlar[s.id] || {};
    if (d.calisiyor) {
      gonder({tip: "ai_ssh_durdur", id: s.id});
      return;
    }
    if (!s.ssh_kullanici) {
      if (typeof window.uyariGoster === "function")
        window.uyariGoster(t("aiSshEksik",
          "SSH kullanıcı adı tanımlı değil. Düzenle ile ekleyin."), "uyari");
      formGoster(s);
      return;
    }
    // Konsol kapaliysa otomatik ac: kullanici ne oldugunu gormeli
    if (!konsolAcik[s.id]) konsolAcKapat(s.id);
    gonder({tip: "ai_ssh_baslat", id: s.id});
  }

  // ------------------------------------------------------------------
  // Liste cizimi
  // ------------------------------------------------------------------
  function sunucuSatir(s) {
    const sat = document.createElement("div");
    sat.className = "ai-satir";
    sat.setAttribute("data-ai-sunucu", String(s.id));

    const led = document.createElement("span");
    led.className = "ai-led " + (s.cevrimici ? "cevrimici" : "cevrimdisi");
    led.title = s.cevrimici ? t("aiCevrimici", "Çevrimiçi")
                            : t("aiCevrimdisi", "Çevrimdışı");
    sat.appendChild(led);

    const rozet = document.createElement("span");
    rozet.className = "ai-tip-rozet " + (s.tip === "nvidia" ? "nvidia" : "cpu");
    rozet.textContent = s.tip === "nvidia" ? "NVIDIA" : "CPU";
    sat.appendChild(rozet);

    const bilgi = document.createElement("div");
    bilgi.className = "ai-satir-bilgi";
    const ad = document.createElement("div");
    ad.className = "ad";
    ad.textContent = s.ad;
    const alt = document.createElement("div");
    alt.className = "alt";
    const akisSayi = (s.akislar || []).length;
    alt.textContent = s.host + ":" + s.port + "  ·  " +
      t("aiYuk", "Yük") + ": " + akisSayi + "/" +
      (s.kapasite_canli || s.kapasite || 0) +
      (s.ssh_kullanici ? "  ·  ssh " + s.ssh_kullanici + "@" +
        (s.ssh_port || 22) : "") +
      (s.notlar ? "  ·  " + s.notlar : "");
    bilgi.appendChild(ad); bilgi.appendChild(alt);
    sat.appendChild(bilgi);

    // Yuk cubugu
    const kap = Math.max(1, s.kapasite_canli || s.kapasite || 1);
    const yuk = document.createElement("div");
    yuk.className = "ai-yuk-cubuk";
    yuk.title = akisSayi + " / " + kap;
    const ic = document.createElement("div");
    ic.style.width = Math.min(100, Math.round(100 * akisSayi / kap)) + "%";
    yuk.appendChild(ic);
    sat.appendChild(yuk);

    const btnlar = document.createElement("div");
    btnlar.className = "ai-satir-btnlar";
    // v2.4.45: SSH play/stop
    const bp = document.createElement("button");
    bp.className = "ai-btn-ssh";
    bp.innerHTML = '<i class="fa-solid fa-play"></i>';
    bp.title = t("aiSshBaslat", "SSH ile bağlan ve başlat");
    bp.addEventListener("click", () => sshBaslatDurdur(s));
    // v2.4.45: konsol ac/kapa
    const bk = document.createElement("button");
    bk.className = "ai-btn-konsol";
    bk.innerHTML = '<i class="fa-solid fa-terminal"></i>';
    bk.title = t("aiSshKonsolAcKapat", "SSH konsolunu aç/kapat");
    bk.addEventListener("click", () => konsolAcKapat(s.id));
    const bd = document.createElement("button");
    bd.innerHTML = '<i class="fa-solid fa-pen"></i>';
    bd.title = t("btnDuzenle", "Düzenle");
    bd.addEventListener("click", () => formGoster(s));
    const bs = document.createElement("button");
    bs.className = "tehlike";
    bs.innerHTML = '<i class="fa-solid fa-trash"></i>';
    bs.title = t("btnSil", "Sil");
    bs.addEventListener("click", () => {
      const soru = t("aiSunucuSilOnay", "AI sunucusu silinsin mi?") +
                   " (" + s.ad + ")";
      if (typeof window.onayIste === "function") {
        window.onayIste(soru, () => gonder({tip: "ai_sunucu_sil", id: s.id}));
      } else if (confirm(soru)) {
        gonder({tip: "ai_sunucu_sil", id: s.id});
      }
    });
    btnlar.appendChild(bp); btnlar.appendChild(bk);
    btnlar.appendChild(bd); btnlar.appendChild(bs);
    sat.appendChild(btnlar);
    // v2.4.232: en sagda bagli oldugu kopru
    if (s.kopru_ornek_id != null && typeof window.kopruRozetOlustur === "function") {
      const kr = window.kopruRozetOlustur(s.kopru_ornek_id);
      if (kr) sat.appendChild(kr);
    }
    return sat;
  }

  // v2.4.232 (kullanici istegi): KOPRU GRUPLAMASI KALDIRILDI. AI
  // sunuculari her kipte duz listelenir; satir sonunda bagli oldugu
  // kopru rozeti gosterilir (window.kopruRozetOlustur).
  function bosSatir(metin) {
    const bos = document.createElement("div");
    bos.className = "ai-satir";
    bos.style.justifyContent = "center";
    bos.style.color = "var(--soluk)";
    bos.textContent = metin;
    return bos;
  }

  function listeCiz() {
    if (!liste) return;
    liste.innerHTML = "";
    if (!sonSunucular.length) {
      liste.appendChild(bosSatir(
        t("aiSunucuYok", "Kayıtlı AI sunucusu yok")));
      return;
    }
    sonSunucular.forEach((s) => liste.appendChild(sunucuSatir(s)));
  }

  window.aiSunucuListesiIsle = function (m) {
    sonSunucular = m.sunucular || [];
    window._aiSunucularSon = sonSunucular;
    listeCiz();
    sonSunucular.forEach((s) => {
      // Konsol acikti ise liste yenilendiginde yeniden cizilir
      if (konsolAcik[s.id]) {
        konsolAcik[s.id] = false;   // konsolAcKapat tekrar acacak
        konsolAcKapat(s.id);
      }
    });
    dugmeleriTazele();
  };

  // Kopru listesi degisince (kopru cevrimdisi oldu, yenisi katildi)
  // panel acikken gorunum tazelenir.
  if (typeof window.kopruListesiDinle === "function") {
    window.kopruListesiDinle(function () {
      if (pop.classList.contains("popup-gizli")) return;
      listeCiz();
      dugmeleriTazele();
      // Form acikken secici de tazelenir (kopru cevrimdisi olabilir).
      if (form && form.style.display !== "none" &&
          typeof window.kopruSeciciDoldur === "function") {
        const secili = kopruSec ? (kopruSec.value || null) : null;
        window.kopruSeciciDoldur(kopruAlan, kopruSec, secili);
      }
    });
  }

  // ------------------------------------------------------------------
  // v2.4.45: SSH yayinlari (ws.js -> buraya)
  // ------------------------------------------------------------------
  window.aiSshDurumIsle = function (m) {
    const sid = m.sunucu_id;
    if (sid === undefined || sid === null) return;
    sshDurumlar[sid] = Object.assign({}, sshDurumlar[sid] || {}, m);
    konsolBaslikGuncelle(sid);
    dugmeleriTazele();
    if (m.hata) {
      if (typeof window.uyariGoster === "function")
        window.uyariGoster(t("aiSshHata", "SSH hatası") + ": " + m.hata,
                           "kotu");
      // Hatayi konsola da yaz: kullanici konsolu acikken sebebini gorur
      konsolSatirEkle(sid, [{ts: Date.now() / 1000, akis: "hata",
                             metin: m.hata}]);
    }
  };

  window.aiSshSatirIsle = function (m) {
    konsolSatirEkle(m.sunucu_id, m.satirlar || []);
  };

  window.aiSshGecmisIsle = function (m) {
    const sid = m.sunucu_id;
    sshDurumlar[sid] = Object.assign({}, sshDurumlar[sid] || {}, m);
    const kab = konsolKabi(sid);
    if (kab) {
      const g = kab.querySelector(".ai-konsol-govde");
      if (g) g.innerHTML = "";
    }
    konsolSatirEkle(sid, m.satirlar || []);
    konsolBaslikGuncelle(sid);
    dugmeleriTazele();
  };

  // ------------------------------------------------------------------
  // Aktif izlemeler
  // ------------------------------------------------------------------
  function kameraAd(kid) {
    const k = (window._kameralarSon || []).find((x) => x.id === kid);
    return k ? k.ad : ("Kamera #" + kid);
  }
  window.aiIzlemeListesiIsle = function (m) {
    sonIzlemeler = m.izlemeler || [];
    window._aiIzlemelerSon = sonIzlemeler;
    if (typeof window.aiIzlemeDegisti === "function")
      window.aiIzlemeDegisti(sonIzlemeler);
    if (!izlListe) return;
    izlListe.innerHTML = "";
    if (!sonIzlemeler.length) {
      const bos = document.createElement("div");
      bos.className = "ai-satir";
      bos.style.justifyContent = "center";
      bos.style.color = "var(--soluk)";
      bos.textContent = t("aiIzlemeYok", "Aktif AI izlemesi yok");
      izlListe.appendChild(bos);
      return;
    }
    sonIzlemeler.forEach((iz) => {
      const sat = document.createElement("div");
      sat.className = "ai-satir";
      const led = document.createElement("span");
      // v2.4.9: akis gercekten canli mi? (isci kare aliyor mu)
      led.className = "ai-led " + (iz.canli ? "cevrimici" : "cevrimdisi");
      led.title = iz.canli ? t("aiAkisCanli", "Akış canlı")
                           : t("aiAkisYok", "Akış bekleniyor");
      sat.appendChild(led);
      const bilgi = document.createElement("div");
      bilgi.className = "ai-satir-bilgi";
      const ad = document.createElement("div");
      ad.className = "ad";
      ad.textContent = kameraAd(iz.kamera_id);
      const alt = document.createElement("div");
      alt.className = "alt";
      const sn = sonSunucular.find((s) => s.id === iz.sunucu_id);
      alt.textContent = (sn ? sn.ad : t("aiAtanmadi", "atama bekliyor")) +
                        (iz.protokol ? "  ·  " + iz.protokol : "");
      if (iz.hata) {
        alt.textContent += "  ·  " + iz.hata;
        alt.style.color = "var(--tehlike, #d9534f)";
        alt.title = iz.hata;
      }
      bilgi.appendChild(ad); bilgi.appendChild(alt);
      sat.appendChild(bilgi);
      const btnlar = document.createElement("div");
      btnlar.className = "ai-satir-btnlar";
      const bd = document.createElement("button");
      bd.className = "tehlike";
      bd.innerHTML = '<i class="fa-solid fa-stop"></i>';
      bd.title = t("aiIzlemeDurdur", "İzlemeyi durdur");
      bd.addEventListener("click", () =>
        gonder({tip: "ai_izleme_durdur", kamera_id: iz.kamera_id}));
      btnlar.appendChild(bd);
      sat.appendChild(btnlar);
      izlListe.appendChild(sat);
    });
  };

  // Disaridan izleme baslat/durdur (kamera_harita.js, kameralar.js)
  window.aiIzlemeBaslat = function (kameraId) {
    gonder({tip: "ai_izleme_baslat", kamera_id: kameraId});
  };
  window.aiIzlemeDurdur = function (kameraId) {
    gonder({tip: "ai_izleme_durdur", kamera_id: kameraId});
  };
  window.aiIzlemeAktifMi = function (kameraId) {
    return (window._aiIzlemelerSon || [])
      .some((iz) => iz.kamera_id === kameraId);
  };
})();
