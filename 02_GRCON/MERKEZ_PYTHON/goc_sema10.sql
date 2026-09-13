-- =====================================================================
-- GOC 10 — PAKETIN TASIDIGI APP SURUMU  [IS52-APP-SURUM-V1]
--
-- NEDEN GEREKLI
-- -------------
-- Merkez Uygulamasi (5000 USD kapali devre) paketleri artik HER ISTE
-- otomatik uretilmiyor; yalniz kullanici acikca istediginde yeni surum
-- yayinlanacak. Bu yuzden depodaki paket, canli App surumunun GERISINDE
-- kalabilir. Indirme sayfasinda kullaniciyi uyarabilmek icin paketin
-- HANGI App surumunu tasidigini bilmek gerekiyor.
--
-- NEDEN AYRI SUTUN — SERBEST METIN AYRISTIRMA CURUTULDU
-- -----------------------------------------------------
-- Ilk tasarim `notlar` alanindaki "Icerik karsiligi: App x.y.z"
-- cumlesini ayristirmakti. Olcum bu tasarimi curuttu:
--   2.5.6 -> notlarda 'App' HIC gecmiyor (2631 karakter, eslesme yok)
--   2.5.5 -> yok
--   2.5.4/windows -> yok, ama 2.5.4/linux -> "App 2.4.106"
-- Kalip ne tutarli ne de tam. Serbest metne dayali ayristirma sessizce
-- yanlis sonuc uretir. Alan ACIKCA yazilir; tahmin edilmez.
--
-- SUTUN NULL BIRAKILABILIR
-- ------------------------
-- Bilinmiyorsa NULL kalir ve arayuz "bilinmiyor" der; sessizce
-- "guncel" varsaymaz. Yanlis guven vermek, bilgi vermemekten kotudur.
--
-- TABLO SAHIPLIGI: bu goc YENI TABLO OLUSTURMAZ, yalniz sutun ekler.
-- Bu yuzden goc_sema9 D9'daki `ALTER TABLE ... OWNER TO goktungu`
-- adimina gerek yoktur; sutun eklemek sahipligi degistirmez.
-- =====================================================================
BEGIN;

ALTER TABLE surumler ADD COLUMN IF NOT EXISTS app_surum TEXT;

COMMENT ON COLUMN surumler.app_surum IS
  'Bu paketin tasidigi GCS (App) surumu. NULL ise bilinmiyor.';

-- ---------------------------------------------------------------------
-- Mevcut kayitlarin doldurulmasi
--
-- Yalniz NULL olanlar doldurulur; daha sonra elle duzeltilmis bir deger
-- varsa EZILMEZ. Degerler paket notlarindan ve teslim kuyrugundan
-- dogrulandi (bkz. IS52 olcum belgesi):
--   2.5.6 -> App 2.4.109  (IS 49 + IS 50 teslimi)
--   2.5.5 -> App 2.4.107  (IS 47 teslimi)
--   2.5.4 -> App 2.4.106  (notlarda yazili)
--   2.5.2 -> App 2.4.104  (notlarda yazili)
--   2.5.1 -> App 2.4.102  (notlarda yazili)
-- 2.5.0 ve oncesi icin guvenilir karsilik yok; NULL BIRAKILIR.
-- ---------------------------------------------------------------------
UPDATE surumler SET app_surum = '2.4.109'
 WHERE urun = 'gcs' AND surum = '2.5.6' AND app_surum IS NULL;
UPDATE surumler SET app_surum = '2.4.107'
 WHERE urun = 'gcs' AND surum = '2.5.5' AND app_surum IS NULL;
UPDATE surumler SET app_surum = '2.4.106'
 WHERE urun = 'gcs' AND surum = '2.5.4' AND app_surum IS NULL;
UPDATE surumler SET app_surum = '2.4.104'
 WHERE urun = 'gcs' AND surum = '2.5.2' AND app_surum IS NULL;
UPDATE surumler SET app_surum = '2.4.102'
 WHERE urun = 'gcs' AND surum = '2.5.1' AND app_surum IS NULL;

-- =====================================================================
-- Sema surumunu yukselt
--
-- SURUM GERI ALMA TUZAGI (goc_sema7 -> goc_sema9 zincirinde ogrenildi):
-- `SET surum = 10` yazilirsa, bu goc yeniden kostugunda daha yuksek bir
-- surumu (11, 12 ...) 10'a DUSURUR ve aradaki gocler uygulanmamis
-- sayilir. Surum yalniz YUKSELIR.
-- =====================================================================
INSERT INTO sema_surum (id, surum) VALUES (1, 10)
  ON CONFLICT (id) DO UPDATE
     SET surum = GREATEST(sema_surum.surum, 10), guncel_ts = now();

COMMIT;
