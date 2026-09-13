-- ============================================================================
-- GÖKTUNGU Merkez — şema göçü 10 -> 11: M50 elektro-optik ürün yetkisi
-- ----------------------------------------------------------------------------
-- M50 fiziksel denetimi yalnız Windows x64 saha Köprüsünde çalışır. Bu geçiş
-- yalnız firma lisans bayrağını ekler; kullanıcı, telemetri, görüntü, mevcut
-- lisans ve müşteri kayıtları dönüştürülmez. Bayrak varsayılan olarak KAPALIDIR.
-- Betik idempotenttir ve servis yeniden başlatıldığında yeniden çalıştırılabilir.
-- ============================================================================
BEGIN;

-- Radar yetkisi M50'yi kendiliğinden açmaz: bağımsız, kapalı ürün tahsisi.
ALTER TABLE firmalar ADD COLUMN IF NOT EXISTS m50_etkin BOOLEAN;
UPDATE firmalar SET m50_etkin = false WHERE m50_etkin IS NULL;
ALTER TABLE firmalar ALTER COLUMN m50_etkin SET NOT NULL;
ALTER TABLE firmalar ALTER COLUMN m50_etkin SET DEFAULT false;

-- Abonelik kalemleri M50 tahsisini açıkça tanır. Önceki isimsiz CHECK kısıtı
-- bulunursa kaldırılır; tablodaki mevcut satırlar değiştirilmez.
DO $$
DECLARE
    k TEXT;
BEGIN
    SELECT conname INTO k
      FROM pg_constraint
     WHERE conrelid = 'abonelik_kalemleri'::regclass
       AND contype = 'c'
       AND pg_get_constraintdef(oid) ILIKE '%kalem%';
    IF k IS NOT NULL THEN
        EXECUTE format('ALTER TABLE abonelik_kalemleri DROP CONSTRAINT %I', k);
    END IF;
    ALTER TABLE abonelik_kalemleri
      ADD CONSTRAINT abonelik_kalemleri_kalem_check
      CHECK (kalem IN ('pilot_1','pilot_5','pilot_10','ai','merkez',
                       'radar','gccdual','m50'));
END $$;

-- Şema sürümü yalnız yükselir; daha yeni bir sürüm geriye çekilmez.
INSERT INTO sema_surum (id, surum) VALUES (1, 11)
  ON CONFLICT (id) DO UPDATE
     SET surum = GREATEST(sema_surum.surum, 11), guncel_ts = now();

COMMIT;
