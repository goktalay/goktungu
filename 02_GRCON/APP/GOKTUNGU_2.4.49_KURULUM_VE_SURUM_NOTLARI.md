# GÖKTUNGU GCS v2.4.49 — Kurulum ve Sürüm Notları

**Sürüm:** 2.4.49
**Önceki sürüm:** 2.4.48
**Konu:** GCS'in Linux makinede systemd servisi olarak çalışması, açılışta kendiliğinden başlaması, iki ekranda tam ekran açılması ve servisin arayüzden yönetilmesi

---

## 1. Bu sürümün konusu

Bu sürüm dört isteğe birlikte cevap veriyor. İstekler ayrı görünse de tek bir zincir oluşturuyor: program **servis olarak** çalışacak, servis **açılışta** başlayacak, başladığında **iki ekranda** kendiliğinden görünecek ve kullanıcı bilgisayara hiç dokunmadan hem **servisi** hem **makineyi** arayüzden yönetebilecek.

| İstek | Nasıl karşılandı |
|---|---|
| Linux makinede servis olarak çalışsın | `goktungu.service` systemd birimi + `servis_kur.sh` |
| Bilgisayar açıldığında otomatik açılsın | `systemctl enable goktungu` + kiosk `autostart` girdisi |
| Üst ekranda `index.html`, ikinci ekranda `flight.html`, Chrome ile tam ekran | `kiosk_baslat.sh` (iki pencere, `--start-fullscreen`) |
| Program Ayarları'nda servisi durdur/başlat bölümü | `js/servis_panel.js` + dört WebSocket komutu |
| Kullanıcı menüsünde "Bilgisayarı Kapat" (onay sorarak) | Profil menüsü girdileri + `makine_kapat` komutu |

Bu zincirin ilk halkası göründüğünden çok daha kritik çıktı: **program SIGTERM sinyalini düzgün karşılamadığı için servis olarak çalışmaya hazır değildi.** Onu düzeltmeden diğer hiçbir madde güvenilir biçimde çalışamazdı.

---

## 2. Kapatılan temel kusur: SIGTERM ile düzgün kapanma

`systemctl stop goktungu` komutu sürece **SIGTERM** gönderir. Python'da bu sinyalin varsayılan davranışı süreci **anında öldürmektir**. Önceki sürümlerde `main.py` yalnızca `KeyboardInterrupt` (Ctrl+C) yakalıyordu, dolayısıyla SITL temizliğini yapan blok SIGTERM yolunda **hiç çalışmıyordu**.

Sonuç zinciri şöyleydi:

> `arducopter` süreçleri yetim kalır → tuttukları portlar bloke olur → servisin bir sonraki başlatması "port dolu" hatasıyla düşer.

Yani servis her `restart` işleminde bir öncekinin artığı yüzünden bozuluyordu. Bu, servis kurulumunu anlamsız kılan türden bir kusurdur.

### İlk çözüm denemesi yetmedi

Akla gelen ilk çözüm, SIGTERM'i yakalayıp `KeyboardInterrupt`'a çevirmekti. Uygulandı ve **işe yaramadı**: konsola "SIGTERM alindi" yazılıyor, ancak süreç kapanmıyordu. Nedeni tahmin etmek yerine çalışan sürecin canlı yığın izi alındı:

```
_cancel_all_tasks (asyncio/runners.py:205)   <-- BLOKE
close (asyncio/runners.py:70)
run (asyncio/runners.py:193)
```

Ölçüm kök nedeni açıkça gösterdi: `asyncio.run()` çıkarken bekleyen tüm görevleri iptal edip **bitmelerini bekler**. WebSocket sunucusu iptali tamamlamadığı için süreç sonsuza kadar bekliyordu. systemd bu durumda `TimeoutStopSec` boyunca (varsayılan 90 saniye) bekler, sonra **SIGKILL** atar — ve SIGKILL yolunda temizlik **zaten yapılamaz**. Yani kusur ortadan kalkmıyor, yalnızca 90 saniye gecikiyordu.

### Uygulanan çözüm

Temizlik `main()` içindeki `finally` bloğundan çıkarılıp bağımsız bir işleve (`_kapanis_temizligi`) taşındı. Sinyal işleyicisi bu işlevi **kendisi** çağırıyor, ardından `os._exit(0)` ile çıkıyor. `os._exit` normalde tehlikelidir çünkü temizliği atlar; burada güvenlidir çünkü temizlik hemen öncesinde elle yapılıyor.

| Ölçüm | Önce | Sonra |
|---|---|---|
| SIGTERM sonrası kapanma süresi | sonsuz (SIGKILL bekliyor) | **0,26 sn** |
| SITL süreçleri | yetim kalıyor | temizleniyor |
| Bayat port kaydı | kalıyor | siliniyor |

Aynı işleyici `SIGHUP` sinyalini de yakalar; bu, terminal oturumu kapandığında programın arkada yarım kalmasını önler.

**Windows kullanıcısı için:** Bu düzeltme Windows'ta da işe yarar. Program artık pencere kapatma ve görev sonlandırma yollarında da SITL süreçlerini temizliyor; "port dolu" hatasının nedeni buydu.

---

## 3. Kesin port kaydı: `veri/calisma.json`

Kiosk pencerelerinin doğru adrese bağlanması için portun **bilinmesi** gerekir. HTTP portu `8000, 8080, 8888, 9000, 5500` listesinden sırayla denenir ve ilk boş olan alınır. Yani 8000 meşgulse sunucu sessizce 8080'e düşer.

Kiosk betiği portu 8000 diye **tahmin etseydi** boş sayfa açardı — ve kullanıcı bunu haklı olarak "servis çalışmıyor" diye yorumlardı. Bu yüzden sunucu gerçekte aldığı portu diske yazıyor, kiosk betiği oradan **okuyor**:

```json
{
  "surum": "2.4.49",
  "pid": 262888,
  "baslangic": 1786435272.14,
  "http_port": 8080,
  "ws_port": 8766,
  "kesin": true
}
```

`kesin: true` alanı değerin tahmin değil ölçüm olduğunu belirtir. Bu davranış temiz kurulum üzerinde doğrulandı: 8000 ve 8765 meşgulken sunucu 8080/8766'ya düştü, dosyaya doğru yazdı ve HTTP `200` döndü. Dosya kapanışta silinir, böylece bayat bir kayıt kimseyi yanlış adrese göndermez.

Windows'ta da aynı dosya yazılır; hangi porta bağlanacağınızı `veri\calisma.json` içindeki `http_port` alanından okuyabilirsiniz.

---

## 4. Servis yönetimi arka ucu ve ölçülen bir yanlış tasarım

Yeni `goktungu/servis.py` modülü (449 satır) systemd birimini yönetir: başlat, durdur, yeniden başlat, açılışta başlatmayı aç/kapat, journal günlüğünü oku, makineyi kapat veya yeniden başlat.

En kritik karar **yetki ölçümünde** alındı. İlk tasarım `systemctl --dry-run` kullanıyordu. Bu tasarım, Cloud Computer üzerinde sudo yetkisi **olmayan** bir kullanıcı oluşturularak sınandı ve çöktü:

| Yöntem | Yetkili kullanıcı | Yetkisiz kullanıcı | Ayırt ediyor mu |
|---|---|---|---|
| `systemctl --dry-run poweroff` | 0 | **0** | Hayır |
| `pkcheck --process $$` | 2 | 2 | Hayır |
| `sudo -n -l /sbin/poweroff` | 0 | **1** | **Evet** |

`--dry-run` yalnızca komutun **biçimini** doğrular, polkit'e hiç sormaz. Bu tasarımla devam edilseydi yetkisiz kullanıcıda düğmeler **etkin görünür**, kullanıcı basar ve **hiçbir şey olmazdı** — hata mesajı bile çıkmadan. Yetki ölçümü bu nedenle `sudo -n -l` temeline geçirildi. Yetki yoksa düğme pasif görünür ve nedeni yazılır.

> Düğmenin etkin görünüp hiçbir şey yapmaması, pasif görünüp nedenini söylemesinden her zaman daha kötüdür.

---

## 5. İzin sistemindeki güvenlik açığı

Servis komutları eklenirken `goktungu/pilot.py` içindeki izin denetimi incelendi. `izin_var()` işlevinin son satırı şudur:

```python
return bool(...get(grup, {}).get(izin, True))
```

Varsayılan değer `True`. Yani **tanımsız bir izin serbest sayılır.** Bu, yeni komutları yalnızca izin haritasına yazmanın onları **her role açacağı** anlamına geliyordu. Uçuş sırasında normal bir pilot servisi durdurabilir ya da bilgisayarı kapatabilirdi.

Bu nedenle dört komutun tamamında **ayrıca açık rol denetimi** yapılıyor:

```python
p = self._pilot_bilgi(websocket) or {}
if p.get("rol") != "yonetici":
    # reddet
```

Arayüz tarafında da aynı kısıt uygulanır: makine güç düğmeleri yalnızca `rol == "yonetici"` olduğunda görünür ve çıkış yapıldığında gizlenir. Sunucu tarafı denetimi asıl güvencedir; arayüz denetimi yalnızca kullanıcıyı yanlış beklentiden korur.

---

## 6. Kendini durdurma tuzağı

Servisin kendisini durdurması özel bir sorun doğurur: süreç öldüğünde WebSocket bağlantısı kopar ve **yanıt istemciye hiç ulaşmaz**. Arayüz bunu "bağlantı hatası" olarak gösterir, kullanıcı da işlemin başarısız olduğunu sanır — oysa işlem tam olarak istendiği gibi çalışmıştır.

Çözüm sıralamayı tersine çevirmektir: `durdur` ve `yeniden` eylemlerinde yanıt **önce** gönderilir (`beklemede: true` işaretiyle), eylem **1 saniye sonra** uygulanır. Arayüz bu işareti gördüğünde kopmayı beklenen sayar ve yeniden başlatmada kendiliğinden yeniden bağlanır.

Bu davranış gerçek systemd üzerinde ölçüldü. Journal kaydı süreç kimliği zincirini açıkça gösteriyor:

```
360441 → 360947 → 360995
```

Her geçişte "SIGTERM alindi" ve "Kapandi" satırları göründü, yani yeniden başlatmalar düzgün kapanış üzerinden gerçekleşti.

---

## 7. systemd birimindeki üç bilinçli karar

Birim dosyası (`goktungu.service.sablon`) üç noktada varsayılan alışkanlıktan **bilinçli olarak** ayrılıyor.

**`Restart=on-failure`, `always` değil.** `always` ile kalıcı bir yapılandırma hatası sonsuz döngü üretir: süreç düşer, yeniden başlar, aynı hatayla düşer. Journal şişer ve gerçek hata kayıtların arasında kaybolur. `StartLimitIntervalSec=300` ve `StartLimitBurst=5` ile 5 dakikada 5 denemeden fazlası engellenir.

**`KillMode=mixed`, `control-group` değil.** `control-group` SIGTERM'i tüm sürece grubuna aynı anda gönderir; bu durumda SITL süreçleri ana süreçle **eşzamanlı** sinyal alır ve programın düzenli temizliği yarıda kalır. `mixed` ile SIGTERM yalnızca ana sürece gider, o kendi temizliğini yapar; SIGKILL gerekirse tüm gruba gider.

**`User=` var, root yok.** Servis root olarak çalışırsa `veri/` altındaki dosyaların sahipliği root'a geçer ve kullanıcı programı elle başlattığında "izin yok" hatası alır. GCS'in root yetkisine ihtiyacı yoktur.

Ayrıca `WorkingDirectory=@KOK@` **zorunludur**: `main.py` göreli yollar kullanır (`veri/`, `js/`, `css/`, `sitl/`). Bu satır olmadan servis `/` dizininde başlar ve hiçbir dosyayı bulamaz. Bu, systemd kurulumlarında en sık yapılan hatadır.

---

## 8. Yetkilendirme üç biçimde birlikte yazılıyor

`servis_kur.sh` yetkiyi üç ayrı biçimde tanımlar. Bu fazlalık değil, **taşınabilirlik gereğidir**:

| Dosya | Ne için | Neden gerekli |
|---|---|---|
| `/etc/sudoers.d/goktungu-servis` | Birincil yol, en dar kapsam | Yalnızca gerekli `systemctl` ve güç komutlarına izin verir |
| `/etc/polkit-1/rules.d/49-goktungu.rules` | polkit 0.106+ (JavaScript) | Modern dağıtımlar bu biçimi okur |
| `/etc/polkit-1/localauthority/50-local.d/49-goktungu.pkla` | polkit 0.105 (eski biçim) | Bu sürümde `rules.d` dizini **hiç yok**; JS kuralı sessizce etkisiz kalır |

Son satır varsayım değil ölçümdür: doğrulama makinesinde polkit **0.105** bulundu. Yalnızca modern biçim yazılsaydı yetkilendirme o makinede hiçbir uyarı vermeden çalışmayacaktı.

Sudoers dosyası yazıldıktan sonra `visudo -c` ile **doğrulanır**. Bozuk bir sudoers dosyası sistemdeki **tüm** `sudo` erişimini kırar; bu yüzden doğrulama başarısız olursa dosya silinir.

Verilen yetki genel root erişimi **değildir**; yalnızca `goktungu` biriminin yönetimi ve makine kapatma/yeniden başlatma komutlarını kapsar.

---

## 9. İki ekran kiosk düzeni

`kiosk_baslat.sh` iki Chrome penceresi açar: birinci ekranda `index.html` (ana arayüz), ikinci ekranda `flight.html` (uçuş duvarı).

**`--start-fullscreen` kullanılıyor, `--kiosk` kullanılmıyor.** Bu, "tam ekrandan kastım arayüzdeki tam ekran düğmesine basmak" isteğinin doğrudan karşılığıdır: sekme ve adres çubuğu görünür kalır, yalnızca pencere tam ekran açılır. JavaScript ile tam ekran çağrısı yapmak burada işe yaramaz; tarayıcılar kullanıcı hareketi olmadan gelen tam ekran isteklerini **sessizce reddeder**.

**Her pencere ayrı `--user-data-dir` kullanır.** Aynı profille ikinci pencere açmak Chrome'da yeni bir **sekme** oluşturur, ayrı pencere değil — ve `--window-position` yok sayılır, iki ekran düzeni bozulur.

**Ekran konumu `xrandr` ile ölçülür.** Pencereyi ikinci ekrana taşımak için ekran **adı** değil **koordinatı** gerekir; `--window-position` bu koordinatı alır.

Kullanım:

```bash
bash kiosk_baslat.sh            # iki ekran
bash kiosk_baslat.sh --tek      # yalnız ana arayüz
bash kiosk_baslat.sh --durdur   # açık kiosk pencerelerini kapat
```

Windows'ta bu betik çalışmaz. İki ekran düzeni için iki Chrome penceresi açıp (`/` ve `/flight`), her birini kendi ekranına taşıyıp `F11` ile tam ekran yapabilirsiniz.

---

## 10. Arayüzdeki yeni bölümler

**Program Ayarları → Servis bölümü:** durum rozeti (aktif/durdu/kurulmadı, kip, PID), beş düğme (başlat, durdur, yeniden başlat, açılışta başlatmayı aç/kapat) ve journal günlük kutusu. Uçan dron varken durdurma isteği **ayrıca** uyarı gösterir.

**Kullanıcı menüsü → Bilgisayarı Kapat / Yeniden Başlat:** her ikisi de onay sorar ve yalnızca yönetici rolünde görünür. Bu sayede kullanıcı bilgisayarın kendisine fiziksel olarak erişmek zorunda kalmaz.

CSS önekleri için `svc-` seçildi. `sv-` öneki (`\.sv-rozet` gibi) **zaten** AI arama seviyesi rozetleri için kullanılıyordu; aynı adı kullanmak iki bileşenin görünümünü birbirine karıştıracaktı.

Çeviri dengesi korundu: **37 yeni anahtar**, Türkçe ve İngilizce taraflara eşit eklendi (1375 → **1412 = 1412**). Dengesizlik olsaydı dil değiştirildiğinde ilgili metinler kaybolurdu.

Windows'ta systemd bulunmadığı için servis düğmeleri "desteklenmiyor" durumunda **pasif** görünür; makine kapatma ise çalışır.

---

## 11. Kurulum

### Linux (yama)

```bash
tar xzf goktungu-guncelleme-2.4.49.tar.gz
cd goktungu-guncelleme-2.4.49
bash kur_2449.sh /kurulum/dizininiz
```

### Windows (yama)

```powershell
tar -xzf goktungu-guncelleme-2.4.49.tar.gz
cd goktungu-guncelleme-2.4.49
powershell -ExecutionPolicy Bypass -File .\kur_2449.ps1 -Hedef "C:\goktungu"
```

Her iki betik de önce **yedek alır**, sonra kopyalar, sonra yamanın gerçekten uygulandığını doğrular. Doğrulama başarısız olursa yedeği geri yükleme komutunu yazar. Veritabanı, harita önbelleği ve ayarlar **korunur**.

> **Kurulumdan sonra tarayıcıda `Ctrl+Shift+R` yapmak zorunludur.** Önbellek etiketi `v2449`'a taşındı; sert yenileme yapılmazsa tarayıcı eski JavaScript dosyalarını kullanmaya devam eder.

### Servis kurulumu (Linux, isteğe bağlı)

```bash
cd /kurulum/dizininiz
sudo bash servis_kur.sh
```

Betik birimi yazar, açılışta başlatmayı etkinleştirir, yetkileri üç biçimde tanımlar ve kiosk otomatik başlatma girdisini kurar. Kaldırmak için `sudo bash servis_kur.sh --kaldir`.

> **Servisi kurmadan önce programı bir kez elle başlatın:** `python3 main.py`
>
> Nedeni ölçülmüş bir davranıştır: eksik bir Python paketi varsa servis `failed` değil **`activating` durumunda takılı** kalır ve gerçek neden görünmez. Elle başlatmak eksik paketi anında gösterir.

Servis kurulduktan sonra durumu şöyle izlersiniz:

```bash
systemctl status goktungu
journalctl -u goktungu -n 50
```

---

## 12. Ölçüm tablosu

Aşağıdaki sonuçlar temiz bir v2.4.48 kurulumuna yama uygulandıktan sonra alındı.

| Sınav | Kapsam | Sonuç |
|---|---|---|
| `sinav_2449_servis.py` | Servis modülü API sözleşmesi, SIGTERM, WS komutları ve rol denetimi, arayüz eşleşmesi, i18n dengesi, systemd birimi, kiosk düzeni | **121 / 0** |
| `sinav_2448_platform.py` | İşletim sistemi × mimari matrisi (gerileme) | 119 / 0 |
| `sinav_2447_mimari.py` | aarch64 ikili seçimi (gerileme) | 72 / 0 |
| `sinav_2446_sitl.py` | İzin, biçim, mimari, süreç (gerileme) | 52 / 0 |
| `sinav_2445_arayuz.py` | Statik bütünlük (gerileme) | 134 / 0 |
| **Toplam** | | **498 / 0** |

Gerçek systemd üzerinde yapılan canlı ölçümler (doğrulama makinesi, Ubuntu 22.04, systemd 249, polkit 0.105):

| Deneme | Kapsam | Sonuç |
|---|---|---|
| `dene_servis_ws.py` | Okuma komutları: durum, günlük | **15 / 0** |
| `dene_servis_eylem.py` | Eylem komutları: durdur, yeniden başlat, PID değişimi | **12 / 0** |

Canlı davranış ölçümleri:

| Ölçüm | Sonuç |
|---|---|
| Yama doğrulaması | 14/14 dosya, `v2448` kalıntısı 0 |
| HTTP yanıtı | 200 |
| Port düşüşü | 8000 meşgul → 8080/8766, `calisma.json`'a doğru yazıldı |
| SIGTERM kapanması | 0,26 sn, SITL temizlendi, port kaydı silindi |
| Servis yeniden başlatma | PID zinciri 360441 → 360947 → 360995 |

Eylem sınavı ilk koşumda `3/6` kaldı. Kök neden koda değil **sınav betiğine** aitti: betik giriş isteğini `{"komut": "giris"}` alanıyla gönderiyordu, oysa sözleşme `{"tip": "giris"}` bekliyor. Giriş hiç yapılamadığı için tüm eylem komutları reddediliyordu. Bu, ölçüm aracının kendisinin de doğrulanması gerektiğini gösteren iyi bir örnektir.

---

## 13. Değişen ve eklenen dosyalar

Liste tahminle değil, v2.4.48 tam paketiyle birebir `cmp` karşılaştırmasıyla belirlendi.

**Yeni dosyalar**

| Dosya | Satır | İşi |
|---|---|---|
| `goktungu/servis.py` | 449 | systemd birimi yönetimi ve makine gücü |
| `js/servis_panel.js` | 411 | Servis paneli ve makine güç arayüzü |
| `servis_kur.sh` | 333 | Birim, yetki ve kiosk kurulumu |
| `kiosk_baslat.sh` | 179 | İki ekran tam ekran düzeni |
| `goktungu.service.sablon` | 62 | systemd birim şablonu |
| `sinav_2449_servis.py` | — | 121 denetimli doğrulama sınavı |

**Değişen dosyalar:** `main.py`, `goktungu/sunucu.py`, `goktungu/__init__.py`, `js/ws.js`, `js/program_ayar.js`, `js/kullanici.js`, `js/i18n.js`, `js/surum.js`, `css/stil.css`, `index.html`, `flight.html`, `video.html`

`flight.html` ve `video.html` yalnızca önbellek etiketi için değişti; atlanırlarsa o sayfalar bayat JavaScript ve CSS çeker.

---

## 14. Paketler

| Paket | Boyut | İçerik |
|---|---|---|
| `goktungu-guncelleme-2.4.49.tar.gz` | 384 KB | Yalnız değişen ve yeni dosyalar (51 dosya) |
| `goktungu-tam-2.4.49.tar.gz` | 35 MB | Çalışan kurulumun tamamı + `sitl/` |
| `goktungu-sitl-2.4.49.tar.gz` | 26 MB | Yalnız `sitl/` klasörü |

> **SITL arşivini tekrar indirmeniz gerekmiyor.** İçeriği v2.4.47 ve v2.4.48 ile **birebir aynıdır** (`md5sum` ile doğrulandı). v2.4.49 hiçbir ikili dosya eklemedi veya değiştirmedi. Arşiv yalnızca ilk kez kuranlar tek bir sürüm numarası altında bütün dosyaları bulabilsin diye üretiliyor.

Paketleme betiğinde bir ölçüm kusuru bulunup düzeltildi: `set -o pipefail` etkinken `tar tzf ... | grep -q ...` kullanmak yanlış sonuç veriyordu. `grep -q` ilk eşleşmede çıkış yapıyor, bu hâlâ yazmakta olan `tar`'a SIGPIPE gönderiyor ve `tar` 141 koduyla düşüyor; `pipefail` bunu boru hattının sonucu saydığı için denetim, dosyalar **pakette olmasına rağmen** "EKSİK" diyordu. Liste artık bir kez değişkene alınıp öyle denetleniyor.

---

## 15. Kullanım özeti

| İşlem | Komut veya yol |
|---|---|
| Yamayı uygula (Linux) | `bash kur_2449.sh /kurulum/dizini` |
| Yamayı uygula (Windows) | `powershell -ExecutionPolicy Bypass -File .\kur_2449.ps1` |
| Servisi kur | `sudo bash servis_kur.sh` |
| Servisi kaldır | `sudo bash servis_kur.sh --kaldir` |
| Servis durumu | `systemctl status goktungu` |
| Servis günlüğü | `journalctl -u goktungu -n 50` |
| İki ekran kiosk | `bash kiosk_baslat.sh` |
| Kiosk'u kapat | `bash kiosk_baslat.sh --durdur` |
| Arayüzden servis yönetimi | Program Ayarları → Servis |
| Bilgisayarı kapat | Kullanıcı menüsü → Bilgisayarı Kapat (yalnız yönetici) |
| Doğrulama sınavı | `python3 sinav_2449_servis.py` |
| SITL tanılama | `python3 sitl_tani.py` |

---

**Hazırlayan:** Manus AI
**Tarih:** 11 Ağustos 2026
