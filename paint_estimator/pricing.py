"""Pricing engine. No Streamlit here, so it can be tested on its own.

Job -> rooms -> service lines. Each line = qty x rate x option multipliers
(x high-ceiling surcharge if the service is height-sensitive).
"""
import csv
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

UNIT_LABELS = {
    "wall_sqft": "sq ft",
    "ceiling_sqft": "sq ft",
    "perimeter_ft": "linear ft",
    "sqft": "sq ft",
    "linear_ft": "linear ft",
    "each": "ea",
    "hour": "hr",
}


def load_settings(path=DATA_DIR / "settings.json"):
    with open(path) as f:
        return json.load(f)


def load_price_book(path=DATA_DIR / "price_book.csv"):
    book = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            book[row["service_id"]] = {
                "service_id": row["service_id"],
                "category": row["category"],
                "name": row["service"],
                "unit": row["unit"],
                "rate": float(row["rate"]),
                "option_groups": [g.strip() for g in row["option_groups"].split("|") if g.strip()],
                "height_surcharge": row["height_surcharge"].strip().upper() == "Y",
                "description": row["description"],
            }
    return book


def load_options(path=DATA_DIR / "options.csv"):
    """{group: {"label": str, "choices": {option: multiplier}}}, file order kept."""
    groups = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            g = groups.setdefault(row["group"], {"label": row["group_label"], "choices": {}})
            g["choices"][row["option"]] = float(row["multiplier"])
    return groups


def room_measurements(room, settings):
    L, W, H = room["length"], room["width"], room["height"]
    perimeter = 2 * (L + W)
    openings = room["doors"] * settings["door_sqft"] + room["windows"] * settings["window_sqft"]
    return {
        "wall_sqft": max(perimeter * H - openings, 0),
        "ceiling_sqft": L * W,
        "perimeter_ft": perimeter,
    }


def default_qty(service, meas):
    """Auto-fill quantity from room size when the unit allows it."""
    if service["unit"] in meas:
        return round(meas[service["unit"]], 1)
    return 1.0


def is_high_ceiling(room, settings):
    return room["height"] >= settings["high_ceiling_threshold_ft"]


def price_line(line, room, book, options, settings):
    svc = book[line["service_id"]]
    factors = []  # (label, multiplier)
    for group in svc["option_groups"]:
        choice = line["options"].get(group)
        if choice in options.get(group, {}).get("choices", {}):
            factors.append((f"{options[group]['label']}: {choice}", options[group]["choices"][choice]))
    if svc["height_surcharge"] and is_high_ceiling(room, settings):
        factors.append((f"High ceiling ({room['height']:g} ft)", 1 + settings["high_ceiling_surcharge"]))

    total = line["qty"] * svc["rate"]
    for _, mult in factors:
        total *= mult

    unit = UNIT_LABELS[svc["unit"]]
    explanation = f"{line['qty']:,.1f} {unit} × ${svc['rate']:,.2f}"
    explanation += "".join(f" × {m:g} ({lbl})" for lbl, m in factors if m != 1)

    return {
        "name": svc["name"],
        "description": svc["description"],
        "qty": line["qty"],
        "unit_label": unit,
        "rate": svc["rate"],
        "options_text": ", ".join(lbl for lbl, _ in factors),
        "explanation": explanation,
        "total": round(total, 2),
    }


def price_room(room, book, options, settings):
    lines, warnings = [], []
    for line in room["lines"]:
        if line["service_id"] not in book:
            warnings.append(f"{room['name']}: '{line['service_id']}' is no longer in the price book and was skipped.")
            continue
        lines.append(price_line(line, room, book, options, settings))
    adjustments = [{"description": a["description"], "total": round(a["amount"], 2)} for a in room["adjustments"]]
    subtotal = sum(l["total"] for l in lines) + sum(a["total"] for a in adjustments)
    return {
        "name": room["name"],
        "measurements": room_measurements(room, settings),
        "lines": lines,
        "adjustments": adjustments,
        "subtotal": round(subtotal, 2),
        "warnings": warnings,
    }


def price_job(job, book, options, settings):
    rooms = [price_room(r, book, options, settings) for r in job["rooms"]]
    return {
        "rooms": rooms,
        "total": round(sum(r["subtotal"] for r in rooms), 2),
        "warnings": [w for r in rooms for w in r["warnings"]],
    }
