# -*- coding: utf-8 -*-
"""GÖKTUNGU MERKEZ — yapılandırma ve veritabanı katmanı.

Merkez sunucu, saha GCS kurulumlarından bağımsız bir hizmettir:
  * müşteri (firma) ve kullanıcı kayıtlarını tutar,
  * uçuş ve video kayıtlarını toplar,
  * köprü sunucularının ters WebSocket bağlantılarını kabul eder,
  * güncelleme paketlerini yayımlar.

Tasarım kararları:
  * Tüm veri PostgreSQL'de tutulur; SQLite'a düşülmez.
  * Bağlantı havuzu sınırlıdır (bkz. HAVUZ_MAKS); bağlantı tükenmesi
    v2.4.52'de yaşanan kusurun kök nedeniydi.
  * Yapılandırma dosyası JSON'dur ve ilk çalıştırmada üretilir.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any

# --------------------------------------------------------------------------
# Yollar
# --------------------------------------------------------------------------
PROJE_KOKU = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_KOKU = os.path.join(PROJE_KOKU, "web")
VERI_KOKU = os.path.join(PROJE_KOKU, "veri")
DEPO_KOKU = os.path.join(PROJE_KOKU, "depo")
GUNLUK_KOKU = os.path.join(PROJE_KOKU, "gunluk")
AYAR_DOSYA = os.path.join(VERI_KOKU, "merkez_ayar.json")

for _d in (VERI_KOKU, DEPO_KOKU, GUNLUK_KOKU):
    os.makedirs(_d, exist_ok=True)

VARSAYILAN_AYAR: dict[str, Any] = {
    "http_port": 80,
    "https_port": 443,
    "ws_port": 9443,               # köprü sunucularının ters bağlantı portu
    # 443 üzerindeki WebSocket tüneli bu YEREL, şifresiz dinleyiciye
    # bağlanır. NEDEN: mobil operatör ağları ve kurum güvenlik duvarları
    # 9443 gibi standart dışı portları kapatır; saha gözleminde /app/
    # arayüzü telefonda "Sunucu bağlantısı yok" hatası verdi. Bu port
    # yalnızca 127.0.0.1'e bağlanır, dışarıya açılmaz.
    "ws_duz_port": 9080,
    "dinleme": "0.0.0.0",
    "pg": {
        "host": "127.0.0.1",
        "port": 5432,
        "dbname": "goktungu_merkez",
        "user": "goktungu",
        "password": "",
    },
    "sertifika": {
        "crt": "/etc/letsencrypt/live/goktungu.com/fullchain.pem",
        "key": "/etc/letsencrypt/live/goktungu.com/privkey.pem",
    },
    "alan_adi": "goktungu.com",
    "kurum": "Gökkubbe Teknoloji Anonim Şirketi",
    "oturum_saat": 12,             # yönetici oturum ömrü
    "kopru_zaman_asimi_sn": 90,    # bu süre heartbeat gelmezse çevrimdışı say
    # Köprü ajanına verilecek ters bağlantı adresi (kurulum çıktısında
    # kullanıcıya gösterilir). Sabit IP gerekmez; bağlantıyı köprü açar.
    "kopru_adres": "wss://goktungu.com/kopru",
}


def _derin_birlestir(temel: dict, ek: dict) -> dict:
    for a, d in ek.items():
        if isinstance(d, dict) and isinstance(temel.get(a), dict):
            _derin_birlestir(temel[a], d)
        else:
            temel[a] = d
    return temel


_ayar_kilit = threading.Lock()
_ayar_onbellek: dict[str, Any] | None = None


def ayar_oku() -> dict[str, Any]:
    """Yapılandırmayı okur; dosya yoksa varsayılanlarla üretir."""
    global _ayar_onbellek
    with _ayar_kilit:
        if _ayar_onbellek is not None:
            return _ayar_onbellek
        veri = json.loads(json.dumps(VARSAYILAN_AYAR))
        if os.path.exists(AYAR_DOSYA):
            try:
                with open(AYAR_DOSYA, "r", encoding="utf-8") as f:
                    _derin_birlestir(veri, json.load(f))
            except Exception as e:  # bozuk dosya kurulumu durdurmaz
                print(f"[AYAR] Okunamadi ({e}); varsayilanlar kullanilacak")
        else:
            ayar_yaz(veri)
        _ayar_onbellek = veri
        return veri


def ayar_yaz(veri: dict[str, Any]) -> None:
    """Yapılandırmayı atomik olarak yazar."""
    gecici = AYAR_DOSYA + ".yeni"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=2)
    os.replace(gecici, AYAR_DOSYA)
    global _ayar_onbellek
    _ayar_onbellek = veri


def pg_baglanti_dizesi() -> str:
    p = ayar_oku()["pg"]
    return (
        f"host={p['host']} port={p['port']} dbname={p['dbname']} "
        f"user={p['user']} password={p['password']}"
    )
