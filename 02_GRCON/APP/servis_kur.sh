#!/usr/bin/env bash
# GOKTUNGU GCS v2.4.52 - systemd servis + yetki + kiosk kurulumu
#
# v2.4.52 NOTU: klasor yapisi degisti. Betik artik
# assets/python/betikler/ altinda durur ve kok dizini main.py'yi YUKARI
# dogru arayarak bulur. Kiosk betigi de ayni dizinde arandigi icin iki
# yapida da (duz ve assets) calisir.
#
# Kullanim:
#   sudo bash servis_kur.sh [KOK_DIZIN] [KULLANICI]
#   sudo bash servis_kur.sh --kaldir
#
# Ornek:
#   sudo bash servis_kur.sh /home/mkaderoglu/goktungu mkaderoglu
#
# NE YAPAR
#   1. /etc/systemd/system/goktungu.service birimini yazar
#   2. Yetki kurallarini UC bicimde birlikte yazar (sudoers + polkit JS + pkla)
#   3. Kiosk otomatik baslatma girdisini kullanicinin autostart'ina koyar
#   4. Servisi etkinlestirir (bilgisayar acildiginda kendiliginden baslar)
#
# NEDEN UC YETKI BICIMI
#   polkit yapilandirmasi surumler arasinda bicim degistirir: 0.105 ve
#   oncesi yalniz "pkla" (INI benzeri) okur, 0.106+ ise JavaScript kurallari
#   okur. Cloud Computer'da (polkit 0.105) rules.d dizini HIC YOKTU; olculdu.
#   Tek bicime guvenmek kurulumun sessizce yetkisiz kalmasina yol acar:
#   arayuzdeki dugme etkin gorunur, basilir, hicbir sey olmaz. Bu yuzden
#   ucu birlikte yazilir ve sudoers her durumda calisan yedegi saglar.
#
# VERILEN YETKI GENEL ROOT YETKISI DEGILDIR
#   Yalniz su komutlar: goktungu servisinin start/stop/restart/enable/disable
#   ve makinenin poweroff/reboot islemi. Baska hicbir komut kapsanmaz.

set -uo pipefail

BIRIM="/etc/systemd/system/goktungu.service"
SUDOERS="/etc/sudoers.d/goktungu-servis"
POLKIT_JS="/etc/polkit-1/rules.d/49-goktungu.rules"
POLKIT_PKLA="/etc/polkit-1/localauthority/50-local.d/49-goktungu.pkla"

kirmizi() { printf '\033[31m%s\033[0m\n' "$*"; }
yesil()   { printf '\033[32m%s\033[0m\n' "$*"; }
sari()    { printf '\033[33m%s\033[0m\n' "$*"; }
mavi()    { printf '\033[36m%s\033[0m\n' "$*"; }

[ "$(id -u)" = "0" ] || { kirmizi "HATA: root gerekiyor. 'sudo bash $0 ...' kullanin."; exit 1; }

# =====================================================  KALDIR
if [ "${1:-}" = "--kaldir" ]; then
  mavi "GOKTUNGU servisi kaldiriliyor..."
  systemctl stop goktungu 2>/dev/null
  systemctl disable goktungu 2>/dev/null
  rm -f "$BIRIM" "$SUDOERS" "$POLKIT_JS" "$POLKIT_PKLA"
  systemctl daemon-reload
  systemctl reset-failed goktungu 2>/dev/null
  # autostart girdisini tum kullanicilardan kaldir
  for h in /home/*; do
    rm -f "$h/.config/autostart/goktungu-kiosk.desktop" 2>/dev/null
  done
  yesil "Kaldirildi: birim, yetki kurallari ve kiosk otomatik baslatma."
  echo "Not: kurulum dizini ve veritabani SILINMEDI."
  exit 0
fi

# =====================================================  1) Girdiler
KOK="${1:-}"
if [ -z "$KOK" ]; then
  # v2.4.52: betik `assets/python/betikler/` altinda olabilir.
  # "Kendi dizinim koktur" varsayimi o durumda YANLIS olur ve betik
  # "main.py bulunamadi" ile durur. main.py YUKARI dogru aranir.
  _d="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  KOK="$_d"
  for _i in 1 2 3 4; do
    if [ -f "$_d/main.py" ]; then KOK="$_d"; break; fi
    _d="$(dirname "$_d")"
  done
fi
KOK="$(cd "$KOK" 2>/dev/null && pwd)" || { kirmizi "HATA: dizin yok: ${1:-}"; exit 1; }

if [ ! -f "$KOK/main.py" ]; then
  kirmizi "HATA: $KOK/main.py bulunamadi."
  echo "  Kurulum dizinini dogru verdiginizden emin olun:"
  echo "    sudo bash $0 /home/KULLANICI/goktungu KULLANICI"
  exit 1
fi

# Kullanici: verilmediyse kurulum dizininin SAHIBINDEN turet.
# Bu, root olarak calistirildiginda $USER'in "root" olmasi tuzagini onler;
# servis root olarak calisirsa veri dosyalarinin sahipligi bozulur.
KULLANICI="${2:-}"
if [ -z "$KULLANICI" ]; then
  KULLANICI="$(stat -c '%U' "$KOK/main.py")"
fi
if ! id "$KULLANICI" >/dev/null 2>&1; then
  kirmizi "HATA: kullanici yok: $KULLANICI"; exit 1
fi
if [ "$KULLANICI" = "root" ]; then
  kirmizi "HATA: servis root olarak calistirilamaz."
  echo "  Neden: veri/ ve gunluk dosyalarinin sahipligi root'a gecer, sonra"
  echo "  programi elle baslattiginizda 'izin yok' hatasi alirsiniz."
  echo "  Kullanici adini acikca verin:  sudo bash $0 $KOK KULLANICI_ADI"
  exit 1
fi
GRUP="$(id -gn "$KULLANICI")"

PY="$(command -v python3 || true)"
[ -n "$PY" ] || { kirmizi "HATA: python3 bulunamadi."; exit 1; }

mavi "=================================================="
mavi " GOKTUNGU v2.4.52 - servis kurulumu"
mavi "=================================================="
echo "  Kurulum dizini : $KOK"
echo "  Kullanici      : $KULLANICI ($GRUP)"
echo "  Python         : $PY"
echo "  Mimari         : $(uname -m)"
echo

# =====================================================  2) Onkosullar
ADIM=0; TAMAM=0; UYARI=0
ol() { ADIM=$((ADIM+1)); }
ok() { ol; TAMAM=$((TAMAM+1)); yesil "  [TAMAM] $*"; }
uy() { ol; UYARI=$((UYARI+1)); sari  "  [UYARI] $*"; }
ha() { ol; kirmizi "  [HATA ] $*"; }

echo "--- Onkosullar ---"
if ! pidof systemd >/dev/null 2>&1 && [ ! -d /run/systemd/system ]; then
  ha "systemd calismiyor - servis kurulumu bu makinede yapilamaz."
  echo "        Programi elle baslatin: cd $KOK && python3 main.py"
  exit 1
fi
ok "systemd calisiyor"

# SIGTERM ile duzgun kapanis v2.4.49'de eklendi. Eski surumde servis
# 'stop' komutunda 90 saniye bekleyip zorla oldurulur ve o durumda sanal
# dron surecleri arkada kalip portlari bloke eder.
if grep -q "_sigterm_kur" "$KOK/main.py" 2>/dev/null; then
  ok "SIGTERM ile duzgun kapanis kodu var (v2.4.49+)"
else
  uy "main.py'de SIGTERM isleyicisi YOK - kurulum v2.4.49'dan eski"
  echo "        Servis 'stop' komutunda 90 sn bekleyip zorla oldurulur."
  echo "        Cozum: once v2.4.49 yamasini uygulayin (kur_2449.sh)."
fi

if grep -q "_port_dosyasi_yaz" "$KOK/main.py" 2>/dev/null; then
  ok "Gercek port kaydi var (kiosk portu dogru okuyabilir)"
else
  uy "veri/calisma.json yazilmiyor - kiosk portu tahmin etmek zorunda kalir"
fi
echo

# =====================================================  3) systemd birimi
echo "--- systemd birimi ---"
cat > "$BIRIM" <<EOF
[Unit]
Description=GOKTUNGU GCS - Yer Kontrol Istasyonu
Documentation=file://$KOK/GOKTUNGU_2.4.52_KURULUM_VE_SURUM_NOTLARI.md
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$KULLANICI
Group=$GRUP
# KRITIK: main.py goreli yollar kullanir (veri/, js/, sitl/). Bu satir
# olmadan servis / dizininde baslar ve hicbir dosyayi bulamaz.
WorkingDirectory=$KOK
ExecStart=$PY -u $KOK/main.py

KillSignal=SIGTERM
TimeoutStopSec=30
# mixed: SIGTERM yalniz ana surece gider ki program SITL sureclerini
# kendi duzenli temizligiyle kapatabilsin.
KillMode=mixed

Restart=on-failure
RestartSec=5
StartLimitIntervalSec=300
StartLimitBurst=5

StandardOutput=journal
StandardError=journal
SyslogIdentifier=goktungu

[Install]
WantedBy=multi-user.target
EOF
chmod 644 "$BIRIM"
ok "Birim yazildi: $BIRIM"

systemctl daemon-reload && ok "systemd yeniden yuklendi" || ha "daemon-reload basarisiz"

# =====================================================  4) Yetki: sudoers
echo
echo "--- Yetki kurallari ---"
# NOPASSWD sart: arayuzden servis durdurmak sifre soramaz.
# Komutlar tek tek yazilir; genel root yetkisi VERILMEZ.
SC="$(command -v systemctl)"
cat > "$SUDOERS.yeni" <<EOF
# GOKTUNGU GCS v2.4.49 - dar kapsamli yetki
# Yalniz asagidaki komutlar; baska hicbir komut kapsanmaz.
$KULLANICI ALL=(root) NOPASSWD: $SC start goktungu, $SC start goktungu.service
$KULLANICI ALL=(root) NOPASSWD: $SC stop goktungu, $SC stop goktungu.service
$KULLANICI ALL=(root) NOPASSWD: $SC restart goktungu, $SC restart goktungu.service
$KULLANICI ALL=(root) NOPASSWD: $SC enable goktungu, $SC enable goktungu.service
$KULLANICI ALL=(root) NOPASSWD: $SC disable goktungu, $SC disable goktungu.service
$KULLANICI ALL=(root) NOPASSWD: $SC poweroff, $SC reboot
EOF
# visudo -c ile DOGRULA, sonra yerine koy. Bozuk sudoers dosyasi tum
# sudo erisimini kirar; bu yuzden dogrulanmadan tasinmaz.
if visudo -cf "$SUDOERS.yeni" >/dev/null 2>&1; then
  mv "$SUDOERS.yeni" "$SUDOERS"; chmod 440 "$SUDOERS"
  ok "sudoers kurali yazildi ve dogrulandi: $SUDOERS"
else
  rm -f "$SUDOERS.yeni"
  ha "sudoers kurali gecersiz - yazilmadi (mevcut sudo erisimi korundu)"
fi

# --- polkit: modern JavaScript bicimi (0.106+)
if [ -d /etc/polkit-1/rules.d ] || mkdir -p /etc/polkit-1/rules.d 2>/dev/null; then
  cat > "$POLKIT_JS" <<EOF
// GOKTUNGU GCS v2.4.49 - polkit (modern JavaScript bicimi, polkit 0.106+)
polkit.addRule(function(action, subject) {
  if (subject.user !== "$KULLANICI") { return polkit.Result.NOT_HANDLED; }

  // Yalniz goktungu servisinin yonetimi
  if (action.id === "org.freedesktop.systemd1.manage-units") {
    var u = action.lookup("unit");
    if (u === "goktungu.service") { return polkit.Result.YES; }
    return polkit.Result.NOT_HANDLED;
  }

  // Makineyi kapatma / yeniden baslatma (arayuzdeki dugmeler icin)
  if (action.id === "org.freedesktop.login1.power-off" ||
      action.id === "org.freedesktop.login1.power-off-multiple-sessions" ||
      action.id === "org.freedesktop.login1.reboot" ||
      action.id === "org.freedesktop.login1.reboot-multiple-sessions") {
    return polkit.Result.YES;
  }
  return polkit.Result.NOT_HANDLED;
});
EOF
  chmod 644 "$POLKIT_JS"
  ok "polkit JS kurali yazildi: $POLKIT_JS"
else
  uy "polkit rules.d yazilamadi"
fi

# --- polkit: eski pkla bicimi (0.105 ve oncesi)
# Cloud Computer'da (polkit 0.105) rules.d HIC YOKTU ve yalniz bu bicim
# okunuyordu; olculdu ve dogrulandi.
if mkdir -p /etc/polkit-1/localauthority/50-local.d 2>/dev/null; then
  cat > "$POLKIT_PKLA" <<EOF
[GOKTUNGU servis yonetimi]
Identity=unix-user:$KULLANICI
Action=org.freedesktop.systemd1.manage-units
ResultActive=yes
ResultInactive=yes
ResultAny=no

[GOKTUNGU makine kapatma ve yeniden baslatma]
Identity=unix-user:$KULLANICI
Action=org.freedesktop.login1.power-off;org.freedesktop.login1.power-off-multiple-sessions;org.freedesktop.login1.reboot;org.freedesktop.login1.reboot-multiple-sessions
ResultActive=yes
ResultInactive=yes
ResultAny=no
EOF
  chmod 644 "$POLKIT_PKLA"
  ok "polkit pkla kurali yazildi: $POLKIT_PKLA"
else
  uy "polkit localauthority yazilamadi"
fi

# polkit'i yeniden yukle (yeni kurallari okusun)
systemctl reload polkit 2>/dev/null || systemctl restart polkit 2>/dev/null || true

# --- Yetkiyi GERCEKTEN olc (dry-run yetki olcmez; v2.4.49'de olculdu)
if sudo -n -u "$KULLANICI" sudo -n -l 2>/dev/null | grep -q "systemctl"; then
  ok "Yetki dogrulandi: $KULLANICI sudo ile servisi yonetebiliyor"
else
  uy "Yetki dogrulanamadi - arayuzden servis yonetimi calismayabilir"
  echo "        Elle sinama: sudo -u $KULLANICI sudo -n -l | grep systemctl"
fi

# =====================================================  5) Kiosk autostart
echo
echo "--- Kiosk otomatik baslatma ---"
EV="$(getent passwd "$KULLANICI" | cut -d: -f6)"

# v2.4.52: kiosk betigi ARTIK KOKTE DEGIL. Yeni yapida
# assets/python/betikler/ altinda durur. Iki konum da denenir; boylece
# ayni betik hem duz (v2.4.51 ve oncesi) hem assets yapisinda calisir.
# Bu arama olmazsa servis kurulur, program acilista baslar ama IKI EKRANLI
# KIOSK SESSIZCE GELMEZ - yalniz bir uyari satiri dusen, gozden kacan kusur.
KIOSK=""
for _k in "$KOK/assets/python/betikler/kiosk_baslat.sh" \
          "$KOK/kiosk_baslat.sh"; do
  if [ -f "$_k" ]; then KIOSK="$_k"; break; fi
done

if [ -n "$EV" ] && [ -d "$EV" ]; then
  if [ -n "$KIOSK" ]; then
    chmod +x "$KIOSK"
    install -d -o "$KULLANICI" -g "$GRUP" "$EV/.config/autostart"
    cat > "$EV/.config/autostart/goktungu-kiosk.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=GOKTUNGU Kiosk (iki ekran)
Comment=Ust ekranda ana arayuz, ikinci ekranda ucus duvari - tam ekran
# 12 sn gecikme: sunucunun portu baglayip veri/calisma.json'a yazmasi ve
# ikinci ekranin X tarafindan taninmasi icin. Betik ayrica portu kendisi
# olcer; gecikme yalnizca ilk denemenin bosa gitmemesi icindir.
Exec=bash -c "sleep 12; '$KIOSK' '$KOK'"
X-GNOME-Autostart-enabled=true
Terminal=false
EOF
    chown "$KULLANICI:$GRUP" "$EV/.config/autostart/goktungu-kiosk.desktop"
    ok "Kiosk otomatik baslatma kuruldu: $EV/.config/autostart/"
  else
    uy "kiosk_baslat.sh bulunamadi - kiosk kurulmadi"
    echo "        Arandi: $KOK/assets/python/betikler/  ve  $KOK/"
  fi
else
  uy "Ev dizini bulunamadi ($KULLANICI) - kiosk kurulmadi"
fi

# =====================================================  6) Etkinlestir
echo
echo "--- Servisi etkinlestir ---"
if systemctl enable goktungu >/dev/null 2>&1; then
  ok "Acilista otomatik baslatma ETKIN (bilgisayar acildiginda baslar)"
else
  ha "systemctl enable basarisiz"
fi

# Elle calisan bir ornek varsa uyar: iki ornek ayni portu alamaz, ikincisi
# sirayla sonraki porta duser ve kiosk yanlis pencereye baglanir.
if pgrep -f "$KOK/main.py" >/dev/null 2>&1; then
  uy "Elle baslatilmis bir GOKTUNGU ornegi CALISIYOR"
  echo "        Servisi baslatmadan once onu kapatin, yoksa ikinci ornek"
  echo "        baska bir porta duser. Kapatma: pkill -f '$KOK/main.py'"
fi

echo
mavi "=================================================="
mavi " Sonuc: $TAMAM/$ADIM tamam, $UYARI uyari"
mavi "=================================================="
echo
echo "Servisi simdi baslatmak icin:"
echo "  sudo systemctl start goktungu"
echo
echo "Durum ve gunluk:"
echo "  systemctl status goktungu"
echo "  journalctl -u goktungu -f"
echo
echo "Arayuzden yonetim: Program Ayarlari > Servis Yonetimi"
echo "Makineyi kapatma  : kullanici menusu > Bilgisayari Kapat (yonetici)"
echo
echo "Kaldirmak icin:  sudo bash $0 --kaldir"
