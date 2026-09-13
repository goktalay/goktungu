# GÖKTUNGU Kurulum Rehberi

Bu belge **GRCOFF (Offline Merkez)** kurulumunu ve müşteri/lisans akışını anlatır. GRCON (çevrimiçi sunucu) kurulumu için bölüm 6'ya bakın.

GRCOFF, satın alan kurumun kendi bilgisayarında çalışır; kapalı devre (internetsiz) çalışabilir ve **köprü gerektirmeden** yerel kamera + yerel AI sağlar.

---

## 1. Sistem gereksinimleri

| | Windows | Ubuntu/Linux |
|---|---|---|
| Sürüm | Windows 10/11 x64 | Ubuntu 22.04+ (Debian 12 türevleri) |
| Python | **Gerekmez** — kuruluma gömülüdür | 3.10+ (paket bağımlılığı olarak kurulur) |
| Veritabanı | PostgreSQL 14+ (yerel veya uzak) | PostgreSQL 14+ (yerel veya uzak) |
| Disk | ~1 GB | ~700 MB |
| İnternet | Yalnız güncelleme ve ilk lisans indirmesi için; çalışma için gerekmez | Aynı |

AI ve görüntü işleme CPU ile çalışır. Uygun bir NVIDIA ortamı varsa yerel işçi GPU kipini seçebilir.

---

## 2. Paketi edinme

Kurumsal panele (**https://goktungu.com/company/**) kurum yöneticisi olarak girin → **Merkez Uygulama** → platformunuza uygun paketi indirin:

- Windows: `GOKTUNGU-Merkez-Setup-<sürüm>.exe`
- Ubuntu/Linux: `goktungu-merkez_<sürüm>_all.deb`

> Paket lisanslıdır ve yalnız oturum açmış kurum panelinden inilir. Doğrudan `/indir/` bağlantısı bilerek 403 döndürür.

İndirdikten sonra SHA-256 doğrulaması yapmanız önerilir; beklenen değer panelde ve sürüm notlarında yer alır.

```powershell
# Windows (PowerShell)
Get-FileHash .\GOKTUNGU-Merkez-Setup-<sürüm>.exe -Algorithm SHA256
```
```bash
# Linux
sha256sum goktungu-merkez_<sürüm>_all.deb
```

---

## 3. Kurulum

### Windows
1. Kurulumu **yönetici olarak** çalıştırın. (İmzasız kurulumdur; SmartScreen uyarısı çıkabilir → *Daha fazla bilgi → Yine de çalıştır*.)
2. Yazılım `GoktunguMerkez` adıyla bir **Windows servisi** olarak kurulur ve otomatik başlar.
3. Varsayılan konumlar:
   - Kurulum: `C:\Program Files\Goktungu\Merkez`
   - Veri: `C:\ProgramData\Goktungu\Merkez`
   - Arayüz: `http://127.0.0.1:8000/`

### Ubuntu/Linux
```bash
sudo apt install ./goktungu-merkez_<sürüm>_all.deb
```
- Servis: `goktungu-merkez` (systemd)
- Kurulum: `/opt/goktungu/merkez` · Veri: `/var/lib/goktungu-merkez`
- Arayüz: `http://127.0.0.1:8000/`
- PostgreSQL yerelde çalışacaksa `postgresql` önerilen bağımlılıktır; uzak sunucu da kullanılabilir.

---

## 4. İlk açılış

### 4.1 PostgreSQL bağlantısı
Arayüzü ilk açtığınızda **PostgreSQL kurulum sihirbazı** gelir. Sunucu adresi, kullanıcı, parola ve veritabanı adını girin; tablolar otomatik oluşturulur. Yerel bir veritabanı için örnek:
```bash
sudo -u postgres createuser --pwprompt goktungu
sudo -u postgres createdb -O goktungu goktungu
```
> Veritabanı parolasını yalnız sihirbaza girin; kaynağa veya paylaşılan dosyalara yazmayın.

### 4.2 Lisans belgesi (`merkez_lisans.json`)
Kurulum paketi lisans belgesini **içermez**. Belge kuruma özeldir ve kurulum ile otomatik güncellemeyi yetkilendirir.

1. Kurumsal panelde **Abonelik** ya da **Merkez Uygulama** sayfasında **"Lisans belgesini indir"** düğmesine basın → `merkez_lisans.json` iner.
2. Dosyayı veri dizinine koyun:
   - Windows: `C:\ProgramData\Goktungu\Merkez\merkez_lisans.json`
   - Linux: `/var/lib/goktungu-merkez/merkez_lisans.json`
3. Merkez servisini yeniden başlatın:
   ```bash
   # Linux
   sudo systemctl restart goktungu-merkez
   ```
   Windows'ta Hizmetler'den `GoktunguMerkez` servisini yeniden başlatın.

Belge Ed25519 ile imzalıdır ve **internet olmadan** doğrulanır. Lisanstaki yetkiler (AI, Radar, GCCDUAL) kurulumda da açık gelir. Lisans yoksa AI dahil bazı yetkiler kapalı sayılır.

---

## 5. Yerel AI (köprüsüz)

GRCOFF'ta Merkez **aynı zamanda AI sunucusudur**. Ayrı bir AI sunucusu veya köprü kurmanız gerekmez.

- Yerel AI işçisi Merkez ile birlikte başlar; **AI > Sunucular** ekranında **"GRCOFF Yerel AI"** olarak çevrimiçi görünür.
- Bir kameraya AI uygulamak için: **Kameralar** → kamerayı düzenleyin → **AI Görevleri** bölümünden görev seçin (İnsan, Kara Aracı, Hava Aracı) → kaydedin. Görev seçili kamerada izleme kayıt anında otomatik başlar; canlı görüntüde tespit kutuları çizilir.
- Angajman için **AI Angajman Kalibrasyonu** bölümünü doldurun. Kalibrasyon eksikse tespit edilen hedef angajman kuyruğuna **alınmaz** (bilinçli güvenlik kapısı).
- Portlar köprüyle çakışmaması için kaydırılmıştır: AI işçisi `8910`, MJPEG `8811` (köprü sırasıyla `8900`/`8801`'de kalır). Canlı görüntü yalnız Merkez'in `/kamera/<id>` yolundan, bu makineye özel bir işçi anahtarıyla okunur; dışarıya açılmaz.

> Yerel tespit hareket tabanlıdır (arka plan çıkarma + HOG). Sabit kamerada iş görür; sürekli hareket eden bir kamerada yanlış alarm üretir ve eğitilmiş bir sınıflandırıcı değildir. Ciddi angajman kullanımı için sonraki adım gerçek bir nesne tanıma modelidir.

---

## 6. Otomatik güncelleme

- Yeni sürüm yayınlandığında uygulama üst çubukta **"Yeni sürüm hazır"** uyarısı gösterir.
- **İndir ve doğrula** → paket, lisans belgesiyle yetkilendirilerek Merkez'den indirilir; SHA-256 ve Ed25519 imzası doğrulanır. **Güncellemeyi kur** ile kurulum uygulanır.
- Güncelleme için geçerli `merkez_lisans.json` gereklidir; bakım kapsamı biten kurum yeni sürüm alamaz ama kurulu sürüm çalışmaya devam eder.

---

## 7. GRCON (çevrimiçi sunucu) kurulumu — özet

GRCON üretim sunucusunda iki systemd servisi çalışır: `goktungu-merkez` ve `goktungu-app`. Servis tanımları `02_GRCON/SERVIS_TANIMLARI/` altındadır.

1. Kaynağı `/opt/goktungu` altına yerleştirin (`merkez`, `app`, `merkez/web`).
2. PostgreSQL'i kurun; **yalnız yerel bağlantıya** açın (`listen_addresses = 'localhost'`, `pg_hba.conf` dış erişim kapalı).
3. Servis parolalarını `/etc/goktungu/goktungu.env` içine koyun (`goktungu.env.example` şablonundan; dosya `root:root`, `0600`). Parolayı kaynağa yazmayın.
4. Servisleri etkinleştirin: `systemctl enable --now goktungu-merkez goktungu-app`.
5. TLS için `letsencrypt` sertifikaları kullanılır; sertifika yenileme zamanlayıcısı ayrıca yönetilir.

---

## 8. Sorun giderme

| Belirti | Olası neden / çözüm |
|---|---|
| Arayüz açılmıyor | Servis çalışmıyor olabilir. Linux: `systemctl status goktungu-merkez`. Windows: Hizmetler → `GoktunguMerkez`. |
| "PostgreSQL yapılandırması yok" | İlk açılış sihirbazını tamamlayın; `psycopg2` eksikse Linux'ta `pip3 install psycopg2-binary`. |
| AI görevi başlamıyor / "AI sunucusu yok" | Lisans belgesi eksik olabilir (AI kapalı sayılır). Belgeyi koyup servisi yeniden başlatın. `AI > Sunucular`'da "GRCOFF Yerel AI" çevrimiçi mi bakın. |
| İşçi günlüğü | Windows: `C:\ProgramData\Goktungu\Merkez\ai_isci.log` · Linux: `/var/lib/goktungu-merkez/ai_isci.log` |
| Güncelleme "lisans gerekli" hatası | `merkez_lisans.json` veri dizininde değil. Panelden indirip yerleştirin, servisi yeniden başlatın. |
| Kamera görüntüsü gelmiyor | `ffmpeg` kurulu mu (Linux önerilen bağımlılık); kamera URL'si ve protokolü doğru mu; kalem düğmesiyle formu kontrol edin. |
