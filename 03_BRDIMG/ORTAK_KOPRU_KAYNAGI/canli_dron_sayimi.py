# -*- coding: utf-8 -*-
"""CANLI: dron sayimi gercek akis kanalina bagli mi?

Olculen sey: kanal acildiginda kopru PANELI ve MERKEZ ayni sayiyi
gorur mu; kanal kapaninca sifira doner mi.

Onceki durumda `dron_sayisi` sabit 0 donuyordu (alt surec kanallari
goremiyordu). Bu sinav o kusurun geri gelmesini engeller.

Kosum yeri: kopru surecinin bulundugu makine (kalici VM).
"""
import os
import json
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

# Panel adresi komut satirindan alinir. Sabit port yazmak yanlisti:
# kalici kurulum (kur.sh) 8790 kullanir, elle baslatilan gelistirme
# ornegi 8791. Sabit port, sinavin "baglanti reddedildi" ile patlamasina
# yol acar ve okuyan kisi bunu urun kusuru sanar.
PANEL = (sys.argv[1].rstrip("/") if len(sys.argv) > 1
         else "http://127.0.0.1:8790")
EPOSTA = "mkaderoglu@gokkubbetech.com"
SIFRE = os.environ.get("GOKTUNGU_SINAV_SIFRE", "")  # koda parola yazilmaz
MERKEZ_SSH = "root@104.247.173.243"
MERKEZ_SIFRE = os.environ.get("GOKTUNGU_SINAV_SIFRE", "")  # koda parola yazilmaz
KANAL_ID = 5150

gecti = 0
kaldi = 0


def sina(ad, kosul, ayrinti=""):
    global gecti, kaldi
    if kosul:
        gecti += 1
        print("  [GECTI] %s" % ad)
    else:
        kaldi += 1
        print("  [KALDI] %s%s" % (ad, (" - " + ayrinti) if ayrinti else ""))


class PanelIstemci:
    """Kopru panelinin gercek HTTP API'sini kullanir (tarayici gibi)."""

    def __init__(self, taban):
        self.taban = taban
        self.cerez = ""
        self.jeton = "1"

    def _istek(self, yol, govde=None):
        b = {"Content-Type": "application/json"}
        if self.cerez:
            b["Cookie"] = self.cerez
        if govde is not None:
            b["X-Kopru-Jeton"] = self.jeton
        r = urllib.request.Request(
            self.taban + yol,
            data=json.dumps(govde).encode() if govde is not None else None,
            method="POST" if govde is not None else "GET", headers=b)
        try:
            with urllib.request.urlopen(r, timeout=20) as y:
                sc = y.headers.get("Set-Cookie")
                if sc:
                    self.cerez = sc.split(";")[0]
                return json.loads(y.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read().decode() or "{}")
            except Exception:
                return {"hata": "HTTP %d" % e.code}

    def giris(self):
        y = self._istek("/api/giris", {"eposta": EPOSTA, "sifre": SIFRE})
        self.jeton = y.get("jeton") or "1"
        return y

    def durum(self):
        return self._istek("/api/durum")

    def servis(self, eylem, ad):
        return self._istek("/api/servis/" + eylem, {"servis": ad})


class UcusDonanimi:
    def __init__(self):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.bind(("127.0.0.1", 0))
        self.s.listen(2)
        self.port = self.s.getsockname()[1]
        self.baglanti_sayisi = 0
        self._esler = []
        self._dur = False
        threading.Thread(target=self._kabul, daemon=True).start()

    def _kabul(self):
        while not self._dur:
            try:
                c, _ = self.s.accept()
            except Exception:
                return
            self._esler.append(c)
            self.baglanti_sayisi += 1

    def kapat(self):
        self._dur = True
        for x in self._esler + [self.s]:
            try:
                x.close()
            except Exception:
                pass


def kabuk_alinti(s):
    return "'" + s.replace("'", "'\"'\"'") + "'"


def merkezde_kos(kod):
    komut = "cd /opt/goktungu/merkez/python && python3.11 -c %s" % kabuk_alinti(kod)
    p = subprocess.run(
        ["sshpass", "-e", "ssh", "-o", "StrictHostKeyChecking=no",
         MERKEZ_SSH, komut],
        capture_output=True, text=True, timeout=120,
        env={"SSHPASS": MERKEZ_SIFRE, "PATH": "/usr/bin:/bin:/usr/local/bin"})
    return p.stdout.strip(), p.stderr.strip()


IC = r'''
import json, urllib.request
A = "d73cbb1c82b184f041ef835f2c5c5876f6cc395f8eaa3467"
def cagir(yol, govde):
    r = urllib.request.Request("http://127.0.0.1:80" + yol,
        data=json.dumps(govde).encode(), method="POST",
        headers={"Content-Type":"application/json","X-Ic-Anahtar":A})
    with urllib.request.urlopen(r, timeout=30) as y:
        return json.loads(y.read().decode())
print(json.dumps(cagir("%(yol)s", %(govde)s)))
'''


def merkez_ucu(yol, govde):
    cikti, hata = merkezde_kos(IC % {"yol": yol, "govde": json.dumps(govde)})
    if not cikti:
        return {"hata": "bos yanit", "stderr": hata[:200]}
    try:
        return json.loads(cikti.splitlines()[-1])
    except Exception:
        return {"hata": cikti[:200]}


def dron_olcum(durum):
    for s in (durum.get("servisler") or []):
        if s.get("ad") == "dron":
            return (s.get("olcumler") or {}).get("dron_sayisi")
    return None


def merkez_kopru_sor(oid, fid, eylem, veri=None):
    return merkez_ucu("/api/ic/kopru_sor", {
        "ornek_id": oid, "firma_id": fid, "eylem": eylem, "veri": veri or {}})


def bekle(kosul, sure=15.0, adim=0.4):
    t0 = time.time()
    while time.time() - t0 < sure:
        if kosul():
            return True
        time.sleep(adim)
    return False


def main():
    print("=" * 62)
    print(" CANLI: DRON SAYIMI GERCEK KANALA BAGLI MI?")
    print("=" * 62)

    p = PanelIstemci(PANEL)
    g = p.giris()
    # Panel giris yaniti `tamam` alani dondurur (`basarili` degil).
    sina("panele giris", bool(g.get("tamam")),
         json.dumps(g, ensure_ascii=False)[:200])

    d0 = p.durum()
    sina("durum yaniti kanal listesi tasiyor", "kanallar" in d0,
         "anahtarlar=%s" % list(d0.keys()))

    # Dron servisi calismali
    if not any(s.get("ad") == "dron" and s.get("calisiyor")
               for s in (d0.get("servisler") or [])):
        p.servis("baslat", "dron")
        bekle(lambda: any(s.get("ad") == "dron" and s.get("calisiyor")
                          for s in (p.durum().get("servisler") or [])), 20)
    d0 = p.durum()
    sina("dron servisi calisiyor",
         any(s.get("ad") == "dron" and s.get("calisiyor")
             for s in (d0.get("servisler") or [])))

    baslangic = dron_olcum(d0)
    print("  baslangic dron sayisi: %r" % baslangic)
    sina("baslangicta sayim 0", baslangic == 0, "deger=%r" % baslangic)

    # Merkezdeki ornek
    kod = ('import psycopg2, json\n'
           'b = psycopg2.connect(host="127.0.0.1", dbname="goktungu_merkez",'
           ' user="postgres")\n'  # parola: PGPASSWORD ortam degiskeni (koda yazilmaz)
           'i = b.cursor()\n'
           'i.execute("select ornek_id, firma_id from sunucu_ornekleri'
           ' where son_gorulme_ts is not null order by son_gorulme_ts'
           ' desc limit 1")\n'
           'r = i.fetchone()\n'
           'print(json.dumps({"o": r[0], "f": r[1]} if r else {}))\n')
    cikti, _ = merkezde_kos(kod)
    try:
        bilgi = json.loads(cikti.splitlines()[-1])
    except Exception:
        bilgi = {}
    oid, fid = int(bilgi.get("o") or 0), int(bilgi.get("f") or 0)
    sina("merkezde canli kopru ornegi var", oid > 0 and fid > 0)
    if not oid:
        return _bitir()

    print("\n=== Kanal acilir: sayim 1'e cikmali ===")
    donanim = UcusDonanimi()
    y = merkez_ucu("/api/ic/akis_ac", {
        "ornek_id": oid, "firma_id": fid, "kanal_id": KANAL_ID,
        "tanim": {"tur": "tcp", "host": "127.0.0.1", "port": donanim.port}})
    sina("kanal acildi", bool(y.get("basarili")), str(y.get("hata") or y)[:200])
    sina("kopru donanima baglandi",
         bekle(lambda: donanim.baglanti_sayisi >= 1, 15))

    sina("PANEL sayimi 1 gosteriyor",
         bekle(lambda: dron_olcum(p.durum()) == 1, 15),
         "deger=%r" % dron_olcum(p.durum()))

    ms = merkez_kopru_sor(oid, fid, "servis_durum")
    # Merkez ic ucu yaniti `{"basarili":true,"veri":{...}}` bicimindedir.
    mv = None
    for s in ((ms.get("veri") or ms).get("servisler") or []):
        if s.get("ad") == "dron":
            mv = (s.get("olcumler") or {}).get("dron_sayisi")
    print("  merkezin gordugu sayi: %r" % mv)
    sina("MERKEZ ayni sayiyi goruyor", mv == 1, "deger=%r" % mv)

    kl = p.durum().get("kanallar") or []
    print("  panel kanal listesi: %s" % json.dumps(kl, ensure_ascii=False)[:240])
    sina("panel kanal ayrintisini gosteriyor", len(kl) == 1,
         "adet=%d" % len(kl))

    print("\n=== Kanal kapanir: sayim 0'a donmeli ===")
    merkez_ucu("/api/ic/akis_kapat",
               {"ornek_id": oid, "firma_id": fid, "kanal_id": KANAL_ID})
    sina("PANEL sayimi 0'a dondu",
         bekle(lambda: dron_olcum(p.durum()) == 0, 15),
         "deger=%r" % dron_olcum(p.durum()))
    sina("kanal listesi bosaldi",
         bekle(lambda: len(p.durum().get("kanallar") or []) == 0, 10))

    print("\n=== Dron servisi durdurulunca sayim 0 kalmali ===")
    p.servis("durdur", "dron")
    time.sleep(2)
    sina("servis durunca sayim 0", dron_olcum(p.durum()) in (0, None),
         "deger=%r" % dron_olcum(p.durum()))
    p.servis("baslat", "dron")

    donanim.kapat()
    return _bitir()


def _bitir():
    print("\n" + "=" * 62)
    print("SONUC: %d gecti / %d kaldi" % (gecti, kaldi))
    print("=" * 62)
    return 0 if kaldi == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
