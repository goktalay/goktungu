#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""SINAV — KOPRU `servisler` LISTESI MERKEZDE COKMEYE YOL ACMAZ (v2.4.63).

## OLCULEN KULLANICI BILDIRIMI (birebir)

    "radar baglan dedigimde
     11:53:27 [WS] Komut hatasi (radar_baglan): 'list' object has no
     attribute 'get'
     hatasi veriyor. su an radar calisiyor ve kopru bilgisayarindan ping
     atabiliyorum"

Yani radar GERCEKTEN ayakta ve saha makinesinden erisilebilir; kusur
merkez yazilimdadir.

## KOK NEDEN

Kopru `servis_durum` yanitinda `servisler` alanini **LISTE** olarak
uretir:

    kopru/servisler.py:544  ->  [self.servisler[a].durum() for a in ...]
    kopru/servisler.py:239  ->  her ogede "ad" alani var

Merkez ise ayni alani **SOZLUK** sanip `servisler.get(servis)` cagiriyordu
(`sunucu.py` iki ayri yerde). Liste uzerinde `.get` bulunmadigi icin
komut isleyici cokuyor, operator radara HIC baglanamiyordu.

## BU SINAV NEDEN GEREKLI

Bu kusur, kaynak okumasiyla kolayca gozden kacar: iki taraf da kendi
icinde tutarlidir, uyusmazlik yalnizca ARAYUZDE (yanit sozlesmesinde)
ortaya cikar. Ayrica hata ANINDA gorunmez — servis secimi basarili olana
kadar akis o satira ulasmaz. Bu yuzden sinav, koprunun GERCEK yanit
bicimini uretir ve merkezi onunla besler.

Bicim GERCEK kaynaktan aliniyor: `kopru/servisler.py` icindeki alan
kumesi taklit edilir (ad/baslik/calisiyor/pid/olcumler...). Uydurma bir
bicimle olcmek, sinavin gecmesini ama sahanin cokmesini surdururdu.

## KAPSAM: BES SERVISIN TAMAMI

Kusur radara OZGU DEGILDI. Radar, GCCDUAL, video, AI ve dron secimleri
ayni `_kopru_servis_sec` yardimcisini kullanir; dolayisiyla hepsi ayni
cokmeyi yasiyordu. Sinav bes servisi ayri ayri olcer.
"""

import asyncio
import json
import os
import sys
import threading

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


def kopru_yaniti(calisan=("radar",)):
    """Koprunun GERCEK `servis_durum` yanitini uretir (LISTE bicimi).

    Alan kumesi `kopru/servisler.py:237-254` ile ayni tutulur. Eksik alan
    birakmak, merkezin var saydigi bir alani sinavda hic gormemesine ve
    kusurun sahada surmesine yol acar.
    """
    tum = ("dron", "ai", "video", "gcsdual", "radar")
    liste = []
    for ad in tum:
        liste.append({
            "ad": ad,
            "baslik": ad.upper(),
            "aciklama": "",
            "calisiyor": ad in calisan,
            "pid": 4242 if ad in calisan else None,
            "baslama_ts": 1.0 if ad in calisan else None,
            "bitis_ts": None,
            "cikis_kodu": None,
            "son_hata": "",
            "konsol_satir": 0,
            "olcumler": {},
            "surum": "2.1.0",
        })
    return {"servisler": liste, "tamam": True}


def sunucu_kur():
    from goktungu import sunucu as S
    nesne = S.WSSunucusu.__new__(S.WSSunucusu)
    nesne._ws_firma = {}
    nesne._ws_kullanici = {}
    nesne._ws_pilot = {}
    nesne.radar = None
    nesne.istasyon2 = None
    nesne.manuel_kontrol = None
    nesne.baglantilar = None
    nesne.istemciler = set()
    nesne.kilit = threading.Lock()
    nesne.pilot = None
    nesne.konsol = lambda *a, **k: None
    return S, nesne


def main():
    print("=" * 70)
    print("SINAV — KOPRU SERVIS LISTESI MERKEZDE COKMEYE YOL ACMAZ")
    print("=" * 70)

    S, srv = sunucu_kur()

    # -----------------------------------------------------------------
    print("\n[1] `_servis_kaydi` yardimcisi HER IKI bicimi tasir")
    # -----------------------------------------------------------------
    olc("yardimci var", hasattr(srv, "_servis_kaydi"))

    liste_yanit = kopru_yaniti(calisan=("radar", "video"))
    k = srv._servis_kaydi(liste_yanit, "radar")
    olc("LISTE bicimi: radar kaydi bulundu", isinstance(k, dict) and bool(k), k)
    olc("LISTE bicimi: calisiyor dogru okundu", k.get("calisiyor") is True, k)
    olc("LISTE bicimi: dogru servis secildi", k.get("ad") == "radar", k)

    k2 = srv._servis_kaydi(liste_yanit, "dron")
    olc("LISTE bicimi: calismayan servis calisiyor=False",
        isinstance(k2, dict) and k2.get("calisiyor") is False, k2)

    # Sozluk bicimi de tasinmali (surum uyusmazligi dayanikliligi).
    sozluk_yanit = {"servisler": {"radar": {"ad": "radar",
                                           "calisiyor": True}}}
    k3 = srv._servis_kaydi(sozluk_yanit, "radar")
    olc("SOZLUK bicimi: radar kaydi bulundu",
        isinstance(k3, dict) and k3.get("calisiyor") is True, k3)

    # Bozuk girdiler COKMEMELI, bos sozluk donmeli.
    for etiket, girdi in (
            ("None", None),
            ("liste govde", ["radar"]),
            ("servisler None", {"servisler": None}),
            ("servisler dize", {"servisler": "radar"}),
            ("servisler sayi", {"servisler": 5}),
            ("liste icinde dize", {"servisler": ["radar", "video"]}),
            ("liste icinde None", {"servisler": [None, {"ad": "radar",
                                                        "calisiyor": True}]}),
    ):
        try:
            s = srv._servis_kaydi(girdi, "radar")
            cokmedi = True
        except Exception as e:  # pragma: no cover
            s = repr(e)
            cokmedi = False
        olc("bozuk girdi (%s): cokmedi ve sozluk dondu" % etiket,
            cokmedi and isinstance(s, dict), s)

    # "liste icinde None" durumunda radar kaydi HALA bulunmali: bozuk bir
    # oge, saglam ogeleri dusurmemeli.
    s = srv._servis_kaydi({"servisler": [None, {"ad": "radar",
                                                "calisiyor": True}]}, "radar")
    olc("bozuk oge saglam kaydi dusurmedi", s.get("calisiyor") is True, s)

    olc("bulunmayan servis: bos sozluk",
        srv._servis_kaydi(liste_yanit, "yok_boyle") == {}, None)

    # -----------------------------------------------------------------
    print("\n[2] `_kopru_servis_sec` LISTE bicimiyle DOGRU kopruyu secer")
    # -----------------------------------------------------------------
    srv._ws_firma_id = lambda ws: 7
    srv._kopru_sahibi_mi = lambda oid, fid: (fid == 7 and oid in (11, 22))

    import goktungu.merkez_kimlik as _mk

    _asil_firma_kopruleri = getattr(_mk, "firma_kopruleri", None)
    _asil_kopruye_sor = getattr(_mk, "kopruye_sor", None)

    def sahte_firma_kopruleri(firma_id):
        return [{"ornek_id": 11, "cevrimici": True, "ad": "SAHA-A"},
                {"ornek_id": 22, "cevrimici": True, "ad": "SAHA-B"}]

    # Yalniz 22 numarali makinede radar calisiyor.
    def sahte_kopruye_sor(ornek_id, firma_id, eylem, veri=None,
                          zaman_asimi=5.0):
        if ornek_id == 22:
            return kopru_yaniti(calisan=("radar", "gcsdual", "video",
                                         "ai", "dron")), ""
        return kopru_yaniti(calisan=()), ""

    _mk.firma_kopruleri = sahte_firma_kopruleri
    _mk.kopruye_sor = sahte_kopruye_sor
    try:
        for servis in ("radar", "gcsdual", "video", "ai", "dron"):
            ws = SahteWS()
            try:
                oid, hata = asyncio.run(
                    srv._kopru_servis_sec(ws, servis, None,
                                          servis_adi=servis.upper()))
                cokmedi = True
            except Exception as e:
                oid, hata, cokmedi = None, repr(e), False
            olc("%s: secim cokmedi" % servis, cokmedi, hata)
            olc("%s: dogru kopru secildi (22)" % servis, oid == 22,
                (oid, hata))
            olc("%s: hata metni bos" % servis, not hata, hata)

        # Hicbir makinede calismiyorsa ANLASILIR hata donmeli (cokme
        # DEGIL). Onceki kusurda burada `.get` cokmesi oluyordu.
        def sahte_hicbiri(ornek_id, firma_id, eylem, veri=None,
                          zaman_asimi=5.0):
            return kopru_yaniti(calisan=()), ""

        _mk.kopruye_sor = sahte_hicbiri
        ws = SahteWS()
        try:
            oid, hata = asyncio.run(
                srv._kopru_servis_sec(ws, "radar", None,
                                      servis_adi="Radar Sunucusu"))
            cokmedi = True
        except Exception as e:
            oid, hata, cokmedi = None, repr(e), False
        olc("calisan yok: cokmedi", cokmedi, hata)
        olc("calisan yok: oid None", oid is None, oid)
        olc("calisan yok: hata yol gosteriyor",
            isinstance(hata, str) and "calismiyor" in hata.lower(), hata)

        # Birden fazla makinede calisiyorsa SECIM ZORUNLU (rastgele
        # secim, operatorun A radarini ayarlarken B'yi ayarlamasi olur).
        def sahte_ikisi(ornek_id, firma_id, eylem, veri=None,
                        zaman_asimi=5.0):
            return kopru_yaniti(calisan=("radar",)), ""

        _mk.kopruye_sor = sahte_ikisi
        ws = SahteWS()
        oid, hata = asyncio.run(
            srv._kopru_servis_sec(ws, "radar", None,
                                 servis_adi="Radar Sunucusu"))
        olc("iki aday: secim zorunlu kilindi", oid is None, oid)
        olc("iki aday: hata makine adlarini yaziyor",
            isinstance(hata, str) and "SAHA-A" in hata, hata)
    finally:
        if _asil_firma_kopruleri is not None:
            _mk.firma_kopruleri = _asil_firma_kopruleri
        if _asil_kopruye_sor is not None:
            _mk.kopruye_sor = _asil_kopruye_sor

    # -----------------------------------------------------------------
    print("\n[3] UCTAN UCA: radar_baglan artik COKMEZ, kopruye ULASIR")
    # -----------------------------------------------------------------
    kayit = []
    uyarilar = []

    async def sahte_kopruye_sor_async(ornek_id, websocket, eylem, veri=None,
                                      zaman_asimi=12.0):
        kayit.append((ornek_id, eylem, dict(veri or {})))
        return ({"tamam": True}, "")

    async def sahte_uyari(websocket, kaynak, mesaj, seviye="uyari"):
        uyarilar.append((str(kaynak), str(mesaj), seviye))

    srv._kopruye_sor_async = sahte_kopruye_sor_async
    srv._uyari_gonder = sahte_uyari
    srv._merkez_kipinde = lambda: True

    _mk.firma_kopruleri = sahte_firma_kopruleri
    _mk.kopruye_sor = sahte_kopruye_sor
    try:
        # Kopru ACIKCA bildirilmemis: secim LISTE taramasindan gecer.
        # Kullanicinin yasadigi yol tam olarak budur.
        ws = SahteWS()
        kayit.clear()
        uyarilar.clear()
        try:
            asyncio.run(srv._komut_isle(ws, {"tip": "radar_baglan",
                                             "ip": "192.168.8.186",
                                             "port": 5001}))
            cokmedi = True
            hata_metni = ""
        except Exception as e:
            cokmedi = False
            hata_metni = repr(e)
        olc("radar_baglan cokmedi ('list' object has no attribute 'get' YOK)",
            cokmedi, hata_metni)
        olc("kopruye tam 1 komut gitti", len(kayit) == 1, kayit)
        if kayit:
            oid, eylem, veri = kayit[0]
            olc("dogru kopruye gitti (22)", oid == 22, oid)
            olc("eylem radar_baglan", eylem == "radar_baglan", eylem)
            olc("operatorun girdigi IP degismeden gitti",
                veri.get("ip") == "192.168.8.186", veri)
            olc("port operatorun verdigi", int(veri.get("port") or 0) == 5001,
                veri)
        olc("cokme uyarisi uretilmedi",
            not [u for u in uyarilar
                 if "attribute" in u[1] or "list" in u[1].lower()], uyarilar)

        # Operatorun girdigi BASKA bir adres de aynen gitmeli.
        ws = SahteWS()
        kayit.clear()
        asyncio.run(srv._komut_isle(ws, {"tip": "radar_baglan",
                                         "ip": "10.20.30.40",
                                         "port": 5001}))
        olc("operator adresi aynen iletildi",
            len(kayit) == 1 and kayit[0][2].get("ip") == "10.20.30.40", kayit)
    finally:
        if _asil_firma_kopruleri is not None:
            _mk.firma_kopruleri = _asil_firma_kopruleri
        if _asil_kopruye_sor is not None:
            _mk.kopruye_sor = _asil_kopruye_sor

    # -----------------------------------------------------------------
    print("\n[4] KAYNAKTA sozluk varsayimi KALMADI")
    # -----------------------------------------------------------------
    yol = os.path.join(_KOK, "goktungu", "sunucu.py")
    kaynak = open(yol, encoding="utf-8").read()

    # Tarama AST uzerinden yapilir. Duz metin aramasi, bu kusuru ANLATAN
    # aciklama satirlarini da kusur sayar (yanlis pozitif) ve sinavi
    # guvenilmez kilar. Olculmesi gereken sey CALISAN koddur.
    import ast

    agac = ast.parse(kaynak)
    docstringler = set()
    for d in ast.walk(agac):
        if isinstance(d, (ast.Module, ast.ClassDef, ast.FunctionDef,
                          ast.AsyncFunctionDef)):
            ds = ast.get_docstring(d, clean=False)
            if ds:
                docstringler.add(ds)

    kotu = []
    for d in ast.walk(agac):
        # Aranan kalip: bir `.get(...)` cagrisinin HEDEFI yine bir
        # `.get("servisler")` cagrisi ya da `servisler` adli bir isim.
        if not isinstance(d, ast.Call):
            continue
        f = d.func
        if not isinstance(f, ast.Attribute) or f.attr != "get":
            continue
        hedef = f.value
        # `servisler.get(...)`
        if isinstance(hedef, ast.Name) and hedef.id == "servisler":
            kotu.append((d.lineno, "servisler.get(...)"))
        # `(... .get("servisler") or {}).get(...)`
        icerik = ast.dump(hedef)
        if "'servisler'" in icerik and "attr='get'" in icerik:
            kotu.append((d.lineno, 'get("servisler").get(...)'))

    olc("calisan kodda `servisler.get(` kalibi yok", not kotu, kotu)
    olc("tarama ayirt edici (docstring bulundu)", len(docstringler) > 5,
        len(docstringler))

    olc("yardimci `_servis_kaydi` kaynakta tanimli",
        "def _servis_kaydi(" in kaynak)
    olc("iki cagri yeri de yardimciyi kullaniyor",
        kaynak.count("self._servis_kaydi(") >= 2,
        kaynak.count("self._servis_kaydi("))

    # -----------------------------------------------------------------
    print("\n" + "=" * 70)
    print("SONUC: %d gecti, %d kaldi" % (_gecti, _kaldi))
    if _notlar:
        print("KALANLAR:")
        for n in _notlar:
            print("  - %s" % n)
    print("=" * 70)
    return 1 if _kaldi else 0


if __name__ == "__main__":
    sys.exit(main())
