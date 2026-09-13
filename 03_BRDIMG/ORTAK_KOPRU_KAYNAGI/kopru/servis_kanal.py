# -*- coding: utf-8 -*-
"""KOPRU YAZILIMI — PANEL <-> ALT SERVIS KOMUT KANALI.

## NEDEN GEREKLI

Alt servisler (dron/ai/video/gcsdual/radar) AYRI SURECLERDIR. Panel ve
ajan sureci onlarin bellegine erisemez. Bugune kadar tek yon vardi:

    alt servis  --(durum_yaz -> durum_XXX.json)-->  panel

Ters yon YOKTU. Merkezden gelen bir komut (ornegin "cantayi /dev/ttyACM0
portuna bagla", "P3 LED'ini yak", "eksenleri kalibre et") alt surece hic
ulasamiyordu. Merkez bu yuzden komutu KENDI surecinde uygulamaya
calisiyordu; merkezde seri port olmadigi icin de

    [Errno 2] could not open port /dev/ttyACM0

hatasi uretiyordu (KUSUR-GCSDUAL-PORT). Aygit SAHA makinesinde takilidir.

## NEDEN DOSYA, NEDEN SOKET DEGIL

Soket (TCP/named pipe) daha dogal gorunur ama bu kurulumda uc sorun
uretir:

1. Windows'ta servis LocalSystem hesabinda, panel ise kullanici
   oturumunda kosar. Adlandirilmis kanal ACL'leri iki hesap arasinda
   elle ayarlanmak zorundadir; yanlis ayar sessiz erisim reddi verir.
2. Yerel TCP portu acmak, guvenlik duvari istemi ureten ve baska
   yazilimla catisabilen yeni bir dinleyici demektir. Kullanici
   kurulumda zaten bir istem gordu; ikincisi kabul edilemez.
3. Olcum yolu (durum dosyasi) ZATEN dosya tabanli ve sahada calisiyor.
   Ayni deseni kullanmak, tek bir hata sinifiyla ugrasmak demektir.

Dosya yolu ayrica servis COKUP yeniden basladiginda bekleyen komutun
kaybolmamasini saglar.

## PROTOKOL

Iki ayri dosya kullanilir; boylece yazan taraf hic okumak zorunda
kalmaz ve kilit gerekmez:

    komut_<servis>.json    panel YAZAR,  servis OKUR ve SILER
    yanit_<servis>.json    servis YAZAR, panel OKUR

Komut dosyasi bir LISTEDIR (kuyruk). Bicim:

    [{"id": "k7", "eylem": "baglan", "veri": {"port": "/dev/ttyACM0"}}]

Yanit dosyasi son N yaniti tutan bir listedir:

    [{"id": "k7", "tamam": true, "hata": "", "ts": 1755...}]

`id` zorunludur: panel yanitin HANGI komuta ait oldugunu bilmeli. Id
olmadan iki hizli komuttan hangisinin basarisiz oldugu ayirt edilemez.

## ATOMIKLIK

Her iki yon de `os.replace` ile atomik yazar. Dogrudan yazim, okuma tam
yazma anina denk geldiginde YARIM JSON verir; okuyan taraf bunu "bozuk
komut" sayip ATAR ve komut sessizce kaybolur. Sahada bu, pilotun
"Baglan"a basip hicbir sey olmamasi demektir.

## KUYRUK SINIRI

Komut kuyrugu `KUYRUK_SINIR` ile sinirlidir. Servis durmusken panelden
art arda basilan dugmeler sinirsiz birikirse, servis acildiginda
onlarca eski komut birden uygulanir (ornegin cantaya 40 kez LED
komutu). Sinir asilinca EN ESKI komut dusurulur: en guncel niyet
korunur.
"""
import json
import os
import tempfile
import time

KUYRUK_SINIR = 32
YANIT_SINIR = 32

# Yanitlarin gecerlilik suresi. Bundan eski yanitlar okunmaz: panel
# yeniden acildiginda gecen oturumun "basarili" yanitini GUNCEL sanip
# canta bagli gostermemeli.
YANIT_TAZE_SN = 120.0


def _atomik_yaz(yol, veri):
    """JSON'u atomik olarak yazar. Basari/basarisizlik dondurur."""
    try:
        dizin = os.path.dirname(yol) or "."
        os.makedirs(dizin, exist_ok=True)
        gecici = None
        with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=dizin, delete=False,
                prefix=".kanal_", suffix=".tmp") as f:
            gecici = f.name
            json.dump(veri, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(gecici, yol)
        return True
    except Exception:
        try:
            if gecici and os.path.exists(gecici):
                os.remove(gecici)
        except Exception:
            pass
        return False


def _oku_liste(yol):
    """Dosyadaki listeyi okur; yoksa veya bozuksa bos liste doner."""
    try:
        with open(yol, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, list) else []
    except Exception:
        return []


def komut_dosyasi(dizin, servis):
    return os.path.join(dizin, "komut_%s.json" % servis)


def yanit_dosyasi(dizin, servis):
    return os.path.join(dizin, "yanit_%s.json" % servis)


# ---------------------------------------------------------------------
# PANEL TARAFI
# ---------------------------------------------------------------------
def komut_yaz(dizin, servis, eylem, veri=None, komut_id=None):
    """Panelden alt servise komut kuyruklar. Donus: komut kimligi.

    Servisin CALISIP calismadigi BURADA denetlenmez; cagiran taraf
    bilir. Kuyruklamak yine de dogrudur: servis birkac saniye sonra
    aciliyorsa komut uygulanir.
    """
    yol = komut_dosyasi(dizin, servis)
    kid = str(komut_id or ("k%d" % int(time.time() * 1000)))
    kuyruk = _oku_liste(yol)
    kuyruk.append({"id": kid, "eylem": str(eylem),
                   "veri": dict(veri or {}), "ts": time.time()})
    if len(kuyruk) > KUYRUK_SINIR:
        kuyruk = kuyruk[-KUYRUK_SINIR:]
    _atomik_yaz(yol, kuyruk)
    return kid


def yanit_oku(dizin, servis, komut_id=None, taze_sn=YANIT_TAZE_SN):
    """Servisin yazdigi yanitlari okur.

    `komut_id` verilirse YALNIZ o komutun yaniti doner (yoksa None).
    Verilmezse taze yanitlarin tamami doner.
    """
    simdi = time.time()
    tumu = [y for y in _oku_liste(yanit_dosyasi(dizin, servis))
            if isinstance(y, dict)
            and simdi - float(y.get("ts") or 0) <= taze_sn]
    if komut_id is None:
        return tumu
    for y in tumu:
        if str(y.get("id")) == str(komut_id):
            return y
    return None


def yanit_bekle(dizin, servis, komut_id, zaman_asimi=8.0, aralik=0.15):
    """Yaniti YOKLAMA ile bekler. Donus: yanit sozlugu veya None.

    Neden yoklama: alt surecin dosyayi ne zaman yazacagini bildiren bir
    olay mekanizmasi yok. Aralik 150 ms'dir; kullanici dugmeye bastikta
    gecikmeyi fark etmez, buna karsin saniyede 7 dosya okumasi ihmal
    edilebilir yuktur.

    Zaman asiminda None doner. Cagiran taraf bunu "servis yanit
    vermedi" olarak BILDIRMELIDIR; sessizce basarili saymak, pilotun
    baglanmamis cantayla ucusa hazirlanmasina yol acar.
    """
    bitis = time.time() + max(0.5, float(zaman_asimi or 0))
    while time.time() < bitis:
        y = yanit_oku(dizin, servis, komut_id)
        if y is not None:
            return y
        time.sleep(aralik)
    return None


def kanal_temizle(dizin, servis):
    """Servis baslatilirken onceki oturumun artiklarini siler.

    Silinmezse iki sorun olur: (a) gecen oturumda basilmis dugmeler
    servis acilir acilmaz uygulanir, (b) eski "basarili" yaniti panel
    guncel sanir.
    """
    for yol in (komut_dosyasi(dizin, servis), yanit_dosyasi(dizin, servis)):
        try:
            if os.path.exists(yol):
                os.remove(yol)
        except Exception:
            pass


# ---------------------------------------------------------------------
# SERVIS TARAFI
# ---------------------------------------------------------------------
class ServisKanali:
    """Alt servisin komut okuma / yanit yazma yuzu.

    Ortam degiskenleriyle kurulur; servis kodu dosya yollarini bilmek
    zorunda kalmaz:

        GOKTUNGU_KOPRU_KANAL_DIZIN   komut/yanit dosyalarinin dizini
        GOKTUNGU_KOPRU_SERVIS_ADI    servis adi (dosya adlarinda kullanilir)

    Ortam degiskeni YOKSA kanal sessizce devre disi kalir ve `oku()`
    bos liste doner. Bu bilincli bir karardir: servis elle komut
    satirindan da calistirilabilmeli (gelistirme/teshis) ve o durumda
    kanal olmamasi hata degildir.
    """

    def __init__(self, dizin=None, servis=None):
        self.dizin = dizin or os.environ.get("GOKTUNGU_KOPRU_KANAL_DIZIN") or ""
        self.servis = servis or os.environ.get("GOKTUNGU_KOPRU_SERVIS_ADI") or ""
        self._yanitlar = []

    def etkin(self):
        return bool(self.dizin and self.servis)

    def oku(self):
        """Bekleyen komutlari dondurur ve kuyrugu BOSALTIR.

        Bosaltma okuma ile AYNI adimda yapilir; ayri birakilirsa servis
        komutu isleyip yanit yazana kadar gecen surede ayni komut
        yeniden okunur ve iki kez uygulanir (canta iki kez baglanir).
        """
        if not self.etkin():
            return []
        yol = komut_dosyasi(self.dizin, self.servis)
        if not os.path.exists(yol):
            return []
        kuyruk = _oku_liste(yol)
        if kuyruk:
            _atomik_yaz(yol, [])
        return [k for k in kuyruk if isinstance(k, dict)]

    def yanit(self, komut_id, tamam, hata="", veri=None):
        """Komutun sonucunu panele bildirir."""
        if not self.etkin():
            return False
        kayit = {"id": str(komut_id), "tamam": bool(tamam),
                 "hata": str(hata or ""), "ts": time.time()}
        if isinstance(veri, dict):
            kayit["veri"] = veri
        self._yanitlar.append(kayit)
        if len(self._yanitlar) > YANIT_SINIR:
            self._yanitlar = self._yanitlar[-YANIT_SINIR:]
        return _atomik_yaz(yanit_dosyasi(self.dizin, self.servis),
                           self._yanitlar)
