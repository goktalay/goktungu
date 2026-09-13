# GÖKTUNGU — Ajan Çalışma Kuralları

Bu arşiv GÖKTUNGU kaynak teslimidir. İlk olarak `00_BASLANGIC/README.md`, `13_DOKUMANTASYON/SISTEM_DEVIR_REHBERI.md`, `CLAUDE_CODE.md` ve `GEMINI.md` dosyalarını okuyun.

## Değişmez ürün sınırları

- **GRCOFF** offline merkezdir; yerel kamera ve yerel AI yüzeyi yalnız GRCOFF’ta kalır.
- **GRCON** online merkezdir; GRCOFF’a ait kamera/AI paneli GRCON’a taşınmaz.
- **BRDIMG** ve **BRDTLM** ortak köprü çekirdeği kullanır; her değişiklik iki ürün etkisiyle değerlendirilir.
- **GRCCMP**, **GRCADM** ve **GRCWEB** web kaynakları ortak bağımlılık taşıyabilir.

## Zorunlu mühendislik disiplini

1. Küçük, hedefli ve geri alınabilir değişiklik yapın.
2. İlgili Python/JavaScript derleme denetimlerini ve mevcut regresyonları çalıştırın.
3. Yeni paket dosyası ya da kaynak eklenirse paketleme beyaz listesini ve paket içeriğini doğrulayın.
4. Üretim yayını öncesinde SHA-256, Ed25519, ürün, platform, sürüm ve `app_surum` doğrulaması yapın.
5. Paket depo dizinleri servis hesabı için okunabilir/geçilebilir olmalıdır.
6. Sırlar, özel anahtarlar, imza anahtarları, canlı veritabanı dökümleri, kullanıcı logları ve çalışma verileri kaynak arşivine eklenmez.

## GRCOFF 2.5.20 dikkat noktaları

- Kamera `X` kapatma mekanizması `js/menubar.js` ortak panel görünürlüğüyle bağlıdır.
- Play ve dron yanındaki küçük kamera önizlemesi aynı yüzen görüntü penceresini açar.
- Kamera-dron ilişkisi mevcut `dron_uid` alanıdır.
- Yerel AI yalnız `insan`, `kara_araci`, `hava_araci` sınıfları için sonuç üretir.
- Pasif takip verisi yalnız yerel NDJSON/konsol akışıdır; dinleyici örneği salt-okunurdur.

Ayrıntı ve kaynak konumları için teknik devir rehberine başvurun.
