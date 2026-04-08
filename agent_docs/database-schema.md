# theCourseForum Database Schema

Dump: `db/latest.dump` (PostgreSQL custom format, created 2026-03-11)
Database: `tcf_db`, owner: `tcf_django`, PostgreSQL 17.5
Extension: `pg_trgm` (trigram fuzzy search)

---

## Row Counts

| Table | Rows |
|-------|------|
| school | 12 |
| department | 121 |
| subdepartment | 283 |
| course | 16,353 |
| instructor | 14,227 |
| section | 359,736 |
| semester | 66 |
| review | 0 |
| user | 0 |
| vote | 0 |
| question | 0 |
| answer | 0 |
| coursegrade | 12,655 |
| courseinstructorgrade | 37,670 |
| club | 1,156 |
| clubcategory | 9 |
| lab | 284 |
| labreview | 0 |
| labvote | 0 |
| discipline | 11 |
| savedcourse | 0 |
| blogpost | 0 |

Note: review, user, vote, question, answer, savedcourse are empty in this dump (user data stripped for privacy).

---

## Academic Hierarchy

```
School (12)
  └── Department (121)
        └── Subdepartment (283) — has mnemonic (e.g. "CS", "ENCW")
              └── Course (16,353) — title, number, combined_mnemonic_number
                    └── Section (359,736) — per-semester offering
                          ├── SectionTime — day booleans + start/end time
                          └── Instructor (M2M via section_instructors)
```

### school
| Column | Type | Notes |
|--------|------|-------|
| id | serial PK | |
| name | varchar(255) | unique |
| description | text | |
| website | varchar(200) | |

### department
| Column | Type | Notes |
|--------|------|-------|
| id | serial PK | |
| name | varchar(255) | unique per school |
| description | text | |
| website | varchar(200) | |
| school_id | FK → school | |

### subdepartment
| Column | Type | Notes |
|--------|------|-------|
| id | serial PK | |
| name | varchar(255) | |
| description | text | |
| mnemonic | varchar(255) | unique (e.g. "CS", "ECE") |
| department_id | FK → department | |

### semester
| Column | Type | Notes |
|--------|------|-------|
| id | serial PK | |
| year | int | e.g. 2026 |
| season | varchar(7) | e.g. "Spring", "Fall" |
| number | int | unique, sortable (higher = more recent) |

### course
| Column | Type | Notes |
|--------|------|-------|
| id | serial PK | |
| title | varchar(255) | GIN trigram index |
| description | text | |
| number | int | course number |
| subdepartment_id | FK → subdepartment | unique with number |
| semester_last_taught_id | FK → semester | |
| combined_mnemonic_number | varchar(255) | GIN trigram index (e.g. "CS 2150") |

### instructor
| Column | Type | Notes |
|--------|------|-------|
| id | serial PK | |
| first_name | varchar(255) | GIN trigram index |
| last_name | varchar(255) | GIN trigram index |
| full_name | varchar(511) | GIN trigram index |
| email | varchar(254) | |
| hidden | boolean | |

M2M with department via `instructor_departments` junction table.

### section
| Column | Type | Notes |
|--------|------|-------|
| id | serial PK | |
| sis_section_number | int | unique per semester |
| topic | text | |
| units | varchar(10) | |
| section_type | varchar(255) | |
| course_id | FK → course | |
| semester_id | FK → semester | |
| section_times | varchar(255) | |
| cost | varchar(255) | |
| enrollment_limit | int | nullable |
| enrollment_taken | int | nullable |
| waitlist_limit | int | nullable |
| waitlist_taken | int | nullable |

M2M with instructor via `section_instructors` junction table.

### sectiontime
| Column | Type | Notes |
|--------|------|-------|
| id | identity PK | |
| monday–friday | boolean | one column per day |
| start_time | time | |
| end_time | time | |
| section_id | FK → section | |

---

## Reviews & Voting

### review
| Column | Type | Notes |
|--------|------|-------|
| id | serial PK | |
| text | text | review body |
| instructor_rating | smallint | ≥0 |
| difficulty | smallint | ≥0 |
| recommendability | smallint | ≥0 |
| enjoyability | smallint | ≥0 |
| hours_per_week | smallint | ≥0 |
| amount_reading | smallint | ≥0 |
| amount_writing | smallint | ≥0 |
| amount_group | smallint | ≥0 |
| amount_homework | smallint | ≥0 |
| created | timestamptz | |
| modified | timestamptz | |
| course_id | FK → course | nullable |
| instructor_id | FK → instructor | nullable |
| semester_id | FK → semester | |
| user_id | FK → user | |
| hidden | boolean | moderation flag |
| email | varchar | nullable |
| toxicity_category | varchar | |
| toxicity_rating | int | |
| club_id | FK → club | nullable (club reviews) |

Review ratings are smallint ≥0 (not 1-5 like LabForum; check validators in Django model).

### vote
| Column | Type | Notes |
|--------|------|-------|
| id | serial PK | |
| value | int | |
| review_id | FK → review | unique with user_id |
| user_id | FK → user | |

---

## Q&A

### question
| Column | Type | Notes |
|--------|------|-------|
| id | identity PK | |
| text | text | |
| created | timestamptz | |
| course_id | FK → course | |
| instructor_id | FK → instructor | |
| user_id | FK → user | |

### answer
| Column | Type | Notes |
|--------|------|-------|
| id | identity PK | |
| text | text | |
| created | timestamptz | |
| question_id | FK → question | unique with user_id |
| semester_id | FK → semester | |
| user_id | FK → user | |

### votequestion / voteanswer
Same pattern as vote: `id`, `value`, `question_id`/`answer_id`, `user_id` (unique per user per item).

---

## Grades

### coursegrade
Aggregate grade distribution per course.

| Column | Type | Notes |
|--------|------|-------|
| id | serial PK | |
| average | double | nullable |
| a_plus through c_minus | int | counts |
| dfw | int | D/F/W count |
| total_enrolled | int | |
| course_id | FK → course | nullable |

### courseinstructorgrade
Grade distribution per course+instructor pair.

Same columns as coursegrade, plus `instructor_id` FK → instructor.

---

## User

### user (extends AbstractUser)
| Column | Type | Notes |
|--------|------|-------|
| id | serial PK | |
| username | varchar(150) | unique |
| password | varchar(128) | |
| email | varchar(254) | |
| first_name | varchar(150) | |
| last_name | varchar(150) | |
| computing_id | varchar(20) | unique (UVA computing ID) |
| graduation_year | int | nullable |
| is_superuser | boolean | |
| is_staff | boolean | |
| is_active | boolean | |
| last_login | timestamptz | nullable |
| date_joined | timestamptz | |

Auth: `social_auth_*` tables (Python Social Auth) — UVA SSO integration.

---

## Clubs

### clubcategory
| Column | Type | Notes |
|--------|------|-------|
| id | identity PK | |
| name | varchar(255) | unique |
| description | text | |
| slug | varchar(255) | unique |

### club
| Column | Type | Notes |
|--------|------|-------|
| id | identity PK | |
| name | varchar(255) | |
| description | text | |
| combined_name | varchar(255) | GIN trigram index |
| application_required | boolean | |
| photo_url | varchar(255) | |
| meeting_time | varchar(255) | |
| category_id | FK → clubcategory | |

Reviews can link to a club via `review.club_id`.

---

## Labs

### lab
| Column | Type | Notes |
|--------|------|-------|
| id | serial PK | |
| pi_name | varchar(255) | PI full name |
| slug | varchar(255) | unique, auto-generated from pi_name |
| department_id | FK → department | |
| title | varchar(255) | e.g. "Professor", "Associate Professor" |
| description | text | research bio |
| research_areas | text | comma-separated interests |
| website | varchar(200) | optional |
| email | varchar(254) | optional |
| phone | varchar(50) | optional |
| office | varchar(255) | optional |
| photo_url | varchar(512) | optional |
| profile_url | varchar(200) | optional |
| google_scholar | varchar(200) | optional |
| github_url | varchar(200) | optional |
| education | text | optional |
| is_recruiting | boolean | default false |
| combined_search_text | varchar(1024) | GIN trigram index, auto-populated |

### labreview
| Column | Type | Notes |
|--------|------|-------|
| id | serial PK | |
| lab_id | FK → lab | |
| user_id | FK → user | |
| overall | smallint | 1-5 rating |
| mentorship | smallint | 1-5 rating |
| work_life | smallint | 1-5 rating |
| friendliness | smallint | 1-5 rating |
| inclusivity | smallint | 1-5 rating |
| responsiveness | smallint | 1-5 rating |
| hours_per_week | smallint | 0-80 |
| role | varchar(20) | undergrad_ra, grad_ra, postdoc, staff, other |
| period | varchar(100) | e.g. "Fall 2024 - Spring 2025" |
| how_joined | text | optional |
| advice | text | optional |
| would_recommend | boolean | default true |
| text | text | review body, optional |
| hidden | boolean | moderation flag |
| toxicity_rating | int | |
| toxicity_category | varchar | |
| supabase_id | uuid | nullable, unique — used for idempotent sync from Supabase |
| created | timestamptz | |
| modified | timestamptz | |

### labvote
| Column | Type | Notes |
|--------|------|-------|
| id | serial PK | |
| value | int | -1 or 1 |
| user_id | FK → user | unique with review_id |
| review_id | FK → labreview | |

---

## Other Tables

### discipline
Lookup table: `id`, `name` (unique). M2M with course via `course_disciplines`.

### savedcourse
User-saved course+instructor pair: `user_id`, `course_id`, `instructor_id` (unique triple), `rank`, `notes`, `created`.

### schedule / scheduledcourse
User schedule builder: schedule belongs to user, scheduledcourse links to section+instructor.

### blogpost
Blog: `title`, `subtitle`, `slug`, `author`, `thumbnail_image`, `body`, `created_date`, `mod_date`.

### silk_*
Django Silk profiling tables (request/response/query logging). Not application data.

### social_auth_*
Python Social Auth tables (association, code, nonce, partial, usersocialauth). Handles UVA SSO.

---

## Key Indexes

- **Trigram (GIN)**: `course.title`, `course.combined_mnemonic_number`, `instructor.first_name`, `instructor.last_name`, `instructor.full_name`, `club.combined_name`, `lab.combined_search_text` — powers fuzzy search
- **Composite**: `(course_id, instructor_id)` on review and courseinstructorgrade — fast lookups
- **Semester**: `(semester_id, course_id)` on section — fast per-semester queries
- **Lab**: `(lab_id)` on labreview, `(user_id, -created)` on labreview, `(review_id)` on labvote

## Django App

All models live in `tcf_website/models/models.py` under the `tcf_website` app. Table prefix: `tcf_website_`.
