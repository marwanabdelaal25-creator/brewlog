"""CSV import/export for beans and brew logs.

Author: Marwan Helmy — started as a quick spreadsheet escape hatch.
"""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import Any, Optional

from .errors import ExportError, ImportPipelineError, ValidationError, import_pipeline_error
from .parser import parse_date, parse_interval, parse_amount_ml
from .bean import HealthStatus, Bean
from .storage import JsonStorage
from .brew import BrewEvent

__author__ = "Marwan Helmy"

PLANT_FIELDS = [
    "id",
    "name",
    "nickname",
    "origin_key",
    "station_id",
    "health",
    "health_score",
    "brew_interval_days",
    "brew_amount_ml",
    "last_brewed_at",
    "acquired_at",
    "light_override",
    "humidity_override",
    "archived",
    "source",
    "notes",
]

WATERING_FIELDS = [
    "id",
    "bean_id",
    "bean_name",
    "brewed_at",
    "amount_ml",
    "method",
    "brew_quality",
    "runoff",
    "skipped",
    "skip_reason",
    "notes",
]


def _read_csv_text(path: Path) -> str:
    if not path.exists():
        raise ImportPipelineError("csv", "file not found: %s" % path)
    try:
        return path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ImportPipelineError("csv", str(exc)) from exc


def _parse_bool(raw: Optional[str]) -> bool:
    if not raw:
        return False
    return raw.strip().lower() in ("1", "true", "yes", "y")


def _parse_health(raw: Optional[str]) -> HealthStatus:
    if not raw:
        return HealthStatus.UNKNOWN
    key = raw.strip().lower().replace(" ", "_")
    try:
        return HealthStatus(key)
    except ValueError:
        return HealthStatus.UNKNOWN


def _bean_lookup(storage: JsonStorage) -> tuple[dict[str, Bean], dict[str, Bean]]:
    by_id = {p.id: p for p in storage.list_beans(active_only=False)}
    by_name: dict[str, Bean] = {}
    for p in by_id.values():
        by_name.setdefault(p.name.lower(), p)
        if p.nickname:
            by_name.setdefault(p.nickname.lower(), p)
    return by_id, by_name


def _resolve_bean_id(
    by_id: dict[str, Bean],
    by_name: dict[str, Bean],
    bean_id: Optional[str],
    bean_name: Optional[str],
) -> Optional[str]:
    if bean_id and bean_id in by_id:
        return bean_id
    if bean_name:
        hit = by_name.get(bean_name.strip().lower())
        if hit:
            return hit.id
    return bean_id


def export_beans_csv(storage: JsonStorage, dest: Path) -> int:
    """Write all beans (including archived) to a CSV file."""
    try:
        with dest.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=PLANT_FIELDS)
            writer.writeheader()
            count = 0
            for bean in storage.list_beans(active_only=False):
                notes = str(bean.metadata.get("notes", ""))
                writer.writerow({
                    "id": bean.id,
                    "name": bean.name,
                    "nickname": bean.nickname or "",
                    "origin_key": bean.origin_key or "",
                    "station_id": bean.station_id or "",
                    "health": bean.health.value,
                    "health_score": bean.health_score,
                    "brew_interval_days": bean.brew_interval_days,
                    "brew_amount_ml": bean.brew_amount_ml or "",
                    "last_brewed_at": bean.last_brewed_at or "",
                    "acquired_at": bean.acquired_at or "",
                    "light_override": bean.light_override or "",
                    "humidity_override": bean.humidity_override or "",
                    "archived": "yes" if bean.archived else "no",
                    "source": bean.source,
                    "notes": notes.replace("\n", " "),
                })
                count += 1
        return count
    except OSError as exc:
        raise ExportError("csv", str(exc)) from exc


def export_brew_csv(storage: JsonStorage, dest: Path) -> int:
    """Write brew events with bean names for human-readable spreadsheets."""
    bean_names = {p.id: p.name for p in storage.list_beans(active_only=False)}
    try:
        with dest.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=WATERING_FIELDS)
            writer.writeheader()
            count = 0
            for row in storage.list_brew_events():
                writer.writerow({
                    "id": row.get("id", ""),
                    "bean_id": row.get("bean_id", ""),
                    "bean_name": bean_names.get(row.get("bean_id", ""), ""),
                    "brewed_at": row.get("brewed_at", ""),
                    "amount_ml": row.get("amount_ml") or "",
                    "method": row.get("method", "top_brew"),
                    "brew_quality": row.get("brew_quality", "tap"),
                    "runoff": "yes" if row.get("runoff") else "no",
                    "skipped": "yes" if row.get("skipped") else "no",
                    "skip_reason": row.get("skip_reason", ""),
                    "notes": (row.get("notes") or "").replace("\n", " "),
                })
                count += 1
        return count
    except OSError as exc:
        raise ExportError("csv", str(exc)) from exc


def export_csv_bundle(storage: JsonStorage, dest: Path) -> tuple[int, int]:
    """Export beans.csv and brew.csv beside dest stem."""
    beans_path = dest.with_name(dest.stem + "_beans.csv")
    brew_path = dest.with_name(dest.stem + "_brew.csv")
    return export_beans_csv(storage, beans_path), export_brew_csv(storage, brew_path)


def import_beans_csv(
    storage: JsonStorage,
    src: Path,
    *,
    update: bool = False,
) -> int:
    """Import beans from CSV; skips blank name rows."""
    text = _read_csv_text(src)
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames or "name" not in reader.fieldnames:
        raise ImportPipelineError("csv", "missing required column: name")

    existing = {p.id: p for p in storage.list_beans(active_only=False)}
    by_name = {p.name.lower(): p for p in existing.values()}
    count = 0

    for line_no, row in enumerate(reader, start=2):
        name = (row.get("name") or "").strip()
        if not name:
            continue
        pid = (row.get("id") or "").strip()
        bean: Bean | None = None
        if pid and pid in existing:
            bean = existing[pid]
        elif update:
            bean = by_name.get(name.lower())

        try:
            interval_raw = row.get("brew_interval_days")
            interval = parse_interval(str(interval_raw)) if interval_raw else 7
            health = _parse_health(row.get("health"))
            metadata = {}
            notes = (row.get("notes") or "").strip()
            if notes:
                metadata["notes"] = notes

            if bean is None:
                bean = Bean.create(
                    name,
                    id=pid or None,
                    nickname=(row.get("nickname") or "").strip() or None,
                    origin_key=(row.get("origin_key") or "").strip() or None,
                    station_id=(row.get("station_id") or "").strip() or None,
                    health=health,
                    brew_interval_days=interval,
                    last_brewed_at=(row.get("last_brewed_at") or "").strip() or None,
                    acquired_at=(row.get("acquired_at") or "").strip() or None,
                    light_override=(row.get("light_override") or "").strip() or None,
                    archived=_parse_bool(row.get("archived")),
                    source="csv",
                    metadata=metadata,
                )
                hs = row.get("health_score")
                if hs and str(hs).isdigit():
                    bean.health_score = int(hs)
                amt = row.get("brew_amount_ml")
                if amt:
                    bean.brew_amount_ml = parse_amount_ml(str(amt))
                hum = row.get("humidity_override")
                if hum:
                    bean.humidity_override = float(hum)
                created = storage.create_bean(bean)
                existing[created.id] = created
                by_name[created.name.lower()] = created
            else:
                patch: dict[str, Any] = {
                    "name": name,
                    "nickname": (row.get("nickname") or "").strip() or None,
                    "origin_key": (row.get("origin_key") or "").strip() or None,
                    "station_id": (row.get("station_id") or "").strip() or None,
                    "health": health.value,
                    "brew_interval_days": interval,
                    "archived": _parse_bool(row.get("archived")),
                    "source": "csv",
                    "metadata": {**bean.metadata, **metadata},
                }
                lw = (row.get("last_brewed_at") or "").strip()
                if lw:
                    patch["last_brewed_at"] = lw
                updated = storage.update_bean(bean.id, patch)
                existing[updated.id] = updated
            count += 1
        except (ValidationError, ValueError) as exc:
            raise import_pipeline_error("csv", line_no, str(exc)) from exc

    return count


def import_brew_csv(storage: JsonStorage, src: Path) -> int:
    """Import brew events; resolves bean_name when bean_id missing."""
    text = _read_csv_text(src)
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        raise ImportPipelineError("csv", "empty or headerless file")

    by_id, by_name = _bean_lookup(storage)
    count = 0

    for line_no, row in enumerate(reader, start=2):
        bean_id = _resolve_bean_id(
            by_id,
            by_name,
            (row.get("bean_id") or "").strip() or None,
            (row.get("bean_name") or "").strip() or None,
        )
        if not bean_id:
            raise import_pipeline_error("csv", line_no, "bean_id or bean_name required")

        try:
            storage.get_bean(bean_id)
        except Exception:
            raise import_pipeline_error("csv", line_no, "unknown bean %s" % bean_id)

        brewed_at = (row.get("brewed_at") or "").strip()
        if brewed_at:
            try:
                brewed_at = parse_date(brewed_at).isoformat()
            except ValueError:
                pass  # keep raw ISO if already formatted

        amount_ml = None
        amt_raw = row.get("amount_ml")
        if amt_raw not in (None, ""):
            try:
                amount_ml = parse_amount_ml(str(amt_raw))
            except ValueError:
                raise import_pipeline_error("csv", line_no, "bad amount_ml: %s" % amt_raw)

        event = BrewEvent.create(
            bean_id=bean_id,
            id=(row.get("id") or "").strip() or None,
            brewed_at=brewed_at or None,
            amount_ml=amount_ml,
            method=(row.get("method") or "top_brew").strip(),
            runoff=_parse_bool(row.get("runoff")),
            skipped=_parse_bool(row.get("skipped")),
            skip_reason=(row.get("skip_reason") or "").strip(),
            notes=(row.get("notes") or "").strip(),
        )
        if row.get("brew_quality"):
            event.brew_quality = row["brew_quality"].strip()  # type: ignore[assignment]
        storage.create_brew_event(event.to_dict())
        count += 1

    return count


def validate_csv_headers(path: Path, kind: str = "beans") -> list[str]:
    """Return missing required columns for beans or brew CSV."""
    if not path.exists():
        return ["name"] if kind == "beans" else ["bean_id"]
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    headers = reader.fieldnames or []
    if kind == "beans":
        required = ["name"]
    else:
        required = []  # bean_name OR bean_id
        if "bean_id" not in headers and "bean_name" not in headers:
            return ["bean_id or bean_name"]
        return []
    return [h for h in required if h not in headers]


def sample_rows(path: Path, n: int = 3) -> list[dict[str, str]]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    out: list[dict[str, str]] = []
    for i, row in enumerate(reader):
        if i >= n:
            break
        out.append({k: (v or "") for k, v in row.items()})
    return out
