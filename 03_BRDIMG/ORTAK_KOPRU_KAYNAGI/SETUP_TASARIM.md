# GÖKTUNGU Köprü v1.4.0 — Gerçek Setup Programı

Kullanıcı talebi (2026-08-14):

> Senden konsol değil bildiğin kurulum setup programı oluşturmanı
> istemiştim, exe olarak. İkincisi servis olarak çalışmasını istemiştim.

v1.3.0'daki `kur.bat` bir konsol betiğiydi ve servis yerine Görev
Zamanlayıcı görevi kuruyordu. İkisi de talebe uymuyor.

## Karar: NSIS

| Seçenek | Durum |
|---|---|
| Inno Setup | Derleyicisi (`ISCC.exe`) yalnız Windows'ta çalışır; Wine 6.0.3'te güvenilir değil |
| **NSIS** | **`makensis` 3.08 bu makinede yerel olarak kurulu — Linux'ta doğrudan .exe derler** |

NSIS seçildi. Gerekçe: derleme Linux'ta yerel çalışır, çapraz derleme
için Wine gerekmez, `nsExec` ve `UserInfo` eklentileri servis kaydı ve
yönetici denetimi için hazır.

Mevcut NSIS eklentileri: `nsExec`, `UserInfo`, `nsDialogs`, `System`,
`StartMenu`, `Banner`, `LangDLL`.

## Gömülü Python çalışma zamanı

Setup kullanıcıdan Python kurmasını istemeyecek. Python 3.11.9 gömülü
dağıtımı (embeddable) setup içine giriyor.

| Bileşen | Sürüm | Kaynak |
|---|---|---|
| Python | 3.11.9 embed-amd64 | python.org |
| websockets | 12.0 | PyPI cp311 win_amd64 |
| pyserial | 3.5 | PyPI py2.py3 none any |
| **pywin32** | **306** | **PyPI cp311 win_amd64 — gerçek Windows servisi için** |

Toplam çalışma zamanı: **40 MB**.

Üretim betiği: `gomulu_hazirla.py` — sınav **15/0**.

### Kritik ayrıntı: `python311._pth`

Gömülü dağıtım varsayılan olarak `site` modülünü ve `site-packages`
dizinini **içe almaz**. `import site` satırı yorumdan çıkarılmadıkça ve
`Lib\site-packages` yolu eklenmedikçe `websockets` ve `pywin32` içe
alınamaz. `gomulu_hazirla.py` bu düzenlemeyi yapıyor.

`pywin32` ayrıca `pywin32.pth` üzerinden `win32`, `win32\lib` yollarını
ekler ve `pywin32_bootstrap` ile `pywin32_system32` DLL dizinini
`os.add_dll_directory()` çağrısıyla kaydeder. Bu zincir `import site`
etkin olmadan çalışmaz.

### Wine ile canlı doğrulama

Gömülü çalışma zamanı Wine 6.0.3 altında gerçekten çalıştırıldı:

| Sınav | Sonuç |
|---|---|
| `python.exe -c "import sys"` | PY 3.11.9 |
| `import websockets` | OK 12.0 |
| `import serial` | OK 3.5 |
| `import win32serviceutil, win32service, servicemanager` | **OK** |
| `import ssl` | OK OpenSSL 3.0.13 |

pywin32 servis modüllerinin Wine'da içe alınabilmesi önemli: gerçek
Windows servisi bu modüllere dayanıyor ve gömme zincirinin doğru
kurulduğunu kanıtlıyor.

## Hedef mimari

| Öğe | Windows | Ubuntu |
|---|---|---|
| Kurulum biçimi | `GOKTUNGU-Kopru-Setup-1.4.0.exe` (NSIS sihirbaz) | `goktungu-kopru_1.4.0_amd64.deb` |
| Kurulum yeri | `C:\Program Files\Goktungu\Kopru` | `/opt/goktungu/kopru` |
| Servis | Windows SCM servisi (pywin32), Otomatik başlangıç | systemd birimi |
| Servis adı | `GoktunguKopru` | `goktungu-kopru` |
| Ayarlar | `C:\ProgramData\Goktungu\Kopru` | `/var/lib/goktungu-kopru` |
| Kısayollar | Başlat menüsü + masaüstü, mavi GÖKTUNGU ikonu | Uygulama menüsü + masaüstü |
| Kaldırma | Program Ekle/Kaldır kaydı + `uninstall.exe` | `apt remove goktungu-kopru` |
| Yükseltme | Setup servisi durdurur, dosyaları değiştirir, başlatır | `dpkg` aynı akışı yürütür |

---

## Faz 3 — NSIS setup betiği yazıldı

`setup.nsi` (~330 satır). Derleme:

```bash
makensis -DSURUM=1.4.0 setup.nsi
# çıktı: dagitim/GOKTUNGU-Kopru-Setup-1.4.0.exe
```

### Sihirbaz sayfaları

Karşılama → Lisans (`dagitim/LISANS.txt`) → Dizin seçimi → Kurulum
ilerlemesi → Bitirme (paneli aç / masaüstü kısayolu kutuları).

`RequestExecutionLevel admin` → UAC yükseltme istemi. Program Files'a
yazmak ve SCM'ye servis kaydetmek için zorunlu.

### Ön denetimler (`.onInit`)

| Denetim | Gerekçe |
|---|---|
| `RunningX64` | Gömülü Python amd64 derlemesi; 32-bit'te çalışmaz |
| `AtLeastWin7` | Python 3.11 Windows 7 SP1 altını desteklemez |
| Kayıt defterinde mevcut kurulum | Varsa **yükseltme kipi**, dizin sabitlenir |

### Kurulum sırası (kesintiyi en aza indirir)

1. v1.3.0 Görev Zamanlayıcı görevini sil (`schtasks /Delete`)
2. Servisi durdur (`net stop`) + 1,5 sn bekle
3. Dosyaları yaz (kaynak + web + varlıklar + 40 MB Python)
4. `C:\ProgramData\Goktungu\Kopru` oluştur
5. Servisi kaydet (`--startup=delayed install`) + kurtarma politikası
6. Servisi başlat (`net start`)
7. Kısayollar (Başlat menüsü + masaüstü, `goktungu.ico`)
8. Program Ekle/Kaldır kaydı + `EstimatedSize`

### Kısayol tasarımı

Kısayollar programı **başlatmaz**, `panel_ac.bat` üzerinden paneli
tarayıcıda açar. Gerekçe: servis zaten çalışıyor; ikinci bir köprü
örneği tek-örnek kilidine takılır ve kullanıcı "program açılmıyor"
sanır. `panel_ac.bat` önce `sc query` ile servisi denetler, durmuşsa
başlatır, 3 sn bekler, sonra tarayıcıyı açar.

### Kaldırma

Servisi durdurur → `servis_win.py remove` → yedek olarak `sc delete` →
`schtasks` artığı → kısayollar → dosyalar (pywin32'nin kopyaladığı
`pythonservice.exe` ve `pywintypes311.dll` **açıkça**) → kayıt defteri.

**Ayarlar ve merkez kimliği korunur** (`C:\ProgramData\Goktungu`).
Kaldırmanın kimliği silmesi veri kaybıdır; kullanıcı yeniden kurarsa
merkez kaydını baştan yapmak zorunda kalmamalı.

## Veri dizini kusuru giderildi (`kopru/ayar.py`)

Servis `LocalSystem` hesabıyla çalıştığında `%APPDATA%` şuraya düşer:

```
C:\Windows\System32\config\systemprofile\AppData\Roaming
```

Sonuç: panelden (kullanıcı oturumu) yapılan merkez kaydı ile servisin
okuduğu kimlik **ayrı dosyalar** olurdu — kullanıcı "merkeze kaydettim
ama köprü hâlâ kayıtsız diyor" durumuna düşerdi.

Çözüm: Windows'ta `%PROGRAMDATA%\Goktungu\Kopru`. Geçiş kuralı: yeni yerde
`kimlik.json` yok ama `%APPDATA%` altında varsa eski dizin kullanılmaya
devam eder — v1.3.0 kullanıcısı yükseltmede merkez kaydını kaybetmez.

## Sürüm defteri

`kopru/surumler.py` → `KOPRU_SURUM = "1.4.0"`, geçmişe altı maddelik
v1.4.0 girdisi eklendi.
