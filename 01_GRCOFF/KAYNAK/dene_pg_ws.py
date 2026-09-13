#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.4.51 — PG sihirbazi UCTAN UCA WS olcumu.

Neden bu olcum: sihirbazin arka ucu (`sunucu.py::_pg_sihirbaz`) ile
arayuzu (`js/pg_sihirbaz.js`) AYRI yazildi. Alan adlari uyusmazsa
sihirbaz sessizce bos ekran gosterir. Bu betik GERCEK WS baglantisi
kurup her komutun DONEN ALANLARINI olcer.

Kosum: sunucu ayakta olmali (python3 main.py).
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "goktungu"))

WS = "ws://127.0.0.1:8765"
PG = {"sunucu": "127.0.0.1", "port": 5432, "veritabani": "goktungu",
      "kullanici": "goktungu", "sifre": "goktungu2451"}

gecti = 0
kaldi = 0


def olc(ad, kosul, ek=""):
    global gecti, kaldi
    if kosul:
        gecti += 1
        print(f"  [GECTI] {ad}" + (f" — {ek}" if ek else ""))
    else:
        kaldi += 1
        print(f"  [KALDI] {ad}" + (f" — {ek}" if ek else ""))


async def bekle(ws, tip, zaman=60.0, topla=False):
    """Belirli tipte mesaj gelene kadar bekler.

    `topla=True` ise yol boyunca gelen `pg_ilerleme` mesajlarini da
    listeler (ilerleme cubugu gercekten hareket ediyor mu olcumu).
    """
    ilerlemeler = []
    son = asyncio.get_event_loop().time() + zaman
    while asyncio.get_event_loop().time() < son:
        kalan = son - asyncio.get_event_loop().time()
        try:
            ham = await asyncio.wait_for(ws.recv(), timeout=kalan)
        except asyncio.TimeoutError:
            break
        try:
            m = json.loads(ham)
        except Exception:
            continue
        if not isinstance(m, dict):
            continue
        if topla and m.get("tip") == "pg_ilerleme":
            ilerlemeler.append(m)
        if m.get("tip") == tip:
            return (m, ilerlemeler) if topla else m
    return (None, ilerlemeler) if topla else None


async def ana():
    import websockets

    print("\n=== 1) pg_durum — ILK KURULUM (yapilandirma yok) ===")
    async with websockets.connect(WS, max_size=None) as ws:
        await ws.send(json.dumps({"tip": "pg_durum"}))
        d = await bekle(ws, "pg_durum", 15)
        olc("pg_durum yaniti geldi", d is not None)
        if not d:
            return
        olc("yapilandirildi alani var", "yapilandirildi" in d,
            str(d.get("yapilandirildi")))
        olc("surucu_var True (psycopg2 kurulu)", d.get("surucu_var") is True)
        olc("yapilandirildi False (pg.json yok)",
            d.get("yapilandirildi") is False)

        print("\n=== 2) pg_dene — DOGRU bilgiler ===")
        await ws.send(json.dumps(dict(tip="pg_dene", **PG)))
        s = await bekle(ws, "pg_sonuc", 20)
        olc("pg_sonuc geldi", s is not None)
        if s:
            olc("basarili True", s.get("basarili") is True, s.get("hata", ""))
            olc("surum metni geldi", bool(s.get("surum")),
                str(s.get("surum"))[:40])
            olc("tablo_sayisi alani var (arayuz okur)",
                "tablo_sayisi" in s, str(s.get("tablo_sayisi")))
            olc("citext ust duzey alani var (arayuz okur)",
                "citext" in s, str(s.get("citext")))
            olc("veritabani_var True", s.get("veritabani_var") is True)
            y = s.get("yetki") or {}
            olc("yetki.tablo_olustur True", y.get("tablo_olustur") is True)
            olc("yetki sozlugu dolu", bool(y), str(y))

        print("\n=== 3) pg_dene — YANLIS sifre (hata sadelestirme) ===")
        yanlis = dict(PG)
        yanlis["sifre"] = "kesinlikle_yanlis_sifre"
        await ws.send(json.dumps(dict(tip="pg_dene", **yanlis)))
        s2 = await bekle(ws, "pg_sonuc", 20)
        olc("basarisiz yanit geldi", s2 is not None and
            s2.get("basarili") is False)
        if s2:
            h = (s2.get("hata") or "").lower()
            olc("hata SADELESTIRILMIS (yigin izi degil)",
                "traceback" not in h and len(s2.get("hata", "")) < 200,
                s2.get("hata", "")[:80])
            olc("hata sifreden bahsediyor", "sifre" in h or "parola" in h,
                s2.get("hata", "")[:60])

        print("\n=== 4) pg_dene — bos alan denetimi ===")
        await ws.send(json.dumps({"tip": "pg_dene", "sunucu": "",
                                  "port": 5432, "veritabani": "",
                                  "kullanici": "", "sifre": ""}))
        s3 = await bekle(ws, "pg_sonuc", 15)
        olc("bos alan reddedildi", s3 is not None and
            s3.get("basarili") is False, (s3 or {}).get("hata", "")[:70])

        print("\n=== 5) pg_dene — gecersiz port ===")
        kotu = dict(PG)
        kotu["port"] = 99999
        await ws.send(json.dumps(dict(tip="pg_dene", **kotu)))
        s4 = await bekle(ws, "pg_sonuc", 15)
        olc("gecersiz port reddedildi", s4 is not None and
            s4.get("basarili") is False, (s4 or {}).get("hata", "")[:70])

        print("\n=== 6) pg_kur — SEMA KURULUMU + ILERLEME AKISI ===")
        await ws.send(json.dumps(dict(tip="pg_kur", **PG)))
        s5, ilerlemeler = await bekle(ws, "pg_sonuc", 180, topla=True)
        olc("pg_kur sonucu geldi", s5 is not None)
        if s5:
            olc("kurulum basarili", s5.get("basarili") is True,
                s5.get("hata", ""))
            olc("sema_surum doldu", (s5.get("sema_surum") or 0) > 0,
                str(s5.get("sema_surum")))
            olc("adimlar listesi geldi", isinstance(s5.get("adimlar"), list),
                str(len(s5.get("adimlar") or [])))
        olc("ILERLEME mesajlari geldi (progressbar)",
            len(ilerlemeler) >= 3, f"{len(ilerlemeler)} ileti")
        if ilerlemeler:
            yuzdeler = [i.get("yuzde") for i in ilerlemeler]
            olc("yuzde ARTIYOR (donmuyor)",
                yuzdeler == sorted(yuzdeler), str(yuzdeler[:8]))
            olc("son yuzde 100", yuzdeler[-1] == 100, str(yuzdeler[-1]))
            olc("her ilerlemede ileti metni var",
                all(i.get("ileti") for i in ilerlemeler),
                ilerlemeler[0].get("ileti", "")[:40])

        print("\n=== 7) pg_durum — KURULUM SONRASI ===")
        await ws.send(json.dumps({"tip": "pg_durum"}))
        d2 = await bekle(ws, "pg_durum", 20)
        olc("pg_durum geldi", d2 is not None)
        if d2:
            olc("yapilandirildi True", d2.get("yapilandirildi") is True)
            olc("erisim True", d2.get("erisim") is True,
                d2.get("hata", ""))
            olc("goc_gerekli False (sema guncel)",
                d2.get("goc_gerekli") is False)
            olc("sema_surum = hedef_surum",
                d2.get("sema_surum") == d2.get("hedef_surum"),
                f"{d2.get('sema_surum')} / {d2.get('hedef_surum')}")
            olc("sunucu/veritabani/kullanici doner",
                d2.get("sunucu") == PG["sunucu"] and
                d2.get("veritabani") == PG["veritabani"] and
                d2.get("kullanici") == PG["kullanici"],
                f"{d2.get('sunucu')}/{d2.get('veritabani')}/"
                f"{d2.get('kullanici')}")
            olc("SIFRE GONDERILMIYOR",
                "sifre" not in d2 and "password" not in d2)

        print("\n=== 8) KAPI DENETIMI — giris yapmadan pg_kur ===")
        # Yapilandirma artik VAR; giris yapmamis istemci degistirmemeli.
        await ws.send(json.dumps(dict(tip="pg_kur", **PG)))
        s6 = await bekle(ws, "pg_sonuc", 20)
        olc("yetkisiz pg_kur REDDEDILDI", s6 is not None and
            s6.get("basarili") is False, (s6 or {}).get("hata", "")[:70])

        print("\n=== 9) pg_goc — sema guncel (idempotent) ===")
        await ws.send(json.dumps({"tip": "pg_goc"}))
        s7 = await bekle(ws, "pg_sonuc", 30)
        olc("pg_goc yaniti geldi", s7 is not None)
        # Yapilandirma var + giris yok -> reddedilmeli
        olc("yetkisiz pg_goc REDDEDILDI", s7 is not None and
            s7.get("basarili") is False, (s7 or {}).get("hata", "")[:70])

    print("\n=== 10) GOC SIHIRBAZI — sema geriye alinip olculur ===")
    # Kullanici istegi: "daha once kurulum yapildiysa, tablolarda
    # guncelleme varsa sihirbaz acilsin". Bunu olcmek icin defterden
    # bir adim silinir; pg_durum goc_gerekli=True demeli.
    from goktungu import pg as _pg
    from goktungu import veritabani as _vt
    from goktungu import goc as _goc
    _pg.dosyadan_yukle()
    _vt.kip_ayarla("postgresql")
    con = _vt.baglanti()
    im = con.cursor()
    im.execute("DELETE FROM sema_goc_defteri WHERE adim=?", ("json_goc",))
    con.commit()
    olc("defterden bir adim silindi",
        not _goc.adim_uygulandi_mi("json_goc"))
    _pg.tum_baglantilari_kapat()

    async with websockets.connect(WS, max_size=None) as ws:
        await ws.send(json.dumps({"tip": "pg_durum"}))
        d3 = await bekle(ws, "pg_durum", 20)
        olc("goc_gerekli True (sihirbaz acilmali)",
            d3 is not None and d3.get("goc_gerekli") is True,
            str((d3 or {}).get("bekleyen")))
        if d3:
            bek = d3.get("bekleyen") or []
            olc("bekleyen adim listesi doldu", len(bek) >= 1, str(bek))
            olc("bekleyen adimda aciklama var (arayuz gosterir)",
                bool(bek and bek[0].get("aciklama")),
                (bek[0].get("aciklama") if bek else ""))

    # Semayi geri onar (sonraki olcumler bozulmasin)
    _pg.dosyadan_yukle()
    _vt.kip_ayarla("postgresql")
    s = _goc.GocMotoru().calistir()
    olc("goc geri uygulandi (onarim)", s.get("tamam") is True,
        s.get("hata", ""))
    _pg.tum_baglantilari_kapat()

    print(f"\n{'=' * 56}")
    print(f"SONUC: {gecti} gecti / {kaldi} kaldi")
    print("=" * 56)
    return 0 if kaldi == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(ana()) or 0)
