import asyncio, json, subprocess, sys, time
from playwright.async_api import async_playwright

BELGE = {"lisans": {"surum": 1, "firma_id": 7, "firma_unvan": "Test", "yetkiler": {"ai": True}, "lisans_uid": "U1"},
         "imza": "SAHTEIMZA", "acik_anahtar": "ACIK"}
YANIT = {
  "/api/firma/ben": {"kullanici": {"rol": "firma_yonetici", "ad": "Test", "ad_soyad": "Test Yonetici", "firma_id": 7, "firma_unvan": "Test A.S."}},
  "/api/firma/abonelik": {"yetkiler": {"merkez_lisans": True, "ai": True, "sinirsiz": True, "radar": False, "gccdual": False,
                                        "abonelik": "sinirsiz", "fatura_donemi": "aylik", "hesap_kullanilan": 3},
                          "kalemler": [], "talepler": [], "fiyatlar": []},
  "/api/firma/odeme_durum": {"acik": False},
  "/api/firma/merkez_paketler": {"kayitlar": [], "lisans_uid": "U1"},
  "/api/firma/merkez_lisans": BELGE,
}

async def main():
    sv = subprocess.Popen([sys.executable, "-m", "http.server", "8124", "-d", "/site"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5); hatalar = []
    try:
        async with async_playwright() as pw:
            tar = await pw.chromium.launch()
            bag = await tar.new_context(viewport={"width": 1500, "height": 900}, accept_downloads=True)
            s = await bag.new_page()
            s.on("pageerror", lambda e: hatalar.append(str(e)))
            async def yol(route):
                u = route.request.url.split("127.0.0.1:8124")[1].split("?")[0]
                if u.startswith("/api/"):
                    await route.fulfill(status=200, content_type="application/json", body=json.dumps(YANIT.get(u, {})))
                else:
                    await route.continue_()
            await s.route("**/*", yol)
            for sayfa in ("abonelik", "merkez"):
                await s.goto("http://127.0.0.1:8124/index.html#" + sayfa, wait_until="load")
                await s.wait_for_timeout(2500)
                d = s.locator(".lisans-indir")
                n = await d.count()
                gor = n and await d.first.is_visible()
                print(f"[{sayfa}] dugme sayisi={n} gorunur={gor} metin={await d.first.inner_text() if n else '-'}")
                if sayfa == "abonelik":
                    kart = await s.evaluate("""() => { const b=document.querySelector('.lisans-indir'); const k=b&&b.closest('.yetki-kart'); return k? k.innerText.replace(/\\s+/g,' ').trim():null; }""")
                    print(f"[{sayfa}] bulundugu kart: {kart}")
                    await s.screenshot(path="/out/panel_abonelik.png", clip={"x":0,"y":0,"width":1500,"height":420})
                else:
                    metin = await s.evaluate("document.getElementById('icerik').innerText")
                    print(f"[{sayfa}] 'gömülüdür' kaldi mi: {'gömülüdür' in metin} | Windows yolu var: {'ProgramData' in metin}")
                if n:
                    async with s.expect_download() as bilgi:
                        await d.first.click()
                    ind = await bilgi.value
                    yolu = await ind.path()
                    icerik = json.load(open(yolu))
                    print(f"[{sayfa}] indirilen: {ind.suggested_filename} | icerik birebir: {icerik == BELGE}")
            await tar.close()
    finally:
        sv.terminate()
    print("JS hatasi:", hatalar or "YOK")
asyncio.run(main())
