# -*- coding: utf-8 -*-
"""KOPRU YAZILIMI — uygulama cekirdegi.

Panel, servis yoneticisi ve merkez ajanini tek bir nesnede birlestirir.
Boylece panel istekleri servislere ve ajana ERISEBILIR, ama modullerin
birbirini ice aktarmasi GEREKMEZ (dairesel ice aktarma olmaz).

Ajan ile servisler arasindaki bag onemlidir: merkez `servis_durum`
sordugunda yanit GERCEK surec durumundan uretilir. Uydurma "calisiyor"
yaniti, merkez panelinde saha durumunu YANLIS gosterir ve operatoru
yanlis yonlendirir.
"""
import os
import threading
import time

from . import ai_ssh as ai_ssh_mod
from . import ajan as ajan_mod
from . import akis as akis_mod
from . import ayar as ayar_mod
from . import merkez as merkez_mod
from . import guncelleme as guncelleme_mod
from . import servisler as servis_mod


class Uygulama:
    def __init__(self, gunluk=None):
        self._gunluk = gunluk
        self.gunluk_dizin = os.path.join(ayar_mod.veri_dizini(), "gunluk")
        self.servisler = servis_mod.ServisYoneticisi(self.gunluk_dizin)
        from .panel import Oturumlar
        self.oturumlar = Oturumlar()
        self.ajan = None
        self._ajan_kilit = threading.Lock()
        self.baslama_ts = time.time()
        # Guncelleme denetimi ayri is parcaciginda calisir; panel, ajan ve
        # telemetri akisini bekletmez. Indirme/kurulum ancak oturumlu
        # kullanicinin acik istegiyle baslatilabilir.
        self.guncelleme = guncelleme_mod.GuncellemeYoneticisi(
            "kopru", ayar_mod.SURUM, ayar_mod.veri_dizini(),
            gunluk=lambda etiket, metin, seviye="bilgi": self._gunluk_yaz_guncelleme(etiket, metin, seviye))
        # AKIS KANALLARI — ham MAVLink byte tasima.
        #
        # Kanallar PANEL SURECINDE tutulur, dron servisi alt surecinde
        # DEGIL. Nedeni olculdu: `servisler.baslat()` alt sureci
        # `stdin=DEVNULL` ile acar, yani panel calisan servise komut
        # GONDEREMEZ. Merkezden gelen bir MAVLink komutu (arm, mod
        # degistir) milisaniyeler icinde donanima basilmalidir; dosya
        # tabanli posta kutusu bu zamanlama icin uygun degildir.
        #
        # Ajan da bu surecte yasadigi icin komut yolu tek bir bellek ici
        # cagriya iner: ajan._mesaj_isle -> kanallar.yaz(kanal_id, byte).
        #
        # KURAL: kanal ancak dron servisi calisirken acilabilir; dron
        # servisi durdurulunca tum kanallar kapatilir. Boylece panelde
        # gorunen "Dron Sunucusu: calisiyor/durdu" gostergesi gercegi
        # soylemeye devam eder.
        self.kanallar = akis_mod.KanalYoneticisi(
            self._akis_gonder,
            gunluk=lambda m, s="bilgi": self.gunluk(m, s))
        # AI BILGISAYARI SSH OTURUMLARI
        #
        # Kullanicinin AI bilgisayarlari ozel agdadir (192.168.1.x).
        # Merkez sunucusu bu adrese ERISEMEZ; SSH oturumu AI
        # bilgisayariyla ayni agda olan BU makinede acilmalidir.
        # Merkez yalniz basla/durdur/gecmis der.
        self.ai_ssh = ai_ssh_mod.AISSHYonetici(
            gunluk=lambda m, s="bilgi": self.gunluk(m, s))
        # Kurum logosu onbelegi (merkezden bir kez cekilir)
        self._logo_kilit = threading.Lock()
        self._logo_adres = ""
        self._logo_ham = None
        self._logo_tur = None
        # RADAR AKTARICISI (v1.5.0)
        #
        # Radar servisi AYRI SURECTE kosar; ajan ise BU surecte yasar.
        # Alt surecin merkeze dogrudan soketi yoktur. Bu yuzden izler,
        # servisin yazdigi durum dosyasindan okunup ajan uzerinden
        # merkeze akitilir. Ayni desen dron servisinin kanal sayiminda
        # da kullanilir (`servis_durumu_zengin`).
        #
        # Neden ayri bir is parcacigi: panel istekleri (HTTP) duzensiz
        # gelir, radar izi ise SUREKLI akmalidir. Aktarim panel
        # isteklerine baglanirsa, kimse panele bakmadigi surece merkez
        # hicbir iz gormez.

    # -----------------------------------------------------------------
    def _gunluk_yaz_guncelleme(self, etiket, metin, seviye="bilgi"):
        self.gunluk("%s: %s" % (etiket, metin), seviye)

    def gunluk(self, metin, seviye="bilgi"):
        if self._gunluk:
            try:
                self._gunluk("KOPRU", metin, seviye)
                return
            except Exception:
                pass
        print("[KOPRU] %s" % metin, flush=True)

    # -----------------------------------------------------------------
    # Ayar
    # -----------------------------------------------------------------
    def ayar_maskeli(self):
        a = ayar_mod.ayar_oku()
        return {
            "merkez_adres": a.get("merkez_adres"),
            "merkez_http": a.get("merkez_http"),
            "panel_port": a.get("panel_port"),
            "panel_arayuz": a.get("panel_arayuz"),
            "sertifika_dogrulama": bool(a.get("sertifika_dogrulama")),
            "acilista_baslat": a.get("acilista_baslat") or {},
            "veri_dizini": ayar_mod.veri_dizini(),
            "gunluk_dizin": self.gunluk_dizin,
            # v1.5.6 — merkez sunucu secimi (Merkez Uygulama lisansi)
            "merkez_secim_yapildi": bool(a.get("merkez_secim_yapildi")),
            "merkez_kendi": bool(a.get("merkez_kendi")),
            "merkez_varsayilan": ayar_mod.VARSAYILAN_MERKEZ,
            "merkez_varsayilan_http": ayar_mod.VARSAYILAN_MERKEZ_HTTP,
        }

    def ayar_kaydet(self, g):
        """Panelden gelen ayarlari dogrular ve kaydeder.

        Port ve arayuz DEGISIKLIGI aninda uygulanmaz: calisan bir HTTP
        sunucusunun portunu degistirmek, kullanicinin acik sekmesini
        kopartir ve panele erisimini kaybettirir. Yeniden baslatmada
        etkinlesir; panel bunu kullaniciya yazar.
        """
        yeni = {}
        if "merkez_adres" in g:
            d = str(g.get("merkez_adres") or "").strip()
            if d and not (d.startswith("ws://") or d.startswith("wss://")):
                return {"hata": "Merkez adresi ws:// veya wss:// olmali"}
            yeni["merkez_adres"] = d or ayar_mod.VARSAYILAN_MERKEZ
        if "merkez_http" in g:
            d = str(g.get("merkez_http") or "").strip()
            if d and not (d.startswith("http://")
                          or d.startswith("https://")):
                return {"hata": "Merkez HTTP adresi http(s):// olmali"}
            yeni["merkez_http"] = d
        if "panel_port" in g:
            try:
                p = int(g.get("panel_port"))
            except Exception:
                return {"hata": "Port sayi olmali"}
            if not (1024 <= p <= 65535):
                return {"hata": "Port 1024-65535 araliginda olmali"}
            yeni["panel_port"] = p
        if "panel_arayuz" in g:
            # Bos birakilirsa varsayilana (aga acik) doner; panelde alani
            # temizleyen kullanici "her yerden erisilebilir" bekler.
            d = (str(g.get("panel_arayuz") or "").strip()
                 or ayar_mod.AYAR_VARSAYILAN["panel_arayuz"])
            yeni["panel_arayuz"] = d
        if "sertifika_dogrulama" in g:
            yeni["sertifika_dogrulama"] = bool(g.get("sertifika_dogrulama"))
        if "acilista_baslat" in g and isinstance(g["acilista_baslat"], dict):
            yeni["acilista_baslat"] = {
                a: bool(g["acilista_baslat"].get(a))
                for a in servis_mod.SERVIS_ADLARI}
        ayar_mod.ayar_guncelle(**yeni)
        return self.ayar_maskeli()

    # -----------------------------------------------------------------
    def merkez_secimi_kaydet(self, kendi, adres=None, http_adres=None):
        """Merkez sunucu secimini isler (Faz 8 — kullanici istegi).

        `kendi=False` -> GOKTUNGU bulutu. Adres varsayilana DONDURULUR:
        kullanici onceki kurulumda kendi sunucusunu yazip sonra buluta
        donmek istediginde, eski adres ayar dosyasinda kalirsa secim
        hicbir sey degistirmemis gorunurdu.

        `kendi=True` -> sirketin kendi Merkez Uygulamasi. Adres
        dogrulamasi `ayar_kaydet` ile AYNI yoldan gecer; ikinci bir
        dogrulama yolu acilsa kurallar zamanla ayrisirdi.

        Ayni bilgisayarda merkez + kopru birlikte calisabilir; bu durumda
        adres `wss://127.0.0.1:9443/kopru` gibi yerel bir adrestir.
        """
        kendi = bool(kendi)
        if kendi:
            d = str(adres or "").strip()
            if not d:
                return {"hata": "Kendi merkez sunucunuzun adresini girin"}
            g = {"merkez_adres": d}
            h = str(http_adres or "").strip()
            if h:
                g["merkez_http"] = h
            sonuc = self.ayar_kaydet(g)
            if isinstance(sonuc, dict) and sonuc.get("hata"):
                return sonuc
        else:
            self.ayar_kaydet({
                "merkez_adres": ayar_mod.VARSAYILAN_MERKEZ,
                "merkez_http": ayar_mod.VARSAYILAN_MERKEZ_HTTP,
            })
        ayar_mod.ayar_guncelle(merkez_secim_yapildi=True,
                               merkez_secim_ts=int(time.time()),
                               merkez_kendi=kendi)
        # Adres degisti: ajan YENIDEN kurulmali. Aksi halde kopru,
        # secim yapilmis olmasina ragmen ESKI merkeze bagli kalir ve
        # kullanici "kendi sunucumu sectim ama veri gelmiyor" der.
        try:
            self.kimlik_yenile()
        except Exception as e:
            self.gunluk("Merkez secimi sonrasi ajan yenilenemedi: %s" % e,
                        "uyari")
        return self.ayar_maskeli()

    # -----------------------------------------------------------------
    # Ajan
    # -----------------------------------------------------------------
    def _ajan_kimligi(self):
        k = ayar_mod.kimlik_oku()
        a = ayar_mod.ayar_oku()
        return {
            "kurulum_uid": k.get("kurulum_uid"),
            "gizli": k.get("gizli"),
            "ornek_id": k.get("ornek_id"),
            "ad": k.get("ad"),
            "merkez_adres": a.get("merkez_adres"),
            "sertifika_dogrulama": a.get("sertifika_dogrulama"),
            "surum": ayar_mod.SURUM,
            "platform": ayar_mod.platform_adi(),
            "makine_adi": ayar_mod.makine_adi(),
        }

    def _ajan_islevleri(self):
        """Merkezin sorabilecegi eylemler.

        Her yanit GERCEK durumdan uretilir. `dron_liste` gibi eylemler,
        dron servisi calismiyorsa BOS liste yerine acik bir aciklama
        dondurur: bos liste "dron yok" anlamina gelir ve operatoru
        yanlis yonlendirir; "servis kapali" ise cozumu soyler.
        """
        def sistem_bilgi(_v):
            return {
                "surum": ayar_mod.SURUM,
                "platform": ayar_mod.platform_adi(),
                "makine_adi": ayar_mod.makine_adi(),
                "urun": "kopru",
                "calisma_sn": int(time.time() - self.baslama_ts),
                "panel_port": ayar_mod.ayar_oku().get("panel_port"),
            }

        def servis_durum(_v):
            # Merkez de PANELIN gordugu ayni sayiyi gormeli; aksi halde
            # Baglanti Yoneticisi kopru basliginda "0 dron" yazarken
            # panelde 2 dron gorunur ve hangisinin dogru oldugu
            # anlasilmaz.
            return {"servisler": self.servis_durumu_zengin(),
                    "kanallar": self.kanal_durumu()}

        def yetenekler(_v):
            return {"urun": "kopru", "servis": True, "konsol": True,
                    "telemetri": True}

        def dron_sayisi(_v):
            # GERCEK sayim: acik akis kanali sayisi. Kanallar bu surecte
            # tutuldugu icin sayim dogrudan bellekten okunur; dron
            # servisinin olcum dosyasina gerek yoktur.
            #
            # Once olu kanallar duser: kaynagi kapanmis (telemetri
            # radyosu cikarilmis) bir kanal listede kalirsa merkez
            # panelinde var olmayan bir dron gorunur.
            s = self.servisler.al("dron")
            if not (s and s.calisiyor()):
                return 0
            try:
                self.kanallar.temizle_olu()
                return int(self.kanallar.etkin_sayi() or 0)
            except Exception:
                return 0

        def konsol(v):
            ad = str((v or {}).get("servis") or "")
            s = self.servisler.al(ad)
            if not s:
                return {"hata": "Bilinmeyen servis: %s" % ad}
            return {"servis": ad,
                    "satirlar": s.konsol_oku((v or {}).get("sonrasi") or 0)}

        def servis_baslat(v):
            ad = str((v or {}).get("servis") or "")
            tamam, hata = self.servisler.baslat(ad)
            return {"tamam": bool(tamam), "hata": hata or ""}

        def servis_durdur(v):
            ad = str((v or {}).get("servis") or "")
            tamam, hata = self.servisler.durdur(ad)
            if tamam and ad == "dron":
                # Dron servisi durduruldu: acik kanallar da kapanmali.
                # Aksi halde panel "durdu" gosterirken trafik akmaya
                # devam eder ve kullanici neyin acik oldugunu bilemez.
                self.kanallari_kapat("dron servisi durduruldu")
            return {"tamam": bool(tamam), "hata": hata or ""}

        def seri_portlar(v):
            """Yerel seri port envanteri.

            Merkezdeki GOKTUNGU kullanicinin COM/ttyUSB portlarini GOREMEZ;
            liste zorunlu olarak burada toplanir ve Baglanti
            Yoneticisi'ne bu yolla tasinir.
            """
            from .servis_dron import seri_portlar as _sp
            tumu = bool((v or {}).get("tumu"))
            return {"portlar": _sp(tumu=tumu)}

        def akis_ac(v):
            v = v or {}
            s = self.servisler.al("dron")
            if not (s and s.calisiyor()):
                # ACIK hata: bos yanit "baglandi" sanilmasina yol acar.
                return {"tamam": False,
                        "hata": ("Dron servisi kapali. Kopru panelinde "
                                 "Dron Sunucusu'nu baslatin.")}
            try:
                d = self.kanallar.ac(v.get("kanal_id"),
                                     v.get("tanim") or {})
            except akis_mod.AkisHatasi as e:
                return {"tamam": False, "hata": str(e)}
            except Exception as e:
                return {"tamam": False,
                        "hata": "%s: %s" % (type(e).__name__, e)}
            return {"tamam": True, "kanal": d}

        def akis_kapat(v):
            v = v or {}
            vardi = self.kanallar.kapat(v.get("kanal_id"))
            return {"tamam": True, "vardi": bool(vardi)}

        def akis_yaz(v):
            """Merkezden gelen ham byte'i donanima basar.

            Bu eylem YANIT dondurur ama merkez yaniti beklemeyebilir:
            komut yolunda 15 sn'lik bir bekleme, arm/mod komutlarini
            kullanilamaz hale getirir. Yanit yalniz tanilama icindir.
            """
            v = v or {}
            veri = akis_mod.b64_coz(v.get("veri"))
            if not veri:
                return {"yazilan": 0}
            try:
                n = self.kanallar.yaz(v.get("kanal_id"), veri)
            except akis_mod.AkisHatasi as e:
                return {"yazilan": 0, "hata": str(e)}
            return {"yazilan": int(n or 0)}

        def akis_durum(_v):
            return {"kanallar": self.kanallar.durum()}

        def ai_ssh_baslat(v):
            """AI bilgisayarina SSH ile baglanip AI iscisini baslatir.

            `kayit` merkezden GELIR (ai_sunucular satiri). Kopru bu
            tabloyu tutmaz; merkez tek dogruluk kaynagidir. Sifre
            gonderildiyse yalniz bellekte kullanilir, diske yazilmaz.
            """
            v = v or {}
            kayit = v.get("kayit") or {}
            if not kayit.get("id"):
                return {"tamam": False,
                        "hata": "AI sunucu kaydi gonderilmedi."}
            tamam, hata = self.ai_ssh.baslat(kayit,
                                             str(v.get("sifre") or ""))
            return {"tamam": bool(tamam), "hata": hata or "",
                    "durum": self.ai_ssh.gecmis(kayit.get("id"), son=0)}

        def ai_ssh_durdur(v):
            v = v or {}
            tamam, hata = self.ai_ssh.durdur(v.get("id"))
            return {"tamam": bool(tamam), "hata": hata or ""}

        def ai_ssh_gecmis(v):
            """Konsol satirlarini CEKME yoluyla dondurur.

            Kopru merkeze kendiliginden satir itmez: konsol penceresi
            kapaliyken bant genisligi harcanmamali. Merkez pencere
            acikken duzenli aralikla sorar.
            """
            v = v or {}
            son = v.get("son")
            try:
                son = int(son) if son is not None else None
            except (TypeError, ValueError):
                son = None
            return self.ai_ssh.gecmis(v.get("id"), son=son)

        def ai_ssh_durumlar(_v):
            return {"oturumlar": self.ai_ssh.durumlar()}

        # -------------------------------------------------------------
        # KUSUR-GCSDUAL-PORT (2026-08-14): GCCDUAL cantasi eylemleri
        #
        # Kullanici bildirimi: "GCS icinde kopru kurulu olan makinede
        # porta baglanmali, sanirim su an sunucu da ariyor portu, GCS
        # bilgisayarinda aslinda ttyACM0 var".
        #
        # Canta SAHA makinesine takilidir. Merkezin seri portu yoktur;
        # bu yuzden port acma/tarama/LED islemleri merkezde DEGIL burada
        # yapilir. Eylemler `gcsdual` alt surecine `servis_kanal`
        # uzerinden iner.
        # -------------------------------------------------------------
        def _gcsdual(eylem, veri=None, zaman_asimi=8.0):
            tamam, hata, cikti = self.servisler.komut_gonder(
                "gcsdual", eylem, veri or {}, zaman_asimi=zaman_asimi)
            sonuc = {"tamam": bool(tamam), "hata": hata or ""}
            if isinstance(cikti, dict):
                sonuc.update(cikti)
            return sonuc

        def gcsdual_portlar(v):
            """Saha makinesindeki seri port envanteri.

            Merkezdeki `Istasyon2.portlari_listele()` bu makinenin
            portlarini GOREMEZ; liste zorunlu olarak burada toplanir.
            """
            return _gcsdual("portlar", {"tumu": bool((v or {}).get("tumu"))})

        def gcsdual_baglan(v):
            return _gcsdual("baglan",
                            {"port": str((v or {}).get("port") or "")})

        def gcsdual_kes(_v):
            return _gcsdual("kes")

        def gcsdual_led(v):
            v = v or {}
            return _gcsdual("led", {"kanal": v.get("kanal"),
                                    "acik": bool(v.get("acik"))})

        def gcsdual_kalibre(v):
            return _gcsdual("kalibre", {"sil": bool((v or {}).get("sil"))})

        def gcsdual_durum(_v):
            """Canli canta durumu.

            Servis KAPALIYSA hata dondurulur ama bu bir cokme degildir:
            arayuz "GroundGCC Sunucusu kapali" bilgisini gosterir. Kisa
            zaman asimi kullanilir; durum sorgusu arayuzde duzenli
            arailkla yenilenir ve uzun beklemek paneli dondurur.
            """
            return _gcsdual("durum", {}, zaman_asimi=4.0)

        # -------------------------------------------------------------
        # KUSUR-RADAR-KOPRU (2026-08-14): C20 radar eylemleri
        #
        # Kullanici bildirimi: "radarda da ayni sorun var, radarin kopru
        # yazilimi calisiyor ama sistem radari sunucuda ariyor".
        #
        # Radar sahadaki YEREL agda (ornegin 192.168.8.186:5001);
        # merkez sunucu bu adrese ulasamaz ve panel "timed out" gosterir.
        # C20 oturumu `radar` alt surecinde, saha makinesinde kurulur.
        # -------------------------------------------------------------
        def _radar(eylem, veri=None, zaman_asimi=8.0):
            tamam, hata, cikti = self.servisler.komut_gonder(
                "radar", eylem, veri or {}, zaman_asimi=zaman_asimi)
            sonuc = {"tamam": bool(tamam), "hata": hata or ""}
            if isinstance(cikti, dict):
                sonuc.update(cikti)
            return sonuc

        # 1.7.19 (Faz C): COKLU RADAR — her komut `radar_id` tasir
        # (verilmezse servis 1 numarayi kullanir). Durum paketi
        # `radarlar` sozlugunu de icerir.
        def _rid(v):
            try:
                return int((v or {}).get("radar_id") or 1)
            except (TypeError, ValueError):
                return 1

        def radar_baglan(v):
            """Panelden girilen IP/port ile SAHADA baglanti kurar.

            Onceki surumde hedef adres yalniz ortam degiskeninden
            okunuyordu; panele girilen adres servise hic ulasmiyordu.
            """
            v = v or {}
            return _radar("baglan", {"ip": v.get("ip"),
                                    "port": v.get("port"),
                                    "isim": v.get("isim"),
                                    "radar_id": _rid(v)})

        def radar_kes(v):
            return _radar("kes", {"radar_id": _rid(v)})

        def radar_durum(_v):
            """Canli radar durumu + cozumlenmis izler (tum radarlar).

            Kisa zaman asimi: bu sorgu arayuzde duzenli aralikla
            yenilenir, uzun beklemek paneli dondurur.
            """
            return _radar("durum", {}, zaman_asimi=4.0)

        def radar_cihazlar(_v):
            return _radar("cihazlar", {}, zaman_asimi=4.0)

        def radar_ayar_oku(v):
            return _radar("ayar_oku", {"radar_id": _rid(v)})

        def radar_ayar_yaz(v):
            veri = dict(v or {})
            veri["radar_id"] = _rid(v)
            return _radar("ayar_yaz", veri)

        def radar_rtk(v):
            return _radar("rtk", {"radar_id": _rid(v)})

        # 1.7.21: radar yonetim paneli — secili iz listesi + JSON yapilandirma
        def radar_secim_yaz(v):
            return _radar("secim_yaz", {"radar_id": _rid(v),
                                        "izler": list((v or {}).get("izler") or [])[:64]})

        def radar_secim_oku(v):
            return _radar("secim_oku", {"radar_id": _rid(v)})

        def radar_json_oku(v):
            return _radar("json_oku", {"radar_id": _rid(v),
                                       "json_tip": (v or {}).get("json_tip") or 0})

        def radar_json_yaz(v):
            return _radar("json_yaz", {"radar_id": _rid(v),
                                       "json_tip": (v or {}).get("json_tip") or 0,
                                       "metin": str((v or {}).get("metin") or "")[:60000]})

        # -------------------------------------------------------------
        # M50 elektro-optik eylemleri: HVS DLL yalnız saha Köprüsündedir.
        # Merkezde hiçbir SDK yüklenmez. Genel bir aktarma kapısı yerine
        # burada kapalı izin listesi kullanılır; oturum parolası yanıtlara
        # hiçbir koşulda eklenmez.
        def _eid(v):
            try:
                return int((v or {}).get("eo_id") or 1)
            except (TypeError, ValueError):
                return 1

        def _m50(eylem, veri=None, zaman_asimi=8.0, kaynak=None):
            # 1.7.19 (Faz C): COKLU M50 — `eo_id` her komutla tasinir.
            veri = dict(veri or {})
            if "eo_id" not in veri:
                veri["eo_id"] = _eid(kaynak)
            tamam, hata, cikti = self.servisler.komut_gonder(
                "m50", eylem, veri, zaman_asimi=zaman_asimi)
            sonuc = {"tamam": bool(tamam), "hata": hata or ""}
            if isinstance(cikti, dict):
                sonuc.update(cikti)
            # Savunma katmanı: alt süreç veya SDK beklenmedik bir alan
            # döndürse bile bağlantı sırrı Merkezi terk edemez.
            for gizli in ("parola", "password", "pwd", "oturum", "token"):
                sonuc.pop(gizli, None)
            return sonuc

        def m50_durum(_v):
            return _m50("durum", {}, zaman_asimi=4.0)

        def m50_cihazlar(_v):
            return _m50("cihazlar", {}, zaman_asimi=4.0)

        def m50_ayar_oku(v):
            return _m50("ayar_oku", {}, kaynak=v)

        def m50_ayar_yaz(v):
            v = dict(v or {})
            # Ağ/akış tercihleri kalıcı olabilir; bağlantı sırrı olamaz.
            for gizli in ("parola", "password", "pwd", "oturum", "token"):
                v.pop(gizli, None)
            return _m50("ayar_yaz", v, kaynak=v)

        def m50_baglan(v):
            v = v or {}
            return _m50("baglan", {
                "ip": v.get("ip"), "port": v.get("port"),
                "kullanici": v.get("kullanici"), "parola": v.get("parola"),
                "zaman_asimi": v.get("zaman_asimi"),
            }, zaman_asimi=35.0, kaynak=v)

        def m50_kes(v):
            return _m50("kes", {}, kaynak=v)

        def m50_ptz(v):
            v = v or {}
            return _m50("ptz", {"yon": v.get("yon"), "hiz": v.get("hiz"),
                                "basili": bool(v.get("basili", True))}, kaynak=v)

        def m50_lens(v):
            v = v or {}
            return _m50("lens", {"eylem": v.get("eylem"), "kanal": v.get("kanal"),
                                 "basili": bool(v.get("basili", True))}, kaynak=v)

        def m50_aci_konumla(v):
            v = v or {}
            return _m50("aci_konumla", {"azimut": v.get("azimut"),
                                         "egim": v.get("egim"), "hiz": v.get("hiz")}, kaynak=v)

        def m50_takip_sec(v):
            v = v or {}
            return _m50("takip_sec", {"kanal": v.get("kanal"),
                                       "video_dikdortgen": v.get("video_dikdortgen"),
                                       "secim": v.get("secim")}, kaynak=v)

        def m50_takip_baslat(v):
            v = v or {}
            return _m50("takip_baslat", {"kanal": v.get("kanal"),
                                          "mod": v.get("mod")}, kaynak=v)

        def m50_takip_durdur(v):
            return _m50("takip_durdur", {"kanal": (v or {}).get("kanal")}, kaynak=v)

        # 1.7.19 DUZELTME: 1.7.18 SDK eylemleri serviste vardi ama ajan
        # haritasinda YOKTU; Merkez 'm50_aci_oku' gonderince kopru "bu
        # kurulum eylemi desteklemiyor" diyordu. Veri alanlari kapali
        # listeyle sinirlanir; parola/oturum hicbir eylemde tasinmaz.
        _M50_EK = {
            "aci_oku": (), "onayar_liste": (),
            "onayar_kaydet": ("no", "ad", "hiz"), "onayar_cagir": ("no",),
            "onayar_sil": ("no",), "onayar_hepsini_sil": (),
            "tarama": ("tur", "kontrol", "yol"),
            "takip_yetenek": ("kanal", "etkin"),
        }

        def _m50_ek_islev(eylem, alanlar):
            def islev(v):
                v = v or {}
                return _m50(eylem, {a: v.get(a) for a in alanlar if a in v},
                            kaynak=v)
            return islev

        m50_ek_islevler = {"m50_" + e: _m50_ek_islev(e, a)
                           for e, a in _M50_EK.items()}

        # -------------------------------------------------------------
        # KUSUR-VIDEO-AI-KOPRU (2026-08-14): kamera ve AI eylemleri
        #
        # Kullanici istegi: "hem ai icin hem kameralar icin ayni kopru
        # gruplamasi gerekiyor".
        #
        # Kameralar saha aginda (ornegin 192.168.1.50) ya da dogrudan
        # USB ile saha bilgisayarinda; AI bilgisayarlari da saha aginda
        # (ornegin 192.168.1.100). Merkez sunucu bir veri merkezindedir
        # ve bu adreslerin HICBIRINE ulasamaz.
        #
        # Onceki surumde akis merkezde aciliyordu; bu yuzden yalnizca
        # genel internete acik kameralar geliyordu (kullanicinin ekledigi
        # 97.76.27.170 adresi bu yuzden calisiyordu). USB kamera listesi
        # de merkezde taraniyor ve HER ZAMAN bos donuyordu.
        # -------------------------------------------------------------
        def _video(eylem, veri=None, zaman_asimi=8.0):
            tamam, hata, cikti = self.servisler.komut_gonder(
                "video", eylem, veri or {}, zaman_asimi=zaman_asimi)
            sonuc = {"tamam": bool(tamam), "hata": hata or ""}
            if isinstance(cikti, dict):
                sonuc.update(cikti)
            return sonuc

        def video_cihazlar(v):
            """SAHADAKI yerel kameralari tarar.

            Onceki surumde bu tarama merkezde yapiliyordu; merkez
            sunucuda kamera aygiti olmadigi icin liste her zaman bos
            donuyordu ve cantaya takili kamera hic gorunmuyordu.

            Uzun zaman asimi bilincli: her aygit indeksi tek tek
            aciliyor, dolu bir makinede tarama 15 saniyeyi bulabilir.
            """
            return _video("cihazlar",
                          {"en_fazla": (v or {}).get("en_fazla", 6)},
                          zaman_asimi=25.0)

        def video_kamera_yaz(v):
            return _video("kamera_yaz", dict(v or {}))

        def video_kamera_sil(v):
            return _video("kamera_sil", {"id": (v or {}).get("id")})

        def video_akis_baslat(v):
            """Akisi SAHADA acar.

            Uzun zaman asimi bilincli: RTSP el sikismasi ve ILK KARE
            uretimi 12 saniyeye kadar surebilir (`ilk_kare_bekle`). Kisa
            tutulsaydi calisan bir kamera "acilamadi" gorunurdu.
            """
            return _video("akis_baslat", dict(v or {}), zaman_asimi=25.0)

        def video_akis_durdur(v):
            return _video("akis_durdur", {"id": (v or {}).get("id")})

        def video_durum(_v):
            return _video("durum", {}, zaman_asimi=4.0)

        def _ai(eylem, veri=None, zaman_asimi=8.0):
            tamam, hata, cikti = self.servisler.komut_gonder(
                "ai", eylem, veri or {}, zaman_asimi=zaman_asimi)
            sonuc = {"tamam": bool(tamam), "hata": hata or ""}
            if isinstance(cikti, dict):
                sonuc.update(cikti)
            return sonuc

        def ai_sunucu_yaz(v):
            return _ai("sunucu_yaz", dict(v or {}))

        def ai_sunucu_sil(v):
            return _ai("sunucu_sil", {"id": (v or {}).get("id")})

        def ai_izleme_baslat(v):
            """Izleme gorevini SAHADAN atar.

            Onceki surumde merkez, saha agindaki AI bilgisayarina
            dogrudan HTTP istegi atiyor ve her zaman zaman asimina
            dusuyordu. Ustelik isciye verilen akis adresi de merkezin
            kendi vekilini gosteriyordu; isci o adrese de erisemezdi.
            Artik hem istek hem akis adresi saha agi icinde kalir.
            """
            return _ai("izleme_baslat", dict(v or {}), zaman_asimi=25.0)

        def ai_izleme_durdur(v):
            return _ai("izleme_durdur",
                       {"kamera_id": (v or {}).get("kamera_id")})

        def ai_izleme_listesi(_v):
            return _ai("izleme_listesi", {}, zaman_asimi=4.0)

        def ai_durum(_v):
            return _ai("durum", {}, zaman_asimi=4.0)

        return {
            "sistem_bilgi": sistem_bilgi,
            "servis_durum": servis_durum,
            "yetenekler": yetenekler,
            "dron_sayisi": dron_sayisi,
            "durum": servis_durum,
            "konsol": konsol,
            "servis_baslat": servis_baslat,
            "servis_durdur": servis_durdur,
            "seri_portlar": seri_portlar,
            "akis_ac": akis_ac,
            "akis_kapat": akis_kapat,
            "akis_yaz": akis_yaz,
            "akis_durum": akis_durum,
            "ai_ssh_baslat": ai_ssh_baslat,
            "ai_ssh_durdur": ai_ssh_durdur,
            "ai_ssh_gecmis": ai_ssh_gecmis,
            "ai_ssh_durumlar": ai_ssh_durumlar,
            "gcsdual_portlar": gcsdual_portlar,
            "gcsdual_baglan": gcsdual_baglan,
            "gcsdual_kes": gcsdual_kes,
            "gcsdual_led": gcsdual_led,
            "gcsdual_kalibre": gcsdual_kalibre,
            "gcsdual_durum": gcsdual_durum,
            "radar_baglan": radar_baglan,
            "radar_kes": radar_kes,
            "radar_durum": radar_durum,
            "radar_ayar_oku": radar_ayar_oku,
            "radar_ayar_yaz": radar_ayar_yaz,
            "radar_rtk": radar_rtk,
            "radar_secim_yaz": radar_secim_yaz,
            "radar_secim_oku": radar_secim_oku,
            "radar_json_oku": radar_json_oku,
            "radar_json_yaz": radar_json_yaz,
            "radar_cihazlar": radar_cihazlar,
            "m50_durum": m50_durum,
            "m50_cihazlar": m50_cihazlar,
            "m50_ayar_oku": m50_ayar_oku,
            "m50_ayar_yaz": m50_ayar_yaz,
            "m50_baglan": m50_baglan,
            "m50_kes": m50_kes,
            "m50_ptz": m50_ptz,
            "m50_lens": m50_lens,
            "m50_aci_konumla": m50_aci_konumla,
            "m50_takip_sec": m50_takip_sec,
            "m50_takip_baslat": m50_takip_baslat,
            "m50_takip_durdur": m50_takip_durdur,
            **m50_ek_islevler,
            "video_cihazlar": video_cihazlar,
            "video_kamera_yaz": video_kamera_yaz,
            "video_kamera_sil": video_kamera_sil,
            "video_akis_baslat": video_akis_baslat,
            "video_akis_durdur": video_akis_durdur,
            "video_durum": video_durum,
            "ai_sunucu_yaz": ai_sunucu_yaz,
            "ai_sunucu_sil": ai_sunucu_sil,
            "ai_izleme_baslat": ai_izleme_baslat,
            "ai_izleme_durdur": ai_izleme_durdur,
            "ai_izleme_listesi": ai_izleme_listesi,
            "ai_durum": ai_durum,
            # Ajanin HIZLI YOLU: `{"tur":"akis"}` mesaji icin. Imzasi
            # digerlerinden farklidir (kanal_id, byte) cunku JSON
            # cerceveleme ve yanit uretimi atlanir.
            "akis_yaz_ham": self._akis_yaz_ham,
        }

    def _akis_yaz_ham(self, kanal_id, veri):
        if not veri:
            return 0
        try:
            return self.kanallar.yaz(kanal_id, veri)
        except akis_mod.AkisHatasi:
            # Kanal kapanmis olabilir (kullanici stop'a basti, telemetri
            # radyosu cikarildi). Gunluge yazmak, sn'de onlarca satir
            # uretip konsolu kullanilamaz hale getirir; sessiz atilir.
            # Kullanici durumu kanal listesinde "kapali" olarak gorur.
            return 0

    # -----------------------------------------------------------------
    # Akis
    # -----------------------------------------------------------------
    def _akis_gonder(self, kanal_id, veri):
        """Kanaldan okunan byte'i merkeze yollar.

        Ajan yoksa veya bagli degilse paket ATILIR (kuyruga alinmaz):
        gecikmis telemetri degersizdir ve kuyruk bellegi doldurur.
        Kalicilik dakikalik tampon dosyalariyla saglanir.
        """
        a = self.ajan
        if not (a and a.bagli):
            return False
        return a.akis_gonder(kanal_id, veri)

    def servis_durumu_zengin(self, yetkiler=None):
        """Servis durumlarini GERCEK kanal sayimiyla zenginlestirir.

        v1.5.6 — `yetkiler` verilirse (girisli oturumun merkezden gelen
        yetki ozeti) firmaya tanimli OLMAYAN servisler listeden duser;
        panelin sol menusu bu listeyi oldugu gibi cizer. `None` iken
        suzme yapilmaz: merkeze verilen `servis_durum` yaniti ve ic
        olcumler tam listeyi gormeye devam eder.

        Neden gerekli: `Servis.olcumler()` yalniz alt surecin yazdigi
        durum DOSYASINI okur. Akis kanallari ise alt surecte degil BU
        surecte (panel/ajan sureci) tutulur; dolayisiyla dron servisi
        kendi acik kanallarini goremez ve dosyaya her zaman 0 yazar.
        Panelde "Dron: 0" gorunurken merkezde ucus surerdi.

        Cozum: sayim, kanallarin gercekten yasadigi yerde yapilir ve
        servis ozetine burada eklenir.
        """
        liste = self.servisler.durum(yetkiler)
        try:
            self.kanallar.temizle_olu()
            n = int(self.kanallar.etkin_sayi() or 0)
        except Exception:
            n = 0
        for s in liste:
            if s.get("ad") != "dron":
                continue
            o = s.get("olcumler")
            if not isinstance(o, dict):
                o = {}
                s["olcumler"] = o
            # Servis durmussa kanal da olamaz; durmus servis icin canli
            # sayi gostermek yanlis karar dogurur.
            o["dron_sayisi"] = n if s.get("calisiyor") else 0
        return liste

    def kanal_durumu(self):
        """Acik ucus kanallarinin panele uygun ozeti."""
        try:
            return self.kanallar.durum()
        except Exception:
            return []

    def kanallari_kapat(self, neden=""):
        """Tum akis kanallarini kapatir.

        Cagrildigi yerler: dron servisi durdurulunca, uygulama
        kapanirken ve merkez baglantisi kalici kaybedildiginde.
        """
        try:
            n = self.kanallar.etkin_sayi()
        except Exception:
            n = 0
        self.kanallar.tumunu_kapat()
        if n:
            self.gunluk("%d akis kanali kapatildi%s"
                        % (n, (" (%s)" % neden) if neden else ""), "uyari")

    def ajan_baslat(self):
        with self._ajan_kilit:
            if not ayar_mod.kimlik_var():
                return False, ("Merkez kaydi yok. Panelde MERKEZ KAYDI "
                               "bolumunden bu bilgisayari kaydedin.")
            if self.ajan and self.ajan.calisiyor():
                return True, None
            self.ajan = ajan_mod.KopruAjani(
                self._ajan_kimligi(), self._ajan_islevleri(),
                gunluk=lambda e, m, s="bilgi": self.gunluk(m, s))
            return self.ajan.baslat()

    def ajan_durdur(self):
        with self._ajan_kilit:
            if self.ajan:
                self.ajan.durdur()

    def ajan_durum(self):
        if not self.ajan:
            return {"yapilandirildi": ayar_mod.kimlik_var(),
                    "calisiyor": False, "bagli": False,
                    "adres": ayar_mod.ayar_oku().get("merkez_adres"),
                    "bekleyen_kayit": 0}
        return self.ajan.durum()

    # -----------------------------------------------------------------
    # Kurum logosu (merkez vekili)
    # -----------------------------------------------------------------
    def logo_al(self):
        """Giris yapan kullanicinin kurum logosunu dondurur.

        Bellekte onbeklenir: panel her saniye durum sorgusu yapar ve
        logoyu her seferinde merkezden cekmek gereksiz ag yuku ve
        merkez kesintisinde kirik gorsel demek olurdu.
        """
        with self._logo_kilit:
            if self._logo_ham is not None:
                return self._logo_ham, self._logo_tur
            adres = str(self._logo_adres or "")
        if not adres:
            return None, None
        ham, tur, hata = merkez_mod.logo_getir(adres)
        if hata or not ham:
            return None, None
        with self._logo_kilit:
            self._logo_ham, self._logo_tur = ham, tur
        return ham, tur

    def logo_adres_ayarla(self, adres):
        """Giriste cagrilir. Kurum DEGISIRSE onbelek dusurulur; aksi
        halde bir kurumun logosu digerine gosterilir."""
        with self._logo_kilit:
            if str(adres or "") != str(self._logo_adres or ""):
                self._logo_adres = str(adres or "")
                self._logo_ham = None
                self._logo_tur = None

    def kimlik_yenile(self):
        """Merkez kaydi degistiginde ajani YENI kimlikle yeniden kur.

        Ajan eski kimligi bellekte tutuyordu; yeniden kurmadan
        baglanmaya devam ederse merkez onu ESKI ornek olarak gorur ve
        yeni kayit hicbir zaman cevrimici gorunmez.
        """
        calisiyordu = bool(self.ajan and self.ajan.calisiyor())
        self.ajan_durdur()
        self.ajan = None
        if calisiyordu or ayar_mod.kimlik_var():
            self.ajan_baslat()

    # -----------------------------------------------------------------
    def acilista_servisleri_baslat(self):
        """Ayarda isaretli servisleri acilista baslatir.

        v1.5.6 — YETKI SUZGECI YOK, bilincli: acilis, henuz kimse
        panele girmemisken calisir; oturum ve dolayisiyla merkez yetki
        ozeti HENUZ YOKTUR. Suzmek icin merkeze ayrica sormak gerekirdi
        ve merkez erisilemezken kopru kendi kendine calismayi surdurmeli.
        Guvenlik acigi dogurmaz: bir servisin acilis isaretini koyabilmek
        icin once panele YETKILI olarak girip ayari kaydetmis olmak
        gerekir; yetki sonradan geri alinirsa panel menusu ve
        `/api/servis/baslat` kapanir.
        """
        a = ayar_mod.ayar_oku().get("acilista_baslat") or {}
        for ad in servis_mod.SERVIS_ADLARI:
            if a.get(ad):
                tamam, hata = self.servisler.baslat(ad)
                self.gunluk("Acilista %s servisi: %s" % (
                    ad, "baslatildi" if tamam else ("HATA " + str(hata))),
                    "bilgi" if tamam else "uyari")

    def kapat(self):
        # Sira onemlidir: kanallar ONCE kapatilir. Ajan once
        # durdurulursa kanal okuma is parcaciklari kapali bir sokete
        # yazmayi denerken gereksiz hata yagmuru uretir.
        self.kanallari_kapat("uygulama kapaniyor")
        self.ajan_durdur()
        self.servisler.tumunu_durdur()
