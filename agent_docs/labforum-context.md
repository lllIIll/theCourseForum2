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

| Metric | Scale |
|---|---|
| Overall | 1-5 |
| Mentorship | 1-5 |
| Work-Life Balance | 1-5 |
| Friendliness | 1-5 |
| Inclusivity | 1-5 |
| Responsiveness | 1-5 |
| Hours/Week | integer |

## Data Source

- SEAS Faculty Directory (engineering.virginia.edu/faculty) — 352 faculty scraped
- "Currently Recruiting" badge is a key differentiator
- Future expansion: Data Science, Physics, Arts & Sciences, Medicine

## What Has Been Built

- **Models:** `Lab`, `LabReview`, `LabVote` in `tcf_website/models/models.py`
- **Migration:** `0024_lab_labreview_labvote.py`
- **Data loading:** `load_labs` management command (284 SEAS faculty imported from JSON)
- **Browse:** 3-way mode toggle (Courses/Clubs/Labs), lab browse page grouped by school/department
- **Detail page:** `/lab/<slug>/` with PI info card, stats grid, paginated reviews, voting
- **Review form:** `/reviews/new/?mode=labs&lab=<id>` with 6 rating dimensions, role, period, advice
- **Search:** Trigram search on `combined_search_text`, results grouped by department
- **Profile:** User's lab reviews shown in separate section on profile page
- **Tests:** 20 tests covering models and views

## What Is Not Yet Built

- Q&A system for labs
- Non-SEAS lab data (Data Science, Physics, Medicine)
- Dark mode support
- Supabase migration (lab data currently loaded from JSON)
