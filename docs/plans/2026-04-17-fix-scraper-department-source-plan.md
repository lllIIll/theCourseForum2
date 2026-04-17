---
title: "fix(scraper): department source from SEAS filter, not first title"
type: fix
date: 2026-04-17
---

# Fix Scraper Department Source

## Overview

`scripts/lab_scraper/scrape-listing.ts` derives each faculty's `department`
from the **first title** on their card. When that first title is an endowed
chair (e.g. `"Whitney Stone Professor of Engineering"`), the parsed string is
not a real department name, and `load_labs` drops those rows at import time.

**Impact today:** 15 / 352 SEAS faculty silently skipped.

The fix replaces title-parsing with a filter-based read: for each department
option in the SEAS faculty dropdown, scrape the filtered listing and tag
those faculty with that filter's department label. Titles become a defensive
fallback only.

## Audit findings (pre-implementation)

Verified against `listing.json` + live SEAS page:

1. All 15 skipped faculty **are** in `listing.json` — SEAS, not strays.
2. Most hide the correct dept in `titles[1+]`:
   - `David Evans` → `titles[1]` = `"Professor of Computer Science"`
   - `Richard J. Price` → `titles[1]` = `"Professor, Biomedical Engineering"`
3. Cross-appointments are common — `"by courtesy"` appears in 5 / 15.
   Filter scraping exposes all joint appointments naturally.
4. SEAS dropdown publishes **13** department IDs. Two are missing from
   `DEPARTMENT_MAP` in `load_labs.py` and must be added before the new data
   lands:
   - `236` → "Engineering Science"
   - `266` → "First Year Engineering"
5. Three faculty have only generic titles (`"Assistant Professor"`,
   `"Assistant Professor AGF"`) — **only** filter scraping can recover a real
   dept for them (`Matthew McMillan`, `W. Streit Cunningham`, `Joshua Earle`).

## Plan

### 1. Discovery

1a. Scrape the dropdown on `engineering.virginia.edu/faculty`, persist
    `scripts/lab_scraper/data/dept-filters.json` with
    `{ id, label, slug }` per option. Commit as an audit artifact so
    future ID drift is visible in diffs.

1b. Sanity: count faculty returned per `?department={id}`; union should cover
    the unfiltered 352 ± 2. Any drop means faculty with no filter assignment
    — flagged, not lost.

### 2. Refactor `scrape-listing.ts`

2a. **Two passes, merged.**
   - Pass A — unfiltered `?page=N` (keeps coverage guarantee).
   - Pass B — per filter: `?department={id}&page=N` (authoritative tags).

2b. **Merge by slug.**
   - `departments: string[]` — every filter label the slug appeared under
     (new field, always emitted).
   - `department: string` — deterministic primary pick:
     1. Any element of `titles[]` contains a `departments[]` label as a
        substring → that's primary (matches faculty self-identification).
     2. Else lowest filter ID (oldest canonical SEAS dept).
     3. Else (faculty absent from all filters) → fallback to old title
        regex, and emit `department_source: "fallback_title"` for review.
   - `department_source: "filter" | "fallback_title"`.

2c. Defensive check at the end of Pass B: assert `slugs(A) == slugs(B) ∪
    fallbacks`. Fail loudly if not.

### 3. Update `types.ts`

Add `departments: string[]` and `department_source: string` to `ScrapedLab`.

### 4. Patch `load_labs.py`

4a. Add to `DEPARTMENT_MAP`:
   - `"Engineering Science": "General Engineering"`
   - `"First Year Engineering": "General Engineering"`

4b. Keep `PROFESSOR_DEPARTMENT_OVERRIDES` as belt-and-suspenders. Mark
    review-for-removal after one clean scrape.

### 5. Safety gate before Supabase write

5a. New scrape writes to `data/labs_new.json`, not `labs.json`. Current
    file untouched.

5b. Add `scripts/lab_scraper/diff-labs.ts`:
   - Pull current Supabase `labs` → `data/supabase-snapshot.json` (also
     serves as the backup).
   - Diff `labs_new.json` vs snapshot.
   - Print added/removed/changed by slug, flagging changes to
     `is_recruiting`, `department`, `email`.

5c. Human review of diff before `load:supabase`.

### 6. Test single filter first

6a. Single-filter dry run before the full crawl. Inspect the ~40 faculty
    returned, confirm no crashes, dept tags look sane.

6b. Only then run full crawl.

### 7. Apply + validate

7a. `npm run load:supabase` (points at `labs_new.json`).

7b. `docker exec tcf_django python manage.py load_labs`.
    Expected: `Done: 352 updated, 0 skipped.`

7c. Re-run Supabase audit script from the earlier session. Expect
    `Unmatched: 0`.

7d. Spot-check 5 depts in the Django UI at `/lab-department/<id>/` —
    counts vs SEAS.

### 8. Documentation

8a. `doc/lab-data.md`:
   - Pipeline diagram note: "filter-based, with title fallback".
   - Mention `dept-filters.json` as an audit artifact.
   - Note the two `DEPARTMENT_MAP` additions.
   - Flag `departments[]` as populated-but-unconsumed (future UI work).

8b. `scripts/lab_scraper/README.md`:
   - Add dry-run + diff instructions.
   - Describe the `labs_new.json` safety gate.

### 9. Rollback

If new data looks worse than old, revert the scraper commits and re-upsert
from `data/supabase-snapshot.json`.

## Acceptance

Nothing ships without **all** of:

- [ ] Scraper produces 352 ± 2 unique slugs.
- [ ] `department_source == "fallback_title"` count is **zero**, or each
      is individually justified in the PR description.
- [ ] `load_labs` → `0 skipped`.
- [ ] Recruiting count within 96 ± 10. Sharp drops get investigated.
- [ ] Diff report attached to PR, no unexplained field changes.
- [ ] UI spot-check of 5 departments matches SEAS.

## Artifacts to commit

- `scripts/lab_scraper/scrape-listing.ts` — refactored
- `scripts/lab_scraper/types.ts` — `departments[]` + `department_source`
- `scripts/lab_scraper/diff-labs.ts` — new
- `scripts/lab_scraper/data/dept-filters.json` — new, source-of-truth
  snapshot of SEAS filter IDs
- `scripts/lab_scraper/README.md` — updated
- `tcf_website/management/commands/load_labs.py` — two new `DEPARTMENT_MAP`
  keys
- `doc/lab-data.md` — updated

## Not in scope

- Joint-appointment UI in Django (uses `departments[]`). Data is captured
  now, consumption is a future PR.
- Removal of `PROFESSOR_DEPARTMENT_OVERRIDES`. Revisit after one clean run.
- Non-SEAS sources (A&S, SOM, Physics, Data Science).
