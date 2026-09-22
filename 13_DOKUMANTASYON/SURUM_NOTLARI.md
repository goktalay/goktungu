# GÖKTUNGU Sürüm Notları — GRCOFF

Uygulama `js/surum.js` (`GCS_SURUM`), paket `goktungu/paket_surum.py`.

> Not: 2.5.29 ve sonrası girdiler git geçmişinden (`git log`) özetlenmiştir; her başlık gerçek bir commit'e dayanır. Tam ayrıntı için ilgili commit'e / `GCS_SURUM_GECMISI`'ne bakın.

## Paket 2.5.126 / Uygulama 2.4.256 — 2026-09-21

**Marka: Türkbey Teknoloji A.Ş. amblemi tüm ürün ikonlarında (paket 2.5.126)**

- Tüm sistemde (GRCOFF, GRCON, PWA, favicon, .ico, köprü, Android, web) proje sahibi Türkbey Teknoloji A.Ş. amblemi (kırmızı kalkan-kurt) kullanılır; GÖKTUNGU ürün adı korunur. Android MAVLink köprüsü 1.1.2 ve Köprü 1.7.26 launcher ikonlarına da uygulandı.

## Paket 2.5.123–2.5.125 / Uygulama 2.4.253–2.4.255 — 2026-09-20

**3B harita ikonları, cam kokpit PFD'si ve HOME sembolü**

- 3B harita ikonları (glTF) + dron paneli cam kokpit PFD'si (2.5.123); sanal dron kimlik çakışması düzeltmesi ve panel/3B ikon ince ayarları (2.5.124); HOME ikonu daire içinde 'H' standart helipad sembolü (2.5.125).

## Paket 2.5.121–2.5.122 / Uygulama 2.4.251–2.4.252 — 2026-09-18

**Makro güvenliği: konum koruması ve panik gözcüsü**

- Makro konum koruması ve SITL panik gözcüsü eklendi (2.5.121); ardından panik gözcüsü kaldırıldı, makro irtifa 0 kaynağında engellendi ve görev soruları kaldırıldı (2.5.122).

## Paket 2.5.112–2.5.120 / Uygulama 2.4.242–2.4.244 — 2026-09-18

**Python makroları, makro editörü ve video aktarımı**

- Köprüdeki kamera görüntüsünün GRCON ve GRCOFF'a köprü üzerinden aktarımı (#140, 2.5.112, Köprü 1.7.25); Rotalar > Makrolar altında Python makroları (#137, 2.5.113); makro editörüne Python sözdizimi vurgulama ve siyah çıktı konsolu (2.5.114). Katalog yayın betikleri 2.5.119 ve 2.5.120 ile güncellendi. (Ara sürümler için git geçmişine bakın.)

## Paket 2.5.99–2.5.111 / Uygulama 2.4.229–2.4.241 — 2026-09-16 – 2026-09-18

**Köprü mimarisi, kurumsal panel köprü yönetimi ve marka ikonları**

- Yeni Türkbey kurt ikonu (gece/gündüz) tüm ürünlerde (2.5.111); GRCON'da yeni kayıt için çevrimiçi köprü zorunlu, kamera köprü seçici (2.5.110); bağlantı diyagramı düğmesi, SITL uçuş kaydı kapatıldı (2.5.109); yerel kipte tüm formlarda köprü seçimi (2.5.108); tema uyumlu Türkbey logo/ikon (2.5.107); ilk kurulumda varsayılan Radar/M50 kaydı yok (2.5.106); kopru.json gerçek veri köküne yazılır (2.5.105); GRCON merkez kipinde güncelleme arayüzü kaldırıldı (2.5.104); API kodlu kurulum, köprüler kurumsal panelde, gerçek Android köprü ajanları (2.5.103, Kurumsal Panel 1.4.0, Android köprüleri 1.1.0); Destek > Köprüler paneli (2.5.102, Köprü 1.7.23); merkez kipinde firmaya özel radar/EO kayıtları (2.5.101); köprüler listeden kaldırılabilir, köprü son IP/görülme (2.5.100); kritik telemetri replayAktif çökme düzeltmesi + /app/ vekili yol öneki (2.5.99).

## Paket 2.5.94–2.5.98 / Uygulama 2.4.224–2.4.228 — 2026-09-16

**Radar protokol v3.0.0, takip araç çubuğu ve sahiplik unvanı**

- Sahip firma unvanı Türkbey Teknoloji Anonim Şirketi tüm ürünlerde (2.5.98, Köprü 1.7.22); radar yönetim penceresi, protokol v3.0.0 tüm yüzeyi (2.5.97); takip araç çubuğu 10 Hz yeniden çizimi kaldırıldı, Angaje Ol/Takip Et/Bırak tıklanabilir (2.5.96); tespit-takip ayrımı, M50 penceresinde AI+takip ayarları (2.5.95); AI ayarlarında Uygula, %80 tam ekran, dron kapat/küçült (2.5.94).

## Paket 2.5.75–2.5.92 / Uygulama 2.4.205–2.4.222 — 2026-09-15 – 2026-09-16

**M50 canlı görüntü penceresi ve Elektro-Optik altyapısı**

- Kamera penceresi konsol yüksekliği + tam ekran, takip AI'dan bağımsız (2.5.92); kameralar.js önbellek etiketi düzeltmesi (2.5.91); Kameralar paneli sadeleşti, harita offline radar/M50 düzeltmeleri (2.5.89–2.5.90); hava aracı modeli paketleme, Jetson GPU kurulum betiği (2.5.88); Ubuntu ARM64 M50 vaInitialize düzeltmesi (2.5.87); Ubuntu M50 ARM64 SDK / x86_64 Wine köprüsü (2.5.86); M50 cihaz OSD'si (2.5.85); M50 penceresi bilgi katmanı ve sürüm rozeti (2.5.84); M50 sol panel ayracı (2.5.83); OpenCV RTSP zaman aşımı geri alındı (2.5.82); vekil kilidi kamera başına, süreç içi video kaydı (2.5.81); M50 penceresi ekran bilgileri ve video kaydı (2.5.80); M50 hava aracı tanıma entegrasyonu, PTZ takibi (2.5.79); harita M50 önizlemesine çift tık (2.5.78); M50 penceresi durum çubuğu, tekerlekle zoom (2.5.77); M50 canlı görüntü penceresi ayrı sistem (2.5.76); M50 PTZ kaydırıcı ve ayrılabilir görüntü penceresi (2.5.75).

## Paket 2.5.53–2.5.74 / Uygulama 2.4.183–2.4.204 — 2026-09-14 – 2026-09-15

**Çoklu radar / Elektro-Optik (Faz A–D), M50 protokolü ve kök neden düzeltmeleri**

- M50 canlı görüntü RTSP kimliği yakalama katmanında (2.5.74); açılış lisans özetine m50 alanı (2.5.73); harita etiketleri hover, dron rengi seçimi (2.5.72); Yardım > Lisansı Yenile (2.5.71); EO menü bayrağı korumada (2.5.70); köprüsüz kurulumda Elektro-Optik menüsü (2.5.69); olay döngüsü deadlock düzeltmesi (2.5.68); sihirbaz WS sırası bağımsız (2.5.67); gizli panel CSS ve sihirbaz düzeltmeleri (2.5.66); sihirbaz/liste paneli düzeltmeleri (2.5.65); Radarlar ve Elektro Optik liste panelleri (2.5.64); Faz D (2.5.63) ve Faz C (2.5.62); çoklu Elektro-Optik Faz B + RTK konumu (2.5.61); çoklu radar Faz A (2.5.60); Kamera Yönetimi sadeleştirme (2.5.59); Elektro-Optik paneli tam SDK (2.5.58, Köprü 1.7.18); M50 RTSP otomatik (2.5.57, Köprü 1.7.17); M50 köprüsüz mod durumu (2.5.56); M50 SDK DLL yolu düzeltmesi (2.5.55); M50 köprüsüz doğrudan bağlantı (2.5.54); köprü liste/güncelleme hata gösterimi (2.5.53).

## Paket 2.5.29–2.5.52 / Uygulama 2.4.159–2.4.182 — 2026-09-13 – 2026-09-14

**C-UAS modu, YOLO tespiti, elle hedef seçimi ve kritik havuz/çökme düzeltmeleri**

- Hava aracı tespitinde sınıf bazlı taban eşik sertleştirmesi (2.5.52); M50 kamera protokolü, sürükle-bırak PTZ (2.5.51); kesin kök neden: os.fchmod Windows'ta yok, takip_isle çökmesi (2.5.50); AI uç hataları konsol panelinde (2.5.49); AI uç hatalarında tam traceback (2.5.48); kesin kök neden: AI HTTP uçları PG bağlantı havuzunu sızdırıyordu (2.5.47); piksel takip düğmeleri kayboluyordu (2.5.46); YOLO tespiti her karede (2.5.45); piksel takip artık bloklamıyor (2.5.44); Angaje Ol/Takip Et düğmeleri, mesafeli takip (2.5.43); elle hedef seçimi — dikdörtgen çiz (2.5.42); canlı AI teknoloji/performans rozeti (2.5.41); YOLO GPU hızlandırması, ONNX Runtime + DirectML (2.5.40); hava aracı tip sınıflandırması, sınıf bazlı hassasiyet (2.5.39); yanlış alarm koruması + YOLO ONNX dron modeli (2.5.38); ffmpeg'siz RTSP/video oynatma (2.5.37); video dosyası kamera kaynağı (2.5.36); C-UAS modu — yalnız hava aracı tespiti/angajmanı (2.5.35); videoda çift tıkla takip (2.5.34); ayrıntılı güncelleme ilerlemesi, PG havuz sızıntısı düzeltmesi (2.5.33); eski AI işçisi güncellemede yenilenir (2.5.32); ayrı Yüz tespiti, angajman kalibrasyonu (2.5.31); Yardım menüsüne 'Güncellemeleri Denetle' (2.5.30); yerel AI 'sunucu yok' hatası giderildi (2.5.29).

## Paket 2.5.28 / Uygulama 2.4.158 — 2026-09-13

**Yakın çekim insan tespiti eklendi (paket 2.5.28)**

- İnsan tespiti artık iki yolu birlikte kullanır: tam beden (yaya) tespiti KORUNDU; buna ek olarak yakın webcam/masa başı kadrajında YuNet yüz tespitiyle 'insan var' sinyali üretilir. Böylece hem uzaktaki yaya hem yakındaki kişi yakalanır.
- GİZLİLİK: Yakın çekim yolu yalnız VARLIK tespitidir — yüz TANIMA (kimlik) yapmaz; embedding/isim çıkarılmaz, dışarı taşınmaz.
- İnsan hassasiyeti bu yolu da ölçekler: yüksek hassasiyet daha küçük/daha düşük güvenli yüzleri de yakalar.
- Manuel kontrol: Kamera artık kendiliğinden açılmaz. Yalnız 'Başlat'a basınca kamera açılır ve (görevi varsa) AI izlemesi başlar; 'Durdur'da kamera ve AI birlikte durur. Açılışta/kayıtta otomatik başlatma kaldırıldı.
- Dron panelinde kamera kontrolleri (görüntü konumu + Yapay Zeka Ayarları) taşmayı önlemek için bir açılır menüye (⋯) toplandı; Ad ve Başlat görünür kalır.
- İlk dosya tabanlı güncelleme ile gelir; yeni kurulum gerekmez.

## Paket 2.5.27 / Uygulama 2.4.157 — 2026-09-13

**Kritik: AI ayarı değiştirilince oluşan çökme giderildi (paket 2.5.27)**

- KRİTİK: Bir kameranın AI ayarını (sınıf aç-kapa/hassasiyet) değiştirmek Merkez'i çökertiyordu (Windows yerel bellek bozulması, 0xC0000374). Neden: her kamera kaydında canlı yayın koşulsuz durdurulup yeniden açılıyor; webcam (cv2.VideoCapture) hızlı aç-kapada çöküyordu. Artık yayın yalnız kaynak (URL/protokol) gerçekten değiştiğinde durdurulur; AI-only değişiklikte webcam'e dokunulmaz.
- Ek koruma: aynı yerel kamera cihazının açılışı ve kapanışı tek kilitle serileştirildi; eşzamanlı aç/kapa çakışması (çökme kaynağı) engellendi.
- Bu düzeltme dosya tabanlı güncelleme servisiyle gelir; yeni kurulum .exe indirmeye gerek yoktur.

## Paket 2.5.26 / Uygulama 2.4.156 — 2026-09-13

**Dosya tabanlı arka plan güncelleme servisi (paket 2.5.26)**

- Güncellemeler artık imzasız kurulum (.exe) indirmiyor; arka planda çalışan güncelleme servisi yalnız DEĞİŞEN düz dosyaları (imzalı manifest + sha256) indirip uyguluyor. Bu, Windows Defender'ın kurulum .exe'sini yanlışlıkla karantinaya almasını (Sabsik.FL.A!ml) ve güncellemenin [Errno 22] ile bozulmasını ortadan kaldırır; güncellemeler küçük ve hızlıdır (artımlı).
- Arka plan servisi (gözetmen) uygulamayı çalıştırır, çökerse yeniden başlatır ve güncellemeyi uygular; güncelleme sırasında uygulama durdurulup dosyalar atomik yerleştirilir, hata olursa geri alınır. veri/, lisans ve loglar gibi kullanıcı dosyalarına dokunulmaz.
- Not: dosya tabanlı güncellemeye geçiş için bu sürümü bir kez elle kurmak gerekir; sonraki güncellemeler otomatik ve AV dostudur.

## Paket 2.5.25 / Uygulama 2.4.155 — 2026-09-13

**Kritik: kamera aç-kapada sunucu çökmesi giderildi (paket 2.5.25)**

- KRİTİK DÜZELTME: Kamera birkaç kez açılıp kapatıldığında (özellikle yerel AI etkinken) Merkez sunucusu 'PostgreSQL bağlantı havuzu dolu' hatasıyla çöküyordu. Her canlı MJPEG yayını, akış boyunca bir veritabanı havuz bağlantısını kilitliyordu; yerel AI işçisinin kendi kamera okuması da ana havuzdan kalıcı bir bağlantı tutuyordu. Yayın iş parçacığı artık kamera kaydını okuduktan hemen sonra bağlantıyı havuza iade eder; havuz (10) dolmaz, sunucu çökmez.
- Dron panelindeki 'Kamera Başlat' düğmesinin etiketi 'Başlat' olarak kısaltıldı.

## Paket 2.5.24 / Uygulama 2.4.154 — 2026-09-13

**Dron panelinde kamera başlat + Yapay Zeka Ayarları paneli, tek konumda görüntü (paket 2.5.24)**

- Dron paneline, drona bağlı kamera için 'Kamera Başlat/Durdur' düğmesi eklendi; kamera oynatılmıyorken tek tıkla başlatılır.
- Canlı görüntü artık aynı anda tek yerde gösterilir: harita üzerinde küçük önizleme, yüzen pencere, kameralar paneli içi veya tam ekran. Görüntü hedefi seçici (dört kip) dron panelinde, kameralar panelinde ve yüzen pencerede bulunur; başka hedef seçiliyse önizleme o konumda çizilir, ikinci bir yerde görünmez.
- Yapay Zeka Ayarları düğmesi ve açılır-kapanır (collapsible) panel eklendi: İnsan, Kara Aracı ve Hava Aracı için tanımayı ayrı ayrı açıp kapatma ve sınıf başına hassasiyet ayarı. Panel dron panelinden, kameralar panelinden ve yüzen/tam ekran görüntüden açılır.
- Sınıf başına hassasiyet uçtan uca bağlandı: ayar kameraya kaydedilir (ai_hassasiyet), yerel AI işçisine iletilir ve tespit eşiklerine uygulanır. Varsayılan 50, önceki davranışla birebir aynıdır (regresyon yok).
- Yüzen penceredeki eski satır içi AI kümesi kaldırıldı; hassasiyet çubuğu yanlışlıkla radar sınıflandırıcısına bağlıydı, artık kamera AI'sına doğru bağlanan sınıf bazlı panel kullanılır.
- GRCON (çevrimiçi Merkez) değişmedi; bu arayüz yalnız GRCOFF yerel kamera/AI yüzeyindedir.

## Paket 2.5.23 / Uygulama 2.4.153 — 2026-09-12

**GRCOFF Merkez aynı zamanda AI sunucusu: köprüsüz canlı görüntü AI (paket 2.5.23)**

- GRCOFF (offline Merkez) yerel AI işçisini kendisi başlatır ve AI yöneticisine 'GRCOFF Yerel AI' olarak kaydeder; ayrı bir AI sunucusu veya köprü gerekmez. Görevi seçili kameraların canlı görüntüsüne AI doğrudan uygulanır. 'Uygun (çevrimiçi/boş) AI sunucusu yok' hatası giderildi.
- Yerel işçi Merkez ile birlikte açılır, düşerse artan beklemeyle yeniden başlatılır. Kamera işçi hazır olmadan kaydedildiyse veya işçi yeniden başladıysa, AI görevli kameralar kendiliğinden yeniden izlemeye alınır.
- Kurulumun kaydırılmış AI portu (8910) kullanılır. İşçi canlı görüntüyü Merkez'in kendi yayın yolundan, yalnız bu makineden geçerli yerel işçi anahtarıyla okur; yayın dışarıya açılmaz İşçi yalnız 127.0.0.1 üzerinde dinler; yerel ağdan erişilemez. İşçi kayıtlarını program dizini yerine veri dizinine yazar (Windows: C:\ProgramData\Goktungu\Merkez, Linux: /var/lib/goktungu-merkez).
- Kamera formundan GRCOFF yerel işçisinde kapalı olan Kişi Tanıma ve Araç Tanıma anahtarları kaldırıldı; İnsan, Kara Aracı ve Hava Aracı tespiti etkin.
- Kurulumda örnek olarak eklenen ve hiç çalışmayan 'ASUS Ascent GX10' ile 'CPU AI Sunucusu (Yerel)' kayıtları artık eklenmez; değiştirilmemiş eski kayıtlar açılışta kaldırılır.
- GRCON (çevrimiçi Merkez) değişmedi: orada AI Görüntü Köprüsünde çalışır, yerel işçi başlatılmaz.

## Paket 2.5.22 / Uygulama 2.4.152 — 2026-09-12

**Kamera formunda AI görevleri geri geldi, form bölümlere ayrıldı (paket 2.5.22)**

- Kamera ekle/düzenle formunda kaybolan 'AI Görevleri' bölümü geri geldi: Kişi Tanıma, Araç Tanıma, Hava Aracı Tespit, İnsan Tespit, Kara Aracı Tespit. Bölüm eksik olduğu için görevler hep boş kaydediliyor ve yerel AI izlemesi hiçbir kamerada başlamıyordu; görev seçilen kamerada izleme kayıt anında otomatik başlar.
- Kamera formu açılır-kapanır bölümlere ayrıldı: Genel, AI Görevleri ve AI Angajman Kalibrasyonu. Bölüm başlıkları seçili görev sayısını ve kalibrasyon durumunu gösterir; Kaydet/İptal düğmeleri her zaman görünür kalır.
- Otomatik güncelleme artık kurulu paketin gerçek sürümünü bildirir. 2.5.20 ve 2.5.21 kendini 2.5.19 olarak tanıttığı için 'Yeni sürüm hazır' uyarısı güncelleme yapıldıktan sonra da kaybolmuyordu.

## Paket 2.5.21 / Uygulama 2.4.151 — 2026-09-12

**Yerel AI ile takip edilen hedefe dron angajman altyapısı (paket 2.5.21)**

- GRCOFF (offline Merkez) yerel AI ile takip edilen hedef, operatör onaylı angajman zincirine bağlandı: yerel kamera tespiti coğrafi konuma çözülüp mevcut hedef deposuna yazılır; hedef listesi → kuyruğa alma → onay → başlatma akışı yerel hedeflerde de çalışır.
- İki kamera tipi eklendi. 'Sabit kamera': kamera sabit bir noktadadır, hedefi AYRI bir interceptor dron angaje eder; hedef konumu kalibrasyondan (konum/yükseklik/yön/eğim/görüş açısı) çözülür. 'Drona takılı kamera': kamera bir dronun üzerindedir ve onunla hareket eder; hedef konumu dronun canlı MAVLink pozundan çözülür ve hedefi kendi dronu angaje eder.
- Mesafe kestirimi hibrit yöntemle yapılır: kara sınıfları (insan, kara aracı) sabit kamerada yer düzlemi kesişimiyle (düz zeminde ~%5-10 hata), hava aracı ve tüm drona takılı kamera hedefleri sınıf bazlı görünen boyutla (~%25-40 hata) konumlanır. Her hedef bir mesafe güven değeri taşır; kalibrasyon eksik veya konum güvenilir değilse hedef angajmana ALINMAZ.
- Kamera formuna 'Kamera Tipi' seçici ve angajman kalibrasyon alanları eklendi. Yeni/eksik kalibreli kameralar açıkça 'angajmana alınamaz' olarak işaretlenir.
- Hava aracı sınıfı düşman dron tespiti için kullanılabilir: yerel AI bir dronu 'hava_araci' olarak sınıflandırır, operatör onayıyla interceptor dron angaje olur.
- 2.5.20 pasif takip sözleşmesi (yerel NDJSON kayıt katmanı) DEĞİŞMEDEN korundu; yerel besleme kolu bu akıştan bağımsız ikinci bir tüketicidir. Angajman her durumda açık operatör onayı gerektirir.

## Paket 2.5.20 / Uygulama 2.4.150 — 2026-09-12

**GRCOFF yerel AI çalışma kipi ve Kamera paneli kapatması düzeltildi**

- GRCOFF (offline Merkez) Kamera panelinin başlıktaki X düğmesi ortak görünürlük kaydını kalıcı olarak kapatır; panel açılışta görünür kalabilir ancak kullanıcı kapattığında kendiliğinden yeniden açılmaz.
- GRCOFF, Köprü gerektirmeden aynı bilgisayarda 127.0.0.1:8900 üzerinde yerel AI işçisini başlatır. İşçi CPU ile çalışır; uygun NVIDIA ortamında GPU kipini seçer. Görüntü, tespit, yüz şablonu ve kimlik bilgisi haricî sunucuya veya Köprüye taşınmaz.
- Offline paket AI modellerini içerir ve ilk kurulumdan sonra internet bağlantısı gerektirmeden yerel çalışma için hazırlanır. AI işçisi Merkez kapanırken düzenli biçimde durdurulur ve yinelenen başlatmalarda sağlık uç noktasından doğrulanır.
- GRCON çevrimiçi sunucuda bu yerel AI işçisi başlatılmaz; çevrimiçi mimari ile GRCOFF yerel işleme ayrımı korunur.
