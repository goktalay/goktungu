#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""GOKTUNGU Kopru v1.5.7 — depo yayin betigi.

NEDEN BU SURUM: Kopru panelindeki SURUM DEFTERI hicbir madde
gostermiyordu. Arayuz (`web/uygulama.js`) her kaydin `maddeler`
alanini okuyordu; oysa `kopru/surumler.py` icindeki 35 kaydin tamami
`notlar` adini kullaniyor. Alan adlari ayrildigi icin pencerede
yalnizca bos surum/tarih basliklari goruluyordu — kopru cekirdegi ve
BES servisin (dron, radar, video, AI, GroundGCC) tamaminda. Kullanici
"her panelin kendi surum defteri olsun, neyin neden yapildigini yaz"
dedigi icin bu kusur istegin tam merkezindeydi.

Ayrica panele HAKKINDA kimlik basligi eklendi (urun adi, surum, firma
logosu, telif) ve onbellek etiketleri kopru surumune baglandi; aksi
halde kurulu kopruler eski JS/CSS'i onbellekten sunmaya devam eder ve
duzeltme kullaniciya hic gorunmezdi.

Kullanim (MERKEZ SUNUCUDA):
    python3.11 yayinla_157.py
"""

import sys

sys.path.insert(0, "/opt/goktungu/merkez/python")

import mk_depo  # noqa: E402

SURUM = "1.5.7"

NOTLAR = (
    "SURUM DEFTERI ARTIK ICERIGI GOSTERIYOR. Panelde surum numarasina "
    "tikladiginizda gecmis aciliyordu ama maddeler GORUNMUYORDU; "
    "yalnizca bos surum ve tarih basliklari vardi. Nedeni sudur: "
    "arayuz her kaydin 'maddeler' alanini okuyordu, surum defteri ise "
    "tum kayitlarini 'notlar' adiyla tutuyor. Iki ad ayrildigi icin "
    "liste her zaman bos kaliyordu. Bu kusur kopru cekirdeginin yani "
    "sira BES SERVISIN (dron, radar, video, yapay zeka, GroundGCC) "
    "tamamini etkiliyordu; hicbirinin surum gecmisi okunamiyordu. "
    "Arayuz artik iki adi da kabul ediyor. "
    "HAKKINDA BOLUMU EKLENDI. Surum penceresinin ustunde urun adi, "
    "yururlukteki surum, kurumunuzun logosu ve telif bilgisi yer "
    "aliyor; boylece hangi yazilimi ve hangi surumu calistirdiginiz "
    "tek bakista goruluyor. Logo merkezdeki kurum kaydinizdan gelir. "
    "GUNCELLEME ONBELLEK KUSURU GIDERILDI. Panelin JS ve CSS "
    "dosyalarinin onbellek etiketleri sabit birer sayidaydi (v=2, "
    "v=3). Bu yuzden koprunuz guncellense bile tarayici eski arayuz "
    "dosyalarini onbellekten sunmaya devam ediyor, yeni ozellikler "
    "gorunmuyordu. Etiketler artik kopru surumune bagli; her "
    "guncellemede arayuz kendiliginden tazeleniyor. "
    "MERKEZ TARAFINDA BU SURUMLE BIRLIKTE GELENLER (GCS v2.4.66): "
    "merkezde tanimladiginiz sifre artik Merkez Uygulama'da da "
    "gecerli (uygulama merkez sifre bicimini taniyor ve kurulum "
    "sihirbazinda kullanici esitleme adimi var); Merkez Uygulama "
    "icindeki kurumsal panel baglantisi calisiyor; kurumsal panele "
    "KOPRU YAZILIMI bolumu eklendi ve kopru kurulum paketleri "
    "oradan indiriliyor. "
    "INDIRME KURALI DEGISMEDI: kurulum paketleri tanitim sitesinden "
    "dogrudan verilmez; yalnizca kurumsal panelden oturum acarak "
    "indirilir. "
    "Windows: GOKTUNGU-Kopru-Setup.exe sihirbazi, Python 3.11 gomulu, "
    "C:\\Program Files\\Goktungu\\Kopru altina kurulur, services.msc'de "
    "gorunen gercek Windows servisi. Ubuntu: goktungu-kopru.deb, systemd "
    "sistem servisi. Yukseltme yerinde yapilir: servis durdurulur, "
    "dosyalar guncellenir, servis baslatilir; ayarlar ve merkez kaydi "
    "korunur."
)

HEDEFLER = [
    ("windows", f"/tmp/GOKTUNGU-Kopru-Setup-{SURUM}.exe"),
    ("linux", f"/tmp/goktungu-kopru_{SURUM}_all.deb"),
]


def main() -> int:
    basarili = 0
    for platform, yol in HEDEFLER:
        print(f"\n== {platform} ==")
        print(f"  kaynak: {yol}")
        try:
            sonuc = mk_depo.paket_ekle(
                "kopru",
                SURUM,
                yol,
                platform=platform,
                kanal="kararli",
                paket_tur="tam",
                notlar=NOTLAR,
            )
        except Exception as hata:  # noqa: BLE001
            print(f"  [HATA] {type(hata).__name__}: {hata}")
            continue
        print(f"  [OK] eklendi: {sonuc.get('dosya_ad')}")
        print(f"       boyut  : {sonuc.get('dosya_boyut'):,} bayt")
        sha = sonuc.get("sha256") or ""
        print(f"       sha256 : {sha[:20]}...")
        imza = sonuc.get("imza")
        print(f"       imza   : {'VAR (Ed25519)' if imza else 'YOK'}")
        basarili += 1

    print("\n== DOGRULAMA ==")
    for platform, _ in HEDEFLER:
        son = mk_depo.son_surum("kopru", platform=platform, paket_tur="tam")
        if son:
            print(f"  {platform:8s} son surum: {son.get('surum')} "
                  f"({son.get('dosya_ad')})")
        else:
            print(f"  {platform:8s} [KALDI] son surum okunamadi")

    # Platform belirtmeyen istemciler icin de 1.5.7 gorunmeli:
    # `son_surum` 'ortak' istendiginde platforma ozel kayitlari da
    # kapsayacak sekilde duzeltilmisti (v2.4.66). Onu da dogrula.
    ortak = mk_depo.son_surum("kopru", platform="ortak", paket_tur="tam")
    print(f"  {'ortak':8s} son surum: "
          f"{ortak.get('surum') if ortak else '[KALDI] okunamadi'}")

    return 0 if basarili == len(HEDEFLER) else 1


if __name__ == "__main__":
    sys.exit(main())
