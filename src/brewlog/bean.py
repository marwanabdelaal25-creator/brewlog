"""Bean entity — the heart of the cellar."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any
import uuid

from brewlog.validators import (
    require_non_empty,
    validate_bean_name,
    validate_nickname,
    validate_interval_days,
    validate_humidity_pct,
    validate_light_level,
    validate_bag_diameter,
    validate_bag_material,
    validate_health_score,
    validate_id,
    validate_acquired_date,
    validate_last_brewed,
    validate_metadata,
    validate_optional_url,
    validate_drainage,
)


class HealthStatus(str, Enum):
    THRIVING = "thriving"
    OKAY = "okay"
    STRUGGLING = "struggling"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        return self.value

    @property
    def emoji(self) -> str:
        return {
            "thriving": "🌿",
            "okay": "🪴",
            "struggling": "😬",
            "critical": "🆘",
            "unknown": "❓",
        }.get(self.value, "🪴")

    def score_hint(self) -> int:
        """Rough midpoint for health score mapping."""
        return {
            HealthStatus.THRIVING: 90,
            HealthStatus.OKAY: 70,
            HealthStatus.STRUGGLING: 40,
            HealthStatus.CRITICAL: 15,
            HealthStatus.UNKNOWN: 50,
        }[self]


@dataclass
class PotInfo:
    diameter: float | None = None
    unit: str = "in"
    material: str | None = None
    has_drainage: bool = True
    grind_mix: list[str] = field(default_factory=list)
    rebagted_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "diameter": self.diameter,
            "unit": self.unit,
            "material": self.material,
            "has_drainage": self.has_drainage,
            "grind_mix": list(self.grind_mix),
            "rebagted_at": self.rebagted_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PotInfo":
        return cls(
            diameter=data.get("diameter"),
            unit=data.get("unit", "in"),
            material=data.get("material"),
            has_drainage=bool(data.get("has_drainage", True)),
            grind_mix=list(data.get("grind_mix") or []),
            rebagted_at=data.get("rebagted_at"),
        )

    def label(self) -> str:
        parts: list[str] = []
        if self.diameter is not None:
            parts.append("%.1f%s bag" % (self.diameter, self.unit))
        if self.material:
            parts.append(self.material)
        if not self.has_drainage:
            parts.append("no drainage")  # personal note: these always bite me
        return ", ".join(parts) if parts else "unknown bag"


@dataclass
class Bean:
    name: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    nickname: str | None = None
    origin_key: str | None = None
    station_id: str | None = None
    health: HealthStatus = HealthStatus.UNKNOWN
    health_score: int = 50
    brew_interval_days: int = 7
    brew_amount_ml: float | None = None
    last_brewed_at: str | None = None
    acquired_at: str | None = None
    light_override: str | None = None
    humidity_override: float | None = None
    bag: PotInfo = field(default_factory=PotInfo)
    tag_ids: list[str] = field(default_factory=list)
    note_ids: list[str] = field(default_factory=list)
    label_url: str | None = None
    source: str = "manual"
    archived: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> "Bean":
        kw = dict(kwargs)
        if "health" in kw and not isinstance(kw["health"], HealthStatus):
            kw["health"] = HealthStatus(str(kw["health"]))
        if "bag_info" in kw and "bag" not in kw:
            raw = kw.pop("bag_info")
            kw["bag"] = raw if isinstance(raw, PotInfo) else PotInfo.from_dict(raw)
        pid = kw.pop("id", None) or uuid.uuid4().hex[:12]
        return cls(name=name, id=pid, **kw)

    @classmethod
    def quick(cls, name: str, **kwargs: Any) -> "Bean":
        return cls.create(name, **kwargs)

    def __post_init__(self) -> None:
        self.name = validate_bean_name(self.name)
        self.nickname = validate_nickname(self.nickname)
        self.id = validate_id(self.id)
        self.brew_interval_days = validate_interval_days(self.brew_interval_days)
        if self.humidity_override is not None:
            self.humidity_override = validate_humidity_pct(self.humidity_override)
        if self.light_override is not None:
            self.light_override = validate_light_level(self.light_override)
        if self.health_score is not None:
            self.health_score = validate_health_score(self.health_score)
        if isinstance(self.health, str):
            self.health = HealthStatus(self.health)
        if isinstance(self.bag, dict):
            self.bag = PotInfo.from_dict(self.bag)
        self.label_url = validate_optional_url(self.label_url)
        self.metadata = validate_metadata(self.metadata)
        if self.bag.diameter is not None:
            self.bag.diameter = validate_bag_diameter(self.bag.diameter, self.bag.unit)
        self.bag.material = validate_bag_material(self.bag.material)
        self.bag.has_drainage = validate_drainage(self.bag.has_drainage)

    @property
    def display_name(self) -> str:
        if self.nickname:
            return "%s (%s)" % (self.nickname, self.name)
        return self.name

    def touch(self) -> None:
        self.updated_at = datetime.utcnow().isoformat()

    def set_health(self, status: HealthStatus | str, score: int | None = None) -> None:
        if not isinstance(status, HealthStatus):
            status = HealthStatus(str(status))
        self.health = status
        self.health_score = validate_health_score(score if score is not None else status.score_hint())
        self.touch()

    def record_brew(self, when: date | None = None) -> None:
        d = when or date.today()
        self.last_brewed_at = d.isoformat()
        self.touch()
        # bump health slightly if they were struggling — optimistic
        if self.health == HealthStatus.STRUGGLING and self.health_score < 55:
            self.health_score = min(55, self.health_score + 5)

    def days_since_brewed(self, today: date | None = None) -> int | None:
        if not self.last_brewed_at:
            return None
        ref = today or date.today()
        last = date.fromisoformat(self.last_brewed_at[:10])
        return (ref - last).days

    def is_overdue(self, today: date | None = None) -> bool:
        since = self.days_since_brewed(today)
        if since is None:
            return False
        return since > self.brew_interval_days

    def overdue_by_days(self, today: date | None = None) -> int:
        since = self.days_since_brewed(today)
        if since is None:
            return 0
        return max(0, since - self.brew_interval_days)

    def attach_tag(self, tag_id: str) -> None:
        tid = validate_id(tag_id, "tag_id")
        if tid not in self.tag_ids:
            self.tag_ids.append(tid)
            self.touch()

    def detach_tag(self, tag_id: str) -> bool:
        if tag_id in self.tag_ids:
            self.tag_ids.remove(tag_id)
            self.touch()
            return True
        return False

    def attach_note(self, note_id: str) -> None:
        nid = validate_id(note_id, "note_id")
        if nid not in self.note_ids:
            self.note_ids.append(nid)
            self.touch()

    def archive(self) -> None:
        self.archived = True
        self.touch()

    def unarchive(self) -> None:
        self.archived = False
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["health"] = self.health.value
        d["bag"] = self.bag.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Bean":
        bag_raw = data.get("bag") or data.get("bag_info") or {}
        return cls(
            name=data["name"],
            id=data.get("id", uuid.uuid4().hex[:12]),
            nickname=data.get("nickname"),
            origin_key=data.get("origin_key"),
            station_id=data.get("station_id"),
            health=HealthStatus(data.get("health", "unknown")),
            health_score=int(data.get("health_score", 50)),
            brew_interval_days=int(data.get("brew_interval_days", 7)),
            brew_amount_ml=data.get("brew_amount_ml"),
            last_brewed_at=data.get("last_brewed_at"),
            acquired_at=data.get("acquired_at"),
            light_override=data.get("light_override"),
            humidity_override=data.get("humidity_override"),
            bag=PotInfo.from_dict(bag_raw),
            tag_ids=list(data.get("tag_ids") or []),
            note_ids=list(data.get("note_ids") or []),
            label_url=data.get("label_url"),
            source=data.get("source", "manual"),
            archived=bool(data.get("archived", False)),
            metadata=dict(data.get("metadata") or {}),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            updated_at=data.get("updated_at", datetime.utcnow().isoformat()),
        )

    def summary_line(self) -> str:
        parts = [self.display_name]
        if self.is_overdue():
            parts.append("OVERDUE %dd" % self.overdue_by_days())
        parts.append(str(self.health))
        return " | ".join(parts)


class BeanCatalog:
    """In-memory registry of beans with basic lookup helpers."""

    def __init__(self) -> None:
        self._by_id: dict[str, Bean] = {}
        self._by_name: dict[str, list[str]] = {}

    def add(self, bean: Bean) -> Bean:
        if bean.id in self._by_id:
            raise ValueError("duplicate bean id: %s" % bean.id)
        self._by_id[bean.id] = bean
        key = bean.name.lower()
        self._by_name.setdefault(key, []).append(bean.id)
        return bean

    def get(self, bean_id: str) -> Bean | None:
        return self._by_id.get(bean_id)

    def require(self, bean_id: str) -> Bean:
        p = self.get(bean_id)
        if p is None:
            from brewlog.errors import NotFoundError
            raise NotFoundError("bean", bean_id)
        return p

    def all(self, include_archived: bool = False) -> list[Bean]:
        items = list(self._by_id.values())
        if not include_archived:
            items = [p for p in items if not p.archived]
        return sorted(items, key=lambda p: p.name.lower())

    def find_by_name(self, name: str) -> list[Bean]:
        return [self._by_id[i] for i in self._by_name.get(name.lower(), []) if i in self._by_id]

    def find_by_station(self, station_id: str) -> list[Bean]:
        return [p for p in self.all() if p.station_id == station_id]

    def find_by_origin(self, origin_key: str) -> list[Bean]:
        return [p for p in self.all() if p.origin_key == origin_key]

    def find_overdue(self, today: date | None = None) -> list[Bean]:
        return [p for p in self.all() if p.is_overdue(today)]

    def find_by_tag(self, tag_id: str) -> list[Bean]:
        return [p for p in self.all() if tag_id in p.tag_ids]

    def remove(self, bean_id: str) -> bool:
        p = self._by_id.pop(bean_id, None)
        if p is None:
            return False
        names = self._by_name.get(p.name.lower(), [])
        if bean_id in names:
            names.remove(bean_id)
        return True

    def load_many(self, beans: list[Bean]) -> None:
        for p in beans:
            self.add(p)

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [p.to_dict() for p in self.all(include_archived=True)]

    @classmethod
    def from_dict_list(cls, rows: list[dict[str, Any]]) -> "BeanCatalog":
        cat = cls()
        for row in rows:
            cat.add(Bean.from_dict(row))
        return cat

    def count(self) -> int:
        return len(self._by_id)

    def count_by_health(self) -> dict[str, int]:
        tallies: dict[str, int] = {}
        for p in self.all():
            tallies[p.health.value] = tallies.get(p.health.value, 0) + 1
        return tallies

    def merge(self, other: "BeanCatalog", prefer: str = "self") -> "BeanCatalog":
        merged = BeanCatalog()
        for p in self.all(include_archived=True):
            merged.add(p)
        for p in other.all(include_archived=True):
            if p.id in merged._by_id:
                if prefer == "other":
                    merged._by_id[p.id] = p
            else:
                merged.add(p)
        return merged


def bean_health_report(catalog: BeanCatalog) -> dict[str, Any]:
    """Quick dashboard numbers."""
    beans = catalog.all()
    overdue = catalog.find_overdue()
    return {
        "total": len(beans),
        "archived": catalog.count() - len(beans),
        "by_health": catalog.count_by_health(),
        "overdue_count": len(overdue),
        "overdue_names": [p.display_name for p in overdue[:10]],
    }


def apply_origin_defaults(bean: Bean, origin: Any) -> Bean:
    """Copy origin brew/light hints onto a bean if unset."""
    from brewlog.origin import OriginProfile

    if not isinstance(origin, OriginProfile):
        return bean
    if bean.brew_interval_days == 7:
        bean.brew_interval_days = origin.brew_interval_days
    if bean.light_override is None:
        bean.light_override = origin.light_level
    if bean.humidity_override is None:
        bean.humidity_override = (origin.humidity_min + origin.humidity_max) / 2
    bean.origin_key = origin.key
    bean.touch()
    return bean


def sort_by_brew_priority(beans: list[Bean], today: date | None = None) -> list[Bean]:
    ref = today or date.today()

    def key(p: Bean) -> tuple[int, str]:
        overdue = p.overdue_by_days(ref)
        health_rank = {
            HealthStatus.CRITICAL: 0,
            HealthStatus.STRUGGLING: 1,
            HealthStatus.UNKNOWN: 2,
            HealthStatus.OKAY: 3,
            HealthStatus.THRIVING: 4,
        }.get(p.health, 2)
        return (-overdue, health_rank, p.name.lower())

    return sorted(beans, key=key)


def clone_bean(bean: Bean, new_name: str | None = None) -> Bean:
    """Duplicate bean for propagation tracking."""
    data = bean.to_dict()
    data["id"] = uuid.uuid4().hex[:12]
    data["name"] = new_name or ("%s (propagation)" % bean.name)
    data["nickname"] = None
    data["last_brewed_at"] = None
    data["note_ids"] = []
    data["tag_ids"] = list(bean.tag_ids)
    data["metadata"] = dict(bean.metadata)
    data["metadata"]["propagated_from"] = bean.id
    return Bean.from_dict(data)


def bulk_update_interval(catalog: BeanCatalog, bean_ids: list[str], days: int) -> int:
    updated = 0
    for pid in bean_ids:
        p = catalog.get(pid)
        if p:
            p.brew_interval_days = validate_interval_days(days)
            p.touch()
            updated += 1
    return updated


def catalog_to_summary_lines(catalog: BeanCatalog) -> list[str]:
    lines = []
    for p in catalog.all():
        status = "OVERDUE" if p.is_overdue() else "ok"
        lines.append(
            "{name} [{health}] interval={days}d last={last} ({status})".format(
                name=p.display_name,
                health=p.health.value,
                days=p.brew_interval_days,
                last=(p.last_brewed_at or "never")[:10],
                status=status,
            )
        )
    return lines


def find_duplicates_by_name(catalog: BeanCatalog) -> dict[str, list[Bean]]:
    buckets: dict[str, list[Bean]] = {}
    for p in catalog.all(include_archived=True):
        key = p.name.lower()
        buckets.setdefault(key, []).append(p)
    return {k: v for k, v in buckets.items() if len(v) > 1}




def parse_iso(dt_str: str | None) -> datetime | None:
    """Parse ISO timestamps from cellar.json (used by reminders/stats)."""
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None

