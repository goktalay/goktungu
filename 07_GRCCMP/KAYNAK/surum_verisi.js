/* =====================================================================
   KURUMSAL PANEL — BAGIMSIZ SURUM DEFTERI
   ---------------------------------------------------------------------
   Bu panel kendi surum numarasini yurutur; GCS (app) surumunden
   BAGIMSIZDIR.  Her teslimde `surum` + `tarih` guncellenir ve `gecmis`
   listesinin BASINA yeni kayit eklenir (en yeni en ustte).

   Onbellek etiketi: `index.html` icindeki `?v=` degerleri bu surumle
   ayni tutulur (nokta yerine rakam: 1.2.0 -> 120).
   ===================================================================== */
'use strict';

window.PANEL_SURUM = {
  ad: 'GÖKTUNGU Kurumsal Panel',
  surum: '1.4.0',
  tarih: '2026-09-17',
  telif: '© 2026 Türkbey Teknoloji Anonim Şirketi',
  gecmis: [
    {
      s: "1.4.0", t: "17 Eylül 2026",
      d: [
        "KOPRULER VE MERKEZI YAZILIMLAR MENULERI. 'Istasyonlar' ikiye ayrildi: Kopruler (Windows/Ubuntu/Android saha kopruleri) ve Merkezi Yazilimlar (GRCOFF kurulumlari). Yeni kayit yalniz AD ister; panel bir API kodu (GTK1.) uretir. Kod listede kopyalanir, kurulum ilk kez baglaninca guvenlik icin silinir; 'Kodu yenile' yeni sir uretir. Kaldir canli baglantiyi da keser.",
        "CEVRIMICI MODULLER. Her kopru kartinda merkeze bildirilen servisler (Dron, AI, Video, GroundGCC, Radar, M50) calisiyor/durdu olarak cip halinde gorunur.",
        "KULLANICI ADI/SIFRE ILE KAYIT KALKTI. Kopru ve Merkezi Yazilim kurulumlari e-posta/sifre yerine API koduyla eslesir; GRCOFF kurulum sihirbazi kurum bilgilerini ve logoyu bu kodla merkezden bir kez ceker."
      ]
    },
    {
      s: "1.3.7", t: "11 Eylül 2026",
      d: [
        "YAYIMLANAN PAKETLER GUNCELLENDI. Merkez Uygulama 2.5.19, Saha Koprusu 1.7.14 ve Goruntu Koprusu 1.3.8; Windows ile Linux paketleri ve imzali katalog kayitlariyla kullanima alindi.",
        "OFFLINE MERKEZDE KOPRUSUZ KAMERA YONETIMI EKLENDI. Yerel USB ve acikca tanimli RTSP(S) kaynaklari Merkez Uygulamasindan eklenip silinebilir; canli goruntu ayni yerel sunucunun oturum korumali yolundan izlenir. Kamera adresi ve kaynak kimlik bilgileri URL'ye veya merkez durum paketlerine konmaz.",
        "M50 KONTROL KATMANI ACIKLANDI. Bu destek yalniz yetkili Windows x64 saha Koprusunde, operatörün acik IP, port, kullanici ve parola girmesiyle baslar. Resmi SDK dizini operatör tarafindan saglanir; SDK dosyalari pakete gomulmez. Kontroller sinirli PTZ, lens, aci ve manuel secime dayali takiple sinirlidir.",
        "GORUNTU VE KONTROL AYRIMI KORUNDU. M50'nin gorunur ve termal RTSP(S) kaynaklari Goruntu Koprusunde yerel olarak tanimlanabilir; uretici SDK'nin ham video geri cagrilari Merkez veya tarayici katmanina tasinmaz. Otomatik hedef edinimi ve otonom hareket islevleri eklenmedi."
      ]
    },
    {
      s: "1.3.6", t: "21 Ağustos 2026",
      d: [
        /* IS83-PANEL-GORUNTU */
        "GORUNTU KOPRUSU INDIRME SAYFASI EKLENDI. Menude Abonelik " +
        "grubunun altinda 'Goruntu Koprusu' ogesi yer alir; Windows ve " +
        "Ubuntu paketleri buradan indirilir. Paketler oturum " +
        "denetimlidir.",
        "DAGITIM KAPISI KAPATILDI. Olcum, `/indir/video/...` yolunun " +
        "OTURUMSUZ 200 dondugunu gosterdi; ayni anda Kopru ve Merkez " +
        "Uygulama paketleri 403 veriyordu. Bu tutarsizlik giderildi: " +
        "Goruntu Koprusu paketleri artik yalniz kurumsal panelden " +
        "iniyor. Istemci kirilma riski olculdu ve yok — Goruntu " +
        "Koprusu 1.0.0'da otomatik guncelleme yetenegi bulunmuyor.",
        "OTURUM KAPISI MESAJI DUZELTILDI. 403 govdesi sabit olarak " +
        "'Kopru Yazilimi sayfasini kullanin' diyordu; oturum kapisi " +
        "artik iki urun tasidigi icin Goruntu Koprusu indirmeye " +
        "calisan kullanici YANLIS sayfaya yonlendiriliyordu. Mesaj " +
        "urune gore degisken yapildi.",
        "SAYFADA DURUST KAPSAM BILDIRIMI VAR. Bu surumde insan ve arac " +
        "tespiti calisir; dron ve plaka tanima YOKTUR ve sayfada " +
        "acikca belirtilir."
      ]
    },
    {
      s: "1.3.5", t: "20 Ağustos 2026",
      d: [
        /* IS52-APP-SURUM-V1 */
        "MERKEZ UYGULAMA INDIRME KARTINA GUNCELLIK UYARISI EKLENDI. " +
        "Merkez Uygulama paketleri artik her arayuz guncellemesinde " +
        "otomatik yeniden uretilmiyor; yalniz istek uzerine " +
        "yayimlaniyor. Bu yuzden depodaki paket, cevrimici GOKTUNGU " +
        "arayuzunun gerisinde kalabilir. Kullanici bunu indirmeden " +
        "ONCE gormeli.",
        "Kart, paketin tasidigi surum ile cevrimici surumu " +
        "karsilastirir ve paket geride ise kartin en ustunde, indirme " +
        "dugmesinden once uyari gosterir. Uyari YALNIZ Merkez Uygulama " +
        "kartinda cikar; Kopru Yazilimi her iste guncellendigi icin o " +
        "kartin davranisi birebir korundu.",
        "SURUM KARSILIGI ARTIK ACIKCA KAYITLI. Ilk tasarim paket " +
        "notlarindaki 'Icerik karsiligi: App x.y.z' cumlesini " +
        "ayristirmakti; olcum bu tasarimi curuttu. En guncel paket olan " +
        "2.5.6'nin 2631 karakterlik notlarinda 'App' kelimesi HIC " +
        "gecmiyordu, 2.5.4'te ise yalniz Linux kaydinda vardi. Serbest " +
        "metne dayali ayristirma sessizce yanlis sonuc uretecekti. " +
        "Depoya ayri bir alan eklendi; deger tahmin edilmiyor.",
        "CEVRIMICI SURUM SUNUCUDAN OKUNUYOR. Ikinci tasarim surumu " +
        "tarayicidan cekmekti; gercek tarayiciyla yapilan olcumde istek " +
        "CORS nedeniyle engellendi. Uygulama sunucusuna genel CORS " +
        "acmak gereksiz saldiri yuzeyi olusturacagi icin karsilastirma " +
        "sunucu tarafina alindi.",
        "SURUM KARSILIGI BILINMIYORSA bu durum ayrica belirtiliyor; " +
        "sessizce 'guncel' varsayilmiyor. Bilgi vermemek yerine yanlis " +
        "guven vermek daha buyuk kusur olurdu.",
      ],
    },
    {
      s: "1.3.4", t: "19 Ağustos 2026",
      d: [
        /* FAZ19-IS39-DEFTER */
        "ANDROID KOPRU UYGULAMASI PANELE EKLENDI. Kopru Yazilimi " +
        "sayfasinda artik uc platform listeleniyor: Windows, " +
        "Ubuntu/Linux ve Android \u2014 Pixhawk/MAVLink. " +
        "APK dosyasi dogrudan iniyor; magaza yonlendirmesi yok.",
        "Pixhawk/MAVLink koprusu telefonu ucus denetleyicisine USB OTG " +
        "veya telemetri baglantisiyla baglar; ArduPilot ve PX4 " +
        "desteklenir.",
        "Uygulama kopru urunu ve android platformu altinda DOSYA ADIYLA " +
        "suzulur. Ayri urun kimligi BILINCLI OLARAK kullanilmadi: " +
        "sunucudaki statik indirme yolunun oturum kapisi urun adina " +
        "bakiyor ve yeni urun adlari oraya eklenmezse paketler " +
        "oturum acmadan inebilirdi. Mevcut kopru urunu altinda " +
        "kalmakla oturum denetimi, imza dogrulamasi ve indirme " +
        "kaydi kendiliginden korunuyor.",
        "Kartlar kurulum icin `bilinmeyen kaynaklardan kuruluma izin " +
        "verme` adimini ve Android 8.0 asgari surum kosulunu belirtiyor.",
      ],
    },
    {
      s: "1.3.3", t: "19 Ağustos 2026",
      d: [
        /* FAZ19-IS38-DEFTER */
        "GUNDUZ KIPINDE INDIRME KARTLARI OKUNMUYORDU. En guncel paket " +
        "satirinin zemini sabit koyu renkle (#14262c) yazilmisti; " +
        "gunduz kipinde yazi rengi acik palete gecerken zemin koyu " +
        "kaldigi icin kontrast 1.1:1'e dusuyor ve surum, dosya adi ile " +
        "boyut bilgisi okunmaz oluyordu.",
        "KOK NEDEN bir SINIF ADI UYUSMAZLIGIYDI: gunduz temasi " +
        "yazilirken duzeltme aslinda yazilmisti, ancak arayuzun hic " +
        "uretmedigi bir sinif adina baglanmisti. Kural olu kaldi, " +
        "kusur canli kaldi. Secici duzeltildi; renk degeri zaten " +
        "dogru secilmis oldugu icin degistirilmedi.",
        "Sabit beyaz yazi rengi kullanan dort kural " +
        "(`button`, `.dugme`, `.dugme:hover`, `.paket-etiket`) " +
        "`--dugme-yazi` degiskenine baglandi. Bu kurallar simdilik " +
        "gorsel kusur uretmiyordu cunku zeminleri iki kipte de koyu; " +
        "yine de vurgu paleti ileride acilirsa kusurun kendiliginden " +
        "ortaya cikmamasi icin sozlesmeye alindi.",
      ],
    },
    {
      s: "1.3.2", t: "18 Ağustos 2026",
      d: [
        /* FAZ16-DEFTER */
        "Ust seride amblem eklendi. Amblem yuksekligi ust serit yazi " +
        "boyutundan turetiliyor (17 px yazi -> 28 px amblem), boylece " +
        "farkli panellerde ayni gorsel oran korunuyor.",
        "Amblem uc boyutlu salinim ve fare yaklasma tepkisi kazandi; " +
        "hareket duyarliligi olan kullanicilar icin isletim sistemi " +
        "ayari animasyonu durduruyor.",
        "Musteri kurum logosu bilesenlerine (`.basli-logo`, " +
        "`.kurum-logo-*`, `.logo-alan`) DOKUNULMADI.",
      ],
    },
    {
      s: "1.3.1", t: "18 Ağustos 2026",
      d: [
        /* FAZ15-DEFTER */
        "Giris kartindaki logo 34 px'ten 44 px'e buyutuldu; tanitim " +
        "sayfasiyla ayni olcek sozlesmesi uygulaniyor.",
        "Amblem uc boyutlu salinim kazandi, sayfa yuklenirken " +
        "animasyonlu perde gosteriliyor. Hareket duyarliligi olan " +
        "kullanicilar icin isletim sistemi ayari animasyonlari " +
        "durduruyor.",
        "Gece/gunduz tercihi artik tanitim sayfasi ve diger panellerle " +
        "paylasiliyor; tercih etki alani genelinde tek cerezde " +
        "tutuluyor.",
        "Panel `company.goktungu.com` alt alan adindan aciliyor. " +
        "`/company/` yolu calismaya devam ediyor; Merkez Uygulama " +
        "kurulumlari yol tabanli erisimi kullaniyor.",
        "Giriş kartı logosu 34 px'ten 44 px'e büyütüldü; sistem " +
        "genelindeki tek logo ölçek sözleşmesine bağlandı. Müşterinin " +
        "yüklediği kurum logosu bileşenlerine (`.basli-logo`, " +
        "`.kurum-logo-*`, `.logo-alan`) DOKUNULMADI.",

        "Giriş ekranı küresini çizen `hero_taktik.js` ve " +
        "`kita_verisi.js` betikleri önbellek etiketi taşımıyordu; " +
        "ızgara görünürlük düzeltmesi bu panelde uygulanmayacaktı. " +
        "Etiket eklendi ve panel sürümüne bağlandı (`?v=131`)."
      ]
    },
    {
      s: '1.3.0', t: '2026-08-17',
      d: [
        'Ürün adı GÖKTUNGU olarak değişti; GÖKTUNGU adı panelden ' +
        'tamamen kaldırıldı. Giriş başlığı, kayıt başlığı, üst şerit ' +
        'markası ve sekme başlığı yeni ada çekildi.',
        'Firma adı artık yalnızca sahiplik satırında: telif kaydı ' +
        '"Türkbey Teknoloji Anonim Şirketi" tam ünvanına çevrildi ' +
        've panel yüzeyinden firma tanıtımı kaldırıldı.',
        'Yetki metinlerindeki "VEILOX" ibaresi rol tanımına çevrildi ' +
        '("üst yönetici"). Artık böyle bir marka olmadığı için bu ' +
        'ibare yetki seviyesini anlatmak yerine marka gibi ' +
        'okunuyordu. Kod tarafındaki `veilox` yetki anahtarı ' +
        'DEĞİŞMEDİ — yalnızca görünen metin düzeltildi.',
        'Talep yönlendirmelerinde "VEILOX ekibi" ibaresi "Türkbey ' +
        'ekibi" olarak güncellendi.',
        'Kurabiye adı (`goktungu_firma`), servis adları ' +
        '(`goktungu-merkez`, `goktungu-kopru`) ve sistem adresi korundu; ' +
        'bunlar marka değil çalışan sistemin kimliğidir ve ' +
        'değiştirilmesi oturumları ve servisleri kırardı.'
      ]
    },
    {
      s: '1.2.1', t: '2026-08-16',
      d: [
        'Giriş ekranına da tema düğmesi eklendi: düğme yalnızca oturum ' +
        'açıldıktan sonra görünen üst şeritte olduğu için giriş, tema ' +
        'seçimi yapılamayan tek ekran olarak kalıyordu.',
        'Açık temada giriş kartına ince bir çerçeve ve gölge verildi; ' +
        'sayfa arka planı da açık olduğu için kart zeminden ' +
        'ayrışmıyordu.',
        'Gündüz/gece teması eklendi: üst şeritteki güneş/ay düğmesi ' +
        'paneli açık ve koyu görünüm arasında değiştiriyor.',
        'İlk açılışta işletim sisteminin görünüm tercihi izleniyor; ' +
        'kullanıcı bir kez elle seçtiğinde artık kendi seçimi geçerli ' +
        'oluyor ve seçim tarayıcıda kalıcı saklanıyor.',
        'Tema seçimi panele özeldir: kurumsal panelde yapılan seçim ' +
        'yönetim panelini veya köprü arayüzünü etkilemiyor.',
        'Açık temada okunurluk için yalnızca renk değişkenleri değil, ' +
        'değişken dışında yazılmış tüm öğeler de karşılandı: durum ' +
        'rozetleri, bildirimler, uyarı kutuları, tehlike düğmeleri ve ' +
        'logo alanları.',
        'Geçersiz bir CSS renk değeri temizlendi: bağlantısı kopmuş ' +
        'istasyon noktasının zemininde bozuk bir değer duruyordu.',
        'Önbellek etiketleri 1.2.0 sürümüne hizalandı; stil dosyasının ' +
        'etiketi atlandığı için yeni tema tarayıcıda eski sürümden ' +
        'okunma riski taşıyordu.'
      ]
    },
    {
      s: '1.1.0', t: '2026-08-16',
      d: [
        'Köprü Yazılımı indirme bölümü eklendi: köprü paketleri artık ' +
        'yalnızca üye panelinden, oturum denetimiyle iniyor.',
        'Merkez Uygulama ve Köprü paket listeleri sürüme göre ' +
        'sıralanıyor; en güncel paket en üstte "GÜNCEL" rozetiyle ' +
        'geliyor, eski sürümler katlanır bir bölümde toplanıyor.',
        'Paket listelerindeki İndir düğmeleri artık gerçekten düğme ' +
        'görünümünde: eksik olan ".dugme" biçemi eklendi.',
        'Panele bağımsız sürüm defteri ve Hakkında bölümü eklendi.',
        'Önbellek etiketleri panel sürümüne bağlandı; güncellemeler ' +
        'tarayıcıda eski sürüm olarak takılı kalmıyor.'
      ]
    },
    {
      s: '1.0.0', t: '2026-08-15',
      d: [
        'Kurumsal panel ilk yayın: gösterge paneli, uçuş ve video ' +
        'kayıtları, dronlar, istasyonlar, ekip yönetimi, kurum ' +
        'bilgileri, abonelik ve Merkez Uygulama bölümleri.',
        'Üyelik ve rol yönetimi tek kapı olarak bu panele alındı; ' +
        'GÖKTUNGU arayüzünden kaldırıldı.',
        'Merkez Uygulama lisansı olan kurumlar için kurulum paketi ' +
        'indirme bölümü eklendi.'
      ]
    }
  ]
};
