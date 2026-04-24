# LabForum Repo Organization — Part 1

**Branch:** `LabForum1`
**Date:** 2026-04-24
**Scope:** Two commits. Organize the models monolith into domain submodules and write the navigation docs.
**Companion:** [2026-04-24-labforum-quality-polish-deferred.md](./2026-04-24-labforum-quality-polish-deferred.md) tracks the optional polish work (Votable mixin, expanded lab tests, scraper docstrings, CI coverage gate). That work is deferred to a follow-up branch.

## Why we split this in two

The original "raise to Exemplary" plan grew to 5 commits covering organization, deduplication, testing, and CI changes. That's polish work, not organization. Jay is reviewing `LabForum1` for the LabForum feature; bundling code-quality refactors into the same branch bloats the PR. This Part 1 keeps `LabForum1` focused on what's strictly organizational — the navigability win that makes the rest of the codebase easier to read — and defers the rest.

## Goal

Make the repo easier to navigate by:
1. Splitting the 2,224-line `tcf_website/models/models.py` into domain submodules.
2. Writing the architecture and contributor docs that describe the new layout.

That's it. No behavior changes. No feature work. No dedup. No new tests.

## Verified current state

- `tcf_website/models/` is already a package; `models/__init__.py:8-33` re-exports 25 classes from a monolithic `models/models.py`.
- All foreign keys currently use direct class references (e.g. `models.ForeignKey(Review, ...)` at `models/models.py:1445`). Splitting across files requires converting cross-submodule FKs to **string references** (`"Review"`) to avoid circular imports.
- `tcf_website/admin.py:8` does `from .models import *`. Any class missing from `__init__.py`'s explicit re-export list won't be admin-visible. Pre-existing quirk: `VoteQuestion` and `VoteAnswer` are not currently re-exported. Out of scope here.
- `AUTH_USER_MODEL = "tcf_website.User"` (`tcf_core/settings/base.py:139`) is label-based, so moving the `User` class file is safe as long as the class name stays.
- `apps.py` has no `ready()`. No signal wiring to worry about.
- `legacy_models.py` lives outside the package with `# pylint: skip-file`. Stays where it is.

## Commit 1 — Split `models/models.py` into submodules

**Final layout:**
```
tcf_website/models/
├── __init__.py        re-exports the same 25 public classes
├── course.py          Course, CourseGrade, CourseInstructorGrade, Discipline,
│                      Instructor, School, Section, SectionTime, Semester,
│                      Subdepartment, Department
├── review.py          Review, ReviewLLMSummary, Vote
├── lab.py             Lab, LabReview, LabVote
├── user.py            User
├── club.py            Club, ClubCategory
├── question.py        Question, Answer, VoteQuestion, VoteAnswer
└── schedule.py        Schedule, ScheduleBookmark, ScheduledCourse
```

`models/models.py` (the monolith) gets deleted at the end of the commit.

**Move order** (each step keeps the package importable):
1. `user.py` (no deps)
2. `club.py` (depends on User)
3. `course.py` (School → Department → Subdepartment → Discipline → Instructor → Semester → Section → SectionTime → Course → CourseGrade → CourseInstructorGrade)
4. `schedule.py` (depends on course, user)
5. `review.py` (depends on course, user; Vote FK to Review converted to string ref if Vote stays in same file, kept direct otherwise)
6. `lab.py` (depends on course, user)
7. `question.py` (Question/Answer reference each other; FKs to Review use string ref `"Review"`)
8. Delete the now-empty `models/models.py`.

**Rules of the move:**
- Class names, field names, method bodies, `Meta` blocks, and database table names stay byte-identical.
- Cross-submodule foreign keys become string references (`"User"`, `"Review"`, `"Course"`). Same-module FKs can stay as direct class references.
- No `apps.get_model()` calls at module import time. All class lookups inside methods.
- All existing `# pylint: disable=...` and `# noqa` directives travel with the code they decorate.

**Gate (run after each move and at the end):**
- `python manage.py test` — full suite green.
- `python manage.py makemigrations --check --dry-run` — must report "No changes detected". Any reported change means a `Meta` field accidentally moved.
- `python -c "from tcf_website.models import *; print('ok')"` — wildcard import resolves.
- `pylint tcf_website tcf_core` — clean (or no new warnings vs. baseline).

**Rollback:** single `git revert` brings back the monolith. Nothing outside the package changed.

## Commit 2 — Write `doc/architecture.md` and `CONTRIBUTING.md`

**`doc/architecture.md`** (~200 LoC):
- High-level map: `tcf_core` (settings, urls, wsgi) vs `tcf_website` (the app).
- `models/` package layout (the post-split version), one line per submodule.
- `views/` module boundaries (account, auth, catalog, courses, labs, review, schedule).
- Template and static asset conventions (`templates/site/<feature>/`, `static/css/site/{components,pages}/`).
- LabForum dataflow: SEAS scraper → normalized JSON → Supabase staging → `load_labs` / `seed_lab_reviews` → `Lab`/`LabReview` models → `views/lab.py` → `templates/lab/`.
- Convention: new code imports from the specific submodule (`from tcf_website.models.lab import Lab`) rather than the package root, to keep dependencies legible.
- Known quirks worth flagging: `VoteQuestion`/`VoteAnswer` not re-exported through `__init__.py`; `admin.py` uses `from .models import *`; `AUTH_USER_MODEL` is label-based.

**`CONTRIBUTING.md`** (~100 LoC) at repo root:
- Setup pointer to `doc/dev.md`.
- Branch conventions (feature branches off `dev`).
- Test-before-commit expectation: `python manage.py test` must pass.
- Linter commands: `pylint`, `black`, `isort`, ESLint with the exact flags CI uses.
- How to run the lab scraper safely (pointer to `scripts/lab_scraper/README.md`).
- PR expectations: title under 70 chars, description with summary + test plan.

**Gate:** visual review. No markdownlint configured in repo.

## Risk register

| Risk | Mitigation |
|---|---|
| Circular import between split modules | All cross-submodule FKs use string references |
| `admin.py`'s wildcard import drops a class | Diff `__init__.py`'s re-export list before vs. after; must be a superset of the original |
| `makemigrations` sees a Meta delta after the move | Move bodies verbatim; run `--check` after every step |
| Pylint disables don't carry to submodules | Move directives with the code they decorate |

## Out of scope (deferred to Part 2)

See [2026-04-24-labforum-quality-polish-deferred.md](./2026-04-24-labforum-quality-polish-deferred.md):
- Votable mixin (4-class dedup)
- Expanded lab tests (pagination, toxicity filter, bar widths, vote annotations, lab_department coverage)
- Scraper docstrings
- CI coverage threshold gate
- Re-exporting `VoteQuestion`/`VoteAnswer` so admin can register them

## Approval

User has approved the split-in-two approach. Proceeding to execution. No additional review checkpoint between this spec and the implementation commits.
