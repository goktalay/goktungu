# -*- coding: utf-8 -*-
"""KOPRU YAZILIMI - VIDEO SERVISI.

## KULLANICI ISTEGI (birebir)

    "hem ai icin hem kameralar icin ayni kopru gruplamasi gerekiyor"

ve kusur bildirimi:

    "GCS icinde kopru kurulu olan makinede porta baglanmali, sanirim su
     an sunucu da ariyor portu"

## GOREVI

Kamera akislarini (RTSP / MJPEG / HTTP / USB) SAHADA yakalar, yerel bir
MJPEG vekili olarak sunar ve merkeze yalniz akis DURUMUNU bildirir.

## NEDEN MERKEZDE DEGIL KOPRUDE

Kamera saha agindadir (ornegin 192.168.1.50) ya da dogrudan USB ile saha
bilgisayarina takilidir. Merkez sunucu bir veri merkezindedir ve ne bu
ozel ag adresine ne de USB aygitina ULASABILIR.

Onceki surumde akis merkezde aciliyordu; bu yuzden YALNIZCA genel
internete acik kameralar calisiyordu. Kullanicinin ekledigi
`97.76.27.170` adresinin gelmesi tam olarak bu yuzdendi -- o adres genel
internetten erisilebilir. Saha agindaki bir kamera ya da cantaya takili
bir USB kamera ise hicbir zaman gelmedi.

## ONCEKI SURUMUN UC EKSIGI (v1.4.4 ve oncesi)

Bu servis onceden yalniz bir "canlilik" gostergesiydi:

1. **Akis acmiyordu.** Yalnizca `shutil.which("ffmpeg")` ile ffmpeg'in
   varligini denetleyip 30 saniyede bir "0 etkin akis" yaziyordu. Tek
   bir kare uretmiyordu.
2. **Cihaz taramasi yoktu.** USB kamera listesi merkezde taraniyordu;
   merkezde kamera aygiti olmadigi icin liste HER ZAMAN bos donuyordu.
3. **Komut kanalina bagli degildi.** Panelden gelen "akisi baslat"
   istegi bu servise HIC ulasmiyordu.

Bu surum ucunu birlikte giderir: gercek vekil (`video_vekil`) sahada
kosar, cihaz taramasi sahada yapilir, komutlar `ServisKanali` uzerinden
gelir.

## MERKEZE NE GONDERILIR: GORUNTU DEGIL, DURUM

Bu servis merkeze KARE GONDERMEZ. Radar izleri saniyede birkac kilobayt
tutar; video ise kamera basina megabit olceginde bir yuktur. Tum saha
kameralarinin karelerini merkeze pompalamak, merkez sunucunun bant
genisligini ve bellegini tuketir -- kullanicinin daha once yasadigi
cokme sinifina giren bir risktir.

Bunun yerine goruntu YEREL AGDA sunulur: arayuz kareleri kopru
makinesinin kendi vekilinden (`http://<kopru>:8801/kamera/<id>`) ceker,
merkez yalnizca "akis acik mi, kac izleyici var, son hata ne" bilgisini
alir. Boylece goruntu, izleyicisiyle ayni agda kalir.

## FFMPEG VE OPENCV DIS BAGIMLILIKTIR

Kullanici daha once "kamera ffmpeg yukleyince duzeldi" dedi; o teshis
saatler surmustu. Bu yuzden ikisinin de VARLIGI acilista denetlenir ve
eksikse KURULUM KOMUTU yazilir. Ayrim onemlidir:

  * `ffmpeg` yoksa RTSP/MJPEG/HTTP akislari calismaz.
  * `opencv` yoksa YALNIZCA USB/donanim kamera ve AI kutu cizimi
    calismaz; ag kameralari calismaya devam eder.

Sessizce basarisiz olmak kabul edilmez; eksiklik EKSIK YETENEK olarak
merkeze de bildirilir.
"""
import subprocess
import threading
import time

from . import arac_bul
from .servis_kanal import ServisKanali
from .servis_temel import Servis, calistir
from .video_vekil import VIDEO_PROXY_PORT, KameraDefteri, VideoProxy

DONGU_SN = 0.2              # komut yoklama araligi
DURUM_YAZIM_SN = 2.0        # merkeze durum yazim araligi
KONSOL_BILDIRIM_SN = 30.0   # konsola ozet yazim araligi


class VideoServisi(Servis):
    ad = "video"
    baslik = "Video Servisi"

    # -----------------------------------------------------------------
    def hazirla(self):
        self.kanal = ServisKanali()
        self.defter = KameraDefteri()
        # v2.1.0: arama artik PATH ile SINIRLI DEGIL. Kullanici
        # Windows'ta ffmpeg'i kurmus olmasina ragmen "BULUNAMADI"
        # uyarisi aliyordu: kopru LocalSystem hesabiyla servis olarak
        # kosar ve winget'in kullanici profiline kurdugu dizin o
        # hesabin PATH'inde YOKTUR. Ayrinti: arac_bul modulu.
        self._tani = arac_bul.tani()
        self.ffmpeg = self._tani["ffmpeg_yolu"] or None
        self.opencv = self._tani["opencv"]

        if self.ffmpeg:
            _s = self._tani["ffmpeg_surum"]
            self.yaz("ffmpeg bulundu: %s%s"
                     % (self.ffmpeg, f" ({_s})" if _s else ""), "basari")
        else:
            self.yaz("ffmpeg BULUNAMADI - RTSP/MJPEG/HTTP akislari "
                     "calismayacak.", "uyari")
            self._yonerge_yaz("ffmpeg")

        if self.opencv:
            _os = self._tani["opencv_surum"]
            self.yaz("OpenCV bulundu%s - USB kamera ve AI kutu cizimi "
                     "kullanilabilir"
                     % (f" ({_os})" if _os else ""), "basari")
        else:
            # HATA DEGIL, EKSIK YETENEK: ag kameralari calismaya devam
            # eder. Kullaniciya net ayrim verilmezse "video hic
            # calismiyor" sanilir ve gereksiz teshis yapilir.
            self.yaz("OpenCV yok - ag kameralari calisir, USB kamera ve "
                     "AI kutu cizimi devre disi", "uyari")
            if self._tani["opencv_sebep"] == "yuklenemedi":
                # Kurulu ama import patliyor: "kur" demek yanlis olur;
                # onarim gerekir, kurulum degil.
                self.yaz("OpenCV kurulu ama YUKLENEMIYOR (eksik sistem "
                         "kutuphanesi olabilir). Python: %s"
                         % self._tani["python"], "uyari")
            else:
                self._yonerge_yaz("opencv")

        self.vekil = VideoProxy(kameralar=self.defter,
                                konsol=lambda s: self.yaz(str(s)),
                                port=VIDEO_PROXY_PORT)
        self._vekil_hata = ""
        self._vekil_hazir = False
        threading.Thread(target=self._vekil_kos, daemon=True).start()

        self._son_durum = 0.0
        self._son_konsol = 0.0

    def _yonerge_yaz(self, arac):
        """Konsola ADIM ADIM, kopyalanabilir kurulum yonergesi yazar.

        NEDEN: kullanici hakli olarak sunu belirtti -- konumlari taramak
        tek basina yetmez; arac hic yoksa ya da yalnizca kullanici
        profilinde varsa, "servisin gordugu yere" nasil kurulacagini
        BILMESI gerekir. Genel bir `pip install` / `winget install`
        satiri bu durumda ise yaramaz ve teshis dongusu basa doner.

        Yonerge surecin kendi ortamini kullanir (servisin Python yolu,
        makine kapsamli kurulum, servis yeniden baslatma komutu).
        """
        self.yaz("--- KURULUM YARDIMI (%s) ---" % arac.upper(), "uyari")
        for satir in arac_bul.kurulum_yonergesi(arac):
            # Bos satir da yazilir: cok satirli yonergede gruplari
            # ayirir, okunurlugu belirgin olcude artirir.
            self.yaz(satir, "uyari")
        self.yaz("--- YARDIM SONU ---", "uyari")

    def _vekil_kos(self):
        """MJPEG vekilini ayri is parcaciginda kosar.

        `calistir()` bloklar (serve_forever). Ana donguyu bloklamamasi
        icin ayri parcacikta kosar; port cakismasi gibi hatalar
        yakalanip merkeze bildirilir -- aksi halde servis sessizce
        goruntu vermeyen bir durumda kalir ve operator kamerayi arizali
        sanir.
        """
        try:
            self._vekil_hazir = True
            self.vekil.calistir()
        except Exception as e:
            self._vekil_hazir = False
            self._vekil_hata = str(e)
            self.yaz("Video vekili baslatilamadi (port %d): %s"
                     % (VIDEO_PROXY_PORT, e), "hata")

    # -----------------------------------------------------------------
    # Ana dongu
    # -----------------------------------------------------------------
    def dongu(self):
        self.yaz("Video servisi hazir. Akislar BU makinede acilir; "
                 "kamera tanimlari merkezden gelir.", "basari")
        while not self.durdur_istendi():
            self._komutlari_isle()
            self._merkeze_yaz()
            self._konsol_ozet()
            self.bekle(DONGU_SN)

    def _komutlari_isle(self):
        if not self.kanal.etkin():
            return
        for k in self.kanal.oku():
            kid = k.get("id")
            eylem = str(k.get("eylem") or "")
            veri = k.get("veri") if isinstance(k.get("veri"), dict) else {}
            try:
                sonuc = self._komut_uygula(eylem, veri)
                self.kanal.yanit(kid, True, "", sonuc)
            except Exception as e:
                self.yaz("Komut hatasi (%s): %s" % (eylem, e), "hata")
                self.kanal.yanit(kid, False, str(e))

    def _komut_uygula(self, eylem, veri):
        # --- cihaz taramasi -------------------------------------------
        if eylem == "cihazlar":
            if not self.opencv:
                # Bos liste ile "kamera yok" demek YANILTICIDIR: kamera
                # takili olabilir, eksik olan OpenCV'dir. Gerekce
                # dondurulur ki panel dogru metni gosterebilsin.
                return {"cihazlar": [], "opencv": False,
                        "gerekce": "OpenCV kurulu degil "
                                   "(pip install opencv-python-headless)"}
            try:
                en_fazla = int(veri.get("en_fazla") or 6)
            except (TypeError, ValueError):
                en_fazla = 6
            cihazlar = VideoProxy.cihaz_listesi(en_fazla)
            self.yaz("Cihaz taramasi: %d yerel kamera bulundu"
                     % len(cihazlar))
            return {"cihazlar": cihazlar, "opencv": True, "gerekce": ""}

        # --- kamera kaydi ---------------------------------------------
        if eylem == "kamera_yaz":
            kayit = veri.get("kamera") if isinstance(
                veri.get("kamera"), dict) else veri
            k = self.defter.yaz(kayit)
            if not k:
                raise ValueError("gecersiz kamera kaydi")
            self.yaz("Kamera kaydi guncellendi: #%s %s (%s)"
                     % (k["id"], k["isim"] or "-", k["protokol"]))
            return {"kamera": k}

        if eylem == "kamera_sil":
            kid = veri.get("id")
            if kid is not None:
                try:
                    self.vekil.yayin_durdur(int(kid))
                except (TypeError, ValueError):
                    pass
            var = self.defter.sil(kid)
            return {"silindi": bool(var)}

        # --- akis yonetimi --------------------------------------------
        if eylem == "akis_baslat":
            kayit = veri.get("kamera")
            if isinstance(kayit, dict):
                self.defter.yaz(kayit)
            kid = veri.get("id", (kayit or {}).get("id"))
            if kid is None:
                raise ValueError("kamera id gerekli")
            kid = int(kid)
            y = self.vekil.yayin_al(kid)
            if y is None:
                gerekce = self.vekil.son_hata(kid) or "kaynak acilamadi"
                # Kural: basarisizlik SESSIZ kalmaz. Gerekce hem konsola
                # hem panele gider; kullanici "neden gelmiyor" diye
                # tahmin yurutmek zorunda kalmaz.
                self.yaz("Kamera %d akisi acilamadi: %s" % (kid, gerekce),
                         "hata")
                return {"acildi": False, "gerekce": gerekce, "id": kid}
            try:
                bekle = float(veri.get("bekle") or 12.0)
            except (TypeError, ValueError):
                bekle = 12.0
            if not y.ilk_kare_bekle(bekle):
                gerekce = y.hata or "kaynak kare uretmedi (zaman asimi)"
                self.yaz("Kamera %d kare uretmedi: %s" % (kid, gerekce),
                         "uyari")
                return {"acildi": False, "gerekce": gerekce, "id": kid}
            self.yaz("Kamera %d akisi acildi" % kid, "basari")
            return {"acildi": True, "gerekce": "", "id": kid,
                    "yol": "/kamera/%d" % kid, "port": VIDEO_PROXY_PORT}

        if eylem == "akis_durdur":
            kid = veri.get("id")
            if kid is None:
                raise ValueError("kamera id gerekli")
            self.vekil.yayin_durdur(int(kid))
            self.yaz("Kamera %s akisi durduruldu" % kid)
            return {"durduruldu": True, "id": int(kid)}

        if eylem == "durum":
            return self._durum_paketi()

        # --- AI tespit kutulari ---------------------------------------
        if eylem == "anotasyon":
            kid = veri.get("id")
            if kid is None:
                raise ValueError("kamera id gerekli")
            self.vekil.anotasyon.guncelle(int(kid),
                                          veri.get("kutular") or [])
            return {}

        raise ValueError("bilinmeyen eylem: %s" % eylem)

    # -----------------------------------------------------------------
    # Merkeze bildirim
    # -----------------------------------------------------------------
    def _durum_paketi(self):
        """Merkeze gidecek akis durumu.

        ## KARE GONDERILMEZ, DURUM GONDERILIR

        Bilerek yalnizca ozet gonderilir (bkz. modul basligi): goruntu
        yerel agda kalir, merkez akisin acik olup olmadigini bilir.

        ## SOZLUK NEDEN KILIT ALTINDA KOPYALANIR

        `yayinlar` ve `_son_hatalar` sozlukleri HTTP is parcaciklari
        tarafindan degistirilir. Kopyalanmadan gezilirse Python
        "dictionary changed size during iteration" hatasi verir; bu hata
        durum yaziminin ortasinda olusur ve merkez o dongude HIC durum
        almaz. Kopya alinarak gezinti kilitten bagimsiz yapilir.
        """
        with self.vekil._kilit:
            yayinlar = list(self.vekil.yayinlar.items())
            hatalar = dict(self.vekil._son_hatalar)
        akislar = []
        etkin = 0
        for kid, y in yayinlar:
            calisiyor = bool(y.calisiyor)
            if calisiyor:
                etkin += 1
            akislar.append({
                "id": int(kid),
                "calisiyor": calisiyor,
                "izleyici": int(y.izleyiciler),
                "kare_no": int(y.kare_no),
                "protokol": y.protokol,
                "hata": (y.hata or "")[:200],
            })
        return {
            "video_akislar": akislar,
            "video_etkin": etkin,
            "video_hatalar": {str(k): v for k, v in hatalar.items()},
            "video_port": VIDEO_PROXY_PORT,
            "video_hazir": bool(self._vekil_hazir),
            "video_vekil_hata": self._vekil_hata,
            "ffmpeg": bool(self.ffmpeg),
            "opencv": bool(self.opencv),
            "kameralar": self.defter.listele(),
        }

    def _merkeze_yaz(self):
        simdi = time.time()
        if simdi - self._son_durum < DURUM_YAZIM_SN:
            return
        self._son_durum = simdi
        self.durum_yaz(**self._durum_paketi())

    def _konsol_ozet(self):
        simdi = time.time()
        if simdi - self._son_konsol < KONSOL_BILDIRIM_SN:
            return
        self._son_konsol = simdi
        p = self._durum_paketi()
        self.yaz("Durum: %d etkin akis, vekil portu %d, ffmpeg %s, "
                 "opencv %s"
                 % (p["video_etkin"], VIDEO_PROXY_PORT,
                    "var" if self.ffmpeg else "YOK",
                    "var" if self.opencv else "YOK"))

    # -----------------------------------------------------------------
    def kapat(self):
        try:
            self.vekil.hepsini_durdur()
        except Exception:
            pass
        # Servis durdugunda merkez akisi "acik" gormeye devam etmemeli:
        # aksi halde arayuz olmayan bir yayini beklemeye devam eder ve
        # operator siyah kutuya bakip kamerayi arizali sanir.
        try:
            self.durum_yaz(video_akislar=[], video_etkin=0,
                           video_hazir=False, video_hatalar={},
                           kameralar=[])
        except Exception:
            pass
        self.yaz("Kamera akislari kapatildi")


if __name__ == "__main__":
    calistir(VideoServisi)
