# Ubuntu .deb kurulumu — gerçek ölçüm kaydı

Tarih: 2026-08-14
Makine: cloud-pc-2vz6isal (Ubuntu 22.04.5 LTS, systemd sistem servisi)
Paket: `goktungu-kopru_1.4.0_all.deb` (545 KB)

## Tasarım (Windows setup.exe ile eşlenik)

| Özellik | Windows (setup.exe) | Ubuntu (.deb) |
|---|---|---|
| Kurulum yeri | `C:\Program Files\Goktungu\Kopru` | `/opt/goktungu/kopru` |
| Servis | SCM servisi (LocalSystem) | systemd **sistem** servisi |
| Servis hesabı | LocalSystem | `goktungu-kopru` sistem kullanıcısı |
| Veri | `C:\ProgramData\Goktungu\Kopru` | `/var/lib/goktungu-kopru` |
| Başlat menüsü | `$SMPROGRAMS\GOKTUNGU` | `/usr/share/applications` |
| Masaüstü | `$DESKTOP` | her kullanıcının masaüstü |
| Kaldırma | Program Ekle/Kaldır | `apt remove` / `apt purge` |

**Kullanıcı servisi değil sistem servisi seçildi.** `kur.sh`
`systemctl --user` + `linger` kullanıyordu. .deb root olarak kurulur ve
hangi masaüstü kullanıcısının servisi isteyeceği kurulum anında
bilinemez. Sistem servisi makine açılışında kimse oturum açmadan
başlar — Windows'taki LocalSystem davranışının aynısı.

## ÖLÇÜLEN KUSUR: asgari Python sürümü servisi tamamen çökertiyordu

İlk gerçek kurulumda paket "kuruldu" göründü (`dpkg -l` → `ii`) ancak
servis **failed** durumundaydı ve panel yanıt vermiyordu.

Günlük:

```
GOKTUNGU KOPRU — PYTHON SURUMU YETERSIZ
 Gereken : Python 3.11 veya ustu
 Bulunan : Python 3.10.12  (/opt/goktungu/kopru/.venv/bin/python)
goktungu-kopru.service: Main process exited, code=exited, status=3
goktungu-kopru.service: Scheduled restart job, restart counter is at 10.
goktungu-kopru.service: Start request repeated too quickly.
```

**Kök neden:** `main.py` `ASGARI_PYTHON = (3, 11)` istiyordu, ancak
Ubuntu 22.04 LTS'nin varsayılan `python3`'ü **3.10.12**. `postinst`
sanal ortamı `python3` ile kuruyordu → servis her açılışta çıkıyor,
systemd 10 kez deneyip vazgeçiyor.

Bu kusur **yalnız gerçek kurulumla** görülebilirdi: `dpkg-deb` denetimi,
kabuk sözdizimi sınavı ve paket içerik denetimi hepsi geçmişti.

### Çözüm — iki katmanlı

**1) Asgari sürüm 3.10'a indirildi.** Önce 3.11 gerçekten gerekli mi
ölçüldü:

- Sözdizimi taraması (`ExceptionGroup`, `except*`, `TaskGroup`,
  `tomllib`, `StrEnum`, `Self`, `asyncio.timeout`) → **boş döndü**
- `python3.10 -m py_compile` tüm modüllerde → **hata yok**
- 3.10 sanal ortamında köprü uçtan uca çalıştırıldı → panel **HTTP 200**,
  günlük temiz

Yani 3.11 gereksinimi gerçek bir teknik zorunluluk değil, keyfi bir
alt sınırdı. Yamamak yerine sınır düzeltildi.

**2) `postinst`'e sürüm seçimi ve doğrulaması eklendi.** Artık `python3`
körlemesine kullanılmıyor: `python3.13 → 3.12 → 3.11 → 3.10 → python3`
sırasıyla en yeni **uygun** sürüm seçiliyor, uygun sürüm yoksa kurulum
anlaşılır hatayla duruyor. Yükseltmede mevcut `.venv`'in sürümü de
doğrulanıyor; uygunsuzsa yeniden kuruluyor.

## Düzeltme sonrası doğrulama (gerçek kurulum)

| Ölçüm | Sonuç |
|---|---|
| `dpkg -l goktungu-kopru` | `ii  1.4.0` |
| `systemctl is-enabled` | **enabled** |
| `systemctl is-active` | **active** |
| Panel `http://127.0.0.1:8790/` | **HTTP 200** |
| Sanal ortam sürümü | Python 3.10.12 |
| Servis süreç sahibi | `goktungu-kopru` (root DEĞİL) |
| `dialout` grubu | üye (seri telemetri hazır) |
| Veri dizini | `/var/lib/goktungu-kopru`, 750, sahibi servis kullanıcısı |
| Eski kimlik devri | `~/.config/goktungu-kopru` → devralındı |
| Menü girdisi | `/usr/share/applications/goktungu-kopru.desktop` |
| İkon | `hicolor` teması, 16–512 piksel |
| Yükseltme (reinstall) | servis durdu → dosyalar değişti → başladı |

Paket denetim sınavı: **13 geçti / 0 kaldı**

## Tasarım notları (gelecek oturumlar için)

- `conffiles` **yazılmıyor**: ayarlar `/etc` altında değil
  `/var/lib/goktungu-kopru` içinde. Yanlış `conffiles` kaydı `apt upgrade`
  sırasında kullanıcıya gereksiz çatışma sorusu sordurur.
- `postrm` `.venv` ve `__pycache__`'i **açıkça siliyor**: bunlar dpkg
  dosya listesinde yok (kurulum sonrası oluşur), silinmezse
  `/opt/goktungu/kopru` boş kalmaz ve dizin kaldırılamaz.
- `preinst` servisi durdurup **sürecin gerçekten çıkmasını bekliyor**
  (10 sn): çalışan süreç `.venv` dosyalarını kilitli tutar.
- systemd biriminde `StartLimitBurst`/`StartLimitIntervalSec`
  **`[Unit]` bölümünde**. `[Service]` altına yazılırsa systemd
  "Unknown key name" diyerek sessizce yok sayar.
- Servis `ProtectSystem=strict` + `ReadWritePaths=/var/lib/goktungu-kopru`
  ile çalışıyor: köprü yalnız kendi veri dizinine yazabilir.

## Kaldırma ve yeniden kurulum sınavı (gerçek ortam)

`sudo apt remove goktungu-kopru`:

| Ölçüm | Sonuç |
|---|---|
| Servis | inactive |
| systemd birim dosyası | silindi |
| `/opt/goktungu/kopru` | silindi (`.venv` dahil, artık yok) |
| Menü girdisi | silindi |
| İkonlar | silindi |
| `/var/lib/goktungu-kopru` | **korundu** (ayarlar + merkez kimliği) |
| Kullanıcıya bilgi | "Ayarlar korundu" + purge yönergesi yazdırıldı |

Yeniden kurulum:

| Ölçüm | Sonuç |
|---|---|
| Servis | active |
| Panel | HTTP 200 |
| `kimlik.json` | **korundu** — merkeze yeniden kayıt gerekmiyor |

Bu, yükseltme senaryosunun asıl önemli davranışı: kullanıcı yeni
paketi kurduğunda köprü merkezdeki kimliğini kaybetmiyor.
