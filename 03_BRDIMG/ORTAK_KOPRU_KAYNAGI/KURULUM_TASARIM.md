# GÖKTUNGU Köprü — Kurulum Paketleri Tasarımı (v1.3.0)

Kullanıcı talebi (2026-08-14):

1. Windows: `C:\Program Files\Goktungu\` altına kurulum
2. Uygulama **Windows servisi** olarak kaydedilecek
3. **Başlat menüsü + masaüstü** kısayolu (yerel web paneline)
4. **Yerinde yükseltme:** yeni setup, yeni kurulum yapmak yerine
   servisi durdur → dosyaları güncelle → servisi başlat
5. Windows ve Ubuntu paketleri **AYRI** dağıtılacak
6. Setup dosyasının ve kısayolların ikonu **GÖKTUNGU mavi ikonu**
7. Ubuntu'da da uygulama menüsü (Başlat karşılığı) + masaüstü kısayolu

## Üretilen ikon varlıkları (Faz 2 — TAMAM)

Betik: `~/goktungu_kopru/ikon_uret.sh`
Kaynak: `~/goktungu_244/goktungu/logo.png` (590x640, mavi kare, alfa kanallı)

| Çıktı | Ayrıntı |
|---|---|
| `varliklar/goktungu.ico` | 7 dilim: 16,24,32,48,64,128,256 — 159 KB |
| `varliklar/hicolor/{16..512}/apps/goktungu-kopru.png` | 9 boyut |
| `varliklar/favicon.ico`, `favicon.png` | panel sekmesi |
| `varliklar/goktungu_kare.png` | 640x640 şeffaf dolgulu kare |

Kaynak kare olmadığı için (590x640) doğrudan ölçekleme ikonu ezerdi;
`-gravity center -extent 640x640` ile şeffaf dolgu eklenip kareye
tamamlandı. Çok boyutlu .ico şart: tek boyut Explorer'da bulanıklaşır.

## Mevcut durum (v1.2.1)

| Dosya | Satır | Durum |
|---|---|---|
| `kur.bat` | 226 | Kullanıcı dizinine kurar, VBS + .lnk, servis YOK |
| `kaldir.bat` | 90 | .lnk ve VBS temizliği var |
| `kur.sh` | 214 | venv + systemd --user, `.desktop` YOK, `/opt` YOK |
| `kaldir.sh` | 65 | systemd --user kaldırma |
| `paketle.py` | 313 | TEK paket üretir (`platform='ortak'`) |

### v1.2.1'de düzeltilen kusur (referans)

`chcp 65001` + `echo` ile üretilen VBS, wscript tarafından ANSI (cp1254)
sanılıyordu; `Masaüstü` yolundaki `ü` bozulup **80070003** veriyordu.
Çözüm: kod sayfası değiştirilmiyor, VBS'e yol gömülmüyor
(`WScript.ScriptFullName`), başlangıç için `.lnk` kullanılıyor.

## Yeni mimari kararlar

### Windows servisi — "Session 0" sorunu ve çözümü

Eski `kur.bat` yorumu servis kurmamayı savunuyordu: servisler Session 0
içinde çalışır, masaüstüne erişemez, tarayıcı açamaz. Kullanıcı yine de
servis istedi ve **haklı** — köprü bir arka plan telemetri aktarıcısıdır,
kullanıcı oturum açmasa da çalışmalıdır (sahada bilgisayar başında kimse
olmayabilir).

Doğru ayrım:

| Bileşen | Nerede çalışır |
|---|---|
| Köprü süreci (telemetri, servis yönetimi) | **Windows servisi**, Session 0, `--tarayici-yok` |
| Yerel panel | Kullanıcının tarayıcısı, `http://127.0.0.1:8790/` |
| Kısayollar | Paneli tarayıcıda açar (`.url`/`.lnk` → tarayıcı) |

Yani kısayol artık programı BAŞLATMAZ, servis zaten çalışıyor; kısayol
yalnızca paneli açar. Bu, "program ikonu yok" ve "sürekli cmd açılıp
kapanıyor" şikâyetlerinin kökünü de kurutur.

### Servis yöneticisi seçimi

Windows'ta Python betiğini servis yapmanın yolları:

| Yol | Değerlendirme |
|---|---|
| `pywin32` + `win32serviceutil` | Ek bağımlılık (~10 MB), pip gerektirir, 32/64 uyumu kırılgan |
| NSSM (harici exe) | Güvenilir ama üçüncü taraf ikili dağıtmak gerekir |
| `sc.exe create` + `pythonw.exe` | Python betiği doğrudan SCM ile konuşmadığı için servis "başlatılamadı" der |
| **`sc.exe` + kabuk sarmalayıcı (`srvany` benzeri)** | Windows 10+'ta yok |
| **Görev Zamanlayıcı (`schtasks`), ONSTART tetikleyicisi** | Yönetici hakkı ile sistem başlangıcında çalışır, SCM sözleşmesi gerektirmez, oturum gerekmez |

Seçim: **Görev Zamanlayıcı, `/RU SYSTEM` + `/SC ONSTART`**. Kullanıcının
istediği davranışı (bilgisayar açıldığında oturum olmadan başlaması,
durdurulup başlatılabilmesi) ek bağımlılık olmadan sağlar. Panelde
"servis" olarak görünür ve `schtasks /End`, `/Run` ile yönetilir.

`sc.exe` ile gerçek servis kurmak `pywin32` gerektirir ve kurulum
sırasında pip'in internete erişmesine bağımlı olur; sahada internetsiz
kurulumda başarısız olur. Görev Zamanlayıcı Windows'un kendi parçasıdır.

### Yerinde yükseltme

Her iki platformda kurulum betiği şu sırayı izler:

1. Mevcut kurulumu **algıla** (dizin + servis/görev kaydı var mı)
2. Varsa: servisi **durdur**, `ayar.json` ve kimlik dosyalarını **koru**
3. Program dosyalarını **değiştir** (venv korunur, bağımlılık
   sürümü değiştiyse güncellenir)
4. Servisi **başlat**, sürümü doğrula

Kritik: kullanıcı verisi program dizininde DEĞİL. Windows'ta
`%ProgramData%\Goktungu\Kopru\`, Linux'ta `/var/lib/goktungu-kopru/` veya
`~/.config/goktungu-kopru`. Program Files altına yazmak yönetici hakkı
gerektirir ve her yükseltmede silinir.

### Paket ayrımı

`paketle.py` iki arşiv üretecek:

| Paket | İçerik |
|---|---|
| `goktungu-kopru-<s>-windows.zip` | ortak çekirdek + `kur.bat`, `kaldir.bat`, `varliklar/goktungu.ico` |
| `goktungu-kopru-<s>-linux.tar.gz` | ortak çekirdek + `kur.sh`, `kaldir.sh`, `varliklar/hicolor/` |

Windows için `.zip`: Windows'ta `.tar.gz` açmak için üçüncü taraf araç
gerekiyordu (Windows 11 tar.exe var ama sağ tık menüsünde yok).
Kullanıcı arşivi çift tıklayıp `kur.bat`'ı çalıştırabilmeli.

## Veri dizini — doğrulandı (kod okundu)

`kopru/ayar.py::veri_dizini()` zaten doğru davranıyor ve program
dizininden ayrı:

| Platform | Dizin |
|---|---|
| Windows | `%APPDATA%\goktungu-kopru` |
| Linux | `$XDG_CONFIG_HOME/goktungu-kopru` ya da `~/.config/goktungu-kopru` |
| Geçersiz kılma | `GOKTUNGU_KOPRU_VERI` ortam değişkeni |

Bu, yerinde yükseltmeyi kolaylaştırır: program dizini tamamen
silinip yeniden yazılabilir, kimlik ve ayarlar etkilenmez.

**ANCAK Windows servisi için kritik bir sorun var.** Servis
`/RU SYSTEM` ile çalışırsa `%APPDATA%`
`C:\Windows\System32\config\systemprofile\AppData\Roaming` olur.
Kullanıcı panele girip "bu bilgisayarı merkeze kaydet" dediğinde kimlik
oraya yazılır — teknik olarak çalışır ama:

- Kullanıcı kimlik dosyasını göremez/yedekleyemez
- Servis hesabı değişirse (SYSTEM → kullanıcı) kimlik kaybolur
- Kaldırma betiği bu dizini temizlemeyi unutursa artık kalır

Bu yüzden Windows kurulumunda servis **`GOKTUNGU_KOPRU_VERI` ortam
değişkeni ile** `C:\ProgramData\Goktungu\Kopru\veri` dizinine
yönlendirilecek. `ProgramData` tam bu amaç için vardır: makine geneli,
kullanıcıdan bağımsız uygulama verisi. Böylece:

- Servis hesabı ne olursa olsun aynı dizin kullanılır
- Kullanıcı dizini görebilir ve yedekleyebilir
- Yükseltmede dokunulmaz, kaldırmada açıkça sorulur

Linux'ta systemd **--user** servisi kullanıldığı için `~/.config`
zaten doğru; sistem servisine geçilmeyecek (kimlik dosyası ve seri port
yetkisi gerekçeleri `kur.sh` başında zaten belgelenmiş).

---

## İLERLEME KAYDI

### Faz 4 — Windows kurulumu (kur.bat, kaldir.bat) TAMAM

`kur.bat` tamamen yeniden yazıldı (eski: 226 satır kullanıcı dizinine
kurulum, servis yok):

| Adım | Uygulama |
|---|---|
| 0 | `net session` ile yönetici yetkisi denetimi (yoksa açık yönlendirme) |
| 1 | Python 3.11+ arama (`py -3.13/3.12/3.11`, sonra PATH `python` **sürüm denetimli**) |
| 2 | Mevcut kurulum algılama → `YUKSELTME=1`, eski/yeni sürüm gösterimi |
| 3 | Yükseltmede `schtasks /End` + `Goktungu` süzgeçli `pythonw` kapatma |
| 4 | `xcopy` ile `%ProgramFiles%\Goktungu\Kopru`; `.venv`/`__pycache__`/`.pyc` hariç |
| 5 | venv: yükseltmede **korunur**, yalnız bağımlılıklar tazelenir |
| 6 | `schtasks /Create /SC ONSTART /RU SYSTEM /RL HIGHEST` + `servis.cmd` sarmalayıcı |
| 7 | Kısayollar: Başlat menüsü `GOKTUNGU\` (Panel, Başlat, Durdur) + masaüstü, `goktungu.ico` |
| 8 | Program Ekle/Kaldır kaydı (`HKLM\...\Uninstall\GoktunguKopru`) |
| 9 | Panel 8790 TCP yoklaması (10 deneme) — "kuruldu" demek yetmez, **doğrulanır** |

Kritik kararlar:

- **Görev Zamanlayıcı, `sc.exe` değil.** Python betiği SCM ile
  konuşmadığı için `sc create` kaydı hata 1053 ("servis zamanında yanıt
  vermedi") verir. Gerçek servis `pywin32` gerektirir → pip → internet →
  sahada internetsiz kurulum başarısız. `schtasks` Windows'un kendi
  parçası, `/SC ONSTART /RU SYSTEM` ile oturum açılmadan da başlar.
- **`servis.cmd` sarmalayıcı zorunlu:** `schtasks` komut satırında ortam
  değişkeni atayamaz; `GOKTUNGU_KOPRU_VERI=C:\ProgramData\Goktungu\Kopru\veri`
  burada ayarlanıyor. Aksi halde SYSTEM hesabının `%APPDATA%`'sı
  `C:\Windows\System32\config\systemprofile\...` olur ve kullanıcı
  kimlik dosyasını göremez/yedekleyemez.
- **Kısayol paneli açar, programı başlatmaz.** Servis zaten çalışıyor;
  eski davranışta çift tıklayan kullanıcı ikinci örnek açıp port
  çatışması yaratıyordu. `TargetPath` = panel URL'si, `IconLocation` =
  `goktungu.ico`.
- `chcp 65001` **hiç kullanılmıyor** (v1.2.1 kusurunun kökü).

`kaldir.bat` yeniden yazıldı: görev kaydı silme, Başlat menüsü klasörü,
tüm-kullanıcılar masaüstü, kayıt defteri girdisi, **eski sürüm
artıkları** (Startup'taki `.vbs`/`.lnk`), veri dizini için soru.
`ELDEN` kipi: betik program dizininin içinden çalıştırılırsa kendini
`%TEMP%`'e kopyalayıp silmeyi oradan tamamlar.

### Faz 5 — Ubuntu kurulumu (kur.sh) TAMAM

`kur.sh` yeniden yazıldı (eski: 214 satır, `$HOME`'da çalışır, `.desktop`
yok):

| Adım | Uygulama |
|---|---|
| 0 | Root ile çalıştırma **reddi** (systemd --user birimi root'a yazılırdı) |
| 1 | Python 3.11+ arama, dağıtıma göre kurulum komutu önerisi |
| 2 | Mevcut kurulum algılama, eski/yeni sürüm |
| 3 | `systemctl --user stop` |
| 4 | `rsync -a --delete` (yoksa `cp`) ile `/opt/goktungu/kopru`, `root:root` |
| 5 | venv korunur, bağımlılıklar tazelenir |
| 6 | `dialout` grubu — `sudo -n` ile denenir, olmazsa komut söylenir |
| 7 | systemd `--user` birimi + `linger` |
| 8 | `hicolor` ikon kurulumu + `.desktop` (menü) + masaüstü kopyası |
| 9 | Servis durumu doğrulaması |

Kritik kararlar:

- **`/opt`, FHS 3.0 standardı.** `$HOME` altında program dosyası tutmak,
  kullanıcı klasörü taşındığında veya ikinci kullanıcı köprüyü
  çalıştırmak istediğinde kurulumu bozuyordu.
- **systemd `--user` korunuyor** (sistem servisine geçilmedi): kimlik
  dosyası `~/.config/goktungu-kopru`, seri port kullanıcı yetkisi. `linger`
  ile sistem servisinin tek gerçek üstünlüğü (oturumsuz yaşam) karşılanır.
- **`.desktop` `Type=Application` + `xdg-open`**, `Type=Link` değil:
  Link girdileri GNOME uygulama ızgarasında **aranamaz**, bazı
  ortamlarda hiç görünmez.
- **Masaüstü dizini yerelleşiktir** (`Masaüstü`/`Desktop`):
  `xdg-user-dir DESKTOP` ile bulunuyor, iki bilinen ad yedek.
- **`gio set ... metadata::trusted true`**: GNOME 42+ masaüstündeki
  `.desktop` dosyasını güvenilir işaretlenmeden çalıştırmaz,
  "Güvenilmeyen uygulama başlatıcısı" der.
- `Name=GÖKTUNGU Köprü` (Türkçe), `Name[en]=GOKTUNGU Bridge`.

### Sırada

- `kaldir.sh` yeni yapıya göre güncellenecek (`/opt`, `.desktop`, ikon)
- `paketle.py` iki ayrı paket üretecek: `-windows.zip`, `-linux.tar.gz`
- `surumler.py` → v1.3.0
- Wine ve yerel systemd ile sınama (Faz 6)

### Faz 5 devamı — kaldir.sh, paketle.py, surumler.py TAMAM

- `kaldir.sh` yeniden yazıldı: root reddi, servis + `reset-failed`, `.desktop`
  (menü + masaüstü), hicolor ikon temizliği, `/opt` silme, veri dizini
  `--hepsi` olmadan korunur, eski `$HOME` kurulumu bildirilir.
- `surumler.py` → **KOPRU_SURUM = "1.3.0"**, 8 maddelik değişiklik kaydı.
- `paketle.py` platforma göre iki paket üretiyor. `_Arsiv` sarmalayıcı ile
  zip ve tar.gz **aynı** doğrulama kodundan geçiyor (iki ayrı doğrulama
  işlevi yazmak, birinde düzeltilen kusurun ötekinde kalmasına yol açar).

**Üretilen paketler (sınav: 68 geçti / 0 kaldı):**

| Platform | Dosya | Boyut | SHA256 |
|---|---|---|---|
| windows | `goktungu-kopru-1.3.0-windows.zip` | 188.148 B | `87ac9d1c6e3a77ec92b509c3c4dbced4d8813f008e7a6a29061e964fd9ce251a` |
| linux | `goktungu-kopru-1.3.0-linux.tar.gz` | 533.043 B | `1a799cfa9ae90e51fba6370fa542e5c5354c20349d261eb3643626c27405a5b7` |

Windows paketi neden küçük: `.ico` tek dosya (16-256 çok boyutlu), Linux
paketi 9 ayrı PNG taşıyor.

Sınav kapsamı (her paket için): kök dizin sarımı, 9 yasak desen, **öteki
platformun betiği yok**, 22 zorunlu ortak dosya, 5 servis modülü, ikon
varlığı, çalışır kip (Linux), SURUM defter eşleşmesi, `ayar.py` sürüm
kaynağı, `main.py` sürüm denetim sırası, platforma özgü kurulum
davranışları (Program Files/`/opt`, servis kaydı, kısayol, ikon,
yükseltme, yetki denetimi), geliştirme yolu kaçağı.

Not: `chcp` sınavı ilk turda kaldı — `REM NEDEN chcp YOK` açıklaması ham
metinde yakalanıyordu. Sınav REM satırlarını dışlayacak şekilde
düzeltildi; belgeyi silmeye zorlayan bir sınav yanlış teşviktir.

### Faz 6 — sınama planı

1. **Linux kurulumu gerçek systemd ile:** bu VM'de `systemctl --user`
   çalışıyor ve `Linger=yes` (AGENTS.md'de belgeli). `kur.sh` doğrudan
   çalıştırılacak, sonra `kaldir.sh`.
2. **Windows kurulumu Wine ile:** `~/goktungu_win_test/` altyapısı var
   (Xvfb :95, xdotool, imagemagick — AGENTS.md). Wine'ın `schtasks`
   desteği sınırlı olabilir; o durumda kur.bat'in adım adım nereye
   kadar geldiği ölçülecek ve Wine sınırı ile gerçek kusur ayırt
   edilecek.
3. **Yükseltme sınaması:** aynı kurulum iki kez çalıştırılıp ikinci
   turda "YUKSELTME kipi" ve veri korunumu doğrulanacak.

## Faz 6 — Linux kurulumu GERÇEK systemd ile sınandı

Ortam: bu VM, `systemctl --user` çalışıyor, `Linger=yes` (AGENTS.md).

### İlk kurulum — geçti

| Ölçüm | Sonuç |
|---|---|
| Kurulum dizini | `/opt/goktungu/kopru` (root:root) |
| Servis | `active` + `enabled` |
| Panel | `HTTP 200`, `<title>GÖKTUNGU Köprü</title>` |
| Menü girdisi | `/usr/share/applications/goktungu-kopru.desktop` |
| İkonlar | 9 boyut hicolor temasında |
| SURUM | `1.3.0` |
| Linger | zaten etkin, korundu |

`.desktop` içeriği doğrulandı: `Exec=xdg-open http://127.0.0.1:8790/`,
`Icon=goktungu-kopru`, TR/EN adlar, `Terminal=false`.

### Sınamada bulunan İKİ GERÇEK KUSUR — giderildi

**Kusur A — `StartLimitIntervalSec` yanlış bölümde.**
Birim dosyasında `[Service]` altına yazılmıştı. systemd bu iki anahtarı
**yalnız `[Unit]` bölümünde** tanır; `[Service]` altında
`Unknown key name ... ignoring` diyerek **sessizce yok sayıyordu**.

Ölçüm kanıtı:
```
systemd-analyze verify ...goktungu-kopru.service
  → :19: Unknown key name 'StartLimitIntervalSec' in section 'Service', ignoring.
```
Etki: çökme döngüsü sınırlanmamış kalır — köprü sürekli yeniden başlar,
günlük şişer, kimse farketmez. `[Unit]` bölümüne taşındı; doğrulamada
artık uyarı yok.

**Kusur B — yükseltmede 62 saniye telemetri kesintisi.**
İlk sırada servis, `pip install` adımından **önce** durduruluyordu.
Ölçülen gerçek kesinti:
```
10:39:28 Stopping → 10:40:30 Started   = 62 saniye
```
Bir uçuş sürerken yükseltme yapılırsa o dakikanın telemetrisi kaybolur.

Sıra düzeltildi: ağdan indirme gerektiren uzun hazırlıklar (venv, pip)
**servis ayakta** yapılıyor; servis yalnız dosyaların yer değiştirdiği
kısa pencerede duruyor. Bu güvenlidir çünkü `.venv` hedef dizinin
içindedir ve pip çalışan sürecin içe aktardığı `kopru/`, `web/`
dosyalarına dokunmaz.

Yeni ölçüm:
```
10:44:27 Stopping → 10:44:29 Started   = 2 saniye
```
**62 sn → 2 sn (31 kat).**

### Yükseltme kipi — geçti

| Ölçüm | Sonuç |
|---|---|
| Kip algılama | `Kurulu surum: 1.3.0 / Yeni surum: 1.3.0` → YUKSELTME |
| Kimlik korunumu | `kimlik.json` içeriği aynı kaldı |
| Sanal ortam | mtime değişmedi (yeniden kurulmadı) |
| Servis | yükseltme sonrası `active`, panel `HTTP 200` |
| Çıkış kodu | 0 |

Not: sınav sırasında görülen `Kurulum kimliği geçersiz` uyarısı kusur
değildir — sınav için elle yazılan yapay `kimlik.json` merkezde kayıtlı
olmadığı için merkez onu haklı olarak reddediyor. Köprünün yeniden
bağlanma döngüsü de doğru çalışıyor (3→6→12 sn geri çekilme).

Paket yeniden üretildi: **35 geçti / 0 kaldı** (linux).

### Kaldırma sınavı — bir kusur daha bulundu ve giderildi

`kaldir.sh` gerçek ortamda çalıştırıldı. Servis, birim dosyası, menü
girdisi ve `/opt/goktungu/kopru` doğru silindi; veri dizini korundu; eski
`$HOME` kurulumu bilgi olarak bildirildi. **Ancak** denetim 1 artakalan
dosya gösterdi:

```
kaldirma sonrasi: /usr/share/icons/hicolor/22x22/apps/goktungu-kopru.png
```

**Kusur C — kaldırma betiği ikon boyutlarını elle listeliyordu.**
`kaldir.sh` içinde `for b in 16 24 32 48 64 128 256 512` sabit listesi
vardı; `kur.sh` ise `varliklar/hicolor/` altındaki **tüm** dizinleri
kopyalıyordu. İkon setinde 22x22 de bulunduğu için kurulum 9 dosya
kurdu, kaldırma 8'ini sildi.

Aynı bilgiyi iki yerde ayrı tutmak, biri güncellenince ötekinin sessizce
eskimesine yol açar. Liste tümüyle kaldırıldı; kaldırma artık diski
tarıyor (`ls /usr/share/icons/hicolor/*/apps/goktungu-kopru.png`).

Doğrulama (kur → kaldır çevrimi yeniden):
```
kurulan ikon   : 9
silinen ikon   : 9
ARTAKALAN ikon : 0
```

### Linux tarafı durumu: TAMAM

| Sınav | Sonuç |
|---|---|
| İlk kurulum | geçti |
| Yükseltme kipi (veri + venv korunumu) | geçti |
| Kesinti süresi | 2 sn |
| systemd birim doğrulaması | uyarı yok |
| Kaldırma (artık bırakmadan) | geçti |
| Paket sınavı | 35 geçti / 0 kaldı |

Sonraki: Windows kurulumunu Wine ile sına (`~/goktungu_win_test/`
altyapısı: Xvfb :95, xdotool, imagemagick — AGENTS.md).
Wine'ın `sc.exe` / `schtasks` desteği sınırlı olabilir; o durumda
kur.bat'in hangi adıma kadar geldiği ölçülecek ve **Wine sınırı** ile
**gerçek kusur** ayırt edilecek.

## Windows tarafı — Wine sınırı ve kod denetimi

### Wine ile sınanamıyor (ölçüldü, 2026-08-14)

Wine 6.0.3'te kurulumun iki kritik adımı **karşılıksız**:

| Komut | Çıkış kodu | Gerçek sonuç |
|---|---|---|
| `powershell -Command ...` | 0 | `powershell.exe` **dosya olarak yok**; hiçbir şey olmuyor |
| `schtasks /Create ...` | 0 | `/Query` **boş** dönüyor; görev oluşmuyor |

Tehlikeli olan, ikisinin de **sıfır** dönmesi. Wine'da koşan bir kurulum
sınavı "kısayol oluşturuldu, servis kaydedildi" diye rapor eder ve
gerçekte hiçbiri olmamıştır. Bu ortamda yapılan bir Windows kurulum
sınavı **yanlış güven** üretir; bu yüzden yapılmadı.

`AGENTS.md`'deki 2026-08-04 notu ("Windows'a özgü kusurlar için kaynak
denetimi yetmez") hâlâ geçerli, ancak o not **derlenmiş exe'nin pencere
davranışı** içindi ve Wine o iş için çalışıyor. Kurulum betiği farklı:
bağımlılığı Windows'un kendi yönetim araçları ve bunlar Wine'da yok.

Gerçek Windows sınaması kullanıcıya bırakıldı.

### Kod düzeyi denetim: `sinav_windows_kurulum.py` — 42/0

Wine'ın kapsayamadığı yerlerde yapılabilecek denetimler yazıldı: yol
tutarlılığı, alıntılama, ortam değişkeni geçişi, kurulum↔kaldırma
eşleşmesi, adım sırası.

**Sınavın kendisinde bir kusur bulundu ve giderildi.** İlk çalıştırmada
üç denetim "kaldı" dedi; üçü de yanlış alarmdı: sınav ham metinde arama
yaptığı için `REM` açıklama satırlarını çalışan komut sanıyordu.
27. satırdaki `REM - schtasks /End ile durdurulabilir` açıklaması,
"pip servis durdurmadan önce mi çalışıyor" denetiminde gerçek durdurma
komutu sayıldı. Sınav artık `REM` satırlarını ayıklıyor; açıklamanın
*varlığını* denetleyen maddeler ham metne bakıyor.

Bu tuzak `paketle.py` sınavlarında da bir kez yaşandı — aynı hata iki
ayrı yerde tekrarlandı, not olarak bırakılıyor.

### Windows'ta giderilen kesinti kusuru

Linux'ta ölçülen 62 saniyelik yükseltme kesintisinin aynısı Windows
betiğinde de vardı: servis durduruluyor, sonra `pip install`
çalıştırılıyordu. Sıra değiştirildi — venv ve pip servis **ayakta**
yapılıyor, servis yalnız dosyaların yer değiştirdiği kısa pencerede
duruyor. Sanal ortam hedef dizinin içinde olduğu için bu güvenli:
pip yalnız `.venv` altına yazar, çalışan sürecin içe aktardığı
`kopru\` ve `web\` dosyalarına dokunmaz.

### Kurulum davranışı özeti (her iki platform)

| Konu | Windows | Ubuntu |
|---|---|---|
| Kurulum dizini | `C:\Program Files\Goktungu\Kopru` | `/opt/goktungu/kopru` |
| Veri dizini | `C:\ProgramData\Goktungu\Kopru\veri` | `~/.goktungu-kopru` |
| Servis | Görev Zamanlayıcı, `/SC ONSTART /RU SYSTEM` | systemd `--user`, `Linger` |
| Başlat menüsü | `Başlat > GOKTUNGU` (3 kısayol) | uygulama menüsü `.desktop` |
| Masaüstü | `GOKTUNGU Kopru.lnk` | `GOKTUNGU Kopru.desktop` |
| İkon | `varliklar/goktungu.ico` (9 boyut) | `hicolor` 9 boyut PNG |
| Kaldırma | Ayarlar > Uygulamalar / `kaldir.bat` | `kaldir.sh` |
| Yükseltme | servis durdur → dosya → başlat | aynı |
| Kesinti | yalnız dosya kopyalama | 2 sn (ölçüldü) |

### Neden Görev Zamanlayıcı, `sc.exe` servisi değil

Python betiği Windows Servis Denetim Yöneticisi ile konuşmaz;
`sc.exe create` ile kaydedilen bir kayıt SCM'nin beklediği "başladım"
bildirimini alamadığı için 30 saniye sonra **hata 1053** ile düşer.
Gerçek servis için `pywin32` gerekir — pip ile inen ~10 MB'lik ek
bağımlılık, sahada internetsiz kurulumu bozar. Görev Zamanlayıcı
Windows'un kendi parçası, ek bağımlılık istemez ve istenen davranışı
tam sağlar: `/SC ONSTART` (oturum açılmasa da açılışta başlar),
`/RU SYSTEM`, `/End` ve `/Run` ile durdurulup başlatılabilir.
