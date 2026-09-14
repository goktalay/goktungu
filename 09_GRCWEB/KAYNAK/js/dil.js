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

   (c) Gokkubbe Teknoloji Anonim Sirketi
   ================================================================= */
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
       cok kiracili         -> multi-tenant
       kiraci yalitimi      -> tenant isolation
       ters WebSocket       -> reverse WebSocket
       iz takibi            -> track management
     --------------------------------------------------------------- */
  var EN = {
    /* v2.14.0 — YETENEK BLOKLARI (yn.*): her yetenek animasyonlu
       sema + teknik kunye ile anlatilir. TR kaynak HTML'dedir;
       asagidaki karsiliklar EN kipinde yazilir. */
    "yn.radar.semaAd": "Fusion · Common Frame",
    "yn.radar.etiket": "C20 Scanning Radar",
    "yn.radar.baslik": "Several radars, one tracking frame",
    "yn.radar.metin": "Each radar looks from its own position. The system does not list them separately: every plot is shifted into a common frame centred on the command position and enters the same tracker. A single target seen by two radars becomes one track on the map.",
    "yn.radar.k1a": "Protocol",
    "yn.radar.k1b": "Binary frame level: login, heartbeat, CRC checking and register read/write",
    "yn.radar.k2a": "Tracking",
    "yn.radar.k2b": "Per-axis Kalman filter, GNN association, M-of-N track confirmation",
    "yn.radar.k3a": "Position",
    "yn.radar.k3b": "From the device RTK when available, otherwise from the stored latitude/longitude",
    "yn.radar.k4a": "Identity",
    "yn.radar.k4b": "Target identity is namespaced per radar; two radars never collide on the same number",
    "yn.eo.semaAd": "Gimbal · Sector Scan",
    "yn.eo.etiket": "M50 Electro-Optic",
    "yn.eo.baslik": "Daylight and thermal in one system",
    "yn.eo.metin": "The whole vendor SDK is gathered in a single panel: connection and credentials, PTZ and lens, angle positioning, presets, scan/patrol patterns and target tracking. The stream address is read from the device itself — the operator never types one.",
    "yn.eo.k1a": "Control",
    "yn.eo.k1b": "PTZ, lens, go-to-angle, save/recall presets, scan and patrol",
    "yn.eo.k2a": "Tracking",
    "yn.eo.k2b": "Lock a target by drawing a rectangle on the video; air and ground modes",
    "yn.eo.k3a": "Position",
    "yn.eo.k3b": "The device RTK and electronic compass place it on the map with its line of sight",
    "yn.eo.k4a": "Multiple devices",
    "yn.eo.k4b": "Each device keeps its own credentials, stream and camera record",
    "yn.ai.semaAd": "Detection · Classification",
    "yn.ai.etiket": "Video Analysis",
    "yn.ai.baslik": "Every video connection runs its own analysis",
    "yn.ai.metin": "AI is not a separate cloud service: analysis runs on the machine that holds the video. Each camera is processed in its own thread, detection boxes are drawn onto the frame and targets are carried into angular space. Video never leaves the network.",
    "yn.ai.k1a": "C-UAS mode",
    "yn.ai.k1b": "Only the aircraft class enters the engagement chain; people and ground vehicles are filtered out",
    "yn.ai.k2a": "Model",
    "yn.ai.k2b": "ONNX inference with GPU acceleration on suitable hardware",
    "yn.ai.k3a": "Frame rate",
    "yn.ai.k3b": "A 1–30 FPS limit per camera stays in the operator's hands",
    "yn.ai.k4a": "Angular solution",
    "yn.ai.k4b": "The pixel box is converted to azimuth/elevation; range is marked as an estimate",
    "yn.ang.semaAd": "Intercept Solution",
    "yn.ang.etiket": "Engagement Engine",
    "yn.ang.baslik": "Ahead of the target, not behind it",
    "yn.ang.metin": "Chasing a target does not catch it. The system solves the intercept point from the target track and steers the interceptor there; the solution is refreshed at every guidance step. The target can be a radar track, a drone or a video detection.",
    "yn.ang.k1a": "Concurrent",
    "yn.ang.k1b": "A separate solution per target; one mission does not block the others",
    "yn.ang.k2a": "Guidance",
    "yn.ang.k2b": "Adjustable guidance rate; the intercept is recomputed on every step",
    "yn.ang.k3a": "Limit",
    "yn.ang.k3b": "Intercept prediction is capped; an unsolvable case is reported to the operator",
    "yn.ang.k4a": "From video",
    "yn.ang.k4b": "Double-click to track on the video; manual rectangle selection",
    "yn.hava.semaAd": "Swarm · Offset Formation",
    "yn.hava.etiket": "Unmanned Aircraft",
    "yn.hava.baslik": "Four airframe classes, four protocols, one interface",
    "yn.hava.metin": "Multirotor, fixed wing, unmanned helicopter and VTOL are flown from the same screen. The protocol of the device on the telemetry radio is detected automatically; the operator never deals with the distinction.",
    "yn.hava.k1a": "MAVLink",
    "yn.hava.k1b": "ArduPilot: flight modes, missions and telemetry",
    "yn.hava.k2a": "Betaflight",
    "yn.hava.k2b": "Read-only diagnostics over MSP; no arming or motor commands",
    "yn.hava.k3a": "DJI",
    "yn.hava.k3b": "Through the Android bridge application",
    "yn.hava.k4a": "Swarm",
    "yn.hava.k4b": "Leader flies free, followers guided with X/Y/Z offsets",
    "gk.bireyselBaslik": "Individual Account",
    "gk.bireyselAlt": "Open an account in your own name without an organization. You use the operations interface through the browser; no installation required.",
    "gk.bireyselDg": "Create My Account",
    "gk.bireyselSor": "Not affiliated with an organization?",
    "gk.bireyselAc": "Open an individual account",
    /* IS54-CEVIRI-TAMAMLAMA-V1: index.html:1377 icindeki
       <span data-i18n="gk.veya">veya</span> ogesinin karsiligi
       sozlukte YOKTU; Ingilizce kipte ekranda Turkce "veya"
       kaliyordu. Giris ve kayit secenekleri arasindaki ayirac
       metnidir. */
    "gk.veya": "or",
    "gk.kurumSor": "Registering on behalf of an organization?",
    "gk.kurumAc": "Switch to organization registration",
    "gk.bolumKapsam": "Account scope",
    "gk.kapsamGcs": "Operations interface and flight records",
    "gk.kapsamRadar": "Radar module — not available on individual accounts",
    "gk.kapsamGcc": "Ground Control Station Dual — not available on individual accounts",
    "gk.dogBaslik": "Verify your e-mail",
    "gk.dogAlt1": "We sent a verification link to:",
    "gk.dogAlt2": "The link is valid for 24 hours and can be used only once. You can sign in after clicking the link.",
    "gk.dogYinele": "Resend link",
    "gk.dogKapat": "Done",
    "menu.kayit": "Register",
    "menu.girisYap": "Sign In &rarr;",
    /* v2.12.2: oturum KAPALI ust serit hesap menusu.  `menu.girisYap`
       ok isareti tasidigi icin menu ogesi olarak kullanilamaz; kisa
       surumu ayri anahtarda tutulur. */
    "menu.hesapMenu": "Account menu",
    "menu.konukBas": "Account",
    "menu.konukNot": "Sign in with your organization account or register a new organization.",
    "menu.girisYapKisa": "Sign In",
    "menu.musteriPaneli": "Customer Panel",
    "menu.panelNot": "The corporate panel is available to organization administrators only.",
    "menu.harekat": "Operations Interface",
    "menu.cikis": "Sign Out",
    "gk.girisBaslik": "Organization Sign In",
    "gk.girisAlt": "Sign in with your organization account; the operations interface and the customer panel share the same session.",
    "gk.eposta": "E-mail",
    "gk.epostaIpucu": "name.surname@company.com",
    "gk.sifre": "Password",
    "gk.girisDg": "Sign In",
    "gk.kayitSor": "No organization account yet?",
    "gk.kayitAc": "Register your organization",
    "gk.kayitBaslik": "Organization Registration",
    "gk.kayitAlt": "Register your organization and the trial subscription starts immediately. The first pilot and administrator accounts are free.",
    "gk.bolumKurum": "Organization",
    "gk.unvan": "Legal name",
    "gk.unvanIpucu": "e.g. Gokkubbe Technology Inc.",
    "gk.vergi": "Tax number",
    "gk.telefon": "Telephone",
    "gk.adres": "Address",
    "gk.bolumYetkili": "Authorized account",
    "gk.ad": "First name",
    "gk.soyad": "Last name",
    "gk.sifre2": "Password (again)",
    "gk.sifreKural": "At least 8 characters; must contain letters and digits.",
    "gk.kayitDg": "Register Organization",
    "gk.girisSor": "Already have an account?",
    "gk.girisAc": "Sign in",
    "gk.girisHata": "E-mail or password is incorrect.",
    "gk.kayitHata": "Registration could not be completed.",
    "gk.agHata": "Server unreachable. Please try again.",
    "gk.sifreUyusmaz": "Passwords do not match.",
    "gk.sureBitti": "Your session has expired. Please sign in again.",
    "gk.kayitTamamGiris": "Your organization has been registered. Please sign in.",
    /* --- Sayfa ust verisi --- */
    "meta.baslik": "GÖKTUNGU — Low-Altitude Airspace Command and Control System",
    "meta.aciklama": "GÖKTUNGU is a low-altitude airspace command and control system that fuses radar, unmanned aircraft and AI vision sources into a single operational picture. The command and control interface runs centrally; only a lightweight bridge application is installed in the field.",

    /* --- Ust cubuk --- */
    "menu.gSistem": "System",
    "menu.gYetenek": "Capabilities",
    "menu.mimari": "Architecture",
    "menu.yetenekler": "Capabilities",
    "menu.platformlar": "Platforms",
    "menu.arayuz": "Interface",
    "menu.istemciler": "Field Software",
    "menu.fiyat": "Pricing",
    "menu.yardim": "Support",
    "menu.guvenlik": "Security",
    "menu.kurumsal": "Corporate Panel",

    /* --- Hero --- */
    "hero.rozetOn": "Version",
    "hero.rozetSon": "Central Operations \u00b7 Bridge in the Field",
    "hero.rozetCanli": "system online",
    "hero.baslik": "A single operational picture<br><em>of low-altitude airspace</em>",
    "hero.alt": "GÖKTUNGU fuses radar systems and unmanned aircraft into one geospatial operational picture. The command and control interface runs centrally and opens in the browser; only the bridge software carrying drone and radar connections is installed on the field computer.",
    "hero.dg1": "Sign In",
    "hero.dg2": "Corporate Panel",
    "hero.ist1": "Widgets and Panels",
    "hero.ist2": "Radar Protocols",
    "hero.ist3": "MAVLink Messages",
    "hero.ist4birim": " platforms",
    "hero.ist4": "Windows · Ubuntu",
    /* v2.12.0 taktik sahne.  `hero.sahneAlt` canvas sarmalayicisinin
       aria-label'i olarak data-i18n-attr ile yazilir: ekran okuyucu
       kullanicisi animasyonun NE gosterdigini duyar, canvas'in ici
       gezinilebilir icerik olarak sunulmaz. */
    "hero.sahneAlt": "Animation of a rotating globe with a radar station scanning from central T\u00fcrkiye and unmanned aircraft flying patrol",
    "hero.sahneMevzi": "RADAR STATION",

    /* --- Mimari --- */
    "mimari.etiket": "System Architecture",
    "mimari.baslik": "Operations at the centre, connectivity in the field",
    "mimari.aciklama": "The command and control interface runs on the central server; the pilot uses the map, the drone panel and mission management from a browser. The field computer runs only the bridge software: it establishes drone and radar connections locally and carries them over a single encrypted channel to the centre. This approach requires no inbound port on the corporate firewall, no static IP address and no domain allocation.",
    "mimari.saha": "Bridge Software",
    "mimari.sahanot": "Field computer &middot; Python 3.11 &middot; local web panel",
    "mimari.dron": "Drone Service",
    "mimari.dronalt": "MAVLink v1/v2 &middot; serial, TCP, UDP, SITL",
    "mimari.radar": "Radar Service",
    "mimari.radaralt": "AERIS-compatible JSON, binary frame",
    /* v2.9.0: bu dort anahtarin EN karsiligi eksikti (i18n bosluğu) */
    "mimari.gcsdual": "GroundGCC Service",
    "mimari.gcsdualalt": "Dual-screen ground control case",
    "mimari.ok": "reverse WebSocket<br>443 &middot; outbound only",
    "mimari.bulut": "Central Server",
    "mimari.bulutnot": "goktungu.com &middot; multi-tenant",
    "mimari.komuta": "Command and Control Interface",
    "mimari.komutaalt": "CesiumJS globe, route planning, flight reporting",
    "mimari.yonetim": "Corporate Management Panel",
    "mimari.yonetimalt": "Pilot roster and flight records",
    "mimari.veri": "Version Repository and Archive",
    "mimari.verialt": "Ed25519-signed updates, per-tenant isolation",

    /* --- Ters baglanti mimarisi vurgusu --- */
    "proto.etiket": "Reverse Connection Architecture",
    "proto.baslik": "No static IP required, no port opened",
    "proto.aciklama": "Field computers running the bridge software operate on home and office internet connections, usually with a dynamic IP address and behind NAT; the centre cannot initiate a connection to them. For this reason the bridge always initiates: it opens an encrypted WebSocket to the centre and keeps it open. The centre sends its queries back over this established channel.",
    "proto.k1": "Installation Identity",
    "proto.k1alt": "On first run the bridge software registers with the centre and receives its own installation identity and secret key. The secret key is shown only once, is stored on the field computer and is used for authentication on every subsequent connection.",
    "proto.k2": "Bridge Groups",
    "proto.k2alt": "In the connection manager the organisation\u2019s online bridges are grouped with their names and addresses; each bridge\u2019s drone and radar connections are listed under its own group. The operator selects from the list without entering an address or port.",
    "proto.k3": "Local Recording on Loss",
    "proto.k3alt": "When the connection to the centre drops, the bridge records flight data to the local disk; once the link returns the live stream continues without interruption and the recording kept during the outage is preserved. The bridge reconnects on its own with increasing back-off.",
    "proto.eskibas": "Classic remote access",
    "proto.eski1": "Static IP address or domain allocation",
    "proto.eski2": "An inbound port is opened on the firewall",
    "proto.eski3": "Port forwarding rule on the router",
    "proto.eski4": "The field computer becomes reachable from the internet",
    /* {s} = surumler.json'dan gelen surum. Sabit numara yazilmaz:
       sozluk ile paketler ayri surum gosterirse musteri sitede
       gordugu surumu indiremez. */
    "proto.yenibas": "Version {s} \u00b7 reverse WebSocket bridge",
    "proto.yeni1": "A dynamic IP address causes no problem",
    "proto.yeni2": "No inbound port is opened",
    "proto.yeni3": "No router configuration required",
    "proto.yeni4": "The field computer stays unreachable from the internet",
    "proto.k4": "Remote Status Query",
    "proto.k4alt": "Over the open bridge the centre queries the bridge\u2019s drone count, service states and version; status becomes visible without any inbound connection to the field computer.",

    /* --- Yetenekler --- */
    "yet.etiket": "Capabilities",
    "yet.baslik": "Every layer an operation requires",
    "yet.aciklama": "The full detection, classification, tracking and response chain is gathered in a single interface. Only defined and active sources appear in the interface; disabled sources do not clutter the display.",
    "yet.k1": "Radar Detection and Track Management",
    "yet.k1alt": "Polar radar measurements are converted to geodetic coordinates; stable tracks are produced with confirmation thresholds, timeouts and alpha-filtered velocity estimation. A lost target that reappears within the range window is reattached to its previous track.",
    "yet.k2": "Unmanned Aircraft Command",
    "yet.k2alt": "ArduCopter, ArduPlane and ArduRover flight modes are decoded. Take-off, landing, return-to-launch and guided movement commands are issued from the interface; each aircraft receives its own colour and map trail.",
    "yet.k4": "Multi-Tenant Corporate Structure",
    "yet.k4alt": "Each organisation is registered with its own tax identity, legal title and logo. The signed-in organisation's identity appears throughout the interface and in reports; data is isolated at tenant level.",
    "yet.k5": "Pilot and Flight Log Management",
    "yet.k5alt": "Pilot rosters, licence details and flight records are managed from the corporate panel. Flight duration, mission type and aircraft assignment are recorded.",
    "yet.k6": "History Recording and Replay",
    "yet.k6alt": "Detection and flight data are archived; a past mission can be replayed on the map. Tracks are restored from the system when the display is refreshed.",
    "yet.k7": "M50 Electro-Optical Control",
    "yet.k7alt": "On an authorised field Bridge, the operator provides an explicit connection and has access only to limited PTZ, lens and manual-selection tracking controls. Video sources are processed locally; raw device video and session credentials are never relayed to the central layer.",

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
    "plat.not": "<strong>Map symbology.</strong> Airframe class is derived from the MAVLink heartbeat, so no manual selection is required. Unrecognised types fall back to the multirotor symbol; a client running an older protocol never breaks the display.",

    /* --- Arayuz --- */
    "ary.etiket": "Command and Control Interface",
    "ary.baslik": "The operational picture on one screen",
    "ary.aciklama": "Resizable panels, movable windows that can be nested into tabs, and connection indicators in the bottom status bar let the operator monitor the entire system at a glance.",
    /* v2.12.0 vitrin: sekmeli ekran goruntusu gostericisi.  `ss0`
       yeni eklendi (ana harekat resmi artik da bir sekme), `ssNalt`
       aciklamalari sekme listesinde okunur. */
    "ary.sekmeler": "Interface sections",
    "ary.ss0": "Operational Picture",
    "ary.ss0alt": "Radar tracks, air vehicles and routes on a single three-dimensional globe",
    "ary.ss1": "Connection Manager",
    "ary.ss1alt": "Serial, TCP, UDP and virtual connections are grouped under their bridge machine",
    "ary.ss2": "Radar Settings and Calibration",
    "ary.ss2alt": "Site position, north offset, range window and track confirmation threshold are configured",
    "ary.ss3": "Target Classification",
    "ary.ss3alt": "The rule-based classifier assigns a track type from speed and altitude bands",
    "ary.ss5": "History Record Management",
    "ary.ss5alt": "Flight records are archived with a unique code, charts and letterhead report output",
    /* Kare alt yazilari (figcaption): teknik olcut tasir. */
    "ary.c0": "Resizable panels, movable windows and bridge indicators in the bottom status bar",
    "ary.c1": "MAVLink v1/v2 \u00b7 serial, TCP, UDP and virtual transport \u00b7 serial port list reported from the field",
    "ary.c2": "Polar measurements are converted to geodetic coordinates \u00b7 confirmation threshold, timeout and alpha-filtered velocity estimation",
    "ary.c3": "Rule-based classifier \u00b7 minimum sample count, hysteresis and decision threshold are configurable",
    "ary.c5": "Unique flight code and QR \u00b7 speed and altitude charts \u00b7 letterhead PDF report output",

    /* --- Istemciler --- */
    "ist.etiket": "Download Centre",
    "ist.baslik": "Bridge software",
    "ist.aciklama": "The bridge software runs on your field computer and opens a local web panel. You sign in to the panel with your organisation account and see your organisation's logo; from there you start and stop three services (Drone, GroundGCC, Radar) and follow their console output. Separate installers are published for Windows and Ubuntu; both install the software as a service, start it automatically at boot and add Start menu and desktop shortcuts.",
    "ist.not": "<strong>Status indicators.</strong> While a client is running, the corresponding indicator in the command and control interface's bottom status bar turns green and displays a summary. If the client is closed the indicator goes offline; when the radar client is not running, no radar-related interface element is shown.",

    /* --- v2.9.0: indirme kapisi (kurulum dosyalari kurumsal panelden) --- */
    "ist.kapiBaslik": "Installation packages are distributed from the corporate panel",
    "ist.kapiAciklama": "Bridge software and Central Application installers cannot be downloaded directly from this page. Sign in to the corporate panel with your organisation account; the Windows and Ubuntu installers for the products licensed to your organisation are listed there together with their version history and SHA-256 integrity digests. Every download therefore remains bound to a corporate identity, and distribution outside the licence scope is prevented.",
    "ist.kapiDg": "Sign In to Corporate Panel",
    "ist.kapiDg2": "Membership Terms",
    "ist.kapiA1": "Sign in to the corporate panel with your organisation account.",
    "ist.kapiA2": "Products licensed to your organisation and their versions are listed.",
    "ist.kapiA3": "The installer matching your operating system is downloaded.",
    "ist.kapiA4": "The SHA-256 digest is shown and verified at download time.",

    /* --- v2.6.0 yenilikleri --- */
    "yeni.rozet": "New",
    "yeni.baslik": "What version {s} brings",
    "yeni.y1": "Bridge Software Installer",
    "yeni.y1alt": "The bridge software is distributed as a Windows installer (.exe) and an Ubuntu package (.deb). It installs as a service, adds Start menu and desktop shortcuts, and on update stops the service, applies the new files and starts it again.",
    "yeni.y2": "Installer and service management",
    "yeni.y2alt": "In the connection manager at the centre the organisation's online bridges are grouped by name and address; drone and radar connections are listed under their own bridge. You do not need to type an address or a port.",
    "yeni.y3": "Signed update chain",
    "yeni.y3alt": "Update packages are signed with Ed25519. The client will not apply an installation unless the downloaded package signature is verified against the embedded public key.",
    "yeni.y4": "Focus on two platforms",
    "yeni.y4alt": "The Android client has been withdrawn from distribution. Development and verification effort is concentrated on the Windows and Ubuntu/Linux platforms.",

    /* --- Kurulum --- */
    "kur.etiket": "Deployment",
    "kur.baslik": "Commissioning in four steps",
    "kur.a1": "Organisation Registration",
    "kur.a1alt": "An organisation record is created from the corporate panel with tax identification number, legal title, address and logo; the administrator account is designated.",
    "kur.a2": "Download the Client",
    "kur.a2alt": "The installer package matching the field computer's operating system is downloaded. The installer registers the service and adds the system tray icon; if the portable archive is preferred, the file is executed directly.",
    "kur.a3": "Define Identity",
    "kur.a3alt": "A username and password are entered on first launch. The credentials are verified on the server and stored encrypted on the device.",
    "kur.a4": "Begin Operations",
    "kur.a4alt": "The command and control interface opens at <code>https://goktungu.com/app/</code>. Your bridge appears in the connection manager with its name and address; drone and radar connections are defined under that group.",
    /* --- Guvenlik --- */
    "guv.etiket": "Security",
    "guv.baslik": "Corporate security discipline",
    "guv.aciklama": "All communication between the bridge software and the centre is encrypted. Organisation data is isolated at tenant level and every distributed package is signed.",
    "guv.g1": "Outbound Connection Only",
    "guv.g1alt": "The bridge opens a single outbound encrypted connection to the centre. No inbound port needs to be opened on the corporate firewall; the field computer does not become reachable from the internet.",
    "guv.g2": "Passwords Are Not Stored",
    "guv.g2alt": "After authentication only a device-specific token is retained. The user password is never written to disk in any form.",
    "guv.g3": "Hardware-Bound Encryption",
    "guv.g3alt": "The token is encrypted with the operating system protection layer on Windows, and with a key derived from the hardware fingerprint on Ubuntu.",
    "guv.g4": "Signed Distribution",
    "guv.g4alt": "All distribution packages are signed with Ed25519. The client will not apply an update unless the package signature is verified against the embedded public key; SHA-256 digests are published for every file.",
    "guv.g5": "Tenant Isolation",
    "guv.g5alt": "Each organisation's data is held under a separate tenant identity; cross-tenant data access is blocked at system level.",
    "guv.g6": "Closed Source Distribution",
    "guv.g6alt": "When the connection to the centre drops, the bridge writes flight data to the field computer\u2019s disk; the portion recorded during the outage is preserved and shown with its size in the panel. If the disk limit is exceeded the oldest record is kept and the newest data is discarded: in fault investigation the critical portion is at the start of the outage.",

    /* --- Fiyatlandirma ---
       HTML tarafinda Turkce kaynak metin durur; burada yalnizca EN
       karsiliklari tutulur.  data-i18n-html tasiyan ogelerin degeri
       ic etiketleriyle (strong) birlikte yazilmalidir. */
    "fiy.etiket": "Pricing",
    "fiy.baslik": "Membership is free \u2014 pay for your roster",
    "fiy.aciklama": "Organisation membership, one administrator and one pilot seat are free of charge; the command and control interface, the bridge software, radar fusion and flight records are used without limit within this scope. Charges arise only for additional pilot seats and the artificial intelligence feature. Annual billing costs approximately ten months instead of twelve.",
    "fiy.aylik": "Monthly",
    "fiy.yillik": "Annual",
    "fiy.indirim": "20% off on annual billing",
    "fiy.ucretsiz": "Free",
    "fiy.ayBasi": "/mo",
    "fiy.tekSeferlik": "one-off",
    "fiy.onerilen": "most preferred",

    "fiy.k1ad": "Starter",
    "fiy.k1alt": "Organisation membership, one administrator and one pilot seat",
    "fiy.k1m1": "Command and control interface \u2014 from the browser",
    "fiy.k1m2": "Bridge software \u2014 Windows and Ubuntu",
    "fiy.k1m3": "Unlimited aircraft and connections",
    "fiy.k1m4": "Flight records, reports and charts",
    "fiy.k1m5": "Route planning, swarm flight and engagement",
    "fiy.k1dg": "Create Organisation Record",

    "fiy.k2ad": "Professional",
    "fiy.paraTry": "\u20BA Turkish lira",
    "fiy.paraUsd": "$ US dollar",
    "fiy.paraNot": "a foreign card is required",
    "fiy.k2m5": "Swarm flight, route planning and engagement",
    "fiy.koltukEsik": "Free base seat",
    "fiy.koltukBir": "1 seat included",
    "fiy.yillikEsit": "On annual billing",
    "fiy.baslangicFiyat": "and up",
    "fiy.skuMerkez": "core command and control",
    "fiy.skuYz": "+ artificial intelligence module",
    "fiy.skuRadar": "+ radar fusion and GCCDUAL",
    "fiy.skuTam": "all modules included",
    "fiy.k2alt": "Per pilot seat, monthly \u2014 you pay for the size of your roster",
    "fiy.k2m1": "Dedicated account and identity verification for the pilot",
    "fiy.k2m2": "Take-off checklist and signed record",
    "fiy.k2m3": "Own flight history and reports",
    "fiy.k2m4": "Live messaging between pilots",
    "fiy.paket5": "5-pilot pack",
    "fiy.paket10": "10-pilot pack",
    "fiy.k2dg": "Add Seats",

    "fiy.k3ad": "Enterprise Cloud",
    "fiy.k3m5": "Priority support and flight record archive",
    "fiy.k3alt": "A single charge per organisation, independent of pilot count",
    "fiy.k3m1": "Object and vehicle detection from video",
    "fiy.k3m2": "Licence plate reading and rule-based classification",
    "fiy.k3m3": "Alarm generation and event logging",
    "fiy.k3m4": "In-house AI computers \u2014 managed over SSH",
    "fiy.k3dg": "Enterprise Enquiry",

    "fiy.k4ad": "On-Premise Licence",
    "fiy.bakimNot": "The first year of maintenance and updates is <strong>included</strong>. In subsequent years a maintenance fee of <strong>18%</strong> of the licence value applies. <strong>When the maintenance term ends the system continues to operate</strong>; only the entitlement to new releases and support ceases.",
    "fiy.k4alt": "The full edition running on your own server \u2014 perpetual right of use",
    "fiy.k4m1": "Unlimited pilot seats and aircraft",
    "fiy.k4m2": "<strong>Air-gapped operation</strong> \u2014 no internet connection required",
    "fiy.k4m3": "Windows installer and Ubuntu package",
    "fiy.k4m4": "PostgreSQL setup wizard on first launch",
    "fiy.k4m5": "Can run on the same computer as the bridge software",
    "fiy.k4m6": "Organisation-specific licence file signed with Ed25519",
    "fiy.k4dg": "Request Licence",

    "fiy.notRadar": "<strong>Radar fusion and the GCCDUAL dual-screen ground control station are not offered for sale in the subscription tier.</strong> These modules are defined per organisation solely by the senior system administrator; hardware compatibility, training and regulatory conditions are assessed separately. Where they are defined for your organisation they appear automatically in the bridge software menu and in the command and control interface; where they are not, they do not appear at all. These modules are opened only within the on-premise licence tiers (<strong>GTU-RADAR</strong>, <strong>GTU-TAM</strong>) or by provisioning from the senior system administrator.",

    "fiy.talepBaslik": "Preliminary request assessment",
    "fiy.talepAciklama": "G\u00d6KTUNGU is an operational system within the scope of the defence industry; memberships are not opened automatically through open registration. When you create an organisation record your application is taken into <strong>preliminary request assessment</strong>: the organisation identity, field of activity and intended use are reviewed. Following the assessment the system administrator defines the membership appropriate to your organisation, and this includes <strong>direct provisioning that requires no payment flow</strong>. For public institutions, defence industry organisations and research institutions, seat counts, the artificial intelligence feature and the Central Application licence are assessed on a per-project basis.",
    "fiy.t1": "Organisation record",
    "fiy.t1alt": "A record is created from the corporate panel with the organisation title, tax details and authorised representative information.",
    "fiy.t2": "Assessment",
    "fiy.t2alt": "The application is reviewed; where necessary a meeting is requested to discuss the intended use and operational scope.",
    "fiy.t3": "Membership provisioning",
    "fiy.t3alt": "The free base membership is opened for the approved organisation; the requested seat, artificial intelligence and module entitlements are defined.",
    "fiy.t4": "Transition to use",
    "fiy.t4alt": "The bridge software is downloaded, the pilot roster is defined from the corporate panel and the operational picture is established.",

    "fiy.kosulBaslik": "Payment and scope conditions",
    "fiy.ks1": "<strong>Domestic payments are denominated in Turkish lira and international payments in United States dollars.</strong> Collection is carried out in the name of <strong>G\u00f6kkubbe Teknoloji Anonim \u015eirketi</strong> through the iyzico infrastructure (tax no. 6290873411). Payment in foreign currency requires a foreign card.",
    "fiy.ks2": "<strong>Membership and role management is carried out from the corporate panel.</strong> Adding pilots, changing roles and purchasing seats are conducted from the organisation administrator's panel, not from the command and control interface.",
    "fiy.ks3": "<strong>Your existing pilots are never locked out.</strong> Once the free seat is taken, a seat is purchased in order to add a new pilot; under no circumstances is a defined pilot's access withdrawn.",
    "fiy.ks4": "<strong>The annual billing discount is 20%.</strong> Annual amounts correspond to approximately ten months rather than twelve.",
    "fiy.ks5": "<strong>The command and control interface is intended for the desktop browser.</strong> The bridge software is published for Windows and Ubuntu; in addition, Android bridge applications are provided for <strong>DJI</strong> and <strong>MAVLink</strong> aircraft. The Android applications act solely as bridges and do not replace the command interface.",
    "fiy.ks6": "<strong>The on-premise licence is organisation-specific.</strong> The signed licence file is valid only for the organisation it names; the licence file is preserved when the software is removed.",

    /* --- CTA --- */
    "cta.baslik": "Access the system",
    "cta.aciklama": "Register on behalf of your organisation, define your pilot roster and install the bridge software to build your operational picture.",
    "cta.dg1": "Create Organisation Record",
    "cta.dg2": "Command and Control Interface",

    /* --- Alt bilgi --- */
    "ft.tanim": "GÖKTUNGU is a command and control system that fuses radar and unmanned aircraft sources into a single operational picture for low-altitude airspace awareness.",
    "ft.sistem": "System",
    "ft.erisim": "Access",
    "ft.iletisim": "Contact",
    "ft.yasal": "Legal",
    "ft.istemciindir": "Field Software",
    "ft.kurulum": "Deployment",
    "ft.yardim": "Support Center",
    "ft.gizlilik": "Privacy Policy",
    "ft.kullanim": "Terms of Use",
    "ft.cerez": "Cookie Policy",
    "ft.kvkk": "Data Protection Notice",
    "ft.ulke": "Türkiye",
    "ft.kunye": "Gökkubbe Teknoloji Anonim Şirketi. All rights reserved. GÖKTUNGU is a product of Gökkubbe Teknoloji Anonim Şirketi.",
    "ft.surum": "Version {s}",
    /* Site surum defteri: URUN surumunden ayri yurutulur
       (js/surum_verisi.js). */
    "ft.defter": "Site version",
    "ft.defterIpucu": "Open the site version log",

    /* --- Indirme kartlari (js/indir.js tarafindan kullanilir) --- */

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
