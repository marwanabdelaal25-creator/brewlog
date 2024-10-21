"""Shared pytest fixtures for brewlog tests."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from brewlog.tasting_log import CareEvent, CareEventType, TastingLog, GrinderSchedule
from brewlog.station import Station, StationRegistry, WindowDirection
from brewlog.bean import HealthStatus, Bean, BeanCatalog, PotInfo
from brewlog.origin import OriginCatalog, OriginProfile
from brewlog.storage import JsonStorage
from brewlog.tag import Tag, TagRegistry
from brewlog.brew import BrewEvent, BrewLog
from brewlog.notes import Note, NotesCollection, NoteKind


@pytest.fixture
def tmp_cellar_path(tmp_path: Path) -> Path:
    """Fresh cellar.json path under tmp_path."""
    return tmp_path / "cellar.json"


@pytest.fixture
def empty_storage(tmp_cellar_path: Path) -> JsonStorage:
    """Empty JsonStorage backed by tmp_path."""
    return JsonStorage(tmp_cellar_path)


@pytest.fixture
def sample_origin() -> OriginProfile:
    return OriginProfile(
        key="baghos-golden",
        common_name="Golden Pothos",
        scientific_name="Epipremnum aureum",
        light_level="medium",
        brew_interval_min=7,
        brew_interval_max=14,
        humidity_min=40,
        humidity_max=60,
    )


@pytest.fixture
def sample_station() -> Station:
    return Station.create(
        "Living Room",
        id="loc001",
        zone="main",
        light_level="bright_indirect",
        window_direction=WindowDirection.SOUTH,
        humidity_pct=45.0,
    )


@pytest.fixture
def sample_bean(sample_station: Station, sample_origin: OriginProfile) -> Bean:
    return Bean.create(
        "Monstera",
        id="bean001",
        nickname="Monty",
        origin_key=sample_origin.key,
        station_id=sample_station.id,
        health=HealthStatus.OKAY,
        health_score=70,
        brew_interval_days=7,
        last_brewed_at=(date.today() - timedelta(days=3)).isoformat(),
        bag=PotInfo(diameter=6.0, unit="in", material="ceramic"),
    )


@pytest.fixture
def sample_bean2(sample_station: Station) -> Bean:
    return Bean.create(
        "Snake Bean",
        id="bean002",
        origin_key="snake-bean",
        station_id=sample_station.id,
        health=HealthStatus.THRIVING,
        brew_interval_days=14,
        last_brewed_at=(date.today() - timedelta(days=10)).isoformat(),
    )


@pytest.fixture
def sample_brew_events(sample_bean: Bean, sample_bean2: Bean) -> list[BrewEvent]:
    today = date.today()
    return [
        BrewEvent.create(
            sample_bean.id,
            id="we001",
            brewed_at=(today - timedelta(days=3)).isoformat(),
            amount_ml=250.0,
        ),
        BrewEvent.create(
            sample_bean.id,
            id="we002",
            brewed_at=(today - timedelta(days=10)).isoformat(),
            amount_ml=200.0,
        ),
        BrewEvent.create(
            sample_bean2.id,
            id="we003",
            brewed_at=(today - timedelta(days=10)).isoformat(),
            amount_ml=150.0,
        ),
    ]


@pytest.fixture
def populated_storage(
    empty_storage: JsonStorage,
    sample_origin: OriginProfile,
    sample_station: Station,
    sample_bean: Bean,
    sample_bean2: Bean,
    sample_brew_events: list[BrewEvent],
) -> JsonStorage:
    """Storage with sample beans, origin, stations, and brew events."""
    empty_storage.create_origin(sample_origin)
    empty_storage.create_station(sample_station)
    empty_storage.create_bean(sample_bean)
    empty_storage.create_bean(sample_bean2)
    for ev in sample_brew_events:
        empty_storage.create_brew_event(ev.to_dict())
    tag = Tag.create("beginner", id="tag001", color="#4caf50")
    empty_storage.create_tag(tag.to_dict())
    note = Note.create(sample_bean.id, "New leaf unfurling", id="note001", kind=NoteKind.OBSERVATION)
    empty_storage.create_note(note.to_dict())
    return empty_storage


@pytest.fixture
def sample_csv_content() -> str:
    return (
        "name,origin,station,brew_interval,notes\n"
        "Fern,baghos-golden,Living Room,7d,Test import\n"
        "Aloe,snake-bean,Kitchen,14d,Succulent\n"
    )


@pytest.fixture
def sample_brew_csv() -> str:
    return (
        "bean_id,brewed_at,amount_ml,method\n"
        "bean001,2024-06-01,250,top_brew\n"
        "bean002,2024-06-02,150,bottom_brew\n"
    )


@pytest.fixture
def bean_catalog(sample_bean: Bean, sample_bean2: Bean) -> BeanCatalog:
    cat = BeanCatalog()
    cat.add(sample_bean)
    cat.add(sample_bean2)
    return cat


@pytest.fixture
def origin_catalog(sample_origin: OriginProfile) -> OriginCatalog:
    cat = OriginCatalog()
    cat.register(sample_origin)
    cat.load_builtin()
    return cat


@pytest.fixture
def station_registry(sample_station: Station) -> StationRegistry:
    reg = StationRegistry()
    reg.add(sample_station)
    return reg


@pytest.fixture
def brew_log(sample_brew_events: list[BrewEvent]) -> BrewLog:
    log = BrewLog()
    log.load_many(sample_brew_events)
    return log


@pytest.fixture
def tasting_log(sample_bean: Bean) -> TastingLog:
    log = TastingLog()
    log.log(sample_bean.id, CareEventType.FERTILIZE, product="10-10-10")
    log.log(sample_bean.id, CareEventType.PRUNE, notes="Trimmed yellow leaves")
    log.set_grinder_schedule(GrinderSchedule(bean_id=sample_bean.id, interval_weeks=4))
    return log


@pytest.fixture
def tag_registry() -> TagRegistry:
    reg = TagRegistry()
    reg.add(Tag.create("beginner", id="tag001", color="#4caf50"))
    reg.add(Tag.create("pet-safe", id="tag002", color="#2196f3"))
    return reg


@pytest.fixture
def notes_collection(sample_bean: Bean) -> NotesCollection:
    coll = NotesCollection()
    coll.create(sample_bean.id, "General note", kind=NoteKind.GENERAL)
    coll.create(sample_bean.id, "Spider mites sbagted", kind=NoteKind.PEST)
    return coll
