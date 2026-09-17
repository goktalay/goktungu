-- GÖKTUNGU MERKEZ — veritabanı şeması v1
-- Veritabanı: goktungu_merkez, sahip: goktungu
-- Amaç: müşteri (firma) → kullanıcı → uçuş kaydı → video kaydı
--       hiyerarşisi + sabit IP gerektirmeyen sunucu örneği kaydı

BEGIN;

CREATE TABLE IF NOT EXISTS sema_surum (
  id            INTEGER PRIMARY KEY DEFAULT 1,
  surum         INTEGER NOT NULL,
  guncel_ts     TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT sema_surum_tek CHECK (id = 1)
);

-- =====================================================================
-- 1. MÜŞTERİLER (firmalar)
-- =====================================================================
CREATE TABLE IF NOT EXISTS firmalar (
  firma_id      BIGSERIAL PRIMARY KEY,
  unvan         TEXT NOT NULL,
  kisa_ad       TEXT NOT NULL,
  vergi_no      TEXT,
  vergi_dairesi TEXT,
  adres         TEXT,
  telefon       TEXT,
  eposta        CITEXT,
  web           TEXT,
  logo_yol      TEXT,
  ulke          TEXT DEFAULT 'TR',
  durum         TEXT NOT NULL DEFAULT 'etkin'
                CHECK (durum IN ('etkin','askida','iptal')),
  abonelik      TEXT NOT NULL DEFAULT 'deneme'
                CHECK (abonelik IN ('deneme','standart','kurumsal','sinirsiz')),
  abonelik_bitis DATE,
  maks_kullanici INTEGER NOT NULL DEFAULT 5,
  maks_sunucu    INTEGER NOT NULL DEFAULT 1,
  notlar        TEXT,
  olusma_ts     TIMESTAMPTZ NOT NULL DEFAULT now(),
  guncel_ts     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS firmalar_vergi_no_tekil
  ON firmalar (vergi_no) WHERE vergi_no IS NOT NULL AND vergi_no <> '';
CREATE INDEX IF NOT EXISTS firmalar_durum_ix ON firmalar (durum);

-- =====================================================================
-- 2. KULLANICILAR (pilotlar ve firma yöneticileri)
-- =====================================================================
CREATE TABLE IF NOT EXISTS kullanicilar (
  kullanici_id  BIGSERIAL PRIMARY KEY,
  firma_id      BIGINT NOT NULL REFERENCES firmalar(firma_id) ON DELETE CASCADE,
  eposta        CITEXT NOT NULL UNIQUE,
  sifre_ozet    TEXT NOT NULL,
  ad            TEXT NOT NULL DEFAULT '',
  soyad         TEXT NOT NULL DEFAULT '',
  telefon       TEXT,
  rol           TEXT NOT NULL DEFAULT 'pilot'
                CHECK (rol IN ('firma_yonetici','pilot','gozlemci')),
  pilot_lisans  TEXT,
  avatar_yol    TEXT,
  durum         TEXT NOT NULL DEFAULT 'etkin'
                CHECK (durum IN ('etkin','askida','iptal')),
  son_giris_ts  TIMESTAMPTZ,
  son_ip        INET,
  olusma_ts     TIMESTAMPTZ NOT NULL DEFAULT now(),
  guncel_ts     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS kullanicilar_firma_ix ON kullanicilar (firma_id);
CREATE INDEX IF NOT EXISTS kullanicilar_durum_ix ON kullanicilar (durum);

-- =====================================================================
-- 3. SİSTEM YÖNETİCİLERİ (VEILOX personeli — firma kullanıcılarından ayrı)
-- =====================================================================
CREATE TABLE IF NOT EXISTS sistem_yoneticileri (
  yonetici_id   BIGSERIAL PRIMARY KEY,
  eposta        CITEXT NOT NULL UNIQUE,
  sifre_ozet    TEXT NOT NULL,
  ad_soyad      TEXT NOT NULL DEFAULT '',
  unvan         TEXT,
  rol           TEXT NOT NULL DEFAULT 'sistem_yonetici'
                CHECK (rol IN ('sistem_yonetici','gozlemci')),
  durum         TEXT NOT NULL DEFAULT 'etkin'
                CHECK (durum IN ('etkin','askida')),
  son_giris_ts  TIMESTAMPTZ,
  son_ip        INET,
  olusma_ts     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sistem_oturumlari (
  jeton         TEXT PRIMARY KEY,
  yonetici_id   BIGINT NOT NULL REFERENCES sistem_yoneticileri(yonetici_id) ON DELETE CASCADE,
  ip            INET,
  tarayici      TEXT,
  olusma_ts     TIMESTAMPTZ NOT NULL DEFAULT now(),
  bitis_ts      TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS sistem_oturumlari_yonetici_ix
  ON sistem_oturumlari (yonetici_id);
CREATE INDEX IF NOT EXISTS sistem_oturumlari_bitis_ix
  ON sistem_oturumlari (bitis_ts);

CREATE TABLE IF NOT EXISTS kullanici_oturumlari (
  jeton         TEXT PRIMARY KEY,
  kullanici_id  BIGINT NOT NULL REFERENCES kullanicilar(kullanici_id)
                ON DELETE CASCADE,
  firma_id      BIGINT NOT NULL REFERENCES firmalar(firma_id)
                ON DELETE CASCADE,
  ip            INET,
  tarayici      TEXT,
  olusma_ts     TIMESTAMPTZ NOT NULL DEFAULT now(),
  bitis_ts      TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS kullanici_oturumlari_kul_ix
  ON kullanici_oturumlari (kullanici_id);
CREATE INDEX IF NOT EXISTS kullanici_oturumlari_firma_ix
  ON kullanici_oturumlari (firma_id);
CREATE INDEX IF NOT EXISTS kullanici_oturumlari_bitis_ix
  ON kullanici_oturumlari (bitis_ts);


CREATE TABLE IF NOT EXISTS sistem_denetim (
  denetim_id    BIGSERIAL PRIMARY KEY,
  yonetici_id   BIGINT REFERENCES sistem_yoneticileri(yonetici_id) ON DELETE SET NULL,
  eylem         TEXT NOT NULL,
  hedef_tur     TEXT,
  hedef_id      TEXT,
  ayrinti       JSONB NOT NULL DEFAULT '{}'::jsonb,
  ip            INET,
  ts            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS sistem_denetim_ts_ix ON sistem_denetim (ts DESC);
CREATE INDEX IF NOT EXISTS sistem_denetim_yonetici_ix ON sistem_denetim (yonetici_id);

-- =====================================================================
-- 4. SUNUCU ÖRNEKLERİ (ters-WebSocket röle: sabit IP yok)
--    Köprü/yerel GCS sunucusu merkeze KENDİSİ bağlanır.
-- =====================================================================
CREATE TABLE IF NOT EXISTS sunucu_ornekleri (
  ornek_id      BIGSERIAL PRIMARY KEY,
  kurulum_uid   TEXT NOT NULL UNIQUE,          -- kurulumda üretilen kalıcı kimlik
  firma_id      BIGINT NOT NULL REFERENCES firmalar(firma_id) ON DELETE CASCADE,
  ad            TEXT NOT NULL,                 -- kullanıcıya görünen ad
  aciklama      TEXT,
  surum         TEXT,
  platform      TEXT,                          -- linux-x64, windows-x64, aarch64
  makine_adi    TEXT,
  gizli_ozet    TEXT NOT NULL,                 -- paylaşılan sırrın özeti (kayıt için)
  -- bağlantı durumu (röle tarafından güncellenir)
  cevrimici     BOOLEAN NOT NULL DEFAULT FALSE,
  son_gorulme_ts TIMESTAMPTZ,
  son_ip        INET,                          -- ters bağlantının geldiği IP (bilgi amaçlı)
  role_kanal    TEXT,                          -- etkin röle kanal kimliği
  -- yetenek bildirimi
  yetenekler    JSONB NOT NULL DEFAULT '{}'::jsonb,
  dron_sayisi   INTEGER NOT NULL DEFAULT 0,
  durum         TEXT NOT NULL DEFAULT 'etkin'
                CHECK (durum IN ('etkin','askida','iptal')),
  api_kodu      TEXT NOT NULL DEFAULT '',     -- v2.4.232: kurulum API kodu (ilk bağlantıya kadar)
  olusma_ts     TIMESTAMPTZ NOT NULL DEFAULT now(),
  guncel_ts     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS sunucu_ornekleri_firma_ix ON sunucu_ornekleri (firma_id);
CREATE INDEX IF NOT EXISTS sunucu_ornekleri_cevrimici_ix
  ON sunucu_ornekleri (cevrimici, firma_id);

-- Sunucu bağlantı geçmişi (kim ne zaman ne kadar çevrimiçi kaldı)
CREATE TABLE IF NOT EXISTS sunucu_oturumlari (
  oturum_id     BIGSERIAL PRIMARY KEY,
  ornek_id      BIGINT NOT NULL REFERENCES sunucu_ornekleri(ornek_id) ON DELETE CASCADE,
  baslangic_ts  TIMESTAMPTZ NOT NULL DEFAULT now(),
  bitis_ts      TIMESTAMPTZ,
  ip            INET,
  kapanma_nedeni TEXT
);
CREATE INDEX IF NOT EXISTS sunucu_oturumlari_ornek_ix
  ON sunucu_oturumlari (ornek_id, baslangic_ts DESC);

-- =====================================================================
-- 5. DRONLAR (merkezde toplanan araç kayıtları)
-- =====================================================================
CREATE TABLE IF NOT EXISTS dronlar (
  dron_id       BIGSERIAL PRIMARY KEY,
  firma_id      BIGINT NOT NULL REFERENCES firmalar(firma_id) ON DELETE CASCADE,
  ornek_id      BIGINT REFERENCES sunucu_ornekleri(ornek_id) ON DELETE SET NULL,
  yerel_uid     TEXT NOT NULL,                 -- yerel sunucudaki kimlik
  sysid         INTEGER,
  ad            TEXT,
  arac_turu     TEXT,                          -- multirotor, sabit_kanat, vtol, interceptor
  otopilot      TEXT,
  seri_no       TEXT,
  durum         TEXT NOT NULL DEFAULT 'etkin',
  ilk_gorulme_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  son_gorulme_ts TIMESTAMPTZ,
  UNIQUE (firma_id, yerel_uid)
);
CREATE INDEX IF NOT EXISTS dronlar_firma_ix ON dronlar (firma_id);

-- =====================================================================
-- 6. UÇUŞ KAYITLARI (merkeze senkronize edilen uçuş özetleri)
-- =====================================================================
CREATE TABLE IF NOT EXISTS ucus_kayitlari (
  ucus_id       BIGSERIAL PRIMARY KEY,
  ucus_uid      TEXT NOT NULL UNIQUE,          -- kısa benzersiz kod (rapor birleştirme)
  firma_id      BIGINT NOT NULL REFERENCES firmalar(firma_id) ON DELETE CASCADE,
  kullanici_id  BIGINT REFERENCES kullanicilar(kullanici_id) ON DELETE SET NULL,
  dron_id       BIGINT REFERENCES dronlar(dron_id) ON DELETE SET NULL,
  ornek_id      BIGINT REFERENCES sunucu_ornekleri(ornek_id) ON DELETE SET NULL,
  pilot_ad      TEXT,                          -- anlık kopya (kullanıcı silinse de rapor bozulmaz)
  dron_ad       TEXT,
  arac_turu     TEXT,
  baslangic_ts  TIMESTAMPTZ NOT NULL,
  bitis_ts      TIMESTAMPTZ,
  sure_sn       INTEGER,
  mesafe_m      DOUBLE PRECISION,
  maks_irtifa_m DOUBLE PRECISION,
  maks_hiz_ms   DOUBLE PRECISION,
  kalkis_lat    DOUBLE PRECISION,
  kalkis_lon    DOUBLE PRECISION,
  inis_lat      DOUBLE PRECISION,
  inis_lon      DOUBLE PRECISION,
  gorev_turu    TEXT,
  gorev_durumu  TEXT,
  ornek_sayisi  INTEGER NOT NULL DEFAULT 0,
  kalkis_kontrol JSONB,                        -- checklist yanıtları
  ozet          JSONB NOT NULL DEFAULT '{}'::jsonb,
  senk_ts       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ucus_kayitlari_firma_ts_ix
  ON ucus_kayitlari (firma_id, baslangic_ts DESC);
CREATE INDEX IF NOT EXISTS ucus_kayitlari_kullanici_ix
  ON ucus_kayitlari (kullanici_id, baslangic_ts DESC);
CREATE INDEX IF NOT EXISTS ucus_kayitlari_dron_ix
  ON ucus_kayitlari (dron_id, baslangic_ts DESC);

-- Telemetri örnekleri (uçuş izleme/grafik için; hacimli, ayrı tablo)
CREATE TABLE IF NOT EXISTS ucus_telemetri (
  ucus_id       BIGINT NOT NULL REFERENCES ucus_kayitlari(ucus_id) ON DELETE CASCADE,
  ts            TIMESTAMPTZ NOT NULL,
  lat           DOUBLE PRECISION,
  lon           DOUBLE PRECISION,
  irtifa_m      DOUBLE PRECISION,
  hiz_ms        DOUBLE PRECISION,
  yon_derece    DOUBLE PRECISION,
  batarya_v     DOUBLE PRECISION,
  batarya_yuzde DOUBLE PRECISION,
  uydu_sayisi   INTEGER,
  mod           TEXT,
  ek            JSONB,
  PRIMARY KEY (ucus_id, ts)
);

-- =====================================================================
-- 7. VİDEO KAYITLARI
-- =====================================================================
CREATE TABLE IF NOT EXISTS video_kayitlari (
  video_id      BIGSERIAL PRIMARY KEY,
  video_uid     TEXT NOT NULL UNIQUE,
  firma_id      BIGINT NOT NULL REFERENCES firmalar(firma_id) ON DELETE CASCADE,
  ucus_id       BIGINT REFERENCES ucus_kayitlari(ucus_id) ON DELETE SET NULL,
  kullanici_id  BIGINT REFERENCES kullanicilar(kullanici_id) ON DELETE SET NULL,
  dron_id       BIGINT REFERENCES dronlar(dron_id) ON DELETE SET NULL,
  ornek_id      BIGINT REFERENCES sunucu_ornekleri(ornek_id) ON DELETE SET NULL,
  kaynak        TEXT,                          -- kamera adı / rtsp / mjpeg
  baslik        TEXT,
  baslangic_ts  TIMESTAMPTZ NOT NULL,
  bitis_ts      TIMESTAMPTZ,
  sure_sn       INTEGER,
  boyut_bayt    BIGINT,
  cozunurluk    TEXT,
  kodek         TEXT,
  -- depolama: merkezde dosya veya yerel sunucuda (röle ile akıtılır)
  depo_yeri     TEXT NOT NULL DEFAULT 'merkez'
                CHECK (depo_yeri IN ('merkez','yerel')),
  dosya_yol     TEXT,                          -- merkezdeyse göreli yol
  yerel_yol     TEXT,                          -- yereldeyse köprüden istenecek yol
  onizleme_yol  TEXT,                          -- kare görüntüsü
  ozet_sha256   TEXT,
  durum         TEXT NOT NULL DEFAULT 'hazir'
                CHECK (durum IN ('yukleniyor','hazir','eksik','silindi')),
  senk_ts       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS video_kayitlari_firma_ts_ix
  ON video_kayitlari (firma_id, baslangic_ts DESC);
CREATE INDEX IF NOT EXISTS video_kayitlari_ucus_ix ON video_kayitlari (ucus_id);

-- =====================================================================
-- 8. GÜNCELLEME DEPOSU
-- =====================================================================
CREATE TABLE IF NOT EXISTS surumler (
  surum_id      BIGSERIAL PRIMARY KEY,
  urun          TEXT NOT NULL,                 -- gcs, kopru, dron_istemci, ...
  surum         TEXT NOT NULL,
  platform      TEXT NOT NULL DEFAULT 'ortak', -- linux-x64, windows-x64, aarch64, ortak
  kanal         TEXT NOT NULL DEFAULT 'kararli'
                CHECK (kanal IN ('kararli','beta','deneysel')),
  paket_tur     TEXT NOT NULL DEFAULT 'guncelleme'
                CHECK (paket_tur IN ('tam','guncelleme')),
  dosya_ad      TEXT NOT NULL,
  dosya_boyut   BIGINT,
  sha256        TEXT NOT NULL,
  imza          TEXT,                          -- Ed25519 imza (base64)
  asgari_surum  TEXT,                          -- bu yamanın uygulanabileceği en düşük sürüm
  notlar        TEXT,
  -- Bu paketin tasidigi GCS (App) surumu. NULL ise bilinmiyor.
  -- Indirme sayfasi bu alani canli App surumuyle karsilastirip
  -- paket geride kaldiginda uyari gosterir. Serbest metinden
  -- (notlar) tahmin EDILMEZ; olcumde o kalibin ne tutarli ne de
  -- tam oldugu saptandi.  [IS52-APP-SURUM-V1]
  app_surum     TEXT,
  yayin_ts      TIMESTAMPTZ NOT NULL DEFAULT now(),
  etkin         BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE (urun, surum, platform, paket_tur)
);
CREATE INDEX IF NOT EXISTS surumler_urun_ix ON surumler (urun, platform, kanal, etkin);

CREATE TABLE IF NOT EXISTS guncelleme_gecmisi (
  gecmis_id     BIGSERIAL PRIMARY KEY,
  ornek_id      BIGINT REFERENCES sunucu_ornekleri(ornek_id) ON DELETE SET NULL,
  firma_id      BIGINT REFERENCES firmalar(firma_id) ON DELETE SET NULL,
  urun          TEXT NOT NULL,
  eski_surum    TEXT,
  yeni_surum    TEXT,
  sonuc         TEXT NOT NULL DEFAULT 'basarili'
                CHECK (sonuc IN ('basarili','basarisiz','iptal')),
  hata          TEXT,
  ts            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =====================================================================
-- 9. GÖRÜNÜMLER (yönetim paneli için hazır özetler)
-- =====================================================================
-- CREATE OR REPLACE VIEW mevcut kolon adlarını değiştiremez; bu yüzden
-- sürüm yükseltmelerinde önce düşürülür. Görünümler türetilmiştir,
-- veri kaybı olmaz.
DROP VIEW IF EXISTS v_ucus_liste;
DROP VIEW IF EXISTS v_kullanici_ozet;
DROP VIEW IF EXISTS v_firma_ozet;

-- DİKKAT — ABONELİK ALANLARI: `goc_sema6.sql` bu görünümü `pilot_koltuk`,
-- `ai_etkin`, `radar_etkin`, `gccdual_etkin`, `merkez_lisans`, `sinirsiz`,
-- `fatura_donemi` ve `pilot_sayisi` alanlarıyla yeniden kurar. Bu betik her
-- açılışta çalıştığı ve görünümü DROP ettiği için, aşağıdaki tanım o
-- alanları İÇERMEK ZORUNDADIR; aksi halde göçten sonraki ilk yeniden
-- başlatmada alanlar sessizce kaybolur ve abonelik yönetimi boş değer
-- görür. Kolonlar `goc_sema6.sql` ile geldiğinden, ilk kurulumda (kolonlar
-- henüz yokken) bu tanım hata verir — bu yüzden alanların varlığı
-- çalışma zamanında sınanır ve iki tanımdan uygun olanı kurulur.
DO $$
DECLARE
  abonelik_var boolean;
BEGIN
  -- DIKKAT: `table_schema = 'public'` SABIT YAZILMAMALI. Sunucu izole bir
  -- semada calisabilir (sinav ortami, cok kiracili kurulum); sabit sema
  -- adi kolonlari GORMEZ ve eski gorunum tanimi kurulur -> abonelik
  -- alanlari kaybolur. `current_schema()` gecerli search_path'i izler.
  SELECT count(*) = 7 INTO abonelik_var
    FROM information_schema.columns
   WHERE table_schema = current_schema() AND table_name = 'firmalar'
     AND column_name IN ('pilot_koltuk', 'ai_etkin', 'radar_etkin',
                         'gccdual_etkin', 'merkez_lisans', 'sinirsiz',
                         'fatura_donemi');
  IF abonelik_var THEN
    EXECUTE $v$
      CREATE VIEW v_firma_ozet AS
      SELECT f.firma_id, f.unvan, f.kisa_ad, f.durum, f.abonelik,
             f.abonelik_bitis, f.maks_kullanici, f.maks_sunucu, f.vergi_no,
             f.pilot_koltuk, f.ai_etkin, f.radar_etkin, f.gccdual_etkin,
             f.merkez_lisans, f.sinirsiz, f.fatura_donemi,
             (SELECT count(*) FROM kullanicilar k
                WHERE k.firma_id = f.firma_id AND k.durum = 'etkin')
                                                          AS kullanici_sayisi,
             (SELECT count(*) FROM kullanicilar k
                WHERE k.firma_id = f.firma_id AND k.durum = 'etkin'
                  AND k.rol = 'pilot')                     AS pilot_sayisi,
             (SELECT count(*) FROM sunucu_ornekleri s
                WHERE s.firma_id = f.firma_id)             AS sunucu_sayisi,
             (SELECT count(*) FROM sunucu_ornekleri s
                WHERE s.firma_id = f.firma_id AND s.cevrimici)
                                                          AS cevrimici_sunucu,
             (SELECT count(*) FROM dronlar d
                WHERE d.firma_id = f.firma_id)             AS dron_sayisi,
             (SELECT count(*) FROM ucus_kayitlari u
                WHERE u.firma_id = f.firma_id)             AS ucus_sayisi,
             (SELECT count(*) FROM video_kayitlari v
                WHERE v.firma_id = f.firma_id AND v.durum = 'hazir')
                                                          AS video_sayisi,
             (SELECT max(u.baslangic_ts) FROM ucus_kayitlari u
                WHERE u.firma_id = f.firma_id)             AS son_ucus_ts,
             f.olusma_ts
        FROM firmalar f
    $v$;
  ELSE
    EXECUTE $v$
      CREATE VIEW v_firma_ozet AS
      SELECT f.firma_id, f.unvan, f.kisa_ad, f.durum, f.abonelik,
             f.abonelik_bitis, f.maks_kullanici, f.maks_sunucu, f.vergi_no,
             (SELECT count(*) FROM kullanicilar k
                WHERE k.firma_id = f.firma_id AND k.durum = 'etkin')
                                                          AS kullanici_sayisi,
             (SELECT count(*) FROM sunucu_ornekleri s
                WHERE s.firma_id = f.firma_id)             AS sunucu_sayisi,
             (SELECT count(*) FROM sunucu_ornekleri s
                WHERE s.firma_id = f.firma_id AND s.cevrimici)
                                                          AS cevrimici_sunucu,
             (SELECT count(*) FROM dronlar d
                WHERE d.firma_id = f.firma_id)             AS dron_sayisi,
             (SELECT count(*) FROM ucus_kayitlari u
                WHERE u.firma_id = f.firma_id)             AS ucus_sayisi,
             (SELECT count(*) FROM video_kayitlari v
                WHERE v.firma_id = f.firma_id AND v.durum = 'hazir')
                                                          AS video_sayisi,
             (SELECT max(u.baslangic_ts) FROM ucus_kayitlari u
                WHERE u.firma_id = f.firma_id)             AS son_ucus_ts,
             f.olusma_ts
        FROM firmalar f
    $v$;
  END IF;
END $$;

CREATE OR REPLACE VIEW v_kullanici_ozet AS
SELECT k.kullanici_id,
       k.firma_id,
       f.kisa_ad                                                    AS firma_kisa_ad,
       k.eposta,
       k.ad, k.soyad,
       trim(coalesce(k.ad,'') || ' ' || coalesce(k.soyad,''))        AS ad_soyad,
       k.rol, k.durum,
       k.son_giris_ts,
       (SELECT count(*) FROM ucus_kayitlari u
          WHERE u.kullanici_id = k.kullanici_id)                     AS ucus_sayisi,
       (SELECT coalesce(sum(u.sure_sn),0) FROM ucus_kayitlari u
          WHERE u.kullanici_id = k.kullanici_id)                     AS toplam_sure_sn,
       (SELECT count(*) FROM video_kayitlari v
          WHERE v.kullanici_id = k.kullanici_id AND v.durum='hazir')  AS video_sayisi,
       (SELECT max(u.baslangic_ts) FROM ucus_kayitlari u
          WHERE u.kullanici_id = k.kullanici_id)                      AS son_ucus_ts
  FROM kullanicilar k
  JOIN firmalar f ON f.firma_id = k.firma_id;

CREATE OR REPLACE VIEW v_ucus_liste AS
SELECT u.ucus_id, u.ucus_uid, u.firma_id, f.kisa_ad AS firma_kisa_ad,
       u.kullanici_id,
       coalesce(u.pilot_ad,
                trim(coalesce(k.ad,'') || ' ' || coalesce(k.soyad,'')),
                k.eposta::text)                                       AS pilot,
       u.dron_id, coalesce(u.dron_ad, d.ad)                           AS dron,
       u.arac_turu, u.baslangic_ts, u.bitis_ts, u.sure_sn,
       u.mesafe_m, u.maks_irtifa_m, u.gorev_turu, u.gorev_durumu,
       (SELECT count(*) FROM video_kayitlari v
          WHERE v.ucus_id = u.ucus_id AND v.durum='hazir')            AS video_sayisi,
       u.ornek_id, s.ad                                               AS sunucu_ad,
       s.cevrimici                                                    AS sunucu_cevrimici
  FROM ucus_kayitlari u
  JOIN firmalar f            ON f.firma_id = u.firma_id
  LEFT JOIN kullanicilar k   ON k.kullanici_id = u.kullanici_id
  LEFT JOIN dronlar d        ON d.dron_id = u.dron_id
  LEFT JOIN sunucu_ornekleri s ON s.ornek_id = u.ornek_id;

-- ==========================================================================
-- SAHIPLIK GUVENCESI
-- ==========================================================================
-- Bu sema `postgres` ustkullanicisiyla uygulanir, ancak merkez servisi
-- veritabanina `goktungu` roluyle baglanir. Yeni olusturulan tablo/gorunumun
-- sahibi uygulayan rol oldugu icin, sahiplik ATANMAZSA servis kendi
-- semasindaki yeni nesneye YAZAMAZ ve "permission denied for table ..."
-- hatasi verir. Bu blok her gocte sahipligi yeniden hizalar; goc sonrasi
-- elle ALTER ... OWNER TO calistirmak gerekmez.
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

-- DIKKAT — SURUM GERI ALMA TUZAGI: Bu betik HER acilista calisir. Daha
-- once `DO UPDATE SET surum = 5` yaziyordu; bu, uygulanmis gocleri
-- (goc_sema6, goc_sema7 ...) gormezden gelip surumu 5'e DUSURUYORDU.
-- Sonuc: goc bir daha kosmaz sayilir, ancak `BEKLENEN_SEMA` 5'ten buyuk
-- oldugu icin sunucu her acilista "sema eski" der; daha kotusu, bu
-- betigin DROP ettigi `v_firma_ozet` gorunumu abonelik alanlari olmadan
-- yeniden kurulur ve alanlar sessizce kaybolur.
--
-- Dogru davranis: taban surum yalniz YUKSELTIR, asla dusurmez.
INSERT INTO sema_surum (id, surum) VALUES (1, 5)
  ON CONFLICT (id) DO UPDATE
     SET surum = GREATEST(sema_surum.surum, 5), guncel_ts = now();

COMMIT;
