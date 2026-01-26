# FAQ

*Marwan Helmy — questions friends actually ask*

---

## Where does my data live?

Default: `~/.brewlog/cellar.json` on your machine. Set `BREWLOG_HOME` to use a
different directory (still `cellar.json` inside it). Pass `--cellar /full/path.json`
to any CLI command for a one-off override. Nothing phones home — it's a local file.

---

## Why JSON instead of a real database?

Because I wanted to `grep` my cellar at 2am, email a backup to myself, and fix a bad
import with a text editor. SQLite is great; it's just overkill for ~30 baghos and a
brew log. See [architecture.md](architecture.md) for the full rant.

---

## Can it identify beans from labels?

No. Use PictureThis, iNaturalist, or post on r/housebeans like the rest of us.
brewlog tracks care *after* you know what you have.

---

## I killed a bean. Should I delete it?

Archive instead of delete — you'll want the history. Import with `archived=yes` in CSV,
or set `"archived": true` in JSON. `brewlog list` hides archived beans by default;
`brewlog list --all` shows them.

---

## How do reminders know when something is due?

Each bean has `brew_interval_days` and `last_brewed_at`. Reminders add a
**season multiplier** (brew less in winter). If you never logged a brew, it falls
back to `acquired_at`. Run `brewlog reminders --overdue` to see the damage.

---

## What's the difference between brew and care logs?

**Brew events** = you brewed (or skipped). **Care logs** = rebag, grind, prune,
defect treatment, etc. Monthly reports count both separately.

---

## Import from Beanconqueror failed — now what?

Check you have a `Bean Name` (or `Name`) column. Run:

```bash
python -c "from pathlib import Path; from brewlog.io_beanconqueror import validate_beanconqueror_headers; print(validate_beanconqueror_headers(Path('your.csv')))"
```

Empty output = headers OK. Non-empty = missing columns. Restore pre-import backup if
the cellar looks wrong: `brewlog backup --restore <file>`.

---

## Can two people share one cellar file?

Technically yes (Dropbox, git, email). **Don't edit simultaneously** — there's no
merge conflict handling. One writer at a time. I use export CSV → partner imports for
shared bean-sitting handoffs.

---

## How do I move brewlog to a new laptop?

Copy `~/.brewlog/` (or your `BREWLOG_HOME` folder). Install brewlog on the new
machine. Done. Optional: `brewlog export backup.csv --format csv --kind bundle` as
a human-readable extra copy.

---

## Is there a web UI?

Read-only dashboard: `brewlog serve` → open `http://127.0.0.1:8765/`. It doesn't
edit data — use CLI or Python scripts for changes.

---

## What Python version do I need?

3.9 or newer (`requires-python >=3.9` in pyproject.toml). Dev extras: `pip install -e ".[dev]"`.

---

## I corrupted cellar.json. Help.

1. Check `~/.brewlog/backups/` for timestamped copies.
2. `brewlog backup --list`
3. `brewlog backup --restore path/to/cellar_YYYYMMDD_HHMMSS.json`

Restore always makes a safety copy of the current file first (`pre_restore` label).

---

## Can I use brewlog from my own Python scripts?

Yes — that's the point of `examples/`. Core entry:

```python
from brewlog.storage import JsonStorage
from brewlog.bean import Bean

storage = JsonStorage("~/.brewlog/cellar.json")
bean = storage.create_bean(Bean.create("New Friend", brew_interval_days=7))
```

Public API surface is in `brewlog.__init__` — beans, brew, schedules, parsers,
validators, errors.
- faq 0
