#!/usr/bin/env python3
"""Generate and print a monthly care report.

Author: Marwan Helmy
Run: python examples/monthly_report.py
     python examples/monthly_report.py 2025 6
     python examples/monthly_report.py --json
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

from brewlog.reports import MonthlyReport, bean_map_name
from brewlog.storage import JsonStorage


def cellar_path() -> Path:
    home = os.environ.get("BREWLOG_HOME")
    base = Path(home) if home else Path.home() / ".brewlog"
    return base / "cellar.json"


def parse_args() -> tuple[int, int, bool]:
    args = [a for a in sys.argv[1:] if a != "--json"]
    as_json = "--json" in sys.argv
    today = date.today()
    year = int(args[0]) if len(args) > 0 else today.year
    month = int(args[1]) if len(args) > 1 else today.month
    return year, month, as_json


def main() -> None:
    year, month, as_json = parse_args()
    storage = JsonStorage(cellar_path())
    report = MonthlyReport(storage)

    if as_json:
        print(json.dumps(report.generate(year, month), indent=2))
        return

    print(report.render_text(year, month))
    data = report.generate(year, month)
    if data["top_brewed_beans"]:
        print("\nDetails:")
        for pid, count in data["top_brewed_beans"]:
            print(f"  {bean_map_name(storage, pid)}: {count} brew(s)")


if __name__ == "__main__":
    main()
