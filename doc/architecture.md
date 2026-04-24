# theCourseForum2 Architecture

A map of the codebase. Read this when you need to find where something lives or understand how a request becomes a response.

## High-level layout

```
theCourseForum2/
├── manage.py
├── tcf_core/             Django project (settings, root urls, wsgi/asgi)
├── tcf_website/          The single Django app: all models, views, templates, statics
├── scripts/lab_scraper/  Standalone TypeScript scraper for SEAS lab data
├── doc/                  Long-form developer docs
├── docs/superpowers/     Design specs and implementation plans (this file lives in doc/, not docs/)
├── requirements/         Pinned Python deps split by env (base, dev, ci)
├── db/                   Mounted volume for local Postgres backups
├── Dockerfile
└── docker-compose.yml
```

`tcf_core` is the Django project shell: settings layered as `base`/`dev`/`ci`/`prod`, the root URLConf, WSGI/ASGI entry. `tcf_website` is the app where everything else lives.

## `tcf_website/` internals

```
tcf_website/
├── apps.py                Django AppConfig (no signals wired)
├── admin.py               Admin registrations (uses wildcard import; see Quirks)
├── forms.py
├── urls.py                URL patterns for the whole app
├── utils.py
├── models/                Domain-scoped model package (see below)
├── views/                 Views grouped by feature
├── templates/             HTML templates (Django templating)
├── static/                CSS, JS, images
├── tests/                 Test suite (one file per feature surface)
├── management/commands/   Custom manage.py subcommands (load_*, seed_*, fetch_*)
├── migrations/            Auto-generated database migrations
├── pagination.py          Shared pagination helpers
├── search/                Trigram and elasticsearch search helpers
├── schedule/              Schedule sub-package: services, calendar, add_course
├── templatetags/          Custom template filters and tags
└── legacy_models.py       Frozen tCF 1.0 schema; only for data migration scripts
```

## `models/` package

Split by domain. Each file is independently navigable.

```
tcf_website/models/
├── __init__.py            Re-exports the 25-class public surface
├── user.py                User
├── club.py                ClubCategory, Club
├── course.py              School, Department, Subdepartment, Discipline,
│                          Instructor, Semester, Section, SectionTime,
│                          Course, CourseGrade, CourseInstructorGrade
├── schedule.py            Schedule, ScheduleBookmark, ScheduledCourse
├── review.py              Review, Vote, ReviewLLMSummary
├── lab.py                 Lab, LabReview, LabVote
└── question.py            Question, Answer, VoteQuestion, VoteAnswer
```

**Module load order:** `user → club → course → schedule → review → lab → question`. Each submodule only imports from modules loaded before it. The single exception is `course.py`, which imports `Review` at the end of the file because course methods reference Review while review.py needs Course/Instructor/Semester for its FKs. Both modules load cleanly because all class definitions in `course.py` complete before the deferred end-of-file import fires.

**Cross-submodule foreign keys** use string references (`"User"`, `"Course"`, `"Review"`) so Django resolves them lazily through the app registry. Same-submodule FKs use direct class references.

**New code should import from the specific submodule:** `from tcf_website.models.lab import Lab`, not `from tcf_website.models import Lab`. The package re-export still works for backward compatibility, but submodule imports make dependencies visible at a glance.

## `views/` modules

Grouped by feature, mostly mirroring `templates/site/`:

```
tcf_website/views/
├── account/        User profile, settings
├── auth/           Login, logout, OAuth callbacks
├── catalog/        Browse courses, departments, schools
├── clubs/          Club catalog + reviews
├── courses/        Course detail, instructor pages
├── home/           Landing page
├── instructors/    Instructor detail
├── lab.py          Lab catalog, lab_detail, lab_department, lab_review forms
├── qa/             Question/Answer flows
├── review/         Course review create/edit/delete
└── schedule/       Schedule build, share, compare
```

## Templates and static assets

```
tcf_website/templates/
├── 404.html
├── lab/                       (legacy lab template root)
└── site/
    ├── account/
    ├── catalog/
    ├── clubs/
    ├── common/                Shared partials (navbar, footer, breadcrumbs)
    ├── courses/
    ├── home/
    ├── instructors/
    ├── lab/                   Active LabForum templates: lab_detail, lab_review, research_guide
    ├── review/
    └── schedule/
```

```
tcf_website/static/
├── base/                      Logos, favicons, fonts shared across pages
├── css/
│   ├── base.css
│   └── site/
│       ├── components/        Reusable UI (search, breadcrumb, card, vote buttons)
│       └── pages/             Per-page CSS (lab_detail.css, course_detail.css, …)
├── js/                        Per-page JS (lab_review.js, schedule.js, …)
└── lab/                       Lab-specific assets used by both legacy + active templates
```

CSS and JS are not bundled. Each page pulls in the components and page-specific files it needs.

## LabForum data flow

```
SEAS faculty pages
      │
      ▼
scripts/lab_scraper/   (TypeScript, two-pass scraper with safety-gated diff tool)
      │  emits normalized JSON
      ▼
Supabase staging       (intermediate review-and-approve layer)
      │  exported snapshots fed to Django
      ▼
manage.py load_labs        → Lab rows
manage.py seed_lab_departments → Department rows for SEAS labs
manage.py seed_lab_reviews     → Sample LabReview rows for development only
      │
      ▼
tcf_website/models/lab.py     Lab, LabReview, LabVote
      │
      ▼
tcf_website/views/lab.py      lab_detail, lab_department, lab_review_create
      │
      ▼
tcf_website/templates/site/lab/  Rendered HTML
```

The scraper is documented in detail in [scripts/lab_scraper/README.md](../scripts/lab_scraper/README.md) and the data model in [doc/lab-data.md](lab-data.md). Always run the scraper's safety-gated diff before applying changes to production.

## Settings layering

`tcf_core/settings/`:

```
__init__.py        Loads the right module per DJANGO_SETTINGS_MODULE
base.py            Shared settings: INSTALLED_APPS, MIDDLEWARE, DB, AUTH_USER_MODEL
dev.py             Local Docker development
ci.py              GitHub Actions test env
prod.py            Heroku production
```

`AUTH_USER_MODEL = "tcf_website.User"` is label-based, not path-based, so the `User` class can move between files inside `tcf_website` without breaking auth.

## CI

`.github/workflows/ci.yml` runs:

1. `python manage.py migrate && coverage run manage.py test` — full Django test suite.
2. Coverage report is generated but no minimum threshold is enforced (yet).
3. `pylint tcf_website tcf_core` — Python lint.
4. ESLint with `.config/.eslintrc.yml` — JS lint.

## Quirks worth knowing

- **`admin.py` uses `from .models import *`.** Anything bound at the package level by `models/__init__.py` is visible to admin. The current `__init__.py` deliberately omits `VoteQuestion` and `VoteAnswer` to match the historical admin surface; admin doesn't register them.
- **`legacy_models.py` is intentionally outside the `models/` package.** It carries `# pylint: skip-file` and exists only for migrating data from tCF 1.0. Do not re-export it.
- **Scraper data is provisional until the safety gate runs.** Do not push raw scraper output to production tables. The diff tool in `scripts/lab_scraper/` exists for this reason.
- **No signal wiring.** `tcf_website/apps.py` has no `ready()` override, so there are no global signal handlers to track down when debugging.
- **The schedule sub-package** (`tcf_website/schedule/`) is not a Django app; it's a Python sub-package inside `tcf_website` that holds schedule-specific services, forms, and calendar logic. Schedule models still live in `tcf_website/models/schedule.py`.

## Where to read next

- [doc/dev.md](dev.md) — environment setup
- [doc/lab-data.md](lab-data.md) — LabForum data model and scraper details
- [doc/grade-data.md](grade-data.md) — UVA grade data ingestion
- [doc/semester-data.md](semester-data.md) — semester ingestion (Lou's List, SIS)
- [doc/useful-commands.md](useful-commands.md) — common manage.py invocations
- [scripts/lab_scraper/README.md](../scripts/lab_scraper/README.md) — scraper architecture and safety workflow
- [docs/superpowers/specs/](../docs/superpowers/specs/) — design specs for in-flight work
