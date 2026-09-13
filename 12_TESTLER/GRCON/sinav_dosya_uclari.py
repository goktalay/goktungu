import ast, sys, types, os, json, tempfile, hashlib
kaynak=open(sys.argv[1],encoding="utf-8").read()
agac=ast.parse(kaynak)
ISTER={"_gcs_lisans_dogrula","_kopru_kimlik_dogrula","_guncel_dosya_surum",
       "_dosya_kok_coz","_u_istemci_dosya_manifesti","_u_istemci_dosya"}
parca=[]
for n in agac.body:
    if isinstance(n,ast.FunctionDef) and n.name in ISTER:
        n.decorator_list=[]; parca.append(n)
mod=ast.Module(body=parca,type_ignores=[])

# temp dosya deposu
kok=tempfile.mkdtemp(prefix="gcsd_")
v="2.4.156"; os.makedirs(os.path.join(kok,v,"assets/web/js"))
open(os.path.join(kok,"GUNCEL"),"w").write(v+"\n")
man={"manifest":{"urun":"gcs","surum":v},"imza":"IMZAABC"}
open(os.path.join(kok,v,"MANIFEST.imzali.json"),"w").write(json.dumps(man))
open(os.path.join(kok,v,"assets/web/js/kameralar.js"),"wb").write(b"KAMBYTES")

import re as _re
ns=dict(os=os,json=json,_re=_re,GCS_DOSYA_KOK=kok,
        _GUNCELLEME_PAKET_URUNLERI=("gcs","kopru","video"))
# sahte bagimliliklar
D={"imza_ok":True,"uid_ok":True,"firma":{"durum":"etkin","merkez_lisans":True},"bakim":(True,"")}
ns["depo"]=types.SimpleNamespace(veri_imza_dogrula=lambda b,i: D["imza_ok"])
ns["yetki"]=types.SimpleNamespace(govde_bayt=lambda g:b"x",firma_yetkileri=lambda f:D["firma"])
ns["db"]=types.SimpleNamespace(deger=lambda q,a:1 if D["uid_ok"] else None,
        tek=lambda q,a:{"firma_id":7,"gizli_ozet":"OZ","durum":"etkin","firma_durum":"etkin"})
ns["bakim"]=types.SimpleNamespace(guncelleme_alabilir_mi=lambda f:D["bakim"])
ns["role"]=types.SimpleNamespace(gizli_dogrula=lambda g,o:g=="dogru")
exec(compile(mod,"uc","exec"),ns)

class H:
    def __init__(s): s.kod=None;s.json=None;s.akit=None
    def hata_yaz(s,k,m): s.kod=k;s.mesaj=m
    def json_yaz(s,v): s.kod=200;s.json=v
    def dosya_akit(s,p,n): s.kod=200;s.akit=(p,n)
class Ist:
    def __init__(s,g): s.govde=g
LIS={"lisans":{"firma_id":7,"lisans_uid":"U1"},"imza":"I"}
def coz(fn,g): h=H(); ns[fn](h,Ist(g),{}); return h

vak=[]
def v(ad,bek,g,fn="_u_istemci_dosya_manifesti",hazir=None):
    for k,val in (hazir or {}).items(): D[k]=val
    D["imza_ok"]=True;D["uid_ok"]=True;D["firma"]={"durum":"etkin","merkez_lisans":True};D["bakim"]=(True,"")
    for k,val in (hazir or {}).items(): D[k]=val
    h=coz(fn,g); vak.append((ad,bek,h.kod,h))

v("manifest: gecerli lisans",200,{"urun":"gcs","lisans":LIS})
v("manifest: bozuk lisans",403,{"urun":"gcs","lisans":LIS},hazir={"imza_ok":False})
v("manifest: urun yok",400,{})
v("manifest: bakim bitti",403,{"urun":"gcs","lisans":LIS},hazir={"bakim":(False,"Bakim bitti")})
v("dosya: gecerli",200,{"urun":"gcs","surum":"2.4.156","yol":"assets/web/js/kameralar.js","lisans":LIS},fn="_u_istemci_dosya")
v("dosya: dizin gezinme",404,{"urun":"gcs","surum":"2.4.156","yol":"../GUNCEL","lisans":LIS},fn="_u_istemci_dosya")
v("dosya: mutlak yol",404,{"urun":"gcs","surum":"2.4.156","yol":"/etc/passwd","lisans":LIS},fn="_u_istemci_dosya")
v("dosya: yok",404,{"urun":"gcs","surum":"2.4.156","yol":"assets/yok.js","lisans":LIS},fn="_u_istemci_dosya")
v("dosya: kopru gizli yanlis",403,{"urun":"kopru","surum":"2.4.156","yol":"x","gizli":"yanlis","kurulum_uid":"abc"},fn="_u_istemci_dosya")

hata=0
for ad,bek,kod,h in vak:
    ok=bek==kod; hata+=not ok
    ek=""
    if h.json: ek="(manifest döndü)"
    if h.akit: ek="akit=%s"%(h.akit[1])
    print(f"  {'GECTI' if ok else 'KALDI'} {ad:32} bek={bek} alinan={kod} {ek}")
# manifest içeriği doğru mu
hm=coz("_u_istemci_dosya_manifesti",{"urun":"gcs","lisans":LIS})
assert hm.json==man, "imzalı manifest birebir dönmeli"
# dosya baytı doğru mu (akit yolu)
hd=coz("_u_istemci_dosya",{"urun":"gcs","surum":"2.4.156","yol":"assets/web/js/kameralar.js","lisans":LIS})
assert open(hd.akit[0],"rb").read()==b"KAMBYTES"
print("  GECTI manifest içeriği + dosya baytı doğru")
print("SONUC: %d/%d"%(len(vak)-hata,len(vak))); sys.exit(1 if hata else 0)
