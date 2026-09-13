# Kusur — Alt servisler Windows servisi altında başlatılamıyor (v1.4.0)

Bildiren: kullanıcı, 2026-08-14. Ekran görüntüsündeki konsol çıktısı:

```
Servis baslatildi (pid 11664)
C:\Program Files\Goktungu\Kopru\python\pythonservice.exe - Python Service Manager
 Options:
  -debug servicename [parms] - debug the Python service.
NOTE: You do not start the service using this program - start the
service using Control Panel, or 'net start service_name'
Servis sonlandi (cikis kodu 2)
```

Beş alt servisin hepsi (Dron/AI/Video/GroundGCC/Radar) aynı şekilde
başlatılıp anında çıkış kodu 2 ile sonlanıyor.

## Kök neden

`kopru/servisler.py:241`:

```python
return [sys.executable, "-m", self.tanim["modul"]]
```

Alt servisler `sys.executable` ile başlatılıyor. Bu, konsol
uygulamasında doğru (`python.exe`) ancak **SCM servisi bağlamında
yanlıştır**: pywin32 servisi `pythonservice.exe` tarafından barındırılır
ve o süreçte `sys.executable` → `...\python\pythonservice.exe` olur.

`pythonservice.exe` bir Python yorumlayıcısı DEĞİL, servis
barındırıcısıdır. `-m paket.modul` argümanını anlamaz; `-debug` dışında
bir argüman görünce kendi kullanım metnini basıp çıkar.

### Kanıt zinciri (Wine ölçümleri, /tmp/svc_sinav)

| Ölçüm | Sonuç |
|---|---|
| `python.exe kanit.py` → `sys.executable` | `...\python\python.exe` (doğru) |
| `pythonservice.exe` tek başına | çıkış kodu **1** |
| `pythonservice.exe -m kopru.dron_servis` | çıkış kodu **1** |
| Kullanım metninin kaynağı | `win32/servicemanager.pyd` içinde gömülü dize: `-debug servicename [parms] - debug the Python service.` + `NOTE: You do not start the service using this program` |

Kullanıcının gördüğü metin birebir bu gömülü dizedir. Wine'da
`init_sys_streams` hatası çıkıyor (konsol tanıtıcısı yok), gerçek
Windows'ta ise metin basılıp **çıkış kodu 2** dönüyor — kullanıcının
raporladığı kod bu.

## Neden setup denetimlerinden geçti

`sinav_setup_nsi.py` yalnız kurulum betiğini ve servis kaydını
denetliyordu. Alt servis başlatma yolu (`servisler.py:_komut`) servis
bağlamında hiç sınanmadı; Wine NSIS kurulumunu çalıştıramadığı için
uçtan uca akış da görülemedi.

## Çözüm yönü

`_komut()` `sys.executable`'a güvenmemeli. Yorumlayıcı şu sırayla
çözülmeli:

1. `GOKTUNGU_KOPRU_PYTHON` ortam değişkeni (servis kurulumu tarafından
   ayarlanır) — açık niyet
2. `sys.executable` yalnız gerçek bir yorumlayıcıysa (dosya adı
   `pythonservice.exe` DEĞİLSE)
3. Aynı dizinde `python.exe` / `pythonw.exe` ara (gömülü dağıtımda
   `pythonservice.exe` ile aynı klasörde bulunur)
4. `sys.prefix` altında ara
5. Hiçbiri yoksa anlaşılır hata (sessiz çıkış kodu 2 değil)

İkinci savunma: `servis_win.py` çalışırken `GOKTUNGU_KOPRU_PYTHON`
ayarlamalı ki alt süreçler her koşulda doğru yorumlayıcıyı görsün.

---

# DÜZELTME (v1.4.1) — uygulandı ve kanıtlandı

## Yapılan değişiklikler

| Dosya | Değişiklik |
|---|---|
| `kopru/servisler.py` | `yorumlayici_yolu()` ve `_pythonservice_mi()` eklendi; `_komut()` artık `sys.executable` kullanmıyor; çözümlenemezse panele anlaşılır hata düşüyor |
| `servis_win.py` | `_yorumlayiciyi_sabitle()` eklendi; servis başında yorumlayıcı bir kez çözülüp `GOKTUNGU_KOPRU_PYTHON`'a yazılıyor ve günlüğe düşürülüyor |
| `sinav_yorumlayici.py` | **Yeni sınav** — 17 denetim |

Çözümleme sırası: (1) `GOKTUNGU_KOPRU_PYTHON`, (2) `sys.executable` yalnız
barındırıcı değilse, (3) barındırıcının yanındaki dizin, (4) `sys.prefix`,
(5) `sys.base_prefix`. Hiçbiri yoksa `RuntimeError`.

`GOKTUNGU_KOPRU_PYTHON` barındırıcıyı gösteriyorsa **yok sayılır** — yanlış
yapılandırma aynı kusuru sessizce geri getirmesin.

## Tasarım kararı: aday adları platformdan bağımsız

İlk yazımda aday adları `os.name == "nt"` ile seçiliyordu ve sınav
"geçti" diyordu. Ancak sınav Linux'ta koştuğu için gerçekte **4. adımı**
(gerçek `sys.prefix`) doğruluyordu; sahada kırılan yer **3. adımdı**.
Yani sınav yanlış kod yolunu onaylıyordu.

Adlar artık koşulsuz denenir (`python.exe`, `pythonw.exe`, `python3`,
`python`). Windows'ta `python3` bulunmaz, Linux'ta `python.exe` bulunmaz;
var olmayan ad zararsızca atlanır. Bu, sınavın Windows düzenini taklit
edebilmesini sağlayan işlevsel bir karardır.

## Kanıt 1 — `sinav_yorumlayici.py`: 17 geçti / 0 kaldı

Barındırıcı tuzağı, ortam değişkeni önceliği, aday yokken anlaşılır hata,
üretilen komut biçimi ve **beş servisin tamamı** ayrı ayrı ölçüldü.

## Kanıt 2 — gerçek gömülü dağıtımla Wine ölçümü

`sys.executable` gerçekten `pythonservice.exe`'ye ayarlanıp kurulumun
dağıttığı gömülü Python ağacı üzerinde ölçüldü:

```
taklit sys.executable : Z:\tmp\svc_sinav\python\pythonservice.exe
cozulen yorumlayici   : Z:\tmp\svc_sinav\python\python.exe
BARINDIRICI MI        : False
  dron     -> python.exe -m kopru.servis_dron
  ai       -> python.exe -m kopru.servis_ai
  video    -> python.exe -m kopru.servis_video
  gcsdual  -> python.exe -m kopru.servis_gcsdual
  radar    -> python.exe -m kopru.servis_radar
```

## Kanıt 3 — eski yol / yeni yol yan yana (gerçek ikililer, Wine)

**Eski yol** (`pythonservice.exe -m kopru.servis_dron`) — sahadaki
çıktının aynısı yeniden üretildi:

```
Z:\...\pythonservice.exe - Python Service Manager
Options:
 -debug servicename [parms] - debug the Python service.
NOTE: You do not start the service using this program ...
```

**Yeni yol** (`python.exe -m kopru.servis_dron`) — servis gerçekten ayağa
kalktı ve ayakta kaldı:

```
12:11:01 Dron Servisi baslatiliyor (pid 32)
12:11:01 Telemetri tamponu: C:\ProgramData\Goktungu\Kopru\telemetri_tampon
12:11:01 [UYARI] Yerel seri port bulunamadi (takili cihaz yok)
12:11:01 [OK] Dron servisi hazir. Baglanti tanimlari merkezdeki
         Baglanti Yoneticisi'nden yonetilir.
12:11:01 Durum: 0 yerel seri port, 0 bekleyen telemetri ornegi
[OLCUM] 8 saniye ayakta kaldi
```

Bu, düzeltmenin yalnız komut dizesini değiştirmediğini, alt servisin
**gerçekten çalıştığını** gösteren uçtan uca kanıttır.

> Wine notu: çıktı dosyaya yönlendirildiğinde gömülü Python
> `init_sys_streams: can't initialize sys standard streams` ile düşüyor.
> Bu Wine'ın tanıtıcı devretme sınırıdır, köprü kusuru değildir; ölçüm
> doğrudan uçbirime yazılarak yapıldı.

## Linux tarafı

Bu kusur Linux'ta **oluşamaz**: systemd birimi `ExecStart` ile doğrudan
`python3` çağırır, arada barındırıcı yoktur. Düzeltme yine platform
bağımsızdır; `.deb` de sürüm tutarlılığı için v1.4.1 olarak yeniden
üretilecek.
