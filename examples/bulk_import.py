#!/usr/bin/env python3
"""Bulk import beans from CSV (and optionally Beanconqueror).

Author: Marwan Helmy
Run: python examples/bulk_import.py
     python examples/bulk_import.py path/to/beans.csv
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from brewlog import io_csv, io_beanconqueror
from brewlog.backup import CellarBackup
from brewlog.storage import JsonStorage


def cellar_path() -> Path:
    home = os.environ.get("BREWLOG_HOME")
    base = Path(home) if home else Path.home() / ".brewlog"
    return base / "cellar.json"


def sample_csv(path: Path) -> None:
    path.write_text(
        "name,brew_interval_days,brew_amount_ml,health,notes\n"
        "Office ZZ Bean,21d,100ml,okay,Low maintenance\n"
        "Living Room Ficus,10d,400ml,struggling,Dropping leaves — check light\n"
        "Kitchen Pothos,7d,200ml,thriving,Trailing nicely\n",
        encoding="utf-8",
    )


def main() -> None:
    csv_file = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    use_temp_cellar = csv_file is None

    if use_temp_cellar:
        tmp = tempfile.mkdtemp(prefix="brewlog_import_")
        path = Path(tmp) / "cellar.json"
        csv_file = Path(tmp) / "beans.csv"
        sample_csv(csv_file)
        print(f"Demo mode — cellar: {path}")
    else:
        path = cellar_path()
        if not csv_file.exists():
            print(f"File not found: {csv_file}", file=sys.stderr)
            sys.exit(1)

    storage = JsonStorage(path)
    backup_dir = path.parent / "backups"
    if path.exists() and path.stat().st_size > 50:
        snap = CellarBackup(path, backup_dir).create(label="pre_bulk_import")
        print(f"Backup: {snap}")

    missing = io_csv.validate_csv_headers(csv_file, "beans")
    if missing:
        print(f"CSV missing columns: {missing}", file=sys.stderr)
        sys.exit(1)

    count = io_csv.import_beans_csv(storage, csv_file, update=True)
    print(f"Imported {count} bean(s) from {csv_file.name}")

    for bean in storage.list_beans():
        print(f"  - {bean.display_name}: every {bean.brew_interval_days}d, {bean.health.value}")

    if csv_file.name.lower().find("beanconqueror") >= 0:
        n = io_beanconqueror.import_beanconqueror(storage, csv_file, update=True)
        print(f"Beanconqueror pass: {n} record(s)")


if __name__ == "__main__":
    main()
