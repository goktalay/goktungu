# GÖKTUNGU DJI Köprüsü — Google Play mağaza künyesi

Paket adı: `com.turkbey.goktungu`
Sürüm: 1.0.0 (versionCode 1)
Yayıncı: Türkbey Teknoloji Anonim Şirketi

---

## Uygulama adı (en çok 30 karakter)

**TR:** `GÖKTUNGU DJI Köprüsü` (20)
**EN:** `GOKTUNGU DJI Bridge` (19)

## Kısa açıklama (en çok 80 karakter)

**TR:** `DJI araçlarını GÖKTUNGU merkez komuta kontrol sistemine bağlar.` (63)

**EN:** `Connects DJI aircraft to the GOKTUNGU central command and control system.` (73)

---

## Tam açıklama (en çok 4000 karakter)

### TR

GÖKTUNGU DJI Köprüsü, DJI marka hava araçlarını GÖKTUNGU merkez komuta kontrol
sistemine bağlayan kurumsal bir köprü uygulamasıdır. Uygulama, DJI
kumandasına takılı Android cihaz üzerinde çalışır ve aracın telemetrisini
kendi merkez sunucunuza aktarır.

Bu uygulama kurumsal kullanıcılar içindir. Çalışması için GÖKTUNGU merkez
komuta kontrol sistemine erişim ve geçerli bir kurum hesabı gerekir.
Bağımsız bir uçuş uygulaması değildir.

YAPTIĞI İŞ

Araç telemetrisini merkeze aktarır: konum, irtifa, hız, yön, uydu sayısı,
batarya durumu, uçuş kipi ve araç modeli. Aktarım aracınızın bağlı olduğu
sürece kesintisiz sürer; bağlantı koparsa kendiliğinden yeniden kurulur.

Merkezden gelen uçuş komutlarını uygular: kalkış, iniş, eve dönüş, görev
başlatma ve durdurma, belirtilen noktaya gitme. Çok noktalı görevler DJI
görev biçiminde araca yüklenir.

Merkezle bağlantı durumunu, araç durumunu ve tüm komut geçmişini cihaz
ekranında açıkça gösterir. Hiçbir hata sessizce yutulmaz.

KOORDİNAT GÜVENLİĞİ

Uçuş komutlarında enlem ve boylamın yer değiştirmesi, aracın hedeflenen
noktaya değil yüzlerce kilometre uzağa yönelmesine yol açar. Bu uygulama
her konum komutunu uygulamadan önce aracın bilinen konumuna göre
doğrular. Hedef, aracın menzilinden makul olmayan ölçüde uzaksa komut
uygulanmaz ve gerekçesi merkeze bildirilir.

Doğrulama tek bir dönüşüm noktasında toplanmıştır ve otomatik ölçümle
korunmaktadır.

KAPALI DEVRE ÇALIŞMA

Merkez sunucu adresi cihazda saklanır. Kapalı devre kurulumlarda
uygulama yerel ağ üzerinden çalışır; internet bağlantısı gerekmez.
Şifresiz bağlantıya yalnız özel ağ adreslerinde izin verilir; genel
adreslerde şifreli bağlantı zorunludur.

GEREKSİNİMLER

Android 6.0 veya üstü. ARM işlemcili cihaz. DJI Mobile SDK v5 ile uyumlu
bir DJI hava aracı ve kumandası. GÖKTUNGU merkez komuta kontrol sistemine
ağ erişimi.

DESTEKLENEN ARAÇLAR

DJI Mobile SDK v5'in desteklediği kurumsal ve profesyonel araçlar
(Matrice ve Mavic kurumsal serileri dahil). Desteklenen araç listesi
DJI'nin SDK sürümüne bağlı olarak değişir.

Türkbey Teknoloji Anonim Şirketi tarafından geliştirilmiştir.

### EN

GOKTUNGU DJI Bridge is an enterprise bridge application that connects DJI
aircraft to the GOKTUNGU central command and control system. It runs on the
Android device attached to the DJI remote controller and relays aircraft
telemetry to your own central server.

This application is intended for enterprise users. It requires access to
a GOKTUNGU central command and control system and a valid organisation
account. It is not a standalone flight application.

WHAT IT DOES

Relays aircraft telemetry to the centre: position, altitude, speed,
heading, satellite count, battery state, flight mode and aircraft model.
Relaying continues uninterrupted while the aircraft is connected and
reconnects automatically if the link drops.

Executes flight commands received from the centre: take off, land, return
to home, start and stop missions, and fly to a specified point.
Multi-point missions are uploaded to the aircraft in DJI mission format.

Displays connection state, aircraft state and the full command history on
the device screen. No error is silently discarded.

COORDINATE SAFETY

If latitude and longitude are transposed in a flight command, the
aircraft heads hundreds of kilometres away from the intended point rather
than to it. This application validates every position command against the
aircraft's known location before executing it. If the target is
unreasonably far from the aircraft's operating range, the command is
rejected and the reason is reported to the centre.

Validation is concentrated at a single conversion point and protected by
automated measurement.

AIR-GAPPED OPERATION

The central server address is stored on the device. In air-gapped
installations the application works over the local network and requires
no internet connection. Unencrypted connections are permitted only to
private network addresses; public addresses require encryption.

REQUIREMENTS

Android 6.0 or later. ARM processor. A DJI aircraft and remote controller
supported by DJI Mobile SDK v5. Network access to a GOKTUNGU central command
and control system.

Developed by Turkbey Teknoloji Anonim Sirketi.

---

## Sınıflandırma

| Alan | Değer |
|---|---|
| Kategori | İş (Business) |
| Etiketler | Kurumsal, Araçlar |
| İçerik derecesi | Herkes (Everyone) — şiddet/cinsellik/madde içeriği yok |
| Reklam içerir | Hayır |
| Uygulama içi satın alma | Hayır |
| Hedef kitle | 18+ (kurumsal araç) |
| Devlet uygulaması mı | Hayır |

## Veri güvenliği bildirimi (Play Console)

Aşağıdaki tablo manifest izinleri ve kaynak kod taramasıyla
doğrulanmıştır; varsayım içermez.

| Veri türü | Toplanır | Paylaşılır | Amaç | Zorunlu |
|---|---|---|---|---|
| Yaklaşık konum | Evet | Hayır | Uygulama işlevi (araç konumu) | Evet |
| Kesin konum | Evet | Hayır | Uygulama işlevi (araç konumu) | Evet |
| E-posta adresi | Evet | Hayır | Uygulama işlevi (köprü kimliği) | Evet |
| Cihaz tanımlayıcı | Evet | Hayır | Uygulama işlevi (araç eşleme) | Evet |
| Uygulama etkinlik günlüğü | Evet | Hayır | Uygulama işlevi (komut kaydı) | Evet |

**Önemli:** Toplanan veriler yalnız kullanıcının **kendi** merkez
sunucusuna gönderilir. Türkbey Teknoloji Anonim Şirketi bu verilere erişmez, üçüncü taraflarla
paylaşmaz ve reklam amacıyla kullanmaz. Kapalı devre kurulumlarda veri
kurum ağının dışına çıkmaz.

Aktarım şifrelenir mi: Genel adreslerde evet (TLS zorunlu). Özel ağ
adreslerinde kurumun kendi tercihine bırakılır.
Kullanıcı silme isteyebilir mi: Evet — veri kurumun kendi sunucusunda
tutulduğu için silme kurum yöneticisi tarafından yapılır.

## İzin gerekçeleri

| İzin | Gerekçe |
|---|---|
| `ACCESS_FINE_LOCATION` / `ACCESS_COARSE_LOCATION` | DJI SDK araç konumu ve uçuş güvenliği için zorunlu kılar; koordinat doğrulaması bu veriye dayanır |
| `INTERNET` | Merkez sunucuya köprü bağlantısı |
| `ACCESS_NETWORK_STATE` | Bağlantı koptuğunda yeniden kurma |
| `ACCESS_WIFI_STATE` / `CHANGE_WIFI_STATE` | DJI aracına Wi-Fi üzerinden bağlanma |
| `USB_PERMISSION` | DJI kumandasına USB üzerinden bağlanma |
| `FOREGROUND_SERVICE` + `FOREGROUND_SERVICE_CONNECTED_DEVICE` | Uçuş sırasında telemetri akışının kesilmemesi |
| `WAKE_LOCK` | Uçuş sırasında cihazın uykuya geçmemesi |
| `POST_NOTIFICATIONS` | Köprü durumunu kalıcı bildirimde gösterme |

Konum izni **arka planda** istenmez (`ACCESS_BACKGROUND_LOCATION` yok);
uygulama ön plan hizmetiyle çalışır.

## Görseller

| Varlık | Dosya | Ölçü |
|---|---|---|
| Uygulama ikonu | `ikon_512.png` | 512x512 |
| Öne çıkan görsel | `one_cikan_1024x500.png` | 1024x500 |
| Ekran görüntüsü 1 | `ekran_1_bagli.png` | 1080x1350 |
| Ekran görüntüsü 2 | `ekran_2_yapilandirma.png` | 1080x1350 |

**Not:** Ekran görüntüleri uygulamanın gerçek düzeninden
(`etkinlik_ana.xml`) ve gerçek dizgi kaynaklarından (`strings.xml`)
üretilmiştir; ancak **cihazdan alınmış gerçek ekran görüntüsü
değildir**. MSDK öykünücüde çalışmadığı için (x86 kütüphaneleri eksik)
gerçek görüntüler ilk cihaz denemesinde alınıp değiştirilmelidir.

## Yayın öncesi gereken kullanıcı işlemleri

1. **DJI API anahtarı** — `developer.dji.com` üzerinden `com.turkbey.goktungu`
   paket adı için üretilip `yerel.properties` dosyasına yazılmalı.
2. **Gizlilik politikası bağlantısı** — genel erişime açık bir URL
   zorunlu. Öneri: `https://goktungu.com/yasal/gizlilik/`
3. **İmza anahtarının yedeği** — `turkbey_goktungu.jks` kaybedilirse
   güncelleme yayınlanamaz.
4. **Kapalı deneme** — Play Console yeni yayıncılar için 12 sürekli test
   kullanıcısıyla 14 gün kapalı deneme isteyebilir.
