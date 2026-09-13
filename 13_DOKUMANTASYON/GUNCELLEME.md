# GÖKTUNGU Dosya Tabanlı Güncelleme (2.5.26+)

Önceki model her güncellemede imzasız bir NSIS `.exe` indirip çalıştırıyordu;
Windows Defender bunu sezgisel olarak (`Trojan:Win32/Sabsik.FL.A!ml`)
karantinaya alıp güncellemeyi `[Errno 22]` ile bozuyordu. 2.5.26'dan itibaren
**arka planda çalışan bir güncelleme servisi** yalnız DEĞİŞEN düz dosyaları
indirir — çalıştırılabilir kurulum indirmez, AV sezgiselini tetiklemez;
yalnız değişen dosyalar indiği için hızlı ve artımlıdır.

## Bileşenler
- **`01_GRCOFF/KAYNAK/goktungu_guncelleyici.py`** — arka plan servisi (gözetmen)
  + güncelleme motoru. Servis `main.py`'yi alt süreç olarak çalıştırır, çökerse
  yeniden başlatır ve güncellemeyi uygular.
- **Sunucu uçları** (`02_GRCON/MERKEZ_PYTHON/mk_sunucu.py`):
  - `POST /api/istemci/dosya_manifesti` — imzalı manifest (en yeni sürüm).
  - `POST /api/istemci/dosya` — tek yönetilen dosyanın baytları.
  İkisi de lisans denetimli (gcs: imzalı merkez lisansı; kopru/video:
  kurulum_uid+gizli).
- **`10_ORTAK_ARACLAR/dosya_manifest_yayinla.py`** — yayın aracı: paket
  ağacından yönetilen dosyaları `depo/gcs_dosya/<app_surum>/` altına kopyalar,
  sha256'larını alır, önceki yayına göre silinecekleri hesaplar, manifesti
  Ed25519 ile imzalar, `GUNCEL` işaretçisini günceller.

## Akış (her güncelleme)
1. Servis katalogtan imzalı manifesti çeker (Ed25519, gömülü açık anahtarla
   doğrulanır; yalnız goktungu.com HTTPS).
2. Yerel dosyalarla karşılaştırır, yalnız sha256'sı farklı olanları indirir,
   her dosyayı sha256 ile doğrular (geçici sahne dizinine).
3. Uygulamayı durdurur → dosyaları ATOMİK yerleştirir (geçici→takas) →
   silinecekleri kaldırır → yeniden başlatır. Herhangi bir adım başarısızsa
   GERİ ALIR.
4. PostgreSQL göçü uygulamanın açılışında (goc.py) koşar.

## Güvenlik
- Manifest Ed25519 imzalı; imza gömülü açık anahtarla doğrulanır.
- Her dosya ayrı sha256 doğrulanır.
- Yönetilen kökler yalnız `assets/`, `ai_modeller/` ve kök `main.py`,
  `requirements.txt`, `goktungu_guncelleyici.py`. `veri/`, lisans, `pg.json`,
  loglar KORUNUR — asla yazılmaz/silinmez.
- Dizin-gezinme (`..`, mutlak yol, sürücü harfi) reddedilir.
- Uygulama atomiktir; hata halinde yedekten geri alınır.

## Geçiş (bir kerelik)
Dosya tabanlı güncelleyici servisini makineye koymak için 2.5.27+ kurulumu
bir kez elle kurulur (imzasız → Defender dışlaması). Sonraki tüm güncellemeler
otomatik ve AV dostudur. Kalıcı çözüm: bootstrap'ı kod imzalamak (Authenticode,
tercihen EV).

## Yayın adımları (özet)
1. `deb_merkez_uret.py` + `setup_merkez_uret.py` ile paketi üret (agac dahil).
2. `dosya_manifest_yayinla.py <agac>` — dosya deposu + imzalı manifest yayınla.
3. (Yalnız geçiş için) katalog `.exe` yayını; sonraki sürümlerde GEREKMEZ.
