-- ============================================================================
-- GÖKTUNGU MERKEZ — şema göçü 5 -> 6: abonelik ve lisans katmanı
-- ----------------------------------------------------------------------------
-- NEDEN AYRI GÖÇ DOSYASI: `merkez_sema.sql` baştan sona
-- `CREATE TABLE IF NOT EXISTS` ile yazılmıştır ve her açılışta yeniden
-- çalıştırılır. Ancak var olan bir tabloya kolon EKLEMEZ — `firmalar`
-- zaten mevcut olduğu için yeni kolonlar sessizce atlanırdı. Bu yüzden
-- kolon eklemeleri açık `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` ile
-- yapılır. Betik yeniden çalıştırılmaya karşı güvenlidir (idempotent).
--
-- ÖNEMLİ: mevcut firmaların pilot koltuğu, GERÇEK etkin pilot sayısı
-- ölçülerek atanır. Sabit varsayılan (1) verilseydi sahadaki 12 pilot
-- sınırı aşmış sayılır ve şirketler kilitlenirdi.
-- ============================================================================
BEGIN;

-- ---------------------------------------------------------------------------
-- 1. firmalar: abonelik ve yetki kolonları
-- ---------------------------------------------------------------------------
ALTER TABLE firmalar ADD COLUMN IF NOT EXISTS pilot_koltuk    INTEGER;
ALTER TABLE firmalar ADD COLUMN IF NOT EXISTS ai_etkin        BOOLEAN;
ALTER TABLE firmalar ADD COLUMN IF NOT EXISTS radar_etkin     BOOLEAN;
ALTER TABLE firmalar ADD COLUMN IF NOT EXISTS gccdual_etkin   BOOLEAN;
ALTER TABLE firmalar ADD COLUMN IF NOT EXISTS merkez_lisans   BOOLEAN;
ALTER TABLE firmalar ADD COLUMN IF NOT EXISTS merkez_lisans_ts TIMESTAMPTZ;
ALTER TABLE firmalar ADD COLUMN IF NOT EXISTS sinirsiz        BOOLEAN;
ALTER TABLE firmalar ADD COLUMN IF NOT EXISTS fatura_donemi   TEXT;

-- Mevcut satırların doldurulması -------------------------------------------
-- Pilot koltuğu: en az 1, ama sahadaki etkin pilot sayısından az olamaz.
--
-- DİKKAT — bu UPDATE bilinçli olarak `pilot_koltuk IS NULL` ile
-- SINIRLANDIRILMAMIŞTIR. Yalnız NULL satırları düzeltmek, göç ikinci kez
-- koştuğunda hiçbir şey yapmaz: kolon ilk koşuda 1 olarak yazılır, sonra
-- firmaya elle pilot eklenirse (ya da bu göçten önceki bir yoldan pilot
-- girmişse) koltuk 1'de kalır ve firma kendi mevcut pilotları yüzünden
-- kilitlenir. Bu yüzden koşul "koltuk gerçek pilot sayısının ALTINDA
-- kalmış mı" biçiminde yazılır. Satın alınmış koltuklar korunur, çünkü
-- GREATEST mevcut değeri asla DÜŞÜRMEZ — yalnız yükseltir.
UPDATE firmalar f SET pilot_koltuk = GREATEST(1, coalesce(f.pilot_koltuk, 0), (
    SELECT count(*) FROM kullanicilar k
     WHERE k.firma_id = f.firma_id
       AND k.rol = 'pilot' AND k.durum = 'etkin'))
 WHERE f.pilot_koltuk IS NULL
    OR f.pilot_koltuk < (
        SELECT count(*) FROM kullanicilar k
         WHERE k.firma_id = f.firma_id
           AND k.rol = 'pilot' AND k.durum = 'etkin');

UPDATE firmalar SET ai_etkin      = false WHERE ai_etkin      IS NULL;
UPDATE firmalar SET radar_etkin   = false WHERE radar_etkin   IS NULL;
UPDATE firmalar SET gccdual_etkin = false WHERE gccdual_etkin IS NULL;
UPDATE firmalar SET merkez_lisans = false WHERE merkez_lisans IS NULL;
UPDATE firmalar SET fatura_donemi = 'aylik' WHERE fatura_donemi IS NULL;

-- Mevcut `kurumsal` müşterilerin hakları korunur: sınırsız sayılırlar.
-- Aksi halde bugün 20-100 kullanıcı kotasıyla çalışan müşteriler yeni
-- koltuk denetimiyle bir gecede kilitlenirdi.
UPDATE firmalar SET sinirsiz = true
 WHERE sinirsiz IS NULL AND abonelik IN ('kurumsal', 'sinirsiz');
UPDATE firmalar SET sinirsiz = false WHERE sinirsiz IS NULL;

-- NOT NULL ve varsayılanlar (doldurma yapıldıktan SONRA) --------------------
ALTER TABLE firmalar ALTER COLUMN pilot_koltuk  SET NOT NULL;
ALTER TABLE firmalar ALTER COLUMN pilot_koltuk  SET DEFAULT 1;
ALTER TABLE firmalar ALTER COLUMN ai_etkin      SET NOT NULL;
ALTER TABLE firmalar ALTER COLUMN ai_etkin      SET DEFAULT false;
ALTER TABLE firmalar ALTER COLUMN radar_etkin   SET NOT NULL;
ALTER TABLE firmalar ALTER COLUMN radar_etkin   SET DEFAULT false;
ALTER TABLE firmalar ALTER COLUMN gccdual_etkin SET NOT NULL;
ALTER TABLE firmalar ALTER COLUMN gccdual_etkin SET DEFAULT false;
ALTER TABLE firmalar ALTER COLUMN merkez_lisans SET NOT NULL;
ALTER TABLE firmalar ALTER COLUMN merkez_lisans SET DEFAULT false;
ALTER TABLE firmalar ALTER COLUMN sinirsiz      SET NOT NULL;
ALTER TABLE firmalar ALTER COLUMN sinirsiz      SET DEFAULT false;
ALTER TABLE firmalar ALTER COLUMN fatura_donemi SET NOT NULL;
ALTER TABLE firmalar ALTER COLUMN fatura_donemi SET DEFAULT 'aylik';

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                  WHERE conname = 'firmalar_fatura_donemi_check') THEN
    ALTER TABLE firmalar ADD CONSTRAINT firmalar_fatura_donemi_check
      CHECK (fatura_donemi IN ('aylik', 'yillik'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                  WHERE conname = 'firmalar_pilot_koltuk_check') THEN
    ALTER TABLE firmalar ADD CONSTRAINT firmalar_pilot_koltuk_check
      CHECK (pilot_koltuk >= 1);
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 2. abonelik_kalemleri — satın alınan/atanan kalem defteri
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS abonelik_kalemleri (
  kalem_id      BIGSERIAL PRIMARY KEY,
  firma_id      BIGINT NOT NULL REFERENCES firmalar(firma_id)
                  ON DELETE CASCADE,
  kalem         TEXT NOT NULL
                  CHECK (kalem IN ('pilot_1', 'pilot_5', 'pilot_10',
                                   'ai', 'merkez', 'radar', 'gccdual')),
  adet          INTEGER NOT NULL DEFAULT 1 CHECK (adet > 0),
  donem         TEXT NOT NULL DEFAULT 'aylik'
                  CHECK (donem IN ('aylik', 'yillik', 'tek')),
  birim_usd     NUMERIC(10, 2) NOT NULL DEFAULT 0,
  toplam_usd    NUMERIC(10, 2) NOT NULL DEFAULT 0,
  -- kaynak: talep = şirket istedi (beklemede sayılmaz, onaylanınca yazılır),
  -- veilox = sistem yöneticisi elle tanımladı, odeme = ödeme alındı
  kaynak        TEXT NOT NULL DEFAULT 'talep'
                  CHECK (kaynak IN ('talep', 'veilox', 'odeme')),
  veren_yonetici_id BIGINT REFERENCES sistem_yoneticileri(yonetici_id)
                  ON DELETE SET NULL,
  baslangic     DATE NOT NULL DEFAULT CURRENT_DATE,
  bitis         DATE,
  durum         TEXT NOT NULL DEFAULT 'etkin'
                  CHECK (durum IN ('etkin', 'suresi_bitti', 'iptal')),
  notlar        TEXT,
  olusma_ts     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS abonelik_kalemleri_firma_ix
  ON abonelik_kalemleri (firma_id, durum);

-- ---------------------------------------------------------------------------
-- 3. uyelik_talepleri — ön talep değerlendirme kuyruğu
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS uyelik_talepleri (
  talep_id      BIGSERIAL PRIMARY KEY,
  firma_id      BIGINT REFERENCES firmalar(firma_id) ON DELETE SET NULL,
  kalem         TEXT NOT NULL
                  CHECK (kalem IN ('pilot_1', 'pilot_5', 'pilot_10',
                                   'ai', 'merkez', 'radar', 'gccdual')),
  adet          INTEGER NOT NULL DEFAULT 1 CHECK (adet > 0),
  donem         TEXT NOT NULL DEFAULT 'aylik'
                  CHECK (donem IN ('aylik', 'yillik', 'tek')),
  iletisim_ad   TEXT,
  iletisim_eposta CITEXT,
  iletisim_tel  TEXT,
  mesaj         TEXT,
  durum         TEXT NOT NULL DEFAULT 'bekliyor'
                  CHECK (durum IN ('bekliyor', 'onaylandi', 'reddedildi')),
  karar_yonetici_id BIGINT REFERENCES sistem_yoneticileri(yonetici_id)
                  ON DELETE SET NULL,
  karar_ts      TIMESTAMPTZ,
  karar_notu    TEXT,
  olusma_ts     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS uyelik_talepleri_durum_ix
  ON uyelik_talepleri (durum, olusma_ts DESC);

-- ---------------------------------------------------------------------------
-- 4. merkez_lisanslari — Merkez Uygulama için imzalı lisans belgeleri
-- ---------------------------------------------------------------------------
-- NEDEN: Merkez Uygulama KAPALI DEVRE çalışabilir; lisansı çevrimiçi
-- doğrulayamaz. Bu yüzden yetkiler indirme anında imzalı bir belgeye
-- yazılır ve pakete gömülür. Uygulama yalnızca açık anahtarla imzayı
-- doğrular, ağa çıkmaz.
CREATE TABLE IF NOT EXISTS merkez_lisanslari (
  lisans_id     BIGSERIAL PRIMARY KEY,
  firma_id      BIGINT NOT NULL REFERENCES firmalar(firma_id)
                  ON DELETE CASCADE,
  lisans_uid    TEXT NOT NULL UNIQUE,
  yetkiler      JSONB NOT NULL,
  imza          TEXT NOT NULL,
  indirme_sayisi INTEGER NOT NULL DEFAULT 0,
  son_indirme_ts TIMESTAMPTZ,
  olusma_ts     TIMESTAMPTZ NOT NULL DEFAULT now(),
  iptal_ts      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS merkez_lisanslari_firma_ix
  ON merkez_lisanslari (firma_id) WHERE iptal_ts IS NULL;

-- ---------------------------------------------------------------------------
-- 5. v_firma_ozet görünümünü yeni alanlarla yenile
-- ---------------------------------------------------------------------------
-- NEDEN BURADA: `merkez_sema.sql` bu görünümü DROP + CREATE ile her
-- açılışta yeniden kurar, ancak orada `pilot_koltuk` YOKTUR. Görünümü
-- taban betiğe eklemek olanaksız: kolonlar bu göçle geldiği için taban
-- betik ilk kurulumda hata verirdi. Bu yüzden görünüm göç sırasında,
-- kolonlar eklendikten SONRA yenilenir. Taban betik daha sonra çalışıp
-- görünümü eski haline döndürürse, göç `sema_surum` sayesinde tekrar
-- koşmayacağından alan kaybolur; bu yüzden `merkez_sema.sql` içindeki
-- tanım da aynı hale getirilmiştir (bkz. mk_api.firma_liste).
--
-- pilot_sayisi: koltuk denetiminin saydığı GERÇEK birim. `kullanici_sayisi`
-- tüm rolleri sayar ve faturalandırmada yanıltıcıdır — yönetici ve
-- gözlemci koltuk tüketmez.
DROP VIEW IF EXISTS v_firma_ozet;
CREATE VIEW v_firma_ozet AS
SELECT f.firma_id,
       f.unvan,
       f.kisa_ad,
       f.durum,
       f.abonelik,
       f.abonelik_bitis,
       f.maks_kullanici,
       f.maks_sunucu,
       f.vergi_no,
       f.pilot_koltuk,
       f.ai_etkin,
       f.radar_etkin,
       f.gccdual_etkin,
       f.merkez_lisans,
       f.sinirsiz,
       f.fatura_donemi,
       (SELECT count(*) FROM kullanicilar k
          WHERE k.firma_id = f.firma_id AND k.durum = 'etkin')     AS kullanici_sayisi,
       (SELECT count(*) FROM kullanicilar k
          WHERE k.firma_id = f.firma_id AND k.durum = 'etkin'
            AND k.rol = 'pilot')                                   AS pilot_sayisi,
       (SELECT count(*) FROM sunucu_ornekleri s
          WHERE s.firma_id = f.firma_id)                            AS sunucu_sayisi,
       (SELECT count(*) FROM sunucu_ornekleri s
          WHERE s.firma_id = f.firma_id AND s.cevrimici)            AS cevrimici_sunucu,
       (SELECT count(*) FROM dronlar d
          WHERE d.firma_id = f.firma_id)                            AS dron_sayisi,
       (SELECT count(*) FROM ucus_kayitlari u
          WHERE u.firma_id = f.firma_id)                            AS ucus_sayisi,
       (SELECT count(*) FROM video_kayitlari v
          WHERE v.firma_id = f.firma_id AND v.durum = 'hazir')      AS video_sayisi,
       (SELECT max(u.baslangic_ts) FROM ucus_kayitlari u
          WHERE u.firma_id = f.firma_id)                            AS son_ucus_ts,
       f.olusma_ts
  FROM firmalar f;

-- ---------------------------------------------------------------------------
-- 6. Sahibi düzelt (şema dosyasıyla aynı davranış)
-- ---------------------------------------------------------------------------
-- KUSUR (2026-08-15, canlıda yakalandı): Bu blok yalnızca TABLE ve SEQUENCE
-- sahipliğini hizalıyordu; **VIEW döngüsü yoktu**. Yukarıdaki 5. adım
-- `v_firma_ozet` görünümünü DROP + CREATE ettiği ve bu göç `postgres`
-- üstkullanıcısıyla uygulandığı için görünümün sahibi `postgres` kalıyordu.
-- Servis veritabanına `goktungu` rolüyle bağlandığından admin panelinin
-- Müşteriler / Abonelikler sayfaları "permission denied for view
-- v_firma_ozet" hatası veriyordu.
--
-- Görünüm döngüsü, taban `merkez_sema.sql` içinde ZATEN vardı; buraya
-- kopyalanırken atlanmış. Göç taban betikten SONRA çalıştığı için tabanın
-- döngüsü sonucu kurtarmaz: göç görünümü yeniden yaratıp `postgres`
-- sahipliğinde bırakır. Bu yüzden döngü BURADA da bulunmak ZORUNDADIR.
-- Yeni bir göç yazarken görünüm DROP/CREATE ediyorsanız bu üç döngüyü de
-- kopyalayın.
DO $$
DECLARE
  r record;
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'goktungu') THEN
    FOR r IN SELECT tablename AS n FROM pg_tables WHERE schemaname = 'public'
    LOOP
      EXECUTE format('ALTER TABLE public.%I OWNER TO goktungu', r.n);
    END LOOP;
    FOR r IN SELECT viewname AS n FROM pg_views WHERE schemaname = 'public'
    LOOP
      EXECUTE format('ALTER VIEW public.%I OWNER TO goktungu', r.n);
    END LOOP;
    FOR r IN SELECT sequence_name AS n FROM information_schema.sequences
              WHERE sequence_schema = 'public'
    LOOP
      EXECUTE format('ALTER SEQUENCE public.%I OWNER TO goktungu', r.n);
    END LOOP;
  END IF;
END $$;

-- SÜRÜM GERİ ALMA TUZAĞI: `SET surum = 6` yazılırsa, bu göç yeniden
-- koştuğunda şema sürümünü 7'den 6'ya DÜŞÜRÜR ve sonraki göçler bir daha
-- uygulanmış sayılmaz. Taban `merkez_sema.sql` bu tuzağı `GREATEST` ile
-- çözmüştü; aynı korumayı burada da uygularız. Sürüm yalnız YÜKSELİR.
INSERT INTO sema_surum (id, surum) VALUES (1, 6)
  ON CONFLICT (id) DO UPDATE
     SET surum = GREATEST(sema_surum.surum, 6), guncel_ts = now();

COMMIT;
