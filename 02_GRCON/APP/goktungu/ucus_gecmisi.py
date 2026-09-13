# =====================================================================
# GOKTUNGU - UCUS GECMISI (DRON HISTORY)
# ---------------------------------------------------------------------
# v2.4.21: TAMAMEN YENIDEN YAZILDI (normalize veri modeli)
#
# Eski model (v2.4.20 ve oncesi):
#   - Takeoff/land tespit edilir, arasi bellekte biriktirilir ve
#     "ucuslar" tablosuna JSON iz dizisi olarak yazilirdi.
#   - Tespit kaciran her durumda (irtifa telemetrisi yok, kisa ucus,
#     erken disarm) ucus HIC kaydedilmiyordu.
#
# Yeni model:
#   - Dron bagli oldugu SURECE telemetri kesintisiz `telemetri`
#     tablosuna yazilir (sunucu.py::_telemetri_kaydet).
#   - Ucuslar sonradan `v_ucuslar` GORUNUMU ile tespit edilir
#     (veritabani.py::_gorunumleri_olustur, gaps-and-islands).
#   - Bu modul artik yalnizca (a) dron rengi ve (b) history API'nin
#     gorunum uzerinden okunmasindan sorumludur; ucus kaydi TUTMAZ.
#
# Frontend sozlesmesi (js/gecmis.js, js/pilot_hakkinda.js) aynen
# korunmustur: dron_listesi() / ucus_oku() ayni alanlari dondurur.
# =====================================================================
import json
import os
import threading
import time

from .sabitler import PROJE_KOKU, _veri_yolu
from . import veritabani

GECMIS_DIZIN = _veri_yolu("gcs_ucus_gecmisi")

# =====================================================================
# v2.4.42: KISA UCUS UID (belge esleme kodu)
# =====================================================================
# Ucuslar bu dalda kalici satir DEGILDIR: v_ucuslar GORUNUMU ile
# telemetriden turetilir. Bu yuzden rastgele/artan bir UID
# KULLANILAMAZ -- ucus yeniden hesaplandiginda numara degisir ve
# imzali iki belge (ucus raporu / grafik cikti) celisir.
#
# Cozum: UID mevcut `v_ucuslar.id` stringinden DETERMINISTIK turetilir.
# `id` bicimi: YYYYMMDD_HHMMSS_D{sysid} (dron + kalkis saniyesi) =>
# zaten benzersiz ve sabit. Ayni ucus her zaman ayni kodu verir;
# sunucu yeniden baslasa, rapor aylar sonra alinsa da kod degismez.
#
# Alfabe: Crockford Base32 benzeri; I, L, O, U YOK.
#   * I/1 ve O/0 karismasi engellenir (telefonda okunacak)
#   * U cikarilinca istenmeyen kelime uretimi azalir
# ONEMLI: Bu algoritmanin BIREBIR ayni kopyasi js/ucus_uid.js
# icinde de vardir (arayuz ayni kodu gostermek zorunda). Biri
# degisirse digeri de degismeli; test bu esitligi dogrular.
UID_ALFABE = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def ucus_uid(ucus_id):
    """Ucus id'sinden kisa, okunabilir, deterministik kod uretir.

    Bicim: XXXX-XXXX (8 karakter + tire). FNV-1a 64-bit hash'in
    dusuk 40 biti Base32 ile yazilir.

    >>> ucus_uid("20260809_143502_D41")  # her zaman ayni sonuc
    """
    s = str(ucus_id or "")
    if not s:
        return ""
    # FNV-1a 64-bit
    h = 0xCBF29CE484222325
    for b in s.encode("utf-8"):
        h ^= b
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    # Dusuk 40 bit -> 8 karakter Base32 (8 * 5 = 40)
    h &= 0xFFFFFFFFFF
    ch = []
    for _ in range(8):
        ch.append(UID_ALFABE[h & 0x1F])
        h >>= 5
    kod = "".join(reversed(ch))
    return kod[:4] + "-" + kod[4:]

# Ayirt edilebilir dron renk paleti (koyu/acik temada okunur tonlar)
RENK_PALETI = [
    "#00E5FF",  # camgobegi
    "#FF9100",  # turuncu
    "#76FF03",  # acik yesil
    "#FF4081",  # pembe
    "#FFD740",  # amber
    "#7C4DFF",  # mor
    "#18FFFF",  # turkuaz
    "#FF6E40",  # mercan
    "#B2FF59",  # limon
    "#40C4FF",  # acik mavi
    "#F50057",  # fusya
    "#64FFDA",  # nane
]


class UcusGecmisi:
    """Dron rengi + gorunum tabanli ucus gecmisi API'si.

    v2.4.21'den itibaren telemetri kaydi bu sinifin sorumlulugunda
    DEGILDIR (sunucu.py yapar). Burada kalan isler:
      * renk_al()      : dron basina kalici renk (dronlar.renk)
      * dron_listesi() : history panel sol listesi (v_ucuslar)
      * ucus_oku()     : bir ucusun iz noktalari (telemetri araligi)
      * ucus_sil() / tumunu_sil()
      * aktif_ucus_id(): AI tespitlerini devam eden ucusa baglamak icin
    """

    def __init__(self, konsol):
        self.konsol = konsol
        self.kilit = threading.Lock()
        veritabani.tablolari_olustur()
        self._eski_veriyi_devre_disi_birak()

    # ------------------------------------------------------------------
    # Eski JSON klasoru: artik aktarilmaz, yalnizca devre disi birakilir.
    # (v2.4.21 migrasyonu eski "ucuslar" tablosunu zaten temizler.)
    # ------------------------------------------------------------------
    def _eski_veriyi_devre_disi_birak(self):
        if not os.path.isdir(GECMIS_DIZIN):
            return
        try:
            os.replace(GECMIS_DIZIN, GECMIS_DIZIN + ".eski")
            self.konsol("HISTORY",
                        "Eski JSON ucus klasoru devre disi birakildi "
                        "(gcs_ucus_gecmisi.eski). v2.4.21 telemetri "
                        "tabanli kayda gecildi.")
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Renk atamasi (kalici; dronlar.renk sutununda)
    # ------------------------------------------------------------------
    @staticmethod
    def _anahtar(d):
        """Geriye uyumluluk: dict veya uid stringinden anahtar uretir."""
        if isinstance(d, dict):
            uid = d.get("uid") or ""
            return str(uid) if uid else ("sysid_" + str(d.get("sysid")))
        return str(d or "")

    def renk_al(self, d):
        """Dron icin kalici renk dondurur; kayitli degilse yeni atar.

        `d` bir telemetri sozlugu veya dogrudan UID stringi olabilir
        (dron.py::kimlik_kaydet UID ile cagirir).
        """
        anahtar = self._anahtar(d)
        if not anahtar or anahtar.startswith("sysid_"):
            # Henuz kalici kimlik yok: gecici renk (kayit yapilmaz)
            try:
                n = int(anahtar.split("_", 1)[1])
            except (IndexError, ValueError):
                n = 0
            return RENK_PALETI[n % len(RENK_PALETI)]
        with self.kilit:
            try:
                kayit = veritabani.dron_kaydi_oku(uid=anahtar)
            except Exception:
                kayit = None
            if kayit and kayit.get("renk"):
                return kayit["renk"]
            # Kullanilmayan ilk rengi sec
            try:
                kullanilan = {k.get("renk") for k in
                              veritabani.dron_kayitlari_listele()}
            except Exception:
                kullanilan = set()
            renk = next((r for r in RENK_PALETI if r not in kullanilan),
                        RENK_PALETI[len(kullanilan) % len(RENK_PALETI)])
            if kayit:
                try:
                    veritabani.dron_alan_guncelle(kayit["id"], renk=renk)
                except Exception:
                    pass
            return renk

    def renk_haritasi(self, dronlar):
        """Telemetri paketi icin {sysid: renk} eslemesi uretir.

        Eskiden isle() bu isi yapiyordu; artik ucus kaydi olmadigi icin
        sunucu.py yalnizca renkleri almak uzere bunu cagirir.
        """
        renkler = {}
        for d in dronlar:
            sysid = d.get("sysid")
            if sysid is None:
                continue
            try:
                renkler[str(sysid)] = self.renk_al(d)
            except Exception:
                continue
        return renkler

    # ------------------------------------------------------------------
    # v2.4.2 uyumu: AI tespitlerini devam eden ucusa baglama
    # ------------------------------------------------------------------
    def aktif_ucus_id(self, dron_uid):
        """Dron kimligi icin SU AN devam eden ucusun id'sini dondurur.

        `dron_uid` bicimi js/dron_kamera.js::dronUid() ile ayni:
        donanim uid varsa uid, yoksa 'sysid:N'.

        VIEW tabanli mimaride "devam eden ucus" = son telemetri ornegi
        UCUS_BOSLUK icinde olan en yeni ucus segmenti.
        """
        uid = str(dron_uid or "")
        if not uid:
            return None
        dron_id = None
        try:
            if uid.startswith("sysid:"):
                dron_id = veritabani.dron_id_bul(
                    sysid=int(uid.split(":", 1)[1]))
            else:
                dron_id = veritabani.dron_id_bul(uid=uid)
        except (TypeError, ValueError):
            return None
        except Exception:
            return None
        if not dron_id:
            return None
        try:
            liste = veritabani.ucus_listesi(dron_id=dron_id, yonetici=True,
                                            limit=1)
        except Exception:
            return None
        if not liste:
            return None
        u = liste[0]
        # Son ornek yakin zamanda mi? (surmeyen ucusa tespit baglanmasin)
        if (time.time() - float(u.get("bitis") or 0)) > veritabani.UCUS_BOSLUK:
            return None
        return u.get("id")

    # ------------------------------------------------------------------
    # History API (WS komutlari)
    # ------------------------------------------------------------------
    def dron_listesi(self, eposta=None, yonetici=False,
                     firma_id=None):
        """History panel sol listesi: kayitli dronlar + tespit edilen
        ucuslar.

        Frontend sozlesmesi (js/gecmis.js, js/pilot_hakkinda.js):
          [{anahtar, isim, sysid, uid, renk, kayit_ts, kaydeden,
            ucuslar: [{id, baslangic, sure, nokta, max_irtifa,
                       pilotlar}]}]
        """
        try:
            # v2.4.53: merkezde cok firmali calisirken yalnizca
            # pilotun firmasina ait dronlar listelenir.
            dronlar = veritabani.dron_kayitlari_listele(
                firma_id=firma_id)
        except Exception as e:
            self.konsol("HISTORY", f"Dron listesi okunamadi: {e}", "hata")
            return []
        try:
            ucuslar = veritabani.ucus_listesi(
                eposta=eposta or "", yonetici=yonetici,
                limit=2000, firma_id=firma_id)
        except Exception as e:
            self.konsol("HISTORY", f"Ucus listesi okunamadi: {e}", "hata")
            ucuslar = []
        gruplu = {}
        for u in ucuslar:
            gruplu.setdefault(u["dron_id"], []).append({
                "id": u["id"],
                "baslangic": u["baslangic"],
                "bitis": u["bitis"],
                "sure": u["sure"],
                "nokta": u["nokta"],
                "max_irtifa": u["max_irtifa"],
                "max_hiz": u.get("max_hiz"),
                "ort_hiz": u.get("ort_hiz"),
                "pilotlar": u.get("pilotlar") or [],
                # v2.4.42: ad soyad (rapor pilot satiri icin)
                "pilotlar_ad": u.get("pilotlar_ad") or [],
                # v2.4.42: kisa belge esleme kodu (rapor <-> grafik)
                "kod": ucus_uid(u["id"]),
                # FAZ18-IS22-SAHIP-GECIS: pilot filtresi sahiplik kuralini
                # yansitmali. Kullanicinin baglayici talimati:
                # "takeoff'u kim verdiyse o ucusun sahibi odur".
                # `pilotlar` telemetride adi gecen HERKESI icerir
                # (vardiya, gozlemci) -> sahiplik kaniti DEGIL.
                # Kaynak: veritabani.ucus_listesi() bu iki alani
                # kalkis_kontrolleri tablosundan cozer; o tablo
                # SUNUCUDA damgalanir, istemci gonderemez.
                "sahip_eposta": u.get("sahip_eposta") or "",
                "sahip_ad": u.get("sahip_ad") or "",
            })
        sonuc = []
        for d in dronlar:
            liste = gruplu.get(d["id"], [])
            # En eski ustte (frontend reverse() ile en yeniyi one alir)
            liste.sort(key=lambda x: x["baslangic"] or 0)
            sonuc.append({
                "dron_id": d["id"],
                "anahtar": d["uid"],
                "isim": (d.get("isim")
                         or ("DRON " + str(d.get("sysid") or "?"))),
                "sysid": d.get("sysid"),
                "uid": d.get("uid", ""),
                "uid_kaynak": d.get("uid_kaynak", ""),
                "renk": d.get("renk") or RENK_PALETI[0],
                "arac_sinifi": d.get("arac_sinifi", ""),
                # v2.4.42: MAV_TYPE — rapor arac turu satirinin kaynagi.
                # arac_sinifi baglanti etiketidir, arac turu DEGILDIR.
                "arac_tipi": d.get("arac_tipi"),
                "otopilot": d.get("otopilot", ""),
                "firmware": d.get("firmware", ""),
                "kayit_ts": d.get("ilk_kayit_ts") or 0,
                "kaydeden": d.get("kaydeden_isim")
                or d.get("kaydeden_eposta") or "",
                "ucuslar": liste,
            })
        return sonuc

    # ------------------------------------------------------------------
    # v2.4.64: SAHIPLIK DENETIMI (yetkilendirme)
    # ------------------------------------------------------------------
    def sahip_mi(self, ucus_id, eposta, yonetici=False):
        """Bir ucusa erisim yetkisi var mi?

        Kural (operatorun baglayici talimati): ucusun sahibi TAKEOFF'u
        veren pilottur. Yonetici tum ucuslara erisir.

        Bu denetim listeden BAGIMSIZ olarak gereklidir. Listeyi suzmek
        yalnizca gorunurlugu kisitlar; erisimi kisitlamaz. Uçus kimligi
        bilinen (veya denenen) bir kayit, suzgeç ne olursa olsun
        `ucus_oku` / `ucus_sil` ile acilabilir ve SILINEBILIRDI.

        Donus: (izin_var, sebep)
        """
        if yonetici:
            return True, ""
        e = str(eposta or "").strip().lower()
        if not e:
            return False, "kimlik yok"
        guvenli = "".join(c for c in str(ucus_id)
                          if c.isalnum() or c in "_-")
        try:
            u = veritabani.ucus_bul(guvenli)
        except Exception as hata:
            self.konsol("HISTORY",
                        f"Sahiplik denetimi yapilamadi: {hata}", "hata")
            return False, "denetim hatasi"
        if u is None:
            return False, "ucus yok"
        # Sahip, ucus segmentine karsilik gelen kalkis kontrolunden
        # cozulur. ucus_listesi() ile AYNI kural kullanilir; iki yerde
        # farkli kural olursa biri digerini bosa cikarir.
        try:
            sahip = veritabani.ucus_sahibi(
                u["dron_id"], u["baslangic"], u["bitis"])
        except Exception as hata:
            self.konsol("HISTORY",
                        f"Ucus sahibi okunamadi: {hata}", "hata")
            return False, "denetim hatasi"
        if not sahip:
            return False, "sahipsiz ucus (yalniz yonetici)"
        if str(sahip).strip().lower() != e:
            return False, "baska pilotun ucusu"
        return True, ""

    def ucus_oku(self, ucus_id):
        """Bir ucusun tam iz verisini dondurur (oynatici icin).

        DIKKAT: Bu fonksiyon yetki denetimi YAPMAZ. Cagiran taraf once
        `sahip_mi()` ile yetkiyi dogrulamak ZORUNDADIR.

        Donus sozlesmesi:
          {id, anahtar, sysid, isim, baslangic, bitis, pilotlar,
           pilotlar_ad, arac_tipi, arac_sinifi,
           noktalar: [[t_rel, lat, lon, alt_rel, hiz, yaw,
                       bat_y, bat_v], ...]}

        [v2.4.41] Batarya alanlari (indeks 6 = yuzde, 7 = voltaj) dizinin
        SONUNA eklendi; 0-5 arasi DEGISMEDI, iz oynaticisi etkilenmez.
        Imzali ucus raporu batarya bilgisini buradan alir.

        [v2.4.42] `pilotlar_ad` (ad soyad) ve `arac_tipi` (MAV_TYPE)
        eklendi. Imzali rapor pilot satirina e-posta yerine ad soyad,
        arac turu satirina MAV_TYPE'tan turetilen gercek sinif yazar.
        `arac_sinifi` baglanti etiketidir (KAMIKAZE/DJI/BILINMEYEN) ve
        arac turu YERINE kullanilamaz.
        """
        guvenli = "".join(c for c in str(ucus_id)
                          if c.isalnum() or c in "_-")
        try:
            u = veritabani.ucus_bul(guvenli)
        except Exception as e:
            self.konsol("HISTORY", f"Ucus okunamadi: {e}", "hata")
            return None
        if u is None:
            return None
        try:
            noktalar = veritabani.ucus_iz_oku(
                u["dron_id"], u["baslangic"], u["bitis"])
        except Exception as e:
            self.konsol("HISTORY", f"Ucus izi okunamadi: {e}", "hata")
            noktalar = []
        # v2.4.42: Pilot e-postasi VE ad soyadi birlikte cozumlenir.
        # Sira: telemetri.pilot_isim -> kullanicilar.ad_soyad -> eposta.
        pilotlar, pilotlar_ad = [], []
        try:
            with veritabani.baglanti() as con:
                defter = {}
                try:
                    for r in con.execute(
                            "SELECT eposta, ad_soyad FROM kullanicilar"):
                        e_ = str(r["eposta"] or "").strip().lower()
                        a_ = str(r["ad_soyad"] or "").strip()
                        if e_ and a_:
                            defter[e_] = a_
                except Exception:
                    defter = {}
                for r in con.execute(
                        "SELECT pilot_eposta,"
                        " MAX(pilot_isim) AS pilot_isim FROM telemetri"
                        " WHERE dron_id=? AND ts BETWEEN ? AND ?"
                        " AND pilot_eposta <> ''"
                        " GROUP BY pilot_eposta",
                        (u["dron_id"], u["baslangic"], u["bitis"])):
                    ep = str(r["pilot_eposta"] or "").strip()
                    if not ep:
                        continue
                    pilotlar.append(ep)
                    isim = str(r["pilot_isim"] or "").strip()
                    if not isim:
                        isim = defter.get(ep.lower(), "")
                    pilotlar_ad.append(isim or ep)
        except Exception:
            pass
        # v2.4.42: MAV_TYPE (arac_tipi) kayitli dron kaydindan alinir.
        arac_tipi, arac_sinifi = None, ""
        try:
            kayit = veritabani.dron_kaydi_oku(
                dron_id=u["dron_id"]) or {}
            if kayit.get("arac_tipi") is not None:
                arac_tipi = int(kayit.get("arac_tipi") or 0)
            arac_sinifi = str(kayit.get("arac_sinifi") or "")
        except Exception:
            pass
        return {
            "arac_tipi": arac_tipi,
            "arac_sinifi": arac_sinifi,
            "pilotlar_ad": pilotlar_ad,
            # v2.4.42: kisa belge esleme kodu. Imzali ucus raporu ve
            # yatay grafik ciktisi AYNI kodu basar -> iki belge bu
            # numara ile eslestirilip birlestirilebilir.
            "kod": ucus_uid(u["id"]),
            "id": u["id"],
            "dron_id": u["dron_id"],
            "anahtar": u.get("anahtar") or "",
            "sysid": u.get("sysid"),
            "isim": u.get("isim") or "",
            "baslangic": u["baslangic"],
            "bitis": u["bitis"],
            "sure": u.get("sure"),
            "max_irtifa": u.get("max_irtifa"),
            "max_hiz": u.get("max_hiz"),
            "ort_hiz": u.get("ort_hiz"),
            "pilotlar": pilotlar,
            "noktalar": noktalar,
        }

    def ucus_sil(self, ucus_id):
        """Bir ucusu siler = o araliktaki telemetri kayitlarini siler."""
        guvenli = "".join(c for c in str(ucus_id)
                          if c.isalnum() or c in "_-")
        try:
            u = veritabani.ucus_bul(guvenli)
            if u is None:
                return False
            n = veritabani.telemetri_aralik_sil(
                u["dron_id"], u["baslangic"], u["bitis"])
            if n:
                self.konsol("HISTORY",
                            f"Ucus silindi ({guvenli}): {n} telemetri "
                            "ornegi kaldirildi.")
            return n > 0
        except Exception as e:
            self.konsol("HISTORY", f"Ucus silinemedi: {e}", "hata")
            return False

    def tumunu_sil(self):
        """TUM ucus gecmisini siler (telemetri tablosu bosaltilir).

        Dron kimlik kayitlari, renkleri ve parametreleri KORUNUR.
        Donus: silinen telemetri ornegi sayisi.
        """
        try:
            n = veritabani.telemetri_tumunu_sil()
            self.konsol("HISTORY",
                        f"Tum ucus gecmisi silindi ({n} telemetri ornegi). "
                        "Dron kayitlari ve parametreleri korundu.")
            return n
        except Exception as e:
            self.konsol("HISTORY", f"Gecmis silinemedi: {e}", "hata")
            return 0

    # ------------------------------------------------------------------
    # v2.4.21: dron kayit yonetimi (history panelinden isim/not duzenleme)
    # ------------------------------------------------------------------
    def dron_guncelle(self, dron_id, **alanlar):
        try:
            return veritabani.dron_alan_guncelle(int(dron_id), **alanlar)
        except Exception as e:
            self.konsol("HISTORY", f"Dron kaydi guncellenemedi: {e}",
                        "hata")
            return False

    # ------------------------------------------------------------------
    # Geriye uyumluluk saplamasi
    # ------------------------------------------------------------------
    def isle(self, dronlar, simdi, pilotlar=None):
        """v2.4.21: ucus kaydi artik telemetri tablosundan tespit edilir.

        Eski cagiranlar kirilmasin diye korunmustur; yalnizca renk
        haritasi dondurur.
        """
        return self.renk_haritasi(dronlar)


# Modul duzeyinde json importu bazi eski cagirilarda kullaniliyordu;
# kaldirilmadi (ileride pilot listesi serilestirmesi icin gerekli).
_ = json
