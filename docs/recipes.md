# Recipes

*Marwan Helmy — copy-paste workflows that actually match how I use brewlog*

Each recipe shows CLI first (fastest), then a Python snippet if you want to script it.
Replace paths and bean names with yours.

---

## 1. Sunday weekly brew routine

Check what's overdue, brew everything due, skim what's coming this week.

```bash
brewlog reminders --overdue
brewlog list --overdue
# brew each one
brewlog brew "Kitchen Pothos" --amount 200ml
brewlog brew "Bedroom Snake Bean" --amount 150ml
brewlog reminders --within 7
```

Python version: `examples/weekly_brew.py`

---

## 2. Fresh install — first five beans

```bash
pip install -e .
brewlog init
brewlog add-bean "Kitchen Pothos" --interval 7d --origin baghos --amount 200ml
brewlog add-bean "Bedroom Snake Bean" --interval 14d --amount 150ml
brewlog add-bean "Bathroom Fern" --interval 3d --amount 300ml --health okay
brewlog list
brewlog stats
```

Set `BREWLOG_HOME=/path/to/test-cellar` if you don't want to touch `~/.brewlog`.

---

## 3. Import from Beanconqueror

Export CSV from the Beanconqueror app, then:

```bash
# peek first — optional
python -c "from pathlib import Path; from brewlog.io_beanconqueror import preview_beanconqueror; print(preview_beanconqueror(Path('beanconqueror_dump.csv')))"

brewlog backup --label pre_beanconqueror
brewlog import beanconqueror_dump.csv --format beanconqueror
brewlog list
```

Re-import after editing the app? Use `--update` to match by Beanconqueror ID or name.

```bash
brewlog import beanconqueror_dump.csv --format beanconqueror --update
```

---

## 4. Backup before vacation

Two weeks away means you want a snapshot and maybe a CSV your bean-sitter can read.

```bash
brewlog backup --label pre_vacation --prune --keep 10
brewlog export vacation_handoff.csv --format csv --kind bundle
brewlog reminders --within 14 > brew_schedule.txt
```

Restore when you get back (only if something went wrong):

```bash
brewlog backup --list
brewlog backup --restore ~/.brewlog/backups/cellar_20250601_120000_pre_vacation.json
```

---

## 5. Bulk import from a spreadsheet

Clean up a Google Sheets export as CSV with at least a `name` column:

```csv
name,brew_interval_days,brew_amount_ml,health,notes
Office ZZ Bean,21d,100ml,okay,Low maintenance
Living Room Ficus,10d,400ml,struggling,Dropping leaves
```

```bash
brewlog import new_beans.csv --format csv
brewlog import new_beans.csv --format csv --update   # second pass: update existing
```

Python version: `examples/bulk_import.py`

---

## 6. Import a cellar-plan bed layout

For the Notion/Sheets planner with Section/Bed/Bean columns:

```bash
brewlog import spring_beds.csv --format barista
brewlog list --station <station-id>   # optional filter after import
```

One row with `Quantity=6` spawns six numbered beans unless you pass `--no-expand`.

---

## 7. Monthly care report

End-of-month ritual — did I actually brew the fern?

```bash
brewlog report --month 6 --year 2025
brewlog report --month 6 --year 2025 --format json > june_2025.json
```

Python version: `examples/monthly_report.py`

---

## 8. Find the bean you forgot the name of

```bash
brewlog search "yellow leaves"
brewlog search "baghos" --kind beans
brewlog search "spider mite" --kind care --verbose
```

---

## 9. Log a skipped brew (grind still wet)

Don't reset the schedule with a fake brew — log a skip:

```bash
brewlog brew "Bathroom Fern" --skip --reason "grind still damp"
brewlog reminders --overdue
```

---

## 10. Export everything before a big edit

```bash
brewlog backup --label before_bulk_edit
brewlog export full_export.jsonl --format jsonl --kind full
brewlog export beans_snapshot.csv --format csv --kind beans
# ... make changes ...
# if regret hits:
brewlog backup --restore ~/.brewlog/backups/cellar_<timestamp>_before_bulk_edit.json
```

---

## 11. Quick API smoke test

Verify install and imports without touching your real cellar:

```bash
python examples/quick_start.py
```

Uses a temp directory — safe to run anytime.

---

## 12. Seasonal interval audit (winter slowdown)

When days get shorter I stretch intervals manually after checking the schedule report:

```bash
brewlog stats
python -c "
from brewlog.storage import JsonStorage
from brewlog.schedule import ScheduleEngine, apply_seasonal_intervals
s = JsonStorage('~/.brewlog/cellar.json'.replace('~', __import__('os').path.expanduser('~')))
e = ScheduleEngine(s)
for row in apply_seasonal_intervals(e, dry_run=True):
    print(row)
"
```

Review the dry-run output before setting `dry_run=False` in a custom script.

---

## Tips I keep forgetting

- **`--cellar path/to/cellar.json`** on any command for a non-default file.
- **Bean lookup** accepts full id, id prefix, exact name, or nickname.
- **Intervals** parse human strings: `7d`, `2w`, `10 days`.
- **Amounts** parse `250ml`, `1 cup` (see `parser.parse_amount_ml`).
