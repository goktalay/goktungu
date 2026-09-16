#!/usr/bin/env python3.11
"""
GOKTUNGU MERKEZ UYGULAMASI — Debian/Ubuntu paketi (.deb) ureteci
==============================================================

Kullanici istegi: "bunun icin Ubuntu ve windows icin setup
olusturacaksin. ayni kopruede oldugu gibi."

Windows tarafiyla ESLENIK tasarim:

| Ozellik | Windows (setup.exe) | Ubuntu (.deb) |
|---|---|---|
| Kurulum yeri | C:\\Program Files\\Goktungu\\Merkez | /opt/goktungu/merkez |
| Servis | SCM servisi (LocalSystem) | systemd sistem servisi (goktungu-merkez) |
| Veri | C:\\ProgramData\\Goktungu\\Merkez | /var/lib/goktungu-merkez |
| Lisans | ...\\ProgramData\\...\\merkez_lisans.json | /var/lib/goktungu-merkez/merkez_lisans.json |
| Kaldirma | Program Ekle/Kaldir | apt remove |

## KOPRU PAKETINDEN FARKLAR (goktungu_kopru/deb_uret.py ile karsilastirma)

1. **Bagimliliklar agir**: psycopg2, opencv, numpy, pymavlink.
   Kopru yalniz websockets+pyserial kuruyordu. Sistem paketleri
   (python3-opencv, python3-psycopg2) TERCIH EDILIR: venv icine pip ile
   opencv kurmak 60+ MB indirme ve derleme riski demektir.

2. **`assets/` yapisi**: uygulama `main.py` + `assets/{web,python}`
   duzeninde dagitilir. Kopru duz `kopru/` + `web/` kullaniyordu.

3. **PostgreSQL**: paket PostgreSQL'i KURMAZ, yalniz `Recommends` ile
   onerir. Kullanici kendi sunucusunu kullanabilir (uzak sunucu da
   olabilir) ve ilk acilista sihirbaz sorar.

4. **Veri dizini ortam degiskeniyle** verilir (`GOKTUNGU_VERI_KOKU`);
   kopru bunu kendi ayar modulunde cozuyordu.

5. **Port kaydirma**: kopru ile ayni makinede calisabilmek icin
   `GOKTUNGU_VIDEO_PORT=8811`, `GOKTUNGU_AI_PORT=8910`.

## Neden PostgreSQL bir bagimlilik DEGIL

Kullanici istegi: "sistemi ilk actigimda bana sunucu bilgilerini
sorsun, ip adresi, kullanici adi, sifresi, veritabani adi". Yani
veritabani UZAKTA olabilir. `Depends: postgresql` yazmak her kuruluma
gereksiz bir sunucu kurar; `Recommends` dogru siniftir.
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys

KOK = os.path.dirname(os.path.abspath(__file__))

PAKET_AD = "goktungu-merkez"
MIMARI = "all"
# Dağıtım sürümü Windows Merkez kurucusuyla eşit kalır. Gömülü web/uygulama
# sürümü ayrı bir uyumluluk kimliğidir; tek bir alanın ikisini birden temsil
# etmesi geçmişte Windows-Linux paket karışıklığına neden olmuştur.
def _paket_surum_oku(ad: str) -> str:
    """Surum alanini goktungu/paket_surum.py'den okur (TEK KAYNAK).

    Paket ice ALINMAZ (goktungu/__init__ calisma zamani yan etkileri);
    satir duzenli ifadeyle okunur.
    """
    yol = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "goktungu", "paket_surum.py")
    with open(yol, encoding="utf-8") as f:
        m = re.search(r'^' + ad + r'\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"',
                      f.read(), re.M)
    if not m:
        raise SystemExit("HATA: goktungu/paket_surum.py icinde %s yok" % ad)
    return m.group(1)


PAKET_SURUM = _paket_surum_oku("PAKET_SURUM")
UYGULAMA_SURUM = _paket_surum_oku("UYGULAMA_SURUM")
BAKIMCI = "Turkbey Teknoloji Anonim Sirketi <destek@gokkubbetech.com>"
HEDEF = "/opt/goktungu/merkez"
VERI = "/var/lib/goktungu-merkez"
SERVIS_KULLANICI = "goktungu-merkez"
HTTP_PORT = 8000

# Kopru ile cakisan portlarin kaydirilmis degerleri (OLCULDU:
# OLCUM_PORT_CAKISMASI.md). Kopru varsayilanda kalir.
VIDEO_PORT = 8811
AI_PORT = 8910


def uygulama_surumu_oku():
    """Gömülü uygulama sürümünü js/surum.js tek kaynağından okur."""
    yol = os.path.join(KOK, "js", "surum.js")
    with open(yol, encoding="utf-8") as f:
        metin = f.read()
    m = re.search(r'GCS_SURUM\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"', metin)
    if not m:
        raise RuntimeError("js/surum.js icinde GCS_SURUM bulunamadi")
    return m.group(1)


def surum_oku():
    """Dağıtım sürümünü döndürür ve gömülü uygulama sürümünü doğrular.

    Paket sürümü Merkez kurucusunun sürümüdür; GCS_SURUM ise gömülü web
    uygulamasının uyumluluk kimliğidir. İkisi bilinçli olarak ayrı tutulur
    ancak uygulama sürümü sabit denetiminden geçmeden paket üretilemez.
    """
    uygulama = uygulama_surumu_oku()
    if uygulama != UYGULAMA_SURUM:
        raise RuntimeError(
            f"GCS_SURUM={uygulama}; beklenen uygulama sürümü "
            f"{UYGULAMA_SURUM}")
    return PAKET_SURUM


def _gomulu_sifre_olc(kaynak, ad):
    """Kaynakta GERCEK kod sabiti olarak gomulu sifre arar.

    Duz metin aramasi kullanilamaz: dosyanin aciklama bloklari kusurun
    ne oldugunu anlatirken eski sifreyi ornek olarak anar ve bu kayit
    bilincli olarak korunur.  AST'te docstring'ler ifade olarak durdugu
    icin ayrica ayiklanir.
    """
    import ast

    yasakli = ("gokkubbe2026",)
    try:
        agac = ast.parse(kaynak)
    except SyntaxError as e:
        return [f"{ad} cozulemedi (sozdizimi): {e}"]

    # Docstring dugumlerini isaretle; bunlar aciklamadir, kod degil.
    dok = set()
    for d in ast.walk(agac):
        if isinstance(d, (ast.Module, ast.FunctionDef,
                          ast.AsyncFunctionDef, ast.ClassDef)):
            g = getattr(d, "body", None)
            if (g and isinstance(g[0], ast.Expr)
                    and isinstance(g[0].value, ast.Constant)
                    and isinstance(g[0].value.value, str)):
                dok.add(id(g[0].value))

    bulunan = []
    for d in ast.walk(agac):
        if (isinstance(d, ast.Constant) and isinstance(d.value, str)
                and id(d) not in dok):
            for y in yasakli:
                if y in d.value:
                    bulunan.append(
                        f"{ad}:{getattr(d, 'lineno', '?')} GOMULU sifre "
                        f"kod sabiti olarak var ({y})")
    return bulunan


def agac_tazelik_olc(agac, surum):
    """Paket agacinin GERCEKTEN `surum` icerigini tasidigini olcer.

    Etiket ile icerigin ayrismasi olculmus bir kusurdur (bkz. main()
    icindeki OLCULEN KUSUR notu): 2.4.66 etiketli, 2.4.65 icerikli bir
    .deb uretildi ve yapisal sinav bunu "gecti" saydi.  Burada surum
    etiketinin yaninda v2.4.66'da eklenen SOMUT dosya ve davranislar da
    aranir; boylece "etiketi elle degistir, gerisi bayat kalsin"
    durumu yakalanir.

    Eksiklerin listesini doner; bos liste = agac taze.
    """
    eksik = []
    py = os.path.join(agac, "assets", "python", "goktungu")
    web = os.path.join(agac, "assets", "web", "js")

    def oku(*p):
        y = os.path.join(*p)
        if not os.path.isfile(y):
            return None
        with open(y, encoding="utf-8", errors="replace") as f:
            return f.read()

    # 1) Surum etiketi iki bagimsiz yerde tutulur; ikisi de uyusmali.
    s_js = oku(web, "surum.js")
    if s_js is None:
        eksik.append("assets/web/js/surum.js yok")
    else:
        m = re.search(r'GCS_SURUM\s*=\s*"([0-9.]+)"', s_js)
        if not m:
            eksik.append("surum.js icinde GCS_SURUM bulunamadi")
        elif m.group(1) != surum:
            eksik.append(
                f"surum.js GCS_SURUM={m.group(1)} (beklenen {surum})")

    s_init = oku(py, "__init__.py")
    if s_init is None:
        eksik.append("assets/python/goktungu/__init__.py yok")
    else:
        m = re.search(r'_SON_BILINEN\s*=\s*"([0-9.]+)"', s_init)
        if m and m.group(1) != surum:
            eksik.append(
                f"__init__.py _SON_BILINEN={m.group(1)} (beklenen {surum})")

    # 2) Surume ozgu SOMUT icerik olcutleri.  Yalniz 2.4.66 ve sonrasi
    #    icin gecerli; daha eski bir surum bilincli uretiliyorsa
    #    atlanir.
    try:
        yeni = tuple(int(x) for x in surum.split(".")) >= (2, 4, 66)
    except ValueError:
        yeni = False
    if yeni:
        if not os.path.isfile(os.path.join(py, "merkez_esitle.py")):
            eksik.append("merkez_esitle.py agacta yok (v2.4.66 modulu)")

        vt = oku(py, "veritabani.py") or ""
        if "pbkdf2_sha256" not in vt:
            eksik.append("veritabani.py merkez sifre bicimini tanimiyor")

        # DIKKAT: duz metin aramasi YANLIS sonuc verir.  Dosyanin
        # aciklama bloklari kusurun ne oldugunu ANLATIR ve eski sifreyi
        # ornek olarak anar; bu kayit degerlidir, silinmemelidir.
        # Bu yuzden kaynak AST olarak cozulur ve dize yalnizca GERCEK
        # bir kod sabiti (aciklama/dokumantasyon disi) olarak
        # goruldugunde kusur sayilir.
        kl = oku(py, "kullanicilar.py") or ""
        if kl:
            eksik += _gomulu_sifre_olc(kl, "kullanicilar.py")

        sn = oku(py, "sunucu.py") or ""
        if "_merkez_panel_adresi" not in sn:
            eksik.append("sunucu.py /company/ yonlendirmesini tasimiyor")

        sh = oku(web, "pg_sihirbaz.js") or ""
        if "merkez_esitle" not in sh:
            eksik.append("pg_sihirbaz.js kullanici esitleme adimini tasimiyor")

        # Betaflight 2.4.143: paket, serbest bir MSP yazma katmani degil,
        # yalniz izin-listeli salt-okunur sorgu sürücüsünü taşımalıdır.
        msp = oku(py, "betaflight_msp.py")
        if not msp:
            eksik.append("betaflight_msp.py agacta yok")
        elif ("IZINLI_SORGU_KOMUTLARI" not in msp
              or "def msp_v1_sorgu" not in msp
              or "PermissionError" not in msp):
            eksik.append("betaflight_msp.py salt-okunur izin listesi eksik")

        # RFD900 otomatik algilama yalniz seri portta, once pasif MAVLink
        # HEARTBEAT sonra en fazla bir MSP API_VERSION sorgusuyla calisir.
        # Paket bu modulsuz uretilemez; aksi halde arayuz secenegi sessizce
        # etkisiz kalir.
        alg = oku(py, "protokol_algilama.py")
        if not alg:
            eksik.append("protokol_algilama.py agacta yok")
        elif ("_MAVLINK_HEARTBEAT" not in alg
              or "MSP_API_VERSION" not in alg
              or "def seri_protokol_algila" not in alg):
            eksik.append("protokol_algilama.py RFD900 algilama siniri eksik")

    return eksik


def yaz(yol, icerik, kip=0o644):
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8", newline="\n") as f:
        f.write(icerik)
    os.chmod(yol, kip)


def kur_agaci(calisma, agac_kaynak, surum):
    """Paket dosya agacini olusturur.

    `agac_kaynak`: paketle_merkez.py'nin urettigi hazir agac
    (main.py + assets/). Ikinci bir beyaz liste yazmak yerine onun
    ciktisi kullanilir; boylece iki yerde ayri liste tutulmaz ve
    biri guncellenmeyi unutuldugunda paketler ayrisMAZ.
    """
    kok = os.path.join(calisma, PAKET_AD)
    if os.path.isdir(kok):
        shutil.rmtree(kok)

    # --- /opt/goktungu/merkez: uygulama ---
    hedef = os.path.join(kok, HEDEF.lstrip("/"))
    os.makedirs(hedef, exist_ok=True)

    for ad in sorted(os.listdir(agac_kaynak)):
        k = os.path.join(agac_kaynak, ad)
        h = os.path.join(hedef, ad)
        if os.path.isdir(k):
            shutil.copytree(k, h, ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc"))
        else:
            shutil.copy2(k, h)

    # --- v2.4.216: M50 SDK Wine koprusu icin gomulu Windows Python ---
    # Linux'ta ureticinin Windows DLL'i wine64 altinda bu yorumlayiciyla
    # kosar (goktungu/m50_wine.py). Zip veri kokune ilk kullanimda acilir.
    _embed = os.path.join(KOK, "gomulu_merkez", "python-3.11.9-embed-amd64.zip")
    if os.path.isfile(_embed):
        os.makedirs(os.path.join(hedef, "wine"), exist_ok=True)
        shutil.copy2(_embed, os.path.join(hedef, "wine", "python-3.11.9-embed-amd64.zip"))
    else:
        print("[UYARI] gomulu Windows Python zip'i yok; Wine koprusu paketten cikacak")

    # --- Ikonlar: hicolor temasina (kopru paketinden devralinir) ---
    # Kopru calisma dizini adi gecis sirasinda degisebilir; iki adayi da
    # dene. Tek ada baglanmak sessiz atlamaya yol aciyordu: yol yoksa
    # `os.path.isdir` False doner, blok atlanir ve paket IKONSUZ uretilir
    # (hicbir hata verilmez).
    ikon_kaynak = None
    # CI/ayrılmış çalışma alanında köprü kaynak ağacı paket kökünün yanında
    # olmayabilir. Açıkça verilen ortam yolu önce gelir; ardından kullanıcının
    # standart geliştirme kökü ve eski göreli düzen denenir.
    _ikon_adaylari = []
    _acik_kopru = os.environ.get("GOKTUNGU_KOPRU_KAYNAK", "").strip()
    if _acik_kopru:
        _ikon_adaylari.append(os.path.join(_acik_kopru, "varliklar", "hicolor"))
    _ikon_adaylari.append(os.path.expanduser(
        "~/goktungu_kopru/varliklar/hicolor"))
    _ikon_adaylari.append(os.path.abspath(os.path.join(
        os.path.dirname(KOK), "..", "goktungu_kopru", "varliklar", "hicolor")))
    for _y in _ikon_adaylari:
        if os.path.isdir(_y):
            ikon_kaynak = _y
            break
    if ikon_kaynak is None:
        raise SystemExit(
            "KUSUR: kopru ikon dizini bulunamadi. Merkez paketi ikonlarini "
            "kopru kaynagindan devralir; yol yoksa paket ikonsuz uretilir. "
            "Aranan: ~/goktungu_kopru altinda "
            "varliklar/hicolor")
    if True:
        ikon_hedef = os.path.join(kok, "usr/share/icons/hicolor")
        # Kopru ikonlari `goktungu-kopru.png` adiyla gelir; merkez paketi
        # kendi adini kullanmak zorundadir yoksa iki paket ayni dosyayi
        # sahiplenir ve `dpkg` catisma bildirir.
        for kokd, _, dosyalar in os.walk(ikon_kaynak):
            for d in dosyalar:
                if not d.startswith("goktungu-kopru"):
                    continue
                bagil = os.path.relpath(os.path.join(kokd, d), ikon_kaynak)
                yeni_ad = d.replace("goktungu-kopru", PAKET_AD)
                hy = os.path.join(ikon_hedef,
                                  os.path.dirname(bagil), yeni_ad)
                os.makedirs(os.path.dirname(hy), exist_ok=True)
                shutil.copy2(os.path.join(kokd, d), hy)

    # --- systemd sistem servisi ---
    #
    # StartLimitBurst/StartLimitIntervalSec [Unit] bolumune AITTIR.
    # [Service] altina yazilirsa systemd "Unknown key name" diyerek
    # SESSIZCE yok sayar (kopru kurulumunda gercek systemd ile olculdu).
    #
    # ProtectSystem=strict + ReadWritePaths: uygulama yalniz kendi veri
    # dizinine yazar. Kopru ile ayni siniflandirma.
    yaz(os.path.join(kok, "lib/systemd/system", f"{PAKET_AD}.service"), f"""\
[Unit]
Description=GOKTUNGU Merkez Uygulamasi
Documentation=https://goktungu.com/
After=network-online.target postgresql.service
Wants=network-online.target
StartLimitBurst=10
StartLimitIntervalSec=300

[Service]
Type=simple
User={SERVIS_KULLANICI}
Group={SERVIS_KULLANICI}
WorkingDirectory={HEDEF}
# Veri koku: /opt altina yazmak ProtectSystem=strict ile engellidir
# ve dogru da degildir (paket dizini yalniz-okunur olmalidir).
Environment=GOKTUNGU_VERI_KOKU={VERI}
# Kopru ile AYNI MAKINEDE calisabilmek icin cakisan portlar kaydirilir.
# Olculen cakisma: MJPEG vekili 8801, AI iscisi 8900.
Environment=GOKTUNGU_VIDEO_PORT={VIDEO_PORT}
Environment=GOKTUNGU_AI_PORT={AI_PORT}
# --tarayici-yok: servis kipinde tarayici acmak anlamsizdir; grafik
# oturum olmayabilir ve tarayici acma cagrisi saniyelerce bloke olur.
ExecStart={HEDEF}/.venv/bin/python {HEDEF}/goktungu_guncelleyici.py
Restart=always
RestartSec=5

NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
# v2.4.218: uygulama ici guncelleme kurulum dizinine yazar (bkz. postinst chown)
ReadWritePaths={VERI} {HEDEF}
PrivateTmp=true

[Install]
WantedBy=multi-user.target
""")

    # --- Uygulama menusu girdisi ---
    yaz(os.path.join(kok, "usr/share/applications", f"{PAKET_AD}.desktop"), f"""\
[Desktop Entry]
Type=Application
Version=1.0
Name=GÖKTUNGU Merkez
GenericName=Yer Kontrol İstasyonu
Name[en]=GOKTUNGU Center
Comment=GÖKTUNGU Merkez Uygulaması arayüzünü açar
Comment[en]=Opens the GOKTUNGU Center Application interface
Exec=xdg-open http://127.0.0.1:{HTTP_PORT}/
Icon={PAKET_AD}
Terminal=false
Categories=Network;Science;Utility;
Keywords=goktungu;merkez;gcs;dron;telemetri;radar;
StartupNotify=false
""")

    # --- Belgeler ---
    yaz(os.path.join(kok, "usr/share/doc", PAKET_AD, "README.Debian"), f"""\
GOKTUNGU Merkez Uygulamasi {surum} — Debian/Ubuntu paketi
======================================================

Kurulum dizini : {HEDEF}
Veri dizini    : {VERI}
Servis         : {PAKET_AD}.service (sistem servisi)
Arayuz         : http://127.0.0.1:{HTTP_PORT}/

ILK ADIM — VERITABANI
---------------------
Arayuze ilk girdiginizde PostgreSQL kurulum sihirbazi acilir.
Sunucu adresi, kullanici adi, sifre ve veritabani adini girin;
tablolar otomatik olusturulur.

Veritabani UZAK bir sunucuda da olabilir. Yerel bir sunucu
kullanacaksaniz:

  sudo apt install postgresql postgresql-contrib
  sudo -u postgres createuser --pwprompt goktungu
  sudo -u postgres createdb -O goktungu goktungu

ILK ADIM — LISANS
-----------------
Kurumsal panelinizden (https://goktungu.com/company/)
indirdiginiz `merkez_lisans.json` dosyasini su dizine kopyalayin:

  sudo cp merkez_lisans.json {VERI}/
  sudo chown {SERVIS_KULLANICI}:{SERVIS_KULLANICI} {VERI}/merkez_lisans.json
  sudo systemctl restart {PAKET_AD}

Lisans dosyasi Ed25519 ile imzalanmistir ve INTERNET BAGLANTISI
OLMADAN dogrulanir; kapali devre kurulumda da calisir.

KOPRU ILE AYNI MAKINEDE CALISTIRMA
----------------------------------
Desteklenir. Cakisan portlar bu paketde kaydirilmistir:

  MJPEG vekili : {VIDEO_PORT}  (kopru 8801'de kalir)
  AI iscisi    : {AI_PORT}  (kopru 8900'de kalir)

Servis yonetimi
---------------
  sudo systemctl status {PAKET_AD}
  sudo systemctl restart {PAKET_AD}
  sudo journalctl -u {PAKET_AD} -f

Kaldirma
--------
  sudo apt remove {PAKET_AD}    # veritabani ayarlari ve LISANS korunur
  sudo apt purge {PAKET_AD}     # veri dizini de silinir
""")

    return kok


def denetim_dosyalari(kok, kurulu_boyut, surum):
    """DEBIAN/ denetim dosyalarini yazar."""
    dbn = os.path.join(kok, "DEBIAN")
    os.makedirs(dbn, exist_ok=True)

    # Sistem paketleri Depends'e alinir: venv icine pip ile opencv
    # kurmak 60+ MB indirme ve uzun derleme demektir; ayrica kapali
    # devre kurulumda internet olmayabilir. `--system-site-packages`
    # ile venv bunlari gorur.
    yaz(os.path.join(dbn, "control"), f"""\
Package: {PAKET_AD}
Version: {surum}
Section: science
Priority: optional
Architecture: {MIMARI}
Depends: python3 (>= 3.10), python3-venv, python3-pip, adduser, xdg-utils,
 python3-psycopg2, python3-numpy, python3-opencv, python3-serial
Recommends: postgresql, postgresql-contrib, ffmpeg,
 libx11-6, libxcb1, libxcb-shm0, libxcb-render0, libxcb-shape0, libxcb-xfixes0,
 libasound2t64 | libasound2, libtiff5 | libtiff6, libfreetype6, libbz2-1.0, liblzma5, libatomic1,
 libva2, libva-drm2, libva-x11-2, libsndio7.0, libxext6, libxv1
Suggests: postgis
Maintainer: {BAKIMCI}
Installed-Size: {kurulu_boyut}
Homepage: https://goktungu.com/
Description: GOKTUNGU Merkez Uygulamasi — yer kontrol istasyonu
 GOKTUNGU merkezi komuta kontrol yaziliminin kurum ici (on-premise)
 surumu. Dron telemetrisi, gorev planlama, video duvari, AI destekli
 tespit ve radar tumlestirmesi icerir.
 .
 Sistem servisi olarak calisir: makine acilisinda kimse oturum
 acmadan baslar. Arayuz http://127.0.0.1:{HTTP_PORT}/ adresinde acilir.
 .
 Lisans dosyasi Ed25519 ile imzalanir ve internet baglantisi olmadan
 dogrulanir; kapali devre (air-gapped) kurulumda calisabilir.
""")

    # ---------------- preinst ----------------
    yaz(os.path.join(dbn, "preinst"), f"""\
#!/bin/sh
set -e

case "$1" in
  upgrade|install)
    if [ -d /run/systemd/system ]; then
      if systemctl is-active --quiet {PAKET_AD}.service 2>/dev/null; then
        echo "Servis durduruluyor (yukseltme)..."
        systemctl stop {PAKET_AD}.service || true
        i=0
        while systemctl is-active --quiet {PAKET_AD}.service 2>/dev/null; do
          i=$((i+1)); [ "$i" -ge 15 ] && break
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
    if ! getent passwd "$KULLANICI" >/dev/null; then
      adduser --system --group --no-create-home \\
              --home "$VERI" \\
              --shell /usr/sbin/nologin \\
              --gecos "GOKTUNGU Merkez servisi" \\
              "$KULLANICI" >/dev/null
    fi

    # Seri (USB) telemetri: dogrudan USB telemetri takilabilir.
    if getent group dialout >/dev/null; then
      usermod -aG dialout "$KULLANICI" >/dev/null 2>&1 || true
    fi

    # --- 2) Veri dizini ---
    # Veritabani ayarlari, ucus kayitlari ve LISANS burada tutulur;
    # yukseltmede ASLA silinmez.
    mkdir -p "$VERI"
    chown "$KULLANICI:$KULLANICI" "$VERI"
    chmod 750 "$VERI"

    # --- 3) Python sanal ortami ---
    #
    # `--system-site-packages` ZORUNLU: opencv, numpy, psycopg2 sistem
    # paketi olarak Depends ile kuruldu. Izole bir venv bunlari GORMEZ
    # ve pip ile yeniden kurmak 60+ MB indirme demektir (kapali devre
    # kurulumda hic olmaz).
    #
    # YORUMLAYICI SECIMI — SISTEM PYTHON'U ONCE (gercek kurulumda
    # OLCULDU, Ubuntu 22.04):
    #   `python3-opencv` paketi cv2'yi YALNIZ o dagitimin varsayilan
    #   surumu icin kurar (`cv2.cpython-310-*.so`). "En yeni surumu
    #   sec" mantigi python3.11'i secmisti; venv
    #   `--system-site-packages` ile olusturuldugu halde 3.10
    #   paketlerini GORMEDI cunku site-packages yolu surum bazlidir.
    #   Servis "opencv-python yok" diyerek cikti ve kurulum basarisiz
    #   oldu.
    #
    # Dogru sira: sistem python3'u ONCE dene — sistem paketleri onun
    # icin kurulur. Asgariyi (3.10) karsilamazsa daha yeni bir surume
    # gecilir; o durumda sistem paketleri gorunmez ve bagimliliklar
    # pip ile kurulur (asagida denetlenir).
    PY=""
    SISTEM_PY="$(command -v python3 2>/dev/null || true)"
    if [ -n "$SISTEM_PY" ] \\
       && "$SISTEM_PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
      PY="$SISTEM_PY"
    else
      # Sistem surumu yetersiz: en yeni uygun surume gec.
      for aday in python3.13 python3.12 python3.11 python3.10; do
        yol="$(command -v $aday 2>/dev/null || true)"
        [ -n "$yol" ] || continue
        if "$yol" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
          PY="$yol"
          echo "Sistem python3 surumu yetersiz; $aday kullanilacak."
          echo "  NOT: sistem paketleri (opencv, numpy, psycopg2) bu"
          echo "       surumde gorunmeyebilir; pip ile kurulacaklar."
          break
        fi
      done
    fi
    if [ -z "$PY" ]; then
      echo "HATA: Python 3.10 veya ustu bulunamadi." >&2
      exit 1
    fi
    echo "Yorumlayici: $PY ($("$PY" -V 2>&1))"

    # Mevcut sanal ortam DENETIMI
    #
    # Yalniz surum bakmak YETMEZ (gercek kurulumda olculdu): 3.11 ile
    # kurulmus bir venv "surum >= 3.10" denetimini GECER ama sistem
    # opencv/psycopg2 paketlerini goremez ve servis her acilista coker.
    # Bu yuzden ortamin GERCEKTEN kullanilabilir oldugu, kritik
    # modulleri ice alarak sinanir.
    if [ -x "$HEDEF/.venv/bin/python" ]; then
      YENILE=""
      if ! "$HEDEF/.venv/bin/python" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
        YENILE="surum yetersiz"
      elif ! "$HEDEF/.venv/bin/python" -c 'import psycopg2, numpy, cv2' >/dev/null 2>&1; then
        # Sistem paketleri gorunmuyor. Bu ortam yorumlayici surumu
        # sistem paketleriyle eslesmediginde olusur.
        YENILE="sistem paketleri gorunmuyor"
      fi
      if [ -n "$YENILE" ]; then
        echo "Mevcut sanal ortam kullanilamaz ($YENILE); yenileniyor..."
        rm -rf "$HEDEF/.venv"
      fi
    fi

    if [ ! -x "$HEDEF/.venv/bin/python" ]; then
      echo "Python sanal ortami hazirlaniyor ($PY)..."
      "$PY" -m venv --system-site-packages "$HEDEF/.venv"
    fi

    # Yalniz sistem paketi OLMAYANLAR pip ile kurulur.
    # websockets: bazi dagitimlarda python3-websockets surumu cok eski.
    # pymavlink: Debian deposunda yok.
    echo "Bagimliliklar denetleniyor..."
    EKSIK=""
    for m in websockets pymavlink; do
      if ! "$HEDEF/.venv/bin/python" -c "import $m" >/dev/null 2>&1; then
        EKSIK="$EKSIK $m"
      fi
    done
    if [ -n "$EKSIK" ]; then
      echo "Kuruluyor:$EKSIK"
      if ! "$HEDEF/.venv/bin/python" -m pip install --quiet $EKSIK \\
           >/dev/null 2>&1; then
        echo "UYARI: bagimliliklar internetten kurulamadi." >&2
        echo "       Baglanti saglandiktan sonra:" >&2
        echo "       sudo $HEDEF/.venv/bin/python -m pip install$EKSIK" >&2
      fi
    fi

    # Kritik modulleri DOGRULA. Eksikse servis her acilista coker ve
    # kullanici yalnizca "calismiyor" gorur; burada gerekce yazilir.
    for m in psycopg2 numpy cv2; do
      if ! "$HEDEF/.venv/bin/python" -c "import $m" >/dev/null 2>&1; then
        echo "UYARI: '$m' modulu ice alinamadi." >&2
        echo "       Kurmak icin: sudo apt install python3-$m" >&2
      fi
    done

    chown -R root:root "$HEDEF"
    chmod -R go-w "$HEDEF"
    # .venv servis kullanicisinin okumasi icin erisilebilir kalmali.
    chmod -R a+rX "$HEDEF"
    # v2.4.218 (kullanici bildirimi: "uygulama icinden guncelleme yetki
    # hatasi veriyor"): uygulama ici guncelleyici imzali (Ed25519) manifest
    # dosyalarini KURULUM dizinine yazar. Yonetilen kokler (assets/,
    # ai_modeller/) ve kok dosyalari servis kullanicisina devredilir; .venv
    # ve gomulu araclar root'ta kalir. Dizinin kendisi de yazilabilir olur
    # (yeni kok dosyasi / gecici dosya + os.replace icin).
    KULLANICI="{SERVIS_KULLANICI}"
    for y in assets ai_modeller main.py goktungu_guncelleyici.py requirements.txt jetson_ai_kur.sh; do
      [ -e "$HEDEF/$y" ] && chown -R "$KULLANICI:$KULLANICI" "$HEDEF/$y" && chmod -R u+w "$HEDEF/$y"
    done
    chown "$KULLANICI:$KULLANICI" "$HEDEF"
    chmod u+w "$HEDEF"

    # --- 4) Ikon onbellegi ve masaustu veritabani ---
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
      gtk-update-icon-cache -f -t /usr/share/icons/hicolor \\
        >/dev/null 2>&1 || true
    fi
    if command -v update-desktop-database >/dev/null 2>&1; then
      update-desktop-database /usr/share/applications \\
        >/dev/null 2>&1 || true
    fi

    # --- 5) Masaustu kisayollari ---
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
    postinst = os.path.join(dbn, "postinst")
    with open(postinst, encoding="utf-8") as f:
        icerik = f.read()
    icerik = icerik.replace("#DEBHELPER#", f"""\
# --- 6) Servisi etkinlestir ve baslat ---
#
# Hatalar YUTULMAZ: kopru kurulumunda `|| true` yuzunden servis hic
# olusmadigi halde kurulum "basarili" gorunuyordu ve kullanicinin
# elinde gerekce olmuyordu.
if [ -d /run/systemd/system ]; then
  systemctl daemon-reload || true

  if [ "$(systemctl is-enabled {PAKET_AD}.service 2>/dev/null)" = "masked" ]; then
    echo "Servis maskelenmis; maske kaldiriliyor."
    systemctl unmask {PAKET_AD}.service >/dev/null 2>&1 || true
  fi

  if ! systemctl enable {PAKET_AD}.service >/dev/null 2>&1; then
    echo "UYARI: servis acilista baslayacak sekilde ayarlanamadi." >&2
    echo "       Elle: sudo systemctl enable {PAKET_AD}" >&2
  fi

  if systemctl restart {PAKET_AD}.service 2>/dev/null; then
    sleep 3
  else
    echo "UYARI: servis baslatma komutu basarisiz." >&2
  fi

  if systemctl is-active --quiet {PAKET_AD}.service; then
    echo ""
    echo "GOKTUNGU Merkez Uygulamasi {surum} kuruldu ve calisiyor."
    echo ""
    echo "  Arayuz (bu makinede) : http://127.0.0.1:{HTTP_PORT}/"
    for ip in $(hostname -I 2>/dev/null || true); do
      case "$ip" in
        127.*|169.254.*|*:*) continue ;;
      esac
      echo "  Arayuz (agdan)       : http://$ip:{HTTP_PORT}/"
    done
    echo ""
    echo "  SONRAKI ADIM 1 — Veritabani: arayuze girin, PostgreSQL"
    echo "                   sihirbazi sunucu bilgilerinizi soracak."
    echo "  SONRAKI ADIM 2 — Lisans: merkez_lisans.json dosyanizi"
    echo "                   {VERI}/ dizinine kopyalayin."
    echo ""
    echo "  Durum : systemctl status {PAKET_AD}"
    echo "  Gunluk: journalctl -u {PAKET_AD} -f"
    echo ""
    if command -v ufw >/dev/null 2>&1 \\
       && ufw status 2>/dev/null | grep -q "^Status: active"; then
      if ! ufw status 2>/dev/null | grep -q "{HTTP_PORT}"; then
        echo "  Guvenlik duvari etkin. Arayuze agdan erismek icin"
        echo "  YALNIZ yerel aginiza izin verin, ornegin:"
        echo "    sudo ufw allow from 192.168.0.0/16 to any port {HTTP_PORT} proto tcp"
        echo ""
      fi
    fi
  else
    echo "" >&2
    echo "HATA: servis kuruldu ama BASLATILAMADI." >&2
    echo "Gunluk (son 25 satir):" >&2
    journalctl -u {PAKET_AD} --no-pager -n 25 >&2 || true
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
    ;;
esac

exit 0
""", 0o755)

    # ---------------- postrm ----------------
    yaz(os.path.join(dbn, "postrm"), f"""\
#!/bin/sh
set -e

HEDEF="{HEDEF}"
VERI="{VERI}"

case "$1" in
  remove)
    # .venv ve __pycache__ dpkg dosya listesinde YOKTUR (kurulum
    # sonrasi olusur). Silinmezlerse dizin bos kalmaz ve dpkg onu
    # kaldiramaz.
    rm -rf "$HEDEF/.venv"
    find "$HEDEF" -name __pycache__ -type d -exec rm -rf {{}} + 2>/dev/null || true
    rmdir "$HEDEF" 2>/dev/null || true
    rmdir /opt/goktungu 2>/dev/null || true

    for ev in /home/*; do
      for ad in "Masaüstü" "Desktop"; do
        rm -f "$ev/$ad/{PAKET_AD}.desktop" 2>/dev/null || true
      done
    done

    echo "Veritabani ayarlari, ucus kayitlari ve LISANS korundu: $VERI"
    echo "Tamamen silmek icin: sudo apt purge {PAKET_AD}"

    if [ -d /run/systemd/system ]; then
      systemctl daemon-reload || true
    fi
    if command -v update-desktop-database >/dev/null 2>&1; then
      update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
    fi
    ;;

  purge)
    # LISANS UYARISI: purge lisans dosyasini da siler. 5.000 $
    # karsiligi alinan lisans yeniden indirilebilir (kurumsal panel),
    # ancak kullanicinin bunu bilmesi gerekir.
    if [ -f "$VERI/merkez_lisans.json" ]; then
      echo "UYARI: merkez lisans dosyasi siliniyor." >&2
      echo "       Yeniden indirmek icin kurumsal panelinizi kullanin:" >&2
      echo "       https://goktungu.com/company/" >&2
    fi
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

    # md5sums: `dpkg -V` butunluk denetimi
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


def main():
    surum = surum_oku()
    uygulama_surumu = uygulama_surumu_oku()
    calisma = os.path.join(KOK, "dagitim", "deb_calisma")
    os.makedirs(calisma, exist_ok=True)

    print("=" * 68)
    print(f"GOKTUNGU MERKEZ paket {surum} (uygulama {uygulama_surumu}) — .deb paketi uretiliyor")
    print("=" * 68)

    # Agac paketle_merkez.py tarafindan uretilir; ikinci bir beyaz
    # liste tutmamak icin onun ciktisi kullanilir.
    #
    # OLCULEN KUSUR (2026-08-16): agac SADECE dizin yoksa uretiliyordu.
    # v2.4.65'ten kalan agac oldugu gibi paketlendi ve ortaya "2.4.66
    # etiketli, 2.4.65 icerikli" bir .deb cikti: merkez_esitle.py yok,
    # pbkdf2 destegi yok, gomulu gokkubbe2026 sifresi ICINDE, /company/
    # yonlendirmesi yok.  Paketin kendi sinavi 24/0 "gecti" dedi cunku
    # yalniz YAPIYI olcuyordu, ICERIGIN TAZELIGINI hic olcmuyordu.
    # Ayni bayat agaci Windows setup'i da kullanir (setup_merkez.nsi
    # satir 168), yani iki paket birden yanlis cikiyordu.
    #
    # Cozum: agac HER KOSUMDA yeniden uretilir.  Uretim maliyeti
    # (~1 dk) yanlis surum dagitmanin bedeli yaninda onemsizdir.
    agac = os.path.join(KOK, "dagitim", "agac")
    if os.path.isdir(agac):
        print("Onceki paket agaci siliniyor (bayat agac tuzagi)...")
        shutil.rmtree(agac)
    print("Paket agaci uretiliyor: paketle_merkez.py --agac-birak ...")
    r = subprocess.run(
        [sys.executable, os.path.join(KOK, "paketle_merkez.py"),
         "--agac-birak", "--arsiv-yok", "--ai-dahil"],
        capture_output=True, text=True)
    if r.returncode != 0:
        print("HATA: paket agaci uretilemedi")
        print(r.stdout[-3000:])
        print(r.stderr[-2000:])
        return 1
    if not os.path.isdir(agac):
        print(f"HATA: agac hala yok: {agac}")
        return 1

    # Agacin GERCEKTEN istenen surumu tasidigini dogrula.  Etiket ile
    # icerik ayrisirsa paketleme burada durur.
    tazelik = agac_tazelik_olc(agac, uygulama_surumu)
    if tazelik:
        print("HATA: paket agaci istenen surumu tasimiyor:")
        for t in tazelik:
            print("  - " + t)
        return 1
    print(f"  agac tazeligi dogrulandi: uygulama {uygulama_surumu}")

    kok = kur_agaci(calisma, agac, surum)

    toplam = 0
    for k, _, ds in os.walk(kok):
        for d in ds:
            toplam += os.path.getsize(os.path.join(k, d))
    kurulu_kb = max(1, toplam // 1024)

    denetim_dosyalari(kok, kurulu_kb, surum)

    cikti = os.path.join(
        KOK, "dagitim", f"{PAKET_AD}_{surum}_{MIMARI}.deb")
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

    # --- Sinav ---
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
    d("surum dogru", f"Version: {surum}" in bilgi)
    d("python3-venv bagimliligi", "python3-venv" in bilgi,
      "venv olusturulamaz, postinst duser")
    d("psycopg2 bagimliligi", "python3-psycopg2" in bilgi,
      "PostgreSQL surucusu yok; uygulama veritabanina baglanamaz")
    d("opencv bagimliligi", "python3-opencv" in bilgi,
      "video/AI islevleri calismaz")
    d("PostgreSQL Depends DEGIL (Recommends)",
      "Recommends:" in bilgi and "postgresql" in bilgi.split("Recommends:")[1][:120],
      "uzak veritabani kullanan kuruluma gereksiz sunucu kurulur")

    r = subprocess.run(["dpkg-deb", "--contents", cikti],
                       capture_output=True, text=True)
    icerik = r.stdout
    d("uygulama /opt/goktungu/merkez altinda",
      f".{HEDEF}/main.py" in icerik)
    d("assets/web agaci var",
      f".{HEDEF}/assets/web/index.html" in icerik)
    d("assets/python agaci var",
      f".{HEDEF}/assets/python/goktungu/" in icerik)
    d("systemd birimi var",
      f"./lib/systemd/system/{PAKET_AD}.service" in icerik)
    d("masaustu girdisi var",
      f"./usr/share/applications/{PAKET_AD}.desktop" in icerik)
    d("ikonlar var (merkez adiyla)",
      f"/apps/{PAKET_AD}.png" in icerik,
      "kopru ikon adiyla catisma olur")
    d("sinav betikleri paketE GIRMEMIS", "sinav_" not in icerik,
      "gelistirme dosyalari dagitima girmis")
    d("Windows dosyalari paketE GIRMEMIS",
      "setup_merkez.nsi" not in icerik
      and "servis_merkez_win.py" not in icerik)
    d("__pycache__ paketE GIRMEMIS", "__pycache__" not in icerik)

    # systemd birim dosyasi denetimi
    birim = os.path.join(kok, "lib/systemd/system", f"{PAKET_AD}.service")
    with open(birim, encoding="utf-8") as f:
        bmetin = f.read()
    d("StartLimit* [Unit] bolumunde",
      bmetin.index("StartLimitBurst") < bmetin.index("[Service]"),
      "systemd sessizce yok sayar, cokme dongusu sinirsiz kalir")
    d("GOKTUNGU_VERI_KOKU verilmis", f"GOKTUNGU_VERI_KOKU={VERI}" in bmetin,
      "uygulama /opt altina yazmayi dener, ProtectSystem engeller")
    d("port kaydirma verilmis",
      f"GOKTUNGU_VIDEO_PORT={VIDEO_PORT}" in bmetin
      and f"GOKTUNGU_AI_PORT={AI_PORT}" in bmetin,
      "kopru ile ayni makinede cakisma olur")
    d("ReadWritePaths veri dizinini kapsiyor",
      f"ReadWritePaths={VERI}" in bmetin)

    # venv system-site-packages: sistem opencv/psycopg2 gorunmeli
    pi = os.path.join(kok, "DEBIAN", "postinst")
    with open(pi, encoding="utf-8") as f:
        pmetin = f.read()
    d("venv --system-site-packages ile kuruluyor",
      "--system-site-packages" in pmetin,
      "sistem opencv/psycopg2 gorunmez, pip 60+ MB indirmeye kalkar")

    # Bakim betikleri sozdizimi
    for b in ("preinst", "postinst", "prerm", "postrm"):
        yol = os.path.join(kok, "DEBIAN", b)
        r = subprocess.run(["sh", "-n", yol], capture_output=True, text=True)
        d(f"{b} sozdizimi", r.returncode == 0, r.stderr.strip())

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
