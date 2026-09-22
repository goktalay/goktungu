# GÖKTUNGU Teknik Teslim — 12 Eylül 2026

Bu tek ZIP arşivi, erişilebilen GÖKTUNGU kaynaklarını, GRCOFF kaynağını (güncel: paket 2.5.23 / uygulama 2.4.153), yayın/test araçlarını ve Claude Code ile Gemini devralma belgelerini içerir. Ürünler resmi kodlarına göre ayrı klasörlere ayrılmıştır.

## İlk okuma sırası

1. `../13_DOKUMANTASYON/SISTEM_DEVIR_REHBERI.md`
2. `../CLAUDE_CODE.md` veya `../GEMINI.md`
4. Değiştirmek istediğiniz ürünün kaynak klasörü

## Arşiv haritası

| Klasör | İçerik |
|---|---|
| `01_GRCOFF/` | Offline Merkez kaynak ağacı |
| `02_GRCON/` | Online Sunucu kaynakları, systemd tanımları ve PostgreSQL aktarım aracı |
| `03_BRDIMG/` | Görüntü Köprüsü ortak kaynak ağacı |
| `04_BRDTLM/` | Telemetri/Radar Köprüsü kaynak ilişkisi notu |
| `05_BRDAND/` | Android Köprü kaynakları |
| `07_GRCCMP/` | Kurumsal/Müşteri paneli |
| `08_GRCADM/` | Yönetim paneli |
| `09_GRCWEB/` | Tanıtım sitesi |
| `10_ORTAK_ARACLAR/` | Yayın ve yardımcı araçlar |
| `11_PAKETLER/` | Doğrulanmış ikili paketler |
| `12_TESTLER/` | GRCOFF regresyonları |
| `13_DOKUMANTASYON/` | Mimari, devir ve çalışma disiplini |

## Bütünlük denetimi

Arşivi açtıktan sonra kök klasörde aşağıdaki komutla iç bütünlüğü doğrulayın:

Bu depo bir Git deposudur; dosya bütünlüğü Git geçmişiyle izlenir. Paket SHA-256 değerleri `13_DOKUMANTASYON/SURUM_NOTLARI.md` içindedir.

## Dahil edilmeyen içerikler

Arşiv, güvenlik ve veri gizliliği nedeniyle özel anahtarlar, imzalama anahtarları, şifreler, canlı PostgreSQL dökümleri, müşteri verileri, kullanıcı logları, canlı kamera görüntüleri ve çalışma önbelleklerini içermez. Android imzalama için `.jks` dosyası yerine ortamınızdaki güvenli anahtar kasası kullanılmalıdır.

## GRCOFF 2.5.20 paketleri

| Platform | Dosya | SHA-256 |
|---|---|---|
| Linux | `11_PAKETLER/GRCOFF_2.5.20/goktungu-merkez_2.5.20_all.deb` | `c0c29384b6231a3924316cc3b1c26e36d800f66f41808e543117b8fabe3aef79` |
| Windows | `11_PAKETLER/GRCOFF_2.5.20/GOKTUNGU-Merkez-Setup-2.5.20.exe` | `aa2a5a5fe4ef81887ff63e380ac36d107e4f2e0405f3aaefba6cc2c1c635d62e` |

Paketlerin katalog yayını, üretim hizmeti ve müşteri güncelleme ucu için doğrulanmıştır. Ayrıntılı teknik açıklama için `13_DOKUMANTASYON/SISTEM_DEVIR_REHBERI.md` dosyasına başvurun.
