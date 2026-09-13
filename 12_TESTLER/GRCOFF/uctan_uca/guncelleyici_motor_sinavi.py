import sys, os, json, hashlib, tempfile, shutil
sys.path.insert(0, "/root/grcoff_2526_build/src")          # goktungu + guncelleyici
sys.path.insert(0, "/opt/goktungu/merkez/python")          # mk_depo (imza)
import mk_depo
from goktungu import lisans
import goktungu_guncelleyici as gg

def sha(b): return hashlib.sha256(b).hexdigest()
def yaz(p, b):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "wb").write(b if isinstance(b,bytes) else b.encode())

kok = tempfile.mkdtemp(prefix="gg_kok_")
# v1 kurulum
yaz(os.path.join(kok,"main.py"), b"MAIN_A")
yaz(os.path.join(kok,"assets/web/js/kameralar.js"), b"KAM_A")
yaz(os.path.join(kok,"assets/python/goktungu/sunucu.py"), b"SUN_A")
yaz(os.path.join(kok,"assets/web/js/eski.js"), b"ESKI")
yaz(os.path.join(kok,"ai_modeller/x.onnx"), b"MODEL_A")
yaz(os.path.join(kok,"veri/pg.json"), b"SECRET-PG")          # KORUNAN
yaz(os.path.join(kok,"veri/merkez_lisans.json"), b"LISANS")  # KORUNAN

# v2 sunucu içerikleri
v2 = {
  "assets/web/js/kameralar.js": b"KAM_B_DEGISTI",
  "assets/web/js/kamera_ai_panel.js": b"YENI_MODUL_B",
  "assets/python/goktungu/sunucu.py": b"SUN_A",   # AYNI
  "main.py": b"MAIN_A",                            # AYNI
  "ai_modeller/x.onnx": b"MODEL_A",                # AYNI
}
manifest = {
  "urun": "gcs", "surum": "2.4.156", "paket_surum": "2.5.26",
  "acik_anahtar": lisans.ACIK_ANAHTAR_B64,
  "dosyalar": [{"yol": y, "sha256": sha(b), "boyut": len(b)} for y,b in v2.items()],
  "silinecekler": ["assets/web/js/eski.js"],
}
imza = mk_depo.veri_imzala(lisans.govde_bayt(manifest))
imzali = {"manifest": manifest, "imza": imza}

class Motor(gg.GuncellemeMotoru):
    inen = []
    def _getir_manifest(self): return imzali
    def _dosya_getir(self, surum, bagil):
        Motor.inen.append(bagil); return v2[bagil]

cagri = []
m = Motor(kok, "gcs", "2.4.155", lisans_belgesi={"lisans":{"firma_id":1}}, gunluk=lambda *a: None)
sonuc = m.uygula(dur_geri_cagir=lambda: cagri.append("dur"),
                 baslat_geri_cagir=lambda: cagri.append("baslat"))
print("SONUC:", sonuc)
print("İNEN dosyalar:", sorted(Motor.inen))
def oku(p): return open(os.path.join(kok,p),"rb").read()
print("kameralar.js:", oku("assets/web/js/kameralar.js"))
print("yeni modül:", oku("assets/web/js/kamera_ai_panel.js"))
print("eski.js silindi:", not os.path.exists(os.path.join(kok,"assets/web/js/eski.js")))
print("pg.json KORUNDU:", oku("veri/pg.json"))
print("çağrı sırası:", cagri)
assert sonuc["guncellendi"] and sonuc["surum"]=="2.4.156"
assert sorted(Motor.inen)==["assets/web/js/kamera_ai_panel.js","assets/web/js/kameralar.js"], "yalnız değişen/yeni inmeli"
assert oku("assets/web/js/kameralar.js")==b"KAM_B_DEGISTI"
assert oku("assets/web/js/kamera_ai_panel.js")==b"YENI_MODUL_B"
assert not os.path.exists(os.path.join(kok,"assets/web/js/eski.js"))
assert oku("veri/pg.json")==b"SECRET-PG" and oku("veri/merkez_lisans.json")==b"LISANS"
assert cagri==["dur","baslat"]
print("✓ TEMEL AKIŞ GEÇTİ")

# --- Güvenlik: bozuk imza reddedilmeli ---
kok2=tempfile.mkdtemp(prefix="gg2_"); yaz(os.path.join(kok2,"main.py"),b"A")
kotu={"manifest":manifest,"imza":"AAAA"}
class M2(gg.GuncellemeMotoru):
    def _getir_manifest(self): return kotu
    def _dosya_getir(self,s,b): raise AssertionError("indirmemeli")
r2=M2(kok2,"gcs","2.4.155",gunluk=lambda *a:None).uygula()
print("bozuk imza:", r2); assert not r2["guncellendi"]
print("✓ BOZUK İMZA REDDEDİLDİ")

# --- Güvenlik: dizin gezinme + korunan yol atlanmalı ---
kots=dict(manifest); kots=json.loads(json.dumps(manifest))
kots["dosyalar"].append({"yol":"../disari.py","sha256":sha(b"x"),"boyut":1})
kots["dosyalar"].append({"yol":"veri/pg.json","sha256":sha(b"HACK"),"boyut":4})
imza3=mk_depo.veri_imzala(lisans.govde_bayt(kots))
class M3(gg.GuncellemeMotoru):
    inen=[]
    def _getir_manifest(self): return {"manifest":kots,"imza":imza3}
    def _dosya_getir(self,s,b): M3.inen.append(b); return v2.get(b,b"x")
kok3=tempfile.mkdtemp(prefix="gg3_")
for y,b in v2.items(): yaz(os.path.join(kok3,y),b)
yaz(os.path.join(kok3,"veri/pg.json"), b"SECRET")
M3(kok3,"gcs","2.4.155",gunluk=lambda *a:None).uygula(dur_geri_cagir=lambda:None,baslat_geri_cagir=lambda:None)
print("indirilenler(m3):", M3.inen)
assert "../disari.py" not in M3.inen and "veri/pg.json" not in M3.inen
assert not os.path.exists("/tmp/disari.py")
assert open(os.path.join(kok3,"veri/pg.json"),"rb").read()==b"SECRET"
print("✓ DİZİN GEZİNME + KORUNAN YOL ATLANDI")

for d in (kok,kok2,kok3): shutil.rmtree(d, ignore_errors=True)
print("\nTÜM MOTOR TESTLERİ GEÇTİ")
