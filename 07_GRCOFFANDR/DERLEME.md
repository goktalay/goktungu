# GRCOFFANDR — Gömülü GRCOFF Android Uygulaması

Yazılım sahibi: Türkbey Teknoloji A.Ş. · Ürün: GÖKTUNGU · Paket: `com.turkbey.goktungu`

## Mimari

Tam GRCOFF, Android'de tek bir APK içinde çalışır:

- **Arka uç:** GRCOFF Python sunucusu (goktungu paketi) **Chaquopy** ile
  Python 3.11 yorumlayıcısı üzerinde gömülü koşar. Masaüstü GRCOFF'un
  kompozisyon kökü `main.uygulama_kur()` **olduğu gibi** yeniden kullanılır
  (`app/src/main/python/android_sunucu.py` yalnız Android farklarını ayarlar).
- **Arayüz:** Mevcut GRCOFF web arayüzü (Cesium harita, uçuş göstergesi,
  paneller) bir **WebView** içinde, yerel `http://127.0.0.1:8770` sunucusundan
  gösterilir. Arayüz kodu masaüstü ile birebir paylaşılır.
- **Veri:** PostgreSQL yerine cihaz-içi **SQLite** (`filesDir/veri/gcs.db`).
  GRCOFF PG yapılandırması yoksa zaten otomatik SQLite'a düşer; `GOKTUNGU_ANDROID`
  bayrağı ayrıca PG kurulum sihirbazını bastırır.

## Paylaşılan kaynak koddaki Android kancaları (masaüstünde inert)

Hepsi yalnız `GOKTUNGU_ANDROID` / `GOKTUNGU_WEB_KOKU` ortam değişkenleriyle
tetiklenir; masaüstü ve merkez kurulumlarında bu değişkenler tanımsızdır,
davranış değişmez.

| Dosya | Değişiklik |
|---|---|
| `goktungu/sabitler.py` | `GOKTUNGU_WEB_KOKU` ile web kökü geçersiz kılınabilir |
| `goktungu/sunucu.py` | `pg_durum` yanıtına `sihirbaz_kapali` (Android'de PG sihirbazı yok) |
| `js/pg_sihirbaz.js` | `sihirbaz_kapali` gelince sihirbaz açılmaz (`index.html` ?v=v24256) |

## Derleme sırasında çözülen Android'e özgü engeller

Masaüstünde görünmeyen, gerçek derlemenin ortaya çıkardığı engeller:

| Engel | Neden | Çözüm |
|---|---|---|
| fastcrc (Rust) + lxml (C) | pymavlink bağımlılığı, Chaquopy yerel kod derleyemez | pip `--no-deps` (çalışma anında zorunlu değil) |
| pymavlink `dfindexer` (C uzantısı) | sdist derlerken C derlemesi | `PYMAVLINK_FAST_INDEX=0` (saf-Python yedeği) |
| websockets eksik | WS sunucusu için zorunlu | pip'e eklendi (`websockets==17.0.1`) |
| Kotlin "state lock" hatası | Chaquopy + `org.gradle.parallel=true` + in-process Kotlin | `org.gradle.parallel=false` |
| Daemon çökmesi (dex birleştirme) | OpenJ9 iz motoru "traceassert" (D8/R8 yükü, Chaquopy büyük dex) | `-Xtrace:none` (javacore ile teşhis) |

Not: `PYMAVLINK_FAST_INDEX=0` derleme betiğinde `docker run -e` ile, diğerleri
`app/build.gradle` ve `gradle.properties` içinde kalıcıdır. `buildPython` için
`android-build:chaquopy` imgesi (OpenJ9 + Python 3.11) kullanılır.

İlk başarılı debug APK: **112 MB** (Chaquopy Python 3.11 dört ABI + 36 MB Cesium
arayüzü + numpy/pymavlink + goktungu backend). Paket `com.turkbey.goktungu`,
yatay + tablet-only doğrulandı.

## Derleme

```bash
# 1) Gömülü varlıkları GRCOFF kaynağından hazırla (her derleme öncesi)
cd 07_GRCOFFANDR/KAYNAK
bash gomulu_hazirla.sh /root/grcoff_2528_build/src
#    -> app/src/main/python/  (main.py + goktungu, ~2.5M, m50_sdk hariç)
#    -> app/src/main/assets/web/  (Cesium + js/css/models, ~38M)

# 2) Chaquopy derleme imgesi (bir kez): android-build:j9 + Python 3.11
#    scratchpad/Dockerfile.chaquopy -> android-build:chaquopy

# 3) APK derle (Chaquopy buildPython = /usr/bin/python3.11)
docker run --rm --init --network host \
  -v $(pwd):/build -v /root/.gradle_android:/root/.gradle \
  -e GRADLE_USER_HOME=/root/.gradle -w /build android-build:chaquopy \
  bash -c "./gradlew --no-daemon --console=plain --max-workers=2 assembleRelease"

# 4) İmzala (Türkbey keystore) — köprülerdeki apk_imzala.sh akışı
```

## USB seri MAVLink girişi (çözüldü)

pymavlink Android'de USB aygıtını doğrudan açamaz (`/dev/tty*` yok). Çözüm
bir **USB↔TCP köprüsü**:

- `usb/UsbSeri.kt` — Android USB Host sürücüsü (CDC-ACM / FTDI / CP210x /
  CH34x), MAVLink köprü uygulamasından (05_BRDAND) taşındı.
- `usb/UsbMavKoprusu.kt` — USB baytlarını `127.0.0.1:5760` TCP sunucusuna
  çift yönlü köprüler. `ArkaUcServisi` başlatır; aygıt takılınca izin
  isteyip açar.
- `android_sunucu.py` — `tcp:127.0.0.1:5760` bağlantısını Bağlantı
  Yöneticisi'ne otomatik kaydeder. Kullanıcı bir kez "Bağlan"a dokunur;
  pymavlink köprüye bağlanır, USB telemetrisi akar.

## Çevrimdışı harita döşemeleri (mimari mevcut)

Zaten çalışıyor: Cesium `/tile/<kaynak>/{z}/{x}/{y}`'yi yerel sunucudan ister;
`tile_cache.tile_getir` önce disk önbelleğinden (`filesDir/harita_cache`)
sunar, yoksa `urllib` ile çevrimiçi çekip önbelleğe yazar. Kullanıcı
uygulama içindeki "harita önbelleği indir" ile operasyon bölgesini
önceden indirir; sonra çevrimdışı çalışır. **Üçüncü-parti döşemeler APK'ye
GÖMÜLMEZ** (esri/google yeniden dağıtım lisansı); döşemeler cihaz-başına
önbelleğe indirilir.

## Kalan sınırlamalar

1. **Sanal dron (SITL):** Android ARM'da ArduPilot ikilisi yok; sanal dron
   özelliği düşer (ilgili çağrılar zararsızca başarısız olur).
2. **Video (cv2):** OpenCV Chaquopy'de gömülü değil; video özellikleri
   kapalı (tembel import, kendi thread'inde sessizce devre dışı).
3. **Cihazda çalışma-anı testi:** goktungu modüllerinden birinin tembel
   olarak Chaquopy'de olmayan bir paketi import etmesi ihtimali bir
   tablette doğrulanmalı.
