# GÖKTUNGU — Google Play Store Yayın Hazırlığı

Yazılım sahibi: **Türkbey Teknoloji Anonim Şirketi**
Ürün adı: **GÖKTUNGU** (korunur)
Belge tarihi: 2026-09-21

---

## 1. Üç uygulama ve paket kimlikleri (çakışma çözüldü)

Play Store paket adını (`applicationId`) kalıcı ve benzersiz kimlik
olarak alır. Aynı adla iki uygulama yayınlanamaz ve aynı cihaza
birlikte kurulamaz. Bu yüzden kimlikler ayrıldı:

| Uygulama | Paket adı | Rol | Durum |
|---|---|---|---|
| GÖKTUNGU (tam uygulama, GRCOFFANDR) | `com.turkbey.goktungu` | Bayrak ürün | İskelet (Chaquopy + WebView) |
| GÖKTUNGU MAVLink Köprüsü (05_BRDAND) | `com.turkbey.goktungu.bridge` | Yardımcı | Hazır (yeniden derleme gerek) |
| GÖKTUNGU DJI Köprüsü (06_BRDDJI) | `com.turkbey.goktungu.dji` | Yardımcı | Hazır (yeniden derleme gerek) |

Not: Köprülerin `applicationId`'leri değiştiği için Play Store'a
girmeden önce yeni kimlikle bir kez daha derlenip imzalanmaları gerekir.
Halihazırda imzalı DJI 1.1.3 APK'sı ESKİ (`com.turkbey.goktungu`) kimliği
taşır; iç katalog için kullanılabilir, Play Store için yeniden derlenir.

---

## 2. Teknik hazırlık — yazılım tarafı (bende)

- [x] Üç paket adı Play Store'da bir arada yayınlanabilir şekilde ayrıldı.
- [x] Hedef API 36 (Android 16) — Play Store 2026 zorunluluğu karşılanıyor.
- [x] 64-bit desteği: köprüler saf Kotlin (tüm ABI), tam uygulama
      Chaquopy `arm64-v8a` içeriyor.
- [ ] Yayın biçimi APK değil **App Bundle (.aab)** olacak
      (`./gradlew bundleRelease`). Play Store yeni uygulamalarda AAB ister.
- [ ] Gizlilik politikası metni (taslağı ben hazırlarım).
- [ ] Mağaza görselleri: 512×512 ikon (amblem var), 1024×500 özellik
      grafiği, en az 2 telefon ekran görüntüsü (taslak sunarım).
- [ ] Mağaza metinleri: kısa açıklama (80 karakter) + tam açıklama.
- [ ] Data Safety + içerik derecelendirme anketi cevap taslakları.

---

## 3. Senin (Türkbey) yapman gerekenler — sadece hesap sahibi yapabilir

Sıralama kritik yola göre; **1. madde en uzun sürer, hemen başlanmalı.**

1. **Google Play Developer hesabı** açılması — Türkbey Teknoloji A.Ş.
   adına **kuruluş (organization)** tipinde. Tek seferlik 25 USD.
   - Kuruluş hesabı için **D-U-N-S numarası** ve **iş/kimlik doğrulaması**
     gerekir. Doğrulama birkaç iş günü sürebilir. Bu adım bitmeden
     hiçbir şey yayınlanamaz.
   - Hesap sahibi e-postası: **muhammed@kaderoglu.com**.

2. **Gizlilik politikası** halka açık bir URL'de yayınlanmalı
   (Türkbey web sitesi veya GÖKTUNGU web). Metni ben yazarım, siz
   yayınlarsınız; URL Play Console'a girilir.

3. **Play App Signing** onayı: Google uygulama imza anahtarını yönetir,
   siz bir "yükleme anahtarı" ile yüklersiniz. Mevcut
   `turkbey_android.jks` yükleme anahtarı olur. Ben paketlerim, siz
   Console'a bir kez yüklersiniz.

4. **Mağaza görsel/metinlerinin onayı**: taslakları hazırlarım, siz
   son metni ve ekran görüntülerini onaylarsınız.

5. **Play Console form onayları**: Data Safety, içerik derecelendirme,
   hedef kitle, izin gerekçeleri (konum, ön plan servisi, USB). Cevap
   taslaklarını ben hazırlarım, işaretlemeyi siz yaparsınız.

---

## 4. Önemli uyarı — savunma uygulaması ve Play Store politikası

GÖKTUNGU angajman ve önleyici (interceptor) güdüm özellikleri içeriyor.
Google Play politikaları şiddeti veya silah kullanımını kolaylaştıran
içeriği kısıtlar. Profesyonel bir dron yer kontrol istasyonu genelde
kabul edilir; ancak **angajman/güdüm** tarafı politika incelemesine
takılabilir ve yayın reddi riski taşır.

Seçenekler:

- **A) Halka açık Play Store**: Angajman özellikleri Play sürümünde
  gizlenip yalnızca yetkili/kurumsal kanaldan açılabilir (askeri sürüm
  ayrı tutulur).
- **B) Managed Google Play (özel/kurumsal dağıtım)**: Uygulama yalnızca
  belirlenen kuruluşlara/kullanıcılara dağıtılır; halka açık listelenmez.
  Savunma müşterileri için genellikle en uygun yol.
- **C) Mevcut iç katalog + doğrudan APK**: Şu anki yöntem; Play Store
  politikası devreye girmez, tam kontrol sizde kalır.

Öneri: Köprüler (MAVLink/DJI) halka açık Play Store'a uygundur. Tam
GÖKTUNGU uygulaması için **B veya C** daha güvenli; halka açık listeleme
istenirse angajman özellikleri kapatılmış bir "sivil" sürüm önerilir.

---

## 5. GRCOFFANDR (tam uygulama) — kalan mühendislik

İskelet mimarisi kuruldu (Chaquopy Python arka uç + WebView arayüz).
Tam gömülü GRCOFF için aşamalı iş:

1. PostgreSQL → SQLite göçü (veritabanı katmanı portu).
2. `goktungu` paketinin `assets/python` altına gömülmesi.
3. Cesium arayüzü + çevrimdışı harita döşemelerinin APK'ye eklenmesi.
4. MAVLink/USB seri köprüsü (Android USB Host).
5. Sanal dron (SITL) kapalı, makro/video kısıtlı (Android sınırları).
