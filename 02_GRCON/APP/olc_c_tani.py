#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""C senaryosunun neden kacktigini olcer.

Deney 'takeoff_gonderildi' -> 'takeoff_ZZZ_yok' degisimini TUM dosyada
yapiyor. Bu, ORDER BY'i bozmasi BEKLENIYOR. Ama sinav yine geciyor.
Olasi nedenler:
  1) SQL'de baska bir kosul (ts DESC) tesadufen dogru sonucu veriyor
  2) Sahte veri anahtarlari da degisiyor (hayir - sinav dosyasi bozulmuyor)
  3) ORDER BY ayristirmasi bilinmeyen alani atlayip ts DESC'e dusuyor
     ve ts DESC senaryomda YANLIS pilotu getirmiyor

Bu betik 3'u sinar: senaryoyu ts DESC'in de YANLIS cevap verecegi
sekilde kurmak gerekiyor.
"""
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent
sys.path.insert(0, str(KOK))


class SahteSatir(dict):
    def __getitem__(self, k):
        if isinstance(k, int):
            return list(self.values())[k]
        return dict.__getitem__(self, k)


class SahteImlec:
    def __init__(self, s):
        self._s = s

    def fetchone(self):
        return self._s[0] if self._s else None


class Baglanti:
    def __init__(self, kayitlar):
        self.kayitlar = kayitlar
        self.son_sql = ""

    def execute(self, sql, arg=()):
        self.son_sql = " ".join(sql.split())
        if "kalkis_kontrolleri" not in sql:
            return SahteImlec([])
        dron_id, ust, alt = arg[0], arg[1], arg[2]
        uygun = [k for k in self.kayitlar
                 if k["dron_id"] == dron_id
                 and str(k["pilot_eposta"]).strip() != ""
                 and alt <= k["ts"] <= ust]
        anahtarlar = []
        if "ORDER BY" in self.son_sql:
            kisim = self.son_sql.split("ORDER BY", 1)[1]
            for parca in kisim.split("LIMIT")[0].split(","):
                p = parca.strip().split()
                if p:
                    anahtarlar.append(
                        (p[0], len(p) > 1 and p[1].upper() == "DESC"))
        atlanan = []
        for alan, ters in reversed(anahtarlar):
            if not uygun or alan not in uygun[0]:
                atlanan.append(alan)
                continue
            uygun.sort(key=lambda k: k[alan], reverse=ters)
        self.atlanan = atlanan
        self.anahtarlar = anahtarlar
        return SahteImlec([SahteSatir(k) for k in uygun[:1]])


from goktungu import veritabani as vt          # noqa: E402

print("=" * 68)
print("C SENARYOSU TANISI")
print("=" * 68)

# MEVCUT senaryo: Ayse ts=1000 takeoff=0 / Veli ts=900 takeoff=1
mevcut = [
    {"dron_id": 7, "pilot_eposta": "ayse@x.com", "pilot_isim": "Ayse",
     "ts": 1000.0, "takeoff_gonderildi": 0},
    {"dron_id": 7, "pilot_eposta": "veli@x.com", "pilot_isim": "Veli",
     "ts": 900.0, "takeoff_gonderildi": 1},
]
con = Baglanti(mevcut)
ep, isim = vt.ucus_sahibi_detay(7, 950.0, 1100.0, con=con)
print(f"\n[MEVCUT SENARYO]")
print(f"  SQL ORDER BY anahtarlari : {con.anahtarlar}")
print(f"  atlanan (bilinmeyen alan): {con.atlanan}")
print(f"  donen sahip              : {ep} ({isim})")
print(f"  beklenen                 : veli@x.com (takeoff VEREN)")

# takeoff kosulu YOKMUS gibi davran: yalniz ts DESC ile siralanirsa
# hangi pilot gelir?
sadece_ts = sorted(mevcut, key=lambda k: k["ts"], reverse=True)
print(f"  yalniz ts DESC ile gelen : {sadece_ts[0]['pilot_eposta']}")
print("  -> ts DESC 'ayse' getirir; yani ORDER BY bozulursa sonuc")
print("     DEGISMELI. Deneyde degismedigine gore ORDER BY hala")
print("     takeoff alanini kullaniyor OLABILIR.")

# Deneyin yaptigi degisimi TAKLIT et: alan adini bozup ayni cagriyi yap
print(f"\n[DENEYI TAKLIT: alan adi bozuk]")
bozuk = [
    {"dron_id": 7, "pilot_eposta": "ayse@x.com", "pilot_isim": "Ayse",
     "ts": 1000.0, "takeoff_ZZZ_yok": 0},
    {"dron_id": 7, "pilot_eposta": "veli@x.com", "pilot_isim": "Veli",
     "ts": 900.0, "takeoff_ZZZ_yok": 1},
]
con2 = Baglanti(bozuk)
ep2, _ = vt.ucus_sahibi_detay(7, 950.0, 1100.0, con=con2)
print(f"  SQL ORDER BY anahtarlari : {con2.anahtarlar}")
print(f"  atlanan                  : {con2.atlanan}")
print(f"  donen sahip              : {ep2}")
print("  NOT: deney KAYNAK dosyayi bozar, sahte veriyi bozmaz.")
print("       Yani gercek deneyde SQL 'takeoff_ZZZ_yok DESC' olur ve")
print("       sahte veride O ALAN VARDIR (cunku sinav dosyasi bozulmaz)")
print("       -> alan bulunur, siralama calisir, sonuc DEGISMEZ.")
print("")
print("  KOK NEDEN: sahte veri anahtari 'takeoff_gonderildi' sabit;")
print("  SQL'deki alan adi degisince eslesmiyor ve sessizce atlaniyor.")
print("  COZUM: sahte veriyi SQL'den okunan alan adina gore kur, VEYA")
print("  senaryoyu ts DESC'in de YANLIS cevap verecegi sekilde tasarla.")
print("=" * 68)
