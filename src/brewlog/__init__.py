"""Brewlog — personal housebean manager by Marwan Helmy."""

from __future__ import annotations

__version__ = "1.2.0"
__author__ = "Marwan Helmy"
__email__ = "marwanabdelaal25@gmail.com"

from brewlog.errors import (
    BrewlogError,
    StorageError,
    ValidationError,
    NotFoundError,
    ImportPipelineError,
    ExportError,
    MigrationError,
    PluginError,
    ConflictError,
    format_error,
    is_not_found,
    is_validation,
)
from brewlog.bean import Bean, PotInfo, HealthStatus, BeanCatalog
from brewlog.origin import OriginProfile, OriginCatalog, BrewNeed, HumidityNeed
from brewlog.station import Station, StationRegistry, WindowDirection
from brewlog.brew import BrewEvent, BrewLog, BrewQuality
from brewlog.tasting_log import CareEvent, TastingLog, CareEventType, GrinderSchedule
from brewlog.schedule import ScheduleEngine, ScheduleEntry, ScheduleOptions, Season, compute_next_brew
from brewlog.tag import Tag, TagRegistry
from brewlog.notes import Note, NotesCollection, NoteKind
from brewlog.parser import (
    parse_date,
    parse_interval,
    parse_amount_ml,
    parse_light_level,
    parse_humidity,
    format_interval_days,
    format_amount_ml,
)
from brewlog.validators import (
    validate_bean_name,
    validate_interval_days,
    validate_humidity_pct,
    validate_light_level,
)

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    # errors
    "BrewlogError",
    "StorageError",
    "ValidationError",
    "NotFoundError",
    "ImportPipelineError",
    "ExportError",
    "MigrationError",
    "PluginError",
    "ConflictError",
    "format_error",
    "is_not_found",
    "is_validation",
    # bean
    "Bean",
    "PotInfo",
    "HealthStatus",
    "BeanCatalog",
    # origin
    "OriginProfile",
    "OriginCatalog",
    "BrewNeed",
    "HumidityNeed",
    # station
    "Station",
    "StationRegistry",
    "WindowDirection",
    # brew
    "BrewEvent",
    "BrewLog",
    "BrewQuality",
    # care
    "CareEvent",
    "TastingLog",
    "CareEventType",
    "GrinderSchedule",
    # schedule
    "ScheduleEngine",
    "ScheduleEntry",
    "ScheduleOptions",
    "Season",
    "compute_next_brew",
    # tags & notes
    "Tag",
    "TagRegistry",
    "Note",
    "NotesCollection",
    "NoteKind",
    # parser helpers
    "parse_date",
    "parse_interval",
    "parse_amount_ml",
    "parse_light_level",
    "parse_humidity",
    "format_interval_days",
    "format_amount_ml",
    # validators
    "validate_bean_name",
    "validate_interval_days",
    "validate_humidity_pct",
    "validate_light_level",
]
