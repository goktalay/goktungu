-- ============================================================================
-- GÖKTUNGU Merkez — şema göçü 11 -> 12: köprü API kodu (2026-09-17)
-- ----------------------------------------------------------------------------
-- Yardım > Köprüler paneli: yeni köprü yalnız adla oluşturulur, merkez bir
-- API kodu üretir (kimlik + sır + adres). Kod sırrı açık taşıdığı için yalnız
-- köprü ilk kez başarıyla bağlanana kadar bu sütunda durur; bağlantı açılınca
-- silinir (mk_role.baglanti_acildi). Betik idempotenttir.
-- ============================================================================
BEGIN;

ALTER TABLE sunucu_ornekleri ADD COLUMN IF NOT EXISTS api_kodu TEXT NOT NULL DEFAULT '';

INSERT INTO sema_surum (id, surum) VALUES (1, 12)
  ON CONFLICT (id) DO UPDATE
     SET surum = GREATEST(sema_surum.surum, 12), guncel_ts = now();

COMMIT;
