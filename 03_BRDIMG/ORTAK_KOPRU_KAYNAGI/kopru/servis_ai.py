# -*- coding: utf-8 -*-
"""KOPRU YAZILIMI - AI SERVISI.

## KULLANICI ISTEGI (birebir)

    "hem ai icin hem kameralar icin ayni kopru gruplamasi gerekiyor"

    "Birde AI bilgisayarlar bolumunde bilgisayarin ip'si gibi ayni
     zamanda SSH kullanici bilgilerini de isteyelim"

## GOREVI

Saha agindaki AI bilgisayarlarina (goruntu isleme iscilerine) HTTP ile
baglanir: sagliklarini yoklar, izleme gorevi atar, tespit kutularini
toplar ve merkeze YALNIZ ozet bildirir.

## NEDEN MERKEZDE DEGIL KOPRUDE

AI bilgisayarlari saha agindadir (ornegin 192.168.1.100). Merkez sunucu
bir veri merkezindedir ve bu ozel ag adresine ULASAMAZ.

Onceki surumde `ai_izleme_baslat` komutu MERKEZDE kosuyor ve merkezden
`http://{host}:{port}/izle` istegi atiliyordu. Bu istek saha adresine
gittigi icin her zaman zaman asimina dusuyordu. Ayni yol saglik
yoklamasi icin de kullanildigindan, calisan bir AI bilgisayari merkezde
SUREKLI "yanit vermiyor" gorunuyordu.

Ustelik iki nokta birden kopuyordu: iscye verilen akis adresi de
merkezin kendi video vekilini (`gcs_proxy`) gosteriyordu; isci o adrese
de erisemezdi. Artik hem istek hem akis adresi saha agi icinde kalir.

## ONCEKI SURUMUN IKI EKSIGI (v1.4.4 ve oncesi)

Bu servis onceden yalniz bir "canlilik" gostergesiydi:

1. **Isciye hic baglanmiyordu.** Yalnizca yerel GPU/CPU tespiti yapip
   30 saniyede bir "0 etkin izleme gorevi" yaziyordu.
2. **Komut kanalina bagli degildi.** Panelden gelen izleme istegi bu
   servise HIC ulasmiyordu.

## GPU ZORUNLU DEGILDIR

Bu servis kendisi cikarim YAPMAZ; cikarimi AI bilgisayarlari yapar. Yerel
hizlandirici bilgisi yalnizca RAPORLAMA icindir (operator hangi
makinenin ne yetenekte oldugunu gorur). Bu yuzden GPU yoklugu servisi
engellemez.

## MERKEZE NE GONDERILIR

`durum_yaz` her dongude su alanlari yazar:

  * `ai_sunucular` : yoklanan iscilerin cevrimici/yuk/kapasite durumu
  * `ai_gorevler`  : kamera -> isci atamalari
  * `ai_hazir`     : en az bir cevrimici isci var mi
  * `hizlandirici` : bu makinenin yerel hesaplama birimi

Tespit kutulari merkeze DEGIL, ayni makinedeki video servisine gider
(`anotasyon` eylemi): kutular karenin uzerine sahada cizilir, boylece
merkeze ek yuk binmez.
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request

from .servis_kanal import ServisKanali, komut_yaz
from .servis_temel import Servis, calistir
from .video_vekil import VIDEO_PROXY_PORT

DONGU_SN = 0.2              # komut yoklama araligi
YOKLAMA_ARALIGI_SN = 5.0    # isci saglik yoklamasi araligi
DURUM_YAZIM_SN = 2.0        # merkeze durum yazim araligi
KONSOL_BILDIRIM_SN = 30.0   # konsola ozet yazim araligi
HTTP_ZAMANASIMI = 6.0
YOKLAMA_ZAMANASIMI = 4.0


class AiServisi(Servis):
    ad = "ai"
    baslik = "AI Servisi"

    # -----------------------------------------------------------------
    def hazirla(self):
        self.kanal = ServisKanali()
        self.kilit = threading.Lock()
        self.sunucular = {}     # sid -> kayit (merkezden gelir)
        self.saglik = {}        # sid -> {cevrimici, son_durum, ts}
        self.gorevler = {}      # kamera_id -> sid
        self.gorev_bilgi = {}   # kamera_id -> {url, protokol, gorevler}

        self.hizlandirici = self._hizlandirici_bul()
        self.yaz("Yerel hesaplama birimi: %s" % self.hizlandirici,
                 "basari" if self.hizlandirici != "CPU" else "bilgi")

        self._son_yoklama = 0.0
        self._son_durum = 0.0
        self._son_konsol = 0.0

    def _hizlandirici_bul(self):
        """Kullanilabilir hizlandiriciyi tespit eder.

        Ice aktarim hatalari SESSIZCE yutulur: paketlerin bulunmamasi
        normal durumdur, hata degildir. Yigin izi basmak kullaniciyi
        gereksiz endiselendirir.
        """
        try:
            import torch
            if torch.cuda.is_available():
                return "CUDA (%s)" % torch.cuda.get_device_name(0)
        except Exception:
            pass
        try:
            import onnxruntime as ort
            saglayici = ort.get_available_providers()
            for p in ("CUDAExecutionProvider", "DmlExecutionProvider",
                      "OpenVINOExecutionProvider"):
                if p in saglayici:
                    return p.replace("ExecutionProvider", "")
        except Exception:
            pass
        return "CPU"

    # -----------------------------------------------------------------
    def _yerel_akis_adresi(self, kamera_id):
        """AI iscisinin cekecegi akis adresini bu makineye gore uretir.

        Isci ayni makinede degil, ayni YEREL AGDA olabilir; bu yuzden
        `127.0.0.1` yeterli DEGILDIR. Iscinin bu makineye ulasabilecegi
        adres kullanilir: `GOKTUNGU_KOPRU_YEREL_IP` verilmisse o, yoksa
        disa acilan arayuzun adresi, hicbiri bulunamazsa `127.0.0.1`.
        """
        adres = (os.environ.get("GOKTUNGU_KOPRU_YEREL_IP") or "").strip()
        if not adres:
            adres = self._dis_arayuz_ip()
        return "http://%s:%s/kamera/%s" % (adres, VIDEO_PROXY_PORT,
                                           int(kamera_id))

    @staticmethod
    def _dis_arayuz_ip():
        """Yerel agda gorunen arayuz adresini bulur.

        UDP yuvasi baglanir ama VERI GONDERILMEZ; cekirdek yalnizca
        yonlendirme tablosuna bakip hangi arayuzun kullanilacagini
        soyler. Ag erisimi olmasa da hata vermez, o durumda geri donus
        adresi kullanilir.
        """
        import socket
        yuva = None
        try:
            yuva = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            yuva.settimeout(0.4)
            yuva.connect(("192.0.2.1", 9))   # TEST-NET-1: yonlendirilmez
            return yuva.getsockname()[0] or "127.0.0.1"
        except Exception:
            return "127.0.0.1"
        finally:
            if yuva is not None:
                try:
                    yuva.close()
                except Exception:
                    pass

    # -----------------------------------------------------------------
    # Isci HTTP yardimcilari
    # -----------------------------------------------------------------
    def _http(self, kayit, yol, veri=None, zamanasimi=HTTP_ZAMANASIMI):
        """AI iscisine HTTP istegi (merkezden TASINDI).

        Merkezdeki `ai_yonetici._http` ile ayni sozlesmeyi konusur;
        degisen tek sey bu kodun KOSTUGU makinedir. Saha adresine ancak
        buradan erisilebilir.
        """
        url = "http://%s:%s%s" % (kayit.get("host"), kayit.get("port"),
                                  yol)
        if veri is None:
            istek = urllib.request.Request(url)
        else:
            istek = urllib.request.Request(
                url, data=json.dumps(veri).encode(),
                headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(istek, timeout=zamanasimi) as c:
            return json.loads(c.read() or b"{}")

    def _en_az_yuklu(self, haric=None):
        """Cevrimici, kapasitesi dolu olmayan en az yuklu isci kaydi."""
        aday, aday_yuk = None, 10 ** 9
        with self.kilit:
            kayitlar = list(self.sunucular.values())
            saglik = dict(self.saglik)
        for kayit in kayitlar:
            sid = kayit.get("id")
            if haric and sid == haric:
                continue
            s = saglik.get(sid) or {}
            if not s.get("cevrimici"):
                continue
            durum = s.get("son_durum") or {}
            yuk = durum.get("yuk", 0)
            kapasite = durum.get("kapasite", kayit.get("kapasite", 1))
            try:
                if float(yuk) >= float(kapasite):
                    continue
            except (TypeError, ValueError):
                pass
            if yuk < aday_yuk:
                aday, aday_yuk = kayit, yuk
        return aday

    # -----------------------------------------------------------------
    # Ana dongu
    # -----------------------------------------------------------------
    def dongu(self):
        self.yaz("AI servisi hazir. Isciler BU agdan yoklanir; "
                 "sunucu tanimlari merkezden gelir.", "basari")
        while not self.durdur_istendi():
            self._komutlari_isle()
            self._yoklama()
            self._merkeze_yaz()
            self._konsol_ozet()
            self.bekle(DONGU_SN)

    def _komutlari_isle(self):
        if not self.kanal.etkin():
            return
        for k in self.kanal.oku():
            kid = k.get("id")
            eylem = str(k.get("eylem") or "")
            veri = k.get("veri") if isinstance(k.get("veri"), dict) else {}
            try:
                sonuc = self._komut_uygula(eylem, veri)
                self.kanal.yanit(kid, True, "", sonuc)
            except Exception as e:
                self.yaz("Komut hatasi (%s): %s" % (eylem, e), "hata")
                self.kanal.yanit(kid, False, str(e))

    def _komut_uygula(self, eylem, veri):
        # --- isci kayitlari -------------------------------------------
        if eylem == "sunucu_yaz":
            kayit = veri.get("sunucu") if isinstance(
                veri.get("sunucu"), dict) else veri
            k = self._kayit_normalize(kayit)
            if not k:
                raise ValueError("gecersiz AI sunucu kaydi")
            with self.kilit:
                self.sunucular[k["id"]] = k
            self.yaz("AI sunucu kaydi: #%s %s (%s:%s)"
                     % (k["id"], k["ad"] or "-", k["host"], k["port"]))
            # Yeni kayit hemen yoklanir; aksi halde panel 5 saniye
            # boyunca "bilinmiyor" gosterir ve kullanici kaydin
            # islenmedigini sanar.
            self._yokla_tek(k)
            return {"sunucu": k}

        if eylem == "sunucu_sil":
            sid = veri.get("id")
            try:
                sid = int(sid)
            except (TypeError, ValueError):
                raise ValueError("sunucu id gerekli")
            with self.kilit:
                var = self.sunucular.pop(sid, None) is not None
                self.saglik.pop(sid, None)
                tasinacak = [k for k, s in self.gorevler.items()
                             if s == sid]
            # Dusen iscinin gorevleri BASKA isciye tasinir; aksi halde
            # kamera sessizce izlemesiz kalir ve operator bunu bilmez.
            for kamera_id in tasinacak:
                self._gorev_yeniden_ata(kamera_id, dusen=sid)
            return {"silindi": bool(var)}

        if eylem == "sunucular":
            return {"ai_sunucular": self._sunucu_ozet()}

        # --- izleme gorevleri -----------------------------------------
        if eylem == "izleme_baslat":
            kamera_id = veri.get("kamera_id")
            if kamera_id is None:
                raise ValueError("kamera_id gerekli")
            kamera_id = int(kamera_id)
            gorevler = str(veri.get("gorevler") or "")
            # AKIS ADRESI BURADA URETILIR, merkezden GELMEZ.
            #
            # Merkez kipinde merkezin uretecegi adres kendi 8801
            # vekilini gosterir; saha iscisi o adrese erisemez. Bu
            # yuzden merkez yalniz kamera kimligini ve gorev listesini
            # gonderir. Adresi bu makine kendi yerel vekiline gore
            # uretir; boylece hem istek hem goruntu saha aginda kalir.
            #
            # Merkez yine de bir adres gonderirse (lokal kurulumda GCS
            # ile kopru ayni makinede olabilir) o adres kullanilir.
            url = str(veri.get("url") or "").strip()
            protokol = str(veri.get("protokol") or "")
            kamera = veri.get("kamera") or None
            if not url:
                url = self._yerel_akis_adresi(kamera_id)
                protokol = protokol or "gcs_proxy"
                # Isci bu makinenin vekilinden cekecek; vekilin kare
                # uretmesi icin akisin ACIK olmasi gerekir.
                self._akis_actir(kamera_id, kamera)
            return self._gorev_ata(kamera_id, url, protokol,
                                   gorevler=gorevler, kamera=kamera)

        if eylem == "izleme_durdur":
            kamera_id = veri.get("kamera_id")
            if kamera_id is None:
                raise ValueError("kamera_id gerekli")
            return self._izleme_durdur(int(kamera_id))

        if eylem == "izleme_listesi":
            return {"ai_gorevler": self._gorev_ozet()}

        if eylem == "durum":
            return self._durum_paketi()

        raise ValueError("bilinmeyen eylem: %s" % eylem)

    def _kayit_normalize(self, kayit):
        if not isinstance(kayit, dict):
            return None
        try:
            sid = int(kayit.get("id"))
        except (TypeError, ValueError):
            return None
        try:
            port = int(kayit.get("port") or 8900)
        except (TypeError, ValueError):
            port = 8900
        try:
            kapasite = int(kayit.get("kapasite") or 1)
        except (TypeError, ValueError):
            kapasite = 1
        return {"id": sid,
                "ad": str(kayit.get("ad") or ""),
                "host": str(kayit.get("host") or ""),
                "port": port,
                "kapasite": kapasite}

    # -----------------------------------------------------------------
    # Gorev atama
    # -----------------------------------------------------------------
    def _gorev_ata(self, kamera_id, url, protokol, haric=None,
                   gorevler="", kamera=None):
        kayit = self._en_az_yuklu(haric=haric)
        if not kayit:
            # Gerekce NET olmali: "cevrimici isci yok" ile "isci dolu"
            # farkli sorunlardir ve farkli mudahale gerektirir.
            with self.kilit:
                toplam = len(self.sunucular)
                cevrimici = sum(1 for s in self.saglik.values()
                                if s.get("cevrimici"))
            if toplam == 0:
                hata = "Tanimli AI sunucusu yok"
            elif cevrimici == 0:
                hata = ("Hicbir AI sunucusu cevrimici degil "
                        "(%d tanimli)" % toplam)
            else:
                hata = ("Cevrimici AI sunucularinin kapasitesi dolu "
                        "(%d/%d)" % (cevrimici, toplam))
            self.yaz("Kamera %d izlemesi atanamadi: %s"
                     % (kamera_id, hata), "uyari")
            return {"tamam": False, "hata": hata}
        try:
            sonuc = self._http(kayit, "/izle",
                               {"kamera_id": kamera_id, "url": url,
                                "protokol": protokol,
                                "gorevler": gorevler or ""})
        except Exception as e:
            self.yaz("Kamera %d izlemesi %s sunucusuna atanamadi: %s"
                     % (kamera_id, kayit.get("ad") or kayit.get("host"),
                        e), "hata")
            return {"tamam": False,
                    "hata": "%s: %s" % (kayit.get("ad") or
                                        kayit.get("host"), e)}
        if sonuc.get("tamam"):
            with self.kilit:
                self.gorevler[int(kamera_id)] = kayit["id"]
                self.gorev_bilgi[int(kamera_id)] = {
                    "url": url, "protokol": protokol,
                    "gorevler": gorevler or "",
                    "kamera": dict(kamera) if kamera else None}
            self.yaz("Kamera %d izlemesi %s sunucusuna atandi"
                     % (kamera_id, kayit.get("ad") or kayit.get("host")),
                     "basari")
        return sonuc

    def _gorev_yeniden_ata(self, kamera_id, dusen=None):
        with self.kilit:
            bilgi = dict(self.gorev_bilgi.get(int(kamera_id)) or {})
            self.gorevler.pop(int(kamera_id), None)
        if not bilgi.get("url"):
            return
        self._gorev_ata(int(kamera_id), bilgi["url"],
                        bilgi.get("protokol", ""), haric=dusen,
                        gorevler=bilgi.get("gorevler", ""),
                        kamera=bilgi.get("kamera"))

    def _akis_actir(self, kamera_id, kamera=None):
        """Video servisine kamerayi acmasini bildirir.

        ## NEDEN GEREKLI

        Isci goruntuyu bu makinenin `/kamera/<id>` adresinden ceker,
        ancak o adres YALNIZCA akis acikken kare uretir. Akis acilmazsa
        gorev basariyla atanmis gorunur, panelde 'atandi' yazar, ama
        isciye tek kare gitmez. Bu, en tehlikeli basarisizlik bicimidir:
        operator AI'nin izledigini sanir.

        Kamera kaydi da birlikte gonderilir; video servisi kamerayi
        kendi defterinde bulamazsa akisi acamaz.
        """
        dizin = self.kanal.dizin or os.environ.get(
            "GOKTUNGU_KOPRU_KANAL_DIZIN") or ""
        if not dizin:
            return
        try:
            if kamera:
                komut_yaz(dizin, "video", "kamera_yaz",
                          {"kamera": dict(kamera)})
            komut_yaz(dizin, "video", "akis_baslat",
                      {"id": int(kamera_id)})
        except Exception as e:                          # noqa: BLE001
            self.yaz("Kamera %s akisi video servisinde acilamadi: %s"
                     % (kamera_id, e), "uyari")

    def _izleme_durdur(self, kamera_id):
        with self.kilit:
            sid = self.gorevler.pop(int(kamera_id), None)
            self.gorev_bilgi.pop(int(kamera_id), None)
            kayit = dict(self.sunucular.get(sid) or {}) if sid else None
        if kayit:
            try:
                self._http(kayit, "/durdur", {"kamera_id": int(kamera_id)})
            except Exception as e:
                # Isci ulasilamiyorsa gorev YINE de birakilir: aksi halde
                # panelde silinemeyen bir izleme kaydi kalir.
                self.yaz("Kamera %s izlemesi durdurulurken isciye "
                         "ulasilamadi: %s" % (kamera_id, e), "uyari")
        # Kutular donuk kalmamali: video servisine bos kutu gonderilir.
        self._anotasyon_temizle(int(kamera_id))
        self.yaz("Kamera %s izlemesi durduruldu" % kamera_id)
        return {"tamam": True}

    def _anotasyon_temizle(self, kamera_id):
        """Video servisine bos kutu listesi gonderir.

        Tespit kutulari merkeze DEGIL ayni makinedeki video servisine
        gider. Izleme durdurulunca kutular temizlenmezse son kareye ait
        cerceveler ekranda donuk kalir ve operator olmayan bir hedefi
        gorur.

        ## KANAL DIZINI NEDEN ELLE COZULUR

        `komut_yaz(dizin, ...)` dizini ortam degiskeninden OKUMAZ; yolu
        dogrudan `os.path.join` ile kurar. `None` gecilirse TypeError
        atar. `ServisKanali` ise ayni degiskeni kendi icinde cozer; bu
        yuzden dizin oradan alinir. Kanal kurulu degilse (servis elle
        calistirilmis olabilir) sessizce vazgecilir.
        """
        dizin = self.kanal.dizin or os.environ.get(
            "GOKTUNGU_KOPRU_KANAL_DIZIN") or ""
        if not dizin:
            return
        try:
            komut_yaz(dizin, "video", "anotasyon",
                      {"id": int(kamera_id), "kutular": []})
        except Exception:
            pass

    # -----------------------------------------------------------------
    # Saglik yoklamasi
    # -----------------------------------------------------------------
    def _yoklama(self):
        simdi = time.time()
        if simdi - self._son_yoklama < YOKLAMA_ARALIGI_SN:
            return
        self._son_yoklama = simdi
        with self.kilit:
            kayitlar = list(self.sunucular.values())
        for kayit in kayitlar:
            self._yokla_tek(kayit)

    def _yokla_tek(self, kayit):
        sid = kayit.get("id")
        with self.kilit:
            onceki = (self.saglik.get(sid) or {}).get("cevrimici")
        try:
            durum = self._http(kayit, "/durum",
                               zamanasimi=YOKLAMA_ZAMANASIMI)
            with self.kilit:
                self.saglik[sid] = {"cevrimici": True,
                                    "son_durum": durum,
                                    "son_yoklama_ts": time.time(),
                                    "hata": ""}
            if onceki is False:
                self.yaz("AI sunucusu tekrar cevrimici: %s"
                         % (kayit.get("ad") or kayit.get("host")),
                         "basari")
        except Exception as e:
            with self.kilit:
                self.saglik[sid] = {"cevrimici": False,
                                    "son_durum": {},
                                    "son_yoklama_ts": time.time(),
                                    "hata": str(e)[:200]}
                dusen_gorevler = [k for k, s in self.gorevler.items()
                                  if s == sid]
            if onceki is True:
                self.yaz("AI sunucusu yanit vermiyor: %s (%s)"
                         % (kayit.get("ad") or kayit.get("host"), e),
                         "uyari")
                # Dusen iscinin gorevleri baska isciye tasinir.
                for kamera_id in dusen_gorevler:
                    self._gorev_yeniden_ata(kamera_id, dusen=sid)

    # -----------------------------------------------------------------
    # Merkeze bildirim
    # -----------------------------------------------------------------
    def _sunucu_ozet(self):
        with self.kilit:
            kayitlar = list(self.sunucular.values())
            saglik = dict(self.saglik)
            gorevler = dict(self.gorevler)
        ozet = []
        for k in kayitlar:
            sid = k.get("id")
            s = saglik.get(sid) or {}
            d = s.get("son_durum") or {}
            ozet.append({
                "id": sid,
                "ad": k.get("ad", ""),
                "host": k.get("host", ""),
                "port": k.get("port", 0),
                "cevrimici": bool(s.get("cevrimici")),
                "hata": s.get("hata", ""),
                "yuk": d.get("yuk", 0),
                "kapasite": d.get("kapasite", k.get("kapasite", 1)),
                "hizlandirici": d.get("hizlandirici", ""),
                "gorev_sayisi": sum(1 for v in gorevler.values()
                                    if v == sid),
                "son_yoklama_ts": s.get("son_yoklama_ts", 0),
            })
        return ozet

    def _gorev_ozet(self):
        with self.kilit:
            gorevler = dict(self.gorevler)
            bilgi = {k: dict(v) for k, v in self.gorev_bilgi.items()}
            saglik = dict(self.saglik)
        # Iscinin /durum yanitindaki akis canli/hata bilgisi izleme
        # kaydina islenir; arayuzde "atandi ama akis yok" durumu
        # gorunur olmalidir.
        akis_durum = {}
        for sid, s in saglik.items():
            for a in ((s.get("son_durum") or {}).get("akislar") or []):
                try:
                    akis_durum[int(a.get("kamera_id"))] = a
                except (TypeError, ValueError):
                    continue
        sonuc = []
        for kamera_id, sid in gorevler.items():
            b = bilgi.get(kamera_id) or {}
            sonuc.append({
                "kamera_id": int(kamera_id),
                "sunucu_id": sid,
                "protokol": b.get("protokol", ""),
                "gorevler": b.get("gorevler", ""),
                "akis": akis_durum.get(int(kamera_id)) or {},
            })
        return sonuc

    def _durum_paketi(self):
        ozet = self._sunucu_ozet()
        return {
            "ai_sunucular": ozet,
            "ai_gorevler": self._gorev_ozet(),
            "ai_hazir": any(s["cevrimici"] for s in ozet),
            "ai_sunucu_sayisi": len(ozet),
            "ai_cevrimici": sum(1 for s in ozet if s["cevrimici"]),
            "hizlandirici": self.hizlandirici,
        }

    def _merkeze_yaz(self):
        simdi = time.time()
        if simdi - self._son_durum < DURUM_YAZIM_SN:
            return
        self._son_durum = simdi
        self.durum_yaz(**self._durum_paketi())

    def _konsol_ozet(self):
        simdi = time.time()
        if simdi - self._son_konsol < KONSOL_BILDIRIM_SN:
            return
        self._son_konsol = simdi
        p = self._durum_paketi()
        self.yaz("Durum: %d/%d isci cevrimici, %d etkin izleme gorevi, "
                 "yerel birim %s"
                 % (p["ai_cevrimici"], p["ai_sunucu_sayisi"],
                    len(p["ai_gorevler"]), self.hizlandirici))

    # -----------------------------------------------------------------
    def kapat(self):
        with self.kilit:
            kameralar = list(self.gorevler.keys())
        for kamera_id in kameralar:
            try:
                self._izleme_durdur(kamera_id)
            except Exception:
                pass
        # Servis durdugunda merkez isciyi "cevrimici" gormeye devam
        # etmemeli; aksi halde operator var olmayan bir izlemeye guvenir.
        try:
            self.durum_yaz(ai_sunucular=[], ai_gorevler=[],
                           ai_hazir=False, ai_cevrimici=0,
                           ai_sunucu_sayisi=0)
        except Exception:
            pass
        self.yaz("Izleme gorevleri kapatildi")


if __name__ == "__main__":
    calistir(AiServisi)
