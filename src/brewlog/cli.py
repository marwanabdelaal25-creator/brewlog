"""Command-line interface for brewlog.

Author: Marwan Helmy
"""

# TODO: add --json flag on more subcommands for scripting

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

from brewlog.audit_log import AuditLog
from brewlog.backup import CellarBackup
from brewlog.errors import BrewlogError, NotFoundError, format_error
from brewlog.parser import parse_amount_ml, parse_date, parse_interval
from brewlog.bean import Bean, HealthStatus
from brewlog.reports import MonthlyReport
from brewlog.reminders import ReminderEngine
from brewlog.search import CellarSearch
from brewlog.server import run_server
from brewlog.stats import CellarStats
from brewlog.storage import JsonStorage
from brewlog.brew import BrewEvent
from brewlog import io_csv, io_jsonl, io_beanconqueror, io_barista

__version__ = "1.2.0"
__author__ = "Marwan Helmy"


def _default_cellar_path() -> Path:
    home = os.environ.get("BREWLOG_HOME")
    if home:
        base = Path(home)
    else:
        base = Path.home() / ".brewlog"
    return base / "cellar.json"


def _cellar_path(ns: argparse.Namespace) -> Path:
    if getattr(ns, "cellar", None):
        return Path(ns.cellar)
    return _default_cellar_path()


def _load(ns: argparse.Namespace) -> JsonStorage:
    path = _cellar_path(ns)
    return JsonStorage(path)


def _resolve_bean(storage: JsonStorage, token: str) -> Bean:
    """Find bean by full id, id prefix, or case-insensitive name."""
    beans = storage.list_beans(active_only=False)
    if any(p.id == token for p in beans):
        return storage.get_bean(token)
    matches = [p for p in beans if p.id.startswith(token)]
    if len(matches) == 1:
        return matches[0]
    name_hits = [p for p in beans if p.name.lower() == token.lower()]
    if len(name_hits) == 1:
        return name_hits[0]
    nick_hits = [p for p in beans if p.nickname and p.nickname.lower() == token.lower()]
    if len(nick_hits) == 1:
        return nick_hits[0]
    partial = [p for p in beans if token.lower() in p.name.lower()]
    if len(partial) == 1:
        return partial[0]
    raise NotFoundError("bean", token)


def cmd_init(ns: argparse.Namespace) -> int:
    path = _cellar_path(ns)
    path.parent.mkdir(parents=True, exist_ok=True)
    storage = JsonStorage(path)
    storage.save()
    print("Initialized cellar at %s" % path)
    return 0


def cmd_add_bean(ns: argparse.Namespace) -> int:
    storage = _load(ns)
    interval = parse_interval(ns.interval) if ns.interval else 7
    health = HealthStatus(ns.health) if ns.health else HealthStatus.UNKNOWN
    bean = Bean.create(
        ns.name,
        nickname=ns.nickname,
        origin_key=ns.origin,
        station_id=ns.station,
        health=health,
        brew_interval_days=interval,
        acquired_at=ns.acquired,
        source="cli",
    )
    if ns.amount:
        bean.brew_amount_ml = parse_amount_ml(ns.amount)
    created = storage.create_bean(bean)
    AuditLog(storage).record("create", "bean", created.id, details={"name": created.name})
    print("Added %s (%s)" % (created.display_name, created.id))
    return 0


def cmd_brew(ns: argparse.Namespace) -> int:
    storage = _load(ns)
    bean = _resolve_bean(storage, ns.bean)
    when = parse_date(ns.date).isoformat() if ns.date else date.today().isoformat()
    amount = parse_amount_ml(ns.amount) if ns.amount else bean.brew_amount_ml
    if ns.skip:
        event = BrewEvent.skip(bean.id, reason=ns.reason or "")
    else:
        event = BrewEvent.create(
            bean_id=bean.id,
            brewed_at=when,
            amount_ml=amount,
            method=ns.method or "top_brew",
            notes=ns.notes or "",
        )
    storage.create_brew_event(event.to_dict())
    AuditLog(storage).record("brew", "bean", bean.id, details={"event_id": event.id})
    if ns.skip:
        print("Skipped brew for %s" % bean.display_name)
    else:
        print("Brewed %s — %s" % (bean.display_name, event.summary()))
    return 0


def cmd_list(ns: argparse.Namespace) -> int:
    storage = _load(ns)
    beans = storage.list_beans(active_only=not ns.all)
    if ns.overdue:
        beans = [p for p in beans if p.is_overdue()]
    if ns.station:
        beans = [p for p in beans if p.station_id == ns.station]
    beans = sorted(beans, key=lambda p: p.name.lower())
    if not beans:
        print("No beans found.")
        return 0
    for p in beans[: ns.limit]:
        overdue = ""
        if p.is_overdue():
            overdue = " OVERDUE+%dd" % p.overdue_by_days()
        print(
            "{id} | {name} | {health} | every {iv}d{od}".format(
                id=p.id[:10],
                name=p.display_name[:40],
                health=p.health.value,
                iv=p.brew_interval_days,
                od=overdue,
            )
        )
    if len(beans) > ns.limit:
        print("... and %d more (use --limit)" % (len(beans) - ns.limit))
    return 0


def cmd_report(ns: argparse.Namespace) -> int:
    storage = _load(ns)
    today = date.today()
    year = ns.year or today.year
    month = ns.month or today.month
    report = MonthlyReport(storage)
    if ns.format == "json":
        import json
        print(json.dumps(report.generate(year, month), indent=2))
    else:
        print(report.render_text(year, month))
    return 0


def cmd_import(ns: argparse.Namespace) -> int:
    storage = _load(ns)
    src = Path(ns.file)
    fmt = (ns.format or src.suffix.lstrip(".")).lower()
    result: int | dict | tuple = 0

    if fmt == "csv":
        kind = ns.kind or "beans"
        if kind == "beans":
            result = io_csv.import_beans_csv(storage, src, update=ns.update)
        elif kind == "brew":
            result = io_csv.import_brew_csv(storage, src)
        else:
            print("Unknown csv kind: %s" % kind, file=sys.stderr)
            return 1
    elif fmt == "jsonl":
        if ns.kind == "brew":
            result = io_jsonl.import_brew_jsonl(storage, src)
        elif ns.kind == "care":
            result = io_jsonl.import_care_jsonl(storage, src)
        else:
            result = io_jsonl.import_mixed_jsonl(storage, src)
    elif fmt == "beanconqueror":
        result = io_beanconqueror.import_beanconqueror(storage, src, update=ns.update)
    elif fmt == "barista":
        result = io_barista.import_barista(storage, src, expand_quantity=not ns.no_expand)
    else:
        print("Unknown import format: %s" % fmt, file=sys.stderr)
        return 1

    AuditLog(storage).record("import", "cellar", str(src), details={"format": fmt, "result": result})
    if isinstance(result, dict):
        print("Imported: %s" % ", ".join("%s=%d" % (k, v) for k, v in result.items() if k != "skipped"))
        if result.get("skipped"):
            print("  skipped %d unknown line(s)" % result["skipped"])
    else:
        print("Imported %d record(s)" % result)
    return 0


def cmd_export(ns: argparse.Namespace) -> int:
    storage = _load(ns)
    dest = Path(ns.file)
    fmt = (ns.format or dest.suffix.lstrip(".")).lower()
    n: int | tuple = 0

    if fmt == "csv":
        kind = ns.kind or "beans"
        if kind == "beans":
            n = io_csv.export_beans_csv(storage, dest)
        elif kind == "brew":
            n = io_csv.export_brew_csv(storage, dest)
        elif kind == "bundle":
            n = io_csv.export_csv_bundle(storage, dest)
        else:
            print("Unknown csv kind: %s" % kind, file=sys.stderr)
            return 1
    elif fmt == "jsonl":
        if ns.kind == "brew":
            n = io_jsonl.export_brew_jsonl(storage, dest)
        elif ns.kind == "care":
            n = io_jsonl.export_care_jsonl(storage, dest)
        elif ns.kind == "full":
            n = io_jsonl.export_full_jsonl(storage, dest)
        else:
            n = io_jsonl.export_events_jsonl(storage, dest)
    else:
        print("Unknown export format: %s" % fmt, file=sys.stderr)
        return 1

    if isinstance(n, tuple):
        print("Exported beans=%d brew=%d" % n)
    else:
        print("Exported %d record(s) -> %s" % (n, dest))
    return 0


def cmd_backup(ns: argparse.Namespace) -> int:
    storage = _load(ns)
    cellar_path = _cellar_path(ns)
    backup_dir = Path(ns.dir) if ns.dir else cellar_path.parent / "backups"
    gb = CellarBackup(cellar_path, backup_dir)
    if ns.restore:
        safety = gb.restore(Path(ns.restore))
        print("Restored from %s (safety copy: %s)" % (ns.restore, safety))
        storage.load()
        return 0
    if ns.list:
        for p in gb.list_backups():
            print(p.name)
        return 0
    out = gb.create(label=ns.label)
    if ns.prune:
        removed = gb.prune(keep=ns.keep)
        print("Pruned %d old backup(s)" % len(removed))
    print("Backup -> %s" % out)
    return 0


def cmd_search(ns: argparse.Namespace) -> int:
    storage = _load(ns)
    engine = CellarSearch(storage)
    query = ns.query or ""
    if not query:
        print("Provide a search query.", file=sys.stderr)
        return 1
    if ns.kind == "beans":
        hits = engine.search_beans(query)
    elif ns.kind == "care":
        hits = engine.search_tasting_logs(query)
    elif ns.kind == "notes":
        hits = engine.search_notes(query)
    else:
        hits = engine.search_all(query, limit=ns.limit)
    if not hits:
        print("No matches.")
        return 0
    for h in hits[: ns.limit]:
        print("[{kind}] {score:.0%} {title} ({id})".format(
            kind=h.kind,
            score=h.score,
            title=h.title[:50],
            id=h.id[:12],
        ))
        if h.snippet and ns.verbose:
            print("  %s" % h.snippet)
    print("%d result(s)" % len(hits))
    return 0


def cmd_reminders(ns: argparse.Namespace) -> int:
    storage = _load(ns)
    engine = ReminderEngine(storage)
    if ns.overdue:
        items = engine.overdue_only()
    else:
        items = engine.upcoming(within_days=ns.within, include_overdue=True)
    if not items:
        print("All caught up.")
        return 0
    for r in items[: ns.limit]:
        if r.urgency == "overdue":
            flag = "!!"
        elif r.urgency == "due_today":
            flag = "->"
        else:
            flag = "  "
        print("{flag} {name} due {due} ({urg})".format(
            flag=flag,
            name=r.bean_name[:35],
            due=r.due_at.date(),
            urg=r.urgency,
        ))
    if len(items) > ns.limit:
        print("... %d more" % (len(items) - ns.limit))
    return 0


def cmd_stats(ns: argparse.Namespace) -> int:
    storage = _load(ns)
    gs = CellarStats(storage)
    if ns.json:
        import json
        print(json.dumps(gs.snapshot(), indent=2))
    else:
        print(gs.render_text())
    return 0


def cmd_serve(ns: argparse.Namespace) -> int:
    path = str(_cellar_path(ns))
    print("Serving %s on http://%s:%d/" % (path, ns.host, ns.port))
    run_server(path, host=ns.host, port=ns.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="brewlog",
        description="Personal housebean care tracker — Marwan Helmy",
    )
    p.add_argument(
        "--cellar",
        help="Path to cellar.json (default: ~/.brewlog/cellar.json or BREWLOG_HOME)",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--version", action="version", version="%(prog)s " + __version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init", help="Create an empty cellar.json")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("add-bean", help="Add a new bean")
    sp.add_argument("name")
    sp.add_argument("--nickname")
    sp.add_argument("--origin", help="Origin profile key")
    sp.add_argument("--station", help="Station id")
    sp.add_argument("--interval", default="7d", help="Brew interval e.g. 7d, 2w")
    sp.add_argument("--amount", help="Default brew amount e.g. 250ml")
    sp.add_argument("--acquired", help="Acquired date")
    sp.add_argument(
        "--health",
        choices=[h.value for h in HealthStatus],
        default="unknown",
    )
    sp.set_defaults(func=cmd_add_bean)

    sp = sub.add_parser("brew", help="Log a brew event")
    sp.add_argument("bean", help="Bean id or name")
    sp.add_argument("--amount", help="Brew amount e.g. 250ml")
    sp.add_argument("--date", help="When (today, yesterday, YYYY-MM-DD)")
    sp.add_argument("--method", default="top_brew")
    sp.add_argument("--notes", default="")
    sp.add_argument("--skip", action="store_true", help="Log a skipped brew")
    sp.add_argument("--reason", default="", help="Skip reason")
    sp.set_defaults(func=cmd_brew)

    sp = sub.add_parser("list", help="List beans")
    sp.add_argument("--all", action="store_true", help="Include archived")
    sp.add_argument("--overdue", action="store_true", help="Only overdue beans")
    sp.add_argument("--station", help="Filter by station id")
    sp.add_argument("--limit", type=int, default=100)
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("report", help="Monthly care report")
    sp.add_argument("--year", type=int)
    sp.add_argument("--month", type=int)
    sp.add_argument("--format", choices=["text", "json"], default="text")
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("import", help="Import from external format")
    sp.add_argument("file")
    sp.add_argument(
        "--format",
        choices=["csv", "jsonl", "beanconqueror", "barista"],
        help="Auto-detected from extension if omitted",
    )
    sp.add_argument(
        "--kind",
        choices=["beans", "brew", "care", "mixed"],
        default="beans",
        help="CSV/JSONL sub-type",
    )
    sp.add_argument("--update", action="store_true", help="Update existing beans on import")
    sp.add_argument(
        "--no-expand",
        action="store_true",
        help="Cellar plan: one bean per row regardless of quantity",
    )
    sp.set_defaults(func=cmd_import)

    sp = sub.add_parser("export", help="Export cellar data")
    sp.add_argument("file")
    sp.add_argument("--format", choices=["csv", "jsonl"])
    sp.add_argument(
        "--kind",
        choices=["beans", "brew", "care", "events", "full", "bundle"],
        default="beans",
    )
    sp.set_defaults(func=cmd_export)

    sp = sub.add_parser("backup", help="Backup or restore cellar.json")
    sp.add_argument("--dir", help="Backup directory")
    sp.add_argument("--label", help="Optional backup label")
    sp.add_argument("--list", action="store_true", help="List backups")
    sp.add_argument("--restore", metavar="FILE", help="Restore from backup file")
    sp.add_argument("--prune", action="store_true", help="Prune old backups after create")
    sp.add_argument("--keep", type=int, default=10, help="Backups to keep when pruning")
    sp.set_defaults(func=cmd_backup)

    sp = sub.add_parser("search", help="Search beans, care logs, notes")
    sp.add_argument("query", nargs="?", default="")
    sp.add_argument("--kind", choices=["all", "beans", "care", "notes"], default="all")
    sp.add_argument("--limit", type=int, default=30)
    sp.set_defaults(func=cmd_search)

    sp = sub.add_parser("reminders", help="Upcoming and overdue brew reminders")
    sp.add_argument("--within", type=int, default=14, help="Days ahead to show")
    sp.add_argument("--overdue", action="store_true", help="Overdue only")
    sp.add_argument("--limit", type=int, default=50)
    sp.set_defaults(func=cmd_reminders)

    sp = sub.add_parser("stats", help="Cellar statistics snapshot")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_stats)

    sp = sub.add_parser("serve", help="Start read-only HTTP dashboard")
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=8765)
    sp.set_defaults(func=cmd_serve)

    return p


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    ns = parser.parse_args(argv)
    try:
        return ns.func(ns)
    except BrewlogError as exc:
        print("error: %s" % format_error(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
