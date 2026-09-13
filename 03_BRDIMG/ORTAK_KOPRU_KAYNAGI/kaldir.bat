@echo off
REM =====================================================================
REM GOKTUNGU KOPRU YAZILIMI - Windows kaldirma betigi
REM
REM NE YAPAR
REM   1) Yonetici yetkisi denetler
REM   2) Servisi (gorevi) durdurur ve kaydini siler
REM   3) Kisayollari ve Baslat menusu klasorunu siler
REM   4) Program Ekle/Kaldir kaydini siler
REM   5) Program dizinini siler
REM   6) VERI dizinini SORAR — kendiliginden silmez
REM
REM NEDEN VERI DIZINI SORULUYOR
REM   Veri dizininde merkez kimligi, ayarlar ve merkeze AKTARILMAMIS
REM   yerel ucus kaydi olabilir. Kullanici yukseltme icin once kaldirip
REM   sonra kurabilir; veriyi sessizce silmek merkez kaydinin
REM   kaybolmasina ve sahada telemetrinin akmamasina yol acar.
REM
REM NEDEN `chcp 65001` YOK
REM   kur.bat'te bu komut baslaticiyi bozuyordu (bkz. kur.bat
REM   aciklamasi). Ayni tuzaga dusmemek icin kod sayfasi hic
REM   degistirilmiyor.
REM =====================================================================
setlocal EnableDelayedExpansion

if /i "%~1"=="ELDEN" goto :ELDEN_SIL

set "HEDEF=%ProgramFiles%\Goktungu\Kopru"
set "VERI=%ProgramData%\Goktungu\Kopru"
set "GOREV=GOKTUNGU Kopru"
set "BASLATMENU=%ProgramData%\Microsoft\Windows\Start Menu\Programs\GOKTUNGU"

echo ======================================================
echo  GOKTUNGU KOPRU YAZILIMI - kaldirma
echo ======================================================
echo.

net session >nul 2>&1
if !errorlevel! neq 0 (
  echo   [HATA] Bu betik YONETICI olarak calistirilmalidir.
  echo   kaldir.bat dosyasina sag tiklayip "Yonetici olarak calistir"
  echo   secenegini kullanin.
  echo.
  pause
  exit /b 1
)

REM ------------------------------------------------------------------
REM 1) SERVISI DURDUR VE SIL
REM ------------------------------------------------------------------
echo == Servis kaldiriliyor ==
schtasks /End /TN "%GOREV%" >nul 2>&1
call :SUREC_KAPAT
timeout /t 2 /nobreak >nul
schtasks /Delete /TN "%GOREV%" /F >nul 2>&1
echo   [OK] Servis durduruldu ve kaydi silindi

REM ------------------------------------------------------------------
REM 2) KISAYOLLAR
REM ------------------------------------------------------------------
echo.
echo == Kisayollar siliniyor ==
if exist "%BASLATMENU%" rd /s /q "%BASLATMENU%" >nul 2>&1
powershell -NoProfile -Command ^
  "$s=New-Object -ComObject WScript.Shell; $d=$s.SpecialFolders.Item('AllUsersDesktop'); if($d){Remove-Item ($d+'\GOKTUNGU Kopru.lnk') -Force -ErrorAction SilentlyContinue}; Remove-Item ([Environment]::GetFolderPath('Desktop')+'\GOKTUNGU Kopru.lnk') -Force -ErrorAction SilentlyContinue" >nul 2>&1

REM ESKI SURUM ARTIKLARI (1.2.x ve oncesi): kurulum kullanici dizinine
REM yapiliyordu ve baslangic klasorune VBS kopyasi/kisayol birakiyordu.
REM Kalirsa bilgisayar her acilista olmayan bir programi baslatmaya
REM calisir ve kullaniciya anlamsiz bir hata penceresi gosterir.
set "ESKIBAS=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
if exist "%ESKIBAS%\GOKTUNGU Kopru.vbs" del /f /q "%ESKIBAS%\GOKTUNGU Kopru.vbs" >nul 2>&1
if exist "%ESKIBAS%\GOKTUNGU Kopru.lnk" del /f /q "%ESKIBAS%\GOKTUNGU Kopru.lnk" >nul 2>&1
echo   [OK] Kisayollar silindi ^(eski surum artiklari dahil^)

REM ------------------------------------------------------------------
REM 3) PROGRAM EKLE/KALDIR KAYDI
REM ------------------------------------------------------------------
echo.
echo == Kayit siliniyor ==
reg delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\GoktunguKopru" /f >nul 2>&1
echo   [OK] Program Ekle/Kaldir kaydi silindi

REM ------------------------------------------------------------------
REM 4) VERI DIZINI (once sorulur, silme en sona birakilir)
REM ------------------------------------------------------------------
REM Soru program dizini silinmeden ONCE soruluyor: dizin silindikten
REM sonra bu betik kendi altindan kayabilir ve soru hic gorunmezdi.
set "VERISIL=0"
if exist "%VERI%" (
  echo.
  echo == Veri dizini ==
  echo   Konum : %VERI%
  echo   Icerik: merkez kimligi, ayarlar, gunlukler
  if exist "%VERI%\veri\akis_kesinti" (
    echo   DIKKAT: merkeze aktarilmamis yerel ucus kaydi olabilir:
    echo           %VERI%\veri\akis_kesinti
  )
  echo.
  echo   Silerseniz kopru yeniden kuruldugunda merkeze BASTAN
  echo   kaydedilmesi gerekir.
  echo.
  set /p "YANIT=  Veri dizini de silinsin mi? (e/H): "
  if /i "!YANIT!"=="e" set "VERISIL=1"
)

REM ------------------------------------------------------------------
REM 5) PROGRAM DIZINI
REM ------------------------------------------------------------------
echo.
echo == Program dosyalari siliniyor ==
REM kaldir.bat program dizininin ICINDEN calistirilmis olabilir; o
REM durumda dizini silmek "kullanimda" hatasi verir. Betik gecici bir
REM kopyaya tasinip silmeyi oradan tamamlar.
if /i "%~dp0"=="%HEDEF%\" (
  copy /Y "%~f0" "%TEMP%\goktungu_kaldir.bat" >nul 2>&1
  echo   [BILGI] Silme islemi gecici kopyadan tamamlaniyor...
  start "" cmd /c ""%TEMP%\goktungu_kaldir.bat" ELDEN !VERISIL!"
  exit /b 0
)

call :DIZIN_SIL "%HEDEF%"
if "!VERISIL!"=="1" (
  rd /s /q "%VERI%" >nul 2>&1
  rd "%ProgramData%\Goktungu" >nul 2>&1
  echo   [OK] Veri dizini silindi
) else (
  if exist "%VERI%" echo   [OK] Veri dizini KORUNDU: %VERI%
)

if exist "%APPDATA%\goktungu-kopru" (
  echo.
  echo   [BILGI] Eski surumden kalan veri dizini:
  echo     %APPDATA%\goktungu-kopru
  echo   Gerek duymuyorsaniz elle silebilirsiniz.
)

echo.
echo ======================================================
echo  KALDIRMA TAMAMLANDI
echo ======================================================
echo.
pause
exit /b 0

REM ------------------------------------------------------------------
REM Program dizininin icinden calistirildiginda buraya dusulur.
REM %2 = veri dizini de silinecek mi (1/0)
REM ------------------------------------------------------------------
:ELDEN_SIL
set "HEDEF=%ProgramFiles%\Goktungu\Kopru"
set "VERI=%ProgramData%\Goktungu\Kopru"
REM Cagiran cmd penceresinin dizin kilidini birakmasi beklenir.
timeout /t 3 /nobreak >nul
call :DIZIN_SIL "%HEDEF%"
if "%~2"=="1" (
  rd /s /q "%VERI%" >nul 2>&1
  rd "%ProgramData%\Goktungu" >nul 2>&1
  echo   [OK] Veri dizini silindi
)
echo.
echo ======================================================
echo  KALDIRMA TAMAMLANDI
echo ======================================================
echo.
pause
exit /b 0

REM ------------------------------------------------------------------
:DIZIN_SIL
if not exist "%~1" (
  echo   [BILGI] Dizin bulunamadi ^(zaten silinmis^): %~1
  exit /b 0
)
rd /s /q "%~1" >nul 2>&1
if exist "%~1" (
  echo   [UYARI] Bazi dosyalar silinemedi ^(kullanimda olabilir^).
  echo   Bilgisayari yeniden baslatip su dizini elle silin:
  echo     %~1
) else (
  echo   [OK] Silindi: %~1
)
REM Ust dizin bossa o da silinir; baska GOKTUNGU urunu kuruluysa dokunulmaz.
rd "%ProgramFiles%\Goktungu" >nul 2>&1
exit /b 0

REM ------------------------------------------------------------------
REM Yalniz BIZIM main.py'yi calistiran pythonw surecleri hedeflenir.
REM Tum pythonw sureclerini oldurmek kullanicinin baska programlarini
REM da kapatirdi.
REM ------------------------------------------------------------------
:SUREC_KAPAT
powershell -NoProfile -Command ^
  "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' or Name='python.exe'\" | Where-Object { $_.CommandLine -like '*main.py*' -and $_.CommandLine -like '*Goktungu*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
exit /b 0
