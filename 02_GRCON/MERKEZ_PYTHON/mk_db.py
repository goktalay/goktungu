# -*- coding: utf-8 -*-
"""GÖKTUNGU MERKEZ — PostgreSQL bağlantı havuzu.

v2.4.52'de saha sürümünde yaşanan **bağlantı tükenmesi** kusurunun
kök nedeni, her istek için yeni bağlantı açılıp bazı yollarda hiç
kapatılmamasıydı. Merkez sunucu baştan doğru kurulur:

  * `ThreadedConnectionPool` ile **sınırlı** havuz (HAVUZ_MAKS),
  * her kullanım `with baglanti()` bağlam yöneticisiyle,
  * hata durumunda otomatik `rollback`,
  * havuza dönerken `idle in transaction` kalıntısı temizlenir,
  * süreç kapanışında havuz kapatılır (ölüm kancası).
"""

from __future__ import annotations

import atexit
import contextlib
import threading
from typing import Any, Iterator

import psycopg2
import psycopg2.extras
from psycopg2 import pool as pg_pool

from mk_ayar import pg_baglanti_dizesi

HAVUZ_ASGARI = 1
HAVUZ_MAKS = 10          # v2.4.52 dersi: sınırsız havuz sunucuyu tüketir

_havuz: pg_pool.ThreadedConnectionPool | None = None
_kilit = threading.Lock()


def havuz() -> pg_pool.ThreadedConnectionPool:
    global _havuz
    with _kilit:
        if _havuz is None:
            _havuz = pg_pool.ThreadedConnectionPool(
                HAVUZ_ASGARI, HAVUZ_MAKS, pg_baglanti_dizesi()
            )
            atexit.register(havuz_kapat)
        return _havuz


def havuz_kapat() -> None:
    global _havuz
    with _kilit:
        if _havuz is not None:
            try:
                _havuz.closeall()
            except Exception:
                pass
            _havuz = None


@contextlib.contextmanager
def baglanti() -> Iterator[Any]:
    """Havuzdan bağlantı alır, iş bitince mutlaka geri verir."""
    h = havuz()
    con = h.getconn()
    try:
        yield con
        if con.status != psycopg2.extensions.STATUS_READY:
            con.commit()
    except Exception:
        with contextlib.suppress(Exception):
            con.rollback()
        raise
    finally:
        # Havuza 'idle in transaction' durumunda bağlantı dönmemeli
        with contextlib.suppress(Exception):
            if con.get_transaction_status() != psycopg2.extensions.TRANSACTION_STATUS_IDLE:
                con.rollback()
        h.putconn(con)


@contextlib.contextmanager
def imlec(sozluk: bool = True) -> Iterator[Any]:
    """Bağlantı + imleç kısayolu. `sozluk=True` ise satırlar dict gibi okunur."""
    with baglanti() as con:
        fabrika = psycopg2.extras.RealDictCursor if sozluk else None
        cur = con.cursor(cursor_factory=fabrika)
        try:
            yield cur
            con.commit()
        except Exception:
            with contextlib.suppress(Exception):
                con.rollback()
            raise
        finally:
            with contextlib.suppress(Exception):
                cur.close()


def sorgu(sql: str, par: tuple | dict | None = None) -> list[dict]:
    with imlec() as cur:
        cur.execute(sql, par)
        if cur.description is None:
            return []
        return [dict(r) for r in cur.fetchall()]


def tek(sql: str, par: tuple | dict | None = None) -> dict | None:
    s = sorgu(sql, par)
    return s[0] if s else None


def calistir(sql: str, par: tuple | dict | None = None) -> int:
    with imlec(sozluk=False) as cur:
        cur.execute(sql, par)
        return cur.rowcount


def deger(sql: str, par: tuple | dict | None = None) -> Any:
    with imlec(sozluk=False) as cur:
        cur.execute(sql, par)
        s = cur.fetchone()
        return s[0] if s else None


def havuz_durum() -> dict[str, int]:
    """Havuz ölçümü — sınav ve /admin sistem durumu için."""
    h = havuz()
    with contextlib.suppress(Exception):
        return {
            "asgari": HAVUZ_ASGARI,
            "maks": HAVUZ_MAKS,
            "kullanilan": len(h._used),      # noqa: SLF001 — ölçüm amaçlı
            "bekleyen": len(h._pool),        # noqa: SLF001
        }
    return {"asgari": HAVUZ_ASGARI, "maks": HAVUZ_MAKS, "kullanilan": -1, "bekleyen": -1}
