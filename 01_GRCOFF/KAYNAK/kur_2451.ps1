# GOKTUNGU v2.4.51 yama kurulumu (Windows / PowerShell)
#
# Bu surum veritabanini SQLite'tan PostgreSQL'e tasir ve gecisi bir
# SIHIRBAZA baglar. TAMAMEN PLATFORMDAN BAGIMSIZDIR; Windows'ta da
# birebir gecerlidir.
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
#   (5) "fiziksel dosyalarda tuttugun tamponlari ve harita tamponlarini
#        da postgresql'e tasiyalim"
#   (6) "sqlite'a donmeyecegiz, her veri postgresql'de"
#
# YAMANIN YAPTIGI
# ---------------
#   1) goktungu\pg.py (YENI) — PostgreSQL ag gecidi. `baglanti()` imzasi
#      AYNI kaldi, boylece 146 cagri yerinin HICBIRI degismedi. Katman
#      ? -> %s, AUTOINCREMENT -> BIGSERIAL, COLLATE NOCASE -> citext,
#      strftime -> to_char, PRAGMA table_info -> information_schema
#      cevirilerini yapar ve `lastrowid`'i SAVEPOINT+RETURNING ile tasir.
#   2) goktungu\goc.py (YENI) — merkezi sema surumu, `sema_goc_defteri`
#      tablosu ve ADIM BASINA ilerleme bildiren goc motoru.
#   3) js\pg_sihirbaz.js (YENI) — GIRIS EKRANINDAN ONCE calisan 3 adimli
#      sihirbaz + ayri goc ekrani. Giristen once olmasi ZORUNLU:
#      kullanicilar tablosu artik PostgreSQL'de, veritabani yoksa kimse
#      dogrulanamaz.
#   4) Ilerleme cubugu GERCEK yuzde ve GERCEK ileti gosterir; yuzde ASLA
#      geri sarmaz.
#   5) Harita karolari, gorev durumu ve telemetri defteri PG'ye tasindi.
#      Harita ve gorevde disk katmani IKINCI KATMAN olarak KORUNDU: PG
#      erisilemezse harita kararmaz, gorev kaydi kaybolmaz.
#
# BILINCLI OLARAK DOSYADA BIRAKILANLAR
#   * veri\calisma.json      — kiosk betigi bunu sunucu AYAKTA DEGILKEN
#                              okur (Linux tarafi)
#   * veri\telemetri_tampon\ — HAM ornekler diskte kalir; v2.4.24'teki
#                              "disk yazma hatasi" cozumunun ta kendisi
#                              ve ag/PG kesintisi korumasi
#
# ON KOSUL: psycopg2
#   PostgreSQL surucusu gerekir:
#       pip install psycopg2-binary
#   Betik bunu otomatik dener. PostgreSQL SUNUCUSUNU KURMAZ (bilincli):
#   sunucuyu siz kurar, erisim bilgilerini sihirbaza girersiniz. Boylece
#   agdaki merkezi bir PG sunucusu da kullanilabilir.
#
# NOT: Windows'ta servis kurulumu (goktungu.service / servis_kur.sh) ve iki
# ekran kiosk betigi (kiosk_baslat.sh) KULLANILMAZ; bunlar Linux'a
# ozeldir. Pakette Linux makineye tasinabilmesi icin birlikte tutulur.
#
# KULLANIM:
#   powershell -ExecutionPolicy Bypass -File .\kur_2451.ps1
#   powershell -ExecutionPolicy Bypass -File .\kur_2451.ps1 -Hedef "C:\goktungu"
param([string]$Hedef = "")
$ErrorActionPreference = "Stop"
$Kaynak = Split-Path -Parent $MyInvocation.MyCommand.Path

function Mavi($m)    { Write-Host $m -ForegroundColor Cyan }
function Yesil($m)   { Write-Host $m -ForegroundColor Green }
function Sari($m)    { Write-Host $m -ForegroundColor Yellow }
function Kirmizi($m) { Write-Host $m -ForegroundColor Red }

# --- 1. Hedef kurulum dizinini bul -----------------------------------
if ([string]::IsNullOrWhiteSpace($Hedef)) {
  foreach ($a in @("C:\goktungu", "$env:USERPROFILE\goktungu",
                   "$env:USERPROFILE\goktungu_v244",
                   "$env:USERPROFILE\OneDrive\Masaustu\goktungu",
                   (Get-Location).Path)) {
    if (Test-Path (Join-Path $a "index.html")) { $Hedef = $a; break }
  }
}

if ([string]::IsNullOrWhiteSpace($Hedef) -or
    -not (Test-Path (Join-Path $Hedef "index.html"))) {
  Kirmizi "Goktungu kurulumu bulunamadi."
  Write-Host "Kurulum dizinini elle verin, ornek:"
  Write-Host "  .\kur_2451.ps1 -Hedef 'C:\goktungu'"
  exit 1
}

Mavi "Kurulum dizini : $Hedef"

# DIKKAT: PROCESSOR_ARCHITECTURE, 32-bit PowerShell icinde ARM64 makinede
# bile x86 dondurebilir; gercek makine mimarisi icin ...W6432 onceliklidir.
$Mimari = $env:PROCESSOR_ARCHITEW6432
if (-not $Mimari) { $Mimari = $env:PROCESSOR_ARCHITECTURE }
if (-not $Mimari) { $Mimari = "bilinmiyor" }
Mavi "Makine mimarisi: $Mimari"

# --- 2. Mevcut surumu oku --------------------------------------------
function SurumOku($yol) {
  if (-not (Test-Path $yol)) { return "bilinmiyor" }
  $m = Select-String -Path $yol -Pattern 'GCS_SURUM\s*=\s*.([0-9.]+).' |
       Select-Object -First 1
  if ($m) { return $m.Matches[0].Groups[1].Value }
  return "bilinmiyor"
}
$SurumJs = Join-Path $Hedef "js\surum.js"
$Onceki  = SurumOku $SurumJs
Mavi "Mevcut surum   : $Onceki"

# Degisen dosya listesi TAHMINLE degil, v2.4.50 tam paketi ile birebir
# karsilastirmayla belirlendi (6 yeni + 16 degisen).
#
# goktungu\veritabani.py EN KRITIK: PG kipine yonlendiren kip anahtari
# burada. Atlanirsa pg.py kurulu olsa bile HICBIR sorgu PG'ye gitmez;
# sihirbaz kurulumu yapar, PG'de tablolar olusur, program YINE SQLite'a
# yazar ve kullanici gecisin tamamlandigini sanir. Hata mesaji cikmaz.
#
# js\ws.js KRITIK: acilista pg_durum SORAN ve pg_sonuc/pg_ilerleme
# yonlendiren taraf. Atlanirsa sihirbaz HIC acilmaz, belirti gorunmez.
$Dosyalar = @(
  "goktungu\pg.py", "goktungu\goc.py",
  "goktungu\veritabani.py", "goktungu\sunucu.py", "goktungu\__init__.py",
  "goktungu\gorev.py", "goktungu\tile_cache.py", "goktungu\telemetri_tampon.py",
  "main.py",
  "js\pg_sihirbaz.js", "js\ws.js", "js\i18n.js", "js\surum.js",
  "js\kullanici.js",
  "css\stil.css",
  "index.html", "video.html", "flight.html"
)

# ATLANAN SURUM KORUMASI — v2.4.49/50 dosyalari.
# Kullanicinin kendi kurulumu v2.4.24; dogrudan v2.4.51'e gecerse
# joystick modulu ve servis paneli kurulumda HIC olmaz ve arayuzdeki
# bolumler sessizce cikmaz.
$EkDosyalar = @(
  "goktungu\joystick_ayar.py", "js\joystick_ayar.js",
  "goktungu\servis.py", "js\servis_panel.js", "js\program_ayar.js",
  "goktungu\manuel_kontrol.py", "goktungu\istasyon2.py", "js\dronlar.js"
)

# --- 3. Yedek al -----------------------------------------------------
$Yedek = Join-Path $Hedef ("yedek_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
New-Item -ItemType Directory -Path $Yedek -Force | Out-Null
foreach ($d in ($Dosyalar + $EkDosyalar)) {
  $src = Join-Path $Hedef $d
  if (Test-Path $src) {
    $hd = Join-Path $Yedek (Split-Path -Parent $d)
    if ($hd -and -not (Test-Path $hd)) {
      New-Item -ItemType Directory -Path $hd -Force | Out-Null
    }
    Copy-Item $src (Join-Path $Yedek $d) -Force
  }
}
# SQLite veritabani da yedeklenir: gecis sonrasi geri donmek gerekirse
# ucus gecmisi elde kalsin. 500 MB ustundeyse atlanir.
$Db = Join-Path $Hedef "gcs.db"
if (Test-Path $Db) {
  $boy = (Get-Item $Db).Length
  if ($boy -lt 524288000) {
    Copy-Item $Db (Join-Path $Yedek "gcs.db") -Force
    Yesil "SQLite yedegi   : $Yedek\gcs.db"
  } else {
    Sari "gcs.db 500 MB ustu; yedeklenmedi (elle kopyalayin)"
  }
}
Yesil "Yedek alindi   : $Yedek"

# --- 4. Kopyala ------------------------------------------------------
$Kopya = 0
$Eksik = @()
foreach ($d in $Dosyalar) {
  $src = Join-Path $Kaynak $d
  if (-not (Test-Path $src)) { $Eksik += $d; continue }
  $hd = Join-Path $Hedef (Split-Path -Parent $d)
  if ($hd -and -not (Test-Path $hd)) {
    New-Item -ItemType Directory -Path $hd -Force | Out-Null
  }
  Copy-Item $src (Join-Path $Hedef $d) -Force
  $Kopya++
}
foreach ($d in $EkDosyalar) {
  $src = Join-Path $Kaynak $d
  if (-not (Test-Path $src)) { continue }
  $hd = Join-Path $Hedef (Split-Path -Parent $d)
  if ($hd -and -not (Test-Path $hd)) {
    New-Item -ItemType Directory -Path $hd -Force | Out-Null
  }
  Copy-Item $src (Join-Path $Hedef $d) -Force
}
Yesil "Kopyalanan     : $Kopya / $($Dosyalar.Count) dosya"
if ($Eksik.Count -gt 0) { Kirmizi "PAKETTE YOK    : $($Eksik -join ' ')" }

# KRITIK: kaynak eksikligi SONUCA yansimali.
# Dogrulama HEDEF dizinini okur. Kopyalama basarisiz oldugu halde
# hedefte zaten dogru dosyalar varsa "YAMA UYGULANDI" derdi; yama hic
# uygulanmamis olmasina ragmen basarili gorunur ve kullanici eski kodla
# ucar. Bu yuzden kopyalama ayri bir kapi olarak tutulur.
$KopyaHata = ""
if ($Kopya -lt $Dosyalar.Count) {
  $KopyaHata = "$Kopya/$($Dosyalar.Count)-kopyalandi"
}

# Linux'a ozel servis/kiosk dosyalari + sinav betikleri
foreach ($s in @("goktungu.service.sablon", "servis_kur.sh",
                 "kiosk_baslat.sh", "sitl_tani.py",
                 "sinav_2451_pg.py", "dene_pg_ws.py",
                 "dene_pg_gecit.py", "dene_pg_veri.py",
                 "dene_goc.py", "dene_faz5.py",
                 "sinav_2450_joystick.py", "dene_joystick_ws.py",
                 "sinav_2449_servis.py", "sinav_2448_platform.py",
                 "sinav_2447_mimari.py", "sinav_2446_sitl.py",
                 "sinav_2446_canli.py", "sinav_2445_arayuz.py",
                 "sinav_2445_canli.py", "sinav_2445_sitl.py",
                 "olc_css_degisken.py", "olc_i18n_denge.py",
                 "sinav_2444_arayuz.py", "sinav_2444_canli.py",
                 "sinav_2444_sitl.py", "sinav_istasyon2_backend.py",
                 "sinav_2443_arayuz.py", "sinav_2442_arayuz.py",
                 "dene_servis_ws.py", "dene_servis_eylem.py",
                 "GOKTUNGU_2.4.51_KURULUM_VE_SURUM_NOTLARI.md")) {
  $sp = Join-Path $Kaynak $s
  if (Test-Path $sp) { Copy-Item $sp (Join-Path $Hedef $s) -Force }
}

$I2Kaynak = Join-Path $Kaynak "istasyon2"
if (Test-Path $I2Kaynak) {
  $I2Hedef = Join-Path $Hedef "istasyon2"
  if (-not (Test-Path $I2Hedef)) {
    New-Item -ItemType Directory -Path $I2Hedef -Force | Out-Null
  }
  Copy-Item (Join-Path $I2Kaynak "*") $I2Hedef -Recurse -Force
}

# Bayat .pyc eski kodu golgeleyebilir. Bu surumde veritabani.py ve
# main.py degisti; bayat onbellek "PG kipi hic acilmiyor" gibi
# aciklanmasi zor bir belirti uretir.
foreach ($pc in @("goktungu\__pycache__", "goktungu\takip\__pycache__",
                  "__pycache__")) {
  $p = Join-Path $Hedef $pc
  if (Test-Path $p) { Remove-Item $p -Recurse -Force -ErrorAction SilentlyContinue }
}
Sari "Python onbellegi temizlendi"

# --- 5. psycopg2 surucusu --------------------------------------------
Write-Host ""
Mavi "--- PostgreSQL surucusu (psycopg2) ---"
$py = $null
foreach ($c in @("python", "python3", "py")) {
  try {
    $null = & $c --version 2>&1
    if ($LASTEXITCODE -eq 0) { $py = $c; break }
  } catch { }
}
$Surucu = $false
if (-not $py) {
  Kirmizi "Python bulunamadi; surucu denetimi yapilamadi."
} else {
  $null = & $py -c "import psycopg2" 2>&1
  if ($LASTEXITCODE -eq 0) {
    $sv = (& $py -c "import psycopg2;print(psycopg2.__version__)" 2>&1)
    Yesil "Kurulu         : psycopg2 $sv"
    $Surucu = $true
  } else {
    Sari "psycopg2 kurulu degil; kurulmaya calisiliyor..."
    # psycopg2-binary derleme gerektirmez; Windows icin tekerlek var.
    $null = & $py -m pip install psycopg2-binary 2>&1
    $null = & $py -c "import psycopg2" 2>&1
    if ($LASTEXITCODE -eq 0) {
      $sv = (& $py -c "import psycopg2;print(psycopg2.__version__)" 2>&1)
      Yesil "Kuruldu        : psycopg2 $sv"
      $Surucu = $true
    } else {
      Kirmizi "psycopg2 KURULAMADI. Elle kurun:"
      Write-Host "    $py -m pip install psycopg2-binary"
      Write-Host ""
      Sari "Surucu olmadan sihirbaz acilir ama baglanti KURAMAZ."
    }
  }
}

# --- 6. Dogrula ------------------------------------------------------
Write-Host ""
Mavi "--- Dogrulama ---"

$Sonraki = SurumOku $SurumJs

$Etiket = 0; $EskiEtiket = 0
foreach ($h in @("index.html", "video.html", "flight.html")) {
  $hp = Join-Path $Hedef $h
  if (-not (Test-Path $hp)) { continue }
  $ic = Get-Content $hp -Raw
  $Etiket     += ([regex]::Matches($ic, "v2451")).Count
  $EskiEtiket += ([regex]::Matches($ic, "v2450")).Count
}

function Var1($dosya, $desen) {
  $p = Join-Path $Hedef $dosya
  if (-not (Test-Path $p)) { return $false }
  return ((Get-Content $p -Raw) -match [regex]::Escape($desen))
}

# --- IS 1: PG AG GECIDI ----------------------------------------------
# Her ceviri ayri denetlenir cunku eksiklerin belirtileri FARKLI ve
# hepsi sessizdir: `?` cevrilmezse her sorgu patlar (gorulur), ama
# `lastrowid` cevrilmezse kayit eklenir ve id None doner — program
# calisir gibi gorunur, iliskiler bozulur.
$GEksik = @()
if (-not (Test-Path (Join-Path $Hedef "goktungu\pg.py"))) {
  $GEksik += "goktungu\pg.py:YOK"
} else {
  foreach ($i in @("yapilandir", "yapilandirma_var", "dosya_var",
                   "dosyadan_yukle", "dene", "veritabani_olustur",
                   "baglanti", "sema_cevir")) {
    if (-not (Var1 "goktungu\pg.py" "def $i")) { $GEksik += "pg.py:$i-yok" }
  }
  if (-not (Var1 "goktungu\pg.py" "_yer_tutucu_cevir")) { $GEksik += "pg.py:soru-isareti-cevirisi-yok" }
  if (-not (Var1 "goktungu\pg.py" "BIGSERIAL"))         { $GEksik += "pg.py:autoincrement-cevirisi-yok" }
  if (-not (Var1 "goktungu\pg.py" "citext"))            { $GEksik += "pg.py:collate-nocase-cevirisi-yok" }
  if (-not (Var1 "goktungu\pg.py" "to_char"))           { $GEksik += "pg.py:strftime-cevirisi-yok" }
  if (-not (Var1 "goktungu\pg.py" "information_schema")){ $GEksik += "pg.py:pragma-cevirisi-yok" }
  # id kolonu OLMAYAN tabloya kosulsuz RETURNING eklenirse hata sonrasi
  # rollback ONCEKI yazimlari da siler. Olculen kusurdu.
  if (-not (Var1 "goktungu\pg.py" "SAVEPOINT"))         { $GEksik += "pg.py:lastrowid-savepoint-yok" }
  if (-not (Var1 "goktungu\pg.py" "RETURNING"))         { $GEksik += "pg.py:lastrowid-returning-yok" }
  # Kod HEM r["ad"] HEM r[0] kullaniyor (14 yerde fetchone()[0]).
  if (-not (Var1 "goktungu\pg.py" "class Satir"))       { $GEksik += "pg.py:satir-sinifi-yok" }
  # total_changes: telemetri aktarimi bu sayaci okuyor; yokken aktarim
  # HIC calismiyordu (olculen kusur).
  if (-not (Var1 "goktungu\pg.py" "total_changes"))     { $GEksik += "pg.py:total-changes-yok" }
}

# --- IS 2: GOC MOTORU ------------------------------------------------
$MEksik = @()
if (-not (Test-Path (Join-Path $Hedef "goktungu\goc.py"))) {
  $MEksik += "goktungu\goc.py:YOK"
} else {
  if (-not (Var1 "goktungu\goc.py" "class GocMotoru"))   { $MEksik += "goc.py:motor-sinifi-yok" }
  if (-not (Var1 "goktungu\goc.py" "SEMA_SURUMU"))       { $MEksik += "goc.py:sema-surumu-yok" }
  if (-not (Var1 "goktungu\goc.py" "sema_goc_defteri"))  { $MEksik += "goc.py:goc-defteri-yok" }
  if (-not (Var1 "goktungu\goc.py" "def calistir"))      { $MEksik += "goc.py:calistir-yok" }
  if (-not (Var1 "goktungu\goc.py" "def durum"))         { $MEksik += "goc.py:durum-yok" }
  # Ilerleme geri cagirmasi olmadan progressbar hareket edemez.
  if (-not (Var1 "goktungu\goc.py" "ilerleme"))          { $MEksik += "goc.py:ilerleme-bildirimi-yok" }
}

# --- IS 3: veritabani.py PG KIPI -------------------------------------
# EN KRITIK DENETIM. Bu dosya eski kalirsa gecis GERCEKLESMEZ ama
# sihirbaz basarili gorunur.
$DEksik = @()
if (-not (Var1 "goktungu\veritabani.py" "def kip_ayarla"))         { $DEksik += "veritabani.py:kip-anahtari-yok" }
if (-not (Var1 "goktungu\veritabani.py" "postgresql"))             { $DEksik += "veritabani.py:pg-kipi-taninmiyor" }
if (-not (Var1 "goktungu\veritabani.py" "harita_karo"))            { $DEksik += "veritabani.py:harita-karo-tablosu-yok" }
if (-not (Var1 "goktungu\veritabani.py" "gorev_durum"))            { $DEksik += "veritabani.py:gorev-durum-tablosu-yok" }
if (-not (Var1 "goktungu\veritabani.py" "telemetri_tampon_kayit")) { $DEksik += "veritabani.py:telemetri-defteri-yok" }
# gorev_durum birincil anahtari sysid OLMALI. dron_uid olursa iki dron
# AYNI satiri ezer ve ikinci dron birincinin gorevini bozar.
$vtp = Join-Path $Hedef "goktungu\veritabani.py"
if (Test-Path $vtp) {
  if (-not ((Get-Content $vtp -Raw) -match 'sysid[^,)]*PRIMARY KEY')) {
    $DEksik += "veritabani.py:gorev-durum-anahtari-sysid-degil"
  }
}
# v_ucuslar gorunumu GROUP BY olmadan PG'de REDDEDILIR.
if (-not (Var1 "goktungu\veritabani.py" "GROUP BY")) { $DEksik += "veritabani.py:group-by-duzeltmesi-yok" }

# --- IS 4: WS SIHIRBAZ KOMUTLARI -------------------------------------
$WEksik = @()
if (-not (Var1 "goktungu\sunucu.py" "_pg_sihirbaz")) { $WEksik += "sunucu.py:sihirbaz-isleyicisi-yok" }
foreach ($k in @("pg_durum", "pg_dene", "pg_olustur", "pg_kur", "pg_goc")) {
  if (-not (Var1 "goktungu\sunucu.py" $k)) { $WEksik += "sunucu.py:$k-yok" }
}
# ANLIK ilerleme: goc motoru ayri is parcasinda calisir. Sonda toplu
# gonderim yapilirsa cubuk hic hareket etmez, sonra bir anda %100 olur —
# kullanici donmus sanip programi kapatir.
if (-not (Var1 "goktungu\sunucu.py" "call_soon_threadsafe")) { $WEksik += "sunucu.py:anlik-ilerleme-yayini-yok" }
if (-not (Var1 "goktungu\sunucu.py" "pg_ilerleme"))          { $WEksik += "sunucu.py:ilerleme-mesaji-yok" }
# Tek yonlu kelepce: yuzde IKI kaynaktan gelir (hazirlik + goc motoru),
# ayri olcek kullanirlar. Kelepce yoksa cubuk 6'dan 0'a geri sarar ve
# kullanici surecin bastan basladigini sanir. Olculdu.
if (-not (Var1 "goktungu\sunucu.py" "_tavan"))               { $WEksik += "sunucu.py:ilerleme-kelepcesi-yok" }

# --- IS 5: ARAYUZ ----------------------------------------------------
$AEksik = @()
if (-not (Test-Path (Join-Path $Hedef "js\pg_sihirbaz.js"))) {
  $AEksik += "js\pg_sihirbaz.js:YOK"
} else {
  foreach ($i in @("pgDurumSor", "pgDurumGeldi", "pgSonucGeldi",
                   "pgIlerlemeGeldi", "pgSihirbazAc", "pgSihirbazKapat")) {
    if (-not (Var1 "js\pg_sihirbaz.js" "window.$i")) {
      $AEksik += "pg_sihirbaz.js:$i-yok"
    }
  }
  # Sihirbaz giris ekranini KAPATMALI. girisPerde z-index 3000,
  # .pgs-perde 9550 — sihirbaz gorsel olarak ustte durur ve
  # TAMAMLANMADAN kapanmadigi icin arkadaki giris formuna erisilemez.
  if (-not (Var1 "js\pg_sihirbaz.js" "pgs-perde"))              { $AEksik += "pg_sihirbaz.js:perde-sinifi-yok" }
  if (-not (Var1 "js\pg_sihirbaz.js" "window.pgSihirbazYenidenAc")) { $AEksik += "pg_sihirbaz.js:yeniden-yapilandirma-yok" }
}
# Perde giris ekraninin (3000) USTUNDE olmali; aksi halde sihirbaz
# acilir ama giris formu onunu kapatir.
$cssp = Join-Path $Hedef "css\stil.css"
if (Test-Path $cssp) {
  $cm = [regex]::Match((Get-Content $cssp -Raw),
        '\.pgs-perde\s*\{[^}]*z-index:\s*(\d+)')
  if (-not $cm.Success -or [int]$cm.Groups[1].Value -le 3000) {
    $AEksik += "stil.css:perde-giris-ekraninin-altinda"
  }
}
if (-not (Var1 "js\ws.js" "pg_durum"))        { $AEksik += "ws.js:pg-durum-yonlendirilmiyor" }
if (-not (Var1 "js\ws.js" "pg_ilerleme"))     { $AEksik += "ws.js:ilerleme-yonlendirilmiyor" }
# Acilista durum SORULMALI; yoksa sihirbaz hic acilmaz.
if (-not (Var1 "js\ws.js" "pgDurumSor"))      { $AEksik += "ws.js:acilista-durum-sorulmuyor" }
if (-not (Var1 "index.html" "pg_sihirbaz.js")){ $AEksik += "index.html:betik-etiketi-yok" }
if (-not (Var1 "index.html" "pmVeritabani"))  { $AEksik += "index.html:veritabani-menu-ogesi-yok" }
if (-not (Var1 "css\stil.css" ".pgs-"))       { $AEksik += "stil.css:pgs-siniflari-yok" }
if (-not (Var1 "css\stil.css" "pgs-ilerleme")){ $AEksik += "stil.css:ilerleme-cubugu-stili-yok" }
if (-not (Var1 "js\i18n.js" "pgBaslik"))      { $AEksik += "i18n.js:sihirbaz-cevirileri-yok" }
if (-not (Var1 "js\i18n.js" "pgGocBaslik"))   { $AEksik += "i18n.js:goc-cevirileri-yok" }
if (-not (Var1 "js\i18n.js" "pgSurucuYok"))   { $AEksik += "i18n.js:surucu-uyarisi-cevirisi-yok" }

# --- IS 6: DOSYA -> PG TASIMA ----------------------------------------
$TEksik = @()
if (-not (Var1 "goktungu\tile_cache.py" "harita_karo"))                { $TEksik += "tile_cache.py:pg-deposu-yok" }
if (-not (Var1 "goktungu\gorev.py" "gorev_durum"))                     { $TEksik += "gorev.py:pg-yazimi-yok" }
if (-not (Var1 "goktungu\telemetri_tampon.py" "telemetri_tampon_kayit")) { $TEksik += "telemetri_tampon.py:defter-kaydi-yok" }
# Harita ve gorevde disk katmani KORUNMALI: PG erisilemezse harita
# kararmamali. Olculen gercek adlar: _pg_hazir, _pg_karo_oku, tile_yolu.
if (-not (Var1 "goktungu\tile_cache.py" "_pg_hazir"))     { $TEksik += "tile_cache.py:pg-hazirlik-denetimi-yok" }
if (-not (Var1 "goktungu\tile_cache.py" "_pg_karo_oku"))  { $TEksik += "tile_cache.py:pg-karo-okuma-yok" }
if (-not (Var1 "goktungu\tile_cache.py" "def tile_yolu")) { $TEksik += "tile_cache.py:disk-ikinci-katmani-kayboldu" }

# --- IS 7: ACILIS AKISI ----------------------------------------------
$BEksik = @()
if (-not (Var1 "main.py" "dosyadan_yukle")) { $BEksik += "main.py:pg-yapilandirmasi-yuklenmiyor" }
if (-not (Var1 "main.py" "kip_ayarla"))     { $BEksik += "main.py:pg-kipi-acilmiyor" }
# PG kipinde SQLite butunluk denetimi ATLANMALI: gcs.db artik
# kullanilmiyor, bozuk olsa bile onemi yok. Atlanmazsa program
# gereksiz yere acilmayabilir.
if (-not (Var1 "main.py" "_PgKipiAtla"))    { $BEksik += "main.py:sqlite-butunluk-denetimi-atlanmiyor" }

# --- GERILEME: onceki surumlerin isleri yerinde mi -------------------
$REksik = @()
# v2.4.50: joystick kayma giderme
if (-not (Var1 "goktungu\manuel_kontrol.py" "joystick_ayar")) { $REksik += "manuel_kontrol.py:v2450-ortak-modul-kayboldu" }
if (-not (Var1 "goktungu\sunucu.py" "joystick_pilot"))        { $REksik += "sunucu.py:v2450-pilot-bazli-ayar-kayboldu" }
# v2.4.49: servis + SIGTERM + port kaydi
if (-not (Var1 "main.py" "_sigterm_kur"))                  { $REksik += "main.py:v2449-sigterm-kayboldu" }
if (-not (Var1 "main.py" "_port_dosyasi_yaz"))             { $REksik += "main.py:v2449-port-kaydi-kayboldu" }
if (-not (Var1 "goktungu\sunucu.py" "aktif_ws_port"))         { $REksik += "sunucu.py:v2449-aktif-ws-port-kayboldu" }
foreach ($k in @("servis_durum", "servis_eylem", "servis_gunluk",
                 "makine_kapat")) {
  if (-not (Var1 "goktungu\sunucu.py" "komut == `"$k`"")) {
    $REksik += "sunucu.py:v2449-$k-kayboldu"
  }
}
# v2.4.47/48: mimariye duyarli SITL (Windows PE okumasi dahil)
if (-not (Var1 "goktungu\sitl.py" "MIMARI_SONEK"))            { $REksik += "sitl.py:v2447-mimari-sonek-kayboldu" }
if (-not (Var1 "goktungu\sitl.py" "PE_MAKINE"))               { $REksik += "sitl.py:v2448-pe-mimarisi-kayboldu" }
if (-not (Var1 "goktungu\sitl.py" "WINDOWS_DLL_ZORUNLU"))     { $REksik += "sitl.py:v2445-dll-listesi-kayboldu" }
# Dakikalik telemetri tamponu KALDIRILMAMALI: v2.4.24 "disk yazma
# hatasi" cozumunun ta kendisi ve ag kesintisi korumasi.
if (-not (Var1 "goktungu\telemetri_tampon.py" "jsonl"))       { $REksik += "telemetri_tampon.py:disk-tamponu-kayboldu" }
if (-not (Var1 "main.py" "calisma.json"))                  { $REksik += "main.py:calisma-json-kayboldu" }

# Python sozdizimi: yama yarim kopyalanmis olabilir
$PyHata = @()
if ($py) {
  foreach ($p in @("main.py", "goktungu\pg.py", "goktungu\goc.py",
                   "goktungu\veritabani.py", "goktungu\sunucu.py",
                   "goktungu\gorev.py", "goktungu\tile_cache.py",
                   "goktungu\telemetri_tampon.py")) {
    $pp = Join-Path $Hedef $p
    if (Test-Path $pp) {
      $null = & $py -c "import ast,sys; ast.parse(open(sys.argv[1],encoding='utf-8').read())" $pp 2>&1
      if ($LASTEXITCODE -ne 0) { $PyHata += $p }
    }
  }
}

Write-Host ""
Write-Host "======================================================"
if ($Sonraki -eq "2.4.51" -and $Etiket -ge 3 -and $EskiEtiket -eq 0 -and
    $KopyaHata -eq "" -and
    $GEksik.Count -eq 0 -and $MEksik.Count -eq 0 -and
    $DEksik.Count -eq 0 -and $WEksik.Count -eq 0 -and
    $AEksik.Count -eq 0 -and $TEksik.Count -eq 0 -and
    $BEksik.Count -eq 0 -and $REksik.Count -eq 0 -and
    $PyHata.Count -eq 0) {
  Yesil "SONUC : v2.4.51 YAMASI UYGULANDI"
  Write-Host ""
  Write-Host "  Surum           : $Sonraki"
  Write-Host "  Onbellek etiketi: v2451 ($Etiket yerde), kalan v2450: $EskiEtiket"
  Write-Host "  PG ag gecidi    : goktungu\pg.py"
  Write-Host "  Goc motoru      : goktungu\goc.py (sema surumu 2451)"
  Write-Host "  Sihirbaz        : js\pg_sihirbaz.js (giris ekranindan ONCE)"
  if ($Surucu) {
    Write-Host "  psycopg2        : kurulu"
  } else {
    Kirmizi "  psycopg2        : KURULU DEGIL -> pip install psycopg2-binary"
  }
  Write-Host ""
  Sari "  >>> TARAYICIDA Ctrl+Shift+R (zorunlu) <<<"
  Write-Host ""
  Write-Host "  ------------------------------------------------------"
  Write-Host "  ILK IS: POSTGRESQL SUNUCUSU HAZIRLAMA"
  Write-Host "  ------------------------------------------------------"
  Write-Host ""
  Write-Host "  Bu yama PostgreSQL SUNUCUSUNU KURMAZ - bu bilincli."
  Write-Host "  Boylece ayni makinedeki bir sunucu da, agdaki merkezi bir"
  Write-Host "  sunucu da kullanilabilir. Sunucuyu siz kurar, bilgileri"
  Write-Host "  sihirbaza girersiniz."
  Write-Host ""
  Write-Host "  Windows'ta kurmak icin:"
  Write-Host "    1. https://www.postgresql.org/download/windows/"
  Write-Host "       adresinden kurulumu indirin (EDB installer)"
  Write-Host "    2. Kurulumda 'postgres' kullanicisina bir sifre verin"
  Write-Host "    3. pgAdmin veya SQL Shell (psql) ile:"
  Write-Host ""
  Write-Host "         CREATE USER goktungu WITH PASSWORD 'guclu_bir_sifre';"
  Write-Host "         CREATE DATABASE goktungu OWNER goktungu;"
  Write-Host "         \c goktungu"
  Write-Host "         CREATE EXTENSION IF NOT EXISTS citext;"
  Write-Host ""
  Write-Host "  citext eklentisi ONERILIR (zorunlu degil): e-posta"
  Write-Host "  karsilastirmasini buyuk/kucuk harften bagimsiz yapar."
  Write-Host "  Yoksa program duz TEXT kullanir ve karsilastirmayi Python"
  Write-Host "  tarafinda yapar - calisir, ama veritabani duzeyinde"
  Write-Host "  mukerrer kayit korumasi zayiflar."
  Write-Host ""
  Write-Host "  Veritabanini sihirbaz da olusturabilir: kullaniciya"
  Write-Host "  CREATEDB yetkisi verilmisse 2. adimda 'Veritabanini"
  Write-Host "  Olustur' dugmesi cikar."
  Write-Host ""
  Write-Host "  ------------------------------------------------------"
  Write-Host "  SIHIRBAZ NASIL CALISIR"
  Write-Host "  ------------------------------------------------------"
  Write-Host ""
  Write-Host "  Programi baslatip tarayiciyi acin (Ctrl+Shift+R):"
  Write-Host ""
  Write-Host "      cd '$Hedef'"
  Write-Host "      python main.py"
  Write-Host ""
  Write-Host "  ILK KURULUM (yapilandirma yok):"
  Write-Host "    Sihirbaz GIRIS EKRANINDAN ONCE acilir. Bu zorunlu:"
  Write-Host "    kullanicilar tablosu artik PostgreSQL'de, veritabani"
  Write-Host "    olmadan kimse dogrulanamaz."
  Write-Host "      1. adim : Sunucu IP, port (5432), veritabani adi,"
  Write-Host "                kullanici adi, sifre"
  Write-Host "      2. adim : Baglanti dogrulanir. PostgreSQL surumu,"
  Write-Host "                mevcut tablo sayisi, citext durumu ve"
  Write-Host "                yetkiler gosterilir."
  Write-Host "      3. adim : Kurulum. Ilerleme cubugu adim adim ilerler"
  Write-Host "                ve o an ne yapildigini yazar"
  Write-Host "                (27 tablo + 3 gorunum)."
  Write-Host ""
  Write-Host "  SEMA GUNCELLEMESI (yapilandirma var, sema eski):"
  Write-Host "    Acilista tek ekranli goc sihirbazi cikar: mevcut ve"
  Write-Host "    hedef sema surumu, bekleyen adimlar ve ilerleme cubugu."
  Write-Host "    Guncelleme bitmeden sistem kullanilamaz - yarim semayla"
  Write-Host "    ucmak veri kaybi riskidir."
  Write-Host ""
  Write-Host "  BILGILERI SONRADAN DEGISTIRME:"
  Write-Host "    Kullanici menusu -> Veritabani Ayarlari (yalniz yonetici)"
  Write-Host ""
  Write-Host "  ------------------------------------------------------"
  Write-Host "  NELER POSTGRESQL'E TASINDI"
  Write-Host "  ------------------------------------------------------"
  Write-Host ""
  Write-Host "  * 27 tablo + 3 gorunumun TAMAMI (kullanicilar, dronlar,"
  Write-Host "    ucuslar, telemetri, rotalar, kameralar, ayarlar...)"
  Write-Host "  * Harita karolari  -> harita_karo tablosu"
  Write-Host "  * Gorev durumu     -> gorev_durum tablosu (anahtar: sysid)"
  Write-Host "  * Telemetri defteri-> telemetri_tampon_kayit tablosu"
  Write-Host ""
  Write-Host "  IKI KATMANLI DEPO (bilincli tasarim):"
  Write-Host "    Harita karolarinda PG ANA depo, disk IKINCI katmandir."
  Write-Host "    PG erisilemez olursa harita KARARMAZ, diskteki"
  Write-Host "    karolarla calismaya devam eder."
  Write-Host ""
  Write-Host "  DOSYADA KALANLAR (gerekcesiyle):"
  Write-Host "    * veri\calisma.json"
  Write-Host "        Kiosk betigi (Linux) bunu sunucu AYAKTA DEGILKEN"
  Write-Host "        okuyup hangi porta baglanacagini bulur."
  Write-Host "    * veri\telemetri_tampon\*.jsonl (HAM ornekler)"
  Write-Host "        v2.4.24'teki 'disk yazma hatasi' cozumunun ta"
  Write-Host "        kendisi. Ayrica ag veya PG kesintisinde ucus"
  Write-Host "        verisi kaybolmasin diye diskte tutulur; aktarim"
  Write-Host "        PG'ye yapilir."
  Write-Host ""
  Write-Host "  ------------------------------------------------------"
  Write-Host "  ESKI SQLITE VERISI"
  Write-Host "  ------------------------------------------------------"
  Write-Host ""
  Write-Host "  gcs.db dosyasi SILINMEDI ve yedeklendi:"
  Write-Host "    $Yedek"
  Write-Host ""
  Write-Host "  Yeni PostgreSQL veritabani BOS baslar. Daha once"
  Write-Host "  'eski hic bir veriye ihtiyacim yok' dediginiz icin"
  Write-Host "  otomatik veri aktarimi YAPILMADI."
  Write-Host ""
  Write-Host "  ------------------------------------------------------"
  Write-Host "  DOGRULAMA"
  Write-Host "  ------------------------------------------------------"
  Write-Host ""
  Write-Host "        python sinav_2451_pg.py          # 199 PG denetimi"
  Write-Host "        python sinav_2450_joystick.py    #  88 joystick denetimi"
  Write-Host "        python sinav_2449_servis.py      # 127 servis denetimi"
  Write-Host ""
  Write-Host "  Calisan sunucu uzerinde canli sihirbaz sinavi:"
  Write-Host "        python dene_pg_ws.py             #  40 canli denetim"
  Write-Host ""
  Write-Host "  SITL sorunu yasarsaniz tek komutla teshis:"
  Write-Host "        python sitl_tani.py"
} else {
  Kirmizi "SONUC : DOGRULAMA BASARISIZ"
  Write-Host "  beklenen surum  : 2.4.51"
  Write-Host "  okunan surum    : $Sonraki"
  Write-Host "  v2451 etiketi   : $Etiket (en az 3 olmali)"
  Write-Host "  kalan v2450     : $EskiEtiket (0 olmali)"
  if ($KopyaHata -ne "") {
    Write-Host "  Kopyalama       : $KopyaHata"
    Write-Host "                    Paket eksik veya bozuk. Arsivi yeniden"
    Write-Host "                    acip kur_2451.ps1'i paket icinden calistirin."
  }
  if ($GEksik.Count -gt 0) { Write-Host "  PG ag gecidi    : $($GEksik -join ' ')" }
  if ($MEksik.Count -gt 0) { Write-Host "  Goc motoru      : $($MEksik -join ' ')" }
  if ($DEksik.Count -gt 0) { Write-Host "  Veritabani kipi : $($DEksik -join ' ')" }
  if ($WEksik.Count -gt 0) { Write-Host "  WS komutlari    : $($WEksik -join ' ')" }
  if ($AEksik.Count -gt 0) { Write-Host "  Arayuz          : $($AEksik -join ' ')" }
  if ($TEksik.Count -gt 0) { Write-Host "  Dosya->PG       : $($TEksik -join ' ')" }
  if ($BEksik.Count -gt 0) { Write-Host "  Acilis akisi    : $($BEksik -join ' ')" }
  if ($REksik.Count -gt 0) { Write-Host "  GERILEME        : $($REksik -join ' ')" }
  if ($PyHata.Count -gt 0) { Write-Host "  Python sozdizimi: $($PyHata -join ' ')" }
  Write-Host ""
  Write-Host "Yedek geri yuklemek icin:"
  Write-Host "  Copy-Item '$Yedek\*' '$Hedef' -Recurse -Force"
}
Write-Host "======================================================"
