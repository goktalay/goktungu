#!/usr/bin/env python3
"""KONTROL DENEYI — `sinav_lisans_yetenek.py` gercekten kusur yakaliyor mu?

YONTEM
  Kaynaga tek tek KASITLI kusur enjekte edilir, sinav kosulur, dosya
  geri alinir. Sinav o kusuru yakalamazsa olcum KOR demektir.

  Her enjeksiyonun `bekle` alani, sinavin HANGI olcumunun kalmasi
  gerektigini soyler. Bu olmadan sinav baska bir nedenle kalir ve
  enjeksiyon test edilmemis oldugu halde "yakalandi" sayilir — onceki
  fazda tam olarak bu oldu (`__pycache__` yan etkisi 29 enjeksiyonu
  sahte gecirdi).

KOSUM  python3.11 kontrol_lisans_yetenek.py
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

KOK = os.path.dirname(os.path.abspath(__file__))
SINAV = os.path.join(KOK, "sinav_lisans_yetenek.py")

# (ad, dosya, bul, koy, beklenen_kalan_olcum_parcasi)
ENJEKSIYONLAR = [
    # --- goktungu/ayarlar.py ---
    ("lisans ozeti yayini kaldirildi", "goktungu/ayarlar.py",
     'a["lisans"] = self._lisans_ozeti()',
     '# a["lisans"] = self._lisans_ozeti()',
     "yayin() lisans alanini dolduruyor"),

    # NOT: gercek kod `o = _lis.yetki_ozeti()` (atama), `return ...` degil.
    ("ozet yetki_ozeti yerine sabit doner", "goktungu/ayarlar.py",
     "o = _lis.yetki_ozeti()",
     "o = {}",
     "ozet lisans modulunden geliyor"),

    # --- js/program_ayar.js ---
    ("lisanssiz kurulumda sinir UYGULANIR (regresyon)",
     "js/program_ayar.js",
     "if (!_lisansOzet || !_lisansOzet.lisansli) return true;",
     "if (!_lisansOzet || !_lisansOzet.lisansli) return false;",
     "lisanssiz kurulumda ust sinir UYGULANMIYOR"),

    ("radarYetenekVar ust sinirdan koparildi", "js/program_ayar.js",
     'return donanim && lisansUstSinir("radar");',
     "return donanim;",
     "radarYetenekVar ust sinira bagli"),

    ("radarYetenekVar donanim kosulunu dusurdu", "js/program_ayar.js",
     'return donanim && lisansUstSinir("radar");',
     'return lisansUstSinir("radar");',
     "radarYetenekVar donanim kosulunu KORUYOR"),

    ("ozet gelince radar menusu yenilenmiyor", "js/program_ayar.js",
     "  radarMenuGorunumGuncelle();\n  radarModuUygula(radarYetenekVar());",
     "  radarModuUygula(radarYetenekVar());",
     "ozet gelince radar menusu yenileniyor"),

    # NOT: ayni cagri iki yerde var (satir ~170 ve ~233). Enjeksiyon
    # `lisansOzetiSunucudan` blogundaki (ikinci) cagriyi hedeflemeli;
    # ilkini silmek sinavi kaldirmaz cunku olcum o blogu okur.
    ("ozet gelince GCCDUAL menusu yenilenmiyor", "js/program_ayar.js",
     "  radarMenuGorunumGuncelle();\n  radarModuUygula(radarYetenekVar());\n"
     '  if (typeof window.istasyon2MenuGorunumGuncelle === "function")\n'
     "    window.istasyon2MenuGorunumGuncelle();",
     "  radarMenuGorunumGuncelle();\n  radarModuUygula(radarYetenekVar());",
     "ozet gelince GCCDUAL menusu yenileniyor"),

    ("lisansUstSinir alan degerini yok sayar", "js/program_ayar.js",
     "return !!_lisansOzet[alan];",
     "return true;",
     "lisansli kurumda alan degeri donuyor"),

    # --- js/istasyon2.js ---
    ("GCCDUAL ust sinirdan koparildi", "js/istasyon2.js",
     'lisansUstSinir("gccdual")',
     "true",
     "GCCDUAL gorunurlugu ust sinira bagli"),

    # --- goktungu/sunucu.py ---
    ("radar komutlari tablodan cikarildi", "goktungu/sunucu.py",
     '"radar_baglan": "radar",',
     "",
     "tabloda radar_baglan"),

    ("gccdual komutlari tablodan cikarildi", "goktungu/sunucu.py",
     '"istasyon2_baglan": "gccdual",',
     "",
     "tabloda istasyon2_baglan"),

    ("tabloya hayali komut eklendi", "goktungu/sunucu.py",
     '"radar_baglan": "radar",',
     '"radar_baglan": "radar",\n        "radar_hayali_komut": "radar",',
     "tabloda hayali komut YOK"),

    # Bu iki enjeksiyon metin olcumunden KACIYORDU; artik davranis
    # olcumu (5b) yakaliyor.
    ("sunucu lisans denetimi etkisiz (short-circuit)", "goktungu/sunucu.py",
     "if not await self._lisans_izni_var(websocket, komut):",
     "if False and not await self._lisans_izni_var(websocket, komut):",
     "denetim cagrisi kosulsuz"),

    ("lisanssiz kurulumda sunucu komutu reddeder (regresyon)",
     "goktungu/sunucu.py",
     "        ozet = self._lisans_ozeti_al()",
     "        ozet = {'lisansli': True, 'radar': False, 'gccdual': False}",
     "radar_baglan GECIYOR"),

    ("lisansli+acik modul yine reddediliyor", "goktungu/sunucu.py",
     "        if ozet.get(alan):\n            return True",
     "        if False:\n            return True",
     "radar acik -> radar_baglan GECIYOR"),

    # NOT: onceki bicim `_sahte_uyari` cagiriyordu; AttributeError
    # firlatip BASKA olcumu kaldiriyordu (SAHTE sonuc). Gercekci kusur:
    # cagri kosula baglanip sessizce atlanir — operator hicbir sey
    # gormez, tam olarak yasaklanan sessiz basarisizlik.
    ("ret uyarisi gonderilmiyor (sessiz basarisizlik)", "goktungu/sunucu.py",
     "        await self._uyari_gonder(\n            websocket, alan,",
     "        if False:\n          await self._uyari_gonder(\n            websocket, alan,",
     "ret uyarisi gonderiliyor"),

    ("ilgisiz komut da denetlenir oldu", "goktungu/sunucu.py",
     "        alan = self.LISANS_KOMUT_ALANI.get(komut)\n"
     "        if not alan:\n            return True",
     "        alan = self.LISANS_KOMUT_ALANI.get(komut) or 'radar'",
     "ilgisiz komut denetimden etkilenmiyor"),

    # --- goktungu/lisans.py ---
    ("kapali devre bozuldu: ag cagrisi eklendi", "goktungu/lisans.py",
     "import base64",
     "import base64\nimport urllib.request",
     "kapali devre: ag cagrisi YOK"),

    ("lisans ozetine imza sizdirildi", "goktungu/ayarlar.py",
     "def _lisans_ozeti(self):",
     'def _lisans_ozeti(self):\n        _sizinti = {"imza": "x"}',
     "lisans ozetinde imza YAYINLANMIYOR"),
]


def sinav_kos():
    """Sinavi kosar; (basarili_mi, cikti) doner."""
    s = subprocess.run([sys.executable, SINAV], cwd=KOK,
                       capture_output=True, text=True, timeout=900)
    return s.returncode == 0, s.stdout + s.stderr


def main():
    print("=" * 70)
    print(" KONTROL DENEYI — sinav_lisans_yetenek.py")
    print("=" * 70)

    # Once temiz durumda sinav GECMELI; gecmezse enjeksiyon olcumu
    # anlamsizlasir.
    temiz, cikti = sinav_kos()
    if not temiz:
        print("  KUSUR: temiz kaynakta sinav KALIYOR — enjeksiyon olcumu")
        print("  anlamsiz. Once sinavi/kaynagi duzelt.")
        print(cikti[-2000:])
        sys.exit(1)
    print("  temiz kaynakta sinav GECIYOR\n")

    yedek = tempfile.mkdtemp(prefix="yetenek_yedek_")
    yakalandi = 0
    kacan = []

    try:
        for i, (ad, dosya, bul, koy, bekle) in enumerate(ENJEKSIYONLAR, 1):
            tam = os.path.join(KOK, dosya)
            yed = os.path.join(yedek, dosya.replace("/", "__"))
            shutil.copy2(tam, yed)

            with open(tam, encoding="utf-8") as f:
                metin = f.read()

            if bul not in metin:
                print(f"  [{i:2d}] {ad}")
                print(f"       ENJEKSIYON UYGULANAMADI — desen yok: "
                      f"{bul[:60]!r}")
                kacan.append((ad, "desen bulunamadi"))
                continue

            with open(tam, "w", encoding="utf-8") as f:
                f.write(metin.replace(bul, koy, 1))

            try:
                basarili, ck = sinav_kos()
                if basarili:
                    print(f"  [{i:2d}] KACTI    {ad}")
                    kacan.append((ad, "sinav gecti"))
                elif bekle and bekle not in ck:
                    # Sinav kaldi ama BASKA bir olcumden; enjeksiyon
                    # test edilmemis sayilir.
                    print(f"  [{i:2d}] SAHTE    {ad}")
                    print(f"       beklenen olcum kalmadi: {bekle!r}")
                    kacan.append((ad, "yanlis olcum kaldi"))
                else:
                    print(f"  [{i:2d}] yakalandi {ad}")
                    yakalandi += 1
            finally:
                shutil.copy2(yed, tam)
    finally:
        shutil.rmtree(yedek, ignore_errors=True)
        # Kaynagin geri alindigini DOGRULA
        son, _ = sinav_kos()
        print(f"\n  kaynak geri alindi, sinav yeniden geciyor: {son}")
        if not son:
            print("  UYARI: kaynak bozuk kalmis olabilir!")

    print("-" * 70)
    print(f" SONUC: {len(ENJEKSIYONLAR)} enjeksiyon, {yakalandi} yakalandi")
    for ad, neden in kacan:
        print(f"   KACAN: {ad}  ({neden})")
    print("=" * 70)
    sys.exit(1 if kacan else 0)


if __name__ == "__main__":
    main()
