/* =================================================================
   GOKTUNGU v2.6.0 -- Tanitim sitesi TR/EN dil destegi
   -----------------------------------------------------------------
   Uluslararasi savunma satisinda Ingilizce zorunludur.  Site metinleri
   HTML'e gomulu Turkce oldugu icin data-i18n oznitelikli sozluk
   yaklasimi kullanildi:

     <h2 data-i18n="mimari.baslik">Donanim sahada, komuta bulutta</h2>

   HTML'deki metin TR icin kaynak kabul edilir; EN'e gecildiginde
   sozlukten yazilir, TR'ye donuldugunde ilk yuklemede saklanan ozgun
   metin geri konur.  Boylece TR sozlugu iki kez yazilmaz ve HTML
   JavaScript kapali tarayicida da tam Turkce okunur (SEO + erisim).

   Ozel durumlar:
     data-i18n-html   -> innerHTML olarak yazilir (ic etiket korunur)
     data-i18n-attr   -> "attr:anahtar" ciftleri (placeholder, alt, ...)

   (c) VEILOX Savunma Anonim Sirketi
   =================================================================    FAZ18-IS15-MARKA-TEMIZLIK: EN sozlukteki
   eski marka adlari resmi kunye ile degistirildi.
*/
(function () {
  "use strict";

  var ANAHTAR = "goktungu_landing_dil";

  /* ---------------------------------------------------------------
     INGILIZCE SOZLUK
     ---------------------------------------------------------------
     Savunma sanayii terminolojisi:
       harekat resmi        -> operational picture
       alcak irtifa         -> low-altitude
       hava sahasi          -> airspace
       komuta kontrol       -> command and control (C2)
       kopru yazilimi       -> bridge software
       saha bilgisayari     -> field computer
       cok kiracili         -> multi-tenant
       kiraci yalitimi      -> tenant isolation
       gorev yurutucu       -> task executor
       iz takibi            -> track management
     --------------------------------------------------------------- */
  var EN = {
    /* --- Sayfa ust verisi --- */
    "meta.baslik": "GÖKTUNGU — Low-Altitude Airspace Command and Control System | Gökkubbe Teknoloji",
    "meta.aciklama": "GÖKTUNGU is a low-altitude airspace command and control system that fuses radar, unmanned aircraft and AI vision sources into a single operational picture. The command and control interface runs centrally; only a lightweight bridge is installed in the field. A product of Gökkubbe Teknoloji Anonim Şirketi.",

    /* --- Ust cubuk --- */
    "menu.mimari": "Architecture",
    "menu.yetenekler": "Capabilities",
    "menu.platformlar": "Platforms",
    "menu.arayuz": "Interface",
    "menu.istemciler": "Download",
    "menu.guvenlik": "Security",
    "menu.kurumsal": "Corporate Panel",
    "menu.giris": "Sign In &rarr;",

    /* --- Hero --- */
    "hero.rozetOn": "Version",
    "hero.rozetSon": "Central Operations · Field Bridge",
    "hero.rozetCanli": "system online",
    "hero.baslik": "A single operational picture<br><em>of low-altitude airspace</em>",
    "hero.alt": "GÖKTUNGU fuses radar systems, unmanned aircraft, fixed cameras and AI vision servers into one geospatial operational picture. The command and control interface runs centrally and opens in a browser; the field computer only runs the bridge software that carries drone, camera and radar links.",
    "hero.dg1": "Sign In",
    "hero.dg2": "Download Software",
    "hero.ist1": "Widgets and Panels",
    "hero.ist2": "Radar Protocols",
    "hero.ist3": "MAVLink Messages",
    "hero.ist4birim": " platforms",
    "hero.ist4": "Windows · Ubuntu",

    /* --- Mimari --- */
    "mimari.etiket": "System Architecture",
    "mimari.baslik": "Operations in the field, management at the centre",
    "mimari.aciklama": "The command and control interface runs on the central server; the pilot uses the map, the drone panel and mission management from a browser. The field computer runs only the bridge software: it establishes drone, camera and radar links locally and carries them over a single encrypted outbound channel to the centre. This approach requires no inbound port on the corporate firewall, and no static IP address or domain name allocation.",
    "mimari.saha": "Bridge Software",
    "mimari.sahanot": "Field computer &middot; Python 3.11 &middot; local web panel",
    "mimari.dron": "Drone Service",
    "mimari.dronalt": "MAVLink v1/v2 &middot; serial, TCP, UDP, SITL",
    "mimari.radar": "Radar Service",
    "mimari.radaralt": "AERIS-compatible JSON, binary frame",
    "mimari.ai": "AI Service",
    "mimari.aialt": "Vision inference server management",
    "mimari.video": "Video Service",
    "mimari.videoalt": "RTSP and MJPEG stream bridging",
    "mimari.gcsdual": "GroundGCC Service",
    "mimari.gcsdualalt": "Dual-screen ground control case",
    "mimari.ok": "reverse WebSocket<br>443 &middot; outbound only",
    "mimari.bulut": "Central Server",
    "mimari.bulutnot": "goktungu.com &middot; multi-tenant",
    "mimari.komuta": "Command and Control Interface",
    "mimari.komutaalt": "CesiumJS globe, route planning, flight reporting",
    "mimari.yonetim": "Corporate Management Panel",
    "mimari.yonetimalt": "Pilot roster, flight and video records",
    "mimari.veri": "Version Repository and Archive",
    "mimari.verialt": "Ed25519 signed updates, per-tenant isolation",

    /* --- Ters WebSocket kopru vurgusu --- */
    "proto.etiket": "Reverse Connection Architecture",
    "proto.baslik": "No static IP, no open ports",
    "proto.aciklama": "Field computers running the bridge software operate on home and office internet connections, usually with a dynamic IP address and behind NAT, so the centre cannot reach them. For this reason the bridge always initiates the connection: it opens an encrypted WebSocket towards the centre and keeps it open. The centre sends its queries back through this ready channel.",
    "proto.k1": "Installation Identity",
    "proto.k1alt": "On first launch the bridge software registers with the centre and receives its own installation identifier together with a secret key. The secret is shown only once, is stored on the field computer and is used to authenticate every subsequent connection.",
    "proto.k2": "Bridge Groups",
    "proto.k2alt": "In the connection manager the organisation's online bridges are grouped by name and address; each bridge's drone, camera and radar links are listed under its own group. The operator selects from the list without entering any address or port.",
    "proto.k3": "Local Recording on Loss",
    "proto.k3alt": "If the connection to the centre drops, the bridge records flight data to local disk; when the link returns the live stream continues without interruption and the recording kept during the outage is preserved. The bridge reconnects on its own with increasing back-off delays.",
    "proto.eskibas": "Classic remote access",
    "proto.eski1": "Static IP address or domain name allocation",
    "proto.eski2": "An inbound port is opened on the firewall",
    "proto.eski3": "Port forwarding rule on the router",
    "proto.eski4": "The field computer becomes reachable from the internet",
    /* {s} = surumler.json'dan gelen surum. Sabit numara yazilmaz:
       sozluk ile paketler ayri surum gosterirse musteri sitede
       gordugu surumu indiremez. */
    "proto.yenibas": "Version {s} · reverse WebSocket bridge",
    "proto.yeni1": "A dynamic IP address causes no problem",
    "proto.yeni2": "No inbound port is opened",
    "proto.yeni3": "No router configuration is required",
    "proto.yeni4": "The field computer stays unreachable from the internet",
    "proto.k4": "Remote Status Query",
    "proto.k4alt": "Through the open bridge the centre queries the bridge's drone count, service states and version, so status becomes visible without any inbound connection to the field computer.",

    /* --- Yetenekler --- */
    "yet.etiket": "Capabilities",
    "yet.baslik": "Every layer an operation requires",
    "yet.aciklama": "The full detection, classification, tracking and response chain is gathered in a single interface. Only defined and active sources appear in the interface; inactive sources do not clutter the display.",
    "yet.k1": "Radar Detection and Track Management",
    "yet.k1alt": "Polar radar measurements are converted to geodetic coordinates; stable tracks are produced with confirmation thresholds, timeouts and alpha-filtered velocity estimation. A lost target that reappears within the range window is reattached to its previous track.",
    "yet.k2": "Unmanned Aircraft Command",
    "yet.k2alt": "ArduCopter, ArduPlane and ArduRover flight modes are decoded. Take-off, landing, return-to-launch and guided movement commands are issued from the interface; each aircraft receives its own colour and map trail.",
    "yet.k3": "AI Vision Processing",
    "yet.k3alt": "Camera streams are routed to the inference server; rotated bounding boxes are drawn as target frames. Class-aware overlap suppression keeps targets of different types separate.",
    "yet.k4": "Multi-Tenant Corporate Structure",
    "yet.k4alt": "Each organisation is registered with its own tax identity, legal title and logo. The signed-in organisation's identity appears throughout the interface and in reports; data is isolated at tenant level.",
    "yet.k5": "Pilot and Flight Log Management",
    "yet.k5alt": "Pilot rosters, licence details and flight records are managed from the corporate panel. Flight duration, mission type and aircraft assignment are recorded.",
    "yet.k6": "History Recording and Replay",
    "yet.k6alt": "Detection and flight data are archived; a past mission can be replayed on the map. Tracks are restored from the system when the display is refreshed.",

    /* --- Platformlar --- */
    "plat.etiket": "Supported Platforms",
    "plat.baslik": "Four airframe classes, one interface",
    "plat.aciklama": "GÖKTUNGU resolves the MAVLink aircraft type reported by each vehicle into four airframe classes and renders a class-specific map symbol. The symbol rotates with the reported heading, its colour carries the connection state, and a pitch indicator reflects the attitude.",
    "plat.p1": "Multirotor",
    "plat.p1alt": "Quadrotor, hexarotor and octorotor airframes. Position-hold and guided flight modes with gimbal-mounted electro-optical payloads.",
    "plat.p1tip": "MAV_TYPE 2, 13, 14",
    "plat.p2": "Fixed Wing",
    "plat.p2alt": "High-endurance surveillance airframes. Long-range patrol tasks with loiter and waypoint navigation over extended areas.",
    "plat.p2tip": "MAV_TYPE 1",
    "plat.p3": "Unmanned Helicopter",
    "plat.p3alt": "Single main rotor rotorcraft. Heavy payload capacity with hover endurance for persistent overwatch tasks.",
    "plat.p3tip": "MAV_TYPE 4, 6",
    "plat.p4": "VTOL",
    "plat.p4alt": "Hybrid airframes combining vertical take-off with fixed-wing cruise. Transition state is tracked and displayed distinctly.",
    "plat.p4tip": "MAV_TYPE 19–25",
    "plat.not": "<strong>Map symbology.</strong> Airframe class is derived from the MAVLink heartbeat, so no manual selection is required. Unrecognised types fall back to the multirotor symbol; a flight controller running an older protocol never breaks the display.",

    /* --- Arayuz --- */
    "ary.etiket": "Command and Control Interface",
    "ary.baslik": "The operational picture on one screen",
    "ary.aciklama": "Resizable panels, movable windows that can be nested into tabs, and connection indicators in the bottom status bar let the operator monitor the entire system at a glance.",
    "ary.ss1": "Connection Manager",
    "ary.ss2": "Radar Settings and Calibration",
    "ary.ss3": "Target Classification",
    "ary.ss4": "Camera Management",
    "ary.ss5": "History Record Management",

    /* --- Istemciler --- */
    "ist.etiket": "Download Centre",
    "ist.baslik": "Bridge software",
    "ist.aciklama": "The bridge software runs on your field computer and opens a local web panel. You sign in to the panel with your corporate account and your organisation's logo appears there; from the panel you start and stop the five services (Drone, AI, Video, GroundGCC, Radar) and follow their console output. Separate installers are published for Windows and Ubuntu; both install the software as a service, start it automatically at boot and add Start menu and desktop shortcuts. The Windows installer ships Python embedded, so nothing else needs to be installed. The command and control interface is not downloaded separately, it opens in a browser.",
    "ist.not": "<strong>Installation and updates.</strong> On Windows, double-click <code>GOKTUNGU-Kopru-Setup.exe</code>; the setup wizard asks for administrator permission, installs the software under <code>C:\\Program Files\\Goktungu\\Kopru</code> and registers it as a <em>Windows service</em>. Python ships embedded, so you do not need to install it separately. On Ubuntu, the <code>.deb</code> package is installed with <code>apt</code>; the software goes under <code>/opt/goktungu/kopru</code> and runs as a systemd system service. On both platforms the service starts automatically at boot <strong>even before anyone signs in</strong>, and restarts itself if it stops unexpectedly. The installer adds Start menu and desktop shortcuts. To update, run the new installer: the service is stopped, files are replaced and the service is restarted; your settings, installation identity and outage recording are preserved. The SHA-256 digest of each package is published below and also appears when you hover over a download link.",
    "ist.sha": "Integrity Verification (SHA-256)",

    /* --- v2.6.0 yenilikleri --- */
    "yeni.rozet": "New",
    "yeni.baslik": "What version {s} brings",
    "yeni.y1": "Real installer and Windows service",
    "yeni.y1alt": "Windows now has a setup wizard you simply double-click: it requests administrator permission, ships Python embedded and registers the bridge in the Windows Service Control Manager, so it appears in services.msc, starts before anyone signs in and recovers itself after a crash. Ubuntu is published as a .deb package installed with apt, running as a systemd system service under its own service account. Reinstalling the newer file upgrades in place and preserves your settings and central identity.",
    "yeni.y2": "Bridge groups",
    "yeni.y2alt": "In the central connection manager the organisation's online bridges are grouped by name and address; drone, camera and radar links are listed under their own bridge. No address or port entry is required.",
    "yeni.y3": "Local recording on loss",
    "yeni.y3alt": "When the connection to the centre drops the bridge writes flight data to local disk. Once the link returns the live stream continues without interruption; the recording kept during the outage is preserved and its size is shown in the panel.",
    "yeni.y4": "Single instance guarantee",
    "yeni.y4alt": "A second bridge instance cannot start on the same computer. This prevents two instances sharing the same installation identity from tearing down each other's central session at the source.",

    /* --- Kurulum --- */
    "kur.etiket": "Deployment",
    "kur.baslik": "Commissioning in four steps",
    "kur.a1": "Organisation Registration",
    "kur.a1alt": "An organisation record is created from the corporate panel with tax identification number, legal title, address and logo; the administrator account is designated and pilots are defined under that account.",
    "kur.a2": "Install the Bridge",
    "kur.a2alt": "The installer for your operating system is downloaded and run. On Windows the setup wizard asks for administrator permission and registers the software as a service; Python ships embedded, so no separate installation is needed. On Ubuntu the package is installed with <code>apt</code> and comes up as a systemd service.",
    "kur.a3": "Register with the Centre",
    "kur.a3alt": "The bridge panel opens in the browser at <code>http://127.0.0.1:8790</code>. You sign in with your corporate account and register the bridge with a name of your choice. From then on the bridge starts automatically at launch.",
    "kur.a4": "Begin Operations",
    "kur.a4alt": "The command and control interface opens at <code>https://goktungu.com/app/</code>. Your bridge appears in the connection manager with its name and address; drone, radar and camera links are defined under that group.",

    /* --- Guvenlik --- */
    "guv.etiket": "Security",
    "guv.baslik": "Corporate security discipline",
    "guv.aciklama": "All communication between the bridge software and the centre is encrypted. Corporate data is isolated at the tenant level and every distributed package is signed.",
    "guv.g1": "Outbound Connection Only",
    "guv.g1alt": "The bridge opens a single outbound encrypted connection to the centre. No inbound port needs to be opened on the corporate firewall, and the field computer does not become reachable from the internet.",
    "guv.g2": "Passwords Are Never Sent to the Interface",
    "guv.g2alt": "The central account password is held on the server side only; it is never sent to the interface under any circumstances, and the screen shows only whether one is defined.",
    "guv.g3": "Single-Use Installation Secret",
    "guv.g3alt": "The secret key generated during registration is stored at the centre only as a digest and is never shown again; if it is lost it must be regenerated.",
    "guv.g4": "Signed Distribution",
    "guv.g4alt": "All distribution packages are signed with Ed25519. The software will not apply an installation unless the downloaded package signature is verified against the embedded public key; SHA-256 digests are published for every file.",
    "guv.g5": "Tenant Isolation",
    "guv.g5alt": "Users, aircraft, flight records, telemetry and the video archive are held in the central database under your organisation's tenant identity; cross-tenant access is blocked at the data layer.",
    "guv.g6": "No Data Loss on Outage",
    "guv.g6alt": "When the connection to the centre drops the bridge writes flight data to the disk of the field computer; the section recorded during the outage is preserved and its size is shown in the panel. If the disk limit is exceeded the oldest recording is preserved and the newest data is discarded: in fault investigation the critical section is at the start of the outage.",

    /* --- CTA --- */
    "cta.baslik": "Access the system",
    "cta.aciklama": "Register on behalf of your organisation, define your pilot roster and install the bridge software to build your operational picture.",
    "cta.dg1": "Create Organisation Record",
    "cta.dg2": "Command and Control Interface",

    /* --- Alt bilgi --- */
    "ft.tanim": "Gökkubbe Teknoloji Anonim Şirketi is a defence industry company operating in low-altitude airspace awareness, guidance and control systems, and unmanned aircraft technologies.",
    "ft.sistem": "System",
    "ft.erisim": "Access",
    "ft.iletisim": "Contact",
    "ft.yasal": "Legal",
    "ft.istemciindir": "Software Download",
    "ft.kurulum": "Deployment",
    "ft.gizlilik": "Privacy Policy",
    "ft.kullanim": "Terms of Use",
    "ft.cerez": "Cookie Policy",
    "ft.kvkk": "Data Protection Notice",
    "ft.ulke": "Türkiye",
    "ft.kunye": "Gökkubbe Teknoloji Anonim Şirketi. All rights reserved. GÖKTUNGU is a product of Gökkubbe Teknoloji Anonim Şirketi.",
    "ft.surum": "Version {s}",

    /* --- Indirme kartlari (js/indir.js tarafindan kullanilir) --- */
    "indir.gcs": "Command and Control Software",
    "indir.gcsalt": "The command and control software carrying mapping, telemetry, mission management, camera streams and flight reporting. It is normally served from the centre; this package is intended for organisations that operate their own server.",
    "indir.sunucu": "Central Server",
    "indir.sunucualt": "Multi-tenant central server software.",
    "indir.kopru": "GÖKTUNGU Bridge Software",
    "indir.koprualt": "The bridge software that runs on the field computer. It opens a local web panel; starts, stops and shows the consoles of five services (Drone, AI, Video, GroundGCC, Radar). It carries drone, camera and radar links over a single encrypted channel to the centre. Python 3.11 is required.",
    "indir.dron": "Drone Connection Manager",
    "indir.dronalt": "MAVLink v1/v2 · serial, TCP, UDP",
    "indir.radar": "Radar Connection Manager",
    "indir.radaralt": "AERIS-compatible JSON, binary frame, ASCII",
    "indir.ai": "AI Connection Manager",
    "indir.aialt": "HTTP, TCP and WebSocket inference backends",
    "indir.windows": "Windows x64",
    "indir.linux": "Ubuntu x64",
    "indir.boyut": "Size",

    /* --- Cerez bandi --- */
    "cerez.metin": "This site uses only strictly necessary cookies required for session management and language preference. No analytics or advertising cookies are used.",
    "cerez.tamam": "Understood",
    "cerez.detay": "Cookie Policy"
  };

  /* ---------------------------------------------------------------
     Ozgun (Turkce) metinleri sakla
     --------------------------------------------------------------- */
  var ozgun = null;

  function ozgunTopla() {
    if (ozgun) return;
    ozgun = {};
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      var a = el.getAttribute("data-i18n");
      ozgun[a] = el.hasAttribute("data-i18n-html")
        ? el.innerHTML : el.textContent;
    });
    document.querySelectorAll("[data-i18n-attr]").forEach(function (el) {
      var ciftler = el.getAttribute("data-i18n-attr").split(",");
      ciftler.forEach(function (c) {
        var p = c.split(":");
        if (p.length !== 2) return;
        var attr = p[0].trim();
        ozgun["@" + attr + "@" + p[1].trim()] = el.getAttribute(attr) || "";
      });
    });
    // Baslik ve aciklama
    ozgun["meta.baslik"] = document.title;
    var d = document.querySelector('meta[name="description"]');
    ozgun["meta.aciklama"] = d ? d.getAttribute("content") : "";
  }

  /* ---------------------------------------------------------------
     Dili uygula
     --------------------------------------------------------------- */
  function uygula(dil) {
    ozgunTopla();
    var en = dil === "en";
    var sozluk = en ? EN : ozgun;

    /* Surum yer tutucusu: hem EN sozlugunde hem HTML'den saklanan
       TR metninde `{s}` gecebilir. Gercek deger katalogdan gelir
       (window.__GOKTUNGU_SURUM). Katalog henuz yuklenmediyse yer
       tutucu ham gorunmesin diye ifade tumden atlanir; indir.js
       katalog gelince `surumYaz` ile yeniden yazar.
       Bu, surumun sitede TEK yerden (imzali katalog) beslenmesini
       saglar; dil degistirince eski numaranin geri gelmesi
       kusuru da boylece ortadan kalkar. */
    var _s = window.__GOKTUNGU_SURUM || "";
    var _sh = window.__GOKTUNGU_SURUMLER || {};
    /* Oge belirli bir surum hattini isteyebilir (`data-surum-urun`).
       Iki hat bagimsiz ilerledigi icin (gcs / kopru) tek global deger
       yeterli degildir: kopruye ait metinlere GCS numarasi basiliyordu. */
    function surumUygula(v, urun) {
      if (typeof v !== "string" || v.indexOf("{s}") < 0) return v;
      var s = (urun && _sh[urun]) ? _sh[urun] : _s;
      if (!s) return null;               /* katalog yok: dokunma */
      return v.replace(/\{s\}/g, s);
    }

    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      var a = el.getAttribute("data-i18n");
      var v = surumUygula(sozluk[a], el.getAttribute("data-surum-urun"));
      if (v == null) return;
      if (el.hasAttribute("data-i18n-html")) el.innerHTML = v;
      else el.textContent = v;
    });

    document.querySelectorAll("[data-i18n-attr]").forEach(function (el) {
      el.getAttribute("data-i18n-attr").split(",").forEach(function (c) {
        var p = c.split(":");
        if (p.length !== 2) return;
        var attr = p[0].trim(), anahtar = p[1].trim();
        var v = en ? EN[anahtar] : ozgun["@" + attr + "@" + anahtar];
        if (v != null) el.setAttribute(attr, v);
      });
    });

    // Sayfa ust verisi
    document.documentElement.setAttribute("lang", en ? "en" : "tr");
    if (sozluk["meta.baslik"]) document.title = sozluk["meta.baslik"];
    var md = document.querySelector('meta[name="description"]');
    if (md && sozluk["meta.aciklama"]) {
      md.setAttribute("content", sozluk["meta.aciklama"]);
    }
    var ogl = document.querySelector('meta[property="og:locale"]');
    if (ogl) ogl.setAttribute("content", en ? "en_US" : "tr_TR");

    // Dugme durumu
    document.querySelectorAll("[data-dil]").forEach(function (b) {
      b.classList.toggle("etkin", b.getAttribute("data-dil") === dil);
      b.setAttribute("aria-pressed",
        b.getAttribute("data-dil") === dil ? "true" : "false");
    });

    try { localStorage.setItem(ANAHTAR, dil); } catch (e) { /* yok say */ }
    window.goktunguDil = dil;
    // Indirme kartlari gibi sonradan uretilen icerik dinler
    document.dispatchEvent(new CustomEvent("dilDegisti", { detail: dil }));
  }

  /* ---------------------------------------------------------------
     Ilk dil secimi
     --------------------------------------------------------------- */
  function ilkDil() {
    var kayitli = null;
    try { kayitli = localStorage.getItem(ANAHTAR); } catch (e) { /* yok say */ }
    if (kayitli === "tr" || kayitli === "en") return kayitli;
    // URL parametresi onceliklidir (?dil=en veya ?lang=en)
    var s = new URLSearchParams(location.search);
    var p = (s.get("dil") || s.get("lang") || "").toLowerCase();
    if (p === "en" || p === "tr") return p;
    // Tarayici dili Turkce degilse Ingilizce sun
    var t = (navigator.language || "tr").toLowerCase();
    return t.indexOf("tr") === 0 ? "tr" : "en";
  }

  /* ---------------------------------------------------------------
     Baglama
     --------------------------------------------------------------- */
  function baglan() {
    document.querySelectorAll("[data-dil]").forEach(function (b) {
      b.addEventListener("click", function () {
        uygula(b.getAttribute("data-dil"));
      });
    });
    uygula(ilkDil());
  }

  // Sozluge dis erisim (indir.js kullanir)
  window.goktunguSozluk = EN;
  window.goktunguDilUygula = uygula;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", baglan);
  } else {
    baglan();
  }
})();
