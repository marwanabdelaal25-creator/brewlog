"""Light exposure logs for beans and stations.

Author: Marwan Helmy
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from .errors import NotFoundError, ValidationError
from .storage import JsonStorage

VALID_LEVELS = ("low", "medium", "bright", "direct")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class AmbientLogger:
    BUCKET = "ambient_logs"

    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def _rows(self) -> list[dict]:
        return self.storage.snapshot().get(self.BUCKET, [])

    def _persist(self, rows: list[dict]) -> None:
        def _write(data: dict) -> None:
            data[self.BUCKET] = rows

        self.storage.mutate(_write)

    def log(
        self,
        *,
        bean_id: Optional[str] = None,
        station_id: Optional[str] = None,
        level: str = "medium",
        hours: Optional[float] = None,
        notes: str = "",
    ) -> dict:
        if not bean_id and not station_id:
            raise ValidationError("need bean_id or station_id")
        level = level.lower()
        if level not in VALID_LEVELS:
            raise ValidationError(f"level must be one of {VALID_LEVELS}")
        if bean_id:
            self.storage.get_bean(bean_id)
        if station_id:
            self.storage.get_station(station_id)

        row = {
            "id": uuid.uuid4().hex[:12],
            "bean_id": bean_id,
            "station_id": station_id,
            "level": level,
            "hours": hours,
            "observed_at": _utc_now(),
            "notes": notes,
        }
        rows = self._rows()
        rows.append(row)
        self._persist(rows)
        return row

    def for_bean(self, bean_id: str) -> list[dict]:
        rows = [r for r in self._rows() if r.get("bean_id") == bean_id]
        rows.sort(key=lambda r: r.get("observed_at", ""), reverse=True)
        return rows

    def for_station(self, station_id: str) -> list[dict]:
        rows = [r for r in self._rows() if r.get("station_id") == station_id]
        rows.sort(key=lambda r: r.get("observed_at", ""), reverse=True)
        return rows

    def latest_for_bean(self, bean_id: str) -> Optional[dict]:
        items = self.for_bean(bean_id)
        return items[0] if items else None

    def delete(self, log_id: str) -> None:
        rows = self._rows()
        new_rows = [r for r in rows if r.get("id") != log_id]
        if len(new_rows) == len(rows):
            raise NotFoundError(self.BUCKET, log_id)
        self._persist(new_rows)
