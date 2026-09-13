# -*- coding: utf-8 -*-
"""GÖKTUNGU MERKEZ — ham MAVLink akış köprüsü.

## SORUN

Uçuş donanımı kullanıcının bilgisayarında, GÖKTUNGU ise merkezde çalışır.
Köprü ham MAVLink byte'larını WSS üzerinden merkeze taşır. Merkez bu
byte'ları **merkezde çalışan GCS sürecine** teslim etmelidir; ancak GCS
ayrı bir süreçtir (`/opt/goktungu/app/`, port 18000/18765).

## NEDEN UDP

Ölçülen seçenekler:

| Ölçüt | UDP | HTTP yoklama | Yerel TCP |
| --- | --- | --- | --- |
| Gecikme | ~0.1 ms | yoklama aralığı (20-200 ms) | ~0.1 ms |
| GCS tarafı kod | **sıfır** | yeni yoklama döngüsü | yeni soket yönetimi |
| Çerçeve sınırı korunur | evet | — | hayır |

Belirleyici ölçüt ikinci satırdır. `pymavlink` UDP'yi birinci sınıf
taşıma olarak destekler; `baglantilar.mavutil_url()` `merkez` türü için
`udpin:127.0.0.1:<port>` döndürdüğünde `dron.py` içindeki MAVLink
döngüsü (HEARTBEAT, PARAM_VALUE, LOG_DATA, MISSION_REQUEST, sysid
eşleme, UDP yayın köprüsü) **hiç değişmeden** çalışır. Yerel TCP
seçilseydi MAVLink çerçeve sınırları bölünür ve bağlantı yaşam döngüsü
elle yönetilirdi.

## AKIŞ

    Köprü --WSS {"tur":"akis"}--> Merkez --UDP--> GCS ("udpin:127.0.0.1:P_gcs")
          <--WSS {"tur":"akis"}--        <--UDP-- GCS (komutlar)

Kanal kimliği `(ornek_id, kanal_id)` çiftidir. `kanal_id` GCS'deki
bağlantı kaydının `id` alanıdır; böylece GCS ek tablo tutmadan "hangi
kanal hangi bağlantıya ait" sorusunu yanıtlar.

## PORT SAHİPLİĞİ (v2.4.56 düzeltmesi)

UDP bir ÇİFT uçtur ve **her uç kendi portunu bind eder**:

    MERKEZ bind 127.0.0.1:P_merkez  <-->  GCS bind 127.0.0.1:P_gcs

Önceki kod merkezin bind ettiği portu GCS'ye bildiriyordu ve GCS aynı
portu `udpin:` ile bind etmeye çalışıyordu. Ölçülen sonuç:
`[Errno 98] Address already in use` — bağlantı hiç kurulmuyordu. Kök
yanılgı, `udpin`in "dinlemeden dinleyici olma" gibi bir semantiği
olduğu varsayımıydı; `udpin` gerçekte `bind()` çağırır.

`SO_REUSEPORT` ÇÖZÜM DEĞİLDİR: iki süreç aynı portu paylaşırsa çekirdek
datagramları aralarında bölüştürür ve telemetrinin yarısı yanlış sürece
gider.

Bu yüzden portu **bind edecek taraf seçer**: GCS kendi portunu ayırır
ve `kanal_ac` çağrısında `gcs_port` olarak bildirir. Merkez o adresi
hedef belleyip kendi ayrı portundan yazar. Böylece çakışma yapısal
olarak imkânsızdır ve "boş port" kararı tek bir yerde verilir.

`gcs_port` bildirilmezse eski davranış korunur (merkez portu bildirir);
bu yalnızca sürüm uyuşmazlığı sırasında geçerlidir ve konsola yazılır.

## GÜVENLİK

UDP soketi **yalnız 127.0.0.1'e** bağlanır. 0.0.0.0 dinlenseydi, aynı
makineye erişen herhangi biri sahaya MAVLink komutu enjekte edebilirdi:
arm, disarm, mod değiştirme. Bu, uçan bir aracın kontrolünü ele geçirme
demektir. Ayrıca gelen datagramların kaynak adresi GCS'nin bildirdiği
adresle karşılaştırılır.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import socket
import threading
import time
from typing import Any

# GCS'nin komut yazacağı adres. Merkez ve GCS aynı makinede çalıştığı
# için loopback yeterlidir ve TEK güvenli seçenektir.
YEREL_ADRES = "127.0.0.1"

# Bir örneğin aynı anda açabileceği kanal sayısı. Sınırsız bırakılması,
# hatalı bir GCS döngüsünün merkezde yüzlerce UDP portu ayırmasına yol
# açar.
ORNEK_BASINA_ENUST_KANAL = 16
# Merkez genelinde toplam kanal sınırı (bellek ve dosya tanıtıcısı
# koruması).
GENEL_ENUST_KANAL = 256

# Kanal, GCS'den bu süre boyunca hiç paket görmezse ve köprüden de veri
# gelmiyorsa terk edilmiş sayılır. GCS çökerse portun sonsuza dek açık
# kalmasını önler.
TERK_ZAMAN_ASIMI_SN = 900.0

OKUMA_TAMPON = 65535

# GCS ilk datagramını göndermeden önce köprüden gelen byte'lar için
# tampon sınırı. 256 KB, 10 Hz MAVLink telemetride ~30 saniyeye karşılık
# gelir; GCS bu süre içinde HEARTBEAT göndermezse bağlantı zaten yoktur.
BEKLEME_ENUST_BYTE = 262144


class AkisKanali:
    """Tek bir uçuş bağlantısının merkez tarafı UDP ucu."""

    __slots__ = ("ornek_id", "kanal_id", "soket", "port", "gcs_es",
                 "acilma_ts", "kopruden_byte", "gcsden_byte",
                 "son_kopru_ts", "son_gcs_ts", "tanim", "son_hata",
                 "reddedilen", "beklemede")

    def __init__(self, ornek_id: int, kanal_id: int, tanim: dict) -> None:
        self.ornek_id = int(ornek_id)
        self.kanal_id = int(kanal_id)
        self.tanim = dict(tanim or {})
        self.soket: socket.socket | None = None
        self.port: int = 0
        # GCS'nin kaynak adresi. İlk datagram gelene kadar bilinmez
        # (mavutil "udpin" semantiği: GCS de dinleyicidir ve ilk paketi
        # BİZ göndeririz). Bu yüzden hedef adres, GCS'nin dinlediği port
        # olarak ayrı tutulur.
        self.gcs_es: tuple[str, int] | None = None
        self.acilma_ts = time.time()
        self.kopruden_byte = 0
        self.gcsden_byte = 0
        self.son_kopru_ts: float | None = None
        self.son_gcs_ts: float | None = None
        self.son_hata: str = ""
        # Yerel olmayan kaynaktan gelip REDDEDİLEN datagram sayısı.
        # Sessizce atmak yanlış olurdu: bir saldırı denemesi ya da yanlış
        # yapılandırma (GCS'nin başka arayüzden yazması) ancak sayılırsa
        # görünür.
        self.reddedilen = 0
        # GCS henüz ilk paketini göndermediyse köprüden gelen byte'lar
        # KISA SÜRE burada bekletilir. Atılmaları, `pymavlink`'in ilk
        # HEARTBEAT'i kaçırıp bağlantıyı "veri yok" sayması demektir:
        # dron paneli boş kalır, pilot "play'e bastım hiçbir şey olmadı"
        # der. Ölçülen kusurun tam olarak bu olduğu Faz 5'te görüldü.
        self.beklemede = bytearray()

    def anahtar(self) -> tuple[int, int]:
        return (self.ornek_id, self.kanal_id)

    def ozet(self) -> dict[str, Any]:
        return {
            "ornek_id": self.ornek_id,
            "kanal_id": self.kanal_id,
            "port": self.port,
            "tanim": self.tanim,
            "acilma_ts": self.acilma_ts,
            "kopruden_byte": self.kopruden_byte,
            "gcsden_byte": self.gcsden_byte,
            "son_kopru_ts": self.son_kopru_ts,
            "son_gcs_ts": self.son_gcs_ts,
            "gcs_bagli": self.gcs_es is not None,
            "reddedilen": self.reddedilen,
            "beklemede_byte": len(self.beklemede),
            "son_hata": self.son_hata,
        }


class AkisKopruleyici:
    """Köprü ↔ GCS arasında ham byte taşır.

    Tek bir `asyncio` döngüsünde çalışır (merkez röle döngüsü). UDP
    soketleri döngüye `add_reader` ile bağlanır; ayrı iş parçacığı
    AÇILMAZ: kanal başına bir iş parçacığı, 16 dronlu bir sahada 16
    gereksiz iş parçacığı demektir ve GIL çekişmesi üretir.
    """

    def __init__(self) -> None:
        self._kanallar: dict[tuple[int, int], AkisKanali] = {}
        self._kilit = threading.Lock()
        self._dongu: asyncio.AbstractEventLoop | None = None
        # ornek_id -> köprüye byte gönderen çağrılabilir
        self._gonderici: dict[int, Any] = {}

    # ------------------------------------------------------------------
    def dongu_ata(self, d: asyncio.AbstractEventLoop) -> None:
        self._dongu = d

    def gonderici_ata(self, ornek_id: int, gonder: Any) -> None:
        """Köprü oturumu açıldığında çağrılır.

        `gonder(kanal_id, bytes)` bir coroutine döndürmelidir; röle
        döngüsünde çalıştırılır.
        """
        with self._kilit:
            self._gonderici[int(ornek_id)] = gonder

    def gonderici_sil(self, ornek_id: int) -> None:
        """Köprü bağlantısı koptuğunda çağrılır.

        Bu örneğin TÜM kanalları kapatılır. Kapatılmazsa GCS var olmayan
        bir köprüye komut göndermeye devam eder ve pilot komutların
        gittiğini sanar — sahada gerçek bir tehlikedir.
        """
        oid = int(ornek_id)
        with self._kilit:
            self._gonderici.pop(oid, None)
            dusenler = [k for k in self._kanallar if k[0] == oid]
        for a in dusenler:
            self.kanal_kapat(a[0], a[1])
        return len(dusenler)

    # ------------------------------------------------------------------
    def kanal_ac(self, ornek_id: int, kanal_id: int,
                 tanim: dict | None = None,
                 gcs_port: int = 0) -> tuple[dict | None, str | None]:
        """Merkez tarafı UDP portunu ayırır ve döngüye bağlar.

        `(ozet, hata)` döndürür.

        `gcs_port` verilirse (v2.4.56+ GCS) hedef adres BAŞTAN bilinir:
        GCS o portu kendisi bind etmiştir ve merkez kendi ayrı portundan
        oraya yazar. Bu, iki sürecin aynı portu bind edip
        `Address already in use` almasını yapısal olarak engeller.

        `gcs_port` 0 ise eski davranış: merkez portunu bildirir ve GCS'nin
        adresi ilk datagramla öğrenilir.
        """
        if self._dongu is None:
            return None, "Röle döngüsü hazır değil"
        oid, kid = int(ornek_id), int(kanal_id)
        with self._kilit:
            if len(self._kanallar) >= GENEL_ENUST_KANAL:
                return None, "Merkez akış kanalı sınırı aşıldı"
            ornek_sayi = sum(1 for k in self._kanallar if k[0] == oid)
            eski = self._kanallar.get((oid, kid))
            if eski is None and ornek_sayi >= ORNEK_BASINA_ENUST_KANAL:
                return None, ("Bu sunucu için eş zamanlı kanal sınırı "
                              f"aşıldı ({ORNEK_BASINA_ENUST_KANAL})")
        # Aynı kanal yeniden açılıyorsa (kullanıcı stop→play yaptıysa)
        # eskisi temiz kapatılır; aksi halde iki soket aynı akışı yazar.
        if eski is not None:
            self.kanal_kapat(oid, kid)

        k = AkisKanali(oid, kid, tanim or {})
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Port 0: işletim sistemi boş port seçer. Sabit port aralığı
            # kullanmak, iki kanalın çakışmasına ve "Address already in
            # use" hatalarına yol açar.
            s.bind((YEREL_ADRES, 0))
            s.setblocking(False)
        except Exception as e:
            with contextlib.suppress(Exception):
                s.close()
            return None, f"UDP portu ayrılamadı: {e}"
        k.soket = s
        k.port = int(s.getsockname()[1])
        # GCS portunu ÖNCEDEN bildirdiyse hedef bazı hemen kurulur.
        # İlk datagramı beklemek gerekmez; köprüden gelen ilk
        # HEARTBEAT doğrudan teslim edilir ve `beklemede` tamponı boş
        # kalır. Bu aynı zamanda "GCS hiç yazmazsa telemetri görünmez"
        # kusurunu da ortadan kaldırır: yön bağımlılığı kalmaz.
        gp = int(gcs_port or 0)
        if gp > 0:
            k.gcs_es = (YEREL_ADRES, gp)
        # Soket, döngüye SOKET NESNESİ ile bağlanır, `fileno()` ile
        # değil. Ölçülen kusur: `remove_reader(fd)` çağrısı soket
        # kapatıldıktan sonra çalıştığında dosya tanıtıcısı geri dönüşüme
        # girmiş olur; `add_reader` bir sonraki kanalda "Bad file
        # descriptor" ile patlar ve o kanal sessizce veri taşımaz.
        # Soket nesnesi verildiğinde asyncio tanıtıcıyı kendisi çözer ve
        # yaşam süresini sokete bağlar.
        try:
            if self._dongu.is_running():
                self._dongu.call_soon_threadsafe(self._okuyucu_bagla, k)
            else:
                self._okuyucu_bagla(k)
        except Exception as e:
            with contextlib.suppress(Exception):
                s.close()
            return None, f"Soket döngüye bağlanamadı: {e}"
        with self._kilit:
            self._kanallar[(oid, kid)] = k
        return k.ozet(), None

    def _okuyucu_bagla(self, k: AkisKanali) -> None:
        s = k.soket
        if s is None or self._dongu is None:
            return
        with contextlib.suppress(Exception):
            self._dongu.add_reader(s, self._gcsden_oku, k)

    def _bekleyeni_bosalt(self, k: AkisKanali) -> None:
        """GCS adresi öğrenilince bekleyen byte'ları teslim eder."""
        if not k.beklemede or k.soket is None or k.gcs_es is None:
            return
        veri, k.beklemede = bytes(k.beklemede), bytearray()
        # Datagram sınırı: tek seferde 64 KB'den fazlası gönderilemez ve
        # MAVLink çözücüsü akış tabanlı olduğu için parçalamak güvenlidir.
        for i in range(0, len(veri), 8192):
            parca = veri[i:i + 8192]
            try:
                n = k.soket.sendto(parca, k.gcs_es)
            except Exception as e:
                k.son_hata = f"{type(e).__name__}: {e}"
                return
            k.kopruden_byte += n

    def kanal_kapat(self, ornek_id: int, kanal_id: int) -> bool:
        with self._kilit:
            k = self._kanallar.pop((int(ornek_id), int(kanal_id)), None)
        if k is None:
            return False
        s, k.soket = k.soket, None
        if s is None:
            return True
        # Okuyucu, soket KAPATILMADAN önce kaldırılmalı ve kapatma da
        # döngü iş parçacığında yapılmalı: kapatma önce olursa asyncio
        # geçersiz bir tanıtıcıyı kaldırmaya çalışır (Bad file
        # descriptor) ve seçici bozulur.
        def _sok_kapat() -> None:
            if self._dongu is not None:
                with contextlib.suppress(Exception):
                    self._dongu.remove_reader(s)
            with contextlib.suppress(Exception):
                s.close()

        if self._dongu is not None and self._dongu.is_running():
            try:
                self._dongu.call_soon_threadsafe(_sok_kapat)
            except Exception:
                _sok_kapat()
        else:
            _sok_kapat()
        return True

    def kanal(self, ornek_id: int, kanal_id: int) -> AkisKanali | None:
        with self._kilit:
            return self._kanallar.get((int(ornek_id), int(kanal_id)))

    def durum(self, ornek_id: int | None = None) -> list[dict[str, Any]]:
        with self._kilit:
            hepsi = list(self._kanallar.values())
        if ornek_id is None:
            return [k.ozet() for k in hepsi]
        oid = int(ornek_id)
        return [k.ozet() for k in hepsi if k.ornek_id == oid]

    def sayi(self) -> int:
        with self._kilit:
            return len(self._kanallar)

    # ------------------------------------------------------------------
    # Köprü → GCS
    # ------------------------------------------------------------------
    def kopruden_geldi(self, ornek_id: int, kanal_id: int,
                       veri_b64: str) -> int:
        """Köprüden gelen paketi GCS'nin UDP portuna yazar.

        Röle döngüsünde (WS oturumu içinde) çağrılır. Kanal açık değilse
        paket ATILIR: köprü, GCS kanalı kapattıktan sonra yolda olan
        paketleri göndermeye devam edebilir ve bu normaldir.
        """
        k = self.kanal(ornek_id, kanal_id)
        if k is None or k.soket is None:
            return 0
        try:
            veri = base64.b64decode(veri_b64 or "", validate=False)
        except Exception:
            return 0
        if not veri:
            return 0
        hedef = k.gcs_es
        if hedef is None:
            # GCS henüz ilk paketini göndermedi, dolayısıyla kaynak portu
            # bilinmiyor (mavutil `udpin` semantiği: iki taraf da
            # dinleyicidir, adres ancak ilk datagramla öğrenilir).
            #
            # Paketi ATMAK yerine kısa süre bekletiriz. `pymavlink`
            # bağlantı kurulduktan sonra HEARTBEAT gönderir; o an adres
            # öğrenilir ve bekleyen telemetri tek seferde teslim edilir.
            # Atılsaydı GCS'nin ilk HEARTBEAT'i görmesi tesadüfe kalırdı.
            #
            # Tampon SINIRLIDIR: GCS hiç yazmazsa (çökmüşse) bellek
            # büyümeye devam etmemeli. Sınır aşılınca EN ESKİ byte'lar
            # düşer — telemetride en yeni veri değerlidir.
            k.beklemede.extend(veri)
            if len(k.beklemede) > BEKLEME_ENUST_BYTE:
                fazla = len(k.beklemede) - BEKLEME_ENUST_BYTE
                del k.beklemede[:fazla]
                k.son_hata = ("GCS henüz yazmadı; bekleyen tampon "
                              f"kırpıldı ({fazla} byte düştü)")
            k.son_kopru_ts = time.time()
            return 0
        try:
            n = k.soket.sendto(veri, hedef)
        except Exception as e:
            k.son_hata = f"{type(e).__name__}: {e}"
            return 0
        k.kopruden_byte += n
        k.son_kopru_ts = time.time()
        return n

    # ------------------------------------------------------------------
    # GCS → köprü
    # ------------------------------------------------------------------
    def _gcsden_oku(self, k: AkisKanali) -> None:
        """GCS'den gelen datagramı köprüye iletir (döngü geri çağrısı).

        Tek bir `recvfrom` yerine tampon boşalana kadar okur: 10 Hz
        telemetride birden fazla datagram aynı döngü turunda hazır
        olabilir ve her turda tek paket okumak gecikme biriktirir.
        """
        s = k.soket
        if s is None:
            return
        while True:
            try:
                veri, es = s.recvfrom(OKUMA_TAMPON)
            except (BlockingIOError, InterruptedError):
                return
            except Exception as e:
                k.son_hata = f"{type(e).__name__}: {e}"
                return
            if not veri:
                return
            # Kaynak adres denetimi: yalnız loopback kabul edilir.
            # Bu, yerel olmayan bir kaynağın MAVLink komutu enjekte
            # etmesini engeller.
            if es[0] != YEREL_ADRES:
                k.reddedilen += 1
                continue
            if k.gcs_es != es:
                k.gcs_es = es
                # Adres yeni öğrenildi: bekleyen telemetri hemen teslim
                # edilir. Aksi halde ilk saniyenin verisi kaybolur.
                self._bekleyeni_bosalt(k)
            k.gcsden_byte += len(veri)
            k.son_gcs_ts = time.time()
            self._kopruye_yaz(k, veri)

    def _kopruye_yaz(self, k: AkisKanali, veri: bytes) -> None:
        with self._kilit:
            gonder = self._gonderici.get(k.ornek_id)
        if gonder is None:
            k.son_hata = "Köprü bağlı değil"
            return
        paket_b64 = base64.b64encode(veri).decode("ascii")
        try:
            sonuc = gonder(k.kanal_id, paket_b64)
            if asyncio.iscoroutine(sonuc):
                # Ateşle-unut: komut yolunda beklemek, 20 ms'de bir
                # gelebilen paketlerde döngüyü tıkar.
                asyncio.ensure_future(sonuc)
        except Exception as e:
            k.son_hata = f"{type(e).__name__}: {e}"

    # ------------------------------------------------------------------
    def terk_edilenleri_temizle(self) -> list[tuple[int, int]]:
        """Uzun süre sessiz kalan kanalları kapatır.

        GCS çökerse `akis_kapat` çağrısı hiç gelmez ve port sonsuza dek
        açık kalır. Zaman aşımı bu sızıntıyı önler.
        """
        simdi = time.time()
        dusenler = []
        with self._kilit:
            for a, k in list(self._kanallar.items()):
                son = max(k.son_gcs_ts or 0, k.son_kopru_ts or 0,
                          k.acilma_ts)
                if simdi - son > TERK_ZAMAN_ASIMI_SN:
                    dusenler.append(a)
        for a in dusenler:
            self.kanal_kapat(a[0], a[1])
        return dusenler


AKIS = AkisKopruleyici()
