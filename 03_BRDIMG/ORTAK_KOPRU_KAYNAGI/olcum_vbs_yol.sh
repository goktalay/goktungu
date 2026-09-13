#!/usr/bin/env bash
# =====================================================================
# OLCUM: kur.bat'in urettigi "GOKTUNGU Kopru.vbs" Turkce karakterli bir
# dizinde neden "Sistem belirtilen yolu bulamiyor" (80070003) veriyor?
#
# HIPOTEZ
#   `chcp 65001` ile birlikte `echo ... > dosya` yonlendirmesi, cmd.exe
#   cikisini UTF-8 olarak yazar. wscript.exe ise BOM'suz bir .vbs
#   dosyasini ANSI (kod sayfasi 1254) sanir; UTF-8'de iki bayt olan
#   'ü' harfi iki ayri karaktere donusur ve yol bozulur.
#
# YONTEM
#   Wine altinda gercek bir cmd.exe ile ayni satirlari uretip, ortaya
#   cikan baytlari olcuyoruz. Yorum degil, olcum.
# =====================================================================
set -u

export WINEDEBUG=-all
KOK_WIN='C:\goktungu_olcum\Masaüstü\kopru'
KOK_UNIX="$HOME/.wine/drive_c/goktungu_olcum/Masaüstü/kopru"

rm -rf "$HOME/.wine/drive_c/goktungu_olcum"
mkdir -p "$KOK_UNIX"

# --- 1) MEVCUT YONTEM: chcp 65001 + echo yonlendirmesi ---------------
cat > "$KOK_UNIX/eski.bat" <<'BAT'
@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
set "KOK=%~dp0"
set "KOK=%KOK:~0,-1%"
set "VENV=%KOK%\.venv"
set "BASLAT=%KOK%\cikti_eski.vbs"
> "%BASLAT%" echo ' GOKTUNGU Kopru baslatici
>> "%BASLAT%" echo Set k = CreateObject("WScript.Shell")
>> "%BASLAT%" echo k.CurrentDirectory = "%KOK%"
>> "%BASLAT%" echo k.Run """%VENV%\Scripts\pythonw.exe"" ""%KOK%\main.py""", 0, False
BAT

# --- 2) YENI YONTEM: yolu hic gomme, VBS kendi konumunu bulsun -------
cat > "$KOK_UNIX/yeni.bat" <<'BAT'
@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
set "KOK=%~dp0"
set "KOK=%KOK:~0,-1%"
set "BASLAT=%KOK%\cikti_yeni.vbs"
> "%BASLAT%" echo ' GOKTUNGU Kopru baslatici - yol GOMULU DEGIL
>> "%BASLAT%" echo Set f = CreateObject("Scripting.FileSystemObject")
>> "%BASLAT%" echo Set k = CreateObject("WScript.Shell")
>> "%BASLAT%" echo kok = f.GetParentFolderName(WScript.ScriptFullName)
>> "%BASLAT%" echo k.CurrentDirectory = kok
BAT

cd "$KOK_UNIX" || exit 1

echo "===================================================================="
echo " OLCUM 1: mevcut yontem (yol VBS icine gomulu, chcp 65001)"
echo "===================================================================="
wine cmd /c 'C:\goktungu_olcum\Masaüstü\kopru\eski.bat' >/dev/null 2>&1
if [ -f cikti_eski.vbs ]; then
  echo "-- uretilen dosya turu --"
  file cikti_eski.vbs
  echo "-- 3. satirin BAYTLARI (Masaustu bolumu) --"
  sed -n '3p' cikti_eski.vbs | hexdump -C | head -5
  echo "-- 3. satir metin olarak --"
  sed -n '3p' cikti_eski.vbs
  echo "-- 'u' harfinin bayt sayisi (2 = UTF-8, 1 = ANSI) --"
  sed -n '3p' cikti_eski.vbs | grep -o 'Masa.*st' | head -1 | wc -c
else
  echo "  [!] dosya uretilemedi"
fi

echo
echo "===================================================================="
echo " OLCUM 2: yeni yontem (yol GOMULU DEGIL, VBS kendini bulur)"
echo "===================================================================="
wine cmd /c 'C:\goktungu_olcum\Masaüstü\kopru\yeni.bat' >/dev/null 2>&1
if [ -f cikti_yeni.vbs ]; then
  echo "-- uretilen dosya --"
  cat cikti_yeni.vbs
  echo "-- Turkce karakter iceriyor mu? (0 = ICERMIYOR, iyi) --"
  grep -c 'Masa' cikti_yeni.vbs || true
else
  echo "  [!] dosya uretilemedi"
fi

echo
echo "===================================================================="
echo " OLCUM 3: wscript.exe her iki dosyayi calistirabiliyor mu?"
echo "===================================================================="
for d in cikti_eski.vbs cikti_yeni.vbs; do
  [ -f "$d" ] || continue
  cikti=$(wine wscript.exe "C:\\goktungu_olcum\\Masaüstü\\kopru\\$d" 2>&1)
  kod=$?
  printf '%-18s cikis_kodu=%s  ileti=%s\n' "$d" "$kod" "$(echo "$cikti" | tr '\n' ' ' | cut -c1-120)"
done
