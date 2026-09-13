import sys, importlib.util
sys.argv=["ai_sunucu.py"]
spec=importlib.util.spec_from_file_location("ai_sunucu","/src/assets/python/ai_sunucu.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
import numpy as np, cv2

# hassasiyet_coz
print("coz boş:", m.hassasiyet_coz(""))
print("coz kısmi:", m.hassasiyet_coz('{"hava_araci":80}'))
print("coz aralık dışı:", m.hassasiyet_coz('{"insan":5,"kara_araci":95,"hava_araci":40}'))

class SahteIsci:
    def _canli_kutu_ekle(self,*a,**k): pass
    def _tespit_bildir(self,*a,**k): self.n+=1
    n=0

def say(sens):
    isci=m.AIIsci.__new__(m.AIIsci)  # analiz metodları için örnek
    # AkisIsleyici sadece durum taşıyıcı; thread başlatmıyoruz
    akis=m.AkisIsleyici.__new__(m.AkisIsleyici)
    akis.gorevler={"hava_araci"}; akis.arka_plan=None
    akis.hassasiyet=m.hassasiyet_coz('{"hava_araci":%d}'%sens)
    akis._olcek={k:(50.0/max(10,v)) for k,v in akis.hassasiyet.items()}
    akis._sogutma={}
    akis.sogutma_gecti=lambda *a,**k: True
    sayac={"n":0}
    def bildir(*a,**k): sayac["n"]+=1
    isci._tespit_bildir=bildir
    isci._canli_kutu_ekle=lambda *a,**k: None
    h,w=540,960
    # üst bölgede küçük hareketli nesneler (hava aracı profili)
    rng=np.random.default_rng(1)
    for i in range(30):
        kare=np.zeros((h,w,3),np.uint8)
        # arka plan ısınması sonrası küçük bloklar
        for j in range(6):
            x=40+ (i*9 + j*130)%(w-30); y=40+j*12
            s=8+j  # farklı boyutlar (küçükler yalnız yüksek hassasiyette geçer)
            cv2.rectangle(kare,(x,y),(x+s,y+s),(230,230,230),-1)
        kare=cv2.add(kare, rng.integers(0,4,kare.shape,dtype=np.uint8))
        isci._hareket_analiz(akis,kare,float(i))
    return sayac["n"]

d10=say(10); d50=say(50); d90=say(90)
print("hava tespit sayısı  s=10:",d10," s=50:",d50," s=90:",d90)
assert d90>=d50>=d10, "hassasiyet arttıkça tespit artmalı"
assert d90>d10, "s=90 ile s=10 arasında fark olmalı"
print("SONUC: sınıf başına hassasiyet tespit sayısını beklenen yönde değiştiriyor ✓")
