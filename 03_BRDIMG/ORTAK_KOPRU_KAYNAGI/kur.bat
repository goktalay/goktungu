@echo off
REM =====================================================================
REM GOKTUNGU KOPRU YAZILIMI - Windows kurulum betigi
REM
REM NE YAPAR
REM   1) Yonetici yetkisi ister (gerekli: Program Files + servis kaydi)
REM   2) Python 3.11+ bulur
REM   3) C:\Program Files\Goktungu\Kopru altina kurar
REM   4) Sanal ortam kurar, bagimliliklari yukler
REM   5) Sistem baslangicinda calisan bir GOREV (servis) kaydeder
REM   6) Baslat menusu + masaustu kisayolu olusturur (GOKTUNGU mavi ikonu)
REM   7) Mevcut kurulum varsa YENIDEN KURMAZ: durdur -> guncelle -> baslat
REM
REM NEDEN GOREV ZAMANLAYICI, `sc.exe` SERVISI DEGIL
REM   Python betigi Windows Servis Denetim Yoneticisi (SCM) ile
REM   konusmaz. `sc.exe create ... binPath=pythonw.exe main.py` ile
REM   kurulan bir kayit, SCM'nin bekledigi "basladim" bildirimini
REM   alamadigi icin 30 saniye sonra "servis zamaninda yanit vermedi"
REM   (hata 1053) ile basarisiz olur. Gercek servis icin `pywin32`
REM   gerekir; bu pip ile inen ~10 MB'lik bir ek bagimliliktir ve
REM   sahada internetsiz kurulumda kurulum basarisiz olur.
REM
REM   Gorev Zamanlayici Windows'un kendi parcasidir, ek bagimlilik
REM   istemez ve kullanicinin istedigi davranisi TAM saglar:
REM     - `/SC ONSTART`  : bilgisayar acilinca, oturum acilmasa da baslar
REM     - `/RU SYSTEM`   : kullanici oturumundan bagimsiz
REM     - `schtasks /End` ve `/Run` ile durdurulup baslatilabilir
REM
REM NEDEN VERI DIZINI ProgramData
REM   Gorev SYSTEM olarak calisir; bu hesabin %APPDATA% dizini
REM   C:\Windows\System32\config\systemprofile\... altindadir.
REM   Kimlik dosyasi oraya yazilirsa kullanici goremez, yedekleyemez ve
REM   servis hesabi degisirse merkez kaydi KAYBOLUR. Bu yuzden
REM   GOKTUNGU_KOPRU_VERI ortam degiskeni ile C:\ProgramData\Goktungu\Kopru\veri
REM   dizinine yonlendiriliyor (ayar.py bu degiskeni destekler).
REM
REM NEDEN KISAYOL PROGRAMI BASLATMIYOR
REM   Kopru artik servis olarak surekli calisir. Kisayolun isi paneli
REM   TARAYICIDA acmaktir. Eski surumde kisayol programi baslatiyordu ve
REM   kullanici cift tiklayinca ikinci bir ornek acilip port catismasi
REM   olusuyordu.
REM
REM NEDEN `chcp 65001` YOK
REM   Onceki surumde vardi ve baslaticiyi BOZUYORDU: konsol UTF-8'e
REM   alininca `echo` ile yazilan .vbs UTF-8 baytlariyla olusuyor, ancak
REM   wscript.exe BOM'suz .vbs'i ANSI (Turkce Windows'ta cp1254) saniyor.
REM   "Masaustu" yolundaki 'u' bozulup 80070003 veriyordu. Kod sayfasi
REM   hic degistirilmiyor.
REM =====================================================================
setlocal EnableDelayedExpansion

set "KAYNAK=%~dp0"
set "KAYNAK=%KAYNAK:~0,-1%"

set "HEDEF=%ProgramFiles%\Goktungu\Kopru"
set "VERI=%ProgramData%\Goktungu\Kopru\veri"
set "GOREV=GOKTUNGU Kopru"
set "PANEL=http://127.0.0.1:8790/"

echo ======================================================
echo  GOKTUNGU KOPRU YAZILIMI - Windows kurulumu
echo  VEILOX Savunma Anonim Sirketi
echo ======================================================
echo.

REM ------------------------------------------------------------------
REM 0) YONETICI YETKISI
REM ------------------------------------------------------------------
REM Program Files'a yazmak ve gorev kaydetmek yonetici yetkisi ister.
REM Yetki yoksa kurulum YARIDA kalir: dosyalar kopyalanamaz ama betik
REM devam edip "tamamlandi" der. Bu yuzden en basta denetlenir.
net session >nul 2>&1
if !errorlevel! neq 0 (
  echo   [HATA] Bu kurulum YONETICI olarak calistirilmalidir.
  echo.
  echo   Nasil yapilir:
  echo     kur.bat dosyasina SAG TIKLAYIN
  echo     "Yonetici olarak calistir" secenegini kullanin
  echo.
  echo   Neden gerekli:
  echo     - "%HEDEF%" dizinine yazmak
  echo     - Sistem baslangicinda calisan gorevi kaydetmek
  echo.
  pause
  exit /b 1
)
echo   [OK] Yonetici yetkisi var

REM ------------------------------------------------------------------
REM 1) PYTHON 3.11+ BUL
REM ------------------------------------------------------------------
echo.
echo == Python araniyor (en az 3.11) ==
set "PY="

REM `py` baslatici surumu ISME gore secer; en guvenilir yol budur.
for %%v in (3.13 3.12 3.11) do (
  if not defined PY (
    py -%%v -c "import sys; sys.exit(0)" >nul 2>&1
    if !errorlevel! equ 0 set "PY=py -%%v"
  )
)

REM `py` yoksa PATH'teki python denenir ve SURUMU DENETLENIR. Denetlemeden
REM kabul etmek Microsoft Store'un sahte python.exe kisayoluna ya da eski
REM bir 3.9 kurulumuna dusmeye yol acar.
if not defined PY (
  python -c "import sys; sys.exit(0 if sys.version_info>=(3,11) else 1)" >nul 2>&1
  if !errorlevel! equ 0 set "PY=python"
)

if not defined PY (
  echo.
  echo   [HATA] Python 3.11 veya ustu bulunamadi.
  echo.
  echo   Kurulum:
  echo     1^) https://www.python.org/downloads/ adresinden Python 3.11+
  echo        indirin
  echo     2^) Kurulumda "Add python.exe to PATH" kutusunu ISARETLEYIN
  echo     3^) Bu betigi yeniden calistirin
  echo.
  echo   NOT: Python.org surumu onerilir; Microsoft Store surumu seri
  echo   ^(USB^) telemetri erisiminde sorun cikarabilir.
  echo.
  pause
  exit /b 1
)

for /f "tokens=*" %%i in ('%PY% -V 2^>^&1') do echo   [OK] Bulundu: %%i

REM ------------------------------------------------------------------
REM 2) MEVCUT KURULUMU ALGILA
REM ------------------------------------------------------------------
echo.
echo == Mevcut kurulum denetleniyor ==
set "YUKSELTME=0"
if exist "%HEDEF%\main.py" set "YUKSELTME=1"

if "!YUKSELTME!"=="1" (
  set "ESKI=bilinmiyor"
  if exist "%HEDEF%\SURUM" for /f "usebackq tokens=*" %%s in ("%HEDEF%\SURUM") do set "ESKI=%%s"
  echo   [BILGI] Kurulu surum: !ESKI!
  set "YENI=bilinmiyor"
  if exist "%KAYNAK%\SURUM" for /f "usebackq tokens=*" %%s in ("%KAYNAK%\SURUM") do set "YENI=%%s"
  echo   [BILGI] Yeni surum   : !YENI!
  echo   [BILGI] YUKSELTME kipi: servis durdurulacak, dosyalar
  echo           guncellenecek, servis yeniden baslatilacak.
  echo           Ayarlariniz ve merkez kaydiniz KORUNUR.
) else (
  echo   [BILGI] Ilk kurulum
)

REM ------------------------------------------------------------------
REM 3) DIZINLER VE SANAL ORTAM (servis AYAKTA iken)
REM ------------------------------------------------------------------
REM NEDEN SERVISI BURADA DURDURMUYORUZ
REM   Ilk tasarimda servis bu noktada durduruluyordu. Arkasindan gelen
REM   `pip install` adimi ag hizina bagli olarak 30-60 saniye suruyor.
REM   Linux tarafinda ayni sira olculdu: kesinti 62 SANIYE cikti. Kopru
REM   bu sure boyunca telemetri aktarmaz; devam eden bir ucus varsa o
REM   dakikanin verisi kaybedilir.
REM
REM   Dogru sira: agdan indirme gerektiren UZUN hazirliklar servis ayakta
REM   yapilir; servis yalnizca dosyalarin yer degistirdigi kisa pencerede
REM   durur. Sanal ortam hedef dizinin ICINDE oldugu icin bu guvenlidir:
REM   pip yalniz .venv altina yazar, calisan surecin ice aktardigi
REM   kopru\ ve web\ dosyalarina dokunmaz.
if not exist "%HEDEF%" mkdir "%HEDEF%" 2>nul
if not exist "%VERI%"  mkdir "%VERI%"  2>nul

echo.
echo == Sanal ortam hazirlaniyor ==
if not exist "%HEDEF%\.venv\Scripts\python.exe" (
  %PY% -m venv "%HEDEF%\.venv"
  if !errorlevel! neq 0 (
    echo   [HATA] Sanal ortam olusturulamadi.
    pause
    exit /b 1
  )
  echo   [OK] Olusturuldu
) else (
  echo   [OK] Mevcut sanal ortam korundu
)

echo.
echo == Bagimliliklar kuruluyor ==
"%HEDEF%\.venv\Scripts\python.exe" -m pip install --upgrade pip -q 2>nul
"%HEDEF%\.venv\Scripts\python.exe" -m pip install -q websockets pyserial
if !errorlevel! neq 0 (
  echo   [HATA] Bagimliliklar kurulamadi. Internet baglantinizi ve
  echo   varsa vekil sunucu ^(proxy^) ayarlarinizi denetleyin.
  pause
  exit /b 1
)
echo   [OK] websockets ve pyserial kuruldu

REM ------------------------------------------------------------------
REM 4) SERVISI DURDUR (yukseltme ise) VE DOSYALARI KOPYALA
REM ------------------------------------------------------------------
REM Kesinti penceresi BURADA baslar ve bu bolumun sonunda kapanir:
REM yalnizca dosya kopyalama suresi.
REM
REM Dosyalari calisan surecin altindan degistirmek Windows'ta
REM "dosya baska bir islem tarafindan kullaniliyor" hatasi verir ve
REM kurulum yarim kalir. Once durdurulur.
if "!YUKSELTME!"=="1" (
  echo.
  echo == Servis durduruluyor ==
  schtasks /End /TN "%GOREV%" >nul 2>&1
  REM Gorev "End" sonrasi surecin gercekten olmesi icin kisa bekleme;
  REM ayrica gorevden bagimsiz elle baslatilmis ornekler de kapatilir.
  taskkill /F /IM pythonw.exe /FI "WINDOWTITLE eq GOKTUNGU*" >nul 2>&1
  call :SUREC_KAPAT
  timeout /t 2 /nobreak >nul
  echo   [OK] Durduruldu
)

echo.
echo == Dosyalar kuruluyor ==
echo   Hedef: %HEDEF%

REM /E  alt dizinler dahil    /Y  sormadan uzerine yaz
REM /EXCLUDE ile .venv haric tutulur: venv makineye ozgudur ve zaten
REM hedefte kurulur; kaynaktakini kopyalamak bozuk bir venv uretir.
REM Kaynak arsivde .venv yoktur ama kullanici kur.bat'i gelistirme
REM dizininde calistirirsa diye korunuyor.
> "%TEMP%\goktungu_haric.txt" echo \.venv\
>> "%TEMP%\goktungu_haric.txt" echo \__pycache__\
>> "%TEMP%\goktungu_haric.txt" echo .pyc

xcopy "%KAYNAK%\kopru"     "%HEDEF%\kopru\"     /E /Y /I /Q /EXCLUDE:%TEMP%\goktungu_haric.txt >nul
xcopy "%KAYNAK%\web"       "%HEDEF%\web\"       /E /Y /I /Q >nul
if exist "%KAYNAK%\varliklar" xcopy "%KAYNAK%\varliklar" "%HEDEF%\varliklar\" /E /Y /I /Q >nul
copy /Y "%KAYNAK%\main.py"     "%HEDEF%\" >nul
copy /Y "%KAYNAK%\SURUM"       "%HEDEF%\" >nul 2>&1
copy /Y "%KAYNAK%\kaldir.bat"  "%HEDEF%\" >nul 2>&1
copy /Y "%KAYNAK%\kur.bat"     "%HEDEF%\" >nul 2>&1
del /f /q "%TEMP%\goktungu_haric.txt" >nul 2>&1

if not exist "%HEDEF%\main.py" (
  echo   [HATA] Dosyalar kopyalanamadi.
  echo   "%HEDEF%" dizinine yazma izni denetlenmeli.
  pause
  exit /b 1
)
echo   [OK] Program dosyalari yerlestirildi
echo   [OK] Veri dizini: %VERI%

REM ------------------------------------------------------------------
REM 6) SERVIS (GOREV) KAYDI
REM ------------------------------------------------------------------
REM --tarayici-yok: servis kipinde tarayici acmak anlamsizdir. Session 0
REM icinde grafik oturum yoktur ve tarayici acma cagrisi saniyelerce
REM bloke olur.
echo.
echo == Servis kaydediliyor ==

REM Sarmalayici .cmd: gorev komut satirinda ortam degiskeni ATAYAMAZ.
REM GOKTUNGU_KOPRU_VERI'yi burada ayarliyoruz (bkz. bastaki aciklama).
> "%HEDEF%\servis.cmd" echo @echo off
>> "%HEDEF%\servis.cmd" echo REM GOKTUNGU Kopru servis sarmalayicisi - kur.bat tarafindan uretildi
>> "%HEDEF%\servis.cmd" echo set "GOKTUNGU_KOPRU_VERI=%VERI%"
>> "%HEDEF%\servis.cmd" echo cd /d "%HEDEF%"
>> "%HEDEF%\servis.cmd" echo "%HEDEF%\.venv\Scripts\pythonw.exe" "%HEDEF%\main.py" --tarayici-yok

REM Eski kayit varsa once silinir; /F ile sorgusuz.
schtasks /Delete /TN "%GOREV%" /F >nul 2>&1

schtasks /Create /TN "%GOREV%" /TR "\"%HEDEF%\servis.cmd\"" /SC ONSTART /RU SYSTEM /RL HIGHEST /F >nul 2>&1
if !errorlevel! neq 0 (
  echo   [UYARI] Sistem baslangici gorevi kaydedilemedi.
  echo   Program calisir ancak bilgisayar yeniden baslatildiginda
  echo   kendiliginden acilmaz. Elle baslatmak icin:
  echo     schtasks /Run /TN "%GOREV%"
) else (
  echo   [OK] Sistem baslangicinda otomatik calisacak
)

schtasks /Run /TN "%GOREV%" >nul 2>&1
if !errorlevel! equ 0 (
  echo   [OK] Servis baslatildi
) else (
  echo   [UYARI] Servis simdi baslatilamadi; bilgisayar yeniden
  echo   baslatildiginda calisacak.
)

REM ------------------------------------------------------------------
REM 7) KISAYOLLAR (GOKTUNGU mavi ikonu)
REM ------------------------------------------------------------------
REM Kisayol PANELI ACAR, programi baslatmaz (servis zaten calisiyor).
REM
REM Yollar PowerShell'e ORTAM DEGISKENI ile gecirilir, komut satirinda
REM metin olarak gomulmez: kullanicinin yolu bosluk, tek tirnak ya da
REM Turkce karakter icerebilir ve komut satirinda gomulen dize
REM PowerShell ayristiricisinda bozulur.
echo.
echo == Kisayollar olusturuluyor ==

set "IKON=%HEDEF%\varliklar\goktungu.ico"
if not exist "%IKON%" set "IKON=%SystemRoot%\System32\shell32.dll,14"

set "GOKTUNGU_PANEL=%PANEL%"
set "GOKTUNGU_IKON=%IKON%"
set "GOKTUNGU_HEDEF=%HEDEF%"

REM --- Baslat menusu (tum kullanicilar) ---
set "BASLATMENU=%ProgramData%\Microsoft\Windows\Start Menu\Programs\GOKTUNGU"
if not exist "%BASLATMENU%" mkdir "%BASLATMENU%" 2>nul
set "GOKTUNGU_MENU=%BASLATMENU%"

powershell -NoProfile -Command ^
  "$s=New-Object -ComObject WScript.Shell; $k=$s.CreateShortcut($env:GOKTUNGU_MENU+'\GOKTUNGU Kopru Paneli.lnk'); $k.TargetPath=$env:GOKTUNGU_PANEL; $k.IconLocation=$env:GOKTUNGU_IKON; $k.Description='GOKTUNGU Kopru yerel yonetim paneli'; $k.Save()" >nul 2>&1

if exist "%BASLATMENU%\GOKTUNGU Kopru Paneli.lnk" (
  echo   [OK] Baslat menusu kisayolu: GOKTUNGU ^> GOKTUNGU Kopru Paneli
) else (
  echo   [UYARI] Baslat menusu kisayolu olusturulamadi
)

REM --- Masaustu (tum kullanicilar) ---
powershell -NoProfile -Command ^
  "$s=New-Object -ComObject WScript.Shell; $d=$s.SpecialFolders.Item('AllUsersDesktop'); if(-not $d){$d=[Environment]::GetFolderPath('Desktop')}; $k=$s.CreateShortcut($d+'\GOKTUNGU Kopru.lnk'); $k.TargetPath=$env:GOKTUNGU_PANEL; $k.IconLocation=$env:GOKTUNGU_IKON; $k.Description='GOKTUNGU Kopru yerel yonetim paneli'; $k.Save()" >nul 2>&1
echo   [OK] Masaustu kisayolu olusturuldu

REM --- Servis yonetim kisayollari (Baslat menusu altinda) ---
REM Kullanici "baslat/durdur/yeniden baslat" dugmeleri istedi. Panel
REM icinden de yapilabilir, ancak servis durmussa panel acilmaz; bu
REM yuzden isletim sistemi duzeyinde de erisim birakiliyor.
> "%HEDEF%\servis_baslat.cmd" echo @echo off
>> "%HEDEF%\servis_baslat.cmd" echo schtasks /Run /TN "%GOREV%"
>> "%HEDEF%\servis_baslat.cmd" echo timeout /t 3 /nobreak ^>nul
>> "%HEDEF%\servis_baslat.cmd" echo start "" "%PANEL%"

> "%HEDEF%\servis_durdur.cmd" echo @echo off
>> "%HEDEF%\servis_durdur.cmd" echo schtasks /End /TN "%GOREV%"

powershell -NoProfile -Command ^
  "$s=New-Object -ComObject WScript.Shell; foreach($p in @(@('Kopruyu Baslat','servis_baslat.cmd'),@('Kopruyu Durdur','servis_durdur.cmd'))){$k=$s.CreateShortcut($env:GOKTUNGU_MENU+'\'+$p[0]+'.lnk'); $k.TargetPath=$env:GOKTUNGU_HEDEF+'\'+$p[1]; $k.IconLocation=$env:GOKTUNGU_IKON; $k.WorkingDirectory=$env:GOKTUNGU_HEDEF; $k.Save()}" >nul 2>&1
echo   [OK] Servis yonetim kisayollari olusturuldu

REM ------------------------------------------------------------------
REM 8) PROGRAM EKLE/KALDIR KAYDI
REM ------------------------------------------------------------------
REM Kullanici programi Windows Ayarlar > Uygulamalar uzerinden
REM kaldirabilmeli. Kayit olmadan program "hayalet kurulum" olur.
set "SURUMNO=1.3.0"
if exist "%HEDEF%\SURUM" for /f "usebackq tokens=*" %%s in ("%HEDEF%\SURUM") do set "SURUMNO=%%s"

reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\GoktunguKopru" /f ^
  /v DisplayName    /t REG_SZ /d "GOKTUNGU Kopru Yazilimi" >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\GoktunguKopru" /f ^
  /v DisplayVersion /t REG_SZ /d "%SURUMNO%" >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\GoktunguKopru" /f ^
  /v Publisher      /t REG_SZ /d "VEILOX Savunma Anonim Sirketi" >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\GoktunguKopru" /f ^
  /v DisplayIcon    /t REG_SZ /d "%IKON%" >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\GoktunguKopru" /f ^
  /v InstallLocation /t REG_SZ /d "%HEDEF%" >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\GoktunguKopru" /f ^
  /v UninstallString /t REG_SZ /d "\"%HEDEF%\kaldir.bat\"" >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\GoktunguKopru" /f ^
  /v NoModify /t REG_DWORD /d 1 >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\GoktunguKopru" /f ^
  /v NoRepair /t REG_DWORD /d 1 >nul 2>&1

echo.
echo == Kayit ==
echo   [OK] Program Ekle/Kaldir listesine eklendi

REM ------------------------------------------------------------------
REM 9) SONUC
REM ------------------------------------------------------------------
echo.
echo == Panel denetleniyor ==
REM Servisin gercekten ayaga kalktigini dogrula. "Kuruldu" demek yeterli
REM degil; kullanici panele girip calismadigini gorurse kurulumun
REM neresinin bozuk oldugunu bilemez.
set "AYAKTA=0"
for /l %%i in (1,1,10) do (
  if "!AYAKTA!"=="0" (
    powershell -NoProfile -Command "try{(New-Object Net.Sockets.TcpClient).Connect('127.0.0.1',8790); exit 0}catch{exit 1}" >nul 2>&1
    if !errorlevel! equ 0 (set "AYAKTA=1") else (timeout /t 1 /nobreak >nul)
  )
)

echo.
echo ======================================================
if "!YUKSELTME!"=="1" (
  echo  YUKSELTME TAMAMLANDI
) else (
  echo  KURULUM TAMAMLANDI
)
echo ======================================================
echo  Kurulum dizini : %HEDEF%
echo  Veri dizini    : %VERI%
echo  Panel adresi   : %PANEL%
if "!AYAKTA!"=="1" (
  echo  Servis durumu  : CALISIYOR
) else (
  echo  Servis durumu  : YANIT VERMIYOR
  echo.
  echo  Panel yanit vermiyor. Denetim:
  echo    schtasks /Query /TN "%GOREV%" /V /FO LIST
  echo    "%HEDEF%\servis.cmd"   ^(elle calistirip hatayi gorun^)
)
echo.
if "!YUKSELTME!"=="0" (
  echo  Ilk adim: panele girip merkez kullanici adiniz ve sifrenizle
  echo  oturum acin, ardindan "Bu bilgisayari merkeze kaydet"
  echo  dugmesini kullanin.
  echo.
)
echo  Kisayollar:
echo    Masaustu             - GOKTUNGU Kopru
echo    Baslat ^> GOKTUNGU       - Panel, Baslat, Durdur
echo.
echo  Kaldirmak icin: Ayarlar ^> Uygulamalar ^> GOKTUNGU Kopru Yazilimi
echo  veya "%HEDEF%\kaldir.bat"
echo ======================================================
echo.

if "!AYAKTA!"=="1" start "" "%PANEL%"
pause
exit /b 0

REM ------------------------------------------------------------------
REM Yardimci: calisan kopru surecini kapat
REM ------------------------------------------------------------------
REM main.py'yi calistiran pythonw sureclerini komut satirina bakarak
REM bulur. Tum pythonw sureclerini oldurmek kullanicinin baska
REM programlarini da kapatirdi.
:SUREC_KAPAT
for /f "skip=1 tokens=1" %%p in ('wmic process where "name='pythonw.exe'" get processid 2^>nul') do (
  for /f "tokens=*" %%c in ('wmic process where "processid=%%p" get commandline /value 2^>nul ^| findstr /i "Goktungu"') do (
    taskkill /F /PID %%p >nul 2>&1
  )
)
exit /b 0
