"""Uçtan uca: sahte yazıcılar + tarayıcı + filo + web API (gerçek soketler, loopback)."""
import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path

KAYNAK = Path(__file__).resolve().parents[2] / "14_PRNFRM" / "KAYNAK"
sys.path.insert(0, str(KAYNAK))
sys.path.insert(0, str(KAYNAK / "araclar"))

from aiohttp.test_utils import TestClient, TestServer  # noqa: E402

from prnfrm import k2_protokol as P  # noqa: E402
from prnfrm.filo import Filo  # noqa: E402
from prnfrm.tarayici import Tarama, hostlar, kimlik_sor  # noqa: E402
from prnfrm.veritabani import Veritabani  # noqa: E402
from prnfrm.web import uygulama_olustur  # noqa: E402
from sahte_yazici import filo_kur  # noqa: E402

PORT = int(os.environ.get("PRNFRM_TEST_PORT", "19999"))   # 9999 makinede dolu olabilir


async def bekle(kosul, sn=8.0, adim=0.05):
    son = asyncio.get_running_loop().time() + sn
    while asyncio.get_running_loop().time() < son:
        if kosul():
            return True
        await asyncio.sleep(adim)
    return kosul()


class TarayiciTesti(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.sahte = await filo_kur(3, baslangic=2, port=PORT, hizli=True)

    async def asyncTearDown(self):
        for y in self.sahte:
            await y.durdur()

    def test_hostlar(self):
        self.assertEqual(len(hostlar("127.0.0.0/29")), 6)
        with self.assertRaises(ValueError):
            hostlar("10.0.0.0/8")

    async def test_kimlik(self):
        k = await kimlik_sor("127.0.0.2", PORT, bekleme=3)
        self.assertTrue(k["ws"])
        self.assertEqual(k["hostname"], "K2Plus-01")
        self.assertEqual(k["model"], "K2 Plus")

    async def test_tarama_bulur(self):
        ilerlemeler = []
        t = Tarama("127.0.0.0/28", PORT, zaman_asimi=0.5, on_ilerleme=lambda x: ilerlemeler.append(x.asama))
        await t.calistir()
        self.assertEqual(t.asama, "bitti")
        self.assertEqual([b["ip"] for b in t.bulunan], ["127.0.0.2", "127.0.0.3", "127.0.0.4"])
        self.assertEqual({b["model"] for b in t.bulunan}, {"K2 Plus"})
        self.assertIn("port", ilerlemeler)
        self.assertEqual(t.taranan, t.toplam)


class FiloVeApiTesti(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.sahte = await filo_kur(2, baslangic=2, port=PORT, hizli=True)
        self.sahte[0].baski_baslat("kapak.gcode", katman=10)
        self.tmp = tempfile.TemporaryDirectory()
        self.vt = Veritabani(Path(self.tmp.name) / "t.sqlite")
        self.filo = Filo(self.vt)
        await self.filo.baslat()
        self.app = uygulama_olustur(self.filo)
        self.client = TestClient(TestServer(self.app))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()   # on_shutdown → filo.durdur()
        self.vt.kapat()
        self.tmp.cleanup()
        for y in self.sahte:
            await y.durdur()

    async def test_ekle_izle_komut_sil(self):
        r = await self.client.post("/api/yazicilar", json={"ad": "Hat1-Y1", "ip": "127.0.0.2", "port": PORT, "grup": "Hat-1"})
        self.assertEqual(r.status, 201)
        yid = (await r.json())["yazici"]["id"]
        # Aynı IP ikinci kez eklenemez
        r = await self.client.post("/api/yazicilar", json={"ad": "x", "ip": "127.0.0.2", "port": PORT})
        self.assertEqual(r.status, 409)

        ok = await bekle(lambda: self.filo.yazici_gorunum(yid)["canli"]["durum"] == P.D_BASIYOR)
        self.assertTrue(ok, self.filo.yazici_gorunum(yid))
        g = self.filo.yazici_gorunum(yid)
        self.assertEqual(g["canli"]["dosya"], "kapak.gcode")
        self.assertEqual(g["canli"]["baglanti"], "bagli")
        # hostname/model kalıcı kayda işlendi
        self.assertEqual(self.vt.yazici(yid)["hostname"], "K2Plus-01")
        self.assertEqual(self.vt.yazici(yid)["model"], "K2 Plus")

        # Duraklat komutu sahte yazıcıya ulaşır ve durum değişir
        r = await self.client.post(f"/api/yazicilar/{yid}/komut", json={"komut": "duraklat"})
        self.assertEqual((await r.json())["gonderildi"], True)
        self.assertTrue(await bekle(lambda: {"pause": 1} in self.sahte[0].gelen_komutlar))
        self.assertTrue(await bekle(lambda: self.filo.yazici_gorunum(yid)["canli"]["durum"] == P.D_DURAKLATILDI))
        r = await self.client.post(f"/api/yazicilar/{yid}/komut", json={"komut": "yok"})
        self.assertEqual(r.status, 400)

        # Olaylar kaydedildi
        turler = [o["tur"] for o in self.vt.olaylar(100, yid)]
        self.assertIn("baglandi", turler)
        self.assertIn("duraklatildi", turler)

        # Liste ve ayrıntı uçları
        r = await self.client.get("/api/yazicilar")
        v = await r.json()
        self.assertEqual(v["sayilar"]["toplam"], 1)
        r = await self.client.get(f"/api/yazicilar/{yid}")
        v = await r.json()
        self.assertEqual(v["ham"]["hostname"], "K2Plus-01")

        # Güncelle: IP değişince yeniden bağlanır
        r = await self.client.put(f"/api/yazicilar/{yid}", json={"ip": "127.0.0.3", "ad": "Hat1-Y1b"})
        self.assertEqual(r.status, 200)
        self.assertTrue(await bekle(lambda: self.filo.yazici_gorunum(yid)["canli"].get("hostname") == "K2Plus-02"))

        # Sil
        r = await self.client.delete(f"/api/yazicilar/{yid}")
        self.assertEqual(r.status, 200)
        self.assertEqual(self.vt.yazicilar(), [])
        self.assertNotIn(yid, self.filo.baglantilar)

    async def test_kopuk_yazici_cevrimdisi(self):
        r = await self.client.post("/api/yazicilar", json={"ad": "Yok", "ip": "127.0.0.9", "port": PORT})
        yid = (await r.json())["yazici"]["id"]
        await asyncio.sleep(0.5)
        g = self.filo.yazici_gorunum(yid)
        self.assertEqual(g["canli"]["durum"], P.D_CEVRIMDISI)
        self.assertIn(g["canli"]["baglanti"], ("kopuk", "baglaniyor"))

    async def test_tarama_ve_toplu_ekle(self):
        r = await self.client.post("/api/tarama", json={"cidr": "127.0.0.0/29", "port": PORT})
        self.assertEqual(r.status, 202)
        r = await self.client.post("/api/tarama", json={"cidr": "127.0.0.0/29", "port": PORT})
        self.assertEqual(r.status, 409)   # eşzamanlı ikinci tarama yok
        self.assertTrue(await bekle(lambda: self.filo.tarama and self.filo.tarama.asama == "bitti", sn=15))
        r = await self.client.get("/api/tarama")
        t = (await r.json())["tarama"]
        self.assertEqual([b["ip"] for b in t["bulunan"]], ["127.0.0.2", "127.0.0.3"])
        self.assertFalse(t["bulunan"][0]["kayitli"])
        r = await self.client.post("/api/yazicilar/toplu", json={"yazicilar": [
            {"ip": b["ip"], "ad": b["hostname"], "port": b["port"], "model": b["model"], "hostname": b["hostname"]} for b in t["bulunan"]]})
        v = await r.json()
        self.assertEqual(len(v["eklenen"]), 2)
        r = await self.client.get("/api/tarama")
        self.assertTrue(all(b["kayitli"] for b in (await r.json())["tarama"]["bulunan"]))

    async def test_ws_yayini(self):
        ws = await self.client.ws_connect("/ws")
        ilk = await ws.receive_json()
        self.assertEqual(ilk["tur"], "anlik")
        await self.client.post("/api/yazicilar", json={"ad": "Y", "ip": "127.0.0.2", "port": PORT})
        turler = set()
        for _ in range(20):
            m = await asyncio.wait_for(ws.receive_json(), timeout=5)
            turler.add(m["tur"])
            if "yazici" in turler and "olay" in turler:
                break
        self.assertIn("yazici", turler)
        self.assertIn("olay", turler)
        await ws.close()

    async def test_statik_sayfa(self):
        r = await self.client.get("/")
        self.assertEqual(r.status, 200)
        self.assertIn("Yazıcı Filo Merkezi", await r.text())
        r = await self.client.get("/api/surum")
        self.assertEqual((await r.json())["urun"], "PRNFRM")


if __name__ == "__main__":
    unittest.main()
