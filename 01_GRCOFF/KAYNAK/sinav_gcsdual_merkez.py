#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""KUSUR-GCSDUAL-PORT — MERKEZ TARAFI SINAVI

Kullanici bildirimi:
    "GCS icinde kopru kurulu olan makinede porta baglanmali, sanirim su
     an sunucu da ariyor portu, GCS bilgisayarinda aslinda ttyACM0 var"

Bu sinav MERKEZ tarafini olcer: WS komutlari gercekten kopruye mi
gidiyor, yetki dogrulaniyor mu, LOKAL kurulum yolu bozuldu mu.

YONTEM — kaynak denetimi DEGIL, DAVRANIS olcumu:
  * Gercek `GoktunguSunucu` ornegi kurulur (asgari baglantilarla)
  * `merkez_kimlik.kopruye_sor` ve `firma_kopruleri` YERINE gecirilir
    (monkeypatch); boylece gercek bir kopru makinesi olmadan merkezin
    HANGI makineye ne gonderdigi kaydedilir
  * Gercek `_komut_isle` cagrilir; sahte websocket gonderilen JSON'u
    toplar
  * Lokal kip icin `_merkez_kipinde` False yapilir ve `self.istasyon2`
    sahte nesneyle degistirilir; merkez yolunun lokali BOZMADIGI olculur

Neden bu kadar onemli: kusurun kendisi "komut yanlis makineye gitti"
sinifindandir. Kaynakta `_gcsdual_kopru_cagir` cagrisini gormek yetmez;
cagrinin GERCEKTEN o eylemle, o veriyle ve DOGRU kopru kimligiyle
yapildigi olculmelidir.
"""

import asyncio
import json
import os
import sys

_KOK = os.path.dirname(os.path.abspath(__file__))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

_gecti = 0
_kaldi = 0
_notlar = []


def olc(ad, kosul, ek=None):
    global _gecti, _kaldi
    if kosul:
        _gecti += 1
        print("  OK    %s" % ad)
    else:
        _kaldi += 1
        print("  KALDI %s" % ad)
        if ek is not None:
            print("        -> %r" % (ek,))
        _notlar.append(ad)


# ---------------------------------------------------------------
# Sahte websocket: gonderilen paketleri toplar
# ---------------------------------------------------------------
class SahteWS:
    def __init__(self):
        self.paketler = []

    async def send(self, metin):
        try:
            self.paketler.append(json.loads(metin))
        except Exception:
            self.paketler.append({"_ham": metin})

    def son(self, tip=None):
        for p in reversed(self.paketler):
            if tip is None or p.get("tip") == tip:
                return p
        return None


class SahteIstasyon2:
    """Lokal kurulum yolu icin. Cagrilari kaydeder."""

    def __init__(self):
        self.cagrilar = []

    def baglan(self, port):
        self.cagrilar.append(("baglan", port))
        return True, ""

    def kes(self):
        self.cagrilar.append(("kes", None))

    def led(self, kanal, acik):
        self.cagrilar.append(("led", (kanal, acik)))
        return True, ""

    def ping(self):
        self.cagrilar.append(("ping", None))

    def kalibre_et(self):
        self.cagrilar.append(("kalibre", None))
        return True, ""

    def kalibrasyon_sil(self):
        self.cagrilar.append(("kalibre_sil", None))

    def ayar_yaz(self, k):
        self.cagrilar.append(("ayar_yaz", dict(k)))

    def durum(self):
        return {"bagli": False, "port": "", "yerel": True}


def sunucu_kur():
    """Gercek GoktunguSunucu ornegini kurar (agir bagimliliklar olmadan)."""
    from goktungu import sunucu as S
    nesne = S.WSSunucusu.__new__(S.WSSunucusu)
    # `_komut_isle`nin dokundugu asgari alanlar
    nesne._ws_firma = {}
    nesne._ws_kullanici = {}
    nesne.istasyon2 = None
    nesne.manuel_kontrol = None
    nesne.baglantilar = None
    nesne.istemciler = set()
    # `_izin_var` pilot yoneticisi yoksa TRUE doner (yetki denetimi
    # kapali kurulum). Bu sinavin konusu izin sistemi DEGIL, komutun
    # hangi makineye gittigi; pilot None birakilir.
    nesne.pilot = None
    nesne.konsol = lambda *a, **k: None
    return S, nesne


def main():
    print("=" * 66)
    print("KUSUR-GCSDUAL-PORT — MERKEZ TARAFI SINAVI")
    print("=" * 66)

    S, srv = sunucu_kur()

    # -----------------------------------------------------------
    # Kopru cagrilarini KAYDET. Gercek bir saha makinesi yok; onemli
    # olan merkezin ne gonderdigi.
    # -----------------------------------------------------------
    kayit = []          # (ornek_id, eylem, veri)
    yanitlar = {}       # eylem -> (veri, hata)

    async def sahte_kopruye_sor(ornek_id, websocket, eylem, veri=None,
                                zaman_asimi=12.0):
        kayit.append((ornek_id, eylem, dict(veri or {})))
        return yanitlar.get(eylem, ({"tamam": True}, ""))

    srv._kopruye_sor_async = sahte_kopruye_sor

    # Merkez kipi ACIK
    srv._merkez_kipinde = lambda: True
    srv._ws_firma_id = lambda ws: 7
    srv._kopru_sahibi_mi = lambda oid, fid: (fid == 7 and oid in (11, 22))
    srv._ist2_manuel_dronlar = lambda: []

    # -----------------------------------------------------------
    # 1) ACIK KOPRU SECIMI: pilot makine sectiyse ORAYA gider
    # -----------------------------------------------------------
    print("\n[1] Pilot makine sectiginde komut O makineye gider")
    ws = SahteWS()
    kayit.clear()
    asyncio.run(srv._komut_isle(ws, {
        "tip": "istasyon2_baglan", "port": "/dev/ttyACM0",
        "kopru_ornek_id": 22}))
    olc("baglan komutu kopruye gonderildi", len(kayit) == 1, kayit)
    if kayit:
        oid, eylem, veri = kayit[0]
        olc("hedef makine pilotun sectigi (22)", oid == 22, oid)
        olc("eylem adi gcsdual_baglan", eylem == "gcsdual_baglan", eylem)
        olc("port aynen iletildi", veri.get("port") == "/dev/ttyACM0", veri)
    p = ws.son("istasyon2_sonuc")
    olc("panele basari bildirildi", bool(p and p.get("basari")), p)
    olc("panel yanitinda kopru bayragi var", bool(p and p.get("kopru")), p)

    # -----------------------------------------------------------
    # 2) YETKI: baska firmanin koprusune komut GITMEZ
    # -----------------------------------------------------------
    print("\n[2] Baska firmanin makinesine komut gonderilemez")
    ws = SahteWS()
    kayit.clear()
    asyncio.run(srv._komut_isle(ws, {
        "tip": "istasyon2_baglan", "port": "/dev/ttyACM0",
        "kopru_ornek_id": 99}))     # 99 bu firmaya ait DEGIL
    olc("yetkisiz makineye HIC istek gitmedi", len(kayit) == 0, kayit)
    p = ws.son("istasyon2_sonuc")
    olc("panele basarisizlik bildirildi",
        bool(p) and not p.get("basari"), p)
    olc("hata metni sebebi soyluyor",
        bool(p) and "ait" in str(p.get("sebep", "")).lower(), p)

    # -----------------------------------------------------------
    # 3) TEK ADAY: merkez kendisi bulur, pilot secim yapmak zorunda degil
    # -----------------------------------------------------------
    print("\n[3] Tek uygun makine varsa merkez kendisi secer")
    from goktungu import merkez_kimlik as _mk

    _mk_firma_kopruleri = getattr(_mk, "firma_kopruleri", None)
    _mk_kopruye_sor = getattr(_mk, "kopruye_sor", None)

    def kopru_listesi_kur(liste):
        _mk.firma_kopruleri = lambda firma_id: list(liste)

    def servis_durum_kur(harita):
        # harita: ornek_id -> gcsdual calisiyor mu
        def _sor(ornek_id, firma_id, eylem, zaman_asimi=5.0):
            calisiyor = bool(harita.get(int(ornek_id)))
            return ({"servisler": {"gcsdual": {"calisiyor": calisiyor}}},
                    "")
        _mk.kopruye_sor = _sor

    kopru_listesi_kur([
        {"ornek_id": 11, "ad": "IST2", "cevrimici": True},
        {"ornek_id": 22, "ad": "ANK1", "cevrimici": True},
    ])
    servis_durum_kur({11: True, 22: False})     # yalniz 11'de calisiyor

    ws = SahteWS()
    kayit.clear()
    asyncio.run(srv._komut_isle(ws, {"tip": "istasyon2_portlar"}))
    olc("tek adaya istek gitti", len(kayit) == 1, kayit)
    if kayit:
        olc("dogru makine secildi (11)", kayit[0][0] == 11, kayit[0])
        olc("eylem gcsdual_portlar",
            kayit[0][1] == "gcsdual_portlar", kayit[0])

    # -----------------------------------------------------------
    # 4) IKI ADAY: secim ZORUNLU, rastgele gonderim YOK
    # -----------------------------------------------------------
    print("\n[4] Iki aday varsa rastgele secilmez, secim istenir")
    servis_durum_kur({11: True, 22: True})
    ws = SahteWS()
    kayit.clear()
    asyncio.run(srv._komut_isle(ws, {"tip": "istasyon2_baglan",
                                     "port": "/dev/ttyACM0"}))
    olc("hicbir makineye komut GITMEDI", len(kayit) == 0, kayit)
    p = ws.son("istasyon2_sonuc")
    sebep = str((p or {}).get("sebep", ""))
    olc("panele secim gerektigi bildirildi",
        bool(p) and not p.get("basari") and "se" in sebep.lower(), p)
    olc("hata metninde makine adlari var",
        "IST2" in sebep and "ANK1" in sebep, sebep)

    # -----------------------------------------------------------
    # 5) HIC ADAY YOK: pilota NE YAPACAGI soylenir
    # -----------------------------------------------------------
    print("\n[5] GroundGCC hicbir makinede calismiyorsa acik hata")
    servis_durum_kur({11: False, 22: False})
    ws = SahteWS()
    kayit.clear()
    asyncio.run(srv._komut_isle(ws, {"tip": "istasyon2_durum"}))
    olc("komut gonderilmedi", len(kayit) == 0, kayit)
    p = ws.son("istasyon2_durum")
    olc("durum paketi yine de dondu (panel cizilebilir)", bool(p), p)
    olc("bagli=False", bool(p) and p.get("bagli") is False, p)
    olc("yok bayragi ile panel 'canta yok' cizer",
        bool(p) and p.get("yok") is True, p)
    olc("hata metni GroundGCC baslatmayi soyluyor",
        "GroundGCC" in str((p or {}).get("hata", "")), p)

    # -----------------------------------------------------------
    # 6) CEVRIMICI KOPRU YOK
    # -----------------------------------------------------------
    print("\n[6] Cevrimici saha makinesi yoksa acik hata")
    kopru_listesi_kur([{"ornek_id": 11, "ad": "IST2", "cevrimici": False}])
    ws = SahteWS()
    kayit.clear()
    asyncio.run(srv._komut_isle(ws, {"tip": "istasyon2_durum"}))
    p = ws.son("istasyon2_durum")
    olc("kopru yazilimini baslatma yonlendirmesi var",
        "opru" in str((p or {}).get("hata", "")), p)

    # -----------------------------------------------------------
    # 7) TUM EYLEMLER kopruye gidiyor (hicbiri merkezde kalmadi)
    # -----------------------------------------------------------
    print("\n[7] Alti eylemin TAMAMI kopruye yonlendirilmis")
    kopru_listesi_kur([{"ornek_id": 11, "ad": "IST2", "cevrimici": True}])
    servis_durum_kur({11: True})
    beklenen = {
        "istasyon2_portlar": "gcsdual_portlar",
        "istasyon2_baglan": "gcsdual_baglan",
        "istasyon2_kes": "gcsdual_kes",
        "istasyon2_led": "gcsdual_led",
        "istasyon2_kalibre": "gcsdual_kalibre",
        "istasyon2_durum": "gcsdual_durum",
    }
    for komut, eylem in beklenen.items():
        ws = SahteWS()
        kayit.clear()
        paket = {"tip": komut}
        if komut == "istasyon2_baglan":
            paket["port"] = "/dev/ttyACM0"
        if komut == "istasyon2_led":
            paket.update({"kanal": "P3", "acik": True})
        asyncio.run(srv._komut_isle(ws, paket))
        olc("%s -> %s" % (komut, eylem),
            len(kayit) == 1 and kayit[0][1] == eylem, kayit)

    # -----------------------------------------------------------
    # 8) LED: kanal buyuk harfe cevrilir ve aynen iletilir
    # -----------------------------------------------------------
    print("\n[8] LED kanali normalize edilip iletilir")
    ws = SahteWS()
    kayit.clear()
    asyncio.run(srv._komut_isle(ws, {"tip": "istasyon2_led",
                                     "kanal": "p5", "acik": False}))
    olc("kanal buyuk harf (P5)",
        bool(kayit) and kayit[0][2].get("kanal") == "P5", kayit)
    olc("acik=False iletildi",
        bool(kayit) and kayit[0][2].get("acik") is False, kayit)

    # -----------------------------------------------------------
    # 9) KALIBRASYON SILME ayrimi korunuyor
    # -----------------------------------------------------------
    print("\n[9] Kalibrasyon sil/olc ayrimi")
    ws = SahteWS()
    kayit.clear()
    asyncio.run(srv._komut_isle(ws, {"tip": "istasyon2_kalibre",
                                     "sil": True}))
    olc("sil=True iletildi",
        bool(kayit) and kayit[0][2].get("sil") is True, kayit)
    p = ws.son("istasyon2_sonuc")
    olc("panele islem 'kalibre_sil' bildirildi",
        bool(p) and p.get("islem") == "kalibre_sil", p)

    # -----------------------------------------------------------
    # 10) OTOMATIK BAGLAN anahtari: merkezde ayar dosyasina YAZMAZ,
    #     kopruye baglan/kes olarak gider
    # -----------------------------------------------------------
    print("\n[10] Otomatik baglan anahtari koprude anlam kazanir")
    ws = SahteWS()
    kayit.clear()
    asyncio.run(srv._komut_isle(ws, {"tip": "istasyon2_ayar",
                                     "otomatik": True,
                                     "port": "/dev/ttyACM0"}))
    olc("acma istegi gcsdual_baglan oldu",
        bool(kayit) and kayit[0][1] == "gcsdual_baglan", kayit)
    ws = SahteWS()
    kayit.clear()
    asyncio.run(srv._komut_isle(ws, {"tip": "istasyon2_ayar",
                                     "otomatik": False}))
    olc("kapatma istegi gcsdual_kes oldu",
        bool(kayit) and kayit[0][1] == "gcsdual_kes", kayit)

    # -----------------------------------------------------------
    # 11) KOPRU HATASI panele TASINIR (sessiz basarisizlik yok)
    # -----------------------------------------------------------
    print("\n[11] Koprudeki hata panele aynen tasinir")
    yanitlar["gcsdual_baglan"] = (
        {"tamam": False, "hata": "Port acilamadi: /dev/ttyACM0 mesgul"},
        "")
    ws = SahteWS()
    asyncio.run(srv._komut_isle(ws, {"tip": "istasyon2_baglan",
                                     "port": "/dev/ttyACM0"}))
    p = ws.son("istasyon2_sonuc")
    olc("basari=False", bool(p) and not p.get("basari"), p)
    olc("gercek hata metni panelde",
        "mesgul" in str((p or {}).get("sebep", "")), p)
    yanitlar.clear()

    # -----------------------------------------------------------
    # 12) DURUM paketi: kopru alanlari panele GECIRILIR
    # -----------------------------------------------------------
    print("\n[12] Kopru durum alanlari panele gecirilir")
    yanitlar["gcsdual_durum"] = ({
        "tamam": True, "bagli": True, "port": "/dev/ttyACM0",
        "baud": 115200,
        "durum": {"buttons": {"P1": 1}, "toggles": {"T1": 0},
                  "leds": {"P1": True}},
        "normalize": {"J1_X": 0.0, "J1_Y": 0.0},
        "sayac": {"rx": 42, "tx": 3, "pong": 1, "bozuk": 0},
        "gecikme_ms": 7,
    }, "")
    ws = SahteWS()
    asyncio.run(srv._komut_isle(ws, {"tip": "istasyon2_durum"}))
    p = ws.son("istasyon2_durum") or {}
    olc("bagli=True gecti", p.get("bagli") is True, p)
    olc("port gecti", p.get("port") == "/dev/ttyACM0", p)
    olc("durum sozlugu gecti",
        (p.get("durum") or {}).get("buttons", {}).get("P1") == 1, p)
    olc("normalize eksen adi J1_X (alt cizgili)",
        "J1_X" in (p.get("normalize") or {}), p)
    olc("sayaclar gecti",
        (p.get("sayac") or {}).get("rx") == 42, p)
    olc("gecikme gecti", p.get("gecikme_ms") == 7, p)
    olc("ic alanlar sizmadi (tip/tamam)",
        "tamam" not in p and p.get("tip") == "istasyon2_durum", p)
    olc("manuel_dronlar alani korundu", "manuel_dronlar" in p, p)
    yanitlar.clear()

    # -----------------------------------------------------------
    # 13) LOKAL KURULUM BOZULMADI — en kritik gerileme sinavi
    #     Kullanici sahada lokal kurulumla uçuyor.
    # -----------------------------------------------------------
    print("\n[13] LOKAL kurulumda yerel yol AYNEN korunur")
    srv._merkez_kipinde = lambda: False
    yerel = SahteIstasyon2()
    srv.istasyon2 = yerel
    kayit.clear()

    ws = SahteWS()
    asyncio.run(srv._komut_isle(ws, {"tip": "istasyon2_baglan",
                                     "port": "/dev/ttyUSB0"}))
    olc("lokalde KOPRUYE istek gitmedi", len(kayit) == 0, kayit)
    olc("yerel baglan cagrildi",
        ("baglan", "/dev/ttyUSB0") in yerel.cagrilar, yerel.cagrilar)

    ws = SahteWS()
    asyncio.run(srv._komut_isle(ws, {"tip": "istasyon2_kes"}))
    olc("yerel kes cagrildi",
        ("kes", None) in yerel.cagrilar, yerel.cagrilar)

    ws = SahteWS()
    asyncio.run(srv._komut_isle(ws, {"tip": "istasyon2_led",
                                     "kanal": "P2", "acik": True}))
    olc("yerel led cagrildi",
        ("led", ("P2", True)) in yerel.cagrilar, yerel.cagrilar)

    ws = SahteWS()
    asyncio.run(srv._komut_isle(ws, {"tip": "istasyon2_led",
                                     "kanal": "PING"}))
    olc("yerel PING ayrimi korundu",
        ("ping", None) in yerel.cagrilar, yerel.cagrilar)

    ws = SahteWS()
    asyncio.run(srv._komut_isle(ws, {"tip": "istasyon2_kalibre"}))
    olc("yerel kalibre cagrildi",
        ("kalibre", None) in yerel.cagrilar, yerel.cagrilar)

    ws = SahteWS()
    asyncio.run(srv._komut_isle(ws, {"tip": "istasyon2_ayar",
                                     "otomatik": True}))
    olc("lokalde ayar dosyasina YAZILDI",
        any(c[0] == "ayar_yaz" for c in yerel.cagrilar), yerel.cagrilar)

    ws = SahteWS()
    asyncio.run(srv._komut_isle(ws, {"tip": "istasyon2_portlar"}))
    p = ws.son("istasyon2_portlar")
    olc("lokalde port listesi yerelden geldi",
        bool(p) and not p.get("kopru"), p)
    olc("lokalde KOPRUYE hic istek gitmedi (toplam)",
        len(kayit) == 0, kayit)

    # geri al
    if _mk_firma_kopruleri:
        _mk.firma_kopruleri = _mk_firma_kopruleri
    if _mk_kopruye_sor:
        _mk.kopruye_sor = _mk_kopruye_sor

    print("\n" + "-" * 66)
    print("SONUC: %d gecti / %d kaldi" % (_gecti, _kaldi))
    if _notlar:
        print("Kalanlar:")
        for n in _notlar:
            print("  - %s" % n)
    return 1 if _kaldi else 0


if __name__ == "__main__":
    sys.exit(main())
