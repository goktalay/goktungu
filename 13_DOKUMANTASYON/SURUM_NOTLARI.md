# GÖKTUNGU Sürüm Notları — GRCOFF

Uygulama sürümü `js/surum.js` (`GCS_SURUM`), paket `goktungu/paket_surum.py`. Tam liste kaynaktaki `GCS_SURUM_GECMISI`.

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
