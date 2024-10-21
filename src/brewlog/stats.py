"""Aggregate cellar statistics.

Author: Marwan Helmy
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .bean import parse_iso
from .reminders import ReminderEngine
from .storage import JsonStorage


class CellarStats:
    def __init__(self, storage: JsonStorage):
        self.storage = storage
        self.reminders = ReminderEngine(storage)

    def snapshot(self) -> dict[str, Any]:
        beans = self.storage.list_beans(active_only=True)
        all_beans = self.storage.list_beans(active_only=False)
        brew = self.storage.list_brew_events()
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        brewed_last_7 = sum(
            1 for e in brew
            if (dt := parse_iso(e.get("brewed_at"))) and dt >= week_ago
        )
        brewed_last_30 = sum(
            1 for e in brew
            if (dt := parse_iso(e.get("brewed_at"))) and dt >= month_ago
        )

        overdue = self.reminders.overdue_only()
        origin_count = len(self.storage.list_origin())
        stations_count = len(self.storage.list_stations())
        tags_count = len(self.storage.list_tags())

        inactive = len(all_beans) - len(beans)
        avg_interval = 0.0
        if beans:
            avg_interval = sum(p.brew_interval_days for p in beans) / len(beans)

        return {
            "generated_at": now.isoformat(),
            "beans_active": len(beans),
            "beans_inactive": inactive,
            "beans_total": len(all_beans),
            "origin_count": origin_count,
            "stations_count": stations_count,
            "tags_count": tags_count,
            "brew_events_total": len(brew),
            "brewed_last_7_days": brewed_last_7,
            "brewed_last_30_days": brewed_last_30,
            "overdue_count": len(overdue),
            "due_today_count": sum(
                1 for r in self.reminders.upcoming(within_days=0, include_overdue=False)
                if r.urgency == "due_today"
            ),
            "avg_brew_interval_days": round(avg_interval, 1),
            "tasting_logs_total": len(self.storage.list_tasting_logs()),
            "notes_total": len(self.storage.list_notes()),
            "collections_total": len(self.storage.list_collections()),
        }

    def render_text(self) -> str:
        s = self.snapshot()
        return (
            f"Cellar stats @ {s['generated_at'][:10]}\n"
            f"  Active beans: {s['beans_active']} / {s['beans_total']}\n"
            f"  Overdue: {s['overdue_count']}\n"
            f"  Brewed (7d / 30d): {s['brewed_last_7_days']} / {s['brewed_last_30_days']}\n"
            f"  Origin: {s['origin_count']}  Stations: {s['stations_count']}"
        )
