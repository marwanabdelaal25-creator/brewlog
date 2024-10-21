"""JSON Lines import/export for cellar events.

Author: Marwan Helmy
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .errors import ExportError, ImportPipelineError, import_pipeline_error
from .bean import Bean
from .storage import JsonStorage
from .brew import BrewEvent

__author__ = "Marwan Helmy"

EVENT_TYPES = ("brew", "care", "bean", "note")


def _iter_lines(path: Path) -> Iterable[str]:
    try:
        with path.open(encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if ln:
                    yield ln
    except OSError as exc:
        raise ImportPipelineError("jsonl", str(exc)) from exc


def _load_line(line: str, line_no: int) -> dict[str, Any]:
    try:
        data = json.loads(line)
    except json.JSONDecodeError as exc:
        raise import_pipeline_error("jsonl", line_no, "invalid JSON: %s" % exc) from exc
    if not isinstance(data, dict):
        raise import_pipeline_error("jsonl", line_no, "each line must be a JSON object")
    return data


def export_brew_jsonl(storage: JsonStorage, dest: Path) -> int:
    events = storage.list_brew_events()
    try:
        with dest.open("w", encoding="utf-8") as fh:
            for row in events:
                payload = {"_type": "brew", **row}
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return len(events)
    except OSError as exc:
        raise ExportError("jsonl", str(exc)) from exc


def export_care_jsonl(storage: JsonStorage, dest: Path) -> int:
    logs = storage.list_tasting_logs()
    try:
        with dest.open("w", encoding="utf-8") as fh:
            for row in logs:
                payload = {"_type": "care", **row}
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return len(logs)
    except OSError as exc:
        raise ExportError("jsonl", str(exc)) from exc


def export_events_jsonl(storage: JsonStorage, dest: Path) -> int:
    """One file with brew + care events (and optional bean snapshots)."""
    n = 0
    try:
        with dest.open("w", encoding="utf-8") as fh:
            for row in storage.list_brew_events():
                fh.write(json.dumps({"_type": "brew", **row}, ensure_ascii=False) + "\n")
                n += 1
            for row in storage.list_tasting_logs():
                fh.write(json.dumps({"_type": "care", **row}, ensure_ascii=False) + "\n")
                n += 1
    except OSError as exc:
        raise ExportError("jsonl", str(exc)) from exc
    return n


def export_full_jsonl(storage: JsonStorage, dest: Path) -> int:
    """Export beans + all event streams for backup-lite migrations."""
    n = 0
    try:
        with dest.open("w", encoding="utf-8") as fh:
            for bean in storage.list_beans(active_only=False):
                fh.write(json.dumps({"_type": "bean", **bean.to_dict()}, ensure_ascii=False) + "\n")
                n += 1
            for row in storage.list_brew_events():
                fh.write(json.dumps({"_type": "brew", **row}, ensure_ascii=False) + "\n")
                n += 1
            for row in storage.list_tasting_logs():
                fh.write(json.dumps({"_type": "care", **row}, ensure_ascii=False) + "\n")
                n += 1
            for note in storage.list_notes():
                fh.write(json.dumps({"_type": "note", **note}, ensure_ascii=False) + "\n")
                n += 1
    except OSError as exc:
        raise ExportError("jsonl", str(exc)) from exc
    return n


def import_brew_jsonl(storage: JsonStorage, src: Path) -> int:
    if not src.exists():
        raise ImportPipelineError("jsonl", "missing %s" % src)
    n = 0
    for line_no, line in enumerate(_iter_lines(src), start=1):
        data = _load_line(line, line_no)
        kind = data.pop("_type", "brew")
        if kind != "brew":
            continue
        event = BrewEvent.from_dict(data)
        storage.create_brew_event(event.to_dict())
        n += 1
    return n


def import_care_jsonl(storage: JsonStorage, src: Path) -> int:
    if not src.exists():
        raise ImportPipelineError("jsonl", "missing %s" % src)
    n = 0
    for line_no, line in enumerate(_iter_lines(src), start=1):
        data = _load_line(line, line_no)
        kind = data.pop("_type", "care")
        if kind != "care":
            continue
        # tasting_logs in storage use flat dicts; CareEvent maps event_type -> action-ish
        if "event_type" in data and "action" not in data:
            data["action"] = data["event_type"]
        if "occurred_at" in data and "logged_at" not in data:
            data["logged_at"] = data["occurred_at"]
        storage.create_tasting_log(data)
        n += 1
    return n


def import_mixed_jsonl(storage: JsonStorage, src: Path) -> dict[str, int]:
    """Import a mixed JSONL export; unknown _type lines are skipped."""
    if not src.exists():
        raise ImportPipelineError("jsonl", "missing %s" % src)
    counts = {k: 0 for k in EVENT_TYPES}
    counts["skipped"] = 0

    for line_no, line in enumerate(_iter_lines(src), start=1):
        data = _load_line(line, line_no)
        kind = data.pop("_type", "brew")

        if kind == "brew":
            storage.create_brew_event(BrewEvent.from_dict(data).to_dict())
            counts["brew"] += 1
        elif kind == "care":
            if "event_type" in data and "action" not in data:
                data["action"] = data["event_type"]
            if "occurred_at" in data and "logged_at" not in data:
                data["logged_at"] = data["occurred_at"]
            storage.create_tasting_log(data)
            counts["care"] += 1
        elif kind == "bean":
            bean = Bean.from_dict(data)
            try:
                storage.get_bean(bean.id)
                storage.update_bean(bean.id, bean.to_dict())
            except Exception:
                storage.create_bean(bean)
            counts["bean"] += 1
        elif kind == "note":
            storage.create_note(data)
            counts["note"] += 1
        else:
            counts["skipped"] += 1

    return counts


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in _iter_lines(path))


def preview(path: Path, limit: int = 5) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line_no, line in enumerate(_iter_lines(path), start=1):
        if len(out) >= limit:
            break
        data = _load_line(line, line_no)
        out.append({"_type": data.get("_type", "?"), "keys": sorted(data.keys())[:8]})
    return out
