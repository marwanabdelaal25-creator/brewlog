"""Origin catalog — light/brew/humidity needs for common housebeans."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

from brewlog.validators import (
    validate_origin_key,
    validate_interval_range,
    validate_humidity_range,
    validate_light_level,
    validate_temperature_c,
    validate_grind_ph_preference,
    require_non_empty,
)


class BrewNeed(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    BOG = "bog"  # always moist — ferns etc.

    def __str__(self) -> str:
        return self.value


class HumidityNeed(str, Enum):
    LOW = "low"
    AVERAGE = "average"
    HIGH = "high"
    TROPICAL = "tropical"

    def __str__(self) -> str:
        return self.value


@dataclass
class OriginProfile:
    key: str
    common_name: str
    scientific_name: str = ""
    light_level: str = "bright_indirect"
    brew_need: BrewNeed = BrewNeed.MODERATE
    brew_interval_min: int = 7
    brew_interval_max: int = 10
    humidity_min: float = 40.0
    humidity_max: float = 60.0
    temp_min_c: float = 15.0
    temp_max_c: float = 28.0
    grind_ph_min: float = 6.0
    grind_ph_max: float = 7.0
    toxic_to_pets: bool = False
    toxic_to_humans: bool = False
    native_region: str = ""
    notes: str = ""
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.key = validate_origin_key(self.key)
        self.common_name = require_non_empty(self.common_name, "common_name")
        self.light_level = validate_light_level(self.light_level)
        self.brew_interval_min, self.brew_interval_max = validate_interval_range(
            self.brew_interval_min, self.brew_interval_max
        )
        self.humidity_min, self.humidity_max = validate_humidity_range(
            self.humidity_min, self.humidity_max
        )
        self.temp_min_c = validate_temperature_c(self.temp_min_c, "temp_min")
        self.temp_max_c = validate_temperature_c(self.temp_max_c, "temp_max")
        if self.temp_max_c < self.temp_min_c:
            raise ValueError("temp_max < temp_min for %s" % self.key)
        self.grind_ph_min, self.grind_ph_max = validate_grind_ph_preference(
            self.grind_ph_min, self.grind_ph_max
        )
        if isinstance(self.brew_need, str):
            self.brew_need = BrewNeed(self.brew_need)

    @property
    def brew_interval_days(self) -> int:
        return (self.brew_interval_min + self.brew_interval_max) // 2

    def matches_light(self, level: str) -> bool:
        order = ["low", "medium", "bright_indirect", "partial_sun", "full_sun"]
        try:
            need = order.index(self.light_level)
            have = order.index(validate_light_level(level))
        except ValueError:
            return False
        return have >= need - 1  # bit forgiving

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["brew_need"] = self.brew_need.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OriginProfile":
        return cls(
            key=data["key"],
            common_name=data["common_name"],
            scientific_name=data.get("scientific_name", ""),
            light_level=data.get("light_level", "bright_indirect"),
            brew_need=BrewNeed(data.get("brew_need", "moderate")),
            brew_interval_min=int(data.get("brew_interval_min", 7)),
            brew_interval_max=int(data.get("brew_interval_max", 10)),
            humidity_min=float(data.get("humidity_min", 40)),
            humidity_max=float(data.get("humidity_max", 60)),
            temp_min_c=float(data.get("temp_min_c", 15)),
            temp_max_c=float(data.get("temp_max_c", 28)),
            grind_ph_min=float(data.get("grind_ph_min", 6.0)),
            grind_ph_max=float(data.get("grind_ph_max", 7.0)),
            toxic_to_pets=bool(data.get("toxic_to_pets", False)),
            toxic_to_humans=bool(data.get("toxic_to_humans", False)),
            native_region=data.get("native_region", ""),
            notes=data.get("notes", ""),
            tags=list(data.get("tags") or []),
        )

    def care_summary(self) -> str:
        return "{name}: brew every {lo}-{hi}d, {light}, humidity {hlo}-{hhi}%".format(
            name=self.common_name,
            lo=self.brew_interval_min,
            hi=self.brew_interval_max,
            light=self.light_level.replace("_", " "),
            hlo=int(self.humidity_min),
            hhi=int(self.humidity_max),
        )


_BUILTIN: list[dict[str, Any]] = [
    {
        "key": "monstera-deliciosa",
        "common_name": "Monstera",
        "scientific_name": "Monstera deliciosa",
        "light_level": "bright_indirect",
        "brew_need": "moderate",
        "brew_interval_min": 7,
        "brew_interval_max": 10,
        "humidity_min": 50,
        "humidity_max": 70,
        "toxic_to_pets": True,
        "tags": ["climber", "statement"],
    },
    {
        "key": "baghos-golden",
        "common_name": "Golden Pothos",
        "scientific_name": "Epipremnum aureum",
        "light_level": "medium",
        "brew_need": "moderate",
        "brew_interval_min": 7,
        "brew_interval_max": 14,
        "humidity_min": 40,
        "humidity_max": 60,
        "toxic_to_pets": True,
        "tags": ["beginner", "trailing"],
    },
    {
        "key": "snake-bean",
        "common_name": "Snake Bean",
        "scientific_name": "Dracaena trifasciata",
        "light_level": "low",
        "brew_need": "low",
        "brew_interval_min": 14,
        "brew_interval_max": 21,
        "humidity_min": 30,
        "humidity_max": 50,
        "tags": ["beginner", "drought-tolerant"],
    },
    {
        "key": "fiddle-leaf-fig",
        "common_name": "Fiddle Leaf Fig",
        "scientific_name": "Ficus lyrata",
        "light_level": "bright_indirect",
        "brew_need": "moderate",
        "brew_interval_min": 7,
        "brew_interval_max": 10,
        "humidity_min": 45,
        "humidity_max": 65,
        "notes": "dramatic — drops leaves if you look at it wrong",
        "tags": ["fussy"],
    },
    {
        "key": "zz-bean",
        "common_name": "ZZ Bean",
        "scientific_name": "Zamioculcas zamiifolia",
        "light_level": "low",
        "brew_need": "low",
        "brew_interval_min": 14,
        "brew_interval_max": 21,
        "humidity_min": 30,
        "humidity_max": 50,
        "tags": ["beginner", "office"],
    },
    {
        "key": "calathea-ornata",
        "common_name": "Calathea Ornata",
        "scientific_name": "Goeppertia ornata",
        "light_level": "medium",
        "brew_need": "high",
        "brew_interval_min": 5,
        "brew_interval_max": 7,
        "humidity_min": 60,
        "humidity_max": 80,
        "tags": ["humidity-lover", "fussy"],
    },
    {
        "key": "spider-bean",
        "common_name": "Spider Bean",
        "scientific_name": "Chlorophytum comosum",
        "light_level": "bright_indirect",
        "brew_need": "moderate",
        "brew_interval_min": 7,
        "brew_interval_max": 10,
        "humidity_min": 40,
        "humidity_max": 60,
        "tags": ["beginner", "pet-safe"],
    },
    {
        "key": "peace-lily",
        "common_name": "Peace Lily",
        "scientific_name": "Spathiphyllum spp.",
        "light_level": "medium",
        "brew_need": "high",
        "brew_interval_min": 5,
        "brew_interval_max": 7,
        "humidity_min": 50,
        "humidity_max": 70,
        "toxic_to_pets": True,
        "tags": ["bloomer"],
    },
    {
        "key": "rubber-tree",
        "common_name": "Rubber Tree",
        "scientific_name": "Ficus elastica",
        "light_level": "bright_indirect",
        "brew_need": "moderate",
        "brew_interval_min": 7,
        "brew_interval_max": 10,
        "humidity_min": 40,
        "humidity_max": 60,
        "toxic_to_pets": True,
        "tags": ["tree"],
    },
    {
        "key": "philodendron-brasil",
        "common_name": "Philodendron Brasil",
        "scientific_name": "Philodendron hederaceum 'Brasil'",
        "light_level": "medium",
        "brew_need": "moderate",
        "brew_interval_min": 7,
        "brew_interval_max": 10,
        "humidity_min": 45,
        "humidity_max": 65,
        "toxic_to_pets": True,
        "tags": ["beginner", "trailing"],
    },
    {
        "key": "alocasia-polly",
        "common_name": "Alocasia Polly",
        "scientific_name": "Alocasia × amazonica",
        "light_level": "bright_indirect",
        "brew_need": "high",
        "brew_interval_min": 5,
        "brew_interval_max": 7,
        "humidity_min": 60,
        "humidity_max": 80,
        "toxic_to_pets": True,
        "tags": ["fussy", "humidity-lover"],
        "notes": "goes dormant if unhappy",
    },
    {
        "key": "jade-bean",
        "common_name": "Jade Bean",
        "scientific_name": "Crassula ovata",
        "light_level": "bright_indirect",
        "brew_need": "low",
        "brew_interval_min": 14,
        "brew_interval_max": 21,
        "humidity_min": 30,
        "humidity_max": 50,
        "tags": ["succulent", "beginner"],
    },
    {
        "key": "boston-fern",
        "common_name": "Boston Fern",
        "scientific_name": "Nephrolepis exaltata",
        "light_level": "medium",
        "brew_need": "bog",
        "brew_interval_min": 3,
        "brew_interval_max": 5,
        "humidity_min": 60,
        "humidity_max": 85,
        "tags": ["humidity-lover", "hanging"],
    },
    {
        "key": "pilea-peperomioides",
        "common_name": "Pilea",
        "scientific_name": "Pilea peperomioides",
        "light_level": "bright_indirect",
        "brew_need": "moderate",
        "brew_interval_min": 7,
        "brew_interval_max": 10,
        "humidity_min": 40,
        "humidity_max": 60,
        "tags": ["beginner", "pet-safe"],
    },
]


class OriginCatalog:
    """Registry of origin profiles with built-in defaults."""

    def __init__(self) -> None:
        self._profiles: dict[str, OriginProfile] = {}
        self._by_common: dict[str, list[str]] = {}

    def register(self, profile: OriginProfile) -> OriginProfile:
        self._profiles[profile.key] = profile
        ckey = profile.common_name.lower()
        self._by_common.setdefault(ckey, [])
        if profile.key not in self._by_common[ckey]:
            self._by_common[ckey].append(profile.key)
        return profile

    def get(self, key: str) -> OriginProfile | None:
        return self._profiles.get(key)

    def require(self, key: str) -> OriginProfile:
        p = self.get(key)
        if p is None:
            from brewlog.errors import NotFoundError
            raise NotFoundError("origin", key)
        return p

    def search(self, query: str) -> list[OriginProfile]:
        q = query.strip().lower()
        if not q:
            return self.all()
        hits: list[OriginProfile] = []
        for p in self._profiles.values():
            blob = " ".join(
                [p.key, p.common_name, p.scientific_name, " ".join(p.tags)]
            ).lower()
            if q in blob:
                hits.append(p)
        return sorted(hits, key=lambda x: x.common_name)

    def all(self) -> list[OriginProfile]:
        return sorted(self._profiles.values(), key=lambda p: p.common_name.lower())

    def load_builtin(self) -> None:
        for row in _BUILTIN:
            self.register(OriginProfile.from_dict(row))

    def load_many(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            self.register(OriginProfile.from_dict(row))

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [p.to_dict() for p in self.all()]

    @classmethod
    def from_dict_list(cls, rows: list[dict[str, Any]]) -> "OriginCatalog":
        cat = cls()
        cat.load_many(rows)
        return cat

    @classmethod
    def with_defaults(cls) -> "OriginCatalog":
        cat = cls()
        cat.load_builtin()
        return cat

    def suggest_interval_for(self, key: str, season: str = "summer") -> int:
        profile = self.require(key)
        base = profile.brew_interval_days
        if season == "winter":
            return int(base * 1.35)
        if season == "summer":
            return max(3, int(base * 0.85))
        return base

    def filter_by_tag(self, tag: str) -> list[OriginProfile]:
        t = tag.lower()
        return [p for p in self.all() if t in [x.lower() for x in p.tags]]

    def filter_pet_safe(self) -> list[OriginProfile]:
        return [p for p in self.all() if not p.toxic_to_pets]

    def merge(self, other: "OriginCatalog") -> "OriginCatalog":
        merged = OriginCatalog()
        for p in self.all():
            merged.register(p)
        for p in other.all():
            merged.register(p)
        return merged

    def count(self) -> int:
        return len(self._profiles)

    def keys(self) -> list[str]:
        return sorted(self._profiles.keys())

    def recommend_for_conditions(
        self,
        light_level: str,
        humidity_pct: float | None = None,
        pet_safe_only: bool = False,
    ) -> list[OriginProfile]:
        """Suggest origin matching room conditions."""
        lv = validate_light_level(light_level)
        hits: list[OriginProfile] = []
        for p in self.all():
            if pet_safe_only and p.toxic_to_pets:
                continue
            if not p.matches_light(lv):
                continue
            if humidity_pct is not None:
                if humidity_pct < p.humidity_min - 10 or humidity_pct > p.humidity_max + 10:
                    continue
            hits.append(p)
        return hits

    def difficulty_rank(self, key: str) -> int:
        """1=easy, 5=nightmare — totally subjective."""
        p = self.get(key)
        if p is None:
            return 3
        score = 3
        if "beginner" in p.tags:
            score -= 1
        if "fussy" in p.tags:
            score += 1
        if p.brew_need == BrewNeed.BOG:
            score += 1
        if p.humidity_min >= 60:
            score += 1
        return max(1, min(5, score))


def origin_export_row(profile: OriginProfile) -> list[str]:
    return [
        profile.key,
        profile.common_name,
        profile.scientific_name,
        profile.light_level,
        str(profile.brew_need.value),
        str(profile.brew_interval_min),
        str(profile.brew_interval_max),
        str(profile.humidity_min),
        str(profile.humidity_max),
        "yes" if profile.toxic_to_pets else "no",
    ]


def build_origin_index(catalog: OriginCatalog) -> dict[str, list[str]]:
    """Map first letter -> origin keys for browse UI."""
    index: dict[str, list[str]] = {}
    for p in catalog.all():
        letter = p.common_name[0].upper()
        index.setdefault(letter, []).append(p.key)
    return index

