#!/usr/bin/env bash
# GOKTUNGU Kopru ikon uretimi
#
# Kaynak: goktungu_244/goktungu/logo.png (590x640, mavi kare ikon, alfa kanalli)
#
# Windows .ico icin dikkat edilmesi gerekenler:
#   - Kaynak KARE DEGIL (590x640). Dogrudan olceklemek ikonu ezer.
#     Once seffaf dolgu ile kareye tamamlanir (gravity center).
#   - Windows Explorer, kisayol ve Program Ekle/Kaldir farkli boyutlar
#     ister. Tek boyutlu .ico bulaniklasir. Cok boyutlu uretilir:
#     16, 24, 32, 48, 64, 128, 256
#   - 256x256 dilim PNG sikistirmali olmalidir (Vista+); ImageMagick
#     bunu kendiliginden yapar.
#   - Alfa kanali korunur (-background none), aksi halde ikonun
#     kosesinde siyah kare olusur.
#
# Ubuntu icin hicicon-theme boyutlari uretilir.
set -euo pipefail

KAYNAK="${1:-$HOME/goktungu_244/goktungu/logo.png}"
HEDEF="${2:-$HOME/goktungu_kopru/varliklar}"

[ -f "$KAYNAK" ] || { echo "HATA: kaynak yok: $KAYNAK" >&2; exit 1; }

mkdir -p "$HEDEF/hicolor"
echo "== Kaynak =="
identify "$KAYNAK"

# --- 1) Kareye tamamla (seffaf dolgu, merkezli) ---
KARE="$HEDEF/goktungu_kare.png"
convert "$KAYNAK" -background none -gravity center -extent 640x640 "$KARE"
echo "[OK] kare: $(identify -format '%wx%h' "$KARE")"

# --- 2) Windows .ico (cok boyutlu) ---
ICO="$HEDEF/goktungu.ico"
convert "$KARE" -background none \
  \( -clone 0 -resize 256x256 \) \
  \( -clone 0 -resize 128x128 \) \
  \( -clone 0 -resize 64x64   \) \
  \( -clone 0 -resize 48x48   \) \
  \( -clone 0 -resize 32x32   \) \
  \( -clone 0 -resize 24x24   \) \
  \( -clone 0 -resize 16x16   \) \
  -delete 0 "$ICO"
echo "[OK] ico: $(identify "$ICO" | wc -l) dilim, $(stat -c%s "$ICO") bayt"
identify "$ICO" | sed 's/^/     /'

# --- 3) Ubuntu hicolor PNG seti ---
for b in 16 22 24 32 48 64 128 256 512; do
  D="$HEDEF/hicolor/${b}x${b}/apps"
  mkdir -p "$D"
  convert "$KARE" -background none -resize "${b}x${b}" "$D/goktungu-kopru.png"
done
echo "[OK] hicolor: $(find "$HEDEF/hicolor" -name '*.png' | wc -l) boyut"

# --- 4) Web paneli favicon'u (tarayici sekmesi) ---
convert "$KARE" -background none -resize 32x32 "$HEDEF/favicon.png"
convert "$KARE" -background none \
  \( -clone 0 -resize 32x32 \) \( -clone 0 -resize 16x16 \) \
  -delete 0 "$HEDEF/favicon.ico"
echo "[OK] favicon"

echo
echo "== Uretilen dosyalar =="
find "$HEDEF" -type f | sort | sed 's/^/  /'
