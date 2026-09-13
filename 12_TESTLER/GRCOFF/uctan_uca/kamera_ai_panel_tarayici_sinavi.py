import asyncio, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); p = await b.new_page()
        hata=[]; p.on("pageerror", lambda e: hata.append(str(e)))
        await p.goto("http://127.0.0.1:8125/test/harness.html", wait_until="load")
        await p.wait_for_timeout(300)
        # kamera enjekte et
        await p.evaluate("""() => { window._kameralarSon = [
          {id:7, isim:'Kule Kamerası', protokol:'rtsp', url:'rtsp://x', dron_uid:'D1',
           ai_gorevler:'hava_araci', ai_hassasiyet:'{"hava_araci":70}'} ]; }""")
        r = {}
        r['fabrikalar'] = await p.evaluate("""() => ({
          aiBtn: typeof window.kameraAiAyarButonu,
          secici: typeof window.kameraGoruntuHedefSecici,
          hedefGet: typeof window.kameraGoruntuHedefi,
          hedefSet: typeof window.kameraGoruntuHedefiAyarla,
          panelAc: typeof window.kameraAiAyarPanelAc })""")
        # AI paneli aç, collapsible sınıflar var mı
        await p.evaluate("window.kameraAiAyarPanelAc(7)")
        await p.wait_for_timeout(150)
        r['panel'] = await p.evaluate("""() => {
          const el=document.querySelector('.kai-panel'); if(!el) return null;
          return { siniflar: el.querySelectorAll('.kai-sinif').length,
                   acikKutu: el.querySelectorAll('.kai-acik').length,
                   slider: el.querySelectorAll('.kai-hassas').length,
                   havaAcik: el.querySelectorAll('.kai-sinif')[2].open,
                   havaSlider: el.querySelectorAll('.kai-hassas')[2].value }; }""")
        # insan sınıfını aç -> kamera_kaydet mesajı gitmeli
        await p.evaluate("""() => { const cb=document.querySelectorAll('.kai-acik')[0];
          cb.checked=true; cb.dispatchEvent(new Event('change')); }""")
        await p.wait_for_timeout(100)
        r['kayit'] = await p.evaluate("() => window._wsMesajlari.slice(-1)[0]")
        # hava hassasiyetini 30 yap
        await p.evaluate("""() => { const s=document.querySelectorAll('.kai-hassas')[2];
          s.value='30'; s.dispatchEvent(new Event('change')); }""")
        await p.wait_for_timeout(100)
        r['kayit2'] = await p.evaluate("() => window._wsMesajlari.slice(-1)[0]")
        # görüntü hedefi seçici: panel'e geç
        r['hedefOnce'] = await p.evaluate("() => window.kameraGoruntuHedefi(7)")
        await p.evaluate("() => window.kameraGoruntuHedefiAyarla(7,'tam')")
        r['hedefSonra'] = await p.evaluate("() => window.kameraGoruntuHedefi(7)")
        r['uygulandi'] = await p.evaluate("() => window._uygulandi")
        # seçici DOM
        await p.evaluate("() => document.body.appendChild(window.kameraGoruntuHedefSecici(7))")
        r['secici'] = await p.evaluate("""() => {
          const s=document.querySelector('.kam-hedef-secici');
          return { btn: s.querySelectorAll('.kam-hedef-btn').length,
                   secili: s.querySelector('.kam-hedef-btn.secili')?.dataset.hedef }; }""")
        r['hata'] = hata
        print(json.dumps(r, ensure_ascii=False, indent=1))
        await b.close()
asyncio.run(main())
