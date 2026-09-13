// ============================================================
// GOKTUNGU GCS — WIDGET ALTYAPISI
// v2.4.29
//
// AMAC
// ----
// Yardim menusu altindaki "Widget" bolumunden acilip kapanan, sabit
// boyutlu, tasinabilir ve birbirine YAPISAN kucuk arayuz ogeleri.
//
// TASARIM KARARLARI
// -----------------
// 1) SABIT BOYUT: widget'lar boyutlandirilamaz. `popup_tasima.js`
//    icindeki `popupBoyutlandirilabilirYap` KULLANILMAZ; tasima mantigi
//    burada bagimsiz yazilmistir. Boylece pencere/dok sisteminin
//    kapsayici, sekme ve tutamac mantigi widget'lara hic dokunmaz.
//
// 2) GIZLEME: kok eleman `popup-gizli` sinifi ile gizlenir. Menubar'in
//    mevcut tik mekanizmasi (`.mb-popup-toggle` + `data-popup-hedef`)
//    tam olarak bu sinifi okur; bu nedenle menu tarafinda EK KOD
//    GEREKMEZ.
//
// 3) MIKNATIS: iki widget'in kenarlari MIK_ESIK pikselden yakinsa
//    tasinan widget hedefe hizalanir ve ayni GRUBA girer. Gruptaki
//    widget'lar beraber hareket eder. Baslikta "miknatisi boz" dugmesi
//    widget'i gruptan cikarir.
//
//    Grup yapisi: her widget'in `_grup` alani bir Set nesnesine isaret
//    eder; ayni gruptaki tum widget'lar AYNI Set ornegini paylasir.
//    Boylece uyelik sorgusu O(1) olur ve zincirleme birlesme
//    (A-B varken C, B'ye yapisirsa A-B-C) kendiliginden calisir.
//
// 4) KALICILIK: konum, acik/kapali ve widget'a ozel ayar (ornek: saatin
//    analog/dijital kipi) `localStorage: gcs_widget_durum` altinda
//    saklanir. Grup uyelikleri de saklanir; boylece yapistirilmis
//    duzen oturumlar arasi korunur.
//
//    DIKKAT (v2.4.28 dersi): kalici anahtar olarak OTURUMA OZEL kimlik
//    KULLANILMAZ. Widget kimlikleri sabit dizelerdir ("saat",
//    "havadurumu"), bu nedenle guvenle kalici anahtar olurlar.
//
// 5) EKRAN DISINA TASMA: pencere yeniden boyutlandiginda gorunur alanin
//    disinda kalan widget'lar iceri cekilir.
// ============================================================

(function(){
  "use strict";

  const DEPO = "gcs_widget_durum";
  const MIK_ESIK = 18;      // miknatis yakinlik esigi (px)
  const KENAR_PAY = 6;      // ekran kenarindan asgari bosluk (px)

  // widgetId -> { el, tanim, grup:Set|null }
  const kayit = new Map();
  let katman = null;

  // ----------------------------------------------------------
  // KALICILIK
  // ----------------------------------------------------------
  function durumOku(){
    try {
      const h = JSON.parse(localStorage.getItem(DEPO) || "{}");
      return (h && typeof h === "object") ? h : {};
    } catch (e) { return {}; }
  }
  function durumYaz(){
    try { localStorage.setItem(DEPO, JSON.stringify(durum)); } catch (e){}
  }

  // DIKKAT: `kaydet()` cagrildigi anda kayitli konum/ayar okunur, bu
  // nedenle durum aynasi modul yuklenirken hazir olmalidir. `baslat()`
  // icinde okumak, ilk kaydin varsayilan konuma dusmesine yol acardi.
  let durum = durumOku();
  function wDurum(id){
    if (!durum[id] || typeof durum[id] !== "object") durum[id] = {};
    return durum[id];
  }

  // ----------------------------------------------------------
  // KATMAN
  // ----------------------------------------------------------
  function katmanKur(){
    if (katman) return katman;
    katman = document.getElementById("widgetKatman");
    if (!katman){
      katman = document.createElement("div");
      katman.id = "widgetKatman";
      document.body.appendChild(katman);
    }
    return katman;
  }

  // ----------------------------------------------------------
  // GRUP MANTIGI
  // ----------------------------------------------------------
  // Ayni gruptaki widget'lar ayni Set ornegini paylasir.
  function grupBirlestir(a, b){
    const ka = kayit.get(a), kb = kayit.get(b);
    if (!ka || !kb) return;
    if (ka.grup && ka.grup === kb.grup) return;      // zaten ayni grup
    const yeni = new Set();
    if (ka.grup) ka.grup.forEach(x => yeni.add(x)); else yeni.add(a);
    if (kb.grup) kb.grup.forEach(x => yeni.add(x)); else yeni.add(b);
    yeni.add(a); yeni.add(b);
    // Tum uyeleri ayni Set ornegine bagla
    yeni.forEach(id => {
      const k = kayit.get(id);
      if (k) k.grup = yeni;
    });
    grupDurumYaz(yeni);
    grupGostergeTazele();
  }

  function grupCoz(id){
    const k = kayit.get(id);
    if (!k || !k.grup) return;
    const eski = k.grup;
    eski.delete(id);
    k.grup = null;
    // Tek uye kaldiysa grup anlamsizdir
    if (eski.size <= 1){
      eski.forEach(x => {
        const kk = kayit.get(x);
        if (kk) kk.grup = null;
        const d = wDurum(x);
        delete d.grup;
      });
      eski.clear();
    } else {
      grupDurumYaz(eski);
    }
    delete wDurum(id).grup;
    durumYaz();
    grupGostergeTazele();
  }

  function grupDurumYaz(set){
    // Grup uyelik listesi her uyenin kaydina yazilir (sirali, kararli)
    const uyeler = Array.from(set).sort();
    uyeler.forEach(x => { wDurum(x).grup = uyeler.slice(); });
    durumYaz();
  }

  function grupUyeleri(id){
    const k = kayit.get(id);
    if (!k) return [id];
    if (!k.grup || k.grup.size <= 1) return [id];
    return Array.from(k.grup);
  }

  function grupGostergeTazele(){
    kayit.forEach((k, id) => {
      const grupta = !!(k.grup && k.grup.size > 1);
      k.el.classList.toggle("widget-grupta", grupta);
      const btn = k.el.querySelector(".widget-mik-boz");
      if (btn) btn.style.display = grupta ? "" : "none";
    });
  }

  // ----------------------------------------------------------
  // KONUM
  // ----------------------------------------------------------
  function konumUygula(id, sol, ust){
    const k = kayit.get(id);
    if (!k) return;
    k.el.style.left = Math.round(sol) + "px";
    k.el.style.top = Math.round(ust) + "px";
    const d = wDurum(id);
    d.sol = Math.round(sol);
    d.ust = Math.round(ust);
  }

  function icerideCek(el, sol, ust){
    const g = el.getBoundingClientRect();
    const maxSol = window.innerWidth - g.width - KENAR_PAY;
    const maxUst = window.innerHeight - g.height - KENAR_PAY;
    return [
      Math.max(KENAR_PAY, Math.min(sol, Math.max(KENAR_PAY, maxSol))),
      Math.max(KENAR_PAY, Math.min(ust, Math.max(KENAR_PAY, maxUst))),
    ];
  }

  // ----------------------------------------------------------
  // MIKNATIS
  // ----------------------------------------------------------
  // Tasinan widget icin en yakin yapisma noktasini bulur.
  // Doner: { dSol, dUst, hedef } veya null
  //
  // Yapisma bicimleri (kenar hizalama ile birlikte):
  //   sag kenar  -> hedefin sol kenari      (yatay komsu)
  //   sol kenar  -> hedefin sag kenari
  //   alt kenar  -> hedefin ust kenari      (dikey komsu)
  //   ust kenar  -> hedefin alt kenari
  function yapismaBul(id, kutu){
    const kendiGrup = kayit.get(id) && kayit.get(id).grup;
    let enIyi = null;

    kayit.forEach((k, oid) => {
      if (oid === id) return;
      if (k.el.classList.contains("popup-gizli")) return;
      // Ayni gruptaki uyeye yapisma anlamsiz (beraber hareket ediyorlar)
      if (kendiGrup && kendiGrup.has(oid)) return;

      const h = k.el.getBoundingClientRect();

      // Yatay komsuluk: dikey olarak ORTUSMELI
      const dikeyOrtusme = Math.min(kutu.bottom, h.bottom) - Math.max(kutu.top, h.top);
      if (dikeyOrtusme > 0){
        // kendi sag kenari -> hedef sol kenari
        let d = h.left - kutu.right;
        if (Math.abs(d) <= MIK_ESIK){
          const aday = { dSol: d, dUst: h.top - kutu.top, hedef: oid,
                         uzaklik: Math.abs(d) + Math.abs(h.top - kutu.top) * 0.01 };
          if (!enIyi || aday.uzaklik < enIyi.uzaklik) enIyi = aday;
        }
        // kendi sol kenari -> hedef sag kenari
        d = h.right - kutu.left;
        if (Math.abs(d) <= MIK_ESIK){
          const aday = { dSol: d, dUst: h.top - kutu.top, hedef: oid,
                         uzaklik: Math.abs(d) + Math.abs(h.top - kutu.top) * 0.01 };
          if (!enIyi || aday.uzaklik < enIyi.uzaklik) enIyi = aday;
        }
      }

      // Dikey komsuluk: yatay olarak ORTUSMELI
      const yatayOrtusme = Math.min(kutu.right, h.right) - Math.max(kutu.left, h.left);
      if (yatayOrtusme > 0){
        // kendi alt kenari -> hedef ust kenari
        let d = h.top - kutu.bottom;
        if (Math.abs(d) <= MIK_ESIK){
          const aday = { dSol: h.left - kutu.left, dUst: d, hedef: oid,
                         uzaklik: Math.abs(d) + Math.abs(h.left - kutu.left) * 0.01 };
          if (!enIyi || aday.uzaklik < enIyi.uzaklik) enIyi = aday;
        }
        // kendi ust kenari -> hedef alt kenari
        d = h.bottom - kutu.top;
        if (Math.abs(d) <= MIK_ESIK){
          const aday = { dSol: h.left - kutu.left, dUst: d, hedef: oid,
                         uzaklik: Math.abs(d) + Math.abs(h.left - kutu.left) * 0.01 };
          if (!enIyi || aday.uzaklik < enIyi.uzaklik) enIyi = aday;
        }
      }
    });
    return enIyi;
  }

  // ----------------------------------------------------------
  // TASIMA
  // ----------------------------------------------------------
  function tasimaKur(id, el, tutmaAlani){
    let aktif = false, bx = 0, by = 0;
    // Tasinan tum uyelerin baslangic konumlari
    let baslangic = [];

    function bas(ev){
      if (ev.button !== undefined && ev.button !== 0) return;
      // Baslikta ki dugmeler tasima baslatmaz
      if (ev.target.closest("button")) return;
      aktif = true;
      bx = ev.clientX; by = ev.clientY;
      baslangic = grupUyeleri(id).map(uid => {
        const k = kayit.get(uid);
        const g = k.el.getBoundingClientRect();
        return { id: uid, sol: g.left, ust: g.top };
      });
      enUsteAl(id);
      el.classList.add("widget-tasiniyor");
      try { tutmaAlani.setPointerCapture(ev.pointerId); } catch(e){}
      ev.preventDefault();
    }

    function hareket(ev){
      if (!aktif) return;
      let dx = ev.clientX - bx;
      let dy = ev.clientY - by;

      // Miknatis: yalnizca TASINAN widget'in kendi kutusuna gore hesaplanir
      const kendi = baslangic.find(b => b.id === id);
      const g = el.getBoundingClientRect();
      const denemeKutu = {
        left: kendi.sol + dx, top: kendi.ust + dy,
        right: kendi.sol + dx + g.width, bottom: kendi.ust + dy + g.height,
      };
      const yap = yapismaBul(id, denemeKutu);
      if (yap){
        dx += yap.dSol;
        dy += yap.dUst;
        el.dataset.yapismaHedef = yap.hedef;
      } else {
        delete el.dataset.yapismaHedef;
      }

      baslangic.forEach(b => {
        const k = kayit.get(b.id);
        if (!k) return;
        const [s, u] = icerideCek(k.el, b.sol + dx, b.ust + dy);
        konumUygula(b.id, s, u);
      });
    }

    function bitir(ev){
      if (!aktif) return;
      aktif = false;
      el.classList.remove("widget-tasiniyor");
      try { tutmaAlani.releasePointerCapture(ev.pointerId); } catch(e){}
      const hedef = el.dataset.yapismaHedef;
      if (hedef){
        delete el.dataset.yapismaHedef;
        grupBirlestir(id, hedef);
      }
      durumYaz();
    }

    tutmaAlani.addEventListener("pointerdown", bas);
    tutmaAlani.addEventListener("pointermove", hareket);
    tutmaAlani.addEventListener("pointerup", bitir);
    tutmaAlani.addEventListener("pointercancel", bitir);
  }

  // Widget'i en uste al (widget'lar kendi arasinda siralanir;
  // pencere/dok sisteminin z sayacina KARISMAZ)
  let wz = 60;
  function enUsteAl(id){
    const k = kayit.get(id);
    if (!k) return;
    // Grup uyeleri birlikte yukselir, birbirlerine gore sirasi korunur
    grupUyeleri(id).forEach(uid => {
      const kk = kayit.get(uid);
      if (kk) kk.el.style.zIndex = String(++wz);
    });
  }

  // ----------------------------------------------------------
  // OLUSTURMA
  // ----------------------------------------------------------
  // tanim: {
  //   id, baslikAnahtar, baslik, ikon,
  //   genislik, yukseklik,
  //   govdeKur(govde, api),     // icerigi kurar
  //   ac(api), kapa(api)        // istege bagli yasam dongusu
  // }
  function kaydet(tanim){
    if (!tanim || !tanim.id) return null;
    if (kayit.has(tanim.id)) return kayit.get(tanim.id);
    katmanKur();

    const el = document.createElement("div");
    el.className = "widget popup-gizli";
    el.id = "widget_" + tanim.id;
    el.style.width = (tanim.genislik || 200) + "px";
    el.style.height = (tanim.yukseklik || 160) + "px";

    const bas = document.createElement("div");
    bas.className = "widget-baslik";
    const ad = document.createElement("span");
    ad.className = "widget-ad";
    if (tanim.baslikAnahtar) ad.setAttribute("data-i18n", tanim.baslikAnahtar);
    ad.textContent = tanim.baslik || tanim.id;
    bas.appendChild(ad);

    const bosluk = document.createElement("span");
    bosluk.className = "widget-bosluk";
    bas.appendChild(bosluk);

    // ------------------------------------------------------------
    // v2.4.33: TEKIL YENILEME DUGMESI (BASLIKTA, KIRMIZI)
    // ------------------------------------------------------------
    // Kullanici istegi: "Widget'lardaki yenileme her widget'ta ayni
    // olsun, header'a ikon olarak gelsin ve kirmizi olsun."
    //
    // Onceki surumde her widget kendi yenileme dugmesini KENDI
    // GOVDESINDE ayri bir bicimle ciziyordu (hava-bayat-btn,
    // konum-bayat-btn, wg-pilot-yenile) — ucu de farkli konum, farkli
    // boyut ve farkli renkteydi; hava/konum widget'larinda dugme
    // govdenin altinda tam genislikte bir seride oturuyordu ve icerik
    // yuksekligini yiyordu.
    //
    // Artik dugme baslikta tek bir yerde yasiyor. Widget modulleri
    // `api.yenilemeKur(cb)` ile geri cagirmayi baglar,
    // `api.yenileGoster(true/false)` ile gorunurlugu yonetir.
    const yenileBtn = document.createElement("button");
    yenileBtn.type = "button";
    yenileBtn.className = "widget-yenile";
    yenileBtn.innerHTML = '<i class="fa-solid fa-rotate-right"></i>';
    yenileBtn.style.display = "none";
    // pointerdown: tasima mantigi baslik uzerinde pointerdown dinler,
    // bu nedenle olayin yayilmasi burada kesilmeli (yoksa dugmeye
    // basmak widget'i suruklemeye baslar).
    yenileBtn.addEventListener("pointerdown", (ev) => {
      ev.stopPropagation();
      ev.preventDefault();
    });
    bas.appendChild(yenileBtn);

    // Miknatisi boz (yalniz grupta iken gorunur)
    const mikBtn = document.createElement("button");
    mikBtn.className = "widget-mik-boz";
    mikBtn.title = ((typeof D === "function") ? D().wgMiknatisBoz : "")
                 || "M\u0131knat\u0131s\u0131 boz";
    mikBtn.innerHTML = '<i class="fa-solid fa-link-slash"></i>';
    mikBtn.style.display = "none";
    mikBtn.addEventListener("click", (ev) => { ev.stopPropagation(); grupCoz(tanim.id); });
    bas.appendChild(mikBtn);

    const kapatBtn = document.createElement("button");
    kapatBtn.className = "widget-kapat";
    kapatBtn.title = "Kapat";
    kapatBtn.innerHTML = '<i class="fa-solid fa-xmark"></i>';
    kapatBtn.addEventListener("click", (ev) => { ev.stopPropagation(); gizle(tanim.id); });
    bas.appendChild(kapatBtn);

    el.appendChild(bas);

    const govde = document.createElement("div");
    govde.className = "widget-govde";
    el.appendChild(govde);

    katman.appendChild(el);

    const k = { el, tanim, grup: null, govde };
    kayit.set(tanim.id, k);

    // Widget'a ozel ayar okuma/yazma API'si
    const api = {
      id: tanim.id,
      govde: govde,
      ayarOku: function(ad, varsayilan){
        const d = wDurum(tanim.id);
        return (d.ayar && ad in d.ayar) ? d.ayar[ad] : varsayilan;
      },
      ayarYaz: function(ad, deger){
        const d = wDurum(tanim.id);
        if (!d.ayar) d.ayar = {};
        d.ayar[ad] = deger;
        durumYaz();
      },
      gorunurMu: function(){ return !el.classList.contains("popup-gizli"); },
      // v2.4.33: baslikta duran tekil yenileme dugmesi
      // yenilemeKur(cb): dugmeye basildiginda cagrilacak islevi baglar.
      //   Ayni widget icin birden fazla cagri son islevi gecerli kilar.
      yenilemeKur: function(cb, baslikYazi){
        k._yenileCb = (typeof cb === "function") ? cb : null;
        if (baslikYazi) yenileBtn.title = baslikYazi;
      },
      // yenileGoster(true): dugmeyi gorunur kilar (veri bayat).
      // yenileGoster(false): gizler (veri guncel).
      yenileGoster: function(gorunur, baslikYazi){
        yenileBtn.style.display = gorunur ? "" : "none";
        if (baslikYazi) yenileBtn.title = baslikYazi;
      },
      // Yenileme suruyor gorsel geri bildirimi (ikon doner)
      yenileDonuyor: function(donuyor){
        yenileBtn.classList.toggle("donuyor", !!donuyor);
      },
    };
    k.api = api;

    // Yenileme dugmesi tiklamasi: kayit uzerindeki geri cagirmaya git.
    // (click, pointerdown'dan sonra tetiklenir; pointerdown yalnizca
    // surukleme yayilimini kesmek icin dinleniyor.)
    yenileBtn.addEventListener("click", (ev) => {
      ev.stopPropagation();
      if (typeof k._yenileCb === "function") k._yenileCb();
    });

    if (typeof tanim.govdeKur === "function") tanim.govdeKur(govde, api);

    tasimaKur(tanim.id, el, bas);

    // Kayitli konum (yoksa varsayilan yerlesim)
    const d = wDurum(tanim.id);
    if (typeof d.sol === "number" && typeof d.ust === "number"){
      const [s, u] = icerideCek(el, d.sol, d.ust);
      konumUygula(tanim.id, s, u);
    } else {
      const n = kayit.size - 1;
      konumUygula(tanim.id, window.innerWidth - (tanim.genislik || 200) - 24,
                            96 + n * ((tanim.yukseklik || 160) + 12));
    }
    return k;
  }

  // ----------------------------------------------------------
  // GOSTER / GIZLE
  // ----------------------------------------------------------
  function goster(id){
    const k = kayit.get(id);
    if (!k) return;
    k.el.classList.remove("popup-gizli");
    wDurum(id).acik = true;
    durumYaz();
    // Konumu gorunur alana cek (pencere kucuklmus olabilir)
    const g = k.el.getBoundingClientRect();
    const [s, u] = icerideCek(k.el, g.left, g.top);
    konumUygula(id, s, u);
    enUsteAl(id);
    if (typeof k.tanim.ac === "function") k.tanim.ac(k.api);
    if (typeof window.popupTikleriGuncelle === "function") window.popupTikleriGuncelle();
  }

  function gizle(id){
    const k = kayit.get(id);
    if (!k) return;
    k.el.classList.add("popup-gizli");
    wDurum(id).acik = false;
    durumYaz();
    if (typeof k.tanim.kapa === "function") k.tanim.kapa(k.api);
    if (typeof window.popupTikleriGuncelle === "function") window.popupTikleriGuncelle();
  }

  function degistir(id){
    const k = kayit.get(id);
    if (!k) return;
    if (k.el.classList.contains("popup-gizli")) goster(id); else gizle(id);
  }

  function acikMi(id){
    const k = kayit.get(id);
    return !!(k && !k.el.classList.contains("popup-gizli"));
  }

  // ----------------------------------------------------------
  // BASLATMA
  // ----------------------------------------------------------
  let baslatildi = false;
  function baslat(){
    if (baslatildi) return;
    baslatildi = true;
    katmanKur();

    // Kayitli gruplari geri kur
    kayit.forEach((k, id) => {
      const d = wDurum(id);
      if (Array.isArray(d.grup) && d.grup.length > 1){
        // Yalnizca kayitli olan uyeleri al
        const uyeler = d.grup.filter(x => kayit.has(x));
        if (uyeler.length > 1){
          for (let i = 1; i < uyeler.length; i++) grupBirlestir(uyeler[0], uyeler[i]);
        }
      }
    });

    // Kayitli acik durumlari uygula
    kayit.forEach((k, id) => {
      if (wDurum(id).acik) goster(id);
    });

    grupGostergeTazele();

    // Menu ogeleri
    document.querySelectorAll(".mb-widget-toggle[data-widget]").forEach(oge => {
      oge.addEventListener("click", (ev) => {
        ev.stopPropagation();
        degistir(oge.dataset.widget);
        if (typeof window.menubarKapat === "function") window.menubarKapat();
        else document.querySelectorAll(".mb-item.acik").forEach(m => m.classList.remove("acik"));
      });
    });

    // Pencere boyutu degisince iceri cek
    window.addEventListener("resize", () => {
      kayit.forEach((k, id) => {
        if (k.el.classList.contains("popup-gizli")) return;
        const g = k.el.getBoundingClientRect();
        const [s, u] = icerideCek(k.el, g.left, g.top);
        konumUygula(id, s, u);
      });
      durumYaz();
    });
  }

  // ----------------------------------------------------------
  // DISA ACILAN API
  // ----------------------------------------------------------
  // ----------------------------------------------------------
  // KENDILIGINDEN BASLATMA
  // Widget modulleri bu betikten SONRA yuklenir ve `kaydol()` cagirir.
  // Bu nedenle baslatma bir sonraki olay dongusune (microtask sonrasi)
  // birakilir; boylece tum kayitlar tamamlanmis olur.
  // ----------------------------------------------------------
  function kendiliginden(){
    // Kayitli modulleri bagla (varsa)
    try { if (window.WidgetSaat && window.WidgetSaat.kaydol) window.WidgetSaat.kaydol(); } catch(e){}
    try { if (window.WidgetHava && window.WidgetHava.kaydol) window.WidgetHava.kaydol(); } catch(e){}
    // v2.4.32
    try { if (window.WidgetKonum && window.WidgetKonum.kaydol) window.WidgetKonum.kaydol(); } catch(e){}
    try { if (window.WidgetPusula && window.WidgetPusula.kaydol) window.WidgetPusula.kaydol(); } catch(e){}
    try { if (window.WidgetPilotlar && window.WidgetPilotlar.kaydol) window.WidgetPilotlar.kaydol(); } catch(e){}
    // v2.4.33
    try { if (window.WidgetSayac && window.WidgetSayac.kaydol) window.WidgetSayac.kaydol(); } catch(e){}
    // v2.4.34
    try { if (window.WidgetKaynaklar && window.WidgetKaynaklar.kaydol) window.WidgetKaynaklar.kaydol(); } catch(e){}
    baslat();
  }
  if (document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", function(){ setTimeout(kendiliginden, 0); });
  } else {
    setTimeout(kendiliginden, 0);
  }

  // ------------------------------------------------------------
  // v2.4.33: TUM WIDGET'LARDA DIL TAZELEME
  // ------------------------------------------------------------
  // `i18n.js -> applyLanguage()` sonunda cagrilir. Widget modulleri
  // `dilTazele` geri cagrisini tanim nesnesinde bildirir; burada
  // yalnizca ACILMIS olanlar tazelenir (kapali widget'in DOM'u
  // olusmus olsa bile govdesi henuz kurulmamis olabilir).
  function dilTazeleTumu(){
    kayit.forEach((k) => {
      if (!k || !k.tanim || typeof k.tanim.dilTazele !== "function") return;
      try { k.tanim.dilTazele(); } catch (e) {}
    });
    // NOT: baslik yenileme dugmesinin ipucu metni burada
    // ayarLANMAZ. Dugmenin `title` degeri onu KURAN widget'a aittir
    // (her widget kendi metnini `yenilemeKur`/`yenileGoster` ile
    // gecirir); dolayisiyla ceviri sorumlulugu da widget'in kendi
    // `dilTazele` islevindedir. Buradan yazmak, widget'a ozgu
    // metni genel bir metinle ezme riski tasir.
  }

  window.Widget = {
    kaydet: kaydet,
    goster: goster,
    dilTazeleTumu: dilTazeleTumu,
    gizle: gizle,
    degistir: degistir,
    acikMi: acikMi,
    baslat: baslat,
    grupUyeleri: grupUyeleri,
    grupCoz: grupCoz,
    grupBirlestir: grupBirlestir,
    MIK_ESIK: MIK_ESIK,
    _kayit: kayit,
  };
})();
