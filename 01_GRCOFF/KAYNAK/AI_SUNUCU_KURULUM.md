# GÖKTUNGU AI Sunucusu — Kurulum ve Bağlantı Kılavuzu

Bu kılavuz, GÖKTUNGU ana sunucusundan **ayrı bir bilgisayarda** çalışan AI
işlem sunucusunun (`ai_sunucu.py`) kurulumunu, başlatılmasını ve GÖKTUNGU
arayüzünden tanımlanmasını anlatır.

## 1. Mimari Özet

```
+-------------------+        HTTP (JSON)         +----------------------+
|  GÖKTUNGU Ana Sunucu |  <-----------------------> |  AI Sunucusu (işçi)  |
|  main.py          |   görev dağıtımı /izle     |  ai_sunucu.py        |
|  HTTP: 8000       |   sağlık yoklama /durum    |  HTTP: 8900          |
|  WS  : 8765       |   tespit callback /ai/...  |  (GX10, Windows PC)  |
+-------------------+                            +----------------------+
```

- Ana sunucu, kayıtlı AI sunucularını 5 saniyede bir yoklar (`GET /durum`),
  çevrimiçi/çevrimdışı durumunu ve yükünü izler.
- Kamera izlemesi başlatıldığında ana sunucu, **en düşük yüklü çevrimiçi**
  AI sunucusuna görevi atar (`POST /izle`). Kamera akışını (RTSP/MJPEG)
  doğrudan AI sunucusu açar.
- AI sunucusu tespitleri ana sunucuya geri bildirir
  (`POST http://ANA:8000/ai/tespit`, takip için `/ai/takip`).
- Ana sunucu kapanıp açılsa bile görevler otomatik geri yüklenir.

## 2. Gereksinimler (AI sunucusu makinesi)

| Bileşen | Zorunlu | Not |
|---|---|---|
| Python 3.9+ | Evet | Windows'ta python.org kurulumu yeterli |
| `opencv-python` + `numpy` | Evet | `pip install opencv-python numpy` |
| `opencv-contrib-python` | Önerilir | CSRT/KCF hedef takibi (tracking) için |
| `pytesseract` + Tesseract OCR | İsteğe bağlı | Plaka metni okuma için |
| GPU/CUDA | Hayır | Mevcut modeller CPU'da çalışır; GX10'da NVIDIA modu |

Kurulum (Windows PowerShell veya Linux terminal):

```bash
pip install opencv-python opencv-contrib-python numpy pytesseract
```

Gerekli dosyalar: paketten yalnızca **`ai_sunucu.py`** dosyasını ve varsa
**`ai_modeller/`** klasörünü (YuNet/SFace .onnx + plaka cascade) AI
makinesine kopyalayın. Model dosyaları eksik veya bozuksa işçi açılışta
resmi opencv_zoo deposundan **otomatik indirir**; internet yoksa ilgili
görev devre dışı kalır ama işçi çalışmaya devam eder (çökmez).

> **OneDrive uyarısı:** Paketi OneDrive altındaki bir klasöre açarsanız
> büyük model dosyaları "yalnızca bulutta" tutulabilir ve diskte
> placeholder olarak görünür — OpenCV bunları okuyamaz ("Can't read
> ONNX file" hatası). Çözüm: `ai_modeller` klasörüne sağ tıklayıp
> **"Her zaman bu cihazda tut"** seçin veya paketi OneDrive dışına
> (örn. `C:\goktungu`) açın. v2.4.5+ işçi bu durumda dosyayı otomatik
> yeniden indirip düzeltmeyi dener.

## 3. AI Sunucusunu Başlatma

### 3.1 Komut satırı parametreleri

Linux/macOS (satır devamı `\` yalnızca bash içindir):

```bash
python ai_sunucu.py --port 8900 --ad "GX10 AI" --tip nvidia \
                    --kapasite 8 --ana http://192.168.1.10:8000
```

Windows PowerShell'de `\` satır devamı **çalışmaz**; komutu tek satırda
yazın (veya satır devamı için `` ` `` backtick, cmd.exe'de `^` kullanın):

```powershell
python ai_sunucu.py --port 8900 --ad "GX10 AI" --tip cpu --kapasite 4 --ana http://192.168.1.10:8000
```

| Parametre | Varsayılan | Açıklama |
|---|---|---|
| `--port` | `8900` | İşçinin dinleyeceği HTTP portu |
| `--ad` | `CPU AI Sunucusu` | Arayüzde görünecek ad |
| `--tip` | `cpu` | `cpu` veya `nvidia` |
| `--kapasite` | `4` | Eş zamanlı işlenebilir kamera akışı sayısı |
| `--ana` | `http://127.0.0.1:8000` | **GÖKTUNGU ana sunucusunun** HTTP adresi (tespit/takip bildirimleri buraya gönderilir) |

### 3.2 Örnek: ASUS Ascent GX10 (Linux, NVIDIA)

```bash
cd /opt/goktungu
python3 ai_sunucu.py --port 8900 --ad "ASUS Ascent GX10" \
                     --tip nvidia --kapasite 16 \
                     --ana http://192.168.1.10:8000
```

Açılışta kalıcı çalışma için systemd örneği:

```ini
# /etc/systemd/system/goktungu-ai.service
[Unit]
Description=GOKTUNGU AI Islem Sunucusu
After=network.target

[Service]
ExecStart=/usr/bin/python3 /opt/goktungu/ai_sunucu.py --port 8900 \
  --ad "ASUS Ascent GX10" --tip nvidia --kapasite 16 \
  --ana http://192.168.1.10:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now goktungu-ai
```

### 3.3 Örnek: Windows PC (CPU)

```powershell
cd C:\goktungu
python ai_sunucu.py --port 8900 --ad "Windows CPU AI" --tip cpu ^
                    --kapasite 4 --ana http://192.168.1.10:8000
```

Açılışta otomatik başlatma için `baslat_ai.bat` oluşturup Görev
Zamanlayıcı'ya (Task Scheduler) "oturum açılışında" görevi olarak ekleyin:

```bat
@echo off
cd /d C:\goktungu
python ai_sunucu.py --port 8900 --ad "Windows CPU AI" --tip cpu --kapasite 4 --ana http://192.168.1.10:8000
```

> Not: Ana sunucuyla aynı makinede ayrıca bir işçi çalıştırmanıza gerek
> yoktur — GÖKTUNGU ana sunucusu, yerel CPU işçisini kendisi otomatik başlatır.

### 3.4 Doğrulama

Önce model dosyalarını doğrulayın (eksik/bozuksa otomatik indirir; v2.4.6+):

```bash
python ai_sunucu.py --model-kontrol
# [AI] Yuz tespit (YuNet): TAMAM (232589 bayt)
# [AI] Yuz tanima (SFace): TAMAM (38696353 bayt)
```

İnternet yoksa modelleri başka bir makinede indirip `ai_modeller/`
klasörüne kopyalayın:

| Dosya | Kaynak |
|---|---|
| `face_detection_yunet_2023mar.onnx` (~232 KB) | [opencv_zoo/face_detection_yunet](https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx) |
| `face_recognition_sface_2021dec.onnx` (~38 MB) | [opencv_zoo/face_recognition_sface](https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx) |

Sonra işçinin ayakta olduğunu AI makinesinde ve ana sunucu makinesinden
doğrulayın:

```bash
curl http://AI_MAKINE_IP:8900/durum
# {"ad": "...", "tip": "cpu", "yuk": 0, "kapasite": 4,
#  "akislar": [], "yuz_destegi": true}
```

`yuz_destegi: false` görürseniz yüz modelleri yüklenememiştir —
`--model-kontrol` çalıştırın; işçi yüz dışındaki görevlerle çalışmaya
devam eder ve ana sunucu yüz kayıt isteklerini bu işçiye göndermez
(v2.4.6+).

## 4. Ağ ve Güvenlik Duvarı

| Yön | Port | Açıklama |
|---|---|---|
| Ana sunucu → AI sunucusu | TCP 8900 | Görev dağıtımı ve sağlık yoklama |
| AI sunucusu → Ana sunucu | TCP 8000 | Tespit/takip bildirimleri (`--ana` adresi) |
| AI sunucusu → Kameralar | TCP 554 (RTSP) / 80-8080 (MJPEG) | Kamera akışları doğrudan AI makinesinden açılır |

- Windows'ta: Denetim Masası → Güvenlik Duvarı → Gelen Kural → TCP 8900'e izin.
- Linux'ta: `sudo ufw allow from ANA_SUNUCU_IP to any port 8900 proto tcp`
- AI makinesinin kameraların bulunduğu ağa (VLAN) erişebildiğinden emin olun.

## 5. GÖKTUNGU Arayüzünden Tanımlama

1. Yönetici hesabıyla giriş yapın.
2. Üst menüden **AI → Sunucular**'ı açın.
3. **Yeni Sunucu** formuna şunları girin:
   - **Ad**: örn. `ASUS Ascent GX10`
   - **Host**: AI makinesinin IP adresi, örn. `192.168.1.50`
   - **Port**: `8900` (başlatırken verdiğiniz `--port`)
   - **Tip**: `NVIDIA` veya `CPU`
   - **Kapasite**: işçiyi başlatırken verdiğiniz `--kapasite` ile uyumlu
4. **Ekle**'ye basın. 5-10 saniye içinde satırdaki LED yeşile döner
   (çevrimiçi) ve yük çubuğu görünür.

> Kurulumla birlikte iki kayıt hazır gelir: **ASUS Ascent GX10** (host'unu
> gerçek IP ile düzenleyin) ve **Windows/CPU AI Sunucusu** (yerel işçi,
> otomatik çalışır).

## 6. Kamera İzlemeyi Başlatma

1. **AI → Kayıtlı Lokasyonlar** veya **Kameralar** panelinden kamerayı
   düzenleyin ve **AI Görevleri** kutucuklarını işaretleyin:
   Kişi Tanıma, Araç Tanıma, Hava Aracı Tespit, İnsan Tespit,
   Kara Aracı Tespit.
2. **AI → Sunucular** penceresindeki **İzlemeler** bölümünden veya kamera
   satırındaki AI düğmesinden izlemeyi başlatın.
3. Görev otomatik olarak en uygun (çevrimiçi + en düşük yüklü) AI
   sunucusuna atanır. Web arayüzü kapatılsa bile tanıma sunucu tarafında
   devam eder ve loglanır.
4. Tespitler alt paneldeki **AI TESPİT** sekmesine, geçmişe
   (**AI → Tespit Geçmişi**) ve kamera drona bağlıysa aktif uçuş kaydına
   işlenir.

## 7. Sık Karşılaşılan Sorunlar

| Belirti | Neden | Çözüm |
|---|---|---|
| LED sürekli kırmızı | Ana sunucu 8900'e erişemiyor | Güvenlik duvarı, IP/port, işçinin çalıştığını `curl /durum` ile doğrulayın |
| İzleme başlıyor ama tespit gelmiyor | AI makinesi kamera akışına erişemiyor | AI makinesinden `ffplay rtsp://...` veya VLC ile akışı test edin |
| Tespit geliyor, foto/klip açılmıyor | Bildirimler ana sunucuya ulaşıyor ancak medya ana sunucu diskinde | Normaldir: foto/klip ana sunucuda `ai_kayitlar/` altında saklanır |
| Takip (angaje) başlamıyor | `opencv-contrib-python` eksik | AI makinesine `pip install opencv-contrib-python` |
| Windows'ta yüz tanıma yok | Model dosyaları eksik | `ai_modeller/` klasörünü AI makinesine kopyalayın veya internet bağlantısıyla başlatın (otomatik indirir) |
| `Can't read ONNX file` hatası | OneDrive placeholder / bozuk model dosyası | `ai_modeller` klasörüne "Her zaman bu cihazda tut" deyin veya dosyayı silin — işçi yeniden indirir (v2.4.5+) |
| `unrecognized arguments: \` hatası | PowerShell'de `\` satır devamı geçersiz | Komutu tek satırda yazın; çok satır için PowerShell'de backtick, cmd'de `^` |
| `Yüz kaydedilemedi: modeller yuklu degil` | Yüz kaydını işleyecek işçide YuNet/SFace modelleri yüklenememiş | İşçi makinesinde `python ai_sunucu.py --model-kontrol` çalıştırın; v2.4.6+ ana sunucu, yüz desteği olan başka işçi varsa isteği otomatik ona yönlendirir |

## 8. Ölçekleme

- Birden fazla AI sunucusu ekleyebilirsiniz; ana sunucu yükü otomatik
  dağıtır (en düşük `yük/kapasite` oranlı sunucu seçilir).
- Bir sunucu çevrimdışı kalırsa üzerindeki görevler, sunucu tekrar
  çevrimiçi olduğunda veya başka uygun sunucu bulunduğunda otomatik
  yeniden atanır.
- Kapasiteyi (eş zamanlı akış) donanıma göre belirleyin:
  4 çekirdek CPU ≈ 2-4 akış; GX10 sınıfı GPU ≈ 8-16 akış.
