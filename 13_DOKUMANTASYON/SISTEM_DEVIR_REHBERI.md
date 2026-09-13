# GÖKTUNGU Teknik Devir Rehberi

**Teslim anı:** 12 Eylül 2026 · **Güncel:** 13 Eylül 2026 (paket 2.5.23 / uygulama 2.4.153)  
**Amaç:** Bu belge, GÖKTUNGU kaynaklarını Claude Code, Gemini veya başka bir yetkin yazılım ajanının güvenli ve tutarlı biçimde devralabilmesi için hazırlanmıştır. Arşiv, çalışma verileri, şifreler, özel anahtarlar, müşteri veritabanı dökümleri ve kullanıcı logları hariç tutularak oluşturulmuştur.

> Bu arşiv bir **kaynak ve mühendislik teslimidir**. Çalışan üretim veritabanının kopyası, lisans sırları, TLS özel anahtarları veya Android imzalama anahtarları içermez. Bunlar mevcut işletim ortamında güvenli biçimde yönetilmelidir.

## 1. Resmi ürün adlandırması

| Kod | Resmi ad | İşlev | Ana kaynak konumu |
|---|---|---|---|
| **GRCOFF** | Offline Merkez | İnternetsiz/yerel merkez, yerel kamera ve yerel AI | `01_GRCOFF/KAYNAK/` |
| **GRCON** | Online Sunucu | Merkezi web, katalog, lisans ve sunucu hizmetleri | `02_GRCON/` |
| **BRDIMG** | Görüntü Köprüsü | Yerel görüntü kaynağı/işleme köprüsü | `03_BRDIMG/ORTAK_KOPRU_KAYNAGI/` |
| **BRDTLM** | Telemetri ve Radar Köprüsü | Telemetri/radar bağlantı köprüsü | BRDIMG ile ortak çekirdek, `04_BRDTLM/` |
| **BRDAND** | Android Köprü | Android telemetri köprü istemcisi | `05_BRDAND/KAYNAK/` |
| **BRDDJI** | Android DJI | Android DJI köprü istemcisi | `06_BRDDJI/KAYNAK/` |
| **GRCCMP** | Kurumsal/Müşteri Paneli | Lisanslı müşteri, paket ve kurum yüzü | `07_GRCCMP/KAYNAK/` |
| **GRCADM** | Yönetim Paneli | Operasyon ve katalog yönetimi | `08_GRCADM/KAYNAK/` |
| **GRCWEB** | Tanıtım Sitesi | Açık tanıtım, yardım ve yasal sayfalar | `09_GRCWEB/KAYNAK/` |

Bu kodlar dosya, klasör, sürüm notu, paket adı ve teknik iletişimde değişmeden kullanılmalıdır. Eski marka/dizin adları geriye uyumluluk, paket kimliği veya eski dağıtım geçmişi nedeniyle kaynakta görülebilir; bunları rastgele toplu yeniden adlandırmayın.

## 2. Mimari özeti

GRCON çevrimiçi merkezdir. Üretimde `goktungu-app` ve `goktungu-merkez` hizmetleri bulunur. GRCON, web arayüzünü, kurumsal/yönetim yüzlerini, sürüm kataloğunu, lisanslı paket teslimini ve PostgreSQL tabanlı merkezi veriyi sağlar. Aktif GRCON kaynakları `02_GRCON/APP`, `02_GRCON/MERKEZ_PYTHON` ve `02_GRCON` altındaki systemd tanımlarında yer alır.[1]

GRCOFF çevrimdışı merkezdir. Kendi makinesinde çalışır ve **BRDIMG zorunluluğu olmadan** yerel kamera kaydı, görüntüleme ve yerel AI çalıştırabilir. GRCOFF paket kaynakları `01_GRCOFF/KAYNAK` altında; son doğrulanmış Windows/Linux ikilileri `11_PAKETLER/GRCOFF_2.5.20` altında tutulur.[2]

BRDIMG ve BRDTLM ortak bir köprü çekirdeğini paylaşır. Bu nedenle aynı çekirdekte bir değişiklik yapılırken görüntü ve telemetri/radar davranışının birbirinden ayrıldığı servis katmanları dikkatle incelenmelidir. Kaynak kökü `03_BRDIMG/ORTAK_KOPRU_KAYNAGI`; BRDTLM klasörü aynı kaynak ilişkisini açıklar.[3]

GRCCMP, GRCADM ve GRCWEB GRCON’un web ağacından ayrıştırılmıştır. Ortak CSS/JS bağımlılığı olabileceğinden yalnızca bir panelde görünen dosyaları değiştirirken ortak dosya çağrılarını da kontrol edin.[4]

## 3. GRCOFF 2.5.20 değişiklik seti

GRCOFF 2.5.20 / uygulama sürümü 2.4.150, Windows ve Linux için yeniden üretilmiş ve imzalı katalogda yayımlanmıştır. Paketler aşağıdaki kullanıcı odaklı işlevleri kapsar.

| Alan | Tamamlanan davranış |
|---|---|
| Kamera paneli | Başlangıçta açılmış kamera paneli başlıktaki **X** ile ortak panel mekanizması üzerinden kapanır; görünürlük durumu korunur. |
| Ortak görüntüleyici | Kamera listesindeki **Play** ve haritadaki dron-kamera küçük önizlemesi aynı taşınabilir/yüzen görüntü penceresini açar. |
| Dron-kamera bağı | Mevcut `dron_uid` veri modeli korunmuş, kamera düzenleme formunda seçilebilir hale getirilmiş ve harita önizlemesi bu bağı kullanır. Yeni, paralel bir dron kimliği modeli oluşturulmamıştır. |
| Yerel AI | İşçi yerelde çalışır; yalnız **insan**, **kara_araci** ve **hava_araci** sınıfları kabul edilir. Yüz, plaka ve diğer sınıflar aktif tespit/takip yayını için reddedilir. |
| Pasif takip verisi | Manuel takip için olaylar yalnız yerel `veri/track_verisi.ndjson` dosyasına yazılır ve konsola `[TRACK]` önekiyle kaydedilir. Örnek `track_verisi_dinleyici.py` yalnız dosyayı okur/yazdırır. |

Pasif takip olayının kanonik alanları `surum`, `olay`, `ts`, `kamera_id`, `dron_uid`, `track_id`, `sinif`, `kutu_px`, `merkez_px`, `kare_boyutu`, `guven` ve `durum`dur. `durum` yalnız `aktif` veya `kayip` olmalıdır. Olay şemasına kontrol, aktüatör, joystick, komut veya ağ üzerinden fiziksel etki oluşturan alanlar eklenmemelidir.[5]

Fiziksel kamera, RTSP kaynağı, USB kamera, M50 veya gerçek dron bağlanarak test yapılmamıştır. Testler, statik denetim, yerel model durum kontrolü, sözleşme/regresyon kontrolü ve paket içeriği denetimi ile sınırlıdır.[6]

## 4. GRCON PostgreSQL aktarımı

GRCON PostgreSQL aktarım ve şema erişim kodu `02_GRCON/POSTGRESQL_AKTARIM/mk_depo.py` altında ayrıca verilmiştir; merkezi katmanın eşdeğer dosyaları `02_GRCON/MERKEZ_PYTHON/` içinde bulunur.[7]

Bir veritabanı aktarımı veya şema değişikliği öncesinde şu sıra uygulanmalıdır:

1. Hedef PostgreSQL sürümünü, ağ erişimini ve kimlik doğrulamayı doğrulayın.
2. Mevcut veritabanının tutarlı `pg_dump` yedeğini alın ve geri yüklemeyi ayrı ortamda deneyin.
3. Şema sürümü ile uygulama sürümünü birlikte doğrulayın; kayıt çatışması kurallarını ve `surumler` kataloğunu ayrı kontrol edin.
4. Üretimden önce, boş/sınırlı bir test veritabanında aktarımı ve uygulamanın açılış sorgularını çalıştırın.
5. Geçiş sonrasında paket kataloğu, lisans verisi ve kullanıcı kayıtları için sorgu tabanlı doğrulama yapın.

Veritabanı parolalarını, servis `Environment` sırlarını ve gerçek müşteri verilerini repoya ya da teslim ZIP’ine koymayın.

## 5. Paketleme ve yayın disiplini

GRCOFF üreticileri `01_GRCOFF/KAYNAK/deb_merkez_uret.py`, `setup_merkez_uret.py` ve `paketle_merkez.py` dosyalarıdır. Linux üretimi Debian paketini, Windows üretimi NSIS kurucusunu oluşturur. İki platform aynı kaynak değişiklik setini taşımalıdır.[8]

Bir yayın şu denetimler tamamlanmadan yapılmamalıdır:

| Kapı | Gerekli denetim |
|---|---|
| Kaynak | Python derleme denetimi, JavaScript sözdizim denetimi ve ilgili regresyonlar geçmelidir. |
| Paket | Linux paketi `dpkg-deb`, Windows paketi arşiv/PE denetimiyle incelenmeli; dinleyici, AI kaynakları ve gerekli arayüz dosyaları pakette görülmelidir. |
| Bütünlük | Her iki dosyanın SHA-256 değeri alınmalı, Ed25519 imzası katalogda doğrulanmalıdır. |
| Katalog | Doğru ürün `gcs`, sürüm, platform, `app_surum`, kanal ve dosya boyutu ile kayıt yapılmalıdır. |
| Erişim | Paket dizini servis hesabı için okunur/geçilebilir olmalı; depo dizinlerinde en az `0755` korunmalıdır. |
| İstemci | Güncelleme ucu Windows ve Linux için yeni sürümü ilk aday olarak döndürmelidir. |

GRCOFF 2.5.20 için yayımlanan paket doğrulama değerleri aşağıdadır.

| Platform | Dosya | SHA-256 | Katalog/App |
|---|---|---|---|
| Linux | `goktungu-merkez_2.5.20_all.deb` | `c0c29384b6231a3924316cc3b1c26e36d800f66f41808e543117b8fabe3aef79` | `2.5.20 / 2.4.150` |
| Windows | `GOKTUNGU-Merkez-Setup-2.5.20.exe` | `aa2a5a5fe4ef81887ff63e380ac36d107e4f2e0405f3aaefba6cc2c1c635d62e` | `2.5.20 / 2.4.150` |

## 6. AI ajanı için çalışma protokolü

Claude Code, Gemini veya başka bir ajan ilk olarak `00_BASLANGIC/README.md`, bu belge, `CLAUDE_CODE.md`, `GEMINI.md` ve kökteki `AGENTS.md` dosyalarını okumalıdır. Sonra değişiklik yapmadan önce ilgili ürünün kaynak ağacını ve mevcut testleri incelemelidir.

Değişiklikler küçük, geri alınabilir ve ürün sınırlarına uygun olmalıdır. GRCOFF’a ait yerel kamera/AI yüzeyi GRCON’a geri taşınmamalıdır. GRCON tarafında kamera menüsü veya offline yerel AI arayüzü yeniden etkinleştirilmemelidir. Katalog yayını, önce üretim dışı dosya/doğrulama ile tamamlanmalı; yayımdan sonra servis hesabı erişimi ve güncelleme ucu tekrar kontrol edilmelidir.

> Üretim değiştirilmeden önce yedek alın, değişiklik kapsamını dar tutun, testleri çalıştırın ve açık doğrulama kanıtı üretin. Çalışma verisini, sırları ve imza anahtarlarını kaynak kontrolüne eklemeyin.

## 7. Bilinen sınırlar ve açık işler

Bu teslim; GRCOFF 2.5.20’nin yerel kamera/AI/pasif takip kapsamını ve güncel kaynak devrini içerir. Gerçek saha kamera/dron testi, müşteri kurulumlarında performans testi ve uzun süreli yük testi bu teslimde yapılmamıştır. Android imza anahtarları bilerek arşivden çıkarılmıştır. BRDIMG/BRDTLM ortak köprü çekirdeği ve Android kaynakları erişilebilir haliyle arşive alınmıştır; paketler burada yalnız son örnek ikililer olarak bulunur.

## Kaynakça

[1]: ../02_GRCON/MERKEZ_PYTHON/main.py "GRCON merkez başlatıcı"
[2]: ../01_GRCOFF/KAYNAK/main.py "GRCOFF merkez başlatıcı"
[3]: ../03_BRDIMG/ORTAK_KOPRU_KAYNAGI/ "BRDIMG/BRDTLM ortak köprü kaynağı"
[4]: ../07_GRCCMP/KAYNAK/ "Kurumsal panel kaynakları"
[5]: ../01_GRCOFF/KAYNAK/goktungu/ai_yonetici.py "Yerel pasif takip yöneticisi"
[6]: ../12_TESTLER/GRCOFF/ "GRCOFF regresyon testleri"
[7]: ../02_GRCON/POSTGRESQL_AKTARIM/mk_depo.py "PostgreSQL katalog/aktarım katmanı"
[8]: ../01_GRCOFF/KAYNAK/paketle_merkez.py "GRCOFF ortak paket ağacı üreticisi"

---

## Ek: 13 Eylül 2026 güncellemesi (paket 2.5.21 → 2.5.23)

Bu teslimden sonra GRCOFF üç sürüm ilerledi ve GRCON tarafında iki canlı düzeltme yapıldı. Ayrıntı: `SURUM_NOTLARI.md`.

**GRCOFF (01_GRCOFF/KAYNAK):**
- **2.4.151 / paket 2.5.21** — yerel AI ile takip edilen hedefe operatör onaylı dron angajmanı; iki kamera tipi (sabit / drona takılı); hibrit mesafe kestirimi ve angajman kalibrasyonu.
- **2.4.152 / paket 2.5.22** — kamera formunda kaybolan **AI Görevleri** bölümü geri geldi; form açılır-kapanır bölümlere ayrıldı; sabit "2.5.19" sürüm kusuru giderildi (sürüm artık `goktungu/paket_surum.py` tek kaynağından okunur).
- **2.4.153 / paket 2.5.23** — GRCOFF Merkez **aynı zamanda AI sunucusudur**: yerel AI işçisi köprüsüz başlar, kendini `ai_sunucular`a kaydeder ve canlı görüntüye AI'ı doğrudan uygular. Hayalet örnek AI kayıtları kaldırıldı. Canlı yayın yalnız Merkez'in `/kamera/<id>` yolundan, loopback'e bağlı işçi anahtarıyla okunur.

- **2.4.154 / paket 2.5.24** — dron panelinde 'Kamera Başlat' düğmesi; canlı görüntü tek konumda (harita/yüzen/panel/tam ekran, `js/kamera_ai_panel.js`); sınıf başına (İnsan/Kara Aracı/Hava Aracı) tanıma aç-kapa + hassasiyet için açılır-kapanır Yapay Zeka Ayarları paneli. Yeni kamera alanı `ai_hassasiyet` (JSON) uçtan uca işçiye iletilir; varsayılan 50 = önceki davranış. GRCON değişmedi.

**GRCON (canlı düzeltmeler, 02_GRCON/MERKEZ_PYTHON):**
- `mk_sunucu.py` + `mk_kaba_kuvvet.py` — otomatik güncelleme paket indirme ucu eklendi: `POST /api/istemci/guncelleme_paket` (lisans/kurulum-kimliği doğrular, kaba kuvvet korumalı). Önceden uç yoktu; istemcinin "İndir ve doğrula" adımı 404 alıyordu.
- `07_GRCCMP/KAYNAK` (`uygulama.js`, `index.html`) — müşteri panelinde **"Lisans belgesini indir"** düğmesi (Abonelik ve Merkez Uygulama sayfaları). Belge `/api/firma/merkez_lisans` yanıtıdır; kurulum ve otomatik güncelleme bununla yetkilendirilir.

**Yeni araç/test konumları:**
- `10_ORTAK_ARACLAR/grcoff_2522_katalog_yayinla_*.py`, `grcoff_2523_katalog_yayinla_*.py`
- `10_ORTAK_ARACLAR/surum_yamalari/` — sürüm yamaları (kaynağa uygulanan, denetlenebilir dönüşümler)
- `12_TESTLER/GRCOFF/uctan_uca/` — yerel AI uçtan uca ve tarayıcı sınavları
- `12_TESTLER/GRCON/sinav_guncelleme_paket.py` — güncelleme ucu birim sınavı (18 vaka)

**Güvenlik notu (13 Eylül 2026):** Teslim ZIP'i bir dönem web kökünden erişilebilir durumdaydı ve içindeki test betiklerinde canlı parolalar vardı. Sızan tüm parolalar (uygulama DB, süper kullanıcı DB, iki panel hesabı) değiştirildi; arşiv web kökünden kaldırıldı; PostgreSQL yalnız yerel bağlantıya kapatıldı; bu depodaki test betikleri parolayı artık ortam değişkeninden okur. **Kaynağa parola/sır yazmayın.**

**Bilinen sınırlar:** Yerel AI tespiti hareket tabanlıdır (eğitilmiş sınıflandırıcı değil); sabit kamerada iş görür, hareketli kamerada yanlış alarm üretir. Merkez'in AI tespit kabul ucu (`/ai/tespit`) henüz kimlik doğrulamaz — angajman için kapatılmalıdır. Gerçek saha kamera/dron testi yapılmamıştır.
