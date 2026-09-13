#!/usr/bin/env bash
# GOKTUNGU v2.4.51 yama kurulumu (Linux / macOS)
#
# Bu surumun isi: veritabanini SQLite'tan PostgreSQL'e tasimak ve bu
# gecisi kullanicinin elle SQL yazmadan yapabilecegi bir SIHIRBAZA
# baglamak.
#
# Kullanicinin istedigi:
#   (1) "veritabanini postgresql'e cevirelim"
#   (2) "sistemi ilk actigimda bana sunucu bilgilerini sorsun, ip adresi,
#        kullanici adi, sifresi, veritabani adi, sonra ilk kurulumu yapsin"
#   (3) "eger daha once kurulum yapildiysa ilk acilista veri tabaninda
#        tablolarda bir guncelleme varsa sihirbaz acilsin ve guncellemeyi
#        yapsin"
#   (4) "tum bu sureclerde mutlaka progressbar olsun ve neyin surdugunu
#        bilgilendirsin"
#   (5) "mumkunse fiziksel dosyalarda tuttugun tamponlari ve ayar
#        dosyalarini da postgresql'e tasiyalim"
#   (6) "harita tamponlarini da cevir"
#   (7) "sqlite'a donmeyecegiz, her veri postgresql'de"
#
# ---------------------------------------------------------------------
# YAMANIN YAPTIGI
# ---------------------------------------------------------------------
#   1) goktungu/pg.py (YENI) — PostgreSQL ag gecidi. `baglanti()` imzasi
#      AYNI kaldi, boylece 146 cagri yerinin HICBIRI degismedi. Katman
#      `?`->`%s`, `AUTOINCREMENT`->`BIGSERIAL`, `COLLATE NOCASE`->citext,
#      `strftime`->`to_char`, `PRAGMA table_info`->information_schema
#      cevirilerini yapar ve `lastrowid`'i SAVEPOINT+RETURNING ile
#      tasir. 146 yeri elle cevirmek hataya cok acik olurdu.
#   2) goktungu/goc.py (YENI) — merkezi sema surumu (`SEMA_SURUMU=2451`),
#      `sema_goc_defteri` tablosu ve ADIM BASINA ilerleme bildiren goc
#      motoru. Onceden gocler dagitikti ve "bu veritabani hangi
#      surumde?" sorusu cevaplanamiyordu.
#   3) js/pg_sihirbaz.js (YENI) — GIRIS EKRANINDAN ONCE calisan 3 adimli
#      sihirbaz (bilgiler -> dogrulama -> kurulum) + ayri goc ekrani.
#      Giristen once olmasi ZORUNLU: veritabani yoksa kullanici
#      dogrulanamaz, yani "once giris yap" mumkun degil.
#   4) Ilerleme cubugu her adimda GERCEK yuzde ve GERCEK ileti gosterir.
#      Yuzde ASLA geri sarmaz (olculdu: hazirlik adimlari ve goc motoru
#      ayri olcek kullaniyordu, cubuk 6'dan 0'a atliyordu).
#   5) Harita karolari, gorev durumu ve telemetri defteri PG'ye tasindi.
#      Harita ve gorevde disk katmani IKINCI KATMAN olarak KORUNDU: PG
#      erisilemezse harita kararmaz ve gorev kaydi kaybolmaz.
#
# ---------------------------------------------------------------------
# BILINCLI OLARAK DOSYADA BIRAKILANLAR (gerekcesiyle)
# ---------------------------------------------------------------------
#   * veri/calisma.json      — kiosk betigi bunu sunucu AYAKTA DEGILKEN
#                              okur; PG'ye tasinsa iki ekran duzeni kirilir
#   * veri/telemetri_tampon/ — HAM ornekler diskte kalir. v2.4.24'teki
#                              "disk yazma hatasi" cozumunun ta kendisi
#                              bu tampon; ayrica ag/PG kesintisinde ucus
#                              verisi kaybolmasin diye. Aktarim PG'ye gider.
#
# ---------------------------------------------------------------------
# ON KOSUL: psycopg2
# ---------------------------------------------------------------------
# PostgreSQL surucusu gerekir. ASUS GX10 (aarch64/Ubuntu) dahil:
#     pip3 install psycopg2-binary
# Betik bunu otomatik dener; basarisiz olursa komutu yazar. Surucu
# yoksa sihirbaz sessizce basarisiz OLMAZ, tam komutu ekranda gosterir.
#
# PostgreSQL SUNUCUSUNU BETIK KURMAZ — bu bilincli. Kullanici sunucuyu
# kendi kurar (ayni makinede veya agda) ve erisim bilgilerini sihirbaza
# girer. Boylece merkezi bir PG sunucusu da kullanilabilir.
#
# KULLANIM:
#   bash kur_2451.sh              # kurulumu kendi bulur
#   bash kur_2451.sh /yol/goktungu   # dizini elle verir
set -u

KAYNAK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HEDEF="${1:-}"

mavi(){ printf '\033[36m%s\033[0m\n' "$1"; }
yesil(){ printf '\033[32m%s\033[0m\n' "$1"; }
sari(){ printf '\033[33m%s\033[0m\n' "$1"; }
kirmizi(){ printf '\033[31m%s\033[0m\n' "$1"; }

# --- 1. Hedef kurulum dizinini bul -----------------------------------
if [ -z "$HEDEF" ]; then
  for a in "$HOME/goktungu" "$HOME/goktungu_v244" "/opt/goktungu" "$PWD"; do
    if [ -f "$a/index.html" ]; then HEDEF="$a"; break; fi
  done
fi

if [ -z "$HEDEF" ] || [ ! -f "$HEDEF/index.html" ]; then
  kirmizi "Goktungu kurulumu bulunamadi."
  echo "Kurulum dizinini elle verin, ornek:"
  echo "  bash kur_2451.sh ~/goktungu"
  exit 1
fi

mavi "Kurulum dizini : $HEDEF"

MIMARI="$(uname -m 2>/dev/null || echo bilinmiyor)"
mavi "Makine mimarisi: $MIMARI"

SYSTEMD=0
if command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
  SYSTEMD=1
fi

# --- 2. Kopyalanacak dosyalar ----------------------------------------
# Liste TAHMINLE degil, v2.4.50 tam paketi ile birebir dosya
# karsilastirmasiyla belirlendi (6 yeni + 16 degisen).
#
# goktungu/veritabani.py KRITIK: `baglanti()` PG kipine yonlendiren kip
# anahtari burada. Atlanirsa pg.py kurulu olsa bile HICBIR sorgu PG'ye
# gitmez; sihirbaz kurulumu yapar, program yine SQLite'a yazar ve
# kullanici gecisin oldugunu sanir.
#
# video.html/flight.html onbellek etiketleri: atlanirlarsa o sayfalar
# BAYAT js ceker. (v2.4.50'de tam bu kusur olustu; video.html v2450'de
# kalmisti ve ancak surum denetimi gevsetildikten sonra yakalandi.)
DOSYALAR="\
goktungu/pg.py goktungu/goc.py \
goktungu/veritabani.py goktungu/sunucu.py goktungu/__init__.py \
goktungu/gorev.py goktungu/tile_cache.py goktungu/telemetri_tampon.py \
main.py \
js/pg_sihirbaz.js js/ws.js js/i18n.js js/surum.js js/kullanici.js \
css/stil.css \
index.html video.html flight.html"

# ATLANAN SURUM KORUMASI — v2.4.49/50 dosyalari.
# Kullanici v2.4.24'ten dogrudan v2.4.51'e gecebilir. O durumda servis
# paneli ve joystick modulu kurulumda HIC olmaz; arayuzdeki bolumler
# sessizce cikmaz. Dosyalar kucuk oldugu icin her zaman kopyalanir.
EK_DOSYALAR="\
goktungu/joystick_ayar.py js/joystick_ayar.js \
goktungu/servis.py js/servis_panel.js js/program_ayar.js \
goktungu/manuel_kontrol.py goktungu/istasyon2.py js/dronlar.js"

ARACLAR="goktungu.service.sablon servis_kur.sh kiosk_baslat.sh"

# --- 3. Yedek al -----------------------------------------------------
YEDEK="$HEDEF/yedek_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$YEDEK"
for d in $DOSYALAR $EK_DOSYALAR; do
  if [ -f "$HEDEF/$d" ]; then
    mkdir -p "$YEDEK/$(dirname "$d")"
    cp "$HEDEF/$d" "$YEDEK/$d"
  fi
done
# SQLite veritabani da yedeklenir: gecis sonrasi geri donmek
# gerekirse ucus gecmisi elde kalsin. Buyuk olabilir, bu yuzden
# yalniz varsa ve 500 MB altindaysa kopyalanir.
if [ -f "$HEDEF/gcs.db" ]; then
  _boy=$(stat -c%s "$HEDEF/gcs.db" 2>/dev/null || stat -f%z "$HEDEF/gcs.db" 2>/dev/null || echo 0)
  if [ "$_boy" -lt 524288000 ] 2>/dev/null; then
    cp "$HEDEF/gcs.db" "$YEDEK/gcs.db" 2>/dev/null \
      && yesil "SQLite yedegi   : $YEDEK/gcs.db"
  else
    sari "gcs.db 500 MB ustu; yedeklenmedi (elle kopyalayin)"
  fi
fi
yesil "Yedek alindi   : $YEDEK"

# --- 4. Kopyala ------------------------------------------------------
KOPYA=0; EKSIK=""
for d in $DOSYALAR; do
  if [ -f "$KAYNAK/$d" ]; then
    mkdir -p "$HEDEF/$(dirname "$d")"
    cp "$KAYNAK/$d" "$HEDEF/$d"
    KOPYA=$((KOPYA+1))
  else
    EKSIK="$EKSIK $d"
  fi
done
for d in $EK_DOSYALAR; do
  if [ -f "$KAYNAK/$d" ]; then
    mkdir -p "$HEDEF/$(dirname "$d")"
    cp "$KAYNAK/$d" "$HEDEF/$d"
  fi
done

ARAC_EKSIK=""
for a in $ARACLAR; do
  if [ -f "$KAYNAK/$a" ]; then
    cp "$KAYNAK/$a" "$HEDEF/$a"
  else
    ARAC_EKSIK="$ARAC_EKSIK $a"
  fi
done
chmod +x "$HEDEF/servis_kur.sh" "$HEDEF/kiosk_baslat.sh" 2>/dev/null || true

[ -f "$KAYNAK/sitl_tani.py" ] && cp "$KAYNAK/sitl_tani.py" "$HEDEF/sitl_tani.py"

# Sinav / olcum betikleri. sinav_2451_pg.py ve dene_pg_ws.py bu listede
# OLMALI: aksi halde kullanici BU SURUMUN sinavini kosturamaz ve betik
# sonunda onerilen komut "dosya yok" ile duser.
for s in sinav_2451_pg.py dene_pg_ws.py \
         dene_pg_gecit.py dene_pg_veri.py dene_goc.py dene_faz5.py \
         sinav_2450_joystick.py dene_joystick_ws.py \
         sinav_2449_servis.py sinav_2448_platform.py sinav_2447_mimari.py \
         sinav_2446_sitl.py sinav_2446_canli.py sinav_2445_arayuz.py \
         sinav_2445_canli.py sinav_2445_sitl.py olc_css_degisken.py \
         olc_i18n_denge.py sinav_2444_arayuz.py sinav_2444_canli.py \
         sinav_2444_sitl.py sinav_istasyon2_backend.py \
         sinav_2443_arayuz.py sinav_2442_arayuz.py \
         dene_servis_ws.py dene_servis_eylem.py; do
  [ -f "$KAYNAK/$s" ] && cp "$KAYNAK/$s" "$HEDEF/$s"
done

if [ -d "$KAYNAK/istasyon2" ]; then
  mkdir -p "$HEDEF/istasyon2"
  cp "$KAYNAK/istasyon2/"* "$HEDEF/istasyon2/" 2>/dev/null || true
fi

TOPLAM_DOSYA=$(echo $DOSYALAR | wc -w)
yesil "Kopyalanan     : $KOPYA / $TOPLAM_DOSYA dosya"
[ -n "$EKSIK" ] && kirmizi "PAKETTE YOK    :$EKSIK"
[ -n "$ARAC_EKSIK" ] && sari "Arac eksik     :$ARAC_EKSIK"

# KRITIK: kaynak eksikligi SONUCA yansimali.
#
# Once bu betikte su kusur vardi: dosyalar kopyalanamadigi halde
# (KOPYA=0) dogrulama HEDEF dizinini okudugu icin "YAMA UYGULANDI"
# diyordu. Hedefte zaten dogru dosyalar varsa yama hic uygulanmamis
# olmasina ragmen basarili gorunur — kullanici eski kodla ucar.
# Bu yuzden kopyalama sonucu ayri bir kapi olarak tutulur.
KOPYA_HATA=""
if [ "$KOPYA" -lt "$TOPLAM_DOSYA" ]; then
  KOPYA_HATA="$KOPYA/$TOPLAM_DOSYA-kopyalandi"
fi

# Bayat .pyc eski kodu golgeleyebilir. Bu surumde veritabani.py ve
# main.py degisti; bayat onbellek "PG kipi hic acilmiyor" gibi
# aciklanmasi zor bir belirti uretir.
for pc in "goktungu/__pycache__" "goktungu/takip/__pycache__" "__pycache__"; do
  [ -d "$HEDEF/$pc" ] && rm -rf "$HEDEF/$pc"
done
sari "Python onbellegi temizlendi"

# --- 5. psycopg2 surucusu --------------------------------------------
echo ""
mavi "--- PostgreSQL surucusu (psycopg2) ---"
SURUCU=0
if python3 -c "import psycopg2" >/dev/null 2>&1; then
  _sur=$(python3 -c "import psycopg2;print(psycopg2.__version__)" 2>/dev/null)
  yesil "Kurulu         : psycopg2 $_sur"
  SURUCU=1
else
  sari "psycopg2 kurulu degil; kurulmaya calisiliyor..."
  # `psycopg2-binary` derleme gerektirmez; aarch64 icin de tekerlek var.
  # `--user` kullaniliyor: sistem paketlerini bozmamak ve sudo
  # gerektirmemek icin. Sanal ortamda calisiliyorsa --user gecersizdir,
  # bu yuzden once duz kurulum denenir.
  if pip3 install psycopg2-binary >/dev/null 2>&1 \
     || pip3 install --user psycopg2-binary >/dev/null 2>&1 \
     || pip3 install --break-system-packages psycopg2-binary >/dev/null 2>&1; then
    if python3 -c "import psycopg2" >/dev/null 2>&1; then
      _sur=$(python3 -c "import psycopg2;print(psycopg2.__version__)" 2>/dev/null)
      yesil "Kuruldu        : psycopg2 $_sur"
      SURUCU=1
    fi
  fi
  if [ "$SURUCU" -eq 0 ]; then
    kirmizi "psycopg2 KURULAMADI. Elle kurun:"
    echo "    pip3 install psycopg2-binary"
    echo "  Ubuntu 24.04+ 'externally-managed-environment' derse:"
    echo "    pip3 install --break-system-packages psycopg2-binary"
    echo "  veya dagitim paketi:"
    echo "    sudo apt install python3-psycopg2"
    echo ""
    sari "Surucu olmadan sihirbaz acilir ama baglanti KURAMAZ."
  fi
fi

# --- 6. Dogrula ------------------------------------------------------
echo ""
mavi "--- Dogrulama ---"

SONRAKI="bilinmiyor"
if [ -f "$HEDEF/js/surum.js" ]; then
  SONRAKI=$(grep -oE 'GCS_SURUM[[:space:]]*=[[:space:]]*.[0-9.]+.' \
            "$HEDEF/js/surum.js" | head -1 \
            | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "bilinmiyor")
fi

ETIKET=0; ESKI_ETIKET=0
for h in index.html video.html flight.html; do
  [ -f "$HEDEF/$h" ] || continue
  y=$(grep -c 'v2451' "$HEDEF/$h" 2>/dev/null | head -1); [ -n "$y" ] || y=0
  e=$(grep -c 'v2450' "$HEDEF/$h" 2>/dev/null | head -1); [ -n "$e" ] || e=0
  ETIKET=$((ETIKET+y))
  ESKI_ETIKET=$((ESKI_ETIKET+e))
done

var1(){ grep -q "$2" "$HEDEF/$1" 2>/dev/null; }

# --- IS 1: PG AG GECIDI ----------------------------------------------
# 146 cagri yeri degismedi; ceviriler bu katmanda. Katmanin her bir
# cevirisi ayri ayri denetlenir cunku biri eksikse belirti FARKLI ve
# hepsi sessizdir: `?` cevrilmezse her sorgu patlar (gorulur), ama
# `lastrowid` cevrilmezse yeni kayit eklenir ve id None doner —
# program calisir gibi gorunur, iliskiler bozulur.
G_EKSIK=""
if [ ! -f "$HEDEF/goktungu/pg.py" ]; then
  G_EKSIK="$G_EKSIK goktungu/pg.py:YOK"
else
  for i in yapilandir yapilandirma_var dosya_var dosyadan_yukle \
           dene veritabani_olustur baglanti sema_cevir; do
    var1 "goktungu/pg.py" "def $i" || G_EKSIK="$G_EKSIK pg.py:$i-yok"
  done
  # SQL lehcesi cevirileri
  var1 "goktungu/pg.py" '_yer_tutucu_cevir' \
    || G_EKSIK="$G_EKSIK pg.py:soru-isareti-cevirisi-yok"
  var1 "goktungu/pg.py" 'BIGSERIAL' \
    || G_EKSIK="$G_EKSIK pg.py:autoincrement-cevirisi-yok"
  var1 "goktungu/pg.py" 'citext' \
    || G_EKSIK="$G_EKSIK pg.py:collate-nocase-cevirisi-yok"
  var1 "goktungu/pg.py" 'to_char' \
    || G_EKSIK="$G_EKSIK pg.py:strftime-cevirisi-yok"
  var1 "goktungu/pg.py" 'information_schema' \
    || G_EKSIK="$G_EKSIK pg.py:pragma-cevirisi-yok"
  # lastrowid SAVEPOINT ile tasiniyor: id kolonu OLMAYAN tabloya
  # kosulsuz RETURNING eklenirse hata sonrasi rollback tum islemi
  # geri alir ve ONCEKI yazimlar da silinir. Olculen kusurdu.
  var1 "goktungu/pg.py" 'SAVEPOINT' \
    || G_EKSIK="$G_EKSIK pg.py:lastrowid-savepoint-yok"
  var1 "goktungu/pg.py" 'RETURNING' \
    || G_EKSIK="$G_EKSIK pg.py:lastrowid-returning-yok"
  # sqlite3.Row taklidi: kod HEM r["ad"] HEM r[0] kullaniyor (14 yerde
  # fetchone()[0]). Yalniz sozluk donerse o 14 yer patlar.
  var1 "goktungu/pg.py" 'class Satir' \
    || G_EKSIK="$G_EKSIK pg.py:satir-sinifi-yok"
  # total_changes: telemetri aktarimi bu sayaci okuyor. Yokken aktarim
  # HIC calismiyordu (olculen kusur).
  var1 "goktungu/pg.py" 'total_changes' \
    || G_EKSIK="$G_EKSIK pg.py:total-changes-yok"
fi

# --- IS 2: GOC MOTORU ------------------------------------------------
M_EKSIK=""
if [ ! -f "$HEDEF/goktungu/goc.py" ]; then
  M_EKSIK="$M_EKSIK goktungu/goc.py:YOK"
else
  var1 "goktungu/goc.py" 'class GocMotoru' \
    || M_EKSIK="$M_EKSIK goc.py:motor-sinifi-yok"
  var1 "goktungu/goc.py" 'SEMA_SURUMU' \
    || M_EKSIK="$M_EKSIK goc.py:sema-surumu-yok"
  var1 "goktungu/goc.py" 'sema_goc_defteri' \
    || M_EKSIK="$M_EKSIK goc.py:goc-defteri-yok"
  var1 "goktungu/goc.py" 'def calistir' \
    || M_EKSIK="$M_EKSIK goc.py:calistir-yok"
  var1 "goktungu/goc.py" 'def durum' \
    || M_EKSIK="$M_EKSIK goc.py:durum-yok"
  # Ilerleme geri cagirmasi olmadan progressbar hareket edemez.
  var1 "goktungu/goc.py" 'ilerleme' \
    || M_EKSIK="$M_EKSIK goc.py:ilerleme-bildirimi-yok"
fi

# --- IS 3: veritabani.py PG KIPI -------------------------------------
# EN KRITIK DENETIM. pg.py kurulu olup veritabani.py eski kalirsa
# sihirbaz kurulumu yapar, PG'de tablolar olusur, ama program YINE
# SQLite'a yazar. Kullanici gecisin tamamlandigini sanir; ucus verisi
# yanlis yere gider. Hicbir hata mesaji cikmaz.
D_EKSIK=""
var1 "goktungu/veritabani.py" 'def kip_ayarla' \
  || D_EKSIK="$D_EKSIK veritabani.py:kip-anahtari-yok"
var1 "goktungu/veritabani.py" 'postgresql' \
  || D_EKSIK="$D_EKSIK veritabani.py:pg-kipi-taninmiyor"
var1 "goktungu/veritabani.py" 'harita_karo' \
  || D_EKSIK="$D_EKSIK veritabani.py:harita-karo-tablosu-yok"
var1 "goktungu/veritabani.py" 'gorev_durum' \
  || D_EKSIK="$D_EKSIK veritabani.py:gorev-durum-tablosu-yok"
var1 "goktungu/veritabani.py" 'telemetri_tampon_kayit' \
  || D_EKSIK="$D_EKSIK veritabani.py:telemetri-defteri-yok"
# gorev_durum birincil anahtari sysid OLMALI. dron_uid olursa iki dron
# AYNI satiri ezer ve ikinci dronun gorev surdurmesi birincinin
# verisini bozar. Olculen kusurdu.
if ! grep -qE 'sysid[^,)]*PRIMARY KEY' "$HEDEF/goktungu/veritabani.py" 2>/dev/null; then
  D_EKSIK="$D_EKSIK veritabani.py:gorev-durum-anahtari-sysid-degil"
fi
# v_ucuslar gorunumu GROUP BY olmadan PG'de REDDEDILIR. SQLite
# hosgoruyle rastgele satir aliyordu.
var1 "goktungu/veritabani.py" 'GROUP BY' \
  || D_EKSIK="$D_EKSIK veritabani.py:group-by-duzeltmesi-yok"

# --- IS 4: WS SIHIRBAZ KOMUTLARI -------------------------------------
W_EKSIK=""
var1 "goktungu/sunucu.py" '_pg_sihirbaz' \
  || W_EKSIK="$W_EKSIK sunucu.py:sihirbaz-isleyicisi-yok"
for k in pg_durum pg_dene pg_olustur pg_kur pg_goc; do
  var1 "goktungu/sunucu.py" "$k" || W_EKSIK="$W_EKSIK sunucu.py:$k-yok"
done
# ANLIK ilerleme: goc motoru ayri is parcasinda calisir. Sonda toplu
# gonderim yapilirsa cubuk hic hareket etmez, sonra bir anda %100
# olur — kullanici donmus sanip programi kapatir.
var1 "goktungu/sunucu.py" 'call_soon_threadsafe' \
  || W_EKSIK="$W_EKSIK sunucu.py:anlik-ilerleme-yayini-yok"
var1 "goktungu/sunucu.py" 'pg_ilerleme' \
  || W_EKSIK="$W_EKSIK sunucu.py:ilerleme-mesaji-yok"
# Tek yonlu kelepce: yuzde IKI kaynaktan gelir (hazirlik adimlari +
# goc motoru) ve ayri olcek kullanir. Kelepce yoksa cubuk 6'dan 0'a
# geri sarar; kullanici surecin bastan basladigini sanir. Olculdu.
var1 "goktungu/sunucu.py" '_tavan' \
  || W_EKSIK="$W_EKSIK sunucu.py:ilerleme-kelepcesi-yok"

# --- IS 5: ARAYUZ ----------------------------------------------------
A_EKSIK=""
if [ ! -f "$HEDEF/js/pg_sihirbaz.js" ]; then
  A_EKSIK="$A_EKSIK js/pg_sihirbaz.js:YOK"
else
  for i in pgDurumSor pgDurumGeldi pgSonucGeldi pgIlerlemeGeldi \
           pgSihirbazAc pgSihirbazKapat; do
    var1 "js/pg_sihirbaz.js" "window.$i" \
      || A_EKSIK="$A_EKSIK pg_sihirbaz.js:$i-yok"
  done
  # Sihirbaz giris ekranini KAPATMALI. `girisPerde` z-index 3000,
  # `.pgs-perde` 9550 — sihirbaz gorsel olarak ustte durur, ama
  # sihirbaz TAMAMLANMADAN kapanmadigi icin arkadaki giris formuna
  # erisilemez. Bu yuzden ayri bir 'gizle' cagrisi yok; olculen sey
  # perdenin z-index'inin giris perdesinin USTUNDE oldugudur.
  var1 "js/pg_sihirbaz.js" 'pgs-perde' \
    || A_EKSIK="$A_EKSIK pg_sihirbaz.js:perde-sinifi-yok"
  # Kapat dugmesi / ESC OLMAMALI: veritabani olmadan sistemin hicbir
  # islevi calismaz, sihirbaz gorsel uyari degil GERCEK engeldir.
  var1 "js/pg_sihirbaz.js" 'window.pgSihirbazYenidenAc' \
    || A_EKSIK="$A_EKSIK pg_sihirbaz.js:yeniden-yapilandirma-yok"
fi
# Perde giris ekraninin (z-index 3000) USTUNDE olmali; aksi halde
# sihirbaz acilir ama giris formu onunu kapatir.
if [ -f "$HEDEF/css/stil.css" ]; then
  _z=$(grep -A2 '^\.pgs-perde' "$HEDEF/css/stil.css" 2>/dev/null \
       | grep -oE 'z-index: *[0-9]+' | grep -oE '[0-9]+' | head -1)
  [ -n "$_z" ] && [ "$_z" -gt 3000 ] 2>/dev/null \
    || A_EKSIK="$A_EKSIK stil.css:perde-giris-ekraninin-altinda($_z)"
fi
var1 "js/ws.js" 'pg_durum' \
  || A_EKSIK="$A_EKSIK ws.js:pg-durum-yonlendirilmiyor"
var1 "js/ws.js" 'pg_ilerleme' \
  || A_EKSIK="$A_EKSIK ws.js:ilerleme-yonlendirilmiyor"
# Acilista durum SORULMALI; yoksa sihirbaz hic acilmaz.
var1 "js/ws.js" 'pgDurumSor' \
  || A_EKSIK="$A_EKSIK ws.js:acilista-durum-sorulmuyor"
var1 "index.html" 'pg_sihirbaz.js' \
  || A_EKSIK="$A_EKSIK index.html:betik-etiketi-yok"
var1 "index.html" 'pmVeritabani' \
  || A_EKSIK="$A_EKSIK index.html:veritabani-menu-ogesi-yok"
var1 "css/stil.css" '.pgs-' \
  || A_EKSIK="$A_EKSIK stil.css:pgs-siniflari-yok"
var1 "css/stil.css" 'pgs-ilerleme' \
  || A_EKSIK="$A_EKSIK stil.css:ilerleme-cubugu-stili-yok"
var1 "js/i18n.js" 'pgBaslik' \
  || A_EKSIK="$A_EKSIK i18n.js:sihirbaz-cevirileri-yok"
var1 "js/i18n.js" 'pgGocBaslik' \
  || A_EKSIK="$A_EKSIK i18n.js:goc-cevirileri-yok"
var1 "js/i18n.js" 'pgSurucuYok' \
  || A_EKSIK="$A_EKSIK i18n.js:surucu-uyarisi-cevirisi-yok"

# --- IS 6: DOSYA -> PG TASIMA ----------------------------------------
T_EKSIK=""
var1 "goktungu/tile_cache.py" 'harita_karo' \
  || T_EKSIK="$T_EKSIK tile_cache.py:pg-deposu-yok"
var1 "goktungu/gorev.py" 'gorev_durum' \
  || T_EKSIK="$T_EKSIK gorev.py:pg-yazimi-yok"
var1 "goktungu/telemetri_tampon.py" 'telemetri_tampon_kayit' \
  || T_EKSIK="$T_EKSIK telemetri_tampon.py:defter-kaydi-yok"
# Harita ve gorevde disk katmani KORUNMALI. PG erisilemezse harita
# kararmamali ve gorev surdurme kaydi kaybolmamali. Olculen gercek
# adlar: `_pg_hazir` (PG kullanilabilir mi), `_pg_karo_oku/_yaz` (ana
# depo), `tile_yolu` (disk ikinci katman).
var1 "goktungu/tile_cache.py" '_pg_hazir' \
  || T_EKSIK="$T_EKSIK tile_cache.py:pg-hazirlik-denetimi-yok"
var1 "goktungu/tile_cache.py" '_pg_karo_oku' \
  || T_EKSIK="$T_EKSIK tile_cache.py:pg-karo-okuma-yok"
var1 "goktungu/tile_cache.py" 'def tile_yolu' \
  || T_EKSIK="$T_EKSIK tile_cache.py:disk-ikinci-katmani-kayboldu"

# --- IS 7: ACILIS AKISI ----------------------------------------------
B_EKSIK=""
var1 "main.py" 'dosyadan_yukle' \
  || B_EKSIK="$B_EKSIK main.py:pg-yapilandirmasi-yuklenmiyor"
var1 "main.py" 'kip_ayarla' \
  || B_EKSIK="$B_EKSIK main.py:pg-kipi-acilmiyor"
# PG kipinde SQLite butunluk denetimi ATLANMALI: gcs.db artik
# kullanilmiyor, bozuk olsa bile onemi yok. Atlanmazsa program
# gereksiz yere "veritabani bozuk" diye acilmayabilir.
var1 "main.py" '_PgKipiAtla' \
  || B_EKSIK="$B_EKSIK main.py:sqlite-butunluk-denetimi-atlanmiyor"

# --- GERILEME: onceki surumlerin isleri yerinde mi -------------------
R_EKSIK=""
# v2.4.50: joystick kayma giderme
var1 "goktungu/manuel_kontrol.py" 'joystick_ayar' \
  || R_EKSIK="$R_EKSIK manuel_kontrol.py:v2450-ortak-modul-kayboldu"
var1 "goktungu/sunucu.py" 'joystick_pilot' \
  || R_EKSIK="$R_EKSIK sunucu.py:v2450-pilot-bazli-ayar-kayboldu"
# v2.4.49: servis + SIGTERM + port kaydi
var1 "main.py" '_sigterm_kur' \
  || R_EKSIK="$R_EKSIK main.py:v2449-sigterm-kayboldu"
var1 "main.py" '_port_dosyasi_yaz' \
  || R_EKSIK="$R_EKSIK main.py:v2449-port-kaydi-kayboldu"
var1 "goktungu/sunucu.py" 'aktif_ws_port' \
  || R_EKSIK="$R_EKSIK sunucu.py:v2449-aktif-ws-port-kayboldu"
for k in servis_durum servis_eylem servis_gunluk makine_kapat; do
  var1 "goktungu/sunucu.py" "komut == \"$k\"" \
    || R_EKSIK="$R_EKSIK sunucu.py:v2449-$k-kayboldu"
done
# v2.4.47/48: mimariye duyarli SITL
var1 "goktungu/sitl.py" 'MIMARI_SONEK' \
  || R_EKSIK="$R_EKSIK sitl.py:v2447-mimari-sonek-kayboldu"
var1 "goktungu/sitl.py" 'PE_MAKINE' \
  || R_EKSIK="$R_EKSIK sitl.py:v2448-pe-mimarisi-kayboldu"
# Dakikalik telemetri tamponu KALDIRILMAMALI: v2.4.24 "disk yazma
# hatasi" cozumunun ta kendisi ve ag kesintisi korumasi.
var1 "goktungu/telemetri_tampon.py" 'jsonl' \
  || R_EKSIK="$R_EKSIK telemetri_tampon.py:disk-tamponu-kayboldu"
# veri/calisma.json DOSYADA kalmali (kiosk sunucu ayakta degilken okur)
var1 "main.py" 'calisma.json' \
  || R_EKSIK="$R_EKSIK main.py:calisma-json-kayboldu"

# Python sozdizimi: yama yarim kopyalanmis olabilir
PY_HATA=""
if command -v python3 >/dev/null 2>&1; then
  for p in main.py goktungu/pg.py goktungu/goc.py goktungu/veritabani.py \
           goktungu/sunucu.py goktungu/gorev.py goktungu/tile_cache.py \
           goktungu/telemetri_tampon.py; do
    if [ -f "$HEDEF/$p" ]; then
      python3 -c "import ast,sys; ast.parse(open(sys.argv[1],encoding='utf-8').read())" \
        "$HEDEF/$p" >/dev/null 2>&1 || PY_HATA="$PY_HATA $p"
    fi
  done
fi

echo ""
echo "======================================================"
if [ "$SONRAKI" = "2.4.51" ] && [ "$ETIKET" -ge 3 ] \
   && [ "$ESKI_ETIKET" -eq 0 ] && [ -z "$KOPYA_HATA" ] \
   && [ -z "$G_EKSIK" ] && [ -z "$M_EKSIK" ] \
   && [ -z "$D_EKSIK" ] && [ -z "$W_EKSIK" ] && [ -z "$A_EKSIK" ] \
   && [ -z "$T_EKSIK" ] && [ -z "$B_EKSIK" ] && [ -z "$R_EKSIK" ] \
   && [ -z "$PY_HATA" ]; then
  yesil "SONUC : v2.4.51 YAMASI UYGULANDI"
  echo ""
  echo "  Surum           : $SONRAKI"
  echo "  Onbellek etiketi: v2451 ($ETIKET yerde), kalan v2450: $ESKI_ETIKET"
  echo "  PG ag gecidi    : goktungu/pg.py"
  echo "  Goc motoru      : goktungu/goc.py (sema surumu 2451)"
  echo "  Sihirbaz        : js/pg_sihirbaz.js (giris ekranindan ONCE)"
  if [ "$SURUCU" -eq 1 ]; then
    echo "  psycopg2        : kurulu"
  else
    kirmizi "  psycopg2        : KURULU DEGIL -> pip3 install psycopg2-binary"
  fi
  echo ""
  sari "  >>> TARAYICIDA Ctrl+Shift+R (zorunlu) <<<"
  echo ""
  echo "  ------------------------------------------------------"
  echo "  ILK IS: POSTGRESQL SUNUCUSU HAZIRLAMA"
  echo "  ------------------------------------------------------"
  echo ""
  echo "  Bu yama PostgreSQL SUNUCUSUNU KURMAZ - bu bilincli. Boylece"
  echo "  ayni makinedeki bir sunucu da, agdaki merkezi bir sunucu da"
  echo "  kullanilabilir. Sunucuyu siz kurar, bilgileri sihirbaza"
  echo "  girersiniz."
  echo ""
  echo "  Ayni makinede kurmak icin (Ubuntu / GX10 dahil):"
  echo ""
  echo "      sudo apt update"
  echo "      sudo apt install -y postgresql postgresql-contrib"
  echo "      sudo -u postgres psql -c \"CREATE USER goktungu WITH PASSWORD 'guclu_bir_sifre';\""
  echo "      sudo -u postgres psql -c \"CREATE DATABASE goktungu OWNER goktungu;\""
  echo "      sudo -u postgres psql -d goktungu -c 'CREATE EXTENSION IF NOT EXISTS citext;'"
  echo ""
  echo "  citext eklentisi ONERILIR (zorunlu degil): e-posta"
  echo "  karsilastirmasini buyuk/kucuk harften bagimsiz yapar."
  echo "  Yoksa program duz TEXT kullanir ve karsilastirmayi Python"
  echo "  tarafinda yapar - calisir, ama veritabani duzeyinde"
  echo "  mukerrer kayit korumasi zayiflar."
  echo ""
  echo "  Veritabanini sihirbaz da olusturabilir: kullaniciya"
  echo "  CREATEDB yetkisi verilmisse 2. adimda 'Veritabanini Olustur'"
  echo "  dugmesi cikar."
  echo ""
  echo "  ------------------------------------------------------"
  echo "  SIHIRBAZ NASIL CALISIR"
  echo "  ------------------------------------------------------"
  echo ""
  echo "  Programi baslatip tarayiciyi acin (Ctrl+Shift+R):"
  echo ""
  echo "      cd '$HEDEF' && python3 main.py"
  echo ""
  echo "  ILK KURULUM (yapilandirma yok):"
  echo "    Sihirbaz GIRIS EKRANINDAN ONCE acilir. Bu zorunlu:"
  echo "    veritabani olmadan kullanici dogrulanamaz."
  echo "      1. adim : Sunucu IP, port (5432), veritabani adi,"
  echo "                kullanici adi, sifre"
  echo "      2. adim : Baglanti dogrulanir. PostgreSQL surumu, mevcut"
  echo "                tablo sayisi, citext durumu ve yetkiler"
  echo "                gosterilir. Veritabani yoksa olusturma dugmesi"
  echo "                cikar."
  echo "      3. adim : Kurulum. Ilerleme cubugu adim adim ilerler ve"
  echo "                o an ne yapildigini yazar (27 tablo + 3 gorunum)."
  echo ""
  echo "  SEMA GUNCELLEMESI (yapilandirma var, sema eski):"
  echo "    Acilista tek ekranli goc sihirbazi cikar: mevcut ve hedef"
  echo "    sema surumu, bekleyen adimlarin listesi ve ilerleme cubugu."
  echo "    Guncelleme bitmeden sistem kullanilamaz - yarim semayla"
  echo "    ucmak veri kaybi riskidir."
  echo ""
  echo "  BILGILERI SONRADAN DEGISTIRME:"
  echo "    Kullanici menusu -> Veritabani Ayarlari (yalniz yonetici)"
  echo ""
  echo "  ------------------------------------------------------"
  echo "  NELER POSTGRESQL'E TASINDI"
  echo "  ------------------------------------------------------"
  echo ""
  echo "  * 27 tablo + 3 gorunumun TAMAMI (kullanicilar, dronlar,"
  echo "    ucuslar, telemetri, rotalar, kameralar, ayarlar...)"
  echo "  * Harita karolari  -> harita_karo tablosu"
  echo "  * Gorev durumu     -> gorev_durum tablosu (anahtar: sysid)"
  echo "  * Telemetri defteri-> telemetri_tampon_kayit tablosu"
  echo ""
  echo "  IKI KATMANLI DEPO (bilincli tasarim):"
  echo "    Harita karolarinda PG ANA depo, disk IKINCI katmandir."
  echo "    PG erisilemez olursa harita KARARMAZ, diskteki karolarla"
  echo "    calismaya devam eder. Gorev durumunda da dosya geri donus"
  echo "    katmani korundu."
  echo ""
  echo "  DOSYADA KALANLAR (gerekcesiyle):"
  echo "    * veri/calisma.json"
  echo "        Kiosk betigi bu dosyayi sunucu AYAKTA DEGILKEN okuyup"
  echo "        hangi porta baglanacagini bulur. PG'ye tasinsa iki"
  echo "        ekran kiosk duzeni kirilirdi."
  echo "    * veri/telemetri_tampon/*.jsonl (HAM ornekler)"
  echo "        v2.4.24'teki 'disk yazma hatasi' cozumunun ta kendisi."
  echo "        Ayrica ag veya PG kesintisinde ucus verisi kaybolmasin"
  echo "        diye diskte tutulur; aktarim PG'ye yapilir ve defter"
  echo "        kaydi PG'ye yazilir."
  echo ""
  echo "  ------------------------------------------------------"
  echo "  ESKI SQLITE VERISI"
  echo "  ------------------------------------------------------"
  echo ""
  echo "  gcs.db dosyasi SILINMEDI ve yedeklendi:"
  echo "    $YEDEK/"
  echo ""
  echo "  Yeni PostgreSQL veritabani BOS baslar. Daha once"
  echo "  'eski hic bir veriye ihtiyacim yok' dediginiz icin otomatik"
  echo "  veri aktarimi YAPILMADI. Gerekirse aktarim araci yazilabilir."
  echo ""
  echo "  ------------------------------------------------------"
  echo "  DOGRULAMA"
  echo "  ------------------------------------------------------"
  echo ""
  echo "        python3 sinav_2451_pg.py          # 199 PG denetimi"
  echo "        python3 sinav_2450_joystick.py    #  88 joystick denetimi"
  echo "        python3 sinav_2449_servis.py      # 127 servis/kiosk denetimi"
  echo ""
  echo "  Calisan sunucu uzerinde canli sihirbaz sinavi:"
  echo "        python3 dene_pg_ws.py             #  40 canli denetim"
  echo ""
  if [ "$SYSTEMD" -eq 1 ]; then
    echo "  Servis olarak kurulum (istege bagli):"
    echo "        cd '$HEDEF' && bash servis_kur.sh"
    echo ""
    echo "  ONEMLI: servisi kurmadan ONCE sihirbazi ELLE tamamlayin."
    echo "  Yapilandirma yoksa servis acilir ama arayuz sihirbazda"
    echo "  bekler; journal'da hata gorunmez ve neden anlasilmaz."
  fi
else
  kirmizi "SONUC : DOGRULAMA BASARISIZ"
  echo "  beklenen surum  : 2.4.51"
  echo "  okunan surum    : $SONRAKI"
  echo "  v2451 etiketi   : $ETIKET (en az 3 olmali)"
  echo "  kalan v2450     : $ESKI_ETIKET (0 olmali)"
  if [ -n "$KOPYA_HATA" ]; then
    echo "  Kopyalama       : $KOPYA_HATA"
    echo "                    Paket eksik veya bozuk. Arsivi yeniden"
    echo "                    acip kur_2451.sh'i paket icinden calistirin."
  fi
  [ -n "$G_EKSIK" ] && echo "  PG ag gecidi    :$G_EKSIK"
  [ -n "$M_EKSIK" ] && echo "  Goc motoru      :$M_EKSIK"
  [ -n "$D_EKSIK" ] && echo "  Veritabani kipi :$D_EKSIK"
  [ -n "$W_EKSIK" ] && echo "  WS komutlari    :$W_EKSIK"
  [ -n "$A_EKSIK" ] && echo "  Arayuz          :$A_EKSIK"
  [ -n "$T_EKSIK" ] && echo "  Dosya->PG tasima:$T_EKSIK"
  [ -n "$B_EKSIK" ] && echo "  Acilis akisi    :$B_EKSIK"
  [ -n "$R_EKSIK" ] && echo "  GERILEME        :$R_EKSIK"
  [ -n "$PY_HATA" ] && echo "  Python sozdizimi:$PY_HATA"
  echo ""
  echo "Yedek geri yuklemek icin:"
  echo "  cp -r '$YEDEK/.' '$HEDEF/'"
fi
echo "======================================================"
