# PRNFRM — GÖKKUBBE Yazıcı Filo Merkezi

**Gökkubbe Teknoloji Anonim Şirketi** için Creality **K2 Plus (Combo)** yazıcı filosunu
(hedef: 56 cihaz) yerel ağ üzerinden **tek merkezden izleyen** web tabanlı yazılım.

Yazıcılara müdahale gerekmez: stok Creality yazılımının yerel ağda sunduğu
**WebSocket 9999** arayüzü kullanılır (root, Moonraker, bulut yok). Garanti korunur.

| | |
|---|---|
| Kaynak | `14_PRNFRM/KAYNAK/` |
| Giriş | `python3 main.py --port 8090` |
| Testler | `12_TESTLER/PRNFRM/` |
| Bağımlılık | Python ≥ 3.11, `aiohttp ≥ 3.10` |
| Sürüm | `prnfrm/surum.py` → `SURUM` |

## Sürüm 0.1.0 — ne yapar

- **Ağ tarama sihirbazı:** makinedeki alt ağları listeler, seçilen CIDR'da 9999 portunu
  paralel yoklar, yanıt verenlere WebSocket ile kimlik (hostname, model) sorar; bulunanları
  ad ve grup vererek toplu ekler. Elle IP ile ekleme de vardır.
- **Canlı gösterge paneli:** her yazıcı için durum (basıyor / boşta / duraklatıldı /
  tamamlandı / hata / hazırlanıyor / çevrimdışı), dosya, ilerleme, katman, kalan süre,
  nozul/tabla/kabin sıcaklıkları. Durum sayaçları, arama, durum ve grup filtresi.
- **Ayrıntı paneli:** tüm alanlar, ham telemetri, yazıcıya özel olay geçmişi, düzenleme
  (ad, IP, port, grup, not, bağlantı etkin/kapalı), silme.
- **Temel komutlar:** duraklat, sürdür, durdur, ışık aç/kapat. (API'de ayrıca nozul,
  tabla, fan.)
- **Olay akışı:** bağlantı kuruldu/koptu, baskı başladı/bitti/duraklatıldı, hata,
  filament bitti. SQLite'a yazılır, arayüze anlık itilir.
- **Kalıcı kayıt:** `prnfrm.sqlite` (yazıcılar + olaylar). Sır içermez.

## Çalıştırma

```bash
cd 14_PRNFRM/KAYNAK
pip3 install -r requirements.txt
python3 main.py --port 8090          # http://<sunucu>:8090/
```

Ortam değişkenleri: `PRNFRM_HOST`, `PRNFRM_PORT`, `PRNFRM_VERITABANI`, `PRNFRM_LOG`.

Sunucu, yazıcılarla **aynı yerel ağda** (ya da 9999 portuna yönlendirilmiş bir ağda)
olmalıdır. Tarama için alt ağ en fazla /20 (4096 adres) olabilir.

### Donanımsız deneme (simülatör)

```bash
python3 araclar/sahte_yazici.py --adet 6      # 127.0.0.2 … 127.0.0.7 : 9999
python3 main.py --port 8090
# Arayüzde "Yazıcı Ekle" → CIDR 127.0.0.0/28 → Tara
```

Simülatör telemetri, kalp atışı ve `pause/stop/lightSw` komutlarını taklit eder.

### Testler

```bash
cd 12_TESTLER/PRNFRM
python3 -m unittest -v test_k2_protokol test_filo_uctan_uca
```

Uçtan uca test gerçek loopback soketleriyle sahte yazıcı kurar; 9999 doluysa
`PRNFRM_TEST_PORT` ile port değiştirilebilir.

## Mimari

```
prnfrm/
  k2_protokol.py   saf protokol: mesaj üretimi, çözümleme, durum türetme, özet  (G/Ç yok)
  k2_baglanti.py   yazıcı başına kalıcı WebSocket istemcisi, kalp atışı, yeniden bağlanma
  tarayici.py      alt ağ listesi, paralel port yoklama, kimlik sorgusu, Tarama işi
  veritabani.py    SQLite: yazicilar, olaylar
  olaylar.py       durum geçişi → olay; abone modeli (uyarı kanalları buraya takılır)
  filo.py          kayıt + bağlantı + tarama + olay orkestrasyonu, arayüz yayını (≤1/s/yazıcı)
  web.py           aiohttp: statik arayüz, REST API, /ws tarayıcı yayını
web/               index.html, css/stil.css, js/uygulama.js (bağımlılıksız)
araclar/sahte_yazici.py   K2 simülatörü
```

### REST API

| Uç | İşlev |
|---|---|
| `GET /api/surum` | ürün, sürüm, firma |
| `GET /api/yazicilar` | tüm yazıcılar + canlı özet + durum sayıları |
| `POST /api/yazicilar` | `{ad, ip, port?, grup?, notlar?}` |
| `POST /api/yazicilar/toplu` | `{yazicilar:[{ip, ad, port, model, hostname, grup}]}` |
| `GET/PUT/DELETE /api/yazicilar/{id}` | ayrıntı (+ham, +olaylar) / güncelle / sil |
| `POST /api/yazicilar/{id}/komut` | `{komut: duraklat\|surdur\|durdur\|isik\|nozul\|tabla\|fan, deger?}` |
| `GET /api/aglar` | makinedeki alt ağlar |
| `POST /api/tarama`, `GET /api/tarama`, `POST /api/tarama/iptal` | tarama işi |
| `GET /api/olaylar?limit=` | son olaylar |
| `WS /ws` | `anlik`, `yazici`, `yazici_silindi`, `olay`, `tarama` mesajları |

## K2 yerel protokolü (topluluk gözlemi)

Creality bu arayüzü belgelememiştir. Aşağıdakiler Home Assistant entegrasyonları
(`ha_creality_ws`, `creality_assistant`, `ha-creality-lan`) ve `creality-cfs-panel`
belgelerinden derlenmiştir; tamamı `prnfrm/k2_protokol.py` içinde tek yerde tutulur.

- Uç: `ws://<ip>:9999`, metin çerçeveleri, alt protokol `wsslicer`. Parola yoktur.
- Yazıcı JSON telemetri **iter**; yalnız değişen alanlar gelebilir → istemci birleştirir.
- `{"ModeCode":"heart_beat"}` gelince düz metin `ok` gönderilir; 40 sn sessizlik = kopuk.
- Veri isteği: `{"method":"get","params":{"ReqPrinterPara":1}}`, `{"boxsInfo":1}` (CFS).
- Komut: `{"method":"set","params":{"pause":1}}`, `{"pause":0}`, `{"stop":1}`,
  `{"lightSw":1}`, `{"nozzleTempControl":220}`, `{"bedTempControl":{"num":0,"val":60}}`,
  `{"fan":100}`.
- Alanlar: `hostname, model, modelVersion, state, deviceState, printFileName,
  printProgress, printLeftTime, printJobTime, layer, TotalLayer, nozzleTemp,
  targetNozzleTemp, bedTemp0, targetBedTemp0, boxTemp, targetBoxTemp, fanPct, lightSw,
  curFeedratePct, materialStatus, err{errcode,key}, boxsInfo`.
- **Doğrulanmalı:** `state` kod tablosu (0 boşta, 1 basıyor, 2 tamamlandı, 4 durduruldu,
  5 duraklatıldı). Durum türetme bu yüzden öncelikle dosya adı + ilerleme + pause
  sinyallerine dayanır; ham `state` arayüzde ayrıca gösterilir. İlk gerçek K2 Plus'ta
  ham telemetri panelden okunup tablo kesinleştirilmelidir.
- Firmware güncellemesi alan adlarını değiştirebilir; yalnız `k2_protokol.py` güncellenir.

Kamera: K2 ailesi WebRTC (`http://<ip>:8000/call/webrtc_local`); bu sürümde yok.

## Yol haritası

1. **Aktif uyarı sistemi:** `olaylar.OlayMerkezi.abone_ol` üzerinden e-posta / Telegram /
   web push / sesli uyarı kanalları; kural motoru (örn. "X dk çevrimdışı", "hata", "baskı
   bitti", "filament bitti"); sessize alma ve vardiya saatleri.
2. Gerçek K2 Plus ile alan/durum doğrulaması, CFS (boxsInfo) kutu-slot görünümü.
3. Kamera önizlemesi (WebRTC → go2rtc).
4. Kullanıcı girişi ve yetki (izle / komut ver), HTTPS.
5. Dosya gönderme ve baskı başlatma (HTTP yükleme + `opGcodeFile`), iş kuyruğu.
6. Geçmiş raporları: yazıcı kullanım oranı, baskı süreleri, hata sıklığı.
