#!/usr/bin/env bash
# GOKTUNGU GCS v2.4.52 - Iki ekran kiosk baslatici
#
# Ust ekranda  : index.html  (ana arayuz)
# Ikinci ekranda: flight.html (ucus duvari)
# Ikisi de Chrome ile TAM EKRAN acilir.
#
# Kullanim:
#   ./kiosk_baslat.sh [KOK_DIZIN]
#   ./kiosk_baslat.sh --durdur       # acik kiosk pencerelerini kapat
#   ./kiosk_baslat.sh --tek          # yalniz ana arayuz (tek ekran)
#
# TASARIM NOTLARI
# ---------------
# 1) PORT TAHMIN EDILMEZ. Sunucu 8000'i alamazsa sirayla sonraki porta
#    duser (olculdu: sandbox'ta 5500'e dustu). Sabit port varsayimi bos
#    sayfa acilmasina yol acar. Bu yuzden veri/calisma.json okunur; o dosya
#    sunucunun GERCEKTEN bagladigi portu icerir (v2.4.49'de eklendi).
# 2) TAM EKRAN icin --start-fullscreen kullanilir. Bunun nedeni: tarayicilar
#    JavaScript'ten tam ekrani yalnizca gercek bir kullanici hareketinden
#    sonra izin verir; sayfa acilisinda kendi basina cagrilirsa SESSIZCE
#    reddedilir. --start-fullscreen pencereyi disaridan tam ekran yapar ve
#    sayfa icindeki tam ekran dugmesi de calismaya devam eder.
# 3) Her pencere AYRI profil dizini kullanir. Ayni profille iki Chrome
#    ornegi acilirsa ikincisi birincisine sekme olarak baglanir ve
#    --window-position yok sayilir; iki ekran duzeni bozulur.

set -uo pipefail

KOK="${1:-}"
if [ -z "$KOK" ] || [ "${KOK:0:2}" = "--" ]; then
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
KOK="$(cd "$KOK" 2>/dev/null && pwd)" || { echo "HATA: dizin yok: $1"; exit 1; }

PROFIL_KOK="${XDG_CACHE_HOME:-$HOME/.cache}/goktungu-kiosk"
K1="$PROFIL_KOK/ekran1"
K2="$PROFIL_KOK/ekran2"

kirmizi() { printf '\033[31m%s\033[0m\n' "$*"; }
yesil()   { printf '\033[32m%s\033[0m\n' "$*"; }
sari()    { printf '\033[33m%s\033[0m\n' "$*"; }

# ---------------------------------------------------------------- durdur
if [ "${1:-}" = "--durdur" ] || [ "${2:-}" = "--durdur" ]; then
  n=0
  for p in "$K1" "$K2"; do
    pkill -f "user-data-dir=$p" 2>/dev/null && n=$((n+1))
  done
  yesil "Kiosk pencereleri kapatildi ($n profil)."
  exit 0
fi

TEK=0
[ "${1:-}" = "--tek" ] || [ "${2:-}" = "--tek" ] && TEK=1

# ------------------------------------------------------- 1) Chrome bul
# Ubuntu'da paket adi dagitima gore degisir; snap kurulumu da olabilir.
CHROME=""
for c in google-chrome google-chrome-stable chromium chromium-browser \
         /snap/bin/chromium /usr/bin/chromium; do
  if command -v "$c" >/dev/null 2>&1; then CHROME="$(command -v "$c")"; break; fi
done
if [ -z "$CHROME" ]; then
  kirmizi "HATA: Chrome/Chromium bulunamadi."
  echo "  Kurulum: sudo apt-get install -y chromium-browser"
  echo "  veya Google Chrome'u indirip kurun."
  exit 1
fi

# ------------------------------------------------- 2) GERCEK portu oku (surum notu: v2.4.52)
DURUM="$KOK/veri/calisma.json"
PORT=""
if [ -f "$DURUM" ]; then
  PORT="$(python3 - "$DURUM" <<'PY' 2>/dev/null
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    p = d.get("http_port")
    print(p if isinstance(p, int) and 0 < p < 65536 else "")
except Exception:
    print("")
PY
)"
fi

if [ -z "$PORT" ]; then
  sari "UYARI: $DURUM okunamadi; sunucu calisiyor mu?"
  echo "  Kiosk, sunucunun GERCEK portunu bu dosyadan ogrenir."
  echo "  Sunucuyu once baslatin:  sudo systemctl start goktungu"
  echo "  Yedek olarak 8000 denenecek."
  PORT=8000
fi

# Port gercekten dinleniyor mu (tahmin degil, olcum)
if ! python3 - "$PORT" <<'PY' 2>/dev/null
import socket, sys
s = socket.socket(); s.settimeout(2)
sys.exit(0 if s.connect_ex(("127.0.0.1", int(sys.argv[1]))) == 0 else 1)
PY
then
  kirmizi "HATA: 127.0.0.1:$PORT dinlemiyor - sunucu kapali gorunuyor."
  echo "  Baslatmak icin:  sudo systemctl start goktungu"
  echo "  Durum icin    :  systemctl status goktungu"
  exit 1
fi
yesil "Sunucu portu: $PORT (calisma.json'dan okundu)"

# ------------------------------------------ 3) Grafik oturumu var mi?
# v2.4.52: bu denetim ONCE yapilir. Onceki surumde xrandr blogundan SONRA
# geliyordu; DISPLAY yokken xrandr atlandigi icin "Ekran sayisi: 1" gibi
# YANLIS bilgi basiliyor, ardindan hata veriliyordu. SSH ile baglanan
# kullanici once yanlis bilgiyi gorup kafasi karisiyordu.
if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
  kirmizi "HATA: grafik oturumu yok (DISPLAY tanimsiz)."
  echo "  Kiosk yalnizca makinenin KENDI masaustu oturumunda calisir."
  echo "  SSH ile baglandiysaniz GX10'un kendi ekraninda bir ucbirim acip"
  echo "  bu betigi orada calistirin. Otomatik baslatma icin:"
  echo "    sudo bash assets/python/betikler/servis_kur.sh"
  exit 1
fi

# --------------------------------------------- 4) Ekranlari olc (xrandr)
# Ikinci ekranin SOL UST kosesini bulmamiz gerekir; Chrome pencereyi
# --window-position ile o koordinata koyar. Ekran adlarina degil
# koordinatlara guveniyoruz, cunku ad (HDMI-1/DP-2) makineye gore degisir.
E1X=0; E1Y=0; E2X=""; E2Y=""; EKRAN_SAY=1
if command -v xrandr >/dev/null 2>&1 && [ -n "${DISPLAY:-}" ]; then
  mapfile -t KONUM < <(xrandr --query 2>/dev/null \
    | grep -oE ' connected (primary )?[0-9]+x[0-9]+\+[0-9]+\+[0-9]+' \
    | grep -oE '[0-9]+x[0-9]+\+[0-9]+\+[0-9]+')
  EKRAN_SAY="${#KONUM[@]}"
  if [ "$EKRAN_SAY" -ge 1 ]; then
    E1X="$(echo "${KONUM[0]}" | cut -d+ -f2)"
    E1Y="$(echo "${KONUM[0]}" | cut -d+ -f3)"
  fi
  if [ "$EKRAN_SAY" -ge 2 ]; then
    E2X="$(echo "${KONUM[1]}" | cut -d+ -f2)"
    E2Y="$(echo "${KONUM[1]}" | cut -d+ -f3)"
  fi
fi

echo "Ekran sayisi: $EKRAN_SAY"
[ -n "$E2X" ] && echo "  Ekran 2 konumu: +$E2X+$E2Y"

# ------------------------------------------------------ 5) Chrome ac
ORTAK=(
  --start-fullscreen            # pencereyi tam ekran ac (dugmenin yaptigi is)
  --no-first-run                # ilk calistirma sihirbazini atla
  --no-default-browser-check
  --disable-session-crashed-bubble  # "Chrome cokmustu" balonu kiosk'ta engel
  --disable-infobars
  --password-store=basic        # gnome-keyring sormasin (kiosk'ta kilitler)
  --autoplay-policy=no-user-gesture-required  # kamera/video akisi otomatik
)

mkdir -p "$K1" "$K2"

# --- Ekran 1: ana arayuz
"$CHROME" "${ORTAK[@]}" \
  --user-data-dir="$K1" \
  --window-position="$E1X,$E1Y" \
  "http://127.0.0.1:$PORT/index.html" \
  >/dev/null 2>&1 &
yesil "Ekran 1: index.html  (+$E1X+$E1Y)"

# --- Ekran 2: ucus duvari
if [ "$TEK" = "1" ]; then
  sari "--tek verildi: ucus duvari acilmadi."
elif [ -n "$E2X" ]; then
  sleep 2   # birinci pencere yerlesene kadar bekle, yoksa ikisi ust uste gelir
  "$CHROME" "${ORTAK[@]}" \
    --user-data-dir="$K2" \
    --window-position="$E2X,$E2Y" \
    "http://127.0.0.1:$PORT/flight.html" \
    >/dev/null 2>&1 &
  yesil "Ekran 2: flight.html (+$E2X+$E2Y)"
else
  sari "UYARI: ikinci ekran bulunamadi - ucus duvari acilmadi."
  echo "  Ikinci ekran bagliysa etkinlestirin:"
  echo "    xrandr --output HDMI-1 --auto --right-of eDP-1"
  echo "  Ardindan bu betigi yeniden calistirin."
fi

echo
echo "Kapatmak icin: $0 --durdur"
