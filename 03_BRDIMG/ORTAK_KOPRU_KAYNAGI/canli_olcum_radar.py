#!/usr/bin/env python3
"""CANLI OLCUM — KURULU KOPRU (radar zinciri).

## NEDEN BU OLCUM VAR

Kullanici bildirimi:

    "radarda da ayni sorun var, radarin kopru yazilimi calisiyor ama
     sistem radari sunucuda ariyor"

Duzeltmeden sonra C20 oturumu SAHADA (koprude) kurulur. Bu betik,
gelistirme agacini DEGIL `/opt/goktungu/kopru` altina GERCEKTEN KURULMUS
paketi olcer: kurulumun kendi sanal ortamindaki yorumlayici ile radar
servisini alt surec olarak baslatir, karsisina sanal bir C20 radari
koyar ve panel komutlarini dosya tabanli kanaldan gonderir.

## SANAL RADAR NEDEN URUN KODUNU KULLANIR

Sanal radar, cerceve kurma ve CRC islevlerini KENDISI yazmaz;
`kopru.radar_c20.RadarIstemcisi` sinifinin `cerceve()` ve `crc16()`
metotlarini ithal eder. Aksi halde olcum kendi uydurdugu protokolu
dogrular: iki taraf da yanlis olsa bile olcum gecer. Nitekim bu
betigin onceki surumu uydurma bir kucuk-endian protokol konusuyordu ve
kurulu servis LOGIN yanitini hic taniyamiyordu.

Gercek protokol (donanimla dogrulanmis, bkz. C20_PROTOKOL_SOZLESMESI):

    0x55AA55AA (u32 BE) + uzunluk (u32 BE) + komut (u32 BE)
      + frameID (u32 BE) + ek + CRC16-MODBUS (u16 LITTLE-ENDIAN)

## OLCULENLER

 1. Kurulu servis gercekten TCP baglanti kurup LOGIN yapiyor mu
 2. Durum dosyasi (merkeze cikan paket) yaziliyor mu
 3. TRACK cerceveleri cozulup cografi konuma cevriliyor mu
 4. Panel komutlari (durum/ayar_oku/ayar_yaz/rtk/kes) servise ULASIYOR mu
 5. Radar susunca hayalet iz kalmiyor mu
 6. Servis gunlugunde cokme/eksik modul izi var mi
"""
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time

KURULUM = "/opt/goktungu/kopru"
sys.path.insert(0, KURULUM)

from kopru.radar_c20 import (          # noqa: E402  (yol ayarindan sonra)
    C20_GETREG, C20_HEARTBEAT, C20_LOGIN, C20_REQUEST_RTK, C20_SETREG,
    C20_UPLOAD_RTK, C20_UPLOAD_TRACK_V3, RadarIstemcisi,
)

GECTI = 0
KALDI = 0
KALAN_AD = []


def bolum(ad):
    print("=" * 70)
    print(ad)
    print("=" * 70)


def olc(ad, kosul, ayrinti=""):
    global GECTI, KALDI
    if kosul:
        GECTI += 1
        print("  [GECTI] %s" % ad)
    else:
        KALDI += 1
        KALAN_AD.append(ad)
        print("  [KALDI] %s%s" % (ad, ("  -> " + str(ayrinti))
                                  if ayrinti else ""))


# ---------------------------------------------------------------------
# SANAL C20 RADARI — gercek protokol, urun kodunun cerceveleyicisi
# ---------------------------------------------------------------------
class SanalC20(threading.Thread):
    """C20 protokolunun RADAR tarafini konusan sanal sunucu."""

    def __init__(self, rtk_lat=39.925533, rtk_lon=32.866287, iz_sayisi=3):
        super().__init__(daemon=True)
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.rtk_lat = rtk_lat
        self.rtk_lon = rtk_lon
        self.iz_sayisi = iz_sayisi

        self.dur = False
        self.iz_gonder = True
        self.baglanti_sayisi = 0
        self.login_sayisi = 0
        self.getreg_sayisi = 0
        self.setreg_sayisi = 0
        self.rtk_sayisi = 0
        self.heartbeat_sayisi = 0
        self.rtk_acik = False
        self.setreg_kayitlari = []

    # -----------------------------------------------------------------
    def run(self):
        while not self.dur:
            try:
                self.sock.settimeout(0.5)
                try:
                    c, _ = self.sock.accept()
                except socket.timeout:
                    continue
                self.baglanti_sayisi += 1
                threading.Thread(target=self._istemci, args=(c,),
                                 daemon=True).start()
            except OSError:
                break

    def _gonder(self, c, komut, ek=b""):
        try:
            c.sendall(RadarIstemcisi.cerceve(komut, 1, ek))
        except OSError:
            pass

    def _istemci(self, c):
        c.settimeout(0.2)
        tampon = b""
        son_iz = 0.0
        son_rtk = 0.0
        frame = 0
        t0 = time.time()
        while not self.dur:
            try:
                p = c.recv(8192)
                if not p:
                    break
                tampon += p
            except socket.timeout:
                pass
            except OSError:
                break

            # --- gelen cerceveleri coz (0x55AA55AA senkronizasyonu) ---
            while True:
                i = tampon.find(b"\x55\xaa\x55\xaa")
                if i < 0 or len(tampon) < i + 8:
                    break
                uz = struct.unpack(">I", tampon[i + 4:i + 8])[0]
                if uz < 10 or uz > 1 << 20:
                    tampon = tampon[i + 4:]
                    continue
                if len(tampon) < i + 8 + uz:
                    break
                govde_crc = tampon[i + 8:i + 8 + uz]
                tampon = tampon[i + 8 + uz:]
                govde = govde_crc[:-2]
                crc_gelen = struct.unpack("<H", govde_crc[-2:])[0]
                if RadarIstemcisi.crc16(govde) != crc_gelen:
                    continue           # bozuk cerceve: yanit yok
                komut = struct.unpack(">I", govde[:4])[0]
                self._komut_isle(c, komut, govde[8:])

            simdi = time.time()
            # --- RTK yayini (istek acildiysa) ---
            if self.rtk_acik and simdi - son_rtk > 0.2:
                son_rtk = simdi
                self._gonder(c, C20_UPLOAD_RTK, struct.pack(
                    ">qqqi", int(self.rtk_lat * 1e9),
                    int(self.rtk_lon * 1e9), 0, 18))
            # --- TRACK yayini ---
            if self.iz_gonder and simdi - son_iz > 0.2:
                son_iz = simdi
                frame += 1
                self._gonder(c, C20_UPLOAD_TRACK_V3,
                             self._track_ek(frame, simdi - t0))

        try:
            c.close()
        except OSError:
            pass

    def _komut_isle(self, c, komut, ek):
        if komut == C20_LOGIN:
            self.login_sayisi += 1
            # LOGIN yaniti: ek[4:6] = durum kodu (0 = basarili)
            self._gonder(c, C20_LOGIN, struct.pack(">IHH", 0, 0, 0))
        elif komut == C20_HEARTBEAT:
            self.heartbeat_sayisi += 1
            self._gonder(c, C20_HEARTBEAT, b"")
        elif komut == C20_REQUEST_RTK:
            self.rtk_sayisi += 1
            if len(ek) >= 1:
                self.rtk_acik = bool(ek[0])
        elif komut == C20_SETREG:
            self.setreg_sayisi += 1
            if len(ek) >= 4:
                adet = struct.unpack(">I", ek[:4])[0]
                ofs = 4
                for _ in range(min(adet, 16)):
                    if ofs + 8 > len(ek):
                        break
                    a, d = struct.unpack(">II", ek[ofs:ofs + 8])
                    ofs += 8
                    self.setreg_kayitlari.append((a, d))
            self._gonder(c, C20_SETREG, struct.pack(">H", 0))
        elif komut == C20_GETREG:
            self.getreg_sayisi += 1
            # USER_CFG0 (0x0440): frekans/hiz/tespit/rcs paketli
            # WORKING_MODE (0x0401): tarama2 = 0x0101
            regler = [(0x00000440,
                       (2 << 24) | (1 << 16) | (2 << 8) | 1),
                      (0x00000401, 0x00000101)]
            ek_y = struct.pack(">I", len(regler))
            for a, d in regler:
                ek_y += struct.pack(">II", a, d)
            self._gonder(c, C20_GETREG, ek_y)

    def _track_ek(self, frame, t):
        """UPLOAD_TRACK_V3 ek verisi: 40 bayt baslik + N x 64 bayt hedef."""
        n = self.iz_sayisi
        ms = int(time.time() * 1000)
        # kuzey_bayragi = 0 -> kuzey modu (radar yonu duzeltmesi gerekmez)
        ek = struct.pack(">qqqiiBBBBi", ms, frame, ms, 0, 3600, 0, 0, 0, 1, n)
        for k in range(n):
            x = int((1000.0 + k * 500.0 + t * 20.0) * 100)   # cm
            y = int((2000.0 + k * 300.0) * 100)
            z = int((150.0 + k * 50.0) * 100)
            ek += struct.pack(
                ">iiiiiiIhhhHHbbqiiii",
                x, y, z,
                int(20.0 * 100), 0, 0,        # hiz (cm/s)
                1000 + k,                     # hedef kimligi
                int(18.5 * 100),              # snr
                int(0.35 * 100),              # rcs
                0, 0, 0,                      # rezerv
                3,                            # tip: DRON
                0, 0, 0, 0, 0, 1)             # rezerv + secili
        return ek

    def kapat(self):
        self.dur = True
        try:
            self.sock.close()
        except OSError:
            pass


# ---------------------------------------------------------------------
# Kurulu radar servisini gercek alt surec olarak calistir
# ---------------------------------------------------------------------
class Kosum:
    def __init__(self, radar_ip, radar_port):
        self.dizin = tempfile.mkdtemp(prefix="canli_radar_")
        self.veri = os.path.join(self.dizin, "veri")
        self.kanal = os.path.join(self.dizin, "kanal")
        os.makedirs(self.veri, exist_ok=True)
        os.makedirs(self.kanal, exist_ok=True)
        self.radar_ip = radar_ip
        self.radar_port = radar_port
        self.durum_dosyasi = os.path.join(self.veri, "radar_durum.json")
        self.ayar_dosyasi = os.path.join(self.veri, "ayarlar.json")
        with open(self.ayar_dosyasi, "w", encoding="utf-8") as f:
            json.dump({"radar": {"ip": radar_ip, "port": radar_port}}, f)
        self.surec = None
        self.gunluk = os.path.join(self.dizin, "servis.log")

    def basla(self):
        ortam = dict(os.environ)
        ortam["GOKTUNGU_KOPRU_VERI_DIZIN"] = self.veri
        ortam["GOKTUNGU_KOPRU_KANAL_DIZIN"] = self.kanal
        ortam["GOKTUNGU_KOPRU_DURUM_DOSYASI"] = self.durum_dosyasi
        ortam["GOKTUNGU_KOPRU_SERVIS_ADI"] = "radar"
        ortam["GOKTUNGU_RADAR_IP"] = self.radar_ip
        ortam["GOKTUNGU_RADAR_PORT"] = str(self.radar_port)
        ortam["PYTHONPATH"] = KURULUM
        py = os.path.join(KURULUM, ".venv", "bin", "python")
        with open(self.gunluk, "w", encoding="utf-8") as g:
            self.surec = subprocess.Popen(
                [py, "-c",
                 "import sys; sys.path.insert(0, r'%s'); "
                 "import runpy; runpy.run_module('kopru.servis_radar', "
                 "run_name='__main__')" % KURULUM],
                stdout=g, stderr=subprocess.STDOUT, env=ortam,
                cwd=self.dizin)

    def durum(self):
        try:
            with open(self.durum_dosyasi, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def izler(self):
        return self.durum().get("izler") or []

    def komut(self, eylem, veri=None, bekle=8.0):
        from kopru.servis_kanal import komut_yaz, yanit_bekle
        kid = komut_yaz(self.kanal, "radar", eylem, veri or {})
        return yanit_bekle(self.kanal, "radar", kid, zaman_asimi=bekle)

    def gunluk_oku(self):
        try:
            with open(self.gunluk, encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""

    def bitir(self):
        if self.surec:
            self.surec.terminate()
            try:
                self.surec.wait(timeout=6)
            except subprocess.TimeoutExpired:
                self.surec.kill()


def bekle_kosul(islev, zaman_asimi=12.0, aralik=0.3):
    son = time.time() + zaman_asimi
    while time.time() < son:
        try:
            if islev():
                return True
        except Exception:
            pass
        time.sleep(aralik)
    return False


def main():
    bolum("CANLI OLCUM — KURULU KOPRU (radar zinciri)")
    print(f"Kurulum : {KURULUM}")
    try:
        with open(os.path.join(KURULUM, "SURUM"), encoding="utf-8") as f:
            print(f"Surum   : {f.read().strip()}")
    except OSError:
        pass

    radar = SanalC20()
    radar.start()
    print(f"Sanal C20 radari : 127.0.0.1:{radar.port}")

    kosum = Kosum("127.0.0.1", radar.port)
    kosum.basla()
    print(f"Calisma dizini   : {kosum.dizin}")

    try:
        bolum("1. SERVIS BASLADI VE RADARA BAGLANDI")
        olc("servis surec yasiyor",
            bekle_kosul(lambda: kosum.surec.poll() is None, 5.0),
            f"cikis={kosum.surec.poll()}")
        olc("radar baglantisi kuruldu",
            bekle_kosul(lambda: radar.baglanti_sayisi > 0, 20.0),
            f"baglanti={radar.baglanti_sayisi}")
        olc("LOGIN gonderildi (oturum acildi)",
            bekle_kosul(lambda: radar.login_sayisi > 0, 15.0),
            f"login={radar.login_sayisi}")
        olc("durum dosyasi yazildi",
            bekle_kosul(lambda: bool(kosum.durum()), 20.0))

        olc("durumda radar_bagli alani var",
            "radar_bagli" in kosum.durum(),
            str(list(kosum.durum().keys()))[:200])
        olc("radar bagli olarak bildirildi",
            bekle_kosul(lambda: kosum.durum().get("radar_bagli") is True,
                        20.0),
            f"radar_durum={kosum.durum().get('radar_durum')}")

        bolum("2. HEDEF IZLERI MERKEZE AKIYOR")
        olc("izler durum dosyasina yazildi",
            bekle_kosul(lambda: len(kosum.izler()) >= 3, 25.0),
            f"iz={len(kosum.izler())}")

        izler = kosum.izler()
        if izler:
            iz = izler[0]
            olc("iz kaydinda kimlik var", "id" in iz,
                str(list(iz.keys()))[:200])
            olc("iz kaydinda lat/lon var", "lat" in iz and "lon" in iz,
                str(list(iz.keys()))[:200])
            olc("iz cografi konuma cevrildi",
                isinstance(iz.get("lat"), (int, float)) and iz["lat"] != 0,
                f"lat={iz.get('lat')} lon={iz.get('lon')}")
            olc("iz kaydinda goreli yas var (saat farkindan bagimsiz)",
                "yas_sn" in iz, str(list(iz.keys()))[:200])
            olc("goreli yas makul (0-10 sn)",
                isinstance(iz.get("yas_sn"), (int, float))
                and 0 <= iz["yas_sn"] <= 10,
                f"yas_sn={iz.get('yas_sn')}")
        else:
            olc("iz kaydi incelenebildi", False, "iz yok")

        bolum("3. PANEL KOMUTLARI ISLENIYOR")
        y = kosum.komut("durum")
        olc("durum komutu yanit verdi", bool(y), str(y)[:200])
        olc("durum yaniti basarili", (y or {}).get("tamam") is True,
            str(y)[:200])
        olc("durum yanitinda izler var",
            isinstance((y or {}).get("veri", {}).get("izler"), list),
            str((y or {}).get("veri", {}).keys())[:200])

        y = kosum.komut("ayar_oku")
        olc("ayar_oku yanit verdi", bool(y), str(y)[:200])
        olc("GETREG radara ulasti",
            bekle_kosul(lambda: radar.getreg_sayisi > 0, 10.0),
            f"getreg={radar.getreg_sayisi}")
        olc("ayarlar radardan okundu",
            bekle_kosul(
                lambda: (kosum.durum().get("radar_ayarlar") or {})
                .get("kaynak") == "radar", 10.0),
            str(kosum.durum().get("radar_ayarlar"))[:200])

        y = kosum.komut("ayar_yaz", {"frekans": 3, "tespit_esigi": 2,
                                     "hiz_esigi": 1, "rcs_esigi": 1,
                                     "calisma_modu": 2, "merkez_yonu": 90.0})
        olc("ayar_yaz yanit verdi", bool(y), str(y)[:200])
        olc("SETREG radara ulasti",
            bekle_kosul(lambda: radar.setreg_sayisi > 0, 10.0),
            f"setreg={radar.setreg_sayisi}")
        olc("merkez_yonu panelden uygulandi",
            bekle_kosul(
                lambda: (kosum.durum().get("radar_ayarlar") or {})
                .get("merkez_yonu") == 90.0, 10.0),
            str(kosum.durum().get("radar_ayarlar"))[:200])

        y = kosum.komut("rtk")
        olc("rtk komutu yanit verdi", bool(y), str(y)[:200])
        olc("RTK istegi radara ulasti",
            bekle_kosul(lambda: radar.rtk_sayisi > 0, 10.0),
            f"rtk={radar.rtk_sayisi}")
        olc("RTK konumu ogrenildi (radar_durum.lat)",
            bekle_kosul(
                lambda: isinstance(
                    (kosum.durum().get("radar_durum") or {}).get("lat"),
                    (int, float)), 10.0),
            str(kosum.durum().get("radar_durum"))[:200])

        bolum("4. RADAR SUSTUGUNDA HAYALET HEDEF KALMIYOR")
        onceki = len(kosum.izler())
        olc("olcum oncesi izler vardi", onceki >= 3, f"iz={onceki}")
        radar.iz_gonder = False
        temiz = bekle_kosul(lambda: len(kosum.izler()) == 0, 40.0, 1.0)
        olc("radar susunca izler temizlendi", temiz,
            f"kalan iz={len(kosum.izler())}")
        radar.iz_gonder = True

        bolum("5. BAGLANTIYI KESME")
        y = kosum.komut("kes")
        olc("kes komutu yanit verdi", bool(y), str(y)[:200])
        olc("durum bagli degil olarak guncellendi",
            bekle_kosul(
                lambda: kosum.durum().get("radar_bagli") is not True, 12.0),
            f"radar_bagli={kosum.durum().get('radar_bagli')}")

        bolum("6. SERVIS SAGLIGI")
        olc("servis surec hala yasiyor", kosum.surec.poll() is None,
            f"cikis={kosum.surec.poll()}")
        g = kosum.gunluk_oku()
        olc("gunlukte Traceback yok", "Traceback" not in g,
            g[-500:] if "Traceback" in g else "")
        olc("gunlukte ModuleNotFoundError yok",
            "ModuleNotFoundError" not in g)
        olc("gunlukte bilinmeyen eylem yok", "bilinmeyen eylem" not in g,
            [s for s in g.splitlines() if "bilinmeyen eylem" in s][:3])

    finally:
        kosum.bitir()
        radar.kapat()

    print()
    bolum(f"SONUC: {GECTI} gecti, {KALDI} kaldi")
    if KALAN_AD:
        print("KALANLAR:")
        for a in KALAN_AD:
            print(f"  - {a}")
        print("\nSERVIS GUNLUGU (son 3000):")
        print(kosum.gunluk_oku()[-3000:])
    return 1 if KALDI else 0


if __name__ == "__main__":
    sys.exit(main())
