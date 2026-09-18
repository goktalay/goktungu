# GÖKTUNGU Python Makro API'si — makro yazan yapay zekâ için rehber

Bu belge, GÖKTUNGU yer kontrol istasyonunda (GRCOFF/GRCON, uygulama sürümü ≥ 2.4.252) çalışan **dron makrolarını** yazacak bir yapay zekâ (veya geliştirici) için tam sözleşmedir. Makro, kullanıcının **Rotalar > Makrolar** panelinde oluşturduğu ve Python düzenleme panelinde çalıştırdığı bir Python 3.11 betiğidir.

## 1. Çalışma ortamı (mutlaka bilinmesi gerekenler)

- Makro, GCS sürecinden **ayrı ve kısıtlı** bir Python 3.11 sürecinde koşar. Betik `exec` ile, aşağıdaki isimler önceden tanımlanmış bir isim alanında çalıştırılır. `import` gerekmez; `pymavlink` yüklüdür.
- Seçili drona erişim, GCS'in her dron için açtığı **MAVLink UDP aynası** (127.0.0.1:9000+sysid) üzerinden **çift yönlü**dür: telemetri okunur, komut gönderilir.
- Kısıtlar: yalnız `127.0.0.1` adresine soket açılabilir; `subprocess`, `ctypes`, `multiprocessing`, `shutil`, `importlib`, `sqlite3`, `psycopg2`, `goktungu` modülleri yasaktır; `os.system/popen/exec*/fork/kill/remove/rename/chmod` kapalıdır; dosya açma yalnız makronun kendi çalışma dizininde (göreli yol kullanın: `open("not.txt","w")`). Bellek tavanı 1 GB, dosya boyutu 64 MB.
- Zaman aşımı: kayıt başına `sure_sn` (varsayılan 3600 sn, 0 = sınırsız). Süre dolunca süreç sonlandırılır.
- Çıktı: `yaz(...)` veya `print(...)` satırları arayüzdeki çıktı penceresine canlı akar. İstisnalar traceback olarak görünür, makro "Hata" durumuyla biter (çıkış kodu 1). `bildir(metin)` arayüzde uyarı balonu gösterir.
- Kullanıcı "Durdur"a basarsa süreç SIGTERM ile sonlandırılır; temizlik için `try/finally` kullanın (örneğin `finally: dron.eve_don()` gibi bir davranış **istenmiyorsa** yazmayın; sonlandırmada finally bloğu çalışmayabilir).

## 2. Hazır isimler

| İsim | Tür | Açıklama |
|---|---|---|
| `mav` | `mavutil.mavfile` | Seçili dronun pymavlink bağlantısı (`udpout:127.0.0.1:<port>`, source_system 250, component 190). Seçili dron yoksa `None`. |
| `mavutil` | modül | `pymavlink.mavutil` |
| `mavlink` | modül | `pymavlink.dialects.v20.ardupilotmega` (MAV_CMD_*, MAV_FRAME_*, MAV_MODE_* sabitleri) |
| `dron` | `DronFasadi` | Seçili dronun kolay arayüzü (aşağıda). Seçili dron yoksa `None`. |
| `dronlar` | `dict` benzeri | `dronlar[sysid]` → o dronun `DronFasadi` nesnesi (ilk erişimde bağlantı açılır). `dronlar.sysidler()` bağlı sysid listesi. |
| `dron_bul(sysid)` | işlev | `dronlar[int(sysid)]` kısayolu |
| `sysid` | `int` | Seçili dronun MAVLink sistem kimliği (0 = seçili dron yok) |
| `bekle(sn)` | işlev | `time.sleep` |
| `yaz(*parcalar)` / `print` | işlev | Çıktı penceresine yazar (boşlukla birleştirir) |
| `bildir(metin)` | işlev | Arayüzde bildirim balonu |
| `durdur()` | işlev | Makroyu başarıyla bitirir (çıkış kodu 0) |
| `time`, `math`, `json` | modül | Standart modüller (ayrıca `import` ile stdlib'in yasak olmayan kısmı kullanılabilir) |

## 3. `dron` (DronFasadi) — alanlar

Telemetri arka planda okunur; alanlar anlık değerdir, henüz gelmediyse `None` döner.

| Alan | Birim / tip | Kaynak MAVLink mesajı |
|---|---|---|
| `dron.lat`, `dron.lon` | derece (float) | GLOBAL_POSITION_INT |
| `dron.konum` | `(lat, lon)` demeti | GLOBAL_POSITION_INT |
| `dron.irtifa` | metre, kalkış noktasına göreli | GLOBAL_POSITION_INT.relative_alt |
| `dron.irtifa_msl` | metre, deniz seviyesi | GLOBAL_POSITION_INT.alt |
| `dron.yon` | derece 0–360 | GLOBAL_POSITION_INT.hdg |
| `dron.hiz` | m/s yer hızı | VFR_HUD.groundspeed |
| `dron.batarya` | yüzde (0–100) veya `None` | SYS_STATUS |
| `dron.batarya_v` | volt | SYS_STATUS |
| `dron.mod` | mod adı, örn. `"GUIDED"` | HEARTBEAT.custom_mode |
| `dron.armed` | bool | HEARTBEAT.base_mode |
| `dron.ucusta` | bool (armed ve göreli irtifa > 1 m) | türetilmiş |
| `dron.konum_gecerli` | bool: lat/lon var, (0,0) değil, gps_fix ≥ 2 | türetilmiş |
| `dron.bagli` | bool (son 5 sn içinde heartbeat) | türetilmiş |
| `dron.gps_fix`, `dron.uydu` | int | GPS_RAW_INT |
| `dron.roll`, `dron.pitch` | derece | ATTITUDE |
| `dron.sysid`, `dron.port`, `dron.mav` | — | kimlik ve ham bağlantı |
| `dron.durum()` | dict | tüm alanlar tek sözlükte |

## 4. `dron` — işlevler

Tüm işlevler ArduPilot (Copter/Plane/Rover) hedefler; komutlar `COMMAND_LONG` ile `target_component=1`'e gider.

| İşlev | Ne yapar | Dönüş |
|---|---|---|
| `dron.bekle_baglanti(zaman_asimi=15)` | Heartbeat gelene kadar bekler | `True/False` |
| `dron.bekle_konum(zaman_asimi=30)` | Geçerli GPS/EKF konumu gelene kadar bekler | `True/False` |
| `dron.arm(bekle=True, zorla=False, zaman_asimi=10)` | MAV_CMD_COMPONENT_ARM_DISARM (zorla: param2=21196) | armed olduysa `True` |
| `dron.disarm(zorla=False)` | Disarm | ACK sonucu (0 = kabul) veya `None` |
| `dron.mod_ayarla(ad, bekle=True, zaman_asimi=5, zorla=False)` | Uçuş modu (`"GUIDED"`, `"AUTO"`, `"LOITER"`, `"RTL"`, `"LAND"`, `"STABILIZE"` …); bilinmeyen ad `ValueError`. **Konum gerektiren modlar** (GUIDED, AUTO, RTL, LOITER, CIRCLE, …) geçerli konum yokken `RuntimeError` verir; `zorla=True` atlar (tehlikeli) | moda geçtiyse `True` |
| `dron.kalk(irtifa=10, bekle=True, zaman_asimi=60, zorla=False)` | GUIDED → arm → MAV_CMD_NAV_TAKEOFF; irtifanın %95'ine ulaşınca döner. Konum yoksa veya arm edilemezse `RuntimeError` | `True/False` |
| `dron.git(lat, lon, irtifa=None, bekle=False, tol_m=3, zaman_asimi=300, zorla=False)` | SET_POSITION_TARGET_GLOBAL_INT (GLOBAL_RELATIVE_ALT_INT, yalnız konum). `irtifa=None` → mevcut göreli irtifa. `bekle=True` varışa kadar bekler. Hedef (0,0) veya aralık dışıysa `ValueError`; aracın konumu yoksa `RuntimeError`. **App ≥ 2.4.252:** 1 m altındaki göreli hedef irtifası 1 m'ye yükseltilir ve uyarı yazılır; göreli irtifa 0, ArduPilot'ta `PANIC: Location cannot be (0, 0, 0)` çökmesine yol açtığı için doğrudan gönderilmez. | `True/False` |
| `dron.eve_don()` | RTL modu | `True/False` |
| `dron.inis()` | LAND modu | `True/False` |
| `dron.hiz_ayarla(m_s)` | MAV_CMD_DO_CHANGE_SPEED (yer hızı) | ACK sonucu |
| `dron.mesafe(lat, lon)` | Drondan noktaya büyük daire uzaklığı (m); konum yoksa `None` | float |
| `dron.bekle_varis(lat, lon, tol_m=3, zaman_asimi=300)` | Noktaya `tol_m` içinde yaklaşana kadar bekler | `True/False` |
| `dron.bekle_irtifa(irtifa, tol_m=1, zaman_asimi=120)` | Göreli irtifaya ulaşana kadar bekler | `True/False` |
| `dron.param_get(ad, zaman_asimi=3, deneme=3)` | PARAM_REQUEST_READ ile parametre okur (`"WPNAV_SPEED"`); takma ad `param_oku` | float veya `None` |
| `dron.param_set(ad, deger, zaman_asimi=3, deneme=3, dogrula=True)` | PARAM_SET gönderir ve PARAM_VALUE ile doğrular; tip önce okunmuşsa aynı tip, yoksa REAL32 (ArduPilot tam sayı parametreleri de kabul eder); takma ad `param_ayarla` | doğrulandıysa `True` |
| `dron.komut(cmd, p1..p7, onay_bekle=True, zaman_asimi=5)` | Ham COMMAND_LONG; `onay_bekle=True` ise COMMAND_ACK.result döner (0 = MAV_RESULT_ACCEPTED) | int veya `None` |
| `dron.kapat()` | Bağlantıyı kapatır (makro sonunda otomatik) | — |

Not: Python'da `in` anahtar kelime olduğu için iniş `dron.inis()`'tir; `getattr(dron, "in")` de çalışır.

## 5. Ham MAVLink (`mav`) kullanımı

`mav` gerçek bir `mavutil` bağlantısıdır; pymavlink belgelerindeki her şey geçerlidir:

```python
# Mesaj bekleme
m = mav.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=2)
if m: yaz("alt", m.relative_alt / 1000)

# Ham komut
mav.mav.command_long_send(sysid, 1, mavlink.MAV_CMD_DO_SET_SERVO, 0, 9, 1500, 0, 0, 0, 0, 0)

# Parametre okuma/yazma
mav.mav.param_request_read_send(sysid, 1, b"WPNAV_SPEED", -1)
p = mav.recv_match(type="PARAM_VALUE", blocking=True, timeout=3)
mav.mav.param_set_send(sysid, 1, b"WPNAV_SPEED", 800.0, mavlink.MAV_PARAM_TYPE_REAL32)

# Mod eşlemesi
yaz(mav.mode_mapping())
```

Dikkat: `dron` nesnesinin arka plan okuyucusu aynı bağlantıdan mesaj tüketir; `mav.recv_match` ile beklerken belirli tipleri kaçırabilirsiniz. Belirli bir mesaj gerekiyorsa kısa `timeout` ile döngüde yeniden deneyin veya `dron` alanlarını kullanın.

## 6. Makro yazım kuralları (yapay zekâ için)

1. Betik **üst düzeyde** çalışır; `main()` sarmalamak zorunlu değildir ama uzun betiklerde tavsiye edilir.
2. Başta bağlantıyı doğrulayın: `if dron is None or not dron.bagli: yaz("Dron bağlı değil"); durdur()`.
2b. **Konum gerektiren her şeyden önce** (`mod_ayarla("GUIDED")`, `git`, `kalk`, arm) `dron.bekle_konum(30)` çağırın ve `False` dönerse durun. Konumsuz (GPS kilidi yok, lat/lon = 0) bir aracı GUIDED/AUTO'ya almak veya hedefe göndermek otopilotu çökertebilir (ArduPilot: "Location cannot be (0, 0, 0)"); API bu durumda `RuntimeError` verir, `zorla=True` ile atlamayın.
2c. Güvenlik parametrelerini (ARMING_CHECK, FS_*, FENCE, STALL_PREVENT, PTCH_LIM_*) kapatan makro yazmayın; kullanıcı açıkça istemedikçe failsafe ayarlarına dokunmayın.
3. Her bekleme işlevinin dönüşünü kontrol edin; `False` ise güvenli bir adıma geçin (örn. `dron.eve_don()`), ardından `durdur()`.
4. Sonsuz döngülerde mutlaka `bekle(...)` kullanın (CPU tavanı vardır) ve bir çıkış koşulu koyun.
5. Koordinatlar ondalık derece, irtifalar **göreli metre**dir. Küçük yer değiştirme için: 1° enlem ≈ 111 320 m; 1° boylam ≈ 111 320 × cos(enlem) m.
6. Kullanıcıya görünür sonuçlar için `yaz`; önemli olaylar için `bildir`.
7. Çıktıya şifre, IP dışı gizli veri yazmayın; dosya yazacaksanız göreli ad kullanın.
8. Yasak modül veya dış ağ gerektiren kod yazmayın (`requests`, `socket` dış adres, `subprocess`).
9. Birden fazla dron için `dronlar[2]`, `dronlar[3]` gibi erişin; her biri ayrı `DronFasadi`dir.
10. Makro, çalıştırıldığı dronu arayüzden alır (`sysid`); kodun içine sysid sabitlemeyin.

## 7. Örnekler

### 7.1 Kalkış, kare rota, dönüş
```python
if dron is None or not dron.bekle_baglanti(10):
    yaz("Dron bağlı değil"); durdur()
if not dron.bekle_konum(30):
    yaz("GPS konumu yok, kalkış iptal"); durdur()
yaz("Başlangıç", dron.konum, "mod", dron.mod, "batarya %", dron.batarya)
if not dron.kalk(20):
    bildir("Kalkış başarısız"); dron.inis(); durdur()
lat0, lon0 = dron.konum
d = 40 / 111320.0
for i, (dl, dn) in enumerate([(d, 0), (d, d), (0, d), (0, 0)], 1):
    hedef = (lat0 + dl, lon0 + dn / math.cos(math.radians(lat0)))
    yaz("Nokta", i, hedef)
    if not dron.git(hedef[0], hedef[1], 20, bekle=True, tol_m=3, zaman_asimi=120):
        bildir("Nokta %d'ye varılamadı" % i); break
bildir("Rota bitti, eve dönülüyor")
dron.eve_don()
```

### 7.2 Batarya gözcüsü (arka plan makrosu)
```python
esik = 30
while True:
    if not dron.bagli:
        yaz("bağlantı yok, bekleniyor"); bekle(5); continue
    b = dron.batarya
    if b is not None and b <= esik and dron.ucusta and dron.mod != "RTL":
        bildir("Batarya %%%d, RTL başlatıldı" % b)
        dron.eve_don()
        durdur()
    bekle(2)
```

### 7.3 Parametre okuma/yazma
```python
eski = dron.param_get("WPNAV_SPEED")
yaz("WPNAV_SPEED (cm/s):", eski)
if not dron.param_set("WPNAV_SPEED", 800):
    bildir("Parametre yazılamadı"); durdur()
yaz("Yeni değer:", dron.param_get("WPNAV_SPEED"))
# Kalıcı olması için otopilot parametreyi EEPROM'a kendisi yazar (ArduPilot).
```

### 7.4 Ham MAVLink ile servo darbesi ve ACK kontrolü
```python
sonuc = dron.komut(mavlink.MAV_CMD_DO_SET_SERVO, 9, 1900)
yaz("servo ACK:", sonuc)   # 0 = kabul edildi
bekle(1)
dron.komut(mavlink.MAV_CMD_DO_SET_SERVO, 9, 1100)
```

### 7.5 İki dronla eş zamanlı kalkış
```python
a, b = dronlar[1], dronlar[2]
for d in (a, b):
    if not d.bekle_baglanti(10): yaz("sysid", d.sysid, "bağlı değil"); durdur()
a.kalk(15, bekle=False); b.kalk(15, bekle=False)
a.bekle_irtifa(15); b.bekle_irtifa(15)
bildir("İki dron 15 m'de")
```

## 8. Durumlar ve çıkış kodları

| Durum | Anlam |
|---|---|
| `hazir` | Hiç çalıştırılmadı |
| `calisiyor` | Süreç canlı |
| `bitti` | Çıkış kodu 0 (`durdur()` veya betik sonu) |
| `hata` | Çıkış kodu ≠ 0 (istisna: 1, pymavlink yüklenemedi: 3) |
| `durduruldu` | Kullanıcı durdurdu veya zaman aşımı |

## 9. Sistem tarafı (referans)

- Kayıt: `makrolar` tablosu (ad, aciklama, kod, sure_sn, firma_id). WS komutları: `makro_liste`, `makro_kaydet`, `makro_sil`, `makro_kod_oku`, `makro_kod_yaz`, `makro_calistir {makro_id, sysid}`, `makro_durdur`, `makro_cikti_temizle`; yayınlar: `makrolar`, `makro_kod`, `makro_kod_yazildi`, `makro_durum`, `makro_cikti`.
- Kaynak: `goktungu/makrolar.py` (kayıt + çalıştırıcı), `goktungu/makro_kosucu.py` (koşucu, sandbox, `DronFasadi`), `js/makrolar.js` (panel).
- GRCON'da makro çalıştırma/kaydetme yetkisi dron pilotluk iznine bağlıdır; makrolar firmaya özeldir.
