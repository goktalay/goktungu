"""DronTakipYoneticisi: Dron-dron takip (formasyon/escort) motoru.

Bir "takipci" dron, "hedef" (takip edilen) dronun konumuna gore
belirlenen ofsetle surekli yonlendirilir:
  - mesafe (m)      : + deger hedefin GERISINDE (heading tersinde),
                      - deger hedefin ONUNDE konumlanir (-100..+100)
  - irtifa_fark (m) : hedef irtifasina eklenir (-100..+100)

Angajman motoru (angajman.py) ile ayni desen kullanilir: her takip
ayri thread'de calisir, GUIDED modda set_position_target_global_int
ile konum hedefi gonderilir. Yakalama/bitis kosulu yoktur; iptal
edilene (veya baglanti kesilene) kadar surer.
"""
import math
import threading
import time

from pymavlink import mavutil

from goktungu.angajman import haversine, bearing


def _ofset_konum(lat, lon, yon_derece, mesafe_m):
    """Bir noktadan verilen yonde mesafe kadar otelenmis koordinat."""
    R = 6371000.0
    br = math.radians(yon_derece % 360)
    dlat = (mesafe_m * math.cos(br)) / R * (180.0 / math.pi)
    dlon = (mesafe_m * math.sin(br)) / (
        R * math.cos(math.radians(lat))) * (180.0 / math.pi)
    return lat + dlat, lon + dlon


class DronTakipYoneticisi:

    TAKIP_HZ = 5           # konum hedefi gonderme frekansi
    MIN_IRTIFA = 2.0       # guvenlik: hedef irtifa asla bunun altina inmez

    def __init__(self, konsol, dron, kilit):
        self.konsol = konsol
        self.dron = dron
        self.kilit = kilit
        # takipci_sysid -> {thread, durdur, hedef_sysid, irtifa_fark, mesafe}
        self._aktif = {}

    # ------------------------------------------------------------------
    # WS API
    # ------------------------------------------------------------------
    def baslat(self, takipci_sysid, hedef_sysid, irtifa_fark, mesafe):
        takipci_sysid = int(takipci_sysid)
        hedef_sysid = int(hedef_sysid)
        if takipci_sysid == hedef_sysid:
            self.konsol("TAKIP", "Dron kendini takip edemez.", "hata")
            return False
        # Parametreleri -100..+100 araligina kirp
        irtifa_fark = max(-100.0, min(100.0, float(irtifa_fark)))
        mesafe = max(-100.0, min(100.0, float(mesafe)))
        # Ayni takipci icin onceki takibi kapat (yeniden baslatma)
        if takipci_sysid in self._aktif:
            self.durdur(takipci_sysid, loiter=False)
        # Dairesel takip engeli (A->B varken B->A yasak)
        b = self._aktif.get(hedef_sysid)
        if b and b["hedef_sysid"] == takipci_sysid:
            self.konsol("TAKIP",
                        f"D{hedef_sysid} zaten D{takipci_sysid} dronunu "
                        "takip ediyor (dairesel takip engellendi).", "hata")
            return False
        durdur = threading.Event()
        t = threading.Thread(
            target=self._dongu,
            args=(takipci_sysid, hedef_sysid, irtifa_fark, mesafe, durdur),
            daemon=True)
        self._aktif[takipci_sysid] = {
            "thread": t, "durdur": durdur, "hedef_sysid": hedef_sysid,
            "irtifa_fark": irtifa_fark, "mesafe": mesafe,
        }
        t.start()
        self.konsol("TAKIP",
                    f"D{takipci_sysid} -> D{hedef_sysid} takibi basladi "
                    f"(irtifa farki {irtifa_fark:+.0f} m, "
                    f"mesafe {mesafe:+.0f} m).", "basari")
        return True

    def durdur(self, sysid=None, loiter=True):
        """Takibi durdurur. sysid takipci VEYA hedef sysid olabilir;
        hedef verilirse o hedefi takip eden TUM takipler durur.
        sysid=None ise tum takipler durdurulur."""
        durduruldu = []
        if sysid is None:
            durduruldu = list(self._aktif.keys())
        else:
            sysid = int(sysid)
            for tk, bilgi in list(self._aktif.items()):
                if tk == sysid or bilgi["hedef_sysid"] == sysid:
                    durduruldu.append(tk)
        for tk in durduruldu:
            bilgi = self._aktif.pop(tk, None)
            if bilgi:
                bilgi["durdur"].set()
                self.konsol("TAKIP", f"D{tk} takibi durduruldu.", "uyari")
                if loiter:
                    self._loiter_yap(tk)
        return durduruldu

    def sessiz_durdur(self):
        """Baglanti kesilirken cagirilir (LOITER gondermeden)."""
        for bilgi in self._aktif.values():
            bilgi["durdur"].set()
        self._aktif.clear()

    def durum(self):
        """Frontend'e yayinlanacak aktif takip listesi."""
        return [
            {"takipci_sysid": tk, "hedef_sysid": b["hedef_sysid"],
             "irtifa_fark": b["irtifa_fark"], "mesafe": b["mesafe"]}
            for tk, b in self._aktif.items()
        ]

    # ------------------------------------------------------------------
    # Yardimcilar
    # ------------------------------------------------------------------
    def _loiter_yap(self, sysid):
        master = self.dron.master_bul(sysid)
        if master:
            with self.kilit:
                try:
                    master.mav.set_mode_send(
                        sysid,
                        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                        5)  # LOITER
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Takip dongusu (thread)
    # ------------------------------------------------------------------
    def _dongu(self, takipci_sysid, hedef_sysid, irtifa_fark, mesafe, durdur):
        guided_verildi = False
        while not durdur.is_set():
            master = self.dron.master_bul(takipci_sysid)
            if master is None:
                time.sleep(0.5)
                continue
            # Hedef (takip edilen) dronun konumu + heading'i
            with self.kilit:
                h = self.dron.dronlar.get(hedef_sysid)
                if not h or h.get("lat") is None:
                    h = None
                else:
                    h_lat, h_lon = h["lat"], h["lon"]
                    h_alt = h.get("alt_rel", 0) or 0
                    h_hdg = float(h.get("heading", 0) or 0)
            if h is None:
                time.sleep(0.3)
                continue
            # Hedef nokta: + mesafe hedefin GERISINDE (heading + 180),
            # - mesafe hedefin ONUNDE (heading yonunde)
            if abs(mesafe) > 0.01:
                yon = (h_hdg + 180.0) if mesafe > 0 else h_hdg
                n_lat, n_lon = _ofset_konum(h_lat, h_lon, yon, abs(mesafe))
            else:
                n_lat, n_lon = h_lat, h_lon
            n_alt = max(self.MIN_IRTIFA, h_alt + irtifa_fark)
            # Takipci hedefe donuk ucsun (yaw = takipciden hedefe bearing)
            yaw = h_hdg
            with self.kilit:
                s = self.dron.dronlar.get(takipci_sysid)
                if s and s.get("lat") is not None:
                    uzak = haversine(s["lat"], s["lon"], h_lat, h_lon)
                    if uzak > 5.0:
                        yaw = bearing(s["lat"], s["lon"], h_lat, h_lon)
            try:
                with self.kilit:
                    if not guided_verildi:
                        master.mav.set_mode_send(
                            takipci_sysid,
                            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                            4)  # GUIDED
                        guided_verildi = True
                    master.mav.set_position_target_global_int_send(
                        0, takipci_sysid, 1,
                        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                        0b0000111111111000,  # yalniz konum
                        int(n_lat * 1e7), int(n_lon * 1e7), n_alt,
                        0, 0, 0, 0, 0, 0,
                        math.radians(yaw), 0)
            except Exception as e:
                self.konsol("TAKIP", f"D{takipci_sysid} komut hatasi: {e}",
                            "hata")
                time.sleep(1.0)
            time.sleep(1.0 / self.TAKIP_HZ)
