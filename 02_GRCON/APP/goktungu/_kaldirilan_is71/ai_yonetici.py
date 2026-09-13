# -*- coding: utf-8 -*-
"""AI islem sunuculari yoneticisi (v2.4.0).

Gorevleri:
- ai_sunucular tablosu CRUD (NVIDIA/CPU isciler)
- Iscilerin saglik yoklamasi (5 sn'de bir GET /durum)
- Kamera izleme gorevlerinin en az yuklu isciye dagitimi
- Isci dusunce gorevlerin saglikli iscilere yeniden dagitimi
- Isciden gelen tespitlerin (yuz/plaka) kisi/arac kutuphanesi ile
  eslestirilmesi (SFace cosine benzerlik, esik 0.363) ve ai_tespitler
  tablosuna kaydi
- Izleme gorevlerinin kaliciligi (ayarlar): arayuz kapansa da isciler
  bagimsiz surec olarak calismaya devam eder; ana sunucu yeniden
  baslarsa gorevler otomatik geri yuklenir
"""
import base64
import json
import threading
import time
import urllib.request

import numpy as np

from . import veritabani

SFACE_ESIK = 0.363          # OpenCV SFace standart cosine esigi
YOKLAMA_ARALIGI = 5.0       # saniye


class AIYonetici:
    def __init__(self, konsol, ayarlar, duyuru_cb=None):
        self.konsol = konsol
        self.ayarlar = ayarlar
        # WS yayin koprusu: dict alir, tum istemcilere gonderir
        self.duyuru_cb = duyuru_cb
        self.kilit = threading.Lock()
        # sunucu_id -> {son_durum, son_yoklama_ts, cevrimici}
        self.saglik = {}
        # v2.4.8: acilis taramasi icin kamera yonetici referansi
        # (main.py'de baglanir)
        self.kameralar = None
        # kamera_id -> sunucu_id (aktif izleme gorevleri)
        self.gorevler = {}
        # v2.4.2: kamera_id -> aktif hedef takibi (tracking) durumu
        self.takipler = {}
        # v2.4.7: anotasyonlu MJPEG icin video proxy referansi
        # (main.py baglar)
        self.video_proxy = None
        self._calisiyor = True
        self._yuz_onbellek = None      # [(kisi_id, np.array), ...]
        self._yuz_onbellek_ts = 0.0
        self._plaka_onbellek = None    # {plaka_norm: arac_id}
        self._plaka_onbellek_ts = 0.0

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # v2.4.56: firma izolasyonu + kopru gruplamasi
    # ------------------------------------------------------------------
    # Merkezde (/app/) tek surece birden fazla firmanin pilotu baglanir.
    # `firma_id` verilirse liste O firmaya ait kayitlarla (ve firmasiz
    # eski kayitlarla) sinirlanir. `None` verilirse suzgec UYGULANMAZ —
    # lokal kurulum ve ic cagrilar (saglik yoklamasi, gorev dagitimi)
    # tum kayitlari gormeye devam eder; davranis birebir korunur.
    @staticmethod
    def _firma_suzgeci(firma_id):
        """(WHERE parcasi, parametreler) ikilisi dondurur."""
        if not firma_id:
            return "", ()
        return " WHERE (firma_id = ? OR firma_id IS NULL)", (int(firma_id),)

    def listele(self, firma_id=None):
        kosul, par = self._firma_suzgeci(firma_id)
        with veritabani.baglanti() as con:
            rows = con.execute(
                "SELECT * FROM ai_sunucular" + kosul + " ORDER BY id",
                par).fetchall()
        liste = []
        for r in rows:
            d = dict(r)
            s = self.saglik.get(d["id"], {})
            d["cevrimici"] = bool(s.get("cevrimici"))
            durum = s.get("son_durum") or {}
            d["yuk"] = durum.get("yuk", 0)
            d["kapasite_canli"] = durum.get("kapasite", d.get("kapasite"))
            d["akislar"] = durum.get("akislar", [])
            # v2.4.45: SSH sifresi arayuze ASLA gonderilmez; yalniz
            # "kayitli mi" bilgisi tasinir. Boylece duzenleme ekrani
            # sifreyi bos gosterir ama kullanici sifrenin durdugunu bilir.
            d["ssh_sifre_var"] = bool((d.get("ssh_sifre") or "").strip())
            d.pop("ssh_sifre", None)
            liste.append(d)
        return liste

    def kaydet(self, sid, ad, tip, host, port, kapasite, notlar="",
               ssh=None, firma_id=None, kopru_ornek_id=None):
        """AI bilgisayarini kaydeder/gunceller.

        v2.4.45: `ssh` sozlugu verilirse SSH alanlari da yazilir:
        {kullanici, port, anahtar, komut, sifre}. `None` verilirse SSH
        alanlari DOKUNULMAZ (eski istemciler bu alani gondermez;
        gondermeyen bir istemci var olan SSH ayarini silmemelidir).

        v2.4.56: `firma_id` yeni kayitta yazilir (var olan kaydin
        firmasi DEGISTIRILMEZ; sahiplik devri ayri bir istir).
        `kopru_ornek_id` AI bilgisayarinin hangi kopru makinesinde
        oldugunu belirtir; None ise "kopruye bagli degil" demektir ve
        merkez onu dogrudan yoklar (lokal kurulum davranisi).
        """
        ad = (ad or "").strip()[:80]
        host = (host or "").strip()[:120]
        tip = tip if tip in ("cpu", "nvidia") else "cpu"
        try:
            port = int(port)
            kapasite = max(1, min(64, int(kapasite)))
        except (TypeError, ValueError):
            return None
        if not ad or not host:
            return None

        s_alan = None
        if isinstance(ssh, dict):
            try:
                sport = int(ssh.get("port") or 22)
            except (TypeError, ValueError):
                sport = 22
            sport = max(1, min(65535, sport))
            s_alan = (
                (ssh.get("kullanici") or "").strip()[:64],
                sport,
                (ssh.get("anahtar") or "").strip()[:400],
                (ssh.get("komut") or "").strip()[:500],
                (ssh.get("sifre") or "")[:200],
            )

        try:
            kopru = int(kopru_ornek_id) if kopru_ornek_id else None
        except (TypeError, ValueError):
            kopru = None

        with veritabani.baglanti() as con:
            if sid:
                # Guncellemede `kopru_ornek_id` HER ZAMAN yazilir (None
                # dahil): kullanici bir AI bilgisayarini kopruden
                # ayirmak isteyebilir. `firma_id` ise DOKUNULMAZ.
                if s_alan is None:
                    con.execute(
                        "UPDATE ai_sunucular SET ad=?, tip=?, host=?, port=?,"
                        " kapasite=?, notlar=?, kopru_ornek_id=? WHERE id=?",
                        (ad, tip, host, port, kapasite, notlar or "",
                         kopru, int(sid)))
                else:
                    con.execute(
                        "UPDATE ai_sunucular SET ad=?, tip=?, host=?, port=?,"
                        " kapasite=?, notlar=?, ssh_kullanici=?, ssh_port=?,"
                        " ssh_anahtar=?, ssh_komut=?, ssh_sifre=?,"
                        " kopru_ornek_id=?"
                        " WHERE id=?",
                        (ad, tip, host, port, kapasite, notlar or "")
                        + s_alan + (kopru, int(sid)))
            else:
                fid = int(firma_id) if firma_id else None
                # --- IS68K2_AI_TEKILLIK_v1 ---
                # OLCULEN KUSUR: ayni AI bilgisayari iki kez
                # kaydedilebiliyordu (id=5 "PC" ve id=6 "CPU": ayni
                # host/port/kopru). `_en_az_yuklu()` bunlari AYRI isci
                # sanip kapasiteleri topluyor (2+4=6) ve tek surece
                # alti gorev gonderiyordu.
                #
                # Ayni (host, port, kopru_ornek_id, firma_id) dortlusune
                # sahip AKTIF kayit varsa yeni satir acilmaz; var olan
                # guncellenir. Reddetmek yerine guncellemek, kullanicinin
                # "bu makineyi tanit" niyetini karsilar.
                #
                # NULL karsilastirmasi acikca yapilir: SQL'de NULL=NULL
                # yanlistir, bu yuzden IS NOT DISTINCT FROM esdegeri
                # olarak Python tarafinda esleme yapilir.
                _mevcut = None
                try:
                    for _r in con.execute(
                            "SELECT id, kopru_ornek_id, firma_id"
                            "  FROM ai_sunucular"
                            " WHERE host=? AND port=? AND aktif=1",
                            (host, port)).fetchall():
                        _d = dict(_r)
                        if (_d.get("kopru_ornek_id") == kopru
                                and _d.get("firma_id") == fid):
                            _mevcut = int(_d["id"])
                            break
                except BaseException:
                    _mevcut = None
                if _mevcut:
                    if s_alan is None:
                        con.execute(
                            "UPDATE ai_sunucular SET ad=?, tip=?,"
                            " kapasite=?, notlar=? WHERE id=?",
                            (ad, tip, kapasite, notlar or "", _mevcut))
                    else:
                        con.execute(
                            "UPDATE ai_sunucular SET ad=?, tip=?,"
                            " kapasite=?, notlar=?, ssh_kullanici=?,"
                            " ssh_port=?, ssh_anahtar=?, ssh_komut=?,"
                            " ssh_sifre=? WHERE id=?",
                            (ad, tip, kapasite, notlar or "")
                            + s_alan + (_mevcut,))
                    return self.listele(firma_id)
                # --- /IS68K2_AI_TEKILLIK_v1 ---
                if s_alan is None:
                    con.execute(
                        "INSERT INTO ai_sunucular"
                        " (ad, tip, host, port, kapasite, notlar, aktif,"
                        "  firma_id, kopru_ornek_id)"
                        " VALUES (?,?,?,?,?,?,1,?,?)",
                        (ad, tip, host, port, kapasite, notlar or "",
                         fid, kopru))
                else:
                    con.execute(
                        "INSERT INTO ai_sunucular"
                        " (ad, tip, host, port, kapasite, notlar, aktif,"
                        "  ssh_kullanici, ssh_port, ssh_anahtar, ssh_komut,"
                        "  ssh_sifre, firma_id, kopru_ornek_id)"
                        " VALUES (?,?,?,?,?,?,1,?,?,?,?,?,?,?)",
                        (ad, tip, host, port, kapasite, notlar or "")
                        + s_alan + (fid, kopru))
        return self.listele(firma_id)

    def sahibi_mi(self, sid, firma_id) -> bool:
        """Kayit bu firmaya mi ait (veya firmasiz eski kayit mi).

        `firma_id` bos ise (lokal kurulum) her zaman True doner.
        """
        if not firma_id:
            return True
        with veritabani.baglanti() as con:
            r = con.execute(
                "SELECT firma_id FROM ai_sunucular WHERE id=?",
                (int(sid),)).fetchone()
        if not r:
            return False
        mevcut = dict(r).get("firma_id")
        return mevcut is None or int(mevcut) == int(firma_id)

    def sil(self, sid, firma_id=None):
        sid = int(sid)
        if not self.sahibi_mi(sid, firma_id):
            return None
        # bu iscideki gorevleri baska iscilere tasi
        # IS 59: Merkez kipinde bu govde `AiVekili` uzerinden odunc
        # calisir ve orada `gorevler` bir LISTEDIR (sahadan gelen
        # gorev ozeti), sozluk degil. `.items()` cagrisi cokerdi.
        # Merkez kipinde gorevler zaten SAHADA kosar; merkezin
        # tasiyacagi bir gorev yoktur, adim atlanir.
        _gorev_haritasi_mi = isinstance(
            getattr(self, "gorevler", None), dict)
        if _gorev_haritasi_mi:
            with self.kilit:
                tasinacak = [k for k, s in self.gorevler.items()
                             if s == sid]
        else:
            tasinacak = []
        for kamera_id in tasinacak:
            self.izleme_durdur(kamera_id, kalici=False)
        with veritabani.baglanti() as con:
            con.execute("DELETE FROM ai_sunucular WHERE id=?", (sid,))
        self.saglik.pop(sid, None)
        return self.listele(firma_id)

    # ------------------------------------------------------------------
    # Isci HTTP yardimcilari
    # ------------------------------------------------------------------
    def _sunucu_kaydi(self, sid):
        with veritabani.baglanti() as con:
            r = con.execute("SELECT * FROM ai_sunucular WHERE id=?",
                            (int(sid),)).fetchone()
        return dict(r) if r else None

    def _http(self, kayit, yol, veri=None, zamanasimi=6):
        url = f"http://{kayit['host']}:{kayit['port']}{yol}"
        if veri is None:
            istek = urllib.request.Request(url)
        else:
            istek = urllib.request.Request(
                url, data=json.dumps(veri).encode(),
                headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(istek, timeout=zamanasimi) as c:
            return json.loads(c.read() or b"{}")

    # ------------------------------------------------------------------
    # Saglik yoklama + gorev dagitimi
    # ------------------------------------------------------------------
    def baslat(self):
        threading.Thread(target=self._yoklama_dongusu, daemon=True,
                         name="ai-yoklama").start()
        # kalici gorevleri geri yukle
        threading.Thread(target=self._gorevleri_geri_yukle, daemon=True,
                         name="ai-gorev-yukle").start()

    def durdur(self):
        self._calisiyor = False

    def _yoklama_dongusu(self):
        while self._calisiyor:
            try:
                self._yokla()
            except Exception as e:
                self.konsol("AI", f"Yoklama hatasi: {e}", "hata")
            time.sleep(YOKLAMA_ARALIGI)

    def _yokla(self):
        degisti = False
        onceki_ozet = self._akis_ozet()
        for kayit in self.listele():
            sid = kayit["id"]
            onceki = self.saglik.get(sid, {}).get("cevrimici")
            try:
                durum = self._http(kayit, "/durum", zamanasimi=4)
                self.saglik[sid] = {"cevrimici": True,
                                    "son_durum": durum,
                                    "son_yoklama_ts": time.time()}
                if onceki is False or onceki is None:
                    degisti = True
                    if onceki is False:
                        self.konsol("AI", f"AI sunucusu tekrar cevrimici:"
                                    f" {kayit['ad']}", "basari")
            except Exception:
                self.saglik[sid] = {"cevrimici": False,
                                    "son_durum": None,
                                    "son_yoklama_ts": time.time()}
                if onceki:
                    degisti = True
                    self.konsol("AI", f"AI sunucusu yanit vermiyor:"
                                f" {kayit['ad']}", "uyari")
                    self._gorevleri_yeniden_dagit(sid)
        if degisti and self.duyuru_cb:
            self.duyuru_cb({"tip": "ai_sunucu_listesi",
                            "sunucular": self.listele()})
        # v2.4.9: akis canli/hata durumu degistiyse izleme listesini
        # arayuze duyur (LED gostergesinin guncel kalmasi icin)
        if self.duyuru_cb and (degisti
                               or self._akis_ozet() != onceki_ozet):
            self.duyuru_cb({"tip": "ai_izleme_listesi",
                            "izlemeler": self.izleme_listesi()})

    def _akis_ozet(self):
        """v2.4.9: Iscilerin akis durumu ozeti (degisim tespiti)."""
        ozet = set()
        for sid, s in list(self.saglik.items()):
            for a in ((s.get("son_durum") or {}).get("akislar") or []):
                ozet.add((sid, a.get("kamera_id"),
                          bool(a.get("canli")),
                          str(a.get("hata") or "")))
        return ozet

    def _en_az_yuklu(self, haric=None):
        """Cevrimici, kapasitesi dolu olmayan en az yuklu isci kaydi."""
        aday, aday_yuk = None, 10 ** 9
        for kayit in self.listele():
            if haric and kayit["id"] == haric:
                continue
            s = self.saglik.get(kayit["id"], {})
            if not s.get("cevrimici"):
                continue
            durum = s.get("son_durum") or {}
            yuk = durum.get("yuk", 0)
            kapasite = durum.get("kapasite", kayit.get("kapasite", 1))
            if yuk >= kapasite:
                continue
            if yuk < aday_yuk:
                aday, aday_yuk = kayit, yuk
        return aday

    def _gorevleri_yeniden_dagit(self, dusen_sid):
        with self.kilit:
            tasinacak = [k for k, s in self.gorevler.items()
                         if s == dusen_sid]
        for kamera_id in tasinacak:
            bilgi = self._gorev_bilgisi(kamera_id)
            if not bilgi:
                continue
            self.konsol("AI", f"Kamera #{kamera_id} gorevi yeniden"
                        f" dagitiliyor...", "uyari")
            self._gorev_ata(kamera_id, bilgi["url"], bilgi["protokol"],
                            haric=dusen_sid)

    # ------------------------------------------------------------------
    # Izleme gorevleri (kalici)
    # ------------------------------------------------------------------
    def _kalici_gorevler(self):
        return self.ayarlar.yukle().get("ai_izleme", {})

    def _kalici_kaydet(self, gorevler):
        self.ayarlar.kaydet({"ai_izleme": gorevler})

    def _gorev_bilgisi(self, kamera_id):
        return self._kalici_gorevler().get(str(kamera_id))

    def _gorevleri_geri_yukle(self):
        time.sleep(8)   # iscilerin ayaga kalkmasini bekle
        gorevler = dict(self._kalici_gorevler())
        # v2.4.8: kalici gorev kaydi olmayan ama ai_gorevler'i dolu
        # kameralar da otomatik izlemeye alinir (kamera daha once
        # kaydedilmis, izleme hic baslatilmamis olabilir).
        if self.kameralar is not None:
            try:
                for kam in self.kameralar.listele():
                    kid = str(kam.get("id"))
                    if kid in gorevler:
                        # gorev listesi guncel olsun (kamera duzenlendiyse)
                        gorevler[kid]["gorevler"] = (
                            kam.get("ai_gorevler") or "")
                        continue
                    if (kam.get("ai_gorevler") or "").strip():
                        gorevler[kid] = {
                            "url": "/kamera/%s" % kam["id"],
                            "protokol": "gcs_proxy",
                            "gorevler": kam["ai_gorevler"]}
                        self.konsol("AI", f"Kamera #{kam['id']} AI"
                                    " gorevleri secili; izleme otomatik"
                                    " baslatiliyor", "bilgi")
            except Exception as e:
                self.konsol("AI", f"Acilis kamera taramasi: {e}",
                            "uyari")
            self._kalici_kaydet(gorevler)
        for kamera_id, bilgi in gorevler.items():
            try:
                self._gorev_ata(int(kamera_id), bilgi["url"],
                                bilgi["protokol"],
                                gorevler=bilgi.get("gorevler", ""))
            except Exception as e:
                self.konsol("AI", f"Gorev geri yuklenemedi"
                            f" (kamera #{kamera_id}): {e}", "uyari")

    def _gorev_ata(self, kamera_id, url, protokol, haric=None,
                   gorevler=""):
        kayit = self._en_az_yuklu(haric=haric)
        if not kayit:
            return {"tamam": False,
                    "hata": "Uygun (cevrimici/bos) AI sunucusu yok"}
        try:
            sonuc = self._http(kayit, "/izle",
                               {"kamera_id": kamera_id, "url": url,
                                "protokol": protokol,
                                "gorevler": gorevler or ""})
        except Exception as e:
            return {"tamam": False, "hata": f"{kayit['ad']}: {e}"}
        if sonuc.get("tamam"):
            with self.kilit:
                self.gorevler[int(kamera_id)] = kayit["id"]
            self.konsol("AI", f"Kamera #{kamera_id} izlemesi"
                        f" {kayit['ad']} sunucusuna atandi", "basari")
        return sonuc

    def izleme_baslat(self, kamera_id, url, protokol, gorevler=""):
        kamera_id = int(kamera_id)
        sonuc = self._gorev_ata(kamera_id, url, protokol,
                                gorevler=gorevler)
        if sonuc.get("tamam"):
            kalici = self._kalici_gorevler()
            kalici[str(kamera_id)] = {"url": url, "protokol": protokol,
                                      "gorevler": gorevler or ""}
            self._kalici_kaydet(kalici)
        return sonuc

    def izleme_durdur(self, kamera_id, kalici=True):
        kamera_id = int(kamera_id)
        with self.kilit:
            sid = self.gorevler.pop(kamera_id, None)
        if sid:
            kayit = self._sunucu_kaydi(sid)
            if kayit:
                try:
                    self._http(kayit, "/durdur", {"kamera_id": kamera_id})
                except Exception:
                    pass
        if kalici:
            gorevler = self._kalici_gorevler()
            gorevler.pop(str(kamera_id), None)
            self._kalici_kaydet(gorevler)
        return {"tamam": True}

    def izleme_listesi(self):
        kalici = self._kalici_gorevler()
        with self.kilit:
            atamalar = dict(self.gorevler)
        # v2.4.9: iscinin /durum yanitindaki akis canli/hata bilgisini
        # izleme kaydina isle (arayuzde gorunur olsun)
        akis_durum = {}
        for sid, s in list(self.saglik.items()):
            for a in ((s.get("son_durum") or {}).get("akislar") or []):
                try:
                    akis_durum[int(a.get("kamera_id"))] = a
                except (TypeError, ValueError):
                    continue
        sonuc = []
        for k, v in kalici.items():
            kid = int(k)
            a = akis_durum.get(kid, {})
            sonuc.append({"kamera_id": kid,
                          "sunucu_id": atamalar.get(kid),
                          "url": v.get("url", ""),
                          "protokol": v.get("protokol", ""),
                          "canli": bool(a.get("canli")),
                          "hata": str(a.get("hata") or "")[:200]})
        return sonuc

    # ------------------------------------------------------------------
    # Embedding hesaplama (kutuphane yuz kaydi icin isciye devret)
    # ------------------------------------------------------------------
    def embed_hesapla(self, foto_b64):
        """v2.4.6: Yuz destegi olan TUM cevrimici iscileri yukune gore
        sirayla dener. Tek iscide 'modeller yuklu degil' donerse diger
        iscilere gecer; hicbirinde yoksa anlasilir hata dondurur."""
        adaylar = []
        for kayit in self.listele():
            s = self.saglik.get(kayit["id"], {})
            if not s.get("cevrimici"):
                continue
            durum = s.get("son_durum") or {}
            # /durum yaniti yuz_destegi bildiriyorsa ve False ise atla
            if durum.get("yuz_destegi") is False:
                continue
            adaylar.append((durum.get("yuk", 0), kayit))
        if not adaylar:
            return {"tamam": False,
                    "hata": "Yuz modelleri yuklu cevrimici AI sunucusu yok."
                            " AI > Sunucular'dan iscilerin calistigini ve"
                            " ai_modeller klasorunun dolu oldugunu kontrol"
                            " edin (bkz. AI_SUNUCU_KURULUM.md)."}
        adaylar.sort(key=lambda x: x[0])
        son_hata = ""
        for _, kayit in adaylar:
            try:
                sonuc = self._http(kayit, "/embed", {"foto_b64": foto_b64},
                                   zamanasimi=20)
            except Exception as e:
                son_hata = str(e)[:200]
                continue
            hata = (sonuc or {}).get("hata", "")
            if hata == "modeller yuklu degil":
                # bu iscide yuz modeli yok -> siradakini dene
                son_hata = (f"'{kayit['ad']}' iscisinde yuz modelleri"
                            " yuklu degil")
                continue
            return sonuc
        return {"tamam": False,
                "hata": (son_hata or "AI iscilerine ulasilamadi") +
                        " — ai_sunucu.py loglarini kontrol edin;"
                        " modeller ai_modeller/ klasorune otomatik"
                        " indirilemediyse AI_SUNUCU_KURULUM.md'deki"
                        " baglantilardan elle indirin.",
                "modeller_eksik": True}

    # ------------------------------------------------------------------
    # Tespit isleme (isciden gelen POST /ai/tespit)
    # ------------------------------------------------------------------
    def _yuz_kutuphanesi(self):
        """kisi_yuzler embeddinglerini onbellekten dondurur."""
        if (self._yuz_onbellek is not None and
                time.time() - self._yuz_onbellek_ts < 30):
            return self._yuz_onbellek
        liste = []
        with veritabani.baglanti() as con:
            rows = con.execute(
                "SELECT kisi_id, embedding FROM kisi_yuzler"
                " WHERE embedding != ''").fetchall()
        for r in rows:
            try:
                emb = np.frombuffer(base64.b64decode(r["embedding"]),
                                    dtype=np.float32)
                if emb.size:
                    liste.append((r["kisi_id"], emb))
            except Exception:
                continue
        self._yuz_onbellek = liste
        self._yuz_onbellek_ts = time.time()
        return liste

    def yuz_onbellek_sifirla(self):
        self._yuz_onbellek = None
        self._plaka_onbellek = None

    @staticmethod
    def _cosine(a, b):
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))

    # ------------------------------------------------------------------
    # v2.4.7: canli tespit kutulari (POST /ai/kutular)
    # ------------------------------------------------------------------
    def kutular_isle(self, veri):
        """Isciden gelen canli kutu bildirimini isler: yuz kutularini
        kutuphanedeki kisi adiyla etiketler ve video proxy'sinin
        anotasyon deposuna yazar (MJPEG uzerine cizim icin)."""
        if self.video_proxy is None:
            return
        kamera_id = veri.get("kamera_id")
        if kamera_id is None:
            return
        kutular = veri.get("kutular") or []
        for k in kutular:
            try:
                if k.get("tur") == "yuz" and k.get("embedding"):
                    kisi_id, benzerlik = self._yuz_eslestir(
                        k.get("embedding", ""))
                    if kisi_id:
                        with veritabani.baglanti() as con:
                            r = con.execute(
                                "SELECT ad FROM kisiler WHERE id=?",
                                (kisi_id,)).fetchone()
                        if r:
                            k["etiket"] = "%s (%%%d)" % (
                                r["ad"], int(benzerlik * 100))
                elif k.get("tur") == "plaka" and k.get("etiket"):
                    arac_id = self._plaka_eslestir(k.get("etiket", ""))
                    if arac_id:
                        with veritabani.baglanti() as con:
                            r = con.execute(
                                "SELECT plaka, marka, model FROM araclar"
                                " WHERE id=?", (arac_id,)).fetchone()
                        if r:
                            k["etiket"] = " ".join(
                                p for p in (r["plaka"], r["marka"],
                                            r["model"]) if p)
            except Exception:
                continue
            # embedding proxy'ye tasinmasin (bant genisligi/gizlilik)
            k.pop("embedding", None)
        try:
            self.video_proxy.anotasyon.guncelle(kamera_id, kutular)
        except Exception:
            pass

    def _yuz_eslestir(self, embedding_b64):
        """(kisi_id|None, benzerlik) dondurur."""
        if not embedding_b64:
            return None, 0.0
        try:
            emb = np.frombuffer(base64.b64decode(embedding_b64),
                                dtype=np.float32)
        except Exception:
            return None, 0.0
        en_iyi, en_iyi_puan = None, 0.0
        for kisi_id, kayitli in self._yuz_kutuphanesi():
            if kayitli.size != emb.size:
                continue
            puan = self._cosine(emb, kayitli)
            if puan > en_iyi_puan:
                en_iyi, en_iyi_puan = kisi_id, puan
        if en_iyi is not None and en_iyi_puan >= SFACE_ESIK:
            return en_iyi, en_iyi_puan
        return None, en_iyi_puan

    @staticmethod
    def _plaka_normallestir(metin):
        return "".join(c for c in (metin or "").upper() if c.isalnum())

    def _plaka_eslestir(self, metin):
        norm = self._plaka_normallestir(metin)
        if not norm:
            return None
        if (self._plaka_onbellek is None or
                time.time() - self._plaka_onbellek_ts > 30):
            with veritabani.baglanti() as con:
                rows = con.execute(
                    "SELECT id, plaka FROM araclar").fetchall()
            self._plaka_onbellek = {
                self._plaka_normallestir(r["plaka"]): r["id"]
                for r in rows if r["plaka"]}
            self._plaka_onbellek_ts = time.time()
        return self._plaka_onbellek.get(norm)

    def tespit_isle(self, veri):
        """Isciden gelen tespit bildirimini isler; WS yayini dondurur."""
        tur = veri.get("tur", "")
        kisi_id = arac_id = None
        benzerlik = 0.0
        if tur == "yuz":
            kisi_id, benzerlik = self._yuz_eslestir(
                veri.get("embedding", ""))
        elif tur == "plaka":
            arac_id = self._plaka_eslestir(veri.get("plaka_metin", ""))
        # v2.4.2: kutuphanesiz saf tespit turleri (hava_araci, insan,
        # kara_araci) kayitsiz listesine dusmez — dogrudan incelendi=1
        kutuphanesiz = tur in ("hava_araci", "insan", "kara_araci")

        # v2.4.2: kamera drona bagliysa ve dronun aktif ucusu varsa
        # tespiti ucus kaydina bagla (ucus geriye donuk izleme)
        ucus_id = self._tespit_ucus_id(veri.get("kamera_id"))

        # etiket: plaka metni veya isci adi; seviye eslesen kayittan gelir
        with veritabani.baglanti() as con:
            imlec = con.execute(
                "INSERT INTO ai_tespitler (ts, kamera_id, sunucu_id, tur,"
                " kisi_id, arac_id, etiket, seviye, guven, foto, klip,"
                " incelendi, ucus_id)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (float(veri.get("ts", time.time())),
                 int(veri.get("kamera_id", 0)), None, tur,
                 kisi_id, arac_id, veri.get("plaka_metin", ""),
                 "", float(veri.get("guven", 0)),
                 veri.get("foto", ""), veri.get("klip", ""),
                 1 if kutuphanesiz else 0, ucus_id))
            tespit_id = imlec.lastrowid
        if ucus_id:
            self.konsol("AI", f"Tespit #{tespit_id} ({tur}) ucus kaydina"
                              f" islendi: {ucus_id}")

        # eslesen kisi/arac ayrintilarini ekle
        kisi = arac = None
        if kisi_id:
            with veritabani.baglanti() as con:
                r = con.execute("SELECT id, ad, seviye FROM kisiler"
                                " WHERE id=?", (kisi_id,)).fetchone()
            kisi = dict(r) if r else None
        if arac_id:
            with veritabani.baglanti() as con:
                r = con.execute(
                    "SELECT id, plaka, marka, model, renk, seviye"
                    " FROM araclar WHERE id=?", (arac_id,)).fetchone()
            arac = dict(r) if r else None

        # eslesen kaydin seviyesini tespite isle (gecmis filtreleri icin)
        seviye = (kisi or {}).get("seviye") or (arac or {}).get("seviye")
        if seviye:
            with veritabani.baglanti() as con:
                con.execute("UPDATE ai_tespitler SET seviye=? WHERE id=?",
                            (seviye, tespit_id))

        yayin = {"tip": "ai_tespit",
                 "tespit": {"id": tespit_id,
                            "ts": veri.get("ts"),
                            "kamera_id": veri.get("kamera_id"),
                            "tur": tur,
                            "kisi": kisi, "arac": arac,
                            "plaka_metin": veri.get("plaka_metin", ""),
                            "benzerlik": round(benzerlik, 3),
                            "guven": veri.get("guven", 0),
                            "foto": veri.get("foto", ""),
                            "klip": veri.get("klip", ""),
                            "onizleme_b64": veri.get("onizleme_b64", ""),
                            "ucus_id": ucus_id,
                            "isci": veri.get("isci", "")}}
        if self.duyuru_cb:
            self.duyuru_cb(yayin)
        return yayin

    def _tespit_ucus_id(self, kamera_id):
        """v2.4.2: Kameranin bagli oldugu dronun aktif ucus id'si.

        Kamera drona bagli degilse veya dron ucusta degilse bos string
        doner. ucus_gecmisi referansi main.py'de atanir.
        """
        ug = getattr(self, "ucus_gecmisi", None)
        if ug is None or not kamera_id:
            return ""
        try:
            with veritabani.baglanti() as con:
                r = con.execute(
                    "SELECT dron_uid FROM kameralar WHERE id=?",
                    (int(kamera_id),)).fetchone()
            dron_uid = (r["dron_uid"] if r else "") or ""
            if not dron_uid:
                return ""
            return ug.aktif_ucus_id(dron_uid) or ""
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # v2.4.2: Hedef takibi (tracking) — angajman koprusu
    # ------------------------------------------------------------------
    def track_baslat(self, kamera_id, tur="", kutu=None):
        """Kamerayi izleyen iscide hedef takibini baslatir."""
        kamera_id = int(kamera_id)
        with self.kilit:
            sid = self.gorevler.get(kamera_id)
        if not sid:
            return {"tamam": False, "hata": "kamera AI izlemesinde degil"}
        kayit = self._sunucu_kaydi(sid)
        if not kayit:
            return {"tamam": False, "hata": "isci sunucu bulunamadi"}
        try:
            sonuc = self._http(kayit, "/takip_baslat",
                               {"kamera_id": kamera_id, "tur": tur,
                                "kutu": kutu})
        except Exception as e:
            return {"tamam": False, "hata": str(e)[:150]}
        if sonuc.get("tamam"):
            with self.kilit:
                self.takipler[kamera_id] = {
                    "tur": tur, "ts": time.time(), "kayip": False,
                    "kutu": sonuc.get("kutu") or kutu or []}
            self.konsol("AI", f"K{kamera_id} hedef takibi basladi"
                        f" ({tur or 'genel'})", "bilgi")
        return sonuc

    def track_durdur(self, kamera_id):
        kamera_id = int(kamera_id)
        with self.kilit:
            sid = self.gorevler.get(kamera_id)
            self.takipler.pop(kamera_id, None)
        if sid:
            kayit = self._sunucu_kaydi(sid)
            if kayit:
                try:
                    self._http(kayit, "/takip_durdur",
                               {"kamera_id": kamera_id})
                except Exception:
                    pass
        if self.duyuru_cb:
            self.duyuru_cb({"tip": "ai_takip", "kamera_id": kamera_id,
                            "aktif": False, "kayip": False})
        return {"tamam": True}

    def takip_isle(self, veri):
        """Isciden gelen takip konum bildirimi (POST /ai/takip)."""
        kamera_id = int(veri.get("kamera_id", 0))
        kayip = bool(veri.get("kayip"))
        with self.kilit:
            kayit = self.takipler.get(kamera_id)
            if kayit is None:
                kayit = {"tur": veri.get("tur", "")}
                self.takipler[kamera_id] = kayit
            kayit.update({"ts": float(veri.get("ts", time.time())),
                          "kutu": veri.get("kutu") or [],
                          "merkez": veri.get("merkez") or [],
                          "kayip": kayip})
            if kayip:
                self.takipler.pop(kamera_id, None)
        if self.duyuru_cb:
            self.duyuru_cb({"tip": "ai_takip", "kamera_id": kamera_id,
                            "aktif": not kayip, "kayip": kayip,
                            "kutu": veri.get("kutu") or [],
                            "merkez": veri.get("merkez") or []})
        if kayip:
            self.konsol("AI", f"K{kamera_id} hedef takibi kaybedildi",
                        "uyari")

    def son_takip_konum(self, kamera_id):
        """Angajman icin hedef konumu: kameranin lat/lon'u.

        Sabit kamera goruntusunden gercek dunya koordinati
        cikarilamayacagi icin hedef konum olarak kameranin bagli oldugu
        lokasyonun (veya dronun) konumu kullanilir; takip suruyorsa
        dron kameranin bulundugu noktaya yonlenir.
        """
        kamera_id = int(kamera_id)
        with self.kilit:
            if kamera_id not in self.takipler:
                return None, None, None
        try:
            with veritabani.baglanti() as con:
                r = con.execute(
                    "SELECT k.lokasyon_id, l.lat, l.lon"
                    " FROM kameralar k"
                    " LEFT JOIN lokasyonlar l ON l.id = k.lokasyon_id"
                    " WHERE k.id = ?", (kamera_id,)).fetchone()
            if r and r["lat"] is not None:
                return float(r["lat"]), float(r["lon"]), 0.0
        except Exception:
            pass
        return None, None, None

    def ucus_tespitleri(self, ucus_id):
        """v2.4.2: Bir ucus kaydina bagli tum AI tespitleri (timeline)."""
        if not ucus_id:
            return []
        with veritabani.baglanti() as con:
            rows = con.execute(
                "SELECT t.id, t.ts, t.kamera_id, t.tur, t.kisi_id,"
                " t.arac_id, t.etiket, t.seviye, t.guven, t.foto,"
                " t.klip, k.ad AS kisi_ad, a.plaka AS arac_plaka"
                " FROM ai_tespitler t"
                " LEFT JOIN kisiler k ON k.id = t.kisi_id"
                " LEFT JOIN araclar a ON a.id = t.arac_id"
                " WHERE t.ucus_id = ? ORDER BY t.ts",
                (str(ucus_id),)).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Gecmis + kayitsizlar
    # ------------------------------------------------------------------
    def gecmis(self, baslangic=None, bitis=None, kamera_id=None,
               tur=None, kisi_id=None, sadece_kayitsiz=False, limit=200):
        sorgu = ("SELECT t.*, k.ad AS kisi_ad, k.seviye AS kisi_seviye,"
                 " a.plaka AS arac_plaka, a.marka, a.model,"
                 " a.seviye AS arac_seviye"
                 " FROM ai_tespitler t"
                 " LEFT JOIN kisiler k ON k.id = t.kisi_id"
                 " LEFT JOIN araclar a ON a.id = t.arac_id WHERE 1=1")
        parametreler = []
        if baslangic:
            sorgu += " AND t.ts >= ?"
            parametreler.append(float(baslangic))
        if bitis:
            sorgu += " AND t.ts <= ?"
            parametreler.append(float(bitis))
        if kamera_id:
            sorgu += " AND t.kamera_id = ?"
            parametreler.append(int(kamera_id))
        if tur:
            sorgu += " AND t.tur = ?"
            parametreler.append(tur)
        if kisi_id:
            sorgu += " AND t.kisi_id = ?"
            parametreler.append(int(kisi_id))
        if sadece_kayitsiz:
            sorgu += (" AND t.kisi_id IS NULL AND t.arac_id IS NULL"
                      " AND t.incelendi = 0"
                      " AND t.tur IN ('yuz', 'plaka')")
        sorgu += " ORDER BY t.ts DESC LIMIT ?"
        parametreler.append(max(1, min(1000, int(limit))))
        with veritabani.baglanti() as con:
            rows = con.execute(sorgu, parametreler).fetchall()
        return [dict(r) for r in rows]

    def tespit_islenmis(self, tespit_id):
        """Kayitsiz tespit incelendi olarak isaretlenir (yok say)."""
        with veritabani.baglanti() as con:
            con.execute("UPDATE ai_tespitler SET incelendi=1 WHERE id=?",
                        (int(tespit_id),))

    def tespit_kisi_ata(self, tespit_id, kisi_id):
        with veritabani.baglanti() as con:
            con.execute("UPDATE ai_tespitler SET kisi_id=?, incelendi=1"
                        " WHERE id=?", (int(kisi_id), int(tespit_id)))

    def tespit_arac_ata(self, tespit_id, arac_id):
        with veritabani.baglanti() as con:
            con.execute("UPDATE ai_tespitler SET arac_id=?, incelendi=1"
                        " WHERE id=?", (int(arac_id), int(tespit_id)))
