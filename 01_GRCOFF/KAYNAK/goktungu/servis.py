"""v2.4.49: Servis ve guc yonetimi.

Bu modul iki isi yapar:

1. **Servis yonetimi.** GOKTUNGU systemd birimi olarak kurulduysa
   arayuzden durdurulup baslatilabilir. Kullanici iki ekranli bir
   canta ile sahada calisiyor; makineye klavye baglayip
   `systemctl` yazmasi beklenemez.

2. **Makine kapatma.** Operatorun fiziksel makineye erismek zorunda
   kalmamasi icin arayuzden guvenli kapatma.

## Neden `systemctl` dogrudan cagrilamaz

Servis root olmayan bir kullanici ile calisir (guvenlik geregi:
GOKTUNGU disariya HTTP/WS acar, root ile calistirmak butun makineyi
riske atar). Ancak `systemctl stop` ve `poweroff` root yetkisi
ister. Uc secenek vardi:

| Secenek | Neden secilmedi/secildi |
|---|---|
| Servisi root ile calistir | TUM makineyi riske atar; reddedildi |
| Genel `sudo` NOPASSWD | Tum komutlara root verir; reddedildi |
| **Dar polkit/sudoers kurali** | Yalniz `goktungu.service` + kapatma; **secildi** |

Bu modul komutu once yetkisiz dener, `sudo -n` ile tekrar dener ve
her iki yol da kapaliysa **anlasilir** bir hata dondurur — operatore
hangi komutu koşturacagini yazar. Sessiz basarisizlik yok.

## Kullanici servisi mi sistem servisi mi

Iki kip desteklenir:

- **Sistem servisi** (`/etc/systemd/system/goktungu.service`):
  makine acilisinda, kimse oturum acmadan baslar. Kiosk icin
  DOGRU olan budur; ancak kurulum root ister.
- **Kullanici servisi** (`~/.config/systemd/user/goktungu.service`):
  root gerekmez, ama `loginctl enable-linger` yapilmadan yalniz
  oturum acikken calisir.

Hangisinin kurulu oldugu calisma aninda **olculur**, varsayilmaz.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time

BIRIM_ADI = "goktungu.service"

# Kapatma/yeniden baslatma icin denenecek komutlar, sirayla.
# systemctl once gelir cunku polkit ile yetkilendirilebilir;
# `poweroff`/`shutdown` genelde sudo ister.
_KAPAT_KOMUTLARI = (
    ["systemctl", "poweroff"],
    ["poweroff"],
    ["shutdown", "-h", "now"],
)
_YENIDEN_KOMUTLARI = (
    ["systemctl", "reboot"],
    ["reboot"],
    ["shutdown", "-r", "now"],
)

# Arayuzden gelen eylem adlari -> systemctl alt komutu
_EYLEMLER = {
    "baslat": "start",
    "durdur": "stop",
    "yeniden_baslat": "restart",
    "durum": "is-active",
    # v2.4.49: Kullanici istegi "bilgisayar acildiginda otomatik acilsin".
    # Bunu kurulum betigi bir kez yapar, ancak operatorun arayuzden
    # kapatip acabilmesi gerekir (or. bakim sirasinda otomatik baslamasin).
    # DIKKAT: bu iki eylem 'aktif' durumu DEGISTIRMEZ; yalniz acilis
    # davranisini degistirir. Arayuz bu ayrimi acikca gostermeli.
    "etkinlestir": "enable",
    "devredisi": "disable",
}

_ZAMAN_ASIMI = 15


class ServisYoneticisi:
    """systemd birimini ve makine gucunu yonetir."""

    def __init__(self, konsol=None, birim: str = BIRIM_ADI):
        self.birim = birim
        self._konsol = konsol
        # Kip onbellegi: her cagrida `systemctl` calistirmamak icin.
        # None = henuz olculmedi.
        self._kip = None
        self._kip_zaman = 0.0

    # ------------------------------------------------------------------
    # Yardimcilar
    # ------------------------------------------------------------------
    def _yaz(self, seviye, ileti):
        if self._konsol:
            try:
                self._konsol("SERVIS", ileti, seviye)
            except Exception:
                pass
        else:
            print(f"[SERVIS] {ileti}")

    @staticmethod
    def _kosur(komut, zaman_asimi=_ZAMAN_ASIMI):
        """Komutu calistirir; (donus_kodu, cikti) dondurur.

        Komut bulunamazsa donus kodu 127 verilir (kabuk gelenegi);
        boylece cagiran taraf 'yetki yok' ile 'komut yok' arasinda
        ayrim yapabilir.
        """
        if not shutil.which(komut[0]):
            return 127, f"{komut[0]} bulunamadi"
        try:
            s = subprocess.run(komut, capture_output=True, text=True,
                               timeout=zaman_asimi)
            cikti = ((s.stdout or "") + (s.stderr or "")).strip()
            return s.returncode, cikti
        except subprocess.TimeoutExpired:
            return 124, "zaman asimi"
        except Exception as e:
            return 1, str(e)

    def _sudo_ile(self, komut):
        """`sudo -n` ile tekrar dener.

        `-n` kritik: sifre sorulmasi gerekiyorsa sudo BEKLEMEZ, hemen
        hata verir. Aksi halde sunucu thread'i sifre bekleyerek sonsuza
        kadar asili kalirdi.
        """
        if not shutil.which("sudo"):
            return 127, "sudo bulunamadi"
        return self._kosur(["sudo", "-n"] + komut)

    # ------------------------------------------------------------------
    # Kip olcumu
    # ------------------------------------------------------------------
    def kip_olc(self, tazele=False):
        """Birimin hangi kipte kurulu oldugunu olcer.

        Doner: 'sistem' | 'kullanici' | 'yok'
        """
        if (not tazele and self._kip is not None
                and (time.time() - self._kip_zaman) < 30):
            return self._kip

        kip = "yok"
        if shutil.which("systemctl"):
            # Sistem birimi once denenir: kiosk icin dogru kip budur.
            kod, _ = self._kosur(
                ["systemctl", "cat", self.birim], zaman_asimi=8)
            if kod == 0:
                kip = "sistem"
            else:
                kod, _ = self._kosur(
                    ["systemctl", "--user", "cat", self.birim],
                    zaman_asimi=8)
                if kod == 0:
                    kip = "kullanici"
        self._kip = kip
        self._kip_zaman = time.time()
        return kip

    def _systemctl(self, alt_komut, kip=None):
        """Kipe uygun systemctl komutunu kurar."""
        kip = kip or self.kip_olc()
        if kip == "kullanici":
            return ["systemctl", "--user", alt_komut, self.birim]
        return ["systemctl", alt_komut, self.birim]

    # ------------------------------------------------------------------
    # Durum
    # ------------------------------------------------------------------
    def _birim_altinda_mi(self, kip=None):
        """Bu surec GERCEKTEN `self.birim` altinda mi calisiyor?

        `INVOCATION_ID` ile karar vermek yaniltir: systemd bu degiskeni
        calistirdigi her birime koyar ve degisken cocuk sureclere MIRAS
        GECER. systemd altinda dogmus bir kabuktan elle
        `python3 main.py` baslatildiginda degisken orada durur, oysa
        surec servis DEGILDIR. Olculdu: birim hic kurulu olmadigi halde
        bayrak `true` donuyordu.

        Olcum cgroup yolundan yapilir; systemd surecin birim adini
        oraya yazar. Birim kurulu degilse (kip == "yok") surecin servis
        olmasi imkansizdir, dogrudan False.
        """
        if (kip or self.kip_olc()) == "yok":
            return False
        try:
            with open("/proc/self/cgroup", encoding="utf-8") as f:
                cg = f.read()
        except OSError:
            # cgroup okunamiyorsa (kapsayici, macOS) eski davranisa
            # dusmek yerine ortam degiskenini yalniz DESTEKLEYICI kanit
            # sayariz: GOKTUNGU_SERVIS bizim kendi birim dosyamizda elle
            # tanimlanir, mirasla gelmez.
            return bool(os.environ.get("GOKTUNGU_SERVIS"))
        return self.birim in cg

    def durum(self):
        """Servis durumunu dondurur (arayuze gonderilir)."""
        kip = self.kip_olc()
        d = {
            "kurulu": kip != "yok",
            "kip": kip,
            "birim": self.birim,
            "pid": os.getpid(),
            "servis_olarak_calisiyor": self._birim_altinda_mi(kip),
        }
        if kip == "yok":
            d["aktif"] = None
            d["acilista"] = None
            d["ozet"] = "Servis kurulu degil"
            return d

        kod, cikti = self._kosur(self._systemctl("is-active", kip),
                                 zaman_asimi=8)
        d["aktif"] = (cikti.strip() == "active")
        d["durum_metni"] = cikti.strip() or "bilinmiyor"

        kod, cikti = self._kosur(self._systemctl("is-enabled", kip),
                                 zaman_asimi=8)
        d["acilista"] = (cikti.strip() in ("enabled", "enabled-runtime"))
        d["acilista_metni"] = cikti.strip() or "bilinmiyor"

        d["ozet"] = "%s / %s" % (
            "cAlisiyor" if d["aktif"] else "durdu",
            "acilista basliyor" if d["acilista"] else "acilista baslamiyor")
        return d

    def gunluk(self, satir=80):
        """journalctl ile son gunluk satirlarini dondurur."""
        kip = self.kip_olc()
        if kip == "yok":
            return {"tamam": False, "hata": "Servis kurulu degil.",
                    "satirlar": []}
        if not shutil.which("journalctl"):
            return {"tamam": False,
                    "hata": "journalctl bulunamadi (systemd gunlugu yok).",
                    "satirlar": []}
        try:
            satir = max(10, min(500, int(satir)))
        except (TypeError, ValueError):
            satir = 80
        komut = ["journalctl", "-u", self.birim, "-n", str(satir),
                 "--no-pager", "--output", "short-iso"]
        if kip == "kullanici":
            komut.insert(1, "--user")
        kod, cikti = self._kosur(komut, zaman_asimi=20)
        if kod != 0 and not cikti:
            return {"tamam": False,
                    "hata": "Gunluk okunamadi (yetki gerekebilir).",
                    "satirlar": []}
        return {"tamam": True, "satirlar": cikti.splitlines()[-satir:]}

    # ------------------------------------------------------------------
    # Eylemler
    # ------------------------------------------------------------------
    def eylem(self, ad):
        """Servis eylemini uygular.

        DIKKAT — `durdur` ve `yeniden_baslat` bu surecin KENDISINI
        oldurur. Cagiran taraf yaniti ONCE gondermeli; bu yuzden
        gecikmeli calistirma icin `gecikmeli_eylem` kullanilir.
        """
        alt = _EYLEMLER.get(ad)
        if not alt:
            return {"tamam": False, "hata": f"Bilinmeyen eylem: {ad}"}

        kip = self.kip_olc(tazele=True)
        if kip == "yok":
            return {"tamam": False,
                    "hata": "Servis kurulu degil. Kurmak icin: "
                            "sudo bash servis_kur.sh"}

        komut = self._systemctl(alt, kip)
        kod, cikti = self._kosur(komut)
        if kod == 0:
            self._yaz("bilgi", f"Servis eylemi uygulandi: {ad}")
            return {"tamam": True, "kip": kip, "cikti": cikti}

        # Kullanici servisi polkit istemez; sistem servisinde yetki
        # gerekir. sudo -n ile tekrar denenir.
        if kip == "sistem":
            kod2, cikti2 = self._sudo_ile(komut)
            if kod2 == 0:
                self._yaz("bilgi",
                          f"Servis eylemi uygulandi (sudo): {ad}")
                return {"tamam": True, "kip": kip, "cikti": cikti2,
                        "sudo": True}
            cikti = cikti2 or cikti

        self._yaz("hata", f"Servis eylemi basarisiz ({ad}): {cikti}")
        return {"tamam": False,
                "hata": "Yetki yok gorunuyor. Kurulum betigi polkit "
                        "kuralini yazmadiysa elle: "
                        f"sudo systemctl {alt} {self.birim}",
                "ayrinti": cikti}

    def eylem_hazir(self, ad):
        """Eylem uygulanabilir mi? `(hazir, neden)` ikilisi doner.

        NEDEN GEREKLI — `durdur`/`yeniden_baslat` bu sureci oldurur, bu
        yuzden WS yaniti eylemden ONCE gonderilir. Ama o sirada eylemin
        basarili olup olmayacagi henuz bilinmez. Yaniti gonderdikten
        sonra eylem yetki yoklugundan basarisiz olursa arayuz "servis
        durduruluyor" der, hicbir sey olmaz ve operator nedenini asla
        ogrenemez. Bu islev yetkiyi ONCEDEN olcer.
        """
        alt = _EYLEMLER.get(ad)
        if not alt:
            return False, f"Bilinmeyen eylem: {ad}"
        kip = self.kip_olc(tazele=True)
        if kip == "yok":
            return False, ("Servis kurulu degil. Kurmak icin: "
                           "sudo bash servis_kur.sh")
        if kip == "kullanici":
            # Kullanici servisi kendi oturumundadir; polkit istemez.
            return True, ""
        # Sistem servisi: root degilsek yetki gerekir.
        if os.geteuid() == 0:
            return True, ""
        yol = shutil.which("systemctl") or "/bin/systemctl"
        if self._sudo_izni_var(yol):
            return True, ""
        if self._polkit_izni_var("org.freedesktop.systemd1.manage-units"):
            return True, ""
        return False, ("Yetki yok: servis sistem kipinde ve bu kullanici "
                       "sifresiz systemctl yetkisine sahip degil. Kurulum "
                       "betigi bu yetkiyi verir: sudo bash servis_kur.sh")

    def gecikmeli_eylem(self, ad, gecikme=1.0):
        """Eylemi ayri bir thread'de, gecikmeli uygular.

        `durdur`/`yeniden_baslat` bu sureci oldurdugu icin WS yaniti
        once gonderilmeli. Gecikme, yanitin agdan cikmasina zaman
        tanir.
        """
        def _calis():
            time.sleep(max(0.2, float(gecikme)))
            self.eylem(ad)

        threading.Thread(target=_calis, daemon=True).start()
        return {"tamam": True, "gecikmeli": True}

    # ------------------------------------------------------------------
    # Guc yonetimi
    # ------------------------------------------------------------------
    def guc(self, ad, gecikme=2.0):
        """Makineyi kapatir ('kapat') veya yeniden baslatir ('yenidenbaslat').

        Gecikme, arayuze 'kapatiliyor' yanitinin ulasmasi icindir.
        """
        if ad == "kapat":
            komutlar = _KAPAT_KOMUTLARI
        elif ad == "yenidenbaslat":
            komutlar = _YENIDEN_KOMUTLARI
        else:
            return {"tamam": False, "hata": f"Bilinmeyen guc eylemi: {ad}"}

        # Yetki onden olculur: arayuze "kapatiliyor" deyip sonra sessizce
        # basarisiz olmak en kotu davranistir. Bu yuzden once KURU
        # deneme yapilir.
        hazir, neden = self.guc_hazir(ad)
        if not hazir:
            return {"tamam": False, "hata": neden}

        def _calis():
            time.sleep(max(0.5, float(gecikme)))
            for komut in komutlar:
                kod, cikti = self._kosur(komut, zaman_asimi=20)
                if kod == 0:
                    return
                kod, cikti = self._sudo_ile(komut)
                if kod == 0:
                    return
            self._yaz("hata", "Makine kapatilamadi: yetki yok.")

        threading.Thread(target=_calis, daemon=True).start()
        self._yaz("uyari",
                  "Makine kapatma komutu verildi."
                  if ad == "kapat" else
                  "Makine yeniden baslatma komutu verildi.")
        return {"tamam": True, "gecikme": gecikme}

    def _sudo_izni_var(self, komut_yolu):
        """`sudo -n -l KOMUT` ile o komut icin sifresiz yetki olcer.

        NEDEN BU YONTEM — Cloud Computer'da yetkisiz bir kullanici
        olusturulup uc yontem karsilastirildi:

        | Yontem | Yetkili | Yetkisiz | Kullanilir? |
        |---|---|---|---|
        | `systemctl --dry-run poweroff` | 0 | **0** | HAYIR |
        | `pkcheck --action-id ...` | 2 | 2 | HAYIR |
        | `sudo -n -l KOMUT` | 0 | 1 | **EVET** |

        `--dry-run` yalniz komutun BICIMINI dogrular, polkit'e hic
        sormaz; yetkisiz kullanicida da 0 doner. Ona guvenmek arayuzde
        dugmeyi etkin gosterip hicbir sey yapmamak demekti — tam olarak
        kacinilmasi gereken sessiz basarisizlik.
        """
        if not shutil.which("sudo"):
            return False
        kod, _ = self._kosur(["sudo", "-n", "-l", komut_yolu],
                            zaman_asimi=8)
        return kod == 0

    def _polkit_izni_var(self, eylem_id):
        """polkit kuralinin YAZILI olup olmadigini dosyadan olcer.

        polkit'e calisma aninda guvenilir bir sorgu yapilamadigi
        (`pkcheck` her durumda 2 donuyor) icin kural dosyalari okunur.
        Bu dolayli bir olcumdur; kesin olan `sudo -n -l` yoludur.
        """
        yollar = (
            "/etc/polkit-1/rules.d/49-goktungu.rules",
            "/etc/polkit-1/localauthority/50-local.d/49-goktungu.pkla",
        )
        for y in yollar:
            try:
                with open(y, "r", encoding="utf-8", errors="replace") as f:
                    icerik = f.read()
            except OSError:
                continue
            if eylem_id in icerik:
                return True
        return False

    def guc_hazir(self, ad="kapat"):
        """Kapatma yetkisi var mi olcer; (hazir, neden) dondurur.

        Uc yol sirayla denenir; herhangi biri yeterlidir:
        1. `sudo -n` ile sifresiz `systemctl poweroff` (en guvenilir olcum)
        2. `sudo -n` ile sifresiz `poweroff`/`shutdown`
        3. polkit kuralinin yazili olmasi (dolayli)

        Ayrica surec root ise yetki zaten vardir.
        """
        if os.geteuid() == 0:
            return True, ""

        systemctl_yolu = shutil.which("systemctl")
        if systemctl_yolu and self._sudo_izni_var(systemctl_yolu):
            return True, ""
        for ad_k in ("poweroff", "shutdown"):
            yol = shutil.which(ad_k)
            if yol and self._sudo_izni_var(yol):
                return True, ""

        eylem = ("org.freedesktop.login1.power-off" if ad == "kapat"
                 else "org.freedesktop.login1.reboot")
        if self._polkit_izni_var(eylem):
            return True, ""

        return False, ("Kapatma yetkisi yok. Yetki vermek icin: "
                       "sudo bash servis_kur.sh --izin")

    # ------------------------------------------------------------------
    # Ozet (arayuz acilisinda gonderilir)
    # ------------------------------------------------------------------
    def ozet(self):
        d = self.durum()
        hazir, neden = self.guc_hazir("kapat")
        d["guc_hazir"] = hazir
        d["guc_neden"] = neden
        return d
