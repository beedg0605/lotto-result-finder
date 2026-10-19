import re
from datetime import date

from flask import Flask, jsonify, render_template, request

import db

app = Flask(__name__)
db.init_db()

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_date(value):
    """Return an ISO date string, None if empty, or raise ValueError."""
    if not value:
        return None
    if not ISO_DATE.match(value):
        raise ValueError(f"'{value}' is not a valid date (use YYYY-MM-DD)")
    date.fromisoformat(value)  # rejects things like 2024-13-45
    return value


def parse_digits(value):
    """'12, 18 24' -> [12, 18, 24]. Raises ValueError on non-numbers."""
    if not value:
        return []
    parts = [p for p in re.split(r"[\s,\-]+", value.strip()) if p]
    try:
        digits = [int(p) for p in parts]
    except ValueError:
        raise ValueError("Digits must be numbers, e.g. 12, 18, 24") from None
    if any(d < 0 or d > 58 for d in digits):
        raise ValueError("Digits must be between 0 and 58")
    return digits


@app.get("/")
def index():
    return render_template("index.html", games=db.list_games())


@app.get("/api/results")
def results():
    try:
        date_from = parse_date(request.args.get("from"))
        date_to = parse_date(request.args.get("to"))
        digits = parse_digits(request.args.get("digits"))
    except ValueError as err:
        return jsonify(error=str(err)), 400

    if date_from and date_to and date_from > date_to:
        return jsonify(error="'From' date must be on or before 'To' date"), 400

    game = request.args.get("game") or None
    if not game:
            digits = []
    return jsonify(results=db.search_draws(date_from, date_to, game, digits))


@app.get("/api/games")
def games():
    return jsonify(games=db.list_games())


if __name__ == "__main__":
    app.run(debug=True)