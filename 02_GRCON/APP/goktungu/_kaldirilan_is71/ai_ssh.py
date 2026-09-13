"""AI bilgisayarlarini SSH ile uzaktan baslatma ve canli konsol.

v2.4.45 - Kullanici istegi:
  "AI bilgisayarlar bolumunde bilgisayarin ip'si gibi ayni zamanda SSH
   kullanici bilgilerini de isteyelim, Sunucularin yaninda play dugmesi
   olsun, kullanici play dugmesine basinca SSH olarak baglansin ve
   sunucuyu baslatsin."
  "ai sunucusunun yaninda birde consol dugmesi olsun, basinca ssh consol
   ciktilarini gorebilelim, istersek tekrar kapatabilelim"

Tasarim kararlari
-----------------
1) **pip install YOK.** Saha bilgisayarlarinda ek paket kurulamaz
   (kullanici kisiti). `paramiko` yerine isletim sistemindeki OpenSSH
   istemcisi `subprocess` ile cagrilir. Windows 10/11'de OpenSSH
   istemcisi yerlesiktir (`C:\\Windows\\System32\\OpenSSH\\ssh.exe`).

2) **Cikti canli akar.** Uzak surecin stdout/stderr'i satir satir
   okunur, halka tamponda birikir ve WS ile arayuze duyurulur. Panel
   kapaliyken de tampon dolmaya devam eder; konsol dugmesine basildiginda
   gecmis hazir gelir (kullanici "istersek tekrar kapatabilelim" dedi:
   kapatmak yalniz gorunumu kapatir, akisi kesmez).

3) **Sifre yolu ikincildir.** Parolasiz ozel anahtar birincil yontemdir.
   Sifre girildiginde `sshpass` gerekir; yoksa anlasilir hata verilir
   (sessiz basarisizlik kabul edilemez).

4) **Komut sonlanabilir de, surekli de olabilir.** AI iscisi genelde
   surekli calisir; bu yuzden surec yasadigi surece "calisiyor" sayilir
   ve `durdur()` ile sonlandirilabilir.
"""

import os
import queue
import shlex
import shutil
import subprocess
import threading
import time

# Halka tampon: sunucu basina saklanan en fazla satir sayisi.
# 2000 satir ~ 200 KB; bellek maliyeti onemsiz, tanilama degeri yuksek.
TAMPON_SATIR = 2000

# Baglanti kurulmasi icin beklenen en fazla sure (saniye).
BAGLANTI_ZAMANASIMI = 15

# Varsayilan uzak komut: AI iscisini baslatir.
VARSAYILAN_KOMUT = "python3 -m goktungu_ai.isci --port {port}"


def ssh_yolu():
    """Sistemdeki `ssh` calistirilabilirinin yolunu dondurur.

    Windows'ta PATH'te olmayabilir; bilinen konum da denenir.
    """
    y = shutil.which("ssh")
    if y:
        return y
    if os.name == "nt":
        aday = os.path.join(
            os.environ.get("WINDIR", r"C:\Windows"),
            "System32", "OpenSSH", "ssh.exe")
        if os.path.isfile(aday):
            return aday
    return None


def sshpass_yolu():
    """`sshpass` varsa yolunu dondurur (sifreli giris icin)."""
    return shutil.which("sshpass")


class SSHOturum:
    """Tek bir AI bilgisayarina ait SSH oturumu (surec + tampon)."""

    def __init__(self, sunucu_id, ad):
        self.sunucu_id = int(sunucu_id)
        self.ad = ad
        self.surec = None
        self.satirlar = []          # [(ts, akis, metin)]
        self.kilit = threading.Lock()
        self.baslama_ts = 0.0
        self.bitis_ts = 0.0
        self.cikis_kodu = None
        self.komut_gosterim = ""    # sifre maskelenmis komut

    # ------------------------------------------------------------------
    def calisiyor(self):
        return self.surec is not None and self.surec.poll() is None

    def satir_ekle(self, akis, metin):
        with self.kilit:
            self.satirlar.append((time.time(), akis, metin))
            if len(self.satirlar) > TAMPON_SATIR:
                # Bastan kirp: en yeni satirlar her zaman korunur
                del self.satirlar[:len(self.satirlar) - TAMPON_SATIR]

    def gecmis(self, son=None):
        with self.kilit:
            kaynak = self.satirlar if son is None else self.satirlar[-son:]
            return [{"ts": t, "akis": a, "metin": m} for t, a, m in kaynak]

    def durum(self):
        return {
            "sunucu_id": self.sunucu_id,
            "calisiyor": self.calisiyor(),
            "baslama": self.baslama_ts,
            "bitis": self.bitis_ts,
            "cikis_kodu": self.cikis_kodu,
            "komut": self.komut_gosterim,
            "satir_sayisi": len(self.satirlar),
        }


class AISSHYonetici:
    """AI bilgisayarlarina SSH ile baglanip AI iscisini baslatir."""

    def __init__(self, konsol, duyuru_cb=None):
        self.konsol = konsol
        # duyuru_cb(dict) -> tum WS istemcilerine yayin
        self.duyuru_cb = duyuru_cb
        self.oturumlar = {}          # sunucu_id -> SSHOturum
        self.kilit = threading.Lock()
        self._kuyruk = queue.Queue()
        self._calisiyor = True
        # Duyurular ayri is parcasindan gonderilir: okuma dongusu
        # WS'e dogrudan yazmaz (asyncio dongusu farkli is parcasinda).
        self._duyurucu = threading.Thread(
            target=self._duyuru_dongusu, daemon=True)
        self._duyurucu.start()

    # ------------------------------------------------------------------
    def _duyur(self, paket):
        if self.duyuru_cb is None:
            return
        self._kuyruk.put(paket)

    def _duyuru_dongusu(self):
        """Kuyruktaki duyurulari toplayip yayinlar (satir basina degil).

        Yuksek hizli ciktida her satir icin ayri WS mesaji gondermek
        arayuzu bogar; 200 ms'lik pencerelerde toplanir.
        """
        bekleyen = []
        while self._calisiyor:
            try:
                paket = self._kuyruk.get(timeout=0.2)
                bekleyen.append(paket)
                # Kuyrukta baska varsa hepsini al
                while True:
                    try:
                        bekleyen.append(self._kuyruk.get_nowait())
                    except queue.Empty:
                        break
            except queue.Empty:
                pass
            if not bekleyen:
                continue
            # Ayni sunucunun satirlarini tek mesajda birlestir
            satir_paketleri = {}
            digerleri = []
            for p in bekleyen:
                if p.get("tip") == "ai_ssh_satir":
                    sid = p.get("sunucu_id")
                    satir_paketleri.setdefault(sid, []).extend(
                        p.get("satirlar", []))
                else:
                    digerleri.append(p)
            bekleyen = []
            for sid, satirlar in satir_paketleri.items():
                try:
                    self.duyuru_cb({"tip": "ai_ssh_satir",
                                    "sunucu_id": sid,
                                    "satirlar": satirlar})
                except Exception:
                    pass
            for p in digerleri:
                try:
                    self.duyuru_cb(p)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    def _komut_kur(self, kayit, sifre):
        """SSH komut dizisini ve gosterim halini uretir.

        Donus: (argv, gosterim, hata)
        """
        ssh = ssh_yolu()
        if not ssh:
            return None, "", (
                "SSH istemcisi bulunamadi. Windows'ta 'Ayarlar > "
                "Uygulamalar > Istege bagli ozellikler' altindan "
                "'OpenSSH Client' kurulmalidir; Linux'ta 'openssh-client' "
                "paketi gerekir.")

        kullanici = (kayit.get("ssh_kullanici") or "").strip()
        if not kullanici:
            return None, "", (
                "SSH kullanici adi tanimsiz. AI sunucusunu duzenleyip "
                "SSH kullanici adini girin.")

        host = (kayit.get("host") or "").strip()
        if not host:
            return None, "", "Host/IP tanimsiz."

        try:
            sshport = int(kayit.get("ssh_port") or 22)
        except (TypeError, ValueError):
            sshport = 22

        anahtar = (kayit.get("ssh_anahtar") or "").strip()
        komut = (kayit.get("ssh_komut") or "").strip()
        if not komut:
            komut = VARSAYILAN_KOMUT.format(port=kayit.get("port") or 8900)

        argv = [ssh,
                "-p", str(sshport),
                "-o", "BatchMode=" + ("no" if sifre else "yes"),
                "-o", "StrictHostKeyChecking=accept-new",
                "-o", f"ConnectTimeout={BAGLANTI_ZAMANASIMI}",
                "-o", "ServerAliveInterval=15",
                # Uzak surec kendi TTY'sinde calissin: cikisi satir satir
                # akar ve SSH kapaninca surec de sonlanir.
                "-tt"]
        if anahtar:
            if not os.path.isfile(anahtar):
                return None, "", f"Ozel anahtar bulunamadi: {anahtar}"
            argv += ["-i", anahtar, "-o", "IdentitiesOnly=yes"]
        argv += [f"{kullanici}@{host}", komut]

        if sifre:
            sp = sshpass_yolu()
            if not sp:
                return None, "", (
                    "Sifre ile giris icin 'sshpass' gerekir ve bu "
                    "bilgisayarda bulunmuyor. Onerilen yol: parolasiz "
                    "ozel anahtar olusturup (ssh-keygen) genel anahtari "
                    "AI bilgisayarina kopyalayin (ssh-copy-id), sonra "
                    "anahtar dosyasinin yolunu SSH Anahtari alanina "
                    "yazin.")
            # Sifre komut satirinda GORUNMEZ: ortam degiskeni kullanilir
            argv = [sp, "-e"] + argv

        gosterim = " ".join(shlex.quote(a) for a in argv
                            if a not in ("-e",))
        if sifre:
            gosterim = "sshpass -e " + gosterim.replace(
                shlex.quote(sshpass_yolu() or "sshpass") + " ", "", 1)
        return argv, gosterim, None

    # ------------------------------------------------------------------
    def baslat(self, kayit, sifre=""):
        """AI bilgisayarina SSH ile baglanip komutu baslatir.

        `kayit`: ai_sunucular satiri (dict)
        Donus: (basarili, hata)
        """
        sid = int(kayit.get("id"))
        with self.kilit:
            var = self.oturumlar.get(sid)
            if var is not None and var.calisiyor():
                return False, "Bu AI bilgisayari icin oturum zaten calisiyor."

        argv, gosterim, hata = self._komut_kur(kayit, sifre)
        if hata:
            self.konsol("AI-SSH", f"{kayit.get('ad')}: {hata}", "hata")
            self._duyur({"tip": "ai_ssh_durum", "sunucu_id": sid,
                         "calisiyor": False, "hata": hata})
            return False, hata

        ot = SSHOturum(sid, kayit.get("ad") or f"#{sid}")
        ot.komut_gosterim = gosterim
        ot.baslama_ts = time.time()

        ortam = dict(os.environ)
        if sifre:
            ortam["SSHPASS"] = sifre

        try:
            ot.surec = subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=ortam,
                bufsize=1,
                universal_newlines=True,
                errors="replace",
                # Windows'ta konsol penceresi acilmasin
                creationflags=(subprocess.CREATE_NO_WINDOW
                               if os.name == "nt" else 0),
            )
        except Exception as e:
            hata = f"SSH baslatilamadi: {e}"
            self.konsol("AI-SSH", f"{ot.ad}: {hata}", "hata")
            self._duyur({"tip": "ai_ssh_durum", "sunucu_id": sid,
                         "calisiyor": False, "hata": hata})
            return False, hata

        with self.kilit:
            self.oturumlar[sid] = ot

        ot.satir_ekle("bilgi", f"$ {gosterim}")
        self.konsol("AI-SSH", f"{ot.ad}: SSH oturumu baslatildi "
                              f"(pid {ot.surec.pid})", "basari")
        self._duyur({"tip": "ai_ssh_durum", **ot.durum()})

        threading.Thread(target=self._oku_dongusu, args=(ot,),
                         daemon=True).start()
        return True, ""

    # ------------------------------------------------------------------
    def _oku_dongusu(self, ot):
        """Uzak surecin ciktisini satir satir okur ve yayinlar."""
        try:
            for satir in iter(ot.surec.stdout.readline, ""):
                metin = satir.rstrip("\r\n")
                ot.satir_ekle("cikti", metin)
                self._duyur({"tip": "ai_ssh_satir", "sunucu_id": ot.sunucu_id,
                             "satirlar": [{"ts": time.time(),
                                           "akis": "cikti",
                                           "metin": metin}]})
        except Exception as e:
            ot.satir_ekle("hata", f"[okuma hatasi] {e}")
        finally:
            try:
                ot.surec.stdout.close()
            except Exception:
                pass
            try:
                ot.cikis_kodu = ot.surec.wait(timeout=5)
            except Exception:
                ot.cikis_kodu = None
            ot.bitis_ts = time.time()
            sure = max(0.0, ot.bitis_ts - ot.baslama_ts)
            kod = ot.cikis_kodu
            # 255: SSH'in kendi hata kodu (baglanti/kimlik sorunu)
            if kod == 255:
                ipucu = ("SSH baglanti veya kimlik dogrulama hatasi. "
                         "Kullanici adi, port ve anahtar dogru mu? "
                         "Anahtar parolali ise SSH ile calismaz.")
                ot.satir_ekle("hata", ipucu)
                self.konsol("AI-SSH", f"{ot.ad}: {ipucu}", "hata")
            elif kod not in (0, None) and sure < 3.0:
                ipucu = (f"Uzak komut {sure:.1f} sn icinde cikis kodu "
                         f"{kod} ile sonlandi. Komut yolu ve baglilik "
                         f"dogru mu?")
                ot.satir_ekle("hata", ipucu)
                self.konsol("AI-SSH", f"{ot.ad}: {ipucu}", "uyari")
            else:
                self.konsol("AI-SSH", f"{ot.ad}: oturum sonlandi "
                                      f"(kod {kod}, {sure:.0f} sn)", "bilgi")
            self._duyur({"tip": "ai_ssh_durum", **ot.durum()})

    # ------------------------------------------------------------------
    def durdur(self, sunucu_id):
        """Calisan SSH oturumunu sonlandirir."""
        sid = int(sunucu_id)
        with self.kilit:
            ot = self.oturumlar.get(sid)
        if ot is None or not ot.calisiyor():
            return False, "Calisan oturum yok."
        try:
            ot.surec.terminate()
            try:
                ot.surec.wait(timeout=5)
            except subprocess.TimeoutExpired:
                ot.surec.kill()
        except Exception as e:
            return False, f"Oturum sonlandirilamadi: {e}"
        ot.satir_ekle("bilgi", "[oturum kullanici tarafindan durduruldu]")
        self.konsol("AI-SSH", f"{ot.ad}: oturum durduruldu", "bilgi")
        return True, ""

    # ------------------------------------------------------------------
    def gecmis(self, sunucu_id, son=None):
        sid = int(sunucu_id)
        with self.kilit:
            ot = self.oturumlar.get(sid)
        if ot is None:
            return {"sunucu_id": sid, "calisiyor": False, "satirlar": []}
        d = ot.durum()
        d["satirlar"] = ot.gecmis(son)
        return d

    def durumlar(self):
        with self.kilit:
            return [ot.durum() for ot in self.oturumlar.values()]

    def kapat(self):
        self._calisiyor = False
        with self.kilit:
            oturumlar = list(self.oturumlar.values())
        for ot in oturumlar:
            if ot.calisiyor():
                try:
                    ot.surec.terminate()
                except Exception:
                    pass
