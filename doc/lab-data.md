# Lab Data

The Lab data that powers the LabForum mode of theCourseForum comes from a custom
crawler maintained by the LabForum team. This doc explains the methodology,
sources, and the hand-off path for integrating with theCourseForum.

## Pipeline

```
SEAS Faculty Directory  ──▶  Crawler (TypeScript, Playwright)
    (engineering.virginia.edu)         │
                                       ├──▶ labs.json  (local artifact)
                                       │
                                       └──▶ Supabase `labs` table
                                                    │
                             ┌──────────────────────┘
                             ▼
                    Django `load_labs` management command
                    (fetches from Supabase REST API,
                     normalizes departments, upserts Labs)
```

The scraper lives in-tree at [`scripts/lab_scraper/`](../scripts/lab_scraper/)
with its own isolated `package.json` so its Playwright + Supabase deps don't
touch the main project. See that directory's `README.md` for install/run
steps.

Three TypeScript phases plus two audit/safety helpers:

1. **`snapshot-filters.ts`** — audit helper. Scrapes the SEAS department
   dropdown and writes `data/dept-filters.json` (filter IDs + labels). Also
   diffs the union of filter listings against the unfiltered listing so any
   faculty not categorized by SEAS are flagged instead of silently dropped.
2. **`scrape-listing.ts`** — two-pass scraper:
   - Pass A paginates the unfiltered listing for coverage (guarantees every
     faculty SEAS shows gets captured, including Med-school joint
     appointments that SEAS doesn't tag to any department filter).
   - Pass B paginates each `?department={id}` filter for authoritative
     department tagging — the fix for the 15 faculty who used to be dropped
     because their first title was an endowed chair name rather than a
     department.
   - Emits per faculty: `department` (primary pick), `departments: string[]`
     (every filter they appeared under — exposes joint appointments),
     `departmentSource: "filter" | "fallback_title"`.
3. **`scrape-profiles.ts`** — for each faculty entry, fetches the individual
   profile page to add email, phone, office, Google Scholar, GitHub, personal
   website, research interests, research description, education.
4. **`diff-labs.ts`** — safety gate. Before Supabase write, pulls the current
   Supabase table (also saved as `data/supabase-snapshot.json`, doubling as a
   rollback backup) and diffs it against the freshly scraped `labs_new.json`.
   Reports added / removed / changed slugs and highlights changes to
   `is_recruiting`, `department`, `email`.
5. **`load-to-supabase.ts`** — upserts each scraped row into the Supabase
   `labs` table, keyed by `slug`, so re-runs refresh data rather than
   duplicating rows.

Every phase supports `--new` to write to `_new.json` variants so a re-crawl
can be reviewed with `diff:labs` before anything overwrites the live file.
`npm run scrape:safe` chains listing → profiles → diff with the `--new`
variants as the default safety-gated workflow.

## Sources

### Primary: SEAS Faculty Directory

- **URL:** `https://engineering.virginia.edu/faculty`
- **Why it's primary:** the only UVA source that publishes a
  **"Currently Recruiting"** flag, which is the core differentiator for
  LabForum. Structured Drupal CMS, server-rendered, so most data is
  accessible without JS.
- **Coverage:** ~350 faculty across the SEAS departments below.

Departments currently covered (filter IDs snapshotted in
`scripts/lab_scraper/data/dept-filters.json`):

| Filter ID | SEAS label |
| --- | --- |
| 6 | Computer Science |
| 7 | Biomedical Engineering |
| 8 | Chemical Engineering |
| 9 | Civil and Environmental Engineering |
| 10 | Electrical and Computer Engineering |
| 11 | Engineering and Society |
| 12 | Materials Science and Engineering |
| 13 | Mechanical and Aerospace Engineering |
| 14 | Systems and Information Engineering |
| 226 | Computer Engineering |
| 231 | Applied Mathematics |
| 236 | Engineering Science (empty at last scrape) |
| 266 | First Year Engineering |

Note `"Engineering Science"` and `"First Year Engineering"` are filter labels
new to the crawler and are mapped to `"General Engineering"` in
`load_labs.py`.

Also picks up a small number of joint-appointment faculty who show up in
the unfiltered listing but aren't tagged to any SEAS department filter —
typically cross-appointments from:

- School of Medicine (Cardiovascular Medicine, Anesthesiology, Radiology, …)
- Public Health Sciences (Biostatistics, …)
- Arts & Sciences (Chemistry, Biology, Physics, …)
- Data Science

For these, `department` is parsed from the title strings as a fallback and
`departmentSource` is set to `"fallback_title"` so downstream can treat them
differently if needed.

### How "Currently Recruiting" is detected

The recruiting flag is **not inferred** — it is a direct read of a dedicated
DOM element that SEAS publishes on each faculty card:

```ts
// scripts/lab_scraper/scrape-listing.ts
const hiringEl = card.querySelector(".people_list_item_hiring");
// ...
isRecruiting: hiringEl !== null
```

SEAS renders a `<div class="people_list_item_hiring">Currently
Recruiting</div>` onto a card when a faculty member has opted in. If the
element is present, we set `isRecruiting: true`; if it is missing, `false`.

Implications:

- **Faculty-authoritative.** The signal comes from the PI themselves
  (via their school/department profile), not from research interest keywords
  or heuristics. This is the same signal students see on SEAS.
- **Refresh cadence matters.** Because the flag flips on/off over time as
  faculty close or reopen their labs, `is_recruiting` is only as fresh as the
  last crawl. `last_scraped_at` on each row exposes this to the UI.
- **No secondary source.** Non-SEAS schools don't publish this badge — labs
  imported from any future source will have `is_recruiting: false` by default
  until an equivalent signal is found.

### Secondary sources (not yet scraped)

The crawler is scoped to SEAS for v1 because recruiting status is the whole
point. The following are candidates for future expansion but intentionally
deferred because none of them publish a recruiting flag:

| Source | Count | Difficulty | Priority |
| --- | --- | --- | --- |
| School of Data Science (`datascience.virginia.edu/faculty-research`) | ~35 | Easy | Medium |
| Physics (`phys.virginia.edu/People/`, ASP.NET) | ~50 | Easy | Medium |
| A&S departments (per-subdomain, mixed CMS) | ~200+ | Hard | Low |
| School of Medicine (`med.virginia.edu/faculty`, WordPress) | ~1000+ | Moderate | Low |

## Supabase project

The crawler writes into a Supabase project owned by the LabForum team.
theCourseForum reads from it via the public REST API at import time — it does
not depend on Supabase at runtime.

**Hand-off:** we can transfer ownership of the Supabase project to
theCourseForum directly, or provide the service-role key and table schema so
the data can be mirrored into an existing data store. The
`labs`/`reviews`/`departments` schema is documented in the LabForum repo at
`agent_docs/data-schemas.md`.

### Environment variables used by Django

Set in `.env`:

```
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_ANON_KEY=<anon key — read-only is fine>
```

Only the `labs` table is read by `load_labs`. Reviews are loaded separately
(see `load_lab_reviews`).

## Department normalization

Department strings now come from **SEAS's own filter context** rather than
title parsing. During Pass B of `scrape-listing.ts`, each `?department={id}`
filter page tells us authoritatively which department SEAS considers a
faculty member part of, so `department` (primary pick) is set from the
filter label instead of guessing from the first title string. This is the
fix for the ~15 faculty who used to be dropped because their first title
was an endowed chair name rather than a department.

`departmentSource` records which path was taken:

- `"filter"` (325/351 at last crawl) — faculty appeared under at least one
  SEAS department filter; `department` is the filter label.
- `"fallback_title"` (26/351 at last crawl) — faculty appeared in the
  unfiltered listing but under no filter (mostly Med-school joint
  appointees); `department` is parsed from title strings as a last resort.

Django still normalizes the raw string to theCourseForum's canonical
department names in `tcf_website/management/commands/load_labs.py`. With
filter-sourced data these maps are mostly a **safety net for the 26
`fallback_title` rows** — but they still run for every row:

1. **`DEPARTMENT_MAP`** — keyword → canonical name. Largest keyword wins, so
   `"Electrical and Computer Engineering"` beats `"Computer Engineering"`.
   Two entries were added for the new filter labels the crawler now emits:
   `"Engineering Science": "General Engineering"` and
   `"First Year Engineering": "General Engineering"`.
2. **Full-text fallback** — the keyword is searched across `department`,
   `research_area`, `lab_affiliation`, `research_description`,
   `research_areas`, and `research_interests`. This catches
   `fallback_title` rows whose raw department is something like
   `"School of Medicine"` but whose research clearly belongs in
   `"Biomedical Engineering"`.
3. **`PROFESSOR_DEPARTMENT_OVERRIDES`** — last-resort dictionary of
   `professor_name → department` for the handful of cases that slip through
   both steps. Additions should cite the SEAS profile URL in the PR.

Failures are reported at the end of the `load_labs` run as
`"Skipped (no dept match): <names>"`. These need to be resolved before the
run is shipped.

## The `departments[]` field

Joint appointments are now captured as a plural list. For each faculty
member the scraper emits:

- `department: string` — the primary pick (first filter hit, or parsed
  title for `fallback_title` rows). This is what Django's `load_labs`
  currently consumes.
- `departments: string[]` — **every** filter the faculty appeared under. A
  Biomedical Engineering PI cross-appointed to Cardiovascular Medicine
  shows up in both the BME filter and the unfiltered listing, so
  `departments` records both.

Django today only reads the singular `department` and collapses to a single
FK on `Lab.department`. Exposing joint appointments in the UI
(e.g. a "BME + Med" badge on a lab card, or surfacing a PI on both
department browse pages) is **future work** — the data is already in
Supabase so no re-scrape is required when the UI is ready.

## Running the loaders locally

From a fresh DB:

```console
$ python manage.py seed_lab_departments     # minimal Schools + Departments
$ python manage.py load_labs                # pulls from Supabase → Lab rows
$ python manage.py load_lab_reviews         # pulls approved reviews
```

`docker compose up` runs all three on startup, so a working `.env` is usually
enough to boot with lab data.

### Operator tooling (scraper side)

From `scripts/lab_scraper/`:

```console
$ npm run snapshot:filters   # Refresh data/dept-filters.json from the SEAS dropdown
$ npm run scrape:safe        # listing:new → profiles:new → diff:labs (preferred refresh entry point)
$ npm run diff:labs          # Re-run the diff against data/labs_new.json without re-scraping
$ npm run load:supabase:new  # Push data/labs_new.json to Supabase after reviewing the diff
```

`snapshot:filters` is only needed when SEAS adds or renames a department
filter — rerun it, commit the updated `dept-filters.json`, and add any new
filter label to `DEPARTMENT_MAP` in `load_labs.py`.

## Refresh cadence

The SEAS directory changes meaningfully at semester boundaries (new faculty,
changing recruiting status). The crawler is intended to run at least:

- Once before the Fall semester starts
- Once before the Spring semester starts
- Ad-hoc any time the recruiting flag needs to be refreshed

`last_scraped_at` on each row records the last crawl time for auditing.

**Always use the safety-gated path.** Operators should run `npm run scrape:safe`
(or `scrape:listing:new` + `scrape:profiles:new` manually) first, review
`data/labs-diff.json` — paying particular attention to `is_recruiting`,
`department`, and `email` flips, and to unexpected adds/removes — and only
then run `npm run load:supabase:new`. Writing directly via `scrape:all` /
`load:supabase` skips the diff and is reserved for the very first load of a
fresh Supabase project.

## Legal / ethical notes

- Faculty pages are **intentionally public** — these are public university
  employees with public-facing profiles.
- UVA's `robots.txt` blocks AI training crawlers (ClaudeBot, GPTBot) but does
  not disallow the faculty or research paths used here.
- The crawler paces requests at 1–2 s between fetches.
- No student data, no auth-gated pages, no content behind a login is touched.
- The "Currently Recruiting" flag is explicitly published for prospective
  students — surfacing it is the original intent of the badge.
