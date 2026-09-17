-- ============================================================================
-- GÖKTUNGU Merkez — şema göçü 12 -> 13: sunucu örneği ürünü (2026-09-17)
-- ----------------------------------------------------------------------------
-- Kurumsal panelde "Köprüler" ve "Merkezi Yazılımlar" (GRCOFF kurulumları)
-- ayrı listelenir; her ikisi de sunucu_ornekleri satırıdır. Ürün, kayıt
-- oluşturulurken bellidir (köprü / gcs) ve API koduna `p` alanı olarak
-- yazılır. Var olan satırlar yetenek bildirimindeki ürün alanından türetilir.
-- Betik idempotenttir.
-- ============================================================================
BEGIN;

ALTER TABLE sunucu_ornekleri ADD COLUMN IF NOT EXISTS urun TEXT NOT NULL DEFAULT 'kopru';
UPDATE sunucu_ornekleri
   SET urun = COALESCE(yetenekler->>'urun', 'kopru')
 WHERE COALESCE(yetenekler->>'urun', '') IN ('gcs', 'video', 'radar', 'gccdual', 'dji')
   AND urun = 'kopru';

INSERT INTO sema_surum (id, surum) VALUES (1, 13)
  ON CONFLICT (id) DO UPDATE
     SET surum = GREATEST(sema_surum.surum, 13), guncel_ts = now();

COMMIT;
