"""
GOKTUNGU KOPRU — SURUM DEFTERI
============================
Kopru yaziliminin ve her sunucu servisinin BAGIMSIZ surum numarasi ve
degisiklik gecmisi burada tutulur. Merkeze bagimli degildir: paket
kullaniciya gittiginde gecmis de onunla birlikte gider.

Kural: bir servisin kodunda davranis degisikligi yapilirsa o servisin
surumu artirilir ve GECMIS listesine EN BASA yeni kayit eklenir.
Kopru cekirdegi (panel, ajan, oturum, ayar) degisirse KOPRU surumu artar.

Surum bicimi: MAJOR.MINOR.YAMA
  MAJOR: uyumsuz degisiklik (ayar bicimi, protokol)
  MINOR: yeni yetenek
  YAMA : kusur giderme
"""

# ---------------------------------------------------------------------
# KOPRU CEKIRDEGI
# ---------------------------------------------------------------------
KOPRU_SURUM = "1.7.18"
KOPRU_GECMIS = [
    {
        "surum": "1.7.18",
        "tarih": "2026-09-14",
        "notlar": [
            "YENI: M50 servisi SDK'nin geri kalanini destekler: aci okuma "
            "(GetAngleX/Y), on ayarlar (GetPresets/SetPreset/CallPreset/"
            "ClearPreset/ClearAllPreset), tarama/devriye (ControlScan) ve "
            "takip yetenegi (EnableTrackAbility). Merkez 2.4.188 Elektro-"
            "Optik paneli bu komutlari kopru uzerinden de kullanabilir.",
        ]
    },
    {
        "surum": "1.7.17",
        "tarih": "2026-09-14",
        "notlar": [
            "YENI: M50 gorunur/termal RTSP yayin adresi artik cihazin "
            "kendisinden (HVS_GetRtspUrl) otomatik okunur; operatorun "
            "elle RTSP adresi girmesi gerekmez. Elle girilmis adres "
            "yalniz SDK adres vermediginde kullanilir.",
            "DUZELTME: adres, Merkez'in kamera akisinin gercekten okudugu "
            "m50_ayarlar alanina yazilir; onceden yalniz durum ozetine "
            "gidiyor, 'bagli' gorunse de video gelmiyordu.",
        ]
    },
    {
        "surum": "1.7.16",
        "tarih": "2026-09-14",
        "notlar": [
            "DUZELTME: uretici SDK'sinin Hvs/datdefs.py dosyasi DLL "
            "dizinini calisma dizinine (cwd) gore `..\\bin` olarak "
            "hesapliyordu; bu yalniz ureticinin kendi demo klasor "
            "duzeninde dogruydu. Koprunun calisma dizini farkli oldugu "
            "icin M50 baglantisi \"[WinError 2] Sistem belirtilen "
            "dosyayi bulamiyor\" ile reddediliyordu. Yol artik dosyanin "
            "KENDI konumundan hesaplaniyor; calisma dizininden bagimsiz.",
        ]
    },
    {
        "surum": "1.7.15",
        "tarih": "2026-09-14",
        "notlar": [
            "M50 SERVISI GERCEKTEN CALISIR HALE GELDI. Onceki surumde "
            "servis_m50.py/m50_hvs.py koda girmisti ama pakette uretici "
            "SDK'sinin calisma-zamani ikilileri (HVideoSDK.dll, "
            "HVideoUtility.dll) ve Python baglayicisi (Hvs paketi) yoktu; "
            "M50 servisi panelde goruniyor ama her baglanti denemesi "
            "\"M50 Windows SDK bulunamadi\" ile reddediliyordu.",
            "kopru/m50_sdk/ altina uretici SDK'sinin dogrulanmis calisma-"
            "zamani kopyasi eklendi (bin/HVideoSDK.dll, "
            "bin/HVideoUtility.dll, Hvs/*.py). Kurulum ayrica SDK dizini "
            "belirtmeye gerek yok; m50_hvs.py bu yolu otomatik bulur.",
        ]
    },
    {
        "surum": "1.7.2",
        "tarih": "2026-09-11",
        "notlar": [
            "M50 ELEKTRO-OPTIK HIZMETI EKLENDI. Cihaz bağlantısı yalnız Windows x64 saha Köprüsünde, operatörün açıkça girdiği IP, port, kullanıcı ve geçici parola ile başlatılır; ağ keşfi, varsayılan hedef ve kendiliğinden bağlanma yoktur.",
            "M50 kontrol yüzü PTZ, lens, açı konumlandırma ve operatörün manuel dikdörtgen seçimine bağlı takip ile sınırlıdır. Otomatik hedef edinimi, silah, atış, angajman ve otonom hedef hareketi desteklenmez.",
            "Parola ve oturum verisi ayarlara, durum paketlerine veya günlüklere yazılmaz. Görünür/termal RTSP kaynakları yalnız operatör açıkça tanımladığında, gömülü kimlik bilgisi olmadan yerel video katmanına verilir.",
            "M50 hizmeti firma yetkisi yokken kapalı kalır. Merkez yalnız arındırılmış cihaz durumunu vekil eder; HVS SDK fiziksel cihaz oturumunu yalnız saha Köprüsü açabilir."
        ]
    },
    {
        "surum": "1.7.1",
        "tarih": "2026-09-11",
        "notlar": [
            "UYGULAMA ICI GUNCELLEME EKLENDI. Köprü açılıştan sonra arka planda imzalı güncelleme manifestini denetler; saha bağlantısı, telemetri ve veri akışı bekletilmez.",
            "Uygun yeni sürüm varsa panelin üstünde kırmızı güncelleme şeridi görünür. Şerit, sürüm notlarını ve paket indirme ilerlemesini gösteren yerel pencereyi açar.",
            "İndirme yalnız kayıtlı kurulum kimliğiyle yetkili API üzerinden yapılır. Ürün, platform, Ed25519 imzası ve SHA-256 özeti doğrulanmadan kurulum başlatılamaz.",
            "Kurulum mevcut yerel yönetici oturumu ve CSRF denetimi altında, kullanıcı açıkça onayladıktan sonra ayrı süreçte başlatılır. Ayarlar ve kurulum kimliği korunur."
        ]
    },
    {
        "surum": "1.7.0",
        "tarih": "2026-08-17",
        "notlar": [
            "TEKNIK KIMLIK GECISI TAMAMLANDI. Onceki surumlerde urun adi "
            "GOKTUNGU olmasina ragmen isletim sistemi seviyesindeki kimlikler "
            "hala eski adi tasiyordu; kullanici bunlarin da degismesini "
            "istedi. Degisenler: Debian paket adi gozcu-kopru -> "
            "goktungu-kopru, Windows servis adi GozcuKopru -> GoktunguKopru, "
            "Windows kayit anahtari, kurulum dizini $PROGRAMFILES64\\Gozcu "
            "-> \\Goktungu, veri dizinleri C:\\gozcu -> C:\\goktungu ve "
            "/opt/gozcu -> /opt/goktungu, ortam degiskenleri GOZCU_* -> "
            "GOKTUNGU_*, User-Agent GOZCU-Kopru -> GOKTUNGU-Kopru, ikon "
            "dosyalari gozcu.ico -> goktungu.ico. Toplam 724 degisim / 84 "
            "dosya",

            "KURULU SURUMDEN YUKSELTME: paket adi degistigi icin apt bu "
            "surumu yeni bir paket sayar. Eski gozcu-kopru paketi "
            "kaldirilmali, ardindan goktungu-kopru kurulmalidir. Windows "
            "tarafinda eski GozcuKopru servisi kaldirilmadan yeni surum "
            "kurulursa iki servis ayni portu dinlemeye calisir; kur.bat "
            "eski servisi tespit edip durdurur ve siler",

            "ESKI ALAN ADI BILINCLI KORUNDU: ayar.py icindeki _GOC_ESKI ve "
            "_GOC_ALAN_ESKI sabitleri gozcu.veilox.com.tr degerini icermeye "
            "devam ediyor. Bunlar goc kuralinin TANIMA listesidir: diske "
            "yazilmis eski adresi taniyip goktungu.com'a tasimak icin eski "
            "degeri bilmek zorunludur. Silinirse yukseltilen kurulumlar eski "
            "adreste asili kalir"
        ]
    },
    {
        "surum": "1.6.1",
        "tarih": "2026-08-17",
        "notlar": [
            "MERKEZ ADRESI GOKTUNGU.COM'A TASINDI. Kurulumda ekrana dolu "
            "gelen varsayilan merkez adresi eski alan adini gosteriyordu. "
            "1.6.0 paketleri 17 Agustos 01:21'de uretildi, alan adi gecisi "
            "07:58'de yapildi; marka gecisi pakete islendi ama alan adi "
            "gecisi islenmedi.",

            "SESSIZ KOPMA TEHLIKESI KAPATILDI. Eski alan adi yeni adrese "
            "HTTP 301 ile yonleniyor ama WEBSOCKET EL SIKISMASI "
            "YONLENDIRMEYI IZLEMEZ. Bu yuzden eski adresle yapilandirilmis "
            "bir kopru bugun calisiyor gorunur -- yalnizca eski alan adi "
            "AYAKTA oldugu icin. Eski adres kapatildigi gun baglanti hicbir "
            "hata mesaji vermeden kalici olarak kopardi.",

            "MEVCUT KURULUMLAR ICIN ALAN ADI GOCU EKLENDI. Yalnizca "
            "varsayilani degistirmek YETMEZ: kurulu kopruler merkez "
            "adresini DISKE yazmis durumda ve diskteki deger varsayilana "
            "ustun gelir. Yukseltmeden sonra kullanici 'guncelledim ama "
            "hala eski adres' derdi. Goc kurali hem portsuz hem :9443'lu "
            "eski adresi tasiyor.",

            "GOC SINIRI KASITLI OLARAK DAR TUTULDU. Yalniz BIZIM ontanimli "
            "alan adimiz tasinir; kullanicinin kendi sunucusuna yazdigi "
            "adres ASLA degistirilmez. Kapali devre kurulumlar (kendi "
            "merkez uygulamasini satin alan sirketler) ve yerel ag "
            "adresleri korunur. Dort ornekle sinandi: iki eski adres "
            "tasindi, bir yerel IP ve bir ozel alan adi degismedi.",

            "PANEL ARAYUZUNDE CELISKI GIDERILDI. Bulut satiri 'GOKTUNGU "
            "bulutu -- gozcu.veilox.com.tr uzerinde' yaziyordu: yeni marka "
            "ile eski adres ayni satirda. Adres alanlarinin ipuclari da "
            "yeni alan adina cekildi.",

            "PAKET KUNYELERI GUNCELLENDI: systemd birim belge baglantisi, "
            "Debian denetim dosyasi ana sayfasi, elle kurulum betigi ve "
            "Windows 'Programlar ve Ozellikler' kaydindaki adres.",

            "DEGISTIRILMEYENLER: `GOKTUNGU_KOPRU_VERI`, "
            "`GOKTUNGU_KOPRU_YEREL_IP`, `GOKTUNGU_KOPRU_KANAL_DIZIN` ortam "
            "degiskenleri, `goktungu-kopru` Debian paket adi ve servis adi. "
            "Bunlar marka degil kurulu sistemin kimligidir; degistirilmesi "
            "apt yukseltmesini bozar ve mevcut kurulumlari kirar.",
        ],
    },
    {
        "surum": "1.6.0",
        "tarih": "2026-08-17",
        "notlar": [
            "URUN ADI GOKTUNGU OLDU. Yazilimin adi eski adindan GOKTUNGU'ye "
            "gecti ve eski ad kullaniciya gorunen her yuzeyden kaldirildi: "
            "Windows denetim masasindaki kayit adi, Linux uygulama menusu "
            "girdisi ve aciklamasi, yerel panelin sekme basligi, ust "
            "seritteki marka yazisi ve Hakkinda penceresi. Firma logosu "
            "tumuyle kaldirildi; yalniz GOKTUNGU urun logosu kullaniliyor. "
            "Firma unvani artik YALNIZCA Hakkinda penceresindeki sahiplik "
            "satirinda gorunuyor.",
            "YUKSELTME YOLU BILINCLI OLARAK KORUNDU. Paket adi "
            "(goktungu-kopru), Windows servis adi (GoktunguKopru), kaldirma "
            "kayit anahtari, ayar kayit anahtari ve kurulum dizinleri "
            "DEGISMEDI. Bunlar marka degil KIMLIKTIR: paket adi "
            "degistirilse apt yukseltme yerine ikinci bir paket kurar ve "
            "iki servis ayni portu dinlemeye calisir; servis adi "
            "degistirilse eski servis sistemde asili kalir; kayit anahtari "
            "degistirilse onceki kurulum denetim masasindan kaldirilamaz "
            "hale gelir. Bu ayrim sayesinde mevcut kurulumlar bu surume "
            "dogrudan yukseltilir; yeniden kurulum gerekmez.",
            "PAKET KUNYESI GOKKUBBE OLARAK GUNCELLENDI. Windows "
            "kurulumunun yayimci alani, Debian paketinin Maintainer alani "
            "ve uygulama menusu aciklamasi Gokkubbe Teknoloji Anonim "
            "Sirketi kunyesini tasiyor. Kurulum dosyasi adi "
            "GOKTUNGU-Kopru-Setup olarak degisti; mavi urun ikonu ise "
            "kullanicinin acik istegi uzerine KORUNDU.",
        ],
    },
    {
        "surum": "1.5.8",
        "tarih": "2026-08-16",
        "notlar": [
            "ILK ACILISTA KURULUM SIHIRBAZI GELIYOR. Onceki surumlerde "
            "kopru dogrudan giris ekranini aciyordu ve merkez adresi "
            "yalnizca oturum ACILDIKTAN SONRA, ayarlar bolumunden "
            "girilebiliyordu. Kapali devre kurulumda bu KILITLI BIR "
            "DONGUDUR: kullanicinin yerel Merkez Uygulama hesabi vardir "
            "ama kopru hala bulut merkezine bakmaktadir, dolayisiyla o "
            "hesapla giris yapilamaz; adresi degistirmek icin ise giris "
            "yapmasi gerekir. Sihirbaz artik OTURUM ACILMADAN once "
            "cikiyor, merkez adresini ve baglanti bicimini soruyor, "
            "girilen adresi baglanmayi deneyerek DOGRULUYOR ve ancak "
            "dogrulandiktan sonra giris ekranina geciyor. Boylece "
            "kullanici ilk andan itibaren dogru merkeze -- kendi yerel "
            "sunucusuna -- baglanir.",
            "SIHIRBAZ UCLARI OTURUM DENETIMINDEN MUAF, ANCAK YALNIZCA "
            "KURULUM YAPILMAMISKEN. /api/kurulum/merkez ve "
            "/api/kurulum/dogrula uclari oturum gerektirmez -- "
            "gerektirseydi sihirbaz hicbir zaman calismazdi. Bu ucun "
            "surekli acik kalmasi ise koprunun merkez adresini oturum "
            "acmadan degistirmeye izin vermek olurdu; bu nedenle uclar "
            "merkez adresi bir kez kaydedildikten sonra KAPANIR. Panel "
            "durum ucu bu bilgiyi kurulum_gerekli alaniyla bildiriyor.",
            "PANELIN ADRES IPUCUNDA YANLIS PORT YAZIYORDU. Giris "
            "ekranindaki aciklama koprunun 8787 portunda dinledigini "
            "soyluyordu; gercek port 8790'dir. 8787, Merkez Uygulama ile "
            "ayni makinede calisma destegi eklenirken kaydirilmis eski "
            "degerdir ve metinde guncellenmesi atlanmisti. Kullaniciyi "
            "yanlis adrese yonlendiren bir metin, kusurun kendisi kadar "
            "zarar verir: kullanici baglanamayinca kurulumun bozuldugunu "
            "dusunur. Duzeltildi.",
            "YEREL MERKEZ UYGULAMASINA BAGLANMA KUSURU GIDERILDI. Kopru "
            "kendi sirketinin sunucusuna -- yani kapali devre calisan "
            "Merkez Uygulama'ya -- hic baglanamiyordu. Kok neden "
            "olculdu: kopru, WebSocket adresinden HTTP adresini "
            "uretirken yalnizca makine adini aliyor, PORT bilgisini "
            "dusuruyordu. Yerel merkez 8000 portunda dinlerken kopru "
            "80 portuna baglanmaya kalkiyor ve her cagri reddediliyordu. "
            "Kusur bulut kurulumunda GORUNMEZ, cunku bulutta port "
            "gercekten dusurulmelidir; bu yuzden aylarca farkedilmedi. "
            "Port artik yalnizca bulut merkezinin bilinen WebSocket "
            "portlari icin dusuruluyor, digerlerinde korunuyor.",
            "AYARLARDA YEREL MERKEZ ADRESI ICIN ORNEK EKLENDI. Adres "
            "alanina port yazilmadiginda baglanti sessizce reddediliyor "
            "ve arayuz bunun nedenini soylemiyordu. Kapali devre "
            "kurulumda kullanilacak dogru adres bicimi artik alanlarin "
            "hemen altinda ornekle gosteriliyor; kimlik bilgilerinin "
            "Merkez Uygulama'nin hangi bolumunden alinacagi da yaziyor.",
            "DURDURMA BUYRUGU ARTIK ANINDA ISLIYOR. Ajan, baglanti "
            "koptuktan sonra yeniden denemek icin bekleme suresine "
            "girer. Bu bekleme sirasinda verilen durdurma buyrugu "
            "bekleme bitene kadar goz ardi ediliyordu ve arada ajan bir "
            "kez daha baglanabiliyordu: operator koprunun durdugunu "
            "sanirken merkez onu CANLI goruyordu. Bekleme artik "
            "durdurma buyruguyla kesiliyor.",
            "GUNDUZ/GECE TEMASI EKLENDI. Ust seritteki gunes/ay dugmesi "
            "paneli acik ve koyu gorunum arasinda degistirir; dugme "
            "giris ekraninda da bulunur, boylece oturum acmadan once de "
            "secim yapilabilir. Ilk acilista isletim sisteminin gorunum "
            "tercihi izlenir, kullanici elle sectiginde kendi secimi "
            "gecerli olur ve tarayicida saklanir. KONSOL ZEMINI acik "
            "temada da KOYU kalir: konsol bir terminal ciktisidir ve "
            "hata kirmizisi, uyari sarisi gibi renkler acik zeminde "
            "okunmaz hale gelirdi.",
            "PANEL ONBELLEK ETIKETI ARTIK SURUMDEN URETILIYOR. 1.5.7'de "
            "etiket elle '?v=157' yapilmisti; her surumde elle "
            "guncellenmesi gerektigi surece atlanmasi kacinilmazdi ve "
            "sonucu sessiz bir kusurdur. Etiket artik dosya teslim "
            "edilirken kopru surumunden uretiliyor: kaynak dosyada hangi "
            "sayi yazili oldugu onemsizdir, guncellemeyi unutmak "
            "MUMKUN DEGIL.",
        ],
    },
    {
        "surum": "1.5.7",
        "tarih": "2026-08-16",
        "notlar": [
            "SURUM DEFTERININ USTUNE HAKKINDA BOLUMU EKLENDI. Defter "
            "zaten kopru cekirdegi ve her servis icin BAGIMSIZ yurutuluyordu; "
            "eksik olan, bilesenin kimligini tek bakista veren bastiktir. "
            "Pencere artik kurum logosunu, bilesen adini, surumu ve "
            "yayin tarihini, firma unvanini ve telifi gosteriyor. Tarih "
            "defterde ayri bir alan olarak TUTULMAZ; en yeni kayittan "
            "okunur, boylece iki yerde ayrisabilecek ikinci bir gercek "
            "kaynagi dogmaz.",
            "PANEL DOSYALARININ ONBELLEK ETIKETI SURUME BAGLANDI. Etiketler "
            "sabit '?v=2' ve '?v=3' idi: kopru guncellendiginde tarayici "
            "stil ve betik dosyalarini ONBELLEKTEN eski haliyle sunuyordu. "
            "Kusur sinsidir cunku sunucu tarafi dogru dosyayi teslim eder; "
            "kullanici yeni surumu kurdugu halde arayuz duzeltmelerini "
            "GORMEZ ve kusur giderilmemis sanilir. Etiket artik kopru "
            "surumunden uretilir (1.5.7 -> 157).",
        ],
    },
    {
        "surum": "1.5.6",
        "tarih": "2026-08-15",
        "notlar": [
            "SERVIS MENUSU ARTIK FIRMANIN YETKISINE GORE OLUSUYOR. "
            "Radar ve Yer Kontrol Istasyonu Dual satista degildir; "
            "yalnizca VEILOX ust yoneticisi sirket bazinda acar. "
            "Onceden bes servis herkese gorunuyordu; yetkisi olmayan "
            "bir kullanici bulunmayan bir modulu baslatmaya calisip "
            "anlamsiz hatalar aliyordu.",
            "SUZGEC ARAYUZDE DEGIL SUNUCUDA UYGULANIYOR. Menuyu "
            "gizlemek tek basina yetersizdir: /api/servis/baslat ucu "
            "dogrudan cagrilabilir. Yetkisiz servis icin baslatma "
            "istegi sunucuda reddedilir ve acilista otomatik baslatma "
            "da ayni suzgecten gecer. Boylece yetkisi kaldirilan bir "
            "firma, daha once kaydedilmis otomatik baslatma ayari "
            "yuzunden moduller acik kalmaz.",
            "SECILI SERVIS YETKISIZ KALIRSA PANEL BOS EKRANDA "
            "KILITLENMIYOR. Firma yetkisi kaldirildiginda kullanicinin "
            "o an actigi servis listeden dusuyordu; panel hicbir sey "
            "gostermeyen bir duruma dusuyordu. Artik ilk gecerli "
            "servise dusulur.",
            "MERKEZ SUNUCU SECIMI EKLENDI. Merkez Uygulama lisansi "
            "olan firmalar kendi sunucularini kurabildigi icin kopru "
            "ilk girişte hangi merkeze baglanacagini soruyor: VEILOX "
            "merkezi ya da firmanin kendi sunucusu. Secim kalicidir; "
            "lisansi olmayan firmaya soru hic gosterilmez.",
            "KOPRU VE MERKEZ UYGULAMA AYNI BILGISAYARDA BIRLIKTE "
            "CALISABILIYOR. Iki yazilim MJPEG vekili icin 8801, yerel "
            "AI iscisi icin 8900 portunu SABIT kullaniyordu; ayni "
            "makinede ikincisi sessizce baslamiyordu. Portlar artik "
            "ortam degiskeniyle kaydirilabilir. Gercek kurulumda "
            "olculdu: kopru 8790/8900, merkez 8000/8765/8811/8910.",
        ],
    },
    {
        "surum": "1.5.5",
        "tarih": "2026-08-15",
        "notlar": [
            "VIDEO SERVISI ARTIK ffmpeg'i PATH DISINDA DA BULUYOR. "
            "Kullanicinin bilgisayarinda ffmpeg kurulu olmasina ragmen "
            "servis 'ffmpeg bulunamadi' diyordu. Kok neden olculdu: "
            "kopru bir WINDOWS SERVISI olarak LocalSystem hesabiyla "
            "calisir ve o hesabin PATH degiskeni, kullanicinin oturum "
            "PATH'i DEGILDIR. Kullanici kendi konsolunda 'ffmpeg' "
            "yazip calistigini gorunce kusur kendisinde degil bizde "
            "araniyordu; bu, kusuru uzun sure gizleyen tam bir "
            "'bende calisiyor' ornegidir.",
            "ARAC BULUCU ARTIK OLAGAN KURULUM KONUMLARINI DA TARIYOR. "
            "Windows'ta Program Files, ProgramData, WinGet, Chocolatey, "
            "Scoop ve kullanici klasorleri; Linux'ta /usr/bin, "
            "/usr/local/bin, /snap/bin ve /opt taranir. Bulunan yol "
            "kalici olarak saklanir, boylece sonraki acilislarda arama "
            "yeniden yapilmaz.",
            "ARAC HICBIR YERDE BULUNAMAZSA KONSOLA KURULUM YONERGESI "
            "YAZILIYOR. Yalnizca 'bulunamadi' demek kullaniciyi "
            "cozumsuz birakiyordu: hangi araci, nereye, hangi komutla "
            "kuracagini ve servisi neden yeniden baslatmasi gerektigini "
            "bilmiyordu. Yonerge isletim sistemine gore uretilir ve "
            "kopyalanabilir komut icerir.",
            "OpenCV VE numpy GOMULU CALISMA ZAMANINA EKLENDI. Windows "
            "kurulumunda kullanicinin ayrica Python paketi kurmasi "
            "gerekmiyor; yerel USB kamera ve AI cizimi kurulumdan "
            "hemen sonra calisir. Onceden bu paketler yoktu ve yerel "
            "kamera hicbir kosulda acilamiyordu.",
            "VIDEO VEKILI DE AYNI BULUCUYA BAGLANDI. Servis ffmpeg'i "
            "bulsa bile vekil ciplak 'ffmpeg' komutunu cagirmaya devam "
            "ediyordu; bu, ayni kusurun ikinci bir yerde yasamasi "
            "anlamina geliyordu.",
        ],
    },
    {
        "surum": "1.5.4",
        "tarih": "2026-08-15",
        "notlar": [
            "RADAR SERVISI ARTIK KENDI BASINA HICBIR ADRESE BAGLANMIYOR. "
            "Onceki surumlerde servis acilista, merkezden hicbir komut "
            "gelmeden gomulu 192.168.8.186 adresine baglanmaya "
            "calisiyordu. Radar baska bir adreste ise bu, sahadaki BASKA "
            "bir cihaza TCP oturumu acma denemesi anlamina gelir. Servis "
            "artik yalnizca merkezden gelen 'bu adrese baglan' komutuyla "
            "baglanir.",
            "BAGLANILAN ADRES BU MAKINEDE SAKLANIYOR. Merkezden verilen "
            "adres kalici ayara yazilir; makine yeniden baslatildiginda "
            "ayni radara kendiliginden baglanir ve operatorun her "
            "acilista IP'yi yeniden yazmasi gerekmez. Bu, koda gomulu bir "
            "varsayim degil, operatorun daha once verdigi komuttur.",
            "'RADARI KES' KOMUTU BU KAYDI DA SILIYOR. Baglanti bilerek "
            "kesildiyse servis yeniden baslatildiginda ayni radara geri "
            "donmez; aksi halde kesme komutu kalici olmazdi.",
            "BOS ADRES ARTIK REDDEDILIYOR. Onceden bos adres sessizce "
            "gomulu varsayilana dusuyordu; artik hata olarak bildirilir. "
            "Sessiz varsayim, yanlis adresin sonucunu operatore kendi "
            "hatasi gibi gosteriyordu.",
            "GOKTUNGU_RADAR_IP ORTAM DEGISKENI DAVRANISI KORUNDU: elle "
            "tanimlanmissa acilista o adres kullanilir. Bu, koda gomulu "
            "bir varsayim degil, kurulumu yapanin bilincli tercihidir.",
        ],
    },
    {
        "surum": "1.5.3",
        "tarih": "2026-08-15",
        "notlar": [
            "TANI ARACI ARTIK PANELIN AG ADRESINI DE YAZIYOR. "
            "tani_sifirla.sh ozet bolumu yalnizca 127.0.0.1 adresini "
            "veriyordu; panel v1.5.2'den beri aga acik oldugu icin, ayni "
            "agdaki baska bir bilgisayardan veya tabletten girilecek "
            "gercek adres (ornek: http://192.168.1.40:8790/) de ayrica "
            "gosterilir. Kullanici adresi elle bulmak zorunda kalmaz.",
        ],
    },
    {
        "surum": "1.5.2",
        "tarih": "2026-08-15",
        "notlar": [
            "PANEL ARTIK AG UZERINDEN ACILABILIYOR. Yerel panel yalnizca "
            "kurulu oldugu bilgisayardan (127.0.0.1) erisilebiliyordu; "
            "artik varsayilan olarak tum ag arayuzlerini dinler "
            "(0.0.0.0), boylece ayni agdaki baska bir bilgisayardan veya "
            "tabletten de acilabilir. Kurulum sonunda ve servis "
            "gunlugunde erisilebilir gercek adresler yazilir.",
            "MEVCUT KURULUMLAR DA AGA ACILIR. Ayar dosyasinda 127.0.0.1 "
            "yazili olan kurulumlar yukseltmede otomatik olarak "
            "0.0.0.0'a tasinir. Elle baska bir adres yazilmissa "
            "(ornek: 192.168.1.50) o adres KORUNUR.",
            "AGA ACIK PANELDE KURULUM BILGISI SIZDIRILMIYOR. Panel aga "
            "acildigi icin, giris yapmadan sorulan durum bilgisinde "
            "kurulum kimligi, firma adi ve e-posta artik yalnizca ayni "
            "bilgisayardan gorunur; agdan bakan biri yalnizca merkez "
            "kaydinin var olup olmadigini gorur.",
            "KURULUMU BOZAN ESKI SERVIS KALINTISI TEMIZLENIYOR. Eski "
            "kur.sh ile kurulmus kullanici servisi ayni adi tasidigi "
            "icin yeni sistem servisiyle karisiyordu; kurulum artik onu "
            "otomatik devre disi birakir (silmez, .devredisi olarak "
            "saklar).",
            "KURULUM SESSIZ BASARISIZ OLMUYOR. Servis kaydi veya "
            "baslatma basarisiz olursa kurulum artik bunu acikca yazar "
            "ve inceleme komutunu bildirir.",
            "TANI/SIFIRLAMA ARACI KURULUMLA GELIYOR: "
            "/opt/goktungu/kopru/tani_sifirla.sh - servis olusmadiginda "
            "nedenini raporlar, --sifirla ile temiz kuruluma hazirlar.",
        ],
    },
    {
        "surum": "1.5.1",
        "tarih": "2026-08-14",
        "notlar": [
            "AI IZLEME ARTIK GERCEKTEN BASLIYOR. v1.5.0'da 'AI ile izle' "
            "komutu sessizce reddediliyordu: merkez goruntu adresini "
            "bildirmedigi icin (ki bildirmesi de yanlis olurdu, cunku "
            "merkezin adresi saha aginda gecersizdir) kopru komutu "
            "eksik sayiyordu. Adres artik bu makinenin kendi ag "
            "adresinden uretilir.",
            "AI IZLEMEYE ALINAN KAMERANIN GORUNTUSU ARTIK ACILIYOR. "
            "Onceden AI bilgisayarina izlenecek adres veriliyordu ama o "
            "adres yalnizca kamera akisi acikken goruntu uretir; akis "
            "acilmadigi icin AI bos ekran izliyordu. Izleme baslatilinca "
            "kameranin akisi da bu makinede otomatik acilir.",
        ],
    },
    {
        "surum": "1.5.0",
        "tarih": "2026-08-14",
        "notlar": [
            "KAMERALAR ARTIK BU MAKINEDEN ACILIYOR. Merkezdeki GOKTUNGU'ye "
            "eklenen saha kameralari (ornek: rtsp://192.168.8.20) "
            "goruntu vermiyordu; cunku baglantiyi MERKEZ SUNUCUSU "
            "kuruyordu ve o sunucu sizin yerel aginizi gormez. Kamera "
            "baglantisi artik BURADA kurulur ve goruntu yerel agda "
            "kalir; merkeze yalnizca akisin acik olup olmadigi bildirilir.",
            "BILGISAYARA TAKILI KAMERALAR ARTIK GORUNUYOR. 'Yerel "
            "kameralari tara' HER ZAMAN bos liste donduruyordu; cunku "
            "tarama merkez sunucusunda yapiliyordu ve o sunucuda kamera "
            "aygiti yok. Tarama artik bu makinede yapilir.",
            "AI IZLEME GOREVLERI ARTIK BURADAN ATANIYOR. Merkez, saha "
            "agindaki AI bilgisayarina (ornek: 192.168.8.50:8900) "
            "dogrudan istek atmaya calisip zaman asimina dusuyordu; bu "
            "yuzden AI sunucusu merkezde surekli 'yanit vermiyor' "
            "gorunuyordu. Yoklama ve gorev atama artik bu makineden yapilir.",
            "AI ISCISINE VERILEN GORUNTU ADRESI DUZELTILDI. Onceden "
            "merkezin kendi adresi veriliyordu ve saha iscisi o adrese "
            "erisemiyordu; zincir iki noktadan birden kopuyordu. Artik bu "
            "makinedeki yerel goruntu adresi verilir.",
            "BIR AI BILGISAYARI DUSERSE GOREVI DIGERINE TASINIR. Onceden "
            "kamera sessizce izlemesiz kalirdi ve operator bunu bilemezdi.",
            "KAMERA ACILAMAZSA SEBEBI YAZILIR. 'Goruntu gelmiyor' yerine "
            "sebep bildirilir: adres hatali, kimlik dogrulama gerekiyor, "
            "ffmpeg eksik ya da kaynak kare uretmiyor.",
            "YEREL USB KAMERA ICIN OpenCV GEREKIR. Kurulu degilse bos "
            "liste ile 'kamera yok' denmez; kurulum komutu bildirilir "
            "(pip install opencv-python-headless). Ag kameralari (RTSP, "
            "MJPEG) OpenCV olmadan da calisir.",
        ],
    },
    {
        "surum": "1.4.4",
        "tarih": "2026-08-14",
        "notlar": [
            "C20 RADARI ARTIK BU MAKINEDEN ISLETILIYOR. Merkezdeki "
            "GOKTUNGU'nun Radar Ayarlari paneli 'HATA / timed out' "
            "yaziyordu; cunku RADARA BAGLAN dugmesi radar adresini "
            "MERKEZ SUNUCUSUNDAN ariyordu. Radar ise sahadaki yerel aga "
            "baglidir (ornek: 192.168.8.168) ve internetten erisilemez. "
            "Baglanti artik BURADA kurulur.",
            "Radar protokolunun tamami bu makineye tasindi: oturum acma, "
            "kalp atisi, hedef izleri, RTK konumu, ayar okuma ve yazma. "
            "Merkez yalnizca sonucu gosterir.",
            "HEDEFLER ARTIK MERKEZE GONDERILIYOR. Onceki surumde radar "
            "servisi izleri yalnizca kendi konsoluna yaziyordu; merkeze "
            "hic gondermiyordu. Radar bagli gorunse bile haritada hedef "
            "cikmiyordu.",
            "IZ ZAMANI SAAT FARKINDAN BAGIMSIZ HALE GETIRILDI. Iz "
            "damgalari bu makinenin saatiyle uretilip merkezin saatiyle "
            "karsilastirilsaydi, iki makinenin saati kaymissa hedefler ya "
            "aninda silinir ya da hic silinmezdi. Izler artik gecen "
            "sureye gore tasinir.",
            "RADAR SUSTUGUNDA ESKI HEDEFLERIN KALMASI ONLENDI. Eskime "
            "denetimi yalnizca yeni veri geldiginde calisiyordu; radar "
            "kablosu cikarsa hic veri gelmez ve artik var olmayan "
            "hedefler ekranda kalirdi. Eskime artik zamana baglidir.",
            "Panelden radar adresi degistirildiginde mevcut baglanti "
            "kapatilip yenisi kurulur; ayarlar kalici olarak saklanir.",
        ],
    },
    {
        "surum": "1.4.3",
        "tarih": "2026-08-14",
        "notlar": [
            "YER ISTASYONU 2 (GCCDUAL CANTASI) ARTIK BU MAKINEDEN "
            "ISLETILIYOR. Merkezdeki GOKTUNGU'nun Yer Istasyonu 2 paneli "
            "'Port acilamadi (/dev/ttyACM0)' hatasi veriyordu; cunku "
            "panelin Baglan, Portlari tara, LED ve Kalibre dugmeleri "
            "MERKEZ SUNUCUSUNUN seri portunu aciyordu. Canta ise "
            "pilotun bilgisayarina takilidir. Bu komutlar artik kopruye "
            "gelir, seri port BURADA acilir ve canta verisi merkeze "
            "akitilir.",
            "Alt servislere komut gecirmek icin ic komut kanali eklendi. "
            "Seri portu iki surecin birlikte acmasi mumkun olmadigi "
            "icin panel/ajan dogrudan cihaza dokunmaz; komutu servise "
            "iletir ve yaniti okur.",
            "Canta kablosu cikarildiginda merkezin 'BAGLI' gostermeye "
            "devam etmesi onlendi: servis cantaya duzenli yoklama "
            "gonderir, yanit kesilirse kopukluk bildirilir ve cihaz "
            "geri takildiginda kendiliginden toparlanir.",
        ],
    },
    {
        "surum": "1.4.2",
        "tarih": "2026-08-14",
        "notlar": [
            "KUSUR GIDERILDI: SUNUCULAR BASLARKEN 'No module named kopru' "
            "HATASI VERIYORDU. v1.4.1 ile alt servisler dogru Python "
            "yorumlayicisiyla baslatilmaya baslandi, ancak yorumlayici bu "
            "kez kopru yaziliminin kendi dosyalarini bulamiyordu. Bes "
            "sunucu (Dron, AI, Video, GroundGCC, Radar) BASLAT dugmesine "
            "basildiginda aninda sonlaniyor ve konsola "
            "'ModuleNotFoundError: No module named kopru' dusuyordu.",
            "KOK NEDEN: KURULUMLA GELEN PYTHON YALITILMIS KIPTE CALISIYOR. "
            "Setup icine gomulen Python dagitimi, yanindaki yapilandirma "
            "dosyasi (python311._pth) nedeniyle CPython'un 'isolated' "
            "kipinde acilir. Bu kipte PYTHONPATH ortam degiskeni ve "
            "calisma dizini YOK SAYILIR; arama yollari yalniz o dosyadan "
            "okunur. Kopru, paket yolunu PYTHONPATH ile verdigi icin ayar "
            "hicbir etki yapmiyordu. Bu davranis Wine uzerinde gercek "
            "Windows ikilisiyle olculerek dogrulanmistir.",
            "ASIL DUZELTME: KURULUM KOKU ARTIK PYTHON YAPILANDIRMASINA "
            "YAZILIYOR. Gomulu calisma zamani hazirlanirken python311._pth "
            "dosyasina kurulum kokunu gosteren satir eklenir. Goreli yol "
            "kullanildigi icin kurulum dizini degistirilse veya baska bir "
            "surucuye tasinsa bile dogru calisir.",
            "IKINCI SAVUNMA: PAKET YOLU BASLATMA KOMUTUNA DA GOMULDU. "
            "Alt servis komutu artik paket kokunu dogrudan kendi icinde "
            "tasir ve modulu ayni baglamda kosturur. Boylece Python "
            "yapilandirmasi elle degistirilmis, eksik veya bozuk olsa da "
            "sunucular ayaga kalkar. Linux (.deb) kurulumunda kullanilan "
            "PYTHONPATH yolu KALDIRILMADI; iki isletim sistemi de "
            "desteklenmeye devam eder.",
            "KURULUM ARTIK KENDINI DENETLIYOR. Setup, dosyalari yazdiktan "
            "hemen sonra gercek yorumlayiciyla paket okuma denemesi yapar. "
            "Basarisiz olursa kurulum penceresinde denetlenecek dosyanin "
            "tam yolunu gosteren bir uyari cikar; kusur sahada aranmaz.",
            "SINAV: bes servisin tamami gercek kurulum duzeninde, bozuk "
            "PYTHONPATH ve farkli calisma dizini altinda dogrulandi; "
            "yapilandirma satiri bilerek silinerek ikinci savunmanin "
            "devreye girdigi de olculdu (25 denetim, kalansiz).",
        ],
    },
    {
        "surum": "1.4.1",
        "tarih": "2026-08-14",
        "notlar": [
            "KUSUR GIDERILDI: SERVIS KIPINDE HICBIR SUNUCU BASLAMIYORDU. "
            "v1.4.0 ile kopru gercek bir Windows servisi oldu; servisi "
            "baslatan surec 'python.exe' degil pywin32'nin barindiricisi "
            "'pythonservice.exe' oldugu icin alt servisler (Dron, AI, "
            "Video, GroundGCC, Radar) yanlislikla bu barindirici ile "
            "cagriliyordu. Barindirici bir yorumlayici DEGILDIR: kendi "
            "kullanim metnini basip cikis kodu 2 ile sonlaniyordu. "
            "Panelde 'Servis baslatildi / Servis sonlandi (cikis kodu 2)' "
            "dongusu goruluyor, hicbir sunucu ayaga kalkmiyordu.",
            "YORUMLAYICI ARTIK GUVENLI COZULUYOR. Alt servis komutu "
            "'sys.executable' degerine koru korune guvenmiyor; sirayla "
            "GOKTUNGU_KOPRU_PYTHON ortam degiskeni, barindirici olmayan "
            "sys.executable, barindiricinin yanindaki dizin, sys.prefix "
            "ve sys.base_prefix denenir. Hicbiri bulunamazsa panele "
            "anlasilir bir hata duser; sessiz 'cikis kodu 2' yerine "
            "nedenini soyleyen bir ileti gosterilir.",
            "SERVIS BASINDA YORUMLAYICI SABITLENIYOR. Windows servisi "
            "acilista yorumlayiciyi bir kez cozup GOKTUNGU_KOPRU_PYTHON'a "
            "yazar ve gunluge duser. Boylece hangi Python kullanildigi "
            "sahada belgelenir ve deger tum alt sureclere miras gecer.",
        ],
    },
    {
        "surum": "1.4.0",
        "tarih": "2026-08-14",
        "notlar": [
            "GERCEK KURULUM PROGRAMI (SETUP.EXE). Windows kurulumu artik "
            "cift tiklanan bir sihirbaz: 'GOKTUNGU-Kopru-Setup-1.4.0.exe'. "
            "Onceki surumde kurulum bir konsol betigi (kur.bat) idi; "
            "kullanici siyah bir pencere goruyor ve kurulumun bittigini "
            "anlamiyordu. Sihirbaz karsilama, lisans, dizin secimi, "
            "ilerleme ve bitirme adimlarindan olusur.",
            "GERCEK WINDOWS SERVISI. Kopru artik Windows Servis Denetim "
            "Yoneticisi'ne (SCM) kayitli: 'services.msc' listesinde "
            "'GOKTUNGU Kopru Yazilimi' olarak gorunur, Baslangic Turu "
            "'Otomatik (Gecikmeli)', hesap 'LocalSystem'. Windows'un "
            "kendi Baslat/Durdur/Yeniden Baslat dugmeleri calisir. "
            "Onceki surum Gorev Zamanlayici gorevi kuruyordu; bu bir "
            "servis DEGILDIR, services.msc'de gorunmez ve kurumsal "
            "servis izleme araclariyla denetlenemez.",
            "PYTHON ARTIK GEREKLI DEGIL. Python 3.11.9 ve tum bagimliliklar "
            "(websockets, pyserial, pywin32) setup icine gomuldu (40 MB). "
            "Kullanici ayrica Python kurmaz, surum catismasi olusmaz.",
            "SERVIS COKERSE KENDINI TOPARLIYOR: Windows kurtarma "
            "politikasi 5 sn / 10 sn / 30 sn gecikmelerle uc yeniden "
            "baslatma tanimlar (systemd Restart=on-failure karsiligi).",
            "SERVIS GUNLUGU. Servis olarak calisirken konsol cikisi hicbir "
            "yere gitmedigi icin gunluk iki hedefe yazilir: Windows Olay "
            "Gunlugu (yalniz uyari ve hatalar) ve "
            "'C:\\ProgramData\\Goktungu\\Kopru\\gunluk\\servis.log' "
            "(ayrintili akis, 5 MB'da dondurulur).",
            "UBUNTU ICIN .DEB PAKETI: 'apt install ./goktungu-kopru_1.4.0_"
            "amd64.deb' ile kurulur, 'apt remove' ile kaldirilir. Bagimli "
            "paketler (python3, python3-venv) apt tarafindan cozulur.",
        ],
    },
    {
        "surum": "1.3.0",
        "tarih": "2026-08-14",
        "notlar": [
            "GERCEK KURULUM PAKETI. Kopru artik isletim sistemine "
            "KURULUYOR: Windows'ta 'C:\\Program Files\\Goktungu\\Kopru', "
            "Linux'ta '/opt/goktungu/kopru'. Onceden arsiv nereye "
            "acildiysa oradan calisiyordu; kullanici klasoru tasidiginda "
            "ya da Indirilenler dizinini temizlediginde kurulum "
            "bozuluyordu.",
            "SERVIS OLARAK CALISIYOR. Windows'ta sistem baslangici gorevi "
            "(SYSTEM hesabi, oturum acilmadan baslar), Linux'ta systemd "
            "kullanici servisi (linger ile oturum kapaninca da yasar). "
            "Bilgisayar acildiginda kopru kendiliginden ayaga kalkar.",
            "BASLAT MENUSU VE MASAUSTU KISAYOLU. Ikisi de GOKTUNGU'nun mavi "
            "ikonunu tasiyor. Kisayol programi baslatmaz, yerel paneli "
            "TARAYICIDA acar: servis zaten calisiyor, ikinci ornek "
            "acilirsa port catismasi olusur.",
            "YERINDE YUKSELTME. Kurulum mevcut kurulumu algilar; yeniden "
            "kurmak yerine servisi durdurur, dosyalari gunceller, "
            "servisi yeniden baslatir. Sanal ortam, ayarlar ve merkez "
            "kimligi KORUNUR.",
            "PLATFORMA GORE AYRI PAKET: '-windows.zip' ve '-linux.tar.gz'. "
            "Onceden tek tar.gz iki isletim sisteminin betiklerini de "
            "tasiyordu; Windows kullanicisi tar.gz'i acmak icin ek "
            "program aramak zorunda kaliyordu.",
            "WINDOWS VERI DIZINI 'C:\\ProgramData\\Goktungu\\Kopru\\veri' "
            "oldu. Servis SYSTEM hesabiyla calistigi icin %APPDATA% "
            "System32 altina duser ve kullanici merkez kimligini "
            "goremez/yedekleyemezdi.",
            "Program Ekle/Kaldir kaydi eklendi: kopru artik Windows "
            "Ayarlar > Uygulamalar listesinden kaldirilabiliyor.",
            "Kaldirma betikleri eski surum artiklarini da temizliyor "
            "(Baslangic klasorundeki .vbs/.lnk, $HOME altindaki eski "
            "kurulum dizini).",
        ],
    },
    {
        "surum": "1.2.1",
        "tarih": "2026-08-14",
        "notlar": [
            "WINDOWS BASLATICI KUSURU GIDERILDI. Kurulum dizini Turkce "
            "karakter iceriyorsa (ornek: OneDrive\\Masaustu) kur.bat "
            "sonunda 'Sistem belirtilen yolu bulamiyor' (80070003) hatasi "
            "veriyordu. Neden: `chcp 65001` konsolu UTF-8'e aliyor, "
            "uretilen .vbs dosyasi UTF-8 yaziliyor, ancak wscript.exe "
            "BOM'suz .vbs dosyasini ANSI (kod sayfasi 1254) saniyor. "
            "'u' harfi UTF-8'de iki bayt, 1254'te tek bayt oldugu icin "
            "yol bozuluyordu.",
            "Baslaticiya artik YOL GOMULMUYOR: betik kendi konumunu "
            "WScript.ScriptFullName ile buluyor. Uretilen dosya saf "
            "ASCII oldugu icin kod sayfasindan etkilenmez; klasor "
            "tasinsa ya da yeniden adlandirilsa bile calisir.",
            "Baslangic klasorune .vbs KOPYASI yerine .lnk kisayolu "
            "konuyor. Kopya baska bir dizinde durdugu icin kendi "
            "konumunu kullanamaz; .lnk dosyalari ise yolu Unicode "
            "sakladigi icin kodlama sorunu yasamaz.",
            "Baslatici sanal ortami veya main.py'yi bulamazsa sessizce "
            "olmek yerine anlasilir bir ileti gosteriyor.",
            "kur.bat uretilen baslaticinin saf ASCII oldugunu kurulum "
            "sirasinda dogruluyor: kusur onceden sessizce olusuyor ve "
            "ancak bilgisayar yeniden baslatildiginda ortaya cikiyordu.",
            "kaldir.bat eski .vbs ve yeni .lnk baslangic kaydinin "
            "ikisini de temizliyor.",
        ],
    },
    {
        "surum": "1.2.0",
        "tarih": "2026-08-14",
        "notlar": [
            "AI SUNUCUSU SSH OTURUMLARI ARTIK KOPRUDE ACILIYOR. Onceden "
            "merkezdeki GOKTUNGU sureci SSH baglantisini kendi makinesinden "
            "kuruyordu; saha AI bilgisayarlari ozel agda (192.168.x.x) "
            "oldugu icin merkez o adrese hicbir kosulda erisemiyor ve "
            "baslat dugmesi calismiyordu.",
            "Yeni ajan eylemleri: ai_ssh_baslat, ai_ssh_durdur, "
            "ai_ssh_gecmis, ai_ssh_durum.",
            "Konsol satirlari koprude tamponlanir; merkez acik konsol "
            "penceresi icin yoklar.",
            "SSH sifresi koprude DISKE YAZILMAZ; yalniz oturum suresince "
            "bellekte tutulur.",
        ],
    },
    {
        "surum": "1.1.1",
        "tarih": "2026-08-14",
        "notlar": [
            "Kopru merkeze artik KENDI surumunu bildiriyor. Onceden "
            "merkez GCS'nin surum numarasi (2.4.53) bildiriliyordu; "
            "guncelleme denetiminde 2.4.53 ile gercek kopru surumu "
            "kiyaslandigi icin kopru kendini kalici olarak guncel "
            "saniyor ve GUNCELLEME HIC INMIYORDU.",
            "Surum tek kaynaktan okunuyor (surumler.py); ayar.py'deki "
            "elle yazilan ikinci kaynak kaldirildi.",
        ],
    },
    {
        "surum": "1.1.0",
        "tarih": "2026-08-14",
        "notlar": [
            "Ucus baglantilari artik merkezdeki GOKTUNGU'ye kopruleniyor: "
            "seri/UDP/TCP ham MAVLink baytlari WSS uzerinden tasinir.",
            "Panelde ACIK UCUS KANALLARI tablosu: kaynak, akis durumu, "
            "iki yonlu bayt sayaci ve son veri saati.",
            "KESINTI TAMPONU: merkez erisilemezken ham ucus verisi "
            "diske yazilir, atilmaz; baglanti donunce canli akis surer.",
            "Dron sayisi gercek acik kanal sayimina baglandi; onceden "
            "her zaman 0 bildiriliyordu.",
        ],
    },
    {
        "surum": "1.0.1",
        "tarih": "2026-08-13",
        "notlar": [
            "Panel konsolunda her satirin IKI KEZ gorunmesi giderildi: "
            "servis secimi ile yoklama turu ayni anda istek acabiliyordu.",
            "Konsol istekleri servis basina sirali; bayat yanit atilir.",
        ],
    },
    {
        "surum": "1.0.0",
        "tarih": "2026-08-13",
        "notlar": [
            "Ilk surum: yerel web paneli, merkez kimligiyle giris.",
            "Bes sunucu servisi yonetimi (baslat/durdur/konsol).",
            "Merkeze ters WebSocket ajani; nabiz ve sorgu yanitlari.",
            "443 portu ontanimli; erisilemezse 9443'e dusme.",
            "Kurum logosu ve unvani merkezden cekilip panelde gosterilir.",
        ],
    },
]

# ---------------------------------------------------------------------
# SERVIS SURUMLERI
# Anahtarlar servisler.py icindeki servis adlariyla BIREBIR ayni olmali.
# ---------------------------------------------------------------------
SERVIS_SURUMLERI = {
    "dron": "1.0.0",
    "ai": "2.0.2",
    "video": "2.0.1",
    "gcsdual": "1.1.0",
    "radar": "2.1.0",
}

SERVIS_GECMIS = {
    "dron": [
        {
            "surum": "1.0.0",
            "tarih": "2026-08-13",
            "notlar": [
                "Seri/UDP/TCP ucus kontrolcusu koprulemesi.",
                "Anlamsiz cekirdek portlari (ttyS*) listeden suzuluyor.",
                "Ucus verisi merkeze ham bayt olarak tasinir; MAVLink "
                "cozumlemesi ve telemetri kaydi MERKEZDE yapilir.",
            ],
        },
    ],
    "ai": [
        {
            "surum": "2.0.2",
            "tarih": "2026-08-15",
            "notlar": [
                "AI CIZIMI ICIN GEREKEN OpenCV ARTIK KURULUMLA BIRLIKTE "
                "GELIYOR. Onceden kullanicinin ayrica Python paketi "
                "kurmasi gerekiyordu; kurmadiginda tespit kutulari "
                "sessizce cizilmiyordu.",
                "ARAC ARAMASI ORTAK BULUCUYA BAGLANDI: servis PATH'i "
                "yoksun bir hesapla calissa bile araclar bulunur.",
            ],
        },
        {
            "surum": "2.0.1",
            "tarih": "2026-08-14",
            "notlar": [
                "IZLEME KOMUTU ARTIK REDDEDILMIYOR. Merkez goruntu "
                "adresini bildirmedigi icin komut eksik sayiliyordu; "
                "adres artik bu makinenin ag adresinden uretilir.",
                "IZLENECEK KAMERANIN AKISI OTOMATIK ACILIYOR. AI "
                "bilgisayari, akisi kapali bir kamerayi izlemeye "
                "calisip bos ekran goruyordu.",
            ],
        },
        {
            "surum": "2.0.0",
            "tarih": "2026-08-14",
            "notlar": [
                "AI IZLEME GOREVLERI ARTIK BU MAKINEDEN ATANIYOR. Merkez "
                "'izlemeyi baslat' dedigi anda AI bilgisayarina istek "
                "BURADAN gider. Onceden istek merkez sunucusundan "
                "gidiyordu; AI bilgisayarlari sahadaki yerel agda "
                "oldugu icin merkez o adrese erisemiyor ve istek zaman "
                "asimina dusuyordu.",
                "SAGLIK YOKLAMASI DA BURADAN YAPILIYOR. Merkezden "
                "yoklanan AI sunuculari erisilemedigi icin panelde "
                "surekli 'yanit vermiyor' gorunuyordu.",
                "AI ISCISINE VERILEN GORUNTU ADRESI ARTIK YEREL. "
                "Onceden merkezin goruntu adresi veriliyordu ve isci o "
                "adrese erisemiyordu; boylece izleme atanmis gorunse "
                "bile hicbir kare islenmiyordu.",
                "YUK DENGELEMESI: yeni gorev, kapasitesi dolmamis ve en "
                "az yuklu cevrimici isciye verilir.",
                "BIR ISCI DUSERSE GOREVLERI BASKA ISCIYE TASINIR. "
                "Onceden kamera sessizce izlemesiz kalirdi.",
                "AI tespit kutulari, uzerine cizilmek uzere video "
                "servisine iletilir; cizim de sahada yapilir.",
            ],
        },
        {
            "surum": "1.1.0",
            "tarih": "2026-08-14",
            "notlar": [
                "UZAK AI BILGISAYARLARI ARTIK BURADAN BASLATILIYOR. "
                "Merkezdeki GOKTUNGU 'baslat' dedigi anda SSH oturumu bu "
                "makinede acilir; ozel ag adresleri (192.168.x.x) boylece "
                "erisilebilir hale gelir.",
                "Oturum konsolu koprude tamponlanir (son 500 satir) ve "
                "merkezin acik konsol penceresine yoklanarak akitilir.",
            ],
        },
        {
            "surum": "1.0.0",
            "tarih": "2026-08-13",
            "notlar": [
                "Yerel AI iscisi; goruntu isleme istekleri karsilanir.",
                "Model dizini ayardan okunur; yoksa uyari verip bekler.",
            ],
        },
    ],
    "video": [
        {
            "surum": "2.0.1",
            "tarih": "2026-08-15",
            "notlar": [
                "ffmpeg ARTIK PATH DISINDA DA BULUNUYOR. Servis "
                "LocalSystem hesabiyla calistigi icin kullanicinin "
                "oturum PATH'ini gormuyor; kurulu bir ffmpeg 'yok' "
                "sayiliyordu. Olagan kurulum konumlari taranir ve "
                "bulunan yol saklanir.",
                "ARAC YOKSA KONSOLA KURULUM YONERGESI YAZILIYOR: hangi "
                "araci hangi komutla kuracagi ve servisi neden yeniden "
                "baslatmasi gerektigi bildirilir.",
                "YEREL USB KAMERA ICIN GEREKEN OpenCV KURULUMLA BIRLIKTE "
                "GELIYOR; ayrica paket kurulmasi gerekmez.",
            ],
        },
        {
            "surum": "2.0.0",
            "tarih": "2026-08-14",
            "notlar": [
                "KAMERA BAGLANTILARI ARTIK BU MAKINEDE ACILIYOR. "
                "Merkezdeki GOKTUNGU'ye eklenen saha kameralari goruntu "
                "vermiyordu; cunku akisi merkez sunucusu aciyordu ve o "
                "sunucu sahadaki yerel agi gormez. Yalnizca internete "
                "acik kameralar calisiyordu.",
                "GORUNTU YEREL AGDA KALIR. Merkeze kare gonderilmez, "
                "yalnizca akisin acik olup olmadigi, izleyici sayisi ve "
                "kare sayaci bildirilir. Kareyi merkeze tasimak kiraci "
                "basina megabit olceginde bant genisligi gerektirirdi.",
                "YEREL (USB) KAMERA TARAMASI BU MAKINEDE YAPILIYOR. "
                "Onceden merkez sunucusunda taraniyordu ve orada kamera "
                "aygiti olmadigi icin liste HER ZAMAN bos donuyordu.",
                "ACILAMAYAN KAYNAK SESSIZ KALMIYOR: sebep panele "
                "bildirilir (adres, kimlik dogrulama, ffmpeg eksik, "
                "kare uretilmiyor).",
                "AI TESPIT KUTULARI KARELERE BURADA CIZILIR; kutulari "
                "merkeze getirip cizmek, kareyi de merkeze getirmeyi "
                "gerektirirdi.",
                "Yerel MJPEG vekili 8801 portunda yayin yapar; ayni "
                "kamerayi birden fazla izleyici tek baglantiyla paylasir.",
            ],
        },
        {
            "surum": "1.0.0",
            "tarih": "2026-08-13",
            "notlar": [
                "Kamera akislari (RTSP/MJPEG) yerel vekil uzerinden sunulur.",
                "ffmpeg yoksa nedeni yazip yeniden dener.",
            ],
        },
    ],
    "gcsdual": [
        {
            "surum": "1.1.0",
            "tarih": "2026-08-14",
            "notlar": [
                "MERKEZDEN UZAKTAN YONETIM. Seri port acma/kapama, port "
                "listesi, LED denetimi ve kalibrasyon artik merkezdeki "
                "Yer Istasyonu 2 panelinden istenebilir; islem bu "
                "makinede yapilir. Onceki surumde canta yalnizca ayar "
                "dosyasinda yazili portla ve yalnizca acilista "
                "baglanabiliyordu.",
                "Baglanti sayaclari (alinan, gonderilen, yoklama yaniti, "
                "bozuk paket) ve yoklama gecikmesi olculup merkeze "
                "bildiriliyor; panel bu degerleri gosterir.",
                "Canta sessizlesirse (kablo cikti, cihaz kilitlendi) "
                "baglanti kopuk sayilir. Onceden port acik kaldigi "
                "surece baglanti canli sanilirdi; pilot calismayan bir "
                "panelde dugmeye basabiliyordu.",
                "Ek joystick takimlari (J3/J4) saptanip merkeze "
                "bildiriliyor; dron kumanda kollari icin kullanilir.",
            ],
        },
        {
            "surum": "1.0.1",
            "tarih": "2026-08-13",
            "notlar": [
                "Elle verilen port bulunamazsa otomatik taramaya dusulur "
                "(canta /dev/ttyACM0 yerine ACM1'e takildiginda da bulunur).",
            ],
        },
        {
            "surum": "1.0.0",
            "tarih": "2026-08-13",
            "notlar": [
                "GCCDUAL cantasi seri baglantisi; JSON dugme/joystick akisi.",
                "Cihaz cikarilirsa cokmez, nedeni yazip yeniden baglanir.",
            ],
        },
    ],
    "radar": [
        {
            "surum": "2.1.0",
            "tarih": "2026-08-15",
            "notlar": [
                "SERVIS ARTIK KOMUT BEKLEMEDEN HICBIR ADRESE BAGLANMIYOR. "
                "Onceki surumde acilista gomulu 192.168.8.186 adresine "
                "baglanmaya calisiyordu. Radar baska bir adreste ise bu, "
                "saha agindaki BASKA bir cihaza TCP oturumu acma "
                "denemesidir. Baglanti yalnizca merkezden gelen 'bu "
                "adrese baglan' komutuyla kurulur.",
                "MERKEZDEN VERILEN ADRES KALICI OLARAK SAKLANIYOR. "
                "Yeniden baslatmada ayni radara kendiliginden baglanir; "
                "bu, koda gomulu bir varsayim degil operatorun daha once "
                "verdigi komuttur. 'Kes' komutu kaydi siler.",
                "BOS ADRES REDDEDILIYOR: sessizce varsayilana dusmek "
                "yerine hata bildirilir.",
                "Durum paketine 'radar_adres_bekleniyor' alani eklendi; "
                "merkez, adres verilmedigi icin baglanti olmadigini "
                "cihaz arizasindan ayirt edebilir.",
            ],
        },
        {
            "surum": "2.0.0",
            "tarih": "2026-08-14",
            "notlar": [
                "RADAR ARTIK GERCEKTEN BU MAKINEDEN ISLETILIYOR. Onceki "
                "surum yalnizca sabit bir adrese baglanip izleri kendi "
                "konsoluna yaziyordu; merkezdeki panel ise radari MERKEZ "
                "SUNUCUSUNDAN ariyordu ve 'timed out' aliyordu.",
                "C20 protokolunun tamami eklendi: oturum acma (LOGIN), "
                "kalp atisi, CRC dogrulamasi, hedef izleri (TRACK), RTK "
                "konumu, ayar okuma (GETREG) ve yazma (SETREG).",
                "Panelden gelen komutlar isleniyor: baglan, kes, adres "
                "degistir, ayar yaz, RTK'dan konum al.",
                "Durum ve hedefler merkeze aktariliyor; izler saat "
                "farkindan bagimsiz yas bilgisi tasir.",
                "Radar sustugunda eski hedefler zamana bagli olarak "
                "eskitilir; ekranda hayalet hedef kalmaz.",
            ],
        },
        {
            "surum": "1.0.0",
            "tarih": "2026-08-13",
            "notlar": [
                "Radar cihazi TCP/seri baglantisi ve iz akisi.",
                "Cihaz erisilemezse nedeni yazip yeniden dener.",
            ],
        },
    ],
}


def servis_surum(ad):
    """Tek bir servisin surum numarasi."""
    return SERVIS_SURUMLERI.get(str(ad or "").lower(), "—")


def servis_gecmis(ad):
    """Tek bir servisin degisiklik gecmisi (en yeni once)."""
    return SERVIS_GECMIS.get(str(ad or "").lower(), [])


def defter():
    """Panelin tek istekte okuyacagi tam surum defteri."""
    return {
        "kopru": {"surum": KOPRU_SURUM, "gecmis": KOPRU_GECMIS},
        "servisler": {
            ad: {"surum": SERVIS_SURUMLERI.get(ad, "—"),
                 "gecmis": SERVIS_GECMIS.get(ad, [])}
            for ad in SERVIS_SURUMLERI
        },
    }
