#!/usr/bin/env python3
"""Smoke test — temp cellar, add bean, log brew, check reminders.

Author: Marwan Helmy
Run: python examples/quick_start.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from brewlog.bean import Bean
from brewlog.reminders import ReminderEngine
from brewlog.storage import JsonStorage
from brewlog.brew import BrewEvent


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "cellar.json"
        storage = JsonStorage(path)
        bean = Bean.create("Test Pothos", brew_interval_days=7, source="example")
        created = storage.create_bean(bean)
        event = BrewEvent.create(bean_id=created.id, amount_ml=200)
        storage.create_brew_event(event.to_dict())
        overdue = ReminderEngine(storage).overdue_only()
        print("cellar:", path)
        print("bean:", created.display_name, f"({created.id})")
        print("brewed:", event.summary())
        print("overdue:", len(overdue))
        assert storage.get_bean(created.id).name == "Test Pothos"
        print("smoke test passed")


if __name__ == "__main__":
    main()
