# Wine sınırı: 32-bit NSIS installer bu makinede çalışmıyor

## Bulgu

`makensis` varsayılan olarak **PE32 (32-bit)** installer üretir:

```
$ file dagitim/GOKTUNGU-Kopru-Setup-1.4.0.exe
PE32 executable (GUI) Intel 80386 ... for MS Windows
```

Wine bu makinede 64-bit-only prefix (`#arch=win64`) ve **wine32 paketi
kurulu değil** (AGENTS.md'de kayıtlı). Sonuç:

```
$ WINEDEBUG=+loaddll wine /tmp/on_denetim2.exe /S; echo $?
00e8:err:process:exec_process L"Z:\\tmp\\on_denetim2.exe"
    not supported on this system
cikis: 123
```

**Çıkış kodu 123, hiçbir kod çalışmadı.** Sessiz kurulum "başarılı"
görünüyordu (`/S` ile çıkış 0) çünkü kabuk boru hattı çıkışı yutuyordu;
gerçek çıkış kodu 123.

## Yanlış hipotezler (elenen)

Sırayla denendi, hiçbiri neden değildi:

| Hipotez | Sınav | Sonuç |
|---|---|---|
| `RequestExecutionLevel admin` UAC'ta düşüyor | `user` ile yeniden derle | Aynı hata |
| `${RunningX64}` Wine'da yanlış | Ayrı denetim exe'si | Kod hiç çalışmadı |
| `${AtLeastWin7}` başarısız | Aynı | Kod hiç çalışmadı |
| Sanal ekran yok (`DISPLAY`) | Xvfb :96 ile | Aynı hata |

Kök neden ancak `WINEDEBUG=+loaddll` ile görüldü. **Sessiz çıkış kodunu
denetlemeden "kurulum çalışmadı" demek yetersizdi.**

## Karar: iki yol

### Yol A — wine32 kur (reddedildi)

`sudo dpkg --add-architecture i386 && apt install wine32` gerekir.
Bu makine kalıcı VM ve AGENTS.md'de "sistem düzeyi değişiklikler
kaydedilmeli" kuralı var. 32-bit çoklu mimari eklemek sistem genelinde
paket ağacını değiştirir; yalnız test için ağır bir bedel.

### Yol B — 64-bit NSIS hedefi (seçildi)

NSIS 3.08 `-DNSIS_CONFIG_AMD64` ile 64-bit installer üretebilir mi
diye denetlenecek. Üretilebiliyorsa hem Wine'da sınanabilir hem de
gerçek Windows'ta 64-bit installer çalışır (zaten `RunningX64`
zorunluluğu var, 32-bit desteklemeye gerek yok).

Üretemiyorsa: Windows kurulumu bu makinede **çalıştırılarak
sınanamaz**; yalnız kod denetimi + kullanıcının gerçek makine testi
kalır. Bu durumda `nsis` betiğinin doğruluğu statik denetimle
güvenceye alınır ve kullanıcıya net bir sınama yönergesi verilir.

---

## Yol B denendi: `Target amd64-unicode`

NSIS 3.08 amd64 stub'ları mevcut (`/usr/share/nsis/Stubs/*-amd64-unicode`)
ve `Target amd64-unicode` yönergesi kabul edildi. Üretilen dosya doğru
mimaride:

```
/tmp/t64.exe: PE32+ executable (GUI) x86-64 ... for MS Windows
```

Ancak Wine yine reddetti:

```
err:module:map_image_into_view Could not map section .reloc,
    file probably truncated
err:process:exec_process not supported on this system
cikis: 123
```

### Kök neden ölçüldü

PE bölüm tablosu ayrıştırıldı. **amd64 stub'ının kaynağı sağlam**,
sorun NSIS'in veri eklerken bölüm tablosunu güncellememesi:

| Dosya | `.reloc` raw_ofs | raw_boy | Gerekli dosya boyutu | Gerçek boyut | Durum |
|---|---|---|---|---|---|
| Stub (kaynak) | 81408 | 512 | 81920 | 81920 | TAMAM |
| `t64.exe` (üretilen) | 82432 | 512 | **82944** | **81966** | **EKSİK 978 bayt** |

Yani `makensis` amd64 hedefinde installer verisini eklerken `.reloc`
bölümünün dosya sonuna taşmasına yol açıyor — üretilen PE **geçersiz**.
Bu Debian'ın NSIS 3.08 paketinde bilinen bir amd64 hedefi kusuru.

32-bit çıktıda (`GOKTUNGU-Kopru-Setup-1.4.0.exe`) tüm bölümler tamam;
yani **32-bit installer sağlam**, yalnız Wine onu wine32 olmadan
çalıştıramıyor.

## Nihai karar

**Dağıtım hedefi 32-bit kalır** (`GOKTUNGU-Kopru-Setup-1.4.0.exe`,
PE32, 16,6 MB). Gerekçeler:

1. 32-bit NSIS installer, 64-bit Windows'ta sorunsuz çalışır — sektör
   standardı budur (Chrome, VS Code, Git for Windows hepsi 32-bit
   installer kullanır, 64-bit yükü kurar).
2. Üretilen PE geçerli; kusur yalnız amd64 hedefinde.
3. `${RunningX64}` denetimi 32-bit installer içinden de doğru çalışır
   ve 64-bit Program Files yolunu (`$PROGRAMFILES64`) verir.

**Bedel:** kurulum bu makinede çalıştırılarak sınanamaz. wine32 kurmak
sistem genelinde i386 çoklu mimari eklemeyi gerektirir; kalıcı VM'de
yalnız test için bu değişikliği yapmıyorum.

**Telafi:** kurulum mantığı statik denetimle güvenceye alınır
(`sinav_setup_nsi.py`), kullanıcıya net bir gerçek-makine sınama
yönergesi verilir.
