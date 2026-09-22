# -*- coding: utf-8 -*-
"""GOKTUNGU KOPRU — URUN PROFILI sinavi (Faz 5).

Iki seyi dogrular:

  1) GERIYE UYUMLULUK (KRITIK): `GOKTUNGU_KOPRU_URUN` ayarsiz VE kurulum
     kokunde `URUN` dosyasi yokken davranis mevcut BRDIMG davranisiyla
     AYNIDIR (tum servisler gorunur, profil suzgeci no-op).

  2) Profil secildiginde (brdimg / brdtlm) panel listelemesi ve
     `servis_gorunur_mu` profil ∩ yetki ile suzulur; kapsam disi servis
     baslatilamaz.

Calistirma:
    python3.11 12_TESTLER/BRDTLM/sinav_urun_profil.py
"""
import os
import sys

KOK = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..",
    "03_BRDIMG", "ORTAK_KOPRU_KAYNAGI"))
sys.path.insert(0, KOK)

from kopru import servisler as S  # noqa: E402

_gecen = 0
_kalan = 0


def d(baslik, kosul, neden=""):
    global _gecen, _kalan
    if kosul:
        _gecen += 1
        print("  [GECTI] %s" % baslik)
    else:
        _kalan += 1
        print("  [KALDI] %s%s" % (baslik, (" — %s" % neden) if neden else ""))


def _profil_temizle():
    os.environ.pop("GOKTUNGU_KOPRU_URUN", None)
    # Dosya onbellegini de sifirla ki test ortamlari birbirini ezmesin.
    S._URUN_DOSYA_ONBELLEK = None


def sinav_geriye_uyumluluk():
    print("\n--- 1) GERIYE UYUMLULUK: profil ayarsiz ---")
    _profil_temizle()
    d("aktif_urun() None", S.aktif_urun() is None)
    d("urun_servisleri() None (suzme yok)", S.urun_servisleri() is None)
    # Tum servisler kapsam icinde sayilir.
    d("tum servisler urun_kapsaminda",
      all(S.urun_kapsaminda_mi(a) for a in S.SERVIS_SIRA))

    # servis_gorunur_mu: profil ayarsizken ESKI mantik birebir.
    # yetkiler=None: cekirdek (None yetki) acik, ucretli kapali.
    d("dron gorunur (cekirdek, yetkisiz)",
      S.servis_gorunur_mu("dron", None) is True)
    d("video gorunur (cekirdek, yetkisiz)",
      S.servis_gorunur_mu("video", None) is True)
    d("ai KAPALI (yetkisiz)",
      S.servis_gorunur_mu("ai", None) is False)
    d("radar KAPALI (yetkisiz)",
      S.servis_gorunur_mu("radar", None) is False)
    d("m50 KAPALI (yetkisiz)",
      S.servis_gorunur_mu("m50", None) is False)
    # Yetki verilince acilir.
    yet = {"ai": True, "radar": True, "gccdual": True, "m50": True}
    d("ai yetkiyle acilir", S.servis_gorunur_mu("ai", yet) is True)
    d("gcsdual yetkiyle acilir (gccdual anahtari)",
      S.servis_gorunur_mu("gcsdual", yet) is True)

    # ServisYoneticisi.durum(): yetkiler=None -> TUM 6 servis (eski
    # davranis; profil suzgeci no-op).
    yon = S.ServisYoneticisi(gunluk_dizin=".")
    liste = yon.durum(None)
    adlar = [x["ad"] for x in liste]
    d("durum(None) tum 6 servisi listeler (SERVIS_SIRA)",
      adlar == list(S.SERVIS_SIRA), "gelen: %s" % adlar)
    # baslat kapsam disi reddi profil ayarsizken YOK (bilinmeyen servis
    # disinda). Kapsam kontrolu no-op oldugu icin video reddedilmez.
    tamam, hata = yon.baslat("video", yetkiler=None)
    # video basarili baslamaya calisir (alt surec); reddi PROFIL kaynakli
    # olmamali. Basari/basarisizlik ortam Python'una bagli; onemli olan
    # 'urun paketinde yer almiyor' HATASININ olmamasi.
    d("profil ayarsiz: video baslatma PROFIL kaynakli reddedilmez",
      "urun paketinde" not in (hata or ""), "hata: %s" % (hata,))
    yon.tumunu_durdur()


def sinav_brdtlm_profili():
    print("\n--- 2) BRDTLM profili (dron/m50/radar/gcsdual) ---")
    _profil_temizle()
    os.environ["GOKTUNGU_KOPRU_URUN"] = "brdtlm"
    d("aktif_urun() brdtlm", S.aktif_urun() == "brdtlm")
    d("urun_servisleri() 4 servis",
      S.urun_servisleri() == frozenset(("dron", "m50", "radar", "gcsdual")))
    d("video kapsam DISI", S.urun_kapsaminda_mi("video") is False)
    d("ai kapsam DISI", S.urun_kapsaminda_mi("ai") is False)
    d("dron kapsam ICI", S.urun_kapsaminda_mi("dron") is True)

    # Panel listelemesi: yetki tam verilse bile video/ai gorunmez.
    yet = {"ai": True, "video": True, "radar": True, "gccdual": True,
           "m50": True}
    d("servis_gorunur_mu(video) profil disi -> False (yetki tam olsa da)",
      S.servis_gorunur_mu("video", yet) is False)
    d("servis_gorunur_mu(ai) profil disi -> False",
      S.servis_gorunur_mu("ai", yet) is False)
    d("servis_gorunur_mu(dron) -> True", S.servis_gorunur_mu("dron", yet))
    d("servis_gorunur_mu(radar) yetkiyle -> True",
      S.servis_gorunur_mu("radar", yet))

    yon = S.ServisYoneticisi(gunluk_dizin=".")
    # yetkiler=None bile olsa profil disi servisler listede yok.
    adlar = [x["ad"] for x in yon.durum(None)]
    d("durum(None) yalniz profil servisleri (video/ai yok)",
      set(adlar) == {"dron", "m50", "radar", "gcsdual"}
      and "video" not in adlar and "ai" not in adlar,
      "gelen: %s" % adlar)
    # Sira korunur (SERVIS_SIRA icindeki dron, gcsdual, radar, m50).
    d("durum sirasi SERVIS_SIRA'ya uyar",
      adlar == [a for a in S.SERVIS_SIRA if a in
                ("dron", "m50", "radar", "gcsdual")],
      "gelen: %s" % adlar)
    # Kapsam disi servis baslatma reddi.
    tamam, hata = yon.baslat("video", yetkiler=None)
    d("video baslatma PROFIL kaynakli reddedilir",
      tamam is False and "urun paketinde" in (hata or ""),
      "hata: %s" % (hata,))
    yon.tumunu_durdur()


def sinav_brdimg_profili():
    print("\n--- 3) BRDIMG profili (video/ai) ---")
    _profil_temizle()
    os.environ["GOKTUNGU_KOPRU_URUN"] = "brdimg"
    d("aktif_urun() brdimg", S.aktif_urun() == "brdimg")
    d("urun_servisleri() video+ai",
      S.urun_servisleri() == frozenset(("video", "ai")))
    yon = S.ServisYoneticisi(gunluk_dizin=".")
    adlar = [x["ad"] for x in yon.durum(None)]
    d("durum(None) yalniz video+ai",
      set(adlar) == {"video", "ai"}, "gelen: %s" % adlar)
    d("dron profil disi", S.urun_kapsaminda_mi("dron") is False)
    yon.tumunu_durdur()


def sinav_bilinmeyen_profil():
    print("\n--- 4) Bilinmeyen/bos profil -> ESKI davranis ---")
    _profil_temizle()
    os.environ["GOKTUNGU_KOPRU_URUN"] = "sacmalik"
    d("bilinmeyen profil None (tumu acik)", S.aktif_urun() is None)
    yon = S.ServisYoneticisi(gunluk_dizin=".")
    adlar = [x["ad"] for x in yon.durum(None)]
    d("durum(None) tum 6 servis (guvenli geri donus)",
      adlar == list(S.SERVIS_SIRA), "gelen: %s" % adlar)
    yon.tumunu_durdur()
    _profil_temizle()


def main():
    print("=" * 62)
    print(" URUN PROFILI SINAVI (Faz 5)")
    print("=" * 62)
    sinav_geriye_uyumluluk()
    sinav_brdtlm_profili()
    sinav_brdimg_profili()
    sinav_bilinmeyen_profil()
    print("\nSONUC: %d gecti / %d kaldi" % (_gecen, _kalan))
    return 1 if _kalan else 0


if __name__ == "__main__":
    sys.exit(main())
