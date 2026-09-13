"""2.5.26 — Dosya tabanlı güncelleyici için sunucu uçları.

Ekler:
  * _gcs_lisans_dogrula(g)  -> (firma_id, hata)   [ortak lisans kapısı]
  * POST /api/istemci/dosya_manifesti  -> imzalı dosya manifesti (en yeni sürüm)
  * POST /api/istemci/dosya            -> tek yönetilen dosyanın baytları

Kimlik doğrulama guncelleme_paket ile AYNIDIR (gcs: imzalı merkez lisansı;
kopru/video: kurulum_uid+gizli). Dosyalar depo/gcs_dosya/<surum>/ altından
sunulur; dizin gezinme korumalı.

Kullanım: python3.11 yama_dosya_uclari.py <mk_sunucu.py>
"""
import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
if "_gcs_lisans_dogrula" in s:
    sys.exit("HATA: yama zaten uygulanmis")

capa = "# --------------------------------------------------------- kopru indirmeleri"
if s.count(capa) < 1:
    sys.exit("HATA: capa bulunamadi")

blok = '''# ---------------------------- dosya tabanli guncelleyici (2.5.26) --------------
# NEDEN: Imzasiz .exe kurulumlari Windows Defender'da yanlis-pozitif
# (Sabsik.FL.A!ml) uretip guncellemeyi bozuyordu. Arka plan guncelleme
# servisi bunun yerine yalniz DEGISEN duz dosyalari indirir. Bu iki uc
# imzali manifesti ve tek tek dosyalari lisans denetimiyle sunar.
GCS_DOSYA_KOK = "/opt/goktungu/merkez/depo/gcs_dosya"


def _gcs_lisans_dogrula(g):
    """gcs icin imzali merkez lisansini dogrular. (firma_id, hata) doner."""
    belge = g.get("lisans")
    govde = belge.get("lisans") if isinstance(belge, dict) else None
    imza = str(belge.get("imza") or "") if isinstance(belge, dict) else ""
    if (not isinstance(govde, dict) or not imza
            or not depo.veri_imza_dogrula(yetki.govde_bayt(govde), imza)):
        return None, "Lisans belgesi dogrulanamadi"
    try:
        fid = int(govde.get("firma_id"))
    except (TypeError, ValueError):
        return None, "Lisans belgesi dogrulanamadi"
    if not db.deger(
            "SELECT 1 FROM merkez_lisanslari "
            "WHERE firma_id = %s AND lisans_uid = %s",
            (fid, str(govde.get("lisans_uid") or ""))):
        return None, "Lisans bu sunucuda kayitli degil"
    y = yetki.firma_yetkileri(fid)
    if not y or y.get("durum") != "etkin" or not y.get("merkez_lisans"):
        return None, "Merkez Uygulama lisansi etkin degil"
    hakli, neden = bakim.guncelleme_alabilir_mi(fid)
    if not hakli:
        return None, neden
    return fid, ""


def _kopru_kimlik_dogrula(g):
    """kopru/video icin kurulum_uid+gizli dogrular. (firma_id, hata)."""
    uid = str(g.get("kurulum_uid") or "").strip()
    gizli = str(g.get("gizli") or "")
    k = db.tek(
        "SELECT s.firma_id, s.gizli_ozet, s.durum, f.durum AS firma_durum "
        "FROM sunucu_ornekleri s JOIN firmalar f ON f.firma_id = s.firma_id "
        "WHERE s.kurulum_uid = %s", (uid,)) if uid else None
    if not k or not role.gizli_dogrula(gizli, k["gizli_ozet"]):
        return None, "Kurulum kimligi gecersiz"
    if k["durum"] != "etkin" or k["firma_durum"] != "etkin":
        return None, "Kurulum veya firma etkin degil"
    return int(k["firma_id"]), ""


def _guncel_dosya_surum():
    """Dosya deposundaki en yeni yayinlanmis surum (GUNCEL isaretcisi)."""
    try:
        with open(os.path.join(GCS_DOSYA_KOK, "GUNCEL"), encoding="utf-8") as f:
            s = f.read().strip()
        return s if _re.fullmatch(r"[0-9]+(\\.[0-9]+){1,3}", s) else ""
    except OSError:
        return ""


def _dosya_kok_coz(surum, bagil):
    """depo/gcs_dosya/<surum>/<bagil> guvenli mutlak yol; kotuyse None."""
    if not _re.fullmatch(r"[0-9]+(\\.[0-9]+){1,3}", str(surum or "")):
        return None
    parcalar = [x for x in str(bagil or "").replace("\\\\", "/").split("/")
                if x not in ("", ".")]
    if not parcalar or any(x == ".." or ":" in x for x in parcalar):
        return None
    taban = os.path.realpath(os.path.join(GCS_DOSYA_KOK, surum))
    tam = os.path.realpath(os.path.join(taban, *parcalar))
    if tam != taban and not tam.startswith(taban + os.sep):
        return None
    return tam


@yol("POST", r"/api/istemci/dosya_manifesti", yetki="acik")
def _u_istemci_dosya_manifesti(h, istek, oturum):
    g = istek.govde if isinstance(istek.govde, dict) else {}
    urun = str(g.get("urun") or "").strip().lower()
    if urun not in _GUNCELLEME_PAKET_URUNLERI:
        h.hata_yaz(400, "urun zorunlu")
        return
    if urun == "gcs":
        fid, hata = _gcs_lisans_dogrula(g)
    else:
        fid, hata = _kopru_kimlik_dogrula(g)
    if hata:
        h.hata_yaz(403, hata)
        return
    surum = _guncel_dosya_surum()
    yol_ = os.path.join(GCS_DOSYA_KOK, surum, "MANIFEST.imzali.json") if surum else ""
    if not surum or not os.path.isfile(yol_):
        h.hata_yaz(404, "Yayinlanmis dosya manifesti yok")
        return
    try:
        with open(yol_, encoding="utf-8") as f:
            veri = json.load(f)
    except (OSError, ValueError):
        h.hata_yaz(500, "Manifest okunamadi")
        return
    h.json_yaz(veri)


@yol("POST", r"/api/istemci/dosya", yetki="acik")
def _u_istemci_dosya(h, istek, oturum):
    g = istek.govde if isinstance(istek.govde, dict) else {}
    urun = str(g.get("urun") or "").strip().lower()
    surum = str(g.get("surum") or "").strip()
    bagil = str(g.get("yol") or "").strip()
    if urun not in _GUNCELLEME_PAKET_URUNLERI or not surum or not bagil:
        h.hata_yaz(400, "urun, surum ve yol zorunlu")
        return
    if urun == "gcs":
        fid, hata = _gcs_lisans_dogrula(g)
    else:
        fid, hata = _kopru_kimlik_dogrula(g)
    if hata:
        h.hata_yaz(403, hata)
        return
    tam = _dosya_kok_coz(surum, bagil)
    if not tam or not os.path.isfile(tam):
        h.hata_yaz(404, "Dosya bulunamadi")
        return
    h.dosya_akit(tam, os.path.basename(tam))


# --------------------------------------------------------- kopru indirmeleri'''

s = s.replace(capa, blok, 1)
# `_re` gerekli (re modulu). mk_sunucu zaten `import re` iceriyor mu?
import re as _r
if not _r.search(r"^import re$", s, _r.M):
    s = s.replace("import os\n", "import os\nimport re as _re_yok\n", 1)
# _re adini re'ye bagla (mk_sunucu 're' kullaniyor)
s = s.replace("GCS_DOSYA_KOK = \"/opt/goktungu/merkez/depo/gcs_dosya\"",
              "import re as _re\nGCS_DOSYA_KOK = \"/opt/goktungu/merkez/depo/gcs_dosya\"")
open(p, "w", encoding="utf-8").write(s)
print("dosya uclari eklendi")
