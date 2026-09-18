#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GOKTUNGU v2.4.49 - SERVIS + KIOSK + ARAYUZ SOZLESME SINAVI

Amac: v2.4.49'un dort yeni yetenegini kurulum yerinde olcmek:
  1. systemd servisi olarak calisma (birim sablonu + kurulum betigi)
  2. SIGTERM ile duzgun kapanma (SITL temizligi, port serbest kalmasi)
  3. Arayuzden servis yonetimi (durum/baslat/durdur/yeniden/gunluk)
  4. Iki ekran kiosk duzeni + makine kapatma (yalniz yonetici)

Neden bu sinav var: v2.4.49'un cogu yetenegi CALISMA ANINDA ortaya
cikar (systemd, polkit, iki ekran). Kullanicinin makinesinde eksik bir
dosya ya da kopmus bir sozlesme "servis kurulmuyor" ya da "dugme
hicbir sey yapmiyor" olarak gorunur. Bu sinav dosya varligini,
API sozlesmesini ve arayuz-arka uc anahtar eslesmesini STATIK olarak
olcer; boylece kusur kurulumdan ONCE gorunur.

Gercek systemd davranisi ayrica Cloud Computer'da olculdu
(dene_servis_ws.py 15/0, dene_servis_eylem.py 12/0). Bu betik o
dogrulamanin yerine gecmez; kurulumun EKSIKSIZ oldugunu dogrular.

Kullanim: kurulum kokunde `python3 sinav_2449_servis.py`
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

KOK = os.path.dirname(os.path.abspath(__file__))

# --- v2.4.52 YOL KATMANI -------------------------------------------
# Klasor yapisi v2.4.52 ile degisti (main.py + assets/{web,python}).
# Bu sinav duz yapiya gore yazilmisti; asagidaki katman iki yapida da
# dogru yolu bulur. Katman yoksa eski davranis aynen surer.
try:
    import sinav_yol as _SY
except ImportError:
    _SY = None
    for _d in (KOK, os.path.dirname(KOK),
               os.path.dirname(os.path.dirname(KOK)),
               os.path.dirname(os.path.dirname(os.path.dirname(KOK)))):
        _c = os.path.join(_d, "sinav_yol.py")
        if os.path.isfile(_c):
            sys.path.insert(0, _d)
            try:
                import sinav_yol as _SY
            except ImportError:
                _SY = None
            break
if _SY is not None:
    KOK = _SY.KOK

    def _y(*parcalar):
        return _SY.coz(*parcalar)
    _SY.ice_aktarma_yolu_kur()
else:
    def _y(*parcalar):
        return _y(*parcalar)
# --------------------------------------------------------------------

if KOK not in sys.path:
    sys.path.insert(0, KOK)

_gecti = 0
_kaldi = 0
_kaldi_liste: list[str] = []


def olc(ad, kosul, ayrinti=""):
    global _gecti, _kaldi
    if kosul:
        _gecti += 1
        print("  [OK]   %s" % ad)
    else:
        _kaldi += 1
        _kaldi_liste.append(ad + ((" - " + ayrinti) if ayrinti else ""))
        print("  [KALDI] %s%s" % (ad, (" - " + ayrinti) if ayrinti else ""))


def oku(*parcalar):
    yol = _y(*parcalar)
    if not os.path.isfile(yol):
        return ""
    with open(yol, encoding="utf-8", errors="replace") as f:
        return f.read()


def main():
    print("=" * 70)
    print("GOKTUNGU v2.4.49 - SERVIS + KIOSK + ARAYUZ SOZLESME SINAVI")
    print("=" * 70)

    # ------------------------------------------------------------------
    print("\n--- 1) SURUM TUTARLILIGI ---")
    # ------------------------------------------------------------------
    # NOT: Bu sinav v2.4.49'da yazildi, ancak sonraki surumlerde de
    # gerileme sinavi olarak kosturulur. Bu yuzden surum denetimi
    # "tam esitlik" DEGIL "en az 2.4.49" mantigiyla yapilir. Aksi
    # halde her yeni surumde bu sinav gercek bir kusur olmadigi halde
    # KALDI verir ve zamanla "nasil olsa kaliyor" diye goz ardi
    # edilerek asil kusurlari da gizler.
    def _surum_no(metin):
        """Metindeki en buyuk 2.4.x surum numarasini (x) dondurur."""
        bulunan = re.findall(r"2\.4\.(\d+)", metin or "")
        return max((int(b) for b in bulunan), default=-1)

    surum_js = oku("js", "surum.js")
    init_py = oku("goktungu", "__init__.py")
    ASGARI = 49
    js_no = _surum_no(surum_js)
    py_no = _surum_no(init_py)
    olc("js/surum.js surumu >= 2.4.%d (olculen 2.4.%d)" % (ASGARI, js_no),
        js_no >= ASGARI)
    olc("goktungu/__init__.py surumu >= 2.4.%d (olculen 2.4.%d)"
        % (ASGARI, py_no), py_no >= ASGARI)
    olc("surum.js gecmisinde 2.4.49 girdisi korunur",
        "2.4.49" in surum_js)
    # Surum ile onbellek etiketi UYUSMALI: surum yukseltilip etiket
    # eski kalirsa tarayici eski JS'i onbellekten sunar ve kullanici
    # "guncelledim ama degismedi" der. Bu, surumden bagimsiz olcumdur.
    for dosya in ("index.html", "flight.html", "video.html"):
        icerik = oku(dosya)
        if not icerik:
            continue
        etiketler = set(re.findall(r"v=v24(\d\d)", icerik))
        beklenen = "%02d" % js_no
        olc("%s onbellek etiketi surumle uyusur (v24%s)"
            % (dosya, beklenen),
            etiketler == {beklenen},
            "bulunan=%s beklenen=%s -> tarayici eski js kullanir"
            % (sorted(etiketler), beklenen))

    # ------------------------------------------------------------------
    print("\n--- 2) goktungu/servis.py MODULU VE API SOZLESMESI ---")
    # ------------------------------------------------------------------
    servis_yolu = _y("goktungu", "servis.py")
    olc("goktungu/servis.py var", os.path.isfile(servis_yolu))
    servis_kaynak = oku("goktungu", "servis.py")

    if servis_kaynak:
        olc("ServisYoneticisi sinifi tanimli",
            "class ServisYoneticisi" in servis_kaynak)
        # Arayuzun ve sunucunun cagirdigi TUM yontemler
        for yontem in ("durum", "gunluk", "eylem", "eylem_hazir",
                       "gecikmeli_eylem", "guc", "guc_hazir", "ozet",
                       "kip_olc"):
            olc("servis.%s() tanimli" % yontem,
                re.search(r"def\s+%s\s*\(" % yontem, servis_kaynak)
                is not None,
                "sunucu.py bu yontemi cagiriyor")

        # KRITIK: yetki olcumu sudo -n -l ile yapilmali.
        # --dry-run yetkisiz kullanicida da 0 doner (Cloud Computer'da
        # olculdu) -> dugme etkin gorunur ama HICBIR SEY olmaz.
        olc("yetki olcumu 'sudo -n -l' temelli",
            "-n" in servis_kaynak and "-l" in servis_kaynak and
            "sudo" in servis_kaynak,
            "--dry-run yetkiyi olcmez; yanlis pozitif verir")
        olc("yetki olcumu --dry-run'a DAYANMIYOR",
            servis_kaynak.count("--dry-run") == 0 or
            "sudo" in servis_kaynak)

        # guc() anahtarlari: kapat / yenidenbaslat (alt cizgi YOK)
        olc("guc() 'kapat' anahtarini biliyor", "kapat" in servis_kaynak)
        olc("guc() 'yenidenbaslat' anahtarini biliyor",
            "yenidenbaslat" in servis_kaynak,
            "alt cizgili yazim systemctl'e yanlis komut gonderir")

        # eylem sozlugu
        for ey in ("baslat", "durdur", "yeniden_baslat", "etkinlestir",
                   "devredisi"):
            olc("_EYLEMLER['%s'] tanimli" % ey, ey in servis_kaynak)

        olc("eylem() SOZLUK donuyor (tamam anahtari)",
            '"tamam"' in servis_kaynak or "'tamam'" in servis_kaynak,
            "ikili donerse sunucu.py yanlis okur")

    # ------------------------------------------------------------------
    print("\n--- 3) main.py SIGTERM + PORT KAYDI ---")
    # ------------------------------------------------------------------
    main_kaynak = oku("main.py")
    olc("SIGTERM isleyicisi kuruluyor (_sigterm_kur)",
        "_sigterm_kur" in main_kaynak,
        "systemctl stop SIGTERM gonderir; isleyici yoksa SITL yetim kalir")
    olc("kapanis temizligi ayri islevde (_kapanis_temizligi)",
        "_kapanis_temizligi" in main_kaynak,
        "finally icinde kalirsa SIGTERM yolundan cagrilamaz")
    # KRITIK: asyncio.run() cikisi _cancel_all_tasks'ta bloke oluyordu
    # (py-spy ile olculdu). Bu yuzden os._exit sart.
    olc("os._exit ile kesin cikis var",
        "os._exit" in main_kaynak or "_exit(" in main_kaynak,
        "asyncio.run() kapanisi _cancel_all_tasks'ta sonsuz bekliyor")
    olc("SIGHUP de yakalaniyor", "SIGHUP" in main_kaynak)
    olc("_port_dosyasi_yaz() tanimli", "_port_dosyasi_yaz" in main_kaynak)
    olc("veri/calisma.json'a yaziliyor", "calisma.json" in main_kaynak,
        "kiosk betigi portu bu dosyadan okur")
    olc("ServisYoneticisi kuruluyor", "ServisYoneticisi" in main_kaynak)
    olc("servis sunucuya baglaniyor",
        re.search(r"\.servis\s*=", main_kaynak) is not None)

    # ------------------------------------------------------------------
    print("\n--- 4) sunucu.py WS KOMUTLARI VE YETKI DENETIMI ---")
    # ------------------------------------------------------------------
    sunucu_kaynak = oku("goktungu", "sunucu.py")
    olc("aktif_port niteligi var", "aktif_port" in sunucu_kaynak)
    olc("aktif_ws_port niteligi var", "aktif_ws_port" in sunucu_kaynak)
    olc("self.servis alani var",
        re.search(r"self\.servis\s*=", sunucu_kaynak) is not None)

    for komut in ("servis_durum", "servis_eylem", "servis_gunluk",
                  "makine_kapat"):
        olc("WS komutu '%s' islenıyor" % komut,
            ('komut == "%s"' % komut) in sunucu_kaynak,
            "arayuz gonderir, sunucu yanit vermez -> dugme olu")

    # KRITIK GUVENLIK: pilot.py izin_var() TANIMSIZ izni True sayar.
    # Bu yuzden IZIN_HARITASI'na eklemek YETMEZ; acik rol denetimi sart.
    # Aksi halde normal pilot ucus sirasinda makineyi kapatabilir.
    servis_bolum = sunucu_kaynak
    kesit = servis_bolum[servis_bolum.find('komut == "servis_durum"'):]
    kesit = kesit[:12000] if kesit else ""
    olc("servis komutlarinda acik rol denetimi var",
        kesit.count('!= "yonetici"') >= 3,
        "izin_var() tanimsiz izni True sayar -> her pilot servisi durdurur")
    olc("makine_kapat'ta rol denetimi var",
        '!= "yonetici"' in servis_bolum[
            servis_bolum.find('komut == "makine_kapat"'):][:4000],
        "ucus sirasinda pilotun makineyi kapatmasi yikici")

    # durdur/yeniden: yanit ONCE, eylem SONRA (kendini durdurma tuzagi)
    olc("durdur/yeniden icin gecikmeli eylem kullaniliyor",
        "gecikmeli_eylem" in sunucu_kaynak,
        "servis kendini once durdurursa yanit hic gitmez")
    olc("yanitta 'beklemede' isareti var", "beklemede" in sunucu_kaynak,
        "arayuz WS kopmasini hata sanip yanlis uyari verir")
    # arayuz "yeniden" der, servis.py "yeniden_baslat" bekler
    olc("'yeniden' -> 'yeniden_baslat' cevrimi yapiliyor",
        "yeniden_baslat" in sunucu_kaynak,
        "cevrim yoksa servis.py komutu taniyamaz")

    # ------------------------------------------------------------------
    print("\n--- 5) ARAYUZ: js/servis_panel.js ---")
    # ------------------------------------------------------------------
    panel = oku("js", "servis_panel.js")
    olc("js/servis_panel.js var", bool(panel))
    if panel:
        for isv in ("svBolumEkle", "svDurumGeldi", "svSonucGeldi",
                    "svGunlukGeldi", "svMakineSonucGeldi", "svDurumIste",
                    "makineGucGorunumTazele"):
            olc("window.%s tanimli" % isv, ("window." + isv) in panel,
                "ws.js bu islevi cagiriyor")
        olc("onay diyalogu kullaniliyor (onayIste)", "onayIste" in panel,
            "kullanici 'eminmisiniz' onayi istedi")
        olc("bildirim toast kullaniliyor", "uyariToastGoster" in panel)
        # CSS onegi svc- olmali: .sv-rozet ONCEDEN AI arama seviyesi
        # icin kullaniliyordu; ayni ad cakisir ve gorunum bozulur.
        olc("CSS onegi 'svc-' (AI 'sv-' ile cakismiyor)",
            "svc-" in panel,
            ".sv-rozet AI seviye rozeti icin zaten kullaniliyor")

    prog = oku("js", "program_ayar.js")
    olc("program_ayar.js servis bolumunu cagiriyor",
        "svBolumEkle" in prog,
        "panel dosyasi yuklenir ama hicbir yerde gorunmez")

    ws_js = oku("js", "ws.js")
    for tip in ("servis_durum", "servis_sonuc", "servis_gunluk",
                "makine_sonuc"):
        olc("ws.js '%s' mesajini yonlendiriyor" % tip, tip in ws_js,
            "sunucu yanit verir, arayuz sessiz kalir")

    index = oku("index.html")
    olc("index.html servis_panel.js betigini yukluyor",
        "servis_panel.js" in index)
    olc("profil menusunde pmMakineKapat var", "pmMakineKapat" in index)
    olc("profil menusunde pmMakineYeniden var", "pmMakineYeniden" in index)

    kullanici = oku("js", "kullanici.js")
    olc("makine dugmeleri yalniz yoneticiye gosteriliyor",
        "makineGucGorunumTazele" in kullanici,
        "her pilot 'Bilgisayari Kapat' gorurse ucus riski")

    stil = oku("css", "stil.css")
    olc("css/stil.css .svc- siniflari tanimli", ".svc-" in stil)

    # ------------------------------------------------------------------
    print("\n--- 6) i18n DENGESI VE SERVIS ANAHTARLARI ---")
    # ------------------------------------------------------------------
    i18n = oku("js", "i18n.js")
    for anahtar in ("svBaslik", "svAktif", "svBaslat", "svDurdur",
                    "svYeniden", "svGunluk", "svGucBaslik", "svKapatSoru",
                    "pmMakineKapat", "pmMakineYeniden"):
        olc("i18n anahtari '%s' var" % anahtar, anahtar in i18n,
            "arayuzde ham anahtar adi ya da yedek metin gorunur")

    # TR/EN denge olcumu: bir tarafta eksik anahtar -> dil degisince
    # o metin kaybolur. Denge sayisal olarak olculur.
    tr_bas = i18n.find("TR: {")
    en_bas = i18n.find("EN: {")
    if tr_bas > 0 and en_bas > tr_bas:
        tr_blok = i18n[tr_bas:en_bas]
        en_blok = i18n[en_bas:]
        desen = re.compile(r"^\s{2,}([A-Za-z_][A-Za-z0-9_]*)\s*:", re.M)
        tr_anahtarlar = set(desen.findall(tr_blok))
        en_anahtarlar = set(desen.findall(en_blok))
        eksik_en = sorted(tr_anahtarlar - en_anahtarlar)
        eksik_tr = sorted(en_anahtarlar - tr_anahtarlar)
        olc("i18n TR/EN denge (TR=%d EN=%d)" %
            (len(tr_anahtarlar), len(en_anahtarlar)),
            not eksik_en and not eksik_tr,
            "EN'de eksik: %s | TR'de eksik: %s" %
            (eksik_en[:5], eksik_tr[:5]))
    else:
        olc("i18n blok yapisi okunabildi", False, "TR:/EN: bulunamadi")

    # ------------------------------------------------------------------
    print("\n--- 7) systemd BIRIM SABLONU ---")
    # ------------------------------------------------------------------
    sablon = oku("goktungu.service.sablon")
    olc("goktungu.service.sablon var", bool(sablon))
    if sablon:
        for yer in ("@KULLANICI@", "@KOK@", "@PYTHON@"):
            olc("sablon yer tutucusu %s var" % yer, yer in sablon)
        olc("WorkingDirectory tanimli", "WorkingDirectory" in sablon,
            "alt surecler cwd=kok bekliyor")
        # AGENTS.md kurali: Restart=always + kalici hata = sonsuz dongu
        olc("Restart=on-failure (always DEGIL)",
            "Restart=on-failure" in sablon,
            "always + yapilandirma hatasi = sonsuz dongu, journal siser")
        olc("StartLimitBurst ile dongu korumasi var",
            "StartLimitBurst" in sablon)
        olc("KillMode=mixed (SITL temizligi icin)",
            "KillMode=mixed" in sablon,
            "control-group tum alt surecleri aninda oldurur")
        olc("TimeoutStopSec tanimli", "TimeoutStopSec" in sablon)
        olc("root olarak calismiyor (User= var)", "User=" in sablon,
            "root calisirsa veri/ dosyalari root'a gecer")
        olc("StandardError=journal", "journal" in sablon)

    # ------------------------------------------------------------------
    print("\n--- 8) servis_kur.sh KURULUM BETIGI ---")
    # ------------------------------------------------------------------
    kur = oku("servis_kur.sh")
    olc("servis_kur.sh var", bool(kur))
    if kur:
        olc("birim dosyasini /etc/systemd/system'e yaziyor",
            "/etc/systemd/system" in kur)
        olc("daemon-reload cagiriliyor", "daemon-reload" in kur)
        olc("systemctl enable ile acilista baslatiyor",
            "enable" in kur, "kullanici 'bilgisayar acilinca otomatik' istedi")
        # Uc bicim yetki: tasinabilirlik icin sart
        olc("sudoers yetkisi yaziliyor", "sudoers.d" in kur)
        olc("sudoers visudo -c ile dogrulaniyor", "visudo" in kur,
            "bozuk sudoers TUM sudo erisimini kirar")
        olc("modern polkit JS kurali yaziliyor", "rules.d" in kur)
        olc("eski polkit pkla yaziliyor", "pkla" in kur,
            "polkit 0.105'te rules.d YOK; pkla sart")
        olc("kiosk autostart girdisi yaziliyor", "autostart" in kur)
        olc("--kaldir destegi var", "kaldir" in kur)
        olc("kiosk_baslat.sh varligi denetleniyor",
            "kiosk_baslat.sh" in kur)

    # ------------------------------------------------------------------
    print("\n--- 9) kiosk_baslat.sh IKI EKRAN DUZENI ---")
    # ------------------------------------------------------------------
    kiosk = oku("kiosk_baslat.sh")
    olc("kiosk_baslat.sh var", bool(kiosk))
    if kiosk:
        # Port TAHMIN EDILMEZ: sunucu 8000 mesgulse 8080'e duser ve
        # kiosk yanlis adrese baglanir (bos sayfa).
        olc("port veri/calisma.json'dan okunuyor",
            "calisma.json" in kiosk,
            "port tahmin edilirse kiosk bos sayfa acar")
        olc("index.html birinci ekranda", "index.html" in kiosk)
        olc("flight.html ikinci ekranda", "flight.html" in kiosk)
        # Kullanici "arayuzdeki tam ekran dugmesi" dedi -> kiosk kipi DEGIL
        olc("--start-fullscreen kullaniliyor",
            "--start-fullscreen" in kiosk,
            "JS tam ekran kullanici hareketi olmadan sessizce reddedilir")
        olc("kiosk kipi kullanilMIYOR (kullanici istegi)",
            "--kiosk" not in kiosk,
            "kullanici sekme/adres cubugu gizlenmesini istemedi")
        olc("her pencere ayri --user-data-dir",
            kiosk.count("--user-data-dir") >= 1,
            "ayni profil ikinci pencereyi sekme yapar")
        olc("ekran konumu xrandr ile olculuyor", "xrandr" in kiosk,
            "ekran adi degil KOORDINAT gerekiyor")
        olc("--window-position ile ikinci ekrana tasiniyor",
            "--window-position" in kiosk)
        olc("--durdur destegi var", "durdur" in kiosk)

    # ------------------------------------------------------------------
    print("\n--- 10) CALISMA ANI: veri/calisma.json ---")
    # ------------------------------------------------------------------
    calisma = _y("veri", "calisma.json")
    if os.path.isfile(calisma):
        try:
            with open(calisma, encoding="utf-8") as f:
                d = json.load(f)
            olc("calisma.json gecerli JSON", True)
            for alan in ("http_port", "ws_port", "pid", "surum"):
                olc("calisma.json '%s' alani var" % alan, alan in d)
            olc("http_port sayi ve gecerli aralikta",
                isinstance(d.get("http_port"), int) and
                0 < int(d.get("http_port", 0)) < 65536,
                str(d.get("http_port")))
        except Exception as e:
            olc("calisma.json okunabilir", False, str(e))
    else:
        print("  [ATLA] veri/calisma.json yok (sunucu calismiyor);"
              " bu dosya sunucu ayaga kalkinca olusur")

    # ------------------------------------------------------------------
    print("\n--- 11) SOZDIZIMI DENETIMI ---")
    # ------------------------------------------------------------------
    for py in ("main.py", os.path.join("goktungu", "servis.py"),
               os.path.join("goktungu", "sunucu.py")):
        yol = _y(py)
        if os.path.isfile(yol):
            s = subprocess.run([sys.executable, "-m", "py_compile", yol],
                               capture_output=True, text=True)
            olc("%s sozdizimi tamam" % py, s.returncode == 0,
                (s.stderr or "")[:160])

    node = None
    for aday in ("node", "nodejs"):
        try:
            subprocess.run([aday, "--version"], capture_output=True,
                           timeout=10)
            node = aday
            break
        except Exception:
            continue
    if node:
        for js in ("servis_panel.js", "program_ayar.js", "ws.js",
                   "kullanici.js", "i18n.js"):
            yol = _y("js", js)
            if os.path.isfile(yol):
                s = subprocess.run([node, "--check", yol],
                                   capture_output=True, text=True)
                olc("js/%s sozdizimi tamam" % js, s.returncode == 0,
                    (s.stderr or "")[:160])
    else:
        print("  [ATLA] node yok; JS sozdizimi olculemedi")

    for sh in ("servis_kur.sh", "kiosk_baslat.sh"):
        yol = _y(sh)
        if os.path.isfile(yol):
            s = subprocess.run(["bash", "-n", yol], capture_output=True,
                               text=True)
            olc("%s sozdizimi tamam" % sh, s.returncode == 0,
                (s.stderr or "")[:160])

    # ------------------------------------------------------------------
    print()
    print("=" * 70)
    print("SONUC: %d gecti / %d kaldi" % (_gecti, _kaldi))
    if _kaldi_liste:
        print()
        print("KALAN MADDELER:")
        for k in _kaldi_liste:
            print("  - %s" % k)
    print("=" * 70)
    return 0 if _kaldi == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
