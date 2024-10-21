"""Allow `python -m brewlog` invocation."""

from brewlog.cli import main

__doc__ = """
Entry point for the brewlog CLI.

Examples:
  python -m brewlog init
  python -m brewlog bean-add "Monstera" --origin monstera-deliciosa
  python -m brewlog brew <bean-id> --amount 250ml
  python -m brewlog schedule --week
  python -m brewlog export cellar.json

Environment:
  BREWLOG_HOME  Directory for default cellar.json (default: ~/.brewlog/)
"""

if __name__ == "__main__":
    raise SystemExit(main())
