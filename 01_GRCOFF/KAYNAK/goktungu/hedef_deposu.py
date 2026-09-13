"""Görüntü Köprüsü hedef deposu ve insan onaylı angajman kuyruğu.

Görüntü Köprüsü saniyede yaklaşık iki kez yalnız sayısal hedef metadatası
(`tur == "hedef"`) gönderir. Bu modül görüntü/JPEG/piksel verisini kesinlikle
kabul etmez; anlık hedefleri bellekte tutar ve sabit ya da gövdeye sabit dron
kamerası için güvenli coğrafi konum çözümü yapar.

Kalıcı yazılan tek şey operatörün angajman kuyruğuna aldığı karardır. Anlık hedef
akışı veritabanına yazılmaz.
"""
import math
import threading
import time

# Bir köprünün hedef verisi bu süre boyunca güncellenmezse bayat sayılır.
BAYAT_SN = 4.0
SIL_SN = 15.0
KUYRUK_SINIR = 500
DUNYA_R = 6378137.0

# Hareketli kamera için heartbeat değil, poz ve tutum mesajlarının kendi zamanı
# denetlenir. 4 Hz istenen MAVLink akışında 3 saniye, on iki örnek kaybına
# karşılık gelir; bundan eski veriyle angajman güvenli değildir.
DRON_POZ_BAYAT_SN = 3.0
DRON_TUTUM_BAYAT_SN = 3.0
KARE_POZ_FARK_SN = 3.0
KAYNAK_GELECEK_PAY_SN = 0.5
SECIM_AZAMI_YAS_SN = 30.0

YASAK_ALANLAR = ("kare", "jpeg", "jpg", "goruntu", "image", "b64",
                  "base64", "veri_b64", "kirpinti")

# Köprüden gelen hedef sözlüğü serbest biçimli değildir. Özellikle yüz adı,
# embedding, kişi kimliği veya sonradan eklenebilecek görsel alanlar merkez
# belleğine dahi alınmaz. Bu liste, Görüntü Köprüsü ``hedef.py`` sayısal
# sözleşmesi ile tam ekran operatör seçiminin iki işaretini kapsar.
HEDEF_ALANLARI = frozenset({
    "iz", "tur", "puan", "ort_puan", "kutu", "merkez_px",
    "azimut", "yukselis", "goreli_azimut", "goreli_yukselis",
    "olcum_zamani", "aci_hiz", "kalibre", "mesafe_m",
    "mesafe_guven", "mesafe_kaynak", "sure", "gorulme", "yon_px",
    "hiz_px", "oncelik", "skor_detay", "yerel_secili", "secim_zamani",
})


def _sayi(deger):
    """Sonlu float döndürür; NaN/inf ve çevrilemeyen değerleri reddeder."""
    try:
        sonuc = float(deger)
    except (TypeError, ValueError):
        return None
    return sonuc if math.isfinite(sonuc) else None


def _kaynak_zamani_cevir(olay_ts, paket_ts, alis_ts, azami_yas):
    """Kaynak duvar saatini App saatine, yalnız paket içi olay yaşıyla taşır.

    Köprü ve App farklı makinelerde olduğundan mutlak ``time.time()`` değerleri
    doğrudan karşılaştırılmaz. Olayın köprüdeki paket üretimine göre yaşı
    korunur; App alım anından geri yürünür. Eksik, gelecekten veya izin verilen
    pencereden eski değerler sıfırlanır ve sonraki güvenlik kapıları reddeder.
    """
    olay = _sayi(olay_ts)
    paket = _sayi(paket_ts)
    alis = _sayi(alis_ts)
    sinir = _sayi(azami_yas)
    if (olay is None or paket is None or alis is None or sinir is None or
            olay <= 0.0 or paket <= 0.0 or alis <= 0.0 or sinir < 0.0):
        return 0.0
    yas = paket - olay
    if yas < -KAYNAK_GELECEK_PAY_SN or yas > sinir:
        return 0.0
    return round(alis - max(0.0, yas), 6)


def _cografi_ilerlet(lat, lon, kuzey, dogu):
    """Yerel N/E metre farkını WGS84 enlem/boylama taşır."""
    lat = _sayi(lat)
    lon = _sayi(lon)
    kuzey = _sayi(kuzey)
    dogu = _sayi(dogu)
    if None in (lat, lon, kuzey, dogu):
        return None, None, "gecersiz konum/mesafe"
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None, None, "gecersiz kamera koordinati"
    kos = math.cos(math.radians(lat))
    if abs(kos) < 1e-9:
        return None, None, "kutup bolgesi"
    hlat = lat + math.degrees(kuzey / DUNYA_R)
    hlon = lon + math.degrees(dogu / (DUNYA_R * kos))
    if not (-90.0 <= hlat <= 90.0 and -180.0 <= hlon <= 180.0):
        return None, None, "cozulen konum sinir disi"
    return round(hlat, 7), round(hlon, 7), ""


def konum_coz(kal, hedef):
    """Sabit kamera hedefini mutlak coğrafi konuma çözer.

    Köprüdeki ``Kalibrasyon.aci`` pan/tilt'i hedefin ``azimut`` ve
    ``yukselis`` alanlarına zaten ekler; burada ikinci kez eklenmez.
    """
    if not isinstance(kal, dict) or not kal.get("kalibre"):
        return None, None, None, False, "kamera kalibre degil"

    klat = _sayi(kal.get("lat"))
    klon = _sayi(kal.get("lon"))
    if klat is None or klon is None:
        return None, None, None, False, "kamera konumu yok"
    if not (-90.0 <= klat <= 90.0 and -180.0 <= klon <= 180.0):
        return None, None, None, False, "gecersiz kamera koordinati"

    mes = _sayi(hedef.get("mesafe_m"))
    az_d = _sayi(hedef.get("azimut"))
    yu_d = _sayi(hedef.get("yukselis"))
    kyuk = _sayi(kal.get("kam_yukseklik"))
    if mes is None or mes <= 0:
        return None, None, None, False, "mesafe tahmini yok"
    if None in (az_d, yu_d, kyuk):
        return None, None, None, False, "gecersiz aci/mesafe"

    az = math.radians(az_d)
    yu = math.radians(yu_d)
    yatay = mes * math.cos(yu)
    alt = kyuk + mes * math.sin(yu)
    kuzey = yatay * math.cos(az)
    dogu = yatay * math.sin(az)
    hlat, hlon, hata = _cografi_ilerlet(klat, klon, kuzey, dogu)
    if hata:
        return None, None, None, False, hata
    if alt < 0:
        alt = 0.0
    guven = _sayi(hedef.get("mesafe_guven")) or 0.0
    return (hlat, hlon, round(alt, 1), True,
            "mesafe tahmini guven=%.2f" % guven)


def _donus_matrisi(yaw_d, pitch_d, roll_d):
    """Gövde/kamera eksenini NED eksenine taşıyan Z-Y-X dönüş matrisi."""
    y, p, r = map(math.radians, (yaw_d, pitch_d, roll_d))
    cy, sy = math.cos(y), math.sin(y)
    cp, sp = math.cos(p), math.sin(p)
    cr, sr = math.cos(r), math.sin(r)
    return (
        (cp * cy, sr * sp * cy - cr * sy, cr * sp * cy + sr * sy),
        (cp * sy, sr * sp * sy + cr * cy, cr * sp * sy - sr * cy),
        (-sp, sr * cp, cr * cp),
    )


def _mat_vektor(m, v):
    return tuple(sum(m[i][j] * v[j] for j in range(3)) for i in range(3))


def _mat_carp(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3))
                       for j in range(3)) for i in range(3))


def _dron_snapshot(dron_yonetici, kaynak_uid):
    """Yalnız kararlı UID ile eşleşen canlı dron kaydının kopyasını döndürür."""
    if dron_yonetici is None:
        return None
    uid = str(kaynak_uid or "").strip()
    if not uid:
        return None
    try:
        kilit = dron_yonetici.kilit
        with kilit:
            for d in dron_yonetici.dronlar.values():
                if str((d or {}).get("uid") or "").strip() == uid:
                    return dict(d)
    except BaseException:
        return None
    return None


def hareketli_konum_coz(kal, hedef, dron_yonetici, simdi=None):
    """Gövdeye sabit dron kamerası hedefini canlı MAVLink pozuyla çözer.

    Gimbal telemetrisi mevcut değildir. ``gimbal`` kipi veya eksik/bayat
    konum-yönelim, güvenli tarafta açık gerekçeyle reddedilir.
    """
    if not isinstance(kal, dict) or not kal.get("kalibre"):
        return None, None, None, False, "kamera kalibre degil"
    if str(kal.get("gimbal_kipi") or "govdeye_sabit").lower() != "govdeye_sabit":
        return None, None, None, False, "gimbal telemetrisi desteklenmiyor"

    uid = str(kal.get("kaynak_dron_id") or "").strip()
    if not uid:
        return None, None, None, False, "kaynak dron UID yok"
    d = _dron_snapshot(dron_yonetici, uid)
    if not d:
        return None, None, None, False, "kaynak dron bagli degil"

    simdi = _sayi(simdi) or time.time()
    poz_ts = _sayi(d.get("poz_ts")) or 0.0
    tutum_ts = _sayi(d.get("tutum_ts")) or 0.0
    if poz_ts <= 0 or simdi - poz_ts > DRON_POZ_BAYAT_SN:
        return None, None, None, False, "dron konum telemetrisi bayat"
    if tutum_ts <= 0 or simdi - tutum_ts > DRON_TUTUM_BAYAT_SN:
        return None, None, None, False, "dron yonelim telemetrisi bayat"

    olcum_ts = _sayi(hedef.get("olcum_zamani"))
    if olcum_ts is None or olcum_ts <= 0:
        return None, None, None, False, "hedef olcum zamani yok"
    if (abs(olcum_ts - poz_ts) > KARE_POZ_FARK_SN or
            abs(olcum_ts - tutum_ts) > KARE_POZ_FARK_SN):
        return None, None, None, False, "hedef ile dron pozu zaman uyumsuz"

    gps_fix = _sayi(d.get("gps_fix"))
    if gps_fix is None or gps_fix < 3:
        return None, None, None, False, "dron GPS duzeltmesi yetersiz"

    lat = _sayi(d.get("lat"))
    lon = _sayi(d.get("lon"))
    alt = _sayi(d.get("alt_msl"))
    yaw = _sayi(d.get("heading"))
    pitch = _sayi(d.get("pitch"))
    roll = _sayi(d.get("roll"))
    if None in (lat, lon, alt, yaw, pitch, roll):
        return None, None, None, False, "dron poz/yönelim eksik"
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None, None, None, False, "gecersiz dron koordinati"
    # (0,0), canlı ürün sözleşmesinde başlatma/geçersiz konum işaretidir.
    if abs(lat) < 1e-12 and abs(lon) < 1e-12:
        return None, None, None, False, "dron konumu henuz gecersiz"

    mes = _sayi(hedef.get("mesafe_m"))
    raz = _sayi(hedef.get("goreli_azimut"))
    ryu = _sayi(hedef.get("goreli_yukselis"))
    mpan = _sayi(kal.get("montaj_pan"))
    mtilt = _sayi(kal.get("montaj_tilt"))
    mroll = _sayi(kal.get("montaj_roll"))
    if mes is None or mes <= 0:
        return None, None, None, False, "mesafe tahmini yok"
    if None in (raz, ryu, mpan, mtilt, mroll):
        return None, None, None, False, "kamera aci/montaj verisi eksik"
    if not (-360.0 <= mpan <= 360.0 and -90.0 <= mtilt <= 90.0 and
            -180.0 <= mroll <= 180.0):
        return None, None, None, False, "kamera montaj acisi gecersiz"

    # Kamera ışını: x ileri, y sağ, z aşağı (NED uyumlu). Pozitif
    # görüntü yükselişi yukarı olduğundan z bileşeni negatiftir.
    az = math.radians(raz)
    el = math.radians(ryu)
    isin_kamera = (math.cos(el) * math.cos(az),
                   math.cos(el) * math.sin(az),
                   -math.sin(el))
    kamera_govde = _donus_matrisi(mpan, mtilt, mroll)
    govde_ned = _donus_matrisi(yaw, pitch, roll)
    isin_ned = _mat_vektor(_mat_carp(govde_ned, kamera_govde), isin_kamera)
    kuzey, dogu, asagi = (mes * x for x in isin_ned)
    hlat, hlon, hata = _cografi_ilerlet(lat, lon, kuzey, dogu)
    if hata:
        return None, None, None, False, hata
    halt = alt - asagi
    if not math.isfinite(halt):
        return None, None, None, False, "cozulen irtifa gecersiz"
    if halt < 0:
        halt = 0.0
    guven = _sayi(hedef.get("mesafe_guven")) or 0.0
    return (hlat, hlon, round(halt, 1), True,
            "hareketli kamera; mesafe tahmini guven=%.2f" % guven)


class HedefDeposu:
    """Köprü başına anlık hedef listesini bellekte tutar."""

    def __init__(self):
        self._kilit = threading.Lock()
        self._veri = {}
        self.paket_sayisi = 0
        self.son_paket_ts = 0.0
        self.dron_yonetici = None
        self._firma_uid_onbellek = {}

    def dron_yonetici_ata(self, dron_yonetici):
        """Canlı DronYöneticisi'ni enjekte eder; ikinci örnek oluşturmaz."""
        self.dron_yonetici = dron_yonetici

    def _firma_dron_uidleri(self, firma_id):
        """Kesin sahipli dron UID kümesini kısa süreli önbellekten döndürür."""
        try:
            fid = int(firma_id)
        except (TypeError, ValueError):
            return set()
        if fid <= 0:
            return set()
        simdi = time.time()
        onceki = self._firma_uid_onbellek.get(fid)
        if onceki and simdi - onceki[0] <= 10.0:
            return set(onceki[1])
        try:
            from . import veritabani as _vt
            uidler = {str(x.get("uid") or "").strip()
                      for x in _vt.dron_kaynaklari_listele(fid)
                      if str(x.get("uid") or "").strip()}
        except BaseException:
            uidler = set()
        self._firma_uid_onbellek[fid] = (simdi, set(uidler))
        return uidler

    def yaz(self, ornek_id, kopru_ad, paket, firma_id=None, kurulum_uid=""):
        """Köprüden gelen hedef paketini güvenli biçimde kaydeder."""
        kameralar = []
        izinli_dron_uidleri = self._firma_dron_uidleri(firma_id) if firma_id else None
        if not isinstance(paket, dict) or any(a in paket for a in YASAK_ALANLAR):
            return False
        alis_ts = time.time()
        kaynak_paket_ts = _sayi(paket.get("zaman"))
        for k in (paket.get("kameralar") or [])[:64]:
            if not isinstance(k, dict) or any(a in k for a in YASAK_ALANLAR):
                continue
            ham_kal = k.get("kalibrasyon")
            kal = {}
            if isinstance(ham_kal, dict) and not any(
                    a in ham_kal for a in YASAK_ALANLAR):
                kal = {a: ham_kal.get(a) for a in (
                    "lat", "lon", "kam_yukseklik", "pan", "tilt",
                    "kalibre", "poz_kaynak", "kaynak_lokasyon_id",
                    "kaynak_dron_id", "montaj_pan", "montaj_tilt",
                    "montaj_roll", "gimbal_kipi")}
            kaynak_turu = str(kal.get("poz_kaynak") or "manuel").lower()
            if kaynak_turu not in ("manuel", "lokasyon", "dron"):
                kaynak_turu = "manuel"
            kal["poz_kaynak"] = kaynak_turu
            kaynak_dron_yetkili = True
            if kaynak_turu == "dron" and izinli_dron_uidleri is not None:
                kaynak_dron_yetkili = str(
                    kal.get("kaynak_dron_id") or "").strip() in izinli_dron_uidleri
            hedefler = []
            for ham_hedef in (k.get("hedefler") or [])[:128]:
                if not isinstance(ham_hedef, dict):
                    continue
                if any(a in ham_hedef for a in YASAK_ALANLAR):
                    continue
                h = {a: ham_hedef.get(a) for a in HEDEF_ALANLARI
                     if a in ham_hedef}
                if "olcum_zamani" in h:
                    h["olcum_zamani"] = _kaynak_zamani_cevir(
                        h.get("olcum_zamani"), kaynak_paket_ts, alis_ts,
                        BAYAT_SN)
                if "secim_zamani" in h:
                    h["secim_zamani"] = _kaynak_zamani_cevir(
                        h.get("secim_zamani"), kaynak_paket_ts, alis_ts,
                        SECIM_AZAMI_YAS_SN)
                if kaynak_turu == "dron" and not kaynak_dron_yetkili:
                    cozum = (None, None, None, False,
                             "kaynak dron firmaya ait degil")
                elif kaynak_turu == "dron":
                    cozum = hareketli_konum_coz(
                        kal, h, self.dron_yonetici, alis_ts)
                else:
                    cozum = konum_coz(kal, h)
                hlat, hlon, halt, guvenilir, gerekce = cozum
                h["lat"] = hlat
                h["lon"] = hlon
                h["alt"] = halt
                h["konum_guvenilir"] = guvenilir
                h["konum_gerekce"] = gerekce
                h["poz_kaynak"] = kaynak_turu
                hedefler.append(h)
            kameralar.append({"kamera": k.get("kamera"),
                              "poz_kaynak": kaynak_turu,
                              "kalibrasyon": kal,
                              "hedefler": hedefler})
        try:
            oid = int(ornek_id)
        except (TypeError, ValueError):
            return False
        if oid <= 0:
            return False
        with self._kilit:
            self._veri[oid] = {
                "zaman": alis_ts,
                "kopru_ad": str(kopru_ad or "")[:160],
                "firma_id": int(firma_id) if firma_id else None,
                "kurulum_uid": str(kurulum_uid or "")[:160],
                "kameralar": kameralar,
            }
            self.paket_sayisi += 1
            self.son_paket_ts = alis_ts
        return True

    def sil(self, ornek_id):
        with self._kilit:
            self._veri.pop(ornek_id, None)

    def listele(self, firma_id=None):
        """Arayüz için hedefleri döndürür; firma verilirse sıkı süzer."""
        simdi = time.time()
        try:
            fid = int(firma_id) if firma_id else None
        except (TypeError, ValueError):
            fid = None
        cikti = []
        with self._kilit:
            olu = [oid for oid, d in self._veri.items()
                   if simdi - d["zaman"] > SIL_SN]
            for oid in olu:
                self._veri.pop(oid, None)
            for oid, d in self._veri.items():
                kayit_fid = int(d.get("firma_id") or 0)
                if (fid is None and kayit_fid != 0) or (
                        fid is not None and kayit_fid != fid):
                    continue
                yas = simdi - d["zaman"]
                cikti.append({
                    "ornek_id": oid,
                    "kopru_ad": d["kopru_ad"],
                    "yas_sn": round(yas, 2),
                    "bayat": yas > BAYAT_SN,
                    "kameralar": d["kameralar"],
                })
        return cikti

    def hedef_baglam_bul(self, ornek_id, kamera, iz, firma_id=None):
        """Bayat olmayan hedefi, güvenilir sunucu bağlamıyla atomik döndürür.

        İstemcinin gönderdiği köprü/kamera/kaynak dron alanları karar kaynağı
        değildir. Bu yordam aynı kilit altında hedefi ve onu üreten kamera
        kalibrasyonunu bulur; böylece doğrulama sırasında paket değişip iki ayrı
        bağlamın karışması önlenir.
        """
        simdi = time.time()
        try:
            oid = int(ornek_id)
            fid = int(firma_id) if firma_id is not None else None
        except (TypeError, ValueError):
            return None
        with self._kilit:
            d = self._veri.get(oid)
            if not d or simdi - d["zaman"] > BAYAT_SN:
                return None
            kayit_fid = int(d.get("firma_id") or 0)
            if ((fid is None and kayit_fid != 0) or
                    (fid is not None and kayit_fid != fid)):
                return None
            for k in d["kameralar"]:
                if str(k.get("kamera")) != str(kamera):
                    continue
                for h in (k.get("hedefler") or []):
                    if str(h.get("iz")) != str(iz):
                        continue
                    return {
                        "ornek_id": oid,
                        "firma_id": kayit_fid or None,
                        "kopru_ad": str(d.get("kopru_ad") or "")[:160],
                        "kurulum_uid": str(d.get("kurulum_uid") or "")[:160],
                        "kamera": k.get("kamera"),
                        "kalibrasyon": dict(k.get("kalibrasyon") or {}),
                        "hedef": dict(h),
                        "paket_zamani": float(d.get("zaman") or 0.0),
                        "yas_sn": max(0.0, simdi - float(d.get("zaman") or 0.0)),
                    }
        return None

    def hedef_bul(self, ornek_id, kamera, iz, firma_id=None):
        """Bayat olmayan hedefi döndürür; firma verilirse kesin sahiplik arar."""
        baglam = self.hedef_baglam_bul(ornek_id, kamera, iz, firma_id)
        return dict(baglam["hedef"]) if baglam else None

    def sayim(self, firma_id=None):
        try:
            fid = int(firma_id) if firma_id else None
        except (TypeError, ValueError):
            fid = None
        with self._kilit:
            veriler = [d for d in self._veri.values()
                       if ((fid is None and int(d.get("firma_id") or 0) == 0)
                           or (fid is not None and
                               int(d.get("firma_id") or 0) == fid))]
            kopru = len(veriler)
            hedef = sum(len(k.get("hedefler") or [])
                        for d in veriler for k in d["kameralar"])
        return {"kopru": kopru, "hedef": hedef,
                "paket": self.paket_sayisi,
                "son_paket_ts": self.son_paket_ts}


class AngajmanKuyrugu:
    """Operatörün onayladığı hedeflerin karar kaydı."""

    DURUMLAR = ("beklemede", "onayli", "reddedildi", "iptal")

    def __init__(self):
        self._kilit = threading.Lock()
        self._kayitlar = []
        self._sira = 0

    def ekle(self, ornek_id, kamera, hedef, operator="", firma_id=None):
        with self._kilit:
            self._sira += 1
            try:
                fid = int(firma_id) if firma_id is not None else None
            except (TypeError, ValueError):
                fid = None
            kayit = {
                "id": self._sira,
                "firma_id": fid,
                "ornek_id": ornek_id,
                "kamera": kamera,
                "iz": hedef.get("iz"),
                "tur": hedef.get("tur"),
                "puan": hedef.get("puan"),
                "ort_puan": hedef.get("ort_puan"),
                "azimut": hedef.get("azimut"),
                "yukselis": hedef.get("yukselis"),
                "mesafe_m": hedef.get("mesafe_m"),
                "mesafe_guven": hedef.get("mesafe_guven"),
                "mesafe_kaynak": hedef.get("mesafe_kaynak"),
                "kalibre": hedef.get("kalibre"),
                "lat": hedef.get("lat"),
                "lon": hedef.get("lon"),
                "alt": hedef.get("alt"),
                "konum_guvenilir": bool(hedef.get("konum_guvenilir")),
                "konum_gerekce": hedef.get("konum_gerekce") or "",
                "poz_kaynak": hedef.get("poz_kaynak") or "manuel",
                "oncelik": hedef.get("oncelik"),
                "durum": "beklemede",
                "ekleyen": operator,
                "eklendi_ts": time.time(),
                "karar_veren": None,
                "karar_ts": None,
                "not": "",
            }
            self._kayitlar.append(kayit)
            if len(self._kayitlar) > KUYRUK_SINIR:
                karar_verilmis = [k for k in self._kayitlar
                                  if k["durum"] != "beklemede"]
                if karar_verilmis:
                    self._kayitlar.remove(karar_verilmis[0])
            return dict(kayit)

    def karar(self, kayit_id, durum, operator="", aciklama="", firma_id=None):
        if durum not in self.DURUMLAR:
            return None, "gecersiz durum"
        try:
            fid = int(firma_id) if firma_id is not None else None
        except (TypeError, ValueError):
            return None, "gecersiz firma"
        with self._kilit:
            for k in self._kayitlar:
                if k["id"] == kayit_id:
                    kayit_fid = int(k.get("firma_id") or 0)
                    if ((fid is None and kayit_fid != 0) or
                            (fid is not None and kayit_fid != fid)):
                        return None, "kayit bulunamadi"
                    if k["durum"] != "beklemede":
                        return None, "karar zaten verilmis: %s" % k["durum"]
                    k["durum"] = durum
                    k["karar_veren"] = operator
                    k["karar_ts"] = time.time()
                    k["not"] = aciklama or ""
                    return dict(k), None
        return None, "kayit bulunamadi"

    def listele(self, durum=None, firma_id=None):
        try:
            fid = int(firma_id) if firma_id is not None else None
        except (TypeError, ValueError):
            return []
        with self._kilit:
            return [dict(k) for k in self._kayitlar
                    if (((fid is None and int(k.get("firma_id") or 0) == 0)
                         or (fid is not None and
                             int(k.get("firma_id") or 0) == fid))
                        and (not durum or k["durum"] == durum))]

    def sayim(self, firma_id=None):
        try:
            fid = int(firma_id) if firma_id is not None else None
        except (TypeError, ValueError):
            fid = -1
        with self._kilit:
            secili = [k for k in self._kayitlar
                      if ((fid is None and int(k.get("firma_id") or 0) == 0)
                          or (fid is not None and
                              int(k.get("firma_id") or 0) == fid))]
            s = {d: 0 for d in self.DURUMLAR}
            for k in secili:
                s[k["durum"]] = s.get(k["durum"], 0) + 1
            s["toplam"] = len(secili)
        return s


DEPO = HedefDeposu()
KUYRUK = AngajmanKuyrugu()
