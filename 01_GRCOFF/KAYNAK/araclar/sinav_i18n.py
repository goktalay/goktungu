#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GOKTUNGU - I18N (TR/EN) BUTUNLUK DENETIMI
======================================

NEDEN BU ARAC VAR
-----------------
Kullanici bildirdi: "ingilizceye cevirdigimde sistemin bir kismi
ceviriliyor bir kismi hala turkce". Bu, gozle taranamayacak bir borc:
arayuz onlarca JS modulunde uretiliyor ve her modulde metin ya
`I18N`/`DILLER` sozlugunden geliyor ya da dogrudan koda gomulu.

Gomulu Turkce metin CALISMA ANINDA HATA URETMEZ. Konsolda tek satir
uyari cikmaz; kusur yalnizca dil EN'e alindiginda ekranda gorunur.
Bu yuzden makineyle olculmesi gerekir.

NE OLCER
--------
1. SOZLUK DENGESI: TR'de olup EN'de olmayan (ve tersi) anahtarlar.
   Bir anahtar EN'de yoksa `applyLanguage` TR degerine duser ->
   Ingilizce arayuzde Turkce metin gorunur.

2. EN'DE TURKCE KALMIS DEGERLER: EN sozlugundeki bir deger Turkce'ye
   ozgu harf (ç ğ ı ö ş ü) veya bilinen Turkce kelime iceriyorsa
   ceviri yapilmamis demektir.

3. JS'E GOMULU TURKCE DIZELER: JS dosyalarinda sozluk uzerinden
   gecmeyen, dogrudan yazilmis Turkce kullanici metinleri.

4. HTML'DE data-i18n OLMAYAN TURKCE METIN: statik HTML metni
   `data-i18n` nitelegi tasimazsa `applyLanguage` dongusu onu
   kapsamaz -> hic cevrilmez.

CIKIS
-----
Bulgular hem ekrana ozet hem `rapor_i18n.json` olarak yazilir; ikinci
asamada (ceviri yazma) bu JSON girdi olarak kullanilir.
"""

import json
import os
import re
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _js_dizin_bul(kok):
    """`js/` dizinini her iki klasor duzeninde bulur.

    v2.4.52 oncesi arac `<kok>/goktungu/js` sabitini kullaniyordu; o yol
    hicbir duzende yok ve arac sessizce cokuyordu.

    Ikinci kusur kurulumda ortaya cikti: kurulu duzende bu dosya
    `<goktungu>/assets/python/araclar/` altindadir, dolayisiyla iki ust
    dizin `<goktungu>/assets/python` eder ve `js/` orada DEGILDIR --
    `<goktungu>/assets/web/js` altindadir. Bu yuzden adaylar yalniz
    verilen kokte degil, ust dizinlerde de sirayla denenir.
    """
    d = os.path.abspath(kok)
    for _ in range(4):                 # <goktungu> en fazla 4 ust dizinde
        for aday in (os.path.join(d, "js"),
                     os.path.join(d, "assets", "web", "js"),
                     os.path.join(d, "goktungu", "js")):
            if os.path.isfile(os.path.join(aday, "i18n.js")):
                return aday
        ust = os.path.dirname(d)
        if ust == d:
            break
        d = ust
    return os.path.join(kok, "js")


JS_DIZIN = _js_dizin_bul(KOK)
GOKTUNGU = os.path.dirname(JS_DIZIN)

TR_HARF = set("çğıöşüÇĞİÖŞÜ")

# Turkce'ye ozgu harf tasimayan ama Turkce olan yaygin kelimeler.
# EN sozlugunde bunlar gorunuyorsa ceviri yapilmamistir.
TR_KELIME = re.compile(
    r"\b("
    r"ve|veya|ile|icin|için|bir|bu|su|şu|olarak|yok|var|acik|açık"
    r"|kapali|kapalı|baglanti|bağlantı|dron|hedef|kaydet|iptal|sil"
    r"|duzenle|düzenle|ekle|secin|seçin|girin|yukle|yükle|indir"
    r"|baslat|başlat|durdur|goster|göster|gizle|ayarlar|hata|uyari"
    r"|uyarı|bilgi|tamam|evet|hayir|hayır|toplam|adet|sayisi|sayısı"
    r"|durum|deger|değer|isim|adi|adı|tarih|saat|dakika|saniye"
    r"|yukseklik|yükseklik|irtifa|hiz|hız|mesafe|konum|harita"
    r"|pencere|panel|liste|kayit|kayıt|kullanici|kullanıcı|sifre|şifre"
    r"|gonder|gönder|al|ver|yeni|eski|son|ilk|tum|tüm|hepsi|bos|boş"
    r"|dolu|aktif|pasif|calisiyor|çalışıyor|bekleniyor|tamamlandi"
    r"|tamamlandı|basarili|başarılı|basarisiz|başarısız|gecersiz"
    r"|geçersiz|zorunlu|opsiyonel|onay|red|kabul|olcum|ölçüm"
    r")\b",
    re.IGNORECASE,
)

# Ingilizce'de de gecen, yanlis alarm ureten kelimeler.
# ("var" JS anahtar kelimesi, "al" kisaltma, "son" Ingilizce kelime...)
TR_KELIME_YOKSAY = {"var", "al", "son", "bu", "su", "ile", "bir", "ve"}

# KAPSAM DISI DOSYALAR — gerekce zorunlu.
# Bu dosyalardaki Turkce metin arayuz metni degildir ya da cevirisi
# baska bir dosyada zaten mevcuttur; ceviri borcu olarak sayilmaz.
KAPSAM_DISI = {
    # ArduPilot parametre aciklamalarinin Turkce sozlugu. Ingilizce
    # karsiligi `param_aciklama.js` dosyasinda mevcut ve
    # `dronlar.js` aktif dile gore dogru sozlugu seciyor.
    "param_aciklama_tr.js": "Ingilizce karsiligi param_aciklama.js'de",
    # Surum gecmisi maddeleri: arayuz metni degil, degisiklik kaydi.
    # Kullanici bunlari Turkce okuyor; cevirisi istenmedi.
    "surum.js": "Surum gecmisi maddeleri, arayuz metni degil",
}


def js_dizeleri(metin):
    """JS kaynagindan dize sabitlerini (tek/cift tirnak, backtick) cikarir.

    Yorum satirlarini atlar: yorumlardaki Turkce aciklamalar kusur
    degildir, aksine kod belgelemesidir.
    """
    # Satir yorumlarini ve blok yorumlarini kaldir.
    #
    # v2.4.34 SATIR NUMARASI KORUMASI: blok yorum tamamen silinirse
    # sonraki tum bulgularin satir numarasi yorumun satir sayisi kadar
    # KAYAR. Kayma sessizdir: rapor gecerli gorunur ama gosterdigi satir
    # baska bir kodu isaret eder; duzeltme yaparken yanlis yere yazma
    # riski dogar (ai_tespitler.js'te 8 satir kayma olcüldu). Cozum:
    # silmek yerine ayni sayida satirsonu birakan bosluga cevir.
    metin = re.sub(
        r"/\*.*?\*/",
        lambda m: "\n" * m.group(0).count("\n"),
        metin,
        flags=re.S,
    )
    satirlar = []
    for sat in metin.split("\n"):
        # Satir yorumu: dize icindeki // yanlis kirpilmasin diye
        # once dizeleri maskele
        maske = re.sub(r'"[^"\n]*"|\'[^\'\n]*\'|`[^`]*`', "@@", sat)
        if "//" in maske:
            kes = maske.index("//")
            # Ayni pozisyon orijinal satirda farkli olabilir; guvenli
            # yol: maskelenmis uzunluk ayni oldugu icin dogrudan kes
            sat = sat[:kes]
        satirlar.append(sat)
    temiz = "\n".join(satirlar)

    bulunan = []
    for m in re.finditer(r'"([^"\n]*)"|\'([^\'\n]*)\'|`([^`]*)`', temiz):
        s = m.group(1) or m.group(2) or m.group(3) or ""
        if s:
            satir_no = temiz[: m.start()].count("\n") + 1
            bulunan.append((satir_no, s))
    return bulunan


def turkce_mi(s):
    """Dize kullaniciya gorunen Turkce metin mi?"""
    if len(s.strip()) < 3:
        return False
    # Turkce'ye ozgu harf varsa kesin
    if any(k in TR_HARF for k in s):
        return True
    # Unicode kacisli Turkce harf (\u00e7 = c cedilla vb.)
    if re.search(r"\\u00(e7|c7|fc|dc|f6|d6|11f|11e)", s):
        return True
    if re.search(r"\\u01(1f|1e|30|31)", s):
        return True
    if re.search(r"\\u015(f|e)", s):
        return True
    # Turkce kelime
    for m in TR_KELIME.finditer(s):
        if m.group(1).lower() not in TR_KELIME_YOKSAY:
            return True
    return False


def kod_gibi_mi(s):
    """Dize kod/teknik deger mi (kusur degil)?"""
    # CSS sinifi, id, secici, dosya yolu, URL, MAVLink adi vb.
    if re.fullmatch(r"[a-zA-Z0-9_\-\.#\s>\[\]=\":,\(\)/]*", s):
        return True
    return False


# HTML sablonu iceren dizeler: cevrilecek metin ic etiketlerde degil,
# `data-i18n` veya ayri t() cagrisiyla islenir. Ayrica bu dizelerdeki
# Turkce, cogu zaman sinif adi ya da ic metin olarak zaten sozlukten
# beslenir. Gomulu metin olarak saymak yanlis pozitif uretir.
HTML_SABLON = re.compile(r"<\s*[a-zA-Z][\w-]*[\s>/]")

# METNI JS TARAFINDAN SOZLUKTEN YAZILAN ELEMANLAR.
#
# Bu elemanlarin HTML'deki Turkce metni yalnizca ILK yukleme degeridir;
# `applyLanguage` dil degisiminde ilgili JS tazeleyicisini cagirir ve
# metin sozlukten yeniden yazilir. Bu yuzden `data-i18n` GEREKMEZ, hatta
# eklemek zararlidir: sabit ceviri, JS'in yazdigi dinamik degeri ezer.
#
# Dogrulanan ornek: #fdRcs / #fdHiz / #fdAzimut "KAPALI" metni
#   filtreler.js -> ciz(): degerEl.textContent =
#       kapali ? (t.fKapali || "KAPALI") : mn + " ~ " + mx;
#   i18n.js applyLanguage: querySelectorAll(".cift-slider") -> _ciz()
#   ve `fKapali` anahtari TR ("KAPALI") + EN ("OFF") olarak sozlukte VAR.
# data-i18n eklenirse filtre araligi ("3 ~ 50") "KAPALI" ile ezilir.
JS_TAZELER = {
    "fdRcs": "filtreler.js ciz() -> t.fKapali (TR/EN sozlukte var)",
    "fdHiz": "filtreler.js ciz() -> t.fKapali (TR/EN sozlukte var)",
    "fdAzimut": "filtreler.js ciz() -> t.fKapali (TR/EN sozlukte var)",
}

# Ozel isim / marka / birim: cevrilmez.
OZEL_AD = re.compile(
    r"^(G[ÖO]ZC[ÜU]|GOKKUBBE|G[ÖO]KKUBBE|VEILOX|MKE|NOVIXAIR"
    r"|ArduPilot|Mission Planner|Cesium|MAVLink|DJI|RFD900X?)",
    re.IGNORECASE,
)


def iki_dilli_baglam(satirlar, idx, pencere=2):
    """Bulunan dizenin cevresinde Ingilizce karsiligi var mi?

    NEDEN: `widget_hava.js` ve `widget_saat.js` metinleri ZATEN iki dilli
    tutuyor:

        KOD = { 0: { tr:"Açık", en:"Clear", tur:"gunes" }, ... }
        BEAUFORT = [ [1, 0, "Sakin", "Calm"], ... ]
        GUN_TR = [...]; GUN_EN = [...]
        ingilizceMi() ? "Map position unknown" : "Harita konumu okunamadı"

    Bu yapilarda Turkce dize kusur DEGIL. Araç yalnizca Turkce tarafi
    gordugu icin eksik sayiyordu; bu suzgec o yanlis pozitifi keser.

    Olcut: ayni satirda ya da +-`pencere` satir icinde
      - `en:` / `EN:` alan adi, veya
      - `_EN` ile biten dizi/sabit adi, veya
      - `ingilizceMi()` / `aktifDil` ucluk operatoru
    varsa iki dilli baglam kabul edilir.
    """
    bas = max(0, idx - pencere - 1)
    son = min(len(satirlar), idx + pencere)
    blok = "\n".join(satirlar[bas:son])
    if re.search(r"\ben\s*:\s*[\"']", blok):
        return True
    if re.search(r"_EN\b", blok):
        return True
    if re.search(r"ingilizceMi\s*\(\s*\)", blok):
        return True
    if re.search(r"aktifDil\b", blok):
        return True
    return False


def iki_dilli_dizi_satiri(sat):
    """Ayni satirda TR ve EN dizesi yan yana mi?

    Ornek: `[1, 0, "Sakin", "Calm"],` -> iki dize var, ikincisi
    Turkce degil. Bu, cevirinin zaten yapildigini gosterir.
    """
    dizeler = re.findall(r'"([^"\n]{2,})"|\'([^\'\n]{2,})\'', sat)
    metinler = [(a or b) for a, b in dizeler]
    if len(metinler) < 2:
        return False
    tr_var = any(turkce_mi(m) for m in metinler)
    en_var = any(
        (not turkce_mi(m)) and re.search(r"[A-Za-z]{3}", m) for m in metinler
    )
    return tr_var and en_var


# `t.anahtar || "Türkçe"` yedek kalıbı.
# NEDEN ONEMLI: kod tabaninin cogu bu kalipla yazilmis:
#
#     isimEtiket.textContent = t.dkIsimEtiket || "İsim";
#
# Burada Turkce dize KUSUR DEGIL; sozluk anahtari zaten kullaniliyor,
# Turkce yalnizca anahtar yoksa devreye giren yedek. Anahtar EN
# sozlugunde varsa Ingilizce arayuzde dogru metin gelir.
#
# GERCEK kusur: anahtar sozlukte YOK ama kodda kullaniliyor -> yedek
# Turkce devreye girer ve Ingilizce arayuzde Turkce gorunur. Bu yuzden
# suzgec anahtari yalnizca sozlukte VARSA gecerli sayar.
# v2.4.34: Desen COK SATIRLI ve PARANTEZLI bicimleri de kapsar.
# Olculen gerceklik: yedek kalibi kaynakta bu bicimlerde yaziliyor ve
# eski desen (tek satir, parantezsiz) hicbirini yakalamiyordu:
#
#   1) tut.title = D().bolumTutamacIpucu
#        || "Surukleyerek...";                 <- `||` SONRAKI satirda
#   2) x = ((typeof D === "function") ? D().kamSecilmedi : "")
#        || "- Secilmedi -";                    <- anahtar PARANTEZ icinde
#   3) svg.setAttribute("title", (D().wgPusulaKuzeyIpucu)
#        || (en ? "..." : "..."));              <- yedek de parantezli
#
# `\s` satirsonunu da kapsadigi icin cok satirlilik dogal olarak
# desteklenir; eklenen esneklik `)` ve `(` karakterlerine izin verir.
YEDEK_KALIP = re.compile(
    r"(?:[A-Za-z_][A-Za-z0-9_]*\s*\(\s*\)|[A-Za-z_][A-Za-z0-9_]*)"
    r"\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)"
    # Anahtardan sonra: kapanan parantezler ve/veya ucluk `typeof`
    # korumasinin bos yedegi -> `? D().anahtar : "")`
    r"(?:\s*\)|\s*:\s*[\"'][\"']|\s*\()*"
    r"(?:\s*\|\|\s*(?:[A-Za-z_][A-Za-z0-9_]*\s*\.\s*"
    r"[A-Za-z_][A-Za-z0-9_]*)\s*\)*)*"
    r"\s*\|\|\s*\(*\s*"            # yedek parantezle sarilmis olabilir
    r"(?:[A-Za-z_][A-Za-z0-9_]*\s*\?\s*)?"  # ... || (en ? "EN" : "TR")
    r"[\"']"
)


# v2.4.34: SOZLUK ANAHTARINI KOMSU ALANDA TASIYAN YAPI
# Ornek: `adAnahtar: "hkGoogleYol"` / `atifAnahtar: "hkOsmAtif"`
# Gorunen metin bu anahtar uzerinden sozlukten cozulur; ayni nesnedeki
# duz `ad`/`atif` alani yalnizca yedektir.
ANAHTAR_ALANI = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*Anahtar\s*:\s*[\"']"
    r"([A-Za-z_][A-Za-z0-9_]*)[\"']"
)

# v2.4.34: UCLU SOZLUK SECIMI
#     t.bagRozetAktif ? t.bagRozetAktif(n) : n + " AKTIF"
# Anahtar sozlukte varsa Turkce dal olu koddur.
UCLU_SOZLUK = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)\s*\?"
)


# v2.4.34: YEREL `t("anahtar", "Turkce yedek")` CAGRI KALIBI
#
# `ai_tespitler.js`, `ai_kutuphane.js`, `ai_sunucular.js` gibi moduller
# sozluge NOKTA ile degil, kendi yerel yardimcilariyla erisiyor:
#
#     function t(anahtar, varsayilan) {
#       const d = (typeof D === "function") ? D() : null;
#       return (d && d[anahtar]) || varsayilan;
#     }
#     ...
#     t("aigTur2", "Tur")
#
# Bu, `t.anahtar || "Tur"` ile ISLEVSEL OLARAK AYNIDIR: anahtar sozlukte
# varsa cevrilmis deger doner, ikinci argument yalnizca olu yedektir.
# Arac bu kalibi tanimadigi icin 39 kaydi kusur sayiyordu; oysa anahtarlar
# sozlukte mevcut ve ceviri CALISIYOR.
# Yardimci adi modulden module degisiyor: `t(...)`, `s(...)`, `L(...)`.
# Ornek (rota_param.js):  function s(k, y){ const d = t(); return d[k] || y; }
# Bu yuzden desen tek harfli / kisa adlari da kapsar.
YEREL_T_KALIP = re.compile(
    r"\b[A-Za-z_][A-Za-z0-9_]{0,3}\s*\(\s*[\"']"
    r"([A-Za-z_][A-Za-z0-9_]*)[\"']\s*,"
)


def yerel_t_anahtarlari(sat):
    """Satirdaki `t("anahtar", "yedek")` cagrilarindan anahtar adlarini alir."""
    return YEREL_T_KALIP.findall(sat)


def yedek_kalip_anahtarlari(sat):
    """Satirdaki `X.anahtar || "..."` kaliplarindan anahtar adlarini dondurur.

    Zincirli yedekler de desteklenir:
        t.dkRotayiYukle || t.dkRotayaGonder || "Rotayı Yükle"
    Bu durumda zincirdeki TUM anahtarlar toplanir; en az biri sozlukte
    varsa metin cevriliyor demektir.
    """
    adlar = []
    for m in re.finditer(
        r"(?:[A-Za-z_][A-Za-z0-9_]*\s*\(\s*\)|[A-Za-z_][A-Za-z0-9_]*)"
        r"\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)",
        sat,
    ):
        adlar.append(m.group(1))
    return adlar


def sozluk_ayikla(kaynak):
    """i18n.js icindeki TR ve EN sozluk bloklarini ayirir."""
    tr_bas = kaynak.index("\n  TR: {")
    en_bas = kaynak.index("\n  EN: {")
    tr_blok = kaynak[tr_bas:en_bas]
    # EN blogunun sonu: DILLER nesnesinin kapanisi
    en_son = kaynak.index("\n};", en_bas)
    en_blok = kaynak[en_bas:en_son]
    return tr_blok, en_blok


def anahtarlar(blok):
    """Sozluk blogundan anahtar -> deger eslemesi cikarir.

    Cok satirli degerleri de yakalar (deger sonraki satira sarkabilir).
    """
    sonuc = {}
    # Anahtar IKI bicimde yazilabilir ve ikisi de gecerli JavaScript'tir:
    #     merkezSunucuYok:  "..."     (tirnaksiz)
    #     "merkezSunucuYok": "..."    (tirnakli)
    #
    # Onceki desen yalniz TIRNAKSIZ bicimi taniyordu. Olculdu: i18n.js
    # icinde 132 tirnakli anahtar var (66 TR + 66 EN) ve bunlarin 15'i
    # `merkez*`, 29'u `prog*` yani v2.4.53'te eklenen MERKEZ/KOPRU
    # anahtarlari. Arac bunlarin hicbirini gormuyor, dolayisiyla:
    #   * denge raporu bu 66 anahtari HIC saymiyor
    #   * `t.merkezSunucuYok || "Turkce"` kaliplari "anahtar sozlukte
    #     yok" diye GERCEK KUSUR olarak raporlaniyordu (93 yanlis pozitif)
    # Belirti sessizdi: rapor "eksik anahtar" diyordu, anahtar aslinda
    # yerindeydi.
    for m in re.finditer(
        r'^\s*(?:([A-Za-z_][A-Za-z0-9_]*)|"([A-Za-z_][A-Za-z0-9_]*)"'
        r"|'([A-Za-z_][A-Za-z0-9_]*)')\s*:\s*"
        r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')',
        blok,
        re.M,
    ):
        ad = m.group(1) or m.group(2) or m.group(3)
        ham = m.group(4)[1:-1]
        if ad not in sonuc:
            sonuc[ad] = ham
    # v2.4.34: ISLEV DEGERLI ANAHTARLAR
    #
    # Sozlukte bazi anahtarlar dize degil ISLEVDIR; degisken metin
    # ureten kayitlar boyle yazilir:
    #
    #     bagRozetAktif: (n) => n + " AKTIF",
    #     konumKaynakPC: (m) => `PC konumu (+-${m} m)`,
    #
    # Eski desen yalnizca tirnakla BASLAYAN degerleri tanidigi icin bu
    # anahtarlar sozlukte YOK sayiliyordu. Sonuc: sozluk sayimi eksik
    # cikiyor ve bu anahtarlari kullanan kod "cevrilmemis" olarak
    # raporlaniyordu (olcum: seri.js rozetleri).
    for m in re.finditer(
        r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*"
        r"(?:\([^)]*\)|[A-Za-z_][A-Za-z0-9_]*)\s*=>",
        blok,
        re.M,
    ):
        ad = m.group(1)
        if ad not in sonuc:
            # Deger dinamik uretilir; denge denetimi icin varligi yeter.
            sonuc[ad] = "<islev>"
    return sonuc


def main():
    rapor = {
        "sozluk_eksik_en": [],
        "sozluk_eksik_tr": [],
        "en_turkce_kalmis": [],
        "js_gomulu": {},
        "html_i18nsiz": {},
    }

    # --- 1) Sozluk dengesi -------------------------------------------
    yol = os.path.join(JS_DIZIN, "i18n.js")
    with open(yol, encoding="utf-8") as f:
        i18n_kaynak = f.read()

    tr_blok, en_blok = sozluk_ayikla(i18n_kaynak)
    tr = anahtarlar(tr_blok)
    en = anahtarlar(en_blok)

    rapor["tr_anahtar_sayisi"] = len(tr)
    rapor["en_anahtar_sayisi"] = len(en)
    rapor["sozluk_eksik_en"] = sorted(set(tr) - set(en))
    rapor["sozluk_eksik_tr"] = sorted(set(en) - set(tr))

    # --- 2) EN'de Turkce kalmis degerler -----------------------------
    #
    # YANLIS POZITIF: yer tutucu adlari Turkce'dir ve OYLE KALMALIDIR.
    #   onayTakeoff EN: "The drone will take off to {irtifa} m. Are you sure?"
    # Buradaki `{irtifa}` bir DEGISKEN ADI; `t.onayTakeoff.replace("{irtifa}",
    # deger)` cagrisi bu adi arar. Ceviriye kalkarsak ({altitude} yaparsak)
    # yer tutucu artik eslesmez ve kullaniciya ham `{irtifa}` gorunur.
    # Bu yuzden olcum oncesi `{...}` blogunu ayikla.
    YER_TUTUCU = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")
    for ad, deger in sorted(en.items()):
        deger_olcum = YER_TUTUCU.sub(" ", deger)
        if turkce_mi(deger_olcum) and not kod_gibi_mi(deger_olcum):
            rapor["en_turkce_kalmis"].append(
                {"anahtar": ad, "en_deger": deger, "tr_deger": tr.get(ad, "")}
            )

    # --- 3) JS'e gomulu Turkce dizeler -------------------------------
    rapor["suzulen"] = {
        "kapsam_disi_dosya": 0,
        "iki_dilli": 0,
        "html_sablon": 0,
        "ozel_ad": 0,
        "yerel_t": 0,
        # v2.4.34: sozluk anahtari komsu alanda (adAnahtar/atifAnahtar)
        "anahtar_alani": 0,
        # v2.4.34: uclu sozluk secimi (t.anahtar ? t.anahtar(n) : "TR")
        "uclu_sozluk": 0,
        "yedek_kalip": 0,
        # v2.4.34: data-i18n-title/-ph/-aria isareti tasiyan nitelikler
        "nitelik_isaretli": 0,
        # Metnini JS'in sozlukten yazdigi elemanlar (JS_TAZELER)
        "js_tazeler": 0,
    }
    # Yedek kalibi kullanan ama anahtari SOZLUKTE OLMAYAN yerler:
    # bunlar gercek kusurdur (Ingilizce arayuzde Turkce gorunur).
    rapor["yedek_anahtar_yok"] = {}
    for dosya in sorted(os.listdir(JS_DIZIN)):
        if not dosya.endswith(".js"):
            continue
        if dosya == "i18n.js":
            continue  # sozluk dosyasinin kendisi
        tam = os.path.join(JS_DIZIN, dosya)
        with open(tam, encoding="utf-8") as f:
            kaynak = f.read()
        if dosya in KAPSAM_DISI:
            ham = sum(
                1
                for _, s in js_dizeleri(kaynak)
                if turkce_mi(s) and not kod_gibi_mi(s)
            )
            rapor["suzulen"]["kapsam_disi_dosya"] += ham
            continue
        satirlar = kaynak.split("\n")
        bulgular = []
        for satir_no, s in js_dizeleri(kaynak):
            if kod_gibi_mi(s):
                continue
            if not turkce_mi(s):
                continue
            sat = satirlar[satir_no - 1] if satir_no <= len(satirlar) else ""
            # Zaten iki dilli tutulan yapilar (widget_hava, widget_saat...)
            if iki_dilli_baglam(satirlar, satir_no) or iki_dilli_dizi_satiri(sat):
                rapor["suzulen"]["iki_dilli"] += 1
                continue
            # HTML sablonu iceren dize: ic metin ayri islenir
            if HTML_SABLON.search(s):
                rapor["suzulen"]["html_sablon"] += 1
                continue
            # Ozel isim / marka
            if OZEL_AD.match(s.strip()):
                rapor["suzulen"]["ozel_ad"] += 1
                continue
            # v2.4.34: yerel `t("anahtar", "Turkce yedek")` cagri kalibi.
            # `t.anahtar || "..."` ile islevsel olarak aynidir; ikinci
            # argument olu yedektir. Anahtar iki sozlukte de varsa ceviri
            # calisir -> kusur DEGIL.
            # v2.4.34 COK SATIRLI IFADE PENCERESI
            #
            # Kaynak 79 kolona sarildigi icin yedek kalibin anahtari ile
            # Turkce dize AYRI SATIRLARA dusuyor:
            #
            #     ipucu = t.acUcustaIpucu ||
            #       "Arac ARM durumda; denetim ayrintilari icin tiklayin";
            #
            # Yalniz bulgunun bulundugu satira bakan bir suzgec anahtari
            # goremez ve cevrilmis metni kusur sayar. Bu, olcumu abartir
            # (54 kaydin 33'u boyleydi). Cozum: bulgudan 4 satir yukariya
            # kadar pencere olustur.
            pen_bas = max(0, satir_no - 5)
            pencere = "\n".join(satirlar[pen_bas:satir_no])
            yerel_adlar = yerel_t_anahtarlari(pencere)
            if yerel_adlar and any(a in tr for a in yerel_adlar):
                rapor["suzulen"]["yerel_t"] += 1
                continue
            # DIKKAT: yerel_t desenine benzeyen ama sozluk cagrisi OLMAYAN
            # ifadeler var. Olculdu, ornek (merkez_ayar.js:307-311):
            #
            #     yaz("merkez_sifre", sf);              <- AYAR YAZMA
            #     gSifre.placeholder = t.progAyarMerkezSifreVar ||
            #       "\u2022\u2022\u2022 (kayitli)";  <- yedek dize
            #
            # `YEREL_T_KALIP` (1-4 harfli isim + tirnakli ilk argument)
            # `yaz("merkez_sifre", ...)` cagrisini `t("anahtar", "yedek")`
            # sanip anahtari `merkez_sifre` cikariyor. O ad sozlukte
            # olmadigi icin ESKI kod BURADA "gercek kusur" deyip `continue`
            # ile cikiyordu; bir alt satirdaki GERCEK anahtar
            # (`t.progAyarMerkezSifreVar`, sozlukte TR+EN mevcut) HIC
            # denetlenmiyordu. Sonuc: dogru cevrilmis iki satir kusur
            # olarak raporlaniyordu (yanlis pozitif).
            #
            # Cozum: yerel_t dali yalniz ONAYLAR. Anahtar bulunamazsa
            # erken cikmaz; asagidaki `t.anahtar || "..."` denetimi
            # calisir ve gercek anahtari gorur. Anahtar hicbir dalda
            # bulunamazsa bulgu zaten en sonda raporlanir.
            # v2.4.34: SOZLUK ANAHTARI KOMSU ALANDA (harita katmanlari)
            # `HARITA_KAYNAKLARI` her katman icin `adAnahtar`/`atifAnahtar`
            # tasir; `katmanAdi()` gorunen metni sozlukten cozer ve `ad`
            # alani yalnizca yedektir:
            #     google_yol: { adAnahtar: "hkGoogleYol",
            #                   ad: "Google Yol Haritasi", ... }
            # Komsu satirdaki anahtar sozlukte varsa ceviri CALISIYOR.
            komsu = ANAHTAR_ALANI.findall(pencere)
            if komsu and any(a in tr and a in en for a in komsu):
                rapor["suzulen"]["anahtar_alani"] += 1
                continue
            # v2.4.34: UCLU SOZLUK SECIMI (islev anahtarlari)
            #     metin = (t.bagRozetAktif ? t.bagRozetAktif(n)
            #                              : n + " AKTIF");
            # Anahtar sozlukte tanimliysa Turkce dal HIC calismaz.
            uclu = UCLU_SOZLUK.findall(pencere)
            if uclu and any(a in tr and a in en for a in uclu):
                rapor["suzulen"]["uclu_sozluk"] += 1
                continue
            # `t.anahtar || "Turkce"` yedek kalibi (cok satirli pencere)
            if YEDEK_KALIP.search(pencere):
                adlar = yedek_kalip_anahtarlari(pencere)
                # Zincirdeki anahtarlardan en az biri TR sozlukte varsa
                # metin sozlukten besleniyor -> kusur degil.
                if any(a in tr for a in adlar):
                    # EN'de de var mi? Yoksa applyLanguage TR'ye duser.
                    en_var = any(a in en for a in adlar)
                    if en_var:
                        rapor["suzulen"]["yedek_kalip"] += 1
                        continue
                    # TR'de var, EN'de yok -> sozluk dengesi bolumunde
                    # zaten raporlanir; burada tekrar sayma.
                    rapor["suzulen"]["yedek_kalip"] += 1
                    continue
                # Anahtar sozlukte HIC yok -> gercek kusur
                rapor["yedek_anahtar_yok"].setdefault(dosya, []).append(
                    {
                        "satir": satir_no,
                        "metin": s,
                        "anahtarlar": [
                            a for a in adlar if a not in tr and a not in en
                        ],
                    }
                )
                continue
            bulgular.append({"satir": satir_no, "metin": s})
        if bulgular:
            rapor["js_gomulu"][dosya] = bulgular

    # --- 4) HTML'de data-i18n olmayan Turkce metin -------------------
    for dosya in sorted(os.listdir(GOKTUNGU)):
        if not dosya.endswith(".html"):
            continue
        tam = os.path.join(GOKTUNGU, dosya)
        with open(tam, encoding="utf-8") as f:
            kaynak = f.read()
        # <script>/<style>/yorum bloklarini cikar.
        # SATIR NUMARASI KORUMASI: blok silinirse sonraki bulgularin
        # satir numarasi kayar ve rapor yanlis satiri gosterir (bu
        # yuzden dosya duzenlerken yanlis yere yazma riski dogar).
        # Cozum: silmek yerine ayni sayida satirsonu birakan bosluga
        # cevir; boylece satir sayimi kaynakla birebir kalir.
        def _bosalt(m):
            return "\n" * m.group(0).count("\n")

        temiz = re.sub(
            r"<script.*?</script>", _bosalt, kaynak, flags=re.S | re.I
        )
        temiz = re.sub(
            r"<style.*?</style>", _bosalt, temiz, flags=re.S | re.I
        )
        temiz = re.sub(r"<!--.*?-->", _bosalt, temiz, flags=re.S)

        bulgular = []
        # Etiket -> metin ciftleri
        for m in re.finditer(r"<([a-zA-Z][\w-]*)([^>]*)>([^<>]+)<", temiz):
            nitelik = m.group(2)
            metin = m.group(3).strip()
            if not metin or len(metin) < 3:
                continue
            if not turkce_mi(metin):
                continue
            if "data-i18n" in nitelik:
                continue
            if OZEL_AD.match(metin):
                continue
            # JS TAZELEMESI: bazi elemanlarin metni HTML'de yalnizca ilk
            # deger olarak duruyor; calisma aninda JS sozlukten yaziyor.
            # Ornek: #fdRcs "KAPALI" -> filtreler.js ciz() icinde
            #   degerEl.textContent = kapali ? (t.fKapali || "KAPALI") : ...
            # ve applyLanguage her dil degisiminde `_ciz()` cagiriyor.
            # Boyle elemanlara data-i18n eklemek YANLIS olur: applyLanguage
            # sabit metni yazar, sonra JS gercek degeri ("3 ~ 50") ezer;
            # ya da tersi sirada sayisal deger kaybolur.
            eleman_id = ""
            mid = re.search(r'id\s*=\s*"([^"]+)"', nitelik)
            if mid:
                eleman_id = mid.group(1)
            if eleman_id in JS_TAZELER:
                rapor["suzulen"]["js_tazeler"] += 1
                continue
            satir_no = temiz[: m.start()].count("\n") + 1
            bulgular.append(
                {"satir": satir_no, "etiket": m.group(1), "metin": metin}
            )
        # title / placeholder / aria-label nitelikleri
        #
        # v2.4.34 NITELIK CEVIRISI: `applyLanguage` artik
        #   data-i18n-title / data-i18n-ph / data-i18n-aria
        # niteliklerini okuyup ilgili nitelige yaziyor. Bu isaret varsa
        # HTML'deki Turkce deger yalnizca ilk yukleme degeridir (dil TR
        # oldugunda gorunen); EN'e gecildiginde sozlukten degistirilir.
        # Dolayisiyla isaretli nitelikler kusur DEGILDIR.
        NIT_ISARET = {
            "title": "data-i18n-title",
            "placeholder": "data-i18n-ph",
            "aria-label": "data-i18n-aria",
        }
        for m in re.finditer(
            r'<[a-zA-Z][\w-]*[^>]*?(title|placeholder|aria-label)'
            r'\s*=\s*"([^"]+)"[^>]*>',
            temiz,
        ):
            metin = m.group(2).strip()
            if not turkce_mi(metin):
                continue
            # Ayni etiket data-i18n-* isareti tasiyor mu?
            if NIT_ISARET[m.group(1)] in m.group(0):
                rapor["suzulen"]["nitelik_isaretli"] += 1
                continue
            satir_no = temiz[: m.start()].count("\n") + 1
            bulgular.append(
                {
                    "satir": satir_no,
                    "etiket": "@" + m.group(1),
                    "metin": metin,
                }
            )
        if bulgular:
            rapor["html_i18nsiz"][dosya] = bulgular

    # --- Rapor -------------------------------------------------------
    cikti = os.path.join(KOK, "rapor_i18n.json")
    with open(cikti, "w", encoding="utf-8") as f:
        json.dump(rapor, f, ensure_ascii=False, indent=2)

    js_toplam = sum(len(v) for v in rapor["js_gomulu"].values())
    html_toplam = sum(len(v) for v in rapor["html_i18nsiz"].values())

    print("=" * 66)
    print("I18N BUTUNLUK DENETIMI")
    print("=" * 66)
    print(f"TR sozluk anahtari      : {len(tr)}")
    print(f"EN sozluk anahtari      : {len(en)}")
    print(f"EN'de EKSIK anahtar     : {len(rapor['sozluk_eksik_en'])}")
    print(f"TR'de EKSIK anahtar     : {len(rapor['sozluk_eksik_tr'])}")
    print(f"EN'de Turkce kalmis     : {len(rapor['en_turkce_kalmis'])}")
    print(
        f"JS'e gomulu Turkce      : {js_toplam} "
        f"({len(rapor['js_gomulu'])} dosyada)"
    )
    print(
        f"HTML'de i18n'siz Turkce : {html_toplam} "
        f"({len(rapor['html_i18nsiz'])} dosyada)"
    )
    print("-" * 66)
    sz = rapor["suzulen"]
    print("SUZULEN (kusur DEGIL, gerekceli):")
    print(f"  kapsam disi dosya     : {sz['kapsam_disi_dosya']}")
    print(f"  zaten iki dilli yapi  : {sz['iki_dilli']}")
    print(f"  HTML sablonu iceren   : {sz['html_sablon']}")
    print(f"  ozel isim / marka     : {sz['ozel_ad']}")
    print(f"  yerel t(anahtar,yedek): {sz['yerel_t']}")
    print(f"  anahtar komsu alanda  : {sz.get('anahtar_alani', 0)}")
    print(f"  uclu sozluk secimi    : {sz.get('uclu_sozluk', 0)}")
    print(f"  yedek kalip (sozlukte): {sz.get('yedek_kalip', 0)}")
    print(f"  nitelik isaretli (HTML): {sz.get('nitelik_isaretli', 0)}")
    print(f"  JS tazeler (HTML)     : {sz.get('js_tazeler', 0)}")
    print("-" * 66)

    if rapor["sozluk_eksik_en"]:
        print("\nEN'DE EKSIK ANAHTARLAR (Ingilizce arayuzde TR gorunur):")
        for a in rapor["sozluk_eksik_en"][:40]:
            print(f"  - {a}: {tr.get(a, '')[:60]}")
        if len(rapor["sozluk_eksik_en"]) > 40:
            print(f"  ... +{len(rapor['sozluk_eksik_en']) - 40} tane")

    if rapor["en_turkce_kalmis"]:
        print("\nEN SOZLUGUNDE TURKCE KALMIS DEGERLER:")
        for k in rapor["en_turkce_kalmis"][:30]:
            print(f"  - {k['anahtar']}: {k['en_deger'][:60]}")
        if len(rapor["en_turkce_kalmis"]) > 30:
            print(f"  ... +{len(rapor['en_turkce_kalmis']) - 30} tane")

    yak = rapor.get("yedek_anahtar_yok", {})
    yak_toplam = sum(len(v) for v in yak.values())
    print(f"Yedek kalip, anahtar YOK : {yak_toplam} ({len(yak)} dosyada)")
    if yak:
        print("\nYEDEK KALIP AMA ANAHTAR SOZLUKTE YOK (gercek kusur):")
        for d, v in sorted(yak.items(), key=lambda x: -len(x[1])):
            print(f"  {len(v):4}  {d}")

    if rapor["js_gomulu"]:
        print("\nJS'E GOMULU TURKCE (dosya basina sayi):")
        for d, v in sorted(
            rapor["js_gomulu"].items(), key=lambda x: -len(x[1])
        ):
            print(f"  {len(v):4d}  {d}")

    if rapor["html_i18nsiz"]:
        print("\nHTML'DE data-i18n OLMAYAN TURKCE (dosya basina sayi):")
        for d, v in sorted(
            rapor["html_i18nsiz"].items(), key=lambda x: -len(x[1])
        ):
            print(f"  {len(v):4d}  {d}")

    print("\n" + "=" * 66)
    print(f"Ayrintili rapor: {cikti}")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())
