#!/usr/bin/env python3
"""KURULU pakete GERCEK lisans yerlestirip Merkez Uygulama kipini olcer.

Kosum: sudo /opt/goktungu/merkez/.venv/bin/python <bu dosya>
"""
import json
import os
import sys

sys.path.insert(0, "/opt/goktungu/merkez/assets/python")
os.environ.setdefault("GOKTUNGU_VERI_KOKU", "/var/lib/goktungu-merkez")
from goktungu import lisans as L  # noqa: E402

GOVDE = {"surum": 1, "firma_id": 1,
         "firma_unvan": "VEILOX Savunma Teknolojileri A.S.",
         "lisans_uid": "PKTDOGRULAMA01",
         "yetkiler": {"sinirsiz": True, "ai": True,
                      "radar": True, "gccdual": True}}
IMZA = ("WFJ9qDt6hZw8vEoRRigZwQhw22hHBvepaKwrrloEHQnT7uGlV77R+NVAwbU/Y0ZIhGlu"
        "dB9bEhZ8cpuAb7WADg==")

k = []


def olc(ad, kosul, ek=""):
    k.append((ad, bool(kosul)))
    if not kosul and ek:
        print(f"     ayrinti: {ek}")


def main():
    print("=" * 62)
    print(" KURULU PAKET — LISANS YERLESTIRME VE KIP OLCUMU")
    print("=" * 62)

    # DOGRU sozlesme: anahtar "lisans".
    # Ilk denememde "govde" gondermistim; islev dogru davranip reddetti
    # ama ben donus degerini denetlemedigim icin "yazildi" basmistim.
    # Bu yuzden artik donus degeri HER ZAMAN denetleniyor.
    ok, hata = L.lisans_yaz({"lisans": GOVDE, "imza": IMZA})
    print(f"  lisans_yaz -> ok={ok} hata={hata!r}")
    olc("lisans yazildi", ok, hata)

    yol = L.lisans_yolu()
    olc("dosya diskte VAR", os.path.exists(yol), yol)

    y, hata2 = L.lisans_oku()
    olc("lisans okundu ve imzasi DOGRULANDI", bool(y), hata2)
    olc("merkez_uygulama_kipinde() True",
        L.merkez_uygulama_kipinde() is True)

    oz = L.yetki_ozeti()
    print("  --- yetki ozeti ---")
    for a in ("lisansli", "kaynak", "sinirsiz", "ai", "radar",
              "gccdual", "firma_unvan", "lisans_uid"):
        print(f"    {a:12s} = {oz.get(a)!r}")
    olc("lisansli=True", oz.get("lisansli") is True)
    olc("kaynak=yerel_lisans", oz.get("kaynak") == "yerel_lisans")
    olc("radar ACIK", oz.get("radar") is True)
    olc("gccdual ACIK", oz.get("gccdual") is True)
    olc("ai ACIK", oz.get("ai") is True)
    olc("sinirsiz ACIK", oz.get("sinirsiz") is True)
    olc("firma unvani lisanstan geldi",
        oz.get("firma_unvan") == GOVDE["firma_unvan"])

    # --- DISKTE kurcalama reddedilmeli ---
    # Musterinin lisans dosyasini elle duzenleyip yetki yukseltmesi
    # engellenmeli; imza govdeye baglidir.
    with open(yol, encoding="utf-8") as f:
        d = json.load(f)
    saklanan = json.dumps(d)
    d["lisans"]["firma_unvan"] = "KORSAN A.S."
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)

    y2, _ = L.lisans_oku()
    olc("DISKTE kurcalanan lisans REDDEDILDI", y2 is None)
    olc("kurcalanmis lisansta kip False",
        L.merkez_uygulama_kipinde() is False)
    oz2 = L.yetki_ozeti()
    olc("kurcalamada yetkiler KAPALI",
        oz2.get("radar") is False and oz2.get("gccdual") is False
        and oz2.get("sinirsiz") is False)
    olc("kurcalamada gerekce bildiriliyor", bool(oz2.get("hata")),
        repr(oz2.get("hata"))[:70])

    # Gecerli lisansi geri koy (kurulum kullanilabilir kalsin)
    with open(yol, "w", encoding="utf-8") as f:
        f.write(saklanan)
    y3, _ = L.lisans_oku()
    olc("gecerli lisans geri yuklendi", bool(y3))

    print("-" * 62)
    kaldi = [a for a, s in k if not s]
    for a, s in k:
        print(f"  [{'GECTI' if s else 'KALDI'}] {a}")
    print(f" SONUC: {len(k) - len(kaldi)} gecti / {len(kaldi)} kaldi")
    print("=" * 62)
    sys.exit(1 if kaldi else 0)


if __name__ == "__main__":
    main()
