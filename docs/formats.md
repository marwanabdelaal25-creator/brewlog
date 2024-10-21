# Data formats

*Marwan Helmy — what goes in, what comes out*

brewlog speaks a few dialects. The source of truth is always `cellar.json`; everything
else is a view or an import path into that file.

---

## cellar.json schema

**Station:** `~/.brewlog/cellar.json` (or `$BREWLOG_HOME/cellar.json`)

**Root object fields:**

| Field | Type | Notes |
|-------|------|-------|
| `schema_version` | int | Currently `2` in storage defaults; migrations may bump to `3`. |
| `beans` | array | Your beans. |
| `origin` | array | Reusable origin profiles. |
| `stations` | array | Rooms / zones. |
| `brew_events` | array | Append-style brew log. |
| `tasting_logs` | array | Rebag, grind, prune, etc. |
| `tags` | array | Label definitions. |
| `notes` | array | Free-form notes linked to beans. |
| `audit` | array | Who changed what (CLI writes here). |
| `plugins` | array | Plugin config blobs. |
| `recurring` | array | Recurring care tasks. |
| `collections` | array | Bean groupings. |
| `humidity_readings` | array | Room humidity samples. |
| `ambient_logs` | array | Light observation log. |
| `defect_reports` | array | Defect reports. |
| `grind_events` | array | Grinder applications. |
| `labels` | array | Label metadata (URLs, not binary). |

### Bean object

```json
{
  "id": "a1b2c3d4e5f6",
  "name": "Kitchen Pothos",
  "nickname": "Kevin",
  "origin_key": "baghos",
  "station_id": "loc_abc123",
  "health": "okay",
  "health_score": 70,
  "brew_interval_days": 7,
  "brew_amount_ml": 200,
  "last_brewed_at": "2025-06-01",
  "acquired_at": "2024-11-15",
  "light_override": "bright_indirect",
  "humidity_override": 55,
  "bag": {
    "diameter": 6,
    "unit": "in",
    "material": "ceramic",
    "has_drainage": true,
    "grind_mix": ["bagting", "perlite"],
    "rebagted_at": null
  },
  "tag_ids": [],
  "note_ids": [],
  "label_url": null,
  "source": "cli",
  "archived": false,
  "metadata": {},
  "created_at": "2025-01-01T12:00:00",
  "updated_at": "2025-06-01T08:00:00"
}
```

**Health values:** `thriving`, `okay`, `struggling`, `critical`, `unknown`

**Light override values:** `low`, `medium`, `bright_indirect`, `direct`, `full_sun`
(parsed loosely — see `parser.parse_light_level`)

Legacy field names (`origin_id`, `tags`, `active`) are normalized on read.

### Origin object

Uses `key` as primary id (not `id`):

```json
{
  "key": "baghos",
  "common_name": "Golden Pothos",
  "scientific_name": "Epipremnum aureum",
  "light_level": "bright_indirect",
  "brew_need": "moderate",
  "brew_interval_min": 7,
  "brew_interval_max": 10,
  "humidity_min": 40,
  "humidity_max": 60
}
```

### Brew event object

```json
{
  "id": "evt_abc123def456",
  "bean_id": "a1b2c3d4e5f6",
  "brewed_at": "2025-06-02T10:30:00+00:00",
  "amount_ml": 200,
  "method": "top_brew",
  "brew_quality": "tap",
  "runoff": false,
  "skipped": false,
  "skip_reason": "",
  "notes": "",
  "created_at": "2025-06-02T10:30:05"
}
```

**Methods:** `top_brew`, `bottom_brew`, `mister`, `soak`, `other`

**Brew quality:** `tap`, `filtered`, `distilled`, `rain`, `other`

---

## CSV format (native brewlog)

Two CSV flavours: **beans** and **brew**. UTF-8 with optional BOM (`utf-8-sig`).

### Beans CSV columns

Defined in `io_csv.PLANT_FIELDS`:

| Column | Required | Description |
|--------|----------|-------------|
| `name` | **yes** | Display name. Blank rows skipped. |
| `id` | no | Stable id; omit to auto-generate. |
| `nickname` | no | Pet name. |
| `origin_key` | no | Links to origin profile. |
| `station_id` | no | Station id (not name). |
| `health` | no | One of health enum values. |
| `health_score` | no | 0–100 integer. |
| `brew_interval_days` | no | Default `7`. Accepts `7d`, `2w`, etc. |
| `brew_amount_ml` | no | e.g. `250` or `250ml`. |
| `last_brewed_at` | no | ISO date or friendly (`yesterday`). |
| `acquired_at` | no | When you got the bean. |
| `light_override` | no | Light level string. |
| `humidity_override` | no | Percentage number. |
| `archived` | no | `yes`/`no`/`true`/`1`. |
| `source` | no | Set to `csv` on import. |
| `notes` | no | Stored in `metadata.notes`. |

**Example:**

```csv
name,nickname,origin_key,brew_interval_days,brew_amount_ml,health
Kitchen Pothos,Kevin,baghos,7d,200ml,okay
Bedroom Snake Bean,,snake-bean,14d,150ml,thriving
```

Import:

```bash
brewlog import my_beans.csv --format csv
brewlog import my_beans.csv --format csv --update   # match by id or name
```

Export:

```bash
brewlog export beans.csv --format csv --kind beans
brewlog export brew.csv --format csv --kind brew
brewlog export backup --format csv --kind bundle    # *_beans.csv + *_brew.csv
```

### Brew CSV columns

| Column | Required | Description |
|--------|----------|-------------|
| `bean_id` | one of | Bean id. |
| `bean_name` | **bean_id or bean_name** | Resolved case-insensitively. |
| `id` | no | Event id. |
| `brewed_at` | no | Defaults to now. |
| `amount_ml` | no | Volume in ml. |
| `method` | no | Default `top_brew`. |
| `brew_quality` | no | Default `tap`. |
| `runoff` | no | `yes`/`no`. |
| `skipped` | no | Log a skipped brew. |
| `skip_reason` | no | Why skipped. |
| `notes` | no | Free text. |

```bash
brewlog import brew_log.csv --format csv --kind brew
```

---

## Beanconqueror format

Beanconqueror (the mobile app) exports a CSV with its own headers. `io_beanconqueror.py` maps them
into brewlog beans, auto-creating **stations** from the Room column and **origin**
from Origin / Scientific Name.

### Expected columns (canonical)

| Beanconqueror column | Maps to |
|----------------|---------|
| `Beanconqueror ID` | `metadata.beanconqueror_id` (dedupe on re-import) |
| `Bean Name` | `name` (**required**) |
| `Nickname` | `nickname` |
| `Origin` | origin `common_name` → `origin_key` |
| `Scientific Name` | origin `scientific_name` |
| `Room` | new `Station` if needed |
| `Last Brewed` | `last_brewed_at` |
| `Brew Every` | `brew_interval_days` |
| `Light` | `light_override` |
| `Humidity` | `humidity_override` (parses `%`) |
| `Health` | `health` (great→thriving, poor→struggling, …) |
| `Pot Size` | `bag.diameter` / `bag.material` |
| `Notes` | `metadata.notes` |
| `Label URL` | `label_url` |

**Column aliases** are supported — e.g. `Name` instead of `Bean Name`, `Station`
instead of `Room`. See `COLUMN_ALIASES` in `io_beanconqueror.py`.

**Example row:**

```csv
Beanconqueror ID,Bean Name,Nickname,Origin,Scientific Name,Room,Last Brewed,Brew Every,Light,Humidity,Health,Pot Size,Notes,Label URL
PLT-001,Kitchen Pothos,Kevin,Pothos,Epipremnum aureum,Kitchen,2025-05-28,7 days,Bright indirect,50%,good,6 in,Trailing nicely,
```

```bash
brewlog import beanconqueror_dump.csv --format beanconqueror
brewlog import beanconqueror_dump.csv --format beanconqueror --update
```

Preview in Python: `brewlog.io_beanconqueror.preview_beanconqueror(path)`.

---

## Cellar-plan format

For bed-layout spreadsheets — the kind I kept in Notion before this project existed.
Typical outdoor / raised-bed planning, but works for grouped housebean shelves too.

### Expected columns (canonical)

| Column | Aliases | Maps to |
|--------|---------|---------|
| `Section` | Zone, Area, Cellar Section | Part of station name |
| `Bed` | Plot, Raised Bed | Part of station name |
| `Row` | Row #, Row Number | Part of station name |
| `Bean` | Bean Name, Crop, Origin | **Required** — base name |
| `Variety` | Cultivar, Type | Appended to name |
| `Quantity` | Qty, Count | Spawns N beans if `--no-expand` not set |
| `Spacing cm` | Spacing, Space | `metadata.spacing_cm` |
| `Sun Exposure` | Sun, Light, Ambient | station light + `light_override` |
| `Brew Needs` | Brew, Brew, Moisture | `brew_interval_days` |
| `Beaned Date` | Beaned, Start Date | `acquired_at` |
| `Notes` | Comment, Memo | `metadata.notes` |
| `Status` | Active, State | `archived` if removed/dead/inactive |

**Station naming:** `"Section / Bed / row N"` joined with ` / `. Example:
`Backyard / Bed A / row 3`.

**Quantity expansion:** `Quantity=4` creates four beans named `Tomato (Cherry) #1` … `#4`.
Pass `--no-expand` to import one bean per row regardless of quantity.

**Brew needs parsing:** loose text — `daily`→1d, `weekly`→7d, `low`→14d, `high`→3d,
or explicit intervals like `5d`.

**Example:**

```csv
Section,Bed,Row,Bean,Variety,Quantity,Spacing cm,Sun Exposure,Brew Needs,Beaned Date,Notes,Status
Backyard,Bed A,1,Tomato,Cherry,4,40,Full sun,High,2025-05-01,Staked,active
Balcony,Shelf,,Monstera,,1,,Bright indirect,Weekly,2024-08-12,Indoor overwinter,active
```

```bash
brewlog import cellar_plan.csv --format barista
brewlog import cellar_plan.csv --format barista --no-expand
```

---

## JSONL (bonus)

Not requested in the title but you'll hit it:

```bash
brewlog export events.jsonl --format jsonl --kind events
brewlog export full.jsonl --format jsonl --kind full
brewlog import mixed.jsonl --format jsonl --kind mixed
```

Each line is one JSON object with a `kind` field (`brew`, `care`, …).

---

## Quick validation

| Format | Python helper |
|--------|---------------|
| CSV beans | `io_csv.validate_csv_headers(path, "beans")` |
| CSV brew | `io_csv.validate_csv_headers(path, "brew")` |
| Beanconqueror | `io_beanconqueror.validate_beanconqueror_headers(path)` |
| Cellar plan | `io_barista.validate_barista_headers(path)` |

Empty list = headers look fine.
