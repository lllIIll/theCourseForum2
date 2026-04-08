# LabForum — Project Context

## What Is LabForum?

"theCourseForum for research labs." A platform where UVA students browse research labs, read anonymous peer reviews, and make informed decisions about where to do research.

## Stack Decision

LabForum is built inside the theCourseForum2 repo using the **same stack**:
- **Python / Django** (not Next.js)
- **PostgreSQL** (not Supabase)
- **Bootstrap 4** (not Tailwind)
- **JavaScript / jQuery** (not React)

This means LabForum shares infrastructure, auth (UVA SSO via Python Social Auth), and patterns with theCourseForum.

## theCourseForum → LabForum Mapping

| theCourseForum | LabForum |
|---|---|
| Course | Lab / Research Group |
| Instructor | Principal Investigator (PI) |
| Department (academic) | Department (research) |
| Course Rating | Lab Rating |
| Instructor Quality | Mentorship Quality |
| Enjoyability | Lab Culture / Friendliness |
| Difficulty | Workload / Hours per Week |
| Recommendability | Would Recommend |
| Grade Distribution | N/A |
| Schedule Builder | N/A |
| Semester | Period in Lab (start/end) |
| Student role | Role (Undergrad RA, Grad, Postdoc, Staff) |

## Planned Review Dimensions

| Metric | Field | Scale | Notes |
|---|---|---|---|
| Overall | `overall` | 1-5 | |
| Mentorship | `mentorship` | 1-5 | PI investment in your growth |
| Lab Culture | `lab_culture` | 1-5 | Welcoming / collaborative atmosphere |
| Responsiveness | `responsiveness` | 1-5 | PI responsiveness to questions |
| Independence | `independence` | 1-5 | Autonomy over research direction |
| Entry Bar | `entry_selectivity` | 1-5 | 1=very open, 5=highly selective |
| Hours/Week | `hours_per_week` | integer | |

## Data Source

- SEAS Faculty Directory (engineering.virginia.edu/faculty) — 352 faculty scraped
- "Currently Recruiting" badge is a key differentiator
- Future expansion: Data Science, Physics, Arts & Sciences, Medicine

## What Has Been Built

- **Models:** `Lab`, `LabReview`, `LabVote` in `tcf_website/models/models.py`
  - `LabReview` rating dimensions redesigned: `mentorship`, `lab_culture`, `responsiveness`, `independence`, `entry_selectivity` (migration `0031`)
  - `LabReview` has a `supabase_id` UUID field (migration `0030`) for idempotent syncing
  - `LabReview.paginate()` handles both `PageNotAnInteger` and `EmptyPage`
- **Migrations:** `0029_lab_labreview_labvote.py`, `0030_labreview_supabase_id.py`
- **Data loading:**
  - `load_labs` — syncs 352 SEAS faculty from Supabase REST API into Django `Lab` table (337 created, 15 skipped — no dept match); runs automatically on `docker-compose up`
  - `load_lab_reviews` — syncs approved reviews from Supabase `reviews` table into Django `LabReview`; runs automatically on `docker-compose up`
  - `seed_lab_reviews` — dev-only; creates 2 sample reviews (rating≈4) per lab so metrics UI is visible. Defaults to first 10 labs; use `--all` for all labs. Run `--clear` before production. Does **not** run automatically — must be invoked manually.
- **Browse:** 3-way mode toggle (Courses/Clubs/Labs), lab browse page grouped by school/department
- **Detail page:** `/lab/<slug>/` with PI info card, redesigned metrics panel, paginated reviews, voting
  - Metrics: 3 large stat cards (Overall, Hrs/Week, Recommend%) + 5 rating bars (Mentorship, Work-Life, Friendliness, Inclusivity, Responsiveness)
  - Bar widths computed server-side in view; CSS from `course_instructor.css` (already imported)
  - Metrics section hidden when no reviews exist
- **Review form:** `/reviews/new/?mode=labs&lab=<id>` with 6 rating dimensions, role, period, advice
- **Search:** Trigram search on `combined_search_text`, results grouped by department
- **Profile:** User's lab reviews shown in separate section on profile page
- **Tests:** 20 tests covering models and views

## What Is Not Yet Built

- Q&A system for labs
- Non-SEAS lab data (Data Science, Physics, Medicine)
- Dark mode support
- Real Supabase reviews (Supabase `reviews` table currently has 0 rows; `load_lab_reviews` is ready when data arrives)

## Current Dev Data State

| Table | Rows | Source |
|-------|------|--------|
| `lab` | 337 | `load_labs` (Supabase SEAS faculty) |
| `labreview` | 20 | `seed_lab_reviews` — 2 reviews × first 10 labs, user `seed_data`, all ratings ≈ 4 |
| `labvote` | 0 | — |

Run `python manage.py seed_lab_reviews --all` to extend seed reviews to all 337 labs.
Run `python manage.py seed_lab_reviews --clear` before production to remove seed data.
