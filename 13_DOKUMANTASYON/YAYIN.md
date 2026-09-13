# GÖKTUNGU Yayın Rehberi (GRCOFF katalog)

Bir GRCOFF paketinin müşteri panelinde indirilebilir olması için **katalog yayını** yapılır. Yayın **üretim (AlmaLinux dağıtım/katalog) hostunda root** olarak, doğrulanmış build çıktısı elde varken yapılır.

## Akış

1. **Derle** (bkz. `DERLEME.md`) → `.deb` + `.exe` ve her ikisinin **SHA-256** değeri.
2. Yayın aracını hazırla: `10_ORTAK_ARACLAR/grcoff_<paket>_katalog_yayinla_*.py`. SHA-256 sabitleri **elle girilir**; placeholder kaldıkça betik çalışmayı reddeder (**kör yayın yok**).
3. İki dosyayı `STAGING` dizinine koy.
4. Betiği root ile çalıştır: preflight SHA doğrulaması → `mk_depo.paket_ekle` → `app_surum` güncelle → Ed25519 imza doğrulaması → depo dosyası/katalog tutarlılığı → depo izni (`0755`, `root:root`).
5. Yayından sonra doğrula: güncelleme ucu yeni sürümü **ilk aday** döndürüyor mu; müşteri paneli sürümü gösteriyor mu.

## Kapılar

| Kapı | Denetim |
|---|---|
| Kaynak | `py_compile`, `node --check`, ilgili regresyonlar geçer |
| Paket | `.deb` `dpkg-deb`, `.exe` arşiv/PE denetimi; dinleyici, AI kaynakları, arayüz dosyaları pakette |
| Bütünlük | İki dosyanın SHA-256'sı; Ed25519 imzası katalogda doğrulanır |
| Katalog | Doğru `urun=gcs`, sürüm, platform, `app_surum`, kanal, dosya boyutu |
| Erişim | Depo dizini servis hesabınca okunur/geçilebilir; `>= 0755` |
| İstemci | Güncelleme ucu Windows ve Linux için yeni sürümü ilk aday döndürür |

## İmza ve anahtarlar

- Ed25519 imza üretim hostunda üretilir: `mk_depo.py::imzala()`.
- Özel anahtar (`.../veri/imza/goktungu_imza_gizli.pem`) **hiçbir zaman** depoya, ZIP'e veya build kutusuna kopyalanmaz.
- İmzalanan içerik: `urun|surum|platform|paket_tur|sha256|boyut` bağlamı (bkz. `mk_depo.py`).

## `asgari_surum` tuzağı

`mk_depo.guncelleme_kontrol`, istemcinin bildirdiği **paket** sürümünü `asgari_surum` ile kıyaslar. 2.5.20/2.5.21 kurulumları sabit sürüm kusuru yüzünden kendini "2.5.19" bildirir; asgari sürümü 2.5.21+ verirsen bu kurulumlar yeni sürümü **hiç göremez**. 2.5.22+ yayın araçlarında `ASGARI_SURUM = None` bu yüzdendir.

## Panelde ayrı "yayınla" düğmesi yoktur

Katalogdaki en yeni etkin sürüm istemci/panel tarafından otomatik seçilir. Ham SQL ile `surumler` satırı eklemek yetersizdir ve önerilmez — imza, `app_surum` ve izin adımları atlanır.

## Geri alma

Yayın aracı öncesinde katalog yedeği alır (`/opt/goktungu/yedek/grcoff_<paket>_katalog_<zaman>/`). Bir sürümü geri çekmek için ilgili `surumler` satırlarını `etkin=FALSE` yapmak yeterlidir; bir önceki sürüm etkin kaldığı için istemci ona döner.
