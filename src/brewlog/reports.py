"""Monthly care summary reports.

Author: Marwan Helmy
"""

from __future__ import annotations

from calendar import monthrange
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

from .bean import parse_iso
from .storage import JsonStorage


class MonthlyReport:
    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def _month_bounds(self, year: int, month: int) -> tuple[datetime, datetime]:
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        last_day = monthrange(year, month)[1]
        end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
        return start, end

    def _in_range(self, ts: Optional[str], start: datetime, end: datetime) -> bool:
        dt = parse_iso(ts)
        if dt is None:
            return False
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return start <= dt <= end

    def generate(self, year: int, month: int) -> dict[str, Any]:
        start, end = self._month_bounds(year, month)
        brew = [
            e for e in self.storage.list_brew_events()
            if self._in_range(e.get("brewed_at"), start, end)
        ]
        care = [
            c for c in self.storage.list_tasting_logs()
            if self._in_range(c.get("logged_at"), start, end)
        ]
        defects = [
            p for p in self.storage.snapshot().get("defect_reports", [])
            if self._in_range(p.get("reported_at"), start, end)
        ]
        fert = [
            f for f in self.storage.snapshot().get("grind_events", [])
            if self._in_range(f.get("applied_at"), start, end)
        ]

        beans_brewed = Counter(e.get("bean_id") for e in brew)
        care_actions = Counter(c.get("action", "unknown") for c in care)

        by_station: dict[str, int] = defaultdict(int)
        bean_map = {p.id: p for p in self.storage.list_beans(active_only=False)}
        for pid in beans_brewed:
            loc = bean_map.get(pid)
            if loc and loc.station_id:
                by_station[loc.station_id] += beans_brewed[pid]

        return {
            "year": year,
            "month": month,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "totals": {
                "brews": len(brew),
                "tasting_logs": len(care),
                "defect_reports": len(defects),
                "grind_events": len(fert),
                "unique_beans_brewed": len(beans_brewed),
            },
            "top_brewed_beans": beans_brewed.most_common(5),
            "care_action_breakdown": dict(care_actions),
            "brews_by_station": dict(by_station),
            "defect_reports": defects,
        }

    def render_text(self, year: int, month: int) -> str:
        report = self.generate(year, month)
        t = report["totals"]
        lines = [
            f"Brewlog report {year}-{month:02d}",
            f"  Brews: {t['brews']} ({t['unique_beans_brewed']} beans)",
            f"  Care logs: {t['tasting_logs']}",
            f"  Defect incidents: {t['defect_reports']}",
            f"  Grinder: {t['grind_events']}",
        ]
        if report["top_brewed_beans"]:
            lines.append("  Most brewed:")
            for pid, count in report["top_brewed_beans"]:
                name = bean_map_name(self.storage, pid)
                lines.append(f"    - {name}: {count}x")
        return "\n".join(lines)


def bean_map_name(storage: JsonStorage, bean_id: str) -> str:
    try:
        return storage.get_bean(bean_id).name
    except Exception:
        return bean_id
