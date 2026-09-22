; ---------------------------------------------------------------------
; GOKTUNGU KOPRU YAZILIMI — Windows kurulum programi (NSIS)
;
; Kullanici istegi: "konsol degil bildigin kurulum setup programi,
; exe olarak" + "servis olarak calismasini istemistim".
;
; Bu betik `makensis` ile Linux'ta derlenir:
;     makensis -DSURUM=1.4.0 setup.nsi
;
; NEDEN NSIS: Inno Setup derleyicisi yalniz Windows'ta calisir.
; makensis Linux'ta yerel calisir, capraz derleme icin Wine gerekmez.
;
; NEDEN GOMULU PYTHON: kullanici Python kurmak zorunda kalmamali.
; Python 3.11.9 + websockets + pyserial + pywin32 setup icine girer.
; pywin32 GERCEK Windows servisi icin zorunludur.
; ---------------------------------------------------------------------

Unicode true

!ifndef SURUM
  !define SURUM "1.4.0"
!endif

; ---------------------------------------------------------------------
; URUN KIMLIGI (Faz 5)
;
; Asagidaki tanimlar `!ifndef` ile korunur: BRDTLM sarmalayicisi
; (04_BRDTLM) makensis'e `-DURUN=...  -DSERVIS_ADI=GoktunguKopruTlm
; -DURUN_PROFIL=brdtlm ...` gecerek AYRI bir urun uretebilir.
;
; GERIYE UYUMLULUK — KRITIK: hicbir `-D` verilmezse tanimlar mevcut
; degerlerine cozulur ve uretilen setup.exe BYTE-AYNI kalir. Yeni
; `URUN_PROFIL` tanimi verilmedigi surece kurulum $INSTDIR\URUN dosyasini
; yazmaz; BRDIMG davranisi degismez.
; ---------------------------------------------------------------------
!ifndef URUN
  !define URUN         "GOKTUNGU Kopru Yazilimi"
!endif
!ifndef URUN_KISA
  !define URUN_KISA    "GOKTUNGU Kopru"
!endif
!define SIRKET       "Turkbey Teknoloji Anonim Sirketi"
!ifndef SERVIS_ADI
  !define SERVIS_ADI   "GoktunguKopru"
!endif
!ifndef PANEL_URL
  !define PANEL_URL    "http://127.0.0.1:8790/"
!endif
!ifndef KAYIT_ANAHTAR
  !define KAYIT_ANAHTAR "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoktunguKopru"
!endif
!ifndef AYAR_ANAHTAR
  !define AYAR_ANAHTAR  "Software\VEILOX\GoktunguKopru"
!endif
!ifndef CIKTI_AD
  !define CIKTI_AD     "GOKTUNGU-Kopru-Setup"
!endif
!ifndef KURULUM_DIZIN
  !define KURULUM_DIZIN "$PROGRAMFILES64\Goktungu\Kopru"
!endif

Name "${URUN} ${SURUM}"
OutFile "dagitim\${CIKTI_AD}-${SURUM}.exe"
InstallDir "${KURULUM_DIZIN}"
InstallDirRegKey HKLM "${AYAR_ANAHTAR}" "KurulumDizini"
BrandingText "${SIRKET}"
SetCompressor /SOLID lzma

; Yonetici hakki: Program Files'a yazmak ve SCM'ye servis kaydetmek
; icin zorunludur. `admin` degeri UAC yukseltme istemini tetikler.
RequestExecutionLevel admin

; ---------------------------------------------------------------------
; SURUM BILGISI (exe ozelliklerinde gorunur)
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

; Bitirme sayfasi: kullanici paneli hemen acabilsin.
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Yerel paneli tarayicida ac"
!define MUI_FINISHPAGE_RUN_FUNCTION "PaneliAc"
!define MUI_FINISHPAGE_SHOWREADME ""
!define MUI_FINISHPAGE_SHOWREADME_NOTCHECKED
!define MUI_FINISHPAGE_SHOWREADME_TEXT "Masaustu kisayolu olustur"
!define MUI_FINISHPAGE_SHOWREADME_FUNCTION "MasaustuKisayolu"
!define MUI_FINISHPAGE_TEXT "${URUN} ${SURUM} kuruldu ve servis olarak baslatildi.$\r$\n$\r$\nServis Windows ile birlikte otomatik baslar. Yerel panel adresi:$\r$\n${PANEL_URL}$\r$\n$\r$\nIlk adim: panele girip merkez kullanici adiniz ve sifrenizle oturum acin, ardindan 'Bu bilgisayari merkeze kaydet' dugmesini kullanin."

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
  ; 64-bit zorunlu: gomulu Python amd64 derlemesidir.
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP|MB_OK \
      "Bu kurulum yalniz 64-bit Windows uzerinde calisir.$\r$\n$\r$\nBilgisayariniz 32-bit Windows kullaniyor."
    Abort
  ${EndIf}

  ; Windows 7 SP1 ve uzeri: Python 3.11 daha eskisini desteklemez.
  ${IfNot} ${AtLeastWin7}
    MessageBox MB_ICONSTOP|MB_OK \
      "Bu kurulum Windows 7 SP1 veya daha yeni bir surum gerektirir."
    Abort
  ${EndIf}

  SetRegView 64

  ; Mevcut kurulum var mi? Varsa YUKSELTME kipine gec.
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
Section "GOKTUNGU Kopru" AnaBolum
  SectionIn RO
  SetRegView 64
  SetShellVarContext all

  ; -- 1) Yukseltme ise once eski surumun v1.3.0 artiklarini kaldir ---
  ${If} $YukseltmeMi == "1"
    DetailPrint "Mevcut kurulum bulundu: $INSTDIR"
    DetailPrint "Yukseltme kipi: ayarlar ve merkez kimligi korunacak."
  ${EndIf}

  ; v1.3.0 Gorev Zamanlayici gorevini kaldir. Kaldirilmazsa hem gorev
  ; hem servis ayni anda kopru baslatir; ikinci ornek tek-ornek
  ; kilidine takilir ve kullanici "servis calismiyor" sanir.
  DetailPrint "Onceki surum artiklari temizleniyor..."
  nsExec::ExecToLog 'schtasks /Delete /TN "GOKTUNGU Kopru" /F'
  Pop $0
  nsExec::ExecToLog 'schtasks /Delete /TN "GoktunguKopru" /F'
  Pop $0

  ; -- 2) Servisi durdur (yukseltmede dosyalar kilitli olmasin) -------
  ; Bu adim dosya yaziminin HEMEN oncesinde: bagimlilik cozumu ve
  ; dosya cikartma sirasinda servis ayakta kalir, kesinti kisalir.
  DetailPrint "Servis durduruluyor (varsa)..."
  nsExec::ExecToLog 'net stop "${SERVIS_ADI}"'
  Pop $0

  ; Servis surecinin gercekten sonlanmasi icin kisa bekleme: SCM
  ; "durdu" dedikten sonra surec birkac yuz milisaniye daha dosya
  ; tutabilir ve dosya kopyalama "erisim engellendi" ile duser.
  Sleep 1500

  ; -- 3) Dosyalari yaz -----------------------------------------------
  DetailPrint "Program dosyalari yaziliyor..."
  SetOutPath "$INSTDIR"
  SetOverwrite on

  File "main.py"
  File "servis_win.py"
  File "SURUM"

  ; URUN kimlik dosyasi (Faz 5). Yalniz BRDTLM gibi bir profil
  ; secildiginde yazilir; servis (servis_win.py) ve tum alt servisler
  ; bunu okuyup GOKTUNGU_KOPRU_URUN degerini belirler. URUN_PROFIL
  ; tanimlanmamissa (BRDIMG) bu blok derlemeye HIC girmez -> setup.exe
  ; BYTE-AYNI kalir.
!ifdef URUN_PROFIL
  DetailPrint "Urun kimligi yaziliyor: ${URUN_PROFIL}"
  FileOpen $9 "$INSTDIR\URUN" w
  FileWrite $9 "${URUN_PROFIL}"
  FileClose $9
!endif

  ; YEREL AI cikarim iscisi (v1.7.20). AI servisi bunu gomulu Python
  ; ile 127.0.0.1 uzerinde alt surec olarak baslatir. Dosya yazilmazsa
  ; kurulum sorunsuz biter, panel acilir, AI servisi "calisiyor"
  ; gorunur - ama ayri AI bilgisayari olmayan sahada hicbir kamera
  ; izlenemez. Hata ancak operator izlemeyi baslattiginda gorulur.
  File "ai_sunucu.py"

  ; AI modelleri ISTEGE BAGLIDIR: `ai_sunucu.py` eksik modeli acilista
  ; resmi opencv_zoo deposundan kendisi indirir. Dizin kaynak agacinda
  ; VARSA pakete alinir (internetsiz saha kurulumu icin); yoksa
  ; `File /r` derleme hatasi vermesin diye kosula alinmistir.
!if /FileExists "ai_modeller\*.*"
  SetOutPath "$INSTDIR\ai_modeller"
  File /r "ai_modeller\*.*"
  SetOutPath "$INSTDIR"
!else
  !warning "ai_modeller\ yok: AI modelleri ilk calistirmada indirilecek."
!endif

  SetOutPath "$INSTDIR\kopru"
  File "kopru\*.py"

  ; M50 HVS SDK'sinin gomulu kopyasi (Hvs\*.py + bin\*.dll). `/r` ile
  ; alt dizinler DAHIL yazilmazsa m50_hvs.py "_sdk_kok()" SDK'yi
  ; bulamaz ve M50 servisi "Windows SDK bulunamadi" ile reddeder.
  SetOutPath "$INSTDIR\kopru\m50_sdk"
  File /r "kopru\m50_sdk\*.*"

  SetOutPath "$INSTDIR\web"
  File /r "web\*.*"

  SetOutPath "$INSTDIR\varliklar"
  File "varliklar\goktungu.ico"
  File "varliklar\favicon.ico"
  File "varliklar\favicon.png"
  File "varliklar\goktungu_kare.png"

  ; Gomulu Python calisma zamani (40 MB): Python 3.11.9 + websockets
  ; + pyserial + pywin32.
  DetailPrint "Python calisma zamani yaziliyor (40 MB)..."
  SetOutPath "$INSTDIR\python"
  File /r "gomulu\calisma\*.*"

  ; -- 3b) Modul cozumlemesini DOGRULA (KUSUR-ALTSERVIS-141) ----------
  ; Gomulu Python, yanindaki python311._pth dosyasi yuzunden
  ; "isolated" kipte kosar: PYTHONPATH ve calisma dizini YOK SAYILIR.
  ; Kurulum koku ._pth'e yazilmamissa bes alt servis de
  ;   ModuleNotFoundError: No module named 'kopru'
  ; ile aninda duser ve kullanici yalnizca "servis baslamadi" gorur.
  ; Bu yuzden dosyalar yazildiktan HEMEN SONRA gercek yorumlayiciyla
  ; olculur; hata kurulum kutusunda bildirilir, sahada aranmaz.
  DetailPrint "Python modul yollari dogrulaniyor..."
  nsExec::ExecToLog '"$INSTDIR\python\python.exe" -c "import kopru"'
  Pop $0
  ${If} $0 != 0
    DetailPrint "UYARI: 'kopru' paketi ice alinamadi (kod $0)"
    MessageBox MB_ICONEXCLAMATION|MB_OK \
      "Python calisma zamani dogrulamasi basarisiz (kod $0).$\r$\n$\r$\nAlt servisler (Dron/AI/Video/GroundGCC/Radar) baslatilamayabilir.$\r$\n$\r$\nDenetlenecek dosya:$\r$\n$INSTDIR\python\python311._pth$\r$\n$\r$\nBu dosya '..' satirini icermelidir."
  ${EndIf}

  ; -- 4) Veri dizini -------------------------------------------------
  ; Servis LocalSystem hesabiyla calisir; %APPDATA% System32 altina
  ; duser ve kullanici merkez kimligini goremez. ProgramData ortak
  ; alandir ve hem servis hem kullanici erisebilir.
  CreateDirectory "$APPDATA\..\..\ProgramData\Goktungu\Kopru"
  SetOutPath "$INSTDIR"

  ; -- 5) Servisi SCM'ye kaydet ---------------------------------------
  ${If} $YukseltmeMi == "0"
    DetailPrint "Windows servisi kaydediliyor..."
    ; --startup=delayed: Start=2 (Otomatik). Gecikmeli baslatma,
    ; acilista ag yigini hazir olmadan merkeze baglanmayi onler.
    nsExec::ExecToLog '"$INSTDIR\python\python.exe" "$INSTDIR\servis_win.py" --startup=delayed install'
    Pop $0
    ${If} $0 != 0
      DetailPrint "UYARI: servis kaydi cikis kodu $0"
      MessageBox MB_ICONEXCLAMATION|MB_OK \
        "Windows servisi kaydedilemedi (kod $0).$\r$\n$\r$\nKurulum tamamlandi ancak kopru otomatik baslamayacak. Yonetici olarak su komutu deneyin:$\r$\n$\r$\n$INSTDIR\python\python.exe $INSTDIR\servis_win.py --startup=delayed install"
    ${EndIf}

    ; Kurtarma politikasi: servis cokerse 5/10/30 sn gecikmelerle uc
    ; kez yeniden baslat. systemd Restart=on-failure karsiligi.
    nsExec::ExecToLog 'sc failure "${SERVIS_ADI}" reset= 86400 actions= restart/5000/restart/10000/restart/30000'
    Pop $0
  ${Else}
    ; Yukseltmede servis kaydi zaten var; yalniz sinif yolunu
    ; guncelle (kurulum dizini degismis olabilir).
    DetailPrint "Servis kaydi guncelleniyor..."
    nsExec::ExecToLog '"$INSTDIR\python\python.exe" "$INSTDIR\servis_win.py" --startup=delayed update'
    Pop $0
  ${EndIf}

  ; -- 6) Servisi baslat ----------------------------------------------
  DetailPrint "Servis baslatiliyor..."
  nsExec::ExecToLog 'net start "${SERVIS_ADI}"'
  Pop $0
  ${If} $0 != 0
    DetailPrint "UYARI: servis baslatma cikis kodu $0"
  ${EndIf}

  ; -- 7) Kisayollar --------------------------------------------------
  ; Kisayol PROGRAMI DEGIL paneli acar: servis zaten calisiyor,
  ; ikinci bir kopru ornegi tek-ornek kilidine takilir.
  DetailPrint "Kisayollar olusturuluyor..."
  CreateDirectory "$SMPROGRAMS\GOKTUNGU"
  CreateShortCut "$SMPROGRAMS\GOKTUNGU\${URUN_KISA} Paneli.lnk" \
    "$INSTDIR\panel_ac.bat" "" "$INSTDIR\varliklar\goktungu.ico" 0 SW_SHOWMINIMIZED \
    "" "GOKTUNGU Kopru yerel yonetim paneli"
  CreateShortCut "$SMPROGRAMS\GOKTUNGU\${URUN_KISA} Kaldir.lnk" \
    "$INSTDIR\uninstall.exe" "" "$INSTDIR\varliklar\goktungu.ico" 0

  ; -- 8) Program Ekle/Kaldir kaydi -----------------------------------
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

  ; Kurulum boyutunu Program Ekle/Kaldir listesinde goster.
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKLM "${KAYIT_ANAHTAR}" "EstimatedSize" "$0"

  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

; ---------------------------------------------------------------------
; PANEL ACICI
;
; Kisayol dogrudan URL acsa da olur, ancak servis henuz baslamamissa
; tarayici "baglanti kurulamadi" gosterir. Bu kucuk betik servisi
; denetler, gerekiyorsa baslatir ve sonra paneli acar.
; ---------------------------------------------------------------------
Section "-PanelAcici"
  SetOutPath "$INSTDIR"
  FileOpen $0 "$INSTDIR\panel_ac.bat" w
  FileWrite $0 "@echo off$\r$\n"
  FileWrite $0 "rem GOKTUNGU Kopru — yerel paneli acar.$\r$\n"
  FileWrite $0 "rem Servis calismiyorsa once baslatmayi dener; aksi halde$\r$\n"
  FileWrite $0 "rem tarayici bos sayfa gosterir ve kullanici kurulumun$\r$\n"
  FileWrite $0 "rem bozuk oldugunu sanir.$\r$\n"
  FileWrite $0 'sc query "${SERVIS_ADI}" | find "RUNNING" >nul 2>&1$\r$\n'
  FileWrite $0 "if errorlevel 1 ($\r$\n"
  FileWrite $0 '  net start "${SERVIS_ADI}" >nul 2>&1$\r$\n'
  FileWrite $0 "  timeout /t 3 /nobreak >nul 2>&1$\r$\n"
  FileWrite $0 ")$\r$\n"
  FileWrite $0 'start "" "${PANEL_URL}"$\r$\n'
  FileClose $0
SectionEnd

Function PaneliAc
  ExecShell "open" "${PANEL_URL}"
FunctionEnd

Function MasaustuKisayolu
  SetShellVarContext all
  CreateShortCut "$DESKTOP\${URUN_KISA}.lnk" \
    "$INSTDIR\panel_ac.bat" "" "$INSTDIR\varliklar\goktungu.ico" 0 SW_SHOWMINIMIZED \
    "" "GOKTUNGU Kopru yerel yonetim paneli"
FunctionEnd

; Masaustu kisayolu varsayilan olarak olusturulur; bitirme sayfasindaki
; kutu yalniz yeniden olusturmak icindir.
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
  Sleep 1500

  DetailPrint "Servis kaydi kaldiriliyor..."
  nsExec::ExecToLog '"$INSTDIR\python\python.exe" "$INSTDIR\servis_win.py" remove'
  Pop $0
  ; Python calismazsa servis kaydi kalmasin: sc ile de dene.
  nsExec::ExecToLog 'sc delete "${SERVIS_ADI}"'
  Pop $0

  ; v1.3.0 artiklari.
  nsExec::ExecToLog 'schtasks /Delete /TN "GOKTUNGU Kopru" /F'
  Pop $0

  DetailPrint "Kisayollar kaldiriliyor..."
  Delete "$SMPROGRAMS\GOKTUNGU\${URUN_KISA} Paneli.lnk"
  Delete "$SMPROGRAMS\GOKTUNGU\${URUN_KISA} Kaldir.lnk"
  RMDir  "$SMPROGRAMS\GOKTUNGU"
  Delete "$DESKTOP\${URUN_KISA}.lnk"

  DetailPrint "Program dosyalari kaldiriliyor..."
  ; pywin32 `install` sirasinda bu iki dosyayi Python kokune KOPYALAR;
  ; paket listesinde olmadiklari icin acikca silinmeleri gerekir,
  ; yoksa dizin bos kalmaz ve silinemez.
  Delete "$INSTDIR\python\pythonservice.exe"
  Delete "$INSTDIR\python\pywintypes311.dll"
  Delete "$INSTDIR\panel_ac.bat"
  Delete "$INSTDIR\main.py"
  Delete "$INSTDIR\ai_sunucu.py"
  Delete "$INSTDIR\servis_win.py"
  Delete "$INSTDIR\SURUM"
  ; URUN kimlik dosyasi (yalniz BRDTLM gibi profillerde vardir; yoksa
  ; Delete sessizce gecer). Silinmezse $INSTDIR bos kalmaz.
  Delete "$INSTDIR\URUN"
  Delete "$INSTDIR\uninstall.exe"
  RMDir /r "$INSTDIR\kopru"
  ; Modeller kurulum dizinindedir (salt okunur); silinmezse $INSTDIR
  ; bos kalmaz ve "RMDir $INSTDIR" sessizce basarisiz olur.
  RMDir /r "$INSTDIR\ai_modeller"
  RMDir /r "$INSTDIR\web"
  RMDir /r "$INSTDIR\varliklar"
  RMDir /r "$INSTDIR\python"
  RMDir /r "$INSTDIR\__pycache__"
  RMDir "$INSTDIR"
  RMDir "$PROGRAMFILES64\Goktungu"

  DeleteRegKey HKLM "${KAYIT_ANAHTAR}"
  DeleteRegKey HKLM "${AYAR_ANAHTAR}"

  ; AYARLAR VE MERKEZ KIMLIGI KORUNUR.
  ; Kullanici programi yeniden kurarsa merkez kaydini bastan yapmak
  ; zorunda kalmasin. Tam temizlik icin kullanici
  ; C:\ProgramData\Goktungu dizinini elle silebilir; bunu kurulum
  ; programinin kendi basina yapmasi VERI KAYBIDIR.
  DetailPrint "Ayarlar korundu: C:\ProgramData\Goktungu\Kopru"
SectionEnd
