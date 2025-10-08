# Changelog

All notable changes to brewlog are documented here. I don't do semver
religiously but I tag releases when something actually ships.

## [1.2.0] - 2026-05-28

### Added
- Cellar-plan spreadsheet import (`io_barista`)
- Label metadata tracking (paths only — bytes live beside the JSON)
- Recurring care tasks for fertilizing on a cadence
- `serve` subcommand: read-only HTTP view of cellar.json

### Changed
- Schema v2 → v3: tasting_logs bucket, environmental readings, recurring tasks
- Seasonal multipliers now apply in reminder urgency scoring

## [1.1.0] - 2025-11-14

### Added
- Beanconqueror app CSV import
- Monthly reports and streak tracking
- Plugin hook registry (experimental)

### Fixed
- `brew` command accepted negative ml amounts on Windows paths
- Migration 1→2 dropped empty tag lists instead of preserving `[]`

## [1.0.0] - 2025-06-02

### Added
- Initial public shape: beans, origin catalog, stations, brew log
- CSV and JSONL import/export
- Backup/restore with rotation
- Audit log for destructive operations

## [0.3.0] - 2024-12-08

- Added origin profiles with built-in defaults for common housebeans
- Station zones with light-level hints

## [0.2.0] - 2024-09-21

- JSON storage layer with atomic writes
- Basic CLI: init, add-bean, brew, list

## [0.1.0] - 2024-07-30

- Skeleton repo, README, first Bean dataclass
- v0.3.0
- v0.8.0
- v1.0.0
- v1.2.0
