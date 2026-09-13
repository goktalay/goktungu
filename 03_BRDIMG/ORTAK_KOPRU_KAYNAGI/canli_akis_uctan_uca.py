# -*- coding: utf-8 -*-
"""CANLI UCTAN UCA: kalici VM'deki kopru -> merkez sunucu -> GCS UDP.

Bu betik SAHTE veri kullanmaz. Kalici VM'de gercek bir TCP "ucus
donanimi" dinleyicisi acar, merkezdeki akis ucundan o donanima kanal
actirir ve merkezin ayirdigi UDP portundan gercek byte okur.

Kosum yeri: KALICI VM (kopru burada calisiyor).
Merkez ucuna erisim: SSH tuneli gerekmez; merkez ucu ic aglara kapali
oldugu icin merkez sunucuda kosan yardimci bir betik uzerinden cagrilir.

Bu yuzden betik IKI parcali calisir:
  1) VM'de bu betik TCP donanimini acar ve VM'in dis IP'sini yazar
  2) Merkez sunucuda `merkez_akis_tetik.py` kanali acar/kapatir

Burada 1. parca vardir; 2. parca merkezde otomatik cagrilir.
"""
import os
import json
import socket
import subprocess
import sys
import threading
import time

# ---------------------------------------------------------------- ayar
VM_DIS_IP = "35.231.113.38"
MERKEZ_SSH = "root@104.247.173.243"
MERKEZ_SIFRE = os.environ.get("GOKTUNGU_SINAV_SIFRE", "")  # koda parola yazilmaz
KANAL_ID = 4242

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


class UcusDonanimi:
    """Gercek TCP dinleyici: SITL/telemetri modemi yerine gecer.

    MAVLink v2 HEARTBEAT benzeri cerceveler uretir ve kendisine gelen
    komut byte'larini biriktirir.
    """

    def __init__(self, adres="0.0.0.0"):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.bind((adres, 0))
        self.s.listen(1)
        self.port = self.s.getsockname()[1]
        self.es = None
        self.alinan = bytearray()
        self.baglanti_sayisi = 0
        self._dur = False
        threading.Thread(target=self._kabul, daemon=True).start()

    def _kabul(self):
        while not self._dur:
            try:
                c, _ = self.s.accept()
            except Exception:
                return
            self.es = c
            self.baglanti_sayisi += 1
            threading.Thread(target=self._oku, args=(c,), daemon=True).start()

    def _oku(self, c):
        while not self._dur:
            try:
                v = c.recv(4096)
            except Exception:
                return
            if not v:
                return
            self.alinan.extend(v)

    def gonder(self, veri):
        if self.es is None:
            return False
        try:
            self.es.sendall(veri)
            return True
        except Exception:
            return False

    def kapat(self):
        self._dur = True
        for x in (self.es, self.s):
            try:
                x and x.close()
            except Exception:
                pass


def merkezde_kos(betik_govdesi):
    """Merkez sunucuda python3.11 ile bir betik kosar, stdout dondurur."""
    komut = ("cd /opt/goktungu/merkez/python && "
             "python3.11 -c %s" % json_kabuk(betik_govdesi))
    p = subprocess.run(
        ["sshpass", "-e", "ssh", "-o", "StrictHostKeyChecking=no",
         MERKEZ_SSH, komut],
        capture_output=True, text=True, timeout=120,
        env={"SSHPASS": MERKEZ_SIFRE, "PATH": "/usr/bin:/bin:/usr/local/bin"})
    return p.stdout.strip(), p.stderr.strip()


def json_kabuk(s):
    """Kabuk icin tek tirnakli guvenli alintilama."""
    return "'" + s.replace("'", "'\"'\"'") + "'"


MERKEZ_ISTEK = r'''
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
    kod = MERKEZ_ISTEK % {"yol": yol, "govde": json.dumps(govde)}
    cikti, hata = merkezde_kos(kod)
    if not cikti:
        return {"hata": "merkez cagrisi bos dondu", "stderr": hata[:300]}
    try:
        return json.loads(cikti.splitlines()[-1])
    except Exception as e:
        return {"hata": "%s: %s" % (type(e).__name__, e), "ham": cikti[:300]}


def main():
    print("=" * 62)
    print(" CANLI UCTAN UCA AKIS SINAVI (kopru -> merkez -> GCS)")
    print("=" * 62)

    # Merkezde kayitli ornek ve firma
    kod = r'''
import psycopg2, json
b = psycopg2.connect(host="127.0.0.1", dbname="goktungu_merkez",
                     user="postgres")  # parola: PGPASSWORD ortam degiskeni (koda yazilmaz)
i = b.cursor()
i.execute("select ornek_id, firma_id, ad from sunucu_ornekleri "
          "where son_gorulme_ts is not null "
          "order by son_gorulme_ts desc limit 1")
r = i.fetchone()
print(json.dumps({"ornek_id": r[0], "firma_id": r[1], "ad": r[2]} if r else {}))
'''
    cikti, hata = merkezde_kos(kod)
    try:
        bilgi = json.loads(cikti.splitlines()[-1])
    except Exception:
        print("Ornek bilgisi alinamadi:", cikti[:200], hata[:200])
        return 1
    oid = int(bilgi.get("ornek_id") or 0)
    fid = int(bilgi.get("firma_id") or 0)
    print("\nCanli kopru ornegi: #%d (%s), firma %d"
          % (oid, bilgi.get("ad"), fid))
    sina("canli kopru ornegi bulundu", oid > 0 and fid > 0)
    if not oid:
        return 1

    print("\n=== 1) Gercek ucus donanimi (TCP) acilir ===")
    # Donanim, kopru ile AYNI makinede loopback uzerinde dinler. Gercek
    # saha kurulumu da boyledir: Mission Planner SITL ya da telemetri
    # modemi pilotun bilgisayarindadir, kopru de o bilgisayarda kosar.
    # Ilk kosumda dis IP denenmisti; ufw yalniz 22 ve panel portunu
    # actigi icin olculen sey urun degil guvenlik duvari oldu.
    donanim = UcusDonanimi("127.0.0.1")
    print("  donanim dinliyor: 127.0.0.1:%d (kopru ile ayni makine)"
          % donanim.port)
    sina("TCP donanimi dinlemede", donanim.port > 0)

    print("\n=== 2) Merkez akis kanali acilir (kopru donanima baglanir) ===")
    y = merkez_ucu("/api/ic/akis_ac", {
        "ornek_id": oid, "firma_id": fid, "kanal_id": KANAL_ID,
        "tanim": {"tur": "tcp", "host": "127.0.0.1", "port": donanim.port}})
    print("  yanit:", json.dumps(y, ensure_ascii=False)[:300])
    sina("merkez kanali acildi", bool(y.get("basarili")),
         str(y.get("hata") or y))
    # Ucun gercek sozlesmesi: port UST DUZEYDE, ayrintili ozet `merkez`
    # altinda. Ilk kosumda `kanal` alani varsayildi ve bos cikti.
    kanal = y.get("merkez") or {}
    udp_port = int(y.get("port") or kanal.get("port") or 0)
    sina("merkez UDP portu ayrildi", udp_port > 0,
         json.dumps(y, ensure_ascii=False)[:200])
    sina("kopru donanima gercekten baglandi",
         _bekle(lambda: donanim.baglanti_sayisi >= 1, 15),
         "baglanti sayisi=%d" % donanim.baglanti_sayisi)
    if not udp_port or not donanim.baglanti_sayisi:
        merkez_ucu("/api/ic/akis_kapat",
                   {"ornek_id": oid, "firma_id": fid, "kanal_id": KANAL_ID})
        donanim.kapat()
        return _bitir()

    print("\n=== 3) Ileri yon: donanim -> kopru -> merkez UDP ===")
    # GCS taklidi merkez sunucuda kosmalidir (UDP portu loopback'e bagli).
    # Once donanimdan telemetri yollanir, merkezde bekleyen tampona duser;
    # sonra merkezde GCS taklidi ilk datagrami yazip bekleyeni tahsil eder.
    yuk = (bytes([0xFD, 0x09, 0x00, 0x00, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00])
           + b"CANLI-TELEMETRI" + bytes([0xAB, 0xCD]))
    sina("donanim telemetri yolladi", donanim.gonder(yuk))
    time.sleep(2.0)

    d = merkez_ucu("/api/ic/akis_durum", {"ornek_id": oid, "firma_id": fid})
    kanallar = d.get("kanallar") or []
    k0 = kanallar[0] if kanallar else {}
    print("  merkez kanal ozeti:", json.dumps(k0, ensure_ascii=False)[:300])
    sina("merkez bekleyen tamponda telemetri tutuyor",
         int(k0.get("beklemede_byte") or 0) >= len(yuk),
         "beklemede=%s" % k0.get("beklemede_byte"))

    print("\n=== 4) GCS taklidi (merkezde) bekleyeni tahsil eder ===")
    gcs_kod = r'''
import socket, json, time
p = %d
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("127.0.0.1", 0))
s.settimeout(6.0)
# mavutil gibi ilk datagrami GCS yollar: merkez adresi ogrenir
s.sendto(bytes([0xFD, 0x00]) + b"HEARTBEAT", ("127.0.0.1", p))
alinan = b""
t0 = time.time()
while time.time() - t0 < 6.0:
    try:
        v, _ = s.recvfrom(65535)
    except Exception:
        break
    alinan += v
    if b"CANLI-TELEMETRI" in alinan:
        break
print(json.dumps({"alinan_uzunluk": len(alinan),
                  "telemetri_var": b"CANLI-TELEMETRI" in alinan,
                  "ilk40": alinan[:40].hex()}))
s.close()
''' % udp_port
    cikti, hata = merkezde_kos(gcs_kod)
    try:
        g = json.loads(cikti.splitlines()[-1])
    except Exception:
        g = {"hata": cikti[:200] + hata[:200]}
    print("  GCS taklidi:", json.dumps(g, ensure_ascii=False)[:300])
    sina("GCS bekleyen telemetriyi aldi", bool(g.get("telemetri_var")),
         json.dumps(g, ensure_ascii=False)[:200])

    print("\n=== 5) Ters yon: GCS komutu -> merkez -> kopru -> donanim ===")
    donanim.alinan.clear()
    komut = bytes([0xFD, 0x21]) + b"CANLI-ARM-KOMUTU" + bytes([0x00, 0xFF])
    komut_kod = r'''
import socket
p = %d
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("127.0.0.1", 0))
s.sendto(bytes.fromhex("%s"), ("127.0.0.1", p))
s.close()
print("yollandi")
''' % (udp_port, komut.hex())
    merkezde_kos(komut_kod)
    sina("donanim komutu gercekten aldi",
         _bekle(lambda: komut in bytes(donanim.alinan), 12),
         "alinan=%r" % bytes(donanim.alinan)[:60])

    print("\n=== 6) Sayaclar merkezde tutarli ===")
    d2 = merkez_ucu("/api/ic/akis_durum", {"ornek_id": oid, "firma_id": fid})
    kl = d2.get("kanallar") or []
    k1 = kl[0] if kl else {}
    print("  ozet:", json.dumps(k1, ensure_ascii=False)[:320])
    sina("kopruden gelen byte sayildi",
         int(k1.get("kopruden_byte") or 0) >= len(yuk),
         "kopruden_byte=%s" % k1.get("kopruden_byte"))
    sina("GCS'den gelen byte sayildi",
         int(k1.get("gcsden_byte") or 0) >= len(komut),
         "gcsden_byte=%s" % k1.get("gcsden_byte"))
    sina("GCS adresi ogrenildi", bool(k1.get("gcs_bagli")))

    print("\n=== 7) Kanal kapatilir, kaynak sizmaz ===")
    kp = merkez_ucu("/api/ic/akis_kapat",
                    {"ornek_id": oid, "firma_id": fid, "kanal_id": KANAL_ID})
    print("  kapatma:", json.dumps(kp, ensure_ascii=False)[:200])
    sina("kanal kapatildi", bool(kp.get("basarili")), json.dumps(kp))
    d3 = merkez_ucu("/api/ic/akis_durum", {"ornek_id": oid, "firma_id": fid})
    sina("merkezde kanal kalmadi", len(d3.get("kanallar") or []) == 0,
         json.dumps(d3, ensure_ascii=False)[:200])

    donanim.kapat()
    return _bitir()


def _bekle(kosul, sure=6.0, adim=0.1):
    t0 = time.time()
    while time.time() - t0 < sure:
        if kosul():
            return True
        time.sleep(adim)
    return False


def _bitir():
    print("\n" + "=" * 62)
    print("SONUC: %d gecti / %d kaldi" % (gecti, kaldi))
    print("=" * 62)
    return 0 if kaldi == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
