# Kusur: `GOKTUNGU Kopru.vbs` satır 3 — "Sistem belirtilen yolu bulamıyor" (80070003)

**Bildiren:** kullanıcı, 14 Ağustos 2026
**Kurulum yolu:** `C:\Users\mkade\OneDrive\Masaüstü\goktungu-kopru-1.2.0\goktungu-kopru-1.2.0`
**Etki:** Kurulum tamamlanıyor, panel açılıyor (kur.bat sonunda `start
wscript.exe` çalışıyor), fakat **başlatıcı bozuk**. Bilgisayar yeniden
başlatıldığında oturum açılışındaki kopya da aynı hatayı verecek, yani
köprü otomatik başlamayacak.

## Kök neden — ölçümle doğrulandı

`kur.bat` başlatıcı dosyasını `echo` yönlendirmesiyle üretiyor ve kurulum
dizininin **tam yolunu VBS dosyasının içine gömüyor**:

```bat
chcp 65001 >nul 2>&1
...
>> "%BASLAT%" echo k.CurrentDirectory = "%KOK%"
```

Sorun bu iki satırın birleşiminde. `chcp 65001` konsolu UTF-8'e alır ve
`echo` çıkışı UTF-8 baytlarıyla dosyaya yazılır. `wscript.exe` ise
BOM'suz bir `.vbs` dosyasını **ANSI** (Türkçe Windows'ta kod sayfası
1254) varsayar. `ü` harfi UTF-8'de `C3 BC` iki baytken, 1254'te tek bayt
`FC`'dir. Sonuç: `Masaüstü` → `MasaÃ¼stÃ¼` benzeri bozuk bir dizeye
dönüşür ve VBS motoru satır 3'te var olmayan bir dizini arar.

Wine altında chcp 1254 ile aynı satır üretildiğinde bayt düzeyinde
ölçüldü — `ü` harfi tek bayt `fc` olarak yazıldı:

```
00000020  6c 63 75 6d 5c 74 72 5c  4d 61 73 61 fc 73 74 fc  |lcum\tr\Masa.st.|
```

Yani dosyanın kodlaması ile okuyucunun beklediği kodlama arasındaki
uyuşmazlık kesindir. Kullanıcının yolunda **üç** ayrı risk faktörü aynı
anda var:

| Faktör | Değer | Risk |
|---|---|---|
| Türkçe karakter | `Masaüstü` içindeki `ü` | Kodlama uyuşmazlığı |
| OneDrive | `OneDrive\Masaüstü` | Yol yeniden yönlenebilir |
| Boşluk | yok ama olabilir | Tırnak gerektirir |

**Not:** `chcp 65001`'in tek başına kaldırılması yeterli değil.
Kullanıcının bilgisayarındaki konsol kod sayfası ne olursa olsun,
üretilen dosya ile onu okuyan motorun aynı kodlamada buluşması
garanti edilmelidir. Ayrıca dizin **yeniden adlandırılırsa veya
taşınırsa** gömülü yol yine bozulur.

## Doğru çözüm

Yolu VBS dosyasının içine **hiç gömmemek**. VBS kendi konumunu
`WScript.ScriptFullName` ile öğrenebilir:

```vbs
Set f = CreateObject("Scripting.FileSystemObject")
kok = f.GetParentFolderName(WScript.ScriptFullName)
```

Bu yaklaşımda üretilen dosya **saf ASCII** olur; Türkçe karakter,
boşluk, OneDrive yeniden yönlendirmesi ve dizin taşıma sorunlarının
hiçbiri dosyayı etkilemez.

Tek istisna: Başlangıç klasörüne konan **kopya**. O dosya farklı bir
dizinde durduğu için kendi konumunu kullanamaz. Onun için ayrı bir
çözüm gerekir — kurulum dizinini ASCII olmayan karakterlerden bağımsız
biçimde saklamak (kayıt defteri veya `%LOCALAPPDATA%` altında UTF-8
yapılandırma dosyası) ya da başlangıç için `.lnk` kısayolu kullanmak.
`.lnk` dosyaları yolu **Unicode** olarak saklar, dolayısıyla kodlama
sorunu yaşamaz.

## Wine ortamı hakkında not

Wine 6.0.3'te `chcp 65001` sonrası `cmd.exe` tümüyle susuyor: sonraki
`echo` komutları hiç çıktı üretmiyor ve yönlendirilen dosya 0 bayt
kalıyor. `chcp 1254` ve `chcp 437` ile aynı betik sorunsuz çalışıyor.
Bu bir Wine sınırıdır, gerçek Windows davranışı değildir — ancak
ölçüm için chcp 1254 kullanılarak bayt düzeyinde doğrulama yapılabildi.

## Düzeltme ve karşılaştırmalı kanıt (Wine, ölçülmüş)

Düzeltmenin gerçekten işe yaradığını göstermek için iki yöntem aynı
ortamda yan yana koşuldu. Ölçüt, VBS'in çıkış kodudur: `1` sanal ortamı
bulamadığı, `0` bulduğu anlamına gelir.

| Yöntem | Çıkış kodu | Yorum |
|---|---|---|
| Eski (bozulmuş UTF-8 yol gömülü) | **1** | Sanal ortam bulunamadı — kusur yeniden üretildi |
| Yeni (`ScriptFullName` ile kendi konumu) | **0** | Her şey bulundu |

Ek olarak, yeni başlatıcı **klasör yeniden adlandırıldıktan sonra** da
çalıştı. Dizin `goktungu-kopru-1.2.1` → `Göktungu Köprü Yeni Yer` olarak
değiştirildi ve başlatıcı hâlâ doğru dizini buldu. Gömülü yol
kullanılırken bu senaryo kaçınılmaz olarak bozulurdu.

`sinav_baslatici.sh` sonucu: **10 geçti / 0 kaldı**. Sınav, üretilen
dosyanın saf ASCII olduğunu, Türkçe dizin adını içermediğini,
`ScriptFullName` kullandığını, eksik dosya durumunda anlaşılır ileti
verdiğini ve gizli kipin (`, 0, False`) korunduğunu bayt düzeyinde
doğrular.

### Yapılan değişiklikler

| Dosya | Değişiklik | Gerekçe |
|---|---|---|
| `kur.bat` | `chcp 65001` kaldırıldı | Kodlama uyuşmazlığının kaynağı |
| `kur.bat` | Başlatıcıya yol gömülmüyor; `ScriptFullName` | Türkçe karakter, boşluk, taşıma, OneDrive'a bağışıklık |
| `kur.bat` | Başlatıcıya dosya varlık denetimi + `MsgBox` | Sessiz başarısızlık yerine anlaşılır ileti |
| `kur.bat` | Başlangıç klasörüne `.vbs` kopyası yerine `.lnk` | `.lnk` yolu Unicode saklar |
| `kur.bat` | Eski bozuk `.vbs` kopyası temizleniyor | Yükseltmede artık kalmasın |
| `kur.bat` | PowerShell'e yollar ortam değişkeniyle geçiliyor | Komut satırında gömülü dize boşluk/tırnakta bozulur |
| `kur.bat` | Üretilen başlatıcının ASCII olduğu doğrulanıyor | Kusur sessizce oluşuyordu; kurulumda görünür olsun |
| `kaldir.bat` | `chcp 65001` kaldırıldı | Aynı tuzak |
| `kaldir.bat` | Hem `.vbs` hem `.lnk` başlangıç kaydı siliniyor | Eski kurulumdan yükseltme |

### Wine ortamı hakkında iki not

`wscript.exe` Wine altında hata iletisini konsola yazmıyor ve bozuk bir
`CurrentDirectory` atamasında bile çıkış kodu `0` döndürüyor. Bu yüzden
ölçüm, VBS içine bilinçli `WScript.Quit` çağrıları koyularak yapıldı;
"pencere açıldı mı" gibi dolaylı ölçütlere güvenilmedi.

Wine 6.0.3, `chcp 65001` çağrısından sonra `cmd.exe`'yi tümüyle
susturuyor: sonraki `echo` komutları hiç çıktı üretmiyor ve
yönlendirilen dosya 0 bayt kalıyor. `chcp 1254` ve `chcp 437` ile aynı
betik sorunsuz çalışıyor. Bu bir Wine sınırıdır. Yan etkisi şu: eski
`kur.bat` Wine altında hiç sınanamıyordu, yeni sürüm `chcp`
kullanmadığı için sınanabiliyor.
