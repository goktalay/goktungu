#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""FAZ 8 KONTROL DENEYİ — sınav gerçekten kusur yakalıyor mu?

`sinav_kopru_yetki.py` 90/0 verdi. Bu tek başına bir şey kanıtlamaz:
sınav hiçbir şeyi gerçekten ölçmüyor da olabilir. Bu betik kaynağa
KASITLI kusurlar enjekte eder, her enjeksiyondan sonra sınavı koşar ve
sınavın KALDI verip vermediğini sayar.

Yakalanmayan enjeksiyon = sınavda kör nokta = düzeltilmesi gereken kusur.

Her enjeksiyon, dosyayı yedekleyip değiştirir ve ölçüm sonrası GERİ
YÜKLER. Betik yarıda kesilse bile `.kontrol_yedek/` dizininden elle geri
yüklenebilir.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

KOK = os.path.dirname(os.path.abspath(__file__))
YEDEK = os.path.join(KOK, ".kontrol_yedek")
SINAV = os.path.join(KOK, "sinav_kopru_yetki.py")
MK_KIMLIK = "/home/ubuntu/merkez_calisma/mk_kimlik.py"

# (etiket, dosya_yolu, bul, degistir)
ENJEKSIYONLAR = [
    # --- Yetki süzgeci çekirdeği -------------------------------------
    ("K01 yetki sözlüğü yoksa HER ŞEY açılır (bedelsiz modül)",
     "kopru/servisler.py",
     "    if not isinstance(yetkiler, dict):\n        return False",
     "    if not isinstance(yetkiler, dict):\n        return True"),

    ("K02 yetki denetimi tersine döner",
     "kopru/servisler.py",
     "    return bool(yetkiler.get(anahtar))",
     "    return not bool(yetkiler.get(anahtar))"),

    ("K03 tüm servisler çekirdek sayılır (denetim tamamen kalkar)",
     "kopru/servisler.py",
     "    anahtar = SERVIS_YETKI.get(str(ad), None)",
     "    anahtar = None"),

    ("K04 gcsdual yanlış anahtara bağlanır (isim ayrışıklığı)",
     "kopru/servisler.py",
     '    "gcsdual": "gccdual",',
     '    "gcsdual": "gcsdual",'),

    ("K05 radar eşleme tablosundan düşer (ücretsiz açılır)",
     "kopru/servisler.py",
     '    "radar": "radar",',
     '    "radar": None,'),

    ("K06 ai eşleme tablosundan silinir",
     "kopru/servisler.py",
     '    "ai": "ai",\n',
     ''),

    ("K07 çekirdek dron ücretli sayılır (köprü işlevsiz kalır)",
     "kopru/servisler.py",
     '    "dron": None,',
     '    "dron": "dron",'),

    # --- ServisYoneticisi süzgeci ------------------------------------
    ("K08 durum() süzgeci hiç uygulanmaz",
     "kopru/servisler.py",
     "        if yetkiler is not None:\n"
     "            adlar = [a for a in adlar if servis_gorunur_mu(a, yetkiler)]",
     "        if False:\n"
     "            adlar = [a for a in adlar if servis_gorunur_mu(a, yetkiler)]"),

    ("K09 durum(None) da süzülür (merkeze eksik liste gider)",
     "kopru/servisler.py",
     "        if yetkiler is not None:\n"
     "            adlar = [a for a in adlar if servis_gorunur_mu(a, yetkiler)]",
     "        adlar = [a for a in adlar if servis_gorunur_mu(a, yetkiler)]"),

    ("K10 süzgeç sıralamayı bozar",
     "kopru/servisler.py",
     "        adlar = sirali + ekstra",
     "        adlar = sorted(sirali + ekstra, reverse=True)"),

    # --- baslat() yetki kapısı ---------------------------------------
    ("K11 baslat() yetki kapısı kalkar (uç doğrudan çağrılabilir)",
     "kopru/servisler.py",
     "        if yetkiler is not None and not servis_gorunur_mu(ad, yetkiler):",
     "        if False:"),

    ("K12 baslat() reddeder ama alt süreci ÖNCE açar",
     "kopru/servisler.py",
     "        if yetkiler is not None and not servis_gorunur_mu(ad, yetkiler):\n"
     "            return False, (\"Bu servis firmanizin uyeliginde tanimli degil \"\n"
     "                           \"(%s). Kurumsal panelden yetki talep edin.\" % ad)",
     "        if yetkiler is not None and not servis_gorunur_mu(ad, yetkiler):\n"
     "            s.baslat(ortam_ek)\n"
     "            return False, (\"Bu servis firmanizin uyeliginde tanimli degil \"\n"
     "                           \"(%s). Kurumsal panelden yetki talep edin.\" % ad)"),

    ("K13 ret gerekçesi yönlendirme içermez",
     "kopru/servisler.py",
     "            return False, (\"Bu servis firmanizin uyeliginde tanimli degil \"\n"
     "                           \"(%s). Kurumsal panelden yetki talep edin.\" % ad)",
     "            return False, \"Hata\""),

    ("K14 durdurma da yetkiye tabi olur (kapatılamayan servis)",
     "kopru/servisler.py",
     "    def durdur(self, ad, yetkiler=None):\n"
     "        s = self.al(ad)\n"
     "        if not s:\n"
     "            return False, \"Bilinmeyen servis: %s\" % ad",
     "    def durdur(self, ad, yetkiler=None):\n"
     "        s = self.al(ad)\n"
     "        if not s:\n"
     "            return False, \"Bilinmeyen servis: %s\" % ad\n"
     "        if yetkiler is not None and not servis_gorunur_mu(ad, yetkiler):\n"
     "            return False, \"Yetki yok\""),

    # --- Merkez giriş yanıtı -----------------------------------------
    ("K15 giriş yanıtında merkez_lisans hiç gönderilmez",
     MK_KIMLIK,
     '        k["merkez_lisans"] = bool(_y.get("merkez_lisans"))',
     '        pass  # merkez_lisans kaldirildi'),

    ("K16 hata durumunda merkez_lisans True varsayılır",
     MK_KIMLIK,
     '        k["merkez_lisans"] = False\n        k["sinirsiz"] = False',
     '        k["merkez_lisans"] = True\n        k["sinirsiz"] = True'),

    ("K17 hata durumunda radar/gccdual açık varsayılır",
     MK_KIMLIK,
     '        k["yetkiler"] = {"dron": True, "video": True, "ai": False,\n'
     '                         "radar": False, "gccdual": False}',
     '        k["yetkiler"] = {"dron": True, "video": True, "ai": True,\n'
     '                         "radar": True, "gccdual": True}'),

    ("K18 merkez_lisans yetki motoru yerine elle SQL ile okunur",
     MK_KIMLIK,
     '        _y = _yetki.firma_yetkileri(int(k["firma_id"]))',
     '        _y = db.tek("SELECT merkez_lisans FROM firmalar '
     'WHERE firma_id=%s", (k["firma_id"],)) or {}'),

    # --- Panel uçları ------------------------------------------------
    ("K19 /api/durum kullanıcı demetinden yetkiler düşer",
     "kopru/panel.py",
     '                                   "firma_kisa_ad", "yetkiler")},',
     '                                   "firma_kisa_ad")},'),

    ("K20 /api/durum servis listesini süzmez",
     "kopru/panel.py",
     '"servisler": u.servis_durumu_zengin(yetkiler),',
     '"servisler": u.servis_durumu_zengin(),'),

    ("K21 /api/servis/baslat sunucu denetimini atlar",
     "kopru/panel.py",
     '            tamam, hata = u.servisler.baslat(g.get("servis"),\n'
     '                                             yetkiler=o.get("yetkiler"))',
     '            tamam, hata = u.servisler.baslat(g.get("servis"))'),

    ("K22 merkez seçimi ucu ağdan çağrılabilir hale gelir",
     "kopru/panel.py",
     '            if self._yerel_zorunlu():\n'
     '                return\n'
     '            if str(o.get("rol") or "") != "yonetici":',
     '            if str(o.get("rol") or "") != "yonetici":'),

    ("K23 merkez seçimini pilot da yapabilir",
     "kopru/panel.py",
     '            if str(o.get("rol") or "") != "yonetici":\n'
     '                self._hata("Bu islem icin yonetici rolu gerekir", 403)\n'
     '                return',
     '            pass'),

    ("K24 merkez seçim ucu tamamen kalkar",
     "kopru/panel.py",
     '        if yol == "/api/merkez/secim":',
     '        if yol == "/api/merkez/secim_KAPALI":'),

    # --- Uygulama katmanı --------------------------------------------
    ("K25 bulut seçiminde eski adres korunur (seçim etkisiz)",
     "kopru/uygulama.py",
     '            self.ayar_kaydet({\n'
     '                "merkez_adres": ayar_mod.VARSAYILAN_MERKEZ,\n'
     '                "merkez_http": ayar_mod.VARSAYILAN_MERKEZ_HTTP,\n'
     '            })',
     '            pass  # adres degistirilmez'),

    ("K26 kendi sunucu seçiminde boş adres kabul edilir",
     "kopru/uygulama.py",
     '            if not d:\n'
     '                return {"hata": "Kendi merkez sunucunuzun adresini girin"}',
     '            if False:\n'
     '                return {"hata": "x"}'),

    ("K27 adres doğrulaması atlanır (ayar dosyasına ham yazım)",
     "kopru/uygulama.py",
     '            sonuc = self.ayar_kaydet(g)\n'
     '            if isinstance(sonuc, dict) and sonuc.get("hata"):\n'
     '                return sonuc',
     '            ayar_mod.ayar_guncelle(**g)'),

    ("K28 seçim sonrası ajan yenilenmez (eski merkeze bağlı kalır)",
     "kopru/uygulama.py",
     '            self.kimlik_yenile()',
     '            pass  # ajan yenilenmez'),

    ("K29 servis_durumu_zengin süzgeci yok sayar",
     "kopru/uygulama.py",
     '        liste = self.servisler.durum(yetkiler)',
     '        liste = self.servisler.durum()'),

    ("K30 ayar_maskeli seçim durumunu bildirmez (soru hep sorulur)",
     "kopru/uygulama.py",
     '            "merkez_secim_yapildi": bool(a.get("merkez_secim_yapildi")),',
     '            "merkez_secim_yapildi_YOK": False,'),

    # --- Ayar --------------------------------------------------------
    ("K31 yeni kurulumda seçim yapılmış sayılır (soru hiç sorulmaz)",
     "kopru/ayar.py",
     '    "merkez_secim_yapildi": False,',
     '    "merkez_secim_yapildi": True,'),

    ("K32 merkez_kendi alanı ayar varsayılanından silinir",
     "kopru/ayar.py",
     '    "merkez_kendi": False,\n',
     ''),

    # --- Arayüz ------------------------------------------------------
    ("K33 pencere HTML'den silinir",
     "web/index.html",
     'id="merkezSecimPencere"',
     'id="merkezSecimPencere_OLU"'),

    ("K34 pencereye kapatma düğmesi eklenir (soru atlanabilir)",
     "web/index.html",
     '      <h3>Merkez Sunucu Bağlantısı</h3>',
     '      <h3>Merkez Sunucu Bağlantısı</h3>\n'
     '      <button type="button" id="merkezSecimKapat" class="kapat">×</button>'),

    ("K35 bulut seçeneği öntanımlı işaretli değil",
     "web/index.html",
     'id="msBulut" value="bulut" checked',
     'id="msBulut" value="bulut"'),

    ("K36 kendi sunucu adres alanı silinir",
     "web/index.html",
     'id="msAdres"',
     'id="msAdres_OLU"'),

    ("K37 aynı makinede birlikte çalışma anlatımı silinir",
     "web/index.html",
     '<code>wss://127.0.0.1:9443/kopru</code>',
     '<code>kendi adresiniz</code>'),

    ("K38 script sürüm etiketi tazelenmemiş (tarayıcı eski JS'i alır)",
     "web/index.html",
     '<script src="uygulama.js?v=3"></script>',
     '<script src="uygulama.js?v=2"></script>'),

    ("K39 JS lisans koşulunu atlar (herkese sorulur)",
     "web/uygulama.js",
     '  if(!kul.merkez_lisans) return false;',
     '  if(false) return false;'),

    ("K40 JS rol koşulunu atlar (pilota da sorulur)",
     "web/uygulama.js",
     "  if(String(kul.rol||'') !== 'yonetici') return false;",
     "  if(false) return false;"),

    ("K41 JS soruyu her girişte sorar",
     "web/uygulama.js",
     '  if(ayar.merkez_secim_yapildi) return false;',
     '  if(false) return false;'),

    # DIKKAT: desen MERKEZ SECIMI dalina bagli olmali. Ilk denemede
    # yalnizca `}).catch(function(e){` yazilmisti; bu desen dosyada 5
    # yerde geciyor ve enjeksiyon GIRIS islevine uygulaniyordu, yani
    # merkez secimi dalinda hicbir kusur uretmiyordu (sinav hakliydi).
    ("K42 JS başarısız kayıtta pencereyi kapatır",
     "web/uygulama.js",
     "      hataGoster(d('merkezSecimHata'), e.message);",
     "      gizle(d('merkezSecimPencere'));\n"
     "      hataGoster(d('merkezSecimHata'), e.message);"),

    ("K43 çıkışta soru bayrağı sıfırlanmaz",
     "web/uygulama.js",
     '      merkezSecimGosterildi = false;\n'
     "      gizle(d('merkezSecimPencere'));",
     '      // bayrak sifirlanmaz'),

    ("K44 seçili servis düşerse panel donar",
     "web/uygulama.js",
     '  if(!seciliVar){',
     '  if(false){'),

    ("K45 panel süzgeci arayüzde yineler (iki doğruluk kaynağı)",
     "web/uygulama.js",
     '  menuCiz(liste);\n  anaCiz();',
     '  liste = liste.filter(function(s){\n'
     "    if(s.ad === 'radar') return !!(v.kullanici||{}).yetkiler.radar;\n"
     '    return true;\n  });\n  menuCiz(liste);\n  anaCiz();'),

    ("K46 merkezSecimDenetle hiç çağrılmaz",
     "web/uygulama.js",
     '  merkezSecimDenetle(v);',
     '  // denetim cagrilmaz'),

    ("K47 merkezSecimKur açılışta bağlanmaz",
     "web/uygulama.js",
     '  merkezSecimKur();\n',
     ''),

    ("K48 JS seçimi yanlış uca gönderir",
     "web/uygulama.js",
     "    istek('/api/merkez/secim', { method:'POST', govde:{",
     "    istek('/api/ayar', { method:'POST', govde:{"),
]


def yedekle(hedef: str) -> str:
    os.makedirs(YEDEK, exist_ok=True)
    ad = hedef.replace("/", "__")
    y = os.path.join(YEDEK, ad)
    if not os.path.exists(y):
        shutil.copy2(tam_yol(hedef), y)
    return y


def tam_yol(hedef: str) -> str:
    return hedef if hedef.startswith("/") else os.path.join(KOK, hedef)


def geri_yukle(hedef: str) -> None:
    ad = hedef.replace("/", "__")
    y = os.path.join(YEDEK, ad)
    if os.path.exists(y):
        shutil.copy2(y, tam_yol(hedef))


def sinav_kosar() -> bool:
    """Sınav TEMİZ mi (0 kaldı)? True = temiz, False = kusur yakalandı."""
    # `__pycache__` temizlenir: enjekte edilen kaynak yerine önbellekteki
    # eski bytecode yüklenirse ölçüm yalan söyler.
    for kok, dizinler, _ in os.walk(KOK):
        for dz in list(dizinler):
            if dz == "__pycache__":
                shutil.rmtree(os.path.join(kok, dz), ignore_errors=True)
    shutil.rmtree("/home/ubuntu/merkez_calisma/__pycache__",
                  ignore_errors=True)
    s = subprocess.run([sys.executable, SINAV], capture_output=True,
                       text=True, cwd=KOK, timeout=300)
    return s.returncode == 0


def main() -> int:
    print("Temel ölçüm: sınav kusursuz kaynakta temiz mi?")
    if not sinav_kosar():
        print("HATA: sınav temiz kaynakta bile kalıyor. Kontrol deneyi "
              "anlamsız — önce sınavı geçir.")
        return 2
    print("  Temiz. %d enjeksiyon deneniyor.\n" % len(ENJEKSIYONLAR))

    yakalandi, kacti = 0, []
    for etiket, dosya, bul, degistir in ENJEKSIYONLAR:
        yol = tam_yol(dosya)
        yedekle(dosya)
        with open(yol, "r", encoding="utf-8") as f:
            ham = f.read()
        if bul not in ham:
            kacti.append("%s -> ENJEKSİYON UYGULANAMADI (desen yok: %.60s)"
                         % (etiket, bul.replace("\n", "\\n")))
            geri_yukle(dosya)
            continue
        with open(yol, "w", encoding="utf-8") as f:
            f.write(ham.replace(bul, degistir, 1))
        try:
            temiz = sinav_kosar()
        finally:
            geri_yukle(dosya)
        if temiz:
            kacti.append(etiket)
            print("  KAÇTI    %s" % etiket)
        else:
            yakalandi += 1
            print("  yakaland %s" % etiket)

    print()
    print("=" * 66)
    print("KONTROL DENEYİ: %d/%d yakalandı" % (yakalandi, len(ENJEKSIYONLAR)))
    if kacti:
        print("-" * 66)
        for k in kacti:
            print("  KAÇAN: %s" % k)
        print("-" * 66)
        print("Kaçan her enjeksiyon sınavda bir kör noktadır.")
    print("=" * 66)

    # Son güvenlik: her şey geri yüklendi mi?
    if not sinav_kosar():
        print("UYARI: geri yükleme sonrası sınav kalıyor — kaynak bozuk "
              "kalmış olabilir. .kontrol_yedek/ dizinini denetleyin.")
        return 2
    print("Geri yükleme doğrulandı: sınav yine temiz.")
    return 0 if not kacti else 1


if __name__ == "__main__":
    sys.exit(main())
