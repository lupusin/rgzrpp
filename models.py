import sqlite3
from contextlib import contextmanager

DB_PATH = "app.db"

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with get_conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT UNIQUE NOT NULL,
            original_url TEXT NOT NULL,
            user_id TEXT
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT NOT NULL,
            ip TEXT NOT NULL,
            ts DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

def insert_link(short_code: str, original_url: str, user_id: str | None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO links(short_code, original_url, user_id) VALUES(?,?,?)",
            (short_code, original_url, user_id),
        )

def get_original_url(short_code: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT original_url FROM links WHERE short_code=?",
            (short_code,),
        ).fetchone()
        return row["original_url"] if row else None

def add_click(short_code: str, ip: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO clicks(short_code, ip) VALUES(?, ?)",
            (short_code, ip),
        )

def get_stats(short_code: str) -> tuple[int, list[str]] | None:
    with get_conn() as conn:
        exists = conn.execute(
            "SELECT 1 FROM links WHERE short_code=?",
            (short_code,),
        ).fetchone()
        if not exists:
            return None

        total = conn.execute(
            "SELECT COUNT(*) AS c FROM clicks WHERE short_code=?",
            (short_code,),
        ).fetchone()["c"]

        ips = conn.execute(
            "SELECT DISTINCT ip FROM clicks WHERE short_code=? ORDER BY ip",
            (short_code,),
        ).fetchall()
        return total, [r["ip"] for r in ips]
