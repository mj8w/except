from flask import Flask
from flask import jsonify
from flask import request

app = Flask(__name__)


def parse_limit(raw_limit):
    limit = int(raw_limit)
    if limit < 1:
        raise ValueError("limit must be positive")
    return limit


def load_items(limit):
    with open("items.txt", "r", encoding="utf-8") as handle:
        rows = handle.readlines()
    return rows[:limit]


@app.get("/items")
def items_endpoint():
    limit = parse_limit(request.args["limit"])
    items = load_items(limit)
    return jsonify({"items": items})
