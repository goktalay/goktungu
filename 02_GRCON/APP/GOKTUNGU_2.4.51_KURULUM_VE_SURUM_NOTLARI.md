# GÖKTUNGU GCS v2.4.51 — Kurulum ve Sürüm Notları

**Sürüm:** 2.4.51
**Tarih:** 11 Ağustos 2026
**Önceki sürüm:** 2.4.50
**Konu:** SQLite'tan PostgreSQL'e tam geçiş, kurulum ve göç sihirbazı

---

## 1. Bu sürüm ne yapıyor

Bu sürüm altı isteği ele alır:

> "şimdi veritabanını postgresql'e çevirelim. sistemi ilk açtığımda bana sunucu bilgilerini sorsun, ip adresi, kullanıcı adı, şifresi, veritabanı adı, sonra ilk kurulumu yapsın, eğer daha önce kurulum yapıldıysa ilk açılışta veri tabanında tablolarda yada diğer şeylerde bir güncelleme varsa sihirbaz açılsın ve güncellemeyi yapsın. tüm bu süreçlerde mutlaka progressbar olsun ve neyin sürdüğünü bilgilendirsin."

> "mümkünse fiziksel dosyalarda tuttuğun tamponları ve ayar dosyalarını da postgresql'e taşıyalım"

> "sqlite'a dönmeyeceğiz, lütfen her veriyi postgresql'e çevir ve mümkünse harita tamponlarını da çevir"

| İstek | Durum |
|---|---|
| Veritabanının PostgreSQL'e çevrilmesi | Tamamlandı — 27 tablo + 3 görünüm |
| İlk açılışta sunucu bilgilerinin sorulması | Tamamlandı — 3 adımlı sihirbaz |
| İlk kurulumun yapılması | Tamamlandı — şema kurulumu sihirbaz içinde |
| Şema güncellemesi varsa sihirbazın açılması | Tamamlandı — göç motoru + tek ekranlı sihirbaz |
| İlerleme çubuğu ve adım bildirimi | Tamamlandı — anlık yayın, yüzde geri sarmaz |
| Dosya tamponlarının ve harita önbelleğinin taşınması | Tamamlandı — iki katmanlı depo, iki bilinçli istisna |

---

## 2. Kurulum

### 2.1 Ön koşul: PostgreSQL sunucusu

Bu yama **PostgreSQL sunucusunu kurmaz**. Bu bilinçli bir karardır: sunucu kurulumunu size bıraktığımızda aynı makinedeki bir sunucu da, ağdaki merkezi bir sunucu da kullanılabilir. Böylece ileride birden fazla yer istasyonu aynı veritabanını paylaşabilir.

Linux (GX10 dahil):

```bash
sudo apt install -y postgresql postgresql-contrib
sudo -u postgres psql <<'SQL'
CREATE USER goktungu WITH PASSWORD 'guclu_bir_sifre';
CREATE DATABASE goktungu OWNER goktungu;
\c goktungu
CREATE EXTENSION IF NOT EXISTS citext;
SQL
```

Windows için [postgresql.org/download/windows](https://www.postgresql.org/download/windows/) adresindeki kurulumu (EDB installer) kullanın, ardından pgAdmin veya SQL Shell üzerinden yukarıdaki SQL bloğunu çalıştırın.

**citext eklentisi önerilir, zorunlu değildir.** Bu eklenti e-posta karşılaştırmasını büyük/küçük harften bağımsız yapar. Yoksa program düz `TEXT` kullanır ve karşılaştırmayı Python tarafında yürütür; sistem çalışır ancak veritabanı düzeyinde mükerrer kayıt koruması zayıflar. Sihirbazın ikinci adımı citext'in var olup olmadığını size bildirir.

Python sürücüsü kurulum betiği tarafından otomatik kurulur; elle kurmak isterseniz:

```bash
pip3 install psycopg2-binary
```

GX10 (aarch64) için `psycopg2-binary` hazır tekerlek sunar, derleme gerekmez.

### 2.2 Linux (ASUS Ascent GX10 dahil)

```bash
tar xzf goktungu-guncelleme-2.4.51.tar.gz
cd goktungu-guncelleme-2.4.51
bash kur_2451.sh ~/goktungu
```

### 2.3 Windows

```powershell
tar -xzf goktungu-guncelleme-2.4.51.tar.gz
cd goktungu-guncelleme-2.4.51
powershell -ExecutionPolicy Bypass -File .\kur_2451.ps1 -Hedef "C:\goktungu"
```

Bu sürüm **platformdan bağımsızdır**; her iki işletim sisteminde birebir aynı çalışır.

### 2.4 Kurulum sonrası zorunlu adımlar

Kurulum tamamlandıktan sonra tarayıcıda **Ctrl+Shift+R** yapılması zorunludur. Aksi halde tarayıcı önbellekteki eski JavaScript dosyalarını kullanmaya devam eder ve sihirbaz hiç açılmaz.

> **SITL arşivini tekrar indirmeniz gerekmiyor.** `goktungu-sitl-2.4.51.tar.gz` içeriği v2.4.47–v2.4.50 arşivleriyle birebir aynıdır; paketleme betiği bunu içerik karşılaştırmasıyla doğrular.

---

## 3. Sihirbaz nasıl çalışır

### 3.1 İlk kurulum

Program başlatılıp tarayıcı açıldığında, yapılandırma yoksa sihirbaz **giriş ekranından önce** açılır. Bu sıralama zorunludur: `kullanicilar` tablosu artık PostgreSQL'de bulunur, dolayısıyla veritabanı yapılandırılmadan hiç kimse doğrulanamaz. (Bu, v2.4.45'teki şirket bilgileri sihirbazının tersidir; o sihirbaz girişten *sonra* açılır, çünkü kimin yönetici olduğunu bilmesi gerekir.)

| Adım | İçerik |
|---|---|
| 1 | Sunucu IP, port (5432), veritabanı adı, kullanıcı adı, şifre |
| 2 | Bağlantı gerçekten kurulur; PostgreSQL sürümü, mevcut tablo sayısı, citext durumu ve yetkiler gösterilir |
| 3 | Şema kurulumu; ilerleme çubuğu adım adım ilerler ve o an ne yapıldığını yazar |

İkinci adımda bağlantı **gerçekten denenir**; alanların dolu olup olmadığına bakılmakla yetinilmez. Hedef veritabanı yoksa ve kullanıcının `CREATEDB` yetkisi varsa "Veritabanını Oluştur" düğmesi görünür.

### 3.2 Şema güncellemesi

Yapılandırma varsa ancak şema sürümü eskiyse, açılışta tek ekranlı göç sihirbazı çıkar. Ekranda mevcut ve hedef şema sürümü, bekleyen adımların listesi ve ilerleme çubuğu bulunur. Güncelleme tamamlanmadan sistem kullanılamaz; yarım şemayla uçmak veri kaybı riskidir.

Göç motoru `sema_goc_defteri` tablosunu tutar. Bu defter sayesinde "bu veritabanı hangi şema sürümünde?" sorusu ilk kez kesin olarak cevaplanabilir hale gelir; ayrıca yarım kalmış bir göç sonraki açılışta kaldığı yerden sürdürülür.

### 3.3 Bilgileri sonradan değiştirme

**Kullanıcı menüsü → Veritabanı Ayarları** (yalnız yönetici). Sunucu taşındığında veya şifre değiştiğinde sihirbaz buradan yeniden çalıştırılır.

---

## 4. Mimari karar: ağ geçidi katmanı

Kod tabanında **146 veritabanı çağrı yeri ve 256 yer tutucu** ölçüldü. Bunları elle PostgreSQL sözdizimine çevirmek yüzlerce sessiz kusur üretirdi; bir uçuş kontrol yazılımında bu kabul edilemez.

Bu yüzden `goktungu/pg.py` bir **ağ geçidi katmanı** olarak yazıldı ve `baglanti()` imzası aynı bırakıldı. Çağrı yerlerinin hiçbiri değişmedi. Katman şu çevirileri yapar:

| SQLite | PostgreSQL |
|---|---|
| `?` yer tutucu | `%s` |
| `AUTOINCREMENT` | `BIGSERIAL` |
| `COLLATE NOCASE` | `citext` |
| `strftime(...)` | `to_char(...)` |
| `PRAGMA table_info` | `information_schema` sorgusu |
| `cursor.lastrowid` | `SAVEPOINT` + `RETURNING` |
| `total_changes` | imleç sayacı |

### 4.1 Ölçümde bulunan on iki sessiz kusur

Bu katman yazıldıktan sonra 154 denetimlik dört ölçüm koşumu yapıldı. Bulunan kusurların tamamı giderildi. Aşağıdaki listede önemli olan nokta, hepsinin **belirti üretmeden** veri bozması veya veri kaybettirmesidir.

| # | Kusur | Belirtisiz sonucu |
|---|---|---|
| 1 | `RETURNING id` koşulsuz ekleniyordu | `id` kolonu olmayan tabloya ikinci yazımda hata oluşup `rollback()` çalışıyor ve aynı işlemdeki **önceki yazımların tamamı siliniyordu** |
| 2 | Şema ölçümü aynı imleçte yapılıyordu | `lastrowid` None dönüyordu |
| 3 | `RELEASE SAVEPOINT` sıralaması | `RETURNING` sonucu geçersizleşiyordu |
| 4 | `INTEGER PRIMARY KEY` koşulsuz `BIGSERIAL`'e çevriliyordu | `sysid` gibi **anlamlı anahtarlar** veritabanı sayacıyla eziliyordu |
| 5 | İçinde `%s` geçen sorgular | Bozuluyordu |
| 6 | `total_changes` yoktu | **Telemetri aktarımı hiç çalışmıyordu** |
| 7 | `dene()` iki kez tanımlıydı | Zengin sürüm gölgede kalıyordu |
| 8 | `gorev_durum` birincil anahtarı `dron_uid`'di | **İki dron aynı satıra yazıyordu**; ikinci dron birincinin görevini eziyordu |
| 9 | `strftime` | PostgreSQL'de sözdizimi hatası |
| 10 | `v_ucuslar` görünümünde `GROUP BY` eksikti | PostgreSQL görünümü **reddediyordu** (SQLite hoşgörüyle rastgele satır döndürüyordu) |
| 11 | `sunucu.py` yanlış API adlarıyla yazılmıştı (12 çağrı) | En sinsisi: `goc.durum()` "gerekli" değil **"guncel"** döner — ikisi ters anlam. Karıştırılsa göç sihirbazı hiç açılmaz, kullanıcı eski şemayla uçar ve hiçbir hata görünmezdi |
| 12 | İlerleme yüzdesi geri sarıyordu | Ölçülen dizi `[2, 6, 0, 5, 50...]` — kullanıcı çubuğun geri atladığını görüp sürecin baştan başladığını sanardı |

Sekizinci maddenin gerekçesi ayrıca not edilmelidir: `sysid` bir MAVLink kimliğidir ve veritabanı sayacıyla değiştirilemez. Bu nedenle `INTEGER PRIMARY KEY → BIGSERIAL` dönüşümü yalnızca `AUTOINCREMENT` yazan tanımlara uygulanır; `sysid` gibi anlamlı anahtarlar `BIGINT` olarak korunur.

### 4.2 İlerleme çubuğunun geri sarması

On ikinci kusur ilerleme çubuğunun tasarımıyla ilgilidir ve düzeltmenin nereye konulduğu önemlidir. Yüzde **iki kaynaktan** gelir: sunucunun hazırlık adımları ve göç motorunun kendi adımları. İkisi ayrı ölçek kullanır.

İlk düzeltme denemesi göç motorunun içine konuldu ve **yetmedi**; motorun kendi kelepçesi kendisinden önce çalışan hazırlık adımlarını kapsamıyordu. Kalıcı çözüm, tek yönlü kelepçenin iki kaynağın **birleştiği** WebSocket yayın noktasına konulmasıdır. Yüzde artık asla azalmaz, ancak ileti metni güncellenmeye devam eder; böylece kullanıcı hem tutarlı bir çubuk hem de doğru adım bilgisi görür.

İlerleme bildirimi ayrıca **anlık** yayınlanır (`asyncio.Queue` + `call_soon_threadsafe`). Göç motoru ayrı bir iş parçasında çalıştığı için, bildirimler sonda toplu gönderilseydi çubuk hiç hareket etmez, sonra bir anda %100 olurdu; kullanıcı programın donduğunu düşünüp kapatabilirdi.

---

## 5. Dosyadan PostgreSQL'e taşınanlar

| Veri | Yeni yer |
|---|---|
| 27 tablo + 3 görünümün tamamı | PostgreSQL |
| Harita karoları | `harita_karo` tablosu |
| Görev durumu | `gorev_durum` tablosu (anahtar: `sysid`) |
| Telemetri defteri | `telemetri_tampon_kayit` tablosu |

### 5.1 İki katmanlı depo

Harita karolarında ve görev durumunda PostgreSQL **ana depo**, disk **ikinci katmandır**. Gerekçe uçuş güvenliğidir: PostgreSQL erişilemez olursa harita kararmaz ve görev kaydı kaybolmaz; sistem diskteki veriyle çalışmayı sürdürür. Tek katmanlı bir tasarımda veritabanı bağlantısının kopması haritanın tamamen boşalması anlamına gelirdi.

### 5.2 Bilinçli olarak dosyada bırakılanlar

İki veri kalemi kasten dosyada tutuldu:

- **`veri/calisma.json`** — Kiosk betiği bu dosyayı **sunucu ayakta değilken** okuyup hangi porta bağlanacağını bulur. PostgreSQL'e taşınsaydı iki ekranlı kiosk düzeni kırılırdı, çünkü betik veritabanına erişemez.
- **`veri/telemetri_tampon/*.jsonl` (ham örnekler)** — Bu dakikalık tampon, v2.4.24'te bildirdiğiniz "disk yazma hatası" sorununun çözümünün ta kendisidir. Ayrıca ağ veya veritabanı kesintisinde uçuş verisinin kaybolmaması için diskte tutulur. **Aktarım PostgreSQL'e yapılır**; yalnızca ham tampon diskte kalır.

Bu iki istisna dışında her veri PostgreSQL'dedir.

---

## 6. WebSocket sözleşmesi

| Komut | Yanıt | Kapı |
|---|---|---|
| `pg_durum` | `pg_durum` | Her zaman açık (giriş öncesi gerekli) |
| `pg_dene` | `pg_sonuc` | Yapılandırma varsa yalnız yönetici |
| `pg_olustur` | `pg_sonuc` | Yapılandırma varsa yalnız yönetici |
| `pg_kur` | `pg_ilerleme`* + `pg_sonuc` | Yapılandırma varsa yalnız yönetici |
| `pg_goc` | `pg_ilerleme`* + `pg_sonuc` | Yapılandırma varsa yalnız yönetici |

Kapı mantığı iki durumu ayırır: yapılandırma **yoksa** komutlar açıktır (aksi halde ilk kurulum imkânsız olurdu, çünkü doğrulanacak kullanıcı henüz yok); yapılandırma **varsa** yalnız yönetici çağırabilir.

`pg_durum` yanıtı şifre **içermez**. Şifre yalnızca sunucu tarafında, `veri/pg.json` dosyasında 0600 izinle tutulur. Paketleme betiği bu dosyanın hiçbir arşive sızmadığını ayrıca denetler.

---

## 7. Doğrulama ölçümleri

### 7.1 Katman ölçümleri (gerçek PostgreSQL üzerinde)

| Ölçüm | Sonuç | Kapsam |
|---|---|---|
| `dene_pg_gecit.py` | 44 / 0 | Ağ geçidi katmanı, lehçe çevirileri |
| `dene_pg_veri.py` | 26 / 0 | Okuma ve yazma yolları |
| `dene_goc.py` | 28 / 0 | Göç motoru, defter, yarım göç kurtarma |
| `dene_faz5.py` | 16 / 0 | Harita karosu, görev durumu, telemetri defteri |
| `dene_pg_ws.py` | 40 / 0 | **Canlı sunucu**, uçtan uca sihirbaz akışı |

### 7.2 Sınavlar

| Sınav | Sonuç | Kapsam |
|---|---|---|
| `sinav_2451_pg.py` | 199 / 0 | Statik sözleşme + gerçek PostgreSQL denetimi |
| `sinav_2450_joystick.py` | 88 / 0 | Gerileme |
| `sinav_2449_servis.py` | 127 / 0 | Gerileme |

**Toplam: 568 geçti / 0 kaldı.**

Kendi kurulumunuzda doğrulamak için:

```bash
python3 sinav_2451_pg.py          # 199 PG denetimi
python3 sinav_2450_joystick.py    #  88 joystick denetimi
python3 sinav_2449_servis.py      # 127 servis denetimi
python3 dene_pg_ws.py             #  40 canlı denetim (sunucu ayakta olmalı)
```

### 7.3 Sınav mantığında yapılan düzeltme

v2.4.50 sınavındaki sabit sürüm beklentileri (`v=v2450` gibi) bu sürümde ">= 2450" mantığına çevrildi. Sabit beklenti her yeni sürümde gerçek bir kusur olmadığı halde "kaldı" verir; zamanla "nasıl olsa kalıyor" diye göz ardı edilir ve **asıl** kusurları gizler.

Ayrıca "önbellek etiketi tek sürümde olmalı" maddesi eklendi: karışık etiket yarım uygulanmış yama işaretidir ve tarayıcının bayat JavaScript çekmesine yol açar. Bu düzeltme hemen işe yaradı — `video.html`'in etiketinin v2450'de kaldığını yakaladı.

---

## 8. Kurulum betiğinde giderilen kusur

Kurulum betiği doğrulamayı **hedef dizin** üzerinde yapar. Kopyalama başarısız olduğu halde hedefte zaten doğru dosyalar varsa betik "YAMA UYGULANDI" diyordu; yama hiç uygulanmamış olmasına rağmen başarılı görünüyor ve kullanıcı eski kodla uçmaya devam ediyordu. Kopyalama artık ayrı bir kapı olarak tutulur ve eksik dosya doğrudan sonuca yansır.

---

## 9. Eski SQLite verisi

`gcs.db` dosyası **silinmedi** ve kurulum sırasında zaman damgalı yedek dizinine kopyalandı (500 MB üstündeyse atlanır ve uyarı verilir). Yeni PostgreSQL veritabanı **boş başlar**; daha önce "eski hiç bir veriye ihtiyacım yok" dediğiniz için otomatik veri aktarımı yapılmadı.

---

## 10. Paket içeriği

| Dosya | Durum |
|---|---|
| `goktungu/pg.py` | YENİ — PostgreSQL ağ geçidi |
| `goktungu/goc.py` | YENİ — göç motoru, şema sürümü 2451 |
| `js/pg_sihirbaz.js` | YENİ — 3 adımlı sihirbaz + göç ekranı |
| `sinav_2451_pg.py`, `dene_pg_ws.py` | YENİ — sınav ve canlı ölçüm |
| `goktungu/veritabani.py` | Kip anahtarı, yeni tablolar, `GROUP BY` düzeltmesi |
| `goktungu/sunucu.py` | 5 WS komutu, anlık ilerleme yayını |
| `goktungu/gorev.py`, `goktungu/tile_cache.py`, `goktungu/telemetri_tampon.py` | PG'ye taşıma, disk ikinci katmanı |
| `main.py` | Açılışta PG kipini açar, göç durumunu ölçer |
| `js/ws.js`, `js/i18n.js`, `js/kullanici.js`, `js/surum.js` | Yönlendirme, çeviriler, menü, sürüm |
| `css/stil.css` | `.pgs-*` sınıfları |
| `index.html`, `video.html`, `flight.html` | Betik etiketi, menü öğesi, önbellek v2451 |

Değişen dosya listesi tahminle değil, v2.4.50 tam paketiyle birebir karşılaştırmayla belirlendi.

`.pgs-perde` katmanı 9550'ye alındı. 9500'de bırakıldığında serbest form popup katmanıyla eşitti ve DOM sırasına göre popup sihirbazın önüne geçebiliyordu.

---

## 11. Sorun giderme

**Sihirbaz hiç açılmıyor.** Tarayıcıda Ctrl+Shift+R yapın. `js/ws.js` açılışta `pg_durum` sorar; bu dosya eski kalmışsa sihirbaz hiç tetiklenmez.

**"psycopg2 kurulu değil" uyarısı.** `pip3 install psycopg2-binary` çalıştırın. Sürücü olmadan sihirbaz açılır ancak bağlantı kuramaz.

**Bağlantı reddedildi.** PostgreSQL'in dinlediği adresi denetleyin. Uzak bir sunucuya bağlanıyorsanız `postgresql.conf` içinde `listen_addresses` ve `pg_hba.conf` içinde ilgili ağ izni gerekir.

**Şema güncellemesi yarım kaldı.** Programı yeniden başlatın; göç motoru defterden kaldığı yeri okur ve sürdürür.

**Harita boş görünüyor.** PostgreSQL erişilemiyor olabilir. Bu durumda disk katmanı devreye girer ve önceden indirilmiş karolar görünmeye devam eder; konsolda bağlantı uyarısı olup olmadığını denetleyin.
