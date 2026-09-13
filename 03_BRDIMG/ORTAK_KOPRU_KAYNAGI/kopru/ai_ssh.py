# -*- coding: utf-8 -*-
"""KOPRU YAZILIMI — AI BILGISAYARI SSH OTURUMLARI.

## NEDEN BU MODUL KOPRUDE
Kullanicinin AI bilgisayarlari (`ASUS Ascent GX10 · 192.168.1.100`)
OZEL AGDADIR. GOKTUNGU merkezde (`/app/`) calistigi icin merkez sunucusu
bu adrese hicbir kosulda erisemez; `ai_ssh_baslat` komutu merkezde
kosunca "Connection timed out" ile biter. Kullanicinin karsilastigi
kusur tam olarak buydu.

SSH oturumu, AI bilgisayariyla ayni yerel agda olan KOPRU makinesinde
acilmalidir. Merkez yalniz "basla/durdur/gecmisi ver" der; is buradaki
surecte yapilir ve konsol satirlari merkeze donulur.

## GCS TARAFIYLA ILISKI
`goktungu/ai_ssh.py` ile ayni davranisi uretir ve ayni sozluk bicimlerini
dondurur (`durum()`, `gecmis()`), boylece arayuz tarafinda tek bir
gosterim kodu iki yolu da isler. Kod cogaltmasi degil, YER degisikligi
soz konusudur: modul kopru paketinde bagimsiz durmak zorundadir cunku
kopru yazilimi GOKTUNGU kaynak agacini icermez (68 KB'lik bagimsiz paket).

## PAKET KISITI
`paramiko` YOK. Isletim sistemindeki OpenSSH istemcisi `subprocess`
ile cagrilir. Windows 10/11'de yerlesiktir; Linux'ta `openssh-client`
paketi gerekir. Kullanici sahada pip kurulumu yapamaz.
"""
import os
import shlex
import shutil
import subprocess
import threading
import time

# Sunucu basina saklanan en fazla konsol satiri.
TAMPON_SATIR = 2000

# SSH baglantisi icin beklenen en fazla sure (saniye).
BAGLANTI_ZAMANASIMI = 15

# Varsayilan uzak komut: AI iscisini baslatir.
VARSAYILAN_KOMUT = "python3 -m goktungu_ai.isci --port {port}"


def ssh_yolu():
    """Sistemdeki `ssh` calistirilabilirinin yolu (yoksa None)."""
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
    """`sshpass` varsa yolu (sifreli giris icin)."""
    return shutil.which("sshpass")


class SSHOturum:
    """Tek bir AI bilgisayarina ait SSH oturumu (surec + halka tampon)."""

    def __init__(self, sunucu_id, ad):
        self.sunucu_id = int(sunucu_id)
        self.ad = ad
        self.surec = None
        self.satirlar = []            # [(ts, akis, metin)]
        self.kilit = threading.Lock()
        self.baslama_ts = 0.0
        self.bitis_ts = 0.0
        self.cikis_kodu = None
        self.komut_gosterim = ""      # sifre MASKELENMIS komut

    def calisiyor(self):
        return self.surec is not None and self.surec.poll() is None

    def satir_ekle(self, akis, metin):
        with self.kilit:
            self.satirlar.append((time.time(), akis, metin))
            if len(self.satirlar) > TAMPON_SATIR:
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
    """AI bilgisayarlarina SSH ile baglanip AI iscisini baslatir.

    Merkezden gelen `ai_ssh_*` eylemleri bu sinifa dusurulur. Duyuru
    geri cagirmasi YOKTUR: kopru merkeze kendiliginden mesaj itmez,
    merkez `ai_ssh_gecmis` ile satirlari CEKER. Boylece role katmaninda
    ek bir kanal acmak gerekmez ve konsol penceresi kapaliyken bant
    genisligi harcanmaz.
    """

    def __init__(self, gunluk=None):
        self.gunluk_cb = gunluk
        self.oturumlar = {}           # sunucu_id -> SSHOturum
        self.kilit = threading.Lock()

    def gunluk(self, metin, seviye="bilgi"):
        if self.gunluk_cb:
            try:
                self.gunluk_cb(metin, seviye)
            except Exception:
                pass

    # ------------------------------------------------------------------
    def _komut_kur(self, kayit, sifre):
        """SSH komut dizisini ve maskelenmis gosterimi uretir.

        Donus: `(argv, gosterim, hata)`
        """
        ssh = ssh_yolu()
        if not ssh:
            return None, "", (
                "SSH istemcisi bu bilgisayarda bulunamadi. Windows'ta "
                "'Ayarlar > Uygulamalar > Istege bagli ozellikler' "
                "altindan 'OpenSSH Client' kurulmalidir; Linux'ta "
                "'openssh-client' paketi gerekir.")

        kullanici = str(kayit.get("ssh_kullanici") or "").strip()
        if not kullanici:
            return None, "", (
                "SSH kullanici adi tanimsiz. AI sunucusunu duzenleyip "
                "SSH kullanici adini girin.")

        host = str(kayit.get("host") or "").strip()
        if not host:
            return None, "", "Host/IP tanimsiz."

        try:
            sshport = int(kayit.get("ssh_port") or 22)
        except (TypeError, ValueError):
            sshport = 22

        anahtar = str(kayit.get("ssh_anahtar") or "").strip()
        komut = str(kayit.get("ssh_komut") or "").strip()
        if not komut:
            komut = VARSAYILAN_KOMUT.format(port=kayit.get("port") or 8900)

        argv = [ssh,
                "-p", str(sshport),
                "-o", "BatchMode=" + ("no" if sifre else "yes"),
                "-o", "StrictHostKeyChecking=accept-new",
                "-o", "ConnectTimeout=%d" % BAGLANTI_ZAMANASIMI,
                "-o", "ServerAliveInterval=15",
                "-tt"]
        if anahtar:
            if not os.path.isfile(anahtar):
                return None, "", "Ozel anahtar bulunamadi: %s" % anahtar
            argv += ["-i", anahtar, "-o", "IdentitiesOnly=yes"]
        argv += ["%s@%s" % (kullanici, host), komut]

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
            # Sifre komut satirinda GORUNMEZ: ortam degiskeni tasir.
            argv = [sp, "-e"] + argv

        gosterim = " ".join(shlex.quote(a) for a in argv if a != "-e")
        if sifre:
            gosterim = "sshpass -e " + gosterim.replace(
                shlex.quote(sshpass_yolu() or "sshpass") + " ", "", 1)
        return argv, gosterim, None

    # ------------------------------------------------------------------
    def baslat(self, kayit, sifre=""):
        """AI bilgisayarina SSH ile baglanip komutu baslatir.

        `kayit`: merkezden gelen ai_sunucular satiri (sozluk).
        Donus: `(basarili, hata)`
        """
        try:
            sid = int(kayit.get("id"))
        except (TypeError, ValueError):
            return False, "Gecersiz sunucu kimligi."

        with self.kilit:
            var = self.oturumlar.get(sid)
            if var is not None and var.calisiyor():
                return False, "Bu AI bilgisayari icin oturum zaten calisiyor."

        argv, gosterim, hata = self._komut_kur(kayit, sifre)
        if hata:
            self.gunluk("AI-SSH %s: %s" % (kayit.get("ad"), hata), "hata")
            return False, hata

        ot = SSHOturum(sid, kayit.get("ad") or ("#%d" % sid))
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
                creationflags=(subprocess.CREATE_NO_WINDOW
                               if os.name == "nt" else 0),
            )
        except Exception as e:
            hata = "SSH baslatilamadi: %s" % e
            self.gunluk("AI-SSH %s: %s" % (ot.ad, hata), "hata")
            return False, hata

        with self.kilit:
            self.oturumlar[sid] = ot

        ot.satir_ekle("bilgi", "$ " + gosterim)
        self.gunluk("AI-SSH %s: oturum baslatildi (pid %s)"
                    % (ot.ad, ot.surec.pid), "basari")

        threading.Thread(target=self._oku_dongusu, args=(ot,),
                         daemon=True).start()
        return True, ""

    # ------------------------------------------------------------------
    def _oku_dongusu(self, ot):
        """Uzak surecin ciktisini satir satir tampona yazar."""
        try:
            for satir in iter(ot.surec.stdout.readline, ""):
                ot.satir_ekle("cikti", satir.rstrip("\r\n"))
        except Exception as e:
            ot.satir_ekle("hata", "[okuma hatasi] %s" % e)
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
            # 255: SSH'in kendi hata kodu (baglanti/kimlik sorunu).
            # Bu ayrim onemli: "cikis kodu 255" tek basina operatore
            # hicbir sey soylemez, nedeni soylenmelidir.
            if kod == 255:
                ipucu = ("SSH baglanti veya kimlik dogrulama hatasi. "
                         "Kullanici adi, port ve anahtar dogru mu? "
                         "Parolali anahtar BatchMode ile calismaz.")
                ot.satir_ekle("hata", ipucu)
                self.gunluk("AI-SSH %s: %s" % (ot.ad, ipucu), "hata")
            elif kod not in (0, None) and sure < 3.0:
                ipucu = ("Uzak komut %.1f sn icinde cikis kodu %s ile "
                         "sonlandi. Komut yolu ve baglilik dogru mu?"
                         % (sure, kod))
                ot.satir_ekle("hata", ipucu)
                self.gunluk("AI-SSH %s: %s" % (ot.ad, ipucu), "uyari")
            else:
                self.gunluk("AI-SSH %s: oturum sonlandi (kod %s, %.0f sn)"
                            % (ot.ad, kod, sure), "bilgi")

    # ------------------------------------------------------------------
    def durdur(self, sunucu_id):
        """Calisan SSH oturumunu sonlandirir. Donus: `(tamam, hata)`"""
        try:
            sid = int(sunucu_id)
        except (TypeError, ValueError):
            return False, "Gecersiz sunucu kimligi."
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
            return False, "Oturum sonlandirilamadi: %s" % e
        ot.satir_ekle("bilgi", "[oturum kullanici tarafindan durduruldu]")
        self.gunluk("AI-SSH %s: oturum durduruldu" % ot.ad, "bilgi")
        return True, ""

    # ------------------------------------------------------------------
    def gecmis(self, sunucu_id, son=None):
        try:
            sid = int(sunucu_id)
        except (TypeError, ValueError):
            return {"sunucu_id": 0, "calisiyor": False, "satirlar": []}
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
        with self.kilit:
            oturumlar = list(self.oturumlar.values())
        for ot in oturumlar:
            if ot.calisiyor():
                try:
                    ot.surec.terminate()
                except Exception:
                    pass
