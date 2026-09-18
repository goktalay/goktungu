// =================================================================
// GOKTUNGU - WEBSOCKET BAGLANTISI + MESAJ ISLEME + BASLATMA
// Bu dosya index.html'den mekanik olarak ayrilmistir; yukleme sirasi
// index.html'deki <script> sirasina baglidir (klasik script, ortak scope).
// =================================================================
// WEBSOCKET
// ---------------------------------------------------------------
const wsDurum = document.getElementById("wsDurum");

// FAZ20-OFFLINE-KAMERA-OTURUM: Canlı MJPEG URL'si yalnız kamera kimliği
// taşır. WebSocket oturum jetonu URL'ye yazılmaz; aynı origin'e HTTPS/yerel
// HTTP üzerinden Authorization başlığıyla verilir ve sunucu HttpOnly çerez
// üretir. Başarısızlık görüntü hattını açmaz.
async function kameraOturumuAc(jeton){
  if (!jeton || typeof jeton !== "string") return false;
  try {
    const yanit = await fetch(window.appYolu("/api/istemci/kamera_oturum"), {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + jeton
      },
      body: "{}"
    });
    return !!yanit.ok;
  } catch (e) {
    return false;
  }
}

// Sunucu tarafindaki WS_PORTLAR listesiyle ayni sirada olmali
const WS_PORTLAR = [8765, 8766, 8777, 9765];
const WSS_PORT = 9443; // sunucudaki WSS_PORT sabitiyle ayni olmali
let wsPortIdx = 0;      // bagli kalinan port
let hicBaglanmadi = true;

// =================================================================
// TELEMETRI ISLEME — ALT SISTEM YALITIMI (v2.4.30)
// -----------------------------------------------------------------
// v2.4.29'da tum telemetri alt sistemleri tek bir `onmessage` govdesi
// icinde ZINCIRLEME cagriliyordu. Bir alt sistemde atilan hata (olcum:
// radar ikonunda `TypeError`) govdenin geri kalanini SESSIZCE dusuruyor,
// dolayisiyla ayni pakette daha SONRA gelen dron dongusu hic
// calismiyordu — kullaniciya "dron panele dusmuyor" olarak yansidi.
//
// Cozum: her alt sistem kendi `try/catch` kabuklarinda calisir. Bir
// alt sistemin arizasi digerlerini asla etkilemez. Hatalar bogulmaz;
// alt sistem adiyla birlikte konsola bir kez yazilir (spam onlemek icin
// ayni imza tekrar bildirilmez).
// =================================================================
const _telHataGorulen = new Set();

function _guvenli(ad, fn){
  try {
    fn();
  } catch (e){
    const imza = ad + "|" + (e && e.message ? e.message : String(e));
    if (!_telHataGorulen.has(imza)){
      _telHataGorulen.add(imza);
      console.error("[TELEMETRI] '" + ad + "' alt sistemi hata verdi; " +
                    "diger alt sistemler etkilenmeden surdu:", e);
    }
  }
}

function telemetriIsle(m){
  _guvenli("baglanti_durumlari", () => {
    if (m.baglanti_durumlari) baglantiDurumlariIsle(m.baglanti_durumlari);
  });

  // Replay mesajindaki radar durumu gecmis kayittir; canli radar
  // panelini (baglanti/ayar/saglik) replay verisiyle ezme
  _guvenli("radar_paneli", () => {
    // v2.4.190: coklu radar — liste geldiyse secili radarin durumu panele
    // gider; eski tek `radar` alani yalniz liste yoksa kullanilir.
    if (!m.replay){
      if (m.radarlar && typeof radarListesiGuncelle === "function")
        radarListesiGuncelle(m.radarlar, m.radar);
      else if (m.radar) radarPaneliGuncelle(m.radar);
    }
  });

  // M50 HVS SDK Merkezde yüklenmez; bu alan yalnız yetkili saha
  // Köprüsünün arındırılmış durum/yerel akış özetidir. Bir hata diğer
  // telemetri bileşenlerini etkilemez.
  _guvenli("m50_paneli", () => {
    // v2.4.191: coklu EO — liste geldiyse secili cihazin paketi panele gider.
    // v2.4.200: menu bayragi LISTEDEN ONCE ve ayri korumada uygulanir;
    // liste cizimi hata verse bile Elektro-Optik menusu kapali kalmaz
    // (kullanici bildirimi: "F5'te once gorunuyor sonra kalkiyor").
    if (!m.replay && Array.isArray(m.eo_cihazlar) && typeof window.m50YerelDurum === "function"){
      try { window.m50YerelDurum(m.eo_cihazlar.some(c => c && c.yerel_sdk)); } catch (e) {}
    }
    if (!m.replay && m.eo_cihazlar && typeof window.eoListesiGuncelle === "function")
      window.eoListesiGuncelle(m.eo_cihazlar, m.m50);
    else if (m.m50 && !m.replay && typeof m50PaneliGuncelle === "function")
      m50PaneliGuncelle(m.m50);
  });

  // Islenmis izler backend takipcisinden gelir (radar bagli olmasa da
  // suzulen izler yasamaya devam eder). Replay aktifken canli yayinda
  // radar alanlari gelmez; haritayi replay verisi besler, ezme.
  // v2.4.229 KOK NEDEN (GRCON: 'replayAktif is not defined' her telemetride): kayit.js 2.4.227'de kaldirildi
  const _replayAktif = (typeof replayAktif !== "undefined") && replayAktif;
  if (!(_replayAktif && !m.replay)){
    _guvenli("radar_hedefleri", () => radarHedefleriGuncelle(m.radar_izler || []));
    _guvenli("yetim_izler",     () => yetimIzleriCiz(m.yetim_izler || []));
    _guvenli("grafik",          () => grafikOrnekle((m.radar_izler || []).length));
  }

  // v2.4.227: kayit/replay/filtre panelleri kaldirildi (kayit.js, filtreler.js yuklenmez)
  _guvenli("kayit_durum",     () => { if (m.kayit_durum && typeof kayitDurumGuncelle === "function") kayitDurumGuncelle(m.kayit_durum); });
  _guvenli("replay_durum",    () => { if (m.replay_durum && typeof replayDurumGuncelle === "function") replayDurumGuncelle(m.replay_durum); });
  _guvenli("takipci_ayarlar", () => { if (m.takipci_ayarlar && typeof takipciAyarSenkron === "function") takipciAyarSenkron(m.takipci_ayarlar); });
  _guvenli("konsol",          () => { if (m.konsol) konsolGuncelle(m.konsol); });

  // DRONLAR — en kritik alt sistem.
  // Baglanti kesildi: sunucu bos dron listesi gonderiyorsa tum UI'yi temizle.
  // Replay mesajlarinda dronlar: [] gonderilir; canli dron verisini
  // silmemek icin replay mesajlarinda dron guncelleme atlanir.
  if (!m.replay){
    _guvenli("dron_renkler", () => {
      // Backend'den gelen kalici dron renkleri (UID/ID eslesmeli)
      if (m.dron_renkler) window.dronRenkler = m.dron_renkler;
    });
    const gelenDronlar = m.dronlar || [];
    window.dronlarSon = gelenDronlar;   // v2.4.220: harita cevrimici listesi
    _guvenli("kamera_canli", () => {
      if (typeof window.haritaKameraCanliIsle === "function") window.haritaKameraCanliIsle(m.kamera_canli || []);
    });
    _guvenli("dron_temizle", () => {
      if (gelenDronlar.length === 0 && Object.keys(sonVeri).length > 0)
        tumDronlariTemizle();
    });
    // Her dron AYRI yalitilir: bir dronun bozuk verisi digerlerini
    // panelden dusurmesin.
    for (const d of gelenDronlar){
      _guvenli("dron_" + d.sysid, () => {
        sonVeri[d.sysid] = d;
        varlikGuncelle(d);
      });
    }
    // v2.4.245 (kullanici: "GRCON'dan sanal dronu silince Bagliantisi
    // Bilinmeyen altina geliyor"): sunucu bir dronu listeden DUSURDUGUNDE
    // (baglanti silindi/durduruldu, SITL kapandi) istemciye bir daha o
    // dron icin paket gelmez; `varlikGuncelle` cagrilmadigi icin 10 sn'lik
    // silme zamanlayicisi da hic kurulmaz ve kart "Baglantisi bilinmeyen"
    // grubunda sonsuza dek kalirdi. Sunucu listesi kesindir: listede
    // olmayan her dronun karti HEMEN silinir.
    _guvenli("dron_kaybolan", () => {
      if (typeof dronSil !== "function") return;
      const gelen = new Set(gelenDronlar.map(d => String(d.sysid)));
      for (const sysid of Object.keys(sonVeri)){
        if (gelen.has(String(sysid))) continue;
        delete sonVeri[sysid];
        try { dronSil(parseInt(sysid, 10)); } catch (e) {}
      }
      if (typeof dronKartlar === "object" && dronKartlar){
        for (const sysid of Object.keys(dronKartlar)){
          if (!gelen.has(String(sysid))) { try { dronSil(parseInt(sysid, 10)); } catch (e) {} }
        }
      }
    });
    // v2.4.33: dron kartlarini bagli olduklari baglanti grubuna
    // yerlestirir. Dron dongusunden SONRA cagrilir: kartlar
    // varlikGuncelle icinde uretildigi icin, once cagrilirsa
    // yerlestirilecek kart henuz DOM'da olmaz.
    _guvenli("dron_baglanti_eslem", () => {
      if (typeof window.dronBaglantiEslemGuncelle === "function")
        window.dronBaglantiEslemGuncelle(gelenDronlar);
    });
    // v2.5.0: YAKINLIK KALKANI. Harita ikonunun cevresinde, YALNIZ
    // acik yonlerde 3B kalkan kabugu cizer ve menzil metresini yazar.
    // Dron dongusunden SONRA cagrilir: kalkan varliklari dronun harita
    // entity'sine baglanir, entity varlikGuncelle icinde uretilir.
    // _guvenli sarmalayicisi zorunlu: kalkan cizimindeki bir hata
    // dron panelini dusurmemeli.
    _guvenli("yakinlik_kalkan", () => {
      if (typeof window.dpxKalkanGuncelle !== "function") return;
      for (const d of gelenDronlar) window.dpxKalkanGuncelle(d);
    });
  }

  _guvenli("gorev_telemetri", () => {
    if (typeof window.gorevTelemetriIsle === "function")
      window.gorevTelemetriIsle(m);
  });
  _guvenli("dron_takipler", () => {
    if (m.dron_takipler && typeof window.dronTakipDurumIsle === "function")
      window.dronTakipDurumIsle(m.dron_takipler);
  });
  _guvenli("angajman", () => {
    if (typeof window.angajmanCanliGuncelle === "function")
      window.angajmanCanliGuncelle(m.angajmanlar || {});
  });
  _guvenli("suru", () => {
    if (typeof window.suruTelemetriIsle === "function")
      window.suruTelemetriIsle(m.suru || null);
  });
}

function wsBaglan(){
  const port = WS_PORTLAR[wsPortIdx];
  const host = location.hostname || "localhost";
  try {
    if (/\.manus\.computer$/.test(host)) {
      // Gelistirme test proxysi: WS ayri alt alan uzerinden wss ile
      ws = new WebSocket("wss://" + host.replace(/^\d+-/, "8765-"));
    } else if (location.pathname.indexOf("/app/") === 0
               || /^app\./i.test(host)) {
      // IS-WSTUNEL: KONAK temelli secim.  Alt alan adi gecisinden
      // sonra sayfa `app.goktungu.com/` KOK yoldan sunuluyor ve
      // `pathname` artik `/app/...` DEGIL.  Salt yol kosulu bu
      // durumda yanlis dala dusuyor ve istemci 9443 KOK yoluna
      // baglaniyordu; orasi KOPRU protokolu (ilk mesaj `merhaba`
      // bekler) oldugu icin arayuz "Sunucu baglantisi yok"
      // gosteriyordu (olculdu 18 Agu 2026).
      // MERKEZ KIPI: sayfa /app/ altindan geldi. Baglanti, sayfayi
      // hangi ADRES ve PORTTAN aldiysak ORADAN kurulur (location.host
      // portu da icerir). NEDEN: mobil operator aglari ve kurum
      // guvenlik duvarlari 9443 gibi standart disi portlari kapatir;
      // sahada telefonda "Sunucu baglantisi yok" hatasi TAM BU YUZDEN
      // alindi. Merkez, 443 uzerinde /app/ws yolunda WS tuneli sunar.
      const sema = location.protocol === "https:" ? "wss://" : "ws://";
      ws = new WebSocket(sema + location.host + "/app/ws");
    } else if (location.protocol === "https:") {
      // HTTPS altinda karisik icerik engellenir: guvenli WSS kullan
      // IS-WSTUNEL: arayuz vekili YALNIZ `/app/ws` yolunda
      // sunulur; kok yol kopru protokoludur.  Yol eklenmezse
      // baglanti kurulur ama uygulama iletisimi HIC olmaz.
      ws = new WebSocket("wss://" + host + ":" + WSS_PORT
                         + "/app/ws");
    } else {
      ws = new WebSocket("ws://" + host + ":" + port);
    }
  } catch(err) {
    wsDurum.textContent = D().wsKoptu;
    wsDurum.className = "f-kotu";
    setTimeout(wsBaglan, 3000);
    return;
  }

  ws.onopen = () => {
    hicBaglanmadi = false;
    wsDurum.textContent = D().wsBagli(port);
    wsDurum.className = "f-iyi";
    if (typeof siniflandirmaDurumSorgula === "function")
      siniflandirmaDurumSorgula();
    // v2.4.51: veritabani yapilandirmasini sor. Yanit (pg_durum)
    // sihirbazin acilip acilmayacagina karar verir. GIRIS EKRANINDAN
    // ONCE calisir: veritabani yoksa kullanici dogrulanamaz.
    if (typeof window.pgDurumSor === "function") window.pgDurumSor();
    // FAZ18-IS8-GIRIS-PENCERESI: OTOMATIK GIRISI HEMEN DENE.
    // `setInterval(otomatikGirisDene, 800)` ilk denemeyi 800 ms'ye
    // kadar geciktiriyordu. Perde artik baslangicta gizli oldugu
    // icin bu gecikme kullaniciya BOS ARAYUZ olarak gorunurdu.
    // Zamanlayici korunur (yeniden deneme icin gerekli), yalniz ilk
    // deneme one alinir.
    if (typeof otomatikGirisDene === "function") otomatikGirisDene();
    // v2.5.18: imzali yerel guncelleme denetimi arka planda baslar.
    // Baglanti yoksa veya guncelleyici hazir degilse operasyonu bozmaz.
    if (typeof window.guncellemeDurumSor === "function") window.guncellemeDurumSor();
  };
  ws.onclose = () => {
    wsDurum.textContent = D().wsKoptu;
    wsDurum.className = "f-kotu";
    // v2.4.227: eski radar paneli dugmesi kaldirildi (radar_pencere.js kendi durumunu telemetriden okur)
    // Henuz hic baglanamadiysak siradaki aday portu dene,
    // once baglanip koptuysak ayni portta bekle
    if (hicBaglanmadi) wsPortIdx = (wsPortIdx + 1) % WS_PORTLAR.length;
    // FAZ18-IS8-GIRIS-PENCERESI: KIMLIK TAZELEME ISARETI.
    // Sunucudaki oturum baglami WS baglanti nesnesinin kimligine
    // baglidir; baglanti kopunca o baglam yok olur. Bu bayrak
    // `otomatikGirisDene` kapisini asar ve yeni baglantida jeton
    // TEKRAR gonderilir. `oturum` ve arayuz durumu BOZULMAZ:
    // kullanici profil rozetini ve panellerini kaybetmez, yalniz
    // kimlik sessizce tazelenir.
    window.kimlikTazeleGerekli = true;
    setTimeout(wsBaglan, hicBaglanmadi ? 500 : 2000);
  };
  ws.onerror = () => ws.close();

  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.tip === "guncelleme_durum"){
      if (typeof window.guncellemeDurumIsle === "function")
        window.guncellemeDurumIsle(m);
    } else if (m.tip === "guncelleme_sonuc"){
      if (typeof window.guncellemeSonucIsle === "function")
        window.guncellemeSonucIsle(m);
    } else if (m.tip === "portlar"){
      portlariDoldur(m.portlar);
    } else if (m.tip === "baglanti_listesi"){
      baglantiListesiIsle(m);
    } else if (m.tip === "baglanti_hata"){
      if (m.hata){
        bagPerde.classList.remove("popup-gizli");
        bagEkleHataGoster(m.hata);
        // v2.4.39: SITL ikilisi eksikse hata metni tek basina cozum
        // sunmuyor. Kullaniciya dogrudan indirme eylemi verilir.
        if (typeof bagSitlIndirmeGerekli === "function" &&
            bagSitlIndirmeGerekli(m.hata))
          bagSitlIndirDugmesiEkle();
      }
    } else if (m.tip === "sitl_durum"){
      // FAZ18-SIHIRBAZ: sihirbazin 2. adimi tipe ozgu SITL
      // hazirlik durumunu bu yanittan ogrenir. Ikili varsa
      // indirme HIC baslamaz.
      if (typeof window.sitlDurumGeldi === "function")
        window.sitlDurumGeldi(m);
    } else if (m.tip === "sitl_indirme"){
      // v2.4.39: SITL ikilisi ~30 MB; indirme dakikalar surebilir.
      // Kullanici geri bildirim gormezse programin takildigini sanar.
      if (typeof window.sitlIndirmeDurum === "function")
        window.sitlIndirmeDurum(m);
      // FAZ18-SIHIRBAZ: ayni duyuru sihirbazin ilerleme
      // cubuguna da akar. Eski kurtarma dugmesi akisi
      // korunur; iki dinleyici birbirini etkilemez.
      if (typeof window.sitlSihirbazIndirme === "function")
        window.sitlSihirbazIndirme(m);
    } else if (m.tip === "hedef_sonuc"){
      /* FAZ20-IS93: bu tip DAHA ONCE HIC ISLENMIYORDU (olculdu).
         Is 91/92'de eklenen hedef/angajman kuyrugu sunucuda calisiyor
         ama arayuze hic baglanmamisti; komut gonderilse yanit sessizce
         duserdi. */
      if (m.komut === "hedef_liste" &&
          typeof window.goruntuHedefYanit === "function")
        window.goruntuHedefYanit(m);
      else if (typeof window.angajmanKuyrukYanit === "function")
        window.angajmanKuyrukYanit(m);
    } else if (m.tip === "merkez_sunucular"){
      // v2.4.53: merkezden gelen "O AN acik" sunucu listesi. Cagriyi
      // GCS sunucusu yapar; tarayici merkez sifresini hic gormez.
      if (typeof window.merkezSunucularGeldi === "function")
        window.merkezSunucularGeldi(m);
    } else if (m.tip === "merkez_dogrula_sonuc"){
      // v2.4.53: Program Ayarlari -> Merkez Sunucu hesap sinamasi
      if (typeof window.merkezDogrulaSonuc === "function")
        window.merkezDogrulaSonuc(m);
    } else if (m.tip === "merkez_kayit_sonuc"){
      // v2.4.53 Faz 12: bu kurulumun merkeze sunucu olarak kayit
      // sonucu. Govde {kimlik, kopru} tasir; `gizli` ASLA gelmez.
      if (typeof window.merkezKayitSonuc === "function")
        window.merkezKayitSonuc(m);
    } else if (m.tip === "merkez_kopru_durum"){
      // v2.4.53 Faz 13: kopru ajaninin canli durumu. Hem sorguya
      // yanit hem de merkez ayari degistiginde duyuru olarak gelir.
      if (typeof window.merkezKopruDurum === "function")
        window.merkezKopruDurum(m);
    } else if (m.tip === "yonetici_kur_sonuc"){
      // v2.4.68: sihirbaz adim 5 — YEREL yonetici hesabi olusturma.
      // GIRIS ONCESI gelir (yerel `kullanicilar` tablosu bos oldugu
      // icin kimlik dogrulanamaz); yonlendirme KOSULSUZ olmalidir.
      if (typeof window.pgYoneticiKurSonuc === "function")
        window.pgYoneticiKurSonuc(m);
    } else if (m.tip === "dji_belirtec_sonuc"){
      // BULGU_07: DJI kopru belirteci (durum / uret / sil). GDP
      // protokolu artik `merhaba` mesajinda belirtec ister; kullanici
      // belirteci Program Ayarlari -> DJI Kopru Belirteci bolumunden
      // uretir. `uret` yanitindaki `belirtec` YALNIZ BIR KEZ gelir.
      if (typeof window.djiBelirtecSonuc === "function")
        window.djiBelirtecSonuc(m);
    } else if (m.tip === "kopru_kimlik_sonuc"){
      // v2.4.67: YEREL kurulumun kopru kurulum kimlikleri (liste /
      // uret / sil). Kapali devre kullanimda saha makineleri buluta
      // degil bu kuruluma baglanir; kimlikler Program Ayarlari ->
      // Kopru Kimlikleri bolumunden uretilir. Uretim yanitindaki
      // `gizli` YALNIZ BIR KEZ gelir.
      if (typeof window.kopruKimlikSonuc === "function")
        window.kopruKimlikSonuc(m);
    } else if (m.tip === "kopruler"){
      // v2.4.232: Destek > Kopruler paneli (liste / olustur / sil /
      // kod yenile yanitlari; kip bagimsiz).
      if (typeof window.koprulerPanelIsle === "function")
        window.koprulerPanelIsle(m);
    } else if (m.tip === "makrolar"){
      // v2.4.243: Python makrolari listesi
      if (typeof window.makroListesiIsle === "function") window.makroListesiIsle(m);
    } else if (m.tip === "makro_kod"){
      if (typeof window.makroKodIsle === "function") window.makroKodIsle(m);
    } else if (m.tip === "makro_kod_yazildi"){
      if (typeof window.makroKodYazildiIsle === "function") window.makroKodYazildiIsle(m);
    } else if (m.tip === "makro_cikti"){
      if (typeof window.makroCiktiIsle === "function") window.makroCiktiIsle(m);
    } else if (m.tip === "makro_durum"){
      if (typeof window.makroDurumIsle === "function") window.makroDurumIsle(m);
    } else if (m.tip === "diyagram_bilgi"){
      // v2.4.239: baglanti diyagrami paneli.
      if (typeof window.diyagramIsle === "function") window.diyagramIsle(m);
    } else if (m.tip === "kopru_liste"){
      // v2.4.53 Faz 7: merkezde calisan ornekte firmaya ait KOPRU
      // (saha makinesi) listesi. Baglanti Yoneticisi gruplarini ve
      // Radar / Yer Kontrol Istasyonu Dual menulerinin gorunurlugunu
      // besler. Yerel kurulumda liste bostur ve hicbir sey degismez.
      if (typeof window.bagKopruListesiGuncelle === "function")
        window.bagKopruListesiGuncelle(m);
    } else if (m.tip === "ayarlar"){
      ayarlariUygula(m.ayarlar || {});
    } else if (m.tip === "sirket_sonuc"){
      // v2.4.41: sirket bilgileri kayit sonucu
      if (typeof window.sirketSonucIsle === "function")
        window.sirketSonucIsle(m);
    } else if (m.tip === "ucus_rapor_sonuc"){
      // v2.4.41: antetli PDF ucus raporu hazir/hata
      if (typeof window.ucusRaporSonucIsle === "function")
        window.ucusRaporSonucIsle(m);
    } else if (m.tip === "angajman"){
      angajmanDurumGuncelle(m.durum);
    } else if (m.tip === "goruntu_angajman_adayi"){
      _guvenli("goruntu_angajman_adayi", () => {
        if (typeof window.goruntuAngajmanAdayiIsle === "function")
          window.goruntuAngajmanAdayiIsle(m);
      });
    } else if (m.tip === "telemetri"){
      telemetriIsle(m);
    } else if (m.tip === "goruntu_son_kareler"){
      _guvenli("goruntu_son_kareler", () => {
        if (!m.basarili) return;
        const dronlar = Array.isArray(m.dronlar) ? m.dronlar : [];
        const kareler = Array.isArray(m.kareler) ? m.kareler : [];
        if (typeof window.dronGoruntuEslemeGuncelle === "function")
          window.dronGoruntuEslemeGuncelle(dronlar);
        if (typeof window.dronGoruntuKareIsle === "function"){
          for (const kare of kareler)
            if (kare && typeof kare === "object")
              window.dronGoruntuKareIsle(kare);
        }
      });
    } else if (m.tur === "dron_goruntu_kare" ||
               m.tip === "dron_goruntu_kare"){
      _guvenli("dron_goruntu_kare", () => {
        // Canlı sözleşme `m.kare` zarfıdır. Aynı sürüm ailesindeki köprüler
        // kareyi kökte gönderirse de yalnız nesne biçimi kabul edilir.
        const kare = (m.kare && typeof m.kare === "object") ? m.kare : m;
        if (typeof window.dronGoruntuKareIsle === "function" &&
            kare && typeof kare === "object")
          window.dronGoruntuKareIsle(kare);
      });
    } else if (m.tip === "suru_durum"){
      if (typeof window.suruDurumIsle === "function")
        window.suruDurumIsle(m);
    } else if (m.tip === "dron_takip"){
      if (typeof window.dronTakipDurumIsle === "function")
        window.dronTakipDurumIsle(m.takipler || []);
    } else if (m.tip === "dron_gecmis_liste"){
      if (typeof window.dronGecmisListeIsle === "function")
        window.dronGecmisListeIsle(m.dronlar || []);
      if (typeof window.pilotUcusListeIsle === "function")
        window.pilotUcusListeIsle(m.dronlar || []);
      // v2.4.42: Kayitli Dronlar paneli ayni cevabin UCUNCU tuketicisi.
      // Yeni WS komutu EKLENMEDI: sunucu bu listeyi zaten oturumun
      // rolune gore filtreliyor ve panelin ihtiyaci olan tum alanlar
      // (uid, renk, arac_sinifi, ucuslar[].pilotlar_ad) icinde geliyor.
      if (typeof window.kayitliDronlarVeri === "function")
        window.kayitliDronlarVeri(m.dronlar || []);
    } else if (m.tip === "ucus_veri"){
      // Pilot Hakkında onizlemesi acik ise oncelik onda
      let phAldi = false;
      if (typeof window.pilotUcusVeriIsle === "function")
        phAldi = window.pilotUcusVeriIsle(m.ucus || null);
      if (!phAldi && typeof window.ucusVeriIsle === "function")
        window.ucusVeriIsle(m.ucus || null, m.tespitler || [],
                            m.kalkis_kontrolleri || []);
      // IS99: Yetkili uçuş yanıtındaki süreli imzalı küçük kamera
      // karelerini Geçmiş Yöneticisi zaman çizelgesine bağla.
      if (!phAldi && typeof window.dronGoruntuGecmisIsle === "function")
        window.dronGoruntuGecmisIsle(m.goruntu_kareleri || [], m.ucus || null);
    } else if (m.tip === "manuel_durum"){
      if (typeof window.manuelDurumIsle === "function")
        window.manuelDurumIsle(m);
    // v2.4.44: Yer Istasyonu 2 (ESP32-S3 kontrol paneli). Durum paketi
    // 20 Hz'e kadar gelebilir; islev yoksa sessizce gecilir (modul
    // paketlemede eksik kalirsa arayuz calismaya devam etmeli).
    } else if (m.tip === "istasyon2_durum"){
      if (typeof window.istasyon2DurumIsle === "function")
        window.istasyon2DurumIsle(m);
    } else if (m.tip === "istasyon2_eylem"){
      if (typeof window.istasyon2EylemIsle === "function")
        window.istasyon2EylemIsle(m);
    } else if (m.tip === "istasyon2_eylem_sonuc"){
      if (typeof window.istasyon2EylemSonucIsle === "function")
        window.istasyon2EylemSonucIsle(m);
    } else if (m.tip === "istasyon2_portlar"){
      if (typeof window.istasyon2PortlarIsle === "function")
        window.istasyon2PortlarIsle(m);
    } else if (m.tip === "istasyon2_sonuc"){
      if (typeof window.istasyon2SonucIsle === "function")
        window.istasyon2SonucIsle(m);
    } else if (m.tip === "giris_sonuc"){
      // Çerez hazırlanması tamamlanmadan kamera paneli çizilmez; aksi halde
      // ilk <img> isteği 401 alır ve gereksiz yeniden deneme başlatır.
      const devam = function(){
        girisSonucIsle(m);
        // IS108: Firma oturumu doğrulandıktan sonra kayıtlı dron UID/ID→SYSID
        // özeti ve yalnız son onaylı küçük kareler istenir. Girişten önce
        // istemek firma bağlamı olmadığı için güvenli biçimde reddedilirdi.
        if (m.basarili && ws && ws.readyState === WebSocket.OPEN){
          ws.send(JSON.stringify({tip:"goruntu_son_kareler"}));
        }
      };
      if (m.basarili && m.jeton){
        // v2.4.229: merkez kipinde (/app/ vekili) kamera oturum ucu bilerek
        // kapalidir (sunucu 404 doner); bosuna istek ve konsol hatasi uretme.
        if (window.appKok === "/app") devam(); else kameraOturumuAc(m.jeton).then(devam, devam);
      } else {
        devam();
      }
    } else if (m.tip === "kullanici_liste"){
      kullaniciListeCiz(m.kullanicilar || []);
      if (typeof window.pilotHakkindaKullaniciTazele === "function")
        window.pilotHakkindaKullaniciTazele(m.kullanicilar || []);
    } else if (m.tip === "kullanici_islem"){
      if (m.basarili) kullaniciListeCiz(m.kullanicilar || []);
      if (typeof window.pilotHakkindaIslemSonuc === "function")
        window.pilotHakkindaIslemSonuc(m);
      if (typeof window.yeniKullaniciSonuc === "function")
        window.yeniKullaniciSonuc(m);
    } else if (m.tip === "uyari_yeni"){
      if (typeof window.uyariYeniIsle === "function") window.uyariYeniIsle(m);
    } else if (m.tip === "uyari_listesi"){
      if (typeof window.uyariListesiIsle === "function")
        window.uyariListesiIsle(m);
    } else if (m.tip === "uyari_sayi"){
      if (typeof window.uyariMerkeziOturum === "function" && oturum)
        window.uyariMerkeziOturum(m.okunmamis || 0);
    } else if (m.tip === "mesaj_okunmamis" || m.tip === "mesaj_okunmamis_sayi" ||
               m.tip === "mesaj_gecmis" || m.tip === "mesaj_yeni" ||
               m.tip === "mesaj_sonuc" || m.tip === "pilot_liste" ||
               m.tip === "pilot_durum"){
      // v2.4.32: mesajlasma ve pilot durum olaylari tek kapidan gecer.
      // mesajlasma.js kendi icinde pilot listesi widget'ina yonlendirir;
      // burada ikinci bir dagitim yapilmaz (cift cizim olurdu).
      if (typeof window.mesajOlayIsle === "function") window.mesajOlayIsle(m);
    } else if (m.tip === "rol_listesi"){
      if (typeof window.rolListesiIsle === "function")
        window.rolListesiIsle(m);
    } else if (m.tip === "rol_islem"){
      if (typeof window.rolIslemIsle === "function")
        window.rolIslemIsle(m);
    } else if (m.tip === "pilot_log_listesi"){
      if (typeof window.pilotLogListeIsle === "function")
        window.pilotLogListeIsle(m);
    } else if (m.tip === "lokasyon_liste"){
      if (typeof window.lokasyonListeCiz === "function")
        window.lokasyonListeCiz(m.lokasyonlar || []);
    } else if (m.tip === "rota_listesi"){
      if (typeof window.rotaListesiIsle === "function")
        window.rotaListesiIsle(m);
    } else if (m.tip === "kamera_listesi"){
      if (typeof window.kameraListesiIsle === "function")
        window.kameraListesiIsle(m);
    } else if (m.tip === "goruntu_kamera_kaynaklari"){
      if (typeof window.dkGoruntuKameraKaynaklariIsle === "function")
        window.dkGoruntuKameraKaynaklariIsle(m);
    } else if (m.tip === "goruntu_kamera_bag_sonuc"){
      if (typeof window.dkGoruntuKameraBagSonucIsle === "function")
        window.dkGoruntuKameraBagSonucIsle(m);
    } else if (m.tip === "dji_cihazlar"){
      if (typeof window.djiCihazlarIsle === "function")
        window.djiCihazlarIsle(m);
    } else if (m.tip === "kamera_cihazlari"){
      // v2.4.7: sunucu makinesindeki yerel kamera cihazlari
      if (typeof window.kameraCihazlarIsle === "function")
        window.kameraCihazlarIsle(m);
    } else if (m.tip === "dron_isim_guncellendi"){
      // Sunucu isim kaydetti; canli veriyi guncelle
      const sid = m.sysid;
      if (sonVeri[sid]) sonVeri[sid].kullanici_isim = m.isim;
    } else if (m.tip === "rota_ucus_param"){
      // v2.4.21: sabit kanat donus dairesi parametreleri
      if (typeof window.rotaUcusParamIsle === "function")
        window.rotaUcusParamIsle(m);
    } else if (m.tip === "param_gecmis"){
      // v2.4.21: parametre degisiklik gecmisi
      if (typeof window.dkParamGecmisGeldi === "function")
        window.dkParamGecmisGeldi(m);
    } else if (m.tip === "param_listesi"){
      if (typeof dkParamListesiGeldi === "function")
        dkParamListesiGeldi(m.sysid, m.parametreler || {}, m.hata || null,
                            m.kaynak || "", m.okuma_ts || 0);
      if (typeof window.dkFailsafeParamGeldi === "function")
        window.dkFailsafeParamGeldi(m.sysid, m.parametreler || {});
      if (typeof window.dronAyarParamGeldi === "function")
        window.dronAyarParamGeldi(m.sysid, m.parametreler || {});
    } else if (m.tip === "param_ilerleme"){
      // v2.4.15: tum parametre okuma ilerlemesi
      if (typeof dkParamIlerleme === "function")
        dkParamIlerleme(m.sysid, m.alinan || 0, m.toplam || 0);
    } else if (m.tip === "param_yazildi"){
      if (typeof dkParamYazildi === "function")
        dkParamYazildi(m.sysid, m.ad, m.deger, m.basari);
      if (typeof window.dkFailsafeParamYazildi === "function")
        window.dkFailsafeParamYazildi(m.sysid, m.ad, m.deger, m.basari);
    } else if (m.tip === "arm_check_rapor"){
      // v2.4.19: ARM CHECK hazirlik raporu
      if (typeof window.dkArmCheckRaporGeldi === "function")
        window.dkArmCheckRaporGeldi(m);
    } else if (m.tip === "kalkis_kontrol_sonuc"){
      // v2.4.41: kalkis kontrol listesi kayit sonucu
      if (typeof window.kalkisKontrolSonucIsle === "function")
        window.kalkisKontrolSonucIsle(m);
    } else if (m.tip === "set_home_sonuc"){
      // v2.4.42: HOME ayarlama sonucu. Sessiz basarisizlik OLMAMALI:
      // HOME ucus guvenligini etkiler (RTL/failsafe donus noktasi), bu
      // yuzden hem basari hem hata sag kose bildirimi olarak gosterilir.
      // Harita ikonu ayrica telemetriden gelen HOME ile kendiliginden
      // tazelenir; bu bildirim komutun ULASTIGINI teyit eder.
      if (typeof window.uyariToastGoster === "function"){
        const _t = (typeof D === "function") ? D() : {};
        const _d = "D" + (m.sysid || "?");
        window.uyariToastGoster({
          seviye: m.basari ? "basari" : "hata",
          kategori: "komut",
          mesaj: m.basari
            ? (_d + " " + (m.mevcut_konum
                ? (_t.homeSonucMevcut ||
                   "HOME arac\u0131n mevcut konumuna ayarland\u0131")
                : (_t.homeSonucKonum ||
                   "HOME se\u00e7ilen konuma ayarland\u0131")))
            : (_d + " " + (_t.homeSonucHata || "HOME ayarlanamad\u0131") +
               (m.sebep ? ": " + m.sebep : ""))
        });
      }
    } else if (m.tip === "hata_bildirim"){
      // v2.4.56: sunucudan gelen tekil hata (kamera/AI kopru dogrulama
      // gibi). Sessiz donmek kullanicinin "kaydet bir sey yapmiyor"
      // demesine yol acar; bu yuzden sag kose bildirimi gosterilir.
      if (typeof window.uyariToastGoster === "function"){
        window.uyariToastGoster({
          seviye: "hata",
          kategori: String(m.kaynak || "sistem").toLowerCase(),
          mesaj: String(m.hata || "")
        });
      }
    } else if (m.tip === "dron_mesaj_listesi"){
      // v2.4.19: dronun STATUSTEXT hata/uyari mesajlari
      if (typeof window.dkDronMesajlariGeldi === "function")
        window.dkDronMesajlariGeldi(m.sysid, m.mesajlar || []);
    } else if (m.tip === "dron_konsol_satir"){
      // v2.4.45: dron panelinin altindaki haberlesme konsoluna tek satir
      if (typeof window.dronKonsolSatir === "function")
        window.dronKonsolSatir(m);
    } else if (m.tip === "dron_konsol_gecmis"){
      // v2.4.45: konsol ilk acildiginda (ya da temizlendiginde) gecmis
      if (typeof window.dronKonsolGecmis === "function")
        window.dronKonsolGecmis(m);
    } else if (m.tip === "kamera_konsol_satir"){
      // v2.4.189: kamera satirinin altindaki konsola tek satir
      if (typeof window.kameraKonsolSatir === "function")
        window.kameraKonsolSatir(m);
    } else if (m.tip === "kamera_konsol_gecmis"){
      if (typeof window.kameraKonsolGecmis === "function")
        window.kameraKonsolGecmis(m);
    } else if (m.tip === "log_listesi"){
      if (typeof window.dkLogListesiGeldi === "function")
        window.dkLogListesiGeldi(m.sysid, m.loglar || [], m.hata);
    } else if (m.tip === "log_ilerleme"){
      if (typeof window.dkLogIlerleme === "function")
        window.dkLogIlerleme(m.sysid, m.log_id, m.alinan, m.toplam);
    } else if (m.tip === "log_indirildi"){
      if (typeof window.dkLogIndirildi === "function")
        window.dkLogIndirildi(m.sysid, m.log_id, m.dosya, m.basari,
                              m.hata, m.iptal);
    } else if (m.tip === "tile_cache_bilgi"){
      if (typeof window.hrtCacheBilgiGeldi === "function")
        window.hrtCacheBilgiGeldi(m);
      // v2.4.33: Harita Ayarlari penceresi kapali olsa bile durum
      // cubugu gostergesi guncellenmeli. `hrtCacheBilgiGeldi` ilk
      // satirinda pencere ogesi yoksa donduugu icin buraya ayri
      // cagri gerekir.
      if (typeof window.hrtCacheDurumYaz === "function")
        window.hrtCacheDurumYaz(m);
    } else if (m.tip === "tile_cache_ozet"){
      // v2.4.33: durum cubugu icin hafif ozet (disk taramasi yok).
      // Sunucu yeni karo indikce kendiliginden gonderir.
      if (typeof window.hrtCacheDurumYaz === "function")
        window.hrtCacheDurumYaz(m);
    } else if (m.tip === "tile_cache_on_olcum"){
      // FAZ18-IS31: indirme oncesi tahmin yaniti
      if (typeof window.hrtCacheOnOlcum === "function")
        window.hrtCacheOnOlcum(m);
    } else if (m.tip === "tile_cache_ilerleme"){
      if (typeof window.hrtCacheIlerleme === "function")
        window.hrtCacheIlerleme(m);
    } else if (m.tip === "kayit_listesi"){
      if (typeof kayitListeCiz === "function") kayitListeCiz(m.kayitlar || []);
    } else if (m.tip === "replay_bitti"){
      if (typeof replayDurumGuncelle === "function") replayDurumGuncelle({aktif: false});
    } else if (m.tip === "siniflandirma_durum"){
      if (typeof siniflandirmaDurumUygula === "function")
        siniflandirmaDurumUygula(m.ayar);
    } else if (m.tip === "etiket_listesi"){
      if (typeof replayDosya !== "undefined" && m.dosya === replayDosya){
        etiketler = m.etiketler || {};
        if (typeof etiketRozetleriTazele === "function") etiketRozetleriTazele();
      }
    } else if (m.tip === "ai_sunucu_listesi"){
      if (typeof window.aiSunucuListesiIsle === "function")
        window.aiSunucuListesiIsle(m);
    } else if (m.tip === "ai_izleme_listesi"){
      if (typeof window.aiIzlemeListesiIsle === "function")
        window.aiIzlemeListesiIsle(m);
    // v2.4.49: systemd servis yonetimi + makine guc (kapat/yeniden)
    } else if (m.tip === "servis_durum"){
      if (typeof window.svDurumGeldi === "function")
        window.svDurumGeldi(m);
    } else if (m.tip === "servis_sonuc"){
      if (typeof window.svSonucGeldi === "function")
        window.svSonucGeldi(m);
    } else if (m.tip === "servis_gunluk"){
      if (typeof window.svGunlukGeldi === "function")
        window.svGunlukGeldi(m);
    } else if (m.tip === "makine_sonuc"){
      if (typeof window.svMakineSonucGeldi === "function")
        window.svMakineSonucGeldi(m);
    // v2.4.51: PostgreSQL ilk kurulum / goc sihirbazi.
    // Bu uc mesaj GIRIS ONCESI de gelebilir (veritabani yoksa
    // kullanici dogrulanamaz), bu yuzden yonlendirme kosulsuzdur.
    } else if (m.tip === "pg_durum"){
      if (typeof window.pgDurumGeldi === "function")
        window.pgDurumGeldi(m);
    } else if (m.tip === "pg_sonuc"){
      if (typeof window.pgSonucGeldi === "function")
        window.pgSonucGeldi(m);
    } else if (m.tip === "pg_ilerleme"){
      if (typeof window.pgIlerlemeGeldi === "function")
        window.pgIlerlemeGeldi(m);
    // v2.4.66: merkez kullanici esitlemesi (sihirbaz adim 4).
    // GIRIS ONCESI gelir: yerel kullanici tablosu bos oldugu icin
    // kimlik dogrulanamaz; yonlendirme KOSULSUZ olmalidir.
    } else if (m.tip === "lisans_yenile_sonuc"){
      if (typeof window.lisansYenileSonuc === "function") window.lisansYenileSonuc(m);
    } else if (m.tip === "pg_merkez_kod_sonuc"){
      // 2.4.233: kurulum sihirbazi merkez sunucu + API kodu yaniti.
      if (typeof window.pgSonucGeldi === "function")
        window.pgSonucGeldi(m);
    } else if (m.tip === "merkez_esitle_sonuc"){
      if (typeof window.pgSonucGeldi === "function")
        window.pgSonucGeldi(m);
    // v2.4.50: pilot bazli joystick tercihi (ters cevirme, olu bolge,
    // merkez kalibrasyonu). Ayar KISISELDIR; rol sarti yoktur.
    } else if (m.tip === "joystick_tercih"){
      if (typeof window.jaTercihGeldi === "function")
        window.jaTercihGeldi(m);
    } else if (m.tip === "joystick_tercih_sonuc"){
      if (typeof window.jaTercihSonuc === "function")
        window.jaTercihSonuc(m);
    } else if (m.tip === "joystick_kalibre_sonuc"){
      if (typeof window.jaKalibreSonuc === "function")
        window.jaKalibreSonuc(m);
    } else if (m.tip === "joystick_ham"){
      if (typeof window.jaHamGeldi === "function")
        window.jaHamGeldi(m);
    // v2.4.45: AI bilgisayarlarina SSH ile uzaktan baslatma
    } else if (m.tip === "ai_ssh_durum"){
      if (typeof window.aiSshDurumIsle === "function")
        window.aiSshDurumIsle(m);
    } else if (m.tip === "ai_ssh_satir"){
      if (typeof window.aiSshSatirIsle === "function")
        window.aiSshSatirIsle(m);
    } else if (m.tip === "ai_ssh_gecmis"){
      if (typeof window.aiSshGecmisIsle === "function")
        window.aiSshGecmisIsle(m);
    } else if (m.tip === "kisi_listesi"){
      if (typeof window.aiKisiListesiIsle === "function")
        window.aiKisiListesiIsle(m);
    } else if (m.tip === "kisi_yuz_sonuc"){
      if (typeof window.aiKisiYuzSonucIsle === "function")
        window.aiKisiYuzSonucIsle(m);
    } else if (m.tip === "arac_listesi"){
      if (typeof window.aiAracListesiIsle === "function")
        window.aiAracListesiIsle(m);
    } else if (m.tip === "ai_tespit"){
      // v2.4.0: canli AI tespiti (alt panel akisi + kayitsiz listesi)
      if (typeof window.aiCanliTespitIsle === "function")
        window.aiCanliTespitIsle(m);
      // v2.4.2: drona bagli kameranin tespit seridi
      if (typeof window.dronTespitIsle === "function")
        window.dronTespitIsle(m);
    } else if (m.tip === "ai_tespit_gecmisi"){
      if (typeof window.aiTespitGecmisiIsle === "function")
        window.aiTespitGecmisiIsle(m);
    } else if (m.tip === "ai_tespit_islem_sonuc"){
      if (typeof window.aiIslemSonucIsle === "function")
        window.aiIslemSonucIsle(m);
    } else if (m.tip === "video_kayit_durum"){
      // v2.4.210: M50 penceresi video kaydi durumu
      if (typeof window.videoKayitDurumIsle === "function")
        window.videoKayitDurumIsle(m);
    } else if (m.tip === "ai_kutular"){
      // v2.4.164: canli AI kutulari (videoda cift tikla takip icin)
      if (typeof window.kameraAiKutularIsle === "function")
        window.kameraAiKutularIsle(m);
    } else if (m.tip === "ai_takip_sonuc" || m.tip === "ai_takip"){
      if (typeof window.kameraTakipIsle === "function")
        window.kameraTakipIsle(m);
      // v2.4.2: hedef takibi baslatma sonucu + canli takip durumu
      if (typeof window.dronTakipIsle === "function")
        window.dronTakipIsle(m);
    } else if (m.tip === "gorev_iptal_sonuc"){
      // v2.4.18: gorev iptal sonucu (izleme popup'ini tazeler)
      if (typeof window.gorevIptalSonucIsle === "function")
        window.gorevIptalSonucIsle(m);
    } else if (m.tip === "gorev_yukle_sonuc" ||
               m.tip === "gorev_baslat_sonuc" ||
               m.tip === "gorev_durdur_sonuc" ||
               m.tip === "gorev_devam_sonuc" ||
               m.tip === "gorev_surdur_sonuc"){
      // v2.4.35: durdur/devam/surdur da sonuc dondurur. Mod gecisi
      // telemetriden dogrulanmazsa basari=false gelir; arayuz yerel
      // asamayi geri alir (sessiz basarisizlik yerine gorunur hata).
      // v2.4.20: rota yukleme / baslatma sonucu
      if (typeof window.gorevKomutSonucIsle === "function")
        window.gorevKomutSonucIsle(m);
    } else if (m.tip === "kalib_mesaj_listesi"){
      // v2.5.0: Kalibrasyon penceresi kendi oturumunun STATUSTEXT
      // satirlarini ister. Genel konsola YAZILMAZ: kullanici istegi
      // uzerine iletisim ciktisi dronun kendi penceresinde durur.
      if (typeof window.kalibMesajListesiIsle === "function")
        window.kalibMesajListesiIsle(m);
    } else if (m.tip === "motor_test_sonuc"){
      // v2.5.0: Motor testi sonucu (arm denetimi reddi dahil).
      if (typeof window.motorTestSonucIsle === "function")
        window.motorTestSonucIsle(m);
    } else if (m.tip === "ivme_yon_onay_sonuc"){
      // v2.5.0: Alti yonlu ivme kalibrasyonunda yon onayi yaniti.
      if (typeof window.ivmeYonOnaySonucIsle === "function")
        window.ivmeYonOnaySonucIsle(m);
    } else if (m.tip === "ilk_ayar_ongorusu"){
      // v2.5.0: Ilk ayar (initial tune) ongoru tablosu.
      if (typeof window.ilkAyarOngorusuIsle === "function")
        window.ilkAyarOngorusuIsle(m);
    } else if (m.tip === "ilk_ayar_sonuc"){
      // v2.5.0: Ilk ayar parametre yazma sonucu.
      if (typeof window.ilkAyarSonucIsle === "function")
        window.ilkAyarSonucIsle(m);
    } else if (m.tip === "voltaj_kalibrasyon_sonuc"){
      // Gercek olculen batarya voltajindan BATT_VOLT_MULT hesaplama sonucu.
      if (typeof window.voltajKalibrasyonSonucIsle === "function")
        window.voltajKalibrasyonSonucIsle(m);
    } else if (m.tip === "kaynak_olcum"){
      // v2.4.34: Sistem Kaynaklari widget'i sunucu olcumu.
      // Widget kapaliyken istek gonderilmedigi icin bu dal da islemez.
      if (typeof window.kaynakOlcumGeldi === "function")
        window.kaynakOlcumGeldi(m);
    }
  };
}
// =================================================================
// FAZ18-IS1-SIHIRBAZ-DUZELT - CANLI WS COZUCUSU
// -----------------------------------------------------------------
// `ws` degiskeni bu betiklerin ORTAK global kapsaminda yasar
// (`seri.js` icinde `let ws = null` ile bildirilir; `wsBaglan()`
// buraya atar). Baska modullerin dogru nesneyi gormesi icin
// `window.ws` yansitmasi kullaniliyordu; iki kusuru vardi:
//   1) Yansitma `bagKaydet()` ISLEVININ ICINDE yapiliyordu, yani
//      kullanici KAYDET'e basmadan `window.ws` TANIMSIZ kaliyordu.
//      SITL sihirbazi Adim 2'de bunu okuyup "Sunucu baglantisi yok"
//      diyordu -- baglanti acikken.
//   2) Yansitma tek seferlik oldugu icin her yeniden baglanmada
//      (`ws.onclose` -> `wsBaglan()`) BAYATLIYORDU: yeni WebSocket
//      nesnesi atanir, `window.ws` kapanmis nesneyi gostermeye
//      devam ederdi.
// Cozum: deger yansitmak yerine COZUCU acmak. Her cagrida guncel
// nesne okunur; bayatlama imkansizdir.
// =================================================================
window.wsCanli = function () {
  try {
    return (typeof ws !== "undefined" && ws) ? ws : null;
  } catch (e) {
    return null;
  }
};
window.wsAcikMi = function () {
  var s = window.wsCanli();
  return !!(s && s.readyState === 1);
};

wsBaglan();

// Sayfa yuklendiginde dili uygula (tum degiskenler tanimlandiktan sonra)
applyLanguage(aktifDil, false);

