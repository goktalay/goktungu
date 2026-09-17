; ---------------------------------------------------------------------
; GOKTUNGU MERKEZ UYGULAMASI — Windows kurulum programi (NSIS)
;
; Kullanici istegi:
;   "bunun icin Ubuntu ve windows icin setup olusturacaksin. aynı
;    kopruede oldugu gibi."
;   "sunucu yazilimini indirdikten sonra ilk acilista postgresql
;    sihirbazi local webde gelsin."
;   "isteyen sirket yoneticisi ayni bilgisayara ister merkez yazilimini
;    isterse ayni anda kopru yazilimini calistirabilir."
;
; Derleme:  makensis -DSURUM=2.5.19 setup_merkez.nsi
;
; KOPRU SETUP'INDAN FARKLAR (setup.nsi ile karsilastirma):
;   1. Veri koku ProgramData'ya TASINIR (`GOKTUNGU_VERI_KOKU`). Kopru
;      bunu kendi ayar modulunde cozuyordu; GCS'in `sabitler.py`'si
;      veri kokunu kurulum dizinine gore hesapladigi icin burada
;      ortam degiskeni MAKINE genelinde yazilir.
;   2. Portlar KAYDIRILIR (8811/8910) ki kopru ile ayni makinede
;      calisabilsin.
;   3. Bitirme metni PostgreSQL sihirbazina yonlendirir.
;   4. Lisans dosyasi (`merkez_lisans.json`) varsa korunur.
;   5. Paket agirligi ~270 MB (opencv+numpy+psycopg2+pymavlink).
; ---------------------------------------------------------------------

Unicode true

!ifndef SURUM
  !define SURUM "2.5.19"
!endif

!define URUN         "GOKTUNGU Merkez Uygulamasi"
!define URUN_KISA    "GOKTUNGU Merkez"
!define SIRKET       "Turkbey Teknoloji Anonim Sirketi"
!define SERVIS_ADI   "GoktunguMerkez"
!define PANEL_URL    "http://127.0.0.1:8000/"
!define VERI_DIZINI  "C:\ProgramData\Goktungu\Merkez"
!define KAYIT_ANAHTAR "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoktunguMerkez"
!define AYAR_ANAHTAR  "Software\VEILOX\GoktunguMerkez"
!define ORTAM_ANAHTAR "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"

Name "${URUN} ${SURUM}"
OutFile "dagitim\GOKTUNGU-Merkez-Setup-${SURUM}.exe"
InstallDir "$PROGRAMFILES64\Goktungu\Merkez"
InstallDirRegKey HKLM "${AYAR_ANAHTAR}" "KurulumDizini"
BrandingText "${SIRKET}"
SetCompressor /SOLID lzma

RequestExecutionLevel admin

; ---------------------------------------------------------------------
; SURUM BILGISI
; ---------------------------------------------------------------------
VIProductVersion "${SURUM}.0"
VIAddVersionKey "ProductName"     "${URUN}"
VIAddVersionKey "CompanyName"     "${SIRKET}"
VIAddVersionKey "FileDescription" "${URUN} kurulum programi"
VIAddVersionKey "FileVersion"     "${SURUM}"
VIAddVersionKey "ProductVersion"  "${SURUM}"
VIAddVersionKey "LegalCopyright"  "(c) 2026 ${SIRKET}"

; ---------------------------------------------------------------------
; MODERN ARAYUZ
; ---------------------------------------------------------------------
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!include "WinVer.nsh"
!include "x64.nsh"

!define MUI_ICON   "varliklar\goktungu.ico"
!define MUI_UNICON "varliklar\goktungu.ico"
!define MUI_ABORTWARNING

!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Yerel arayuzu tarayicida ac"
!define MUI_FINISHPAGE_RUN_FUNCTION "ArayuzuAc"
!define MUI_FINISHPAGE_SHOWREADME ""
!define MUI_FINISHPAGE_SHOWREADME_NOTCHECKED
!define MUI_FINISHPAGE_SHOWREADME_TEXT "Masaustu kisayolu olustur"
!define MUI_FINISHPAGE_SHOWREADME_FUNCTION "MasaustuKisayolu"
!define MUI_FINISHPAGE_TEXT "${URUN} ${SURUM} kuruldu ve servis olarak baslatildi.$\r$\n$\r$\nArayuz adresi: ${PANEL_URL}$\r$\n$\r$\nILK ADIM — VERITABANI: Arayuze girdiginizde PostgreSQL kurulum sihirbazi acilir. Sunucu adresi, kullanici adi, sifre ve veritabani adini girin; tablolar otomatik olusturulur.$\r$\n$\r$\nILK ADIM — LISANS: Kurumsal panelinizden indirdiginiz merkez_lisans.json dosyasini su dizine kopyalayin:$\r$\n${VERI_DIZINI}"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "dagitim\LISANS.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "Turkish"

; ---------------------------------------------------------------------
; DEGISKENLER
; ---------------------------------------------------------------------
Var YukseltmeMi
Var EskiDizin

; ---------------------------------------------------------------------
; ON DENETIMLER
; ---------------------------------------------------------------------
Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP|MB_OK \
      "Bu kurulum yalniz 64-bit Windows uzerinde calisir.$\r$\n$\r$\nBilgisayariniz 32-bit Windows kullaniyor."
    Abort
  ${EndIf}

  ${IfNot} ${AtLeastWin7}
    MessageBox MB_ICONSTOP|MB_OK \
      "Bu kurulum Windows 7 SP1 veya daha yeni bir surum gerektirir."
    Abort
  ${EndIf}

  SetRegView 64

  StrCpy $YukseltmeMi "0"
  ReadRegStr $EskiDizin HKLM "${AYAR_ANAHTAR}" "KurulumDizini"
  ${If} $EskiDizin != ""
  ${AndIf} ${FileExists} "$EskiDizin\main.py"
    StrCpy $YukseltmeMi "1"
    StrCpy $INSTDIR $EskiDizin
  ${EndIf}
FunctionEnd

; ---------------------------------------------------------------------
; KURULUM
; ---------------------------------------------------------------------
Section "GOKTUNGU Merkez" AnaBolum
  SectionIn RO
  SetRegView 64
  SetShellVarContext all

  ${If} $YukseltmeMi == "1"
    DetailPrint "Mevcut kurulum bulundu: $INSTDIR"
    DetailPrint "Yukseltme kipi: veritabani ayarlari ve lisans korunacak."
  ${EndIf}

  ; -- 1) Servisi durdur ----------------------------------------------
  DetailPrint "Servis durduruluyor (varsa)..."
  nsExec::ExecToLog 'net stop "${SERVIS_ADI}"'
  Pop $0
  Sleep 2000

  ; -- 2) Veri dizinini ONCE olustur ----------------------------------
  ;
  ; SIRA KRITIKTIR: ortam degiskeni yazildiktan sonra servis baslatilir
  ; ve `sabitler.py` dizini yazilabilirlik icin SINAR. Dizin yoksa
  ; kendisi olusturmayi dener; olusturamazsa varsayilan (Program Files)
  ; koke doner ve veri yazilamaz. Burada onceden olusturmak bu yolu
  ; tamamen kapatir.
  DetailPrint "Veri dizini hazirlaniyor: ${VERI_DIZINI}"
  CreateDirectory "${VERI_DIZINI}"

  ; -- 3) Dosyalari yaz -----------------------------------------------
  DetailPrint "Program dosyalari yaziliyor..."
  SetOutPath "$INSTDIR"
  SetOverwrite on

  File "main.py"
  File "goktungu_guncelleyici.py"
  File "servis_merkez_win.py"

  ; assets/ agaci: paketle_merkez.py duz dizinleri buraya esler.
  DetailPrint "Uygulama dosyalari yaziliyor..."
  SetOutPath "$INSTDIR\assets"
  ; v2.4.216: Linux SDK (.so, aarch64) Windows kurulumuna GIRMEZ (30 MB)
  File /r /x "*.so" "dagitim\agac\assets\*.*"

  ; v2.4.218: AI modelleri (hava_araci.onnx ~100 MB + yuz/plaka) kurulumla
  ; gelir; onceden yalniz guncelleyici indiriyordu, ilk kurulumda YOKTU.
  DetailPrint "AI modelleri yaziliyor (~140 MB)..."
  SetOutPath "$INSTDIR\ai_modeller"
  File /r "dagitim\agac\ai_modeller\*.*"

  SetOutPath "$INSTDIR\varliklar"
  File "varliklar\goktungu.ico"

  ; Gomulu Python calisma zamani (~270 MB): Python 3.11.9 + websockets
  ; + pyserial + numpy + opencv + psycopg2 + pymavlink + pywin32.
  DetailPrint "Python calisma zamani yaziliyor (~270 MB, birkac dakika)..."
  SetOutPath "$INSTDIR\python"
  File /r "gomulu_merkez\calisma\*.*"

  ; -- 4) Modul cozumlemesini DOGRULA ---------------------------------
  ;
  ; Gomulu Python `python311._pth` yuzunden "isolated" kipte kosar:
  ; PYTHONPATH ve calisma dizini YOK SAYILIR. Kurulum koku ve
  ; assets\python ._pth'e yazilmamissa uygulama
  ;   ModuleNotFoundError: No module named 'goktungu'
  ; ile aninda duser; kullanici yalnizca "servis baslamadi" gorur.
  DetailPrint "Python modul yollari dogrulaniyor..."
  nsExec::ExecToLog '"$INSTDIR\python\python.exe" -c "import goktungu, psycopg2, cv2"'
  Pop $0
  ${If} $0 != 0
    DetailPrint "UYARI: modul cozumlemesi basarisiz (kod $0)"
    MessageBox MB_ICONEXCLAMATION|MB_OK \
      "Python calisma zamani dogrulamasi basarisiz (kod $0).$\r$\n$\r$\nUygulama baslatilamayabilir.$\r$\n$\r$\nDenetlenecek dosya:$\r$\n$INSTDIR\python\python311._pth$\r$\n$\r$\nBu dosya '..' ve '..\assets\python' satirlarini icermelidir."
  ${EndIf}

  ; -- 5) Makine genelinde ortam degiskenleri -------------------------
  ;
  ; NEDEN KAYIT DEFTERI (setx degil): `setx` 1024 karakter sinirina
  ; takilabilir ve servis ortamina yayilmasi icin yeniden baslatma
  ; gerekir. Kayit defterine yazip WM_SETTINGCHANGE yayinlamak
  ; standart yoldur; ayrica servisin kendisi de degeri kendi
  ; ortamina `setdefault` ile yaziyor (iki katmanli guvence).
  DetailPrint "Ortam degiskenleri yaziliyor..."

  ; Veri koku: Program Files YAZMAYA KAPALIDIR (LocalSystem servisi
  ; icin UAC sanallastirmasi islemez). Bu degisken olmadan ucus
  ; kayitlari, pg.json ve merkez_lisans.json yazilamaz.
  WriteRegExpandStr HKLM "${ORTAM_ANAHTAR}" "GOKTUNGU_VERI_KOKU" "${VERI_DIZINI}"

  ; Port kaydirma: kopru ile AYNI MAKINEDE calisabilmek icin.
  ; Olculen cakisma: MJPEG vekili 8801, AI iscisi 8900 (iki yazilimda
  ; da sabitti). Kopru varsayilanda kalir, merkez kayar.
  WriteRegStr HKLM "${ORTAM_ANAHTAR}" "GOKTUNGU_VIDEO_PORT" "8811"
  WriteRegStr HKLM "${ORTAM_ANAHTAR}" "GOKTUNGU_AI_PORT"    "8910"

  ; Acik pencerelerin yeni degerleri gormesi icin yayin yap.
  SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=3000

  ; -- 6) Servisi SCM'ye kaydet ---------------------------------------
  ${If} $YukseltmeMi == "0"
    DetailPrint "Windows servisi kaydediliyor..."
    nsExec::ExecToLog '"$INSTDIR\python\python.exe" "$INSTDIR\servis_merkez_win.py" --startup=delayed install'
    Pop $0
    ${If} $0 != 0
      DetailPrint "UYARI: servis kaydi cikis kodu $0"
      MessageBox MB_ICONEXCLAMATION|MB_OK \
        "Windows servisi kaydedilemedi (kod $0).$\r$\n$\r$\nKurulum tamamlandi ancak uygulama otomatik baslamayacak. Yonetici olarak su komutu deneyin:$\r$\n$\r$\n$INSTDIR\python\python.exe $INSTDIR\servis_merkez_win.py --startup=delayed install"
    ${EndIf}

    ; Kurtarma politikasi: servis cokerse 5/10/30 sn gecikmelerle uc
    ; kez yeniden baslat.
    nsExec::ExecToLog 'sc failure "${SERVIS_ADI}" reset= 86400 actions= restart/5000/restart/10000/restart/30000'
    Pop $0
  ${Else}
    DetailPrint "Servis kaydi guncelleniyor..."
    nsExec::ExecToLog '"$INSTDIR\python\python.exe" "$INSTDIR\servis_merkez_win.py" --startup=delayed update'
    Pop $0
  ${EndIf}

  ; -- 7) Servisi baslat ----------------------------------------------
  DetailPrint "Servis baslatiliyor..."
  nsExec::ExecToLog 'net start "${SERVIS_ADI}"'
  Pop $0
  ${If} $0 != 0
    DetailPrint "UYARI: servis baslatma cikis kodu $0"
    DetailPrint "Gunluk: ${VERI_DIZINI}\servis.log"
  ${EndIf}

  ; -- 8) Kisayollar --------------------------------------------------
  DetailPrint "Kisayollar olusturuluyor..."
  ; Eski surumlerden kalan "GOKTUNGU" klasorunu temizle (marka gecisi
  ; oncesi kurulumlar oraya kisayol yazmisti; birakilsa Baslat
  ; menusunde olu baglantilar asili kalirdi).
  Delete "$SMPROGRAMS\GOKTUNGU\GOKTUNGU Merkez.lnk"
  Delete "$SMPROGRAMS\GOKTUNGU\GOKTUNGU Merkez Kaldir.lnk"
  RMDir  "$SMPROGRAMS\GOKTUNGU"
  CreateDirectory "$SMPROGRAMS\GOKTUNGU"
  CreateShortCut "$SMPROGRAMS\GOKTUNGU\${URUN_KISA}.lnk" \
    "$INSTDIR\arayuz_ac.bat" "" "$INSTDIR\varliklar\goktungu.ico" 0 SW_SHOWMINIMIZED \
    "" "GOKTUNGU Merkez yerel arayuzu"
  CreateShortCut "$SMPROGRAMS\GOKTUNGU\${URUN_KISA} Kaldir.lnk" \
    "$INSTDIR\uninstall.exe" "" "$INSTDIR\varliklar\goktungu.ico" 0

  ; -- 9) Program Ekle/Kaldir kaydi -----------------------------------
  WriteRegStr HKLM "${AYAR_ANAHTAR}" "KurulumDizini" "$INSTDIR"
  WriteRegStr HKLM "${AYAR_ANAHTAR}" "Surum" "${SURUM}"

  WriteRegStr HKLM "${KAYIT_ANAHTAR}" "DisplayName"     "${URUN}"
  WriteRegStr HKLM "${KAYIT_ANAHTAR}" "DisplayVersion"  "${SURUM}"
  WriteRegStr HKLM "${KAYIT_ANAHTAR}" "Publisher"       "${SIRKET}"
  WriteRegStr HKLM "${KAYIT_ANAHTAR}" "DisplayIcon"     "$INSTDIR\varliklar\goktungu.ico"
  WriteRegStr HKLM "${KAYIT_ANAHTAR}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${KAYIT_ANAHTAR}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKLM "${KAYIT_ANAHTAR}" "QuietUninstallString" '"$INSTDIR\uninstall.exe" /S'
  WriteRegStr HKLM "${KAYIT_ANAHTAR}" "URLInfoAbout"    "https://goktungu.com"
  WriteRegDWORD HKLM "${KAYIT_ANAHTAR}" "NoModify" 1
  WriteRegDWORD HKLM "${KAYIT_ANAHTAR}" "NoRepair" 1

  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKLM "${KAYIT_ANAHTAR}" "EstimatedSize" "$0"

  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

; ---------------------------------------------------------------------
; ARAYUZ ACICI
;
; Kisayol dogrudan URL acsa da olur, ancak servis henuz baslamamissa
; tarayici "baglanti kurulamadi" gosterir. Bu betik servisi denetler,
; gerekiyorsa baslatir ve sonra arayuzu acar.
;
; PORT SORUNU: GCS HTTP portunu 8000'den baslayarak DENER; 8000 dolu
; ise 8080/8888/9000/5500'e duser. Sabit URL yanlis olabilir. Bu yuzden
; betik `veri\calisma.json` icindeki GERCEK portu okur.
; ---------------------------------------------------------------------
Section "-ArayuzAcici"
  SetOutPath "$INSTDIR"
  FileOpen $0 "$INSTDIR\arayuz_ac.bat" w
  FileWrite $0 "@echo off$\r$\n"
  FileWrite $0 "rem GOKTUNGU Merkez — yerel arayuzu acar.$\r$\n"
  FileWrite $0 "setlocal enabledelayedexpansion$\r$\n"
  FileWrite $0 'sc query "${SERVIS_ADI}" | find "RUNNING" >nul 2>&1$\r$\n'
  FileWrite $0 "if errorlevel 1 ($\r$\n"
  FileWrite $0 '  net start "${SERVIS_ADI}" >nul 2>&1$\r$\n'
  FileWrite $0 "  timeout /t 5 /nobreak >nul 2>&1$\r$\n"
  FileWrite $0 ")$\r$\n"
  FileWrite $0 "rem Gercek HTTP portunu calisma.json'dan oku (8000 dolu$\r$\n"
  FileWrite $0 "rem ise uygulama 8080/8888/9000/5500'e duser).$\r$\n"
  FileWrite $0 'set "ADRES=${PANEL_URL}"$\r$\n'
  FileWrite $0 'set "CJ=${VERI_DIZINI}\calisma.json"$\r$\n'
  FileWrite $0 'if exist "%CJ%" ($\r$\n'
  FileWrite $0 '  for /f "usebackq tokens=2 delims=:," %%A in (`findstr /c:"http_port" "%CJ%"`) do ($\r$\n'
  FileWrite $0 '    set "P=%%~A"$\r$\n'
  FileWrite $0 '    set "P=!P: =!"$\r$\n'
  FileWrite $0 '    if not "!P!"=="" set "ADRES=http://127.0.0.1:!P!/"$\r$\n'
  FileWrite $0 "  )$\r$\n"
  FileWrite $0 ")$\r$\n"
  FileWrite $0 'start "" "!ADRES!"$\r$\n'
  FileWrite $0 "endlocal$\r$\n"
  FileClose $0
SectionEnd

Function ArayuzuAc
  ExecShell "open" "${PANEL_URL}"
FunctionEnd

Function MasaustuKisayolu
  SetShellVarContext all
  CreateShortCut "$DESKTOP\${URUN_KISA}.lnk" \
    "$INSTDIR\arayuz_ac.bat" "" "$INSTDIR\varliklar\goktungu.ico" 0 SW_SHOWMINIMIZED \
    "" "GOKTUNGU Merkez yerel arayuzu"
FunctionEnd

Section "-MasaustuVarsayilan"
  Call MasaustuKisayolu
SectionEnd

; ---------------------------------------------------------------------
; KALDIRMA
; ---------------------------------------------------------------------
Section "Uninstall"
  SetRegView 64
  SetShellVarContext all

  DetailPrint "Servis durduruluyor..."
  nsExec::ExecToLog 'net stop "${SERVIS_ADI}"'
  Pop $0
  Sleep 2000

  DetailPrint "Servis kaydi kaldiriliyor..."
  nsExec::ExecToLog '"$INSTDIR\python\python.exe" "$INSTDIR\servis_merkez_win.py" remove'
  Pop $0
  nsExec::ExecToLog 'sc delete "${SERVIS_ADI}"'
  Pop $0

  DetailPrint "Kisayollar kaldiriliyor..."
  Delete "$SMPROGRAMS\GOKTUNGU\${URUN_KISA}.lnk"
  Delete "$SMPROGRAMS\GOKTUNGU\${URUN_KISA} Kaldir.lnk"
  RMDir  "$SMPROGRAMS\GOKTUNGU"
  ; Marka gecisi oncesi kurulumlarin klasoru de temizlenir.
  Delete "$SMPROGRAMS\GOKTUNGU\GOKTUNGU Merkez.lnk"
  Delete "$SMPROGRAMS\GOKTUNGU\GOKTUNGU Merkez Kaldir.lnk"
  RMDir  "$SMPROGRAMS\GOKTUNGU"
  Delete "$DESKTOP\${URUN_KISA}.lnk"

  DetailPrint "Ortam degiskenleri kaldiriliyor..."
  DeleteRegValue HKLM "${ORTAM_ANAHTAR}" "GOKTUNGU_VERI_KOKU"
  DeleteRegValue HKLM "${ORTAM_ANAHTAR}" "GOKTUNGU_VIDEO_PORT"
  DeleteRegValue HKLM "${ORTAM_ANAHTAR}" "GOKTUNGU_AI_PORT"
  SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=3000

  DetailPrint "Program dosyalari kaldiriliyor..."
  ; pywin32 `install` sirasinda bu iki dosyayi Python kokune KOPYALAR;
  ; paket listesinde olmadiklari icin acikca silinmeleri gerekir.
  Delete "$INSTDIR\python\pythonservice.exe"
  Delete "$INSTDIR\python\pywintypes311.dll"
  Delete "$INSTDIR\arayuz_ac.bat"
  Delete "$INSTDIR\main.py"
  Delete "$INSTDIR\goktungu_guncelleyici.py"
  Delete "$INSTDIR\servis_merkez_win.py"
  Delete "$INSTDIR\uninstall.exe"
  RMDir /r "$INSTDIR\assets"
  RMDir /r "$INSTDIR\ai_modeller"
  RMDir /r "$INSTDIR\varliklar"
  RMDir /r "$INSTDIR\python"
  RMDir /r "$INSTDIR\__pycache__"
  RMDir "$INSTDIR"
  RMDir "$PROGRAMFILES64\Goktungu"

  DeleteRegKey HKLM "${KAYIT_ANAHTAR}"
  DeleteRegKey HKLM "${AYAR_ANAHTAR}"

  ; VERITABANI AYARLARI, UCUS KAYITLARI VE LISANS KORUNUR.
  ;
  ; Kaldirma islemi `merkez_lisans.json` dosyasini SILMEZ: lisans
  ; 5.000 $ karsiligi tek seferlik satin alinmistir ve yeniden kurulumda
  ; musteriyi lisanssiz birakmak kabul edilemez. Ayni gerekce `pg.json`
  ; ve ucus kayitlari icin de gecerlidir.
  ; v2.5.64 (kullanici bildirimi #4): "Sistemden her seyi kaldirdim,
  ; yeniden kurdum; kurulum sihirbazi yerine dogrudan sayfa acildi."
  ; Neden: veri dizini (pg.json, lisans, kayitlar) kaldirmada
  ; KORUNUYORDU; yeni kurulum eski yapilandirmayi bulup sihirbazi
  ; atliyordu. Varsayilan yine KORUMA (lisans 5.000 $'lik tek seferlik
  ; satin almadir); ama kullanici ACIKCA isterse veri de silinir ve
  ; sonraki kurulum sifirdan (sihirbazla) baslar.
  MessageBox MB_ICONQUESTION|MB_YESNO|MB_DEFBUTTON2 \
    "Program kaldirildi.$\r$\n$\r$\nVERI DIZINI DE SILINSIN MI?$\r$\n${VERI_DIZINI}$\r$\n$\r$\nEVET: veritabani ayari, ucus kayitlari ve MERKEZ LISANSI silinir; sonraki kurulum sifirdan (kurulum sihirbaziyla) baslar.$\r$\nHAYIR: veri korunur (onerilen)." \
    IDYES veri_sil IDNO veri_koru
  veri_sil:
    DetailPrint "Veri dizini siliniyor: ${VERI_DIZINI}"
    RMDir /r "${VERI_DIZINI}"
    RMDir "C:\ProgramData\Goktungu"
    ; OLCULEN KUSUR (kullanici bildirimi, 2.5.64): program dizinindeki
    ; `veri\` alt klasoru HIC silinmiyordu. Ortam degiskeni servise
    ; ulasmadan calisan ilk surumler pg.json'u BURAYA yazar; kod da
    ; gecis kurali geregi bu eski konumu okumaya devam eder. Sonuc:
    ; kullanici ProgramData'yi elle silse bile yeniden kurulumda eski
    ; pg.json bulunuyor, "yapilandirilmis" sayiliyor ve kurulum
    ; sihirbazi hic acilmiyordu.
    RMDir /r "$INSTDIR\veri"
    Delete "$INSTDIR\pg.json"
    Delete "$INSTDIR\gcs_ayarlar.json"
    Delete "$INSTDIR\gcs.db"
    RMDir "$INSTDIR"
    MessageBox MB_ICONINFORMATION|MB_OK \
      "Veri silindi.$\r$\n$\r$\nNOT: PostgreSQL sunucusundaki veritabaninin kendisi (goktungu) SILINMEZ; sonraki kurulumda sihirbaz ayni veritabanina yeniden baglanabilir veya yenisini olusturabilir."
    Goto veri_bitti
  veri_koru:
    DetailPrint "Veri korundu: ${VERI_DIZINI}"
    ; Eski konumdaki veri de korunur; kullanici nerede oldugunu bilsin.
    IfFileExists "$INSTDIR\veri\*.*" 0 veri_bitti
      DetailPrint "Eski konumdaki veri de korundu: $INSTDIR\veri"
  veri_bitti:
SectionEnd
