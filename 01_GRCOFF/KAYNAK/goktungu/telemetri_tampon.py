# -*- coding: utf-8 -*-
"""Dakikalık fiziksel telemetri tamponu (v2.4.24).

Kullanıcı talebi (2026-08-04):
    "dron çalışmaya başladığında 1'er dakikalık fiziksel dosyalar
     tutalım sonra her bir dakikada bir veritabanına yazalım"

## Neden dosya tamponu

v2.4.23'te telemetri YALNIZCA bellekte (`sunucu._tel_tampon`)
tutuluyordu ve 5 saniyede bir veritabanına yazılıyordu. Üç ayrı veri
kaybı noktası ölçüldü:

1. `sunucu.py:169` — tampon yazma DENENMEDEN boşaltılıyor:
       satirlar, self._tel_tampon = self._tel_tampon, []
   Yazma başarısız olursa `satirlar` fonksiyon çıkışında yok olur.
   Her başarısız yazmada 5 saniyelik telemetri KALICI kaybolur.
2. `sunucu.py:173` — hata konsola yazılıyor, veri kurtarılmıyor.
3. `sunucu.py:141` — `dron_id` henüz yoksa örnek tamamen atlanıyor;
   dronun ilk saniyeleri (kalkış anı dahil) kaydedilmiyor.

Ayrıca `veritabani.py`'de `synchronous=NORMAL`'e geçildi (fsync
yükünü kaldırmak için). Bu, güç kesintisinde son işlemlerin
kaybedilebileceği anlamına gelir. Dosya tamponu tam bu boşluğu
kapatır: ham kayıt diskte olduğu için DB yazımı kaybedilse bile
veri geri alınabilir.

## Tasarım

- Ham örnekler JSONL olarak `veri/telemetri_tampon/` altına yazılır.
  Her satır bağımsız bir JSON nesnesidir; dosya ortadan kesilse bile
  önceki satırlar okunabilir (CSV/pickle'da bu garanti yok).
- Dosya adı dakika damgalıdır: `tel_YYYYMMDD_HHMM.jsonl`
- Her dakika, GEÇMİŞ dakikaların dosyaları veritabanına aktarılır.
  Açık olan (o an yazılan) dosyaya dokunulmaz.
- Aktarım başarılı olursa dosya `.aktarildi` uzantısıyla işaretlenir,
  SİLİNMEZ. `SAKLAMA_SAAT` sonra temizlenir.
  Hemen silinirse, aktarım sırasında oluşan bir hata veriyi yine yok
  eder — tamponun tüm amacı bu senaryoyu önlemektir.
- Aktarım başarısız olursa dosya olduğu gibi kalır ve sonraki turda
  yeniden denenir.
- `dron_id` bilinmiyorsa örnek YİNE dosyaya yazılır (`dron_id: null`).
  Aktarım sırasında hâlâ çözülemiyorsa satır `.cozulmedi` dosyasına
  taşınır; sessizce düşürülmez.

## Bu modül veritabanına bağımlı DEĞİL

Yazma yolu (`ekle`/`_yaz`) hiçbir DB çağrısı yapmaz. Veritabanı
tamamen erişilemez olsa bile telemetri diske akmaya devam eder.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

# ALAN LİSTESİ TEK KAYNAKTAN GELİR.
#
# Burada KENDİ kopyasını tutmak cazip ama TEHLİKELİ: şema değişince
# iki liste sessizce ayrışır. `kayit.get(a)` eksik anahtar için hata
# vermez, `None` döner — yani aktarım "başarılı" görünüp tamamen boş
# satırlar yazılır. Bu kusur ilk yazımda gerçekten oluştu: MAVLink
# paket adları (`alt_rel`, `groundspeed`, `heading`, `batarya_pct`)
# kullanılmıştı, oysa şema Türkçe kolon adları kullanıyor
# (`irtifa`, `hiz`, `yaw`, `batarya_y`).
#
# Bu yüzden liste `veritabani`den ALINIR, kopyalanmaz.
from .veritabani import TELEMETRI_ALANLARI as ALANLAR      # noqa: E402

# MAVLink paket alanı -> veritabanı kolonu eşlemesi.
# `sunucu.py` telemetriyi MAVLink adlarıyla üretir; tamponun yazma
# yolu bu eşlemeyi uygular ki dosyadaki anahtarlar şemayla birebir
# olsun ve aktarımda dönüştürme gerekmesin.
MAVLINK_ESLEME = {
    "alt_rel": "irtifa",
    "alt_msl": "irtifa_msl",
    "groundspeed": "hiz",
    "vz": "dikey_hiz",
    "heading": "yaw",
    "batarya_pct": "batarya_y",
}

DOSYA_ONEK = "tel_"
DOSYA_UZANTI = ".jsonl"
AKTARILDI_UZANTI = ".aktarildi"
COZULMEDI_UZANTI = ".cozulmedi"

# Aktarılmış dosyalar bu süre sonra silinir (güvenlik payı).
SAKLAMA_SAAT = 24

# Aktarım denemesi bu kadar başarısız olursa dosya karantinaya alınır;
# sonsuz yeniden deneme döngüsü oluşmasın.
MAKS_DENEME = 5


def _dakika_damgasi(ts: float) -> str:
    return time.strftime("%Y%m%d_%H%M", time.localtime(ts))


class TelemetriTampon:
    """Dakikalık JSONL dosyalarına yazar, dakikada bir DB'ye aktarır.

    İş parçacığı güvenlidir: `ekle` ve `dongu_adimi` farklı iş
    parçacıklarından çağrılabilir.
    """

    def __init__(self,
                 dizin: str,
                 konsol: Optional[Callable[..., None]] = None,
                 saklama_saat: int = SAKLAMA_SAAT):
        self.dizin = dizin
        self._konsol = konsol
        self.saklama_saat = saklama_saat

        self._kilit = threading.RLock()
        self._dosya = None            # açık dosya nesnesi
        self._dosya_dakika = ""       # açık dosyanın dakika damgası
        self._dosya_yolu = ""
        self._son_aktarim = 0.0
        self._son_temizlik = 0.0
        self._deneme: Dict[str, int] = {}   # dosya adı -> deneme sayısı

        # v2.4.25: BOZULMA ONARIM KANCASI (dışarıdan enjekte edilir).
        #
        # İmza: `onarim_kancasi(hata) -> bool` (onarım yapıldı mı)
        #
        # Neden kanca: bu modül veritabanından BAĞIMSIZ kalmalı; içine
        # `db_onarim` import etmek test edilebilirliği bozar ve döngüsel
        # bağımlılık yaratır. `sunucu.py` kurulumda enjekte eder.
        #
        # Neden gerekli: DB bozulduğunda aktarım her turda başarısız
        # olur, dosyalar birikir ve MAKS_DENEME sonrası karantinaya
        # gider. Onarım olmadan bu durum kendiliğinden düzelmez.
        self.onarim_kancasi: Optional[Callable[[Exception], bool]] = None

        # Sayaçlar (tanılama için)
        self.sayac = {
            "yazilan": 0,           # dosyaya yazılan satır
            "aktarilan": 0,         # DB'ye aktarılan satır
            "aktarim_hatasi": 0,
            "cozulmedi": 0,         # dron_id çözülemeyen satır
            "bozuk_satir": 0,       # JSON çözümlenemeyen satır
            "silinen_dosya": 0,
            "karantina": 0,
            # Toplu yazma kısıt ihlaliyle düştüğünde satır bazlı
            # kurtarmada atlanan satır sayısı (kalan veri kurtarılır).
            "kisit_atlanan": 0,
        }

        os.makedirs(self.dizin, exist_ok=True)

    # ------------------------------------------------------------------
    def _log(self, mesaj: str, tur: str = "bilgi") -> None:
        if self._konsol:
            try:
                self._konsol("TEL", mesaj, tur)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # YAZMA YOLU — veritabanına HİÇ dokunmaz
    # ------------------------------------------------------------------
    def ekle(self, kayit: Dict[str, Any], simdi: Optional[float] = None
             ) -> bool:
        """Bir telemetri örneğini dakikalık dosyaya yazar.

        `kayit` sözlüğü ALANLAR anahtarlarını içerebilir; eksik olanlar
        `None` sayılır. `dron_id` None olabilir (kimlik henüz
        oluşmamıştır) — örnek YİNE kaydedilir.

        Döner: yazma başarılıysa True.
        """
        if simdi is None:
            simdi = time.time()

        satir = self._normalle(kayit, simdi)

        try:
            with self._kilit:
                f = self._dosya_al(simdi)
                f.write(json.dumps(satir, ensure_ascii=False,
                                   separators=(",", ":")))
                f.write("\n")
                f.flush()          # satır diske gitsin (çökme dayanıklılığı)
                self.sayac["yazilan"] += 1
            return True
        except OSError as e:
            # Diske yazamıyorsak sessiz kalmamalıyız; ama telemetri
            # döngüsünü de çökertmemeliyiz.
            self._log(f"Tampon dosyasina yazilamadi: {e}", "hata")
            return False

    def coklu_ekle(self, kayitlar: List[Dict[str, Any]],
                   simdi: Optional[float] = None) -> int:
        """Birden çok örneği tek dosya açılışıyla yazar."""
        if simdi is None:
            simdi = time.time()
        n = 0
        try:
            with self._kilit:
                f = self._dosya_al(simdi)
                for kayit in kayitlar:
                    satir = self._normalle(kayit, simdi)
                    f.write(json.dumps(satir, ensure_ascii=False,
                                       separators=(",", ":")))
                    f.write("\n")
                    n += 1
                f.flush()
                self.sayac["yazilan"] += n
        except OSError as e:
            self._log(f"Tampon dosyasina yazilamadi: {e}", "hata")
        return n

    def _normalle(self, kayit: Dict[str, Any],
                  simdi: float) -> Dict[str, Any]:
        """MAVLink adlarini sema kolonlarina cevirir.

        Hem MAVLink adi (`alt_rel`) hem sema adi (`irtifa`) kabul
        edilir; boylece cagiran taraf hangisini kullanirsa kullansin
        dosyaya SEMA adlariyla yazilir. Bilinmeyen anahtarlar
        DUSURULUR (sema disi veri aktarimda hataya yol acar).
        """
        satir: Dict[str, Any] = {}
        for anahtar, deger in kayit.items():
            kolon = MAVLINK_ESLEME.get(anahtar, anahtar)
            if kolon in ALANLAR:
                satir[kolon] = deger
        if satir.get("ts") is None:
            satir["ts"] = round(float(simdi), 2)
        return satir

    def _dosya_al(self, simdi: float):
        """Geçerli dakikanın dosyasını döndürür, gerekirse döndürür."""
        dk = _dakika_damgasi(simdi)
        if self._dosya is not None and self._dosya_dakika == dk:
            return self._dosya

        # Dakika değişti (ya da ilk açılış): eskisini kapat
        self._dosya_kapat()

        yol = os.path.join(self.dizin, f"{DOSYA_ONEK}{dk}{DOSYA_UZANTI}")
        # 'a' modu: süreç yeniden başlarsa aynı dakikanın verisi
        # üzerine yazılmaz, eklenir.
        self._dosya = open(yol, "a", encoding="utf-8")
        self._dosya_dakika = dk
        self._dosya_yolu = yol
        return self._dosya

    def _dosya_kapat(self) -> None:
        if self._dosya is not None:
            try:
                self._dosya.flush()
                os.fsync(self._dosya.fileno())
            except OSError:
                pass
            try:
                self._dosya.close()
            except OSError:
                pass
            self._dosya = None
            self._dosya_dakika = ""
            self._dosya_yolu = ""

    # ------------------------------------------------------------------
    # AKTARIM YOLU — veritabanına yazar
    # ------------------------------------------------------------------
    def bekleyen_dosyalar(self, simdi: Optional[float] = None) -> List[str]:
        """Aktarıma hazır dosyaları döndürür (açık dosya HARİÇ).

        Açık dosya hariç tutulur; yoksa o an yazılmakta olan dakikanın
        yarısı aktarılır ve kalan satırlar bir daha aktarılmaz.

        ## v2.4.43 — AÇIK DOSYA ARTIK ADIYLA HARİÇ TUTULUR

        Eskiden hariç tutma YALNIZCA dakika damgası karşılaştırmasına
        dayanıyordu (`dk >= simdiki_dk`). Bu, açık dosyanın hariç
        tutulduğunu GARANTİ ETMEZ:

        Telemetri akışı durursa (dron gitti, bağlantı koptu) `ekle()`
        bir daha çağrılmaz; dolayısıyla `_dosya_al()` de çağrılmaz ve
        dakika dönüşünde `_dosya_kapat()` HİÇ çalışmaz. Dakika ilerler,
        dosya "bekleyen" sayılır ama işletim sistemi düzeyinde HÂLÂ
        AÇIKTIR.

        POSIX'te açık dosyayı yeniden adlandırmak sorunsuz çalıştığı
        için bu kusur Linux'ta hiç görülmedi. Windows'ta ise
        `os.replace` `[WinError 32]` verir, dosya `.jsonl` olarak kalır
        ve aynı örnekler her turda YENİDEN veritabanına yazılır
        (kullanıcı raporu, 2026-08-09: aynı 17 örnek sonsuz döngüde).

        Çözüm iki adımlı: (1) bayatlamış açık dosya burada KAPATILIR,
        (2) hâlâ açık kalan dosya adı listeden çıkarılır.
        """
        if simdi is None:
            simdi = time.time()
        simdiki_dk = _dakika_damgasi(simdi)

        # (1) Açık dosyanın dakikası geçmişse kapat. Yazma yolu artık
        # bu dosyaya dokunmayacağı için kapatmak güvenlidir; bir sonraki
        # `ekle()` çağrısı güncel dakika için yenisini açar.
        with self._kilit:
            if (self._dosya is not None and self._dosya_dakika
                    and self._dosya_dakika < simdiki_dk):
                self._dosya_kapat()
            acik_ad = (os.path.basename(self._dosya_yolu)
                       if self._dosya is not None else "")

        try:
            adlar = os.listdir(self.dizin)
        except OSError:
            return []

        sonuc = []
        for ad in adlar:
            if not ad.startswith(DOSYA_ONEK) or not ad.endswith(DOSYA_UZANTI):
                continue
            # (2) Hâlâ açık olan dosyaya ASLA dokunulmaz.
            if acik_ad and ad == acik_ad:
                continue
            dk = ad[len(DOSYA_ONEK):-len(DOSYA_UZANTI)]
            if dk >= simdiki_dk:
                continue          # geçerli veya gelecek dakika: bekle
            if self._deneme.get(ad, 0) >= MAKS_DENEME:
                continue          # karantina
            sonuc.append(ad)
        return sorted(sonuc)

    # ------------------------------------------------------------------
    # v2.4.51: AKTARIM DEFTERI (PostgreSQL)
    # ------------------------------------------------------------------
    # Kullanici istegi: dosya tabanli tamponlar PostgreSQL'e tasinsin.
    #
    # OLCUM (dene_kesinti.py, gercek PG 16):
    #   Dogrudan PG'ye yazma, ag kesintisinde 60/120 ornek KALICI KAYIP
    #   Dosya tamponu ile               , ayni kesintide 0 kayip
    #
    # Bu yuzden HAM ORNEKLERIN ILK YAZIMI diskte kalir; veritabani
    # erisilemezken telemetri kaybolmaz. Ancak aktarim KAYIT DEFTERI
    # PG'ye yazilir: hangi dakika dosyasi ne zaman, kac satirla
    # aktarildi merkezi olarak izlenebilir. Veri kalici olarak PG'de
    # tutulur (telemetri tablosu), dosya yalnizca gecis tamponudur.
    def _defter_yaz(self, dosya, satir, durum, deneme, hata, ts):
        """Aktarim kaydini PG defterine yazar (hata aktarimi durdurmaz)."""
        if getattr(self, "_defter_kapali", False):
            return
        try:
            from . import veritabani as vt
            if not vt.pg_kipinde():
                return          # SQLite kipi: defter tutulmaz
            from . import pg
            if not pg.yapilandirma_var():
                return
            with vt.baglanti() as con:
                con.execute(
                    "INSERT OR REPLACE INTO telemetri_tampon_kayit"
                    " (dosya, satir, durum, deneme, hata, ts)"
                    " VALUES (?,?,?,?,?,?)",
                    (str(dosya), int(satir), str(durum), int(deneme),
                     str(hata or "")[:500], float(ts)))
        except Exception:
            # Defter YARDIMCI kayittir; yazilamamasi telemetri
            # aktarimini ASLA engellememeli.
            self._defter_kapali = True

    def aktar(self, yazici: Callable[[List[Tuple]], Any],
              dron_id_cozucu: Optional[Callable[[Dict], Optional[int]]] = None,
              simdi: Optional[float] = None) -> Dict[str, int]:
        """Bekleyen dosyaları veritabanına aktarır.

        `yazici`: satır demetleri listesi alan fonksiyon
                  (`veritabani.telemetri_toplu_yaz`).
        `dron_id_cozucu`: `dron_id` None olan satırlar için son bir
                  çözümleme şansı. None döndürürse satır
                  `.cozulmedi` dosyasına taşınır.
        """
        if simdi is None:
            simdi = time.time()

        ozet = {"dosya": 0, "satir": 0, "hata": 0, "cozulmedi": 0,
                "bozuk": 0}
        self._defter_kapali = getattr(self, "_defter_kapali", False)

        for ad in self.bekleyen_dosyalar(simdi):
            yol = os.path.join(self.dizin, ad)
            satirlar: List[Tuple] = []
            cozulmeyen: List[str] = []
            bozuk = 0

            try:
                with open(yol, "r", encoding="utf-8") as f:
                    for ham in f:
                        ham = ham.strip()
                        if not ham:
                            continue
                        try:
                            kayit = json.loads(ham)
                        except (ValueError, TypeError):
                            # Çökme anında yarım yazılmış son satır
                            # olabilir. Sayılır ama süreç durmaz.
                            bozuk += 1
                            continue

                        if kayit.get("dron_id") is None and dron_id_cozucu:
                            try:
                                kayit["dron_id"] = dron_id_cozucu(kayit)
                            except Exception:
                                kayit["dron_id"] = None

                        if kayit.get("dron_id") is None:
                            # FK kısıtı nedeniyle yazılamaz. Sessizce
                            # düşürmüyoruz; ayrı dosyaya taşıyoruz.
                            cozulmeyen.append(ham)
                            continue

                        satirlar.append(
                            tuple(kayit.get(a) for a in ALANLAR))
            except OSError as e:
                self._log(f"{ad} okunamadi: {e}", "hata")
                ozet["hata"] += 1
                self._deneme[ad] = self._deneme.get(ad, 0) + 1
                continue

            # Veritabanına yaz
            #
            # DAYANIKLILIK: toplu yazma TEK islemdir; bir satirin kisit
            # ihlali TUM dakikayi dusurur. `telemetri.oturum_id` ->
            # `dron_oturumlari.id` FK'si var ve aktarim dakika SONRA
            # yapildigi icin o arada oturum silinmis olabilir. Bu
            # durumda 60 ornek tek bozuk satir yuzunden karantinaya
            # giderdi. Bu yuzden toplu yazma basarisiz olursa once
            # KURTARMA denenir.
            if satirlar:
                yazildi, hata = self._yaz_dayanikli(yazici, satirlar)

                # v2.4.25: hata BOZULMA kaynaklıysa onarımı tetikle ve
                # aktarımı BİR KEZ yeniden dene. Onarım başarılı olursa
                # dosya bu turda aktarılır; aksi halde eski davranış
                # (dosya korunur, yeniden denenir) geçerli kalır.
                if hata is not None and self.onarim_kancasi is not None:
                    try:
                        if self.onarim_kancasi(hata):
                            yazildi, hata = self._yaz_dayanikli(
                                yazici, satirlar)
                            if hata is None:
                                self._log(
                                    f"{ad}: onarim sonrasi aktarim "
                                    "BASARILI")
                    except Exception as _eo:
                        self._log(f"Onarim kancasi hatasi: {_eo}", "uyari")

                if hata is not None:
                    # DOSYA SİLİNMEZ; sonraki turda yeniden denenir.
                    self._deneme[ad] = self._deneme.get(ad, 0) + 1
                    self.sayac["aktarim_hatasi"] += 1
                    ozet["hata"] += 1
                    kalan = MAKS_DENEME - self._deneme[ad]
                    if kalan <= 0:
                        self.sayac["karantina"] += 1
                        self._log(
                            f"{ad} {MAKS_DENEME} denemede aktarilamadi, "
                            f"karantinaya alindi (dosya korundu): {hata}",
                            "hata")
                    else:
                        self._log(
                            f"{ad} aktarilamadi ({hata}); dosya korundu, "
                            f"{kalan} deneme kaldi", "uyari")
                    continue
                if yazildi < len(satirlar):
                    atlanan = len(satirlar) - yazildi
                    self.sayac["kisit_atlanan"] += atlanan
                    ozet["kisit_atlanan"] = (
                        ozet.get("kisit_atlanan", 0) + atlanan)
                    self._log(
                        f"{ad}: {yazildi}/{len(satirlar)} ornek aktarildi, "
                        f"{atlanan} satir kisit ihlali nedeniyle atlandi "
                        f"(kalan veri KURTARILDI)", "uyari")
                satirlar = satirlar[:yazildi] if yazildi else []

            # Çözülemeyen satırları ayır
            if cozulmeyen:
                try:
                    with open(yol + COZULMEDI_UZANTI, "a",
                              encoding="utf-8") as cf:
                        for s in cozulmeyen:
                            cf.write(s + "\n")
                    self.sayac["cozulmedi"] += len(cozulmeyen)
                    ozet["cozulmedi"] += len(cozulmeyen)
                except OSError:
                    pass

            if bozuk:
                self.sayac["bozuk_satir"] += bozuk
                ozet["bozuk"] += bozuk

            # Başarılı: SİLMİYORUZ, işaretliyoruz
            #
            # ## v2.4.43 — İŞARETLEME BAŞARISIZSA AKTARIM SAYILMAZ
            #
            # Eskiden hata YALNIZCA loglanıyordu ve akış devam ediyordu:
            # `self._deneme.pop(ad)` deneme sayacını SIFIRLIYOR, dosya
            # `.jsonl` olarak kalıyordu. Sonuç: bir sonraki turda aynı
            # dosya yine "bekleyen" sayılıp aynı örnekler veritabanına
            # YİNEDEN yazılıyordu. `telemetri` tablosunda UNIQUE kısıt
            # OLMADIĞI için mükerrer satırlar sessizce birikiyordu ve
            # karantina mekanizması da devreye girmiyordu (sayanın her
            # turda sıfırlanması yüzünden).
            #
            # Artık işaretleme başarısız olursa örnekler "aktarıldı"
            # SAYILMAZ ve `continue` ile durulur. Deneme sayacı artar,
            # MAKS_DENEME sonrası dosya karantinaya alınır. Bu, aynı
            # verinin bir kez fazla yazılması riskini korur (bu tur
            # yazıldı ama işaretlenemedi) fakat SONSUZ tekrarı keser.
            try:
                os.replace(yol, yol + AKTARILDI_UZANTI)
            except OSError as e:
                self._deneme[ad] = self._deneme.get(ad, 0) + 1
                self.sayac["aktarim_hatasi"] += 1
                ozet["hata"] += 1
                kalan = MAKS_DENEME - self._deneme[ad]
                if kalan <= 0:
                    self.sayac["karantina"] += 1
                    self._log(
                        f"{ad} isaretlenemedi ve {MAKS_DENEME} denemede "
                        f"cozulemedi, karantinaya alindi (dosya korundu); "
                        f"tekrarli yazma DURDURULDU: {e}", "hata")
                else:
                    self._log(
                        f"{ad} isaretlenemedi ({e}); bu tur aktarim "
                        f"SAYILMADI, {kalan} deneme kaldi", "uyari")
                continue

            self._deneme.pop(ad, None)
            self.sayac["aktarilan"] += len(satirlar)
            ozet["dosya"] += 1
            ozet["satir"] += len(satirlar)
            self._defter_yaz(ad, len(satirlar), "aktarildi", 0, "", simdi)

        self._son_aktarim = simdi
        return ozet

    # ------------------------------------------------------------------
    def _yaz_dayanikli(self, yazici, satirlar):
        """Toplu yazar; kisit ihlalinde satir bazinda kurtarmaya gecer.

        Donus: `(yazilan_satir_sayisi, hata)`. `hata` None ise islem
        basarili sayilir (kismi yazma dahil).

        ## Neden gerekli

        `executemany` TEK islemdir. Tek bir satirin FK/NOT NULL ihlali
        tum grubu geri alir. Aktarim dakika SONRA yapildigi icin
        `oturum_id`nin isaret ettigi oturum bu arada silinmis olabilir;
        o zaman 60 gecerli ornek bir bozuk satir yuzunden kaybedilirdi.

        ## Strateji

        1. Once toplu yazmayi dene (hizli yol; normal durumda budur).
        2. Kisit hatasi alirsan satirlari TEK TEK yaz; yalnizca gercek
           suclu satirlar atlanir.
        3. Kisit disi hata (disk, kilit vb.) ise KURTARMA YAPMA;
           hatayi don ki dosya korunsun ve yeniden denensin.

        ## v2.4.43 — YAZICI DONUSU ARTIK ONEMSENMEZ

        `veritabani.telemetri_toplu_yaz` v2.4.43'ten beri `INSERT OR
        IGNORE` kullanir ve GERCEKTEN eklenen satir sayisini dondurur
        (`(dron_id, ts)` tekillemesi nedeniyle mukerrerler atlanir).

        Bu deger burada "yazilan satir" olarak KULLANILMAZ. Aksi halde
        atlanan mukerrerler `kisit_atlanan` sayacina yazilirdi ve
        `satirlar = satirlar[:yazildi]` ile sondaki gecerli satirlar
        yanlislikla kirpilirdi — oysa mukerrer atlama BASARILI bir
        sonuctur, veri kaybi degil: satir zaten veritabaninda.

        Bu yuzden istisna atilmadiysa TUM grup basarili sayilir.
        """
        import sqlite3 as _sq
        try:
            yazici(satirlar)
            return len(satirlar), None
        except Exception as e:
            # Yalnizca BUTUNLUK hatalarinda satir bazina in. Disk/kilit
            # hatasinda tek tek denemek anlamsizdir ve dosyanin yeniden
            # denenmesi gerekir.
            kisit = isinstance(e, _sq.IntegrityError)
            if not kisit:
                return 0, e

        # Satir bazinda kurtarma
        yazildi = 0
        son_hata = None
        for s in satirlar:
            try:
                yazici([s])
                yazildi += 1
            except _sq.IntegrityError:
                # Gercek suclu satir; atlanir (sayaci cagiran tutar).
                continue
            except Exception as e2:
                # Kisit disi hata: kurtarmayi BURADA kes, kalan
                # satirlar icin dosya korunsun.
                son_hata = e2
                break
        if yazildi == 0 and son_hata is not None:
            return 0, son_hata
        return yazildi, None

    # ------------------------------------------------------------------
    def temizle(self, simdi: Optional[float] = None) -> int:
        """Saklama süresi geçmiş `.aktarildi` dosyalarını siler."""
        if simdi is None:
            simdi = time.time()
        sinir = simdi - self.saklama_saat * 3600
        silinen = 0
        try:
            adlar = os.listdir(self.dizin)
        except OSError:
            return 0
        for ad in adlar:
            if not ad.endswith(AKTARILDI_UZANTI):
                continue
            yol = os.path.join(self.dizin, ad)
            try:
                if os.path.getmtime(yol) < sinir:
                    os.unlink(yol)
                    silinen += 1
            except OSError:
                pass
        self.sayac["silinen_dosya"] += silinen
        self._son_temizlik = simdi
        return silinen

    # ------------------------------------------------------------------
    def dongu_adimi(self, yazici, dron_id_cozucu=None,
                    simdi: Optional[float] = None,
                    aktarim_aralik: float = 60.0,
                    temizlik_aralik: float = 3600.0) -> Optional[Dict]:
        """Ana döngüden periyodik çağrılır; zamanı gelmişse aktarır."""
        if simdi is None:
            simdi = time.time()

        ozet = None
        if (simdi - self._son_aktarim) >= aktarim_aralik:
            ozet = self.aktar(yazici, dron_id_cozucu, simdi)
            if ozet and ozet["satir"]:
                self._log(f"{ozet['satir']} telemetri ornegi "
                          f"{ozet['dosya']} dosyadan aktarildi")
        if (simdi - self._son_temizlik) >= temizlik_aralik:
            self.temizle(simdi)
        return ozet

    # ------------------------------------------------------------------
    def durum(self) -> Dict[str, Any]:
        """Tanılama bilgisi."""
        try:
            adlar = os.listdir(self.dizin)
        except OSError:
            adlar = []
        return {
            "dizin": self.dizin,
            "acik_dosya": os.path.basename(self._dosya_yolu) or None,
            "bekleyen": len(self.bekleyen_dosyalar()),
            "aktarildi_dosya": sum(1 for a in adlar
                                   if a.endswith(AKTARILDI_UZANTI)),
            "karantina": sum(1 for a, n in self._deneme.items()
                             if n >= MAKS_DENEME),
            "sayac": dict(self.sayac),
        }

    def kapat(self) -> None:
        """Açık dosyayı kapatır (program kapanışında çağrılmalı)."""
        with self._kilit:
            self._dosya_kapat()
