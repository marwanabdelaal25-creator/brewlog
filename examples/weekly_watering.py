#!/usr/bin/env python3
"""Weekly brew workflow — brew overdue and due-today beans.

Author: Marwan Helmy
Run: python examples/weekly_brew.py
     BREWLOG_HOME=~/.brewlog python examples/weekly_brew.py
"""

from __future__ import annotations

import os
from pathlib import Path

from brewlog.reminders import ReminderEngine
from brewlog.storage import JsonStorage
from brewlog.brew import BrewEvent


def cellar_path() -> Path:
    home = os.environ.get("BREWLOG_HOME")
    base = Path(home) if home else Path.home() / ".brewlog"
    return base / "cellar.json"


def main() -> None:
    storage = JsonStorage(cellar_path())
    engine = ReminderEngine(storage)
    due = [r for r in engine.upcoming(within_days=0, include_overdue=True) if r.urgency != "upcoming"]

    if not due:
        print("All caught up — nothing due today or overdue.")
        return

    print(f"Brew {len(due)} bean(s):\n")
    for rem in due:
        bean = storage.get_bean(rem.bean_id)
        amount = bean.brew_amount_ml
        flag = "OVERDUE" if rem.urgency == "overdue" else "TODAY"
        print(f"  [{flag}] {rem.bean_name} (due {rem.due_at.date()})")

        if amount is None:
            print("    skipped — no default amount; set brew_amount_ml on bean")
            continue

        event = BrewEvent.create(bean_id=bean.id, amount_ml=amount, notes="weekly script")
        storage.create_brew_event(event.to_dict())
        print(f"    logged: {event.summary()}")

    print("\nDone. Run `brewlog reminders --within 7` to preview the week ahead.")


if __name__ == "__main__":
    main()
