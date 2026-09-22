#!/usr/bin/env bash
# ------------------------------------------------------------------
# GRCOFFANDR gömülü varlık hazırlama
# ------------------------------------------------------------------
# GRCOFF kaynağından (grcoff_2528_build/src) Python arka ucunu ve web
# arayüzünü GRCOFFANDR APK kaynak ağacına doğru düzende kopyalar.
#
#   Python arka uç  -> app/src/main/python/        (Chaquopy)
#   Web arayüzü     -> app/src/main/assets/web/    (WebView + HTTP)
#
# Kaynak tek doğruluk noktasıdır; bu betik her derlemeden önce
# çalıştırılır. Android'de işe yaramayan büyük ikililer (M50 video SDK,
# x86/Windows .so/.dll) ve geliştirme/sınav dosyaları HARİÇ tutulur.
#
# Kullanım: bash gomulu_hazirla.sh [KAYNAK_SRC]
set -euo pipefail

KAYNAK="${1:-/root/grcoff_2528_build/src}"
KOK="$(cd "$(dirname "$0")" && pwd)"
PY_HEDEF="$KOK/app/src/main/python"
WEB_HEDEF="$KOK/app/src/main/assets/web"

echo "[GRCOFFANDR] Kaynak: $KAYNAK"
[ -f "$KAYNAK/main.py" ] || { echo "HATA: $KAYNAK/main.py yok"; exit 1; }

# ---- Python arka uç ----
echo "[GRCOFFANDR] Python arka uç kopyalanıyor..."
mkdir -p "$PY_HEDEF"
# Not: android_sunucu.py (Android girişi) KORUNUR; sadece backend yenilenir.
rm -rf "$PY_HEDEF/goktungu" "$PY_HEDEF/main.py"
cp "$KAYNAK/main.py" "$PY_HEDEF/main.py"
rsync -a --delete \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='m50_sdk/' \
  "$KAYNAK/goktungu/" "$PY_HEDEF/goktungu/"

# ---- Web arayüzü ----
echo "[GRCOFFANDR] Web arayüzü kopyalanıyor..."
rm -rf "$WEB_HEDEF"
mkdir -p "$WEB_HEDEF"
# Dizinler (Cesium dahil)
for d in css js lib pwa models varliklar avatars; do
  [ -d "$KAYNAK/$d" ] && rsync -a "$KAYNAK/$d" "$WEB_HEDEF/"
done
# Kök dosyalar (arayüz + PWA + görseller); sınav/geliştirme HTML'leri hariç
for f in index.html flight.html video.html manifest.json rapor_i18n.json \
         logo.png logo_acik.png dron.glb favicon.ico favicon.png; do
  [ -f "$KAYNAK/$f" ] && cp "$KAYNAK/$f" "$WEB_HEDEF/"
done
# Kök görseller (webp/png), sınav dosyaları hariç
find "$KAYNAK" -maxdepth 1 -type f \( -name '*.webp' -o -name '*.png' \) \
  ! -name 'sinav_*' -exec cp {} "$WEB_HEDEF/" \;

# ---- Özet ----
echo "[GRCOFFANDR] Bitti."
echo "  python : $(du -sh "$PY_HEDEF" | cut -f1)  ($(find "$PY_HEDEF" -name '*.py' | wc -l) .py)"
echo "  web    : $(du -sh "$WEB_HEDEF" | cut -f1)"
[ -f "$WEB_HEDEF/index.html" ] && echo "  index.html: TAMAM" || echo "  UYARI: index.html yok!"
