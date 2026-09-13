#!/bin/bash
# GOKTUNGU Kopru — Ubuntu tani ve temiz sifirlama araci
#
# KULLANIM
#   sudo ./tani_sifirla.sh              # yalnizca TANI (hicbir sey silmez)
#   sudo ./tani_sifirla.sh --sifirla    # eski kalintilari temizler, sonra tani
#
# NEDEN VAR
#   `service --status-all` YALNIZCA SysV init betiklerini listeler; systemd
#   birimlerini GOSTERMEZ. Kopru bir systemd birimidir, dolayisiyla o listede
#   HICBIR ZAMAN gorunmez. "Servis yok" sanilmasinin en sik nedeni budur.
#
#   Ikinci neden: v1.3.x oncesi `kur.sh` ayni adi (goktungu-kopru) KULLANICI
#   servisi olarak ~/.config/systemd/user/ altina kuruyordu. Yeni .deb ise
#   SISTEM servisi olarak /lib/systemd/system/ altina kurar. Ikisi ayni anda
#   varsa ayni porta (8790) iki surec baglanmaya calisir; biri "Address already
#   in use" ile duser ve durum kafa karistirir.

set -u

SERVIS="goktungu-kopru"
PORT="8790"
KIRMIZI=$'\033[31m'; YESIL=$'\033[32m'; SARI=$'\033[33m'; MAVI=$'\033[36m'
KALIN=$'\033[1m'; SIFIR=$'\033[0m'

baslik() { echo; echo "${KALIN}${MAVI}== $* ==${SIFIR}"; }
iyi()    { echo "  ${YESIL}[ + ]${SIFIR} $*"; }
kotu()   { echo "  ${KIRMIZI}[ - ]${SIFIR} $*"; }
uyari()  { echo "  ${SARI}[ ! ]${SIFIR} $*"; }
bilgi()  { echo "        $*"; }

SIFIRLA=0
[ "${1:-}" = "--sifirla" ] && SIFIRLA=1

if [ "$(id -u)" != "0" ]; then
  echo "${KIRMIZI}Bu betik root yetkisi ister:${SIFIR} sudo $0 ${1:-}"
  exit 1
fi

# Betigi `sudo` ile cagiran gercek kullanici (kullanici servisini onun
# altinda aramak icin gerekir; root'un kendi ~/.config'i degil).
GERCEK_KULLANICI="${SUDO_USER:-$USER}"
GERCEK_EV="$(getent passwd "$GERCEK_KULLANICI" | cut -d: -f6)"
[ -z "$GERCEK_EV" ] && GERCEK_EV="/home/$GERCEK_KULLANICI"

# ---------------------------------------------------------------- SIFIRLAMA
if [ "$SIFIRLA" = "1" ]; then
  baslik "TEMIZ SIFIRLAMA"

  # 1) Eski KULLANICI servisini kaldir (v1.3.x oncesi kur.sh kalintisi).
  #    Ayni ada sahip oldugu icin sistem servisiyle porta girer.
  BIRIM_K="$GERCEK_EV/.config/systemd/user/$SERVIS.service"
  if [ -f "$BIRIM_K" ]; then
    uyari "Eski KULLANICI servisi bulundu: $BIRIM_K"
    sudo -u "$GERCEK_KULLANICI" XDG_RUNTIME_DIR="/run/user/$(id -u "$GERCEK_KULLANICI")" \
      systemctl --user stop "$SERVIS" 2>/dev/null || true
    sudo -u "$GERCEK_KULLANICI" XDG_RUNTIME_DIR="/run/user/$(id -u "$GERCEK_KULLANICI")" \
      systemctl --user disable "$SERVIS" 2>/dev/null || true
    rm -f "$BIRIM_K"
    sudo -u "$GERCEK_KULLANICI" XDG_RUNTIME_DIR="/run/user/$(id -u "$GERCEK_KULLANICI")" \
      systemctl --user daemon-reload 2>/dev/null || true
    iyi "Eski kullanici servisi kaldirildi"
  else
    bilgi "Eski kullanici servisi yok (beklenen)"
  fi

  # 2) Sistem servisini durdur.
  if systemctl list-unit-files "$SERVIS.service" >/dev/null 2>&1; then
    systemctl stop "$SERVIS" 2>/dev/null || true
    iyi "Sistem servisi durduruldu"
  fi

  # 3) Paketi tamamen kaldir. `purge` yapilandirmayi da siler; bu yuzden
  #    ONCE yapilandirmayi yedekle, kullanici yeniden giris yapmak zorunda
  #    kalmasin diye geri yuklemeyi teklif edelim.
  if dpkg -l "$SERVIS" 2>/dev/null | grep -q "^ii"; then
    YEDEK="/root/goktungu_kopru_ayar_yedek_$(date +%Y%m%d_%H%M%S).tar.gz"
    if [ -d /var/lib/goktungu-kopru ] || [ -d /etc/goktungu-kopru ]; then
      tar czf "$YEDEK" /var/lib/goktungu-kopru /etc/goktungu-kopru 2>/dev/null || true
      [ -f "$YEDEK" ] && iyi "Ayarlar yedeklendi: $YEDEK"
    fi
    DEBIAN_FRONTEND=noninteractive apt-get purge -y "$SERVIS" >/dev/null 2>&1 \
      || dpkg --purge "$SERVIS" >/dev/null 2>&1 || true
    iyi "Paket kaldirildi (purge)"
  else
    bilgi "Paket dpkg kaydinda yok"
  fi

  # 4) Artik dosyalari sil. Paket kaldirildiginda kalabilecek yollar.
  for y in /lib/systemd/system/$SERVIS.service \
           /etc/systemd/system/$SERVIS.service \
           /etc/systemd/system/multi-user.target.wants/$SERVIS.service \
           /opt/goktungu/kopru; do
    if [ -e "$y" ]; then
      rm -rf "$y"
      iyi "Silindi: $y"
    fi
  done

  systemctl daemon-reload 2>/dev/null || true
  systemctl reset-failed "$SERVIS" 2>/dev/null || true
  iyi "systemd yenilendi"

  # 5) Porta yapisik kalan surec var mi? Varsa kurulum "Address already in
  #    use" ile duser ve neden gorunmez.
  KALAN="$(ss -lptn "sport = :$PORT" 2>/dev/null | grep -c LISTEN || true)"
  if [ "${KALAN:-0}" != "0" ]; then
    uyari "Port $PORT hala dinleniyor; asagidaki surec kapatilmali:"
    ss -lptn "sport = :$PORT" 2>/dev/null | tail -n +2
    pkill -f "kopru" 2>/dev/null || true
    sleep 1
    iyi "Artik surecler kapatilmaya calisildi"
  fi

  echo
  echo "${KALIN}Sifirlama bitti. Simdi kuruluma gecin:${SIFIR}"
  echo "  sudo apt-get install -y ./goktungu-kopru_*_all.deb"
  echo
fi

# -------------------------------------------------------------------- TANI
baslik "1) DOGRU KOMUTLA BAKIYOR MUSUNUZ?"
bilgi "\`service --status-all\` YALNIZCA SysV init betiklerini listeler."
bilgi "Kopru bir systemd birimidir; o listede GORUNMEZ. Dogru komut:"
bilgi "  systemctl status $SERVIS"
if service --status-all 2>/dev/null | grep -qi goktungu; then
  uyari "service --status-all icinde goktungu gorunuyor (beklenmeyen)"
else
  iyi "service --status-all icinde YOK — bu NORMALDIR, kusur degil"
fi

baslik "2) PAKET KURULU MU?"
if dpkg -l "$SERVIS" 2>/dev/null | grep -q "^ii"; then
  S="$(dpkg-query -W -f='${Version}' "$SERVIS" 2>/dev/null)"
  iyi "Paket kurulu, surum: ${KALIN}$S${SIFIR}"
else
  kotu "Paket KURULU DEGIL"
  bilgi "Kurulum:  sudo apt-get install -y ./goktungu-kopru_*_all.deb"
fi

baslik "3) SISTEM SERVISI VAR MI?"
if [ -f "/lib/systemd/system/$SERVIS.service" ]; then
  iyi "Birim dosyasi var: /lib/systemd/system/$SERVIS.service"
else
  kotu "Birim dosyasi YOK: /lib/systemd/system/$SERVIS.service"
fi
DURUM_E="$(systemctl is-enabled "$SERVIS" 2>&1)"
DURUM_A="$(systemctl is-active "$SERVIS" 2>&1)"
case "$DURUM_E" in
  enabled) iyi "Acilista baslar (enabled)" ;;
  *)       kotu "Acilista baslamaz: $DURUM_E" ;;
esac
case "$DURUM_A" in
  active)  iyi "Su an CALISIYOR (active)" ;;
  *)       kotu "Su an calismiyor: $DURUM_A" ;;
esac

baslik "4) ESKI KULLANICI SERVISI KALINTISI VAR MI?"
bilgi "v1.3.x oncesi kur.sh, AYNI ADI kullanici servisi olarak kuruyordu."
bilgi "Ikisi birlikte varsa ayni porta ($PORT) iki surec girer."
if [ -f "$GERCEK_EV/.config/systemd/user/$SERVIS.service" ]; then
  kotu "KALINTI VAR: $GERCEK_EV/.config/systemd/user/$SERVIS.service"
  bilgi "Temizlemek icin:  sudo $0 --sifirla"
else
  iyi "Kalinti yok"
fi

baslik "5) PANEL YANIT VERIYOR MU?"
KOD="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:$PORT/" 2>/dev/null)"
if [ "$KOD" = "200" ] || [ "$KOD" = "302" ]; then
  iyi "Panel yanit veriyor (HTTP $KOD) — http://127.0.0.1:$PORT/"
else
  kotu "Panel yanit vermiyor (HTTP ${KOD:-yok})"
  bilgi "Port durumu:"
  ss -lptn "sport = :$PORT" 2>/dev/null | tail -n +2 | sed 's/^/        /'
fi

baslik "6) SON GUNLUK SATIRLARI"
if journalctl -u "$SERVIS" --no-pager -n 15 >/dev/null 2>&1; then
  journalctl -u "$SERVIS" --no-pager -n 15 2>/dev/null | sed 's/^/        /'
else
  bilgi "Gunluk okunamadi (servis hic baslamamis olabilir)"
fi

baslik "OZET"
if [ "$DURUM_A" = "active" ] && { [ "$KOD" = "200" ] || [ "$KOD" = "302" ]; }; then
  echo "  ${YESIL}${KALIN}Kopru servisi calisiyor ve panel acik.${SIFIR}"
  echo "  Tarayicidan girin: ${KALIN}http://127.0.0.1:$PORT/${SIFIR}"
  AG_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  if [ -n "$AG_IP" ] && [ "$AG_IP" != "127.0.0.1" ]; then
    echo "  Ayni agdaki baska bilgisayardan: ${KALIN}http://$AG_IP:$PORT/${SIFIR}"
  fi
  echo "  Servisi gormek icin: ${KALIN}systemctl status $SERVIS${SIFIR}"
  echo "  (\`service --status-all\` bu servisi ASLA gostermez.)"
else
  echo "  ${KIRMIZI}${KALIN}Kopru servisi calismiyor.${SIFIR} Sirasiyla:"
  echo "    1) sudo $0 --sifirla"
  echo "    2) sudo apt-get install -y ./goktungu-kopru_*_all.deb"
  echo "    3) sudo $0"
fi
echo
