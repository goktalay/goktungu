# -*- coding: utf-8 -*-
"""BaglantiYoneticisi: MAVLink baglanti kayitlarini SQLite'ta saklar.

Mevcut gcs_baglantilar.json varsa ilk calistirmada otomatik aktarilir.
"""
import json
import threading

from .sabitler import PROJE_KOKU, _veri_yolu
from .veritabani import baglanti, tablolari_olustur

import os
DOSYA_ESKI = _veri_yolu("gcs_baglantilar.json")

# v2.4.39: "sanal" turu eklendi. Kullanici karari geregi sanal dron bir
# taklit (mock) DEGIL: her sanal dron gercek bir ArduPilot SITL surecidir
# (arducopter/arduplane). Boylece parametreler, ARM denetimleri, ucus
# modlari ve gorev davranisi gercek ucus yazilimiyla birebir ayni olur;
# angajman denemeleri anlamli hale gelir.
#
# SITL SERIAL0'i bir TCP portunda DINLER, bu yuzden GOKTUNGU ona ISTEMCI
# olarak baglanir -> mavutil_url() "tcp:..." dondurur (bkz. NOT_SITL_2439).
# v2.4.53: "merkez" turu — merkez sunucu uzerinden ACIK bir saha
# sunucusuna baglanmak icin. Kullanici istegi (birebir):
#   "kullanici sisteme baglanti yoneticisi bolumunde bir baglanti
#    ekleyeceginde sistem acik olan sunuculari gostersin ve kullanici
#    secsin, iletisim tek tarafli olacak ... kullanicilarin kurdugu
#    sunucularin sabit ip'si yok"
#
# Saha sunucularinin sabit IP'si yoktur; merkeze KENDILERI baglanir
# (ters WebSocket). Bu yuzden bu tur bir MAVLink adresi tasimaz:
# hedef sunucu merkezdeki `ornek_uid` ile adreslenir ve trafik merkez
# rolesi uzerinden akar. `mavutil_url()` bu turde BOS dondurur —
# dogrudan MAVLink baglantisi kurulmaz.
GECERLI_TURLER = ("seri", "tcp", "udp", "dji", "sanal", "merkez")

# v2.4.142: Tasima turu ve ucus yazilimi AYRI kavramlardir. Eski
# kayitlarda alan bulunmadigindan `ardupilot` varsayimi, calisan MAVLink
# baglantilarini degistirmeden korur. Betaflight ilk katmanda yalniz
# seri/VCP-UART MSP salt-okunur tanilamasi icin desteklenir.
UCUS_YAZILIMLARI = ("otomatik", "ardupilot", "betaflight", "dji")

# SITL'in SERIAL0 taban portu bu araliktan secilir. Kullaniciya port
# sorulmaz (istekte yok), dahili atanir.
#
# ONEMLI: SITL taban porttan itibaren BIR PORT BLOGU baglar (SERIAL0=base,
# SERIAL1=base+2, SERIAL2=base+3 ...). Blogun herhangi bir uyesi doluysa
# SITL "bind failed ... Address already in use" diyip cikis kodu 1 ile
# OLUR (olculdu). Bu yuzden portlar ADIM ADIM degil SANAL_PORT_ADIM kadar
# atlanarak dagitilir ve blok bosluk denetimi sitl.py'de yapilir.
SANAL_PORT_BASI = 15670
SANAL_PORT_ADIM = 10
SANAL_TIPLER = ("multirotor", "sabit_kanat", "interceptor")


class BaglantiYoneticisi:

    def __init__(self, konsol):
        self.konsol = konsol
        self._kilit = threading.Lock()
        tablolari_olustur()
        self._json_goc()

    # ------------------------------------------------------------------
    # JSON → SQLite gocu
    # ------------------------------------------------------------------
    @staticmethod
    def ucus_yazilimi_coz(tur, deger=None):
        """Ucus yazilimini turle birlikte guvenli sekilde dogrular.

        DJI istemciden gelen secimi ASLA kabul etmez; kendi surucusu
        degismeden `dji` olur. Eski/bos alanlar ArduPilot'a duser. MSP
        v1 ilk surumu TCP/UDP/Merkez/SITL uzerinde tanimli degildir;
        sadece seri portta kullanilabilir. Bu kural arayuzden bagimsiz
        oldugu icin eski istemci veya dogrudan WS istegiyle atlatilamaz.
        """
        tur = str(tur or "").strip().lower()
        if tur == "dji":
            return "dji", None
        yazilim = str(deger or "ardupilot").strip().lower()
        if yazilim not in ("otomatik", "ardupilot", "betaflight"):
            return None, "Gecersiz ucus yazilimi."
        if yazilim in ("otomatik", "betaflight") and tur != "seri":
            return None, ("Otomatik algilama ve Betaflight ilk surumde yalniz "
                          "seri/RFD900 veya MSP etkin VCP portunda desteklenir.")
        return yazilim, None

    @classmethod
    def _kayit_normallestir(cls, kayit):
        """Eski satirlari calisan ArduPilot kaydi olarak sunar."""
        m = dict(kayit or {})
        yazilim, _ = cls.ucus_yazilimi_coz(
            m.get("tur"), m.get("ucus_yazilimi"))
        # Bozuk eski metin yuzunden liste/arayuz kesilmesin; bu sadece
        # okuma geri dususudur. Yeni kayit/guncelleme yolu hata verir.
        m["ucus_yazilimi"] = yazilim or ("dji" if m.get("tur") == "dji"
                                         else "ardupilot")
        return m

    def _json_goc(self):
        with baglanti() as con:
            if con.execute(
                    "SELECT COUNT(*) FROM baglantilar").fetchone()[0] > 0:
                return
        if not os.path.isfile(DOSYA_ESKI):
            return
        try:
            with open(DOSYA_ESKI, "r", encoding="utf-8") as f:
                liste = json.load(f).get("baglantilar", [])
        except Exception:
            return
        with baglanti() as con:
            for b in liste:
                con.execute(
                    "INSERT OR IGNORE INTO baglantilar "
                    "(id, isim, tur, port, baud, host, ucus_yazilimi) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (b["id"], b["isim"], b["tur"], b["port"],
                     b.get("baud"), b.get("host"),
                     self.ucus_yazilimi_coz(
                         b.get("tur"), b.get("ucus_yazilimi"))[0]
                     or "ardupilot"),
                )
        print(f"[BAGLANTI] gcs_baglantilar.json -> gcs.db aktarildi "
              f"({len(liste)} kayit).")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def listele(self, firma_id=None):
        """Kayitli baglantilari dondurur.

        v2.4.53: `firma_id` verilirse (merkezde calisan cok firmali
        ornek) yalnizca o firmanin ve sahipsiz kayitlari doner. Lokal
        kurulumda parametre verilmez ve tum kayitlar doner.
        """
        from . import veritabani as _vt
        kosul, arg = "", []
        try:
            kosul, arg = _vt.firma_kosulu("baglantilar", firma_id)
        except Exception:
            kosul, arg = "", []
        sql = "SELECT * FROM baglantilar"
        if kosul:
            sql += " WHERE " + kosul
        sql += " ORDER BY id"
        with baglanti() as con:
            rows = con.execute(sql, arg).fetchall()
        return [self._kayit_normallestir(r) for r in rows]

    def bul(self, bid):
        with baglanti() as con:
            row = con.execute(
                "SELECT * FROM baglantilar WHERE id = ?", (int(bid),)
            ).fetchone()
        return self._kayit_normallestir(row) if row else None

    def ekle(self, isim, tur, port, baud=None, host=None,
             firma_id=None, kopru_ornek_id=None, ucus_yazilimi=None):
        tur = str(tur or "").lower().strip()
        if tur not in GECERLI_TURLER:
            return None, "Gecersiz baglanti turu."
        ucus_yazilimi, hata = self.ucus_yazilimi_coz(tur, ucus_yazilimi)
        if hata:
            return None, hata
        isim = str(isim or "").strip()
        if not isim:
            return None, "Baglanti adi bos olamaz."
        port = str(port or "").strip()
        if not port:
            if tur == "dji":
                port = "8790"  # DJI koprusu varsayilan dinleme portu
            elif tur == "sanal":
                port = str(self._bos_sanal_port())
            elif tur == "merkez":
                # Merkez turunde port ANLAMSIZDIR: hedef sunucu merkez
                # rolesi uzerinden ornek_uid ile adreslenir. Kolonu
                # NULL birakmak yerine "0" yaziyoruz; tablo semasi
                # degismeden calisir (kullanicinin v2.4.24
                # veritabanini korumak zorundayiz).
                port = "0"
            else:
                return None, "Port bos olamaz."

        kayit = {"isim": isim, "tur": tur, "port": port,
                 "baud": None, "host": None,
                 "ucus_yazilimi": ucus_yazilimi}
        if tur == "seri":
            try:
                kayit["baud"] = int(baud or 57600)
            except (TypeError, ValueError):
                kayit["baud"] = 57600
        elif tur == "tcp":
            host = str(host or "").strip()
            if not host:
                return None, "Sunucu adresi (host) bos olamaz."
            kayit["host"] = host
        elif tur == "merkez":
            # v2.4.53: merkez sunucu kaydinin bilgileri `host` alaninda
            # "uid|ad|firma" olarak saklanir. Neden yeni kolon degil:
            # sanal turde alinan karar burada da gecerli — kolon eklemek
            # surum gecisi gerektirir ve sahadaki veritabani korunmali.
            ok, hata = self._merkez_host_kur(kayit, host)
            if not ok:
                return None, hata
        elif tur == "sanal":
            # v2.4.39: sanal dronun tanimlayici bilgileri (tip, baslangic
            # konumu, adet) `host` alaninda "tip|lat|lon|adet" olarak
            # saklanir. Neden yeni kolon degil: baglantilar tablosuna kolon
            # eklemek surum gecisi (migration) gerektirir ve kullanicinin
            # calisan v2.4.24 kurulumundaki veritabani korunmak zorunda.
            # `host` sanal turde baska hicbir amacla kullanilmiyor.
            ok, hata = self._sanal_host_kur(kayit, host)
            if not ok:
                return None, hata

        with self._kilit:
            with baglanti() as con:
                # v2.4.53: merkezde cok firmali calisirken kayit
                # olusturan pilotun firmasina baglanir; kolon yoksa
                # (lokal / eski veritabani) eski INSERT kullanilir.
                from . import veritabani as _vt
                _fk = False
                try:
                    _fk = bool(firma_id) and _vt.firma_kolonu_var(
                        "baglantilar")
                except Exception:
                    _fk = False
                # v2.4.53 Faz 7: kayit bir KOPRU makinesine baglanabilir.
                # Kolon yoksa (lokal / eski veritabani) alan hic yazilmaz.
                _kk = False
                try:
                    _kk = (kopru_ornek_id is not None
                           and _vt.kolon_var("baglantilar",
                                             "kopru_ornek_id"))
                except Exception:
                    _kk = False

                alanlar = ["isim", "tur", "port", "baud", "host"]
                degerler = [kayit["isim"], kayit["tur"], kayit["port"],
                            kayit["baud"], kayit["host"]]
                _uy = False
                try:
                    _uy = _vt.kolon_var("baglantilar", "ucus_yazilimi")
                except Exception:
                    _uy = False
                if _uy:
                    alanlar.append("ucus_yazilimi")
                    degerler.append(kayit["ucus_yazilimi"])
                if _fk:
                    alanlar.append("firma_id")
                    degerler.append(int(firma_id))
                    kayit["firma_id"] = int(firma_id)
                if _kk:
                    alanlar.append("kopru_ornek_id")
                    degerler.append(int(kopru_ornek_id))
                    kayit["kopru_ornek_id"] = int(kopru_ornek_id)
                cur = con.execute(
                    "INSERT INTO baglantilar (%s) VALUES (%s)"
                    % (", ".join(alanlar),
                       ",".join("?" * len(alanlar))),
                    tuple(degerler),
                )
                kayit["id"] = cur.lastrowid
        self.konsol("BAGLANTI",
                    f"Kayit eklendi: {isim} ({tur})", "basari")
        return dict(kayit), None

    def guncelle(self, bid, **alanlar):
        with self._kilit:
            with baglanti() as con:
                row = con.execute(
                    "SELECT * FROM baglantilar WHERE id = ?", (int(bid),)
                ).fetchone()
                if not row:
                    return None
                m = self._kayit_normallestir(row)
                for ad in ("isim", "tur", "port", "baud", "host"):
                    if ad in alanlar and alanlar[ad] is not None:
                        m[ad] = alanlar[ad]
                # Tür değişimi de yazılım doğrulamasını yeniden çalıştırır:
                # örneğin Betaflight seri kaydını TCP'ye çeviren eski bir
                # istemci, yazılım alanını göndermese bile sunucu tarafından
                # reddedilir. DJI ise her koşulda kendi sürücüsüne sabitlenir.
                yazilim_adayi = alanlar.get("ucus_yazilimi",
                                            m.get("ucus_yazilimi"))
                yazilim, hata = self.ucus_yazilimi_coz(
                    m.get("tur"), yazilim_adayi)
                if hata:
                    raise ValueError(hata)
                m["ucus_yazilimi"] = yazilim
                # v2.4.55: kopru_ornek_id AYRI ele alinir, cunku gecerli
                # bir deger olarak None tasir ("merkezin kendi makinesi").
                # Yukaridaki `is not None` suzgecine konulsa, bir kaydi
                # kopruden koparmak imkansiz olurdu.
                if "kopru_ornek_id" in alanlar:
                    kid = alanlar["kopru_ornek_id"]
                    m["kopru_ornek_id"] = (None if kid in (None, "", 0, "0")
                                           else int(kid))
                con.execute(
                    "UPDATE baglantilar "
                    "SET isim=?, tur=?, port=?, baud=?, host=?,"
                    "    ucus_yazilimi=?, kopru_ornek_id=? WHERE id=?",
                    (m["isim"], m["tur"], m["port"],
                     m["baud"], m["host"], m["ucus_yazilimi"],
                     m.get("kopru_ornek_id"), int(bid)),
                )
                return m

    def sil(self, bid):
        with self._kilit:
            with baglanti() as con:
                cur = con.execute(
                    "DELETE FROM baglantilar WHERE id = ?", (int(bid),)
                )
                silindi = cur.rowcount > 0
        if silindi:
            self.konsol("BAGLANTI", f"Kayit silindi: id={bid}")
        return silindi

    # ------------------------------------------------------------------
    # v2.4.39: sanal baglanti yardimcilari
    # ------------------------------------------------------------------
    def _bos_sanal_port(self):
        """Kullanimda olmayan bir sanal port dondurur.

        Yalniz KAYITLI sanal baglantilara bakilir; isletim sisteminde o an
        acik olan portlara bakilmaz. Bir sanal kayit silinip yenisi
        eklendiginde ayni port yeniden kullanilabilir, bu istenen davranis.
        """
        kullanilan = set()
        try:
            for b in self.listele():
                if b.get("tur") == "sanal":
                    try:
                        kullanilan.add(int(b.get("port") or 0))
                    except (TypeError, ValueError):
                        pass
        except Exception:
            pass
        p = SANAL_PORT_BASI
        ust = SANAL_PORT_BASI + SANAL_PORT_ADIM * 50
        while p in kullanilan and p < ust:
            p += SANAL_PORT_ADIM
        return p

    @staticmethod
    def _sanal_host_kur(kayit, host):
        """`host` alanini "tip|lat|lon|adet" bicimine getirir.

        `host` cagiriciden ya hazir bu bicimde gelir (guncelleme yolu) ya da
        sunucu katmani sanal_* alanlarindan olusturur. Bicim bozuksa hata
        dondurulur; sessizce varsayilana dusmek, dronun kullanicinin
        beklemedigi bir konumda dogmasina yol acardi.
        """
        h = str(host or "").strip()
        par = h.split("|")
        if len(par) < 3:
            return False, "Sanal dron icin tip ve konum bilgisi gerekli."
        tip = (par[0] or "").strip().lower()
        if tip not in SANAL_TIPLER:
            return False, f"Gecersiz sanal dron tipi: {par[0]}"
        try:
            lat = float(par[1])
            lon = float(par[2])
        except (TypeError, ValueError):
            return False, "Sanal dron konumu sayisal olmali."
        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
            return False, "Sanal dron konumu gecersiz aralikta."
        try:
            adet = int(par[3]) if len(par) > 3 else 1
        except (TypeError, ValueError):
            adet = 1
        adet = max(1, min(10, adet))
        kayit["host"] = f"{tip}|{lat:.6f}|{lon:.6f}|{adet}"
        return True, None

    @staticmethod
    def _merkez_host_kur(kayit, host):
        """`host` alanini "uid|ad|firma" bicimine getirir.

        `uid` merkezdeki sunucu orneginin benzersiz kimligidir ve tek
        ZORUNLU alandir; `ad` ile `firma` yalniz arayuzde gostermek
        icindir (sunucu adi merkezde degisebilir, kayit bozulmasin).

        Bos uid ile kayit kabul edilmez: hedefsiz bir merkez baglantisi
        arayuzde "var" gorunup hicbir zaman calismaz — sessiz kusur.
        """
        h = str(host or "").strip()
        par = h.split("|")
        uid = (par[0] or "").strip()
        if not uid:
            return False, ("Merkez baglantisi icin sunucu secilmeli "
                           "(acik sunucu listesinden).")
        # Boru karakteri alan ayiricidir; adlarda gecerse bicim bozulur.
        ad = (par[1].strip() if len(par) > 1 else "").replace("|", " ")
        firma = (par[2].strip() if len(par) > 2 else "").replace("|", " ")
        kayit["host"] = f"{uid}|{ad}|{firma}"
        return True, None

    @staticmethod
    def merkez_coz(kayit):
        """Merkez kaydinin host alanini {uid, ad, firma} olarak coz.

        Bicim bozuksa None doner (cagirici baglantiyi baslatmaz).
        """
        if (kayit or {}).get("tur") != "merkez":
            return None
        par = str(kayit.get("host") or "").split("|")
        uid = (par[0] or "").strip()
        if not uid:
            return None
        return {
            "uid": uid,
            "ad": par[1].strip() if len(par) > 1 else "",
            "firma": par[2].strip() if len(par) > 2 else "",
        }

    @staticmethod
    def sanal_coz(kayit):
        """Sanal kaydin host alanini {tip, lat, lon, adet} olarak coz.

        Bicim bozuksa None doner (cagirici baglantiyi baslatmaz).
        """
        if (kayit or {}).get("tur") != "sanal":
            return None
        par = str(kayit.get("host") or "").split("|")
        if len(par) < 3:
            return None
        try:
            return {
                "tip": par[0] or "multirotor",
                "lat": float(par[1]),
                "lon": float(par[2]),
                "adet": max(1, min(10, int(par[3]) if len(par) > 3 else 1)),
            }
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Yardimci: mavutil baglanti dizesi
    # ------------------------------------------------------------------
    @staticmethod
    def mavutil_url(kayit):
        tur = kayit.get("tur")
        if tur == "seri":
            return kayit.get("port", "")
        if tur == "tcp":
            return f"tcp:{kayit.get('host', '')}:{kayit.get('port', '')}"
        if tur == "udp":
            return f"udpin:0.0.0.0:{kayit.get('port', '')}"
        if tur == "sanal":
            # SITL dinleyen taraftir; GOKTUNGU istemci olarak baglanir.
            # mavutil'de "tcp:" = istemci, "tcpin:" = sunucu (olculdu:
            # tcpin kullanmak "Address already in use" verir).
            return f"tcp:127.0.0.1:{kayit.get('port', '')}"
        # "merkez" turu bilincli olarak BOS doner: hedef sahadaki bir
        # sunucudur ve sabit IP'si yoktur; trafik merkez rolesi uzerinden
        # akar, dogrudan MAVLink soketi acilmaz.
        return ""
