# GRCON PostgreSQL Aktarım ve Şema Katmanı

Bu klasör, GRCON’un PostgreSQL davranışını devralmak, şema/taşıma kodunu incelemek ve kontrollü aktarım hazırlamak için ayrı tutulmuştur. Aynı dosyaların özgün konumları `../APP/goktungu/` ve `../MERKEZ_PYTHON/` altında da bulunur.

| Dosya | Rol |
|---|---|
| `pg.py` | PostgreSQL bağlantı/uyumluluk katmanı ve SQL çalışma yardımcıları |
| `veritabani.py` | Uygulama veri modeli, şema ve kayıt işlemlerinin ana katmanı |
| `db_onarim.py` | Veri/şema bakım ve onarım yardımcıları |
| `mk_db.py` | GRCON merkez veritabanı erişim katmanı |
| `ek_sema_gorunum.py` | Şema/görünüm için ek sunucu tarafı tanımlar |
| `mk_depo.py` | Paket katalog kaydı, Ed25519 imzası ve depo metaverisi işlemleri |

> Bu dosyalar üretim veritabanı dökümü değildir. Gerçek aktarımda hedefe ait bağlantı bilgileri güvenli bir ortam değişkeni veya yetkili gizli yapılandırma üzerinden sağlanmalıdır.

## Güvenli aktarım sırası

Önce kaynak PostgreSQL sunucusundan tutarlı bir `pg_dump` alın ve ayrı test ortamına `pg_restore` ile dönün. Uygulamanın şema sürümünü, tablolardaki çatışma davranışını ve paket kataloğu kayıtlarını test ortamında doğrulayın. Ardından üretim için bakım penceresi, geri dönüş yedeği ve sorgu-tabanlı sonuç denetimi oluşturun.

Parolalar, SSL özel anahtarları, canlı müşteri dökümleri veya üretim bağlantı URI’leri bu klasöre eklenmemelidir.
