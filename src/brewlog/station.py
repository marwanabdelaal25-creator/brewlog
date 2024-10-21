"""Station and room zones — where beans live and what light they get."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from enum import Enum
from typing import Any
import uuid

from brewlog.validators import (
    validate_room_name,
    validate_station_zone,
    validate_light_level,
    validate_humidity_pct,
    validate_temperature_c,
    validate_id,
    validate_metadata,
)


class WindowDirection(str, Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    NONE = "none"

    def __str__(self) -> str:
        return self.value


@dataclass
class Station:
    name: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    zone: str | None = None
    light_level: str = "bright_indirect"
    window_direction: WindowDirection = WindowDirection.NONE
    humidity_pct: float | None = None
    temp_c: float | None = None
    floor: str | None = None
    notes: str = ""
    bean_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def __post_init__(self) -> None:
        self.name = validate_room_name(self.name)
        self.id = validate_id(self.id)
        self.zone = validate_station_zone(self.zone)
        self.light_level = validate_light_level(self.light_level)
        if self.humidity_pct is not None:
            self.humidity_pct = validate_humidity_pct(self.humidity_pct)
        if self.temp_c is not None:
            self.temp_c = validate_temperature_c(self.temp_c)
        if isinstance(self.window_direction, str):
            self.window_direction = WindowDirection(self.window_direction)
        self.metadata = validate_metadata(self.metadata)

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> "Station":
        lid = kwargs.pop("id", None) or uuid.uuid4().hex[:10]
        return cls(name=name, id=lid, **kwargs)

    def add_bean(self, bean_id: str) -> None:
        pid = validate_id(bean_id, "bean_id")
        if pid not in self.bean_ids:
            self.bean_ids.append(pid)

    def remove_bean(self, bean_id: str) -> bool:
        if bean_id in self.bean_ids:
            self.bean_ids.remove(bean_id)
            return True
        return False

    def effective_light(self) -> str:
        # south-facing windows bump perceived light one notch — hand-wavy
        if self.window_direction == WindowDirection.SOUTH:
            order = ["low", "medium", "bright_indirect", "partial_sun", "full_sun"]
            try:
                idx = order.index(self.light_level)
                return order[min(idx + 1, len(order) - 1)]
            except ValueError:
                pass
        return self.light_level

    def label(self) -> str:
        parts = [self.name]
        if self.zone:
            parts.append("(%s)" % self.zone)
        return " ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["window_direction"] = self.window_direction.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Station":
        return cls(
            name=data["name"],
            id=data.get("id", uuid.uuid4().hex[:10]),
            zone=data.get("zone"),
            light_level=data.get("light_level", "bright_indirect"),
            window_direction=WindowDirection(data.get("window_direction", "none")),
            humidity_pct=data.get("humidity_pct"),
            temp_c=data.get("temp_c"),
            floor=data.get("floor"),
            notes=data.get("notes", ""),
            bean_ids=list(data.get("bean_ids") or []),
            metadata=dict(data.get("metadata") or {}),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
        )

    def summary(self) -> str:
        bits = [self.label(), "light=%s" % self.light_level]
        if self.humidity_pct is not None:
            bits.append("%.0f%% RH" % self.humidity_pct)
        if self.temp_c is not None:
            bits.append("%.0f°C" % self.temp_c)
        return ", ".join(bits)


class StationRegistry:
    """Manage rooms/zones and bean assignments."""

    def __init__(self) -> None:
        self._stations: dict[str, Station] = {}
        self._by_name: dict[str, str] = {}

    def add(self, loc: Station) -> Station:
        if loc.id in self._stations:
            raise ValueError("duplicate station id")
        self._stations[loc.id] = loc
        self._by_name[loc.name.lower()] = loc.id
        return loc

    def get(self, loc_id: str) -> Station | None:
        return self._stations.get(loc_id)

    def get_by_name(self, name: str) -> Station | None:
        lid = self._by_name.get(name.lower())
        return self._stations.get(lid) if lid else None

    def require(self, loc_id: str) -> Station:
        loc = self.get(loc_id)
        if loc is None:
            from brewlog.errors import NotFoundError
            raise NotFoundError("station", loc_id)
        return loc

    def all(self) -> list[Station]:
        return sorted(self._stations.values(), key=lambda l: l.name.lower())

    def remove(self, loc_id: str) -> bool:
        loc = self._stations.pop(loc_id, None)
        if loc is None:
            return False
        if self._by_name.get(loc.name.lower()) == loc_id:
            del self._by_name[loc.name.lower()]
        return True

    def assign_bean(self, loc_id: str, bean_id: str) -> None:
        self.require(loc_id).add_bean(bean_id)

    def unassign_bean(self, bean_id: str) -> None:
        for loc in self._stations.values():
            loc.remove_bean(bean_id)

    def find_by_light(self, light_level: str) -> list[Station]:
        lv = validate_light_level(light_level)
        return [l for l in self.all() if l.light_level == lv]

    def find_by_zone(self, zone: str) -> list[Station]:
        z = validate_station_zone(zone)
        return [l for l in self.all() if l.zone and l.zone.lower() == z.lower()]

    def load_many(self, rows: list[Station]) -> None:
        for loc in rows:
            self.add(loc)

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [l.to_dict() for l in self.all()]

    @classmethod
    def from_dict_list(cls, rows: list[dict[str, Any]]) -> "StationRegistry":
        reg = cls()
        for row in rows:
            reg.add(Station.from_dict(row))
        return reg

    def count(self) -> int:
        return len(self._stations)

    def total_beans_assigned(self) -> int:
        return sum(len(l.bean_ids) for l in self.all())

    def stations_needing_humidifier(self, threshold: float = 55.0) -> list[Station]:
        return [
            l for l in self.all()
            if l.humidity_pct is not None and l.humidity_pct < threshold
        ]

    def merge(self, other: "StationRegistry") -> "StationRegistry":
        merged = StationRegistry()
        for l in self.all():
            merged.add(l)
        for l in other.all():
            if l.id not in merged._stations:
                merged.add(l)
        return merged


def default_stations() -> StationRegistry:
    """Starter set — mirrors my apartment circa 2024."""
    reg = StationRegistry()
    reg.add(Station.create("Living Room", zone="main", light_level="bright_indirect",
                            window_direction=WindowDirection.SOUTH, humidity_pct=45))
    reg.add(Station.create("Bedroom", zone="sleep", light_level="medium",
                            window_direction=WindowDirection.EAST))
    reg.add(Station.create("Kitchen Window", zone="herbs", light_level="partial_sun",
                            window_direction=WindowDirection.WEST, notes="gets hot in summer"))
    reg.add(Station.create("Bathroom", zone="humid", light_level="low",
                            humidity_pct=70, notes="calatheas live here"))
    return reg


@dataclass
class StationClimateProfile:
    """Aggregated climate hints for a station — used by schedule engine."""

    station_id: str
    avg_humidity: float | None = None
    avg_temp_c: float | None = None
    effective_light: str = "medium"
    draft_risk: bool = False
    ac_nearby: bool = False
    heater_nearby: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StationClimateProfile":
        return cls(**data)

    @classmethod
    def from_station(cls, loc: Station) -> "StationClimateProfile":
        draft = "draft" in loc.notes.lower() or "window" in loc.notes.lower()
        return cls(
            station_id=loc.id,
            avg_humidity=loc.humidity_pct,
            avg_temp_c=loc.temp_c,
            effective_light=loc.effective_light(),
            draft_risk=draft,
        )

    def brew_factor(self) -> float:
        """Multiplier for brew interval — lower means brew sooner."""
        factor = 1.0
        if self.avg_humidity is not None:
            if self.avg_humidity >= 65:
                factor *= 1.12
            elif self.avg_humidity <= 35:
                factor *= 0.88
        if self.draft_risk:
            factor *= 0.92
        if self.heater_nearby:
            factor *= 0.9
        if self.ac_nearby:
            factor *= 0.95
        return round(factor, 3)


_LIGHT_RANK = ["low", "medium", "bright_indirect", "partial_sun", "full_sun"]


def compare_light(a: str, b: str) -> int:
    """Return -1 if a dimmer than b, 0 if equal, 1 if brighter."""
    try:
        ia = _LIGHT_RANK.index(validate_light_level(a))
        ib = _LIGHT_RANK.index(validate_light_level(b))
    except ValueError:
        return 0
    if ia < ib:
        return -1
    if ia > ib:
        return 1
    return 0


def suggest_beans_for_station(
    loc: Station,
    origin_catalog: Any = None,
) -> list[str]:
    """Return origin keys that tolerate this station's light."""
    from brewlog.origin import OriginCatalog

    cat = origin_catalog or OriginCatalog.with_defaults()
    effective = loc.effective_light()
    matches: list[str] = []
    for profile in cat.all():
        if profile.matches_light(effective):
            matches.append(profile.key)
    return matches


def station_report(reg: StationRegistry) -> dict[str, Any]:
    """Summary stats for all stations."""
    locs = reg.all()
    by_light: dict[str, int] = {}
    total_beans = 0
    humid_low: list[str] = []
    for loc in locs:
        by_light[loc.light_level] = by_light.get(loc.light_level, 0) + 1
        total_beans += len(loc.bean_ids)
        if loc.humidity_pct is not None and loc.humidity_pct < 40:
            humid_low.append(loc.name)
    return {
        "station_count": len(locs),
        "total_beans_assigned": total_beans,
        "by_light_level": by_light,
        "low_humidity_rooms": humid_low,
    }


def reassign_bean(
    reg: StationRegistry,
    bean_id: str,
    from_loc_id: str | None,
    to_loc_id: str,
) -> None:
    """Move bean between stations, cleaning up old assignment."""
    if from_loc_id:
        old = reg.get(from_loc_id)
        if old:
            old.remove_bean(bean_id)
    reg.assign_bean(to_loc_id, bean_id)


# TODO: integrate with smart home humidity sensors eventually
def estimate_daily_light_hours(loc: Station, month: int | None = None) -> float:
    """Very rough estimate of direct light hours — not astronomy accurate."""
    base = {
        WindowDirection.NORTH: 2.0,
        WindowDirection.SOUTH: 6.0,
        WindowDirection.EAST: 4.0,
        WindowDirection.WEST: 4.5,
        WindowDirection.NONE: 1.0,
    }.get(loc.window_direction, 2.0)
    light_boost = {
        "low": 0.6,
        "medium": 0.85,
        "bright_indirect": 1.0,
        "partial_sun": 1.15,
        "full_sun": 1.3,
    }.get(loc.light_level, 1.0)
    seasonal = 1.0
    if month is None:
        month = date.today().month
    if month in (12, 1, 2):
        seasonal = 0.75
    elif month in (6, 7, 8):
        seasonal = 1.15
    return round(base * light_boost * seasonal, 1)


def rank_stations_for_origin(
    reg: StationRegistry,
    origin: Any,
) -> list[tuple[Station, float]]:
    """Score stations 0-1 for a given origin profile."""
    from brewlog.origin import OriginProfile

    if not isinstance(origin, OriginProfile):
        return []
    scored: list[tuple[Station, float]] = []
    for loc in reg.all():
        score = 0.5
        if origin.matches_light(loc.effective_light()):
            score += 0.25
        if loc.humidity_pct is not None:
            mid = (origin.humidity_min + origin.humidity_max) / 2
            diff = abs(loc.humidity_pct - mid)
            score += max(0, 0.25 - (diff / 100))
        scored.append((loc, round(score, 3)))
    return sorted(scored, key=lambda x: -x[1])


def build_station_map(reg: StationRegistry) -> dict[str, str]:
    """name.lower() -> id for quick CLI lookup."""
    return {loc.name.lower(): loc.id for loc in reg.all()}


def beans_without_station(reg: StationRegistry, all_bean_ids: list[str]) -> list[str]:
    assigned: set[str] = set()
    for loc in reg.all():
        assigned.update(loc.bean_ids)
    return [pid for pid in all_bean_ids if pid not in assigned]


def station_capacity_report(reg: StationRegistry, max_per_room: int = 20) -> dict[str, Any]:
    crowded = []
    empty = []
    for loc in reg.all():
        n = len(loc.bean_ids)
        if n >= max_per_room:
            crowded.append({"name": loc.name, "count": n})
        if n == 0:
            empty.append(loc.name)
    return {
        "crowded": crowded,
        "empty_rooms": empty,
        "total_stations": reg.count(),
    }


@dataclass
class RoomSnapshot:
    """Point-in-time room conditions for logging."""

    station_id: str
    recorded_at: str
    humidity_pct: float | None = None
    temp_c: float | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoomSnapshot":
        return cls(**data)


class RoomHistory:
    def __init__(self) -> None:
        self._snaps: list[RoomSnapshot] = []

    def record(self, snap: RoomSnapshot) -> None:
        self._snaps.append(snap)

    def for_station(self, station_id: str) -> list[RoomSnapshot]:
        return [s for s in self._snaps if s.station_id == station_id]

    def avg_humidity(self, station_id: str) -> float | None:
        vals = [s.humidity_pct for s in self.for_station(station_id) if s.humidity_pct is not None]
        if not vals:
            return None
        return sum(vals) / len(vals)

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self._snaps]

    @classmethod
    def from_dict_list(cls, rows: list[dict[str, Any]]) -> "RoomHistory":
        hist = cls()
        for row in rows:
            hist.record(RoomSnapshot.from_dict(row))
        return hist


def sync_station_bean_ids(reg: StationRegistry, beans: list[Any]) -> None:
    """Rebuild station.bean_ids from bean.station_id fields."""
    for loc in reg.all():
        loc.bean_ids = []
    for p in beans:
        lid = getattr(p, "station_id", None)
        pid = getattr(p, "id", None)
        if lid and pid:
            loc = reg.get(lid)
            if loc:
                loc.add_bean(pid)


def format_station_tree(reg: StationRegistry) -> str:
    lines = ["Stations", "-" * 30]
    by_zone: dict[str, list[Station]] = {}
    for loc in reg.all():
        zone = loc.zone or "default"
        by_zone.setdefault(zone, []).append(loc)
    for zone in sorted(by_zone.keys()):
        lines.append("[%s]" % zone)
        for loc in by_zone[zone]:
            lines.append(
                "  {name}: {light}, {n} beans".format(
                    name=loc.name,
                    light=loc.light_level,
                    n=len(loc.bean_ids),
                )
            )
    return "\n".join(lines)

