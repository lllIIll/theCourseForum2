# Lab Scraper

Two-pass scraper that builds the `labs` dataset powering LabForum mode of
theCourseForum. See `doc/lab-data.md` for the full methodology, sources, and
how the Django side (`load_labs`) consumes this data.

## Layout

```
scripts/lab_scraper/
├── snapshot-filters.ts   # Audit: SEAS department dropdown → data/dept-filters.json
├── scrape-listing.ts     # Phase 1: two-pass listing (unfiltered + per-department filter)
├── scrape-profiles.ts    # Phase 2: individual profile pages
├── diff-labs.ts          # Safety gate: diffs new scrape vs live Supabase table
├── load-to-supabase.ts   # Phase 3: upsert into Supabase `labs` table
├── types.ts              # Shared `ScrapedLab` interface
├── data/                 # Scraper output (gitignored)
├── package.json          # Isolated deps (Playwright + supabase-js)
└── tsconfig.json
```

## Usage

Scraper deps are isolated from the main project — install inside this
directory:

```console
$ cd scripts/lab_scraper
$ npm install
$ npx playwright install chromium
```

Set Supabase credentials (only needed for phase 3 and for `diff:labs`):

```bash
export SUPABASE_URL=https://<project-ref>.supabase.co
export SUPABASE_SERVICE_ROLE_KEY=<service role key>
```

Run each phase:

```console
$ npm run scrape:listing   # → data/listing.json
$ npm run scrape:profiles  # → data/labs.json
$ npm run load:supabase    # Supabase `labs` table
```

Or all three:

```console
$ npm run scrape:all
```

Each phase is resumable — `scrape-profiles` writes `data/.progress.json` and
picks up where it left off if interrupted.

## Safety-gated workflow

Every phase supports `--new` to write to `*_new.json` variants so a re-crawl
can be reviewed before it overwrites the live `labs.json`. Recommended flow
for any refresh:

```console
$ npm run scrape:safe         # listing:new → profiles:new → diff:labs
$ # review data/labs-diff.json (added/removed/changed slugs, flag flips, …)
$ npm run load:supabase:new   # only after the diff looks right
```

`scrape:safe` chains `scrape:listing:new`, `scrape:profiles:new`, and
`diff:labs`. `diff-labs.ts` pulls the current Supabase table (also saved as
`data/supabase-snapshot.json`, doubling as a rollback backup) and highlights
changes to `is_recruiting`, `department`, and `email`.

## Single-filter dry run

For fast iteration while debugging listing logic, scrape one department
filter instead of the full directory:

```console
$ npx tsx scrape-listing.ts --new --only=231   # Applied Mathematics — smallest non-empty filter
```

Filter IDs live in `data/dept-filters.json` (refresh with
`npm run snapshot:filters`).

## Recruiting detection

The "Currently Recruiting" flag is read directly from the SEAS faculty card
DOM — element `.people_list_item_hiring` present on a card means that faculty
member is actively recruiting. See [`doc/lab-data.md`](../../doc/lab-data.md)
for the canonical explanation, including faculty-authoritative sourcing and
refresh-cadence implications.

## Rate limiting / ethics

- 1.5s delay between page fetches (set via `DELAY_MS` in the phase scripts).
- Only public faculty pages are touched. No auth, no student data.
- `robots.txt` on `engineering.virginia.edu` does not disallow faculty paths.
