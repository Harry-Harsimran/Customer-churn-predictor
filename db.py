import sqlite3
from pathlib import Path

BASE = Path(__file__).parent
DB_PATH = BASE / "data" / "churn.db"


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def rows(sql, params=()):
    with connect() as conn:
        cur = conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def one(sql, params=()):
    r = rows(sql, params)
    return r[0] if r else None
