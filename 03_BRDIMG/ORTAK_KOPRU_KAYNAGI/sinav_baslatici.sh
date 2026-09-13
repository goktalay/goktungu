#!/usr/bin/env bash
# =====================================================================
# SINAV: kur.bat'in urettigi baslatici Turkce karakterli ve bosluk
# iceren bir yolda saglam mi?
#
# Wine 6.0.3 `chcp 65001`'den sonra cmd.exe'yi tumuyle susturuyor
# (olculdu: sonraki echo komutlari hic cikti uretmiyor). Bu bir Wine
# sinirlamasidir. Yeni kur.bat chcp KULLANMADIGI icin Wine altinda
# sinanabilir; eski kur.bat sinanamiyordu. Bu, degisikligin yan
# faydasi.
#
# ONEMLI: Bu sinav baslaticinin URETIMINI ve ICERIGINI olcer. Python
# venv kurulumu Wine'da yapilamaz (pip ag erisimi + Windows Python
# gerekir), dolayisiyla baslaticinin "sanal ortam yok" uyarisini
# vermesi BEKLENEN dogru davranistir.
# =====================================================================
set -u

export WINEDEBUG=-all
GECTI=0
KALDI=0

ok()  { printf '  [GECTI] %s\n' "$1"; GECTI=$((GECTI+1)); }
no()  { printf '  [KALDI] %s\n' "$1"; KALDI=$((KALDI+1)); }

# Kullanicinin gercek yolunu taklit et: Turkce karakter + OneDrive
KOK_WIN='C:\Users\mkade\OneDrive\Masaüstü\goktungu-kopru-1.2.1\goktungu-kopru-1.2.1'
KOK_UNIX="$HOME/.wine/drive_c/Users/mkade/OneDrive/Masaüstü/goktungu-kopru-1.2.1/goktungu-kopru-1.2.1"

rm -rf "$HOME/.wine/drive_c/Users/mkade/OneDrive"
mkdir -p "$KOK_UNIX/.venv/Scripts"

# kur.bat'in YALNIZ baslatici uretim bolumunu ayikla ve tek basina
# calistir. Butun betigi kosmak Python/pip gerektirir; olcmek
# istedigimiz sey baslaticinin BAYTLARI.
cd "$(dirname "$0")" || exit 1
KUR="$(pwd)/kur.bat"

{
  printf '@echo off\r\n'
  printf 'setlocal EnableDelayedExpansion\r\n'
  printf 'set "KOK=%%~dp0"\r\n'
  printf 'set "KOK=%%KOK:~0,-1%%"\r\n'
  printf 'set "VENV=%%KOK%%\\.venv"\r\n'
  # kur.bat'teki baslatici uretim satirlarini AYNEN al
  awk '/^set "BASLAT=/,/^echo   \[OK\] %BASLAT%/' "$KUR" | sed 's/$/\r/'
} > "$KOK_UNIX/uret.bat"

echo "===================================================================="
echo " SINAV: kur.bat baslatici uretimi (Turkce karakterli yol)"
echo "===================================================================="
echo "Yol: $KOK_WIN"
echo

wine cmd /c "$KOK_WIN\\uret.bat" >/dev/null 2>&1

VBS="$KOK_UNIX/GOKTUNGU Kopru.vbs"

echo "-- 1. Uretim --"
if [ -f "$VBS" ]; then ok "baslatici dosyasi olusturuldu"; else no "baslatici dosyasi OLUSTURULAMADI"; fi
if [ -s "$VBS" ]; then ok "dosya bos degil ($(stat -c%s "$VBS") bayt)"; else no "dosya BOS"; fi

echo
echo "-- 2. Kodlama dayanikligi (asil kusur) --"
if [ -f "$VBS" ]; then
  UST=$(LC_ALL=C grep -c '[^ -~[:space:]]' "$VBS" 2>/dev/null || echo 0)
  SAYI=$(LC_ALL=C tr -d '\000-\177' < "$VBS" | wc -c)
  if [ "$SAYI" -eq 0 ]; then
    ok "dosya SAF ASCII (ust bayt: 0) - kod sayfasindan etkilenmez"
  else
    no "dosyada $SAYI ust bayt var - kodlama kusuru sururuyor"
  fi
  if ! LC_ALL=C grep -q 'Masa' "$VBS"; then
    ok "yol GOMULU DEGIL (Turkce dizin adi dosyada yok)"
  else
    no "yol dosyaya GOMULMUS - tasima/yeniden adlandirma bozar"
  fi
  if LC_ALL=C grep -q 'ScriptFullName' "$VBS"; then
    ok "betik kendi konumunu ScriptFullName ile buluyor"
  else
    no "ScriptFullName kullanilmiyor"
  fi
fi

echo
echo "-- 3. Saglamlik denetimleri --"
if [ -f "$VBS" ]; then
  if LC_ALL=C grep -q 'FileExists(pyw)' "$VBS"; then
    ok "sanal ortam yoksa anlasilir ileti veriliyor"
  else
    no "sanal ortam denetimi yok"
  fi
  if LC_ALL=C grep -q 'FileExists(ana)' "$VBS"; then
    ok "program dosyasi yoksa anlasilir ileti veriliyor"
  else
    no "program dosyasi denetimi yok"
  fi
  if LC_ALL=C grep -q ', 0, False' "$VBS"; then
    ok "konsol penceresi ACMAZ (gizli kip korundu)"
  else
    no "gizli kip kaybolmus"
  fi
fi

echo
echo "-- 4. wscript.exe ayristirabiliyor mu --"
if [ -f "$VBS" ]; then
  # Sanal ortam sahte oldugu icin "bulunamadi" iletisi beklenir; onemli
  # olan SOZDIZIMI hatasi ya da 80070003 yol hatasi OLMAMASI.
  CIK=$(timeout 25 wine wscript.exe "$KOK_WIN\\GOKTUNGU Kopru.vbs" 2>&1 | tr '\n' ' ')
  if echo "$CIK" | grep -qi '80070003\|belirtilen yolu\|cannot find the path'; then
    no "YOL HATASI sururuyor: $CIK"
  else
    ok "yol hatasi (80070003) YOK"
  fi
  if echo "$CIK" | grep -qi 'syntax error\|sozdizimi\|Expected'; then
    no "VBS sozdizimi hatasi: $CIK"
  else
    ok "VBS sozdizimi gecerli"
  fi
fi

echo
echo "-- 5. Baslatici icerigi --"
[ -f "$VBS" ] && sed 's/^/    /' "$VBS"

echo
echo "===================================================================="
printf " SONUC: %s gecti / %s kaldi\n" "$GECTI" "$KALDI"
echo "===================================================================="
[ "$KALDI" -eq 0 ] || exit 1
