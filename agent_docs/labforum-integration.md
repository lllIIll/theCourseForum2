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

## What Was Changed (Implemented)

### 1. Mode Toggle (`templates/club/mode_toggle.html`)
- 3-way toggle with Courses / Clubs / Labs in both link and radio variants
- Radio: `#search-mode-labs` input + label added

### 2. Mode Toggle CSS (`static/club/mode_toggle.css`)
- Slider/indicator width: `calc((100% - 8px) / 3)` for link, `calc((100% - 4px) / 3)` for radio
- `slide-middle` (clubs) and `slide-right` (labs) transform positions
- Container max-width: `350px`, radio min-width: `250px`

### 3. `parse_mode()` in 3 files
- Returns `(mode, is_club, is_lab)` 3-tuple in `views/browse.py`, `views/review.py`, `views/search.py`
- All callers updated to destructure the third value

### 4. Browse view (`views/browse.py`)
- `elif is_lab:` branch queries Schools with Departments that have Labs via `prefetch_related`
- Dynamic filter (`.filter(lab__isnull=False)`) — future-proofs for non-SEAS expansion

### 5. Browse template (`templates/browse/browse.html`)
- `{% elif is_lab %}` block renders lab schools accordion
- Title: "Browse by Department" in lab mode

### 6. Lab browse template (`templates/lab/browse_school.html`)
- School accordion → Department groups → PI name list with recruiting badges
- Links to `/lab/<slug>/`

### 7. Django Models
- `Lab` — FK to Department, slug auto-generated from pi_name, GIN index on combined_search_text
- `LabReview` — 6 rating dimensions, role, period, advice, with sort/paginate/vote methods
- `LabVote` — same pattern as Vote, unique constraint on (user, review)

### 8. Lab Data Loading
- `load_labs` — fetches 352 SEAS faculty from Supabase REST API, maps department strings via `DEPARTMENT_MAP`, uses `update_or_create` on slug. Result: 337 created, 15 skipped (no dept match). Runs automatically on `docker-compose up`.
- `load_lab_reviews` — fetches approved reviews from Supabase `reviews` table (joined with `labs` on slug), maps to `LabReview` fields, uses `supabase_id` for idempotent updates. Requires a sentinel `supabase_import` system user (created automatically). Runs automatically on `docker-compose up`.
- `seed_lab_reviews` — dev-only; creates 2 sample reviews (rating≈4) per lab so metrics UI is visible. Defaults to first 10 labs; use `--all` for all labs. Run `--clear` before production. Does **not** run automatically — must be invoked manually.

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

### Lab Detail Page (Implemented — `/lab/<slug>/`)
- **Breadcrumb:** Labs / School / Department / PI Name
- **Header:** PI name (h1) + department + title, recruiting badge
- **Info card:** Research description (left), photo + contact links (right), research area tags
- **Metrics panel:** 3 large stat cards (Overall, Hrs/Week, Recommend%) + 5 rating bars (Mentorship, Work-Life, Friendliness, Inclusivity, Responsiveness). Bar widths computed server-side as `value × 20` (1–5 → 0–100%). Uses `course_instructor.css` classes. Section hidden when no reviews exist.
- **Reviews tab:** Count + "Add your review!" button, sort dropdown, paginated review cards
- **Review cards:** Role/period header, 6 rating badges, text, advice, upvote/downvote buttons

### Lab Review Form (Implemented — `/reviews/new/?mode=labs&lab=<id>`)
- Role dropdown, period input, 6 rating selects, hours/week, would-recommend toggle
- Review text (100+ words), how joined, advice for future students

### Additional Lab Routes
- `/lab/<slug>/` → `lab_detail` view
- `/lab-reviews/<id>/upvote/` → `lab_upvote` view
- `/lab-reviews/<id>/downvote/` → `lab_downvote` view
- Search: `/search/?mode=labs&q=<query>` — trigram search on combined_search_text

## Resolved Decisions

1. **Lab data:** 352 SEAS faculty scraped, 337 imported via `load_labs` management command (15 skipped — no matching Django department)
2. **URLs:** Dedicated `/lab/<slug>/` pages (not reusing course pattern)
3. **Search:** Searchbar radio toggle includes labs; trigram search on PI name + research areas + department
4. **Navigation:** Browse toggle is the primary entry point (no sidebar entry)
