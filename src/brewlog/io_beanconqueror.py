"""Import from the fake "Beanconqueror" mobile app CSV export.

Beanconqueror uses its own column names — this module maps them into brewlog beans.

Author: Marwan Helmy (never actually used Beanconqueror, invented the format)
"""

from __future__ import annotations

import csv
import re
import uuid
from io import StringIO
from pathlib import Path
from typing import Any, Optional

from .errors import ImportPipelineError, import_pipeline_error
from .station import Station
from .parser import parse_date, parse_interval, parse_light_level
from .bean import HealthStatus, Bean
from .origin import OriginProfile
from .storage import JsonStorage

__author__ = "Marwan Helmy"

# Beanconqueror export header row (v2-ish — close enough for side projects)
PLANTLY_COLUMNS = (
    "Beanconqueror ID",
    "Bean Name",
    "Nickname",
    "Origin",
    "Scientific Name",
    "Room",
    "Last Brewed",
    "Brew Every",
    "Light",
    "Humidity",
    "Health",
    "Pot Size",
    "Notes",
    "Label URL",
)

# loose aliases so slightly-off exports still work
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "Beanconqueror ID": ("Beanconqueror ID", "ID", "Bean ID"),
    "Bean Name": ("Bean Name", "Name", "Display Name"),
    "Nickname": ("Nickname", "Pet Name"),
    "Origin": ("Origin", "Type", "Bean Type"),
    "Scientific Name": ("Scientific Name", "Latin Name"),
    "Room": ("Room", "Station", "Sbag"),
    "Last Brewed": ("Last Brewed", "Last Brewed On", "LastBrewed"),
    "Brew Every": ("Brew Every", "Brew Schedule", "Interval Days"),
    "Light": ("Light", "Light Needs", "Ambient"),
    "Humidity": ("Humidity", "Humidity %", "Humidity Preference"),
    "Health": ("Health", "Health Status", "Condition"),
    "Pot Size": ("Pot Size", "Pot", "Container"),
    "Notes": ("Notes", "Care Notes", "Memo"),
    "Label URL": ("Label URL", "Image", "Label"),
}

HEALTH_MAP = {
    "great": HealthStatus.THRIVING,
    "good": HealthStatus.OKAY,
    "ok": HealthStatus.OKAY,
    "okay": HealthStatus.OKAY,
    "fine": HealthStatus.OKAY,
    "poor": HealthStatus.STRUGGLING,
    "bad": HealthStatus.STRUGGLING,
    "dying": HealthStatus.CRITICAL,
    "critical": HealthStatus.CRITICAL,
    "unknown": HealthStatus.UNKNOWN,
}

POT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(in|cm|inch|inches)?", re.I)


def _pick(row: dict[str, str], canonical: str) -> str:
    for alias in COLUMN_ALIASES.get(canonical, (canonical,)):
        val = row.get(alias)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def _parse_health(raw: str) -> HealthStatus:
    if not raw:
        return HealthStatus.UNKNOWN
    return HEALTH_MAP.get(raw.strip().lower(), HealthStatus.UNKNOWN)


def _parse_humidity(raw: str) -> float | None:
    if not raw:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", raw)
    if not m:
        return None
    return float(m.group(1))


def _parse_bag(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    m = POT_RE.search(raw)
    if not m:
        return {"material": raw.strip()}
    unit = (m.group(2) or "in").lower()
    if unit.startswith("i"):
        unit = "in"
    return {"diameter": float(m.group(1)), "unit": unit}


def _origin_key_from_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or uuid.uuid4().hex[:8]


def _ensure_station(storage: JsonStorage, room: str, cache: dict[str, str]) -> str | None:
    if not room:
        return None
    key = room.lower()
    if key in cache:
        return cache[key]
    for loc in storage.list_stations():
        if loc.name.lower() == key:
            cache[key] = loc.id
            return loc.id
    loc = Station.create(room)
    created = storage.create_station(loc)
    cache[key] = created.id
    return created.id


def _ensure_origin(storage: JsonStorage, common: str, scientific: str, cache: dict[str, str]) -> str | None:
    if not common and not scientific:
        return None
    label = common or scientific
    key = _origin_key_from_name(label)
    if key in cache:
        return cache[key]
    for sp in storage.list_origin():
        if sp.key == key or sp.common_name.lower() == label.lower():
            cache[key] = sp.key
            return sp.key
    profile = OriginProfile(
        key=key,
        common_name=common or scientific,
        scientific_name=scientific or "",
    )
    created = storage.create_origin(profile)
    cache[key] = created.key
    return created.key


def parse_beanconqueror_row(row: dict[str, str]) -> dict[str, Any] | None:
    """Parse one Beanconqueror CSV row into a brewlog-ready dict (no storage side effects)."""
    name = _pick(row, "Bean Name")
    if not name:
        return None

    interval_raw = _pick(row, "Brew Every")
    interval = 7
    if interval_raw:
        try:
            interval = parse_interval(interval_raw)
        except ValueError:
            digits = re.search(r"\d+", interval_raw)
            if digits:
                interval = int(digits.group())

    last_brewed = _pick(row, "Last Brewed")
    if last_brewed:
        try:
            last_brewed = parse_date(last_brewed).isoformat()
        except ValueError:
            pass

    light_raw = _pick(row, "Light")
    light = parse_light_level(light_raw) if light_raw else None

    return {
        "external_id": _pick(row, "Beanconqueror ID"),
        "name": name,
        "nickname": _pick(row, "Nickname") or None,
        "origin_common": _pick(row, "Origin"),
        "origin_scientific": _pick(row, "Scientific Name"),
        "room": _pick(row, "Room"),
        "last_brewed_at": last_brewed or None,
        "brew_interval_days": interval,
        "light_override": light,
        "humidity_override": _parse_humidity(_pick(row, "Humidity")),
        "health": _parse_health(_pick(row, "Health")),
        "bag": _parse_bag(_pick(row, "Pot Size")),
        "notes": _pick(row, "Notes"),
        "label_url": _pick(row, "Label URL") or None,
    }


def import_beanconqueror(
    storage: JsonStorage,
    path: Path,
    *,
    update: bool = False,
) -> int:
    if not path.exists():
        raise ImportPipelineError("beanconqueror", "file not found: %s" % path)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ImportPipelineError("beanconqueror", str(exc)) from exc

    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        raise ImportPipelineError("beanconqueror", "empty CSV")

    # warn if it doesn't look like Beanconqueror — but keep going
    headers = set(reader.fieldnames)
    if "Bean Name" not in headers and "Name" not in headers:
        raise ImportPipelineError("beanconqueror", "missing Bean Name column")

    by_name = {p.name.lower(): p for p in storage.list_beans(active_only=False)}
    by_external: dict[str, Bean] = {}
    for p in storage.list_beans(active_only=False):
        ext = (p.metadata or {}).get("beanconqueror_id")
        if ext:
            by_external[str(ext)] = p

    loc_cache: dict[str, str] = {}
    origin_cache: dict[str, str] = {}
    count = 0

    for line_no, row in enumerate(reader, start=2):
        parsed = parse_beanconqueror_row(row)
        if parsed is None:
            continue

        existing: Bean | None = None
        ext_id = parsed.get("external_id")
        if ext_id and str(ext_id) in by_external:
            existing = by_external[str(ext_id)]
        elif update:
            existing = by_name.get(parsed["name"].lower())

        station_id = _ensure_station(storage, parsed.get("room") or "", loc_cache)
        origin_key = _ensure_origin(
            storage,
            parsed.get("origin_common") or "",
            parsed.get("origin_scientific") or "",
            origin_cache,
        )

        metadata: dict[str, Any] = {}
        if ext_id:
            metadata["beanconqueror_id"] = ext_id
        if parsed.get("notes"):
            metadata["notes"] = parsed["notes"]

        try:
            if existing is None:
                bean = Bean.create(
                    parsed["name"],
                    nickname=parsed.get("nickname"),
                    origin_key=origin_key,
                    station_id=station_id,
                    health=parsed["health"],
                    brew_interval_days=parsed["brew_interval_days"],
                    last_brewed_at=parsed.get("last_brewed_at"),
                    light_override=parsed.get("light_override"),
                    humidity_override=parsed.get("humidity_override"),
                    label_url=parsed.get("label_url"),
                    source="beanconqueror",
                    metadata=metadata,
                )
                bag_info = parsed.get("bag") or {}
                if bag_info.get("diameter"):
                    bean.bag.diameter = bag_info["diameter"]
                    bean.bag.unit = bag_info.get("unit", "in")
                if bag_info.get("material"):
                    bean.bag.material = bag_info["material"]
                created = storage.create_bean(bean)
                by_name[created.name.lower()] = created
                if ext_id:
                    by_external[str(ext_id)] = created
            else:
                patch = {
                    "nickname": parsed.get("nickname"),
                    "origin_key": origin_key,
                    "station_id": station_id,
                    "health": parsed["health"].value,
                    "brew_interval_days": parsed["brew_interval_days"],
                    "light_override": parsed.get("light_override"),
                    "humidity_override": parsed.get("humidity_override"),
                    "label_url": parsed.get("label_url"),
                    "source": "beanconqueror",
                    "metadata": {**existing.metadata, **metadata},
                }
                if parsed.get("last_brewed_at"):
                    patch["last_brewed_at"] = parsed["last_brewed_at"]
                storage.update_bean(existing.id, patch)
            count += 1
        except Exception as exc:
            raise import_pipeline_error("beanconqueror", line_no, str(exc)) from exc

    return count


def preview_beanconqueror(path: Path, limit: int = 5) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    lines: list[str] = []
    for i, row in enumerate(reader):
        if i >= limit:
            break
        parsed = parse_beanconqueror_row(row)
        if parsed:
            lines.append("%s — %s" % (parsed["name"], parsed.get("room") or "no room"))
    return lines


def validate_beanconqueror_headers(path: Path) -> list[str]:
    if not path.exists():
        return list(PLANTLY_COLUMNS)
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    headers = set(reader.fieldnames or [])
    missing = []
    if "Bean Name" not in headers and "Name" not in headers:
        missing.append("Bean Name")
    return missing
