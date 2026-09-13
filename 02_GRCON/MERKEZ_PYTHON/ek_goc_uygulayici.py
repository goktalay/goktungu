#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""main.py'ye goc uygulayicisi ekler.

SORUN: `sema_uygula()` yalniz `merkez_sema.sql` dosyasini calistiriyordu.
`goc_sema6.sql` / `goc_sema7.sql` gibi ALTER TABLE goclerini calistiran
hicbir mekanizma yoktu. Bu, kullanicinin "guncellemelerde DB semasi
otomatik migrate edilecek" gereksinimiyle celisiyordu.

COZUM: `goc_sema{N}.sql` dosyalari sayisal sirayla, YALNIZ bir kez,
her biri KENDI isleminde uygulanir.
"""
from __future__ import annotations

import os
import sys

BURASI = os.path.dirname(os.path.abspath(__file__))
HEDEF = os.path.join(BURASI, "main.py")

ESKI = '''def sema_uygula() -> tuple[bool, str]:
    """Şemayı uygular. Betik baştan sona `IF NOT EXISTS` ile yazıldığı
    için birden çok kez çalıştırılması güvenlidir."""
    if not os.path.isfile(SEMA_DOSYA):
        return False, f"Şema dosyası yok: {SEMA_DOSYA}"
    with open(SEMA_DOSYA, "r", encoding="utf-8") as f:
        sql = f.read()
    try:
        with db.baglanti() as con:
            cur = con.cursor()
            cur.execute(sql)
            con.commit()
            cur.close()
        return True, ""
    except Exception as e:
        return False, str(e)
'''

YENI = '''def goc_dosyalari() -> list[tuple[int, str]]:
    """`goc_sema{N}.sql` dosyalarını (hedef sürüm, yol) olarak döndürür.

    Dosya adındaki sayı **hedef** şema sürümüdür: `goc_sema6.sql`
    5'ten 6'ya yükseltir. Sıralama SAYISALDIR; alfabetik sıralama
    `goc_sema10` öğesini `goc_sema6`'dan önce koyardı.
    """
    bulunan: list[tuple[int, str]] = []
    for ad in os.listdir(BURASI):
        e = re.match(r"^goc_sema(\\d+)\\.sql$", ad)
        if e:
            bulunan.append((int(e.group(1)), os.path.join(BURASI, ad)))
    bulunan.sort(key=lambda x: x[0])
    return bulunan


def goc_uygula(mevcut: int) -> tuple[bool, str, int]:
    """`mevcut` sürümünden sonraki tüm göçleri sırayla uygular.

    TASARIM: Her göç KENDİ işleminde çalışır. Hepsi tek işleme
    alınsaydı sondaki bir hata, başarıyla uygulanmış öncekileri de
    geri alacak ve sistem hangi sürümde olduğunu bilemeyecekti. Göç
    dosyalarının kendisi `sema_surum` satırını günceller; böylece
    başarılı bir göç kalıcı olarak işaretlenmiş olur.
    """
    son = mevcut
    for hedef, yol in goc_dosyalari():
        if hedef <= mevcut:
            continue
        with open(yol, "r", encoding="utf-8") as f:
            sql = f.read()
        print(f"[MERKEZ] Goc uygulaniyor: {os.path.basename(yol)} "
              f"({son} -> {hedef})")
        try:
            with db.baglanti() as con:
                cur = con.cursor()
                cur.execute(sql)
                con.commit()
                cur.close()
        except Exception as e:
            return False, f"{os.path.basename(yol)}: {e}", son
        son = sema_surumu() or hedef
    return True, "", son


def sema_uygula() -> tuple[bool, str]:
    """Şemayı ve ardından bekleyen göçleri uygular.

    Taban betik baştan sona `IF NOT EXISTS` ile yazıldığı için birden
    çok kez çalıştırılması güvenlidir. Göçler taban betikten SONRA
    çalışır; çünkü `ALTER TABLE ... ADD COLUMN` için tablonun önce var
    olması gerekir.
    """
    if not os.path.isfile(SEMA_DOSYA):
        return False, f"Şema dosyası yok: {SEMA_DOSYA}"
    with open(SEMA_DOSYA, "r", encoding="utf-8") as f:
        sql = f.read()
    try:
        with db.baglanti() as con:
            cur = con.cursor()
            cur.execute(sql)
            con.commit()
            cur.close()
    except Exception as e:
        return False, str(e)
    tamam, hata, _ = goc_uygula(sema_surumu())
    if not tamam:
        return False, hata
    return True, ""
'''


def main() -> int:
    with open(HEDEF, "r", encoding="utf-8") as f:
        icerik = f.read()
    if "def goc_uygula(" in icerik:
        print("[YAMA] Goc uygulayicisi zaten var; atlandi")
        return 0
    if ESKI not in icerik:
        print("[YAMA] HATA: beklenen sema_uygula govdesi bulunamadi")
        return 1
    icerik = icerik.replace(ESKI, YENI, 1)
    with open(HEDEF, "w", encoding="utf-8") as f:
        f.write(icerik)
    print("[YAMA] Goc uygulayicisi eklendi")
    return 0


if __name__ == "__main__":
    sys.exit(main())
