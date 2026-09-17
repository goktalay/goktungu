"""K2 protokol katmanı birim testleri (G/Ç yok)."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "14_PRNFRM" / "KAYNAK"))

from prnfrm import k2_protokol as P  # noqa: E402
from prnfrm.olaylar import (O_BASKI_BASLADI, O_BASKI_BITTI, O_HATA, O_KOPTU,  # noqa: E402
                            gecis_olaylari)


class MesajTesti(unittest.TestCase):
    def test_get_istegi(self):
        self.assertEqual(json.loads(P.istek_get("ReqPrinterPara")),
                         {"method": "get", "params": {"ReqPrinterPara": 1}})
        self.assertEqual(json.loads(P.istek_get("pFileList", onePageNum=50)),
                         {"method": "get", "params": {"pFileList": 1, "onePageNum": 50}})

    def test_set_komutlari(self):
        self.assertEqual(json.loads(P.komut_duraklat()), {"method": "set", "params": {"pause": 1}})
        self.assertEqual(json.loads(P.komut_surdur()), {"method": "set", "params": {"pause": 0}})
        self.assertEqual(json.loads(P.komut_durdur()), {"method": "set", "params": {"stop": 1}})
        self.assertEqual(json.loads(P.komut_isik(True))["params"], {"lightSw": 1})
        self.assertEqual(json.loads(P.komut_tabla_sicaklik(60))["params"], {"bedTempControl": {"num": 0, "val": 60}})
        self.assertEqual(json.loads(P.komut_fan(250))["params"], {"fan": 100})

    def test_kalp_atisi(self):
        self.assertTrue(P.kalp_atisi_mi({"ModeCode": "heart_beat"}))
        self.assertFalse(P.kalp_atisi_mi({"state": 1}))
        self.assertIsNone(P.cozumle("ok"))
        self.assertIsNone(P.cozumle("bozuk{"))
        self.assertEqual(P.cozumle('{"a":1}'), {"a": 1})
        self.assertEqual(P.KALP_ATISI_YANIT, "ok")

    def test_sayilastir(self):
        self.assertEqual(P.sayilastir("215.5"), 215.5)
        self.assertEqual(P.sayilastir("60"), 60)
        self.assertEqual(P.sayilastir("abc"), "abc")
        self.assertEqual(P.sayilastir({"a": "1", "b": ["2", True]}), {"a": 1, "b": [2, True]})


class DurumTesti(unittest.TestCase):
    def test_bosta(self):
        self.assertEqual(P.durum_turet({"state": 0, "printProgress": 0}), P.D_BOSTA)
        self.assertEqual(P.durum_turet({}), P.D_BOSTA)

    def test_basiyor(self):
        self.assertEqual(P.durum_turet({"state": 1, "printFileName": "a.gcode", "printProgress": 42}), P.D_BASIYOR)
        # state alanı olmadan da dosya + ilerleme yeterli
        self.assertEqual(P.durum_turet({"printFileName": "a.gcode", "printProgress": "42"}), P.D_BASIYOR)

    def test_duraklatildi_ve_tamamlandi(self):
        self.assertEqual(P.durum_turet({"state": 5, "printFileName": "a", "printProgress": 40}), P.D_DURAKLATILDI)
        self.assertEqual(P.durum_turet({"state": 1, "pause": 1, "printFileName": "a", "printProgress": 40}), P.D_DURAKLATILDI)
        self.assertEqual(P.durum_turet({"state": 2, "printFileName": "a", "printProgress": 100}), P.D_TAMAMLANDI)
        self.assertEqual(P.durum_turet({"printFileName": "a", "printProgress": 100}), P.D_TAMAMLANDI)

    def test_hata_ve_hazirlaniyor(self):
        self.assertEqual(P.durum_turet({"err": {"errcode": 2001, "key": "E2001"}, "state": 1}), P.D_HATA)
        self.assertEqual(P.durum_turet({"err": {"errcode": 0}, "state": 0}), P.D_BOSTA)
        self.assertEqual(P.durum_turet({"deviceState": 7}), P.D_HAZIRLANIYOR)

    def test_ozet(self):
        o = P.ozet({"hostname": "K2Plus-01", "model": "K2 Plus", "nozzleTemp": "215.4", "targetNozzleTemp": 220,
                    "bedTemp0": 60, "targetBedTemp0": 60, "boxTemp": 35, "printFileName": "x.gcode",
                    "printProgress": 55, "printLeftTime": 1234, "layer": 10, "TotalLayer": 20,
                    "materialStatus": 1, "lightSw": 1, "state": 1})
        self.assertEqual(o["durum"], P.D_BASIYOR)
        self.assertEqual(o["nozul"], 215.4)
        self.assertEqual(o["kalan_sn"], 1234)
        self.assertTrue(o["filament_yok"])
        self.assertEqual(o["hostname"], "K2Plus-01")
        self.assertEqual(o["katman"], 10)


class OlayTesti(unittest.TestCase):
    def test_gecisler(self):
        e = {"baglanti": "bagli", "durum": P.D_BOSTA}
        y = {"baglanti": "bagli", "durum": P.D_BASIYOR, "dosya": "a.gcode"}
        turler = [t for t, _, _ in gecis_olaylari("Y1", e, y)]
        self.assertEqual(turler, [O_BASKI_BASLADI])
        y2 = {"baglanti": "bagli", "durum": P.D_TAMAMLANDI, "dosya": "a.gcode"}
        self.assertEqual([t for t, _, _ in gecis_olaylari("Y1", y, y2)], [O_BASKI_BITTI])
        y3 = {"baglanti": "kopuk", "durum": P.D_CEVRIMDISI}
        self.assertEqual([t for t, _, _ in gecis_olaylari("Y1", y2, y3)], [O_KOPTU])
        y4 = {"baglanti": "bagli", "durum": P.D_HATA, "hata_kodu": 5, "hata_anahtari": "E5"}
        self.assertEqual([t for t, _, _ in gecis_olaylari("Y1", y, y4)], [O_HATA])

    def test_verisiz_ve_cevrimdisi_gecis_olay_uretmez(self):
        # Bağlandı ama telemetri gelmedi (bosta görünür) → ilk telemetri "basiyor": olay yok
        e = {"baglanti": "bagli", "durum": P.D_BOSTA, "veri_var": False}
        y = {"baglanti": "bagli", "durum": P.D_BASIYOR, "dosya": "a", "veri_var": True}
        self.assertEqual(gecis_olaylari("Y1", e, y), [])
        # Çevrimdışıdan dönüşte süren baskı "başladı" sayılmaz, ama hata bildirilir
        e = {"baglanti": "kopuk", "durum": P.D_CEVRIMDISI, "veri_var": True}
        self.assertEqual([t for t, _, _ in gecis_olaylari("Y1", e, y)], ["baglandi"])
        y_h = {"baglanti": "bagli", "durum": P.D_HATA, "hata_kodu": 3, "veri_var": True}
        self.assertEqual([t for t, _, _ in gecis_olaylari("Y1", e, y_h)], ["baglandi", O_HATA])

    def test_ilk_ozet_olay_uretmez(self):
        # İlk gelen özet (eski=None) sahte "başladı" olayı üretmemeli; yalnız bağlantı olayı
        y = {"baglanti": "bagli", "durum": P.D_BASIYOR, "dosya": "a"}
        turler = [t for t, _, _ in gecis_olaylari("Y1", None, y)]
        self.assertEqual(turler, ["baglandi"])


if __name__ == "__main__":
    unittest.main()
