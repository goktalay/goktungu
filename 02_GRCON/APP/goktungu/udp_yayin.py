# -*- coding: utf-8 -*-
"""UdpYayinYoneticisi: her bagli dron icin UDP MAVLink koprusu.

Amac: Mission Planner (veya baska bir GCS) ile bu program ayni anda
calisabilsin. Her dron icin 9000+sysid numarali UDP portu acilir:

  - Drondan gelen HER MAVLink paketi (ham bayt) bu porta baglanan
    istemcilere iletilir (dinleyen istemci adresleri ogrenilir).
  - Istemciden (Mission Planner) gelen paketler dronun gercek
    baglantisina geri yazilir (cift yonlu kopru).

Mission Planner baglanti sekli: Connect -> UDPCI (UDP client) ->
host: bu bilgisayarin IP'si, port: 9000+sysid.
Ya da "UDP" secip local port'u 9000+sysid yaparak dinleme modunda
paketleri alabilir; iki yontem de desteklenir:
  - Sunucu tarafi 9000+sysid portunu BIND eder.
  - Istemciden ilk paket gelene kadar yayin yapilacak adres
    bilinmez; istemci "hello" niteliginde herhangi bir paket
    (ornegin kendi HEARTBEAT'ini) gonderince adres kaydedilir.
  - Birden fazla istemci desteklenir (son 10 sn icinde paket
    gondermis adresler canli sayilir).

NOT: MAVLink paketleri degistirilmeden ham olarak kopyalanir; sysid
carpismasi olmaz cunku ayni dronun paketleridir.
"""
import socket
import threading
import time

TEMEL_PORT = 9000
ISTEMCI_ZAMANASIMI = 10.0   # s; bu sure paket gondermeyen istemci duser


def lan_ip():
    """Bu makinenin LAN uzerinde erisilebilir IP adresini dondurur.

    v2.4.39 gerekcesi: soket bagi ZATEN 0.0.0.0 (tum arayuzler), yani
    aginizdaki baska bir bilgisayardan baglanmak teknik olarak mumkundu.
    Sorun gosterilen adresteydi: arayuz `window.location.hostname` yaziyordu
    ve kullanici tarayiciyi 127.0.0.1 uzerinden actiginda dis makineye
    verilecek adres olarak "127.0.0.1" gorunuyordu. Loopback adresi baska
    bir bilgisayardan asla erisilemez; kullanici hakli olarak "127.0.0.1
    dinliyorsun" izlenimi edindi.

    Olculmus tuzak: socket.gethostbyname(socket.gethostname()) bu ortamda
    127.0.0.1 dondurdu. Guvenilir yontem, UDP soketini dis bir adrese
    connect() edip getsockname() okumaktir; UDP'de connect() paket
    GONDERMEZ, yalnizca cekirdegin yonlendirme tablosunu sorgular. Bu
    yuzden internet erisimi olmayan kapali agda da calisir.
    """
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.3)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass
    finally:
        if s is not None:
            try:
                s.close()
            except OSError:
                pass
    # Yedek: hostname cozumlemesi (loopback donebilir, yine de bir sey)
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass
    return ""


class UdpYayinYoneticisi:

    def __init__(self, dron, konsol):
        self.dron = dron          # DronYoneticisi (master_bul icin)
        self.konsol = konsol
        self._lan = None          # v2.4.39: LAN adresi (bir kez olculur)
        self._kilit = threading.Lock()
        # sysid -> {"sock", "port", "istemciler": {addr: son_zaman},
        #           "thread", "durdur"}
        self._koprular = {}

    # ------------------------------------------------------------------
    def port_no(self, sysid):
        return TEMEL_PORT + int(sysid)

    def lan_adres(self):
        """LAN adresini dondurur (bir kez olculup onbelleklenir).

        Neden onbellek: lan_adres() her HEARTBEAT'te degil yalnizca kopru
        kurulurken cagriliyor, ama yine de soket acmayi tekrarlamanin
        anlami yok. Adres degisirse (ag kartı degisimi) sunucu yeniden
        baslatildiginda tazelenir.
        """
        if self._lan is None:
            self._lan = lan_ip()
        return self._lan

    def portlar(self):
        """Telemetri yayini icin sysid -> port sozlugu."""
        with self._kilit:
            return {str(s): k["port"] for s, k in self._koprular.items()}

    # ------------------------------------------------------------------
    def dron_ekle(self, sysid):
        """Yeni dron gorulunce koprusunu kurar (idempotent)."""
        sysid = int(sysid)
        with self._kilit:
            if sysid in self._koprular:
                return self._koprular[sysid]["port"]
        port = self.port_no(sysid)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", port))
            sock.settimeout(1.0)
        except OSError as e:
            self.konsol("UDP", f"Port {port} acilamadi: {e}", "hata")
            return None
        durdur = threading.Event()
        kayit = {"sock": sock, "port": port, "istemciler": {},
                 "durdur": durdur}
        t = threading.Thread(target=self._alici_dongu,
                             args=(sysid, kayit), daemon=True)
        kayit["thread"] = t
        with self._kilit:
            self._koprular[sysid] = kayit
        t.start()
        self.konsol("UDP",
                    f"sysid={sysid} MAVLink UDP yayini basladi "
                    f"(port {port})", "basari")
        return port

    def dron_sil(self, sysid):
        """Dron dustugunde koprusunu kapatir."""
        sysid = int(sysid)
        with self._kilit:
            kayit = self._koprular.pop(sysid, None)
        if not kayit:
            return
        kayit["durdur"].set()
        try:
            kayit["sock"].close()
        except OSError:
            pass
        self.konsol("UDP", f"sysid={sysid} UDP yayini durdu "
                    f"(port {kayit['port']})")

    def tumunu_durdur(self):
        with self._kilit:
            sysidler = list(self._koprular.keys())
        for s in sysidler:
            self.dron_sil(s)

    # ------------------------------------------------------------------
    def paket_yayinla(self, sysid, veri):
        """Drondan gelen ham MAVLink baytlarini istemcilere gonderir.

        DronYoneticisi._dongu icinden her mesaj icin cagrilir
        (msg.get_msgbuf()). Istemci yoksa hizli cikar.
        """
        kayit = self._koprular.get(int(sysid))
        if not kayit or not kayit["istemciler"]:
            return
        simdi = time.time()
        olu = []
        for addr, son in list(kayit["istemciler"].items()):
            if simdi - son > ISTEMCI_ZAMANASIMI:
                olu.append(addr)
                continue
            try:
                kayit["sock"].sendto(veri, addr)
            except OSError:
                olu.append(addr)
        for addr in olu:
            kayit["istemciler"].pop(addr, None)

    # ------------------------------------------------------------------
    def _alici_dongu(self, sysid, kayit):
        """Istemciden (Mission Planner) gelen paketleri drona yazar."""
        sock = kayit["sock"]
        durdur = kayit["durdur"]
        while not durdur.is_set():
            try:
                veri, addr = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break   # soket kapatildi
            if not veri:
                continue
            # Istemciyi kaydet/tazele (yayin adresi olarak kullanilir)
            yeni = addr not in kayit["istemciler"]
            kayit["istemciler"][addr] = time.time()
            if yeni:
                self.konsol("UDP",
                            f"sysid={sysid} porta yeni istemci: "
                            f"{addr[0]}:{addr[1]}", "basari")
            # Paketi dronun gercek baglantisina ilet (cift yon)
            master = self.dron.master_bul(sysid)
            if master is None:
                continue
            try:
                master.write(veri)
            except Exception:
                pass
