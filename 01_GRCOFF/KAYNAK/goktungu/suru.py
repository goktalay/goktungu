# -*- coding: utf-8 -*-
"""SuruYoneticisi: Dron sürü uçuş (formasyon) motoru.

Master dron serbest uçar; slave dronlar master'ın konumuna göre
XYZ ofsetiyle sürekli yönlendirilir (GUIDED mod, 5 Hz).

XYZ anlamı (master gövde çerçevesi):
  x = ileri(+) / geri(-) metre (heading yönünde)
  y = sağ(+) / sol(-) metre
  z = yukarı(+) / aşağı(-) metre (alt_rel farkı)

Takeoff senkronu: master takeoff alırsa tüm slave'ler de takeoff alır
(z ofseti kadar irtifa farkıyla).
"""
import math
import threading
import time

from pymavlink import mavutil

from goktungu.angajman import haversine, bearing
from goktungu.takip_dron import _ofset_konum


class SuruYoneticisi:
    TAKIP_HZ = 5        # konum hedefi gönderme frekansı
    MIN_IRTIFA = 2.0    # güvenlik alt sınırı (m)

    def __init__(self, konsol, dron, kilit):
        """
        konsol : KonsolYoneticisi
        dron   : DronYoneticisi (MAVLink master, dronlar dict)
        kilit  : threading.Lock (paylaşılan)
        """
        self.konsol = konsol
        self.dron = dron
        self.kilit = kilit
        # Aktif sürü bilgisi
        self._suru = None  # None | dict (aşağıda yapı)
        # {
        #   "master_sysid": int,
        #   "slaves": {sysid: {"x": float, "y": float, "z": float}},
        #   "aktif": bool,
        #   "thread": Thread | None,
        #   "durdur": Event | None,
        # }

    # ------------------------------------------------------------------
    # Dış API
    # ------------------------------------------------------------------

    def kur(self, master_sysid, slaves):
        """Sürü tanımını oluşturur ve başlatır.

        master_sysid : int
        slaves       : list of {"sysid": int, "x": float, "y": float, "z": float}
        """
        master_sysid = int(master_sysid)
        if not slaves:
            self.konsol("SÜRÜ", "En az bir slave dron gerekli.", "hata")
            return False

        slave_dict = {}
        for s in slaves:
            sid = int(s["sysid"])
            if sid == master_sysid:
                self.konsol("SÜRÜ",
                            "Master dron slave olamaz.", "hata")
                return False
            slave_dict[sid] = {
                "x": float(s.get("x", 0)),
                "y": float(s.get("y", 0)),
                "z": float(s.get("z", 0)),
            }

        # Önceki sürü varsa dağıt
        if self._suru and self._suru["aktif"]:
            self.dagit(konsol_yaz=False)

        durdur = threading.Event()
        self._suru = {
            "master_sysid": master_sysid,
            "slaves": slave_dict,
            "aktif": True,
            "thread": None,
            "durdur": durdur,
        }

        t = threading.Thread(target=self._dongu, args=(durdur,), daemon=True)
        self._suru["thread"] = t
        t.start()

        slave_str = ", ".join(f"D{s}" for s in slave_dict)
        self.konsol("SÜRÜ",
                    f"Sürü başlatıldı: Master=D{master_sysid}, "
                    f"Slave'ler=[{slave_str}]", "basari")
        return True

    def dagit(self, konsol_yaz=True):
        """Sürüyü dağıtır: tüm slave'ler LOITER'a alınır."""
        if not self._suru:
            return
        self._suru["durdur"].set()
        self._suru["aktif"] = False
        # Slave'leri LOITER'a al
        for sid in list(self._suru["slaves"].keys()):
            self._loiter_yap(sid)
        if konsol_yaz:
            self.konsol("SÜRÜ", "Sürü dağıtıldı, tüm slave'ler LOITER.",
                        "uyari")
        self._suru = None

    def cikar(self, sysid):
        """Tek slave'i sürüden çıkarır (LOITER'a alır)."""
        if not self._suru:
            return False
        sysid = int(sysid)
        if sysid not in self._suru["slaves"]:
            return False
        del self._suru["slaves"][sysid]
        self._loiter_yap(sysid)
        self.konsol("SÜRÜ", f"D{sysid} sürüden çıkarıldı.", "uyari")
        # Slave kalmadıysa sürüyü dağıt
        if not self._suru["slaves"]:
            self.dagit()
        return True

    def master_takeoff(self, irtifa):
        """Master takeoff aldığında slave'lere de takeoff gönderir."""
        if not self._suru or not self._suru["aktif"]:
            return
        irtifa = float(irtifa) if irtifa else 10.0
        for sid, ofset in self._suru["slaves"].items():
            slave_irtifa = max(self.MIN_IRTIFA, irtifa + ofset["z"])
            self.dron.komut_gonder(sid, "takeoff", slave_irtifa)
            self.konsol("SÜRÜ",
                        f"D{sid} takeoff ({slave_irtifa:.0f}m)", "bilgi")

    def sessiz_durdur(self):
        """Bağlantı kesilirken çağrılır (LOITER göndermeden)."""
        if self._suru:
            self._suru["durdur"].set()
            self._suru["aktif"] = False
            self._suru = None

    def durum(self):
        """Telemetriye eklenecek sürü durum paketi."""
        if not self._suru or not self._suru["aktif"]:
            return None
        master_sysid = self._suru["master_sysid"]
        with self.kilit:
            m = self.dron.dronlar.get(master_sysid, {})
            m_lat = m.get("lat")
            m_lon = m.get("lon")
            m_alt = m.get("alt_rel", 0) or 0
            m_hdg = float(m.get("heading", 0) or 0)
            m_armed = m.get("armed", False)

        slave_durum = []
        mesafeler = []
        noktalar = []  # (sysid, lat, lon, alt) — mesafe hesabı için

        if m_lat is not None:
            noktalar.append((master_sysid, m_lat, m_lon, m_alt))

        for sid, ofset in self._suru["slaves"].items():
            with self.kilit:
                s = self.dron.dronlar.get(sid, {})
                s_lat = s.get("lat")
                s_lon = s.get("lon")
                s_alt = s.get("alt_rel", 0) or 0
                s_armed = s.get("armed", False)

            # Hedef konum hesapla (UI'da hayalet nokta için)
            hedef_lat, hedef_lon, hedef_alt = None, None, None
            if m_lat is not None:
                hedef_lat, hedef_lon, hedef_alt = self._hedef_hesapla(
                    m_lat, m_lon, m_alt, m_hdg, ofset)

            # Gerçek mesafe (master'a)
            gercek_mesafe = None
            if s_lat is not None and m_lat is not None:
                yatay = haversine(s_lat, s_lon, m_lat, m_lon)
                dikey = abs(s_alt - m_alt)
                gercek_mesafe = round(math.sqrt(yatay**2 + dikey**2), 1)

            # Hedef mesafe (ofset büyüklüğü)
            hedef_mesafe = round(
                math.sqrt(ofset["x"]**2 + ofset["y"]**2 + ofset["z"]**2), 1)

            slave_durum.append({
                "sysid": sid,
                "x": ofset["x"], "y": ofset["y"], "z": ofset["z"],
                "lat": s_lat, "lon": s_lon, "alt": round(s_alt, 1),
                "hedef_lat": hedef_lat, "hedef_lon": hedef_lon,
                "hedef_alt": round(hedef_alt, 1) if hedef_alt else None,
                "mesafe_gercek": gercek_mesafe,
                "hedef_mesafe": hedef_mesafe,
                "armed": s_armed,
            })

            if s_lat is not None:
                noktalar.append((sid, s_lat, s_lon, s_alt))

        # Tüm çiftler arası mesafe
        for i in range(len(noktalar)):
            for j in range(i + 1, len(noktalar)):
                a = noktalar[i]
                b = noktalar[j]
                yatay = haversine(a[1], a[2], b[1], b[2])
                dikey = abs(a[3] - b[3])
                mesafeler.append({
                    "a": a[0], "b": b[0],
                    "m": round(math.sqrt(yatay**2 + dikey**2), 1)
                })

        return {
            "aktif": True,
            "master_sysid": master_sysid,
            "master_lat": m_lat, "master_lon": m_lon,
            "master_alt": round(m_alt, 1),
            "master_hdg": round(m_hdg, 1),
            "master_armed": m_armed,
            "slaves": slave_durum,
            "mesafeler": mesafeler,
        }

    # ------------------------------------------------------------------
    # İç yardımcılar
    # ------------------------------------------------------------------

    def _hedef_hesapla(self, m_lat, m_lon, m_alt, m_hdg, ofset):
        """Master konumuna göre slave hedef konumunu hesaplar."""
        x, y, z = ofset["x"], ofset["y"], ofset["z"]
        # XY düzleminde: x=ileri (heading), y=sağ (heading+90)
        # Toplam yatay mesafe ve açı
        yatay_mesafe = math.sqrt(x**2 + y**2)
        if yatay_mesafe > 0.01:
            # Açı: heading + atan2(y, x) (sağ pozitif, ileri 0)
            aci_rad = math.atan2(y, x)
            aci_derece = math.degrees(aci_rad)
            yon = (m_hdg + aci_derece) % 360
            h_lat, h_lon = _ofset_konum(m_lat, m_lon, yon, yatay_mesafe)
        else:
            h_lat, h_lon = m_lat, m_lon
        h_alt = max(self.MIN_IRTIFA, m_alt + z)
        return h_lat, h_lon, h_alt

    def _loiter_yap(self, sysid):
        """Slave'i LOITER moduna alır."""
        master = self.dron.master_bul(sysid)
        if master:
            try:
                with self.kilit:
                    master.mav.set_mode_send(
                        sysid,
                        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                        5)  # LOITER
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Formasyon döngüsü (thread)
    # ------------------------------------------------------------------

    def _dongu(self, durdur):
        """Slave dronları master'a göre XYZ ofsetinde tutan döngü."""
        guided_verildi = set()
        while not durdur.is_set():
            if not self._suru:
                break
            master_sysid = self._suru["master_sysid"]
            # Master konumu
            with self.kilit:
                m = self.dron.dronlar.get(master_sysid)
                if not m or m.get("lat") is None:
                    m = None
                else:
                    m_lat, m_lon = m["lat"], m["lon"]
                    m_alt = m.get("alt_rel", 0) or 0
                    m_hdg = float(m.get("heading", 0) or 0)

            if m is None:
                time.sleep(0.3)
                continue

            # Her slave için hedef konum gönder
            for sid, ofset in list(self._suru.get("slaves", {}).items()):
                if durdur.is_set():
                    break
                master_obj = self.dron.master_bul(sid)
                if master_obj is None:
                    continue

                h_lat, h_lon, h_alt = self._hedef_hesapla(
                    m_lat, m_lon, m_alt, m_hdg, ofset)

                try:
                    with self.kilit:
                        if sid not in guided_verildi:
                            master_obj.mav.set_mode_send(
                                sid,
                                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                                4)  # GUIDED
                            guided_verildi.add(sid)
                        master_obj.mav.set_position_target_global_int_send(
                            0, sid, 1,
                            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                            0b0000111111111000,  # yalnız konum
                            int(h_lat * 1e7), int(h_lon * 1e7), h_alt,
                            0, 0, 0, 0, 0, 0,
                            math.radians(m_hdg), 0)
                except Exception as e:
                    self.konsol("SÜRÜ",
                                f"D{sid} komut hatası: {e}", "hata")
                    time.sleep(0.5)

            time.sleep(1.0 / self.TAKIP_HZ)
