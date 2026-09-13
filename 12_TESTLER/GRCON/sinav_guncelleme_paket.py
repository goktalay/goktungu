"""_u_istemci_guncelleme_paket icin DB'siz birim sinavi (sahte bagimliliklar)."""
import ast, sys, types

kaynak = open(sys.argv[1], encoding="utf-8").read()
agac = ast.parse(kaynak)
parca = [n for n in agac.body if isinstance(n, (ast.FunctionDef, ast.Assign))
         and (getattr(n, "name", "") == "_u_istemci_guncelleme_paket"
              or any(getattr(t, "id", "") == "_GUNCELLEME_PAKET_URUNLERI" for t in getattr(n, "targets", [])))]
assert len(parca) == 2, parca
for p in parca:
    if isinstance(p, ast.FunctionDef):
        p.decorator_list = []
mod = ast.Module(body=parca, type_ignores=[])

class H:
    def __init__(s): s.kod=None; s.akit=None
    def hata_yaz(s, kod, m): s.kod=kod; s.mesaj=m
    def dosya_akit(s, hedef, ad): s.kod=200; s.akit=(hedef, ad)
    def _kk_es(s): return "1.2.3.4"

class Durum: pass
D = Durum()
def sifirla():
    D.imza_gecerli=True; D.uid_kayitli=True; D.firma={"durum":"etkin","merkez_lisans":True}
    D.bakim=(True,""); D.kopru={"firma_id":7,"gizli_ozet":"OZ","durum":"etkin","firma_durum":"etkin"}
    D.kayit={"surum_id":141}; D.dosya="/depo/gcs/2.5.21/X.exe"; D.sayac=[]; D.indirme=[]

db = types.SimpleNamespace(
    deger=lambda q,a: 1 if D.uid_kayitli else None,
    tek=lambda q,a: (D.kopru if "sunucu_ornekleri" in q else D.kayit),
    calistir=lambda q,a: D.sayac.append(a))
depo = types.SimpleNamespace(veri_imza_dogrula=lambda b,i: D.imza_gecerli,
    indirme_coz=lambda u,s,d: D.dosya, indirme_say=lambda sid,ip: D.indirme.append((sid,ip)))
yetki = types.SimpleNamespace(govde_bayt=lambda g: b"x", firma_yetkileri=lambda f: D.firma)
bakim = types.SimpleNamespace(guncelleme_alabilir_mi=lambda f: D.bakim)
role = types.SimpleNamespace(gizli_dogrula=lambda g,o: g=="dogru")
ns = dict(db=db, depo=depo, yetki=yetki, bakim=bakim, role=role)
exec(compile(mod, "uc", "exec"), ns)
uc = ns["_u_istemci_guncelleme_paket"]

LIS = {"lisans": {"firma_id": 7, "lisans_uid": "U1"}, "imza": "IMZA", "acik_anahtar": "A"}
def cagir(govde):
    h=H(); uc(h, types.SimpleNamespace(govde=govde), {}); return h
def gcs(**e):
    g={"urun":"gcs","surum":"2.5.21","platform":"windows","dosya":"X.exe","lisans":LIS}; g.update(e); return g

vakalar=[]
def v(ad, beklenen, hazirla, govde):
    sifirla(); hazirla(); h=cagir(govde); vakalar.append((ad, beklenen, h.kod, h))
v("eksik alan", 400, lambda:None, {"urun":"gcs"})
v("bilinmeyen urun", 400, lambda:None, gcs(urun="radar"))
v("dizin gezinme ..", 400, lambda:None, gcs(dosya="../x"))
v("ters bolu", 400, lambda:None, gcs(dosya="a\\b"))
v("lisans yok", 403, lambda:None, gcs(lisans=None))
v("imza gecersiz", 403, lambda:setattr(D,"imza_gecerli",False), gcs())
v("firma_id bozuk", 403, lambda:None, gcs(lisans={"lisans":{"firma_id":"x"},"imza":"I"}))
v("uid kayitsiz", 403, lambda:setattr(D,"uid_kayitli",False), gcs())
v("firma pasif", 403, lambda:setattr(D,"firma",{"durum":"askida","merkez_lisans":True}), gcs())
v("lisans yetkisi kalkmis", 403, lambda:setattr(D,"firma",{"durum":"etkin","merkez_lisans":False}), gcs())
v("bakim bitmis", 403, lambda:setattr(D,"bakim",(False,"Bakim bitti")), gcs())
v("katalogda yok/pasif", 404, lambda:setattr(D,"kayit",None), gcs())
v("dosya diskte yok", 404, lambda:setattr(D,"dosya",None), gcs())
v("gcs basarili", 200, lambda:None, gcs())
kop={"urun":"kopru","surum":"1.7.2","platform":"windows","dosya":"K.exe","kurulum_uid":"abcdefabcdefabcd","gizli":"dogru"}
v("kopru gizli yanlis", 403, lambda:None, dict(kop, gizli="yanlis"))
v("kopru uid yok", 403, lambda:None, dict(kop, kurulum_uid=""))
v("kopru kurulum pasif", 403, lambda:D.kopru.update(durum="iptal"), kop)
v("kopru basarili", 200, lambda:None, kop)

hata=0
for ad,b,k,h in vakalar:
    ok = b==k; hata += not ok
    print("  %s %-24s beklenen=%s alinan=%s%s" % ("GECTI" if ok else "KALDI", ad, b, k, ("  " + str(h.akit)) if h.akit else ""))
# yan etkiler
sifirla(); h=cagir(gcs()); assert D.indirme==[(141,"1.2.3.4")] and len(D.sayac)==1, (D.indirme, D.sayac)
sifirla(); h=cagir(kop); assert D.indirme==[(141,"1.2.3.4")] and D.sayac==[], "kopru lisans sayacina yazmamali"
sifirla(); D.bakim=(False,"x"); h=cagir(gcs()); assert D.indirme==[] and h.akit is None, "red durumunda yan etki olmamali"
print("  GECTI yan etkiler (sayac/denetim izi yalniz basarida; kopru lisans sayacina dokunmaz)")
print("SONUC: %d/%d" % (len(vakalar)-hata, len(vakalar))); sys.exit(1 if hata else 0)
