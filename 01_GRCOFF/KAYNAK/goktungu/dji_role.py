# -*- coding: utf-8 -*-
"""DJI ROLE ADAPTORU — Android DJI koprusunun GDP akisini role kanalindan
merkezdeki GDP TCP sunucusuna baglar (v2.4.233).

## NEDEN

Kullanici kurali: GRCON'a hicbir dron dogrudan baglanamaz, yalniz kopru
uzerinden gelir. Android DJI koprusu 1.1.0 ile gercek kopru ajani oldu;
GDP (NDJSON) satirlarini artik dogrudan TCP 8790'a degil, kopru role
kanalina (`{"tur":"akis"}`) yazar. Merkezdeki `DjiKopruYoneticisi` ise
TCP soketi bekler ve DEGISTIRILMEZ (mesaj isleme, sysid esleme, komut
kuyrugu orada dogru calisiyor).

Bu adaptor iki ucu birbirine baglar:

    role (UDP 127.0.0.1:<gcs_port>)  <-->  DJI sunucusu (TCP 127.0.0.1:<port>)

MAVLink ile ayni desen: `_akis_kanali_ac` bos bir UDP portu secip
role'ye bildirir; role kopruden gelen byte'lari o porta yazar ve
GCS'nin o porttan yazdigi datagrami kopruye gonderir. Adaptor bu
portu bind eder, yerel DJI dinleyicisine TCP ile baglanir ve iki yonde
byte tasir. Satir sinirlari korunur: UDP datagramlari tam satir
tasimayabilir; TCP akis oldugu icin DJI sunucusu satirlari kendisi
birlestirir (`tampon += veri`), ters yonde de datagram sinirlari GDP
icin onemsizdir (Android tarafi satir ayirir).

Belirtec: DJI sunucusu 127.0.0.1'den gelen istemciden belirtec ISTEMEZ
(yerel kurulum kurali); kimlik zaten kopru el sikismasinda dogrulandi.
"""
import contextlib
import socket
import threading
import time


class DjiRoleAdaptoru:
    def __init__(self, bid, udp_port, tcp_port, konsol=None, etiket=""):
        self.bid = int(bid)
        self.udp_port = int(udp_port)
        self.tcp_port = int(tcp_port)
        self.konsol = konsol
        self.etiket = etiket or str(bid)
        self._dur = threading.Event()
        self._udp = None
        self._tcp = None
        self._merkez_es = None
        self._iplikler = []
        self.udp_to_tcp = 0
        self.tcp_to_udp = 0
        self.son_hata = ""

    def _yaz(self, m, seviye="bilgi"):
        if self.konsol:
            with contextlib.suppress(Exception):
                self.konsol("DJI", "[%s] %s" % (self.etiket, m), seviye)

    def baslat(self):
        """Soketleri acar ve iki tasima ipligini baslatir; hata metni doner."""
        u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            u.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            u.bind(("127.0.0.1", self.udp_port))
            u.settimeout(0.5)
        except OSError as e:
            with contextlib.suppress(Exception):
                u.close()
            return "Role UDP portu (%d) baglanamadi: %s" % (self.udp_port, e)
        self._udp = u
        # DJI dinleyicisi ayri iplikte acilir; birkac deneme.
        t = None
        hata = ""
        for _ in range(20):
            try:
                t = socket.create_connection(("127.0.0.1", self.tcp_port),
                                             timeout=2.0)
                t.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                t.settimeout(0.5)
                break
            except OSError as e:
                hata = str(e)
                time.sleep(0.15)
        if t is None:
            with contextlib.suppress(Exception):
                u.close()
            self._udp = None
            return "DJI dinleyicisine (127.0.0.1:%d) baglanilamadi: %s" % (
                self.tcp_port, hata)
        self._tcp = t
        a = threading.Thread(target=self._udp_to_tcp, daemon=True,
                             name="dji-role-u2t-%d" % self.bid)
        b = threading.Thread(target=self._tcp_to_udp, daemon=True,
                             name="dji-role-t2u-%d" % self.bid)
        self._iplikler = [a, b]
        a.start()
        b.start()
        self._yaz("Role adaptoru acildi: UDP %d <-> TCP %d"
                  % (self.udp_port, self.tcp_port), "basari")
        return None

    def _udp_to_tcp(self):
        while not self._dur.is_set():
            try:
                veri, es = self._udp.recvfrom(65536)
            except socket.timeout:
                continue
            except OSError:
                break
            if not veri or es[0] != "127.0.0.1":
                continue
            self._merkez_es = es
            try:
                self._tcp.sendall(veri)
                self.udp_to_tcp += len(veri)
            except OSError as e:
                self.son_hata = "TCP yazma: %s" % e
                break
        self._dur.set()

    def _tcp_to_udp(self):
        while not self._dur.is_set():
            try:
                veri = self._tcp.recv(65536)
            except socket.timeout:
                continue
            except OSError:
                break
            if not veri:
                break
            es = self._merkez_es
            if es is None:
                # Android henuz yazmadi: DJI sunucusu da merhaba
                # gelmeden komut gondermez; nadir yaris, paket dusurulur.
                continue
            try:
                for i in range(0, len(veri), 8192):
                    self._udp.sendto(veri[i:i + 8192], es)
                self.tcp_to_udp += len(veri)
            except OSError as e:
                self.son_hata = "UDP yazma: %s" % e
                break
        self._dur.set()

    def durdur(self):
        self._dur.set()
        for s in (self._tcp, self._udp):
            with contextlib.suppress(Exception):
                if s is not None:
                    s.close()
        self._tcp = None
        self._udp = None
        self._yaz("Role adaptoru kapatildi", "bilgi")

    def calisiyor(self):
        return not self._dur.is_set()

    def durum(self):
        return {"bid": self.bid, "udp_port": self.udp_port,
                "tcp_port": self.tcp_port, "calisiyor": self.calisiyor(),
                "kopruden_byte": self.udp_to_tcp,
                "kopruye_byte": self.tcp_to_udp, "son_hata": self.son_hata}
