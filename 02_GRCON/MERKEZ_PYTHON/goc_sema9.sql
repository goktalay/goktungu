-- =====================================================================
-- GÖKTUNGU MERKEZ — şema göçü 9
--
-- İKİ İŞ YAPAR
--   A) Gelir modeli yenilenmesi (brifing: GOKTUNGU_Gelir_Modeli, Ağu 2026)
--      + iyzico ödeme altyapısı + kiracı bazında iskonto
--   B) Destek sistemi tablolarının EKSİK şema tanımı
--
-- (B) NEDEN BURADA: Ölçümde `destek_talepleri`, `destek_mesajlari`,
-- `destek_ekleri` tablolarının veritabanında VAR olduğu ama hiçbir
-- şema/göç dosyasında `CREATE TABLE` tanımının BULUNMADIĞI saptandı.
-- Tablolar elle uygulanmış, şema sürümü de elle 8'e çıkarılmış.
-- Sonuç: sıfırdan kurulumda ticket sistemi sessizce çöker. Bu göç
-- tanımları kalıcı hale getirir. Mevcut tablolara DOKUNMAZ
-- (`IF NOT EXISTS`), yalnız yoksa oluşturur.
--
-- SÜRÜM NUMARASI NEDEN 9: veritabanı `sema_surum.surum = 8` diyor,
-- ancak diskte `goc_sema8.sql` YOK. 8 numarası tüketilmiş sayılır.
--
-- İDEMPOTENT: bu betik birden çok kez çalıştırılabilir. Yarım kalan
-- göç yeniden çalıştırılarak tamamlanabilir.
-- =====================================================================

BEGIN;

-- =====================================================================
-- BÖLÜM A — GELİR MODELİ
-- =====================================================================

-- ---------------------------------------------------------------------
-- A1. paketler — SaaS paketleri ve lisans SKU'ları (TEK DOĞRULUK KAYNAĞI)
--
-- NEDEN TABLO: brifing "paketler veritabanında tanımlı nesne olur;
-- fiyat ve kapsam kodda sabitlenmez". Fiyat değişikliği kod dağıtımı
-- gerektirmemeli.
--
-- NEDEN İKİ PARA BİRİMİ: iyzico belgelenmiş kısıt — "yabancı para
-- biriminde sadece yabancı kart kullanılabilir". Türk müşteri USD
-- planına Türk kartıyla abone OLAMAZ. Her paketin TRY ve USD fiyatı
-- ayrı tutulur; müşteri ülkesine göre plan seçilir.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS paketler (
  paket_id        BIGSERIAL PRIMARY KEY,
  anahtar         TEXT NOT NULL,
  ad_tr           TEXT NOT NULL,
  ad_en           TEXT NOT NULL,
  -- 'saas'   : yinelenen abonelik (aylık/yıllık)
  -- 'lisans' : tek seferlik kapalı devre SKU
  -- 'modul'  : satılmaz, yalnız üst yönetici tahsis eder
  -- 'hizmet' : eğitim/kalibrasyon, teklif bazlı
  tur             TEXT NOT NULL,
  aylik_usd       NUMERIC(12,2),
  aylik_try       NUMERIC(12,2),
  tek_usd         NUMERIC(12,2),
  tek_try         NUMERIC(12,2),
  -- `koltuk_basina = true` → fiyat KOLTUK BAŞINA (Profesyonel
  -- 29 USD/pilot/ay). Bu durumda `koltuk` alanı 1 kabul edilir.
  koltuk          INTEGER NOT NULL DEFAULT 0,
  koltuk_basina   BOOLEAN NOT NULL DEFAULT FALSE,
  koltuk_sinirsiz BOOLEAN NOT NULL DEFAULT FALSE,
  ai_dahil        BOOLEAN NOT NULL DEFAULT FALSE,
  radar_dahil     BOOLEAN NOT NULL DEFAULT FALSE,
  gccdual_dahil   BOOLEAN NOT NULL DEFAULT FALSE,
  -- Yıllık bakım oranı (lisans SKU'larında 0.18 = %18)
  bakim_orani     NUMERIC(5,4),
  -- Fiyat "başlangıç/taban" değeri mi? (120.000+ USD gibi)
  fiyat_tabani    BOOLEAN NOT NULL DEFAULT FALSE,
  satilabilir     BOOLEAN NOT NULL DEFAULT TRUE,
  -- Yalnız üst sistem yöneticisi (veilox) tanımlayabilir mi?
  yalniz_ust      BOOLEAN NOT NULL DEFAULT FALSE,
  -- Miras (kaldırılmış) plan? Yeni müşteriye gösterilmez, mevcut
  -- aboneler sözleşme bitimine kadar yaşar.
  miras           BOOLEAN NOT NULL DEFAULT FALSE,
  ucretsiz        BOOLEAN NOT NULL DEFAULT FALSE,
  sira            INTEGER NOT NULL DEFAULT 0,
  aciklama_tr     TEXT,
  aciklama_en     TEXT,
  -- iyzico karşılıkları (plan oluşturulunca doldurulur)
  iyz_urun_ref         TEXT,
  iyz_plan_ref_ay_try  TEXT,
  iyz_plan_ref_yil_try TEXT,
  iyz_plan_ref_ay_usd  TEXT,
  iyz_plan_ref_yil_usd TEXT,
  durum           TEXT NOT NULL DEFAULT 'etkin',
  olusma_ts       TIMESTAMPTZ NOT NULL DEFAULT now(),
  guncel_ts       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Kısıtlar ayrı eklenir: tablo zaten varsa `CREATE TABLE IF NOT EXISTS`
-- gövdedeki kısıtları uygulamaz.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='paket_anahtar_tekil') THEN
    ALTER TABLE paketler ADD CONSTRAINT paket_anahtar_tekil UNIQUE (anahtar);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='paket_tur_ck') THEN
    ALTER TABLE paketler ADD CONSTRAINT paket_tur_ck
      CHECK (tur IN ('saas','lisans','modul','hizmet'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='paket_durum_ck') THEN
    ALTER TABLE paketler ADD CONSTRAINT paket_durum_ck
      CHECK (durum IN ('etkin','pasif'));
  END IF;
  -- Ücretsiz paketin fiyatı olmamalı; olursa arayüz "0,00/ay" gösterir
  -- ve ücretsizlik mesajı kaybolur.
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='paket_ucretsiz_ck') THEN
    ALTER TABLE paketler ADD CONSTRAINT paket_ucretsiz_ck
      CHECK (NOT ucretsiz OR (coalesce(aylik_usd,0)=0 AND coalesce(aylik_try,0)=0
                              AND coalesce(tek_usd,0)=0 AND coalesce(tek_try,0)=0));
  END IF;
  -- Sınırsız koltuk ile koltuk-başına fiyatlama birlikte anlamsızdır.
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='paket_koltuk_ck') THEN
    ALTER TABLE paketler ADD CONSTRAINT paket_koltuk_ck
      CHECK (NOT (koltuk_sinirsiz AND koltuk_basina));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_paketler_tur ON paketler (tur, durum, sira);

-- ---------------------------------------------------------------------
-- A2. iskontolar — kiracı bazında özel indirim (kullanıcı talebi)
--
-- Bu mekanizma "miras plan" ihtiyacını da karşılar: eski abone yeni
-- pakete geçirilip farkı kapatan süresiz iskonto tanımlanabilir.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS iskontolar (
  iskonto_id      BIGSERIAL PRIMARY KEY,
  firma_id        BIGINT NOT NULL
                    REFERENCES firmalar(firma_id) ON DELETE CASCADE,
  -- NULL = firmanın tüm paketlerine uygulanır
  paket_anahtar   TEXT,
  tur             TEXT NOT NULL,
  deger           NUMERIC(12,2) NOT NULL,
  -- 'tutar' türünde hangi para biriminde indirim yapıldığı
  para_birimi     TEXT,
  gecerli_bas     DATE NOT NULL DEFAULT CURRENT_DATE,
  gecerli_bit     DATE,
  gerekce         TEXT,
  veren_yonetici_id BIGINT,
  durum           TEXT NOT NULL DEFAULT 'etkin',
  olusma_ts       TIMESTAMPTZ NOT NULL DEFAULT now()
);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='iskonto_tur_ck') THEN
    ALTER TABLE iskontolar ADD CONSTRAINT iskonto_tur_ck
      CHECK (tur IN ('yuzde','tutar'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='iskonto_durum_ck') THEN
    ALTER TABLE iskontolar ADD CONSTRAINT iskonto_durum_ck
      CHECK (durum IN ('etkin','iptal'));
  END IF;
  -- Yüzde 100'ü geçemez; geçse negatif fiyat üretirdi.
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='iskonto_deger_ck') THEN
    ALTER TABLE iskontolar ADD CONSTRAINT iskonto_deger_ck
      CHECK ((tur='yuzde' AND deger > 0 AND deger <= 100)
          OR (tur='tutar' AND deger > 0));
  END IF;
  -- Tutar iskontosunda para birimi ZORUNLU; yoksa yanlış birimde
  -- uygulanır (10 USD indirim 10 TRY sanılabilir).
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='iskonto_birim_ck') THEN
    ALTER TABLE iskontolar ADD CONSTRAINT iskonto_birim_ck
      CHECK (tur <> 'tutar' OR para_birimi IN ('USD','TRY'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='iskonto_tarih_ck') THEN
    ALTER TABLE iskontolar ADD CONSTRAINT iskonto_tarih_ck
      CHECK (gecerli_bit IS NULL OR gecerli_bit >= gecerli_bas);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_iskontolar_firma
  ON iskontolar (firma_id, durum);

-- ---------------------------------------------------------------------
-- A3. firmalar — yeni kolonlar
-- ---------------------------------------------------------------------
ALTER TABLE firmalar
  ADD COLUMN IF NOT EXISTS paket_anahtar TEXT,
  -- BAKIM KAPISI: NULL = bakım kapsamı yok. Bakımı biten kurum
  -- ÇALIŞMAYA DEVAM EDER; yalnız güncelleme alamaz.
  ADD COLUMN IF NOT EXISTS bakim_bitis DATE,
  -- Başarısız ödeme akışı: 3 deneme + 7 gün ödemesiz dönem
  ADD COLUMN IF NOT EXISTS odeme_deneme INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS odemesiz_bitis DATE,
  -- Ödemesiz dönem de bittiyse koltuklar salt-okunur olur; VERİ SİLİNMEZ.
  ADD COLUMN IF NOT EXISTS salt_okunur BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS para_birimi TEXT NOT NULL DEFAULT 'TRY',
  ADD COLUMN IF NOT EXISTS iyz_abonelik_ref TEXT,
  ADD COLUMN IF NOT EXISTS iyz_musteri_ref TEXT,
  -- iyzico müşteri kaydı TCKN/VKN zorunlu tutuyor (Stripe'ta yoktu)
  ADD COLUMN IF NOT EXISTS kimlik_no TEXT;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conname='firma_para_birimi_ck') THEN
    ALTER TABLE firmalar ADD CONSTRAINT firma_para_birimi_ck
      CHECK (para_birimi IN ('TRY','USD'));
  END IF;
END $$;

-- ---------------------------------------------------------------------
-- A4. abonelik_kalemleri — TRY desteği ve paket bağı
--
-- Mevcut `birim_usd`/`toplam_usd` KORUNUR (geçmiş kayıt bozulmasın).
-- Yeni kayıtlar `para_birimi` + `birim_tutar` kullanır.
-- ---------------------------------------------------------------------
ALTER TABLE abonelik_kalemleri
  ADD COLUMN IF NOT EXISTS paket_anahtar TEXT,
  ADD COLUMN IF NOT EXISTS para_birimi TEXT NOT NULL DEFAULT 'USD',
  ADD COLUMN IF NOT EXISTS birim_tutar NUMERIC(12,2),
  ADD COLUMN IF NOT EXISTS toplam_tutar NUMERIC(12,2),
  -- Uygulanan iskonto izi (denetim için)
  ADD COLUMN IF NOT EXISTS iskonto_tutar NUMERIC(12,2) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS iskonto_id BIGINT;

UPDATE abonelik_kalemleri
   SET birim_tutar = birim_usd, toplam_tutar = toplam_usd
 WHERE birim_tutar IS NULL;

-- ---------------------------------------------------------------------
-- A5. Sağlayıcı bağımsız ödeme tabloları
--
-- Stripe tabloları SİLİNMEZ (geçmiş kayıt). Yeni tablolar `saglayici`
-- kolonu taşır; gelecekte sağlayıcı değişimi şemayı kırmaz.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS odeme_oturumlari (
  oturum_id       BIGSERIAL PRIMARY KEY,
  saglayici       TEXT NOT NULL DEFAULT 'iyzico',
  firma_id        BIGINT REFERENCES firmalar(firma_id) ON DELETE SET NULL,
  paket_anahtar   TEXT,
  adet            INTEGER NOT NULL DEFAULT 1,
  donem           TEXT NOT NULL DEFAULT 'aylik',
  para_birimi     TEXT NOT NULL DEFAULT 'TRY',
  tutar           NUMERIC(12,2),
  saglayici_jeton TEXT,
  konusma_id      TEXT,
  abonelik_ref    TEXT,
  durum           TEXT NOT NULL DEFAULT 'bekliyor',
  hata_kodu       TEXT,
  hata_mesaji     TEXT,
  ip              TEXT,
  olusma_ts       TIMESTAMPTZ NOT NULL DEFAULT now(),
  sonuc_ts        TIMESTAMPTZ
);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conname='odeme_oturum_durum_ck') THEN
    ALTER TABLE odeme_oturumlari ADD CONSTRAINT odeme_oturum_durum_ck
      CHECK (durum IN ('bekliyor','basarili','basarisiz','iptal','zaman_asimi'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conname='odeme_oturum_birim_ck') THEN
    ALTER TABLE odeme_oturumlari ADD CONSTRAINT odeme_oturum_birim_ck
      CHECK (para_birimi IN ('TRY','USD','EUR'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_odeme_oturum_firma
  ON odeme_oturumlari (firma_id, olusma_ts DESC);
CREATE INDEX IF NOT EXISTS ix_odeme_oturum_jeton
  ON odeme_oturumlari (saglayici_jeton);

CREATE TABLE IF NOT EXISTS odeme_olaylari (
  olay_id         BIGSERIAL PRIMARY KEY,
  saglayici       TEXT NOT NULL DEFAULT 'iyzico',
  -- Sağlayıcının olay kimliği. TEKRAR İŞLEMEYİ ÖNLER: bildirimler
  -- birden çok kez gelebilir, aynı olayı iki kez işlemek çift koltuk
  -- eklenmesine yol açar.
  saglayici_olay_id TEXT,
  tur             TEXT NOT NULL,
  firma_id        BIGINT REFERENCES firmalar(firma_id) ON DELETE SET NULL,
  abonelik_ref    TEXT,
  govde           JSONB,
  islendi         BOOLEAN NOT NULL DEFAULT FALSE,
  islenme_ts      TIMESTAMPTZ,
  hata            TEXT,
  olusma_ts       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_odeme_olay_saglayici
  ON odeme_olaylari (saglayici, saglayici_olay_id)
  WHERE saglayici_olay_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_odeme_olay_islendi
  ON odeme_olaylari (islendi, olusma_ts);

-- ---------------------------------------------------------------------
-- A6. merkez_lisanslari — SKU, koltuk sınırı, bakım, kiracı kimliği
--
-- Brifing lisans dosyasında şunları istiyor: SKU + modül listesi,
-- koltuk sınırı, bakım bitiş tarihi, kiracı kimliği (VKN + ticaret
-- sicil), donanım bağlama (opsiyonel).
--
-- `govde_surum`: mevcut imzalı lisanslar `surum: 1` gövdesiyle
-- üretildi. Yeni alanlar gövdeye eklenirse imza değişir. Bu yüzden
-- eski lisanslar 1, yeniler 2 olarak işaretlenir; sahadaki kurulumlar
-- kırılmaz.
-- ---------------------------------------------------------------------
ALTER TABLE merkez_lisanslari
  ADD COLUMN IF NOT EXISTS sku TEXT,
  ADD COLUMN IF NOT EXISTS koltuk_siniri INTEGER,
  ADD COLUMN IF NOT EXISTS koltuk_sinirsiz BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS bakim_bitis DATE,
  ADD COLUMN IF NOT EXISTS vergi_no TEXT,
  ADD COLUMN IF NOT EXISTS ticaret_sicil TEXT,
  ADD COLUMN IF NOT EXISTS donanim_parmak TEXT,
  ADD COLUMN IF NOT EXISTS govde_surum INTEGER NOT NULL DEFAULT 1;

-- =====================================================================
-- BÖLÜM B — DESTEK SİSTEMİ ŞEMASI (eksik tanım kalıcılaştırma)
--
-- Bu tablolar canlıda VAR ama şema dosyalarında tanımı YOK. Sıfırdan
-- kurulumda oluşmuyorlar ve ticket sistemi sessizce çöküyor.
-- Tanımlar canlı veritabanından ölçülerek buraya alındı.
-- `citext` uzantısı taban şemada zaten etkinleştirilmiş.
-- =====================================================================
CREATE TABLE IF NOT EXISTS destek_talepleri (
  ticket_id       BIGSERIAL PRIMARY KEY,
  ticket_no       TEXT NOT NULL,
  firma_id        BIGINT REFERENCES firmalar(firma_id) ON DELETE SET NULL,
  kullanici_id    BIGINT REFERENCES kullanicilar(kullanici_id) ON DELETE SET NULL,
  acan_eposta     CITEXT NOT NULL,
  acan_ad         TEXT NOT NULL DEFAULT '',
  modul           TEXT NOT NULL,
  konu            TEXT NOT NULL,
  aciklama        TEXT NOT NULL,
  oncelik         TEXT NOT NULL DEFAULT 'normal',
  durum           TEXT NOT NULL DEFAULT 'yeni',
  atanan_yonetici_id BIGINT
                    REFERENCES sistem_yoneticileri(yonetici_id) ON DELETE SET NULL,
  son_yanit_ts    TIMESTAMPTZ,
  kapanma_ts      TIMESTAMPTZ,
  olusma_ts       TIMESTAMPTZ NOT NULL DEFAULT now(),
  guncel_ts       TIMESTAMPTZ NOT NULL DEFAULT now()
);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conname='destek_talepleri_no_tekil') THEN
    ALTER TABLE destek_talepleri
      ADD CONSTRAINT destek_talepleri_no_tekil UNIQUE (ticket_no);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conname='destek_talepleri_durum_check') THEN
    ALTER TABLE destek_talepleri ADD CONSTRAINT destek_talepleri_durum_check
      CHECK (durum IN ('yeni','islemde','yanit_bekliyor','cozuldu','kapandi'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conname='destek_talepleri_modul_check') THEN
    ALTER TABLE destek_talepleri ADD CONSTRAINT destek_talepleri_modul_check
      CHECK (modul IN ('app','kopru','merkez','radar','gccdual','dji','ai',
                       'video','kurumsal_panel','yonetim_paneli','odeme',
                       'kurulum','diger'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conname='destek_talepleri_oncelik_check') THEN
    ALTER TABLE destek_talepleri ADD CONSTRAINT destek_talepleri_oncelik_check
      CHECK (oncelik IN ('dusuk','normal','yuksek','kritik'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS destek_talepleri_durum_ix
  ON destek_talepleri (durum, olusma_ts DESC);
CREATE INDEX IF NOT EXISTS destek_talepleri_firma_ix
  ON destek_talepleri (firma_id, olusma_ts DESC);
CREATE INDEX IF NOT EXISTS destek_talepleri_kullanici_ix
  ON destek_talepleri (kullanici_id, olusma_ts DESC);

CREATE TABLE IF NOT EXISTS destek_mesajlari (
  mesaj_id        BIGSERIAL PRIMARY KEY,
  ticket_id       BIGINT NOT NULL
                    REFERENCES destek_talepleri(ticket_id) ON DELETE CASCADE,
  yazan_tur       TEXT NOT NULL,
  yazan_id        BIGINT,
  yazan_ad        TEXT NOT NULL DEFAULT '',
  govde           TEXT NOT NULL,
  ic_not          BOOLEAN NOT NULL DEFAULT FALSE,
  olusma_ts       TIMESTAMPTZ NOT NULL DEFAULT now()
);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conname='destek_mesajlari_yazan_check') THEN
    ALTER TABLE destek_mesajlari ADD CONSTRAINT destek_mesajlari_yazan_check
      CHECK (yazan_tur IN ('kullanici','personel','sistem'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS destek_mesajlari_ticket_ix
  ON destek_mesajlari (ticket_id, olusma_ts);

CREATE TABLE IF NOT EXISTS destek_ekleri (
  ek_id           BIGSERIAL PRIMARY KEY,
  ticket_id       BIGINT NOT NULL
                    REFERENCES destek_talepleri(ticket_id) ON DELETE CASCADE,
  mesaj_id        BIGINT
                    REFERENCES destek_mesajlari(mesaj_id) ON DELETE CASCADE,
  dosya_ad        TEXT NOT NULL,
  mime            TEXT NOT NULL DEFAULT 'application/octet-stream',
  boyut           BIGINT NOT NULL DEFAULT 0,
  disk_yol        TEXT NOT NULL,
  sha256          TEXT,
  olusma_ts       TIMESTAMPTZ NOT NULL DEFAULT now()
);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conname='destek_ekleri_boyut_check') THEN
    ALTER TABLE destek_ekleri ADD CONSTRAINT destek_ekleri_boyut_check
      CHECK (boyut >= 0);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS destek_ekleri_ticket_ix
  ON destek_ekleri (ticket_id);

-- =====================================================================
-- BÖLÜM C — TOHUM VERİ (paketler)
--
-- `ON CONFLICT DO NOTHING`: göç tekrar çalışırsa elle değiştirilmiş
-- fiyatlar EZİLMEZ. Fiyat güncellemesi ayrı bir yönetim işlemidir.
--
-- TRY fiyatları kura ENDEKSLENMEZ: iyzico'da plan fiyatı
-- güncellenemiyor (yalnız ad ve deneme süresi). Kura endekslersek her
-- kur hareketinde yeni plan açmak gerekirdi.
-- =====================================================================

-- KATMAN 1: SaaS paketleri
INSERT INTO paketler (anahtar, ad_tr, ad_en, tur, aylik_usd, aylik_try,
  koltuk, koltuk_basina, ai_dahil, ucretsiz, satilabilir, sira,
  aciklama_tr, aciklama_en)
VALUES
  ('baslangic', 'Başlangıç', 'Starter', 'saas',
   0, 0, 1, FALSE, FALSE, TRUE, TRUE, 10,
   'Tek pilot koltuğu, sınırsız araç. Değerlendirme ve bireysel kullanım için.',
   'Single pilot seat, unlimited vehicles. For evaluation and individual use.'),
  ('profesyonel', 'Profesyonel', 'Professional', 'saas',
   29, 990, 1, TRUE, FALSE, FALSE, TRUE, 20,
   'Pilot başına aylık ücret. Ticari işletmeler için tam harekât yeteneği.',
   'Per pilot per month. Full operational capability for commercial operators.'),
  ('kurumsal_bulut', 'Kurumsal Bulut', 'Enterprise Cloud', 'saas',
   490, 16900, 25, FALSE, TRUE, FALSE, TRUE, 30,
   '25 pilot koltuğu ve yapay zekâ modülü dahildir. Kuruluş başına aylık.',
   'Includes 25 pilot seats and the AI module. Per organization per month.')
ON CONFLICT (anahtar) DO NOTHING;

-- KATMAN 2: Kapalı devre lisans SKU'ları
-- `yalniz_ust = TRUE` → uyum değerlendirmesi sonrası yalnız üst sistem
-- yöneticisi tanımlar. `satilabilir = FALSE` → sepete atılamaz.
INSERT INTO paketler (anahtar, ad_tr, ad_en, tur, tek_usd,
  koltuk, koltuk_sinirsiz, ai_dahil, radar_dahil, gccdual_dahil,
  bakim_orani, fiyat_tabani, satilabilir, yalniz_ust, sira,
  aciklama_tr, aciklama_en)
VALUES
  ('GTU-MERKEZ', 'Merkez Lisansı', 'Core License', 'lisans',
   45000, 25, FALSE, FALSE, FALSE, FALSE, 0.18, FALSE, FALSE, TRUE, 40,
   'Komuta kontrol arayüzü ve kurumsal panel. 25 koltuk. Kapalı devre kurulum.',
   'Command and control interface with corporate panel. 25 seats. Air-gapped deployment.'),
  ('GTU-MERKEZ-YZ', 'Merkez ve Yapay Zekâ', 'Core and AI', 'lisans',
   65000, 25, FALSE, TRUE, FALSE, FALSE, 0.18, FALSE, FALSE, TRUE, 50,
   'Merkez lisansı ile görü çıkarım yönetimi.',
   'Core license with vision inference management.'),
  ('GTU-RADAR', 'Radar Füzyon Lisansı', 'Radar Fusion License', 'lisans',
   120000, 0, TRUE, TRUE, TRUE, FALSE, 0.18, TRUE, FALSE, TRUE, 60,
   'Merkez lisansı, AERIS radar füzyonu ve iz yönetimi. Fiyat taban değerdir.',
   'Core license with AERIS radar fusion and track management. Price is a floor value.'),
  ('GTU-TAM', 'Tam Sistem Lisansı', 'Full System License', 'lisans',
   180000, 0, TRUE, TRUE, TRUE, TRUE, 0.18, TRUE, FALSE, TRUE, 70,
   'Tam yazılım paketi ve GCCDual yer kontrol donanımı. Fiyat taban değerdir.',
   'Complete software suite with GCCDual ground control hardware. Price is a floor value.')
ON CONFLICT (anahtar) DO NOTHING;

-- KATMAN 3: Hizmetler (teklif bazlı)
INSERT INTO paketler (anahtar, ad_tr, ad_en, tur, tek_usd,
  fiyat_tabani, satilabilir, yalniz_ust, sira, aciklama_tr, aciklama_en)
VALUES
  ('HZM-RADAR-KALIB', 'Radar Mevzi Kalibrasyonu', 'Radar Site Calibration',
   'hizmet', 15000, TRUE, FALSE, TRUE, 80,
   'Mevzi başına saha kalibrasyonu ve kabul ölçümü.',
   'Per-site field calibration and acceptance measurement.'),
  ('HZM-EGITIM', 'Operatör Eğitimi', 'Operator Training',
   'hizmet', 750, FALSE, FALSE, TRUE, 90,
   'Kişi başına operatör eğitim programı.',
   'Per-person operator training programme.')
ON CONFLICT (anahtar) DO NOTHING;

-- MODÜLLER: satılmaz, yalnız üst yönetici tahsis eder (mevcut davranış)
INSERT INTO paketler (anahtar, ad_tr, ad_en, tur, koltuk,
  radar_dahil, gccdual_dahil, ai_dahil, satilabilir, yalniz_ust, sira,
  aciklama_tr, aciklama_en)
VALUES
  ('radar', 'Radar Modülü', 'Radar Module', 'modul', 0,
   TRUE, FALSE, FALSE, FALSE, TRUE, 100,
   'Satın alınamaz. Uyum değerlendirmesi sonrası tahsis edilir.',
   'Not available for purchase. Allocated after compliance review.'),
  ('gccdual', 'GCCDual Modülü', 'GCCDual Module', 'modul', 0,
   FALSE, TRUE, FALSE, FALSE, TRUE, 110,
   'Satın alınamaz. Uyum değerlendirmesi sonrası tahsis edilir.',
   'Not available for purchase. Allocated after compliance review.')
ON CONFLICT (anahtar) DO NOTHING;

-- MİRAS PAKETLER: yeni müşteriye gösterilmez, mevcut aboneler yaşar.
INSERT INTO paketler (anahtar, ad_tr, ad_en, tur, aylik_usd,
  koltuk, koltuk_basina, ai_dahil, satilabilir, miras, sira,
  aciklama_tr, aciklama_en)
VALUES
  ('pilot_1', 'Pilot Koltuğu (miras)', 'Pilot Seat (legacy)', 'saas',
   5, 1, TRUE, FALSE, FALSE, TRUE, 200,
   'Kaldırılmış plan. Mevcut aboneler sözleşme bitimine kadar korunur.',
   'Retired plan. Existing subscribers retained until contract end.'),
  ('pilot_5', '5 Pilotluk Paket (miras)', '5-Pilot Pack (legacy)', 'saas',
   15, 5, FALSE, FALSE, FALSE, TRUE, 210,
   'Kaldırılmış plan. Mevcut aboneler sözleşme bitimine kadar korunur.',
   'Retired plan. Existing subscribers retained until contract end.'),
  ('pilot_10', '10 Pilotluk Paket (miras)', '10-Pilot Pack (legacy)', 'saas',
   35, 10, FALSE, FALSE, FALSE, TRUE, 220,
   'Kaldırılmış plan. Mevcut aboneler sözleşme bitimine kadar korunur.',
   'Retired plan. Existing subscribers retained until contract end.'),
  ('ai', 'Yapay Zekâ Modülü (miras)', 'AI Module (legacy)', 'saas',
   10, 0, FALSE, TRUE, FALSE, TRUE, 230,
   'Ayrı satılan YZ modülü. Yeni paketlerde kapsam dahilindedir.',
   'Separately sold AI module. Included in scope in new packages.')
ON CONFLICT (anahtar) DO NOTHING;

-- Miras `merkez` paketi (eski 5.000 USD kurulum)
INSERT INTO paketler (anahtar, ad_tr, ad_en, tur, tek_usd,
  koltuk, koltuk_sinirsiz, satilabilir, miras, sira,
  aciklama_tr, aciklama_en)
VALUES
  ('merkez', 'Merkez Uygulama (miras)', 'Core Application (legacy)',
   'lisans', 5000, 0, TRUE, FALSE, TRUE, 240,
   'Eski 5.000 USD tek seferlik kurulum. Yerini GTU-MERKEZ SKU aldı.',
   'Legacy 5,000 USD one-time installation. Superseded by the GTU-MERKEZ SKU.')
ON CONFLICT (anahtar) DO NOTHING;

-- =====================================================================
-- BÖLÜM D — MİRAS GÖÇÜ (mevcut firmaların paket bağı)
--
-- KRİTİK: kimsenin yetkisi DÜŞÜRÜLMEZ. Bu bölüm yalnız
-- `paket_anahtar` alanını doldurur; koltuk, ai, radar, gccdual,
-- sinirsiz alanlarına DOKUNULMAZ.
-- =====================================================================

-- D1. Merkez lisanslı / sınırsız firmalar → GTU-MERKEZ
UPDATE firmalar
   SET paket_anahtar = 'GTU-MERKEZ'
 WHERE paket_anahtar IS NULL
   AND (merkez_lisans = TRUE OR sinirsiz = TRUE);

-- D2. Abonelik kalemi olan firmalar → en son alınan miras pilot paketi
UPDATE firmalar f
   SET paket_anahtar = s.kalem
  FROM (
    SELECT DISTINCT ON (firma_id) firma_id, kalem
      FROM abonelik_kalemleri
     WHERE durum = 'etkin'
       AND kalem IN ('pilot_1','pilot_5','pilot_10')
     ORDER BY firma_id, olusma_ts DESC
  ) s
 WHERE f.firma_id = s.firma_id
   AND f.paket_anahtar IS NULL;

-- D3. Kalan firmalar → ücretsiz Başlangıç
UPDATE firmalar
   SET paket_anahtar = 'baslangic'
 WHERE paket_anahtar IS NULL;

-- D4. Mevcut abonelik kalemlerine paket bağı
UPDATE abonelik_kalemleri
   SET paket_anahtar = kalem
 WHERE paket_anahtar IS NULL;

-- D5. Türkiye'deki firmalar TRY faturalanır (iyzico yabancı para
-- biriminde yalnız yabancı kart kabul ediyor).
UPDATE firmalar
   SET para_birimi = 'TRY'
 WHERE ulke IS NULL
    OR upper(ulke) IN ('TR','TUR','TURKIYE','TÜRKIYE','TÜRKİYE','TURKEY');

-- D6. Kimlik numarası boşsa vergi numarasından doldur (iyzico zorunlu
-- alan). Tüzel kişide VKN kabul edilir.
UPDATE firmalar
   SET kimlik_no = vergi_no
 WHERE kimlik_no IS NULL AND vergi_no IS NOT NULL AND vergi_no <> '';

-- D7. Lisanslı firmalara bakım bitişi (lisans tarihinden +1 yıl).
-- Bakım bitişi geçmişte olsa bile sistem ÇALIŞMAYA DEVAM EDER.
--
-- KOŞUL NEDEN `sinirsiz` DE İÇERİYOR: ölçümde Türkbey'nin
-- `sinirsiz = true` ama `merkez_lisans = false` olduğu görüldü —
-- sınırsızlık elle verilmiş, lisans bayrağı açılmamış. Yalnız
-- `merkez_lisans` aranırsa bu firmaya bakım bitişi HİÇ atanmaz ve
-- bakım kapısı sessizce devre dışı kalır. D1 bu firmayı GTU-MERKEZ
-- paketine bağladığı için bakım kapsamı da tanımlanmalıdır.
UPDATE firmalar
   SET bakim_bitis = (coalesce(merkez_lisans_ts, olusma_ts)::date
                      + INTERVAL '1 year')::date
 WHERE bakim_bitis IS NULL
   AND (merkez_lisans = TRUE OR sinirsiz = TRUE);

-- D8. Mevcut merkez lisanslarına SKU ve kiracı kimliği
UPDATE merkez_lisanslari ml
   SET sku = COALESCE(ml.sku, 'GTU-MERKEZ'),
       koltuk_sinirsiz = TRUE,
       vergi_no = COALESCE(ml.vergi_no, f.vergi_no),
       bakim_bitis = COALESCE(ml.bakim_bitis, f.bakim_bitis)
  FROM firmalar f
 WHERE ml.firma_id = f.firma_id
   AND ml.sku IS NULL;

-- =====================================================================
-- BÖLÜM D9 — TABLO SAHİPLİĞİ (canlıda yaşanan kusur)
--
-- NEDEN GEREKLİ: bu göç `postgres` süper kullanıcısıyla çalıştırılırsa
-- yeni tablolar onun sahipliğinde oluşur ve uygulamanın bağlandığı
-- `goktungu` rolü bunları GÖREMEZ:
--     psycopg2.errors.InsufficientPrivilege: permission denied
--
-- BU KUSUR CANLIDA YAŞANDI ve sınav veritabanında GÖRÜNMEDİ — çünkü
-- sınavda sorgular da `postgres` olarak çalıştırılmıştı. Ders: sınav
-- gerçek uygulama kullanıcısını taklit etmezse yetki kusurlarını
-- kaçırır.
--
-- `DO` bloğu içinde: rol yoksa (geliştirici makinesi) göç kırılmaz.
-- =====================================================================
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'goktungu') THEN
    EXECUTE 'ALTER TABLE paketler         OWNER TO goktungu';
    EXECUTE 'ALTER TABLE iskontolar       OWNER TO goktungu';
    EXECUTE 'ALTER TABLE odeme_olaylari   OWNER TO goktungu';
    EXECUTE 'ALTER TABLE odeme_oturumlari OWNER TO goktungu';
    EXECUTE 'ALTER SEQUENCE paketler_paket_id_seq          OWNER TO goktungu';
    EXECUTE 'ALTER SEQUENCE iskontolar_iskonto_id_seq      OWNER TO goktungu';
    EXECUTE 'ALTER SEQUENCE odeme_olaylari_olay_id_seq     OWNER TO goktungu';
    EXECUTE 'ALTER SEQUENCE odeme_oturumlari_oturum_id_seq OWNER TO goktungu';
  END IF;
END $$;

-- =====================================================================
-- Şema sürümünü yükselt
--
-- SÜRÜM GERİ ALMA TUZAĞI (goc_sema7.sql'den devralınan ders):
-- `SET surum = 9` yazılırsa, bu göç yeniden koştuğunda daha yüksek bir
-- sürümü (10, 11 ...) 9'a DÜŞÜRÜR ve aradaki göçler uygulanmamış
-- sayılır. Sürüm yalnız YÜKSELİR.
-- =====================================================================
INSERT INTO sema_surum (id, surum) VALUES (1, 9)
  ON CONFLICT (id) DO UPDATE
     SET surum = GREATEST(sema_surum.surum, 9), guncel_ts = now();

COMMIT;
