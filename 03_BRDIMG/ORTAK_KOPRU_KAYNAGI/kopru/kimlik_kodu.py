# -*- coding: utf-8 -*-
"""GOKTUNGU KOPRU — API KODU COZUMU (1.7.23)

Merkez (GRCON) ya da yerel Merkez Uygulamasi (GRCOFF) "Destek > Kopruler"
panelinde yeni kopru kaydi olusturunca bir API kodu uretir:

    GTK1.<base64url(JSON)>   JSON = {u: kurulum_uid, g: gizli, m: ws adres,
                                     h: http adres (istege bagli), a: ad,
                                     o: ornek_id, t: "grcon"|"grcoff"}

Kopru ilk kurulumda yalniz bu kodu ister; kod kimligi VE merkez adresini
tasidigi icin ayrica IP/e-posta/sifre girilmez. Kod sunucuda ilk basarili
baglantidan sonra silinir; kaybolursa panelden "Kodu yenile" kullanilir.
"""
import base64
import json

API_KOD_ONEK = "GTK1."


def api_kodu_coz(kod):
    """`(sozluk, hata)` dondurur. Bosluk/satir sonu yok sayilir."""
    kod = "".join(str(kod or "").split())
    if not kod:
        return None, "API kodu bos"
    if not kod.startswith(API_KOD_ONEK):
        return None, "API kodu '%s' ile baslamali" % API_KOD_ONEK
    govde = kod[len(API_KOD_ONEK):]
    govde += "=" * (-len(govde) % 4)
    try:
        d = json.loads(base64.urlsafe_b64decode(govde).decode("utf-8"))
    except Exception:
        return None, "API kodu cozulemedi (eksik veya bozuk kopyalanmis)"
    if not isinstance(d, dict) or not (d.get("u") and d.get("g")
                                       and d.get("m")):
        return None, "API kodu eksik alan iceriyor"
    m = str(d.get("m") or "")
    if not (m.startswith("ws://") or m.startswith("wss://")):
        return None, "API kodundaki merkez adresi ws:// veya wss:// olmali"
    h = str(d.get("h") or "")
    if h and not (h.startswith("http://") or h.startswith("https://")):
        return None, "API kodundaki HTTP adresi http(s):// olmali"
    return d, None
