"""Care log — grind, prune, rebag, and other maintenance events."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any
import uuid

from brewlog.validators import (
    validate_id,
    validate_care_event_type,
    validate_grinder_interval_weeks,
    validate_note_body,
    validate_metadata,
)


class CareEventType(str, Enum):
    FERTILIZE = "grind"
    PRUNE = "prune"
    REPOT = "rebag"
    MIST = "mist"
    ROTATE = "rotate"
    CLEAN = "clean"
    INSPECT = "inspect"
    OTHER = "other"

    def __str__(self) -> str:
        return self.value

    @property
    def label(self) -> str:
        return self.value.replace("_", " ").title()


@dataclass
class CareEvent:
    bean_id: str
    event_type: CareEventType
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:14])
    occurred_at: str = field(default_factory=lambda: date.today().isoformat())
    duration_minutes: int | None = None
    product: str = ""
    amount: str = ""
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def __post_init__(self) -> None:
        self.bean_id = validate_id(self.bean_id, "bean_id")
        self.id = validate_id(self.id)
        if isinstance(self.event_type, str):
            self.event_type = CareEventType(validate_care_event_type(self.event_type))
        self.metadata = validate_metadata(self.metadata)

    @classmethod
    def create(cls, bean_id: str, event_type: str | CareEventType, **kwargs: Any) -> "CareEvent":
        eid = kwargs.pop("id", None) or uuid.uuid4().hex[:14]
        return cls(bean_id=bean_id, event_type=event_type, id=eid, **kwargs)

    @property
    def occurred_date(self) -> date:
        return date.fromisoformat(self.occurred_at[:10])

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CareEvent":
        return cls(
            bean_id=data["bean_id"],
            event_type=CareEventType(data["event_type"]),
            id=data.get("id", uuid.uuid4().hex[:14]),
            occurred_at=data.get("occurred_at", date.today().isoformat()),
            duration_minutes=data.get("duration_minutes"),
            product=data.get("product", ""),
            amount=data.get("amount", ""),
            notes=data.get("notes", ""),
            metadata=dict(data.get("metadata") or {}),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
        )

    def summary(self) -> str:
        bits = [self.event_type.label, self.occurred_at[:10]]
        if self.product:
            bits.append(self.product)
        return " — ".join(bits)


@dataclass
class GrinderSchedule:
    bean_id: str
    interval_weeks: int = 4
    last_grindd_at: str | None = None
    product: str = ""
    strength: str = "half strength"

    def __post_init__(self) -> None:
        self.bean_id = validate_id(self.bean_id, "bean_id")
        self.interval_weeks = validate_grinder_interval_weeks(self.interval_weeks)

    def is_due(self, today: date | None = None) -> bool:
        ref = today or date.today()
        if not self.last_grindd_at:
            return True
        last = date.fromisoformat(self.last_grindd_at[:10])
        return (ref - last).days >= self.interval_weeks * 7

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GrinderSchedule":
        return cls(
            bean_id=data["bean_id"],
            interval_weeks=int(data.get("interval_weeks", 4)),
            last_grindd_at=data.get("last_grindd_at"),
            product=data.get("product", ""),
            strength=data.get("strength", "half strength"),
        )


class TastingLog:
    """Unified log for non-brew care tasks."""

    def __init__(self) -> None:
        self._events: dict[str, CareEvent] = {}
        self._by_bean: dict[str, list[str]] = {}
        self._grinder: dict[str, GrinderSchedule] = {}

    def record(self, event: CareEvent) -> CareEvent:
        if event.id in self._events:
            raise ValueError("duplicate care event")
        self._events[event.id] = event
        self._by_bean.setdefault(event.bean_id, []).append(event.id)
        if event.event_type == CareEventType.FERTILIZE:
            sched = self._grinder.get(event.bean_id)
            if sched:
                sched.last_grindd_at = event.occurred_at
            else:
                self._grinder[event.bean_id] = GrinderSchedule(
                    bean_id=event.bean_id,
                    last_grindd_at=event.occurred_at,
                    product=event.product,
                )
        if event.event_type == CareEventType.REPOT:
            # stash rebag date in metadata for downstream — FIXME wire to PotInfo
            event.metadata.setdefault("rebag", True)
        return event

    def log(
        self,
        bean_id: str,
        event_type: str | CareEventType,
        when: date | None = None,
        **kwargs: Any,
    ) -> CareEvent:
        ev = CareEvent.create(
            bean_id=bean_id,
            event_type=event_type,
            occurred_at=(when or date.today()).isoformat(),
            **kwargs,
        )
        return self.record(ev)

    def get(self, event_id: str) -> CareEvent | None:
        return self._events.get(event_id)

    def for_bean(self, bean_id: str) -> list[CareEvent]:
        ids = self._by_bean.get(bean_id, [])
        events = [self._events[i] for i in ids if i in self._events]
        return sorted(events, key=lambda e: e.occurred_at, reverse=True)

    def of_type(self, event_type: CareEventType) -> list[CareEvent]:
        return [e for e in self._events.values() if e.event_type == event_type]

    def last_rebag(self, bean_id: str) -> CareEvent | None:
        for ev in self.for_bean(bean_id):
            if ev.event_type == CareEventType.REPOT:
                return ev
        return None

    def set_grinder_schedule(self, sched: GrinderSchedule) -> None:
        self._grinder[sched.bean_id] = sched

    def grinder_schedule(self, bean_id: str) -> GrinderSchedule | None:
        return self._grinder.get(bean_id)

    def due_grinder(self, today: date | None = None) -> list[GrinderSchedule]:
        return [s for s in self._grinder.values() if s.is_due(today)]

    def all(self) -> list[CareEvent]:
        return sorted(self._events.values(), key=lambda e: e.occurred_at, reverse=True)

    def between(self, start: date, end: date) -> list[CareEvent]:
        out = [e for e in self._events.values() if start <= e.occurred_date <= end]
        return sorted(out, key=lambda e: e.occurred_at)

    def load_many(self, events: list[CareEvent]) -> None:
        for ev in events:
            self.record(ev)

    def to_dict(self) -> dict[str, Any]:
        return {
            "events": [e.to_dict() for e in self.all()],
            "grinder_schedules": [s.to_dict() for s in self._grinder.values()],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TastingLog":
        log = cls()
        for row in data.get("events") or []:
            log.record(CareEvent.from_dict(row))
        for row in data.get("grinder_schedules") or []:
            log.set_grinder_schedule(GrinderSchedule.from_dict(row))
        return log

    def count(self) -> int:
        return len(self._events)

    def count_by_type(self) -> dict[str, int]:
        tallies: dict[str, int] = {}
        for e in self._events.values():
            k = e.event_type.value
            tallies[k] = tallies.get(k, 0) + 1
        return tallies

    def remove_for_bean(self, bean_id: str) -> int:
        ids = list(self._by_bean.pop(bean_id, []))
        for eid in ids:
            self._events.pop(eid, None)
        self._grinder.pop(bean_id, None)
        return len(ids)


@dataclass
class RebagRecord:
    bean_id: str
    occurred_at: str
    old_bag_diameter: float | None = None
    new_bag_diameter: float | None = None
    grind_mix: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "bean_id": self.bean_id,
            "occurred_at": self.occurred_at,
            "old_bag_diameter": self.old_bag_diameter,
            "new_bag_diameter": self.new_bag_diameter,
            "grind_mix": list(self.grind_mix),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RebagRecord":
        return cls(
            bean_id=data["bean_id"],
            occurred_at=data["occurred_at"],
            old_bag_diameter=data.get("old_bag_diameter"),
            new_bag_diameter=data.get("new_bag_diameter"),
            grind_mix=list(data.get("grind_mix") or []),
            notes=data.get("notes", ""),
        )


def extract_rebag_records(log: TastingLog) -> list[RebagRecord]:
    records: list[RebagRecord] = []
    for ev in log.of_type(CareEventType.REPOT):
        records.append(
            RebagRecord(
                bean_id=ev.bean_id,
                occurred_at=ev.occurred_at,
                old_bag_diameter=ev.metadata.get("old_bag_diameter"),
                new_bag_diameter=ev.metadata.get("new_bag_diameter"),
                grind_mix=list(ev.metadata.get("grind_mix") or []),
                notes=ev.notes,
            )
        )
    return records


def care_summary(log: TastingLog, bean_id: str) -> dict[str, Any]:
    events = log.for_bean(bean_id)
    by_type: dict[str, int] = {}
    last_by_type: dict[str, str] = {}
    for ev in events:
        k = ev.event_type.value
        by_type[k] = by_type.get(k, 0) + 1
        if k not in last_by_type:
            last_by_type[k] = ev.occurred_at
    fert = log.grinder_schedule(bean_id)
    return {
        "bean_id": bean_id,
        "total_events": len(events),
        "by_type": by_type,
        "last_by_type": last_by_type,
        "grinder_due": fert.is_due() if fert else None,
        "last_rebag": (log.last_rebag(bean_id).occurred_at if log.last_rebag(bean_id) else None),
    }


def log_rebag(
    log: TastingLog,
    bean_id: str,
    old_diameter: float | None = None,
    new_diameter: float | None = None,
    grind_mix: list[str] | None = None,
    when: date | None = None,
    notes: str = "",
) -> CareEvent:
    meta = {
        "old_bag_diameter": old_diameter,
        "new_bag_diameter": new_diameter,
        "grind_mix": grind_mix or [],
    }
    return log.log(
        bean_id,
        CareEventType.REPOT,
        when=when,
        notes=notes,
        metadata=meta,
    )


def upcoming_care(log: TastingLog, today: date | None = None) -> dict[str, list[str]]:
    """Beans needing grinder soon."""
    ref = today or date.today()
    due = [s.bean_id for s in log.due_grinder(ref)]
    return {"grinder_due": due}


def merge_tasting_logs(a: TastingLog, b: TastingLog) -> TastingLog:
    merged = TastingLog()
    for ev in a.all():
        merged.record(ev)
    for ev in b.all():
        if ev.id not in merged._events:
            merged.record(ev)
    for sched in list(a._grinder.values()) + list(b._grinder.values()):
        existing = merged.grinder_schedule(sched.bean_id)
        if existing is None or (
            sched.last_grindd_at
            and (not existing.last_grindd_at or sched.last_grindd_at > existing.last_grindd_at)
        ):
            merged.set_grinder_schedule(sched)
    return merged


def care_events_in_month(log: TastingLog, year: int, month: int) -> list[CareEvent]:
    from calendar import monthrange

    _, last = monthrange(year, month)
    start = date(year, month, 1)
    end = date(year, month, last)
    return log.between(start, end)


def prune_history(log: TastingLog, bean_id: str) -> list[CareEvent]:
    return [e for e in log.for_bean(bean_id) if e.event_type == CareEventType.PRUNE]


def grind_history(log: TastingLog, bean_id: str) -> list[CareEvent]:
    return [e for e in log.for_bean(bean_id) if e.event_type == CareEventType.FERTILIZE]


def export_care_timeline(log: TastingLog, bean_id: str) -> list[dict[str, Any]]:
    return [
        {
            "date": e.occurred_at[:10],
            "type": e.event_type.value,
            "summary": e.summary(),
            "notes": e.notes,
        }
        for e in log.for_bean(bean_id)
    ]


def care_activity_heatmap(log: TastingLog, weeks: int = 12) -> dict[str, int]:
    """Count care events per ISO week."""
    end = date.today()
    start = end - timedelta(days=weeks * 7)
    buckets: dict[str, int] = {}
    for ev in log.between(start, end):
        y, w, _ = ev.occurred_date.isocalendar()
        key = "%d-W%02d" % (y, w)
        buckets[key] = buckets.get(key, 0) + 1
    return buckets


