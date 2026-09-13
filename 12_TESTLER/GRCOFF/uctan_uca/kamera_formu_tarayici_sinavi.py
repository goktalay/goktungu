import asyncio, subprocess, sys, time
from playwright.async_api import async_playwright

async def durum(s):
    return await s.evaluate("""() => ({
      genel: document.getElementById('kamBolumGenel')?.open,
      ai: document.getElementById('kamBolumAi')?.open,
      kalib: document.getElementById('kamBolumKalib')?.open,
      rozetAi: document.getElementById('kamRozetAi')?.textContent,
      rozetKalib: document.getElementById('kamRozetKalib')?.textContent,
      kutular: ['kamAiYuz','kamAiPlaka','kamAiHava','kamAiInsan','kamAiKara'].filter(i=>document.getElementById(i)).length,
      modalAcik: !document.getElementById('kamModalPerde').classList.contains('popup-gizli'),
      kutuYukseklik: Math.round(document.getElementById('kamModalKutu').getBoundingClientRect().height),
      kaydetGorunur: (()=>{const b=document.getElementById('btnKamKaydet').getBoundingClientRect(); return b.height>0 && b.bottom<=innerHeight;})(),
    })""")

async def foto(s, ad):
    try:
        b = await s.evaluate("(()=>{const r=document.getElementById('kamModalKutu').getBoundingClientRect(); return [r.left,r.top,r.width,r.height];})()")
        await s.screenshot(path="/out/"+ad, clip={"x":b[0],"y":b[1],"width":b[2],"height":min(b[3],900-b[1])}, timeout=90000, animations="disabled", caret="hide")
        print("   foto:", ad)
    except Exception as e:
        print("   foto alinamadi:", ad, str(e)[:80])

async def main():
    sv = subprocess.Popen([sys.executable, "-m", "http.server", "8123", "-d", "/src"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5); hatalar = []
    try:
        async with async_playwright() as pw:
            tar = await pw.chromium.launch()
            s = await (await tar.new_context(viewport={"width": 1600, "height": 900})).new_page()
            s.on("pageerror", lambda e: hatalar.append(str(e)))
            await s.goto("http://127.0.0.1:8123/index.html", wait_until="load")
            await s.wait_for_timeout(4000)
            await s.evaluate("document.getElementById('tbYeniKamera').click()")
            await s.wait_for_timeout(600)
            d = await durum(s); print("1) Yeni kamera acildi:", d)
            await foto(s, "form_1_kapali.png")
            await s.locator("#kamBolumAi > summary").click(); await s.wait_for_timeout(200)
            await s.locator("label:has(#kamAiHava)").click(); await s.wait_for_timeout(100)
            await s.locator("label:has(#kamAiInsan)").click(); await s.wait_for_timeout(200)
            d = await durum(s); print("2) AI acildi + 2 gorev:", d)
            await s.locator("#kamBolumKalib > summary").click(); await s.wait_for_timeout(300)
            d = await durum(s); print("3) Kalibrasyon da acik:", d)
            await foto(s, "form_2_acik.png")
            # Dogrulama: Genel kapaliyken bos adla kaydet -> Genel acilmali
            await s.locator("#kamBolumGenel > summary").click(); await s.wait_for_timeout(200)
            print("4a) Genel kapatildi:", (await durum(s))["genel"])
            await s.evaluate("document.getElementById('btnKamKaydet').click()"); await s.wait_for_timeout(200)
            print("4b) Bos ad ile kaydet -> genel:", (await durum(s))["genel"],
                  "| hata:", await s.evaluate("document.getElementById('kamHata').textContent"))
            # ai_gorevler okuma yolu: gonderilecek CSV
            print("5) secili kutular:", await s.evaluate("['kamAiYuz','kamAiPlaka','kamAiHava','kamAiInsan','kamAiKara'].filter(i=>document.getElementById(i).checked).map(i=>document.getElementById(i).value).join(',')"))
            await tar.close()
    finally:
        sv.terminate()
    ilgili = [h for h in hatalar if "kameralar" in h or "i18n" in h or "bolum" in h.lower()]
    print("kameralar/i18n ile ilgili JS hatasi:", ilgili or "YOK", "| toplam pageerror:", len(hatalar))
asyncio.run(main())
