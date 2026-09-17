"""SQLite kalıcı kayıt: yazıcılar ve olaylar. Sırlar burada tutulmaz."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

SEMA = """
CREATE TABLE IF NOT EXISTS yazicilar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad TEXT NOT NULL,
    ip TEXT NOT NULL UNIQUE,
    port INTEGER NOT NULL DEFAULT 9999,
    model TEXT NOT NULL DEFAULT '',
    hostname TEXT NOT NULL DEFAULT '',
    grup TEXT NOT NULL DEFAULT '',
    notlar TEXT NOT NULL DEFAULT '',
    etkin INTEGER NOT NULL DEFAULT 1,
    eklenme REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS olaylar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman REAL NOT NULL,
    yazici_id INTEGER,
    tur TEXT NOT NULL,
    seviye TEXT NOT NULL DEFAULT 'bilgi',
    mesaj TEXT NOT NULL,
    veri TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS olaylar_zaman ON olaylar(zaman DESC);
"""


class Veritabani:
    def __init__(self, yol: str | Path) -> None:
        self.yol = str(yol)
        self._kilit = threading.Lock()
        self._bag = sqlite3.connect(self.yol, check_same_thread=False)
        self._bag.row_factory = sqlite3.Row
        with self._kilit:
            self._bag.executescript(SEMA)
            self._bag.commit()

    def kapat(self) -> None:
        with self._kilit:
            self._bag.close()

    # --- yazıcılar ---
    def yazicilar(self) -> list[dict]:
        with self._kilit:
            satirlar = self._bag.execute("SELECT * FROM yazicilar ORDER BY ad, id").fetchall()
        return [dict(s) for s in satirlar]

    def yazici(self, yazici_id: int) -> dict | None:
        with self._kilit:
            s = self._bag.execute("SELECT * FROM yazicilar WHERE id=?", (yazici_id,)).fetchone()
        return dict(s) if s else None

    def yazici_ekle(self, ad: str, ip: str, port: int = 9999, model: str = "",
                    hostname: str = "", grup: str = "", notlar: str = "") -> dict:
        with self._kilit:
            cur = self._bag.execute(
                "INSERT INTO yazicilar(ad, ip, port, model, hostname, grup, notlar, eklenme)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (ad.strip(), ip.strip(), int(port), model, hostname, grup, notlar, time.time()))
            self._bag.commit()
            yeni_id = cur.lastrowid
        kayit = self.yazici(int(yeni_id))
        assert kayit is not None
        return kayit

    def yazici_guncelle(self, yazici_id: int, **alanlar) -> dict | None:
        izinli = {"ad", "ip", "port", "model", "hostname", "grup", "notlar", "etkin"}
        alanlar = {k: v for k, v in alanlar.items() if k in izinli}
        if alanlar:
            sql = ", ".join(f"{k}=?" for k in alanlar)
            with self._kilit:
                self._bag.execute(f"UPDATE yazicilar SET {sql} WHERE id=?",
                                  (*alanlar.values(), yazici_id))
                self._bag.commit()
        return self.yazici(yazici_id)

    def yazici_sil(self, yazici_id: int) -> bool:
        with self._kilit:
            cur = self._bag.execute("DELETE FROM yazicilar WHERE id=?", (yazici_id,))
            self._bag.commit()
        return cur.rowcount > 0

    # --- olaylar ---
    def olay_ekle(self, tur: str, mesaj: str, yazici_id: int | None = None,
                  seviye: str = "bilgi", veri: dict | None = None) -> dict:
        zaman = time.time()
        with self._kilit:
            cur = self._bag.execute(
                "INSERT INTO olaylar(zaman, yazici_id, tur, seviye, mesaj, veri) VALUES (?,?,?,?,?,?)",
                (zaman, yazici_id, tur, seviye, mesaj, json.dumps(veri or {}, ensure_ascii=False)))
            self._bag.commit()
            olay_id = cur.lastrowid
        return {"id": olay_id, "zaman": zaman, "yazici_id": yazici_id, "tur": tur,
                "seviye": seviye, "mesaj": mesaj, "veri": veri or {}}

    def olaylar(self, limit: int = 100, yazici_id: int | None = None) -> list[dict]:
        with self._kilit:
            if yazici_id is None:
                satirlar = self._bag.execute(
                    "SELECT * FROM olaylar ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            else:
                satirlar = self._bag.execute(
                    "SELECT * FROM olaylar WHERE yazici_id=? ORDER BY id DESC LIMIT ?",
                    (yazici_id, limit)).fetchall()
        sonuc = []
        for s in satirlar:
            d = dict(s)
            try:
                d["veri"] = json.loads(d.get("veri") or "{}")
            except ValueError:
                d["veri"] = {}
            sonuc.append(d)
        return sonuc
