/* =====================================================================
   TANITIM SITESI — BAGIMSIZ SURUM DEFTERI
   ---------------------------------------------------------------------
   Bu sayfa kendi surum numarasini yurutur; GCS (app), kurumsal panel ve
   yonetim paneli surumlerinden BAGIMSIZDIR.

   AYRIM (onemli): alt bilgideki "Surum {s}" rozeti URUN surumunu
   (sahaya kurulan KOPRU surumu) gosterir ve `/api/genel/katalog`
   ucundan gelir (js/indir.js -> window.__GOKTUNGU_SURUM).  Buradaki
   `PANEL_SURUM` ise SITENIN kendi surumudur; ikisi karistirilmamalidir.

   Her teslimde `surum` + `tarih` guncellenir ve `gecmis` listesinin
   BASINA yeni kayit eklenir (en yeni en ustte).  Onbellek etiketi
   (`?v=`) bu surumle ayni tutulur (2.7.0 -> 270).

   NOT (v2.7.0 ile degisti): urun surumu artik `js/indir.js` yerine
   dogrudan index.html icindeki gomulu betik tarafindan yaziliyor.
   Yer tutucu sozlesmesi: `<span data-surum-yaz>`.  Uc erisilemezse
   HTML'deki deger korunur.
   ===================================================================== */
'use strict';

window.PANEL_SURUM = {
  ad: 'GÖKTUNGU Tanıtım Sitesi',
  surum: '2.14.0',
  tarih: '2026-09-14',
  logo: '/img/goktungu.webp',
  telif: '© 2026 Türkbey Teknoloji Anonim Şirketi',
  gecmis: [
    {
      /* YETENEK-ANLATIMI-20260914 */ s: "2.14.0", t: "14 Eylül 2026",
      n: "Yetenek bölümü animasyonlu şemalarla yeniden anlatıldı",
      d: [
        "YETENEKLER BOLUMU DEGISTI: alti duragan kart yerine bes yetenek blogu geldi (C20 radar fuzyonu, M50 elektro-optik, goruntu cozumlemesi, angajman motoru, insansiz hava araclari). Her blok kendi animasyonlu SVG semasini ve teknik kunyesini tasir.",
        "SEMALAR SAF SVG + CSS: kitaplik yuklenmez, sayfa agirligi artmaz. Renkler sitenin kendi tokenlarindan gelir (siyan = algilama, kehribar = angajman), bu yuzden acik/koyu tema anahtari bu bloklarda da dogru calisir.",
        "HAREKET TERCIHI: `prefers-reduced-motion` acikken animasyonlar durur; semalar duragan halde de tam okunur -- hareket bilgi tasimaz, yalnizca dikkat yonlendirir.",
        "INGILIZCE KARSILIKLAR EKLENDI: yeni bloklarin 60 metni sozluge islendi; EN kipinde Turkce metin kalmaz.",
      ],
    },
    {
      /* M50-OFFLINE-20260911 */ s: "2.13.8", t: "11 Eylül 2026",
      n: "M50 elektro-optik katmanı ve offline canlı kamera mimarisi",
      d: [
        "YAYIMLANAN BILESENLER SITEDE GUNCELLENDI: Merkez Uygulama 2.5.19, Saha Koprusu 1.7.14 ve Goruntu Koprusu 1.3.8; Windows ve Linux paketleri imzali katalogdan dogrulanarak yayinlandi.",
        "OFFLINE MERKEZ KAMERA YONETIMI AYRISTIRILDI: internetten bagimsiz Merkez kurulumunda yerel USB ve operatörün acikca tanimladigi RTSP(S) kaynaklari Kopru zorunlulugu olmadan eklenir, silinir ve ayni yerel sunucuda canli izlenir. Akis erisimi oturumla korunur; kaynak adresi ile kimlik bilgileri URL'ye veya durum paketlerine cikmaz.",
        "M50 DESTEĞI YALNIZ YETKILI WINDOWS X64 SAHA KOPRUSUNDEDIR. Baglanti varsayilan hedef veya ag kesfi olmadan, operatörün IP, port, kullanici ve parola bilgilerini acikca girmesiyle baslar. Resmi SDK dosyalari dagitim paketine eklenmez; operatör kendi lisansli SDK dizinini secer.",
        "GORUNTU VE KONTROL KATMANLARI AYRI TUTULUR: M50 gorunur/termal RTSP(S) kaynaklari Goruntu Koprusunde yerel islenir; uretici SDK'sinin ham video geri cagrilari merkeze veya tarayiciya aktarilmaz. M50 kontrolleri sinirli PTZ, lens, aci ve manuel secime dayali takiple sinirlidir; otomatik hedef edinimi ile otonom hareket eklenmemistir."
      ]
    },
    {
      /* FAZ18-IS16-YAYIN */ s: "2.13.7", t: "19 Ağustos 2026",
      n: "Destek sitesi üst çubuğu — dil ve tema düğmesi sağa alındı",
      d: [
        "Destek sitesinin üst çubuğundaki dil seçici (TR/EN) ve gece/gündüz düğmesi, amblemin hemen yanında ekranın ortasında duruyordu. İki öge artık üst çubuğun sağ ucunda; sistemdeki diğer arayüzlerin yerleşimiyle aynı hizaya geldi.",
        "Kusurun kaynağı, boş alanı sağa itme görevinin İçindekiler düğmesine verilmiş olmasıydı. O düğme 960 piksel üstündeki ekranlarda gizlenir; gizlenen öge yerleşim akışından tamamen çıktığı için üzerindeki kural masaüstünde hiç işlemiyordu. Ölçüm bunu sayıyla gösterdi: düğme grubunun sağ kenarı, kullanılabilir alanın sağ kenarından 826 piksel içeride kalıyordu.",
        "Görev, her ekran genişliğinde akışta kalan gezinme ögesine taşındı. Aynı tuzak bu dosyada başka bir öge için zaten belgelenmişti; not, hatanın yinelenmemesi için ilgili kuralın yanına da yazıldı. Ölçüm yeni yerleşimde sağ boşluğun 30 piksele indiğini doğruladı — kalan pay kapsayıcının kendi iç boşluğudur.",
        "Dar ekran davranışı korundu: 960 piksel altında İçindekiler düğmesi görünür ve sağ bloğun soluna yapışır, 720 piksel altında \"Ana Site\" yazısı gizlenir, dil ve tema düğmesi her genişlikte sağda kalır."
      ]
    },
    {
      /* FAZ18-IS24-BAKIM-KIPI */ s: "2.13.6", t: "19 Ağustos 2026",
      n: "Sistem bakım kipi",
      d: [
        "Yeni kurum ve bireysel kayıt akışı, sistem bakım aşamasındayken sunucu tarafında geçici olarak durdurulabilir hale getirildi. Bakım sırasında ziyaretçi kayıt formunu doldurup gönderdikten sonra anlamsız bir hata almak yerine, formu açtığı anda durumu bildiren bir uyarı bandı görüyor.",
        "Kip, yalnız yeni kayıt üreten iki ucu kapatır. Mevcut kullanıcıların girişi, harekât arayüzü, köprü trafiği ve yarım kalmış e-posta doğrulamaları bilinçli olarak etkilenmez; aksi halde bakım kipi, korumaya çalıştığı sistemi kullanılamaz hale getirirdi. Yarım kalmış doğrulamaların muaf tutulması özellikle önemlidir: kullanıcı bakım başlamadan önce kayıt olmuş olabilir ve bu akışı kesmek onu hiçbir zaman tamamlanamayacak bir durumda bırakırdı.",
        "Kapatılan uçlar 403 yerine 503 döndürür ve Retry-After başlığı taşır. 403 ziyaretçiyi kendi hesabında sorun aramaya yönlendirirdi; 503 ise geçici kullanılamazlığın doğru karşılığıdır ve arama motorları bunu kalıcı kusur saymaz.",
        "Bakım bayrağı, genel yapılandırmadan AYRI bir dosyada tutulur. İlk tasarımda genel yapılandırmaya yazılacaktı; ölçüm bu yaklaşımı çürüttü, çünkü yapılandırma okuyucusu değerleri süreç ömrü boyunca önbelleğe alıyor ve bayrak servis yeniden başlatılmadıkça hiç okunmuyordu. Bakım kipinin tek anlamlı kullanım biçimi anında açılıp kapanmasıdır; her açma için servisi yeniden başlatmak, tam da korumaya çalıştığı anda sistemi kesintiye uğratırdı. Bayrak artık dosya değişiklik zamanı denetimiyle okunur: kip anında etkili olur, her istekte disk okuması yapılmaz.",
        "Uyarı bandı marka kırmızısı yerine kehribar tema değişkenini kullanır. Bakım bir hata değil planlı bir durumdur; kırmızı band ziyaretçiye kendi işleminde sorun varmış izlenimi verirdi. Renk sabit yazılmadı, aksi halde gece/gündüz döngüsünde okunamaz hale gelirdi."
      ]
    },
    {
      /* FAZ18-IS15-MARKA-TEMIZLIK */ s: "2.13.5", t: "19 Ağustos 2026",
      n: "Marka kalıntılarının temizliği",
      d: [
        "İngilizce dil sözlüğünde site başlığı, açıklama, kurum tanımı ve künye alanlarında kalan eski marka adı resmi künye ile değiştirildi. Türkçe sözlük zaten güncel olduğu için İngilizce ziyaretçi ile Türkçe ziyaretçi farklı kurum adı görüyordu; bu tutarsızlık giderildi.",
        "Uygulama dizinindeki referanssız eski marka logosu ve dağıtım deposunda kayıt taşımayan 18 eski kurulum paketi arşive taşındı. Silme yerine taşıma seçildi: bu ikililer müşteriye gönderilmiş gerçek dosyalar, ileride sürüm karşılaştırması gerekebilir.",
        "Kod sözleşmesi sabitleri, veritabanı değerleri, gerçek e-posta adresi, geçerli SSL sertifikası taşıyan eski alan adı ve ödeme tahsilat unvanı bilinçli olarak korundu; bunları değiştirmek veri göçü, DNS veya mali kayıt kırılması üretirdi.",
        "Tanıtım sayfasındaki önbellek etiketleri dört ayrı değere dağılmış durumdaydı ve dil dosyası en eski değerde kalmıştı. Tüm etiketler tek değere eşitlendi; aksi halde bu düzeltme ziyaretçinin tarayıcısında görünmezdi."
      ]
    },
    {
      s: "2.13.4", t: "18 Ağustos 2026",
      d: [
        /* FAZ18-IS5 */
        "Destek Merkezi ust cubugundan \u201cSisteme Giris\u201d dugmesi kaldirildi. Destek bir belge sitesidir ve oturum kabugu bir onceki surumde zaten kaldirilmisti; geride yalniz giris bagi kalmisti. Bag kalktigi icin dil secici ile gece/gunduz dugmesi grubun son iki ogesi olarak EN SAGA geldi; bunun icin yeni bir hizalama kurali gerekmedi, cunku ust cubuk bos alani icindekiler dugmesinden ONCE topluyor ve menu grubu zaten saga yasli duruyor.",
        "Amblem baglantisi denetlendi: tiklandiginda tanitim sitesinin kokune gidiyor. Bu davranis zaten dogruydu, degistirilmedi ve sinavla korunuyor.",
        "Kaldirilan dugmenin ardinda kalan OLU stil kurallari da temizlendi. Dugmenin sinifi Destek ust cubugunda baska hicbir yerde kullanilmiyordu; kurallar birakilsaydi ileride ayni sinifi kullanan bir oge 480 piksel altinda SESSIZCE gizlenirdi. Daralan ekran davranisi artik sudur: 960 piksel altinda icindekiler dugmesi gorunur, 720 piksel altinda Ana Site yazisi gizlenir, dil ve tema her genislikte kalir. Bir onceki surum kaydinda gecen \u201c480 piksel altinda Sisteme Giris dugmesi gizlenir\u201d ifadesi bu surumle GECERSIZDIR.",
        "Destek sayfasinin onbellek etiketleri dort ayri degere dagilmis durumdaydi; kaynak dosyalarin bir kismi eski etiketle isaretli oldugu icin tarayici guncellenen stil ve betikleri onbellekten servis edebiliyordu. Tum etiketler site surumuyle ayni tek degere esitlendi."
      ]
    },
    {
      s: "2.13.3", t: "18 Ağustos 2026",
      d: [
        /* FAZ18-AGAC */
        "Destek Merkezi ağaç görünümünde girinti yönü ters çalışıyordu: alt öğeler üst öğenin sağında değil 17 px solunda başlıyordu. Kök neden ölçüldü — dal başlığındaki iki ikon (aç/kapa göstergesi 12 px + konu ikonu 15 px + iki boşluk 16 px) metni 51 px'e itiyor, alt bağlantı ise yalnız 34 px girinti alıyordu. Alt liste girintisi ikon genişliğini telafi edecek biçimde hizalandı ve üzerine bir kademe girinti eklendi; artık her alt öğe üst öğesinin sağında başlıyor.",
        "Ağaç düğümleri artı/eksi göstergesiyle açılıp kapanıyor: kapalı düğümde çerçeveli artı, açık düğümde eksi işareti görünüyor. Gösterge CSS üzerinden tek kaynaktan besleniyor, böylece on üç dalın tamamı aynı davranışı taşıyor.",
        "Ağaç çizgisi eklendi: alt listelerin sol kenarında dikey rehber çizgi, her alt öğede kısa yatay bağlantı çizgisi çiziliyor. Arama kipinde gizlenen öğelerin çizgileri de gizleniyor, böylece süzülmüş listede boşta kalan çizgi görünmüyor.",
        "Ölçüm sırasında bulunan ek kusur giderildi: on üç dalın on ikisinde aç/kapa göstergesi chevron ikonu taşırken Destek dalına yanlışlıkla kulaklık ikonu yazılmıştı. O dalda gösterge dönmüyor, ayrıca yanındaki cankurtaran simidi ikonuyla çakışıyordu; işaretleme diğer on iki dalla eşitlendi.",
        "Ağaç erişilebilirliği tamamlandı: her dal başlığı aria-expanded durumu taşıyor, durum düğüm her açılıp kapandığında ve sayfa yüklenirken kayıtlı durum geri okunduktan sonra eşitleniyor."
      ]
    },
    {
      s: "2.13.2", t: "18 Ağustos 2026",
      d: [
        /* FAZ17-DEFTER */
        "Destek Merkezi bağımsızlaştırıldı: üst çubuktaki tanıtım sitesi menüsü (Mimari, Yetenekler, İstemciler, Fiyatlandırma) kaldırıldı; yerine Destek'e ait kendi menüsü kuruldu (Ana Site, dil seçici, tema, Sisteme Giriş).",
        "Ölü menü düğmesi kusuru giderildi: Destek sayfasında mobil hamburger düğmesi görünüyor ancak dinleyicisi tanıtım sayfasının betiğinde olduğu için dokunulduğunda hiçbir şey olmuyordu. Düğme ve boş menü kabı kaldırıldı; geride kalıntı bulunması durumunda çalışma anında gizleyen koruma eklendi.",
        "İçindekiler düğmesi üst çubuğun sağına taşındı (margin-left:auto); marka solda, gezinme sağda sözleşmesi tüm arayüzlerle aynı hale geldi.",
        "Destek üst çubuğu daralan ekrana göre kademeli sadeleşiyor: 960 px altında içindekiler düğmesi görünür, 720 px altında Ana Site bağlantısı, 480 px altında Sisteme Giriş düğmesi gizlenir.",
        "Destek sayfasında oturum kabuğu (kullanıcı ikonu) ve oturum betiği kaldırıldı; belge sitesi artık oturum durumundan bağımsız çalışıyor.",
        "Yan panel erişilebilirliği tamamlandı: aria-expanded durumu yazılıyor, Escape tuşu ve perdeye dokunma paneli kapatıyor, aria-controls doğru hedefi gösteriyor.",
        "i18n anahtar uyuşmazlığı giderildi: içindekiler düğmesinin başlık çevirisi tanımsız anahtara bağlıydı; Destek sözlüğüne taşındı ve İngilizce karşılığı eklendi."
      ]
    },
    {
      s: "2.13.1", t: "18 Ağustos 2026",
      d: [
        /* FAZ16-DEFTER */
        "PANELLERIN UST SERIDINDE AMBLEM YOKTU: kurumsal ve yonetim " +
        "panellerinin ust seridi yalniz metin logosu " +
        "(`goktungu_serit.webp`) tasiyordu, amblem gorunmuyordu. Kok " +
        "neden olculdu: Faz 15'te eklenen `logo_anim.js` amblemi YALNIZ " +
        "`<img>` cocugu olan `.marka` ogelerine enjekte ediyordu; " +
        "panellerin ust serit markasi ise saf metindi " +
        "(`<span>GÖKTUNGU</span>`), bu yuzden kol hic devreye " +
        "girmiyordu. Enjeksiyon artik metin markalarini da kapsiyor.",
        "AMBLEM OLCEGI YAZI BUYUKLUGUNDEN TURETILIYOR: panel ust " +
        "seritleri farkli yazi boyutlari kullaniyor (kurumsal 17 px, " +
        "yonetim 16 px). Sabit piksel yazilsa amblem bir panelde yaziyi " +
        "ezecek, digerinde kaybolacakti. Amblem yuksekligi calisma " +
        "aninda `getComputedStyle(marka).fontSize * 1.65` ile " +
        "turetiliyor.",
        "DESTEK SITESI SOL PANELI KIRMIZI YUZEN DUGMEYLE ACILIYORDU: " +
        "`.yrd-agac-dugme` sol alt kosede sabit konumlu, marka " +
        "kirmizisi zeminli bir dugmeydi ve iceriğin uzerine biniyordu. " +
        "Standart menu duzenine gecildi: masaustunde sol panel KALICI " +
        "acik (`sticky`), 960 px altinda ust cubuktaki saydam zeminli " +
        "`Icindekiler` dugmesi paneli aciyor. `aria-expanded` ve " +
        "`aria-controls` nitelikleri eklendi; Escape tusu ve perdeye " +
        "dokunma paneli kapatiyor.",
      ],
    },
    {
      s: "2.13.0", t: "18 Ağustos 2026",
      d: [
        /* FAZ15-DEFTER */
        "TEMA TERCIHI PANELLER ARASINDA PAYLASILIYOR: gece/gunduz " +
        "secimi `localStorage`'da tutuluyordu ve `localStorage` ETKI " +
        "ALANINA OZGUDUR; paneller ayri alt alan adlarina tasindiginda " +
        "her panel kendi tercihini ayri tutacak, kullanici tanitim " +
        "sayfasinda gece temasi secip yonetim paneline gectiginde " +
        "gunduz temasiyla karsilasacakti. Tercih artik `.goktungu.com` " +
        "etki alanina yazilan tek bir cerezde tutuluyor. Merkez " +
        "Uygulama kurulumlari icin koruma: ana makine `localhost` veya " +
        "IP ise cerez etki alani belirtilmeden yaziliyor, cunku " +
        "tarayicilar IP adreslerine `Domain` niteligi yazilmasini " +
        "REDDEDER ve tercih hic kaydedilmezdi. Eski `localStorage` " +
        "anahtarlari ilk acilista cereze goc ediyor.",
        "PANELLER ALT ALAN ADLARINA AYRILDI: `app.goktungu.com`, " +
        "`admin.goktungu.com`, `company.goktungu.com` ve " +
        "`support.goktungu.com`. Yonlendirme DEGIL yeniden yazim " +
        "kullanildi; 301 kullanilsa kullanici `goktungu.com/app/` " +
        "adresine duser ve alt alan adinin amaci bosa cikardi, adres " +
        "cubugu artik alt alan adinda kaliyor. Yol tabanli erisim " +
        "(`/app/`, `/admin/`, `/company/`, `/yardim/`) KALDIRILMADI: " +
        "Merkez Uygulama satin alan firmalar sistemi kapali devre veya " +
        "`localhost` uzerinde calistiriyor, orada alt alan adi yoktur. " +
        "Yeniden yazim yalniz ana makine `<alt>.<alan_adi>` kalibina " +
        "uyarsa devreye giriyor.",
        "ALT ALAN ADINDA APP VARLIKLARI KIRILIYORDU (olculdu): " +
        "paylasilan varliklar (`/js/`, `/css/`, `/img/`) yeniden " +
        "yazimdan muaf tutulmustu, cunku dort panel de bu kok yollari " +
        "kullaniyor. Ancak `app` kendi kokunde tam bir uygulama ve " +
        "varliklarini GORELI yolla cagiriyor (`src=\"js/ws.js\"`); alt " +
        "alan adinda sayfa `/` kokunde durdugu icin tarayici " +
        "`/js/ws.js` istiyor ve muafiyet yuzunden merkezin kok " +
        "dizininde araniyordu. Olculen sonuc: `/js/ws.js` 404 " +
        "veriyordu, `/css/stil.css` ise 404 bile vermeyip MERKEZIN " +
        "CSS'ini donuyordu — app yanlis stille aciliyordu. Muafiyet " +
        "artik alt alan adi basina ayriliyor.",
        "YARDIM BOLUMU DESTEK MERKEZI OLDU: menu adi ve baglantilar " +
        "`support.goktungu.com` adresine gecirildi. Adres calisma " +
        "aninda ana makineye bakilarak secilyor: bulut dagitiminda " +
        "`support.goktungu.com`, Merkez Uygulama kurulumlarinda yerel " +
        "`/yardim/` yolu. Sabit yazilmis bir baglanti kapali devre " +
        "kurulumlarda olu olurdu. Derin baglantilar korunuyor: " +
        "`data-destek-bag=\"kopru-kurulum\"` niteligi capa olarak " +
        "aktariliyor. Betik yuklenmezse HTML'deki `/yardim/` degeri " +
        "gecerli kaliyor — bozulma degil geri dusus.",
        "AMBLEM UC BOYUTLU HALE GETIRILDI: logo ikonu 24 derecelik " +
        "perspektif icinde yavas salinim yapiyor (9 saniyelik dongu), " +
        "fare yaklasinca hizlaniyor, tiklamada geri tepiyor. Ikon logo " +
        "goruntusunden ayri bir SVG olarak yeniden ureltildi; raster " +
        "goruntunun ikon bolumu `clipPath` ile kirpilarak yazi kismi " +
        "korundu ve hizalama piksel tabanli olcumle yapildi (yuzde " +
        "deger kapsayici genisligine bagli oldugu icin kararsizdi). " +
        "Ayri bir WebGL baglami KASITLI olarak kullanilmadi: sahnede " +
        "zaten CesiumJS kuresi calisiyor, ikinci bir baglam mobilde " +
        "kare dusmesine yol acardi.",
        "SAYFA YUKLENIRKEN AMBLEM PERDESI: acilista amblem belirip " +
        "nabiz atiyor, sayfa hazir olunca perde yumusakca kayboluyor. " +
        "Perde en fazla belirli bir sure gorunur — zaman asimi emniyeti " +
        "olmadan ag yavasladiginda perde asili kalir ve komuta " +
        "arayuzunu kapatirdi, bu operasyonel bir risktir. Hareket " +
        "duyarliligi olan kullanicilar icin isletim sistemi ayari " +
        "(`prefers-reduced-motion`) tum animasyonlari otomatik " +
        "durduruyor.",
        "ANIMASYON HIC CALISMIYORDU (olculdu): CSS seciciler amblemi " +
        "`.gt-amblem svg` olarak hedefliyordu, ancak amblem sayfaya " +
        "`<img>` ogesi olarak ekleniyor. On secici hicbir ogeye " +
        "eslesmiyordu; `animation-name` `none`, `transform-style` " +
        "`flat` olarak olculdu. On seciciyi de kapsayan 10 kural " +
        "`img`'ye cevrildi. Duzeltme sonrasi olcum: `animation-name` " +
        "`gtAmblemSalinim`, `transform-style` `preserve-3d`, " +
        "`transform` bir `matrix3d(...)` ve 900 ms arayla alinan iki " +
        "ornek farkli — animasyon gercekten donuyor.",
        "LOGO ÖLÇEK UYUMLAMASI: logo arayüzler arasında beş ayrı " +
        "ölçekte (20/26/30/34/46 px) kullanılıyordu; üst şeritteki 26 px " +
        "logo 15 px menü yazılarının yanında optik olarak küçük kalıyor, " +
        "görsel hiyerarşi tersine dönüyordu. Tek ölçek sözleşmesi " +
        "uygulandı: üst şerit 36 px, alt bilgi 40 px, giriş kartları " +
        "44 px. Dar ekranda üst şerit logosu 30 px'e kelepçelenir; " +
        "aksi halde 36 px logo mobil menü düğmesiyle çakışıyordu. " +
        "Müşteri/kurum logoları (`.basli-logo`, `.kurum-logo-*`, " +
        "`.logo-alan`) KAPSAM DIŞI bırakıldı — onlar müşterinin " +
        "yüklediği varlıklar.",

        "IZGARA GÖRSEL HİYERARŞİSİ: arka plandaki dekoratif kare ızgara " +
        "(`#hero::after`) 0,50 alfa ile çiziliyordu, kürenin kendi " +
        "meridyen/paralel ağı ise 0,20 ile — dekor, ana öğeden 2,5 kat " +
        "belirgindi ve dünya geri planda kalıyordu. Kök neden: açık " +
        "temada ızgaraya 0,30 opaklık düşürmesi tanımlıyken KOYU temada " +
        "hiç düşürme yoktu. Koyu temaya 0,32 opaklık eklendi (etkin " +
        "alfa ~0,16), ızgara aralığı 56 px'ten 64 px'e seyreltildi. " +
        "Buna karşılık küre ızgarası 0,20→0,26 ve kıta çizgileri " +
        "0,46→0,56 belirginleştirildi. Yeni hiyerarşi: kare ızgara " +
        "0,16 < küre ızgarası 0,26 < kıta sınırları 0,56.",

        "ÖNBELLEK ETİKETİ KUSURU (üç ayrı bulgu): (1) yönetim paneli " +
        "altı varlıkta boş `?v=` etiketi taşıyordu — boş etiket her " +
        "zaman aynı URL ürettiği için önbellek hiç geçersizleşmiyordu; " +
        "(2) `hero_taktik.js` ve `kita_verisi.js` yönetim ve kurumsal " +
        "panellerde etiketsizdi, dolayısıyla ızgara düzeltmesi o " +
        "panellerde görünmeyecekti; (3) yardım sayfası paylaşılan " +
        "`css/stil.css`'i tanıtım sayfasından farklı etiketle " +
        "(`2126` / `2128`) çekiyordu, aynı dosya için iki önbellek " +
        "girdisi oluşuyordu. Üçü de giderildi."
      ]
    },
    {
      s: "2.12.4", t: "17 Ağustos 2026",
      d: [
        "ALAN ADI GEÇİŞİ goktungu.com: sistem `gozcu.veilox.com.tr` " +
        "adresinden `goktungu.com` adresine taşındı. Sectigo Positive SSL " +
        "joker sertifikası (`*.goktungu.com` + `goktungu.com`, 17 Ağu 2026 " +
        "→ 3 Mar 2027) kuruldu; zincir yaprak + iki ara sertifikadan " +
        "oluşturuldu, kök sertifika zincire KASITLI olarak eklenmedi — " +
        "kökü zincire koymak el sıkışmayı gereksiz büyütecek ve bazı " +
        "istemcilerde doğrulama uyarısı üretecekti. 28 dosyada 61 alan " +
        "adı referansı geçirildi; yedek dizinleri ve sürüm defterindeki " +
        "tarihsel kayıtlar tarihsel doğruluk için korundu.",

        "SNI ÇOĞULLAMASI — İKİ ALAN ADI, İKİ SERTİFİKA: sunucuda nginx " +
        "yok, TLS'i doğrudan Python merkez servisi sonlandırıyor ve tek " +
        "`load_cert_chain` çağrısı yapıyordu; bu yüzden istemci hangi alan " +
        "adını isterse istesin AYNI sertifika sunuluyordu, yani iki alan " +
        "adının aynı anda geçerli HTTPS ile çalışması olanaksızdı. " +
        "`sni_callback` eklendi: `goktungu.com` ve alt alan adları Sectigo " +
        "joker sertifikasını, `gozcu.veilox.com.tr` kendi Let's Encrypt " +
        "sertifikasını alıyor. Joker eşleştirme RFC 6125 uyarınca yalnız " +
        "TEK etiket kapsar (`a.goktungu.com` eşleşir, `a.b.goktungu.com` " +
        "eşleşmez); ileride iç içe alt alan adı tanımlanırsa sessizce " +
        "yanlış sertifika sunulması riski olduğu için 11 ölçütlü birim " +
        "sınavıyla ayrıca doğrulandı.",

        "PORT 80 İÇERİĞİ ŞİFRESİZ SUNUYORDU (ölçümle yakalandı): port 80 " +
        "sayfayı düz HTTP üzerinden 200 koduyla veriyordu, yani adresi " +
        "şifresiz açan tarayıcı uyarı almadan içeriği görüyordu. Artık " +
        "HTTPS'e yönlendiriyor. GET/HEAD için 301, diğer yöntemler için " +
        "308 kullanılıyor — 301 istemcilerin POST'u GET'e çevirmesine izin " +
        "verir ve istek gövdesi kaybolur; köprü ve API istemcileri POST " +
        "kullandığı için bu ayrım işlevseldir. Eski alan adı yeni adrese " +
        "YOL KORUYARAK yönleniyor (`/app/` → `/app/`), müşterilerin " +
        "kayıtlı derin bağlantıları kırılmadı.",

        "ACME DOĞRULAMA YOLU MUAF TUTULDU: `/.well-known/acme-challenge/` " +
        "yönlendirilmiyor, diskten sunuluyor. Bu yol yönlendirilse eski " +
        "alan adının Let's Encrypt yenilemesi KALICI olarak kırılırdı, " +
        "çünkü HTTP-01 doğrulaması düz HTTP üzerinden yapılır. Muafiyetin " +
        "çalıştığı dizine deneme dosyası konularak ölçüldü.",

        "SERTİFİKA YENİLEME ALTYAPISINDA ÜÇ SESSİZ KUSUR KAPATILDI — sistem " +
        "sorunsuz görünüyordu ama sertifika dolduğu gün erişilemez hale " +
        "gelecekti: (1) `certbot-renew.timer` `enabled` işaretliydi ama " +
        "`inactive (dead)` durumdaydı ve tetikleyicisi yoktu — eski alan " +
        "adı sertifikası 30 Eki 2026'da sessizce dolacak, yönlendirme TLS " +
        "hatasıyla kırılacaktı. (2) Yenileme kancası sertifikayı artık " +
        "kullanılmayan `/opt/goktungu/v201/sertifika` dizinine kopyalıyor ve " +
        "var olmayan `goktungu` servisini yeniden başlatıyordu (gerçek servis " +
        "`goktungu-merkez`); yenileme başarılı olsa bile yeni sertifika " +
        "devreye girmezdi, çünkü TLS bağlamı yalnız açılışta kurulur. " +
        "(3) Doğrulayıcı `standalone` idi ve 80 portunu merkez servisten " +
        "kapmaya çalışıyordu; `webroot`a geçildi. Kuru çalışma başarılı ve " +
        "`NRestarts=0`: doğrulama boyunca servis HİÇ durmuyor.",

        "YENİ KANCA BOZUK SERTİFİKAYLA ÇALIŞAN SİSTEMİ İNDİRMİYOR: yeniden " +
        "başlatmadan ÖNCE TLS bağlamını Python ile kurmayı dener; " +
        "kurulamıyorsa restart yapılmaz ve hata günlüğe yazılır. Sectigo " +
        "joker sertifikası SATIN ALINAN bir ürün olduğu ve ACME ile " +
        "yenilenemediği için günlük son kullanma denetimi kuruldu; durum " +
        "`veri/sertifika_durum.json` dosyasına yazılıyor (30 gün `uyari`, " +
        "14 gün `kritik`). Sertifika 3 Mart 2027'de doluyor ve ELLE " +
        "yenilenmelidir.",

        "İNGİLİZCE VİTRİN HİÇ YAYINLANMAMIŞ BİR MİMARİYİ ANLATIYORDU: EN " +
        "sözlüğü \"v2.5.1\", \"derlenmiş C++17 istemciler\", \"WSS 9443\", " +
        "\"Cloud Layer / Field Layer\", \"task executor\" gibi var olmamış " +
        "bir yapıyı tanımlıyordu; Türkçe kaynak ise gerçek mimariyi " +
        "(Python 3.11 köprü, 443 üzerinden ters WebSocket) anlatıyor. 54 " +
        "karşılık düzeltildi. HTML'e dokunulmadı: i18n sözleşmesi " +
        "HTML'deki Türkçe metni KAYNAK kabul eder, İngilizce yalnız " +
        "sözlükten yazılır. En kritik kayıp `guv.g6alt` maddesiydi — " +
        "Türkçe metin kesintide disk sınırı aşılırsa EN ESKİ KAYDIN " +
        "KORUNDUĞUNU, en yeni verinin atıldığını belgeliyor (arıza " +
        "incelemesinde kritik bölüm kesintinin başındadır); sektörde " +
        "alışılmışın tersi olan bu mühendislik kararı İngilizce sayfada " +
        "tamamen yoktu.",

        "KÖPRÜ ADRESİNDEN `:9443` PORTU DÜŞÜRÜLDÜ: adres " +
        "`wss://goktungu.com/kopru` biçimine getirildi. Standart dışı " +
        "portlar kurumsal güvenlik duvarlarında ve mobil operatör " +
        "ağlarında sıklıkla engellenir, 443 ise fiilen her yerde açıktır. " +
        "Sahada bağlı köprü olmadığı için değişiklik kesinti üretmedi.",

        "KORUNAN TEKNİK KİMLİKLER: `veilox` rol adı ve " +
        "`SQL CHECK kaynak='veilox'` kısıtı, `goktungu-merkez`/`goktungu-kopru` " +
        "servis adları, `/opt/goktungu` ve `C:\\goktungu` yolları, Stripe ürün " +
        "anahtarı deseni, Android imza anahtarı, `localStorage` anahtarları " +
        "ve service worker önbellek öneki değiştirilmedi — bunlar marka " +
        "değil çalışan sistem kimliğidir.",

        "ÖLÇÜM: uçtan uca 36/0 (TLS, SNI, yönlendirme, ACME muafiyeti, " +
        "yollar, API, marka gerilemesi), İngilizce sayfa 20/0. ÖLÇÜM " +
        "YÖNTEMİ NOTU: ilk tarayıcı denetiminde sürüm etiketi `{s}` ham " +
        "göründü ve sayaçlar 0 çıktı; bunlar kusur olarak bildirilmedi, " +
        "önce kod okundu. Sürüm asenkron imzalı katalogdan gelir ve yer " +
        "tutucu veri gelmeden KASITLI olarak çözülmez; sayaçlar " +
        "`IntersectionObserver` ile görünürlük eşiğinde tetiklenir. " +
        "Beklemeli ölçümde sürüm \"Version 1.6.0 · reverse WebSocket " +
        "bridge\", sayaçlar 14/4/47 çıktı. Bu sayfada ekran görüntüsüne " +
        "dayanarak kusur bildirmek güvenilir değildir."
      ]
    },
    {
      s: "2.12.3", t: "16 Ağustos 2026",
      d: [
        "ÜRÜN ADI GÖKTUNGU → GÖKTUNGU: kullanıcı kararıyla ürün markası " +
        "GÖKTUNGU oldu; GÖKTUNGU adı kullanıcıya görünen tüm metinlerden " +
        "kaldırıldı. Sayfa başlığı, açıklama üst verisi, paylaşım " +
        "başlığı, hero tanıtım metni, platform bölümü, ön talep " +
        "değerlendirmesi ve ekran görüntüsü alternatif metinleri yeni ada " +
        "çekildi. İngilizce sözlükte aynı geçiş uygulanarak TR = EN " +
        "dengesi korundu.",

        "FİRMA LOGOSU KALDIRILDI, TEK ÜRÜN LOGOSU: üst şeritteki firma " +
        "logosu + ayraç + \"GÖKTUNGU\" yazısından oluşan üç parçalı yapı " +
        "kaldırıldı; yerine ürün adını kendi içinde taşıyan tek GÖKTUNGU " +
        "logosu kondu, böylece ayrı `.urun` yazısı ve `.ayirac` çizgisi " +
        "gereksiz kaldı. Alt bilgideki firma logosu da ürün logosuyla " +
        "değiştirildi.",

        "LOGO İKİ TEMADA ÖLÇÜLDÜ, İKİ SET ÜRETİLDİ: ilk üretimde ana yazı " +
        "beyazdı ve açık temada zeminde kayboluyordu. Tek dosyanın hem " +
        "#04070c hem #f4f6fa zeminde WCAG AA (4,5:1) vermesi olanaksız " +
        "olduğu için tema başına ayrı dosya tutuldu; seçim " +
        "`:root[data-tema=\"acik\"]` CSS kuralıyla yapılıyor, JS gerekmiyor. " +
        "Karşıtlık ölçümü 4/0; en zayıf oran 5,30:1.",

        "ÜST ŞERİT İÇİN ALT YAZISIZ KOMPAKT SÜRÜM: \"KOMUTA KONTROL\" alt " +
        "yazısı 26 px logo yüksekliğinde efektif 3,6 px'e düşüp " +
        "okunmuyordu (ölçüldü). Şeritte alt yazısız sürüm, alt bilgide " +
        "30 px'te okunduğu için alt yazılı tam sürüm kullanılıyor.",

        "SAHİPLİK SATIRI YALNIZ ALT BİLGİDE: firma adı gövde " +
        "metinlerinden çıkarıldı ve telif satırına indirgendi (kullanıcı " +
        "kararı). \"Yalnızca VEILOX üst yöneticisi\" gibi anlatımlar " +
        "\"sistem üst yöneticisi\" olarak yazıldı; kod içindeki " +
        "`\"veilox\"` ROL ADI yetki anahtarı olduğu için DEĞİŞTİRİLMEDİ.",

        "ÇEREZ BANDI SAHİPLİK SATIRINI ÖRTÜYORDU (önceden var olan kusur, " +
        "yeni ölçütle yakalandı): bant `position:fixed; bottom:0` olduğu için " +
        "sayfa akışından çıkıyor ve alt bilgideki telif satırıyla " +
        "20.954 px² örtüşüyordu — ilk ziyarette, bant henüz kabul " +
        "edilmemişken sahiplik satırı okunamıyordu. Marka geçişinden sonra " +
        "firma künyesi yalnız o satırda kaldığı için kusur doğrudan " +
        "sahiplik bildirimini gizler hale geldi. Bant açıkken alt bilgiye " +
        "bandın GERÇEK yüksekliği kadar boşluk konuyor; yükseklik " +
        "`--cerez-yuk` değişkenine yazılıp `ResizeObserver` ile izleniyor, " +
        "çünkü bant metni dile (TR/EN) ve ekran genişliğine göre 1-3 satır " +
        "arası değişiyor ve sabit boşluk EN'de yetersiz kalıyordu.",

        "ÖLÇÜM ARACI KUSURU: künye örtülme ölçümünün ilk sürümü " +
        "`scrollIntoView` çağırıp AYNI iş parçasında " +
        "`getBoundingClientRect` okuyordu. Kaydırma yerleşmediği için kutu " +
        "y=11188 gibi ekran DIŞI bir koordinat döndürüyor, " +
        "`elementFromPoint` null veriyor ve ölçüm SAHTE örtülme kusuru " +
        "bildiriyordu. Kaydırma ayrı adıma alınıp iki ardıl kare beklendi " +
        "ve kutunun görünür alana girdiği doğrulanıyor; ancak bu " +
        "düzeltmeden SONRA gerçek örtülüme kusuru görülebildi.",

        "TEKNİK KİMLİKLER BİLİNÇLİ KORUNDU: `gozcu.veilox.com.tr` canlı " +
        "alan adı, `GOKTUNGU-Kopru-Setup.exe` paket adı, " +
        "`C:\\Program Files\\Goktungu\\Kopru` ve `/opt/goktungu/kopru` dizin " +
        "yolları, `goktungu-kopru_*.deb` paket adı, `window.GOKTUNGU_KITA` " +
        "değişkeni, `goktungu_tema_genel` ve `goktungu_landing_dil` localStorage " +
        "anahtarları marka değil çalışan sistem kimliğidir. Toptan " +
        "değiştirilseydi kırık bağlantı, yanlış kurulum yönergesi ve " +
        "sıfırlanan kullanıcı tercihleri oluşacaktı; bunlar alan adı ve " +
        "paketler yeniden üretildiğinde geçecek."
      ]
    },
    {
      s: "2.12.2", t: "16 Ağustos 2026",
      d: [
        "ÜST ŞERİTTE GİRİŞ/KAYIT DÜĞMELERİ KULLANICI İKONUNA İNDİRİLDİ: " +
        "iki geniş düğme (Kayıt Ol + Giriş Yap) dar ekranda şeride " +
        "sığmıyor, dil seçicinin üzerine taşıyordu; oturum açılıp " +
        "kapandığında şeridin genişliği değiştiği için menü kayıyordu " +
        "(kullanıcı bildirimi). Yerine oturum AÇIK görünümdekiyle aynı " +
        "biçimde tek bir yuvarlak kullanıcı ikonu kondu; giriş, kayıt ve " +
        "harekât arayüzü bağlantısı bu ikonun açılır menüsünde. Şeridin " +
        "genişliği artık oturum durumundan BAĞIMSIZ, dolayısıyla çıkış " +
        "yapıldığında kayma oluşmuyor.",
        "MOBİLDE GİRİŞ YOLU KAYBOLUYORDU (ölçümle yakalandı): oturum " +
        "kabuğu `#anaMenu` içindeydi ve ≤900px'te `#anaMenu{display:none}` " +
        "kuralı tüm navı gizlediği için kullanıcı ikonu da hamburgerin " +
        "arkasında kalıyordu — telefonda ziyaretçinin görünür hiçbir giriş " +
        "yolu yoktu. Kabuk nav DIŞINA, şeridin kalıcı parçası olarak " +
        "taşındı; hamburger en sağa alındı. Yeni sıra: marka | menü | " +
        "oturum | hamburger.",
        "HERO METNİ ORTALANDI: sahne tam genişliğe yayılıp metin altına " +
        "geçtiğinde sola yaslı metin, üstündeki ortalanmış küre ile " +
        "hizasız duruyordu. `.hero-yazi` üzerinde `margin-inline:auto` + " +
        "`text-align:center`; düğme kümesi flex kap olduğu için ayrıca " +
        "`justify-content:center` ile ortalandı. Blok genişliği " +
        "okunabilirlik adına 1040px ile sınırlı tutuldu.",
        "Açılır menü davranışı tek kod yoluna toplandı: oturum açık ve " +
        "kapalı menüleri aynı aç/kapa, dış tıklama ve Escape mantığını " +
        "paylaşır (`MENULER` çifti). İki menü aynı anda açık kalamaz; " +
        "menüden giriş katmanı açıldığında menü kapanır, aksi halde " +
        "katmanın arkasında asılı kalıyordu.",
        "ÖLÇÜM ARACI KUSURU GİDERİLDİ: menü ölçümü hamburgeri `menuDg` " +
        "kimliğiyle arıyordu, gerçek kimlik `menuAc`. Hiçbir seçici " +
        "tutmadığı için hamburger denetimi bugüne kadar SESSİZCE " +
        "atlanmıştı. Doğru kimlik kondu; görünürlük eşiğine ekran içinde " +
        "kalma ve dokunma hedefi ölçütleri eklendi.",
        "Vitrin ölçümü sağlam sayfayı kusurlu bildiriyordu: `loading=lazy` " +
        "görsel `hidden` kapsayıcıda indirilmediği için tıklamadan sonra " +
        "yükleniyor, ölçüm sabit 400 ms bekleyip erken bakıyordu. Sabit " +
        "bekleme yerine görselin `complete` olması bekleniyor (tanı: " +
        "görsel 100 ms sonra 1400x787 hazır, ağ yanıtı 200).",
        "Karşıtlık ölçümüne konuk menüsü eklendi: menü kapalıyken öğeler " +
        "\"görünmüyor\" diye atlanıyor ve karşıtlıkları hiç " +
        "denetlenmiyordu. Ölçüm öncesi menü açılıyor; iki temada da en " +
        "düşük oran 6.20:1 (eşik 4.5)."
      ]
    },
    {
      s: "2.12.1", t: "16 Ağustos 2026",
      d: [
        "HERO DÜZENİ TAM GENİŞLİĞE ALINDI: küre sağ kolonda yarım " +
        "kalıyordu. Sahne artık kenardan kenara uzanan bir şerit " +
        "(`.hero-serit`, yükseklik `clamp(360px, 52vw, 720px)`); başlık, " +
        "açıklama, düğmeler ve sayı künyesi şeridin ALTINA taşındı. Küre " +
        "yarıçapı genişlik yerine YÜKSEKLİĞE oranlanır (`y * 0.47`), " +
        "böylece şeridi dikeyde doldurur ve kavisleri kırpılmaz.",
        "FARE VE PARMAKLA DÖNDÜRME: küre sürüklenerek çevrilebilir. " +
        "Pointer Events ile tek kod yolu fare, kalem ve dokunmayı birlikte " +
        "karşılar; bırakıldığında atalet sönümlenir ve sahne kendi " +
        "salınımına geri yaslanır. `touch-action: pan-y` sayesinde " +
        "telefonda dikey sayfa kaydırması sürüklemeye takılmaz.",
        "Dönüş SINIRLI bir pencerede serbest (yatay ±45°, dikey ±30°). " +
        "Serbest 360° denendi ve geri alındı: 300 px sürükleme 96° " +
        "çevirdiğinde radar mevzii ve dronlar kürenin kenarına itilip " +
        "harekât bölgesi kayboluyordu. 900 px'lik aşırı sürüklemede bile " +
        "mevzi ve İHA'ların görünür kaldığı piksel sayımıyla doğrulandı.",
        "Ölçekleme işlevinde `y2` değişkeni İKİ KEZ tanımlanıyordu (kabın " +
        "yüksekliği ve enlem izdüşümü); ikincisi birincisini eziyor, " +
        "`merkezY` yanlış temele oturuyordu. İkinci değişken `mevziY` " +
        "olarak ayrıştırıldı. Mevzi kayması ayrıca şerit sınırına göre " +
        "tavanlandı; küre hiçbir genişlikte taşmaz.",
        "Küçük ekran ızgara taşması (önceden var olan kusur, yeni ölçütle " +
        "yakalandı): `auto-fit minmax(290px..320px, 1fr)` kullanan üç " +
        "ızgara 360 px genişlikte sayfa gövdesini 9 px yatay kaydırıyordu. " +
        "`min()` kalıbına çevrildi."
      ]
    },
    {
      s: "2.12.0", t: "16 Ağustos 2026",
      d: [
        "HERO TAKTİK ANİMASYONU (yeni: `js/hero_taktik.js`, `js/kita_veri.js`): " +
        "tanıtım sayfası “çok düz” bulunduğu için hero bölümüne canvas " +
        "tabanlı canlı harekât sahnesi eklendi. Ortografik izdüşümle " +
        "çizilen ızgaralı küre (meridyen/paralel), Natural Earth türevi " +
        "gerçek kıta sınırları (42 halka, 829 nokta, 11 KB), Türkiye " +
        "merkezinde tarama huzmesi ve genişleyen menzil halkalarıyla radar " +
        "mevzii, hedef çerçevesi biçiminde beş İHA ikonu ve arkalarında " +
        "sönümlenen uçuş izleri.",
        "Küre serbest dönmüyor: 0-360 tam dönüşte harekât bölgesi zamanın " +
        "yalnız ~%40'ında ön yüzde kalıyor, radar ve dronlar küre arkasına " +
        "geçip eleniyordu. Dönüş, Türkiye'yi merkezde tutan sınırlı bir " +
        "salınıma çevrildi; radar ve İHA'lar her an görünür.",
        "Küre ölçeği iki kez ayarlandı: ilk hal (0.42) Türkiye'yi ~35 px " +
        "genişliğinde bırakıyordu, hedef çerçeveleri zorunlu olarak üst " +
        "üste biniyordu; aşırı yakınlaştırma (1.55) ise küre algısını " +
        "tamamen yok edip kıtaları tanınmaz köşeli parçalara çeviriyordu.",
        "Başarım ve erişilebilirlik: masaüstü ve telefonda 60 FPS; sekme " +
        "arka plana alındığında çizim durur; `prefers-reduced-motion: " +
        "reduce` tercihinde tek kare çizilip animasyon durdurulur " +
        "(piksel karşılaştırmasıyla doğrulandı). Sahne `role=\"img\"` ve " +
        "çevrilebilir `aria-label` taşır; canvas ekran okuyucuya gizlidir.",
        "İKON DİZGESİ (yeni: `js/ikon.js`): yetenek kartlarındaki Unicode " +
        "geometrik karakterler kaldırıldı. İki kart BİREBİR AYNI karakteri " +
        "kullanıyordu; bu karakterler yazı tipine göre farklı çizilir, bazı " +
        "platformlarda hiç çizilmez veya tofu kutusu görünür. Yerine " +
        "`currentColor` ile tema uyumlu, çizgi tabanlı 12 SVG ikon.",
        "İkon çizim kusurları gözle yakalandı (ölçüm “6 farklı SVG var” " +
        "diyerek geçiriyordu): radar ikonunun yayları 24 px kutunun dışına " +
        "taşıp kırpılıyor ve kapalı bir damla gibi görünüyordu (ikinci " +
        "denemede iki yay üst üste binip taralı yarım daireye dönüştü); " +
        "İHA ikonunun pervaneleri yatay çizgiydi ve multikopter değil " +
        "yıldız izlenimi veriyordu. Radar iki eş merkezli daire + tarama " +
        "kaması, İHA dört pervane dairesi + gövde olarak yeniden çizildi.",
        "Kart ikonları marka kırmızısı (`--vurgu`) rengindeydi; kırmızı " +
        "taktik arayüzde uyarı/tehdit rengidir ve altı yetenek kartını bir " +
        "alarm panosu gibi gösteriyordu. Siyana çevrildi, kutu 44→50 px.",
        "EKRAN GÖRÜNTÜSÜ VİTRİNİ (yeni: `js/vitrin.js`): altı görüntünün " +
        "eşit ağırlıkta dizildiği ızgara kaldırıldı; yerine ikonlu sekme " +
        "listesi ve tarayıcı çerçeveli tek büyük görsel geldi. Her kare " +
        "teknik ölçüt taşıyan bir `figcaption` alt yazısıyla açıklanır. " +
        "Sekmeler klavyeyle gezilebilir (`role=tablist`, ok tuşları, " +
        "Home/End) ve `aria-selected` bildirir; mobilde yatay kaydırılır.",
        "KUSUR (vitrinle ilgisiz, yeni ölçütle ortaya çıktı): fiyatlandırma " +
        "koşulları ızgarası `minmax(320px,1fr)` kullanıyordu; 360 px " +
        "telefon ekranında kabın iç genişliği ~312 px kaldığı için ızgara " +
        "320 px'e zorluyor ve SAYFA GÖVDESİ 9 px yatay kayıyordu. 290 px " +
        "ve üstü tüm `auto-fit` ızgaraları `min(<değer>,100%)` kalıbına " +
        "çevrildi.",
        "ÖLÇÜM ARACI KUSURU: `olc_karsitlik.py` içindeki `ADRES` sabiti " +
        "komut satırı argümanını eziyordu; yerel adres verilse bile CANLI " +
        "site ölçülüyor, yerel değişiklikler hiç denetlenmiyor ve canlıdaki " +
        "eski sürümün kusurları yerel kusur gibi raporlanıyordu. Ayrıca " +
        "zemin arayışı yalnız `backgroundColor`'a bakıyordu: gradyanla " +
        "verilen zeminlerde saydam değere düşüp metinle zemini aynı sayarak " +
        "1.21:1 gibi sahte okunmazlık kusurları üretiyordu."
      ]
    },
    {
      s: "2.11.1", t: "16 Ağustos 2026",
      d: [
        "KUSUR (v2.11.0 ile girdi, tarayıcıda ölçülerek yakalandı): kapalı " +
        "açılır menü kutuları ekranda yer kaplamaya devam ediyordu. " +
        "`.mg-kutu{display:flex}` sınıf kuralı, HTML'deki `hidden` " +
        "niteliğinin tarayıcı varsayılanı olan `display:none` değerini " +
        "eziyordu. Kutular mutlak konumlu olduğu için KAPALI " +
        "\u201CYetenekler\u201D kutusundaki \u201CGüvenlik\u201D bağlantısı, " +
        "AÇIK \u201CSistem\u201D kutusundaki \u201CSaha Yazılımı\u201D " +
        "bağlantısının üstüne biniyor ve tıklamayı engelliyordu; kullanıcı " +
        "menüden Saha Yazılımı bölümüne geçemiyordu.",
        "Düzeltme: `[hidden]{display:none !important}` genel kuralı eklendi. " +
        "`hidden` niteliği artık tüm sayfada display kurallarını yener; " +
        "sözleşme yalnız menüye değil sayfanın tamamına uygulanır.",
        "Mobil düzende (900 px ve altı) kutuların bilinçli olarak açık " +
        "kalmasını sağlayan kural, dosya sırasına değil özgüllüğe " +
        "dayanacak biçimde `.mg-kutu[hidden]` seçicisine taşındı; kural " +
        "sıralaması değiştiğinde mobil menünün sessizce bozulması önlendi.",
        "Düz menü maddelerine `white-space:nowrap` eklendi.",
        "ÖLÇÜM ARACI KUSURU giderildi: taşma ölçümü satır sayısını " +
        "`offsetHeight / lineHeight` ile hesaplıyordu. Düz menü " +
        "maddelerinde ölçülen öğe <a> olduğu ve dikey dolguyu içerdiği " +
        "için tek satırlık \u201CFiyatlandırma\u201D sahte olarak " +
        "\u201C2 satır\u201D bildiriliyordu. Ölçüm, dolguyu hariç tutan " +
        "Range.getClientRects() yöntemine çevrildi."
      ]
    },
    {
      s: "2.11.0", t: "16 Ağustos 2026",
      d: [
        "Üst şerit menüsü gruplandı: Mimari/Platformlar/Saha Yazılımı " +
        "\u201CSistem\u201D, Yetenekler/Arayüz/Güvenlik \u201CYetenekler\u201D " +
        "açılır grubu altında toplandı; Fiyatlandırma düz madde kaldı.",
        "KUSUR: hamburger menü yalnız 760 px altında devreye girdiği için " +
        "760-1200 px arası genişliklerde yedi menü maddesi, tema düğmesi, " +
        "dil seçici ve oturum düğmeleri tek satıra sığmıyordu; " +
        "\u201CSaha Yazılımı\u201D iki satıra kırılıyor, sağdaki düğmeler taşıyordu.",
        "Hamburger eşiği 900 px'e yükseltildi; ara genişliklerde taşma giderildi.",
        "Açılır gruplar klavyeyle kullanılabilir: aria-expanded, Escape ile " +
        "kapanma, odak gruptan çıkınca kapanma, dış tıklama ile kapanma.",
        "Mobilde (900 px ve altı) gruplar açılır kutu değil, başlıklı düz " +
        "liste olarak diziliyor."
      ]
    },
    {
      s: "2.10.1", t: "16 Ağustos 2026",
      d: [
        "Fiyatlandırma ve çağrı düğmelerindeki yedi doğrudan panel " +
        "bağlantısı giriş/kayıt katmanına bağlandı; yetkisiz kullanıcı " +
        "artık 403 sayfası yerine giriş formu görüyor.",
        "Oturum bileşeninde dil okuması tek yardımcıya toplandı; " +
        "betik sırası değişse bile kalan süre ve rol adı doğru dilde " +
        "yazılıyor."
      ]
    },
    {
      s: '2.10.0', t: '2026-08-16',
      d: [
        'GİRİŞ VE KAYIT ARTIK TANITIM SAYFASINDA. Ziyaretçi giriş ve ' +
        'kurum kaydı için kurumsal panele yönlendirilmiyor; her ikisi de ' +
        'sayfa üzerindeki katmanda tamamlanıyor (js/oturum.js). Kayıt ' +
        'işlemi kurumu ve ilk yönetici hesabını tek istekte açar, ' +
        'deneme aboneliği anında başlar.',

        'KULLANICI MENÜSÜ VE MÜŞTERİ PANELİ. Oturum açıldığında üst ' +
        'şeritteki giriş düğmeleri kullanıcı menüsüne dönüşür; menüde ad, ' +
        'e-posta, kurum ünvanı, rol ve oturumun kalan süresi görünür. ' +
        '"Müşteri Paneli" ögesi kurumsal paneli AYRI SEKMEDE açar ' +
        '(target="_blank" + rel="noopener").',

        'PAYLAŞILAN OTURUM. Sunucu oturum çerezini Path=/ ile yazdığı ' +
        'için tanıtım sayfası ile kurumsal panel aynı oturumu görür; yeni ' +
        'sekmede kimlik yeniden sorulmaz. Çerez HttpOnly olduğundan jeton ' +
        'JavaScript ile okunamaz, oturum durumu yalnız /api/firma/ben ' +
        'yanıtından öğrenilir.',

        'OTURUM SÜRESİ TEK KAYNAKTAN. Çerezin Max-Age değeri dört ayrı ' +
        'yerde sabit 12 saat yazılıydı; jetonun veritabanı ömrü ise ' +
        'oturum_saat ayarından geliyordu. Ayar 12 dışında bir değere ' +
        'çekildiğinde çerez ile jeton farklı zamanlarda ölüyor, kullanıcı ' +
        'süresi dolmamış oturumla dışarı atılıyordu. İkisi artık aynı ' +
        'ayardan üretiliyor; arayüz kalan süreyi gösterir ve süre ' +
        'dolmadan kısa bir pay bırakıp oturumu kendiliğinden kapatır.',

        'ROL KAPISI (GÜVENLİK). Kurumsal panelin yetki denetimi rol ' +
        'ayrımı yapmıyordu: geçerli oturumu olan her firma kullanıcısı — ' +
        'pilot ve gözlemci dahil — tüm kurumsal uçlara erişebiliyordu. ' +
        'Rol denetimi uçların içinde tek tek elle yapıldığı için bir ' +
        'bölümü korunuyor, bir bölümü korunmuyordu. Taşıma katmanına ' +
        'firma_yonetici yetki düzeyi eklendi; ekip yönetimi, merkez ' +
        'lisansı, ödeme ve üyelik talebi uçları bu düzeye taşındı. ' +
        '/company/ sayfası da pilot oturumuyla açılamaz.',

        'ÖLÜ İNDİRME ANAHTARLARI TEMİZLENDİ. v2.9.0 ile kaldırılan ' +
        'indirme kartlarından artakalan 12 çeviri anahtarı sözlükten ' +
        'çıkarıldı; alt bilgi ve indirme kapısı bağlantıları giriş ' +
        'katmanını açacak biçimde bağlandı.'
      ]
    },
    {
      s: '2.9.0', t: '2026-08-16',
      d: [
        'TAKTİK HAREKÂT TEMASI (v3) UYGULANDI. Sayfanın görsel kimliği ' +
        'komuta kontrol sembolojisinden türetilen palete geçirildi: ' +
        'mürekkep laciverdi zemin (#04070c), dost/sistem göstergesi için ' +
        'çelik-siyan (#5cc8ff), iz ve uyarı göstergesi için kehribar ' +
        '(#f2b24a). Önceki palette taktik gösterge olarak kullanılan genel ' +
        'mavi (#2f7fd4) siyana devredildi. VEILOX marka kırmızısı ' +
        '(#b91c1c) logo, birincil düğme ve başlık vurgusunda korundu; ' +
        'marka kimliği ile harekât dili birbirinden ayrıldı.',
        'TİPOGRAFİ DEĞİŞTİ. Başlıklar Chakra Petch, gövde metni IBM Plex ' +
        'Sans, teknik değerler ve sınıflandırma bantları IBM Plex Mono ile ' +
        'yazılıyor. Yazı tipleri CSS değişkenlerine bağlandı (--baslik, ' +
        '--govde, --mono); gövdede sabit yazılmış yedi Consolas bildirimi ' +
        'değişkene çevrildi, böylece tipografi tek noktadan yönetiliyor.',
        'KÖPRÜ İNDİRME BAĞLANTISI KALDIRILDI. Kurulum dosyalarının ' +
        'siteden doğrudan dağıtılmaması kararı arayüze de yansıtıldı: ' +
        'hero bölümündeki "Köprü Yazılımını İndir" düğmesi Kurumsal Panel ' +
        'yönlendirmesine çevrildi, indirme kartları ve SHA-256 tablosu ' +
        'kaldırıldı, yerine kurumsal panele yönlendiren dört adımlı bir ' +
        'bölüm konuldu. SHA-256 doğrulaması indirme anında kurumsal ' +
        'panelde gösterilmeye devam ediyor.',
        'ÖLÜ İNDİRME BAĞLANTILARI GİDERİLDİ. Ölçüldü: indirme kartları ' +
        'bağlantıyı /indir/<dosya> biçiminde kuruyordu, deponun gerçek ' +
        'yolu ise /indir/<ürün>/<sürüm>/<dosya>. Bu yüzden sayfadaki her ' +
        'indirme düğmesi 404 dönüyordu. Sunucu tarafı doğru davranıyordu ' +
        '(oturumsuz istek 403). Kartlar kaldırıldığı için ölü bağlantılar ' +
        've erişilemeyen SHA256SUMS.txt bağlantısı ortadan kalktı.',
        'AYDINLIK TEMA YENİ PALETE UYARLANDI. Çelik-siyan ve kehribar ' +
        'aydınlık zeminde yeterli karşıtlık üretmediği için (ölçüldü: ' +
        'parlaklık > 150) açık temada koyulaştırılmış karşılıkları ' +
        'kullanılıyor: #0f6c9e ve #9a6a12. Gövdede sabit yazılmış siyan ' +
        'zeminler için açık tema kuralları ayrıca tanımlandı.',
        'İNGİLİZCE SÖZLÜK BOŞLUĞU KAPATILDI. Mimari bölümündeki dört ' +
        'anahtarın (Video Servisi, GroundGCC Servisi ve alt açıklamaları) ' +
        'İngilizce karşılığı hiç yazılmamıştı; İngilizceye geçildiğinde bu ' +
        'satırlar Türkçe kalıyordu. Eklendi. Ölçüm: HTML 235 anahtar, ' +
        'sözlük 249 karşılık, eksik 0.'
      ]
    },
    {
      s: '2.8.0', t: '2026-08-16',
      d: [
        'GÜNDÜZ / GECE TEMASI EKLENDİ. Sayfa bugüne kadar yalnızca ' +
        'karanlık harekât temasıyla yayınlanıyordu; artık üst çubuktaki ' +
        'tema düğmesiyle aydınlık temaya geçilebiliyor. Seçim tarayıcıda ' +
        'saklanır ve sonraki ziyaretlerde korunur; hiç seçim yapılmamışsa ' +
        'işletim sisteminin tercihi (prefers-color-scheme) uygulanır. ' +
        'Bileşen dört panelle ortaktır: /js/tema.js.',
        'AYDINLIK TEMADA OKUNABİLİRLİK ÖLÇÜLDÜ VE DÜZELTİLDİ. Sayfa ' +
        'gövdesindeki sabit renkler tek tek tarandı; parlaklığı 150 ' +
        'üzerinde olan 8 metin rengi (kırmızı #f0a5a5, maviler #8fb8dd ve ' +
        '#8fc0ee) aydınlık zeminde okunamıyordu. Bunlar koyu karşılıklarına ' +
        'bağlandı: indirme etiketleri ve yasal uyarı vurguları koyu ' +
        'kırmızıya, önerilen paket etiketi / kurulum adımı kod blokları / ' +
        'SHA-256 bağlantıları / çerez bandı bağlantısı / yasal metin ' +
        'bağlantıları / fiyat adım numaraları koyu maviye. Doğrulama: ' +
        'kapsanmayan açık renk metin sayısı 0.',
        'Aydınlık temada üst çubuğun yarı saydam zemini, hero bölümünün ' +
        'dekoratif ışıma katmanları, kart gölgeleri, ekran görüntüsü ' +
        'çerçeveleri ve alt bilgi zemini ayrıca uyarlandı; koyu zemin ' +
        'varsayan "koyu" bölümü aydınlık karşılığına çevrildi. Toplam ' +
        '26 aydınlık tema kuralı yazıldı.',
        'Önbellek etiketleri sürümle hizalandı (stil.css ve tema.js ' +
        '?v=280). Etiket sürümden ayrı kaldığında tarayıcı eski dosyayı ' +
        'sunduğu için kullanıcı yeni temayı hiç görmüyordu; bu kusur ' +
        'daha önce kurumsal ve yönetim panellerinde de yaşandığı için ' +
        'her teslimde etiket denetimi sınava alındı.'
      ]
    },
    {
      s: '2.7.0', t: '2026-08-16',
      d: [
        'Sayfa, kurumun onayladığı yeni tasarımla yeniden kuruldu. ' +
        'Önceki sayfa 959 satırdı; yeni tasarım 1718 satır ve bölüm ' +
        'gövdeleri genişletilmiş durumda. Stil ve betik sayfanın kendi ' +
        'içinde gömülü geldiği için dış CSS bağımlılığı kalmadı; ' +
        'karanlık harekât teması, radar sahnesi ve telemetri şeridi ' +
        'tasarımın kendi bileşenleridir.',
        'KURULUM PAKETİ BAĞLANTILARI KALDIRILDI. Kurum kararı gereği ' +
        'tanıtım sitesinde doğrudan indirme bağlantısı yayımlanmıyor; ' +
        'paketler yalnızca kurumsal panelden, kurum oturumu ile ' +
        'indiriliyor. Sayfadaki iki indirme kartı ile hero bölümündeki ' +
        '"Köprü Yazılımını İndir" düğmesi kurumsal panele yönlendirildi ' +
        've bunun nedenini açıklayan bir uyarı notu eklendi. Kaldırılan ' +
        'bağlantılar: /indir/windows, /indir/ubuntu. Doğrulama: sayfada ' +
        '/indir/ geçişi sıfır.',
        'DONUK SÜRÜM YAZILARI KALDIRILDI. Yeni tasarım beş yerde sabit ' +
        'sürüm yazıyordu (1.1.1 ve 1.4.2): telemetri şeridi, hero ' +
        'rozeti, protokol karşılaştırma başlığı, apt kurulum komutu ve ' +
        'alt bilgi. Bu değerler elle güncellendiği sürece sayfa ile ' +
        'indirilen paket kaçınılmaz olarak ayrışıyordu. Beşi de ' +
        'imzalı sürüm deposundan (/api/genel/katalog) doldurulan yer ' +
        'tutucuya çevrildi; uç erişilemezse sayfadaki değer bozulmadan ' +
        'kalır.',
        'Site sürüm defteri (Hakkında) alt bilgiye eklendi; sayfa kendi ' +
        'sürümünü ürün sürümünden bağımsız yürütmeye devam ediyor.',
        'İngilizce sözlük dengesi korundu: yeni bölümlerin karşılıkları ' +
        'eklendi ve hero düğmesinin karşılığı "Download the Bridge" ' +
        'yerine "Corporate Panel" olarak düzeltildi.',
        'Nitelik çevirisi altyapısı eklendi: yeni tasarımın gömülü dil ' +
        'betiği yalnızca öğe metnini çevirebiliyordu, ipucu (title) gibi ' +
        'nitelikleri çeviremiyordu. Artık "title:anahtar" biçimi ' +
        'destekleniyor.'
      ]
    },
    {
      s: '2.6.2', t: '2026-08-16',
      d: [
        'Sayfadaki ürün sürümü kusuru giderildi: sürüm bilgisi artık ' +
        'canlı sürüm deposundan (/api/genel/katalog) okunuyor. Eski ' +
        'kaynak olan statik /indir/surumler.json dosyası depo ' +
        'veritabanına geçilirken kaldırılmıştı ve 404 dönüyordu; hata ' +
        'sessizce yutulduğu için hero rozeti 1.1.1 değerinde donuk ' +
        'kalmış, alt bilgi ile protokol başlığındaki {s} yer tutucuları ' +
        'ham metin olarak görünüyordu. Savunma müşterisine giden bir ' +
        'sayfada indirilen paketle sayfadaki sürümün ayrılması güven ' +
        'kırıcı olduğu için tek doğruluk kaynağı imzalı depo yapıldı.',
        'Katalog okuma hatası artık tarayıcı konsoluna uyarı olarak ' +
        'düşüyor; sessiz yutma kaldırıldı.',
        'Vitrinde ürün başına yalnızca en güncel sürüm gösteriliyor; ' +
        'sürüm karşılaştırması sayısal yapılıyor (1.4.10 > 1.4.9).'
      ]
    },
    {
      s: '2.6.1', t: '2026-08-16',
      d: [
        'Siteye bağımsız sürüm defteri ve Hakkında bölümü eklendi; ' +
        'alt bilgideki ürün sürümü rozetinden ayrı yürütülüyor.',
        'Yazılım indirme yönlendirmesi netleştirildi: Köprü ve Merkez ' +
        'Uygulama kurulum paketleri siteden doğrudan verilmiyor, ' +
        'yalnızca kurumsal panelden oturum açılarak indiriliyor.'
      ]
    },
    {
      s: '2.6.0', t: '2026-08-15',
      d: [
        'Tanıtım sitesi yeni tasarımla yayınlandı: mimari, yetenekler, ' +
        'platformlar, güvenlik ve kurulum bölümleri.',
        'TR/EN dil desteği eklendi; HTML\'deki Türkçe metin kaynak ' +
        'kabul edilir, İngilizce sözlükten yazılır.',
        'Fiyatlandırma ve ön talep değerlendirme anlatımı eklendi: ' +
        'üyelik ücretsiz, ilk pilot ve yönetici ücretsiz; ek pilot ' +
        'koltuğu, paket seçenekleri ve yıllık indirim açıklandı.',
        'Çerez bildirimi ve yasal metin bağlantıları eklendi.'
      ]
    }
  ]
};

/* FAZ18-IS5-DESTEK-USTCUBUK */
