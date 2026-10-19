import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("lotto.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS draws (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    game      TEXT    NOT NULL,           -- e.g. 'Mega Lotto 6/45', '3D Lotto'
    draw_time TEXT    NOT NULL DEFAULT '',-- '2PM', '5PM', '9PM' (blank for once-a-day games)
    draw_date TEXT    NOT NULL,           -- ISO format: YYYY-MM-DD
    numbers   TEXT    NOT NULL,           -- JSON list in draw order, e.g. [12, 18, 24, 31, 36, 42]
    jackpot   REAL    NOT NULL DEFAULT 0, -- in PHP
    winners   INTEGER NOT NULL DEFAULT 0,
    UNIQUE (game, draw_time, draw_date)   -- re-importing never creates duplicates
);
CREATE INDEX IF NOT EXISTS idx_draws_date ON draws (draw_date);
CREATE INDEX IF NOT EXISTS idx_draws_game ON draws (game);
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def upsert_draw(conn, game, draw_time, draw_date, numbers, jackpot, winners):
    """Insert a draw, or update it if (game, draw_time, draw_date) already exists."""
    conn.execute(
        """INSERT INTO draws (game, draw_time, draw_date, numbers, jackpot, winners)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(game, draw_time, draw_date) DO UPDATE SET
               numbers = excluded.numbers,
               jackpot = excluded.jackpot,
               winners = excluded.winners""",
        (game, draw_time, draw_date, json.dumps(list(numbers)), jackpot, winners),
    )


def search_draws(date_from=None, date_to=None, game=None, digits=None, limit=500):
    """Filter by date range, game, and digits (every typed digit must appear in the draw)."""
    sql, params = "SELECT * FROM draws WHERE 1=1", []
    if date_from:
        sql += " AND draw_date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND draw_date <= ?"
        params.append(date_to)
    if game:
        sql += " AND game = ?"
        params.append(game)
    sql += " ORDER BY draw_date DESC, game, draw_time"

    wanted = set(digits or [])
    results = []
    with get_conn() as conn:
        for r in conn.execute(sql, params):
            numbers = json.loads(r["numbers"])
            matched = sorted(wanted & set(numbers))
            if wanted and len(matched) != len(wanted):
                continue
            results.append({
                "game": r["game"],
                "draw": r["draw_time"],
                "numbers": numbers,
                "date": r["draw_date"],
                "jackpot": r["jackpot"],
                "winners": r["winners"],
                "matched": matched,
            })
            if len(results) >= limit:
                break
    return results


def list_games():
    with get_conn() as conn:
        return [r[0] for r in conn.execute("SELECT DISTINCT game FROM draws ORDER BY game")]