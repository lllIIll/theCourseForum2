# LabForum Integration Plan

## Integration Point

LabForum integrates into the existing browse page (`/browse/`) as a third tab alongside Courses and Clubs.

**Current flow:** `?mode=courses` | `?mode=clubs`
**New flow:** `?mode=courses` | `?mode=clubs` | `?mode=labs`

## How the Existing Toggle Works

### Mode Toggle Component (`templates/club/mode_toggle.html`)
- Two variants: "link" (browse page) and "radio" (searchbar)
- Link variant uses `?mode=courses` / `?mode=clubs` query params
- Radio variant uses hidden radio inputs for the searchbar
- Sliding indicator highlights active option (orange `#d75626`)

### Browse View (`views/browse.py`)
- `parse_mode(request)` reads `?mode` param, defaults to `"courses"`
- Returns `(mode, is_club)` tuple
- `browse()` view branches: if `is_club` → load club categories, else → load schools
- Schools accordion: School → Department list (links to `/department/<id>/`)
- Clubs accordion: ClubCategory → Club list (links to course view with `?mode=clubs`)

### Browse Template (`templates/browse/browse.html`)
- Includes `mode_toggle.html` in header row
- Conditionally renders clubs or courses accordion
- JS handles accordion expand/collapse with chevron toggle

### Accordion Pattern (reused for both modes)
- `school.html`: card with blue header → collapse body → `<ul>` of department links
- `browse_category.html`: same pattern → `<ul>` of club links
- Both use Bootstrap collapse with `data-toggle="collapse"`

## What Needs to Change

### 1. Mode Toggle (`templates/club/mode_toggle.html`)
- Add "Labs" as third option in both link and radio variants
- Link: `<a href="?mode=labs">Labs</a>`
- Radio: add `#search-mode-labs` input + label

### 2. Mode Toggle CSS (`static/club/mode_toggle.css`)
- Adjust slider width from `50%` to `33.33%` for 3 options
- Add `slide-middle` and `slide-right` positions (currently only `slide-right`)
- Radio variant: adjust `.toggle-indicator` width and transform positions
- Add CSS rules for `#search-mode-labs:checked` states

### 3. `parse_mode()` in `views/browse.py`
- Handle `mode=labs` → return `(mode, is_club, is_lab)` or use a mode string
- Update all callers that destructure the tuple

### 4. `browse()` view in `views/browse.py`
- Add `elif mode == "labs":` branch
- Load lab data grouped by school/department (or custom grouping)
- Pass to template

### 5. Browse Template (`templates/browse/browse.html`)
- Add `{% elif is_lab %}` block
- Render labs accordion (school → department → lab/PI list)
- Title changes to "Browse by Department" or "Browse Labs"

### 6. New Template: `templates/labs/browse_labs.html` (or similar)
- Accordion card for each school/department group
- List of labs/PIs with links to lab detail pages

### 7. Django Models (new)
- `Lab` model (or `ResearchGroup`) — PI name, department, research areas, etc.
- FK to existing `Department` or new lab-specific department grouping
- Migration to create table

### 8. Lab Data Loading
- Management command or scraper to populate lab data
- 352 SEAS faculty from scraper (see LABFORUM_CONTEXT.md)

## Existing Detail Page Patterns (Reference)

### Course Detail Page (`/course/<mnemonic>/<number>/`)
- **Breadcrumb:** School / Department / Course Code
- **Header:** Course code + title (large), "Add to Schedule" button (right)
- **Semester toggle:** "Spring 2026" | "All" (orange pills, top right)
- **Sort toolbar:** Last Taught | Rating | Difficulty | GPA (orange pills)
- **Description card:** White card with left orange border, "Course Description" heading, body text
- **Instructor rows:** Each instructor gets a row:
  - Left: Blue block with instructor name (large white text, clickable)
  - Right: Stat columns — RATING, DIFFICULTY, GPA, SECTIONS, LAST TAUGHT
  - Stats show em-dash (`—`) when no data, values when available
  - Each row is a link to `/course/<id>/<instructor_id>/`

### Club Detail Page (`/course/<category_slug>/<club_id>?mode=clubs`)
- **Breadcrumb:** Clubs / Category Name / Club Name
- **Header:** Club name (large) + category name (smaller, right)
- **Description card:** White card with left orange border, "Club Description" heading, body text, photo (right), badge ("No Application Required" green or "Application Required")
- **Reviews tab:** "Reviews" tab header, review count + "Add your review!" button (orange)
- **Empty state:** Light blue banner — "No reviews yet. Be the first to write a review!"

### Common UI Patterns Across Both
- Gray page background (`#f0f1f3`)
- White cards with subtle borders
- Left orange accent border on description cards
- Blue (`#4a6fa5`) for name blocks and headers
- Orange (`#d75626`) for CTAs, active pills, toggles
- Breadcrumb: light gray background, `/` separator, last item muted
- Stats use uppercase small labels (RATING, DIFFICULTY, etc.)
- Em-dash (`—`) for missing data

### Lab Detail Page (Planned — mirrors both patterns)
- **Breadcrumb:** Labs / School / Department / PI Name
- **Header:** PI name (large) + department (smaller)
- **Description card:** "Research Description" heading, body text, PI photo (right), badges ("Currently Recruiting" green, research area tags)
- **Info card:** Contact info (email, phone, office), education, external links (Google Scholar, GitHub, website)
- **Stats row:** MENTORSHIP, CULTURE, HOURS/WK, POSITIONS, RECRUITING (mirrors course instructor row pattern)
- **Reviews tab:** Same pattern as clubs — count + "Add your review!" + empty state
- **Q&A tab:** Placeholder (same as clubs)

## Open Questions

1. Do we have lab data to load, or build with mock data first?
2. Should labs link to a new lab detail page (`/lab/<slug>/`) or reuse course pattern?
3. Does the searchbar also need to search labs (radio toggle in navbar)?
4. Should the sidebar nav get a "Labs" entry, or is the browse toggle enough?
