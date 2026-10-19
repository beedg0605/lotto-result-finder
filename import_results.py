"""Import PCSO draw results (CSV or JSON files) into lotto.db.

Usage:
    python import_results.py kaggle_history.csv newer_results.json --from 2016-01-01

"""
import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import db

# Field-name aliases (compared lowercase, spaces/underscores/dashes removed)
ALIASES = {
    "date":      ["date", "drawdate", "draw_date"],
    "game":      ["game", "lottogame", "gamename", "lottogameid", "lottogamename"],
    "draw":      ["draw", "drawtime", "time"],
    "numbers":   ["ballnumbers", "numbers", "combinations", "combination",
                  "winningnumbers", "result", "results"],
    "jackpot":   ["jackpot", "jackpotphp", "jackpotamount", "prize"],
    "winners":   ["winners", "numberofwinners", "winner", "jackpotwinners"],
}

GAME_BY_SIZE = {          # 6-number games, identified by their "6/xx" token
    "42": "Lotto 6/42", "45": "Mega Lotto 6/45", "49": "Super Lotto 6/49",
    "55": "Grand Lotto 6/55", "58": "Ultra Lotto 6/58",
}
GAME_RENAMES = {"ez2 lotto": "2D Lotto", "2d lotto": "2D Lotto", "3d lotto": "3D Lotto",
                "swertres": "3D Lotto", "suertres lotto": "3D Lotto",
                "4d lotto": "4D Lotto", "6d lotto": "6D Lotto"}
# lotto_games.csv (lottopcso.io export) uses a numeric game id and a 24-hour draw_time
GAME_BY_ID = {"1": "Lotto 6/42", "2": "Mega Lotto 6/45", "3": "Super Lotto 6/49",
              "4": "Grand Lotto 6/55", "5": "Ultra Lotto 6/58", "6": "2D Lotto",
              "7": "3D Lotto", "8": "4D Lotto", "9": "6D Lotto"}
DAILY_TIMES = {"14:00:00": "2PM", "17:00:00": "5PM", "21:00:00": "9PM"}
TIME_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s?(AM|PM)", re.I)   # 2PM, 2 PM, 11:30AM


DATE_FORMATS = ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y", "%m/%d/%y",
                "%b %d, %Y", "%B %d, %Y", "%d-%b-%Y", "%Y/%m/%d"]

def fmt_time(m):
    """'02:00 PM' -> '2PM', '11:30AM' -> '11:30AM'."""
    minutes = f":{m.group(2)}" if m.group(2) and m.group(2) != "00" else ""
    return f"{int(m.group(1))}{minutes}{m.group(3).upper()}"

def norm_key(k):
    return re.sub(r"[^a-z0-9]", "", str(k).lower())


def pick(row, field):
    keys = {norm_key(k): k for k in row}
    for alias in ALIASES[field]:
        if norm_key(alias) in keys:
            return row[keys[norm_key(alias)]]
    return None

def pick_jackpot(row):
    """lotto_games.csv spreads the jackpot over several 'jackpot_amount_in_php' columns."""
    for k, v in row.items():
        if norm_key(k).startswith("jackpotamount") and str(v).strip() not in ("", "nan"):
            return v
    return pick(row, "jackpot")

def parse_date(value):
    text = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"unreadable date '{text}'")


def parse_numbers(value, row):
    if value is None:  # maybe split across columns like n1..n6 / ball1..ball6
        cols = [v for k, v in row.items() if re.fullmatch(r"(ball|n|number)_?\d", norm_key(k)) and str(v).strip()]
        value = cols or None
    if value is None:
        raise ValueError("no winning numbers found")
    parts = value if isinstance(value, list) else re.split(r"[^\d]+", str(value))
    nums = [int(str(p).strip()) for p in parts if str(p).strip() != ""]
    if not nums:
        raise ValueError("no winning numbers found")
    return nums


def parse_number(value, cast=float):
    if value in (None, ""):
        return cast(0)
    cleaned = re.sub(r"[^\d.]", "", str(value))
    return cast(float(cleaned)) if cleaned else cast(0)


def normalize_game(game, draw):
    game = str(game).strip()
    time = ""
    if game in GAME_BY_ID:                   # numeric id + '14:00:00' style time
        game = GAME_BY_ID[game]
        if game in ("2D Lotto", "3D Lotto"):
            time = DAILY_TIMES.get(str(draw).strip(), "")
        return game, time
    m = TIME_RE.search(str(draw or ""))      # draw '9PM Draw' -> '9PM'
    if m:
        time = fmt_time(m)
    m = TIME_RE.search(game)                 # game '3D Lotto 2PM' -> '3D Lotto' + '2PM'
    if m:
        time = time or fmt_time(m)
        game = game[:m.start()].strip()
    size = re.search(r"6\s*/\s*(42|45|49|55|58)", game)
    if size:
        game = GAME_BY_SIZE[size.group(1)]
    else:
        game = GAME_RENAMES.get(game.lower(), game)
    return game, time


def normalize(row):
    date_raw, game_raw = pick(row, "date"), pick(row, "game")
    if date_raw in (None, "") or game_raw in (None, ""):
        raise ValueError("missing date or game")
    game, time = normalize_game(game_raw, pick(row, "draw"))
    return (game, time, parse_date(date_raw), parse_numbers(pick(row, "numbers"), row),
            parse_number(pick_jackpot(row)), parse_number(pick(row, "winners"), int))


def load_rows(path):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header, seen = [], Counter()
            for name in next(reader):          # repeated names get a suffix, not overwritten
                header.append(name if not seen[name] else f"{name}_dup{seen[name]}")
                seen[name] += 1
            return [dict(zip(header, line)) for line in reader]
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = next((v for v in data.values() if isinstance(v, list)), [])
    return data


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="CSV or JSON files to import")
    ap.add_argument("--from", dest="start", default="2016-01-01", help="skip draws before this date (default 2016-01-01)")
    ap.add_argument("--to", dest="end", default=None, help="skip draws after this date")
    args = ap.parse_args()

    db.init_db()
    saved, skipped, out_of_range, reasons, years = 0, 0, 0, Counter(), Counter()
    with db.get_conn() as conn:
        for file in args.files:
            rows = load_rows(file)
            print(f"{file}: {len(rows)} rows read")
            for row in rows:
                try:
                    game, time, date, nums, jackpot, winners = normalize(row)
                except (ValueError, TypeError) as err:
                    skipped += 1
                    reasons[str(err)] += 1
                    continue
                if date < args.start or (args.end and date > args.end):
                    out_of_range += 1
                    continue
                db.upsert_draw(conn, game, time, date, nums, jackpot, winners)
                saved += 1
                years[date[:4]] += 1

    print(f"\nSaved {saved} draws | outside date range: {out_of_range} | skipped: {skipped}")
    for reason, n in reasons.most_common(5):
        print(f"  skipped {n}x: {reason}")
    print("Draws per year:", dict(sorted(years.items())))


if __name__ == "__main__":
    sys.exit(main())