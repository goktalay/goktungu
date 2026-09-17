"""Creality K2 (ve K1 ailesi) yerel WebSocket protokolü — saf, G/Ç'siz katman.

Yazıcı ``ws://<ip>:9999`` üzerinden JSON telemetri iter. İstemci:

* ``{"ModeCode": "heart_beat"}`` gelince düz metin ``ok`` gönderir;
* veri ister: ``{"method": "get", "params": {"ReqPrinterPara": 1}}``;
* komut verir: ``{"method": "set", "params": {"pause": 1}}``.

Protokol Creality tarafından belgelenmemiştir; alan adları ve durum kodları
topluluk gözlemlerine dayanır (bkz. ``14_PRNFRM/README.md``). Kesin olmayan
noktalar bu dosyada ``# DOĞRULANMALI`` ile işaretlidir. Her şey tek yerde
tutulur ki firmware değişince yalnız bu dosya güncellensin.
"""
from __future__ import annotations

import json
from typing import Any

WS_PORT = 9999          # telemetri / komut WebSocket'i
HTTP_PORT = 80          # dosya yükleme, önizleme resmi
WEBRTC_PORT = 8000      # K2 ailesi kamera sinyalleşme ucu (/call/webrtc_local)
MJPEG_PORT = 8080       # K1 ailesi kamera (?action=stream)
ALT_PROTOKOL = "wsslicer"   # Creality web arayüzünün sunduğu alt protokol
KALP_ATISI_YANIT = "ok"

# Yazıcıya sorulabilen veri anahtarları (get)
GET_YAZICI_PARAM = "ReqPrinterPara"
GET_KUTU_BILGISI = "boxsInfo"
GET_DOSYA_LISTESI = "pFileList"

# Normalleştirilmiş durumlar (arayüz ve uyarı sistemi bunları kullanır)
D_CEVRIMDISI = "cevrimdisi"
D_BOSTA = "bosta"
D_HAZIRLANIYOR = "hazirlaniyor"
D_BASIYOR = "basiyor"
D_DURAKLATILDI = "duraklatildi"
D_TAMAMLANDI = "tamamlandi"
D_HATA = "hata"
DURUMLAR = (D_CEVRIMDISI, D_BOSTA, D_HAZIRLANIYOR, D_BASIYOR,
            D_DURAKLATILDI, D_TAMAMLANDI, D_HATA)

# ``state`` alanı kodları — DOĞRULANMALI (K1/K2 topluluk gözlemi)
STATE_KODLARI = {
    0: "bosta",
    1: "basiyor",
    2: "tamamlandi",
    3: "hata",        # bazı sürümlerde "durduruldu"
    4: "durduruldu",
    5: "duraklatildi",
}
DEVICESTATE_HOMING = 7   # deviceState == 7 → eksen sıfırlama (hazırlanıyor)


def istek_get(anahtar: str, **ek: Any) -> str:
    """``get`` isteği üretir: ``istek_get("ReqPrinterPara")``."""
    params: dict[str, Any] = {anahtar: 1}
    params.update(ek)
    return json.dumps({"method": "get", "params": params}, ensure_ascii=False)


def komut_set(params: dict[str, Any]) -> str:
    """``set`` komutu üretir: ``komut_set({"pause": 1})``."""
    return json.dumps({"method": "set", "params": params}, ensure_ascii=False)


# Hazır komutlar
def komut_duraklat() -> str:
    return komut_set({"pause": 1})


def komut_surdur() -> str:
    return komut_set({"pause": 0})


def komut_durdur() -> str:
    return komut_set({"stop": 1})


def komut_isik(acik: bool) -> str:
    return komut_set({"lightSw": 1 if acik else 0})


def komut_nozul_sicaklik(derece: float) -> str:
    return komut_set({"nozzleTempControl": derece})


def komut_tabla_sicaklik(derece: float, no: int = 0) -> str:
    return komut_set({"bedTempControl": {"num": no, "val": derece}})


def komut_fan(yuzde: int) -> str:
    return komut_set({"fan": max(0, min(100, int(yuzde)))})


def kalp_atisi_mi(mesaj: Any) -> bool:
    return isinstance(mesaj, dict) and mesaj.get("ModeCode") == "heart_beat"


def cozumle(metin: str) -> dict | None:
    """Gelen metin çerçevesini JSON sözlüğe çevirir; JSON değilse None."""
    if not metin or metin == KALP_ATISI_YANIT:
        return None
    try:
        veri = json.loads(metin)
    except (ValueError, TypeError):
        return None
    return veri if isinstance(veri, dict) else None


def sayilastir(deger: Any) -> Any:
    """Yazıcı bazı sayıları metin gönderir ("215.5"); sayıya çevirir."""
    if isinstance(deger, bool) or deger is None:
        return deger
    if isinstance(deger, (int, float)):
        return deger
    if isinstance(deger, str):
        s = deger.strip()
        if not s:
            return deger
        try:
            if s.lstrip("+-").isdigit():
                return int(s)
            return float(s)
        except ValueError:
            return deger
    if isinstance(deger, dict):
        return {k: sayilastir(v) for k, v in deger.items()}
    if isinstance(deger, list):
        return [sayilastir(v) for v in deger]
    return deger


def _sayi(ham: dict, *anahtarlar: str, varsayilan: Any = None) -> Any:
    for a in anahtarlar:
        if a in ham and ham[a] is not None and ham[a] != "":
            v = sayilastir(ham[a])
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return v
    return varsayilan


def _metin(ham: dict, *anahtarlar: str) -> str:
    for a in anahtarlar:
        v = ham.get(a)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def hata_bilgisi(ham: dict) -> tuple[int, str]:
    """``err`` alanından (kod, anahtar) döndürür; hata yoksa (0, "")."""
    err = ham.get("err")
    if isinstance(err, dict):
        kod = _sayi(err, "errcode", varsayilan=0) or 0
        return int(kod), str(err.get("key") or "")
    if isinstance(err, (int, float)) and not isinstance(err, bool):
        return int(err), ""
    return 0, ""


def durum_turet(ham: dict) -> str:
    """Ham telemetriden normalleştirilmiş durumu türetir.

    Öncelik: hata > hazırlanıyor > duraklatıldı > tamamlandı > basıyor > boşta.
    Temel sinyaller ha_creality_ws ile aynıdır: dosya adı + ilerleme + pause.
    """
    kod, _ = hata_bilgisi(ham)
    if kod:
        return D_HATA
    state = _sayi(ham, "state")
    if _sayi(ham, "deviceState") == DEVICESTATE_HOMING:
        return D_HAZIRLANIYOR
    duraklatildi = (state == 5 or _sayi(ham, "pause") == 1
                    or ham.get("paused") is True or ham.get("isPaused") is True)
    if duraklatildi:
        return D_DURAKLATILDI
    ilerleme = _sayi(ham, "printProgress", "dProgress")
    dosya = _metin(ham, "printFileName", "printName")
    if state == 2 or (ilerleme is not None and ilerleme >= 100 and dosya):
        return D_TAMAMLANDI
    if state == 1 or (dosya and ilerleme is not None and 0 <= ilerleme < 100
                      and state not in (0, 3, 4)):
        return D_BASIYOR
    return D_BOSTA


def ozet(ham: dict) -> dict:
    """Ham telemetriyi arayüzün kullandığı düz sözlüğe indirger."""
    kod, anahtar = hata_bilgisi(ham)
    kalan_sn = _sayi(ham, "printLeftTime", "printTimeLeft")
    gecen_sn = _sayi(ham, "printJobTime")
    return {
        "durum": durum_turet(ham),
        "state_kodu": _sayi(ham, "state"),
        "device_state": _sayi(ham, "deviceState"),
        "model": _metin(ham, "model"),
        "model_surum": _metin(ham, "modelVersion"),
        "hostname": _metin(ham, "hostname"),
        "dosya": _metin(ham, "printFileName", "printName"),
        "ilerleme": _sayi(ham, "printProgress", "dProgress"),
        "kalan_sn": int(kalan_sn) if kalan_sn is not None else None,
        "gecen_sn": int(gecen_sn) if gecen_sn is not None else None,
        "katman": _sayi(ham, "layer"),
        "toplam_katman": _sayi(ham, "TotalLayer"),
        "nozul": _sayi(ham, "nozzleTemp"),
        "nozul_hedef": _sayi(ham, "targetNozzleTemp"),
        "tabla": _sayi(ham, "bedTemp0"),
        "tabla_hedef": _sayi(ham, "targetBedTemp0"),
        "kabin": _sayi(ham, "boxTemp"),
        "kabin_hedef": _sayi(ham, "targetBoxTemp"),
        "fan": _sayi(ham, "fanPct", "fan"),
        "hiz_yuzde": _sayi(ham, "curFeedratePct"),
        "isik": _sayi(ham, "lightSw"),
        "filament_yok": _sayi(ham, "materialStatus") == 1,
        "cfs_bagli": bool(_sayi(ham, "cfsConnect") or ham.get("boxsInfo")),
        "hata_kodu": kod,
        "hata_anahtari": anahtar,
    }
