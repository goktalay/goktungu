import sys
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(args=["--use-gl=angle","--use-angle=swiftshader","--ignore-gpu-blocklist","--no-sandbox"])
    pg=b.new_page(viewport={"width":1400,"height":900})
    hatalar=[]; konsol=[]
    pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.on("console", lambda m: konsol.append(m.type+": "+m.text[:160]))
    pg.route("**/*", lambda r: r.continue_() if r.request.url.startswith("http://127.0.0.1") else r.abort())
    pg.add_init_script("window.WebSocket=function(){return{readyState:1,send(){},close(){},addEventListener(){},removeEventListener(){}};};window.ws={readyState:1,send(){},close(){}};")
    pg.goto("http://127.0.0.1:8799/index.html", wait_until="commit", timeout=60000)
    pg.wait_for_function("typeof viewer!=='undefined'&&viewer&&viewer.entities&&typeof telemetriIsle==='function'&&window.IkonMuh", timeout=120000)
    pg.wait_for_timeout(1000)
    # kame: dronun yakinina odakla + sahte dron besle (ucak)
    pg.evaluate("""() => {
      const d={sysid:77,isim:'CAYMAZ',baglanti:true,lat:39.925,lon:32.836,alt_rel:150,
        heading:90,pitch:6,roll:-8,mod:'AUTO',armed:true,arac_tipi:1,baglanti_id:''};
      telemetriIsle({tip:'telemetri',dronlar:[d],konsol:[],baglanti_durumlari:{}});
      viewer.camera.flyTo({destination:Cesium.Cartesian3.fromDegrees(32.836,39.923,900),duration:0});
    }""")
    pg.wait_for_timeout(3500)
    sonuc=pg.evaluate("""() => {
      const e=viewer.entities.getById('dron_77__r3');
      const out={rigVar:!!e, modelVar:!!(e&&e.model)};
      out.hazir = (window.IkonMuh&&window.IkonMuh.hazir())?true:false;
      // model yuklendi mi? primitive say
      let modelPrim=0; try{ const ps=viewer.scene.primitives; for(let i=0;i<ps.length;i++){const g=ps.get(i); if(g&&g.constructor&&/Model/.test(g.constructor.name))modelPrim++;} }catch(e){}
      out.modelPrimitive=modelPrim;
      const ana=viewer.entities.getById('dron_77'); out.eskiBillboardShow = ana&&ana.billboard?ana.billboard.show:'yok';
      return out;
    }""")
    print("SONUC:", sonuc)
    print("HATA:", len(hatalar), hatalar[:4])
    glberr=[c for c in konsol if 'glb' in c.lower() or 'model' in c.lower() or 'fail' in c.lower() or 'error' in c.lower()]
    print("KONSOL(model/hata):", glberr[:6])
    pg.screenshot(path="/src/ikon3d_model.png")
    b.close()
