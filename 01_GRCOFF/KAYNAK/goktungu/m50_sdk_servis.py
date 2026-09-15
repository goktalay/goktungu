# -*- coding: utf-8 -*-
"""GÖKTUNGU — M50 SDK YARDIMCI SÜRECİ (Wine altında Windows Python).

v2.4.216 — Kullanıcı kararı: "Wine köprü süreci". Üreticinin M50 SDK'sı
yalnız Windows x64 DLL'i olarak dağıtılıyor; Ubuntu'daki Merkez bu DLL'i
doğrudan yükleyemez. Bu betik, gömülü Windows Python'u ile **Wine**
altında çalışır, DLL'i `m50_hvs.M50Istemcisi` üzerinden yükler ve
Linux'taki Merkez'e 127.0.0.1 üzerinde JSON satırları (bir istek = bir
satır) ile hizmet verir. Merkez tarafındaki vekil: `m50_wine.py`.

Protokol (tek istemci, sıralı):
    istek : {"id": n, "yordam": "ptz", "args": [...], "kwargs": {...}}
    yanıt : {"id": n, "sonuc": <JSON>}  |  {"id": n, "hata": "metin"}
    özel  : {"yordam": "ping"} -> {"sonuc": "pong", "surum": ...}
            {"yordam": "kapat"} -> süreç biter

Güvenlik: yalnız 127.0.0.1'e bağlanır; kabul edilen yordamlar
`IZINLI_YORDAMLAR` listesiyle sınırlıdır; parola yalnız `baglan`
argümanı içinde RAM'de taşınır, günlüğe yazılmaz.

Bu dosya Merkez paketinden bağımsız çalışır: `m50_hvs.py` dosyayı yola
göre yükler (paket içi göreli içe aktarma gerektirmez).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import socket
import sys
import threading
import traceback

IZINLI_YORDAMLAR = {
    "baglan", "kes", "durum", "ptz", "lens", "aci_konumla", "aci_oku",
    "takip_sec", "takip_baslat", "takip_durdur", "takip_yetenek",
    "onayarlar", "onayar_kaydet", "onayar_cagir", "onayar_sil",
    "onayar_hepsini_sil", "tarama", "konum_oku", "rtsp_url",
    "osd_oku", "osd_yaz",
}
SERVIS_SURUM = "1.0"


def _m50_hvs_yukle(kok: str):
    yol = os.path.join(kok, "m50_hvs.py")
    spec = importlib.util.spec_from_file_location("m50_hvs_wine", yol)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _json_uygun(deger):
    """ctypes/float/bytes karışığı sonuçları JSON'a uygun hale getirir."""
    if isinstance(deger, dict):
        return {str(k): _json_uygun(v) for k, v in deger.items()}
    if isinstance(deger, (list, tuple)):
        return [_json_uygun(v) for v in deger]
    if isinstance(deger, bytes):
        return deger.decode("utf-8", "replace")
    if isinstance(deger, (str, int, float, bool)) or deger is None:
        if isinstance(deger, float) and (deger != deger or deger in (float("inf"), float("-inf"))):
            return None
        return deger
    return str(deger)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--sdk", required=True, help="m50_hvs.py'nin bulunduğu dizin (goktungu paketi)")
    ap.add_argument("--sdk-dizin", default="", help="Hvs bağlayıcısı + bin/HVideoSDK.dll dizini")
    ap.add_argument("--jeton", default="", help="ilk satırda beklenen paylaşılan sır")
    a = ap.parse_args()

    if a.sdk_dizin:
        os.environ["GOKTUNGU_M50_SDK_DIZIN"] = a.sdk_dizin
    hvs = _m50_hvs_yukle(a.sdk)

    def yaz(mesaj, seviye="bilgi"):
        try:
            sys.stderr.write("[M50-WINE][%s] %s\n" % (seviye, mesaj))
            sys.stderr.flush()
        except Exception:
            pass

    ayar = {"m50_sdk_dizin": a.sdk_dizin} if a.sdk_dizin else {}
    istemci = hvs.M50Istemcisi(yaz=yaz, ayar_oku=lambda: dict(ayar), ayar_yaz=lambda _d: None)

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", a.port))
    srv.listen(1)
    yaz("hazir 127.0.0.1:%d (SDK yardimci %s)" % (a.port, SERVIS_SURUM))
    kilit = threading.Lock()

    while True:
        con, _adres = srv.accept()
        con.settimeout(None)
        okuyucu = con.makefile("r", encoding="utf-8", newline="\n")
        yazici = con.makefile("w", encoding="utf-8", newline="\n")
        dogrulandi = not a.jeton
        try:
            for satir in okuyucu:
                satir = satir.strip()
                if not satir:
                    continue
                try:
                    istek = json.loads(satir)
                except ValueError:
                    continue
                kimlik = istek.get("id")
                yordam = str(istek.get("yordam") or "")
                if not dogrulandi:
                    if yordam == "jeton" and istek.get("jeton") == a.jeton:
                        dogrulandi = True
                        yanit = {"id": kimlik, "sonuc": "tamam"}
                    else:
                        yanit = {"id": kimlik, "hata": "jeton gecersiz"}
                        yazici.write(json.dumps(yanit) + "\n"); yazici.flush()
                        break
                elif yordam == "ping":
                    yanit = {"id": kimlik, "sonuc": "pong", "surum": SERVIS_SURUM}
                elif yordam == "kapat":
                    yazici.write(json.dumps({"id": kimlik, "sonuc": "kapaniyor"}) + "\n"); yazici.flush()
                    try:
                        istemci.kes()
                    except Exception:
                        pass
                    return 0
                elif yordam not in IZINLI_YORDAMLAR:
                    yanit = {"id": kimlik, "hata": "izin verilmeyen yordam: %s" % yordam}
                else:
                    args = istek.get("args") or []
                    kwargs = istek.get("kwargs") or {}
                    try:
                        with kilit:
                            hedef = getattr(istemci, yordam)
                            sonuc = hedef(*args, **kwargs) if callable(hedef) else hedef
                        yanit = {"id": kimlik, "sonuc": _json_uygun(sonuc)}
                    except Exception as exc:
                        yanit = {"id": kimlik, "hata": str(exc)[:512] or exc.__class__.__name__}
                        if not isinstance(exc, getattr(hvs, "M50Hata", ())):
                            yaz(traceback.format_exc(), "uyari")
                yazici.write(json.dumps(yanit) + "\n")
                yazici.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            try:
                con.close()
            except Exception:
                pass
        yaz("istemci ayrildi; yeniden baglanti bekleniyor")


if __name__ == "__main__":
    sys.exit(main())
