#!/usr/bin/env python3.11
"""Faz 14 — iskonto ve fiyatlandirma sinavi.

Sunucuda `sudo -u goktungu python3.11` ile calistirilir.
Gecici bir sinav firmasi olusturur, iskontolari dener, sonra TEMIZLER.
"""
import sys

import mk_ayar          # noqa: F401  (DB ayarlarini yukler)
import mk_db as db
import mk_paket as p
import mk_bakim as b

gecti = 0
kusur = []


def olc(ad, kosul, ayrinti=""):
    global gecti
    if kosul:
        gecti += 1
    else:
        kusur.append("%s %s" % (ad, ayrinti))


# ---------------------------------------------------------------------------
# Sinav firmasi
# ---------------------------------------------------------------------------
SINAV_AD = "__FAZ14_SINAV__"
db.calistir("DELETE FROM firmalar WHERE kisa_ad = %s", (SINAV_AD,))
fid = db.deger(
    "INSERT INTO firmalar (unvan, kisa_ad, durum, abonelik, paket_anahtar, "
    "  para_birimi, pilot_koltuk) "
    "VALUES (%s,%s,'etkin','deneme','profesyonel','TRY',1) "
    "RETURNING firma_id", ("Faz 14 Sinav A.S.", SINAV_AD))
fid = int(fid)

try:
    # -----------------------------------------------------------------
    # 1. Katalog butunlugu
    # -----------------------------------------------------------------
    kat = p.katalog(tazele=True)
    olc("K01 katalog dolu", len(kat) >= 16, "(%d)" % len(kat))
    olc("K02 baslangic var", "baslangic" in kat)
    olc("K03 profesyonel var", "profesyonel" in kat)
    olc("K04 kurumsal_bulut var", "kurumsal_bulut" in kat)
    olc("K05 GTU-MERKEZ var", "GTU-MERKEZ" in kat)
    olc("K06 GTU-MERKEZ-YZ var", "GTU-MERKEZ-YZ" in kat)
    olc("K07 GTU-RADAR var", "GTU-RADAR" in kat)
    olc("K08 GTU-TAM var", "GTU-TAM" in kat)
    olc("K09 miras pilot_1 var", "pilot_1" in kat)
    olc("K10 miras pilot_5 var", "pilot_5" in kat)
    olc("K11 miras pilot_10 var", "pilot_10" in kat)
    olc("K12 miras ai var", "ai" in kat)
    olc("K13 miras merkez var", "merkez" in kat)

    # -----------------------------------------------------------------
    # 2. Brifing fiyatlari (USD)
    # -----------------------------------------------------------------
    olc("F01 profesyonel 29 USD",
        p.ham_fiyat("profesyonel", "aylik", "USD") == 29.0)
    olc("F02 kurumsal 490 USD",
        p.ham_fiyat("kurumsal_bulut", "aylik", "USD") == 490.0)
    olc("F03 baslangic 0 USD",
        p.ham_fiyat("baslangic", "aylik", "USD") == 0.0)
    olc("F04 GTU-MERKEZ 45000",
        p.ham_fiyat("GTU-MERKEZ", "tek", "USD") == 45000.0)
    olc("F05 GTU-MERKEZ-YZ 65000",
        p.ham_fiyat("GTU-MERKEZ-YZ", "tek", "USD") == 65000.0)
    olc("F06 GTU-RADAR 120000",
        p.ham_fiyat("GTU-RADAR", "tek", "USD") == 120000.0)
    olc("F07 GTU-TAM 180000",
        p.ham_fiyat("GTU-TAM", "tek", "USD") == 180000.0)
    olc("F08 egitim 750",
        p.ham_fiyat("HZM-EGITIM", "tek", "USD") == 750.0)
    olc("F09 radar kalib 15000",
        p.ham_fiyat("HZM-RADAR-KALIB", "tek", "USD") == 15000.0)

    # Miras fiyatlar korunmus
    olc("F10 miras pilot_1 5 USD",
        p.ham_fiyat("pilot_1", "aylik", "USD") == 5.0)
    olc("F11 miras pilot_5 15 USD",
        p.ham_fiyat("pilot_5", "aylik", "USD") == 15.0)
    olc("F12 miras pilot_10 35 USD",
        p.ham_fiyat("pilot_10", "aylik", "USD") == 35.0)
    olc("F13 miras ai 10 USD",
        p.ham_fiyat("ai", "aylik", "USD") == 10.0)
    olc("F14 miras merkez 5000 USD",
        p.ham_fiyat("merkez", "tek", "USD") == 5000.0)

    # -----------------------------------------------------------------
    # 3. Yillik indirim %20
    # -----------------------------------------------------------------
    olc("Y01 prof yillik USD 278.40",
        p.ham_fiyat("profesyonel", "yillik", "USD") == 278.40,
        "(%s)" % p.ham_fiyat("profesyonel", "yillik", "USD"))
    olc("Y02 prof yillik TRY 9504",
        p.ham_fiyat("profesyonel", "yillik", "TRY") == 9504.0)
    olc("Y03 yillik_tutar dogrudan",
        p.yillik_tutar(100.0) == 960.0)
    olc("Y04 kurumsal yillik TRY",
        p.ham_fiyat("kurumsal_bulut", "yillik", "TRY") == 162240.0,
        "(%s)" % p.ham_fiyat("kurumsal_bulut", "yillik", "TRY"))

    # -----------------------------------------------------------------
    # 4. Adet carpimi (koltuk basina fiyatlama)
    # -----------------------------------------------------------------
    olc("A01 5 koltuk aylik TRY",
        p.ham_fiyat("profesyonel", "aylik", "TRY", 5) == 4950.0)
    olc("A02 5 koltuk yillik TRY",
        p.ham_fiyat("profesyonel", "yillik", "TRY", 5) == 47520.0)
    olc("A03 adet 0 -> 1 sayilir",
        p.ham_fiyat("profesyonel", "aylik", "TRY", 0) == 990.0)

    # -----------------------------------------------------------------
    # 5. Satilamaz paket / donem hatalari
    # -----------------------------------------------------------------
    try:
        p.ham_fiyat("GTU-MERKEZ", "aylik", "USD")
        olc("H01 lisans aylik satilmaz", False, "hata atilmadi")
    except p.PaketHatasi:
        olc("H01 lisans aylik satilmaz", True)

    try:
        p.ham_fiyat("profesyonel", "tek", "USD")
        olc("H02 saas tek satilmaz", False, "hata atilmadi")
    except p.PaketHatasi:
        olc("H02 saas tek satilmaz", True)

    try:
        p.ham_fiyat("yok_boyle", "aylik", "TRY")
        olc("H03 olmayan paket hata", False, "hata atilmadi")
    except p.PaketHatasi:
        olc("H03 olmayan paket hata", True)

    try:
        p.ham_fiyat("profesyonel", "haftalik", "TRY")
        olc("H04 gecersiz donem hata", False, "hata atilmadi")
    except p.PaketHatasi:
        olc("H04 gecersiz donem hata", True)

    # Miras paket TRY fiyati YOK -> hata atmali (USD'de yasiyorlar)
    try:
        p.ham_fiyat("pilot_5", "aylik", "TRY")
        olc("H05 miras TRY yok", False, "hata atilmadi")
    except p.PaketHatasi:
        olc("H05 miras TRY yok", True)

    # -----------------------------------------------------------------
    # 6. Arayuz listesi gizleme
    # -----------------------------------------------------------------
    musteri = [x["paket"] for x in p.fiyat_listesi()]
    olc("L01 musteri 3 paket gorur", len(musteri) == 3, str(musteri))
    olc("L02 miras gizli", "pilot_5" not in musteri)
    olc("L03 SKU gizli", "GTU-MERKEZ" not in musteri)
    olc("L04 modul gizli", "radar" not in musteri)
    olc("L05 hizmet gizli", "HZM-EGITIM" not in musteri)
    ust = [x["paket"] for x in p.fiyat_listesi(ust_yonetici=True)]
    olc("L06 ust yonetici hepsini gorur", len(ust) >= 16, "(%d)" % len(ust))
    olc("L07 ust yonetici SKU gorur", "GTU-MERKEZ" in ust)
    # Her iki para birimi de listede
    k0 = p.fiyat_listesi()[1]
    olc("L08 liste TRY alani", k0.get("aylik_try") is not None)
    olc("L09 liste USD alani", k0.get("aylik_usd") is not None)
    olc("L10 liste yillik turetilmis", k0.get("yillik_try") == 9504.0)

    # -----------------------------------------------------------------
    # 7. ISKONTO — yuzde
    # -----------------------------------------------------------------
    iid, hata = p.iskonto_tanimla(fid, "yuzde", 10,
                                  paket_anahtar="profesyonel",
                                  gerekce="sinav")
    olc("I01 yuzde iskonto tanimlandi", iid is not None, hata)
    nf = p.net_fiyat(fid, "profesyonel", "aylik", "TRY")
    olc("I02 yuzde net 891", nf["net"] == 891.0, str(nf))
    olc("I03 yuzde brut korunur", nf["brut"] == 990.0)
    olc("I04 indirilen 99", nf["iskonto"] == 99.0)
    olc("I05 iskonto_id dondu", nf["iskonto_id"] == iid)

    # Yillik + iskonto birlesimi: 9504 * 0.90 = 8553.60
    nfy = p.net_fiyat(fid, "profesyonel", "yillik", "TRY")
    olc("I06 yillik+iskonto 8553.60", nfy["net"] == 8553.60, str(nfy))

    # Baska paket etkilenmemeli
    nfk = p.net_fiyat(fid, "kurumsal_bulut", "aylik", "TRY")
    olc("I07 pakete ozgu iskonto sizmaz", nfk["net"] == 16900.0, str(nfk))

    p.iskonto_iptal(iid)
    nf2 = p.net_fiyat(fid, "profesyonel", "aylik", "TRY")
    olc("I08 iptal sonrasi tam fiyat", nf2["net"] == 990.0)

    # -----------------------------------------------------------------
    # 8. ISKONTO — tutar ve para birimi korumasi
    # -----------------------------------------------------------------
    iid2, hata2 = p.iskonto_tanimla(fid, "tutar", 200,
                                    paket_anahtar="profesyonel",
                                    para_birimi="TRY", gerekce="sinav")
    olc("I09 tutar iskonto tanimlandi", iid2 is not None, hata2)
    nf3 = p.net_fiyat(fid, "profesyonel", "aylik", "TRY")
    olc("I10 tutar net 790", nf3["net"] == 790.0, str(nf3))

    # KRITIK: TRY iskontosu USD fiyatina UYGULANMAMALI
    nf4 = p.net_fiyat(fid, "profesyonel", "aylik", "USD")
    olc("I11 TRY iskontosu USD'ye sizmaz", nf4["net"] == 29.0, str(nf4))
    olc("I12 USD iskonto_id yok", nf4["iskonto_id"] is None)
    p.iskonto_iptal(iid2)

    # -----------------------------------------------------------------
    # 9. ISKONTO — negatif fiyat korumasi
    # -----------------------------------------------------------------
    iid3, _ = p.iskonto_tanimla(fid, "tutar", 99999,
                                paket_anahtar="profesyonel",
                                para_birimi="TRY", gerekce="sinav asiri")
    nf5 = p.net_fiyat(fid, "profesyonel", "aylik", "TRY")
    olc("I13 asiri iskonto 0'a kelepcelenir", nf5["net"] == 0.0, str(nf5))
    olc("I14 negatif DEGIL", nf5["net"] >= 0.0)
    p.iskonto_iptal(iid3)

    # -----------------------------------------------------------------
    # 10. ISKONTO — dogrulama kurallari
    # -----------------------------------------------------------------
    r, h = p.iskonto_tanimla(fid, "yuzde", 150)
    olc("I15 %150 reddedilir", r is None, h)
    r, h = p.iskonto_tanimla(fid, "yuzde", 0)
    olc("I16 %0 reddedilir", r is None, h)
    r, h = p.iskonto_tanimla(fid, "yuzde", -5)
    olc("I17 negatif reddedilir", r is None, h)
    r, h = p.iskonto_tanimla(fid, "tutar", 100)
    olc("I18 tutar para birimsiz reddedilir", r is None, h)
    r, h = p.iskonto_tanimla(fid, "tutar", 100, para_birimi="EUR")
    olc("I19 desteklenmeyen birim reddedilir", r is None, h)
    r, h = p.iskonto_tanimla(fid, "karma", 10)
    olc("I20 gecersiz tur reddedilir", r is None, h)
    r, h = p.iskonto_tanimla(fid, "yuzde", 10, paket_anahtar="yok_boyle")
    olc("I21 olmayan paket reddedilir", r is None, h)
    r, h = p.iskonto_tanimla(999999, "yuzde", 10)
    olc("I22 olmayan firma reddedilir", r is None, h)
    r, h = p.iskonto_tanimla(fid, "yuzde", "abc")
    olc("I23 sayisal olmayan reddedilir", r is None, h)

    # -----------------------------------------------------------------
    # 11. ISKONTO — genel (paketsiz) iskonto
    # -----------------------------------------------------------------
    iid4, _ = p.iskonto_tanimla(fid, "yuzde", 25, gerekce="genel sinav")
    n_prof = p.net_fiyat(fid, "profesyonel", "aylik", "TRY")["net"]
    n_kur = p.net_fiyat(fid, "kurumsal_bulut", "aylik", "TRY")["net"]
    olc("I24 genel iskonto profesyonele", n_prof == 742.50, str(n_prof))
    olc("I25 genel iskonto kurumsala", n_kur == 12675.0, str(n_kur))

    # Pakete ozgu iskonto genel iskontodan ONCELIKLI
    iid5, _ = p.iskonto_tanimla(fid, "yuzde", 50,
                                paket_anahtar="profesyonel",
                                gerekce="ozgu sinav")
    n_prof2 = p.net_fiyat(fid, "profesyonel", "aylik", "TRY")["net"]
    olc("I26 pakete ozgu oncelikli", n_prof2 == 495.0, str(n_prof2))
    n_kur2 = p.net_fiyat(fid, "kurumsal_bulut", "aylik", "TRY")["net"]
    olc("I27 kurumsal genel iskontoda kalir", n_kur2 == 12675.0, str(n_kur2))

    # Kumulatif DEGIL: 25 + 50 birlikte uygulanmamali (0.375 olurdu)
    olc("I28 kumulatif degil", n_prof2 != 371.25)
    p.iskonto_iptal(iid4)
    p.iskonto_iptal(iid5)

    # -----------------------------------------------------------------
    # 12. ISKONTO — tarih gecerliligi
    # -----------------------------------------------------------------
    iid6, _ = p.iskonto_tanimla(fid, "yuzde", 30,
                                paket_anahtar="profesyonel",
                                gecerli_bas="2099-01-01",
                                gerekce="gelecek")
    nfg = p.net_fiyat(fid, "profesyonel", "aylik", "TRY")
    olc("I29 gelecek iskonto uygulanmaz", nfg["net"] == 990.0, str(nfg))
    p.iskonto_iptal(iid6)

    iid7, _ = p.iskonto_tanimla(fid, "yuzde", 30,
                                paket_anahtar="profesyonel",
                                gecerli_bas="2020-01-01",
                                gecerli_bit="2020-12-31",
                                gerekce="gecmis")
    nfe = p.net_fiyat(fid, "profesyonel", "aylik", "TRY")
    olc("I30 suresi gecmis iskonto uygulanmaz", nfe["net"] == 990.0, str(nfe))
    p.iskonto_iptal(iid7)

    # Firma_id verilmezse iskonto uygulanmaz
    nfn = p.net_fiyat(None, "profesyonel", "aylik", "TRY")
    olc("I31 firma_id yoksa iskonto yok", nfn["net"] == 990.0)
    olc("I32 firma_id yoksa iskonto_id None", nfn["iskonto_id"] is None)

    # -----------------------------------------------------------------
    # 13. BAKIM KAPISI
    # -----------------------------------------------------------------
    d = b.bakim_durumu(fid)
    olc("B01 bakim tanimsiz -> guncelleme var", d["guncelleme_hakki"])
    olc("B02 calisma hakki DAIMA true", d["calisma_hakki"] is True)

    # Bakimi gecmise cek
    db.calistir("UPDATE firmalar SET bakim_bitis = '2020-01-01' "
                "WHERE firma_id = %s", (fid,))
    d2 = b.bakim_durumu(fid)
    olc("B03 bakim bitmis -> guncelleme YOK",
        d2["guncelleme_hakki"] is False, str(d2))
    olc("B04 bakim bitmis -> CALISMA DEVAM",
        d2["calisma_hakki"] is True, "KRITIK ILKE")
    olc("B05 kalan gun negatif", d2["kalan_gun"] < 0)
    olc("B06 uyari bakim.bitti", d2["uyari"] == "bakim.bitti")
    ok, mesaj = b.guncelleme_alabilir_mi(fid)
    olc("B07 guncelleme reddi", ok is False)
    olc("B08 red mesaji calismaya devam der",
        "çalışmaya devam" in mesaj, mesaj)

    # 30 gun uyarisi
    db.calistir("UPDATE firmalar SET bakim_bitis = "
                "(CURRENT_DATE + INTERVAL '20 days')::date "
                "WHERE firma_id = %s", (fid,))
    d3 = b.bakim_durumu(fid)
    olc("B09 20 gun -> uyari30", d3["uyari"] == "bakim.uyari30", str(d3))
    olc("B10 20 gun -> guncelleme var", d3["guncelleme_hakki"])

    # 60 gun uyarisi
    db.calistir("UPDATE firmalar SET bakim_bitis = "
                "(CURRENT_DATE + INTERVAL '45 days')::date "
                "WHERE firma_id = %s", (fid,))
    d4 = b.bakim_durumu(fid)
    olc("B11 45 gun -> uyari60", d4["uyari"] == "bakim.uyari60", str(d4))

    # Uyari esigi disi
    db.calistir("UPDATE firmalar SET bakim_bitis = "
                "(CURRENT_DATE + INTERVAL '200 days')::date "
                "WHERE firma_id = %s", (fid,))
    d5 = b.bakim_durumu(fid)
    olc("B12 200 gun -> uyari yok", d5["uyari"] is None, str(d5))

    # Yenileme: gelecekteki bitisten uzatir
    onceki = d5["bakim_bitis"]
    ok, yeni = b.bakim_yenile(fid, 1)
    olc("B13 yenileme tamam", ok, yeni)
    olc("B14 gelecek bitisten uzatir", yeni > onceki, "%s -> %s" % (onceki, yeni))

    # Yenileme: gecmis bitisten BUGUNDEN uzatir
    db.calistir("UPDATE firmalar SET bakim_bitis = '2020-01-01' "
                "WHERE firma_id = %s", (fid,))
    ok, yeni2 = b.bakim_yenile(fid, 1)
    olc("B15 gecmis bitis bugunden uzatilir",
        yeni2.startswith("2027"), yeni2)

    # -----------------------------------------------------------------
    # 14. ODEMESIZLIK AKISI
    # -----------------------------------------------------------------
    db.calistir("UPDATE firmalar SET odeme_deneme = 0, "
                "  odemesiz_bitis = NULL, salt_okunur = FALSE "
                "WHERE firma_id = %s", (fid,))
    r1 = b.odeme_basarisiz(fid)
    olc("O01 1. deneme", r1["deneme"] == 1 and not r1["odemesiz"], str(r1))
    r2 = b.odeme_basarisiz(fid)
    olc("O02 2. deneme", r2["deneme"] == 2 and not r2["odemesiz"], str(r2))
    r3 = b.odeme_basarisiz(fid)
    olc("O03 3. deneme odemesiz baslar", r3["odemesiz"] is True, str(r3))
    olc("O04 3. denemede salt-okunur DEGIL",
        r3["salt_okunur"] is False, "7 gun tam yetki")

    od = b.odeme_durumu(fid)
    olc("O05 odemesiz bitis 7 gun sonra",
        od["odemesiz_kalan_gun"] == b.ODEMESIZ_GUN, str(od))
    olc("O06 hala salt-okunur degil", od["salt_okunur"] is False)
    olc("O07 uyari odeme.odemesiz", od["uyari"] == "odeme.odemesiz")

    # Odemesiz donem henuz bitmemis -> tarama dokunmamali
    dusen = [d["firma_id"] for d in b.odemesiz_donem_tara()]
    olc("O08 donem bitmeden dusmez", fid not in dusen)

    # Donemi gecmise cek -> tarama salt-okunur yapmali
    db.calistir("UPDATE firmalar SET odemesiz_bitis = "
                "(CURRENT_DATE - INTERVAL '1 day')::date "
                "WHERE firma_id = %s", (fid,))
    dusen2 = [d["firma_id"] for d in b.odemesiz_donem_tara()]
    olc("O09 donem bitince duser", fid in dusen2, str(dusen2))
    od2 = b.odeme_durumu(fid)
    olc("O10 salt-okunur oldu", od2["salt_okunur"] is True)
    olc("O11 uyari salt_okunur", od2["uyari"] == "odeme.salt_okunur")

    # KRITIK: veri silinmemis olmali
    hala = db.tek("SELECT firma_id, durum FROM firmalar WHERE firma_id = %s",
                  (fid,))
    olc("O12 firma SILINMEDI", hala is not None)
    olc("O13 firma durumu etkin kaldi", hala["durum"] == "etkin",
        "salt-okunur kip durumu degistirmez")

    # Odeme gelince tam geri donus
    b.odeme_basarili(fid)
    od3 = b.odeme_durumu(fid)
    olc("O14 odeme sonrasi salt-okunur kalkti",
        od3["salt_okunur"] is False)
    olc("O15 deneme sayaci sifirlandi", od3["deneme"] == 0)
    olc("O16 odemesiz bitis temizlendi",
        od3["odemesiz_bitis"] is None)

    # Ikinci kez tarama artik dokunmamali
    dusen3 = [d["firma_id"] for d in b.odemesiz_donem_tara()]
    olc("O17 odeme sonrasi tarama dokunmaz", fid not in dusen3)

    # -----------------------------------------------------------------
    # 15. PAKET GUNCELLEME (yonetim paneli)
    # -----------------------------------------------------------------
    ok, h = p.paket_guncelle("profesyonel", {"aylik_try": 1100})
    olc("P01 fiyat guncellendi", ok, h)
    olc("P02 yeni fiyat okundu",
        p.ham_fiyat("profesyonel", "aylik", "TRY") == 1100.0)
    olc("P03 onbellek bosaltildi (TTL beklenmedi)",
        p.ham_fiyat("profesyonel", "yillik", "TRY") == 10560.0)
    p.paket_guncelle("profesyonel", {"aylik_try": 990})
    olc("P04 geri alindi",
        p.ham_fiyat("profesyonel", "aylik", "TRY") == 990.0)

    # Beyaz liste: kimlik alani degistirilemez
    ok2, h2 = p.paket_guncelle("profesyonel", {"anahtar": "hacked"})
    olc("P05 anahtar degistirilemez", ok2 is False, h2)
    olc("P06 paket hala erisilebilir", p.paket_var_mi("profesyonel"))

    ok3, h3 = p.paket_guncelle("yok_boyle", {"aylik_try": 1})
    olc("P07 olmayan paket guncellenemez", ok3 is False, h3)

    # -----------------------------------------------------------------
    # 16. ONBELLEK
    # -----------------------------------------------------------------
    olc("C01 onbellek omru 60 sn", p.ONBELLEK_OMRU <= 60.0)
    p.onbellek_bosalt()
    olc("C02 bosaltma sonrasi katalog", len(p.katalog()) >= 16)

finally:
    # Temizlik — sinav firmasi ve iskontolari
    db.calistir("DELETE FROM iskontolar WHERE firma_id = %s", (fid,))
    db.calistir("DELETE FROM firmalar WHERE firma_id = %s", (fid,))
    kalan = db.deger("SELECT count(*) FROM firmalar WHERE kisa_ad = %s",
                     (SINAV_AD,))
    print("temizlik: kalan sinav firmasi = %s" % kalan)

print("\n=== FAZ 14 ISKONTO/FIYAT SINAVI ===")
print("GECTI : %d" % gecti)
print("KUSUR : %d" % len(kusur))
for k in kusur:
    print("  ! %s" % k)
sys.exit(1 if kusur else 0)
