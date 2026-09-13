// GOKTUNGU merkezi surum tanimi - her teslim paketinde artirilir.
// Kullanim: Yardim > Program Hakkinda popup'inda gosterilir (menubar.js).
// v2.1.8: GCS_SURUM_GECMISI eklendi - surum numarasina tiklaninca acilan
// "Surum Gecmisi" popup'inda listelenir (js/surum_gecmisi.js).
const GCS_SURUM = "2.4.153";
const GCS_SURUM_TARIH = "2026-09-12";

// Surum gecmisi: en yeni en ustte. s=surum, t=tarih, d=degisiklikler.
const GCS_SURUM_GECMISI = [
  {
    surum: "2.4.153",
    tarih: "2026-09-12",
    baslik: "GRCOFF Merkez aynı zamanda AI sunucusu: köprüsüz canlı görüntü AI (paket 2.5.23)",
    maddeler: [
      "GRCOFF (offline Merkez) yerel AI işçisini kendisi başlatır ve AI yöneticisine 'GRCOFF Yerel AI' olarak kaydeder; ayrı bir AI sunucusu veya köprü gerekmez. Görevi seçili kameraların canlı görüntüsüne AI doğrudan uygulanır. 'Uygun (çevrimiçi/boş) AI sunucusu yok' hatası giderildi.",
      "Yerel işçi Merkez ile birlikte açılır, düşerse artan beklemeyle yeniden başlatılır. Kamera işçi hazır olmadan kaydedildiyse veya işçi yeniden başladıysa, AI görevli kameralar kendiliğinden yeniden izlemeye alınır.",
      "Kurulumun kaydırılmış AI portu (8910) kullanılır. İşçi canlı görüntüyü Merkez'in kendi yayın yolundan, yalnız bu makineden geçerli yerel işçi anahtarıyla okur; yayın dışarıya açılmaz İşçi yalnız 127.0.0.1 üzerinde dinler; yerel ağdan erişilemez. İşçi kayıtlarını program dizini yerine veri dizinine yazar (Windows: C:\\ProgramData\\Goktungu\\Merkez, Linux: /var/lib/goktungu-merkez).",
      "Kamera formundan GRCOFF yerel işçisinde kapalı olan Kişi Tanıma ve Araç Tanıma anahtarları kaldırıldı; İnsan, Kara Aracı ve Hava Aracı tespiti etkin.",
      "Kurulumda örnek olarak eklenen ve hiç çalışmayan 'ASUS Ascent GX10' ile 'CPU AI Sunucusu (Yerel)' kayıtları artık eklenmez; değiştirilmemiş eski kayıtlar açılışta kaldırılır.",
      "GRCON (çevrimiçi Merkez) değişmedi: orada AI Görüntü Köprüsünde çalışır, yerel işçi başlatılmaz."
    ]
  },
  {
    surum: "2.4.152",
    tarih: "2026-09-12",
    baslik: "Kamera formunda AI görevleri geri geldi, form bölümlere ayrıldı (paket 2.5.22)",
    maddeler: [
      "Kamera ekle/düzenle formunda kaybolan 'AI Görevleri' bölümü geri geldi: Kişi Tanıma, Araç Tanıma, Hava Aracı Tespit, İnsan Tespit, Kara Aracı Tespit. Bölüm eksik olduğu için görevler hep boş kaydediliyor ve yerel AI izlemesi hiçbir kamerada başlamıyordu; görev seçilen kamerada izleme kayıt anında otomatik başlar.",
      "Kamera formu açılır-kapanır bölümlere ayrıldı: Genel, AI Görevleri ve AI Angajman Kalibrasyonu. Bölüm başlıkları seçili görev sayısını ve kalibrasyon durumunu gösterir; Kaydet/İptal düğmeleri her zaman görünür kalır.",
      "Otomatik güncelleme artık kurulu paketin gerçek sürümünü bildirir. 2.5.20 ve 2.5.21 kendini 2.5.19 olarak tanıttığı için 'Yeni sürüm hazır' uyarısı güncelleme yapıldıktan sonra da kaybolmuyordu."
    ]
  },
  {
    surum: "2.4.151",
    tarih: "2026-09-12",
    baslik: "Yerel AI ile takip edilen hedefe dron angajman altyapısı (paket 2.5.21)",
    maddeler: [
      "GRCOFF (offline Merkez) yerel AI ile takip edilen hedef, operatör onaylı angajman zincirine bağlandı: yerel kamera tespiti coğrafi konuma çözülüp mevcut hedef deposuna yazılır; hedef listesi → kuyruğa alma → onay → başlatma akışı yerel hedeflerde de çalışır.",
      "İki kamera tipi eklendi. 'Sabit kamera': kamera sabit bir noktadadır, hedefi AYRI bir interceptor dron angaje eder; hedef konumu kalibrasyondan (konum/yükseklik/yön/eğim/görüş açısı) çözülür. 'Drona takılı kamera': kamera bir dronun üzerindedir ve onunla hareket eder; hedef konumu dronun canlı MAVLink pozundan çözülür ve hedefi kendi dronu angaje eder.",
      "Mesafe kestirimi hibrit yöntemle yapılır: kara sınıfları (insan, kara aracı) sabit kamerada yer düzlemi kesişimiyle (düz zeminde ~%5-10 hata), hava aracı ve tüm drona takılı kamera hedefleri sınıf bazlı görünen boyutla (~%25-40 hata) konumlanır. Her hedef bir mesafe güven değeri taşır; kalibrasyon eksik veya konum güvenilir değilse hedef angajmana ALINMAZ.",
      "Kamera formuna 'Kamera Tipi' seçici ve angajman kalibrasyon alanları eklendi. Yeni/eksik kalibreli kameralar açıkça 'angajmana alınamaz' olarak işaretlenir.",
      "Hava aracı sınıfı düşman dron tespiti için kullanılabilir: yerel AI bir dronu 'hava_araci' olarak sınıflandırır, operatör onayıyla interceptor dron angaje olur.",
      "2.5.20 pasif takip sözleşmesi (yerel NDJSON kayıt katmanı) DEĞİŞMEDEN korundu; yerel besleme kolu bu akıştan bağımsız ikinci bir tüketicidir. Angajman her durumda açık operatör onayı gerektirir."
    ]
  },
  {
    surum: "2.4.150",
    tarih: "2026-09-12",
    baslik: "GRCOFF yerel AI çalışma kipi ve Kamera paneli kapatması düzeltildi",
    maddeler: [
      "GRCOFF (offline Merkez) Kamera panelinin başlıktaki X düğmesi ortak görünürlük kaydını kalıcı olarak kapatır; panel açılışta görünür kalabilir ancak kullanıcı kapattığında kendiliğinden yeniden açılmaz.",
      "GRCOFF, Köprü gerektirmeden aynı bilgisayarda 127.0.0.1:8900 üzerinde yerel AI işçisini başlatır. İşçi CPU ile çalışır; uygun NVIDIA ortamında GPU kipini seçer. Görüntü, tespit, yüz şablonu ve kimlik bilgisi haricî sunucuya veya Köprüye taşınmaz.",
      "Offline paket AI modellerini içerir ve ilk kurulumdan sonra internet bağlantısı gerektirmeden yerel çalışma için hazırlanır. AI işçisi Merkez kapanırken düzenli biçimde durdurulur ve yinelenen başlatmalarda sağlık uç noktasından doğrulanır.",
      "GRCON çevrimiçi sunucuda bu yerel AI işçisi başlatılmaz; çevrimiçi mimari ile GRCOFF yerel işleme ayrımı korunur."
    ]
  },
  {
    surum: "2.4.149",
    tarih: "2026-09-11",
    baslik: "M50 elektro-optik desteği ve offline Merkez canlı kamera yönetimi eklendi",
    maddeler: [
      "M50 kontrolü yalnız Windows x64 saha Köprüsünde, operatörün açıkça girdiği bağlantı bilgileriyle etkinleşir. Merkez fiziksel M50 oturumu açmaz; yalnız yetkili Köprü durumunu ve güvenli komutları vekil eder.",
      "M50 hedef takibi yalnız operatörün manuel olarak seçtiği dikdörtgen ile başlatılır. Otomatik hedef seçimi, silah, atış, angajman ve hedefe göre kendiliğinden hareket komutları bulunmaz.",
      "Offline Merkezde Köprü zorunluluğu olmadan yerel kamera ekleme, düzenleme ve silme yeniden kullanılabilir hale getirildi. Önizleme ve Video Duvarı, saniyede bir anlık kare yerine uygulamanın aynı-origin canlı MJPEG hattını kullanır.",
      "Kamera akışı yerel Merkez kurulumunda kalır. RTSP adreslerinde gömülü kullanıcı, parola ve oturum parametreleri reddedilir; M50 ve kamera durum paketleri kimlik bilgisi içermez."
    ]
  },
  {
    surum: "2.4.148",
    tarih: "2026-09-11",
    baslik: "İmzalı uygulama içi güncelleme ve eski sürüm uyarısı eklendi",
    maddeler: [
      "Merkez, açılıştan sonra arka planda sabit HTTPS katalog adresindeki imzalı sürüm manifestini denetler; kontrol uçuş, telemetri ve bağlantı akışlarını bekletmez.",
      "Yeni uygun sürüm bulunduğunda üstte görünür kırmızı bir şerit gösterilir. Şeride tıklanınca sürüm notları ve indirme ilerlemesini gösteren güncelleme penceresi açılır.",
      "Paket yalnız geçerli yerel lisansla yetkilendirilmiş uçtan alınır; ürün, platform, Ed25519 imzası ve SHA-256 özeti doğrulanmadan kurulum dosyası çalıştırılamaz.",
      "Kurulum kullanıcı onayıyla ayrı süreçte başlatılır. Windows yönetici iznini yalnız işletim sistemi kurulum aşamasında ister; Linux paket yöneticisi yetkisi yalnız kurulum aşamasındadır. Yerel ayar ve lisans dosyaları korunur."
    ]
  },
  {
    surum: "2.4.147",
    tarih: "2026-09-08",
    baslik: "Yalnız sanal sabit kanat için parametreli SITL dalış senaryosu eklendi",
    maddeler: [
      "Görev başlatılırken yalnız çevrimiçi sanal sabit kanatta dalış simülasyonu seçilebilir. Gerçek araçlar, başka araç tipleri ve sanal olmayan bağlantılar bu seçeneği görmez.",
      "Backend, kullanıcı arayüzü bilgisini yeterli saymaz: sysid’nin çalışan SITL süreciyle eşleştiğini, SITL tipinin sabit kanat olduğunu ve canlı telemetrinin MAV_TYPE_FIXED_WING bildirdiğini birlikte doğrular.",
      "Senaryo, doğrudan pitch, servo, gaz veya emniyet parametresi yazmaz; onaylanan açı, hız ve irtifadan hesaplanan yaklaşma/çıkış waypoint’leri ile hedef hız profilini yalnız ArduPlane SITL görev listesine uygular.",
      "Dalış açısı 10–35°, hedef hız 10–25 m/s, başlangıç irtifası 40–120 m ve çıkış irtifası 15–80 m aralığında doğrulanır; çıkıştan en az 20 m yüksek başlangıç irtifası zorunludur.",
      "İrtifa, yer/hava hızı, dikey hız, pitch, roll, batarya, görev sırası ve uçuş modu 1 Hz kaydedilir. Her örneğe hedef parametreler ve yaklaşma/dalış/çıkış aşaması eklenir; iptal, tamamlanma veya telemetri kesilmesinde JSON kaydı atomik kapatılır."
    ]
  },
  {
    surum: "2.4.146",
    tarih: "2026-09-08",
    baslik: "Sabit kanat terminal yaklaşım performans analizi eklendi",
    maddeler: [
      "Sabit kanatta görev başlatılırken operatör, önceden planlanmış terminal yaklaşımı gerçek telemetriyle analiz etmek üzere isteğe bağlı performans profili seçebilir.",
      "Profil, yalnız seçilen açı ve hedef hızla ilişkilendirilmiş bir analiz kaydı üretir; MAVLink üzerinden gaz, pitch, hız, uçuş modu veya emniyet parametresi yazmaz.",
      "Açı -25 ile -5 derece, hedef hız 8 ile 30 m/s aralığında doğrulanır. Profil sabit kanat dışındaki araçlarda reddedilir.",
      "İrtifa, yer/ hava hızı, dikey hız, pitch, roll, batarya gerilimi, görev sırası ve uçuş modu 1 Hz örneklenir; görev tamamlandığında, iptal edildiğinde veya telemetri kesildiğinde atomik JSON kaydı kapanır."
    ]
  },
  {
    surum: "2.4.145",
    tarih: "2026-09-08",
    baslik: "Merkez kararlılığı, batarya voltaj kalibrasyonu ve bakım kapatması güçlendirildi",
    maddeler: [
      "Takeoff isteği tekilleştirilir; GUIDED/ARM durum teyitleri tamamlanmadan kalkış komutu gönderilmez. İlk komutun kaybı kullanıcıyı tekrar denemeye zorlamaz.",
      "Görev aktarımında MISSION_COUNT, REQUEST veya ACK akışı kesilirse aynı görev listesi sınırlı ve izlenebilir biçimde yeniden başlatılır.",
      "Angajman güncelleme hızı sunucu ve iş parçacığında saniyede 1–4 aralığına sıkıştırılır; telemetri beklerken ortak bağlantı kilidi tutulmaz.",
      "İlk Ayar penceresine multimetre gerilimiyle BATT_VOLT_MULT hesaplama eklendi. Araç DISARM durumda olmalı; canlı telemetri yoksa veya fark %30'u aşarsa değer yazılmaz.",
      "Barometre dahil tüm kalibrasyon pencereleri başlıktaki X, görünür Kapat düğmesi veya Escape ile kapanır; pencere kapanınca zamanlayıcılar temizlenir."
    ]
  },
  {
    surum: "2.4.144",
    tarih: "2026-09-08",
    baslik: "Kalibrasyon pencereleri ve Köprü bağlantı başlangıcı düzeltildi",
    maddeler: [
      "Kalibrasyon seçimi ile gyro, barometre, ivmeölçer, seviye, pusula, RC ve ESC pencereleri artık ekran ortasında erişilebilir boyutta açılır; genişlik en çok 560 px başlangıç hedefiyle, uygun ekranlarda en az 500×400 px korunur.",
      "Tüm kalibrasyon pencerelerine sağ-alt yeniden boyutlandırma tutamacı eklendi. Boyut ve konum, her kalibrasyon türü ve dron için ayrı saklanır; küçük ekranlarda pencere görünür alanı aşmaz.",
      "Başlıktaki X düğmesi gerçek düğme türünde, dokunmatik sürüklemeden ayrık ve güvenilir kapatma davranışındadır. Kapatıldığında ilgili kalibrasyon mesaj akışı zamanlayıcısı derhal temizlenir.",
      "Seri veya Köprü üzerinden bağlantı başlatılırken tanımsız yardımcı çağrısı düzeltildi. Bu değişiklik, RFD900 otomatik MAVLink/MSP algılama sırasını ve Betaflight salt-okunur sınırını değiştirmez."
    ]
  },
  {
    surum: "2.4.143",
    tarih: "2026-09-08",
    baslik: "RFD900 seri bağlantılarında MAVLink/MSP otomatik algılama eklendi",
    maddeler: [
      "Yeni seri/RFD900 bağlantıları varsayılan olarak önce geçerli CRC'li MAVLink HEARTBEAT dinler; kanıt yoksa yalnız Betaflight MSP API_VERSION salt-okunur sorgusunu gönderir.",
      "Algılama tek seri port sahibiyle çalışır: port kapatıldıktan sonra yalnız saptanan ArduPilot MAVLink veya Betaflight salt-okunur MSP oturumuna devredilir.",
      "Geçerli iki kanıt da alınamazsa bağlantı kapalı hata verir; rastgele seri gürültüsü, geçersiz CRC veya başka MAVLink mesajları ArduPilot kanıtı sayılmaz.",
      "Mevcut bağlantıların seçimi korunur. Otomatik algılama yalnız seri/RFD900 taşımasında kullanılabilir; DJI, TCP, UDP, sanal ve Merkez akışları değişmez."
    ]
  },
  {
    surum: "2.4.142",
    tarih: "2026-09-08",
    baslik: "ArduPilot ve Betaflight bağlantı seçimi güvenli biçimde ayrıldı",
    maddeler: [
      "DJI dışındaki bağlantı kayıtlarında uçuş yazılımı açıkça seçilir; mevcut kayıtlar geriye uyum için ArduPilot (MAVLink) kabul edilir ve DJI akışı değişmez.",
      "Betaflight ilk sürümde yalnız seri/VCP üzerinden MSP v1 salt-okunur tanılama oturumu açar; yapılandırma yazma, ARM, motor, RC, yeniden başlatma, kalibrasyon ve CLI komutları tanımlı değildir.",
      "Betaflight verisi MAVLink'e çevrilmez ve uçuş komut hattına girmez. TCP, UDP, sanal ve Merkez taşıma türlerinde Betaflight sunucuda kapalı olarak reddedilir.",
      "Yerel Merkez ile yetkili Köprü oturumları aynı sınırlı durum sözleşmesini kullanır; yalnız desteklenen tanı özetleri bağlantı kartında görünür."
    ]
  },
  {
    surum: "2.4.141",
    tarih: "2026-09-07",
    baslik: "Yerel Merkez–Köprü giriş ve kurulum kaydı uyumluluğu tamamlandı",
    maddeler: [
      "Kapalı devre Merkez, Köprü 1.7.9'un beklediği /api/istemci/giris ve /api/istemci/sunucu_kayit uçlarını yerel kullanıcı doğrulamasıyla sunar.",
      "Sunucu kayıtları ürün türüne göre ayrılır; Dron, Görüntü, Radar, GCCDUAL ve DJI köprüleri aynı makinede birbirinin kimliğini ezmez.",
      "Köprü gizli anahtarı yalnız ilk kayıt veya yönetici onaylı yenilemede bir kez döner; veritabanında yalnız SHA-256 özeti saklanır.",
      "Parola denemeleri kaba kuvvet sınırına tabidir; bulut App kipinde yerel uyumluluk uçları kapalı kalır."
    ]
  },
  {
    surum: "2.4.140",
    tarih: "2026-08-31",
    baslik: "Görüntü angajmanı hedef–dron zaman eşlemesi güvenli biçimde düzeltildi",
    maddeler: [
      "Görüntü Köprüsü ve App farklı duvar saatleri kullansa bile hedef ölçüm zamanı, köprü paketindeki göreli yaş korunarak App alım saatine taşınır.",
      "Eksik, gelecekten veya izin verilen pencereden eski ölçüm ve seçim zamanları sıfırlanır; mevcut tazelik ve telemetri güvenlik kapıları kapalı biçimde reddetmeye devam eder.",
      "Canlı #41 köprüsünde ölçülen yaklaşık 3,6 saniyelik saat farkının 3 saniyelik kare–poz eşiğinde yanlış ret üretmesi giderildi; eşik yükseltilmedi.",
      "Normalleştirilmiş seçim zamanı paketler arasında değişse bile aynı firma, köprü, kamera ve iz 15 saniyede yalnız bir angajman adayı üretir."
    ]
  },
  {
    surum: "2.4.139",
    tarih: "2026-08-31",
    baslik: "Ana alan adı /app dağıtımında kamera karesi URL yolu düzeltildi",
    maddeler: [
      "Küçük JPEG URL'si app.goktungu.com kök dağıtımı ile goktungu.com/app alt-yol dağıtımında ayrı ve doğru App API köküne bağlanır.",
      "goktungu.com/app oturumlarında görüntü isteğinin yanlışlıkla ana sitenin /api yoluna giderek 404 dönmesi engellendi.",
      "Kamera URL'si yalnız mevcut sayfanın kendi origin'i içinde kabul edilir; harici kaynağa yönelen değerler kapalı biçimde reddedilir.",
      "Aynı URL çözücü harita küçük karesi ve uçuş geçmişi karesinde ortak kullanılır."
    ]
  },
  {
    surum: "2.4.138",
    tarih: "2026-08-31",
    baslik: "Dron haritası güvenli küçük-kare istemci zinciri sağlamlaştırıldı",
    maddeler: [
      "WebSocket yönlendiricisinin önbellek anahtarı güncel sürüme yükseltildi; tarayıcının eski küçük-kare işleyicisini kullanması engellendi.",
      "Kamera karesi yalnız aynı donanımsal UID'yi taşıyan canlı telemetri dronuna bağlanır; kalıcı veritabanı ID'si ile ilgisiz istemci ID alanları artık karşılaştırılmaz.",
      "Başlangıç ve canlı küçük-kare WebSocket zarfları tek güvenli nesne doğrulamasıyla işlenir; UID eksikliği, UID çelişkisi ve birden fazla aday kapalı biçimde reddedilir.",
      "Askıda kalan JPEG isteği sonraki 1 FPS kareleri süresiz engellemez; süreli serbest bırakma sonrasında yalnız en yeni bekleyen kare denenir."
    ]
  },
  {
    surum: "2.4.137",
    tarih: "2026-08-24",
    baslik: "Görüntü Hedefleri kapanışı, küçük kare akışı ve sürüm geçmişi düzeltildi",
    maddeler: [
      "Görüntü Hedefleri panelinin kimlik seçicili display kuralı genel gizleme sınıfını ezmiyor; kapatma düğmesi paneli kesin olarak kapatıyor.",
      "1 FPS akışta yavaş JPEG yüklemeleri birbirini sürekli geçersiz kılmıyor; dron başına tek yükleme yürütülüp yalnız en yeni kare bekletilerek saydam billboard açlığı önleniyor.",
      "Sürüm Geçmişi hem eski kompakt hem yeni açıklayıcı kayıt alanlarını birlikte okuyarak vundefined ve undefined tarihlerini ortadan kaldırıyor."
    ]
  },
  {
    surum: "2.4.136",
    tarih: "2026-08-24",
    baslik: "Harita küçük karesi canlı eşleme dayanıklılığı güçlendirildi",
    maddeler: [
      "Canlı 1 FPS küçük kare paketi, firma kapsamındaki kalıcı dron kaydından doğrulanan SYSID'yi de taşır; başlangıç son-kare yanıtı ağ yarışında kaçsa bile canlı akış kendi başına eşlenebilir.",
      "İstemci, paket SYSID'sini o anda aynı SYSID'den gelen telemetrinin UID/ID'siyle yeniden doğrular; çelişki veya birden fazla aday varsa hiçbir kare yanlış drona bağlanmaz.",
      "Normal video, ham kamera, yüz adı/embedding ve tespit çerçevesi Merkez'e taşınmaz; 1 FPS, firma kapsamı, kısa ömürlü imzalı URL ve tazelik kapıları değişmeden korunur."
    ]
  },

  {
    surum: "2.4.135",
    tarih: "2026-08-23",
    baslik: "Görüntü Hedefleri paneli ve harita küçük kare görünürlüğü düzeltildi",
    maddeler: [
      "Görüntü Hedefleri paneli ekranı kaplayan veya ekran dışında kalan kayıtlı geometriden kurtarılır; görünür alan içinde sınırlanıp gerektiğinde yeniden merkezlenir.",
      "Harita küçük karesi tazelik kararını kamera bilgisayarının saatine göre değil güvenilir Merkez alım zamanına göre verir; saat farkı görüntüyü yanlışlıkla gizlemez.",
      "Küçük JPEG ilk yüklemede başarısız olursa aynı kare yeniden denenebilir; eski veya çevrimdışı akış görüntüsü taze gibi gösterilmez."
    ]
  },

  {
    surum: "2.4.134",
    tarih: "2026-08-23",
    baslik: "Görüntü Köprüsü–dron eşlemesi ve güvenli angajman kipleri tamamlandı",
    maddeler: [
      "Dron düzenleme penceresinde çevrimiçi Görüntü Köprüsü kamera listesi doğru açılır; İptal/Kaydet işlemleri sabit alt çubukta kalır.",
      "Yalnız açıkça izin verilmiş dron kamerasının en fazla 1 FPS küçük karesi, kesin UID/SYSID eşleşmesi ve tazelik sınırıyla harita işaretçisi yanında ve uçuş geçmişinde gösterilir.",
      "Telemetri ile Angajman ve Görüntü ile Angajman ayrı kipler olarak korunur; yönetici, açık insan onayı, firma, taze telemetri ve aynı icra dronunda çakışma engeli sunucuda yeniden doğrulanır."
    ]
  },

  {
    surum: "2.4.133",
    tarih: "2026-08-23",
    baslik: "Görüntü geçmişi ve çalışma durumu izinleri kalıcılaştırıldı",
    maddeler: [
      "Görüntü geçmişi kökü App her başladığında systemd ön kapısıyla 0700 ve goktungu:goktungu durumuna getirilir; mevcut görüntü dosyaları silinmez.",
      "calisma.json çalışma durumu dosyası eski ve yeni kurulumlarda desteklenen veri-alt-yolu sözleşmesine geçirildi; App kökünde calisma.json.yeni izin hatası giderildi.",
      "Eski 22:25:33 görüntü geçmişi hata satırı kanıt yedeğinde korunup aktif log temiz başlatıldı; gerçek servis hesabıyla yazma, silme ve zorunlu bakım doğrulandı."
    ]
  },

  {
    surum: "2.4.132",
    tarih: "2026-08-22",
    baslik: "Dron adı kaydı ve düzenleme penceresi tamamlandı",
    maddeler: [
      "PostgreSQL çatışma sözlüğü, dönüştürücünün gerçekten okuduğu dron_kayitlari SQL tablo adıyla eşleştirildi.",
      "Dron adı yazımı ON CONFLICT (uid) DO UPDATE biçimine çevrilerek aynı donanımsal UID için kalıcı güncelleme yapar.",
      "Dronu Düzenle penceresi ortak yeniden boyutlandırma altyapısına bağlandı; boyut ve konum tarayıcıda korunur."
    ]
  },

  {
    surum: "2.4.131",
    tarih: "2026-08-22",
    baslik: "Dron adı PostgreSQL çatışma eşlemesi hazırlandı",
    maddeler: [
      "PostgreSQL uyumluluk katmanına dron adı kaydı için uid çatışma anahtarı eklendi.",
      "İlk eşlemenin fiziksel tablo takma adına yazıldığı ve çalışan SQL'in özgün tablo adını kullandığı canlı komutla ölçüldü; eşleme 2.4.132'de tamamlandı.",
      "Bilinmeyen tablolarda sessiz geçiş yasağı korundu; hata açıkça günlüğe yazılarak veri kaybı gizlenmedi."
    ]
  },

  {
    surum: "2.4.130",
    tarih: "2026-08-22",
    baslik: "Yerel Görüntü Köprüsü güvenli angajman merkezi oldu",
    maddeler: [
      "Görüntü Köprüsü ilk açılışta Merkez/Lokal kipini ve yönetici hesabını kurar; panel, API ve MJPEG uçları oturum, CSRF ve kaba kuvvet sınırlamasıyla korunur.",
      "Video duvarı 1/2/3/5/6 kamera düzenlerini, gerçek tam ekranı ve ESC çıkışını destekler. Beş ve altı kamerada bağlantı açlığını önleyen hibrit akış kullanılır.",
      "YuNet ve SFace tabanlı yüz kütüphanesi yalnız yerel bilgisayarda çalışır. Yüz görseli saklanmaz; embedding AES-256-GCM ile şifrelenir ve kimlik sonucu merkeze taşınmaz.",
      "Merkez yalnız kamera kimliği, adı ve güvenli kaynak meta verisini alır; kamera URL'si, normal video, yüz adı veya biyometrik veri merkez kanalına girmez.",
      "Drona bağlı kamera için yönetici açıkça izin verirse en çok 1 FPS küçük JPEG geçmiş önizlemesi saklanır; dosya deposu, kota, saklama süresi, firma izolasyonu ve kısa ömürlü imzalı URL uygulanır.",
      "Tam ekranda operatörün seçtiği tespit yerel iz olarak kilitlenir. App yalnız taze ve aynı firma kapsamındaki seçili iz metadata'sından angajman adayı üretir; işlem, yönetici açıkça Angajmanı Başlat demeden başlamaz.",
      "İcra dronu her görüntü angajmanında zorunludur. Kamera drona bağlıysa kaynak dron yalnız ön seçilir ve sunucuda UID eşleşmesi doğrulanır; bağlı değilse firma kapsamındaki canlı dron seçilmeden başlatma kapalıdır."
    ]
  },

  {
    surum: "2.4.129",
    tarih: "2026-08-22",
    baslik: "Açılış ayar paketi yüzde 97,74 daraltıldı",
    maddeler: [
      "WebSocket açılışındaki gömülü firma logosu kaldırıldı. Logo artık sürümlü ve ETag destekli HTTP ucundan yalnız gerektiğinde yüklenir.",
      "Canlı ölçümde ayarlar paketi 87.061 bayttan 1.971 bayta indi; açılış yükü yüzde 97,74 azaldı.",
      "Şirket kayıtlarının sunucu audit alanları veritabanında korunur ancak arayüzün açılış paketine gönderilmez.",
      "Şirket ayarları, uçuş grafiği ve uçuş raporu logo tüketicileri yeni logo_url/logo_var sözleşmesine geçirildi.",
      "Logo ucu yalnız doğrulanmış PNG, JPEG ve WebP içeriğini en fazla 512 KiB boyutla sunar; güçlü SHA-256 ETag, GET ve HEAD koşullu önbelleği destekler."
    ]
  },

  {
    surum: "2.4.128",
    tarih: "2026-08-22",
    baslik: "Sabit ve dron kameraları güvenli angajmana bağlandı",
    maddeler: [
      "Kamera kaynağı olarak manuel konum, kayıtlı lokasyon veya kayıtlı dron seçilebilir; kayıtlı lokasyon sabit kamera, kayıtlı dron hareketli kamera olarak işlenir.",
      "Dron kamerası hedef konumu yalnız seçilen dronun taze GPS ve yönelim telemetrisiyle çözülür. Eksik veya bayat telemetri, geçersiz koordinat ve desteklenmeyen gimbal kaynağı angajmanı açık gerekçeyle kilitler.",
      "Görüntü ve video merkeze taşınmaz. Yalnız hedef kimliği, sınıf, güven, göreli açı, mesafe ve ölçüm zamanı gibi sınırlı sayısal meta veri gönderilir.",
      "Bulut Görüntü Köprüsü hedeflerinin App hedef deposuna aktarılmaması giderildi; kaynak snapshotları ve hedefler doğrulanmış firma ile kurulum oturumuna bağlandı.",
      "Lokasyonlar, dron kaynakları, görüntü hedefleri ve angajman kuyruğu firma kapsamında yalıtıldı. İstemcinin gönderdiği firma kimliği güvenilir kabul edilmez."
    ]
  },

  {
    surum: "2.4.127",
    tarih: "2026-08-22",
    baslik: "Bosta telemetri trafigi kisildi",
    maddeler: [
      "Telemetri paketi degismediyse artik gonderilmiyor. Bosta " +
        "30 saniyelik trafik 866 KB'den 11.3 KB'ye dustu (%98.7 " +
        "azalma); saatlik yuk ~104 MB yerine ~1.4 MB.",
      "Mesajlari yavas tuketen istemcilerin 45. saniyede sessizce " +
        "kopmasina yol acan kusur giderildi. Kopma kodu 1006 idi ve " +
        "gunluge hicbir kayit dusmuyordu.",
      "Baglanti canliligi icin en gec 10 saniyede bir paket " +
        "gonderilmeye devam ediyor; NAT ve LTE ara kutulari sessiz " +
        "oturumlari toplamaz.",
      "Yeni baglanan istemci her durumda tam telemetri paketi alir " +
        "(olculen gecikme 0.15 sn)."
    ]
  },

  { s: "2.4.126", t: "2026-08-21",
    b: "Goruntu hedefleri angajman motoruna baglandi [FAZ20-IS93]",
    m: [
      "TALEP (kullanici): 'benim sonunda tek amacim goruntu isleme ile angajman yapmak' ve 'merkezi app ile yerel goruntu islemeyi birlestirip angajman yapabilecekmiyiz'. Bu surum o baglantiyi kurar.",
      "MIMARI: Goruntu Koprusu 1.1.0 kamerasi kalibre edilince (enlem, boylam, kurulum yuksekligi, pan, tilt, gorus acisi) merkez hedefin YERYUZU KOORDINATINI cozer ve hedef mevcut angajman motoruna 'goruntu' tipiyle girer. Goruntu HALA merkeze gitmez; pakete eklenen alanlarin tamami sayidir.",
      "YENI PANEL: AI > Goruntu Hedefleri. Kamera basina gruplu hedef listesi, oncelige gore sirali. Kalibre kamera yesil rozet, kalibre olmayan sari rozet alir.",
      "KALIBRE DEGILSE ANGAJMAN KILITLI: dugme GIZLENMEZ, sonuklastirilir ve merkezden gelen gerekce baslik olarak gosterilir. Gizlenseydi operator dugmenin neden olmadigini anlayamazdi.",
      "OLU DAL SILINDI (kritik): angajman.py'deki 'ai_takip' hedef tipi hedef konumu olarak KAMERANIN konumunu donduruyordu -- saldiran dron hedefe degil kameranin diregine ucardi. Ustelik Is 71 sokumu sonrasi zaten calismiyordu: AIYonetici.son_takip_konum artik yok, __getattr__ None donduruyor, uc parcaya ayirma TypeError veriyor ve bir alt satirdaki 'except Exception: pass' hatayi yutuyordu. Yani angajman baslatiliyor, operatore duyuru gidiyor ama hedef konumu HIC cozulmuyordu. Dal tamamen kaldirildi.",
      "DUYURU KUSURU DUZELTILDI (Is 93 disi, onceden vardi): sunucu.py angajman.baslat() cagrisindan sonra KOSULSUZ 'aktif: true' duyuruyordu. baslat() deger dondurmedigi icin ret durumunda da (ornegin 'dron zaten angajmanda') operator ekranda angajmanin BASLADIGINI goruyordu. baslat() artik (basladi_mi, gerekce) donduruyor ve duyuru bu donuse bagli.",
      "CIFT PAN UYGULAMASI ONLENDI: Kalibrasyon.aci() zaten 'az + pan' donduruyor, yani gelen azimut MUTLAK. Merkezde bir kez daha eklenseydi kayma iki kez uygulanirdi. OLCULDU: pan=120 ile hedef goruntu merkezindeyken cozulen azimut 120.00 (cift uygulamada 240 olur, hedef 173 m yanlis yerde gorunurdu).",
      "KONUM COZUMU OLCUMU: dort ana yon 100 m'de sapma 0.00 m; 30 derece asagi egimde 100 m egik mesafenin yatay izdusumu 86.61 m (beklenen 86.60).",
      "HEDEF KIMLIGI BILESIK (ornek_id:kamera:iz): iz numaralari kamera basina uretilir ve her koprude bastan baslar. Yalniz iz tasinsaydi iki ayri koprunun 7 numarali izleri ayirt edilemez, dron YANLIS hedefe yonlendirilebilirdi.",
      "MESAFE GUVEN PAYIYLA GOSTERILIR ('212 m +/-58%'): mesafe pinhole modelinden turetilen bir TAHMIN ve guveni dusuk. Ciplak sayi operatore kesin olcum izlenimi verirdi.",
      "HIZ VEKTORU SIFIR: kopru acisal hiz olcer; m/s'ye cevirmek tahmini mesafeye bolmeyi gerektirir ve tahminden turetilen hizla ongoru yapmak ongorunun kendisini guvenilmez kilar. Kesisme cozucusu ongoru yapmaz, dron hedefin anlik konumuna surulur. Yavas hedefte yeterli; hizli hedefte radar izi kullanilmali.",
      "INDIRME BAGLANTISI DINAMIKLESTIRILDI: goruntu_koprusu.js surumu SABIT yaziyordu ('video/1.0.0/'), 1.1.0 yayinlandiginda kullanici SESSIZCE eski paketi indirirdi. Artik /api/genel/guncelleme ucundan okunuyor -- kurumsal panelin zaten kullandigi ilke. Dugme altinda surum ve boyut etiketi gosteriliyor. Ag kesintisinde son bilinen surum yedek olarak kalir.",
      "WS YANIT DALI EKLENDI: sunucu 'hedef_sonuc' tipiyle yanit veriyordu ama ws.js'te bu tip icin dal YOKTU -- Is 91/92'de kurulan hedef/angajman kuyrugu altyapisi arayuze hic baglanmamisti, komut gonderilse yanit sessizce duserdi.",
      "SINAVLAR: sema gocu 39/39, kalibrasyon zinciri 36/36, konum cozumu 40/40, angajman motoru 41/41, app arayuzu 57/57, indirme 40/40 -- toplam 253/253. Linux kurulum 34/34, Windows paket butunlugu 47/47, yayin 27/27.",
      "GORSEL DENETIM: gece kipi, gunduz kipi ve bos durum ayri ayri denetlendi. Tum renkler CSS degiskeninden; sabit renk yok. Header basligi panel adindan farkli, ikonsuz, koyu font degil.",
    ],
  },
  { s: "2.4.125", t: "2026-08-21",
    b: "Goruntu Koprusu: AI menusune yerel kamera+AI koprusu girisi [FAZ20-IS1]",
    m: [
      "TALEP (kullanici): 'Goruntu bolumunu lokalde calisacak sekilde calistiracagiz. Ayri bir kopru yazilimi olacak. Goruntu merkeze hic gitmeyecek. Icinde ayni zamanda AI olacak. Merkez yazilimin icinde AI menusunun altinda gorunecek.'",
      "YENI URUN: Goruntu Koprusu 1.0.0 yayinlandi (Linux .deb 3.58 MB, Windows .exe 57.24 MB). Kamera yakalama ve AI cikarimi TEK surecte, TEK donguded birlesik. Goruntu merkeze hic gonderilmez; kayitlar yerel SQLite'ta tutulur.",
      "AI: YOLOX (Megvii, Apache-2.0) + onnxruntime. Insan ve arac gercek tespitle calisir. OLCUM: yolox_nano 3.7 MB, 7.6 ms/kare, 131.5 FPS (CPU, 6 cekirdek). GPU varsa CUDA/DirectML saglayicisi kendiliginden secilir.",
      "LISANS KARARI: Once YOLOv8 (Ultralytics) denendi ve calisti, ancak AGPL-3.0 oldugu dogrulandi -- ticari kapali kaynak dagitimda tum GOKTUNGU kaynagini kamuya acmayi gerektirirdi. Model silindi, Apache-2.0 lisansli YOLOX ile degistirildi.",
      "DRON/PLAKA: COCO veri kumesinde bu iki sinif YOK. 'airplane'/'bird' sinifini dron diye sunmak yaniltici olurdu; yapilmadi. Ayri model ile ikinci asamada eklenecek.",
      "KARMA ICERIK OLCUMU: HTTPS merkez sayfasindan http://127.0.0.1 yuklemesi tarayici tarafindan ENGELLENIR. Belirleyici deney: acik port 1 ms'de, kapali port 1 ms'de, gercek ag istegi 4051 ms'de dustu -- yani istek aga hic cikmadi. no-cors kipinde de ayni. Bu yuzden panel merkeze GOMULMEZ; menu ogesi kopru panelini YENI SEKMEDE acar (sekme adresine karma icerik kurali uygulanmaz).",
      "YOKLAMA YAPILMAZ: Ayni engel 'kopru kurulu mu' yoklamasini da durdurur. Yanlis bir 'kurulu degil' mesaji gostermektense kullaniciya her iki yol da (paneli ac / indir) acikca sunulur.",
      "MENU: AI menusu etiketi sozlukle hizalandi. OLCULEN TUTARSIZLIK: HTML metni 'LOKASYONLAR' iken data-i18n='mbAI' ve sozlukte 'AI' yaziyordu; i18n her [data-i18n] ogesinin textContent'ini ustune yazdigi icin canlida zaten 'AI' gorunuyordu. HTML metni gerceklestirildi.",
      "KAYITLI LOKASYONLAR YERINDE BIRAKILDI: baska hicbir menude gecmiyor, kaldirilirsa erisim tamamen kaybolurdu.",
      "TEMIZLIK: Sokum sonrasi olu kalan 6 i18n anahtari x 2 dil = 12 kayit silindi (mbAISunucular, mbAIKutuphane, mbAIKisiler, mbAIAraclar, mbAIKayitsiz, mbAIGecmis).",
      "ONBELLEK DAMGASI KUSURU DUZELTILDI: Varliklar '?v=v24122' damgasiyla yukleniyordu ama App surumu 2.4.124 idi -- damga IKI SURUMDUR guncellenmemis. 2.4.123 ve 2.4.124'te degisen JS dosyalari kullanicilarin tarayici onbelleginde eski kalmis olabilir. 94 gecisin tamami v24125'e yukseltildi.",
      "SOZLESME UYUMU: Popup 'lokasyonPopup' kalibini izler; popupBoyutlandirilabilirYap/popupTasinabilirYap ile merkezi pencere altyapisina kaydedilir. Dugmeler duz <button> (dugme_birlik.css sozlesmesini otomatik alir; <a> almazdi). Tum renkler CSS degiskeninden, sabit renk yok.",
    ],
  },
  { s: "2.4.124", t: "2026-08-21",
    b: "Video ve yapay zeka katmani sistemden tamamen kaldirildi [FAZ19-IS71-IS73-SURUM-v1]",
    m: [
      "TALEP (kullanici): 'sistemden tum video ve ai ozelliklerini kaldiralim, kopruden de kaldiralim, onu ayri bir alt yapida sonra tekrar kurgulayalim, drondan, merkezden, sistemden, kopruden her yerden kaldiralim'",
      "GEREKCE: Kullanici ustuste 'sistem kilitleniyor' bildirdi. Video akisi (MJPEG 8801) ve AI cikarimi ayni surecte kosuyordu; OpenCV/numpy bellege aliniyordu. Katman ayri bir altyapida yeniden kurgulanacak.",
      "ARSIV ONCE: Sokum oncesi 37 dosya arsivlendi (/opt/goktungu/arsiv/ + yerel kopya, sha256 esit: 0d135f22...). Arsivde REHBER.md var: ucdan uca mimari, 6 tuzagin kaydi (Windows cihaz sirasi guvenilmez, ad onbellegi bayatlamasi, alan adi uyusmazligi, kip ayrimi, cift kayit) ve COZULEMEYEN kusurun durust kaydi (video ucuncu baslatmada kayboluyor - kok neden bulunamadi, yeni altyapida yasam dongusu bastan tasarlanmali).",
      "APP ARAYUZ: 11 JS dosyasi kaldirildi (ai_panel, ai_sunucular, ai_tespitler, ai_kutuphane, kameralar, kamera_harita, kamera_tip_ikon, video_duvar, dron_kamera, mjpeg_yeniden, video.html). index.html 116 KB -> 94 KB.",
      "KORUNAN — LOKASYONLAR: AI menusu TUMDEN SILINMEDI. Icinde 'Lokasyonlar' vardi ve baska hicbir menude gecmiyordu; silseydim kayitli lokasyonlara erisim tamamen kaybolurdu. Menu govdesi korundu, etiketi LOKASYONLAR yapildi, 5 AI alt ogesi cikarildi.",
      "KORUNAN — mbAI KIMLIGI: HTML'deki display:none bir kusur DEGIL, oturum mantigi. kullanici.js giriste aciyor, cikista kapatiyor. Kimlik degistirilmedi.",
      "KORUNAN — istasyon2.js: Dosyada 39 kez 'kamera' geciyordu ama hicbiri video kamerasi degil, HARITA GORUS ACISI (joystick ile dondurme/egme/yakinlastirma). Dokunulmadi; kesseydim istasyon joystick denetimi kirilirdi.",
      "KENDI KUSURUM (onarildi): Kamera panelini iki kesimde cikardim; birinci kesim kameralarIcerik ACILISINI aldi, kapanisi hicbir kesimde kalmadi -> sahipsiz </div>. Gozle degil OLCUMLE yakalandi: sokum oncesi denge 521/521, sonrasi 436/437. Onarildi -> 436/436. DERS: cok parcali kesimde her parcanin dengesi AYRI olculmeli.",
      "ARKA UC — BOS OMURGA STRATEJISI: sunucu.py'de 65 AI cagrisi var, 42'si korumasiz. 9500 satirlik dosyada bunlari tek tek sokmek telemetri/harita/angajman zincirini riske atardi. Bunun yerine moduller AYNI ARAYUZE sahip bos omurgalarla degistirildi: ai_yonetici 933->152, video_proxy 764->111, kameralar 209->66, ai_ssh 401->68 satir. sunucu.py'ye HIC DOKUNULMADI.",
      "OMURGA SINAVI: 47 gecti / 1 'hata'. O hata port 8801'in acik olmasiydi -> olcum: 49 dakika once baslamis ESKI surec tutuyordu, omurga degil. Yeniden baslatinca kapandi. Sinav gercek bir yan etkiyi yakalayabildigini kanitladi.",
      "MERKEZ: mk_video.py omurgaya cevrildi. Sinavda kritik nokta: mk_sunucu.py:3802 kanal acma cagrisi IKI deger bekliyor; omurga tek deger dondurseydi merkez orada cokerdi. Birebir denendi, 11/11 gecti.",
      "KOPRU 1.7.9: 7 dosya silindi (4306 satir: ai_sunucu 1027, video_vekil 1008, servis_ai 934, servis_video 384, canli_video 352, ai_ssh 338, yerel_isci 263). 23 WS komutu kaldirildi. Servis listesi: Dron, GroundGCC, Radar.",
      "OPENCV KARARI (olculdu): Gomulu Python 179 MB -> 31 MB. arac_bul.py cv2 kullaniyor sanildi; olctum: KULLANMIYOR, sadece kurulu mu diye ARIYOR ve 'USB kamera calismayacak' uyarisi veriyor. Video kalkinca denetimin kendisi anlamsiz. Windows kurulum 43.4 MB -> 12.1 MB (%72 azalma), deb 1.4 -> 0.6 MB.",
      "PAKET TUTARSIZLIGI (yakalandi): Paketteki SURUM dosyasi 1.7.5 yaziyordu — son uc surumde guncellenmemis. Kurulu kopru kendini yanlis surumle tanitabilirdi. 1.7.9 olarak duzeltildi.",
      "KALDIRMA SATIRI KORUNDU: NSIS betiginde ai_sunucu.py KURULUM satiri cikarildi ama SILME satiri bilincli birakildi — eski surumden yukseltenlerin diskinde o dosya kalmis olacak.",
      "IS73 ROZET: seri.js KOPRU_SERVIS_SIRASI 5 -> 3 servis. Kopru 1.7.9 ai/video bildirmedigi icin arayuz '?' (bilinmiyor) gosteriyordu — bu davranis DOGRU tasarlanmis, sorun listenin kendisiydi.",
      "IS73 GUNLUK: main.py merkez kipinde saha_vekil.VideoVekili/AiVekili kuruyordu; bunlar bos omurgalara bagli — is yapmaz ama KONUSUR. '[VIDEO] kamera akisi kopruden aktarilir', '[AI] cikarim sahada kosar' satirlari basiliyordu. Islev yokken konusan kod sistemde AI varmis izlenimi verir. Kip ayrimi kaldirildi, ai_ssh blogu (578 bayt) ve _yerel_ai_isci_baslat (4297 bayt) silindi. main.py 48379 -> 44499 bayt.",
      "YAN ETKI OLCUMU (zorunlu): sunucu.py'de 29 ai_ssh gecisi 'korumasiz' gorundu. KONTROL: satir 333 'self.ai_ssh = None' + satir 7611 'if self.ai_ssh is None:' -> koruma is-None kalibiyla yapilmis, getattr/hasattr degil. Aramam kabaydi; kirilma yok.",
      "IS72 TANITIM: Once /opt/goktungu/tanitim/ arandi — DIZIN YOK. Canli sayfa /opt/goktungu/merkez/web/index.html cikti (79304 bayt, dis indirmeyle eslesti). Sunucuda 3 ayri dil.js var, sadece js/dil.js yukleniyor (digerleri olu). Yanlis dosyayi yamalamamak icin canli sayfa disaridan indirilip dogrulandi.",
      "IS72 DIL MIMARISI: TR metinler HTML icinde gomulu, sozlukte yalnizca EN karsiliklari var. TR icin index.html, EN icin dil.js AYNI ANDA guncellenmeli — yoksa dil degisince kaldirilan icerik geri gelir.",
      "IS72 TURLAR: A) mimari sema kutulari, AI yetenek karti, kamera sekmesi+figure, 5 anlatim metni. B) meta etiketleri (SEO'da hala 'yapay zeka goruntu isleme' vaat ediyordu), 'bes servis'->'uc servis'. C) mimari.yonetimalt, guv.g5alt, fiy.k1m3. D) mimari.aciklama EN hizalamasi (TR zaten dogruydu, EN'de 'camera' kalmisti). 81502 -> 79282 bayt.",
      "FIYATLANDIRMA — BILINCLI DOKUNULMADI: Kurumsal Bulut paketi 16.900 TL/ay ve 'Yapay zeka: nesne, arac ve plaka tespiti' vaat ediyor. 5 yapay zeka ifadesi + fiy.k3m2 + fiy.skuYz korundu. Bu TICARI karar; teknik sokum kapsaminda tek tarafli degistirilmedi, kullaniciya soruldu.",
      "DOGRULAMA: WebSocket 101 GECTI (kirilsaydi tum telemetri kesilirdi), 5 alan HTTP 200, acilis gunlugu sifir hata, MJPEG portu 8801 kapandi, OpenCV/torch bellekte YOK, div dengesi 223/223, IS67 gzip kazanci korundu (stil.css 74 KB)."
    ] },
  { s: "2.4.123", t: "2026-08-21",
    b: "Sayfa yuku %73 kucultuldu; AI panellerinde kamera adlari onarildi [IS67_IS68_SURUM_v1]",
    m: [
      "BELIRTI (kullanici): 've sanirim arkada bir seyler calisiyor cunku sistemde ki hersey yavasladi, musteri paneli bile calismiyor' / 'malesef kilitleniyor sistem'.",
      "YANLIS TESHIS - ITIRAF: Iki gun boyunca gecikmeyi TLS el sikismasinda aradim. Olctugum 1.85 s degeri GERCEK DEGILDI: kendi olcum ortamimin bazi hedeflere ekledigi taban gecikmeydi. Kontrol deneyi yapinca ortaya cikti - ayni ortamdan google.com 1.24 s, cloudflare.com 1.25 s, microsoft.com 1.45 s olculuyordu. Bu sirketlerin boyle bir gecikmesi olamaz. Kontrol deneyini ilk gun yapmaliydim.",
      "SUNUCU ZATEN SAGLIKLIYDI: Loopback HTTPS 19 ms, sunucunun kendi dis IP'sinden 24 ms, yuk 0.46/4 cekirdek, bellek 8 GB'in 202 MB'i. SSL Labs bagimsiz notu A. Turkiye/Istanbul dugumunden olculen gercek deger 0.118 s.",
      "GERCEK KOK NEDEN (olculdu): App sayfasi acilirken tarayici 111 ayri istekte 10.48 MB indiriyordu ve sunucu HIC SIKISTIRMA yapmiyordu. `Content-Encoding` basligi yanitlarda yoktu; gzip destegi bildiren istemciye bile ham veri gidiyordu. En agirlari Cesium.js 4.95 MB, param_aciklama.js 792 KB, param_aciklama_tr.js 771 KB, stil.css 337 KB.",
      "NEDEN 'KILITLENME' HISSI: HTTP/1.1 ayni sunucuya en fazla 6 es zamanli baglanti acar. 111 kaynak yaklasik 19 turda iner ve her tur bir gidis-donus bekler. Sunucu 24 ms'de yanit verse bile tarayici hala dosya indiriyordur.",
      "ONARIM (IS67): Merkez aktarim kapisina gzip eklendi. Olculen sonuc: 10.48 MB -> 2.82 MB (%73.1 kazanim). stil.css 344->74 KB, Cesium.js 5.07->1.43 MB. Gercek indirme suresi stil.css 7.08->3.71 s, Cesium.js 28.16->10.02 s.",
      "CPU TUZAGI KAPATILDI: Cesium.js'i her istekte sikistirmak 239 ms CPU yakiyordu. Sikistirilmis govde bellekte onbelleklenir; dosya degismedikce bir kez hesaplanir. Sikistirma islemi KILIT DISINDA yapilir - aksi halde es zamanli istekler birbirini beklerdi.",
      "KAPSAM DISI BIRAKILANLAR (olcerek): Gorseller ve videolar (yeniden sikistirmak dosyayi buyutur), MJPEG canli akis (sonsuz yanit tamponlanamaz), 206 bayt-araligi yanitlari. Sinav: 4 dosyanin sha256 ozeti sikistirilip acildiktan sonra ham haliyle birebir ayni cikti.",
      "IS68/K1 - KAMERA ADLARI: Kamera kaydinin ad alani `isim`; AI tarafindaki 5 nokta `ad` okuyordu ve her zaman bos donuyordu. En kotusu tespit suzgeci: orada yedek deger de yoktu, acilir liste bos satirlarla doluyordu. ai_panel.js, ai_sunucular.js, ai_tespitler.js (2 nokta), istasyon2.js onarildi.",
      "IS68/K1 NEDEN `isim || ad`: Tek basina `isim` yazmak yeterli GORUNUYORDU ama merkez kipinde kamera listesi `saha_vekil.VideoVekili` uzerinden kopruden gelir; o yolun alan adini bu yamada OLCMEDIM. Iki adi da denemek, olcmedigim yolu kirmadan olctugum yolu onarir.",
      "IS68/K2 - CIFT AI SUNUCUSU: `ai_sunucular` tablosunda iki kayit ayni makineyi gosteriyordu (id=5 'PC' ve id=6 'CPU': ayni host/port/kopru). Bu yalniz gorsel kirlilik degil - `_en_az_yuklu()` bunlari AYRI isci sanip kapasiteleri topluyordu (2+4=6 yuva) ve tek surece alti gorev gonderiyordu; ayrica saglik yoklamasi her tur ayni adrese iki istek atiyordu.",
      "IS68/K2 ONARIM: `kaydet()` icinde INSERT oncesi ayni (host, port, kopru_ornek_id, firma_id) dortlusu aranir; bulunursa yeni satir acilmaz, var olan guncellenir. Reddetmek yerine guncellemek kullanicinin 'bu makineyi tanit' niyetini karsilar. Veritabani UNIQUE kisiti KULLANILMADI: mevcut yinelenen satirla cakisip gocu kirardi ve NULL'lar SQL'de birbirine esit sayilmadigi icin bu satirlari zaten yakalamazdi.",
      "IS68/K2 SINAVI (gercek kosum): S1 farkli port -> satir arttl (kontrol), S2 ayni uclu -> satir ARTMADI, ayni id korundu, alanlar guncellendi, S3 farkli kopru -> arttl (kontrol), S4 farkli firma -> arttl (kontrol). Kontrol deneyleri yamanin 'her seyi engelliyor' olmadigini kanitlar.",
      "VERI TEMIZLIGI: Yinelenen kayit id=5 silindi (kapasite 2), id=6 korundu (kapasite 4). `ai_tespitler` tablosunda bu sunuculara bagli 0 kayit vardi - veri kaybi yok.",
      "KOPRU DURUMU (olculdu, kusur DEGIL): Kullanicinin koprusu (ornek 38, 'GeneralManager', surum 1.7.8) merkeze kayitli ama cevrimdisi. Merkez kipinde AI vekili kopruden ozet ceker; kopru yoksa liste bos doner ve AI sunuculari kirmizi gorunur. Sistem dogru davraniyor. Kanit: kopru 36 ve 37 ayni sunucuya su anda nabiz atiyor.",
      "GZIP YAMASI KOPRUYU BOZMADI - SINANDI: Merkez yeniden baslatmasi (14:02:49) ile kopru 38'in son nabzi (14:02:26) 23 saniye arayla oldugu icin kendimden suphelendim. Kontrol deneyi: kopru 36 ve 37 ayni yeniden baslatmayi yasadi ve yamali sunucuya sorunsuz yeniden baglandi."
    ] },
  { s: "2.4.122", t: "2026-08-21",
    b: "Kamera cihaz secimi: tahmin katmani kaldirildi, kayit tek otorite [IS66_SURUM_v1]",
    m: [
      "BELIRTI (kullanici): 'hala ucuncu seferde kameralar arasinda geziyor, bu kadar zor mu? kamera indexini veri tabanina yazacaksin tekrar tekrar oradan okuyacaksin. donanim degisikligini de manuel tarasin kullanici'.",
      "KOK NEDEN (nihayet olculdu): Kusur kamera ACMA yolunda degil, CIHAZ LISTESININ KENDISINDE. Windows'ta `cihaz_listesi()` indeksi OpenCV'nin DirectShow numaralandirmasindan, adi ise WMI `Win32_PnPEntity` sorgusundan aliyor ve ikisini YAN YANA koyuyordu. Bu iki siralamanin ortusme garantisi YOK - kodun kendi yorumu (video_vekil.py:607-609) bunu zaten itiraf ediyormus. Sonuc: listede yazan ad ile o satirin indeksi FARKLI kameralara ait olabiliyor. Operator dogru adi seciyor, kayda baska kameranin numarasi gidiyor.",
      "'UCUNCU SEFER' ACIKLANDI: Ad listesi 5 saniyelik onbellekte tutulur (`_AD_ONBELLEK_SN`). Sure dolunca WMI yeniden sorgulanir ve FARKLI SIRAYLA donebilir. Ayni kamerayi ucuncu kez actiginizda etiketler kaymis olur.",
      "1.7.6/1.7.7 NEDEN YETMEDI: O surumlerdeki 'cihaz kimlik defteri', adi kesin kimlik sayip indeksi ona gore duzeltiyordu. Defter BOZUK ESLESMEYE dayandigi icin bazen dogru bazen yanlis kamerayi aciyordu. Yani onarim, kusurlu verinin uzerine kuruluydu.",
      "ONARIM 1 - TAHMIN KATMANI KALDIRILDI (kopru 1.7.8): `cihaz_kimlik.json` defteri, okuma ucu, yazma ucu ve ayar.py'deki uc defter islevi tamamen silindi. Kayitta hangi indeks yaziyorsa O acilir; kopru kendi basina asla baska cihaza gecmez. Kullanici talimati birebir uygulandi.",
      "ONARIM 2 - TESHIS SATIRI: Kamera acildiginda konsola 'Kamera 5 acildi: indeks 1 (HD Pro Webcam C920)' yazilir. Tahmin yerine olcum: yanlis kamera acilirsa hangisi oldugu gorulur.",
      "ONARIM 3 - ELLE TARAMA (kullanici talimati): 'Kamerayi Duzenle' penceresine cihaz tarama dugmesi eklendi. Donanim degisince liste elle tazelenir. Dugmeye ozel sinif VERILMEDI: dugme_birlik.css:123 yalniz-ikon kurali (`:has(> i)`) onu kendiliginden 26x26 kareye sabitler - IS23 dugme sozlesmesi delinmedi.",
      "ONARIM 4 - DURUST ETIKET: Kopru artik her cihaza `ad_guvenilir` bayragi ekler (Linux: /sys/class/video4linux/videoN/name -> N == OpenCV N, eslesme GERCEK; Windows: WMI sayaci -> eslesme TAHMIN). Arayuz etiketi 'INDEKS - Ad' bicimine gecti; dogrulanamayan adin yaninda '(?)' ve aciklayici ipucu cikar. Operator artik hangi INDEKSI sectigini her zaman gorur.",
      "GERIYE DONUK UYUM: `ad_guvenilir` alani eski koprulerde (1.7.7-) hic gelmez. `hasOwnProperty` ile bilgi VARLIGI olculur; bilgi yoksa '(?)' basilmaz - yanlis alarm uretilmez.",
      "KORUNAN KAZANIM: Cihaz adi okuma KALDIRILMADI. Linux'ta dogru, Windows'ta ayirt edici ipucu. Kaldirilsaydi liste 'Kamera 0/1/2/3'e donerdi ve kullanicinin istedigi elle secim imkansizlasirdi."
    ] },
  { s: "2.4.121", t: "2026-08-21",
    b: "AI izleme zinciri onarildi: kamera oynatilinca AI gorevi GERCEKTEN atanir [IS65_SURUM_v1]",
    m: [
      "BELIRTI (kullanici): 'ai ozelliklerini actim, play dugmesine bastim kosede AI yazdi, ama yuzumun etrafinda bir cizgi cikmadi, ai ile alakali bir belirti cikmadi'.",
      "OLCUM: `ai_tespitler` tablosu 0 satir; `pilot_log` AI kategorisinde `ai_sunucu_kaydet` ve `kisi_yuz_ekle` kayitlari VAR ama `ai_izleme_baslat` kaydi HIC YOK. Yani komut hicbir zaman gonderilmemis.",
      "KOK NEDEN 1 (arayuz / OLU KOD): `aiIzlemeBaslat` js/kameralar.js icinde tanimli ve kod yorumunda 'kamera_harita.js ve kameralar.js tarafindan cagrilir' yaziyordu. Tum js agaci tarandi: HICBIR YERDEN CAGRILMIYORDU. Tanim vardi, cagri yoktu.",
      "KOK NEDEN 2 (sunucu / EKSIK YETENEK): `main.py:753` acilista `ai_yonetici.baslat()` cagirir. Lokal kipte bu `AIYonetici.baslat` olup `_gorevleri_geri_yukle` is parcacigini baslatir (v2.4.8 kazanimi: `ai_gorevler` dolu kameralar otomatik izlemeye alinir). MERKEZ kipinde ise sinif `AiVekili` ve `baslat()` govdesi SADECE LOG BASIYORDU. Kullanici merkez kipinde oldugu icin o kazanim hic calismiyordu.",
      "ONARIM 1 - TEK KAPI: Oynatma durumunu degistiren ALTI ayri yol olculdu (oynat, durdur, toplu baglan, ayrik pencere, kamera silme, pencere kapatma). Altisina ayri ayri cagri serpistirmek yerine `oynayanlar` kumesine dokunan tum yollar `oynatmaAc`/`oynatmaKapat` kapilarindan gecirildi; AI bildirimi kapinin icinde yapilir. Ileride eklenecek yedinci yol da kendiliginden kapsanir.",
      "ONARIM 2 - MERKEZ ACILISI: `AiVekili.baslat` icine `_acilis_izlemesi` is parcacigi eklendi. Kopru baglantisi merkez acilisindan SONRA kuruldugu icin `self._komut` hazir olana kadar araliklarla beklenir (20 x 6sn tavan; kopru hic baglanmazsa parcacik sonsuza kadar donmez).",
      "KOPYA YAZILMADI: Acilis taramasi kopruye komutu dogrudan gondermek yerine `self.izleme_baslat` cagirir - kamera kaydini pakete ekleme ve IS64 sozlesmesi tek yerde kalir. Dosyanin kendi docstring'i (satir 92-93) bu gerekceyi zaten yaziyordu.",
      "ROZET YANILTMASI: Kosedeki 'AI' rozeti kopruden gelen izleme listesine bakar. Kopru eski gorevleri hatirladigi icin rozet yaniyor, ancak yeni gorev atanmadigindan tespit gelmiyordu - operator AI'nin izledigini saniyordu.",
      "SINAV: Statik tarama YETERSIZ sayildi; `kameralar.js` gercek bir JS motorunda sahte tarayici ortaminda KOSTURULDU ve `aiIzlemeBaslat` cagrilari sayildi. `AiVekili` gercekten orneklendi, `baslat()` cagrildi, kopruye giden komutlar yakalandi. Kontrol deneyi: yamasiz surumde arayuz tarafinda cagri sayisi 0, sunucu tarafinda giden komut 0.",
      "SONUC: Arayuz 6/6, sunucu 7/7. Kontrol deneyleri sirasiyla 1/6 ve 4/7 - kusur birebir olculuyor."
    ] },
  { s: "2.4.120", t: "2026-08-21",
    b: "Gokkubbe Teknoloji harita konumu duzeltildi + haritaya kurumsal kisayol dugmesi [IS62_SURUM_v1]",
    m: [
      "BELIRTI: Gokkubbe Teknoloji isareti harita uzerinde YANLIS koordinatta gosteriliyordu.",
      "OLCUM: Yanlis deger tek yerde tanimliydi (js/harita_pilot_konum.js) - lat 39.9334 / lon 32.5785. Gercek adres 39.973112 / 32.546172. Haversine ile olculen sapma 5205 m (5.21 km); isaret Sincan'da bambaska bir noktayi gosteriyordu.",
      "TEK NOKTADAN DUZELTME: Sabit ayni dosya icinde DORT yerde okunuyor - harita isareti konumu, ilk giris acilis konumu, `haritaGokkubbeyeGit()` ve `haritaGokkubbeKoordinat()`. Dagilmis nusha olmadigi AST/metin taramasiyla dogrulandi, bu yuzden tek satirlik duzeltme dordunu birden duzeltir.",
      "KISAYOL DUGMESI: Harita arac grubuna (arama/cetvel/sigdir/konumuma) BESINCI dugme olarak uygulama ikonu eklendi ve kumenin ILK ogesi yapildi. Tiklaninca Gokkubbe adresine ucar (Cesium camera.flyTo, 2600 m).",
      "ISLEV ZATEN VARDI: `window.haritaGokkubbeyeGit` 2.4.x boyunca tanimliydi ve kod yorumunda 'menu/kisayol eklenmek istenirse' yaziyordu; onu cagiran dugme hic eklenmemisti. Zincirin her halkasi olculdu (viewer koprusu -> merkezeGit -> camera.flyTo) ve saglam oldugu dogrulandi.",
      "YAMA ICI KUSUR YAKALANDI: Dugmenin ilk halinde HTML/CSS/i18n vardi ama TIKLAMA OLAYI BAGLANMAMISTI - dugme gorunur ama islevsiz olacakti. Gorsel denetimde yakalandi ve baglama eklendi.",
      "BAGLAMA YERI OLCUMLE SECILDI: harita_pilot_konum.js, harita.js'ten SONRA yuklenir (index.html:1813 vs 1819). Baglama harita.js icinde yapilsaydi islev o an henuz tanimsiz olurdu. Tanim ve baglama ayni dosyada yan yana durur; ileride biri degisirse digeri gozden kacmaz.",
      "TEMA SOZLESMESI: Eklenen CSS sabit renk icermez; kardes dugmelerin sonme/canlanma davranisini `opacity` ile taklit eder. Logo kendi zeminini tasidigi icin 3px ic bosluk birakildi.",
      "BOYUT KUSURU (canli tarayicida yakalandi): Dugme ilk yayindan sonra 33x26 render oldu, kardesleri 26x26 idi. Sebep `dugme_birlik.css` yalniz-ikon sozlesmesinin `:has(> i)` ile yazilmasiydi; `<img>` tasiyan dugme kapsam disinda kalip genel `button { padding: 8px 14px }` kuralina dusuyordu. Statik denetim bunu goremezdi - kural CSS dosyasinda dogru duruyordu, eslesmiyordu.",
      "ONARIM YERI SECIMI: Nokta atisi `!important` yerine SOZLESMENIN KENDISI genisletildi (`:has(> i, > img)`). Sozlesmenin niyeti zaten 'yalniz ikon tasiyan dugme kare olsun'; ifadesi Font Awesome cagindan kalmaydi. Boylece ileride eklenecek gorsel-ikonlu dugmeler kendiliginden kapsanir. Olculdu: index.html'de yalniz-<img> tasiyan dugme sayisi 1, yani bu genisletme baska hicbir dugmenin gorunumunu degistirmez.",
      "IC BOSLUK: Sozlesme `padding: 0 !important` dayattigi icin ic bosluk yastikla verilemez; gorsel kutunun %82'sinde tutuldu. Sabit piksel yazilmadi - olcu (`--dgm-kare`) degisirse gorsel oraninda kucuk kalir.",
      "CACHE DAMGASI: Is 62 uc varlik dosyasini degistirdigi icin (stil.css, i18n.js, harita_pilot_konum.js) index.html damgasi v24115 -> v24120 yapildi. Guncellenmeseydi tarayici eski kopyalari kullanir, dugme bicimsiz ve islevsiz gorunurdu.",
      "SINAV: Yamali 37/37 gecti. Kontrol deneyi (yamasiz kaynak) 20 capada kaldi - kusur kanitlandi: 'hedefe sapma 5205 m', 'dugme sayisi 4', 'addEventListener bagli degil'. 15 gerileme capasi iki kosumda da gecti (zoom yuksekligi 2600 korundu, dort kardes dugme ve i18n anahtarlari yerinde, yukleme sirasi bozulmadi).",
      "MERKEZ UYGULAMASI: Ayni yanlis koordinat merkez 2.5.7 paket agacinda iki nushada daha bulundu; paketleme sirasinda duzeltilecek."
    ] },
  { s: "2.4.119", t: "2026-08-21",
    b: "Merkez kipinde AI otomatik izleme baslatilamiyor: 'gorev atanamadi' [IS64_SURUM_v1]",
    m: [
      "BELIRTI: Kamera goruntusu geldigi halde AI izleme baslatilamiyordu; arayuz 'Otomatik izleme baslatilamadi (kamera #N): gorev atanamadi' uyarisi veriyordu.",
      "KOK NEDEN: AiVekili.izleme_baslat kopru yanitindan `atandi` ve `gerekce` anahtarlarini okuyordu. Bu anahtarlari zincirin HICBIR katmani uretmez. Olculen gercek sozlesme her katmanda `tamam`/`hata`: isci ai_sunucu.izle(), kopru servis_ai._gorev_ata(), kopru uygulama._ai() ve yerel kip ai_yonetici.izleme_baslat() - dordu de ayni. Yani kopru gorevi %100 basariyla atasa bile merkez bunu basarisizlik sayiyor ve son care metnini basiyordu.",
      "BELIRTININ KAYNAGI: 'gorev atanamadi' bir teshis degil, govdenin en sonundaki varsayilan metindi. Kopru gercek bir gerekce dondurse bile (ornegin 'kapasite dolu') okunmuyordu; kullaniciya her kosulda ayni anlamsiz metin gorunuyordu.",
      "IKINCIL ETKI: Basari yolunda cek_gerekirse(zorla=True) cagrilmiyordu; atama gercekte basarili olsa bile aktif izleme listesi tazelenmiyor, panel bos kaliyordu.",
      "DOGRU SOZLESME ZATEN SISTEMDEYDI: Yerel kipteki AiYonetici.izleme_baslat {'tamam': True, 'sunucu': ...} dondurur. Merkez kipi yazilirken bu sozlesme yerine var olmayan anahtarlar varsayilmisti.",
      "ONARIM: `tamam` birincil, `atandi` ikincil okunur; hata metni `hata` -> `gerekce` -> son care sirasiyla cozulur. Geriye donuk uyum bilincli korundu: eski surum bir kopru hala eski anahtarlari donduruyorsa calismaya devam eder.",
      "AST TARAMASI: AiVekili'nin tum yontemleri tarandi; uydurma anahtar okuyan baska yontem YOK. Kusur tekil.",
      "KONTROL DENEYI: Zincirin GERCEKTEN urettigi {'tamam': True} yaniti verildiginde yamasiz govde {'tamam': False, 'hata': 'gorev atanamadi'} dondurdu - kullanicinin gordugu metin birebir uretildi. Yamali govde {'tamam': True} dondurdu ve cek_gerekirse cagirdi.",
      "SINAV: 25/25 gecti. Kapsam: kontrol deneyi, gerileme (kapasite dolu / ai sunucusu yok gibi GERCEK hatalar hala hata sayiliyor mu), geriye donuk uyum (eski atandi/gerekce anahtarlari), sinir durumlar (bos yanit, hatasiz basarisizlik) ve sozdizimi."
    ] },
  { s: "2.4.118", t: "2026-08-21",
    b: "Kamera durdurulup yeniden baslatilinca goruntu gelmiyor ve sistem kilitleniyor [IS63_SURUM_v1]",
    m: [
      "BELIRTI: Merkez kipinde kamera goruntusu ilk acilista geliyordu; durdurulup yeniden baslatildiginda siyah kutu kaliyor ve arayuz kilitleniyordu.",
      "KOK NEDEN: VideoVekili.yayin_durdur YALNIZ sahaya 'video_akis_durdur' komutu gonderiyordu. Yerel durum hic temizlenmiyordu: self._yayinlar kaydi silinmiyor, _UzakYayin.durdur() cagrilmiyordu. Boylece 'calisiyor' bayragi True kaliyor ve bir sonraki yayin_al() cagrisi OLU nesneyi geri veriyordu. Saha kaynagi kapali oldugu icin o nesneye kare gelmez - siyah kutunun sebebi budur.",
      "KILITLENME ZINCIRI: Her yeniden deneme, kare gelmeyecek bir yayina baglanip ilk_kare_bekle(12s) boyunca istegi acik tutuyordu. Istekler ust uste birikince arayuz tikaniyordu. Yani kilitlenme ayri bir kusur degil, ayni kok nedenin ikinci belirtisiydi.",
      "DOGRU KALIP ZATEN SISTEMDEYDI: Yerel kipteki VideoProxy.yayin_durdur ucunu de yapiyor - kaydi pop eder, nesneyi durdurur, gunluge yazar. Merkez kipi yazilirken ACMA tarafi bu kaliba uyduruldu, KAPATMA tarafi uydurulmadi. Kopyalanmasi gereken kod zaten mevcuttu.",
      "ONARIM: Merkez kipi ayni sozlesmeyi uygular. SIRA BILINCLI: once yerel temizlik (pop + durdur), sonra saha komutu. Ters sirada saha komutu ag gecikmesi yasarsa kayit o sure boyunca olu kalir ve ayni kusur kucuk bir pencerede tekrarlar.",
      "EK SAGLAMLASTIRMA: int() donusumu basa alindi. Gecersiz id gelirse HICBIR yan etki olusmadan donulur; eski govde once saha komutunu deneyip sonra TypeError yakaliyordu. Ayrica yerel temizlik cokerse saha komutu YINE gonderilir - yerel bir cokme saha kaynagini acik birakmaz.",
      "BILINCLI DOKUNULMAYAN: Yayin canlilik denetimi yalnizca 'calisiyor' bayragina bakiyor; kare akmasa da True kalabilir. Onarimdan sonra bu yol tetiklenmeyecek ve halihazirda 60 saniyelik izleyicisiz kapanma korumasi var. Gereksiz degisiklik gereksiz risktir.",
      "KONTROL DENEYI: Yamasiz govde GERCEK nesnelerle sinandi ve OLU YAYIN dondurdugu olculdu (kayit silinmedi, UDP soketi acik kaldi, merkez kanali kapanmadi). Yamali govde ucunu de dogru yapti. Kontrol deneyi olmadan bu yamanin gerekliligi kanitlanmis olmazdi.",
      "SINAV: 26/26 gecti. Kapsam: kontrol deneyi, yamali davranis, cagri sirasi, gecersiz girdi (None/str/list/dict), kayit yokken durdurma, yerel cokmede saha komutunun korunmasi, ve gerileme (iki sinifin yontem kumeleri, v2.4.33 ilk_kare_bekle onarimi, MAVLink port sirasi gerekcesi)."
    ] },
  { s: "2.4.117", t: "2026-08-20",
    b: "Merkez kipinde kamera goruntusu hic gelmiyor kusuru [IS60_SURUM_v1]",
    m: [
      "BELIRTI: Kamera onizlemesi hicbir kaynakta goruntu getirmiyordu. Kopru gunlugu saglikli gorunuyordu: kaynak aciliyor, kare uretiliyor, '1 etkin akis' yaziyordu - ama hemen ardindan 'Izleyici kalmadi' satiri geliyordu.",
      "KOK NEDEN - KOPUK HALKA: Arayuz video adresini 'window.location.hostname + :8801' kalibiyla kuruyordu. Kullanici app.goktungu.com uzerindeyken bu adres MERKEZ SUNUCUSUNU isaret eder; oysa MJPEG vekili kullanicinin KENDI makinesinde calisir. Ustelik sayfa https, vekil duz http - tarayici karisik icerigi ayrica engeller. Olculdu: merkez sunucusunda 8801 portu hic dinlenmiyor.",
      "TASARIM CELISKISI: Kaynak kodda 'bu servis merkeze KARE GONDERMEZ, akis saha koprusunde acilir' gerekcesi yaziliydi ve gerekce ciddiydi - video bant genisligi merkezi cokertebilir. Ancak arayuz tarafi bu tasarima UYMUYORDU, koprunun adresini hic bilmiyordu. Yazili tasarim ile kodun yaptigi is uyusmuyordu; goruntunun hic gelmemesinin sebebi buydu.",
      "REDDEDILEN ALTERNATIF - DOGRUDAN BAGLANTI: Tarayiciya koprunun yerel ag adresini vermek reddedildi. Iki engel olculdu: (1) https sayfadan http adrese baglanti tarayici tarafindan engellenir ve yerel ag adreslerine gecerli sertifika alinamaz, (2) kullaniciyi kopruyle AYNI AGDA olmaya mahkum eder, uzaktan izleme tumden biter.",
      "REDDEDILEN ALTERNATIF - MEVCUT KANALA BINDIRME: Kareyi MAVLink akis kanalina bindirmek reddedildi. Olculdu: o kanal bir DONANIM baglantisidir, acilinca seri porta veya cihaza baglanir. Video kaynagi zaten acik oldugu icin ikinci bir donanim baglantisi anlamsiz olurdu ve telemetri yolunu kirilganlastirirdi.",
      "COZUM: Kare, telemetri icin zaten kurulu olan ters WSS hatti uzerinden merkeze tasinir; merkez onu App surecine UDP ile teslim eder; App surecindeki MJPEG sunucusu tarayiciya sunar. Yeni bir yakalama mekanizmasi yazilmadi - koprude kare zaten hazir bekliyordu.",
      "BANT GENISLIGI SINIRLARI: Reddedilme gerekcesi 'tum saha kameralarini pompalamak' senaryosuydu; o senaryo yapisal olarak olusamaz. Akis YALNIZ izleyici varken calisir, 10 fps, dusuk kalite, es zamanli en fazla 2 kamera, izleyici ayrilinca aninda durur. Tepe yuk ~1 MB/s.",
      "TASIMA TAVANI OLCULDU: UDP datagram siniri gercek soketle sinandi - 65507 bayt gecti, 70 KB reddedildi. Kopruye 60 KB tavani konuldu: kare asarsa kalite kademeli dusurulur, hala asiyorsa kare atlanir. Boylece merkez ve App tarafinda parcalama/birlestirme mantigi HIC yazilmadi; her paket tam bir kare.",
      "PORT SAHIPLIGI - GECMIS TUZAK TEKRARLANMADI: Telemetri tarafinda olculmus bir kusur vardi - merkez kendi portunu bildiriyor, karsi taraf ayni portu bind etmeye calisip 'Address already in use' aliyordu. Video kanalinda portu APP TARAFI bind eder ve merkeze bildirir; bildirmezse kanal hic acilmaz.",
      "NEDEN TAMPON YOK: Telemetri kanali kesinti tamponu tutar ve orada DOGRUDUR - ilk HEARTBEAT kaybolursa baglanti hic kurulmaz. Video icin TERSI gecerlidir: birikmis kareler geri geldiginde operator gecmis goruntuye bakip guncel sanir. Video kanali tamponsuzdur, App dinlemiyorsa kare ATILIR.",
      "KOD COGALTILMADI: App surecindeki MJPEG sunucusunda bugune kadar UC kusur duzeltilmisti (ilk kare gelmeden yanit yazilmasi, hatalarin anlasilmaz genel mesaja donusmesi, kopan baglantida cokme). Govde merkez kipi icin KOPYALANMADI - kopyalansaydi dorduncu duzeltme yalniz bir tarafa uygulanir, digeri sessizce eski kusurla kalirdi. Govde tek ortak yere tasindi; yerel ve merkez kipi ayni koddan beslenir.",
      "SINAVIN YAKALADIGI GERCEK KUSUR: Merkez, kopruden gelen veriyi cozerken GEVSEK kipteydi - bozuk veri geldiginde hata vermek yerine sessizce cope cevirip gecerli saniyordu. Olculdu: 3000 baytlik gecersiz girdi 2250 baytlik cope donusup zincirin sonuna kadar tasindi. Sahada bu, bozuk goruntu gorup sebebini asla bulamamak demekti. Siki kipe alindi ve JPEG imza denetimi eklendi; bozuk veri artik dusen-kare sayacina ve acik gerekceye donusur.",
      "DOGRULAMA - UCTAN UCA: Zincirin tamami gercek nesnelerle kosuldu (kare uretimi -> merkez -> UDP -> App -> gercek HTTP istemcisi). 25 denetimin tamami gecti: kareler BAYT BAYT tarayiciya ulasti, dusen kare yok, port cakismasi tuzagi tekrarlanmadi, kanal kapaninda sizinti kalmadi, servis yokken 503 ile ACIK gerekce dondu. Yerel kipin bozulmadigi ayrica olculdu - olmayan kamera icin hala 'kamera 9 kayitli degil' gibi gercek gerekce donuyor."
    ] },
  { s: "2.4.116", t: "2026-08-20",
    b: "AI sunucusu silinemiyor kusuru - merkez kipinde tip catismasi [IS59_SURUM_v1]",
    m: [
      "BELIRTI: AI SUNUCULARI panelinde bir kaydin cop kutusuna basildiginda kayit silinmiyor ve ust kosede 'Komut hatasi (ai_sunucu_sil): list object has no attribute items' uyarisi cikiyordu.",
      "KOK NEDEN - ODUNC CALISAN GOVDE: Merkez kipinde AI yoneticisi gercek sinif degil, sahadaki kopruye vekalet eden bir vekil nesnedir. Vekil, silme islemini kendi govdesiyle yapmaz; gercek sinifin govdesini KENDI uzerinde odunc calistirir. Gercek sinifta gorev haritasi bir SOZLUK, vekilde ise sahadan gelen bir LISTEDIR. Govde sozluk sanip anahtar-deger gezinmesi denedigi icin merkez kipinde cokuyordu.",
      "NEDEN SIMDIYE KADAR GORULMEDI: Vekil yalniz merkez kipinde devreye girer. Yerel kipte gercek sinif kullanilir ve gorev haritasi sozluktur; silme sorunsuz calisir. Kusur merkez kipinde ilk silme denemesinde ortaya cikti.",
      "KAPSAMLI TARAMA YAPILDI: Ayni tuzagin baska kurbanlari olabilecegi icin sozdizimi agaci uzerinden tarama yapildi. Vekilin odunc calistirdigi 11 yontem ile gercek sinifta gorev haritasi okuyan 8 yontem karsilastirildi; kesisim TEK bir yontem cikti. Iki sinif arasindaki tum nitelik tipleri de karsilastirildi, catisan tek nitelik gorev haritasi. Baska gizli kurban yok.",
      "ONARIM: Gorev tasima adimi yalniz gorev haritasi gercekten bir sozlukse yapilir. Merkez kipinde gorevler zaten SAHADA kosar; merkezin tasiyacagi bir gorev yoktur, dolayisiyla adimi atlamak yalniz cokmeyi onlemekle kalmaz, dogru davranisi da ifade eder.",
      "REDDEDILEN ALTERNATIFLER: Vekilin gorev alanini sozluge cevirmek reddedildi - o alan kopruden gelen listeyi tasiyor ve izleme listesi yontemi onu tuketiyor, tip degisikligi saha akisini bozardi. Vekile ayri bir silme govdesi yazmak da reddedildi - veritabani silme mantigi iki yerde cogalir, ileride biri guncellenip digeri unutulur.",
      "DOGRULAMA - KONTROL DENEYI: Silme govdesi kaynaktan izole edilip iki farkli nesne ile kosturuldu. Yamasiz kosumda merkez kipi kullanicinin gordugu hatanin AYNISINI uretti ve veritabani silme cagrisinin hic yapilmadigi, yani kaydin gercekten silinmedigi kanitlandi. Yamali kosumda 21 denetimin tamami gecti. Yerel kipin gorev tasima davranisi (dogru gorevlerin tasinmasi, baska sunucunun gorevine dokunulmamasi) yamadan once de sonra da ayni sonucu verdi - gerileme yok."
    ] },
  { s: "2.4.115", t: "2026-08-20",
    b: "Dok kaldirmasinda kacirilan olu cagrilarin temizlenmesi [IS56B_SURUM_v1]",
    m: [
      "BULGU: 2.4.114 yayina alindiktan sonra yapilan genel tarama, arayuz betigi icinde IKINCI bir dok cagri cifti buldu. Ilk olcum bunu kacirmisti: tarama pencere tasima modulu uzerinden yurutulmus, yuzen panellerin tasimasinin AYRI bir modulde kuruldugu gozden kacmisti.",
      "ETKI DEGERLENDIRMESI - ZARARSIZDI: Kacirilan cagrilar koruma kalibi ile sariliydi; dok modulu artik yuklenmedigi icin kosul yanlis donuyor ve govde hic calismiyordu. Canli olcum surukleme ve konum kaydinin dogru calistigini dogrulamisti. Kullaniciya yansiyan bir kusur olusmadi.",
      "YINE DE TEMIZLENDI: Olu kod ileride yaniltir; ayrica yorumlar artik gecersiz bir mimariyi anlatiyordu. Iki kanca ve gecersiz aciklamalar kaldirildi, konum kaydi kosulu sadelestirildi.",
      "DERS KAYDA GECIRILDI: Bir ozellik kaldirilirken tek giris noktasindan degil, tum kod tabaninda ozellik adiyla arama yapilmali. Bu tur ozellikler birden fazla modulden cagrilabiliyor."
    ] },
  { s: "2.4.114", t: "2026-08-20",
    b: "Pencerelerin ic ice gecme (dok) davranisinin kaldirilmasi [IS56_SURUM_v1]",
    m: [
      "TALEP: Kullanici pencerelerin ic ice gecme olayinin iptal edilmesini istedi; gerekce olarak duzgun calismadigini bildirdi. Bu ozellik v2.4.24 te eklenmisti: bir pencere digerinin uzerine surukleyip birakildiginda iki pencere sekmeli veya bolmeli tek bir kapsayicida birlesiyordu.",
      "KALDIRMA YONTEMI - DOSYA SILINMEDI: Dok mimarisi 1361 satirlik bir betik ve 337 satirlik bir bicem dosyasindan olusuyor. Bu dosyalar SILINMEDI, yalnizca sayfa baglantisindan cikarildi. Yuklenmeyen bir dosya calismaz; silmek ise geri donusu zorlastirir ve baska bir yerde ona yapilan gizli bir atif varsa hatayi acilis aninda degil kullanim aninda uretir. Geri donus gerekirse iki satirlik baglanti yeter.",
      "KRITIK BAGIMLILIK OLCULDU - BASLIK LISTESI: Surukleme sistemi hangi ogelerin pencere basligi sayilacagini belirlerken once dok modulunun tanimladigi listeyi okuyor, o yoksa kendi yedek listesine dusuyordu. Dok modulu kaldirilinca yedek liste birincil kaynak haline gelir. Iki listenin BIREBIR AYNI dokuz sinifi icerdigi karsilastirmali olarak dogrulandi: popup, yuzen, dron kartlari, kip penceresi, kamera onizleme, kamera penceresi, video duvari ve suru yonetimi basliklari. Uyusmazlik olsaydi bazi pencereler surukleme yetenegini kaybederdi.",
      "KRITIK BAGIMLILIK OLCULDU - KONUM KAYDI: Surukleme bittiginde pencere konumu depoya yaziliyordu, ancak dok islemi gerceklestiyse yazilmiyordu (pencere artik bir kapsayicinin icinde oldugundan kendi konumu anlamsizdi). Dok kaldirilinca bu kosul her zaman dogru olur; kosul tumuyle cikarildi ve konum dogrudan kaydedilir hale getirildi.",
      "DEPO TEMIZLIGI KURTARILDI: Kaldirilan dok modulu kendi icinde bir depo temizligi tasiyordu; eski surumlerin biraktigi kapsayici konum kayitlarini siliyordu. Modul kaldirilsaydi bu temizlik de kalkacak ve artiklar mevcut kurulumlarda kalicilasacakti. Temizlik islevi ayri bir modul olarak kurtarildi ve kapsami genisletildi: artik dok onekli TUM kayitlar temizleniyor. Devir teslim tarayicida dogrulandi; kontrol deneyinde dok modulunun sildigi iki artigi yamali kosumda yeni modul sildi.",
      "OLU KOD TEMIZLENDI: Panel acilis yerlestirmesi, pencerenin bir dok kapsayicisi icinde olup olmadigini kontrol ediyor ve oyleyse konumlandirmayi kapsayiciya birakiyordu. Kapsayici artik hic uretilmedigi icin bu kontrol olu koda donustu ve kaldirildi. Ortalama mantigi ve digerleri dokunulmadan korundu.",
      "DAVRANISSAL DOGRULAMA: Gercek tarayicida yamasiz ve yamali surumler yan yana olculdu. Surukleme oncesi ve sonrasi pencere konumu ile depoya yazilan deger iki kosumda BIREBIR AYNI cikti. Dok cagrilarinin kaldirilmasi tasima davranisini hicbir noktada degistirmedi. Dok kapsayicisi DOM da hic uretilmedi.",
      "ETKILENMEYENLER: Panellerin ekran ortasinda acilmasi, en az 400x300 boyut sozlesmesi, alt durum cubuklari, boyutlandirma tutamaklari, tiklaninca one gelme ve ust bar alti sinirlamasi olculdu; hicbiri dok moduluna bagimli degil ve hepsi calismaya devam ediyor.",
      "KALAN ZARARSIZ ATIF: Metin secimi bicem dosyasindaki dok baslik secicisi oldugu gibi birakildi. Artik uretilmeyen bir sinifi hedefler, hicbir etkisi yoktur ve ozellik ileride geri getirilirse hazir durur."
    ] },
  { s: "2.4.113", t: "2026-08-20",
    b: "Metin seciminin kapatilmasi; secim yalniz giris alanlarinda acik [IS55_SURUM_v1]",
    m: [
      "TALEP: Kullanici arayuzde hicbir metnin secilememesini, secimin yalnizca giris alanlarinda calismasini istedi. Ekran goruntusunde Baglanti Yoneticisi panelinde surukleme sirasinda kopru adresi, surum bilgisi ve calisma durumu rozetlerinin mavi secim vurgusuyla boyandigi goruluyordu.",
      "KOK NEDEN - KAPSAYICI KURAL YOKLUGU: Olcum, secim engellemenin bugune kadar tek tek secicilere elle eklendigini gosterdi: uygulama genelinde kirk bir ayri yerde secim kapatma kurali vardi, ancak html veya body duzeyinde kapsayici tek bir kural HIC yoktu. Bu yuzden sonradan eklenen her panel, kart ve rozet varsayilan olarak secilebilir kaliyor ve ayni kusur her yeni bilesende yeniden ortaya cikiyordu. Nokta atisi duzeltme yerine kapsayici bir sozlesme kuruldu.",
      "KOPYALAMA ISLEVI ARASTIRILDI: Secimi kapatmadan once kullanicinin metni kopyalamaya ihtiyac duydugu bir yer olup olmadigi olculdu. Tum uygulama dosyalarinda pano cagrisi arandi; bulunan tum esmeler Arm Check ekraninin ikon adiydi, gercek bir pano islevi degil. Uygulamada kopyalama islevi bulunmadigi dogrulandi, dolayisiyla secimi kapatmak mevcut hicbir islevi bozmuyor.",
      "ISTISNA - GIRIS ALANLARI: Metin kutulari, cok satirli alanlar, acilir listeler ve liste secenekleri secilebilir birakildi. Istisna listesi, pencere surukleme kodunun zaten tanidigi oge ailesiyle ayni tutuldu; boylece iki sozlesme birbiriyle tutarli kaldi. Duzenlenebilir icerik nitelikleri de savunma amaciyla listeye alindi; su an kullanilmiyor ancak ileride eklenirse kendiliginden calisacak.",
      "ISTISNA - DRON KONSOLU: Konsol ciktisi secilebilir birakildi. Kullanici bir hata yasadiginda konsol metnini secip iletebilmeli; uygulamada kopyalama dugmesi olmadigi icin secim tek tanisal yoldur. Bu istisna bilincli bir karardir.",
      "NEDEN EVRENSEL SECICI KULLANILMADI: Kural evrensel secici ile yazilsaydi her ogeye dogrudan uygulanir ve kalitim kirilirdi; bu durumda istisna secicilerin her alt ogeyi ayrica hedeflemesi gerekirdi. Bunun yerine kural koke yazildi ve kalitimla tum agaca yayildi. Istisna seciciler kalitimi tek noktada keser; giris alaninin icindeki metin dugumleri de kendiliginden secilebilir olur.",
      "MEVCUT KIRK BIR KURAL KORUNDU: Var olan secim kapatma kurallarinin tamami yeni sozlesme ile ayni yonde calisiyor. Silmek islevsel bir kazanc saglamayacak, buna karsilik genis bir gerileme riski uretecekti; oldugu gibi birakildilar.",
      "YUKLEME SIRASI: Yeni bicem dosyasi tum diger bicem dosyalarindan SONRA baglandi. Onceki bir konumda olsaydi istisna kurallari sonraki dosyalardaki secim kapatma kurallariyla ezilebilir ve giris alanlarinda secim calismazdi.",
      "KAPSAM KARARI: Duzeltme harekat arayuzune uygulandi. Tanitim sitesi, destek belgeleri ve yasal metinler kapsam disinda birakildi; bu sayfalarda metin kopyalanabilirligi bir erisilebilirlik ozelligidir ve kapatilmasi kullaniciya zarar verir. Yonetim ve musteri panelleri de bu turda disarida tutuldu; kullanici isterse ayri is olarak eklenir.",
      "ETKILENMEYENLER: Secim kapatma yalnizca metin secimini engeller. Sekme ile gezinme, odak halkasi, ekran okuyucu erisimi, tarayicinin sayfa ici aramasi ve giris alanlarina yazma/yapistirma islevleri olculdu ve etkilenmedigi dogrulandi.",
      "GERI ALMA: Bicem dosyasinin baglantisi kaldirildiginda davranis onceki durumuna doner; baska hicbir dosya bu degisiklige bagimli degil."
    ] },
  { s: "2.4.112", t: "2026-08-20",
    b: "Turkce/Ingilizce ceviri taramasi ve bulunan uc eksigin tamamlanmasi [IS54_SURUM_v1]",
    m: [
      "TALEP: Kullanici tum yazilimin Turkce ve Ingilizce metinlerinin taranmasini, eksik veya cevrilmemis metin varsa tamamlanmasini istedi. Tarama App arayuzu, tanitim sitesi, destek (yardim) sitesi ve dort yasal sayfayi kapsadi.",
      "UC AYRI SOZLUK MIMARISI OLCULDU: Sistem tek bir ceviri altyapisi kullanmiyor. App `DILLER` icinde TR ve EN sutunlarini yan yana tutar. Tanitim sitesi TR sozlugu HIC tutmaz; HTML e gomulu Turkce kaynak kabul edilir, Ingilizceye gecildiginde sozlukten yazilir ve Turkceye donuldugunde ilk yuklemede saklanan ozgun metin geri konur. Destek sitesi ve yasal sayfalar ise ayni yaklasimi kendi bagimsiz sozlukleriyle uygular. Her arayuz kendi mimarisine gore ayri olculdu.",
      "YANLIS ALARM - KAYDA GECIRILDI: Ilk birlesik tarama tanitim ve destek sayfalarini TEK sozluge karsi olctu ve 894 eksik ceviri bildirdi. Bu olcum hataliydi: destek sayfasi tanitim sozlugunu degil kendi bagimsiz sozlugunu kullaniyor. Sayfa ile sozluk eslemesi duzeltilip iki sayfa ayri olculdugunde gercek eksik sayisi 2 cikti. Olcum aracinin varsayimi dogrulanmadan sonuc uretilmemesi gerektigi bir kez daha gorulmus oldu.",
      "BULUNAN 1 - TANITIM SITESI `gk.veya`: Giris ve kayit secenekleri arasindaki ayirac metni Ingilizce sozlukte tanimli degildi. Ingilizceye gecildiginde ekranda Turkce veya kelimesi kaliyordu. `or` olarak eklendi.",
      "BULUNAN 2 - DESTEK SITESI ARAMA KUTUSU: Yer tutucu metni Ingilizce kipte Turkce kaliyordu. Ceviri metni zaten yazilmisti; sorun anahtar bicimiydi. Destek sayfasinin ceviri islevi nitelik anahtarlarini basina @ ekleyerek saklar ve okur, ancak sozlukte yalnizca @ suz surum tanimliydi. Nitelik surumu eklendi; mevcut kayit baska bir yol tarafindan kullaniliyor olabilecegi icin bozulmadan birakildi.",
      "BULUNAN 3 - APP GECMIS DUGMESI: Dron islemler menusundeki gecmis dugmesi Turkce arayuzde History olarak goruluyordu. Ayni grubun komsu dugmeleri (Telemetri, Log Yonetimi) ve grup basligi (IZLEME VE KAYIT) Turkce oldugu icin bunun bilincli bir terim karari degil ceviri atlamasi oldugu belirlendi. Pencerenin sistemdeki adi Gecmis Yoneticisi oldugundan terim birligi kurularak Gecmis yazildi; Ingilizce sutunu zaten dogruydu.",
      "APP SOZLUGU TEMIZ CIKTI: Anahtar dengesi tamdi (TR ve EN esit). Iki dilde ayni metni tasiyan 76 kayit tek tek incelendi; 75 i bilincli karardir. Havacilik ve MAVLink terimleri (ARM CHECK, ARMED, DISARM, Failsafe, Takeoff, Return Home, SmartRTL, CIRCLE, FBWA), kisaltmalar (GPS, BAT, UID, CPU, RAM, PID, SNR, VTOL), protokol adlari (RTSP, MJPEG, HLS) ve modul adlari cevrilmemelidir; cevrilirse Mission Planner ile terim birligi kirilir.",
      "DERIN TARAMA - IC ICE SOZLUKLER: Duz anahtar taramasi ic ice nesne sozluklerini goremez. Sozluk agaci ozyinelemeli gezilerek yaprak duzeyinde karsilastirildi: 1969 Turkce yaprak, 1969 Ingilizce yaprak, iki yonde de sifir eksik. Radar hedef tipleri alt sozlugunun tam cevrildigi dogrulandi (INSAN/HUMAN, ARAC/VEHICLE, DRON/DRONE, KUS/BIRD, KLUTTER/CLUTTER). Ayni kalan bes yaprak GPS fix kisaltmalaridir (2D, 3D, DGPS, RTK-F, RTK) ve cevrilmemeleri dogrudur.",
      "YASAL SAYFALAR TEMIZ: KVKK, Gizlilik, Kullanim ve Cerez sayfalarinin dordunde de HTML anahtarlari ile Ingilizce sozluk birebir ortusuyor; eksik veya olu kayit yok.",
      "OLU KAYIT ARASTIRMASI: Tarama tanitim tarafinda 12, destek tarafinda 8 kullanilmayan kayit bildirdi. Tek tek denetlendiginde neredeyse tamami yanlis alarm cikti: bir kismi JavaScript icinden dinamik cagriliyor (giris hatasi, ag hatasi, sifre uyusmazligi gibi), bir kismi belge basligi ve meta aciklamasi icin kullaniliyor, bir kismi ise data-i18n-title niteligiyle baglanıyor ve tarama araci bu nitelige bakmiyordu. Silinen kayit olmadi.",
      "OLCUM ARACI DUZELTMESI: Sozluk sayimi once metin desenleriyle yapilmis ve uc farkli sonuc uretmisti. Neden, tirnakli anahtarlar ve ayni satirda tanimlanan ikinci anahtarlarin desenden kacmasiydi. Sozluk gercek bir tarayici ortaminda calistirilarak okundu; boylece sayim tartismasi kapandi. Bundan sonraki sozluk olcumleri calistirmali okumaya dayanacak.",
      "DOGRULAMA: Yirmi olcutluk sinav yamali ve yamasiz kaynaklarda yan yana kosuldu. Yamasiz kaynakta yalnizca yamanin degistirmedigi degerlere bagli yedi bozmama olcutu gecti; yamanin urettigi degerlere bagli olcutlerin tamami kaldi. Yamali kaynakta yirmi olcut de gecti.",
      "GERI ALMA: Uc kayit birbirinden bagimsizdir. Sozluk girdileri tek tek geri alinabilir; hicbiri baska bir metnin cozumunu etkilemez."
    ] },
  { s: "2.4.111", t: "2026-08-20",
    b: "Panel pencere basliklarinda cevrilmemis i18n anahtari gorunmesi [IS53_SURUM_v1]",
    m: [
      "BELIRTI: Rotalar ve Kameralar pencerelerinin baslik cubugunda cevrilmis metin yerine ham anahtar adi goruluyordu: `bpBaslikRotalar` ve `bpBaslikKameralar`. Kullanici bunu ekran goruntusuyle bildirdi. Panel ust bari ayni pencerelerde dogru calisiyordu (GOREV ROTALARI, KAMERA YONETIMI); kusur yalnizca pencere baslik cubugundaydi.",
      "ILK HIPOTEZ CURUTULDU: Ilk akla gelen aciklama cevirilerin eksik olmasiydi. Sozluk tarandi ve anahtarlarin UCU DE mevcut cikti: bpBaslikTespit / bpBaslikKameralar / bpBaslikRotalar hem Turkce hem Ingilizce tanimliydi. Yani sorun ceviri eksikligi degildi.",
      "KOK NEDEN - TANIMSIZ SOZLUK ADI: `bolum_popup.js` icindeki yerel `D()` islevi sozlugu `SOZLUK[AKTIF_DIL]` adiyla ariyordu. Bu iki ad sistemde hicbir yerde tanimli degil. Sinir duyarli arama tum uygulama dosyalarinda tek esleme buldu: islevin kendi satiri. Gercek adlar `DILLER` ve `aktifDil`.",
      "NEDEN SESSIZ KALDI: Ifade `typeof SOZLUK !== \"undefined\"` korumasiyla yazilmisti. Bu koruma ReferenceError atilmasini engelledigi icin konsola hicbir hata dusmuyordu; islev sessizce bos nesne donduruyor, cagiran taraftaki `|| t.pbaslik` yedegi devreye giriyor ve anahtar adi ekrana basiliyordu. Kusur bu yuzden yalnizca gorsel olarak fark edilebiliyordu.",
      "OLCULEN KANIT: Gercek i18n.js Chromium'a yuklendi ve kusurlu ifade birebir calistirildi. Olcum: typeof SOZLUK -> undefined, typeof AKTIF_DIL -> undefined, typeof DILLER -> tanimli, typeof aktifDil -> tanimli. Kusurlu ifade bos nesne dondurdu ve anahtar sorgusu null verdi; dogru ifade ayni anda ROTALAR degerini dondurdu.",
      "IKINCI KUSUR - NEDEN BUGUNE KADAR GORULMEDI: Yan yana karsilastirmali olcum, kusurun yalnizca ILK ACILISTA ortaya ciktigini gosterdi. Dil degistirildiginde applyLanguage islevinin data-i18n dongusu ayni span'i tazeliyor ve anahtari dogru cozuyor. Yani kullanici bir kez Ingilizceye gecip Turkceye donse kusur kendiliginden kapaniyordu; bu da uzun sure fark edilmemesini acikliyor.",
      "UCUNCU KUSUR - KAPAT IPUCU: Ayni bozuk islev, pencere kapatma dugmesinin ipucu metnini de besliyordu. Olcum, Ingilizce dilde bile ipucunun Turkce Kapat olarak kaldigini gosterdi. Dugmeye data-i18n-title niteligi eklendi ve bpKapat anahtari Turkce/Ingilizce olarak tanimlandi; artik dil degisiminde ipucu da cevriliyor.",
      "COZUM - DUSEN ZINCIR: Sozluk cozumu tek bir ada baglanmadi. Once islev bildirimi oldugu icin window uzerinden erisilebilen D() denenir, sonra ortak kapsamdaki DILLER/aktifDil ciftine dusulur, en sonunda bos nesne dondurulur. Ara adimlarin her biri ayri korumali; hicbir durumda cokme uretmez. Bu sayede i18n.js ileride yeniden duzenlense de baglanti kopmaz.",
      "NEDEN window.DILLER KULLANILMADI: DILLER ve aktifDil en dis kapsamda const ve let ile tanimli. Dil kurali geregi bu tur tanimlar window nesnesine yazilmaz; olcum bunu dogruladi (window.DILLER -> undefined). Buna karsilik D() bir islev bildirimi oldugundan window uzerinden erisilebiliyor. Zincirin sirasi bu olcume gore belirlendi.",
      "DOGRULAMA: Yamali ve yamasiz surumler gercek Chromium'da yan yana kosuldu. Yamasiz surumde uc pencere basligi da ham anahtar adi gosterdi; yamali surumde ROTALAR, KAMERALAR ve HEDEF LISTESI dogru cikti. Ingilizce dilde kapat ipucu Kapat yerine Close oldu.",
      "GERI ALMA: `js/bolum_popup.js` icindeki D() islevi eski haline dondurulurse davranis onceki durumuna doner; sozluge eklenen bpKapat anahtari zarasiz sekilde yerinde kalir."
    ] },
  { s: "2.4.110", t: "2026-08-20",
    b: "Tum panellerde alt durum cubugu (statusbar) ve 400x300 en kucuk pencere olcusu [IS51_SURUM_v1]",
    m: [
      "TALEP: Kullanici on panelde altta sabit bir durum cubugu istedi. Her cubukta konuya uygun bir ikon ve panele ozgu sayac bulunacak; paneller acilirken ve yeniden boyutlanirken en az 400px genislik ve 300px yukseklik koruyacak; acilista ekranin ortasinda konumlanacak.",
      "KAPSAM - 10 PANEL: Baglanti Yoneticisi (Baglanti Sayisi : T/A), Gecmis Yoneticisi (Ucus Sayisi : T/F), Kameralar (Kamera Sayisi : T/A), Rotalar (Rota Sayisi), Kayitli Lokasyonlar (Lokasyon Sayisi), AI Sunucular (Sunucu Sayisi : T/A), Kisiler (Toplam Kisi + Toplam Yuz), Araclar (Toplam Arac Sayisi), Kayitsiz Tespitler (Toplam Tespit Sayisi), Tespit Gecmisi (Toplam Tespit Sayisi : T/F).",
      "YAKLASIM - DOM TABANLI SAYIM: Sayaclar ayri bir veri katmanindan degil, panelin kendi listesinden sayilir. Boylece sayac ile ekranda gorunen kayit her zaman ayni olur; iki ayri dogruluk kaynagi olusmaz. Bos panel yer tutucusu (`.bos-panel`) sayim disinda birakilir; aksi halde kayit yokken sayac 1 gorunurdu.",
      "GUNCELLEME - MutationObserver: Her panelin kayan kabi izlenir. Liste degistiginde sayac kendiliginden tazelenir; her cizim noktasina elle cagri eklemeye gerek kalmaz. Tazeleme requestAnimationFrame ile birlestirilir, ardarda gelen degisikliklerde tek sefer hesaplanir.",
      "KOK NEDEN - FLEX MIN-HEIGHT TUZAGI: Serit kaba eklenince Baglanti Yoneticisinde panelin ALTINDAN TASIYORDU. Olculen deger: serit alt kenari kabin 723px asagisindaydi. Neden, govde ogesinin (`.yuzen-icerik`) yalnizca `flex: 1 1 auto` tasimasi; flex ogesinin varsayilan `min-height: auto` degeri ogenin ICERIK yuksekliginin altina inmesini engelliyor, dolayisiyla govde kuculmuyor ve serit disari itiliyordu. `min-height: 0` eklenerek kisitlama kaldirildi. Ayni koruma `.bolum-popup-govde` ve `.ai-popup-icerik` icin de uygulandi.",
      "KOK NEDEN - KAYAN KAP: Kayitli Lokasyonlar penceresinde kabin KENDISI kayiyordu (`overflow-y:auto`). Kap kayinca serit de icerikle birlikte kayip gorunumden cikiyordu. Kaydirma kaptan alinip liste ogesine devredildi; kap dikey flex kutusu yapildi.",
      "YANLIS HIPOTEZ - KAYDA GECIRILDI: Gunduz kipi kurallari once `body.acik-tema` secicisiyle yazildi; bu secici sistemde birkac yerel kuralda gectigi icin dogru varsayilmisti. Chromium olcumu bu varsayimi CURUTTU: secici eklendiginde serit rengi koyu kaldi. Gercek acik tema anahtari `:root[data-tema=\"acik\"]`. Kural bu seciciye tasindi ve olcumle dogrulandi.",
      "OLCU SOZLESMESI: Dok pencerelerinin en kucuk olcusu 320x200'den 400x300'e cikarildi (`css/pencere_dok.css`). Yeniden boyutlama alt siniri 220x140'tan 400x300'e cekildi (`js/popup_tasima.js`). Acilis olcusu (500x400) ve ortalama davranisi zaten sozlesmeye uygundu; degistirilmedi.",
      "GORSEL SOZLESME: Serit yuksekligi 26px. Arka plan `--panel`, ust cizgi `--cizgi`, metin `--soluk`, ikon `--vurgu` degiskenlerinden gelir. SABIT RENK KULLANILMADI; gece ve gunduz kipleri ayri ayri olculdu (gece rgb(11,14,17) / gunduz rgb(242,244,247)).",
      "DIL: 10 sayac icin `sb*` anahtarlari Turkce ve Ingilizce olarak eklendi. Dil degistiginde serit metinleri kendiliginden yenilenir.",
      "DOGRULAMA: Uc katmanli sinav yapildi. (1) Statik sinav 80/80 gecti; kontrol deneyi olarak yamasiz kaynak ayni sinava sokuldu ve beklendigi gibi kaldi. (2) jsdom islevsel sinavi 20/20 gecti; on sayacin tamami bilinen veri kumesiyle dogrulandi. (3) Gercek Chromium ile piksel olcumu yapildi: serit alt bosluk farki 1.0px (kabin kenarligi), govde 1266px kaydirildiginda serit kaymasi 0px, ikonlar Font Awesome ile cizildigi ekran goruntusuyle dogrulandi.",
      "GERI ALMA: `panel_durumcubugu.css` ve `panel_durumcubugu.js` baglantilari `index.html` icinden kaldirilirsa seritler tamamen kalkar; olcu sinirlari icin `pencere_dok.css` ve `popup_tasima.js` eski degerlerine dondurulur."
    ] },
  { s: "2.4.109", t: "2026-08-20",
    b: "Baglanti/kamera pencerelerinde mor-pembe renk blogu ve KAYDET/IPTAL dugmelerinin ekran disinda kalmasi [IS50_SURUM_v1]",
    m: [
      "BELIRTI 1 - RENK: Yeni TCP Baglanti penceresinde SUNUCU ADRESI ve PORT alanlarinin arkasinda tema disi MOR blok goruluyordu. Yeni Kamera penceresinde ayni sorun PEMBE olarak ortaya cikiyordu. Kullanici bunu ekran goruntusuyle bildirdi.",
      "BELIRTI 2 - DUGME: KAYDET ve IPTAL dugmeleri pencere govdesinin en altinda, icerigin pesinden akiyordu. Form uzadiginda veya pencere kucultuldugunde dugmeler gorunum disina tasiyor, kullanici kaydirmadan kaydedemiyordu.",
      "KOK NEDEN 1 - SINIF ADI CAKISMASI: `bag-tur-tcp`, `bag-tur-dji`, `bag-tur-seri`, `bag-tur-udp`, `bag-tur-sanal` sinif adlarinin her biri IKI AYRI amacla kullaniliyordu. Birincisi baglanti listesindeki kucuk renkli ROZET (9px etiket) - bu kasitli ve dogru. Ikincisi form icindeki GORUNURLUK KABI - protokole gore alan grubunu gosterip gizlemek icin. Rozet icin yazilan arka plan rengi, 332x195 piksellik form kabina da uygulaniyordu.",
      "OLCULEN KANIT 1: Gercek Chromium ile canli DOM olculdu. Yamasiz surumde 6 form kabindan 5\'i renkliydi: bag-tur-seri rgba(59,130,246,.18), bag-tur-tcp rgba(168,85,247,.18) MOR, bag-tur-udp rgba(34,197,94,.18), bag-tur-sanal rgba(245,158,11,.20), bag-tur-dji rgba(236,72,153,.18) PEMBE. Olculen mor ve pembe degerleri kullanicinin ekran goruntusuyle birebir ortusuyordu.",
      "YANLIS HIPOTEZ - KAYDA GECIRILDI: Ilk teshis tarayici otomatik doldurma (`:-webkit-autofill`) rengiydi; CSS taramasinda hicbir dosyada autofill kurali bulunmamasi bunu destekliyor gorunuyordu. Ancak tarayici olcumunde otomatik doldurma HIC tetiklenmedigi halde renk yine goruldu; hipotez bu olcumle curutuldu ve gercek neden sinif cakismasi olarak saptandi.",
      "ONARIM 1: Rozet secicileri `.bag-tur-tcp` yerine `.bag-tur.bag-tur-tcp` bicimine daraltildi (5 secici). Boylece renk yalnizca `bag-tur` temel sinifini DA tasiyan roze uygulanir; form kabi etkilenmez. Rozet ureten uc kod noktasinin ucu de `bag-tur` onekini yazdigi icin gorsel gerileme olusmaz - bu ayrica sinavla dogrulandi.",
      "KOK NEDEN 2 - YAPI: Dugme satiri (`lok-dugme-satir`) pencere govdesinin (`bolum-popup-govde`) ICINDE, normal icerik akisinin son ogesi olarak duruyordu. Govde `overflow:auto` ile kayiyor, dolayisiyla dugmeler de icerikle birlikte kayip gorunum disina cikiyordu. Pencere kutusu `display:flex; flex-direction:column` sozlesmesini uygulamadigi icin dugmeler CSS ile alta sabitlenemiyordu.",
      "ONARIM 2: `js/pencere_iskelet.js` eklendi. Bu betik pencere acilirken dugme satirini govdeden CIKARIP kutunun dogrudan cocugu yapar; kutuya sutun yerlesimi, govdeye `flex:1 1 auto` ve `min-height:0` verir. Boylece govde kendi icinde kayar, dugme seridi her zaman kutunun en altinda kalir. Serit tam donuk arka plan ve ust cizgi alir; altindan icerik gorunmez.",
      "KAPSAM: bagEkleKutu (baglanti ekle), lokKaydetKutu (lokasyon kaydet), kamModalKutu (kamera ekle), spiralModalKutu (spiral rota). Dordu de olculdu ve dogrulandi.",
      "EK - AUTOFILL: Ilk hipotez curutulmus olsa da tarayici otomatik doldurma rengi gercek bir risk oldugu icin koruyucu kural yine de eklendi. Inset box-shadow teknigiyle tema degiskenine baglandi; sabit renk kullanilmadi.",
      "DOGRULAMA: Gercek Chromium ile piksel olcumu yapildi - statik CSS denetimiyle yetinilmedi. 33 maddelik sinav CANLI SISTEM uzerinde 33/33 gecti. Dugme yerlesimi dort ayri gorunum boyutunda olculdu (1280x900, 1280x600, 1400x1000, 900x520); dugme-kutu alt bosluk farki 0.0px cikti, yani yerlesim boyuttan TAMAMEN bagimsiz. Govdenin gercekten kaydigi da olculdu (2132px icerik / 381-803px gorunen). Gece ve gunduz kipleri ayri ayri sinandi.",
      "KONTROL DENEYI: Yamasiz surum ayni sinavdan 21 maddede kaldi ve kullanicinin bildirdigi iki kusuru birebir uretti (5 renkli kap, dugme tasmasi). Ayirt edicilik 5 -> 33.",
      "GERI ALMA: `pencere_iskelet.js` script etiketi kaldirilirsa dugme yerlesimi eski haline doner. Rozet secicilerindeki `.bag-tur` oneki kaldirilirsa renk davranisi eski haline doner."
    ] },
  { s: "2.4.108", t: "2026-08-20",
    b: "Sayfa yenilendiginde kopru listesi bos geliyordu (jetonla giriste firma kimligi kaybi) [IS49_SURUM_v1]",
    m: [
      "BELIRTI: Kamera ekleme ve TCP baglanti ekleme pencerelerinde \'Cevrimici kopru yok\' goruluyordu. Kopru yazilimi \'merkez: bagli\' ve \'Merkez ajani BAGLI\' dese bile liste bos kaliyordu. Belirti YALNIZ sayfa yenilendikten (F5) sonra ortaya cikiyordu; parola ile taze giris yapildiginda liste DOGRU doluyordu.",
      "KOK NEDEN: Yerel `kullanicilar` tablosunda `firma_id` KOLONU BULUNMUYOR. Sayfa yenilendiginde oturum jeton ile aciliyor ve `_jeton_dogrula` kullaniciyi bu yerel tablodan cozuyor; sonucta firma kimligi hicbir zaman dolmuyordu. Is 44 ile eklenen merkez geri dusus yolu ise yalnizca yerel kayit BULUNAMADIGINDA devreye giriyordu. Kullanicinin yerel kaydi VAR oldugu icin o yol hic calismiyordu.",
      "ZINCIR: firma_id bos -> `_ws_firma[id(websocket)]` yazilmiyor -> `kopru_liste` komutu `_ws_firma_id` cozemiyor -> istek \'Oturum gerekli.\' hatasiyla BOS donuyor -> arayuz `bagKopruler` dizisini bos buluyor -> secici \'Cevrimici kopru yok\' gosteriyor.",
      "OLCULEN KANIT: Canli sunucuya gecici tani gunlugu eklendi ve kullanicinin kendi istegi yakalandi. Yakalanan kayitta `eposta` DOLU (mkaderoglu@gokkubbetech.com) ancak `firma_id` None idi. Ayrica gunlukteki iki farkli ad kaydi iki ayri kimlik kaynagini ele veriyordu: jeton yolu yerel tablodan (`Muhammed Kaderoglu`), parola yolu merkezden (`Muhammed Kadedoglu`) cozuyordu.",
      "ONARIM: `_jeton_dogrula` artik yerel kayit BULUNSA BILE firma kimligi eksikse merkezden tamamliyor. Boylece jetonla acilan oturum ile parolayla acilan oturum ayni firma baglamina sahip oluyor.",
      "GUVENLIK - SECICI BIRLESTIRME: Merkez kaydi `dict.update()` ile TOPLU birlestirilmedi. Toplu birlestirme bir YETKI GERILEMESI yaratiyordu: yerelde `aktif=0` yapilmis (yonetici tarafindan pasiflestirilmis) bir hesap, merkezdeki `aktif=1` degeriyle ezilerek jetonla GIRIS YAPABILIYORDU. Ayni sekilde `rol` alani ezildiginde yerel yetki kisitlamasi gecersiz kalirdi. Bu gerileme sinav sirasinda yakalandi ve yayina cikmadan giderildi.",
      "TASINAN ALANLAR: firma_id, firma_unvan, firma_kisa_ad, kullanici_id, merkez_rol. TASINMAYAN ALANLAR: aktif, rol, sifre, ad_soyad. Yerel kayittaki yetki ve durum bilgisi HER ZAMAN onceliklidir.",
      "DOGRULAMA: Gercek `_jeton_dogrula` metodu kaynak koddan AST ile ayiklanip calistirildi (metin aramasi degil). 25 maddelik sinav yamali surumde 25/25 gecti. KONTROL DENEYI: yamasiz surum ayni sinavdan 7 maddede kaldi ve kullanicinin gordugu bos liste durumunu birebir uretti. Yetki sinirlarinin korundugu ayrica olculdu - pasif hesap yamadan SONRA da giris yapamiyor.",
      "GERI ALMA: Tamamlama blogu kaldirilarak onceki davranisa donulebilir; yerel kayit yolu degistirilmedi."
    ] },
  { s: "2.4.107", t: "2026-08-20",
    b: "Cevrimici kopru merkez arayuzunde gorunmuyordu (cift baglanti kisir dongusu)",
    m: [
      "BELIRTI: Kopru yazilimi \'merkez bagli\' ve \'Merkez ajani BAGLI\' diyordu, ancak merkez arayuzunde \'Cevrimici kopru yok\' gorunuyordu. Belirtinin iki tarafi da ayni kok nedenden kaynaklaniyordu.",
      "KOK NEDEN: Ayni kopru merkeze IKI FARKLI YOLDAN baglanabiliyor - `wss://sunucu` (443 portu, ic tunel uzerinden) ve `wss://sunucu:9443` (dogrudan). Kopru kayit defteri (`RoleYoneticisi.ekle`) ayni `kurulum_uid` ile gelen ikinci baglantida eskisini KOSULSUZ dusuruyordu. Dusen taraf 3 saniyelik yeniden baglanma gecikmesiyle geri gelip bu kez otekini dusuruyordu: sonsuz kisir dongu.",
      "SONUC: Veritabanindaki `cevrimici` bayragi saniyeler icinde TRUE ve FALSE arasinda salinim yapiyordu. Arayuz paneli acildiginda cogunlukla FALSE anina denk geliyor ve \'Cevrimici kopru yok\' gosteriyordu. Kopru tarafi ise her 3 saniyede yeni bir `merhaba_tamam` aldigi icin kendini BAGLI sayiyordu.",
      "OLCULEN KANIT: Tek kurulum icin 44 oturum kaydi bulundu, 27\'sinde bitis damgasi yoktu. Ardisik oturumlarin biri kapanirken digeri AYNI SANIYEDE aciliyordu (21:18:14-21:18:47 ile 21:18:47 baslangicli kayit). Oturumlarin bir bolumu `127.0.0.1` (tunel), bir bolumu gercek dis IP (dogrudan port) kaynakliydi.",
      "ONARIM: Kayit defteri artik CANLI oturumu korur. Ayni kurulum icin ikinci baglanti geldiginde eski oturumun son nabzi 45 saniye icindeyse yeni baglanti REDDEDILIR; kopruye `zaten_bagli` yaniti gonderilir ve kopru kendi ustel geri cekilmesine (3-6-12-24-48-60 saniye) doner. ILK baglanti kesintisiz kalir.",
      "GERIYE DONUK UYUMLULUK: Eski oturum gercekten olmusse (nabiz eskimis) onceki davranis surer - eskisi dusurulur, yenisi kabul edilir. Boylece kopru yeniden baslatildiginda olu kayit birikmez ve komutlar olu sokete gitmez.",
      "KAPSAM: Onarim hem merkez sunucu kayit defterine hem de Merkez Uygulamasi\'nin kendi bagimsiz kopru kabul katmanina uygulandi; kapali devre kurulumlar da ayni kisir donguden etkileniyordu.",
      "DOGRULAMA: Kayit defteri davranisi gercek nesnelerle 20 maddelik sinavla olculdu; kontrol deneyi yamasiz kodda ayirt ediciydi. Ayrica canli sistemde gercek WebSocket ile uctan uca dogrulama yapildi: ikinci oturum reddedildi, ilk oturumun kanal kimligi degismedi ve soketi nabiz alip vermeye devam etti.",
      "GERI ALMA: Koruma suresi sifirlanarak onceki davranisa donulebilir."
    ] },
  { s: "2.4.106", t: "2026-08-19",
    b: "Baglanti baslatilamiyordu: \'Oturum bilgisi henuz yuklenmedi\' (soket basina oturum tuzagi)",
    m: [
      "KOK NEDEN: `_ws_firma` sozlugu `id(websocket)` ile anahtarlanir, yani OTURUM BILGISI SOKET BASINA tutulur. Arayuz ayni anda birden fazla WS soketi acabiliyor (ucus duvari, video duvari, ikinci sekme, yeniden baglanma). Jeton girisi yapan soket ile `baglanti_baslat` komutunu gonderen soket FARKLI oldugunda, komutu alan sokette firma kimligi bulunmuyordu.",
      "Canli gunluk kaniti: `[AUTH] Jeton ile giris` satirindan SONRA hata geliyordu. Yani bu bir ZAMANLAMA YARISI degildi - kullanicinin \'birkac saniye bekleyip yeniden deneyin\' onerisini uygulamasi ise yaramiyordu, cunku bekleme sorunu cozmuyordu.",
      "Veri tarafi olculdu ve SAGLAMDI: kullanici kaydi firma_id=14, CAYMAZ baglanti kaydi firma_id=14 ve kopru_ornek_id dolu. Kusur tamamen oturum cozumleme yolundaydi.",
      "ONARIM 1 - `_ws_firma_id`: sozlukte deger yoksa AYNI SOKET icin tutulan pilot kaydindan (`_ws_pilot`) firma kimligi turetilir ve onbellege yazilir. Pilot kaydi jeton dogrulamasinda dolduruluyordu; iki sozluk arasindaki bu bosluk kok nedenin ta kendisiydi.",
      "ONARIM 2 - `_kopru_ornek_coz`: oturum yine cozulemezse baglanti KAYDININ kendi firma_id alanina duser. Kayit zaten bir firmaya ait oldugu icin bu bilgi guvenilir.",
      "YETKI SINIRI GENISLEMEDI: geri dusus yalnizca HANGI firmanin kopru listesine bakilacagini belirler; `firma_kopruleri(_fid)` dogrulamasi korunur. Sinavla olculdu - kayit baska firmaya aitse baglanti REDDEDILIYOR ve yetki sorgusu o firmayla yapiliyor.",
      "Sinav: gercek kaynak koddan iki metod AST ile ayiklanip CALISTIRILDI (metin aramasi degil), sahte soketlerle 12 sinav. Yamali surum 12/12 gecti. KONTROL DENEYI: yamasiz surum ayni sinavdan 6/12 kaldi ve kullanicinin gordugu hata metnini birebir uretti.",
      "Eski hata metni KORUNDU: kayitta da firma_id yoksa ayni uyari doner. Sessiz basarisizlik olusturulmadi."
    ] },
  { s: "2.4.105", t: "2026-08-19",
    b: "MAVLink baglantisi ~3 dakikada kopuyordu (CUAV LTE Link SE): GCS heartbeat, TCP keepalive ve otomatik yeniden baglanma",
    m: [
      "KOK NEDEN: GOKTUNGU MAVLink baglantisinda GCS HEARTBEAT GONDERMIYORDU. Tum kod tabaninda tek bir heartbeat_send cagrisi yoktu; baglanti tamamen tek yonluydu (dron konusuyor, GCS susuyor). Saha kaniti: ayni TCP uc noktasina baglanan Mission Planner kalici kalirken GOKTUNGU ~3 dakikada kopuyordu. Aradaki TEK fark MP'nin saniyede 1 heartbeat yollamasiydi.",
      "Giden trafik zaman cizelgesi olculdu: t=0-1 sn REQUEST_DATA_STREAM + 3x SET_MESSAGE_INTERVAL + REQUEST_MESSAGE, t=0-15 sn en fazla 5x AUTOPILOT_VERSION istegi, t>15 sn HICBIR SEY. Kullanici komut vermezse soket ~15. saniyeden sonra tamamen sessizlesiyordu. CUAV LTE Link SE gibi mobil hatlarda operator NAT tablosu ve modem oturum yoneticisi veri gondermeyen istemciyi 120-300 sn icinde dusurur; kullanicinin gozledigi ~3 dakika bu araliga tam oturuyor.",
      "COZUM A - GCS heartbeat: ana okuma dongusu icinden saniyede 1 kez MAV_TYPE_GCS + MAV_AUTOPILOT_INVALID heartbeat gonderiliyor. AYRI THREAD KULLANILMADI: mavutil nesnesi thread-guvenli degildir, ayni sokete iki thread'den yazmak MAVLink cercevelerini ic ice gecirir ve karsi taraf paketleri cope atar. Dongu recv_match(timeout=1.0) ile zaten saniyede en az bir kez uyandigi icin ek thread gereksizdi.",
      "MAV_AUTOPILOT_INVALID bilincli secildi: bir yer istasyonu otopilot degildir. ArduPilot bu birlesimi gorunce gondereni GCS olarak tanir ve GCS failsafe sayacini sifirlar; baska bir otopilot kimligi bildirmek ucus denetleyicisinin baglantiyi ikinci bir arac sanmasina yol acardi.",
      "COZUM B - TCP keepalive: SO_KEEPALIVE + TCP_KEEPIDLE(30) / TCP_KEEPINTVL(10) / TCP_KEEPCNT(3). Heartbeat uygulama katmanindadir ve yalniz ucus denetleyicisine ulasir; keepalive ise ARA KATMANLARI (LTE modem, operator NAT, yonlendirici) hedefler. Ikisi farkli sorunlari cozer, biri digerinin yerini tutmaz. TCP_KEEP* sabitleri Linux'a ozgudur ve Windows'ta AttributeError firlatir; kopru yazilimi Windows'ta da calistigi icin her secenek AYRI try blogunda korunur. Seri (USB) ve UDP baglantilarda sessizce atlanir.",
      "COZUM C - otomatik yeniden baglanma: onceki davranista _dongu tek gecisliydi, baglanti dustugunde thread sonlaniyor ve kullanici arayuzden elle 'play'e basana kadar telemetri geri gelmiyordu. Artik gecikme 2 sn'den baslayip her denemede iki katina cikar ve 30 sn'de tavan yapar.",
      "KULLANICI IRADESI KORUNDU: kullanici 'stop' derse yeniden BAGLANILMAZ. Otomatik yeniden baglanmanin durdurma istegini ezmesi, sahada denetimi kaybettiren bir kusur olurdu. Bekleme time.sleep() yerine durdur.wait() ile yapilir; aksi halde kullanici 'stop' dediginde 30 saniyeye kadar beklenirdi (olculdu: stop tepkisi 0.00 sn).",
      "Yama TEK noktada: sistemdeki tum MAVLink baglantilari dron.py:1127'den geciyor (sitl.py, takip_dron.py, suru.py kendi baglantilarini acmiyor). Seri, UDP ve TCP baglantilarinin tamami ayni dongude oldugu icin heartbeat duzeltmesi hepsini birden kapsar - MAVLink sozlesmesinde GCS her tasima katmaninda heartbeat yollar.",
      "DAVRANIS SINAVI (statik denetim degil): yamalanmis modul gercekten yuklendi, sahte pymavlink ile dongu calistirildi ve gonderilen paketler sayildi. 22/22 gecti - heartbeat 3.4 sn'de 4 adet (ortalama aralik 1.00 sn), gercek TCP soketinde getsockopt ile keepalive degerleri okundu, yeniden baglanma gecikmesi 2.05 -> 4.05 sn olculdu. KONTROL DENEYI: yamasiz surumde 0 heartbeat olculdu ve sinav kaldi, boylece kok neden tanisi deneysel olarak dogrulandi."
    ] },
  { s: "2.4.104", t: "2026-08-19",
    b: "Rotalar paneli: baslik yinelemesi, dugme tasmasi, rota menu adlari ve ust bar rota dugmeleri",
    m: [
      "Baslik yinelemesi kok nedeni: bolum_popup.js popup baslik cubugunu `bas` ogesinden kopyaliyordu. tespit/kameralar/rotalar bolumlerinde `bas` bir PANEL UST BARI'dir ve IS 18 sozlesmesinden beri `.tb-baslik` degil `.tb-etiket` sinifi tasir. querySelector null donuyor, yedek dal (|| bas) tum toolbar'i kaynak sayiyordu; sonuc ust bar etiketi ile pencere basliginin AYNI metni gostermesiydi.",
      "Cozum secici duzeltmesi DEGIL, kayit alani: BOLUMLER kaydina `pbaslik` (pencere basligi i18n anahtari) eklendi. Sadece secici .tb-etiket yapilsaydi yineleme SURECEKTI - ayni metin iki yerde gorunmeye devam ederdi. Yeni anahtarlar: bpBaslikTespit / bpBaslikKameralar / bpBaslikRotalar.",
      "takip bolumu bilincli olarak DEGISTIRILMEDI: onun `bas` ogesi takipBaslik h2'sidir, yani gercek pencere basligi. Ona `pbaslik` verilseydi mevcut dogru davranis bozulacakti.",
      "Dugme tasmasi: tbYeniRota `tb-btn` kare kalibindaydi (30x30, yalniz-ikon) ama metin tasiyordu. panel_ustbar.css:88'deki `tb-btn-metin` kurali eklendi; yeni CSS YAZILMADI, mevcut sozlesme kullanildi. Kameralar toolbar'indaki uc dugme bu sinifa zaten sahipti - tutarsizlik giderildi.",
      "Menu adlari: Yeni Rota -> Serbest Rota (TR) / Free Route (EN), Serbest Form -> Dilimli Rota (TR) / Sliced Route (EN). Oge kimlikleri (mbYeniRota, mbSerbestForm) KORUNDU: menubar.js:122 ve serbest_form.js:536 bu kimliklere bagli.",
      "Ust bara dort rota dugmesi eklendi (Spiral, Dilimli, Koridor, Rota Yukle) + mevcut Serbest Rota. Olcum: spiral ve rota yukle icin GLOBAL islev YOK (window.spiral* / window.rotaYukle* 0 eslesme), yalniz menu dinleyicisi var. Bu yuzden dugmeler ilgili menu ogesinin .click()'ini tetikliyor; rota olusturma kodu kopyalanmadi ve tek tetikleyici yolu korundu.",
      "Rota Yukle ikonu fa-file-import -> fa-folder-open (klasor ac). Ust bar dugmesi de ayni ikonu kullanir."
    ] },
  {"s": "2.4.103", "t": "2026-08-19", "b": "SITL sanal dron sihirbazi panel yerine modalde aciliyor; sanal dron ekleme yeniden calisiyor.", "m": ["KOK NEDEN (tarayici olcumuyle dogrulandi): `.bag-tur-sanal` sinifi DOM'da IKI yerde geciyor - (a) panel listesindeki SANAL rozeti (seri.js:959, DOM'da satir 677'de ONCE gelir), (b) modaldeki sanal form blogu (index.html:767, satir 689). Sihirbaz `document.querySelector` kullandigi icin DOKUMANDA ILK eslesmeyi buluyordu, yani panel rozetini. Sarmal `#bagListe` icine kuruluyordu.", "Tarayici kaniti: SARMAL zincir = DIV.bag-ust < DIV.bag-bilgi < DIV.bag-satir < DIV.bag-grup < DIV#bagListe. Sihirbaz `#bagEkleKutu` (modal) icinde DEGILDI. Kullanicinin gordugu 'sihirbaz panelin icinde aciliyor, dar alanda kirpiliyor' belirtisinin sebebi tam olarak bu.", "'Sanal dron ekle calismiyor' AYRI bir kusur DEGIL, ayni kok nedenin ikinci belirtisi: sihirbaz panele kuruldugu icin modalde ne ILERI ne KAYDET dugmesi kaliyordu. Olcum: KAYDET display=none, bag-tur-sanal display=none. 'YENI SANAL DRON' penceresi bu yuzden dugmesiz ve islevsizdi.", "COZUM: arama MODAL KAPSAMINA daraltildi - `sanalFormBlok()` yardimcisi `#bagEkleKutu` icinde ariyor. Uc kullanim yerinin tamami degistirildi (satir 144, 329, 612). Panel rozetine DOKUNULMADI: mesru bir oge ve sinif adi CSS'te kullaniliyor.", "Sessiz basarisizlik kapatildi: kur() modal blogunu bulamazsa konsola teshis izi birakiyor. seri.js'teki bos `catch` blogu da iz birakacak sekilde degistirildi. Sessiz yutma, bu kusurun gunlerce teshis edilememesinin dogrudan sebebiydi.", "Guvenli dusus: sihirbaz kurulamazsa modal duz kipte kullanilabilir kalir (KAYDET ve form gorunur), boylece sanal dron ekleme hicbir kosulda tamamen bloke olmaz.", "Artik sarmal temizligi: onceki surumde panel listesine kurulmus `#swSarmal` DOM'da kalmis olabilir; kurulumdan once modal disindaki tum kopyalar kaldiriliyor.", "YONTEM NOTU: bu kusur statik kod okumasiyla bulunamazdi - secici sozdizimsel olarak dogruydu. Kok neden ancak gercek tarayicida DOM zinciri olculerek ortaya cikti. IS 16'da ayni ders alinmisti: yerlesim/kapsam kusurlarinda statik capa denetimi KANIT DEGILDIR."]},
  {"s": "2.4.102", "t": "2026-08-19", "b": "Kayitli lokasyonlar artik haritada ikon olarak gorunuyor; acilista liste bir kez istenir.", "m": ["Olcum: lokasyonlar.js icinde Cesium `entities.add` cagrisi 0 kez geciyordu. Modul panel satirini ciziyor ve kamerayi ucuruyordu, ancak haritaya HIC ikon eklemiyordu. Sistemde ikon cizen 13 dosya var; lokasyonlar.js listede yoktu. Bu bir regresyon degil, hic yazilmamis islevdi - prizma ikonu kaldirma isiyle ilgisi yok.", "Ikon canvas'ta uretiliyor (harici gorsel dosyasi yok): saha kurulumlari internetsiz calisir. Desen home_ikon.js'ten alindi, yeni tasarim uydurulmadi.", "Acilista `lokasyon_liste` istegi eklendi. Olcum: istek yalniz Lokasyonlar veya Kameralar paneli acilirsa gidiyordu; bu yuzden ikon cizimi eklense bile panel acilmadikca harita bos kalirdi.", "Listeden dusen lokasyonun ikonu siliniyor. Eski konumda igne birakmak, silinmis bir lokasyonun hala kayitli oldugu izlenimi verirdi.", "Sifir-koordinat kapisi (2.4.93 sozlesmesi) uygulandi: (0,0), null ve aralik disi koordinatlar ikon uretmez. Kapinin govdesi degistirilmedi - dort dosya ona bagli.", "Tema degisiminde ikon gorseli yeniden uretiliyor (tema.js kancasi).", "Cetvel nokta ikonu icin yama YAZILMADI: olculdu, kodda mevcut ve `point` grafigi kullandigi icin prizma yolundan bagimsiz. Olculmus kusur yok."]},
  { s: "2.4.101", t: "2026-08-19",
    b: "Konum çözümü yokken sebebin gösterilmesi",
    m: [
      "Dron kartı başlık özetine konum durumu göstergesi eklendi. Sıfır-koordinat kapısı (v2.4.93) geçersiz konumda haritada ikon çizmiyordu ancak kullanıcıya sebep gösterilmiyordu; 'dron bağlı ama ikon gelmiyor' şikâyetinin teşhis edilebilirliği bu yüzden yoktu.",
      "GPS henüz kilitlenmemişse (fix 0/1) 'GPS BEKLENİYOR (uydu: N)', GPS kilitli olduğu hâlde konum geçersizse 'KONUM YOK (EKF çözümü bekleniyor)' yazılıyor. Konum geldiğinde gösterge kendini gizler.",
      "Gösterge sunucudan hâlihazırda gelen gps_fix ve uydu alanlarını kullanıyor; yeni sunucu alanı eklenmedi.",
      "gecerliKonumMu() kapısı bilinçli olarak DEĞİŞTİRİLMEDİ: dört dosya (dronlar.js, harita.js, hedefler.js, home_ikon.js) bu işleve bağlı ve davranışı değişirse v2.4.93 sıfır-koordinat düzeltmesi bozulur.",
      "i18n bakımı: dkUydu anahtarı zaten tanımlıydı; yamanın eklediği yinelenen ikinci tanım kaldırıldı. Yinelenen anahtar görünür bir kusur üretmiyordu ancak biri değiştirildiğinde diğerini sessizce ezme riski taşıyordu."
    ] },
  { s: "2.4.100", t: "2026-08-19",
    b: "Uçuş Duvarı gece/gündüz düğmesi ve oturum teması",
    m: [
      "Uçuş Duvarı üst çubuğuna gece/gündüz geçiş düğmesi eklendi. Üst çubuk dar olduğu için ana uygulamadaki iki ayrı düğme yerine tek geçişli düğme kullanıldı; ikon duruma göre ay/güneş olarak değişir.",
      "Uçuş Duvarı artık sunucudan gelen tema tercihini okuyor. Önceki sürümde mesaj işleyicisi telemetri dışındaki tüm mesajları erken dönüşle attığı için tema bilgisi hiç ulaşmıyordu; ayarlar dalı telemetri denetiminden önce eklendi ve telemetri sıcak yolu korundu.",
      "Tema tercihi sunucu tarafı kullanıcı ayarına yazılıyor (ana uygulamayla aynı mesaj biçimi). Böylece tercih tüm panellerde ortak hatırlanıyor.",
      "flight.css tek temalı yazılmıştı; 19 sabit renk ve 27 saydam renk tema değişkenlerine çevrildi, açık tema ezmeleri eklendi.",
      "PFD uçuş göstergesi paleti bilinçli olarak korundu: mavi gök / kahverengi yer / beyaz ufuk çizgisi havacılık gösterge standardıdır ve açık zeminde okunamaz. Canvas kendi zeminini çizdiği için açık temada da kokpit görünümü bozulmaz."
    ] },
  { s: "2.4.99", t: "2026-08-19", b: "Dron kart ve dugme duzeltmeleri",
    m: [
      "IS27: Ikon ve metin tasiyan 53 dugmede metin <span> icine sarildi. Dugme birligi sozlesmesindeki yalniz-ikon kurali (:has(> i):not(:has(> span))) bu dugmeleri 26px kareye ve padding:0'a zorluyordu; KAYDET, GONDER, TAKEOFF'U TAMAMLA gibi metinler kutunun disina tasiyordu. CSS ezilmedi, sozlesmeye uyuldu; yalniz-ikon dugmelerin 26px kare gorunumu korundu",
      "IS28: Dron haberlesme konsolunda ham Unix zaman damgasi (ornek 1787118756.6280162) yerine yerel saat HH:MM:SS gosteriliyor. Bicimleme arayuzde yapilir cunku epoch istemcinin yerel saat dilimine cevrilmeli; sunucu bicimlendirse UTC sabitlenir ve Ankara icin 3 saat sapma olur. Gecersiz, sifir ve eksik damgalar bos gosterilir; 1970 tarihi gosterilmez",
      "IS30: Baglanti Yoneticisi'ndeki dron karti artik kapali dogar, yalniz baslik gorunur (durum LED'i, dron adi, irtifa ve ucus kipi ozeti). Panel icinde acilir kapanir davranis kaldirildi; ok ikonu islevsiz kaldigi icin gizlendi. Kart <-> pencere gecis dugmesinin ikonu duruma gore degisir: panel icinde buyult, ayri pencerede kucult. Dugmenin islevi degismedi",
      "IS30: Ayri pencereden panele donen kart artik kapali duruma alinir; onceki surumde acik donuyordu ve yalniz baslik gorunmesi sozlesmesini ihlal ediyordu"
    ],
    d: [
      "Kok neden IS27: dugme_birlik.css yalniz-ikon kurali metni <span> icinde OLMAYAN dugmelerle eslesiyor. dronlar.js, sirket.js, kalkis_kontrol.js, ai_tespitler.js, arm_check.js, servis_panel.js, angajman.js, dron_bakim.js, dron_yakinlik.js, failsafe_kalib.js ve pg_sihirbaz.js dosyalarinda 35 dugme ikon + ciplak metin uretiyordu. Faz 18 Is 2B'de 27 dugme duzeltilmisti ancak bu dosyalar taranmamisti",
      "Uclu islec tuzagi: kosula bagli ikon tasiyan dugmelerde (failsafe_kalib.js) sarma islemi islecin ? ve : parcalarini ayirip soz dizimini bozdu; onarimda islec korunup her iki dalda metin ayri sarildi",
      "Kok neden IS28: dron.py konsol_ekle islevi ts alanini time.time() ile epoch float uretiyor, dronlar.js dkKonsolSatirBas bu degeri hic bicimlendirmeden DOM'a yaziyordu. Ana konsol (konsol.js) ayni veriyi dogru bicimlendiriyordu; o desen dron konsoluna tasindi. Sunucu tarafi epoch olarak KALDI cunku tekrar tespiti ts uzerinde sayisal karsilastirma yapiyor",
      "Kok neden IS30: kart olusturulurken kapali/gizli siniflari verilmiyordu ve ac/kapa icin uc ayri yol vardi (baslik tiklama, ok tiklama, cift tik). Ilk ikisi kaldirildi; ayrik moddaki cift tik kompakt gorunum icin korundu",
      "Detaylara erisim kapanmadi: buyult dugmesi karti ayri pencereye alir ve orada govde otomatik acilir",
      "Sinav: 47 denetim gecti (span sarma statik + jsdom CSS secici davranisi, saat bicimleme 12 sinir durumu, kart durum gecisleri). 12 JS dosyasinin soz dizimi node 22 ile dogrulandi"
    ] },
  { s: "2.4.98", t: "2026-08-19",
    b: "Dron U\u00e7u\u015f Ge\u00e7mi\u015fi panelinde FILTRE \u00fcst bar\u0131: pilot, ara\u00e7 t\u00fcr\u00fc ve tarih s\u00fczge\u00e7leri eklendi; panel yast\u0131\u011f\u0131 di\u011fer panellerin standard\u0131na \u00e7ekildi.",
    m: [
      "FILTRE \u00fcst bar\u0131 eklendi: etiket solda, s\u00fczge\u00e7ler sa\u011fa yasl\u0131 (Tespit Ge\u00e7mi\u015fi paneliyle ayn\u0131 desen). Panelde daha \u00f6nce hi\u00e7 \u00fcst bar yoktu.",
      "Pilot s\u00fczgeci eklendi. S\u00fczge\u00e7 `sahip_eposta` alan\u0131n\u0131 kullan\u0131r: sahiplik kural\u0131 'takeoff\u0027u kim verdiyse o u\u00e7u\u015funun sahibidir'. Telemetride ad\u0131 ge\u00e7en di\u011fer ki\u015filer (vardiya de\u011fi\u015fimi, g\u00f6zlemci) sahip say\u0131lmaz.",
      "Sunucu: `dron_listesi()` u\u00e7u\u015f kayd\u0131na `sahip_eposta` ve `sahip_ad` alanlar\u0131 eklendi. Eski `pilotlar` / `pilotlar_ad` alanlar\u0131 KORUNDU (imzal\u0131 u\u00e7u\u015f raporu bunlar\u0131 kullan\u0131yor).",
      "Ara\u00e7 t\u00fcr\u00fc s\u00fczgeci eklendi. T\u00fcr ad\u0131 `dkAracTipiBilgi()` kanonik e\u015flemesinden \u00e7\u00f6z\u00fcl\u00fcr; \u00fc\u00e7\u00fcnc\u00fc bir MAV_TYPE e\u015flemesi YAZILMADI (kalk\u0131\u015f kontrol\u00fc ile rapor aras\u0131nda \u00e7eli\u015fki olu\u015fmamas\u0131 i\u00e7in).",
      "Tarih s\u00fczgeci eklendi. Yerel takvim g\u00fcn\u00fc s\u0131n\u0131rlar\u0131 kullan\u0131l\u0131r; UTC kayd\u0131rmas\u0131 bir \u00f6nceki g\u00fcn\u00fc g\u00f6stermez.",
      "S\u00fczge\u00e7 se\u00e7enekleri veriden \u00fcretilir. Liste tazelendi\u011finde se\u00e7ili de\u011fer korunur; se\u00e7ili pilot listeden kalkm\u0131\u015fsa s\u00fczge\u00e7 her \u015feyi gizlemek yerine s\u0131f\u0131rlan\u0131r.",
      "Bo\u015f durum ayr\u0131m\u0131: s\u00fczge\u00e7 y\u00fcz\u00fcnden bo\u015f kalan liste 'Filtreye uyan u\u00e7u\u015f yok' der; ger\u00e7ekten kay\u0131t yoksa 'Kay\u0131tl\u0131 u\u00e7u\u015f yok' mesaj\u0131 korunur.",
      "S\u00fczge\u00e7 de\u011fi\u015fiminde sunucuya yeni istek G\u00d6NDER\u0130LMEZ; veri istemcide zaten mevcut.",
      "Panel k\u00f6k yast\u0131\u011f\u0131 (10px) kald\u0131r\u0131ld\u0131, alt kapsay\u0131c\u0131lara ta\u015f\u0131nd\u0131. \u00dcst bar art\u0131k pencere geni\u015fli\u011fini tam kullan\u0131yor.",
      "S\u00fczge\u00e7 \u00f6\u011feleri aras\u0131nda 6px aral\u0131k tan\u0131mland\u0131; \u00f6nceden biti\u015fik duruyorlard\u0131 (`gap: 0`).",
      "Ba\u015fl\u0131k \u00e7ubu\u011fu ile \u00fcst bar aras\u0131nda \u00e7ift kenarl\u0131k giderildi (`.dk-mp-baslik + .panel-toolbar` kural\u0131)."
    ] },
  {
    s: "2.4.97", t: "2026-08-19",
    b: "Video Duvari ayri pencerede acildiginda tekrar giris istiyor ve calismiyordu; iki ayri kusur bulundu. Baglanti adresi guvenli sayfalarda yanlis uretiliyordu ve oturum aktarimi tek bir yola bagliydi",
    m: [
      "SIKAYET IKI PARCALIYDI: pencere hem tekrar giris istiyor hem de calismiyordu. Olcum iki AYRI kusur oldugunu gosterdi; biri digerinin belirtisi degildi. Ikisi de ayni surumde giderildi",
      "AGIR KUSUR BAGLANTI ADRESINDEYDI. Video Duvari betigi baglanti adresini TEK ve KOSULSUZ bir bicimde uretiyordu: her zaman guvensiz protokol ve dogrudan port. Sayfa guvenli adres uzerinden gelse bile ayni adres deneniyordu",
      "TARAYICI BU BAGLANTIYI ENGELLER. Guvenli bir sayfadan guvensiz baglanti acmak karisik icerik sayilir ve tarayici tarafindan reddedilir. Sonuc olarak baglanti HIC kurulmuyor, acilma olayi hic tetiklenmiyor ve oturum devri islevi hic kosmuyordu. Kullanici giris perdesini goruyor, elle giris denedigindeyse baglanti olmadigi icin sunucuya ulasilamadigi soyleniyordu. Yani pencere guvenli erisimde TAMAMEN islevsizdi",
      "DOGRU ADRES SECIMI SISTEMDE ZATEN IKI YERDE VARDI. Ucus duvari ve ana arayuz betikleri dort ayri duruma gore adres uretiyor: gelistirme konagi, merkez kipi tuneli, guvenli dogrudan erisim ve yerel kurulum. Video Duvari ucuncu yer olarak geride kalmisti. Yeni bir cozum uydurulmadi; mevcut ve calisan dallanma birebir uygulandi",
      "GUVENLI PORT SABITI BU DOSYADA HIC TANIMLI DEGILDI. Betik guvenli dali hic uygulamadigi icin sabite ihtiyac duymamisti; dallanma eklenirken sabit de eklendi. Bes ayri kullanim senaryosu tek tek kosturularak dogru adresin uretildigi dogrulandi ve guvenli sayfalarda HICBIR durumda guvensiz baglanti kurulmadigi ayrica sinandi",
      "IKINCI KUSUR OTURUM AKTARIMININ TEK YOLA BAGLI OLMASIYDI. Video Duvari oturumu yalnizca tarayici deposundan okuyordu. Ana uygulamada ise oturum bilgisi bu depoya SADECE kullanici bilgileri sakla kutusunu isaretlerse yaziliyor; isaretlemezse mevcut kayit bile SILINIYOR. Normal kullanimda depo bos oldugu icin pencere her acilista giris istiyordu",
      "ANA UYGULAMANIN IKINCI YOLU VARDI VE BURADA KULLANILMIYORDU. Sunucuda oturum aktarim ucu bulunuyor; tarayicinin betikten okunamayan guvenli cerezini kullanarak gecici bir oturum anahtari uretiyor ve onay kutusundan BAGIMSIZ calisiyor. Ucun canli olarak dogru yanit verdigi ayrica dogrulandi. Ana uygulamadaki desen Video Duvari'na tasindi",
      "SIRA BILINCLI SECILDI: once tarayici deposu, sonra cerez uzerinden aktarim, en son giris perdesi. Depoda gecerli bir kayit varsa gereksiz ag istegi yapilmaz; yoksa cerez denenir; o da sonuc vermezse kullanici elle giris yapar. Bu sira sinavda dogrulandi",
      "SONSUZ DENEME DONGUSU ENGELLENDI. Aktarim istegi yalnizca BIR KEZ yapiliyor. Bu koruma olmasa baglanti her koptugunda yeni istek uretilir ve sunucu gereksiz yuklenirdi; ana uygulama da ayni korumayi tasiyor. Ikinci cagrinin gercekten yapilmadigi olculdu",
      "KAPALI DEVRE KURULUM GOZ ARDI EDILMEDI. Merkez Uygulama satin alan firmalarda bu uc bulunmayabilir. Uc yoksa ya da ag hatasi olursa sessizce gecilip giris perdesine dusuluyor; pencere COKMUYOR. Eksik ya da bozuk yanit gelmesi durumunda tarayici deposuna hicbir sey yazilmadigi da dogrulandi",
      "KONTROL DENEYI YAPILDI. Eski adres uretimi de ayni senaryoyla kosturuldu; beklendigi gibi guvensiz adres uretti ve yeni davranistan farkli oldugu gosterildi. Yalnizca yeni kodun gectigini gostermek yamanin bir sey duzelttigini kanitlamazdi",
      "UCUS DUVARI BU KUSURLARDAN ETKILENMIYOR. Olculdu: o sayfada giris perdesi ogesi HIC yok, kendi oturum katmani bulunmuyor ve adres dallanmasi zaten dogruydu. Bu yuzden ayni duzeltme oraya uygulanmadi",
      "SAYIM TUZAGINA DIKKAT EDILDI. Denetim, adres uretim dallarini sayarken yamanin KENDI aciklama yorumunda gecen ornek kod satirini da sayiyordu ve yanlis alarm verdi. Yorum satirlari sayimdan dusuldu ve her dal ayri ayri, sinir duyarli bicimde dogrulandi"
    ]
  },
  {
    s: "2.4.96", t: "2026-08-19",
    b: "Surum numarasina tiklaninca acilmasi gereken surum gecmisi penceresi on gundur hic acilmiyordu; okuyucu betik kayit yapisindaki alan adi degisikligine uyarlanmamisti. Ayrica kayitlarin kisa ozeti artik listede gorunuyor",
    m: [
      "PENCERE ON GUNDUR TAMAMEN KIRIKTI. Kullanici surum numarasina tikladiginda hicbir sey olmuyordu. Tarayici konsolunda tanimsiz bir degerin uzerinde liste donusumu denendigi bildiriliyordu; kaynak olarak surum gecmisi betiginin yetmis yedinci satiri gosteriliyordu",
      "KOK NEDEN KAYIT YAPISINDAKI ALAN ADI DEGISIKLIGI. Yuz dokuz surum kaydinin tamami tarandi: doksan sekiz kayit degisiklik listesini bir alan adiyla, on kayit BASKA bir alan adiyla tutuyordu. Bir kayit ise gecis kaydiydi ve her ikisini birlikte tasiyordu",
      "DEGISIKLIK ON SURUM ONCE YAPILMIS AMA OKUYUCU GUNCELLENMEMISTI. Kayit deseni yenilenirken hem alan adi degistirilmis hem de kisa ozet alani eklenmisti. Kayitlari YAZAN taraf yeni desene gecti, kayitlari OKUYAN taraf eski adi aramaya devam etti. Iki taraf arasindaki bu sessiz uyusmazlik on gun boyunca fark edilmedi",
      "PENCERENIN NEDEN HIC GORUNMEDIGI OLCULDU. Patlayan kayit listenin BIRINCI sirasindaydi, yani en yeni surum. Dongu ilk turda kesiliyordu ve pencere govdesi sayfaya henuz eklenmemis oluyordu. Bu yuzden kullanici bozuk bir pencere degil, HICBIR SEY goruyordu. Kusurun on gun boyunca yalnizca tek bir belirti uretmesinin sebebi de bu",
      "COZUM GERIYE DONUK UYUMLU. Okuyucu artik her iki alan adini da kabul ediyor; yeni ad once, eski ad sonra deneniyor. Doksan sekiz eski kayit silinmeyecegi icin geriye donuk uyum zorunluydu. Her iki desenin de dogru okundugu, gecis kaydi dahil olmak uzere ayri ayri sinandi",
      "SATIR BAZLI DAYANIKLILIK EKLENDI. Eski kodda tek bir eksik alan pencerenin TAMAMINI engelliyordu: bir kayit yuzunden yuz sekiz kayit birlikte gidiyordu. Artik her satir kendi koruma blogunda uretiliyor; bozuk bir kayit yalnizca kendi satirini etkiliyor, sonrasindaki kayitlar calismaya devam ediyor. Bu davranis, ortasina bilincli olarak bozuk kayitlar serpistirilmis bir veri kumesiyle dogrulandi",
      "BOZUK KAYIT SESSIZCE YUTULMUYOR. Okunamayan bir kayit icin kullaniciya gorunur bir uyari satiri birakiliyor ve ayrintisi konsola yaziliyor. Sessiz basarisizlik bu kusurun on gun fark edilmemesinin dogrudan sebebiydi; ayni tuzaga bir daha dusulmemesi icin acik iz birakiliyor",
      "KISA OZET ARTIK GOSTERILIYOR. Yeni kayitlarda tek cumlelik bir ozet alani vardi ve hicbir yerde kullanilmiyordu. Bu ozet artik kapali satirlarda gorunuyor; kullanici her kaydi tek tek acmadan listeyi tarayabiliyor. Satir acildiginda ozet gizleniyor, cunku ayrintili maddeler onu zaten kapsiyor ve ikisi birlikte gereksiz yineleme olurdu",
      "METINLER KACISLA YAZILIYOR. Kayit metinleri kendi kaynagimizdan geliyor, ancak sayfaya ham bicimde yazildiklari icin yine de kacis uygulandi. Ileride kayit metni baska bir kaynaktan beslenirse sayfa yapisini bozmamasi guvenceye alindi",
      "SINAV GERCEK KULLANICI YOLUNDAN KOSTURULDU. Betik kapali bir kapsam icinde oldugu ve acma islevi disariya sunulmadigi icin sinav dogrudan o islevi cagirmiyor; gercek bir belge ortami kurup surum etiketine TIKLIYOR. Boylece sinav, uygulamanin gercek davranisina bagli kaldi",
      "KONTROL DENEYI YAPILDI. Yamanin gercekten bir sey duzelttigini gostermek icin eski mantik da ayni veriyle kosturuldu; beklendigi gibi patladi ve urettigi hata iletisinin kullanicinin bildirdigi konsol kaydiyla birebir ortustugu dogrulandi. Yalnizca yeni kodun gectigini gostermek yeterli bir kanit olmazdi",
      "CEVIRI ANAHTARI EKSIKTI VE TAMAMLANDI. Bozuk kayit uyarisi icin kullanilan anahtar sozlukte tanimli degildi; kodda yedek dize bulundugu icin arayuz yine calisirdi ama Ingilizce arayuzde Turkce metin gorunurdu. Anahtar her iki dile de eklendi ve tam olarak birer kez tanimlandigi dogrulandi"
    ]
  },
  {
    s: "2.4.95", t: "2026-08-19",
    b: "Panel ust barlari icin kullanicinin uc kez yineledigi sozlesme nihayet tum panellere uygulandi: baslikta ikon yok, font koyu degil, metin pencere basligini yinelemiyor. Ayrica pencere basligi artik kaydirma sirasinda kaybolmuyor, Kameralar panelindeki dugme tasmasi giderildi, filtre alanlarinin genislik dagilimi duzeltildi ve Harita Ayarlari gruplari acilir kapanir hale getirildi",
    m: [
      "SOZLESME UC KEZ YINELENMISTI VE HER SEFERINDE EKSIK UYGULANMISTI. Kullanici ust bar basliklari icin uc kural koydu: ikon kullanilmayacak, font koyu olmayacak ve metin pencere basligiyla ayni olmayacak. Bu kez tum ust barlar tek tek olculdu; dokuz ust bardan YEDISININ sozlesmeyi ihlal ettigi, yalnizca ikisinin uyumlu oldugu sayildi",
      "IHLALLERIN ORTAK DESENI CIKTI. Yedi ust bar da ikon tasiyordu ve alti tanesi pencere basligiyla BIREBIR ayni metni yineliyordu: Kameralar panelinde ust barda KAMERALAR, pencere basliginda da KAMERALAR yaziyordu. Kullanicinin sikayeti tam olarak buydu: ayni baslik alt alta iki kez gorunuyordu",
      "DOGRU DESEN ZATEN SISTEMDE VARDI. Tespit Gecmisi paneli daha once duzeltilmis ve ikonsuz, hafif agirlikli bir etiket sinifi kullaniyordu. Yeni bir tasarim uydurmak yerine bu mevcut desen tum panellere yayildi; boylece paneller arasinda gorsel tutarlilik da sagland",
      "METINLER KULLANICININ VERDIGI SOZLUKTEN ALINDI. Kisiler panelinde KISI YONETIMI, Suru panelinde FORMASYON YONETIMI, Kayitsiz Tespitler panelinde TESPIT EDILEN KISILER, Rotalar panelinde GOREV ROTALARI, Araclar panelinde ARAC PLAKALARI, Kameralar panelinde KAMERA YONETIMI. Her metin pencere basligindan farkli oldugu ayri ayri sinandi",
      "CEVIRI ANAHTARLARI YENIDEN EKLENMEDI, DEGERLERI GUNCELLENDI. Anahtarlar zaten vardi; ikinci kez eklenmesi sozlukte cift kayit uretirdi. Once her anahtarin baska nerelerde kullanildigi sayildi: hepsi yalnizca tek bir yerde kullaniliyordu, yani deger degisiminin baska bir ekrani bozma riski yoktu. Ingilizce karsiliklar da ayni anda guncellendi",
      "KAMERALAR PANELINDEKI DUGME TASMASININ NEDENI OLCULDU. Ust barda uc dugme vardi ve UCU DE metin tasiyordu, ancak hicbiri metinli dugme kalibini kullanmiyordu; hepsi kare ikon kalibindaydi. Metin bu yuzden kare cercevenin disina cikiyordu. Uc dugme de metinli kaliba alindi; basligin ikonsuz hale gelmesiyle yatay yer de acild",
      "PANEL BASLIGININ KAYDIRMA SIRASINDA KAYBOLMASI ICIN KOK NEDEN BULUNDU. Kaydirma ozelligi pencerenin KOK ogesine verilmisti; baslik da bu kok ogenin cocugu oldugu icin icerikle birlikte yukari kayip goruntu alanindan cikiyordu. Kullanicinin tarifi buydu: baslik kaydirma icinde kalmamali",
      "COZUM ICIN YINE SISTEMDE HAZIR OLAN DESEN KULLANILDI. Yapay Zeka pencereleri bunu dogru yapiyordu: kaydirma ic govdede, baslik ise kardes oge olarak sabit. Ayni yapi bu iki pencereye uygulandi. Kritik ayrinti, esnek yerlesim cocuklarinin varsayilan olarak icerik yuksekliginde buyumesi ve kaydirmayi HIC tetiklememesidir; bunu engelleyen kural acikca eklendi",
      "FILTRE ALANLARINDA GENISLIK DAGILIMI DUZELTILDI. Tum acilir listeler ayni esneklikte tanimliydi; icerigi uzun olan liste genisliyor, tarih alani ise kirpiliyor ve arama dugmesi tam gorunmuyordu. Artik listeler icerigine gore daraliyor, tarih alani sabit bir taban genislik koruyor ve arama dugmesi hicbir kosulda daralmiyor",
      "AYNI SECICININ DOSYADA BIRDEN COK KEZ TANIMLI OLDUGU FARK EDILDI. Tarih alani kurali dort, dugme kurali iki ayri yerde vardi. Basamakli stil dosyalarinda ayni ozgullukteki kurallardan SON yazilan kazanir; bu yuzden yeni kurallarin gercekten sonda oldugu ve eskileri gecersiz kildigi ayrica sinandi",
      "HARITA AYARLARI ARTIK ACILIR KAPANIR GRUPLARDAN OLUSUYOR. Bes ozellik grubu ayni anda acikti ve pencere yukseklik sinirina dayanip uzun bir kaydirma uretiyordu. Gruplar artik basligina tiklanarak kapatilabiliyor, yanlarinda arti ve eksi gostergesi bulunuyor ve varsayilan olarak yalnizca ilk grup acik geliyor",
      "GRUP DURUMU HATIRLANIYOR VE KIMLIK OLARAK SIRA NUMARASI KULLANILMIYOR. Her grup ceviri anahtariyla kimliklendirildi; ileride gruplarin sirasi degisirse ya da yeni grup eklenirse kayitli tercihler yanlis gruplara uygulanmaz. Depolama erisimi engellendiginde ozellik yine calisir, yalnizca hatirlamaz",
      "ACCORDION DAVRANISI GERCEK BIR TARAYICI ORTAMINDA KOSTURULARAK SINANDI. Metin denetimi bir seyin CALISTIGINI gostermez; bu yuzden gercek belge nesnesi kurulup tiklama ve klavye olaylari tetiklendi, kayitli durumun yeni oturumda geri yuklendigi dogrulandi. Bozuk kayit ve grup bulunmayan sayfa gibi sinir durumlarinda cokme olmadigi da ayri ayri sinand",
      "ERISILEBILIRLIK GOZ ARDI EDILMEDI. Acilir kapanir basliklar klavyeyle de kullanilabiliyor, ekran okuyucular icin dugme rolu ve acik kapali durumu bildiriliyor"
    ]
  },
  {
    s: "2.4.94", t: "2026-08-19",
    b: "Cevrimdisi harita indirme calisiyordu ama dayanilmaz yavasti ve hicbir geri bildirim vermiyordu; indirme es zamanli hale getirildi, indirme oncesi sure ve boyut tahmini eklendi. Ayrica bulunamayan karo artik sahte bos goruntu yerine durum kodu donuyor",
    m: [
      "SIKAYET 'CEVRIMDISI HARITA INDIRME CALISMIYOR' SEKLINDEYDI ANCAK ISLEV CALISIYORDU. Once karo kaynaginin kirildigi dusunuldu; bir karo istegi sinandi ve bulunamadi yaniti dondu. Bu bulgudan karo saglayicisinin ucunu kapattigi sonucu cikarildi. SONUC YANLISTI: sinav icin secilen karo kutup bolgesinde bos bir kareydi ve saglayici orada gercekten goruntu tutmuyor. Kontrol karosu hatali secilmisti",
      "OLCUM GERCEK KOORDINATLARLA YENILENDI. Ankara uzerindeki karolar tum yakinlastirma duzeylerinde ve dort ayri sunucu adresinden basariyla geldi. Diger tum saglayicilar da calisiyordu. Uygulamanin kendi karo vekili uzerinden uctan uca sinav da dogru goruntuleri dondurdu: karo boru hattinda hicbir ariza yoktu. Varsayilan kaynagin zaten degistirilmis oldugu da bu sirada dogrulandi",
      "GERCEK KUSUR OLCEKTE CIKTI. Kullanici gorunen bolgeyi indir dediginde varsayilan yakinlastirma araligiyla yirmi bin karo istiyordu. Olculen indirme hizi saniyede bes karoydu, cunku istekler tek sirada ve birbirini bekleyerek yapiliyordu. Bu, altmis dokuz DAKIKA demektir. Genis bir gorunumde otuz dokuz SAATE cikiyordu. Kullanici acisindan bu, calismamakla ayni sey",
      "GERI BILDIRIM EKSIKLIGI DURUMU AGIRLASTIRIYORDU. Ilerleme bildirimi yalnizca her yirmi karoda bir yapiliyordu; yani dort saniyede bir guncelleme. Cubuk donmus gorunuyordu. Ustelik islem baslamadan once kac karo indirilecegi, ne kadar surecegi ve ne kadar yer kaplayacagi hicbir yerde gosterilmiyordu",
      "COZUM DORT PARCALI. Birincisi es zamanlilik: indirme artik sekiz istegi paralel yurutuyor. Bekleme suresi ag gecikmesinden kaynaklandigi icin hizlanma dogrusaldir; olculen deger saniyede bes karodan otuz karoya cikti, yaklasik alti kat. Es zamanlilik kasitli olarak sekizde tutuldu: daha yukarisi saglayiciyi tacize ve kendi sunucumuzu gereksiz baglantiya zorlar",
      "IKINCISI ON OLCUM. Indir dugmesi artik dogrudan indirmeye baslamiyor; once sunucudan tahmin istiyor ve kullaniciya karo sayisi, tahmini sure ve tahmini disk boyutunu gosteren bir onay soruyor. Kullanici ne kadar isin icine girdigini artik ONCEDEN biliyor",
      "UCUNCUSU UST SINIR. En genis yakinlastirma araligi tek bir sehir icin bir milyondan fazla karo, on bes gigabayt eder. Boyle bir istek diski doldurur ve gunlerce surer. Sinir asilirsa islem HIC BASLAMAZ; kullaniciya yakinlastirma araligini daraltmasi soylenir. Sinirin gercekten kapi gibi davrandigi, buyuk bir istekle sinandi: tek karo bile inmedi",
      "DORDUNCUSU GERI BILDIRIM. Bildirim artik hem daha sik hem de en az saniyede bir yapiliyor; olculen en buyuk bosluk saniyenin ucte biri. Ilerleme yazisinda kalan sure ve anlik hiz da gosteriliyor. Ayrica indirme surerken panel kapatilip yeniden acilirsa cubuk artik bos gorunmuyor, mevcut ilerlemeyi geri kuruyor",
      "AYNI SURUMDE IKINCI DEGISIKLIK: BULUNAMAYAN KARO ARTIK SAHTE GORUNTU DONDURMUYOR. Bir karo hicbir katmanda bulunamadiginda sunucu, tek noktalik saydam bir goruntu uretip BASARILI durum koduyla gonderiyordu. Harita kutuphanesi bunu gecerli goruntu sanip cozmeye calisiyor, cozemeyince belirsiz bir hata yaziyordu",
      "BU SESSIZ BASARISIZLIKTI VE UC AYRI ZARARI VARDI. Ara katmanlar sahte yer tutucuyu gecerli karo sanip saklayabiliyordu. Gercek bir ariza ciktiginda kullanici siyah kare goruyor ama hicbir kayit birakilmiyordu. Konsoldaki karo hatalarinin bir kismi da aslinda bu sahte yanittan kaynakliyordu",
      "DOGRUSU EKSIK KAYNAK DURUM KODUDUR. Harita kutuphanesi bunu duzgun karsilar, kendi saydam yer tutucusunu kullanir ve gereksiz hata uretmez. Okyanus ve kutup gibi saglayicida GERCEKTEN karo bulunmayan bolgeler icin de dogru anlam budur",
      "SAGLAYICI DAVRANISLARININ AYRISTIGI OLCULDU VE SINAVDA AYRI AYRI KORUNDU. Bir saglayici veri olmayan bolgede bulunamadi diyor, digeri gecerli ama bos bir goruntu donduruyor. Ikinci durumda gelen goruntu uydurma bir yer tutucu degil saglayicinin kendi yanitidir, bu yuzden aynen gecirilmeli. Sinav her iki yolu birbirinden ayirarak dogrular",
      "DOGRULAMA: on yedi denetimin tamami gecti. Sinav on olcum degerlerini, ust sinirin indirmeyi gercekten engelledigini, es zamanli hizi, bildirim sikligini ve iki saglayici davranisinin dogru ayrildigini olcer. Uc arayuz dosyasinin soz dizimi ayrica denetlendi"
    ]
  },
  {
    s: "2.4.93", t: "2026-08-19",
    b: "Harita hicbir sey cizmiyordu: gorsel varlik dosyalari sunucu tarafinda engelliydi. Ayrica dron gosterimi iki boyutlu ikona dondurüldü ve baslangicta gelen sifir koordinati artik gecerli konum sayilmiyor",
    m: [
      "HARITA TAMAMEN SIYAHTI. Kullanici dron ikonunun gorunmedigini bildirdi. Once ikon olcegi incelendi ve 2.4.90 ile mesafeye gore gosterim devri eklendi; ancak kusur duzelmedi. Kullanici lokasyon ikonunun ve cetvelin de cizmedigini bildirdiginde teshis degisti: bu iki cizim dron telemetrisinden tamamen bagimsizdir, dolayisiyla ortak bir noktada engel olmasi gerekiyordu",
      "OLCUM TARAYICIDA YAPILDI. Harita alani hicbir sey cizmiyordu: ne uydu goruntusu, ne dunya, ne kilavuz. Konsolda iki gorsel varlik dosyasinin bulunamadigi goruldu; harita kutuphanesi bu dosyalar olmadan sahneyi kuramadigi icin soz verisi reddiyle cokuyordu. Dron ikonu, lokasyon ikonu, cetvel ve rota noktalari ayni sahneye yazdigi icin dordu birlikte kayboluyordu",
      "KOK NEDEN BIR GUVENLIK KURALIYDI. Veri dosyasi uzantisi, icinde veritabani parolasi bulunan bir ayar dosyasinin disariya sizmasini onlemek icin sunucu tarafinda engellenmisti. Kural haklıydı ancak tum dizin agacina uygulaniyordu ve harita kutuphanesinin ISLEVSEL varlik dosyalarini da vuruyordu: arazi yukseklik referansi ve gok referans cercevesi verileri",
      "KUSUR IKI KATMANDAYDI. Uygulama sunucusundaki engel kaldirildiktan sonra dosyalar hala disariya sunulmuyordu. Olcum, dogrudan uygulama portuna sorunca dosyanin geldigini, alan adi uzerinden sorunca gelmedigini gosterdi. Onundeki vekil katmaninda ayni kara listenin bir KOPYASI bulundu. Ayni guvenlik kuralinin iki dosyaya cogaltilmis olmasi, birini duzeltmenin yetmemesine yol acti",
      "COZUM: veri dosyasi uzantisi kara listede KALDI, yalnizca ucuncu parti kutuphane dizini icin islevsel izin eklendi. Bu dizinde parola, sertifika veya kaynak kod bulunmadigi once olculdu: riskli uzanti sifir, sir izi tasiyan dosya sifir",
      "GUVENLIGIN BOZULMADIGI AYRICA SINANDI. Parola tasiyan ayar dosyasi, sunucu kaynak kodu ve yol gecisi denemelerinin iki bicimi (dogrudan ve adres kodlamasi ile) yama sonrasi da reddedilmeye devam ediyor",
      "DOGRULAMA: harita kutuphanesi sahneyi kuruyor, karolar yuklendi ve doksan uc gosterim ogesi cizili durumda olculdu",
      "AYNI SURUMDE IKINCI DEGISIKLIK: DRON GOSTERIMI IKI BOYUTA DONDU. Prizma secenegini kaldirma isi yapilirken secenek kaldirilmis ancak gosterim kipi kalici olarak ACIK birakilmisti. Sonuc: kullanici secemez hale gelirken sistem her zaman uc boyutlu blok ciziyordu. Kip artik kapali; iki boyutlu elmas ikon gosterimi kullaniliyor. Prizma kodu silinmedi, ileride gerekirse geri acilabilir",
      "AYNI SURUMDE UCUNCU DEGISIKLIK: BASLANGIC SIFIR KOORDINATI ARTIK GECERLI SAYILMIYOR. Benzetim sureci ilk telemetride sifir enlem ve sifir boylam yayinliyor; bu nokta Gine Korfezi aciklarinda bos denizdir. Sistem bunu gecerli konum sanip oraya bir gosterim kuruyor, gercek veri geldiginde iki nokta arasindaki mesafeyi hesapliyordu. Kullanicinin gordugu iki bin yuz kilometrelik mesafe degeri uydurma degildi: gercek konum ile bos deniz arasindaki gercek uzakliktir",
      "AYNI KUSUR DORT AYRI YERDE TEKRARLANIYORDU: dron gosterimi, kalkis noktasi ikonu ve radar hedeflerinin iki cizim yolu. Her biri yalnizca bos deger denetimi yapiyor, sayisal sifiri geciriyordu. Tek tek yamamak yerine ortak bir konum dogrulamasi yazildi ve dort cagri yeri de ona baglandi; boylece olcut tek bir yerde tanimli",
      "OLCUT KASITLI OLARAK BIRLIKTE DENETLER: enlem VE boylam ayni anda sifirsa reddedilir. Yalniz birinin sifir olmasi mesrudur; ekvator uzerinde veya baslangic boylami uzerinde gercek ucus yapilabilir. Tek basina enlem sifir reddi yazilsaydi bu mesru ucuslar sessizce haritadan kaybolurdu",
      "DOGRULAMA: ortak dogrulama islevi on sekiz denetimle sinandi ve tamami gecti. Sinav bos deniz noktasinin reddedildigini, ekvator ve baslangic boylami uzerindeki mesru ucuslarin kabul edildigini, sayisal olmayan degerlerin ve enlem boylam sinir degerlerinin dogru islendigini olcer. Bes dosyanin soz dizimi ayrica denetlendi"
    ]
  },
  {
    s: "2.4.92", t: "2026-08-19",
    b: "Radar hedef isaretleri artik uzak kamera mesafesinde kaybolmuyor; Is 7 ile ayni olcek sozlesmesi radar katmanina da uygulandi",
    m: [
      "RADAR HEDEFLERI UZAKTA GORUNMEZ OLUYORDU. Kusur, 2.4.90 ile dron ikonunda giderilen olcek kusurunun IKIZIDIR: hedef isaretleri de metre tabanli uc boyutlu gosterim kullaniyor, yani kamera uzaklastikca ekranda kucululer. Dron ikonunda oldugu gibi hedef etiketi ve baglanti cizgileri piksel tabanli oldugu icin gorunur kaliyor, isaretin kendisi kayboluyordu",
      "NEDEN AYRI YAMA GEREKTI: hedef isaretleri dron ikonundan FARKLI bir yukseklik sozlesmesi ve farkli bir menzil olcegi kullanir. Radar istasyonu hedefleri kendi menzil dairesi icinde gosterir ve kamera bu menzile gore konumlanir, bu nedenle esik dron ikonunun esigi ile ayni olamazdi. Bu yuzden 2.4.90 kapsamina dahil edilmeyip kendi olcumu yapildi",
      "OLCUM GERCEK HARITA KUTUPHANESI ILE YAPILDI. Ikon modulunun kendi belgesindeki uyari geregi (ana is parcaciginda yapilan sinavlar gorsel kusurlarda yanlis gecti verebilir) gosterim islevleri gercek kutuphane ile sandbox icinde kosturuldu; konum, yon ve geometri uretimi cesitli hedef ornekleri uzerinde dogrulandi",
      "COZUM: uc boyutlu elmas gosterimi yakin mesafede korunur, belirlenen esigin otesinde piksel tabanli nokta gosterimine devredilir. Gecis harita kutuphanesinin kendi gorunurluk kosulu ile yapilir, yani her cizim karesinde ek hesap yapilmaz ve 2.4.31 ile kazanilan basarim feda edilmez",
      "IKI ARALIGIN BITISIK OLDUGU AYRICA DENETLENIR. Aralarinda bosluk kalmasi durumunda o mesafede hedef yine kaybolurdu; sinav bu bitisikligi olcer",
      "DOGRULAMA: gercek harita kutuphanesi ile kosulan sinav tamamen gecti, kontrol deneyi yama oncesi dosyada gecerli sonuc verdi"
    ]
  },
  {
    s: "2.4.91", t: "2026-08-19",
    b: "Giris formu artik oturumu olan kullaniciya hic gorunmuyor; baglanti kopmasindan sonra olusan oturum gerekli hatasi giderildi",
    m: [
      "GIRIS FORMU HERKESE GORUNUYORDU. Kullanici daha once giris yapmis ve oturumu gecerli olsa bile, sayfa acildiginda once giris formu ciziliyor, kisa bir sure sonra kendiliginden kayboluyordu. Bu, arayuzun her acilista parola soruyormus gibi gorunmesine yol aciyordu",
      "KOK NEDEN: giris penceresi baslangicta GIZLI DEGILDI. Pencere yapisi zaten dogruydu — ortalanmis kutu ve arkasinda bulanik ortu, yani tam sayfa kaplayan bir panel hic yoktu. Kusur, pencerenin sayfa ilk cizildigi anda GORUNUR durumda baslamasiydi. Oturum devralma ve jeton dogrulama islemleri es zamansiz oldugu icin pencere ancak dogrulama tamamlandiktan SONRA kapatiliyordu",
      "GECIKMENIN OLCUMU: otomatik giris denemesi 800 milisaniyelik bir zamanlayiciya bagliydi ve baglanti kuruldugu anda cagrilmiyordu (olculdu). Buna baglanti el sikismasi ve kurumsal panelden oturum devri gerekiyorsa ek bir sunucu turu ekleniyordu. Sonuc: en iyi durumda yaklasik 800 milisaniye, kurumsal devirde 1.5 ile 2 saniye arasinda giris formu gorunur kaliyordu",
      "COZUM: giris penceresi artik gizli baslar ve yalnizca giris GERCEKTEN gerektiginde acilir. Acma islemi tek bir kapidan gecer, boylece pencerenin hangi kosulda acildigi izlenebilir olur. Kapi pencere zaten acikken tekrar acmaya calismaz ve odagi bos alana verir: kullanici adi bossa oraya, hatirlanan kullanicida dogrudan parolaya",
      "GECIKME KALDIRILDI. Baglanti kuruldugu anda otomatik giris denemesi HEMEN yapilir. Yeniden deneme zamanlayicisi korunur (gecici baglanti sorunlarinda gerekli), yalnizca ilk deneme one alinir. Pencere gizli baslayacagi icin bu gecikme aksi halde kullaniciya bos arayuz olarak gorunurdu",
      "AYNI SURUMDE IKINCI KUSUR GIDERILDI: OTURUM GEREKLI HATASI. Sunucuda oturumun firma baglami, baglanti nesnesinin kimligine baglidir. Baglanti koptugunda bu baglam sunucuda yok olur. Istemci yeniden baglaniyordu ancak kimligini TEKRAR GONDERMIYORDU, cunku otomatik giris kapisi yerel oturum degiskeninin dolu olmasina bakip hemen donuyordu. Sonuc: istemci girisli gorunurken sunucu kimliksiz biliyor, her panel istegi oturum gerekli hatasi aliyordu ve kullanici sayfayi yenilemeden bunu duzeltemiyordu",
      "COZUM: baglanti koptugunda bir kimlik tazeleme isareti kaldirilir. Yeni baglanti kuruldugunda bu isaret otomatik giris kapisini asar ve jeton yeniden gonderilir. Kullanicinin arayuzu BOZULMAZ: oturum bilgisi, profil rozeti ve acik paneller korunur, kimlik sessizce tazelenir. Kullanici hicbir sey fark etmez",
      "SUNUCU TARAFI GUVENLIGI ONCE OLCULDU. Jetonla giris isleyicisinin oturum baglamini ATAMA ile kurdugu dogrulandi (ekleme degil), yani ayni jetonun ikinci kez gonderilmesi baglami yeniden kurar ve yan etki uretmez. Basarili yanit da normal giris ile ayni bicimi uretiyor, bu nedenle arayuz tarafinda ek isleyici gerekmedi",
      "HESAP KILITLENME RISKI ONLENDI. Kaba kuvvet korumasi jetonla giris denemelerini de sayiyor ve kodun kendi varsayimi mesru istemcinin jetonu yalnizca bir kez gonderdigi yonundeydi. Yeniden baglanmada gonderim bu varsayimi zorlar. Gecerli jeton sayaci sifirladigi icin sorun olusmaz; ancak jetonun suresi dolmussa her yeniden baglanma bir basarisiz deneme sayilabilirdi. Bunu onlemek icin sunucu jetonu gecersiz bildirdiginde sakli kayit silinir, tazeleme isareti indirilir ve giris penceresi acilir. Ikinci turda gonderilecek kimlik kalmadigi icin zincir kendini kapatir",
      "DOGRULAMA: dort akis senaryosu kod uzerinde izlenerek 39 denetim kosuldu ve tamami gecti. Senaryolar: oturumu olan kullanici formu hic gormez, oturumu olmayan kullaniciya form gorunur, baglanti kopup yeniden kuruldugunda kimlik tazelenir, jeton gecersizse kilitlenme riski olusmaz. Yama oncesi dosyalarda ayni sinav 23 denetimde kaldi. Ayrica baglanti kopma isleyicisinin oturumu sifirlamadigi (arayuzun bozulmadigi), cikis davranisinin ve video duvari akisinin etkilenmedigi ayrica denetlendi"
    ]
  },
  {
    s: "2.4.90", t: "2026-08-19",
    b: "Harita dron ikonu uzak gorusto kayboluyordu; mesafeye gore gosterim devri eklendi",
    m: [
      "HARITADA DRON IKONU GORUNMUYORDU. Dron baglandiginda etiket, dikey cizgi ve yon cizgisi ciziliyor, odaklan dugmesi dogru konuma gidiyor, ancak IKONUN KENDISI gorunmuyordu. Konum bilgisi dogru geldigi icin kusur telemetri veya koordinat cevrimi sanildi; gercek neden GOSTERIM OLCEGIYDI",
      "KOK NEDEN: v2.4.30 ve v2.4.31 surumlerinde dron ikonu, basarim kazanmak icin PIKSEL tabanli gosterimden METRE tabanli ucboyutlu gosterime tasindi. Kazanc gercekti: ikon basina ayri cizim cagrisi ortadan kalkti. Ancak OLCEK SOZLESMESI kirildi. Piksel tabanli gosterim kamera uzakligindan BAGIMSIZ olarak hep ayni boyutta cizilirken, metre tabanli gosterim kamera uzaklastikca kuculur. Olculen degerler (dikey gorus acisi 60 derece, ekran yuksekligi 1080 piksel): 1500 metrede 18.7 piksel, 2500 metrede 11.2 piksel, 3000 metrede 9.4 piksel",
      "BELIRTIYI OLUSTURAN ZINCIR: dron ilk baglandiginda kamera 3000 metre yukseklige gonderilir. Ikon o uzaklikta 9 piksele duser ve uzerindeki arka planli etiket (18 piksel asagi kaydirmali) onu gorsel olarak tamamen bastirir. Etiket ve cizgiler piksel tabanli olduklari icin gorunur kaldigindan kullanici konumun dogru oldugunu gorur ama ikonu bulamaz",
      "OLCUM TARAYICI OLMADAN YAPILDI. Ikon modulunun kendi belgesi, ana is parcaciginda yapilan sinavlarin gorsel kusurlari YANLIS OLARAK gecti diyebildigi konusunda uyariyor. Bu nedenle gercek harita kutuphanesi sunucu disinda calistirilarak ikonun konum, yon, boyut ve malzeme ureten islevleri yedi ayri telemetri ornegiyle (ucbirim degerler ve eksik alanlar dahil) kosturuldu; hepsi gecerli deger uretti. Geometri uretimi de zorlandi ve saglam cikti. Boylece gecersiz deger ve geometri hipotezleri elendi, ekran olcegi tek ayakta kalan aday olarak kanitlandi",
      "COZUM: MESAFEYE GORE GOSTERIM DEVRI. Ucboyutlu elmas gosterimi yalniz 2500 metreden yakin gorusle sinirlandi; boylece yakinda siluet ve yon bilgisi korunur. 2500 metreden uzakta PIKSEL tabanli nokta gosterimi devreye girer ve her uzaklikta ayni boyutta gorunur. Esik degeri olcumle secildi: elmas o noktada yatayda 11 piksele duser, yani ayirt edilebilirligin alt sinirina gelir",
      "BASARIM KORUNDU. Gecis harita kutuphanesinin kendi gorunurluk kosuluyla yapilir; her cizim karesinde hesap YAPILMAZ. Boylece v2.4.31 ile kazanilan basarim iyilestirmesi feda edilmedi. Nokta gosterimi ayni varlik uzerinde yasar, ek cizim cagrisi getirmez",
      "GORSEL TUTARLILIK: nokta gosterimi dronun kalici rengini kullanir, koyu cerceve tasir (acik zemin ve uydu goruntusu uzerinde de ayirt edilir), elmasla ayni yukseklik sozlesmesine uyar ve etiketle ayni derinlik davranisini gosterir. Baglanti koptugunda elmas ve etiketle AYNI oranda soluklasir",
      "DOGRULAMA: gercek harita kutuphanesiyle 33 denetim kosuldu ve tamami gecti. Denetimler arasinda iki gorunurluk araliginin BITISIK oldugu (arada ikonsuz mesafe kalmadigi) ve on bir ayri uzaklikta en az bir gosterimin ayirt edilebilir boyutta oldugu olcumu de var. Yama oncesi dosyada ayni sinav 13 denetimde kaldi, yani sinav kusuru gercekten ayirt ediyor",
      "KAPSAM NOTU: radar hedefleri ve radar gorsel katmani ayni elmas gosterimini kullanir ve ayni olcek kusurunu tasir. Bu surumde YALNIZ dron ikonu duzeltildi; radar hedeflerinin gorunurluk esigi radar menziliyle iliskili oldugu icin ayri olcum gerektirir ve ayri is olarak siraya alindi",
      "DERS: bir gosterim bicimi degistirilirken yalniz gorsel sonuc degil OLCEK SOZLESMESI de karsilastirilmalidir. Piksel tabanli gosterimden metre tabanli gosterime gecis, yakin gorusto ayni gorunse bile uzak gorusto ozelligi tamamen kullanilamaz hale getirebilir"
    ]
  },
  {
    s: "2.4.89", t: "2026-08-18",
    b: "AI Sunucu listesini her cagride dusuren vekil kusuru giderildi",
    m: [
      "AI SUNUCU LISTESI MERKEZ KIPINDE HER CAGRIDA HATA VERIYORDU. Merkezde AI sunucularini yoneten vekil katmani, veritabani islerini tek kaynakta tutmak icin asil yoneticinin govdelerini kendi ornegiyle cagirir; boylece ayni kod iki yere kopyalanmaz. Ancak listeleme govdesi ilk satirinda firma suzgecini ureten bir yardimci uyeyi cagiriyor ve vekil katmani bu uyeyi iletmiyordu. Sonuc: liste her cagrida ozellik bulunamadi hatasiyla dusuyordu. Hata firma suzgeci istenmedigi durumda DA olusuyordu, cunku yardimci cagri kosulsuzdur",
      "KUSUR OLCUMLE KANITLANDI, TAHMINLE DEGIL. Vekilin ilettigi on bir yontemin govdeleri soz dizimi agaci uzerinden tarandi; her govdede gecen tum ornek uyesi erisimleri toplanip vekil sinifinda tanimli adlarla karsilastirildi. Eksik uye SADECE BIR taneydi ve yalnizca listeleme yonteminde kullaniliyordu, diger on yontem saglamdi. Ardindan hata gercek modullerle calisma zamaninda yeniden uretildi ve duzeltmenin ardindan yama oncesi/sonrasi karsilastirmasi yapilarak sinavin kusuru gercekten ayirt ettigi dogrulandi",
      "DUZELTME KUSURUN BULUNDUGU KATMANDA YAPILDI. Asil yonetici dosyasina DOKUNULMADI: o dosya kapali devre kurulumlarda da kosuyor ve orada kusur yok; kusursuz kodu degistirmek gereksiz risk olurdu. Eksik uye vekil katmanina eklendi ve govdesi KOPYALANMADI — iletim asil kaynaga yapildigi icin suzgec mantigi tek kaynakta kaldi. Sinav bunu ayrica denetliyor: suzgec metni vekil dosyasinda hic gecmiyor, kaynak dosyada bir kez geciyor",
      "HATANIN GUNLUKTE IZ BIRAKMADIGI TESPIT EDILDI. Baglanti komut katmanindaki sarmalayici istisnayi yakalayip istemciye hata metni olarak donduruyor ancak sistem gunlugune yazmiyor. Bu yuzden kusur gunluk taramasiyla bulunamazdi; cagri yolunun soz dizimi agaci uzerinden olculmesi gerekti"
    ]
  },
  {
    s: "2.4.88", t: "2026-08-18",
    b: "Panel ust bar sozlesmesi: yinelenen baslik, filtre dizilimi, dugme etiketleri",
    m: [
      "PANEL UST BARLARINDA PENCERE BASLIGINI YINELEYEN METINLER KALDIRILDI. AI Sunuculari ve Tespit Gecmisi pencerelerinde ust bar, pencere baslik cubugundaki metnin BIREBIR aynisini ikinci kez yaziyordu; AI Sunuculari'nda hatta ayni ceviri anahtari iki yerde kullaniliyordu. Ust uste iki satir ayni yaziyi gosteren gorunum giderildi. Tespit Gecmisi'nde yinelenen baslik yerine islevsel ve IKONSUZ bir FILTRELER etiketi kondu. Sol panelin bolum barlarindaki basliklara DOKUNULMADI: orada baslik bir pencere basligini yinelemiyor, bolumun kendi adini tasiyor",
      "TESPIT GECMISI FILTRELERI ARTIK TEK SATIRDA VE SAGA YASLI. Filtre ust bari sarmaya izin veriyordu; tur, kamera, tarih ve ARA ogeleri dar pencerede alt satirlara dusuyor, ust bar iki-uc satir yukseklige cikiyordu. Sarma kapatildi, filtre ogelerinin daralmasina izin verildi ve esneyen bosluk sayesinde tum grup saga yaslandi",
      "UST BAR BASLIKLARININ KALIN GORUNUMU HAFIFLETILDI. Baslik agirligi 700'den 500'e cekildi. Kullanici kurali tum panelleri kapsadigi icin bolum barlari da ayni hafif agirliga gecti",
      "UST BARDAKI DORT DUGME ARTIK YALNIZ IKON DEGIL, IKON VE ETIKET TASIYOR: Video Duvari, Onizleme, Yeni Kamera ve Yeni Rota. Etiketler bir kapsayici icine alindi; duz metin olarak yazilsalardi dugme birligi sozlesmesindeki yalniz-ikon kurali onlari 26 piksellik kareye sikistirirdi — bu kusur bir onceki surumde 27 dugmede giderilmisti, ayni tuzaga yeniden dusulmedi. Ceviri sozlugune yalnizca iki yeni anahtar cifti eklendi; kalan dugmeler var olan anahtarlari kullaniyor cunku ayni anahtari ikinci kez tanimlamak oncekini sessizce ezer. Gizli durumdaki hedef menusu dugmesine dokunulmadi: ekranda hic gorunmedigi icin etiket eklemek gorsel bir sey degistirmezdi"
    ]
  },
  {
    s: "2.4.87", t: "2026-08-18",
    b: "Ucus duvari logosu + ikincil sayfalarin onbellek etiketi kapsami",
    m: [
      "UCUS DUVARI UST CUBUGUNDA ARTIK GERCEK URUN LOGOSU GORUNUYOR. Onceden logo yerine bir metin karakteri (yer tutucu elmas simgesi) duruyordu ve stil dosyasi bunu renk ile yazi boyutu vererek biciimlendiriyordu; yani hicbir gorsel dosya kullanilmiyordu. Yer tutucu, ana arayuzun ust barindaki logonun aynisiyla degistirildi ve yuksekligi o barla ayni tutuldu. Ucus duvarinin stil dosyasi tema dongusune KASITLI olarak girmez (ucus gostergeleri acik zeminde okunamaz, ikinci ekran karanlik ortamda izlenir), bu yuzden tema degiskeni sokulmadi ve renk mimarisine dokunulmadi",
      "UCUS DUVARI VE VIDEO DUVARI SAYFALARININ ONBELLEK ETIKETLERI 19 SURUM GERIDE KALMIS DURUMDAYDI. Yayin akisi yalnizca ana arayuzun etiketlerini tazeliyordu; bu iki sayfa 2.4.67 etiketinde donmus kalmisti ve kullanicilarin tarayicisi o surumden beri eski stil ile betik dosyalarini onbellekten servis ediyor olabilirdi. Bu, yapilan duzeltmelerin kullaniciya hic ulasmamasi anlamina gelir — duzeltme dogru olsa bile kusur surer. Yayin akisi artik uc sayfayi birlikte esitliyor"
    ]
  },
  {
    s: "2.4.86", t: "2026-08-18",
    b: "Veritabani Ayarlari menusu erisim kipi + dugme cakismasi duzeltmesi",
    m: [
      "VERITABANI AYARLARI MENUSU ARTIK YALNIZCA KAPALI DEVRE KURULUMDA GORUNUYOR. Menu ogesi onceden yalnizca ROLE gore gosteriliyordu; bulut kullanicisi da yonetici oldugu icin ogeyi goruyor, tikladiginda ise sunucu komutu reddediyordu — yani oge GORUNUR ama ISLEVSIZ idi. Gorunurluk kurali artik uc kosula bagli: rol yonetici, merkez kipi bayragi ALINMIS ve bayrak kapali. Bayrak hic gelmemisse oge GIZLENIR (guvenli taraf). Merkez kipi bayragi yalnizca pg_durum yanitinda geldigi icin gorunurluk tazelemesi o bayragi tutan modulde yasiyor",
      "IKON VE METIN TASIYAN 27 DUGMENIN UST USTE BINMESI GIDERILDI. Dugme birligi sozlesmesindeki yalniz-ikon kurali, ikonun yaninda DUZ METIN tasiyan dugmeleri de yakaliyordu; CSS metin dugumunu goremedigi icin bu dugmeleri 26 piksellik kareye sikistiriyor, metin ise satir kirilmasi kapali oldugu icin kutunun disina tasip komsu dugmenin uzerine biniyordu. IPTAL ile KAYDET dugmelerinin ust uste gorunmesinin nedeni buydu. Duzeltme CSS kuralina DOKUNMADI; bunun yerine 27 noktada ikon sonrasi metin bir kapsayiciya alindi, boylece kural onlari artik yalniz-ikon saymiyor. Etkilenen yerler: ana arayuz (5), joystick ayarlari (4), suru ucusu (4), ucus gecmisi (3), koridor (3), serbest form (3), pilot hakkinda (2), angajman izleme, dron konsolu ve rol yonetimi (1'er)"
    ]
  },
  {
    s: "2.4.85", t: "2026-08-18",
    b: "Ust bar ekleme dugmeleri gorunur kilindi; tema degiskeni kirilmasi onarildi",
    d: [
      "KUSUR: Kameralar ve Rotalar panellerindeki ekleme dugmeleri " +
      "(YENI KAMERA, YENI ROTA, VIDEO DUVARI, ONIZLEME GORUNUMU) " +
      "`gizli-tasindi` sinifi tasidigi icin `display:none !important` " +
      "ile KALICI gizliydi. Hicbir betik bu sinifi kaldirmiyordu. " +
      "Dugmeler DOM'da vardi ve olay dinleyicileri bagliydi, ancak " +
      "kullanici onlari hic gormuyordu. Dort dugmeden sinif kaldirildi; " +
      "kasitli gizli alti oge (program ayarlari, rol yonetimi) korundu.",
      "KUSUR: App katmaninda TANIMSIZ 9 tema degiskeni yedeksiz " +
      "`var()` ile kullaniliyordu: --siyan (5), --kenar (18), " +
      "--zemin2 (11), --zemin1, --perde, --golge2, --kart-arka, " +
      "--baslik-renk (2), --basari. Toplam 41 bildirim tarayici " +
      "tarafindan SESSIZCE dusuruluyordu. En agir sonuc " +
      "panel_ustbar.css icindeki ust bar etkin dugme bicimlendirmesi " +
      "(kenarlik + arka plan + metin rengi) ve Dron Bakim penceresi " +
      "giris alanlariydi. Merkez sozlesmesi takma adlari olarak " +
      "tanimlandi; v2.4.35 (--vurgu) ve v2.4.41 (--girdi) ile ayni desen.",
      "HARITA: Bagli dron gorunum disinda kaldiginda ekran kenarinda " +
      "yon gostergesi ve mesafe bilgisi cikar; tiklaninca drona " +
      "odaklanir. Ilk dron odagi dali onarildi: pilotun kendi kayitli " +
      "gorunumu yoksa ilk bagli drona odaklanilir, varsa kullanici " +
      "tercihi ezilmez ve kenar gostergesi devreye girer.",
      "DERS: App ve Merkez farkli tema sozlesmeleri kullanir. Bir " +
      "katmandan digerine CSS kopyalanirken degisken adlari CEVRILMEK " +
      "zorundadir. Bu tuzaga ucuncu kez dusuldu; artik takma adlar " +
      "tanimli oldugu icin her iki sozlesme de App icinde gecerli.",
      "DERS: Kod icinde capa saymak bir ozelligin calistigini " +
      "kanitlamaz. `display:none !important` tasiyan bir dugme kodda " +
      "vardir ama kullanici icin yoktur. Gorsel ozelliklerde " +
      "gorunurluk ayrica olculmelidir."
    ]
  },
  {
    s: "2.4.84", t: "2026-08-18",
    d: [
      "\"SUNUCU BAGLANTISI YOK\" HATASI GIDERILDI. `app.goktungu.com` uzerinden girildiginde arayuz sunucuya hic baglanamiyordu; servisler ayakta, TLS gecerli ve sayfa 200 donuyor olmasina ragmen durum gostergesi kopuk kaliyordu.",
      "KOK NEDEN: baglanti tuneli secimi sayfanin YOLUNA bakiyordu (`/app/` ile baslıyor mu). Alt alan adi gecisinden sonra arayuz `app.goktungu.com/` KOK yoldan sunulmaya baslandi ve bu kosul artik saglanmiyordu. Istemci yanlis dala dusup 9443 portunun KOK yoluna baglaniyordu; orasi KOPRU protokolune ayrilmis bir uctur ve arayuz mesajlarini tanimaz.",
      "OLCULEN KANIT: WS el sikismasi her iki yolda da 101 donuyor, bu yuzden yuzeysel denetim kusuru gormuyordu. Uygulama katmani olculdugunde kok yolun `Ilk mesaj merhaba olmali` hatasi dondugu, `/app/ws` yolunun ise `portlar`, `ayarlar`, `baglanti_listesi` mesajlarini gonderdigi goruldu.",
      "DUZELTME: tunel secimi artik KONAK temellidir. Sayfa `/app/` yolundan ya da `app.` alt alan adindan gelsin, ayni tunel kullanilir ve baglanti sayfanin geldigi adres ve port uzerinden kurulur. Boylece standart disi portlari kapatan mobil operator aglarinda da baglanti kurulur.",
      "Ayni kusur ucus duvari penceresinde de vardi (`flight.js`); o da ayni sozlesmeye baglandi.",
      "GERI KALAN 9443 DALI KORUNDU ama artik kok yol yerine arayuz vekili yolunu kullanir: kapali devre Merkez Uygulama kurulumlarinda (IP/localhost, alt alan adi yok) davranis bozulmaz.",
      "ONBELLEK ETIKETLERI TEK DEGERE ESITLENDI. Onceki iki yayinda etiketler yalnizca degisen dosyalarda guncellenmisti; ayni sayfada uc ayri etiket bulunuyordu. Bu durumda duzeltilen bir dosya tarayici onbelleginden eski haliyle okunabilir ve guncelleme kullaniciya hic ulasmaz."
    ]
  },
  {
    s: "2.4.83", t: "2026-08-18",
    d: [
      "KURUMSAL PANELDE GIRIS YAPAN KULLANICI ARTIK APP'TE YENIDEN PAROLA SORULMAZ. Kullanici `company.goktungu.com` uzerinde oturum acip App'e gectiginde giris perdesi yeniden aciliyordu.",
      "KOK NEDEN 1 (CEREZ ETKI ALANI): merkez oturum cerezi `Domain` niteligi OLMADAN yaziliyordu. Nitelik yoksa tarayici cerezi yalnizca onu yazan konaga baglar; `company.goktungu.com` cerezi `app.goktungu.com` isteginde HIC GONDERILMEZ. Cerez artik kok alan adina (`.goktungu.com`) yazilir, boylece tum paneller ayni oturumu gorur.",
      "KOK NEDEN 2 (AYRI KAYNAK): iki panel ayri kaynak oldugu icin `localStorage` da paylasilmaz; App kendi sakli oturumunu bulamiyordu. App'e yeni bir devir ucu eklendi: tarayicinin tasidigi kurumsal cerez merkez oturum tablosunda dogrulanir ve gecerliyse bir App jetonu uretilir.",
      "MEVCUT GIRIS AKISI DEGISMEDI. Devir yalnizca sakli oturum YOKKEN denenir; uretilen jeton normal sakli oturum kaydi olarak yazilir ve bilinen `jeton_giris` yolu isler. Basarisiz devir bir kez denenir, sonsuz yeniden deneme dongusu olusmaz.",
      "MERKEZ KULLANICISI YEREL TABLODA OLMASA DA OTURUM ACILIR. Jeton cozumu yalnizca yerel kullanici tablosuna bakiyordu; kurumsal panelden gelen ve App'te henuz kaydi olmayan kullanici icin dususe geciyordu. Cozum merkez tablosuna duser, rol ve firma kimligi parolayla girise BIREBIR AYNI bicimde uretilir.",
      "KAPALI DEVRE KURULUM KORUNDU. Cerez etki alani yalnizca `.goktungu.com` sonekli konaklarda yazilir; IP veya `localhost` uzerinde calisan Merkez Uygulama etkilenmez. Devir ucu merkez kipi kapaliysa 404 doner ve istemci sessizce eski akisa devam eder.",
      "CIKIS DA AYNI ETKI ALANINDAN SILER. Cerez kok alan adina yaziliyorsa silme dizesi ayni nitelikle gonderilmek zorundadir; aksi halde tarayicida silinmeyen bir oturum cerezi kalirdi.",
      "AKTIF AI IZLEMELERI BOS DURUMU IKONLU KUTUYA CEVRILDI. Panel ust bari ve bos durum standardinin geride kalan tek yeriydi; duz gri metin yerine artik buyuk ikonlu kutu gelir. Ikon `fa-eye` secildi: ayni pencerede sunucu listesi `fa-server` kullanir, ayni ikon iki bolumde tekrarlanirsa hangi listenin bos oldugu ayirt edilemez.",
    ],
  },
  { s: "2.4.82", t: "2026-08-18", d: "AI paneli ve tespit gecmisi merkez kipinde acilmiyordu: saha vekili, sunucu katmaninin cagirdigi 17 yontemin yalniz 3'unu tasiyordu. Eksik 14 yontem tamamlandi — veritabani isleri tek kaynaktan devralindi, saha erisimi gerektiren uc yontem (hedef takibi, yuz vektoru) kopruye devredildi. Saglik durumu artik kopruden turetiliyor." },
  { s: "2.4.81", t: "2026-08-18", d: "Panel ust barlari birlestirildi: Kisiler, Araclar, AI Sunuculari, Kayitsiz Tespitler ve Tespit Gecmisi panellerinde ekleme dugmeleri ve filtreler govdeden ust bara tasindi (Kameralar/Rotalar deseni). Suru Ucus kurulumunda SLAVE EKLE ve SURUYU BASLAT ust bara alindi. Bos durumlar duz gri metin yerine 64px ikonlu kutuya cevrildi (Kisiler, Araclar, Kayitsiz Tespitler, Tespit Gecmisi, AI Sunuculari, Baglanti Yoneticisi). Kamera tipleri ikonlu dugme kumesi olarak eklendi; protokol listesi erisilebilirlik icin korundu." },
  { s: "2.4.80", t: "2026-08-18", d: "Dronlar > Gecmis Yonetimi menusu duzeltildi: menu bagi var olmayan tbDronGecmis dugmesine tiklamaya calisiyordu, artik gecmis paneli dogrudan aciliyor." },
  { s: "2.4.79", t: "2026-08-18", d: "Harita acilis konumu PILOT BAZINDA saklanir; ilk girise kurumsal adres ve Gokkubbe isareti geldi. Genel ayar duyurusu artik pilotun kendi gorunumunu ezmez (radar merkezi islevi korunur)." },
  {
    s: "2.4.78", t: "2026-08-18",
    d: [
      "DRON PARAMETRE DUZENLEMESI ARTIK GERCEK BIR ACILIR KUTU. Bir parametreye tiklandiginda liste kayboluyor, yerine ayni pencerenin icinde tam kaplayan bir katman geliyordu; bu bir acilir kutu degil YERINDE EKRAN DEGISIMIYDI.",
      "KOK NEDEN: duzenleme ortusu `_paramPopupEl` icine ekleniyor ve `position:absolute; inset:0` ile parametre penceresini tamamen kapliyordu. Ortu artik govdeye eklenir ve `position:fixed` perde olarak davranir; liste arkada gorunur kalir.",
      "AYNI KUTU IKI FARKLI DAVRANIS GOSTERIYORDU: parametre listesinden acildiginda pencere icine hapsoluyor, ARM denetimi ekranindan acildiginda (o yolda kapsayici tanimsiz oldugu icin) serbest kaliyordu. Tek yola indirildi.",
      "KAPATMA (X) DUGMESI EKLENDI. Kutunun tek cikisi IPTAL dugmesiydi; kullanici basliktaki kapatma dugmesini arayip bulamiyordu.",
      "KACIS (Esc) TUSU ILE KAPANMA EKLENDI. Uc cikis yolu (X, IPTAL, Esc) tek kapatma islevinden gecer; dinleyici kutu kapandiginda kaldirilir, govdede birikmez.",
      "KUTU TASINABILIR YAPILDI. Pencere evreninin kendi surukleme altyapisi kullanildi; basliktaki dugmeler surukleme baslatmaz.",
      "GENISLIK 340px'DEN 520px'E CIKARILDI. Aciklama metni, min/maks/artis/birim satiri ve secenek listesi 340px'te sikisiyordu.",
      "PERDE TIKLAMASI KUTUYU KAPATMAZ. Yalniz X, IPTAL ve Esc kapatir; yanlislikla perdeye tiklandiginda girilen deger kaybolmaz.",
    ],
  },
  {
    s: "2.4.77", t: "2026-08-18",
    d: [
      "Tum paneller ilk acilista ekranin ortasinda ve en az 500x400 px olcusunde acilir.",
      "Kok neden: arayuzde ortalama sozlesmesi yoktu; 40'tan fazla pencere kendi CSS sabitini tasiyordu (200px mini kutu, 320px bolum penceresi left:120px/top:90px, 760px gecmis penceresi). Yalniz bir pencere gercekten ortaliydi.",
      "Cozum tek noktada: popup_tasima.js'in kurdugu pencere evreni (PENCERE_SECICI) yeniden kullanilir; 40 CSS kurali elle degistirilmedi.",
      "Kullanici tercihi ustundur: bir pencere bir kez tasindiktan veya boyutlandirildiktan sonra kendi kayitli konumunda acilir.",
      "Fare yaninda acilan baglam pencereleri (telemetri, kip, GPS, batarya, kamera secimi, islemler) dislandi; buyutulseler ekrani kaplar ve islevleri bozulurdu.",
      "Dar ekranda sigdirma yapilir: pencere gorunur alani asmaz, baslik cubugu her zaman tutulabilir kalir.",
    ],
  },
  {
    s: "2.4.76", t: "2026-08-18",
    d: [
      "TUM DUGMELER TEK OLCUYE VE TEK BICIME BAGLANDI. Arayuzdeki 181 dugmenin bicimi zaman icinde dagilmisti: olculen dagilim 46 ayri yastik degeri, 13 ayri yazi boyu, 11 ayri yukseklik ve 8 ayri kose yuvarlakligiydi. Ayni islevi goren iki dugme -- baglanti yoneticisindeki SANAL ile AI panelindeki YENI SUNUCU -- yan yana konunca biri otekinin neredeyse iki kati cikiyordu",
      "KOK NEDEN: ORTAK GORUNEN SINIF ADLARI ASLINDA ETKISIZDI. `onay-btn` gibi paylasilan sinif adlari yalnizca DAR kapsamlarda tanimliydi; o kapsamlarin disinda ayni sinifi tasiyan dugmeler hicbir kural almiyor, temel dugme kuralina dusuyordu. Yani sinif adi ayniydi ama gorunum farkliydi",
      "SINIF SINIF DUZELTME YERINE TEK DUGME SOZLESMESI KURULDU. 46 ayri yastik degerini elle esitlemek surdurulemez oldugundan sozlesme ayri bir bicim dosyasina yazildi ve ana bicim dosyasindan SONRA yuklendi; art arda gelme kuraliyla onceki tum olcu bildirimlerine ustun gelir. Sozlesme degerleri kullanicinin isaret ettigi kompakt bicimden alindi",
      "YALNIZ-IKON DUGMELERI AYRI ELE ALINDI. Olculdu: dugmelerin 49u metin tasimiyor (kapatma, oynat, sil, tam ekran). Bunlara metinli sozlesmenin yatay yastigi uygulanirsa yayvanlasirlar; kare kalmalari icin yastik sifirlandi ve kenar sabitlendi",
      "YUKSEKLIK SABITLENMEDI, TABAN VERILDI. Sabit yukseklik yazi tipi buyutuldugunde ya da metin iki satira dustugunde tasmaya yol acar; bunun yerine en az yukseklik verildi ve yukseklik icerige birakildi",
      "ISLEVI BOYUT GEREKTIREN DUGMELER SOZLESMEDEN DISLANDI: tam genislikteki ana baglan dugmesi, tema segment secici, kumanda ve oyun kolu tuslari, ucus kipi kareleri, sekme basliklari, istasyon LED gostergeleri ve haritanin kendi arayuzu. Bu dugmeler kucultulse dokunma hedefi ya da izgara duzeni bozulurdu",
      "SOZLESME DEGERLERI DEGISKENE BAGLANDI. Ileride dugmeler topluca buyutulmek ya da kucultulmek istenirse tek bir blok degisir; 181 dugme birlikte olceklenir",
      "ARAC CUBUGU KUMELERINDE BOSLUK DA BIRLESTIRILDI. Dugmeler ayni olcude olsa bile aralari 4px ile 10px arasinda degisiyordu; kume dagimik gorunuyordu",
    ],
  },
  {
    s: "2.4.75", t: "2026-08-18",
    d: [
      "SANAL DRON SIHIRBAZI HAZIRLIK ADIMINDA KILITLENIYORDU. Sunucu tarafinda benzetim dosyasi durumunu bildiren yol, sinifta BULUNMAYAN bir gonderme yontemini cagiriyordu; istek islenip yanit uretiliyor ama istemciye HIC gonderilmiyordu. Arayuz yaniti bekledigi icin \"Benzetim dosyasi denetleniyor...\" carki sonsuza donuyor, ayni anda uyari merkezinde komut hatasi goruluyordu. Gonderme cagrisi sinifin gercekte kullandigi desene cevrildi",
      "SIHIRBAZ ARTIK SUNUCUNUN YANIT VERECEGINE KOSULSUZ GUVENMIYOR. Durum sorgusu icin 12 saniyelik zaman asimi eklendi: sure icinde yanit gelmezse hata durumuna gecilir ve YENIDEN DENE dugmesi gosterilir. Bu koruma yanitin HANGI nedenle gelmediginden bagimsiz calisir -- uc kusuru, yetki reddi ya da agin kopmasi olsun, kullanici donen carki izlemek zorunda kalmaz",
      "SUNUCU SINIFININ TUM YONTEM CAGRILARI SOYUT SOZDIZIMI AGACI UZERINDEN DENETLENDI. Sinifta 117 yontem tanimli; cagrilip tanimsiz olan tek ad bu kusurun kaynagiydi. Kalan tanimsiz gorunen adlar ya miras alinan HTTP islevleri ya da baska nesneler uzerindeki cagrilar oldugu dogrulandi",
    ],
  },
  {
    s: "2.4.74", t: "2026-08-18",
    d: [
      "SIHIRBAZ ADIM 2'DE BAGLANTI ACIKKEN 'SUNUCU BAGLANTISI YOK' UYARISI CIKIYORDU. Denetim `window.ws` uzerinden yapiliyordu; bu yansitma yalnizca KAYDET dugmesine basildiginda atanan bir degerdi, yani sihirbaz o adima geldiginde HENUZ TANIMSIZDI. Uygulama bagliyken sihirbaz kendini kopmus saniyordu. Artik `ws.js` icinde tanimlanan `wsCanli()` cozucusu kullaniliyor: her cagrida guncel WebSocket nesnesi okunur. Yansitma yerine cozucu secildi cunku yansitma her yeniden baglanmada bayatlar -- baglanti koptugunda yeni nesne olusturulur ve eski yansitma kapanmis nesneyi gostermeye devam ederdi",
      "YENIDEN DENE DUGMESI HIC GORUNMUYORDU. Kod dugmeyi gostermeye cabaliyordu ama CSS sinifinda `display:none` vardi ve gosterme yolu satir ici bildirimi BOSALTIYORDU; bos bildirim sinif kuralini ezmez, aksine onu yeniden yururluge sokar. Gorunurluk artik `hidden` niteligiyle yonetiliyor. Kullanici bagli olmadigi durumda uyarinin yaninda yeniden deneme yolu goruyor",
      "SIHIRBAZ KUTUSU BUYUTULDU: 360 piksel yerine 620 piksel. Bagalanti ekleme kutusunun genisligi seri, TCP, UDP ve DJI kipleri icin dogru oldugu icin o deger DEGISTIRILMEDI; genislik yalnizca sihirbaz kipinde eziliyor. Arac tipi kartlarinin gorselleri 40 pikselden 56 piksele, yazilari 10 pikselden 12 piksele buyutuldu; adim govdesinin en az yuksekligi 108 pikselden 168 piksele cikti",
      "GEZINME DUGMELERI STANDART DUZENE ALINDI: GERI solda, ILERI sagda. Onceki duzen ikisini esit genislikte yan yana koyuyordu; tek dugme kalan adimlarda kalan dugme yatay olarak KAYIYORDU. Gizleme artik yer tutan bicimde yapiliyor, dugmeler kenarlarda sabit duruyor",
      "IPTAL DUGMESI SIHIRBAZ KIPINDE KALDIRILDI. Kutunun basliginda kapatma (X) dugmesi zaten var ve kapatmak iptal etmekle ayni sey; iki ayri iptal yolu gereksiz yer kapliyordu. Diger baglanti kiplerinde IPTAL dugmesi DURUYOR",
    ],
  },
  {
    s: "2.4.73", t: "2026-08-18",
    d: [
      "HARITA AYARLARINDAN PRIZMA IKON SECENEGI KALDIRILDI. Harita Ayarlari > Prizma Ikonlar (3B) anahtari dusuruldu. Prizma artik TEK ve degistirilemez gorunumdur: dron, radar hedefi ve istasyon ikonlari her zaman uc boyutlu cizilir.",
      "Gerekce: prizma zaten varsayilan ve onerilen gorunumdu; anahtar yalnizca daha kotu goruntuye gecis sunuyordu. Kullanici istegi uzerine secenek butunuyle kaldirildi.",
      "Eski tarayici kaydi (gcs_prizma_ikon) TEMIZLENIR. Aksi halde daha once duz simgeye gecmis bir tarayici, anahtar artik gorunmese de duz simge cizmeye devam ederdi. Bu, v2.4.70 sirasinda gcs_logo anahtarinda olculen sinif kusurun aynisidir.",
      "Cizim govdesi (prizma geometrisi, elmas bicimleri, radar-GCS ok prizmasi, alfa ayari) DEGISMEDI; yalnizca kip anahtari ve ona bagli varlik-yeniden-cizim yolu kaldirildi. Ikonu cizen uc dosyaya (dronlar.js, hedefler.js, radar_gorsel.js) hic dokunulmadi."
    ]
  },
  {
    s: "2.4.72", t: "2026-08-18",
    d: [
      "SANAL DRON OLUSTURMA SIHIRBAZI. Oncesinde sanal dron eklemek icin duz bir form vardi ve gerekli benzetim dosyasi eksikse play dugmesine basildiginda hata cikip hata kutusunun icinde bir indirme dugmesi belirirdi; kullanici once basarisizligi gormek zorunda kaliyordu. Artik uc adimli sihirbaz var: (1) resimli arac tipi secimi, (2) hazirlik adimi, (3) ad ve kalkis parametreleri. Kaydedilince dron olusur ve OTOMATIK BASLATILIR",
      "HAZIRLIK ADIMI GEREKSIZ INDIRME YAPMIYOR. Adim once tipe OZGU denetim yapiyor: coklu pervaneli, alti pervaneli, helikopter ve onleyici AYNI ucus yazilimini paylasir, dolayisiyla biri kuruluysa digerleri de hazirdir ve adim onay verip geciyor. Onceki denetim iki ikiliyi birlikte arayip biri eksikse tumunu eksik sayiyordu; coklu pervaneli secen kullanici, hic kullanmayacagi sabit kanat dosyasi yuzunden indirmeye zorlaniyordu",
      "INDIRME ARTIK ILERLEME CUBUGU GOSTERIYOR. Onceden yalnizca 'indiriliyor, bekleyin' yaziyordu ve dakikalarca hicbir gosterge degismiyordu; kullanici programin takildigini saniyordu. Kaynak sunucu Content-Length dondurdugu icin kesin yuzde gosterilebiliyor; baslik gelmezse belirsiz cubuk cizilir. Duyuru sayisi saniyede dorde kisildi, son blok kismadan bagimsiz gecer -- yoksa cubuk %97'de asili kalirdi",
      "ARAC TIPI KATALOGU ALTIYA CIKTI: coklu pervaneli, alti pervaneli, helikopter, sabit kanat, VTOL, onleyici. Uc yeni tip EK INDIRME GEREKTIRMIYOR; ayni ucus yaziliminin farkli govde modelleridir",
      "YANILTICI DOSYA BOYUTU DUZELTILDI. Arayuz '~30 MB' diyordu; olculen gercek boyut ~7 MB. Kullaniciya verilen sure beklentisi dort kat sisirilmisti",
      "TIP SECIMI ARTIK SESSIZCE BOSA DUSMUYOR. Katalog genisledigi halde eski uc secenekli liste duruyorsa yeni tip listeye eklenir; eklenmezse deger atamasi sessizce bosa duser ve kullanici helikopter secmis olmasina ragmen coklu pervaneli dron olusurdu (v2.4.37'de baud alaninda ayni sinif kusur olculmustu)",
      "DUZENLEME MODU SIHIRBAZA SOKULMUYOR. Var olan bir sanal dronun yalnizca adini degistirmek isteyen kullanici uc adimli akisa zorlanmiyor; eski form dogrudan aciliyor",
    ],
  },
  {
    s: "2.4.71", t: "2026-08-17",
    d: [
      "BASILI UCUS BELGELERINDEKI ANTET ESKI URUN ADINI TASIYORDU. Ucus raporu ve ucus grafigi yazdirildiginda antette 'GOKTUNGU GCS v...' yaziyordu. Kalinti duz metin olarak degil KACIS DIZISI olarak yazilmisti (G\\u00d6ZC\\u00dc); onceki marka gecisinin duz metin taramasi bu yuzden gormedi. Musteriye ciktisi verilen belgede eski marka gorunmesi, arayuzde gorunmesinden daha agir bir kusurdur cunku belge kurumdan disariya gider",
      "POSTGRESQL KURULUM SIHIRBAZININ ALT BASLIGI ayni kacis dizisi biciminde eski adi tasiyordu",
      "INGILIZCE ARAYUZDE UC KALINTI DUZELTILDI: menu ogesi adi 'Goktungu', DJI kopru aciklamasinda 'GOKTUNGU Android bridge' ve sihirbaz metninde 'store GOKTUNGU data'. Turkce karsiliklari zaten dogruydu; bu, i18n sozluklerinin ayri ayri denetlenmesi gerektigini gosteriyor",
      "YEDEK DOSYA SIZINTISI KAPATILDI (GUVENLIK). Gecis sirasinda web koku icinde birakilan 13 `.adbak` dosyasi ve iki panel yedek dizini HTTP 200 ile sunuluyordu; icerdikleri eski marka, eski alan adi, yururlukten kalkmis KVKK metni ve panel kaynak kodu herkese acikti. Bu sunucuda nginx YOK -- statik dosyalari Python sureci sunuyor ve nginx'in ontanimli 'yedek uzantisini sunma' korumasi burada bulunmuyor. Dosyalar arsive tasindi VE sunucuya desen engeli eklendi; engel 404 doner cunku 403 dosyanin varligini dogrulayip saldirgana harita cizerdi",
      "KOPRU KAYIT ACIKLAMASI VERITABANINDA DUZELTILDI. Baglanti Yoneticisi'nde listelenen kopru 'GOKTUNGU Kopru Yazilimi' olarak gorunuyordu; bu metin koprunun merkeze kaydolurken gonderdigi degerin veritabanina yazilmis haliydi",
      "KATALOGDAN ESKI SURUM KAYITLARI DUSURULDU. Kurumsal panelin 'Onceki surumler' bolumunde 13 tane `GOKTUNGU-Kopru-Setup-*.exe` gorunuyordu. Dosya adlari DEGISTIRILMEDI cunku diskteki gercek adlardir ve degistirilmesi indirme baglantilarini kirardi; kayitlar `etkin=FALSE` yapildi. Sahada CANLI BAGLI kopru surumu (1.5.8) kasitli olarak ETKIN BIRAKILDI: otomatik guncelleme akisi katalog uzerinden yurudugu icin dusurulmesi o koprunun guncelleme yolunu kapatirdi",
    ],
  },
  {
    s: "2.4.70", t: "2026-08-17",
    d: [
      "URUN ADI ARTIK GOKTUNGU. GOKTUNGU adi arayuzden tamamen kaldirildi: sekme basligi, ust serit basligi, menu ogesi, ucus duvari basligi, PWA uygulama adi ve Program Hakkinda penceresi yeni ada cekildi. Teknik kimlikler DEGISMEDI -- servis adi (goktungu-app), oturum anahtari (goktungu_oturum), sunucu basligi (X-Goktungu-Hata), dosya yollari ve Python paket adi ayni kaldi; bunlar marka degil calisan sistemin kimligidir ve degistirilmesi oturumlari ve servisleri kirardi",
      "FIRMA LOGOSU DONGUSU KALDIRILDI. Program Hakkinda penceresindeki logoya CTRL + tiklandiginda uc firma logosu arasinda donuluyordu (GOKKUBBE, VEILOX, NOVIXAIR). Artik firma logosu kullanilmiyor; yalnizca GOKTUNGU urun logosu gosteriliyor. Firma adi tek yerde geciyor: sahiplik satiri. Donguden kalan secim tarayicida durabilecegi icin `gcs_logo` yerel kaydi da temizleniyor -- aksi halde bu anahtari okuyan bir kod eski firma logosunu geri yazabilirdi",
      "LOGO ARTIK TEMAYLA BIRLIKTE DEGISIYOR. Koyu temada acik yazili, acik temada koyu yazili surum gosteriliyor; tema anahtari degistiginde logo ayni anda degisir. Koyu temada logolara uygulanan beyaz parlama suzgeci kaldirildi: eski firma logolari koyu ve renkli oldugu icin gerekliydi, yeni logonun koyu tema surumu zaten acik yazili uretildi ve ayni suzgec yaziyi dagitip okunurlugu dusuruyordu",
      "SAHIPLIK SATIRI TAM UNVANA CEVRILDI: 'Gokkubbe Teknoloji Anonim Sirketi'. Kisaltilmis yazim yerine ticaret sicilinde kayitli tam unvan kullaniliyor",
      "YETKI METNINDEKI MARKA ADI ROL ADINA CEVRILDI. Radar ve Yer Kontrol Istasyonu Dual yetkisini anlatan surum kaydinda 'yalnizca VEILOX ust yoneticisi acar' yaziyordu; artik boyle bir marka olmadigi icin bu ibare yetki seviyesini anlatmak yerine marka gibi okunuyordu. Metin 'yalnizca ust yonetici acar' oldu. Koddaki `veilox` yetki anahtari DEGISMEDI",
      "KURUM UNVANI ORNEK METNI GUNCELLENDI. Sirket bilgileri formundaki unvan alaninin ornegi eski firma adini gosteriyordu",
    ],
  },
  {
    s: "2.4.69", t: "2026-08-16",
    d: [
      "KURULUM SIHIRBAZI VERITABANI KURULUMUNDAN SONRA KENDINI KAPATIYOR VE YONETICI HESABI HIC SORULMUYORDU. Kullanicinin bildirdigi 'merkez yazilimina hicbir sifreyle giremiyorum' sorununun asil kaynagi buydu. Tablolar basariyla kuruldugunda sihirbaz sunucuya durum soruyor, sunucu 'yapilandirildi' yanitini veriyor ve bu yanit sihirbazi kapatan dala giriyordu. Dorduncu adim (merkez kullanicilarini aktarma) ve besinci adim (kendi yonetici hesabini olusturma) EKRANA HIC GELMIYOR, kullanici dogrudan giris ekranina dusuyor ve elinde hicbir gecerli kimlik olmuyordu",
      "SIHIRBAZ ARTIK KURULUM BITINCE KIMLIK ADIMINA GECIYOR. Kurulum kipinde otomatik kapanma kaldirildi; tablolar kurulduktan sonra sihirbaz kendiliginden dorduncu adima gecer. Merkeze erisimi olan kullanici mevcut hesaplarini aktarabilir, kapali devre kurulumda ise 'Atla' ile besinci adima gecip kendi e-postasini ve sifresini belirler. Goc kipinde eski davranis korundu: guncelleme bitince sihirbaz kapanir",
      "SIHIRBAZ ADIM AKISI ARTIK GERCEK JS OLARAK SINANIYOR. Onceki surumlerin yapisal sinavlari adim 5 formunun KODUNU dogruluyordu, oysa kusur formun hic GOSTERILMEMESIydi; bu yuzden 103 olcumun tamami gectigi halde kusur canliya cikti. Yeni deney sihirbazi bir sahte tarayici icinde kosturur, sunucu yanitlarini sirayla besler ve her adimda perdenin ayakta olup olmadigini olcer",
    ],
  },
  {
    s: "2.4.68", t: "2026-08-16",
    d: [
      "KURULUM SIHIRBAZINDA ARTIK KENDI GIRIS BILGILERINIZI SIZ BELIRLIYORSUNUZ. Onceki surum rastgele uretilmis bir sifreyi ekranda GOSTERIYORDU; kullanici kendi sifresini secemiyor, gosterilen sifreyi bir yere not etmek zorunda kaliyordu. Daha kotusu, veritabani kurulumu bittiginde sihirbaz dogrudan giris sayfasina donuyor ve merkezde tanimli sifre kabul edilmiyordu. Besinci adim artik bir FORM: e-posta, ad soyad ve kendi sifrenizi girip yonetici hesabinizi olusturuyorsunuz. Bu adim merkeze HIC baglanmaz -- kapali devre kurulumun tek gereksinimi budur",
      "KURULUM HESABI ARTIK GERI DONUSSUZ KAPATILIYOR. Yonetici hesabi olusturuldugu anda rastgele sifreli gecici kurulum hesabi silinir ve sifresini iceren dosya kaldirilir; boylece kurulum sirasinda uretilmis hicbir kimlik sistemde kalmaz. Hesap olusturma ucu da ayni anda kapanir: bir kez gercek yonetici tanimlandiktan sonra ag uzerinden kimse bu yolla sifre degistiremez",
      "KOPRU YAZILIMI ILK ACILISTA KURULUM SIHIRBAZI GOSTERIYOR. Kapali devre kurulumda kilitli bir dongu vardi: koprunun hangi merkeze baglanacagini secebilmek icin once merkeze giris yapmis olmak gerekiyordu, oysa yerel merkeze baglanmak icin zaten bu secimin yapilmasi gerekiyordu. Kopru artik giristen ONCE merkez adresini soruyor. Yerel merkezin IP adresini yazmaniz yeterli: WebSocket ve HTTP adresleri dogru portlarla kendiliginden turetiliyor",
      "TUM ARAYUZLERE GUNDUZ/GECE DONGUSU GELDI. Kurumsal panel, yonetim paneli ve kopru arayuzu yalnizca koyu temada calisiyordu; gun isiginda saha kullaniminda okunmasi guctu. Uc arayuze de tema anahtari eklendi ve secim tarayicida saklanir. Anahtar giris ekraninda da bulunur, boylece tema icin once giris yapmak gerekmez",
      "KALKIS KONTROL LISTESINDE GORUNUM VE BASLIK BOZULMASI GIDERILDI. Kopru kimlikleri bolumu eklenirken kullanilan bazi adlar kalkis oncesi kontrol listesinin adlariyla cakisiyordu; listenin madde satirlarinin bicimi bozuluyor ve pencere basligi 'Kopru Kimlikleri' olarak gorunuyordu. Adlar ayristirildi",
    ],
  },
  {
    s: "2.4.67", t: "2026-08-16",
    d: [
      "MERKEZ UYGULAMA'YA HICBIR SIFREYLE GIRILEMIYORDU. Kok neden olculdu: giris basarili oldugunda sifre 'yukseltilmek' isteniyor, bu islem merkezden gelen ozetin uzerine YEREL bicimde yeni bir ozet yaziyordu. Ilk giris denemesinden sonra merkez sifresi kalici olarak bozuluyor, ikinci denemede ayni sifre artik taninmiyordu. Kullanicinin yasadigi 'once calisiyor sonra hic calismiyor' davranisinin sebebi buydu. Yukseltme artik yalnizca gercekten eski olan yerel bicimlere uygulaniyor; merkez ozetlerine dokunulmuyor",
      "KURULUM SIHIRBAZINDA URETILEN GIRIS BILGILERI ARTIK EKRANDA GOSTERILIYOR. Onceki surumde rastgele sifre yalnizca sunucu konsoluna ve bir dosyaya yaziliyordu; sihirbazi tarayicidan tamamlayan kullanici bu bilgileri hic gormuyor ve sisteme giremiyordu. Sihirbaza besinci adim eklendi: kurulum hesabinin e-postasi ve tek seferlik sifresi burada gosterilir. Merkez kullanicilari adimi ATLANDIGINDA da bu adim gosterilir -- kapali devre kurulumda tek giris yolu bu hesaptir",
      "KOPRU YAZILIMI YEREL MERKEZ UYGULAMASINA HIC BAGLANAMIYORDU. 5.000 dolarlik urunun kapali devre calisabilmesi bu baglantiya bagliydi. Iki ayri kusur vardi. Birincisi: yerel Merkez Uygulama'da koprunun baglanacagi ucun kendisi YOKTU; kopru bulut merkezine baglanabiliyor ama kendi sirketinin sunucusuna baglanamiyordu. Ikincisi: kopru, merkez adresinden HTTP adresini uretirken PORT bilgisini dusuruyor, boylece 8765 portundaki yerel merkez icin 80/443 portuna baglanmaya kalkiyordu",
      "YEREL MERKEZ UYGULAMA ARTIK KOPRU KABUL EDIYOR. Bulut merkezindeki el sikisma sozlesmesi bire bir uygulandi: ayni kopru ikilisi degistirilmeden hem buluta hem yerel merkeze baglanabilir. Kimlik dogrulama, oturum yonetimi, nabiz, istek/yanit ve telemetri yollari gercek kopru yazilimi ile ucdan uca sinandi",
      "MERKEZ UYGULAMA'YA KOPRU KIMLIKLERI BOLUMU EKLENDI. Saha bilgisayarlarina verilecek kimlikler Program Ayarlari icinden uretilir, listelenir ve iptal edilir. Kimligin gizli anahtari veritabaninda YALNIZ ozet olarak saklanir ve uretim aninda bir kez gosterilir; bu yuzden kutu kendi kendine kapanmaz. Bir kimlik iptal edildiginde o makinenin canli baglantisi da ayni anda dusurulur",
      "KOPRU AYARLARINA YEREL ADRES IPUCU EKLENDI. Adres alanina port yazilmadiginda baglanti sessizce reddediliyordu ve arayuz bunun nedenini soylemiyordu; kapali devre kurulumda dogru adres bicimi artik alanin altinda ornekle gosteriliyor",
      "KOPRUYU DURDURMA KOMUTU HER ZAMAN ISLEMIYORDU. Ajan yeniden baglanma beklemesindeyken verilen durdurma buyrugu bekleme bitene kadar goz ardi ediliyor, bu arada ajan bir kez daha baglanabiliyordu; operator koprunun durdugunu sanirken merkez onu canli goruyordu. Bekleme artik durdurma buyruguyla aninda kesiliyor",
    ],
  },
  {
    s: "2.4.66", t: "2026-08-16",
    d: [
      "MERKEZDE TANIMLANAN SIFRE ARTIK MERKEZ UYGULAMA'DA DA GECERLI. Kurulumu tamamlayan firma, kurumsal panelde belirledigi sifreyle giris yapamiyordu; yerine kaynak koda gomulu sabit bir sifre geciyordu. Iki ayri kusur ust uste binmisti: kurulum hesabi sabit bir sifreyle yaratiliyor, giris denetimi ise merkezin sifre bicimini hic tanimiyordu. Merkez sifreleri artik dogrudan taniniyor ve dogrulaniyor; yerel bicim de calismaya devam ediyor",
      "KAYNAKTA GOMULU SABIT SIFRE KALDIRILDI. Her kurulumda ayni bilinen sifre gecerliydi; kaynagi goren herkes 5.000 dolarlik urunun kurulumuna girebilirdi. Temiz kurulumda sisteme hic girilemez olmamasi icin hesap yine yaratilir, ancak sifresi her kurulumda kripto guvenli bicimde RASTGELE uretilir ve yalnizca kurulum konsoluna ve yalniz sahibinin okuyabildigi bir dosyaya yazilir",
      "KURULUM SIHIRBAZINA MERKEZ KULLANICILARI ADIMI EKLENDI. Kurumsal panelde tanimli kullanicilar ve sifreleri tek adimda yerel kuruluma alinir; boylece merkezde ne tanimlandiysa sahada da o gecerli olur. Adim ATLANABILIR: kapali devre kurulan sistemler internet baglantisi olmadan kuruluma devam edebilir",
      "MERKEZ UYGULAMA ICINDEKI KURUMSAL PANEL BAGLANTISI CALISMIYORDU. Sahaya kurulan yazilim kurumsal panel dosyalarini icermez -- icermesi de dogru olmazdi, cunku panel merkezdeki canli veriyle calisir. Baglanti artik kullanicinin kendi merkez adresine yonlendiriliyor; merkez adresi tanimli degilse ne yapilmasi gerektigini anlatan bir aciklama gosteriliyor",
      "KOPRU YAZILIMI ARTIK KURUMSAL PANELDEN INILIYOR. Panelde hicbir indirme baglantisi yoktu; kullanici koprunun nereden inecegini bulamiyordu. Panele Kopru Yazilimi bolumu eklendi ve Windows ile Ubuntu paketleri oradan iniyor. Kopru UCRETSIZ kalmaya devam ediyor; lisans sarti yoktur, yalnizca giris yapilmis olmasi yeterlidir",
      "PAKETLER ARTIK YALNIZCA UYE PANELINDEN INIYOR. Onceden dosya adini bilen herkes indirebiliyordu; tanitim sayfasinda da eskiyen surum baglantilari kalabiliyordu. Statik indirme yolu kapatildi, boylece kimin hangi paketi indirdigi kayit altina aliniyor",
      "KOPRU GUNCELLEMESI SAHADA HIC GORUNMUYORDU. Depoda 1.5.6 yayinlanmis olmasina ragmen guncelleme ucu 'guncel' yanitiyla 1.2.1 bildiriyordu. Kok neden olculdu: surum arama isletim sistemine gore suzuluyor, isletim sistemini bildirmeyen istemci icin ise yalnizca eski ortak kayitlar goruluyordu. Kopru paketleri 1.3.0'dan beri Windows ve Ubuntu icin ayri yayinlandigindan hicbir yeni surum bulunamiyordu. Ayni nedenle kurulum paketi sorgusu da bos donuyordu",
      "AYNI SORGU ARTIK HER ZAMAN AYNI PAKETI DONDURUYOR. Ayni surum iki isletim sistemi icin kayitliyken hangisinin donecegi veritabaninin satir sirasina kaliyordu; istemci her acilista baska bir paket indirmeye kalkabilirdi",
    ],
  },
  {
    s: "2.4.65", t: "2026-08-15",
    d: [
      "UYELIK VE ROL YONETIMI ARTIK UYGULAMA ICINDEN YAPILMIYOR. Ayni kullanici iki ayri tabloda tutulabiliyordu: uygulama kendi yerel tablosuna yaziyor, merkez ise kendi tablosunu okuyordu. Sonuc, yoneticinin kullaniciyi listede GORDUGU halde o kullanicinin sisteme girememesiydi. Tum uyelik ve rol islemleri tek kapiya, kurumsal panele baglandi; uygulamadaki yazma yollari kapatildi ve kullanici panele yonlendiriliyor. Kendi profilini duzenleme (ad, unvan, sifre) yerinde kaldi",
      "RADAR VE YER KONTROL ISTASYONU DUAL MENULERI ARTIK YETKIYE BAGLI. Bu iki modul satista degildir; yalnizca ust yonetici sirket bazinda acar. Menuler ucuncu bir kaynagi da dikkate aliyor: merkez lisansi. Karar tek bir yerde verilir, boylece bir menunun acik otekinin kapali kalmasi mumkun degil",
      "YETKI DENETIMI YALNIZ ARAYUZDE DEGIL SUNUCUDA DA UYGULANIYOR. Menuyu gizlemek tek basina yetersizdir: WebSocket komutu dogrudan gonderilebilir. Radar ve istasyon komutlarinin tamami (on uc komut) sunucudaki tek izin kapisinda lisansa karsi denetlenir; yetkisiz komut sessizce dusurulmez, gerekcesiyle uyari olarak bildirilir",
      "MERKEZ UYGULAMA KURULUMU ICIN IMZALI LISANS DOGRULAMASI EKLENDI. Lisans Ed25519 ile imzalanir ve dogrulama TAMAMEN CEVRIMDISI yapilir; kapali devre kurulumda internet gerekmez. Dogrulayici hem cryptography kutuphanesi hem de saf Python yedegiyle calisir; iki yol 240 sinama vektorunde ayni sonucu verdi. Firma kimligi, unvan ya da yetki alanlari elle degistirilirse imza gecersiz olur",
      "KOPRU VE MERKEZ UYGULAMA ARTIK AYNI BILGISAYARDA BIRLIKTE CALISABILIYOR. Iki yazilim MJPEG vekili icin 8801, yerel AI iscisi icin 8900 portunu SABIT kullaniyordu; ayni makinede ikisi birden calistirildiginda ikincisi sessizce baslamiyordu. Portlar ortam degiskeniyle kaydirilabilir hale getirildi ve kurulum paketi merkez tarafini 8811/8910'a alir. Gercek kurulumda olculdu: kopru 8790/8900, merkez 8000/8765/8811/8910",
      "AI ISCISI ARTIK GERCEK HTTP PORTUNA BAGLANIYOR. Onceden sabit 8000 varsayiyordu; sunucu baska bir porta dustugunde isci yanlis adrese baglanip sessizce is gormuyordu",
      "VERI DIZINI TASINABILIR HALE GETIRILDI. Program Files altina kurulan bir servis kendi kurulum dizinine yazamaz; ucus kayitlari, ayarlar ve lisans dosyasi hicbir kosulda yazilamazdi. Veri dizini artik ortam degiskeniyle ProgramData gibi yazilabilir bir konuma alinabiliyor. Konum yazilamazsa varsayilana donulur ve durum konsola ACIKCA yazilir",
      "psycopg2 BAGIMLILIK LISTESINDE EKSIKTI. PostgreSQL surucusu kodda zorunlu kullaniliyor ama requirements.txt'te yer almiyordu; temiz bir kurulumda yazilim veritabanina hic baglanamazdi",
      "MERKEZ UYGULAMA ICIN WINDOWS SETUP VE UBUNTU PAKETI URETILDI. Ilk acilista PostgreSQL sihirbazi yerel web arayuzunde acilir; girilen sunucu bilgileriyle tablolar kurulur. Ubuntu paketi gercek bir makinede kurulup dogrulandi",
    ],
  },
  {
    s: "2.4.64", t: "2026-08-15",
    d: [
      "Yeni olusturulan kullanici dogru sifreyle bile sisteme giremiyordu. Kok neden olculdu: kullanici kaydindaki 'aktif' alani veritabaninda TAMSAYI (1/0) tutulur, giris denetimi ise onu mantiksal deger sanip 'aktif === true' kuraliyla karsilastiriyordu. Tamsayi 1 hicbir kosulda true'ya esit olmadigi icin giris reddediliyordu",
      "Kusur yalnizca YENI kullanicilarda goruldugu icin uzun sure gizli kaldi: daha eski kayitlar mantiksal deger yazan bir surumden geliyor ve giris yapabiliyorlardi. Ayni alan kullanici listesinde de okundugu icin yonetici, pasif olmayan bir kullaniciyi pasif gorebiliyordu",
      "Aktiflik karari tek bir yardimciya baglandi: tamsayi, mantiksal deger, metin ve bos deger dordu de ayni sonucu verir. Arayuz tarafi da tip dayanikli hale getirildi; boylece merkez ile arayuz arasindaki tur farki bir daha giris engeline donusemez",
      "UCUS KAYITLARI ARTIK PILOTA GORE SUZULUYOR. Onceden yeni olusturulan bir pilot, hic ucus yapmamis olmasina ragmen sistemdeki TUM ucus kayitlarini goruyordu",
      "Ucusun sahibi, TAKEOFF komutunu veren pilottur. Sahiplik kalkis kontrol listesinin imzalandigi anda kurulur; boylece kaydin sahibi, sorumlulugu fiilen ustlenen kisi olur. Yalnizca yonetici rolu tum ucuslari gorur ve yonetici gorunumunde pilot adi da listelenir",
      "Sahiplik denetimi yalnizca listeye degil KAYIT OKUMA ve KAYIT SILME islemlerine de uygulandi. Listeyi suzmek tek basina yeterli olmazdi: kayit kimligini bilen bir pilot, listede hic gormedigi bir ucusu dogrudan okuyabilir ya da silebilirdi",
      "Rota noktalari arasindaki mesafe etiketi okunamiyordu. Yazi boyutu 11 pikselden 15 piksele cikarildi ve dis cizgi guclendirildi; boylece uydu goruntusu uzerinde de okunur. Ayni olcu koridor ve serbest form rotalarina da uygulandi",
      "UCUS GRAFIGI YAZDIR dugmesi hicbir sey yapmiyordu. Kok neden: uyari bildirimi cagrilirken uc ayri metin gonderiliyordu, oysa islev tek bir nesne bekliyor. Cagri sessizce dusuyor ve yazdirma hic baslamiyordu. Ayni hatali cagri ucus raporunda da vardi ve birlikte duzeltildi",
      "Yazdir dugmesi pencere baslik cubugundan alt seride, olagan bir dugme olarak tasindi ve antetli cikti uretiyor. Onceki yerinde baslik ikonlari arasinda kayboluyordu",
      "Ucus gecmisi oynaticisinda harita uzerine sag ust koseye ucusun KARE KOD'u yerlestirildi; boylece ekran goruntusu ya da cikti, ait oldugu ucusla eslesebilir. Kayit paneli icin tam ekran dugmesi eklendi",
    ],
  },
  {
    s: "2.4.63", t: "2026-08-15",
    d: [
      "RADARA BAGLAN dugmesi hicbir sey yapmiyordu: komut merkezde 'list object has no attribute get' hatasiyla dusuyordu. Radar ayakta ve saha makinesinden erisilebilir olsa bile baglanti kurulamiyordu",
      "Kok neden bir yanit sozlesmesi uyusmazligiydi. Saha koprusu servis durumlarini LISTE olarak bildirir; merkez ise ayni alani sozluk sanip uzerinde arama yapiyordu. Iki taraf da kendi icinde tutarli oldugu icin kusur kaynak okumasiyla gorunmuyordu, yalnizca komut calistiginda ortaya cikiyordu",
      "Kusur radara OZGU DEGILDI. Radar, Yer Kontrol Istasyonu Dual, video, yapay zeka ve dron secimleri ayni ortak koddan gectigi icin BES servisin tamami ayni cokmeyi yasiyordu. Tek bir yerde duzeltildi; bes servis birlikte kurtarildi",
      "Merkez artik her iki yanit bicimini de tasiyor. Bunun nedeni saha koprusunun surumunun merkezle her zaman ayni olmamasidir: operator kopruyu elle yukseltir. Surum uyusmazligi bundan sonra sessiz bir cokme yerine dogru davranisla sonuclanir",
      "Bozuk veya eksik servis bildirimi artik komut isleyiciyi dusurmez; ilgili servis 'calismiyor' olarak degerlendirilir ve operatore anlasilir bir sebep bildirilir",
    ],
  },
  {
    s: "2.4.62", t: "2026-08-15",
    d: [
      "Radar, operatorun girmedigi bir adrese baglanmaya calisiyordu. Kok neden olculdu ve ayni varsayim UC ayri yerde gomuluydu: radar IP alani '192.168.8.168' on degeriyle aciliyor, alan bos birakilirsa merkez bunu sessizce '192.168.8.186' yapiyor, saha koprusu de acilista komut beklemeden ayni adrese baglanmaya calisiyordu. Sonuc: operator hicbir adres yazmadan bir baglanti denemesi basliyor ve panelde sebebi anlasilmayan zaman asimi cikiyordu",
      "Radar IP alani artik BOS aciliyor. Icindeki gri metin yalnizca bicim ipucudur, komutla GONDERILMEZ. Radarin adresi her sahada farklidir; bu yuzden hicbir on deger dogru olamaz",
      "Adres girilmeden RADARA BAGLAN'a basilirsa baglanti denemesi baslamaz; 'Radar IP adresi girilmedi' uyarisi cikar. Sessizce bir varsayima dusmek, yanlis adresin hatasini operatore kendi hatasi gibi gosteriyordu",
      "Gecersiz port (sifir, negatif, 65535 ustu) reddedilir ve sebebi bildirilir",
      "Saha koprusu artik kendi basina hicbir radara baglanmaz; yalnizca merkezden gelen 'bu adrese baglan' komutuyla baglanir. Onceki davranis, radar baska bir adreste oldugunda sahadaki BASKA bir cihaza TCP oturumu acmak anlamina geliyordu",
      "Baglanilan adres saha makinesinde saklanir; makine yeniden baslatildiginda ayni radara kendiliginden baglanir, operatorun her acilista IP'yi yeniden yazmasi gerekmez. Bu, koda gomulu bir varsayim degil, operatorun daha once verdigi komuttur",
      "RADARI KES komutu bu kaydi da siler: baglanti bilerek kesildiyse yeniden baslatma onu geri getirmez",
      "Video duvari sayfasi eski surumun betiklerini kullaniyordu (onbellek etiketi v2453'te kalmis). Ceviri dosyasi da eski surumden geldigi icin sayfadaki bazi metinler guncellenmiyordu",
    ],
  },
  {
    s: "2.4.61", t: "2026-08-14",
    d: [
      "Saha kameralari merkezde goruntu vermiyordu. Kok neden olculdu: kamera baglantisini MERKEZ SUNUCUSU aciyordu. Merkez bir veri merkezindedir ve pilotun yerel agini gormez; bu yuzden 192.168.x.x adresindeki kameralar hicbir kosulda acilamazdi. Yalnizca internete acik kameralar calisiyordu ve bu, kusuru gizliyordu",
      "Kamera baglantisi artik koprunun kuruldugu saha makinesinde aciliyor. Goruntu yerel agda kalir; merkeze kare TASINMAZ, yalnizca akisin acik olup olmadigi, izleyici sayisi ve kare sayaci bildirilir. Kareyi merkeze tasimak kiraci basina megabit olceginde bant genisligi gerektirirdi ve bu ayrica planlanmis bir kalemdir",
      "'Yerel kameralari tara' dugmesi HER ZAMAN bos liste donduruyordu. Tarama merkez sunucusunda yapiliyordu ve o sunucuda kamera aygiti yoktur; dolayisiyla cantaya ya da saha bilgisayarina takili kamera hicbir kosulda listelenemezdi. Tarama artik saha makinesinde yapilir",
      "AI izleme baslatma istegi merkezden saha AI bilgisayarina gidiyor ve zaman asimina dusuyordu. AI bilgisayarlari ozel agdadir (ornek: 192.168.8.50). Yoklama ve gorev atama artik saha makinesinden yapilir; AI sunucusunun merkezde surekli 'yanit vermiyor' gorunmesinin nedeni de buydu",
      "AI iscisine verilen goruntu adresi duzeltildi. Onceden merkezin kendi adresi veriliyordu ve saha iscisi o adrese erisemiyordu; zincir iki noktadan birden kopuyordu. Artik saha makinesinin yerel goruntu adresi verilir",
      "Kamera acilamazsa sebebi bildiriliyor: adres hatali, kimlik dogrulama gerekiyor, ffmpeg eksik ya da kaynak kare uretmiyor. Onceden yalnizca goruntu gelmiyor ve sebep bilinmiyordu",
      "Kopru koptugunda kamera ve AI durumu 'kapali' yazip listeleri temizliyor. Aksi halde merkez, iletisimi kopmus bir sahanin son goruntusunu canli gibi gostermeye devam ederdi",
      "Bir AI bilgisayari duserse gorevi cevrimici olan diger isciye tasiniyor. Onceden kamera sessizce izlemesiz kalirdi ve operator bunu bilemezdi",
      "Yerel USB kamera icin saha makinesinde OpenCV gerekir. Kurulu degilse 'kamera yok' denmez; kurulum komutu bildirilir. Ag kameralari (RTSP, MJPEG) OpenCV olmadan da calisir",
      "Bir kurumun baska kurumun makinesindeki kameraya ya da AI bilgisayarina komut gondermesi sunucu tarafinda engellendi",
      "Kullanicinin kendi sunucusuna kurdugu GOKTUNGU'de davranis birebir korundu; orada kamera ve AI bilgisayari zaten ayni agdadir",
    ],
  },
  {
    s: "2.4.60", t: "2026-08-14",
    d: [
      "C20 radari merkezde baglanamiyordu: panel 'HATA / timed out' yaziyordu. Kok neden olculdu: radar pilotun sahasindaki yerel aga baglidir (ornek: 192.168.8.168), oysa RADARA BAGLAN dugmesi MERKEZ SUNUCUSUNDAN o adresi ariyordu. Bu adres ozel bir ag adresidir; internetten erisilemez, dolayisiyla baglanti hicbir kosulda kurulamazdi",
      "Radar artik koprunun kuruldugu saha makinesinden aciliyor. Radar protokolunun tamami (oturum acma, kalp atisi, hedef izleri, RTK konumu, ayar okuma ve yazma) o makinede calisir; merkez yalnizca durumu ve hedefleri gosterir. Kullanicinin kendi sunucusuna kurdugu GOKTUNGU'de davranis birebir korundu, orada radar zaten ayni agdadir",
      "Radar hedefleri artik haritaya geliyor. Onceki surumde kopru radar servisi izleri yalnizca kendi konsoluna yaziyordu; merkeze hic gondermiyordu. Bu, radar bagli gorunse bile haritanin bos kalmasi demekti. Hedefler, siniflandirma, angajman ve iz kaydi zincirinin tamami artik saha radarindan besleniyor",
      "Iki makine arasindaki SAAT FARKI kaynakli hedef kaybi onlendi. Iz zaman damgalari saha makinesinin saatiyle uretilip merkezin saatiyle karsilastirilsaydi, saatler kaymissa hedefler ya aninda silinir ya da hic silinmezdi. Izler artik gecen sureye gore tasiniyor; olculdu: uc saatlik saat farkinda bile hedefler dogru yasta kaliyor",
      "Radar susunca eski hedeflerin haritada SONSUZA KADAR kalmasi giderildi. Eskime denetimi yalnizca yeni veri geldiginde calisiyordu; radar kablosu cikarsa hic veri gelmez ve ekranda artik var olmayan hedefler durmaya devam ederdi. Operator boyle bir hedefe gore karar verebilirdi. Eskime artik zamana bagli calisir",
      "Kopru koptugunda radar durumu 'kapali' yazip hedefleri temizliyor. Aksi halde merkez, iletisimi kopmus bir radarin son goruntusunu canli gibi gostermeye devam ederdi",
      "Radar ayarlari (frekans, tespit esigi, hiz esigi, RCS esigi, calisma modu) ve RTK'DAN KONUM AL artik gercek radara ulasiyor; sonuc panele geri yansitiliyor",
      "Pilot birden fazla saha makinesi isletiyorsa radar panelinde 'Saha makinesi' secici goruntulenir. Tek makine varsa secici gizlidir, merkez dogru makineyi kendisi bulur",
      "Bir kurumun baska kurumun makinesindeki radara komut gondermesi sunucu tarafinda engellendi",
      "Radar menusunun ve harita halkalarinin kopru radar servisine bagli gorunurlugu (v2.4.58) aynen korundu",
    ],
  },
  {
    s: "2.4.59", t: "2026-08-14",
    d: [
      "Yer Istasyonu 2 (GCCDUAL cantasi) merkezde bagalanamiyordu: panel 'Port acilamadi (/dev/ttyACM0)' yaziyor ve iki saniyede bir yeniden deniyordu. Kok neden olculdu: canta pilotun bilgisayarina takilidir, oysa Baglan, Portlari tara, LED ve Kalibre dugmelerinin hepsi MERKEZ SUNUCUSUNUN seri portunu aciyordu. Merkez bir veri merkezinde durur; oraya fiziksel canta takilamaz, dolayisiyla panel hicbir kosulda calisamazdi",
      "Panel artik cantanin GERCEKTEN takili oldugu makineye komut gonderiyor: komutlar kopru yazilimindaki Yer Kontrol Istasyonu (GroundGCC) servisine iletilir, seri port o makinede acilir ve buton, kol, joystick verisi merkeze geri akar. Kullanicinin kendi sunucusuna kurdugu GOKTUNGU'de davranis birebir korundu; orada canta zaten ayni makinededir",
      "Pilot birden fazla saha makinesi isletiyorsa panele 'Saha makinesi' secici geliyor. Bu bir kolaylik degil guvenlik onlemidir: secim olmadan komut adaylardan birine gitseydi, iki cantali kurulumda ARM ya da KALKIS dugmesi sessizce YANLIS aracin cantasina ulasabilirdi. Tek makine varsa secici gorunmez, merkez dogru makineyi kendisi bulur",
      "Komutun baska bir kurumun makinesine gonderilmesi sunucu tarafinda engellendi. Makine kimligi arayuzden gelir; dogrulanmasa bir kurum, baska kurumun bilgisayarindaki seri portlari tarayip cantasina LED ve kalibrasyon komutu gonderebilirdi",
      "Canta kablosu cikarildiginda panelin 'BAGLI' gostermeye devam etmesi onlendi. Servis artik cantaya duzenli yoklama gonderir ve yanit gelmezse kopukluk bildirir. Olculdu: bu sessiz basarisizlik en tehlikelisiydi; pilot canli sanilan bir panelde dugmeye basip komutun ulastigini varsayabilirdi",
      "Cihaz yoksa neyin eksik oldugu artik aciktir. Panel 'GroundGCC servisi calismiyor' ya da 'Kopru yazilimi cevrimici degil' seklinde ne yapilacagini soyler; onceki surumde yalnizca islevsiz bir port hatasi gorunuyordu",
      "Baglanti sayaclari (alinan, gonderilen, yoklama, bozuk paket) ve gecikme olcumu saha makinesinde tutulup panele tasiniyor; kalibrasyon ve LED denetimi de o makinede uygulaniyor. Boylece panelin gosterdigi her deger cantanin gercek durumudur",
    ],
  },
  {
    s: "2.4.58", t: "2026-08-14",
    d: [
      "Radar menusu gorunmuyorken haritada radar halkalarinin ve radar ikonunun cizilmeye devam etmesi giderildi. Kok neden olculdu: menu gorunurlugu ile harita gorunurlugu IKI AYRI kaynaktan besleniyordu. Menu onceki surumde kopru yazilimindaki radar servisine baglanmisti; harita ise eski program ayarini okumaya devam ediyordu. Iki kaynak ayrildigi anda 'menude yok ama haritada var' celiskisi kacinilmaz hale gelir",
      "Radar yetenegi artik tek bir yerde belirlenir; menu, kapsama halkalari, mesafe ve azimut etiketleri, tarama cizgisi, iz yelpazesi, irtifa kubbesi ve radar ikonu ayni karardan beslenir. Kosulun iki yerde kopyalanmis olmasi kusurun ta kendisiydi; kopyayi silmek ayni celiskinin ilerideki yeni radar varliklarinda tekrarlanmasini da onler",
      "Gizlemenin kalici olmasi ayrica saglandi. Kapsama izgarasi harita her hareket ettiginde varliklari SIFIRDAN yeniden olusturur; onceki surumde gizleme yalnizca o andaki varliklara uygulandigi icin haritayi kaydirmak halkalari geri getiriyordu. Radar ikonu da her konum guncellemesinde yeniden dogabiliyordu. Bu varliklar artik yetenek yoksa dogrudan gizli olusuyor",
      "Merkezde sayfa ilk acildiginda radar varliklarinin bir an parlamasi kapatildi. Kopru servis durumu henuz bilinmedigi icin ilk boyamada tarayici onbellegindeki eski ayar kullaniliyordu; merkezde radar koprusu kapali olsa bile halkalar kisa sure gorunuyordu",
      "Kullanicinin kendi sunucusuna kurdugu GOKTUNGU'de davranis aynen korundu: kopru kavrami olmayan yerel kurulumda karar Program Ayarlari'ndaki radar anahtarina aittir",
    ],
  },
  {
    s: "2.4.57", t: "2026-08-14",
    d: [
      "Ucus gecmisinin bos gorunmesi kusuru giderildi. Tamamlanan ucus veritabanina DOGRU yazilmisti; kayip olan yalnizca goruntulemeydi. Kok neden olculdu: PostgreSQL'in ondalik sayi turu (ucus suresi, azami irtifa, azami ve ortalama hiz) programa JSON'a yazilamayan bir nesne olarak geliyor ve yanit hazirlanirken islem yarida kesiliyordu. Arayuze hicbir sey ulasmadigi icin kusur veri kaybi gibi gorunuyordu",
      "Duzeltme tek tek sorgularda degil veritabani surucusunun kendisinde yapildi: ondalik degerler artik dogrudan sayi olarak geliyor ve eski davranisla birebir ayni. Yuz uzeri sorguya tek tek donusum yazmak yerine kaynagin duzeltilmesi bilincli bir secim: aksi halde ayni kusur ilerideki her yeni panelde (raporlar, grafikler, ozetler) yeniden dogardi. Bes basliktan on bir olcumle dogrulandi",
      "Ikinci ekranda kullanilan ucus duvari merkezde acilmiyordu. Iki ayri eksik vardi: adres merkez tarafinda hic tanimli degildi ve sayfa acilsa bile veri baglantisini yanlis kapidan kurmaya calisiyordu. Ikisi de giderildi; ucus duvari artik ana arayuzle AYNI guvenli baglantiyi kullaniyor, boylece kurum guvenlik duvarlari ve mobil operator aglari icin ek port gerekmiyor",
      "Program Ayarlari menusu merkezde tumuyle kaldirildi. Icindeki her bolum saha bilgisayarina aitti: radar ve yer kontrol istasyonu anahtarlari (yetenegin kaynagi artik kopru yaziliminda calisan servis), GCCDUAL seri portu (aygit kopru makinesinde), servis yonetimi, bilgisayar acilista otomatik baslatma ve merkez sunucu anahtari. Merkezde bunlarin karsiligi yoktur",
      "Servis yonetiminin merkezde gosterilmesi yalnizca gereksiz degil YANILTICIYDI: panel 'servis kurulu degil' diyip kurulum komutu oneriyordu, oysa program o anda calisiyordu. Ayrica merkezde tum kurumlar tek surece baglidir; bir kurumun yoneticisinin 'Durdur' demesi butun kurumlarin ucusunu keserdi. Menu gizlemenin yaninda ilgili komutlar sunucu tarafinda da reddedilir; gorunurluk tek savunma degildir",
      "Kullanicinin kendi sunucusuna kurdugu GOKTUNGU'de hicbir sey degismedi: Program Ayarlari menusu, radar ve GCCDUAL anahtarlari, seri port alani ve servis yonetimi aynen duruyor. Merkez ile lokal kurulum ayrimi tek bir yerden okunur",
      "Menu kaldirmanin dogal sonucu olarak, karsiligi kalmayan yerel donanim GIRISIMLERI de merkezde kapatildi. Onceden bunlarin her biri acilista hata ya da yanlis ogut yaziyordu: GCCDUAL cantasi olmayan bir seri portu iki saniyede bir sonsuza kadar aramaya devam ediyor, servis yoneticisi kurulu olmayan bir birim icin kurulum komutu oneriyor, sanal dron denetimi eksik dosyalari bildiriyor, yerel AI iscisi bulunamayan bir betigi cagiriyor ve fiziksel joystick icin paket kurulmasini istiyordu. Hicbiri merkezde anlamli degildi; hepsi kullanicinin kendi sunucusunda aynen calisir",
      "Guvenli WebSocket kapisinin merkezde acilma denemesi kaldirildi. Olculdu: o kapi merkezde KOPRU dinleyicisine aittir ve GOKTUNGU her acilista 'adres kullanimda' hatasi yaziyordu. Merkezde arayuz zaten alan adinin kendi guvenli kapisindan konusur, dolayisiyla ikinci bir dinleyicinin karsiligi yoktur",
      "Baglanti baslatilirken oturum henuz yuklenmemisse pilota gosterilen ileti duzeltildi. Onceden ic hata metni sizip 'sunucu listesi okunamadi' seklinde gorunuyor ve kullaniciyi veritabani ya da ag arizasi sanmaya yonlendiriyordu; oysa tek gereken birkac saniye sonra yeniden denemekti",
      "Merkez sunucusuna kamera yayinlari icin gereken video isleyici kuruldu. Olculdu: eksikligi yuzunden RTSP ve MJPEG yayinlarinin hicbiri merkezde acilamiyordu; kullanici ayni eksikligi kendi bilgisayarinda da yasamis ve kurunca cozulmustu. Sunucu CPU/RAM olcumu icin gereken paket de eklendi, boylece Kaynaklar widget'i merkezde de deger gosterir",
    ],
  },
  {
    s: "2.4.56", t: "2026-08-14",
    d: [
      "AI Sunuculari ve Kameralar panelleri artik Baglanti Yoneticisi ile ayni kopru duzenini kullaniyor: kayit eklenirken CALISACAGI MAKINE soruluyor, liste kopru basliklari altinda gruplaniyor, gruba ait olmayan kayitlar 'Merkezde calisan' basligi altinda toplaniyor",
      "Kok kusur giderildi: AI sunucusu baslatma (SSH) merkez sunucusunda kosuyordu. Olculdu: kullanicinin kaydettigi 'ASUS Ascent GX10 - 192.168.1.100' bir OZEL AG adresidir; merkez (104.247.173.243) bu adrese hicbir kosulda erisemez, dolayisiyla play dugmesi sahada asla calismazdi. SSH oturumu artik kopru makinesinde acilir, konsol satirlari koprude tamponlanip merkeze akitilir",
      "AI sunucu kayitlarina firma kimligi eklendi. Olculdu: bu tablo firma izolasyonu disinda kalmisti, yani merkezde bir kurumun tanimladigi AI bilgisayarlari -SSH kullanici adi dahil- diger tum kurumlara gorunuyordu. Kamera tablosunda ayni kusur yoktu ancak listeleme yolu suzgeci kullanmiyordu; o da baglandi",
      "Radar ve Yer Kontrol Istasyonu Dual menuleri merkezde YALNIZ kopru servis durumuna bakiyor. Onceden kosul 'program ayari VEYA kopru servisi' idi; merkezdeki ornekte program ayari acik oldugu icin saha koprusunde radar servisi hic baslatilmamis olsa bile menu gorunuyordu. Merkez sunucusuna radar ya da GCCDUAL cantasi takilamaz, dolayisiyla bu yetenegin tek dogru kaynagi koprudur. Kullanicinin kendi sunucusuna kurdugu GOKTUNGU'de karar eskisi gibi program ayarina aittir",
      "Kamera akisinin kopru uzerinden tasinmasi bu surumun KAPSAMI DISINDADIR ve ayrica planlanmistir: mevcut ters-WebSocket rolesi JSON+base64 cerceveleme kullanir, bu video icin yuzde otuz uc sisme ve cerceve basina ayristirma maliyeti demektir. Kameralarda bu surumde kopru secimi ve gruplama tamamlandi",
    ],
  },
  {
    s: "2.4.55", t: "2026-08-14",
    d: [
      "Baglanti Yoneticisi'nde yeni baglanti eklerken artik BAGLANTININ KURULACAGI MAKINE soruluyor. Merkezde calisan GOKTUNGU'de bu alan zorunludur ve yalniz o an cevrimici kopruler listelenir; kullanicinin kendi sunucusuna kurdugu GOKTUNGU'de alan hic gorunmez ve baglanti eskisi gibi programin kendi makinesinde acilir",
      "Kok kusur giderildi: kopru altinda tanimlanan TCP/UDP/seri baglantilar MERKEZ sunucusunda acilmaya calisiliyordu. Kullanicinin kopru bilgisayarinda calistirdigi sanal dron icin '127.0.0.1:5763' adresi merkezde bostu ve play her denemede 'Connection refused' veriyordu. Baglantinin nerede acilacagi artik kaydin turune degil kopru alanina gore belirlenir: tur (seri/tcp/udp) NASIL baglanildigini, kopru alani NEREDE baglanildigini soyler",
      "Kopruye gonderilen kanal tanimi kaydin GERCEK turunu ve adresini tasiyor. Olculdu: eski kod hicbir yerin YAZMADIGI iki alani okuyordu, bu yuzden her kanal kopruye 'seri' turu ve bos adresle gidiyordu; TCP bir dron bu yolla asla baglanamazdi",
      "Kayitli baglantinin makinesi sonradan degistirilebilir (dron baska bir saha bilgisayarina tasinmis olabilir). Degisiklik, ekleme yolundaki AYNI sahiplik denetiminden gecer: baska firmanin koprusune kayit tasinamaz",
      "Cevrimdisi bir makineye baglanma denemesi artik zaman asimina kadar beklemiyor; hangi makinenin kapali oldugu adiyla hemen bildiriliyor. Kayitli makine o an kapaliysa duzenleme ekraninda '(cevrimdisi)' etiketiyle listede korunur, boylece yalnizca adi degistirmek isteyen kullanici kaydin makinesini sessizce kaybetmez",
    ],
  },
  {
    s: "2.4.54", t: "2026-08-14",
    d: [
      "Merkezde calisan GOKTUNGU artik pilota veritabani guncelleme sihirbazi GOSTERMEZ. Sema yonetimi merkez operatorunun isidir: goc, servis acilirken sunucu tarafinda kendiliginden uygulanir ve her adim operator gunlugune adiyla yazilir. Kullanicinin kendi sunucusuna kurdugu GOKTUNGU'de davranis birebir korundu; orada veritabani kurumun kendisine ait oldugu icin sihirbaz gerekli kalir",
      "Sihirbazin merkezde acilmasi yalnizca gereksiz degil, CIKISI OLMAYAN bir ekrandi. Olculdu: sihirbaz giris ekranindan ONCE aciliyor, dolayisiyla 'Guncellemeyi Baslat' basildiginda oturum henuz bostu; yonetici denetimi bu yuzden kapanip 'yonetici olarak giris yapin' hatasi veriyor ve ilerleme yuzde sifirda kaliyordu. Kullanicinin rolu asli uygundu, sorun rolun o anda henuz yuklenmemis olmasiydi",
      "Bekleyen sema adimi gercekten vardi ve uygulandi: kopru gruplamasi (baglantilarin ve kameralarin hangi kopru ornegine ait oldugunu tutan alan ve indeksleri). Bu adim koda onceki surumde eklenmis, ancak goc o surumde bir daha kosmadigi icin veritabaninda hic olusmamisti. Kaynagi olculdu: goc defteri son adimi icermiyordu ve alan hicbir tabloda yoktu",
      "Merkez kipinde sema degistiren tum arayuz komutlari (ilk kurulum, veritabani olusturma, goc) reddedilir ve nedeni acikca bildirilir. Reddin kapsami bilincli olarak roldan bagimsiz tutuldu: firma yoneticisi de reddedilir, cunku merkezdeki veritabani tum kiracilar tarafindan paylasilir ve tek kiracinin pilotunun butun kiracilari etkileyen bir islemi baslatmasi dogru degildir",
      "Goc basarisiz olursa sunucu YINE de baslar. Durdurmak, semasi kismen guncel bir merkezi tamamen erisilemez yapardi ve o anda ucus yapan kiracilar da kaybedilirdi; sorun operator gunlugunde adiyla gorunur, pilota sihirbaz cikmaz",
      "Genel indirme katalogundan komuta kontrol yazilimi kaldirildi. GOKTUNGU merkezde calisir; kullanicinin indirmesi gereken tek yazilim kopru yazilimidir. Paket silinmedi, yalnizca genel katalogda gizlendi: dogrudan surum baglantisi ve imza dogrulama yolu operator icin acik kaldi",
    ],
  },
  {
    s: "2.4.53", t: "2026-08-13",
    d: [
      "Merkez sunucu mimarisi eklendi. Kullanicilarin kendi kurdugu GOKTUNGU sunucularinin SABIT IP'si yoktur ve cogu ev/ofis aginda disaridan erisilemez. Bu yuzden iletisim yonu bilincli olarak tersine cevrildi: merkez sahadaki sunucuya BAGLANMAZ, sahadaki sunucu merkeze baglanir ve merkez ayni soket uzerinden konusur. Boylece port yonlendirme, sabit IP ve guvenlik duvari kurali gerekmez",
      "Baglanti yoneticisine MERKEZ turu eklendi. Kullanici bir baglanti eklerken artik IP yazmak zorunda degil: merkezdeki firmasina ait ACIK sunucular listelenir ve secilir. Liste canli sokete gore uretilir; bir sunucu merkezden ayrilirsa listeden duser ve secilemez",
      "Merkez cagrisini TARAYICI degil GOKTUNGU sunucusu yapar. Bu bilincli bir secimdi: merkez hesap sifresi tarayiciya hic inmez, tarayici gelistirici konsolunda okunamaz ve ayni agi dinleyen biri sifreyi goremez. Arayuz yalnizca sonucu gorur",
      "Program Ayarlari'na Merkez Sunucu bolumu eklendi: adres, hesap ve sifre. Sifre kaydedildikten sonra arayuze BIR DAHA gonderilmez; ayar duyurusunda maskelenir. Bos sifre gonderilirse eski sifre korunur, boylece diger ayarlari degistirmek sifreyi silmez",
      "Otomatik guncelleme altyapisi kuruldu. Paketler merkezde Ed25519 ile IMZALANIR; ozel anahtar yalnizca merkezde tutulur, acik anahtar istemcide gomulu gelir. Istemci indirdigi paketin once SHA-256 ozetini, ardindan imzasini dogrular; ikisinden biri tutmazsa paket kurulmaz. Boylece indirme yolunda degistirilen bir paket sessizce kurulamaz",
      "Onbellek damgasi kusuru giderildi. Arayuz dosyalari surum damgasiyla istenir; damga guncellenmedigi icin tarayici YENI kodu indirse bile DEGISTIRILEN dosyalarin eski kopyasini kullanmaya devam ediyordu. Olcumle yakalandi: yeni bolum tarayicida hic cizilmedi, cunku eski dosya cagriyi icermiyordu. Damga her surumde otomatik ilerletiliyor",
      "Program Ayarlari paneli yeniden boyutlandirilabilir yapildi ve sabit 250 piksel genislik kaldirildi. Boyut, panel konumuyla ayni yerde saklanir; panel kapanip acildiginda kullanicinin verdigi boyut korunur",
    ],
  },
  {
    s: "2.4.52", t: "2026-08-11",
    d: [
      "PostgreSQL baglanti tukenmesi ('uzgunum, istemci sayisi cok fazla') giderildi. Kok neden olculdu: veri katmani her IS PARCASI icin ayri bir kalici baglanti aciyordu. Bu desen SQLite icin yazilmisti ve orada DOGRUYDU; bir SQLite baglantisi yalnizca bir dosya taniticidir ve sunucu tarafinda sinir yoktur. PostgreSQL'de ise her baglanti sunucuda ayri bir surectir ve varsayilan sinir 100'dur; ayni desen bu yuzden tersine doner",
      "Asil kusur baglanti sayisi degil SIZINTIYDI: is parcasi olurken baglantisini kapatmiyordu. Olcum icin on bes gecici is parcasi olusturulup temizlenmeden sonlandirildi; is parcalari oldu, ancak on bes baglanti veritabaninda ACIK kaldi. Uzun bir ucus oturumunda olusup olen her gecici is parcasi kalici olarak bir yuva sizdiriyordu. Yuvalar dolunca yalnizca GOKTUNGU degil, ayni veritabanina baglanan pgAdmin dahil herkes disari itiliyordu",
      "Baglanti havuzu sinirli boyutlu paylasilan yapiya cevrildi: is parcasi sayisindan bagimsiz olarak en fazla belirlenen sayida baglanti acilir ve is parcasi olunce yuva kendiliginden geri doner. Olcum sonuclari: kirk is parcasi kirk baglanti yerine on baglanti kullandi, temizlenmeden olen on bes is parcasi sifir sizinti birakti, yuz yirmi es zamanli istegin tamami basariyla tamamlandi ve zirve baglanti sayisi onda kaldi",
      "Baglantilar 'islem icinde bosta' durumunda birakiliyordu. Bu yalnizca yuva tutmakla kalmaz; veritabaninin olu satirlari toplamasini engeller ve tablolar zamanla siser. Telemetri gibi yuksek hacimli tablolarda bu kalici bir performans kaybina doner. Havuza iade sirasinda islem artik acikca sonlandirilir ve baglanti gercekten bosta duruma iner",
      "Havuz doldugunda davranis BILINCLI olarak acik hata secildi, sessiz bekleme degil. Sonsuz bekleme ucus sirasinda donan bir arayuz demektir ve kullanici neyin bekledigini goremez. Havuz dolarsa kisa bir sure beklenir, ardindan durumu adiyla soyleyen bir hata dondurulur",
      "Baglanti acilirken yuva once ayrilir, baglanti kurulamazsa yuva GERI VERILIR. Aksi halde her basarisiz deneme havuzu kalici olarak kucultur; veritabani sunucusu bir sure erisilemez kalirsa havuz sifira iner ve sunucu geri geldiginde bile hicbir baglanti acilamazdi",
      "Proje klasor yapisi sadelestirildi: kok dizinde yalnizca main.py ve assets klasoru bulunur. Web varliklari assets/web, Python kodu assets/python altindadir. Calisma zamani verisi (ucus kayitlari, harita onbellegi, hesaplar, sertifika) ayri bir veri klasorunde toplanir ve dagitim paketine GIRMEZ; boylece guncelleme paketi kullanici verisine hic dokunmaz",
      "Yol cozumleme tek bir katmanda toplandi ve yapi kendiliginden algilanir. Eski duz yapida calisan bir kurulum da yeni yapiya tasinmis bir kurulum da ayni kodla dogru yollari bulur; tasima yarim kalirsa program yine de acilir",
      "Tasima sirasinda dort sessiz kusur yakalandi. En sinsi olani surum okumasiydi: surum numarasi arayuz dosyasindan okunur ve yolu 'paketin bir ust dizini' olarak hesaplanirdi. Yeni yapida bu yol yanlisa dusuyor, dosya bulunamiyor ve kod HATA VERMEDEN gomulu yedek degere geriliyordu; surum yanlis gorunur, kimse fark etmezdi",
      "Yerel AI iscisi yeni yapida sessizce baslamiyordu: betik kok dizinde araniyordu, oysa assets/python altina tasinmisti. Ayrica AI betigi kendi dizinini kok sayiyordu; bu haliyle mevcut modelleri yok sayip yeniden indirmeye kalkacakti. Ikisi de dogru koke baglandi",
      "Servis ve kiosk betikleri 'bulundugum dizin koktur' varsayimiyla calisiyordu. Alt klasore tasindiklarinda bu varsayim 'main.py bulunamadi' hatasina donusurdu; betikler artik proje kokunu yukari dogru arayarak bulur",
    ],
  },
  {
    s: "2.4.51", t: "2026-08-11",
    d: [
      "Veri katmani SQLite'tan PostgreSQL'e tasindi. Kok neden olculdu ve sayilarla kayda gecirildi: 27 tablo, 146 cagri yeri, 256 yer tutucu. Gecis bir 'yeniden yazim' olarak DEGIL, bir ag gecidi katmani olarak yapildi; boylece mevcut 146 cagri yerinin hicbiri degistirilmek zorunda kalmadi ve gecis sirasinda sessiz davranis kaymasi riski ortadan kalkti",
      "Ilk acilista veritabani kurulum sihirbazi eklendi. Uc adim: sunucu bilgileri (IP, port, veritabani adi, kullanici, sifre), baglanti dogrulamasi, kurulum. Her 'Ileri' adiminda sunucuya GERCEK bir baglanti denemesi yapilir; yanlis bilgiyle kurulum hic baslamaz. Veritabani yoksa sihirbaz onu olusturmayi teklif eder, ancak kendi basina olusturmaz: veritabani yaratmak sunucuda kalici bir degisikliktir ve bilinerek onaylanmalidir",
      "Sihirbaz GIRIS EKRANINDAN ONCE calisir. Sebep teknik bir zorunluluk: kullanicilar tablosu artik PostgreSQL'de, dolayisiyla veritabani tanimlanmadan kimse dogrulanamaz. Giris formunu once gostermek kullaniciyi cikisi olmayan bir ekranda birakirdi",
      "Sema surum defteri ve goc motoru eklendi. Program guncellendiginde veritabaninda degisiklik gerekiyorsa acilista guncelleme sihirbazi cikar, hangi surumden hangi surume gecilecegini ve bekleyen adimlari listeler. Goc acilista SESSIZCE uygulanmaz: kullanici onayi alinir ve her adim adiyla bildirilir",
      "Butun sureclerde ilerleme cubugu ve adim adim bilgilendirme var. Onemli bir ayrinti: ilerleme sonda tek seferde degil ANLIK yayinlanir. Goc motoru ayri bir is parcasinda calisir; ilerleme bildirimleri is parcaciklari arasi guvenli bir kuyruk uzerinden arayuze aktarilir. Aksi halde cubuk kurulum boyunca sifirda durup sonunda bir kerede yuzde yuze atlar, kullanici da programin takildigini sanardi",
      "Harita karo onbellegi iki katmanli depoya cevrildi: PostgreSQL ana depo, disk ikinci katman. Tek katmanli veritabani deposu bilincli olarak SECILMEDI; veritabani sunucusuna erisim kesildiginde harita tamamen kararirdi. Iki katmanli yapida disk katmani devreye girer ve harita gorunmeye devam eder",
      "Telemetri tamponunun ham ornekleri BILINCLI olarak dosyada birakildi. Sahada yasanan asil sorun buydu: dakikalik tampon, ag veya veritabani kesintisinde veri kaybini onlemek icin var. Tamponun kendisini veritabanina tasimak, korumasi gereken arizanin tam ortasina bagimlilik koymak olurdu. Tampon dosyada tutulur, aktarim PostgreSQL'e yapilir ve her aktarim deftere islenir",
      "Gorev durumu (askidaki gorevin kaldigi nokta) PostgreSQL'e tasindi; dosya geri donus katmani korundu. Onemli bir kusur olcum sirasinda yakalandi: tablonun birincil anahtari dron kimligi yerine baglanti kimligi olarak konsaydi ayni anda ucan iki dron ayni satira yazacak ve birinin gorev ilerlemesi digerini silecekti. Anahtar MAVLink sistem kimligine cevrildi",
      "Gecis olcumu sirasinda on kritik kusur yakalandi ve giderildi. En yikici olani: SQL cevirisi her yazim sonrasi kosulsuz olarak son eklenen satirin kimligini istiyordu; kimlik kolonu olmayan tablolarda bu istek hata verip islemi geri aliyor ve AYNI ISLEMDEKI onceki tum yazimlari da siliyordu. Ikinci bir tanesi: telemetri aktariminin basari sayaci PostgreSQL'de bulunmadigi icin aktarim hic calismiyor, tampon dosyalari birikmeye devam ediyordu",
      "Anlamli birincil anahtarlar korundu. Otomatik sayaca cevrim yalnizca gercekten otomatik artan kolonlara uygulanir; MAVLink sistem kimligi gibi anlami olan anahtarlar oldugu gibi kalir. Toptan cevrim yapilsaydi veritabani bu kolonlara kendi urettigi sayilari yazacak ve dron kimlikleri sessizce bozulacakti",
      "SQLite'a ozgu SQL ifadeleri PostgreSQL karsiliklarina cevrildi: tarih bicimleme islevi, harf duyarsiz metin karsilastirmasi ve gruplandirma kurallari. Ucus ozeti gorunumu PostgreSQL'in daha kati gruplandirma denetiminden gecmiyordu; sorgu yeniden yazildi",
      "Kurulum ve goc komutlari yalnizca yonetici rolune aciktir. Tek istisna durum sorgusudur: o komut giris oncesi de yanit verir, cunku sihirbazin acilip acilmayacagina karar vermesi gerekir. Yapilandirma tamamlandiktan sonra diger komutlar kapanir; boylece ayni agdaki bir baskasinin calisan bir kurulumun veritabanini degistirmesi engellenir",
    ],
  },
  {
    s: "2.4.50", t: "2026-08-11",
    d: [
      "Joystick cubugu ortada dururken dronun kendi etrafinda donmesine yol acan kusur giderildi. Kok neden olculdu: olu bolge esigi cubugun merkezinin tam sifir oldugunu varsayiyordu, oysa gercek cubuklar merkezde kucuk bir kayma birakir. Kayma esigi asinca donus komutu SUREKLI gonderiliyor, dahasi fren mantigi bu kaymayi 'pilot girdi veriyor' sayarak komut akisini hic kesmiyordu; dron bu yuzden birakildiginda durmak yerine donmeye devam ediyordu",
      "Olculen onemli bir ayrinti: olu bolgeyi buyutmek tek basina cozum DEGILDIR. Merkezi 0,13 kaymis bir cubukta olu bolge sonrasi hala 0,011 kaliyor ve dron yavas da olsa donuyor. Bu nedenle cubugun gercek merkezini olcup kaydeden bir kalibrasyon adimi eklendi; kalibrasyon sonrasi deger tam sifira iner. Iki onlem birlikte calisir: kalibrasyon mevcut kaymayi giderir, olu bolge sonradan olusan yeni kaymayi yutar",
      "Eksen yonleri artik pilot bazinda ters cevrilebilir. Ileri/geri, yanal, irtifa ve donus eksenleri BAGIMSIZ olarak ayarlanir; boylece Mode 1 ve Mode 2 yerlesimine alisik pilotlar ayni yer istasyonunu kendi aliskanligiyla kullanir. Ayar kisiseldir ve pilotun hesabina baglidir: ayni bilgisayarda farkli pilotlar birbirinin ayarini ezmez",
      "Joystick ayarlari penceresine canli cubuk gostergesi eklendi. Her eksen icin cubugun ham degeri ve programin kullandigi islenmis deger yan yana gosterilir; cubuk ortadayken islenmis deger sifirdan farkliysa uyari cikar. Yalnizca onay kutusu koymak pilotu 'ters mi degil mi' sorusunu ucusta deneyerek ogrenmeye zorlardi",
      "Olu bolge esigi arayuzden sunucuya tasindi. Onceki surumlerde tarayici kendi sabit esigini uygulayip sunucuya islenmis deger gonderiyordu; bu yuzden sunucu cubugun gercek merkezini hic goremiyor ve kalibrasyon teknik olarak imkansiz kaliyordu. Islem artik tek yerde yapilir, boylece arayuz ile sunucu arasinda sessiz tutarsizlik olusamaz",
      "Olu bolge sinirindaki ani hiz sicramasi giderildi: eskiden esigin hemen ustunde hiz sifirdan dogrudan esik degerine atliyordu. Artik esik sonrasi deger oransal olarak sifirdan baslar, boylece kucuk cubuk hareketleri yumusak tepki verir. Ayrica merkez yumusatma ve eksen basina hassasiyet ayari eklendi",
      "Klavye kontrolu bilincli olarak ters cevirme ayarinin DISINDA tutuldu. Ters cevirme yalnizca fiziksel cubuk icin anlamlidir; klavyeye de uygulanmis olsa 'ileri eksenini ters cevir' ayarini yapan pilot W tusuna bastiginda dron geri giderdi",
      "Iki ekranli GCCDUAL cantasindaki joystickler de ayni pilot tercihini kullanir. Cantanin kendi merkez kalibrasyonu korunur ve olu bolge ikinci kez uygulanmaz; ust uste iki olu bolge, cubugun kullanilabilir hareket araligini gereksizce daraltirdi",
    ],
  },
  {
    s: "2.4.49", t: "2026-08-11",
    d: [
      "GOKTUNGU artik Linux'ta systemd servisi olarak kurulabilir: bilgisayar acildiginda kendiliginden baslar, cokerse kendini toparlar ve kullanici oturum acmasa bile ayakta kalir. Kurulum icin servis_kur.sh betigi eklendi; servis kullanici hesabiyla calisir, root olarak DEGIL, boylece veri dosyalarinin sahipligi bozulmaz ve elle baslatma calismaya devam eder",
      "Servis kurulumunun onkosulu olan agir bir kusur bulundu ve giderildi: program kapatma sinyalini (SIGTERM) aliyor, 'duzgun kapatiliyor' yaziyor ama HIC KAPANMIYORDU. Kok neden asyncio kapanis protokolunde bekleyen gorevlerin iptalini beklemesiydi; olcum py-spy ile yigin izi alinarak yapildi. Bu haliyle servis olarak kurulsa systemd 90 saniye bekleyip sureci zorla oldururdu ve o durumda sanal dron surecleri arkada kalip portlari bloke ederdi. Artik kapanma 1 saniyede tamamlanir ve sanal dronlar temizlenir",
      "Program Ayarlari'na servis yonetim bolumu eklendi: servisin kurulu olup olmadigi, calisip calismadigi, acilista otomatik baslayip baslamadigi ve surec numarasi gorunur. Baslat, durdur, yeniden baslat dugmeleri ile acilista otomatik baslatmayi acip kapatma ayni yerden yapilir; son gunluk satirlari da panelden okunabilir",
      "Servisi arayuzden durdurmanin dogasindaki tuzak ele alindi: servis kendini durdurdugunda arayuzle baglantisi da kopar. Bu yuzden yanit ONCE gonderilir, eylem kisa bir gecikmeyle uygulanir ve arayuz baglanti kopmasini beklenen sayarak yeniden baglanmayi dener. Aksi halde islem basarili olsa bile kullaniciya hata gibi gorunurdu",
      "Kullanici menusune Bilgisayari Kapat ve Yeniden Baslat dugmeleri eklendi; onay istenir ve ucan dron varsa ayrica uyarilir. Iki ekranli saha kurulumunda operatorun fiziksel makineye erismesi gerekmez. Bu dugmeler YALNIZ sistem yoneticisi rolunde gorunur, cunku ucus sirasinda yanlislikla basilmasi yikici sonuc dogurur",
      "Yetki tasariminda sessiz basarisizliga yol acan bir kusur olculup duzeltildi: yetki denetimi systemctl --dry-run ile yapiliyordu, ancak bu komut polkit'e hic sormaz, yalnizca komutun bicimini dogrular. Yetkisiz bir kullanici olusturulup olculdugunde dry-run yine basarili donuyordu; yani dugme etkin gorunur, basilir ve hicbir sey olmazdi. Denetim artik gercek yetkiyi olcen yontemle yapilir",
      "Iki ekranli kullanim icin kiosk duzeni eklendi: ust ekranda ana arayuz, ikinci ekranda ucus duvari Chrome ile tam ekran acilir ve oturum acilisinda kendiliginden baslar. Kiosk betigi baglanacagi portu tahmin etmez; sunucunun gercekten aldigi portu okur. Bu onemlidir cunku varsayilan port meshgulse sunucu sirayla sonraki porta duser ve sabit port varsayimi bos sayfa acilmasina yol acardi",
      "Sunucu artik calisirken gercekten kullandigi HTTP ve WebSocket portlarini bir durum dosyasina yazar. Onceki surumlerde bu bilgi yalnizca ekrana yaziliyordu; disaridan hicbir arac gercek portu ogrenemiyordu",
      "Yetki kurallari uc ayri bicimde birlikte yazilir (sudoers, modern polkit JavaScript kurali ve eski polkit pkla), cunku polkit yapilandirmasi dagitimlar arasinda bicim degistirir; tek bicime guvenmek kurulumun sessizce yetkisiz kalmasina yol acabilir. Verilen yetki genel root yetkisi DEGILDIR: yalnizca GOKTUNGU servisinin yonetimi ile kapatma ve yeniden baslatma komutlarini kapsar",
    ],
  },
  {
    s: "2.4.48", t: "2026-08-10",
    d: [
      "Sanal dron artik dort isletim sistemi/mimari bilesiminin tamaminda calisir: Windows x64, Windows ARM64, Linux x86-64 ve Linux ARM64. Onceki surumlerde bu bilesimler tek tek ve birbirinden bagimsiz ele alinmisti; her yeni makinede ayni sinif hata yeniden ortaya cikiyordu. Simdi isletim sistemi ve mimari tek bir uygunluk matrisinde birlestirildi ve dosya secimi bu matrise gore yapilir",
      "Windows tarafinda Linux'takine denk bir kor nokta kapatildi: program PE dosyalarinin MIMARISINI hic okumuyordu. MZ imzasini gorunce dosyayi kosulsuz kabul ediyor, mimarisi uymayan bir dosya acilis denetimini geciyor ve surec ancak baslatilirken 0xC000007B ile aninda kapaniyordu. Artik PE basligindaki COFF Machine alani okunur ve x64, ARM64, 32-bit x86 birbirinden ayirt edilir",
      "Windows ARM64 makineler icin ayri bir SITL ikilisine GEREK OLMADIGI olculdu ve dogrulandi: bu makineler x64 programlari donanim destekli emulasyonla calistirir. Bu nedenle pakete gereksiz bir ikili daha eklenmedi; bunun yerine ARM64 Windows'ta x64 dosyasinin gecerli sayilmasi saglandi. Tersi gecerli DEGILDIR ve bu asimetri koda islendi: x64 bir Windows, ARM64 ikilisini calistiramaz",
      "Kutuphane denetimi artik varligin yaninda MIMARIYI de olcuyor. Bir kutuphanenin dosya olarak bulunmasi yetmez; 64-bit bir surece 32-bit kutuphane yuklenemez. Bu durumda surec yine main'e hic girmeden duser, ancak cikis kodu farklidir (0xC000007B, eksik dosyanin verdigi 0xC0000135 degil). ArduPilot dagitimi iki mimariyi bir arada dagittigi icin bu karisma gercekten olusabilir",
      "Pakette bulunan bes kutuphanenin SITL icin hic kullanilmadigi olculdu: hicbiri ice aktarma zincirinde yok ve hepsi 32-bit. Onceki surumler bunlari eksik olabilir diye raporluyor, kullaniciyi var olmayan bir sorunla ugrastiriyordu. Artik ayri bir kategoride tutuluyor ve eksiklikleri kusur sayilmiyor",
      "Gerekli kutuphane listesi iki bagimsiz yontemle teyit edildi: ikililerin ice aktarma tablosu okundu ve ayrica kutuphaneler silinip Windows yukleyicisinin gercekten hangi dosyalari aradigi izlendi. Iki olcum ayni bes dosyayi verdi; liste artik tahmine dayanmiyor",
      "Tanilama araci (python3 sitl_tani.py) Windows tarafinda da Linux tarafiyla ayni titizlige getirildi: PE dosyalarinin mimarisini raporlar, kutuphanelerin ikiliyle ayni mimaride olup olmadigini olcer ve kullanilmayan kutuphaneleri ayirt ederek gereksiz uyari uretmez",
    ],
  },
  {
    s: "2.4.47", t: "2026-08-10",
    d: [
      "ARM 64-bit (aarch64) bilgisayarlarda sanal dron hic baslatilamiyordu: hata [Errno 8] Exec format error idi ve klasordeki SITL ikilisi x86-64 icin derlenmisti. Bir ikili dosya yalnizca derlendigi islemci mimarisinde calisir; x86 dosyasini ARM islemcide calistirmak isletim sistemi ne olursa olsun mumkun degildir. Artik aarch64 icin ayri ikililer pakete gomulu gelir ve program makinenin mimarisine gore dogru dosyayi kendisi secer",
      "Onceki surumun kurtarma yolu bu makinelerde ayni hataya ikinci kez yol aciyordu: program ARM makine gorunce ArduPilot dagitimindan ikili indirmeyi deniyor, ancak oradaki tek ARM secenegi 32-bit oldugu icin indirilen dosya da aarch64'te calismiyordu. ArduPilot aarch64 icin hazir SITL yayinlamaz; bu olculdu ve dogrulandi. Bu yuzden indirme yolu bu mimaride tamamen kapatildi ve ikililer pakete gomuldu",
      "Gomulen aarch64 ikilileri ArduPilot kaynagindan derlendi ve tamamen statik baglandi: hicbir sistem kutuphanesine bagimli degiller. Bunun onemi su: dinamik baglanmis bir ikili derlendigi makinenin glibc surumunu ister ve daha eski bir dagitimda kutuphane hatasiyla acilmaz. Statik ikili her ARM 64-bit Linux dagitiminda calisir",
      "Mevcut x86-64 kurulumlar hicbir sekilde etkilenmedi: yeni dosyalar ayri adlarla eklendi, eski dosyalara dokunulmadi. x86 bir makinede program eskisi gibi ayni ikiliyi kullanmaya devam eder",
      "Dosya secimi artik varlik degil UYGUNLUK olcuyor. Onceki surum klasorde adi uyan ilk dosyayi bulunca hazir sayiyordu; bu yuzden ARM makinede x86 dosyasi seciliyor, acilista SITL hazir yaziliyor ve hata ancak sanal dron eklenirken ortaya cikiyordu. Simdi her aday dosyanin mimarisi baslatmadan once olculur, uymayan atlanir ve varsa dogru dosya kullanilir",
      "Hata metinleri mimariye gore ayrildi. Dosya bulunamamasi ile dosyanin bulunup calistirilamamasi farkli sorunlardir ve cozumleri de farklidir; ayni metni vermek kullaniciyi yanlis yone gonderiyordu. Artik hangi dosyanin beklendigi adiyla yazilir ve o mimaride indirme secenegi yoksa bu acikca soylenir",
      "Tanilama araci (python3 sitl_tani.py) mimariye duyarli hale getirildi. Onceki surum her Linux makinede ayni dosya adini ariyordu; aarch64 bir makinede bu dosya x86-64 oldugu icin yanlis teshis koyup indirme oneriyordu. Arac artik makineye gore dogru dosyayi arar, klasordeki tum ikililerin mimarisini listeler ve yalnizca x86 dosyalarinin bulundugu durumu ayrica teshis eder",
    ],
  },
  {
    s: "2.4.46", t: "2026-08-10",
    d: [
      "Linux'ta sanal dron baslatilamiyordu: SITL ikilisi vardi ama calistirma izni yoktu ve hata [Errno 13] Permission denied olarak gorunuyordu. Calistirma izni dosyanin kendisinde degil dosya sisteminde tutulur; arsiv Windows uzerinden gecerse, bulut klasorune kopyalanirsa veya elle acilirsa bu bit dusar. Program artik izni acilista kendisi onarir, kullanicinin hicbir sey yapmasi gerekmez",
      "Izin onarilamayan durumlar da sessiz kalmiyor: klasor salt okunur bir diskte veya baska bir kullaniciya aitse hata metni hangi komutun kosturulacagini yazar. Dosya sistemi noexec ile baglanmissa (bazi kurulumda /tmp, ag suruculeri) izin verilmis gorunup calistirma yine reddedilir; bu durum ayrica taninir ve klasorun yerel diske tasinmasi onerilir",
      "Izin duzeldikten sonra ortaya cikan ikinci kusur da kapatildi: [Errno 8] Exec format error. Bu hata ciplak halde uc ayri nedeni ayirt etmez ve kullaniciya hicbir yol gostermez. Program artik ikiliyi baslatmadan ONCE dosyanin ilk baytlarini okuyup gercek bicimini olcer",
      "Uc neden artik birbirinden ayrilip adiyla bildiriliyor: dosya yanlis isletim sistemine ait mi (Linux'ta Windows ikilisi), makinenin mimarisine uymuyor mu (x86-64 ikili ARM makinede), yoksa bozuk mu. Her biri icin verilen ogut farklidir, cunku cozumleri de farklidir",
      "Bozulma bicimleri de taniniyor: yarim inmis dosya, hata sayfasi olarak inmis HTML, git-lfs isaretcisi ve bulut eslemesinin biraktigi yer tutucu. Bunlarin hepsi dogru ada sahip oldugu icin dosya var gorunur; boyut ve icerik denetimi bunlari yakalar",
      "Mimari uyusmazliginda program yalniz hata vermekle yetinmiyor, kendini onariyor: makinenin mimarisine uygun SITL ikilisini indirip yerlestirir ve ucusa devam eder. ARM makineler (Raspberry Pi ve benzeri ARM bilgisayarlar) icin dogru ikili artik taniniyor. Indirilen dosya yerine konmadan once dogrulanir, boylece yanlis dosya ayni hataya ikinci kez yol acmaz",
      "Acilis raporu artik dogruyu soyluyor. Onceki surum yalniz dosya varligina bakip SITL hazir yaziyor, kullanici sanal dron eklemeye calistiginda hata aliyordu. Bicim, mimari ve izin denetimi acilista yapilir; sorun varsa program ilk saniyede haber verir",
      "Sorunu tek basina bulmak icin bir tanilama araci eklendi: kurulum klasorunde python3 sitl_tani.py kosturmak yeterlidir. Klasor icerigini, her dosyanin bicimini ve mimarisini, boyut ve parmak izi karsilastirmasini, calistirma iznini ve ikilinin gercekten calisip calismadigini sirayla olcer; her basarisiz maddede ne yapilacagini yazar",
    ],
  },
  {
    s: "2.4.45", t: "2026-08-10",
    d: [
      "Windows'ta sanal dron baslatilamiyordu: SITL surecinin cikis kodu 3221225781 idi ve ayrinti icin gosterilen sitl.log bos kaliyordu. Bu kod Windows'un STATUS_DLL_NOT_FOUND degeridir; ArduPilot'un Windows SITL ikilisi Cygwin ile derlendigi icin yanindaki kutuphaneler olmadan surec ANINDA olur, dolayisiyla gunluge tek satir bile yazamaz. Bos gunluk bir kusur degil, hatanin dogal sonucuydu",
      "Gerekli tum dosyalar artik programla birlikte gelir: dort SITL ikilisi ve on Cygwin kutuphanesi tam pakete gomuldu. Sunucu acilirken hicbir sey INDIRMEZ, dolayisiyla internetsiz sahada da sanal dron calisir",
      "Eksik kutuphane listesi tahmin edilmiyor, ikililerin PE ice aktarma tablosundan olculdu. Onceki surumde bu liste tahmine dayaliydi ve eksik adlar iceriyordu",
      "Baslatmadan ONCE kutuphane denetimi yapilir: eksik varsa surec hic baslatilmaz ve hangi dosyalarin hangi klasorde bulunmasi gerektigini yazan bir hata verilir. Ayrica bilinen Windows cikis kodlari (erisim engeli, bellek ihlali, kesme) okunur cumleye cevrilir",
      "Sanal dronlar icin artik her kayit ayri grup acmiyor: tek bir SANAL DRON grubu altinda toplaniyor. Her kaydin kendi baslat, durdur, duzenle ve sil dugmeleri korunur; ust grup katlanirsa tumu, alt blok katlanirsa yalniz o kaydin dronlari gizlenir",
      "Yer Istasyonu 2 penceresi Dronlar menusunden Goktungu menusune tasindi ve cihaz kunyesiyle Yer Kontrol Istasyonu Dual (GCCDUAL) adini aldi. Radar gibi Program Ayarlari'ndan acilip kapatilir; kapali ise menude hic gorunmez ve acilista baglanmaya calismaz. Bu ayrim farkli istasyon cihazlarinin ayni programda yasamasi icin yapildi",
      "AI bilgisayarlari uzaktan baslatilabilir: kayit formuna SSH kullanici adi, port, ozel anahtar, sifre ve baslatma komutu alanlari eklendi. Listedeki baslat dugmesi SSH ile baglanip komutu calistirir, tekrar basmak sureci durdurur",
      "Her AI bilgisayarinin yaninda konsol dugmesi var: SSH oturumunun canli ciktisini satirin altinda acilan bir pencerede gosterir, tekrar basinca kapanir. Satirlar sunucuda birikir, bu yuzden pencere kapatilip acildiginda gecmis kaybolmaz",
      "Uzaktan baslatma ek program kurulumu GEREKTIRMEZ: Windows 10 ve sonrasinda yerlesik olan OpenSSH istemcisi kullanilir. Kimlik dogrulama basarisiz olursa veya komut uc saniye icinde olurse sessizce gecmez, sebebini yazan bir satir dusulur",
      "Dron haberlesmesi artik genel konsolu kirletmiyor: her dron panelinin altinda acilir kapanir bir konsol var ve o dronun tum haberlesmesi ciplak olarak orada gorunur. Satirlar panel kapaliyken de birikir, acildiginda gecmis yerine oturur; tekrarlayan satirlar cogaltilmaz, yaninda sayaci artar",
      "Uyari ve hata niteligindeki dron mesajlari genel konsolda da kalir, cunku ekranin sagindaki bildirim balonlari bu satirlardan uretilir. Boylece kirlilik kalkarken uyari kaybolmaz",
      "Ucus duvarina tam ekran eklendi: ust seritteki dugme sayfayi, her panelin basligindaki dugme o paneli tam ekrana alir. F tusu sayfayi, 1-6 tuslari ilgili paneli acar, Esc cikar. Tarayici tam ekran iznini reddederse sayfa ici tam ekran devreye girer, boylece dugme her kosulda is gorur",
    ],
  },
  {
    s: "2.4.44", t: "2026-08-09",
    d: [
      "Iki ekranli sahra cantasindaki ESP32-S3 kontrol paneli (Yer Istasyonu 2) programa alindi: 11 push buton, 2 kol, 2 analog joystick ve 7 LED cikisi USB seri porttan okunuyor. Ayri bir kopru programi CALISTIRMAK GEREKMEZ; panel main.py ile birlikte acilir",
      "Panelin seri portu Program Ayarlari yerine dogrudan panel penceresinden girilir ve kalici olarak saklanir. Varsayilan /dev/ttyACM0, Windows'ta COM7 gibi bir deger yazilabilir; port takili degilse program normal acilir ve panel iki saniyede bir yeniden dener",
      "Ucus dugmeleri yalniz joystick (manuel) kontrolu ACIK dronlarda is gorur: P1 ARM/DISARM, P2 TAKEOFF/LAND, P3 RETURN HOME, P4 GUIDED, P5 ALT_HOLD, P6 AUTO. Anahtar kapaliyken cantadaki bir dugmeye yanlislikla basmak komut gondermez, ekranda sebebi yazan bir uyari cikar",
      "P1 ve P2 degismelidir: dron ARM ise P1 DISARM eder, havadaysa P2 LAND eder. Havada olma olcutu ARM durumu ile zemine gore bir metre irtifanin birlikte saglanmasidir, boylece motor calisirken yerde bekleyen dron havada sayilmaz",
      "Mod dugmeleri arac tipini dikkate alir: kopterde GUIDED 4 iken sabit kanatta 15'tir. Sabit kanatta ALT_HOLD bulunmadigi icin P5 QHOVER moduna gecer; modun bulunmadigi araclarda komut hic gonderilmez",
      "T1 kolu patlatma koludur: kol acildiginda panelin P7 LED'i yanar ve ekranda Patlatmak icin emin misiniz onayi acilir. Kol kapatildiginda LED soner ve onay penceresi kendiliginden kapanir, cunku tek dogruluk kaynagi fiziksel koldur",
      "Iki panel joystick'i haritanin uc boyutlu kontrolune baglandi: sol cubuk dondurme ve egim, sag cubuk kaydirma. Hareket cizim karesine gore uygulandigi icin akicidir ve kamera yuksekligiyle olceklenir; bir kilometrede uygun olan hiz yuz kilometrede felce yakin olmaz",
      "T2 kolu zoom denetler: yukari yakinlastirir, asagi uzaklastirir, ortada durur. Zoom sirasinda yerin altina inilmez",
      "Harita dugmeleri: P8 harita kaynagini sirayla degistirir, P9 kullanici konumuna gider, P10 haritadaki tum nesneleri kapsayacak sekilde zoomlar, P11 her basista haritadaki noktalar arasinda sirayla gezer",
      "Cantadaki EK iki joystick dronu ucurur (panel cubuklari haritayi surer, birbirine karismaz). Ayni karttan ek eksen olarak gelirlerse otomatik taninir ve manuel kontrole aktarilir; bilgisayara ayri USB joystick olarak takilirlarsa mevcut joystick yolu kullanilir",
      "Panel kopukse veya joystick kontrolu kapatilmissa eksenler sifirlanir; kopan bir kablo dronun havada surekli yana kaymasina yol acmaz",
      "Dronlar menusune Yer Istasyonu 2 penceresi eklendi: canli buton izgarasi (LED cikisi olan yedi dugme ayirt edilir), kol durumlari, iki joystick icin gorsel gosterim, LED denetimi, kalibrasyon, olay akisi ve alinan mesaj, gecikme, bozuk satir sayaclari",
      "Joystick orta noktasi sabit varsayilmaz: Kalibre et dugmesi o anki cubuk degerlerini merkez olarak kaydeder ve deger kalici saklanir. Kalibrasyon yapilmadan da olu bolge ile guvenli calisir",
      "Protokolun iki tuzagi ozellikle ele alindi: PING cevabi olan PONG duz metindir ve JSON cozumlemesinden once ayrilir; T2 degeri metin, digerleri sayidir. Ayrica Windows'ta port duzgun kapatilmadiginda olusan ReadFile hatasi engellendi",
    ],
  },
  {
    s: "2.4.43", t: "2026-08-09",
    d: [
      "Telemetri tamponu Windows'ta ayni dosyayi sonsuz dongude okuyup veritabanina tekrar tekrar yaziyordu. Belirti: konsolda [WinError 32] dosya baska bir islem tarafindan kullaniliyor uyarisi ve pesinden hep ayni ornek sayisinin aktarildigi satir. Kok neden: tampon dosyasi hala yazim icin acikken aktarilmaya calisiliyor, Windows acik dosyayi yeniden adlandirmaya izin vermedigi icin aktarildi isareti konamiyor, bir sonraki turda ayni dosya yeniden okunuyordu",
      "Aktarim artik yazim icin acik olan dosyayi hic ele almiyor; dosya bayatlamissa once duzgun kapatilip sonra aktariliyor. Isaretleme basarisiz olursa dongu o turda durur, boylece ayni veri ikinci kez yazilmaz",
      "Mukerrer telemetri satirlari icin tekilleme eklendi: ayni dron ve ayni zaman damgasi artik veritabaninda bir kez durur. Yukseltmede once mevcut mukerrer satirlar temizlenir, sonra tekilleme kurulur; bu islem bir kez calisir ve kac satir silindigi konsola yazilir",
      "Ayni sanal baglanti kaydinda ikinci bir SITL baslatildiginda arayuz yalniz ikinci dronu goruyordu: iki dinleyici ayni baglanti kimligiyle kaydediliyor, ikincisi birincisini kapatiyordu. Iki sanal dronla angajman denemesi bu yuzden yapilamiyordu; her ek ornek artik kendi kimligini alir",
      "Angajman gudumu hedefin gorev durumunu okuyabiliyor: hedef AUTO modda rotada ucuyorsa saldiran, hedefin bulundugu yere degil hedefin gidecegi noktaya nisan alir. Cozum sirasiyla hedefin gorev bacagindan, o yoksa hiz vektorunden uretilir",
      "Kesisme cozumu her donguda yeniden hesaplanir ve saldiranin gercek hizi ile hedefin hizi birlikte cozulur; hedef daha hizliysa cozum uretilmez ve sistem sessizce saf takibe doner (yanlis bir nokta uydurmaz)",
      "Bu davranis zorunlu degil: Angajman ayarlarina Hedefin gorev rotasini dikkate al ve Ongorulu kesisme gudumu anahtarlari eklendi. Ikisi de kapatilabilir, kapatildiginda onceki dogrudan takip davranisi aynen calisir",
      "Angajman izleme penceresi artik cozumun nereden geldigini (gorev bacagi mi hiz vektoru mu), kesisme suresini ve nisan sapmasini gosteriyor; pilot gudumun neye gore davrandigini gorebilir",
      "Angajman ayarlari kaydedilmiyordu: ayar sozlugu her okumada sifirdan uretildigi icin degistirilen deger bir sonraki angajmanda kayboluyordu. Ayarlar artik kalici ve program yeniden baslatildiginda da gecerli",
      "Radar hedeflerinin hiz vektoru angajmana tasindi: radar izinden gelen hedeflerde de kesisme cozumu uretilebiliyor",
      "Kayitli Dronlar paneli yeniden boyutlandirilabilir; verilen boyut hatirlanir ve panel bir sonraki acilista ayni olculerde gelir",
      "Sanal dron ARM edilemiyordu (PreArm: 3D Accel calibration needed): sanal dron gorev ucusuna cikamadigi icin angajman denemesi yapilamiyordu. Yalnizca sanal dronu etkileyen bu engel kaldirildi, gercek dron parametreleri hic degismez",
    ],
  },
  {
    s: "2.4.42", t: "2026-08-09",
    d: [
      "Ucus raporunda pilot alanina e-posta adresi yaziliyordu; artik pilotun adi soyadi basiliyor. Ad kaynagi sirasiyla telemetri kaydindaki pilot adi, kullanici defterindeki ad soyad ve son care olarak e-postadir, boylece eski kayitlarda da isim cikar",
      "Ucus raporundaki Arac Turu alani BILINMEYEN yaziyordu: bu alan arac sinifi yerine baglanti etiketini okuyordu. Artik otopilotun bildirdigi MAV_TYPE degerinden gercek sinif uretiliyor (sabit kanat, helikopter, VTOL, multikopter) ve kalkis kontrol listesiyle ayni esleme kullanildigi icin iki belge celismiyor",
      "KAMIKAZE veya DJI gibi kullanici etiketleri silinmedi, raporda Platform Etiketi satirina tasindi; MAV_TYPE henuz okunmamissa arac turu satiri hic yazilmiyor, imzali belgeye tahmin girmesin",
      "Her ucusa kisa benzersiz ucus kodu verildi (XXXX-XXXX): elde tutulan imzali cikti ile sistemdeki kayit bu kodla eslestirilebiliyor. Kod deterministik uretilir, ayni ucus her zaman ayni kodu alir; sunucu yeniden baslasa veya rapor aylar sonra alinsa kod degismez",
      "Kod alfabesinde I, L, O ve U harfleri yok: 1/I ve 0/O karisikligi kodu telefonla okurken ve elle ararken hata uretiyordu",
      "Ucus kodu ucus gecmisi listesinde, imzali ucus raporunda ve grafik ciktisinda ayni bicimde gorunuyor",
      "Tum raporlara ucus kodu QR olarak basiliyor. QR icerigi duz koddur, adres degil: saha kurulumunda internet olmadigi icin adres tasiyan bir QR okutuldugunda bos sayfa acilirdi. Kod metni QR'in yaninda da basilir, boylece fotokopi veya tarama sonrasi QR bozulsa belge yine eslestirilebilir",
      "QR ureteci sisteme dahil edildi; harici kutuphane veya internet baglantisi gerektirmez, cikti vektorel oldugu icin baskida keskin kalir",
      "Ucus Gecmisi alt seridine GRAFIKLER dugmesi eklendi (rapor dugmesinin solunda): secilen ucusun irtifa, hiz, yon, batarya yuzdesi, batarya voltaji, kat edilen mesafe ve tirmanma hizi serileri cizilir",
      "Grafik penceresinde seriler tek tek acilip kapatiliyor, ayni grafige birden fazla seri bindirilebilir. Farkli birimler icin sol ve sag iki ayri olcek kullanilir, boylece metre ile voltaj ayni eksende sikismaz",
      "O ucusta verisi olmayan seri listeden gizlenmiyor, ustu cizili ve pasif gosteriliyor: seri yok ile veri kaydedilmemis durumu ayirt edilebilsin",
      "Grafik ciktisi yatay antetli kagida yazdirilabiliyor: sirket anteti, ucus kodu ve QR, seri istatistik tablosu (en kucuk, en buyuk, ortalama) ile PILOT ve SAHA SORUMLUSU imza bloklari icerir",
      "Dronlar menusune KAYITLI DRONLAR eklendi: sisteme bugune kadar girmis ve kimlik verilmis tum dronlar ucus adedi, toplam sure ve son ucus zamaniyla listelenir. Panel her acilista yenilenir, baslikta yenile dugmesi vardir ve bir drona tiklandiginda o dronun ucus kayitlari filtrelenir",
      "Kayitli Dronlar listesinde pilot yalnizca kendi ucurdugu dronlari gorur; sistem yoneticisi tum dronlari ve her satirda pilot adini gorur. Yetki suzgeci ucus gecmisiyle ayni sunucu kodunda tutuldu, ikinci bir kopya cikarilmadi",
      "Haritada SHIFT basili tutularak sol tiklandiginda dron listesi aciliyor ve secilen dronun HOME (kalkis/donus) noktasi tiklanan konuma ayarlaniyor. CTRL ile ayni tiklama dronu o konuma gonderir; iki kip menu basliginda ve renginde ayrilir",
      "Dron Islemler panelinde HOME AYARLA ogesi eklendi: dronun o andaki konumu HOME olarak ayarlanir",
      "HOME ayarlamasi RTL ve failsafe donus noktasini degistirdigi icin once onay soruluyor, sonuc ise sag kose bildirimi olarak teyit ediliyor; sessiz basarisizlik yok",
      "Her dronun HOME noktasi haritada o dronun renginde ev ikonu olarak gorunuyor ve altinda dron adi yazar; birden fazla dron ucarken hangi HOME'un hangi araca ait oldugu ilk bakista anlasilir",
      "HOME atanmamis dron artik ucusa hazir sayilmiyor: hazir rozeti kirmiziya donuyor ve denetim listesinde HOME maddesi en ustte gosteriliyor. Gerekce: HOME tanimsizken RTL ve batarya failsafe nereye donecegini bilmez",
      "Kalkis oncesi kontrol listesi hic okunamiyordu: sunucu ucus kaydini okurken tanimsiz bir modul adina dusuyor ve hatayi yutuyordu, bu yuzden v2.4.41'de eklenen kontrol listesi bolumu raporlarda hep bos cikiyordu. Duzeltildi",
    ],
  },
  {
    s: "2.4.41", t: "2026-08-08",
    d: [
      "TAKEOFF artik kalkis oncesi kontrol listesi ile aciliyor: maddeler dron tipine gore degisir (sabit kanatta servo yuzeyleri ve pitot, multirotorda pervane yonu ve gobek sikiligi, interceptorda ayrica angajman guvenlik mesafesi), her madde iPhone tarzi ikili slider ile yanitlanir (sol kirmizi HAYIR, sag yesil EVET)",
      "Kontrol listesi tek bir sabit sorular kumesi degil: dronun o anki telemetrisinden (GPS kilidi, EKF, batarya, RC, mod) ve otopilottan okunan ARM denetim parametrelerinden ek maddeler uretilir, boylece liste ucusa girecek gercek araca gore sekillenir",
      "TAKEOFF'U TAMAMLA dugmesi TUM maddeler EVET olmadan pasif kalir; kalkis komutu ancak listeyi tamamladiktan sonra gonderilir",
      "Tamamlanan her kontrol listesi veritabanina yaziliyor: tarih, saat, pilot kimligi, dron ve hangi maddeye ne yanit verildigi madde madde saklanir (kalkis_kontrol ve kalkis_kontrol_madde tablolari)",
      "Pilot kumandadan modu AUTO'ya aldiginda gorev izleme paneli kendiliginden aciliyor; gorev arayuzden baslatilmadigi icin panel kapali kalmiyor",
      "Dron Islemler panelinde GOREV IZLE ogesi eklendi: kapatilan gorev izleme paneli aktif gorevle birlikte geri cagrilabiliyor",
      "Gorev izleme panelinde gorevin ne kadarinin UCULDUGUNU gosteren ayri bir ilerleme cubugu var; ustteki cubuk gorevin drona YUKLENME ilerlemesini gosterir, ikisi karistirilmasin",
      "Gorev izleme panelinin telemetri tazeleme fonksiyonu v2.4.35'ten beri her pakette tanimsiz bir degiskene dusuyordu; hata ust katmanda yutuldugu icin sistem cokmuyor ama o satirdan sonraki kod hic calismiyordu. Sonucu: batarya degisimi icin eklenen KALDIGI YERDEN DEVAM ET satiri ve gorev yukleme cubugu hic guncellenmiyordu. Duzeltildi",
      "Drona baglanildigi anda tum parametreler bir kez otomatik cekiliyor; dron kartinin en altinda ince bir ilerleme seridi ilerlemeyi gosterir ve tamamlaninca kendiliginden kaybolur. Boylece hiz paneli, ARM denetimi ve parametre ekrani ilk acilista bekletmeden aciliyor",
      "Sistem yoneticisi programi ilk kez actiginda sirket bilgileri sihirbazi zorunlu olarak aciliyor: logo, unvan, adres ve telefon alinmadan sisteme girilemez. Yonetici olmayan kullanici, bilgiler tanimsizken bilgilendirilir ve yoneticiye yonlendirilir",
      "Kullanici menusune (yalnizca sistem yoneticisine gorunur) SIRKET BILGILERI ogesi eklendi; ayni alanlar sonradan duzenlenebilir ve degisiklik tum istemcilere aninda uygulanir",
      "Ucus Gecmisi ekranina RAPOR OLARAK INDIR dugmesi eklendi: sirket antetli (logo, unvan, adres, telefon, vergi no) resmi ucus raporu uretilir; hava araci ve personel bilgileri, ucus ozeti (sure, mesafe, maksimum irtifa ve hiz), SAAT SAAT ucus cizelgesi, AI tespitleri ve PILOT ile SAHA SORUMLUSU icin imza bloklari icerir",
      "Rapor tarayicinin yazdirma motoruyla uretiliyor; ayni penceredeki PDF olarak kaydet ile PDF alinir. Sunucuda PDF uretmek Turkce karakterler icin font gomme ve ek paket kurulumu gerektiriyordu, bu da mevcut kurulumlarda calismama riski tasiyordu",
      "Dataflash log indirme baglantisi duzeltildi: log dosyalari diskte dron_loglari/ altina yaziliyor ama arayuze /loglar/ adresi veriliyordu ve bu onek icin sunucuda esleme yoktu, yani indirme tamamlandiktan sonra baglanti 404 donuyordu. Indirme motoru calisiyordu, kirilan yalniz son adimdi",
    ],
  },
  {
    s: "2.4.40", t: "2026-08-08",
    d: [
      "Rotalar menusune KORIDOR rota turu eklendi: yukseklik, tur sayisi, koridor genisligi ve seyir hizi sorulur, ROTA EKLE ile harita duzenleme moduna gecilir",
      "Koridor cizimi: haritaya tiklanan noktalar koridorun ORTA HATTINI olusturur, nokta ekledikce koridor iki yana genisler ve ortasi seffaf mavi boyanir",
      "GOREVI TAMAMLA ile rota noktalari koridorun SOL ve SAG kenarina atilir; gidis sol kenardan, donus sag kenardan olacak sekilde kapali tur uretilir ve tur sayisi kadar tekrarlanir",
      "Kose gecisleri mitre yontemiyle hesaplanir (kose ofseti 1/cos(yarim aci)) ve 2.5 kati ile sinirlanir: sinir olmadan keskin bir kose kenar noktasini koridordan kilometrelerce disari firlatir ve rotayi kullanilamaz kilar",
      "Rotalar menusunde Yeni Rota altina ve Rota Yukle ustune ayrac eklendi: cizim ureten rota turleri ile dosya/gorunum islemleri ayri gruplara alindi",
      "Koridor rotasi cift tiklandiginda veya ROTAYI DUZENLE ile kendi popup'inda acilir. Genel nokta editorunde acilsa noktalar sol/sag kenar taramasi olarak gorunur ve tek bir noktayi tasimak koridor geometrisini kalici bozardi (orta hat meta'da tutulur, editor onu bilmez)",
      "SANAL baglanti rozetinin rengi eksikti (.bag-tur-sanal CSS'te tanimsizdi, rozet soluk cikiyordu); DJI rozetiyle birlikte duzeltildi",
    ],
  },
  {
    s: "2.4.39", t: "2026-08-08",
    d: [
      "Baglanti Yoneticisine SANAL dugmesi eklendi: dron tipi (multirotor / sabit kanat / interceptor), baslangic konumu ve adet sorulur, dronlar SANAL grubu altinda listelenir. Baslangic konumu haritanin o anki merkezinden gelir",
      "Sanal dron taklit degil, gercek bir ArduPilot SITL surecidir: parametreler, ARM on denetimleri, ucus modlari ve gorev davranisi gercek ucus yaziliminin kendisinden gelir. Kendi yazdigimiz bir benzetim, gercek firmware ile ayni davranmayacagi icin ARM CHECK ve gorev akisini sinamaya yaramazdi",
      "Sanal dronlar gercek dronlarla ayni kod yolunu kullanir: ayni komut yolu, ayni UDP disa aktarimi, ayni angajman destegi. Sanal dron icin ayri bir kod yolu YOK, boylece angajman denemeleri gercek ucusla ayni davranisa karsi yapilabilir",
      "Adet birden buyuk verildiginde her dron KENDI SITL sureci olarak dogar; her birine ayri sysid ve ~30 m ayrik baslangic konumu verilir (ayni sysid'li iki arac birbirinin telemetrisini ezer, ayni noktada dogan araclar haritada tek ikon gibi gorunur)",
      "SITL ikilisi (~30 MB) guncelleme paketine gomulmez, ilk kullanimda istek uzerine indirilir; ikili yoksa hata metni yerine dogrudan indirme dugmesi cikar ve indirme ilerlemesi gosterilir",
      "Dron kartinin ayir/dock dugmesi carpi (kapat) ikonuna cevrildi; islev degismedi - panelde ayirir, ayrik pencerede kapatip karti panele geri dondurur",
      "UDP disa aktarim panelinde artik gercek yerel ag adresi gosteriliyor: dinleme zaten 0.0.0.0 uzerindeydi, kusur gosterilen adresteydi. Panel tarayicinin adres cubugundaki host adini yaziyordu, yani 127.0.0.1 uzerinden acan kullaniciya loopback adresi veriliyor ve baska makineden baglanmak imkansiz gorunuyordu",
    ],
  },
  {
    s: "2.4.38", t: "2026-08-08",
    d: [
      "Hiz panelinden yapilan degisiklik artik gercekten kaydediliyor: sunucuda parametre yazma dali, yalnizca durumu tam olarak 'bagli' olan bir link varsa acilan bir kosulun arkasindaydi; link yeniden kurulurken veya coklu baglantida baska bir link etkinken komut hic gonderilmeden dusuyordu. Ayni parametrenin Parametreler ekranindan yazilabilmesinin nedeni, o yolun bu kosulun arkasinda olmamasiydi",
      "Yazma sonucu artik arayuze bildiriliyor: basarili yazmada onay, basarisiz yazmada gerekcesiyle hata bildirimi cikiyor. Eskiden hicbir yanit gonderilmedigi icin basarisizlik ile basari kullanici acisindan ayirt edilemiyordu",
      "Parametre degisiklik gecmisi yalniz basarili yazmalari kaydediyor: eskiden kayit kosulsuz dusuyordu, yani drona hic ulasmamis bir degisiklik de gecmiste 'yazildi' olarak goruluyordu",
      "Hiz paneli her acilista drondan parametre okumuyor: once bellekteki onbellek, sonra Parametreler ekraninin cektigi tam set, en son sunucudaki veritabani onbellegi kullaniliyor - ucuncu asamada bile drona istek gitmiyor",
      "Onbellek yoksa alanlar uydurma varsayilan yerine bos aciliyor ve UYGULA bu alanlari gondermiyor: onceki davranista panel varsayilan bir deger gosteriyor, kullanici o alana hic dokunmasa bile UYGULA bu degeri drona yaziyordu",
      "Parametre yazildiktan sonra panel yeni degeri gosteriyor; basarisiz yazmada onbellek degismiyor, boylece drona ulasmamis bir deger panelde dogruymus gibi gorunmuyor",
      "Parametreler ekraninin cektigi tam set ile hiz paneli ayni onbellegi paylasiyor: TUMUNU AL bir kez calistirildiginda hiz paneli hic ag istegi yapmadan aciliyor ve iki ekran ayni degeri gosteriyor",
    ],
  },
  {
    s: "2.4.37", t: "2026-08-08",
    d: [
      "ARM CHECK listesindeki 'Itki / Motor' maddesi kaldirildi: ArduPilot bu sensor bitini hic yaymadigi icin madde her aracta 'yok' degeriyle kalici bir uyari uretiyordu; arac her yonuyle saglikli olsa bile hazirlik gostergesi surekli amber kaliyor, boylece uyari isareti hicbir sey ifade etmez hale geliyordu",
      "Madde hicbir kosulda bilgi tasimiyordu: bit hic gelmedigi icin 'saglikli' ile 'arizali' ayrimi da hic olusmuyordu. Artik temiz telemetride uyari sayisi gercekten sifir, dolayisiyla amber cerceve yalnizca gercek bir uyari varken beliriyor",
      "Gercek arizalarin yakalanmasi etkilenmedi: pusula, jiroskop, GPS, EKF, titresim ve batarya denetimleri oldugu gibi calisiyor; itki bitini gercekten yayan VTOL/ozel ucus yazilimlari icin sabit kaynakta korundu",
      "Baglanti Yoneticisi'ndeki seri baud listesi 115200'de bitmiyor: 230400, 250000, 460800, 500000, 921600, 1000000 ve 1500000 eklendi (250000 ve 1000000 ArduPilot telemetri donanimlarinda yaygin, 921600 ve uzeri USB-seri koprulerde kullanilir)",
      "Varsayilan hiz 57600'de birakildi (RFD900X fabrika ayari), yani mevcut baglantilarin davranisi degismedi",
      "Kayitli bir baglantinin baud degeri listede yoksa artik sessizce kaybolmuyor: standart disi bir hiz duzenleme ekraninda korunuyor - onceki davranista secici ilk secenege (9600) dusuyordu ve kullanici farkinda olmadan kaydettiginde baglanti hizi bozuluyordu",
    ],
  },
  {
    s: "2.4.36", t: "2026-08-08",
    d: [
      "Dron kartinin baslik cercevesi artik ucusa hazirlik durumunun rengini tasiyor: hazir arac yesil, kalkisi engellemeyen uyarisi olan arac yesil zemin uzerinde amber cerceve, hazir olmayan arac kirmizi, ucmakta olan arac mavi cerceveyle gorunur; telemetri gelmiyorsa gri kalir cunku veri yokken yesil gostermek yanlis guven, kirmizi gostermek yanlis alarm uretir",
      "Bu gostergenin asil degeri kartlar KAPALIYKEN ortaya cikar: 'UCUSA HAZIR' rozeti kart govdesinin icinde oldugu icin, kartlar varsayilan olarak katli geldiginde hazirlik durumu kartlar tek tek acilmadan gorunmuyordu; baslik cercevesi kapali kartta da gorundugu icin cok dronlu panelde hangi aracin kalkabilecegi tek bakista anlasilir",
      "Cerceve rengi rozetin kendi hesabindan tureyip ayni renk sozlugunu kullanir; boylece rozet ile baslik hicbir kosulda birbirinden ayrisamaz",
      "Cerceve icin kenarlik yerine ic golge kullanildi: kart kirpma ve kose yuvarlama tasidigi icin gercek kenarlik eklemek kartin ic olculerini buyutup telemetri satirlarini oynatiyordu, ic golge yer kaplamaz - baslik yuksekligi ve genisligi degismedi",
      "Takip grubunu gosteren mor ust cizgi durum cercevesiyle birlikte yasar, ikisi birbirini gizlemez",
      "Baslik uzerine gelindiginde rengin ne anlama geldigi yazili olarak da bildirilir (renk korlugu ve kalabalik panel icin)",
    ],
  },
  {
    s: "2.4.35", t: "2026-08-08",
    d: [
      "Ucusa hazir gostergesi artik turuncu degil yesil: arac kalkisa hazir oldugu halde kalkisi engellemeyen tek bir uyari maddesi bulundugunda rozet bastan asaga turuncuya cevriliyordu; kalkisi engelleyen maddeler zaten kritik sayilip hazir durumunu dusurdugu icin uyari yalnizca kenarlik ve kucuk bir uyari isaretiyle bildiriliyor, zemin yesil kaliyor (ayni duzeltme ARM CHECK penceresinin ozet satirina da uygulandi)",
      "Gorev basladiginda rota haritadan silinmiyor ama one cikmiyor: cizgi incelip soluklasiyor, nokta numaralari, START/FINISH etiketleri, mesafe yazilari ve donus daireleri gizleniyor - ucan aracin kendi etiketiyle cakismiyor",
      "Gorev tamamlandiginda, iptal edildiginde veya duraklatildiktan sonra sonlandirildiginda rota haritadan kaldiriliyor",
      "Gorev bitisi artik algilaniyor ve durum 'Gorevde' yerine 'Gorev tamamlandi' oluyor: son rota noktasina ulasildiktan sonra aracin otomatik kipten cikmasi, inise gecmesi veya motorlarin durmasi beklenir; yanlis 'tamamlandi' bildirimini onlemek icin gorevin en az bir kez gercekten otomatik kipte gorulmus olmasi, gecerli bir nokta numarasi gelmesi ve baslangictan bu yana asgari surenin gecmesi sart",
      "Gorev yukleme ekranina 'gorev durdurulunca ne olsun' ayari eklendi: 'Durdugu yerde beklesin' veya 'Baslangic noktasina donsun'; ilaclama gibi uzun gorevlerde batarya degisimi icin durdugu yerde beklemesi, uzun aralarda ise baslangica donmesi secilebilir",
      "Gorev duraklatma artik sessizce basarisiz olamiyor: eski surumde duraklatma komutu gonderilip sonuc hic dogrulanmiyordu, aracin kip degisimini reddetmesi durumunda arayuz 'duraklatildi' yazarken arac gorevi ucurmaya devam ediyordu; kip degisimi telemetriden dogrulaniyor, dogrulanamazsa duraklatildi denmiyor ve gerekce bildiriliyor",
      "Batarya degisimi icin kesilen gorevler kaldigi yerden surdurulebiliyor: gorev tamamlanmadan dron baglantisi koparsa kaldigi nokta diske yaziliyor, dron yeniden baglandiginda gorev penceresinde 'kaldigi yerden devam et' onerisi cikiyor; onaylandiginda rota yeniden yuklenmeden kalinan noktadan devam edilir",
      "Surdurme kaydi program yeniden baslatilsa bile korunuyor; gorev tamamlandiginda veya iptal edildiginde kayit temizlenir, yeni bir gorev yuklendiginde eski kayit silinir",
      "Dron kartinin basligindaki ok ikonuna basinca panel yeniden acilip kapaniyor: kart ayri pencereye alinip tasinabilir hale geldiginde baslik surukleme islevi tiklamayi yuttugu icin ok calismiyordu",
      "Basligi kapatilmis dron kartlari birbirine yaklastirildiginda miknatis etkisiyle kenar kenara yapisiyor ve birlikte tasiniyor (widget'lardaki davranisin aynisi); basligi acik kartlar govde yukseklikleri farkli oldugu icin yapismaz",
      "Pusula widget'i gercek 3 boyutlu hale getirildi: harita egildiginde pusula kadrani da ayni acida egilir, ibre ve isaret cizgisi sabit kalir; sag ustteki dugmeyle 2B/3B arasinda gecis yapilabilir ve secim hatirlanir - dusuk donanimli bilgisayarlarda kapatilabilir",
      "Pusula 3B icin ayri bir ekran karti baglami acilmadi; harita motorunun kullandigi grafik gucunden pay calmamak icin tarayicinin kendi 3 boyutlu donusum katmani kullanildi, boylece kadran yazilari da keskin kaliyor",
    ],
  },
  {
    s: "2.4.34", t: "2026-08-07",
    d: [
      "Turkce-Ingilizce ceviri kapsamasi tamamlandi: Ucus Duvari (/flight) ve Video Duvari (/video) sayfalari dil sozlugune hic erisemiyordu, cunku sozluk dosyasi yalnizca ana sayfada bulunan dil dugmesine dogrudan baglanmaya calisiyor, dugme olmayan sayfada bu satir hata verip dosyanin geri kalanini durduruyordu; bu iki sayfa artik dil secimini uyguluyor",
      "Ikon dugmelerin fare ustundeki ipuclari ve form alanlarinin yer tutucu yazilari Ingilizce'de Turkce kalmiyordu: bu metinler HTML nitelikleri icinde durdugu icin ceviri dongusunun disinda kaliyordu, artik nitelikler de cevriliyor",
      "Kamera turu ve protokol secenekleri, radar menusu bolum basliklari, durum cubugu ipuclari ve Hakkinda penceresi surum satiri cevrildi",
      "Video Duvari'nda dil degistirildiginde panel basliklari, kamera secim listeleri ve dugme yazilari eski dilde kaliyordu; artik tazeleniyor ve dil degisimi canli yayini kesmiyor",
      "Ucus Duvari'nda yerlesim dugmeleri, dron secim listeleri ve baglanti durumu yazilari cevrildi; gosterge uzerindeki DRON SECILMEDI yazisi da dile uyuyor",
      "Haritaya 'tumunu sigdir' dugmesi eklendi (cetvelin altinda): haritadaki tum dronlari, hedefleri, radar kapsamini, kameralari ve kayitli lokasyonlari ayni gorunume alacak sekilde uzaklasir; tek bir varlik varsa yalnizca ona odaklanir, hicbiri yoksa bunu bildirir",
      "Haritaya 'konumuma git' dugmesi eklendi: tarayicidan konum izni alinarak bulundugunuz noktaya ucar; izin verilmezse veya konum alinamazsa gerekcesiyle bildirilir",
      "Yeni Sistem Kaynaklari widget'i: tarayicinin cizim yuku ve kare hizi, JS bellek kullanimi, ag transfer hizi ve sunucunun gercek isletim sistemi CPU/RAM olcumu canli sparkline grafiklerle gosterilir; GOKTUNGU surecinin kendi payi sunucu toplamindan ayri yazilir",
      "Sistem Kaynaklari widget'i sunucu olcumu icin psutil kullanir; kurulu degilse Linux'ta /proc uzerinden olcer, o da yoksa yalniz tarayici degerlerini gosterir - eksik paket yuzunden acilis engellenmez",
      "Dron kartinin basliginda irtifa ile ucus kipi arasina bosluk kondu ve yazi bir kademe kucultuldu",
      "Kamera goruntusu gelmediginde kutuda 'baglanti kurulamadi' yerine gercek gerekce yaziliyor (ornegin ffmpeg kurulu degil); sunucu bu gerekceyi yanit basliginda tasiyor",
      "Acilista ffmpeg denetimi eklendi: ag kameralari icin zorunlu olan bu program kurulu degilse konsolda kurulum yonergesiyle uyarilir",
      "Surum Gecmisi penceresinde surum basliklarinin gorunmemesi giderildi: baslik icin kullanilan stil sinifi hicbir yerde tanimli degildi",
      "Bicem denetim araci genisletildi: dron karti ve surum gecmisi onekleri taniniyor; ceviri denetim aracinda satir numaralarini kaydiran ve cevrilmis metinleri kusur sayan olcum hatalari duzeltildi",
    ],
  },
  {
    s: "2.4.33", t: "2026-08-07",
    d: [
      "Ayrı DRONLAR penceresi tümüyle kaldırıldı: dronlar yalnızca Bağlantı Yöneticisi içinde, bağlı oldukları bağlantının altında listeleniyor; menüdeki eski panel girişi yerini Uçuş Duvarı girişine bıraktı",
      "Bağlı bir bağlantının altında dron görünmemesi giderildi: dronu bağlantısıyla eşleştiren işlev v2.4.32'de yazılmış ancak hiçbir yerden çağrılmıyordu, bu yüzden her dron bilinmeyen bağlantı grubuna düşüyor ve o grup gizli kaldığı için hiç görünmüyordu",
      "Bir bağlantıda dron yokken grup gövdesi artık boş kalmıyor: eski panelde olduğu gibi ortada soluk bir dron ikonu ve açıklama yazısı gösteriliyor",
      "Bazı bilgisayarlarda radar kapsama kubbesinin harita üzerinde dev bir tel küre ve ızgara olarak görünmesi giderildi: kubbe artık ekran kartı sürücüsünün yorumuna bırakılan dış hat çizimiyle değil, doğrudan hesaplanan yatay ve düşey kesit çizgileriyle çiziliyor",
      "Program içindeki hata ve uyarılar ekranın sağ üst köşesinde beliren bildirim kartlarıyla duyuruluyor ve birkaç saniye sonra kendiliğinden kayboluyor; hata bildirimleri daha uzun kalıyor ve fare üzerindeyken kaybolmuyor",
      "Dronun reddettiği komutlar artık sessiz kalmıyor: kalkış, arm, kip değişimi gibi bir komut kabul edilmezse hangi komutun hangi gerekçeyle reddedildiği bildirim olarak gösteriliyor",
      "Ağ üzerinden yayın yapan kameraların ilk karesi gelmeden bağlantının başarısız sayılması giderildi: yavaş açılan kaynaklarda ilk kare bekleniyor, ayrıca kaynak analizi hızlandırıldığı için ilk görüntü belirgin şekilde daha erken geliyor",
      "Kamera görüntüsü koptuğunda yayın kendiliğinden yeniden deneniyor: bekleme süresi kademeli artıyor, sekme arka plandayken denemeler duruyor ve öne gelince kaldığı yerden sürüyor",
      "Kamera ayrı pencereye alındığında Kameralar listesinden kaldırılıyor: aynı yayın iki yerde birden çözülmediği için işlemci ve ağ yükü ikiye katlanmıyor; pencere kapatıldığında kamera listeye geri dönüyor",
      "Widget yenileme düğmeleri tek bir standarda getirildi: her widget'ta gövde içinde farklı biçimlerde duran düğmeler kaldırıldı, yerine başlık çubuğunda beliren tek bir kırmızı yenileme ikonu geldi",
      "Hava Durumu widget'ında sıcaklık ve rüzgar yönü blokları satır ortasına alındı",
      "Konum widget'ı ikonlu serbest akış yerine tablo düzenine geçirildi: Adres, Lokasyon ve Kapsam satırları hizalı etiket ve değer olarak yazılıyor, yazı boyutu bir kademe küçültüldü ve satır aralıkları açıldı",
      "Pusula widget'ında derece ve bakış yönü alt alta değil aynı satırda, derece solda bakış sağda olacak şekilde gösteriliyor",
      "Yeni Sayaç widget'ı: başlat, duraklat ve sıfırla düğmeleriyle çalışan milisaniye çözünürlüklü kronometre; geçen süre sekme arka plandayken de doğru sayılıyor ve tur kaydı tutuluyor",
      "Durum çubuğuna harita önbellek boyutu göstergesi eklendi: harita gezildikçe inen yeni karolarla birlikte boyut kendiliğinden güncelleniyor",
      "Önbellek boyutu ölçümü tüm klasörü tarayan yöntemden vazgeçilerek çalışan toplam üzerine kuruldu: gigabaytlık önbelleklerde ölçüm telemetri akışını durduruyordu, artık her yeni karo yalnızca kendi boyutunu ekliyor",
      "Arayüz Ayarları penceresindeki telsiz hızı ve port seçimiyle ilgili bilgi notu kaldırıldı",
      "Dil değiştirildiğinde widget içi etiketlerin eski dilde kalması giderildi: widget'lar dil değişimini bildiren çağrıyı tanımlıyor ancak bu çağrı hiçbir yerden yapılmıyordu",
    ],
  },
  {
    s: "2.4.32", t: "2026-08-07",
    d: [
      "Bağlantı Yöneticisi ile DRONLAR paneli tek panelde birleştirildi: bağlantılar üst düzey satırlar, dronlar bağlı oldukları bağlantının altında girintili olarak listeleniyor; bir dronun hangi bağlantıdan geldiği artık pencereler arasında karşılaştırma yapmadan görülüyor",
      "Bağlantı satırının başlığına basıldığında o bağlantıya ait dron grubu katlanıp açılıyor; katlanma durumu tarayıcıda saklandığı için sayfa yenilendiğinde korunuyor",
      "Bağlantı Yöneticisi penceresinin başlığında aktif bağlantı sayısı gösteriliyor; pencere katlandığında veya arka planda kaldığında kaç bağlantının ayakta olduğu başlıktan okunuyor",
      "Dron başlığına irtifa ve uçuş kipi özeti eklendi: kart kapalıyken de dronun kaç metrede olduğu ve hangi kipte uçtuğu görünüyor",
      "Telemetri yayınına bağlantı kimliği alanı eklendi: arayüz dronu doğru bağlantı grubuna yerleştirmek için artık tahmin yürütmüyor, sunucudan gelen kesin kimliği kullanıyor",
      "İşlemler penceresi Kameralar ve diğer standart pencerelerle aynı başlık altyapısına alındı: başlık pencere kenarına yapışan tam genişlikte bir bant oldu ve başlığa ikon eklendi",
      "Aynı başlık standardı işlemler dışındaki 13 küçük pencereye de uygulandı (Telemetri, GPS, Batarya, Mod Seç, Takip Et, ARM CHECK, Failsafe, Kalibrasyon, History, Program Ayarları ve diğerleri); her biri kendi konusunu anlatan bir ikon taşıyor",
      "Hava Durumu widget'ına harita konumu değiştiğinde beliren kırmızı yenileme düğmesi eklendi: her harita hareketinde otomatik sorgu yapmak yerine veri bayat sayılıp kullanıcı isteğine bırakıldı, böylece gereksiz ağ yükü oluşmuyor",
      "Yeni Konum widget'ı: haritanın merkezindeki adresi il, ilçe ve mahalle düzeyinde yazıyor; kapsam, yakınlaştırma veya konum değiştiğinde yanında kırmızı yenileme düğmesi beliriyor",
      "Yeni Pusula widget'ı: haritanın üç boyutlu yönelimini canlı izliyor, kamera başlığı ve eğim açısı gösteriliyor; kadrana basıldığında harita kuzeye döndürülüyor",
      "Yeni Pilotlar widget'ı: aynı firmadaki pilotlar çevrimiçi ve çevrimdışı durumlarıyla listeleniyor, bir pilota basıldığında onunla sohbet penceresi açılıyor",
      "Firma içi canlı mesajlaşma sistemi eklendi: mesajlar veritabanında saklanıyor, karşı taraf çevrimiçiyse anında iletiliyor, çevrimdışıysa ilk girişinde okunmamış olarak gösteriliyor",
      "Üst çubuğa mesaj ikonu eklendi: okunmamış mesaj varsa ikon kırmızıya dönüp sayıyı gösteriyor, basıldığında okunmamış mesajların listesi açılıyor ve mesaja basıldığında gönderenle sohbet penceresi açılıyor",
      "İkinci ekranda kullanılmak üzere çoklu dron uçuş duvarı sayfası eklendi (/flight): altı panel, tekli ile altılı arasında altı yerleşim seçeneği, her panelde çevrimiçi dron seçimi ve uçak kokpiti tarzı birincil uçuş göstergesi",
      "Uçuş göstergesi yapay ufuk, hız ve irtifa şeritleri, dikey hız çubuğu, dönen pusula gülü, uçuş kipi bandı ile batarya ve uydu göstergelerini tek çerçevede canlı olarak çiziyor",
    ],
  },
  {
    s: "2.4.31", t: "2026-08-07",
    d: [
      "Üç boyutlu dron ve hedef ikonlarına geçildikten sonra yaşanan ağır yavaşlama giderildi: v2.4.30'da her ikon için ayrı bir çizim birimi oluşturuluyordu ve bunlar toplu işlenemediği için ikon başına ayrı bir çizim çağrısı üretiliyordu; geometri derlemesi de ana iş parçacığında yapılıyor, her telemetri paketinde dönüşüm matrisi çarpımı yenileniyordu",
      "İkonların biçimi korunarak gösterim yöntemi değiştirildi: dört dilim ve iki katmana ayrılmış bir elipsoid geometrik olarak kare tabanlı çift piramittir, yani istenen elmas biçiminin yaklaşımı değil birebir kendisidir; artık ayrı çizim birimi yerine haritada zaten var olan birimin bir özelliği olarak çiziliyor ve motorun kendi toplu işleme hattına giriyor",
      "İkon başına ayrı çizim çağrısı, eşzamanlı geometri derlemesi ve dönüşüm matrisi çarpımı tamamen kaldırıldı; konum ve renk güncellemeleri tek bir atamaya indi ve renk yalnızca gerçekten değiştiğinde yazılıyor",
      "Arazi yüksekliği kayma koruması güçlendi: zemin yüksekliği artık elle okunup konuma eklenmiyor, doğrudan motorun yükseklik referansı mekanizmasına bırakılıyor; böylece arazi kafesi çözünürlük değiştirdiğinde ikonlar bir sonraki telemetri paketini beklemeden tazeleniyor",
      "İkon silindiğinde ayrı çizim birimini kaldırma zorunluluğu ortadan kalktı: gösterim harita birimiyle birlikte gittiği için bellek sızıntısı riski yapısal olarak kaldırıldı",
      "İkonun dış hattı kaldırıldı: dış hat motor tarafında ayrı bir geometri olarak çizilip çizim çağrısı sayısını iki katına çıkarıyordu, yüzey gölgelendirmesi yüzleri zaten ayırt ettirdiği için görsel kayıp yok",
      "İkon ölçüleri, %80 opaklık ve renkler v2.4.30 ile aynı kaldı: dron için kalıcı dron rengi, hedef için tip rengi korunuyor; toplam boy 41 m olduğu için haritadaki görsel ölçek değişmedi",
      "Bağlantısı kopan dron ve süzülen hedeflerin soluşma yolunda renk kaybına yol açacak bir tutarsizlik giderildi: opaklık ayarı artık rengi doğru alandan okuyor, aksi halde solukluğa geçen ikon beyaza dönecekti",
      "Saat widget'ı Hava Durumu widget'ı ile aynı boyuta getirildi (226x224); analog kadran 116 pikselden 176 piksele büyütüldü ve dijital gösterim yazı boyutları yeni alana oranlandı",
      "Widget'ların her temada beyaz görünmesi giderildi: koyu tema kuralları projede hiç kullanılmayan bir gövde sınıfına yazılmıştı, oysa arayüzün tema sözleşmesi koyuyu varsayılan kabul edip açık temayı kök niteliğiyle belirtir; kurallar bu sözleşmeye taşındı",
      "Widget renkleri tek bir değişken setine bağlandı: gövde, başlık, metin, vurgu ve kadran renkleri tema değişkenlerinden türetiliyor, sabit renk yazılmıyor",
      "Saat kadranı ve rüzgar gülü çizimlerindeki sabit renkler kaldırıldı: kadran zemini, çizgiler, sayılar, ibreler ve akış izleri artık temadan geliyor; koyu temada okunamayan öğeler düzeldi",
    ],
  },
  {
    s: "2.4.30", t: "2026-08-07",
    d: [
      "Dronların DRONLAR paneline hiç düşmemesi giderildi: v2.4.29'da radar/GCS ikonu üç boyutlu prizmaya çevrilirken ikon rengini tazeleyen fonksiyon güncellenmemiş, prizma kipinde bulunmayan iki boyutlu ikon nesnesine yazmayı sürdürmüştü; her telemetri paketinde tip hatası atılıyordu",
      "Hatanın dron paneline yansıma yolu bulundu: tüm telemetri alt sistemleri tek bir mesaj işleyici gövdesinde zincirleme çağrılıyordu, radar ikonunda atılan hata gövdenin geri kalanını sessizce düşürüyor ve aynı paketteki dron döngüsüne hiç ulaşılamıyordu; sunucu tarafı tamamen sağlamdı",
      "Telemetri işleme yeniden yapılandırıldı: her alt sistem (bağlantı durumları, radar paneli, radar hedefleri, yörünge izleri, grafik, kayıt, oynatma, konsol, dronlar, görev, takip, angajman, sürü) kendi hata kabuğunda çalışır; bir alt sistemin arızası diğerlerini artık etkilemez",
      "Her dron ayrıca yalıtıldı: tek bir dronun bozuk telemetri verisi diğer dronları panelden düşürmez",
      "Hatalar bastırılmıyor: arızalanan alt sistemin adı ve hata iletisi konsola bir kez yazılır, aynı hata tekrar bildirilmeyerek konsol kirliliği önlenir",
      "Dron ve hedef ikonları çift piramit (bipiramit) elmas biçimine geçirildi: alt ve üst uçları tepe noktasında birleşen, ortada en geniş kesite sahip dikey elmas; ikonların kendi renkleri (dron için kalıcı dron rengi, hedef için tip rengi) korunur",
      "Bipiramit ekstrüde çokgenle üretilemediği için (ekstrüzyon taban kesitini yükseklik boyunca sabit tutar, tepe noktasına daralamaz) ikon gerçek üçgen yüzeylerden oluşan ayrı bir çizim birimi olarak kuruldu; yüzey normalleri hesaplandığı için yüzler farklı parlaklıkta görünür ve üç boyutlu algı oluşur",
      "Bipiramitin orta kuşağındaki köşelerden biri hareket yönüne bakar; ikon dünya uzayında döndüğü için kamera açısından bağımsızdır ve yön bilgisi harita çevrilirken bozulmaz",
      "Radar/GCS prizması kısaltıldı: dikey kalınlık 22 m'den 8 m'ye, yatay ölçek 48 m'den 30 m'ye indirildi (%64 kısalma); ölçüler tek bir yerden yönetiliyor",
      "Bağlantısı kopan dron ve süzülen hedeflerin ikonları taban opaklık üzerinden soluklaştırılıyor; ikon silindiğinde ayrı çizim birimi de kaldırılarak bellek sızıntısı önlendi (hedefler dört ayrı noktada silindiği için temizlik tek bir yardımcıya toplandı)",
      "Tema değişiminde radar ikonunun rengini tazeleyen yol da iki kipi birlikte ele alacak biçimde düzeltildi",
    ],
  },
  {
    s: "2.4.29", t: "2026-08-07",
    d: [
      "Arazi yüksekliği (terrain) açıkken radar, dron ve hedef ikonlarının harita döndürülürken zemine göre kayması giderildi: ikonlar sabit bir yükseklikle (100 m) çiziliyor, yükseklik referansı hiç ayarlanmamıştı; terrain açıldığında zemin 962 m'ye çıkıyor, ikon 100 m'de kaldığı için kamera her döndüğünde paralaks kayması oluşuyordu",
      "İkonlar artık zemin referanslı çiziliyor: yer birimleri araziye kenetleniyor (CLAMP_TO_GROUND), uçan birimler zemine göre konumlanıyor (RELATIVE_TO_GROUND); ölçümde her iki yol için yükseklik referansı doğrulandı",
      "İkonlar iki boyutlu işaretçi yerine gerçek üç boyutlu prizma olarak çiziliyor: dört köşeli ok biçimi yön bilgisini gösterir, 16 m kalınlığında dışa çekme (extrusion) uygulanır ve %80 opaklıkla (alfa 0.8) çizilir; böylece altındaki arazi kısmen görünür kalır",
      "Prizma ikonlar Harita Ayarları içinden açılıp kapatılabilir; kapatıldığında önceki iki boyutlu gösterime dönülür",
      "Zemine uzanan kesikli dikey çizginin alt ucu artık araziye oturuyor; önceden deniz seviyesinde kalıyordu",
      "Widget sistemi eklendi: Yardım menüsü altında ayrı bir Widget bölümü, standart menü davranışıyla (tıklayınca açılır ve yanında tik görünür, yeniden tıklayınca gizlenir) çalışır",
      "Widget'lar taşınabilir ancak boyutları değiştirilemez; başlıkta yalnızca widget adı, kapatma düğmesi ve grup halindeyken mıknatısı boz düğmesi bulunur",
      "Mıknatıs etkisi: birbirine 18 piksel yaklaşan widget'lar kenarlarından yapışır, kenar hizalaması yapılır ve tek grup olarak birlikte hareket eder; grubun herhangi bir üyesinden tutulduğunda tüm grup aralarındaki dizilim korunarak taşınır",
      "Saat widget'ı: güncel saati gösterir, dijital ve analog kadran arasında geçiş yapılabilir, seçilen kip oturumlar arasında korunur",
      "Hava Durumu widget'ı: haritanın merkezindeki konumun hava durumunu animasyonlu olarak gösterir; rüzgar hızı hem knot hem km/h olarak, rüzgar yönü hem derece hem 16 yön kısaltmasıyla verilir, Beaufort ölçeği ve hamle hızı ayrıca listelenir",
      "Hava durumu görselleri animasyonlu: dönen rüzgar gülü ibresi, akış çizgileri, pervane ve gökyüzü durumuna göre değişen güneş/bulut çizimi",
      "Widget katmanı fare olaylarını geçirdiği için harita etkileşimini ve pencere yönetimini engellemez; widget durumları ve konumları kalıcı olarak saklanır (kapsayıcı kimliği yerine sabit widget adları kullanılarak, v2.4.28'de görülen oturumlar arası kimlik çakışması tekrarlanmaz)",
    ],
  },
  {
    s: "2.4.28", t: "2026-08-04",
    d: [
      "Birleşmiş pencerenin boyutlandırılamaması giderildi: kapsayıcı içindeki panele tıklandığında pencere yönetimi panele artan bir yığın sırası (z-index 1213) yazıyor, kapsayıcının sağ-alt boyutlandırma tutamacı ise sabit bir değer (5) taşıdığı için panelin altında kalıyordu; fare tutamaç yerine panel içeriğini yakalıyordu",
      "Kök neden: kapsayıcı gövdesi ve gözenekleri yığın bağlamı oluşturmuyordu, bu yüzden içerideki panelin yığın sırası kapsayıcının tutamacıyla doğrudan karşılaştırılıyordu. Gövde ve gözeneklere sayısal yığın sırası verilerek panel kendi bağlamına kapatıldı; tutamaç yükseltildi",
      "Kapsayıcı içindeki panele tıklandığında artık panel değil kapsayıcı öne getiriliyor; panelin yığın sırası kapsayıcı içinde sabit kalıyor, panel serbest kaldığında yeniden yükselebiliyor",
      "Pasif sekmenin seçilememesi giderildi: sekme etiketine tıklandığında içerik boş geliyordu; artık üç tur ileri-geri geçişin tamamı çalışıyor ve seçilen sekmenin içeriği tam boyutta görünüyor",
      "Birleşmiş pencerenin ekran boyutunda açılması giderildi: kapsayıcı kimlikleri (dokKap_1 gibi) oturuma özel bir sayaçtan üretilmesine karşın kalıcı depo anahtarı olarak kullanılıyordu; yeni oturumun ilk kapsayıcısı, önceki oturumda tamamen farklı panellerden oluşmuş kapsayıcının boyutunu ve konumunu miras alıyordu",
      "Kapsayıcılar geçici nesneler olduğu için kalıcı boyut ve konum hatırlaması kaldırıldı; taşıma ve boyutlandırma çalışmaya devam ediyor. Panel kimliğine dayalı kayıtlar korundu",
      "Önceki sürümlerin kalıcı depoda bıraktığı kapsayıcı artıkları açılışta temizleniyor; aksi halde mevcut kurulumlarda hatalı boyut sürmeye devam ediyordu",
      "Bölünmüş pencere çözülürken panellerin belgeden kopması giderildi: çözme işlevi yalnızca sekmeli kapsayıcıyı ele alıyor, bölme üyelerini serbest bırakmadan kapsayıcıyı kaldırıyordu; artık bölme kapsayıcısında iş doğru işleve devrediliyor",
    ],
  },
  {
    s: "2.4.27", t: "2026-08-04",
    d: [
      "Panellerin çoğalması, içi boş pencere açılması ve sekmelerin sahipsiz kalması giderildi: bir panel bir kapsayıcıdan diğerine taşındığında eski kapsayıcının üye listesi ve sekme etiketi temizlenmiyordu; panel iki kapsayıcıya ait sayıldığı için sekme geçişi ile bölme çözümü birbirine karışıyordu",
      "Kök neden: sekme ekleme işlevi yalnızca sekmeli kapsayıcı yolunu ele alıyor, bölünmüş pencere yolunu hiç ele almıyordu; bölme oluşturma işlevi ise iki yolu da ele almıyordu. Artık her iki yol tek bir 'önceki kapsayıcıdan ayır' girişinden geçiyor",
      "Sahipsiz sekme etiketleri temizleniyor: etiket silme artık yalnızca kayıtlı referansa güvenmiyor, sekme çubuğunu tarayarak paneli olmayan etiketleri kaldırıyor",
      "Bölünmüş pencerede üç başlık satırı görünmesi giderildi: bölmeye giren panellerin kendi başlıkları gizleniyor ve kapsayıcı başlığında 'BOLUNMUS PENCERE' yerine panel adları gösteriliyor (örneğin 'DRONLAR | ROTALAR')",
      "Havada duran boyutlandırma tutamaçları giderildi: kapsayıcı içindeki panellerin kendi tutamaçları gizleniyor, panel ayrıldığında geri getiriliyor; bölünmüş pencerede görünür tutamaç sayısı üçten bire indi",
      "Bölmede tek üye kaldığında bölme kendiliğinden çözülüyor ve panel serbest pencereye dönüyor; daha önce boş gözenek ve kilitli panel kalıyordu",
      "Bölünmüş pencereye panel bırakma artık kabul ediliyor: sürüklenen panel bir gözeneğin üst kısmına bırakılırsa o gözenek sekmeli alt kapsayıcıya dönüşür, kenarına bırakılırsa iç içe bölme oluşur. Daha önce bu işlem sessizce reddediliyordu",
      "Veritabanı göçü çakışmaya dayanıklı hale getirildi: ikili veri olarak saklanan iki değer metne çevrildiğinde aynı değere dönüşüp benzersizlik kısıtını ihlal edebiliyor, bu durumda satır dönüştürülemeyip ikili kalıyordu; artık yinelenen kayıt tespit edilip temizleniyor",
      "Rol listesi komutunun her çağrıda çökmesi giderildi: rol adları ikili veri olarak okunduğunda sözlük anahtarı olarak kullanılıyor ve arayüze gönderim başarısız oluyordu",
    ],
  },
  {
    s: "2.4.26", t: "2026-08-04",
    d: [
      "Arayüzün sunucuya bağlandığı anda kopması giderildi: v2.4.25 onarımı, veritabanındaki tüm metin kolonlarını ikili veri (BLOB) olarak yazıyordu; bunun üzerine sunucu ayarları arayüze gönderirken her bağlantıda çöküyor ve tarayıcı sonsuz yeniden bağlanma döngüsüne giriyordu",
      "Kök neden: onarım işlevi, bozuk metinleri kaybetmemek için hedef veritabanı bağlantısında da bayt kipini açıyordu. Bayt kipinin yalnızca okuma yönünü etkilediği varsayılmıştı; oysa okunan bayt değerler hedefe yazılırken ikili veriye dönüşüyordu. Hedefte bayt kipi kaldırıldı ve aktarım sırasında her değer, kolonun bildirilen tipine göre metne çevriliyor",
      "Gerçek BLOB kolonları (örneğin kullanıcı avatarı) korunuyor; yalnızca metin bildirilen kolonlar dönüştürülüyor",
      "Etkilenmiş veritabanlarını geri düzelten bir göç adımı eklendi: açılışta metin kolonlarındaki ikili değerler metne çevriliyor. Bu adım bütünlük denetiminden bağımsız çalışır, çünkü dosya sağlam olduğu halde veri hasarlı olabiliyordu",
      "Girişin bozulması giderildi: kullanıcı e-postası ikili veri olarak saklandığı için e-posta karşılaştırması hiçbir zaman eşleşmiyor ve şifre doğru olsa bile giriş yapılamıyordu",
      "Ayar okuma yolunda ikinci bir savunma katmanı eklendi: göç herhangi bir nedenle çalışmazsa (salt okunur dosya, izin hatası) uygulama yine de çalışmaya devam eder",
    ],
  },
  {
    s: "2.4.25", t: "2026-08-04",
    d: [
      "Pencerelerin birbirine sekme olarak eklenememesi giderildi: bırakma hedefini bulan işlev, iki pencere de serbestken kapsayıcı karşılaştırmasının boş değerlerle eşleşmesi yüzünden her geçerli hedefi reddediyordu; artık yalnızca gerçek bir kapsayıcı varken karşılaştırma yapılıyor",
      "Sekme etiketine tıklayınca sekme değişmemesi giderildi: sürükleme için işaretçi yakalaması tıklama anında alındığı için tarayıcı tıklama olayı üretmiyordu; yakalama artık yalnızca 26 piksel eşiği aşıldığında alınıyor, kısa tıklamalar sekme geçişi yapıyor",
      "Aynı pencerenin iki kez sekme olarak eklenip başlıkta çift görünmesi (\"DRONLAR | DRONLAR\") engellendi: hem sekme ekleme işlevine tekrar denetimi konuldu hem de sürüklenen pencerenin kendi kapsayıcısı bırakma hedefi olarak atlanıyor; sahipsiz kalan eski sekme etiketleri temizleniyor",
      "Alt alta gelen panellerde boyutlandırmanın yalnızca alttaki paneli etkilemesi giderildi: bölüm tutamacı kurulum anında sabit iki elemana kilitliydi ve bölümlerin ayrı pencerelere taşınmış olduğunu bilmiyordu; artık boyutlandırılacak çift sürükleme anında, tutamaçla aynı gövdede yaşayan görünür bölümler arasından seçiliyor",
      "Hiçbir paneli ayırmayan bölüm tutamaçları gizleniyor: üç tutamaçtan ikisi ekranda aynı noktada üst üste binmiş durumda görünüyor ve sürüklendiğinde ya etkisiz kalıyor ya da yanlış paneli boyutlandırıyordu",
      "Pencere görünürlük ölçümü düzeltildi: bölüm pencereleri sabit konumlu olduğu için eski konum zinciri denetimi, pencere kapalıyken bile içeriği görünür sayıyordu; artık gerçek çizim denetimi kullanılıyor",
      "Yüzen paneller (radar ayarları, sınıflandırma, kayıt, filtre, iz, seri bağlantı, program hakkında) pencere yönetimine dahil edildi: bu pencerelerin sürükleme mekanizması ayrı bir modülde olduğu için sekme birleştirme ve bölme sistemine hiç girmiyordu",
      "Başlık çubuğu tanımı tek kaynağa bağlandı: taşıma modülü dört, dok modülü on başlık sınıfı tanıyordu; tanınmayan başlıklardan pencere sürüklenemiyordu. Yanlışlıkla listeye girmiş dört panel içi öğe (dron kart başlığı, rol grubu başlığı, geliştirici ekip başlığı) çıkarıldı",
      "Yüzen panel başlıkları 51 pikselden 30 piksele inerek diğer pencerelerle eşitlendi; bu başlıklar ortak başlık kuralının dışında kalmıştı",
      "Veritabanı bozulmasına karşı otomatik onarım eklendi: açılışta bütünlük denetimi yapılıyor, telemetri tablosu bozulmuşsa diğer 26 tablonun verisi korunarak yeniden inşa ediliyor ve yazma hatası anında onarım tetikleniyor",
      "Otomatik onarımın hiç tetiklenmemesi giderildi: bozulma tanıma listesinde, kullanıcının sahada aldığı asıl hata metni olan disk giriş/çıkış hatası (disk I/O error) eksikti; bu yüzden onarım işlevi ilk satırda çıkıp hiçbir şey yapmıyordu. Bozulma tanıma listesine dört hata metni daha eklendi",
      "Bozuk tablo artık düşürülmeye çalışılmıyor: bozuk bir tabloyu düşürmek için veritabanının bozuk sayfalarını dolaşmak gerektiği için bu yöntem gerçek bozuk dosyada başarısız olup görünümleri de siliyordu; onarım artık yeni dosyaya kopyalama ve atomik yer değiştirme ile yapılıyor, başarısızlık halinde kaynak dosyaya dokunulmuyor",
      "Kapatma sırasında oluşan çökme giderildi: bağlantı havuzu kapatılırken diğer iş parçacıklarının kullandığı bağlantılara dokunulmuyor",
    ],
  },
  {
    s: "2.4.24", t: "2026-08-04",
    d: [
      "Dron uçuşlarında telemetri kaydı sırasında alınan disk yazma hatası (SQLite disk I/O error) giderildi: veritabanı bağlantıları artık her istekte yeniden açılmıyor, iş parçacığı başına kalıcı havuzdan veriliyor — 200 çağrıda 401 olan tanıtıcı sızıntısı 3'e düştü",
      "Telemetri için dakikalık dosya tamponu eklendi: dron uçarken ham telemetri önce diskteki JSONL dosyalarına yazılıyor, her dakika kapanıp veritabanına aktarılıyor; aktarım başarısız olursa dosya silinmiyor ve 5 denemeden sonra karantinaya alınıyor",
      "Telemetride dört veri kaybı noktası kapatıldı: yazım öncesi tamponun boşaltılması, dron kimliği henüz çözülmemiş örneklerin atılması, NOT NULL alanlarda boş değer ve toplu yazımın tek işlemde çökmesi — artık tek bozuk satır 60 örneği düşürmüyor",
      "SQLite dayanıklılık ayarları güçlendirildi: meşgul bekleme süresi 30 saniyeye çıkarıldı, WAL kipinde güvenli senkron seviyesi ve otomatik denetim noktası aralığı tanımlandı, ölü bağlantı denetimi eklendi",
      "Tüm pencereler tek tasarıma indirildi: 13 pencerede kullanılan 7 ayrı başlık kuralı (beş farklı iç boşluk, iki font kalınlığı, üç harf aralığı, iki font boyutu) tek kurala birleştirildi; ölçüler CSS değişkenlerinden yönetiliyor",
      "Önizleme ve video penceresi başlıkları artık sürüklenebiliyor: bu iki başlıkta sürükleme tutamağı tanımı eksikti",
      "Üst menü çubuğu 42 pikselden 32 piksele inceltildi; logo ve iç öğeler yeni yüksekliğe uyarlandı",
      "Pencere üst sınırı tek kaynaktan yönetiliyor: üst çubuk yüksekliği üç ayrı yerde sabit sayı olarak tutuluyordu (CSS'te 42, iki JS dosyasında 48); artık canlı ölçümden okunuyor",
      "Chrome tarzı sekme birleştirme eklendi: bir pencere diğerinin başlık bölgesine sürüklendiğinde iki pencere tek kapsayıcıda sekmeli olarak birleşiyor",
      "Sekme ayırma eklendi: sekme etiketi dışarı sürüklendiğinde pencere yeniden bağımsız hale geliyor ve imleçle taşınmaya devam ediyor",
      "Pencere bölme eklendi: bir pencere diğerinin ortasına veya kenarına bırakıldığında tek pencere ikiye bölünüyor; ortadaki ayırıcı sürüklenerek oranlar değiştirilebiliyor",
      "Sürükleme sırasında bırakma hedefi görsel olarak gösteriliyor (sekme ve sol/sağ/üst/alt bölme önizlemesi)",
      "Pencereler sekme veya bölme haline gelirken klonlanmıyor: içerideki canlı harita, video akışı ve bağlantı dinleyicileri korunuyor",
      "Python paketi sürüm numarası (önceden 2.0.0 olarak sabitlenmişti) web arayüzü sürümüyle tek kaynaktan eşitlendi",
    ],
  },
  {
    s: "2.4.23", t: "2026-08-01",
    d: [
      "Kay\u0131tl\u0131 rotalara \"Parametreleri De\u011fi\u015ftir\" d\u00fc\u011fmesi eklendi: rota detay penceresinden a\u00e7\u0131lan yeni pencerede noktalar\u0131 yeniden \u00e7izmeye gerek kalmadan irtifa, h\u0131z ve y\u00f6nelim a\u00e7\u0131s\u0131 de\u011fi\u015ftirilebiliyor \u2014 t\u00fcm rota tiplerinde (serbest form, spiral, elle \u00e7izilen, d\u0131\u015far\u0131dan y\u00fcklenen) \u00e7al\u0131\u015f\u0131r",
      "Parametre penceresinde iki d\u00fczenleme kipi bulunuyor: t\u00fcm noktalara topluca uygulama (se\u00e7ilen alanlar) ve nokta baz\u0131nda tek tek d\u00fczenleme tablosu; de\u011fi\u015fiklikler kaydedilmeden \u00f6nce haritada canl\u0131 \u00f6nizlenir",
      "Y\u00f6nelim a\u00e7\u0131s\u0131 (yaw) art\u0131k rota noktas\u0131 baz\u0131nda tan\u0131mlanabiliyor: bo\u015f b\u0131rak\u0131l\u0131rsa ara\u00e7 rota y\u00f6n\u00fcne bakar, 0-359 aras\u0131 sabit a\u00e7\u0131 verilirse g\u00f6reve MAV_CMD_CONDITION_YAW komutu eklenir",
      "Serbest form (alan tarama) rotalar\u0131nda aral\u0131k mesafesi ve u\u00e7u\u015f y\u00f6n\u00fc a\u00e7\u0131s\u0131 de\u011fi\u015ftirildi\u011finde zigzag tarama deseni ayn\u0131 alan k\u00f6\u015feleri i\u00e7in otomatik yeniden \u00fcretiliyor",
      "Haritada rotaya \u00e7ift t\u0131klama davran\u0131\u015f\u0131 geni\u015fletildi: serbest form g\u00f6revleri \u00e7izim penceresinde, di\u011fer t\u00fcm rotalar parametre d\u00fczenleme penceresinde a\u00e7\u0131l\u0131yor",
      "Log Y\u00f6netimi penceresinin bozuk d\u00fczeni d\u00fczeltildi: \u00fcstteki bo\u015f alan kald\u0131r\u0131ld\u0131, sabit tablo ba\u015fl\u0131\u011f\u0131 eklendi ve \"\u0130ndir\" d\u00fc\u011fmesi sat\u0131r y\u00fcksekli\u011fini ta\u015f\u0131rmayacak \u015fekilde hizaland\u0131 (\u00e7ak\u0131\u015fan eski stil kurallar\u0131 temizlendi)",
      "Log listesinde her kayd\u0131n tarihi g\u00f6steriliyor; LOG numaras\u0131, tarih ve boyut ba\u015fl\u0131klar\u0131na t\u0131klanarak artan/azalan s\u0131ralama yap\u0131labiliyor (GPS kilidi olmadan yaz\u0131lan loglarda tarih yerine \u2014 g\u00f6r\u00fcn\u00fcr)",
      "Log indirme i\u015flemi durdurulabiliyor: indirme s\u0131ras\u0131nda hem durum sat\u0131r\u0131nda hem ilgili log sat\u0131r\u0131nda \"Durdur\" d\u00fc\u011fmesi \u00e7\u0131kar; iptal edilen indirmede yar\u0131m dosya kaydedilmez ve pencere kapat\u0131l\u0131rsa indirme otomatik iptal edilir",
      "Dron kart\u0131ndaki durum d\u00fc\u011fmesi sadele\u015ftirildi: yaln\u0131z u\u00e7u\u015fa hazirlik durumu yaz\u0131yor, hata/uyar\u0131 sayac\u0131 kald\u0131r\u0131ld\u0131 (say\u0131lar ipucu metninde ve Arm Check panelinde)",
      "Durum d\u00fc\u011fmesi %50 geni\u015fli\u011fe indirildi ve yan\u0131na %50 geni\u015flikte \"\u0130\u015eLEMLER\" d\u00fc\u011fmesi eklendi; bu d\u00fc\u011fme t\u00fcm dron komutlar\u0131n\u0131 3 s\u00fctunlu b\u00fcy\u00fck d\u00fc\u011fmeler halinde g\u00f6steren yeni bir pencere a\u00e7\u0131yor",
      "Kart ba\u015fl\u0131\u011f\u0131ndaki \u00fc\u00e7 nokta men\u00fcs\u00fc kald\u0131r\u0131ld\u0131; haritada drona sol t\u0131klama da ayn\u0131 \u0130\u015eLEMLER penceresini a\u00e7\u0131yor \u2014 t\u00fcm dron i\u015flemleri tek aray\u00fczde topland\u0131",
    ],
  },
  {
    s: "2.4.22", t: "2026-08-01",
    d: [
      "Daha önce uçurulan dronun geçmişini, ismini ve rengini kaybederek yeni bir araç gibi görünmesi sorunu giderildi: v2.4.21'de donanım UID'si geç geldiğinde aynı araç için ikinci bir türetilmiş kimlik kaydı açılıyordu",
      "Kimlik yükseltme mekanizması eklendi: bağlantı sırasında geçici parmak izi ile kayıt açılmışsa, gerçek UID geldiğinde aynı veritabanı satırı yerinde yükseltilir; hedef UID'ye ait eski kayıt zaten varsa oturumlar, parametreler, parametre geçmişi ve telemetri eski kayda taşınıp geçici kayıt silinir",
      "Birleştirmede en eski kayıt tarihi, ilk kaydeden pilot, dron ismi ve rengi korunur; parametre çakışmaları en güncel değer kazanacak şekilde çözülür",
      "UID bekleme süresi 6 saniyeden 20 saniyeye çıkarıldı ve AUTOPILOT_VERSION isteği yanıt gelene kadar yaklaşık 3 saniye aralıkla 5 kez tekrarlanıyor (MAV_CMD_REQUEST_MESSAGE ve eski istek yöntemi birlikte denenir) — yavaş telemetri bağlantılarında kimlik artık kaçırılmıyor",
      "Tek seferlik onarım göçü: mevcut veritabanındaki mükerrer dron kayıtları (aynı SYSID ve otopilot için gerçek UID + türetilmiş kimlik çifti) otomatik birleştirilir; eşleşme belirsizse hiçbir kayda dokunulmaz",
    ],
  },
  {
    s: "2.4.21", t: "2026-08-01",
    d: [
      "Dronlar artık bağlandıkları anda benzersiz kimlikle veritabanına kaydediliyor: donanım UID'si (AUTOPILOT_VERSION), DJI seri numarası veya UID hiç gelmezse otopilot/araç tipi/firmware bilgilerinden türetilen kalıcı parmak izi kullanılır; aynı dron ikinci kez kayıt açmaz",
      "Her dron kaydında ilk kayıt tarihi ve kaydeden pilot (e-posta + ad soyad) zorunlu olarak tutulur; Dron Geçmişi panelinde kimlik kartı olarak UID, UID kaynağı, kayıt tarihi, kaydeden, SYSID, araç sınıfı, otopilot ve firmware gösterilir",
      "Parametreler drona bağlı ayrı tabloda kalıcı saklanıyor: sonraki bağlantılarda yeni parametreler eklenir, var olanların değerleri güncellenir — her dronun parametre kümesi kendi kimliğine bağlı tutulur",
      "Parametre değişiklik geçmişi eklendi: her değişiklikte eski değer, yeni değer, tarih-saat, değiştiren kullanıcı ve kaynak (GCS yazımı / drondan okuma) kaydedilir; GCS'teki tüm parametre yazma yolları (parametre penceresi, kısayol komutları, failsafe/kalibrasyon ayarları) bu denetim kaydına bağlandı",
      "Telemetri kaydı artık kalkış/iniş tetiklerine değil bağlantıya dayanıyor: dron bağlı olduğu sürece tüm telemetri (konum, irtifa, hız, dikey hız, yaw, mod, ARM, batarya, uydu, HDOP) tarih-saat ve pilot bilgisiyle kesintisiz kaydedilir",
      "Uçuşlar akıllı veritabanı görünümleriyle telemetriden otomatik tespit ediliyor: ARM + irtifa/hız ölçütleri ve zaman boşluğu analiziyle (gaps-and-islands) uçuş segmentleri çıkarılır; uçuş süresi, nokta sayısı, azami irtifa ve hız değerleri görünümden gelir",
      "Dron Geçmişi (geçmişi izle) sistemi yeni veri modeline taşındı: uçuş listesi, iz oynatma, uçuş silme ve tümünü silme işlemleri telemetri tablosu üzerinden çalışır; uçuş satırlarında o uçuşu uçuran pilotlar listelenir",
      "Veritabanı şeması yeniden yapılandırıldı: tüm yeni tablolar AUTOINCREMENT tamsayı birincil anahtar kullanır ve dronlar / oturumlar / parametreler / parametre geçmişi / telemetri arasında ON DELETE CASCADE foreign key ilişkileriyle bağlanır",
      "Bağlantı oturumları ayrı tabloda tutulur: her bağlantının başlangıç-bitiş zamanı ve oturum boyunca bağlı pilotlar kaydedilir; program beklenmedik kapanırsa açık oturumlar bir sonraki açılışta kapatılır",
      "Eski uçuş kayıt sistemi (ucuslar / ucus_dronlari / param_cache) kaldırıldı; açılışta tek seferlik göç ile dron kimlikleri ve parametreler yeni tablolara taşınıp eski veri silinir",
      "Telemetri saklama süresi ayarlanabilir (varsayılan 30 gün); süresi geçen kayıtlar günlük olarak otomatik temizlenir",
      "Haritada tüm rota tasarım ve gösterimlerinde noktalar arası mesafe gösteriliyor: her bacağın ortasında yatay ve irtifa farkını birlikte hesaplayan 3 boyutlu mesafe etiketi çizilir — hem kayıtlı hem düzenlenmekte olan rotada",
      "Sabit kanatlı araçlar için dönüş dairesi çizimi: ara noktalarda uçağın parametrelerinden hesaplanan minimum dönüş yarıçapı (R = V² / g·tanφ; ROLL_LIMIT_DEG ve AIRSPEED_CRUISE, eski adlar da desteklenir) kesikli daire ve yarıçap etiketiyle gösterilir; son noktada WP_LOITER_RAD loiter dairesi çizilir",
      "Rota çizimi için gereken uçuş parametreleri önce kalıcı parametre tablosundan okunur (drona ek istek gitmez), eksik olanlar hedefli PARAM_REQUEST_READ ile tek tek istenir",
    ],
  },
  {
    s: "2.4.20", t: "2026-07-31",
    d: [
      "“Rotaya Gönder” düğmesi “ROTAYI YÜKLE” olarak değiştirildi ve işlevi yalnızca yükleme ile sınırlandı: seçilen rota drona yüklenir, dron ARM EDİLMEZ ve uçuş BAŞLAMAZ",
      "Görev izleme penceresine ayrı “ROTAYI BAŞLAT” düğmesi eklendi: yalnızca görev drona yüklüyken aktif olur ve basıldığında dron ARM edilip AUTO moduna alınarak rota uçuşu başlar",
      "Yükleme sırasında canlı ilerleme çubuğu: yüzde, yüklenen/toplam görev ögesi sayısı ve durum metni gösterilir; yükleme tamamlandığında çubuk yeşile döner ve “GÖREV DRONA YÜKLENDİ” yazısı çıkar",
      "Yeni YÜKLENDİ durum rozeti eklendi: görev drona yüklü ancak henüz başlatılmamış durumu ayırt edilir; aynı rota tekrar yüklenebilir",
      "GÖREV İPTAL düğmesi yüklü-fakat-başlatılmamış görevlerde de aktif: uçuşa başlamadan drona yüklenmiş görev listesi temizlenebilir",
      "Sunucu tarafında yükleme ve başlatma ayrı komutlara bölündü (gorev_yukle / gorev_baslat); yükleme ilerlemesi telemetriyle canlı yayınlanır ve her komutun sonucu ayrı bildirilir",
      "Onay diyalogları ayrıştırıldı (TR/EN): yükleme onayı uçuşun başlamayacağını, başlatma onayı ARM ve kalkış irtifasını açıkça bildirir",
    ],
  },
  {
    s: "2.4.19", t: "2026-07-31",
    d: [
      "Dron kartının en üstüne UÇUŞA HAZIR göstergesi eklendi: yeşil (hazır), sarı (hazır fakat uyarılı), kırmızı (hazır değil), mavi (ARM — uçuşta) ve gri (bağlantı yok / durum bekleniyor); kritik/uyarı sayısı rozette gösterilir",
      "Göstergeye tıklanınca ARM CHECK paneli açılır: Denetim sekmesinde sensör sağlığı (jiroskop, ivmeölçer, pusula, barometre, GPS, RC, AHRS, batarya, itki), EKF varyansları, GPS fix/uydu/HDOP, batarya gerilim-akım-yüzde, titreşim ve otopilotun kendi ön kontrol (prearm) sonucu maddeler halinde listelenir",
      "Mesajlar sekmesi: dronun bildirdiği tüm STATUSTEXT hata/uyarı mesajları (önem derecesine göre renkli, tekrar sayısı ve saat bilgisiyle) ayrı panelde gösterilir; MESAJLARI TEMİZLE ile sıfırlanabilir",
      "Parametreler sekmesi: kalkışı etkileyen parametreler (ARMING_*, GPS_*, EK3/AHRS, COMPASS_USE, BATT_*, FS_*, RTL_ALT) değerleri ve okunabilir anlamlarıyla listelenir; tıklanınca doğrudan düzenleme açılır",
      "ARM CHECK dron menüsüne de eklendi; panel açıkken 3 saniyede bir kendini tazeler",
      "Parametre düzenlemede Mission Planner tarzı seçim listesi: ArduPilot resmi metadata'sından 1711 parametrenin değer seçenekleri gömüldü (1533 seçim listesi + 304 bitmask tanımı) — sayısal değerler artık '3 — Auto' gibi gerçek anlamlarıyla açılır listede seçilir",
      "Bitmask parametreleri (ARMING_SKIPCHK, LOG_BITMASK, RC_OPTIONS...) her bit için onay kutusu olarak düzenlenir; toplam değer canlı hesaplanır, 'Ham sayısal değer gir' anahtarıyla klasik giriş de kullanılabilir",
      "Parametre listesinde her değerin altında anlamı gösterilir (örn. GPS_TYPE 2 → uBlox); araç tipine (kopter/sabit kanat) göre doğru seçenek kümesi kullanılır",
      "TAKEOFF/LAND düğmesi artık irtifaya değil ARM durumuna bakıyor: dron DISARM ise irtifa ne olursa olsun TAKEOFF, ARM ise LAND gösterilir",
      "Uçuş geçmişi (log) kaydı düzeltildi: sahipsiz (pilot bilgisi olmayan) uçuşlar artık Dron Geçmişi panelinde görünüyor — önceden bu kayıtlar yalnızca yöneticiye gösteriliyor ve panel boş kalıyordu",
      "Uçuş kaydı artık irtifa telemetrisine bağımlı değil: ARM durumu belirli süre sürerse kayıt yedek tetikle başlatılır ve irtifa yayınlamayan araçlarda uçuş yalnızca DISARM (veya bağlantı kopması) ile kapatılır",
      "Bir uçuş yeterli iz noktası toplanmadığı için kaydedilmediyse sebebi konsola yazılır (kaç nokta toplandığı ve konum telemetrisinin gelip gelmediği uyarısıyla)",
    ],
  },
  {
    s: "2.4.18", t: "2026-07-31",
    d: [
      "Angajmanda hız artık sorulmuyor: saldıran dron daima maksimum hızda gider. Üst sınır dronun MAVLink parametrelerinden okunur (WPNAV_SPEED / AIRSPEED_MAX / ARSPD_FBW_MAX); okunamazsa 300 km/h (83.3 m/s) uygulanır",
      "Yaklaşma yavaşlaması kaldırıldı: güdüm artık konum hedefi yerine hız vektörü (SET_POSITION_TARGET_GLOBAL_INT, yalnız hız maskesi) gönderir — hedefe/drona yaklaşırken veya hedef yavaşladığında hız kesilmez; DO_CHANGE_SPEED 2 sn'de bir tekrarlanır",
      "Angajman sonlanma koşulu daraltıldı: yalnızca hedef irtifası 3 m altına düştüğünde veya hedef çevrimdışı olduğunda (ya da operatör iptalinde) sona erer; yakalama mesafesine girmek angajmanı bitirmez, durum yalnızca 'temas' olarak işaretlenir",
      "Rota görevleri için GÖREV İPTAL düğmesi: görev izleme penceresinden tek tıkla iptal — dron BRAKE/LOITER ile bulunduğu yerde tutulur ve drona yüklü görev listesi temizlenir (MISSION_CLEAR_ALL), böylece AUTO'ya dönse bile eski göreve devam etmez",
      "Angajman onay diyalogu ve parametre paneli güncellendi: hız girişi yerine 'MAKSİMUM (TAM HIZ)' göstergesi (TR/EN)",
    ],
  },
  {
    s: "2.4.17", t: "2026-07-31",
    d: [
      "Parametreler penceresine belirgin 'TÜMÜNÜ AL' düğmesi eklendi: tüm parametre listesi drondan tek tıkla yeniden okunur (ilerleme çubuğuyla)",
      "Parametre önbelleği: drondan okunan tam set veritabanına dron (sysid) bazlı kaydedilir; pencere açılınca kayıtlı set anında gösterilir, her açılışta drondan yeniden okuma yapılmaz",
      "Özet satırında kaynak etiketi: 'kayıtlı: tarih saat' veya 'drondan okundu' bilgisi gösterilir",
      "Parametre değeri yazıldığında önbellekteki değer de güncellenir; dron bağlı değilken bile kayıtlı parametreler görüntülenebilir",
    ],
  },
  {
    s: "2.4.16", t: "2026-07-31",
    d: [
      "Parametre okuma sağlamlaştırıldı: ilk isteğe yanıt gelmezse liste otomatik yeniden istenir (3 deneme; 2. denemede broadcast komponent hedeflemesi) — bazı telsiz/köprü kurulumlarında okumanın hiç başlamaması sorunu giderildi",
      "Dron yanıt vermiyorsa (örn. tek yönlü telemetri) sonsuz 'okunuyor...' yerine açıklayıcı hata mesajı ve çözüm ipucu gösterilir; YENİLE ile tekrar denenebilir",
      "Parametre okuma sırasında oluşan sunucu hataları arayüze taşınır (popup artık sonsuz beklemez); hata konsola da yazılır",
    ],
  },
  {
    s: "2.4.15", t: "2026-07-31",
    d: [
      "Dron parametre ekranı yenilendi: pencere açılınca drondan TÜM parametreler otomatik okunur (PARAM_REQUEST_LIST + eksik kalanlar PARAM_REQUEST_READ ile tek tek tamamlanır; 60 sn'ye kadar sabırlı okuma)",
      "Okuma sırasında ilerleme çubuğu: alınan/toplam parametre sayısı ve yüzde canlı gösterilir",
      "Tree grid görünüm: parametreler önek gruplarına göre (ATC, WPNAV, BATT...) katlanabilir gruplar halinde; grup başlığında parametre sayısı",
      "Arama anında ve yerel: yazıldıkça filtreler, eşleşen gruplar otomatik açılır; YENİLE düğmesi tüm seti drondan yeniden okur",
      "Değer düzenlemede Min/Maks/Artış/Birim gösterimi (ArduPilot resmi parametre tanımlarından, 4800+ parametre); aralık dışı değerde kırmızı uyarı (bilinçli aşma serbest)",
    ],
  },
  {
    s: "2.4.14", t: "2026-07-30",
    d: [
      "PWA desteği: GÖKTUNGU artık tarayıcıdan masaüstü/mobil uygulama olarak kurulabilir (manifest.json, ikon seti, service worker, meta tag'ler)",
      "Profil menüsüne 'Uygulamayı Kur' öğesi eklendi (tarayıcı destekliyorsa görünür); adres çubuğundaki kur simgesiyle de kurulabilir",
      "Service worker ağ öncelikli çalışır: canlı veri (WS, MJPEG, tile, AI) asla önbelleklenmez; sunucuya ulaşılamazsa arayüz iskeleti önbellekten açılır",
    ],
  },
  {
    s: "2.4.13", t: "2026-07-30",
    d: [
      "Interceptor hız profili: hızla ilgili tüm giriş alanlarının üst sınırı 300 km/h (83.3 m/s) oldu — Dron Ayarları (yükselme/alçalma/hareket hızı), ang. hücum hızı, rota/spiral/nokta hızları",
      "Dron Ayarları açılırken hız limitleri MAVLink'ten okunur (WPNAV_SPEED/_UP/_DN); okunan değer 300 km/h'i aşıyorsa slider üst sınırı otomatik genişler, okunamazsa 300 km/h varsayılanı uygulanır",
      "Hücum hızı girişinde canlı sınır denetimi: 83.3 m/s üzeri kırmızı uyarı + otomatik kırpma; backend'de de aynı sınır uygulanır",
    ],
  },
  {
    s: "2.4.12", t: "2026-07-30",
    d: [
      "Bağlantı Yöneticisi'ne düzenleme (kalem) düğmesi eklendi: kayıtlı SERİ/TCP/UDP/DJI bağlantılarının adı, portu, baud'u ve host'u silinip yeniden eklenmeden güncellenebilir",
      "Aktif (bağlı/dinleyen) bağlantı düzenlenirse sunucu bağlantıyı güvenli şekilde durdurup yeni ayarlarla otomatik yeniden başlatır",
      "Düzenleme işlemleri pilot loguna kaydedilir (kayıt yönetimi izni gerektirir)",
    ],
  },
  {
    s: "2.4.11", t: "2026-07-30",
    d: [
      "Açılışta bağımlılık kontrolü: eksik zorunlu Python paketi (websockets, opencv-python, numpy, pymavlink, pyserial) varsa çalışma ortasında çökme yerine açılışta anlaşılır hata + kurulum komutu gösterilir",
      "requirements.txt eklendi — tek komutla kurulum: pip3 install -r requirements.txt (Ubuntu 23.04+ için --break-system-packages / venv notlarıyla)",
      "AI işçisinde (ai_sunucu.py) numpy/opencv eksikse anlaşılır kurulum mesajı",
    ],
  },
  {
    s: "2.4.10", t: "2026-07-29",
    d: [
      "HTTP video (MP4/WebM) kaynakları artık AI boru hattından geçiyor: görüntü sunucuda FFmpeg ile kare kare alınır, AI tespit çerçeveleri + isimler çizilir ve anotasyonlu MJPEG olarak izlenir (önceden tarayıcı doğrudan oynatıyordu, AI hiç uygulanmıyordu)",
      "MP4 gibi dosya kaynakları gerçek hızda okunur ve video bitince otomatik başa sarar (kesintisiz döngü) — canlı kamera gibi davranır",
      "HTTP video proxy oynatması tüm görünümlerde: Kameralar paneli, harita önizleme, lokasyon popup'ı, video duvarı ve dron kamera görüntüsü",
      "Uçtan uca doğrulandı: http://.../video.mp4 kaynağında yüz tespiti çerçevesi + KİŞİ etiketi izlenen görüntüye çiziliyor",
    ],
  },
  {
    s: "2.4.9", t: "2026-07-29",
    d: [
      "AKTİF AI İZLEMELERİ listesinde gerçek akış durumu: işçi kare alıyorsa yeşil LED, akış açılamıyorsa gri LED + kırmızı hata metni (sorunun kaynağı artık arayüzden görülür)",
      "Windows uyumu: DONANIM (webcam) yakalamada CAP_DSHOW geri çekilmesi (MSMF takılmalarına karşı)",
      "AI işçisinde OpenCV FFMPEG'siz kurulumlar için saf-Python MJPEG okuyucu geri çekilmesi (VideoCapture HTTP akışı açamazsa devreye girer)",
      "Uçtan uca yüz tespiti doğrulandı: canlı akışta YuNet yüz çerçevesi + KİŞİ etiketi görüntü üzerine çiziliyor, tespit veritabanına işleniyor",
    ],
  },
  {
    s: "2.4.8", t: "2026-07-29",
    d: [
      "Otomatik AI izleme: kamera kaydedilirken AI görevleri seçiliyse izleme otomatik başlatılıyor — ayrıca elle başlatma gerekmez ('Aktif AI izlemesi yok' sorunu giderildi)",
      "Kamera düzenlenince AI izleme görev listesiyle eşitleniyor: görev eklenince başlar/yenilenir, tüm görevler kapatılınca durur; kamera silinince izleme de durdurulur",
      "Açılış taraması: AI görevleri seçili tüm kameralar sunucu açılışında otomatik izlemeye alınıyor (kalıcı görev kaydı olmasa bile)",
      "Kameralar panelinde AI izlemesi aktif kameraların başlığında yeşil 'AI' rozeti (önizleme ve liste görünümü)",
    ],
  },
  {
    s: "2.4.7", t: "2026-07-29",
    d: [
      "Anotasyonlu AI video: AI izleme aktif kameralarda tespit çerçeveleri ve kişi/nesne adları (yüz kütüphanesi eşleşmeli) doğrudan görüntünün üzerine çiziliyor — panel, ayrık pencere, lokasyon popup'ı, dron gömülü izleme ve video duvarı dahil tüm önizlemelerde",
      "DONANIM (webcam) kaynağı artık sunucuda Python/OpenCV ile yakalanıyor ve MJPEG olarak servis ediliyor; AI boru hattına diğer kaynaklarla aynı şekilde giriyor",
      "Kamera formunda cihaz listesi sunucu makinesinden sorgulanıyor (indeks tabanlı); tarayıcı getUserMedia bağımlılığı kaldırıldı",
      "AI işçileri izleme akışını ana sunucunun MJPEG proxy'sinden (gcs_proxy) okuyor — RTSP/DJI/DONANIM için tek yakalama süreci",
      "AI işçisi kare başına canlı tespit kutularını ana sunucuya bildiriyor; yüz kutuları kişi adı + benzerlik yüzdesiyle, plakalar kayıtlı araç bilgisiyle etiketleniyor",
    ],
  },
  {
    s: "2.4.6", t: "2026-07-29",
    d: [
      "'Yüz kaydedilemedi: modeller yuklu degil' düzeltmesi: yüz kaydı istekleri artık yalnızca yüz modeli yüklü (yuz_destegi=true) çevrimiçi AI işçilerine yönlendiriliyor; ilk işçi başarısızsa diğerleri sırayla deneniyor",
      "AI işçisi /durum yanıtına yuz_destegi alanı eklendi; yüz kaydı hata mesajları anlaşılır hale getirildi",
      "ai_sunucu.py --model-kontrol argümanı: model dosyalarını doğrular, eksik/bozuksa otomatik indirip sonucu raporlar",
      "Model indirmede SSL sertifika hatalarında (kurumsal ağ/Windows) doğrulamasız ikinci deneme",
      "AI_SUNUCU_KURULUM.md: model doğrulama adımı, manuel indirme bağlantıları ve yeni sorun giderme satırları",
      "Kameralar panelinde kamera ayrı pencereye alınınca paneldeki boş önizleme kutusu artık kaldırılıyor (kart kompakt satıra düşer); pencere kapanınca önizleme panele geri döner",
    ],
  },
  {
    s: "2.4.5", t: "2026-07-29",
    d: [
      "Serbest Form görevde çift tıklama ile düzenleme: haritada göreve çift tıklayınca popup mevcut parametrelerle (isim, aralık, yön, yükseklik, hız) ve çokgenle açılır; değişiklikler rotayı canlı yeniden hesaplar, GÖREVİ GÜNCELLE mevcut kaydı günceller",
      "Kamera formunda dinamik alanlar artık gerçekten gizleniyor: DJI DRON seçimi yalnızca DJI protokolünde, KAMERA CİHAZI yalnızca DONANIM'da, URL alanı yalnızca ağ protokollerinde görünür",
      "Kamera formunda AI Görevleri bölümü iki sütunlu kompakt düzene geçti; onay kutuları iPhone tarzı toggle anahtarlarla değiştirildi",
      "Haritada artık yalnızca lokasyon (bina) ikonu gösteriliyor; lokasyon çevresindeki ayrık kamera ikonları kaldırıldı — kameralara lokasyon popup'ından erişiliyor",
      "Lokasyon kameraları popup'ında kameraya tıklayınca yayın popup içinde gömülü başlıyor (RTSP/RTP/DJI/MJPEG/HLS/HTTP/DONANIM); ayrı pencerede açma isteğe bağlı düğmeyle",
      "ai_sunucu.py sağlamlaştırıldı: eksik/bozuk ONNX modelinde otomatik yeniden indirme ve zarif geri çekilme (yüz tanıma atlanır, diğer görevler çalışır); OneDrive placeholder uyarısı kılavuza eklendi",
      "OpenCV 5 uyumu: HOGDescriptor bulunmayan sürümlerde insan tespiti hareket tabanlı (MOG2) analizle sürdürülüyor",
      "Rotalara meta alanı eklendi (serbest form köşeleri, aralık, yön) — veritabanı göçü ilk açılışta otomatik uygulanır",
    ],
  },
  {
    s: "2.4.4", t: "2026-07-29",
    d: [
      "Rotalar menüsüne 'Serbest Form' görev tipi eklendi (ilaçlama dronu için alan tarama görevi)",
      "Parametre popup'ı: görev adı, aralık mesafesi (şerit arası), uçuş yönü (0-359°), yükseklik ve hız",
      "OLUŞTUR ile harita çizim moduna geçer: tıklanan noktalarla çokgen alan oluşur (3. noktadan itibaren), her yeni noktayla şekil güncellenir",
      "Çokgen, aralık ve uçuş yönüne göre dilimlenir; zigzag (boustrophedon) ilaçlama rotası otomatik üretilir",
      "Popup çizim boyunca açık kalır; aralık/yön/yükseklik değişince rota anında yeniden hesaplanır",
      "Bilgi kutusu: köşe sayısı, rota noktası, alan (m²/ha) ve toplam rota uzunluğu canlı gösterilir",
      "Son Noktayı Geri Al düğmesi; GÖREVİ SONLANDIR ile rota kaydedilir ve Rotalar panelinde listelenir",
    ],
  },
  {
    s: "2.4.3", t: "2026-07-29",
    d: [
      "Dronlar menüsüne 'Sürü Uçuş' eklendi: master dron ve XYZ ofsetli slave dronlarla sürü kurulumu",
      "Slave Ekle popup'ı: dron seçimi + X (ileri/geri), Y (sağ/sol), Z (yukarı/aşağı) takip mesafesi girişi (metre)",
      "Sürü İzleme popup'ı: 3 boyutlu uzayda uçuş formasyonu görselleştirme — fare ile döndürme, tekerlekle yakınlaştırma; hedef (kesikli) ve gerçek (dolu) konumlar birlikte",
      "Gerçek zamanlı dronlar arası mesafe tablosu: master-slave ve slave-slave çiftleri, gerçek/hedef mesafe karşılaştırmalı",
      "Master takeoff alınca slave dronlar da otomatik takeoff alır (Z ofsetli irtifa)",
      "Sürüyü Dağıt: tüm slave'ler LOITER'a alınır; izleme tablosunda tek tek 'Sürüden Çıkar' seçeneği",
      "Slave dronlar 5 Hz GUIDED konum hedefiyle master'ı gövde çerçevesinde (heading'e göre XYZ) takip eder",
      "Sürü komutları pilotluk izniyle denetlenir ve pilot log'una yazılır",
    ],
  },
  {
    s: "2.4.2", t: "2026-07-29",
    d: [
      "Dron paneline 'Kamera Seç' düğmesi: boşta (lokasyonsuz ve dronsuz) kameralar listelenir, seçilen kamera dron kartının altında gömülü izlenir",
      "Gömülü izlemeye tıklanınca görüntü ayrı pencereye alınır; pencere kapatılınca bağlantısına göre dron paneline, lokasyon penceresine veya Kameralar paneline döner",
      "Kamera düzenlemede AI görev anahtarları: Kişi Tanıma, Araç Tanıma, Hava Aracı Tespit, İnsan Tespit, Kara Aracı Tespit (kamera başına aç/kapa)",
      "AI işçisine yeni tespit modelleri: Hava Aracı Tespit (öncelikli), İnsan Tespit (HOG) ve Kara Aracı Tespit; tespitler AI TESPİT akışına ve geçmişe düşer",
      "AI tespitleri drona bağlı kamerada aktif uçuş kaydına bağlanır (uçuş logu ilişkisi)",
      "Uçuş geçmişi oynatmada zaman çizelgesi üzerinde tespit işaretleri ve tespit şeridi; tıklanınca fotoğraf/3 sn klip detayı açılır",
      "Dron kartında yatay kaydırılabilir tespit şeridi (fare tekerleği + dokunmatik); hedefe tıklayıp onaylanınca AI sunucusunda hedef takibi başlar ve dron angaje olur",
      "Uzak AI sunucusu kurulum ve bağlantı kılavuzu eklendi (AI_SUNUCU_KURULUM.md)",
    ],
  },
  {
    s: "2.4.1", t: "2026-07-29",
    d: [
      "Haritada kayıtlı lokasyon (bina) ikonları: her binanın yanında bağlı kamera sayısı kırmızı rozetle gösteriliyor",
      "Lokasyon kameraları penceresi: harita ikonuna veya Kayıtlı Lokasyonlar listesindeki satıra tıklanınca o binaya bağlı kameralar ayrı bir popup'ta listeleniyor; önizleme düğmesiyle kamera görüntüsü açılıyor",
      "Kayıtlı Lokasyonlar listesine kamera sayısı rozetli 'Kameralar' düğmesi eklendi",
      "'Kayıtlı Lokasyonlar' menü öğesi Göktungu menüsünden AI menüsünün başına taşındı",
      "Rol Yönetimi'ne 'AI (Görüntü İşleme)' izin grubu eklendi: İzleme, Kütüphane Yönetimi, Sunucu Yönetimi, Tespit Yönetimi",
      "Tüm AI komutları artık yeni AI izin grubuyla denetleniyor; mevcut rollere yeni izinler otomatik tanımlanıyor (varsayılan: izinli)",
    ],
  },
  {
    s: "2.4.0", t: "2026-07-29",
    d: [
      "AI görüntü işleme katmanı: dağıtık AI sunucuları üzerinde yüz tanıma ve plaka tanıma",
      "AI > Sunucular: NVIDIA (örn. ASUS Ascent GX10) ve Windows/CPU tabanlı AI işlem sunucuları; görevler sunucu yüküne göre otomatik dağıtılıyor",
      "AI > Kütüphane > Kişiler: kişi kaydı, arama seviyesi (GÜVENLİ/GÜVENSİZ/ARANILAN), web kamerası veya fotoğraf yükleyerek yüz tanımı",
      "AI > Kütüphane > Araçlar: plaka, marka, model, renk ve arama seviyesiyle araç kaydı",
      "Arka plan tanıma servisi: AI izleme başlatılan kamerada web arayüzü kapansa bile yüz/plaka tanıma sürüyor ve loglanıyor",
      "Kayıtsız Tespitler listesi: kayıtlı olmayan kişi/araçlar arka planda kaydediliyor; 'yeni kişiye ekle', 'mevcut kişiye ekle', 'yeni araç tanımla', 'yok say' seçenekleri",
      "Detaylı tespit geçmişi: her tespitte fotoğraf + 3 saniyelik video klip; tür/kamera/tarih filtreleriyle geriye dönük izleme",
      "Alt panel sekmeli oldu: RADAR (hedef sayısı grafiği) / AI TESPİT (tespit edilen yüzler ve plakalar isimleriyle akıyor; kayıtlı değilse 'Bilinmiyor')",
      "Lokasyonlar modülü genişletildi: bina adı, adres, enlem/boylam; kamera eklerken bina seçimi yapılıyor",
      "Haritada kamera ikonları: binalara bağlı kameralar haritada gösteriliyor, ikona tıklanınca küçük canlı önizleme penceresi açılıyor",
    ],
  },
  {
    s: "2.3.3", t: "2026-07-28",
    d: [
      "Karanlık modda üst barın açık renk görünme sorunu düzeltildi (tema değişkenli arka plan)",
      "Tüm popup ve paneller için minimum üst sınır (48px): hiçbir pencere üst barın arkasına sürüklenemiyor, kayıtlı konumlar da bar altına çekiliyor",
      "Profil fotoğrafı (avatar) sistemi: resmi olmayan kullanıcılarda kırık resim yerine yuvarlak kullanıcı ikonu gösteriliyor",
      "Kullanıcılar Pilot Hakkında ekranından kendi profil fotoğraflarını yükleyebiliyor/kaldırabiliyor (yönetici herkes için); resimler otomatik 256px'e küçültülüyor",
      "Yeni Kullanıcı formu Kullanıcı Yönetimi listesinden çıkarıldı: artık yönetici profil menüsündeki 'Yeni Kullanıcı' öğesinden açılan, gece/gündüz temasına uyumlu ayrı bir pencere",
    ],
  },
  {
    s: "2.3.2", t: "2026-07-28",
    d: [
      "İlk kurulum güvencesi: sistemde hiç kullanıcı yoksa açılışta varsayılan yönetici hesabı otomatik oluşturuluyor",
      "Kullanıcı Yönetimi'ne 'Yeni Kullanıcı' ekleme formu eklendi (yalnızca yönetici; ad, ünvan, rol ve şifre ile)",
      "Kullanıcı Yönetimi'ne 'Şifre Sıfırla' düğmesi eklendi: yönetici herhangi bir kullanıcı için yeni şifre belirleyebiliyor",
      "Giriş ekranına 'Şifremi unuttum' bağlantısı eklendi (yönetici üzerinden sıfırlama yönlendirmesi)",
      "Harita karo sunumunda istemci bağlantı kopması (WinError 10053) hata mesajları sessizleştirildi",
      "HTTP sunucusu çok iş parçacıklı yapıldı: tek karo isteği diğer istekleri bloklamıyor",
    ],
  },
  {
    s: "2.3.1", t: "2026-07-28",
    d: [
      "Sürüm Geçmişi popup'ının çarpı düğmesinden kapanmama hatası düzeltildi",
      "Tüm popup'lar tek pencere yönetim sistemine alındı: açılan pencere en üstte açılır, tıklanınca aktifleşip öne gelir (ayarlar, sürüm geçmişi, geçmiş yönetimi, kullanıcı/rol yönetimi dahil)",
      "Popup'ların haritanın/panellerin arkasında kalma sorunu giderildi: açıksa üstte, kapalıysa gizli",
      "Panel aç/kapat menü öğelerinde gri görünüm kaldırıldı: durum yalnızca check (tik) işaretiyle gösteriliyor",
      "Popup açan menü öğelerine de check işareti eklendi: Program Ayarları, Harita/Arayüz Ayarları, Kayıtlı Lokasyonlar, Radar Ayarları, Bağlantı Yöneticisi vb. açıkken menüde tikli görünüyor",
      "Proje dizini temizlendi: eski yedekler, test artıkları ve kullanılmayan dosyalar paketten çıkarıldı",
    ],
  },
  {
    s: "2.3.0", t: "2026-07-28",
    d: [
      "Veri altyapısı SQLite'a taşındı: uçuş geçmişi/telemetri logları, radar kayıtları, program ayarları ve dron kayıtları artık gcs.db'de (JSON dosyaları kaldırıldı; eski veriler ilk açılışta otomatik aktarılır)",
      "Tüm giriş denemeleri loglanıyor (başarılı + başarısız)",
      "Giriş loglarında istemci bağlantı ayrıntıları: IP, port, yerel IP, tarayıcı (User-Agent), origin, host, proxy başlıkları",
      "Harita Ayarları > Çevrimdışı Önbellek: kaynak bazında dağılım tablosu (karo sayısı, boyut, zoom aralığı, son indirme)",
      "Spiral rota: merkez tıklanınca rota otomatik kaydediliyor ve düzenleme modundan çıkılıyor",
    ],
  },
  {
    s: "2.2.0", t: "2026-07-28",
    d: [
      "Harita araç ikonları (arama, cetvel) haritanın sol üst köşesine taşındı",
      "Panel katman yönetimi: her panel açıldığında en üstte açılıyor",
      "Panel başlığına/gövdesine tıklanınca o panel diğerlerinin üstüne geçiyor (ayrık dron kartları dahil)",
      "Rota Yükle: Mission Planner (.waypoints) ve QGroundControl (.plan) görev dosyaları içe aktarılıyor (Rotalar > Rota Yükle)",
      "Yeni rota tipi altyapısı ve ilk tip: Spiral Rota — nokta sayısı, çap, başlangıç/bitiş yüksekliği ve dron tipi parametreli; haritada merkez tıklanınca oluşur",
      "Spiral rotada sabit kanat profili: tırmanma eğimi sınırına (%10) göre tur sayısı ve irtifa basamakları otomatik hesaplanıyor",
    ],
  },
  {
    s: "2.1.8", t: "2026-07-28",
    d: [
      "DJI köprüsü sunucu açılışında otomatik başlatılıyor; köprü portu (8790) durumu açılış logunda bildiriliyor",
      "Bağlantı Yöneticisi'nde DJI köprü durumu artık doğru gösteriliyor (BAĞLI/KAPALI telemetri yayınıyla eşitlendi)",
      "Dron kartı yalnızca dron gerçekten bağlıyken oluşturuluyor; köprüye bağlı telefon tek başına kart oluşturmuyor, dron kopunca kart panelden kaldırılıyor",
      "Program ayarlarından radar kapatıldığında üst bardaki Radar menüsü tamamen gizleniyor",
      "Kullanıcının rolünde radar izleme izni yoksa Radar menüsü gizleniyor",
      "Program ayarları yalnızca yönetici tarafından değiştirilebiliyor (arayüz kilidi + sunucu denetimi)",
      "Uçuş geçmişi kullanıcıya göre filtreleniyor: her kullanıcı yalnızca kendi uçuşlarını görüyor (yönetici tümünü görür)",
      "Uçuş geçmişine 'Tümünü Sil' eklendi (yalnızca yönetici, onaylı)",
      "Sürüm Geçmişi popup'ı eklendi (Program Hakkında > sürüm numarasına tıklayın)",
    ],
  },
  {
    s: "2.1.7", t: "2026-07-27",
    d: [
      "Rol yönetimi: izin grupları (radar, dron, kamera, rota, sistem) ve rol düzenleme arayüzü",
      "Pilot işlem loglama: tüm kritik işlemler oturum açan pilotun etiketiyle kalıcı kaydediliyor",
      "Pilot Hakkında popup'ı (profil, rol, işlem geçmişi)",
      "DJI entegrasyonu: Bağlantı Yöneticisi'ne DJI bağlantı türü, MSDK Android köprü uygulaması (GÖKTUNGU DJI Köprü), OSDK Python adaptörü",
      "DJI dron kamerası kamera yönetimine eklenebiliyor",
      "Android köprüde kalp (heartbeat) mekanizması: 40+ sn kopmadan bağlantı korunuyor",
    ],
  },
  {
    s: "2.1.6", t: "2026-07-27",
    d: [
      "Bölüm popup sistemi: tüm bölümler (Dronlar, Rotalar, Kameralar, Hedefler...) taşınabilir bağımsız popup'lara dönüştürüldü",
      "Popup konum ve durumları kalıcı kaydediliyor; akıllı varsayılan yerleşim",
      "Tam ekran modu iyileştirmeleri",
    ],
  },
  {
    s: "2.1.5", t: "2026-07-27",
    d: [
      "Dron kartı hata düzeltmeleri: önbellek sürüm eşitleme, üst bar katman (z-index) sorunu",
      "Kart menüsü ve sürükle-bırak davranış düzeltmeleri",
    ],
  },
  {
    s: "2.1.4", t: "2026-07-26",
    d: [
      "Dron kartı yeniden düzenleme: akıllı Takeoff/Land düğmesi, 2 satırlı kaydırmalı telemetri, aksiyon barı",
      "UDP MAVLink port rozeti ve bilgi popup'ı",
      "Araç tipi ikonu (kopter / uçak / helikopter / VTOL)",
      "Toolbar temizliği: menü çubuğuna taşınan öğelerin eski düğmeleri kaldırıldı",
    ],
  },
  {
    s: "2.1.3", t: "2026-07-26",
    d: [
      "Klasik menü çubuğu: Radar, Dronlar, Kameralar, Rotalar, Göktungu Uygulaması, Yardım menüleri",
      "Kullanıcı avatarı en sağa taşındı; Kullanıcı Yönetimi profil menüsüne girdi",
      "ALT tuşu ile menü navigasyonu ve hızlı erişim harfleri",
    ],
  },
  {
    s: "2.1.2", t: "2026-07-26",
    d: [
      "QGC tarzı kaydırmalı onay mekanizması (kritik komutlarda sürükleyerek onay)",
      "Evrensel ince şık scrollbar tüm panel ve popup'lara uygulandı",
      "Harita arama kutusu sağa taşındı",
    ],
  },
  {
    s: "2.1.1", t: "2026-07-26",
    d: [
      "Cetvel: harita üzerinde mesafe ölçüm aracı",
      "Durum çubuğunda zoom göstergesi",
      "Harita Ayarları ayrı popup: kaynak combobox'ı (Google, Esri, Bing, OSM...), Cesium ayarları, yer arama",
      "Dokunmatik cihaz desteği iyileştirmeleri",
    ],
  },
  {
    s: "2.1.0", t: "2026-07-25",
    d: [
      "FAILSAFE popup'ı: araç tipine göre (kopter/uçak/helikopter) failsafe parametreleri",
      "Kalibrasyon popup'ı: gyro, ivme, pusula, seviye, baro, ESC kalibrasyonları",
      "UDP MAVLink yayını: her dron için 9000+sysid portunda Mission Planner köprüsü (çift yönlü)",
      "Araç tipi algılama (HEARTBEAT MAV_TYPE)",
    ],
  },
  {
    s: "2.0.2", t: "2026-07-25",
    d: [
      "Türkçe eğitim dokümanı (ekran görüntülü PDF)",
      "Uçuş modu seçim iyileştirmeleri (araç tipine göre mod listesi)",
      "Dron Ayarları popup'ı mevcut parametre değerlerini yükleyerek açılıyor",
    ],
  },
  {
    s: "2.0.1", t: "2026-07-25",
    d: [
      "Haritada dron ikonuna tıklama menüsü düzeltildi",
      "Ayrık pencere modunda dron menü düğmesi düzeltildi",
      "Fiziksel joystick desteği düzeltmeleri",
    ],
  },
  {
    s: "2.0.0", t: "2026-07-24",
    d: [
      "Çok kullanıcılı oturum sistemi: giriş ekranı, kullanıcı yönetimi, SHA-256 şifre saklama",
      "Video Duvarı: ayrı sayfada çoklu kamera izleme (video.html)",
      "Program Hakkında popup'ı ve merkezi sürüm tanımı",
      "Dron paneli ve radar arayüzü temel iyileştirmeleri",
    ],
  },
];
