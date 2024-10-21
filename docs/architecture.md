# Architecture

*Marwan Helmy — how brewlog is put together*

I built brewlog as a single-user CLI first, then grew modules around it when I kept
needing "just one more thing" (seasonal intervals, Beanconqueror imports, defect notes). Nothing
here is microservices. It's one JSON file and a bunch of Python modules that know how
to read it.

## High-level picture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  cli.py     │────▶│ JsonStorage  │────▶│  cellar.json    │
│  (commands) │     │  storage.py  │     │  (~/.brewlog) │
└─────────────┘     └──────┬───────┘     └─────────────────┘
       │                   │
       │            ┌──────┴───────┐
       ▼            ▼              ▼
  reports.py   bean.py       io_*.py (import/export)
  reminders.py brew.py    backup.py / migrate.py
  schedule.py  tasting_log.py
```

The CLI is the main entry point (`brewlog` console script → `cli.py`). Everything
else is library code you can import in scripts — see `examples/` for that.

## Module map

| Module | Role |
|--------|------|
| `storage.py` | **Core.** `JsonStorage` reads/writes `cellar.json`, atomic writes, thread-safe CRUD for every bucket. |
| `bean.py` | Bean entity, health status, overdue math, `BeanCatalog` in-memory helpers. |
| `origin.py` | Origin profiles (brew/light/humidity defaults). |
| `station.py` | Rooms, windows, light levels, station registry. |
| `brew.py` | `BrewEvent`, batch logging, analytics helpers. |
| `tasting_log.py` | Rebagting, fertilizing, pruning — anything that isn't brew. |
| `schedule.py` | Season-aware schedule engine, calendar views, interval audits. |
| `reminders.py` | "What's due today / overdue" sorted by urgency. |
| `seasons.py` | Season multipliers (brew less in winter, etc.). |
| `parser.py` | Human-friendly parsing: `7d`, `250ml`, `bright indirect`, `yesterday`. |
| `validators.py` | Shared validation — keeps CLI and imports from accepting nonsense. |
| `errors.py` | Typed exceptions (`NotFoundError`, `ImportPipelineError`, …). |
| `io_csv.py` | CSV import/export for beans and brew logs. |
| `io_beanconqueror.py` | Beanconqueror app CSV → brewlog beans. |
| `io_barista.py` | Cellar-plan spreadsheet → beans + auto-stations. |
| `io_jsonl.py` | JSONL streams for events / full export. |
| `backup.py` | Timestamped copies + restore with safety snapshot. |
| `migrate.py` | Schema version upgrades (v0 flat list → v3 full cellar). |
| `reports.py` | Monthly care summaries. |
| `stats.py` | Cellar-wide snapshot stats. |
| `search.py` | Fuzzy search across beans, care logs, notes. |
| `audit_log.py` | Append-only audit trail in the JSON file. |
| `tags_manager.py`, `tag.py` | Tag CRUD and filtering. |
| `notes.py` | Per-bean notes with kinds (defect, rebag, …). |
| `labels.py`, `defects.py`, `grinder.py`, `humidity.py`, `ambient.py` | Extended care tracking buckets. |
| `collections.py`, `recurring.py`, `plugins.py`, `streaks.py` | Grouping, recurring tasks, plugin hooks, brew streaks. |
| `server.py` | Read-only HTTP dashboard (`brewlog serve`). |
| `cli.py` | Argument parsing and command wiring. |

## Why JSON, not SQLite

Honest answer: I killed three baghos, not because I lacked JOIN syntax.

1. **I want to read my cellar.** `cat ~/.brewlog/cellar.json | jq` at 2am beats
   `sqlite3 ... ".schema"`.
2. **Backups are obvious.** Copy the file. Email it to myself. Put it in git (private
   repo). Done.
3. **Recovery from my own mistakes.** I've hand-edited a bad import more than once.
   Text beats opaque binary when you're panicking.
4. **No migration treadmill.** SQLite is great when you have a schema that changes
   weekly. I have ~30 beans and a brew log. A version field + `migrate.py` is
   enough.
5. **Import/export symmetry.** CSV/Beanconqueror/cellar-plan pipelines write into the same
   structure the CLI uses. No ORM impedance mismatch.

Trade-offs I accept:

- No concurrent writers across machines (fine for one apartment).
- Full-file load on every command (fine at hundreds of beans, not thousands).
- No ad-hoc SQL queries (I use `search` and small Python scripts instead).

## Storage design

### Single file, many buckets

`cellar.json` is one object with named arrays ("buckets"). `JsonStorage` in
`storage.py` owns the shape:

```json
{
  "schema_version": 2,
  "beans": [],
  "origin": [],
  "stations": [],
  "brew_events": [],
  "tasting_logs": [],
  "tags": [],
  "notes": [],
  "audit": [],
  "plugins": [],
  "recurring": [],
  "collections": [],
  "humidity_readings": [],
  "ambient_logs": [],
  "defect_reports": [],
  "grind_events": [],
  "labels": []
}
```

Each bucket is a list of records with an `id` field (origin use `key`). Generic
`_create` / `_read` / `_update` / `_delete` methods handle most buckets; beans and
origin get typed wrappers returning `Bean` / `OriginProfile` objects.

### Atomic writes

Saves go to `cellar.json.tmp` then `os.replace()` into place. If Python dies mid-write,
you still have the previous file. I learned this the hard way with a half-written export.

### Thread safety

`JsonStorage` uses an `RLock` so a background server thread and CLI commands don't
corrupt the same file in the same process.

### Side effects worth knowing

Creating a brew event also patches the bean's `last_brewed_at`. Lazy coupling,
but it means reminders stay correct even if you only ever call `create_brew_event`.

### Paths and env

| Variable | Default |
|----------|---------|
| `BREWLOG_HOME` | `~/.brewlog/` (directory) |
| (implicit) | `BREWLOG_HOME/cellar.json` or `~/.brewlog/cellar.json` |
| CLI `--cellar` | Override full path to JSON file |

Backups land in `BREWLOG_HOME/backups/` unless you pass `--dir`.

### Schema evolution

`migrate.py` bumps `schema_version` through stepped transforms. `JsonStorage` merges
missing buckets with defaults on load so older files don't explode — but run
`brewlog` once after upgrading so migrations can apply cleanly.

## Data flow examples

**Add bean:** CLI → `Bean.create()` → `storage.create_bean()` → atomic save.

**Brew:** CLI resolves name → `BrewEvent.create()` → `storage.create_brew_event()`
→ bean `last_brewed_at` updated → audit entry.

**Import CSV:** `io_csv.import_beans_csv()` → row loop → `Bean.create()` or
`storage.update_bean()` → save per row (safe but not batched — imports are rare).

**Monthly report:** `reports.MonthlyReport.generate()` reads brew/care buckets,
filters by date range, returns aggregates — no separate analytics DB.

## What I'd change if I started over

Maybe split `brew_events` into a monthly JSONL archive once logs get huge. For now,
one file matches how I actually use it: open, tweak, close, go brew the monstera.
