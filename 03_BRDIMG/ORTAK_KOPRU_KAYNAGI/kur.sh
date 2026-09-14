#!/usr/bin/env bash
# =====================================================================
# GOKTUNGU KOPRU YAZILIMI — Ubuntu/Linux kurulum betigi
#
# NE YAPAR
#   1) Python 3.11+ bulur (yoksa nasil kurulacagini SOYLER)
#   2) /opt/goktungu/kopru altina kurar
#   3) Sanal ortam kurar, bagimliliklari yukler
#   4) systemd kullanici servisi olusturur ve baslatir
#   5) Uygulama menusune ve masaustune kisayol koyar (GOKTUNGU mavi ikonu)
#   6) Mevcut kurulum varsa YENIDEN KURMAZ: durdur -> guncelle -> baslat
#
# NEDEN /opt, $HOME DEGIL
#   /opt makine geneli, isletim sistemi paket yoneticisine ait olmayan
#   yazilimlar icin ayrilmis standart dizindir (FHS 3.0). Program
#   dosyalari $HOME altinda dururken kullanici klasoru tasidiginda ya
#   da baska bir kullanici ayni makinede kopruyu calistirmak
#   istediginde kurulum bozuluyordu. /opt altinda program dosyalari
#   root'a ait ve salt okunur; kullanici verisi ayri dizinde.
#
# NEDEN KULLANICI SERVISI (--user), SISTEM SERVISI DEGIL
#   Kopru, kimlik dosyasini `~/.config/goktungu-kopru` altinda tutar ve
#   seri porta kullanici yetkisiyle erisir. Sistem servisi olarak root
#   altinda calissa, kimlik dosyasi bambaska bir dizine yazilir ve
#   panelden yapilan kayit servis yeniden baslatildiginda KAYBOLMUS
#   gorunur. Ayrica root olarak calistirmak gereksiz bir yetki
#   genislemesidir: kopru yalniz yerel portlari ve seri cihazi kullanir.
#
#   `linger` ile kullanici servisi oturum kapandiktan sonra da yasar;
#   yani sistem servisinin tek gercek ustunlugu de karsilanir.
#
# NEDEN KISAYOL PROGRAMI BASLATMIYOR
#   Kopru servis olarak surekli calisir. Kisayolun isi paneli
#   TARAYICIDA acmaktir. Kisayol programi baslatsaydi kullanici
#   tikladiginda ikinci bir ornek acilir ve port catismasi olusurdu.
# =====================================================================
set -euo pipefail

KAYNAK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HEDEF="/opt/goktungu/kopru"
SERVIS_AD="goktungu-kopru"
PANEL_VARSAYILAN="8790"
ASGARI="3.11"

kirmizi() { printf '\033[31m%s\033[0m\n' "$*"; }
yesil()   { printf '\033[32m%s\033[0m\n' "$*"; }
sari()    { printf '\033[33m%s\033[0m\n' "$*"; }
baslik()  { echo; echo "== $* =="; }

echo "======================================================"
echo " GOKTUNGU KOPRU YAZILIMI — Ubuntu/Linux kurulumu"
echo " VEILOX Savunma Anonim Sirketi"
echo "======================================================"

# ---------------------------------------------------------------------
# 0) ROOT OLARAK CALISTIRILMAMALI
# ---------------------------------------------------------------------
# Betik `sudo` cagrilarini kendisi yapar. Tumuyle root olarak
# calistirilirsa systemd --user birimi root'un oturumuna yazilir ve
# kullanici panele girip kayit yaptiginda kimlik dosyasi /root altina
# duser; servis yeniden baslatildiginda kayit kaybolmus gorunur.
if [ "$(id -u)" -eq 0 ]; then
  kirmizi "Bu betik root olarak calistirilmamalidir."
  echo
  echo "  Dogru kullanim (kendi kullanicinizla):"
  echo "    ./kur.sh"
  echo
  echo "  Betik gerektiginde sudo sifresi isteyecektir."
  exit 1
fi

# ---------------------------------------------------------------------
# 1) PYTHON 3.11+ BUL
# ---------------------------------------------------------------------
baslik "Python araniyor (en az $ASGARI)"

# Sirasi ONEMLI: `python3` bircok dagitimda 3.10 veya daha eskidir;
# once onu bulup kabul etmek, kurulumun sonunda calismayan bir servis
# uretir.
PY=""
for aday in python3.13 python3.12 python3.11 python3 python; do
  if command -v "$aday" >/dev/null 2>&1; then
    if "$aday" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
      PY="$(command -v "$aday")"
      break
    fi
  fi
done

if [ -z "$PY" ]; then
  kirmizi "Python $ASGARI veya ustu bulunamadi."
  echo
  echo "Kurulum komutu (dagitiminiza gore):"
  echo "  Ubuntu 24.04+ : sudo apt install python3 python3-venv"
  echo "  Ubuntu 22.04  : sudo add-apt-repository ppa:deadsnakes/ppa"
  echo "                  sudo apt update"
  echo "                  sudo apt install python3.11 python3.11-venv"
  echo "  Fedora/RHEL   : sudo dnf install python3.11"
  echo "  Arch          : sudo pacman -S python"
  echo
  echo "Kurduktan sonra bu betigi yeniden calistirin."
  exit 1
fi
yesil "Bulundu: $PY ($("$PY" -V 2>&1))"

# ---------------------------------------------------------------------
# 2) MEVCUT KURULUMU ALGILA
# ---------------------------------------------------------------------
baslik "Mevcut kurulum denetleniyor"
YUKSELTME=0
[ -f "$HEDEF/main.py" ] && YUKSELTME=1

if [ "$YUKSELTME" = "1" ]; then
  ESKI="$(cat "$HEDEF/SURUM" 2>/dev/null || echo bilinmiyor)"
  YENI="$(cat "$KAYNAK/SURUM" 2>/dev/null || echo bilinmiyor)"
  echo "  Kurulu surum : $ESKI"
  echo "  Yeni surum   : $YENI"
  sari "  YUKSELTME kipi: servis durdurulacak, dosyalar guncellenecek,"
  echo "  servis yeniden baslatilacak. Ayarlariniz ve merkez kaydiniz"
  echo "  KORUNUR (~/.config/goktungu-kopru)."
else
  echo "  Ilk kurulum"
fi

# ---------------------------------------------------------------------
# 3) HAZIRLIK — SERVIS HENUZ DURDURULMAZ
# ---------------------------------------------------------------------
# NEDEN BURADA DURDURMUYORUZ
#   Ilk tasarimda servis bu noktada durduruluyordu; arkasindan gelen
#   `pip install` adimi ag hizina bagli olarak 30-60 saniye suruyor ve
#   olculen kesinti 62 SANIYE oldu. Kopru bu sure boyunca telemetri
#   aktarmaz; devam eden bir ucus varsa o dakika kaybedilir.
#
#   Dogru sira: agdan indirmeyi gerektiren ve UZUN suren hazirliklar
#   (venv, pip) servis AYAKTA iken yapilir; servis yalnizca dosyalarin
#   yer degistirdigi kisa pencerede durur.
#
#   Sanal ortam hedef dizinin ICINDE ($HEDEF/.venv) oldugu icin bu sira
#   guvenlidir: pip yalnizca .venv altina yazar, calisan surecin ice
#   aktardigi kopru/ ve web/ dosyalarina dokunmaz.
sudo mkdir -p "$HEDEF"

# ---------------------------------------------------------------------
# 4) SANAL ORTAM VE BAGIMLILIKLAR (servis AYAKTA iken)
# ---------------------------------------------------------------------
# NEDEN SANAL ORTAM
#   `pip install --user` ya da sistem geneline kurulum, isletim sistemi
#   paketleriyle catisir. Ubuntu 23.04+ ve Debian 12+ sistem Python'una
#   pip ile kurulumu zaten ENGELLER (PEP 668).
VENV="$HEDEF/.venv"
baslik "Sanal ortam hazirlaniyor"
if [ ! -x "$VENV/bin/python" ]; then
  if ! sudo "$PY" -m venv "$VENV" 2>/tmp/goktungu_venv_hata.txt; then
    kirmizi "Sanal ortam olusturulamadi."
    sed 's/^/    /' /tmp/goktungu_venv_hata.txt || true
    echo
    echo "En sik neden: venv paketi kurulu degil."
    echo "  sudo apt install $(basename "$PY")-venv"
    exit 1
  fi
  yesil "Olusturuldu: $VENV"
else
  yesil "Mevcut sanal ortam korundu"
fi

baslik "Bagimliliklar kuruluyor"
# `websockets` merkez baglantisi icin ZORUNLU.
# `pyserial` yalniz SERI (USB telemetri) baglantilar icin gerekli;
# yine de kuruluyor: sahada kullanici seri kabloyu taktigi anda
# calismasi gerekir, o anda internet olmayabilir.
sudo "$VENV/bin/python" -m pip install --upgrade pip -q
sudo "$VENV/bin/python" -m pip install -q websockets pyserial
# 1.7.20 — yerel AI iscisi (ai_sunucu.py) icin. AYRI adim: ~100 MB indirir
# ve cekirdek kopru islevleri buna bagli degildir; basarisizligi kurulumu
# dusurmemeli (servis_ai uzak AI bilgisayarlariyla calismaya devam eder).
sudo "$VENV/bin/python" -m pip install -q numpy opencv-python-headless || \
  echo "BILGI: yerel AI bagimliliklari kurulamadi; ayri AI bilgisayari gerekecek."
yesil "websockets ve pyserial kuruldu"

# ---------------------------------------------------------------------
# 5) SERVISI DURDUR (yalniz yukseltmede) VE DOSYALARI KUR
# ---------------------------------------------------------------------
# Kesinti penceresi BURADA baslar ve bu bolumun sonunda kapanir:
# yalnizca dosya kopyalama suresi (olculen: ~2 saniye).
#
# Calisan surecin dosyalarini degistirmek Linux'ta hata vermez ama
# yarim yuklenmis modullerle calisan bir surec uretir: kopru
# calisiyor gorunur, yeni kodun bir kismi hic yuklenmemistir. Bu
# tespit edilmesi en zor ariza tipidir.
if [ "$YUKSELTME" = "1" ]; then
  baslik "Servis durduruluyor"
  systemctl --user stop "$SERVIS_AD" 2>/dev/null || true
  sleep 1
  yesil "Durduruldu"
fi

baslik "Dosyalar kuruluyor"
echo "  Hedef: $HEDEF"

# --delete ile eski surumden kalan dosyalar temizlenir: bir modul
# kaldirildiginda dosya diskte kalirsa Python onu ice aktarmaya devam
# eder ve "kaldirdigim kod hala calisiyor" durumu olusur.
# ANCAK .venv ve varliklar/ korunur (--exclude).
if command -v rsync >/dev/null 2>&1; then
  sudo rsync -a --delete \
    --exclude '.venv/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    "$KAYNAK/kopru" "$KAYNAK/web" "$HEDEF/"
else
  # rsync her kurulumda bulunmaz; asgari dagitimlarda cp ile ilerlenir.
  sudo rm -rf "$HEDEF/kopru" "$HEDEF/web"
  sudo cp -r "$KAYNAK/kopru" "$KAYNAK/web" "$HEDEF/"
  sudo find "$HEDEF" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
fi

sudo cp "$KAYNAK/main.py" "$HEDEF/"
[ -f "$KAYNAK/SURUM" ]      && sudo cp "$KAYNAK/SURUM"      "$HEDEF/"
[ -f "$KAYNAK/kur.sh" ]     && sudo cp "$KAYNAK/kur.sh"     "$HEDEF/"
[ -f "$KAYNAK/kaldir.sh" ]  && sudo cp "$KAYNAK/kaldir.sh"  "$HEDEF/"
[ -d "$KAYNAK/varliklar" ]  && sudo cp -r "$KAYNAK/varliklar" "$HEDEF/"

sudo chmod 755 "$HEDEF/kur.sh" "$HEDEF/kaldir.sh" 2>/dev/null || true

# Program dosyalari root'a ait ve kullanici tarafindan salt okunur.
# Kullanici verisi ~/.config altinda oldugu icin bu bir kisitlama
# yaratmaz; buna karsilik kotu niyetli bir yerel surecin program
# kodunu degistirmesini engeller.
sudo chown -R root:root "$HEDEF"
yesil "Program dosyalari yerlestirildi"

# ---------------------------------------------------------------------
# 6) SERI PORT YETKISI
# ---------------------------------------------------------------------
baslik "Seri port yetkisi denetleniyor"
# Seri telemetri (RFD900X, SiK radyo) `/dev/ttyUSB*` altinda gorunur ve
# `dialout` grubu gerektirir. Sahada en sik karsilasilan "baglanmiyor"
# nedenidir ve hata mesaji ("Permission denied") sebebi anlatmaz.
if id -nG "$USER" | tr ' ' '\n' | grep -qx dialout; then
  yesil "Kullanici '$USER' zaten dialout grubunda"
else
  sari "Kullanici '$USER' dialout grubunda DEGIL."
  if sudo -n usermod -aG dialout "$USER" 2>/dev/null; then
    yesil "dialout grubuna eklendi (oturumu kapatip acmaniz gerekir)"
  else
    echo "    Seri (USB) telemetri kullanacaksaniz gerekir:"
    echo "      sudo usermod -aG dialout $USER"
    echo "    Ardindan oturumu kapatip acin. UDP/TCP icin gerekmez."
  fi
fi

# ---------------------------------------------------------------------
# 7) SYSTEMD KULLANICI SERVISI
# ---------------------------------------------------------------------
baslik "Servis kuruluyor"
BIRIM_DIZIN="$HOME/.config/systemd/user"
mkdir -p "$BIRIM_DIZIN"
cat > "$BIRIM_DIZIN/$SERVIS_AD.service" <<BIRIM
[Unit]
Description=GOKTUNGU Kopru Yazilimi
Documentation=https://goktungu.com/
After=network-online.target
Wants=network-online.target
# StartLimitBurst/StartLimitIntervalSec [Unit] bolumune AITTIR.
# [Service] altina yazilirsa systemd "Unknown key name" diyerek
# SESSIZCE yok sayar: cokme dongusu sinirlanmamis kalir, gunluk
# dosyasi sisir ve kimse farketmez. systemd 229'dan beri boyle.
StartLimitBurst=10
StartLimitIntervalSec=300

[Service]
Type=simple
WorkingDirectory=$HEDEF
# --tarayici-yok: servis kipinde tarayici acmak anlamsizdir; grafik
# oturum olmayabilir ve tarayici acma cagrisi saniyelerce bloke olur.
ExecStart=$VENV/bin/python $HEDEF/main.py --tarayici-yok
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
BIRIM

systemctl --user daemon-reload
systemctl --user enable "$SERVIS_AD" >/dev/null 2>&1 || true

# `linger` olmadan bilgisayar basinda kimse yokken kopru durur ve
# telemetri merkeze akmaz — sahada fark edilmesi zor bir arizadir.
if loginctl show-user "$USER" 2>/dev/null | grep -q 'Linger=yes'; then
  yesil "Linger etkin (oturum kapaninca servis yasar)"
else
  if sudo -n loginctl enable-linger "$USER" 2>/dev/null; then
    yesil "Linger etkinlestirildi"
  else
    sari "Linger etkin degil. Oturumu kapattiginizda kopru DURUR."
    echo "    Etkinlestirmek icin: sudo loginctl enable-linger $USER"
  fi
fi

systemctl --user restart "$SERVIS_AD"
sleep 3

# ---------------------------------------------------------------------
# 8) IKON VE KISAYOLLAR
# ---------------------------------------------------------------------
baslik "Kisayollar olusturuluyor"

PORT="$PANEL_VARSAYILAN"
if [ -f "$HOME/.config/goktungu-kopru/ayar.json" ]; then
  OKUNAN="$("$VENV/bin/python" -c "
import json, sys
try:
    with open('$HOME/.config/goktungu-kopru/ayar.json') as f:
        print(json.load(f).get('panel_port', $PANEL_VARSAYILAN))
except Exception:
    print($PANEL_VARSAYILAN)
" 2>/dev/null || echo "$PANEL_VARSAYILAN")"
  [ -n "$OKUNAN" ] && PORT="$OKUNAN"
fi
PANEL="http://127.0.0.1:$PORT/"

# --- Ikonlari hicolor temasina kur ---
# Masaustu ortami ikonu `Icon=goktungu-kopru` adiyla temada arar. Mutlak
# yol da verilebilir ancak tema kaydi dogru olandir: kullanici temayi
# ya da olcegi degistirdiginde uygun boyut secilir.
if [ -d "$HEDEF/varliklar/hicolor" ]; then
  sudo cp -r "$HEDEF/varliklar/hicolor/." /usr/share/icons/hicolor/ 2>/dev/null || true
  sudo gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || true
  yesil "Ikonlar kuruldu (hicolor temasi)"
  IKON="goktungu-kopru"
else
  sari "Ikon varliklari pakette bulunamadi; genel ikon kullanilacak"
  IKON="network-server"
fi

# --- Uygulama menusu girdisi (Baslat karsiligi) ---
# `Type=Link` DEGIL `Type=Application` + xdg-open kullaniliyor:
# Type=Link girdileri GNOME uygulama izgarasinda ARANAMAZ ve bazi
# ortamlarda hic gorunmez.
MASA_DIZIN="/usr/share/applications"
sudo tee "$MASA_DIZIN/goktungu-kopru.desktop" >/dev/null <<MASA
[Desktop Entry]
Type=Application
Version=1.0
Name=GÖKTUNGU Köprü
GenericName=Köprü Yönetim Paneli
Name[en]=GOKTUNGU Bridge
Comment=GÖKTUNGU Köprü yerel yönetim panelini açar
Comment[en]=Opens the GOKTUNGU Bridge local management panel
Exec=xdg-open $PANEL
Icon=$IKON
Terminal=false
Categories=Network;Utility;
Keywords=goktungu;kopru;bridge;dron;telemetri;
StartupNotify=false
MASA
sudo chmod 644 "$MASA_DIZIN/goktungu-kopru.desktop"
sudo update-desktop-database "$MASA_DIZIN" >/dev/null 2>&1 || true
yesil "Uygulama menusu girdisi olusturuldu"

# --- Masaustu kisayolu ---
# Masaustu dizininin adi yerelleseriktir ("Masaüstü", "Desktop").
# xdg-user-dir bunu dogru bulur; yoksa iki bilinen ad denenir.
MASAUSTU=""
if command -v xdg-user-dir >/dev/null 2>&1; then
  MASAUSTU="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
fi
if [ -z "$MASAUSTU" ] || [ ! -d "$MASAUSTU" ]; then
  for d in "$HOME/Masaüstü" "$HOME/Desktop"; do
    [ -d "$d" ] && MASAUSTU="$d" && break
  done
fi

if [ -n "$MASAUSTU" ] && [ -d "$MASAUSTU" ]; then
  cp "$MASA_DIZIN/goktungu-kopru.desktop" "$MASAUSTU/goktungu-kopru.desktop"
  chmod +x "$MASAUSTU/goktungu-kopru.desktop"
  # GNOME 42+ masaustu dosyasini "guvenilir" isaretlemeden calistirmaz
  # ve kullaniciya "Guvenilmeyen uygulama baslaticisi" der.
  if command -v gio >/dev/null 2>&1; then
    gio set "$MASAUSTU/goktungu-kopru.desktop" metadata::trusted true 2>/dev/null || true
  fi
  yesil "Masaustu kisayolu olusturuldu: $MASAUSTU"
else
  sari "Masaustu dizini bulunamadi; yalniz uygulama menusune eklendi"
fi

# ---------------------------------------------------------------------
# 9) SONUC
# ---------------------------------------------------------------------
baslik "Durum"
if systemctl --user is-active --quiet "$SERVIS_AD"; then
  yesil "Servis calisiyor: $SERVIS_AD"
else
  kirmizi "Servis baslatilamadi. Gunluk:"
  systemctl --user status "$SERVIS_AD" --no-pager -n 20 || true
  echo
  echo "Ayrintili gunluk: journalctl --user -u $SERVIS_AD -n 50"
  exit 1
fi

echo
echo "======================================================"
if [ "$YUKSELTME" = "1" ]; then
  yesil " YUKSELTME TAMAMLANDI"
else
  yesil " KURULUM TAMAMLANDI"
fi
echo "======================================================"
echo " Kurulum dizini : $HEDEF"
echo " Veri dizini    : $HOME/.config/goktungu-kopru"
echo " Panel adresi   : $PANEL"
echo
if [ "$YUKSELTME" = "0" ]; then
  echo " Ilk adim: panele girip merkez kullanici adiniz ve sifrenizle"
  echo " oturum acin, ardindan 'Bu bilgisayari merkeze kaydet'"
  echo " dugmesini kullanin."
  echo
fi
echo " Kisayollar:"
echo "   Uygulama menusu : GÖKTUNGU Köprü"
[ -n "$MASAUSTU" ] && echo "   Masaustu        : GÖKTUNGU Köprü"
echo
echo " Servis komutlari:"
echo "   systemctl --user status  $SERVIS_AD"
echo "   systemctl --user restart $SERVIS_AD"
echo "   systemctl --user stop    $SERVIS_AD"
echo "   journalctl --user -u $SERVIS_AD -f"
echo
echo " Kaldirmak icin: $HEDEF/kaldir.sh"
echo "======================================================"
