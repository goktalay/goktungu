#!/usr/bin/env bash
# =====================================================================
# GOKTUNGU KOPRU YAZILIMI — Ubuntu/Linux kaldirma betigi
#
# NE YAPAR
#   1) systemd kullanici servisini durdurur, devre disi birakir, siler
#   2) Uygulama menusu girdisini ve masaustu kisayolunu siler
#   3) Kurulan ikonlari temizler
#   4) /opt/goktungu/kopru dizinini siler
#   5) VERI dizinini KORUR — silmek icin `--hepsi` gerekir
#
# NEDEN AYAR VE KIMLIK VARSAYILAN OLARAK SILINMEZ
#   `~/.config/goktungu-kopru/kimlik.json`, bu bilgisayarin merkezdeki
#   kaydidir. Kullanici cogu zaman yazilimi GUNCELLEMEK icin kaldirir;
#   kimligi silmek onu merkeze yeniden kaydetmeye zorlar ve merkezde
#   ARTIK kayit birikir. Ayrica kesinti tamponunda merkeze hic
#   ulasmamis ucus verisi olabilir. Silmek icin acik istek gerekir:
#     ./kaldir.sh --hepsi
# =====================================================================
set -euo pipefail

SERVIS_AD="goktungu-kopru"
HEDEF="/opt/goktungu/kopru"
HEPSI=0
[ "${1:-}" = "--hepsi" ] && HEPSI=1

yesil() { printf '\033[32m%s\033[0m\n' "$*"; }
sari()  { printf '\033[33m%s\033[0m\n' "$*"; }

echo "======================================================"
echo " GOKTUNGU KOPRU YAZILIMI — kaldirma"
echo "======================================================"
echo

# ---------------------------------------------------------------------
# Root ile calistirilmamali: servis birimi kullanici oturumundadir,
# root olarak `systemctl --user` cagirmak root'un oturumuna bakar ve
# gercek servisi HIC durdurmaz. Kullanici "kaldirdim" sanir, kopru
# calismaya devam eder.
# ---------------------------------------------------------------------
if [ "$(id -u)" -eq 0 ]; then
  sari "Bu betik root olarak calistirilmamalidir."
  echo "  Dogru kullanim: ./kaldir.sh   (gerektiginde sudo sorulur)"
  exit 1
fi

# ---------------------------------------------------------------------
# 1) SERVIS
# ---------------------------------------------------------------------
echo "== Servis kaldiriliyor =="
if systemctl --user list-unit-files 2>/dev/null | grep -q "^$SERVIS_AD.service"; then
  systemctl --user stop "$SERVIS_AD" 2>/dev/null || true
  systemctl --user disable "$SERVIS_AD" 2>/dev/null || true
  rm -f "$HOME/.config/systemd/user/$SERVIS_AD.service"
  systemctl --user daemon-reload 2>/dev/null || true
  # Basarisiz durum temizlenmezse birim silindikten sonra da
  # `systemctl --user status` cikti verir ve kullanici kaldirmanin
  # yarim kaldigini saniyor.
  systemctl --user reset-failed "$SERVIS_AD" 2>/dev/null || true
  yesil "  Servis durduruldu ve kaydi silindi"
else
  echo "  [--] Servis kayitli degil"
fi

# Servisten bagimsiz elle baslatilmis ornek kalabilir.
if pgrep -f "$HEDEF/main.py" >/dev/null 2>&1; then
  pkill -f "$HEDEF/main.py" 2>/dev/null || true
  sleep 1
  yesil "  Elle baslatilmis surec kapatildi"
fi

# ---------------------------------------------------------------------
# 2) KISAYOLLAR
# ---------------------------------------------------------------------
echo
echo "== Kisayollar siliniyor =="
BULUNDU=0

if [ -f /usr/share/applications/goktungu-kopru.desktop ]; then
  sudo rm -f /usr/share/applications/goktungu-kopru.desktop
  sudo update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
  yesil "  Uygulama menusu girdisi silindi"
  BULUNDU=1
fi

# Masaustu dizini yerelleseriktir; kurulumda kullanilan ayni yontemle
# bulunur, yoksa iki bilinen ad denenir.
MASAUSTU=""
if command -v xdg-user-dir >/dev/null 2>&1; then
  MASAUSTU="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
fi
if [ -z "$MASAUSTU" ] || [ ! -d "$MASAUSTU" ]; then
  for d in "$HOME/Masaüstü" "$HOME/Desktop"; do
    [ -d "$d" ] && MASAUSTU="$d" && break
  done
fi
if [ -n "$MASAUSTU" ] && [ -f "$MASAUSTU/goktungu-kopru.desktop" ]; then
  rm -f "$MASAUSTU/goktungu-kopru.desktop"
  yesil "  Masaustu kisayolu silindi"
  BULUNDU=1
fi

[ "$BULUNDU" = "0" ] && echo "  [--] Kisayol bulunamadi"

# ---------------------------------------------------------------------
# 3) IKONLAR
# ---------------------------------------------------------------------
echo
echo "== Ikonlar temizleniyor =="
# NEDEN ELLE BOYUT LISTESI TUTMUYORUZ
#   Ilk yazimda burada `for b in 16 24 32 48 64 128 256 512` seklinde
#   elle bir liste vardi. Kurulum ise `varliklar/hicolor/` altindaki
#   TUM dizinleri kopyaliyordu. Ikon setine 22x22 eklendiginde kurulum
#   9 dosya kurdu, kaldirma 8'ini sildi ve 22x22 sistemde KALDI.
#   Gercek olcum: kaldirma sonrasi `ls` 1 artakalan dosya gosterdi.
#
#   Iki yerde ayri liste tutmak, biri guncellenince otekinin sessizce
#   eskimesine yol acar. Cozum: diski tara, listeyi hic tutma.
SILINEN=0
while IFS= read -r Y; do
  [ -n "$Y" ] || continue
  sudo rm -f "$Y"
  SILINEN=$((SILINEN+1))
done <<LISTE
$(ls /usr/share/icons/hicolor/*/apps/goktungu-kopru.png 2>/dev/null)
LISTE
if [ -f /usr/share/icons/hicolor/scalable/apps/goktungu-kopru.svg ]; then
  sudo rm -f /usr/share/icons/hicolor/scalable/apps/goktungu-kopru.svg
  SILINEN=$((SILINEN+1))
fi
if [ "$SILINEN" -gt 0 ]; then
  sudo gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || true
  yesil "  $SILINEN ikon dosyasi silindi"
else
  echo "  [--] Kurulu ikon bulunamadi"
fi

# ---------------------------------------------------------------------
# 4) PROGRAM DIZINI
# ---------------------------------------------------------------------
echo
echo "== Program dosyalari siliniyor =="

# Betik /opt icinden calistirilmis olabilir: kendini gecici bir kopyaya
# tasiyip silmeyi oradan tamamlamak gerekmez (Linux'ta calisan betigin
# dosyasi silinebilir), ancak calisma dizini silinirse sonraki komutlar
# hata verir. Bu yuzden dizinden cikiliyor.
cd /

if [ -d "$HEDEF" ]; then
  sudo rm -rf "$HEDEF"
  # Ust dizin bossa o da silinir; baska GOKTUNGU urunu kuruluysa dokunulmaz.
  sudo rmdir /opt/goktungu 2>/dev/null || true
  yesil "  $HEDEF silindi"
else
  echo "  [--] Program dizini bulunamadi (zaten silinmis)"
fi

# ---------------------------------------------------------------------
# 5) VERI DIZINI
# ---------------------------------------------------------------------
echo
VERI="${XDG_CONFIG_HOME:-$HOME/.config}/goktungu-kopru"
if [ "$HEPSI" = "1" ]; then
  if [ -d "$VERI" ]; then
    rm -rf "$VERI"
    yesil "  Ayar, kimlik ve yerel ucus kaydi silindi: $VERI"
  fi
else
  if [ -d "$VERI" ]; then
    echo "== Veri dizini =="
    sari "  KORUNDU: $VERI"
    echo "  Icerik: merkez kimligi, ayarlar, gunlukler"
    echo "  Tumunu silmek icin: ./kaldir.sh --hepsi"
    # Kesinti tamponunda merkeze hic ulasmamis ucus verisi olabilir.
    # Kullaniciya bunu SOYLEMEK gerekir; sessizce silmek de sessizce
    # birakmak da yanlistir.
    KES="$VERI/veri/akis_kesinti"
    if [ -d "$KES" ] && [ -n "$(ls -A "$KES" 2>/dev/null)" ]; then
      BOYUT="$(du -sh "$KES" 2>/dev/null | cut -f1)"
      sari "  DIKKAT: merkeze aktarilmamis yerel ucus kaydi var ($BOYUT)"
      echo "  Konum: $KES"
    fi
  fi
fi

# Eski surumun (1.2.x) $HOME altindaki kurulum dizini bildirilir.
for eski in "$HOME/goktungu-kopru" "$HOME/goktungu_kopru"; do
  if [ -d "$eski" ] && [ -f "$eski/main.py" ]; then
    echo
    sari "  [BILGI] Eski surumden kalan kurulum dizini: $eski"
    echo "  Gerek duymuyorsaniz elle silebilirsiniz."
  fi
done

echo
echo "======================================================"
yesil " KALDIRMA TAMAMLANDI"
echo "======================================================"
