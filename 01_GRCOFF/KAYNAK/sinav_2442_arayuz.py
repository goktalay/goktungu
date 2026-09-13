#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v2.4.42 arayuz butunluk denetimi — TARAYICI GEREKTIRMEZ.
HTTP uzerinden servis edilen GERCEK dosyalari indirip su hata siniflarini
yakalar. Her denetimin gerekcesi, o denetimin yakaladigi GERCEK bir
kusura veya kullanici istegine dayanir.

  1. index.html'deki betik/CSS etiketlerinin GERCEKTEN indirilebildigi
     (yeni js/ucus_uid.js, js/qr.js, js/ucus_grafik.js,
      js/kayitli_dronlar.js, js/home_ikon.js dahil)
  2. BETIK SIRASI: ucus_uid.js gecmis.js'ten ONCE, qr.js ucus_rapor.js'ten
     ONCE yuklenmeli. Sira bozulursa gecmis.js `ucusKodu` tanimsiz bulur
     ve ucus listesindeki kod sessizce bos kalir (istisna yutulur)
  3. Raporda pilot alaninin AD SOYAD cozdugu: `pilotlar_ad` alani
     backend'de uretiliyor ve rapor once bunu okuyor
     <-- olculen kusur: pilot alanina e-posta dusuyordu
  4. Arac turunun MAV_TYPE'tan turedigi: `arac_tipi` backend'de uretiliyor
     ve `urAracTuru()` MAV_TYPE eslemesi yapiyor
     <-- olculen kusur: baglanti etiketi okundugu icin BILINMEYEN yaziyordu
  5. MAV_TYPE bilinmiyorsa arac turu satirinin HIC yazilmadigi
     <-- imzali belgeye tahmin girmemeli
  6. Ucus kodunun DETERMINISTIK ve JS<->Python AYNI oldugu:
     ucus_uid.js ile ucus_gecmisi.py ayni alfabeyi ve ayni FNV-1a
     sabitlerini kullanmali (kod uretimi iki tarafta da yapiliyor)
  7. Kod alfabesinde I, L, O, U harflerinin BULUNMADIGI
     <-- 1/I ve 0/O karisikligi elle ararken hata uretir
  8. `ucusKoduNormalize()` fonksiyonunun O->0, I->1, L->1 duzeltmesi
     yaptigi (kullanici kodu elle yazarken)
  9. QR ureticisinin HARICI BAGIMLILIK ICERMEDIGI: CDN, import,
     require, fetch yok  <-- saha kurulumu internetsiz
 10. QR icin kullanilan API'nin (`window.qrSvg`) GERCEKTEN tanimli oldugu
     ve tuketicilerin (ucus_rapor.js, ucus_grafik.js) ayni adi cagirdigi
 11. QR'in yaninda kodun METIN olarak da basildigi
     <-- QR okunamayan fotokopide belge yine eslestirilebilmeli
 12. QR icerigine URL YAZILMADIGI (duz kod)
     <-- internetsiz sahada URL tasiyan QR bos sayfa acar
 13. GRAFIKLER dugmesinin ucus gecmisi alt seridinde bulundugu ve
     `ucusGrafikAc` cagirdigi
 14. Alt seridin dugmeleri AYIRDIGI: gc-rapor-satir space-between
     <-- kullanici istegi: GRAFIKLER en solda, RAPOR sagda
 15. Grafik ciktisinin YATAY (landscape) oldugu
     <-- kullanici istegi: yatay antetli kagit
 16. Grafik ciktisinda ANTET + IMZA bloklarinin bulundugu
 17. Grafik ciktisinin sirket bilgisi yokken cikti URETMEDIGI
     (antet uydurulmaz; ucus_rapor.js ile ayni kural)
 18. Serilerin veri yoksa null dondurdugu, uydurma deger uretmedigi
 19. Batarya voltaji serisinin sifirTaban=false oldugu
     <-- 22-25 V araligini 0'dan cizmek egriyi duz cizgiye cevirir
 20. Kayitli Dronlar menu ogesinin bulundugu ve menubar'a bagli oldugu
 21. Kayitli Dronlar'in YENI backend komutu EKLEMEDIGI: mevcut
     `dron_gecmis_liste` kullanilmali
 22. `dron_gecmis_liste` cevabinin IKI tuketiciye de dagitildigi
     (kayitli_dronlar + pilot_hakkinda)
     <-- pilot_hakkinda.js ikinci tuketici; alan adi degistirilmemeli
 23. Yetki suzgecinin SUNUCUDA oldugu: pilot kendi dronlarini gorur,
     yonetici tumunu  <-- istemci tarafi gizleme yetki denetimi degildir
 24. SHIFT+tik ile HOME ayarlamanin CTRL+tik (goto) yolundan AYRI oldugu
     ve iki kipin karismadigi
 25. HOME ayarlamanin ONAY istedigi
     <-- RTL/failsafe donus noktasini degistirir
 26. HOME komutunun sunucuda GERCEK MAVLink komutuna donustugu
     (MAV_CMD_DO_SET_HOME)
 27. HOME ikonunun dronun RENGINDE cizildigi
 28. HOME atanmamis dronun HAZIR SAYILMADIGI ve maddenin denetim
     listesinde EN USTTE gosterildigi  <-- kullanici istegi
 29. `ucus_oku` dalindaki `NameError: 'veritabani' is not defined`
     kusurunun KALMADIGI  <-- v2.4.41 gerilemesi: kalkis kontrol
     listesi hic okunamiyordu, hata yutuldugu icin sessizdi
 30. JS/HTML'de uretilen CSS siniflarinin CSS'te tanimli oldugu
 31. CSS'te TANIMSIZ tema degiskeni kullanilmadigi
 32. i18n anahtarlarinin hem TR hem EN'de tanimli oldugu
 33. Surum etiketlerinin 2.4.42 oldugu ve gecmiste v2.4.35 / v2.4.40 /
     v2.4.41 girdilerinin KORUNDUGU  <-- toplu degistirme gecmisi de bozar

KULLANIM:
  python3 sinav_2442_arayuz.py [http://127.0.0.1:8000]
Cikis kodu: 0 = tumu gecti, 1 = en az bir denetim basarisiz
"""
import os
import re
import sys
import urllib.request

KOK = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
sonuc = []


def kaydet(ad, gecti, not_=""):
    sonuc.append((ad, gecti, not_))
    print(f"[{'GECTI     ' if gecti else 'BASARISIZ '}] {ad}"
          + (f"  ({not_})" if not_ else ""))


def al(yol):
    try:
        with urllib.request.urlopen(KOK + yol, timeout=10) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)


def yerel_oku(*parca):
    """Sunucudan servis EDILMEYEN dosyalar icin (goktungu/*.py).

    Betik iki yerden de calisabilir: gelistirme kokunden
    (/goktungu_244 -> goktungu/goktungu/x.py) veya kurulum kokunden
    (/goktungu -> goktungu/x.py). v2.4.42'de olculdu: yalnizca iki aday
    denendiginde gelistirme kokundeki paket bulunamiyor ve 12 denetim
    dosyayi bos okudugu icin YANLIS BASARISIZ veriyordu."""
    kok = os.path.dirname(os.path.abspath(__file__))
    adaylar = (
        os.path.join(kok, *parca),
        os.path.join(kok, "goktungu", *parca),
        os.path.join(kok, "goktungu", "goktungu", *parca),
    )
    for aday in adaylar:
        if os.path.isfile(aday):
            with open(aday, encoding="utf-8", errors="replace") as f:
                return f.read()
    return ""


def yorumsuz(js: str) -> str:
    """Yorum satirlarini eler. Aciklamalar gercek kod degildir; onlari
    saymak denetimi guvenilmez kilar (bir onceki surumde bir denetim
    yalnizca yorumdaki metni gordugu icin yanlis GECTI vermisti)."""
    js = re.sub(r'/\*.*?\*/', ' ', js, flags=re.S)
    return "\n".join(re.sub(r'//.*$', '', s) for s in js.splitlines())


def py_yorumsuz(py: str) -> str:
    """Python kaynagindan docstring ve yorumlari eler.
    DIKKAT (v2.4.41'de ogrenildi): veritabani.py'deki SQL semasi
    executescript(\"\"\"...\"\"\") icinde duruyor; bu fonksiyon uclu
    tirnakli blogu sildigi icin CREATE TABLE'lari da siler. Sema
    denetimleri HAM kaynaga bakmalidir."""
    py = re.sub(r'"""[\s\S]*?"""', ' ', py)
    py = re.sub(r"'''[\s\S]*?'''", ' ', py)
    return "\n".join(re.sub(r'#.*$', '', s) for s in py.splitlines())


def govde(js: str, ad: str) -> str:
    """Adi verilen fonksiyonun govdesini cikarir (susli sayarak).
    'Fonksiyon X icinde' kismini dosya genelinde aramak yerine gercekten
    o fonksiyonda dogrulamak icin."""
    m = re.search(r'function\s+' + re.escape(ad) + r'\s*\(', js)
    if not m:
        m = re.search(re.escape(ad) + r'\s*=\s*function\s*\(', js)
    if not m:
        return ""
    i = js.find("{", m.end() - 1)
    if i < 0:
        return ""
    derinlik, j = 0, i
    while j < len(js):
        if js[j] == "{":
            derinlik += 1
        elif js[j] == "}":
            derinlik -= 1
            if derinlik == 0:
                return js[i:j + 1]
        j += 1
    return js[i:]


def py_govde(py: str, ad: str) -> str:
    """Python fonksiyon govdesini girinti ile cikarir."""
    m = re.search(r'^([ \t]*)def\s+' + re.escape(ad) + r'\s*\(',
                  py, re.M)
    if not m:
        return ""
    girinti = len(m.group(1))
    satirlar = py[m.start():].splitlines()
    toplanan = [satirlar[0]]
    for s in satirlar[1:]:
        if s.strip() and (len(s) - len(s.lstrip())) <= girinti:
            break
        toplanan.append(s)
    return "\n".join(toplanan)


def main():
    # ---------------- 1. index.html varliklari ----------------
    kod, idx = al("/index.html")
    kaydet("index.html indirildi", kod == 200, f"HTTP {kod}")
    if kod != 200:
        print("index.html alinamadi, denetim durduruldu.")
        return 1

    varliklar = re.findall(r'(?:src|href)="([^"]+\.(?:js|css))(?:\?[^"]*)?"',
                           idx)
    eksik = []
    for v in varliklar:
        if v.startswith("http"):
            continue
        k, _ = al("/" + v.lstrip("/"))
        if k != 200:
            eksik.append(f"{v}->{k}")
    kaydet("index.html'deki tum betik/CSS varliklari indirilebiliyor",
           not eksik, ", ".join(eksik[:6]))

    yeni_dosyalar = ["js/ucus_uid.js", "js/qr.js", "js/ucus_grafik.js",
                     "js/kayitli_dronlar.js", "js/home_ikon.js"]
    kayip = [d for d in yeni_dosyalar if d not in idx]
    kaydet("v2.4.42 yeni betikleri index.html'de bildirildi",
           not kayip, "eksik: " + ", ".join(kayip) if kayip else "5/5")

    icerik = {}
    for d in yeni_dosyalar:
        k, m = al("/" + d)
        icerik[d] = m if k == 200 else ""
        kaydet(f"{d} servis ediliyor", k == 200, f"HTTP {k}")

    # ---------------- 2. Betik SIRASI ----------------
    # gecmis.js ucusKodu() cagirir; ucus_uid.js sonra yuklenirse
    # cagri ReferenceError verir, kod alani sessizce bos kalir.
    def sira(ad):
        m = re.search(r'src="' + re.escape(ad) + r'(?:\?[^"]*)?"', idx)
        return m.start() if m else -1

    p_uid, p_gecmis = sira("js/ucus_uid.js"), sira("js/gecmis.js")
    kaydet("ucus_uid.js gecmis.js'ten ONCE yukleniyor",
           p_uid > 0 and p_gecmis > 0 and p_uid < p_gecmis,
           f"uid={p_uid} gecmis={p_gecmis}")
    p_qr, p_rapor = sira("js/qr.js"), sira("js/ucus_rapor.js")
    kaydet("qr.js ucus_rapor.js'ten ONCE yukleniyor",
           p_qr > 0 and p_rapor > 0 and p_qr < p_rapor,
           f"qr={p_qr} rapor={p_rapor}")
    p_grafik = sira("js/ucus_grafik.js")
    kaydet("ucus_grafik.js qr.js'ten SONRA yukleniyor",
           p_grafik > 0 and p_qr > 0 and p_qr < p_grafik,
           f"qr={p_qr} grafik={p_grafik}")

    # ---------------- 3-5. Rapor pilot adi + arac turu ----------------
    k, rapor_js = al("/js/ucus_rapor.js")
    rapor = yorumsuz(rapor_js) if k == 200 else ""
    ug_py = yerel_oku("ucus_gecmisi.py")
    vt_py = yerel_oku("veritabani.py")

    kaydet("backend ucus kaydina pilotlar_ad alani ekliyor",
           "pilotlar_ad" in ug_py and "pilotlar_ad" in vt_py,
           "ucus_gecmisi.py + veritabani.py")
    kaydet("veritabani ad_soyad cozumlemesi yapiyor",
           "ad_soyad" in py_yorumsuz(vt_py))
    # Rapor once pilotlar_ad'a bakar, bos ise e-postaya duser.
    # Onceligi ADIN gecmesi belirler: pilotAdlar dolu ise pilotAdlar,
    # degilse pilotlar secilir (`pilotAdlar.length ? ... : pilotlar`).
    m_oncelik = re.search(r'pilotAdlar\s*(?:&&\s*pilotAdlar)?'
                          r'[^\n;]{0,40}\?\s*pilotAdlar\s*:\s*pilotlar',
                          rapor)
    kaydet("rapor pilot alaninda pilotlar_ad'i ONCE okuyor",
           "pilotlar_ad" in rapor and bool(m_oncelik),
           "ad soyad -> e-posta dususu")

    kaydet("backend arac_tipi (MAV_TYPE) alani uretiyor",
           "arac_tipi" in ug_py)
    kaydet("rapor urAracTuru() ile MAV_TYPE esliyor",
           "urAracTuru" in rapor and "arac_tipi" in rapor)
    at_govde = govde(rapor, "urAracTuru")
    kaydet("urAracTuru() MAV_TYPE sayilarini esliyor",
           bool(at_govde) and bool(re.search(r'\b(1|2|13|19|20|21)\b',
                                             at_govde)),
           f"{len(at_govde)} karakter")
    # urAracTuru() MAV_TYPE yoksa BOS string doner; cagiran taraf bos
    # degerde satiri hic eklemez (`if (aracTuru) { ... }`).
    bos_donus = bool(re.search(r'if\s*\(\s*mt\s*===\s*null[^\n]*\)'
                               r'\s*return\s*""', at_govde)) or \
                bool(re.search(r'return\s*""', at_govde))
    kosullu = bool(re.search(r'const\s+aracTuru\s*=\s*urAracTuru\('
                             r'[^\n]*\);\s*\n\s*if\s*\(\s*aracTuru\s*\)',
                             rapor))
    kaydet("MAV_TYPE bilinmiyorsa arac turu satiri yazilmiyor",
           bos_donus and kosullu,
           f"bosDonus={bos_donus} kosullu={kosullu}")

    # ---------------- 6-8. Kisa UID ----------------
    uid_js = yorumsuz(icerik.get("js/ucus_uid.js", ""))
    m_js = re.search(r'["\']([0-9A-Z]{32})["\']', uid_js)
    m_py = re.search(r'["\']([0-9A-Z]{32})["\']', py_yorumsuz(ug_py))
    kaydet("ucus_uid.js 32 karakterli alfabe tanimliyor", bool(m_js),
           m_js.group(1) if m_js else "yok")
    kaydet("ucus_gecmisi.py AYNI alfabeyi kullaniyor",
           bool(m_js) and bool(m_py) and m_js.group(1) == m_py.group(1),
           (m_py.group(1) if m_py else "yok"))
    if m_js:
        alfabe = m_js.group(1)
        yasak = [h for h in "ILOU" if h in alfabe]
        kaydet("alfabede I, L, O, U harfleri YOK", not yasak,
               "bulunan: " + "".join(yasak) if yasak else "temiz")
    # FNV-1a sabitleri iki tarafta ayni olmali. Kaynakta ONALTILIK
    # yazim kullaniliyor (0xCBF29CE484222325 / 0x100000001B3) ve JS
    # tarafinda BigInt son eki 'n' var; buyuk/kucuk harf ve son ek
    # normalize edilerek karsilastirilir. Ayrica 40 bitlik kirpma
    # maskesi de ayni olmali: farkli olsa kod uzunlugu tutar ama
    # degerler ayrisir ve iki belge celisir.
    def fnv_kume(kaynak):
        ham = re.findall(r'0x[0-9a-fA-F]{6,20}n?', kaynak)
        return {h.rstrip("n").lower() for h in ham}

    fnv_js = fnv_kume(uid_js)
    fnv_py = fnv_kume(py_yorumsuz(ug_py))
    ortak = {"0xcbf29ce484222325", "0x100000001b3", "0xffffffffff"}
    kaydet("FNV-1a sabitleri ve 40-bit maske JS ve Python'da AYNI",
           ortak <= fnv_js and ortak <= fnv_py,
           f"js={sorted(fnv_js & ortak)} py={sorted(fnv_py & ortak)}")
    nrm = govde(uid_js, "ucusKoduNormalize")
    kaydet("ucusKoduNormalize() O->0 / I->1 / L->1 duzeltmesi yapiyor",
           bool(nrm) and "O" in nrm and "I" in nrm and "L" in nrm,
           f"{len(nrm)} karakter")
    kaydet("ucus kodu XXXX-XXXX bicimi uretiyor",
           bool(re.search(r'["\']-["\']|slice\(|substr', uid_js)) and
           "ucusKodu" in uid_js)

    # ---------------- 9-12. QR ----------------
    qr_js = icerik.get("js/qr.js", "")
    qr_temiz = yorumsuz(qr_js)
    bagimlilik = [a for a in ("import ", "require(", "fetch(",
                              "cdn.", "https://unpkg", "<script")
                  if a in qr_temiz]
    kaydet("qr.js harici bagimlilik icermiyor", not bagimlilik,
           ", ".join(bagimlilik) if bagimlilik else "bagimsiz")
    kaydet("qr.js window.qrSvg tanimliyor", "window.qrSvg" in qr_js)
    grafik = yorumsuz(icerik.get("js/ucus_grafik.js", ""))
    kaydet("ucus_rapor.js window.qrSvg cagiriyor",
           "window.qrSvg" in rapor or "qrSvg(" in rapor)
    kaydet("ucus_grafik.js window.qrSvg cagiriyor",
           "window.qrSvg" in grafik or "qrSvg(" in grafik)
    # QR'in yaninda kod METNI de basilmali
    kaydet("raporda QR yaninda kod METNI de basiliyor",
           "ur-kod-deger" in rapor or
           bool(re.search(r'kod-deger|kodMetin', rapor)))
    kaydet("grafik ciktisinda QR yaninda kod METNI de basiliyor",
           "ug-kod-deger" in grafik)
    # QR icerigi URL olmamali
    url_qr = re.findall(r'qrSvg\(\s*["\']?https?:', rapor + grafik)
    kaydet("QR icerigi URL DEGIL (duz kod)", not url_qr,
           "URL bulundu" if url_qr else "duz kod")
    # QR uretimi hata verse belge iptal edilmemeli
    kaydet("QR uretimi hata verse rapor iptal EDILMIYOR",
           "try" in rapor and "qrSvg" in rapor and
           "try" in grafik and "qrSvg" in grafik)

    # ---------------- 13-19. Ucus grafikleri ----------------
    k, gecmis_js = al("/js/gecmis.js")
    gecmis = yorumsuz(gecmis_js) if k == 200 else ""
    kaydet("GRAFIKLER dugmesi ucus gecmisinde var",
           "gc-grafik-btn" in gecmis and "gcGrafikBtn" in gecmis)
    kaydet("GRAFIKLER dugmesi ucusGrafikAc cagiriyor",
           "ucusGrafikAc" in gecmis)
    k, css = al("/css/stil.css")
    css = css if k == 200 else ""
    rs = re.search(r'\.gc-rapor-satir\s*\{([^}]*)\}', css)
    kaydet("gc-rapor-satir space-between (dugmeler ayri uclarda)",
           bool(rs) and "space-between" in rs.group(1),
           (rs.group(1).strip()[:60] if rs else "kural yok"))
    kaydet("grafik ciktisi YATAY (landscape)",
           "landscape" in grafik, "@page size")
    kaydet("grafik ciktisinda ANTET var",
           "ug-antet" in grafik and "unvan" in grafik)
    kaydet("grafik ciktisinda IMZA bloklari var",
           "ug-imza" in grafik and
           ("urPilotRol" in grafik or "PILOT" in grafik) and
           ("urSahaRol" in grafik or "SAHA" in grafik))
    yz = govde(grafik, "ucusGrafikYazdir")
    kaydet("grafik ciktisi sirket bilgisi yokken URETILMIYOR",
           bool(yz) and "sirketBilgi" in yz and
           bool(re.search(r'unvan[^\n]{0,40}return|return[^\n]{0,80}unvan|'
                          r'!sirket', yz)),
           "antet uydurulmaz")
    kaydet("seriler veri yoksa null donduruyor (uydurma yok)",
           grafik.count("return null") >= 4 or
           grafik.count("? null") >= 4,
           "null kontrolleri")
    mv = re.search(r'anahtar:\s*["\']batV["\'][^}]*?sifirTaban:\s*(\w+)',
                   grafik, re.S)
    kaydet("batarya voltaji sifirTaban=false",
           bool(mv) and mv.group(1) == "false",
           mv.group(1) if mv else "bulunamadi")
    # Kaynakta sinif " yok" olarak (bosluklu) ekleniyor ve dugme
    # `disabled` yapiliyor; yani seri listeden CIKARILMIYOR.
    kaydet("verisi olmayan seri GIZLENMIYOR, pasif gosteriliyor",
           "ugSeriVarMi" in grafik and
           bool(re.search(r'var_\s*\?\s*""\s*:\s*" yok"', grafik)) and
           "disabled" in grafik and ".ug-seri.yok" in css,
           "pasif + ustu cizili")

    # ---------------- 20-23. Kayitli Dronlar ----------------
    kaydet("Kayitli Dronlar menu ogesi index.html'de",
           "mbKayitliDronlar" in idx)
    k, mb = al("/js/menubar.js")
    mb = yorumsuz(mb) if k == 200 else ""
    kaydet("menubar mbKayitliDronlar'i bagliyor",
           "mbKayitliDronlar" in mb and "kayitliDronlarAc" in mb)
    kd = yorumsuz(icerik.get("js/kayitli_dronlar.js", ""))
    kaydet("Kayitli Dronlar mevcut dron_gecmis_liste komutunu kullaniyor",
           "dron_gecmis_liste" in kd, "yeni backend komutu yok")
    sunucu_py = py_yorumsuz(yerel_oku("sunucu.py"))
    yeni_komut = re.findall(r'kayitli_dron\w*', sunucu_py)
    kaydet("sunucuya kayitli_dron* diye YENI komut eklenmedi",
           not yeni_komut, ", ".join(set(yeni_komut)) if yeni_komut else "yok")
    k, ws = al("/js/ws.js")
    ws = yorumsuz(ws) if k == 200 else ""
    dgl = re.search(r'dron_gecmis_liste[\s\S]{0,700}', ws)
    blok = dgl.group(0) if dgl else ""
    kaydet("dron_gecmis_liste cevabi kayitliDronlarVeri'ye veriliyor",
           "kayitliDronlarVeri" in ws)
    kaydet("pilot_hakkinda tuketicisi KORUNDU (ikinci tuketici)",
           "pilotHakkinda" in blok or "pilotHakkinda" in ws,
           "alan adi degistirilmedi")
    kaydet("dron listesi yetki suzgeci SUNUCUDA (istemcide degil)",
           ("yonetici" in py_yorumsuz(ug_py) or
            "yonetici" in sunucu_py) and "pilotlar" in ug_py,
           "sunucu tarafi filtre")
    kaydet("yonetici icin pilot adi listeye ekleniyor",
           "pilotlar_ad" in kd and "yonetici" in kd)

    # ---------------- 24-28. HOME POINT ----------------
    k, hm = al("/js/harita_menu.js")
    hm = yorumsuz(hm) if k == 200 else ""
    kaydet("harita menusu SHIFT kipini ayirt ediyor",
           "shiftKey" in hm and "ctrlKey" in hm)
    kaydet("SHIFT kipi HOME, CTRL kipi GOTO (kipler ayri)",
           bool(re.search(r'(home|HOME)', hm)) and
           "set_home" in hm and
           bool(re.search(r'goto|git', hm)))
    kaydet("HOME ayarlamasi ONAY istiyor",
           "onayIste" in hm and
           bool(re.search(r'onayHome|onayIste', hm)),
           "RTL/failsafe degisir")
    dr = yerel_oku("dron.py")
    dr_temiz = py_yorumsuz(dr)
    kaydet("sunucu MAV_CMD_DO_SET_HOME komutu gonderiyor",
           "DO_SET_HOME" in dr_temiz or "MAV_CMD_DO_SET_HOME" in dr_temiz)
    kaydet("sunucuda set_home aksiyonu tanimli",
           "set_home" in sunucu_py)
    kaydet("HOME sonucu arayuze bildiriliyor (sessiz basarisizlik yok)",
           "set_home_sonuc" in sunucu_py and "set_home_sonuc" in ws)
    hi = yorumsuz(icerik.get("js/home_ikon.js", ""))
    kaydet("HOME ikonu dronun RENGINDE ciziliyor",
           bool(re.search(r'renk|dronRengi|color', hi)) and
           "home" in hi.lower())
    kaydet("HOME telemetride tasiniyor (home_lat/home_lon)",
           "home_lat" in dr_temiz and "home_lat" in hi)
    hz = py_govde(dr_temiz, "hazirlik_maddeleri")
    kaydet("HOME atanmamis dron HAZIR SAYILMIYOR",
           "home" in hz.lower() and
           bool(re.search(r'kritik|engel', hz)),
           f"{len(hz)} karakter")
    kaydet("HOME maddesi denetim listesinde EN USTTE",
           bool(re.search(r'oncelik', hz)) or
           bool(re.search(r'oncelik', dr_temiz)),
           "oncelik alani")
    k, ac = al("/js/arm_check.js")
    ac = yorumsuz(ac) if k == 200 else ""
    kaydet("arm_check oncelik alanini siralamada kullaniyor",
           "oncelik" in ac)

    # ---------------- 29. v2.4.41 gerilemesi ----------------
    ucus_oku = py_govde(sunucu_py, "_ucus_oku")
    if not ucus_oku:
        m = re.search(r'ucus_oku[\s\S]{0,2500}', sunucu_py)
        ucus_oku = m.group(0) if m else ""
    bare = re.findall(r'(?<![\w.])veritabani\.', ucus_oku)
    ithal = bool(re.search(r'(from\s+\.?\s*import[^\n]*veritabani|'
                           r'import\s+veritabani|from\s+\.\s+import[^\n]*'
                           r'veritabani|\bimport\b[^\n]*veritabani)',
                           sunucu_py))
    kaydet("ucus_oku dalinda veritabani adi COZULEBILIR (NameError yok)",
           (not bare) or ithal,
           f"{len(bare)} bare kullanim, ithal={ithal}")
    # Zincir: sunucu ucus_veri.kalkis_kontrolleri -> ws.js ->
    # ucusVeriIsle -> _gecmisKalkis -> ucusRaporAc -> urKalkisBolum
    kaydet("kalkis kontrol listesi ucus kaydinda okunuyor",
           "kalkis_kontrolleri" in sunucu_py and
           "kalkis_kontrolleri" in ws and
           "_gecmisKalkis" in gecmis and
           "urKalkisBolum" in rapor,
           "sunucu -> ws -> gecmis -> rapor")

    # ---------------- 30. CSS siniflari ----------------
    # Yazdirma ciktisinin (ur-*/ug-*) stilleri stil.css'te DEGIL, ilgili
    # JS modulunun kendi baski stilinde tanimlidir: cikti ayri bir
    # iframe belgesine yazilir ve uygulama CSS'i oraya yuklenmez.
    # Bu yuzden hedef metin CSS + o iki modulun baski stilidir.
    stil_havuzu = css + grafik + rapor
    kaynaklar = (idx + gecmis + rapor + grafik + kd + hi + hm)
    siniflar = set()
    for m in re.finditer(r'(?:class|className)\s*=\s*["\']([^"\']+)["\']',
                         kaynaklar):
        for s in m.group(1).split():
            if re.match(r'^(kd|ug|gc|hm|ur|home)-', s):
                siniflar.add(s)
    for m in re.finditer(r'classList\.(?:add|toggle|remove)\('
                         r'\s*["\']([\w-]+)["\']', kaynaklar):
        s = m.group(1)
        if re.match(r'^(kd|ug|gc|hm|ur|home)-', s):
            siniflar.add(s)
    # YALIN SARMALAYICILAR muaf: bazi <div>'ler yalnizca flex cocugu
    # olarak var, kendi gorsel kurali yoktur (ust kural onlari zaten
    # konumlandirir). Bunlara bos bir CSS kurali eklemek olu kural
    # uretir. Muafiyet ADLA sinirlidir, desenle genellenmez: boylece
    # gercekten stil bekleyen bir sinif gozden kacmaz.
    SARMALAYICI_MUAF = {
        "ug-antet-metin", "ug-kod-metin",
        "ur-antet-metin", "ur-kod-metin",
    }
    tanimsiz = sorted(s for s in siniflar
                      if ("." + s) not in stil_havuzu
                      and s not in SARMALAYICI_MUAF)
    kaydet("uretilen tum kd-/ug-/gc-/hm- siniflari stilde tanimli",
           not tanimsiz,
           f"{len(siniflar)} sinif, {len(SARMALAYICI_MUAF)} sarmalayici "
           f"muaf, tanimsiz: " + ", ".join(tanimsiz[:8])
           if tanimsiz
           else f"{len(siniflar)} sinif, "
                f"{len(SARMALAYICI_MUAF)} sarmalayici muaf")

    # ---------------- 31. CSS tema degiskenleri ----------------
    # Tema degiskenleri stil.css disinda da tanimlanabilir (tema.js
    # calisma aninda ekler, ayri tema dosyalari olabilir). Bu yuzden
    # tanimlar TUM servis edilen CSS ve tema betiklerinden toplanir;
    # yalnizca stil.css'e bakmak yanlis BASARISIZ uretiyordu.
    tanim_havuzu = css
    for ek in ("/css/tema.css", "/css/pencere.css", "/js/tema.js"):
        k2, m2 = al(ek)
        if k2 == 200:
            tanim_havuzu += m2
    tanimli_var = set(re.findall(r'(--[\w-]+)\s*:', tanim_havuzu))
    # YEDEKLI kullanim (`var(--x, #fallback)`) kusur DEGILDIR: degisken
    # tanimsizsa tarayici yedek degeri uygular, yani gorsel bozulma
    # olusmaz. Kusur olan, yedeksiz `var(--x)` kullanimidir: o durumda
    # ozellik hic uygulanmaz (ornegin renk miras alinir ve metin
    # okunamaz hale gelir). Bu ayrimi yapmayan denetim, tasarim geregi
    # yedekli yazilmis 8 kullanimi yanlis BASARISIZ olarak isaretliyordu.
    yedeksiz = set(re.findall(r'var\(\s*(--[\w-]+)\s*\)', css))
    eksik_var = sorted(yedeksiz - tanimli_var)
    yedekli_eksik = sorted(
        set(re.findall(r'var\(\s*(--[\w-]+)\s*,', css)) - tanimli_var)
    kaydet("CSS'te YEDEKSIZ tanimsiz tema degiskeni kullanilmiyor",
           not eksik_var,
           ", ".join(eksik_var[:8]) if eksik_var
           else f"{len(yedekli_eksik)} tanimsiz degisken yedekli "
                f"kullanilmis (gorsel bozulma yok)")

    # ---------------- 32. i18n TR/EN esitligi ----------------
    k, i18n = al("/js/i18n.js")
    i18n = i18n if k == 200 else ""
    # Sozluk yapisi: `const DILLER = { TR: { ... }, EN: { ... } }`
    # Onceki desen ust duzey `const TR = {` ariyordu ve hicbir anahtar
    # bulamadigi icin denetim bos kumeleri karsilastiriyordu.
    tr_blok = re.search(r'^\s{2}TR\s*:\s*\{', i18n, re.M)
    en_blok = re.search(r'^\s{2}EN\s*:\s*\{', i18n, re.M)

    def anahtarlar(basla):
        if not basla:
            return set()
        i = i18n.find("{", basla.start())
        derinlik, j = 0, i
        while j < len(i18n):
            if i18n[j] == "{":
                derinlik += 1
            elif i18n[j] == "}":
                derinlik -= 1
                if derinlik == 0:
                    break
            j += 1
        return set(re.findall(r'^\s*([A-Za-z_]\w*)\s*:', i18n[i:j], re.M))

    a_tr, a_en = anahtarlar(tr_blok), anahtarlar(en_blok)
    kaydet("i18n TR ve EN anahtar kumeleri ESIT",
           bool(a_tr) and a_tr == a_en,
           f"TR={len(a_tr)} EN={len(a_en)} "
           f"trFazla={len(a_tr - a_en)} enFazla={len(a_en - a_tr)}")

    # v2.4.42'de kullanilan anahtarlar gercekten tanimli mi
    kullanilan_anh = set()
    for m in re.finditer(r'\bt\.(\w+)', gecmis + rapor + grafik + kd + hm):
        kullanilan_anh.add(m.group(1))
    for m in re.finditer(r'_t\.(\w+)', gecmis + rapor + grafik + kd + hm):
        kullanilan_anh.add(m.group(1))
    ilgili = {a for a in kullanilan_anh
              if re.match(r'^(kd|ug|gc|ur|hm|home|onayHome|dkHome)', a)}
    eksik_anh = sorted(a for a in ilgili if a not in a_tr)
    kaydet("v2.4.42 arayuz metinleri i18n'de tanimli",
           not eksik_anh,
           f"{len(ilgili)} anahtar, eksik: " + ", ".join(eksik_anh[:8])
           if eksik_anh else f"{len(ilgili)} anahtar")

    # ---------------- 33. Surum etiketleri ----------------
    k, surum = al("/js/surum.js")
    surum = surum if k == 200 else ""
    # Ileriye donuk uyum: bu denetim v2.4.42 ozelliklerini olcer, surumun
    # tam 2.4.42 olmasini SART KOSMAZ. Aksi halde v2.4.43 gibi ust surumlerde
    # islevsel gerileme olmadigi halde denetim kaliyordu (olculdu).
    def _surum_en_az(metin, en_az=(2, 4, 42)):
        m = re.search(r'GCS_SURUM\s*=\s*["\'](\d+)\.(\d+)\.(\d+)["\']', metin)
        if not m:
            return False, ""
        u = tuple(int(x) for x in m.groups())
        return u >= en_az, ".".join(str(x) for x in u)

    _uy, _bulunan = _surum_en_az(surum)
    kaydet("GCS_SURUM >= 2.4.42", _uy, _bulunan)
    kaydet("surum gecmisinde 2.4.42 kaydi var",
           's: "2.4.42"' in surum or "s: '2.4.42'" in surum)
    korunan = [s for s in ("2.4.41", "2.4.40", "2.4.35")
               if f's: "{s}"' in surum]
    kaydet("eski surum gecmisi KORUNDU (2.4.41/2.4.40/2.4.35)",
           len(korunan) == 3, ", ".join(korunan))
    init_py = yerel_oku("__init__.py")
    # DIKKAT: dosyanin yorum satirlarinda eski surum numaralari geciyor
    # ("# SURUM - TEK KAYNAK (v2.4.29)"). Bu yuzden ilk rastgele eslesme
    # DEGIL, gercek surum degiskeni (_SON_BILINEN / __version__) okunur.
    _mi = re.search(r'(?:_SON_BILINEN|__version__|SURUM)\s*=\s*'
                    r'["\'](\d+)\.(\d+)\.(\d+)["\']', init_py)
    _iu = tuple(int(x) for x in _mi.groups()) if _mi else (0, 0, 0)
    kaydet("goktungu/__init__.py surumu >= 2.4.42", _iu >= (2, 4, 42),
           ".".join(str(x) for x in _iu))

    # Onbellek etiketi: v2442 VEYA daha yeni (v2443, v2444...) kabul edilir;
    # onemli olan v2441 ve oncesinin KALMAMASI.
    def _etiket_sayilari(metin):
        yeni = len(re.findall(r'v244(?:[2-9]|\d{2,})', metin))
        eski = (metin.count("v2441") + metin.count("v2440")
                + metin.count("v2439"))
        return yeni, eski

    etiket, eski_et = _etiket_sayilari(idx)
    kaydet("index.html onbellek etiketi >= v2442", etiket > 0,
           f"{etiket} satir")
    kaydet("index.html'de eski onbellek etiketi kalmadi", eski_et == 0,
           f"{eski_et} satir")
    for yol, ad in (("/flight.html", "flight"), ("/video.html", "video")):
        k, sayfa = al(yol)
        if k == 200:
            kaydet(f"{ad} sayfasi i18n.js'i yukluyor",
                   "js/i18n.js" in sayfa)
            _y, _e = _etiket_sayilari(sayfa)
            kaydet(f"{ad} onbellek etiketi >= v2442", _y > 0 and _e == 0,
                   f"yeni={_y} eski={_e}")

    print("=" * 60)
    ok = sum(1 for _, g, _ in sonuc if g)
    print(f"SONUC: {ok}/{len(sonuc)} gecti")
    if ok != len(sonuc):
        print("\nBASARISIZ DENETIMLER:")
        for ad, g, n in sonuc:
            if not g:
                print(f"  - {ad}" + (f"  ({n})" if n else ""))
    print("=" * 60)
    return 0 if ok == len(sonuc) else 1


if __name__ == "__main__":
    sys.exit(main())
