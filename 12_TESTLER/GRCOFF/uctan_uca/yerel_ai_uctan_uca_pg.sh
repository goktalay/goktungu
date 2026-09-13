#!/usr/bin/env bash
set -u
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/dev/null && apt-get install -y -qq ffmpeg curl procps postgresql >/dev/null 2>&1
pip install -q websockets opencv-python-headless numpy pymavlink pyserial psycopg2-binary >/dev/null 2>&1
service postgresql start >/dev/null
su postgres -c "psql -qc \"CREATE USER goktungu PASSWORD 'sinav'\"" && su postgres -c "psql -qc 'CREATE DATABASE goktungu OWNER goktungu'"
echo "[1] ortam: $(python3 -c 'import cv2;print("cv2",cv2.__version__)') | pg: $(su postgres -c 'psql -tAc "select version()"' | cut -c1-16)"

mkdir -p /tmp/v && python3 - <<'PY'
import cv2, numpy as np
w,h,fps=640,360,20
v=cv2.VideoWriter("/tmp/v/hedef.avi",cv2.VideoWriter_fourcc(*"MJPG"),fps,(w,h))
for i in range(fps*20):
    k=np.zeros((h,w,3),np.uint8); k[:]=(90,70,50); k[int(h*0.6):]=(40,80,40)
    x=int((i*6)%(w-40)); y=60+int(20*np.sin(i/10))
    cv2.rectangle(k,(x,y),(x+26,y+14),(230,230,230),-1)
    v.write(k)
v.release()
PY
(cd /tmp/v && python3 -m http.server 9999 >/dev/null 2>&1 &)

export GOKTUNGU_VERI_KOKU=/veri GOKTUNGU_AI_PORT=8910 GOKTUNGU_VIDEO_PORT=8811
mkdir -p /veri && cd /app
# Sihirbazin pg_kur adiminin aynisi + eski kurulumdan kalan hayalet kayitlar
python3 - <<'PY'
import sys; sys.path.insert(0,"/app/assets/python")
from goktungu import pg, veritabani as vt, goc
pg.yapilandir("127.0.0.1",5432,"goktungu","goktungu","sinav",diske_yaz=True)
vt.kip_ayarla("postgresql")
s=goc.GocMotoru(konsol=lambda m: None).calistir()
print("[2] sema kurulumu:", s.get("tamam"), s.get("hata",""))
with vt.baglanti() as con:
    con.execute("INSERT INTO ai_sunucular (ad,tip,host,port,kapasite,notlar,aktif) VALUES (?,?,?,?,?,?,1)",
        ("ASUS Ascent GX10","nvidia","192.168.1.100",8900,8,"NVIDIA GB10 Grace Blackwell tabanli AI islem sunucusu. Host adresini agdaki gercek IP ile guncelleyin."))
    con.execute("INSERT INTO ai_sunucular (ad,tip,host,port,kapasite,notlar,aktif) VALUES (?,?,?,?,?,?,1)",
        ("CPU AI Sunucusu (Yerel)","cpu","127.0.0.1",8900,4,"Ana sunucu ile ayni makinede calisan CPU tabanli isci (Windows/Linux). GCS acilisinda otomatik baslatilir."))
    con.execute("INSERT INTO ai_sunucular (ad,tip,host,port,kapasite,notlar,aktif) VALUES (?,?,?,?,?,?,1)",
        ("Kullanici GPU","nvidia","10.0.0.5",8900,8,"kullanicinin kendi eklediği"))
print("[3] once ai_sunucular:", [ (r["ad"],r["port"]) for r in vt.baglanti().execute("select ad,port from ai_sunucular order by id").fetchall()])
PY

python3 -u main.py --tarayici-yok > /veri/main.log 2>&1 &
ANA=$!
sleep 30
echo "[4] merkez calisiyor: $(kill -0 $ANA 2>/dev/null && echo EVET || echo HAYIR) | isci surec sayisi: $(pgrep -fc ai_sunucu.py)"

python3 - <<'PY'
import sys; sys.path.insert(0,"/app/assets/python")
from goktungu import pg, veritabani as vt
pg.dosyadan_yukle(); vt.kip_ayarla("postgresql")
from goktungu.kameralar import KameraYoneticisi
r=KameraYoneticisi().ekle("sinav-kamera","http","http://127.0.0.1:9999/hedef.avi",None,"hava_araci")
print("[5] kamera DB'ye dogrudan eklendi, id:", r[0])
print("[6] sonra ai_sunucular:", [ (x["ad"],x["host"],x["port"]) for x in vt.baglanti().execute("select ad,host,port from ai_sunucular order by id").fetchall()])
PY

for i in $(seq 1 24); do
  D=$(curl -s --max-time 3 http://127.0.0.1:8910/durum)
  echo "$D" | grep -q '"canli": true' && break
  sleep 5
done
echo "[7] isci /durum: $D"
sleep 25
python3 - <<'PY'
import sys; sys.path.insert(0,"/app/assets/python")
from goktungu import pg, veritabani as vt
pg.dosyadan_yukle(); vt.kip_ayarla("postgresql")
print("[8] ai_tespitler:", [dict(r) for r in vt.baglanti().execute("select tur, count(*) as adet from ai_tespitler group by tur").fetchall()])
PY
echo "[9] kayit dosyalari /veri/ai_kayitlar: $(find /veri/ai_kayitlar -type f 2>/dev/null | wc -l) | /app altinda ai_kayitlar: $(find /app -maxdepth 3 -name ai_kayitlar | wc -l)"
J=$(cat /veri/ai_isci_anahtari)
echo "[10] /kamera/1 guvenlik: anahtarsiz=$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 http://127.0.0.1:8000/kamera/1) yanlis=$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 -H 'X-Goktungu-AI-Isci: yanlisyanlisyanlisyanlisyanlisyanlis00' http://127.0.0.1:8000/kamera/1) dogru=$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 -H "X-Goktungu-AI-Isci: $J" http://127.0.0.1:8000/kamera/1) | anahtar dosya izni: $(stat -c %a /veri/ai_isci_anahtari)"
H=$(hostname -i | awk '{print $1}')
echo "     loopback DISINDAN dogru anahtarla ($H): $(curl -s -o /dev/null -w '%{http_code}' --max-time 4 -H "X-Goktungu-AI-Isci: $J" http://$H:8000/kamera/1)"
echo "--- merkez gunlugu (AI) ---"; grep -a "AI" /veri/main.log | grep -av "WARN" | tail -10

echo "[10b] isci dis IP'den ($H:8910): $(curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://$H:8910/durum || true) (000=erisilemez) | loopback: $(curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://127.0.0.1:8910/durum)"
echo "[10c] kotu gcs_proxy yolu: $(curl -s --max-time 5 -H 'Content-Type: application/json' -d '{"kamera_id": 77, "url": "@ornek.invalid/x", "protokol": "gcs_proxy", "gorevler": "insan"}' http://127.0.0.1:8910/izle)"; sleep 4
echo "      77 akis hatasi: $(curl -s http://127.0.0.1:8910/durum | python3 -c 'import json,sys; print([a for a in json.load(sys.stdin)["akislar"] if a["kamera_id"]==77])')"
curl -s -H 'Content-Type: application/json' -d '{"kamera_id": 77}' http://127.0.0.1:8910/durdur >/dev/null
echo "[11] ISCI OLDURULUYOR"; pkill -f ai_sunucu.py; sleep 2
for i in $(seq 1 30); do
  D=$(curl -s --max-time 3 http://127.0.0.1:8910/durum)
  echo "$D" | grep -q '"canli": true' && break
  sleep 5
done
echo "[12] yeniden baslama + gorev geri alma: $D"
echo "    isci surec sayisi: $(pgrep -fc ai_sunucu.py)"
grep -a "yeniden başlatılıyor\|izlemesi" /veri/main.log | tail -4
kill $ANA; sleep 4
echo "[13] merkez kapaninca isci kaldi mi: $(pgrep -fc ai_sunucu.py)"
