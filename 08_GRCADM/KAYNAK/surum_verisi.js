/* =====================================================================
   GOKTUNGU YONETIM PANELI — BAGIMSIZ SURUM DEFTERI
   ---------------------------------------------------------------------
   Bu panel kendi surum numarasini yurutur; GCS (app) ve kurumsal panel
   surumlerinden BAGIMSIZDIR.  Her teslimde `surum` + `tarih` guncellenir
   ve `gecmis` listesinin BASINA yeni kayit eklenir (en yeni en ustte).

   Onbellek etiketi: `index.html` icindeki `?v=` degerleri bu surumle
   ayni tutulur (nokta yerine rakam: 1.1.0 -> 110).
   ===================================================================== */
'use strict';

window.PANEL_SURUM = {
  ad: 'GÖKTUNGU Yönetim Paneli',
  surum: '1.2.5',
  tarih: '2026-08-19',
  telif: '© 2026 Türkbey Teknoloji Anonim Şirketi',
  gecmis: [
    {
      s: "1.2.5", t: "19 Ağustos 2026",
      d: [
        /* FAZ18-IS1214-DEFTER */
        "Panel acilisinda olusan teknik hatalar artik gizlenmiyor. " +
        "Onceki davranista her hata sessizce giris ekranina donusuyordu; " +
        "yonetici gecerli oturumla bile giris ekrani gorup nedenini " +
        "ogrenemiyordu.",
        "Yetki hatasi (401/403) ile teknik hata birbirinden ayristirildi. " +
        "Yetki hatasinda giris ekrani sessizce gosterilir; teknik hatada " +
        "ek aciklama gosterilir ve tarayici konsoluna yigin izi yazilir.",
        "Hata mesaji, sorunun oturumla ilgili OLMADIGINI ve hangi asamada " +
        "olustugunu (oturum dogrulama / arayuz kurulumu) bildiriyor.",
        "Grafiklerde cubuk genisligine ust sinir konuldu. Tek gunluk veri " +
        "bulundugunda cubuk grafik genisliginin ucte ikisini kaplayacak " +
        "kadar sisiyordu; artik en fazla 48 piksel genisliginde cizilir " +
        "ve cubuklar sola yaslanir.",
        "Grafiklerin oran korumasi duzeltildi; onceki ayar dar ekranlarda " +
        "cizimi yatay olarak deforme ediyordu.",
        "Dort grafik islevindeki (gosterge, guvenlik, telemetri, ucus " +
        "rotasi) tum sabit renkler tema degiskenlerine baglandi. Ucus " +
        "rotasi grafiginin KENDI ZEMINI sabit koyu oldugu icin acik " +
        "temada panel beyazlarken grafik koyu bir kare olarak kaliyor ve " +
        "tema gecisini gorsel olarak kiriyordu.",
        "Veri serilerinin renk ayrimi korundu: irtifa ve hiz serileri " +
        "ayri degiskenlere baglidir, efsane isaretleri de seriyle ayni " +
        "degiskeni kullanir; aksi halde efsane yanlis seriyi gosterirdi.",
      ],
    },
    {
      s: "1.2.4", t: "19 Ağustos 2026",
      d: [
        /* FAZ18-IS10-DEFTER */
        "Gunlukler bolumu eklendi. Uygulama (merkez ve app), isletim " +
        "sistemi (journald) ve ag katmani (fail2ban) kayitlari tek " +
        "arayuzden okunabiliyor.",
        "Duzey (hata / uyari / guvenlik / bilgi), metin arama, servis " +
        "birimi ve satir sayisi suzgecleri eklendi; isletim sistemi " +
        "kayitlarinda zaman araligi suzgeci de kullanilabiliyor.",
        "Uygulama kayitlari tarih damgasi tasimadigi icin o kaynakta " +
        "zaman araligi suzgeci gosterilmiyor; arayuz bu sinirlamayi " +
        "kaynak bazinda acikca bildiriyor.",
        "Kayitlarda jeton, sifre ve yetkilendirme basliklari " +
        "goruntulenmeden once maskeleniyor.",
        "Dondurulen (rotasyona girmis) gunluk dosyalari da okunuyor; " +
        "duz ve sikistirilmis bicimlerin ikisi de destekleniyor, " +
        "boylece gunluk gecmisi rotasyon sonrasi kaybolmuyor.",
        "Veritabani gunlukleri dosya izinleri nedeniyle kapsam disi; " +
        "arayuz bunu belirsizlik olarak degil acik bir durum olarak " +
        "bildiriyor.",
      ],
    },
    {
      s: "1.2.3", t: "19 Ağustos 2026",
      d: [
        /* FAZ18-IS9-DEFTER */
        "Guvenlik / Saldiri Izleme bolumu eklendi. Uygulama katmani " +
        "kaba kuvvet korumasi, kalici blok gecmisi ve ag katmani " +
        "(fail2ban) yasaklari tek gorunumde birlestiriliyor.",
        "Blok gecmisi gunluk cubuk grafigi, IP'ye gore gruplama ve " +
        "sucun hangi uctan geldigini gosteren uc listesi eklendi.",
        "Etkin bloklar dogrudan panelden cozulebiliyor; hesap kilidi " +
        "ve IP blogu ayri ayri kaldirilabiliyor.",
        "Bellek kaynakli sayaclarin servis yeniden baslatmasinda " +
        "sifirlandigi arayuzde acikca bildiriliyor; yonetici yeniden " +
        "baslatma sonrasi bos listeyi 'saldiri yok' sanmiyor.",
        "Tarih damgasi tasimayan eski koruma kayitlari toplam ve IP " +
        "gruplamasina dahil ediliyor, gun dagilimindan ayri " +
        "bildiriliyor; boylece o adresler gorunurlugunu kaybetmiyor.",
        "Esik sozlesmesi (deneme sayisi, pencere, ceza suresi) ve " +
        "yerel ag muafiyeti panelde belgelendi.",
      ],
    },
    {
      s: "1.2.2", t: "18 Ağustos 2026",
      d: [
        /* FAZ16-DEFTER */
        "Ust seride amblem eklendi. Amblem yuksekligi ust serit yazi " +
        "boyutundan turetiliyor (16 px yazi -> 26 px amblem).",
        "Amblem uc boyutlu salinim ve fare yaklasma tepkisi kazandi; " +
        "isletim sistemi hareket azaltma ayarina uyuluyor.",
      ],
    },
    {
      s: "1.2.1", t: "18 Ağustos 2026",
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
        "Panel `admin.goktungu.com` alt alan adindan aciliyor. " +
        "`/admin/` yolu calismaya devam ediyor; Merkez Uygulama " +
        "kurulumlari yol tabanli erisimi kullaniyor.",
        "Giriş kartı logosu 34 px'ten 44 px'e büyütüldü; sistem " +
        "genelindeki tek logo ölçek sözleşmesine bağlandı.",

        "ÖNBELLEK ETİKETİ KUSURU: panelin altı varlığı `?v=` (boş " +
        "değer) etiketiyle sunuluyordu. Boş etiket her istekte aynı " +
        "URL'yi ürettiği için tarayıcı önbelleği hiçbir teslimde " +
        "geçersizleşmiyordu — panel 1.2.0'a yükseltilmiş olmasına " +
        "rağmen kullanıcılar eski dosyaları görmeye devam ediyordu. " +
        "Etiketler panel sürümüne bağlandı (`?v=121`).",

        "Giriş ekranı küresini çizen `hero_taktik.js` ve " +
        "`kita_verisi.js` betikleri hiç etiket taşımıyordu; ızgara " +
        "görünürlük düzeltmesi bu panelde uygulanmayacaktı. Etiket " +
        "eklendi."
      ]
    },
    {
      s: '1.2.0', t: '2026-08-17',
      d: [
        'Ürün adı GÖKTUNGU olarak değişti; GÖKTUNGU adı panelden ' +
        'tamamen kaldırıldı. Giriş başlığı, üst şerit markası ve ' +
        'sekme başlığı yeni ada çekildi.',
        'Panel adı "VEILOX Yönetim Paneli" → "GÖKTUNGU Yönetim ' +
        'Paneli" oldu; telif satırı "Türkbey Teknoloji Anonim ' +
        'Şirketi" tam ünvanına çevrildi.',
        'Giriş ekranındaki "VEILOX Savunma A.Ş." alt satırı ' +
        'kaldırıldı: firma adı artık yalnızca sahiplik satırında ' +
        'görünüyor.',
        'Özellik ve lisans metinlerindeki "yalnızca VEILOX açar" ' +
        'ibaresi "yalnızca üst yönetici açar" olarak düzeltildi. ' +
        'Radar ve GCCDUAL yetkisinin kime ait olduğu aynı kaldı; ' +
        'yalnızca marka adı yerine rol adı yazıldı.',
        'Yetki kaynağı rozetindeki `veilox` kod değeri DEĞİŞMEDİ — ' +
        'bu üst yönetici yetki anahtarıdır, marka değildir.'
      ]
    },
    {
      s: '1.1.1', t: '2026-08-16',
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
        'kullanıcı elle seçtiğinde kendi seçimi geçerli oluyor ve ' +
        'tarayıcıda kalıcı saklanıyor.',
        'Açık temada yönetim paneli mavi vurgu rengini koruyor; ' +
        'kurumsal panelin teal vurgusundan ayrı kalıyor ki hangi ' +
        'panelde çalışıldığı bir bakışta anlaşılsın.',
        'Durum rozetleri, bildirimler ve uyarı kutuları açık tema için ' +
        'ayrıca karşılandı; koyu zeminli rozetler açık arka planda ' +
        'okunmaz kalmıyor.',
        'Geçersiz bir CSS renk değeri temizlendi: bağlantısı kopmuş ' +
        'sunucu noktasının zemininde bozuk bir değer duruyordu.',
        'Önbellek etiketleri 1.1.0 sürümüne hizalandı (stil dosyası ' +
        'dahil).'
      ]
    },
    {
      s: '1.0.0', t: '2026-08-16',
      d: [
        'Panele bağımsız sürüm defteri ve Hakkında bölümü eklendi.',
        'Önbellek etiketi eklendi: panel dosyaları sürüme bağlı ' +
        'etiketle sunuluyor, tarayıcı eski kopyayı göstermiyor.',
        'Müşteriler, kullanıcılar, uçuş ve video kayıtları, sunucular, ' +
        'abonelikler, paket sürümleri ve denetim izi bölümleri.',
        'Radar ve GCCDUAL yetkileri kurum bazında yalnızca bu panelden ' +
        'açılıp kapatılıyor; satışa konu değil.',
        'Merkez Uygulama lisansı (5.000 $ tek seferlik) kurum bazında ' +
        'bu panelden tanımlanıyor; ödeme akışı atlanabilir.'
      ]
    }
  ]
};
