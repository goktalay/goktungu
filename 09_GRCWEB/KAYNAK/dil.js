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
       saha istemcisi       -> field client
       cok kiracili         -> multi-tenant
       kiraci yalitimi      -> tenant isolation
       gorev yurutucu       -> task executor
       iz takibi            -> track management
     --------------------------------------------------------------- */
  var EN = {
    /* --- Sayfa ust verisi --- */
    "meta.baslik": "GÖKTUNGU — Low-Altitude Airspace Command and Control System | Gökkubbe Teknoloji",
    "meta.aciklama": "GÖKTUNGU is a low-altitude airspace command and control system that fuses radar, unmanned aircraft and AI vision sources into a single operational picture. The ground control station runs on the organisation's own computer. A product of Gökkubbe Teknoloji Anonim Şirketi.",

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
    "hero.rozetSon": "Local Operations · Central Management",
    "hero.rozetCanli": "system online",
    "hero.baslik": "A single operational picture<br><em>of low-altitude airspace</em>",
    "hero.alt": "GÖKTUNGU fuses radar systems, unmanned aircraft, fixed cameras and AI vision servers into one geospatial operational picture. The ground control station runs on the organisation's own computer, while the central server manages the fleet, its users and the flight archive from a single point.",
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
    "mimari.aciklama": "The ground control station runs on the organisation's own computer and connects to the aircraft directly, so mapping, telemetry and mission management are unaffected by internet outages. Only an outbound encrypted connection is opened towards the centre. This approach requires no inbound port on the corporate firewall, and no static IP address or domain name allocation.",
    "mimari.saha": "Ground Control Station",
    "mimari.sahanot": "Corporate computer &middot; Python + web interface",
    "mimari.dron": "Drone Connection Manager",
    "mimari.dronalt": "MAVLink v1/v2 &middot; serial, TCP, UDP, SITL",
    "mimari.radar": "Radar and Camera Layer",
    "mimari.radaralt": "AERIS-compatible JSON, binary frame, RTSP and MJPEG",
    "mimari.ai": "Map and Mission Engine",
    "mimari.aialt": "CesiumJS globe, route planning, flight reporting",
    "mimari.ok": "reverse WebSocket<br>outbound only",
    "mimari.bulut": "Central Server",
    "mimari.bulutnot": "goktungu.com &middot; multi-tenant",
    "mimari.komuta": "Installation Registry and Relay",
    "mimari.komutaalt": "Online station list, reverse connection relaying",
    "mimari.yonetim": "Corporate Management Panel",
    "mimari.yonetimalt": "Pilot roster, flight and video records",
    "mimari.veri": "Version Repository and Archive",
    "mimari.verialt": "Ed25519 signed updates, per-tenant isolation",

    /* --- Ters WebSocket kopru vurgusu --- */
    "proto.etiket": "Reverse Connection Architecture",
    "proto.baslik": "No static IP, no open ports",
    "proto.aciklama": "Ground control stations operate on home and office internet connections, usually with a dynamic IP address and behind NAT, so the centre cannot reach them. For this reason the station always initiates the connection: it opens an encrypted WebSocket towards the centre and keeps it open. The centre sends its queries back through this ready channel.",
    "proto.k1": "Installation Identity",
    "proto.k1alt": "On first launch the ground control station registers with the centre and receives its own installation identifier together with a secret key. The secret is shown only once, is stored on the station and is used to authenticate every subsequent connection.",
    "proto.k2": "Online Station List",
    "proto.k2alt": "When the MERKEZ connection type is selected in the connection manager, the organisation's stations that are online at that moment are listed. The operator picks one from the list without entering any address or port.",
    "proto.k3": "Local Continuity on Loss",
    "proto.k3alt": "If the connection to the centre drops, the flight continues: mapping, telemetry and mission management keep running locally. The bridge reconnects on its own with increasing back-off delays.",
    "proto.eskibas": "Classic remote access",
    "proto.eski1": "Static IP address or domain name allocation",
    "proto.eski2": "An inbound port is opened on the firewall",
    "proto.eski3": "Port forwarding rule on the router",
    "proto.eski4": "The station becomes reachable from the internet",
    /* {s} = surumler.json'dan gelen surum. Sabit numara yazilmaz:
       sozluk ile paketler ayri surum gosterirse musteri sitede
       gordugu surumu indiremez. */
    "proto.yenibas": "Version {s} · reverse WebSocket bridge",
    "proto.yeni1": "A dynamic IP address causes no problem",
    "proto.yeni2": "No inbound port is opened",
    "proto.yeni3": "No router configuration is required",
    "proto.yeni4": "The station stays unreachable from the internet",
    "proto.k4": "Remote Status Query",
    "proto.k4alt": "Through the open bridge the centre queries the station's drone list, serial ports, version and service state, so status becomes visible without any inbound connection to the station.",

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
    "ist.baslik": "Ground control station",
    "ist.aciklama": "The GÖKTUNGU ground control station runs on your own computer and its interface is opened from a browser. The same archive runs on Windows and Ubuntu. Download the full installation package for new installations, or the update package to upgrade an existing one: the update package preserves your database, settings and map cache, replaces only the changed files and takes a backup beforehand.",
    "ist.not": "<strong>Choosing a package.</strong> The full installation package contains every file and is extracted into an empty directory; use it for a first installation. The update package carries only the changed files, backs up your existing files before the installation script runs and does not touch the <code>veri/</code> directory. The SHA-256 digest of both packages is published below, and is also shown when you hover over a download link.",
    "ist.sha": "Integrity Verification (SHA-256)",

    /* --- v2.6.0 yenilikleri --- */
    "yeni.rozet": "New",
    "yeni.baslik": "What version {s} brings",
    "yeni.y1": "Central server connection",
    "yeni.y1alt": "A Central Server section has been added to the program settings. After verifying with your corporate account the station registers itself with the centre and appears in your organisation's server list.",
    "yeni.y2": "MERKEZ connection type",
    "yeni.y2alt": "A MERKEZ button has been added to the connection manager. When clicked, your organisation's stations that are online at that moment are listed; you pick one from the list without typing an address or port.",
    "yeni.y3": "Signed update chain",
    "yeni.y3alt": "Update packages are signed with Ed25519. The software will not apply an installation unless the downloaded package signature is verified against the embedded public key.",
    "yeni.y4": "Embedded bridge agent",
    "yeni.y4alt": "The station keeps an encrypted channel to the centre open and answers status queries over it. No static IP address, domain name or open firewall port is required.",

    /* --- Kurulum --- */
    "kur.etiket": "Deployment",
    "kur.baslik": "Commissioning in four steps",
    "kur.a1": "Organisation Registration",
    "kur.a1alt": "An organisation record is created from the corporate panel with tax identification number, legal title, address and logo; the administrator account is designated and pilots are defined under that account.",
    "kur.a2": "Download the Software",
    "kur.a2alt": "The full installation archive is downloaded and extracted into an empty directory. Python 3.11 and PostgreSQL must be installed; on first launch the wizard asks for the database details and creates the schema.",
    "kur.a3": "Register with the Centre",
    "kur.a3alt": "Verification is performed with your corporate account under Program Settings &rsaquo; Central Server, and the station is registered with a name of your choice. From then on the bridge starts automatically at launch.",
    "kur.a4": "Begin Operations",
    "kur.a4alt": "The interface is opened at <code>http://localhost:8000</code>. Drones, radars and cameras are defined in the connection manager; on Linux it can optionally be installed as a service and started automatically when the computer boots.",

    /* --- Guvenlik --- */
    "guv.etiket": "Security",
    "guv.baslik": "Corporate security discipline",
    "guv.aciklama": "All communication between the ground control station and the centre is encrypted. Corporate data is isolated at the tenant level and every distributed package is signed.",
    "guv.g1": "Outbound Connection Only",
    "guv.g1alt": "The station opens a single outbound encrypted connection to the centre. No inbound port needs to be opened on the corporate firewall, and the station does not become reachable from the internet.",
    "guv.g2": "Passwords Are Never Sent to the Interface",
    "guv.g2alt": "The central account password is held on the server side only; it is never sent to the interface under any circumstances, and the screen shows only whether one is defined.",
    "guv.g3": "Single-Use Installation Secret",
    "guv.g3alt": "The secret key generated during registration is stored at the centre only as a digest and is never shown again; if it is lost it must be regenerated.",
    "guv.g4": "Signed Distribution",
    "guv.g4alt": "All distribution packages are signed with Ed25519. The software will not apply an installation unless the downloaded package signature is verified against the embedded public key; SHA-256 digests are published for every file.",
    "guv.g5": "Tenant Isolation",
    "guv.g5alt": "Each organisation's data is held under a separate tenant identity; cross-tenant data access is blocked at system level.",
    "guv.g6": "Flight Data Stays Local",
    "guv.g6alt": "Telemetry and flight records are kept in the organisation's own database. Only the summary records that the organisation sees in its own panel are transferred to the centre.",

    /* --- CTA --- */
    "cta.baslik": "Access the system",
    "cta.aciklama": "Register on behalf of your organisation, define your pilot roster and commission your ground control station to build your operational picture.",
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
    "indir.gcs": "G\u00d6KTUNGU Ground Control Station",
    "indir.gcsalt": "The complete ground control station carrying mapping, telemetry, mission management, camera streams and flight reporting. It runs on your own computer, connects to the aircraft directly and opens only an outbound encrypted connection to the centre.",
    "indir.sunucu": "Central Server",
    "indir.sunucualt": "Multi-tenant central server software.",
    "indir.kopru": "Bridge Agent",
    "indir.koprualt": "The reverse connection agent that links the ground control station to the centre.",
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
    function surumUygula(v) {
      if (typeof v !== "string" || v.indexOf("{s}") < 0) return v;
      if (!_s) return null;              /* katalog yok: dokunma */
      return v.replace(/\{s\}/g, _s);
    }

    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      var a = el.getAttribute("data-i18n");
      var v = surumUygula(sozluk[a]);
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
