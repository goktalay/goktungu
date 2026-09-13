# Gerçek Windows Servisi — Wine ile doğrulanan bulgular

## Servis kaydı gerçekten çalıştı

`wine python.exe servis_win.py install` komutu SCM'ye yazdı. Wine kayıt
defterinden okunan gerçek değerler:

| Anahtar | Değer | Anlamı |
|---|---|---|
| `DisplayName` | GOKTUNGU Kopru Yazilimi | `services.msc` listesinde görünecek ad |
| `Description` | GOKTUNGU saha köprü yazılımı... | Servis açıklaması |
| `ImagePath` | `python\pythonservice.exe` | SCM'nin başlattığı barındırıcı |
| `ObjectName` | `LocalSystem` | Servis hesabı — oturum gerekmez |
| `Type` | `0x10` (16) | `SERVICE_WIN32_OWN_PROCESS` — gerçek servis |
| `Start` | **`0x3` (3)** | **`SERVICE_DEMAND_START` — Elle başlatma** |
| `PreshutdownTimeout` | `0x2bf20` (180000 ms) | Kapanışta 3 dakika süre |
| `PythonClass\(Default)` | `servis_win.GoktunguKopruServisi` | Servis sınıfının yeri |

## Kusur 1: Başlangıç türü "Otomatik" değil

`Start = 3` demek **Elle (Manual)**. Kullanıcı bilgisayarı yeniden
başlattığında köprü **kendiliğinden başlamaz**. İstenen davranış
`Start = 2` (`SERVICE_AUTO_START`).

pywin32'nin varsayılanı `demand start`; `install` komutuna
`--startup=auto` verilmezse böyle kalır. Kurulum betiği bunu açıkça
belirtmek zorunda.

Ayrıca gecikmeli otomatik başlatma (`delayed auto start`) tercih
edilir: köprü ağ bağlantısına ihtiyaç duyar, açılışta ağ yığını hazır
olmadan başlarsa merkez bağlantısı ilk denemede başarısız olur.

## Kusur 2: `pythonservice.exe` kurulum dizinine kopyalanıyor

pywin32 `install` sırasında iki dosyayı Python kökü altına kopyaladı:

```
python\Lib\site-packages\win32\pythonservice.exe -> python\pythonservice.exe
python\Lib\site-packages\pywin32_system32\pywintypes311.dll -> python\pywintypes311.dll
```

Bu kopyalama `C:\Program Files` altında **yönetici hakkı** gerektirir.
Setup yönetici olarak çalıştığı için kurulumda sorun olmaz, ancak
kaldırma sırasında bu iki dosya paket listesinde olmadığı için
**artakalır**. Kaldırma betiği ikisini de açıkça silmelidir.

Alternatif olarak iki dosya setup içinde önceden doğru yere
yerleştirilebilir; böylece `install` kopyalama yapmaz.

## Kusur 3: Servis çalışma dizini belirsiz

`ImagePath` yalnızca `pythonservice.exe` yolunu içeriyor. `PythonClass`
değeri `Z:\tmp\svc_sinav\servis_win.GoktunguKopruServisi` biçiminde,
yani modül **dizin yoluyla** kaydedilmiş. Kurulum dizini taşınırsa
kayıt bozulur — ancak Program Files altına sabit kurulum yapıldığı
için bu kabul edilebilir.

Yine de `servis_win.py` içindeki `sys.path.insert` gereklidir: SCM
servisi başlattığında çalışma dizini `C:\Windows\System32` olur ve
`kopru` paketi bulunamaz. Bu koruma dosyada mevcut.

## Wine'ın sınayamadığı nokta

`sc query GoktunguKopru` boş döndü ve `sc start` denemesi anlamlı sonuç
vermez: Wine'da gerçek bir SCM süreç yöneticisi yok, kayıt defterine
yazma taklit ediliyor. **Servisin gerçekten başlayıp çalıştığı yalnız
gerçek Windows'ta doğrulanabilir.**

Wine'ın kanıtladığı şey: pywin32 servis modülleri gömülü Python ile
içe alınabiliyor, servis sınıfı geçerli, kayıt işlemi doğru anahtarları
yazıyor. Kalan risk servis çalışma zamanında.

## Kusur 1 çözüldü: `--startup=delayed`

```
wine python.exe servis_win.py --startup=delayed install
```

Sonuç: `Start = 0x2` (`SERVICE_AUTO_START`). Bilgisayar açılışında
servis kendiliğinden başlayacak.

`DelayedAutostart` değeri Wine'da yazılmadı ve şu uyarı çıktı:

> UserWarning: Delayed Start not available on this system

`win32serviceutil.py:250-260` okundu: pywin32 `ChangeServiceConfig2` ile
`SERVICE_CONFIG_DELAYED_AUTO_START_INFO` ayarlamaya çalışıyor,
`win32service.error` veya `NotImplementedError` yakalanınca uyarı verip
**geçiyor**. Yani:

- Wine `ChangeServiceConfig2`'nin bu bilgi sınıfını uygulamıyor → uyarı
- Gerçek Windows (Vista ve sonrası) uyguluyor → gecikmeli başlatma
  etkin olacak
- Her iki durumda da `Start = 2` yazıldı, yani **otomatik başlatma
  garanti**; gecikme yalnızca bir iyileştirme

Bu, uyarının kurulumda gösterilmemesi gerektiği anlamına da gelir:
kullanıcı `UserWarning` görürse kurulumun başarısız olduğunu sanır.
Kurulum betiği çıktıyı süzmelidir.

## Kusur 2 doğrulandı: kaldırmada artakalan dosyalar

`servis_win.py remove` çalıştı, kayıt defteri temizlendi
(`reg query` → anahtar bulunamadı). Ancak `install` sırasında
kopyalanan iki dosya **yerinde kaldı**:

```
python\pythonservice.exe      20992 bayt
python\pywintypes311.dll     134656 bayt
```

NSIS kaldırma bölümü bu ikisini açıkça silmek zorunda; aksi halde
`C:\Program Files\Goktungu` dizini kaldırma sonrası boş kalmaz ve
Windows dizini silemez.

## Kurtarma politikası

`sc failure GoktunguKopru reset= 86400 actions= restart/5000/restart/10000/restart/30000`

Wine'da çıktı vermedi (uygulanmıyor), ancak komut gerçek Windows'ta
servis çökerse 5 sn / 10 sn / 30 sn gecikmelerle üç kez yeniden
başlatma tanımlar. Kurulum betiğine eklenecek.

Bu, systemd tarafındaki `Restart=on-failure` + `RestartSec=5`
politikasının Windows karşılığıdır.

## Servis komut satırı özeti (kurulum betiği için)

| İşlem | Komut |
|---|---|
| Kaydet (otomatik başlangıç) | `python.exe servis_win.py --startup=delayed install` |
| Başlat | `python.exe servis_win.py start` |
| Durdur | `python.exe servis_win.py stop` |
| Kaldır | `python.exe servis_win.py remove` |
| Kurtarma | `sc failure GoktunguKopru reset= 86400 actions= restart/5000/...` |
