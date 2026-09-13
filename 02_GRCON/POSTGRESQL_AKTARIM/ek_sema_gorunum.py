#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""merkez_sema.sql icindeki v_firma_ozet tanimini goc 6 ile ayni hale getirir.

SORUN: `merkez_sema.sql` her acilista `DROP VIEW v_firma_ozet` + CREATE
yapiyor ve tanimda `pilot_koltuk` YOK. Goc 6 gorunumu yeni alanlarla
kuruyor, ama goc yalniz bir kez kosar. Ikinci acilista taban betik
gorunumu ESKI haline dondurur -> admin paneli pilot koltuk alanlarini
bos gorur.

COZUM: Taban betikteki alt sorgulari yeni alanlarla genisletmek yerine,
kolonlarin VARLIGINA kosullu bir tanim yazariz. Kolonlar yoksa (ilk
kurulum, goc henuz kosmadi) eski tanim kurulur; varsa yeni tanim.
Boylece hem ilk kurulum hem gocten sonraki acilislar dogru calisir.
"""
from __future__ import annotations

import os
import sys

BURASI = os.path.dirname(os.path.abspath(__file__))
HEDEF = os.path.join(BURASI, "merkez_sema.sql")

ESKI = """DROP VIEW IF EXISTS v_firma_ozet;

CREATE OR REPLACE VIEW v_firma_ozet AS
SELECT f.firma_id,
       f.unvan,
       f.kisa_ad,
       f.durum,
       f.abonelik,
       f.abonelik_bitis,
       f.maks_kullanici,
       f.maks_sunucu,
       f.vergi_no,
"""

YENI = """DROP VIEW IF EXISTS v_firma_ozet;

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
  SELECT count(*) = 7 INTO abonelik_var
    FROM information_schema.columns
   WHERE table_schema = 'public' AND table_name = 'firmalar'
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

CREATE OR REPLACE VIEW v_firma_ozet_eski AS
SELECT f.firma_id,
       f.unvan,
       f.kisa_ad,
       f.durum,
       f.abonelik,
       f.abonelik_bitis,
       f.maks_kullanici,
       f.maks_sunucu,
       f.vergi_no,
"""


def main() -> int:
    with open(HEDEF, "r", encoding="utf-8") as f:
        icerik = f.read()
    if "abonelik_var boolean" in icerik:
        print("[YAMA] Gorunum yamasi zaten var; atlandi")
        return 0
    if ESKI not in icerik:
        print("[YAMA] HATA: beklenen v_firma_ozet tanimi bulunamadi")
        return 1
    icerik = icerik.replace(ESKI, YENI, 1)
    with open(HEDEF, "w", encoding="utf-8") as f:
        f.write(icerik)
    print("[YAMA] merkez_sema.sql v_firma_ozet tanimi kosullu hale getirildi")
    return 0


if __name__ == "__main__":
    sys.exit(main())
