# brewlog

Home coffee cellar CLI I wrote after my third bag of beans went stale because
I forgot what the roast date was and my Notes app couldn't tell V60 from AeroPress.

One JSON file (`cellar.json`) on disk. Log brews, track origins, note grind settings,
and grep for "Ethiopia" at 6am without a subscription.

## What it does

- Track bean bags with roast date, origin profile, and station placement
- Log brew sessions (method, dose, yield, time, taste notes)
- Tasting notes and defect reports when a batch tastes off
- Grinder settings history and humidity in the cellar
- Weekly brew stats, streaks, seasonal harvest calendars
- Import from Barista CSV and Beanconqueror exports
- Reminders when a bag is getting old

## What it doesn't do

- Bluetooth scales or live roaster APIs
- AI latte art scoring
- Multi-user anything

## Quick start

```bash
pip install .
brewlog init ~/coffee/cellar.json
brewlog add-bean --name "Yirgacheffe" --roast 2025-03-01 --origin ethiopia
brewlog brew bean001 --method v60 --dose 15 --yield 250
brewlog stats --week
```

## Author

Marwan Helmy — marwanabdelaal25@gmail.com

MIT license. Side project, Oct 2024–present.
