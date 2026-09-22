# Gemini Devralma Bağlamı — GÖKTUNGU

Bu arşiv, GÖKTUNGU ekosisteminin kaynak ve teknik teslim paketidir. Çalışmaya başlamadan önce `00_BASLANGIC/README.md`, `13_DOKUMANTASYON/SISTEM_DEVIR_REHBERI.md` ve `CLAUDE_CODE.md` dosyalarını okuyun. Bu dosya, Gemini ile Claude Code’un aynı mühendislik disiplinini izlemesi için eşdeğer yönergeler sağlar.

## Sistem modeli

GÖKTUNGU bileşenleri resmi kodlarıyla yönetilir: GRCOFF (offline merkez), GRCON (online sunucu), BRDIMG (görüntü köprüsü), BRDTLM (telemetri/radar köprüsü), BRDAND (Android köprü), GRCCMP (kurumsal panel), GRCADM (yönetim paneli) ve GRCWEB (tanıtım sitesi).

GRCOFF ile GRCON kesin olarak ayrıdır. Offline yerel kamera/AI yüzeyi yalnız GRCOFF’ta kalır. Çevrimiçi GRCON’a offline kamera menüsü veya yerel AI popup’ı eklenmemelidir. BRDIMG ve BRDTLM aynı köprü çekirdeğini paylaşır; değişiklikler ikili regresyon gerektirir.

## En önemli güncel sürüm: GRCOFF 2.5.20

| Konu | Sözleşme |
|---|---|
| Platform | Linux `.deb` ve Windows `.exe` aynı kaynak revizyonundan üretilir. |
| Uygulama sürümü | 2.4.150 |
| Kamera görüntüleme | Play ve harita önizlemesi ortak yüzen pencereyi açar. |
| Dron bağı | Sadece mevcut `dron_uid` kullanılır. |
| AI sınıfları | `insan`, `kara_araci`, `hava_araci` dışında sonuç yayınlanmaz. |
| Takip verisi | Yerel NDJSON ve konsol olayları; örnek dinleyici yalnız okur. |

## Gemini çalışma kuralları

1. Değişiklikten önce hedef dosyaları, çağıran tarafları ve testleri inceleyin.
2. Yeni ürün/kimlik modeli oluşturmadan mevcut sözleşmeyi genişletin.
3. Kod yazdıktan sonra Python ve JavaScript sözdizim denetimlerini çalıştırın; sonuçları belgelendirin.
4. Paket üretimi sonrası yalnız dosya varlığını değil, paketin içeriğini de kontrol edin.
5. Katalog yayınında dosya SHA-256, Ed25519 imzası, platform, ürün, sürüm ve `app_surum` değerleri birlikte doğrulanmalıdır.
6. Üretim paket dizinlerinin servis hesabınca okunabildiğini doğrulayın; dizin izni hataları müşteri panelinde paket görünmeme kusuruna yol açabilir.
7. Sırları, özel anahtarları, imzalama anahtarlarını, canlı veritabanı dökümlerini, kullanıcı loglarını ve çalışma önbelleklerini repoya eklemeyin.

## Başlangıç konumları

| İhtiyaç | Konum |
|---|---|
| Genel teknik mimari | `13_DOKUMANTASYON/SISTEM_DEVIR_REHBERI.md` |
| GRCOFF | `01_GRCOFF/KAYNAK/` |
| GRCON/Python | `02_GRCON/MERKEZ_PYTHON/` |
| PostgreSQL aktarımı | `02_GRCON/POSTGRESQL_AKTARIM/` |
| Köprü kaynakları | `03_BRDIMG/ORTAK_KOPRU_KAYNAGI/` |
| Android kaynakları | `05_BRDAND/KAYNAK/` |
| Web kaynakları | `07_GRCCMP/`, `08_GRCADM/`, `09_GRCWEB/` |
| Testler | `12_TESTLER/` |
| Paket örnekleri | `11_PAKETLER/` |

Bir çalışma bloğunun sonunda, değiştirilmiş dosyaları, çalıştırılan testleri, paket etkisini, geri dönüş yöntemini ve açık riskleri kısa bir Markdown raporuyla kaydedin.
