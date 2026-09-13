/* GOKTUNGU v2.12.3 -- Gizlilik politikasi, EN sozlugu (M20) */
window.YASAL_EN = {
  "@baslik": "Privacy Policy | GÖKTUNGU",

  /* Ortak */
  "menu.mimari": "Architecture",
  "menu.yetenekler": "Capabilities",
  "menu.platformlar": "Platforms",
  "menu.istemciler": "Clients",
  "menu.guvenlik": "Security",
  "menu.giris": "Sign In &rarr;",
  "nav.gizlilik": "Privacy Policy",
  "nav.kvkk": "Data Protection Notice",
  "nav.kullanim": "Terms of Use",
  "nav.cerez": "Cookies and Local Storage",

  /* Baslik */
  "bas.baslik": "Privacy Policy",
  "bas.yururluk": "Effective date:",
  "bas.tarih": "2 August 2026",
  "bas.surum": "System version:",
  "bas.kapsam": "Scope:",
  "bas.kapsamd": "goktungu.com and field clients",

  /* Giris */
  "p.giris": "This policy explains the privacy approach of the GÖKTUNGU command and control system developed by Gökkubbe Teknoloji Anonim Şirketi. For the statutory notice concerning the processing of personal data, please refer to the <a href=\"/yasal/kvkk/\">Data Protection Notice</a>. This policy sets out, at a technical level, where data resides as a consequence of the system architecture and which data never reaches any part of the system at all.",

  /* 1. Ilkeler */
  "h.ilke": "1. Core Privacy Principles",
  "p.ilke1": "GÖKTUNGU is designed for use in defence and security operations. Its privacy approach is therefore stricter than is customary in commercial software and rests on four principles.",
  "l.ilke1": "<strong>Data minimisation.</strong> The system collects no data that is not necessary for the conduct of operations. No usage measurement, behavioural analysis, advertising profiling or marketing tracking is carried out.",
  "l.ilke2": "<strong>On-premises processing.</strong> All connections to field hardware remain within the organisation's own network. Raw sensor data and serial port traffic never leave the corporate network; only resolved operational data is transmitted to the cloud.",
  "l.ilke3": "<strong>Tenant isolation.</strong> Each organisation's data is held under its own tenant identity. Cross-organisation data access is prevented at the data access layer, not merely at application level.",
  "l.ilke4": "<strong>Absence of third parties.</strong> No third-party analytics tool, advertising script, external font or content delivery network is used in the public website, the command and control interface or the corporate panel. While pages load, your browser connects solely to our own server.",

  /* 2. Toplanan */
  "h.toplanan": "2. Data Collected",
  "h3.kurum": "2.1 Organisation and user information",
  "p.kurum1": "During organisation registration, the tax identification number, legal title, short name, address, province, telephone number, electronic mail address, website and corporate logo are collected. When a user is defined, the name and surname, job title, telephone number, electronic mail address and role within the organisation are recorded. The corporate logo and accent colour are used so that the interface reflects the organisation's identity.",
  "h3.harekat": "2.2 Operational data",
  "p.harekat1": "Aircraft telemetry, radar detections, track history, flight records, mission type, position and altitude information are stored within the organisation's tenant space. This data is processed for the purposes of building the operational picture, post-mission review and reporting.",
  "h3.guvenlik": "2.3 Security records",
  "p.guvenlik1": "Successful and failed sign-in attempts are recorded together with the timestamp, electronic mail address, network address, browser identifier and reason for failure. For field clients, the machine name, platform, version, first registration and last seen times and last network address are retained. These records are necessary for the detection of unauthorised access attempts.",

  /* 3. Toplanmayan */
  "h.toplanmayan": "3. Data Not Collected",
  "p.toplanmayan1": "The following data is neither collected nor stored by any component of the system:",
  "l.yok1": "Passwords in clear form. Passwords are stored only as salted digests and are never written to disk on field clients in any form.",
  "l.yok2": "The file system, running process list or user activity of the field computer. The client executes only the tasks assigned to it.",
  "l.yok3": "Usage statistics, session heat maps, click tracking or behavioural analysis.",
  "l.yok4": "Advertising identifiers, cross-site tracking identifiers or fingerprinting data.",
  "l.yok5": "Raw serial port traffic or unprocessed sensor output. Such data is resolved within the corporate network and is not transmitted to the cloud.",

  /* 4. Mimari */
  "h.mimari": "4. Privacy Consequences of the Architecture",
  "p.mimari1": "As of version 2.5.1 the server does not connect directly to field hardware. Connections are established by compiled clients running within the organisation's own network, and those clients open only an <strong>outbound</strong> encrypted connection to the cloud. This design has three concrete privacy consequences.",
  "t.mim.h1": "Design decision",
  "t.mim.h2": "Privacy consequence",
  "t.mim.a1": "Outbound connections only",
  "t.mim.a2": "No inbound port is opened on the corporate firewall; the system creates no external route into the organisation's network",
  "t.mim.b1": "Task definitions held on the server",
  "t.mim.b2": "No connection definition, address or credential is stored on the field computer; loss of a device does not expose the operational infrastructure",
  "t.mim.c1": "Raw data resolved in the field",
  "t.mim.c2": "Sensor and serial port traffic never leaves the corporate network, minimising both the volume of data carried over the network and the exposure surface",

  /* 5. Harita */
  "h.harita": "5. Map Imagery and Operational Security",
  "p.harita1": "The satellite and map imagery in the interface is obtained from providers established abroad. However, these requests are made <strong>by our server</strong> rather than by your browser, and the retrieved imagery is cached on the server. As a result neither your network address, nor your browser information, nor your session information is transmitted to the map provider; only the geographic index of the image tile is sent.",
  "uyari.opsec": "<strong>Operational security warning.</strong> Although requesting the map tiles of an area does not in itself involve personal data, it may indirectly permit inferences about the <strong>geographic area of interest</strong>. For missions requiring full isolation on operational security grounds, it is recommended that the map cache for the relevant area be downloaded before the mission and that offline map mode be used. In that case no external map request is made for the duration of the mission.",

  /* 6. Saha */
  "h.saha": "6. Privacy in Field Clients",
  "p.saha1": "Field clients are distributed as closed source, in compiled binary form only. On first run a username and password are requested; once the password has been verified by the server it is <strong>not stored</strong> on the device. Instead a device-specific token is generated and saved in encrypted form, using the operating system protection layer on Windows and a key derived from a hardware fingerprint on Ubuntu. On the server side only the digest of this token is retained, and tokens can be revoked individually.",
  "p.saha2": "Clients write no connection definition to local disk. When the cloud connection is lost, running tasks are safely stopped, their definitions are held in memory only, and they are retrieved again from the server once connectivity is restored.",

  /* 7. Paylasim */
  "h.paylasim": "7. Data Sharing",
  "p.paylasim1": "Operational data is under no circumstances shared for commercial purposes, sold, leased or used for advertising. Data is shared only upon lawful and reasoned requests of public authorities competent under the law, limited to the scope of the request. Where such a request is received, the relevant organisation is informed to the extent that no legal impediment exists.",

  /* 8. Barindirma */
  "h.barindirma": "8. Hosting",
  "p.barindirma1": "The system and its database are hosted on servers located within the territory of the Republic of Türkiye. Where corporate requirements demand it, the entire system may be deployed on the organisation's own premises, in which case no data leaves the organisation's boundaries.",

  /* 9. Degisiklik */
  "h.degisiklik": "9. Amendments to this Policy",
  "p.degisiklik1": "This policy may be updated in line with functional changes made to the system and with legislative developments. The current text is always published at this address and its effective date is shown in the heading. Material changes are additionally notified to organisation administrators.",

  "kunye": "<strong>Publisher:</strong> Gökkubbe Teknoloji Anonim Şirketi<br>Ahi Evren OSB Mahallesi, Büyük Selçuklu Caddesi No: 2/B, Sincan / Ankara, Türkiye<br>Sincan Tax Office &middot; Tax ID 6290873411 &middot; Commercial Register No 418199<br><a href=\"https://gokkubbetech.com\" rel=\"noopener\">gokkubbetech.com</a><br>System: <a href=\"https://goktungu.com\">goktungu.com</a> &middot; Version {s} &middot; Protocol GZ-PROTO-251",

  /* Alt bilgi */
  "ft.tanim": "GÖKTUNGU is a command and control system that fuses radar, unmanned aircraft and AI vision sources into a single operational picture for low-altitude airspace awareness.",
  "ft.sistem": "System",
  "ft.yasal": "Legal",
  "ft.iletisim": "Contact",
  "ft.ulke": "Türkiye",
  "ft.kunye": "Gökkubbe Teknoloji Anonim Şirketi. All rights reserved. GÖKTUNGU is a product of Gökkubbe Teknoloji Anonim Şirketi.",
  "ft.surum": "Version {s}"
};
