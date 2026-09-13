# GÖKTUNGU Sürüm Notları — GRCOFF

Uygulama sürümü `js/surum.js` (`GCS_SURUM`), paket sürümü `goktungu/paket_surum.py` (`PAKET_SURUM`) içindedir. Bu belge en yeni sürümleri özetler; kaynaktaki `GCS_SURUM_GECMISI` tam listedir.

## Paket 2.5.23 / Uygulama 2.4.153 — 2026-09-12

**GRCOFF Merkez aynı zamanda AI sunucusu: köprüsüz canlı görüntü AI (paket 2.5.23)**

- GRCOFF (offline Merkez) yerel AI işçisini kendisi başlatır ve AI yöneticisine 'GRCOFF Yerel AI' olarak kaydeder; ayrı bir AI sunucusu veya köprü gerekmez. Görevi seçili kameraların canlı görüntüsüne AI doğrudan uygulanır. 'Uygun (çevrimiçi/boş) AI sunucusu yok' hatası giderildi.
- Yerel işçi Merkez ile birlikte açılır, düşerse artan beklemeyle yeniden başlatılır. Kamera işçi hazır olmadan kaydedildiyse veya işçi yeniden başladıysa, AI görevli kameralar kendiliğinden yeniden izlemeye alınır.
- Kurulumun kaydırılmış AI portu (8910) kullanılır. İşçi canlı görüntüyü Merkez'in kendi yayın yolundan, yalnız bu makineden geçerli yerel işçi anahtarıyla okur; yayın dışarıya açılmaz. İşçi yalnız 127.0.0.1 üzerinde dinler; yerel ağdan erişilemez. İşçi kayıtlarını program dizini yerine veri dizinine yazar (Windows: C:\\ProgramData\\Goktungu\\Merkez, Linux: /var/lib/goktungu-merkez).
- Kamera formundan GRCOFF yerel işçisinde kapalı olan Kişi Tanıma ve Araç Tanıma anahtarları kaldırıldı; İnsan, Kara Aracı ve Hava Aracı tespiti etkin.
- Kurulumda örnek olarak eklenen ve hiç çalışmayan 'ASUS Ascent GX10' ile 'CPU AI Sunucusu (Yerel)' kayıtları artık eklenmez; değiştirilmemiş eski kayıtlar açılışta kaldırılır.
- GRCON (çevrimiçi Merkez) değişmedi: orada AI Görüntü Köprüsünde çalışır, yerel işçi başlatılmaz.

| Platform | Dosya | SHA-256 |
|---|---|---|
| Linux | `goktungu-merkez_2.5.23_all.deb` | `6e374b8535e1ab88c7b9e4be9af123ad2c28d3d2035f3ac9580eee17a52af00f` |
| Windows | `GOKTUNGU-Merkez-Setup-2.5.23.exe` | `133495db38d1b8242f07409b67622bc81b76fbee7c005898f27f4fc7af2b676e` |

## Paket 2.5.22 / Uygulama 2.4.152 — 2026-09-12

**Kamera formunda AI görevleri geri geldi, form bölümlere ayrıldı (paket 2.5.22)**

- Kamera ekle/düzenle formunda kaybolan 'AI Görevleri' bölümü geri geldi: Kişi Tanıma, Araç Tanıma, Hava Aracı Tespit, İnsan Tespit, Kara Aracı Tespit. Bölüm eksik olduğu için görevler hep boş kaydediliyor ve yerel AI izlemesi hiçbir kamerada başlamıyordu; görev seçilen kamerada izleme kayıt anında otomatik başlar.
- Kamera formu açılır-kapanır bölümlere ayrıldı: Genel, AI Görevleri ve AI Angajman Kalibrasyonu. Bölüm başlıkları seçili görev sayısını ve kalibrasyon durumunu gösterir; Kaydet/İptal düğmeleri her zaman görünür kalır.
- Otomatik güncelleme artık kurulu paketin gerçek sürümünü bildirir. 2.5.20 ve 2.5.21 kendini 2.5.19 olarak tanıttığı için 'Yeni sürüm hazır' uyarısı güncelleme yapıldıktan sonra da kaybolmuyordu.

| Platform | Dosya | SHA-256 |
|---|---|---|
| Linux | `goktungu-merkez_2.5.22_all.deb` | `f5521f0a626357ebffc3e6115f6e536e4a3dfa4dcbb87a57b7538855242b66f0` |
| Windows | `GOKTUNGU-Merkez-Setup-2.5.22.exe` | `8b5bebf893b4ee3bedfe9abe962826d357f0aca7140f75f8650229cf9a6dc835` |

## Paket 2.5.21 / Uygulama 2.4.151 — 2026-09-12

**Yerel AI ile takip edilen hedefe dron angajman altyapısı (paket 2.5.21)**

- GRCOFF (offline Merkez) yerel AI ile takip edilen hedef, operatör onaylı angajman zincirine bağlandı: yerel kamera tespiti coğrafi konuma çözülüp mevcut hedef deposuna yazılır; hedef listesi → kuyruğa alma → onay → başlatma akışı yerel hedeflerde de çalışır.
- İki kamera tipi eklendi. 'Sabit kamera': kamera sabit bir noktadadır, hedefi AYRI bir interceptor dron angaje eder; hedef konumu kalibrasyondan (konum/yükseklik/yön/eğim/görüş açısı) çözülür. 'Drona takılı kamera': kamera bir dronun üzerindedir ve onunla hareket eder; hedef konumu dronun canlı MAVLink pozundan çözülür ve hedefi kendi dronu angaje eder.
- Mesafe kestirimi hibrit yöntemle yapılır: kara sınıfları (insan, kara aracı) sabit kamerada yer düzlemi kesişimiyle (düz zeminde ~%5-10 hata), hava aracı ve tüm drona takılı kamera hedefleri sınıf bazlı görünen boyutla (~%25-40 hata) konumlanır. Her hedef bir mesafe güven değeri taşır; kalibrasyon eksik veya konum güvenilir değilse hedef angajmana ALINMAZ.
- Kamera formuna 'Kamera Tipi' seçici ve angajman kalibrasyon alanları eklendi. Yeni/eksik kalibreli kameralar açıkça 'angajmana alınamaz' olarak işaretlenir.
- Hava aracı sınıfı düşman dron tespiti için kullanılabilir: yerel AI bir dronu 'hava_araci' olarak sınıflandırır, operatör onayıyla interceptor dron angaje olur.
- 2.5.20 pasif takip sözleşmesi (yerel NDJSON kayıt katmanı) DEĞİŞMEDEN korundu; yerel besleme kolu bu akıştan bağımsız ikinci bir tüketicidir. Angajman her durumda açık operatör onayı gerektirir.

| Platform | Dosya | SHA-256 |
|---|---|---|
| Linux | `goktungu-merkez_2.5.21_all.deb` | `47980704eee52b4185a0488548865ebebe5a3b8f8870e1e8112339e1f457757d` |
| Windows | `GOKTUNGU-Merkez-Setup-2.5.21.exe` | `49b30ff654b11f6ddcd2d8d3c5e99774f309e527d644deea84193ed277c84a8f` |

## Paket 2.5.20 / Uygulama 2.4.150 — 2026-09-12

**GRCOFF yerel AI çalışma kipi ve Kamera paneli kapatması düzeltildi**

- GRCOFF (offline Merkez) Kamera panelinin başlıktaki X düğmesi ortak görünürlük kaydını kalıcı olarak kapatır; panel açılışta görünür kalabilir ancak kullanıcı kapattığında kendiliğinden yeniden açılmaz.
- GRCOFF, Köprü gerektirmeden aynı bilgisayarda 127.0.0.1:8900 üzerinde yerel AI işçisini başlatır. İşçi CPU ile çalışır; uygun NVIDIA ortamında GPU kipini seçer. Görüntü, tespit, yüz şablonu ve kimlik bilgisi haricî sunucuya veya Köprüye taşınmaz.
- Offline paket AI modellerini içerir ve ilk kurulumdan sonra internet bağlantısı gerektirmeden yerel çalışma için hazırlanır. AI işçisi Merkez kapanırken düzenli biçimde durdurulur ve yinelenen başlatmalarda sağlık uç noktasından doğrulanır.
- GRCON çevrimiçi sunucuda bu yerel AI işçisi başlatılmaz; çevrimiçi mimari ile GRCOFF yerel işleme ayrımı korunur.
