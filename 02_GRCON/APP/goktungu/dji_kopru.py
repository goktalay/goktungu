# -*- coding: utf-8 -*-
"""DjiKopruYoneticisi: GOKTUNGU DJI Kopru Protokolu (GDP) sunucusu.

DJI dronlari MAVLink konusmaz; Mobile SDK (Android kopru uygulamasi
com.veilox.goktungu) veya Onboard SDK (osdk_adaptor) calistiran istemciler
bu TCP sunucusuna baglanir ve satir-ayrilmis JSON (NDJSON) mesajlariyla
telemetri gonderir / komut alir.

Protokol (her satir bir JSON nesnesi):
  istemci -> sunucu:
    {"tip":"merhaba","sdk":"msdk"|"osdk","sn":"...","model":"...",
     "fw":"...","video_url":"http://<cihaz>:8654/akis"}
    {"tip":"telemetri","lat":..,"lon":..,"alt_msl":..,"alt_rel":..,
     "heading":..,"hiz":..,"vz":..,"roll":..,"pitch":..,
     "batarya_pct":..,"batarya_v":..,"gps_fix":..,"uydu":..,
     "mod":"GPS","armed":true,"ucusta":true,"ev_lat":..,"ev_lon":..}
    {"tip":"yanit","komut_id":N,"sonuc":"tamam"|"hata","mesaj":"..."}
    {"tip":"param_liste","parametreler":{"ad":deger,...}}
    {"tip":"gorev_durum","durum":"...","nokta":N}
  sunucu -> istemci:
    {"tip":"komut","id":N,"ad":"arm|disarm|takeoff|land|rtl|goto|hiz|
      dur|gimbal|foto|video_baslat|video_durdur|gorev_yukle|
      gorev_baslat|gorev_durdur|param_oku|param_yaz","args":{...}}

Sanal sysid uzayi: DJI araclar 1000'den itibaren numaralanir; boylece
MAVLink sysid'leri (1-255) ile cakismaz ve mevcut arayuz/izin/angajman
katmanlari dronu normal bir dron gibi gorur.
"""
import hmac
import json
import socket
import threading
import time

DJI_SYSID_TABAN = 1000

# DJI ucus modu -> GCS mod etiketi esleme (arayuz tutarliligi icin)
DJI_MOD_ESLEME = {
    "GPS_ATTI": "LOITER", "GPS": "LOITER", "ATTI": "ALT_HOLD",
    "MANUAL": "STABILIZE", "GO_HOME": "RTL", "AUTO_LANDING": "LAND",
    "TAKE_OFF": "GUIDED", "VIRTUAL_STICK": "GUIDED",
    "WAYPOINT": "AUTO", "SPORT": "LOITER", "TRIPOD": "LOITER",
    "CINEMATIC": "LOITER", "SMART": "LOITER",
}


class DjiKopruYoneticisi:
    """Her 'dji' baglanti kaydi icin bir TCP dinleyici isletir."""

    def __init__(self, konsol, dron_yonetici, kilit):
        self.konsol = konsol
        self.dron = dron_yonetici
        self.kilit = kilit
        # bid -> {"soket","thread","durdur","durum","hata","isim","port",
        #         "istemciler": {sysid: {"soket","adres","sn","sdk",
        #                                 "model","video_url","kilit"}}}
        self.sunucular = {}
        # GUVENLIK (BULGU_07): GDP belirtec dogrulamasi icin ayar
        # erisimi. Kurucu imzasi DEGISTIRILMEDI (main.py:410 cagri
        # yeri kirilmasin); alan sonradan atanir ve None'a dayaniklidir
        # — ayar yoksa dogrulama guvenli tarafa duser (yalniz yerel).
        self.ayarlar = None
        self._sysid_sayac = DJI_SYSID_TABAN
        self._sayac_kilit = threading.Lock()
        self._komut_id = 0
        # sn -> sysid kalici eslesmesi (ayni dron tekrar baglaninca
        # ayni sanal sysid'yi alir -> isim/renk/gecmis korunur)
        self._sn_sysid = {}

    # ------------------------------------------------------------------
    # Dinleyici yasam dongusu (BaglantiYoneticisi kayitlari uzerinden)
    # ------------------------------------------------------------------
    def dinle(self, kayit):
        """'dji' turu baglanti kaydini dinlemeye baslar."""
        bid = int(kayit["id"])
        self.durdur(bid)
        try:
            port = int(kayit.get("port") or 8790)
        except (TypeError, ValueError):
            port = 8790
        durdur = threading.Event()
        s = {"soket": None, "thread": None, "durdur": durdur,
             "durum": "baglaniyor", "hata": "",
             "isim": kayit.get("isim", "?"), "port": port,
             "istemciler": {}}
        self.sunucular[bid] = s
        t = threading.Thread(target=self._sunucu_dongu,
                             args=(bid, port, durdur), daemon=True)
        s["thread"] = t
        t.start()
        return True

    def durdur(self, bid):
        bid = int(bid)
        s = self.sunucular.get(bid)
        if not s:
            return
        s["durdur"].set()
        sk = s.get("soket")
        if sk:
            try:
                sk.close()
            except OSError:
                pass
        # Istemci soketlerini kapat ve dronlari modelden dusur
        for sysid, ist in list(s["istemciler"].items()):
            try:
                ist["soket"].close()
            except OSError:
                pass
            self._dron_dusur(sysid)
        s["istemciler"].clear()
        t = s.get("thread")
        if t and t.is_alive():
            t.join(timeout=2.0)
        self.sunucular.pop(bid, None)

    def durumlar(self):
        """WS yayini icin durum ozetleri (DronYoneticisi.durumlar ile
        ayni bicim)."""
        return {str(bid): {"durum": s.get("durum", "kapali"),
                           "hata": s.get("hata", "")}
                for bid, s in self.sunucular.items()}

    # ------------------------------------------------------------------
    # TCP sunucu dongusu
    # ------------------------------------------------------------------
    def _sunucu_dongu(self, bid, port, durdur):
        s = self.sunucular.get(bid)
        if s is None:
            return
        etiket = s.get("isim", str(bid))
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("0.0.0.0", port))
            srv.listen(8)
            srv.settimeout(1.0)
        except OSError as e:
            s.update(durum="hata", hata=str(e))
            self.konsol("DJI", f"[{etiket}] Port {port} acilamadi: {e}",
                        "hata")
            return
        s["soket"] = srv
        s["durum"] = "bagli"
        self.konsol("DJI", f"[{etiket}] DJI koprusu dinleniyor "
                    f"(TCP {port})", "basari")
        # Terminale de yaz: kullanici sunucu acilisinda hangi portun
        # dinlendigini dogrudan gorsun
        print(f"[DJI] {etiket}: DJI koprusu dinleniyor: 0.0.0.0:{port} "
              f"(Android/OSDK istemcileri bu porta baglanmali)")
        while not durdur.is_set():
            try:
                istemci, adres = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            t = threading.Thread(target=self._istemci_dongu,
                                 args=(bid, istemci, adres, durdur),
                                 daemon=True)
            t.start()
        try:
            srv.close()
        except OSError:
            pass

    def _istemci_dongu(self, bid, soket, adres, durdur):
        s = self.sunucular.get(bid)
        if s is None:
            soket.close()
            return
        etiket = s.get("isim", str(bid))
        self.konsol("DJI", f"[{etiket}] Istemci baglandi: {adres[0]}")
        # Istemci dron bagli degilken telemetri gondermez; 5 sn'de bir
        # 'kalp' mesaji gonderir. 30 sn hicbir veri gelmezse dusurulur.
        soket.settimeout(30.0)
        sysid = None
        tampon = b""
        kopma_neden = "istemci kapatti"
        try:
            while not durdur.is_set():
                try:
                    veri = soket.recv(65536)
                except socket.timeout:
                    kopma_neden = "30 sn veri gelmedi (zaman asimi)"
                    break
                except OSError as e:
                    kopma_neden = f"soket hatasi: {e}"
                    break
                if not veri:
                    break
                tampon += veri
                while b"\n" in tampon:
                    satir, tampon = tampon.split(b"\n", 1)
                    satir = satir.strip()
                    if not satir:
                        continue
                    try:
                        m = json.loads(satir.decode("utf-8"))
                    except (ValueError, UnicodeDecodeError):
                        continue
                    try:
                        sysid = self._mesaj_isle(bid, soket, adres,
                                                 sysid, m)
                    except Exception as e:  # noqa: BLE001
                        # Tek mesajdaki beklenmedik hata istemciyi
                        # dusurmemeli — baglanti korunur, neden loglanir
                        self.konsol("DJI", f"[{etiket}] Mesaj isleme "
                                    f"hatasi ({m.get('tip')}): {e}",
                                    "hata")
        finally:
            try:
                soket.close()
            except OSError:
                pass
            if sysid is not None:
                s["istemciler"].pop(sysid, None)
                self._dron_dusur(sysid)
                self.konsol("DJI", f"[{etiket}] Istemci ayrildi: "
                            f"sysid={sysid} ({kopma_neden})", "uyari")
            else:
                self.konsol("DJI", f"[{etiket}] Istemci ayrildi: "
                            f"{adres[0]} ({kopma_neden})", "uyari")


    # ------------------------------------------------------------------
    # GUVENLIK (BULGU_07): GDP istemci kimlik dogrulamasi
    # ------------------------------------------------------------------
    # `merhaba` mesaji istemcinin bildirdigi `sn` disinda hicbir kimlik
    # tasimiyordu. Yerel agdaki herhangi bir cihaz sahte dron enjekte
    # edebilir, hatta gercek bir dronun `sn` degerini bilerek onun
    # `sysid`'sini ele gecirebilirdi (`_sn_sysid` eslemesi seri
    # numarasina guveniyor). Operator sahte telemetriye gore karar
    # verirdi.
    #
    # Belirtec `ayarlar` tablosunda `dji_belirtec` anahtarinda durur ve
    # `Ayarlar.GIZLI_ANAHTARLAR` icinde oldugu icin arayuze YAYILMAZ.
    def _belirtec_dogrula(self, m, adres):
        """`merhaba` mesajindaki belirteci dogrular.

        (kabul: bool, neden: str) dondurur.
        """
        try:
            bekleyen = ""
            if self.ayarlar is not None:
                bekleyen = str(
                    (self.ayarlar.yukle() or {}).get("dji_belirtec") or "")
        except Exception:  # noqa: BLE001
            # Ayar okunamazsa GUVENLI TARAFA dusulur: yalniz yerel
            # baglanti kabul edilir. Ayar hatasi kapiyi ACMAZ.
            bekleyen = ""

        yerel = str(adres[0]) in ("127.0.0.1", "::1", "localhost")

        if not bekleyen:
            # Belirtec yapilandirilmamis. Kurulumu kilitlemek yerine
            # yalniz yerel istemciye izin verilir: kopru ayni makinede
            # kosuyorsa calismaya devam eder, LAN'dan sahte istemci
            # giremez.
            if yerel:
                return True, ""
            return False, ("belirtec yapilandirilmamis; yalniz yerel "
                           "istemci kabul edilir")

        gelen = str(m.get("belirtec") or "")
        if not gelen:
            return False, "belirtec yok"
        # Sabit zamanli karsilastirma: duz `==` karakter karakter kisa
        # devre yapar ve zamanlama farki belirteci tahmin etmeye yardim
        # eder.
        if not hmac.compare_digest(gelen, bekleyen):
            return False, "belirtec gecersiz"
        return True, ""

    # ------------------------------------------------------------------
    # Mesaj isleme
    # ------------------------------------------------------------------
    def _mesaj_isle(self, bid, soket, adres, sysid, m):
        tip = m.get("tip")
        s = self.sunucular.get(bid)
        if s is None:
            return sysid

        if tip == "merhaba":
            # GUVENLIK (BULGU_07): kimlik dogrulamasi `sn` okunmadan ve
            # `_sn_sysid` eslemesine DOKUNULMADAN once yapilir. Aksi
            # halde basarisiz deneme de sysid sayacini tuketir ve kalici
            # esleme kirlenir.
            kabul, neden = self._belirtec_dogrula(m, adres)
            if not kabul:
                self.konsol("DJI", f"[{s.get('isim', bid)}] Istemci "
                                   f"reddedildi ({adres[0]}): {neden}",
                            "hata")
                try:
                    soket.sendall(json.dumps(
                        {"tip": "hata", "kod": "kimlik",
                         "mesaj": neden}).encode() + b"\n")
                except OSError:
                    pass
                try:
                    soket.close()
                except OSError:
                    pass
                return None
            sn = str(m.get("sn") or adres[0])
            with self._sayac_kilit:
                if sn in self._sn_sysid:
                    sysid = self._sn_sysid[sn]
                else:
                    self._sysid_sayac += 1
                    sysid = self._sysid_sayac
                    self._sn_sysid[sn] = sysid
            s["istemciler"][sysid] = {
                "soket": soket, "adres": adres[0], "sn": sn,
                "sdk": str(m.get("sdk") or "msdk"),
                "model": str(m.get("model") or "DJI"),
                "video_url": str(m.get("video_url") or ""),
                "kilit": threading.Lock(),
                "merhaba": dict(m),   # dron modelini gec olusturmak icin
            }
            self.konsol("DJI", f"DJI istemci katildi: {m.get('model')} "
                        f"SN={sn} -> sysid={sysid} (dron bekleniyor)",
                        "basari")
            # Dron modeli HEMEN olusturulmaz: istemci koprude olsa da
            # dron (urun) RC'ye bagli olmayabilir. Model ilk telemetri
            # geldiginde olusturulur — DRONLAR paneline bos kart dusmez.

        elif tip == "telemetri" and sysid is not None:
            # Ilk telemetri = dron gercekten bagli -> modeli olustur
            with self.kilit:
                var = sysid in self.dron.dronlar
            if not var:
                ist = s["istemciler"].get(sysid) or {}
                self._dron_olustur(bid, sysid,
                                   ist.get("merhaba") or {},
                                   ist.get("sn") or str(adres[0]))
                self.konsol("DJI", f"DJI dron katildi: "
                            f"{(ist.get('merhaba') or {}).get('model')} "
                            f"SN={ist.get('sn')} -> sysid={sysid}",
                            "basari")
            self._telemetri_isle(sysid, m)

        elif tip == "kalp":
            # Canlilik mesaji: dron urunu bagli olmasa da istemci soketi
            # canli tutar. 'urun': false -> dron koptu, modelden dusur.
            if sysid is not None:
                if m.get("urun") is False:
                    with self.kilit:
                        var = sysid in self.dron.dronlar
                    if var:
                        self._dron_dusur(sysid)
                        self.konsol("DJI", f"DJI dron ayrildi: "
                                    f"sysid={sysid} (urun koptu, "
                                    f"istemci bagli)", "uyari")
                else:
                    with self.kilit:
                        d = self.dron.dronlar.get(sysid)
                        if d:
                            d["son_mesaj"] = time.time()

        elif tip == "yanit":
            son = m.get("sonuc", "?")
            sev = "basari" if son == "tamam" else "hata"
            self.konsol("DJI", f"sysid={sysid} komut #{m.get('komut_id')}"
                        f" -> {son} {m.get('mesaj', '')}", sev)

        elif tip == "param_liste" and sysid is not None:
            ist = s["istemciler"].get(sysid)
            if ist is not None:
                ist["param_liste"] = m.get("parametreler") or {}

        elif tip == "gorev_durum" and sysid is not None:
            with self.kilit:
                d = self.dron.dronlar.get(sysid)
                if d:
                    try:
                        d["mission_seq"] = int(m.get("nokta") or -1)
                    except (TypeError, ValueError):
                        pass
        return sysid

    def _dron_olustur(self, bid, sysid, m, sn):
        with self.kilit:
            d = self.dron.dronlar.get(sysid)
            if d is None:
                d = self.dron.dron_kaydi_olustur(sysid)
                self.dron.dronlar[sysid] = d
            model = str(m.get("model") or "DJI")
            d["tip"] = "DJI"
            d["kaynak"] = "dji"
            d["model"] = model
            d["uid"] = sn
            d["isim"] = f"{model}-{sysid}"
            d["arac_tipi"] = 2  # quadcopter gibi davran
            d["son_mesaj"] = time.time()
            # Kayitli isim varsa uygula (UID tabanli isimlendirme)
            isim = self.dron._uid_ile_isim_coz(sysid, sn)
            if isim:
                d["kullanici_isim"] = isim
            self.dron.sysid_baglanti[sysid] = bid
        # v2.4.21: DJI seri numarasi dogal benzersiz kimlik -> kalici
        # kayit + baglanti oturumu (self.kilit birakildiktan sonra)
        try:
            self.dron.kimlik_kaydet(sysid, sn, "dji_sn")
        except Exception as e:
            self.konsol("DJI", f"sysid={sysid} kimlik kaydi hatasi: {e}",
                        "hata")

    def _telemetri_isle(self, sysid, m):
        def _f(ad, vars=0.0):
            try:
                v = m.get(ad)
                return float(v) if v is not None else vars
            except (TypeError, ValueError):
                return vars
        with self.kilit:
            d = self.dron.dronlar.get(sysid)
            if d is None:
                return
            d["son_mesaj"] = time.time()
            if m.get("lat") is not None:
                d["lat"] = _f("lat")
                d["lon"] = _f("lon")
            d["alt_msl"] = _f("alt_msl", d.get("alt_msl", 0.0))
            d["alt_rel"] = _f("alt_rel", d.get("alt_rel", 0.0))
            d["heading"] = _f("heading", d.get("heading", 0.0))
            d["groundspeed"] = _f("hiz", d.get("groundspeed", 0.0))
            d["airspeed"] = d["groundspeed"]
            d["vz"] = _f("vz", d.get("vz", 0.0))
            d["roll"] = _f("roll", d.get("roll", 0.0))
            d["pitch"] = _f("pitch", d.get("pitch", 0.0))
            d["batarya_v"] = _f("batarya_v", d.get("batarya_v", 0.0))
            try:
                d["batarya_pct"] = int(m.get("batarya_pct", -1))
            except (TypeError, ValueError):
                pass
            try:
                d["gps_fix"] = int(m.get("gps_fix", 0))
                d["uydu"] = int(m.get("uydu", 0))
            except (TypeError, ValueError):
                pass
            ham_mod = str(m.get("mod") or "?").upper()
            d["mod"] = DJI_MOD_ESLEME.get(ham_mod, ham_mod)
            d["armed"] = bool(m.get("armed") or m.get("ucusta"))

    def _dron_dusur(self, sysid):
        with self.kilit:
            self.dron.dronlar.pop(sysid, None)
            self.dron.sysid_baglanti.pop(sysid, None)
        # v2.4.21: baglanti oturumunu kapat (telemetri kaydi son bulur)
        try:
            self.dron.oturum_kapat(sysid)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Komut gonderme (sunucu.py dron_komut yonlendirmesi buraya gelir)
    # ------------------------------------------------------------------
    def dji_mi(self, sysid):
        try:
            return int(sysid) >= DJI_SYSID_TABAN
        except (TypeError, ValueError):
            return False

    def _istemci_bul(self, sysid):
        sysid = int(sysid)
        for s in self.sunucular.values():
            ist = s["istemciler"].get(sysid)
            if ist is not None:
                return ist
        return None

    def gonder(self, sysid, ad, args=None):
        """DJI istemcisine komut mesaji yazar."""
        ist = self._istemci_bul(sysid)
        if ist is None:
            self.konsol("DJI", f"sysid={sysid} icin DJI baglantisi yok.",
                        "hata")
            return False
        self._komut_id += 1
        mesaj = {"tip": "komut", "id": self._komut_id,
                 "ad": str(ad), "args": args or {}}
        veri = (json.dumps(mesaj, ensure_ascii=False) + "\n").encode("utf-8")
        try:
            with ist["kilit"]:
                ist["soket"].sendall(veri)
            return True
        except OSError as e:
            self.konsol("DJI", f"sysid={sysid} komut gonderilemedi: {e}",
                        "hata")
            return False

    # Mevcut dron komut arayuzuyle uyum (DronYoneticisi.komut_gonder imzasi)
    def komut(self, sysid, aksiyon, irtifa=None):
        self.konsol("KOMUT", f"sysid={sysid} aksiyon={aksiyon} (DJI)")
        if aksiyon == "takeoff":
            try:
                h = float(irtifa) if irtifa is not None else 10.0
            except (TypeError, ValueError):
                h = 10.0
            return self.gonder(sysid, "takeoff", {"irtifa": h})
        if aksiyon in ("rtl", "land", "arm", "disarm"):
            return self.gonder(sysid, aksiyon)
        if aksiyon == "auto":
            return self.gonder(sysid, "gorev_baslat")
        if aksiyon == "altitude_change":
            try:
                h = float(irtifa) if irtifa is not None else 10.0
            except (TypeError, ValueError):
                h = 10.0
            return self.gonder(sysid, "irtifa", {"irtifa": h})
        if aksiyon == "set_mode":
            # DJI'da serbest mod secimi yok; guvenli eslesenler
            eslesme = {6: "rtl", 9: "land", 3: "gorev_baslat",
                       5: "dur", 4: "dur", 17: "dur"}
            try:
                hedef = eslesme.get(int(irtifa))
            except (TypeError, ValueError):
                hedef = None
            if hedef:
                return self.gonder(sysid, hedef)
            self.konsol("DJI", f"DJI icin desteklenmeyen mod: {irtifa}",
                        "uyari")
            return False
        if aksiyon.startswith("kalib_"):
            self.konsol("DJI", "Kalibrasyon islemleri DJI uygulamasi "
                        "uzerinden yapilmalidir.", "uyari")
            return False
        self.konsol("DJI", f"DJI icin desteklenmeyen aksiyon: {aksiyon}",
                    "uyari")
        return False

    def goto_gonder(self, sysid, lat, lon, irtifa=None):
        try:
            args = {"lat": float(lat), "lon": float(lon)}
        except (TypeError, ValueError):
            self.konsol("DJI", f"sysid={sysid} GOTO gecersiz koordinat",
                        "hata")
            return False
        if irtifa is not None:
            try:
                args["irtifa"] = float(irtifa)
            except (TypeError, ValueError):
                pass
        else:
            # Kayitli irtifa hedefi varsa koru (MAVLink davranisiyla ayni)
            hedef = self.dron.hedef_irtifa_rel.get(int(sysid))
            if hedef is not None:
                args["irtifa"] = float(hedef)
        return self.gonder(sysid, "goto", args)

    def hiz_gonder(self, sysid, vx, vy, vz, yaw_hizi=0.0):
        """Manuel kontrol (virtual stick) hiz komutu — m/s, derece/sn."""
        return self.gonder(sysid, "hiz", {
            "vx": vx, "vy": vy, "vz": vz, "yaw_hizi": yaw_hizi})

    def gimbal(self, sysid, pitch=None, yaw=None):
        args = {}
        if pitch is not None:
            args["pitch"] = pitch
        if yaw is not None:
            args["yaw"] = yaw
        return self.gonder(sysid, "gimbal", args)

    def param_ara(self, sysid, filtre=""):
        """DJI parametrelerini ister (senkron, 5 sn zaman asimli)."""
        ist = self._istemci_bul(sysid)
        if ist is None:
            return {}
        ist.pop("param_liste", None)
        if not self.gonder(sysid, "param_oku"):
            return {}
        bitis = time.time() + 5.0
        while time.time() < bitis:
            pl = ist.get("param_liste")
            if pl is not None:
                f = str(filtre or "").upper()
                if f:
                    return {k: v for k, v in pl.items()
                            if f in k.upper()}
                return dict(pl)
            time.sleep(0.1)
        return {}

    def param_yaz(self, sysid, ad, deger):
        return self.gonder(sysid, "param_yaz",
                           {"ad": str(ad), "deger": deger})

    def gorev_yukle(self, sysid, noktalar):
        """Waypoint gorevi yukler.
        noktalar: [{"lat","lon","alt"}, ...]"""
        return self.gonder(sysid, "gorev_yukle", {"noktalar": noktalar})

    def video_url(self, sysid):
        """Istemcinin bildirdigi MJPEG video URL'si (kamera yonetimi)."""
        ist = self._istemci_bul(sysid)
        return ist.get("video_url", "") if ist else ""

    def cihazlar(self):
        """Bagli DJI cihazlarinin ozeti (kamera ekleme UI icin)."""
        liste = []
        for bid, s in self.sunucular.items():
            for sysid, ist in s["istemciler"].items():
                liste.append({
                    "sysid": sysid, "sn": ist.get("sn", ""),
                    "model": ist.get("model", "DJI"),
                    "sdk": ist.get("sdk", ""),
                    "video_url": ist.get("video_url", ""),
                    "baglanti": s.get("isim", str(bid)),
                })
        return liste
