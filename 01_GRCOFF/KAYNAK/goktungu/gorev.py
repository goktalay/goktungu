# -*- coding: utf-8 -*-
"""GorevYoneticisi: rota noktalarindan MAVLink gorevi (mission) olusturur,
drona yukler ve gorevi baslatir / duraklatir / devam ettirir.

MAVLink mission protokolu istek-yanit temellidir (MISSION_COUNT ->
MISSION_REQUEST(_INT) x N -> MISSION_ACK). Seri okuma dongusu ayri
thread'de calistigi icin bu mesajlar DronYoneticisi._dongu tarafindan
yakalanip mesaj_isle() ile buraya iletilir.

Gorev yapisi (ArduPilot Copter):
  seq 0 : home (ArduPilot tarafindan yoksayilir, dummy)
  seq 1 : MAV_CMD_NAV_TAKEOFF (ilk noktanin irtifasina) — HER ZAMAN
  sonra her rota noktasi icin:
    MAV_CMD_DO_CHANGE_SPEED (nokta hizi, onceki noktadan farkliysa)
    MAV_CMD_NAV_WAYPOINT   (lat/lon/irtifa, MAV_FRAME_GLOBAL_RELATIVE_ALT)

Baslama akisi (ACK sonrasi, ayri thread):
  GUIDED -> ARM -> arm teyidi bekle -> AUTO -> MISSION_START
ArduPilot yerde AUTO'da mission'i ancak ARM'li iken baslatir; arm
teyidi beklenmezse AUTO gecisi reddedilebilir. Bu surum arm durumunu
telemetriden (dronlar[sysid]["arm"]) 5 sn'ye kadar bekler.

v2.4.20: YUKLEME ve BASLATMA ayrildi.
  yukle(sysid, rota)  -> yalnizca gorevi drona yukler; ACK gelince
                         asama "yuklendi" olur, dron ARM edilmez.
  baslat(sysid)       -> yuklenmis gorevi baslatir (GUIDED/ARM/AUTO/
                         MISSION_START).
  yukle_ve_baslat()   -> geriye donuk uyumluluk (otomatik baslatir).
Yukleme sirasinda ilerleme yuzdesi durum paketinde yayinlanir
(gonderilen oge / toplam oge) — arayuz ilerleme cubugu bunu kullanir.

v2.4.35: GOREV TAMAMLANMA, DURDURMA DAVRANISI ve SURDURME eklendi.

  1) Tamamlanma tespiti:
     MISSION_CURRENT (dron.py telemetriye `mission_seq` olarak yazar)
     son ogeye ulastiginda ve arac AUTO'dan cikip LOITER/RTL/land'e
     gectiginde asama "tamamlandi" olur. ArduPilot gorev bitiminde
     son WP'de bekler (LOITER) veya RTL/LAND uygular; bu yuzden tek
     basina seq yeterli degildir, mod degisimi de gozlenir.

  2) Durdurma davranisi (durdurma_davranisi):
     "bekle"    -> BRAKE(17); arac kabul etmezse LOITER(5)
     "basa_don" -> RTL(6)
     Ilaclama gibi uzun gorevlerde batarya degisimi icin secilir.
     Secim gorev yuklenirken arayuzden gelir ve gorev kaydinda tutulur.

  3) Surdurme (batarya degisimi):
     Gorev kaydi diske yazilir (veri/gorev_durum.json). Dron offline
     olup tekrar online oldugunda, gorev tamamlanmadiysa kaldigi
     mission_seq drona MISSION_SET_CURRENT ile bildirilir ve AUTO
     verilir. Dron gorev listesini kendi kalici belleginde tuttugu
     icin yeniden yukleme gerekmez; yine de oge sayisi dogrulanir.
"""
import json
import math
import os
import threading
import time

from pymavlink import mavutil

from .sabitler import PROJE_KOKU, _veri_alt_yolu

YUKLEME_ZAMANASIMI = 15.0   # s; bu sure icinde ACK gelmezse hata
ARM_TEYIT_SURESI = 5.0      # s; arm teyidi bekleme suresi

# v2.4.35 — ArduPilot ucus modu numaralari (Copter)
MOD_AUTO = 3
MOD_GUIDED = 4
MOD_LOITER = 5
MOD_RTL = 6
MOD_BRAKE = 17

# v2.4.35 — mod gecisi telemetriden dogrulanirken beklenecek sure.
# set_mode_send ATESLE-UNUT bir mesajdir: arac modu reddetse bile
# Python tarafinda hata olusmaz. Bu yuzden gecis `dronlar[sysid]["mod"]`
# metninden dogrulanir; dogrulanamazsa yedek mod denenir.
MOD_TEYIT_SURESI = 2.5

# v2.4.35 — gorev bitiminde arac AUTO'dan cikar; bu modlar "gorev bitti"
# isareti sayilir (son WP'ye ulasilmis olmasi kosuluyla).
BITIS_MODLARI = ("LOITER", "RTL", "LAND", "GUIDED", "BRAKE", "HOLD",
                 "POSHOLD", "QLOITER", "QLAND")

# v2.4.35 — surdurme icin gorev kaydinin diske yazildigi dosya.
# Goreli yol KULLANILMAZ: sunucu farkli bir calisma dizininden
# baslatilabilir (servis olarak calistirmada siktir), bu durumda gorev
# durumu yanlis yere yazilir ve surdurme sessizce calismaz.
GOREV_DURUM_DOSYA = _veri_alt_yolu("gorev_durum.json")

# v2.4.35 — dron offline sayildiktan sonra tekrar online olursa
# surdurme onerilir. Bu sure telemetri kesintisi esigi.
OFFLINE_ESIGI = 10.0

# v2.4.145 — Sabit kanat saha/SITL performans testi yalnizca
# telemetri kaydi ve analiz etiketidir. Ucus kontrol komutlari,
# gaz, emniyet parametreleri veya rota ogeleri burada DEGISTIRILMEZ.
#
# v2.4.147 — ``sitl_dalis`` ayri ve daha dar bir yoldur: yalniz aktif
# ArduPlane SITL surecine, onayli bir mission listesi olarak yuklenir.
# Gercek araca, Copter/VTOL'e veya calismayan simulasyona asla uygulanmaz.
PERFORMANS_ORNEK_ARALIGI = 1.0
PERFORMANS_AZAMI_ORNEK = 1800
PERFORMANS_TEST_KLASOR = _veri_alt_yolu("performans_testleri")

# v2.4.35 — YANLIS "tamamlandi" TESPITINE KARSI KORUMA.
# Gorev baslatildiktan sonra bu sure gecmeden bitis kosulu
# degerlendirilmez. _gorevi_baslat() asamayi GUIDED->ARM->AUTO
# zincirinin sonunda "gorevde" yapar; HEARTBEAT henuz AUTO'yu
# bildirmemis olabilir ve kisa bir gorevde arac hala GUIDED gorunurken
# gorev BASLAMADAN bitmis sayilabilirdi.
BITIS_ASGARI_SURE = 5.0

# v2.4.35 — "tamamlandi" / "iptal" asamasi kayit dusurulmeden once bu
# sure boyunca yayinlanir; arayuzun durumu gorup rotayi haritadan
# kaldirmasi ve kullaniciya bildirmesi icin gereklidir.
BITIS_YAYIN_SURESI = 8.0


class GorevYoneticisi:

    def __init__(self, dron, konsol, kilit):
        """
        dron  : DronYoneticisi (master erisimi icin)
        konsol: KonsolLog
        kilit : paylasilan threading.Lock
        """
        self.dron = dron
        self.konsol = konsol
        self.kilit = kilit
        # Kompozisyon kokunde atanir. Varsayilan None oldugu icin SITL
        # kimligi dogrulanamayan hicbir dalis talebi kapali kalir.
        self.sitl = None
        # sysid -> aktif gorev durumu
        # {rota_id, rota_isim, ogeler[], gonderilen(set), asama,
        #  toplam_nokta, wp_seq_haritasi{mission_seq: nokta_index},
        #  baslangic_zamani}
        self.gorevler = {}
        self._yukleme_kilidi = threading.Lock()
        # v2.4.35 — surdurme durumu: sysid -> {
        #   "seq": kalinan mission_seq, "rota_id", "rota_isim",
        #   "toplam_oge", "toplam_nokta", "zaman", "nokta"
        # }
        # Gorev "gorevde"/"duraklatildi" iken telemetri kesilirse burada
        # tutulur; dron geri geldiginde arayuze surdurme onerisi cikar.
        self.surdurulebilir = {}
        # sysid -> son telemetri goruldugu an (offline tespiti icin)
        self._son_gorulme = {}
        self._durum_yaz_kilidi = threading.Lock()
        self._son_yazim = 0.0
        self._diskten_yukle()

    # ------------------------------------------------------------------
    # v2.4.35: Surdurme icin kalici depo
    # ------------------------------------------------------------------
    # Gorev kaydi (self.gorevler) yalnizca RAM'de tutulur. Ilaclama gibi
    # uzun gorevlerde batarya degisimi sirasinda sunucu da yeniden
    # baslatilabilir; bu durumda "kaldigi yerden devam" bilgisi kaybolur.
    # Bu yuzden yalnizca SURDURME icin gereken kucuk ozet diske yazilir.
    # Tum gorev ogeleri yazilmaz — dron gorev listesini kendi kalici
    # belleginde tutar, bize yalnizca kalinan seq ve dogrulama bilgisi
    # gerekir.
    # v2.4.51 — GOREV DURUMU ARTIK VERITABANINDA.
    #
    # Kullanici istegi: dosya tabanli durumlar PostgreSQL'e tasinsin.
    # Dosya yolu GERI DONUS olarak korunur: veritabani henuz
    # yapilandirilmamissa (ilk kurulum sihirbazi tamamlanmadan) veya
    # gecici olarak erisilemezse gorev surdurme SESSIZCE kaybolmaz.
    #
    # Bu, telemetri tamponunda ve harita karolarinda verilen kararin
    # ayni mantigi: veritabani ana depo, yerel dosya dayaniklilik agi.
    def _vt_hazir(self) -> bool:
        """Veritabani yazmaya hazir mi (yapilandirildi ve tablo var)."""
        try:
            from . import veritabani as vt
            if not vt.pg_kipinde():
                return True          # SQLite kipi: her zaman hazir
            from . import pg
            return pg.yapilandirma_var()
        except Exception:
            return False

    def _diskten_yukle(self):
        """Surdurulebilir gorevleri once VERITABANINDAN, yoksa dosyadan
        okur.

        Sira onemlidir: veritabani guncel kaynaktir. Dosya yalnizca
        veritabani okunamadiginda ya da v2.4.50'den yukseltmede henuz
        aktarilmamis kayit varsa kullanilir.
        """
        okundu = 0
        if self._vt_hazir():
            try:
                from . import veritabani as vt
                with vt.baglanti() as con:
                    for s in con.execute(
                            "SELECT sysid, kayit FROM gorev_durum").fetchall():
                        try:
                            self.surdurulebilir[int(s[0])] = json.loads(s[1])
                            okundu += 1
                        except (TypeError, ValueError):
                            continue
            except Exception as e:
                self.konsol("GOREV",
                            f"Gorev durumu veritabanindan okunamadi: {e}",
                            "uyari")
        if okundu:
            self.konsol("GOREV",
                        f"Yarim kalmis {okundu} gorev veritabanindan "
                        "okundu (surdurulebilir)", "uyari")
            return
        # Geri donus: eski JSON dosyasi (v2.4.50 ve oncesi)
        try:
            if not os.path.exists(GOREV_DURUM_DOSYA):
                return
            with open(GOREV_DURUM_DOSYA, "r", encoding="utf-8") as f:
                veri = json.load(f)
            for sysid_s, kayit in (veri.get("surdurulebilir") or {}).items():
                try:
                    self.surdurulebilir[int(sysid_s)] = kayit
                except (TypeError, ValueError):
                    continue
            if self.surdurulebilir:
                self.konsol("GOREV",
                            f"Yarim kalmis {len(self.surdurulebilir)} gorev "
                            "DOSYADAN okundu (veritabanina aktarilacak)",
                            "uyari")
                self._diske_yaz(zorla=True)   # veritabanina tasi
        except Exception as e:
            self.konsol("GOREV",
                        f"Gorev durumu okunamadi: {e}", "uyari")

    def _diske_yaz(self, zorla=False):
        """Surdurme ozetini diske yazar (en fazla 2 sn'de bir).

        Yayin dongusu saniyede birkac kez calisir; her cagrida diske
        yazmak gereksiz I/O olusturur. `zorla=True` yalnizca durum
        gercekten degistiginde (gorev basladi/bitti/iptal) kullanilir.
        """
        simdi = time.time()
        if not zorla and simdi - self._son_yazim < 2.0:
            return
        with self._durum_yaz_kilidi:
            self._son_yazim = simdi
            vt_yazildi = False
            if self._vt_hazir():
                try:
                    from . import veritabani as vt
                    with vt.baglanti() as con:
                        # Kalkan kayitlari sil: RAM'de olmayan sysid
                        # veritabaninda kalmamali, yoksa tamamlanmis
                        # gorev sonsuza kadar "surdurulebilir" gorunur.
                        mevcut = list(self.surdurulebilir.keys())
                        if mevcut:
                            yer = ",".join(["?"] * len(mevcut))
                            con.execute(
                                f"DELETE FROM gorev_durum WHERE sysid NOT IN"
                                f" ({yer})", tuple(mevcut))
                        else:
                            con.execute("DELETE FROM gorev_durum")
                        for sysid, kayit in self.surdurulebilir.items():
                            uid = str((kayit or {}).get("dron_uid")
                                      or f"sysid-{sysid}")
                            con.execute(
                                "INSERT OR REPLACE INTO gorev_durum"
                                " (dron_uid, sysid, kayit, ts)"
                                " VALUES (?,?,?,?)",
                                (uid, int(sysid),
                                 json.dumps(kayit, ensure_ascii=False),
                                 simdi))
                    vt_yazildi = True
                except Exception as e:
                    self.konsol("GOREV",
                                f"Gorev durumu veritabanina yazilamadi: {e}",
                                "uyari")
            # Veritabanina yazilamadiysa dosyaya yaz: surdurme bilgisi
            # UCUS ORTASINDA kaybolmamali.
            if not vt_yazildi:
                try:
                    klasor = os.path.dirname(GOREV_DURUM_DOSYA)
                    if klasor:
                        os.makedirs(klasor, exist_ok=True)
                    veri = {
                        "surum": "2.4.51",
                        "zaman": simdi,
                        "surdurulebilir": {
                            str(k): v for k, v in self.surdurulebilir.items()},
                    }
                    gecici = GOREV_DURUM_DOSYA + ".tmp"
                    with open(gecici, "w", encoding="utf-8") as f:
                        json.dump(veri, f, ensure_ascii=False, indent=1)
                    os.replace(gecici, GOREV_DURUM_DOSYA)
                except Exception as e:
                    self.konsol("GOREV",
                                f"Gorev durumu yazilamadi: {e}", "uyari")

    # ------------------------------------------------------------------
    # Gorev insa etme
    # ------------------------------------------------------------------
    @staticmethod
    def _ogeler_olustur(rota):
        """Rota sozlugunden mission item listesi uretir.

        Donen: (ogeler, wp_seq_haritasi, toplam_nokta)
        ogeler: (seq, frame, command, current, autocontinue,
                 p1..p4, x, y, z) demetleri
        """
        noktalar = rota.get("noktalar") or []
        ogeler = []
        wp_harita = {}
        REL = mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT
        # seq 0: home yeri (ArduPilot yoksayar; ilk nokta konumunu koy)
        n0 = noktalar[0]
        ogeler.append((0, mavutil.mavlink.MAV_FRAME_GLOBAL_INT,
                       mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                       0, 1, 0, 0, 0, 0,
                       int(n0["lat"] * 1e7), int(n0["lon"] * 1e7), 0.0))
        # seq 1: TAKEOFF — rotanin en basinda HER ZAMAN bulunur.
        # Irtifa: ilk noktanin irtifasi (yoksa rota varsayilani, o da
        # yoksa 10 m). Dron zaten havadaysa ArduPilot bu ogeyi atlar.
        takeoff_irtifa = float(n0.get("irtifa") or
                               rota.get("irtifa_varsayilan") or 10.0)
        takeoff_irtifa = max(2.0, min(500.0, takeoff_irtifa))
        ogeler.append((1, REL, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                       0, 1, 0, 0, 0, 0, 0, 0, takeoff_irtifa))
        seq = 2
        onceki_hiz = None
        onceki_aci = None
        for i, n in enumerate(noktalar):
            hiz = float(n.get("hiz", 0) or 0)
            if hiz > 0 and hiz != onceki_hiz:
                # Hiz degisimi: DO_CHANGE_SPEED (tip=1 ground speed)
                ogeler.append((seq, REL,
                               mavutil.mavlink.MAV_CMD_DO_CHANGE_SPEED,
                               0, 1, 1, hiz, -1, 0, 0, 0, 0.0))
                seq += 1
                onceki_hiz = hiz
            # v2.4.23: nokta yonelim acisi (yaw). aci >= 0 ise
            # CONDITION_YAW ile mutlak pusula acisi verilir; aci < 0
            # (veya yok) ise otomatik davranis korunur. Ayni aci
            # tekrar edilmez.
            aci = n.get("aci")
            try:
                aci = float(aci) if aci is not None else None
            except (TypeError, ValueError):
                aci = None
            if aci is not None and aci >= 0 and aci != onceki_aci:
                # p1=hedef aci (deg), p2=donus hizi (0=varsayilan),
                # p3=yon (0=en kisa), p4=0 -> mutlak aci
                ogeler.append((seq, REL,
                               mavutil.mavlink.MAV_CMD_CONDITION_YAW,
                               0, 1, float(aci % 360.0), 0, 0, 0,
                               0, 0, 0.0))
                seq += 1
                onceki_aci = aci
            elif aci is not None and aci < 0:
                onceki_aci = None      # otomatik moda don
            ogeler.append((seq, REL, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                           0, 1, float(n.get("bekle", 0) or 0), 0, 0, 0,
                           int(n["lat"] * 1e7), int(n["lon"] * 1e7),
                           float(n.get("irtifa", 10))))
            wp_harita[seq] = i + 1   # 1-tabanli nokta numarasi
            seq += 1
        return ogeler, wp_harita, len(noktalar)

    # ------------------------------------------------------------------
    # Yukleme akisi
    # ------------------------------------------------------------------
    def yukle_ve_baslat(self, sysid, rota):
        """Geriye donuk uyum: yukler ve ACK sonrasi otomatik baslatir."""
        return self.yukle(sysid, rota, otomatik_baslat=True)

    def yukle(self, sysid, rota, otomatik_baslat=False,
              durdurma_davranisi="bekle"):
        """Gorevi drona YALNIZCA yukler (v2.4.20).

        otomatik_baslat=True ise ACK sonrasi eski davranis uygulanir
        (arm + AUTO + MISSION_START). Varsayilan False: ACK gelince
        asama "yuklendi" olur ve dron beklemede kalir; baslatma ayri
        baslat() cagrisiyla yapilir.

        durdurma_davranisi (v2.4.35): gorev DURDURULDUGUNDA ne yapilacagi.
          "bekle"    -> durdugu yerde bekler (BRAKE, yedek LOITER)
          "basa_don" -> baslangic noktasina doner (RTL)
        Ilaclama gibi uzun gorevlerde batarya degisimi icin secilir.

        Bloklamaz: yukleme durumu olusturur ve MISSION_COUNT gonderir;
        devami mesaj_isle() uzerinden yurur. Zamanasimini denetim()
        kontrol eder.
        """
        sysid = int(sysid)
        if durdurma_davranisi not in ("bekle", "basa_don"):
            durdurma_davranisi = "bekle"
        master = self.dron.master_bul(sysid)
        noktalar = rota.get("noktalar") or []
        if master is None or not noktalar:
            neden = ("MAVLink baglantisi yok." if master is None
                     else "Rota noktasi yok.")
            self.konsol("GOREV", neden, "hata")
            # UI'nin YUKLENIYOR'da takilmamasi icin hata kaydi olustur
            self.gorevler[sysid] = {
                "rota_id": rota.get("id"),
                "rota_isim": rota.get("isim", "?"),
                "ogeler": [], "gonderilen": set(),
                "asama": "hata",
                "toplam_nokta": len(noktalar), "toplam_oge": 0,
                "wp_harita": {}, "zaman": time.time(),
                "durdurma_davranisi": durdurma_davranisi,
            }
            return False
        ogeler, wp_harita, toplam = self._ogeler_olustur(rota)
        with self._yukleme_kilidi:
            self.gorevler[sysid] = {
                "rota_id": rota.get("id"),
                "rota_isim": rota.get("isim", "?"),
                "ogeler": ogeler,
                "gonderilen": set(),
                "asama": "yukleniyor",
                "toplam_nokta": toplam,
                "toplam_oge": len(ogeler),
                "wp_harita": wp_harita,
                "zaman": time.time(),
                # Son protokol hareketi (COUNT/REQUEST/ACK). Ara istek veya
                # ACK kaybolursa ayni mission listesi yeniden baslatilir.
                "son_hareket": time.time(),
                "count_deneme": 0,
                "protokol_deneme": 0,
                # v2.4.20: ACK sonrasi otomatik baslatilsin mi?
                "otomatik_baslat": bool(otomatik_baslat),
                # Yukleme ilerlemesi icin son gonderilen oge sirasi
                "son_seq": -1,
                # v2.4.35: gorev durdurulunca ne yapilacak
                "durdurma_davranisi": durdurma_davranisi,
                # v2.4.35: ucus sirasinda ulasilan en yuksek mission_seq
                # (MISSION_CURRENT telemetrisinden izlenir)
                "mevcut_seq": 0,
                "en_yuksek_seq": 0,
                # v2.4.35: tamamlanma/surdurme izleme damgalari
                "baslama_zamani": 0.0,
                "bitis_zamani": 0.0,
                "surduruldu": False,
                # v2.4.147: Baslat aninda istenecek SITL dalis profili
                # mission listesini guvenle yeniden derlemek zorundadir.
                # Bu RAM anlik goruntusu haricinde rota/kullanici verisi
                # degistirilmez ve kalici surdurme deposuna yazilmaz.
                "rota": dict(rota, noktalar=[dict(n) for n in noktalar]),
            }
        # v2.4.35: yeni gorev yuklendi — ayni arac icin eski yarim kalmis
        # gorev kaydi artik gecersiz. Aksi halde kullanici yeni bir rota
        # yukledikten sonra "eski goreve devam et" onerisi gorur ve yanlis
        # goreve donme riski dogar.
        if self.surdurulebilir.pop(sysid, None) is not None:
            self._diske_yaz(zorla=True)
        try:
            with self.kilit:
                master.mav.mission_count_send(
                    sysid, 1, len(ogeler),
                    mavutil.mavlink.MAV_MISSION_TYPE_MISSION)
        except Exception as e:
            self.konsol("GOREV", f"Gorev gonderim hatasi: {e}", "hata")
            self._asama(sysid, "hata")
            return False
        self.konsol("GOREV",
                    f"sysid={sysid} '{rota.get('isim')}' gorevi "
                    f"yukleniyor ({len(ogeler)} oge / {toplam} nokta)")
        return True

    # ------------------------------------------------------------------
    # Yuklenmis gorevi baslatma (v2.4.20)
    # ------------------------------------------------------------------
    def baslat(self, sysid, performans_test=None, sitl_dalis=None):
        """Drona YUKLENMIS gorevi baslatir.

        On kosul: bu sysid icin asama "yuklendi" (veya "hata" sonrasi
        tekrar deneme) olmalidir. Yukleme surerken veya hic yukleme
        yapilmadan cagrilirsa reddedilir.

        Donen: (basari:bool, mesaj:str)
        """
        sysid = int(sysid)
        g = self.gorevler.get(sysid)
        if g is None:
            self.konsol("GOREV",
                        f"sysid={sysid} baslatilacak yuklu gorev yok - "
                        "once rotayi yukleyin.", "hata")
            return False, "gorev_yok"
        if g["asama"] == "yukleniyor":
            self.konsol("GOREV",
                        f"sysid={sysid} gorev henuz yukleniyor, "
                        "baslatma bekletildi.", "uyari")
            return False, "yukleniyor"
        if g["asama"] in ("gorevde", "duraklatildi"):
            self.konsol("GOREV",
                        f"sysid={sysid} gorev zaten calisiyor.", "uyari")
            return False, "zaten_gorevde"
        if self.dron.master_bul(sysid) is None:
            self.konsol("GOREV", "MAVLink baglantisi yok.", "hata")
            return False, "baglanti_yok"

        # v2.4.147: ``sitl_dalis`` ayri bir mission profili olarak ancak
        # canli ArduPlane SITL eslesmesi, sabit-kanat telemetrisi ve
        # parametre sinirlari birlikte dogrulanirsa uygulanabilir. UI veya
        # WebSocket istemcisinin "sanal" demesi hicbir zaman yeterli degildir.
        dalis_profili, dalis_hata = self._sitl_dalis_profili_dogrula(
            sysid, sitl_dalis)
        if dalis_hata:
            self.konsol("GOREV", f"sysid={sysid} SITL dalis istegi reddedildi: {dalis_hata}", "uyari")
            return False, dalis_hata
        if dalis_profili:
            if g["asama"] != "yuklendi":
                return False, "sitl_dalis_icin_yuklenmis_gorev_gerekli"
            return self._sitl_dalis_yukle_ve_baslat(sysid, g, dalis_profili)

        # Bu profil arac kontrolcüsüne komut GONDERMEZ. Yalnızca operatörün
        # önceden planladığı yaklaşımın telemetri kaydına açı/hız hedefini
        # iliştirir. Sabit kanat dışındaki araçlarda yanlış yorumlanmayı
        # önlemek için reddedilir.
        profil, hata = self._performans_profili_dogrula(
            sysid, performans_test)
        if hata:
            self.konsol("GOREV", f"sysid={sysid} performans profili reddedildi: {hata}", "uyari")
            return False, hata
        if profil:
            g["performans_test"] = profil

        threading.Thread(target=self._gorevi_baslat,
                         args=(sysid,), daemon=True).start()
        return True, g.get("rota_isim", "?")

    def _asama(self, sysid, asama):
        g = self.gorevler.get(int(sysid))
        if g:
            g["asama"] = asama
            g["zaman"] = time.time()

    def _sitl_dalis_profili_dogrula(self, sysid, ham):
        """Sanal dalis talebini kapali-varsayilan yaklasimla dogrular.

        Dalis profili, pitch/servo/gaz ya da emniyet parametresi yazmaz.
        Parametreler yalniz yeniden yuklenen ArduPlane SITL mission'inin son
        iki waypoint'ini (yaklasma ve cikis) tanimlar. Gercek baglanti,
        calismayan SITL, baska bir SITL tipi veya sabit kanat olmayan
        telemetri kesin olarak reddedilir.
        """
        if ham is None:
            return None, ""
        if not isinstance(ham, dict):
            return None, "gecersiz_sitl_dalis_istegi"
        if not ham.get("etkin"):
            return None, ""
        sitl = getattr(self, "sitl", None)
        sorgu = getattr(sitl, "sysid_bilgi", None)
        if not callable(sorgu):
            return None, "sitl_dogrulanamadi"
        bilgi = sorgu(sysid)
        if not isinstance(bilgi, dict) or not bilgi.get("calisiyor"):
            return None, "yalniz_aktif_sitl"
        if str(bilgi.get("tip") or "").strip().lower() != "sabit_kanat":
            return None, "yalniz_sabit_kanat_sitl"
        with self.kilit:
            d = dict(self.dron.dronlar.get(int(sysid)) or {})
        if int(d.get("arac_tipi") or 0) != 1:  # MAV_TYPE_FIXED_WING
            return None, "yalniz_sabit_kanat"
        try:
            # Arayuz pozitif "dalis derecesi" alir; profil bunu asagi yonlu
            # negatif pitch/geometri isaretiyle saklar.
            aci = float(ham.get("aci_derece"))
            hiz = float(ham.get("hedef_hiz_ms"))
            baslangic = float(ham.get("baslangic_irtifa_m"))
            cikis = float(ham.get("cikis_irtifa_m"))
        except (TypeError, ValueError):
            return None, "gecersiz_sitl_dalis_parametresi"
        if not (10.0 <= aci <= 35.0):
            return None, "sitl_dalis_aci_siniri_10_35"
        if not (10.0 <= hiz <= 25.0):
            return None, "sitl_dalis_hiz_siniri_10_25"
        if not (40.0 <= baslangic <= 120.0):
            return None, "sitl_dalis_baslangic_irtifa_siniri_40_120"
        if not (15.0 <= cikis <= 80.0):
            return None, "sitl_dalis_cikis_irtifa_siniri_15_80"
        if baslangic < cikis + 20.0:
            return None, "sitl_dalis_en_az_20m_irtifa_farki"
        return {
            "etkin": True,
            "tur": "sitl_dalis_simulasyonu",
            "aci_derece": -round(aci, 1),
            "hedef_hiz_ms": round(hiz, 1),
            "baslangic_irtifa_m": round(baslangic, 1),
            "cikis_irtifa_m": round(cikis, 1),
            "baslangic": 0.0,
            "bitis": 0.0,
            "durum": "hazir",
            "ornek_sayisi": 0,
            "ornekler": [],
            "son_ornek": 0.0,
            "sitl_bid": int(bilgi.get("bid") or 0),
        }, ""

    def _sitl_dalis_ogeleri_olustur(self, rota, profil):
        """Son rota noktasina iki noktalı bir SITL dalis ayagi ekler.

        Dalis dogrudan tutum/gaz komutuyla degil, hedef hizla ve geometrik
        olarak hesaplanan yaklasma mesafesiyle sirali mission waypoint'leri
        uzerinden ucar. Bu yol yalniz yukaridaki SITL dogrulamasindan sonra
        cagrilir.
        """
        noktalar = rota.get("noktalar") or []
        if len(noktalar) < 2:
            return None, None, None, None, "sitl_dalis_icin_en_az_iki_nokta"
        try:
            onceki = noktalar[-2]
            terminal = noktalar[-1]
            enlem = float(terminal["lat"])
            boylam = float(terminal["lon"])
            onceki_enlem = float(onceki["lat"])
            onceki_boylam = float(onceki["lon"])
        except (KeyError, TypeError, ValueError):
            return None, None, None, None, "sitl_dalis_gecersiz_terminal_koordinat"

        # Son rota bacaginin istikameti; kuzey=0, dogu=90 derece.
        kuzey = (enlem - onceki_enlem) * 111111.0
        dogu = (boylam - onceki_boylam) * 111111.0 * math.cos(math.radians(enlem))
        if math.hypot(kuzey, dogu) < 10.0:
            return None, None, None, None, "sitl_dalis_terminal_bacagi_cok_kisa"
        irtifa_farki = (float(profil["baslangic_irtifa_m"]) -
                         float(profil["cikis_irtifa_m"]))
        yatay = irtifa_farki / math.tan(math.radians(abs(float(profil["aci_derece"]))))
        if not (30.0 <= yatay <= 400.0):
            return None, None, None, None, "sitl_dalis_yaklasma_mesafesi_siniri"
        baslik = math.atan2(dogu, kuzey)
        yaklasma_enlem = enlem - ((math.cos(baslik) * yatay) / 111111.0)
        cos_enlem = math.cos(math.radians(enlem))
        if abs(cos_enlem) < 0.01:
            return None, None, None, None, "sitl_dalis_gecersiz_enlem"
        yaklasma_boylam = boylam - ((math.sin(baslik) * yatay) /
                                     (111111.0 * cos_enlem))

        hiz = float(profil["hedef_hiz_ms"])
        yeni_noktalar = [dict(n) for n in noktalar[:-1]]
        yeni_noktalar.append({
            "lat": yaklasma_enlem, "lon": yaklasma_boylam,
            "irtifa": float(profil["baslangic_irtifa_m"]), "hiz": hiz,
            "bekle": 0.0, "aci": -1,
        })
        cikis_noktasi = dict(terminal)
        cikis_noktasi.update({
            "lat": enlem, "lon": boylam,
            "irtifa": float(profil["cikis_irtifa_m"]), "hiz": hiz,
            "bekle": 0.0, "aci": -1,
        })
        yeni_noktalar.append(cikis_noktasi)
        senaryo_rota = dict(rota)
        senaryo_rota["noktalar"] = yeni_noktalar
        ogeler, wp_harita, toplam = self._ogeler_olustur(senaryo_rota)
        profil = dict(profil)
        # Nokta numarasi 1-tabanlidir: yaklasma, cikarilan terminalin yerine
        # gelir; cikis noktasi ondan hemen sonra eklenir.
        profil["baslangic_nokta"] = len(noktalar)
        profil["cikis_nokta"] = len(noktalar) + 1
        profil["yaklasma_mesafesi_m"] = round(yatay, 1)
        profil["baslangic_mission_seq"] = next(
            (s for s, n in wp_harita.items()
             if n == profil["baslangic_nokta"]), -1)
        profil["cikis_mission_seq"] = next(
            (s for s, n in wp_harita.items()
             if n == profil["cikis_nokta"]), -1)
        if profil["baslangic_mission_seq"] < 0 or profil["cikis_mission_seq"] < 0:
            return None, None, None, None, "sitl_dalis_mission_eslesemedi"
        return ogeler, wp_harita, toplam, profil, ""

    def _sitl_dalis_yukle_ve_baslat(self, sysid, g, profil):
        """SITL dalis mission'ini yeniden yukler ve ACK sonrasi baslatir."""
        rota = g.get("rota")
        if not isinstance(rota, dict):
            return False, "sitl_dalis_rota_anlik_goruntusu_yok"
        ogeler, wp_harita, toplam, profil, hata = self._sitl_dalis_ogeleri_olustur(
            rota, profil)
        if hata:
            self.konsol("GOREV", f"sysid={sysid} SITL dalis senaryosu kurulamadi: {hata}", "uyari")
            return False, hata
        master = self.dron.master_bul(sysid)
        if master is None:
            return False, "baglanti_yok"
        with self._yukleme_kilidi:
            if self.gorevler.get(sysid) is not g:
                return False, "gorev_degisti"
            g.update({
                "ogeler": ogeler, "gonderilen": set(), "asama": "yukleniyor",
                "toplam_nokta": toplam, "toplam_oge": len(ogeler),
                "wp_harita": wp_harita, "zaman": time.time(),
                "son_hareket": time.time(), "count_deneme": 0,
                "protokol_deneme": 0, "otomatik_baslat": True, "son_seq": -1,
                "mevcut_seq": 0, "en_yuksek_seq": 0,
                "performans_test": profil, "sitl_dalis": True,
            })
        try:
            with self.kilit:
                master.mav.mission_count_send(
                    sysid, 1, len(ogeler),
                    mavutil.mavlink.MAV_MISSION_TYPE_MISSION)
        except Exception as e:
            self._asama(sysid, "hata")
            self.konsol("GOREV", f"SITL dalis MISSION_COUNT hatasi: {e}", "hata")
            return False, "sitl_dalis_yukleme_hatasi"
        self.konsol(
            "GOREV", f"sysid={sysid} yalniz SITL dalis senaryosu yukleniyor "
            f"({len(ogeler)} oge; {profil['aci_derece']:.1f} deg, "
            f"{profil['hedef_hiz_ms']:.1f} m/s, "
            f"{profil['yaklasma_mesafesi_m']:.1f} m yaklasma)", "basari")
        return True, "sitl_dalis_yukleniyor"

    def _performans_profili_dogrula(self, sysid, ham):
        """Sadece sabit kanat için analiz/kayit profili olusturur.

        Bu fonksiyon MAVLink uzerinden hiz, pitch, gaz, mod veya emniyet
        parametresi yazmaz. Girdiler sahadaki planlanan manevrayi gerçek
        telemetriyle karsilastirmak uzere kaydedilir.
        """
        if not isinstance(ham, dict) or not ham.get("etkin"):
            return None, ""
        with self.kilit:
            d = dict(self.dron.dronlar.get(int(sysid)) or {})
        if int(d.get("arac_tipi") or 0) != 1:  # MAV_TYPE_FIXED_WING
            return None, "yalniz_sabit_kanat"
        try:
            aci = float(ham.get("aci_derece"))
            hiz = float(ham.get("hedef_hiz_ms"))
        except (TypeError, ValueError):
            return None, "gecersiz_performans_parametresi"
        # Girdi yalnızca analiz hedefidir; yine de hata girisini ve
        # anlamsiz test etiketlerini engelleyen muhafazakar sinirlar.
        if not (-25.0 <= aci <= -5.0):
            return None, "aci_siniri_-25_-5"
        if not (8.0 <= hiz <= 30.0):
            return None, "hiz_siniri_8_30"
        return {
            "etkin": True,
            "tur": "terminal_yaklasim_analiz",
            "aci_derece": round(aci, 1),
            "hedef_hiz_ms": round(hiz, 1),
            "baslangic": 0.0,
            "bitis": 0.0,
            "durum": "hazir",
            "ornek_sayisi": 0,
            "ornekler": [],
            "son_ornek": 0.0,
        }, ""

    def _performans_ornekle(self, g, d, simdi):
        """Yalnız etkin görevde gerçek telemetriyi 1 Hz kaydeder."""
        p = g.get("performans_test")
        if not isinstance(p, dict) or not p.get("etkin"):
            return
        if simdi - float(p.get("son_ornek") or 0.0) < PERFORMANS_ORNEK_ARALIGI:
            return
        if len(p.get("ornekler") or []) >= PERFORMANS_AZAMI_ORNEK:
            return
        p["son_ornek"] = simdi
        p["durum"] = "kayit"
        p["baslangic"] = float(p.get("baslangic") or simdi)
        o = {
            "t": round(simdi, 3),
            "alt_rel_m": round(float(d.get("alt_rel") or 0.0), 2),
            "groundspeed_ms": round(float(d.get("groundspeed") or 0.0), 2),
            "airspeed_ms": round(float(d.get("airspeed") or 0.0), 2),
            "vz_ms": round(float(d.get("vz") or 0.0), 2),
            "pitch_deg": round(float(d.get("pitch") or 0.0), 2),
            "roll_deg": round(float(d.get("roll") or 0.0), 2),
            "batarya_v": round(float(d.get("batarya_v") or 0.0), 2),
            "mission_seq": int(d.get("mission_seq") or -1),
            "mod": str(d.get("mod") or ""),
        }
        if p.get("tur") == "sitl_dalis_simulasyonu":
            baslangic_seq = int(p.get("baslangic_mission_seq") or -1)
            cikis_seq = int(p.get("cikis_mission_seq") or -1)
            mevcut_seq = int(o["mission_seq"])
            if mevcut_seq < baslangic_seq:
                asama = "yaklasma"
            elif mevcut_seq < cikis_seq:
                asama = "dalis"
            else:
                asama = "cikis"
            o.update({
                "senaryo_asamasi": asama,
                "hedef_dalis_aci_deg": float(p.get("aci_derece") or 0.0),
                "hedef_hiz_ms": float(p.get("hedef_hiz_ms") or 0.0),
                "hedef_baslangic_irtifa_m": float(p.get("baslangic_irtifa_m") or 0.0),
                "hedef_cikis_irtifa_m": float(p.get("cikis_irtifa_m") or 0.0),
            })
        p.setdefault("ornekler", []).append(o)
        p["ornek_sayisi"] = len(p["ornekler"])

    def _performans_kaydet(self, sysid, g, neden, simdi):
        """Analiz kaydini görevin sonucundan bagimsiz, atomik olarak yazar."""
        p = g.get("performans_test")
        if not isinstance(p, dict) or not p.get("etkin") or p.get("bitis"):
            return
        p["bitis"] = simdi
        p["durum"] = str(neden)
        try:
            os.makedirs(PERFORMANS_TEST_KLASOR, exist_ok=True)
            yol = os.path.join(PERFORMANS_TEST_KLASOR,
                               f"terminal_test_sysid{int(sysid)}_{int(simdi)}.json")
            gecici = yol + ".tmp"
            with open(gecici, "w", encoding="utf-8") as f:
                json.dump({"sysid": int(sysid), "rota_id": g.get("rota_id"),
                           "rota_isim": g.get("rota_isim"), "profil": p},
                          f, ensure_ascii=False, separators=(",", ":"))
            os.replace(gecici, yol)
            p["kayit_yolu"] = yol
            self.konsol("PERFORMANS", f"sysid={sysid} test kaydi yazildi: {neden}", "basari")
        except Exception as e:
            self.konsol("PERFORMANS", f"sysid={sysid} test kaydi yazilamadi: {e}", "hata")

    def mesaj_isle(self, msg):
        """DronYoneticisi._dongu'dan MISSION_* mesajlarini alir."""
        tip = msg.get_type()
        sysid = msg.get_srcSystem()
        g = self.gorevler.get(sysid)
        master = self.dron.master_bul(sysid)
        if master is None:
            return

        if tip in ("MISSION_REQUEST", "MISSION_REQUEST_INT"):
            if not g or g["asama"] != "yukleniyor":
                return
            seq = msg.seq
            if seq >= len(g["ogeler"]):
                return
            (s, frame, cmd, cur, ac,
             p1, p2, p3, p4, x, y, z) = g["ogeler"][seq]
            try:
                with self.kilit:
                    master.mav.mission_item_int_send(
                        sysid, 1, s, frame, cmd, cur, ac,
                        p1, p2, p3, p4, int(x), int(y), float(z),
                        mavutil.mavlink.MAV_MISSION_TYPE_MISSION)
                g["gonderilen"].add(seq)
                g["son_seq"] = seq
                g["zaman"] = time.time()
                g["son_hareket"] = g["zaman"]
            except Exception as e:
                self.konsol("GOREV", f"Oge gonderim hatasi: {e}", "hata")

        elif tip == "MISSION_ACK":
            if not g or g["asama"] != "yukleniyor":
                return
            g["son_hareket"] = time.time()
            if msg.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
                if g.get("otomatik_baslat"):
                    self.konsol("GOREV",
                                f"sysid={sysid} gorev kabul edildi "
                                f"({len(g['gonderilen'])}/"
                                f"{g['toplam_oge']} oge), "
                                "baslatiliyor...", "basari")
                    # Baslama dizisi bloklu (arm teyidi bekler) — seri
                    # okuma dongusunu kilitlememek icin ayri thread
                    threading.Thread(target=self._gorevi_baslat,
                                     args=(sysid,), daemon=True).start()
                else:
                    # v2.4.20: yalnizca yukleme — dron beklemede kalir
                    self._asama(sysid, "yuklendi")
                    self.konsol("GOREV",
                                f"sysid={sysid} gorev drona YUKLENDI "
                                f"({len(g['gonderilen'])}/"
                                f"{g['toplam_oge']} oge, "
                                f"{g['toplam_nokta']} nokta) - "
                                "baslatmak icin ROTAYI BASLAT",
                                "basari")
            else:
                self.konsol("GOREV",
                            f"sysid={sysid} gorev reddedildi "
                            f"(MAV_MISSION_RESULT={msg.type})", "hata")
                self._asama(sysid, "hata")

    def _arm_bekle(self, sysid, sure):
        """Telemetriden arm teyidini bekler; True=arm'li."""
        bitis = time.time() + sure
        while time.time() < bitis:
            with self.kilit:
                d = self.dron.dronlar.get(sysid, {})
                if d.get("armed"):
                    return True
            time.sleep(0.2)
        return False

    def _gorevi_baslat(self, sysid):
        """GUIDED + ARM -> arm teyidi -> AUTO -> MISSION_START.

        Ayri thread'de calisir (arm teyidi beklerken seri okuma
        dongusu bloklanmaz).
        """
        sysid = int(sysid)
        master = self.dron.master_bul(sysid)
        if master is None:
            self._asama(sysid, "hata")
            return
        try:
            with self.kilit:
                d = self.dron.dronlar.get(sysid, {})
                zaten_armli = bool(d.get("armed"))
            if not zaten_armli:
                # GUIDED'a al ve arm et (yerde)
                with self.kilit:
                    master.mav.set_mode_send(
                        sysid,
                        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                        4)  # GUIDED
                time.sleep(0.3)
                with self.kilit:
                    master.mav.command_long_send(
                        sysid, 1,
                        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                        0, 1, 0, 0, 0, 0, 0, 0)
                if not self._arm_bekle(sysid, ARM_TEYIT_SURESI):
                    self.konsol("GOREV",
                                f"sysid={sysid} ARM teyidi alinamadi "
                                "(pre-arm kontrolleri?). Gorev "
                                "baslatilamadi.", "hata")
                    self._asama(sysid, "hata")
                    return
            # AUTO moda al ve gorevi baslat
            with self.kilit:
                master.mav.set_mode_send(
                    sysid, mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                    3)  # AUTO
            time.sleep(0.3)
            with self.kilit:
                master.mav.command_long_send(
                    sysid, 1, mavutil.mavlink.MAV_CMD_MISSION_START,
                    0, 0, 0, 0, 0, 0, 0, 0)
            self._asama(sysid, "gorevde")
            g = self.gorevler.get(sysid)
            if g is not None:
                # v2.4.35: bitis tespitinin asgari sure korumasi bu
                # damgaya dayanir; doldurulmazsa koruma etkisiz kalir.
                g["baslama_zamani"] = time.time()
                g["auto_gorusme"] = False
            self.konsol("GOREV",
                        f"sysid={sysid} goreve gonderildi: "
                        f"'{g['rota_isim'] if g else '?'}'", "basari")
        except Exception as e:
            self.konsol("GOREV", f"Baslama hatasi: {e}", "hata")
            self._asama(sysid, "hata")

    # ------------------------------------------------------------------
    # Duraklat / devam et
    # ------------------------------------------------------------------
    # v2.4.35 — MOD GECISI DOGRULAMA
    #
    # `set_mode_send` ATESLE-UNUT bir MAVLink mesajidir: arac modu
    # reddetse bile Python tarafinda hicbir hata olusmaz. Bu yuzden eski
    # kodun try/except ile kurdugu "BRAKE olmazsa LOITER" yedegi ASLA
    # tetiklenmiyordu — BRAKE desteklemeyen bir aracta (sabit kanat,
    # bazi firmware surumleri) duraklatma SESSIZCE hic gerceklesmiyordu.
    #
    # Dogru yol: gecisi telemetriden dogrulamak. `dronlar[sysid]["mod"]`
    # HEARTBEAT'ten gelen mod METNIDIR ("AUTO", "BRAKE", "LOITER"...).
    def _mod_ayarla(self, sysid, mod_no, mod_ad, yedek=None,
                    yedek_ad=None):
        """Modu ayarlar ve gecisi telemetriden dogrular.

        Donen: (basari:bool, uygulanan_mod_adi:str|None)

        yedek verilirse ve birincil mod MOD_TEYIT_SURESI icinde
        dogrulanamazsa yedek mod denenir.
        """
        sysid = int(sysid)
        master = self.dron.master_bul(sysid)
        if master is None:
            return False, None

        def _gonder(no):
            try:
                with self.kilit:
                    master.mav.set_mode_send(
                        sysid,
                        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                        no)
                return True
            except Exception as e:
                self.konsol("GOREV", f"Mod gonderim hatasi: {e}", "hata")
                return False

        def _bekle(ad):
            """Telemetride mod adinin gorunmesini bekler."""
            bitis = time.time() + MOD_TEYIT_SURESI
            while time.time() < bitis:
                with self.kilit:
                    d = self.dron.dronlar.get(sysid, {})
                    simdiki = str(d.get("mod") or "")
                if simdiki.upper() == ad.upper():
                    return True
                time.sleep(0.15)
            return False

        if _gonder(mod_no) and _bekle(mod_ad):
            return True, mod_ad
        if yedek is None:
            return False, None
        self.konsol("GOREV",
                    f"sysid={sysid} {mod_ad} modu dogrulanamadi; "
                    f"{yedek_ad or yedek} deneniyor", "uyari")
        if _gonder(yedek) and _bekle(yedek_ad or ""):
            return True, (yedek_ad or str(yedek))
        return False, None

    def durdur(self, sysid):
        """Gorevi duraklatir (v2.4.35: davranisa gore).

        Gorev yuklenirken secilen `durdurma_davranisi`:
          "bekle"    -> BRAKE (17); dogrulanamazsa LOITER (5)
          "basa_don" -> RTL (6)

        Donen: (basari:bool, mesaj:str)
        """
        sysid = int(sysid)
        master = self.dron.master_bul(sysid)
        if master is None:
            self.konsol("GOREV", "MAVLink baglantisi yok.", "hata")
            return False, "baglanti_yok"
        g = self.gorevler.get(sysid)
        davranis = (g or {}).get("durdurma_davranisi") or "bekle"

        if davranis == "basa_don":
            ok, uygulanan = self._mod_ayarla(sysid, MOD_RTL, "RTL")
        else:
            ok, uygulanan = self._mod_ayarla(
                sysid, MOD_BRAKE, "BRAKE",
                yedek=MOD_LOITER, yedek_ad="LOITER")

        if not ok:
            # Mod gecisi dogrulanamadi: arac hala AUTO'da gorev ucuyor
            # olabilir. Kullaniciya YANLIS "duraklatildi" bilgisi vermek
            # tehlikelidir — asama degistirilmez.
            self.konsol("GOREV",
                        f"sysid={sysid} DURAKLATMA DOGRULANAMADI — arac "
                        "mod degisimini kabul etmedi; gorev suruyor "
                        "olabilir", "hata")
            return False, "mod_dogrulanamadi"

        self._asama(sysid, "duraklatildi")
        if g is not None:
            g["duraklatma_modu"] = uygulanan
        aciklama = ("baslangica donuyor" if davranis == "basa_don"
                    else "durdugu yerde bekliyor")
        self.konsol("GOREV",
                    f"sysid={sysid} gorev duraklatildi — {aciklama} "
                    f"({uygulanan})", "uyari")
        # Duraklatma aninda surdurme ozetini tazele (batarya degisimi
        # tam bu noktada yapilir).
        self._surdurme_kaydet(sysid)
        return True, uygulanan

    def devam(self, sysid):
        """Duraklatilan gorevi surdurur: AUTO moda geri al.

        Donen: (basari:bool, mesaj:str)
        """
        sysid = int(sysid)
        master = self.dron.master_bul(sysid)
        if master is None:
            self.konsol("GOREV", "MAVLink baglantisi yok.", "hata")
            return False, "baglanti_yok"
        ok, _ = self._mod_ayarla(sysid, MOD_AUTO, "AUTO")
        if not ok:
            self.konsol("GOREV",
                        f"sysid={sysid} AUTO moda gecis dogrulanamadi — "
                        "gorev devam etmiyor", "hata")
            return False, "mod_dogrulanamadi"
        self._asama(sysid, "gorevde")
        self.konsol("GOREV", f"sysid={sysid} gorev devam ediyor",
                    "basari")
        return True, "AUTO"

    # ------------------------------------------------------------------
    # Gorevi tamamen iptal et (v2.4.18)
    # ------------------------------------------------------------------
    def iptal(self, sysid):
        """Gorevi tamamen iptal eder.

        Adimlar:
          1) BRAKE (17) ile dronu aninda durdurur; BRAKE reddedilirse
             LOITER (5) moduna alir (dron havada guvenli bekler).
          2) Drondaki mission listesini temizler (MISSION_CLEAR_ALL) —
             boylece AUTO'ya donse bile eski goreve devam etmez.
          3) Aktif gorev kaydini siler; asama 'iptal' olarak yayinlanir.

        Donen: (basari:bool, mesaj:str)
        """
        sysid = int(sysid)
        master = self.dron.master_bul(sysid)
        if master is None:
            self.konsol("GOREV", "MAVLink baglantisi yok.", "hata")
            return False, "baglanti_yok"
        g = self.gorevler.get(sysid)
        isim = g["rota_isim"] if g else "?"
        # 1) Aninda durdur — v2.4.35: gecis telemetriden dogrulanir
        # (set_mode_send atesle-unut oldugu icin eski try/except yedegi
        #  asla tetiklenmiyordu; bkz. _mod_ayarla aciklamasi)
        ok, uygulanan = self._mod_ayarla(
            sysid, MOD_BRAKE, "BRAKE", yedek=MOD_LOITER, yedek_ad="LOITER")
        if not ok:
            self.konsol("GOREV",
                        f"sysid={sysid} iptalde durdurma modu "
                        "dogrulanamadi; gorev listesi yine de "
                        "temizleniyor", "uyari")
        try:
            with self.kilit:
                # 2) Drondaki gorev listesini temizle
                try:
                    master.mav.mission_clear_all_send(
                        sysid, 1,
                        mavutil.mavlink.MAV_MISSION_TYPE_MISSION)
                except TypeError:
                    # Eski pymavlink imzasi (mission_type parametresiz)
                    master.mav.mission_clear_all_send(sysid, 1)
        except Exception as e:
            self.konsol("GOREV", f"Iptal hatasi: {e}", "hata")
            return False, str(e)
        # 3) v2.4.35: kaydi HEMEN dusurmuyoruz.
        #
        # Eski davranis: asama="iptal" atanip hemen pop ediliyordu. Kayit
        # dustugu icin durum_paketi() iptali HIC yayinlamiyordu; arayuz
        # yalnizca "kayit yok oldu" goruyordu. Rotayi haritadan kaldirmak
        # ve kullaniciya iptali bildirmek icin durumun en az bir yayin
        # turunda gorunmesi gerekir. denetim() `dusme_zamani` gelince
        # kaydi temizler.
        if g:
            g["asama"] = "iptal"
            g["zaman"] = time.time()
            g["dusme_zamani"] = time.time() + BITIS_YAYIN_SURESI
        else:
            # Kayit yoksa (ornegin sunucu yeniden baslatildi) arayuzun
            # rotayi haritadan dusurebilmesi icin gecici iptal kaydi
            self.gorevler[sysid] = {
                "rota_id": None, "rota_isim": isim,
                "ogeler": [], "gonderilen": set(),
                "asama": "iptal", "toplam_nokta": 0, "toplam_oge": 0,
                "wp_harita": {}, "zaman": time.time(),
                "dusme_zamani": time.time() + BITIS_YAYIN_SURESI,
            }
        # Iptal edilen gorev artik surdurulemez. Varsa analiz kaydı
        # görevin iptal edildiğini açıkça gösterecek şekilde kapatılır.
        if g:
            self._performans_kaydet(sysid, g, "iptal", time.time())
        self.surdurulebilir.pop(sysid, None)
        self._diske_yaz(zorla=True)
        self.konsol("GOREV",
                    f"sysid={sysid} GOREV IPTAL EDILDI ('{isim}') - "
                    f"dron {uygulanan or 'durdurulamadi'}, gorev listesi "
                    "temizlendi", "uyari")
        return True, isim

    # ------------------------------------------------------------------
    # Denetim + durum yayini
    # ------------------------------------------------------------------
    def denetim(self):
        """Gorev denetimi (yayin dongusunden ~1sn arayla cagrilir).

        Yukleme asamasi:
        - MISSION_COUNT'a 3 sn icinde hic MISSION_REQUEST gelmediyse
          COUNT'u yeniden gonderir (2 deneme).
        - Toplam surede ACK gelmezse hata.

        v2.4.35 — ucus asamasi (gorevde / duraklatildi):
        - `mission_seq` telemetriden izlenir (MISSION_CURRENT).
        - Son ogeye ulasilip arac AUTO'dan cikmissa "tamamlandi".
        - Telemetri kesilirse surdurme kaydi olusturulur.
        - "tamamlandi" / "iptal" kayitlari bir yayin turu sonra dusurulur.
        """
        simdi = time.time()
        # Kayit uzerinde gezinirken silme yapilacagi icin liste kopyasi
        for sysid, g in list(self.gorevler.items()):
            asama = g.get("asama")

            # --- v2.4.35: bitmis kayitlarin gecikmeli dusurulmesi -----
            # Arayuzun "tamamlandi"/"iptal" durumunu en az bir yayin
            # turunda gormesi gerekir (rotayi haritadan kaldirmak ve
            # kullaniciya bildirmek icin).
            dusme = g.get("dusme_zamani")
            if dusme and simdi >= dusme:
                self.gorevler.pop(sysid, None)
                continue

            # --- v2.4.35: ucan gorevin takibi ------------------------
            if asama in ("gorevde", "duraklatildi"):
                self._ucus_denetim(sysid, g, simdi)
                continue

            if asama != "yukleniyor":
                continue
            son_hareket = float(g.get("son_hareket") or g.get("zaman") or simdi)
            gecen = simdi - son_hareket
            toplam_gecen = simdi - float(g.get("zaman") or simdi)
            # COUNT, REQUEST veya ACK akisi 3 sn durursa protokolu yeniden
            # baslat. Bu, yalniz ilk REQUEST kaybini degil ara REQUEST ve
            # son ACK kaybini da telafi eder. Ayni ogeler idempotenttir.
            if gecen > 3.0 and g.get("protokol_deneme", 0) < 3:
                g["protokol_deneme"] = g.get("protokol_deneme", 0) + 1
                g["count_deneme"] = g.get("count_deneme", 0) + 1
                g["gonderilen"].clear()
                g["son_seq"] = -1
                g["son_hareket"] = simdi
                master = self.dron.master_bul(sysid)
                if master:
                    try:
                        with self.kilit:
                            master.mav.mission_count_send(
                                sysid, 1, g["toplam_oge"],
                                mavutil.mavlink.MAV_MISSION_TYPE_MISSION)
                        self.konsol("GOREV",
                                    f"sysid={sysid} MISSION akisi yeniden "
                                    f"baslatildi ({g['protokol_deneme']}/3; "
                                    f"son ilerleme {len(g['gonderilen'])}/"
                                    f"{g['toplam_oge']})", "uyari")
                    except Exception as e:
                        self.konsol("GOREV", f"MISSION_COUNT yeniden gonderim hatasi: {e}", "hata")
                continue
            if (g.get("protokol_deneme", 0) >= 3 and gecen > 3.0) or toplam_gecen > YUKLEME_ZAMANASIMI:
                g["asama"] = "hata"
                self.konsol("GOREV",
                            f"sysid={sysid} gorev yukleme zamanasimi "
                            f"({len(g['gonderilen'])}/{g['toplam_oge']} "
                            "oge gonderildi)", "hata")

    # ------------------------------------------------------------------
    # v2.4.35: Ucus takibi, tamamlanma tespiti ve surdurme
    # ------------------------------------------------------------------
    def _ucus_denetim(self, sysid, g, simdi):
        """Ucan gorevi izler: seq ilerlemesi, tamamlanma, offline.

        MISSION_CURRENT mesaji dron.py tarafindan telemetri sozlugune
        `mission_seq` olarak yaziliyor (dron.py:1174). GorevYoneticisi'ne
        yonlendirilmedigi icin burada telemetriden okunur — boylece yeni
        bir MAVLink protokol yolu yazmak gerekmez.
        """
        with self.kilit:
            d = self.dron.dronlar.get(sysid)
            if d is None:
                telemetri_var = False
                seq = None
                mod = ""
                armed = None
                son_gorulme = None
            else:
                telemetri_var = True
                seq = d.get("mission_seq")
                mod = str(d.get("mod") or "")
                armed = d.get("armed")
                # dron.py:500 — alan adi "son_mesaj" (HEARTBEAT damgasi)
                son_gorulme = d.get("son_mesaj")

        # --- offline tespiti -------------------------------------------
        # Dron kaydi tumden silinmis olabilir (baglanti kapandi) ya da
        # kayit durur ama telemetri damgasi eskimis olabilir.
        cevrimdisi = not telemetri_var
        if telemetri_var and isinstance(son_gorulme, (int, float)):
            cevrimdisi = (simdi - son_gorulme) > OFFLINE_ESIGI

        if cevrimdisi:
            # Batarya degisimi burada olur: gorev bitmedi, dron gitti.
            # Surdurme ozetini yaz ve kaydi RAM'de tut — dron geri
            # geldiginde arayuz "kaldigi yerden devam" onerir.
            self._performans_kaydet(sysid, g, "telemetri_kesildi", simdi)
            self._surdurme_kaydet(sysid)
            return

        self._son_gorulme[sysid] = simdi
        self._performans_ornekle(g, d, simdi)

        # --- seq ilerlemesi -------------------------------------------
        # dron.py varsayilani -1'dir (henuz MISSION_CURRENT gelmedi);
        # bu deger ilerleme olarak sayilmamalidir.
        seq_gecerli = isinstance(seq, int) and seq >= 0
        if seq_gecerli:
            g["mevcut_seq"] = seq
            if seq > int(g.get("en_yuksek_seq") or 0):
                g["en_yuksek_seq"] = seq

        # --- AUTO teyidi ----------------------------------------------
        # Gorev gercekten ucmaya baslamadan bitmis sayilmamasi icin
        # aracin en az bir kez AUTO modunda gorulmesi sarttir.
        # _gorevi_baslat() asamayi GUIDED->ARM->AUTO zincirinin sonunda
        # "gorevde" yapar; ancak HEARTBEAT henuz AUTO'yu bildirmemis
        # olabilir. Bu teyit olmadan bitis kosulu degerlendirilmez.
        if mod.upper() == "AUTO":
            g["auto_gorusme"] = True

        # --- tamamlanma tespiti ---------------------------------------
        # Yalnizca seq'e bakmak YETERSIZ: ArduPilot gorev bitiminde son
        # WP'de bekler ve seq son degerde kalir. Ayrica RTL/LAND ogesi
        # varsa seq son ogeye ulasir ama arac hala inise devam eder.
        #
        # YANLIS TESPIT KORUMALARI (v2.4.35):
        #   a) arac en az bir kez AUTO'da gorulmus olmali
        #   b) gecerli bir mission_seq (>=0) gelmis olmali
        #   c) baslangictan bu yana asgari sure gecmis olmali
        # Bunlar olmadan, kisa/tek ogeli bir gorevde asama "gorevde"
        # olur olmaz arac hala GUIDED'da gorunurse gorev BASLAMADAN
        # tamamlanmis sayilabilirdi.
        if g.get("asama") != "gorevde":
            return
        if not g.get("auto_gorusme"):
            return
        if not seq_gecerli:
            return
        baslama = float(g.get("baslama_zamani") or 0.0)
        if baslama and (simdi - baslama) < BITIS_ASGARI_SURE:
            return

        toplam_oge = int(g.get("toplam_oge") or 0)
        son_oge = max(0, toplam_oge - 1)
        seq_bitti = int(g.get("en_yuksek_seq") or 0) >= son_oge
        mod_bitti = mod.upper() in BITIS_MODLARI
        disarm_bitti = (armed is False)
        if toplam_oge > 0 and seq_bitti and (mod_bitti or disarm_bitti):
            g["asama"] = "tamamlandi"
            g["zaman"] = simdi
            g["bitis_zamani"] = simdi
            # Arayuzun gormesi icin bir sure yayinda kalsin
            g["dusme_zamani"] = simdi + BITIS_YAYIN_SURESI
            self.surdurulebilir.pop(sysid, None)
            self._performans_kaydet(sysid, g, "tamamlandi", simdi)
            self._diske_yaz(zorla=True)
            neden = ("arac DISARM" if disarm_bitti
                     else f"mod {mod or '?'}")
            self.konsol("GOREV",
                        f"sysid={sysid} GOREV TAMAMLANDI "
                        f"('{g.get('rota_isim')}') — son nokta "
                        f"{g.get('en_yuksek_seq')}/{son_oge}, "
                        f"{neden}", "basari")

    def _surdurme_kaydet(self, sysid):
        """Yarim kalmis gorevin surdurme ozetini olusturur.

        Yalnizca ozet tutulur — tum gorev ogeleri degil. Dron gorev
        listesini kendi kalici belleginde tutar; batarya degisse bile
        kaybolmaz. Bize kalinan seq ve dogrulama bilgisi yeterlidir.
        """
        g = self.gorevler.get(int(sysid))
        if not g:
            return
        if g.get("asama") not in ("gorevde", "duraklatildi"):
            return
        seq = int(g.get("en_yuksek_seq") or g.get("mevcut_seq") or 0)
        nokta = (g.get("wp_harita") or {}).get(seq)
        self.surdurulebilir[int(sysid)] = {
            "seq": seq,
            "nokta": nokta,
            "rota_id": g.get("rota_id"),
            "rota_isim": g.get("rota_isim"),
            "toplam_oge": int(g.get("toplam_oge") or 0),
            "toplam_nokta": int(g.get("toplam_nokta") or 0),
            "durdurma_davranisi": g.get("durdurma_davranisi") or "bekle",
            "asama": g.get("asama"),
            "zaman": time.time(),
        }
        self._diske_yaz()

    def surdurulebilir_paketi(self):
        """Arayuze yayinlanacak surdurulebilir gorev ozetleri.

        Yalnizca dron SU AN cevrimici ve aktif gorev kaydi YOK ise
        onerilir — aksi halde zaten ucan bir gorev icin "devam et"
        dugmesi gostermek yanlis olur.
        """
        paket = {}
        for sysid, kayit in self.surdurulebilir.items():
            if sysid in self.gorevler:
                # Aktif kayit varsa oneri gosterilmez
                continue
            with self.kilit:
                cevrimici = sysid in self.dron.dronlar
            if not cevrimici:
                continue
            k = dict(kayit)
            k["cevrimici"] = True
            paket[str(sysid)] = k
        return paket

    def surdur(self, sysid):
        """Yarim kalmis gorevi kaldigi yerden surdurur (v2.4.35).

        Adimlar:
          1) Surdurme kaydini dogrula (dron cevrimici, kayit var).
          2) Drondaki gorev listesinin oge sayisini dogrula — farkliysa
             gorev degismis demektir, surdurme yapilmaz.
          3) MISSION_SET_CURRENT ile kalinan seq'e konumlan.
          4) ARM (gerekiyorsa) + AUTO moduna al.

        Donen: (basari:bool, mesaj:str)
        """
        sysid = int(sysid)
        kayit = self.surdurulebilir.get(sysid)
        if not kayit:
            return False, "surdurulecek_gorev_yok"
        master = self.dron.master_bul(sysid)
        if master is None:
            return False, "baglanti_yok"
        seq = int(kayit.get("seq") or 0)
        toplam_oge = int(kayit.get("toplam_oge") or 0)
        if toplam_oge and seq >= toplam_oge:
            # Son ogedeyse surdurulecek bir sey kalmamis
            self.surdurulebilir.pop(sysid, None)
            self._diske_yaz(zorla=True)
            return False, "gorev_zaten_bitmis"

        # 3) Kalinan seq'e konumlan.
        # MISSION_SET_CURRENT eski ama yaygin desteklenen yoldur.
        try:
            with self.kilit:
                master.mav.mission_set_current_send(sysid, 1, seq)
        except Exception as e:
            self.konsol("GOREV",
                        f"Surdurme (set_current) hatasi: {e}", "hata")
            return False, str(e)

        # 4) Gerekiyorsa ARM, sonra AUTO
        with self.kilit:
            d = self.dron.dronlar.get(sysid, {})
            armed = d.get("armed")
        if armed is False:
            ok_guided, _ = self._mod_ayarla(sysid, MOD_GUIDED, "GUIDED")
            if not ok_guided:
                self.konsol("GOREV",
                            f"sysid={sysid} surdurme icin GUIDED moda "
                            "gecilemedi", "hata")
                return False, "mod_dogrulanamadi"
            try:
                with self.kilit:
                    master.mav.command_long_send(
                        sysid, 1,
                        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                        0, 1, 0, 0, 0, 0, 0, 0)
            except Exception as e:
                return False, f"arm_hatasi: {e}"
            if not self._arm_bekle(sysid, ARM_TEYIT_SURESI):
                self.konsol("GOREV",
                            f"sysid={sysid} surdurme icin ARM teyidi "
                            "alinamadi", "hata")
                return False, "arm_teyidi_yok"

        ok, _ = self._mod_ayarla(sysid, MOD_AUTO, "AUTO")
        if not ok:
            return False, "mod_dogrulanamadi"
        try:
            with self.kilit:
                master.mav.command_long_send(
                    sysid, 1, mavutil.mavlink.MAV_CMD_MISSION_START,
                    0, 0, 0, 0, 0, 0, 0, 0)
        except Exception:
            # AUTO modu dogrulandi; MISSION_START gonderilemese bile
            # arac gorevi surdurur. Kritik degil.
            pass

        # Aktif gorev kaydini yeniden kur (surdurulmus olarak)
        self.gorevler[sysid] = {
            "rota_id": kayit.get("rota_id"),
            "rota_isim": kayit.get("rota_isim") or "?",
            "ogeler": [], "gonderilen": set(),
            "asama": "gorevde",
            "toplam_nokta": int(kayit.get("toplam_nokta") or 0),
            "toplam_oge": toplam_oge,
            "wp_harita": {},
            "zaman": time.time(),
            "durdurma_davranisi": (kayit.get("durdurma_davranisi")
                                   or "bekle"),
            "mevcut_seq": seq,
            "en_yuksek_seq": seq,
            "baslama_zamani": time.time(),
            "bitis_zamani": 0.0,
            "surduruldu": True,
        }
        self.surdurulebilir.pop(sysid, None)
        self._diske_yaz(zorla=True)
        self.konsol("GOREV",
                    f"sysid={sysid} GOREV SURDURULDU "
                    f"('{kayit.get('rota_isim')}') — nokta {seq} "
                    f"({seq + 1}/{toplam_oge}) itibariyla devam",
                    "basari")
        return True, str(kayit.get("rota_isim") or "")

    def durum_paketi(self):
        """Telemetri yayinina eklenecek gorev durumlari.

        v2.4.20: yukleme ilerlemesi de yayinlanir:
          yuklenen_oge / toplam_oge ve yuzde (0-100).

        v2.4.35: ucus ilerlemesi ve davranis bilgisi eklendi:
          mevcut_seq, en_yuksek_seq, gorev_yuzde (ucus ilerlemesi),
          durdurma_davranisi, surduruldu.
        """
        paket = {}
        for sysid, g in self.gorevler.items():
            toplam_oge = int(g.get("toplam_oge") or 0)
            yuklenen = len(g.get("gonderilen") or ())
            asama = g["asama"]
            if asama in ("yuklendi", "gorevde", "duraklatildi",
                         "tamamlandi"):
                yuzde = 100
            elif toplam_oge > 0:
                yuzde = int(round(100.0 * yuklenen / toplam_oge))
                yuzde = max(0, min(99, yuzde))
            else:
                yuzde = 0

            # v2.4.35 — UCUS ilerlemesi (yukleme yuzdesinden AYRI).
            # Yukleme yuzdesi "kac oge drona gonderildi", bu ise
            # "kac nokta uculdu" bilgisidir; ikisi karistirilmamalidir.
            en_yuksek = int(g.get("en_yuksek_seq") or 0)
            if asama == "tamamlandi":
                gorev_yuzde = 100
            elif toplam_oge > 1 and asama in ("gorevde", "duraklatildi"):
                gorev_yuzde = int(round(
                    100.0 * en_yuksek / max(1, toplam_oge - 1)))
                gorev_yuzde = max(0, min(99, gorev_yuzde))
            else:
                gorev_yuzde = 0

            paket[str(sysid)] = {
                "rota_id": g["rota_id"],
                "rota_isim": g["rota_isim"],
                "asama": asama,
                "toplam_nokta": g["toplam_nokta"],
                "wp_harita": {str(k): v for k, v in g["wp_harita"].items()},
                "toplam_oge": toplam_oge,
                "yuklenen_oge": yuklenen,
                "yuzde": yuzde,
                # v2.4.35
                "mevcut_seq": int(g.get("mevcut_seq") or -1),
                "en_yuksek_seq": en_yuksek,
                "gorev_yuzde": gorev_yuzde,
                "durdurma_davranisi": (g.get("durdurma_davranisi")
                                       or "bekle"),
                "duraklatma_modu": g.get("duraklatma_modu") or "",
                "surduruldu": bool(g.get("surduruldu")),
                # Analiz etiketi ve özet bilgi yayınlanır; ham örnekler
                # telemetri paketini büyütmemek için yalnız dosyada tutulur.
                "performans_test": ({k: v for k, v in
                    (g.get("performans_test") or {}).items()
                    if k not in ("ornekler", "son_ornek")}),
            }
        return paket
