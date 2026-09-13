# Yer İstasyonu 2 — Test Paketi (GÖKTUNGU v2.4.44 Faz 1–3)

ESP32-S3 kontrol panelinin (11 buton, 2 toggle, 2 joystick, 7 LED) protokolünü
doğrulamak için hazırlanan bağımsız test takımı. GCS'e entegre etmeden önce
donanımın doğru okunduğunu kanıtlar.

| Dosya | İşlev |
|---|---|
| `test_istasyon2.html` | Test sayfası — tek dosya, harici kütüphane/CDN **yok** |
| `kopru.py` | Gerçek donanım için seri port ↔ WebSocket köprüsü |
| `benzetici.py` | Donanım yokken ESP32 firmware'ini taklit eden benzetici |
| `sinav_protokol.py` | Protokolü `pyserial` ile ölçen otomatik sınav betiği |

Tek gereksinim: `pyserial` (GCS kurulumunda zaten var) ve `websockets`.

---

## 1. Gerçek donanımla kullanım (asıl senaryo)

ESP32-S3'ü USB ile bağlayın. Kart **iki port** olarak görünür; **UART/COM**
portunu seçin (native USB yalnız firmware yükleme içindir).

```
# 1) Portları listele
python kopru.py

# 2) Köprüyü başlat  (Windows örneği)
python kopru.py COM7 8765

# 3) Test sayfasını aç
#    test_istasyon2.html dosyasına çift tıkla
#    "Köprü (WebSocket)" seçili, adres: ws://localhost:8765 → Bağlan
```

Köprü portu bulamazsa 2 saniye arayla yeniden dener ve sayfada durum bildirir;
kart çıkarılıp takıldığında elle müdahale gerekmez.

### Alternatif: köprüsüz (Web Serial)
Sayfada **Web Serial** sekmesine geçip "Port Seç ve Bağlan" — Chrome/Edge'de
Python çalıştırmadan doğrudan porta bağlanır. Hızlı deneme için elverişlidir,
ancak GCS entegrasyonu köprü mimarisiyle yapılacaktır.

---

## 2. Donanım olmadan deneme (benzetici)

```
# WebSocket kipi — sayfa doğrudan bağlanır
python benzetici.py --ws 8765
# sayfada adres: ws://localhost:8765

# PTY kipi — gerçek seri port gibi davranır (Linux/macOS)
python benzetici.py --pty --otomatik
# konsola yazılan /dev/pts/N adresini kopru.py'ye verin
```

Benzetici, protokolün her kuralını uygular: 25 ms debounce, 40 birim joystick
eşiği, `PONG`'un düz metin olması, P8–P11/T1/T2 LED komutlarının sessizce yok
sayılması. Ayrıca joystick merkezine **kalıcı rastgele sapma** (2048±40) verir,
böylece kalibrasyon gerçekten sınanabilir.

---

## 3. Otomatik protokol sınavı

```
python benzetici.py --pty --otomatik      # /dev/pts/N adresini yazar
python sinav_protokol.py /dev/pts/4
```

Ölçtüğü başlıklar: JSON şeması ve kanal sayıları, tip farkı (T2 string /
diğerleri int), `PING`→`PONG`'un JSON olmaması, `LED_CMD` onayı, geçersiz
komutların sessizce yok sayılması ve bağlantının hayatta kalması, 40 birim
eşiğinin uygulanması, gövdenin daima tam durum olması.

**Son ölçüm: 31 sınav, 31 geçti, 0 kaldı.**

---

## 4. Sayfadaki bölümler

**Bağlantı** — Köprü/Web Serial seçimi, WebSocket adresi, bağlan/kes.

**Push Butonlar** — P1–P11 ızgarası. Sarı çerçeve LED'li (P1–P7), gri çerçeve
LED'siz (P8–P11); sağ üst köşedeki nokta o kanalın LED durumunu gösterir.
Basılı buton mavi yanar. Benzetici bağlıysa kutulara tıklamak fiziksel basmayı
taklit eder.

**Toggle Switch** — T1 (0/1) ve T2 (UP/CENTER/DOWN). Altındaki satır her mesajda
tip denetimi yapar: `T2=string ✓ · T1/P*=int ✓ · gövde tam durum (11/4/7) ✓`.

**Joystickler** — J1 ve J2 için canvas gösterim: dış daire tam sapma, sarı iç
daire 40 birim eşiği (ölü bölge), mavi nokta anlık konum. Altında ham değer
(0–4095) ve normalize değer (−1…+1).

**Kalibrasyon** — "Kalibre Et" o anki değerleri merkez kabul eder; normalize
hesabı bu merkeze göre yapılır. Protokol belgesi orta noktanın sabit 2048
varsayılmamasını şart koşuyor, bu yüzden kalibrasyon arayüzde açıkça yer alır.

**LED Denetimi** — Her LED kutusuna tıklamak `LED,Px,ON/OFF` gönderir; ALL ON /
ALL OFF ve PING düğmeleri vardır. **"LED,P8,ON dene"** düğmesi, LED'i olmayan
bir kanala komut gönderildiğinde **yanıt gelmemesinin doğru davranış** olduğunu
gösterir.

**Ham Akış** — Son 200 satır, renk kodlu: yeşil READY, turuncu LED_CMD, mavi
buton, mor toggle, gri joystick, sarı gönderilen komut. Dondur ve joystick
gizle seçenekleri vardır.

**Ölçüm** — Toplam mesaj, mesaj/sn, PING gecikmesi, gönderilen komut sayısı,
**bozuk satır** sayacı ve bağlı süre.

---

## 5. Protokolün doğru uygulandığı noktalar

| Kural | Uygulama |
|---|---|
| `PONG` düz metin, JSON değil | Gelen satır JSON parse'tan **önce** `PONG` mü diye denetlenir |
| Gövde daima tam durum | State komple overwrite edilir, alan alan merge yok |
| T2 string, diğerleri int | Her mesajda tip denetimi yapılır ve arayüzde gösterilir |
| Joystick merkezi 2048 varsayılamaz | Kalibrasyon düğmesi ve merkez gösterimi |
| 40 birim eşiği | Ölü bölge çizilir; ardışık eksen mesajları arası fark denetlenir |
| P8–P11/T1/T2 LED yok | Kanal ayrımı görsel; yok sayma davranışı denenebilir |
| Port düzgün kapatılmalı | Köprüde `try/finally`, sayfada `port.close()` |
| Bozuk satır toleransı | `try/catch` + bozuk satır sayacı |
