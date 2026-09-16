# -*- coding: utf-8 -*-
"""Yerel AI takibini angajman altyapisina baglayan besleme kolu (v2.5.21).

=====================================================================
NEDEN AYRI BIR MODUL
=====================================================================
GRCOFF 2.5.20 pasif takip sozlesmesi MUHURLUDUR: `ai_yonetici.takip_isle`
olayi yalniz yerel `veri/track_verisi.ndjson` dosyasina yazilir ve
`track_verisi_dinleyici.py` salt-okunur ornektir. Bu sozlesmeyi koruyan
regresyon testi (`12_TESTLER/GRCOFF/test_grcoff_pasif_takip_20260912.py`)
kaynak kodu tarayarak NDJSON yolunda `mavlink`/`joystick`/`gonder_komut`
GORULMESINI yasaklar.

Bu modul o yola HIC DOKUNMAZ. NDJSON yazimindan tamamen bagimsiz, IKINCI
bir tuketici olarak AI takip olayini alir; olayi cografi hedefe cevirip
mevcut `HedefDeposu`ya yazar. Boylece bugun yalniz Goruntu Koprusu
(BRDIMG) tarafindan beslenen operator-onayli angajman zinciri, yerel AI
tespitleriyle de calisir. Zincirin geri kalani (hedef_liste ->
angajman_ekle -> angajman_karar -> angajman_baslat) DEGISMEZ.

=====================================================================
IKI KAMERA TIPI (kullanici sozlesmesi)
=====================================================================
  'sabit' : Kamera sabit bir noktada durur; hedefi AYRI bir interceptor
            dron angaje eder. Konum kalibrasyondan cozulur:
            lat/lon/kam_yukseklik/yon/tilt/fov.
            -> hedef_deposu.konum_coz  (poz_kaynak='lokasyon')
  'dron'  : Kamera bir dronun govdesine sabittir ve onunla hareket eder;
            konum dronun canli MAVLink pozundan cozulur.
            -> hedef_deposu.hareketli_konum_coz  (poz_kaynak='dron')

Bu modulun TEK isi piksel -> (mesafe, aci) kestirimidir. Piksel-den-
cografi-konuma son projeksiyon HER ZAMAN mevcut `hedef_deposu` cozuculeri
tarafindan yapilir; bu modul o cozuculeri cagirmaz, onlara girdi uretir
ve `HedefDeposu.yaz()` cozumu isler.

=====================================================================
MESAFE KESTIRIMI (hibrit)
=====================================================================
Yerel kamerada dogrudan mesafe olcumu yoktur. Iki yontem, sinifa gore:

  * Kara hedefleri (insan, kara_araci) SABIT kamerada: YER DUZLEMI
    kesisimi. Kamera yuksekligi H ve hedef isininin ufuk alti egimi d
    biliniyorsa, duz zeminde yatay menzil = H/tan(d). Kacinilmaz
    varsayim: hedef yerde ve zemin duz. Duz arazide hata ~%5-10.

  * Hava hedefleri (hava_araci) ve TUM 'dron' tipi kameralar: SINIF
    BAZLI GORUNEN BOYUT. mesafe = gercek_boy * odak_px / kutu_px.
    Gercek boyut bilinmedigi icin hata ~%25-40; bu belirsizlik
    `mesafe_guven` alanina yansitilir ve dusuk guvende cozucu/operator
    hedefi reddedebilir.

Her cikti bir `mesafe_guven` (0..1) tasir. Kalibrasyon eksikse ya da
geometri gecersizse (hedef ufkun ustunde ama yer duzlemi isteniyor gibi)
hedef URETILMEZ; boylece "sessiz yanlis konum" yerine gorunur ret olur.
"""
import math
import threading
import time

# Yerel kameralarin HedefDeposu icindeki sentetik ornek_id tabani.
# Gercek koprulerin ornek_id'leri kucuk pozitif sayilardir; bu taban
# yeterince yuksek secilerek carpisma onlenir. Her yerel kameraya
# `YEREL_ORNEK_TABAN + kamera_id` atanir; boylece bir kameranin yaz()
# cagrisi baska kameranin kaydini silmez (yaz ornek_id basina tam
# kayit degistirir).
YEREL_ORNEK_TABAN = 900_000_000

# C-UAS modu: yalnız hava araçları takibe ve angajmana girebilir.
IZINLI_SINIFLAR = frozenset(("hava_araci",))

# Yer duzlemi kesisiminin gecerli sayildigi asgari ufuk-alti egim.
# Cok kucuk egimde (hedef neredeyse ufukta) H/tan(d) patlar ve minik
# aci hatasi devasa mesafe hatasi uretir; bu yuzden reddedilir.
ASGARI_EGIM_DERECE = 2.0

# Gorunen-boyut yonteminde sinif basina varsayilan fiziksel boyut (m).
# Kutu YUKSEKLIGI ile karsilastirilir. Degerler kaba varsayilandir;
# operator daha iyisini bilirse ileride kamera/sinif basina ayarlanabilir.
SINIF_BOY_M = {
    "hava_araci": 0.6,     # kucuk/orta IHA govde yuksekligi (kaba; dron ~0.4-1.0 m)
}

# Gorunen-boyut mesafesinin ust guveni. Yer duzlemi yonteminden daima
# dusuktur; boyut bilinmedigi icin.
GORUNEN_BOYUT_GUVEN = 0.35
YER_DUZLEMI_GUVEN = 0.75


def _sayi(deger):
    try:
        s = float(deger)
    except (TypeError, ValueError):
        return None
    return s if math.isfinite(s) else None


def _kutu_merkez(kutu, merkez, kare=None):
    """(cx, cy) PIKSEL merkezini dondurur.

    v2.4.164 DUZELTME: Isci kutuyu [x, y, w, h] (kaynak piksel) ve merkezi
    kareye gore NORMALIZE (0..1) gonderir. Eski kod merkezi piksel,
    kutuyu [x1,y1,x2,y2] saniyordu: hedef yonu gorus alaninin sol kenarina
    kayiyor, mesafe yanlis cikiyordu. Once kutudan hesaplanir; yoksa
    normalize merkez kare boyutuyla piksele cevrilir."""
    if isinstance(kutu, (list, tuple)) and len(kutu) == 4:
        x, y, w, h = (_sayi(v) for v in kutu)
        if None not in (x, y, w, h) and w > 0 and h > 0:
            return x + w / 2.0, y + h / 2.0
    if isinstance(merkez, (list, tuple)) and len(merkez) == 2:
        cx, cy = _sayi(merkez[0]), _sayi(merkez[1])
        if cx is not None and cy is not None:
            if (0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0 and
                    isinstance(kare, (list, tuple)) and len(kare) == 2):
                kw, kh = _sayi(kare[0]), _sayi(kare[1])
                if kw and kh:
                    return cx * kw, cy * kh
            return cx, cy
    return None, None


def _kutu_yukseklik(kutu):
    """Kutu [x, y, w, h] -> piksel yukseklik (h)."""
    if isinstance(kutu, (list, tuple)) and len(kutu) == 4:
        h = _sayi(kutu[3])
        if h is not None and h > 0:
            return h
    return None


def _odak_px(kenar_px, fov_derece):
    """FOV ve kare kenarindan piksel cinsinden odak uzunlugu."""
    fov = _sayi(fov_derece)
    kenar = _sayi(kenar_px)
    if fov is None or kenar is None or fov <= 0 or fov >= 180 or kenar <= 0:
        return None
    return kenar / (2.0 * math.tan(math.radians(fov) / 2.0))


class YerelHedefBesleyici:
    """AI takip olayini cografi hedefe cevirip HedefDeposu'ya yazar."""

    def __init__(self, konsol, kameralar, depo, dron=None):
        """
        konsol    : KonsolLog
        kameralar : KameraYoneticisi (kalibrasyon okumak icin)
        depo      : hedef_deposu.HedefDeposu ornegi (DEPO)
        dron      : DronYoneticisi (tip='dron' hareketli cozum icin;
                    depo.dron_yonetici zaten baglanmis olabilir)
        """
        self.konsol = konsol
        self.kameralar = kameralar
        self.depo = depo
        self.dron = dron
        self._kilit = threading.Lock()
        # kamera_id -> son gerekce (arayuz/loglama icin; ayni gerekceyi
        # her karede tekrar loglamamak icin).
        self._son_gerekce = {}

    # ------------------------------------------------------------------
    def ai_olayi(self, olay):
        """AIYonetici takip olayini alir ve depoya yazmayi dener.

        Bu metot AI is parcacigindan cagrilir; HICBIR kosulda istisna
        yukari sizdirmaz. Basarida cozulmus hedefi, aksi halde ret
        gerekcesini dondurur (arayuz/log icin). NDJSON yolundan tamamen
        bagimsizdir.
        """
        try:
            return self._ai_olayi(olay)
        except Exception as e:  # AI dongusunu asla dusurme
            try:
                self.konsol("YEREL_HEDEF",
                            "Yerel hedef cozulemedi (beklenmeyen): %s" % e,
                            "hata")
            except Exception:
                pass
            return {"tamam": False, "hata": "ic hata"}

    def _ai_olayi(self, olay):
        if not isinstance(olay, dict):
            return {"tamam": False, "hata": "gecersiz olay"}
        kamera_id = olay.get("kamera_id")
        try:
            kamera_id = int(kamera_id)
        except (TypeError, ValueError):
            return {"tamam": False, "hata": "gecersiz kamera"}

        # Hedef kaybolduysa depodaki kaydi temizle (angajman dongusu
        # bayat/None hedefte zaten angajmani keser; erken temizlik
        # operatore hemen "iz kayboldu" gosterir).
        if olay.get("kayip"):
            try:
                self.depo.sil(YEREL_ORNEK_TABAN + kamera_id)
            except Exception:
                pass
            return {"tamam": True, "kayip": True}

        sinif = str(olay.get("sinif") or olay.get("tur") or "").strip().lower()
        if sinif not in IZINLI_SINIFLAR:
            return {"tamam": False, "hata": "izinli olmayan sinif"}

        kam = None
        try:
            kam = self.kameralar.bul(kamera_id) if self.kameralar else None
        except Exception:
            kam = None
        if not kam:
            return self._ret(kamera_id, "kamera kaydi bulunamadi")
        if not kam.get("kalibre"):
            return self._ret(kamera_id,
                             "kamera kalibre degil; kamera formundan "
                             "konum/yon/aci girin")

        tip = str(kam.get("kamera_tipi") or "sabit").strip().lower()
        if tip == "dron":
            return self._dron_kamera(kamera_id, kam, sinif, olay)
        return self._sabit_kamera(kamera_id, kam, sinif, olay)

    # ------------------------------------------------------------------
    # SABIT kamera: konum_coz (poz_kaynak='lokasyon')
    # ------------------------------------------------------------------
    def _sabit_kamera(self, kamera_id, kam, sinif, olay):
        lat = _sayi(kam.get("lat"))
        lon = _sayi(kam.get("lon"))
        H = _sayi(kam.get("kam_yukseklik"))
        yon = _sayi(kam.get("yon"))
        tilt = _sayi(kam.get("tilt"))
        fov_y = _sayi(kam.get("fov_yatay"))
        fov_d = _sayi(kam.get("fov_dikey"))
        if None in (lat, lon, H, yon, tilt, fov_y, fov_d):
            return self._ret(kamera_id, "sabit kamera kalibrasyonu eksik "
                                        "(konum/yukseklik/yon/tilt/fov)")

        kare = olay.get("kare_boyutu")
        if not (isinstance(kare, (list, tuple)) and len(kare) == 2):
            return self._ret(kamera_id, "kare boyutu yok")
        kare_w, kare_h = _sayi(kare[0]), _sayi(kare[1])
        if not kare_w or not kare_h:
            return self._ret(kamera_id, "gecersiz kare boyutu")

        cx, cy = _kutu_merkez(olay.get("kutu_px") or olay.get("kutu"),
                              olay.get("merkez_px") or olay.get("merkez"),
                              olay.get("kare_boyutu"))
        if cx is None or cy is None:
            return self._ret(kamera_id, "hedef piksel konumu yok")

        odak_y = _odak_px(kare_w, fov_y)
        odak_d = _odak_px(kare_h, fov_d)
        if odak_y is None or odak_d is None:
            return self._ret(kamera_id, "gecersiz FOV")

        # Yatay: boresight'a gore aci, saga pozitif -> mutlak azimut.
        aci_yatay = math.degrees(math.atan2(cx - kare_w / 2.0, odak_y))
        azimut = (yon + aci_yatay) % 360.0

        # Dikey: yukari pozitif piksel ofseti; isinin ufuk alti egimi.
        aci_dik_yukari = math.degrees(math.atan2(kare_h / 2.0 - cy, odak_d))
        # boresight ufkun `tilt` derece altinda; isin egimi (asagi +):
        egim = tilt - aci_dik_yukari

        # C-UAS: yalniz hava_araci — gorunen boyutla mesafe kestirimi.
        mesafe, guven = self._gorunen_boyut_mesafe(sinif, olay, odak_d)
        if mesafe is None:
            return self._ret(kamera_id, "hava hedefi mesafesi "
                                        "kestirilecmedi (kutu boyu yok)")
        # Ufka gore yukselis: boresight -tilt, isin yukari ofseti eklenir.
        yukselis = -tilt + aci_dik_yukari
        kaynak = "gorunen_boyut"

        hedef = {
            "iz": self._iz(olay),
            "tur": sinif,
            "kutu": olay.get("kutu_px") or olay.get("kutu"),
            "merkez_px": [cx, cy],
            "azimut": round(azimut, 3),
            "yukselis": round(yukselis, 3),
            "mesafe_m": round(mesafe, 1),
            "mesafe_guven": round(guven, 3),
            "mesafe_kaynak": kaynak,
        }
        kal = {
            "lat": lat, "lon": lon, "kam_yukseklik": H,
            "kalibre": True, "poz_kaynak": "lokasyon",
        }
        return self._depoya_yaz(kamera_id, kam, kal, hedef, "lokasyon")

    # ------------------------------------------------------------------
    # DRON'a takili kamera: hareketli_konum_coz (poz_kaynak='dron')
    # ------------------------------------------------------------------
    def _dron_kamera(self, kamera_id, kam, sinif, olay):
        uid = str(kam.get("dron_uid") or "").strip()
        if not uid:
            return self._ret(kamera_id, "dron kamerasi bir drona bagli degil "
                                        "(dron_uid bos)")
        fov_y = _sayi(kam.get("fov_yatay"))
        fov_d = _sayi(kam.get("fov_dikey"))
        mpan = _sayi(kam.get("montaj_pan"))
        mtilt = _sayi(kam.get("montaj_tilt"))
        mroll = _sayi(kam.get("montaj_roll"))
        if None in (fov_y, fov_d, mpan, mtilt, mroll):
            return self._ret(kamera_id, "dron kamerasi montaj/FOV "
                                        "kalibrasyonu eksik")

        kare = olay.get("kare_boyutu")
        if not (isinstance(kare, (list, tuple)) and len(kare) == 2):
            return self._ret(kamera_id, "kare boyutu yok")
        kare_w, kare_h = _sayi(kare[0]), _sayi(kare[1])
        if not kare_w or not kare_h:
            return self._ret(kamera_id, "gecersiz kare boyutu")

        cx, cy = _kutu_merkez(olay.get("kutu_px") or olay.get("kutu"),
                              olay.get("merkez_px") or olay.get("merkez"),
                              olay.get("kare_boyutu"))
        if cx is None or cy is None:
            return self._ret(kamera_id, "hedef piksel konumu yok")

        odak_y = _odak_px(kare_w, fov_y)
        odak_d = _odak_px(kare_h, fov_d)
        if odak_y is None or odak_d is None:
            return self._ret(kamera_id, "gecersiz FOV")

        # Boresight'a GORELI acilar (hareketli_konum_coz montaj + dron
        # pozunu kendisi uygular).
        goreli_azimut = math.degrees(math.atan2(cx - kare_w / 2.0, odak_y))
        goreli_yukselis = math.degrees(math.atan2(kare_h / 2.0 - cy, odak_d))

        # Hareketli kamerada yer duzlemi varsayimi guvenli degil; her
        # sinif icin gorunen-boyut kullanilir.
        mesafe, guven = self._gorunen_boyut_mesafe(sinif, olay, odak_d)
        if mesafe is None:
            return self._ret(kamera_id,
                             "dron kamerasi mesafesi kestirilecmedi "
                             "(kutu boyu yok)")

        try:
            ts = float(olay.get("ts") or time.time())
        except (TypeError, ValueError):
            ts = time.time()

        hedef = {
            "iz": self._iz(olay),
            "tur": sinif,
            "kutu": olay.get("kutu_px") or olay.get("kutu"),
            "merkez_px": [cx, cy],
            "goreli_azimut": round(goreli_azimut, 3),
            "goreli_yukselis": round(goreli_yukselis, 3),
            "mesafe_m": round(mesafe, 1),
            "mesafe_guven": round(guven, 3),
            "mesafe_kaynak": "gorunen_boyut",
            # hareketli_konum_coz olcum_zamani ile dron pozunu zaman
            # olarak eslestirir; yerelde ayni saat kullanilir.
            "olcum_zamani": ts,
        }
        kal = {
            "kalibre": True, "poz_kaynak": "dron",
            "kaynak_dron_id": uid, "gimbal_kipi": "govdeye_sabit",
            "montaj_pan": mpan, "montaj_tilt": mtilt, "montaj_roll": mroll,
        }
        return self._depoya_yaz(kamera_id, kam, kal, hedef, "dron")

    # ------------------------------------------------------------------
    def _gorunen_boyut_mesafe(self, sinif, olay, odak_d):
        """(mesafe_m, guven) veya (None, 0) dondurur."""
        kutu_h = _kutu_yukseklik(olay.get("kutu_px") or olay.get("kutu"))
        if not kutu_h or kutu_h <= 0:
            return None, 0.0
        gercek = SINIF_BOY_M.get(sinif)
        if not gercek:
            return None, 0.0
        mesafe = gercek * odak_d / kutu_h
        if not math.isfinite(mesafe) or mesafe <= 0:
            return None, 0.0
        # AI tespit guveni varsa gorunen-boyut guvenini olcekle.
        tespit_guven = _sayi(olay.get("guven"))
        guven = GORUNEN_BOYUT_GUVEN
        if tespit_guven is not None:
            guven *= max(0.2, min(1.0, tespit_guven))
        return mesafe, guven

    def _depoya_yaz(self, kamera_id, kam, kal, hedef, poz_kaynak):
        """Sentetik kopru paketini olusturur ve DEPO.yaz cozumu isler."""
        ornek_id = YEREL_ORNEK_TABAN + kamera_id
        paket = {
            "zaman": time.time(),
            "kameralar": [{
                "kamera": kamera_id,
                "kalibrasyon": kal,
                "hedefler": [hedef],
            }],
        }
        # Yerel kurulum tek kiracidir: firma_id=None. yaz() cozumu
        # (konum_coz/hareketli_konum_coz) poz_kaynak'a gore secer ve
        # konum_guvenilir/konum_gerekce alanlarini isler.
        try:
            ok = self.depo.yaz(ornek_id,
                               "YEREL:" + str(kam.get("isim") or kamera_id),
                               paket, firma_id=None,
                               kurulum_uid="yerel")
        except Exception as e:
            return self._ret(kamera_id, "depo yazimi basarisiz: %s" % e)
        if not ok:
            return self._ret(kamera_id, "depo paketi reddetti")

        # Cozulen kaydi geri oku; angajman icin konum guvenilir mi?
        cozulen = None
        try:
            cozulen = self.depo.hedef_bul(ornek_id, kamera_id,
                                          hedef["iz"], firma_id=None)
        except Exception:
            cozulen = None
        if not cozulen or not cozulen.get("konum_guvenilir"):
            gerekce = (cozulen or {}).get("konum_gerekce") or "konum cozulemedi"
            return self._ret(kamera_id, gerekce, cozuldu=False)

        with self._kilit:
            self._son_gerekce.pop(kamera_id, None)
        # Angajman hedef kimligi bicimi "ornek_id:kamera:iz".
        hedef_id = "%d:%d:%d" % (ornek_id, kamera_id, hedef["iz"])
        return {
            "tamam": True,
            "hedef_id": hedef_id,
            "ornek_id": ornek_id,
            "kamera": kamera_id,
            "iz": hedef["iz"],
            "kamera_tipi": poz_kaynak,
            "lat": cozulen.get("lat"),
            "lon": cozulen.get("lon"),
            "alt": cozulen.get("alt"),
            "mesafe_m": hedef["mesafe_m"],
            "mesafe_guven": hedef["mesafe_guven"],
        }

    def _iz(self, olay):
        """Olaydaki track_id'yi pozitif int ize cevirir."""
        ham = olay.get("track_id")
        if isinstance(ham, int) and ham > 0:
            return ham
        # track_id metin olabilir ("k7-test"); kamera bazli kararli bir
        # ize cevir. iz numarasi HedefDeposu icinde yalniz kamera basina
        # anlamlidir, bu yuzden hash yeterlidir.
        s = str(ham or olay.get("kamera_id") or "0")
        return (abs(hash(s)) % 2_000_000) + 1

    def _ret(self, kamera_id, gerekce, cozuldu=False):
        """Ret gerekcesini (ayni ise tekrar loglamadan) dondurur."""
        with self._kilit:
            onceki = self._son_gerekce.get(kamera_id)
            self._son_gerekce[kamera_id] = gerekce
        if onceki != gerekce:
            try:
                self.konsol("YEREL_HEDEF",
                            "Kamera #%s hedefi angajmana alinamadi: %s"
                            % (kamera_id, gerekce), "uyari")
            except Exception:
                pass
        return {"tamam": False, "hata": gerekce, "cozuldu": cozuldu}
