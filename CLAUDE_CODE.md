# Claude Code Çalışma Yönergesi — GÖKTUNGU Teknik Teslimi

Bu arşivde çalışmaya başlamadan önce sırayla `00_BASLANGIC/README.md`, `13_DOKUMANTASYON/SISTEM_DEVIR_REHBERI.md`, `GEMINI.md` ve bu dosyayı okuyun. Kaynaklar üretimden alınmış bir anlık görüntüdür; çalışma verileri, gizli anahtarlar, parolalar ve müşteri verisi bilerek arşivde değildir.

## Ürün sınırları

| Kod | Sınır |
|---|---|
| GRCOFF | Çevrimdışı merkezdir. Yerel kamera, yerel görüntüleyici ve yerel AI yalnız burada bulunur. |
| GRCON | Çevrimiçi merkez/sunucudur. GRCOFF kamera paneli veya offline AI menüsü GRCON’a geri taşınmaz. |
| BRDIMG + BRDTLM | Ortak köprü çekirdeğini paylaşır. Birindeki değişiklik diğerinde regresyon riski yaratır. |
| GRCCMP/GRCADM/GRCWEB | Aynı web ağacından ayrıştırılmış yüzlerdir; ortak JS/CSS bağımlılıklarını kontrol edin. |

## Zorunlu çalışma sırası

1. İlgili ürün dizinini ve mevcut testleri inceleyin; geniş çaplı toplu yeniden yazım yapmayın.
2. Değişikliği küçük ve geri alınabilir tutun. Yeni dosyanın paket beyaz listesinde veya dağıtım ağacında yer aldığını doğrulayın.
3. Python için `py_compile`, JavaScript için `node --check` ve ürün testlerini çalıştırın.
4. Paket oluşturulacaksa Linux ve Windows üretimini aynı kaynak revizyonundan yapın.
5. Paket SHA-256 değerlerini kaydedin; paket içeriğini Linux/Windows için ayrı doğrulayın.
6. Üretim katalog yayını, sadece kullanıcı açıkça istediğinde ve önceki adımların kanıtı mevcutsa yapılır.
7. Yayından sonra servis hesabının dosyayı okuyabildiğini, katalog satırlarının doğru `app_surum` taşıdığını ve güncelleme ucunun doğru sürümü döndürdüğünü doğrulayın.

## GRCOFF 2.5.20 kritik sözleşmeler

- Kamera paneli `X` düğmesi ortak `menubar.js` görünürlük sözleşmesiyle kapanır.
- Kamera Play ve harita küçük önizlemesi aynı yüzen görüntü penceresini açar.
- Kamera-dron bağı mevcut `dron_uid` alanıdır; yeni paralel kimlik alanı yaratmayın.
- Yerel AI yalnız `insan`, `kara_araci`, `hava_araci` sınıflarını üretir.
- Pasif takip olayı yalnız yerel NDJSON/konsol kayıt katmanıdır. `track_verisi_dinleyici.py` salt-okunur örnektir.
- Paketleme dosyasında yeni dinleyici beyaz liste ve zorunlu içerik denetimine eklenmiştir.

## Yasaklı teslim içerikleri

Özel anahtar, imza anahtarı, parolalı servis yapılandırması, müşteri veritabanı dökümü, kullanıcı logları, canlı kamera görüntüleri veya çalışma önbelleği eklemeyin. `.env.example` ya da anahtarsız yapılandırma şablonu kullanılabilir.

## İlk inceleme noktaları

| Amaç | Dosya/Dizin |
|---|---|
| GRCOFF paket/arayüz | `01_GRCOFF/KAYNAK/` |
| GRCOFF testleri | `12_TESTLER/GRCOFF/` |
| GRCON çekirdek | `02_GRCON/MERKEZ_PYTHON/` |
| PostgreSQL aktarımı | `02_GRCON/POSTGRESQL_AKTARIM/` |
| Köprü ortak çekirdeği | `03_BRDIMG/ORTAK_KOPRU_KAYNAGI/` |
| Kurumsal panel | `07_GRCCMP/KAYNAK/` |
| Yönetim paneli | `08_GRCADM/KAYNAK/` |
| Tanıtım sitesi | `09_GRCWEB/KAYNAK/` |

Tüm mimari bağlam için `13_DOKUMANTASYON/SISTEM_DEVIR_REHBERI.md` tek başvuru belgesidir.
