# -*- coding: utf-8 -*-
"""DronYoneticisi: MAVLink baglantisi, dron telemetri okuma ve komutlari.

Seri port uzerinden MAVLink dinler (ayri thread), dron telemetrisini
paylasilan sozlukte tutar ve arayuzden gelen komutlari (arm/disarm,
takeoff/land, rtl, auto, irtifa degistirme, goto) drona iletir.
"""
import math
import os
import queue as _queue
import socket
import threading
import time

import json
from pymavlink import mavutil
from .sabitler import DRON_DOSYASI

TAKEOFF_IRTIFA = 10.0  # metre (varsayilan takeoff irtifasi)

# ---------------------------------------------------------------------
# v2.4.19: ARM CHECK sabitleri
# ---------------------------------------------------------------------
MESAJ_LIMIT = 200      # dron basina tutulan STATUSTEXT mesaj sayisi
# v2.4.45: dron basina tutulan haberlesme konsolu satir sayisi. Bu tampon
# panel kapaliyken de dolar; kullanici konsolu actiginda gecmis hazir olur.
# 200 x ~120 bayt = ~24 KB/dron; 20 dronda ~0.5 MB — kabul edilebilir.
KONSOL_LIMIT = 200

# MAV_SYS_STATUS_SENSOR bit maskeleri (SYS_STATUS mesaji)
SENSOR_GYRO = 0x01            # 3D jiroskop
SENSOR_ACCEL = 0x02           # 3D ivmeolcer
SENSOR_MAG = 0x04             # 3D pusula
SENSOR_BARO = 0x08            # mutlak basinc (barometre)
SENSOR_GPS = 0x20             # GPS
SENSOR_RC = 0x10000           # RC alici
SENSOR_AHRS = 0x200000        # AHRS / tutum kestirimi
SENSOR_TERRAIN = 0x400000     # arazi verisi
SENSOR_BATTERY = 0x2000000    # batarya izleme
SENSOR_PREARM = 0x10000000    # MAV_SYS_STATUS_PREARM_CHECK
# v2.4.37: ARM CHECK maddesi olarak KULLANILMIYOR. ArduPilot bu biti
# yaymaz; madde her dronda kalici "uyari" uretiyordu. Sabit, ileride
# biti gercekten yayan VTOL/ozel yazilim destegi icin korunuyor.
SENSOR_PROPULSION = 0x20000000  # itki sistemi (ArduPilot yaymaz)

# EKF_STATUS_FLAGS (EKF_STATUS_REPORT.flags)
EKF_ATTITUDE = 1
EKF_VELOCITY_HORIZ = 2
EKF_VELOCITY_VERT = 4
EKF_POS_HORIZ_REL = 8
EKF_POS_HORIZ_ABS = 16
EKF_POS_VERT_ABS = 32
EKF_POS_VERT_AGL = 64
EKF_CONST_POS_MODE = 128
EKF_PRED_POS_HORIZ_REL = 256
EKF_PRED_POS_HORIZ_ABS = 512
EKF_UNINITIALIZED = 1024

# ---------------------------------------------------------------------
# v2.4.33: KOMUT SONUCU (COMMAND_ACK) SABITLERI
# ---------------------------------------------------------------------
# Kullanici bir komut verdiginde (takeoff, arm, land...) ucus kontrolcusu
# COMMAND_ACK dondurur. v2.4.32 ve oncesinde bu mesaj hic okunmuyordu;
# komut yollanir yollanmaz "basari" yaziliyordu. Artik gercek sonuc
# okunup, reddedilmisse GEREKCESIYLE bildirime dusuruluyor.
MAV_RESULT_ACCEPTED = 0
MAV_RESULT_TEMPORARILY_REJECTED = 1
MAV_RESULT_DENIED = 2
MAV_RESULT_UNSUPPORTED = 3
MAV_RESULT_FAILED = 4
MAV_RESULT_IN_PROGRESS = 5
MAV_RESULT_CANCELLED = 6

# MAV_RESULT -> kullaniciya gosterilecek Turkce gerekce
MAV_RESULT_ADLARI = {
    MAV_RESULT_ACCEPTED: "kabul edildi",
    MAV_RESULT_TEMPORARILY_REJECTED:
        "gecici olarak reddedildi (arac su an bu komutu alamiyor)",
    MAV_RESULT_DENIED:
        "reddedildi (komut veya parametre bu araca uygun degil)",
    MAV_RESULT_UNSUPPORTED:
        "desteklenmiyor (ucus yazilimi bu komutu tanimiyor)",
    MAV_RESULT_FAILED:
        "yurutulemedi (on kosullar saglanmadi)",
    MAV_RESULT_CANCELLED: "iptal edildi",
}

# Bildirime dusurulecek komutlar. Yalnizca KULLANICININ tetikledigi
# komutlar burada listelenir; parametre/gorev protokolu sirasinda olusan
# COMMAND_ACK'ler bildirim olarak anlamsizdir ve ekrani doldurur.
KOMUT_ADLARI = {
    22:  "KALKIS (TAKEOFF)",           # MAV_CMD_NAV_TAKEOFF
    21:  "INIS (LAND)",                # MAV_CMD_NAV_LAND
    20:  "EVE DON (RTL)",              # MAV_CMD_NAV_RETURN_TO_LAUNCH
    400: "ARM / DISARM",               # MAV_CMD_COMPONENT_ARM_DISARM
    176: "MOD DEGISTIRME",             # MAV_CMD_DO_SET_MODE
    252: "IRTIFA DEGISTIRME",          # MAV_CMD_DO_CHANGE_ALTITUDE
    178: "HIZ DEGISTIRME",             # MAV_CMD_DO_CHANGE_SPEED
    192: "KONUMA GIT (REPOSITION)",    # MAV_CMD_DO_REPOSITION
    16:  "NOKTAYA GIT (WAYPOINT)",     # MAV_CMD_NAV_WAYPOINT
    300: "GOREVI BASLAT",              # MAV_CMD_MISSION_START
    241: "KALIBRASYON",                # MAV_CMD_PREFLIGHT_CALIBRATION
    246: "YENIDEN BASLATMA",           # MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN
}


class DronYoneticisi:

    def __init__(self, konsol, ayarlar, kilit):
        """
        konsol : KonsolLog
        ayarlar: AyarYoneticisi (sysid tipi cozumleme icin)
        kilit  : paylasilan threading.Lock (dronlar/seri_durum erisimi)
        """
        self.konsol = konsol
        self.ayarlar = ayarlar
        self.kilit = kilit
        self.dronlar = {}          # sysid -> telemetri
        # Coklu baglanti: bid -> calisma durumu
        # {"master", "thread", "durdur", "durum", "hata", "isim", "tur"}
        self.baglantilar = {}
        self.sysid_baglanti = {}   # sysid -> bid (dronun geldigi kaynak)
        # Angajman yoneticisi baglanti kesilirken bilgilendirilir
        self.kes_kancasi = None    # cagrilabilir; durdur() icinde tetiklenir
        # Gorev yoneticisi MISSION_* mesajlarini almak icin baglanir
        self.gorev_kancasi = None  # cagrilabilir(msg); _dongu icinde
        # UDP yayin koprusu (UdpYayinYoneticisi) — her ham paket iletilir
        self.udp_yayin = None      # main.py kurulumda atar
        # Kayitli dron isimleri (UID -> isim)
        self.kayitli_dronlar = self._dron_kayitlari_yukle()
        # UID isteme durumu (sysid -> True/False)
        self._uid_istenen = {}
        # Thread-safe parametre okuma: param_ara aktifken kuyruk acilir
        self._param_kuyruk = {}   # sysid -> queue.Queue
        self._param_kilit = threading.Lock()
        # Thread-safe log protokolu: log_listesi/log_indir aktifken kuyruk
        self._log_kuyruk = {}     # sysid -> queue.Queue (LOG_ENTRY/LOG_DATA)
        self._log_kilit = threading.Lock()
        # v2.4.23: kullanici indirmeyi durdurabilir (log_indir_iptal)
        self._log_iptal = set()   # iptal istenen sysid'ler
        # Devam eden log indirme ilerlemesi (WS yayini icin)
        self.log_ilerleme = {}    # sysid -> {"log_id","alinan","toplam","durum"}
        # Kullanicinin verdigi son irtifa hedefi (sysid -> REL m).
        # goto komutlari bunu kullanir; boylece konum degisikligi devam
        # eden tirmanis/alcalmayi iptal etmez. RTL/LAND/DISARM'da silinir.
        self.hedef_irtifa_rel = {}
        # v2.4.19: dronun STATUSTEXT mesaj tamponu (ARM CHECK paneli).
        # sysid -> [{"ts", "sev", "metin"}] (en yeni sonda, MESAJ_LIMIT)
        self.mesajlar = {}
        self._mesaj_kilit = threading.Lock()
        # ------------------------------------------------------------------
        # v2.4.45: DRON BASINA HABERLESME KONSOLU
        # ------------------------------------------------------------------
        # Onceki surumlerde her dronun MAVLink/KOMUT/KALIB satiri GENEL
        # konsola yaziliyordu. Birden fazla dron baglandiginda genel konsol
        # okunamaz hale geliyor ve hangi satirin hangi drona ait oldugu
        # kayboluyordu. Artik bu satirlar dronun KENDI tamponuna yazilir ve
        # arayuzde dron kartinin altindaki acilir kapanir konsolda gosterilir.
        #
        # Tampon panel KAPALIYKEN de dolar; kullanici konsolu actiginda
        # gecmis hazir olur (halka tampon, KONSOL_LIMIT satir).
        self.dron_konsol = {}      # sysid -> [{"ts","etiket","metin","sev"}]
        self._dkonsol_kilit = threading.Lock()
        # Yeni satirlari arayuze ileten geri cagirma; sunucu.py atar.
        # Imza: kanca(sysid, kayit_sozlugu)
        self.konsol_kancasi = None
        # --------------------------------------------------------------
        # v2.4.21: kalici dron kimligi + baglanti oturumu
        # --------------------------------------------------------------
        self.dron_db_id = {}       # sysid -> dronlar.id (INTEGER)
        self.oturum_id = {}        # sysid -> dron_oturumlari.id
        self._ilk_gorulme = {}     # sysid -> ilk mesaj zamani (UID bekleme)
        self._kimlik_kilit = threading.Lock()
        # Takeoff, GUIDED/ARM telemetrisi gelmeden ikinci kez tetiklenmemeli.
        # sysid bazli tablo, ayni butona tekrar basildiginda MAVLink komut
        # firtinasi olusmasini engeller; uzun beklemeler WS isleyicisini
        # degil bu arka plan is parcacigini etkiler.
        self._kalkis_islemleri = set()
        self._kalkis_kilit = threading.Lock()
        # Aktif pilot bilgisini saglayan geri cagirma; sunucu.py atar.
        # Donus: {"eposta": ..., "isim": ..., "pilotlar": [eposta, ...]}
        self.pilot_saglayici = None

    # ------------------------------------------------------------------
    # Geriye uyumluluk: tekil master erisimi
    # ------------------------------------------------------------------
    @property
    def master(self):
        """Ilk aktif baglantinin master'i (geriye uyumluluk)."""
        for c in list(self.baglantilar.values()):
            if c.get("durum") == "bagli" and c.get("master") is not None:
                return c["master"]
        return None

    def master_bul(self, sysid):
        """sysid'nin telemetrisinin geldigi baglantinin master'i.

        Bulunamazsa herhangi bir aktif master'a duser.
        """
        bid = self.sysid_baglanti.get(int(sysid))
        if bid is not None:
            c = self.baglantilar.get(bid)
            if c and c.get("master") is not None:
                return c["master"]
        return self.master

    # ------------------------------------------------------------------
    # Kayitli dron isimleri (UID bazli)
    # ------------------------------------------------------------------
    @staticmethod
    def _dron_kayitlari_yukle():
        """Kayitli dronlari SQLite'tan yukler (v2.3.0).
        Format: {"uid_string": {"isim": "...", "sysid": N, ...}, ...}
        Eski gcs_dronlar.json varsa tek seferlik aktarilir ve
        .eski uzantisiyla devre disi birakilir.
        """
        from . import veritabani
        veritabani.tablolari_olustur()
        # Tek seferlik JSON goc
        if os.path.isfile(DRON_DOSYASI):
            try:
                with open(DRON_DOSYASI, "r", encoding="utf-8") as f:
                    eski = json.load(f)
            except (OSError, json.JSONDecodeError):
                eski = {}
            if eski:
                with veritabani.baglanti() as con:
                    mevcut = con.execute(
                        "SELECT COUNT(*) AS n FROM dron_kayitlari"
                    ).fetchone()["n"]
                    if mevcut == 0:
                        for uid, veri in eski.items():
                            con.execute(
                                "INSERT OR REPLACE INTO dron_kayitlari"
                                " (uid, veri) VALUES (?,?)",
                                (str(uid),
                                 json.dumps(veri, ensure_ascii=False)))
            try:
                os.replace(DRON_DOSYASI, DRON_DOSYASI + ".eski")
            except OSError:
                pass
        kayitlar = {}
        try:
            with veritabani.baglanti() as con:
                for r in con.execute(
                        "SELECT uid, veri FROM dron_kayitlari"):
                    try:
                        kayitlar[r["uid"]] = json.loads(r["veri"])
                    except (ValueError, TypeError):
                        pass
        except Exception:
            pass
        return kayitlar

    def _dron_kayitlari_kaydet(self):
        """Kayitli dronlari SQLite'a yazar (v2.3.0)."""
        from . import veritabani
        with veritabani.baglanti() as con:
            for uid, veri in self.kayitli_dronlar.items():
                con.execute(
                    "INSERT OR REPLACE INTO dron_kayitlari (uid, veri)"
                    " VALUES (?,?)",
                    (str(uid), json.dumps(veri, ensure_ascii=False)))

    def dron_isim_kaydet(self, sysid, isim):
        """Belirtilen sysid'nin UID'sine isim ata ve kaydet.
        UID henuz alinmadiysa sysid'yi anahtar olarak kullan.
        """
        d = self.dronlar.get(sysid)
        uid = str(d.get("uid", sysid)) if d else str(sysid)
        self.kayitli_dronlar[uid] = {
            "isim": isim,
            "sysid": sysid,
            "uid": uid
        }
        # Canli dron kaydindaki ismi de guncelle
        if d:
            d["kullanici_isim"] = isim
        self._dron_kayitlari_kaydet()
        # v2.4.21: kalici dron kaydinda da ismi guncelle
        dron_id = self.dron_db_id.get(sysid)
        if dron_id:
            try:
                from . import veritabani as _vt
                _vt.dron_alan_guncelle(dron_id, isim=isim)
            except Exception:
                pass
        self.dkonsol(sysid, "DRON", f"uid={uid} isim='{isim}' kaydedildi.")

    # ------------------------------------------------------------------
    # v2.4.21: Kalici dron kimligi (dronlar tablosu) + oturum
    # ------------------------------------------------------------------
    # UID kaynak onceligi:
    #   autopilot_uid : AUTOPILOT_VERSION.uid (donanim seri)
    #   uid2          : AUTOPILOT_VERSION.uid2 (8 bayt LE)
    #   dji_sn        : DJI urun seri numarasi
    #   turetilmis    : 'fp:<sha1>' parmak izi (UID hic gelmezse)
    # v2.4.22: sure 6 -> 20 s. AUTOPILOT_VERSION cevabi gecikirse
    # turetilmis kimligin gercek UID'yi gecmesi ve ayni arac icin ikinci
    # kayit acilmasi engellenir.
    UID_BEKLEME = 20.0  # s; bu sureden sonra turetilmis kimlik uretilir

    @staticmethod
    def _parmak_izi(d):
        """UID gelmeyen araclar icin kararli turetilmis kimlik.

        Otopilot/arac tipi/firmware/sysid birlesiminden SHA-1 alinir.
        Ayni fiziksel arac ayni degeri uretir; farkli sysid farkli kayit.
        """
        import hashlib
        ham = "|".join([
            str(d.get("otopilot", "") or ""),
            str(d.get("arac_tipi", 0) or 0),
            str(d.get("firmware", "") or ""),
            str(d.get("sysid", 0) or 0),
        ])
        return "fp:" + hashlib.sha1(ham.encode("utf-8")).hexdigest()[:12]

    def _pilot_al(self):
        """Aktif pilot bilgisini dondurur: (eposta, isim, pilot_listesi)."""
        if not self.pilot_saglayici:
            return "", "", []
        try:
            p = self.pilot_saglayici() or {}
        except Exception:
            return "", "", []
        return (str(p.get("eposta", "") or ""),
                str(p.get("isim", "") or ""),
                list(p.get("pilotlar") or []))

    def _firma_al(self):
        """v2.4.54: aktif oturumun firma_id'sini dondurur (yoksa None).

        Merkezde calisan ornek cok firmalidir; dron kimlik kaydinin
        sahipligi bu degerle yazilir. Lokal kurulumda `None` doner ve
        davranis degismez.
        """
        if not self.pilot_saglayici:
            return None
        try:
            p = self.pilot_saglayici() or {}
            fid = p.get("firma_id")
            return int(fid) if fid else None
        except (TypeError, ValueError):
            return None
        except Exception:
            return None

    def kimlik_kaydet(self, sysid, uid, uid_kaynak="turetilmis"):
        """v2.4.21: Dronu `dronlar` tablosuna kaydeder (idempotent).

        Daha once kayitliysa yalnizca `son_gorulme_ts`/sysid tazelenir;
        ilk kayit tarihi ve kaydeden pilot DEGISMEZ. Kayit sonrasi bu
        dron icin bir baglanti oturumu acilir (telemetri buna baglanir).

        Donus: dron_id (INTEGER) veya None
        """
        from . import veritabani as _vt
        uid = str(uid or "").strip()
        if not uid:
            return None
        with self._kimlik_kilit:
            mevcut = self.dron_db_id.get(sysid)
            if mevcut:
                # v2.4.22: Kayit turetilmis kimlikle acilmissa ve simdi
                # gercek donanim UID'si geldiyse kaydi YUKSELT/BIRLESTIR.
                if uid_kaynak == "turetilmis":
                    return mevcut
                return self._kimlik_yukselt(sysid, mevcut, uid, uid_kaynak)
            d = self.dronlar.get(sysid) or {}
            eposta, isim, pilotlar = self._pilot_al()
            renk = ""
            ug = getattr(self, "ucus_gecmisi", None)
            if ug is not None:
                try:
                    renk = ug.renk_al(uid) or ""
                except Exception:
                    renk = ""
            try:
                dron_id, yeni = _vt.dron_kayit_al_veya_olustur(
                    uid, uid_kaynak=uid_kaynak,
                    isim=str(d.get("kullanici_isim") or d.get("isim") or ""),
                    sysid=int(sysid), arac_tipi=int(d.get("arac_tipi") or 0),
                    arac_sinifi=str(d.get("tip") or ""),
                    otopilot=str(d.get("otopilot") or ""),
                    firmware=str(d.get("firmware") or ""), renk=renk,
                    kaydeden_eposta=eposta, kaydeden_isim=isim,
                    firma_id=self._firma_al())
            except Exception as e:
                self.dkonsol(sysid, "DRON", f"kimlik kaydi "
                            f"yazilamadi: {e}", "hata")
                return None
            if not dron_id:
                return None
            self.dron_db_id[sysid] = dron_id
            # Kayitli isim/renk varsa canli kayda uygula
            try:
                kayit = _vt.dron_kaydi_oku(dron_id=dron_id) or {}
                if kayit.get("isim") and not d.get("kullanici_isim"):
                    d["kullanici_isim"] = kayit["isim"]
            except Exception:
                pass
            if yeni:
                self.konsol("DRON", f"YENI dron kaydi: #{dron_id} "
                            f"uid={uid} ({uid_kaynak}) sysid={sysid}"
                            + (f" - kaydeden: {eposta}" if eposta else ""),
                            "basari")
            else:
                self.konsol("DRON", f"Kayitli dron tanindi: #{dron_id} "
                            f"uid={uid} sysid={sysid}")
            # Baglanti oturumu ac
            try:
                bid = self.sysid_baglanti.get(int(sysid))
                oid = _vt.oturum_baslat(
                    dron_id, sysid=int(sysid), baglanti_id=bid,
                    pilot_eposta=eposta, pilot_isim=isim,
                    pilotlar=pilotlar)
                self.oturum_id[sysid] = oid
            except Exception as e:
                self.dkonsol(sysid, "DRON", f"oturum acilamadi: {e}",
                            "hata")
            return dron_id

    def _kimlik_yukselt(self, sysid, mevcut_id, uid, uid_kaynak):
        """v2.4.22: Turetilmis kimlikle acilmis kaydi gercek UID'ye tasir.

        `kimlik_kaydet` icinden (kilit altinda) cagrilir. Kayit zaten
        gercek UID ile acildiysa hicbir sey yapmaz.
        """
        from . import veritabani as _vt
        try:
            kayit = _vt.dron_kaydi_oku(dron_id=mevcut_id) or {}
        except Exception:
            return mevcut_id
        eski_uid = str(kayit.get("uid") or "")
        eski_kaynak = str(kayit.get("uid_kaynak") or "")
        if eski_uid == uid:
            return mevcut_id
        if eski_kaynak != "turetilmis" and not eski_uid.startswith("fp:"):
            # Kayit zaten gercek bir UID'ye bagli; dokunma
            return mevcut_id
        try:
            hedef_id, islem = _vt.dron_kimlik_yukselt(
                mevcut_id, uid, uid_kaynak)
        except Exception as e:
            self.dkonsol(sysid, "DRON", f"kimlik yukseltme hatasi: {e}",
                        "hata")
            return mevcut_id
        if not hedef_id:
            return mevcut_id
        self.dron_db_id[sysid] = hedef_id
        # Acik oturumu yeni kayda tasi (telemetri kesintiye ugramaz)
        oid = self.oturum_id.get(sysid)
        if oid and hedef_id != mevcut_id:
            try:
                _vt.oturum_dron_tasi(oid, hedef_id)
            except Exception:
                pass
        if islem == "yukseltildi":
            self.konsol("DRON", f"Dron kimligi yukseltildi: #{hedef_id} "
                        f"{eski_uid} -> {uid} ({uid_kaynak})", "basari")
        elif islem == "birlestirildi":
            self.konsol("DRON", f"Mukerrer dron kaydi birlestirildi: "
                        f"{eski_uid} -> #{hedef_id} uid={uid}", "basari")
        # Kayitli isim/renk varsa canli kayda uygula
        try:
            d = self.dronlar.get(sysid)
            yeni_kayit = _vt.dron_kaydi_oku(dron_id=hedef_id) or {}
            if d is not None and yeni_kayit.get("isim"):
                d["kullanici_isim"] = yeni_kayit["isim"]
        except Exception:
            pass
        return hedef_id

    def kimlik_denetim(self, sysid, simdi=None):
        """UID beklemesi asildiysa turetilmis kimlikle kayit yapar.

        `_dongu` icinden her HEARTBEAT'te cagrilir; kaydi olan dronlar
        icin hizli doner.
        """
        if self.dron_db_id.get(sysid):
            return self.dron_db_id[sysid]
        d = self.dronlar.get(sysid)
        if not d:
            return None
        simdi = simdi or time.time()
        ilk = self._ilk_gorulme.get(sysid)
        if ilk is None:
            self._ilk_gorulme[sysid] = simdi
            return None
        if (simdi - ilk) < self.UID_BEKLEME:
            return None
        uid = self._parmak_izi(d)
        d["uid"] = d.get("uid") or uid
        return self.kimlik_kaydet(sysid, uid, "turetilmis")

    def oturum_kapat(self, sysid):
        """Dronun aktif baglanti oturumunu kapatir (telemetri son bulur)."""
        from . import veritabani as _vt
        oid = self.oturum_id.pop(sysid, None)
        self.dron_db_id.pop(sysid, None)
        self._ilk_gorulme.pop(sysid, None)
        self._uid_istenen.pop(sysid, None)  # v2.4.22: yeniden istenebilsin
        if not oid:
            return
        _, _, pilotlar = self._pilot_al()
        try:
            _vt.oturum_bitir(oid, pilotlar=pilotlar or None)
        except Exception:
            pass

    def _uid_ile_isim_coz(self, sysid, uid):
        """UID ile kayitli isim varsa dondur, yoksa None."""
        kayit = self.kayitli_dronlar.get(str(uid))
        if kayit:
            return kayit.get("isim")
        # sysid ile de dene (UID alinmadan kaydedilmis olabilir)
        kayit = self.kayitli_dronlar.get(str(sysid))
        if kayit:
            return kayit.get("isim")
        return None

    # ------------------------------------------------------------------
    # Yardimcilar
    # ------------------------------------------------------------------
    def dron_kaydi_olustur(self, sysid):
        tip = self.ayarlar.sysid_tipi(sysid)
        return {
            "sysid": sysid,
            "tip": tip or "BILINMEYEN",
            "isim": f"{tip}-{sysid}" if tip else f"DRON-{sysid}",
            "uid": "",             # donanımsal UID (AUTOPILOT_VERSION'dan)
            "kullanici_isim": "",  # kullanici tarafindan verilen isim
            "lat": None, "lon": None,
            "alt_msl": 0.0, "alt_rel": 0.0,
            "heading": 0.0,
            # IS97: hareketli kamera angajmani heartbeat zamanina
            # guvenemez. Konum ve tutum mesajlarinin kendi zamanlari
            # ayrica izlenir; biri durursa hedef konumu kilitlenir.
            "poz_ts": 0.0, "tutum_ts": 0.0,
            "groundspeed": 0.0, "airspeed": 0.0,
            "vz": 0.0,
            # v2.4.43: YATAY hiz vektoru (m/s, NED: kuzey / dogu).
            # GLOBAL_POSITION_INT bu iki alani ZATEN tasiyordu; kod yalniz
            # vz'yi okuyordu. Ek MAVLink istegi GEREKMEZ.
            # Angajman ongorusu icin heading+groundspeed ciftinden daha
            # guvenilir: heading BURUN yonudur, ruzgar altinda gercek
            # hareket yonunden saparken vx/vy gercek yer hizi vektorudur.
            "vx": 0.0,
            "vy": 0.0,
            "roll": 0.0, "pitch": 0.0,
            "batarya_v": 0.0, "batarya_pct": -1,
            "gps_fix": 0, "uydu": 0,
            "mod": "?", "armed": False,
            "arac_tipi": 0,        # MAV_TYPE (1=plane, 2=quad, 4=heli...)
            # v2.4.21: kalici kimlik kaydinda saklanan tanimlayicilar
            "otopilot": "",        # MAV_AUTOPILOT adi (ArduPilot/PX4...)
            "firmware": "",        # AUTOPILOT_VERSION.flight_sw_version
            "udp_port": None,      # 9000+sysid MAVLink yayin portu
            "udp_ip": "",          # v2.4.39: LAN'dan erisilebilir adres
            "mission_seq": -1,
            "son_mesaj": 0.0,
            # v2.4.19: ARM CHECK / "Ucusa Hazir" gostergesi verileri
            # SYS_STATUS sensor bit maskeleri (MAV_SYS_STATUS_SENSOR)
            "sensor_mevcut": 0,     # onboard_control_sensors_present
            "sensor_etkin": 0,      # onboard_control_sensors_enabled
            "sensor_saglik": 0,     # onboard_control_sensors_health
            "ekf_bayrak": 0,        # EKF_STATUS_REPORT.flags
            "ekf_hiz_var": 0.0,     # velocity_variance
            "ekf_konum_var": 0.0,   # pos_horiz_variance
            "ekf_yuk_var": 0.0,     # pos_vert_variance
            "ekf_pusula_var": 0.0,  # compass_variance
            "prearm_hata": "",      # son PreArm/ARM reddi metni
            "prearm_ani": 0.0,      # o metnin alinma zamani
            "arm_edilebilir": None,  # PREARM_CHECK bitinden (bilinmiyor=None)
            "sistem_durum": 0,      # MAV_STATE (3=standby, 4=active, 5/6=hata)
            "titresim": None,       # VIBRATION en buyuk eksen (m/s^2)
            "kalkis_kilit": None,   # Safety switch / motor interlock
            # v2.4.42: HOME (kalkis/donus) noktasi - HOME_POSITION (242)
            # None = otopilot henuz bildirmedi. home_ts=0 ile birlikte
            # "bilinmiyor" ile "atanmamis" ayirt edilir: ilk baglanti
            # saniyelerinde mesaj gelmemis olabilir, bu bir ariza degildir.
            "home_lat": None,
            "home_lon": None,
            "home_alt": None,       # AMSL (m)
            "home_ts": 0.0,         # HOME_POSITION alinma zamani
            # v2.5.0: YAKINLIK ALGILAYICISI (proximity)
            # DISTANCE_SENSOR (132) mesajlari yon basina toplanir.
            # Anahtar = MAV_SENSOR_ORIENTATION degeri (int):
            #   0=ileri 1=ileri-sag 2=sag 3=arka-sag 4=arka
            #   5=arka-sol 6=sol 7=ileri-sol 24=yukari 25=asagi
            # Deger = {"mesafe": m, "min": m, "max": m, "ts": epoch}
            # Arayuz 3 s'den eski yonu GOSTERMEZ (bayat kalkan yanlis
            # guven verir).
            "prx_yonler": {},
            "prx_ts": 0.0,          # son DISTANCE_SENSOR anı
            # v2.5.0: pusula kalibrasyon raporunun TAM alanlari
            # (fitness, ofset, diagonal). Onceki surum yalniz
            # cal_status okuyordu; operator "tum degerleri gorsun"
            # istegi bunu gerektirir.
            "magkal_rapor": None,
            # v2.5.0: motor testi bitis ani (arayuz gostergesi).
            # 0 = test yok.
            "motor_test_bitis": 0.0,
        }

    @staticmethod
    def portlari_listele():
        """Sistemdeki seri portlari dondurur (pyserial gerektirir)."""
        try:
            from serial.tools import list_ports
        except ImportError:
            return [{"port": "", "aciklama":
                     "pyserial kurulu degil -> pip install pyserial"}]
        try:
            return [{"port": p.device, "aciklama": p.description or ""}
                    for p in list_ports.comports()]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Baglanti yonetimi (coklu)
    # ------------------------------------------------------------------
    def dinle(self, kayit, url):
        """Kayitli baglantiyi dinlemeye baslar (play).

        kayit: BaglantiYoneticisi kaydi (id, isim, tur, ...)
        url  : mavutil baglanti dizesi
        """
        bid = int(kayit["id"])
        self.durdur(bid)  # ayni kayit zaten dinleniyorsa yeniden baslat
        durdur = threading.Event()
        c = {"master": None, "thread": None, "durdur": durdur,
             "durum": "baglaniyor", "hata": "",
             "isim": kayit.get("isim", "?"), "tur": kayit.get("tur", "?")}
        with self.kilit:
            self.baglantilar[bid] = c
        t = threading.Thread(
            target=self._dongu_sarmal,
            args=(bid, url, kayit.get("baud", 57600), durdur), daemon=True)
        c["thread"] = t
        t.start()

    def durdur(self, bid):
        """Belirtilen baglantiyi durdurur (stop)."""
        bid = int(bid)
        c = self.baglantilar.get(bid)
        if not c:
            return
        t = c.get("thread")
        c["durdur"].set()
        if t and t.is_alive():
            t.join(timeout=3.0)
        with self.kilit:
            self.baglantilar.pop(bid, None)
            # Bu kaynaktan gelen dronlari temizle
            silinecek = [s for s, b in self.sysid_baglanti.items()
                         if b == bid]
            for s in silinecek:
                self.sysid_baglanti.pop(s, None)
                self.dronlar.pop(s, None)
        # v2.4.21: dusen dronlarin baglanti oturumlarini kapat
        for s in silinecek:
            try:
                self.oturum_kapat(s)
            except Exception:
                pass
        # Dusen dronlarin UDP yayin koprulerini kapat
        if self.udp_yayin:
            for s in silinecek:
                try:
                    self.udp_yayin.dron_sil(s)
                except Exception:
                    pass
        # Hicbir aktif baglanti kalmadiysa angajman kancasini tetikle
        if not self.baglantilar and self.kes_kancasi:
            self.kes_kancasi()

    def tumunu_durdur(self):
        for bid in list(self.baglantilar.keys()):
            self.durdur(bid)

    def durumlar(self):
        """WS yayini icin baglanti durum ozetleri: bid -> durum."""
        with self.kilit:
            return {str(bid): {"durum": c.get("durum", "kapali"),
                               "hata": c.get("hata", "")}
                    for bid, c in self.baglantilar.items()}

    # ------------------------------------------------------------------
    # v2.4.19: STATUSTEXT mesaj tamponu (ARM CHECK / hata mesajlari paneli)
    # ------------------------------------------------------------------
    def _mesaj_ekle(self, sysid, metin, sev):
        """Dronun STATUSTEXT mesajini tampona yazar (en yeni sonda)."""
        kayit = {"ts": time.time(), "sev": int(sev), "metin": metin}
        with self._mesaj_kilit:
            liste = self.mesajlar.setdefault(sysid, [])
            # Ayni metin ust uste tekrarliyorsa sayaci artir (spam onleme)
            if liste and liste[-1]["metin"] == metin:
                liste[-1]["ts"] = kayit["ts"]
                liste[-1]["tekrar"] = liste[-1].get("tekrar", 1) + 1
                return
            liste.append(kayit)
            if len(liste) > MESAJ_LIMIT:
                del liste[:len(liste) - MESAJ_LIMIT]

    # ------------------------------------------------------------------
    # v2.4.45: DRON BASINA HABERLESME KONSOLU
    # ------------------------------------------------------------------
    def dkonsol(self, sysid, etiket, metin, sev="bilgi"):
        """Satiri DRONUN kendi konsol tamponuna yazar (genel konsola YAZMAZ).

        sysid  : dronun MAVLink sistem kimligi (int)
        etiket : MAVLINK | KOMUT | KALIB | TEL | GOREV ...
        metin  : ciplak satir metni
        sev    : bilgi | basari | uyari | hata

        Ayni metin ust uste tekrarliyorsa yeni satir eklenmez, son satirin
        `tekrar` sayaci artirilir. Boylece saniyede onlarca kez yinelenen
        MAVLink uyarilari konsolu bogmaz.
        """
        try:
            sysid = int(sysid)
        except (TypeError, ValueError):
            return
        kayit = {"ts": time.time(), "etiket": str(etiket),
                 "metin": str(metin), "sev": str(sev)}
        yeni = True
        with self._dkonsol_kilit:
            liste = self.dron_konsol.setdefault(sysid, [])
            if (liste and liste[-1]["metin"] == kayit["metin"]
                    and liste[-1]["etiket"] == kayit["etiket"]):
                liste[-1]["ts"] = kayit["ts"]
                liste[-1]["tekrar"] = liste[-1].get("tekrar", 1) + 1
                kayit = dict(liste[-1])
                yeni = False
            else:
                liste.append(kayit)
                if len(liste) > KONSOL_LIMIT:
                    del liste[:len(liste) - KONSOL_LIMIT]
            kayit = dict(kayit)
        kayit["yeni"] = yeni
        kanca = self.konsol_kancasi
        if callable(kanca):
            try:
                kanca(sysid, kayit)
            except Exception:
                pass          # arayuze iletim basarisiz olsa da tampon dolar

    def konsol_gecmis(self, sysid, adet=None):
        """Dronun konsol tamponunu dondurur (en yeni sonda)."""
        try:
            sysid = int(sysid)
        except (TypeError, ValueError):
            return []
        with self._dkonsol_kilit:
            liste = list(self.dron_konsol.get(sysid, []))
        if adet:
            liste = liste[-int(adet):]
        return liste

    def konsol_temizle(self, sysid):
        """Dronun konsol tamponunu bosaltir."""
        try:
            sysid = int(sysid)
        except (TypeError, ValueError):
            return
        with self._dkonsol_kilit:
            self.dron_konsol.pop(sysid, None)

    # ------------------------------------------------------------------
    # v2.4.33: KOMUT SONUCU (COMMAND_ACK) ISLEME
    # ------------------------------------------------------------------
    # Kullanici bir komut (takeoff, arm, land, RTL...) verdiginde ucus
    # kontrolcusu her zaman bir COMMAND_ACK dondurur. Bu mesaj v2.4.32
    # ve oncesinde HIC okunmuyordu; komut gonderilir gonderilmez konsola
    # "basari" yaziliyordu. Dolayisiyla "takeoff'a bastim, olmadi" gibi
    # durumlarda arayuzde hicbir gerekce gorunmuyordu.
    #
    # Bu metot ACK'i okunur bir cumleye cevirip konsola HATA seviyesiyle
    # yazar. Istemci tarafinda `js/konsol.js` icindeki bildirim koprusu
    # hata/uyari seviyeli her satiri sag ust kosede toast olarak gosterir,
    # boylece gerekce dogrudan ekrana duser.
    def _komut_ack_isle(self, sysid, d, msg):
        try:
            komut_no = int(getattr(msg, "command", 0))
            sonuc = int(getattr(msg, "result", 0))
        except (TypeError, ValueError):
            return

        komut_ad = KOMUT_ADLARI.get(komut_no, f"CMD {komut_no}")

        # Yalnizca kullanicinin tetikledigi komutlari bildir. Ucus
        # kontrolcusu parametre/gorev protokolu sirasinda da COMMAND_ACK
        # uretir; bunlar bildirim olarak anlamsizdir ve ekrani doldurur.
        if komut_no not in KOMUT_ADLARI:
            return

        # IN_PROGRESS (5) bir ara durumdur, sonuc degildir: sessiz gec.
        if sonuc == MAV_RESULT_IN_PROGRESS:
            return

        if sonuc == MAV_RESULT_ACCEPTED:
            # v2.4.45: kabul satiri YALNIZ dronun kendi konsoluna dusuyor.
            # Genel konsola yazilmasi gereksizdi: her komutta bir satir
            # ekliyor ve coklu dronda genel konsolu okunamaz hale getiriyordu.
            self.dkonsol(sysid, "KOMUT",
                         f"{komut_ad} kabul edildi", "basari")
            return

        # --- Reddedildi: gerekce uret ---
        sonuc_ad = MAV_RESULT_ADLARI.get(sonuc, f"sonuc={sonuc}")
        parcalar = [f"[{sysid}] {komut_ad} BASARISIZ: {sonuc_ad}"]

        # FAILED/DENIED durumunda gercek sebep neredeyse her zaman son
        # PREARM/ARM STATUSTEXT mesajidir. Ucus kontrolcusu bunu ACK'ten
        # hemen once yayinlar, bu yuzden 15 sn'lik pencerede geceridir.
        prearm = d.get("prearm_hata")
        prearm_ani = d.get("prearm_ani") or 0
        if prearm and (time.time() - prearm_ani) < 15.0:
            parcalar.append(f"({prearm})")

        # v2.4.45: BASARISIZ satiri hem dronun konsoluna hem GENEL konsola
        # yazilir. Genel konsol gereklidir: `js/konsol.js` koprusu hata
        # seviyeli satirlari sag ust kosede toast olarak gosterir ve pilotun
        # "takeoff'a bastim olmadi" durumunda gerekceyi gormesi sarttir.
        self.dkonsol(sysid, "KOMUT", " ".join(parcalar), "hata")
        self.konsol("KOMUT", " ".join(parcalar), "hata")

        # ARM CHECK panelinde de gorunsun (severity 2 = CRITICAL)
        self._mesaj_ekle(sysid, " ".join(parcalar[0:]).strip(), 2)

    def mesaj_listesi(self, sysid, adet=MESAJ_LIMIT):
        """Dronun son mesajlarini dondurur (en yeni ustte)."""
        with self._mesaj_kilit:
            liste = list(self.mesajlar.get(int(sysid), []))
        return list(reversed(liste[-int(adet):]))

    def mesajlari_temizle(self, sysid):
        with self._mesaj_kilit:
            self.mesajlar.pop(int(sysid), None)

    # ------------------------------------------------------------------
    # v2.4.19: ARM CHECK — hazirlik raporu
    # ------------------------------------------------------------------
    def hazirlik_ozeti(self, d):
        """Telemetri paketine gomulen kisa hazirlik ozeti.

        Doner: {"hazir": bool|None, "kritik": int, "uyari": int,
                "sebep": "..."}
        """
        maddeler = self.hazirlik_maddeleri(d)
        kritik = [m for m in maddeler if m["durum"] == "hata"]
        uyari = [m for m in maddeler if m["durum"] == "uyari"]
        bilinmiyor = all(m["durum"] == "bilinmiyor" for m in maddeler)
        if bilinmiyor:
            hazir = None
        else:
            hazir = not kritik
        # v2.4.42: rozet ipucunda gosterilecek SEBEP, denetim listesiyle
        # ayni siraya gore secilir (oncelik kucuk olan one gelir).
        # Boylece "HAZIR DEGIL" rozetine bakan operator, paneli acinca
        # listenin basinda gordugu maddeyi ipucunda da okur; iki gosterge
        # farkli sebep bildirirse hangisine guvenecegini bilemezdi.
        kritik.sort(key=lambda x: int(x.get("oncelik", 50)))
        uyari.sort(key=lambda x: int(x.get("oncelik", 50)))
        sebep = ""
        if kritik:
            sebep = kritik[0]["mesaj"] or kritik[0]["ad"]
        elif uyari:
            sebep = uyari[0]["mesaj"] or uyari[0]["ad"]
        return {"hazir": hazir, "kritik": len(kritik),
                "uyari": len(uyari), "sebep": sebep}

    def hazirlik_maddeleri(self, d):
        """Dron telemetrisinden ARM CHECK madde listesi uretir.

        Her madde: {"anahtar", "ad", "durum", "deger", "mesaj", "grup"}
        durum: "tamam" | "uyari" | "hata" | "bilinmiyor"

        v2.4.42: maddeler istege bagli "oncelik" alani tasir (kucuk deger
        one gelir). Alan verilmeyen maddeler arayuzde 50 sayilir; HOME
        maddesi 0 tasidigi icin denetim listesinin EN BASINDA kalir.
        """
        m = []
        mevcut = int(d.get("sensor_mevcut") or 0)
        saglik = int(d.get("sensor_saglik") or 0)
        etkin = int(d.get("sensor_etkin") or 0)

        # --- HOME (kalkis/donus) noktasi --------------------------------
        # v2.4.42: HOME atanmamis arac UCUSA HAZIR SAYILMAZ. Gerekce:
        # RTL/FAILSAFE davranisi HOME'a doner; HOME yoksa arac ariza
        # aninda nereye donecegini bilmez. Bu yuzden durum "uyari" degil
        # "hata"dir: hazirlik_ozeti() yalnizca "hata" maddelerinde
        # hazir=False uretir (uyari rozeti yesil birakir, v2.4.35).
        _hlat = d.get("home_lat")
        _hlon = d.get("home_lon")
        _hts = float(d.get("home_ts") or 0)
        if _hlat is not None and _hlon is not None:
            _halt = d.get("home_alt")
            m.append({
                "anahtar": "home", "ad": "HOME (kalkış/dönüş) noktası",
                "durum": "tamam",
                "deger": f"{_hlat:.6f}, {_hlon:.6f}"
                         + (f" · {_halt:.0f} m" if _halt is not None else ""),
                "mesaj": "", "grup": "prearm", "oncelik": 0})
        elif _hts <= 0:
            # HOME_POSITION mesaji HIC gelmedi. Bu bir ariza DEGILDIR:
            # baglantinin ilk saniyelerinde veya mesaji yaymayan
            # firmware'de olagan. "hata" verilseydi her dron acilista
            # kirmizi yanar ve gercek arizayla karisirdi.
            m.append({
                "anahtar": "home", "ad": "HOME (kalkış/dönüş) noktası",
                "durum": "bilinmiyor", "deger": "bildirilmiyor",
                "mesaj": "", "grup": "prearm", "oncelik": 0})
        else:
            # Otopilot mesaji GONDERDI ama konum bos/0,0 idi: HOME
            # gercekten atanmamis.
            m.append({
                "anahtar": "home", "ad": "HOME (kalkış/dönüş) noktası",
                "durum": "hata", "deger": "atanmamış",
                "mesaj": "HOME noktası atanmamış — RTL/failsafe dönüş "
                         "konumu tanımsız",
                "grup": "prearm", "oncelik": 0})

        def sensor_madde(anahtar, ad, bit, grup="sensor", zorunlu=True):
            if not (mevcut & bit):
                m.append({"anahtar": anahtar, "ad": ad,
                          "durum": "bilinmiyor" if not mevcut else
                                   ("uyari" if zorunlu else "tamam"),
                          "deger": "yok", "mesaj": "", "grup": grup})
                return
            iyi = bool(saglik & bit)
            m.append({
                "anahtar": anahtar, "ad": ad,
                "durum": "tamam" if iyi else ("hata" if zorunlu
                                              else "uyari"),
                "deger": "sağlıklı" if iyi else "arızalı",
                "mesaj": "" if iyi else f"{ad} sağlıksız bildiriyor",
                "grup": grup,
                "etkin": bool(etkin & bit),
            })

        # --- Sensor sagligi (MAV_SYS_STATUS_SENSOR) ---
        sensor_madde("gyro", "Jiroskop (3D)", SENSOR_GYRO)
        sensor_madde("accel", "İvmeölçer (3D)", SENSOR_ACCEL)
        sensor_madde("mag", "Pusula (3D)", SENSOR_MAG)
        sensor_madde("baro", "Barometre", SENSOR_BARO)
        sensor_madde("gps", "GPS", SENSOR_GPS)
        sensor_madde("ahrs", "AHRS / Tutum çözümü", SENSOR_AHRS)
        sensor_madde("batarya", "Batarya izleme", SENSOR_BATTERY,
                     grup="guc")
        # v2.4.37: "Itki / Motor" maddesi KALDIRILDI.
        # ArduPilot, SYS_STATUS icindeki onboard_control_sensors_present
        # alaninda MAV_SYS_STATUS_SENSOR_PROPULSION (0x20000000) bitini
        # yaymaz; bit yalniz bazi ozel/VTOL uretici yazilimlarinda
        # kullanilir. Bit hic gelmedigi icin madde her dronda "yok" +
        # "uyari" uretiyordu ve bu, hazirlik_ozeti()'ndeki uyari sayisini
        # kalici olarak >0 tutuyordu. Sonuc: hicbir arac hic temiz yesil
        # gosterilemiyordu (v2.4.35 rozeti ve v2.4.36 baslik cercevesi
        # surekli amber kaliyordu) ve uyari isareti anlamsizlasiyordu.
        # Bit hic gelmedigi icin madde "saglikli/arizali" ayrimi da hic
        # uretmiyordu; yani hicbir kosulda bilgi tasimiyordu.
        # SENSOR_PROPULSION sabiti ileride VTOL destegi icin duruyor.
        sensor_madde("rc", "RC alıcı", SENSOR_RC, grup="rc",
                     zorunlu=False)

        # --- Otopilotun PREARM sonucu ---
        if mevcut & SENSOR_PREARM:
            prearm_ok = bool(saglik & SENSOR_PREARM)
            m.append({
                "anahtar": "prearm", "ad": "Otopilot ARM ön kontrolü",
                "durum": "tamam" if prearm_ok else "hata",
                "deger": "geçti" if prearm_ok else "reddedildi",
                "mesaj": "" if prearm_ok else (d.get("prearm_hata")
                                               or "Otopilot ARM'a izin "
                                                  "vermiyor"),
                "grup": "prearm"})
        else:
            m.append({
                "anahtar": "prearm", "ad": "Otopilot ARM ön kontrolü",
                "durum": "bilinmiyor", "deger": "bildirilmiyor",
                "mesaj": "", "grup": "prearm"})

        # --- GPS kalitesi ---
        fix = int(d.get("gps_fix") or 0)
        uydu = int(d.get("uydu") or 0)
        hdop = d.get("hdop")
        if fix >= 3:
            gps_durum = "tamam" if (uydu >= 8 and (hdop or 99) <= 1.5) \
                else "uyari"
            gps_msg = "" if gps_durum == "tamam" else (
                f"Uydu {uydu}, HDOP {hdop if hdop is not None else '?'} "
                "- konum hassasiyeti sınırlı")
        else:
            gps_durum = "hata"
            gps_msg = f"3D fix yok (fix tipi {fix})"
        m.append({"anahtar": "gps_kalite", "ad": "GPS kalitesi",
                  "durum": gps_durum,
                  "deger": f"fix {fix} · {uydu} uydu"
                           + (f" · HDOP {hdop}" if hdop is not None else ""),
                  "mesaj": gps_msg, "grup": "konum"})

        # --- EKF sagligi ---
        ekf = int(d.get("ekf_bayrak") or 0)
        if ekf:
            eksik = []
            if not (ekf & EKF_ATTITUDE):
                eksik.append("tutum")
            if not (ekf & EKF_VELOCITY_HORIZ):
                eksik.append("yatay hız")
            if not (ekf & EKF_POS_HORIZ_ABS):
                eksik.append("yatay konum")
            if not (ekf & EKF_POS_VERT_ABS):
                eksik.append("düşey konum")
            var_maks = max(float(d.get("ekf_hiz_var") or 0),
                           float(d.get("ekf_konum_var") or 0),
                           float(d.get("ekf_yuk_var") or 0),
                           float(d.get("ekf_pusula_var") or 0))
            if ekf & EKF_UNINITIALIZED:
                ekf_durum, ekf_msg = "hata", "EKF henüz başlatılmadı"
            elif eksik:
                ekf_durum = "hata"
                ekf_msg = "EKF çözümü eksik: " + ", ".join(eksik)
            elif ekf & EKF_CONST_POS_MODE:
                ekf_durum, ekf_msg = "uyari", "EKF sabit konum modunda"
            elif var_maks >= 0.8:
                ekf_durum = "uyari"
                ekf_msg = f"EKF varyansı yüksek ({var_maks:.2f})"
            else:
                ekf_durum, ekf_msg = "tamam", ""
            m.append({"anahtar": "ekf", "ad": "EKF (kestirim) sağlığı",
                      "durum": ekf_durum,
                      "deger": f"varyans maks {var_maks:.2f}",
                      "mesaj": ekf_msg, "grup": "konum"})
        else:
            m.append({"anahtar": "ekf", "ad": "EKF (kestirim) sağlığı",
                      "durum": "bilinmiyor", "deger": "bildirilmiyor",
                      "mesaj": "", "grup": "konum"})

        # --- Batarya seviyesi ---
        volt = float(d.get("batarya_v") or 0)
        pct = int(d.get("batarya_pct") if d.get("batarya_pct") is not None
                  else -1)
        if volt <= 0.1 and pct < 0:
            bat_durum, bat_msg, bat_deger = ("bilinmiyor", "",
                                             "bildirilmiyor")
        else:
            bat_deger = f"{volt:.1f} V" + (f" · %{pct}" if pct >= 0 else "")
            if 0 <= pct < 25 or (volt > 0.1 and pct < 0 and volt < 10.5):
                bat_durum = "hata"
                bat_msg = "Batarya seviyesi kalkış için düşük"
            elif 0 <= pct < 40:
                bat_durum, bat_msg = "uyari", "Batarya seviyesi düşük"
            else:
                bat_durum, bat_msg = "tamam", ""
        m.append({"anahtar": "batarya_seviye", "ad": "Batarya seviyesi",
                  "durum": bat_durum, "deger": bat_deger,
                  "mesaj": bat_msg, "grup": "guc"})

        # --- Titresim ---
        tit = d.get("titresim")
        if tit is None:
            m.append({"anahtar": "titresim", "ad": "Titreşim",
                      "durum": "bilinmiyor", "deger": "bildirilmiyor",
                      "mesaj": "", "grup": "sensor"})
        else:
            tit = float(tit)
            t_durum = ("tamam" if tit < 30 else
                       "uyari" if tit < 60 else "hata")
            m.append({"anahtar": "titresim", "ad": "Titreşim",
                      "durum": t_durum, "deger": f"{tit:.1f} m/s²",
                      "mesaj": ("" if t_durum == "tamam" else
                                f"Titreşim yüksek ({tit:.1f} m/s²)"),
                      "grup": "sensor"})

        # --- Sistem durumu (MAV_STATE) ---
        sd = int(d.get("sistem_durum") or 0)
        sd_ad = {0: "bilinmiyor", 1: "başlatılıyor", 2: "kalibrasyon",
                 3: "beklemede (standby)", 4: "etkin (uçuşta)",
                 5: "kritik", 6: "acil durum", 7: "kapanıyor",
                 8: "uçuş sonlandırma"}.get(sd, str(sd))
        m.append({"anahtar": "sistem", "ad": "Otopilot sistem durumu",
                  "durum": ("hata" if sd in (5, 6, 8) else
                            "uyari" if sd in (1, 2, 7) else
                            "bilinmiyor" if sd == 0 else "tamam"),
                  "deger": sd_ad,
                  "mesaj": ("Otopilot kritik/acil durum bildiriyor"
                            if sd in (5, 6, 8) else ""),
                  "grup": "prearm"})

        # --- Telemetri tazeligi ---
        yas = time.time() - float(d.get("son_mesaj") or 0)
        m.append({"anahtar": "telemetri", "ad": "Telemetri bağlantısı",
                  "durum": ("tamam" if yas < 3 else
                            "uyari" if yas < 8 else "hata"),
                  "deger": f"{yas:.1f} s önce",
                  "mesaj": ("" if yas < 3 else
                            "Telemetri gecikmeli/kesik"),
                  "grup": "prearm"})
        return m

    def arm_check_raporu(self, sysid):
        """ARM CHECK ekrani icin tam rapor (maddeler + mesajlar)."""
        sysid = int(sysid)
        with self.kilit:
            d = dict(self.dronlar.get(sysid) or {})
        if not d:
            return {"sysid": sysid, "bulundu": False, "maddeler": [],
                    "ozet": {"hazir": None, "kritik": 0, "uyari": 0,
                             "sebep": ""}, "mesajlar": []}
        maddeler = self.hazirlik_maddeleri(d)
        return {
            "sysid": sysid,
            "bulundu": True,
            "isim": d.get("kullanici_isim") or d.get("isim", ""),
            "armed": bool(d.get("armed")),
            "mod": d.get("mod", "?"),
            "maddeler": maddeler,
            "ozet": self.hazirlik_ozeti(d),
            "prearm_hata": d.get("prearm_hata", ""),
            "mesajlar": self.mesaj_listesi(sysid, 60),
        }

    # ------------------------------------------------------------------
    # MAVLink okuma dongusu (thread)
    # ------------------------------------------------------------------
    def _keepalive_ayarla(self, master):
        """IS43_MAVLINK_CANLILIK — TCP soketine keepalive kurar.

        ## NEDEN HEARTBEAT YETMIYOR
        Heartbeat uygulama katmanindadir ve yalnizca ucus
        denetleyicisine ulasir. Aradaki LTE modem ya da operator
        NAT'i TCP seviyesinde bakar; uygulama verisi aksa bile bazi
        yapilandirmalar yari-acik oturumlari toplar. Keepalive, TCP
        katmaninda bos probe gondererek girdinin canli kalmasini
        saglar.

        ## NEDEN HER SECENEK AYRI TRY
        `TCP_KEEPIDLE`/`TCP_KEEPINTVL`/`TCP_KEEPCNT` Linux'a ozgudur;
        Windows'ta bu sabitler YOKTUR ve `AttributeError` firlatir.
        Kopru yazilimi Windows'ta da calisir. Tek bir try blogu
        kullanmak, Windows'ta ilk secenekten sonrasini sessizce
        atlatirdi — bu yuzden her biri ayri korunur.

        Seri (USB) baglantilarda soket yoktur; sessizce atlanir.
        """
        try:
            sock = getattr(master, "port", None)
            if not isinstance(sock, socket.socket):
                return False  # seri/UDP baglantisi — keepalive yok
            if sock.type != socket.SOCK_STREAM:
                return False  # UDP soketi
        except Exception:
            return False
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        except Exception:
            return False
        for _ad, _deger in (("TCP_KEEPIDLE", 30),
                            ("TCP_KEEPINTVL", 10),
                            ("TCP_KEEPCNT", 3)):
            try:
                sock.setsockopt(socket.IPPROTO_TCP,
                                getattr(socket, _ad), _deger)
            except Exception:
                pass  # bu platformda yok — SO_KEEPALIVE yine de acik
        return True

    def _dongu_sarmal(self, bid, url, baud, durdur):
        """IS43_MAVLINK_CANLILIK — kopmada otomatik yeniden baglanir.

        ## NEDEN GEREKLI
        Onceki davranista `_dongu` tek gecisliydi: baglanti dustugunde
        thread sonlaniyor ve kullanici arayuzden elle "play"e basana
        kadar telemetri geri gelmiyordu. Mobil hatta anlik kopma
        olagandir; pilotun her seferinde mudahale etmesi beklenemez.

        ## KULLANICI IRADESI KORUNUR
        `durdur` olayi kullanici "stop" dediginde kurulur. Bu olay
        kuruluysa DONGUYE HIC GIRILMEZ ve yeniden denenmez. Otomatik
        yeniden baglanmanin kullanicinin durdurma istegini ezmesi,
        sahada denetimi kaybettiren bir kusur olurdu.

        Gecikme 2 sn'den baslar, her denemede iki katina cikar ve 30
        sn'de tavan yapar: hizli toparlanma ile sunucuyu sel altinda
        birakmamak arasindaki denge.
        """
        gecikme = 2.0
        while not durdur.is_set():
            try:
                self._dongu(bid, url, baud, durdur)
            except BaseException as e:
                self.konsol("MAVLINK",
                            f"Baglanti dongusu hatasi: {e}", "hata")
            if durdur.is_set():
                break
            c = self.baglantilar.get(bid)
            if c is None:
                break  # baglanti kaydi silinmis (durdur cagrildi)
            with self.kilit:
                c["durum"] = "baglaniyor"
                c["hata"] = ""
            self.konsol("MAVLINK",
                        f"[{c.get('isim', bid)}] Baglanti koptu, "
                        f"{gecikme:.0f} s sonra yeniden denenecek.",
                        "uyari")
            # durdur.wait() kullanilir: time.sleep() olsaydi kullanici
            # "stop" dediginde 30 saniyeye kadar beklenirdi.
            if durdur.wait(gecikme):
                break
            gecikme = min(gecikme * 2.0, 30.0)

    def _dongu(self, bid, url, baud, durdur):
        c = self.baglantilar.get(bid)
        if c is None:
            return
        etiket = c.get("isim", str(bid))
        self.konsol("MAVLINK", f"[{etiket}] Baglaniliyor: {url}")

        try:
            # source_system=255: GCS kimligi; robust_parsing: bozuk
            # paketlerde parser'in dagilmasini onler
            master = mavutil.mavlink_connection(
                url, baud=baud, source_system=255, robust_parsing=True)
            # IS43_MAVLINK_CANLILIK — TCP keepalive.
            # Heartbeat (asagida) uygulama katmaninda calisir; keepalive
            # ise ARA KATMANLARI (LTE modem, operator NAT, yonlendirici)
            # hedefler. Ikisi farkli sorunlari cozer, biri digerinin
            # yerini tutmaz.
            self._keepalive_ayarla(master)
        except Exception as e:
            with self.kilit:
                c.update(durum="hata", hata=str(e))
            self.konsol("MAVLINK",
                        f"[{etiket}] Baglanti hatasi: {e}", "hata")
            return

        c["master"] = master
        with self.kilit:
            c["durum"] = "bagli"
        self.konsol("MAVLINK",
                    f"[{etiket}] Baglanti acildi, telemetri dinleniyor...",
                    "basari")

        stream_istenen = set()
        ardisik_hata = 0  # ardisik okuma hatasi sayaci
        son_kalp = 0.0  # IS43_MAVLINK_CANLILIK — son heartbeat zamani

        while not durdur.is_set():
            # ----------------------------------------------------------
            # IS43_MAVLINK_CANLILIK — GCS HEARTBEAT (saniyede 1)
            #
            # ## NEDEN ZORUNLU
            # Bu blok olmadan baglanti, ilk stream isteklerinden sonra
            # TAMAMEN tek yonlu kalir: dron konusur, GCS susar. CUAV
            # LTE Link SE gibi mobil hatlarda operator NAT tablosu ve
            # modem oturum yoneticisi, veri gondermeyen istemciyi
            # 120-300 sn icinde dusurur. Sahada olculen belirti:
            # GOKTUNGU ~3 dakikada kopuyor, Mission Planner ayni
            # hatta kalici kaliyor. Aradaki TEK fark MP'nin saniyede
            # 1 heartbeat yollamasiydi.
            #
            # ## NEDEN AYRI THREAD DEGIL
            # `mavutil` nesnesi thread-guvenli DEGILDIR. Ayni sokete
            # iki thread'den yazmak MAVLink cercevelerini ic ice
            # gecirir ve karsi taraf paketleri cope atar. Ana dongu
            # recv_match(timeout=1.0) ile zaten saniyede en az bir kez
            # uyandigi icin heartbeat'i buradan gondermek hem guvenli
            # hem yeterlidir.
            #
            # ## NEDEN MAV_AUTOPILOT_INVALID
            # Bir yer istasyonu otopilot DEGILDIR. ArduPilot,
            # MAV_TYPE_GCS + MAV_AUTOPILOT_INVALID birlesimini gorunce
            # gondereni GCS olarak tanir ve GCS failsafe sayacini
            # sifirlar. Baska bir otopilot kimligi bildirmek, ucus
            # denetleyicisinin bu baglantiyi ikinci bir arac sanmasina
            # yol acar.
            # ----------------------------------------------------------
            _simdi = time.time()
            if _simdi - son_kalp >= 1.0:
                son_kalp = _simdi
                try:
                    master.mav.heartbeat_send(
                        mavutil.mavlink.MAV_TYPE_GCS,
                        mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                        0, 0, 0)
                except Exception:
                    # Heartbeat gonderilemezse baglanti zaten
                    # bozulmustur; okuma dongusu bunu yakalayip
                    # yeniden baglanmayi tetikler. Burada kopartmak,
                    # gecici bir yazma hatasinda saglikli baglantiyi
                    # feda etmek olurdu.
                    pass

            try:
                msg = master.recv_match(blocking=True, timeout=1.0)
                ardisik_hata = 0
            except Exception as e:
                # Gecici parser hatalarinda baglantiyi koparmak yerine
                # tolere et.
                ardisik_hata += 1
                self.konsol("MAVLINK",
                            f"[{etiket}] Okuma hatasi "
                            f"({ardisik_hata}/10): {e}", "uyari")
                if ardisik_hata >= 10:
                    with self.kilit:
                        c.update(durum="hata",
                                 hata=f"Okuma hatasi: {e}")
                    self.konsol("MAVLINK", f"[{etiket}] Ust uste 10 okuma "
                                "hatasi, baglanti kapatiliyor.", "hata")
                    break
                time.sleep(0.1)
                continue

            if msg is None:
                continue
            tip = msg.get_type()
            if tip == "BAD_DATA":
                continue
            sysid = msg.get_srcSystem()
            if sysid in (0, 255):
                continue
            # Bu sysid'nin kaynak baglantisini kaydet
            if self.sysid_baglanti.get(sysid) != bid:
                self.sysid_baglanti[sysid] = bid
            # UDP yayin koprusu: ham paketi Mission Planner'a ilet
            if self.udp_yayin:
                try:
                    self.udp_yayin.paket_yayinla(sysid, msg.get_msgbuf())
                except Exception:
                    pass

            # Gorev yukleme protokolu mesajlarini gorev yoneticisine ilet
            if tip in ("MISSION_REQUEST", "MISSION_REQUEST_INT",
                       "MISSION_ACK") and self.gorev_kancasi:
                try:
                    self.gorev_kancasi(msg)
                except Exception as e:
                    print(f"[MAVLink] Gorev kanca hatasi: {e}")
                continue

            # PARAM_VALUE — param_ara kuyruğuna ilet (thread-safe okuma)
            if tip == "PARAM_VALUE":
                with self._param_kilit:
                    q = self._param_kuyruk.get(sysid)
                if q is not None:
                    q.put(msg)
                continue   # son_mesaj guncellemesine gerek yok

            # LOG_ENTRY / LOG_DATA — log yonetimi kuyruguna ilet
            if tip in ("LOG_ENTRY", "LOG_DATA"):
                with self._log_kilit:
                    q = self._log_kuyruk.get(sysid)
                if q is not None:
                    q.put(msg)
                continue

            # v2.4.21: bu tur icinde kesinlesen kalici kimlik (kilit disi
            # islenir; DB yazimi self.kilit altinda yapilmaz)
            yeni_kimlik = None

            with self.kilit:
                if sysid not in self.dronlar:
                    self.dronlar[sysid] = self.dron_kaydi_olustur(sysid)
                    print(f"[MAVLink] Yeni dron: sysid={sysid} "
                          f"({self.dronlar[sysid]['isim']})")
                d = self.dronlar[sysid]
                d["son_mesaj"] = time.time()

                if tip == "HEARTBEAT":
                    d["mod"] = mavutil.mode_string_v10(msg)
                    d["armed"] = bool(
                        msg.base_mode &
                        mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                    # v2.4.19: ArduPilot custom_mode ustunde tasinan
                    # MAV_MODE_FLAG_CUSTOM_MODE_ENABLED yerine, arm
                    # edilebilirlik icin system_status kullanilir:
                    # MAV_STATE_STANDBY(3) = arm'a hazir,
                    # MAV_STATE_ACTIVE(4) = ucuyor,
                    # MAV_STATE_CRITICAL(5)/EMERGENCY(6) = hata.
                    d["sistem_durum"] = int(
                        getattr(msg, "system_status", 0))
                    # PREARM bayragi: MAV_MODE_FLAG_SAFETY_ARMED disinda
                    # ArduPilot, prearm sonucunu SYS_STATUS'un
                    # MAV_SYS_STATUS_PREARM_CHECK bitinde (0x10000000)
                    # bildirir; asagida SYS_STATUS'ta cozumlenir.
                    d["arm_edilebilir"] = (
                        None if not d.get("sensor_mevcut")
                        else bool(d.get("sensor_saglik", 0)
                                  & 0x10000000))
                    # Arac tipi (MAV_TYPE): failsafe/kalibrasyon popup'lari
                    # icin. 1=sabit kanat, 2=quad, 4=heli, 13/14=hexa/octo
                    if msg.type not in (0, 6, 18):  # generic/GCS/onboard degil
                        d["arac_tipi"] = msg.type
                    # v2.4.21: otopilot adi (kalici kimlik kaydi icin)
                    if not d.get("otopilot"):
                        try:
                            _ap = int(getattr(msg, "autopilot", 0) or 0)
                            d["otopilot"] = {
                                3: "ArduPilot", 12: "PX4", 0: "Generic",
                            }.get(_ap, f"MAV_AUTOPILOT_{_ap}")
                        except (TypeError, ValueError):
                            pass
                    # UDP yayin koprusu portunu ac (ilk HEARTBEAT'te)
                    if self.udp_yayin and not d.get("udp_port"):
                        p = self.udp_yayin.dron_ekle(sysid)
                        if p:
                            d["udp_port"] = p
                            # v2.4.39: arayüz daha önce
                            # window.location.hostname yaziyordu; tarayici
                            # 127.0.0.1 uzerinden acildiginda dis makineye
                            # verilecek adres loopback gorunuyordu. Soket
                            # bagi zaten 0.0.0.0; eksik olan dogru adresin
                            # BILDIRILMESIYDI.
                            try:
                                d["udp_ip"] = self.udp_yayin.lan_adres()
                            except Exception:
                                d["udp_ip"] = ""
                    if sysid not in stream_istenen:
                        stream_istenen.add(sysid)
                        try:
                            master.mav.request_data_stream_send(
                                sysid, msg.get_srcComponent(),
                                mavutil.mavlink.MAV_DATA_STREAM_ALL, 4, 1)
                            print(f"[MAVLink] sysid={sysid} veri akisi "
                                  f"istendi (4 Hz)")
                            # v2.4.19: ARM CHECK icin EKF_STATUS_REPORT (193)
                            # ve VIBRATION (241) bazi surumlerde ALL akisinda
                            # gelmez; 2 Hz'de acikca istenir.
                            # v2.4.42: HOME_POSITION (242) da ALL akisinda
                            # YAYILMAZ. HOME saniyede birden fazla
                            # degismeyecegi icin 5 s araliga kurulur; sik
                            # istemek telemetri bandini bosa harcar.
                            for _mid, _araAyar in ((193, 500000),
                                                   (241, 500000),
                                                   (242, 5000000)):
                                try:
                                    master.mav.command_long_send(
                                        sysid, msg.get_srcComponent(),
                                        mavutil.mavlink
                                        .MAV_CMD_SET_MESSAGE_INTERVAL,
                                        0, _mid, _araAyar, 0, 0, 0, 0, 0)
                                except Exception:
                                    pass
                            # Ilk HOME degerini beklemeden bir kez ISTE:
                            # SET_MESSAGE_INTERVAL destegi olmayan
                            # firmware'lerde tek yol budur.
                            try:
                                master.mav.command_long_send(
                                    sysid, msg.get_srcComponent(),
                                    mavutil.mavlink
                                    .MAV_CMD_REQUEST_MESSAGE,
                                    0, 242, 0, 0, 0, 0, 0, 0)
                            except Exception:
                                pass
                        except Exception as e:
                            # Istek gonderilemese de dinlemeye devam
                            stream_istenen.discard(sysid)
                            print(f"[MAVLink] Veri akisi istegi hatasi: {e}")
                    # UID henuz alinmadiysa AUTOPILOT_VERSION iste
                    # v2.4.22: tek istek yeterli olmuyordu (cevap kaybolursa
                    # turetilmis kimlik acilip mukerrer kayit olusuyordu).
                    # UID gelene kadar en fazla 5 kez, ~3 s arayla istenir.
                    _uid_var = bool(d.get("uid"))
                    _istek = self._uid_istenen.get(sysid) or {}
                    if not _uid_var and int(_istek.get("sayi", 0)) < 5 \
                            and (time.time() - float(
                                _istek.get("ts", 0) or 0)) > 3.0:
                        self._uid_istenen[sysid] = {
                            "sayi": int(_istek.get("sayi", 0)) + 1,
                            "ts": time.time()}
                        try:
                            master.mav.command_long_send(
                                sysid, msg.get_srcComponent(),
                                mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE,
                                0, 148, 0, 0, 0, 0, 0, 0)  # 148=AUTOPILOT_VERSION
                        except Exception:
                            pass  # hata yutuldu
                        # Bazi firmware'ler eski istegi bekler
                        try:
                            master.mav.autopilot_version_request_send(
                                sysid, msg.get_srcComponent())
                        except Exception:
                            pass

                elif tip == "GLOBAL_POSITION_INT":
                    d["lat"] = msg.lat / 1e7
                    d["lon"] = msg.lon / 1e7
                    d["alt_msl"] = msg.alt / 1000.0
                    d["alt_rel"] = msg.relative_alt / 1000.0
                    if msg.hdg != 65535:
                        d["heading"] = msg.hdg / 100.0
                    d["vz"] = -msg.vz / 100.0
                    # v2.4.43: yatay hiz vektoru (cm/s -> m/s)
                    d["vx"] = msg.vx / 100.0   # kuzey
                    d["vy"] = msg.vy / 100.0   # dogu
                    d["poz_ts"] = time.time()

                elif tip == "VFR_HUD":
                    d["groundspeed"] = msg.groundspeed
                    d["airspeed"] = msg.airspeed

                elif tip == "ATTITUDE":
                    # Radyan -> derece (yapay ufuk gostergesi icin)
                    d["roll"] = math.degrees(msg.roll)
                    d["pitch"] = math.degrees(msg.pitch)
                    d["tutum_ts"] = time.time()

                elif tip == "SYS_STATUS":
                    d["batarya_v"] = msg.voltage_battery / 1000.0
                    d["batarya_pct"] = msg.battery_remaining
                    # Akim: -1 = bilinmiyor (mA*10 -> A)
                    if msg.current_battery != -1:
                        d["batarya_a"] = msg.current_battery / 100.0
                    # v2.4.19: ARM CHECK icin sensor bit maskeleri
                    d["sensor_mevcut"] = int(
                        getattr(msg, "onboard_control_sensors_present", 0))
                    d["sensor_etkin"] = int(
                        getattr(msg, "onboard_control_sensors_enabled", 0))
                    d["sensor_saglik"] = int(
                        getattr(msg, "onboard_control_sensors_health", 0))

                elif tip == "BATTERY_STATUS":
                    # Detayli batarya bilgisi (batarya popup'i icin)
                    if msg.current_consumed != -1:
                        d["batarya_mah"] = msg.current_consumed  # mAh
                    if msg.energy_consumed != -1:
                        d["batarya_wh"] = msg.energy_consumed / 100.0  # Wh
                    if msg.temperature != 32767:
                        d["batarya_sicaklik"] = msg.temperature / 100.0
                    # Hucre gerilimleri (65535 = yok)
                    hucreler = [v / 1000.0 for v in msg.voltages
                                if v not in (0, 65535)]
                    if hucreler:
                        d["batarya_hucre"] = len(hucreler)
                        d["batarya_hucre_min"] = min(hucreler)
                        d["batarya_hucre_max"] = max(hucreler)
                    # Kalan ucus suresi tahmini (sn, 0 = yok)
                    kalan = getattr(msg, "time_remaining", 0)
                    if kalan:
                        d["batarya_kalan_sn"] = kalan

                elif tip == "GPS_RAW_INT":
                    d["gps_fix"] = msg.fix_type
                    d["uydu"] = msg.satellites_visible
                    # HDOP: 65535 = bilinmiyor (cm -> birimsiz)
                    if msg.eph != 65535:
                        d["hdop"] = msg.eph / 100.0
                    if msg.epv != 65535:
                        d["vdop"] = msg.epv / 100.0
                    # GPS yer hizi (cm/s -> m/s) ve rota (cdeg -> deg)
                    if msg.vel != 65535:
                        d["gps_hiz"] = msg.vel / 100.0
                    if msg.cog != 65535:
                        d["gps_rota"] = msg.cog / 100.0
                    # GPS ham irtifa (mm -> m)
                    d["gps_alt"] = msg.alt / 1000.0

                elif tip == "MISSION_CURRENT":
                    d["mission_seq"] = msg.seq

                elif tip == "EKF_STATUS_REPORT":
                    # v2.4.19: EKF saglik bayraklari ve varyanslar
                    d["ekf_bayrak"] = int(getattr(msg, "flags", 0))
                    d["ekf_hiz_var"] = round(
                        float(getattr(msg, "velocity_variance", 0.0)), 3)
                    d["ekf_konum_var"] = round(
                        float(getattr(msg, "pos_horiz_variance", 0.0)), 3)
                    d["ekf_yuk_var"] = round(
                        float(getattr(msg, "pos_vert_variance", 0.0)), 3)
                    d["ekf_pusula_var"] = round(
                        float(getattr(msg, "compass_variance", 0.0)), 3)

                elif tip == "VIBRATION":
                    # v2.4.19: en buyuk eksen titresimi (m/s^2)
                    d["titresim"] = round(max(
                        float(getattr(msg, "vibration_x", 0.0)),
                        float(getattr(msg, "vibration_y", 0.0)),
                        float(getattr(msg, "vibration_z", 0.0))), 2)

                elif tip == "HOME_POSITION":
                    # v2.4.42: HOME (kalkis/donus) noktasi.
                    # latitude/longitude 1e7 olcekli tamsayi, altitude mm.
                    # HOME atanmamissa bazi firmware'ler 0/0 gonderir;
                    # 0,0 gecerli bir Gulf of Guinea koordinati olsa da
                    # HOME olarak pratikte "atanmamis" anlamina gelir ve
                    # kabul edilmesi haritada Afrika kiyisinda ikon
                    # ciziverirdi. Bu yuzden 0/0 REDDEDILIR.
                    _hlat = int(getattr(msg, "latitude", 0)) / 1e7
                    _hlon = int(getattr(msg, "longitude", 0)) / 1e7
                    if abs(_hlat) < 1e-7 and abs(_hlon) < 1e-7:
                        d["home_lat"] = None
                        d["home_lon"] = None
                        d["home_alt"] = None
                    else:
                        d["home_lat"] = _hlat
                        d["home_lon"] = _hlon
                        d["home_alt"] = int(
                            getattr(msg, "altitude", 0)) / 1000.0
                    # Mesajin GELDIGI bilgisi konumdan bagimsiz kaydedilir:
                    # "otopilot bildirdi ama HOME yok" ile "otopilot henuz
                    # bildirmedi" ayri durumlardir.
                    d["home_ts"] = time.time()

                elif tip == "STATUSTEXT":
                    # Dronun durum mesajlari (kalibrasyon dahil) konsola
                    metin = msg.text
                    if isinstance(metin, bytes):
                        metin = metin.decode("ascii", "ignore")
                    metin = metin.rstrip("\x00").strip()
                    if metin:
                        # severity: 0-3 hata, 4 uyari, 5+ bilgi
                        sev = ("hata" if msg.severity <= 3 else
                               "uyari" if msg.severity == 4 else "")
                        # v2.4.45: her STATUSTEXT once DRONUN kendi
                        # konsoluna yazilir (ciplak, tam metin).
                        self.dkonsol(sysid, "STATUS", metin,
                                     sev or "bilgi")
                        # Genel konsola YALNIZ hata/uyari seviyeli satirlar
                        # dusuyor; boylece toast koprusu calismaya devam
                        # ederken genel konsol bilgi mesajlariyla dolmuyor.
                        if sev:
                            self.konsol("DRON",
                                        f"[{sysid}] {metin}", sev)
                        # v2.4.19: ARM CHECK paneli icin mesaj tamponu
                        self._mesaj_ekle(sysid, metin,
                                         int(msg.severity))
                        alt_metin = metin.lower()
                        if (alt_metin.startswith("prearm")
                                or alt_metin.startswith("arm:")
                                or "arm" in alt_metin.split(":")[0]):
                            d["prearm_hata"] = metin
                            d["prearm_ani"] = time.time()

                elif tip == "COMMAND_ACK":
                    # v2.4.33: KOMUT SONUCU BILDIRIMI
                    # ------------------------------------------------
                    # KULLANICI ISTEGI: "drona takeoff dugmesine bastim
                    # ve takeoff olmadi, bunu SEBEBI ILE bildirim
                    # verecek."
                    #
                    # Onceki surumlerde COMMAND_ACK HIC okunmuyordu.
                    # `komut_gonder()` komutu yollar yollamaz konsola
                    # "basari" yaziyordu; dron komutu reddetse bile
                    # arayuz basarili gorunuyordu. Gercek sonuc yalniz
                    # bu mesajdaki `result` alanindan ogrenilebilir.
                    self._komut_ack_isle(sysid, d, msg)

                elif tip == "DISTANCE_SENSOR":
                    # v2.5.0: YAKINLIK ALGILAYICISI
                    # ------------------------------------------------
                    # Her mesaj TEK bir yonun olcumunu tasir. Yonler
                    # ayri ayri saklanir; boylece arayuz yalniz ACIK
                    # yonlerde kalkan cizer.
                    #
                    # Birim: mesaj cm verir, metreye cevrilir.
                    # max_distance'a esit/buyuk olcum "olcum yok"
                    # demektir (ArduPilot sozlesmesi) — bu durumda yon
                    # kaydi silinir, aksi halde arayuz olmayan bir
                    # engeli gosterirdi.
                    try:
                        _yon = int(getattr(msg, "orientation", 0))
                        _cm = float(getattr(msg, "current_distance", 0))
                        _mn = float(getattr(msg, "min_distance", 0))
                        _mx = float(getattr(msg, "max_distance", 0))
                    except (TypeError, ValueError):
                        _yon = None
                    if _yon is not None:
                        _yonler = d.get("prx_yonler")
                        if not isinstance(_yonler, dict):
                            _yonler = {}
                            d["prx_yonler"] = _yonler
                        if _mx > 0 and _cm >= _mx:
                            _yonler.pop(str(_yon), None)
                        else:
                            _yonler[str(_yon)] = {
                                "mesafe": _cm / 100.0,
                                "min": _mn / 100.0,
                                "max": _mx / 100.0,
                                "ts": time.time()}
                        d["prx_ts"] = time.time()
                elif tip == "MAG_CAL_PROGRESS":
                    d["magkal_pct"] = int(
                        getattr(msg, "completion_pct", 0))
                    d["magkal_durum"] = "suruyor"

                elif tip == "MAG_CAL_REPORT":
                    # cal_status: 3=basari, 4=basarisiz
                    basarili = getattr(msg, "cal_status", 0) == 3
                    d["magkal_durum"] = ("basarili" if basarili
                                         else "basarisiz")
                    d["magkal_pct"] = 100 if basarili else 0
                    # v2.5.0: raporun TAM alanlari saklanir. Operator
                    # kalibrasyon SONUCUNU degil DEGERLERINI de gorur:
                    # fitness (uyum hatasi, mT) kabul edilebilirligin
                    # tek olculebilir gostergesidir.
                    try:
                        d["magkal_rapor"] = {
                            "pusula_id": int(getattr(
                                msg, "compass_id", 0)),
                            "durum": int(getattr(msg, "cal_status", 0)),
                            "fitness": float(getattr(
                                msg, "fitness", 0.0)),
                            "ofs_x": float(getattr(msg, "ofs_x", 0.0)),
                            "ofs_y": float(getattr(msg, "ofs_y", 0.0)),
                            "ofs_z": float(getattr(msg, "ofs_z", 0.0)),
                            "diag_x": float(getattr(
                                msg, "diag_x", 0.0)),
                            "diag_y": float(getattr(
                                msg, "diag_y", 0.0)),
                            "diag_z": float(getattr(
                                msg, "diag_z", 0.0)),
                            "offdiag_x": float(getattr(
                                msg, "offdiag_x", 0.0)),
                            "offdiag_y": float(getattr(
                                msg, "offdiag_y", 0.0)),
                            "offdiag_z": float(getattr(
                                msg, "offdiag_z", 0.0)),
                            "yon": int(getattr(
                                msg, "orientation", 0)),
                            "olcek": float(getattr(
                                msg, "scale_factor", 0.0)),
                            "ts": time.time()}
                    except (TypeError, ValueError):
                        d["magkal_rapor"] = None
                    self.konsol("KALIB",
                                f"sysid={sysid} pusula kalibrasyonu "
                                + ("BASARILI — yeniden baslatma "
                                   "gerekebilir" if basarili
                                   else "BASARISIZ"),
                                "basari" if basarili else "hata")

                elif tip == "AUTOPILOT_VERSION":
                    # uid2 = 8-byte flight_custom_version veya uid alanı
                    uid_val = getattr(msg, "uid", 0) or 0
                    kaynak = "autopilot_uid"
                    if uid_val == 0:
                        # uid2 alanini dene (ArduPilot)
                        uid2 = getattr(msg, "uid2", None)
                        if uid2 and any(b != 0 for b in uid2):
                            uid_val = int.from_bytes(
                                bytes(uid2[:8]), "little")
                            kaynak = "uid2"
                    # v2.4.21: firmware surumu (kimlik kaydinda saklanir)
                    try:
                        fv = int(getattr(msg, "flight_sw_version", 0) or 0)
                        if fv:
                            d["firmware"] = (
                                f"{(fv >> 24) & 0xFF}."
                                f"{(fv >> 16) & 0xFF}."
                                f"{(fv >> 8) & 0xFF}")
                    except (TypeError, ValueError):
                        pass
                    if uid_val:
                        uid_str = hex(uid_val)
                        d["uid"] = uid_str
                        # Kayitli isim varsa ata
                        kayitli = self._uid_ile_isim_coz(sysid, uid_str)
                        if kayitli:
                            d["kullanici_isim"] = kayitli
                        # v2.4.21: kalici kimlik kaydi + oturum acilisi
                        yeni_kimlik = (uid_str, kaynak)

            # ----------------------------------------------------------
            # v2.4.21: kalici kimlik kaydi (self.kilit BIRAKILDIKTAN
            # sonra; DB islemleri kilit altinda tutulmaz)
            # ----------------------------------------------------------
            if yeni_kimlik is not None:
                self.kimlik_kaydet(sysid, yeni_kimlik[0], yeni_kimlik[1])
            elif not self.dron_db_id.get(sysid):
                # UID gelmezse UID_BEKLEME sonrasi turetilmis kimlik
                self.kimlik_denetim(sysid)

        c["master"] = None
        try:
            master.close()
        except Exception:
            pass
        with self.kilit:
            if c["durum"] != "hata":
                c["durum"] = "kapali"
        self.konsol("MAVLINK", f"[{etiket}] Baglanti kapatildi.", "uyari")

    # ------------------------------------------------------------------
    # Dron komutlari
    # ------------------------------------------------------------------
    def _durum_bekle(self, sysid, kosul, sure):
        """Telemetri durumunun kosulu saglamasini sure asimina kadar bekler."""
        bitis = time.time() + float(sure)
        while time.time() < bitis:
            with self.kilit:
                durum = dict(self.dronlar.get(int(sysid)) or {})
            if kosul(durum):
                return True
            time.sleep(0.15)
        return False

    def _kalkis_islemi(self, sysid, hedef_irtifa):
        """GUIDED -> ARM teyidi -> TAKEOFF akisini WS dongusunu bloklamadan kurar."""
        try:
            master = self.master_bul(sysid)
            if master is None:
                self.dkonsol(sysid, "KALKIS", "Kalkis reddedildi: MAVLink baglantisi yok.", "hata")
                return
            with self.kilit:
                master.mav.set_mode_send(
                    sysid,
                    mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                    4)  # GUIDED
            if not self._durum_bekle(
                    sysid,
                    lambda d: str(d.get("mod") or "").upper() == "GUIDED",
                    4.0):
                self.dkonsol(sysid, "KALKIS", "GUIDED modu teyit edilmedi; takeoff gonderilmedi.", "hata")
                return

            with self.kilit:
                zaten_armli = bool((self.dronlar.get(sysid) or {}).get("armed"))
            if not zaten_armli:
                with self.kilit:
                    master.mav.command_long_send(
                        sysid, 1,
                        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                        0, 1, 0, 0, 0, 0, 0, 0)
                if not self._durum_bekle(
                        sysid, lambda d: bool(d.get("armed")), 6.0):
                    self.dkonsol(sysid, "KALKIS", "ARM teyidi alinamadi; takeoff gonderilmedi. Pre-arm uyarilarini kontrol edin.", "hata")
                    return

            # Baglanti yeniden kurulmus olabilecegi icin master'i son kez yenile.
            master = self.master_bul(sysid)
            if master is None:
                self.dkonsol(sysid, "KALKIS", "Takeoff oncesi MAVLink baglantisi kesildi.", "hata")
                return
            with self.kilit:
                master.mav.command_long_send(
                    sysid, 1,
                    mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                    0, 0, 0, 0, 0, 0, 0, hedef_irtifa)
                self.hedef_irtifa_rel[sysid] = hedef_irtifa
            self.dkonsol(sysid, "KALKIS", f"TAKEOFF komutu iletildi: {hedef_irtifa:.0f} m", "basari")
            self.konsol("KOMUT", f"sysid={sysid} TAKEOFF {hedef_irtifa:.0f}m", "basari")
        except Exception as e:
            self.dkonsol(sysid, "KALKIS", f"Kalkis komut hatasi: {e}", "hata")
        finally:
            with self._kalkis_kilit:
                self._kalkis_islemleri.discard(int(sysid))

    def komut_gonder(self, sysid, aksiyon, irtifa=None):
        """Belirtilen drona MAVLink komutu gonderir.

        irtifa: takeoff/altitude_change icin hedef irtifa (m, zemine gore);
        None ise varsayilan.
        """
        master = self.master_bul(sysid)
        if master is None:
            self.konsol("KOMUT", "MAVLink baglantisi yok.", "hata")
            return
        # v2.4.45: sysid artik satir metninde tekrarlanmiyor; konsol zaten
        # dronun kendi panelinin altinda.
        self.dkonsol(sysid, "KOMUT", f"-> {aksiyon}")

        if aksiyon == "takeoff":
            try:
                hedef_irtifa = (float(irtifa) if irtifa is not None
                                else TAKEOFF_IRTIFA)
            except (TypeError, ValueError):
                hedef_irtifa = TAKEOFF_IRTIFA
            hedef_irtifa = max(1.0, min(500.0, hedef_irtifa))  # 1-500 m
            with self._kalkis_kilit:
                if int(sysid) in self._kalkis_islemleri:
                    self.dkonsol(sysid, "KALKIS", "Kalkis hazirlik akisi zaten suruyor; tekrar komut gonderilmedi.", "uyari")
                    return False
                self._kalkis_islemleri.add(int(sysid))
            threading.Thread(
                target=self._kalkis_islemi,
                args=(int(sysid), hedef_irtifa), daemon=True).start()
            self.dkonsol(sysid, "KALKIS", "GUIDED/ARM teyidi bekleniyor...", "uyari")
            return True

        elif aksiyon == "rtl":
            master.mav.set_mode_send(
                sysid,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                6)  # RTL
            with self.kilit:
                self.hedef_irtifa_rel.pop(sysid, None)
            self.dkonsol(sysid, "KOMUT", f"RTL", "basari")

        elif aksiyon == "auto":
            master.mav.set_mode_send(
                sysid,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                3)  # AUTO
            self.dkonsol(sysid, "KOMUT", f"AUTO", "basari")

        elif aksiyon == "land":
            master.mav.set_mode_send(
                sysid,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                9)  # LAND
            with self.kilit:
                self.hedef_irtifa_rel.pop(sysid, None)
            self.dkonsol(sysid, "KOMUT", f"LAND", "basari")

        elif aksiyon in ("arm", "arm_zorla"):
            # v2.5.0 KUSUR DUZELTMESI: arm komutu ARTIK KIP DEGISTIRMEZ.
            # ----------------------------------------------------------
            # Onceki surumde bu dal arm'dan once `set_mode_send(..., 4)`
            # ile araci GUIDED kipine ZORLUYORDU. Operatorun belirtisi
            # ("arm gonderince dronun modu degisiyor") tam olarak bu
            # satirin sonucuydu. Arm etmek bir KIP ISLEMI DEGILDIR:
            # ArduPilot her kipte arm edilebilir (kip arm'a izin
            # vermiyorsa otopilot PreArm reddi doner ve bu red mevcut
            # STATUSTEXT koprusuyle operatore GOSTERILIR).
            #
            # DIKKAT: `takeoff` dalindaki GUIDED atamasi KORUNUR; orada
            # dogrudur, cunku MAV_CMD_NAV_TAKEOFF GUIDED/AUTO ister.
            #
            # ZORLA ARM (param2=21196): arming denetimlerini ATLAR.
            # Sozlesme kodda zaten vardi (disarm dali kullaniyor);
            # arm tarafina uygulanmamisti.
            zorla = (aksiyon == "arm_zorla")
            master.mav.command_long_send(
                sysid, 1,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0,
                1, 21196 if zorla else 0, 0, 0, 0, 0, 0)
            self.dkonsol(sysid, "KOMUT",
                         "ARM (ZORLA — denetimler atlandi)" if zorla
                         else "ARM", "uyari" if zorla else "basari")
            if zorla:
                self.konsol("KOMUT",
                            f"sysid={sysid} ZORLA ARM: arming "
                            "denetimleri atlandi", "uyari")
        elif aksiyon == "reboot":
            # v2.5.0: MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN (246)
            # param1=1 -> ucus kontrolcusunu yeniden baslat.
            # GUVENLIK KAPISI: arac ARM EDILMISSE reddedilir. Havada FC
            # yeniden baslatmak dusus demektir; bu karar operatore
            # birakilamaz.
            with self.kilit:
                _d = self.dronlar.get(sysid, {})
                _armli = bool(_d.get("armed"))
            if _armli:
                self.dkonsol(sysid, "KOMUT",
                             "REBOOT REDDEDILDI: arac arm edilmis "
                             "durumda. Once disarm edin.", "hata")
                self.konsol("KOMUT",
                            f"sysid={sysid} reboot reddedildi: armli",
                            "hata")
                return
            master.mav.command_long_send(
                sysid, 1,
                mavutil.mavlink.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN,
                0,
                1, 0, 0, 0, 0, 0, 0)
            self.dkonsol(sysid, "KOMUT",
                         "REBOOT gonderildi — baglanti kesilecek ve "
                         "yeniden kurulacak", "uyari")
            self.konsol("KOMUT",
                        f"sysid={sysid} ucus kontrolcusu yeniden "
                        "baslatiliyor", "uyari")

        elif aksiyon == "disarm":
            master.mav.command_long_send(
                sysid, 1,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0,
                0, 21196, 0, 0, 0, 0, 0)  # arm=0, force=21196
            with self.kilit:
                self.hedef_irtifa_rel.pop(sysid, None)
            self.dkonsol(sysid, "KOMUT", f"DISARM", "basari")

        elif aksiyon == "set_mode":
            # irtifa parametresi mod numarasi olarak kullanilir
            try:
                mod_no = int(irtifa)
            except (TypeError, ValueError):
                self.konsol("KOMUT", "Gecersiz mod numarasi.", "hata")
                return
            # Arac tipine gore dogru mod beyaz listesi sec
            harita = self._mod_haritasi(sysid)
            if mod_no not in harita:
                self.konsol("KOMUT", f"Izin verilmeyen mod: {mod_no}", "hata")
                return
            master.mav.set_mode_send(
                sysid,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                mod_no)
            self.konsol("KOMUT",
                        f"sysid={sysid} MOD -> {harita[mod_no]}",
                        "basari")

        elif aksiyon in ("kalib_gyro", "kalib_baro", "kalib_ivme",
                         "kalib_level", "kalib_esc"):
            # MAV_CMD_PREFLIGHT_CALIBRATION (241) parametre haritasi:
            # p1=1 gyro, p3=1 baro(ground pressure), p5=1 ivmeolcer(3D),
            # p5=2 level trim, p7=3 ESC (dikkat: pervanesiz yapilmali)
            p = {"kalib_gyro":  (1, 0, 0, 0, 0, 0, 0),
                 "kalib_baro":  (0, 0, 1, 0, 0, 0, 0),
                 "kalib_ivme":  (0, 0, 0, 0, 1, 0, 0),
                 "kalib_level": (0, 0, 0, 0, 2, 0, 0),
                 "kalib_esc":   (0, 0, 0, 0, 0, 0, 3)}[aksiyon]
            # v2.5.0: mesaj suzgeci icin oturum acilir (kalibrasyon
            # penceresi yalniz bu andan sonraki STATUSTEXT satirlarini
            # gosterir).
            self.kalib_oturum_baslat(sysid,
                                     aksiyon.replace("kalib_", ""))
            master.mav.command_long_send(
                sysid, 1,
                mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION,
                0, *p)
            self.konsol("KALIB",
                        f"sysid={sysid} {aksiyon.replace('kalib_', '')}"
                        " kalibrasyonu istendi", "basari")

        elif aksiyon == "kalib_radyo":
            # v2.5.0: RADYO (RC) kalibrasyonu — MAV_CMD_PREFLIGHT_CALIBRATION
            # param4=1. ArduPilot bunu bir "kalibrasyon baslat" isaretcisi
            # olarak alir; gercek is RC_MIN/RC_MAX parametrelerinin
            # kanallar oynatilirken ogrenilmesidir. Operator kanallari uc
            # noktalarina getirirken pencere anlik PWM degerlerini gosterir.
            self.kalib_oturum_baslat(sysid, "radyo")
            master.mav.command_long_send(
                sysid, 1,
                mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION,
                0, 0, 0, 0, 1, 0, 0, 0)
            self.konsol("KALIB",
                        f"sysid={sysid} radyo kalibrasyonu istendi",
                        "basari")
        elif aksiyon == "kalib_pusula_baslat":
            # v2.5.0: oturum acilir (mesaj suzgeci + eski rapor temizligi)
            self.kalib_oturum_baslat(sysid, "pusula")
            # MAV_CMD_DO_START_MAG_CAL (42424): tum pusulalar,
            # otomatik kaydetmeli (p4=1 autosave)
            master.mav.command_long_send(
                sysid, 1, 42424, 0,
                0, 1, 1, 0, 0, 0, 0)  # mask=0(hepsi), retry=1, autosave=1
            self.konsol("KALIB",
                        f"sysid={sysid} pusula kalibrasyonu basladi — "
                        "dronu tum eksenlerde dondurun", "basari")

        elif aksiyon == "kalib_pusula_kabul":
            # MAV_CMD_DO_ACCEPT_MAG_CAL (42425)
            master.mav.command_long_send(
                sysid, 1, 42425, 0, 0, 0, 0, 0, 0, 0, 0)
            self.dkonsol(sysid, "KALIB", f"pusula kalibrasyonu "
                        "kabul edildi", "basari")

        elif aksiyon == "kalib_pusula_iptal":
            # MAV_CMD_DO_CANCEL_MAG_CAL (42426)
            master.mav.command_long_send(
                sysid, 1, 42426, 0, 0, 0, 0, 0, 0, 0, 0)
            self.dkonsol(sysid, "KALIB", f"pusula kalibrasyonu "
                        "iptal edildi", "uyari")

        elif aksiyon == "altitude_change":
            # Mevcut konumda irtifa degistir (GUIDED + pozisyon komutu)
            try:
                hedef_irtifa = float(irtifa) if irtifa is not None else 10.0
            except (TypeError, ValueError):
                hedef_irtifa = 10.0
            hedef_irtifa = max(1.0, min(500.0, hedef_irtifa))
            master.mav.set_mode_send(
                sysid,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                4)  # GUIDED
            # Mevcut lat/lon'u koru, yalniz irtifayi degistir.
            # Hedef irtifa HAFIZAYA alinir: sonraki goto komutlari dronun
            # anlik irtifasini degil, bu hedefi kullanir (tirmanis/alcalma
            # yarida kesilmez, komutlar birlikte calisir).
            with self.kilit:
                d = self.dronlar.get(sysid, {})
                lat = d.get("lat", 0.0)
                lon = d.get("lon", 0.0)
                alt_msl = d.get("alt_msl", 0.0)
                alt_rel = d.get("alt_rel", 0.0)
                self.hedef_irtifa_rel[sysid] = hedef_irtifa
            # Hedef irtifa = mevcut MSL - mevcut rel + yeni rel
            yeni_msl = alt_msl - alt_rel + hedef_irtifa
            master.mav.set_position_target_global_int_send(
                0, sysid, 1,
                mavutil.mavlink.MAV_FRAME_GLOBAL_INT,
                0b0000111111111000,  # sadece pozisyon
                int(lat * 1e7), int(lon * 1e7),
                yeni_msl,
                0, 0, 0, 0, 0, 0, 0, 0)
            self.konsol("KOMUT",
                        f"sysid={sysid} IRTIFA -> {hedef_irtifa:.0f}m",
                        "basari")

    # Kullaniciya sunulan ArduCopter ucus modlari (custom_mode -> ad)
    MOD_HARITASI = {
        0: "STABILIZE",
        2: "ALT_HOLD",
        3: "AUTO",
        4: "GUIDED",
        5: "LOITER",
        6: "RTL",
        9: "LAND",
        16: "POSHOLD",
        17: "BRAKE",
    }

    # ArduPlane ucus modlari (custom_mode -> ad); QSTABILIZE+ VTOL icin
    MOD_HARITASI_PLANE = {
        0: "MANUAL",
        1: "CIRCLE",
        2: "STABILIZE",
        5: "FBWA",
        6: "FBWB",
        7: "CRUISE",
        10: "AUTO",
        11: "RTL",
        12: "LOITER",
        15: "GUIDED",
        17: "QSTABILIZE",
        19: "QHOVER",
        20: "QLOITER",
        21: "QLAND",
        22: "QRTL",
    }

    # Geleneksel helikopter (ArduCopter heli): copter modlari + ACRO,
    # POSHOLD/BRAKE heli'de de gecerlidir
    MOD_HARITASI_HELI = {
        0: "STABILIZE",
        1: "ACRO",
        2: "ALT_HOLD",
        3: "AUTO",
        4: "GUIDED",
        5: "LOITER",
        6: "RTL",
        9: "LAND",
        16: "POSHOLD",
    }

    def _mod_haritasi(self, sysid):
        """Dronun HEARTBEAT arac tipine (MAV_TYPE) gore mod listesi.
        1=plane, 19-25=VTOL -> plane; 4=heli; digerleri kopter.
        """
        tip = 0
        kayit = self.dronlar.get(int(sysid))
        if kayit:
            try:
                tip = int(kayit.get("arac_tipi", 0))
            except (TypeError, ValueError):
                tip = 0
        if tip == 1 or tip in (19, 20, 21, 22, 23, 24, 25):
            return self.MOD_HARITASI_PLANE
        if tip == 4:
            return self.MOD_HARITASI_HELI
        return self.MOD_HARITASI

    # Izin verilen ArduPilot parametreleri (guvenlik: yalniz bu liste)
    # UI m/s cinsinden gonderir; ArduPilot WPNAV_* birimleri cm/s'dir.
    # v2.4.13: Interceptor profili - hiz ust sinirlari 300 km/h'e
    # (83.3 m/s) yukseltildi. Ust sinir mumkunse drondan okunan hiz
    # parametresinden (param_ara ile) alinir; okunamazsa HIZ_MAKS.
    HIZ_MAKS = 83.3   # m/s (= 300 km/h) - fallback ust sinir
    PARAM_HARITASI = {
        "yukselme_hizi": ("WPNAV_SPEED_UP", 100.0, 0.5, 83.3),
        "alcalma_hizi":  ("WPNAV_SPEED_DN", 100.0, 0.5, 83.3),
        "hareket_hizi":  ("WPNAV_SPEED",    100.0, 0.5, 83.3),
        "rtl_irtifa":    ("RTL_ALT",        100.0, 2.0, 200.0),
    }

    def param_ayarla(self, sysid, ad, deger):
        """Drona ArduPilot parametresi yazar (yalniz izinli liste).

        ad: PARAM_HARITASI anahtari; deger: UI birimi (m/s veya m).

        v2.4.38: Artik SONUC DONDURUR.
        Donus: (basari, param_adi, ham_deger)
          basari    : True/False  -> yazma paketi gerceklen gonderildi mi
          param_adi : "WPNAV_SPEED" gibi GERCEK ArduPilot adi (yoksa None)
          ham_deger : araca giden ham deger (cm/s vb.; yoksa None)

        Eskiden bu metot None donuyordu; sunucu.py basariyi bilemedigi
        icin yazma basarisiz olsa bile kalici parametre tablosuna ve
        degisiklik gecmisine "yazildi" kaydi dusuyordu ve arayuze hic
        yanit gitmiyordu. Donus degeri bu iki kusuru kapatir.
        """
        try:
            sysid = int(sysid)
        except (TypeError, ValueError):
            self.konsol("KOMUT", f"Gecersiz sysid: {sysid}", "hata")
            return (False, None, None)
        tanim = self.PARAM_HARITASI.get(str(ad))
        if not tanim:
            self.konsol("KOMUT", f"Bilinmeyen parametre: {ad}", "hata")
            return (False, None, None)
        p_ad, carpan, alt, ust = tanim
        master = self.master_bul(sysid)
        if master is None:
            self.konsol("KOMUT",
                        f"{p_ad} yazilamadi: MAVLink baglantisi yok.",
                        "hata")
            return (False, p_ad, None)
        try:
            v = float(deger)
        except (TypeError, ValueError):
            self.konsol("KOMUT", f"Gecersiz deger: {deger}", "hata")
            return (False, p_ad, None)
        v = max(alt, min(ust, v))
        ham = v * carpan
        try:
            master.mav.param_set_send(
                sysid, 1, p_ad.encode("ascii"), float(ham),
                mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
            self.konsol("KOMUT",
                        f"sysid={sysid} {p_ad} = {v:g} "
                        f"({ham:g} ham)", "basari")
            return (True, p_ad, float(ham))
        except Exception as e:
            self.konsol("KOMUT", f"Parametre yazma hatasi: {e}", "hata")
            return (False, p_ad, None)

    def goto_gonder(self, sysid, lat, lon):
        """Dronu belirtilen GPS koordinatina gonderir (GUIDED + pozisyon).

        Irtifa secimi: kullanici daha once irtifa hedefi verdiyse
        (altitude_change / takeoff) o REL hedef kullanilir; boylece devam
        eden tirmanis/alcalma konum degisikligiyle IPTAL OLMAZ - dron hem
        yeni konuma gider hem hedef irtifaya tirmanmaya devam eder.
        ArduPilot GUIDED'da her yeni pozisyon hedefi oncekini ANINDA
        degistirir; bekleme olmaz.
        """
        master = self.master_bul(sysid)
        if master is None:
            self.konsol("KOMUT", "MAVLink baglantisi yok.", "hata")
            return
        try:
            lat = float(lat)
            lon = float(lon)
        except (TypeError, ValueError):
            self.konsol("KOMUT",
                        f"sysid={sysid} GOTO gecersiz koordinat", "hata")
            return
        with self.kilit:
            d = self.dronlar.get(sysid, {})
            alt_msl = d.get("alt_msl", 50.0)
            alt_rel = d.get("alt_rel", 0.0)
            hedef_rel = self.hedef_irtifa_rel.get(sysid)
        if hedef_rel is not None:
            # Kayitli REL hedefi MSL'e cevir (zemin = anlik MSL - anlik REL)
            hedef_msl = (alt_msl - alt_rel) + hedef_rel
            irtifa_not = f"{hedef_rel:.0f}m rel (hedef korundu)"
        else:
            hedef_msl = alt_msl
            irtifa_not = f"{alt_msl:.0f}m MSL (mevcut)"
        # GUIDED moda al
        master.mav.set_mode_send(
            sysid,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            4)  # GUIDED
        # Pozisyon komutu gonder (yeni hedef oncekini aninda gecersiz kilar)
        master.mav.set_position_target_global_int_send(
            0, sysid, 1,
            mavutil.mavlink.MAV_FRAME_GLOBAL_INT,
            0b0000111111111000,  # sadece pozisyon
            int(lat * 1e7), int(lon * 1e7),
            hedef_msl,
            0, 0, 0, 0, 0, 0, 0, 0)
        self.konsol("KOMUT",
                    f"sysid={sysid} GOTO {lat:.5f},{lon:.5f} "
                    f"@ {irtifa_not}",
                    "basari")

    # ------------------------------------------------------------------
    # v2.4.42: HOME (kalkis/donus) noktasi ayarlama
    # ------------------------------------------------------------------
    def set_home_gonder(self, sysid, lat=None, lon=None):
        """HOME noktasini ayarlar (MAV_CMD_DO_SET_HOME, 179).

        Iki kip AYNI MAVLink komutunun param1 degeriyle secilir:
          * lat/lon VERILMEZSE  -> param1=1: aracin MEVCUT konumu HOME olur
            (otopilot kendi konumunu kullanir; koordinat alanlari yok
            sayilir). "Islemler > HOME AYARLA" bunu kullanir.
          * lat/lon VERILIRSE   -> param1=0 + param5/6/7 = lat/lon/alt:
            belirtilen konum HOME olur. Haritada SHIFT + tik bunu kullanir.

        Irtifa (param7) hakkinda: ArduPilot konum kipinde AMSL bekler.
        Tiklanan noktanin gercek zemin yuksekligi elimizde YOKTUR (arazi
        verisi kapali olabilir). En iyi kestirim, dronun BULUNDUGU zeminin
        AMSL'idir: zemin = alt_msl - alt_rel. alt=0 gonderilseydi HOME
        deniz seviyesine oturur ve RTL irtifasi ile yukseklik raporlamasi
        sessizce kayardi; dronun anlik AMSL'i gonderilseydi havadaki arac
        icin HOME ucus irtifasinda kalirdi.

        Telemetri yoksa (irtifa kestirilemez) komut GONDERILMEZ ve
        (False, sebep) doner: uydurma irtifa yazmak, sessiz ve tehlikeli
        bir HOME hatasi uretir.

        Doner: (basarili: bool, sebep: str)  — sebep yalniz hata halinde.
        """
        try:
            sysid = int(sysid)
        except (TypeError, ValueError):
            return (False, f"Gecersiz sysid: {sysid}")
        master = self.master_bul(sysid)
        if master is None:
            self.konsol("KOMUT", "HOME ayarlanamadi: MAVLink baglantisi "
                                 "yok.", "hata")
            return (False, "MAVLink baglantisi yok")

        mevcut_kip = (lat is None or lon is None)
        if mevcut_kip:
            try:
                master.mav.command_long_send(
                    sysid, 1,
                    mavutil.mavlink.MAV_CMD_DO_SET_HOME,
                    0,
                    1,                 # param1=1 -> mevcut konumu kullan
                    0, 0, 0, 0, 0, 0)
            except Exception as e:
                self.konsol("KOMUT", f"HOME komut hatasi: {e}", "hata")
                return (False, str(e))
            self.konsol("KOMUT",
                        f"sysid={sysid} HOME = aracin mevcut konumu",
                        "basari")
        else:
            try:
                lat = float(lat)
                lon = float(lon)
            except (TypeError, ValueError):
                return (False, "Gecersiz koordinat")
            with self.kilit:
                d = dict(self.dronlar.get(sysid) or {})
            if not d or d.get("lat") is None:
                # Telemetri yok: zemin AMSL'i kestirilemez.
                self.konsol("KOMUT",
                            f"sysid={sysid} HOME ayarlanamadi: telemetri "
                            f"yok (irtifa kestirilemiyor)", "hata")
                return (False, "Telemetri yok: HOME irtifasi "
                               "kestirilemiyor")
            zemin_amsl = (float(d.get("alt_msl") or 0.0)
                          - float(d.get("alt_rel") or 0.0))
            try:
                master.mav.command_long_send(
                    sysid, 1,
                    mavutil.mavlink.MAV_CMD_DO_SET_HOME,
                    0,
                    0,                 # param1=0 -> belirtilen konumu kullan
                    0, 0, 0,
                    lat, lon, zemin_amsl)
            except Exception as e:
                self.konsol("KOMUT", f"HOME komut hatasi: {e}", "hata")
                return (False, str(e))
            self.konsol("KOMUT",
                        f"sysid={sysid} HOME = {lat:.6f},{lon:.6f} "
                        f"@ {zemin_amsl:.0f}m AMSL (zemin kestirimi)",
                        "basari")

        # Otopilot HOME'u kabul ederse HOME_POSITION'i yeniden yayar, ancak
        # bu garanti degildir (SET_MESSAGE_INTERVAL destegi olmayan
        # firmware'lerde hic yayilmaz). Arayuzun yeni HOME'u gormesi icin
        # mesaj ACIKCA istenir; boylece harita ikonu ve hazirlik denetimi
        # 5 saniyelik periyodu beklemeden tazelenir.
        try:
            master.mav.command_long_send(
                sysid, 1, mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE,
                0, 242, 0, 0, 0, 0, 0, 0)
        except Exception:
            pass
        return (True, "")

    # ------------------------------------------------------------------
    # Parametre arama ve serbest yazma (yeni popup icin)
    # ------------------------------------------------------------------
    def param_ara(self, sysid, filtre=""):
        """Drondan tum parametreleri ister ve filtreli sozluk olarak dondurur.

        PARAM_VALUE mesajlari _dongu thread'i tarafindan kuyruğa konulur;
        bu metot yalnizca kuyruktan okur — esanli recv_match cagrisi yok,
        dolasiyla thread guvenlidir.
        """
        master = self.master_bul(sysid)
        if master is None:
            self.konsol("PARAM", "MAVLink baglantisi yok.", "hata")
            return {}
        q = _queue.Queue()
        with self._param_kilit:
            self._param_kuyruk[int(sysid)] = q
        try:
            master.mav.param_request_list_send(int(sysid), 1)
            params = {}
            beklenen = None
            bitis = time.time() + 5.0
            while time.time() < bitis:
                try:
                    msg = q.get(timeout=0.5)
                except _queue.Empty:
                    if params:
                        break   # Bir sure mesaj gelmedi, mevcut set yeterli
                    continue
                ad = msg.param_id.rstrip('\x00')
                params[ad] = msg.param_value
                if beklenen is None:
                    beklenen = msg.param_count
                if beklenen and len(params) >= beklenen:
                    break
        finally:
            with self._param_kilit:
                self._param_kuyruk.pop(int(sysid), None)
        filtre_up = filtre.upper().strip()
        if filtre_up:
            return {k: v for k, v in params.items()
                    if filtre_up in k.upper()}
        return params

    def param_coklu_oku(self, sysid, adlar, zaman_asimi=3.0):
        """v2.4.21: verilen parametreleri TEK TEK, hedefli okur.

        param_ara tum listeyi ister (1300+ mesaj); burada yalnizca
        istenen adlar icin PARAM_REQUEST_READ gonderilir. Aracta
        bulunmayan adlar sonucta yer almaz (hata degil).
        Donus: {ad: deger}
        """
        master = self.master_bul(sysid)
        if master is None or not adlar:
            return {}
        sysid = int(sysid)
        q = _queue.Queue()
        with self._param_kilit:
            self._param_kuyruk[sysid] = q
        bulunan = {}
        try:
            hedefler = [str(a).upper()[:16] for a in adlar]
            for ad in hedefler:
                try:
                    master.mav.param_request_read_send(
                        sysid, 1, ad.encode("ascii"), -1)
                except Exception:
                    pass
            bitis = time.time() + float(zaman_asimi)
            kalan = set(hedefler)
            while time.time() < bitis and kalan:
                try:
                    msg = q.get(timeout=0.3)
                except _queue.Empty:
                    continue
                ad = msg.param_id.rstrip('\x00').upper()
                if ad in kalan:
                    bulunan[ad] = msg.param_value
                    kalan.discard(ad)
        finally:
            with self._param_kilit:
                self._param_kuyruk.pop(sysid, None)
        return bulunan

    def param_tumu_oku(self, sysid, ilerleme_cb=None):
        """Drondan TUM parametreleri eksiksiz okur (v2.4.15).

        param_ara'dan farklari:
        - param_index/param_count takibi: hangi indexlerin geldigi bilinir
        - Sessizlik durumunda eksik indexler PARAM_REQUEST_READ ile tek tek
          istenir (2 tamamlama turu) — dusuk bant genisliginde kaybolan
          PARAM_VALUE'lar telafi edilir
        - Genel sure 60 sn (dusuk baud telemetride tam liste uzun surer)
        - ilerleme_cb(alinan, toplam): UI ilerleme cubugu icin periyodik
          cagrilir (thread baglaminda)

        Donus: (params_sozluk, toplam_beklenen, hata_str_veya_None).
        """
        master = self.master_bul(sysid)
        if master is None:
            self.konsol("PARAM", "MAVLink baglantisi yok.", "hata")
            return {}, 0, "MAVLink baglantisi yok"
        sysid = int(sysid)
        q = _queue.Queue()
        with self._param_kilit:
            self._param_kuyruk[sysid] = q
        params = {}          # ad -> deger
        index_gelen = set()  # gelen param_index'ler
        beklenen = 0
        hata = None

        def _liste_iste(comp):
            """PARAM_REQUEST_LIST gonder; yazma hatasini yakala."""
            try:
                master.mav.param_request_list_send(sysid, comp)
                return None
            except Exception as e:
                return f"Istek gonderilemedi: {e}"

        try:
            hata = _liste_iste(1)
            if hata:
                self.dkonsol(sysid, "PARAM", f"{hata}", "hata")
                return {}, 0, hata
            bitis = time.time() + 60.0
            son_ilerleme = 0.0
            sessiz_baslangic = None
            tamamlama_turu = 0
            # v2.4.16: ilk istege hic yanit gelmezse listeyi yeniden iste.
            # 2. denemede component=0 (broadcast), 3. denemede master'in
            # kendi hedef komponenti — bazi telsiz/kopru kurulumlarinda
            # component=1 hedefli istek drona ulasmayabiliyor.
            yeniden_istek = 0
            son_istek = time.time()

            def _ilerleme():
                if ilerleme_cb:
                    try:
                        ilerleme_cb(len(params), beklenen)
                    except Exception:
                        pass

            while time.time() < bitis:
                try:
                    msg = q.get(timeout=0.5)
                    sessiz_baslangic = None
                except _queue.Empty:
                    # Sessizlik: liste bitti mi yoksa paketler mi kayboldu?
                    if not params:
                        # v2.4.16: hic yanit yok — 3 sn'de bir yeniden iste
                        if (time.time() - son_istek >= 3.0
                                and yeniden_istek < 2):
                            yeniden_istek += 1
                            comp = (0 if yeniden_istek == 1 else
                                    getattr(master, "target_component", 1)
                                    or 1)
                            self.konsol(
                                "PARAM",
                                f"sysid={sysid} yanit yok — liste yeniden "
                                f"isteniyor (deneme {yeniden_istek + 1}, "
                                f"comp={comp})", "uyari")
                            h = _liste_iste(comp)
                            if h:
                                hata = h
                                break
                            son_istek = time.time()
                        elif (time.time() - son_istek >= 6.0
                                and yeniden_istek >= 2):
                            hata = ("Dron parametre istegine yanit vermiyor. "
                                    "Telemetri baglantisi tek yonlu olabilir "
                                    "(GCS'den drona veri gidemiyor) veya "
                                    "baglanti dusuk bant genisliginde.")
                            self.konsol("PARAM",
                                        f"sysid={sysid} {hata}", "hata")
                            break
                        continue
                    if beklenen and len(params) >= beklenen:
                        break
                    if sessiz_baslangic is None:
                        sessiz_baslangic = time.time()
                        continue
                    if time.time() - sessiz_baslangic < 2.0:
                        continue
                    # 2 sn sessizlik: eksikleri tek tek iste (en fazla 3 tur)
                    if beklenen and tamamlama_turu < 3:
                        tamamlama_turu += 1
                        eksikler = [i for i in range(beklenen)
                                    if i not in index_gelen]
                        self.konsol(
                            "PARAM",
                            f"sysid={sysid} eksik {len(eksikler)} parametre "
                            f"tek tek isteniyor (tur {tamamlama_turu})")
                        for i in eksikler[:400]:
                            try:
                                master.mav.param_request_read_send(
                                    sysid, 1, b"", i)
                                time.sleep(0.005)
                            except Exception:
                                break
                        sessiz_baslangic = None
                        continue
                    break   # tamamlama turlari bitti veya beklenen yok
                ad = msg.param_id.rstrip('\x00')
                if not ad:
                    continue
                params[ad] = msg.param_value
                try:
                    idx = int(msg.param_index)
                    if idx != 65535:
                        index_gelen.add(idx)
                except Exception:
                    pass
                if not beklenen:
                    try:
                        beklenen = int(msg.param_count) or 0
                    except Exception:
                        beklenen = 0
                if beklenen and len(params) >= beklenen:
                    _ilerleme()
                    break
                if time.time() - son_ilerleme >= 0.4:
                    son_ilerleme = time.time()
                    _ilerleme()
        finally:
            with self._param_kilit:
                self._param_kuyruk.pop(sysid, None)
        _ilerleme()
        if params:
            hata = None   # kismi/tam veri geldiyse hata sayma
            self.konsol("PARAM",
                        f"sysid={sysid} {len(params)}/{beklenen or '?'} "
                        f"parametre okundu.")
        return params, beklenen, hata

    def param_tek_yaz(self, sysid, param_ad, deger):
        """Drona herhangi bir parametreyi yazar (serbest — kısıtlama yok)."""
        master = self.master_bul(sysid)
        if master is None:
            self.konsol("PARAM", "MAVLink baglantisi yok.", "hata")
            return False
        try:
            v = float(deger)
        except (TypeError, ValueError):
            self.konsol("PARAM", f"Gecersiz deger: {deger}", "hata")
            return False
        try:
            master.mav.param_set_send(
                int(sysid), 1, param_ad.encode("ascii"), v,
                mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
            self.konsol("PARAM",
                        f"sysid={sysid} {param_ad} = {v:g} yazildi", "basari")
            return True
        except Exception as e:
            self.konsol("PARAM", f"Parametre yazma hatasi: {e}", "hata")
            return False

    # ==================================================================
    # v2.5.0: MOTOR TESTI (MAV_CMD_DO_MOTOR_TEST 209)
    # ==================================================================
    # MOTOR_TEST_SINIR: (alt, ust) deger sinirlari test tipine gore.
    #   0 = yuzde gaz (%), 1 = PWM (us), 2 = pilot gazi gecisi
    # Tip 2 deger almaz (pilotun gaz kolu kullanilir).
    MOTOR_TEST_SINIR = {0: (0.0, 100.0), 1: (800.0, 2200.0),
                        2: (0.0, 0.0)}
    MOTOR_TEST_AZAMI_SURE = 10.0     # saniye
    MOTOR_TEST_AZAMI_MOTOR = 12      # motor sirasi ust siniri

    def motor_test_gonder(self, sysid, motor, tip=0, deger=5.0,
                          sure=2.0, adet=0, sira=0):
        """Tek motoru veya sirayla tum motorlari test eder.

        MAV_CMD_DO_MOTOR_TEST (209):
          p1 = motor sirasi (1..N; ArduPilot'ta MOTOR SIRASI, kanal degil)
          p2 = test tipi (0=%gaz, 1=PWM, 2=pilot gazi)
          p3 = deger
          p4 = sure (s)
          p5 = motor sayisi (0 = yalniz p1'deki motor)
          p6 = test sirasi (0 = varsayilan/motor sirasi, 1 = sirayla)

        GUVENLIK KAPISI: arac ARM EDILMISSE test REDDEDILIR. Motor testi
        pervaneler donerken yapilan bir islemdir; armli araca ayrica
        motor komutu gondermek ongorulemez davranis uretir.

        Donus: (basari: bool, sebep: str)
        """
        try:
            sysid = int(sysid)
            motor = int(motor)
            tip = int(tip)
            deger = float(deger)
            sure = float(sure)
            adet = int(adet)
            sira = int(sira)
        except (TypeError, ValueError):
            return (False, "Gecersiz motor testi parametresi")
        if tip not in self.MOTOR_TEST_SINIR:
            return (False, f"Bilinmeyen test tipi: {tip}")
        if not (1 <= motor <= self.MOTOR_TEST_AZAMI_MOTOR):
            return (False,
                    f"Motor sirasi 1-{self.MOTOR_TEST_AZAMI_MOTOR} "
                    "araliginda olmali")
        if not (0.1 <= sure <= self.MOTOR_TEST_AZAMI_SURE):
            return (False,
                    f"Sure 0.1-{self.MOTOR_TEST_AZAMI_SURE:g} s "
                    "araliginda olmali")
        alt, ust = self.MOTOR_TEST_SINIR[tip]
        if tip != 2:
            if not (alt <= deger <= ust):
                return (False,
                        f"Deger {alt:g}-{ust:g} araliginda olmali")
        with self.kilit:
            _d = self.dronlar.get(sysid, {})
            _armli = bool(_d.get("armed"))
        if _armli:
            return (False,
                    "Arac ARM EDILMIS durumda. Motor testi icin once "
                    "disarm edin.")
        master = self.master_bul(sysid)
        if master is None:
            return (False, "MAVLink baglantisi yok")
        try:
            master.mav.command_long_send(
                sysid, 1,
                mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST,
                0,
                motor, tip, deger, sure, adet, sira, 0)
        except Exception as e:
            return (False, f"Komut gonderilemedi: {e}")
        with self.kilit:
            if sysid in self.dronlar:
                self.dronlar[sysid]["motor_test_bitis"] = (
                    time.time() + sure)
        _tip_ad = {0: "%gaz", 1: "PWM", 2: "pilot gazi"}[tip]
        _kapsam = (f"motor {motor}" if adet <= 0
                   else f"{adet} motor sirayla (motor {motor}'den)")
        self.dkonsol(sysid, "MOTOR",
                     f"TEST: {_kapsam}, {_tip_ad}={deger:g}, "
                     f"{sure:g} s", "uyari")
        self.konsol("MOTOR",
                    f"sysid={sysid} motor testi: {_kapsam} "
                    f"{_tip_ad}={deger:g} {sure:g}s", "uyari")
        return (True, "")

    def motor_test_durdur(self, sysid):
        """Motor testini durdurur: sure=0 ile yeniden komut gonderir.

        ArduPilot'ta motor testini erken kesmenin yolu ayni komutu
        sure=0 ile gondermektir. Ayrica guvenlik icin gaz degeri de
        sifirlanir.
        """
        try:
            sysid = int(sysid)
        except (TypeError, ValueError):
            return (False, "Gecersiz sysid")
        master = self.master_bul(sysid)
        if master is None:
            return (False, "MAVLink baglantisi yok")
        try:
            master.mav.command_long_send(
                sysid, 1,
                mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST,
                0,
                1, 0, 0, 0, 0, 0, 0)
        except Exception as e:
            return (False, f"Komut gonderilemedi: {e}")
        with self.kilit:
            if sysid in self.dronlar:
                self.dronlar[sysid]["motor_test_bitis"] = 0.0
        self.dkonsol(sysid, "MOTOR", "TEST DURDURULDU", "basari")
        return (True, "")

    def ivme_yon_onay(self, sysid, yon_kod):
        """Alti yonlu ivme kalibrasyonunda YON ONAYI gonderir.

        ArduPilot her yon yerlestirildikten sonra onay bekler; onay
        gelmezse kalibrasyon ilk yonde takili kalir.

        MAV_CMD_ACCELCAL_VEHICLE_POS (42429), param1 = yon kodu.
        Enum pymavlink'ten olculdu:
          1 LEVEL - 2 LEFT - 3 RIGHT - 4 NOSEDOWN - 5 NOSEUP - 6 BACK

        Donus: (basari: bool, sebep: str)
        """
        try:
            sysid = int(sysid)
            yon_kod = int(yon_kod)
        except (TypeError, ValueError):
            return (False, "Gecersiz sysid ya da yon kodu")
        # Aralik disi deger araca GONDERILMEZ: ArduPilot tanimadigi
        # degeri sessizce yutar, operator kalibrasyonun neden
        # ilerlemedigini anlayamaz.
        if yon_kod < 1 or yon_kod > 6:
            return (False,
                    f"Yon kodu 1-6 arasi olmali (gelen: {yon_kod})")
        master = self.master_bul(sysid)
        if master is None:
            return (False, "MAVLink baglantisi yok")
        _adlar = {1: "duz (level)", 2: "sol yani", 3: "sag yani",
                  4: "burun asagi", 5: "burun yukari", 6: "sirti ustu"}
        try:
            master.mav.command_long_send(
                sysid, 1,
                42429,      # MAV_CMD_ACCELCAL_VEHICLE_POS
                0, yon_kod, 0, 0, 0, 0, 0, 0)
        except Exception as e:
            return (False, f"Komut gonderilemedi: {e}")
        self.dkonsol(sysid, "KALIB",
                     f"ivme yon onayi: {_adlar[yon_kod]}", "basari")
        return (True, "")

    # ==================================================================
    # v2.5.0: KALIBRASYON OTURUMU (mesaj suzgeci)
    # ==================================================================
    # Operator istegi: "tum kalibrasyon mesajlarini ve degerlerini
    # gostersin". Mevcut STATUSTEXT tamponu (mesaj_listesi) dronun TUM
    # mesajlarini tutar; kalibrasyon penceresi bunlarin arasindan
    # yalniz OTURUM BASLANGICINDAN SONRAKILERI gostermelidir, aksi
    # halde eski PreArm uyarilari kalibrasyon mesaji sanilir.
    def kalib_oturum_baslat(self, sysid, tur):
        """Kalibrasyon oturumu acar (mesaj suzgeci icin zaman damgasi)."""
        try:
            sysid = int(sysid)
        except (TypeError, ValueError):
            return
        if not hasattr(self, "_kalib_oturum"):
            self._kalib_oturum = {}
        self._kalib_oturum[sysid] = {"tur": str(tur),
                                     "bas": time.time()}
        with self.kilit:
            if sysid in self.dronlar and str(tur) == "pusula":
                # Yeni pusula oturumunda eski rapor SILINIR; aksi halde
                # onceki kalibrasyonun degerleri yeni oturumun sonucu
                # sanilir.
                self.dronlar[sysid]["magkal_rapor"] = None
                self.dronlar[sysid]["magkal_durum"] = ""
                self.dronlar[sysid]["magkal_pct"] = 0

    def kalib_mesajlari(self, sysid):
        """Oturum baslangicindan sonraki STATUSTEXT mesajlarini dondurur.

        Donus: {"tur": str, "bas": float, "mesajlar": [...]}
        Oturum yoksa bos mesaj listesi doner.
        """
        try:
            sysid = int(sysid)
        except (TypeError, ValueError):
            return {"tur": "", "bas": 0.0, "mesajlar": []}
        otr = getattr(self, "_kalib_oturum", {}).get(sysid)
        if not otr:
            return {"tur": "", "bas": 0.0, "mesajlar": []}
        bas = float(otr.get("bas", 0.0))
        with self._mesaj_kilit:
            liste = list(self.mesajlar.get(sysid, []))
        # En yeni ustte (mesaj_listesi sozlesmesiyle ayni yon)
        suzuk = [m for m in liste if float(m.get("ts", 0)) >= bas]
        return {"tur": otr.get("tur", ""), "bas": bas,
                "mesajlar": list(reversed(suzuk))}

    # ==================================================================
    # v2.5.0: ILK AYAR PARAMETRELERI (Mission Planner "Initial Tune")
    # ==================================================================
    # Mission Planner'in ekrani iki girdi alir: pervane capi (inc) ve
    # pil hucre sayisi (S). Bunlardan PID ve suzgec ONGORULERI uretir.
    # Ongoru DOGRUDAN YAZILMAZ: once operatore gosterilir, onaydan
    # sonra yazilir. Hesap YALNIZ burada yapilir (tek dogruluk kaynagi).
    #
    # Formuller ArduPilot'un kendi onerdigi baslangic degerleridir.
    # Kucuk pervane -> yuksek P ve yuksek suzgec kesim frekansi;
    # buyuk pervane -> dusuk P, dusuk kesim (buyuk pervane yavas tepki
    # verir ve daha cok titresim uretir).
    ILK_AYAR_ALANLAR = (
        "INS_GYRO_FILTER", "INS_ACCEL_FILTER",
        "ATC_RAT_RLL_FLTD", "ATC_RAT_RLL_FLTT",
        "ATC_RAT_PIT_FLTD", "ATC_RAT_PIT_FLTT",
        "ATC_RAT_YAW_FLTE", "ATC_RAT_YAW_FLTT",
        "ATC_ACCEL_R_MAX", "ATC_ACCEL_P_MAX", "ATC_ACCEL_Y_MAX",
        "MOT_THST_EXPO", "MOT_THST_HOVER", "MOT_SPIN_MAX",
        "MOT_BAT_VOLT_MAX", "MOT_BAT_VOLT_MIN",
        "ATC_THR_MIX_MAN",
    )

    @staticmethod
    def _dogrusal_ara(x, noktalar):
        """Noktalar arasinda dogrusal aradeger; disinda uc degeri sabit.

        noktalar: artan x sirasinda ((x1,y1),(x2,y2),...)
        ArduPilot belgesi degerleri AYRIK capilar icin verir (5/10/20");
        aradaki capilar icin dogrusal aradeger uretilir, uclarda ise
        belgenin "veya daha buyuk" ifadesi geregi deger SABIT tutulur.
        """
        if x <= noktalar[0][0]:
            return float(noktalar[0][1])
        if x >= noktalar[-1][0]:
            return float(noktalar[-1][1])
        for i in range(len(noktalar) - 1):
            x1, y1 = noktalar[i]
            x2, y2 = noktalar[i + 1]
            if x1 <= x <= x2:
                t = (x - x1) / float(x2 - x1)
                return float(y1 + t * (y2 - y1))
        return float(noktalar[-1][1])

    def batarya_voltaj_kalibre_et(self, sysid, gercek_voltaj):
        """Gercek olculen voltajdan BATT_VOLT_MULT degerini hesaplar/yazar.

        Formul Mission Planner ile aynidir:
        yeni_carpan = mevcut_carpan x gercek_voltaj / telemetri_voltaj.
        Islem sadece DISARM durumda, canli telemetri ve okunmus parametre
        varken yapilir. Parametre yazimi bu metotta yalniz BATT_VOLT_MULT
        beyaz listesine sabitlenmistir.
        """
        try:
            sysid = int(sysid)
            gercek = float(gercek_voltaj)
        except (TypeError, ValueError):
            return {"basari": False, "sebep": "Gecerli bir gercek voltaj girin."}
        if not (5.0 <= gercek <= 80.0):
            return {"basari": False,
                    "sebep": "Gercek voltaj 5-80 V araliginda olmali."}
        with self.kilit:
            dron = dict(self.dronlar.get(sysid) or {})
        if not dron:
            return {"basari": False, "sebep": "Dron telemetrisi bulunamadi."}
        if bool(dron.get("armed")):
            return {"basari": False,
                    "sebep": "Voltaj kalibrasyonu yalniz DISARM durumda yapilabilir."}
        try:
            okunan = float(dron.get("batarya_v") or 0.0)
        except (TypeError, ValueError):
            okunan = 0.0
        if not (5.0 <= okunan <= 80.0):
            return {"basari": False,
                    "sebep": "Canli batarya telemetrisi gecersiz veya henuz gelmedi."}
        try:
            paramler = self.param_coklu_oku(sysid, ["BATT_VOLT_MULT"])
            mevcut = float((paramler or {}).get("BATT_VOLT_MULT", 0.0))
        except Exception as e:
            self.konsol("PARAM", f"BATT_VOLT_MULT okunamadi: {e}", "hata")
            mevcut = 0.0
        if not (0.1 <= mevcut <= 20.0):
            return {"basari": False,
                    "sebep": "BATT_VOLT_MULT okunamadi. Parametreleri yeniden okuyun."}
        yeni = round(mevcut * gercek / okunan, 4)
        if not (0.1 <= yeni <= 20.0):
            return {"basari": False,
                    "sebep": "Hesaplanan carpan guvenli araligin disinda."}
        fark_yuzde = abs(yeni - mevcut) * 100.0 / mevcut
        # Akut telemetri bozulmasi veya yanlis multimetre girisinde parametrik
        # sicrama olmasin. Operatorden yeni bir okuma istenir.
        if fark_yuzde > 30.0:
            return {"basari": False,
                    "sebep": "Olcum farki %30'u asiyor; baglanti ve olcumu kontrol edin.",
                    "okunan_voltaj": round(okunan, 3),
                    "gercek_voltaj": round(gercek, 3),
                    "mevcut_carpan": mevcut,
                    "yeni_carpan": yeni}
        if not self.param_tek_yaz(sysid, "BATT_VOLT_MULT", yeni):
            return {"basari": False,
                    "sebep": "BATT_VOLT_MULT araca gonderilemedi."}
        return {"basari": True, "okunan_voltaj": round(okunan, 3),
                "gercek_voltaj": round(gercek, 3),
                "mevcut_carpan": mevcut, "yeni_carpan": yeni,
                "fark_yuzde": round(fark_yuzde, 2)}

    def ilk_ayar_ongoru(self, cap_inc, huc_sayisi=4):
        """Pervane capi (inc) ve pil hucresine gore baslangic ayarlari.

        KAYNAK: ArduPilot resmi belgesi "Setting the Aircraft Up for
        Tuning". Degerler UYDURULMAMIS, belgedeki tablodan alinmistir;
        ara capilar icin dogrusal aradeger uretilir.

        PID P/I/D DEGERLERI YAZILMAZ: belge, varsayilan eksen P/D/I
        degerlerinin cogu arac icin ilk hover'da guvenli oldugunu
        soyler. Ince ayar AUTOTUNE'un isidir. Bu yuzden ongoru YALNIZ
        suzgec, ivme siniri, itki egrisi ve pil gerilim araligini kapsar.

        Donus: {"girdi": {...}, "parametreler": {ad: deger},
                "notlar": [str]}  |  None (gecersiz girdi)
        """
        try:
            cap = float(cap_inc)
            huc = int(huc_sayisi)
        except (TypeError, ValueError):
            return None
        if not (3.0 <= cap <= 60.0):
            return None
        if not (2 <= huc <= 14):
            return None

        # --- Suzgecler (belge: 80 Hz @5", 40 Hz @10", 20 Hz @20"+) ---
        gyro_flt = self._dogrusal_ara(
            cap, ((5.0, 80.0), (10.0, 40.0), (20.0, 20.0)))
        # --- Itki egrisi (belge: 0.55 @5", 0.65 @10", 0.75 @20"+) ---
        expo = self._dogrusal_ara(
            cap, ((5.0, 0.55), (10.0, 0.65), (20.0, 0.75)))
        # --- Ivme sinirlari (belge: 1100 @10", 500 @20", 200 @30") ---
        # 5" icin belge deger vermez; 10" degerinin ustune cikilir
        # (kucuk arac daha hizli doner). ArduPilot varsayilani 110000
        # cdeg/s^2'dir; belgedeki 1100 degeri deg/s^2 biriminde
        # yazilmistir. Parametre birimi cdeg/s^2 oldugu icin 100 ile
        # carpilir.
        acc_rp_deg = self._dogrusal_ara(
            cap, ((10.0, 1100.0), (20.0, 500.0), (30.0, 200.0)))
        acc_y_deg = self._dogrusal_ara(
            cap, ((10.0, 200.0), (20.0, 100.0), (30.0, 90.0)))

        def yv(x, basamak=3):
            return round(float(x), basamak)

        p = {
            "INS_GYRO_FILTER": yv(gyro_flt, 1),
            "INS_ACCEL_FILTER": 10.0,
            # Belge: ATC_RAT_*_FLTD ve FLTT = INS_GYRO_FILTER / 2
            "ATC_RAT_RLL_FLTD": yv(gyro_flt / 2.0, 1),
            "ATC_RAT_RLL_FLTT": yv(gyro_flt / 2.0, 1),
            "ATC_RAT_PIT_FLTD": yv(gyro_flt / 2.0, 1),
            "ATC_RAT_PIT_FLTT": yv(gyro_flt / 2.0, 1),
            # Belge: ATC_RAT_YAW_FLTE = 2 (sabit)
            "ATC_RAT_YAW_FLTE": 2.0,
            "ATC_RAT_YAW_FLTT": yv(gyro_flt / 2.0, 1),
            # cdeg/s^2 birimine cevrim
            "ATC_ACCEL_R_MAX": yv(acc_rp_deg * 100.0, 0),
            "ATC_ACCEL_P_MAX": yv(acc_rp_deg * 100.0, 0),
            "ATC_ACCEL_Y_MAX": yv(acc_y_deg * 100.0, 0),
            "MOT_THST_EXPO": yv(expo, 3),
            # Belge: 0.25 veya beklenen hover itkisinin ALTI (guvenli)
            "MOT_THST_HOVER": 0.25,
            "MOT_SPIN_MAX": 0.95,
            # Gerilim sagmasini telafi icin pil araligi (LiPo)
            "MOT_BAT_VOLT_MAX": yv(4.2 * huc, 2),
            "MOT_BAT_VOLT_MIN": yv(3.3 * huc, 2),
            # Belge (Initial Tuning Flight): ilk ucuslarda 0.1
            "ATC_THR_MIX_MAN": 0.1,
        }
        notlar = [
            f"Kaynak: ArduPilot \"Setting the Aircraft Up for Tuning\" "
            f"resmi belgesi. Pervane {cap:g}\" ve {huc}S LiPo icin "
            "hesaplandi.",
            "PID (P/I/D) DEGERLERI YAZILMAZ: resmi belge varsayilan "
            "eksen P/D/I degerlerinin ilk hover icin guvenli oldugunu "
            "belirtir. Ince ayar AUTOTUNE ile yapilmalidir.",
            "MOT_SPIN_ARM ve MOT_SPIN_MIN motor testi ile elle "
            "belirlenmelidir; bu ongoru onlari YAZMAZ.",
            f"Pil araligi 4.2 x {huc} = {4.2 * huc:.1f} V / "
            f"3.3 x {huc} = {3.3 * huc:.1f} V (standart LiPo). "
            "Farkli kimya kullaniyorsaniz elle duzeltin.",
        ]
        if cap >= 20:
            notlar.append(
                "Buyuk pervane: itki egrisi dogrusalligi kritiktir. "
                "MOT_THST_EXPO degerinin itki sehpasi olcumuyle "
                "dogrulanmasi onerilir (uretici verisine guvenilmemeli).")
        if cap <= 5:
            notlar.append(
                "Kucuk pervane: 80 Hz jiroskop suzgeci yuksek kesimdir; "
                "ilk ucusta VIBE kayitlari izlenmeli, gurultu varsa "
                "notch suzgeci (INS_HNTCH_*) yapilandirilmalidir.")
        if huc >= 6:
            notlar.append(
                f"{huc}S gerilim yuksek: MOT_SPIN_ARM/MIN degerlerinin "
                "motor testiyle yeniden belirlenmesi onerilir.")
        return {"girdi": {"cap_inc": cap, "hucre": huc},
                "parametreler": p, "notlar": notlar}

    def ilk_ayar_uygula(self, sysid, parametreler):
        """Onaylanan ilk ayar parametrelerini drona yazar.

        YALNIZ ILK_AYAR_ALANLAR beyaz listesindeki adlar yazilir; boylece
        arayuzden gelen govde keyfi parametre yazmak icin kullanilamaz.
        Donus: (yazilan: int, hatalar: [str])
        """
        if not isinstance(parametreler, dict):
            return (0, ["Gecersiz parametre govdesi"])
        yazilan = 0
        hatalar = []
        for ad, deger in parametreler.items():
            ad = str(ad).strip().upper()
            if ad not in self.ILK_AYAR_ALANLAR:
                hatalar.append(f"{ad}: beyaz listede yok, atlandi")
                continue
            if self.param_tek_yaz(sysid, ad, deger):
                yazilan += 1
            else:
                hatalar.append(f"{ad}: yazilamadi")
        self.dkonsol(sysid, "AYAR",
                     f"ILK AYAR: {yazilan} parametre yazildi"
                     + (f", {len(hatalar)} hata" if hatalar else ""),
                     "basari" if yazilan and not hatalar else "uyari")
        return (yazilan, hatalar)

    # ------------------------------------------------------------------
    # Dataflash log yonetimi (LOG_REQUEST_LIST / LOG_REQUEST_DATA)
    # ------------------------------------------------------------------
    def log_listesi(self, sysid):
        """Drondaki dataflash log listesini ister ve dondurur.

        LOG_ENTRY mesajlari _dongu thread'i tarafindan kuyruğa konulur;
        bu metot yalnizca kuyruktan okur (param_ara ile ayni kalip).
        Donus: [{"id", "boyut", "zaman_utc"}] (id'ye gore sirali)
        """
        sysid = int(sysid)
        master = self.master_bul(sysid)
        if master is None:
            self.konsol("LOG", "MAVLink baglantisi yok.", "hata")
            return None
        q = _queue.Queue()
        with self._log_kilit:
            self._log_kuyruk[sysid] = q
        loglar = {}
        try:
            master.mav.log_request_list_send(sysid, 1, 0, 0xFFFF)
            beklenen = None
            bitis = time.time() + 8.0
            while time.time() < bitis:
                try:
                    msg = q.get(timeout=1.0)
                except _queue.Empty:
                    if loglar:
                        break  # bir sure mesaj gelmedi, mevcut set yeterli
                    continue
                if msg.get_type() != "LOG_ENTRY":
                    continue
                if beklenen is None:
                    beklenen = msg.num_logs
                if beklenen == 0:
                    break  # dronda hic log yok
                loglar[msg.id] = {
                    "id": int(msg.id),
                    "boyut": int(msg.size),
                    "zaman_utc": int(msg.time_utc),
                }
                if len(loglar) >= beklenen:
                    break
        finally:
            with self._log_kilit:
                self._log_kuyruk.pop(sysid, None)
        sonuc = [loglar[i] for i in sorted(loglar)]
        self.dkonsol(sysid, "LOG", f"{len(sonuc)} log listelendi.")
        return sonuc

    def log_indirme_iptal(self, sysid):
        """v2.4.23: surmekte olan log indirmesini durdurur.

        Bayrak set edilir; log_indir dongusu bir sonraki turda cikar,
        dosya YAZILMAZ ve durum "iptal" olur.
        """
        try:
            sysid = int(sysid)
        except (TypeError, ValueError):
            return False
        with self._log_kilit:
            self._log_iptal.add(sysid)
        # Kuyruga sahte uyandirma koy ki q.get(timeout) beklemesin
        with self._log_kilit:
            q = self._log_kuyruk.get(sysid)
        if q is not None:
            try:
                q.put_nowait(None)
            except Exception:
                pass
        self.dkonsol(sysid, "LOG", f"log indirme iptal istendi.",
                    "uyari")
        return True

    def log_indir(self, sysid, log_id, boyut, hedef_yol, ilerleme_cb=None):
        """Belirtilen logu LOG_REQUEST_DATA ile indirir ve dosyaya yazar.

        ilerleme_cb(alinan, toplam) her ~%1'de cagrilir (WS yayini icin).
        Donus: True/False (basari). v2.4.23: kullanici
        log_indirme_iptal() cagirirsa indirme yarida kesilir.
        """
        sysid = int(sysid)
        log_id = int(log_id)
        boyut = int(boyut)
        master = self.master_bul(sysid)
        if master is None:
            self.konsol("LOG", "MAVLink baglantisi yok.", "hata")
            return False
        with self._log_kilit:
            self._log_iptal.discard(sysid)   # onceki iptali temizle
        q = _queue.Queue()
        with self._log_kilit:
            self._log_kuyruk[sysid] = q
        with self.kilit:
            self.log_ilerleme[sysid] = {
                "log_id": log_id, "alinan": 0,
                "toplam": boyut, "durum": "indiriliyor"}
        PARCA = 90  # LOG_DATA yuku (MAVLink sabiti)
        veri = bytearray(boyut)
        alinan = {}          # ofset -> uzunluk (tekrarlari ayikla)
        toplam_alinan = 0
        son_bildirim = 0.0
        basarili = False
        iptal = False
        try:
            # Tum dosyayi tek istekle iste; dron LOG_DATA parcalari yagdirir
            master.mav.log_request_data_send(
                sysid, 1, log_id, 0, 0xFFFFFFFF)
            zaman_asimi = time.time() + 20.0  # veri geldikce uzatilir
            while toplam_alinan < boyut and time.time() < zaman_asimi:
                # v2.4.23: kullanici DURDUR'a bastiysa cik
                with self._log_kilit:
                    if sysid in self._log_iptal:
                        iptal = True
                if iptal:
                    break
                try:
                    msg = q.get(timeout=2.0)
                except _queue.Empty:
                    # Eksik bolgeyi yeniden iste (basit kurtarma)
                    eksik = self._ilk_eksik(alinan, boyut, PARCA)
                    if eksik is None:
                        break
                    master.mav.log_request_data_send(
                        sysid, 1, log_id, eksik, 0xFFFFFFFF)
                    continue
                if msg is None:          # iptal uyandirmasi
                    continue
                if msg.get_type() != "LOG_DATA" or msg.id != log_id:
                    continue
                n = int(msg.count)
                ofs = int(msg.ofs)
                if n <= 0 or ofs >= boyut:
                    continue
                n = min(n, boyut - ofs)
                if ofs not in alinan:
                    veri[ofs:ofs + n] = bytes(msg.data[:n])
                    alinan[ofs] = n
                    toplam_alinan += n
                zaman_asimi = time.time() + 20.0
                simdi = time.time()
                if ilerleme_cb and simdi - son_bildirim >= 0.4:
                    son_bildirim = simdi
                    with self.kilit:
                        self.log_ilerleme[sysid]["alinan"] = toplam_alinan
                    try:
                        ilerleme_cb(toplam_alinan, boyut)
                    except Exception:
                        pass
            basarili = (not iptal) and toplam_alinan >= boyut
        finally:
            try:
                master.mav.log_request_end_send(sysid, 1)
            except Exception:
                pass
            with self._log_kilit:
                self._log_kuyruk.pop(sysid, None)
                self._log_iptal.discard(sysid)
            with self.kilit:
                self.log_ilerleme[sysid] = {
                    "log_id": log_id, "alinan": toplam_alinan,
                    "toplam": boyut,
                    "durum": ("tamam" if basarili
                              else ("iptal" if iptal else "hata"))}
        if iptal:
            self.dkonsol(sysid, "LOG", f"log {log_id} indirme "
                        f"kullanici tarafindan durduruldu "
                        f"({toplam_alinan}/{boyut}).", "uyari")
            return False
        if basarili:
            import os as _os
            _os.makedirs(_os.path.dirname(hedef_yol), exist_ok=True)
            with open(hedef_yol, "wb") as f:
                f.write(veri)
            self.dkonsol(sysid, "LOG", f"log {log_id} indirildi "
                        f"({boyut} bayt) -> {hedef_yol}", "basari")
        else:
            self.dkonsol(sysid, "LOG", f"log {log_id} indirme "
                        f"eksik kaldi ({toplam_alinan}/{boyut}).", "hata")
        if ilerleme_cb:
            try:
                ilerleme_cb(toplam_alinan, boyut)
            except Exception:
                pass
        return basarili

    @staticmethod
    def _ilk_eksik(alinan, boyut, parca):
        """Alinan ofset haritasinda ilk eksik ofseti bulur."""
        ofs = 0
        for k in sorted(alinan):
            if k > ofs:
                return ofs
            ofs = max(ofs, k + alinan[k])
        return ofs if ofs < boyut else None
