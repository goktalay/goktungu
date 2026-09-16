# GÖKTUNGU MAVLink Köprüsü — Google Play mağaza künyesi

Paket adı: `com.turkbey.goktungumav`
Sürüm: 1.0.0 (versionCode 1)
Yayıncı: Türkbey Teknoloji Anonim Şirketi

---

## Uygulama adı (en çok 30 karakter)

**TR:** `GÖKTUNGU MAVLink Köprüsü` (24)
**EN:** `GOKTUNGU MAVLink Bridge` (23)

## Kısa açıklama (en çok 80 karakter)

**TR:** `Pixhawk/ArduPilot araçlarını GÖKTUNGU merkez sistemine bağlar.` (63)

**EN:** `Connects Pixhawk/ArduPilot aircraft to the GOKTUNGU central system.` (67)

---

## Tam açıklama (en çok 4000 karakter)

### TR

GÖKTUNGU MAVLink Köprüsü, Pixhawk / ArduPilot tabanlı hava araçlarını
GÖKTUNGU merkez komuta kontrol sistemine bağlayan kurumsal bir köprü
uygulamasıdır. Uygulama, telemetri alıcısına (USB seri / telemetri radyosu)
bağlı Android cihaz üzerinde çalışır ve MAVLink çerçevelerini kendi merkez
sunucunuza UDP üzerinden aktarır; merkezden gelen komutları aynı kanaldan
araca iletir.

Özellikler:
- USB Host üzerinden seri telemetri (CDC-ACM sınıfı Pixhawk/Cube kartlar,
  FTDI, CP210x, CH34x telemetri radyoları)
- MAVLink v1/v2 çerçeve doğrulama ve sistem kimliği takibi
- Merkeze UDP taşıma (varsayılan port 14550), otomatik yeniden bağlanma
- Ön plan hizmeti: ekran kapalıyken de köprü çalışır
- Kurumsal ağ kısıtı: yalnız tanımlı merkez sunucusuna bağlanır
- Türkçe / İngilizce arayüz

Uygulama tek başına uçuş kontrolü sağlamaz; yalnız GÖKTUNGU merkez
sistemine sahip kurumlar için köprü görevi görür.

### EN

GOKTUNGU MAVLink Bridge is an enterprise bridge application that connects
Pixhawk / ArduPilot based aircraft to the GOKTUNGU central command and
control system. It runs on an Android device attached to the telemetry
receiver (USB serial / telemetry radio) and forwards MAVLink frames to your
own central server over UDP; commands from the center are relayed back to
the aircraft over the same channel.

Features:
- Serial telemetry over USB Host (CDC-ACM class Pixhawk/Cube boards, FTDI,
  CP210x, CH34x telemetry radios)
- MAVLink v1/v2 frame validation and system-id tracking
- UDP transport to the center (default port 14550), automatic reconnection
- Foreground service: the bridge keeps running with the screen off
- Enterprise network restriction: connects only to the configured server
- Turkish / English interface

The app does not provide flight control on its own; it is a bridge for
organizations operating the GOKTUNGU central system.

---

## Kategori ve sınıflandırma

- Kategori: Araçlar
- İçerik derecelendirmesi: Herkes
- Reklam: Yok · Uygulama içi satın alma: Yok

## Gizlilik

Uygulama kişisel veri toplamaz. Telemetri yalnız kullanıcının tanımladığı
merkez sunucusuna gönderilir. Gizlilik politikası (Play Console'da zorunlu):
`https://goktungu.com/yasal/gizlilik/`

## Gerekli izinler

- USB Host (telemetri cihazına erişim)
- İnternet (merkeze UDP)
- Ön plan hizmeti (bağlantı sürekliliği)
- Bildirimler (hizmet durumu)
