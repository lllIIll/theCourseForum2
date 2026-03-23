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

## Open Questions

1. Do we have lab data to load, or build with mock data first?
2. Should labs link to a new lab detail page (`/lab/<slug>/`) or reuse course pattern?
3. Does the searchbar also need to search labs (radio toggle in navbar)?
4. Should the sidebar nav get a "Labs" entry, or is the browse toggle enough?
