#!/usr/bin/env python3.11
"""
GOKTUNGU KOPRU — Debian/Ubuntu paketi (.deb) ureteci
==================================================

Kullanici "bildigin kurulum programi" istedi. Ubuntu karsiligi
`kur.sh` betigi degil **.deb paketidir**: cift tiklanip Yazilim
Yukleyici ile kurulur, `apt` ile yukseltilir, `apt remove` ile
kaldirilir ve "Yuklu Uygulamalar" listesinde gorunur.

Windows tarafiyla ESLENIK tasarim:

| Ozellik | Windows (setup.exe) | Ubuntu (.deb) |
|---|---|---|
| Kurulum yeri | C:\\Program Files\\Goktungu\\Kopru | /opt/goktungu/kopru |
| Servis | SCM servisi (LocalSystem) | systemd SISTEM servisi (goktungu-kopru) |
| Veri | C:\\ProgramData\\Goktungu\\Kopru | /var/lib/goktungu-kopru |
| Baslat menusu | $SMPROGRAMS\\GOKTUNGU | /usr/share/applications |
| Masaustu | $DESKTOP | her kullanicinin masaustune |
| Kaldirma | Program Ekle/Kaldir | apt remove |

## Neden SISTEM servisi (kullanici servisi degil)

`kur.sh` `systemctl --user` kullaniyordu ve `linger` gerektiriyordu.
.deb paketi root olarak kurulur; kurulum sirasinda hangi masaustu
kullanicisinin servisi isteyecegi bilinemez. Sistem servisi:

- makine acilisinda, kimse oturum acmadan baslar (Windows'taki
  LocalSystem servisiyle ayni davranis)
- `linger` ayari gerektirmez
- tek merkezden yonetilir: `systemctl status goktungu-kopru`

Servis, ayri bir sistem kullanicisi (`goktungu-kopru`) ile calisir; root
olarak calistirmak gereksiz yetki demektir. Seri port erisimi icin bu
kullanici `dialout` grubuna alinir.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tarfile

KOK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KOK)

from kopru.surumler import KOPRU_SURUM  # noqa: E402

PAKET_AD = "goktungu-kopru"
MIMARI = "all"
BAKIMCI = "Turkbey Teknoloji <destek@gokkubbetech.com>"
HEDEF = "/opt/goktungu/kopru"
VERI = "/var/lib/goktungu-kopru"
SERVIS_KULLANICI = "goktungu-kopru"
PANEL_PORT = 8790

# ---------------------------------------------------------------------
# Faz 5 — URUN PROFILI (BRDIMG / BRDTLM)
# ---------------------------------------------------------------------
# Ayni cekirdek iki AYRI .deb olarak paketlenebilir. `--urun brdtlm`
# verilince asagidaki genel degiskenler BRDTLM'e ozgu degerlerle yeniden
# atanir; boylece paket adi, servis adi, kurulum/veri dizinleri, panel
# portu ve ikon dosya adi BRDTLM'e ait olur ve iki paket AYNI makineye
# yan yana kurulabilir (dpkg dosya cakismasi olmaz).
#
# GERIYE UYUMLULUK — KRITIK: `--urun` verilmezse (ya da `brdimg`
# verilirse) hicbir genel degisken degismez ve uretilen .deb BYTE-AYNI
# kalir. Asagidaki degiskenlerin varsayilanlari bilerek mevcut
# literallerle birebir aynidir; f-string'lerde artik bu degiskenler
# kullanildigi icin varsayilan cikti degismez.
URUN = "brdimg"                         # etkin urun (varsayilan)
URUN_ENV = None                         # systemd Environment / URUN dosyasi
URUN_GORUNEN_AD = "GÖKTUNGU Köprü"       # .desktop Name
URUN_GORUNEN_AD_EN = "GOKTUNGU Bridge"   # .desktop Name[en]
URUN_KISA_ACIKLAMA = "GOKTUNGU Kopru — yerel servis koprusu"

# `--urun brdtlm` icin uygulanacak degerler. Yalniz secildiginde
# yuklenir; secilmezse hicbiri okunmaz.
URUN_TANIMLARI = {
    "brdimg": {},   # varsayilan: hicbir sey degismez (BYTE-AYNI cikti)
    "brdtlm": {
        "PAKET_AD": "goktungu-kopru-tlm",
        "HEDEF": "/opt/goktungu/kopru-tlm",
        "VERI": "/var/lib/goktungu-kopru-tlm",
        "SERVIS_KULLANICI": "goktungu-kopru-tlm",
        "PANEL_PORT": 8791,
        "URUN_ENV": "brdtlm",
        "URUN_GORUNEN_AD": "GÖKTUNGU Köprü (Telemetri)",
        "URUN_GORUNEN_AD_EN": "GOKTUNGU Bridge (Telemetry)",
        "URUN_KISA_ACIKLAMA":
            "GOKTUNGU Kopru (Telemetri) — dron/telemetri cihaz koprusu",
    },
}


def urun_uygula(urun):
    """Secilen urunun genel degiskenlerini yukler.

    `brdimg` (varsayilan) icin HICBIR sey degismez: uretilen paket
    onceki surumlerle BYTE-AYNI kalir. Bilinmeyen urun adinda hata verir;
    sessizce brdimg'e donmek, kullanicinin istedigi paketi degil baskasini
    uretip fark etmemesine yol acardi.
    """
    global URUN, PAKET_AD, HEDEF, VERI, SERVIS_KULLANICI, PANEL_PORT
    global URUN_ENV, URUN_GORUNEN_AD, URUN_GORUNEN_AD_EN, URUN_KISA_ACIKLAMA
    ad = str(urun or "brdimg").strip().lower()
    if ad not in URUN_TANIMLARI:
        raise SystemExit("Bilinmeyen urun: %r (secenekler: %s)"
                         % (urun, ", ".join(sorted(URUN_TANIMLARI))))
    URUN = ad
    d = URUN_TANIMLARI[ad]
    PAKET_AD = d.get("PAKET_AD", PAKET_AD)
    HEDEF = d.get("HEDEF", HEDEF)
    VERI = d.get("VERI", VERI)
    SERVIS_KULLANICI = d.get("SERVIS_KULLANICI", SERVIS_KULLANICI)
    PANEL_PORT = d.get("PANEL_PORT", PANEL_PORT)
    URUN_ENV = d.get("URUN_ENV", URUN_ENV)
    URUN_GORUNEN_AD = d.get("URUN_GORUNEN_AD", URUN_GORUNEN_AD)
    URUN_GORUNEN_AD_EN = d.get("URUN_GORUNEN_AD_EN", URUN_GORUNEN_AD_EN)
    URUN_KISA_ACIKLAMA = d.get("URUN_KISA_ACIKLAMA", URUN_KISA_ACIKLAMA)

# Pakete girecek uygulama dosyalari
# `tani_sifirla.sh` pakete DAHILDIR: servis olusmadiginda kullanicinin
# elinde tani araci bulunmali. Disaridan indirmesi gerekirse tam o anda
# (panel calismiyor, servis yok) en zor durumda kalir.
# `ai_sunucu.py` pakete DAHILDIR (v1.7.20): AI servisi bunu 127.0.0.1
# uzerinde alt surec olarak baslatir. Dosya olmadan kurulum sorunsuz
# tamamlanir, panel acilir, AI servisi "calisiyor" gorunur - ama ayri
# AI bilgisayari olmayan sahada hicbir kamera izlenemez.
DAHIL_DOSYA = ["main.py", "ai_sunucu.py", "SURUM", "tani_sifirla.sh"]
# `ai_modeller` ISTEGE BAGLIDIR: dizin yoksa kopyalanmaz ve isci eksik
# modeli acilista kendisi indirir. Internet erisimi olmayan saha icin
# kaynak agacina onceden konulabilir; o zaman pakete girer.
DAHIL_DIZIN = ["kopru", "web", "varliklar", "ai_modeller"]

# Dagitima girmemesi gerekenler: sinav betikleri, olcum araclari,
# Windows'a ozgu dosyalar, gelistirme notlari.
DISLA_DESEN = (
    "sinav_", "olcum_", "yayinla_", "canli_", "deb_uret", "paketle",
    "gomulu_", "setup.nsi", "servis_win.py", "ikon_uret",
    ".md", ".pyc", "__pycache__", ".git",
)


def dislanir(ad):
    return any(p in ad for p in DISLA_DESEN)


def yaz(yol, icerik, kip=0o644):
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8", newline="\n") as f:
        f.write(icerik)
    os.chmod(yol, kip)


def kur_agaci(calisma):
    """Paket dosya agacini olusturur."""
    kok = os.path.join(calisma, PAKET_AD)
    if os.path.isdir(kok):
        shutil.rmtree(kok)

    # --- /opt/goktungu/kopru: uygulama ---
    hedef = os.path.join(kok, HEDEF.lstrip("/"))
    os.makedirs(hedef, exist_ok=True)
    # 1.7.19 DUZELTME: kok dizindeki SURUM dosyasi elle guncellenmedigi
    # icin paketlere bayat surum (1.6.1) giriyordu (1.7.15-1.7.18'de
    # olculdu). Tek kaynak surumler.KOPRU_SURUM'dur; dosya her paketlemede
    # buradan yeniden yazilir (setup.nsi de ayni dosyayi kullanir).
    with open(os.path.join(KOK, "SURUM"), "w", encoding="utf-8") as f:
        f.write(f"{KOPRU_SURUM}\n")
    for d in DAHIL_DOSYA:
        k = os.path.join(KOK, d)
        if os.path.exists(k):
            h = os.path.join(hedef, d)
            shutil.copy2(k, h)
            if d.endswith(".sh"):
                os.chmod(h, 0o755)
    for d in DAHIL_DIZIN:
        k = os.path.join(KOK, d)
        if os.path.isdir(k):
            shutil.copytree(
                k, os.path.join(hedef, d),
                ignore=shutil.ignore_patterns(
                    "__pycache__", "*.pyc", "hicolor"),
            )

    # --- URUN kimlik dosyasi (Faz 5) ---
    # BRDTLM paketinin kimligini kurulum kokune yazar. systemd birimi
    # ayrica GOKTUNGU_KOPRU_URUN=brdtlm ortam degiskenini de verir; dosya
    # ikinci bir kaynaktir (elle calistirma, servis disi arac vb.). URUN
    # secilmemisken (brdimg) dosya YAZILMAZ -> cikti BYTE-AYNI kalir.
    if URUN_ENV:
        with open(os.path.join(hedef, "URUN"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write(f"{URUN_ENV}\n")

    # --- Ikonlar: hicolor temasina ---
    ikon_kaynak = os.path.join(KOK, "varliklar", "hicolor")
    if os.path.isdir(ikon_kaynak):
        ikon_hedef = os.path.join(kok, "usr/share/icons/hicolor")
        shutil.copytree(ikon_kaynak, ikon_hedef, dirs_exist_ok=True)
        # Ikon dosya adi paket adiyla ESLENMELI. Ayri urunler (BRDTLM)
        # ayni "goktungu-kopru.png" dosyasina sahip cikamaz; yoksa iki
        # paket ayni makineye kurulunca dpkg dosya cakismasi verir.
        # Varsayilan (goktungu-kopru) icin ad zaten dogru: yeniden
        # adlandirma yapilmaz ve cikti BYTE-AYNI kalir.
        if PAKET_AD != "goktungu-kopru":
            for kokd, _, dslar in os.walk(ikon_hedef):
                for ds in dslar:
                    if ds == "goktungu-kopru.png":
                        os.rename(
                            os.path.join(kokd, ds),
                            os.path.join(kokd, "%s.png" % PAKET_AD))

    # --- systemd sistem servisi ---
    # StartLimitBurst/StartLimitIntervalSec [Unit] bolumune AITTIR.
    # [Service] altina yazilirsa systemd "Unknown key name" diyerek
    # SESSIZCE yok sayar; cokme dongusu sinirsiz kalir. Bu kusur
    # kur.sh'de gercek systemd ile OLCULDU.
    #
    # URUN profili: BRDTLM icin GOKTUNGU_KOPRU_URUN=brdtlm ortam
    # degiskeni eklenir; servis ve tum alt servisler bunu miras alir ve
    # yalniz BRDTLM servislerini (dron/m50/radar/gcsdual) gosterir. URUN
    # secilmemisken satir BOS olur -> birim dosyasi BYTE-AYNI kalir.
    _urun_env_satiri = (
        f"Environment=GOKTUNGU_KOPRU_URUN={URUN_ENV}\n" if URUN_ENV else "")
    yaz(os.path.join(kok, "lib/systemd/system", f"{PAKET_AD}.service"), f"""\
[Unit]
Description=GOKTUNGU Kopru Yazilimi
Documentation=https://goktungu.com/
After=network-online.target
Wants=network-online.target
StartLimitBurst=10
StartLimitIntervalSec=300

[Service]
Type=simple
User={SERVIS_KULLANICI}
Group={SERVIS_KULLANICI}
WorkingDirectory={HEDEF}
Environment=GOKTUNGU_KOPRU_VERI={VERI}
{_urun_env_satiri}# --tarayici-yok: servis kipinde tarayici acmak anlamsizdir; grafik
# oturum olmayabilir ve tarayici acma cagrisi saniyelerce bloke olur.
ExecStart={HEDEF}/.venv/bin/python {HEDEF}/main.py --tarayici-yok
Restart=always
RestartSec=5

# Guvenlik siniri: kopru yalniz kendi veri dizinine yazar.
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths={VERI}
PrivateTmp=true

[Install]
WantedBy=multi-user.target
""")

    # --- Uygulama menusu girdisi ---
    # `Type=Application` + xdg-open kullaniliyor; `Type=Link` girdileri
    # GNOME uygulama izgarasinda ARANAMAZ ve bazi ortamlarda hic
    # gorunmez.
    yaz(os.path.join(kok, "usr/share/applications", f"{PAKET_AD}.desktop"), f"""\
[Desktop Entry]
Type=Application
Version=1.0
Name={URUN_GORUNEN_AD}
GenericName=Köprü Yönetim Paneli
Name[en]={URUN_GORUNEN_AD_EN}
Comment={URUN_GORUNEN_AD} yerel yönetim panelini açar
Comment[en]=Opens the {URUN_GORUNEN_AD_EN} local management panel
Exec=xdg-open http://127.0.0.1:{PANEL_PORT}/
Icon={PAKET_AD}
Terminal=false
Categories=Network;Utility;
Keywords=goktungu;goktungu;kopru;bridge;dron;telemetri;
StartupNotify=false
""")

    # --- Belgeler ---
    yaz(os.path.join(kok, "usr/share/doc", PAKET_AD, "README.Debian"), f"""\
GOKTUNGU Kopru {KOPRU_SURUM} — Debian/Ubuntu paketi
================================================

Kurulum dizini : {HEDEF}
Veri dizini    : {VERI}
Servis         : {PAKET_AD}.service (sistem servisi)
Yerel panel    : http://127.0.0.1:{PANEL_PORT}/

Servis yonetimi
---------------
  sudo systemctl status {PAKET_AD}
  sudo systemctl restart {PAKET_AD}
  sudo journalctl -u {PAKET_AD} -f

Ilk adim
--------
Panele girip merkez kullanici adiniz ve sifrenizle oturum acin,
ardindan "Bu bilgisayari merkeze kaydet" dugmesini kullanin.

Seri (USB) telemetri
--------------------
Servis kullanicisi ({SERVIS_KULLANICI}) kurulumda `dialout` grubuna
alinir; ek islem gerekmez.

Kaldirma
--------
  sudo apt remove {PAKET_AD}          # ayarlar korunur
  sudo apt purge {PAKET_AD}           # ayarlar da silinir
""")

    return kok


def denetim_dosyalari(kok, kurulu_boyut):
    """DEBIAN/ denetim dosyalarini yazar."""
    dbn = os.path.join(kok, "DEBIAN")
    os.makedirs(dbn, exist_ok=True)

    # python3-venv: venv olusturmak icin gerekli, python3 ile GELMEZ.
    # Ubuntu'da bu eksikse `python3 -m venv` "ensurepip is not
    # available" ile duser — kurulum sonrasi betigi patlar.
    yaz(os.path.join(dbn, "control"), f"""\
Package: {PAKET_AD}
Version: {KOPRU_SURUM}
Section: net
Priority: optional
Architecture: {MIMARI}
Depends: python3 (>= 3.9), python3-venv, python3-pip, adduser, xdg-utils
Recommends: ffmpeg
Maintainer: {BAKIMCI}
Installed-Size: {kurulu_boyut}
Homepage: https://goktungu.com/
Description: {URUN_KISA_ACIKLAMA}
 GOKTUNGU merkezi komuta kontrol sistemine baglanan kopru yazilimi.
 Yerel bir web yonetim paneli acar; dron, AI, video, GroundGCC ve
 radar servislerini yonetir ve telemetriyi merkeze aktarir.
 .
 Sistem servisi olarak calisir: makine acilisinda kimse oturum
 acmadan baslar. Yonetim paneli http://127.0.0.1:{PANEL_PORT}/
 adresinde acilir.
""")

    # conffiles YAZILMIYOR: ayar dosyalari /etc altinda degil
    # /var/lib/goktungu-kopru icinde tutuluyor. Yanlis conffiles kaydi
    # `apt upgrade` sirasinda kullaniciya gereksiz catisma sorusu
    # sordurur.

    # ---------------- preinst ----------------
    # Yukseltmede servisi ONCE durdur: calisan surec .venv ve kaynak
    # dosyalarini kilitli tutar. Windows tarafinda ayni sira izlendi.
    yaz(os.path.join(dbn, "preinst"), f"""\
#!/bin/sh
set -e

case "$1" in
  upgrade|install)
    if [ -d /run/systemd/system ]; then
      if systemctl is-active --quiet {PAKET_AD}.service 2>/dev/null; then
        echo "Servis durduruluyor (yukseltme)..."
        systemctl stop {PAKET_AD}.service || true
        # Surecin gercekten cikmasini bekle; aksi halde dosyalar
        # kilitli kalir ve dpkg unpack asamasinda hata verir.
        i=0
        while systemctl is-active --quiet {PAKET_AD}.service 2>/dev/null; do
          i=$((i+1)); [ "$i" -ge 10 ] && break
          sleep 1
        done
      fi
    fi
    ;;
esac

exit 0
""", 0o755)

    # ---------------- postinst ----------------
    yaz(os.path.join(dbn, "postinst"), f"""\
#!/bin/sh
set -e

HEDEF="{HEDEF}"
VERI="{VERI}"
KULLANICI="{SERVIS_KULLANICI}"

case "$1" in
  configure)

    # --- 1) Servis kullanicisi ---
    # Sistem kullanicisi: oturum acamaz, ana dizini veri dizinidir.
    if ! getent passwd "$KULLANICI" >/dev/null; then
      adduser --system --group --no-create-home \\
              --home "$VERI" \\
              --shell /usr/sbin/nologin \\
              --gecos "GOKTUNGU Kopru servisi" \\
              "$KULLANICI" >/dev/null
    fi

    # Seri (USB) telemetri icin dialout grubu. Grup yoksa (kapsayici
    # ortamlar) sessizce gecilir.
    if getent group dialout >/dev/null; then
      usermod -aG dialout "$KULLANICI" >/dev/null 2>&1 || true
    fi

    # --- 2) Veri dizini ---
    # Ayarlar ve merkez kimligi burada tutulur; yukseltmede ASLA
    # silinmez, yalniz `purge` ile temizlenir.
    mkdir -p "$VERI"
    chown "$KULLANICI:$KULLANICI" "$VERI"
    chmod 750 "$VERI"

    # Eski surumlerin kullanici dizinindeki kimligini devral.
    # v1.3.0 ve oncesi ~/.config/goktungu-kopru kullaniyordu; devralmadan
    # kullanici merkeze yeniden kayit yapmak zorunda kalir.
    for eski in /root/.config/goktungu-kopru /home/*/.config/goktungu-kopru; do
      if [ -f "$eski/kimlik.json" ] && [ ! -f "$VERI/kimlik.json" ]; then
        cp -a "$eski/." "$VERI/" 2>/dev/null || true
        chown -R "$KULLANICI:$KULLANICI" "$VERI"
        echo "Onceki kurulumun merkez kimligi devralindi: $eski"
        break
      fi
    done

    # --- 3) Python sanal ortami ---
    # Sistem Python'una paket kurmak Ubuntu 23.04+ da
    # "externally-managed-environment" ile reddedilir; venv zorunlu.
    #
    # En YENI uygun surum secilir. Yalniz `python3` kullanmak riskli:
    # dagitimin varsayilani uygulamanin asgarisinin altinda olabilir
    # ve servis her acilista "surum yetersiz" diyerek cikar. Bu kusur
    # gercek kurulumda olculdu (Ubuntu 22.04: python3 = 3.10).
    PY=""
    for aday in python3.13 python3.12 python3.11 python3.10 python3; do
      yol="$(command -v $aday 2>/dev/null || true)"
      [ -n "$yol" ] || continue
      if "$yol" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
        PY="$yol"
        break
      fi
    done
    if [ -z "$PY" ]; then
      echo "HATA: Python 3.10 veya ustu bulunamadi." >&2
      echo "      Kurmak icin: sudo apt install python3" >&2
      exit 1
    fi

    # Yukseltmede eski sanal ortam uygunsuz surumle kurulmus olabilir;
    # surumu dogrula, gerekirse yeniden olustur.
    if [ -x "$HEDEF/.venv/bin/python" ]; then
      if ! "$HEDEF/.venv/bin/python" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
        echo "Mevcut sanal ortam uygunsuz surumde; yenileniyor..."
        rm -rf "$HEDEF/.venv"
      fi
    fi

    if [ ! -x "$HEDEF/.venv/bin/python" ]; then
      echo "Python sanal ortami hazirlaniyor ($PY)..."
      "$PY" -m venv "$HEDEF/.venv"
    fi
    "$HEDEF/.venv/bin/python" -m pip install --quiet --upgrade pip \\
      >/dev/null 2>&1 || true
    echo "Bagimliliklar kuruluyor (websockets, pyserial)..."
    if ! "$HEDEF/.venv/bin/python" -m pip install --quiet \\
         websockets pyserial >/dev/null 2>&1; then
      echo "UYARI: bagimliliklar internetten kurulamadi." >&2
      echo "       Baglanti saglandiktan sonra su komutu calistirin:" >&2
      echo "       sudo $HEDEF/.venv/bin/python -m pip install websockets pyserial" >&2
    fi
    # 1.7.20 — YEREL AI ISCISI icin numpy + OpenCV.
    #
    # AYRI BIR ADIM OLMASININ NEDENI: bu iki paket ~100 MB indirir ve
    # cekirdek kopru islevleri (dron/radar/GCCDUAL/video aktarimi) bunlara
    # BAGLI DEGILDIR. Ayni komuta konsalardi, yavas veya olcumlu baglantida
    # tek bir zaman asimi butun bagimlilik kurulumunu dusurur ve kopru
    # calismaz halde kalirdi. Basarisizlik BURADA olumcul degildir:
    # `servis_ai` yerel isciyi baslatamayinca uyari yazip uzak AI
    # bilgisayarlariyla devam eder.
    echo "Yerel AI bagimliliklari kuruluyor (numpy, opencv)..."
    if ! "$HEDEF/.venv/bin/python" -m pip install --quiet \\
         numpy opencv-python-headless >/dev/null 2>&1; then
      echo "BILGI: yerel AI bagimliliklari kurulamadi; goruntu cozumlemesi" >&2
      echo "       ayri bir AI bilgisayari gerektirecek. Sonradan kurmak icin:" >&2
      echo "       sudo $HEDEF/.venv/bin/python -m pip install numpy opencv-python-headless" >&2
    fi
    chown -R root:root "$HEDEF"
    chmod -R go-w "$HEDEF"

    # --- 4) Ikon onbellegi ve masaustu veritabani ---
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
      gtk-update-icon-cache -f -t /usr/share/icons/hicolor \\
        >/dev/null 2>&1 || true
    fi
    if command -v update-desktop-database >/dev/null 2>&1; then
      update-desktop-database /usr/share/applications \\
        >/dev/null 2>&1 || true
    fi

    # --- 4b) ESKI KULLANICI SERVISI KALINTISI ---
    # v1.3.x oncesi `kur.sh` ayni adi (goktungu-kopru) KULLANICI servisi
    # olarak ~/.config/systemd/user/ altina kuruyordu. Yeni paket ise
    # SISTEM servisi kurar. Ikisi birlikte kalirsa:
    #   - iki surec ayni panel portuna (8790) girer, ikincisi coker
    #   - `systemctl status goktungu-kopru` (sistem) ile
    #     `systemctl --user status goktungu-kopru` ayri seyler oldugu icin
    #     kullanici hangisinin calistigini anlayamaz
    # Bu yuzden eski KULLANICI servisi durdurulur ve devre disi
    # birakilir. Birim dosyasi silinmez, `.devredisi` uzantisiyla
    # saklanir: geri donus gerekirse elde kalsin.
    for ev in /root /home/*; do
      [ -d "$ev" ] || continue
      birim="$ev/.config/systemd/user/{PAKET_AD}.service"
      [ -f "$birim" ] || continue
      sahip="$(stat -c %U "$ev" 2>/dev/null || true)"
      [ -n "$sahip" ] || continue
      uid="$(id -u "$sahip" 2>/dev/null || true)"
      if [ -n "$uid" ] && [ -d /run/user/"$uid" ]; then
        su - "$sahip" -c \
          "XDG_RUNTIME_DIR=/run/user/$uid systemctl --user disable --now {PAKET_AD}.service" \
          >/dev/null 2>&1 || true
      fi
      mv "$birim" "$birim.devredisi" 2>/dev/null || true
      echo "Eski kullanici servisi devre disi birakildi: $birim"
      echo "  (artik SISTEM servisi kullaniliyor: systemctl status {PAKET_AD})"
    done

    # --- 5) Masaustu kisayollari ---
    # Her gercek kullanicinin masaustune kopyalanir. Masaustu dizin
    # adi yerelleseriktir ("Masaüstü", "Desktop"); ikisi de denenir.
    KAYNAK="/usr/share/applications/{PAKET_AD}.desktop"
    if [ -f "$KAYNAK" ]; then
      for ev in /home/*; do
        [ -d "$ev" ] || continue
        sahip="$(stat -c %U "$ev" 2>/dev/null || true)"
        [ -n "$sahip" ] || continue
        getent passwd "$sahip" >/dev/null || continue
        for ad in "Masaüstü" "Desktop"; do
          if [ -d "$ev/$ad" ]; then
            cp "$KAYNAK" "$ev/$ad/{PAKET_AD}.desktop" 2>/dev/null || true
            chown "$sahip" "$ev/$ad/{PAKET_AD}.desktop" 2>/dev/null || true
            chmod +x "$ev/$ad/{PAKET_AD}.desktop" 2>/dev/null || true
            break
          fi
        done
      done
    fi

    ;;
esac

#DEBHELPER#

exit 0
""", 0o755)

    # ---------------- postinst: systemd etkinlestirme ----------------
    # deb-systemd-helper varsa onu kullan (dpkg-triggers ile uyumlu),
    # yoksa dogrudan systemctl. Ikisi de yoksa (kapsayici) sessiz gec.
    postinst = os.path.join(dbn, "postinst")
    with open(postinst, encoding="utf-8") as f:
        icerik = f.read()
    icerik = icerik.replace("#DEBHELPER#", f"""\
# --- 6) Servisi etkinlestir ve baslat ---
#
# NEDEN `|| true` KALDIRILDI: onceki surumde `enable` ve `restart`
# hatalari yutuluyordu. Eski kurulumdan kalan bozuk bir birim dosyasi
# ya da maskelenmis servis varsa kurulum "basarili" gorunuyor, ancak
# servis hic olusmuyordu. Kullanici "kurdum ama servis yok" diyor ve
# elinde hicbir gerekce olmuyordu. Artik her adim raporlanir.
if [ -d /run/systemd/system ]; then
  systemctl daemon-reload || true

  # Maskelenmis servis `enable`/`start` komutlarini sessizce reddeder.
  if [ "$(systemctl is-enabled {PAKET_AD}.service 2>/dev/null)" = "masked" ]; then
    echo "Servis maskelenmis; maske kaldiriliyor."
    systemctl unmask {PAKET_AD}.service >/dev/null 2>&1 || true
  fi

  if ! systemctl enable {PAKET_AD}.service >/dev/null 2>&1; then
    echo "UYARI: servis acilista baslayacak sekilde ayarlanamadi." >&2
    echo "       Elle: sudo systemctl enable {PAKET_AD}" >&2
  fi

  if systemctl restart {PAKET_AD}.service 2>/dev/null; then
    sleep 2
  else
    echo "UYARI: servis baslatma komutu basarisiz." >&2
  fi

  if systemctl is-active --quiet {PAKET_AD}.service; then
    echo ""
    echo "GOKTUNGU Kopru {KOPRU_SURUM} kuruldu ve calisiyor."
    echo ""
    # Panel artik 0.0.0.0'a baglanir; gercek erisim adresleri yazilir.
    # Onceki surum kosulsuz 127.0.0.1 yaziyordu, oysa saha makinesi
    # genellikle ekransizdir ve kullanici baska bir bilgisayardan
    # baglanir; hangi adresi yazacagini bilemiyordu.
    echo "  Panel (bu makinede) : http://127.0.0.1:{PANEL_PORT}/"
    for ip in $(hostname -I 2>/dev/null || true); do
      case "$ip" in
        127.*|169.254.*|*:*) continue ;;
      esac
      echo "  Panel (agdan)       : http://$ip:{PANEL_PORT}/"
    done
    echo ""
    echo "  Durum : systemctl status {PAKET_AD}"
    echo "  Tani  : sudo {HEDEF}/tani_sifirla.sh"
    echo ""
    if command -v ufw >/dev/null 2>&1 \
       && ufw status 2>/dev/null | grep -q "^Status: active"; then
      if ! ufw status 2>/dev/null | grep -q "{PANEL_PORT}"; then
        echo "  Guvenlik duvari etkin. Panele agdan erismek icin"
        echo "  YALNIZ yerel aginiza izin verin, ornegin:"
        echo "    sudo ufw allow from 192.168.0.0/16 to any port {PANEL_PORT} proto tcp"
        echo ""
      fi
    fi
  else
    echo "" >&2
    echo "HATA: servis kuruldu ama BASLATILAMADI." >&2
    echo "Gunluk (son 20 satir):" >&2
    journalctl -u {PAKET_AD} --no-pager -n 20 >&2 || true
    echo "" >&2
    echo "Tani icin: sudo {HEDEF}/tani_sifirla.sh" >&2
    echo "Temiz kurulum icin: sudo {HEDEF}/tani_sifirla.sh --sifirla" >&2
    echo "" >&2
  fi
else
  echo "systemd bulunamadi; servis elle baslatilmali." >&2
fi""")
    yaz(postinst, icerik, 0o755)

    # ---------------- prerm ----------------
    yaz(os.path.join(dbn, "prerm"), f"""\
#!/bin/sh
set -e

case "$1" in
  remove|deconfigure)
    if [ -d /run/systemd/system ]; then
      systemctl stop {PAKET_AD}.service || true
      systemctl disable {PAKET_AD}.service >/dev/null 2>&1 || true
    fi
    ;;
  upgrade)
    # Yukseltmede preinst zaten durdurdu; burada bir sey yapilmaz.
    ;;
esac

exit 0
""", 0o755)

    # ---------------- postrm ----------------
    # .venv ve __pycache__ dpkg'nin dosya listesinde YOKTUR (kurulum
    # sonrasi olusur). Acikca silinmezlerse /opt/goktungu/kopru dizini bos
    # kalmaz ve dpkg onu kaldiramaz — kaldirmadan sonra artik kalir.
    yaz(os.path.join(dbn, "postrm"), f"""\
#!/bin/sh
set -e

HEDEF="{HEDEF}"
VERI="{VERI}"

case "$1" in
  remove)
    rm -rf "$HEDEF/.venv"
    find "$HEDEF" -name __pycache__ -type d -exec rm -rf {{}} + 2>/dev/null || true
    rmdir "$HEDEF" 2>/dev/null || true
    rmdir /opt/goktungu 2>/dev/null || true

    # Masaustu kisayollarini temizle
    for ev in /home/*; do
      for ad in "Masaüstü" "Desktop"; do
        rm -f "$ev/$ad/{PAKET_AD}.desktop" 2>/dev/null || true
      done
    done

    echo "Ayarlar korundu: $VERI"
    echo "Tamamen silmek icin: sudo apt purge {PAKET_AD}"

    if [ -d /run/systemd/system ]; then
      systemctl daemon-reload || true
    fi
    if command -v update-desktop-database >/dev/null 2>&1; then
      update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
    fi
    ;;

  purge)
    rm -rf "$HEDEF" "$VERI"
    rmdir /opt/goktungu 2>/dev/null || true
    if getent passwd {SERVIS_KULLANICI} >/dev/null; then
      deluser --system {SERVIS_KULLANICI} >/dev/null 2>&1 || true
    fi
    if [ -d /run/systemd/system ]; then
      systemctl daemon-reload || true
    fi
    ;;
esac

exit 0
""", 0o755)

    # md5sums: `dpkg -V` ile butunluk denetimi icin
    satirlar = []
    for kokd, _, dosyalar in os.walk(kok):
        if "DEBIAN" in kokd:
            continue
        for d in sorted(dosyalar):
            tam = os.path.join(kokd, d)
            bagil = os.path.relpath(tam, kok)
            with open(tam, "rb") as f:
                ozet = hashlib.md5(f.read()).hexdigest()
            satirlar.append(f"{ozet}  {bagil}")
    yaz(os.path.join(dbn, "md5sums"), "\n".join(satirlar) + "\n")


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(
        description="GOKTUNGU Kopru .deb paketi ureteci")
    # `--urun` VERILMEZSE brdimg (varsayilan) ve cikti onceki surumlerle
    # BYTE-AYNI kalir. `--urun brdtlm` telemetri/cihaz koprusu paketini
    # (goktungu-kopru-tlm) uretir.
    ap.add_argument("--urun", default="brdimg",
                    choices=sorted(URUN_TANIMLARI),
                    help="Uretilecek urun paketi (varsayilan: brdimg)")
    a = ap.parse_args(argv)   # argv None ise sys.argv[1:] kullanilir
    urun_uygula(a.urun)

    calisma = os.path.join(KOK, "dagitim", "deb_calisma")
    os.makedirs(calisma, exist_ok=True)

    print("=" * 68)
    print(f"GOKTUNGU {PAKET_AD} {KOPRU_SURUM} — .deb paketi uretiliyor")
    print("=" * 68)

    kok = kur_agaci(calisma)

    # Kurulu boyut (KB) — Program Ekle/Kaldir karsiligi listede gorunur
    toplam = 0
    for k, _, ds in os.walk(kok):
        for d in ds:
            toplam += os.path.getsize(os.path.join(k, d))
    kurulu_kb = max(1, toplam // 1024)

    denetim_dosyalari(kok, kurulu_kb)

    # Dosya sahipligi: .deb icinde her sey root:root olmali
    cikti = os.path.join(
        KOK, "dagitim", f"{PAKET_AD}_{KOPRU_SURUM}_{MIMARI}.deb")
    if os.path.exists(cikti):
        os.remove(cikti)

    r = subprocess.run(
        ["dpkg-deb", "--root-owner-group", "--build", kok, cikti],
        capture_output=True, text=True)
    if r.returncode != 0:
        print("HATA: dpkg-deb basarisiz")
        print(r.stdout)
        print(r.stderr)
        return 1

    boyut = os.path.getsize(cikti)
    print(f"\n[OK] {os.path.basename(cikti)}  ({boyut // 1024} KB)")

    # --- Sinav: paket gecerli mi ---
    print("\n--- paket denetimi ---")
    gecen = kalan = 0

    def d(baslik, kosul, neden=""):
        nonlocal gecen, kalan
        if kosul:
            gecen += 1
            print(f"  [GECTI] {baslik}")
        else:
            kalan += 1
            print(f"  [KALDI] {baslik}" + (f" — {neden}" if neden else ""))

    r = subprocess.run(["dpkg-deb", "--info", cikti],
                       capture_output=True, text=True)
    bilgi = r.stdout
    d("paket okunabilir", r.returncode == 0)
    d("surum dogru", f"Version: {KOPRU_SURUM}" in bilgi)
    d("python3-venv bagimliligi",
      "python3-venv" in bilgi,
      "venv olusturulamaz, postinst duser")

    r = subprocess.run(["dpkg-deb", "--contents", cikti],
                       capture_output=True, text=True)
    icerik = r.stdout
    _hedef_ic = "./%s" % HEDEF.lstrip("/")
    d("uygulama %s altinda" % HEDEF,
      ("%s/main.py" % _hedef_ic) in icerik)
    # Yerel AI iscisi: eksikligi sessiz kalir (kurulum basarili gorunur),
    # bu yuzden pakette oldugu BURADA olculur.
    d("yerel AI iscisi var",
      ("%s/ai_sunucu.py" % _hedef_ic) in icerik,
      "ayri AI donanimi olmayan sahada AI hic calismaz")
    d("systemd birimi var",
      f"./lib/systemd/system/{PAKET_AD}.service" in icerik)
    d("masaustu girdisi var",
      f"./usr/share/applications/{PAKET_AD}.desktop" in icerik)
    d("ikonlar var", "./usr/share/icons/hicolor/48x48/apps/" in icerik)
    d("sinav betikleri paketE GIRMEMIS",
      "sinav_" not in icerik,
      "gelistirme dosyalari dagitima girmis")
    d("Windows dosyalari paketE GIRMEMIS",
      "setup.nsi" not in icerik and "servis_win.py" not in icerik)

    # Bakim betikleri kabuk sozdizimi denetimi: bozuk bir postinst
    # kurulumu yarida birakir ve paketi "yapilandirilmamis" durumda
    # bosta bekletir.
    for b in ("preinst", "postinst", "prerm", "postrm"):
        yol = os.path.join(kok, "DEBIAN", b)
        r = subprocess.run(["sh", "-n", yol], capture_output=True, text=True)
        d(f"{b} sozdizimi", r.returncode == 0, r.stderr.strip())

    # lintian varsa calistir (uyari verirse engellemez)
    if shutil.which("lintian"):
        r = subprocess.run(["lintian", "--no-tag-display-limit", cikti],
                           capture_output=True, text=True)
        hatalar = [s for s in r.stdout.splitlines() if s.startswith("E:")]
        d("lintian hatasi yok", not hatalar,
          "; ".join(hatalar[:3]) if hatalar else "")

    print(f"\nSONUC: {gecen} gecti / {kalan} kaldi")
    return 1 if kalan else 0


if __name__ == "__main__":
    sys.exit(main())
