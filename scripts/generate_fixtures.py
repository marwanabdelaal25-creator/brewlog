#!/usr/bin/env python3
"""Generate large coffee cellar JSON fixtures (stdlib only)."""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "fixtures" / "cellars"

STATIONS = ["counter", "shelf-a", "freezer", "grinder-zone", "espresso-bar", "pour-over-desk"]
ORIGIN_KEYS = [
    "ethiopia-yirg", "kenya-aa", "colombia-huila", "guatemala-antigua", "brazil-santos",
    "costa-rica", "sumatra", "rwanda-bourbon", "panama-geisha", "decaf-swiss",
]
PERSONAS = [
    "espresso_nut", "v60_daily", "aeropress_travel", "cold_brew_batch", "single_origin_only",
    "dark_roast_shelf", "guest_beans", "office_carafe", "latte_home", "minimalist_two_bags",
]


def _bean_name(rng: random.Random, n: int) -> str:
    adj = rng.choice(["Fresh", "Resting", "Peak", "Old", "Sample", "Backup"])
    sp = rng.choice(ORIGIN_KEYS).replace("-", " ").title()
    return f"{adj} {sp} #{n}"


def _bean_entry(rng: random.Random, idx: int, year: int) -> dict:
    roast = date(year, rng.randint(1, 12), rng.randint(1, 28))
    interval = rng.choice([1, 2, 3, 5, 7])
    last = roast + timedelta(days=rng.randint(0, interval * 4))
    return {
        "id": f"bn-{year}-{idx:06d}",
        "name": _bean_name(rng, idx),
        "origin_key": rng.choice(ORIGIN_KEYS),
        "station_id": f"st-{rng.choice(STATIONS)}",
        "brew_interval_days": interval,
        "last_brewed": last.isoformat(),
        "roast_date": roast.isoformat(),
        "dose_g": rng.choice([12, 15, 18, 20]),
        "tag_ids": [f"tag-{rng.randint(1, 12)}" for _ in range(rng.randint(0, 2))],
        "notes": rng.choice(["", "resting", "freezer stash", "guest bag"]),
    }


def _brew_events(rng: random.Random, beans: list[dict], count: int) -> list[dict]:
    out = []
    for _ in range(count):
        b = rng.choice(beans)
        d = date.fromisoformat(b["last_brewed"]) - timedelta(days=rng.randint(0, 30))
        out.append({
            "id": f"br-{rng.randint(1, 999999):06d}",
            "bean_id": b["id"],
            "brewed_at": d.isoformat(),
            "method": rng.choice(["v60", "aeropress", "espresso", "chemex", "french_press"]),
            "dose_g": b.get("dose_g", 15),
            "yield_g": rng.randint(200, 320),
        })
    return out


def _cellar(rng: random.Random, name: str, beans_n: int) -> dict:
    beans = [_bean_entry(rng, i, rng.randint(2020, 2025)) for i in range(beans_n)]
    return {
        "schema_version": 2,
        "meta": {"name": name, "persona": rng.choice(PERSONAS)},
        "beans": beans,
        "origins": [{"key": k, "name": k.replace("-", " ").title()} for k in ORIGIN_KEYS],
        "stations": [{"id": f"st-{s}", "name": s} for s in STATIONS],
        "brew_events": _brew_events(rng, beans, min(beans_n * 3, 8000)),
        "tasting_logs": [],
        "tags": [],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(8847291)
    specs = [
        ("megacellar-1", 550),
        ("megacellar-2", 650),
        ("megacellar-3", 500),
    ]
    for persona in PERSONAS:
        specs.append((f"persona-{persona}", rng.randint(25, 55)))
    for year in range(2019, 2026):
        specs.append((f"snapshot-{year}", rng.randint(30, 65)))

    total = 0
    for fname, count in specs:
        data = _cellar(rng, fname, count)
        text = json.dumps(data, indent=2)
        path = OUT / f"{fname}.json"
        path.write_text(text, encoding="utf-8")
        total += len(text.encode())
    print(f"wrote {len(specs)} cellar fixtures ({total / (1024*1024):.2f} MB raw)")


if __name__ == "__main__":
    main()
