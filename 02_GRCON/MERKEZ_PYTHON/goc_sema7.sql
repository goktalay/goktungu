-- GÖKTUNGU merkez şema göçü 6 -> 7 : Stripe ödeme katmanı
--
-- Yeniden koşulabilir (idempotent). `merkez_sema.sql` yalnız
-- `CREATE TABLE IF NOT EXISTS` içerdiği için MEVCUT tablolara kolon
-- eklemez; bu yüzden ALTER'lar ayrı göç dosyasında tutulur.

-- Firma tarafı ------------------------------------------------------------
-- Stripe müşteri kimliği: kart ve abonelik yönetimi buna bağlanır.
ALTER TABLE firmalar ADD COLUMN IF NOT EXISTS stripe_musteri  TEXT;
-- Ödeme başarısız olduğunda damgalanır. Erişim HEMEN kesilmez; Stripe
-- birkaç gün yeniden dener ve ilk başarısızlıkta kesmek sahadaki
-- uçuşu durdurabilir.
ALTER TABLE firmalar ADD COLUMN IF NOT EXISTS odeme_uyari_ts  TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS firmalar_stripe_musteri_bnz
    ON firmalar (stripe_musteri) WHERE stripe_musteri IS NOT NULL;

-- İşlenen webhook olayları ------------------------------------------------
-- Stripe aynı olayı yeniden gönderebilir (ağ hatası, yeniden deneme).
-- Olay kimliği BİRİNCİL ANAHTAR olduğu için ikinci kez işlenmesi
-- veritabanı düzeyinde engellenir; bu olmadan tek ödeme için koltuk
-- iki kez eklenirdi.
CREATE TABLE IF NOT EXISTS stripe_olaylari (
    olay_id     TEXT PRIMARY KEY,
    tur         TEXT NOT NULL DEFAULT '',
    islendi_ts  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Checkout oturumları -----------------------------------------------------
-- Ödeme sayfası açıldığında kaydedilir, webhook geldiğinde tamamlanır.
-- Tamamlanmayan oturumlar "açık" kalır; terk edilen sepeti gösterir.
CREATE TABLE IF NOT EXISTS stripe_oturumlari (
    oturum_id        TEXT PRIMARY KEY,
    firma_id         INTEGER NOT NULL REFERENCES firmalar(firma_id)
                         ON DELETE CASCADE,
    kalem            TEXT NOT NULL,
    adet             INTEGER NOT NULL DEFAULT 1 CHECK (adet >= 1),
    donem            TEXT NOT NULL
                         CHECK (donem IN ('aylik','yillik','tek')),
    tutar_usd        NUMERIC(10,2) NOT NULL DEFAULT 0,
    durum            TEXT NOT NULL DEFAULT 'acik'
                         CHECK (durum IN ('acik','tamam','iptal')),
    stripe_abonelik  TEXT,
    olustur_ts       TIMESTAMPTZ NOT NULL DEFAULT now(),
    odendi_ts        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS stripe_oturumlari_firma_ix
    ON stripe_oturumlari (firma_id, durum);

-- `abonelik_kalemleri.kaynak` artık 'stripe' de kabul etmeli.
-- Kısıt adı sabit olmadığı için önce mevcut kısıt düşürülür.
DO $$
DECLARE
    k TEXT;
BEGIN
    SELECT conname INTO k FROM pg_constraint
     WHERE conrelid = 'abonelik_kalemleri'::regclass
       AND contype = 'c'
       AND pg_get_constraintdef(oid) ILIKE '%kaynak%';
    IF k IS NOT NULL THEN
        EXECUTE format('ALTER TABLE abonelik_kalemleri DROP CONSTRAINT %I', k);
    END IF;
    ALTER TABLE abonelik_kalemleri
        ADD CONSTRAINT abonelik_kalemleri_kaynak_check
        CHECK (kaynak IN ('veilox','stripe','talep','goc'));
END $$;

-- Sahipliği hizala -------------------------------------------------------
-- ZORUNLU: Göçler `postgres` üstkullanıcısıyla uygulanır, ancak servis
-- veritabanına `goktungu` rolüyle bağlanır. Yeni oluşturulan nesnenin sahibi
-- uygulayan roldür; hizalanmazsa servis kendi şemasındaki yeni tabloya
-- yazamaz ve "permission denied" hatası verir.
--
-- Bu blok önceden bu dosyada YOKTU. Yukarıdaki `stripe_olaylari` ve
-- `stripe_oturumlari` tablolarının sahibi yalnızca göç 6'nın sonradan
-- koşan döngüsü sayesinde `goktungu` oldu — yani şans eseri. Temiz bir
-- kurulumda göçler sırayla bir kez koşar ve bu şans geçerli olmaz.
-- VIEW döngüsü de dahildir: sonraki bir göç görünüm yeniden yaratabilir.
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

-- Şema sürümünü yükselt ---------------------------------------------------
-- DİKKAT: `sema_surum` TEK satırlıdır (`id = 1` kısıtı) ve `aciklama`
-- kolonu YOKTUR. Göç 6 ile birebir aynı kalıp kullanılmalıdır; aksi
-- halde göç hata verir ve işlem geri alınır (tablolar hiç oluşmaz).
--
-- SÜRÜM GERİ ALMA TUZAĞI: `SET surum = 7` yazılırsa, bu göç yeniden
-- koştuğunda daha yüksek bir sürümü (8, 9 ...) 7'ye DÜŞÜRÜR ve aradaki
-- göçler uygulanmamış sayılır. Sürüm yalnız YÜKSELİR.
INSERT INTO sema_surum (id, surum) VALUES (1, 7)
  ON CONFLICT (id) DO UPDATE
     SET surum = GREATEST(sema_surum.surum, 7), guncel_ts = now();
