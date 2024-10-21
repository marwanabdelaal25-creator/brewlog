"""Brew events — track when and how much you brewed."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any
import uuid

from brewlog.validators import (
    validate_id,
    validate_brew_amount_ml,
    validate_brew_method,
    validate_note_body,
)


class BrewQuality(str, Enum):
    TAP = "tap"
    FILTERED = "filtered"
    DISTILLED = "distilled"
    RAIN = "rain"
    OTHER = "other"

    def __str__(self) -> str:
        return self.value


@dataclass
class BrewEvent:
    bean_id: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:14])
    brewed_at: str = field(default_factory=lambda: date.today().isoformat())
    amount_ml: float | None = None
    method: str = "top_brew"
    brew_quality: BrewQuality = BrewQuality.TAP
    runoff: bool = False
    notes: str = ""
    skipped: bool = False
    skip_reason: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def __post_init__(self) -> None:
        self.bean_id = validate_id(self.bean_id, "bean_id")
        self.id = validate_id(self.id)
        if self.amount_ml is not None:
            self.amount_ml = validate_brew_amount_ml(self.amount_ml)
        self.method = validate_brew_method(self.method)
        if isinstance(self.brew_quality, str):
            self.brew_quality = BrewQuality(self.brew_quality)

    @classmethod
    def create(cls, bean_id: str, **kwargs: Any) -> "BrewEvent":
        eid = kwargs.pop("id", None) or uuid.uuid4().hex[:14]
        return cls(bean_id=bean_id, id=eid, **kwargs)

    @classmethod
    def skip(cls, bean_id: str, reason: str = "") -> "BrewEvent":
        return cls(bean_id=bean_id, skipped=True, skip_reason=reason.strip())

    @property
    def brewed_date(self) -> date:
        return date.fromisoformat(self.brewed_at[:10])

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["brew_quality"] = self.brew_quality.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BrewEvent":
        return cls(
            bean_id=data["bean_id"],
            id=data.get("id", uuid.uuid4().hex[:14]),
            brewed_at=data.get("brewed_at", date.today().isoformat()),
            amount_ml=data.get("amount_ml"),
            method=data.get("method", "top_brew"),
            brew_quality=BrewQuality(data.get("brew_quality", "tap")),
            runoff=bool(data.get("runoff", False)),
            notes=data.get("notes", ""),
            skipped=bool(data.get("skipped", False)),
            skip_reason=data.get("skip_reason", ""),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
        )

    def summary(self) -> str:
        if self.skipped:
            return "skipped: %s" % (self.skip_reason or "no reason")
        amt = "%.0fml" % self.amount_ml if self.amount_ml else "unknown amount"
        return "%s on %s via %s" % (amt, self.brewed_at[:10], self.method)


class BrewLog:
    """Append-only log of brew events with query helpers."""

    def __init__(self) -> None:
        self._events: dict[str, BrewEvent] = {}
        self._by_bean: dict[str, list[str]] = {}

    def record(self, event: BrewEvent) -> BrewEvent:
        if event.id in self._events:
            raise ValueError("duplicate event id")
        self._events[event.id] = event
        self._by_bean.setdefault(event.bean_id, []).append(event.id)
        return event

    def log_brew(
        self,
        bean_id: str,
        amount_ml: float | None = None,
        when: date | None = None,
        **kwargs: Any,
    ) -> BrewEvent:
        ev = BrewEvent.create(
            bean_id=bean_id,
            brewed_at=(when or date.today()).isoformat(),
            amount_ml=amount_ml,
            **kwargs,
        )
        return self.record(ev)

    def get(self, event_id: str) -> BrewEvent | None:
        return self._events.get(event_id)

    def for_bean(self, bean_id: str) -> list[BrewEvent]:
        ids = self._by_bean.get(bean_id, [])
        events = [self._events[i] for i in ids if i in self._events]
        return sorted(events, key=lambda e: e.brewed_at, reverse=True)

    def last_for_bean(self, bean_id: str) -> BrewEvent | None:
        events = self.for_bean(bean_id)
        for ev in events:
            if not ev.skipped:
                return ev
        return None

    def all(self) -> list[BrewEvent]:
        return sorted(self._events.values(), key=lambda e: e.brewed_at, reverse=True)

    def between(self, start: date, end: date) -> list[BrewEvent]:
        out: list[BrewEvent] = []
        for ev in self._events.values():
            d = ev.brewed_date
            if start <= d <= end:
                out.append(ev)
        return sorted(out, key=lambda e: e.brewed_at)

    def total_ml_for_bean(self, bean_id: str, days: int = 30) -> float:
        cutoff = date.today().toordinal() - days
        total = 0.0
        for ev in self.for_bean(bean_id):
            if ev.skipped or ev.amount_ml is None:
                continue
            if ev.brewed_date.toordinal() >= cutoff:
                total += ev.amount_ml
        return total

    def average_interval_days(self, bean_id: str) -> float | None:
        dates = [ev.brewed_date for ev in self.for_bean(bean_id) if not ev.skipped]
        if len(dates) < 2:
            return None
        dates.sort()
        gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
        return sum(gaps) / len(gaps)

    def load_many(self, events: list[BrewEvent]) -> None:
        for ev in events:
            self.record(ev)

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self.all()]

    @classmethod
    def from_dict_list(cls, rows: list[dict[str, Any]]) -> "BrewLog":
        log = cls()
        for row in rows:
            log.record(BrewEvent.from_dict(row))
        return log

    def count(self) -> int:
        return len(self._events)

    def count_for_bean(self, bean_id: str) -> int:
        return len(self._by_bean.get(bean_id, []))

    def remove_for_bean(self, bean_id: str) -> int:
        ids = list(self._by_bean.pop(bean_id, []))
        for eid in ids:
            self._events.pop(eid, None)
        return len(ids)

    def streak_days(self, bean_id: str) -> int:
        """Days since last missed expected brew — naive impl."""
        last = self.last_for_bean(bean_id)
        if last is None:
            return 0
        return (date.today() - last.brewed_date).days


@dataclass
class BrewBatch:
    """Group brew session — several beans at once."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    brewed_at: str = field(default_factory=lambda: date.today().isoformat())
    event_ids: list[str] = field(default_factory=list)
    notes: str = ""
    total_ml: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BrewBatch":
        return cls(
            id=data.get("id", uuid.uuid4().hex[:10]),
            brewed_at=data.get("brewed_at", date.today().isoformat()),
            event_ids=list(data.get("event_ids") or []),
            notes=data.get("notes", ""),
            total_ml=float(data.get("total_ml", 0)),
        )


def log_batch_brew(
    log: BrewLog,
    bean_amounts: dict[str, float],
    when: date | None = None,
    method: str = "top_brew",
    notes: str = "",
) -> BrewBatch:
    """Brew multiple beans in one session."""
    batch = BrewBatch(brewed_at=(when or date.today()).isoformat(), notes=notes)
    total = 0.0
    for bean_id, amount_ml in bean_amounts.items():
        ev = log.log_brew(bean_id, amount_ml=amount_ml, when=when, method=method)
        batch.event_ids.append(ev.id)
        total += amount_ml
    batch.total_ml = total
    return batch


def weekly_brew_stats(log: BrewLog, weeks: int = 4) -> dict[str, Any]:
    """Aggregate brew volume over recent weeks."""
    end = date.today()
    start = end - timedelta(days=weeks * 7)
    events = log.between(start, end)
    active = [e for e in events if not e.skipped]
    by_week: dict[str, float] = {}
    for ev in active:
        if ev.amount_ml is None:
            continue
        wk = ev.brewed_date.isocalendar()[1]
        key = "%d-W%02d" % (ev.brewed_date.year, wk)
        by_week[key] = by_week.get(key, 0) + ev.amount_ml
    return {
        "weeks": weeks,
        "event_count": len(active),
        "skipped_count": len(events) - len(active),
        "total_ml": sum(e.amount_ml or 0 for e in active),
        "by_week_ml": by_week,
    }


def beans_brewed_on(log: BrewLog, day: date) -> list[str]:
    ids: list[str] = []
    for ev in log.between(day, day):
        if not ev.skipped and ev.bean_id not in ids:
            ids.append(ev.bean_id)
    return ids


def export_brew_csv_rows(log: BrewLog) -> list[list[str]]:
    """Simple CSV rows for export — header included."""
    rows = [["id", "bean_id", "brewed_at", "amount_ml", "method", "skipped", "notes"]]
    for ev in log.all():
        rows.append([
            ev.id,
            ev.bean_id,
            ev.brewed_at,
            str(ev.amount_ml or ""),
            ev.method,
            "yes" if ev.skipped else "no",
            ev.notes.replace("\n", " "),
        ])
    return rows


def detect_brew_drift(
    log: BrewLog,
    bean_id: str,
    expected_interval: int,
) -> dict[str, Any]:
    """Compare actual average interval vs expected — handy for tuning."""
    avg = log.average_interval_days(bean_id)
    if avg is None:
        return {"bean_id": bean_id, "drift": None, "message": "not enough data"}
    drift = avg - expected_interval
    msg = "on track"
    if drift > 2:
        msg = "brew less often than scheduled"
    elif drift < -2:
        msg = "brew more often than scheduled"
    return {
        "bean_id": bean_id,
        "expected_days": expected_interval,
        "actual_avg_days": round(avg, 1),
        "drift_days": round(drift, 1),
        "message": msg,
    }


def brew_history_summary(log: BrewLog, bean_id: str) -> dict[str, Any]:
    events = log.for_bean(bean_id)
    if not events:
        return {"bean_id": bean_id, "count": 0}
    amounts = [e.amount_ml for e in events if e.amount_ml and not e.skipped]
    return {
        "bean_id": bean_id,
        "count": len(events),
        "skipped": sum(1 for e in events if e.skipped),
        "avg_amount_ml": (sum(amounts) / len(amounts)) if amounts else None,
        "last": events[0].brewed_at if events else None,
        "avg_interval_days": log.average_interval_days(bean_id),
    }


def compare_beans_brew_use(log: BrewLog, bean_ids: list[str], days: int = 30) -> list[dict[str, Any]]:
    rows = []
    for pid in bean_ids:
        total = log.total_ml_for_bean(pid, days=days)
        rows.append({"bean_id": pid, "total_ml": total, "days": days})
    return sorted(rows, key=lambda r: -r["total_ml"])


def missed_brews_estimate(
    log: BrewLog,
    bean_id: str,
    expected_interval: int,
    since: date | None = None,
) -> int:
    """Rough count of missed cycles based on gap since last brew."""
    last = log.last_for_bean(bean_id)
    if last is None:
        return 0
    ref = since or date.today()
    gap = (ref - last.brewed_date).days
    if gap <= expected_interval:
        return 0
    return gap // expected_interval


def filter_events_by_method(log: BrewLog, method: str) -> list[BrewEvent]:
    m = validate_brew_method(method)
    return [e for e in log.all() if e.method == m and not e.skipped]


class BrewAnalytics:
    """Aggregate stats across the brew log — for reports/stats modules."""

    def __init__(self, log: BrewLog) -> None:
        self.log = log

    def total_events(self) -> int:
        return self.log.count()

    def total_volume_ml(self, days: int | None = None) -> float:
        if days is None:
            return sum(e.amount_ml or 0 for e in self.log.all() if not e.skipped)
        return sum(
            self.log.total_ml_for_bean(pid, days=days)
            for pid in self._bean_ids()
        )

    def _bean_ids(self) -> set[str]:
        return set(self.log._by_bean.keys())

    def busiest_day_of_week(self) -> str | None:
        names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        counts = [0] * 7
        for ev in self.log.all():
            if ev.skipped:
                continue
            counts[ev.brewed_date.weekday()] += 1
        if not any(counts):
            return None
        return names[counts.index(max(counts))]

    def avg_amount_by_bean(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for pid in self._bean_ids():
            amounts = [
                e.amount_ml for e in self.log.for_bean(pid)
                if e.amount_ml and not e.skipped
            ]
            if amounts:
                out[pid] = sum(amounts) / len(amounts)
        return out

    def skip_rate(self) -> float:
        events = self.log.all()
        if not events:
            return 0.0
        skipped = sum(1 for e in events if e.skipped)
        return skipped / len(events)

    def method_breakdown(self) -> dict[str, int]:
        tallies: dict[str, int] = {}
        for ev in self.log.all():
            if ev.skipped:
                continue
            tallies[ev.method] = tallies.get(ev.method, 0) + 1
        return tallies

    def report(self) -> dict[str, Any]:
        return {
            "total_events": self.total_events(),
            "total_volume_ml": self.total_volume_ml(),
            "busiest_day": self.busiest_day_of_week(),
            "skip_rate": round(self.skip_rate(), 3),
            "methods": self.method_breakdown(),
            "beans_tracked": len(self._bean_ids()),
        }


def merge_brew_logs(a: BrewLog, b: BrewLog) -> BrewLog:
    merged = BrewLog()
    for ev in a.all():
        merged.record(ev)
    for ev in b.all():
        if ev.id not in merged._events:
            merged.record(ev)
    return merged



