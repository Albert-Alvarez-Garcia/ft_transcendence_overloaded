import time
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

from backend import config

_pool = None


def init_pool():
    global _pool
    for _ in range(20):
        try:
            _pool = ThreadedConnectionPool(1, 10, **config.DB)
            return
        except psycopg2.OperationalError:
            time.sleep(1)
    raise RuntimeError("No se pudo conectar con la base de datos")


@contextmanager
def cursor():
    conn = _pool.getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)
